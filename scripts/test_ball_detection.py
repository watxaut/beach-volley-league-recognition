#!/usr/bin/env python3
"""
Test script for ball detection.

Runs YOLO ball detection frame-by-frame, draws detected positions,
and reports detection rate.

Usage:
    python scripts/test_ball_detection.py resources/avp_front_1.mp4
    python scripts/test_ball_detection.py resources/avp_front_1.mp4 --output output/ball_test/ --max-frames 300
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.ball_detector import BallDetector


def main():
    parser = argparse.ArgumentParser(description="Test ball detection")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--output", default="output/ball_test", help="Output directory")
    parser.add_argument("--max-frames", type=int, default=500, help="Max frames to process")
    parser.add_argument("--confidence", type=float, default=0.9, help="Detection confidence threshold")
    parser.add_argument("--model", type=str, default=None, help="Path to custom YOLO model weights")
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
    print(f"Video: {w}x{h} @ {fps:.1f}fps, {total} frames")

    # keep_all=True so every detection above the confidence threshold is drawn,
    # including false positives -- this is a diagnostic script, not the tracker.
    detector = BallDetector(
        model_path=args.model,
        confidence_threshold=args.confidence,
        keep_all=True,
    )

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_name = Path(args.video).stem
    writer = None
    if args.save_video:
        out_path = str(output_dir / f"{video_name}_ball_detection.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    detected_frames = 0
    total_frames = 0
    confidences = []

    for frame_idx in range(min(args.max_frames, total)):
        ret, frame = cap.read()
        if not ret:
            break

        total_frames += 1
        detections = detector.detect(frame)

        if detections:
            detected_frames += 1
            for det in detections:
                conf = det["confidence"]
                confidences.append(conf)
                cx, cy = int(det["center"][0]), int(det["center"][1])
                x1, y1, x2, y2 = det["bbox"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
                cv2.putText(frame, f"{conf:.2f}", (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        cv2.putText(frame, f"Frame {frame_idx} | Balls: {len(detections)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        if writer:
            writer.write(frame)

        if frame_idx % 100 == 0:
            print(f"  Frame {frame_idx}/{min(args.max_frames, total)} | Detection rate: {detected_frames}/{total_frames}")

    cap.release()
    if writer:
        writer.release()
        print(f"\nAnnotated video saved to {output_dir / f'{video_name}_ball_detection.mp4'}")

    # Print summary
    rate = detected_frames / total_frames if total_frames > 0 else 0
    avg_conf = np.mean(confidences) if confidences else 0
    print(f"\n{'='*50}")
    print(f"  Ball Detection Summary")
    print(f"{'='*50}")
    print(f"  Frames processed: {total_frames}")
    print(f"  Frames with ball: {detected_frames}")
    print(f"  Detection rate:   {rate:.1%}")
    print(f"  Avg confidence:   {avg_conf:.3f}")
    if confidences:
        print(f"  Min confidence:   {min(confidences):.3f}")
        print(f"  Max confidence:   {max(confidences):.3f}")


if __name__ == "__main__":
    main()
