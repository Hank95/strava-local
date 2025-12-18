"""Activity browser routes."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from web.app import templates, get_db
from web.services.stats import get_activity_types

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def activity_list(
    request: Request,
    db: Session = Depends(get_db),
    type: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    has_gps: Optional[str] = None,
    page: int = 1,
    per_page: int = 25,
):
    """Render the activity browser."""
    from sqlalchemy import func
    from db.models import Activity, Stream

    # Parse has_gps string to bool (handles empty strings from forms)
    has_gps_bool: Optional[bool] = None
    if has_gps == "true":
        has_gps_bool = True
    elif has_gps == "false":
        has_gps_bool = False

    # Build query
    query = db.query(Activity)

    if type:
        query = query.filter(Activity.activity_type == type)

    if after:
        after_date = datetime.strptime(after, "%Y-%m-%d")
        query = query.filter(Activity.start_time >= after_date)

    if before:
        before_date = datetime.strptime(before, "%Y-%m-%d")
        query = query.filter(Activity.start_time <= before_date)

    if has_gps_bool is not None:
        query = query.join(Stream, Activity.activity_id == Stream.activity_id)
        query = query.filter(Stream.has_gps == has_gps_bool)

    # Get total count
    total = query.count()

    # Order and paginate
    query = query.order_by(Activity.start_time.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    activities = query.all()
    activity_types = get_activity_types(db)

    # Calculate pagination
    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse(
        "activities/index.html",
        {
            "request": request,
            "activities": activities,
            "activity_types": activity_types,
            "current_type": type,
            "current_after": after,
            "current_before": before,
            "current_has_gps": has_gps_bool,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.get("/{activity_id}", response_class=HTMLResponse)
async def activity_detail(
    request: Request,
    activity_id: str,
    db: Session = Depends(get_db),
):
    """Render a single activity detail page."""
    from db.models import Activity, Stream, FitFile

    activity = db.query(Activity).filter_by(activity_id=activity_id).first()
    if not activity:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Activity not found")

    stream = db.query(Stream).filter_by(activity_id=activity_id).first()
    fit_file = db.query(FitFile).filter_by(activity_id=activity_id).first()

    return templates.TemplateResponse(
        "activities/detail.html",
        {
            "request": request,
            "activity": activity,
            "stream": stream,
            "fit_file": fit_file,
        },
    )


@router.get("/api/table", response_class=HTMLResponse)
async def activity_table_partial(
    request: Request,
    db: Session = Depends(get_db),
    type: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    has_gps: Optional[str] = None,
    page: int = 1,
    per_page: int = 25,
):
    """HTMX partial: return just the activity table rows."""
    from db.models import Activity, Stream

    # Parse has_gps string to bool (handles empty strings from forms)
    has_gps_bool: Optional[bool] = None
    if has_gps == "true":
        has_gps_bool = True
    elif has_gps == "false":
        has_gps_bool = False

    query = db.query(Activity)

    if type:
        query = query.filter(Activity.activity_type == type)

    if after:
        after_date = datetime.strptime(after, "%Y-%m-%d")
        query = query.filter(Activity.start_time >= after_date)

    if before:
        before_date = datetime.strptime(before, "%Y-%m-%d")
        query = query.filter(Activity.start_time <= before_date)

    if has_gps_bool is not None:
        query = query.join(Stream, Activity.activity_id == Stream.activity_id)
        query = query.filter(Stream.has_gps == has_gps_bool)

    total = query.count()
    query = query.order_by(Activity.start_time.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    activities = query.all()
    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse(
        "partials/activity_table.html",
        {
            "request": request,
            "activities": activities,
            "page": page,
            "total": total,
            "total_pages": total_pages,
        },
    )
