#!/usr/bin/env python3
"""
Test script for court calibration.

Opens the first frame of a video, lets the user click 4 court corners + 2 net posts,
saves the calibration to calibrations/<video_name>.json, and draws the overlay to verify.

If a calibration already exists for that video, it loads it automatically (use --recalibrate to redo).

Usage:
    python scripts/test_court_calibration.py resources/avp_front_1.mp4
    python scripts/test_court_calibration.py resources/avp_front_1.mp4 --recalibrate
    python scripts/test_court_calibration.py resources/avp_front_1.mp4 --output output/court_test/
"""

import argparse
import sys
from pathlib import Path

import cv2

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.court_calibration import CourtCalibration
from src.utils.video_upscale import resolve_source_stem

CALIBRATIONS_DIR = Path(__file__).resolve().parent.parent / "calibrations"


def get_calibration_path(video_path: str) -> Path:
    """Derive calibration JSON path from video filename.

    Cached upscaled files (see src/utils/video_upscale.py) save under the
    SOURCE stem: the pipeline's auto-detect keys on the source video name
    (calibrations/<source_stem>.json), and a calibration is only valid in
    the pixel space it was clicked in -- i.e. the upscaled file's.
    """
    return CALIBRATIONS_DIR / f"{resolve_source_stem(video_path)}.json"


def main():
    parser = argparse.ArgumentParser(description="Test court calibration")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--output", default="output/court_test", help="Output directory for overlay image")
    parser.add_argument("--recalibrate", action="store_true", help="Force recalibration even if saved calibration exists")
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

    calib_path = get_calibration_path(args.video)
    calib = CourtCalibration()

    if calib_path.exists() and not args.recalibrate:
        calib.load(str(calib_path))
        print(f"Loaded existing calibration from {calib_path}")
    else:
        CALIBRATIONS_DIR.mkdir(parents=True, exist_ok=True)
        print("Click 8 points:")
        print("  1-4: Court corners (clockwise: far-left, far-right, near-right, near-left)")
        print("  5-6: Midcourt ground line (left, right) - on the SAND where court changes sides")
        print("  7-8: Net top (left, right) - top edge of the net at each post")
        print("Controls: [R] Reset  [U] Undo last point  [Q] Cancel")
        success = calib.calibrate_from_frame(frame, save_path=str(calib_path))
        if not success:
            print("Calibration cancelled")
            sys.exit(1)
        print(f"Calibration saved to {calib_path}")

    # Draw overlay and save
    overlay = calib.draw_court_overlay(frame)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    video_name = Path(args.video).stem
    output_path = output_dir / f"{video_name}_court_overlay.jpg"
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
