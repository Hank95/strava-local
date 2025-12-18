"""Main ingestion logic for Strava Local."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

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
from ingest.gpx_parser import (
    GpxData,
    get_gpx_start_time,
    parse_gpx_file,
)


class ActivityFileData(Protocol):
    """Protocol for parsed activity file data (FIT or GPX)."""
    file_path: str
    file_size: int
    sha256: str
    start_time: datetime | None
    total_distance: float | None
    latitudes: list[float]
    longitudes: list[float]
    heart_rates: list[int]
    altitudes: list[float]
    has_gps: bool


class IngestionStats:
    """Track ingestion statistics."""

    def __init__(self):
        self.csv_activities_loaded = 0
        self.csv_activities_new = 0
        self.csv_activities_updated = 0
        self.fit_files_found = 0
        self.gpx_files_found = 0
        self.activity_files_matched = 0
        self.activity_files_parsed = 0
        self.activities_with_gps = 0
        self.errors: list[str] = []

    def __str__(self) -> str:
        total_files = self.fit_files_found + self.gpx_files_found
        return (
            f"Ingestion complete:\n"
            f"  CSV activities loaded: {self.csv_activities_loaded}\n"
            f"  - New: {self.csv_activities_new}\n"
            f"  - Updated: {self.csv_activities_updated}\n"
            f"  Activity files found: {total_files}\n"
            f"  - FIT files: {self.fit_files_found}\n"
            f"  - GPX files: {self.gpx_files_found}\n"
            f"  - Matched to activities: {self.activity_files_matched}\n"
            f"  - Successfully parsed: {self.activity_files_parsed}\n"
            f"  - With GPS data: {self.activities_with_gps}\n"
            f"  Errors: {len(self.errors)}"
        )


def find_activity_files(activity_dir: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    """
    Find all FIT and GPX files in a directory.

    Returns (fit_files, gpx_files) dicts mapping activity ID to file path.
    """
    fit_files: dict[str, Path] = {}
    gpx_files: dict[str, Path] = {}

    for file_path in activity_dir.iterdir():
        if not file_path.is_file():
            continue

        name = file_path.name.lower()

        # Check for FIT files
        if name.endswith(".fit") or name.endswith(".fit.gz"):
            activity_id = extract_activity_id_from_filename(file_path.name)
            if activity_id:
                fit_files[activity_id] = file_path

        # Check for GPX files
        elif name.endswith(".gpx") or name.endswith(".gpx.gz"):
            activity_id = extract_activity_id_from_filename(file_path.name)
            if activity_id:
                gpx_files[activity_id] = file_path

    return fit_files, gpx_files


def match_file_by_time(
    activity_time: datetime,
    unmatched_files: dict[str, Path],
    file_type: str,
    time_window_minutes: int = 10,
) -> tuple[str | None, Path | None]:
    """
    Try to match an activity to a FIT/GPX file by start time.

    Args:
        activity_time: The activity start time to match.
        unmatched_files: Dict of activity_id -> file_path.
        file_type: Either "fit" or "gpx".
        time_window_minutes: Maximum time difference for a match.

    Returns (activity_id, file_path) if matched, (None, None) otherwise.
    """
    window = timedelta(minutes=time_window_minutes)

    for file_id, file_path in unmatched_files.items():
        if file_type == "fit":
            file_time = get_fit_start_time(file_path)
        else:
            file_time = get_gpx_start_time(file_path)

        if file_time is None:
            continue

        # Check if within time window
        if abs(file_time - activity_time) <= window:
            return file_id, file_path

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


def upsert_activity_file(
    session: Session,
    activity_id: str,
    file_data: FitData | GpxData,
) -> FitFile:
    """Insert or update activity file metadata (FIT or GPX)."""
    existing = session.query(FitFile).filter_by(activity_id=activity_id).first()

    # Get sport/type - FitData has 'sport', GpxData has 'activity_type'
    sport = getattr(file_data, 'sport', None) or getattr(file_data, 'activity_type', None)

    if existing:
        existing.fit_path = file_data.file_path
        existing.file_size = file_data.file_size
        existing.sha256 = file_data.sha256
        existing.fit_start_time = file_data.start_time
        existing.fit_sport = sport
        existing.fit_distance = file_data.total_distance
        existing.ingested_at = datetime.utcnow()
        return existing
    else:
        fit_file = FitFile(
            activity_id=activity_id,
            fit_path=file_data.file_path,
            file_size=file_data.file_size,
            sha256=file_data.sha256,
            fit_start_time=file_data.start_time,
            fit_sport=sport,
            fit_distance=file_data.total_distance,
        )
        session.add(fit_file)
        return fit_file


def upsert_stream(
    session: Session,
    activity_id: str,
    file_data: FitData | GpxData,
    max_points: int = 500,
) -> Stream:
    """Insert or update stream data from FIT or GPX file."""
    existing = session.query(Stream).filter_by(activity_id=activity_id).first()

    # Prepare data
    route = downsample_route(file_data.latitudes, file_data.longitudes, max_points)
    heart_rate = downsample_stream(file_data.heart_rates, max_points) if file_data.heart_rates else None
    altitude = downsample_stream(file_data.altitudes, max_points) if file_data.altitudes else None
    has_gps = len(route) > 0
    original_count = max(len(file_data.latitudes), len(file_data.heart_rates), len(file_data.altitudes))

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
        fit_dir: Path to the directory containing FIT/GPX files.
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

        # Find FIT and GPX files
        log(f"Scanning activity files in {fit_dir}...")
        fit_files, gpx_files = find_activity_files(fit_dir)
        stats.fit_files_found = len(fit_files)
        stats.gpx_files_found = len(gpx_files)
        log(f"  Found {len(fit_files)} FIT files, {len(gpx_files)} GPX files")

        # Track unmatched files for time-based matching
        unmatched_fits = dict(fit_files)
        unmatched_gpx = dict(gpx_files)

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

            # Try to match activity file (prefer FIT over GPX)
            file_path = None
            file_type = None

            # First, try direct ID match for FIT
            if activity_id in fit_files:
                file_path = fit_files[activity_id]
                file_type = "fit"
                unmatched_fits.pop(activity_id, None)

            # Then try direct ID match for GPX
            elif activity_id in gpx_files:
                file_path = gpx_files[activity_id]
                file_type = "gpx"
                unmatched_gpx.pop(activity_id, None)

            # If no direct match and we have a start_time, try time-based match
            elif activity_data.get("start_time"):
                # Try FIT files first
                matched_id, matched_path = match_file_by_time(
                    activity_data["start_time"],
                    unmatched_fits,
                    "fit",
                )
                if matched_path:
                    file_path = matched_path
                    file_type = "fit"
                    unmatched_fits.pop(matched_id, None)
                    log(f"  Matched activity {activity_id} to FIT by time: {matched_path.name}")
                else:
                    # Try GPX files
                    matched_id, matched_path = match_file_by_time(
                        activity_data["start_time"],
                        unmatched_gpx,
                        "gpx",
                    )
                    if matched_path:
                        file_path = matched_path
                        file_type = "gpx"
                        unmatched_gpx.pop(matched_id, None)
                        log(f"  Matched activity {activity_id} to GPX by time: {matched_path.name}")

            # Process activity file if matched
            if file_path and file_type:
                stats.activity_files_matched += 1

                # Parse the file
                if file_type == "fit":
                    file_data = parse_fit_file(file_path)
                else:
                    file_data = parse_gpx_file(file_path)

                if file_data:
                    stats.activity_files_parsed += 1

                    # Upsert file metadata
                    upsert_activity_file(session, activity_id, file_data)

                    # Upsert stream data
                    upsert_stream(session, activity_id, file_data)

                    if file_data.has_gps:
                        stats.activities_with_gps += 1
                else:
                    stats.errors.append(f"Failed to parse {file_type.upper()}: {file_path}")

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
