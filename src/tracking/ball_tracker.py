"""
Ball tracker for volleyball video analysis.

This module implements ball tracking across video frames,
maintaining ball trajectory and handling temporary occlusions.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2
from collections import deque
import logging


class BallTracker:
    """Tracker for volleyball ball across video frames.

    Maintains ball trajectory and handles cases where the ball
    is temporarily occluded or not detected.
    """

    def __init__(
        self,
        max_missing_frames: int = 30,  # Increased from 10 - volleyball can be fast
        trajectory_smoothing: int = 8,  # Increased smoothing window
        velocity_threshold: float = 200.0  # Much higher threshold for volleyball
    ):
        """Initialize the ball tracker.

        Args:
            max_missing_frames: Maximum frames ball can be missing before reset
            trajectory_smoothing: Number of frames to use for trajectory smoothing
            velocity_threshold: Maximum velocity change for trajectory validation
        """
        self.max_missing_frames = max_missing_frames
        self.trajectory_smoothing = trajectory_smoothing
        self.velocity_threshold = velocity_threshold

        # Enhanced tracking state for volleyball
        self.trajectory = deque(maxlen=200)  # Increased to store longer trajectory
        self.velocities = deque(maxlen=20)   # Store more velocity history
        self.accelerations = deque(maxlen=10)  # Track acceleration for better prediction
        self.missing_count = 0
        self.last_position = None
        self.last_velocity = None
        self.last_acceleration = None
        self.confidence_history = deque(maxlen=10)  # Track detection confidence

        self.logger = logging.getLogger(__name__)

    def update(self, detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Update tracker with new ball detections.

        Args:
            detections: List of ball detections from current frame

        Returns:
            Tracked ball with trajectory info, or None if no valid ball
        """
        if not detections:
            return self._handle_missing_ball()

        # Select best detection if multiple balls detected
        best_detection = self._select_best_detection(detections)

        if best_detection is None:
            return self._handle_missing_ball()

        return self._update_trajectory(best_detection)

    def _select_best_detection(self, detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select the best ball detection from multiple candidates.

        Args:
            detections: List of ball detections

        Returns:
            Best detection or None
        """
        if len(detections) == 1:
            return detections[0]

        # If we have trajectory history, select detection closest to predicted position
        if len(self.trajectory) >= 2:
            predicted_position = self._predict_next_position()
            if predicted_position:
                best_detection = None
                min_distance = float('inf')

                for detection in detections:
                    center = detection["center"]
                    distance = np.sqrt(
                        (center[0] - predicted_position[0])**2 +
                        (center[1] - predicted_position[1])**2
                    )

                    if distance < min_distance:
                        min_distance = distance
                        best_detection = detection

                return best_detection

        # Otherwise, select detection with highest confidence
        return max(detections, key=lambda x: x["confidence"])

    def _predict_next_position(self) -> Optional[List[float]]:
        """Predict next ball position based on trajectory.

        Returns:
            Predicted [x, y] position or None
        """
        if len(self.trajectory) < 2:
            return None

        # Simple linear prediction based on last velocity
        if self.last_velocity:
            last_pos = self.trajectory[-1]
            predicted_x = last_pos[0] + self.last_velocity[0]
            predicted_y = last_pos[1] + self.last_velocity[1]
            return [predicted_x, predicted_y]

        return None

    def _update_trajectory(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """Update trajectory with new detection.

        Args:
            detection: Ball detection to add to trajectory

        Returns:
            Enhanced detection with trajectory information
        """
        center = detection["center"]

        # Calculate velocity if we have previous position
        velocity = None
        if self.last_position:
            velocity = [
                center[0] - self.last_position[0],
                center[1] - self.last_position[1]
            ]

            # Validate velocity (check for sudden jumps)
            if self._is_valid_velocity(velocity):
                self.velocities.append(velocity)
                self.last_velocity = velocity
            else:
                self.logger.debug(f"Invalid velocity detected: {velocity}")

        # Calculate acceleration if we have previous velocity
        acceleration = None
        if self.last_velocity and velocity:
            acceleration = [
                velocity[0] - self.last_velocity[0],
                velocity[1] - self.last_velocity[1]
            ]

            # Validate acceleration (check for sudden spikes)
            if self._is_valid_acceleration(acceleration):
                self.accelerations.append(acceleration)
                self.last_acceleration = acceleration
            else:
                self.logger.debug(f"Invalid acceleration detected: {acceleration}")

        # Add to trajectory
        self.trajectory.append(center)
        self.last_position = center
        self.missing_count = 0

        # Enhance detection with trajectory info
        enhanced_detection = detection.copy()
        enhanced_detection.update({
            "velocity": velocity,
            "acceleration": acceleration,
            "trajectory_length": len(self.trajectory),
            "smoothed_position": self._get_smoothed_position(),
            "ball_state": self._classify_ball_state()
        })

        return enhanced_detection

    def _handle_missing_ball(self) -> Optional[Dict[str, Any]]:
        """Handle frame where ball was not detected.

        Returns:
            Predicted ball info or None
        """
        self.missing_count += 1

        # If missing for too long, reset tracker
        if self.missing_count > self.max_missing_frames:
            self._reset_tracker()
            return None

        # Try to predict ball position
        predicted_position = self._predict_next_position()
        if predicted_position:
            return {
                "center": predicted_position,
                "confidence": 0.0,  # Low confidence for predicted position
                "bbox": self._estimate_bbox(predicted_position),
                "class_name": "volleyball",
                "velocity": self.last_velocity,
                "trajectory_length": len(self.trajectory),
                "smoothed_position": predicted_position,
                "ball_state": "predicted",
                "is_predicted": True
            }

        return None

    def _is_valid_velocity(self, velocity: List[float]) -> bool:
        """Check if velocity is reasonable.

        Args:
            velocity: [vx, vy] velocity vector

        Returns:
            True if velocity is valid
        """
        if not velocity:
            return False

        # Check velocity magnitude
        magnitude = np.sqrt(velocity[0]**2 + velocity[1]**2)

        # Too fast movement is likely a detection error
        if magnitude > self.velocity_threshold:
            return False

        # If we have velocity history, check for sudden changes
        if len(self.velocities) > 0:
            avg_velocity = np.mean(self.velocities, axis=0)
            velocity_change = np.sqrt(
                (velocity[0] - avg_velocity[0])**2 +
                (velocity[1] - avg_velocity[1])**2
            )

            # Sudden velocity changes might indicate detection errors
            if velocity_change > self.velocity_threshold * 0.5:
                return False

        return True

    def _is_valid_acceleration(self, acceleration: List[float]) -> bool:
        """Check if acceleration is reasonable.

        Args:
            acceleration: [ax, ay] acceleration vector

        Returns:
            True if acceleration is valid
        """
        if not acceleration:
            return False

        # Check acceleration magnitude
        magnitude = np.sqrt(acceleration[0]**2 + acceleration[1]**2)

        # Too high acceleration is likely a detection error
        if magnitude > self.velocity_threshold * 2:  # Higher threshold for acceleration
            return False

        # If we have acceleration history, check for sudden changes
        if len(self.accelerations) > 0:
            avg_acceleration = np.mean(self.accelerations, axis=0)
            acceleration_change = np.sqrt(
                (acceleration[0] - avg_acceleration[0])**2 +
                (acceleration[1] - avg_acceleration[1])**2
            )

            # Sudden acceleration changes might indicate detection errors
            if acceleration_change > self.velocity_threshold:
                return False

        return True

    def _get_smoothed_position(self) -> List[float]:
        """Get smoothed ball position using recent trajectory.

        Returns:
            Smoothed [x, y] position
        """
        if len(self.trajectory) == 0:
            return [0, 0]

        if len(self.trajectory) == 1:
            return list(self.trajectory[-1])

        # Use weighted average of recent positions
        recent_positions = list(self.trajectory)[-self.trajectory_smoothing:]
        weights = np.linspace(0.5, 1.0, len(recent_positions))
        weights = weights / weights.sum()

        smoothed_x = np.average([pos[0] for pos in recent_positions], weights=weights)
        smoothed_y = np.average([pos[1] for pos in recent_positions], weights=weights)

        return [float(smoothed_x), float(smoothed_y)]

    def _classify_ball_state(self) -> str:
        """Classify current ball state based on trajectory.

        Returns:
            Ball state: "ascending", "descending", "horizontal", "stationary"
        """
        if len(self.trajectory) < 2:
            return "unknown"

        if not self.last_velocity:
            return "stationary"

        vx, vy = self.last_velocity

        # Classify based on vertical velocity
        if abs(vy) < 2:  # Minimal vertical movement
            return "horizontal"
        elif vy < 0:  # Moving up (negative y is up in image coordinates)
            return "ascending"
        else:  # Moving down
            return "descending"

    def _estimate_bbox(self, center: List[float], size: int = 20) -> List[float]:
        """Estimate bounding box for predicted ball position.

        Args:
            center: Ball center position
            size: Estimated ball size in pixels

        Returns:
            Bounding box [x1, y1, x2, y2]
        """
        x, y = center
        half_size = size // 2
        return [
            x - half_size,
            y - half_size,
            x + half_size,
            y + half_size
        ]

    def _reset_tracker(self) -> None:
        """Reset tracker state."""
        self.trajectory.clear()
        self.velocities.clear()
        self.accelerations.clear()
        self.missing_count = 0
        self.last_position = None
        self.last_velocity = None
        self.last_acceleration = None
        self.logger.debug("Ball tracker reset")

    def get_trajectory(self) -> List[List[float]]:
        """Get complete ball trajectory.

        Returns:
            List of [x, y] positions
        """
        return list(self.trajectory)

    def get_ball_statistics(self) -> Dict[str, Any]:
        """Get ball movement statistics.

        Returns:
            Dictionary with trajectory statistics
        """
        if len(self.trajectory) < 2:
            return {}

        positions = np.array(self.trajectory)

        # Calculate path length
        distances = np.sqrt(np.sum(np.diff(positions, axis=0)**2, axis=1))
        total_distance = np.sum(distances)

        # Calculate speed statistics
        speeds = distances  # Speed per frame
        avg_speed = np.mean(speeds) if len(speeds) > 0 else 0
        max_speed = np.max(speeds) if len(speeds) > 0 else 0

        # Calculate trajectory bounds
        x_coords = positions[:, 0]
        y_coords = positions[:, 1]

        return {
            "total_distance": float(total_distance),
            "average_speed": float(avg_speed),
            "max_speed": float(max_speed),
            "trajectory_points": len(self.trajectory),
            "x_range": [float(np.min(x_coords)), float(np.max(x_coords))],
            "y_range": [float(np.min(y_coords)), float(np.max(y_coords))],
            "current_state": self._classify_ball_state()
        }
