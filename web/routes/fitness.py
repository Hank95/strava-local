"""Fitness dashboard routes."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from web.deps import templates, get_db
from web.services.fitness import (
    get_training_load_chart_data,
    get_current_form_status,
    get_weekly_summary,
    get_recent_activities_with_tss,
    get_hr_zone_distribution,
    get_streak_info,
    get_fitness_summary,
)
from metrics.profile import get_effective_values

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def fitness_dashboard(request: Request, db: Session = Depends(get_db)):
    """Render the fitness dashboard."""
    form_status = get_current_form_status(db)
    weekly_summary = get_weekly_summary(db, weeks=8)
    recent_activities = get_recent_activities_with_tss(db, limit=10)
    streak_info = get_streak_info(db)
    fitness_summary = get_fitness_summary(db)
    profile = get_effective_values(db)

    return templates.TemplateResponse(
        "analysis/fitness.html",
        {
            "request": request,
            "form_status": form_status,
            "weekly_summary": weekly_summary,
            "recent_activities": recent_activities,
            "streak_info": streak_info,
            "fitness_summary": fitness_summary,
            "profile": profile,
        },
    )


@router.get("/api/training-load", response_class=JSONResponse)
async def api_training_load(
    request: Request,
    db: Session = Depends(get_db),
    days: int = 90,
):
    """Return training load data for charts."""
    data = get_training_load_chart_data(db, days=days)
    return JSONResponse(content=data)


@router.get("/api/hr-zones/{activity_id}", response_class=JSONResponse)
async def api_hr_zones(
    request: Request,
    activity_id: str,
    db: Session = Depends(get_db),
):
    """Return HR zone distribution for an activity."""
    data = get_hr_zone_distribution(db, activity_id)
    if data is None:
        return JSONResponse(content={"error": "No HR zone data available"}, status_code=404)
    return JSONResponse(content=data)


@router.get("/api/weekly-summary", response_class=JSONResponse)
async def api_weekly_summary(
    request: Request,
    db: Session = Depends(get_db),
    weeks: int = 12,
):
    """Return weekly summary data."""
    data = get_weekly_summary(db, weeks=weeks)
    return JSONResponse(content=data)


@router.get("/api/current-form", response_class=JSONResponse)
async def api_current_form(request: Request, db: Session = Depends(get_db)):
    """Return current training form status."""
    data = get_current_form_status(db)
    return JSONResponse(content=data)
