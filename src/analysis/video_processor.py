"""
Video processor for volleyball video analysis.

This module orchestrates the entire video processing pipeline,
coordinating detection, tracking, and action recognition.
"""

from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np
import logging
from pathlib import Path
from tqdm import tqdm

from ..detection.ball_detector import BallDetector
from ..detection.player_detector import PlayerDetector
from ..tracking.ball_tracker import BallTracker
from ..tracking.player_tracker import PlayerTracker
from ..recognition.pose_estimator import PoseEstimator
from ..recognition.action_classifier import ActionClassifier
from .statistics import StatisticsAnalyzer


class VideoProcessor:
    """Main video processing pipeline for volleyball analysis.

    Coordinates all computer vision components to analyze volleyball videos
    and extract player actions and statistics.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the video processor.

        Args:
            config: Configuration dictionary with processing parameters
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self._initialize_components()

        # Processing state
        self.frame_count = 0
        self.total_frames = 0

    def _initialize_components(self) -> None:
        """Initialize all computer vision components."""
        try:
            # Detection components
            from ..detection.court_detector import CourtDetector

            self.court_detector = CourtDetector(
                config=self.config,
                debug_mode=self.config.get("debug_mode", False)
            )

            self.ball_detector = BallDetector(
                confidence_threshold=self.config.get("ball_confidence", 0.3),
                device=self.config.get("device", "cpu"),
                detection_method=self.config.get("detection_method", "template"),
                horizontal_margin_percent=self.config.get("ball_horizontal_margin_percent", 0.15)
            )

            self.player_detector = PlayerDetector(
                confidence_threshold=self.config.get("player_confidence", 0.5),
                device=self.config.get("device", "cpu"),
                max_players=self.config.get("max_players", 4)
            )

            # Connect court detector to player detector for court-based filtering
            self.player_detector.set_court_detector(self.court_detector)

            # Tracking components
            self.ball_tracker = BallTracker(
                max_missing_frames=self.config.get("ball_max_missing", 10),
                trajectory_smoothing=self.config.get("trajectory_smoothing", 5)
            )

            self.player_tracker = PlayerTracker(
                max_disappeared=self.config.get("player_max_disappeared", 30),
                max_distance=self.config.get("tracking_max_distance", 100.0)
            )

            # Recognition components
            self.pose_estimator = PoseEstimator(
                min_detection_confidence=self.config.get("pose_confidence", 0.5),
                model_complexity=self.config.get("pose_complexity", 1)
            )

            self.action_classifier = ActionClassifier(
                pose_estimator=self.pose_estimator,
                temporal_window=self.config.get("temporal_window", 10),
                confidence_threshold=self.config.get("action_confidence", 0.6)
            )

            # Analysis component
            self.statistics_analyzer = StatisticsAnalyzer()

            self.logger.info("All components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise

    def process_video(self, video_path: str) -> Dict[str, Any]:
        """Process a volleyball video and extract analysis results.

        Args:
            video_path: Path to the video file

        Returns:
            Analysis results dictionary
        """
        self.logger.info(f"Starting video processing: {video_path}")

        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        # Get video properties
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.logger.info(f"Video properties: {self.total_frames} frames, {fps} FPS, {width}x{height}")
        
        # Update ball detector with actual video FPS for accurate motion analysis
        if hasattr(self.ball_detector, 'wilson_detectors') and 'template' in self.ball_detector.wilson_detectors:
            template_detector = self.ball_detector.wilson_detectors['template']
            if template_detector.motion_tracker is not None:
                template_detector.motion_tracker.fps = fps
                # Recalculate gravity with correct FPS
                template_detector.motion_tracker.gravity_px_per_frame2 = template_detector.motion_tracker._calculate_gravity_pixels()
                self.logger.info(f"Updated motion tracker FPS to {fps:.2f}, gravity: {template_detector.motion_tracker.gravity_px_per_frame2:.4f} px/frame²")

        # Initialize results storage
        results = {
            "video_info": {
                "path": video_path,
                "total_frames": self.total_frames,
                "fps": fps,
                "width": width,
                "height": height
            },
            "frame_results": [],
            "player_actions": {},
            "ball_trajectory": [],
            "statistics": {}
        }

        # Process frames
        self.frame_count = 0

        with tqdm(total=self.total_frames, desc="Processing frames") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                try:
                    # Process single frame
                    frame_result = self._process_frame(frame)
                    results["frame_results"].append(frame_result)

                    # Update progress
                    self.frame_count += 1
                    pbar.update(1)

                    # Optional: Save debug frames
                    if self.config.get("save_debug_frames", False):
                        self._save_debug_frame(frame, frame_result)

                except Exception as e:
                    self.logger.error(f"Error processing frame {self.frame_count}: {e}")
                    continue

        cap.release()

        # Post-process results
        results = self._post_process_results(results)

        self.logger.info("Video processing completed")
        return results

    def _process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """Process a single video frame.

        Args:
            frame: Input frame as numpy array

        Returns:
            Frame processing results
        """
        frame_result = {
            "frame_index": self.frame_count,
            "ball_detections": [],
            "player_detections": [],
            "tracked_players": [],
            "tracked_ball": None,
            "actions": [],
            "processing_time": 0.0
        }

        import time
        start_time = time.time()

        # 1. Object Detection
        ball_detections = self.ball_detector.detect(frame)
        player_detections = self.player_detector.detect(frame)

        frame_result["ball_detections"] = ball_detections
        frame_result["player_detections"] = player_detections

        # 2. Object Tracking
        tracked_players = self.player_tracker.update(player_detections)
        tracked_ball = self.ball_tracker.update(ball_detections)

        frame_result["tracked_players"] = tracked_players
        frame_result["tracked_ball"] = tracked_ball

        # 3. Action Recognition
        if tracked_players:
            actions = self.action_classifier.classify_actions(
                frame, tracked_players, tracked_ball
            )
            frame_result["actions"] = actions

        # Record processing time
        frame_result["processing_time"] = time.time() - start_time

        return frame_result

    def _post_process_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process complete video results.

        Args:
            results: Raw processing results

        Returns:
            Post-processed results with statistics
        """
        self.logger.info("Post-processing video results...")

        # Extract ball trajectory
        ball_trajectory = []
        for frame_result in results["frame_results"]:
            tracked_ball = frame_result.get("tracked_ball")
            if tracked_ball:
                ball_trajectory.append(tracked_ball.get("center", [None, None]))
            else:
                ball_trajectory.append([None, None])

        results["ball_trajectory"] = ball_trajectory

        # Aggregate player actions
        player_actions = {}
        for frame_result in results["frame_results"]:
            for action in frame_result.get("actions", []):
                track_id = action.get("track_id")
                if track_id is not None:
                    if track_id not in player_actions:
                        player_actions[track_id] = []
                    player_actions[track_id].append({
                        "frame_index": frame_result["frame_index"],
                        "action": action.get("action"),
                        "confidence": action.get("confidence"),
                        "bbox": action.get("bbox")
                    })

        results["player_actions"] = player_actions

        # Generate statistics
        results["statistics"] = self.statistics_analyzer.analyze_video_results(results)

        # Calculate processing statistics
        processing_times = [fr.get("processing_time", 0) for fr in results["frame_results"]]
        results["processing_stats"] = {
            "total_processing_time": sum(processing_times),
            "average_frame_time": np.mean(processing_times),
            "fps_achieved": 1.0 / np.mean(processing_times) if np.mean(processing_times) > 0 else 0
        }

        return results

    def _save_debug_frame(self, frame: np.ndarray, frame_result: Dict[str, Any]) -> None:
        """Save debug frame with annotations.

        Args:
            frame: Original frame
            frame_result: Frame processing results
        """
        debug_frame = frame.copy()

        # Draw player detections
        for player in frame_result.get("tracked_players", []):
            bbox = player.get("bbox", [])
            if len(bbox) == 4:
                x1, y1, x2, y2 = map(int, bbox)
                track_id = player.get("track_id", -1)

                # Draw bounding box
                cv2.rectangle(debug_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Draw track ID
                cv2.putText(
                    debug_frame,
                    f"Player {track_id}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

        # Draw ball detection
        tracked_ball = frame_result.get("tracked_ball")
        if tracked_ball:
            center = tracked_ball.get("center", [0, 0])
            if center[0] is not None and center[1] is not None:
                cv2.circle(debug_frame, tuple(map(int, center)), 10, (0, 0, 255), -1)

        # Draw actions
        for action in frame_result.get("actions", []):
            bbox = action.get("bbox", [])
            action_type = action.get("action", "unknown")
            confidence = action.get("confidence", 0.0)

            if len(bbox) == 4:
                x1, y1, x2, y2 = map(int, bbox)
                label = f"{action_type}: {confidence:.2f}"

                cv2.putText(
                    debug_frame,
                    label,
                    (x1, y2 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 0),
                    2
                )

        # Save debug frame
        debug_dir = Path(self.config.get("debug_output_dir", "./debug"))
        debug_dir.mkdir(exist_ok=True)

        debug_path = debug_dir / f"frame_{self.frame_count:06d}.jpg"
        cv2.imwrite(str(debug_path), debug_frame)

    def get_processing_progress(self) -> float:
        """Get current processing progress.

        Returns:
            Progress as percentage (0.0 to 1.0)
        """
        if self.total_frames == 0:
            return 0.0
        return self.frame_count / self.total_frames
