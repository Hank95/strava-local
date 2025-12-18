"""Compute derived metrics for all activities.

Usage:
    python -m scripts.compute_metrics           # Compute new metrics
    python -m scripts.compute_metrics --force   # Recompute all metrics
    python -m scripts.compute_metrics --quiet   # Suppress output
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import get_engine, get_session, init_db
from metrics.compute import run_full_computation
from metrics.profile import get_effective_values
from metrics.training_load import get_current_form


def main():
    parser = argparse.ArgumentParser(
        description="Compute derived metrics (TSS, ATL/CTL/TSB, HR zones, etc.)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute all metrics (default: only compute missing)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    parser.add_argument(
        "--db",
        type=Path,
        help="Path to database file",
    )

    args = parser.parse_args()

    # Initialize database
    engine = get_engine(args.db)
    init_db(engine)
    session = get_session(engine)

    try:
        # Run computation
        stats = run_full_computation(
            session,
            force=args.force,
            quiet=args.quiet,
        )

        if not args.quiet:
            print()
            print("=" * 50)
            print("Computation Summary")
            print("=" * 50)
            print(f"Activities processed: {stats['activities_processed']}")
            print(f"Days computed: {stats['days_computed']}")

            if stats["errors"]:
                print(f"Errors: {len(stats['errors'])}")
                for error in stats["errors"][:5]:
                    print(f"  - {error}")
                if len(stats["errors"]) > 5:
                    print(f"  ... and {len(stats['errors']) - 5} more")

            # Show current profile values
            print()
            profile = get_effective_values(session)
            print("Profile Values:")
            print(f"  Max HR: {profile['max_hr']} {'(estimated)' if not profile['has_user_max_hr'] else ''}")
            print(f"  LTHR: {profile['lthr']} {'(estimated)' if not profile['has_user_lthr'] else ''}")

            # Show current form
            print()
            form = get_current_form(session)
            if form["ctl"] is not None:
                print("Current Training Status:")
                print(f"  CTL (Fitness): {form['ctl']:.1f}")
                print(f"  ATL (Fatigue): {form['atl']:.1f}")
                print(f"  TSB (Form): {form['tsb']:.1f}")
                print(f"  Status: {form['status']}")
                print(f"  {form['description']}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
