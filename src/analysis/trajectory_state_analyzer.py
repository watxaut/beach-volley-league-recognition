"""
Trajectory state analyzer for game state detection.

This module analyzes ball trajectory patterns to infer game state transitions,
serve detection, and point-ending events.
"""

from typing import List, Dict, Any, Optional, Tuple
from collections import deque
import numpy as np
import logging
import math

from .game_state import AnalysisResult


class TrajectoryStateAnalyzer:
    """Analyzes ball trajectory for game state indicators."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the trajectory state analyzer.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config.get("game_state_detection", {}).get("trajectory_analysis", {})
        self.logger = logging.getLogger(__name__)
        
        # Configuration parameters
        serve_features = self.config.get("serve_trajectory_features", {})
        self.min_arc_height = serve_features.get("min_arc_height", 50)
        self.horizontal_distance_threshold = serve_features.get("horizontal_distance_threshold", 200)
        self.velocity_pattern_weight = serve_features.get("velocity_pattern_weight", 0.7)
        
        point_end = self.config.get("point_end_detection", {})
        self.ground_contact_threshold = point_end.get("ground_contact_threshold", 20)
        self.out_of_bounds_margin = point_end.get("out_of_bounds_margin", 30)
        self.velocity_drop_threshold = point_end.get("velocity_drop_threshold", 0.3)
        
        # State tracking
        self.trajectory_history = deque(maxlen=60)  # ~2 seconds at 30fps
        self.velocity_history = deque(maxlen=30)
        self.acceleration_history = deque(maxlen=20)
        
        # Court boundaries (will be updated from court detector)
        self.court_bounds = None
        self.frame_height = 1080  # Default, will be updated
        self.frame_width = 1920   # Default, will be updated
    
    def analyze_frame(self, frame_result: Dict[str, Any], frame_number: int) -> AnalysisResult:
        """Analyze current frame for trajectory patterns.
        
        Args:
            frame_result: Frame processing results
            frame_number: Current frame number
            
        Returns:
            Analysis result with confidence scores
        """
        # Extract ball information
        ball_info = frame_result.get("tracked_ball")
        ball_position = None
        
        if ball_info and ball_info.get("center"):
            ball_position = ball_info["center"]
            if ball_position[0] is not None and ball_position[1] is not None:
                ball_position = tuple(ball_position)
            else:
                ball_position = None
        
        # Update trajectory history
        self._update_trajectory_history(ball_position, frame_number)
        
        # Analyze patterns
        confidence_scores = {
            "serve_trajectory": self._detect_serve_trajectory(),
            "attack_trajectory": self._detect_attack_trajectory(),
            "point_ending": self._detect_point_ending_trajectory(),
            "ball_in_play": self._detect_ball_in_play(),
            "trajectory_quality": self._assess_trajectory_quality()
        }
        
        metadata = {
            "trajectory_length": len(self.trajectory_history),
            "current_ball_position": ball_position,
            "velocity_available": len(self.velocity_history) > 0,
            "court_bounds_available": self.court_bounds is not None
        }
        
        return AnalysisResult(
            confidence_scores=confidence_scores,
            metadata=metadata
        )
    
    def _update_trajectory_history(self, ball_position: Optional[Tuple[float, float]], 
                                 frame_number: int) -> None:
        """Update trajectory tracking data.
        
        Args:
            ball_position: Current ball position (x, y) or None
            frame_number: Current frame number
        """
        trajectory_point = {
            "position": ball_position,
            "frame": frame_number,
            "timestamp": frame_number / 30.0  # Assume 30fps
        }
        
        self.trajectory_history.append(trajectory_point)
        
        # Calculate velocities if we have recent positions
        if len(self.trajectory_history) >= 2:
            self._calculate_velocity()
        
        # Calculate accelerations if we have recent velocities
        if len(self.velocity_history) >= 2:
            self._calculate_acceleration()
    
    def _calculate_velocity(self) -> None:
        """Calculate velocity from recent trajectory points."""
        if len(self.trajectory_history) < 2:
            return
        
        current = self.trajectory_history[-1]
        previous = self.trajectory_history[-2]
        
        if (current["position"] is None or previous["position"] is None):
            velocity = None
        else:
            dt = current["timestamp"] - previous["timestamp"]
            if dt > 0:
                dx = current["position"][0] - previous["position"][0]
                dy = current["position"][1] - previous["position"][1]
                speed = np.sqrt(dx**2 + dy**2) / dt
                velocity = {
                    "speed": speed,
                    "dx": dx / dt,
                    "dy": dy / dt,
                    "frame": current["frame"]
                }
            else:
                velocity = None
        
        self.velocity_history.append(velocity)
    
    def _calculate_acceleration(self) -> None:
        """Calculate acceleration from recent velocity data."""
        if len(self.velocity_history) < 2:
            return
        
        current_vel = self.velocity_history[-1]
        previous_vel = self.velocity_history[-2]
        
        if current_vel is None or previous_vel is None:
            acceleration = None
        else:
            dt = 1.0 / 30.0  # Frame time at 30fps
            
            # Calculate acceleration components
            ax = (current_vel["dx"] - previous_vel["dx"]) / dt
            ay = (current_vel["dy"] - previous_vel["dy"]) / dt
            
            acceleration = {
                "ax": ax,
                "ay": ay,
                "magnitude": np.sqrt(ax**2 + ay**2),
                "frame": current_vel["frame"]
            }
        
        self.acceleration_history.append(acceleration)
    
    def _detect_serve_trajectory(self) -> float:
        """Detect serve trajectory patterns.
        
        Returns:
            Confidence score for serve trajectory (0.0 to 1.0)
        """
        if len(self.trajectory_history) < 10:  # Need sufficient history
            return 0.0
        
        # Get valid trajectory points
        valid_points = [
            point for point in self.trajectory_history
            if point["position"] is not None
        ]
        
        if len(valid_points) < 5:
            return 0.0
        
        confidence = 0.0
        
        # Feature 1: High initial arc (serves start high)
        if len(valid_points) >= 3:
            start_y = valid_points[0]["position"][1]
            mid_y = valid_points[len(valid_points)//2]["position"][1]
            
            # Serve should start relatively high and go up initially
            if start_y > self.frame_height * 0.6:  # Lower part of frame (high in court)
                confidence += 0.3
            
            # Check for upward initial motion
            if len(valid_points) >= 2:
                initial_dy = valid_points[1]["position"][1] - valid_points[0]["position"][1]
                if initial_dy < -20:  # Moving up (negative y direction)
                    confidence += 0.2
        
        # Feature 2: Significant horizontal distance
        if len(valid_points) >= 2:
            horizontal_distance = abs(
                valid_points[-1]["position"][0] - valid_points[0]["position"][0]
            )
            if horizontal_distance > self.horizontal_distance_threshold:
                confidence += 0.3
        
        # Feature 3: Velocity pattern analysis
        velocity_confidence = self._analyze_serve_velocity_pattern()
        confidence += velocity_confidence * self.velocity_pattern_weight
        
        return min(confidence, 1.0)
    
    def _analyze_serve_velocity_pattern(self) -> float:
        """Analyze velocity pattern for serve characteristics.
        
        Returns:
            Confidence score based on velocity pattern (0.0 to 1.0)
        """
        if len(self.velocity_history) < 5:
            return 0.0
        
        valid_velocities = [v for v in self.velocity_history if v is not None]
        if len(valid_velocities) < 3:
            return 0.0
        
        speeds = [v["speed"] for v in valid_velocities]
        
        # Serve typically has: moderate start, acceleration, then deceleration
        confidence = 0.0
        
        # Check for reasonable speed range
        max_speed = max(speeds)
        if 100 < max_speed < 800:  # Reasonable ball speed range
            confidence += 0.3
        
        # Check for speed variation (acceleration/deceleration)
        speed_variation = np.std(speeds)
        if speed_variation > 20:  # Some variation expected
            confidence += 0.2
        
        return confidence
    
    def _detect_attack_trajectory(self) -> float:
        """Detect attack/spike trajectory patterns.
        
        Returns:
            Confidence score for attack trajectory (0.0 to 1.0)
        """
        if len(self.velocity_history) < 3:
            return 0.0
        
        valid_velocities = [v for v in self.velocity_history if v is not None]
        if len(valid_velocities) < 2:
            return 0.0
        
        confidence = 0.0
        
        # Feature 1: High speed
        recent_speeds = [v["speed"] for v in valid_velocities[-3:]]
        max_recent_speed = max(recent_speeds)
        
        if max_recent_speed > 200:  # Fast attack
            confidence += 0.4
        elif max_recent_speed > 100:
            confidence += 0.2
        
        # Feature 2: Downward motion
        recent_dy = [v["dy"] for v in valid_velocities[-2:]]
        if recent_dy and max(recent_dy) > 50:  # Strong downward motion
            confidence += 0.4
        
        # Feature 3: Sudden acceleration
        if len(self.acceleration_history) >= 2:
            acceleration_list = list(self.acceleration_history)
            recent_accelerations = [
                a for a in acceleration_list[-2:]
                if a is not None
            ]
            if recent_accelerations:
                max_accel = max(a["magnitude"] for a in recent_accelerations)
                if max_accel > 500:  # High acceleration
                    confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _detect_point_ending_trajectory(self) -> float:
        """Detect trajectory patterns that indicate point ending.
        
        Returns:
            Confidence score for point ending (0.0 to 1.0)
        """
        if len(self.trajectory_history) < 3:
            return 0.0
        
        # Get recent trajectory points
        recent_points = [
            point for point in list(self.trajectory_history)[-5:]
            if point["position"] is not None
        ]
        
        if len(recent_points) < 2:
            return 0.0
        
        confidence = 0.0
        
        # Feature 1: Ball near ground level
        latest_position = recent_points[-1]["position"]
        if latest_position[1] > self.frame_height * 0.85:  # Near bottom of frame
            confidence += 0.5
        
        # Feature 2: Ball trajectory going out of bounds
        if self.court_bounds is not None:
            out_of_bounds_confidence = self._check_out_of_bounds(recent_points)
            confidence += out_of_bounds_confidence * 0.4
        
        # Feature 3: Sudden velocity drop (ball hitting something)
        if len(self.velocity_history) >= 3:
            recent_velocities = [
                v for v in list(self.velocity_history)[-3:]
                if v is not None
            ]
            
            if len(recent_velocities) >= 2:
                speed_drop = (recent_velocities[-2]["speed"] - 
                            recent_velocities[-1]["speed"])
                relative_drop = speed_drop / recent_velocities[-2]["speed"]
                
                if relative_drop > self.velocity_drop_threshold:
                    confidence += 0.3
        
        return min(confidence, 1.0)
    
    def _check_out_of_bounds(self, trajectory_points: List[Dict]) -> float:
        """Check if trajectory indicates ball going out of bounds.
        
        Args:
            trajectory_points: Recent trajectory points
            
        Returns:
            Confidence score for out of bounds (0.0 to 1.0)
        """
        if not self.court_bounds or len(trajectory_points) < 2:
            return 0.0
        
        latest_position = trajectory_points[-1]["position"]
        
        # Simple boundary check (this would be enhanced with actual court detection)
        court_left = self.court_bounds.get("left", 0)
        court_right = self.court_bounds.get("right", self.frame_width)
        court_top = self.court_bounds.get("top", 0)
        court_bottom = self.court_bounds.get("bottom", self.frame_height)
        
        # Check if ball is outside court boundaries with margin
        if (latest_position[0] < court_left - self.out_of_bounds_margin or
            latest_position[0] > court_right + self.out_of_bounds_margin or
            latest_position[1] < court_top - self.out_of_bounds_margin or
            latest_position[1] > court_bottom + self.out_of_bounds_margin):
            return 0.8
        
        return 0.0
    
    def _detect_ball_in_play(self) -> float:
        """Detect if ball is currently in active play.
        
        Returns:
            Confidence score for ball in play (0.0 to 1.0)
        """
        if len(self.trajectory_history) < 3:
            return 0.0
        
        # Check recent ball tracking quality
        recent_points = list(self.trajectory_history)[-10:]
        valid_points = [p for p in recent_points if p["position"] is not None]
        
        if len(recent_points) == 0:
            return 0.0
        
        tracking_ratio = len(valid_points) / len(recent_points)
        
        # Ball in play if good tracking and reasonable movement
        confidence = tracking_ratio * 0.6
        
        # Boost confidence if ball is moving
        if len(self.velocity_history) > 0:
            recent_velocities = [v for v in list(self.velocity_history)[-3:] if v is not None]
            if recent_velocities:
                avg_speed = np.mean([v["speed"] for v in recent_velocities])
                if avg_speed > 10:  # Ball is moving
                    confidence += 0.4
        
        return min(confidence, 1.0)
    
    def _assess_trajectory_quality(self) -> float:
        """Assess the quality of trajectory tracking.
        
        Returns:
            Quality score (0.0 to 1.0)
        """
        if len(self.trajectory_history) < 5:
            return 0.0
        
        recent_points = list(self.trajectory_history)[-10:]
        valid_points = [p for p in recent_points if p["position"] is not None]
        
        if len(recent_points) == 0:
            return 0.0
        
        # Quality based on tracking consistency
        tracking_ratio = len(valid_points) / len(recent_points)
        
        return tracking_ratio
    
    def set_court_boundaries(self, court_bounds: Dict[str, float]) -> None:
        """Set court boundary information.
        
        Args:
            court_bounds: Dictionary with court boundary coordinates
        """
        self.court_bounds = court_bounds
        self.logger.debug(f"Updated court boundaries: {court_bounds}")
    
    def set_frame_dimensions(self, width: int, height: int) -> None:
        """Set video frame dimensions.
        
        Args:
            width: Frame width in pixels
            height: Frame height in pixels
        """
        self.frame_width = width
        self.frame_height = height
        self.logger.debug(f"Updated frame dimensions: {width}x{height}")
    
    def reset(self) -> None:
        """Reset analyzer state."""
        self.trajectory_history.clear()
        self.velocity_history.clear()
        self.acceleration_history.clear()
        self.logger.info("Trajectory state analyzer reset")
    
    def get_current_trajectory(self) -> List[Optional[Tuple[float, float]]]:
        """Get current trajectory positions.
        
        Returns:
            List of recent ball positions
        """
        return [point["position"] for point in self.trajectory_history]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get analyzer statistics.
        
        Returns:
            Statistics dictionary
        """
        valid_trajectory_points = [
            p for p in self.trajectory_history if p["position"] is not None
        ]
        valid_velocities = [v for v in self.velocity_history if v is not None]
        
        stats = {
            "trajectory_points": len(self.trajectory_history),
            "valid_trajectory_points": len(valid_trajectory_points),
            "velocity_points": len(valid_velocities),
            "tracking_quality": len(valid_trajectory_points) / max(len(self.trajectory_history), 1)
        }
        
        if valid_velocities:
            speeds = [v["speed"] for v in valid_velocities]
            stats.update({
                "avg_speed": np.mean(speeds),
                "max_speed": np.max(speeds),
                "speed_variation": np.std(speeds)
            })
        
        return stats