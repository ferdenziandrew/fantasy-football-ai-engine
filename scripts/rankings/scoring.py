"""
Core rankings engine. Reads weekly_stats, computes a transparent weighted score per
player, and writes results to the `rankings` table.

Known limitation (not fixed here -- see ROADMAP.md): players with zero weekly_stats
rows (mainly incoming rookies) get no score at all, since there's nothing to weight.
Draft capital (import_draft_picks()) is the planned supplementary signal for that gap,
not yet built.

The formula, in order of what it does to a player's raw weekly point totals:

0. Recency eligibility filter -- players with no games in the last N seasons are
   dropped entirely before scoring (almost certainly retired/out of the league). This
   has to be a hard filter, not a decay factor baked into the weighted average below --
   averaging cancels out any constant per-player scale factor, so two players with
   identical stats from different (internally uniform) seasons would otherwise score
   identically no matter how strong the decay rate is. Caught this via a test comparing
   an identical stat line in 2025 vs. 2020, which should NOT have scored the same.
1. Recency-weighted average -- within an eligible player's own game log, recent
   seasons/weeks count more than old ones.
2. Sample-size shrinkage -- players with few games get pulled toward their positional
   average, so a tiny hot streak can't outrank a full proven season on a technicality.
3. Opportunity bonus -- players with a high target_share/wopr (underlying role, not
   just results) get a proportional boost, since usage tends to predict future
   production before the box score fully catches up.
4. Value over replacement (VOR) -- final cross-position ranking is based on how much
   better a player is than the last realistically-startable player at their position,
   not raw points, since raw points aren't comparable across positions with different
   scarcity.

Every number that drives this is in weights_config.py -- tune there, not here.

Usage:
    py scripts/rankings/scoring.py
"""

import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path

from weights_config import WEIGHTS, REPLACEMENT_RANK

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"

# The season we're building rankings FOR (hasn't been played yet) -- recency decay and
# eligibility are measured as distance back from this, not from "today."
REFERENCE_SEASON = 2026


def load_weekly_rows(conn: sqlite3.Connection) -> list[dict]:
    points_col = "fantasy_points_ppr" if WEIGHTS["scoring_format"] == "ppr" else "fantasy_points_half_ppr"
    cur = conn.execute(f"""
        SELECT w.gsis_id, p.position, p.full_name, w.season, w.week,
               w.{points_col} AS points, w.target_share, w.wopr
        FROM weekly_stats w
        JOIN players p ON w.gsis_id = p.gsis_id
    """)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_season_max_weeks(conn: sqlite3.Connection) -> dict:
    """Last week actually played in each season -- used as the anchor point for
    within-season recency (so the most recent week of a season gets full weight,
    not a fixed week-18 assumption that's wrong for shortened/older seasons)."""
    rows = conn.execute("SELECT season, MAX(week) FROM weekly_stats GROUP BY season").fetchall()
    return dict(rows)


def row_weight(season: int, week: int, season_max_weeks: dict) -> float:
    season_distance = REFERENCE_SEASON - season
    week_distance = season_max_weeks[season] - week
    return (WEIGHTS["season_decay_rate"] ** season_distance) * (WEIGHTS["week_decay_rate"] ** week_distance)


def compute_player_aggregates(rows: list[dict], season_max_weeks: dict) -> dict:
    """One pass over weekly rows -> per-player recency-weighted average points,
    weighted average opportunity metric, floor/ceiling, games played, and the most
    recent season they appear in (used by the eligibility filter)."""
    by_player: dict = {}
    for r in rows:
        by_player.setdefault(r["gsis_id"], {
            "full_name": r["full_name"],
            "position": r["position"],
            "points_list": [],
            "weighted_points_sum": 0.0,
            "weighted_wopr_sum": 0.0,
            "weight_sum": 0.0,
            "games_played": 0,
            "most_recent_season": r["season"],
        })
        agg = by_player[r["gsis_id"]]
        w = row_weight(r["season"], r["week"], season_max_weeks)
        agg["points_list"].append(r["points"])
        agg["weighted_points_sum"] += r["points"] * w
        agg["weighted_wopr_sum"] += (r["wopr"] or 0) * w
        agg["weight_sum"] += w
        agg["games_played"] += 1
        agg["most_recent_season"] = max(agg["most_recent_season"], r["season"])

    results = {}
    for gsis_id, agg in by_player.items():
        weighted_avg_points = agg["weighted_points_sum"] / agg["weight_sum"]
        weighted_avg_wopr = agg["weighted_wopr_sum"] / agg["weight_sum"]
        sorted_points = sorted(agg["points_list"])
        results[gsis_id] = {
            "full_name": agg["full_name"],
            "position": agg["position"],
            "games_played": agg["games_played"],
            "most_recent_season": agg["most_recent_season"],
            "weighted_avg_points": weighted_avg_points,
            "weighted_avg_wopr": weighted_avg_wopr,
            "floor": statistics.quantiles(sorted_points, n=4)[0] if len(sorted_points) >= 4 else min(sorted_points),
            "ceiling": statistics.quantiles(sorted_points, n=4)[2] if len(sorted_points) >= 4 else max(sorted_points),
        }
    return results


def filter_eligible_players(aggregates: dict) -> dict:
    """Drops players with no games in the last `eligibility_window_seasons` seasons --
    see the module docstring for why this has to be a hard filter, not a decay factor."""
    cutoff = REFERENCE_SEASON - WEIGHTS["eligibility_window_seasons"]
    return {
        gsis_id: p for gsis_id, p in aggregates.items()
        if p["most_recent_season"] >= cutoff
    }


def apply_shrinkage_and_opportunity(aggregates: dict) -> dict:
    """Applies sample-size shrinkage (toward positional average) and the opportunity
    bonus on top of the recency-weighted average, producing each player's raw_score."""
    min_games = WEIGHTS["min_games_for_full_confidence"]
    shrink_strength = WEIGHTS["low_sample_shrinkage_strength"]
    opportunity_weight = WEIGHTS["opportunity_weight"]

    # Positional baseline computed only from players who already meet the games
    # threshold, so small-sample noise doesn't drag down the average it's compared to.
    by_position: dict = {}
    for p in aggregates.values():
        if p["games_played"] >= min_games:
            by_position.setdefault(p["position"], []).append(p["weighted_avg_points"])
    positional_avg = {
        pos: sum(vals) / len(vals) for pos, vals in by_position.items() if vals
    }

    for p in aggregates.values():
        baseline = positional_avg.get(p["position"], p["weighted_avg_points"])
        confidence = min(p["games_played"] / min_games, 1.0)
        effective_shrink = shrink_strength * (1 - confidence)
        shrunk_points = p["weighted_avg_points"] * (1 - effective_shrink) + baseline * effective_shrink

        # Proportional boost, not a flat point add -- e.g. a true #1 WR (wopr ~1.0) with
        # opportunity_weight=0.15 gets up to a 15% score bump; a pure rusher/QB with
        # wopr=0 gets none. This is the "underlying role predicts production" signal.
        opportunity_multiplier = 1 + (opportunity_weight * p["weighted_avg_wopr"])

        p["raw_score"] = shrunk_points * opportunity_multiplier

    return aggregates


def compute_vor(aggregates: dict) -> dict:
    """Value over replacement: how much better a player is than the last
    realistically-startable player at their position, so positions with steeper
    drop-offs aren't unfairly compared to positions with deeper talent pools."""
    by_position: dict = {}
    for gsis_id, p in aggregates.items():
        by_position.setdefault(p["position"], []).append((gsis_id, p["raw_score"]))

    for position, players in by_position.items():
        players.sort(key=lambda x: x[1], reverse=True)
        replacement_idx = REPLACEMENT_RANK.get(position, len(players)) - 1
        replacement_idx = max(0, min(replacement_idx, len(players) - 1))
        replacement_score = players[replacement_idx][1]

        for rank_in_position, (gsis_id, score) in enumerate(players, start=1):
            aggregates[gsis_id]["positional_rank"] = rank_in_position
            aggregates[gsis_id]["vor"] = score - replacement_score

    return aggregates


def write_rankings(conn: sqlite3.Connection, aggregates: dict) -> None:
    generated_at = datetime.now(timezone.utc).isoformat()
    scoring_format = WEIGHTS["scoring_format"]

    ranked = sorted(aggregates.items(), key=lambda kv: kv[1]["vor"], reverse=True)
    rows = [
        {
            "gsis_id": gsis_id,
            "scoring_format": scoring_format,
            "rank": overall_rank,
            "score": p["vor"],
            "blurb": None,
            "blurb_source": None,
            "generated_at": generated_at,
        }
        for overall_rank, (gsis_id, p) in enumerate(ranked, start=1)
    ]

    conn.executemany(
        """
        INSERT INTO rankings (gsis_id, scoring_format, rank, score, blurb, blurb_source, generated_at)
        VALUES (:gsis_id, :scoring_format, :rank, :score, :blurb, :blurb_source, :generated_at)
        """,
        rows,
    )


def print_preview(aggregates: dict, top_n: int = 30) -> None:
    ranked = sorted(aggregates.items(), key=lambda kv: kv[1]["vor"], reverse=True)
    print(f"\n=== Top {top_n} overall (VOR-based) ===")
    for i, (gsis_id, p) in enumerate(ranked[:top_n], start=1):
        print(f"  {i:>3}. {p['full_name']:<25} {p['position']:<3} "
              f"score={p['raw_score']:.1f}  vor={p['vor']:.1f}  "
              f"floor={p['floor']:.1f}  ceiling={p['ceiling']:.1f}  games={p['games_played']}")

    print("\n=== Top 10 per position ===")
    by_position: dict = {}
    for gsis_id, p in aggregates.items():
        by_position.setdefault(p["position"], []).append(p)
    for position in sorted(by_position):
        players = sorted(by_position[position], key=lambda p: p["raw_score"], reverse=True)[:10]
        print(f"\n  -- {position} --")
        for p in players:
            print(f"    {p['positional_rank']:>2}. {p['full_name']:<25} "
                  f"score={p['raw_score']:.1f}  games={p['games_played']}")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = load_weekly_rows(conn)
        print(f"{len(rows)} weekly rows loaded")

        season_max_weeks = get_season_max_weeks(conn)
        aggregates = compute_player_aggregates(rows, season_max_weeks)
        print(f"{len(aggregates)} players with at least one game")

        aggregates = filter_eligible_players(aggregates)
        print(f"{len(aggregates)} players still eligible (played within the last "
              f"{WEIGHTS['eligibility_window_seasons']} seasons)")

        aggregates = apply_shrinkage_and_opportunity(aggregates)
        aggregates = compute_vor(aggregates)

        print_preview(aggregates)

        conn.execute(
            "DELETE FROM rankings WHERE scoring_format = ?", (WEIGHTS["scoring_format"],)
        )  # clear previous run for this format before writing the new one
        write_rankings(conn, aggregates)
        conn.commit()
        print(f"\nWrote {len(aggregates)} rows to rankings (scoring_format={WEIGHTS['scoring_format']})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
