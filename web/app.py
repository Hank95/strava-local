"""FastAPI application for Strava Local."""
import sys
from pathlib import Path
from typing import Generator

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import get_engine, get_session

# Paths
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Create FastAPI app
app = FastAPI(
    title="Strava Local",
    description="Local analysis of your Strava data",
)

# Setup Jinja2 templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database session."""
    engine = get_engine()
    session = get_session(engine)
    try:
        yield session
    finally:
        session.close()


# Import and include routers after app is created
from web.routes import dashboard, activities, maps, analysis

app.include_router(dashboard.router)
app.include_router(activities.router, prefix="/activities", tags=["activities"])
app.include_router(maps.router, prefix="/maps", tags=["maps"])
app.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
