"""
Action sequence analyzer for game state detection.

This module analyzes patterns in detected action sequences to infer
game state transitions and rally patterns.
"""

from typing import List, Dict, Any, Optional
from collections import deque
import numpy as np
import logging

from .game_state import AnalysisResult, GameState


class ActionSequenceAnalyzer:
    """Analyzes action sequences for game state indicators."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the action sequence analyzer.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config.get("game_state_detection", {}).get("action_sequence", {})
        self.logger = logging.getLogger(__name__)
        
        # Configuration parameters
        self.serve_pattern_window = self.config.get("serve_pattern_window", 30)
        self.rally_end_inactivity_threshold = self.config.get("rally_end_inactivity_threshold", 90)
        self.action_confidence_threshold = self.config.get("action_confidence_threshold", 0.6)
        
        # State tracking
        self.recent_actions = deque(maxlen=self.serve_pattern_window)
        self.last_action_frame = None
        self.inactivity_frames = 0
        
        # Pattern recognition
        self.serve_indicators = ["serve", "ace"]
        self.rally_actions = ["dig", "set", "spike", "block"]
        self.rally_end_patterns = [
            ["spike", "dig"],  # Attack followed by defense
            ["block"],         # Block ending rally
            ["ace"],          # Direct ace
        ]
    
    def analyze_frame(self, frame_result: Dict[str, Any], frame_number: int) -> AnalysisResult:
        """Analyze current frame for action sequence patterns.
        
        Args:
            frame_result: Frame processing results
            frame_number: Current frame number
            
        Returns:
            Analysis result with confidence scores
        """
        actions = frame_result.get("actions", [])
        
        # Filter high-confidence actions
        valid_actions = [
            action for action in actions
            if action.get("confidence", 0.0) > self.action_confidence_threshold
        ]
        
        # Update action history
        self._update_action_history(valid_actions, frame_number)
        
        # Analyze patterns
        confidence_scores = {
            "serve_detected": self._detect_serve_sequence(),
            "rally_active": self._detect_rally_activity(),
            "rally_end_pattern": self._detect_rally_end_pattern(),
            "inactivity_detected": self._detect_inactivity()
        }
        
        metadata = {
            "recent_actions": list(self.recent_actions),
            "inactivity_frames": self.inactivity_frames,
            "last_action_frame": self.last_action_frame,
            "current_frame": frame_number
        }
        
        return AnalysisResult(
            confidence_scores=confidence_scores,
            metadata=metadata
        )
    
    def _update_action_history(self, actions: List[Dict[str, Any]], frame_number: int) -> None:
        """Update the recent action history.
        
        Args:
            actions: List of detected actions
            frame_number: Current frame number
        """
        if actions:
            # Add actions to history
            for action in actions:
                action_info = {
                    "action": action.get("action", "unknown"),
                    "confidence": action.get("confidence", 0.0),
                    "frame": frame_number,
                    "track_id": action.get("track_id")
                }
                self.recent_actions.append(action_info)
            
            # Update activity tracking
            self.last_action_frame = frame_number
            self.inactivity_frames = 0
        else:
            # No actions detected - increment inactivity
            if self.last_action_frame is not None:
                self.inactivity_frames = frame_number - self.last_action_frame
    
    def _detect_serve_sequence(self) -> float:
        """Detect if a serve sequence is starting.
        
        Returns:
            Confidence score for serve detection (0.0 to 1.0)
        """
        if not self.recent_actions:
            return 0.0
        
        # Look for recent serve actions
        recent_serves = [
            action for action in self.recent_actions
            if action["action"] in self.serve_indicators
        ]
        
        if not recent_serves:
            return 0.0
        
        # Check if serve is recent (within last 10 frames)
        latest_serve = max(recent_serves, key=lambda x: x["frame"])
        frames_since_serve = (list(self.recent_actions)[-1]["frame"] - latest_serve["frame"])
        
        if frames_since_serve <= 10:
            # High confidence for recent serve
            base_confidence = min(latest_serve["confidence"], 0.9)
            
            # Boost confidence if preceded by inactivity
            if self.inactivity_frames > 30:  # Had a pause before serve
                base_confidence = min(base_confidence + 0.2, 1.0)
            
            return base_confidence
        
        return 0.0
    
    def _detect_rally_activity(self) -> float:
        """Detect if rally is currently active.
        
        Returns:
            Confidence score for active rally (0.0 to 1.0)
        """
        if not self.recent_actions:
            return 0.0
        
        # Count rally actions in recent history
        recent_rally_actions = [
            action for action in self.recent_actions
            if action["action"] in self.rally_actions
        ]
        
        if not recent_rally_actions:
            return 0.0
        
        # Check recency and frequency
        latest_rally_action = max(recent_rally_actions, key=lambda x: x["frame"])
        frames_since_rally_action = (list(self.recent_actions)[-1]["frame"] - 
                                   latest_rally_action["frame"])
        
        # Rally is active if recent rally actions and not too much inactivity
        if frames_since_rally_action <= 20 and self.inactivity_frames < 60:
            # More recent rally actions = higher confidence
            action_frequency = len(recent_rally_actions) / len(self.recent_actions)
            confidence = min(action_frequency * 2.0, 0.9)
            
            # Boost for multiple different players involved
            unique_players = len(set(
                action.get("track_id") for action in recent_rally_actions
                if action.get("track_id") is not None
            ))
            if unique_players >= 2:
                confidence = min(confidence + 0.3, 1.0)
            
            return confidence
        
        return 0.0
    
    def _detect_rally_end_pattern(self) -> float:
        """Detect patterns that indicate rally ending.
        
        Returns:
            Confidence score for rally end (0.0 to 1.0)
        """
        if len(self.recent_actions) < 2:
            return 0.0
        
        # Get last few actions
        last_actions = list(self.recent_actions)[-5:]  # Last 5 actions
        action_sequence = [action["action"] for action in last_actions]
        
        # Check for known rally-ending patterns
        confidence = 0.0
        
        # Pattern 1: Spike without immediate response (likely point)
        if "spike" in action_sequence:
            spike_idx = len(action_sequence) - 1 - action_sequence[::-1].index("spike")
            actions_after_spike = action_sequence[spike_idx + 1:]
            
            # If spike is recent and no defensive response
            if spike_idx >= len(action_sequence) - 3 and not any(
                action in ["dig", "block"] for action in actions_after_spike
            ):
                confidence = max(confidence, 0.7)
        
        # Pattern 2: Block without continuation
        if "block" in action_sequence[-2:]:  # Recent block
            if not any(action in self.rally_actions for action in action_sequence[-1:]):
                confidence = max(confidence, 0.6)
        
        # Pattern 3: Ace (direct serve winner)
        if "ace" in action_sequence[-2:]:
            confidence = max(confidence, 0.9)
        
        return confidence
    
    def _detect_inactivity(self) -> float:
        """Detect extended inactivity periods.
        
        Returns:
            Confidence score for inactivity (0.0 to 1.0)
        """
        if self.inactivity_frames < 30:  # Less than 1 second at 30fps
            return 0.0
        
        # Scale confidence with inactivity duration
        if self.inactivity_frames >= self.rally_end_inactivity_threshold:
            return 1.0
        
        # Linear scaling between 30 frames and threshold
        normalized_inactivity = (self.inactivity_frames - 30) / (
            self.rally_end_inactivity_threshold - 30
        )
        
        return min(normalized_inactivity, 0.9)
    
    def reset(self) -> None:
        """Reset analyzer state."""
        self.recent_actions.clear()
        self.last_action_frame = None
        self.inactivity_frames = 0
        self.logger.info("Action sequence analyzer reset")
    
    def get_current_sequence(self) -> List[str]:
        """Get current action sequence.
        
        Returns:
            List of recent action types
        """
        return [action["action"] for action in self.recent_actions]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get analyzer statistics.
        
        Returns:
            Statistics dictionary
        """
        action_types = [action["action"] for action in self.recent_actions]
        action_counts = {}
        for action in action_types:
            action_counts[action] = action_counts.get(action, 0) + 1
        
        return {
            "total_actions_tracked": len(self.recent_actions),
            "action_counts": action_counts,
            "inactivity_frames": self.inactivity_frames,
            "last_action_frame": self.last_action_frame,
            "unique_players": len(set(
                action.get("track_id") for action in self.recent_actions
                if action.get("track_id") is not None
            ))
        }