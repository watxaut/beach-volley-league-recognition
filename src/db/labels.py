"""Player labeling: map per-video track ids to real player names.

Track ids are per-video bootstrap artifacts (k-means on the first frames)
-- they are NOT stable across videos, so a label is always (video_key,
track_id) -> player. Labels are applied via the web UI after ingest and
survive re-ingest (the ingester never touches these tables).
"""

import sqlite3
from typing import Dict, List, Optional


def get_or_create_player(conn: sqlite3.Connection, name: str) -> int:
    """Return the player id for ``name``, creating the player if new."""
    name = name.strip()
    if not name:
        raise ValueError("Player name must not be empty")
    row = conn.execute("SELECT id FROM players WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    with conn:
        cur = conn.execute("INSERT INTO players (name) VALUES (?)", (name,))
    return cur.lastrowid


def set_label(
    conn: sqlite3.Connection,
    video_key: str,
    track_id: int,
    player_name: str,
    team: Optional[str] = None,
) -> int:
    """Create or update the (video_key, track_id) -> player label."""
    player_id = get_or_create_player(conn, player_name)
    with conn:
        conn.execute(
            """INSERT INTO video_players (video_key, track_id, player_id, team)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(video_key, track_id)
               DO UPDATE SET player_id = excluded.player_id, team = excluded.team""",
            (video_key, track_id, player_id, team),
        )
    return player_id


def clear_label(conn: sqlite3.Connection, video_key: str, track_id: int) -> None:
    """Remove one label (the player row itself is kept)."""
    with conn:
        conn.execute(
            "DELETE FROM video_players WHERE video_key = ? AND track_id = ?",
            (video_key, track_id),
        )


def labels_for_video(conn: sqlite3.Connection, video_key: str) -> Dict[int, Dict]:
    """Existing labels for a video: track_id -> {player_id, name, team}."""
    rows = conn.execute(
        """SELECT vp.track_id, vp.team, p.id AS player_id, p.name
           FROM video_players vp JOIN players p ON p.id = vp.player_id
           WHERE vp.video_key = ?""",
        (video_key,),
    ).fetchall()
    return {
        r["track_id"]: {
            "player_id": r["player_id"],
            "name": r["name"],
            "team": r["team"],
        }
        for r in rows
    }


def tracks_in_video(conn: sqlite3.Connection, video_key: str) -> List[int]:
    """Sorted track ids that appear in this video's actions or spikes."""
    rows = conn.execute(
        """SELECT DISTINCT track_id FROM actions WHERE video_key = ? AND track_id IS NOT NULL
           UNION
           SELECT DISTINCT track_id FROM spikes WHERE video_key = ? AND track_id IS NOT NULL
           ORDER BY track_id""",
        (video_key, video_key),
    ).fetchall()
    return [r["track_id"] for r in rows]


def all_players(conn: sqlite3.Connection) -> List[Dict]:
    """All known players with the videos they are labeled in."""
    return [
        dict(r)
        for r in conn.execute(
            """SELECT p.id, p.name,
                      COUNT(DISTINCT vp.video_key) AS n_videos
               FROM players p
               LEFT JOIN video_players vp ON vp.player_id = p.id
               GROUP BY p.id
               ORDER BY p.name"""
        ).fetchall()
    ]
