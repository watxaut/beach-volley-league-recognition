"""Contact sheets for owner GT adjudication.

Extracts the given frame ranges from the video (sequentially decoded --
the match file is VFR), runs the RAW ball detector (suppress_static=False,
conf 0.15 -- sees held/tossed balls too) on each extracted frame, draws
every detection, burns in the frame number and tiles the frames into one
PNG per range.  Anchored serve frames are marked with a red bar + "A",
pipeline action frames with the action label.

Usage:
    venv/bin/python scripts/contact_sheet.py \
        --video resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4 \
        --ranges "p7:3560-3900:12,p11a:6890-6980:6" \
        --serve-anchors ground_truth/20260920_match_serve_anchors.txt \
        --pipeline output/match20260920_posegate/pipeline_output.json \
        --out output/contact_sheets
Ranges: name:start-end:stride.  Diagnostic/GT tooling only.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.detection.ball_detector import BallDetector  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from map_episodes_to_points import parse_serve_anchors  # noqa: E402

TILE_W, TILE_H = 384, 216
COLS = 5


def draw_label(img: np.ndarray, text: str, org: Tuple[int, int],
               color: Tuple[int, int, int]) -> None:
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--video", required=True)
    ap.add_argument("--ranges", required=True,
                    help="comma-separated name:start-end:stride")
    ap.add_argument("--serve-anchors", required=True)
    ap.add_argument("--pipeline", required=True)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", default="output/contact_sheets")
    args = ap.parse_args()

    ranges: List[Tuple[str, int, int, int]] = []
    for spec in args.ranges.split(","):
        name, span, stride = spec.split(":")
        lo, hi = span.split("-")
        ranges.append((name.strip(), int(lo), int(hi), int(stride)))

    anchors = parse_serve_anchors(args.serve_anchors)
    anchor_frames = {a["frame"]: f"P{k} anchor" for k, a in anchors["points"].items()}
    anchor_frames.update({f["frame"]: "FALSE mark" for f in anchors["false"]})

    pipeline = json.loads(Path(args.pipeline).read_text(encoding="utf-8"))
    action_at: Dict[int, List[Dict[str, Any]]] = {}
    for x in pipeline["actions"]:
        action_at.setdefault(x["frame_number"], []).append(x)

    detector = BallDetector(model_path=str(Path("models/volleyball_ball_best.pt")),
                            confidence_threshold=0.15, device=args.device,
                            suppress_static=False)

    wanted: Dict[str, List[int]] = {}
    for name, lo, hi, stride in ranges:
        wanted[name] = list(range(lo, hi + 1, stride))
    all_frames = sorted({f for frames in wanted.values() for f in frames})

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"cannot open {args.video}")
    frames: Dict[int, np.ndarray] = {}
    idx = 0
    for f in all_frames:
        while idx <= f:
            ok, img = cap.read()
            if not ok:
                raise SystemExit(f"video ended before frame {f}")
            idx += 1
        frames[f] = img.copy()
    cap.release()
    print(f"extracted {len(frames)} frames")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, lo, hi, stride in ranges:
        tiles = []
        for f in wanted[name]:
            img = cv2.resize(frames[f], (TILE_W, TILE_H))
            sy = TILE_H / frames[f].shape[0]
            sx = TILE_W / frames[f].shape[1]
            for d in detector.detect(frames[f]):
                cx, cy = int(d["center"][0] * sx), int(d["center"][1] * sy)
                r = max(4, int((d["bbox"][2] - d["bbox"][0]) * sx / 2))
                color = (0, 200, 0) if not d.get("stationary_suspect") else (0, 140, 255)
                cv2.circle(img, (cx, cy), r, color, 1)
                draw_label(img, f"{d['confidence']:.2f}", (max(2, cx - r), max(12, cy - r - 4)),
                           (0, 200, 0))
            tag = anchor_frames.get(f)
            if tag:
                cv2.rectangle(img, (0, 0), (TILE_W - 1, TILE_H - 1), (0, 0, 255), 2)
                draw_label(img, tag, (TILE_W - 130, TILE_H - 8), (0, 0, 255))
            for a in action_at.get(f, []):
                draw_label(img, f"{a['action']} {a.get('team', '')}",
                           (4, TILE_H - 26), (0, 220, 220))
            draw_label(img, f"f{f}", (4, 14), (255, 255, 255))
            tiles.append(img)
        if not tiles:
            continue
        rows = (len(tiles) + COLS - 1) // COLS
        sheet = np.full((rows * TILE_H, COLS * TILE_W, 3), 30, dtype=np.uint8)
        for i, tile in enumerate(tiles):
            r, c = divmod(i, COLS)
            sheet[r * TILE_H:(r + 1) * TILE_H, c * TILE_W:(c + 1) * TILE_W] = tile
        out_path = out_dir / f"{name}_{lo}-{hi}_s{stride}.png"
        cv2.imwrite(str(out_path), sheet)
        print(f"wrote {out_path} ({len(tiles)} tiles)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
