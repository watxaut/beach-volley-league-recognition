#!/usr/bin/env python3
"""
Interactive player-ID ground-truth annotator.

Pre-draws the tracker's boxes on sampled frames (from a dump_player_tracks.py
JSON) so you only verify/correct them and assign canonical IDs 1-4 -- you never
draw boxes from scratch unless the tracker missed a player entirely.

Writes into the existing ground_truth/<video>_annotations.json (creates it if
missing), touching ONLY annotated_frames.players -- ball/actions/court stay as
they are. Saves after every frame, so it is safe to Ctrl-C / quit and resume:
already-annotated frames are skipped on the next run (override with --redo).

Usage:
    python scripts/annotate_player_gt.py resources/video_entreno_1.mp4 \
        --tracks output/1c/video_entreno_1_tracks.json

    # then evaluate:
    python scripts/evaluate.py --tracks-json output/1c/video_entreno_1_tracks.json \
        --ground-truth ground_truth/video_entreno_1_annotations.json --component players

Controls (per box, highlighted in yellow):
    1-4   assign canonical GT id to the highlighted box, advance
    D     drop the highlighted box (bad/ghost detection -- it will NOT go into GT)
    A     add a box the tracker missed (drag a rectangle, then assign 1-4)
    F     skip the whole frame (nothing written)
    B     go back one sampled frame and redo it
    Q     save & quit
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import cv2

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.court_calibration import CourtCalibration

GROUND_TRUTH_DIR = Path(__file__).resolve().parent.parent / "ground_truth"

# Colors (BGR)
COLOR_DONE = (0, 200, 0)       # assigned box
COLOR_CURRENT = (0, 255, 255)  # highlighted box
COLOR_DROPPED = (128, 128, 128)


def load_tracks_boxes(tracks_path: str) -> Dict[int, List[dict]]:
    """frame index -> [{'track_id', 'bbox'}] from a dump_player_tracks.py JSON."""
    with open(tracks_path) as f:
        data = json.load(f)
    return {
        fr["frame"]: [
            {"track_id": p["track_id"], "bbox": [int(v) for v in p["bbox"]]}
            for p in fr.get("players", [])
        ]
        for fr in data.get("frames", [])
    }


def sample_frames(n_frames: int, every: int, start: int, end: Optional[int]) -> List[int]:
    """Every Nth frame in [start, end); capped at n_frames."""
    end = min(end, n_frames) if end is not None else n_frames
    return list(range(start, end, max(1, every)))


def derive_team(calib: CourtCalibration, bbox: List[int]) -> Optional[str]:
    """'A'/'B' from the bbox foot point, same convention as the tracker."""
    if calib is None or not calib._calibrated:
        return None
    return calib.get_team_for_bbox(bbox)


def load_or_create_gt(gt_path: Path, video_path: str, fps: float,
                      width: int, height: int) -> dict:
    """Load the GT file, creating the skeleton if missing. Never drops keys."""
    if gt_path.exists():
        with open(gt_path) as f:
            gt = json.load(f)
    else:
        gt = {
            "video": video_path,
            "fps": fps,
            "resolution": [width, height],
            "annotated_frames": {
                "ball": {"description": "Ball center position every 5 frames", "frames": {}},
                "players": {"description": "Player bounding boxes + IDs every 10 frames", "frames": {}},
                "actions": {"description": "Action events with frame number, player ID, and type", "events": []},
            },
            "court": None,
        }
    af = gt.setdefault("annotated_frames", {})
    af.setdefault("players", {"description": "Player bounding boxes + IDs", "frames": {}})
    af["players"].setdefault("frames", {})
    return gt


def write_frame_gt(gt: dict, frame_idx: int, boxes: List[dict],
                   assignments: Dict[int, int], calib: CourtCalibration) -> List[int]:
    """Store one annotated frame into gt['annotated_frames']['players']['frames'].

    boxes/assignments use the annotator's internal representation: assignments
    maps box index -> canonical id. Returns the list of canonical ids written
    (for duplicate detection by the caller).
    """
    players = []
    for i, box in enumerate(boxes):
        if i not in assignments:
            continue
        bbox = box["bbox"]
        players.append({
            "id": assignments[i],
            "team": derive_team(calib, bbox),
            "bbox": bbox,
        })
    gt["annotated_frames"]["players"]["frames"][str(frame_idx)] = players
    return [p["id"] for p in players]


def draw_annotation_frame(frame, boxes, assignments, dropped, current,
                          frame_idx, message=""):
    """Render one annotator view: court-free overlay of box states + HUD."""
    out = frame.copy()
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = box["bbox"]
        if i in dropped:
            color, thick = COLOR_DROPPED, 1
        elif i in assignments:
            color, thick = COLOR_DONE, 2
        elif i == current:
            color, thick = COLOR_CURRENT, 3
        else:
            color, thick = (0, 120, 255), 1
        cv2.rectangle(out, (x1, y1), (x2, y2), color, thick)
        label = f"pred {box['track_id']}"
        if i in assignments:
            label += f" -> GT {assignments[i]}"
        elif i in dropped:
            label += " (dropped)"
        cv2.putText(out, label, (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    n_assigned = len(assignments)
    n_drop = len(dropped)
    hud = [
        f"frame {frame_idx}  [{message}]" if message else f"frame {frame_idx}",
        f"boxes: {n_assigned} assigned / {n_drop} dropped / {len(boxes) - n_assigned - n_drop} left",
        "[1-4] assign  [D] drop  [A] add  [R] reset frame  [F] skip  [B] back  [Q] quit",
    ]
    for j, line in enumerate(hud):
        cv2.putText(out, line, (10, 30 + 28 * j),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
    return out


def annotate_frame(window, frame, frame_idx, boxes):
    """Run the interactive loop for one frame. Returns (assignments, dropped) or
    (None, None) if the user skipped the frame."""
    assignments: Dict[int, int] = {}
    dropped: set = set()
    current = 0

    while True:
        n_left = len(boxes) - len(assignments) - len(dropped)
        # Auto-advance current past boxes already handled
        while current < len(boxes) and (current in assignments or current in dropped):
            current += 1
        if current >= len(boxes) or n_left == 0:
            msg = "press [ENTER] accept & save  [F] skip  [Q] quit" if boxes else \
                  "no tracker boxes -- [A] add some  [F] skip  [Q] quit"
            view = draw_annotation_frame(frame, boxes, assignments, dropped, current,
                                         frame_idx, msg)
        else:
            view = draw_annotation_frame(frame, boxes, assignments, dropped, current,
                                         frame_idx, f"box {current + 1}/{len(boxes)}: press 1-4 / D")
        cv2.imshow(window, view)
        key = cv2.waitKey(0) & 0xFF

        if key in (ord('1'), ord('2'), ord('3'), ord('4')) and current < len(boxes):
            assignments[current] = key - ord('0')
            current += 1
        elif key == ord('d') and current < len(boxes):
            dropped.add(current)
            current += 1
        elif key == ord('r'):
            # Reset the whole frame: clear every assignment/drop and start over
            assignments.clear()
            dropped.clear()
            current = 0
        elif key == ord('a'):
            roi = cv2.selectROI(window, frame, showCrosshair=True)
            if any(roi):
                x, y, w, h = roi
                boxes.append({"track_id": -1, "bbox": [int(x), int(y), int(x + w), int(y + h)]})
                current = len(boxes) - 1
        elif key == 13:  # Enter -- accept
            return assignments, dropped
        elif key == ord('f'):
            return None, None
        elif key == ord('b'):
            return "back", None
        elif key == ord('q'):
            return "quit", None


def main():
    parser = argparse.ArgumentParser(description="Annotate player-ID ground truth")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--tracks", required=True, help="dump_player_tracks.py JSON (pre-drawn boxes)")
    parser.add_argument("--gt", default=None, help="GT JSON (default: ground_truth/<video>_annotations.json)")
    parser.add_argument("--calibration", default=None, help="Court calibration JSON (for team A/B)")
    parser.add_argument("--every", type=int, default=10, help="Sample every Nth frame (default 10)")
    parser.add_argument("--start", type=int, default=0, help="First frame to sample")
    parser.add_argument("--end", type=int, default=None, help="Last frame (exclusive)")
    parser.add_argument("--redo", action="store_true", help="Re-annotate frames that already have GT")
    args = parser.parse_args()

    gt_path = Path(args.gt) if args.gt else GROUND_TRUTH_DIR / f"{Path(args.video).stem}_annotations.json"

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: cannot open video {args.video}")
        sys.exit(1)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    tracks = load_tracks_boxes(args.tracks)
    gt = load_or_create_gt(gt_path, args.video, fps, width, height)
    gt_frames = gt["annotated_frames"]["players"]["frames"]

    calib = CourtCalibration()
    if args.calibration:
        calib.load(args.calibration)
        print(f"Loaded calibration {args.calibration} (team labels enabled)")
    else:
        print("No calibration given -- 'team' will be null in GT")

    frame_indices = sample_frames(n_frames, args.every, args.start, args.end)
    todo = [i for i in frame_indices if args.redo or str(i) not in gt_frames]
    print(f"{len(frame_indices)} sampled frames, {len(frame_indices) - len(todo)} already annotated, "
          f"{len(todo)} to do -> {gt_path}")

    window = "player GT annotator"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    quit_requested = False
    pos = 0
    while pos < len(todo):
        frame_idx = todo[pos]
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            print(f"Warning: could not read frame {frame_idx}, skipping")
            pos += 1
            continue

        boxes = [dict(b) for b in tracks.get(frame_idx, [])]
        assignments, dropped = annotate_frame(window, frame, frame_idx, boxes)

        if assignments == "quit":
            quit_requested = True
            break
        if assignments == "back":
            # Redo the previous sampled frame; re-accepting overwrites its GT.
            pos = max(0, pos - 2) + 1
            continue
        if assignments is None:  # skipped
            pos += 1
            continue

        ids = write_frame_gt(gt, frame_idx, boxes, assignments, calib)
        if len(ids) != len(set(ids)):
            print(f"WARNING frame {frame_idx}: duplicate canonical ids {ids} -- rerun with --redo to fix")
        with open(gt_path, "w") as f:
            json.dump(gt, f, indent=2)
        print(f"frame {frame_idx}: wrote {len(ids)} players {ids}")
        pos += 1

    cap.release()
    cv2.destroyAllWindows()
    n_annotated = len(gt["annotated_frames"]["players"]["frames"])
    print(f"\nDone. {n_annotated} GT player frames in {gt_path}")
    print("Evaluate with:")
    print(f"  python scripts/evaluate.py --tracks-json {args.tracks} "
          f"--ground-truth {gt_path} --component players")
    if quit_requested:
        sys.exit(0)


if __name__ == "__main__":
    main()
