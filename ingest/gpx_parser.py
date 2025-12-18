"""GPX file parsing utilities."""
import gzip
import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class GpxData:
    """Parsed data from a GPX file."""

    # File metadata
    file_path: str
    file_size: int
    sha256: str

    # Activity info
    start_time: datetime | None = None
    name: str | None = None
    activity_type: str | None = None
    total_distance: float | None = None  # meters (calculated from points)

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


# GPX namespaces
NAMESPACES = {
    "gpx": "http://www.topografix.com/GPX/1/1",
    "gpxtpx": "http://www.garmin.com/xmlschemas/TrackPointExtension/v1",
    "gpxx": "http://www.garmin.com/xmlschemas/GpxExtensions/v3",
}


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def parse_iso_datetime(dt_str: str) -> datetime | None:
    """Parse ISO 8601 datetime string."""
    if not dt_str:
        return None
    try:
        # Handle various ISO formats
        dt_str = dt_str.replace("Z", "+00:00")
        if "+" in dt_str or dt_str.endswith("Z"):
            # Has timezone
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return datetime.fromisoformat(dt_str)
    except ValueError:
        return None


def calculate_distance(latitudes: list[float], longitudes: list[float]) -> float:
    """
    Calculate total distance from GPS points using Haversine formula.
    Returns distance in meters.
    """
    from math import radians, cos, sin, sqrt, atan2

    if len(latitudes) < 2:
        return 0.0

    total_distance = 0.0
    earth_radius = 6371000  # meters

    for i in range(1, len(latitudes)):
        lat1, lon1 = radians(latitudes[i - 1]), radians(longitudes[i - 1])
        lat2, lon2 = radians(latitudes[i]), radians(longitudes[i])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        total_distance += earth_radius * c

    return total_distance


def parse_gpx_file(file_path: Path) -> GpxData | None:
    """
    Parse a GPX file and extract relevant data.

    Handles both plain .gpx files and gzipped .gpx.gz files.

    Returns GpxData on success, None on failure.
    """
    if not file_path.exists():
        return None

    # Compute file size and hash
    file_size = file_path.stat().st_size
    sha256 = compute_sha256(file_path)

    # Determine if file is gzipped
    is_gzipped = file_path.suffix == ".gz" or file_path.name.endswith(".gpx.gz")

    try:
        if is_gzipped:
            with gzip.open(file_path, "rb") as f:
                gpx_content = f.read()
            root = ET.fromstring(gpx_content)
        else:
            tree = ET.parse(file_path)
            root = tree.getroot()

        result = GpxData(
            file_path=str(file_path),
            file_size=file_size,
            sha256=sha256,
        )

        # Handle namespace in root tag
        # GPX files typically have xmlns="http://www.topografix.com/GPX/1/1"
        ns = NAMESPACES

        # Try to find metadata time
        metadata = root.find("gpx:metadata", ns) or root.find("metadata")
        if metadata is not None:
            time_elem = metadata.find("gpx:time", ns) or metadata.find("time")
            if time_elem is not None and time_elem.text:
                result.start_time = parse_iso_datetime(time_elem.text)

        # Find tracks
        tracks = root.findall("gpx:trk", ns) or root.findall("trk")

        for trk in tracks:
            # Get track name
            name_elem = trk.find("gpx:name", ns) or trk.find("name")
            if name_elem is not None and name_elem.text:
                result.name = name_elem.text

            # Get track type
            type_elem = trk.find("gpx:type", ns) or trk.find("type")
            if type_elem is not None and type_elem.text:
                result.activity_type = type_elem.text

            # Find track segments
            trksegs = trk.findall("gpx:trkseg", ns) or trk.findall("trkseg")

            for trkseg in trksegs:
                # Find track points
                trkpts = trkseg.findall("gpx:trkpt", ns) or trkseg.findall("trkpt")

                for trkpt in trkpts:
                    # Get lat/lon from attributes
                    lat = trkpt.get("lat")
                    lon = trkpt.get("lon")

                    if lat is not None and lon is not None:
                        result.latitudes.append(float(lat))
                        result.longitudes.append(float(lon))

                    # Get elevation
                    ele_elem = trkpt.find("gpx:ele", ns) or trkpt.find("ele")
                    if ele_elem is not None and ele_elem.text:
                        try:
                            result.altitudes.append(float(ele_elem.text))
                        except ValueError:
                            pass

                    # Get time
                    time_elem = trkpt.find("gpx:time", ns) or trkpt.find("time")
                    if time_elem is not None and time_elem.text:
                        ts = parse_iso_datetime(time_elem.text)
                        if ts:
                            result.timestamps.append(ts)
                            # Use first timestamp as start time if not set
                            if result.start_time is None:
                                result.start_time = ts

                    # Get heart rate from extensions
                    extensions = trkpt.find("gpx:extensions", ns) or trkpt.find("extensions")
                    if extensions is not None:
                        # Try Garmin TrackPointExtension
                        tpx = extensions.find("gpxtpx:TrackPointExtension", ns)
                        if tpx is not None:
                            hr_elem = tpx.find("gpxtpx:hr", ns)
                            if hr_elem is not None and hr_elem.text:
                                try:
                                    result.heart_rates.append(int(hr_elem.text))
                                except ValueError:
                                    pass

        # Calculate total distance from GPS points
        if result.has_gps:
            result.total_distance = calculate_distance(result.latitudes, result.longitudes)

        return result

    except Exception as e:
        print(f"  Warning: Failed to parse GPX {file_path}: {e}")
        return None


def get_gpx_start_time(file_path: Path) -> datetime | None:
    """
    Quickly extract just the start time from a GPX file.

    Useful for matching GPX files to CSV activities by timestamp.
    """
    is_gzipped = file_path.suffix == ".gz" or file_path.name.endswith(".gpx.gz")

    try:
        if is_gzipped:
            with gzip.open(file_path, "rb") as f:
                gpx_content = f.read()
            root = ET.fromstring(gpx_content)
        else:
            tree = ET.parse(file_path)
            root = tree.getroot()

        ns = NAMESPACES

        # Try metadata time first
        metadata = root.find("gpx:metadata", ns) or root.find("metadata")
        if metadata is not None:
            time_elem = metadata.find("gpx:time", ns) or metadata.find("time")
            if time_elem is not None and time_elem.text:
                return parse_iso_datetime(time_elem.text)

        # Fall back to first track point time
        tracks = root.findall("gpx:trk", ns) or root.findall("trk")
        for trk in tracks:
            trksegs = trk.findall("gpx:trkseg", ns) or trk.findall("trkseg")
            for trkseg in trksegs:
                trkpts = trkseg.findall("gpx:trkpt", ns) or trkseg.findall("trkpt")
                for trkpt in trkpts:
                    time_elem = trkpt.find("gpx:time", ns) or trkpt.find("time")
                    if time_elem is not None and time_elem.text:
                        return parse_iso_datetime(time_elem.text)

    except Exception:
        pass

    return None
