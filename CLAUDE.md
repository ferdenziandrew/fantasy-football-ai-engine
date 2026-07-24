# Fantasy Football Project — Instructions

This file is read at the start of every session working in this folder. It captures how this project is run and why, so decisions don't need to be re-litigated each time.

## What this project is

Andrew's first Cowork project. Two goals running in parallel, in priority order:

1. **Learn to build real AI/automation tools** as part of a QA → AI Engineer career transition. This is the primary driver.
2. **Build a genuine fantasy football data/rankings engine** that can eventually feed content (YouTube, Instagram, podcast, newsletter — undecided which first) and possibly generate income. Rankings accuracy matters to Andrew personally, not just as a demo.

Not a goal right now: picking a content platform, growing an audience, or monetizing. Those come after the data foundation and rankings engine exist and are good.

## Who's building this

- CS degree, ~5 years QA (Cox Communications, commercial voice), strong Java background, Python at a beginner-to-low-intermediate level and rebuilding it deliberately.
- Learns best concept-first: the "why" before the "how," anchored to this real project rather than toy exercises.
- Wants a mixed coding split: I write more of the scaffolding/boilerplate early and explain it, Andrew drives direction and takes on more of the implementation as skill builds. This should shift over time — check in periodically rather than assuming the same split forever.
- Workflow preference: give a concrete suggestion/plan, let Andrew read it, then get yes/no or directional feedback rather than open-ended questions. Increase detail and autonomy as the project matures and trust builds.
- Wants a mentor who pushes back on unnecessary complexity but stays collaborative — not purely blunt. This is new territory for Andrew; tone can be tuned further as we go.

## Operating philosophy

Andrew has a stated tendency to over-engineer. Default posture: favor MVPs, fast feedback, and real learning over architectural purity.

Before building anything, ask: **"What is the simplest version that creates value?"**

Avoid, unless explicitly justified: multi-agent architectures, premature optimization, enterprise-grade infra, ML models where a transparent formula works, building automation before the underlying logic is validated manually.

When proposing a feature or approach, briefly rate it: Must Have / Nice to Have / Future Version / Avoid For Now, and note learning value, career value, monetization value, complexity, and time cost when the tradeoff isn't obvious.

## Current phase

See `ROADMAP.md` for the full phased plan. Today's date context: kickoff on 2026-07-23, with fantasy drafts typically landing late August–early September, so Phase 1–2 work is timed to land before draft season, and Phase 3 (weekly content) picks up once the season starts.

## Tech stack decisions (see ARCHITECTURE.md for detail)

- **Language:** Python (deliberate choice to build back up Python fluency; also the right ecosystem for data + AI work).
- **Storage:** SQLite for now — a real step up from CSVs, teaches SQL, zero infra to manage. Do not reach for Postgres/cloud DB until there's an actual reason (multi-user access, concurrent writes, etc.).
- **Data sources:** Free-tier first — Sleeper API, nfl_data_py (nflverse), FantasyPros free personal-use API. Paid data (FantasyPros commercial tier, PFF) considered later, once there's a concrete gap the free sources can't fill.
- **AI:** Anthropic API (Claude) — Andrew already has a key. Used for summarization, content idea generation, and eventually the research digest.
- **League format:** Full PPR is the primary target (matches Andrew's own leagues). Half-PPR is a toggle for content purposes, not a separate parallel system — one scoring engine, parametrized.
- **Version control:** Public GitHub repo (Andrew has an account already). Portfolio value matters here — keep secrets out via `.env` + `.gitignore`, never commit API keys.

## Automation

Hold off on Cowork scheduled tasks until there's 2-3 weeks of manually-validated output from whatever we're automating (per Andrew's own suggestion — don't debug the automation and the underlying logic at the same time). Lay groundwork (clean, callable scripts/functions) now so flipping on a scheduled task later is low-effort, not a rebuild.

## Folder structure

```
FantasyFootballProject/
├── CLAUDE.md          — this file
├── ROADMAP.md         — phased build plan
├── ARCHITECTURE.md     — tech stack, data sources, schema
├── data/
│   ├── raw/           — untouched pulls from APIs
│   ├── processed/     — cleaned/transformed data
│   └── db/            — SQLite database file(s)
├── scripts/
│   ├── ingest/        — pulls data from Sleeper, nfl_data_py, FantasyPros
│   ├── rankings/       — scoring engine, cheat sheet generation
│   └── content/        — digest/content idea generation (Phase 3+)
└── content/
    └── drafts/         — generated content ideas/scripts, pre-publish
```

## Environment limitation: never write to data/db/*.db or .git from the sandbox

This folder reaches Claude's sandbox through a virtualized mount that does not reliably
support the file-locking operations SQLite and git depend on. Writing to the real
`data/db/fantasy_football.db` from the sandbox while Andrew also has local processes
touching it (or ever, really) risks silent corruption — this happened once already
(2026-07-24, "database disk image is malformed", full rebuild required). `git init`
hit an analogous failure earlier (2026-07-23) for the same underlying reason.

Rule going forward: test all database logic (ingest scripts, upserts, schema changes)
against a throwaway copy in `/tmp`, never against the real `data/db/fantasy_football.db`.
Andrew runs the real thing locally. Same logic applies to any git operations.

A related variant hit the same day (2026-07-24): after using the Write tool to update
`scripts/ingest/nfl_data.py`, the sandbox's bash view of that file was stuck showing a
stale, truncated copy from an earlier write (confirmed by comparing `wc -l` / a syntax
check in bash against a Read tool call, which showed the correct full file). A stale
`__pycache__/*.pyc` next to it caused a separate but related symptom (Python running old
code after a source edit) because this mount doesn't seem to report file mtimes reliably
enough for Python's import cache invalidation to trust.

Rule going forward: after editing a script that will immediately be tested via bash in
the same session, don't assume the Write/Edit tool's view and bash's view agree. Verify
with a quick `wc -l` / `python3 -m py_compile` in bash before relying on it, and if it
looks stale, rewrite the file directly from bash (`cat > file << 'EOF' ... EOF`) rather
than fighting the cache. Always delete `__pycache__` before re-running a script that was
just edited.

## Notes for future sessions

- Don't re-ask Andrew about coding split, mentor tone, or automation timing — it's captured above and in memory. Do check in if it seems like the split should shift.
- Don't assume a content platform has been chosen — it hasn't.
- Rankings need to be genuinely defensible (transparent methodology), not just "close enough to FantasyPros." That's the actual differentiator if this ever gets published.
