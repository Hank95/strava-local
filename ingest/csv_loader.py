"""CSV loading and parsing utilities."""
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dateutil import parser as dateparser


def normalize_header(header: str) -> str:
    """
    Convert header to snake_case.

    Examples:
        'Activity ID' -> 'activity_id'
        'Max Heart Rate' -> 'max_heart_rate'
        'Average Speed' -> 'average_speed'
    """
    # Remove leading/trailing whitespace
    header = header.strip()

    # Replace spaces and special chars with underscores
    header = re.sub(r"[\s\-/]+", "_", header)

    # Convert to lowercase
    header = header.lower()

    # Remove consecutive underscores
    header = re.sub(r"_+", "_", header)

    # Remove leading/trailing underscores
    header = header.strip("_")

    return header


def parse_date(value: str) -> datetime | None:
    """
    Parse a date string robustly.

    Handles various formats including:
        - 'Mar 31, 2020, 9:26:15 PM'
        - '2020-03-31T21:26:15'
        - Unix timestamps
    """
    if not value or value.strip() == "":
        return None

    value = value.strip()

    # Try Unix timestamp (float)
    try:
        ts = float(value)
        if ts > 1e9:  # Reasonable timestamp range
            return datetime.fromtimestamp(ts)
    except ValueError:
        pass

    # Try dateutil parser
    try:
        return dateparser.parse(value)
    except (ValueError, TypeError):
        return None


def parse_float(value: str) -> float | None:
    """Parse a float value, returning None for empty or invalid values."""
    if not value or value.strip() == "":
        return None

    try:
        return float(value.strip())
    except ValueError:
        return None


def parse_bool(value: str) -> bool | None:
    """Parse a boolean value."""
    if not value or value.strip() == "":
        return None

    value = value.strip().lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    return None


# Mapping from normalized CSV headers to Activity model fields
FIELD_MAPPING = {
    "activity_id": "activity_id",
    "activity_name": "name",
    "activity_type": "activity_type",
    "type": "activity_type",
    "start_time": "start_time",
    "activity_date": "start_time",
    "distance": "distance",
    "moving_time": "moving_time",
    "elapsed_time": "elapsed_time",
    "average_speed": "avg_speed",
    "avg_speed": "avg_speed",
    "max_speed": "max_speed",
    "average_heart_rate": "avg_hr",
    "avg_heart_rate": "avg_hr",
    "max_heart_rate": "max_hr",
    "elevation_gain": "elevation_gain",
    "elevation_loss": "elevation_loss",
    "elevation_low": "elevation_low",
    "elevation_high": "elevation_high",
    "average_watts": "avg_watts",
    "avg_watts": "avg_watts",
    "max_watts": "max_watts",
    "average_cadence": "avg_cadence",
    "avg_cadence": "avg_cadence",
    "max_cadence": "max_cadence",
    "calories": "calories",
    "athlete_weight": "athlete_weight",
}

# Fields that should be parsed as dates
DATE_FIELDS = {"start_time", "activity_date"}

# Fields that should be parsed as floats
FLOAT_FIELDS = {
    "distance",
    "moving_time",
    "elapsed_time",
    "average_speed",
    "avg_speed",
    "max_speed",
    "average_heart_rate",
    "avg_heart_rate",
    "max_heart_rate",
    "elevation_gain",
    "elevation_loss",
    "elevation_low",
    "elevation_high",
    "average_watts",
    "avg_watts",
    "max_watts",
    "average_cadence",
    "avg_cadence",
    "max_cadence",
    "calories",
    "athlete_weight",
}


def load_csv(csv_path: Path) -> list[dict[str, Any]]:
    """
    Load and parse the activities CSV file.

    Returns a list of dictionaries with normalized keys and parsed values.
    Each dict contains:
        - Known fields mapped to model field names
        - 'csv_extra' dict with any unmapped fields
        - 'filename' (original filename from CSV if present)
    """
    activities = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            activity: dict[str, Any] = {}
            extra: dict[str, Any] = {}

            # Track which model fields we've set to avoid duplicates
            seen_fields: set[str] = set()

            for header, value in row.items():
                normalized = normalize_header(header)

                # Skip empty values
                if not value or value.strip() == "":
                    continue

                # Check if this maps to a known field
                if normalized in FIELD_MAPPING:
                    model_field = FIELD_MAPPING[normalized]

                    # Skip if we already set this field (handles duplicate columns)
                    if model_field in seen_fields:
                        # Store in extra instead
                        extra[normalized] = value
                        continue

                    # Parse the value based on field type
                    if normalized in DATE_FIELDS:
                        parsed = parse_date(value)
                    elif normalized in FLOAT_FIELDS:
                        parsed = parse_float(value)
                    else:
                        parsed = value.strip()

                    if parsed is not None:
                        activity[model_field] = parsed
                        seen_fields.add(model_field)
                else:
                    # Store in extra
                    # Try to parse as float if it looks numeric
                    try:
                        extra[normalized] = float(value.strip())
                    except ValueError:
                        extra[normalized] = value.strip()

            # Preserve original filename if present
            if "filename" in extra:
                activity["_filename"] = extra.pop("filename")

            # Store extra fields
            if extra:
                activity["csv_extra"] = extra

            # Only add if we have an activity_id
            if "activity_id" in activity:
                activities.append(activity)

    return activities


def extract_activity_id_from_filename(filename: str) -> str | None:
    """
    Extract activity ID from a filename.

    Examples:
        'activities/1234567890.fit.gz' -> '1234567890'
        '1234567890.gpx' -> '1234567890'
    """
    # Get just the filename without path
    basename = Path(filename).name

    # Remove extensions (.fit.gz, .gpx, etc.)
    name = basename.split(".")[0]

    # Check if it looks like a numeric activity ID
    if name.isdigit():
        return name

    return None
