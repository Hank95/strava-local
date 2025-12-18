"""Run the Strava Local web application."""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn


def main():
    """Start the web server."""
    print("Starting Strava Local web server...")
    print("Open http://127.0.0.1:8000 in your browser")
    print("Press Ctrl+C to stop\n")

    uvicorn.run(
        "web.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
