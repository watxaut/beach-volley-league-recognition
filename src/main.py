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
            logger.info(f"Using court calibration: {court_path}")
        else:
            logger.warning(
                "No court calibration found (calibrations/%s.json). Serve/net/team "
                "features will be limited. Pass --court to supply one.", source_stem
            )

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
