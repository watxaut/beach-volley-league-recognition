#!/usr/bin/env python3
"""Calibrate a video's court without clicks (``make autocalibrate``).

    venv/bin/python scripts/auto_calibrate.py resources/<key>.mp4            # proposal only
    venv/bin/python scripts/auto_calibrate.py resources/<key>.mp4 --write    # + calibrations/<key>.json when its own checks pass

Writes the proposal next to the run (``output/<key>/calibration_auto/``): the
plate, an overlay, the 8 points zoomed (``auto_points.jpg``: what to look at)
and ``calibration_auto.json``. ``--write`` saves ``calibrations/<key>.json``
only when the detector ACCEPTED its own result and no calibration exists
yet: a manual calibration is never overwritten. Exit code 0 = accepted,
2 = a proposal the owner must look at (or nothing found), 1 = error.
The detector: ``src/detection/court_autocalibration.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.detection import court_autocalibration as ac  # noqa: E402

PROPOSAL_DIR = "calibration_auto"
PROPOSAL_NAME = "calibration_auto.json"


def write_proposal(out: Path, plate: Any, result: ac.AutoCalibration,
                   manual: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Plate, overlay, 8-point sheet and the proposal JSON into ``out``."""
    out.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out / "plate.png"), plate)
    cv2.imwrite(str(out / "auto_overlay.jpg"), ac.draw(plate, result, manual))
    report: Dict[str, Any] = {"version": ac.VERSION, "accepted": result.accepted,
                              "reasons": result.reasons, "checks": ac.jsonable(result.checks),
                              "points": result.points}
    if result.points is not None:
        cv2.imwrite(str(out / "auto_points.jpg"), ac.contact_sheet(plate, result.points, manual))
        (out / PROPOSAL_NAME).write_text(json.dumps(ac.calibration_document(result), indent=2))
        if manual:
            report["vs_manual"] = ac.compare(result.points, manual)
    (out / "auto_calibration.json").write_text(json.dumps(report, indent=1))
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("video", help="video file")
    parser.add_argument("--debug-dir", help="where the proposal goes "
                        "(default: output/<key>/calibration_auto)")
    parser.add_argument("--write", action="store_true",
                        help="save calibrations/<key>.json when the result is accepted "
                             "and none exists")
    parser.add_argument("--compare", action="store_true",
                        help="also draw / report the existing calibrations/<key>.json")
    parser.add_argument("--no-camera-prior", action="store_true",
                        help="do not use the focal length earlier calibrations agree on")
    parser.add_argument("--calibrations", default=str(ROOT / "calibrations"))
    args = parser.parse_args(argv)

    calibrations = Path(args.calibrations)
    try:
        stem, plate, result = ac.calibrate_video(
            Path(args.video), None if args.no_camera_prior else calibrations)
    except (RuntimeError, ValueError) as exc:        # no such video / nothing decoded
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    target = calibrations / f"{stem}.json"
    manual = json.loads(target.read_text()) if args.compare and target.exists() else None
    out = Path(args.debug_dir) if args.debug_dir else ROOT / "output" / stem / PROPOSAL_DIR
    report = write_proposal(out, plate, result, manual)
    report["stem"] = stem
    print(json.dumps(report, indent=1))
    print(f"proposal: {out}", file=sys.stderr)
    if args.write and result.accepted:
        if target.exists():
            print(f"{target} exists: not overwritten", file=sys.stderr)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(ac.calibration_document(result), indent=2))
            print(f"written: {target}", file=sys.stderr)
    return 0 if result.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
