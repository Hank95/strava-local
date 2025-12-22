"""Map generation service for web views."""
from datetime import datetime
from typing import Optional

import folium
from folium.plugins import HeatMap
from sqlalchemy.orm import Session

from db.models import Activity, Stream


# Color palette for different activity types (from scripts/map.py)
ACTIVITY_COLORS = {
    "Run": "#FF5722",
    "Ride": "#2196F3",
    "Walk": "#4CAF50",
    "Hike": "#8BC34A",
    "Swim": "#00BCD4",
    "Yoga": "#9C27B0",
    "Golf": "#FFEB3B",
    "Workout": "#F44336",
    "WeightTraining": "#795548",
    "default": "#607D8B",
}


def get_activity_color(activity_type: str | None) -> str:
    """Get color for an activity type."""
    if activity_type is None:
        return ACTIVITY_COLORS["default"]
    return ACTIVITY_COLORS.get(activity_type, ACTIVITY_COLORS["default"])


def query_activities_with_gps(
    session: Session,
    activity_type: Optional[str] = None,
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    limit: Optional[int] = None,
) -> list[tuple[Activity, Stream]]:
    """Query activities that have GPS data."""
    query = (
        session.query(Activity, Stream)
        .join(Stream, Activity.activity_id == Stream.activity_id)
        .filter(Stream.has_gps == True)
    )

    if activity_type:
        query = query.filter(Activity.activity_type == activity_type)

    if after:
        query = query.filter(Activity.start_time >= after)

    if before:
        query = query.filter(Activity.start_time <= before)

    query = query.order_by(Activity.start_time.desc())

    if limit:
        query = query.limit(limit)

    return query.all()


def calculate_center(activities: list[tuple[Activity, Stream]]) -> tuple[float, float]:
    """Calculate the center point of all activities."""
    all_lats = []
    all_lons = []

    for _, stream in activities:
        if stream.route:
            for point in stream.route:
                all_lats.append(point[0])
                all_lons.append(point[1])

    if not all_lats:
        return (37.7749, -122.4194)  # Default to SF

    return (sum(all_lats) / len(all_lats), sum(all_lons) / len(all_lons))


def generate_heatmap_html(
    session: Session,
    activity_type: Optional[str] = None,
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    limit: Optional[int] = 200,  # Default limit to prevent overload
    user_lat: Optional[float] = None,
    user_lon: Optional[float] = None,
) -> str:
    """Generate heatmap and return HTML string."""
    # Cap the limit to prevent browser crashes
    if limit is None or limit > 500:
        limit = 200

    activities = query_activities_with_gps(
        session,
        activity_type=activity_type,
        after=after,
        before=before,
        limit=limit,
    )

    if not activities:
        # Still show map centered on user location if available
        center = (user_lat, user_lon) if user_lat and user_lon else (37.7749, -122.4194)
        m = folium.Map(location=center, zoom_start=11, tiles="cartodbpositron")
        info_html = '''
        <div style="position: fixed; top: 16px; right: 16px;
                    z-index: 9999; background-color: rgba(255,255,255,0.95); padding: 16px 20px; border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.15); backdrop-filter: blur(10px);">
            <p style="margin: 0; color: #666; font-size: 13px;">No activities with GPS data found.</p>
            <p style="margin: 4px 0 0 0; color: #999; font-size: 12px;">Try adjusting your filters.</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(info_html))
        return m._repr_html_()

    # Collect all points
    heat_data = []
    for _, stream in activities:
        if stream.route:
            for point in stream.route:
                heat_data.append([point[0], point[1]])

    if not heat_data:
        return "<p style='padding: 20px;'>No GPS points found.</p>"

    # Use user location if provided, otherwise calculate from activities
    if user_lat and user_lon:
        center = (user_lat, user_lon)
    else:
        center = calculate_center(activities)

    m = folium.Map(
        location=center,
        zoom_start=12,
        tiles="cartodbpositron",
    )

    HeatMap(
        heat_data,
        radius=8,
        blur=10,
        max_zoom=15,
        gradient={0.2: "blue", 0.4: "cyan", 0.6: "lime", 0.8: "yellow", 1: "red"},
    ).add_to(m)

    # Add info panel (positioned top-right to avoid corner clipping)
    limited_text = f"(showing {limit} most recent)" if len(activities) >= limit else ""
    info_html = f'''
    <div style="position: fixed; top: 16px; right: 16px; z-index: 9999;
                background-color: rgba(255,255,255,0.95); padding: 12px 16px; border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.15); backdrop-filter: blur(10px);">
        <div style="font-size: 13px; font-weight: 600; color: #333;">Heatmap</div>
        <div style="font-size: 12px; color: #666; margin-top: 2px;">
            {len(activities)} activities &middot; {len(heat_data):,} points
        </div>
        {f'<div style="font-size: 11px; color: #999; margin-top: 4px;">{limited_text}</div>' if limited_text else ''}
    </div>
    '''
    m.get_root().html.add_child(folium.Element(info_html))

    return m._repr_html_()


def generate_routes_html(
    session: Session,
    activity_type: Optional[str] = None,
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    limit: Optional[int] = 200,
    user_lat: Optional[float] = None,
    user_lon: Optional[float] = None,
) -> str:
    """Generate routes map and return HTML string."""
    # Cap the limit to prevent browser crashes
    if limit is None or limit > 500:
        limit = 200

    activities = query_activities_with_gps(
        session,
        activity_type=activity_type,
        after=after,
        before=before,
        limit=limit,
    )

    if not activities:
        # Still show map centered on user location if available
        center = (user_lat, user_lon) if user_lat and user_lon else (37.7749, -122.4194)
        m = folium.Map(location=center, zoom_start=11, tiles="cartodbpositron")
        info_html = '''
        <div style="position: fixed; top: 16px; right: 16px;
                    z-index: 9999; background-color: rgba(255,255,255,0.95); padding: 16px 20px; border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.15); backdrop-filter: blur(10px);">
            <p style="margin: 0; color: #666; font-size: 13px;">No activities with GPS data found.</p>
            <p style="margin: 4px 0 0 0; color: #999; font-size: 12px;">Try adjusting your filters.</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(info_html))
        return m._repr_html_()

    # Use user location if provided, otherwise calculate from activities
    if user_lat and user_lon:
        center = (user_lat, user_lon)
    else:
        center = calculate_center(activities)

    m = folium.Map(
        location=center,
        zoom_start=12,
        tiles="cartodbpositron",
    )

    type_counts: dict[str, int] = {}

    for activity, stream in activities:
        if not stream.route or len(stream.route) < 2:
            continue

        activity_type_name = activity.activity_type or "Unknown"
        type_counts[activity_type_name] = type_counts.get(activity_type_name, 0) + 1

        color = get_activity_color(activity.activity_type)

        popup_html = f"""
        <b>{activity.name or 'Unnamed'}</b><br>
        Type: {activity_type_name}<br>
        Date: {activity.start_time.strftime('%Y-%m-%d') if activity.start_time else 'Unknown'}<br>
        """
        if activity.distance:
            popup_html += f"Distance: {activity.distance/1000:.2f} km<br>"

        route_coords = [[p[0], p[1]] for p in stream.route]
        folium.PolyLine(
            route_coords,
            color=color,
            weight=2,
            opacity=0.7,
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(m)

    # Add legend (positioned bottom-left to not overlap controls)
    legend_items = ""
    for at in sorted(type_counts.keys(), key=lambda x: type_counts[x], reverse=True)[:8]:
        color = get_activity_color(at)
        count = type_counts[at]
        legend_items += f'''<div style="display: flex; align-items: center; margin-bottom: 6px;">
            <span style="background:{color};width:16px;height:3px;border-radius:2px;margin-right:8px;"></span>
            <span style="flex:1;">{at}</span>
            <span style="color:#999;margin-left:8px;">{count}</span>
        </div>'''

    limited_text = f"(showing {limit} most recent)" if len(activities) >= limit else ""
    legend_html = f'''
    <div style="position: fixed; top: 16px; right: 16px; z-index: 9999;
                background-color: rgba(255,255,255,0.95); padding: 14px 16px; border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.15); backdrop-filter: blur(10px); min-width: 160px;
                max-height: calc(100vh - 250px); overflow-y: auto;">
        <div style="font-size: 13px; font-weight: 600; color: #333; margin-bottom: 10px;">
            {len(activities)} Routes
        </div>
        <div style="font-size: 12px; color: #444;">
            {legend_items}
        </div>
        {f'<div style="font-size: 11px; color: #999; margin-top: 8px;">{limited_text}</div>' if limited_text else ''}
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    return m._repr_html_()


def generate_activity_map_html(
    session: Session,
    activity_id: str,
) -> str | None:
    """Generate single activity map and return HTML string."""
    activity = session.query(Activity).filter_by(activity_id=activity_id).first()
    stream = session.query(Stream).filter_by(activity_id=activity_id).first()

    if not activity or not stream or not stream.route or len(stream.route) < 2:
        return None

    route_coords = [[p[0], p[1]] for p in stream.route]

    lats = [p[0] for p in stream.route]
    lons = [p[1] for p in stream.route]
    center = (sum(lats) / len(lats), sum(lons) / len(lons))

    # Create map centered on route - don't call fitBounds here, let JS handle it
    m = folium.Map(
        location=center,
        zoom_start=14,
        tiles="cartodbpositron",
    )

    color = get_activity_color(activity.activity_type)

    folium.PolyLine(
        route_coords,
        color=color,
        weight=4,
        opacity=0.8,
    ).add_to(m)

    # Start marker
    folium.Marker(
        route_coords[0],
        popup="Start",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    # End marker
    folium.Marker(
        route_coords[-1],
        popup="Finish",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(m)

    # Store bounds for JavaScript
    south, west = min(lats), min(lons)
    north, east = max(lats), max(lons)

    # Get HTML
    html = m._repr_html_()

    # Inject script AFTER the map is created (at end of body)
    fit_script = f"""
    <script>
        (function() {{
            var bounds = [[{south}, {west}], [{north}, {east}]];

            // Find map - folium creates a variable like map_xxxxx
            var map = null;
            for (var key in window) {{
                if (key.indexOf('map_') === 0 && window[key]._leaflet_id) {{
                    map = window[key];
                    break;
                }}
            }}

            if (map) {{
                console.log('Found map, fitting bounds');
                map.fitBounds(bounds, {{padding: [30, 30]}});
            }} else {{
                console.log('Map not found');
            }}
        }})();
    </script>
    """
    html = html.replace("</body>", fit_script + "</body>")

    return html
