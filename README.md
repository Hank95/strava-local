# Strava Local

A local ingestion and analysis tool for Strava activity data. Ingest your Strava export (CSV + FIT files) into a local SQLite database for analysis and visualization.

**All data stays local** - your activity data, GPS tracks, and generated maps are never uploaded anywhere.

## Getting Your Strava Data

1. Go to [Strava Settings](https://www.strava.com/settings/profile)
2. Click "My Account" in the sidebar
3. Click "Get Started" under "Download or Delete Your Account"
4. Click "Request Your Archive"
5. Wait for email (can take a few hours)
6. Download and extract the ZIP file
7. You'll have `activities.csv` and an `activities/` folder with FIT and GPX files

## Requirements

- Python 3.11+
- macOS/Linux

## Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Project Structure

```
strava-local/
├── activities/          # Your Strava FIT/GPX files (from export)
├── activities.csv       # Your Strava activities CSV (from export)
├── data/                # SQLite database location
│   └── strava_local.db
├── db/                  # Database models and schema
│   └── models.py
├── ingest/              # Ingestion logic
│   ├── csv_loader.py    # CSV parsing
│   ├── fit_parser.py    # FIT file parsing
│   ├── gpx_parser.py    # GPX file parsing
│   └── ingest.py        # Main ingestion orchestration
├── scripts/             # CLI entry points
│   ├── ingest.py        # Run ingestion
│   ├── stats.py         # View statistics
│   ├── latest.py        # View latest activity
│   ├── map.py           # Generate map visualizations
│   └── serve.py         # Start web server
├── web/                 # Web application
│   ├── app.py           # FastAPI application
│   ├── routes/          # Route handlers
│   ├── services/        # Business logic
│   ├── templates/       # Jinja2 HTML templates
│   └── static/          # CSS and JS files
├── requirements.txt
└── README.md
```

## Usage

### Ingest Data

Run the ingestion to load your CSV and FIT files into the database:

```bash
python -m scripts.ingest --csv activities.csv --fit-dir activities/
```

Options:
- `--csv PATH`: Path to activities CSV file (required)
- `--fit-dir PATH`: Path to directory containing FIT files (required)
- `--db PATH`: Custom database path (default: `data/strava_local.db`)
- `--quiet`: Suppress progress output

The ingestion is idempotent - re-running will update existing records rather than creating duplicates.

### View Statistics

```bash
python -m scripts.stats
```

Shows:
- Total number of activities
- Number of activities with GPS tracks
- Date range
- Top 5 activity types

### View Latest Activity

```bash
python -m scripts.latest
```

Shows details about the most recent activity including:
- Name, type, date
- Distance, time, speed
- Heart rate, elevation, calories
- Whether FIT file and GPS data are available

### Generate Maps

Create interactive HTML maps of your activities:

```bash
# Generate a heatmap of all GPS points
python -m scripts.map --heatmap

# Generate a map with all routes overlaid
python -m scripts.map --routes

# Generate a map for a single activity
python -m scripts.map --activity <ACTIVITY_ID>

# Filter by activity type
python -m scripts.map --routes --type Run

# Filter by date range
python -m scripts.map --heatmap --after 2024-01-01 --before 2024-12-31

# Limit number of activities (most recent first)
python -m scripts.map --routes --limit 50

# Custom output path
python -m scripts.map --heatmap -o my_heatmap.html
```

Maps are saved to `data/map.html` by default. Open the HTML file in a browser to view.

**Map Modes:**
- `--heatmap`: Shows density of GPS points across all activities
- `--routes`: Shows all routes overlaid, colored by activity type
- `--activity ID`: Shows a single activity with start/end markers

### Web Interface

Start the web server to explore your data in a browser:

```bash
python -m scripts.serve
```

Then open http://127.0.0.1:8000 in your browser.

**Features:**
- **Dashboard**: Summary statistics, activity charts, recent activities
- **Activity Browser**: Searchable, filterable table of all activities with detail pages
- **Maps**: Interactive heatmap and routes explorer with filters
- **Analysis**: Personal records, heart rate statistics

The web interface provides the same functionality as the CLI tools but with an interactive UI.

## Database Schema

### activities
Main table storing activity metadata from the CSV:
- `activity_id` (PK): Strava activity ID
- `name`, `activity_type`, `start_time`
- `distance`, `moving_time`, `elapsed_time`
- `avg_speed`, `max_speed`
- `avg_hr`, `max_hr`
- `elevation_gain`, `elevation_loss`, `elevation_low`, `elevation_high`
- `avg_watts`, `max_watts`, `avg_cadence`, `max_cadence`
- `calories`, `athlete_weight`
- `csv_extra` (JSON): Any additional CSV columns

### fit_files
FIT file metadata:
- `activity_id` (FK): Links to activities table
- `fit_path`, `file_size`, `sha256`
- `fit_start_time`, `fit_sport`, `fit_distance`
- `ingested_at`

### streams
Time-series data extracted from FIT files:
- `activity_id` (FK): Links to activities table
- `route` (JSON): Downsampled `[[lat, lon], ...]` array
- `heart_rate` (JSON): Downsampled HR array
- `altitude` (JSON): Downsampled altitude array
- `has_gps`: Boolean flag for quick filtering
- `original_point_count`: Points before downsampling

## Querying the Database

You can query the database directly with Python or any SQLite client:

```python
from db import get_session, Activity, Stream

session = get_session()

# Find all runs with GPS
runs_with_gps = (
    session.query(Activity)
    .join(Stream)
    .filter(Activity.activity_type == "Run")
    .filter(Stream.has_gps == True)
    .all()
)

# Get total distance by activity type
from sqlalchemy import func
stats = (
    session.query(
        Activity.activity_type,
        func.count(Activity.activity_id),
        func.sum(Activity.distance) / 1000  # km
    )
    .group_by(Activity.activity_type)
    .all()
)
```

Or with the SQLite CLI:

```bash
sqlite3 data/strava_local.db "SELECT activity_type, COUNT(*), SUM(distance)/1000 FROM activities GROUP BY activity_type"
```

## Notes

- FIT and GPX files are matched to CSV activities by activity ID (from filename) or by start time (within 10 minutes)
- FIT files are preferred over GPX when both exist for the same activity
- GPS routes are downsampled to max 500 points to reduce storage
