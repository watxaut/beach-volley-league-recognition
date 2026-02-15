"""
Ball tracker for volleyball video analysis.

Conservative tracker: when the ball is lost, returns None instead of
hallucinating positions. Predictions are limited to a few frames and
validated against court bounds.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from collections import deque
import logging


class BallTracker:
    """Tracks a single volleyball across video frames.

    Design principles:
    - When ball is lost, return None (don't hallucinate).
    - Short prediction window (max 10 frames).
    - Higher confidence threshold (0.4) to avoid noise.
    - Small trajectory gap (60px) to avoid merging unrelated events.
    - Optional court bounds check to reject out-of-court predictions.
    """

    def __init__(
        self,
        max_missing_frames: int = 10,
        trajectory_smoothing: int = 5,
        velocity_threshold: float = 200.0,
        low_confidence_threshold: float = 0.4,
        max_trajectory_gap: float = 60.0,
        court_bounds: Optional[tuple] = None,
    ):
        """Initialize the ball tracker.

        Args:
            max_missing_frames: Max frames before returning None.
            trajectory_smoothing: Window size for position smoothing.
            velocity_threshold: Max velocity magnitude (px/frame).
            low_confidence_threshold: Min confidence to accept a detection.
            max_trajectory_gap: Max distance (px) for trajectory continuation.
            court_bounds: Optional (x1, y1, x2, y2) to reject out-of-bounds predictions.
        """
        self.max_missing_frames = max_missing_frames
        self.trajectory_smoothing = trajectory_smoothing
        self.velocity_threshold = velocity_threshold
        self.low_confidence_threshold = low_confidence_threshold
        self.max_trajectory_gap = max_trajectory_gap
        self.court_bounds = court_bounds

        # State
        self.trajectory: deque = deque(maxlen=120)
        self.velocities: deque = deque(maxlen=10)
        self.missing_count = 0
        self.last_position: Optional[List[float]] = None
        self.last_velocity: Optional[List[float]] = None

        self.logger = logging.getLogger(__name__)

    def set_court_bounds(self, bounds: tuple) -> None:
        """Set court bounds for out-of-bounds rejection.

        Args:
            bounds: (x1, y1, x2, y2) court bounding box.
        """
        self.court_bounds = bounds

    def update(self, detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Update tracker with new detections.

        Args:
            detections: Ball detections from current frame.

        Returns:
            Tracked ball dict or None if ball is lost.
        """
        if not detections:
            return self._handle_missing()

        # Pick best detection
        best = self._select_best(detections)
        if best is None:
            return self._handle_missing()

        return self._accept_detection(best)

    def _select_best(self, detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select the best detection, validated against trajectory."""
        candidates = []

        for det in detections:
            conf = det.get("confidence", 0.0)
            if conf < self.low_confidence_threshold:
                continue

            # If we have trajectory history, check distance from predicted position
            if self.last_position is not None:
                det_center = det["center"]
                dist = np.sqrt(
                    (det_center[0] - self.last_position[0]) ** 2
                    + (det_center[1] - self.last_position[1]) ** 2
                )
                # Allow larger gap if ball has been missing
                gap = self.max_trajectory_gap * (1 + self.missing_count * 0.5)
                if dist > gap:
                    continue

            candidates.append(det)

        if not candidates:
            return None

        # Return highest confidence
        return max(candidates, key=lambda d: d.get("confidence", 0.0))

    def _accept_detection(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """Accept a detection and update trajectory state."""
        center = detection["center"]

        # Compute velocity
        velocity = None
        if self.last_position is not None:
            vx = center[0] - self.last_position[0]
            vy = center[1] - self.last_position[1]
            mag = np.sqrt(vx ** 2 + vy ** 2)
            if mag <= self.velocity_threshold:
                velocity = [vx, vy]
                self.velocities.append(velocity)
                self.last_velocity = velocity

        self.trajectory.append(center)
        self.last_position = center
        self.missing_count = 0

        result = detection.copy()
        result.update({
            "velocity": velocity,
            "trajectory_length": len(self.trajectory),
            "smoothed_position": self._smoothed_position(),
            "ball_state": self._classify_state(),
            "is_predicted": False,
        })
        return result

    def _handle_missing(self) -> Optional[Dict[str, Any]]:
        """Handle frame with no valid detection."""
        self.missing_count += 1

        if self.missing_count > self.max_missing_frames:
            self._reset_tracker()
            return None

        # Conservative prediction: only if we have good velocity data
        if self.last_position is None or self.last_velocity is None:
            return None
        if len(self.trajectory) < 3:
            return None

        predicted = self._predict_position()
        if predicted is None:
            return None

        # Reject if outside court bounds
        if self.court_bounds is not None:
            x1, y1, x2, y2 = self.court_bounds
            margin = 50  # small margin
            if not (x1 - margin <= predicted[0] <= x2 + margin and
                    y1 - margin <= predicted[1] <= y2 + margin):
                return None

        confidence = max(0.05, 0.3 - 0.03 * self.missing_count)

        return {
            "center": predicted,
            "confidence": confidence,
            "bbox": self._estimate_bbox(predicted),
            "class_name": "sports_ball",
            "velocity": self.last_velocity,
            "trajectory_length": len(self.trajectory),
            "smoothed_position": predicted,
            "ball_state": "predicted",
            "is_predicted": True,
            "missing_frames": self.missing_count,
        }

    def _predict_position(self) -> Optional[List[float]]:
        """Predict next position using linear velocity."""
        if self.last_position is None or self.last_velocity is None:
            return None

        t = self.missing_count
        px = self.last_position[0] + self.last_velocity[0] * t
        py = self.last_position[1] + self.last_velocity[1] * t
        return [px, py]

    def _smoothed_position(self) -> List[float]:
        """Weighted average of recent positions."""
        if not self.trajectory:
            return [0.0, 0.0]
        recent = list(self.trajectory)[-self.trajectory_smoothing:]
        weights = np.linspace(0.5, 1.0, len(recent))
        weights /= weights.sum()
        sx = float(np.average([p[0] for p in recent], weights=weights))
        sy = float(np.average([p[1] for p in recent], weights=weights))
        return [sx, sy]

    def _classify_state(self) -> str:
        """Classify ball state from velocity."""
        if not self.last_velocity:
            return "unknown"
        vx, vy = self.last_velocity
        if abs(vy) < 2:
            return "horizontal"
        return "ascending" if vy < 0 else "descending"

    def _estimate_bbox(self, center: List[float], size: int = 20) -> List[float]:
        half = size // 2
        return [center[0] - half, center[1] - half, center[0] + half, center[1] + half]

    def _reset_tracker(self) -> None:
        """Reset all state."""
        self.trajectory.clear()
        self.velocities.clear()
        self.missing_count = 0
        self.last_position = None
        self.last_velocity = None
        self.logger.debug("Ball tracker reset")

    def reset(self) -> None:
        """Public reset method."""
        self._reset_tracker()

    def get_trajectory(self) -> List[List[float]]:
        """Get full trajectory."""
        return list(self.trajectory)

    def get_ball_statistics(self) -> Dict[str, Any]:
        """Get trajectory statistics."""
        if len(self.trajectory) < 2:
            return {}
        positions = np.array(self.trajectory)
        distances = np.sqrt(np.sum(np.diff(positions, axis=0) ** 2, axis=1))
        return {
            "total_distance": float(np.sum(distances)),
            "average_speed": float(np.mean(distances)),
            "max_speed": float(np.max(distances)),
            "trajectory_points": len(self.trajectory),
            "x_range": [float(positions[:, 0].min()), float(positions[:, 0].max())],
            "y_range": [float(positions[:, 1].min()), float(positions[:, 1].max())],
            "current_state": self._classify_state(),
        }
