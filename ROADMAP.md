# Roadmap

Kickoff: 2026-07-23. Drafts typically run late August–early September, so Phases 1-2 are timed to land before draft season. Time budget: ~3-8 hrs/week, variable (work-from-home flexibility + weekends), can flex up if it's clicking.

Each phase lists: what gets built, what you learn, and the resume/portfolio artifact it produces. Classification tags: **Must Have**, **Nice to Have**, **Future Version**, **Avoid For Now**.

---

## Phase 0 — Setup (this week, ~2026-07-23 to 07-27) — ✅ DONE (2026-07-23)

**Must Have**
- Git repo initialized, pushed to GitHub (public), `.gitignore` covering `.env`, `data/db/*.sqlite`, `__pycache__`.
- Python environment set up (venv or similar).
- Open the project folder in VS Code (Python + SQLite Viewer extensions) — this is the same folder Cowork writes to, so no syncing needed, just `File > Open Folder`.
- Request FantasyPros free API access (personal/non-commercial tier — takes a few days to get approved, so start now even though it's not used until Phase 1).
- Confirm Anthropic API key works from a script (not just chat).

**Learning focus:** git/GitHub basics refresher, Python virtual environments, reading API docs, getting comfortable running/debugging scripts in VS Code instead of only through Cowork.

---

## Phase 1 — Data Foundation (~2026-07-28 to 08-17, 2-3 weeks)

**Must Have**
- SQLite schema: players, teams, season_stats, weekly_stats, adp (see `ARCHITECTURE.md`).
- Ingest script: Sleeper API → players + team metadata (free, no auth).
- Ingest script: nfl_data_py → historical weekly/season stats (2020-2025).
- Ingest script: FantasyPros → current ADP + expert consensus rankings (once API access is approved).
- Basic data validation (row counts, null checks) — nothing fancy, just sanity checks.

**Nice to Have**
- A small CLI or notebook to query the DB and sanity-check data by eye.

**Avoid For Now**
- Any kind of scheduled/automated ingestion — run scripts manually.
- Multiple data source reconciliation logic (e.g., resolving conflicting ADP numbers) — pick one source of truth per data type for now.

**Learning focus:** `requests`, REST API pagination/rate limits, `pandas`, SQL via `sqlite3`, structuring a Python project (modules, not one giant script).

**Deliverable:** a local `fantasy_football.db` with queryable historical + current player data. This is the foundation everything else reads from — worth taking the extra time to get the schema right.

---

## Phase 2 — Rankings Engine + Cheat Sheet (~08-18 to 09-01, targeting pre-draft)

**Must Have**
- Transparent, tunable scoring formula (not ML) that blends: recent performance, ADP/expert consensus, and Andrew's own adjustable weights per stat category.
- PPR / Half-PPR toggle — one parametrized engine, not two.
- Export to a clean, shareable format (CSV → formatted spreadsheet via the xlsx skill, or a simple PDF cheat sheet).

**Must Have (refined 2026-07-23 after product discussion)**
- Two-layer design, not a flat list: an overview tab (simple ranked list + tiers, works for casual users at a glance) plus per-player detail views (color-coded yearly/weekly stats, team context, a short blurb) for anyone who wants to click deeper. Buildable in Excel now (summary tab + linked player tabs with conditional formatting) — this is the low-tech stepping stone toward the eventual UDK-style app in Phase 6.
- Positional tiers (not just a flat ranked list) — closer to what FantasyPros/@fantasyguides-style cheat sheets look like.
- A short "why" blurb per player: Andrew writes/curates blurbs himself for players he has real opinions on; for the rest, Claude drafts a blurb from the underlying stats and Andrew reviews/edits/approves before it ships. Goal is full coverage by start of season without requiring Andrew to hand-write every one — his approval is the quality gate, not the authorship.

**Nice to Have**
- Track which blurbs are "Andrew-written" vs "Claude-drafted, Andrew-approved" (even just a column/flag) — useful later for seeing which blurbs actually perform better with the audience.

**Avoid For Now**
- Machine learning projection models. A well-reasoned weighted formula is more defensible, more explainable in an interview, and faster to ship.

**Learning focus:** designing a scoring system with clear, explainable inputs; basic data viz/formatting for a polished output.

**Deliverable:** your own rankings + cheat sheet, PPR and Half-PPR, exportable and presentable. First genuinely portfolio- and possibly publish-ready artifact.

---

## Phase 3 — Weekly Research Digest + Content Ideas (season start, ~09-01 onward)

**Must Have**
- Script that pulls weekly news/injuries, summarizes with Claude, flags fantasy-relevant implications.
- Generates content ideas: short-form hooks, titles, angle suggestions (per the original brief — 10 ideas/day was the original ask; start smaller, e.g. 3-5, and expand once quality is proven).
- Run manually for the first 2-3 weeks of the season to validate output quality before automating.

**Nice to Have**
- Script outlines (not just ideas) for the strongest 1-2 ideas per run.

**Future Version**
- Automated posting/scheduling to actual platforms.

**Learning focus:** prompt engineering for structured/repeatable output, chaining API calls (news → summary → ideas), evaluating LLM output quality systematically rather than just "eyeballing it."

**Deliverable:** a working daily/weekly digest — this is what eventually becomes the scheduled task.

---

## Phase 4 — Automation (2-3 weeks into Phase 3, once validated)

**Must Have**
- Cowork scheduled task running the Phase 3 digest automatically (e.g., daily during the season).

**Learning focus:** scheduled task design, idempotency (safe to re-run), basic error handling/alerting when a run fails.

---

## Phase 5 — V2 Features (future, in-season/off-season)

**Future Version**
- ADP movement tracking over time (requires storing historical snapshots, not just current ADP).
- Reddit/social sentiment signal for sleeper/bust identification.
- Trade analyzer (compare value of two trade packages using the rankings engine).
- Multi-platform content repurposing (one digest → YouTube script + IG caption + newsletter blurb).

---

## Phase 6 — Public Product (future, once V2 is proven)

**Future Version**
- Pick a platform (or platforms) and actually start publishing.
- Explore monetization: newsletter subscriptions, affiliate links, sponsorships, possibly a paid tier for deeper rankings/tools.
- Revisit whether a public-facing site/app makes sense, vs. continuing to work through existing platforms (YouTube/IG/Substack).

This phase is intentionally light on detail — decisions here should be made with real data/rankings in hand, not guessed at now.
