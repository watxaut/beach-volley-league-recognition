#!/usr/bin/env python3
"""Quick verifier for action annotations produced by annotate_video.py.

Loads a JSON file and prints the action sequence with rally-state context,
so you can sanity-check the auto-tracking without re-launching the GUI.

Usage:
    python scripts/verify_action_labels.py ground_truth/video_annotations.json
    python scripts/verify_action_labels.py ground_truth/video_annotations.json --rally 2
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("annotations", help="Path to annotation JSON")
    parser.add_argument(
        "--rally", type=int, default=None,
        help="Only show events from this rally_id",
    )
    args = parser.parse_args()

    path = Path(args.annotations)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    events = data.get("annotated_frames", {}).get("actions", {}).get("events", [])
    if not events:
        print("No action events found.")
        return

    events = sorted(events, key=lambda e: e["frame"])

    video = data.get("video", "?")
    fps = data.get("fps", 30)
    print(f"Video: {video}")
    print(f"Total events: {len(events)}")
    print()

    header = (
        f"{'Frame':>6}  {'Time':>7}  {'Rally':>5}  {'Team':>4}  "
        f"{'Touch':>5}  {'PrevAtk':>7}  {'Final':<8}  {'Raw':<24}  Player"
    )
    print(header)
    print("-" * len(header))

    for e in events:
        if args.rally is not None and e.get("rally_id") != args.rally:
            continue
        time_s = e["frame"] / fps if fps else 0
        raw = ",".join(e.get("raw_visual_actions", []))
        prev_atk = "Y" if e.get("preceded_by_attack") else "-"
        team = e.get("team_in_possession") or "?"
        overrides = e.get("overrides") or {}
        team_str = team + ("*" if "team_in_possession" in overrides else "")
        touch_str = str(e.get("touch_number", 0)) + (
            "*" if "touch_number" in overrides else ""
        )
        print(
            f"{e['frame']:>6}  {time_s:>6.1f}s  {e.get('rally_id', 0):>5}  "
            f"{team_str:>4}  {touch_str:>5}  {prev_atk:>7}  "
            f"{e['final_action']:<8}  {raw:<24}  P{e.get('player_id', '?')}"
        )

    # Counts per final_action
    counts: dict = {}
    for e in events:
        counts[e["final_action"]] = counts.get(e["final_action"], 0) + 1
    print()
    print("Action counts:")
    for action, count in sorted(counts.items()):
        print(f"  {action}: {count}")

    # Touch number distribution
    touches: dict = {}
    for e in events:
        tn = e.get("touch_number", 0)
        touches[tn] = touches.get(tn, 0) + 1
    print()
    print("Touch number distribution:")
    for tn in sorted(touches):
        print(f"  Touch {tn}: {touches[tn]} events")

    # Override count
    n_overrides = sum(1 for e in events if e.get("overrides"))
    if n_overrides:
        print()
        print(f"Events with manual overrides: {n_overrides}")


if __name__ == "__main__":
    main()
