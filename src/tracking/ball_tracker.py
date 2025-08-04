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
        velocity_threshold: float = 200.0,  # Much higher threshold for volleyball
        low_confidence_threshold: float = 0.15,  # Accept lower confidence with good trajectory
        trajectory_confidence_boost: float = 0.3,  # Boost confidence for consistent detections
        max_trajectory_gap: float = 150.0,  # Maximum distance for trajectory continuation
        velocity_consistency_weight: float = 0.4,  # Weight for velocity consistency
        acceleration_consistency_weight: float = 0.2,  # Weight for acceleration consistency
        trajectory_prediction_frames: int = 5,  # Frames to predict ahead
        fast_ball_velocity_threshold: float = 50.0  # Threshold for fast ball mode
    ):
        """Initialize the ball tracker.

        Args:
            max_missing_frames: Maximum frames ball can be missing before reset
            trajectory_smoothing: Number of frames to use for trajectory smoothing
            velocity_threshold: Maximum velocity change for trajectory validation
            low_confidence_threshold: Accept detections above this confidence if trajectory is good
            trajectory_confidence_boost: Amount to boost confidence for trajectory-consistent detections
            max_trajectory_gap: Maximum distance to consider trajectory continuation
            velocity_consistency_weight: Weight for velocity consistency in trajectory scoring
            acceleration_consistency_weight: Weight for acceleration consistency in trajectory scoring
            trajectory_prediction_frames: Number of frames to predict ahead for missing ball
            fast_ball_velocity_threshold: Velocity threshold to activate fast ball tracking mode
        """
        self.max_missing_frames = max_missing_frames
        self.trajectory_smoothing = trajectory_smoothing
        self.velocity_threshold = velocity_threshold
        self.low_confidence_threshold = low_confidence_threshold
        self.trajectory_confidence_boost = trajectory_confidence_boost
        self.max_trajectory_gap = max_trajectory_gap
        self.velocity_consistency_weight = velocity_consistency_weight
        self.acceleration_consistency_weight = acceleration_consistency_weight
        self.trajectory_prediction_frames = trajectory_prediction_frames
        self.fast_ball_velocity_threshold = fast_ball_velocity_threshold

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
        """Select the best ball detection from multiple candidates with trajectory-based scoring.

        Args:
            detections: List of ball detections

        Returns:
            Best detection or None, with enhanced confidence if trajectory is good
        """
        if not detections:
            return None
            
        if len(detections) == 1:
            detection = detections[0]
            # Boost confidence if detection follows good trajectory
            enhanced_detection = self._enhance_detection_confidence(detection)
            return enhanced_detection

        # Score all detections based on confidence + trajectory consistency
        scored_detections = []
        
        for detection in detections:
            # Start with base confidence
            base_confidence = detection.get("confidence", 0.0)
            
            # Calculate trajectory consistency score
            trajectory_score = self._calculate_trajectory_consistency(detection)
            
            # Combine confidence and trajectory score
            final_score = base_confidence + trajectory_score
            
            # Accept low confidence detections if trajectory is very good
            if (base_confidence < self.low_confidence_threshold and 
                trajectory_score > 0.2):  # Strong trajectory evidence
                final_score += self.trajectory_confidence_boost
                
            scored_detections.append((final_score, detection))

        # Return the highest scoring detection
        if scored_detections:
            best_score, best_detection = max(scored_detections, key=lambda x: x[0])
            
            # Enhance the confidence of the selected detection
            enhanced_detection = self._enhance_detection_confidence(best_detection)
            return enhanced_detection

        return None

    def _calculate_trajectory_consistency(self, detection: Dict[str, Any]) -> float:
        """Calculate how well a detection fits the current trajectory.

        Args:
            detection: Ball detection to evaluate

        Returns:
            Trajectory consistency score (0.0 to 1.0)
        """
        if len(self.trajectory) < 2:
            return 0.0

        center = detection["center"]
        score = 0.0
        
        # 1. Distance from predicted position
        predicted_position = self._predict_next_position()
        if predicted_position:
            distance = np.sqrt(
                (center[0] - predicted_position[0])**2 +
                (center[1] - predicted_position[1])**2
            )
            
            # Closer to prediction = better score
            distance_score = max(0, 1.0 - distance / self.max_trajectory_gap)
            score += distance_score * 0.4
        
        # 2. Velocity consistency
        if self.last_velocity and len(self.trajectory) >= 1:
            last_pos = self.trajectory[-1]
            current_velocity = [
                center[0] - last_pos[0],
                center[1] - last_pos[1]
            ]
            
            # Compare with expected velocity
            velocity_diff = np.sqrt(
                (current_velocity[0] - self.last_velocity[0])**2 +
                (current_velocity[1] - self.last_velocity[1])**2
            )
            
            velocity_score = max(0, 1.0 - velocity_diff / self.velocity_threshold)
            score += velocity_score * self.velocity_consistency_weight
        
        # 3. Acceleration consistency (if we have enough history)
        if self.last_acceleration and len(self.trajectory) >= 2:
            if len(self.velocities) >= 1:
                prev_velocity = self.velocities[-1]
                last_pos = self.trajectory[-1]
                current_velocity = [
                    center[0] - last_pos[0],
                    center[1] - last_pos[1]
                ]
                current_acceleration = [
                    current_velocity[0] - prev_velocity[0],
                    current_velocity[1] - prev_velocity[1]
                ]
                
                accel_diff = np.sqrt(
                    (current_acceleration[0] - self.last_acceleration[0])**2 +
                    (current_acceleration[1] - self.last_acceleration[1])**2
                )
                
                accel_score = max(0, 1.0 - accel_diff / (self.velocity_threshold * 2))
                score += accel_score * self.acceleration_consistency_weight
        
        return min(1.0, score)

    def _enhance_detection_confidence(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance detection confidence based on trajectory consistency.

        Args:
            detection: Original detection

        Returns:
            Detection with potentially boosted confidence
        """
        enhanced_detection = detection.copy()
        
        # Calculate trajectory consistency
        trajectory_score = self._calculate_trajectory_consistency(detection)
        
        # Boost confidence for trajectory-consistent detections
        original_confidence = detection.get("confidence", 0.0)
        
        if trajectory_score > 0.3:  # Good trajectory evidence
            confidence_boost = trajectory_score * self.trajectory_confidence_boost
            enhanced_confidence = min(1.0, original_confidence + confidence_boost)
            enhanced_detection["confidence"] = enhanced_confidence
            enhanced_detection["trajectory_boosted"] = True
            enhanced_detection["trajectory_score"] = trajectory_score
            
            self.logger.debug(f"Boosted confidence from {original_confidence:.3f} to {enhanced_confidence:.3f} "
                            f"(trajectory_score: {trajectory_score:.3f})")
        
        return enhanced_detection

    def _predict_next_position(self) -> Optional[List[float]]:
        """Predict next ball position based on trajectory with enhanced physics.

        Returns:
            Predicted [x, y] position or None
        """
        if len(self.trajectory) < 2:
            return None

        # Enhanced prediction using velocity and acceleration
        if self.last_velocity:
            last_pos = self.trajectory[-1]
            
            # Use acceleration if available for better prediction
            if self.last_acceleration and len(self.accelerations) > 0:
                # Physics-based prediction: pos = pos + velocity*t + 0.5*acceleration*t^2
                # For t=1 frame: pos = pos + velocity + 0.5*acceleration
                predicted_x = (last_pos[0] + self.last_velocity[0] + 
                              0.5 * self.last_acceleration[0])
                predicted_y = (last_pos[1] + self.last_velocity[1] + 
                              0.5 * self.last_acceleration[1])
            else:
                # Simple linear prediction
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
        """Handle frame where ball was not detected with enhanced prediction.

        Returns:
            Predicted ball info or None
        """
        self.missing_count += 1

        # If missing for too long, reset tracker
        if self.missing_count > self.max_missing_frames:
            self._reset_tracker()
            return None

        # Enhanced multi-frame prediction for fast balls
        predicted_position = self._predict_position_multiple_frames(self.missing_count)
        if predicted_position:
            # Calculate prediction confidence based on missing frames and trajectory quality
            prediction_confidence = max(0.1, 0.5 - 0.05 * self.missing_count)
            
            # Higher confidence if we have good velocity/acceleration data
            if (self.last_velocity and self.last_acceleration and 
                len(self.trajectory) > 5):
                prediction_confidence += 0.2
            
            return {
                "center": predicted_position,
                "confidence": prediction_confidence,
                "bbox": self._estimate_bbox(predicted_position),
                "class_name": "volleyball",
                "velocity": self._predict_velocity_for_frame(self.missing_count),
                "trajectory_length": len(self.trajectory),
                "smoothed_position": predicted_position,
                "ball_state": "predicted",
                "is_predicted": True,
                "missing_frames": self.missing_count,
                "prediction_method": "physics" if self.last_acceleration else "linear"
            }

        return None

    def _predict_position_multiple_frames(self, frames_ahead: int) -> Optional[List[float]]:
        """Predict ball position multiple frames ahead using physics.

        Args:
            frames_ahead: Number of frames to predict ahead

        Returns:
            Predicted [x, y] position or None
        """
        if len(self.trajectory) < 2 or not self.last_velocity:
            return None

        last_pos = self.trajectory[-1]
        
        if self.last_acceleration and len(self.accelerations) > 0:
            # Physics-based prediction: pos = pos + velocity*t + 0.5*acceleration*t^2
            t = frames_ahead
            predicted_x = (last_pos[0] + self.last_velocity[0] * t + 
                          0.5 * self.last_acceleration[0] * t * t)
            predicted_y = (last_pos[1] + self.last_velocity[1] * t + 
                          0.5 * self.last_acceleration[1] * t * t)
        else:
            # Linear prediction
            t = frames_ahead
            predicted_x = last_pos[0] + self.last_velocity[0] * t
            predicted_y = last_pos[1] + self.last_velocity[1] * t
        
        return [predicted_x, predicted_y]

    def _predict_velocity_for_frame(self, frames_ahead: int) -> Optional[List[float]]:
        """Predict velocity for a frame ahead.

        Args:
            frames_ahead: Number of frames ahead

        Returns:
            Predicted [vx, vy] velocity or None
        """
        if not self.last_velocity:
            return self.last_velocity

        if self.last_acceleration and len(self.accelerations) > 0:
            # velocity = initial_velocity + acceleration * time
            t = frames_ahead
            predicted_vx = self.last_velocity[0] + self.last_acceleration[0] * t
            predicted_vy = self.last_velocity[1] + self.last_acceleration[1] * t
            return [predicted_vx, predicted_vy]
        
        return self.last_velocity

    def _is_valid_velocity(self, velocity: List[float]) -> bool:
        """Check if velocity is reasonable with enhanced validation for fast balls.

        Args:
            velocity: [vx, vy] velocity vector

        Returns:
            True if velocity is valid
        """
        if not velocity:
            return False

        # Check velocity magnitude
        magnitude = np.sqrt(velocity[0]**2 + velocity[1]**2)

        # Adaptive velocity threshold for fast ball tracking
        adaptive_threshold = self.velocity_threshold
        
        # If ball is moving fast, be more lenient with velocity changes
        if magnitude > self.fast_ball_velocity_threshold:
            adaptive_threshold *= 1.5  # 50% more lenient for fast balls
            self.logger.debug(f"Fast ball detected (speed: {magnitude:.1f}), using adaptive threshold: {adaptive_threshold:.1f}")

        # Too fast movement is likely a detection error (but be more lenient)
        if magnitude > adaptive_threshold:
            return False

        # If we have velocity history, check for sudden changes
        if len(self.velocities) > 0:
            # Use recent velocities for better validation
            recent_velocities = list(self.velocities)[-5:]  # Last 5 velocities
            avg_velocity = np.mean(recent_velocities, axis=0)
            
            velocity_change = np.sqrt(
                (velocity[0] - avg_velocity[0])**2 +
                (velocity[1] - avg_velocity[1])**2
            )

            # More lenient threshold for velocity changes
            change_threshold = adaptive_threshold * 0.7  # Increased from 0.5
            
            if velocity_change > change_threshold:
                # Allow the change if it's consistent with recent trajectory trend
                if len(self.velocities) >= 3:
                    # Check if this is part of a consistent acceleration pattern
                    recent_changes = []
                    for i in range(min(3, len(self.velocities) - 1)):
                        v1 = self.velocities[-(i+2)]
                        v2 = self.velocities[-(i+1)]
                        change = np.sqrt((v2[0] - v1[0])**2 + (v2[1] - v1[1])**2)
                        recent_changes.append(change)
                    
                    avg_recent_change = np.mean(recent_changes)
                    
                    # If current change is similar to recent trend, allow it
                    if abs(velocity_change - avg_recent_change) < adaptive_threshold * 0.3:
                        self.logger.debug(f"Velocity change {velocity_change:.1f} allowed due to consistent trend")
                        return True
                
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
