"""
Action classifier for volleyball video analysis.

This module implements action recognition for volleyball-specific movements
using pose data and temporal features.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from collections import deque
from enum import Enum
import logging

from .pose_estimator import PoseEstimator
from .volleyball_actions import VolleyballAction
from .enhanced_ball_contact import EnhancedBallContactValidator
from .temporal_contact_validator import TemporalContactValidator
from .ball_trajectory_analyzer import BallTrajectoryAnalyzer
from .court_position_validator import CourtPositionValidator


class ActionClassifier:
    """Classifier for volleyball actions using pose and context data.

    Recognizes volleyball-specific actions (digs, sets, blocks, aces, spikes)
    based on player pose, ball trajectory, and temporal context.
    """

    def __init__(
        self,
        pose_estimator: PoseEstimator,
        temporal_window: int = 10,
        confidence_threshold: float = 0.6,
        enhanced_validation_config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the action classifier.

        Args:
            pose_estimator: Pose estimator instance
            temporal_window: Number of frames to consider for temporal analysis
            confidence_threshold: Minimum confidence for action classification
        """
        self.pose_estimator = pose_estimator
        self.temporal_window = temporal_window
        self.confidence_threshold = confidence_threshold

        # Store temporal data for each tracked player
        self.player_histories = {}  # track_id -> deque of frame data
        
        # Store recent actions to prevent consecutive identical actions
        self.recent_actions = {}  # track_id -> list of (frame_number, action, confidence)

        self.logger = logging.getLogger(__name__)

        # Action classification rules
        self._initialize_action_rules()
        
        # Enhanced validation modules
        self.enhanced_validation_config = enhanced_validation_config or {}
        self.enhanced_validation_enabled = self.enhanced_validation_config.get("enabled", True)
        
        if self.enhanced_validation_enabled:
            # Initialize enhanced validation modules
            self.ball_contact_validator = EnhancedBallContactValidator(
                self.enhanced_validation_config.get("ball_contact", {})
            )
            
            self.temporal_validator = TemporalContactValidator(
                self.enhanced_validation_config.get("temporal", {})
            )
            
            self.trajectory_analyzer = BallTrajectoryAnalyzer(
                self.enhanced_validation_config.get("trajectory", {})
            )
            
            self.court_validator = CourtPositionValidator(
                self.enhanced_validation_config.get("court", {})
            )
        else:
            self.ball_contact_validator = None
            self.temporal_validator = None
            self.trajectory_analyzer = None
            self.court_validator = None

    def classify_actions(
        self,
        frame: np.ndarray,
        player_detections: List[Dict[str, Any]],
        ball_info: Optional[Dict[str, Any]] = None,
        frame_number: Optional[int] = None,
        court_info: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Classify actions for all players in the current frame.

        Args:
            frame: Current video frame
            player_detections: List of player detections with tracking IDs
            ball_info: Ball detection/tracking information

        Returns:
            List of action classifications for each player
        """
        action_results = []

        # Estimate poses for all players
        poses = self.pose_estimator.estimate_poses_batch(frame, player_detections)

        for i, (detection, pose_data) in enumerate(zip(player_detections, poses)):
            track_id = detection.get("track_id")

            if track_id is None or pose_data is None:
                continue

            # Update player history
            self._update_player_history(track_id, detection, pose_data, ball_info)

            # Classify action for this player with enhanced validation
            action_result = self._classify_player_action_enhanced(
                track_id=track_id,
                detection=detection,
                pose_data=pose_data,
                ball_info=ball_info,
                frame_number=frame_number,
                court_info=court_info
            )

            if action_result:
                # Additional safety check: no ball detected means no actions possible
                if ball_info is None or not ball_info.get("center"):
                    # No ball detected - force action to UNKNOWN
                    action_result["action"] = VolleyballAction.UNKNOWN.value
                    action_result["confidence"] = 0.0
                    action_result["no_ball_detected"] = True
                
                action_result.update({
                    "track_id": track_id,
                    "bbox": detection["bbox"],
                    "frame_pose": pose_data
                })
                
                # Apply temporal filtering to prevent consecutive identical actions
                if self._should_filter_consecutive_action(track_id, action_result["action"], frame_number):
                    action_result["action"] = VolleyballAction.UNKNOWN.value
                    action_result["confidence"] = 0.0
                    action_result["filtered_consecutive"] = True
                
                action_results.append(action_result)

        return action_results

    def _initialize_action_rules(self) -> None:
        """Initialize rule-based action classification criteria."""
        self.action_rules = {
            VolleyballAction.DIG: {
                "arm_height_threshold": 0.7,  # Arms below body center
                "body_lean_min": 15,  # Leaning forward
                "arm_angle_max": 120,  # Arms extended/bent
                "requires_ball_contact": True
            },
            VolleyballAction.SET: {
                "arm_height_threshold": 0.3,  # Arms above head
                "arm_angle_min": 90,  # Arms bent upward
                "finger_position": "overhead",
                "requires_ball_contact": True
            },
            VolleyballAction.SPIKE: {
                "arm_height_threshold": 0.2,  # One arm high
                "arm_angle_min": 150,  # Arm extended
                "jump_indicator": True,
                "requires_ball_contact": True
            },
            VolleyballAction.BLOCK: {
                "arm_height_threshold": 0.2,  # Both arms high
                "arm_position": "parallel_up",
                "jump_indicator": True,
                "near_net": True
            },
            VolleyballAction.SERVE: {
                "arm_swing": True,
                "ball_trajectory": "serve_pattern",
                "court_position": "back"
            }
        }

    def _update_player_history(
        self,
        track_id: int,
        detection: Dict[str, Any],
        pose_data: Dict[str, Any],
        ball_info: Optional[Dict[str, Any]]
    ) -> None:
        """Update temporal history for a player.

        Args:
            track_id: Player tracking ID
            detection: Player detection data
            pose_data: Pose estimation data
            ball_info: Ball information
        """
        if track_id not in self.player_histories:
            self.player_histories[track_id] = deque(maxlen=self.temporal_window)

        frame_data = {
            "detection": detection,
            "pose": pose_data,
            "ball": ball_info,
            "timestamp": len(self.player_histories[track_id])
        }

        self.player_histories[track_id].append(frame_data)

    def _classify_player_action(
        self,
        track_id: int,
        frame_index: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Classify action for a specific player.

        Args:
            track_id: Player tracking ID
            frame_index: Specific frame index (None for latest)

        Returns:
            Action classification result
        """
        if track_id not in self.player_histories:
            return None

        history = self.player_histories[track_id]
        if len(history) == 0:
            return None

        # Use latest frame if no specific index provided
        current_frame = history[-1] if frame_index is None else history[frame_index]

        # Extract features for classification
        features = self._extract_action_features(track_id, current_frame)

        # Classify action using rule-based approach
        action_scores = self._calculate_action_scores(features)

        # Determine best action
        best_action = max(action_scores.items(), key=lambda x: x[1])
        action_type, confidence = best_action

        if confidence < self.confidence_threshold:
            action_type = VolleyballAction.UNKNOWN

        return {
            "action": action_type.value,
            "confidence": float(confidence),
            "features": features,
            "action_scores": {a.value: s for a, s in action_scores.items()}
        }

    def _classify_player_action_enhanced(
        self,
        track_id: int,
        detection: Dict[str, Any],
        pose_data: Dict[str, Any],
        ball_info: Optional[Dict[str, Any]] = None,
        frame_number: Optional[int] = None,
        court_info: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Enhanced action classification with ball contact and position validation.
        
        Args:
            track_id: Player tracking ID
            detection: Player detection data
            pose_data: Pose estimation data
            ball_info: Ball tracking information
            frame_number: Current frame number
            court_info: Court detection information
            
        Returns:
            Enhanced action classification result
        """
        # Start with basic classification
        basic_result = self._classify_player_action(track_id)
        
        if not basic_result:
            return None
            
        if not self.enhanced_validation_enabled:
            return basic_result
        
        # Get the predicted action
        predicted_action = VolleyballAction(basic_result["action"])
        player_bbox = detection.get("bbox", [])
        
        # Enhanced validation results
        validation_results = {}
        
        try:
            # 1. Enhanced ball contact validation - check all available ball candidates
            if self.ball_contact_validator and ball_info:
                # Try to find best ball candidate if multiple balls available
                best_ball_info = self._find_best_ball_candidate(ball_info, pose_data, player_bbox)
                
                ball_contact_validation = self.ball_contact_validator.validate_ball_contact(
                    best_ball_info, pose_data, predicted_action, player_bbox
                )
                validation_results["ball_contact"] = ball_contact_validation
        except Exception as e:
            self.logger.debug(f"Ball contact validation failed: {e}")
            validation_results["ball_contact"] = {"valid": False, "confidence": 0.0, "error": str(e)}
        
        try:
            # 2. Temporal contact validation
            if self.temporal_validator and ball_info:
                # Update trajectory analyzer first
                if self.trajectory_analyzer and frame_number is not None:
                    trajectory_analysis = self.trajectory_analyzer.analyze_trajectory(
                        ball_info, frame_number
                    )
                    validation_results["trajectory_analysis"] = trajectory_analysis
                    
                    # Validate trajectory for action type
                    trajectory_validation = self.trajectory_analyzer.validate_action_trajectory(
                        predicted_action, trajectory_analysis
                    )
                    validation_results["trajectory_validation"] = trajectory_validation
                
                # Get instantaneous validation for temporal analysis
                instantaneous_validation = validation_results.get("ball_contact", {"valid": False, "confidence": 0.0})
                
                temporal_validation = self.temporal_validator.validate_temporal_contact(
                    track_id, ball_info, instantaneous_validation, predicted_action, frame_number
                )
                validation_results["temporal_contact"] = temporal_validation
        except Exception as e:
            self.logger.debug(f"Temporal validation failed: {e}")
            validation_results["temporal_contact"] = {"valid": False, "confidence": 0.0, "error": str(e)}
        
        try:
            # 3. Court position validation
            if self.court_validator and court_info:
                # Set court boundaries if available
                if "boundaries" in court_info:
                    self.court_validator.set_court_boundaries(court_info["boundaries"])
                
                # Calculate player center position
                if player_bbox and len(player_bbox) >= 4:
                    player_center = (
                        (player_bbox[0] + player_bbox[2]) / 2,
                        (player_bbox[1] + player_bbox[3]) / 2
                    )
                    
                    court_validation = self.court_validator.validate_position_for_action(
                        player_center, predicted_action, player_bbox
                    )
                    validation_results["court_position"] = court_validation
                    
                    # Special serve validation
                    if predicted_action == VolleyballAction.SERVE:
                        ball_position = None
                        if ball_info and "center" in ball_info:
                            ball_position = tuple(ball_info["center"])
                        
                        serve_validation = self.court_validator.validate_serve_position(
                            player_center, ball_position, "contact"
                        )
                        validation_results["serve_position"] = serve_validation
        except Exception as e:
            self.logger.debug(f"Court validation failed: {e}")
            validation_results["court_position"] = {"valid": True, "confidence": 1.0, "error": str(e)}
        
        try:
            # Calculate enhanced confidence score
            enhanced_confidence = self._calculate_enhanced_confidence(
                basic_result["confidence"], validation_results, predicted_action
            )
            
            # Determine if action should be filtered out
            action_valid = self._determine_action_validity(validation_results, predicted_action)
            
            # Update result with enhanced validation
            enhanced_result = basic_result.copy()
            enhanced_result.update({
                "enhanced_confidence": enhanced_confidence,
                "action_valid": action_valid,
                "validation_results": validation_results,
                "enhanced_validation_enabled": True
            })
            
            # Override confidence with enhanced score
            enhanced_result["confidence"] = enhanced_confidence
            
            # Filter out invalid actions in strict mode
            strict_mode = self.enhanced_validation_config.get("strict_mode", True)
            if strict_mode and not action_valid:
                enhanced_result["action"] = VolleyballAction.UNKNOWN.value
                enhanced_result["confidence"] = 0.1
            
            return enhanced_result
            
        except Exception as e:
            self.logger.debug(f"Enhanced validation processing failed: {e}")
            # Fallback to basic result with validation info
            fallback_result = basic_result.copy()
            fallback_result.update({
                "enhanced_validation_enabled": True,
                "validation_error": str(e),
                "validation_results": validation_results
            })
            return fallback_result

    def _extract_action_features(
        self,
        track_id: int,
        current_frame: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract features for action classification.

        Args:
            track_id: Player tracking ID
            current_frame: Current frame data

        Returns:
            Extracted features dictionary
        """
        features = {}
        pose_data = current_frame["pose"]
        ball_data = current_frame.get("ball")

        # Pose-based features
        pose_features = pose_data.get("pose_features", {})
        features.update(pose_features)

        # Ball interaction features
        if ball_data:
            features.update(self._extract_ball_interaction_features(pose_data, ball_data))

        # Temporal features
        if track_id in self.player_histories:
            features.update(self._extract_temporal_features(track_id))

        # Context features
        features.update(self._extract_context_features(current_frame))

        return features

    def _extract_ball_interaction_features(
        self,
        pose_data: Dict[str, Any],
        ball_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract features related to player-ball interaction.

        Args:
            pose_data: Player pose data
            ball_data: Ball position/trajectory data

        Returns:
            Ball interaction features
        """
        features = {}

        ball_center = ball_data.get("center", [0, 0])
        player_bbox = pose_data.get("bbox", [0, 0, 0, 0])

        # Distance to ball
        player_center = [
            (player_bbox[0] + player_bbox[2]) / 2,
            (player_bbox[1] + player_bbox[3]) / 2
        ]

        ball_distance = np.sqrt(
            (ball_center[0] - player_center[0])**2 +
            (ball_center[1] - player_center[1])**2
        )

        features["ball_distance"] = float(ball_distance)
        features["ball_in_reach"] = ball_distance < 100  # Threshold for reachable ball

        # Ball height relative to player
        player_height = player_bbox[3] - player_bbox[1]
        ball_relative_height = (ball_center[1] - player_bbox[1]) / player_height
        features["ball_relative_height"] = float(ball_relative_height)

        # Ball velocity (if available)
        ball_velocity = ball_data.get("velocity", [0, 0])
        if ball_velocity:
            features["ball_speed"] = float(np.linalg.norm(ball_velocity))
            features["ball_direction"] = ball_velocity

        return features

    def _extract_temporal_features(self, track_id: int) -> Dict[str, Any]:
        """Extract temporal features from player history.

        Args:
            track_id: Player tracking ID

        Returns:
            Temporal features
        """
        features = {}
        history = self.player_histories[track_id]

        if len(history) < 2:
            return features

        # Movement analysis
        positions = []
        for frame_data in history:
            bbox = frame_data["detection"]["bbox"]
            center = [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
            positions.append(center)

        positions = np.array(positions)

        # Calculate movement speed
        if len(positions) > 1:
            movements = np.diff(positions, axis=0)
            speeds = np.linalg.norm(movements, axis=1)
            features["avg_movement_speed"] = float(np.mean(speeds))
            features["max_movement_speed"] = float(np.max(speeds))

        # Pose stability
        arm_heights = []
        for frame_data in history:
            pose_features = frame_data["pose"].get("pose_features", {})
            left_arm_height = pose_features.get("left_arm_height", 0)
            right_arm_height = pose_features.get("right_arm_height", 0)
            arm_heights.append([left_arm_height, right_arm_height])

        if arm_heights:
            arm_heights = np.array(arm_heights)
            features["arm_height_stability"] = float(np.std(arm_heights))

        return features

    def _extract_context_features(self, frame_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract contextual features from frame data.

        Args:
            frame_data: Current frame data

        Returns:
            Context features
        """
        features = {}

        detection = frame_data["detection"]
        bbox = detection["bbox"]

        # Player position on court (estimated)
        player_center_x = (bbox[0] + bbox[2]) / 2
        player_center_y = (bbox[1] + bbox[3]) / 2

        # Normalize positions (assuming standard frame dimensions)
        features["normalized_x"] = float(player_center_x / 1920)  # Assume 1920 width
        features["normalized_y"] = float(player_center_y / 1080)  # Assume 1080 height

        # Estimate court region
        if features["normalized_y"] > 0.7:
            features["court_region"] = "back"
        elif features["normalized_y"] < 0.3:
            features["court_region"] = "front"
        else:
            features["court_region"] = "middle"

        return features

    def _calculate_action_scores(self, features: Dict[str, Any]) -> Dict[VolleyballAction, float]:
        """Calculate scores for each volleyball action.

        Args:
            features: Extracted features

        Returns:
            Dictionary of action scores
        """
        scores = {}

        # Dig detection
        scores[VolleyballAction.DIG] = self._score_dig_action(features)

        # Set detection
        scores[VolleyballAction.SET] = self._score_set_action(features)

        # Spike detection
        scores[VolleyballAction.SPIKE] = self._score_spike_action(features)

        # Block detection
        scores[VolleyballAction.BLOCK] = self._score_block_action(features)

        # Serve detection
        scores[VolleyballAction.SERVE] = self._score_serve_action(features)

        # Ace is a special case of serve that results in a point
        scores[VolleyballAction.ACE] = scores[VolleyballAction.SERVE] * 0.1  # Lower probability

        # Apply cross-action validation to prevent misclassification
        scores = self._apply_cross_action_validation(scores, features)

        return scores

    def _score_dig_action(self, features: Dict[str, Any]) -> float:
        """Score dig action based on features."""
        score = 0.0

        # Low arm position
        left_arm_height = features.get("left_arm_height", 500)
        right_arm_height = features.get("right_arm_height", 500)
        avg_arm_height = (left_arm_height + right_arm_height) / 2

        if avg_arm_height > 400:  # Arms low
            score += 0.3

        # Body lean forward
        body_lean = features.get("body_lean", 0)
        if body_lean > 15:
            score += 0.2

        # Ball interaction
        if features.get("ball_in_reach", False):
            score += 0.3

        # Ball coming down (typical for dig)
        ball_relative_height = features.get("ball_relative_height", 0.5)
        if 0.3 < ball_relative_height < 0.8:
            score += 0.2

        return min(score, 1.0)

    def _score_set_action(self, features: Dict[str, Any]) -> float:
        """Score set action based on features."""
        score = 0.0

        # Both arms moderately high (for overhead setting position)
        left_arm_height = features.get("left_arm_height", 500)
        right_arm_height = features.get("right_arm_height", 500)
        avg_arm_height = (left_arm_height + right_arm_height) / 2
        arm_height_diff = abs(left_arm_height - right_arm_height)

        # Arms should be high but not as extreme as spikes
        if 150 < avg_arm_height < 250:  # Moderate arm height (not too extreme)
            score += 0.3
        elif avg_arm_height < 200:  # Very high arms
            score += 0.2  # Lower score since might be spike/block

        # Set characteristic: arms relatively symmetric (both used for setting)
        if arm_height_diff < 60:  # Arms fairly symmetric
            score += 0.3
        elif arm_height_diff > 120:  # Too asymmetric (more like spike)
            score -= 0.3

        # Ball overhead and controlled contact
        ball_relative_height = features.get("ball_relative_height", 0.5)
        if 0.1 < ball_relative_height < 0.4:  # Ball overhead but accessible
            score += 0.4
        elif ball_relative_height < 0.1:  # Ball too high (more like spike)
            score += 0.1

        # Ball interaction is essential for sets
        if features.get("ball_in_reach", False):
            score += 0.2

        # Sets can happen anywhere but are more common in middle/back for setup
        court_region = features.get("court_region", "")
        if court_region in ["middle", "back"]:
            score += 0.1
        elif court_region == "front":
            score += 0.05  # Can happen but less common

        # Low to moderate movement (sets are more controlled)
        movement_speed = features.get("max_movement_speed", 0)
        if movement_speed < 8:  # Controlled, precise movement
            score += 0.2
        elif movement_speed > 15:  # Too aggressive for set
            score -= 0.2

        # Penalty for extreme arm positions (more characteristic of spike/block)
        if avg_arm_height < 120:  # Arms too high (spike-like)
            score -= 0.2
        
        return max(0.0, min(score, 1.0))

    def _score_spike_action(self, features: Dict[str, Any]) -> float:
        """Score spike action based on features."""
        score = 0.0

        # One arm much higher than the other (asymmetric arm position)
        left_arm_height = features.get("left_arm_height", 500)
        right_arm_height = features.get("right_arm_height", 500)
        max_arm_height = min(left_arm_height, right_arm_height)  # Highest arm
        min_arm_height = max(left_arm_height, right_arm_height)  # Lowest arm
        arm_height_diff = abs(left_arm_height - right_arm_height)

        # Primary spike indicator: one arm very high
        if max_arm_height < 150:  # Very high arm
            score += 0.3
        
        # Strong spike indicator: significant arm height difference (asymmetric)
        if arm_height_diff > 100:  # Large difference between arms
            score += 0.4
        elif arm_height_diff < 50:  # Arms too similar (more like block/set)
            score -= 0.2

        # High movement speed (aggressive jumping for spike)
        movement_speed = features.get("max_movement_speed", 0)
        if movement_speed > 15:  # Higher threshold for aggressive spike motion
            score += 0.3
        elif movement_speed > 10:
            score += 0.1

        # Ball interaction high above head (spike contact point)
        ball_relative_height = features.get("ball_relative_height", 0.5)
        if ball_relative_height < 0.1:  # Very high ball contact
            score += 0.3
        elif ball_relative_height < 0.2:
            score += 0.1

        # Court position (usually front/middle for spikes)
        court_region = features.get("court_region", "")
        if court_region in ["front", "middle"]:
            score += 0.1

        # Penalize if both arms are equally high (more like a block)
        if abs(left_arm_height - right_arm_height) < 30 and max_arm_height < 200:
            score -= 0.3

        return max(0.0, min(score, 1.0))

    def _score_block_action(self, features: Dict[str, Any]) -> float:
        """Score block action based on features."""
        score = 0.0

        # Both arms high and parallel (key block characteristic)
        left_arm_height = features.get("left_arm_height", 500)
        right_arm_height = features.get("right_arm_height", 500)
        arm_height_diff = abs(left_arm_height - right_arm_height)
        avg_arm_height = (left_arm_height + right_arm_height) / 2

        # Both arms must be high
        if left_arm_height < 200 and right_arm_height < 200:
            score += 0.3
        
        # Strong block indicator: arms at similar height (parallel/symmetric)
        if arm_height_diff < 50:  # Arms are parallel
            score += 0.4
        elif arm_height_diff > 100:  # Arms too different (more like spike)
            score -= 0.3

        # Moderate movement (controlled jumping, not aggressive like spike)
        movement_speed = features.get("max_movement_speed", 0)
        if 5 < movement_speed < 12:  # Controlled block jump
            score += 0.2
        elif movement_speed > 15:  # Too aggressive for block
            score -= 0.2

        # Ball position (blocks typically occur with ball slightly in front)
        ball_relative_height = features.get("ball_relative_height", 0.5)
        if 0.0 < ball_relative_height < 0.3:  # Ball overhead to slightly in front
            score += 0.2

        # Front court position (essential for blocks)
        court_region = features.get("court_region", "")
        if court_region == "front":
            score += 0.4
        elif court_region in ["middle", "back"]:
            score -= 0.2  # Blocks rarely happen in back court

        # Bonus for symmetric arm position with both arms high
        if arm_height_diff < 30 and avg_arm_height < 180:
            score += 0.2

        return max(0.0, min(score, 1.0))

    def _apply_cross_action_validation(self, scores: Dict[VolleyballAction, float], features: Dict[str, Any]) -> Dict[VolleyballAction, float]:
        """Apply cross-validation between similar actions to improve classification.
        
        Args:
            scores: Initial action scores
            features: Extracted features
            
        Returns:
            Adjusted action scores
        """
        adjusted_scores = scores.copy()
        
        # Get key discriminating features
        left_arm_height = features.get("left_arm_height", 500)
        right_arm_height = features.get("right_arm_height", 500)
        arm_height_diff = abs(left_arm_height - right_arm_height)
        avg_arm_height = (left_arm_height + right_arm_height) / 2
        movement_speed = features.get("max_movement_speed", 0)
        ball_relative_height = features.get("ball_relative_height", 0.5)
        court_region = features.get("court_region", "")
        
        # Spike vs Block vs Set discrimination
        spike_score = scores.get(VolleyballAction.SPIKE, 0)
        block_score = scores.get(VolleyballAction.BLOCK, 0)
        set_score = scores.get(VolleyballAction.SET, 0)
        
        # If multiple high scores, apply discriminating logic
        high_scores = [s for s in [spike_score, block_score, set_score] if s > 0.3]
        
        if len(high_scores) >= 2:
            # Multiple similar actions detected - apply stronger discrimination
            
            # Strong asymmetric arms favor spike
            if arm_height_diff > 120:
                adjusted_scores[VolleyballAction.SPIKE] *= 1.3
                adjusted_scores[VolleyballAction.BLOCK] *= 0.5
                adjusted_scores[VolleyballAction.SET] *= 0.6
            
            # Strong symmetric arms favor block or set
            elif arm_height_diff < 40:
                # Very high symmetric arms favor block
                if avg_arm_height < 160 and court_region == "front":
                    adjusted_scores[VolleyballAction.BLOCK] *= 1.4
                    adjusted_scores[VolleyballAction.SPIKE] *= 0.4
                    adjusted_scores[VolleyballAction.SET] *= 0.7
                # Moderate symmetric arms favor set
                elif 160 < avg_arm_height < 220:
                    adjusted_scores[VolleyballAction.SET] *= 1.3
                    adjusted_scores[VolleyballAction.SPIKE] *= 0.5
                    adjusted_scores[VolleyballAction.BLOCK] *= 0.8
            
            # High movement speed favors spike over set/block
            if movement_speed > 15:
                adjusted_scores[VolleyballAction.SPIKE] *= 1.2
                adjusted_scores[VolleyballAction.SET] *= 0.6
                adjusted_scores[VolleyballAction.BLOCK] *= 0.8
            
            # Low movement speed favors set
            elif movement_speed < 5:
                adjusted_scores[VolleyballAction.SET] *= 1.2
                adjusted_scores[VolleyballAction.SPIKE] *= 0.7
            
            # Very high ball contact favors spike
            if ball_relative_height < 0.05:
                adjusted_scores[VolleyballAction.SPIKE] *= 1.3
                adjusted_scores[VolleyballAction.SET] *= 0.7
                adjusted_scores[VolleyballAction.BLOCK] *= 0.8
            
            # Moderate ball height favors set
            elif 0.1 < ball_relative_height < 0.3:
                adjusted_scores[VolleyballAction.SET] *= 1.2
                adjusted_scores[VolleyballAction.SPIKE] *= 0.8
            
            # Court position discrimination
            if court_region == "front":
                # Front court: spike and block more likely than set
                adjusted_scores[VolleyballAction.SPIKE] *= 1.1
                adjusted_scores[VolleyballAction.BLOCK] *= 1.2
                adjusted_scores[VolleyballAction.SET] *= 0.8
            elif court_region == "back":
                # Back court: set more likely, spike less likely, block very unlikely
                adjusted_scores[VolleyballAction.SET] *= 1.2
                adjusted_scores[VolleyballAction.SPIKE] *= 0.7
                adjusted_scores[VolleyballAction.BLOCK] *= 0.3
        
        # Ensure scores remain in valid range
        for action in adjusted_scores:
            adjusted_scores[action] = max(0.0, min(adjusted_scores[action], 1.0))
        
        return adjusted_scores

    def _score_serve_action(self, features: Dict[str, Any]) -> float:
        """Score serve action based on features."""
        score = 0.0

        # Back court position
        court_region = features.get("court_region", "")
        if court_region == "back":
            score += 0.5

        # Arm swing motion (would need temporal analysis)
        arm_height_stability = features.get("arm_height_stability", 0)
        if arm_height_stability > 50:  # Variable arm position
            score += 0.3

        # Ball interaction
        if features.get("ball_in_reach", False):
            score += 0.2

        return min(score, 1.0)

    def _find_best_ball_candidate(
        self, 
        ball_info: Dict[str, Any], 
        pose_data: Dict[str, Any], 
        player_bbox: List[float]
    ) -> Dict[str, Any]:
        """Find the best ball candidate for contact validation.
        
        Args:
            ball_info: Primary ball tracking info (may contain multiple candidates)
            pose_data: Player pose data
            player_bbox: Player bounding box [x1, y1, x2, y2]
            
        Returns:
            Best ball candidate for this player
        """
        # If ball_info has multiple candidates, choose the closest to player
        candidates = ball_info.get("candidates", [ball_info])
        if len(candidates) <= 1:
            return ball_info
        
        # Calculate player center
        player_center = [
            (player_bbox[0] + player_bbox[2]) / 2,
            (player_bbox[1] + player_bbox[3]) / 2
        ]
        
        best_candidate = ball_info
        best_distance = float('inf')
        
        for candidate in candidates:
            ball_center = candidate.get("center", [0, 0])
            if not ball_center:
                continue
                
            # Calculate distance to player center
            distance = np.sqrt(
                (ball_center[0] - player_center[0]) ** 2 + 
                (ball_center[1] - player_center[1]) ** 2
            )
            
            # Prefer balls that are closer to player
            if distance < best_distance:
                best_distance = distance
                best_candidate = candidate
        
        self.logger.debug(f"Selected best ball candidate at distance {best_distance:.1f} from player")
        return best_candidate

    def _should_filter_consecutive_action(self, track_id: int, action: str, frame_number: Optional[int] = None) -> bool:
        """Check if action should be filtered due to consecutive identical actions.
        
        Args:
            track_id: Player tracking ID
            action: Action type being classified
            frame_number: Current frame number
            
        Returns:
            True if action should be filtered out
        """
        if action == "unknown" or frame_number is None:
            return False
            
        # Initialize recent actions for this player if needed
        if track_id not in self.recent_actions:
            self.recent_actions[track_id] = []
            
        recent = self.recent_actions[track_id]
        
        # Remove old actions (older than 30 frames)
        cutoff_frame = frame_number - 30
        recent = [r for r in recent if r[0] > cutoff_frame]
        self.recent_actions[track_id] = recent
        
        # Check for consecutive identical actions
        if len(recent) > 0:
            last_frame, last_action, last_confidence = recent[-1]
            
            # Filter if same action within last 5 frames (avoid immediate duplicates)
            if action == last_action and frame_number - last_frame < 5:
                return True
                
            # Filter if more than 1 of the same action in last 15 frames (more aggressive)
            same_action_count = sum(1 for f, a, _ in recent if a == action and frame_number - f < 15)
            if same_action_count >= 1:
                return True
        
        # Record this action
        self.recent_actions[track_id].append((frame_number, action, 0.8))  # Placeholder confidence
        
        return False

    def _calculate_enhanced_confidence(
        self,
        base_confidence: float,
        validation_results: Dict[str, Any],
        action_type: VolleyballAction
    ) -> float:
        """Calculate enhanced confidence score incorporating all validation results.
        
        Args:
            base_confidence: Base confidence from traditional classification
            validation_results: Results from all validation modules
            action_type: Predicted action type
            
        Returns:
            Enhanced confidence score (0.0 to 1.0)
        """
        # Start with base confidence (weighted 30%)
        enhanced_confidence = base_confidence * 0.3
        
        # Ball contact validation (weighted 40%)
        ball_contact = validation_results.get("ball_contact", {})
        if ball_contact:
            ball_confidence = ball_contact.get("confidence", 0.0)
            enhanced_confidence += ball_confidence * 0.4
        else:
            # No ball contact validation - use reduced weight for pose-only actions
            enhanced_confidence += base_confidence * 0.4
        
        # Temporal validation (weighted 20%)
        temporal_contact = validation_results.get("temporal_contact", {})
        if temporal_contact:
            temporal_confidence = temporal_contact.get("confidence", 0.0)
            enhanced_confidence += temporal_confidence * 0.2
        else:
            enhanced_confidence += base_confidence * 0.2
        
        # Court position validation (weighted 10%)
        court_position = validation_results.get("court_position", {})
        if court_position:
            court_confidence = court_position.get("confidence", 1.0)
            enhanced_confidence += court_confidence * 0.1
        else:
            enhanced_confidence += 0.1  # Default court confidence
        
        # Trajectory validation bonus/penalty
        trajectory_validation = validation_results.get("trajectory_validation", {})
        if trajectory_validation:
            traj_confidence = trajectory_validation.get("confidence", 0.5)
            if traj_confidence > 0.7:
                enhanced_confidence *= 1.1  # Bonus for good trajectory match
            elif traj_confidence < 0.3:
                enhanced_confidence *= 0.8  # Penalty for poor trajectory match
        
        # Special serve position validation
        if action_type == VolleyballAction.SERVE:
            serve_position = validation_results.get("serve_position", {})
            if serve_position:
                if not serve_position.get("valid", True):
                    enhanced_confidence *= 0.3  # Heavy penalty for invalid serve position
        
        # Action-specific validation requirements
        enhanced_confidence = self._apply_action_specific_validation_rules(
            enhanced_confidence, validation_results, action_type
        )
        
        return max(0.0, min(1.0, enhanced_confidence))
    
    def _determine_action_validity(
        self,
        validation_results: Dict[str, Any],
        action_type: VolleyballAction
    ) -> bool:
        """Determine if action should be considered valid based on validation results.
        
        Args:
            validation_results: Results from all validation modules
            action_type: Predicted action type
            
        Returns:
            True if action is valid
        """
        # Get validation results
        ball_contact = validation_results.get("ball_contact", {})
        temporal_contact = validation_results.get("temporal_contact", {})
        court_position = validation_results.get("court_position", {})
        serve_position = validation_results.get("serve_position", {})
        
        # ALL actions except UNKNOWN require ball contact/proximity
        if action_type != VolleyballAction.UNKNOWN:
            # Must have valid ball contact for ANY action
            if not ball_contact.get("valid", False):
                return False
            
            # Must have reasonable ball contact confidence
            ball_confidence = ball_contact.get("confidence", 0.0)
            min_contact_confidence = self.enhanced_validation_config.get("ball_contact", {}).get("min_contact_confidence", 0.7)
            if ball_confidence < min_contact_confidence:
                return False
            
            # Must have reasonable temporal validation in strict mode
            strict_mode = self.enhanced_validation_config.get("strict_mode", True)
            if strict_mode and temporal_contact:
                if not temporal_contact.get("valid", False):
                    return False
                if temporal_contact.get("confidence", 0.0) < 0.2:
                    return False
        
        # Special serve validation
        if action_type == VolleyballAction.SERVE:
            if serve_position and not serve_position.get("valid", True):
                return False
        
        # Court position validation
        if court_position and not court_position.get("valid", True):
            # Allow some flexibility unless confidence is very low
            if court_position.get("confidence", 1.0) < 0.2:
                return False
        
        # Block-specific validation (must be near net and have ball contact)
        if action_type == VolleyballAction.BLOCK:
            if court_position:
                region = court_position.get("details", {}).get("current_region", "")
                if region not in ["front_court", "unknown"]:
                    return False
        
        return True
    
    def _apply_action_specific_validation_rules(
        self,
        confidence: float,
        validation_results: Dict[str, Any],
        action_type: VolleyballAction
    ) -> float:
        """Apply action-specific validation rules to adjust confidence.
        
        Args:
            confidence: Current confidence score
            validation_results: Validation results
            action_type: Action type
            
        Returns:
            Adjusted confidence score
        """
        # Get relevant validation results
        ball_contact = validation_results.get("ball_contact", {})
        trajectory_validation = validation_results.get("trajectory_validation", {})
        court_position = validation_results.get("court_position", {})
        
        if action_type == VolleyballAction.DIG:
            # Digs require good ball contact and upward trajectory
            if ball_contact.get("valid", False):
                dig_details = ball_contact.get("details", {}).get("action_specific", {}).get("details", {})
                if dig_details.get("ball_height_appropriate", False):
                    confidence *= 1.1
            
            if trajectory_validation.get("upward_motion", False):
                confidence *= 1.1
        
        elif action_type == VolleyballAction.SET:
            # Sets require controlled ball contact and moderate trajectory
            if ball_contact.get("valid", False):
                set_details = ball_contact.get("details", {}).get("action_specific", {}).get("details", {})
                if set_details.get("ball_height_appropriate", False) and set_details.get("arms_raised", False):
                    confidence *= 1.2
            
            # Sets should have controlled, moderate velocity changes
            if trajectory_validation.get("controlled_velocity", False):
                confidence *= 1.2
            
            # Penalize sets with high velocity (more like spikes)
            if trajectory_validation.get("high_velocity", False):
                confidence *= 0.6
            
            # Penalize sets with strong downward motion (more like spikes)
            if trajectory_validation.get("downward_motion", False):
                confidence *= 0.7
        
        elif action_type == VolleyballAction.SPIKE:
            # Spikes require high ball contact and fast downward trajectory
            if ball_contact.get("valid", False):
                spike_details = ball_contact.get("details", {}).get("action_specific", {}).get("details", {})
                if spike_details.get("ball_height_appropriate", False) and spike_details.get("arm_extended_high", False):
                    confidence *= 1.3
            
            # Strong boost for spikes with high velocity and downward motion
            if trajectory_validation.get("high_velocity", False) and trajectory_validation.get("downward_motion", False):
                confidence *= 1.4
            elif trajectory_validation.get("high_velocity", False):
                confidence *= 1.2
            elif trajectory_validation.get("downward_motion", False):
                confidence *= 1.1
            
            # Penalize spikes with controlled velocity (more like sets)
            if trajectory_validation.get("controlled_velocity", False):
                confidence *= 0.5
            
            # Penalize spikes in back court
            if court_position.get("valid", False):
                region = court_position.get("details", {}).get("current_region", "")
                if region == "back_court":
                    confidence *= 0.6
        
        elif action_type == VolleyballAction.BLOCK:
            # Blocks require front court position and both arms raised
            if court_position.get("valid", False):
                region = court_position.get("details", {}).get("current_region", "")
                if region == "front_court":
                    confidence *= 1.3
                elif region in ["middle_court", "back_court"]:
                    confidence *= 0.4  # Heavy penalty for blocks away from net
            
            if ball_contact.get("valid", False):
                block_details = ball_contact.get("details", {}).get("action_specific", {}).get("details", {})
                if block_details.get("both_arms_raised", False):
                    confidence *= 1.2
            
            # Blocks should show ball deflection or minimal velocity change
            if trajectory_validation.get("velocity_reduction", False):
                confidence *= 1.2
            
            # Penalize blocks with high velocity changes (more like spikes)
            if trajectory_validation.get("high_velocity", False):
                confidence *= 0.7
            
            # Blocks typically show sudden velocity changes due to deflection
            if trajectory_validation.get("sudden_direction_change", False):
                confidence *= 1.1
        
        elif action_type == VolleyballAction.SERVE:
            # Serves require back court position and ball acceleration
            serve_position = validation_results.get("serve_position", {})
            if serve_position.get("valid", False):
                confidence *= 1.3
            
            if trajectory_validation.get("acceleration_detected", False):
                confidence *= 1.2
        
        return confidence
    
    def set_court_boundaries(self, court_boundaries: Dict[str, Any]) -> None:
        """Set court boundaries for position validation.
        
        Args:
            court_boundaries: Court boundary information
        """
        if self.court_validator:
            self.court_validator.set_court_boundaries(court_boundaries)
    
    def reset_enhanced_validation(self) -> None:
        """Reset all enhanced validation modules."""
        if self.temporal_validator:
            self.temporal_validator.reset_all_histories()
        
        if self.trajectory_analyzer:
            self.trajectory_analyzer.clear_history()
        
        if self.court_validator:
            self.court_validator.reset_court_boundaries()
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get statistics from validation modules.
        
        Returns:
            Validation statistics
        """
        stats = {
            "enhanced_validation_enabled": self.enhanced_validation_enabled
        }
        
        if self.temporal_validator:
            # Get player contact histories
            player_histories = {}
            for player_id in self.temporal_validator.player_histories:
                history = self.temporal_validator.get_player_contact_history(player_id)
                state = self.temporal_validator.get_player_state(player_id)
                player_histories[player_id] = {
                    "history_length": len(history) if history else 0,
                    "current_state": state.value if state else "unknown"
                }
            stats["temporal_validation"] = player_histories
        
        if self.trajectory_analyzer:
            trajectory_stats = {
                "trajectory_points": len(self.trajectory_analyzer.get_trajectory_history()),
                "detected_events": len(self.trajectory_analyzer.get_detected_events())
            }
            stats["trajectory_analysis"] = trajectory_stats
        
        if self.court_validator:
            court_stats = {
                "court_available": self.court_validator.is_court_available(),
                "regions_defined": len(self.court_validator.get_court_regions())
            }
            stats["court_validation"] = court_stats
        
        return stats
