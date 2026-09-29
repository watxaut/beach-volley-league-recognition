"""Off-by-default diagnostic capture for the shared frame path (task T4).

The loss waterfall (``scripts/waterfall.py``) needs to know, for every GT
contact, at which stage the contact died: raw detection -> track admission ->
trajectory candidate -> gate -> attribution -> label.  Today those
intermediates exist only inside the components that consume them, so the only
way to see them was to re-implement the pipeline in a probe script (the eval
-vs-pipeline skew bug class, AGENTS.md §2).

This module adds an **inert** sink instead:

* ``DiagRecorder`` accumulates per-frame records and writes one JSON object
  per line (JSONL) at the end of the run;
* components get a ``diag_enabled`` flag and a ``pop_diag()`` accessor.  When
  ``diag_enabled`` is False (the default, and every production/batch/live path
  unless ``diag_dump`` is configured) nothing is recorded and no computed
  value is touched -- the hooks are plain ``if self.diag_enabled:`` guards
  next to values that already exist.

Record schema (one JSONL line per frame, plus a first ``meta`` line)::

    {"frame": 1234,
     "ball_dets":  [{"center": [x, y], "conf": 0.8, "persist": 0.1,
                     "suspect": false, "removed": false}, ...],
     "ball_track": {"state": "tracked|predicted|unlocked|none", "locked": true,
                    "missing": 0, "center": [x, y], "conf": 0.7,
                    "reason": "locked_admitted"},
     "players":   [{"track_id": 1, "team": "A", "bbox": [...], "predicted": false}],
     "actions":   [{"frame": 1230, "action": "dig", "gesture": "bump_set",
                     "team": "A", "track_id": 2, "touch_number": 1, ...}],
     "candidates": [{"frame": 1230, "seen_at": 1237, "stage": "accepted|rejected",
                     "reason": "reach|no_player|context_confidence|...",
                     "kind": "bounce|drive|redirect|reentry", ...}]}

``actions`` and ``candidates`` are keyed by their CONTACT frame (the value the
classifier reports as ``frame_number``), not by the frame the contact was
confirmed on, so a consumer can look a contact up in one place.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

#: Bumped when the record shape changes; recorded in the file header.
SCHEMA_VERSION = 1


def _new_frame_record(frame: int) -> Dict[str, Any]:
    return {
        "frame": int(frame),
        "ball_dets": [],
        "ball_track": None,
        "players": [],
        "actions": [],
        "candidates": [],
    }


class DiagRecorder:
    """Collect per-frame diagnostics and write them as JSONL.

    Inert unless constructed: ``FrameProcessor`` only builds one when the
    ``diag_dump`` config key is set (``--diag-dump`` on the CLI).
    """

    def __init__(self, path: str, video: str = "", fps: Optional[float] = None,
                 total_frames: Optional[int] = None):
        self.path = str(path)
        self.video = video
        self.fps = fps
        self.total_frames = total_frames
        self._frames: Dict[int, Dict[str, Any]] = {}
        self._closed = False

    # -- recording ---------------------------------------------------------

    def add_frame(self, frame_index: int, data: Dict[str, Any]) -> None:
        """Merge one frame's directly observed state (dets, tracker, players,
        emitted actions) into the buffer."""
        rec = self._frames.setdefault(int(frame_index), _new_frame_record(frame_index))
        for key in ("ball_dets", "ball_track", "players", "actions", "candidates"):
            if key in data:
                rec[key] = data[key]

    def add_section(self, name: str, payload: Any) -> None:
        """Merge a component-side section (detector/tracker/classifier pops).

        Sections carry their own contact frame when they have one; otherwise
        they are attached to ``seen_at`` (the processing frame).
        """
        if isinstance(payload, list):
            items: List[Dict[str, Any]] = [p for p in payload if isinstance(p, dict)]
        elif isinstance(payload, dict):
            items = [payload]
        else:
            return
        for item in items:
            frame = item.get("frame", item.get("seen_at"))
            if frame is None:
                continue
            rec = self._frames.setdefault(int(frame), _new_frame_record(frame))
            rec.setdefault(name, []).append(item)

    # -- output ------------------------------------------------------------

    def write(self) -> str:
        """Write the JSONL dump and return the path. Idempotent."""
        if self._closed:
            return self.path
        parent = os.path.dirname(os.path.abspath(self.path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        header = {
            "meta": {
                "schema_version": SCHEMA_VERSION,
                "kind": "volley_recognition_diag_dump",
                "video": self.video,
                "fps": self.fps,
                "total_frames": self.total_frames,
                "frames_recorded": len(self._frames),
                "note": "OFF-BY-DEFAULT diagnostic capture; produced from the same "
                        "FrameProcessor.process_frame path as production. Keys are "
                        "observations of values the pipeline already computed.",
            }
        }
        with open(self.path, "w") as f:
            f.write(json.dumps(header) + "\n")
            for frame in sorted(self._frames):
                rec = self._frames[frame]
                # Drop empty containers so a frame with nothing interesting is
                # one short line.
                out = {k: v for k, v in rec.items() if v not in (None, [], {})}
                f.write(json.dumps(out) + "\n")
        self._closed = True
        return self.path


def load_diag(path: str) -> Dict[str, Any]:
    """Read a diag dump -> ``{"meta": {...}, "frames": {frame: record}}``."""
    meta: Dict[str, Any] = {}
    frames: Dict[int, Dict[str, Any]] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "meta" in rec and len(rec) == 1:
                meta = rec["meta"]
                continue
            frames[int(rec["frame"])] = rec
    return {"meta": meta, "frames": frames}
