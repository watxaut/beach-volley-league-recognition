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


class VolleyballAction(Enum):
    """Enumeration of volleyball actions to recognize."""
    DIG = "dig"
    SET = "set"
    SPIKE = "spike"
    BLOCK = "block"
    ACE = "ace"
    SERVE = "serve"
    UNKNOWN = "unknown"


class ActionClassifier:
    """Classifier for volleyball actions using pose and context data.

    Recognizes volleyball-specific actions (digs, sets, blocks, aces, spikes)
    based on player pose, ball trajectory, and temporal context.
    """

    def __init__(
        self,
        pose_estimator: PoseEstimator,
        temporal_window: int = 10,
        confidence_threshold: float = 0.6
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

        self.logger = logging.getLogger(__name__)

        # Action classification rules
        self._initialize_action_rules()

    def classify_actions(
        self,
        frame: np.ndarray,
        player_detections: List[Dict[str, Any]],
        ball_info: Optional[Dict[str, Any]] = None
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

            # Classify action for this player
            action_result = self._classify_player_action(track_id, frame_index=None)

            if action_result:
                action_result.update({
                    "track_id": track_id,
                    "bbox": detection["bbox"],
                    "frame_pose": pose_data
                })
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

        # High arm position
        left_arm_height = features.get("left_arm_height", 500)
        right_arm_height = features.get("right_arm_height", 500)
        avg_arm_height = (left_arm_height + right_arm_height) / 2

        if avg_arm_height < 200:  # Arms high
            score += 0.4

        # Ball overhead
        ball_relative_height = features.get("ball_relative_height", 0.5)
        if ball_relative_height < 0.3:
            score += 0.3

        # Ball interaction
        if features.get("ball_in_reach", False):
            score += 0.3

        return min(score, 1.0)

    def _score_spike_action(self, features: Dict[str, Any]) -> float:
        """Score spike action based on features."""
        score = 0.0

        # One arm very high (spiking arm)
        left_arm_height = features.get("left_arm_height", 500)
        right_arm_height = features.get("right_arm_height", 500)
        max_arm_height = min(left_arm_height, right_arm_height)

        if max_arm_height < 150:  # Very high arm
            score += 0.4

        # High movement speed (jumping)
        movement_speed = features.get("max_movement_speed", 0)
        if movement_speed > 10:
            score += 0.2

        # Ball interaction high
        ball_relative_height = features.get("ball_relative_height", 0.5)
        if ball_relative_height < 0.2:
            score += 0.2

        # Court position (usually front/middle)
        court_region = features.get("court_region", "")
        if court_region in ["front", "middle"]:
            score += 0.2

        return min(score, 1.0)

    def _score_block_action(self, features: Dict[str, Any]) -> float:
        """Score block action based on features."""
        score = 0.0

        # Both arms high
        left_arm_height = features.get("left_arm_height", 500)
        right_arm_height = features.get("right_arm_height", 500)

        if left_arm_height < 200 and right_arm_height < 200:
            score += 0.4

        # High movement (jumping)
        movement_speed = features.get("max_movement_speed", 0)
        if movement_speed > 8:
            score += 0.2

        # Front court position
        court_region = features.get("court_region", "")
        if court_region == "front":
            score += 0.4

        return min(score, 1.0)

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
