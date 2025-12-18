"""Main ingestion logic for Strava Local."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from db.models import Activity, FitFile, Stream, get_engine, get_session, init_db
from ingest.csv_loader import extract_activity_id_from_filename, load_csv
from ingest.fit_parser import (
    FitData,
    downsample_route,
    downsample_stream,
    get_fit_start_time,
    parse_fit_file,
)


class IngestionStats:
    """Track ingestion statistics."""

    def __init__(self):
        self.csv_activities_loaded = 0
        self.csv_activities_new = 0
        self.csv_activities_updated = 0
        self.fit_files_found = 0
        self.fit_files_matched = 0
        self.fit_files_parsed = 0
        self.fit_files_with_gps = 0
        self.errors: list[str] = []

    def __str__(self) -> str:
        return (
            f"Ingestion complete:\n"
            f"  CSV activities loaded: {self.csv_activities_loaded}\n"
            f"  - New: {self.csv_activities_new}\n"
            f"  - Updated: {self.csv_activities_updated}\n"
            f"  FIT files found: {self.fit_files_found}\n"
            f"  - Matched to activities: {self.fit_files_matched}\n"
            f"  - Successfully parsed: {self.fit_files_parsed}\n"
            f"  - With GPS data: {self.fit_files_with_gps}\n"
            f"  Errors: {len(self.errors)}"
        )


def find_fit_files(fit_dir: Path) -> dict[str, Path]:
    """
    Find all FIT files in a directory.

    Returns a dict mapping activity ID to file path.
    """
    fit_files: dict[str, Path] = {}

    for file_path in fit_dir.iterdir():
        if not file_path.is_file():
            continue

        # Accept .fit, .fit.gz, and skip .gpx for now
        name = file_path.name.lower()
        if not (name.endswith(".fit") or name.endswith(".fit.gz")):
            continue

        # Extract activity ID from filename
        activity_id = extract_activity_id_from_filename(file_path.name)
        if activity_id:
            fit_files[activity_id] = file_path

    return fit_files


def match_fit_by_time(
    activity_time: datetime,
    unmatched_fits: dict[str, Path],
    time_window_minutes: int = 10,
) -> tuple[str | None, Path | None]:
    """
    Try to match an activity to a FIT file by start time.

    Returns (activity_id, fit_path) if matched, (None, None) otherwise.
    """
    window = timedelta(minutes=time_window_minutes)

    for fit_id, fit_path in unmatched_fits.items():
        fit_time = get_fit_start_time(fit_path)
        if fit_time is None:
            continue

        # Check if within time window
        if abs(fit_time - activity_time) <= window:
            return fit_id, fit_path

    return None, None


def upsert_activity(session: Session, activity_data: dict[str, Any]) -> tuple[Activity, bool]:
    """
    Insert or update an activity in the database.

    Returns (activity, is_new).
    """
    activity_id = str(activity_data["activity_id"])

    # Check if exists
    existing = session.query(Activity).filter_by(activity_id=activity_id).first()

    if existing:
        # Update existing
        for key, value in activity_data.items():
            if key != "activity_id" and hasattr(existing, key):
                setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        return existing, False
    else:
        # Create new
        activity = Activity(**{k: v for k, v in activity_data.items() if hasattr(Activity, k)})
        session.add(activity)
        return activity, True


def upsert_fit_file(
    session: Session,
    activity_id: str,
    fit_data: FitData,
) -> FitFile:
    """Insert or update FIT file metadata."""
    existing = session.query(FitFile).filter_by(activity_id=activity_id).first()

    if existing:
        existing.fit_path = fit_data.file_path
        existing.file_size = fit_data.file_size
        existing.sha256 = fit_data.sha256
        existing.fit_start_time = fit_data.start_time
        existing.fit_sport = fit_data.sport
        existing.fit_distance = fit_data.total_distance
        existing.ingested_at = datetime.utcnow()
        return existing
    else:
        fit_file = FitFile(
            activity_id=activity_id,
            fit_path=fit_data.file_path,
            file_size=fit_data.file_size,
            sha256=fit_data.sha256,
            fit_start_time=fit_data.start_time,
            fit_sport=fit_data.sport,
            fit_distance=fit_data.total_distance,
        )
        session.add(fit_file)
        return fit_file


def upsert_stream(
    session: Session,
    activity_id: str,
    fit_data: FitData,
    max_points: int = 500,
) -> Stream:
    """Insert or update stream data."""
    existing = session.query(Stream).filter_by(activity_id=activity_id).first()

    # Prepare data
    route = downsample_route(fit_data.latitudes, fit_data.longitudes, max_points)
    heart_rate = downsample_stream(fit_data.heart_rates, max_points) if fit_data.heart_rates else None
    altitude = downsample_stream(fit_data.altitudes, max_points) if fit_data.altitudes else None
    has_gps = len(route) > 0
    original_count = max(len(fit_data.latitudes), len(fit_data.heart_rates), len(fit_data.altitudes))

    if existing:
        existing.route = route if route else None
        existing.heart_rate = heart_rate
        existing.altitude = altitude
        existing.has_gps = has_gps
        existing.original_point_count = original_count
        return existing
    else:
        stream = Stream(
            activity_id=activity_id,
            route=route if route else None,
            heart_rate=heart_rate,
            altitude=altitude,
            has_gps=has_gps,
            original_point_count=original_count,
        )
        session.add(stream)
        return stream


def run_ingestion(
    csv_path: Path,
    fit_dir: Path,
    db_path: Path | None = None,
    verbose: bool = True,
) -> IngestionStats:
    """
    Run the full ingestion process.

    Args:
        csv_path: Path to the activities CSV file.
        fit_dir: Path to the directory containing FIT files.
        db_path: Optional path to the SQLite database file.
        verbose: Whether to print progress messages.

    Returns:
        IngestionStats with summary of ingestion.
    """
    stats = IngestionStats()

    def log(msg: str):
        if verbose:
            print(msg)

    # Initialize database
    log("Initializing database...")
    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)

    try:
        # Load CSV
        log(f"Loading CSV from {csv_path}...")
        activities = load_csv(csv_path)
        stats.csv_activities_loaded = len(activities)
        log(f"  Loaded {len(activities)} activities from CSV")

        # Find FIT files
        log(f"Scanning FIT files in {fit_dir}...")
        fit_files = find_fit_files(fit_dir)
        stats.fit_files_found = len(fit_files)
        log(f"  Found {len(fit_files)} FIT files")

        # Track unmatched FIT files for time-based matching
        unmatched_fits = dict(fit_files)

        # Process each activity
        log("Processing activities...")
        for i, activity_data in enumerate(activities):
            activity_id = str(activity_data["activity_id"])

            # Upsert activity
            activity, is_new = upsert_activity(session, activity_data)
            if is_new:
                stats.csv_activities_new += 1
            else:
                stats.csv_activities_updated += 1

            # Try to match FIT file
            fit_path = None

            # First, try direct ID match
            if activity_id in fit_files:
                fit_path = fit_files[activity_id]
                unmatched_fits.pop(activity_id, None)

            # If no direct match and we have a start_time, try time-based match
            elif activity_data.get("start_time"):
                matched_id, matched_path = match_fit_by_time(
                    activity_data["start_time"],
                    unmatched_fits,
                )
                if matched_path:
                    fit_path = matched_path
                    unmatched_fits.pop(matched_id, None)
                    log(f"  Matched activity {activity_id} to FIT by time: {matched_path.name}")

            # Process FIT file if matched
            if fit_path:
                stats.fit_files_matched += 1

                fit_data = parse_fit_file(fit_path)
                if fit_data:
                    stats.fit_files_parsed += 1

                    # Upsert FIT file metadata
                    upsert_fit_file(session, activity_id, fit_data)

                    # Upsert stream data
                    upsert_stream(session, activity_id, fit_data)

                    if fit_data.has_gps:
                        stats.fit_files_with_gps += 1
                else:
                    stats.errors.append(f"Failed to parse FIT: {fit_path}")

            # Progress update
            if verbose and (i + 1) % 100 == 0:
                log(f"  Processed {i + 1}/{len(activities)} activities...")

        # Commit all changes
        log("Committing to database...")
        session.commit()

        log(f"\n{stats}")

        return stats

    except Exception as e:
        session.rollback()
        stats.errors.append(f"Fatal error: {e}")
        raise

    finally:
        session.close()
