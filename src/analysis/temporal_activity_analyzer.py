"""
Temporal activity analyzer for game state detection.

This module analyzes temporal patterns in player and ball activity
to detect game flow changes, pauses, and activity levels.
"""

from typing import List, Dict, Any, Optional
from collections import deque
import numpy as np
import logging

from .game_state import AnalysisResult


class TemporalActivityAnalyzer:
    """Analyzes temporal activity patterns for game state indicators."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the temporal activity analyzer.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config.get("game_state_detection", {}).get("temporal_analysis", {})
        self.logger = logging.getLogger(__name__)
        
        # Configuration parameters
        self.activity_smoothing_window = self.config.get("activity_smoothing_window", 15)
        pause_thresholds = self.config.get("pause_classification_thresholds", {})
        self.short_pause_threshold = pause_thresholds.get("short_pause", 1.0)  # seconds
        self.medium_pause_threshold = pause_thresholds.get("medium_pause", 5.0)  # seconds
        self.long_pause_threshold = pause_thresholds.get("long_pause", 15.0)  # seconds
        
        # Frame rate (will be updated from video info)
        self.fps = 30.0
        
        # Activity tracking
        self.activity_history = deque(maxlen=300)  # 10 seconds at 30fps
        self.player_activity_history = deque(maxlen=150)  # 5 seconds
        self.ball_activity_history = deque(maxlen=150)  # 5 seconds
        
        # State tracking
        self.last_activity_frame = None
        self.current_pause_duration = 0
        self.pause_start_frame = None
        
        # Activity metrics
        self.activity_levels = deque(maxlen=self.activity_smoothing_window)
    
    def analyze_frame(self, frame_result: Dict[str, Any], frame_number: int) -> AnalysisResult:
        """Analyze current frame for temporal activity patterns.
        
        Args:
            frame_result: Frame processing results
            frame_number: Current frame number
            
        Returns:
            Analysis result with confidence scores
        """
        # Calculate current activity level
        activity_level = self._calculate_frame_activity(frame_result)
        
        # Update activity history
        self._update_activity_history(activity_level, frame_number)
        
        # Analyze temporal patterns
        confidence_scores = {
            "activity_resuming": self._detect_activity_resuming(),
            "extended_pause": self._detect_extended_pause(),
            "activity_level": self._get_current_activity_level(),
            "pause_type": self._classify_current_pause_type(),
            "rhythm_change": self._detect_rhythm_change()
        }
        
        metadata = {
            "current_activity_level": activity_level,
            "pause_duration_seconds": self.current_pause_duration / self.fps,
            "frames_since_activity": self._get_frames_since_activity(frame_number),
            "activity_history_length": len(self.activity_history)
        }
        
        return AnalysisResult(
            confidence_scores=confidence_scores,
            metadata=metadata
        )
    
    def _calculate_frame_activity(self, frame_result: Dict[str, Any]) -> float:
        """Calculate activity level for current frame.
        
        Args:
            frame_result: Frame processing results
            
        Returns:
            Activity level (0.0 to 1.0)
        """
        activity = 0.0
        
        # Player activity
        player_detections = frame_result.get("tracked_players", [])
        player_actions = frame_result.get("actions", [])
        
        # Base activity from player presence
        if player_detections:
            activity += len(player_detections) * 0.1  # 0.1 per player
        
        # Activity from actions
        if player_actions:
            # Weight actions by confidence
            action_activity = sum(
                action.get("confidence", 0.0) * 0.3
                for action in player_actions
            )
            activity += min(action_activity, 0.5)  # Cap at 0.5
        
        # Ball activity
        ball_info = frame_result.get("tracked_ball")
        if ball_info and ball_info.get("center"):
            ball_position = ball_info["center"]
            if ball_position[0] is not None and ball_position[1] is not None:
                activity += 0.3  # Ball is tracked
                
                # Extra activity if ball appears to be moving
                # (This could be enhanced with velocity information)
                if len(self.ball_activity_history) > 0:
                    last_ball_activity = self.ball_activity_history[-1]
                    if last_ball_activity.get("position"):
                        # Simple movement detection
                        distance = np.sqrt(
                            (ball_position[0] - last_ball_activity["position"][0])**2 +
                            (ball_position[1] - last_ball_activity["position"][1])**2
                        )
                        if distance > 10:  # Ball moved significantly
                            activity += 0.2
        
        return min(activity, 1.0)
    
    def _update_activity_history(self, activity_level: float, frame_number: int) -> None:
        """Update activity tracking data.
        
        Args:
            activity_level: Calculated activity level
            frame_number: Current frame number
        """
        activity_info = {
            "level": activity_level,
            "frame": frame_number,
            "timestamp": frame_number / self.fps
        }
        
        self.activity_history.append(activity_info)
        self.activity_levels.append(activity_level)
        
        # Update pause tracking
        if activity_level > 0.2:  # Significant activity threshold
            if self.pause_start_frame is not None:
                # Activity resumed - end pause
                self.current_pause_duration = 0
                self.pause_start_frame = None
            self.last_activity_frame = frame_number
        else:
            # Low activity
            if self.pause_start_frame is None:
                self.pause_start_frame = frame_number
            
            if self.last_activity_frame is not None:
                self.current_pause_duration = frame_number - self.last_activity_frame
    
    def _detect_activity_resuming(self) -> float:
        """Detect if activity is resuming after a pause.
        
        Returns:
            Confidence score for activity resuming (0.0 to 1.0)
        """
        if len(self.activity_levels) < 5:
            return 0.0
        
        activity_levels_list = list(self.activity_levels)
        recent_levels = activity_levels_list[-5:]
        
        # Check for recent increase in activity
        if len(recent_levels) >= 3:
            # Compare last 2 frames to previous 3
            recent_list = list(recent_levels)
            recent_avg = np.mean(recent_list[-2:]) if len(recent_list) >= 2 else 0.0
            if len(recent_list) >= 5:
                previous_avg = np.mean(recent_list[-5:-2])
            else:
                previous_avg = np.mean(recent_list[:-2]) if len(recent_list) > 2 else 0.0
            
            if recent_avg > previous_avg + 0.3:  # Significant increase
                # Additional confidence if coming from a pause
                if self.current_pause_duration > self.short_pause_threshold * self.fps:
                    return min(0.8 + (recent_avg - previous_avg), 1.0)
                else:
                    return min(0.5 + (recent_avg - previous_avg), 1.0)
        
        return 0.0
    
    def _detect_extended_pause(self) -> float:
        """Detect extended pause periods.
        
        Returns:
            Confidence score for extended pause (0.0 to 1.0)
        """
        if self.current_pause_duration == 0:
            return 0.0
        
        pause_seconds = self.current_pause_duration / self.fps
        
        if pause_seconds >= self.long_pause_threshold:
            return 1.0
        elif pause_seconds >= self.medium_pause_threshold:
            return 0.8
        elif pause_seconds >= self.short_pause_threshold:
            return 0.6
        else:
            # Scale confidence for shorter pauses
            return min(pause_seconds / self.short_pause_threshold * 0.5, 0.5)
    
    def _get_current_activity_level(self) -> float:
        """Get smoothed current activity level.
        
        Returns:
            Smoothed activity level (0.0 to 1.0)
        """
        if not self.activity_levels:
            return 0.0
        
        # Use smoothed average of recent activity
        return np.mean(list(self.activity_levels))
    
    def _classify_current_pause_type(self) -> float:
        """Classify the type of current pause.
        
        Returns:
            Confidence score for pause classification
        """
        if self.current_pause_duration == 0:
            return 0.0  # No pause
        
        pause_seconds = self.current_pause_duration / self.fps
        
        if pause_seconds >= self.long_pause_threshold:
            return 3.0  # Long pause (timeout/break)
        elif pause_seconds >= self.medium_pause_threshold:
            return 2.0  # Medium pause (between points)
        elif pause_seconds >= self.short_pause_threshold:
            return 1.0  # Short pause (brief break in action)
        else:
            return 0.5  # Very short pause
    
    def _detect_rhythm_change(self) -> float:
        """Detect changes in game rhythm/tempo.
        
        Returns:
            Confidence score for rhythm change (0.0 to 1.0)
        """
        if len(self.activity_history) < 20:
            return 0.0
        
        # Compare recent activity variance to historical variance
        activity_list = list(self.activity_history)
        recent_activity = [item["level"] for item in activity_list[-10:]]
        
        if len(activity_list) >= 20:
            historical_activity = [item["level"] for item in activity_list[-20:-10]]
        else:
            # Not enough historical data
            return 0.0
        
        if len(historical_activity) < 5:
            return 0.0
        
        recent_variance = np.var(recent_activity)
        historical_variance = np.var(historical_activity)
        
        # Detect significant change in activity pattern
        if historical_variance > 0:
            variance_ratio = abs(recent_variance - historical_variance) / historical_variance
            if variance_ratio > 0.5:  # 50% change in variance
                return min(variance_ratio, 1.0)
        
        return 0.0
    
    def _get_frames_since_activity(self, current_frame: int) -> int:
        """Get number of frames since last significant activity.
        
        Args:
            current_frame: Current frame number
            
        Returns:
            Frames since last activity
        """
        if self.last_activity_frame is None:
            return 0
        
        return current_frame - self.last_activity_frame
    
    def set_fps(self, fps: float) -> None:
        """Set video frame rate.
        
        Args:
            fps: Frames per second
        """
        self.fps = fps
        self.logger.debug(f"Updated FPS to {fps}")
    
    def reset(self) -> None:
        """Reset analyzer state."""
        self.activity_history.clear()
        self.player_activity_history.clear()
        self.ball_activity_history.clear()
        self.activity_levels.clear()
        
        self.last_activity_frame = None
        self.current_pause_duration = 0
        self.pause_start_frame = None
        
        self.logger.info("Temporal activity analyzer reset")
    
    def get_activity_timeline(self) -> List[Dict[str, Any]]:
        """Get activity timeline for analysis.
        
        Returns:
            List of activity data points
        """
        return list(self.activity_history)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get analyzer statistics.
        
        Returns:
            Statistics dictionary
        """
        if not self.activity_history:
            return {
                "total_frames": 0,
                "avg_activity": 0.0,
                "current_pause_duration": 0.0,
                "pause_count": 0
            }
        
        activity_levels = [item["level"] for item in self.activity_history]
        
        # Count pauses (periods with low activity)
        pause_count = 0
        in_pause = False
        
        for level in activity_levels:
            if level < 0.2 and not in_pause:
                pause_count += 1
                in_pause = True
            elif level >= 0.2:
                in_pause = False
        
        return {
            "total_frames": len(self.activity_history),
            "avg_activity": np.mean(activity_levels),
            "max_activity": np.max(activity_levels),
            "activity_variance": np.var(activity_levels),
            "current_pause_duration": self.current_pause_duration / self.fps,
            "pause_count": pause_count,
            "frames_with_activity": sum(1 for level in activity_levels if level > 0.2),
            "activity_ratio": sum(1 for level in activity_levels if level > 0.2) / len(activity_levels)
        }