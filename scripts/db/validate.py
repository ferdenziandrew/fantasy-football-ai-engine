"""
Basic sanity checks against the database -- row counts, foreign key integrity, null
checks, and range checks. Not a full test suite, just a quick "does this look right"
report to run after ingestion. Nothing here should be treated as a hard failure by
itself -- read the numbers and decide whether they make sense.

Usage:
    py scripts/db/validate.py
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"

TABLES = ["teams", "players", "weekly_stats", "snap_counts", "advanced_stats", "team_stats", "adp", "rankings"]


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    print("=== Row counts ===")
    for t in TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {count}")

    print("\n=== Foreign key integrity ===")
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        print(f"  {len(violations)} FK violations found (showing up to 10):")
        for v in violations[:10]:
            print(" ", v)
    else:
        print("  OK -- no foreign key violations")

    print("\n=== Players with no weekly stats ===")
    total_players = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    orphans = conn.execute(
        "SELECT COUNT(*) FROM players p "
        "WHERE NOT EXISTS (SELECT 1 FROM weekly_stats w WHERE w.gsis_id = p.gsis_id)"
    ).fetchone()[0]
    print(f"  {orphans} of {total_players} players have zero weekly_stats rows")
    print("  (expected for rookies not yet in a game / recently retired players -- only")
    print("   worth investigating if this fraction looks surprisingly high)")

    print("\n=== Null checks on key columns ===")
    for table, col in [
        ("players", "full_name"),
        ("players", "position"),
        ("weekly_stats", "season"),
        ("weekly_stats", "week"),
    ]:
        n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL").fetchone()[0]
        print(f"  {table}.{col}: {n} nulls")

    print("\n=== Season / week range check ===")
    season_min, season_max, week_min, week_max = conn.execute(
        "SELECT MIN(season), MAX(season), MIN(week), MAX(week) FROM weekly_stats"
    ).fetchone()
    print(f"  season range: {season_min}-{season_max}, week range: {week_min}-{week_max}")
    if season_min < 2020 or season_max > 2025 or week_min < 1 or week_max > 18:
        print("  ! outside expected range (season 2020-2025, week 1-18) -- worth investigating")
    else:
        print("  OK -- within expected range")

    print("\n=== Fantasy points sanity (min/max per season) ===")
    for (season,) in conn.execute("SELECT DISTINCT season FROM weekly_stats ORDER BY season").fetchall():
        pts_min, pts_max = conn.execute(
            "SELECT MIN(fantasy_points_ppr), MAX(fantasy_points_ppr) FROM weekly_stats WHERE season = ?",
            (season,),
        ).fetchone()
        print(f"  {season}: min={pts_min:.1f}, max={pts_max:.1f}")

    conn.close()


if __name__ == "__main__":
    main()
