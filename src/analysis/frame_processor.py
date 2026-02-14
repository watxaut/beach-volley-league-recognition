"""
Shared frame processing logic for volleyball video analysis.

This module provides a unified frame processing pipeline that ensures
consistent results between live debug and batch video processing.
"""

from typing import List, Dict, Any, Optional
import cv2
import numpy as np
import logging
import time

from ..detection.ball_detector import BallDetector
from ..detection.player_detector import PlayerDetector
from ..tracking.ball_tracker import BallTracker
from ..tracking.enhanced_ball_tracker import EnhancedBallTracker
from ..tracking.player_tracker import PlayerTracker
from ..recognition.pose_estimator import PoseEstimator
from ..recognition.action_classifier import ActionClassifier
from .game_state_manager import GameStateManager


class FrameProcessor:
    """Unified frame processing pipeline used by both video processor and live debug.
    
    This ensures that both video_processor.py and live_debug_processor.py
    use exactly the same processing logic behind the scenes.
    """
    
    def __init__(self, config: Dict[str, Any], use_enhanced_ball_tracker: bool = False):
        """Initialize the frame processor.
        
        Args:
            config: Configuration dictionary
            use_enhanced_ball_tracker: Whether to use enhanced ball tracker (for live debug)
        """
        self.config = config
        self.use_enhanced_ball_tracker = use_enhanced_ball_tracker
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self._initialize_components()
        
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
                wilson_ball_dir=self.config.get("wilson_ball_dir", "resources/wilson_ball"),
                horizontal_margin_percent=self.config.get("ball_horizontal_margin_percent", 0.15),
                enable_motion_filtering=False
            )

            self.player_detector = PlayerDetector(
                confidence_threshold=self.config.get("player_confidence", 0.5),
                device=self.config.get("device", "cpu"),
                max_players=self.config.get("max_players", 4)
            )

            # Connect court detector to player detector for court-based filtering
            self.player_detector.set_court_detector(self.court_detector)

            # Tracking components - choose based on use case
            if self.use_enhanced_ball_tracker:
                # Enhanced tracker for live debug (better continuity)
                self.ball_tracker = EnhancedBallTracker(
                    max_missing_frames=self.config.get("ball_max_missing", 45),
                    template_update_interval=5,
                    optical_flow_quality=0.01,
                    kalman_process_noise=0.1,
                    kalman_measurement_noise=1.0
                )
            else:
                # Standard tracker for batch processing (consistent with existing logic)
                self.ball_tracker = BallTracker(
                    max_missing_frames=self.config.get("ball_max_missing", 10),
                    trajectory_smoothing=self.config.get("trajectory_smoothing", 5),
                    velocity_threshold=self.config.get("velocity_threshold", 200.0),
                    low_confidence_threshold=self.config.get("low_confidence_threshold", 0.15),
                    trajectory_confidence_boost=self.config.get("trajectory_confidence_boost", 0.3),
                    max_trajectory_gap=self.config.get("max_trajectory_gap", 150.0),
                    velocity_consistency_weight=self.config.get("velocity_consistency_weight", 0.4),
                    acceleration_consistency_weight=self.config.get("acceleration_consistency_weight", 0.2),
                    trajectory_prediction_frames=self.config.get("trajectory_prediction_frames", 5),
                    fast_ball_velocity_threshold=self.config.get("fast_ball_velocity_threshold", 50.0)
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
                confidence_threshold=self.config.get("action_confidence", 0.6),
                enhanced_validation_config=self.config.get("enhanced_validation", {})
            )

            # Game state detection
            self.game_state_manager = GameStateManager(self.config)

            self.logger.info("Frame processor components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize frame processor components: {e}")
            raise
    
    def setup_video_fps(self, fps: float) -> None:
        """Setup components with video FPS information.
        
        Args:
            fps: Video frames per second
        """
        # Update ball detector with actual video FPS for accurate motion analysis
        if hasattr(self.ball_detector, 'wilson_detectors') and 'template' in self.ball_detector.wilson_detectors:
            template_detector = self.ball_detector.wilson_detectors['template']
            if template_detector.motion_tracker is not None:
                template_detector.motion_tracker.fps = fps
                # Recalculate gravity with correct FPS
                template_detector.motion_tracker.gravity_px_per_frame2 = template_detector.motion_tracker._calculate_gravity_pixels()
                self.logger.info(f"Updated motion tracker FPS to {fps:.2f}, gravity: {template_detector.motion_tracker.gravity_px_per_frame2:.4f} px/frame²")
        
        # Update game state manager with video info (width/height will be set separately)
        if hasattr(self.game_state_manager, 'set_video_info'):
            self.game_state_manager.fps = fps
    
    def setup_video_dimensions(self, width: int, height: int) -> None:
        """Setup components with video dimensions.
        
        Args:
            width: Video width
            height: Video height
        """
        if hasattr(self.game_state_manager, 'set_video_info'):
            self.game_state_manager.set_video_info(getattr(self.game_state_manager, 'fps', 30.0), width, height)
    
    def process_frame(self, frame: np.ndarray, frame_index: int, 
                     enable_court_redetection: bool = False) -> Dict[str, Any]:
        """Process a single video frame using the unified pipeline.
        
        Args:
            frame: Input frame as numpy array
            frame_index: Current frame index
            enable_court_redetection: Whether to re-detect court (for live debug every N frames)
            
        Returns:
            Frame processing results
        """
        frame_result = {
            "frame_index": frame_index,
            "ball_detections": [],
            "player_detections": [],
            "tracked_players": [],
            "tracked_ball": None,
            "actions": [],
            "processing_time": 0.0,
            "game_state": {}
        }

        start_time = time.time()

        try:
            # 0. Court Detection (conditional re-detection for live debug)
            if frame_index == 0 or (enable_court_redetection and frame_index % 30 == 0):
                self.court_detector.detect_court(frame)

            # 1. Object Detection
            ball_detections = self.ball_detector.detect(frame)
            player_detections = self.player_detector.detect(frame)

            frame_result["ball_detections"] = ball_detections
            frame_result["player_detections"] = player_detections

            # 2. Filter detections by court area
            filtered_player_detections = self.court_detector.filter_detections_by_court(player_detections)
            filtered_ball_detections = self.court_detector.filter_detections_by_court(ball_detections)

            # 3. Object Tracking
            # For players: use filtered detections (only in-court players)
            tracked_players = self.player_tracker.update(filtered_player_detections)
            
            # For ball: use ALL detections (ball can be outside court bounds)
            # Enhanced tracker needs frame for optical flow
            if self.use_enhanced_ball_tracker:
                tracked_ball = self.ball_tracker.update(ball_detections, frame)
            else:
                tracked_ball = self.ball_tracker.update(ball_detections)

            frame_result["tracked_players"] = tracked_players
            frame_result["tracked_ball"] = tracked_ball

            # 4. Initial Game State Analysis (for context)  
            initial_game_state = self.game_state_manager.analyze_frame(frame_result, frame_index)

            # 5. Action Recognition (with game state context)
            actions = []
            if tracked_players:
                # Get court info for enhanced validation
                court_info = None
                if hasattr(self.court_detector, 'get_court_statistics'):
                    court_stats = self.court_detector.get_court_statistics()
                    if court_stats.get("court_detected", False):
                        court_info = {"boundaries": court_stats.get("boundaries", {})}
                        # Set court boundaries for game state manager
                        try:
                            self.game_state_manager.set_court_boundaries(court_stats)
                        except AttributeError:
                            pass  # Court boundaries not supported

                # Action classification with game state context
                actions = self.action_classifier.classify_actions(
                    frame, tracked_players, tracked_ball,
                    frame_number=frame_index,
                    court_info=court_info,
                    game_state_info=initial_game_state.to_dict()  # Add initial game state context
                )

                # Filter out UNKNOWN actions - only keep actions with ball contact
                actions = [
                    action for action in actions 
                    if action.get("action", "unknown") != "unknown" and action.get("confidence", 0.0) > 0.1
                ]

            # Update frame result with detected actions before final game state analysis
            frame_result["actions"] = actions

            # 6. Final Game State Analysis (after context-aware actions are detected)
            game_state_info = self.game_state_manager.analyze_frame(frame_result, frame_index)
            frame_result["game_state"] = game_state_info.to_dict()

        except Exception as e:
            self.logger.error(f"Error processing frame {frame_index}: {e}")
            # Keep basic frame result structure even on error

        # Record processing time
        frame_result["processing_time"] = time.time() - start_time

        return frame_result
    
    def reset_trackers(self) -> None:
        """Reset all tracking state."""
        # Reset player tracker
        self.player_tracker.tracks = {}
        self.player_tracker.disappeared = {}
        self.player_tracker.next_id = 0

        # Reset ball tracker
        if hasattr(self.ball_tracker, '_reset_tracker'):
            self.ball_tracker._reset_tracker()
        elif hasattr(self.ball_tracker, 'reset'):
            self.ball_tracker.reset()

        # Reset game state manager
        if hasattr(self, 'game_state_manager'):
            self.game_state_manager = GameStateManager(self.config)

        self.logger.debug("Trackers and game state reset")
    
    def get_court_detector(self):
        """Get the court detector for visualization."""
        return self.court_detector
    
    def get_ball_detector(self):
        """Get the ball detector for statistics."""
        return self.ball_detector
    
    def get_game_state_manager(self):
        """Get the game state manager for debugging."""
        return self.game_state_manager