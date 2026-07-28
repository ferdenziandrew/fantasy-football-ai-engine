"""
Compares our own rankings against market ADP and flags the biggest disagreements --
NOT to feed ADP into the scoring formula (deliberately kept separate, see
weights_config.py's docstring/ROADMAP.md for why: blending market consensus into our
own score would just make the rankings converge toward "matching ADP," undermining the
whole point of having an independent, defensible methodology).

Instead, this is a QA-style review tool: a big disagreement means one of two things,
and this script can't tell you which --
  - a real edge -- the market hasn't caught up to something our formula sees (a good thing)
  - a formula blind spot -- context we don't have (an injury, a coaching change, a
    depth-chart battle) that only shows up in a human's read of the situation
Both are worth a look before the cheat sheet ships; this just surfaces the candidates.

ADP source: Fantasy Football Calculator (ffc.py), the primary source since FantasyPros'
free tier only returns 10 players. Uses the most recent pull for that source.

delta = adp - our_rank
  positive delta -> we rank him BETTER (lower rank number) than the market does
                    ("we like him more than consensus" -- a possible value)
  negative delta -> we rank him WORSE than the market does
                    ("we like him less than consensus" -- a possible fade, or a blind spot)

Usage:
    py scripts/rankings/adp_comparison.py
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"

SCORING_FORMAT = "ppr"
ADP_SOURCE = "ffc"
TOP_N = 20  # how many rows to show per direction


def fetch_comparison(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        """
        SELECT p.full_name, p.position, r.rank AS our_rank, a.adp
        FROM rankings r
        JOIN players p ON r.gsis_id = p.gsis_id
        JOIN adp a ON a.gsis_id = r.gsis_id
        WHERE r.scoring_format = ?
          AND a.source = ?
          AND a.pulled_at = (SELECT MAX(pulled_at) FROM adp WHERE source = ?)
        """,
        (SCORING_FORMAT, ADP_SOURCE, ADP_SOURCE),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    for r in rows:
        r["delta"] = r["adp"] - r["our_rank"]
    return rows


def print_report(rows: list[dict]) -> None:
    if not rows:
        print("No overlap between rankings and ADP -- check both tables have data for "
              f"scoring_format='{SCORING_FORMAT}' and source='{ADP_SOURCE}'.")
        return

    print(f"{len(rows)} players matched between our rankings and {ADP_SOURCE} ADP\n")

    likes_more = sorted(rows, key=lambda r: r["delta"], reverse=True)[:TOP_N]
    print(f"=== Top {TOP_N}: we rank HIGHER than the market (possible value) ===")
    for r in likes_more:
        print(f"  {r['full_name']:<25} {r['position']:<3} our_rank={r['our_rank']:>4}  "
              f"adp={r['adp']:>6.1f}  delta={r['delta']:>+6.1f}")

    likes_less = sorted(rows, key=lambda r: r["delta"])[:TOP_N]
    print(f"\n=== Top {TOP_N}: we rank LOWER than the market (possible fade or blind spot) ===")
    for r in likes_less:
        print(f"  {r['full_name']:<25} {r['position']:<3} our_rank={r['our_rank']:>4}  "
              f"adp={r['adp']:>6.1f}  delta={r['delta']:>+6.1f}")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = fetch_comparison(conn)
    finally:
        conn.close()
    print_report(rows)


if __name__ == "__main__":
    main()
