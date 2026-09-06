"""
Game state data structures for volleyball analysis.

Defines the on/off game state machine's public types. The machine itself
lives in ``game_state_manager``; this module keeps the enum/dataclasses so
renderers and exporters can depend on stable shapes.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class GameState(Enum):
    """High-level game flow states.

    The machine is deliberately two-state: ``GAME_OFF`` covers everything
    between points (ball retrieval, practice hits, holds) and ``GAME_ON``
    covers a detected ball-in-play episode. Whether an episode chain counts
    as a scored *point* is decided by the point layer (see ``GamePoint``),
    not by this enum.
    """

    GAME_OFF = "game_off"
    GAME_ON = "game_on"


@dataclass
class GamePoint:
    """A confirmed rally/point segment.

    A rally group (episodes merged across short gaps) becomes a GamePoint
    when at least ``point_min_actions`` classifier actions were detected
    inside it. Practice exchanges without detected contacts stay
    unconfirmed and are never emitted.
    """

    start_frame: int
    end_frame: int
    n_actions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "n_actions": self.n_actions,
        }


@dataclass
class GameStateInfo:
    """Game state snapshot for one processed frame."""

    current_state: GameState
    frame_number: int
    # Frame the current GAME_ON episode started at (backdated to the arming
    # burst), or None while GAME_OFF.
    episode_start_frame: Optional[int] = None
    # Frames of GAME_ON so far in the current episode (0 while off).
    episode_frames: int = 0
    # Confirmed points known SO FAR (finalized groups only; the group that
    # is still open is not listed yet).
    points: List[GamePoint] = field(default_factory=list)
    # True while GAME_ON comes from the fast serve-track (candidate with
    # sustained flight) rather than a fully confirmed episode. Points are
    # unaffected; the live HUD shows it dimmer.
    provisional: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_state": self.current_state.value,
            "frame_number": self.frame_number,
            "episode_start_frame": self.episode_start_frame,
            "episode_frames": self.episode_frames,
            "points": [p.to_dict() for p in self.points],
            "provisional": self.provisional,
        }
