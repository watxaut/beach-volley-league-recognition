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
from ..detection.court_calibration import CourtCalibration
from ..tracking.ball_tracker import BallTracker
from ..tracking.player_tracker import PlayerTracker
from ..recognition.pose_estimator import PoseEstimator
from ..recognition.action_classifier import ActionClassifier
from .game_state_manager import GameStateManager
from .spike_analyzer import SpikeAnalyzer


class FrameProcessor:
    """Unified frame processing pipeline.

    Uses CourtCalibration (one-time) instead of per-frame court detection.
    All new components: YOLO ball detector, 4-player locked tracker,
    conservative ball tracker, event-driven action classifier.
    """

    def __init__(self, config: Dict[str, Any], use_enhanced_ball_tracker: bool = False):
        """Initialize the frame processor.

        Args:
            config: Configuration dictionary.
            use_enhanced_ball_tracker: Deprecated, ignored.
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Court calibration (loaded from JSON or interactive)
        self.court_calibration: Optional[CourtCalibration] = None
        calibration_path = config.get("court_calibration_path")
        if calibration_path:
            self.court_calibration = CourtCalibration(calibration_path)

        self._initialize_components()

    def _initialize_components(self) -> None:
        """Initialize all computer vision components.

        The inline ``self.config.get(key, fallback)`` fallbacks mirror
        ``Config.DEFAULT_CONFIG`` and are locked by tests/test_config_drift.py
        (the 2026-08-17 f539 block/spike fork was exactly this class of drift).
        """
        try:
            # If no calibration loaded, create empty one (will work without spatial features)
            if self.court_calibration is None:
                self.court_calibration = CourtCalibration()

            # For backward compat: expose court_detector attribute (same interface)
            self.court_detector = self.court_calibration

            # Play-area margin (how far beyond the court polygon established tracks
            # may roam). Set once here from config; the mask builds lazily on use.
            if self.court_calibration.is_calibrated:
                self.court_calibration.set_play_area_margin(
                    self.config.get("player_play_area_margin_px", 100)
                )

            # Ball detection (YOLO-based)
            self.ball_detector = BallDetector(
                model_path=self.config.get("ball_model_path"),
                confidence_threshold=self.config.get("ball_confidence", 0.15),
                device=self.config.get("device", "auto"),
            )

            # Player detection (YOLO-based). The detector cap is a generous
            # safety limit (max_detections), NOT the team size -- capping it to
            # the roster would drop real in-court players before tracking.
            self.player_detector = PlayerDetector(
                confidence_threshold=self.config.get("player_confidence", 0.5),
                device=self.config.get("device", "auto"),
                max_players=self.config.get("max_detections", 20),
                imgsz=self.config.get("player_imgsz", 1280),
            )

            # Connect court calibration to player detector for filtering
            self.player_detector.set_court_detector(self.court_calibration)

            # Ball tracker (conservative)
            self.ball_tracker = BallTracker(
                max_missing_frames=self.config.get("ball_max_missing", 10),
                trajectory_smoothing=self.config.get("trajectory_smoothing", 5),
                velocity_threshold=self.config.get("velocity_threshold", 200.0),
                low_confidence_threshold=self.config.get("low_confidence_threshold", 0.4),
                max_trajectory_gap=self.config.get("max_trajectory_gap", 60.0),
                lock_min_speed=self.config.get("ball_lock_min_speed", 8.0),
                lock_motion_window=self.config.get("ball_lock_motion_window", 5),
                lock_max_jump=self.config.get("ball_lock_max_jump", 90.0),
                lock_max_pair_gap=self.config.get("ball_lock_max_pair_gap", 2),
                selection_conf_window=self.config.get("ball_selection_conf_window", 10.0),
                locked_low_conf_floor=self.config.get("ball_locked_low_conf_floor", 0.15),
                boot_low_conf_floor=self.config.get("ball_boot_low_conf_floor", 0.15),
            )
            # Set court bounds for out-of-bounds rejection
            if self.court_calibration.is_calibrated and self.court_calibration.court_bounds:
                self.ball_tracker.set_court_bounds(self.court_calibration.court_bounds)

            # Player tracker (4-player lock with appearance features)
            self.player_tracker = PlayerTracker(
                max_disappeared=self.config.get("player_max_disappeared", 90),
                max_distance=self.config.get("tracking_max_distance", 150.0),
                max_velocity=self.config.get("player_max_velocity", 150.0),
                max_players=self.config.get("max_players", 4),
                appearance_weight=self.config.get("player_appearance_weight", 0.4),
                init_frames=self.config.get("player_init_frames", 60),
                court_calibration=self.court_calibration,
                team_vote_window=self.config.get("player_team_vote_window", 15),
                coast_extrapolation_cap=self.config.get("coast_extrapolation_cap", 15),
                coast_velocity_decay=self.config.get("coast_velocity_decay", 0.85),
                gallery_enabled=self.config.get("player_gallery_enabled", True),
                gallery_reacquire_distance_px=self.config.get("player_gallery_reacquire_distance_px", 120.0),
                gallery_reacquire_min_appearance=self.config.get("player_gallery_reacquire_min_appearance", 0.15),
                gallery_reacquire_appearance_min=self.config.get("player_gallery_reacquire_appearance_min", 0.5),
                gallery_evict_min_hold_frames=self.config.get("player_gallery_evict_min_hold_frames", 60),
                bootstrap_min_window=self.config.get("player_bootstrap_min_window", 8),
                bootstrap_ball_required=self.config.get("player_bootstrap_ball_required", True),
                signature_color_weight=self.config.get("player_signature_color_weight", 0.4),
                signature_head_weight=self.config.get("player_signature_head_weight", 0.15),
                signature_height_weight=self.config.get("player_signature_height_weight", 0.3),
                signature_proportions_weight=self.config.get("player_signature_proportions_weight", 0.15),
                signature_height_smoothing=self.config.get("player_signature_height_smoothing", 30),
                off_court_grace_frames=self.config.get("player_off_court_grace_frames", 45),
                off_court_hold_frames=self.config.get("player_off_court_hold_frames", 90),
                off_court_cost_penalty_px=self.config.get("player_off_court_cost_penalty_px", 300.0),
                squatter_enabled=self.config.get("player_squatter_enabled", True),
                squatter_review_frames=self.config.get("player_squatter_review_frames", 120),
                squatter_min_fed_frames=self.config.get("player_squatter_min_fed_frames", 20),
                squatter_min_in_court_frac=self.config.get("player_squatter_min_in_court_frac", 0.35),
                squatter_cooldown_radius_m=self.config.get("player_squatter_cooldown_radius_m", 0.5),
                serve_zone_enabled=self.config.get("player_serve_zone_enabled", True),
                serve_zone_depth_m=self.config.get("player_serve_zone_depth_m", 3.0),
                serve_zone_side_margin_m=self.config.get("player_serve_zone_side_margin_m", 1.0),
                serve_zone_trial_frames=self.config.get("player_serve_zone_trial_frames", 90),
                serve_zone_ball_votes=self.config.get("player_serve_zone_ball_votes", 2),
                coast_vertical_damping=self.config.get("coast_vertical_damping", 0.5),
            )

            # Pose estimation (video mode for temporal smoothing)
            self.pose_estimator = PoseEstimator(
                min_detection_confidence=self.config.get("pose_confidence", 0.5),
                model_complexity=self.config.get("pose_complexity", 0),
            )

            # Action classifier (event-driven)
            self.action_classifier = ActionClassifier(
                pose_estimator=self.pose_estimator,
                temporal_window=self.config.get("temporal_window", 10),
                confidence_threshold=self.config.get("action_confidence", 0.3),
                court_calibration=self.court_calibration,
                team_aware=self.config.get("attribution_team_aware", True),
                width_side_enabled=self.config.get("attribution_width_side", True),
                width_window=self.config.get("attribution_width_window", 8),
                width_far_px=self.config.get("attribution_width_far_px", 26.0),
                width_near_px=self.config.get("attribution_width_near_px", 35.0),
                near_net_exempt_m=self.config.get("attribution_near_net_exempt_m", 2.5),
            )

            # Spike outcome/zone analyzer (pure observer of the stream above)
            self.spike_analyzer = SpikeAnalyzer(self.court_calibration)

            # Game state detection
            self.game_state_manager = GameStateManager(self.config)

            self.logger.info("Frame processor components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize frame processor components: {e}")
            raise

    def set_court_calibration(self, calibration: CourtCalibration) -> None:
        """Set or update court calibration after initialization."""
        self.court_calibration = calibration
        self.court_detector = calibration
        self.player_detector.set_court_detector(calibration)
        self.player_tracker.set_court_calibration(calibration)
        self.action_classifier.set_court_calibration(calibration)
        self.spike_analyzer.court = calibration
        if calibration.is_calibrated and calibration.court_bounds:
            self.ball_tracker.set_court_bounds(calibration.court_bounds)

    def setup_video_fps(self, fps: float) -> None:
        """Setup components with video FPS information."""
        if hasattr(self.game_state_manager, "set_video_info"):
            self.game_state_manager.fps = fps

    def setup_video_dimensions(self, width: int, height: int) -> None:
        """Setup components with video dimensions."""
        if hasattr(self.game_state_manager, "set_video_info"):
            self.game_state_manager.set_video_info(
                getattr(self.game_state_manager, "fps", 30.0), width, height
            )

    def process_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
        enable_court_redetection: bool = False,
    ) -> Dict[str, Any]:
        """Process a single video frame.

        Args:
            frame: Input frame.
            frame_index: Current frame index.
            enable_court_redetection: Ignored (court is calibrated once).

        Returns:
            Frame processing results dict.
        """
        frame_result = {
            "frame_index": frame_index,
            "ball_detections": [],
            "player_detections": [],
            "tracked_players": [],
            "tracked_ball": None,
            "actions": [],
            "processing_time": 0.0,
            "game_state": {},
        }

        start_time = time.time()

        try:
            # 0. Court is pre-calibrated -- just ensure mask exists
            self.court_calibration.detect_court(frame)

            # 1. Detection
            ball_detections = self.ball_detector.detect(frame)
            player_detections = self.player_detector.detect(frame)

            frame_result["ball_detections"] = ball_detections
            frame_result["player_detections"] = player_detections

            # 2. Two-zone filter. STRICT (foot-in-court) is the admission pool for
            # NEW tracks and the live/dead-ball count; the detector output (already
            # play-area bbox-overlap filtered) is the association set, so an
            # established track can follow a player who steps off-court (server
            # behind baseline, chaser). NEW tracks are still gated by the strict
            # foot-in-court admission test inside PlayerTracker.
            strict_players = self.court_calibration.filter_detections_by_court(player_detections)
            play_area_players = player_detections

            # 3. Tracking. The top-1 ball detection anchors serve-zone
            # admission to the likely server (the server holds/tosses the
            # ball; a serve-zone bystander does not).
            ball_position = None
            if ball_detections:
                top_ball = max(ball_detections, key=lambda d: d.get("confidence", 0))
                bc = top_ball.get("center")
                if bc and bc[0] is not None:
                    ball_position = (float(bc[0]), float(bc[1]))
            tracked_players = self.player_tracker.update(
                play_area_players,
                frame,
                strict_detections=strict_players,
                ball_active=bool(ball_detections),
                n_court_det=len(strict_players),
                ball_position=ball_position,
            )
            tracked_ball = self.ball_tracker.update(ball_detections)

            frame_result["tracked_players"] = tracked_players
            frame_result["tracked_ball"] = tracked_ball

            # 4. Action recognition (event-driven -- only emits at ball contacts)
            actions = []
            if tracked_players:
                actions = self.action_classifier.classify_actions(
                    frame,
                    tracked_players,
                    tracked_ball,
                    frame_number=frame_index,
                )

                # Filter low-confidence and unknown
                actions = [
                    a
                    for a in actions
                    if a.get("action", "unknown") != "unknown"
                    and a.get("confidence", 0.0) > 0.1
                ]

            frame_result["actions"] = actions

            # 5b. Spike enrichment (pure observer -- never mutates the actions)
            self.spike_analyzer.observe(frame_index, tracked_ball, tracked_players, actions)

            # 6. Game state machine (pure observer: ball velocity + emitted
            # actions; runs once per frame, after the actions exist)
            game_state_info = self.game_state_manager.analyze_frame(frame_result, frame_index)
            frame_result["game_state"] = game_state_info.to_dict()

        except Exception as e:
            self.logger.error(f"Error processing frame {frame_index}: {e}")

        frame_result["processing_time"] = time.time() - start_time
        return frame_result

    def flush_actions(self) -> List[Dict[str, Any]]:
        """Return the last action(s) the classifier held back for look-ahead.

        The action classifier finalises each contact only once the next contact
        arrives (needed to tell a set from an overpass), so the final contact of
        a video stays pending until flushed. Call once after the last frame.
        """
        actions = self.action_classifier.flush()
        visible = []
        if actions:
            # The flushed contacts never pass through process_frame; feed the
            # analyzer so a last-video spike/dig still resolves (same emission
            # filter as process_frame applies).
            visible = [
                a
                for a in actions
                if a.get("action", "unknown") != "unknown"
                and a.get("confidence", 0.0) > 0.1
            ]
            if visible:
                self.spike_analyzer.observe(None, None, None, visible)
        # The flushed contacts close the trailing rally group before the
        # final point decision.
        self.game_state_manager.observe_flushed_actions(visible)
        self.game_state_manager.finish()
        self.spike_analyzer.flush()
        return actions

    def reset_trackers(self) -> None:
        """Reset all tracking state."""
        self.player_tracker.reset()

        self.ball_tracker.reset()
        self.ball_detector.reset()
        self.action_classifier.reset()
        self.spike_analyzer.reset()

        self.game_state_manager = GameStateManager(self.config)
        self.logger.debug("Trackers and game state reset")

    def get_court_detector(self):
        """Get court calibration (backward compat name)."""
        return self.court_calibration

    def get_ball_detector(self):
        """Get the ball detector."""
        return self.ball_detector

    def get_game_state_manager(self):
        """Get the game state manager."""
        return self.game_state_manager
