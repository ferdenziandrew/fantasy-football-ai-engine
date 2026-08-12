# Fantasy Football Rankings Engine

A transparent, from-scratch fantasy football rankings and cheat-sheet generator, built on real NFL data rather than a black-box model. This is a personal project with two goals: build something genuinely useful for my own leagues, and build it the way I'd want a real data/AI-adjacent project to be built — a documented schema, a defensible scoring methodology, and a pipeline I can actually explain line by line.

## What this is

Most public "fantasy rankings" are either a spreadsheet someone eyeballed or the output of an opaque model nobody can interrogate. This project is neither: it's a SQLite database of real historical NFL performance, current ADP, and rookie draft capital, fed into a fully parametrized value-over-replacement (VOR) scoring formula — every weight is a named constant in a config file, not a hidden coefficient. If a player's rank looks wrong, the answer to "why" is always traceable to a specific number in `weights_config.py`, not "the model said so."

The output is a formatted Excel cheat sheet: one Overall tab (every scored player, ranked and tiered) plus one tab per position (QB/RB/WR/TE/K) for the drill-down view, each with real season stats, per-game rate columns, tier-based color coding, and short "why" Notes explaining context a stats-only formula structurally can't see (coaching changes, depth-chart battles, injury history).

## How the rankings actually work

- **Recency-weighted history, not a single season.** Each player's score blends multiple years of game logs, with recent seasons and recent weeks weighted more heavily than older ones (configurable decay rates) — a player's last 5 games matter more than their rookie year.
- **Small-sample shrinkage.** A player with only a handful of games isn't judged purely on a noisy small sample; their score gets pulled toward the positional average, with the threshold and strength tunable per position (kickers, for example, need a much stronger pull than running backs — a thin, tightly-scored positional pool makes VOR swing on small samples much more easily).
- **Value over replacement (VOR), not raw points.** A player's score reflects how much better they are than a realistic replacement-level player at their position in a standard league — the actual question a draft decision hinges on, not just "who scored the most fantasy points."
- **A separate, explicit path for rookies.** Players with zero game history get a baseline derived from draft capital (draft round/pick), not a performance score that doesn't exist yet — with a position-specific cap, since draft capital predicts rookie-year production very differently at QB than at RB.
- **ADP is a check, not an input.** Market ADP is deliberately kept out of the scoring formula itself — folding it in would just make the rankings converge toward "matching the market," undermining the point of having an independent methodology. Instead, a separate comparison tool flags the biggest disagreements between our rank and the market's, for manual review.

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Storage | SQLite (schema in `scripts/db/schema.sql`) |
| Data sources | Sleeper API (player IDs/metadata), nflverse via `nflreadpy` (historical weekly stats), Fantasy Football Calculator (current ADP), nflverse draft data (rookie draft capital) |
| Export | openpyxl (formatted Excel, conditional formatting, tiering) |
| AI | Anthropic API — used for Notes drafting and, eventually, the weekly research digest |

No ML projection models — a transparent weighted formula is more explainable, easier to debug, and (so far) just as defensible as a black box.

## Repo structure

```
scripts/
├── db/
│   ├── schema.sql          # source of truth for the DB structure
│   ├── init_db.py          # builds/migrates data/db/fantasy_football.db from schema.sql
│   └── validate.py         # basic row-count/null sanity checks
├── ingest/
│   ├── sleeper.py          # player IDs + team metadata
│   ├── nfl_data.py         # historical weekly stats, 2020-present (nflreadpy)
│   ├── ffc.py               # current ADP (Fantasy Football Calculator, primary source)
│   ├── fantasypros.py       # ADP/expert consensus (backup source, free tier is limited)
│   └── draft_picks.py       # rookie draft capital
├── rankings/
│   ├── weights_config.py    # every tunable parameter in the scoring formula
│   ├── scoring.py           # the VOR scoring engine itself
│   ├── cheat_sheet.py        # generates the formatted Excel cheat sheet
│   ├── adp_comparison.py     # flags biggest our-rank-vs-market-ADP disagreements
│   ├── blurb_worklist.py    # generates an editable worksheet for writing "why" Notes
│   ├── load_blurbs.py        # loads approved Notes back into rankings.blurb/blurb_source
│   ├── snapshot_rankings.py  # saves current rankings + weights before a tuning change
│   └── rankings_diff.py      # diffs a snapshot against the current rankings/weights
└── content/                  # Phase 3+ — weekly research digest, content ideas
```

## Running it locally

```bash
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env       # add your own API keys — never commit .env

py scripts/db/init_db.py           # build the database from schema.sql
py scripts/ingest/sleeper.py       # player IDs + team metadata
py scripts/ingest/nfl_data.py      # historical weekly stats (2020-present)
py scripts/ingest/draft_picks.py   # rookie draft capital
py scripts/ingest/ffc.py           # current ADP

py scripts/rankings/scoring.py     # generate rankings (edit weights_config.py first to tune)
py scripts/rankings/cheat_sheet.py # export the formatted Excel cheat sheet -> content/cheat_sheet.xlsx
```

## Status / what's next

Data pipeline and scoring engine are built and tuned; the Excel cheat sheet (Overall + position tabs, tiers, per-game rate stats, conditional formatting, rookie/ADP-outlier flags) is shipped and in active use, with "why" Notes written for QB/RB/WR/TE's top players. Next up: a final rankings-vs-ADP accuracy pass, then a weekly research digest that pulls current news/injuries and flags fantasy-relevant implications, feeding into the Notes as the season starts. See `ROADMAP.md` for the full phased plan.

This is an actively developed personal project — expect the schema and scoring weights to keep evolving as more seasons of real usage validate (or challenge) the methodology.
