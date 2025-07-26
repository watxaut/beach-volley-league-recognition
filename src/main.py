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
from src.output_gen.csv_exporter import CSVExporter
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

        # Create output directory
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize video processor
        processor = VideoProcessor(config)

        # Check if debug live mode is enabled
        if args.debug_live:
            logger.info("Starting live debug mode...")
            from src.analysis.live_debug_processor import LiveDebugProcessor
            debug_processor = LiveDebugProcessor(config, debug_speed=args.debug_speed)
            debug_processor.process_video_live(str(video_file))
            return 0

        # Process the video
        logger.info("Starting video processing...")
        analysis_results = processor.process_video(str(video_file))

        # Export results to CSV
        logger.info("Exporting results to CSV...")
        csv_exporter = CSVExporter()
        csv_path = output_dir / "results.csv"
        csv_exporter.export(analysis_results, csv_path)

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
