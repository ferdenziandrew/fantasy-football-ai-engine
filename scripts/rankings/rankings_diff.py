"""
Compares the CURRENT rankings/weights_config.py against a saved snapshot (see
snapshot_rankings.py), so a weights-tuning pass shows exactly what changed -- both in
the config itself and in the resulting rank movements -- instead of eyeballing two full
cheat sheets side by side.

Shows, in order: which weight values actually changed between the snapshot and now,
then the biggest risers/fallers by rank, then the biggest movers by raw score (a
different cut -- a player can move a lot in score without changing rank much in a
crowded tier, or vice versa near a thin part of the board).

Not a fully general diff tool -- deliberately simple (plain dict comparison, no nested
diff library) since this is meant to be read once right after a tuning change, not
maintained as its own subsystem.

Usage:
    py scripts/rankings/rankings_diff.py [snapshot_file]
    (defaults to the most recently modified rankings_snapshot_*.json in data/processed/)
"""

import json
import sqlite3
import sys
from pathlib import Path

import weights_config
from snapshot_rankings import fetch_current_rankings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "processed"

TOP_N = 15  # how many risers/fallers to show per section


def find_latest_snapshot() -> Path:
    candidates = sorted(SNAPSHOT_DIR.glob("rankings_snapshot_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise SystemExit(
            f"No snapshot files found in {SNAPSHOT_DIR} -- run snapshot_rankings.py before "
            "changing weights_config.py, then re-run scoring.py, then this script."
        )
    return candidates[-1]


def diff_weights(old_weights: dict, new_weights: dict, old_replacement: dict, new_replacement: dict) -> list[str]:
    lines = []
    for key in sorted(set(old_weights) | set(new_weights)):
        old_val, new_val = old_weights.get(key), new_weights.get(key)
        if old_val != new_val:
            lines.append(f"  WEIGHTS[{key!r}]: {old_val!r} -> {new_val!r}")
    for key in sorted(set(old_replacement) | set(new_replacement)):
        old_val, new_val = old_replacement.get(key), new_replacement.get(key)
        if old_val != new_val:
            lines.append(f"  REPLACEMENT_RANK[{key!r}]: {old_val!r} -> {new_val!r}")
    return lines


def diff_rankings(old_rankings: list[dict], new_rankings: list[dict]) -> dict:
    old_by_id = {r["gsis_id"]: r for r in old_rankings}
    new_by_id = {r["gsis_id"]: r for r in new_rankings}

    movers = []
    for gsis_id, new_r in new_by_id.items():
        old_r = old_by_id.get(gsis_id)
        if old_r is None:
            continue  # newly scored player (e.g. a rookie added since the snapshot) -- not a "mover"
        movers.append({
            "full_name": new_r["full_name"],
            "position": new_r["position"],
            "old_rank": old_r["rank"],
            "new_rank": new_r["rank"],
            "rank_delta": old_r["rank"] - new_r["rank"],  # positive = moved UP (better rank)
            "old_score": old_r["score"],
            "new_score": new_r["score"],
            "score_delta": new_r["score"] - old_r["score"],
        })

    new_players = [r["full_name"] for gsis_id, r in new_by_id.items() if gsis_id not in old_by_id]
    dropped_players = [r["full_name"] for gsis_id, r in old_by_id.items() if gsis_id not in new_by_id]

    return {"movers": movers, "new_players": new_players, "dropped_players": dropped_players}


def print_report(snapshot: dict, current_weights: dict, current_replacement: dict, diff: dict) -> None:
    print(f"Comparing against snapshot taken {snapshot['taken_at']} "
          f"(scoring_format='{snapshot['scoring_format']}')\n")

    weight_lines = diff_weights(snapshot["weights"], current_weights, snapshot["replacement_rank"], current_replacement)
    print("=== Config changes ===")
    if weight_lines:
        for line in weight_lines:
            print(line)
    else:
        print("  (no weights_config.py changes detected -- rank/score movement below is from data changes only)")

    movers = diff["movers"]
    risers = sorted(movers, key=lambda m: m["rank_delta"], reverse=True)[:TOP_N]
    fallers = sorted(movers, key=lambda m: m["rank_delta"])[:TOP_N]

    print(f"\n=== Top {TOP_N} risers (rank improved most) ===")
    for m in risers:
        if m["rank_delta"] <= 0:
            break
        print(f"  {m['full_name']:<25} {m['position']:<3} rank {m['old_rank']:>4} -> {m['new_rank']:<4} "
              f"(+{m['rank_delta']})  score {m['old_score']:.1f} -> {m['new_score']:.1f}")

    print(f"\n=== Top {TOP_N} fallers (rank dropped most) ===")
    for m in fallers:
        if m["rank_delta"] >= 0:
            break
        print(f"  {m['full_name']:<25} {m['position']:<3} rank {m['old_rank']:>4} -> {m['new_rank']:<4} "
              f"({m['rank_delta']})  score {m['old_score']:.1f} -> {m['new_score']:.1f}")

    if diff["new_players"]:
        print(f"\n=== Newly scored (weren't in the snapshot) === ({len(diff['new_players'])})")
        print("  " + ", ".join(diff["new_players"][:20]) + (" ..." if len(diff["new_players"]) > 20 else ""))

    if diff["dropped_players"]:
        print(f"\n=== No longer scored (were in the snapshot, aren't now) === ({len(diff['dropped_players'])})")
        print("  " + ", ".join(diff["dropped_players"][:20]) + (" ..." if len(diff["dropped_players"]) > 20 else ""))


def main() -> None:
    snapshot_path = Path(sys.argv[1]) if len(sys.argv) > 1 else find_latest_snapshot()
    snapshot = json.loads(snapshot_path.read_text())

    conn = sqlite3.connect(DB_PATH)
    try:
        current_rankings = fetch_current_rankings(conn, snapshot["scoring_format"])
    finally:
        conn.close()

    diff = diff_rankings(snapshot["rankings"], current_rankings)
    print_report(snapshot, weights_config.WEIGHTS, weights_config.REPLACEMENT_RANK, diff)


if __name__ == "__main__":
    main()
