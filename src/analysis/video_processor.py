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

from .statistics import StatisticsAnalyzer
from .frame_processor import FrameProcessor


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

        # Initialize shared frame processor (batch mode - use standard ball tracker)
        self.frame_processor = FrameProcessor(config, use_enhanced_ball_tracker=False)
        
        # Analysis component
        self.statistics_analyzer = StatisticsAnalyzer()

        # Processing state
        self.frame_count = 0
        self.total_frames = 0

    # Removed _initialize_components - now handled by FrameProcessor

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
        
        # Setup frame processor with video properties
        self.frame_processor.setup_video_fps(fps)
        self.frame_processor.setup_video_dimensions(width, height)

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
                    # Process single frame using shared processor
                    frame_result = self.frame_processor.process_frame(frame, self.frame_count)
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

        # Flush the final contact held back by the action classifier's
        # one-contact look-ahead, attaching it to the last frame's results.
        flushed = self.frame_processor.flush_actions()
        if flushed and results["frame_results"]:
            results["frame_results"][-1].setdefault("actions", []).extend(flushed)

        # Post-process results
        results = self._post_process_results(results)

        self.logger.info("Video processing completed")
        return results

    # Removed _process_frame - now handled by FrameProcessor

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
                        # Prefer the action's true contact frame (it is finalised
                        # a little after the frame it was emitted on).
                        "frame_index": action.get("frame_number", frame_result["frame_index"]),
                        "action": action.get("action"),
                        "gesture": action.get("gesture"),
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
