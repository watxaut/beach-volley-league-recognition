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

    def record_action(action):
        act_name = action["action"]
        tid = action.get("track_id", -1)
        conf = action.get("confidence", 0)
        # frame_number is the TRUE contact frame. The classifier confirms a
        # contact a few frames late and finalises it only once the NEXT contact
        # arrives (look-ahead), so an event is *emitted* well after its contact.
        # We anchor the on-screen label to frame_number in pass 2 so the label
        # appears on the contact frame, not where it happened to be emitted.
        contact_frame = action.get("frame_number")
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
        print(f"  Frame {contact_frame}: Player {tid} (idx {action.get('player_id')}) "
              f"[{action.get('gesture')}] -> {act_name} ({conf:.2f})")

    # ---- Pass 1: detect / track / classify. Cache lightweight per-frame overlay
    # data (ball + player boxes) so pass 2 can redraw without re-running YOLO. ----
    frame_cache = []
    for frame_idx in range(min(args.max_frames, total)):
        ret, frame = cap.read()
        if not ret:
            break

        ball_dets = ball_detector.detect(frame)
        player_dets = player_detector.detect(frame)
        if court.is_calibrated:
            player_dets = court.filter_detections_by_court(player_dets)

        tracked_players = player_tracker.update(player_dets, frame)
        tracked_ball = ball_tracker.update(ball_dets)

        actions = action_classifier.classify_actions(
            frame, tracked_players, tracked_ball, frame_number=frame_idx
        )
        for action in actions:
            record_action(action)

        ball_draw = None
        if tracked_ball and tracked_ball.get("center") and tracked_ball["center"][0] is not None:
            ball_draw = (int(tracked_ball["center"][0]), int(tracked_ball["center"][1]),
                         bool(tracked_ball.get("is_predicted")))
        frame_cache.append({
            "ball": ball_draw,
            "players": [(p.get("track_id", -1), [int(v) for v in p["bbox"]]) for p in tracked_players],
        })

    # Finalise the last contact still held for its look-ahead (context layer).
    for action in action_classifier.flush():
        record_action(action)

    cap.release()

    # ---- Build a per-track label plan anchored on each action's contact frame ----
    LABEL_PERSIST = 30  # frames a label stays on screen after its contact
    events_by_track = defaultdict(list)
    for e in action_log:
        if e["frame"] is not None:
            events_by_track[e["track_id"]].append((e["frame"], e["action"], e["confidence"]))

    def label_for(tid, frame_idx):
        """Most-recent action for this track whose window covers frame_idx."""
        best = None
        for cf, name, conf in events_by_track.get(tid, []):
            if cf <= frame_idx < cf + LABEL_PERSIST and (best is None or cf > best[0]):
                best = (cf, name, conf)
        return best

    # ---- Pass 2: redraw from cache, labels anchored on the true contact frame ----
    if writer:
        cap = cv2.VideoCapture(args.video)
        for frame_idx, cache in enumerate(frame_cache):
            ret, frame = cap.read()
            if not ret:
                break

            if court.is_calibrated:
                frame = court.draw_court_overlay(frame)

            if cache["ball"] is not None:
                bx, by, pred = cache["ball"]
                cv2.circle(frame, (bx, by), 8, (0, 0, 255) if pred else (0, 255, 0), -1)

            for tid, (x1, y1, x2, y2) in cache["players"]:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                lab = label_for(tid, frame_idx)
                if lab is not None:
                    _, act_name, act_conf = lab
                    color = ACTION_COLORS.get(act_name, (255, 255, 255))
                    cv2.putText(frame, f"{act_name} ({act_conf:.2f})", (x1, y1 - 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                cv2.putText(frame, f"P{tid}", (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            writer.write(frame)

        cap.release()
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
