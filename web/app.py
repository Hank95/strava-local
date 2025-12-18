"""FastAPI application for Strava Local."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Import shared dependencies (templates, get_db)
from web.deps import templates, get_db  # noqa: F401 - re-exported for backwards compatibility

# Paths
WEB_DIR = Path(__file__).parent
STATIC_DIR = WEB_DIR / "static"

# Create FastAPI app
app = FastAPI(
    title="Strava Local",
    description="Local analysis of your Strava data",
)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Import and include routers after app is created
from web.routes import dashboard, activities, maps, analysis, fitness, settings

app.include_router(dashboard.router)
app.include_router(activities.router, prefix="/activities", tags=["activities"])
app.include_router(maps.router, prefix="/maps", tags=["maps"])
app.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
app.include_router(fitness.router, prefix="/fitness", tags=["fitness"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])
