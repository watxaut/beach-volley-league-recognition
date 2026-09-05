#!/usr/bin/env python3
"""Score the game on/off machine against gt_point_start_end.txt.

Reads the confirmed points from output/<stem>/pipeline_output.json (key
"game_state" -> "points", written by make run) and the owner's
point start/end ground truth, then reports one-to-one matched points,
false/missed segments, per-frame accuracy of the point mask, and boundary
errors for matched points (GT times are whole seconds, so +/-15 frames is
annotation granularity, not machine error).

Usage:
    python scripts/evaluate_game_state.py output/video_entreno_game_state/pipeline_output.json \
        --gt ground_truth/gt_point_start_end.txt
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FPS = 30.0


def parse_gt(path: str, fps: float = FPS):
    """Parse 'MM:SS point starts/stops' pairs into (start_frame, end_frame)."""
    text = Path(path).read_text()
    events = []
    for m in re.finditer(r"(\d{1,2}):(\d{2})\s+point\s+(starts|stops)", text, re.IGNORECASE):
        events.append((int(m.group(1)) * 60 + int(m.group(2)), m.group(3).lower()))
    segs, start = [], None
    for t, kind in events:
        if kind == "starts":
            if start is not None:
                raise ValueError("nested 'point starts' in GT")
            start = t
        else:
            if start is None:
                raise ValueError("'point stops' without 'point starts' in GT")
            segs.append((start, t))
            start = None
    if start is not None:
        raise ValueError("GT ends with an unclosed 'point starts'")
    return [(int(s * fps), int(e * fps)) for s, e in segs]


def one_to_one(pred, gt):
    """Greedy IoU matching (>=50% GT coverage required)."""
    pairs = []
    for i, (a, b) in enumerate(pred):
        for j, (s, e) in enumerate(gt):
            inter = max(0, min(b, e) - max(a, s) + 1)
            if inter:
                pairs.append((inter / (e - s + 1), i, j, inter))
    pairs.sort(reverse=True)
    used_p, used_g, matches = set(), set(), []
    for cov, i, j, _ in pairs:
        if i in used_p or j in used_g or cov < 0.5:
            continue
        used_p.add(i)
        used_g.add(j)
        matches.append((i, j))
    return matches, [j for j in range(len(gt)) if j not in used_g], [
        i for i in range(len(pred)) if i not in used_p
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pipeline_output", help="pipeline_output.json from make run")
    ap.add_argument("--gt", default="ground_truth/gt_point_start_end.txt")
    ap.add_argument("--total-frames", type=int, default=0,
                    help="video frame count (default: taken from the JSON)")
    args = ap.parse_args()

    payload = json.load(open(args.pipeline_output))
    points = payload.get("game_state", {}).get("points", [])
    pred = [(p["start_frame"], p["end_frame"]) for p in points]
    gt = parse_gt(args.gt)
    n = args.total_frames or payload.get("video", {}).get("total_frames") or 0
    if not n:
        n = max([e for _, e in pred] + [e for _, e in gt]) + 1

    print(f"predicted points: {len(pred)}   GT points: {len(gt)}")
    matches, missed, false = one_to_one(pred, gt)
    for i, j in matches:
        (a, b), (s, e) = pred[i], gt[j]
        print(f"  pt{j:02d} match: start {a-s:+5d}f ({(a-s)/FPS:+5.1f}s)  "
              f"stop {b-e:+5d}f ({(b-e)/FPS:+5.1f}s)  "
              f"dur {(b-a+1)/FPS:5.1f}s vs {(e-s+1)/FPS:5.1f}s")
    for j in missed:
        s, e = gt[j]
        print(f"  pt{j:02d} MISSED: f{s}-{e}")
    for i in false:
        a, b = pred[i]
        print(f"  FALSE point: f{a}-{b} ({(b-a+1)/FPS:.1f}s, "
              f"{points[i].get('n_actions', 0)} actions)")

    # per-frame accuracy of the point mask
    truth = [False] * n
    for s, e in gt:
        for f in range(s, min(e + 1, n)):
            truth[f] = True
    correct = 0
    for f in range(n):
        in_pred = any(a <= f <= b for a, b in pred)
        correct += in_pred == truth[f]
    print(f"\nmatched={len(matches)}/{len(gt)}  false={len(false)}  "
          f"frame accuracy={correct / n * 100:.1f}%")
    return 0 if not missed and not false else 1


if __name__ == "__main__":
    sys.exit(main())
