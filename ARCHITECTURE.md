# Architecture

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Best ecosystem for data + AI; deliberate choice to rebuild Python fluency (background is Java-heavy) |
| Storage | SQLite | File-based, zero infra, real SQL practice, plenty for single-user scale. Revisit only if concurrent writes or multi-user access become a real requirement. |
| Data validation | plain pandas/sanity checks | No need for a validation framework (e.g. Great Expectations) at this scale |
| AI | Anthropic API (Claude) | Already have a key; used for summarization + content generation |
| Env/secrets | `.env` file + `python-dotenv`, gitignored | Never commit API keys, even to a private repo |
| Version control | Git + public GitHub repo | Portfolio value; simple `main` + short-lived feature branches is enough — no need for gitflow at this size |

## Data sources

| Source | Cost | Auth | What it's used for |
|---|---|---|---|
| **Sleeper API** | Free, no tier limits | None required (read-only, public) | Player IDs, team rosters, metadata. Stay under ~1000 calls/min per their guidance. Docs: docs.sleeper.app |
| **nfl_data_py (nflverse)** | Free, open source | None | Historical play-by-play, weekly/season stats going back years. This is the backbone of the historical database. |
| **FantasyPros API** | Free for personal/non-commercial use | Requires requesting an API key via their support portal | ADP, expert consensus rankings, projections. Commercial use (redistribution, high volume, bulk historical access) requires contacting partners@fantasypros.com for custom pricing — no public price list exists. Not needed unless/until this becomes a commercial product. |
| **PFF (Pro Football Focus)** | Paid subscription | N/A | Advanced grades/stats. Not evaluated in depth — genuinely a "Nice to Have," worth pricing out only once free sources have a proven gap (e.g., needing PFF-style grades specifically). |
| **News/web** | Free (scraping) or paid news APIs | Varies | Phase 3 — weekly news pulls for the research digest. Revisit specific source when we get there. |

Everything in Phase 1-2 runs on the free tier. Paid data is a Phase 5+ conversation, not now.

**Why Sleeper over ESPN despite Andrew personally playing on ESPN:** this is a data-engineering choice, not a "which app do I play fantasy on" choice. Sleeper's player endpoint is a free, unauthenticated, canonical database of every NFL player with a stable ID — usable regardless of what platform anyone drafts on. ESPN has no equivalent: its fantasy API is unofficial/reverse-engineered (community libraries like `espn-api` on GitHub), and private leagues require scraping `SWID`/`espn_s2` cookies out of a logged-in browser session — extra auth friction for zero benefit here, since we're not pulling *league* data (rosters, scores), we're building a *player* database. `player_id` (Sleeper's ID) is used as the internal primary key across our schema for this reason. If a future feature needs to sync an individual's actual ESPN/Sleeper/Yahoo league (e.g., a trade analyzer using someone's real roster), that's a separate, later concern and would use that platform's API specifically for that user's league.

## Database schema (finalized 2026-07-23)

Source of truth is `scripts/db/schema.sql` — run `py scripts/db/init_db.py` to build/update `data/db/fantasy_football.db` from it. Not duplicated here to avoid the two drifting out of sync; see that file's comments for the full reasoning behind each choice.

Summary of tables: `teams`, `players` (keyed on nflverse's `gsis_id`, with `sleeper_id`/`fantasypros_id`/`espn_id` populated from nflverse's `ff_playerids` crosswalk — see "why Sleeper" note above, same logic applies to matching across all three platforms), `weekly_stats` (raw counting stats, not just fantasy points — needed for the drill-down/color-coded stats view), `season_stats` (a **view**, not a table — derived live from `weekly_stats` so it can't drift out of sync), `snap_counts`, `advanced_stats` (Next Gen Stats — air yards/aDOT, receiving-focused for now), `team_stats` (pace/scoring context, and the denominator for share metrics), `adp`, and `rankings` (Phase 2's own output, including a `blurb_source` column tracking `'andrew'` vs `'claude_drafted'`).

Deliberately excluded from the schema (compute at query/display time instead of storing): yards per carry, yards per reception, completion percentage, targets per game — all simple division from columns we already have.

Deliberately deferred to a future version (real complexity, not just extra columns): red zone carries/targets (needs play-by-play aggregation), expected fantasy points (no ready-made source — would need our own model), yards per route run/routes run (only charted since 2022, would leave a historical gap).

## Repo structure

```
FantasyFootballProject/
├── CLAUDE.md
├── ROADMAP.md
├── ARCHITECTURE.md
├── .env                 (gitignored — API keys)
├── .gitignore
├── requirements.txt
├── data/
│   ├── raw/              (gitignored — raw API pulls, can be large)
│   ├── processed/
│   └── db/               (gitignored — the .sqlite file itself; schema lives in code, not git)
├── scripts/
│   ├── ingest/
│   │   ├── sleeper.py
│   │   ├── nfl_data.py
│   │   └── fantasypros.py
│   ├── rankings/
│   │   ├── scoring.py
│   │   └── cheat_sheet.py
│   └── content/
│       └── digest.py     (Phase 3)
└── content/
    └── drafts/           (gitignored or not — decide once there's real output; likely fine to commit as portfolio evidence)
```

## Git conventions

- `main` stays deployable/working at all times.
- Short-lived branches per feature (e.g. `feature/sleeper-ingest`), merged via PR into `main` even solo — good habit, and PRs give a natural changelog for the portfolio.
- Commit often, in small units; message format `type: short description` (e.g. `feat: add sleeper player ingest script`, `fix: handle missing ADP for rookies`).
- README at repo root (separate from this docs set) should be the public-facing pitch: what this is, screenshots of the cheat sheet output, how to run it. Write this once Phase 2 has a real deliverable to show — an empty-scaffold README isn't worth much to a recruiter.
