"""
Creates (or updates) the SQLite database from schema.sql.

Safe to re-run: every statement in schema.sql uses IF NOT EXISTS, so running this
against an existing database just fills in anything missing rather than wiping data.

Usage:
    py scripts/db/init_db.py
"""

import sqlite3
from pathlib import Path

# Paths are relative to the project root, not this file's location, so this works
# regardless of which directory you run it from.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "scripts" / "db" / "schema.sql"
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    schema_sql = SCHEMA_PATH.read_text()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    print(f"Database ready at {DB_PATH}")


if __name__ == "__main__":
    init_db()
