"""
Pulls historical weekly stats (regular season only) and inserts them into weekly_stats.

Only players already present in our `players` table (built by sleeper.py) are kept.
weekly_stats has a foreign key on gsis_id, so a row can't be inserted for a player who
isn't there first. nflverse's weekly data covers every player in the league (linemen,
kickers, defensive players, etc.) -- far broader than the ~2,700 fantasy-relevant
players sleeper.py loaded -- so filtering down to known gsis_ids is what narrows it
back to players we actually care about.

Uses nflreadpy, not nfl_data_py. nfl_data_py is deprecated/unmaintained, and its
hardcoded data URLs point at an old nflverse release path that stopped getting the
newest season -- 2020-2024 still resolved through it, but 2025 (the most important
year) 404'd. nflreadpy is the actively maintained successor and correctly resolves
current data. It returns Polars DataFrames, converted to pandas here immediately so
the rest of this script (and every other script in this project) can stay pandas-only.

Column mapping notes (confirmed 2026-07-24 against nflreadpy's actual output --
don't trust this blindly if nflverse restructures data again, re-check with a quick
`print(sorted(df.columns))` first, the way we caught this rename):
- Renamed vs. the old nfl_data_py columns: `interceptions` -> `passing_interceptions`,
  `recent_team` -> `team`.
- fumbles_lost is now a single ready-made column, `fumbles_lost_total` -- no more
  summing sack/rushing/receiving fumbles ourselves.
- fantasy_points_ppr comes directly from nflverse for non-kickers. fantasy_points_half_ppr
  doesn't -- computed here as fantasy_points (standard scoring) + 0.5 * receptions.
- Numeric stat columns get fillna(0) right after fetching -- NaN is truthy in Python,
  so a plain `x or 0` guard would silently let NaNs through and corrupt any sum built
  from them instead of treating a missing stat as zero.

Kicker scoring (confirmed 2026-07-24, a real gap, not a guess): nflverse's
fantasy_points/fantasy_points_ppr do NOT include kicking stats at all -- every kicker
scored exactly 0.0 in scoring.py until this was added. fg_made/pat_made etc. are present
in the same load_player_stats() data, just never folded into the points total upstream.
Computed here instead, using Andrew's actual league scoring (confirmed 2026-07-25, not
a generic default): 3/4/5 pts for FG makes under 40, 40-49, and 50+ yards; 1 pt per PAT
made; -1 for a missed FG; a missed PAT is 0, not -1 (differs from some common defaults --
this is deliberate, matches Andrew's real leagues, not an oversight). Since PPR doesn't
apply to kickers, fantasy_points_ppr and fantasy_points_half_ppr are identical for K rows.

Usage:
    py scripts/ingest/nfl_data.py
"""

import sqlite3
from pathlib import Path

import nflreadpy as nfl

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"
YEARS = list(range(2020, 2026))  # 2020-2025

# nflverse's historical data isn't always internally consistent about team abbreviations
# (e.g. the Rams show up as both "LA" and "LAR" across different rows). Not a bug we
# introduced -- normalize known aliases to one canonical code so team-level grouping
# (used later by team_stats) doesn't silently split one team's stats into two buckets.
# Add to this as validate.py/_diag scripts surface more, rather than guessing upfront.
TEAM_ABBR_ALIASES = {
    "LA": "LAR",
}

# Andrew's actual league scoring (confirmed 2026-07-25) -- a missed PAT is 0, not -1,
# which differs from some common defaults. Adjust if a different league scores differently.
KICKER_POINTS = {
    "fg_0_39": 3,
    "fg_40_49": 4,
    "fg_50_plus": 5,
    "fg_missed": -1,
    "pat_made": 1,
    "pat_missed": 0,
}

# Columns that should be treated as 0, not NaN, when a player didn't do that action that week
NUMERIC_STAT_COLUMNS = [
    "completions", "attempts", "passing_yards", "passing_tds", "passing_interceptions",
    "carries", "rushing_yards", "rushing_tds",
    "receptions", "targets", "receiving_yards", "receiving_tds",
    "fumbles_lost_total", "fantasy_points", "fantasy_points_ppr",
    "target_share", "wopr",  # 0 = no share of the passing game that week (e.g. a pure rusher)
    "fg_made_0_19", "fg_made_20_29", "fg_made_30_39", "fg_made_40_49", "fg_made_50_59", "fg_made_60_",
    "fg_missed", "pat_made", "pat_missed",
]


def get_known_gsis_ids(conn: sqlite3.Connection) -> set:
    cur = conn.execute("SELECT gsis_id FROM players")
    return {row[0] for row in cur.fetchall()}


def fetch_weekly_stats(years: list[int]):
    df = nfl.load_player_stats(years).to_pandas()
    df = df[df["season_type"] == "REG"].copy()  # regular season only -- most leagues don't play NFL playoff weeks
    df[NUMERIC_STAT_COLUMNS] = df[NUMERIC_STAT_COLUMNS].fillna(0)
    return df


def compute_kicker_points(r) -> float:
    fg_0_39 = r.fg_made_0_19 + r.fg_made_20_29 + r.fg_made_30_39
    fg_50_plus = r.fg_made_50_59 + r.fg_made_60_
    return (
        fg_0_39 * KICKER_POINTS["fg_0_39"]
        + r.fg_made_40_49 * KICKER_POINTS["fg_40_49"]
        + fg_50_plus * KICKER_POINTS["fg_50_plus"]
        + r.fg_missed * KICKER_POINTS["fg_missed"]
        + r.pat_made * KICKER_POINTS["pat_made"]
        + r.pat_missed * KICKER_POINTS["pat_missed"]
    )


def build_weekly_rows(df, known_gsis_ids: set) -> list[dict]:
    df = df[df["player_id"].isin(known_gsis_ids)]

    rows = []
    for r in df.itertuples(index=False):
        team = TEAM_ABBR_ALIASES.get(r.team, r.team)

        if r.position == "K":
            kicker_points = compute_kicker_points(r)
            fantasy_points_ppr = kicker_points
            fantasy_points_half_ppr = kicker_points  # PPR doesn't apply to kickers -- same value either way
        else:
            fantasy_points_ppr = r.fantasy_points_ppr
            fantasy_points_half_ppr = r.fantasy_points + 0.5 * r.receptions

        fg_0_39 = r.fg_made_0_19 + r.fg_made_20_29 + r.fg_made_30_39
        fg_50_plus = r.fg_made_50_59 + r.fg_made_60_

        rows.append({
            "gsis_id": r.player_id,
            "season": r.season,
            "week": r.week,
            "team": team,
            "completions": r.completions,
            "attempts": r.attempts,
            "passing_yards": r.passing_yards,
            "passing_tds": r.passing_tds,
            "interceptions": r.passing_interceptions,
            "carries": r.carries,
            "rushing_yards": r.rushing_yards,
            "rushing_tds": r.rushing_tds,
            "receptions": r.receptions,
            "targets": r.targets,
            "receiving_yards": r.receiving_yards,
            "receiving_tds": r.receiving_tds,
            "fumbles_lost": r.fumbles_lost_total,
            "fantasy_points_ppr": fantasy_points_ppr,
            "fantasy_points_half_ppr": fantasy_points_half_ppr,
            "target_share": r.target_share,
            "wopr": r.wopr,
            "fg_made_0_39": fg_0_39,
            "fg_made_40_49": r.fg_made_40_49,
            "fg_made_50_plus": fg_50_plus,
            "fg_missed": r.fg_missed,
            "pat_made": r.pat_made,
            "pat_missed": r.pat_missed,
        })
    return rows


def upsert_teams(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Ensures every team abbreviation referenced by these rows exists in `teams` first --
    weekly_stats.team is a foreign key, and nflverse's historical team codes don't
    necessarily match Sleeper's current-snapshot codes exactly (e.g. old vs. new
    abbreviations for a relocated/renamed team). Loading the dimension table (teams)
    before the fact table (weekly_stats) is what avoids the FK violation."""
    team_abbrs = {row["team"] for row in rows if row["team"]}
    conn.executemany(
        "INSERT OR IGNORE INTO teams (team_abbr, team_name) VALUES (?, ?)",
        [(abbr, abbr) for abbr in team_abbrs],  # team_name enriched later via import_team_desc()
    )


def upsert_weekly_stats(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        """
        INSERT INTO weekly_stats (
            gsis_id, season, week, team, completions, attempts, passing_yards, passing_tds,
            interceptions, carries, rushing_yards, rushing_tds, receptions, targets,
            receiving_yards, receiving_tds, fumbles_lost, fantasy_points_ppr, fantasy_points_half_ppr,
            target_share, wopr, fg_made_0_39, fg_made_40_49, fg_made_50_plus, fg_missed, pat_made, pat_missed
        ) VALUES (
            :gsis_id, :season, :week, :team, :completions, :attempts, :passing_yards, :passing_tds,
            :interceptions, :carries, :rushing_yards, :rushing_tds, :receptions, :targets,
            :receiving_yards, :receiving_tds, :fumbles_lost, :fantasy_points_ppr, :fantasy_points_half_ppr,
            :target_share, :wopr, :fg_made_0_39, :fg_made_40_49, :fg_made_50_plus, :fg_missed, :pat_made, :pat_missed
        )
        ON CONFLICT(gsis_id, season, week) DO UPDATE SET
            team=excluded.team,
            completions=excluded.completions,
            attempts=excluded.attempts,
            passing_yards=excluded.passing_yards,
            passing_tds=excluded.passing_tds,
            interceptions=excluded.interceptions,
            carries=excluded.carries,
            rushing_yards=excluded.rushing_yards,
            rushing_tds=excluded.rushing_tds,
            receptions=excluded.receptions,
            targets=excluded.targets,
            receiving_yards=excluded.receiving_yards,
            receiving_tds=excluded.receiving_tds,
            fumbles_lost=excluded.fumbles_lost,
            fantasy_points_ppr=excluded.fantasy_points_ppr,
            fantasy_points_half_ppr=excluded.fantasy_points_half_ppr,
            target_share=excluded.target_share,
            wopr=excluded.wopr,
            fg_made_0_39=excluded.fg_made_0_39,
            fg_made_40_49=excluded.fg_made_40_49,
            fg_made_50_plus=excluded.fg_made_50_plus,
            fg_missed=excluded.fg_missed,
            pat_made=excluded.pat_made,
            pat_missed=excluded.pat_missed
        """,
        rows,
    )


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        known_gsis_ids = get_known_gsis_ids(conn)
        print(f"{len(known_gsis_ids)} known players in the database")

        print(f"Fetching weekly stats for {YEARS[0]}-{YEARS[-1]}...")
        df = fetch_weekly_stats(YEARS)
        print(f"  {len(df)} total weekly rows from nflverse (all players, all positions, regular season)")

        rows = build_weekly_rows(df, known_gsis_ids)
        print(f"  {len(rows)} rows matched to a known player")

        upsert_teams(conn, rows)
        upsert_weekly_stats(conn, rows)
        conn.commit()
    finally:
        conn.close()

    print("Done.")


if __name__ == "__main__":
    main()
