"""Athlete profile management."""

from sqlalchemy.orm import Session
from sqlalchemy import func

from db.models import AthleteProfile, Activity
from metrics.config import DEFAULT_HR_ZONE_THRESHOLDS, LTHR_ESTIMATE_PCT


def get_or_create_profile(session: Session) -> AthleteProfile:
    """Get existing profile or create a new one.

    Returns the singleton athlete profile, creating it if it doesn't exist.
    """
    profile = session.query(AthleteProfile).first()

    if profile is None:
        profile = AthleteProfile()
        session.add(profile)
        session.commit()

    return profile


def estimate_max_hr(session: Session) -> int | None:
    """Estimate max HR from activity data.

    Returns the highest max_hr recorded across all activities.
    """
    result = session.query(func.max(Activity.max_hr)).scalar()
    return int(result) if result else None


def estimate_lthr(max_hr: int) -> int:
    """Estimate LTHR from max HR.

    Uses standard 89% of max HR estimation.
    """
    return int(max_hr * LTHR_ESTIMATE_PCT)


def update_estimates(session: Session) -> AthleteProfile:
    """Update auto-estimated values in the profile.

    Computes estimates from activity data and saves them.
    """
    profile = get_or_create_profile(session)

    # Estimate max HR from highest recorded
    estimated_max = estimate_max_hr(session)
    if estimated_max:
        profile.estimated_max_hr = estimated_max
        profile.estimated_lthr = estimate_lthr(estimated_max)

    session.commit()
    return profile


def get_effective_values(session: Session) -> dict:
    """Get effective profile values (user values take precedence over estimates).

    Returns a dict with:
        - max_hr: Effective max HR
        - lthr: Effective lactate threshold HR
        - resting_hr: Resting HR (may be None)
        - ftp: Functional threshold power (may be None)
        - weight_kg: Body weight (may be None)
        - hr_zones: Zone thresholds as HR values
        - has_user_max_hr: Whether max_hr was user-specified
        - has_user_lthr: Whether lthr was user-specified
    """
    profile = get_or_create_profile(session)

    # Ensure we have estimates
    if profile.estimated_max_hr is None:
        update_estimates(session)
        session.refresh(profile)

    # User values take precedence
    max_hr = profile.max_hr or profile.estimated_max_hr
    lthr = profile.lthr or profile.estimated_lthr

    # Get zone thresholds (user custom or defaults)
    zone_pcts = profile.hr_zone_thresholds or DEFAULT_HR_ZONE_THRESHOLDS

    # Convert zone percentages to actual HR values
    hr_zones = None
    if lthr:
        hr_zones = {
            "z1_max": int(lthr * zone_pcts["z1_max"] / 100),
            "z2_max": int(lthr * zone_pcts["z2_max"] / 100),
            "z3_max": int(lthr * zone_pcts["z3_max"] / 100),
            "z4_max": int(lthr * zone_pcts["z4_max"] / 100),
        }

    return {
        "max_hr": max_hr,
        "lthr": lthr,
        "resting_hr": profile.resting_hr,
        "ftp": profile.ftp,
        "weight_kg": profile.weight_kg,
        "hr_zones": hr_zones,
        "zone_pcts": zone_pcts,
        "has_user_max_hr": profile.max_hr is not None,
        "has_user_lthr": profile.lthr is not None,
    }
