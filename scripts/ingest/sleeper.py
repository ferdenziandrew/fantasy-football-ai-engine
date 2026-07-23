"""
Pulls current player + team data and upserts it into the players/teams tables.

Two sources, joined together:
- Sleeper API (https://api.sleeper.app/v1/players/nfl): free, no auth, but keyed by
  Sleeper's own player_id -- not the gsis_id our players table uses as primary key.
- nflverse's player ID crosswalk (nfl_data_py.import_ids()): maps sleeper_id to gsis_id
  (plus fantasypros_id, espn_id), so we can resolve Sleeper's data onto our schema
  without ever matching players by name.

Known simplification: team defenses (DEF) are skipped here. Sleeper represents a
defense's "player_id" as the team abbreviation itself (e.g. "SEA"), and defenses don't
have an individual gsis_id in the crosswalk -- they also don't fit weekly_stats at all
(D/ST scoring is sacks/turnovers/points-allowed, not completions/carries/targets). That's
a separate data model to design later, not a missing lookup to patch around here.

Usage:
    py scripts/ingest/sleeper.py
"""

import sqlite3
from pathlib import Path

import requests
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"

SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"
# The same crosswalk nfl_data_py.import_ids() pulls, fetched directly (see fetch_id_crosswalk).
CROSSWALK_URL = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K"}  # DEF excluded -- see module docstring


def fetch_id_crosswalk() -> dict:
    """Returns {sleeper_id: {gsis_id, fantasypros_id, espn_id}} for every player nflverse tracks.

    Pulls DynastyProcess's player ID crosswalk CSV directly rather than going through
    nfl_data_py.import_ids() -- that function indexes a DataFrame with a Python `set`,
    which modern pandas rejects (TypeError). nfl_data_py itself is deprecated/unmaintained
    (the project points users to a successor, nflreadpy), so there's no upstream fix
    coming. The underlying data is just a public CSV either way -- this skips the broken
    wrapper and reads it straight.
    """
    df = pd.read_csv(
        CROSSWALK_URL,
        usecols=["sleeper_id", "gsis_id", "fantasypros_id", "espn_id"],
    )
    df = df.dropna(subset=["sleeper_id", "gsis_id"])  # need both, or this row is useless to us

    crosswalk = {}
    for row in df.itertuples(index=False):
        # sleeper_id comes through as a float (e.g. 4046.0) in this crosswalk -- normalize
        # to a plain string so it matches the string keys Sleeper's own API uses.
        sleeper_id = str(int(row.sleeper_id))
        crosswalk[sleeper_id] = {
            "gsis_id": row.gsis_id,
            "fantasypros_id": row.fantasypros_id,
            "espn_id": row.espn_id,
        }
    return crosswalk


def fetch_sleeper_players() -> dict:
    """Returns Sleeper's full player dict: {sleeper_id: {...player info...}}."""
    resp = requests.get(SLEEPER_PLAYERS_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def build_player_rows(sleeper_players: dict, crosswalk: dict) -> list[dict]:
    """Joins Sleeper's player info onto the ID crosswalk, filtered to fantasy-relevant positions."""
    rows = []
    for sleeper_id, p in sleeper_players.items():
        position = p.get("position")
        if position not in FANTASY_POSITIONS:
            continue

        ids = crosswalk.get(sleeper_id)
        if not ids or not ids["gsis_id"]:
            # No gsis_id means nflverse's historical stats can't be joined to this player --
            # typically very recent rookies not yet in the crosswalk. Skip for now; if this
            # turns out to drop real players we care about, revisit.
            continue

        full_name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()

        rows.append({
            "gsis_id": ids["gsis_id"],
            "sleeper_id": sleeper_id,
            "fantasypros_id": ids["fantasypros_id"],
            "espn_id": ids["espn_id"],
            "full_name": full_name,
            "position": position,
            "current_team": p.get("team"),
            "status": p.get("status"),
            "age": p.get("age"),
            "height": p.get("height"),
            "weight": p.get("weight"),
            "college": p.get("college"),
            "years_exp": p.get("years_exp"),
        })
    return rows


def upsert_teams(conn: sqlite3.Connection, player_rows: list[dict]) -> None:
    team_abbrs = {row["current_team"] for row in player_rows if row["current_team"]}
    conn.executemany(
        "INSERT OR IGNORE INTO teams (team_abbr, team_name) VALUES (?, ?)",
        # team_name is just the abbreviation for now -- enriched later once we pull
        # nfl_data_py.import_team_desc() for full team names/colors/etc.
        [(abbr, abbr) for abbr in team_abbrs],
    )


def upsert_players(conn: sqlite3.Connection, player_rows: list[dict]) -> None:
    conn.executemany(
        """
        INSERT INTO players (
            gsis_id, sleeper_id, fantasypros_id, espn_id, full_name,
            position, current_team, status, age, height, weight, college, years_exp
        ) VALUES (
            :gsis_id, :sleeper_id, :fantasypros_id, :espn_id, :full_name,
            :position, :current_team, :status, :age, :height, :weight, :college, :years_exp
        )
        ON CONFLICT(gsis_id) DO UPDATE SET
            sleeper_id=excluded.sleeper_id,
            fantasypros_id=excluded.fantasypros_id,
            espn_id=excluded.espn_id,
            full_name=excluded.full_name,
            position=excluded.position,
            current_team=excluded.current_team,
            status=excluded.status,
            age=excluded.age,
            height=excluded.height,
            weight=excluded.weight,
            college=excluded.college,
            years_exp=excluded.years_exp
        """,
        player_rows,
    )


def main() -> None:
    print("Fetching nflverse ID crosswalk...")
    crosswalk = fetch_id_crosswalk()
    print(f"  {len(crosswalk)} players in crosswalk")

    print("Fetching Sleeper player list...")
    sleeper_players = fetch_sleeper_players()
    print(f"  {len(sleeper_players)} total entries from Sleeper")

    player_rows = build_player_rows(sleeper_players, crosswalk)
    print(f"  {len(player_rows)} fantasy-relevant players matched to a gsis_id")

    conn = sqlite3.connect(DB_PATH)
    try:
        upsert_teams(conn, player_rows)
        upsert_players(conn, player_rows)
        conn.commit()
    finally:
        conn.close()

    print("Done.")


if __name__ == "__main__":
    main()
