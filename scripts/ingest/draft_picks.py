"""
Pulls NFL draft picks and either updates existing players with their draft capital
(draft_year/draft_round/draft_pick) or inserts a new minimal player row for rookies
who aren't in `players` yet.

This exists specifically to fix the "rookies get zero score" gap: a player with no
weekly_stats rows has nothing for scoring.py to compute a recency-weighted average
from, so draft capital (round/pick) becomes the substitute signal for a baseline
score -- draft position is one of the best-established predictors of rookie fantasy
output, even before they've played a snap.

As a side effect, this also fixes some of the "unmatched" rookies from ffc.py's
name-matching -- several 2026 draft picks weren't in `players` at all yet (not just a
name-matching miss), since Sleeper's crosswalk hadn't linked them to a gsis_id. Once
they're inserted here, a later ffc.py re-run should pick them up by name.

Only skill positions relevant to standard fantasy scoring are kept (QB/RB/WR/TE/K) --
draft picks data covers every position (offensive line, defense, etc.), which we have
no use for.

Column/matching notes (confirmed 2026-07-24 against nflreadpy's actual output):
- gsis_id is present directly -- a clean ID join, no name-matching needed (unlike ffc.py).
- Team abbreviations here come from Pro Football Reference's convention, which
  disagrees with nflverse's in at least one case seen so far: "NWE" for the Patriots
  vs. "NE" elsewhere. Same normalization approach as nfl_data.py's LA/LAR fix.

Usage:
    py scripts/ingest/draft_picks.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
import nflreadpy as nfl

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"

YEARS = [2024, 2025, 2026]
FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K"}

# See module docstring -- add to this as more mismatches are found, rather than
# guessing every possible alias upfront.
TEAM_ABBR_ALIASES = {
    "NWE": "NE",
}


def fetch_draft_picks(years: list[int]):
    df = nfl.load_draft_picks(years).to_pandas()
    df = df[df["position"].isin(FANTASY_POSITIONS)]
    return df


def get_known_gsis_ids(conn: sqlite3.Connection) -> set:
    return {row[0] for row in conn.execute("SELECT gsis_id FROM players").fetchall()}


def build_rows(df, known_gsis_ids: set) -> tuple[list[dict], list[dict]]:
    """Returns (rows_to_update, rows_to_insert) -- existing players get just their
    draft capital updated; new rookies get a minimal full row so they exist at all."""
    to_update, to_insert = [], []

    for r in df.itertuples(index=False):
        if pd.isna(r.gsis_id) or not r.gsis_id:
            # a handful of picks (mostly very old/obscure) lack a gsis_id -- checking
            # pd.isna() specifically matters here because NaN is truthy in Python, so a
            # plain `if not r.gsis_id` silently lets NaN through instead of skipping it
            # (the same NaN-is-truthy trap already caught once this session, in
            # nfl_data.py's fumbles_lost handling -- missed it here the first time).
            continue
        team = TEAM_ABBR_ALIASES.get(r.team, r.team)
        row = {
            "gsis_id": r.gsis_id,
            "draft_year": r.season,
            "draft_round": r.round,
            "draft_pick": r.pick,
        }
        if r.gsis_id in known_gsis_ids:
            to_update.append(row)
        else:
            row.update({
                "full_name": r.pfr_player_name,
                "position": r.position,
                "current_team": team,
            })
            to_insert.append(row)

    return to_update, to_insert


def upsert_teams(conn: sqlite3.Connection, rows_to_insert: list[dict]) -> None:
    team_abbrs = {row["current_team"] for row in rows_to_insert if row["current_team"]}
    conn.executemany(
        "INSERT OR IGNORE INTO teams (team_abbr, team_name) VALUES (?, ?)",
        [(abbr, abbr) for abbr in team_abbrs],
    )


def update_existing_players(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        """
        UPDATE players
        SET draft_year = :draft_year, draft_round = :draft_round, draft_pick = :draft_pick
        WHERE gsis_id = :gsis_id
        """,
        rows,
    )


def insert_new_players(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        """
        INSERT INTO players (gsis_id, full_name, position, current_team, draft_year, draft_round, draft_pick)
        VALUES (:gsis_id, :full_name, :position, :current_team, :draft_year, :draft_round, :draft_pick)
        ON CONFLICT(gsis_id) DO UPDATE SET
            draft_year=excluded.draft_year,
            draft_round=excluded.draft_round,
            draft_pick=excluded.draft_pick
        """,
        rows,
    )


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        known_gsis_ids = get_known_gsis_ids(conn)
        print(f"{len(known_gsis_ids)} known players in the database")

        df = fetch_draft_picks(YEARS)
        print(f"{len(df)} skill-position draft picks fetched for {YEARS}")

        to_update, to_insert = build_rows(df, known_gsis_ids)
        print(f"  {len(to_update)} existing players to update with draft capital")
        print(f"  {len(to_insert)} new rookies to insert")

        upsert_teams(conn, to_insert)
        update_existing_players(conn, to_update)
        insert_new_players(conn, to_insert)
        conn.commit()
    finally:
        conn.close()

    print("Done.")


if __name__ == "__main__":
    main()
