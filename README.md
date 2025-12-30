# Strava Local

A local ingestion and analysis tool for Strava activity data. Ingest your Strava export (CSV + FIT files) into a local SQLite database for analysis and visualization.

**All data stays local** - your activity data, GPS tracks, and training metrics are never uploaded anywhere.

## Features

- **Dashboard**: Summary statistics, activity breakdown charts, recent activities
- **Activity Browser**: Searchable, filterable table with detailed activity pages
- **Maps**: Interactive heatmap and route explorer with filters
- **Training Metrics**: TSS, CTL/ATL/TSB (fitness/fatigue/form), HR zones, TRIMP
- **Analysis**: Personal records, heart rate statistics
- **Pace & Speed**: Displays pace (min/mile) for runs, speed (mph) for other activities

## Screenshots

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="Dashboard" width="800">
  <br>
  <em>Dashboard with activity stats, breakdown charts, and recent activities</em>
</p>

<p align="center">
  <img src="docs/screenshots/heatmap.png" alt="Heatmap" width="800">
  <br>
  <em>Interactive heatmap of all your activities</em>
</p>

<p align="center">
  <img src="docs/screenshots/fitness.png" alt="Fitness Tracking" width="800">
  <br>
  <em>CTL/ATL/TSB fitness and fatigue tracking over time</em>
</p>

<p align="center">
  <img src="docs/screenshots/activity.png" alt="Activity Detail" width="800">
  <br>
  <em>Detailed activity view with route map and metrics</em>
</p>

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/strava-local.git
cd strava-local

# Run the interactive setup
python3 setup.py
```

The setup script will:
1. Check your Python version (3.10+ required)
2. Create a virtual environment
3. Install dependencies
4. Initialize the database
5. Optionally configure your athlete profile (max HR, LTHR, etc.)

## Getting Your Strava Data

1. Go to [Strava Settings](https://www.strava.com/settings/profile)
2. Click "My Account" in the sidebar
3. Click "Get Started" under "Download or Delete Your Account"
4. Click "Request Your Archive"
5. Wait for email (can take a few hours)
6. Download and extract the ZIP file
7. Copy these to the project root:
   - `activities/` - folder containing your .fit.gz files
   - `activities.csv` - file with activity metadata

## Usage

### Import Your Data

```bash
# Activate virtual environment (if not already)
source .venv/bin/activate

# Import activities from CSV and FIT files
python -m scripts.ingest
```

The ingestion is idempotent - re-running will update existing records rather than creating duplicates.

### Compute Training Metrics

```bash
python -m scripts.compute_metrics
```

This calculates:
- **TSS** (Training Stress Score) - workout intensity
- **TRIMP** (Training Impulse) - HR-based training load
- **HR Zones** - time spent in each heart rate zone
- **CTL/ATL/TSB** - fitness, fatigue, and form over time

### Start the Web Dashboard

```bash
uvicorn web.app:app --reload
```

Then open http://localhost:8000 in your browser.

> **Note**: The `--reload` flag enables auto-restart on file changes (useful for development). Omit it for production use.

## Athlete Settings

For accurate training metrics, configure your athlete profile at `/settings` or during setup:

- **Max Heart Rate**: Your maximum heart rate (bpm)
- **Resting Heart Rate**: Your resting heart rate (bpm)
- **LTHR**: Lactate threshold heart rate (bpm)
- **FTP**: Functional threshold power (watts) - for cycling
- **Weight**: Body weight (kg) - for power-to-weight calculations

If not set, the system will estimate values based on your data.

## Project Structure

```
strava-local/
├── activities/          # Your Strava FIT/GPX files (from export)
├── activities.csv       # Your Strava activities CSV (from export)
├── data/                # SQLite database location
│   └── strava_local.db
├── db/                  # Database models and schema
├── ingest/              # CSV and FIT file parsing
├── metrics/             # Training metrics computation
├── scripts/             # CLI entry points
├── web/                 # Web application
│   ├── routes/          # API and page routes
│   ├── services/        # Business logic
│   ├── templates/       # Jinja2 HTML templates
│   └── static/          # CSS and JS files
├── setup.py             # Interactive setup script
├── requirements.txt
└── README.md
```

## CLI Commands

### View Statistics

```bash
python -m scripts.stats
```

### View Latest Activity

```bash
python -m scripts.latest
```

### Generate Maps

```bash
# Heatmap of all GPS points
python -m scripts.map --heatmap

# All routes overlaid
python -m scripts.map --routes

# Single activity
python -m scripts.map --activity <ACTIVITY_ID>

# Filter by type or date
python -m scripts.map --routes --type Run
python -m scripts.map --heatmap --after 2024-01-01 --before 2024-12-31
```

## Advanced Usage

### Custom Ingestion Options

```bash
python -m scripts.ingest --csv activities.csv --fit-dir activities/ --db data/custom.db
```

Options:
- `--csv PATH`: Path to activities CSV file
- `--fit-dir PATH`: Path to directory containing FIT files
- `--db PATH`: Custom database path
- `--quiet`: Suppress progress output

### Querying the Database

```python
from db.models import get_session, Activity, Stream

session = get_session()

# Find all runs with GPS
runs_with_gps = (
    session.query(Activity)
    .join(Stream)
    .filter(Activity.activity_type == "Run")
    .filter(Stream.has_gps == True)
    .all()
)
```

Or with SQLite CLI:

```bash
sqlite3 data/strava_local.db "SELECT activity_type, COUNT(*), SUM(distance)/1609 as miles FROM activities GROUP BY activity_type"
```

## Database Schema

### activities
Activity metadata from CSV: `activity_id`, `name`, `activity_type`, `start_time`, `distance`, `moving_time`, `avg_speed`, `avg_hr`, `elevation_gain`, `calories`, etc.

### fit_files
FIT file metadata: `activity_id`, `fit_path`, `file_size`, `sha256`, `fit_sport`

### streams
Time-series data from FIT files: `route` (GPS), `heart_rate`, `altitude`, `has_gps`

### activity_metrics
Computed training metrics: `tss`, `trimp`, `intensity_factor`, `hr_z1_time` through `hr_z5_time`

### athlete_profile
User settings: `max_hr`, `resting_hr`, `lthr`, `ftp`, `weight_kg`

### rolling_averages
Daily CTL/ATL/TSB values for fitness tracking

## Requirements

- Python 3.10+
- macOS/Linux/Windows

## Notes

- FIT files are matched to CSV activities by activity ID or start time
- GPS routes are downsampled to max 500 points to reduce storage
- All units displayed in imperial (miles, feet, mph, min/mile)
