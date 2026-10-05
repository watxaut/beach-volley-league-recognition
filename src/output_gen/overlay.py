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
import numpy as np

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

# Ball-side possession label (#77): which half the ball is in (near/far)
# and whether it is inside the net-crossing band. BGR like everything else.
POSSESSION_NEAR_COLOR = (0, 220, 0)      # green
POSSESSION_FAR_COLOR = (0, 140, 255)     # orange
POSSESSION_CROSSING_COLOR = (0, 230, 230)  # yellow while crossing
POSSESSION_UNKNOWN_COLOR = (200, 200, 200)

# Ball ground-contact label (#80): GROUND / OUT / AIR next to the tracked
# ball, plus the per-candidate groundedness tag in the live-debug ``b``
# overlay. BGR like everything else.
GROUND_STATE_COLOR = (0, 165, 255)     # orange: resting on the sand
GROUND_OUT_COLOR = (0, 0, 255)         # red: grounded outside the court
GROUND_AIR_COLOR = (255, 255, 255)     # white: in flight
GROUND_HELD_COLOR = (160, 160, 160)    # gray: held state (no fresh read)

# Typed spike labels reuse the spike colour (cv2 text is ASCII-only, hence
# "spike hard"/"spike touch" rather than a middle dot).
ACTION_COLORS["spike hard"] = (0, 0, 255)
ACTION_COLORS["spike touch"] = (0, 0, 255)

# Frames a label stays on screen, counting from its true contact frame.
LABEL_PERSIST = 30

# Ball trail after a spike: red, fading as each point ages, gone past max age.
# --- ball-candidate markers (live debug only, toggle 'b') ---------------
# Every ball the DETECTOR saw this frame, not just the tracked one: a hollow
# box per candidate with its confidence beside it. The colours are chosen
# outside the action palette (green/blue/yellow/cyan/red) and the boxes are
# hollow (the tracked ball is a FILLED circle), so a candidate can never be
# read as the ball in play or as a player action tint.
CANDIDATE_COLOR = (255, 0, 255)       # magenta: plain candidate
CANDIDATE_SUSPECT_COLOR = (0, 165, 255)   # BGR orange: detector flagged it stationary
CANDIDATE_REMOVED_COLOR = (170, 170, 170)  # grey: static suppression dropped it
CANDIDATE_FLAG_TEXT = {"sus": "sus", "rm": "rm"}
# Half-size of the fallback box used when a detection carries no bbox.
CANDIDATE_HALF = 7

TRAIL_COLOR = (0, 0, 255)
TRAIL_MAX_AGE = 45
TRAIL_MAX_GAP_FRAMES = 8  # no connecting line across sighting gaps larger than this


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
        """Record an action at its true contact frame (ignored if either is None).

        Re-adding the same (track, contact frame) replaces the earlier entry,
        so late-resolving knowledge (e.g. a spike's touch/hard type, final only
        after its outcome) can upgrade a label already on screen.
        """
        if track_id is None or contact_frame is None:
            return
        entries = self._by_track.setdefault(track_id, [])
        entries[:] = [e for e in entries if e[0] != contact_frame]
        entries.append((contact_frame, action, confidence))

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


def draw_ball_candidate(
    frame,
    bbox: Optional[Sequence[float]] = None,
    center: Optional[Sequence[float]] = None,
    confidence: Optional[float] = None,
    flag: str = "",
    ground: Optional[str] = None,
) -> None:
    """Draw ONE un-tracked ball candidate: a hollow box + its confidence.

    Display-only annotation (the live-debug ``b`` overlay); it says nothing the
    pipeline does not already know -- ``flag`` carries the detector's own verdict
    (``"sus"`` = stationary suspect, ``"rm"`` = removed by static suppression, so
    the tracker never saw it) rather than re-deriving a threshold here.

    Args:
        frame: BGR frame, drawn in place.
        bbox: ``(x1, y1, x2, y2)`` detection box, when it has one.
        center: ``(x, y)`` used to place the box when ``bbox`` is missing/short.
        confidence: Detector confidence; ``None`` renders as "-".
        flag: ``""`` / ``"sus"`` / ``"rm"`` -- tints the box and suffixes the label.
        ground: per-box groundedness verdict (#80) -- ``"ground"`` / ``"air"`` /
            ``None`` (band or unmeasurable); rendered as ``GND`` / ``AIR`` after
            the flag, so parked balls can be told from the ball in play by eye.
    """
    color = (CANDIDATE_SUSPECT_COLOR if flag == "sus"
             else CANDIDATE_REMOVED_COLOR if flag == "rm"
             else CANDIDATE_COLOR)
    h, w = frame.shape[:2]
    if bbox is not None and len(bbox) == 4:
        x1, y1, x2, y2 = (int(round(float(v))) for v in bbox)
    elif center is not None and len(center) >= 2:
        cx, cy = int(round(float(center[0]))), int(round(float(center[1])))
        x1, y1, x2, y2 = cx - CANDIDATE_HALF, cy - CANDIDATE_HALF, cx + CANDIDATE_HALF, cy + CANDIDATE_HALF
    else:
        return                       # nothing placeable: skip rather than draw at 0,0
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    x1, y1 = max(0, x1 - 2), max(0, y1 - 2)
    x2, y2 = min(w - 1, x2 + 2), min(h - 1, y2 + 2)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)

    conf_txt = "-" if confidence is None else f"{float(confidence):.2f}"
    suffix = CANDIDATE_FLAG_TEXT.get(flag, "")
    if ground == "ground":
        suffix = f"{suffix} GND".strip()
    elif ground == "air":
        suffix = f"{suffix} AIR".strip()
    label = f"{conf_txt} {suffix}".strip()
    org = (x1, max(12, y1 - 4))
    cv2.putText(frame, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
    cv2.putText(frame, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)


def draw_ball_trail(
    frame,
    points: Sequence[Tuple[float, float, int]],
    max_age: int = TRAIL_MAX_AGE,
) -> None:
    """Draw a spike's ball flight as a red trail that faints over frames.

    Args:
        frame: BGR frame, drawn in place.
        points: ``(x, y, age_frames)`` flight points (as produced by
            ``SpikeAnalyzer.trail_points``), in flight order.
        max_age: age at which a point has fully faded (skipped beyond).

    Each segment is blended into the frame with alpha ``1 - age/max_age`` on
    the line's pixels ONLY (a masked blend -- OpenCV lines carry no alpha,
    and blending a whole addWeighted ROI darkens the rectangle around the
    line to a visible black box). Segments are not drawn across sighting
    gaps larger than ``TRAIL_MAX_GAP_FRAMES``.
    """
    pts = [(int(x), int(y), age) for (x, y, age) in points if 0 <= age < max_age]
    for (x0, y0, a0), (x1, y1, a1) in zip(pts, pts[1:]):
        # No connecting line across an occlusion-sized gap in the flight.
        if abs(a1 - a0) > TRAIL_MAX_GAP_FRAMES:
            continue
        alpha = max(0.1, 1.0 - max(a0, a1) / float(max_age))
        x_min, x_max = min(x0, x1), max(x0, x1)
        y_min, y_max = min(y0, y1), max(y0, y1)
        pad = 2
        rx0, rx1 = max(0, x_min - pad), min(frame.shape[1], x_max + pad + 1)
        ry0, ry1 = max(0, y_min - pad), min(frame.shape[0], y_max + pad + 1)
        if rx1 <= rx0 or ry1 <= ry0:
            continue
        roi = frame[ry0:ry1, rx0:rx1]
        scratch = np.zeros_like(roi)
        cv2.line(
            scratch, (x0 - rx0, y0 - ry0), (x1 - rx0, y1 - ry0),
            TRAIL_COLOR, 2, lineType=cv2.LINE_AA,
        )
        mask = scratch[..., 2] > 0  # pixels the line touched (incl. AA fringe)
        blended = (
            roi * (1.0 - alpha) + scratch.astype(np.float32) * alpha
        ).astype(roi.dtype)
        roi[mask] = blended[mask]


def draw_kill_marker(frame, x: float, y: float, text: str) -> None:
    """Draw a kill annotation at the landing point (red, black underlay)."""
    org = (int(x) + 12, int(y) - 12)
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.7, TRAIL_COLOR, 2)


# Squad display palette (E3): color follows the TEAM (enrollment-time squad,
# owner convention), NOT the current side -- a side switch shows the blue pair
# moving to the far side. Team A (P1A, P2A) is blue, team B (P1B, P2B) is red;
# within a team the two players are a light and a saturated shade. Both are
# bright enough to read on the black label plate (no navy / maroon).
# BGR values: light blue #64C8FF, vivid blue #1E90FF, light red #FF968C,
# vivid red #FF4545.
PLAYER_SQUAD_COLORS = {
    (1, "A"): (255, 200, 100),   # P1A light blue
    (1, "B"): (255, 144, 30),    # P2A vivid blue
    (2, "A"): (140, 150, 255),   # P1B light red
    (2, "B"): (69, 69, 255),     # P2B vivid red
}


def player_box_style(player: Optional[dict]):
    """(box_color, label) for a tracked-player dict, or (None, None).

    Uses the enrollment identity when present (P1A..P2B + squad color);
    otherwise returns (None, None) and the caller falls back to today's
    green ``P<id>`` display (fallback videos, pre-lock temps, unlabeled
    tracks).
    """
    if not isinstance(player, dict):
        return None, None
    squad, slot = player.get("squad"), player.get("slot")
    label = player.get("player_label")
    if not label or squad is None:
        return None, None
    return PLAYER_SQUAD_COLORS.get((squad, slot)), label


def draw_player(
    frame,
    track_id: int,
    bbox: Sequence[float],
    action: Optional[str] = None,
    confidence: Optional[float] = None,
    color: Optional[tuple] = None,
    label: Optional[str] = None,
) -> None:
    """Draw a player box + id, tinted to the action colour when acting.

    Args:
        frame: BGR frame, drawn in place.
        track_id: Stable player id (shown as ``P<id>`` unless ``label``).
        bbox: ``(x1, y1, x2, y2)`` box in pixels.
        action: Action name if one is currently on screen for this player;
            ``None`` leaves the box green with no action label.
        confidence: Action confidence, appended to the label when provided.
        color: Explicit box/text colour (enrollment squad colour). When given,
            it takes precedence over the action tint -- identity colour is
            stable, the action is carried by the text label instead.
        label: Explicit id text (``P1A``..); defaults to ``P<track_id>``.
    """
    x1, y1, x2, y2 = (int(v) for v in bbox)
    if color is not None:
        box_color = id_color = color
    else:
        box_color = ACTION_COLORS.get(action, PLAYER_COLOR) if action else PLAYER_COLOR
        id_color = PLAYER_COLOR
    id_text = label or f"P{track_id}"

    def _plate_text(text, org, scale, text_color, thickness):
        """Text on a filled black plate (owner request 2026-10-06: bright sand
        + thin court lines make bare text unreadable)."""
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
        ox, oy = org
        cv2.rectangle(frame, (ox - 2, oy - th - 3), (ox + tw + 2, oy + 3), (0, 0, 0), -1)
        cv2.putText(frame, text, (ox, oy), cv2.FONT_HERSHEY_SIMPLEX, scale,
                    text_color, thickness)

    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
    if action:
        conf_str = f" ({confidence:.2f})" if confidence is not None else ""
        action_color = box_color if color is not None else ACTION_COLORS.get(action, PLAYER_COLOR)
        _plate_text(f"{action}{conf_str}", (x1, y1 - 25), 0.6, action_color, 2)
    _plate_text(id_text, (x1, y1 - 8), 0.5, id_color, 1)


def draw_frame_counter(frame, frame_idx: int, total: Optional[int] = None) -> None:
    """Draw the frame counter on a black plate in the top-right corner (in place).

    Events are referenced by frame number throughout the project (GT
    annotations, STATUS.md, eval reports), so burning the number into each
    rendered frame keeps live scrubbing cross-referenceable. The plate is a
    solid black rectangle (drawn first, like the game-state badge) so the
    number reads the same on blown-out sand, dark background and the live
    debug panel's own strip -- the thin black text underlay alone was not
    enough contrast over bright pixels at this size. Scale is 0.60 (was
    0.55: +1 px cap height). ``total`` (frame count) is appended when known
    and non-zero.
    """
    label = f"f{frame_idx}" if not total else f"f{frame_idx}/{total}"
    scale = 0.6
    (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    x, y = frame.shape[1] - tw - 12, 28          # y = text baseline
    cv2.rectangle(frame, (x - 8, y - th - 8), (x + tw + 8, y + baseline), (0, 0, 0), -1)
    cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 4)
    cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1)


def draw_game_state(frame, state: str, points: int = 0, provisional: bool = False) -> None:
    """Draw the game on/off badge in the top-left corner (in place).

    ``state`` is the game-state machine's value for the frame being drawn
    ("game_on"/"game_off"); ``points`` is the count of confirmed points so
    far. ``provisional`` dims the badge -- GAME_ON from the fast serve-track
    before the episode is fully confirmed. Render-only -- the machine itself
    lives in the pipeline.

    The badge sits on a solid black plate on its own line BELOW the court
    overlay's "Court: CALIBRATED" text (which owns the top-left line at
    y=30), so the two never overprint each other.
    """
    label = "GAME ON" if state == "game_on" else "GAME OFF"
    if points:
        label += f"  P{points}"
    if provisional:
        label += " ~"
    color = (60, 220, 60) if state == "game_on" else (160, 160, 160)
    if provisional:
        color = (120, 200, 120)
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    x, y = 12, 62  # text baseline; keeps clear of CALIBRATED (baseline y=30)
    cv2.rectangle(frame, (x - 8, y - th - 8), (x + tw + 8, y + 8), (0, 0, 0), -1)
    cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4)
    cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)


def draw_possession(frame, possession: Optional[Dict[str, object]]) -> None:
    """Draw the ball-side possession label + CROSSING tag (in place, #77).

    ``possession`` is the per-frame ``BallSidePossessionObserver.observe``
    row cached by live debug (side/crossing). The side shown is the LAST
    COMMITTED side (the observer holds it while the ball is lost or
    predicted); ``CROSSING`` is appended in yellow while the ball is inside
    the net band between committed sides. Sits top-left BELOW the game
    badge on its own black plate. Pure render: never reads observer state.
    """
    if not possession:
        return
    side = possession.get("side")
    crossing = bool(possession.get("crossing"))
    label = f"possession: {str(side).upper()}" if side else "possession: --"
    color = (POSSESSION_NEAR_COLOR if side == "near"
             else POSSESSION_FAR_COLOR if side == "far"
             else POSSESSION_UNKNOWN_COLOR)
    scale = 0.55
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    x, y = 12, 94  # text baseline; one line below the game badge (y=62)
    pad = 8
    extra = 0
    if crossing:
        (cw, _), _ = cv2.getTextSize("CROSSING", cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
        extra = cw + 18
    cv2.rectangle(frame, (x - pad, y - th - pad),
                  (x + tw + extra + pad, y + pad), (0, 0, 0), -1)
    cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 4)
    cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1)
    if crossing:
        cv2.putText(frame, "CROSSING", (x + tw + 18, y), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, (0, 0, 0), 4)
        cv2.putText(frame, "CROSSING", (x + tw + 18, y), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, POSSESSION_CROSSING_COLOR, 1)


def draw_ball_ground(frame, x: float, y: float,
                     ground: Optional[Dict[str, object]]) -> None:
    """Draw the tracked ball's ground-contact label (in place, #80).

    ``ground`` is the per-frame ``BallGroundContactObserver.observe`` row
    cached by live debug. ``GROUND`` (resting on the sand, inside the
    court), ``OUT`` (grounded outside the court rect + margin), or
    ``AIR n.nn`` (airborne; the number is the groundedness ratio -- how
    many ball-diameters wider than a resting ball it measures, growing
    with height). A held row (no fresh read: ball lost/predicted) renders
    the short state in gray, so a stale label is never mistaken for a live
    one. Pure render: never reads observer state.
    """
    if not ground:
        return
    state = ground.get("state")
    if state not in ("ground", "out", "air"):
        return
    ratio = ground.get("ratio")
    held = bool(ground.get("held"))
    if held:
        label = {"ground": "GND", "out": "OUT", "air": "AIR"}[state]
        color = GROUND_HELD_COLOR
    elif state == "ground":
        label, color = "GROUND", GROUND_STATE_COLOR
    elif state == "out":
        label, color = "OUT", GROUND_OUT_COLOR
    else:
        label = f"AIR {ratio:.2f}" if ratio else "AIR"
        color = GROUND_AIR_COLOR
    scale = 0.5
    org = (int(x) + 12, int(y) - 10)
    cv2.putText(frame, label, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3)
    cv2.putText(frame, label, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1)
