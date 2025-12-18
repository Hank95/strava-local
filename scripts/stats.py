"""CLI script for viewing database statistics."""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func

from db.models import Activity, FitFile, Stream, get_engine, get_session


def main():
    engine = get_engine()
    session = get_session(engine)

    try:
        # Total activities
        total_activities = session.query(func.count(Activity.activity_id)).scalar() or 0

        if total_activities == 0:
            print("No activities in database. Run ingestion first:")
            print("  python -m scripts.ingest --csv activities.csv --fit-dir activities/")
            return

        # Activities with GPS
        activities_with_gps = (
            session.query(func.count(Stream.id))
            .filter(Stream.has_gps == True)
            .scalar()
            or 0
        )

        # Date range
        min_date = session.query(func.min(Activity.start_time)).scalar()
        max_date = session.query(func.max(Activity.start_time)).scalar()

        # Top 5 sports
        top_sports = (
            session.query(Activity.activity_type, func.count(Activity.activity_id))
            .filter(Activity.activity_type.isnot(None))
            .group_by(Activity.activity_type)
            .order_by(func.count(Activity.activity_id).desc())
            .limit(5)
            .all()
        )

        # FIT files ingested
        fit_files_count = session.query(func.count(FitFile.id)).scalar() or 0

        # Print statistics
        print("=" * 50)
        print("STRAVA LOCAL DATABASE STATISTICS")
        print("=" * 50)
        print()
        print(f"Total activities:     {total_activities:,}")
        print(f"Activities with GPS:  {activities_with_gps:,} ({activities_with_gps/total_activities*100:.1f}%)")
        print(f"FIT files ingested:   {fit_files_count:,}")
        print()

        if min_date and max_date:
            print(f"Date range:")
            print(f"  First activity: {min_date.strftime('%Y-%m-%d')}")
            print(f"  Last activity:  {max_date.strftime('%Y-%m-%d')}")
            print()

        if top_sports:
            print("Top 5 activity types:")
            for sport, count in top_sports:
                pct = count / total_activities * 100
                print(f"  {sport:20} {count:5,} ({pct:.1f}%)")
            print()

        print("=" * 50)

    finally:
        session.close()


if __name__ == "__main__":
    main()
