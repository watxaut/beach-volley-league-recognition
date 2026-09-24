#!/usr/bin/env python3
"""
Test script for pose estimation with normalized features.

Runs player detection + tracking + pose estimation, draws skeleton overlays,
and shows normalized feature values.

Usage:
    python scripts/test_pose_estimation.py resources/avp_front_1.mp4
    python scripts/test_pose_estimation.py resources/avp_front_1.mp4 --save-video
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.player_detector import PlayerDetector
from src.detection.court_calibration import CourtCalibration
from src.tracking.player_tracker import PlayerTracker
from src.recognition.pose_estimator import PoseEstimator
from src.utils.video_upscale import resolve_source_stem

# MediaPipe pose connections for drawing skeleton
POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # Arms
    (11, 23), (12, 24), (23, 24),  # Torso
    (23, 25), (25, 27), (24, 26), (26, 28),  # Legs
]


def main():
    parser = argparse.ArgumentParser(description="Test pose estimation")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--court", help="Path to court calibration JSON (auto-detected from calibrations/ if omitted)")
    parser.add_argument("--output", default="output/pose_test", help="Output directory")
    parser.add_argument("--max-frames", type=int, default=300, help="Max frames to process")
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

    # Load court calibration (auto-detect from calibrations/<video_name>.json)
    court_path = args.court
    if not court_path:
        auto_path = Path(__file__).resolve().parent.parent / "calibrations" / f"{resolve_source_stem(args.video)}.json"
        if auto_path.exists():
            court_path = str(auto_path)
            print(f"Auto-loaded court calibration: {court_path}")
    court = CourtCalibration(court_path) if court_path else CourtCalibration()
    detector = PlayerDetector(confidence_threshold=0.5)
    tracker = PlayerTracker(max_players=4, court_calibration=court)
    pose_estimator = PoseEstimator(min_detection_confidence=0.5, model_complexity=1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_name = Path(args.video).stem
    writer = None
    if args.save_video:
        out_path = str(output_dir / f"{video_name}_pose_estimation.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    pose_count = 0
    no_pose_count = 0

    for frame_idx in range(min(args.max_frames, total)):
        ret, frame = cap.read()
        if not ret:
            break

        detections = detector.detect(frame)
        if court.is_calibrated:
            detections = court.filter_detections_by_court(detections)
        tracked = tracker.update(detections, frame)

        for player in tracked:
            bbox = player["bbox"]
            tid = player.get("track_id", -1)
            pose_data = pose_estimator.estimate_pose(frame, bbox)

            if pose_data is None:
                no_pose_count += 1
                continue

            pose_count += 1
            kps = pose_data.get("keypoints_dict", {})
            features = pose_data.get("pose_features", {})

            # Draw skeleton
            for (a, b) in POSE_CONNECTIONS:
                if a in kps and b in kps:
                    pa = kps[a]
                    pb = kps[b]
                    if pa["visibility"] > 0.5 and pb["visibility"] > 0.5:
                        pt1 = (int(pa["x"]), int(pa["y"]))
                        pt2 = (int(pb["x"]), int(pb["y"]))
                        cv2.line(frame, pt1, pt2, (0, 255, 255), 2)

            # Draw keypoints
            for kp_id, kp in kps.items():
                if kp["visibility"] > 0.5:
                    cv2.circle(frame, (int(kp["x"]), int(kp["y"])), 3, (0, 0, 255), -1)

            # Show normalized features
            x1 = int(bbox[0])
            y2 = int(bbox[3])
            feat_strs = []
            for key in ["avg_wrist_height_ratio", "wrist_height_diff", "body_lean"]:
                if key in features:
                    feat_strs.append(f"{key[:12]}={features[key]:.2f}")

            for i, s in enumerate(feat_strs):
                cv2.putText(frame, s, (x1, y2 + 15 + i * 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

        if writer:
            writer.write(frame)

    cap.release()
    if writer:
        writer.release()
        print(f"Annotated video saved to {output_dir / f'{video_name}_pose_estimation.mp4'}")

    total_attempts = pose_count + no_pose_count
    print(f"\n{'='*50}")
    print(f"  Pose Estimation Summary")
    print(f"{'='*50}")
    print(f"  Total attempts:  {total_attempts}")
    print(f"  Successful:      {pose_count} ({pose_count/max(1,total_attempts):.1%})")
    print(f"  Failed:          {no_pose_count}")


if __name__ == "__main__":
    main()
