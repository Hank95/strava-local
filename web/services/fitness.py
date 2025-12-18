"""Fitness and training load query services."""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from db.models import (
    Activity, ActivityMetrics, DailyMetrics,
    PeriodAggregation, RollingAverage, AthleteProfile
)


def get_training_load_chart_data(session: Session, days: int = 90) -> dict:
    """Get training load data for charting.

    Returns data formatted for Chart.js visualization.
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    daily_metrics = (
        session.query(DailyMetrics)
        .filter(DailyMetrics.date >= cutoff)
        .filter(DailyMetrics.ctl.isnot(None))
        .order_by(DailyMetrics.date)
        .all()
    )

    return {
        "labels": [dm.date for dm in daily_metrics],
        "ctl": [dm.ctl for dm in daily_metrics],
        "atl": [dm.atl for dm in daily_metrics],
        "tsb": [dm.tsb for dm in daily_metrics],
        "tss": [dm.total_tss for dm in daily_metrics],
    }


def get_current_form_status(session: Session) -> dict:
    """Get current training form status."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Get most recent day with data (might not be today)
    daily = (
        session.query(DailyMetrics)
        .filter(DailyMetrics.ctl.isnot(None))
        .order_by(DailyMetrics.date.desc())
        .first()
    )

    if not daily:
        return {
            "ctl": None,
            "atl": None,
            "tsb": None,
            "status": "No Data",
            "status_class": "secondary",
            "description": "Run metrics computation first",
            "date": None,
        }

    tsb = daily.tsb or 0

    # Determine status and styling
    if tsb > 25:
        status = "Very Fresh"
        status_class = "success"
        description = "Well recovered, ready for hard efforts"
    elif tsb > 5:
        status = "Fresh"
        status_class = "success"
        description = "Good form for quality training"
    elif tsb > -10:
        status = "Neutral"
        status_class = "warning"
        description = "Balanced training load"
    elif tsb > -25:
        status = "Fatigued"
        status_class = "warning"
        description = "Accumulated fatigue, consider recovery"
    else:
        status = "Very Fatigued"
        status_class = "error"
        description = "High fatigue, prioritize rest"

    return {
        "ctl": daily.ctl,
        "atl": daily.atl,
        "tsb": daily.tsb,
        "status": status,
        "status_class": status_class,
        "description": description,
        "date": daily.date,
    }


def get_weekly_summary(session: Session, weeks: int = 12) -> list[dict]:
    """Get weekly summary data for table display."""
    # Get recent weeks
    weeks_data = (
        session.query(PeriodAggregation)
        .filter(PeriodAggregation.period_type == "week")
        .order_by(PeriodAggregation.period_start.desc())
        .limit(weeks)
        .all()
    )

    return [
        {
            "week": w.period_key,
            "start": w.period_start,
            "activities": w.activity_count,
            "distance_km": round(w.total_distance / 1000, 1) if w.total_distance else 0,
            "time_hours": round(w.total_moving_time / 3600, 1) if w.total_moving_time else 0,
            "tss": round(w.total_tss, 0) if w.total_tss else 0,
            "active_days": w.active_days,
        }
        for w in weeks_data
    ]


def get_recent_activities_with_tss(session: Session, limit: int = 10) -> list[dict]:
    """Get recent activities with their TSS values."""
    activities = (
        session.query(Activity, ActivityMetrics)
        .outerjoin(ActivityMetrics, Activity.activity_id == ActivityMetrics.activity_id)
        .order_by(Activity.start_time.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": a.activity_id,
            "name": a.name or "Unnamed",
            "type": a.activity_type,
            "date": a.start_time.strftime("%Y-%m-%d") if a.start_time else None,
            "distance_km": round(a.distance / 1000, 2) if a.distance else None,
            "duration_min": round(a.moving_time / 60, 0) if a.moving_time else None,
            "tss": round(m.tss, 0) if m and m.tss else None,
            "tss_method": m.tss_method if m else None,
        }
        for a, m in activities
    ]


def get_hr_zone_distribution(session: Session, activity_id: str) -> dict | None:
    """Get HR zone distribution for a single activity."""
    metrics = session.query(ActivityMetrics).filter_by(activity_id=activity_id).first()

    if not metrics or not metrics.hr_z1_time:
        return None

    total = (
        (metrics.hr_z1_time or 0) +
        (metrics.hr_z2_time or 0) +
        (metrics.hr_z3_time or 0) +
        (metrics.hr_z4_time or 0) +
        (metrics.hr_z5_time or 0)
    )

    if total == 0:
        return None

    return {
        "z1": {"seconds": metrics.hr_z1_time, "pct": round(metrics.hr_z1_time / total * 100, 1)},
        "z2": {"seconds": metrics.hr_z2_time, "pct": round(metrics.hr_z2_time / total * 100, 1)},
        "z3": {"seconds": metrics.hr_z3_time, "pct": round(metrics.hr_z3_time / total * 100, 1)},
        "z4": {"seconds": metrics.hr_z4_time, "pct": round(metrics.hr_z4_time / total * 100, 1)},
        "z5": {"seconds": metrics.hr_z5_time, "pct": round(metrics.hr_z5_time / total * 100, 1)},
        "aerobic_pct": round((metrics.aerobic_time or 0) / total * 100, 1),
        "anaerobic_pct": round((metrics.anaerobic_time or 0) / total * 100, 1),
    }


def get_streak_info(session: Session) -> dict:
    """Get current and longest activity streak."""
    # Get all days with activities
    active_days = (
        session.query(DailyMetrics.date)
        .filter(DailyMetrics.has_activity == True)
        .order_by(DailyMetrics.date.desc())
        .all()
    )

    if not active_days:
        return {"current": 0, "longest": 0}

    # Convert to date objects and sort
    dates = sorted([datetime.strptime(d[0], "%Y-%m-%d").date() for d in active_days], reverse=True)

    # Calculate current streak (from today backwards)
    today = datetime.now().date()
    current_streak = 0

    # Check if today or yesterday has activity (streak might be ongoing)
    if dates and (dates[0] == today or dates[0] == today - timedelta(days=1)):
        current_streak = 1
        for i in range(1, len(dates)):
            if (dates[i - 1] - dates[i]).days == 1:
                current_streak += 1
            else:
                break

    # Calculate longest streak
    longest_streak = 1
    current = 1

    for i in range(1, len(dates)):
        if (dates[i - 1] - dates[i]).days == 1:
            current += 1
            longest_streak = max(longest_streak, current)
        else:
            current = 1

    return {"current": current_streak, "longest": longest_streak}


def get_fitness_summary(session: Session) -> dict:
    """Get overall fitness summary statistics."""
    # Get total TSS this week
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    week_tss = (
        session.query(func.sum(DailyMetrics.total_tss))
        .filter(DailyMetrics.date >= week_start)
        .scalar()
    ) or 0

    # Get activities count this week
    week_start_dt = datetime.strptime(week_start, "%Y-%m-%d")
    week_activities = (
        session.query(func.count(Activity.activity_id))
        .filter(Activity.start_time >= week_start_dt)
        .scalar()
    ) or 0

    # Get 30-day averages
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    avg_stats = (
        session.query(
            func.avg(DailyMetrics.total_tss),
            func.avg(DailyMetrics.total_distance),
        )
        .filter(DailyMetrics.date >= thirty_days_ago)
        .filter(DailyMetrics.has_activity == True)
        .first()
    )

    return {
        "week_tss": round(week_tss, 0),
        "week_activities": week_activities,
        "avg_daily_tss_30d": round(avg_stats[0], 1) if avg_stats[0] else 0,
        "avg_daily_distance_30d": round(avg_stats[1] / 1000, 1) if avg_stats[1] else 0,
    }
