#!/usr/bin/env python3
"""
Test script for court calibration.

Opens the first frame of a video, lets the user click 4 court corners + 2 net posts,
saves the calibration, and draws the overlay to verify.

Usage:
    python scripts/test_court_calibration.py resources/full_videos/video.mp4
    python scripts/test_court_calibration.py resources/avp_front_1.mp4 --output output/court_test/
    python scripts/test_court_calibration.py resources/avp_front_1.mp4 --load court_calibration.json
"""

import argparse
import sys
from pathlib import Path

import cv2

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.court_calibration import CourtCalibration


def main():
    parser = argparse.ArgumentParser(description="Test court calibration")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--output", default="output/court_test", help="Output directory")
    parser.add_argument("--save", default="court_calibration.json", help="Calibration save path")
    parser.add_argument("--load", help="Load existing calibration instead of clicking")
    args = parser.parse_args()

    # Open video
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: cannot open video {args.video}")
        sys.exit(1)

    ret, frame = cap.read()
    cap.release()
    if not ret:
        print("Error: cannot read first frame")
        sys.exit(1)

    print(f"Video frame: {frame.shape[1]}x{frame.shape[0]}")

    # Calibrate
    calib = CourtCalibration()

    if args.load:
        calib.load(args.load)
        print(f"Loaded calibration from {args.load}")
    else:
        print("Click 4 court corners (clockwise: far-left, far-right, near-right, near-left)")
        print("Then click 2 net-sideline intersections at ground level (left, right)")
        print("  - NOT the post tops! Click where the net crosses the sideline on the sand.")
        print("Controls: [R] Reset  [U] Undo last point  [Q] Cancel")
        success = calib.calibrate_from_frame(frame, save_path=args.save)
        if not success:
            print("Calibration cancelled")
            sys.exit(1)
        print(f"Calibration saved to {args.save}")

    # Draw overlay and save
    overlay = calib.draw_court_overlay(frame)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "court_calibration_overlay.jpg"
    cv2.imwrite(str(output_path), overlay)
    print(f"Overlay saved to {output_path}")

    # Print stats
    stats = calib.get_court_statistics()
    print("\nCourt Statistics:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Show overlay
    cv2.namedWindow("Court Calibration Result", cv2.WINDOW_NORMAL)
    cv2.imshow("Court Calibration Result", overlay)
    print("\nPress any key to close...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
