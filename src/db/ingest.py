"""Ingest pipeline_output.json files into the analysis database.

Separate process from extraction by design (owner requirement): extraction
writes files, this reads them. Usage::

    python -m src.db.ingest video_entreno_3          # resolves output/<stem>/pipeline_output.json
    python -m src.db.ingest output/video_entreno_3   # an output directory
    python -m src.db.ingest output/                  # sweep ALL output dirs
    python -m src.db.ingest output/foo/pipeline_output.json
    python -m src.db.ingest output/ --db data/volley.db

Upsert semantics: re-ingesting a video_key transactionally replaces that
video's actions/spikes rows. Player labels (video_players) and the players
table are never modified here.
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union

from .schema import DEFAULT_DB_PATH, connect, init_db

SCHEMA_VERSION = 1


class IngestError(Exception):
    """Raised when a pipeline_output.json violates the contract."""


def resolve_json_paths(target: Union[str, Path]) -> List[Path]:
    """Resolve a CLI target to a list of pipeline_output.json paths.

    Accepts: the JSON file itself, an output directory containing it, the
    bare video stem (resolved against output/<stem>/), or a parent directory
    (e.g. output/) whose subdirectories are swept.
    """
    target = Path(target)

    # Bare video stem ("video_entreno_3") -> output/<stem>/pipeline_output.json
    if not target.exists() and (Path("output") / target / "pipeline_output.json").exists():
        target = Path("output") / target

    if target.is_file():
        return [target]

    if target.is_dir():
        direct = target / "pipeline_output.json"
        if direct.exists():
            return [direct]
        # Sweep subdirectories (sorted for deterministic ingest order).
        found = sorted(
            p for p in target.glob("*/pipeline_output.json") if p.is_file()
        )
        if found:
            return found
        raise FileNotFoundError(f"No pipeline_output.json under {target}/")

    raise FileNotFoundError(f"Target not found: {target} "
                            f"(expected a stem, output dir, or JSON path)")


def validate_payload(payload: Dict) -> None:
    """Check the canonical-JSON contract before touching the database."""
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise IngestError(
            f"Unsupported schema_version {payload.get('schema_version')!r} "
            f"(expected {SCHEMA_VERSION})"
        )
    video = payload.get("video") or {}
    if not video.get("key"):
        raise IngestError("video.key (the video stem) is missing")
    if not isinstance(payload.get("actions"), list):
        raise IngestError("actions must be a list")
    if not isinstance(payload.get("spikes"), list):
        raise IngestError("spikes must be a list")


def ingest_payload(conn, payload: Dict) -> Dict[str, int]:
    """Upsert one canonical payload. Returns row counts written."""
    validate_payload(payload)

    video = payload["video"]
    video_key = video["key"]
    actions: List[Dict] = payload["actions"]
    spikes: List[Dict] = payload["spikes"]
    fps = video.get("fps") or 0.0

    with conn:  # single transaction: replace derived rows, keep labels
        # UPSERT the videos row (never DELETE -- the ON DELETE CASCADE would
        # wipe video_players, and labels must survive reprocessing).
        conn.execute(
            """INSERT INTO videos (video_key, path, fps, width, height,
                                   total_frames, processed_at,
                                   pipeline_version, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(video_key) DO UPDATE SET
                   path = excluded.path,
                   fps = excluded.fps,
                   width = excluded.width,
                   height = excluded.height,
                   total_frames = excluded.total_frames,
                   processed_at = excluded.processed_at,
                   pipeline_version = excluded.pipeline_version,
                   ingested_at = excluded.ingested_at""",
            (
                video_key,
                video.get("path") or "",
                fps,
                video.get("width"),
                video.get("height"),
                video.get("total_frames"),
                payload.get("processed_at"),
                payload.get("pipeline_version"),
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        # Replace this video's derived rows only (other videos untouched).
        conn.execute("DELETE FROM actions WHERE video_key = ?", (video_key,))
        conn.execute("DELETE FROM spikes WHERE video_key = ?", (video_key,))

        conn.executemany(
            """INSERT INTO actions (video_key, frame, ts, track_id, action,
                                    gesture, confidence, team,
                                    team_in_possession, touch_number,
                                    rally_id, contact_kind,
                                    contact_x, contact_y)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    video_key,
                    a.get("frame_number", 0) or 0,
                    round((a.get("frame_number", 0) or 0) / fps, 3) if fps else None,
                    a.get("track_id"),
                    a.get("action") or "unknown",
                    a.get("gesture"),
                    a.get("confidence"),
                    a.get("team"),
                    a.get("team_in_possession"),
                    a.get("touch_number"),
                    a.get("rally_id"),
                    a.get("contact_kind"),
                    (a.get("contact_point") or [None, None])[0],
                    (a.get("contact_point") or [None, None])[1],
                )
                for a in actions
            ],
        )

        conn.executemany(
            """INSERT INTO spikes (video_key, frame, track_id, team,
                                   spike_type, attack_zone, outcome,
                                   landing_zone, dug_zone, exit_speed_px,
                                   flight_frames, resolution_frame)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    video_key,
                    s.get("frame", 0) or 0,
                    s.get("track_id"),
                    s.get("team"),
                    s.get("spike_type"),
                    s.get("attack_zone"),
                    s.get("outcome"),
                    s.get("landing_zone"),
                    s.get("dug_zone"),
                    s.get("exit_speed_px"),
                    s.get("flight_frames"),
                    s.get("resolution_frame"),
                )
                for s in spikes
            ],
        )

    return {"video_key_len": 1, "actions": len(actions), "spikes": len(spikes)}


def ingest_file(conn, json_path: Path) -> Dict[str, int]:
    """Load one pipeline_output.json and upsert it."""
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    counts = ingest_payload(conn, payload)
    logging.getLogger(__name__).info(
        f"Ingested {json_path}: +{counts['actions']} actions, "
        f"+{counts['spikes']} spikes"
    )
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upsert pipeline_output.json files into the analysis DB"
    )
    parser.add_argument(
        "target",
        help="Video stem, output directory, parent directory to sweep, "
             "or a pipeline_output.json path",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"Database path (default: {DEFAULT_DB_PATH})",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)

    try:
        json_paths = resolve_json_paths(args.target)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    conn = connect(Path(args.db))
    init_db(conn)

    total_actions = total_spikes = 0
    for path in json_paths:
        try:
            counts = ingest_file(conn, path)
        except (IngestError, json.JSONDecodeError, KeyError) as e:
            print(f"error: {path}: {e}", file=sys.stderr)
            conn.close()
            return 1
        total_actions += counts["actions"]
        total_spikes += counts["spikes"]
    conn.close()

    n = len(json_paths)
    print(f"Ingested {n} video(s): +{total_actions} actions, +{total_spikes} spikes -> {args.db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
