"""SQLAlchemy models for Strava Local database."""
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Activity(Base):
    """Activity table - one row per activity from CSV."""

    __tablename__ = "activities"

    # Primary key - activity ID from Strava
    activity_id = Column(String, primary_key=True)

    # Core summary fields
    name = Column(String, nullable=True)
    activity_type = Column(String, nullable=True)
    start_time = Column(DateTime, nullable=True)

    # Distance and time
    distance = Column(Float, nullable=True)  # meters
    moving_time = Column(Float, nullable=True)  # seconds
    elapsed_time = Column(Float, nullable=True)  # seconds

    # Speed
    avg_speed = Column(Float, nullable=True)  # m/s
    max_speed = Column(Float, nullable=True)  # m/s

    # Heart rate
    avg_hr = Column(Float, nullable=True)
    max_hr = Column(Float, nullable=True)

    # Elevation
    elevation_gain = Column(Float, nullable=True)  # meters
    elevation_loss = Column(Float, nullable=True)  # meters
    elevation_low = Column(Float, nullable=True)  # meters
    elevation_high = Column(Float, nullable=True)  # meters

    # Power
    avg_watts = Column(Float, nullable=True)
    max_watts = Column(Float, nullable=True)

    # Cadence
    avg_cadence = Column(Float, nullable=True)
    max_cadence = Column(Float, nullable=True)

    # Other
    calories = Column(Float, nullable=True)
    athlete_weight = Column(Float, nullable=True)  # kg

    # Store any extra CSV columns as JSON
    csv_extra = Column(JSON, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    fit_file = relationship("FitFile", back_populates="activity", uselist=False)
    stream = relationship("Stream", back_populates="activity", uselist=False)

    def __repr__(self) -> str:
        return f"<Activity {self.activity_id}: {self.name}>"


class FitFile(Base):
    """FIT file metadata table."""

    __tablename__ = "fit_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(String, ForeignKey("activities.activity_id"), unique=True, nullable=False)

    # File info
    fit_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)  # bytes
    sha256 = Column(String(64), nullable=True)

    # Parsed info from FIT
    fit_start_time = Column(DateTime, nullable=True)
    fit_sport = Column(String, nullable=True)
    fit_distance = Column(Float, nullable=True)  # meters

    # Metadata
    ingested_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    activity = relationship("Activity", back_populates="fit_file")

    def __repr__(self) -> str:
        return f"<FitFile {self.fit_path}>"


class Stream(Base):
    """Time-series stream data extracted from FIT files."""

    __tablename__ = "streams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(String, ForeignKey("activities.activity_id"), unique=True, nullable=False)

    # Downsampled lat/lon track as JSON array of [lat, lon] pairs
    # Null if no GPS data
    route = Column(JSON, nullable=True)

    # Heart rate stream as JSON array
    heart_rate = Column(JSON, nullable=True)

    # Altitude stream as JSON array
    altitude = Column(JSON, nullable=True)

    # Has GPS flag for quick querying
    has_gps = Column(Boolean, default=False)

    # Number of original points before downsampling
    original_point_count = Column(Integer, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    activity = relationship("Activity", back_populates="stream")

    def __repr__(self) -> str:
        gps_status = "with GPS" if self.has_gps else "no GPS"
        return f"<Stream {self.activity_id} ({gps_status})>"


class AthleteProfile(Base):
    """Athlete profile for personalized metrics calculation.

    Stores both user-configured values and auto-estimated values.
    User values take precedence when set.
    """

    __tablename__ = "athlete_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # User-configured physiological parameters (take precedence)
    max_hr = Column(Integer, nullable=True)  # Maximum heart rate
    resting_hr = Column(Integer, nullable=True)  # Resting heart rate
    lthr = Column(Integer, nullable=True)  # Lactate threshold heart rate
    ftp = Column(Integer, nullable=True)  # Functional threshold power (watts)
    weight_kg = Column(Float, nullable=True)  # Body weight in kg

    # Auto-estimated values (computed from activity data)
    estimated_max_hr = Column(Integer, nullable=True)
    estimated_lthr = Column(Integer, nullable=True)

    # Custom HR zone thresholds as percentages of LTHR
    # Format: {"z1_max": 68, "z2_max": 83, "z3_max": 94, "z4_max": 105}
    hr_zone_thresholds = Column(JSON, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<AthleteProfile max_hr={self.max_hr or self.estimated_max_hr}>"


class ActivityMetrics(Base):
    """Per-activity derived metrics including TSS and HR zones."""

    __tablename__ = "activity_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(String, ForeignKey("activities.activity_id"), unique=True, nullable=False)

    # Training Stress Score
    tss = Column(Float, nullable=True)  # Computed TSS value
    tss_method = Column(String, nullable=True)  # 'hr', 'power', or 'duration'
    intensity_factor = Column(Float, nullable=True)  # IF for power-based
    normalized_power = Column(Float, nullable=True)  # NP for power-based

    # HR Zone time distribution (seconds in each zone)
    hr_z1_time = Column(Float, nullable=True)  # Recovery
    hr_z2_time = Column(Float, nullable=True)  # Aerobic
    hr_z3_time = Column(Float, nullable=True)  # Tempo
    hr_z4_time = Column(Float, nullable=True)  # Threshold
    hr_z5_time = Column(Float, nullable=True)  # VO2max

    # Aggregated zone time
    aerobic_time = Column(Float, nullable=True)  # Z1 + Z2
    anaerobic_time = Column(Float, nullable=True)  # Z4 + Z5

    # Advanced HR metrics
    trimp = Column(Float, nullable=True)  # Training Impulse
    hr_efficiency = Column(Float, nullable=True)  # pace/HR or power/HR
    cardiac_drift = Column(Float, nullable=True)  # % HR increase over activity

    # Data availability flags
    has_power_data = Column(Boolean, default=False)
    has_hr_stream = Column(Boolean, default=False)

    # Metadata
    computed_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    activity = relationship("Activity", backref="metrics")

    def __repr__(self) -> str:
        return f"<ActivityMetrics {self.activity_id} TSS={self.tss}>"


class DailyMetrics(Base):
    """Daily aggregated metrics and training load (ATL, CTL, TSB)."""

    __tablename__ = "daily_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, unique=True, nullable=False)  # YYYY-MM-DD format

    # Daily activity totals
    activity_count = Column(Integer, default=0)
    total_distance = Column(Float, default=0)  # meters
    total_moving_time = Column(Float, default=0)  # seconds
    total_elevation = Column(Float, default=0)  # meters
    total_tss = Column(Float, default=0)
    total_calories = Column(Float, default=0)

    # Training load metrics (Exponential Moving Averages)
    atl = Column(Float, nullable=True)  # Acute Training Load (fatigue, 7-day)
    ctl = Column(Float, nullable=True)  # Chronic Training Load (fitness, 42-day)
    tsb = Column(Float, nullable=True)  # Training Stress Balance (form = CTL - ATL)

    # Daily HR zone totals (seconds)
    total_hr_z1_time = Column(Float, default=0)
    total_hr_z2_time = Column(Float, default=0)
    total_hr_z3_time = Column(Float, default=0)
    total_hr_z4_time = Column(Float, default=0)
    total_hr_z5_time = Column(Float, default=0)

    # Streak tracking
    has_activity = Column(Boolean, default=False)

    # Metadata
    computed_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<DailyMetrics {self.date} TSS={self.total_tss} CTL={self.ctl}>"


class PeriodAggregation(Base):
    """Aggregated metrics for weeks, months, and years."""

    __tablename__ = "period_aggregations"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Period identification
    period_type = Column(String, nullable=False)  # 'week', 'month', 'year'
    period_start = Column(String, nullable=False)  # YYYY-MM-DD of period start
    period_key = Column(String, nullable=False)  # e.g., '2024-W01', '2024-01', '2024'

    # Totals
    activity_count = Column(Integer, default=0)
    total_distance = Column(Float, default=0)  # meters
    total_moving_time = Column(Float, default=0)  # seconds
    total_elevation = Column(Float, default=0)  # meters
    total_tss = Column(Float, default=0)
    total_calories = Column(Float, default=0)

    # Averages (per activity)
    avg_distance = Column(Float, nullable=True)
    avg_tss = Column(Float, nullable=True)
    avg_hr = Column(Float, nullable=True)

    # Streak and consistency
    active_days = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)

    # Breakdown by activity type as JSON
    # Format: {"Run": {"count": 10, "distance": 50000}, "Ride": {...}}
    by_type = Column(JSON, nullable=True)

    # Metadata
    computed_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PeriodAggregation {self.period_type} {self.period_key}>"


class RollingAverage(Base):
    """Rolling averages for trend analysis."""

    __tablename__ = "rolling_averages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, unique=True, nullable=False)  # YYYY-MM-DD format

    # 7-day rolling averages
    avg_7d_distance = Column(Float, nullable=True)
    avg_7d_time = Column(Float, nullable=True)
    avg_7d_tss = Column(Float, nullable=True)
    count_7d_activities = Column(Integer, nullable=True)

    # 30-day rolling averages
    avg_30d_distance = Column(Float, nullable=True)
    avg_30d_time = Column(Float, nullable=True)
    avg_30d_tss = Column(Float, nullable=True)
    count_30d_activities = Column(Integer, nullable=True)

    # 90-day rolling averages
    avg_90d_distance = Column(Float, nullable=True)
    avg_90d_time = Column(Float, nullable=True)
    avg_90d_tss = Column(Float, nullable=True)
    count_90d_activities = Column(Integer, nullable=True)

    # Year-to-date comparisons
    ytd_distance = Column(Float, nullable=True)
    ytd_activities = Column(Integer, nullable=True)
    prev_ytd_distance = Column(Float, nullable=True)  # Same day last year
    prev_ytd_activities = Column(Integer, nullable=True)

    # Metadata
    computed_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<RollingAverage {self.date}>"


# Database path
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "strava_local.db"


def get_engine(db_path: Path | None = None, echo: bool = False):
    """Create and return a SQLAlchemy engine."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    # Ensure the data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return create_engine(f"sqlite:///{db_path}", echo=echo)


def get_session(engine=None) -> Session:
    """Create and return a new database session."""
    if engine is None:
        engine = get_engine()

    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def init_db(engine=None) -> None:
    """Initialize the database schema."""
    if engine is None:
        engine = get_engine()

    Base.metadata.create_all(engine)
