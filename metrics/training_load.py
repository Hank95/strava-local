"""Training load computation (ATL, CTL, TSB)."""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.models import Activity, ActivityMetrics, DailyMetrics
from metrics.config import ATL_DECAY, CTL_DECAY


def get_daily_tss(session: Session, date_str: str) -> float:
    """Get total TSS for a specific date.

    Args:
        session: Database session
        date_str: Date in YYYY-MM-DD format

    Returns:
        Total TSS for that date (0 if no activities)
    """
    # Parse date to get start/end of day
    date = datetime.strptime(date_str, "%Y-%m-%d")
    next_day = date + timedelta(days=1)

    # Sum TSS from activity_metrics for activities on this date
    result = (
        session.query(func.sum(ActivityMetrics.tss))
        .join(Activity, ActivityMetrics.activity_id == Activity.activity_id)
        .filter(Activity.start_time >= date)
        .filter(Activity.start_time < next_day)
        .scalar()
    )

    return result or 0.0


def compute_ema(previous_value: float, new_value: float, decay: float) -> float:
    """Compute exponential moving average.

    Formula: EMA = previous × decay + new × (1 - decay)

    Args:
        previous_value: Previous EMA value
        new_value: New data point
        decay: Decay factor (e.g., 0.857 for 7-day ATL)

    Returns:
        New EMA value
    """
    return previous_value * decay + new_value * (1 - decay)


def compute_training_load(
    session: Session,
    start_date: datetime | None = None,
    force_recompute: bool = False,
) -> None:
    """Compute ATL, CTL, TSB for all days.

    Updates DailyMetrics table with training load values.
    Processes chronologically to properly accumulate EMAs.

    Args:
        session: Database session
        start_date: Start from this date (default: earliest activity)
        force_recompute: If True, recompute all days; otherwise start from last computed
    """
    # Get date range
    if start_date is None:
        earliest = session.query(func.min(Activity.start_time)).scalar()
        if earliest is None:
            return
        start_date = earliest.replace(hour=0, minute=0, second=0, microsecond=0)

    # If not forcing, find where we left off
    if not force_recompute:
        last_computed = (
            session.query(DailyMetrics)
            .filter(DailyMetrics.ctl.isnot(None))
            .order_by(DailyMetrics.date.desc())
            .first()
        )
        if last_computed:
            # Start from day after last computed
            start_date = datetime.strptime(last_computed.date, "%Y-%m-%d") + timedelta(days=1)

    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if start_date > end_date:
        return

    # Get previous day's values to seed EMA
    prev_date_str = (start_date - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_daily = session.query(DailyMetrics).filter_by(date=prev_date_str).first()

    atl = prev_daily.atl if prev_daily and prev_daily.atl else 0.0
    ctl = prev_daily.ctl if prev_daily and prev_daily.ctl else 0.0

    # Process each day
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")

        # Get or create daily metrics
        daily = session.query(DailyMetrics).filter_by(date=date_str).first()
        if daily is None:
            daily = DailyMetrics(date=date_str)
            session.add(daily)

        # Get TSS for this day
        daily_tss = get_daily_tss(session, date_str)
        daily.total_tss = daily_tss
        daily.has_activity = daily_tss > 0

        # Compute EMAs
        atl = compute_ema(atl, daily_tss, ATL_DECAY)
        ctl = compute_ema(ctl, daily_tss, CTL_DECAY)
        tsb = ctl - atl

        daily.atl = round(atl, 1)
        daily.ctl = round(ctl, 1)
        daily.tsb = round(tsb, 1)
        daily.computed_at = datetime.utcnow()

        current_date += timedelta(days=1)

    session.commit()


def get_training_load_series(
    session: Session,
    days: int = 90,
) -> list[dict]:
    """Get training load data for charting.

    Args:
        session: Database session
        days: Number of days to retrieve

    Returns:
        List of dicts with date, atl, ctl, tsb, tss
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    daily_metrics = (
        session.query(DailyMetrics)
        .filter(DailyMetrics.date >= cutoff)
        .order_by(DailyMetrics.date)
        .all()
    )

    return [
        {
            "date": dm.date,
            "atl": dm.atl,
            "ctl": dm.ctl,
            "tsb": dm.tsb,
            "tss": dm.total_tss,
        }
        for dm in daily_metrics
    ]


def get_current_form(session: Session) -> dict:
    """Get current training form status.

    Returns:
        Dict with current ATL, CTL, TSB and interpretation
    """
    today = datetime.now().strftime("%Y-%m-%d")
    daily = session.query(DailyMetrics).filter_by(date=today).first()

    if not daily or daily.ctl is None:
        return {
            "atl": None,
            "ctl": None,
            "tsb": None,
            "status": "No data",
            "description": "Run metrics computation first",
        }

    tsb = daily.tsb or 0

    # Interpret TSB
    if tsb > 25:
        status = "Very Fresh"
        description = "Well recovered, ready for hard efforts"
    elif tsb > 5:
        status = "Fresh"
        description = "Good form for quality training"
    elif tsb > -10:
        status = "Neutral"
        description = "Balanced training load"
    elif tsb > -25:
        status = "Fatigued"
        description = "Accumulated fatigue, consider recovery"
    else:
        status = "Very Fatigued"
        description = "High fatigue, prioritize rest"

    return {
        "atl": daily.atl,
        "ctl": daily.ctl,
        "tsb": daily.tsb,
        "status": status,
        "description": description,
    }
