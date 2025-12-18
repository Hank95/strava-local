"""CLI script for running ingestion."""
import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingest.ingest import run_ingestion


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Strava activities from CSV and FIT files into a local SQLite database."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Path to the activities CSV file",
    )
    parser.add_argument(
        "--fit-dir",
        type=Path,
        required=True,
        help="Path to the directory containing FIT files",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to the SQLite database file (default: data/strava_local.db)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.csv.exists():
        print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    if not args.fit_dir.exists():
        print(f"Error: FIT directory not found: {args.fit_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.fit_dir.is_dir():
        print(f"Error: FIT path is not a directory: {args.fit_dir}", file=sys.stderr)
        sys.exit(1)

    # Run ingestion
    try:
        stats = run_ingestion(
            csv_path=args.csv,
            fit_dir=args.fit_dir,
            db_path=args.db,
            verbose=not args.quiet,
        )

        if stats.errors:
            print(f"\nWarnings/Errors ({len(stats.errors)}):")
            for error in stats.errors[:10]:
                print(f"  - {error}")
            if len(stats.errors) > 10:
                print(f"  ... and {len(stats.errors) - 10} more")

        sys.exit(0)

    except Exception as e:
        print(f"Error during ingestion: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
