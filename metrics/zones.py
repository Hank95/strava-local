"""HR zone time calculation."""

from db.models import Stream
from metrics.config import MIN_HR_SAMPLES_FOR_ZONES


def compute_hr_zones(
    stream: Stream | None,
    hr_zones: dict | None,
    duration_seconds: float,
) -> dict:
    """Compute time spent in each HR zone.

    Args:
        stream: Stream record with heart_rate data
        hr_zones: Zone thresholds as HR values from get_effective_values()
        duration_seconds: Total activity duration in seconds

    Returns:
        Dict with:
            - z1_time through z5_time: Seconds in each zone
            - aerobic_time: Z1 + Z2 seconds
            - anaerobic_time: Z4 + Z5 seconds
            - valid: Whether calculation was possible
    """
    result = {
        "z1_time": 0.0,
        "z2_time": 0.0,
        "z3_time": 0.0,
        "z4_time": 0.0,
        "z5_time": 0.0,
        "aerobic_time": 0.0,
        "anaerobic_time": 0.0,
        "valid": False,
    }

    if not stream or not stream.heart_rate or not hr_zones:
        return result

    hr_samples = stream.heart_rate
    if len(hr_samples) < MIN_HR_SAMPLES_FOR_ZONES:
        return result

    # Calculate time per sample (assuming even distribution)
    time_per_sample = duration_seconds / len(hr_samples)

    # Zone thresholds
    z1_max = hr_zones["z1_max"]
    z2_max = hr_zones["z2_max"]
    z3_max = hr_zones["z3_max"]
    z4_max = hr_zones["z4_max"]

    # Count samples in each zone
    z1_count = 0
    z2_count = 0
    z3_count = 0
    z4_count = 0
    z5_count = 0

    for hr in hr_samples:
        if hr <= 0:
            continue
        elif hr < z1_max:
            z1_count += 1
        elif hr < z2_max:
            z2_count += 1
        elif hr < z3_max:
            z3_count += 1
        elif hr < z4_max:
            z4_count += 1
        else:
            z5_count += 1

    # Convert counts to time
    result["z1_time"] = z1_count * time_per_sample
    result["z2_time"] = z2_count * time_per_sample
    result["z3_time"] = z3_count * time_per_sample
    result["z4_time"] = z4_count * time_per_sample
    result["z5_time"] = z5_count * time_per_sample

    # Aggregated zones
    result["aerobic_time"] = result["z1_time"] + result["z2_time"]
    result["anaerobic_time"] = result["z4_time"] + result["z5_time"]

    result["valid"] = True
    return result


def compute_cardiac_drift(
    stream: Stream | None,
    duration_seconds: float,
) -> float | None:
    """Compute cardiac drift as percentage HR increase.

    Compares average HR in first half vs second half of activity.
    Positive drift indicates decoupling (HR rising for same effort).

    Args:
        stream: Stream record with heart_rate data
        duration_seconds: Total activity duration in seconds

    Returns:
        Percentage drift (e.g., 5.0 means 5% increase), or None if not calculable
    """
    if not stream or not stream.heart_rate:
        return None

    hr_samples = stream.heart_rate
    if len(hr_samples) < 20:  # Need enough samples for meaningful split
        return None

    midpoint = len(hr_samples) // 2

    first_half = [hr for hr in hr_samples[:midpoint] if hr > 0]
    second_half = [hr for hr in hr_samples[midpoint:] if hr > 0]

    if not first_half or not second_half:
        return None

    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)

    if avg_first <= 0:
        return None

    drift = ((avg_second - avg_first) / avg_first) * 100
    return round(drift, 2)


def compute_hr_efficiency(
    activity_type: str | None,
    avg_hr: float | None,
    avg_speed: float | None,
    avg_watts: float | None,
) -> float | None:
    """Compute HR efficiency metric.

    For running/cycling: speed or power per heart beat.
    Higher values indicate better aerobic efficiency.

    Args:
        activity_type: Type of activity
        avg_hr: Average heart rate
        avg_speed: Average speed in m/s
        avg_watts: Average power in watts

    Returns:
        Efficiency metric, or None if not calculable
    """
    if not avg_hr or avg_hr <= 0:
        return None

    # Power-based efficiency (watts per bpm)
    if avg_watts and avg_watts > 0:
        return round(avg_watts / avg_hr, 3)

    # Speed-based efficiency (m/s per bpm × 100)
    if avg_speed and avg_speed > 0:
        return round((avg_speed / avg_hr) * 100, 3)

    return None
