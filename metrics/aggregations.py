"""Period aggregations (weekly, monthly, yearly)."""

from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from db.models import Activity, ActivityMetrics, DailyMetrics, PeriodAggregation, RollingAverage


def get_week_start(date: datetime) -> datetime:
    """Get Monday of the week containing the date."""
    return date - timedelta(days=date.weekday())


def get_month_start(date: datetime) -> datetime:
    """Get first day of the month."""
    return date.replace(day=1)


def get_year_start(date: datetime) -> datetime:
    """Get first day of the year."""
    return date.replace(month=1, day=1)


def compute_period_aggregation(
    session: Session,
    period_type: str,
    period_start: datetime,
    period_key: str,
) -> PeriodAggregation:
    """Compute aggregation for a specific period.

    Args:
        session: Database session
        period_type: 'week', 'month', or 'year'
        period_start: Start datetime of the period
        period_key: Identifier like '2024-W01', '2024-01', '2024'

    Returns:
        PeriodAggregation record (not yet committed)
    """
    # Calculate period end
    if period_type == "week":
        period_end = period_start + timedelta(days=7)
    elif period_type == "month":
        # Next month
        if period_start.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1)
    else:  # year
        period_end = period_start.replace(year=period_start.year + 1)

    # Query activities in this period
    activities = (
        session.query(Activity)
        .filter(Activity.start_time >= period_start)
        .filter(Activity.start_time < period_end)
        .all()
    )

    # Get or create aggregation record
    agg = (
        session.query(PeriodAggregation)
        .filter_by(period_type=period_type, period_key=period_key)
        .first()
    )
    if agg is None:
        agg = PeriodAggregation(
            period_type=period_type,
            period_start=period_start.strftime("%Y-%m-%d"),
            period_key=period_key,
        )
        session.add(agg)

    # Compute totals
    agg.activity_count = len(activities)
    agg.total_distance = sum(a.distance or 0 for a in activities)
    agg.total_moving_time = sum(a.moving_time or 0 for a in activities)
    agg.total_elevation = sum(a.elevation_gain or 0 for a in activities)
    agg.total_calories = sum(a.calories or 0 for a in activities)

    # Sum TSS from activity_metrics
    tss_sum = (
        session.query(func.sum(ActivityMetrics.tss))
        .join(Activity, ActivityMetrics.activity_id == Activity.activity_id)
        .filter(Activity.start_time >= period_start)
        .filter(Activity.start_time < period_end)
        .scalar()
    )
    agg.total_tss = tss_sum or 0

    # Compute averages
    if agg.activity_count > 0:
        agg.avg_distance = agg.total_distance / agg.activity_count
        agg.avg_tss = agg.total_tss / agg.activity_count

        hrs = [a.avg_hr for a in activities if a.avg_hr]
        agg.avg_hr = sum(hrs) / len(hrs) if hrs else None
    else:
        agg.avg_distance = None
        agg.avg_tss = None
        agg.avg_hr = None

    # Activity days and streaks
    activity_dates = set()
    for a in activities:
        if a.start_time:
            activity_dates.add(a.start_time.strftime("%Y-%m-%d"))
    agg.active_days = len(activity_dates)

    # Compute longest streak
    if activity_dates:
        sorted_dates = sorted(activity_dates)
        current_streak = 1
        longest_streak = 1

        for i in range(1, len(sorted_dates)):
            prev = datetime.strptime(sorted_dates[i - 1], "%Y-%m-%d")
            curr = datetime.strptime(sorted_dates[i], "%Y-%m-%d")

            if (curr - prev).days == 1:
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)
            else:
                current_streak = 1

        agg.longest_streak = longest_streak
    else:
        agg.longest_streak = 0

    # Breakdown by type
    by_type = defaultdict(lambda: {"count": 0, "distance": 0, "time": 0, "tss": 0})
    for a in activities:
        t = a.activity_type or "Unknown"
        by_type[t]["count"] += 1
        by_type[t]["distance"] += a.distance or 0
        by_type[t]["time"] += a.moving_time or 0

    # Add TSS by type
    for activity in activities:
        t = activity.activity_type or "Unknown"
        metrics = session.query(ActivityMetrics).filter_by(activity_id=activity.activity_id).first()
        if metrics and metrics.tss:
            by_type[t]["tss"] += metrics.tss

    agg.by_type = dict(by_type)
    agg.computed_at = datetime.utcnow()

    return agg


def compute_all_aggregations(session: Session, force_recompute: bool = False) -> None:
    """Compute all period aggregations.

    Args:
        session: Database session
        force_recompute: If True, recompute all periods
    """
    # Get date range
    earliest = session.query(func.min(Activity.start_time)).scalar()
    if earliest is None:
        return

    latest = session.query(func.max(Activity.start_time)).scalar()
    if latest is None:
        return

    # Generate weeks
    current = get_week_start(earliest)
    while current <= latest:
        year, week, _ = current.isocalendar()
        period_key = f"{year}-W{week:02d}"
        compute_period_aggregation(session, "week", current, period_key)
        current += timedelta(days=7)

    # Generate months
    current = get_month_start(earliest)
    while current <= latest:
        period_key = current.strftime("%Y-%m")
        compute_period_aggregation(session, "month", current, period_key)
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    # Generate years
    current = get_year_start(earliest)
    while current <= latest:
        period_key = str(current.year)
        compute_period_aggregation(session, "year", current, period_key)
        current = current.replace(year=current.year + 1)

    session.commit()


def compute_rolling_averages(session: Session, force_recompute: bool = False) -> None:
    """Compute rolling averages for trend analysis.

    Args:
        session: Database session
        force_recompute: If True, recompute all days
    """
    # Get date range
    earliest = session.query(func.min(Activity.start_time)).scalar()
    if earliest is None:
        return

    start_date = earliest.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")

        # Get or create rolling average record
        ra = session.query(RollingAverage).filter_by(date=date_str).first()
        if ra is None:
            ra = RollingAverage(date=date_str)
            session.add(ra)

        # 7-day rolling
        ra.avg_7d_distance, ra.avg_7d_time, ra.avg_7d_tss, ra.count_7d_activities = (
            _compute_rolling_stats(session, current_date, 7)
        )

        # 30-day rolling
        ra.avg_30d_distance, ra.avg_30d_time, ra.avg_30d_tss, ra.count_30d_activities = (
            _compute_rolling_stats(session, current_date, 30)
        )

        # 90-day rolling
        ra.avg_90d_distance, ra.avg_90d_time, ra.avg_90d_tss, ra.count_90d_activities = (
            _compute_rolling_stats(session, current_date, 90)
        )

        # YTD stats
        year_start = current_date.replace(month=1, day=1)
        ytd_stats = _compute_ytd_stats(session, year_start, current_date)
        ra.ytd_distance = ytd_stats["distance"]
        ra.ytd_activities = ytd_stats["count"]

        # Previous YTD (same day last year)
        prev_year_start = year_start.replace(year=year_start.year - 1)
        # Handle leap year edge case (Feb 29 -> Feb 28)
        try:
            prev_current = current_date.replace(year=current_date.year - 1)
        except ValueError:
            # Feb 29 in leap year -> Feb 28 in non-leap year
            prev_current = current_date.replace(year=current_date.year - 1, day=28)
        prev_ytd_stats = _compute_ytd_stats(session, prev_year_start, prev_current)
        ra.prev_ytd_distance = prev_ytd_stats["distance"]
        ra.prev_ytd_activities = prev_ytd_stats["count"]

        ra.computed_at = datetime.utcnow()
        current_date += timedelta(days=1)

    session.commit()


def _compute_rolling_stats(
    session: Session,
    end_date: datetime,
    days: int,
) -> tuple[float | None, float | None, float | None, int]:
    """Compute rolling statistics for a period.

    Returns (avg_distance, avg_time, avg_tss, count)
    """
    start_date = end_date - timedelta(days=days)

    activities = (
        session.query(Activity)
        .filter(Activity.start_time >= start_date)
        .filter(Activity.start_time <= end_date)
        .all()
    )

    count = len(activities)
    if count == 0:
        return None, None, None, 0

    total_distance = sum(a.distance or 0 for a in activities)
    total_time = sum(a.moving_time or 0 for a in activities)

    # Get TSS
    activity_ids = [a.activity_id for a in activities]
    tss_sum = (
        session.query(func.sum(ActivityMetrics.tss))
        .filter(ActivityMetrics.activity_id.in_(activity_ids))
        .scalar()
    ) or 0

    return (
        total_distance / days,  # Daily average
        total_time / days,
        tss_sum / days,
        count,
    )


def _compute_ytd_stats(
    session: Session,
    year_start: datetime,
    current_date: datetime,
) -> dict:
    """Compute year-to-date statistics."""
    activities = (
        session.query(Activity)
        .filter(Activity.start_time >= year_start)
        .filter(Activity.start_time <= current_date)
        .all()
    )

    return {
        "distance": sum(a.distance or 0 for a in activities),
        "count": len(activities),
    }
