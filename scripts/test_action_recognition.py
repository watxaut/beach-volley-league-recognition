#!/usr/bin/env python3
"""
Test script for full action recognition pipeline.

Runs detection + tracking + pose + action classification,
draws action labels on players when detected.

Usage:
    python scripts/test_action_recognition.py resources/avp_front_1.mp4
    python scripts/test_action_recognition.py resources/avp_front_1.mp4 --court court_calibration.json --save-video
"""

import argparse
import sys
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.ball_detector import BallDetector
from src.detection.player_detector import PlayerDetector
from src.detection.court_calibration import CourtCalibration
from src.tracking.ball_tracker import BallTracker
from src.tracking.player_tracker import PlayerTracker
from src.recognition.pose_estimator import PoseEstimator
from src.recognition.action_classifier import ActionClassifier

ACTION_COLORS = {
    "serve": (0, 255, 0),
    "block": (255, 0, 0),
    "dig": (0, 255, 255),
    "set": (255, 255, 0),
    "spike": (0, 0, 255),
}


def main():
    parser = argparse.ArgumentParser(description="Test action recognition")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--court", help="Path to court calibration JSON (auto-detected from calibrations/ if omitted)")
    parser.add_argument("--ball-model", help="Path to fine-tuned ball model (auto-detected from models/volleyball_ball_best.pt if omitted)")
    parser.add_argument("--output", default="output/action_test", help="Output directory")
    parser.add_argument("--max-frames", type=int, default=1000, help="Max frames to process")
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
        auto_path = Path(__file__).resolve().parent.parent / "calibrations" / f"{Path(args.video).stem}.json"
        if auto_path.exists():
            court_path = str(auto_path)
            print(f"Auto-loaded court calibration: {court_path}")
    court = CourtCalibration(court_path) if court_path else CourtCalibration()

    # Fine-tuned ball model (auto-detect from models/ if not given). Needed on
    # real footage; the COCO fallback rarely finds a volleyball.
    ball_model = args.ball_model
    if not ball_model:
        auto_model = Path(__file__).resolve().parent.parent / "models" / "volleyball_ball_best.pt"
        if auto_model.exists():
            ball_model = str(auto_model)
            print(f"Auto-loaded ball model: {ball_model}")

    ball_detector = BallDetector(model_path=ball_model, confidence_threshold=0.15)
    player_detector = PlayerDetector(confidence_threshold=0.5)
    ball_tracker = BallTracker(max_missing_frames=10, low_confidence_threshold=0.4, max_trajectory_gap=60.0)
    player_tracker = PlayerTracker(max_players=6, court_calibration=court)
    pose_estimator = PoseEstimator(min_detection_confidence=0.5, model_complexity=1)
    action_classifier = ActionClassifier(
        pose_estimator=pose_estimator,
        confidence_threshold=0.3,
        court_calibration=court,
    )

    if court.is_calibrated and court.court_bounds:
        ball_tracker.set_court_bounds(court.court_bounds)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_name = Path(args.video).stem
    writer = None
    if args.save_video:
        out_path = str(output_dir / f"{video_name}_action_recognition.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    action_counts = defaultdict(int)
    action_log = []
    recent_actions = {}  # track_id -> (frame, action, confidence) for display persistence

    def record_action(action, display_frame):
        act_name = action["action"]
        tid = action.get("track_id", -1)
        conf = action.get("confidence", 0)
        # The classifier confirms a contact a few frames late; report it at its
        # true contact frame so it lines up with ground truth.
        contact_frame = action.get("frame_number", display_frame)
        action_counts[act_name] += 1
        action_log.append({
            "frame": contact_frame,
            "player_id": action.get("player_id"),
            "track_id": tid,
            "action": act_name,
            "gesture": action.get("gesture"),
            "confidence": conf,
            "team": action.get("team"),
            "touch_number": action.get("touch_number"),
            "rally_id": action.get("rally_id"),
            "contact_kind": action.get("contact_kind"),
        })
        recent_actions[tid] = (display_frame, act_name, conf)
        print(f"  Frame {contact_frame}: Player {tid} (idx {action.get('player_id')}) "
              f"[{action.get('gesture')}] -> {act_name} ({conf:.2f})")

    for frame_idx in range(min(args.max_frames, total)):
        ret, frame = cap.read()
        if not ret:
            break

        # Detection
        ball_dets = ball_detector.detect(frame)
        player_dets = player_detector.detect(frame)
        if court.is_calibrated:
            player_dets = court.filter_detections_by_court(player_dets)

        # Tracking
        tracked_players = player_tracker.update(player_dets, frame)
        tracked_ball = ball_tracker.update(ball_dets)

        # Action classification
        actions = action_classifier.classify_actions(
            frame, tracked_players, tracked_ball, frame_number=frame_idx
        )

        for action in actions:
            record_action(action, frame_idx)

        # Draw court
        if court.is_calibrated:
            frame = court.draw_court_overlay(frame)

        # Draw ball
        if tracked_ball:
            cx, cy = int(tracked_ball["center"][0]), int(tracked_ball["center"][1])
            color = (0, 0, 255) if tracked_ball.get("is_predicted") else (0, 255, 0)
            cv2.circle(frame, (cx, cy), 8, color, -1)

        # Draw players with action labels
        for player in tracked_players:
            tid = player.get("track_id", -1)
            bbox = player["bbox"]
            x1, y1, x2, y2 = [int(v) for v in bbox]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            label = f"P{tid}"
            # Show recent action (persist for 30 frames)
            if tid in recent_actions:
                act_frame, act_name, act_conf = recent_actions[tid]
                if frame_idx - act_frame < 30:
                    label += f" {act_name.upper()}"
                    color = ACTION_COLORS.get(act_name, (255, 255, 255))
                    cv2.putText(frame, f"{act_name} ({act_conf:.2f})", (x1, y1 - 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            cv2.putText(frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        if writer:
            writer.write(frame)

    # Finalise the last contact still held for its look-ahead (context layer).
    for action in action_classifier.flush():
        record_action(action, frame_idx)

    cap.release()
    if writer:
        writer.release()
        print(f"\nAnnotated video saved to {output_dir / f'{video_name}_action_recognition.mp4'}")

    # Save action log
    import json
    log_path = output_dir / f"{video_name}_action_log.json"
    with open(log_path, "w") as f:
        json.dump(action_log, f, indent=2)
    print(f"Action log saved to {log_path}")

    print(f"\n{'='*50}")
    print(f"  Action Recognition Summary")
    print(f"{'='*50}")
    print(f"  Total actions detected: {sum(action_counts.values())}")
    for action, count in sorted(action_counts.items()):
        print(f"    {action:10s}: {count}")


if __name__ == "__main__":
    main()
