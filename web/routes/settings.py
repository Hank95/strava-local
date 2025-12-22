"""Settings routes for profile configuration."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from web.deps import templates, get_db
from db.models import AthleteProfile
from metrics.profile import get_or_create_profile, get_effective_values
from metrics.config import DEFAULT_HR_ZONE_THRESHOLDS
from web.services import strava as strava_service


router = APIRouter()

# Base URL for OAuth callback - adjust for your deployment
OAUTH_CALLBACK_BASE = "http://localhost:8000"


@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Render the settings page."""
    profile = get_or_create_profile(db)
    effective = get_effective_values(db)

    # Check Strava connection status
    strava_connected = strava_service.is_connected(profile)

    return templates.TemplateResponse(
        "settings/index.html",
        {
            "request": request,
            "profile": profile,
            "effective": effective,
            "default_zones": DEFAULT_HR_ZONE_THRESHOLDS,
            "strava_connected": strava_connected,
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


# =============================================================================
# Strava API Integration Routes
# =============================================================================


@router.post("/strava", response_class=HTMLResponse)
async def save_strava_credentials(
    request: Request,
    db: Session = Depends(get_db),
    strava_client_id: str = Form(default=""),
    strava_client_secret: str = Form(default=""),
):
    """Save Strava API credentials."""
    profile = get_or_create_profile(db)

    profile.strava_client_id = strava_client_id.strip() if strava_client_id.strip() else None
    profile.strava_client_secret = strava_client_secret.strip() if strava_client_secret.strip() else None
    db.commit()

    return RedirectResponse(url="/settings?strava_saved=1", status_code=303)


@router.get("/strava/connect", response_class=HTMLResponse)
async def strava_connect(request: Request, db: Session = Depends(get_db)):
    """Redirect to Strava OAuth authorization."""
    profile = get_or_create_profile(db)

    if not profile.strava_client_id:
        return RedirectResponse(url="/settings?strava_error=no_credentials", status_code=303)

    redirect_uri = f"{OAUTH_CALLBACK_BASE}/settings/strava/callback"
    auth_url = strava_service.get_authorization_url(profile.strava_client_id, redirect_uri)

    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/strava/callback", response_class=HTMLResponse)
async def strava_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str = None,
    error: str = None,
):
    """Handle Strava OAuth callback."""
    if error:
        return RedirectResponse(url=f"/settings?strava_error={error}", status_code=303)

    if not code:
        return RedirectResponse(url="/settings?strava_error=no_code", status_code=303)

    profile = get_or_create_profile(db)

    if not profile.strava_client_id or not profile.strava_client_secret:
        return RedirectResponse(url="/settings?strava_error=no_credentials", status_code=303)

    try:
        # Exchange code for tokens
        tokens = strava_service.exchange_code_for_tokens(
            profile.strava_client_id,
            profile.strava_client_secret,
            code,
        )

        # Save tokens to profile
        profile.strava_access_token = tokens["access_token"]
        profile.strava_refresh_token = tokens["refresh_token"]
        profile.strava_token_expires_at = tokens["expires_at"]
        if "athlete" in tokens:
            profile.strava_athlete_id = tokens["athlete"].get("id")
        db.commit()

        return RedirectResponse(url="/settings?strava_connected=1", status_code=303)

    except Exception as e:
        print(f"Strava OAuth error: {e}")
        return RedirectResponse(url="/settings?strava_error=token_exchange_failed", status_code=303)


@router.post("/strava/sync", response_class=HTMLResponse)
async def strava_sync(request: Request, db: Session = Depends(get_db)):
    """Sync activities from Strava API."""
    profile = get_or_create_profile(db)

    if not strava_service.is_connected(profile):
        return RedirectResponse(url="/settings?strava_error=not_connected", status_code=303)

    try:
        stats = strava_service.sync_activities(db, profile)
        return RedirectResponse(
            url=f"/settings?strava_synced=1&new={stats['new']}&updated={stats['updated']}",
            status_code=303,
        )
    except Exception as e:
        print(f"Strava sync error: {e}")
        return RedirectResponse(url="/settings?strava_error=sync_failed", status_code=303)


@router.post("/strava/disconnect", response_class=HTMLResponse)
async def strava_disconnect(request: Request, db: Session = Depends(get_db)):
    """Disconnect Strava integration."""
    profile = get_or_create_profile(db)
    strava_service.disconnect(db, profile)

    return RedirectResponse(url="/settings?strava_disconnected=1", status_code=303)
