"""Map routes."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from web.app import templates, get_db
from web.services.stats import get_activity_types

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def maps_index(request: Request, db: Session = Depends(get_db)):
    """Render the map exploration page."""
    activity_types = get_activity_types(db)

    return templates.TemplateResponse(
        "maps/index.html",
        {
            "request": request,
            "activity_types": activity_types,
        },
    )


@router.get("/embed/heatmap", response_class=HTMLResponse)
async def embed_heatmap(
    request: Request,
    db: Session = Depends(get_db),
    type: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    limit: Optional[int] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    """Return heatmap HTML for iframe embedding."""
    from web.services.maps import generate_heatmap_html

    after_date = datetime.strptime(after, "%Y-%m-%d") if after else None
    before_date = datetime.strptime(before, "%Y-%m-%d") if before else None

    html = generate_heatmap_html(
        db,
        activity_type=type,
        after=after_date,
        before=before_date,
        limit=limit,
        user_lat=lat,
        user_lon=lon,
    )

    return HTMLResponse(content=html)


@router.get("/embed/routes", response_class=HTMLResponse)
async def embed_routes(
    request: Request,
    db: Session = Depends(get_db),
    type: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    limit: Optional[int] = 100,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    """Return routes map HTML for iframe embedding."""
    from web.services.maps import generate_routes_html

    after_date = datetime.strptime(after, "%Y-%m-%d") if after else None
    before_date = datetime.strptime(before, "%Y-%m-%d") if before else None

    html = generate_routes_html(
        db,
        activity_type=type,
        after=after_date,
        before=before_date,
        limit=limit,
        user_lat=lat,
        user_lon=lon,
    )

    return HTMLResponse(content=html)


@router.get("/embed/activity/{activity_id}", response_class=HTMLResponse)
async def embed_activity_map(
    request: Request,
    activity_id: str,
    db: Session = Depends(get_db),
):
    """Return single activity map HTML for iframe embedding."""
    from web.services.maps import generate_activity_map_html

    html = generate_activity_map_html(db, activity_id)

    if html is None:
        return HTMLResponse(
            content="<p>No GPS data available for this activity.</p>",
            status_code=404,
        )

    return HTMLResponse(content=html)
