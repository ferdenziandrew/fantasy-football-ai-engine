"""
Compares the two most recent ADP pulls (source='ffc') to show market risers/fallers
over time -- ROADMAP.md's Phase 5 "ADP movement tracking" item, made trivial by a
design choice already in place: the adp table stores every pull as its own snapshot
(pulled_at as part of the primary key), never overwriting the previous one. So this is
just a comparison query, not a new data model.

Positive delta = ADP got LOWER (earlier/more valuable) since the last pull -- a riser.
Negative delta = ADP got HIGHER (later/less valuable) -- a faller.

Not position-filtered (unlike export_rankings_vs_adp.py) -- market movement is a valid
signal at any position, including K, so this intentionally includes everyone with an
ADP in both pulls.

Usage (run AFTER re-pulling ADP -- i.e. after `py scripts/ingest/ffc.py`):
    py scripts/rankings/export_adp_movement.py
"""

import csv
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "adp_movement.csv"

ADP_SOURCE = "ffc"


def get_two_most_recent_pulls(conn: sqlite3.Connection) -> tuple[str, str]:
    rows = conn.execute(
        "SELECT DISTINCT pulled_at FROM adp WHERE source = ? ORDER BY pulled_at DESC LIMIT 2",
        (ADP_SOURCE,),
    ).fetchall()
    if len(rows) < 2:
        raise SystemExit(
            f"Need at least 2 separate ADP pulls to compare -- found {len(rows)}. "
            f"Re-run `py scripts/ingest/ffc.py` to create a new snapshot, then try again."
        )
    return rows[0][0], rows[1][0]  # (most_recent, previous)


def fetch_adp_at(conn: sqlite3.Connection, pulled_at: str) -> dict:
    cur = conn.execute(
        """
        SELECT a.gsis_id, p.full_name, p.position, a.adp
        FROM adp a JOIN players p ON a.gsis_id = p.gsis_id
        WHERE a.source = ? AND a.pulled_at = ?
        """,
        (ADP_SOURCE, pulled_at),
    )
    return {row[0]: {"full_name": row[1], "position": row[2], "adp": row[3]} for row in cur.fetchall()}


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        latest_ts, previous_ts = get_two_most_recent_pulls(conn)
        latest = fetch_adp_at(conn, latest_ts)
        previous = fetch_adp_at(conn, previous_ts)
    finally:
        conn.close()

    common = set(latest) & set(previous)
    rows = []
    for gsis_id in common:
        new, old = latest[gsis_id], previous[gsis_id]
        rows.append({
            "player": new["full_name"],
            "position": new["position"],
            "previous_adp": old["adp"],
            "current_adp": new["adp"],
            "delta": round(old["adp"] - new["adp"], 1),  # positive = riser (ADP got lower)
        })
    rows.sort(key=lambda r: r["delta"], reverse=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["player", "position", "previous_adp", "current_adp", "delta"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Comparing {previous_ts} -> {latest_ts}")
    print(f"{len(rows)} players present in both pulls. Wrote full comparison to {OUTPUT_PATH}\n")

    risers = [r for r in rows if r["delta"] > 0][:15]
    fallers = sorted([r for r in rows if r["delta"] < 0], key=lambda r: r["delta"])[:15]

    print("=== Top 15 risers (ADP moved earlier/more valuable) ===")
    for r in risers:
        print(f"  {r['player']:<25} {r['position']:<3} {r['previous_adp']:>6.1f} -> {r['current_adp']:<6.1f} (+{r['delta']})")

    print("\n=== Top 15 fallers (ADP moved later/less valuable) ===")
    for r in fallers:
        print(f"  {r['player']:<25} {r['position']:<3} {r['previous_adp']:>6.1f} -> {r['current_adp']:<6.1f} ({r['delta']})")


if __name__ == "__main__":
    main()
