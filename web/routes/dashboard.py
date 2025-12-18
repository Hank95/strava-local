"""Dashboard routes."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from web.app import templates, get_db
from web.services.stats import (
    get_summary_stats,
    get_activity_type_breakdown,
    get_activities_over_time,
    get_recent_activities,
)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Render the main dashboard."""
    stats = get_summary_stats(db)
    type_breakdown = get_activity_type_breakdown(db)
    time_data = get_activities_over_time(db)
    recent = get_recent_activities(db, limit=10)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "type_breakdown": type_breakdown,
            "time_data": time_data,
            "recent_activities": recent,
        },
    )


@router.get("/api/stats/chart", response_class=HTMLResponse)
async def stats_chart_data(
    request: Request,
    grouping: str = "month",
    db: Session = Depends(get_db),
):
    """Return activity chart data as JSON for Chart.js."""
    from fastapi.responses import JSONResponse

    time_data = get_activities_over_time(db, grouping=grouping)
    return JSONResponse(content=time_data)
