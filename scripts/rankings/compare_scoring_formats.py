"""
Sanity-checks the Half-PPR scoring path against Full-PPR by comparing both directly
from the DB. Both scoring_formats can coexist in the rankings table at once -- scoring.py's
DELETE is scoped to a single scoring_format (see scoring.py's main()), so running it for
'half_ppr' doesn't touch the existing 'ppr' rows. That means no snapshot file is needed
here, unlike rankings_diff.py, which compares the same format across time and does need one.

v1 (2026-08-01) compared every player by raw overall rank and got swamped by noise: the
biggest "movers" were all deep-bench players (QB QB40+, replacement-level TEs) with
negative VOR scores bunched within fractions of a point of each other -- a tiny score
nudge among hundreds of near-identical scrubs swings the overall cross-position rank by
100+ spots without anything meaningful actually changing. Below replacement level, rank
isn't a stable signal at all. Fixed by:
  - Only comparing players ABOVE replacement in both formats (score > 0 in both -- VOR
    is 0 exactly at replacement level by construction, so this is a principled cutoff,
    not an arbitrary one).
  - Restricting the mover lists to RB/WR/TE -- the positions where receptions actually
    factor into the score. QB and K are EXPECTED to barely move: kicker scoring never
    involves receptions at all (see nfl_data.py), and QBs essentially never catch
    passes, so their PPR and Half-PPR scores being near-identical is correct behavior,
    not a sign the toggle is broken -- printed as an informational note instead of
    being mixed into the "did this move the right direction" mover list, where it was
    just confusing noise (huge rank deltas on scores that hadn't meaningfully changed).

What "sanity" means here: Half-PPR should differ from Full-PPR in a specific, predictable
direction among fantasy-relevant RB/WR/TE -- pass-catching specialists (high receptions)
should lose relative rank, since each reception is worth half as much; low-reception,
high-carry players should hold steady or gain relative rank. This script doesn't
automate that judgment (too fuzzy to be worth encoding for a one-time check) -- it just
prints the filtered comparison, sorted by biggest movers, for a human to eyeball.

Usage (run AFTER generating half_ppr rankings):
    1. Temporarily edit weights_config.py: change "scoring_format": "ppr" to "half_ppr"
    2. py scripts/rankings/scoring.py
    3. Change weights_config.py's scoring_format back to "ppr" (so future normal runs
       don't stay on half_ppr by accident)
    4. py scripts/rankings/compare_scoring_formats.py
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"

TOP_N = 20
MOVER_POSITIONS = {"RB", "WR", "TE"}  # positions where receptions actually affect the score


def fetch_format(conn: sqlite3.Connection, scoring_format: str) -> dict:
    cur = conn.execute(
        """
        SELECT r.gsis_id, p.full_name, p.position, r.rank, r.score
        FROM rankings r JOIN players p ON r.gsis_id = p.gsis_id
        WHERE r.scoring_format = ?
        """,
        (scoring_format,),
    )
    cols = [d[0] for d in cur.description]
    return {row[0]: dict(zip(cols, row)) for row in cur.fetchall()}


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        ppr = fetch_format(conn, "ppr")
        half = fetch_format(conn, "half_ppr")
    finally:
        conn.close()

    if not half:
        raise SystemExit(
            "No half_ppr rankings found. Temporarily set weights_config.py's "
            "scoring_format to 'half_ppr', run scoring.py, then re-run this script "
            "(and remember to set scoring_format back to 'ppr' afterward)."
        )
    if not ppr:
        raise SystemExit("No ppr rankings found -- run scoring.py with scoring_format='ppr' first.")

    common = set(ppr) & set(half)
    if not common:
        raise SystemExit("No players scored in both formats -- can't compare.")

    all_players = []
    for gid in common:
        p, h = ppr[gid], half[gid]
        all_players.append({
            "full_name": p["full_name"], "position": p["position"],
            "ppr_rank": p["rank"], "half_rank": h["rank"], "rank_delta": p["rank"] - h["rank"],
            "ppr_score": p["score"], "half_score": h["score"],
        })

    identical = sum(1 for m in all_players if m["rank_delta"] == 0 and m["ppr_score"] == m["half_score"])
    print(f"{len(all_players)} players compared. {identical} identical between formats.")
    if identical == len(all_players):
        print("WARNING: every player is identical between ppr and half_ppr -- the toggle "
              "may not actually be wired up. Check weights_config.py['scoring_format'] "
              "was really 'half_ppr' when scoring.py last ran, and that it wasn't "
              "immediately reverted before running.")
        return

    # QB/K informational note -- these are EXPECTED to barely move, not a sign of a bug.
    qb_k = [m for m in all_players if m["position"] in ("QB", "K")]
    qb_k_score_changed = [m for m in qb_k if abs(m["ppr_score"] - m["half_score"]) > 0.05]
    print(f"\nQB/K note: {len(qb_k) - len(qb_k_score_changed)}/{len(qb_k)} have essentially unchanged "
          f"scores between formats -- expected, since kicker scoring never involves receptions and QBs "
          f"almost never catch passes. Large RANK swings among these at deep bench positions are noise "
          f"from crowded replacement-level scores, not a bug -- ignore rank movement for QB/K here.")

    # The real signal: above-replacement (score > 0 in both formats) RB/WR/TE only.
    movers = [m for m in all_players
              if m["position"] in MOVER_POSITIONS and m["ppr_score"] > 0 and m["half_score"] > 0]
    excluded = len([m for m in all_players if m["position"] in MOVER_POSITIONS]) - len(movers)
    print(f"\nComparing {len(movers)} above-replacement RB/WR/TE ({excluded} below-replacement "
          f"RB/WR/TE excluded as noise -- not fantasy-relevant in either format).")

    risers = sorted(movers, key=lambda m: m["rank_delta"], reverse=True)[:TOP_N]
    fallers = sorted(movers, key=lambda m: m["rank_delta"])[:TOP_N]

    print("\n=== Gained the most rank moving PPR -> Half-PPR (expect low-reception rushers here) ===")
    for m in risers:
        if m["rank_delta"] <= 0:
            break
        print(f"  {m['full_name']:<25} {m['position']:<3} PPR #{m['ppr_rank']:<4} -> Half #{m['half_rank']:<4} "
              f"(+{m['rank_delta']})  score {m['ppr_score']:.1f} -> {m['half_score']:.1f}")

    print("\n=== Lost the most rank moving PPR -> Half-PPR (expect pass-catching specialists here) ===")
    for m in fallers:
        if m["rank_delta"] >= 0:
            break
        print(f"  {m['full_name']:<25} {m['position']:<3} PPR #{m['ppr_rank']:<4} -> Half #{m['half_rank']:<4} "
              f"({m['rank_delta']})  score {m['ppr_score']:.1f} -> {m['half_score']:.1f}")


if __name__ == "__main__":
    main()
