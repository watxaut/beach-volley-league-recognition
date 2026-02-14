"""
Score tracker for volleyball game state detection.

This module tracks team scores, service rotation, and point-scoring events
based on game state transitions and rally outcomes.
"""

from typing import Dict, Any, Optional, List
import logging

from .game_state import ScoreInfo, Team, GameState


class ScoreTracker:
    """Tracks volleyball game score and service rotation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the score tracker.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config.get("game_state_detection", {}).get("score_tracking", {})
        self.logger = logging.getLogger(__name__)
        
        # Configuration parameters
        self.max_score_per_set = self.config.get("max_score_per_set", 25)
        self.service_rotation_enabled = self.config.get("service_rotation_enabled", True)
        self.point_detection_methods = self.config.get("point_detection_methods", ["trajectory", "action_sequence"])
        
        # Current score state
        self.score_info = ScoreInfo()
        
        # Point tracking
        self.point_history = []
        self.last_point_frame = None
        self.rally_in_progress = False
        
        # Service tracking
        self.service_streak = 0  # How many consecutive points current server has scored
        self.last_serving_team = Team.UNKNOWN
        
        # Point detection state
        self.potential_point_detected = False
        self.point_detection_confidence = 0.0
        self.point_detection_frame = None
    
    def analyze_frame(self, frame_result: Dict[str, Any], game_state_info: Dict[str, Any], 
                     frame_number: int) -> ScoreInfo:
        """Analyze frame for scoring events and update score state.
        
        Args:
            frame_result: Frame processing results
            game_state_info: Current game state information
            frame_number: Current frame number
            
        Returns:
            Updated score information
        """
        current_state = game_state_info.get("current_state")
        analysis_breakdown = game_state_info.get("analysis_breakdown", {})
        
        # Handle game state transitions
        self._handle_state_transition(current_state, frame_number)
        
        # Detect point scoring events
        self._detect_point_events(analysis_breakdown, frame_number)
        
        # Update service tracking
        self._update_service_tracking(current_state, frame_number)
        
        # Update rally tracking
        self._update_rally_tracking(current_state)
        
        return self.score_info
    
    def _handle_state_transition(self, current_state: str, frame_number: int) -> None:
        """Handle game state transitions for scoring logic.
        
        Args:
            current_state: Current game state
            frame_number: Current frame number
        """
        if current_state == GameState.GAME_ON.value:
            if not self.rally_in_progress:
                # Rally started
                self.rally_in_progress = True
                self.score_info.point_in_progress = True
                self.logger.debug(f"Rally started at frame {frame_number}")
        
        elif current_state == GameState.POINT_SCORED.value:
            if self.rally_in_progress:
                # Point scored - rally ended
                self._record_point(frame_number)
                self.rally_in_progress = False
                self.score_info.point_in_progress = False
        
        elif current_state == GameState.GAME_OFF.value:
            # Between points
            self.score_info.point_in_progress = False
    
    def _detect_point_events(self, analysis_breakdown: Dict[str, Any], frame_number: int) -> None:
        """Detect point-scoring events from analysis breakdown.
        
        Args:
            analysis_breakdown: Analysis results from all modules
            frame_number: Current frame number
        """
        # Get confidence scores from different detection methods
        trajectory_confidence = 0.0
        action_confidence = 0.0
        
        trajectory_analysis = analysis_breakdown.get("trajectory", {})
        if trajectory_analysis:
            trajectory_confidence = trajectory_analysis.get("point_ending", 0.0)
        
        action_analysis = analysis_breakdown.get("action_sequence", {})
        if action_analysis:
            action_confidence = action_analysis.get("rally_end_pattern", 0.0)
        
        # Combine confidences based on enabled methods
        total_confidence = 0.0
        weight_sum = 0.0
        
        if "trajectory" in self.point_detection_methods:
            total_confidence += trajectory_confidence * 0.6
            weight_sum += 0.6
        
        if "action_sequence" in self.point_detection_methods:
            total_confidence += action_confidence * 0.4
            weight_sum += 0.4
        
        if weight_sum > 0:
            combined_confidence = total_confidence / weight_sum
        else:
            combined_confidence = 0.0
        
        # Update point detection state
        if combined_confidence > 0.7:  # High confidence threshold
            if not self.potential_point_detected:
                self.potential_point_detected = True
                self.point_detection_confidence = combined_confidence
                self.point_detection_frame = frame_number
                self.logger.debug(f"Potential point detected at frame {frame_number} with confidence {combined_confidence:.2f}")
        else:
            # Reset if confidence drops
            if self.potential_point_detected and combined_confidence < 0.3:
                self.potential_point_detected = False
                self.point_detection_confidence = 0.0
                self.point_detection_frame = None
    
    def _record_point(self, frame_number: int) -> None:
        """Record a scored point.
        
        Args:
            frame_number: Frame number when point was scored
        """
        # Determine which team scored (simplified logic for now)
        scoring_team = self._determine_scoring_team()
        
        # Update score
        if scoring_team == Team.TEAM_A:
            self.score_info.team_a_score += 1
        elif scoring_team == Team.TEAM_B:
            self.score_info.team_b_score += 1
        else:
            # Unknown team - increment based on current serving team or alternate
            if self.score_info.serving_team == Team.TEAM_A:
                self.score_info.team_a_score += 1
                scoring_team = Team.TEAM_A
            else:
                self.score_info.team_b_score += 1
                scoring_team = Team.TEAM_B
        
        # Record point in history
        point_record = {
            "frame": frame_number,
            "scoring_team": scoring_team.value,
            "score_after": (self.score_info.team_a_score, self.score_info.team_b_score),
            "serving_team": self.score_info.serving_team.value,
            "detection_confidence": self.point_detection_confidence
        }
        self.point_history.append(point_record)
        
        # Handle service rotation
        if self.service_rotation_enabled:
            self._handle_service_rotation(scoring_team)
        
        # Reset point detection state
        self.potential_point_detected = False
        self.point_detection_confidence = 0.0
        self.point_detection_frame = None
        self.last_point_frame = frame_number
        
        self.logger.info(f"Point scored by {scoring_team.value} at frame {frame_number}. "
                        f"Score: {self.score_info.team_a_score}-{self.score_info.team_b_score}")
    
    def _determine_scoring_team(self) -> Team:
        """Determine which team scored the point.
        
        This is a simplified implementation. In a full system, this would
        analyze player positions, last contact, etc.
        
        Returns:
            Team that scored the point
        """
        # For now, implement simple alternating logic
        # In a real system, this would be much more sophisticated
        
        if len(self.point_history) == 0:
            # First point - assign to team A
            return Team.TEAM_A
        
        # Simple alternating for demonstration
        # Real implementation would analyze:
        # - Which side of court ball landed on
        # - Last player to touch ball
        # - Out of bounds vs in bounds
        # - Action sequence analysis
        
        last_scoring_team = Team(self.point_history[-1]["scoring_team"])
        
        # For demonstration, alternate between teams
        if last_scoring_team == Team.TEAM_A:
            return Team.TEAM_B
        else:
            return Team.TEAM_A
    
    def _handle_service_rotation(self, scoring_team: Team) -> None:
        """Handle service rotation logic.
        
        Args:
            scoring_team: Team that just scored
        """
        if scoring_team == self.score_info.serving_team:
            # Serving team scored - continue serving
            self.service_streak += 1
        else:
            # Non-serving team scored - service changes
            self.score_info.serving_team = scoring_team
            self.service_streak = 1
            self.logger.debug(f"Service changed to {scoring_team.value}")
    
    def _update_service_tracking(self, current_state: str, frame_number: int) -> None:
        """Update service tracking based on game state.
        
        Args:
            current_state: Current game state
            frame_number: Current frame number
        """
        # Initialize serving team if unknown
        if (self.score_info.serving_team == Team.UNKNOWN and 
            current_state == GameState.GAME_ON.value):
            # Game started - assign initial serving team
            self.score_info.serving_team = Team.TEAM_A
            self.logger.debug("Initialized serving team to TEAM_A")
    
    def _update_rally_tracking(self, current_state: str) -> None:
        """Update rally tracking state.
        
        Args:
            current_state: Current game state
        """
        if current_state == GameState.GAME_ON.value:
            self.rally_in_progress = True
            self.score_info.point_in_progress = True
        elif current_state in [GameState.GAME_OFF.value, GameState.POINT_SCORED.value]:
            self.rally_in_progress = False
            self.score_info.point_in_progress = False
    
    def force_point(self, scoring_team: Team, frame_number: int) -> None:
        """Manually force a point for testing/debugging.
        
        Args:
            scoring_team: Team to award point to
            frame_number: Frame number of the point
        """
        if scoring_team == Team.TEAM_A:
            self.score_info.team_a_score += 1
        elif scoring_team == Team.TEAM_B:
            self.score_info.team_b_score += 1
        
        point_record = {
            "frame": frame_number,
            "scoring_team": scoring_team.value,
            "score_after": (self.score_info.team_a_score, self.score_info.team_b_score),
            "serving_team": self.score_info.serving_team.value,
            "detection_confidence": 1.0,
            "forced": True
        }
        self.point_history.append(point_record)
        
        if self.service_rotation_enabled:
            self._handle_service_rotation(scoring_team)
        
        self.logger.info(f"Forced point for {scoring_team.value} at frame {frame_number}")
    
    def reset(self) -> None:
        """Reset score tracker state."""
        self.score_info = ScoreInfo()
        self.point_history.clear()
        self.last_point_frame = None
        self.rally_in_progress = False
        self.service_streak = 0
        self.last_serving_team = Team.UNKNOWN
        
        self.potential_point_detected = False
        self.point_detection_confidence = 0.0
        self.point_detection_frame = None
        
        self.logger.info("Score tracker reset")
    
    def get_current_score(self) -> ScoreInfo:
        """Get current score information.
        
        Returns:
            Current score information
        """
        return self.score_info
    
    def get_point_history(self) -> List[Dict[str, Any]]:
        """Get history of scored points.
        
        Returns:
            List of point records
        """
        return self.point_history.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scoring statistics.
        
        Returns:
            Statistics dictionary
        """
        total_points = self.score_info.team_a_score + self.score_info.team_b_score
        
        stats = {
            "total_points": total_points,
            "team_a_score": self.score_info.team_a_score,
            "team_b_score": self.score_info.team_b_score,
            "serving_team": self.score_info.serving_team.value,
            "service_streak": self.service_streak,
            "rallies_completed": len(self.point_history),
            "rally_in_progress": self.rally_in_progress
        }
        
        if total_points > 0:
            stats.update({
                "team_a_win_percentage": self.score_info.team_a_score / total_points,
                "team_b_win_percentage": self.score_info.team_b_score / total_points
            })
        
        return stats