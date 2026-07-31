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

## Phase 1 — Data Foundation (~2026-07-28 to 08-17, 2-3 weeks) — ✅ effectively DONE (2026-07-30, well ahead of the 08-17 target)

**Must Have**
- ✅ SQLite schema: players, teams, season_stats (view), weekly_stats, snap_counts, advanced_stats, team_stats, adp, rankings (see `ARCHITECTURE.md` and `scripts/db/schema.sql`) — done 2026-07-23.
- ✅ Ingest script: Sleeper API → players + team metadata (`scripts/ingest/sleeper.py`) — done 2026-07-23, 2,741 fantasy-relevant players loaded.
- ✅ Ingest script: historical weekly stats, 2020-2025 (`scripts/ingest/nfl_data.py`, via `nflreadpy` — switched from `nfl_data_py`, which is deprecated and missing 2025 data) — done 2026-07-24, 38,054 rows loaded across 2,638 players.
- ✅ Ingest script: FantasyPros → ADP/expert consensus (`scripts/ingest/fantasypros.py`) — built 2026-07-24, but free tier caps at 10 players, so `ffc.py` (Fantasy Football Calculator) became the primary ADP source instead; FantasyPros stays as a working backup if the paid-tier question ever resolves in its favor.
- ✅ Basic data validation (`scripts/db/validate.py`) — built 2026-07-24.

**Nice to Have**
- A small CLI or notebook to query the DB and sanity-check data by eye.

**Avoid For Now**
- Any kind of scheduled/automated ingestion — run scripts manually.
- Multiple data source reconciliation logic (e.g., resolving conflicting ADP numbers) — pick one source of truth per data type for now.

**Learning focus:** `requests`, REST API pagination/rate limits, `pandas`, SQL via `sqlite3`, structuring a Python project (modules, not one giant script).

**Deliverable:** a local `fantasy_football.db` with queryable historical + current player data. This is the foundation everything else reads from — worth taking the extra time to get the schema right.

---

## Phase 2 — Rankings Engine + Cheat Sheet (~08-18 to 09-01, targeting pre-draft) — nearly DONE as of 2026-07-30, well ahead of schedule

**Status check-in (2026-07-30):** this phase wasn't even supposed to start until 08-18 and it's nearly wrapped on 07-30 — the original Phase 1/2 date split no longer reflects how the work actually happened (in practice they overlapped). Remaining before Phase 2 is genuinely closed out:
1. RB/WR blurb pass (in progress — QB/TE done 2026-07-30, `content/blurb_worklist_v2.xlsx`).
2. Build the not-yet-built "load worklist back into `rankings.blurb`/`blurb_source`" script (matched by gsis_id, not name), run it for all four positions, regenerate `cheat_sheet.xlsx` with full blurb coverage.
3. Quick Half-PPR sanity check — the toggle is wired up in `weights_config.py` but has never actually been run and eyeballed end to end.
4. One more rankings-vs-ADP review pass (`adp_comparison.py` on real, current data) plus any `weights_config.py` adjustments that surfaces — Andrew's explicit call (2026-07-30) is to prioritize rankings accuracy before moving on, not just ship on schedule.

**Sequencing decision (2026-07-30):** once the four items above are done, move straight into Phase 3 (research digest) rather than waiting for season start as originally planned — the schedule surplus this phase created is deliberately being spent on accuracy (item 4) first, then redirected to start Phase 3 early, not spent on gold-plating Phase 2 further (e.g. extending blurb coverage past WR50/RB40, further tier-threshold tweaking) unless something in the ADP review pass specifically calls for it.

**Off-roadmap additions, queued 2026-07-31 (Claude's suggestions, Andrew agreed to all three):**
- README.md for the repo (public-facing portfolio pitch, separate from this internal docs set — see the "Git conventions" note in ARCHITECTURE.md, which already flagged this as worth doing "once Phase 2 has a real deliverable to show," which it now does) — started 2026-07-31, no dependency on anything else.
- Rankings snapshot + diff tool (`scripts/rankings/snapshot_rankings.py` + `rankings_diff.py`) — built 2026-07-31 specifically to support item 4 above (the ADP/tuning review pass): snapshot current rankings + weights before changing `weights_config.py`, then diff against the new run to see who moved and why, rather than eyeballing two full spreadsheets side by side.
- Pytest regression suite (gsis_id uniqueness, tier-boundary agreement between cheat_sheet.py/blurb_worklist.py, PPR vs Half-PPR actually differing, no orphaned rankings rows) — queued to start once RB/WR blurbs and the load-back script are done, not before. Directly ties to Andrew's QA background/career-transition goal (see CLAUDE.md) — real test-automation discipline applied to this project's own pipeline, not a generic "add tests" task.

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

**Design note (2026-07-25):** "linked player tabs" (one Excel tab per player) doesn't scale now that we have real data — 855 scored players/rookies would mean 855 tabs. Revised to: one Overview tab (all players, sortable/color-coded) plus one tab per position (QB/RB/WR/TE/K) for the drill-down experience instead. Same two-tier spirit, practical at this volume.

**Known tuning item (2026-07-25):** kickers with very few games are ranking too high relative to established kickers — small positional pool (K) makes VOR swing more easily on a hot small sample. Address during the weights-tuning pass, not now — Andrew's call was to defer, not remove kickers from rankings.

**Cheat sheet shipped (2026-07-25):** `scripts/rankings/cheat_sheet.py` — Overall + position tabs, Tier column (real score gaps, not fixed groups), 2025 season stat columns (Pass/Rush/Rec yards/TDs, Targets, Rec, R+R Yds), full AutoFilter, conditional-formatting-based zebra striping and rookie highlighting (survives sorting, unlike the static-fill version that shipped first). ADP source ended up being Fantasy Football Calculator (free, ~225 players) rather than FantasyPros (free tier caps at 10) — FantasyPros stays available as a second source if the premium tier question resolves in its favor.

**Future potential addition:** VBA macro to auto-highlight whichever column is currently sorted/filtered (Andrew's ask, 2026-07-25). Deferred — requires converting the workbook to macro-enabled `.xlsm` with the security-prompt tradeoffs that come with it. Manual click-to-select-column already works natively in Excel as a no-code stand-in.

**Avoid For Now**
- Machine learning projection models. A well-reasoned weighted formula is more defensible, more explainable in an interview, and faster to ship.

**Learning focus:** designing a scoring system with clear, explainable inputs; basic data viz/formatting for a polished output.

**Deliverable:** your own rankings + cheat sheet, PPR and Half-PPR, exportable and presentable. First genuinely portfolio- and possibly publish-ready artifact.

---

## Phase 3 — Weekly Research Digest + Content Ideas (pulled forward, Andrew's call 2026-07-30 — starts once Phase 2's close-out list above is done, not at season start as originally planned)

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
- ADP movement tracking over time — the `adp` table already stores every pull as its own snapshot (not overwritten), so this is mostly "write a comparison script," not a new data model. Andrew wants weekly re-pulls once the season approaches, specifically to catch training camp/preseason risers and fallers. Natural pairing with a Cowork scheduled task once this is validated manually a few times (per the automation-timing rule elsewhere in this doc).
- Team defenses (2026-07-26, Andrew's ask): bring DEF into the data model (currently excluded entirely, see sleeper.py/nfl_data.py notes), and once the season starts, track weekly matchup difficulty — how the opposing defense a player faces that week stacks up against QBs/RBs/WRs/TEs specifically (a "defense vs. position" signal), plus general team defensive stats. This is a real, separate data model from offensive weekly_stats (sacks/turnovers/points-allowed, not completions/carries/targets) — scope it as its own mini-project when picked up, not a quick bolt-on.
- Reddit/social sentiment signal for sleeper/bust identification.
- Trade analyzer (compare value of two trade packages using the rankings engine).
- Multi-platform content repurposing (one digest → YouTube script + IG caption + newsletter blurb).
- Handcuff rankings (2026-07-26, Andrew's idea, sparked by the ADP outlier review): rank backup RBs specifically by upside-if-the-starter-gets-hurt — factoring in the backup's own passing-game usage, the team's overall quality/pace, and how bad the starter's injury history is. A real, separate ranking dimension from the main board, not something VOR/the main formula should try to fold in.
- Situational/news context ("camp news," 2026-07-26): the ADP outlier review surfaced real cases (Tyreek Hill's situation, James Conner's backfield competition/team outlook) where the *market* has forward-looking context our stats-only formula structurally cannot have — a season's box score can't know about an offseason injury, a coaching change, or a depth-chart battle. This is NOT a decay-rate/weights fix — no amount of recency tuning solves it, since the information isn't in any historical season at all. The real fix is the Phase 3 research-digest concept (pulls current news, flags fantasy-relevant implications) feeding into the blurb layer as manual overrides/annotations, not a new scoring parameter. Sourcing decision (2026-07-28): X/Twitter's API moved to pay-per-use in 2026 with no free tier at all (even the old $200/mo Basic tier is closed to new signups) — not a good fit for automated ingestion. Free RSS feeds (RotoWire/RotoBaller injury and player-news feeds) are the better source for the automated digest; X stays useful as something Andrew personally browses for camp-reporter color that feeds his own blurb-writing, not something to build scraping infrastructure around.
- Betting markets as a signal (2026-07-28, Andrew's idea): use sportsbook lines — team win totals, game spreads/totals (implied team scoring environment), and player props (anytime TD odds, yardage overs/unders) — to help project expected season/weekly output. Markets are widely regarded as one of the sharpest available signals precisely for things our formula can't see from box scores alone (team quality, game script expectations, role certainty) — directly relevant to gaps already found (e.g. the James Conner/team-outlook case). Worth scoping as its own data source once picked up (odds APIs, which team/player, which markets to pull) rather than a quick bolt-on.
- Offensive line quality tracking (2026-07-28, Andrew's idea): track O-line rankings/quality (in-season performance metrics, or preseason projections) as a signal feeding QB and RB projections specifically — pass-block quality affects QB opportunity/sack avoidance, run-block quality affects RB efficiency directly — and eventually defense projections too, once the team-defense data model above exists (O-line quality is also a factor in the opposing side's matchup difficulty). PFF O-line grades are the standard signal here but sit behind PFF's paid tier; check free alternatives (e.g. ESPN's pass-block/run-block win rate) first. Scope as its own data source when picked up, not a quick bolt-on.
- Backtest validation (2026-07-31, Claude's suggestion, Andrew agreed): build rankings using only 2020-2024 data, then check how they'd have actually performed against real 2025 season outcomes (e.g. Spearman correlation between pre-season projected rank and actual season-end fantasy finish). This is the strongest possible answer to "why should anyone trust this formula" — directly serves the "rankings need to be genuinely defensible" goal stated elsewhere in this doc — but it's nontrivial (need a defensible scoring-of-the-scorer method, and scoring.py would need a "pretend today is August 2025" mode). Explicitly deferred: Andrew's call was not to start this until Phase 3 (research digest) is proven out, not before.

**Known minor data-quality quirk (2026-07-26):** a small number of very recent/late-round players get a synthetic (non-gsis_id) placeholder ID from nflverse-adjacent sources when they don't have an official ID assigned yet, and different sources (the ID crosswalk vs. draft picks data) can synthesize *different* placeholders for the same real person — found via "Mike Washington Jr.," who has two separate `players` rows (`WAS569019` from Sleeper's crosswalk, `WAS797326` from draft_picks.py) that are almost certainly the same guy. Doesn't affect rankings today (only the row with draft info qualifies for scoring), so not worth building entity-resolution for one player — revisit if this shows up more as more rookie classes get ingested.

---

## Phase 6 — Public Product (future, once V2 is proven)

**Future Version**
- Pick a platform (or platforms) and actually start publishing.
- Explore monetization: newsletter subscriptions, affiliate links, sponsorships, possibly a paid tier for deeper rankings/tools.
- Revisit whether a public-facing site/app makes sense, vs. continuing to work through existing platforms (YouTube/IG/Substack).

This phase is intentionally light on detail — decisions here should be made with real data/rankings in hand, not guessed at now.
