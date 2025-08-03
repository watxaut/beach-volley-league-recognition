"""
Ball trajectory analysis for volleyball action recognition.

This module analyzes ball trajectory patterns to detect contact events
and validate that ball behavior matches expected action outcomes.
"""

from typing import Dict, Any, List, Optional, Tuple
from collections import deque
import numpy as np
import logging
from dataclasses import dataclass
from enum import Enum

from .volleyball_actions import VolleyballAction


@dataclass
class TrajectoryPoint:
    """Represents a single point in ball trajectory."""
    position: Tuple[float, float]
    velocity: Tuple[float, float]
    timestamp: float
    frame_number: int


class TrajectoryEvent(Enum):
    """Types of trajectory events that can be detected."""
    CONTACT_DETECTED = "contact_detected"
    DIRECTION_CHANGE = "direction_change"
    VELOCITY_SPIKE = "velocity_spike"
    TRAJECTORY_BREAK = "trajectory_break"
    BOUNCE_DETECTED = "bounce_detected"


class BallTrajectoryAnalyzer:
    """Analyzes ball trajectory patterns for contact detection and validation."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the ball trajectory analyzer.
        
        Args:
            config: Configuration dictionary with analysis parameters
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Trajectory analysis parameters
        self.trajectory_window = self.config.get("trajectory_window", 10)
        self.min_velocity_change = self.config.get("min_velocity_change", 50.0)  # pixels/frame
        self.min_direction_change = self.config.get("min_direction_change", 30.0)  # degrees
        self.velocity_spike_threshold = self.config.get("velocity_spike_threshold", 2.0)  # multiplier
        self.smoothing_window = self.config.get("smoothing_window", 3)
        
        # Trajectory history
        self.trajectory_history: deque = deque(maxlen=self.trajectory_window)
        self.detected_events: List[Dict[str, Any]] = []
        
        # Physics validation parameters
        self.gravity_acceleration = self.config.get("gravity_acceleration", 9.8)  # pixels/frame^2
        self.air_resistance_factor = self.config.get("air_resistance_factor", 0.98)
        self.bounce_energy_loss = self.config.get("bounce_energy_loss", 0.7)
        
    def analyze_trajectory(
        self,
        ball_data: Dict[str, Any],
        frame_number: int,
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """Analyze ball trajectory and detect significant events.
        
        Args:
            ball_data: Current ball tracking data
            frame_number: Current frame number
            timestamp: Frame timestamp
            
        Returns:
            Trajectory analysis results
        """
        if not ball_data or "center" not in ball_data:
            return self._create_analysis_result(False, "No ball data available")
        
        # Create trajectory point
        trajectory_point = self._create_trajectory_point(
            ball_data, frame_number, timestamp
        )
        
        if not trajectory_point:
            return self._create_analysis_result(False, "Invalid trajectory point")
        
        # Add to history
        self.trajectory_history.append(trajectory_point)
        
        # Need at least 3 points for meaningful analysis
        if len(self.trajectory_history) < 3:
            return self._create_analysis_result(
                True, "Collecting trajectory data", 
                {"points_collected": len(self.trajectory_history)}
            )
        
        # Analyze trajectory patterns
        analysis_results = {}
        
        # Detect contact events
        contact_detection = self._detect_contact_events()
        analysis_results["contact_detection"] = contact_detection
        
        # Analyze velocity patterns
        velocity_analysis = self._analyze_velocity_patterns()
        analysis_results["velocity_analysis"] = velocity_analysis
        
        # Analyze direction changes
        direction_analysis = self._analyze_direction_changes()
        analysis_results["direction_analysis"] = direction_analysis
        
        # Physics validation
        physics_validation = self._validate_trajectory_physics()
        analysis_results["physics_validation"] = physics_validation
        
        # Detect trajectory events
        events = self._detect_trajectory_events(analysis_results)
        analysis_results["events"] = events
        
        return self._create_analysis_result(
            True, "Trajectory analysis completed", analysis_results
        )
    
    def validate_action_trajectory(
        self,
        action_type: VolleyballAction,
        trajectory_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate that trajectory matches expected patterns for action type.
        
        Args:
            action_type: Volleyball action type
            trajectory_analysis: Results from trajectory analysis
            
        Returns:
            Action-specific trajectory validation results
        """
        if action_type == VolleyballAction.DIG:
            return self._validate_dig_trajectory(trajectory_analysis)
        elif action_type == VolleyballAction.SET:
            return self._validate_set_trajectory(trajectory_analysis)
        elif action_type == VolleyballAction.SPIKE:
            return self._validate_spike_trajectory(trajectory_analysis)
        elif action_type == VolleyballAction.BLOCK:
            return self._validate_block_trajectory(trajectory_analysis)
        elif action_type == VolleyballAction.SERVE:
            return self._validate_serve_trajectory(trajectory_analysis)
        else:
            return {"valid": False, "message": f"Unknown action type: {action_type}"}
    
    def _create_trajectory_point(
        self,
        ball_data: Dict[str, Any],
        frame_number: int,
        timestamp: Optional[float]
    ) -> Optional[TrajectoryPoint]:
        """Create trajectory point from ball data.
        
        Args:
            ball_data: Ball tracking data
            frame_number: Frame number
            timestamp: Timestamp
            
        Returns:
            TrajectoryPoint or None if data is invalid
        """
        center = ball_data.get("center")
        if not center or len(center) != 2:
            return None
        
        # Calculate velocity from position history
        velocity = self._calculate_velocity(center)
        
        return TrajectoryPoint(
            position=(float(center[0]), float(center[1])),
            velocity=velocity,
            timestamp=timestamp or frame_number,
            frame_number=frame_number
        )
    
    def _calculate_velocity(self, current_position: List[float]) -> Tuple[float, float]:
        """Calculate velocity from position history.
        
        Args:
            current_position: Current ball position [x, y]
            
        Returns:
            Velocity vector (vx, vy)
        """
        if len(self.trajectory_history) == 0:
            return (0.0, 0.0)
        
        # Use previous position to calculate velocity
        prev_point = self.trajectory_history[-1]
        dt = 1.0  # Assuming 1 frame time unit
        
        vx = (current_position[0] - prev_point.position[0]) / dt
        vy = (current_position[1] - prev_point.position[1]) / dt
        
        return (float(vx), float(vy))
    
    def _detect_contact_events(self) -> Dict[str, Any]:
        """Detect potential contact events from trajectory changes.
        
        Returns:
            Contact detection results
        """
        if len(self.trajectory_history) < 3:
            return {"contact_detected": False, "confidence": 0.0}
        
        # Get recent trajectory points
        recent_points = list(self.trajectory_history)[-5:]  # Last 5 points
        
        # Analyze velocity changes
        velocity_changes = self._analyze_velocity_changes(recent_points)
        
        # Analyze direction changes
        direction_changes = self._analyze_direction_changes_points(recent_points)
        
        # Combine evidence for contact detection
        contact_confidence = self._calculate_contact_confidence(
            velocity_changes, direction_changes
        )
        
        contact_detected = contact_confidence > 0.6
        
        return {
            "contact_detected": contact_detected,
            "confidence": contact_confidence,
            "velocity_changes": velocity_changes,
            "direction_changes": direction_changes,
            "analysis_points": len(recent_points)
        }
    
    def _analyze_velocity_changes(self, points: List[TrajectoryPoint]) -> Dict[str, Any]:
        """Analyze velocity changes in trajectory points.
        
        Args:
            points: List of trajectory points
            
        Returns:
            Velocity change analysis
        """
        if len(points) < 2:
            return {"significant_changes": 0, "max_change": 0.0}
        
        velocity_magnitudes = []
        velocity_changes = []
        
        for point in points:
            velocity_mag = np.sqrt(point.velocity[0]**2 + point.velocity[1]**2)
            velocity_magnitudes.append(velocity_mag)
        
        # Calculate velocity changes
        for i in range(1, len(velocity_magnitudes)):
            change = abs(velocity_magnitudes[i] - velocity_magnitudes[i-1])
            velocity_changes.append(change)
        
        significant_changes = sum(1 for change in velocity_changes 
                                if change > self.min_velocity_change)
        max_change = max(velocity_changes) if velocity_changes else 0.0
        avg_change = np.mean(velocity_changes) if velocity_changes else 0.0
        
        return {
            "significant_changes": significant_changes,
            "max_change": max_change,
            "average_change": avg_change,
            "velocity_magnitudes": velocity_magnitudes,
            "changes": velocity_changes
        }
    
    def _analyze_direction_changes_points(self, points: List[TrajectoryPoint]) -> Dict[str, Any]:
        """Analyze direction changes in trajectory points.
        
        Args:
            points: List of trajectory points
            
        Returns:
            Direction change analysis
        """
        if len(points) < 2:
            return {"significant_changes": 0, "max_change": 0.0}
        
        direction_angles = []
        direction_changes = []
        
        # Calculate direction angles
        for point in points:
            if point.velocity[0] != 0 or point.velocity[1] != 0:
                angle = np.arctan2(point.velocity[1], point.velocity[0])
                direction_angles.append(np.degrees(angle))
        
        # Calculate direction changes
        for i in range(1, len(direction_angles)):
            change = abs(direction_angles[i] - direction_angles[i-1])
            # Handle wrap-around (e.g., -179° to 179°)
            if change > 180:
                change = 360 - change
            direction_changes.append(change)
        
        significant_changes = sum(1 for change in direction_changes 
                                if change > self.min_direction_change)
        max_change = max(direction_changes) if direction_changes else 0.0
        avg_change = np.mean(direction_changes) if direction_changes else 0.0
        
        return {
            "significant_changes": significant_changes,
            "max_change": max_change,
            "average_change": avg_change,
            "direction_angles": direction_angles,
            "changes": direction_changes
        }
    
    def _calculate_contact_confidence(
        self,
        velocity_changes: Dict[str, Any],
        direction_changes: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for contact detection.
        
        Args:
            velocity_changes: Velocity change analysis
            direction_changes: Direction change analysis
            
        Returns:
            Contact confidence score (0.0 to 1.0)
        """
        confidence = 0.0
        
        # Velocity change evidence
        vel_significant = velocity_changes.get("significant_changes", 0)
        vel_max_change = velocity_changes.get("max_change", 0.0)
        
        if vel_significant > 0:
            confidence += 0.3
        if vel_max_change > self.min_velocity_change * 2:
            confidence += 0.2
        
        # Direction change evidence
        dir_significant = direction_changes.get("significant_changes", 0)
        dir_max_change = direction_changes.get("max_change", 0.0)
        
        if dir_significant > 0:
            confidence += 0.3
        if dir_max_change > self.min_direction_change * 2:
            confidence += 0.2
        
        return min(1.0, confidence)
    
    def _analyze_velocity_patterns(self) -> Dict[str, Any]:
        """Analyze velocity patterns over the trajectory window.
        
        Returns:
            Velocity pattern analysis
        """
        if len(self.trajectory_history) < 3:
            return {"pattern": "insufficient_data"}
        
        velocities = []
        for point in self.trajectory_history:
            vel_mag = np.sqrt(point.velocity[0]**2 + point.velocity[1]**2)
            velocities.append(vel_mag)
        
        # Smooth velocities
        smoothed_velocities = self._smooth_values(velocities)
        
        # Analyze patterns
        is_accelerating = self._detect_acceleration_pattern(smoothed_velocities)
        is_decelerating = self._detect_deceleration_pattern(smoothed_velocities)
        has_spikes = self._detect_velocity_spikes(velocities)
        
        return {
            "pattern": self._classify_velocity_pattern(is_accelerating, is_decelerating, has_spikes),
            "velocities": velocities,
            "smoothed_velocities": smoothed_velocities,
            "is_accelerating": is_accelerating,
            "is_decelerating": is_decelerating,
            "has_spikes": has_spikes,
            "average_velocity": np.mean(velocities),
            "max_velocity": np.max(velocities),
            "min_velocity": np.min(velocities)
        }
    
    def _analyze_direction_changes(self) -> Dict[str, Any]:
        """Analyze direction changes over the trajectory window.
        
        Returns:
            Direction change analysis
        """
        if len(self.trajectory_history) < 3:
            return {"pattern": "insufficient_data"}
        
        directions = []
        for point in self.trajectory_history:
            if point.velocity[0] != 0 or point.velocity[1] != 0:
                angle = np.arctan2(point.velocity[1], point.velocity[0])
                directions.append(np.degrees(angle))
        
        if len(directions) < 2:
            return {"pattern": "insufficient_data"}
        
        # Calculate direction changes
        direction_changes = []
        for i in range(1, len(directions)):
            change = abs(directions[i] - directions[i-1])
            if change > 180:
                change = 360 - change
            direction_changes.append(change)
        
        # Analyze patterns
        total_change = sum(direction_changes)
        max_change = max(direction_changes) if direction_changes else 0
        avg_change = np.mean(direction_changes) if direction_changes else 0
        
        return {
            "pattern": self._classify_direction_pattern(direction_changes),
            "directions": directions,
            "direction_changes": direction_changes,
            "total_change": total_change,
            "max_change": max_change,
            "average_change": avg_change
        }
    
    def _validate_trajectory_physics(self) -> Dict[str, Any]:
        """Validate trajectory against basic physics principles.
        
        Returns:
            Physics validation results
        """
        if len(self.trajectory_history) < 3:
            return {"valid": True, "confidence": 0.5, "reason": "insufficient_data"}
        
        # Check for realistic acceleration patterns
        physics_violations = []
        confidence = 1.0
        
        # Analyze vertical motion for gravity effects
        gravity_analysis = self._analyze_gravity_effects()
        if not gravity_analysis["realistic"]:
            physics_violations.append("unrealistic_gravity")
            confidence *= 0.7
        
        # Check for reasonable velocity changes
        velocity_analysis = self._analyze_physics_velocity()
        if not velocity_analysis["realistic"]:
            physics_violations.append("unrealistic_velocity_changes")
            confidence *= 0.8
        
        # Check trajectory smoothness
        smoothness_analysis = self._analyze_trajectory_smoothness()
        if not smoothness_analysis["smooth"]:
            physics_violations.append("trajectory_too_erratic")
            confidence *= 0.9
        
        is_valid = len(physics_violations) == 0
        
        return {
            "valid": is_valid,
            "confidence": confidence,
            "violations": physics_violations,
            "gravity_analysis": gravity_analysis,
            "velocity_analysis": velocity_analysis,
            "smoothness_analysis": smoothness_analysis
        }
    
    def _detect_trajectory_events(self, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect significant trajectory events.
        
        Args:
            analysis_results: Combined analysis results
            
        Returns:
            List of detected events
        """
        events = []
        
        # Contact detection event
        contact_detection = analysis_results.get("contact_detection", {})
        if contact_detection.get("contact_detected", False):
            events.append({
                "type": TrajectoryEvent.CONTACT_DETECTED.value,
                "confidence": contact_detection.get("confidence", 0.0),
                "frame": len(self.trajectory_history) - 1,
                "details": contact_detection
            })
        
        # Direction change event
        direction_analysis = analysis_results.get("direction_analysis", {})
        if direction_analysis.get("max_change", 0) > self.min_direction_change * 1.5:
            events.append({
                "type": TrajectoryEvent.DIRECTION_CHANGE.value,
                "confidence": min(1.0, direction_analysis.get("max_change", 0) / 90.0),
                "frame": len(self.trajectory_history) - 1,
                "details": direction_analysis
            })
        
        # Velocity spike event
        velocity_analysis = analysis_results.get("velocity_analysis", {})
        if velocity_analysis.get("has_spikes", False):
            events.append({
                "type": TrajectoryEvent.VELOCITY_SPIKE.value,
                "confidence": 0.8,
                "frame": len(self.trajectory_history) - 1,
                "details": velocity_analysis
            })
        
        return events
    
    def _validate_dig_trajectory(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trajectory for dig action."""
        # Digs typically cause upward ball movement
        velocity_analysis = analysis.get("velocity_analysis", {})
        
        # Check for upward trajectory after contact
        recent_points = list(self.trajectory_history)[-3:]
        upward_motion = any(point.velocity[1] < 0 for point in recent_points)  # Negative Y is up
        
        confidence = 0.5
        if upward_motion:
            confidence += 0.3
        
        # Check for appropriate velocity increase
        if velocity_analysis.get("is_accelerating", False):
            confidence += 0.2
        
        return {
            "valid": confidence > 0.6,
            "confidence": confidence,
            "action_type": "dig",
            "upward_motion": upward_motion,
            "details": velocity_analysis
        }
    
    def _validate_set_trajectory(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trajectory for set action."""
        # Sets typically involve controlled, moderate velocity
        velocity_analysis = analysis.get("velocity_analysis", {})
        avg_velocity = velocity_analysis.get("average_velocity", 0)
        
        confidence = 0.5
        
        # Moderate velocity is preferred for sets
        if 10 <= avg_velocity <= 40:
            confidence += 0.3
        
        # Smooth trajectory is important for sets
        physics_validation = analysis.get("physics_validation", {})
        if physics_validation.get("smoothness_analysis", {}).get("smooth", False):
            confidence += 0.2
        
        return {
            "valid": confidence > 0.6,
            "confidence": confidence,
            "action_type": "set",
            "controlled_velocity": 10 <= avg_velocity <= 40,
            "details": velocity_analysis
        }
    
    def _validate_spike_trajectory(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trajectory for spike action."""
        # Spikes typically cause high downward velocity
        velocity_analysis = analysis.get("velocity_analysis", {})
        max_velocity = velocity_analysis.get("max_velocity", 0)
        
        # Check for downward motion
        recent_points = list(self.trajectory_history)[-3:]
        downward_motion = any(point.velocity[1] > 30 for point in recent_points)  # Positive Y is down
        
        confidence = 0.5
        if downward_motion and max_velocity > 50:
            confidence += 0.4
        elif max_velocity > 30:
            confidence += 0.2
        
        return {
            "valid": confidence > 0.6,
            "confidence": confidence,
            "action_type": "spike",
            "high_velocity": max_velocity > 50,
            "downward_motion": downward_motion,
            "details": velocity_analysis
        }
    
    def _validate_block_trajectory(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trajectory for block action."""
        # Blocks can cause various trajectory changes
        contact_detection = analysis.get("contact_detection", {})
        direction_analysis = analysis.get("direction_analysis", {})
        
        confidence = 0.5
        
        # Direction change is expected for blocks
        if direction_analysis.get("max_change", 0) > 45:
            confidence += 0.3
        
        # Contact detection is important
        if contact_detection.get("contact_detected", False):
            confidence += 0.2
        
        return {
            "valid": confidence > 0.6,
            "confidence": confidence,
            "action_type": "block",
            "direction_change": direction_analysis.get("max_change", 0) > 45,
            "details": contact_detection
        }
    
    def _validate_serve_trajectory(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trajectory for serve action."""
        # Serves should show ball acceleration from stationary
        velocity_analysis = analysis.get("velocity_analysis", {})
        
        confidence = 0.5
        
        # Acceleration pattern expected for serves
        if velocity_analysis.get("is_accelerating", False):
            confidence += 0.4
        
        # Significant velocity increase
        max_velocity = velocity_analysis.get("max_velocity", 0)
        if max_velocity > 25:
            confidence += 0.1
        
        return {
            "valid": confidence > 0.6,
            "confidence": confidence,
            "action_type": "serve",
            "acceleration_detected": velocity_analysis.get("is_accelerating", False),
            "details": velocity_analysis
        }
    
    # Helper methods for pattern analysis
    def _smooth_values(self, values: List[float]) -> List[float]:
        """Apply smoothing to values."""
        if len(values) < self.smoothing_window:
            return values
        
        smoothed = []
        for i in range(len(values)):
            start = max(0, i - self.smoothing_window // 2)
            end = min(len(values), i + self.smoothing_window // 2 + 1)
            smoothed.append(np.mean(values[start:end]))
        
        return smoothed
    
    def _detect_acceleration_pattern(self, velocities: List[float]) -> bool:
        """Detect if velocities show acceleration pattern."""
        if len(velocities) < 3:
            return False
        
        increases = sum(1 for i in range(1, len(velocities)) 
                       if velocities[i] > velocities[i-1])
        return increases >= len(velocities) * 0.6
    
    def _detect_deceleration_pattern(self, velocities: List[float]) -> bool:
        """Detect if velocities show deceleration pattern."""
        if len(velocities) < 3:
            return False
        
        decreases = sum(1 for i in range(1, len(velocities)) 
                       if velocities[i] < velocities[i-1])
        return decreases >= len(velocities) * 0.6
    
    def _detect_velocity_spikes(self, velocities: List[float]) -> bool:
        """Detect velocity spikes in the data."""
        if len(velocities) < 3:
            return False
        
        avg_velocity = np.mean(velocities)
        spikes = sum(1 for v in velocities 
                    if v > avg_velocity * self.velocity_spike_threshold)
        return spikes > 0
    
    def _classify_velocity_pattern(self, is_accelerating: bool, is_decelerating: bool, has_spikes: bool) -> str:
        """Classify velocity pattern based on analysis."""
        if has_spikes:
            return "spiked"
        elif is_accelerating:
            return "accelerating"
        elif is_decelerating:
            return "decelerating"
        else:
            return "stable"
    
    def _classify_direction_pattern(self, direction_changes: List[float]) -> str:
        """Classify direction change pattern."""
        if not direction_changes:
            return "no_change"
        
        max_change = max(direction_changes)
        avg_change = np.mean(direction_changes)
        
        if max_change > 90:
            return "sharp_turn"
        elif avg_change > 30:
            return "curved"
        elif avg_change > 10:
            return "slight_curve"
        else:
            return "straight"
    
    def _analyze_gravity_effects(self) -> Dict[str, Any]:
        """Analyze if trajectory shows realistic gravity effects."""
        if len(self.trajectory_history) < 4:
            return {"realistic": True, "reason": "insufficient_data"}
        
        # Check vertical acceleration patterns
        y_velocities = [point.velocity[1] for point in self.trajectory_history]
        
        # Simple gravity check: vertical velocity should generally increase downward
        consistent_gravity = True
        for i in range(1, len(y_velocities) - 1):
            # Allow for some noise, but generally expect downward acceleration
            if y_velocities[i+1] < y_velocities[i] - 5:  # Upward acceleration > 5 pixels/frame
                consistent_gravity = False
                break
        
        return {
            "realistic": consistent_gravity,
            "y_velocities": y_velocities,
            "reason": "gravity_check"
        }
    
    def _analyze_physics_velocity(self) -> Dict[str, Any]:
        """Analyze if velocity changes are physically realistic."""
        if len(self.trajectory_history) < 3:
            return {"realistic": True, "reason": "insufficient_data"}
        
        # Check for unrealistic velocity jumps
        velocities = []
        for point in self.trajectory_history:
            vel_mag = np.sqrt(point.velocity[0]**2 + point.velocity[1]**2)
            velocities.append(vel_mag)
        
        # Check for sudden velocity changes that would require unrealistic forces
        unrealistic_changes = 0
        for i in range(1, len(velocities)):
            change = abs(velocities[i] - velocities[i-1])
            if change > 100:  # More than 100 pixels/frame change is suspicious
                unrealistic_changes += 1
        
        realistic = unrealistic_changes < len(velocities) * 0.3
        
        return {
            "realistic": realistic,
            "unrealistic_changes": unrealistic_changes,
            "velocities": velocities,
            "reason": "velocity_jump_check"
        }
    
    def _analyze_trajectory_smoothness(self) -> Dict[str, Any]:
        """Analyze trajectory smoothness."""
        if len(self.trajectory_history) < 4:
            return {"smooth": True, "reason": "insufficient_data"}
        
        # Calculate position changes
        position_changes = []
        for i in range(1, len(self.trajectory_history)):
            prev_pos = self.trajectory_history[i-1].position
            curr_pos = self.trajectory_history[i].position
            change = np.sqrt((curr_pos[0] - prev_pos[0])**2 + (curr_pos[1] - prev_pos[1])**2)
            position_changes.append(change)
        
        # Check for erratic movement
        if len(position_changes) < 2:
            return {"smooth": True, "reason": "insufficient_data"}
        
        avg_change = np.mean(position_changes)
        std_change = np.std(position_changes)
        
        # High standard deviation relative to mean indicates erratic movement
        smoothness_ratio = std_change / (avg_change + 1e-6)
        is_smooth = smoothness_ratio < 2.0
        
        return {
            "smooth": is_smooth,
            "smoothness_ratio": smoothness_ratio,
            "position_changes": position_changes,
            "reason": "smoothness_check"
        }
    
    def _create_analysis_result(
        self,
        success: bool,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create standardized analysis result.
        
        Args:
            success: Whether analysis was successful
            message: Analysis message
            details: Optional additional details
            
        Returns:
            Standardized analysis result
        """
        return {
            "success": success,
            "message": message,
            "trajectory_points": len(self.trajectory_history),
            "details": details or {}
        }
    
    def get_trajectory_history(self) -> List[TrajectoryPoint]:
        """Get current trajectory history.
        
        Returns:
            List of trajectory points
        """
        return list(self.trajectory_history)
    
    def clear_history(self) -> None:
        """Clear trajectory history."""
        self.trajectory_history.clear()
        self.detected_events.clear()
    
    def get_detected_events(self) -> List[Dict[str, Any]]:
        """Get list of detected trajectory events.
        
        Returns:
            List of detected events
        """
        return self.detected_events.copy()