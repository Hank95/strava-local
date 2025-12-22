"""Strava API integration service."""

import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from db.models import AthleteProfile, Activity, Stream, FitFile


# Strava API endpoints
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"


def get_authorization_url(client_id: str, redirect_uri: str) -> str:
    """Generate the Strava OAuth authorization URL."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "read,activity:read_all",
    }
    return f"{STRAVA_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    code: str,
) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    with httpx.Client() as client:
        response = client.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()


def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict:
    """Refresh an expired access token."""
    with httpx.Client() as client:
        response = client.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        return response.json()


def get_valid_access_token(db: Session, profile: AthleteProfile) -> Optional[str]:
    """Get a valid access token, refreshing if necessary."""
    if not profile.strava_access_token:
        return None

    # Check if token is expired (with 5 minute buffer)
    if profile.strava_token_expires_at and profile.strava_token_expires_at < time.time() + 300:
        # Token expired or expiring soon, refresh it
        if not profile.strava_refresh_token:
            return None

        try:
            tokens = refresh_access_token(
                profile.strava_client_id,
                profile.strava_client_secret,
                profile.strava_refresh_token,
            )
            # Update stored tokens
            profile.strava_access_token = tokens["access_token"]
            profile.strava_refresh_token = tokens["refresh_token"]
            profile.strava_token_expires_at = tokens["expires_at"]
            db.commit()
        except Exception:
            return None

    return profile.strava_access_token


def fetch_activities(
    access_token: str,
    after: Optional[int] = None,
    per_page: int = 50,
    page: int = 1,
) -> list[dict]:
    """Fetch activities from Strava API."""
    params = {"per_page": per_page, "page": page}
    if after:
        params["after"] = after

    with httpx.Client() as client:
        response = client.get(
            f"{STRAVA_API_BASE}/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        response.raise_for_status()
        return response.json()


def fetch_activity_streams(
    access_token: str,
    activity_id: int,
) -> dict:
    """Fetch detailed streams for a specific activity."""
    with httpx.Client() as client:
        response = client.get(
            f"{STRAVA_API_BASE}/activities/{activity_id}/streams",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "keys": "latlng,heartrate,altitude,time",
                "key_by_type": "true",
            },
        )
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json()


def sync_activities(db: Session, profile: AthleteProfile) -> dict:
    """Sync activities from Strava API to local database.

    Returns dict with sync statistics.
    """
    access_token = get_valid_access_token(db, profile)
    if not access_token:
        raise ValueError("No valid Strava access token")

    stats = {
        "fetched": 0,
        "new": 0,
        "updated": 0,
        "errors": 0,
    }

    # Get timestamp of last sync to only fetch newer activities
    after_timestamp = None
    if profile.strava_last_sync:
        after_timestamp = int(profile.strava_last_sync.timestamp())

    page = 1
    while True:
        activities = fetch_activities(
            access_token,
            after=after_timestamp,
            per_page=50,
            page=page,
        )

        if not activities:
            break

        stats["fetched"] += len(activities)

        for activity_data in activities:
            try:
                result = import_strava_activity(db, access_token, activity_data)
                if result == "new":
                    stats["new"] += 1
                elif result == "updated":
                    stats["updated"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"Error importing activity {activity_data.get('id')}: {e}")

        page += 1

        # Safety limit
        if page > 20:
            break

    # Update last sync time
    profile.strava_last_sync = datetime.utcnow()
    db.commit()

    return stats


def import_strava_activity(
    db: Session,
    access_token: str,
    activity_data: dict,
) -> str:
    """Import a single activity from Strava API data.

    Returns 'new', 'updated', or 'skipped'.
    """
    activity_id = str(activity_data["id"])

    # Check if activity already exists
    existing = db.query(Activity).filter_by(activity_id=activity_id).first()

    # Parse start time
    start_time = None
    if activity_data.get("start_date"):
        start_time = datetime.fromisoformat(activity_data["start_date"].replace("Z", "+00:00"))

    if existing:
        # Update existing activity
        existing.name = activity_data.get("name")
        existing.activity_type = activity_data.get("type")
        existing.start_time = start_time
        existing.distance = activity_data.get("distance")
        existing.moving_time = activity_data.get("moving_time")
        existing.elapsed_time = activity_data.get("elapsed_time")
        existing.avg_speed = activity_data.get("average_speed")
        existing.max_speed = activity_data.get("max_speed")
        existing.avg_hr = activity_data.get("average_heartrate")
        existing.max_hr = activity_data.get("max_heartrate")
        existing.elevation_gain = activity_data.get("total_elevation_gain")
        existing.calories = activity_data.get("calories")
        db.commit()
        return "updated"

    # Create new activity
    activity = Activity(
        activity_id=activity_id,
        name=activity_data.get("name"),
        activity_type=activity_data.get("type"),
        start_time=start_time,
        distance=activity_data.get("distance"),
        moving_time=activity_data.get("moving_time"),
        elapsed_time=activity_data.get("elapsed_time"),
        avg_speed=activity_data.get("average_speed"),
        max_speed=activity_data.get("max_speed"),
        avg_hr=activity_data.get("average_heartrate"),
        max_hr=activity_data.get("max_heartrate"),
        elevation_gain=activity_data.get("total_elevation_gain"),
        elevation_loss=None,  # Not in summary
        elevation_low=activity_data.get("elev_low"),
        elevation_high=activity_data.get("elev_high"),
        calories=activity_data.get("calories"),
    )
    db.add(activity)

    # Fetch and import streams if activity has GPS data
    if activity_data.get("start_latlng"):
        try:
            streams_data = fetch_activity_streams(access_token, int(activity_id))
            if streams_data:
                import_activity_streams(db, activity_id, streams_data)
        except Exception as e:
            print(f"Error fetching streams for {activity_id}: {e}")

    db.commit()
    return "new"


def import_activity_streams(
    db: Session,
    activity_id: str,
    streams_data: dict,
) -> None:
    """Import stream data for an activity."""
    # Check if stream already exists
    existing = db.query(Stream).filter_by(activity_id=activity_id).first()
    if existing:
        return

    # Extract GPS route
    route = None
    has_gps = False
    original_point_count = 0

    if "latlng" in streams_data:
        latlng_stream = streams_data["latlng"]
        if latlng_stream.get("data"):
            route = latlng_stream["data"]
            original_point_count = len(route)
            has_gps = True

            # Downsample if needed (max 500 points)
            if len(route) > 500:
                step = len(route) / 500
                route = [route[int(i * step)] for i in range(500)]

    # Extract heart rate
    heart_rate = None
    if "heartrate" in streams_data:
        hr_stream = streams_data["heartrate"]
        if hr_stream.get("data"):
            heart_rate = hr_stream["data"]
            # Downsample if needed
            if len(heart_rate) > 500:
                step = len(heart_rate) / 500
                heart_rate = [heart_rate[int(i * step)] for i in range(500)]

    # Extract altitude
    altitude = None
    if "altitude" in streams_data:
        alt_stream = streams_data["altitude"]
        if alt_stream.get("data"):
            altitude = alt_stream["data"]
            # Downsample if needed
            if len(altitude) > 500:
                step = len(altitude) / 500
                altitude = [altitude[int(i * step)] for i in range(500)]

    stream = Stream(
        activity_id=activity_id,
        route=route,
        heart_rate=heart_rate,
        altitude=altitude,
        has_gps=has_gps,
        original_point_count=original_point_count,
    )
    db.add(stream)


def is_connected(profile: AthleteProfile) -> bool:
    """Check if Strava is connected."""
    return bool(
        profile.strava_client_id
        and profile.strava_client_secret
        and profile.strava_access_token
    )


def disconnect(db: Session, profile: AthleteProfile) -> None:
    """Disconnect Strava by clearing tokens."""
    profile.strava_access_token = None
    profile.strava_refresh_token = None
    profile.strava_token_expires_at = None
    profile.strava_athlete_id = None
    profile.strava_last_sync = None
    db.commit()
