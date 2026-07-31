"""
Saves a point-in-time snapshot of the current rankings + the weights_config.py values
that produced them, so a later run (after tuning weights) can be diffed against it via
rankings_diff.py.

Why this exists as a separate file rather than just comparing two DB states: scoring.py
deliberately DELETEs the previous run for a scoring_format before writing the new one
(see scoring.py's main()) -- unlike the adp table, rankings history isn't kept as
snapshots in the DB itself. That's a reasonable choice for the DB (keeps the table
simple, avoids unbounded growth from routine tuning re-runs), but it means there's
nothing left in the DB to compare against once a new run has overwritten the old one.
This script is the "before" side of that comparison, saved to a plain file instead.

Typical workflow:
    py scripts/rankings/snapshot_rankings.py     # before changing weights_config.py
    # ... edit weights_config.py, re-run scoring.py ...
    py scripts/rankings/rankings_diff.py         # compares against the latest snapshot

Usage:
    py scripts/rankings/snapshot_rankings.py [scoring_format]
    (defaults to weights_config.WEIGHTS["scoring_format"] if not given)
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import weights_config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "processed"


def fetch_current_rankings(conn: sqlite3.Connection, scoring_format: str) -> list[dict]:
    cur = conn.execute(
        """
        SELECT r.gsis_id, p.full_name, p.position, r.rank, r.positional_rank, r.score
        FROM rankings r
        JOIN players p ON r.gsis_id = p.gsis_id
        WHERE r.scoring_format = ?
        ORDER BY r.rank
        """,
        (scoring_format,),
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def main() -> None:
    scoring_format = sys.argv[1] if len(sys.argv) > 1 else weights_config.WEIGHTS["scoring_format"]

    conn = sqlite3.connect(DB_PATH)
    try:
        rankings = fetch_current_rankings(conn, scoring_format)
    finally:
        conn.close()

    if not rankings:
        raise SystemExit(f"No rankings found for scoring_format='{scoring_format}' -- run scoring.py first.")

    snapshot = {
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "scoring_format": scoring_format,
        "weights": weights_config.WEIGHTS,
        "replacement_rank": weights_config.REPLACEMENT_RANK,
        "rankings": rankings,
    }

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = SNAPSHOT_DIR / f"rankings_snapshot_{scoring_format}_{ts}.json"
    out_path.write_text(json.dumps(snapshot, indent=2))

    print(f"Snapshotted {len(rankings)} players (scoring_format='{scoring_format}') to {out_path}")


if __name__ == "__main__":
    main()
