#!/usr/bin/env python3
"""Add Strava API columns to athlete_profile table.

Run this script once to migrate existing databases.
Safe to run multiple times - it checks if columns exist first.
"""

import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "strava_local.db"


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate():
    """Add Strava columns to athlete_profile table."""
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("Run 'python -m scripts.ingest' first to create the database.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # New columns to add
    new_columns = [
        ("strava_client_id", "TEXT"),
        ("strava_client_secret", "TEXT"),
        ("strava_access_token", "TEXT"),
        ("strava_refresh_token", "TEXT"),
        ("strava_token_expires_at", "INTEGER"),
        ("strava_athlete_id", "INTEGER"),
        ("strava_last_sync", "DATETIME"),
    ]

    added = 0
    for col_name, col_type in new_columns:
        if not column_exists(cursor, "athlete_profile", col_name):
            print(f"Adding column: {col_name}")
            cursor.execute(f"ALTER TABLE athlete_profile ADD COLUMN {col_name} {col_type}")
            added += 1
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()

    if added > 0:
        print(f"\nMigration complete! Added {added} new column(s).")
    else:
        print("\nNo migration needed - all columns already exist.")


if __name__ == "__main__":
    migrate()
