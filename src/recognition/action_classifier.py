"""
Event-driven action classifier for beach volleyball.

Instead of classifying every player every frame, this classifier:
1. Detects ball trajectory inflection points (direction changes).
2. Finds the closest player at each inflection.
3. Classifies the action based on pose, court position, and ball direction.

Requires a CourtCalibration instance for spatial context (net position,
baseline, team zones).
"""

from typing import List, Dict, Any, Optional, Tuple
from collections import deque
import numpy as np
import logging

from .pose_estimator import PoseEstimator
from .volleyball_actions import VolleyballAction


class ActionClassifier:
    """Event-driven volleyball action classifier.

    Actions are only classified when the ball trajectory changes direction
    (inflection point), which corresponds to a ball contact event.
    """

    # Minimum frames between ball contacts to avoid double-counting
    MIN_CONTACT_GAP = 8

    def __init__(
        self,
        pose_estimator: PoseEstimator,
        temporal_window: int = 10,
        confidence_threshold: float = 0.4,
        court_calibration=None,
        # Accept but ignore legacy params
        enhanced_validation_config: Optional[Dict[str, Any]] = None,
    ):
        self.pose_estimator = pose_estimator
        self.temporal_window = temporal_window
        self.confidence_threshold = confidence_threshold
        self.court = court_calibration

        # Ball trajectory history: list of (frame_num, x, y)
        self._ball_history: deque = deque(maxlen=60)
        self._last_contact_frame: int = -100

        # Per-player pose history for temporal features
        self._player_pose_history: Dict[int, deque] = {}

        # Rally state
        self._rally_active = False
        self._rally_start_frame: Optional[int] = None

        self.logger = logging.getLogger(__name__)

    def set_court_calibration(self, court) -> None:
        """Set court calibration for spatial reasoning."""
        self.court = court

    def classify_actions(
        self,
        frame: np.ndarray,
        player_detections: List[Dict[str, Any]],
        ball_info: Optional[Dict[str, Any]] = None,
        frame_number: Optional[int] = None,
        court_info: Optional[Dict[str, Any]] = None,
        game_state_info: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Classify actions for the current frame.

        Returns a list of action dicts. Most frames return empty -- actions
        are only emitted at ball contact events (trajectory inflections).
        """
        if frame_number is None:
            frame_number = 0

        # Update ball history
        if ball_info and not ball_info.get("is_predicted", False):
            center = ball_info.get("center")
            if center and center[0] is not None:
                self._ball_history.append((frame_number, center[0], center[1]))

        # Estimate poses for all players
        poses = self.pose_estimator.estimate_poses_batch(frame, player_detections)

        # Store pose history per player
        for det, pose in zip(player_detections, poses):
            tid = det.get("track_id")
            if tid is None or pose is None:
                continue
            if tid not in self._player_pose_history:
                self._player_pose_history[tid] = deque(maxlen=self.temporal_window)
            self._player_pose_history[tid].append({
                "frame": frame_number,
                "pose": pose,
                "center": det["center"],
                "bbox": det["bbox"],
                "team": det.get("team"),
            })

        # Check for ball contact event (trajectory inflection)
        contact = self._detect_ball_contact(frame_number)
        if contact is None:
            return []

        # Find closest player to the contact point
        contact_point, ball_direction = contact
        closest = self._find_closest_player(contact_point, player_detections)
        if closest is None:
            return []

        det, pose, distance = closest

        # Classify the action
        action, confidence = self._classify_contact(
            det, pose, contact_point, ball_direction, frame_number
        )

        if action == VolleyballAction.UNKNOWN or confidence < self.confidence_threshold:
            return []

        self._last_contact_frame = frame_number

        return [{
            "track_id": det.get("track_id"),
            "action": action.value,
            "confidence": round(confidence, 3),
            "frame_number": frame_number,
            "contact_point": contact_point,
            "player_center": det["center"],
            "ball_direction": ball_direction,
            "team": det.get("team"),
        }]

    # --- Ball contact detection ---

    def _detect_ball_contact(
        self, current_frame: int
    ) -> Optional[Tuple[List[float], str]]:
        """Detect if a ball contact (trajectory inflection) happened.

        Returns:
            Tuple of (contact_point, ball_direction) or None.
            ball_direction: "up", "down", "left", "right"
        """
        if len(self._ball_history) < 5:
            return None

        # Don't detect contacts too close together
        if current_frame - self._last_contact_frame < self.MIN_CONTACT_GAP:
            return None

        # Look at the last few positions
        recent = list(self._ball_history)[-5:]
        frames = [r[0] for r in recent]
        xs = [r[1] for r in recent]
        ys = [r[2] for r in recent]

        # Check if frames are recent (within last 10 frames)
        if current_frame - frames[-1] > 5:
            return None

        # Check for vertical direction change (most common in volleyball)
        # vy before midpoint vs vy after midpoint
        mid = len(ys) // 2
        vy_before = ys[mid] - ys[0]  # positive = moving down
        vy_after = ys[-1] - ys[mid]  # positive = moving down

        # Direction change: sign flip in vertical velocity
        if vy_before * vy_after < 0 and (abs(vy_before) > 5 or abs(vy_after) > 5):
            contact_point = [xs[mid], ys[mid]]
            direction = "up" if vy_after < 0 else "down"
            return contact_point, direction

        # Check for horizontal direction change (less common but happens with blocks)
        vx_before = xs[mid] - xs[0]
        vx_after = xs[-1] - xs[mid]
        if vx_before * vx_after < 0 and (abs(vx_before) > 10 or abs(vx_after) > 10):
            contact_point = [xs[mid], ys[mid]]
            direction = "left" if vx_after < 0 else "right"
            return contact_point, direction

        return None

    def _find_closest_player(
        self,
        contact_point: List[float],
        player_detections: List[Dict[str, Any]],
        max_distance: float = 200.0,
    ) -> Optional[Tuple[Dict, Optional[Dict], float]]:
        """Find the player closest to the ball contact point.

        Returns:
            Tuple of (detection, pose_data, distance) or None.
        """
        best = None
        best_dist = float("inf")

        for det in player_detections:
            center = det.get("center", [0, 0])
            dist = np.sqrt(
                (center[0] - contact_point[0]) ** 2
                + (center[1] - contact_point[1]) ** 2
            )
            if dist < best_dist and dist < max_distance:
                best_dist = dist
                tid = det.get("track_id")
                pose = None
                if tid and tid in self._player_pose_history and self._player_pose_history[tid]:
                    pose = self._player_pose_history[tid][-1].get("pose")
                best = (det, pose, best_dist)

        return best

    # --- Action classification ---

    def _classify_contact(
        self,
        detection: Dict[str, Any],
        pose: Optional[Dict[str, Any]],
        contact_point: List[float],
        ball_direction: str,
        frame_number: int,
    ) -> Tuple[VolleyballAction, float]:
        """Classify what action the player performed at a ball contact.

        Uses tiered classification:
        - Tier 1 (spatial): serve, block - high accuracy
        - Tier 2 (pose+ball): dig, set, spike - moderate accuracy
        """
        player_center = detection.get("center", [0, 0])
        team = detection.get("team")

        # Extract pose features
        features = {}
        if pose and "pose_features" in pose:
            features = pose["pose_features"]

        # --- Tier 1: Spatial checks ---

        # SERVE: behind baseline + rally not active (or at rally start)
        if self.court and team:
            if self.court.is_behind_baseline((int(player_center[0]), int(player_center[1])), team):
                if not self._rally_active or frame_number == self._rally_start_frame:
                    self._rally_active = True
                    self._rally_start_frame = frame_number
                    return VolleyballAction.SERVE, 0.8

        # BLOCK: near net + arms above shoulders
        if self.court and self.court.is_near_net((int(player_center[0]), int(player_center[1])), threshold_px=100):
            avg_wrist = features.get("avg_wrist_height_ratio", 0)
            if avg_wrist > 1.0:  # wrists above shoulders
                return VolleyballAction.BLOCK, 0.7

        # Start rally if not started
        if not self._rally_active:
            self._rally_active = True
            self._rally_start_frame = frame_number

        # --- Tier 2: Pose + ball direction ---

        avg_wrist = features.get("avg_wrist_height_ratio", 0)
        wrist_diff = features.get("wrist_height_diff", 0)
        body_lean = features.get("body_lean", 0)

        # DIG: arms below shoulders + ball goes up from low position
        if ball_direction == "up" and avg_wrist < 0.5:
            confidence = 0.5
            if body_lean > 30:  # leaning forward
                confidence += 0.1
            return VolleyballAction.DIG, confidence

        # SET: both arms symmetric and high + ball goes up moderately
        if ball_direction == "up" and avg_wrist > 0.8 and wrist_diff < 0.3:
            return VolleyballAction.SET, 0.45

        # SPIKE: near net + one arm high + ball goes down
        if ball_direction == "down":
            near_net = False
            if self.court:
                near_net = self.court.is_near_net(
                    (int(player_center[0]), int(player_center[1])), threshold_px=150
                )
            if near_net and wrist_diff > 0.3 and avg_wrist > 0.6:
                return VolleyballAction.SPIKE, 0.45
            # Even without net proximity, asymmetric high arm + ball down suggests spike
            if wrist_diff > 0.4 and avg_wrist > 0.8:
                return VolleyballAction.SPIKE, 0.35

        # Fallback: if ball goes up with arms at mid height, likely a dig or set
        if ball_direction == "up":
            if avg_wrist < 0.8:
                return VolleyballAction.DIG, 0.35
            return VolleyballAction.SET, 0.3

        # Ball goes down but doesn't match spike criteria
        if ball_direction == "down":
            return VolleyballAction.SPIKE, 0.25

        return VolleyballAction.UNKNOWN, 0.0
