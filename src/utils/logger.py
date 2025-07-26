"""
Logging utilities for volleyball video analysis.

This module provides centralized logging configuration and utilities
for debugging and monitoring the video analysis pipeline.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional
import sys


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """Setup logging configuration for the volleyball analysis system.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file
        log_format: Custom log format string
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep
    """
    # Define default log format
    if log_format is None:
        log_format = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - %(message)s"
        )

    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(log_format)

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Log the logging setup
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured - Level: {level}, File: {log_file}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class VideoProcessingLogger:
    """Specialized logger for video processing with progress tracking."""

    def __init__(self, name: str):
        """Initialize the video processing logger.

        Args:
            name: Logger name
        """
        self.logger = logging.getLogger(name)
        self.total_frames = 0
        self.processed_frames = 0

    def set_total_frames(self, total: int) -> None:
        """Set total number of frames for progress tracking.

        Args:
            total: Total number of frames
        """
        self.total_frames = total
        self.processed_frames = 0
        self.logger.info(f"Starting video processing: {total} frames")

    def log_frame_processed(self, frame_index: int, processing_time: float = 0.0) -> None:
        """Log progress for a processed frame.

        Args:
            frame_index: Index of processed frame
            processing_time: Time taken to process frame
        """
        self.processed_frames += 1

        if self.total_frames > 0:
            progress = (self.processed_frames / self.total_frames) * 100

            # Log every 10% or every 100 frames, whichever is less frequent
            log_interval = max(1, min(100, self.total_frames // 10))

            if self.processed_frames % log_interval == 0:
                self.logger.info(
                    f"Progress: {progress:.1f}% ({self.processed_frames}/{self.total_frames}) "
                    f"- Frame {frame_index} processed in {processing_time:.3f}s"
                )

    def log_detection_results(
        self,
        frame_index: int,
        ball_count: int,
        player_count: int
    ) -> None:
        """Log detection results for a frame.

        Args:
            frame_index: Frame index
            ball_count: Number of balls detected
            player_count: Number of players detected
        """
        self.logger.debug(
            f"Frame {frame_index}: {ball_count} balls, {player_count} players detected"
        )

    def log_action_recognition(
        self,
        frame_index: int,
        actions: list
    ) -> None:
        """Log action recognition results.

        Args:
            frame_index: Frame index
            actions: List of recognized actions
        """
        if actions:
            action_summary = ", ".join([
                f"{action.get('action', 'unknown')}({action.get('confidence', 0):.2f})"
                for action in actions
            ])
            self.logger.debug(f"Frame {frame_index}: Actions - {action_summary}")

    def log_completion(self, total_time: float, avg_fps: float) -> None:
        """Log completion statistics.

        Args:
            total_time: Total processing time
            avg_fps: Average processing FPS
        """
        self.logger.info(
            f"Video processing completed: {self.processed_frames} frames in "
            f"{total_time:.2f}s (avg {avg_fps:.2f} FPS)"
        )


def configure_third_party_loggers() -> None:
    """Configure logging levels for third-party libraries to reduce noise."""
    # Reduce logging from common computer vision libraries
    logging.getLogger("ultralytics").setLevel(logging.WARNING)
    logging.getLogger("torch").setLevel(logging.WARNING)
    logging.getLogger("torchvision").setLevel(logging.WARNING)
    logging.getLogger("mediapipe").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)

    # Keep OpenCV relatively quiet
    logging.getLogger("cv2").setLevel(logging.ERROR)


def log_system_info() -> None:
    """Log system information for debugging purposes."""
    import platform
    import sys
    import torch
    import cv2

    logger = logging.getLogger(__name__)

    logger.info("=== System Information ===")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"Processor: {platform.processor()}")

    # GPU information
    if torch.cuda.is_available():
        logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA version: {torch.version.cuda}")
    else:
        logger.info("CUDA not available")

    # OpenCV information
    logger.info(f"OpenCV version: {cv2.__version__}")

    # Memory information (if available)
    try:
        import psutil
        memory = psutil.virtual_memory()
        logger.info(f"Total memory: {memory.total // (1024**3)} GB")
        logger.info(f"Available memory: {memory.available // (1024**3)} GB")
    except ImportError:
        logger.info("Memory information not available (psutil not installed)")

    logger.info("=== End System Information ===")


class PerformanceLogger:
    """Logger for tracking performance metrics."""

    def __init__(self, name: str):
        """Initialize performance logger.

        Args:
            name: Logger name
        """
        self.logger = logging.getLogger(f"{name}.performance")
        self.metrics = {}

    def start_timer(self, operation: str) -> None:
        """Start timing an operation.

        Args:
            operation: Name of the operation
        """
        import time
        self.metrics[operation] = {"start": time.time()}

    def end_timer(self, operation: str) -> float:
        """End timing an operation and log the duration.

        Args:
            operation: Name of the operation

        Returns:
            Duration in seconds
        """
        import time
        if operation not in self.metrics:
            self.logger.warning(f"Timer for '{operation}' was not started")
            return 0.0

        duration = time.time() - self.metrics[operation]["start"]
        self.metrics[operation]["duration"] = duration

        self.logger.debug(f"{operation}: {duration:.3f}s")
        return duration

    def log_memory_usage(self, operation: str) -> None:
        """Log current memory usage.

        Args:
            operation: Name of the operation
        """
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            self.logger.debug(f"{operation} - Memory usage: {memory_mb:.1f} MB")
        except ImportError:
            pass  # psutil not available

    def get_summary(self) -> dict:
        """Get performance summary.

        Returns:
            Dictionary with performance metrics
        """
        summary = {}
        for operation, data in self.metrics.items():
            if "duration" in data:
                summary[operation] = data["duration"]
        return summary
