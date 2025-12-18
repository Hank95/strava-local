"""CLI script for viewing the most recent activity."""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import Activity, FitFile, Stream, get_engine, get_session


def main():
    engine = get_engine()
    session = get_session(engine)

    try:
        # Get most recent activity
        activity = (
            session.query(Activity)
            .filter(Activity.start_time.isnot(None))
            .order_by(Activity.start_time.desc())
            .first()
        )

        if not activity:
            print("No activities in database. Run ingestion first:")
            print("  python -m scripts.ingest --csv activities.csv --fit-dir activities/")
            return

        # Check for FIT file
        fit_file = session.query(FitFile).filter_by(activity_id=activity.activity_id).first()

        # Check for GPS data
        stream = session.query(Stream).filter_by(activity_id=activity.activity_id).first()

        # Print info
        print("=" * 50)
        print("MOST RECENT ACTIVITY")
        print("=" * 50)
        print()
        print(f"Activity ID:   {activity.activity_id}")
        print(f"Name:          {activity.name or '(unnamed)'}")
        print(f"Type:          {activity.activity_type or '(unknown)'}")
        print(f"Date:          {activity.start_time.strftime('%Y-%m-%d %H:%M') if activity.start_time else '(unknown)'}")
        print()

        # Distance and time
        if activity.distance:
            km = activity.distance / 1000
            print(f"Distance:      {km:.2f} km")

        if activity.moving_time:
            hours = int(activity.moving_time // 3600)
            mins = int((activity.moving_time % 3600) // 60)
            secs = int(activity.moving_time % 60)
            if hours:
                print(f"Moving time:   {hours}:{mins:02d}:{secs:02d}")
            else:
                print(f"Moving time:   {mins}:{secs:02d}")

        if activity.avg_speed:
            kmh = activity.avg_speed * 3.6
            print(f"Avg speed:     {kmh:.1f} km/h")

        if activity.elevation_gain:
            print(f"Elevation:     {activity.elevation_gain:.0f} m")

        if activity.avg_hr:
            print(f"Avg HR:        {activity.avg_hr:.0f} bpm")

        if activity.calories:
            print(f"Calories:      {activity.calories:.0f}")

        print()

        # FIT and GPS status
        has_fit = "Yes" if fit_file else "No"
        has_gps = "Yes" if (stream and stream.has_gps) else "No"

        print(f"Has FIT file:  {has_fit}")
        if fit_file:
            print(f"  - Path: {Path(fit_file.fit_path).name}")
            if fit_file.sha256:
                print(f"  - SHA256: {fit_file.sha256[:16]}...")

        print(f"Has GPS track: {has_gps}")
        if stream and stream.has_gps and stream.route:
            print(f"  - Points: {len(stream.route)} (downsampled from {stream.original_point_count})")

        print()
        print("=" * 50)

    finally:
        session.close()


if __name__ == "__main__":
    main()
