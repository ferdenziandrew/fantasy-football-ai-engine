"""
Pulls current ADP from Fantasy Football Calculator (FFC) and inserts it into the adp
table, source='ffc'.

Free, no API key required, no truncation (returned 225 players in testing, vs.
FantasyPros' free-tier cap of 10). Data comes from FFC's own free mock draft platform
-- human-only picks aggregated over a rolling window (494 drafts, one week, as of
2026-07-24) -- which is a different (and arguably noisier, given it's mock drafts, not
real high-stakes leagues) methodology than FantasyPros' 130+-expert consensus, but
still a legitimate, widely-used ADP source and the only free one with real coverage.

FantasyPros stays as a separate, still-working source (see fantasypros.py) -- both
write to the same adp table under different `source` values, so switching back or
using both is just a matter of which script you run, not a rebuild.

Matching note: FFC's player_id isn't part of the nflverse ID crosswalk our players
table uses, so there's no clean ID join here -- matching is done by normalized name
(lowercased, suffixes/punctuation stripped), with position used as a tiebreaker when
two players share a normalized name. Defenses (FFC labels these as position "DEF",
e.g. "Seattle Defense") won't match anything, since our players table doesn't include
team defenses at all (see sleeper.py) -- expected, not a bug.

Usage:
    py scripts/ingest/ffc.py
"""

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"

URL = "https://fantasyfootballcalculator.com/api/v1/adp/ppr"
YEAR = 2026

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
# FFC labels kickers "PK"; our schema (via Sleeper) uses "K"
POSITION_ALIASES = {"PK": "K"}


def normalize_name(name: str) -> str:
    """Lowercases, strips periods/apostrophes, and drops suffixes (Jr./Sr./II/III/IV/V)
    so e.g. "Michael Pittman Jr." and "Michael Pittman" match, and "Ja'Marr Chase"
    matches regardless of apostrophe handling on either side."""
    name = name.lower().replace(".", "").replace("'", "")
    words = [w for w in name.split() if w not in SUFFIXES]
    return " ".join(words)


def fetch_adp() -> list[dict]:
    resp = requests.get(URL, params={"teams": 12, "year": YEAR}, timeout=30)
    resp.raise_for_status()
    return resp.json()["players"]


def build_name_lookup(conn: sqlite3.Connection) -> dict:
    """Returns {normalized_name: [(gsis_id, position), ...]} -- a list per name since
    normalized names aren't guaranteed unique (rare, but two same-named players at
    different positions is possible)."""
    rows = conn.execute("SELECT gsis_id, full_name, position FROM players").fetchall()
    lookup: dict = {}
    for gsis_id, full_name, position in rows:
        key = normalize_name(full_name)
        lookup.setdefault(key, []).append((gsis_id, position))
    return lookup


def build_adp_rows(players: list[dict], name_lookup: dict, pulled_at: str) -> tuple[list[dict], dict]:
    """Returns (rows_to_insert, counts) where counts tracks matched/unmatched/ambiguous
    for visibility into match quality."""
    rows = []
    counts = {"matched": 0, "unmatched": 0, "ambiguous": 0}

    for p in players:
        key = normalize_name(p["name"])
        candidates = name_lookup.get(key, [])
        ffc_position = POSITION_ALIASES.get(p["position"], p["position"])

        if not candidates:
            counts["unmatched"] += 1
            continue

        if len(candidates) > 1:
            # disambiguate by position if possible
            position_matches = [c for c in candidates if c[1] == ffc_position]
            if len(position_matches) == 1:
                candidates = position_matches
            else:
                counts["ambiguous"] += 1
                continue

        gsis_id, _position = candidates[0]
        counts["matched"] += 1
        rows.append({
            "gsis_id": gsis_id,
            "source": "ffc",
            "adp": float(p["adp"]),
            "pulled_at": pulled_at,
        })

    return rows, counts


def insert_adp(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        "INSERT INTO adp (gsis_id, source, adp, pulled_at) VALUES (:gsis_id, :source, :adp, :pulled_at)",
        rows,
    )


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        name_lookup = build_name_lookup(conn)
        print(f"{len(name_lookup)} distinct normalized names in players")

        players = fetch_adp()
        print(f"{len(players)} players returned from Fantasy Football Calculator")

        pulled_at = datetime.now(timezone.utc).isoformat()
        rows, counts = build_adp_rows(players, name_lookup, pulled_at)
        print(f"  matched: {counts['matched']}  unmatched: {counts['unmatched']}  ambiguous: {counts['ambiguous']}")

        insert_adp(conn, rows)
        conn.commit()
    finally:
        conn.close()

    print("Done.")


if __name__ == "__main__":
    main()
