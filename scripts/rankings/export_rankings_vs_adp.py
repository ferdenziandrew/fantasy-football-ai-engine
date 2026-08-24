"""
Exports our positional rank vs. current market ADP for QB/RB/WR/TE (K excluded --
kicker ADP is thin/unreliable and not where the interesting disagreements are) to a CSV,
for visualizing where our rankings and the market diverge. Complements
adp_comparison.py (which prints the biggest disagreements as text) with the full
top-N-per-position picture, laid out for charting rather than reading top-to-bottom.

Depth per position mirrors blurb_worklist.py's reasoning -- QB/TE run thinner in real
10-12 team draft relevance than RB/WR, which go deep on flex/handcuff/PPR value.

Reuses cheat_sheet.fetch_rankings() and blurb_worklist.fetch_adp_lookup() rather than
re-deriving rank/tier/ADP logic -- same source of truth as the cheat sheet and the
blurb worklists, so this can never quietly disagree with them about a player's rank or
what "current ADP" means.

Usage:
    py scripts/rankings/export_rankings_vs_adp.py
"""

import csv
import sqlite3
from pathlib import Path

from cheat_sheet import fetch_rankings, DB_PATH, PROJECT_ROOT
from blurb_worklist import fetch_adp_lookup

OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "rankings_vs_adp.csv"

POSITION_LIMITS = {
    "QB": 20,
    "RB": 40,
    "WR": 45,
    "TE": 20,
}


def build_rows(all_rankings: list[dict], adp_lookup: dict) -> list[dict]:
    rows = []
    for position, limit in POSITION_LIMITS.items():
        position_rows = sorted(
            (r for r in all_rankings if r["position"] == position),
            key=lambda r: r["positional_rank"],
        )[:limit]
        for r in position_rows:
            adp = adp_lookup.get(r["gsis_id"])
            rows.append({
                "position": position,
                "our_rank": r["positional_rank"],
                "player": r["full_name"],
                "team": r["current_team"],
                "adp": round(adp, 1) if adp is not None else "",
                "delta": round(adp - r["rank"], 1) if adp is not None else "",
                "overall_rank": r["rank"],
            })
    return rows


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        all_rankings = fetch_rankings(conn)
        adp_lookup = fetch_adp_lookup(conn)
    finally:
        conn.close()

    if not all_rankings:
        raise SystemExit("No rankings found -- run scoring.py first.")

    rows = build_rows(all_rankings, adp_lookup)
    missing_adp = sum(1 for r in rows if r["adp"] == "")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["position", "our_rank", "player", "team", "adp", "delta", "overall_rank"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows ({sum(POSITION_LIMITS.values())} slots across "
          f"{len(POSITION_LIMITS)} positions) to {OUTPUT_PATH}")
    if missing_adp:
        print(f"  ({missing_adp} rows have no ADP match -- deep bench players not in FFC's mock draft pool)")


if __name__ == "__main__":
    main()
