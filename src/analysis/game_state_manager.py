"""
Game state manager for volleyball video analysis.

This module coordinates multiple analysis modules to detect and track
game state transitions, providing comprehensive game flow understanding.
"""

from typing import Dict, Any, List, Optional
from collections import deque
import logging
from datetime import datetime

from .game_state import (
    GameState, GameStateInfo, StateTransition, ScoreInfo, Team, AnalysisResult
)
from .action_sequence_analyzer import ActionSequenceAnalyzer
from .trajectory_state_analyzer import TrajectoryStateAnalyzer
from .temporal_activity_analyzer import TemporalActivityAnalyzer
from .score_tracker import ScoreTracker


class GameStateManager:
    """Central coordinator for game state detection using multiple modalities."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the game state manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config.get("game_state_detection", {})
        self.logger = logging.getLogger(__name__)
        
        # Configuration parameters
        self.enabled = self.config.get("enabled", True)
        self.serve_threshold = self.config.get("serve_threshold", 0.7)
        self.point_end_threshold = self.config.get("point_end_threshold", 0.6)
        self.min_state_duration_frames = self.config.get("min_state_duration_frames", 10)
        self.activity_gap_threshold_seconds = self.config.get("activity_gap_threshold_seconds", 3.0)
        
        # Current state
        self.current_state = GameState.GAME_OFF
        self.state_confidence = 0.0
        self.state_duration_frames = 0
        self.state_start_frame = 0
        
        # State history
        self.state_history = deque(maxlen=100)
        self.transitions = []
        
        # Initialize analysis modules
        if self.enabled:
            self._initialize_analyzers(config)
        else:
            self.logger.info("Game state detection disabled")
            self.action_analyzer = None
            self.trajectory_analyzer = None
            self.temporal_analyzer = None
            self.score_tracker = None
        
        # Frame tracking
        self.fps = 30.0  # Will be updated from video info
        self.current_frame = 0
    
    def _initialize_analyzers(self, config: Dict[str, Any]) -> None:
        """Initialize all analysis modules.
        
        Args:
            config: Full configuration dictionary
        """
        try:
            self.action_analyzer = ActionSequenceAnalyzer(config)
            self.trajectory_analyzer = TrajectoryStateAnalyzer(config)
            self.temporal_analyzer = TemporalActivityAnalyzer(config)
            self.score_tracker = ScoreTracker(config)
            
            self.logger.info("Game state analysis modules initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize game state analyzers: {e}")
            raise
    
    def analyze_frame(self, frame_result: Dict[str, Any], frame_number: int) -> GameStateInfo:
        """Analyze frame for game state and return complete state information.
        
        Args:
            frame_result: Frame processing results from video processor
            frame_number: Current frame number
            
        Returns:
            Complete game state information
        """
        if not self.enabled:
            # Return default state info if disabled
            return GameStateInfo(
                current_state=GameState.GAME_OFF,
                state_confidence=0.0,
                state_duration_frames=0,
                transitions=[],
                analysis_breakdown={},
                score_info=ScoreInfo()
            )
        
        self.current_frame = frame_number
        
        try:
            # Run all analysis modules
            analysis_results = self._run_analysis_modules(frame_result, frame_number)
            
            # Update game state based on analysis
            new_state = self._update_game_state(analysis_results)
            
            # Handle state transitions
            transitions = self._handle_state_transitions(new_state, frame_number)
            
            # Update score tracking
            current_game_state_info = {
                "current_state": self.current_state.value,
                "analysis_breakdown": {
                    name: result.confidence_scores 
                    for name, result in analysis_results.items()
                }
            }
            score_info = self.score_tracker.analyze_frame(
                frame_result, current_game_state_info, frame_number
            )
            
            # Create complete state information
            game_state_info = GameStateInfo(
                current_state=self.current_state,
                state_confidence=self.state_confidence,
                state_duration_frames=self.state_duration_frames,
                transitions=transitions,
                analysis_breakdown={
                    name: result.confidence_scores 
                    for name, result in analysis_results.items()
                },
                score_info=score_info
            )
            
            # Update state history
            self.state_history.append({
                "frame": frame_number,
                "state": self.current_state.value,
                "confidence": self.state_confidence,
                "timestamp": datetime.now()
            })
            
            return game_state_info
            
        except Exception as e:
            self.logger.error(f"Error in game state analysis at frame {frame_number}: {e}")
            # Return safe default state
            return GameStateInfo(
                current_state=GameState.GAME_OFF,
                state_confidence=0.0,
                state_duration_frames=0,
                transitions=[],
                analysis_breakdown={},
                score_info=ScoreInfo()
            )
    
    def _run_analysis_modules(self, frame_result: Dict[str, Any], 
                            frame_number: int) -> Dict[str, AnalysisResult]:
        """Run all analysis modules on the current frame.
        
        Args:
            frame_result: Frame processing results
            frame_number: Current frame number
            
        Returns:
            Dictionary of analysis results from each module
        """
        results = {}
        
        # Action sequence analysis
        if self.action_analyzer:
            results["action_sequence"] = self.action_analyzer.analyze_frame(
                frame_result, frame_number
            )
        
        # Trajectory analysis
        if self.trajectory_analyzer:
            results["trajectory"] = self.trajectory_analyzer.analyze_frame(
                frame_result, frame_number
            )
        
        # Temporal activity analysis
        if self.temporal_analyzer:
            results["temporal"] = self.temporal_analyzer.analyze_frame(
                frame_result, frame_number
            )
        
        return results
    
    def _update_game_state(self, analysis_results: Dict[str, AnalysisResult]) -> GameState:
        """Update game state based on multi-modal analysis results.
        
        Args:
            analysis_results: Results from all analysis modules
            
        Returns:
            New game state
        """
        # Extract confidence scores from each analyzer
        action_confidence = analysis_results.get("action_sequence", AnalysisResult({}, {})).confidence_scores
        trajectory_confidence = analysis_results.get("trajectory", AnalysisResult({}, {})).confidence_scores
        temporal_confidence = analysis_results.get("temporal", AnalysisResult({}, {})).confidence_scores
        
        # Apply state transition logic
        new_state = self.current_state
        new_confidence = self.state_confidence
        
        if self.current_state == GameState.GAME_OFF:
            # Check for game starting (serve detected)
            serve_probability = (
                action_confidence.get("serve_detected", 0.0) * 0.4 +
                trajectory_confidence.get("serve_trajectory", 0.0) * 0.4 +
                temporal_confidence.get("activity_resuming", 0.0) * 0.2
            )
            
            if serve_probability > self.serve_threshold:
                new_state = GameState.GAME_ON
                new_confidence = serve_probability
                self.logger.debug(f"State transition to GAME_ON with confidence {serve_probability:.2f}")
        
        elif self.current_state == GameState.GAME_ON:
            # Check for point ending
            point_end_probability = (
                action_confidence.get("rally_end_pattern", 0.0) * 0.3 +
                trajectory_confidence.get("point_ending", 0.0) * 0.5 +
                temporal_confidence.get("extended_pause", 0.0) * 0.2
            )
            
            if point_end_probability > self.point_end_threshold:
                new_state = GameState.POINT_SCORED
                new_confidence = point_end_probability
                self.logger.debug(f"State transition to POINT_SCORED with confidence {point_end_probability:.2f}")
            else:
                # Update confidence for ongoing rally
                rally_confidence = (
                    action_confidence.get("rally_active", 0.0) * 0.5 +
                    trajectory_confidence.get("ball_in_play", 0.0) * 0.3 +
                    temporal_confidence.get("activity_level", 0.0) * 0.2
                )
                new_confidence = max(rally_confidence, 0.3)  # Minimum confidence for active rally
        
        elif self.current_state == GameState.POINT_SCORED:
            # Transition back to GAME_OFF after point
            new_state = GameState.GAME_OFF
            new_confidence = 0.8
            self.logger.debug("State transition to GAME_OFF after point scored")
        
        # Apply temporal smoothing to prevent rapid state changes
        new_state = self._apply_temporal_smoothing(new_state)
        
        # Update state tracking
        if new_state != self.current_state:
            self.state_start_frame = self.current_frame
            self.state_duration_frames = 0
        else:
            self.state_duration_frames = self.current_frame - self.state_start_frame
        
        self.state_confidence = new_confidence
        
        return new_state
    
    def _apply_temporal_smoothing(self, new_state: GameState) -> GameState:
        """Apply temporal smoothing to prevent rapid state changes.
        
        Args:
            new_state: Proposed new state
            
        Returns:
            Smoothed state (may be current state if change too rapid)
        """
        # Require minimum duration before allowing state change
        if (new_state != self.current_state and 
            self.state_duration_frames < self.min_state_duration_frames):
            # Keep current state if minimum duration not met
            return self.current_state
        
        return new_state
    
    def _handle_state_transitions(self, new_state: GameState, 
                                frame_number: int) -> List[StateTransition]:
        """Handle state transitions and record them.
        
        Args:
            new_state: New game state
            frame_number: Current frame number
            
        Returns:
            List of state transitions for this frame
        """
        transitions = []
        
        if new_state != self.current_state:
            # Create transition record
            transition = StateTransition(
                from_state=self.current_state,
                to_state=new_state,
                frame_number=frame_number,
                confidence=self.state_confidence,
                trigger=self._determine_transition_trigger(self.current_state, new_state),
                timestamp=datetime.now()
            )
            
            transitions.append(transition)
            self.transitions.append(transition)
            
            self.logger.info(f"Game state transition: {self.current_state.value} → {new_state.value} "
                           f"(frame {frame_number}, confidence {self.state_confidence:.2f})")
            
            # Update current state
            self.current_state = new_state
        
        return transitions
    
    def _determine_transition_trigger(self, from_state: GameState, to_state: GameState) -> str:
        """Determine what triggered a state transition.
        
        Args:
            from_state: Previous state
            to_state: New state
            
        Returns:
            String describing the trigger
        """
        if from_state == GameState.GAME_OFF and to_state == GameState.GAME_ON:
            return "serve_detected"
        elif from_state == GameState.GAME_ON and to_state == GameState.POINT_SCORED:
            return "point_ending_detected"
        elif from_state == GameState.POINT_SCORED and to_state == GameState.GAME_OFF:
            return "point_completed"
        else:
            return "state_machine_logic"
    
    def set_video_info(self, fps: float, width: int, height: int) -> None:
        """Set video information for all analyzers.
        
        Args:
            fps: Video frame rate
            width: Video width
            height: Video height
        """
        self.fps = fps
        
        if self.enabled:
            if self.temporal_analyzer:
                self.temporal_analyzer.set_fps(fps)
            
            if self.trajectory_analyzer:
                self.trajectory_analyzer.set_frame_dimensions(width, height)
        
        self.logger.debug(f"Updated video info: {fps} FPS, {width}x{height}")
    
    def set_court_boundaries(self, court_bounds: Dict[str, float]) -> None:
        """Set court boundary information.
        
        Args:
            court_bounds: Court boundary coordinates
        """
        if self.enabled and self.trajectory_analyzer:
            self.trajectory_analyzer.set_court_boundaries(court_bounds)
    
    def reset(self) -> None:
        """Reset all game state tracking."""
        self.current_state = GameState.GAME_OFF
        self.state_confidence = 0.0
        self.state_duration_frames = 0
        self.state_start_frame = 0
        
        self.state_history.clear()
        self.transitions.clear()
        
        if self.enabled:
            if self.action_analyzer:
                self.action_analyzer.reset()
            if self.trajectory_analyzer:
                self.trajectory_analyzer.reset()
            if self.temporal_analyzer:
                self.temporal_analyzer.reset()
            if self.score_tracker:
                self.score_tracker.reset()
        
        self.logger.info("Game state manager reset")
    
    def get_current_state(self) -> GameState:
        """Get current game state.
        
        Returns:
            Current game state
        """
        return self.current_state
    
    def get_score_info(self) -> ScoreInfo:
        """Get current score information.
        
        Returns:
            Current score information
        """
        if self.enabled and self.score_tracker:
            return self.score_tracker.get_current_score()
        else:
            return ScoreInfo()
    
    def get_transitions(self) -> List[StateTransition]:
        """Get all state transitions.
        
        Returns:
            List of state transitions
        """
        return self.transitions.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all modules.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "enabled": self.enabled,
            "current_state": self.current_state.value,
            "state_confidence": self.state_confidence,
            "state_duration_frames": self.state_duration_frames,
            "total_transitions": len(self.transitions)
        }
        
        if self.enabled:
            # Add module-specific statistics
            if self.action_analyzer:
                stats["action_sequence"] = self.action_analyzer.get_statistics()
            
            if self.trajectory_analyzer:
                stats["trajectory"] = self.trajectory_analyzer.get_statistics()
            
            if self.temporal_analyzer:
                stats["temporal"] = self.temporal_analyzer.get_statistics()
            
            if self.score_tracker:
                stats["score_tracking"] = self.score_tracker.get_statistics()
            
            # Transition statistics
            transition_types = {}
            for transition in self.transitions:
                trigger = transition.trigger
                transition_types[trigger] = transition_types.get(trigger, 0) + 1
            
            stats["transition_types"] = transition_types
        
        return stats