#!/usr/bin/env python3
"""
Test script for court calibration.

Opens the first frame of a video, lets the user click 4 court corners + 2 net posts,
saves the calibration to calibrations/<video_name>.json, and draws the overlay to verify.

If a calibration already exists for that video, it loads it automatically (use --recalibrate to redo).

If `make autocalibrate` / the inbox left a PROPOSAL for the video
(output/<key>/calibration_auto/calibration_auto.json), it is shown first:
[A] takes it as the calibration (recorded as accepted by the owner), [C] clicks
the 8 points as before. --accept-proposal takes it without a window.

Usage:
    python scripts/test_court_calibration.py resources/avp_front_1.mp4
    python scripts/test_court_calibration.py resources/avp_front_1.mp4 --recalibrate
    python scripts/test_court_calibration.py resources/avp_front_1.mp4 --output output/court_test/
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.court_calibration import CourtCalibration
from src.utils.video_upscale import resolve_source_stem

ROOT = Path(__file__).resolve().parent.parent
CALIBRATIONS_DIR = ROOT / "calibrations"
PROPOSAL = ("calibration_auto", "calibration_auto.json")


def get_calibration_path(video_path: str) -> Path:
    """Derive calibration JSON path from video filename.

    Cached upscaled files (see src/utils/video_upscale.py) save under the
    SOURCE stem: the pipeline's auto-detect keys on the source video name
    (calibrations/<source_stem>.json), and a calibration is only valid in
    the pixel space it was clicked in -- i.e. the upscaled file's.
    """
    return CALIBRATIONS_DIR / f"{resolve_source_stem(video_path)}.json"


def proposal_path(video_path: str, output_root: Path = ROOT / "output") -> Path:
    """Where the automatic calibration leaves its proposal for this video."""
    return output_root / resolve_source_stem(video_path) / PROPOSAL[0] / PROPOSAL[1]


def load_proposal(path: Path, frame_shape: Tuple[int, int]) -> Optional[Dict[str, Any]]:
    """The proposal, when there is one FOR THIS PICTURE: a calibration is only
    valid in the pixel space it was found in."""
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text())
        usable = list(doc["frame_dimensions"]) == list(frame_shape) and len(doc["court_corners"]) == 4
    except (ValueError, KeyError, TypeError):
        return None
    return doc if usable else None


def save_accepted_proposal(doc: Dict[str, Any], calib_path: Path) -> None:
    """The proposal as the video's calibration, on the owner's word."""
    doc = dict(doc)
    doc["auto"] = {**(doc.get("auto") or {}), "accepted_by": "owner"}
    calib_path.parent.mkdir(parents=True, exist_ok=True)
    calib_path.write_text(json.dumps(doc, indent=2))


def calibration_from(doc: Dict[str, Any]) -> CourtCalibration:
    calib = CourtCalibration()
    calib.calibrate_from_points(doc["court_corners"], doc["midcourt_points"],
                                tuple(doc["frame_dimensions"]), doc.get("net_top_points"))
    return calib


def ask_about_proposal(frame, doc: Dict[str, Any]) -> str:
    """Show the proposal on the frame: 'accept', 'click' or 'quit'."""
    overlay = calibration_from(doc).draw_court_overlay(frame)
    auto = doc.get("auto") or {}
    sure = "its own checks passed" if auto.get("accepted") else "NOT sure: " + "; ".join(
        auto.get("reasons") or ["look closely"])
    cv2.rectangle(overlay, (0, frame.shape[0] - 90), (frame.shape[1], frame.shape[0]), (0, 0, 0), -1)
    cv2.putText(overlay, f"Automatic calibration ({sure})"[:150], (15, frame.shape[0] - 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(overlay, "[A] Accept it   [C] Click the 8 points yourself   [Q] Cancel",
                (15, frame.shape[0] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (128, 255, 128), 2)
    window = "Court Calibration - proposal"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.imshow(window, overlay)
    try:
        while True:
            key = cv2.waitKey(50) & 0xFF
            if key in (ord("a"), ord("A")):
                return "accept"
            if key in (ord("c"), ord("C")):
                return "click"
            if key in (ord("q"), ord("Q"), 27):
                return "quit"
    finally:
        cv2.destroyWindow(window)


def main():
    parser = argparse.ArgumentParser(description="Test court calibration")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--output", default="output/court_test", help="Output directory for overlay image")
    parser.add_argument("--recalibrate", action="store_true", help="Force recalibration even if saved calibration exists")
    parser.add_argument("--accept-proposal", action="store_true",
                        help="Take the automatic calibration's proposal without showing it")
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

    proposal = None
    if not calib_path.exists() or args.recalibrate:
        proposal = load_proposal(proposal_path(args.video), frame.shape[:2])
    answer = None
    if proposal is not None:
        answer = "accept" if args.accept_proposal else ask_about_proposal(frame, proposal)
        if answer == "quit":
            print("Calibration cancelled")
            sys.exit(1)
    elif args.accept_proposal:
        print(f"Error: no usable proposal at {proposal_path(args.video)}")
        sys.exit(1)

    if answer == "accept":
        save_accepted_proposal(proposal, calib_path)
        calib.load(str(calib_path))
        print(f"Automatic calibration accepted and saved to {calib_path}")
    elif calib_path.exists() and not args.recalibrate:
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

    if args.accept_proposal:                      # no window was asked for
        return

    # Show overlay
    cv2.namedWindow("Court Calibration Result", cv2.WINDOW_NORMAL)
    cv2.imshow("Court Calibration Result", overlay)
    print("\nPress any key to close...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
