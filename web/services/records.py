"""Personal records and performance analysis service."""
from typing import Any

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from db.models import Activity, Stream


def get_personal_records(session: Session) -> dict[str, Any]:
    """Get overall personal records across all activities."""
    # Longest distance
    longest = (
        session.query(Activity)
        .filter(Activity.distance.isnot(None))
        .order_by(desc(Activity.distance))
        .first()
    )

    # Longest time
    longest_time = (
        session.query(Activity)
        .filter(Activity.moving_time.isnot(None))
        .order_by(desc(Activity.moving_time))
        .first()
    )

    # Highest elevation gain
    highest_climb = (
        session.query(Activity)
        .filter(Activity.elevation_gain.isnot(None))
        .order_by(desc(Activity.elevation_gain))
        .first()
    )

    # Fastest speed (for activities with speed data)
    fastest = (
        session.query(Activity)
        .filter(Activity.max_speed.isnot(None))
        .order_by(desc(Activity.max_speed))
        .first()
    )

    # Highest heart rate
    highest_hr = (
        session.query(Activity)
        .filter(Activity.max_hr.isnot(None))
        .order_by(desc(Activity.max_hr))
        .first()
    )

    # Most calories
    most_calories = (
        session.query(Activity)
        .filter(Activity.calories.isnot(None))
        .order_by(desc(Activity.calories))
        .first()
    )

    return {
        "longest_distance": longest,
        "longest_time": longest_time,
        "highest_climb": highest_climb,
        "fastest_speed": fastest,
        "highest_hr": highest_hr,
        "most_calories": most_calories,
    }


def get_personal_records_by_type(session: Session) -> dict[str, dict[str, Any]]:
    """Get personal records grouped by activity type."""
    # Get all activity types
    types = (
        session.query(Activity.activity_type)
        .filter(Activity.activity_type.isnot(None))
        .distinct()
        .all()
    )

    records_by_type = {}

    for (activity_type,) in types:
        # Longest distance for this type
        longest = (
            session.query(Activity)
            .filter(Activity.activity_type == activity_type)
            .filter(Activity.distance.isnot(None))
            .order_by(desc(Activity.distance))
            .first()
        )

        # Fastest average speed for this type
        fastest = (
            session.query(Activity)
            .filter(Activity.activity_type == activity_type)
            .filter(Activity.avg_speed.isnot(None))
            .filter(Activity.distance > 1000)  # At least 1km
            .order_by(desc(Activity.avg_speed))
            .first()
        )

        # Highest elevation for this type
        highest_climb = (
            session.query(Activity)
            .filter(Activity.activity_type == activity_type)
            .filter(Activity.elevation_gain.isnot(None))
            .order_by(desc(Activity.elevation_gain))
            .first()
        )

        records_by_type[activity_type] = {
            "longest_distance": longest,
            "fastest_avg_speed": fastest,
            "highest_climb": highest_climb,
        }

    return records_by_type


def get_hr_stats(session: Session) -> dict[str, Any]:
    """Get heart rate statistics."""
    # Activities with HR data
    hr_count = (
        session.query(func.count(Activity.activity_id))
        .filter(Activity.avg_hr.isnot(None))
        .scalar()
        or 0
    )

    if hr_count == 0:
        return {"has_data": False}

    avg_hr = session.query(func.avg(Activity.avg_hr)).scalar() or 0
    max_hr_overall = session.query(func.max(Activity.max_hr)).scalar() or 0

    return {
        "has_data": True,
        "activities_with_hr": hr_count,
        "average_hr": round(avg_hr, 1),
        "max_hr_ever": round(max_hr_overall, 0),
    }
