#!/usr/bin/env python3
"""G4 follow-up -- WHY are the far serves not tracked / not emitted?

Diagnose-only (no ``src/`` change).  The G4 serve events found 3/17 GT far
serves, but the question is sharper than that: at a far-serve contact, which
signal in the chain fails to flip?  This walks the SAME chain the loss
waterfall does -- raw ball detection -> track admission -> contact candidate ->
candidate gate -> actor/team -> label -- on every GT far-serve window, replayed
through the real ``FrameProcessor.process_frame`` with the T4 diag dump ON, so
each stage is observed rather than re-derived.

Per window it reports, around the contact (+-TOL):

* raw ball detections and their confidence (is the ball even SEEN);
* the ball tracker's state per frame plus the unlock/never-lock reason;
* the classifier's contact probes with the reason each was refused;
* the tracked players, and whether the serve-runway emitter saw an occupant;
* what the action stream emitted nearby.

Usage::

    venv/bin/python scripts/probe_far_serve_tracking.py
    venv/bin/python scripts/probe_far_serve_tracking.py --points 13,22
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.score_serve_events import (  # noqa: E402
    MATCH_CALIB,
    MATCH_GT,
    MATCH_VIDEO,
    load_control_contacts,
    load_far_serves,
    load_serves,
    production_config,
)
from src.analysis.frame_processor import FrameProcessor  # noqa: E402
from src.utils.diagnostics import load_diag  # noqa: E402

#: Reasons the ball tracker gives when it is not holding a real ball.
TRACK_REASONS = ("locked_admitted", "locked_admitted_stationary_suspect",
                 "unlocked", "none", "predicted", "coast")


def run_window(start: int, end: int, fps: float, device: str) -> Dict[str, Any]:
    """Decode [start, end] through the shared path with diag + serve events on."""
    cap = cv2.VideoCapture(MATCH_VIDEO)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    config = production_config(device)
    config["court_calibration_path"] = str(ROOT / MATCH_CALIB)
    config["serve_events_enabled"] = True
    with tempfile.TemporaryDirectory() as tmp:
        dump = Path(tmp) / "diag.jsonl"
        config["diag_dump"] = str(dump)
        processor = FrameProcessor(config)
        processor.setup_video_fps(fps)
        processor.setup_video_dimensions(1920, 1080)
        events: List[Dict[str, Any]] = []
        for frame in range(start, end + 1):
            ok, image = cap.read()
            if not ok:
                break
            result = processor.process_frame(image, frame)
            events.extend(result.get("serve_events", []))
        processor.flush_actions()
        events.extend(processor.get_serve_events())
        processor.close_diagnostics()
        # Read it INSIDE the context: TemporaryDirectory removes the file on exit.
        diag = load_diag(str(dump))
    cap.release()
    seen, unique = set(), []
    for event in events:
        key = (event["type"], event["frame"], event.get("start_frame"),
               event.get("flight_onset_frame"), event.get("evidence_frame"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)
    return {"frames": diag["frames"], "serve_events": sorted(unique, key=lambda e: e["frame"])}


def window_state(frames: Dict[int, Dict[str, Any]], serve_events: List[Dict[str, Any]],
                 frame: int, tol: int) -> Dict[str, Any]:
    """Everything the chain saw around one contact."""
    lo, hi = frame - tol, frame + tol
    recs = [frames[f] for f in sorted(frames) if lo <= f <= hi]
    dets = [d for r in recs for d in (r.get("ball_dets") or [])]
    states = Counter((r.get("ball_track") or {}).get("state", "missing") for r in recs)
    reasons = Counter(str((r.get("ball_track") or {}).get("reason")) for r in recs
                      if (r.get("ball_track") or {}).get("reason"))
    candidates = [c for r in recs for c in (r.get("candidates") or [])]
    probes = Counter(str(c.get("reason")) for c in candidates if c.get("stage") != "accepted")
    accepted = [c for c in candidates if c.get("stage") == "accepted"]
    gate = Counter(str(c.get("reason")) for c in candidates
                   if c.get("stage") != "accepted" and c.get("kind"))
    actions = [(a.get("frame"), a.get("action"), a.get("team")) for r in recs
               for a in (r.get("actions") or [])]
    tracked_frames = sum(1 for r in recs if r.get("players"))
    # How far apart are the raw ball SIGHTINGS? The tracker's bootstrap needs
    # two of them within ball_lock_max_pair_gap frames (default 2), so this is
    # the precondition for ever locking the ball at all.
    det_frames = sorted({f for f, r in frames.items() if lo <= f <= hi and r.get("ball_dets")})
    gaps = [b - a for a, b in zip(det_frames, det_frames[1:])]
    lockable_pairs = sum(1 for g in gaps if g <= 2)
    ev_types = Counter(e["type"] for e in serve_events
                       if frame - 90 <= e["frame"] <= frame + 60)
    return {
        "ball_dets": len(dets),
        "ball_det_max_conf": round(max((float(d.get("conf", 0)) for d in dets), default=0.0), 2),
        "track_states": dict(states),
        "track_reasons": dict(reasons),
        "tracked_frames": tracked_frames,
        "det_frames": len(det_frames),
        "det_gap_median": (sorted(gaps)[len(gaps) // 2] if gaps else None),
        "det_gap_max": (max(gaps) if gaps else None),
        "lockable_pairs": lockable_pairs,
        "candidates_accepted": len(accepted),
        "candidate_reasons": dict(probes),
        "gate_reasons": dict(gate),
        "actions": actions,
        "serve_events": dict(ev_types),
    }


def first_failing_stage(state: Dict[str, Any]) -> str:
    """Mirror of waterfall's order, on the state this probe collected."""
    if state["ball_dets"] == 0:
        return "1_raw_detection"
    if state["track_states"].get("tracked", 0) == 0:
        return "2_track_admission"
    if state["candidates_accepted"] == 0 and state["candidate_reasons"]:
        return "3_candidate"
    if state["candidates_accepted"] == 0:
        return "3_candidate"
    if not any(a and a[1] for a in state["actions"]):
        return "4_candidate_gate"
    return "6_gesture_context_label"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", default="far", choices=["far", "near"],
                    help="far = the loss under study; near = the CONTROL side")
    ap.add_argument("--control", action="store_true",
                    help="score mid-rally NON-serve contacts instead (false-positive windows)")
    ap.add_argument("--control-limit", type=int, default=24)
    ap.add_argument("--points", default="")
    ap.add_argument("--before", type=int, default=90)
    ap.add_argument("--after", type=int, default=60)
    ap.add_argument("--tolerance", type=int, default=15)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", default="output/g4/far_serve_tracking.json")
    ap.add_argument("--keep-dumps", default="output/g4/far_serve_dumps",
                    help="directory for the per-window diag JSONL (probe_far_serve_geometry reads it)")
    args = ap.parse_args()

    if args.control:
        serves = load_control_contacts(ROOT / MATCH_GT, args.control_limit)
        print(f"CONTROL mode: {len(serves)} mid-rally non-serve windows")
    elif args.side == "far":
        serves = load_far_serves(ROOT / MATCH_GT)
    else:
        serves = load_serves(ROOT / MATCH_GT, args.side)
    if args.points:
        want = {int(p) for p in args.points.split(",") if p}
        serves = [s for s in serves if s["point"] in want]

    cap = cv2.VideoCapture(MATCH_VIDEO)
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    cap.release()
    print(f"fps {fps:.2f}; {len(serves)} GT {args.side} serves")

    rows: List[Dict[str, Any]] = []
    t0 = time.time()
    for serve in serves:
        start, end = serve["frame"] - args.before, serve["frame"] + args.after
        result = run_window(start, end, fps, args.device)
        if args.keep_dumps:
            dump_dir = ROOT / args.keep_dumps
            dump_dir.mkdir(parents=True, exist_ok=True)
            path = dump_dir / f"p{serve['point']:03d}_f{serve['frame']}.jsonl"
            with path.open("w") as fh:
                for f in sorted(result["frames"]):
                    fh.write(json.dumps({"frame": f, **result["frames"][f]}) + "\n")
        state = window_state(result["frames"], result["serve_events"],
                             serve["frame"], args.tolerance)
        stage = first_failing_stage(state)
        row = {"point": serve["point"], "serve_frame": serve["frame"], "side": args.side,
               "held_out": serve["held_out"], "stage": stage, **state}
        rows.append(row)
        print(f"P{serve['point']:<3} f{serve['frame']:<6} {'held-out' if serve['held_out'] else 'dev     '} "
              f"stage={stage:<26} dets={state['ball_dets']:<3} maxconf={state['ball_det_max_conf']:.2f} "
              f"track={state['track_states']} players={state['tracked_frames']}/{2 * args.tolerance + 1} "
              f"acc={state['candidates_accepted']} cand={state['candidate_reasons']} "
              f"act={state['actions']} ev={state['serve_events']} "
              f"gaps(med/max)={state['det_gap_median']}/{state['det_gap_max']} "
              f"lockable_pairs={state['lockable_pairs']} [{time.time()-t0:.0f}s]")

    print(f"\nFIRST FAILING STAGE ({len(rows)} GT {args.side} serves)")
    for stage, n in Counter(r["stage"] for r in rows).most_common():
        print(f"  {stage:<28} {n}")
    print("\nBALL TRACK STATE inside +-TOL of each contact")
    merged = Counter()
    for r in rows:
        merged.update(r["track_states"])
    for state, n in merged.most_common():
        print(f"  {state:<28} {n} frames total")
    print("\nBALL TRACK REASONS (why the tracker was not holding it)")
    reasons = Counter()
    for r in rows:
        reasons.update(r["track_reasons"])
    for reason, n in reasons.most_common(12):
        print(f"  {reason:<28} {n}")
    print("\nRAW BALL SIGHTING GAPS inside +-TOL (the lock bootstrap needs <=2 f)")
    ok = [r for r in rows if r["lockable_pairs"] > 0]
    print(f"  windows with >=1 pair inside the 2-frame gate: {len(ok)}/{len(rows)}")
    print("  per-window median gap:", [r["det_gap_median"] for r in rows])
    print("\nCONTACT-PROBE REASONS (classifier asked, found nothing)")
    probes = Counter()
    for r in rows:
        probes.update(r["candidate_reasons"])
    for reason, n in probes.most_common(12):
        print(f"  {reason:<28} {n}")

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": rows}, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
