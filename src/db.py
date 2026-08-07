"""SQLite connection and schema for data/wnba.db, the project's single source of truth."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "wnba.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    location TEXT,
    name TEXT,
    display_name TEXT,
    abbreviation TEXT,
    color TEXT,
    alternate_color TEXT
);

CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    player_name TEXT,
    position TEXT,
    first_season INTEGER,
    last_season INTEGER
);

CREATE TABLE IF NOT EXISTS games (
    game_id INTEGER PRIMARY KEY,
    season INTEGER NOT NULL,
    game_date TEXT NOT NULL,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    home_score INTEGER,
    away_score INTEGER,
    overtime_periods INTEGER NOT NULL DEFAULT 0,
    possessions_est REAL,
    pace REAL,
    home_off_rating REAL,
    away_off_rating REAL,
    attendance INTEGER,
    FOREIGN KEY (home_team_id) REFERENCES teams (team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams (team_id)
);

CREATE TABLE IF NOT EXISTS player_games (
    game_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    game_date TEXT NOT NULL,
    season INTEGER NOT NULL,
    player_name TEXT,
    team_id INTEGER,
    opponent_id INTEGER,
    home_away TEXT,
    minutes REAL,
    fga INTEGER,
    fgm INTEGER,
    fg3a INTEGER,
    fg3m INTEGER,
    fta INTEGER,
    ftm INTEGER,
    points INTEGER,
    oreb INTEGER,
    dreb INTEGER,
    reb INTEGER,
    ast INTEGER,
    stl INTEGER,
    blk INTEGER,
    tov INTEGER,
    pf INTEGER,
    plus_minus REAL,
    started INTEGER,
    dnp_reason TEXT,
    PRIMARY KEY (game_id, player_id),
    FOREIGN KEY (game_id) REFERENCES games (game_id),
    FOREIGN KEY (player_id) REFERENCES players (player_id)
);

-- One row per player per game, including players who did not play. The
-- minutes model (phase 5) needs to know who could have played, not just who
-- did; status is a fixed, normalized category derived from the raw
-- dnp_reason text in player_games.
CREATE TABLE IF NOT EXISTS availability (
    game_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    team_id INTEGER,
    status TEXT NOT NULL CHECK (
        status IN ('played', 'dnp_coach', 'dnp_injury', 'dnp_rest', 'inactive', 'not_on_roster')
    ),
    minutes_played REAL,
    PRIMARY KEY (game_id, player_id),
    FOREIGN KEY (game_id) REFERENCES games (game_id),
    FOREIGN KEY (player_id) REFERENCES players (player_id)
);

-- Every non-exhibition schedule entry (played or not), one row per team per
-- game. Separate from `games` (completed games only, with results) so the
-- games-per-team check compares against the full published schedule instead
-- of just what's been played so far.
CREATE TABLE IF NOT EXISTS scheduled_games (
    game_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    PRIMARY KEY (game_id, team_id)
);

-- Bookkeeping for idempotent ingestion: which seasons are fully backfilled
-- and can be skipped on the next `update` run.
CREATE TABLE IF NOT EXISTS ingest_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
