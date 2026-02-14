"""
Game state enumeration and data structures for volleyball analysis.

This module defines the core data structures and enumerations used
for game state detection and tracking.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime


class GameState(Enum):
    """Enumeration of possible game states."""
    GAME_OFF = "game_off"              # Between points, timeouts
    GAME_ON = "game_on"                # Active rally in progress  
    SERVE_PREPARATION = "serve_prep"   # Server preparing
    POINT_SCORED = "point_scored"      # Point just scored
    TIMEOUT = "timeout"                # Official timeout


class Team(Enum):
    """Team enumeration."""
    TEAM_A = "team_a"
    TEAM_B = "team_b"
    UNKNOWN = "unknown"


@dataclass
class StateTransition:
    """Represents a game state transition."""
    from_state: GameState
    to_state: GameState
    frame_number: int
    confidence: float
    trigger: str
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "frame": self.frame_number,
            "confidence": self.confidence,
            "trigger": self.trigger,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


@dataclass
class ScoreInfo:
    """Current score information."""
    team_a_score: int = 0
    team_b_score: int = 0
    serving_team: Team = Team.UNKNOWN
    point_in_progress: bool = False
    set_number: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "team_a_score": self.team_a_score,
            "team_b_score": self.team_b_score,
            "serving_team": self.serving_team.value,
            "point_in_progress": self.point_in_progress,
            "set_number": self.set_number
        }


@dataclass
class GameStateInfo:
    """Complete game state information for a frame."""
    current_state: GameState
    state_confidence: float
    state_duration_frames: int
    transitions: List[StateTransition]
    analysis_breakdown: Dict[str, Dict[str, float]]
    score_info: ScoreInfo
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "current_state": self.current_state.value,
            "state_confidence": self.state_confidence,
            "state_duration_frames": self.state_duration_frames,
            "transitions": [t.to_dict() for t in self.transitions],
            "analysis_breakdown": self.analysis_breakdown,
            "score_info": self.score_info.to_dict()
        }


@dataclass
class AnalysisResult:
    """Result from individual analysis modules."""
    confidence_scores: Dict[str, float]
    metadata: Dict[str, Any]
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "confidence_scores": self.confidence_scores,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }