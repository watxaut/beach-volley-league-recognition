"""Diagnose the #77 possession labels on owner-flagged windows.

Owner feedback (2026-10-04, session #78): the match (f250-f345, f378+) and
the full practice video (f1185) both read FAR/CROSSING while the ball stays
NEAR after a spike into the net; near-side occlusion seems to shrink the
measured width. This probe replays the EXACT ball path (BallDetector at the
production 0.15 threshold + BallTracker + BallSidePossessionObserver, 1080
normalized via ensure_1080 like src/main) and dumps, per frame:

* the tracked ball's bbox + width + is_predicted (the observer's input),
* the observer row (side/crossing/bands),
* the raw detector candidates (to see what occlusion did to the widths),

and saves zoomed crops (bbox drawn) for requested windows so the actual ball
pixels can be inspected. Sequential decode only -- NO seeks (AGENTS §9).

Usage:
  python scripts/probe_possession_feedback.py VIDEO [--max-frames N]
      [--crop-from A --crop-to B] [--out-dir output/possession_feedback]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.detection.ball_detector import BallDetector          # noqa: E402
from src.detection.court_calibration import CourtCalibration  # noqa: E402
from src.tracking.ball_tracker import BallTracker             # noqa: E402
from src.analysis.ball_side_possession import (               # noqa: E402
    BallSidePossessionObserver,
    net_plane_width_px,
)
from src.utils.video_upscale import ensure_1080, resolve_source_stem  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video")
    ap.add_argument("--court", help="calibration JSON (auto from calibrations/<stem>.json)")
    ap.add_argument("--ball-model")
    ap.add_argument("--max-frames", type=int, default=100000)
    ap.add_argument("--crop-from", type=int, default=None)
    ap.add_argument("--crop-to", type=int, default=None)
    ap.add_argument("--out-dir", default="output/possession_feedback")
    args = ap.parse_args()

    stem = resolve_source_stem(Path(args.video))
    video_file = ensure_1080(Path(args.video))

    court_path = args.court or str(ROOT / "calibrations" / f"{stem}.json")
    court = CourtCalibration(court_path) if Path(court_path).exists() else CourtCalibration()
    d_net = net_plane_width_px(court.court_corners)
    print(f"[{stem}] video={video_file} calib={court_path} d_net={d_net}")

    ball_model = args.ball_model or str(ROOT / "models" / "volleyball_ball_best.pt")
    detector = BallDetector(model_path=ball_model if Path(ball_model).exists() else None,
                            confidence_threshold=0.15)
    tracker = BallTracker(max_missing_frames=10, low_confidence_threshold=0.4,
                          max_trajectory_gap=60.0)
    observer = BallSidePossessionObserver()
    observer.set_calibration(court)
    print(f"bands: far_px={observer.far_px:.1f} near_px={observer.near_px:.1f}")

    out_dir = ROOT / args.out_dir / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "frames.jsonl"
    jf = jsonl_path.open("w")

    cap = cv2.VideoCapture(str(video_file))
    if not cap.isOpened():
        sys.exit(f"cannot open {video_file}")
    idx = 0
    while idx < args.max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        dets = detector.detect(frame)
        tracked = tracker.update(dets)
        row = observer.observe(idx, tracked)

        rec = {
            "f": idx,
            "side": row["side"],
            "crossing": bool(row["crossing"]),
            "width": row["width_px"],
            "width_f": row["width_frame"],
            "predicted": bool(tracked.get("is_predicted")) if tracked else None,
            "bbox": tracked.get("bbox") if tracked else None,
            "conf": tracked.get("confidence") if tracked else None,
            "raw": [
                {"w": round(float(d["bbox"][2] - d["bbox"][0]), 1),
                 "h": round(float(d["bbox"][3] - d["bbox"][1]), 1),
                 "c": round(float(d.get("confidence", 0)), 2)}
                for d in (dets or [])[:4]
            ],
        }
        jf.write(json.dumps(rec) + "\n")

        if args.crop_from is not None and args.crop_from <= idx <= args.crop_to \
                and tracked and tracked.get("bbox"):
            x1, y1, x2, y2 = [float(v) for v in tracked["bbox"]]
            w, h = x2 - x1, y2 - y1
            pad = max(2.5 * max(w, h), 60.0)
            H, W = frame.shape[:2]
            xa, xb = int(max(0, x1 - pad)), int(min(W, x2 + pad))
            ya, yb = int(max(0, y1 - pad)), int(min(H, y2 + pad))
            crop = frame[ya:yb, xa:xb].copy()
            cv2.rectangle(crop, (int(x1) - xa, int(y1) - ya),
                          (int(x2) - xa, int(y2) - ya),
                          (0, 0, 255) if tracked.get("is_predicted") else (0, 255, 0), 1)
            cv2.putText(crop, f"f{idx} w={w:.0f} {row['side'] or '--'}"
                        f"{' X' if row['crossing'] else ''}",
                        (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
            cv2.putText(crop, f"f{idx} w={w:.0f} {row['side'] or '--'}"
                        f"{' X' if row['crossing'] else ''}",
                        (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
            cv2.imwrite(str(out_dir / f"f{idx:06d}.jpg"), crop,
                        [cv2.IMWRITE_JPEG_QUALITY, 90])
        idx += 1
    jf.close()
    cap.read()  # drain
    cap.release()
    print(f"wrote {idx} frames -> {jsonl_path} (crops in {out_dir})")


if __name__ == "__main__":
    main()
