"""FIT file parsing utilities."""
import gzip
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fitparse import FitFile


@dataclass
class FitData:
    """Parsed data from a FIT file."""

    # File metadata
    file_path: str
    file_size: int
    sha256: str

    # Activity info
    start_time: datetime | None = None
    sport: str | None = None
    total_distance: float | None = None  # meters

    # Streams (raw, before downsampling)
    latitudes: list[float] = field(default_factory=list)
    longitudes: list[float] = field(default_factory=list)
    heart_rates: list[int] = field(default_factory=list)
    altitudes: list[float] = field(default_factory=list)
    timestamps: list[datetime] = field(default_factory=list)

    @property
    def has_gps(self) -> bool:
        """Check if we have GPS data."""
        return len(self.latitudes) > 0 and len(self.longitudes) > 0


def semicircles_to_degrees(semicircles: int) -> float:
    """
    Convert FIT semicircles to degrees.

    FIT uses semicircles where 2^31 = 180 degrees.
    """
    return semicircles * (180.0 / 2**31)


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def parse_fit_file(file_path: Path) -> FitData | None:
    """
    Parse a FIT file and extract relevant data.

    Handles both plain .fit files and gzipped .fit.gz files.

    Returns FitData on success, None on failure.
    """
    if not file_path.exists():
        return None

    # Compute file size and hash
    file_size = file_path.stat().st_size
    sha256 = compute_sha256(file_path)

    # Determine if file is gzipped
    is_gzipped = file_path.suffix == ".gz" or file_path.name.endswith(".fit.gz")

    try:
        if is_gzipped:
            with gzip.open(file_path, "rb") as f:
                fit_data_bytes = f.read()
            fit = FitFile(fit_data_bytes)
        else:
            fit = FitFile(str(file_path))

        # Parse the FIT data
        result = FitData(
            file_path=str(file_path),
            file_size=file_size,
            sha256=sha256,
        )

        # Iterate through messages
        for record in fit.get_messages():
            record_type = record.name

            if record_type == "session":
                # Extract session-level data
                for field_data in record:
                    if field_data.name == "start_time":
                        result.start_time = field_data.value
                    elif field_data.name == "sport":
                        result.sport = str(field_data.value)
                    elif field_data.name == "total_distance":
                        result.total_distance = field_data.value

            elif record_type == "record":
                # Extract per-record stream data
                lat = None
                lon = None
                hr = None
                alt = None
                ts = None

                for field_data in record:
                    if field_data.name == "position_lat" and field_data.value is not None:
                        lat = semicircles_to_degrees(field_data.value)
                    elif field_data.name == "position_long" and field_data.value is not None:
                        lon = semicircles_to_degrees(field_data.value)
                    elif field_data.name == "heart_rate" and field_data.value is not None:
                        hr = int(field_data.value)
                    elif field_data.name == "altitude" and field_data.value is not None:
                        alt = float(field_data.value)
                    elif field_data.name == "enhanced_altitude" and field_data.value is not None:
                        alt = float(field_data.value)
                    elif field_data.name == "timestamp":
                        ts = field_data.value

                # Only add if we have valid position data
                if lat is not None and lon is not None:
                    result.latitudes.append(lat)
                    result.longitudes.append(lon)

                if hr is not None:
                    result.heart_rates.append(hr)

                if alt is not None:
                    result.altitudes.append(alt)

                if ts is not None:
                    result.timestamps.append(ts)

        return result

    except Exception as e:
        # Log the error but don't crash
        print(f"  Warning: Failed to parse {file_path}: {e}")
        return None


def downsample_route(
    latitudes: list[float],
    longitudes: list[float],
    max_points: int = 500,
) -> list[list[float]]:
    """
    Downsample a route to reduce storage size.

    Uses simple stride-based downsampling. Returns array of [lat, lon] pairs.
    """
    if not latitudes or not longitudes:
        return []

    n = len(latitudes)
    if n <= max_points:
        # No downsampling needed
        return [[lat, lon] for lat, lon in zip(latitudes, longitudes)]

    # Calculate stride
    stride = n // max_points

    # Sample points at regular intervals, always including first and last
    result = []
    for i in range(0, n, stride):
        result.append([latitudes[i], longitudes[i]])

    # Ensure last point is included
    if len(result) == 0 or result[-1] != [latitudes[-1], longitudes[-1]]:
        result.append([latitudes[-1], longitudes[-1]])

    return result


def downsample_stream(
    stream: list[Any],
    max_points: int = 500,
) -> list[Any]:
    """
    Downsample a stream to reduce storage size.

    Uses simple stride-based downsampling.
    """
    if not stream:
        return []

    n = len(stream)
    if n <= max_points:
        return list(stream)

    stride = n // max_points

    result = []
    for i in range(0, n, stride):
        result.append(stream[i])

    return result


def get_fit_start_time(file_path: Path) -> datetime | None:
    """
    Quickly extract just the start time from a FIT file.

    Useful for matching FIT files to CSV activities by timestamp.
    """
    is_gzipped = file_path.suffix == ".gz" or file_path.name.endswith(".fit.gz")

    try:
        if is_gzipped:
            with gzip.open(file_path, "rb") as f:
                fit_data_bytes = f.read()
            fit = FitFile(fit_data_bytes)
        else:
            fit = FitFile(str(file_path))

        # Look for start_time in session or file_id messages
        for record in fit.get_messages(["session", "file_id"]):
            for field_data in record:
                if field_data.name == "start_time" and field_data.value is not None:
                    return field_data.value
                if field_data.name == "time_created" and field_data.value is not None:
                    return field_data.value

    except Exception:
        pass

    return None
