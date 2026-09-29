#!/usr/bin/env python3
"""
Test script for player tracking with 4-player lock.

Runs player detection + tracking, draws bounding boxes with stable IDs
and team colors.

Usage:
    python scripts/test_player_tracking.py resources/avp_front_1.mp4
    python scripts/test_player_tracking.py resources/avp_front_1.mp4 --court court_calibration.json --save-video
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.player_detector import PlayerDetector
from src.detection.court_calibration import CourtCalibration
from src.detection.calibration_readiness import resolve_script_calibration
from src.tracking.player_tracker import PlayerTracker
from src.utils.video_upscale import resolve_source_stem

# Team colors
TEAM_COLORS = {
    "A": (255, 0, 0),    # Blue for Team A
    "B": (0, 165, 255),  # Orange for Team B
    None: (0, 255, 0),   # Green for unknown
}

PLAYER_COLORS = {
    1: (255, 0, 0),
    2: (255, 100, 100),
    3: (0, 165, 255),
    4: (100, 200, 255),
}


def main():
    parser = argparse.ArgumentParser(description="Test player tracking")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--court", help="Path to court calibration JSON (auto-detected from calibrations/ if omitted)")
    parser.add_argument("--output", default="output/player_test", help="Output directory")
    parser.add_argument("--max-frames", type=int, default=500, help="Max frames to process")
    parser.add_argument("--save-video", action="store_true", help="Save annotated video")
    parser.add_argument("--allow-uncalibrated", action="store_true",
                        help="Run without a usable court calibration (court admission, "
                             "serve-zone admission and the bystander guard are DEGRADED "
                             "-- track IDs are NOT comparable with calibrated runs).")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: cannot open {args.video}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Court calibration + readiness gate: track quality measured without a court
    # is a different (and much better-looking) measurement.
    court_path = resolve_script_calibration(
        args.video, args.court, args.allow_uncalibrated,
        calibrations_dir=Path(__file__).resolve().parent.parent / "calibrations",
        script_name=Path(__file__).name,
    )
    court = CourtCalibration(court_path) if court_path else CourtCalibration()

    detector = PlayerDetector(confidence_threshold=0.5)
    tracker = PlayerTracker(max_players=4, court_calibration=court)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_name = Path(args.video).stem
    writer = None
    if args.save_video:
        out_path = str(output_dir / f"{video_name}_player_tracking.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    id_seen = set()
    max_simultaneous = 0

    for frame_idx in range(min(args.max_frames, total)):
        ret, frame = cap.read()
        if not ret:
            break

        detections = detector.detect(frame)
        if court.is_calibrated:
            detections = court.filter_detections_by_court(detections)

        tracked = tracker.update(detections, frame)
        max_simultaneous = max(max_simultaneous, len(tracked))

        # Draw court overlay
        if court.is_calibrated:
            frame = court.draw_court_overlay(frame)

        for player in tracked:
            tid = player.get("track_id", -1)
            team = player.get("team")
            bbox = player["bbox"]
            x1, y1, x2, y2 = [int(v) for v in bbox]

            id_seen.add(tid)
            color = PLAYER_COLORS.get(tid, TEAM_COLORS.get(team, (0, 255, 0)))

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"P{tid}"
            if team:
                label += f" T{team}"
            cv2.putText(frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        status = f"Frame {frame_idx} | Players: {len(tracked)} | IDs: {sorted(id_seen)}"
        cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        if writer:
            writer.write(frame)

    cap.release()
    if writer:
        writer.release()
        print(f"Annotated video saved to {output_dir / f'{video_name}_player_tracking.mp4'}")

    print(f"\n{'='*50}")
    print(f"  Player Tracking Summary")
    print(f"{'='*50}")
    print(f"  Unique IDs seen:      {sorted(id_seen)}")
    print(f"  Total unique IDs:     {len(id_seen)}")
    print(f"  Max simultaneous:     {max_simultaneous}")
    print(f"  Expected (beach VB):  4")
    print(f"  Ghost players:        {max(0, len(id_seen) - 4)}")


if __name__ == "__main__":
    main()
