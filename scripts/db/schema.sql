-- Fantasy Football Project — SQLite schema
-- Source of truth for the database structure. ARCHITECTURE.md links here rather than
-- duplicating the SQL, so this file is the one place to look/update.
--
-- Design notes (the "why"):
-- - gsis_id (nflverse's player ID) is the primary key for players, not sleeper_id or
--   fantasypros_id, because it's the ID our richest historical stats source (nfl_data_py)
--   uses natively. The other platform IDs are stored as plain columns, populated from
--   nflverse's ff_playerids crosswalk (import_ids()), so we never have to match players
--   by name across sources.
-- - weekly_stats holds raw counting stats (not just fantasy points) because the product
--   needs drill-down/color-coded stats per player, not just a single score.
-- - season_stats is a VIEW, not a table: it's fully derivable by summing weekly_stats,
--   so storing it separately would just be a second copy of the same numbers that could
--   drift out of sync. Recompute it live instead.
-- - snap_counts, advanced_stats (NGS), and team_stats are separate tables rather than
--   extra columns on weekly_stats, because they come from different source calls with
--   different historical coverage (e.g. NGS doesn't go back as far) — keeping them
--   separate avoids a core table full of nulls.

PRAGMA foreign_keys = ON;

-- One row per team
CREATE TABLE IF NOT EXISTS teams (
    team_abbr   TEXT PRIMARY KEY,
    team_name   TEXT NOT NULL,
    bye_week    INTEGER
);

-- One row per player (canonical identity, not stats)
CREATE TABLE IF NOT EXISTS players (
    gsis_id         TEXT PRIMARY KEY,       -- nflverse's stable player ID
    sleeper_id      TEXT,
    fantasypros_id  TEXT,
    espn_id         TEXT,
    full_name       TEXT NOT NULL,
    position        TEXT NOT NULL,
    current_team    TEXT REFERENCES teams(team_abbr),
    status          TEXT,                   -- e.g. active, injured_reserve
    age             INTEGER,
    height          INTEGER,                -- inches
    weight          INTEGER,                -- lbs
    college         TEXT,
    years_exp       INTEGER
);

CREATE INDEX IF NOT EXISTS idx_players_sleeper_id ON players(sleeper_id);
CREATE INDEX IF NOT EXISTS idx_players_fantasypros_id ON players(fantasypros_id);

-- One row per player per game
CREATE TABLE IF NOT EXISTS weekly_stats (
    gsis_id             TEXT NOT NULL REFERENCES players(gsis_id),
    season              INTEGER NOT NULL,
    week                INTEGER NOT NULL,
    team                TEXT REFERENCES teams(team_abbr),

    completions         INTEGER DEFAULT 0,
    attempts            INTEGER DEFAULT 0,
    passing_yards       INTEGER DEFAULT 0,
    passing_tds         INTEGER DEFAULT 0,
    interceptions       INTEGER DEFAULT 0,

    carries             INTEGER DEFAULT 0,
    rushing_yards       INTEGER DEFAULT 0,
    rushing_tds         INTEGER DEFAULT 0,

    receptions          INTEGER DEFAULT 0,
    targets             INTEGER DEFAULT 0,
    receiving_yards     INTEGER DEFAULT 0,
    receiving_tds       INTEGER DEFAULT 0,

    fumbles_lost        INTEGER DEFAULT 0,

    fantasy_points_ppr      REAL,           -- from nflverse directly
    fantasy_points_half_ppr REAL,           -- computed by us: standard + 0.5 * receptions

    target_share            REAL,           -- share of team's targets that week; from nflverse directly
    wopr                    REAL,           -- weighted opportunity rating (1.5*target_share + 0.7*air_yards_share); from nflverse directly

    PRIMARY KEY (gsis_id, season, week)
);
-- Note: target_share/wopr were added after weekly_stats already existed in real databases --
-- see MIGRATIONS in init_db.py, since CREATE TABLE IF NOT EXISTS won't retroactively add
-- columns to a table that's already there.

CREATE INDEX IF NOT EXISTS idx_weekly_stats_season_week ON weekly_stats(season, week);

-- Derived, not ingested — recomputed live from weekly_stats so it can never drift out of sync
CREATE VIEW IF NOT EXISTS season_stats AS
SELECT
    gsis_id,
    season,
    COUNT(DISTINCT week)          AS games_played,
    SUM(completions)              AS completions,
    SUM(attempts)                 AS attempts,
    SUM(passing_yards)            AS passing_yards,
    SUM(passing_tds)              AS passing_tds,
    SUM(interceptions)            AS interceptions,
    SUM(carries)                  AS carries,
    SUM(rushing_yards)            AS rushing_yards,
    SUM(rushing_tds)              AS rushing_tds,
    SUM(receptions)               AS receptions,
    SUM(targets)                  AS targets,
    SUM(receiving_yards)          AS receiving_yards,
    SUM(receiving_tds)            AS receiving_tds,
    SUM(fumbles_lost)             AS fumbles_lost,
    SUM(fantasy_points_ppr)       AS fantasy_points_ppr,
    SUM(fantasy_points_half_ppr)  AS fantasy_points_half_ppr
FROM weekly_stats
GROUP BY gsis_id, season;

-- Playing-time data (import_snap_counts) — separate table, different source/coverage than weekly_stats
CREATE TABLE IF NOT EXISTS snap_counts (
    gsis_id       TEXT NOT NULL REFERENCES players(gsis_id),
    season        INTEGER NOT NULL,
    week          INTEGER NOT NULL,
    team          TEXT REFERENCES teams(team_abbr),
    offense_snaps INTEGER,
    offense_pct   REAL,
    PRIMARY KEY (gsis_id, season, week)
);

-- Next Gen Stats — receiving-focused for now (aDOT/air yards); extend with passing/rushing
-- NGS fields later if needed. Kept separate from weekly_stats: NGS coverage is shorter
-- historically and only applies to certain positions, so it would just add nulls to the core table.
CREATE TABLE IF NOT EXISTS advanced_stats (
    gsis_id                  TEXT NOT NULL REFERENCES players(gsis_id),
    season                   INTEGER NOT NULL,
    week                     INTEGER NOT NULL,
    avg_depth_of_target      REAL,           -- aDOT
    avg_yac                  REAL,
    avg_separation           REAL,
    PRIMARY KEY (gsis_id, season, week)
);

-- Team-level weekly stats: standalone context (pace/scoring environment) and the
-- denominator for share metrics (target share, carry share) computed at query time.
CREATE TABLE IF NOT EXISTS team_stats (
    team_abbr      TEXT NOT NULL REFERENCES teams(team_abbr),
    season         INTEGER NOT NULL,
    week           INTEGER NOT NULL,
    pass_attempts  INTEGER,                 -- derived: sum of weekly_stats.attempts for the team
    rush_attempts  INTEGER,                 -- derived: sum of weekly_stats.carries for the team
    points_scored  INTEGER,                 -- from import_schedules()
    points_allowed INTEGER,                 -- from import_schedules()
    PRIMARY KEY (team_abbr, season, week)
);

-- Current ADP/expert consensus snapshot (Phase 1: FantasyPros)
CREATE TABLE IF NOT EXISTS adp (
    gsis_id    TEXT NOT NULL REFERENCES players(gsis_id),
    source     TEXT NOT NULL,               -- e.g. 'fantasypros'
    adp        REAL,
    pulled_at  TEXT NOT NULL,               -- ISO timestamp
    PRIMARY KEY (gsis_id, source, pulled_at)
);

-- Our own rankings engine's output (Phase 2) — not ingested from anywhere
CREATE TABLE IF NOT EXISTS rankings (
    gsis_id       TEXT NOT NULL REFERENCES players(gsis_id),
    scoring_format TEXT NOT NULL,           -- 'ppr' or 'half_ppr'
    rank          INTEGER,
    score         REAL,
    blurb         TEXT,
    blurb_source  TEXT,                     -- 'andrew' or 'claude_drafted'
    generated_at  TEXT NOT NULL,
    PRIMARY KEY (gsis_id, scoring_format, generated_at)
);
