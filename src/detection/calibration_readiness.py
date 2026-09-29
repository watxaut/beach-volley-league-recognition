"""Calibration / view readiness: is this run's court geometry trustworthy?

Extracted from ``src/main.py`` (commit 0761cdc) so the probe scripts in
``scripts/`` can apply the SAME precondition as the batch pipeline. The whole
point of the check is that an uncalibrated run silently drops every
court-derived feature; that is only visible if the entry point says so.

Two layers:

* :func:`build_calibration_readiness` / :func:`format_readiness` /
  :func:`validate_calibration_readiness` -- the report and the hard gate
  (``main.py`` uses these verbatim; behaviour unchanged).
* :func:`resolve_script_calibration` -- the same gate packaged for a probe
  script: auto-detect ``calibrations/<source_stem>.json``, print the report and
  exit non-zero unless the calibration is usable or ``--allow-uncalibrated``
  was passed. Scripts are cwd-independent, so the calibrations dir is passed
  in by the caller.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2

from src.utils.video_upscale import resolve_source_stem

# Court-derived features that silently disappear when no calibration is loaded.
# Each entry names the gate that turns it off, so the readiness report is a list
# of the code paths that are currently DEAD in this run, not a generic warning.
#   action_classifier: _court_ready() (team-aware attribution, :853-854),
#   :520-526 (foot-team re-entry scoring), :570-585 (above-net re-entry gate),
#   :975-988 (near-net ground-metre attribution exemption), :1061-1066
#   (foot_team / near_net / behind_baseline gesture context);
#   player_tracker: :1038 (court admission -> bystander guard + serve-zone
#   admission), frame_processor: :68 (strict in-court filter);
#   player_detector: :178-197 (play-area mask filter);
#   ball_tracker via frame_processor: :109 (court-bounds out-of-bounds reject);
#   spike_analyzer: get_court_zone / world_point_to_zone (attack/landing/dug zones).
DEGRADED_OUTPUTS_WITHOUT_CALIBRATION = (
    "team_attribution",
    "near_net_gesture_context",
    "behind_baseline",
    "above_net_reentry_gate",
    "serve_zone_admission",
    "bystander_guard",
    "court_filtered_detections",
    "ball_out_of_bounds_reject",
    "spike_attack_zone",
    "spike_landing_zone",
    "spike_dug_zone",
)

# CourtCalibration.load() substitutes this when the JSON has no frame_dimensions.
DEFAULT_CALIBRATION_FRAME_DIMENSIONS = (1080, 1920)  # (h, w)

# Aspect ratios within this relative tolerance are treated as the same view.
ASPECT_RATIO_TOLERANCE = 0.02


def read_video_dimensions(video_path: Path) -> Optional[Tuple[int, int]]:
    """(width, height) of a video, or None if it cannot be opened."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        return None
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if width <= 0 or height <= 0:
        return None
    return width, height


def read_calibration_frame_dimensions(court_path: str) -> Tuple[int, int]:
    """``frame_dimensions`` (h, w) stored in a calibration JSON.

    Mirrors ``CourtCalibration.load`` (court_calibration.py:830): a calibration
    without the key is assumed to be 1920x1080.

    Raises:
        OSError / ValueError: if the file is missing or is not a valid JSON
            calibration (``CourtCalibration`` would silently ignore it).
    """
    with open(court_path, "r") as f:
        data = json.load(f)
    dims = data.get("frame_dimensions")
    return tuple(dims) if dims else DEFAULT_CALIBRATION_FRAME_DIMENSIONS


def build_calibration_readiness(
    court_path: Optional[str],
    source_stem: str,
    video_file: Path,
    origin: str = "auto_stem",
) -> Dict[str, Any]:
    """Describe the calibration/view state of this run.

    Args:
        origin: HOW the path was resolved -- "explicit" when --court was
            given, "auto_stem" when calibrations/<source_stem>.json was picked
            up, "none" when there is no calibration at all. (Independent of
            ``stem_matched``: an explicit --court may still be named after the
            source video.)

    Keys:
        calibration_path: file actually used, or None.
        calibration_source: "explicit" (--court), "auto_stem"
            (calibrations/<source_stem>.json) or "none".
        stem_matched: the calibration file is named after THIS video's stem --
            False for an explicit --court borrowed from another recording, which
            is only safe when the two views share a camera.
        calibration_frame_dimensions / video_dimensions: both emitted as
            {"width": W, "height": H} -- the JSON stores (h, w), the video is
            decoded (post `ensure_1080` upscale), so the two orders differ.
        dimensions_match: exact match of the two (w, h) pairs.
        aspect_ratio_match: same view shape within ASPECT_RATIO_TOLERANCE.
        calibration_scaled_to_video: always False. The pipeline does NOT rescale
            a calibration to the processed frame: `frame_dimensions` only sizes
            `court_mask` / the play-area mask (court_calibration.py:316-320), and
            the stored points are used verbatim. A smaller calibration is
            therefore not merely imprecise -- `PlayerDetector._is_player_in_court`
            clamps every bbox into the mask bounds and `is_point_in_court`
            rejects anything below the mask height, so near-half players vanish.
        degraded_outputs: court-derived features that are off in this run.
    """
    video_file = Path(video_file)
    video_dims = read_video_dimensions(video_file)
    calib_dims = None
    read_error = None
    if court_path:
        try:
            calib_dims = read_calibration_frame_dimensions(court_path)
        except (OSError, ValueError) as exc:
            # CourtCalibration's constructor ignores a non-existent path, so a
            # broken --court silently produced an uncalibrated run before.
            read_error = str(exc)

    stem_matched = bool(court_path) and Path(court_path).stem == source_stem
    source = "none" if court_path is None else origin

    dimensions_match = bool(calib_dims) and bool(video_dims) and tuple(calib_dims) == (video_dims[1], video_dims[0])
    aspect_ratio_match = False
    if calib_dims and video_dims:
        calib_ar = calib_dims[1] / calib_dims[0]
        video_ar = video_dims[0] / video_dims[1]
        aspect_ratio_match = abs(calib_ar - video_ar) / video_ar <= ASPECT_RATIO_TOLERANCE

    usable = bool(calib_dims) and dimensions_match and aspect_ratio_match
    return {
        "calibration_path": court_path,
        "calibration_source": source,
        "source_stem": source_stem,
        "stem_matched": stem_matched,
        "calibration_frame_dimensions": (
            {"height": calib_dims[0], "width": calib_dims[1]} if calib_dims else None
        ),
        "video_dimensions": (
            {"width": video_dims[0], "height": video_dims[1]} if video_dims else None
        ),
        "dimensions_match": dimensions_match,
        "aspect_ratio_match": aspect_ratio_match,
        "calibration_scaled_to_video": False,
        "read_error": read_error,
        "usable": usable,
        "degraded_outputs": [] if usable else list(DEGRADED_OUTPUTS_WITHOUT_CALIBRATION),
    }


def format_readiness(readiness: Dict[str, Any]) -> str:
    """One-block, human-readable readiness summary for the startup log."""
    lines = [
        "--- Calibration / view readiness ---",
        f"  calibration      : {readiness['calibration_path'] or 'NONE'}"
        f"  (source: {readiness['calibration_source']},"
        f" stem matched: {readiness['stem_matched']})",
        f"  video size       : {readiness['video_dimensions']}",
        f"  calibration size : {readiness['calibration_frame_dimensions']}"
        f"  exact match: {readiness['dimensions_match']},"
        f" aspect ratio match: {readiness['aspect_ratio_match']}",
        "  rescaled to video: no -- calibration points are used verbatim",
        f"  usable           : {readiness['usable']}",
    ]
    if readiness["degraded_outputs"]:
        lines.append(
            "  DEGRADED outputs : " + ", ".join(readiness["degraded_outputs"])
        )
    return "\n".join(lines)


def validate_calibration_readiness(
    readiness: Dict[str, Any], allow_uncalibrated: bool
) -> None:
    """Fail the run unless the calibration is usable (or explicitly waived).

    Raises:
        ValueError: with the reason and the --allow-uncalibrated escape hatch.
    """
    if readiness["usable"]:
        return

    if readiness["calibration_path"] is None:
        reason = (
            "no court calibration found (expected calibrations/"
            f"{readiness['source_stem']}.json, or pass --court)"
        )
    elif readiness.get("read_error"):
        reason = (
            f"calibration {readiness['calibration_path']} could not be read: "
            f"{readiness['read_error']}"
        )
    elif not readiness["dimensions_match"] or not readiness["aspect_ratio_match"]:
        reason = (
            f"calibration frame_dimensions {readiness['calibration_frame_dimensions']} "
            f"do not fit the video {readiness['video_dimensions']}; "
            "the calibration is NOT rescaled, so the court mask would be the "
            "wrong size and near-half players would be filtered out"
        )
    else:
        reason = f"calibration {readiness['calibration_path']} is not usable"

    degraded = ", ".join(readiness["degraded_outputs"])
    if allow_uncalibrated:
        logging.getLogger(__name__).warning(
            "UNUSABLE COURT CALIBRATION (%s). Proceeding anyway because "
            "--allow-uncalibrated was passed. Court-derived features are OFF: "
            "%s. Numbers from this run are not comparable with calibrated runs.",
            reason, degraded,
        )
        return

    raise ValueError(
        f"Unusable court calibration: {reason}. Court-derived features would be "
        f"OFF ({degraded}). Fix the calibration (or point --court at a matching "
        "one), or pass --allow-uncalibrated to run degraded on purpose."
    )


def resolve_script_calibration(
    video: str,
    court: Optional[str],
    allow_uncalibrated: bool,
    calibrations_dir: Path,
    script_name: str = "this script",
) -> Optional[str]:
    """Auto-detect the calibration, report readiness, and gate the run.

    The script-level counterpart of ``main.py``'s check: same functions, same
    verdict, so a probe script cannot quietly produce uncalibrated numbers
    that are then compared against calibrated baselines.

    Args:
        video: the video the script is about to decode.
        court: explicit ``--court`` value, or None to auto-detect
            ``<calibrations_dir>/<source_stem>.json``.
        allow_uncalibrated: the ``--allow-uncalibrated`` escape hatch.
        calibrations_dir: repository ``calibrations/`` directory (scripts are
            run from anywhere, so it is not resolved relative to the cwd).
        script_name: used in the error message.

    Returns:
        The calibration path to load, or None when running uncalibrated on
        purpose (``--allow-uncalibrated``).

    Raises:
        SystemExit: with code 1 and a readable message on stderr when the
            calibration is missing / unreadable / mismatched and the waiver was
            not passed.
    """
    source_stem = resolve_source_stem(video)
    court_path = court
    if not court_path:
        auto_path = Path(calibrations_dir) / f"{source_stem}.json"
        if auto_path.exists():
            court_path = str(auto_path)

    readiness = build_calibration_readiness(
        court_path,
        source_stem,
        Path(video),
        origin="explicit" if court else "auto_stem",
    )
    print(format_readiness(readiness))
    try:
        validate_calibration_readiness(readiness, allow_uncalibrated)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(
            f"Error: {script_name} refuses to report numbers it cannot "
            "calibrate for. (Scripts read the video at its native resolution; "
            "if the source is sub-1080p, point --court at the matching "
            "calibration or at the upscaled cache.)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return court_path
