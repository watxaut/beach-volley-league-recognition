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

from .frame_processor import FrameProcessor


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

        # Initialize shared frame processor (live mode - use enhanced ball tracker)
        self.frame_processor = FrameProcessor(config, use_enhanced_ball_tracker=True)

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
            'action_serve': (255, 20, 147), # Deep pink for serves
            'action_overpass': (0, 100, 255), # Orange-red for overpass
            'game_state_off': (128, 128, 128),  # Gray for game off
            'game_state_on': (0, 255, 0),       # Green for game on
            'game_state_serve': (255, 165, 0),  # Orange for serve prep
            'game_state_scored': (255, 0, 255), # Magenta for point scored
            'game_state_timeout': (255, 255, 0) # Yellow for timeout
        }

        # Ball trajectory history with enhanced tracking
        self.ball_trajectory = deque(maxlen=50)  # Store last 50 positions
        self.ball_raw_detections = deque(maxlen=20)  # Store raw detections for visualization
        self.ball_detection_stats = {
            'total_detections': 0,
            'filtered_detections': 0,
            'tracked_detections': 0,
            'method_counts': {}  # Track which methods are detecting balls
        }
        
        # Detection method tracking
        self.recent_detection_methods = deque(maxlen=10)  # Store recent detection methods used

        # Performance tracking
        self.frame_times = deque(maxlen=30)

        # Recent actions per track_id for on-screen persistence. Actions are
        # emitted on a single frame (and the last one only on flush), so we keep
        # each visible for a window of frames near its player.
        self.recent_actions: Dict[int, Dict[str, Any]] = {}
        self.action_persist_frames = 45
        
        # Quick access to shared components for visualization
        self.ball_detector = self.frame_processor.get_ball_detector()
        self.court_detector = self.frame_processor.get_court_detector()
        self.game_state_manager = self.frame_processor.get_game_state_manager()

    # Removed _initialize_components - now handled by FrameProcessor

    def process_video_live(
        self,
        video_path: str,
        save_video: Optional[str] = None,
        display: bool = True,
    ) -> None:
        """Process a video with debug overlays, shown live and/or written to file.

        Args:
            video_path: Path to the video file.
            save_video: If set, write the annotated frames to this path. Enables
                headless use (no display needed).
            display: If True, show the live window (needs a display) with
                q/space/r controls. Set False for headless save-only runs.
        """
        self.logger.info(f"Starting debug processing: {video_path}")

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

        # Setup frame processor with video properties
        self.frame_processor.setup_video_fps(fps)
        self.frame_processor.setup_video_dimensions(width, height)

        writer = None
        if save_video:
            writer = cv2.VideoWriter(
                save_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
            )

        if display:
            self.logger.info("Press 'q' to quit, SPACE to pause/resume, 'r' to restart")

        frame_count = 0
        paused = False
        debug_frame = None
        last_frame = None

        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    self.logger.info("End of video reached")
                    break
                last_frame = frame

                start_time = time.time()

                # Process frame using shared processor
                frame_result = self.frame_processor.process_frame(frame, frame_count, enable_court_redetection=True)
                self._ingest_actions(frame_result.get("actions", []), frame_count)

                # Create debug visualization
                debug_frame = self._create_debug_visualization(frame, frame_result, frame_count)

                # Add performance info
                debug_frame = self._add_performance_overlay(debug_frame, frame_count, total_frames)

                frame_count += 1

                # Track processing time
                processing_time = time.time() - start_time
                self.frame_times.append(processing_time)

                if writer is not None:
                    writer.write(debug_frame)

            if display and debug_frame is not None:
                cv2.imshow('Volleyball Analysis Debug', debug_frame)
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
                    self.recent_actions.clear()
                    self.frame_processor.reset_trackers()
                    self.logger.info("Video restarted")

        # Flush the final contact the classifier held back for its look-ahead.
        flushed = self.frame_processor.flush_actions()
        if flushed and last_frame is not None:
            self._ingest_actions(flushed, frame_count)
            final = self._create_debug_visualization(last_frame, {"actions": flushed}, frame_count)
            if writer is not None:
                writer.write(final)
            if display:
                cv2.imshow('Volleyball Analysis Debug', final)
                cv2.waitKey(500)

        cap.release()
        if writer is not None:
            writer.release()
            self.logger.info(f"Annotated video written: {save_video}")
        if display:
            cv2.destroyAllWindows()
        self.logger.info("Debug session ended")

    def _ingest_actions(self, actions: List[Dict[str, Any]], frame_index: int) -> None:
        """Record emitted actions per track_id for on-screen persistence."""
        for action in actions:
            tid = action.get("track_id")
            if tid is None:
                continue
            self.recent_actions[tid] = {
                "frame": frame_index,
                "action": action.get("action", "?"),
                "confidence": action.get("confidence", 0.0),
                "touch_number": action.get("touch_number"),
                "gesture": action.get("gesture"),
            }
            self.logger.info(
                "Action: frame~%s player %s -> %s (%.2f)",
                action.get("frame_number", frame_index), tid,
                action.get("action"), action.get("confidence", 0.0),
            )

    def _create_debug_visualization(self, frame: np.ndarray, frame_result: Dict[str, Any], frame_index: int) -> np.ndarray:
        """Create debug visualization from frame processing results.

        Args:
            frame: Input frame
            frame_result: Results from frame processor
            frame_index: Frame index

        Returns:
            Debug frame with overlays
        """
        debug_frame = frame.copy()
        self._current_frame = frame_index

        try:
            # Extract results
            ball_detections = frame_result.get("ball_detections", [])
            tracked_players = frame_result.get("tracked_players", [])
            tracked_ball = frame_result.get("tracked_ball")
            actions = frame_result.get("actions", [])
            game_state = frame_result.get("game_state", {})
            
            # Update ball detection statistics and track methods used
            self.ball_detection_stats['total_detections'] += len(ball_detections)
            self.ball_raw_detections.extend(ball_detections)
            
            # Track detection methods used
            for detection in ball_detections:
                method = detection.get('method', 'unknown')
                self.ball_detection_stats['method_counts'][method] = \
                    self.ball_detection_stats['method_counts'].get(method, 0) + 1
                self.recent_detection_methods.append(method)

            # Update filtered ball statistics (estimate from total vs tracked)
            if tracked_ball:
                self.ball_detection_stats['tracked_detections'] += 1

            # Draw visualizations
            debug_frame = self._draw_court_overlay(debug_frame)  # Draw court first
            debug_frame = self._draw_players(debug_frame, tracked_players)
            debug_frame = self._draw_ball_and_trajectory(debug_frame, tracked_ball, ball_detections)
            debug_frame = self._draw_actions(debug_frame, actions)
            
            # Convert game state dict to object-like structure for visualization
            if game_state:
                # Create a simple namespace object from the dict
                class GameStateInfo:
                    def __init__(self, data):
                        for key, value in data.items():
                            setattr(self, key, value)
                
                game_state_obj = GameStateInfo(game_state)
                debug_frame = self._draw_game_state(debug_frame, game_state_obj)
            
            player_detections = frame_result.get("player_detections", [])
            debug_frame = self._draw_frame_info(debug_frame, frame_index, len(tracked_players), len(player_detections), len(player_detections))

        except Exception as e:
            self.logger.error(f"Error creating debug visualization {frame_index}: {e}")
            # Draw error message on frame
            cv2.putText(debug_frame, f"Visualization Error: {str(e)[:50]}",
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

            # Overlay a recent action for this player (persisted for a window of
            # frames, since actions are emitted on a single frame).
            self._draw_player_action(frame, track_id, x1, y1, x2, y2)

        return frame

    def _draw_player_action(self, frame: np.ndarray, track_id: int,
                            x1: int, y1: int, x2: int, y2: int) -> None:
        """Draw the most recent action for a player, if still within its window."""
        rec = self.recent_actions.get(track_id)
        if not rec:
            return
        age = self._current_frame - rec["frame"] if hasattr(self, "_current_frame") else 0
        if age < 0 or age > self.action_persist_frames:
            return
        action = rec["action"]
        color = self.colors.get(f"action_{action}", (255, 255, 255))
        # Highlight border + label above the box.
        cv2.rectangle(frame, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), color, 3)
        touch = rec.get("touch_number")
        touch_str = f" t{touch}" if touch else ""
        label = f"{action.upper()}{touch_str} ({rec['confidence']:.2f})"
        size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        ly = y2 + 28
        cv2.rectangle(frame, (x1, ly - size[1] - 6), (x1 + size[0] + 6, ly + 4), color, -1)
        cv2.putText(frame, label, (x1 + 3, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    def _draw_ball_and_trajectory(self, frame: np.ndarray, tracked_ball: Optional[Dict[str, Any]], current_detections: List[Dict[str, Any]] = None) -> np.ndarray:
        """Draw enhanced ball detection and trajectory with comprehensive visual feedback.

        Args:
            frame: Input frame
            tracked_ball: Ball tracking data
            current_detections: Current frame ball detections with method info

        Returns:
            Frame with enhanced ball overlays
        """
        # First, draw all raw ball detections with method information
        frame = self._draw_raw_ball_detections(frame, current_detections)

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

                # Enhanced ball information panel with method info
                self._draw_ball_info_panel(frame, x, y, confidence, velocity, ball_state, is_predicted, tracked_ball)

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

    def _draw_raw_ball_detections(self, frame: np.ndarray, current_detections: List[Dict[str, Any]] = None) -> np.ndarray:
        """Draw all raw ball detections with method information."""
        # Define colors for different detection methods
        method_colors = {
            'template': (255, 165, 0),      # Orange for template matching
            'features': (0, 255, 255),      # Cyan for feature-based
            'hybrid': (255, 0, 255),        # Magenta for hybrid CNN
            'fusion': (128, 255, 128),      # Light green for fusion
            'yolo': (255, 255, 0),          # Yellow for YOLO
            'wilson_tracker': (255, 192, 203), # Pink for Wilson tracker
            'unknown': (128, 128, 128)      # Gray for unknown
        }
        
        # Draw current frame detections with method labels
        if current_detections:
            for i, detection in enumerate(current_detections):
                bbox = detection.get("bbox", [])
                confidence = detection.get("confidence", 0.0)
                method = detection.get("method", "unknown")
                
                if len(bbox) == 4:
                    x1, y1, x2, y2 = map(int, bbox)
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2
                    
                    # Get method color
                    method_color = method_colors.get(method, method_colors['unknown'])
                    
                    # Draw detection circle with method-specific color
                    cv2.circle(frame, (center_x, center_y), 5, method_color, 2)
                    
                    # Draw method label with template info for template detections
                    if method.startswith('template') and 'template_name' in detection:
                        template_name = detection.get('template_name', 'unknown')
                        scale_used = detection.get('scale_used', 0)
                        method_label = f"{template_name[:6]}@{scale_used:.1f}"
                    else:
                        method_label = f"{method[:8]}" # Truncate long method names
                    
                    cv2.putText(frame, method_label, (center_x + 8, center_y - 8),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.4, method_color, 1)
                    
                    # Draw confidence
                    cv2.putText(frame, f"{confidence:.2f}", (center_x + 8, center_y + 8),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.3, method_color, 1)
                    
                    # Draw detection number
                    cv2.putText(frame, str(i+1), (center_x - 10, center_y - 10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.4, method_color, 1)
        
        # Also show recent historical detections (smaller)
        for detection in list(self.ball_raw_detections)[-3:]:  # Show last 3 historical detections
            bbox = detection.get("bbox", [])
            confidence = detection.get("confidence", 0.0)
            method = detection.get("method", "unknown")

            if len(bbox) == 4:
                x1, y1, x2, y2 = map(int, bbox)
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                
                method_color = method_colors.get(method, method_colors['unknown'])
                
                # Draw smaller circle for historical detections
                cv2.circle(frame, (center_x, center_y), 2, method_color, 1)

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
                             velocity: List[float], ball_state: str, is_predicted: bool, ball_data: Dict[str, Any]) -> None:
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

        # Ball info text with enhanced template information
        status = "PREDICTED" if is_predicted else "DETECTED"
        method = ball_data.get('method', 'unknown')
        
        lines = [
            f"Ball {status}",
            f"Method: {method}",
            f"Confidence: {confidence:.3f}",
            f"State: {ball_state}",
        ]
        
        # Add template-specific information if available
        if 'template_name' in ball_data:
            template_name = ball_data.get('template_name', 'unknown')
            scale_used = ball_data.get('scale_used', 0)
            template_idx = ball_data.get('template_index', 0)
            lines.append(f"Template: {template_name}")
            lines.append(f"Scale: {scale_used:.2f}")
            lines.append(f"Index: {template_idx}")

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
        """Draw ball detection statistics panel with method breakdown."""
        h, w = frame.shape[:2]

        # Statistics panel
        stats_x = w - 300
        stats_y = 60

        # Main statistics
        stats_text = [
            f"Ball Detections:",
            f"  Total: {self.ball_detection_stats['total_detections']}",
            f"  Filtered: {self.ball_detection_stats['filtered_detections']}",
            f"  Tracked: {self.ball_detection_stats['tracked_detections']}",
            f"  Trajectory: {len(self.ball_trajectory)} pts",
            "",
            f"Detection Methods Used:"
        ]

        # Add method counts with template breakdown
        for method, count in self.ball_detection_stats['method_counts'].items():
            if method.startswith('template_'):
                # Extract template index and show template name if available
                try:
                    template_idx = int(method.split('_')[1])
                    if hasattr(self.ball_detector, 'wilson_detectors') and 'template' in self.ball_detector.wilson_detectors:
                        template_detector = self.ball_detector.wilson_detectors['template']
                        if template_idx < len(template_detector.template_names):
                            template_name = template_detector.template_names[template_idx]
                            stats_text.append(f"  {template_name}: {count}")
                        else:
                            stats_text.append(f"  {method}: {count}")
                    else:
                        stats_text.append(f"  {method}: {count}")
                except (ValueError, IndexError):
                    stats_text.append(f"  {method}: {count}")
            else:
                stats_text.append(f"  {method}: {count}")

        # Add recent methods used
        if len(self.recent_detection_methods) > 0:
            recent_methods = list(self.recent_detection_methods)[-3:]  # Last 3 methods
            recent_str = " → ".join(recent_methods)
            stats_text.append("")
            stats_text.append(f"Recent: {recent_str}")

        # Current detection method from ball detector
        current_method = getattr(self.ball_detector, 'detection_method', 'unknown')
        stats_text.append(f"Config: {current_method}")

        # Background for stats
        for i, text in enumerate(stats_text):
            if text.strip():  # Skip empty lines
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
                cv2.rectangle(frame, (stats_x - 5, stats_y + i * 15 - 10),
                             (stats_x + text_size[0] + 5, stats_y + i * 15 + 3), (0, 0, 0), -1)

                # Color coding for headers vs data
                if text.endswith(":") and not text.startswith("  "):
                    color = (255, 255, 255)  # White for headers
                elif text.startswith("  "):
                    color = (200, 200, 200)  # Light gray for indented items
                else:
                    color = (150, 255, 150)  # Light green for recent/config info

                cv2.putText(frame, text, (stats_x, stats_y + i * 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # Method color legend
        legend_y = stats_y + len(stats_text) * 15 + 20
        legend_items = [
            ("● Template", (255, 165, 0)),     # Orange
            ("● Features", (0, 255, 255)),     # Cyan  
            ("● Hybrid", (255, 0, 255)),       # Magenta
            ("● Fusion", (128, 255, 128)),     # Light green
            ("● YOLO", (255, 255, 0)),         # Yellow
            ("● Wilson", (255, 192, 203)),     # Pink
        ]

        for i, (text, color) in enumerate(legend_items):
            cv2.putText(frame, text, (stats_x, legend_y + i * 12),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

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

    def _draw_game_state(self, frame: np.ndarray, game_state_info: Dict[str, Any]) -> np.ndarray:
        """Draw game state information overlay.

        Args:
            frame: Input frame
            game_state_info: Game state analysis results

        Returns:
            Frame with game state overlay
        """
        if not game_state_info:
            return frame

        h, w = frame.shape[:2]
        
        # Game state panel position (top right)
        panel_x = w - 350
        panel_y = 60
        panel_width = 340
        panel_height = 200

        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (panel_x, panel_y),
                     (panel_x + panel_width, panel_y + panel_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

        # Game state header
        current_state = game_state_info.current_state if hasattr(game_state_info, 'current_state') else 'unknown'
        state_confidence = game_state_info.state_confidence if hasattr(game_state_info, 'state_confidence') else 0.0
        state_color = self.colors.get(f'game_state_{current_state.value if hasattr(current_state, "value") else str(current_state)}', (255, 255, 255))
        
        cv2.putText(frame, "GAME STATE", (panel_x + 10, panel_y + 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Current state with confidence
        state_text = f"State: {current_state.value.upper() if hasattr(current_state, 'value') else str(current_state).upper()}"
        cv2.putText(frame, state_text, (panel_x + 10, panel_y + 45),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, state_color, 2)
        
        confidence_text = f"Confidence: {state_confidence:.3f}"
        cv2.putText(frame, confidence_text, (panel_x + 10, panel_y + 65),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, state_color, 1)

        # Score information
        team_a_score = game_state_info.team_a_score if hasattr(game_state_info, 'team_a_score') else 0
        team_b_score = game_state_info.team_b_score if hasattr(game_state_info, 'team_b_score') else 0
        serving_team = game_state_info.serving_team if hasattr(game_state_info, 'serving_team') else 'unknown'
        
        score_text = f"Score: {team_a_score} - {team_b_score}"
        cv2.putText(frame, score_text, (panel_x + 10, panel_y + 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        serve_text = f"Serving: Team {serving_team}"
        cv2.putText(frame, serve_text, (panel_x + 10, panel_y + 110),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

        # Analysis module confidences
        analysis_results = game_state_info.analysis_results if hasattr(game_state_info, 'analysis_results') else {}
        y_offset = 135
        
        cv2.putText(frame, "Analysis Modules:", (panel_x + 10, panel_y + y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        y_offset += 15
        
        # Action sequence analysis
        action_analysis = analysis_results.get('action_sequence', {})
        serve_conf = action_analysis.get('serve_confidence', 0.0)
        rally_conf = action_analysis.get('rally_confidence', 0.0)
        
        cv2.putText(frame, f"Action: S:{serve_conf:.2f} R:{rally_conf:.2f}", 
                   (panel_x + 15, panel_y + y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)
        y_offset += 12
        
        # Trajectory analysis
        trajectory_analysis = analysis_results.get('trajectory', {})
        traj_serve_conf = trajectory_analysis.get('serve_confidence', 0.0)
        traj_attack_conf = trajectory_analysis.get('attack_confidence', 0.0)
        
        cv2.putText(frame, f"Trajectory: S:{traj_serve_conf:.2f} A:{traj_attack_conf:.2f}", 
                   (panel_x + 15, panel_y + y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)
        y_offset += 12
        
        # Temporal analysis
        temporal_analysis = analysis_results.get('temporal', {})
        activity_level = temporal_analysis.get('activity_level', 0.0)
        activity_resuming = temporal_analysis.get('activity_resuming_confidence', 0.0)
        
        cv2.putText(frame, f"Temporal: A:{activity_level:.2f} R:{activity_resuming:.2f}", 
                   (panel_x + 15, panel_y + y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)
        
        # State transition indicator
        transition_info = game_state_info.transition_info if hasattr(game_state_info, 'transition_info') else None
        if transition_info:
            y_offset += 20
            from_state = transition_info.get('from_state', 'unknown') if isinstance(transition_info, dict) else 'unknown'
            to_state = transition_info.get('to_state', 'unknown') if isinstance(transition_info, dict) else 'unknown'
            trigger = transition_info.get('trigger', 'unknown') if isinstance(transition_info, dict) else 'unknown'
            
            transition_text = f"Transition: {from_state} → {to_state}"
            cv2.putText(frame, transition_text, (panel_x + 10, panel_y + y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
            
            trigger_text = f"Trigger: {trigger}"
            cv2.putText(frame, trigger_text, (panel_x + 10, panel_y + y_offset + 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)

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

    # Removed _reset_trackers - now handled by FrameProcessor
