"""
Shared clean overlay drawing for annotated volleyball videos.

Both the batch/live save-video path (`LiveDebugProcessor`) and the standalone
``scripts/test_action_recognition.py`` draw through these helpers so the two
outputs share one minimal layout: court lines (drawn by the caller), a single
ball marker, and player boxes that take the action colour while an action is on
screen. Keeping the drawing here prevents the two entry points from drifting.

Colours are BGR (OpenCV convention).
"""

from typing import Dict, List, Optional, Sequence, Tuple

import cv2

# One colour per recognised action. While an action is on screen the player box
# and its label take the action colour; otherwise the box is plain green.
ACTION_COLORS = {
    "serve": (0, 255, 0),     # green
    "block": (255, 0, 0),     # blue
    "dig": (0, 255, 255),     # yellow
    "set": (255, 255, 0),     # cyan
    "spike": (0, 0, 255),     # red
}

PLAYER_COLOR = (0, 255, 0)          # green box when no action is active
BALL_COLOR = (0, 255, 0)            # green when the ball is detected
BALL_PREDICTED_COLOR = (0, 0, 255)  # red when the position is predicted

# Frames a label stays on screen, counting from its true contact frame.
LABEL_PERSIST = 30


class LabelPlan:
    """Maps track_id -> action labels anchored on their true contact frame.

    The two-layer classifier confirms a contact a few frames late and only
    *emits* it once the next contact arrives (a look-ahead), so an action is
    returned well after its contact -- but each carries its true contact frame
    in ``frame_number``. Feeding actions here keyed by that frame, then querying
    :meth:`active` per rendered frame, makes a label appear on the contact frame
    instead of the later frame it was emitted on. Used by the two-pass save
    render, the buffered live render, and ``test_action_recognition.py`` so all
    three anchor labels identically.
    """

    def __init__(self, persist: int = LABEL_PERSIST):
        self.persist = persist
        self._by_track: Dict[int, List[Tuple[int, str, Optional[float]]]] = {}

    def add(self, track_id: Optional[int], contact_frame: Optional[int],
            action: str, confidence: Optional[float] = None) -> None:
        """Record an action at its true contact frame (ignored if either is None)."""
        if track_id is None or contact_frame is None:
            return
        self._by_track.setdefault(track_id, []).append((contact_frame, action, confidence))

    def active(self, track_id: int, frame_idx: int) -> Optional[Tuple[str, Optional[float]]]:
        """Most-recent ``(action, confidence)`` whose window covers ``frame_idx``, else None."""
        best_cf, best = -1, None
        for cf, action, conf in self._by_track.get(track_id, []):
            if cf <= frame_idx < cf + self.persist and cf > best_cf:
                best_cf, best = cf, (action, conf)
        return best


def draw_ball(frame, x: float, y: float, predicted: bool = False) -> None:
    """Draw the tracked ball as a single filled circle (in place)."""
    color = BALL_PREDICTED_COLOR if predicted else BALL_COLOR
    cv2.circle(frame, (int(x), int(y)), 8, color, -1)


def draw_player(
    frame,
    track_id: int,
    bbox: Sequence[float],
    action: Optional[str] = None,
    confidence: Optional[float] = None,
) -> None:
    """Draw a player box + id, tinted to the action colour when acting.

    Args:
        frame: BGR frame, drawn in place.
        track_id: Stable player id (shown as ``P<id>``).
        bbox: ``(x1, y1, x2, y2)`` box in pixels.
        action: Action name if one is currently on screen for this player;
            ``None`` leaves the box green with no action label.
        confidence: Action confidence, appended to the label when provided.
    """
    x1, y1, x2, y2 = (int(v) for v in bbox)
    box_color = ACTION_COLORS.get(action, PLAYER_COLOR) if action else PLAYER_COLOR

    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
    if action:
        conf_str = f" ({confidence:.2f})" if confidence is not None else ""
        cv2.putText(frame, f"{action}{conf_str}", (x1, y1 - 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)
    cv2.putText(frame, f"P{track_id}", (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, PLAYER_COLOR, 1)


def draw_frame_counter(frame, frame_idx: int, total: Optional[int] = None) -> None:
    """Draw a small frame counter in the top-right corner (in place).

    Events are referenced by frame number throughout the project (GT
    annotations, STATUS.md, eval reports), so burning the number into each
    rendered frame keeps live scrubbing cross-referenceable. White text over
    a thin black underlay so it reads on bright sand and dark backgrounds
    alike. ``total`` (frame count) is appended when known and non-zero.
    """
    label = f"f{frame_idx}" if not total else f"f{frame_idx}/{total}"
    (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    org = (frame.shape[1] - tw - 12, 28)
    cv2.putText(frame, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4)
    cv2.putText(frame, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
