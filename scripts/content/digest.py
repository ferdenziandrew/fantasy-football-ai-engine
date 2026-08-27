"""
Weekly research digest (Phase 3): pulls recent player news from two RSS feeds, matches
items to players in our own database, and asks Claude to summarize the fantasy-relevant
takeaway and flag a direction (UP/DOWN/NEUTRAL/PENDING) plus a separate news tone for
each match.

Deliberately does NOT write to rankings.blurb automatically -- outputs a plain markdown
report to content/drafts/ for Andrew to review and manually decide what becomes a real
Note update. This matches the design already settled in ROADMAP.md: news feeds into
Notes as a human-approved layer, not a silent auto-override of Andrew-authored content.

Two sources, added together 2026-08-24 to catch up on missed preseason news faster
(both are small-rolling-window feeds, not deep archives -- so more sources = more
coverage per run, not a substitute for running this regularly):

- RotoWire (confirmed reachable/clean): title format is "Player Name: headline", a
  clean, structured split. <ttl>10</ttl> -- built for frequent polling, exposes only a
  handful of the very latest items at any moment.
- RotoBaller (`/player-news/feed`, NOT the general `/feed`, which is long-form articles,
  and NOT `/nfl/feed`, which is a dead WordPress comments feed that returns nothing --
  confirmed 2026-08-24 via direct inspection): cross-sport feed, filtered here to items
  tagged "Fantasy Football & NFL". Titles are natural-sentence headlines with the player
  name woven in ("George Kittle Still on PUP List") -- no clean separator to split on,
  so matching here works by searching for a KNOWN player's normalized full name inside
  the normalized title text instead (see match_rotoballer_items). This is a looser,
  substring-based heuristic (vs. RotoWire's exact structured match) -- full first+last
  name combinations are distinctive enough to make false positives unlikely in
  practice, but it's a real trade-off worth knowing about if an odd match shows up.
  pubDate is unreliable on this feed (empty on every item but the first one observed),
  so it's carried through for display only, not relied on for sorting/filtering.

Matching is deliberately against the FULL players table, not just players already in
our rankings table -- a player excluded from scoring (e.g. by scoring.py's
min_games_to_score filter) can still be exactly the kind of situational riser this
digest exists to catch (see the MarShawn Lloyd case logged in ROADMAP.md's handcuff-
rankings note).

v3 (2026-08-24, Andrew's ask): a persistent per-player history
(data/processed/digest_history.json) is now read before summarizing and written after,
so the digest can tell "is this genuinely new information, or an expected continuation
of something already known" -- without it, a routine practice-absence for an
already-reported injury (Ashton Jeanty) read identically to fresh bad news. Design:
  - Each player's last few entries (date, impact, tone, summary) are fed back into the
    Claude prompt, with explicit instruction to treat a mere continuation as NEUTRAL,
    not re-trigger the same UP/DOWN.
  - A LONG_TERM flag (season-ending injury / IR / 4+ week absence) exempts a player's
    history from the normal 3-week aging-out window -- Andrew's catch: a flat time-based
    expiry would forget an out-for-season player and treat his eventual return as a
    surprise. The flag is re-derived from the LATEST classification each run, so it
    clears itself automatically once news no longer indicates long-term status (e.g. he
    returns to practice) -- no separate reset logic needed.
  - PENDING items are reminded ONCE PER CALENDAR DAY (tracked via
    last_pending_alert_date), not on every run, since Andrew's planned run cadence
    (~3x/day now, possibly ~every 10 min later) would otherwise repeat the same
    reminder many times in one day.
  - The report only gets WRITTEN if something actually changed (a player's impact/tone
    differs from their last known status, or they're new) or there's a same-day-unseen
    pending reminder -- a run that finds nothing new writes nothing, per Andrew's
    "notify me on changes" ask, rather than a repetitive file every run.

v4 (2026-08-25, real-run calibration): two prompt refinements from a second live run --
a veteran starter resting in a PRESEASON GAME (not practice, not injury-related) is
routine and should read NEUTRAL, not DOWN (caught on Josh Allen); an undiagnosed
"being looked at by trainers"-type report should get PENDING, not a premature DOWN,
since the actual severity isn't known yet (caught on Brian Thomas Jr.). Not addressed
here, logged in ROADMAP.md instead as its own feature: cross-player ripple effects
(e.g. Kirk Cousins being the Week 1 starter should inform how to read news about his
own pass-catchers; Ashton Jeanty's injury should flag Mike Washington's snaps as more
relevant) -- this needs real depth-chart/relationship data the digest doesn't have
yet, not a prompt tweak.

v5 (2026-08-25, same-day follow-up): two more refinements from a third live run --
(1) the PRESEASON-GAME guidance from v4 was too blunt (blanket "not a signal"). Andrew's
counter-example: JaDarian Price being deliberately shut down for the last two preseason
games with "we've seen enough" framing IS a real signal (usually UP -- it means the
team has already decided in his favor), unlike a settled veteran starter just resting.
The real test is WHY a player didn't play, not whether it was a preseason game.
(2) `append_validation_log()` writes every reported entry to a persistent CSV
(data/processed/digest_validation_log.csv, one growing file, not one per day) with
blank `correct` and `andrew_notes` columns -- built because Andrew was validating
classifications by narrating them back in chat one at a time, which doesn't scale and
wasn't captured anywhere durable. This becomes a real labeled dataset over time.
Also: the terminal's "Summarizing" line now shows (TEAM-POSITION) per player, since a
bare name wasn't always enough to place who was being discussed.

v6 (2026-08-25, same-day follow-up #2): Andrew's ask -- he wants final say on the
IMPACT/TONE classification, not just a passive log of what the AI decided (right now a
wrong AI call would silently keep feeding "prior status" to future runs uncorrected).
Added two more columns to the validation log -- `override_impact` and `override_tone`
-- and a companion script, apply_validation_overrides.py, that patches
digest_history.json to match Andrew's correction once filled in. The AI still proposes
fast (handles the volume), but Andrew's correction is what actually sticks and feeds
forward, not the AI's original call, once he's reviewed it.

v7 (2026-08-25, first real override review): Andrew's first full validation pass
corrected 7 of 12 overridden entries from the SAME pattern -- a single positive camp
report (Gainwell, Skattebo, Sarratt, Williams, Adams, Hurst, Tuten) had been flagged UP
off one good report, when it should stay NEUTRAL until corroborated. Added explicit
guidance: don't flag UP off a single camp/practice report, wait for a 2nd/3rd
consecutive positive report or something more concrete (depth chart listing, real
usage numbers, a coach naming a starter, a contract/trade).

Run manually for now -- no scheduling yet, per the project's automation-timing rule
(hold off until output quality is validated over a few real runs). Two daily reminders
(11:50am, 5:30pm) are scheduled as of 2026-08-25 to build the habit -- reminders only,
not automated runs, per the same rule.

Usage:
    py scripts/content/digest.py
"""

import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from anthropic import Anthropic
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "db" / "fantasy_football.db"
OUTPUT_DIR = PROJECT_ROOT / "content" / "drafts"
HISTORY_PATH = PROJECT_ROOT / "data" / "processed" / "digest_history.json"
VALIDATION_LOG_PATH = PROJECT_ROOT / "data" / "processed" / "digest_validation_log.xlsx"

# Reuse the ingest layer's proven name-matching logic rather than duplicating it.
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "ingest"))
from ffc import normalize_name  # noqa: E402

ROTOWIRE_FEED_URL = "https://www.rotowire.com/rss/news.php?sport=NFL"
ROTOBALLER_FEED_URL = "https://www.rotoballer.com/player-news/feed"
ROTOBALLER_CATEGORY_MARKER = "fantasy football"  # case-insensitive substring match against item categories
CLAUDE_MODEL = "claude-haiku-4-5-20251001"  # fast/cheap -- lightweight summarization, not deep analysis

# IMPACT (does this change fantasy value) and TONE (how the story itself is framed) are
# two separate flags -- e.g. Justin Jefferson being excited about his new QB is clearly
# POSITIVE tone but NEUTRAL impact (he's elite regardless). PENDING is a real 4th impact
# value, not a NEUTRAL synonym -- for news that's genuinely too early to call.
IMPACT_ORDER = {"UP": 0, "DOWN": 1, "PENDING": 2, "NEUTRAL": 3}
IMPACT_ARROWS = {"UP": "^", "DOWN": "v", "PENDING": "?", "NEUTRAL": "-"}

HISTORY_MAX_AGE_DAYS = 21  # 3 weeks -- Andrew's call, 2026-08-24
HISTORY_ENTRY_CAP = 5
LONG_TERM_ENTRY_CAP = 10  # more room for players we're actively watching through a long absence


def fetch_rotowire_items() -> list[dict]:
    """RotoWire's title format is "Player Name: headline" -- items that don't match
    that shape (rare -- e.g. team-level news with no single player) are skipped rather
    than guessed at."""
    resp = requests.get(ROTOWIRE_FEED_URL, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if ":" not in title:
            continue
        player_name, headline = title.split(":", 1)
        items.append({
            "player_name": player_name.strip(),
            "headline": headline.strip(),
            "description": (item.findtext("description") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "pub_date": (item.findtext("pubDate") or "").strip(),
        })
    return items


def fetch_rotoballer_items() -> list[dict]:
    """Cross-sport feed -- filtered here to items with a football-relevant category tag
    (see module docstring for why /player-news/feed specifically, not /feed or
    /nfl/feed). No player-name field or clean title separator, so player_name isn't
    extracted here -- match_rotoballer_items() searches the raw headline text directly
    instead."""
    resp = requests.get(ROTOBALLER_FEED_URL, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    items = []
    for item in root.findall(".//item"):
        categories = [c.text or "" for c in item.findall("category")]
        if not any(ROTOBALLER_CATEGORY_MARKER in c.lower() for c in categories):
            continue
        items.append({
            "headline": (item.findtext("title") or "").strip(),
            "description": (item.findtext("description") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "pub_date": (item.findtext("pubDate") or "").strip(),
        })
    return items


def build_name_lookup(conn: sqlite3.Connection) -> dict:
    """normalized_name -> [(gsis_id, full_name, position, current_team), ...]. Matches
    against the FULL players table, not just currently-ranked players -- see module
    docstring. current_team included so the report can show it."""
    rows = conn.execute("SELECT gsis_id, full_name, position, current_team FROM players").fetchall()
    lookup: dict = {}
    for gsis_id, full_name, position, current_team in rows:
        key = normalize_name(full_name)
        lookup.setdefault(key, []).append((gsis_id, full_name, position, current_team))
    return lookup


def match_rotowire_items(items: list[dict], name_lookup: dict) -> list[dict]:
    matched = []
    unmatched_count = 0
    for item in items:
        key = normalize_name(item["player_name"])
        candidates = name_lookup.get(key)
        if not candidates:
            unmatched_count += 1
            continue
        if len(candidates) > 1:
            # Ambiguous (rare -- two same-named players). Take the first rather than
            # guess further, same pragmatic call ffc.py makes for genuine ambiguity.
            candidates = candidates[:1]
        gsis_id, full_name, position, current_team = candidates[0]
        matched.append({**item, "gsis_id": gsis_id, "full_name": full_name, "position": position,
                         "team": current_team, "source": "rotowire"})

    print(f"  RotoWire: {len(matched)} matched, {unmatched_count} unmatched "
          f"(coaches, team-level news, non-fantasy-relevant players -- expected, not an error)")
    return matched


def match_rotoballer_items(items: list[dict], name_lookup: dict) -> list[dict]:
    """No clean player-name field on this feed (see module docstring) -- searches for
    each known player's normalized full name as a substring of the normalized headline
    instead. Only checks the headline, not the longer description -- headlines
    consistently lead with the player's name in the examples inspected, and searching
    the full description too would raise the false-positive risk (a name mentioned in
    passing, not the item's actual subject) for little added coverage."""
    matched = []
    unmatched_count = 0
    for item in items:
        normalized_headline = normalize_name(item["headline"])
        found = None
        for normalized_name, candidates in name_lookup.items():
            if normalized_name and normalized_name in normalized_headline:
                found = candidates[0]  # same ambiguity call as RotoWire's matcher
                break
        if not found:
            unmatched_count += 1
            continue
        gsis_id, full_name, position, current_team = found
        matched.append({**item, "gsis_id": gsis_id, "full_name": full_name, "position": position,
                         "team": current_team, "source": "rotoballer"})

    print(f"  RotoBaller: {len(matched)} matched, {unmatched_count} unmatched "
          f"(coaches, team-level news, non-fantasy-relevant players -- expected, not an error)")
    return matched


def group_by_player(matched: list[dict]) -> list[dict]:
    """Merges multiple items about the SAME player (often the same underlying event
    reported by both outlets) into one group, so Claude sees all of it and writes ONE
    synthesized summary instead of near-identical duplicate entries. Order in the input
    list is preserved for the first occurrence of each player."""
    groups: dict = {}
    order: list = []
    for item in matched:
        gsis_id = item["gsis_id"]
        if gsis_id not in groups:
            groups[gsis_id] = {
                "gsis_id": gsis_id, "full_name": item["full_name"], "position": item["position"],
                "team": item["team"], "items": [],
            }
            order.append(gsis_id)
        groups[gsis_id]["items"].append({
            "headline": item["headline"], "description": item["description"],
            "link": item["link"], "source": item["source"],
        })
    return [groups[gsis_id] for gsis_id in order]


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    return json.loads(HISTORY_PATH.read_text())


def save_history(history: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2))


def prune_history(history: dict, today: date) -> dict:
    """Drops a player entirely once their most recent entry is older than
    HISTORY_MAX_AGE_DAYS -- UNLESS their latest entry was flagged long_term (season-
    ending injury/IR/4+ week absence), in which case they're kept indefinitely (with a
    larger entry cap) until a future update's classification clears the flag on its
    own. See module docstring for why a flat time-based expiry isn't enough here."""
    pruned = {}
    for gsis_id, record in history.items():
        entries = record.get("entries", [])
        if not entries:
            continue
        is_long_term = entries[-1].get("long_term", False)
        if not is_long_term:
            last_date = date.fromisoformat(entries[-1]["date"])
            if (today - last_date).days > HISTORY_MAX_AGE_DAYS:
                continue
        cap = LONG_TERM_ENTRY_CAP if is_long_term else HISTORY_ENTRY_CAP
        record["entries"] = entries[-cap:]
        pruned[gsis_id] = record
    return pruned


def format_history_for_prompt(prior_entries: list[dict]) -> str:
    if not prior_entries:
        return "No prior history for this player -- this is the first time we've seen news about them."
    lines = ["Prior known status (most recent last):"]
    for e in prior_entries:
        lines.append(f"  {e['date']}: impact={e['impact']}, tone={e['tone']} -- {e['summary']}")
    return "\n".join(lines)


def summarize_with_claude(client: Anthropic, group: dict, prior_entries: list[dict]) -> dict:
    """One call per PLAYER (a group may bundle multiple items from different sources
    reporting the same story), not one call per raw item. Now also passes prior history
    so Claude can judge whether this is genuinely new or an expected continuation."""
    items_text = "\n\n".join(
        f"[{i}] ({it['source']}) {it['headline']}\n{it['description']}"
        for i, it in enumerate(group["items"], start=1)
    )
    multiple_note = (
        " These are multiple reports of the same underlying story -- synthesize them "
        "into ONE summary, don't just restate one and ignore the rest."
        if len(group["items"]) > 1 else ""
    )
    history_text = format_history_for_prompt(prior_entries)

    prompt = (
        f"You're a fantasy football analyst. Given the following news about {group['full_name']} "
        f"({group['position']}, {group['team'] or 'no current team'}), write:\n"
        f"1. A one-sentence fantasy-relevant summary (what a fantasy manager needs to know).{multiple_note}\n"
        f"2. A news tone flag: POSITIVE, NEGATIVE, or NEUTRAL -- how the story itself is framed, "
        f"independent of whether it actually changes his fantasy value.\n"
        f"3. A ranking impact flag: UP, DOWN, NEUTRAL, or PENDING -- does this actually change his "
        f"fantasy value. Positive news doesn't always mean UP (e.g. a good quote about a player who's "
        f"already a clear starter is POSITIVE tone but NEUTRAL impact). A SINGLE positive camp/practice "
        f"report (flashing potential, impressing in a joint practice, one good outing) is NOT enough on its "
        f"own to flag UP -- that's noise until it's corroborated. Check the prior status below: if this is "
        f"the first report of this kind for this player, impact should be NEUTRAL even with POSITIVE tone; "
        f"only flag UP once there's a pattern -- e.g. this is the 2nd or 3rd consecutive positive report, or "
        f"something more concrete than camp buzz (a depth chart listing, a snap-count/target-share number, "
        f"a coach naming him the starter, a contract/trade). PRESEASON GAME participation needs "
        f"judgment, not a blanket rule -- a clear veteran starter resting in a preseason game is routine, "
        f"NEUTRAL, not a signal either way. But a roster-bubble/competition player being deliberately held "
        f"out with language like 'they've seen enough' or 'earned a roster spot' IS a real signal (usually "
        f"UP -- it implies the team has already decided in his favor) -- the distinguishing question is "
        f"WHY he didn't play: standard rest for someone whose role is already settled = no signal; a "
        f"decision reflecting the team's actual evaluation of a player whose role is still being decided = "
        f"real signal. Use PENDING, not a premature DOWN, when something concerning is reported but "
        f"genuinely undiagnosed yet -- e.g. 'being looked at by trainers' or 'left with an issue' with no "
        f"diagnosis or missed-time estimate given. Don't assume worst case; wait for the actual diagnosis "
        f"before committing to DOWN. IMPORTANT: check the prior status below first -- if this news is just "
        f"an expected continuation of something already known (e.g. a routine practice absence for an "
        f"injury already reported as DOWN), the impact should usually be NEUTRAL, not a repeat of the same "
        f"UP/DOWN. Only flag a new UP/DOWN if something has genuinely changed or escalated since the prior "
        f"status.\n"
        f"4. A long-term flag: YES if this news indicates a season-ending injury, IR placement, or an "
        f"absence of 4+ weeks; NO otherwise.\n\n"
        f"{history_text}\n\n"
        f"News:\n{items_text}\n\n"
        f"Respond in exactly this format:\n"
        f"SUMMARY: <one sentence>\n"
        f"TONE: <POSITIVE, NEGATIVE, or NEUTRAL>\n"
        f"IMPACT: <UP, DOWN, NEUTRAL, or PENDING>\n"
        f"LONG_TERM: <YES or NO>"
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=250,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_claude_response(group, response.content[0].text)


def parse_claude_response(group: dict, text: str) -> dict:
    """Split out so the parsing logic can be tested without a real API call."""
    summary, tone, impact, long_term = "", "NEUTRAL", "NEUTRAL", False
    for line in text.splitlines():
        if line.startswith("SUMMARY:"):
            summary = line[len("SUMMARY:"):].strip()
        elif line.startswith("TONE:"):
            tone = line[len("TONE:"):].strip().upper()
        elif line.startswith("IMPACT:"):
            impact = line[len("IMPACT:"):].strip().upper()
        elif line.startswith("LONG_TERM:"):
            long_term = line[len("LONG_TERM:"):].strip().upper() == "YES"
    return {**group, "summary": summary or text.strip(), "tone": tone, "impact": impact, "long_term": long_term}


def is_change(result: dict, history: dict) -> bool:
    """A player counts as "changed" if this is the first time we've seen them, or their
    impact/tone differs from their most recently recorded status. Used to decide what
    goes in the report -- a run where nothing changed writes nothing (see module
    docstring, Andrew's "notify me on changes" ask)."""
    prior_entries = history.get(result["gsis_id"], {}).get("entries", [])
    if not prior_entries:
        return True
    last = prior_entries[-1]
    return last["impact"] != result["impact"] or last["tone"] != result["tone"]


def update_history(history: dict, results: list[dict], today_str: str) -> dict:
    """Records every result (not just changes) so last-seen dates stay accurate even
    for unchanged/confirmed statuses."""
    for r in results:
        gsis_id = r["gsis_id"]
        record = history.setdefault(gsis_id, {
            "full_name": r["full_name"], "position": r["position"], "team": r["team"],
            "last_pending_alert_date": None, "entries": [],
        })
        record["full_name"] = r["full_name"]
        record["position"] = r["position"]
        record["team"] = r["team"]
        record["entries"].append({
            "date": today_str, "impact": r["impact"], "tone": r["tone"],
            "summary": r["summary"], "long_term": r.get("long_term", False),
        })
    return history


def get_pending_reminders(history: dict, today_str: str) -> list[dict]:
    """Players whose latest known status is PENDING and haven't already been reminded
    today -- mutates last_pending_alert_date in history as a side effect (caller must
    save_history() afterward). Once per calendar day, not once per run -- see module
    docstring on why (Andrew's planned run cadence would otherwise repeat this many
    times in one day)."""
    reminders = []
    for gsis_id, record in history.items():
        entries = record.get("entries", [])
        if not entries or entries[-1]["impact"] != "PENDING":
            continue
        if record.get("last_pending_alert_date") == today_str:
            continue
        reminders.append({
            "gsis_id": gsis_id, "full_name": record["full_name"], "position": record["position"],
            "team": record["team"], "summary": entries[-1]["summary"], "since_date": entries[-1]["date"],
        })
        record["last_pending_alert_date"] = today_str
    return reminders


def write_report(changes: list[dict], pending_reminders: list[dict], date_str: str) -> Path | None:
    if not changes and not pending_reminders:
        return None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"digest_{date_str}.md"

    lines = [f"# Research Digest -- {date_str}", ""]

    if changes:
        changes = sorted(changes, key=lambda r: IMPACT_ORDER.get(r["impact"], 4))
        source_counts: dict = {}
        for r in changes:
            for it in r["items"]:
                source_counts[it["source"]] = source_counts.get(it["source"], 0) + 1
        source_summary = ", ".join(f"{count} from {source}" for source, count in source_counts.items())
        lines.append(f"## What's new ({len(changes)} players, {sum(source_counts.values())} items: {source_summary})")
        lines.append("")
        for r in changes:
            arrow = IMPACT_ARROWS.get(r["impact"], "?")
            team = r["team"] or "no current team"
            long_term_tag = " [long-term]" if r.get("long_term") else ""
            lines.append(f"### [{arrow}] {r['full_name']} ({r['position']}, {team}) -- "
                         f"Impact: {r['impact']} | Tone: {r['tone']}{long_term_tag}")
            lines.append(r["summary"])
            source_links = ", ".join(f"[*{it['headline']}*]({it['link']}) ({it['source']})" for it in r["items"])
            lines.append(f"Sources: {source_links}")
            lines.append("")

    if pending_reminders:
        lines.append("## Still pending from earlier")
        lines.append("")
        for p in pending_reminders:
            team = p["team"] or "no current team"
            lines.append(f"- **{p['full_name']}** ({p['position']}, {team}) -- "
                         f"pending since {p['since_date']}: {p['summary']}")
        lines.append("")

    out_path.write_text("\n".join(lines))
    return out_path


VALIDATION_LOG_FIELDNAMES = [
    "date", "player", "position", "team", "impact", "tone", "long_term",
    "summary", "headlines", "correct", "andrew_notes", "override_impact", "override_tone",
]

# Andrew's preferred column widths (2026-08-25 ask, tightened further 2026-08-26 so
# override_impact/override_tone are visible without scrolling) -- re-applied on every
# write so they're always right when he opens the file, not something to redo by hand
# each time. Units are openpyxl's "characters" width, same scale Excel itself uses.
VALIDATION_LOG_COLUMN_WIDTHS = {
    "date": 12, "player": 12, "position": 5, "team": 5, "impact": 9, "tone": 8,
    "long_term": 7, "summary": 20, "headlines": 55, "correct": 6,
    "andrew_notes": 45, "override_impact": 14, "override_tone": 12,
}


def append_validation_log(changes: list[dict], pending_reminders: list[dict], date_str: str) -> int:
    """Appends every reported entry to a persistent Excel workbook
    (data/processed/digest_validation_log.xlsx) for Andrew to review after reading the
    markdown report. Columns beyond the core data are all his to fill in: `correct`
    (Y/N), `andrew_notes` (free text), and `override_impact` / `override_tone` -- if the
    AI's call was wrong, filling in an override here and running
    apply_validation_overrides.py patches that player's actual recorded status in
    digest_history.json, so the CORRECTED value (not the AI's original wrong one) is
    what feeds into future runs' "prior status" context. Andrew's ask 2026-08-25: he
    wants final say on IMPACT/TONE, not just a passive log of what the AI decided.

    v8 (2026-08-25, same-day format switch): originally a plain CSV, but CSV has no way
    to store column widths -- Andrew was manually re-widening the same 4 columns every
    time he opened it, and separately Excel silently reformatted the date column
    (2026-08-25 -> 8/25/2026) on save, which broke apply_validation_overrides.py's date
    matching entirely. Switched to .xlsx (openpyxl, already a project dependency) which
    solves both: column widths persist in the file itself and get re-applied on every
    write, and the date column is written as a real Excel date type + explicit
    YYYY-MM-DD number format instead of a string Excel is free to reinterpret.

    Built 2026-08-25: Andrew was validating classifications by narrating them back in
    chat one at a time, which doesn't scale and isn't captured anywhere durable (the
    history file records what the digest DECIDED, not whether Andrew thought that
    decision was right). This grows into a real labeled dataset over time -- e.g.
    "what fraction of PENDING calls were actually correct" becomes an answerable
    question once there's enough of this, not just a vibe. Appends across runs into
    ONE file (not one file per day) specifically so it accumulates into something
    analyzable, rather than being scattered across many small files."""
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import PatternFill

    # Light grey fill for "(reminder)" rows -- visually distinct from a real, actionable
    # entry so an override doesn't accidentally land on a reminder row instead of the
    # original entry it's re-surfacing (a reminder row is skipped entirely by
    # apply_validation_overrides.py -- see that script's docstring -- so an override
    # placed there silently does nothing). Added 2026-08-27 after this happened for
    # real: Malik Nabers' override was placed on his 8/27 reminder row instead of his
    # original 8/26 entry.
    REMINDER_FILL = PatternFill(start_color="EDEDED", end_color="EDEDED", fill_type="solid")

    rows = []
    for r in changes:
        headlines = " / ".join(it["headline"] for it in r["items"])
        rows.append({
            "date": date_str, "player": r["full_name"], "position": r["position"],
            "team": r["team"] or "", "impact": r["impact"], "tone": r["tone"],
            "long_term": r.get("long_term", False), "summary": r["summary"],
            "headlines": headlines, "correct": "", "andrew_notes": "",
            "override_impact": "", "override_tone": "",
        })
    for p in pending_reminders:
        # "(pending since <date>)" is appended directly to the summary text rather
        # than living in its own column -- Andrew's call, 2026-08-26: a whole extra
        # column ate screen space just for a fact that only applies to reminder rows.
        # The since_date itself is computed by get_pending_reminders(), same as before.
        summary_with_since = f"{p['summary']} (pending since {p['since_date']})"
        rows.append({
            "date": date_str, "player": p["full_name"], "position": p["position"],
            "team": p["team"] or "", "impact": "PENDING (reminder)", "tone": "",
            "long_term": "", "summary": summary_with_since, "headlines": "", "correct": "", "andrew_notes": "",
            "override_impact": "", "override_tone": "",
        })

    if not rows:
        return 0

    VALIDATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if VALIDATION_LOG_PATH.exists():
        wb = load_workbook(VALIDATION_LOG_PATH)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.append(VALIDATION_LOG_FIELDNAMES)

    for r in rows:
        row_values = [r[field] for field in VALIDATION_LOG_FIELDNAMES]
        ws.append(row_values)
        # Write date as a real date type (not the string) so Excel can't silently
        # reformat it into something apply_validation_overrides.py can't parse.
        date_cell = ws.cell(row=ws.max_row, column=VALIDATION_LOG_FIELDNAMES.index("date") + 1)
        date_cell.value = date.fromisoformat(r["date"])
        date_cell.number_format = "YYYY-MM-DD"
        if "reminder" in str(r["impact"]).lower():
            for c in range(1, len(VALIDATION_LOG_FIELDNAMES) + 1):
                ws.cell(row=ws.max_row, column=c).fill = REMINDER_FILL

    for i, field in enumerate(VALIDATION_LOG_FIELDNAMES, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = VALIDATION_LOG_COLUMN_WIDTHS[field]
    ws.freeze_panes = "A2"  # keep the header row visible while scrolling -- Andrew's ask, 2026-08-25

    # AutoFilter dropdowns on every column (Andrew's ask, 2026-08-26) -- lets him filter
    # `impact` down to just "PENDING"/"PENDING (reminder)" to see what still needs a
    # verdict, filter `player` to jump straight to one name, or filter to a specific
    # UP/DOWN/NEUTRAL to spot-check a category, instead of scrolling the whole sheet.
    # Re-applied on every write (like the column widths/freeze pane above) so it always
    # covers the full current row range, not just whatever it was when the file was
    # first created.
    last_col_letter = ws.cell(row=1, column=len(VALIDATION_LOG_FIELDNAMES)).column_letter
    ws.auto_filter.ref = f"A1:{last_col_letter}{ws.max_row}"

    wb.save(VALIDATION_LOG_PATH)
    return len(rows)


def main() -> None:
    load_dotenv()
    today = datetime.now(timezone.utc).date()
    today_str = today.isoformat()

    conn = sqlite3.connect(DB_PATH)
    try:
        name_lookup = build_name_lookup(conn)
    finally:
        conn.close()

    history = prune_history(load_history(), today)

    print("Fetching RotoWire NFL news feed...")
    rotowire_items = fetch_rotowire_items()
    print(f"  {len(rotowire_items)} items in feed")

    print("Fetching RotoBaller player-news feed...")
    rotoballer_items = fetch_rotoballer_items()
    print(f"  {len(rotoballer_items)} football-tagged items in feed")

    print("Matching items to known players...")
    matched = match_rotowire_items(rotowire_items, name_lookup)
    matched += match_rotoballer_items(rotoballer_items, name_lookup)

    if not matched:
        print("No items matched a known player -- nothing to summarize.")
        save_history(history)  # still persist any pruning that happened above
        return

    groups = group_by_player(matched)
    merged_count = len(matched) - len(groups)
    if merged_count:
        print(f"  Merged {merged_count} duplicate item(s) reporting the same player from multiple sources")

    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment (loaded above via .env)
    results = []
    for group in groups:
        sources = ", ".join(it["source"] for it in group["items"])
        headlines = " / ".join(it["headline"] for it in group["items"])
        team_tag = group["team"] or "FA"
        print(f"  Summarizing ({sources}): {group['full_name']} ({team_tag}-{group['position']}) -- {headlines}")
        prior_entries = history.get(group["gsis_id"], {}).get("entries", [])
        results.append(summarize_with_claude(client, group, prior_entries))

    changes = [r for r in results if is_change(r, history)]
    print(f"  {len(changes)} of {len(results)} are new/changed since last known status")

    history = update_history(history, results, today_str)
    pending_reminders = get_pending_reminders(history, today_str)
    save_history(history)

    out_path = write_report(changes, pending_reminders, today_str)
    if out_path:
        print(f"\nWrote report to {out_path}")
    else:
        print("\nNothing new to report (no changes, no unreminded pending items) -- no file written.")

    logged_count = append_validation_log(changes, pending_reminders, today_str)
    if logged_count:
        print(f"Logged {logged_count} entries to {VALIDATION_LOG_PATH} for review "
              f"(fill in the 'correct' and 'andrew_notes' columns after reading the report)")


if __name__ == "__main__":
    main()
