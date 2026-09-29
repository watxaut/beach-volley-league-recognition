#!/usr/bin/env python3
"""T5 step 2: replay A (weak-speed lock tier) vs B (backfill on a fresh lock).

Both candidate mechanisms for the far-side serve admission were REFUTED as a
recovery (0/5 far serves each, see ``docs/t5_mechanism_ab.md``), so they live
OUTSIDE ``src/`` in ``scripts/serve_mechanism_harness.py`` as default-off
subclasses of the production components. This harness therefore measures the
PRODUCTION classes plus a measured delta: it feeds the per-frame raw ball
detections of a T4 ``--diag-dump`` JSONL back into the real ``BallTracker``
and then drives the real ``ActionClassifier`` contact probe over the ball
history the pipeline would have seen. (Fidelity gate: the ``baseline``
arm reproduces the dumped ``ball_track`` state/centres on every frame.)

For each arm it reports, on the dev clip:

* ``serve_candidates``   -- contact candidates recovered at the GT serve frames
  (of the far-side serves that die today) and within their +-tolerance,
* ``new_locks``          -- bootstrap locks the arm adds (spurious lock risk),
* ``extra_candidates``   -- contact candidates OUTSIDE every GT contact window
  (false-positive risk), with their frames.

Usage::

    venv/bin/python scripts/probe_serve_mechanisms.py \\
        --diag output/t4/dev_diag.jsonl \\
        --ground-truth ground_truth/video_ari_joan_8_first_points_annotations.json \\
        --json output/t5/dev_mechanisms.json \\
        --markdown docs/t5_mechanism_ab.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.detection.court_calibration import CourtCalibration  # noqa: E402
from src.utils.config import Config  # noqa: E402
from src.utils.diagnostics import load_diag  # noqa: E402

# The refuted mechanisms live here, not in src/ (both 0/5 far serves).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from serve_mechanism_harness import (  # noqa: E402
    ProbeClassifier, ServeMechanismBallTracker)

# Tracker construction: exactly the FrameProcessor wiring (config keys), so a
# replayed arm is the pipeline's tracker.
TRACKER_KEYS = [
    ("max_missing_frames", "ball_max_missing", 10),
    ("trajectory_smoothing", "trajectory_smoothing", 5),
    ("velocity_threshold", "velocity_threshold", 200.0),
    ("low_confidence_threshold", "low_confidence_threshold", 0.4),
    ("max_trajectory_gap", "max_trajectory_gap", 60.0),
    ("lock_min_speed", "ball_lock_min_speed", 8.0),
    ("lock_motion_window", "ball_lock_motion_window", 5),
    ("lock_max_jump", "ball_lock_max_jump", 90.0),
    ("lock_max_pair_gap", "ball_lock_max_pair_gap", 2),
    ("selection_conf_window", "ball_selection_conf_window", 10.0),
    ("locked_low_conf_floor", "ball_locked_low_conf_floor", 0.15),
    ("boot_low_conf_floor", "ball_boot_low_conf_floor", 0.15),
]

# The arms. ``base`` reproduces production; A and B switch on one mechanism
# each with the values the T5 doc measured / the doc's proposal used.
ARMS: Dict[str, Dict[str, Any]] = {
    "base": {},
    "A_weak3_w30": {"weak_min_speed": 3.0, "weak_max_width": 30.0},
    "A_weak3_nowidth": {"weak_min_speed": 3.0},
    "B_backfill": {"backfill_lookback": 20, "backfill_max_width": 30.0},
    "B_backfill_narrow": {"backfill_lookback": 20},
    "B_backfill_tight": {"backfill_lookback": 20, "backfill_radius": 20.0,
                         "backfill_radius_growth": 6.0,
                         "backfill_max_width": 30.0},
    "B_backfill_skip_suspect": {"backfill_lookback": 20,
                                "backfill_max_width": 30.0,
                                "backfill_skip_suspect": True},
    "B_backfill_lookback12": {"backfill_lookback": 12,
                              "backfill_max_width": 30.0},
}


def make_tracker(cfg: Config, extra: Dict[str, Any],
                 court_bounds: Optional[tuple]) -> ServeMechanismBallTracker:
    kwargs = {param: cfg.get(key, default) for param, key, default in TRACKER_KEYS}
    kwargs.update(extra)
    tracker = ServeMechanismBallTracker(**kwargs)
    if court_bounds:
        tracker.set_court_bounds(court_bounds)
    return tracker


def det_rows(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Diag detections -> the dicts the detector hands the tracker.

    ``removed`` detections never reach the tracker in production (the detector
    drops them at ``ball_static_persist``), so they are dropped here too --
    that IS the static exclusion the backfill chain relies on.
    """
    out = []
    for d in record.get("ball_dets", []) or []:
        if d.get("removed"):
            continue
        det = {"center": [float(d["center"][0]), float(d["center"][1])],
               "confidence": float(d.get("conf", 0.0)),
               "bbox": list(d.get("bbox") or []),
               "class_name": "sports_ball"}
        if d.get("suspect"):
            det["stationary_suspect"] = True
        out.append(det)
    return out


def replay_arm(frames: Dict[int, Dict[str, Any]], cfg: Config,
               extra: Dict[str, Any], court_bounds: Optional[tuple],
               calibration=None) -> Dict[str, Any]:
    """Run one arm: real BallTracker over the dumped detections, then the real
    contact probe over the ball history the classifier would have received."""
    tracker = make_tracker(cfg, extra, court_bounds)
    classifier = ProbeClassifier(pose_estimator=None,
                                 court_calibration=calibration)
    classifier.diag_enabled = True
    candidates: List[Dict[str, Any]] = []
    locks: List[int] = []
    backfilled: List[Dict[str, Any]] = []
    probe_reasons: Dict[int, str] = {}
    prev_locked = False
    mismatch_lock = 0
    mismatch_center = 0
    for frame in sorted(frames):
        record = frames[frame]
        dets = det_rows(record)
        out = tracker.update(dets, frame_number=frame)
        chain = tracker.pop_backfill()
        if chain:
            backfilled.append({"lock_frame": frame, "points": len(chain),
                               "span": [chain[0]["frame_offset"],
                                        chain[-1]["frame_offset"]]})
        classifier.add_ball_sightings([
            {"frame": frame + int(pt["frame_offset"]),
             "x": pt["center"][0], "y": pt["center"][1],
             "w": pt.get("width", 0.0), "h": pt.get("height", 0.0)}
            for pt in chain])
        if tracker.locked and not prev_locked:
            locks.append(frame)
        prev_locked = tracker.locked
        # fidelity against the dumped production state
        bt = record.get("ball_track") or {}
        if bool(bt.get("locked")) != bool(tracker.locked):
            mismatch_lock += 1
        elif bt.get("center") and out is not None and not out.get("is_predicted"):
            if (abs(bt["center"][0] - out["center"][0]) > 1e-6
                    or abs(bt["center"][1] - out["center"][1]) > 1e-6):
                mismatch_center += 1
        # exactly what FrameProcessor feeds the classifier
        if out is not None and not out.get("is_predicted"):
            bbox = out.get("bbox") or []
            if bbox and len(bbox) == 4 and out.get("center"):
                classifier._ball_history.append((
                    frame, float(out["center"][0]), float(out["center"][1]),
                    float(bbox[2] - bbox[0]), float(bbox[3] - bbox[1])))
        c = frame - classifier.CONTACT_DELAY
        if c > 0:
            hit = classifier._detect_contact(c)
            if hit is not None:
                candidates.append({"frame": hit[4], "kind": hit[1],
                                   "point": [round(hit[0][0], 1),
                                             round(hit[0][1], 1)]})
                classifier._last_contact_frame = hit[4]
        for rec in classifier.pop_diag():
            probe_reasons[int(rec["frame"])] = (rec.get("reason")
                                                or rec.get("stage"))
    return {
        "candidates": candidates,
        "locks": locks,
        "backfill_events": backfilled,
        "probe_reasons": probe_reasons,
        "fidelity": {"locked_mismatch": mismatch_lock,
                     "center_mismatch": mismatch_center},
    }


def gt_events(gt_path: str) -> List[Dict[str, Any]]:
    gt = json.loads(open(gt_path, encoding="utf-8").read())
    events = []
    for point in gt.get("points", []):
        for ev in point.get("events", []):
            events.append({
                "point": point.get("point"),
                "frame": int(ev["frame"]),
                "action": ev.get("final_action") or ev.get("action"),
                "side": ev.get("owner_side"),
                "tolerance": int(ev.get("frame_tolerance", 15)),
            })
    events.sort(key=lambda e: e["frame"])
    return events


def score(arm: Dict[str, Any], events: List[Dict[str, Any]],
          base_locks: Optional[List[int]] = None) -> Dict[str, Any]:
    """Per-GT-event hit and the false-positive census."""
    cand_frames = sorted(c["frame"] for c in arm["candidates"])
    per_event = []
    for ev in events:
        exact = ev["frame"] in cand_frames
        near = [f for f in cand_frames if abs(f - ev["frame"]) <= ev["tolerance"]]
        per_event.append({**ev, "exact": exact,
                          "near": sorted(near)[:3],
                          "near_offset": (None if not near
                                          else min(near, key=lambda f: abs(f - ev["frame"]))
                                          - ev["frame"])})
    matched = set()
    for row in per_event:
        for f in row["near"]:
            matched.add(f)
    extra = [c for c in arm["candidates"] if c["frame"] not in matched]
    reasons = arm.get("probe_reasons") or {}
    for row in per_event:
        window = [reasons.get(f) for f in
                  range(row["frame"] - row["tolerance"],
                        row["frame"] + row["tolerance"] + 1)]
        counts: Dict[str, int] = {}
        for r in window:
            if r:
                counts[r] = counts.get(r, 0) + 1
        row["probe_reasons"] = dict(sorted(counts.items(),
                                          key=lambda kv: -kv[1]))
    out = {
        "candidates_total": len(arm["candidates"]),
        "events_total": len(events),
        "events_exact": sum(1 for r in per_event if r["exact"]),
        "events_within_tolerance": sum(1 for r in per_event if r["near"]),
        "events": per_event,
        "extra_candidates": len(extra),
        "extra_candidate_frames": [c["frame"] for c in extra],
        "extra_candidate_detail": extra[:40],
        "lock_count": len(arm["locks"]),
        "backfill_events": arm["backfill_events"],
        "probe_reasons": arm["probe_reasons"],
    }
    if base_locks is not None:
        new = [f for f in arm["locks"] if f not in set(base_locks)]
        out["new_locks"] = new
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--diag", required=True)
    ap.add_argument("--ground-truth", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--calibration", default=None)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--json", default=None)
    ap.add_argument("--markdown", default=None)
    args = ap.parse_args(argv)

    diag = load_diag(args.diag)
    frames = diag["frames"]
    cfg = Config(args.config) if args.config else Config()
    court = None
    if args.calibration:
        court = CourtCalibration()
        court.load(args.calibration)
    bounds = court.court_bounds if court is not None and court.is_calibrated else None
    events = gt_events(args.ground_truth)
    serves = [e for e in events if e["action"] == "serve"]
    far_serves = [s for s in serves if s["side"] == "far"]

    report: Dict[str, Any] = {
        "diag": args.diag, "ground_truth": args.ground_truth,
        "frames": len(frames), "calibration": args.calibration,
        "arms": {}, "events": events,
    }
    base_locks = None
    for name in args.arms.split(","):
        name = name.strip()
        if not name:
            continue
        extra = dict(ARMS.get(name, {}))
        arm = replay_arm(frames, cfg, extra, bounds, court)
        scored = score(arm, events, base_locks)
        scored["params"] = extra
        scored["fidelity"] = arm["fidelity"]
        scored["serve_candidates"] = [
            {"point": e["point"], "frame": e["frame"], "side": e["side"],
             "exact": e["exact"], "near": e["near"], "offset": e["near_offset"]}
            for e in scored["events"] if e["action"] == "serve"]
        scored["far_serve_candidates"] = sum(
            1 for e in scored["serve_candidates"] if e["side"] == "far" and e["near"])
        scored["far_serves_total"] = len(far_serves)
        report["arms"][name] = scored
        if name == "base":
            base_locks = arm["locks"]
            report["base_locks"] = arm["locks"]

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(markdown(report))

    hdr = (f"{'arm':<24}{'far serves':>12}{'contacts':>10}{'exact':>8}"
           f"{'extra':>8}{'new locks':>11}{'fidelity':>12}")
    print(hdr)
    for name, a in report["arms"].items():
        print(f"{name:<24}"
              f"{a['far_serve_candidates']}/{a['far_serves_total']:>10}"
              f"{a['candidates_total']:>10}"
              f"{a['events_exact']:>8}"
              f"{a['extra_candidates']:>8}"
              f"{len(a.get('new_locks', [])):>11}"
              f"{str(a['fidelity']):>12}")
    for name, a in report["arms"].items():
        if name == "base":
            continue
        print(f"  {name}: serve " + ", ".join(
            f"P{s['point']} f{s['frame']}"
            f"{'@' + str(s['offset']) if s['offset'] is not None else ':MISS'}"
            for s in a["serve_candidates"]))
    return 0


def markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# T5 step 2 - mechanism A vs B (replay)",
        "",
        "Both mechanisms were REFUTED as a recovery (0/5 far serves) and live",
        "OUTSIDE `src/`, in `scripts/serve_mechanism_harness.py` as",
        "default-off subclasses; `src/` is unchanged.",
        "",
        f"Replay of `{report['diag']}` ({report['frames']} frames) through the real",
        "`BallTracker` + `ActionClassifier` contact probe, against",
        f"`{report['ground_truth']}`.",
        "",
        "| arm | far serves with a candidate | contacts | exact-frame | "
        "extra candidates | new locks | fidelity |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, a in report["arms"].items():
        lines.append(
            f"| {name} | {a['far_serve_candidates']}/{a['far_serves_total']} | "
            f"{a['candidates_total']} | {a['events_exact']}/{a['events_total']} | "
            f"{a['extra_candidates']} | {len(a.get('new_locks', []))} | "
            f"{a['fidelity']['locked_mismatch']} locked / "
            f"{a['fidelity']['center_mismatch']} centre |")
    lines += ["", "## Per-serve candidates (frame:offset from the GT frame)", ""]
    for name, a in report["arms"].items():
        cells = ", ".join(
            f"P{s['point']} f{s['frame']}"
            + (f"@{s['offset']:+d}" if s["offset"] is not None else " MISS")
            for s in a["serve_candidates"])
        lines.append(f"* **{name}**: {cells}")
    lines += ["", "## Contact-probe outcome inside each serve window "
              "(+-tolerance frames)", ""]
    for name, a in report["arms"].items():
        lines.append(f"* **{name}**:")
        for e in a["events"]:
            if e["action"] != "serve":
                continue
            lines.append(f"  * P{e['point']} f{e['frame']} ({e['side']}): "
                         f"{e['probe_reasons'] or 'no probe record'}")
    lines += ["", "## Extra candidates (outside every GT contact window)", ""]
    for name, a in report["arms"].items():
        frames = a["extra_candidate_frames"]
        lines.append(f"* **{name}** ({len(frames)}): {frames[:60]}")
    lines += ["", "## New locks vs baseline", ""]
    for name, a in report["arms"].items():
        if name == "base":
            continue
        lines.append(f"* **{name}**: {a.get('new_locks', [])}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
