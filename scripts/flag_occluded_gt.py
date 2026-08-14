#!/usr/bin/env python3
"""
Flag occluded players in a player-GT annotation file.

A GT player is marked "visible": false when its bbox is largely contained in
another player's bbox (>= threshold of its own area) -- i.e. someone else is
standing in front of it and no detector can be expected to find it.
evaluate.py's player component skips invisible GT boxes.

One-time fixup tool, safe to re-run (idempotent): re-computes all flags from
geometry every time.

Usage:
    python scripts/flag_occluded_gt.py ground_truth/video_entreno_1_annotations.json
    python scripts/flag_occluded_gt.py <gt.json> --threshold 0.5 --dry-run
"""

import argparse
import json
from pathlib import Path


def _box_area(b):
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def containment(inner, outer):
    """Fraction of `inner`'s area covered by `outer`."""
    x1, y1 = max(inner[0], outer[0]), max(inner[1], outer[1])
    x2, y2 = min(inner[2], outer[2]), min(inner[3], outer[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    a = _box_area(inner)
    return inter / a if a > 0 else 0.0


def flag_occluded_frames(gt_players: dict, threshold: float) -> dict:
    """Return {frame_str: {gt_id: bool}} visibility for every annotated player.

    The occluded player is the SMALLER box (farther from camera): with nested
    boxes the containment is mutual, so area breaks the tie and the occluder
    (bigger, nearer box) stays visible.
    """
    flags = {}
    for frame_str, players in gt_players.items():
        per_frame = {}
        for p in players or []:
            occluded = any(
                q is not p
                and _box_area(p["bbox"]) < _box_area(q["bbox"])
                and containment(p["bbox"], q["bbox"]) >= threshold
                for q in players or []
            )
            per_frame[p["id"]] = not occluded
        flags[frame_str] = per_frame
    return flags


def main():
    parser = argparse.ArgumentParser(description="Flag occluded players in player GT")
    parser.add_argument("gt", help="Ground-truth annotations JSON")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="Containment fraction of own area that counts as occluded (default 0.5)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change, don't write")
    args = parser.parse_args()

    path = Path(args.gt)
    gt = json.loads(path.read_text())
    frames = gt.get("annotated_frames", {}).get("players", {}).get("frames", {})
    if not frames:
        print("No player frames in GT -- nothing to do")
        return

    flags = flag_occluded_frames(frames, args.threshold)
    changed = []
    for frame_str, players in frames.items():
        vis = flags[frame_str]
        for p in players or []:
            new_visible = vis[p["id"]]
            if p.get("visible", True) != new_visible:
                changed.append((frame_str, p["id"], new_visible))
                p["visible"] = new_visible
            elif "visible" not in p:
                p["visible"] = new_visible  # record explicit True too

    n_occluded = sum(1 for vis in flags.values() for v in vis.values() if not v)
    n_total = sum(len(vis) for vis in flags.values())
    print(f"{len(flags)} frames, {n_total} players: {n_occluded} flagged occluded at threshold {args.threshold}")
    for frame_str, pid, vis in changed:
        if not vis:
            print(f"  frame {frame_str}: GT {pid} -> visible: false")

    if args.dry_run:
        print("(dry run -- nothing written)")
        return
    path.write_text(json.dumps(gt, indent=2))
    print(f"Written to {path}")


if __name__ == "__main__":
    main()
