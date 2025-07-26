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
            'ball_filtered': (100, 100, 255),  # Light red for filtered balls
            'ball_predicted': (128, 128, 128), # Gray for predicted balls
            'trajectory': (255, 0, 255), # Magenta for ball trajectory
            'trajectory_predicted': (200, 100, 200), # Light magenta for predicted trajectory
            'ball_detection_raw': (0, 150, 255), # Orange for raw detections
            'velocity_vector': (255, 255, 0), # Cyan for velocity vectors
            'action_dig': (255, 255, 0), # Cyan for digs
            'action_set': (0, 255, 255), # Yellow for sets
            'action_spike': (255, 0, 0), # Blue for spikes
            'action_block': (0, 165, 255), # Orange for blocks
            'action_ace': (128, 0, 128),  # Purple for aces
            'action_serve': (255, 20, 147) # Deep pink for serves
        }

        # Ball trajectory history with enhanced tracking
        self.ball_trajectory = deque(maxlen=50)  # Store last 50 positions
        self.ball_raw_detections = deque(maxlen=20)  # Store raw detections for visualization
        self.ball_detection_stats = {
            'total_detections': 0,
            'filtered_detections': 0,
            'tracked_detections': 0
        }

        # Performance tracking
        self.frame_times = deque(maxlen=30)

    def _initialize_components(self) -> None:
        """Initialize all computer vision components."""
        try:
            # Detection components
            from ..detection.court_detector import CourtDetector

            self.court_detector = CourtDetector(
                config=self.config,
                debug_mode=self.config.get("debug_mode", True)
            )

            self.ball_detector = BallDetector(
                confidence_threshold=self.config.get("ball_confidence", 0.3),
                device=self.config.get("device", "cpu")
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
            # 0. Court Detection (detect once, then use for filtering)
            if frame_index == 0 or frame_index % 30 == 0:  # Re-detect every 30 frames
                self.court_detector.detect_court(frame)

            # 1. Object Detection
            ball_detections = self.ball_detector.detect(frame)
            player_detections = self.player_detector.detect(frame)

            # Update ball detection statistics
            self.ball_detection_stats['total_detections'] += len(ball_detections)
            self.ball_raw_detections.extend(ball_detections)

            # 2. Filter detections by court area
            filtered_player_detections = self.court_detector.filter_detections_by_court(player_detections)
            filtered_ball_detections = self.court_detector.filter_detections_by_court(ball_detections)

            # Update filtered ball statistics
            filtered_out_balls = len(ball_detections) - len(filtered_ball_detections)
            self.ball_detection_stats['filtered_detections'] += filtered_out_balls

            # Log filtering results
            if len(player_detections) != len(filtered_player_detections):
                filtered_count = len(player_detections) - len(filtered_player_detections)
                self.logger.debug(f"Frame {frame_index}: Filtered {filtered_count} out-of-court players")

            if filtered_out_balls > 0:
                self.logger.debug(f"Frame {frame_index}: Filtered {filtered_out_balls} out-of-court balls")

            # 3. Object Tracking
            # For players: use filtered detections (only in-court players)
            tracked_players = self.player_tracker.update(filtered_player_detections)
            # For ball: use ALL detections (ball can be outside court bounds)
            tracked_ball = self.ball_tracker.update(ball_detections)

            # 4. Action Recognition
            actions = []
            if tracked_players:
                actions = self.action_classifier.classify_actions(
                    frame, tracked_players, tracked_ball
                )

            # 5. Draw visualizations
            debug_frame = self._draw_court_overlay(debug_frame)  # Draw court first
            debug_frame = self._draw_players(debug_frame, tracked_players)
            debug_frame = self._draw_ball_and_trajectory(debug_frame, tracked_ball)
            debug_frame = self._draw_actions(debug_frame, actions)
            debug_frame = self._draw_frame_info(debug_frame, frame_index, len(tracked_players), len(filtered_player_detections), len(player_detections))

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
        """Draw enhanced ball detection and trajectory with comprehensive visual feedback.

        Args:
            frame: Input frame
            tracked_ball: Ball tracking data

        Returns:
            Frame with enhanced ball overlays
        """
        # First, draw all raw ball detections (before filtering)
        frame = self._draw_raw_ball_detections(frame)

        # Then draw the main tracked ball
        if tracked_ball:
            center = tracked_ball.get("center", [0, 0])
            confidence = tracked_ball.get("confidence", 0.0)
            velocity = tracked_ball.get("velocity", [0, 0])
            ball_state = tracked_ball.get("ball_state", "unknown")
            is_predicted = tracked_ball.get("is_predicted", False)

            if center[0] is not None and center[1] is not None:
                x, y = map(int, center)

                # Add to trajectory with metadata
                self.ball_trajectory.append((x, y, confidence, is_predicted))
                self.ball_detection_stats['tracked_detections'] += 1

                # Enhanced ball circle with multiple visual indicators
                if is_predicted:
                    # Predicted ball - dashed circle
                    self._draw_dashed_circle(frame, (x, y), 8, self.colors['ball_predicted'], 2)
                    color = self.colors['ball_predicted']
                    radius = 6
                else:
                    # Actual detection - solid circle with confidence-based sizing
                    radius = max(6, int(8 + confidence * 4))  # Size based on confidence
                    color = self.colors['ball']
                    cv2.circle(frame, (x, y), radius, color, -1)

                    # Add confidence ring
                    ring_radius = radius + 3
                    ring_color = tuple(int(c * confidence) for c in color)
                    cv2.circle(frame, (x, y), ring_radius, ring_color, 2)

                # Enhanced ball information panel
                self._draw_ball_info_panel(frame, x, y, confidence, velocity, ball_state, is_predicted)

                # Draw velocity vector with enhanced styling
                if velocity and velocity != [0, 0]:
                    speed = np.sqrt(velocity[0]**2 + velocity[1]**2)
                    if speed > 1:  # Only draw if significant movement
                        vector_length = min(50, speed * 2)  # Scale vector length
                        end_x = int(x + (velocity[0] / speed) * vector_length)
                        end_y = int(y + (velocity[1] / speed) * vector_length)

                        # Draw velocity vector with gradient effect
                        cv2.arrowedLine(frame, (x, y), (end_x, end_y),
                                      self.colors['velocity_vector'], 3, tipLength=0.3)

                        # Add speed indicator
                        cv2.putText(frame, f"{speed:.1f}px/f", (end_x + 5, end_y),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.colors['velocity_vector'], 1)

        # Draw enhanced trajectory trail
        self._draw_enhanced_trajectory(frame)

        # Draw ball detection statistics
        self._draw_ball_statistics(frame)

        return frame

    def _draw_raw_ball_detections(self, frame: np.ndarray) -> np.ndarray:
        """Draw all raw ball detections before filtering."""
        # Show recent raw detections that were filtered out
        for detection in list(self.ball_raw_detections)[-5:]:  # Show last 5 raw detections
            bbox = detection.get("bbox", [])
            confidence = detection.get("confidence", 0.0)

            if len(bbox) == 4:
                x1, y1, x2, y2 = map(int, bbox)
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2

                # Draw small orange circle for raw detections
                cv2.circle(frame, (center_x, center_y), 3, self.colors['ball_detection_raw'], 1)

                # Add small confidence label
                cv2.putText(frame, f"{confidence:.2f}", (center_x + 5, center_y - 5),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.colors['ball_detection_raw'], 1)

        return frame

    def _draw_dashed_circle(self, frame: np.ndarray, center: Tuple[int, int],
                           radius: int, color: Tuple[int, int, int], thickness: int) -> None:
        """Draw a dashed circle for predicted ball positions."""
        x, y = center
        for angle in range(0, 360, 10):  # Draw dashes every 10 degrees
            start_angle = np.radians(angle)
            end_angle = np.radians(angle + 5)  # 5-degree dashes

            start_x = int(x + radius * np.cos(start_angle))
            start_y = int(y + radius * np.sin(start_angle))
            end_x = int(x + radius * np.cos(end_angle))
            end_y = int(y + radius * np.sin(end_angle))

            cv2.line(frame, (start_x, start_y), (end_x, end_y), color, thickness)

    def _draw_ball_info_panel(self, frame: np.ndarray, x: int, y: int, confidence: float,
                             velocity: List[float], ball_state: str, is_predicted: bool) -> None:
        """Draw detailed ball information panel."""
        # Create info panel background
        panel_x = x + 20
        panel_y = y - 40
        panel_width = 200
        panel_height = 80

        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (panel_x, panel_y),
                     (panel_x + panel_width, panel_y + panel_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Ball info text
        status = "PREDICTED" if is_predicted else "DETECTED"
        lines = [
            f"Ball {status}",
            f"Confidence: {confidence:.3f}",
            f"State: {ball_state}",
        ]

        if velocity and velocity != [0, 0]:
            speed = np.sqrt(velocity[0]**2 + velocity[1]**2)
            angle = np.degrees(np.arctan2(velocity[1], velocity[0]))
            lines.append(f"Speed: {speed:.1f} px/f")
            lines.append(f"Angle: {angle:.1f}°")

        # Draw text lines
        for i, line in enumerate(lines):
            text_y = panel_y + 15 + (i * 12)
            color = self.colors['ball_predicted'] if is_predicted else self.colors['ball']
            cv2.putText(frame, line, (panel_x + 5, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    def _draw_enhanced_trajectory(self, frame: np.ndarray) -> None:
        """Draw enhanced ball trajectory with fade effect and prediction indicators."""
        if len(self.ball_trajectory) > 1:
            points = list(self.ball_trajectory)

            for i in range(1, len(points)):
                if len(points[i]) >= 4:  # Has metadata
                    _, _, confidence, is_predicted = points[i]
                    prev_point = points[i-1][:2]
                    curr_point = points[i][:2]

                    # Calculate alpha based on position in trajectory and confidence
                    alpha = (i / len(points)) * confidence
                    thickness = max(1, int(alpha * 4))

                    # Choose color based on prediction status
                    if is_predicted:
                        color = self.colors['trajectory_predicted']
                    else:
                        color = self.colors['trajectory']

                    # Fade color
                    faded_color = tuple(int(c * alpha) for c in color)
                    cv2.line(frame, prev_point, curr_point, faded_color, thickness)
                else:
                    # Fallback for old format
                    prev_point = points[i-1][:2]
                    curr_point = points[i][:2]
                    alpha = i / len(points)
                    thickness = max(1, int(alpha * 3))
                    cv2.line(frame, prev_point, curr_point, self.colors['trajectory'], thickness)

    def _draw_ball_statistics(self, frame: np.ndarray) -> None:
        """Draw ball detection statistics panel."""
        h, w = frame.shape[:2]

        # Statistics panel
        stats_x = w - 250
        stats_y = 60

        stats_text = [
            f"Ball Detections:",
            f"  Total: {self.ball_detection_stats['total_detections']}",
            f"  Filtered: {self.ball_detection_stats['filtered_detections']}",
            f"  Tracked: {self.ball_detection_stats['tracked_detections']}",
            f"  Trajectory: {len(self.ball_trajectory)} pts"
        ]

        # Background for stats
        for i, text in enumerate(stats_text):
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            cv2.rectangle(frame, (stats_x - 5, stats_y + i * 18 - 12),
                         (stats_x + text_size[0] + 5, stats_y + i * 18 + 5), (0, 0, 0), -1)

            color = (255, 255, 255) if i == 0 else (200, 200, 200)
            cv2.putText(frame, text, (stats_x, stats_y + i * 18),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        # Legend for ball visualization
        legend_y = stats_y + len(stats_text) * 18 + 20
        legend_items = [
            ("● Detected", self.colors['ball']),
            ("○ Predicted", self.colors['ball_predicted']),
            ("● Raw Detection", self.colors['ball_detection_raw']),
            ("→ Velocity", self.colors['velocity_vector'])
        ]

        for i, (text, color) in enumerate(legend_items):
            cv2.putText(frame, text, (stats_x, legend_y + i * 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

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

    def _draw_frame_info(self, frame: np.ndarray, frame_index: int, tracked_count: int, filtered_count: int, total_detections: int) -> np.ndarray:
        """Draw frame information overlay.

        Args:
            frame: Input frame
            frame_index: Current frame index
            tracked_count: Number of tracked players
            filtered_count: Number of players after court filtering
            total_detections: Total player detections before filtering

        Returns:
            Frame with info overlay
        """
        h, w = frame.shape[:2]

        # Frame info with filtering statistics
        info_text = f"Frame: {frame_index} | Tracked: {tracked_count} | In-Court: {filtered_count}/{total_detections}"
        cv2.putText(frame, info_text, (10, h - 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Ball trajectory info
        ball_info = f"Ball trajectory points: {len(self.ball_trajectory)}"
        cv2.putText(frame, ball_info, (10, h - 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Court detection status
        court_stats = self.court_detector.get_court_statistics()
        court_status = "Court Detected" if court_stats.get("court_detected", False) else "No Court"
        cv2.putText(frame, f"Court: {court_status}", (10, h - 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0) if court_stats.get("court_detected", False) else (0, 0, 255), 2)

        # Controls info
        controls = "Controls: 'q'=quit, SPACE=pause, 'r'=restart"
        cv2.putText(frame, controls, (10, h - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        return frame

    def _draw_court_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Draw court boundary overlay for debugging.

        Args:
            frame: Input frame

        Returns:
            Frame with court boundary overlay
        """
        return self.court_detector.draw_court_overlay(frame)

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
