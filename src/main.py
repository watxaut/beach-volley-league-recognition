"""
Beach Volleyball Video Analysis System

Main entry point for the volleyball action recognition and player tracking system.
This module orchestrates the entire video processing pipeline.
"""

import argparse
import logging
import sys
from pathlib import Path

from src.analysis.video_processor import VideoProcessor
from src.detection.base_detector import resolve_device
# Re-exported: the readiness check lives in a shared module so the probe
# scripts in scripts/ apply the exact same gate (tests import these names
# from src.main, so they stay available here).
from src.detection.calibration_readiness import (
    ASPECT_RATIO_TOLERANCE,
    DEFAULT_CALIBRATION_FRAME_DIMENSIONS,
    DEGRADED_OUTPUTS_WITHOUT_CALIBRATION,
    build_calibration_readiness,
    format_readiness,
    read_calibration_frame_dimensions,
    read_video_dimensions,
    validate_calibration_readiness,
)
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

    parser.add_argument(
        "--diag-dump",
        type=str,
        help="Diagnostic capture (task T4): write a per-frame JSONL dump of raw ball "
             "detections + suppression flags, ball-tracker state/reason, player tracks, "
             "contact candidates (incl. rejected ones + the gate that refused them), "
             "actor/team and the emitted label. Off by default and inert when off; "
             "consumed by scripts/waterfall.py."
    )

    parser.add_argument(
        "--serve-events",
        action="store_true",
        help="Emit serve-evidence events (far flight + serve runway + serve candidate). "
             "Pure observers over detections the pipeline already produces; off by "
             "default and inert when off (byte-identical output either way). Needs a "
             "court calibration -- the runway region IS the 8 calibration clicks."
    )

    return parser.parse_args()


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


def _close_diagnostics(processor) -> None:
    """Flush the T4 diag dump when the processor owns a FrameProcessor."""
    frame_processor = getattr(processor, "frame_processor", None)
    closer = getattr(frame_processor, "close_diagnostics", None)
    if closer is not None:
        closer()


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
        if args.diag_dump:
            config["diag_dump"] = args.diag_dump
        if args.serve_events:
            config["serve_events_enabled"] = True

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
            _close_diagnostics(debug_processor)
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
        _close_diagnostics(processor)

        return 0

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Analysis failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
