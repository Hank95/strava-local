"""Statistics service for dashboard and queries."""
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import Activity, Stream, FitFile


def get_summary_stats(session: Session) -> dict[str, Any]:
    """Get summary statistics for the dashboard."""
    total = session.query(func.count(Activity.activity_id)).scalar() or 0
    with_gps = (
        session.query(func.count(Stream.id)).filter(Stream.has_gps == True).scalar()
        or 0
    )
    total_distance = session.query(func.sum(Activity.distance)).scalar() or 0
    total_time = session.query(func.sum(Activity.moving_time)).scalar() or 0

    min_date = session.query(func.min(Activity.start_time)).scalar()
    max_date = session.query(func.max(Activity.start_time)).scalar()

    return {
        "total_activities": total,
        "activities_with_gps": with_gps,
        "gps_percentage": round((with_gps / total * 100), 1) if total > 0 else 0,
        "total_distance_km": round(total_distance / 1000, 1),
        "total_time_hours": round(total_time / 3600, 1),
        "first_activity": min_date,
        "last_activity": max_date,
    }


def get_activity_type_breakdown(session: Session) -> list[dict[str, Any]]:
    """Get activity counts and distance by type."""
    results = (
        session.query(
            Activity.activity_type,
            func.count(Activity.activity_id).label("count"),
            func.sum(Activity.distance).label("distance"),
        )
        .filter(Activity.activity_type.isnot(None))
        .group_by(Activity.activity_type)
        .order_by(func.count(Activity.activity_id).desc())
        .all()
    )

    return [
        {
            "type": r.activity_type,
            "count": r.count,
            "distance_km": round((r.distance or 0) / 1000, 1),
        }
        for r in results
    ]


def get_activities_over_time(
    session: Session, grouping: str = "month"
) -> list[dict[str, Any]]:
    """Get activity counts grouped by time period."""
    if grouping == "month":
        date_fmt = "%Y-%m"
    elif grouping == "week":
        date_fmt = "%Y-%W"
    else:
        date_fmt = "%Y"

    results = (
        session.query(
            func.strftime(date_fmt, Activity.start_time).label("period"),
            func.count(Activity.activity_id).label("count"),
            func.sum(Activity.distance).label("distance"),
        )
        .filter(Activity.start_time.isnot(None))
        .group_by("period")
        .order_by("period")
        .all()
    )

    return [
        {
            "period": r.period,
            "count": r.count,
            "distance_km": round((r.distance or 0) / 1000, 1),
        }
        for r in results
    ]


def get_recent_activities(session: Session, limit: int = 10) -> list[Activity]:
    """Get the most recent activities."""
    return (
        session.query(Activity)
        .filter(Activity.start_time.isnot(None))
        .order_by(Activity.start_time.desc())
        .limit(limit)
        .all()
    )


def get_activity_types(session: Session) -> list[str]:
    """Get list of distinct activity types."""
    results = (
        session.query(Activity.activity_type)
        .filter(Activity.activity_type.isnot(None))
        .distinct()
        .order_by(Activity.activity_type)
        .all()
    )
    return [r[0] for r in results]
