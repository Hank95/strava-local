"""Configuration constants for metrics computation."""

# HR Zone thresholds as percentage of LTHR (Friel zones)
# Z1: Recovery (< z1_max%)
# Z2: Aerobic (z1_max% - z2_max%)
# Z3: Tempo (z2_max% - z3_max%)
# Z4: Threshold (z3_max% - z4_max%)
# Z5: VO2max (> z4_max%)
DEFAULT_HR_ZONE_THRESHOLDS = {
    "z1_max": 68,   # < 68% LTHR
    "z2_max": 83,   # 68-83% LTHR
    "z3_max": 94,   # 83-94% LTHR
    "z4_max": 105,  # 94-105% LTHR
    # Z5 is anything above 105%
}

# TSS estimation factors by activity type (per hour)
# These are used when HR/power data is unavailable
TSS_DURATION_FACTORS = {
    "Run": 65,
    "Ride": 55,
    "VirtualRide": 60,
    "Walk": 30,
    "Hike": 45,
    "Swim": 70,
    "Workout": 50,
    "WeightTraining": 40,
    "Yoga": 20,
    "Golf": 25,
    "default": 45,
}

# Exponential moving average decay factors
# ATL (Acute Training Load) - 7 day time constant
# Formula: new_atl = old_atl * ATL_DECAY + today_tss * (1 - ATL_DECAY)
ATL_DECAY = 0.857  # exp(-1/7) ≈ 0.857

# CTL (Chronic Training Load) - 42 day time constant
CTL_DECAY = 0.976  # exp(-1/42) ≈ 0.976

# TRIMP constants (Bannister's Training Impulse)
# Gender-specific exponential weighting factor
TRIMP_FACTOR_MALE = 1.92
TRIMP_FACTOR_FEMALE = 1.67
TRIMP_FACTOR_DEFAULT = 1.80  # Average

# Default LTHR estimation as percentage of max HR
LTHR_ESTIMATE_PCT = 0.89  # 89% of max HR

# Minimum data requirements
MIN_HR_SAMPLES_FOR_ZONES = 10  # Minimum HR data points for zone calculation
MIN_ACTIVITY_DURATION_SECONDS = 60  # Minimum duration to compute TSS
