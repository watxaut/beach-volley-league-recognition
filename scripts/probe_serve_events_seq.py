#!/usr/bin/env python3
"""G4/M2 -- the far-serve ingredients and the OPENER GATE, on a seek-free pass.

Why this script exists
----------------------
Two things forced a rewrite of the G4 measurement.

1. **Frame alignment.**  Every windowed G4 probe decodes with
   ``cv2.CAP_PROP_POS_FRAMES`` seeks.  The 20260920 match is VFR (25.67 fps
   content in a 30.12 fps container, AGENTS.md §7) and the seek is therefore
   FRAME-UNRELIABLE: measured against a sequential decode, seeks land
   **-28..+30 frames** from the requested index (``docs/g4_far_serve_alignment.md``)
   -- twice the +-15 f tolerance every score here uses.  This script decodes the
   file ONCE, sequentially, and scores against the true decode index.

2. **The ball is not absent.**  The M1 probe
   (``scripts/probe_far_roi_ball.py``) showed the fine-tuned detector sees a
   15-21 px ball in **23 of 31** frames at P1's far serve and in 14-31 of 31 in
   every one of the 17 far-serve windows (only P31 f24543 is a real miss,
   2/31).  So the documented "the far ball is seen on 0-1 frames in 8/17
   windows" is the **tracker's** frame count, not the detector's: the ball is
   there, the tracker will not lock it (a far toss creeps 1.6-6.7 px/f under
   ``lock_min_speed = 8``, T5) and the contact geometry refuses it anyway.

So this pass records every ingredient a structural far-serve proposer could use,
in one decode, so the rules can be swept offline without re-running anything:

* ``ball``      -- raw ball candidates (pre-static-suppression): cx, cy, w, conf
* ``ball_track``-- the tracked ball (None when unlocked)
* ``people``    -- in-area + off-area person detections with a runway-band flag
* ``actions``   -- every emitted contact (the opener gap is measured on these)
* ``game``      -- the GAME_ON / GAME_OFF state per frame

and scores, on the same windows:

* **baseline** -- the G4 conjunction as emitted (no gate);
* **M2 opener gate** -- a serve opens a rally, so a candidate only counts when no
  contact was emitted in the preceding ``--opener-gap`` frames.  On this match
  openers follow >=153 f of dead time and the largest mid-rally gap is 134 f
  (``GAP_SERVE_MIN=143``, session 28): a *structural* property, not a fit.

Usage::

    venv/bin/python scripts/probe_serve_events_seq.py --device mps
    venv/bin/python scripts/probe_serve_events_seq.py --device cpu --out output/g4/seq_cpu.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.frame_processor import FrameProcessor  # noqa: E402


def _load_scorer():
    """``scripts/`` is not a package; load the G4 scorer by path."""
    spec = importlib.util.spec_from_file_location(
        "score_serve_events", ROOT / "scripts" / "score_serve_events.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_SCORER = _load_scorer()
MATCH_CALIB = _SCORER.MATCH_CALIB
MATCH_GT = _SCORER.MATCH_GT
MATCH_VIDEO = _SCORER.MATCH_VIDEO
load_control_contacts = _SCORER.load_control_contacts
load_far_serves = _SCORER.load_far_serves
production_config = _SCORER.production_config

#: Frames of emitted-contact silence before a candidate that make it a
#: rally-opener candidate.  Validated on this match: openers >= 153 f, largest
#: mid-rally gap 134 f (session 28).  The gate is swept, never trusted blind.
DEFAULT_OPENER_GAP = 143
WINDOW_BEFORE = 90
WINDOW_AFTER = 60


def sequential_pass(
    config: Dict[str, Any],
    fps: float,
    start: int = 0,
    end: Optional[int] = None,
    diag_path: Optional[str] = None,
    verbose_every: int = 2000,
) -> Dict[str, Any]:
    """Decode [start, end] SEQUENTIALLY through ONE FrameProcessor.

    The AGENTS.md "Infra rule" for VFR files, honoured here: no seeks, one
    processor, so the trackers see the same causal stream ``src/main.py``
    produces and every frame index is the true decode index.
    """
    cap = cv2.VideoCapture(str(MATCH_VIDEO))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {MATCH_VIDEO}")
    if start:
        # Seeking is frame-unreliable; walk there.  Only used to skip a prefix.
        for _ in range(start):
            if not cap.read()[0]:
                raise RuntimeError("short read while walking to the start frame")

    config = dict(config)
    config["court_calibration_path"] = str(ROOT / MATCH_CALIB)
    config["serve_events_enabled"] = True
    if diag_path:
        config["diag_dump"] = str(ROOT / diag_path)

    processor = FrameProcessor(config)
    processor.setup_video_fps(fps)
    processor.setup_video_dimensions(1920, 1080)

    # ServeRunway, for the band test on raw person boxes (the same geometry the
    # G4 emitter uses -- see src/analysis/serve_events.py).
    from src.analysis.serve_events import ServeRunway
    calib = json.loads((ROOT / MATCH_CALIB).read_text())
    runway = ServeRunway(calib["court_corners"], calib.get("midcourt_points"))

    def region_of(bbox) -> str:
        """``runway`` / ``court`` / ``out`` for a person's ground point."""
        return runway.classify(((bbox[0] + bbox[2]) / 2.0, bbox[3])) or "out"

    events: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    per_frame: Dict[int, Dict[str, Any]] = {}
    ball_seen: Dict[int, int] = {}          # frame -> raw ball candidates (pre-suppression)
    ball_locked: Dict[int, int] = {}       # frame -> 1 when a track is out
    game_on: List[int] = []                 # frames the game state says GAME_ON
    frame = start
    t0 = time.time()
    while end is None or frame <= end:
        ok, image = cap.read()
        if not ok:
            break
        result = processor.process_frame(image, frame)
        events.extend(result.get("serve_events") or [])
        for action in result.get("actions") or []:
            actions.append({
                "frame": int(action.get("frame_number", frame)),
                "seen_at": frame,
                "action": action.get("action"),
                "team": action.get("team"),
                "final_action": action.get("final_action"),
            })
        if processor.ball_detector is not None:
            n = len(processor.ball_detector.raw_detections or [])
            if n:
                ball_seen[frame] = n
        tracked = result.get("tracked_ball")
        if tracked and not tracked.get("predicted", False):
            ball_locked[frame] = 1
        state = (result.get("game_state") or {}).get("current_state")
        if state == "game_on":
            game_on.append(frame)
        per_frame[frame] = {
            "ball": [[round(d["center"][0], 1), round(d["center"][1], 1),
                      int(d["bbox"][2] - d["bbox"][0]), round(d["confidence"], 3)]
                     for d in (processor.ball_detector.raw_detections or [])],
            "ball_track": None if not tracked else [
                round(tracked.get("center", [0, 0])[0], 1),
                round(tracked.get("center", [0, 0])[1], 1),
                int(tracked.get("bbox", [0, 0, 0, 0])[2]
                    - tracked.get("bbox", [0, 0, 0, 0])[0]),
            ],
            "people": [
                [round(d["center"][0], 1), round(d["bbox"][3], 1),
                 int(d["bbox"][2] - d["bbox"][0]), int(d["bbox"][3] - d["bbox"][1]),
                 round(d.get("confidence", 0.0), 3), region_of(d["bbox"])]
                for d in (list(result.get("player_detections") or [])
                          + list(processor.player_detector.off_area_detections))
            ],
            "game": state,
        }
        if verbose_every and frame % verbose_every == 0:
            print(f"  f{frame}  {time.time()-t0:.0f}s  "
                  f"({(frame-start)/max(1e-9,time.time()-t0):.1f} fps)", flush=True)
        frame += 1
    cap.release()

    for action in processor.flush_actions() or []:
        actions.append({
            "frame": int(action.get("frame_number", frame)),
            "seen_at": frame,
            "action": action.get("action"),
            "team": action.get("team"),
            "final_action": action.get("final_action"),
        })
    events.extend(processor.get_serve_events())
    if processor.diag is not None:
        processor.close_diagnostics()

    # The per-frame stream and the roll-up overlap; dedup as the G4 scorer does.
    seen, unique = set(), []
    for event in events:
        key = (event["type"], event["frame"], event.get("contact_frame"),
               event.get("onset_frame"), event.get("start_frame"),
               event.get("evidence_frame"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)
    unique.sort(key=lambda e: e["frame"])
    actions.sort(key=lambda a: (a["frame"], a["seen_at"]))
    print(f"pass done: {frame-start} frames in {time.time()-t0:.0f}s; "
          f"{len(unique)} serve events, {len(actions)} emitted actions")
    return {
        "events": unique,
        "actions": actions,
        "ball_seen": ball_seen,
        "ball_locked": ball_locked,
        "game_on": game_on,
        "per_frame": per_frame,
        "first_frame": start,
        "last_frame": frame - 1,
        "seconds": round(time.time() - t0, 1),
    }


def _prev_action_frame(actions: List[Dict[str, Any]], frame: int) -> Optional[int]:
    """Last emitted contact frame strictly before ``frame`` (bisect)."""
    lo, hi = 0, len(actions)
    while lo < hi:
        mid = (lo + hi) // 2
        if actions[mid]["frame"] < frame:
            lo = mid + 1
        else:
            hi = mid
    return actions[lo - 1]["frame"] if lo else None


def _in_game_on(game_on: List[int], frame: int, radius: int = 2) -> bool:
    import bisect
    i = bisect.bisect_left(game_on, frame)
    return any(abs(game_on[j] - frame) <= radius
               for j in range(i, min(len(game_on), i + 2 * radius + 1)))


def score_windows(
    pass_result: Dict[str, Any],
    windows: List[Dict[str, Any]],
    tolerance: int = 15,
    opener_gap: int = DEFAULT_OPENER_GAP,
) -> List[Dict[str, Any]]:
    """Per-window event coverage + the opener-gate verdict for every candidate."""
    events = pass_result["events"]
    actions = pass_result["actions"]
    ball_seen = pass_result["ball_seen"]
    ball_locked = pass_result["ball_locked"]
    game_on = pass_result["game_on"]
    rows = []
    for window in windows:
        c = window["frame"]
        lo, hi = c - WINDOW_BEFORE, c + WINDOW_AFTER
        in_contact = lambda f: abs(f - c) <= tolerance  # noqa: E731
        in_window = lambda f: lo <= f <= hi  # noqa: E731
        candidates = [e for e in events if e["type"] == "serve_candidate" and in_window(e["frame"])]
        flights = [e for e in events if e["type"] == "far_flight" and in_window(e["frame"])]
        runway = [e for e in events if e["type"] == "runway_occupant" and in_window(e["frame"])]

        annotated = []
        for event in candidates:
            frame = event["frame"]
            prev = _prev_action_frame(actions, frame)
            gap = None if prev is None else frame - prev
            annotated.append({
                "frame": frame,
                "contact_frame": event.get("contact_frame", frame),
                "offset": event.get("contact_frame", frame) - c,
                "prev_action": prev,
                "gap": gap,
                "gate_open": (gap is None or gap > opener_gap),
                "game_off": not _in_game_on(game_on, frame),
                "in_contact": in_contact(event.get("contact_frame", frame)),
            })

        def best(predicate) -> Optional[Dict[str, Any]]:
            hits = [a for a in annotated if predicate(a)]
            if not hits:
                return None
            return min(hits, key=lambda a: abs(a["offset"]))

        raw = best(lambda a: a["in_contact"])
        gated = best(lambda a: a["in_contact"] and a["gate_open"])
        gated_off = best(lambda a: a["in_contact"] and a["gate_open"] and a["game_off"])
        contact_frames = range(c - tolerance, c + tolerance + 1)
        rows.append({
            "point": window["point"],
            "frame": c,
            "kind": window.get("action") or "serve",
            "held_out": window["held_out"],
            "runway_in_window": len(runway),
            "far_flight_in_window": len(flights),
            "far_flight_in_contact": sum(1 for e in flights if in_contact(e.get("onset_frame", e["frame"]))),
            "candidates_in_window": len(candidates),
            "baseline_hit": bool(raw),
            "baseline_offset": raw["offset"] if raw else None,
            "gated_hit": bool(gated),
            "gated_offset": gated["offset"] if gated else None,
            "gated_gameoff_hit": bool(gated_off),
            "candidates": annotated,
            "ball_seen_frames": sum(1 for f in contact_frames if f in ball_seen),
            "ball_locked_frames": sum(1 for f in contact_frames if ball_locked.get(f)),
            "window_ball_seen_frames": sum(1 for f in range(lo, hi + 1) if f in ball_seen),
            "window_ball_locked_frames": sum(1 for f in range(lo, hi + 1) if ball_locked.get(f)),
        })
    return rows


def report(rows: List[Dict[str, Any]], opener_gap: int) -> Dict[str, Any]:
    def agg(subset: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "n": len(subset),
            "baseline_hits": sum(1 for r in subset if r["baseline_hit"]),
            "gated_hits": sum(1 for r in subset if r["gated_hit"]),
            "gated_gameoff_hits": sum(1 for r in subset if r["gated_gameoff_hit"]),
            "runway": sum(1 for r in subset if r["runway_in_window"] > 0),
            "flight_window": sum(1 for r in subset if r["far_flight_in_window"] > 0),
            "flight_contact": sum(1 for r in subset if r["far_flight_in_contact"] > 0),
            "cand_window": sum(1 for r in subset if r["candidates_in_window"] > 0),
            "zero_ball_frames": sum(1 for r in subset
                                    if r["ball_seen_frames"] == 0),
        }

    serves = [r for r in rows if r["kind"] == "serve"]
    controls = [r for r in rows if r["kind"] != "serve"]
    out = {
        "opener_gap": opener_gap,
        "far_serves": agg(serves),
        "far_dev": agg([r for r in serves if not r["held_out"]]),
        "far_held_out": agg([r for r in serves if r["held_out"]]),
        "controls": agg(controls),
    }
    for name, key in (("baseline", "baseline_hits"), ("gated", "gated_hits"),
                      ("gated+game_off", "gated_gameoff_hits")):
        hits, fps = out["far_serves"][key], out["controls"][key]
        out[f"precision_{name.replace('+','_')}"] = round(hits / (hits + fps), 3) if hits + fps else 0.0
        out[f"recall_{name.replace('+','_')}"] = round(hits / out["far_serves"]["n"], 3) if out["far_serves"]["n"] else 0.0
    return out


def sweep_gate(rows: List[Dict[str, Any]], gaps: List[int]) -> List[Dict[str, Any]]:
    """Precision/recall of the opener gate as a function of the gap constant."""
    serves = [r for r in rows if r["kind"] == "serve"]
    controls = [r for r in rows if r["kind"] != "serve"]
    out = []
    for gap in gaps:
        def hit(r: Dict[str, Any]) -> bool:
            return any(a["in_contact"] and (a["gap"] is None or a["gap"] > gap)
                       for a in r["candidates"])
        h, f = sum(1 for r in serves if hit(r)), sum(1 for r in controls if hit(r))
        out.append({
            "gap": gap,
            "hits": h, "false_positives": f,
            "precision": round(h / (h + f), 3) if h + f else 0.0,
            "recall": round(h / len(serves), 3) if serves else 0.0,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--from", dest="start", type=int, default=0)
    ap.add_argument("--to", dest="end", type=int, default=None)
    ap.add_argument("--tolerance", type=int, default=15)
    ap.add_argument("--opener-gap", type=int, default=DEFAULT_OPENER_GAP)
    ap.add_argument("--control-limit", type=int, default=24)
    ap.add_argument("--diag", default="", help="diag dump path (output/...)")
    ap.add_argument("--out", default="output/g4/serve_events_seq.json")
    ap.add_argument("--reuse", default="", help="skip the decode, re-score this pass file")
    args = ap.parse_args()

    serves = load_far_serves(ROOT / MATCH_GT)
    controls = load_control_contacts(ROOT / MATCH_GT, args.control_limit)
    windows = serves + controls
    lo = min(w["frame"] for w in windows) - WINDOW_BEFORE
    hi = max(w["frame"] for w in windows) + WINDOW_AFTER
    if args.start or args.end:
        lo, hi = args.start, (args.end if args.end is not None else hi)
    print(f"{len(serves)} GT far serves + {len(controls)} control windows; "
          f"decoding f{lo}..f{hi} sequentially on {args.device}")

    if args.reuse:
        pass_result = json.loads((ROOT / args.reuse).read_text())
        pass_result["ball_seen"] = {int(k): v for k, v in pass_result["ball_seen"].items()}
        pass_result["ball_locked"] = {int(k): v for k, v in pass_result["ball_locked"].items()}
    else:
        cap = cv2.VideoCapture(str(MATCH_VIDEO))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        cap.release()
        pass_result = sequential_pass(production_config(args.device), fps, lo, hi,
                                      diag_path=args.diag or None)
        # Persist the raw recording so the rules can be swept offline without
        # another 30-minute decode.
        raw_out = ROOT / (args.out.replace(".json", "_recording.json"))
        raw_out.write_text(json.dumps(pass_result))
        print(f"wrote raw recording {raw_out}")

    rows = score_windows(pass_result, windows, args.tolerance, args.opener_gap)
    summary = report(rows, args.opener_gap)
    sweep = sweep_gate(rows, [0, 30, 60, 90, 120, 143, 180, 240, 400])

    print("\nPER WINDOW  (c = GT contact frame; cand d = offset of the nearest candidate)")
    for row in rows:
        gaps = [a["gap"] for a in row["candidates"] if a["in_contact"]]
        print(f"P{row['point']:<3} f{row['frame']:<6} {row['kind']:<8} "
              f"{'held-out' if row['held_out'] else 'dev     '} "
              f"base={int(row['baseline_hit'])} gated={int(row['gated_hit'])} "
              f"goff={int(row['gated_gameoff_hit'])} "
              f"d={row['baseline_offset']} gaps={gaps} "
              f"runway={row['runway_in_window']} fl(w/c)={row['far_flight_in_window']}/"
              f"{row['far_flight_in_contact']} ball(c±15f)={row['ball_seen_frames']} "
              f"locked={row['ball_locked_frames']}")

    print("\nSUMMARY", json.dumps(summary, indent=1))
    print("\nOPENER-GAP SWEEP", json.dumps(sweep, indent=1))

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "device": args.device,
        "span": [lo, hi],
        "fps_container": 25.67,
        "summary": summary,
        "sweep": sweep,
        "rows": rows,
    }, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
