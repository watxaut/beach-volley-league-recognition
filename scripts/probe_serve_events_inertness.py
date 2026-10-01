#!/usr/bin/env python3
"""Prove the serve emitters are INERT: the action stream must not move.

`src/analysis/serve_events.py` is a default-off observer family
(`serve_events_enabled = False`, `--serve-events` to switch on). The claim it
makes is stronger than "adds a key": with the emitters ON, the emitted ACTIONS
must be byte-identical to a run with them OFF, on the same device, in the same
process. Session 53 added the structural arm (`ServeContactProposer`) to that
family, so the claim needs re-proving.

Method: one sequential decode, two `FrameProcessor` instances fed the SAME
frames (the match is VFR, so this must not seek -- AGENTS.md §9), one with the
emitters off and one with them on, then compare the action lists field by field.
CPU is the deterministic device for this comparison (MPS jitter can flip a
gesture label on its own, AGENTS.md).

Usage::

    venv/bin/python scripts/probe_serve_events_inertness.py --from 1900 --to 2400
    venv/bin/python scripts/probe_serve_events_inertness.py --points 1,2,6,8
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.frame_processor import FrameProcessor  # noqa: E402


def _load_scorer():
    spec = importlib.util.spec_from_file_location(
        "score_serve_events", ROOT / "scripts" / "score_serve_events.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_S = _load_scorer()
MATCH_VIDEO, MATCH_CALIB = _S.MATCH_VIDEO, _S.MATCH_CALIB
production_config = _S.production_config


def _actions(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for action in result.get("actions") or []:
        out.append({k: action.get(k) for k in
                    ("frame_number", "action", "final_action", "team", "player_id",
                     "touch_number", "confidence", "gesture")})
    return out


def run_span(start: int, end: int, device: str) -> Tuple[List[Dict[str, Any]],
                                                         List[Dict[str, Any]],
                                                         int, bool]:
    """Decode [start, end] SEQUENTIALLY twice: emitters off, then on."""
    cap = cv2.VideoCapture(str(MATCH_VIDEO))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {MATCH_VIDEO}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frames: List[Any] = []
    for index in range(end + 1):
        ok, image = cap.read()
        if not ok:
            break
        if index >= start:
            frames.append((index, image))
    cap.release()

    base = dict(production_config(device))
    base["court_calibration_path"] = str(ROOT / MATCH_CALIB)

    off_cfg = dict(base, serve_events_enabled=False)
    off = FrameProcessor(off_cfg)
    off.setup_video_fps(fps)
    off.setup_video_dimensions(1920, 1080)
    off_actions: List[Dict[str, Any]] = []
    saw_key = False
    for index, image in frames:
        result = off.process_frame(image, index)
        off_actions += _actions(result)
        saw_key = saw_key or "serve_events" in result
    off_actions += _actions({"actions": off.flush_actions() or []})

    on_cfg = dict(base, serve_events_enabled=True)
    on = FrameProcessor(on_cfg)
    on.setup_video_fps(fps)
    on.setup_video_dimensions(1920, 1080)
    on_actions: List[Dict[str, Any]] = []
    events = 0
    for index, image in frames:
        result = on.process_frame(image, index)
        on_actions += _actions(result)
        events += len(result.get("serve_events") or [])
    on_actions += _actions({"actions": on.flush_actions() or []})
    events += len(on.get_serve_events() or [])
    return off_actions, on_actions, events, saw_key


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=1900)
    ap.add_argument("--to", dest="end", type=int, default=2400)
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()

    t0 = time.time()
    off, on, events, saw_key = run_span(args.start, args.end, args.device)
    same = json.dumps(off, sort_keys=True) == json.dumps(on, sort_keys=True)
    print(f"span f{args.start}-f{args.end} on {args.device} ({time.time()-t0:.0f}s)")
    print(f"  actions OFF {len(off)} | ON {len(on)} | serve events ON {events}")
    print(f"  'serve_events' key seen with the emitters OFF: {saw_key}")
    if same:
        print("  RESULT: action streams are byte-identical -> the observers are inert")
        return 0
    print("  RESULT: ACTION STREAMS DIFFER -- the emitters are not inert")
    for index, (a, b) in enumerate(zip(off, on)):
        if a != b:
            print(f"    first difference at action {index}:\n      OFF {a}\n      ON  {b}")
            break
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
