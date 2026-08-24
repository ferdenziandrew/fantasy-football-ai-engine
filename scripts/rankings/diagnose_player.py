"""
Diagnostic tool: shows a player's raw weekly game log AND how scoring.py's own pipeline
turned it into a score -- weighted average, shrinkage applied, opportunity multiplier,
final VOR. Built 2026-08-24 specifically to check two cases Andrew flagged as "shouldn't
be ranked at all" (Phil Mafah, Will Levis) -- were they scored high off a genuinely hot
small sample that shrinkage isn't pulling down hard enough, or something else? Reuses
scoring.py's actual functions (not a reimplementation), so what this prints is exactly
what the real pipeline computed, not an approximation of it.

Usage:
    py scripts/rankings/diagnose_player.py <name substring> [<name substring> ...]
    e.g. py scripts/rankings/diagnose_player.py "Mafah" "Levis"
"""

import sqlite3
import sys

import scoring
from weights_config import WEIGHTS


def find_players(conn: sqlite3.Connection, name_substring: str) -> list[tuple]:
    cur = conn.execute(
        "SELECT gsis_id, full_name, position, current_team, draft_year, draft_pick FROM players WHERE full_name LIKE ?",
        (f"%{name_substring}%",),
    )
    return cur.fetchall()


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: py scripts/rankings/diagnose_player.py <name substring> [...]")

    conn = sqlite3.connect(scoring.DB_PATH)
    try:
        rows = scoring.load_weekly_rows(conn)
        season_max_weeks = scoring.get_season_max_weeks(conn)
        aggregates = scoring.compute_player_aggregates(rows, season_max_weeks)
        aggregates = scoring.filter_eligible_players(aggregates)
        aggregates = scoring.filter_current_roster(aggregates)
        positional_avg = scoring.compute_positional_avg(aggregates)
        aggregates = scoring.apply_shrinkage_and_opportunity(aggregates, positional_avg)
        aggregates = scoring.compute_vor(aggregates)

        for name_substring in sys.argv[1:]:
            print(f"\n{'='*60}\nSearching for: {name_substring!r}\n{'='*60}")
            matches = find_players(conn, name_substring)
            if not matches:
                print("  No player found with that name.")
                continue

            for gsis_id, full_name, position, current_team, draft_year, draft_pick in matches:
                print(f"\n{full_name} ({position}, {current_team or 'NO CURRENT TEAM'}) -- {gsis_id}")
                print(f"  draft_year={draft_year} draft_pick={draft_pick}")

                weekly = [r for r in rows if r["gsis_id"] == gsis_id]
                weekly.sort(key=lambda r: (r["season"], r["week"]))
                print(f"  {len(weekly)} weekly rows in our data:")
                for w in weekly:
                    print(f"    {w['season']} wk{w['week']:>2}: {w['points']:>6.1f} pts  "
                          f"target_share={w['target_share']}  wopr={w['wopr']}")

                if gsis_id not in aggregates:
                    print("  NOT in final aggregates (filtered out before scoring -- "
                          "check recency eligibility or current-roster status above).")
                    continue

                p = aggregates[gsis_id]
                baseline = positional_avg.get(position)
                min_games = scoring.get_min_games(position)
                shrink_strength = scoring.get_shrink_strength(position)
                confidence = min(p["games_played"] / min_games, 1.0)
                print(f"  games_played={p['games_played']}  min_games_for_full_confidence={min_games}  "
                      f"confidence={confidence:.2f}  shrink_strength={shrink_strength}")
                print(f"  weighted_avg_points={p['weighted_avg_points']:.2f}  "
                      f"positional_avg({position})={baseline:.2f}" if baseline else "  no positional_avg available")
                print(f"  weighted_avg_wopr={p['weighted_avg_wopr']:.3f}  "
                      f"opportunity_weight={WEIGHTS['opportunity_weight']}")
                print(f"  FINAL raw_score={p['raw_score']:.2f}  positional_rank={p['positional_rank']}  "
                      f"vor={p['vor']:.2f}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
