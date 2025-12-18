"""CLI script for generating map visualizations of activities."""
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import folium
from folium.plugins import HeatMap, MarkerCluster
from sqlalchemy import and_

from db.models import Activity, Stream, get_engine, get_session


# Color palette for different activity types
ACTIVITY_COLORS = {
    "Run": "#FF5722",      # Deep orange
    "Ride": "#2196F3",     # Blue
    "Walk": "#4CAF50",     # Green
    "Hike": "#8BC34A",     # Light green
    "Swim": "#00BCD4",     # Cyan
    "Yoga": "#9C27B0",     # Purple
    "Golf": "#FFEB3B",     # Yellow
    "Workout": "#F44336",  # Red
    "WeightTraining": "#795548",  # Brown
    "default": "#607D8B",  # Blue grey
}


def get_activity_color(activity_type: str | None) -> str:
    """Get color for an activity type."""
    if activity_type is None:
        return ACTIVITY_COLORS["default"]
    return ACTIVITY_COLORS.get(activity_type, ACTIVITY_COLORS["default"])


def query_activities_with_gps(
    session,
    activity_type: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    limit: int | None = None,
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


def generate_heatmap(
    activities: list[tuple[Activity, Stream]],
    output_path: Path,
) -> None:
    """Generate a heatmap of all GPS points."""
    print(f"Generating heatmap from {len(activities)} activities...")

    # Collect all points
    heat_data = []
    for _, stream in activities:
        if stream.route:
            for point in stream.route:
                heat_data.append([point[0], point[1]])

    if not heat_data:
        print("No GPS data found!")
        return

    print(f"  Total points: {len(heat_data):,}")

    # Calculate center
    center = calculate_center(activities)

    # Create map
    m = folium.Map(
        location=center,
        zoom_start=11,
        tiles="cartodbpositron",
    )

    # Add heatmap layer
    HeatMap(
        heat_data,
        radius=8,
        blur=10,
        max_zoom=15,
        gradient={0.2: "blue", 0.4: "cyan", 0.6: "lime", 0.8: "yellow", 1: "red"},
    ).add_to(m)

    # Add title
    title_html = '''
    <div style="position: fixed; top: 10px; left: 50px; z-index: 9999;
                background-color: white; padding: 10px; border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);">
        <h4 style="margin: 0;">Activity Heatmap</h4>
        <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">
            {} activities | {:,} points
        </p>
    </div>
    '''.format(len(activities), len(heat_data))
    m.get_root().html.add_child(folium.Element(title_html))

    # Save
    m.save(str(output_path))
    print(f"  Saved to: {output_path}")


def generate_routes_map(
    activities: list[tuple[Activity, Stream]],
    output_path: Path,
    show_markers: bool = True,
) -> None:
    """Generate a map with all routes overlaid."""
    print(f"Generating routes map from {len(activities)} activities...")

    if not activities:
        print("No activities with GPS data found!")
        return

    # Calculate center
    center = calculate_center(activities)

    # Create map
    m = folium.Map(
        location=center,
        zoom_start=11,
        tiles="cartodbpositron",
    )

    # Group activities by type for legend
    type_counts: dict[str, int] = {}

    # Add each route
    for activity, stream in activities:
        if not stream.route or len(stream.route) < 2:
            continue

        activity_type = activity.activity_type or "Unknown"
        type_counts[activity_type] = type_counts.get(activity_type, 0) + 1

        color = get_activity_color(activity.activity_type)

        # Create popup content
        popup_html = f"""
        <b>{activity.name or 'Unnamed'}</b><br>
        Type: {activity_type}<br>
        Date: {activity.start_time.strftime('%Y-%m-%d %H:%M') if activity.start_time else 'Unknown'}<br>
        """
        if activity.distance:
            popup_html += f"Distance: {activity.distance/1000:.2f} km<br>"
        if activity.moving_time:
            mins = int(activity.moving_time // 60)
            popup_html += f"Time: {mins} min<br>"

        # Add route line
        route_coords = [[p[0], p[1]] for p in stream.route]
        folium.PolyLine(
            route_coords,
            color=color,
            weight=2,
            opacity=0.7,
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(m)

    # Add legend
    legend_items = ""
    for activity_type in sorted(type_counts.keys(), key=lambda x: type_counts[x], reverse=True)[:10]:
        color = get_activity_color(activity_type)
        count = type_counts[activity_type]
        legend_items += f'<li><span style="background:{color};width:20px;height:3px;display:inline-block;margin-right:5px;"></span>{activity_type} ({count})</li>'

    legend_html = f'''
    <div style="position: fixed; bottom: 30px; right: 30px; z-index: 9999;
                background-color: white; padding: 15px; border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3); max-height: 300px; overflow-y: auto;">
        <h4 style="margin: 0 0 10px 0;">Routes by Type</h4>
        <ul style="list-style: none; padding: 0; margin: 0; font-size: 12px;">
            {legend_items}
        </ul>
        <p style="margin: 10px 0 0 0; font-size: 11px; color: #666;">
            Total: {len(activities)} activities
        </p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    # Save
    m.save(str(output_path))
    print(f"  Saved to: {output_path}")


def generate_single_activity_map(
    activity: Activity,
    stream: Stream,
    output_path: Path,
) -> None:
    """Generate a detailed map for a single activity."""
    print(f"Generating map for activity: {activity.name or activity.activity_id}")

    if not stream.route or len(stream.route) < 2:
        print("No GPS data for this activity!")
        return

    route_coords = [[p[0], p[1]] for p in stream.route]

    # Calculate bounds
    lats = [p[0] for p in stream.route]
    lons = [p[1] for p in stream.route]
    center = (sum(lats) / len(lats), sum(lons) / len(lons))

    # Create map
    m = folium.Map(
        location=center,
        zoom_start=13,
        tiles="cartodbpositron",
    )

    # Fit bounds
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])

    color = get_activity_color(activity.activity_type)

    # Add route
    folium.PolyLine(
        route_coords,
        color=color,
        weight=4,
        opacity=0.8,
    ).add_to(m)

    # Add start marker
    folium.Marker(
        route_coords[0],
        popup="Start",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    # Add end marker
    folium.Marker(
        route_coords[-1],
        popup="Finish",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(m)

    # Add info panel
    info_html = f'''
    <div style="position: fixed; top: 10px; left: 50px; z-index: 9999;
                background-color: white; padding: 15px; border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);">
        <h4 style="margin: 0 0 10px 0;">{activity.name or 'Unnamed Activity'}</h4>
        <table style="font-size: 12px;">
            <tr><td style="color:#666;padding-right:10px;">Type:</td><td>{activity.activity_type or 'Unknown'}</td></tr>
            <tr><td style="color:#666;">Date:</td><td>{activity.start_time.strftime('%Y-%m-%d %H:%M') if activity.start_time else 'Unknown'}</td></tr>
    '''
    if activity.distance:
        info_html += f'<tr><td style="color:#666;">Distance:</td><td>{activity.distance/1000:.2f} km</td></tr>'
    if activity.moving_time:
        mins = int(activity.moving_time // 60)
        secs = int(activity.moving_time % 60)
        info_html += f'<tr><td style="color:#666;">Time:</td><td>{mins}:{secs:02d}</td></tr>'
    if activity.elevation_gain:
        info_html += f'<tr><td style="color:#666;">Elevation:</td><td>{activity.elevation_gain:.0f} m</td></tr>'
    if activity.avg_hr:
        info_html += f'<tr><td style="color:#666;">Avg HR:</td><td>{activity.avg_hr:.0f} bpm</td></tr>'

    info_html += '</table></div>'
    m.get_root().html.add_child(folium.Element(info_html))

    # Save
    m.save(str(output_path))
    print(f"  Saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate map visualizations of Strava activities."
    )

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--heatmap",
        action="store_true",
        help="Generate a heatmap of all GPS points",
    )
    mode_group.add_argument(
        "--routes",
        action="store_true",
        help="Generate a map with all routes overlaid",
    )
    mode_group.add_argument(
        "--activity",
        type=str,
        metavar="ID",
        help="Generate a map for a single activity by ID",
    )

    # Filters
    parser.add_argument(
        "--type",
        type=str,
        help="Filter by activity type (e.g., Run, Ride, Walk)",
    )
    parser.add_argument(
        "--after",
        type=str,
        help="Filter activities after date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--before",
        type=str,
        help="Filter activities before date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of activities",
    )

    # Output
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output HTML file path (default: data/map.html)",
    )

    args = parser.parse_args()

    # Parse dates
    after = None
    before = None
    if args.after:
        after = datetime.strptime(args.after, "%Y-%m-%d")
    if args.before:
        before = datetime.strptime(args.before, "%Y-%m-%d")

    # Default output path
    if args.output:
        output_path = args.output
    else:
        output_path = Path(__file__).parent.parent / "data" / "map.html"

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect to database
    engine = get_engine()
    session = get_session(engine)

    try:
        if args.activity:
            # Single activity mode
            activity = session.query(Activity).filter_by(activity_id=args.activity).first()
            if not activity:
                print(f"Activity not found: {args.activity}", file=sys.stderr)
                sys.exit(1)

            stream = session.query(Stream).filter_by(activity_id=args.activity).first()
            if not stream or not stream.has_gps:
                print(f"No GPS data for activity: {args.activity}", file=sys.stderr)
                sys.exit(1)

            generate_single_activity_map(activity, stream, output_path)

        else:
            # Query activities
            activities = query_activities_with_gps(
                session,
                activity_type=args.type,
                after=after,
                before=before,
                limit=args.limit,
            )

            if not activities:
                print("No activities with GPS data found matching filters.", file=sys.stderr)
                sys.exit(1)

            if args.heatmap:
                generate_heatmap(activities, output_path)
            elif args.routes:
                generate_routes_map(activities, output_path)

        print(f"\nOpen in browser: file://{output_path.absolute()}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
