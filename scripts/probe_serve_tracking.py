"""Probe: what does the ball detector actually see at each owner-anchored serve?

Open point 22, mechanism 2 diagnosis. The owner ratified serve anchors
(``ground_truth/20260920_match_serve_anchors.txt``) and hypothesised: "the
ball might be tracked by the yolo model, but maybe as it starts not moving
then" -- i.e. the detector sees the serve but the tracker never admits it
because a serve starts near-stationary (held ball -> toss -> slow flight),
which is what the static-suppression machinery eats (detections persisting
>=0.55 of the window at one spot are DROPPED; >=0.30 flagged
stationary_suspect; tracker bootstrap needs a >=8 px/f near-consecutive
motion pair).

What the production TRACKER did is already observable from the run outputs
(game_on episodes + emitted actions); the open question is the DETECTOR.
So this probe runs TWO detectors strictly inside the anchored serve windows
(--window-before/-after), on the sequentially decoded frames (VFR file --
CAP_PROP_POS_FRAMES seeks are frame-unreliable):

- PRODUCTION detector: suppress_static=True, conf 0.15, v3 weights (the
  exact src.main wiring) -- what the pipeline could have used;
- RAW detector: suppress_static=False -- also sees the held/tossed ball the
  production pass would have suppressed, with stationary_suspect flags.

Per window it reports det coverage, confidences, and the frame-to-frame
motion of the best raw detection (the bootstrap criterion). Diagnostic
only; nothing feeds production.

Usage:
    venv/bin/python scripts/probe_serve_tracking.py \
        --video resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4 \
        --serve-anchors ground_truth/20260920_match_serve_anchors.txt \
        --pipeline output/match20260920_posegate/pipeline_output.json \
        [--device cpu] --out output/probe_serve_tracking.json
"""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.ball_detector import BallDetector
from src.utils.video_upscale import resolve_source_stem

sys.path.insert(0, str(Path(__file__).resolve().parent))
from map_episodes_to_points import parse_serve_anchors  # noqa: E402


def best_det(dets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not dets:
        return None
    return max(dets, key=lambda d: d["confidence"])


def dist(a: Optional[List[float]], b: Optional[List[float]]) -> Optional[float]:
    if a is None or b is None:
        return None
    return math.hypot(a[0] - b[0], a[1] - b[1])


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    prod = [r for r in rows if r["prod_n_dets"] > 0]
    raw = [r for r in rows if r["raw_n_dets"] > 0]
    speeds = [r["raw_speed"] for r in rows
              if r.get("raw_speed") is not None]
    boot = next((r["frame"] for r in rows if r.get("raw_speed") is not None
                 and r["raw_speed"] >= 8.0), None)
    return {
        "prod_det_frames": len(prod),
        "prod_first_det_frame": prod[0]["frame"] if prod else None,
        "prod_max_conf": max((r["prod_best_conf"] for r in rows), default=0.0),
        "raw_det_frames": len(raw),
        "raw_first_det_frame": raw[0]["frame"] if raw else None,
        "raw_max_conf": max((r["raw_best_conf"] for r in rows), default=0.0),
        "raw_suspect_frames": sum(1 for r in rows if r["raw_best_suspect"]),
        "raw_motion_pairs": len(speeds),
        "raw_speed_max": max(speeds) if speeds else None,
        "raw_speed_median": sorted(speeds)[len(speeds) // 2] if speeds else None,
        "bootstrap_frame_first_ge8pxf": boot,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--video", required=True)
    ap.add_argument("--serve-anchors", required=True)
    ap.add_argument("--pipeline", required=True)
    ap.add_argument("--out", default="output/probe_serve_tracking.json")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--window-before", type=int, default=45)
    ap.add_argument("--window-after", type=int, default=150)
    args = ap.parse_args()

    anchors = parse_serve_anchors(args.serve_anchors)
    windows = {k: (a["frame"] - args.window_before, a["frame"] + args.window_after)
               for k, a in anchors["points"].items()}
    false_frames = [f["frame"] for f in anchors["false"]]

    pipeline = json.loads(Path(args.pipeline).read_text(encoding="utf-8"))
    actions = pipeline["actions"]

    # production wiring (src.main): auto-detected v3 weights, conf 0.15
    model_path = Path("models/volleyball_ball_best.pt")
    if not model_path.exists():
        raise SystemExit(f"ball weights not found: {model_path}")
    prod_detector = BallDetector(model_path=str(model_path),
                                 confidence_threshold=0.15, device=args.device)
    raw_detector = BallDetector(model_path=str(model_path),
                                confidence_threshold=0.15, device=args.device,
                                suppress_static=False)
    print(f"weights: {model_path} | device: {args.device} | "
          f"windows: {len(windows)} (sequential decode)")

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"cannot open {args.video}")

    per_frame: Dict[int, Dict[str, Any]] = {k: [] for k in windows}
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        active = [k for k, (lo, hi) in windows.items() if lo <= frame_idx <= hi]
        if active:
            row: Dict[str, Any] = {"frame": frame_idx}
            dets = prod_detector.detect(frame)
            bd = best_det(dets)
            row["prod_n_dets"] = len(dets)
            row["prod_best_conf"] = bd["confidence"] if bd else 0.0
            raw = raw_detector.detect(frame)
            rb = best_det(raw)
            row["raw_n_dets"] = len(raw)
            row["raw_best_conf"] = rb["confidence"] if rb else 0.0
            row["raw_best_center"] = rb["center"] if rb else None
            row["raw_best_suspect"] = bool(rb.get("stationary_suspect")) if rb else False
            prev = (per_frame[active[0]][-1] if per_frame[active[0]]
                    and per_frame[active[0]][-1]["frame"] == frame_idx - 1 else None)
            row["raw_speed"] = (dist(rb["center"] if rb else None,
                                     prev["raw_best_center"]) if prev else None)
            for k in active:
                per_frame[k].append(row)
        frame_idx += 1
        if frame_idx % 5000 == 0:
            print(f"  decoded {frame_idx} frames...")
    cap.release()
    total = frame_idx
    print(f"decoded {total} frames total")

    serves = []
    for k in sorted(windows):
        a = anchors["points"][k]
        lo, hi = windows[k]
        rows = per_frame[k]
        emitted = [{"frame": x["frame_number"], "action": x["action"],
                    "team": x["team"]}
                   for x in actions if lo - 15 <= x["frame_number"] <= hi + 15]
        serves.append({
            "point": k,
            "anchor_frame": a["frame"],
            "side": a["side"],
            "owner_verdict": a["verdict"],
            "summary": summarize(rows),
            "emitted_actions": emitted,
        })

    result = {
        "video": args.video,
        "total_frames": total,
        "device": args.device,
        "window": [args.window_before, args.window_after],
        "note": "prod_* = production detector (static suppression on); "
                "raw_* = suppress_static=False (sees held/tossed ball); "
                "bootstrap_frame_first_ge8pxf = first frame pair meeting the "
                "tracker's motion-admission criterion",
        "false_serve_frames": false_frames,
        "serves": serves,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"wrote {out}")

    print(f"\n{'P':>3} {'frame':>6} {'side':>5} {'owner':>12} | "
          f"prod det (conf) | raw det (conf) | motion max/med, boot@ | emitted")
    for s in serves:
        sm = s["summary"]
        em = ",".join(f"{e['frame']}:{e['action']}" for e in s["emitted_actions"]) or "-"
        print(f"P{s['point']:<2} {s['anchor_frame']:>6} {str(s['side']):>5} "
              f"{str(s['owner_verdict']):>12} | "
              f"{sm['prod_det_frames']:>3} ({sm['prod_max_conf']:.2f}) | "
              f"{sm['raw_det_frames']:>3} ({sm['raw_max_conf']:.2f}) | "
              f"{str(sm['raw_speed_max'] and round(sm['raw_speed_max'], 1))}/"
              f"{str(sm['raw_speed_median'] and round(sm['raw_speed_median'], 1))}, "
              f"{sm['bootstrap_frame_first_ge8pxf']} | {em}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
