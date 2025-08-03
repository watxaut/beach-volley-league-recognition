"""
Temporal contact validation for volleyball action recognition.

This module validates ball-player contact across multiple frames to ensure
sustained proximity and reduce false positive detections.
"""

from typing import Dict, Any, List, Optional, Deque
from collections import deque
import numpy as np
import logging
from dataclasses import dataclass
from enum import Enum

from .volleyball_actions import VolleyballAction


@dataclass
class ContactFrame:
    """Represents contact validation data for a single frame."""
    frame_number: int
    ball_data: Dict[str, Any]
    validation_result: Dict[str, Any]
    confidence: float
    timestamp: float


class ContactState(Enum):
    """Possible states for temporal contact validation."""
    NO_CONTACT = "no_contact"
    APPROACHING = "approaching"
    IN_CONTACT = "in_contact"
    DEPARTING = "departing"
    CONTACT_LOST = "contact_lost"


class TemporalContactValidator:
    """Validates ball-player contact across multiple frames."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the temporal contact validator.
        
        Args:
            config: Configuration dictionary with validation parameters
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Temporal validation parameters
        self.window_size = self.config.get("window_size", 5)
        self.min_frames_in_contact = self.config.get("min_frames_in_contact", 3)
        self.confidence_decay_rate = self.config.get("confidence_decay_rate", 0.1)
        self.contact_stability_threshold = self.config.get("contact_stability_threshold", 0.6)
        
        # Player history tracking
        self.player_histories: Dict[int, Deque[ContactFrame]] = {}
        self.player_states: Dict[int, ContactState] = {}
        self.player_contact_sequences: Dict[int, List[Dict[str, Any]]] = {}
        
        # Frame counter for temporal tracking
        self.current_frame = 0
        
    def validate_temporal_contact(
        self,
        player_id: int,
        ball_data: Dict[str, Any],
        instantaneous_validation: Dict[str, Any],
        action_type: VolleyballAction,
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """Validate ball contact across multiple frames.
        
        Args:
            player_id: Unique identifier for the player
            ball_data: Current frame ball data
            instantaneous_validation: Single-frame contact validation result
            action_type: Type of volleyball action
            timestamp: Frame timestamp (optional)
            
        Returns:
            Temporal validation results with sustained contact analysis
        """
        # Initialize player history if needed
        if player_id not in self.player_histories:
            self.player_histories[player_id] = deque(maxlen=self.window_size)
            self.player_states[player_id] = ContactState.NO_CONTACT
            self.player_contact_sequences[player_id] = []
        
        # Create contact frame
        contact_frame = ContactFrame(
            frame_number=self.current_frame,
            ball_data=ball_data,
            validation_result=instantaneous_validation,
            confidence=instantaneous_validation.get("confidence", 0.0),
            timestamp=timestamp or self.current_frame
        )
        
        # Add to history
        self.player_histories[player_id].append(contact_frame)
        
        # Update contact state
        self._update_contact_state(player_id, instantaneous_validation)
        
        # Validate sustained contact
        temporal_validation = self._validate_sustained_contact(player_id, action_type)
        
        # Update contact sequences
        self._update_contact_sequences(player_id, temporal_validation)
        
        # Increment frame counter
        self.current_frame += 1
        
        return temporal_validation
    
    def _update_contact_state(
        self, 
        player_id: int, 
        instantaneous_validation: Dict[str, Any]
    ) -> None:
        """Update the contact state for a player based on current validation.
        
        Args:
            player_id: Player identifier
            instantaneous_validation: Current frame validation result
        """
        current_state = self.player_states[player_id]
        is_valid = instantaneous_validation.get("valid", False)
        confidence = instantaneous_validation.get("confidence", 0.0)
        
        # State transition logic
        if current_state == ContactState.NO_CONTACT:
            if is_valid and confidence > 0.5:
                self.player_states[player_id] = ContactState.APPROACHING
                
        elif current_state == ContactState.APPROACHING:
            if is_valid and confidence > self.contact_stability_threshold:
                self.player_states[player_id] = ContactState.IN_CONTACT
            elif not is_valid or confidence < 0.3:
                self.player_states[player_id] = ContactState.NO_CONTACT
                
        elif current_state == ContactState.IN_CONTACT:
            if not is_valid or confidence < 0.4:
                self.player_states[player_id] = ContactState.DEPARTING
                
        elif current_state == ContactState.DEPARTING:
            if is_valid and confidence > self.contact_stability_threshold:
                self.player_states[player_id] = ContactState.IN_CONTACT
            elif not is_valid or confidence < 0.2:
                self.player_states[player_id] = ContactState.CONTACT_LOST
                
        elif current_state == ContactState.CONTACT_LOST:
            if is_valid and confidence > 0.5:
                self.player_states[player_id] = ContactState.APPROACHING
            # Stay in CONTACT_LOST for a few frames before returning to NO_CONTACT
            elif self._frames_since_state_change(player_id) > 3:
                self.player_states[player_id] = ContactState.NO_CONTACT
    
    def _validate_sustained_contact(
        self, 
        player_id: int, 
        action_type: VolleyballAction
    ) -> Dict[str, Any]:
        """Validate sustained contact over the temporal window.
        
        Args:
            player_id: Player identifier
            action_type: Volleyball action type
            
        Returns:
            Temporal validation results
        """
        history = self.player_histories[player_id]
        current_state = self.player_states[player_id]
        
        if len(history) < 2:
            return self._create_temporal_result(False, 0.0, "Insufficient history")
        
        # Analyze contact frames in the window
        contact_analysis = self._analyze_contact_frames(history)
        
        # Calculate temporal confidence
        temporal_confidence = self._calculate_temporal_confidence(
            contact_analysis, current_state, action_type
        )
        
        # Determine if temporal validation passes
        is_valid = self._determine_temporal_validity(
            contact_analysis, current_state, temporal_confidence
        )
        
        # Create detailed result
        return self._create_temporal_result(
            is_valid,
            temporal_confidence,
            f"Temporal validation for {action_type.value}",
            {
                "contact_analysis": contact_analysis,
                "current_state": current_state.value,
                "history_length": len(history),
                "action_type": action_type.value
            }
        )
    
    def _analyze_contact_frames(self, history: Deque[ContactFrame]) -> Dict[str, Any]:
        """Analyze contact frames to extract temporal patterns.
        
        Args:
            history: Deque of contact frames
            
        Returns:
            Analysis results with temporal patterns
        """
        if not history:
            return {}
        
        # Basic statistics
        total_frames = len(history)
        valid_frames = sum(1 for frame in history if frame.validation_result.get("valid", False))
        confidence_values = [frame.confidence for frame in history]
        
        # Temporal patterns
        confidence_trend = self._calculate_confidence_trend(confidence_values)
        contact_stability = self._calculate_contact_stability(history)
        contact_duration = self._calculate_contact_duration(history)
        
        # Ball movement analysis
        ball_movement = self._analyze_ball_movement(history)
        
        return {
            "total_frames": total_frames,
            "valid_frames": valid_frames,
            "valid_frame_ratio": valid_frames / total_frames if total_frames > 0 else 0.0,
            "average_confidence": np.mean(confidence_values) if confidence_values else 0.0,
            "max_confidence": np.max(confidence_values) if confidence_values else 0.0,
            "min_confidence": np.min(confidence_values) if confidence_values else 0.0,
            "confidence_trend": confidence_trend,
            "contact_stability": contact_stability,
            "contact_duration": contact_duration,
            "ball_movement": ball_movement
        }
    
    def _calculate_confidence_trend(self, confidence_values: List[float]) -> str:
        """Calculate the trend in confidence values.
        
        Args:
            confidence_values: List of confidence values over time
            
        Returns:
            Trend description ("increasing", "decreasing", "stable", "volatile")
        """
        if len(confidence_values) < 3:
            return "insufficient_data"
        
        # Calculate trend using linear regression slope
        x = np.arange(len(confidence_values))
        y = np.array(confidence_values)
        
        # Simple linear regression
        slope = np.polyfit(x, y, 1)[0]
        
        # Calculate volatility (standard deviation)
        volatility = np.std(confidence_values)
        
        if volatility > 0.3:
            return "volatile"
        elif slope > 0.05:
            return "increasing"
        elif slope < -0.05:
            return "decreasing"
        else:
            return "stable"
    
    def _calculate_contact_stability(self, history: Deque[ContactFrame]) -> float:
        """Calculate contact stability over the temporal window.
        
        Args:
            history: Contact frame history
            
        Returns:
            Stability score between 0.0 and 1.0
        """
        if len(history) < 2:
            return 0.0
        
        # Count state transitions
        states = []
        for frame in history:
            is_valid = frame.validation_result.get("valid", False)
            states.append(is_valid)
        
        # Calculate state changes
        transitions = sum(1 for i in range(1, len(states)) if states[i] != states[i-1])
        max_transitions = len(states) - 1
        
        if max_transitions == 0:
            return 1.0
        
        # Stability is inverse of transition rate
        stability = 1.0 - (transitions / max_transitions)
        return max(0.0, min(1.0, stability))
    
    def _calculate_contact_duration(self, history: Deque[ContactFrame]) -> Dict[str, Any]:
        """Calculate contact duration metrics.
        
        Args:
            history: Contact frame history
            
        Returns:
            Duration metrics
        """
        if not history:
            return {"current_streak": 0, "max_streak": 0, "total_contact_frames": 0}
        
        # Analyze contact streaks
        current_streak = 0
        max_streak = 0
        total_contact_frames = 0
        temp_streak = 0
        
        for frame in history:
            is_valid = frame.validation_result.get("valid", False)
            if is_valid:
                temp_streak += 1
                total_contact_frames += 1
            else:
                max_streak = max(max_streak, temp_streak)
                temp_streak = 0
        
        # Update max streak with final streak
        max_streak = max(max_streak, temp_streak)
        
        # Current streak is the streak at the end
        for frame in reversed(history):
            is_valid = frame.validation_result.get("valid", False)
            if is_valid:
                current_streak += 1
            else:
                break
        
        return {
            "current_streak": current_streak,
            "max_streak": max_streak,
            "total_contact_frames": total_contact_frames
        }
    
    def _analyze_ball_movement(self, history: Deque[ContactFrame]) -> Dict[str, Any]:
        """Analyze ball movement patterns during contact window.
        
        Args:
            history: Contact frame history
            
        Returns:
            Ball movement analysis
        """
        if len(history) < 2:
            return {"movement_detected": False, "average_speed": 0.0}
        
        # Extract ball positions
        positions = []
        velocities = []
        
        for frame in history:
            ball_data = frame.ball_data
            center = ball_data.get("center", [0, 0])
            velocity = ball_data.get("velocity", [0, 0])
            
            positions.append(center)
            if velocity and len(velocity) == 2:
                velocities.append(np.linalg.norm(velocity))
            else:
                velocities.append(0.0)
        
        # Calculate movement metrics
        if len(positions) >= 2:
            position_changes = []
            for i in range(1, len(positions)):
                if positions[i] and positions[i-1]:
                    change = np.linalg.norm(np.array(positions[i]) - np.array(positions[i-1]))
                    position_changes.append(change)
            
            average_position_change = np.mean(position_changes) if position_changes else 0.0
        else:
            average_position_change = 0.0
        
        average_velocity = np.mean(velocities) if velocities else 0.0
        max_velocity = np.max(velocities) if velocities else 0.0
        
        return {
            "movement_detected": average_position_change > 5.0 or average_velocity > 5.0,
            "average_speed": average_velocity,
            "max_speed": max_velocity,
            "average_position_change": average_position_change,
            "total_positions": len(positions)
        }
    
    def _calculate_temporal_confidence(
        self,
        contact_analysis: Dict[str, Any],
        current_state: ContactState,
        action_type: VolleyballAction
    ) -> float:
        """Calculate overall temporal confidence score.
        
        Args:
            contact_analysis: Analysis of contact frames
            current_state: Current contact state
            action_type: Volleyball action type
            
        Returns:
            Temporal confidence score between 0.0 and 1.0
        """
        base_confidence = contact_analysis.get("average_confidence", 0.0)
        
        # State-based multipliers
        state_multipliers = {
            ContactState.NO_CONTACT: 0.1,
            ContactState.APPROACHING: 0.6,
            ContactState.IN_CONTACT: 1.0,
            ContactState.DEPARTING: 0.8,
            ContactState.CONTACT_LOST: 0.3
        }
        
        state_multiplier = state_multipliers.get(current_state, 0.5)
        
        # Stability bonus
        stability = contact_analysis.get("contact_stability", 0.0)
        stability_bonus = stability * 0.2
        
        # Valid frame ratio bonus
        valid_ratio = contact_analysis.get("valid_frame_ratio", 0.0)
        ratio_bonus = valid_ratio * 0.3
        
        # Contact duration bonus
        duration_info = contact_analysis.get("contact_duration", {})
        current_streak = duration_info.get("current_streak", 0)
        duration_bonus = min(0.2, current_streak * 0.05)
        
        # Action-specific adjustments
        action_multiplier = self._get_action_temporal_multiplier(action_type, contact_analysis)
        
        # Calculate final confidence
        temporal_confidence = (
            base_confidence * state_multiplier * action_multiplier +
            stability_bonus + ratio_bonus + duration_bonus
        )
        
        return max(0.0, min(1.0, temporal_confidence))
    
    def _get_action_temporal_multiplier(
        self, 
        action_type: VolleyballAction, 
        contact_analysis: Dict[str, Any]
    ) -> float:
        """Get action-specific temporal multiplier.
        
        Args:
            action_type: Volleyball action type
            contact_analysis: Contact analysis results
            
        Returns:
            Action-specific multiplier
        """
        # Different actions have different temporal requirements
        if action_type == VolleyballAction.DIG:
            # Digs typically have brief contact
            return 1.1 if contact_analysis.get("contact_duration", {}).get("max_streak", 0) <= 3 else 0.9
            
        elif action_type == VolleyballAction.SET:
            # Sets need controlled, sustained contact
            stability = contact_analysis.get("contact_stability", 0.0)
            return 1.0 + (stability * 0.2)
            
        elif action_type == VolleyballAction.SPIKE:
            # Spikes are explosive, brief contact
            ball_movement = contact_analysis.get("ball_movement", {})
            if ball_movement.get("max_speed", 0) > 30:
                return 1.2
            return 0.8
            
        elif action_type == VolleyballAction.BLOCK:
            # Blocks may have brief or sustained contact
            return 1.0
            
        elif action_type == VolleyballAction.SERVE:
            # Serves should show ball acceleration
            ball_movement = contact_analysis.get("ball_movement", {})
            return 1.1 if ball_movement.get("movement_detected", False) else 0.7
        
        return 1.0
    
    def _determine_temporal_validity(
        self,
        contact_analysis: Dict[str, Any],
        current_state: ContactState,
        temporal_confidence: float
    ) -> bool:
        """Determine if temporal validation passes.
        
        Args:
            contact_analysis: Analysis results
            current_state: Current contact state
            temporal_confidence: Calculated temporal confidence
            
        Returns:
            True if temporal validation passes
        """
        # Basic confidence threshold
        if temporal_confidence < 0.5:
            return False
        
        # Minimum frames requirement
        valid_frames = contact_analysis.get("valid_frames", 0)
        if valid_frames < self.min_frames_in_contact:
            return False
        
        # State-based validation
        valid_states = {
            ContactState.IN_CONTACT,
            ContactState.DEPARTING
        }
        
        if current_state not in valid_states:
            # For other states, require higher confidence
            return temporal_confidence > 0.7
        
        return True
    
    def _update_contact_sequences(
        self, 
        player_id: int, 
        temporal_validation: Dict[str, Any]
    ) -> None:
        """Update contact sequences for pattern analysis.
        
        Args:
            player_id: Player identifier
            temporal_validation: Temporal validation result
        """
        if temporal_validation.get("valid", False):
            # Add to current sequence or start new one
            sequences = self.player_contact_sequences[player_id]
            if not sequences or not sequences[-1].get("active", False):
                # Start new sequence
                sequences.append({
                    "start_frame": self.current_frame,
                    "end_frame": self.current_frame,
                    "peak_confidence": temporal_validation.get("confidence", 0.0),
                    "active": True
                })
            else:
                # Extend current sequence
                sequences[-1]["end_frame"] = self.current_frame
                sequences[-1]["peak_confidence"] = max(
                    sequences[-1]["peak_confidence"],
                    temporal_validation.get("confidence", 0.0)
                )
        else:
            # End current sequence if active
            sequences = self.player_contact_sequences[player_id]
            if sequences and sequences[-1].get("active", False):
                sequences[-1]["active"] = False
    
    def _frames_since_state_change(self, player_id: int) -> int:
        """Calculate frames since last state change.
        
        Args:
            player_id: Player identifier
            
        Returns:
            Number of frames since state change
        """
        # This would require tracking state change timestamps
        # For simplicity, return a default value
        return 1
    
    def _create_temporal_result(
        self,
        is_valid: bool,
        confidence: float,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create standardized temporal validation result.
        
        Args:
            is_valid: Whether validation passed
            confidence: Confidence score
            message: Validation message
            details: Optional additional details
            
        Returns:
            Standardized temporal validation result
        """
        return {
            "valid": is_valid,
            "confidence": max(0.0, min(1.0, confidence)),
            "message": message,
            "temporal": True,
            "details": details or {}
        }
    
    def get_player_contact_history(self, player_id: int) -> Optional[List[ContactFrame]]:
        """Get contact history for a player.
        
        Args:
            player_id: Player identifier
            
        Returns:
            List of contact frames or None if player not found
        """
        if player_id in self.player_histories:
            return list(self.player_histories[player_id])
        return None
    
    def get_player_state(self, player_id: int) -> Optional[ContactState]:
        """Get current contact state for a player.
        
        Args:
            player_id: Player identifier
            
        Returns:
            Current contact state or None if player not found
        """
        return self.player_states.get(player_id)
    
    def reset_player_history(self, player_id: int) -> None:
        """Reset history for a specific player.
        
        Args:
            player_id: Player identifier
        """
        if player_id in self.player_histories:
            self.player_histories[player_id].clear()
            self.player_states[player_id] = ContactState.NO_CONTACT
            self.player_contact_sequences[player_id].clear()
    
    def reset_all_histories(self) -> None:
        """Reset all player histories."""
        self.player_histories.clear()
        self.player_states.clear()
        self.player_contact_sequences.clear()
        self.current_frame = 0