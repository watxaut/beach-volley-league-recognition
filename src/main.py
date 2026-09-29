"""
Beach Volleyball Video Analysis System

Main entry point for the volleyball action recognition and player tracking system.
This module orchestrates the entire video processing pipeline.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2

from src.analysis.video_processor import VideoProcessor
from src.detection.base_detector import resolve_device
from src.utils.video_upscale import ensure_1080, resolve_source_stem
from src.output_gen.csv_exporter import CSVExporter
from src.output_gen.json_exporter import JSONExporter
from src.output_gen.visualization import VisualizationGenerator
from src.utils.config import Config
from src.utils.logger import setup_logging


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Analyze beach volleyball videos for player actions"
    )
    parser.add_argument(
        "video_path",
        type=str,
        help="Path to the volleyball video file to analyze"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="Directory to save analysis results (default: ./output)"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file (optional)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    parser.add_argument(
        "--skip-visualization",
        action="store_true",
        help="Skip generating visualization graphs"
    )
    parser.add_argument(
        "--debug-live",
        action="store_true",
        help="Enable live debug mode with real-time visualization"
    )
    parser.add_argument(
        "--debug-speed",
        type=float,
        default=1.0,
        help="Debug playback speed multiplier (default: 1.0)"
    )
    parser.add_argument(
        "--court",
        type=str,
        help="Path to court calibration JSON (auto-detected from calibrations/<video>.json if omitted)"
    )
    parser.add_argument(
        "--ball-model",
        type=str,
        help="Path to fine-tuned ball model (auto-detected from models/volleyball_ball_best.pt if omitted)"
    )
    parser.add_argument(
        "--device",
        type=str,
        choices=["auto", "cpu", "cuda", "mps"],
        default=None,
        help="Compute device for YOLO detection. 'auto' (default) picks "
             "CUDA > MPS (Apple GPU) > CPU. Pass 'cpu' to force CPU (e.g. for parity checks)."
    )
    parser.add_argument(
        "--save-video",
        action="store_true",
        help="Save an annotated video (headless-friendly). Combine with --debug-live to also show it live."
    )
    parser.add_argument(
        "--allow-uncalibrated",
        action="store_true",
        help="Run without a usable court calibration (missing file, stem mismatch or "
             "frame_dimensions that do not fit the video). Court-derived features "
             "(team, near-net, serve-zone, spike zones) are DEGRADED -- use only for "
             "probing, never for reported numbers."
    )

    return parser.parse_args()


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


def validate_inputs(video_path: str) -> Path:
    """Validate input video file exists and is accessible.

    Args:
        video_path: Path to the video file

    Returns:
        Path: Validated video file path

    Raises:
        FileNotFoundError: If video file doesn't exist
        ValueError: If file is not a video format
    """
    video_file = Path(video_path)

    if not video_file.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    valid_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}
    if video_file.suffix.lower() not in valid_extensions:
        raise ValueError(f"Unsupported video format: {video_file.suffix}")

    return video_file


def main() -> int:
    """Main function to run the volleyball video analysis.

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    try:
        # Parse command line arguments
        args = parse_arguments()

        # Setup logging
        setup_logging(args.log_level)
        logger = logging.getLogger(__name__)

        logger.info("Starting Beach Volleyball Video Analysis")
        logger.info(f"Video file: {args.video_path}")
        logger.info(f"Output directory: {args.output_dir}")

        # Validate inputs
        video_file = validate_inputs(args.video_path)

        # Load configuration
        config = Config.load(args.config) if args.config else Config.default()

        # Sub-1080p sources are upscaled ONCE (cached next to the original)
        # before anything reads them: the pixel-space constants downstream
        # (ball width side signal, NEAR_NET_PX, TOUCH_RISE_PX, tracker gates)
        # were all measured at 1080p. 1080p+ sources pass through untouched.
        # NOTE: calibration/output naming keeps keying on the SOURCE stem.
        # A trailing _up<target> suffix (the cached upscale file, see
        # src/utils/video_upscale.py) is stripped so pointing a run directly
        # at the cache still auto-detects calibrations/<source_stem>.json.
        source_stem = resolve_source_stem(video_file)
        video_file = ensure_1080(
            video_file, target_height=config.get("upscale_to_height", 1080)
        )

        # Resolve compute device: explicit --device overrides the config value;
        # "auto" picks the best available backend (CUDA > MPS (Apple GPU) > CPU).
        requested_device = args.device or config.get("device", "auto")
        config["device"] = resolve_device(requested_device)
        logger.info(f"Compute device: {config['device']}")

        # Court calibration: explicit --court, else auto-detect calibrations/<stem>.json
        # (keyed on the SOURCE video stem, not the cached upscaled file's).
        court_path = args.court
        if not court_path:
            auto_court = Path("calibrations") / f"{source_stem}.json"
            if auto_court.exists():
                court_path = str(auto_court)
        if court_path:
            config["court_calibration_path"] = court_path

        # Calibration / view readiness: reported loudly, and a missing or
        # unusable calibration is a hard error unless --allow-uncalibrated
        # (Stage 0 / T1: "actions stopped" must be distinguishable from
        # "calibration never loaded").
        readiness = build_calibration_readiness(
            court_path, source_stem, video_file,
            origin="explicit" if args.court else "auto_stem",
        )
        logger.info("\n%s", format_readiness(readiness))
        validate_calibration_readiness(readiness, args.allow_uncalibrated)

        # Ball detector: explicit --ball-model, else auto-detect the fine-tuned model.
        # The COCO fallback (yolov8n) rarely finds a volleyball on real footage.
        ball_model = args.ball_model
        if not ball_model:
            auto_model = Path("models/volleyball_ball_best.pt")
            if auto_model.exists():
                ball_model = str(auto_model)
        if ball_model:
            config["ball_model_path"] = ball_model
            # The fine-tuned model needs a low confidence threshold; a high value
            # (e.g. a config file still carrying the old 0.7) misses the ball
            # entirely. Only override if left above the tuned range.
            if config.get("ball_confidence", 0.15) > 0.3:
                config["ball_confidence"] = 0.15
            logger.info(
                f"Using ball model: {ball_model} (ball_confidence={config.get('ball_confidence')})"
            )

        # Create output directory
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Live and/or save-annotated-video paths share the visual processor.
        if args.debug_live or args.save_video:
            from src.analysis.live_debug_processor import LiveDebugProcessor
            debug_processor = LiveDebugProcessor(config, debug_speed=args.debug_speed)
            save_path = str(output_dir / f"{source_stem}_annotated.mp4") if args.save_video else None
            if args.debug_live:
                logger.info("Starting live debug mode...")
            if save_path:
                logger.info(f"Saving annotated video to {save_path}")
            debug_processor.process_video_live(
                str(video_file), save_video=save_path, display=args.debug_live
            )
            return 0

        # Batch processing
        processor = VideoProcessor(config)
        logger.info("Starting video processing...")
        analysis_results = processor.process_video(str(video_file))
        # Readiness travels with the results so every exported artifact carries
        # the geometry it was produced under.
        analysis_results.setdefault("video_info", {})["calibration_readiness"] = readiness

        # Export results to CSV
        logger.info("Exporting results to CSV...")
        csv_exporter = CSVExporter()
        csv_path = output_dir / "results.csv"
        csv_exporter.export(analysis_results, csv_path)

        # Canonical machine-readable output (contract for the DB ingester).
        logger.info("Exporting canonical JSON...")
        json_exporter = JSONExporter()
        json_exporter.export(analysis_results, output_dir / "pipeline_output.json")

        # Generate visualizations (unless skipped)
        if not args.skip_visualization:
            logger.info("Generating visualization graphs...")
            viz_generator = VisualizationGenerator()
            viz_path = output_dir / "summary_graphs.png"
            viz_generator.generate_summary_graphs(analysis_results, viz_path)

        logger.info("Analysis completed successfully!")
        logger.info(f"Results saved to: {output_dir}")

        return 0

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Analysis failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
