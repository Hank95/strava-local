"""Training Stress Score (TSS) calculation."""

import math
from sqlalchemy.orm import Session

from db.models import Activity, Stream
from metrics.config import (
    TSS_DURATION_FACTORS,
    TRIMP_FACTOR_DEFAULT,
    MIN_ACTIVITY_DURATION_SECONDS,
)


def compute_trimp(
    hr_samples: list[int],
    resting_hr: int | None,
    max_hr: int,
    duration_seconds: float,
    gender_factor: float = TRIMP_FACTOR_DEFAULT,
) -> float:
    """Compute TRIMP (Training Impulse) from HR stream.

    Uses Bannister's TRIMP formula:
    TRIMP = duration × HRr × 0.64 × e^(gender_factor × HRr)

    Where HRr = (HR - resting) / (max - resting) is the heart rate reserve fraction.

    Args:
        hr_samples: List of heart rate values
        resting_hr: Resting heart rate (defaults to 60 if not provided)
        max_hr: Maximum heart rate
        duration_seconds: Total duration in seconds
        gender_factor: Exponential weighting (1.92 male, 1.67 female)

    Returns:
        TRIMP value
    """
    if not hr_samples or max_hr <= 0:
        return 0.0

    resting = resting_hr or 60  # Default resting HR

    if max_hr <= resting:
        return 0.0

    # Calculate average HR reserve fraction
    valid_samples = [hr for hr in hr_samples if hr > resting]
    if not valid_samples:
        return 0.0

    avg_hr = sum(valid_samples) / len(valid_samples)
    hr_reserve = (avg_hr - resting) / (max_hr - resting)
    hr_reserve = max(0, min(1, hr_reserve))  # Clamp to [0, 1]

    # TRIMP formula
    duration_minutes = duration_seconds / 60
    trimp = duration_minutes * hr_reserve * 0.64 * math.exp(gender_factor * hr_reserve)

    return trimp


def compute_hr_tss(
    trimp: float,
    lthr: int,
    resting_hr: int | None,
    max_hr: int,
) -> float:
    """Convert TRIMP to TSS-like score.

    Normalizes TRIMP relative to a 1-hour threshold effort.

    Args:
        trimp: TRIMP value from compute_trimp()
        lthr: Lactate threshold heart rate
        resting_hr: Resting heart rate
        max_hr: Maximum heart rate

    Returns:
        TSS value (100 = 1 hour at threshold)
    """
    if trimp <= 0 or max_hr <= 0:
        return 0.0

    resting = resting_hr or 60

    if max_hr <= resting:
        return 0.0

    # Compute threshold HR reserve
    lthr_reserve = (lthr - resting) / (max_hr - resting)
    lthr_reserve = max(0.1, min(1, lthr_reserve))  # Clamp with minimum

    # TRIMP for 1 hour at threshold
    threshold_trimp = 60 * lthr_reserve * 0.64 * math.exp(TRIMP_FACTOR_DEFAULT * lthr_reserve)

    if threshold_trimp <= 0:
        return 0.0

    # Scale TRIMP to TSS (100 = 1 hour at threshold)
    tss = (trimp / threshold_trimp) * 100

    return tss


def compute_duration_tss(
    activity_type: str | None,
    duration_seconds: float,
) -> float:
    """Compute TSS estimate from duration and activity type.

    Uses activity-type-specific factors when HR data is unavailable.

    Args:
        activity_type: Type of activity (Run, Ride, etc.)
        duration_seconds: Duration in seconds

    Returns:
        Estimated TSS value
    """
    if duration_seconds < MIN_ACTIVITY_DURATION_SECONDS:
        return 0.0

    factor = TSS_DURATION_FACTORS.get(
        activity_type or "default",
        TSS_DURATION_FACTORS["default"]
    )

    hours = duration_seconds / 3600
    return factor * hours


def compute_activity_tss(
    session: Session,
    activity: Activity,
    stream: Stream | None,
    profile_values: dict,
) -> dict:
    """Compute TSS for a single activity.

    Tries HR-based calculation first, falls back to duration-based.

    Args:
        session: Database session
        activity: Activity record
        stream: Stream record (may be None)
        profile_values: Dict from get_effective_values()

    Returns:
        Dict with:
            - tss: Computed TSS value
            - tss_method: 'hr', 'power', or 'duration'
            - trimp: TRIMP value (if HR-based)
            - has_hr_stream: Whether HR data was available
    """
    result = {
        "tss": 0.0,
        "tss_method": "duration",
        "trimp": None,
        "has_hr_stream": False,
        "has_power_data": False,
    }

    duration = activity.moving_time or activity.elapsed_time or 0
    if duration < MIN_ACTIVITY_DURATION_SECONDS:
        return result

    max_hr = profile_values.get("max_hr")
    lthr = profile_values.get("lthr")
    resting_hr = profile_values.get("resting_hr")

    # Try HR-based TSS if we have stream data and profile values
    if stream and stream.heart_rate and max_hr and lthr:
        hr_samples = stream.heart_rate
        if len(hr_samples) >= 10:
            result["has_hr_stream"] = True

            trimp = compute_trimp(
                hr_samples=hr_samples,
                resting_hr=resting_hr,
                max_hr=max_hr,
                duration_seconds=duration,
            )

            if trimp > 0:
                tss = compute_hr_tss(
                    trimp=trimp,
                    lthr=lthr,
                    resting_hr=resting_hr,
                    max_hr=max_hr,
                )

                result["tss"] = tss
                result["tss_method"] = "hr"
                result["trimp"] = trimp
                return result

    # Fall back to duration-based TSS
    result["tss"] = compute_duration_tss(activity.activity_type, duration)
    result["tss_method"] = "duration"

    return result
