"""
Creates (or updates) the SQLite database from schema.sql.

Safe to re-run: every statement in schema.sql uses IF NOT EXISTS, so running this
against an existing database just fills in anything missing rather than wiping data.

Note on schema changes after the table already exists: CREATE TABLE IF NOT EXISTS does
NOT retroactively add new columns to a table that's already there -- it just gets
skipped entirely since the table exists. Adding a column to an existing table needs an
explicit ALTER TABLE migration, which is what MIGRATIONS below is for. This is a real,
common data-engineering gotcha: editing a CREATE TABLE definition doesn't sync itself
into an already-running database.

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

# (table, column, sql_type) -- add a new entry here any time a column gets added to an
# existing table in schema.sql, so existing databases pick it up on the next init_db.py run.
MIGRATIONS = [
    ("weekly_stats", "target_share", "REAL"),
    ("weekly_stats", "wopr", "REAL"),
]


def run_migrations(conn: sqlite3.Connection) -> None:
    for table, column, sql_type in MIGRATIONS:
        existing_cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing_cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
            print(f"  migrated: added {table}.{column}")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    schema_sql = SCHEMA_PATH.read_text()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema_sql)
        run_migrations(conn)
        conn.commit()
    finally:
        conn.close()

    print(f"Database ready at {DB_PATH}")


if __name__ == "__main__":
    init_db()
