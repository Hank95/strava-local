"""Settings routes for profile configuration."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from web.deps import templates, get_db
from db.models import AthleteProfile
from metrics.profile import get_or_create_profile, get_effective_values
from metrics.config import DEFAULT_HR_ZONE_THRESHOLDS


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Render the settings page."""
    profile = get_or_create_profile(db)
    effective = get_effective_values(db)

    return templates.TemplateResponse(
        "settings/index.html",
        {
            "request": request,
            "profile": profile,
            "effective": effective,
            "default_zones": DEFAULT_HR_ZONE_THRESHOLDS,
        },
    )


@router.post("/profile", response_class=HTMLResponse)
async def update_profile(
    request: Request,
    db: Session = Depends(get_db),
    max_hr: str = Form(default=""),
    resting_hr: str = Form(default=""),
    lthr: str = Form(default=""),
    ftp: str = Form(default=""),
    weight_kg: str = Form(default=""),
):
    """Update athlete profile settings."""
    profile = get_or_create_profile(db)

    # Parse and update values (empty string = None/use estimate)
    profile.max_hr = int(max_hr) if max_hr.strip() else None
    profile.resting_hr = int(resting_hr) if resting_hr.strip() else None
    profile.lthr = int(lthr) if lthr.strip() else None
    profile.ftp = int(ftp) if ftp.strip() else None
    profile.weight_kg = float(weight_kg) if weight_kg.strip() else None

    db.commit()

    # Redirect back to settings with success message
    return RedirectResponse(url="/settings?saved=1", status_code=303)


@router.post("/recompute", response_class=HTMLResponse)
async def trigger_recompute(request: Request, db: Session = Depends(get_db)):
    """Trigger a full metrics recomputation."""
    from metrics.compute import run_full_computation

    # Run computation (this may take a while for large datasets)
    stats = run_full_computation(db, force=True, quiet=True)

    # Redirect back with stats
    return RedirectResponse(
        url=f"/settings?recomputed=1&count={stats['activities_processed']}",
        status_code=303,
    )
