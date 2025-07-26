"""
Live debug processor for volleyball video analysis.

This module provides real-time video debugging capabilities with visual overlays
showing detected actions, player tracking, and ball trajectory.
"""

from typing import Dict, Any, Optional, List, Tuple
import cv2
import numpy as np
import logging
import time
from collections import deque

from ..detection.ball_detector import BallDetector
from ..detection.player_detector import PlayerDetector
from ..tracking.ball_tracker import BallTracker
from ..tracking.player_tracker import PlayerTracker
from ..recognition.pose_estimator import PoseEstimator
from ..recognition.action_classifier import ActionClassifier


class LiveDebugProcessor:
    """Real-time video processor with visual debugging capabilities.

    Displays video frames with overlays showing:
    - Player bounding boxes and tracking IDs
    - Ball detection and trajectory
    - Real-time action recognition
    - Performance metrics
    """

    def __init__(self, config: Dict[str, Any], debug_speed: float = 1.0):
        """Initialize the live debug processor.

        Args:
            config: Configuration dictionary
            debug_speed: Playback speed multiplier (1.0 = normal speed)
        """
        self.config = config
        self.debug_speed = debug_speed
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self._initialize_components()

        # Visual settings
        self.colors = {
            'player': (0, 255, 0),      # Green for players
            'ball': (0, 0, 255),        # Red for ball
            'trajectory': (255, 0, 255), # Magenta for ball trajectory
            'action_dig': (255, 255, 0), # Cyan for digs
            'action_set': (0, 255, 255), # Yellow for sets
            'action_spike': (255, 0, 0), # Blue for spikes
            'action_block': (0, 165, 255), # Orange for blocks
            'action_ace': (128, 0, 128),  # Purple for aces
            'action_serve': (255, 20, 147) # Deep pink for serves
        }

        # Ball trajectory history
        self.ball_trajectory = deque(maxlen=50)  # Store last 50 positions

        # Performance tracking
        self.frame_times = deque(maxlen=30)

    def _initialize_components(self) -> None:
        """Initialize all computer vision components."""
        try:
            # Detection components
            self.ball_detector = BallDetector(
                confidence_threshold=self.config.get("ball_confidence", 0.3),
                device=self.config.get("device", "cpu")
            )

            self.player_detector = PlayerDetector(
                confidence_threshold=self.config.get("player_confidence", 0.5),
                device=self.config.get("device", "cpu"),
                max_players=self.config.get("max_players", 4)
            )

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

            self.logger.info("Live debug components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize debug components: {e}")
            raise

    def process_video_live(self, video_path: str) -> None:
        """Process video with real-time debugging visualization.

        Args:
            video_path: Path to the video file
        """
        self.logger.info(f"Starting live debug processing: {video_path}")

        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_delay = (1.0 / fps) / self.debug_speed if fps > 0 else 0.033
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.logger.info(f"Video: {total_frames} frames, {fps} FPS, {width}x{height}")
        self.logger.info("Press 'q' to quit, SPACE to pause/resume, 'r' to restart")

        frame_count = 0
        paused = False

        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    self.logger.info("End of video reached")
                    break

                start_time = time.time()

                # Process frame
                debug_frame = self._process_debug_frame(frame, frame_count)

                # Add performance info
                debug_frame = self._add_performance_overlay(debug_frame, frame_count, total_frames)

                frame_count += 1

                # Track processing time
                processing_time = time.time() - start_time
                self.frame_times.append(processing_time)

            # Display frame
            cv2.imshow('Volleyball Analysis Debug', debug_frame)

            # Handle keyboard input
            key = cv2.waitKey(int(frame_delay * 1000) if not paused else 0) & 0xFF

            if key == ord('q'):
                break
            elif key == ord(' '):  # Space to pause/resume
                paused = not paused
                self.logger.info(f"{'Paused' if paused else 'Resumed'}")
            elif key == ord('r'):  # Restart video
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_count = 0
                self.ball_trajectory.clear()
                self._reset_trackers()
                self.logger.info("Video restarted")

        cap.release()
        cv2.destroyAllWindows()
        self.logger.info("Live debug session ended")

    def _process_debug_frame(self, frame: np.ndarray, frame_index: int) -> np.ndarray:
        """Process a single frame for debug visualization.

        Args:
            frame: Input frame
            frame_index: Frame index

        Returns:
            Debug frame with overlays
        """
        debug_frame = frame.copy()

        try:
            # 1. Object Detection
            ball_detections = self.ball_detector.detect(frame)
            player_detections = self.player_detector.detect(frame)

            # 2. Object Tracking
            tracked_players = self.player_tracker.update(player_detections)
            tracked_ball = self.ball_tracker.update(ball_detections)

            # 3. Action Recognition
            actions = []
            if tracked_players:
                actions = self.action_classifier.classify_actions(
                    frame, tracked_players, tracked_ball
                )

            # 4. Draw visualizations
            debug_frame = self._draw_players(debug_frame, tracked_players)
            debug_frame = self._draw_ball_and_trajectory(debug_frame, tracked_ball)
            debug_frame = self._draw_actions(debug_frame, actions)
            debug_frame = self._draw_frame_info(debug_frame, frame_index, len(tracked_players))

        except Exception as e:
            self.logger.error(f"Error processing debug frame {frame_index}: {e}")
            # Draw error message on frame
            cv2.putText(debug_frame, f"Processing Error: {str(e)[:50]}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        return debug_frame

    def _draw_players(self, frame: np.ndarray, tracked_players: List[Dict[str, Any]]) -> np.ndarray:
        """Draw player bounding boxes and tracking information.

        Args:
            frame: Input frame
            tracked_players: List of tracked player data

        Returns:
            Frame with player overlays
        """
        for player in tracked_players:
            bbox = player.get("bbox", [])
            if len(bbox) != 4:
                continue

            x1, y1, x2, y2 = map(int, bbox)
            track_id = player.get("track_id", -1)
            confidence = player.get("confidence", 0.0)

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), self.colors['player'], 2)

            # Draw track ID and confidence
            label = f"Player {track_id} ({confidence:.2f})"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]

            # Background for text
            cv2.rectangle(frame, (x1, y1 - label_size[1] - 10),
                         (x1 + label_size[0], y1), self.colors['player'], -1)

            # Text
            cv2.putText(frame, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

            # Draw center point
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            cv2.circle(frame, (center_x, center_y), 3, self.colors['player'], -1)

        return frame

    def _draw_ball_and_trajectory(self, frame: np.ndarray, tracked_ball: Optional[Dict[str, Any]]) -> np.ndarray:
        """Draw ball detection and trajectory.

        Args:
            frame: Input frame
            tracked_ball: Ball tracking data

        Returns:
            Frame with ball overlays
        """
        if tracked_ball:
            center = tracked_ball.get("center", [0, 0])
            confidence = tracked_ball.get("confidence", 0.0)
            velocity = tracked_ball.get("velocity", [0, 0])
            ball_state = tracked_ball.get("ball_state", "unknown")

            if center[0] is not None and center[1] is not None:
                x, y = map(int, center)

                # Add to trajectory
                self.ball_trajectory.append((x, y))

                # Draw ball circle
                radius = 8 if not tracked_ball.get("is_predicted", False) else 5
                color = self.colors['ball'] if not tracked_ball.get("is_predicted", False) else (128, 128, 128)
                cv2.circle(frame, (x, y), radius, color, -1)

                # Draw ball info
                ball_info = f"Ball {confidence:.2f} | {ball_state}"
                if velocity and velocity != [0, 0]:
                    speed = np.sqrt(velocity[0]**2 + velocity[1]**2)
                    ball_info += f" | Speed: {speed:.1f}"

                cv2.putText(frame, ball_info, (x + 15, y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                # Draw velocity vector
                if velocity and velocity != [0, 0]:
                    end_x = int(x + velocity[0] * 3)
                    end_y = int(y + velocity[1] * 3)
                    cv2.arrowedLine(frame, (x, y), (end_x, end_y), color, 2)

        # Draw trajectory trail
        if len(self.ball_trajectory) > 1:
            points = list(self.ball_trajectory)
            for i in range(1, len(points)):
                # Fade older points
                alpha = i / len(points)
                thickness = max(1, int(alpha * 3))
                cv2.line(frame, points[i-1], points[i], self.colors['trajectory'], thickness)

        return frame

    def _draw_actions(self, frame: np.ndarray, actions: List[Dict[str, Any]]) -> np.ndarray:
        """Draw recognized actions.

        Args:
            frame: Input frame
            actions: List of action recognition results

        Returns:
            Frame with action overlays
        """
        for action in actions:
            bbox = action.get("bbox", [])
            if len(bbox) != 4:
                continue

            x1, y1, x2, y2 = map(int, bbox)
            action_type = action.get("action", "unknown")
            confidence = action.get("confidence", 0.0)
            track_id = action.get("track_id", -1)

            # Get action color
            action_color = self.colors.get(f"action_{action_type}", (255, 255, 255))

            # Draw action indicator (colored border)
            cv2.rectangle(frame, (x1-3, y1-3), (x2+3, y2+3), action_color, 3)

            # Draw action label
            action_label = f"{action_type.upper()} ({confidence:.2f})"
            label_size = cv2.getTextSize(action_label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]

            # Position label below player box
            label_y = y2 + 25

            # Background for action text
            cv2.rectangle(frame, (x1, label_y - label_size[1] - 5),
                         (x1 + label_size[0], label_y + 5), action_color, -1)

            # Action text
            cv2.putText(frame, action_label, (x1, label_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

        return frame

    def _draw_frame_info(self, frame: np.ndarray, frame_index: int, player_count: int) -> np.ndarray:
        """Draw frame information overlay.

        Args:
            frame: Input frame
            frame_index: Current frame index
            player_count: Number of detected players

        Returns:
            Frame with info overlay
        """
        h, w = frame.shape[:2]

        # Frame info
        info_text = f"Frame: {frame_index} | Players: {player_count}"
        cv2.putText(frame, info_text, (10, h - 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Ball trajectory info
        ball_info = f"Ball trajectory points: {len(self.ball_trajectory)}"
        cv2.putText(frame, ball_info, (10, h - 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Controls info
        controls = "Controls: 'q'=quit, SPACE=pause, 'r'=restart"
        cv2.putText(frame, controls, (10, h - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        return frame

    def _add_performance_overlay(self, frame: np.ndarray, frame_count: int, total_frames: int) -> np.ndarray:
        """Add performance metrics overlay.

        Args:
            frame: Input frame
            frame_count: Current frame count
            total_frames: Total frames in video

        Returns:
            Frame with performance overlay
        """
        h, w = frame.shape[:2]

        # Progress bar
        progress = frame_count / total_frames if total_frames > 0 else 0
        bar_width = w - 40
        bar_height = 10
        bar_x = 20
        bar_y = 20

        # Background
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height),
                     (50, 50, 50), -1)

        # Progress fill
        fill_width = int(bar_width * progress)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_width, bar_y + bar_height),
                     (0, 255, 0), -1)

        # Progress text
        progress_text = f"{progress*100:.1f}% ({frame_count}/{total_frames})"
        cv2.putText(frame, progress_text, (bar_x, bar_y - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # FPS info
        if len(self.frame_times) > 0:
            avg_time = np.mean(list(self.frame_times))
            fps_achieved = 1.0 / avg_time if avg_time > 0 else 0
            fps_text = f"Processing: {fps_achieved:.1f} FPS | Speed: {self.debug_speed}x"
            cv2.putText(frame, fps_text, (w - 300, 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return frame

    def _reset_trackers(self) -> None:
        """Reset all tracking state."""
        # Reset player tracker
        self.player_tracker.tracks = {}
        self.player_tracker.disappeared = {}
        self.player_tracker.next_id = 0

        # Reset ball tracker
        self.ball_tracker._reset_tracker()

        # Clear trajectory
        self.ball_trajectory.clear()

        self.logger.debug("Trackers reset")
