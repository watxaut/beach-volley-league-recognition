#!/usr/bin/env python3
"""
Test script for ball tracking.

Runs ball detection + tracking, draws trajectory on frames,
highlights detected vs predicted positions.

Usage:
    python scripts/test_ball_tracking.py resources/avp_front_1.mp4
    python scripts/test_ball_tracking.py resources/avp_front_1.mp4 --output output/tracking_test/ --save-video
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.ball_detector import BallDetector
from src.tracking.ball_tracker import BallTracker


def main():
    parser = argparse.ArgumentParser(description="Test ball tracking")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--output", default="output/tracking_test", help="Output directory")
    parser.add_argument("--max-frames", type=int, default=500, help="Max frames to process")
    parser.add_argument("--save-video", action="store_true", help="Save annotated video")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: cannot open {args.video}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    detector = BallDetector(confidence_threshold=0.15)
    tracker = BallTracker(max_missing_frames=10, low_confidence_threshold=0.4, max_trajectory_gap=60.0)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    writer = None
    if args.save_video:
        out_path = str(output_dir / "ball_tracking.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    detected_count = 0
    predicted_count = 0
    lost_count = 0
    trajectory_points = []

    for frame_idx in range(min(args.max_frames, total)):
        ret, frame = cap.read()
        if not ret:
            break

        detections = detector.detect(frame)
        tracked = tracker.update(detections)

        if tracked:
            cx, cy = int(tracked["center"][0]), int(tracked["center"][1])
            is_predicted = tracked.get("is_predicted", False)

            if is_predicted:
                predicted_count += 1
                color = (0, 0, 255)  # Red for predicted
                label = "PRED"
            else:
                detected_count += 1
                color = (0, 255, 0)  # Green for detected
                label = "DET"

            trajectory_points.append((cx, cy, is_predicted))

            cv2.circle(frame, (cx, cy), 8, color, -1)
            cv2.putText(frame, label, (cx + 10, cy - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # Draw trajectory tail (last 30 points)
            recent = trajectory_points[-30:]
            for i in range(1, len(recent)):
                px, py, pred_prev = recent[i - 1]
                nx, ny, pred_curr = recent[i]
                c = (0, 0, 255) if pred_curr else (0, 255, 0)
                cv2.line(frame, (px, py), (nx, ny), c, 2)
        else:
            lost_count += 1

        total_processed = frame_idx + 1
        status = f"Frame {frame_idx} | Det:{detected_count} Pred:{predicted_count} Lost:{lost_count}"
        cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        if writer:
            writer.write(frame)

    cap.release()
    if writer:
        writer.release()
        print(f"Annotated video saved to {output_dir / 'ball_tracking.mp4'}")

    total_processed = detected_count + predicted_count + lost_count
    print(f"\n{'='*50}")
    print(f"  Ball Tracking Summary")
    print(f"{'='*50}")
    print(f"  Frames processed:   {total_processed}")
    print(f"  Detected (green):   {detected_count} ({detected_count/total_processed:.1%})")
    print(f"  Predicted (red):    {predicted_count} ({predicted_count/total_processed:.1%})")
    print(f"  Lost (no output):   {lost_count} ({lost_count/total_processed:.1%})")


if __name__ == "__main__":
    main()
