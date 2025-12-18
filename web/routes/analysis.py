"""Performance analysis routes."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from web.app import templates, get_db

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def analysis_index(request: Request, db: Session = Depends(get_db)):
    """Render the performance analysis overview."""
    from web.services.records import get_personal_records, get_hr_stats

    records = get_personal_records(db)
    hr_stats = get_hr_stats(db)

    return templates.TemplateResponse(
        "analysis/index.html",
        {
            "request": request,
            "records": records,
            "hr_stats": hr_stats,
        },
    )


@router.get("/records", response_class=HTMLResponse)
async def records_page(request: Request, db: Session = Depends(get_db)):
    """Render the personal records page."""
    from web.services.records import get_personal_records_by_type

    records_by_type = get_personal_records_by_type(db)

    return templates.TemplateResponse(
        "analysis/records.html",
        {
            "request": request,
            "records_by_type": records_by_type,
        },
    )


@router.get("/api/elevation/{activity_id}")
async def elevation_profile_data(
    activity_id: str,
    db: Session = Depends(get_db),
):
    """Return elevation profile data as JSON for Chart.js."""
    from db.models import Stream

    stream = db.query(Stream).filter_by(activity_id=activity_id).first()

    if not stream or not stream.altitude:
        return JSONResponse(content={"labels": [], "data": []})

    # Create labels (point index or distance if we calculate it)
    labels = list(range(len(stream.altitude)))

    return JSONResponse(
        content={
            "labels": labels,
            "data": stream.altitude,
        }
    )


@router.get("/api/heartrate/{activity_id}")
async def heartrate_profile_data(
    activity_id: str,
    db: Session = Depends(get_db),
):
    """Return heart rate profile data as JSON for Chart.js."""
    from db.models import Stream

    stream = db.query(Stream).filter_by(activity_id=activity_id).first()

    if not stream or not stream.heart_rate:
        return JSONResponse(content={"labels": [], "data": []})

    labels = list(range(len(stream.heart_rate)))

    return JSONResponse(
        content={
            "labels": labels,
            "data": stream.heart_rate,
        }
    )
