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
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union

import cv2
import numpy as np

from .schema import DEFAULT_DB_PATH, connect, init_db

SCHEMA_VERSION = 1

# Labeling-UI thumbnails: cropped player snapshots materialized next to the
# DB (data/thumbs/<video_key>/track_<id>.png) from the payload's snapshots.
THUMB_HEIGHT_PX = 150
THUMB_GAP_PX = 4
BBOX_PAD_FRACTION = 0.15


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
        conn.execute("DELETE FROM points WHERE video_key = ?", (video_key,))

        gs = payload.get("game_state") or {}
        conn.executemany(
            """INSERT INTO points (video_key, point_index, start_frame,
                                   end_frame, n_actions)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (video_key, i, p.get("start_frame", 0), p.get("end_frame", 0),
                 p.get("n_actions", 0))
                for i, p in enumerate(gs.get("points", []))
            ],
        )

        conn.executemany(
            """INSERT INTO actions (video_key, frame, ts, track_id, action,
                                    gesture, confidence, team,
                                    team_in_possession, touch_number,
                                    rally_id, contact_kind,
                                    contact_x, contact_y, point_index)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    a.get("point_index"),
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


def _resolve_video_path(raw_path: str) -> Optional[Path]:
    """Locate the source video (paths are recorded relative to the repo root
    at extraction time; try as-is, then relative to ./output and ./)."""
    if not raw_path:
        return None
    candidates = [Path(raw_path)]
    if not Path(raw_path).is_absolute():
        candidates += [Path("..") / raw_path, Path.cwd().parent / raw_path]
    for c in candidates:
        if c.is_file():
            return c
    return None


def write_thumbnails(payload: Dict, thumbs_root: Path) -> Dict[str, Path]:
    """Materialize per-track thumbnail strips for the labeling UI.

    Wipes the video's thumbs directory first (stale tracks from previous
    runs must not survive), then crops each track's snapshot frames out of
    the source video into one horizontal strip per track. Returns
    track_id -> written path; empty when the video file is unavailable
    (the UI then falls back to a placeholder).
    """
    video_key = payload.get("video", {}).get("key")
    snapshots = payload.get("snapshots") or {}
    video_dir = Path(thumbs_root) / str(video_key)

    if not video_key:
        return {}
    shutil.rmtree(video_dir, ignore_errors=True)
    if not snapshots:
        return {}

    video_path = _resolve_video_path(payload["video"].get("path", ""))
    if video_path is None:
        logging.getLogger(__name__).warning(
            f"Thumbnails skipped for {video_key}: video file not found "
            f"({payload['video'].get('path')!r})"
        )
        return {}

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logging.getLogger(__name__).warning(
            f"Thumbnails skipped for {video_key}: cannot open {video_path}"
        )
        return {}

    written: Dict[str, Path] = {}
    try:
        video_dir.mkdir(parents=True, exist_ok=True)
        for track_id, snaps in snapshots.items():
            crops = []
            for snap in snaps[:3]:
                frame_idx = int(snap.get("frame", 0))
                bbox = snap.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                h, w = frame.shape[:2]
                x1, y1, x2, y2 = bbox
                pad_x = (x2 - x1) * BBOX_PAD_FRACTION
                pad_y = (y2 - y1) * BBOX_PAD_FRACTION
                x1 = max(0, int(x1 - pad_x))
                y1 = max(0, int(y1 - pad_y))
                x2 = min(w, int(x2 + pad_x))
                y2 = min(h, int(y2 + pad_y))
                if x2 - x1 < 8 or y2 - y1 < 8:
                    continue
                crop = frame[y1:y2, x1:x2]
                # Far-side players project as thin boxes; widen very skinny
                # crops (min aspect 0.45 w/h, centered on the bbox) so faces
                # stay recognizable in the strip.
                ch, cw = crop.shape[:2]
                min_w = int(ch * 0.45)
                if cw < min_w:
                    cx = (x1 + x2) // 2
                    nx1 = max(0, cx - min_w // 2)
                    nx2 = min(w, nx1 + min_w)
                    nx1 = max(0, nx2 - min_w)
                    crop = frame[y1:y2, nx1:nx2]
                scale = THUMB_HEIGHT_PX / crop.shape[0]
                crop = cv2.resize(
                    crop, (max(1, int(crop.shape[1] * scale)), THUMB_HEIGHT_PX)
                )
                crops.append(crop)
            if not crops:
                continue
            gap = np.full((THUMB_HEIGHT_PX, THUMB_GAP_PX, 3), 24, dtype=np.uint8)
            strip = crops[0]
            for crop in crops[1:]:
                strip = np.hstack([strip, gap, crop])
            out_path = video_dir / f"track_{track_id}.png"
            if cv2.imwrite(str(out_path), strip):
                written[str(track_id)] = out_path
    finally:
        cap.release()
    return written


def ingest_file(conn, json_path: Path, thumbs_root: Optional[Path] = None) -> Dict[str, int]:
    """Load one pipeline_output.json and upsert it."""
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    counts = ingest_payload(conn, payload)
    if thumbs_root is not None:
        thumbs = write_thumbnails(payload, thumbs_root)
        if thumbs:
            key = payload.get("video", {}).get("key")
            logging.getLogger(__name__).info(
                f"Thumbnails for {key}: {len(thumbs)} track(s)"
            )
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
    parser.add_argument(
        "--no-thumbs",
        action="store_true",
        help="Skip writing labeling thumbnails (data/thumbs/)",
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
    thumbs_root = None if args.no_thumbs else Path(args.db).parent / "thumbs"

    total_actions = total_spikes = 0
    for path in json_paths:
        try:
            counts = ingest_file(conn, path, thumbs_root=thumbs_root)
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
