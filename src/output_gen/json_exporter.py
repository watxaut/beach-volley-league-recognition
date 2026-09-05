"""Canonical JSON exporter for pipeline results.

Writes ``pipeline_output.json`` next to the CSVs in the output directory.
This is the machine-readable contract consumed by the database ingester
(``src.db.ingest``): unlike the human-facing CSVs it is LOSSLESS -- every
emitted action keeps its full field set (team, touch_number, rally_id,
contact_kind, contact_point, ...) and spike records keep their enrichment
minus the bulky flight arrays.

Presentation-only: reads ``analysis_results``, never touches the action
stream (same rule as the CSV exporter and the live-debug spike log).
"""

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Spike record fields persisted in the JSON (the ``flight`` array and other
# render-only keys are deliberately dropped -- bulky, no analytic use).
SPIKE_FIELDS = (
    "frame",
    "track_id",
    "player_id",
    "team",
    "spike_type",
    "attack_zone",
    "outcome",
    "landing_zone",
    "dug_zone",
    "exit_speed_px",
    "flight_frames",
    "resolution_frame",
)

# Player-thumbnail snapshots per track: frames the ingester crops from the
# video for the labeling UI. Action frames first (identifiable moments),
# then an evenly-spread frame for a neutral stance.
SNAPSHOTS_PER_TRACK = 3


def git_version() -> Optional[str]:
    """Short git hash of the working tree, or None outside a repo."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def _zone_key(zone: Optional[Dict[str, Any]]) -> Optional[str]:
    """{"side": "B", "zone": 3} -> "B3" (None passes through)."""
    if not zone:
        return None
    return f"{zone['side']}{zone['zone']}"


class JSONExporter:
    """Exports the canonical machine-readable pipeline output."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def export(
        self,
        analysis_results: Dict[str, Any],
        output_path: Path,
        pipeline_version: Optional[str] = None,
    ) -> None:
        """Write ``pipeline_output.json``.

        Args:
            analysis_results: Complete results from VideoProcessor.
            output_path: Destination path (conventionally
                ``<output_dir>/pipeline_output.json``).
            pipeline_version: Version stamp; defaults to the git hash.
        """
        payload = self.build_payload(analysis_results, pipeline_version)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        self.logger.info(f"Canonical JSON written: {output_path}")

    def build_payload(
        self,
        analysis_results: Dict[str, Any],
        pipeline_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assemble the canonical payload dict (separated for tests)."""
        video_info = analysis_results.get("video_info", {})
        path = video_info.get("path", "")

        actions = self.collect_actions(analysis_results)
        spikes = self.collect_spikes(analysis_results)

        return {
            "schema_version": 1,
            "video": {
                # The video stem is the unique video key everywhere (matches
                # calibrations/<stem>.json and output/<stem>/ conventions).
                "key": Path(path).stem if path else None,
                "path": path,
                "fps": video_info.get("fps"),
                "width": video_info.get("width"),
                "height": video_info.get("height"),
                "total_frames": video_info.get("total_frames"),
            },
            "processed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pipeline_version": pipeline_version if pipeline_version is not None else git_version(),
            "actions": actions,
            "spikes": spikes,
            "snapshots": self.collect_snapshots(analysis_results, actions),
            "game_state": self.collect_game_state(analysis_results),
        }

    def collect_actions(self, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """All emitted actions with their full field set, frame-ordered.

        Actions are attached to frame_results in emission order (the final
        contact arrives via the end-of-video flush on the last frame); each
        action carries its own ``frame_number`` (the true contact frame).
        """
        actions: List[Dict[str, Any]] = []
        for frame_result in analysis_results.get("frame_results", []):
            for action in frame_result.get("actions", []):
                actions.append({
                    "track_id": action.get("track_id"),
                    "player_id": action.get("player_id"),
                    "action": action.get("action"),
                    "gesture": action.get("gesture"),
                    "confidence": action.get("confidence"),
                    "frame_number": action.get("frame_number", frame_result.get("frame_index")),
                    "contact_point": action.get("contact_point"),
                    "team": action.get("team"),
                    "team_in_possession": action.get("team_in_possession"),
                    "touch_number": action.get("touch_number"),
                    "rally_id": action.get("rally_id"),
                    "contact_kind": action.get("contact_kind"),
                })
        actions.sort(key=lambda a: (a.get("frame_number") or 0,))
        # Annotate each action with the confirmed point it belongs to (-1 =
        # outside any point: practice / between points -- consumers use this
        # to avoid counting actions when no point is on).
        points = analysis_results.get("game_state", {}).get("points", [])
        for action in actions:
            af = action.get("frame_number")
            action["point_index"] = next(
                (
                    i
                    for i, p in enumerate(points)
                    if p["start_frame"] <= af <= p["end_frame"]
                ),
                -1,
            )
        return actions

    def collect_spikes(self, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Spike enrichment records, zones flattened to "B3"-style keys."""
        spikes: List[Dict[str, Any]] = []
        for r in analysis_results.get("spike_analysis", []):
            rec = {}
            for field in SPIKE_FIELDS:
                value = r.get(field)
                if field in ("attack_zone", "landing_zone", "dug_zone"):
                    value = _zone_key(value)
                rec[field] = value
            spikes.append(rec)
        spikes.sort(key=lambda s: (s.get("frame") or 0,))
        return spikes

    def collect_game_state(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """Confirmed point segments from the game on/off state machine."""
        points = analysis_results.get("game_state", {}).get("points", [])
        return {
            "point_count": len(points),
            "points": [
                {
                    "start_frame": p["start_frame"],
                    "end_frame": p["end_frame"],
                    "n_actions": p.get("n_actions", 0),
                }
                for p in points
            ],
        }

    def collect_snapshots(
        self, analysis_results: Dict[str, Any], actions: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Per-track thumbnail snapshots (frame + bbox) for the labeling UI.

        The UI crops these frames out of the source video so the owner can
        see WHO each track id is before naming them. Up to
        SNAPSHOTS_PER_TRACK per track: appearances nearest the track's own
        action frames first (a dig/spike moment is more identifiable than a
        blurred coast), then the track's mid-video appearance for a neutral
        stance. Frame-ordered, deduplicated.
        """
        from collections import defaultdict

        # track_id -> ordered [(frame, bbox)] from the per-frame track states
        appearances: Dict[int, List[tuple]] = defaultdict(list)
        for frame_result in analysis_results.get("frame_results", []):
            frame = frame_result.get("frame_index", 0)
            for p in frame_result.get("tracked_players", []):
                tid = p.get("track_id")
                bbox = p.get("bbox")
                if tid is not None and bbox and len(bbox) == 4:
                    appearances[tid].append((frame, [round(v, 1) for v in bbox]))

        # track_id -> ordered action frames
        action_frames: Dict[int, List[int]] = defaultdict(list)
        for a in actions:
            tid = a.get("track_id")
            if tid is not None and a.get("frame_number") is not None:
                action_frames[tid].append(a["frame_number"])

        snapshots: Dict[str, List[Dict[str, Any]]] = {}
        for tid, appearances_list in sorted(appearances.items()):
            chosen: List[tuple] = []

            def nearest_appearance(target: int) -> Optional[tuple]:
                if not appearances_list:
                    return None
                return min(appearances_list, key=lambda fr: abs(fr[0] - target))

            # Action moments first (cap at SNAPSHOTS_PER_TRACK - 1, keep one
            # slot for the neutral mid-video stance).
            for af in action_frames.get(tid, [])[: SNAPSHOTS_PER_TRACK - 1]:
                pick = nearest_appearance(af)
                if pick and pick not in chosen:
                    chosen.append(pick)
            # Neutral stance: the appearance closest to the track's midpoint.
            if appearances_list:
                mid_frame = (appearances_list[0][0] + appearances_list[-1][0]) // 2
                pick = nearest_appearance(mid_frame)
                if pick and pick not in chosen:
                    chosen.append(pick)

            chosen.sort(key=lambda fr: fr[0])
            snapshots[str(tid)] = [
                {"frame": frame, "bbox": bbox} for frame, bbox in chosen[:SNAPSHOTS_PER_TRACK]
            ]
        return snapshots
