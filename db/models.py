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
