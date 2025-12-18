"""Shared dependencies for web routes."""

import sys
from pathlib import Path
from typing import Generator

from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import get_engine, get_session

# Paths
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"

# Setup Jinja2 templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database session."""
    engine = get_engine()
    session = get_session(engine)
    try:
        yield session
    finally:
        session.close()
