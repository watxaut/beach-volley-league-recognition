"""Database schema for volleyball analysis.

SQLite at ``data/volley.db`` (WAL mode). Design decisions ratified in the
2026-09-05 session:

- ``videos.video_key`` is the video file STEM -- the unique video name that
  already keys calibrations/<stem>.json and output/<stem>/.
- Re-ingesting a video is a transactional DELETE + re-INSERT of that video's
  derived rows (actions, spikes). ``players`` and ``video_players`` (the
  labeling table) are NEVER touched by ingest, so labels survive
  reprocessing.
- Player names are resolved at query time via video_players -- actions and
  spikes store only track_id, because track ids are per-video bootstrap
  artifacts, not stable identities.
- No per-frame data (ball trajectory / frame_results) is stored.
"""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path("data/volley.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS videos (
    video_key        TEXT PRIMARY KEY,
    path             TEXT NOT NULL,
    fps              REAL,
    width            INTEGER,
    height           INTEGER,
    total_frames     INTEGER,
    processed_at     TEXT,
    pipeline_version TEXT,
    ingested_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

-- Per-video labeling: track_id (1-4 within this video) -> real player.
-- Team is informational (a snapshot at labeling time); per-action team is
-- authoritative and lives on the action rows.
CREATE TABLE IF NOT EXISTS video_players (
    video_key TEXT NOT NULL REFERENCES videos(video_key) ON DELETE CASCADE,
    track_id  INTEGER NOT NULL,
    player_id INTEGER NOT NULL REFERENCES players(id),
    team      TEXT,
    PRIMARY KEY (video_key, track_id)
);

CREATE TABLE IF NOT EXISTS actions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    video_key          TEXT NOT NULL REFERENCES videos(video_key) ON DELETE CASCADE,
    frame              INTEGER NOT NULL,
    ts                 REAL,
    track_id           INTEGER,
    action             TEXT NOT NULL,
    gesture            TEXT,
    confidence         REAL,
    team               TEXT,
    team_in_possession TEXT,
    touch_number       INTEGER,
    rally_id           INTEGER,
    contact_kind       TEXT,
    contact_x          REAL,
    contact_y          REAL,
    -- game-state machine: index into points() of the point this action
    -- belongs to; -1 = outside any point (practice / between points)
    point_index        INTEGER
);
CREATE INDEX IF NOT EXISTS idx_actions_video ON actions(video_key, frame);
CREATE INDEX IF NOT EXISTS idx_actions_rally ON actions(video_key, rally_id);

CREATE TABLE IF NOT EXISTS points (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    video_key     TEXT NOT NULL REFERENCES videos(video_key) ON DELETE CASCADE,
    point_index   INTEGER NOT NULL,
    start_frame   INTEGER NOT NULL,
    end_frame     INTEGER NOT NULL,
    n_actions     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_points_video ON points(video_key, point_index);
CREATE INDEX IF NOT EXISTS idx_actions_track ON actions(video_key, track_id);

CREATE TABLE IF NOT EXISTS spikes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    video_key        TEXT NOT NULL REFERENCES videos(video_key) ON DELETE CASCADE,
    frame            INTEGER NOT NULL,
    track_id         INTEGER,
    team             TEXT,
    spike_type       TEXT,
    attack_zone      TEXT,
    outcome          TEXT,
    landing_zone     TEXT,
    dug_zone         TEXT,
    exit_speed_px    REAL,
    flight_frames    INTEGER,
    resolution_frame INTEGER
);
CREATE INDEX IF NOT EXISTS idx_spikes_video ON spikes(video_key, frame);
CREATE INDEX IF NOT EXISTS idx_spikes_track ON spikes(video_key, track_id);
"""


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open (and create) the database with sane pragmas.

    WAL for concurrent read (web UI) + write (ingest); foreign keys ON so
    the cascade delete in the ingester actually fires. check_same_thread=False
    because the web app's sync route handlers run in a threadpool while the
    connection is opened in the middleware thread -- safe here since each
    request owns its own short-lived connection.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables if they do not exist + idempotent migrations."""
    conn.executescript(SCHEMA_SQL)
    # Migration for DBs created before the game-state feature: actions gains
    # point_index and a points table appears. ALTER TABLE ... ADD COLUMN is
    # idempotent-guarded via pragma inspection (older SQLite has no IF NOT
    # EXISTS for columns).
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(actions)")}
    if "point_index" not in cols:
        conn.execute("ALTER TABLE actions ADD COLUMN point_index INTEGER")
    conn.commit()
