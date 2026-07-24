"""
Pulls current ADP (average draft position) from FantasyPros and inserts it into the
adp table.

Requires FANTASYPROS_API_KEY in .env (free personal-use tier, requested via FantasyPros'
support portal -- see docs/SETUP.md).

API notes (confirmed 2026-07-24 against the real API, since the public docs page is a
JS app that couldn't be read directly):
- Endpoint: https://api.fantasypros.com/public/v2/json/nfl/{year}/consensus-rankings
- Auth: x-api-key header.
- `position` is a required parameter -- passing a specific position (e.g. "RB") returns
  that position's internal rank (RB1, RB2, ...), NOT overall ADP. `position=ALL` is what
  returns the true cross-position board -- confirmed by rank_ave values that only make
  sense as overall picks (e.g. 1.33, 3.33) once ALL was used; a single-position request
  showed the same-looking numbers but they were actually positional ranks in disguise.
- `player_id` in the response is FantasyPros' own player ID, which matches the
  `fantasypros_id` column already populated on `players` (from the nflverse ID crosswalk
  sleeper.py uses) -- so no name-matching is needed, just a direct lookup.
- `rank_ave` is used as the ADP value (a precise float), not the rounded `rank_ecr`.

Every pull is inserted as a new row (not upserted) since `adp`'s primary key includes
`pulled_at` -- this deliberately keeps a history of ADP snapshots over time, useful
later for tracking ADP movement (a Phase 5 idea), not just the latest value.

Usage:
    py scripts/ingest/fantasypros.py
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"

API_KEY = os.environ["FANTASYPROS_API_KEY"]
YEAR = 2026  # the season being drafted for -- update each year
URL = f"https://api.fantasypros.com/public/v2/json/nfl/{YEAR}/consensus-rankings"


def fetch_adp() -> list[dict]:
    resp = requests.get(
        URL,
        params={"type": "ADP", "scoring": "PPR", "position": "ALL"},
        headers={"x-api-key": API_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["players"]


def get_fantasypros_id_map(conn: sqlite3.Connection) -> dict:
    """Returns {fantasypros_id: gsis_id} for every player we already know about."""
    rows = conn.execute(
        "SELECT fantasypros_id, gsis_id FROM players WHERE fantasypros_id IS NOT NULL"
    ).fetchall()
    return {fp_id: gsis_id for fp_id, gsis_id in rows}


def build_adp_rows(players: list[dict], fp_id_map: dict, pulled_at: str) -> list[dict]:
    rows = []
    for p in players:
        fp_id = str(p["player_id"])
        gsis_id = fp_id_map.get(fp_id)
        if not gsis_id:
            # Not every FantasyPros player matches our players table -- deep bench
            # guys, or occasional crosswalk gaps. Skip rather than guess by name.
            continue
        rows.append({
            "gsis_id": gsis_id,
            "source": "fantasypros",
            "adp": float(p["rank_ave"]),
            "pulled_at": pulled_at,
        })
    return rows


def insert_adp(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        "INSERT INTO adp (gsis_id, source, adp, pulled_at) VALUES (:gsis_id, :source, :adp, :pulled_at)",
        rows,
    )


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        fp_id_map = get_fantasypros_id_map(conn)
        print(f"{len(fp_id_map)} players have a known fantasypros_id")

        players = fetch_adp()
        print(f"{len(players)} players returned from FantasyPros")

        pulled_at = datetime.now(timezone.utc).isoformat()
        rows = build_adp_rows(players, fp_id_map, pulled_at)
        print(f"{len(rows)} matched to a known player and will be inserted")

        insert_adp(conn, rows)
        conn.commit()
    finally:
        conn.close()

    print("Done.")


if __name__ == "__main__":
    main()
