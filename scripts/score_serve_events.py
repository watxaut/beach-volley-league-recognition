#!/usr/bin/env python3
"""G4 -- score the serve-evidence EVENTS against the owner GT far serves.

Diagnosis, not production: it replays ONLY the windows around the GT far-serve
contacts through the real ``FrameProcessor.process_frame`` (AGENTS.md §2: one
shared path, no divergent fast path) with the emitters on, then reports what
each event type covers.  The windowed decode is the cheap path to a decision
(open point G2): the emitters are evidence, and evidence is scored against GT
before anything is allowed to change the action stream.

Windows are independent (trackers reset between them), so a track-id continuity
claim would NOT be valid here -- the events are deliberately track-free.

Usage::

    venv/bin/python scripts/score_serve_events.py                  # all 17 GT far serves
    venv/bin/python scripts/score_serve_events.py --points 13,22
    venv/bin/python scripts/score_serve_events.py --dev-only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.frame_processor import FrameProcessor  # noqa: E402
from src.utils.config import Config  # noqa: E402

MATCH_VIDEO = "resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4"
MATCH_CALIB = "calibrations/20260920_match_ari_joan_lost.json"
MATCH_GT = "ground_truth/20260920_match_contacts.json"
#: The fine-tuned ball model.  src/main.py auto-detects it and the COCO
#: fallback "rarely finds a volleyball on real footage" (its own comment) --
#: probes that skip this silently measure a different pipeline (the G4 scoring
#: bug: the first far-flight numbers came from yolov8n.pt).
BALL_MODEL = ROOT / "models" / "volleyball_ball_best.pt"


def production_config(device: str = "cpu", **overrides: Any) -> Dict[str, Any]:
    """Config.default() + the ball-model wiring src/main.py does.

    Reused by every probe that decodes through FrameProcessor, so a probe can
    never again measure the COCO detector instead of the shipped one.
    """
    config = dict(Config.default().config)
    if BALL_MODEL.exists():
        config["ball_model_path"] = str(BALL_MODEL)
    config["device"] = device
    config.update(overrides)
    return config


#: Owner frame estimates are coarse (+-10-15 f, stated in the GT file itself).
DEFAULT_TOLERANCE = 15


def load_serves(gt_path: Path, side: str = "far") -> List[Dict[str, Any]]:
    """GT serves on one side (the far set is the loss; the near set is the control)."""
    data = json.loads(gt_path.read_text())
    out = []
    for point in data["points"]:
        for event in point.get("events", []):
            if event.get("action") != "serve" or event.get("owner_side") != side:
                continue
            out.append({
                "point": point["point"],
                "frame": int(event["match_frame"]),
                "tolerance": int(event.get("frame_tolerance") or DEFAULT_TOLERANCE),
                "squad": event.get("player_team"),
                "held_out": point["point"] > 8,
            })
    out.sort(key=lambda s: s["frame"])
    return out


def load_control_contacts(gt_path: Path, limit: int = 12) -> List[Dict[str, Any]]:
    """Mid-rally NON-serve contacts: the false-positive control windows.

    A serve event that fires here is a false positive by construction (nothing
    in these windows is a serve), which is the number the decision needs next to
    recall: 3/17 contacts found is worthless if 20 candidates fire per video.
    """
    data = json.loads(gt_path.read_text())
    controls = []
    for point in data["points"]:
        contacts = [c for c in point.get("events", [])
                    if c.get("action") not in ("serve", None)
                    and c.get("owner_side") not in (None, "")]
        if len(contacts) < 2:
            continue
        contact = contacts[len(contacts) // 2]  # mid-rally, not the reception
        controls.append({
            "point": point["point"],
            "frame": int(contact["match_frame"]),
            "tolerance": int(contact.get("frame_tolerance") or DEFAULT_TOLERANCE),
            "squad": contact.get("player_team"),
            "held_out": point["point"] > 8,
            "action": contact.get("action"),
        })
        if len(controls) >= limit:
            break
    return controls


def load_far_serves(gt_path: Path) -> List[Dict[str, Any]]:
    """GT far-serve contacts: point, frame, tolerance, dev/held-out split."""
    data = json.loads(gt_path.read_text())
    serves = []
    for point in data["points"]:
        for event in point.get("events", []):
            if event.get("action") != "serve" or event.get("owner_side") != "far":
                continue
            serves.append({
                "point": point["point"],
                "frame": int(event["match_frame"]),
                "tolerance": int(event.get("frame_tolerance") or DEFAULT_TOLERANCE),
                "squad": event.get("player_team"),
                "held_out": point["point"] > 8,
            })
    serves.sort(key=lambda s: s["frame"])
    return serves


class WindowRunner:
    """One FrameProcessor reused across windows (models load once)."""

    def __init__(self, calibration: str, fps: float, device: str = "cpu") -> None:
        self.config = production_config(device)
        self.config["court_calibration_path"] = calibration
        self.config["serve_events_enabled"] = True
        self.fps = fps
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_index = 0

    @property
    def cap(self) -> cv2.VideoCapture:
        if self._cap is None:
            self._cap = cv2.VideoCapture(MATCH_VIDEO)
            if not self._cap.isOpened():
                raise RuntimeError(f"cannot open {MATCH_VIDEO}")
        return self._cap

    def open(self) -> None:
        self._cap = cv2.VideoCapture(MATCH_VIDEO)
        if not self._cap.isOpened():
            raise RuntimeError(f"cannot open {MATCH_VIDEO}")
        self.fps = float(self._cap.get(cv2.CAP_PROP_FPS))

    def run_window(self, start: int, end: int) -> List[Dict[str, Any]]:
        """Decode [start, end] through the shared path; return the events."""
        cap = self.cap
        cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        processor = FrameProcessor(self.config)
        processor.setup_video_fps(self.fps)
        processor.setup_video_dimensions(1920, 1080)
        events: List[Dict[str, Any]] = []
        frame = start
        while frame <= end:
            ok, image = cap.read()
            if not ok:
                break
            result = processor.process_frame(image, frame)
            events.extend(result.get("serve_events", []))
            frame += 1
        processor.flush_actions()
        events.extend(processor.get_serve_events())
        # Deduplicate: the per-frame stream and the final roll-up overlap.
        seen, unique = set(), []
        for event in events:
            key = (event["type"], event["frame"],
                   event.get("contact_frame"), event.get("onset_frame"),
                   event.get("start_frame"), event.get("evidence_frame"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(event)
        unique.sort(key=lambda e: e["frame"])
        return unique


def score_window(events: List[Dict[str, Any]], frame: int, tolerance: int) -> Dict[str, Any]:
    """Per-event-type coverage of one GT far serve."""
    lo, hi = frame - tolerance, frame + tolerance
    window_lo, window_hi = frame - 90, frame + 60
    in_contact = lambda e: lo <= e["frame"] <= hi  # noqa: E731
    in_window = lambda e: window_lo <= e["frame"] <= window_hi  # noqa: E731

    runway = [e for e in events if e["type"] == "runway_occupant"]
    flights = [e for e in events if e["type"] == "far_flight"]
    candidates = [e for e in events if e["type"] == "serve_candidate"]
    # The reach evidence nearest the GT frame, whichever contact proxy it came
    # from: this is what tells us HOW FAR the event lands from the owner label.
    best_offset = min((abs(e["contact_frame"] - frame) for e in candidates), default=None)
    flight_offset = min((abs(e["onset_frame"] - frame) for e in flights), default=None)
    # An occupant that overlaps the serve moment is the useful signal; a run
    # that ended long before is not.
    near_occupant = [e for e in runway if e["end_frame"] >= frame - 45]
    return {
        "runway_events": len(runway),
        "runway_near": len(near_occupant),
        "runway_off_court": any(e.get("off_court_frames", 0) > 0 for e in runway),
        "far_flights_in_window": len([e for e in flights if in_window(e)]),
        "far_flights_in_contact": len([e for e in flights if in_contact(e)]),
        "candidates": len(candidates),
        "candidate_in_contact": len([e for e in candidates if in_contact(e)]),
        "candidates_in_window": len([e for e in candidates if in_window(e)]),
        "best_candidate_offset": best_offset,
        "best_flight_offset": flight_offset,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", default="", help="only these point numbers")
    ap.add_argument("--before", type=int, default=90)
    ap.add_argument("--after", type=int, default=60)
    ap.add_argument("--tolerance", type=int, default=DEFAULT_TOLERANCE)
    ap.add_argument("--control", action="store_true",
                    help="score NON-serve mid-rally contacts instead (false-positive windows)")
    ap.add_argument("--control-limit", type=int, default=12)
    ap.add_argument("--dev-only", action="store_true")
    ap.add_argument("--held-out-only", action="store_true")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", default="output/g4/serve_events_score.json")
    args = ap.parse_args()

    if args.control:
        serves = load_control_contacts(ROOT / MATCH_GT, args.control_limit)
        print(f"CONTROL mode: {len(serves)} mid-rally non-serve windows "
              f"(a candidate here is a false positive)")
    else:
        serves = load_far_serves(ROOT / MATCH_GT)
    if args.points:
        want = {int(p) for p in args.points.split(",") if p}
        serves = [s for s in serves if s["point"] in want]
    if args.dev_only:
        serves = [s for s in serves if not s["held_out"]]
    if args.held_out_only:
        serves = [s for s in serves if s["held_out"]]

    runner = WindowRunner(str(ROOT / MATCH_CALIB), 30.0, device=args.device)
    runner.open()
    print(f"fps {runner.fps:.2f}; {len(serves)} GT far serves "
          f"({sum(s['held_out'] for s in serves)} held-out)")

    report = []
    t0 = time.time()
    for serve in serves:
        start, end = serve["frame"] - args.before, serve["frame"] + args.after
        events = runner.run_window(start, end)
        scored = score_window(events, serve["frame"], serve["tolerance"] or args.tolerance)
        row = {"point": serve["point"], "serve_frame": serve["frame"],
               "kind": serve.get("action") or "serve",
               "held_out": serve["held_out"], "window": [start, end], **scored}
        report.append(row)
        print(f"P{serve['point']:<3} f{serve['frame']:<6} "
              f"{('held-out' if serve['held_out'] else 'dev     '):<9} "
              f"{serve.get('action') or 'serve':<8} "
              f"runway={scored['runway_events']}(near {scored['runway_near']}) "
              f"flight(w/c)={scored['far_flights_in_window']}/{scored['far_flights_in_contact']} "
              f"cand(w/c)={scored['candidates_in_window']}/{scored['candidate_in_contact']} "
              f"d(cand)={scored['best_candidate_offset']} d(flight)={scored['best_flight_offset']} "
              f"[{time.time()-t0:.0f}s]")

    summary = {
        "n": len(report),
        "n_held_out": sum(1 for r in report if r["held_out"]),
        "runway_near": sum(1 for r in report if r["runway_near"] > 0),
        "runway_off_court": sum(1 for r in report if r["runway_off_court"]),
        "far_flight_in_window": sum(1 for r in report if r["far_flights_in_window"] > 0),
        "far_flight_in_contact": sum(1 for r in report if r["far_flights_in_contact"] > 0),
        "candidate_in_window": sum(1 for r in report if r["candidates_in_window"] > 0),
        "candidate_in_contact": sum(1 for r in report if r["candidate_in_contact"] > 0),
        "offsets_candidate": sorted(r["best_candidate_offset"] for r in report
                                    if r["best_candidate_offset"] is not None),
        "offsets_flight": sorted(r["best_flight_offset"] for r in report
                                 if r["best_flight_offset"] is not None),
        "seconds": round(time.time() - t0, 1),
    }
    print("\nSUMMARY", json.dumps(summary, indent=1))
    for label, rows in (("dev", [r for r in report if not r["held_out"]]),
                        ("held-out", [r for r in report if r["held_out"]])):
        if not rows:
            continue
        print(f"{label:>9} (n={len(rows)}): runway_near "
              f"{sum(1 for r in rows if r['runway_near'])} | flight_w "
              f"{sum(1 for r in rows if r['far_flights_in_window'])} | cand_w "
              f"{sum(1 for r in rows if r['candidates_in_window'])} | cand_c "
              f"{sum(1 for r in rows if r['candidate_in_contact'])}")

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": report}, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
