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
1. ✅ RB/WR Notes pass — done 2026-07-31, `content/blurb_worklist.xlsx` (QB/TE) + `content/blurb_worklist_rbwr.xlsx` (RB/WR).
2. ✅ Load worklist Notes back into `rankings.blurb`/`blurb_source` (`scripts/rankings/load_blurbs.py`, matched by gsis_id) — done 2026-07-31, 94 players covered. `cheat_sheet.xlsx` regenerated with full Notes coverage.
3. Quick Half-PPR sanity check — the toggle is wired up in `weights_config.py` but has never actually been run and eyeballed end to end.
4. One more rankings-vs-ADP review pass (`adp_comparison.py` on real, current data) plus any `weights_config.py` adjustments that surfaces — Andrew's explicit call (2026-07-30) is to prioritize rankings accuracy before moving on, not just ship on schedule.

**Sequencing decision (2026-07-30):** once the four items above are done, move straight into Phase 3 (research digest) rather than waiting for season start as originally planned — the schedule surplus this phase created is deliberately being spent on accuracy (item 4) first, then redirected to start Phase 3 early, not spent on gold-plating Phase 2 further (e.g. extending blurb coverage past WR50/RB40, further tier-threshold tweaking) unless something in the ADP review pass specifically calls for it.

**Off-roadmap additions, queued 2026-07-31 (Claude's suggestions, Andrew agreed to all three):**
- README.md for the repo (public-facing portfolio pitch, separate from this internal docs set — see the "Git conventions" note in ARCHITECTURE.md, which already flagged this as worth doing "once Phase 2 has a real deliverable to show," which it now does) — started 2026-07-31, no dependency on anything else.
- Rankings snapshot + diff tool (`scripts/rankings/snapshot_rankings.py` + `rankings_diff.py`) — built 2026-07-31 specifically to support item 4 above (the ADP/tuning review pass): snapshot current rankings + weights before changing `weights_config.py`, then diff against the new run to see who moved and why, rather than eyeballing two full spreadsheets side by side.
- Pytest regression suite (gsis_id uniqueness, tier-boundary agreement between cheat_sheet.py/blurb_worklist.py, PPR vs Half-PPR actually differing, no orphaned rankings rows) — RB/WR Notes and the load-back script are now done, so this is unblocked; not started yet. Directly ties to Andrew's QA background/career-transition goal (see CLAUDE.md) — real test-automation discipline applied to this project's own pipeline, not a generic "add tests" task.
- Terminology (2026-07-31, Andrew's call): the player "why" write-ups are called **Notes** in conversation and docs going forward, not "blurbs" — simpler, more professional, more straightforward. The underlying DB column (`rankings.blurb`/`blurb_source`) and file names (`blurb_worklist.py`, `load_blurbs.py`) keep their existing names deliberately — renaming those touches live code and data for a cosmetic-only win, so it's just the human-facing language that changed, not the internal plumbing.

**Must Have**
- Transparent, tunable scoring formula (not ML) that blends: recent performance, ADP/expert consensus, and Andrew's own adjustable weights per stat category.
- PPR / Half-PPR toggle — one parametrized engine, not two.
- Export to a clean, shareable format (CSV → formatted spreadsheet via the xlsx skill, or a simple PDF cheat sheet).

**Must Have (refined 2026-07-23 after product discussion)**
- Two-layer design, not a flat list: an overview tab (simple ranked list + tiers, works for casual users at a glance) plus per-player detail views (color-coded yearly/weekly stats, team context, a short Note) for anyone who wants to click deeper. Buildable in Excel now (summary tab + linked player tabs with conditional formatting) — this is the low-tech stepping stone toward the eventual UDK-style app in Phase 6.
- Positional tiers (not just a flat ranked list) — closer to what FantasyPros/@fantasyguides-style cheat sheets look like.
- A short "why" Note per player: Andrew writes/curates Notes himself for players he has real opinions on; for the rest, Claude drafts a Note from the underlying stats and Andrew reviews/edits/approves before it ships. Goal is full coverage by start of season without requiring Andrew to hand-write every one — his approval is the quality gate, not the authorship.

**Nice to Have**
- Track which Notes are "Andrew-written" vs "Claude-drafted, Andrew-approved" (even just a column/flag, already exists as `blurb_source`) — useful later for seeing which Notes actually perform better with the audience.

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

**Sequencing decision (2026-08-24):** Andrew's manual-rank review (QB/RB, comparing his own "how I'd rank" calls against our formula and market ADP) surfaced two distinct gaps — this phase (news/depth-chart/trade context) and the unit-quality-ratings idea logged in Phase 5. Research digest goes first, for three reasons: (1) volume — it explained roughly twice as many of Andrew's real disagreements in that review (15+ examples: trades, camp battles, depth-chart changes, injury-recovery context) versus unit quality (~8, concentrated in RB game-script specifically); (2) fit — a trade or a depth-chart change is a discrete EVENT a continuous "team quality" rating wouldn't have caught either (Kenneth Walker being traded to KC, Malik Willis becoming a new team's starter) — these need the news layer specifically, not a better team rating; (3) architecture — news/context slots into the Notes system already built (manual overrides/annotations), while unit quality would mean a new signal feeding the VOR formula itself, a bigger methodology question (how much weight, avoiding double-counting with the existing opportunity_weight) worth its own dedicated design pass, not a bolt-on alongside this phase. Unit quality ratings stay logged and scoped in Phase 5, picked up after this phase is proven out.

**Must Have**
- ✅ Script that pulls weekly news/injuries, summarizes with Claude, flags fantasy-relevant implications (`scripts/content/digest.py`) — built 2026-08-24. RotoWire NFL news RSS feed (confirmed reachable/clean), matched against the FULL players table (not just currently-ranked players -- deliberate, see the MarShawn Lloyd note under Handcuff rankings in Phase 5: a player excluded from scoring can still be exactly who this digest needs to catch), summarized + direction-flagged (UP/DOWN/NEUTRAL) via Claude Haiku, written to `content/drafts/digest_<date>.md`. Does NOT auto-write to `rankings.blurb` -- Andrew reviews the report and manually decides what becomes a real Note update, per the human-approval design already settled on above (this year). First real run (with a live API call) still pending as of this write-up.

**Vision update (2026-09-02, Andrew's call):** the human-approval/manual-Note-update design above is Day-1/this-season thinking, not the end state -- this year Andrew won't lean on it heavily anyway, since he isn't fully trusting these rankings for his own draft yet and this isn't a product for anyone else yet. The actual intent: by next preseason, once a full season of validated digest history exists, an actual product should take the digest's news classifications, the VOR rankings, and Andrew's own input as inputs and draft NOTES for Andrew to review -- same human-approval gate (he still reviews before anything ships), but AI-assisted drafting across more signals than just news, not Andrew authoring from scratch. Separately, Andrew's view is that scoring.py/weights_config.py themselves should eventually be nudgeable by digest news too -- modest, not drastic (e.g. a depth-chart change or a trade shifting one player's score relative to a teammate's), not just Notes. This updates the Phase 5 framing below, where unit-quality-ratings was logged as the only planned live input to the VOR formula -- news-as-a-scoring-input is now an explicit intended direction too, just not scoped or designed yet. Not started; logged here so it isn't lost, not a Phase 3/4 change.

- Generates content ideas: short-form hooks, titles, angle suggestions (per the original brief — 10 ideas/day was the original ask; start smaller, e.g. 3-5, and expand once quality is proven).
- Run manually for the first 2-3 weeks of the season to validate output quality before automating.
- News category coverage, informed by real cases from the 2026-08-24 manual-rank review (use these as concrete test cases when scoping/evaluating digest output, not just injuries): trades (Kenneth Walker to KC), starter/depth-chart changes (Malik Willis becoming a team's starter), camp/preseason role battles (Montgomery sitting with starters, Tracy losing snaps to Skattebo), and trade-risk/role-uncertainty rumors (James Conner). Injury *recovery* context matters too, not just injury *events* — Mahomes' rushing-floor question is about a past ACL tear's lingering effect on this year's projection, not a new injury to report.

**Nice to Have**
- Script outlines (not just ideas) for the strongest 1-2 ideas per run.
- Static "player card" HTML view of digest output (Andrew's idea, 2026-08-24, timing refined 2026-08-24 after a follow-up question) — a regenerated, non-interactive HTML page rendering the digest history as visual cards (status badges, team, trend) instead of a plain markdown report. Distinct from the full interactive app in Phase 6 below (this is a report-layer polish, not a live/searchable UI) — deliberately timed for AFTER the digest has run for a week or two and the history/memory system has held up under real use, not immediately: building a viewer on top of a data model still being actively fixed (the headline-display regression and tone/impact split both happened within this same session) means rebuilding the UI every time the shape changes underneath it.

**Future Version**
- Automated posting/scheduling to actual platforms.
- Full interactive web app — rankings management (add/remove/override players via UI, not just editing `weights_config.py`/spreadsheets) AND live player-card/news browsing, not just the regenerated static view above (the "UDK-style app" already noted under Phase 2's two-layer design decision). Explicitly NOT near-term (Andrew asked 2026-08-24, timing addressed then): "add/remove rankings via UI" is a real interaction-model decision, not a frontend-only add — it means either exposing manual overrides on top of the VOR formula (the same tension flagged in the Phase 3 "news-driven watch list" idea above) or exposing weight-tuning through a UI, plus real infrastructure this project doesn't have yet (a web framework, hosting, a safe way to sync UI edits back into the local SQLite file). Makes the most sense once the scoring methodology itself stops changing week to week — it's been touched every session so far (roster filter, min-games filter, and more before that). Stays Phase 6 "Public Product."

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
- Unit-level quality ratings (2026-07-26 team defenses + 2026-07-28 O-line, consolidated and expanded 2026-08-24 after Andrew's manual-rank review surfaced the same gap repeatedly): track quality ratings for both sides of the ball at the UNIT level, not just whole-team win totals — Offense, Defense, OL, DL, and (new 2026-08-24) WR corps / RB corps depth, plus how each team's defense specifically performs against each fantasy position (a "defense vs. position" matchup signal, useful once the season starts and weekly matchups exist). Why this showed up so often in the 2026-08-24 review: RB value in particular swings a lot on team offensive quality/game script (Andrew's own stated theory, confirmed across ~8 real examples -- Kenneth Walker, Montgomery, Corum, Mason, Javonte Williams all moved because of team outlook, not personal stats), and QBs can swing the OPPOSITE direction off defensive quality (a good defense can suppress a QB's passing volume by keeping games out of hurry-up mode -- Mahomes case, 2026-08-24). Real, separate data model from offensive weekly_stats (sacks/turnovers/points-allowed and blocking win-rate stats, not completions/carries/targets) -- scope as its own mini-project when picked up, not a quick bolt-on. PFF grades are the standard paid source for O-line/D-line specifically; check free alternatives (ESPN's pass-block/run-block win rate) first, same as noted below. Explicitly NOT started yet (2026-08-24) -- see the Phase 3-vs-this sequencing note under Phase 3 for why research digest goes first.

**Defense-vs-position matchup signal, schema check (2026-09-03):** confirmed directly against schema.sql -- the pieces are partially there already, this is NOT a new data source the way O-line/D-line grading is. `weekly_stats` already has every player's production by position/team/week; `team_stats` already pulls schedule data via an existing `import_schedules()` call (currently only feeding points_scored/points_allowed). What's missing: an opponent field tying a team's week to who they played, plus a derived "fantasy points allowed by position" rollup -- a modest addition on top of existing tables, not a new ingest pipeline. Sequencing (Andrew's call, 2026-09-03): pick this up once the season has actually started (the matchup signal can't be populated before real games happen anyway) and once depth-chart/team-grades work is already in progress -- not immediately, but sooner than the heavier O-line/D-line grading piece above, which stays fully deferred.
- Reddit/social sentiment signal for sleeper/bust identification.
- Trade analyzer (compare value of two trade packages using the rankings engine).
- Multi-platform content repurposing (one digest → YouTube script + IG caption + newsletter blurb).
- Handcuff rankings (2026-07-26, Andrew's idea, sparked by the ADP outlier review): rank backup RBs specifically by upside-if-the-starter-gets-hurt — factoring in the backup's own passing-game usage, the team's overall quality/pace, and how bad the starter's injury history is. A real, separate ranking dimension from the main board, not something VOR/the main formula should try to fold in. Live example (2026-08-24): MarShawn Lloyd got dropped from the main board entirely by the new `min_games_to_score` filter (too few games logged) right as he's genuinely rising — Josh Jacobs' negative news is pushing Lloyd up real draft boards. Not a bug in that filter (it correctly can't tell "1 game because irrelevant" from "1 game because a real opportunity just opened up" — that distinction needs news, not stats) — it's exactly the case this handcuff-ranking idea exists to catch.
- Cross-player ripple effects in the digest (2026-08-25, Andrew's ask, from a second real digest run): right now every player's news gets summarized in total isolation, but a huge share of Andrew's real feedback that day pointed at the same gap — Kirk Cousins being the likely Week 1 starter should inform how to read news about his own pass-catchers (Bowers, etc.); J.J. McCarthy's practice news only makes sense in light of Kyler Murray being the presumed starter ahead of him; Ashton Jeanty's injury should flag Mike Washington's rising snaps as more fantasy-relevant; Jacory Croskey-Merritt trending down should flag Rachaad White trending up on the same roster; Sean Tucker's bad news is relatively good for other Tampa Bay backs. This is the same underlying idea as handcuff rankings above, generalized beyond just "who's the backup RB" to any same-team/same-position relationship the digest could reason about. Deliberately NOT attempted as a quick prompt hack — it needs real depth-chart/relationship data (who's actually the competition for whom on a given roster) that doesn't exist cleanly in the schema yet, which is a real data-modeling question, not a wording tweak. Scope together with handcuff rankings when picked up, since they're the same underlying capability.
- Situational/news context ("camp news," 2026-07-26): the ADP outlier review surfaced real cases (Tyreek Hill's situation, James Conner's backfield competition/team outlook) where the *market* has forward-looking context our stats-only formula structurally cannot have — a season's box score can't know about an offseason injury, a coaching change, or a depth-chart battle. This is NOT a decay-rate/weights fix — no amount of recency tuning solves it, since the information isn't in any historical season at all. The real fix is the Phase 3 research-digest concept (pulls current news, flags fantasy-relevant implications) feeding into the Notes as manual overrides/annotations, not a new scoring parameter. Sourcing decision (2026-07-28): X/Twitter's API moved to pay-per-use in 2026 with no free tier at all (even the old $200/mo Basic tier is closed to new signups) — not a good fit for automated ingestion. Free RSS feeds (RotoWire/RotoBaller injury and player-news feeds) are the better source for the automated digest; X stays useful as something Andrew personally browses for camp-reporter color that feeds his own note-writing, not something to build scraping infrastructure around.
- Betting markets as a signal (2026-07-28, Andrew's idea): use sportsbook lines — team win totals, game spreads/totals (implied team scoring environment), and player props (anytime TD odds, yardage overs/unders) — to help project expected season/weekly output. Markets are widely regarded as one of the sharpest available signals precisely for things our formula can't see from box scores alone (team quality, game script expectations, role certainty) — directly relevant to gaps already found (e.g. the James Conner/team-outlook case). Worth scoping as its own data source once picked up (odds APIs, which team/player, which markets to pull) rather than a quick bolt-on.
- Backtest validation (2026-07-31, Claude's suggestion, Andrew agreed): build rankings using only 2020-2024 data, then check how they'd have actually performed against real 2025 season outcomes (e.g. Spearman correlation between pre-season projected rank and actual season-end fantasy finish). This is the strongest possible answer to "why should anyone trust this formula" — directly serves the "rankings need to be genuinely defensible" goal stated elsewhere in this doc — but it's nontrivial (need a defensible scoring-of-the-scorer method, and scoring.py would need a "pretend today is August 2025" mode). Explicitly deferred: Andrew's call was not to start this until Phase 3 (research digest) is proven out, not before.

**Known minor data-quality quirk (2026-07-26, confirmed real-world impact 2026-08-24):** a small number of very recent/late-round players get a synthetic (non-gsis_id) placeholder ID from nflverse-adjacent sources when they don't have an official ID assigned yet, and different sources (the ID crosswalk vs. draft picks data) can synthesize *different* placeholders for the same real person — found via "Mike Washington Jr.," who has two separate `players` rows (`WAS569019` from Sleeper's crosswalk, `WAS797326` from draft_picks.py) that are almost certainly the same guy. Originally assessed as low-priority ("doesn't affect rankings today... revisit if this shows up more") — revisit is now warranted: Andrew's 2026-08-24 manual-rank review hit this player directly (rated him HowIdRank 50, but he shows no rank at all in our system because his stats/draft-capital data is split across the two IDs). Worth a real fix next time rookie/ID-crosswalk data is touched, not just noted.

---

## Phase 6 — Public Product (future, once V2 is proven)

**Future Version**
- Pick a platform (or platforms) and actually start publishing.
- Explore monetization: newsletter subscriptions, affiliate links, sponsorships, possibly a paid tier for deeper rankings/tools.
- Revisit whether a public-facing site/app makes sense, vs. continuing to work through existing platforms (YouTube/IG/Substack).

This phase is intentionally light on detail — decisions here should be made with real data/rankings in hand, not guessed at now.
