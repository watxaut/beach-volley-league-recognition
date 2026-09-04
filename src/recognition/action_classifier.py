"""
Visual layer of the two-layer action recognizer for beach volleyball.

Action recognition is split into two layers (see also `action_context.py`):

  Layer 1 -- THIS module -- watches the ball-in-play trajectory and fires only
  at ball *contacts*, then reports the *context-free* :class:`VisualGesture`:
  what the body/ball did, independent of the rally. A contact is a bottom-of-arc
  (ball falls to a player and is sent back up) or a horizontal redirect (ball
  deflected sideways without rising); every candidate must have a player within
  reach, which rejects the arc's natural apex. The gesture is read from:
    - **Ball motion** around the contact (a sideways drive vs a fall-and-rise);
    - **Court geometry** (near the net?) via :class:`CourtCalibration`;
    - **Pose** (when MediaPipe returns it) -- overhead hands support a block.
  The gestures are deliberately coarse: BUMP_SET, ATTACK, BLOCK. A bump-set is
  ambiguous on purpose -- it could be a dig, a set, or an overpass.

  Layer 2 -- :class:`ActionContextResolver` -- turns a sequence of gestures into
  canonical actions (dig/set/spike/block/serve/overpass) using rally state
  (touch number + previous/next contact). Because it needs a one-contact
  look-ahead, this class holds each contact back until the next one arrives and
  finalises it then; call :meth:`flush` at end of video for the last one.

Requires a :class:`CourtCalibration` instance for spatial context. Works without
pose (falls back to ball motion).
"""

from typing import List, Dict, Any, Optional, Tuple
from collections import deque
import numpy as np
import logging

from .pose_estimator import PoseEstimator
from .volleyball_actions import VisualGesture
from .action_context import ActionContextResolver


class ActionClassifier:
    """Event-driven volleyball action classifier.

    Actions are emitted only at detected ball contacts. Because a contact is
    confirmed once the ball trajectory is seen on both sides of it, events are
    finalised a few frames late and reported at their true contact frame via the
    ``frame_number`` field of each result.
    """

    # --- Contact-detection tuning ---
    MIN_CONTACT_GAP = 9      # min frames between successive contacts
    CONTACT_DELAY = 7        # frames to wait before confirming a contact
    NEIGH = 7                # frames each side used to test a contact vertex
    MIN_PROMINENCE = 26.0    # px the ball must rise on both sides of a bounce
    XREV_MIN = 20.0          # px net horizontal displacement for a redirect
    CONTACT_REACH = 140.0    # max px from ball to nearest player's bbox (arm reach)

    # --- Gap-bridged bounce ---
    # The ball is often UNDETECTED across a touch (occluded by the toucher's
    # own body/hands -- entreno_5 f111: real sightings stop falling at f102 and
    # resume rising at f114, the set itself invisible). With no vertex sighting
    # _detect_contact can never fire, and the missed touch corrupts the whole
    # downstream touch-counting (one missed set turned spike->dig->set->dig in
    # a cascade). The bridge fires only where the normal detector PROVABLY
    # cannot: a sighting gap of at least BRIDGE_SHORT_MIN_GAP frames has no
    # frame with a vertex AND no frame with >=2 real points within NEIGH on
    # both sides, so small flicker gaps (which the normal path handles) are
    # left alone -- on entreno_1/3/4 histories these gates yield ZERO
    # candidates, keeping their validated contact streams byte-identical.
    BRIDGE_SHORT_MIN_GAP = 5  # frames; SHORT-gap band floor (see _bridge_contact)
    BRIDGE_MIN_GAP = 8       # frames; classic band floor -- below this the bridge
                             # needs the extra short-band gates (sparse sides +
                             # ball identity continuity)
    BRIDGE_MAX_GAP = 14      # frames; beyond this the touch is too uncertain to place
    BRIDGE_WINDOW = 6        # frames of real sightings each side used to shape-check
    BRIDGE_MIN_DROP = 20.0   # px net descent into the gap over the left window
    BRIDGE_MIN_RISE = 60.0   # px net ascent out of the gap over the right window
                             # (a sand bounce rebounds low: e5 f332-340 rises 25px
                             # and must NOT read as a touch; a set toss rises 140+)
    BRIDGE_X_CONT_PX = 24.0      # short-band ball-identity continuity: max |dx|
    BRIDGE_X_CONT_PER_F = 3.0    # between the last pre-gap and first post-gap
                                 # sighting (a spare ball appearing elsewhere must
                                 # not bridge -- e6 f236/f289, e5 f320/f325)

    # --- Reentry contact (the touch happened where the ball was not visible) ---
    # A hard contact can happen out of sight: a spiker meets the set toss ABOVE
    # the frame top and the joust impulse sits behind the net tape while the
    # ball tracker is lost. The tracker gives up after max_missing_frames and
    # often adopts a SPARE ball; when it re-locks the game ball, _ball_history
    # shows a long sighting gap whose endpoints free flight cannot connect,
    # followed by a fast horizontal run at/above the net tape (e6: spare junk
    # at f302 (34,118) -> game ball at f314 (1152,278) running -48px/f, the
    # joust impulse vx +3 -> -50 hidden in between; the real re-entry descent
    # f301-310 never reached the history). The normal tests cannot fire (the
    # gap leaves <2 left points within NEIGH) and both bridge bands refuse
    # (shape/identity gates). This band manufactures the touch:
    #   * gap in [REENTRY_MIN_GAP, REENTRY_MAX_GAP] -- shorter gaps are the
    #     bridges' turf, longer ones are dead-ball/serve territory;
    #   * >=REENTRY_MIN_RUN real points after the gap moving at attack scale
    #     (>= REENTRY_MIN_SPEED px/f), horizontally dominated, starting at or
    #     above the net tape (a lob re-descends vertically; a free-driven ball
    #     keeps its speed and stays connectible);
    #   * IDENTITY BREAK (load-bearing): the pre-gap point must be UNREACHABLE
    #     from the run extrapolated backward across the gap (e6: 1695px; the
    #     bridged apex it must not fire on is velocity-consistent: 34px);
    #   * the touch sits at the gap MIDPOINT (max-likelihood when the flight
    #     is unseen on both sides; e6 -> f308 == GT) and the point is back-
    #     extrapolated along the run; it must be above the net tape;
    #   * attribution runs normally at the manufactured frame; the emitted
    #     team is read from the takeoff stance because the contact-time
    #     snapshot is mid-jump by construction and airborne feet project deep
    #     (the SpikeAnalyzer takeoff-window lesson, [c-12, c-2]).
    REENTRY_MIN_GAP = 8       # frames; below this the bridge bands' turf
    REENTRY_MAX_GAP = 30      # frames; beyond this = dead ball / new rally
    REENTRY_RUN_WINDOW = 7    # frames after the gap used to measure the run
    REENTRY_MIN_RUN = 2       # real sightings needed in the run window
    REENTRY_MIN_SPEED = 40.0  # px/frame; attack-drive scale
    REENTRY_JUMP_PX = 200.0   # min identity break (px) pre-gap -> run
    REENTRY_TEAM_BACK = 12    # takeoff-stance window (frames before contact),
    REENTRY_TEAM_END = 2      # mirroring SpikeAnalyzer's [c-12, c-2]

    # --- Drive (attacking hit) detection ---
    # A spike drives the ball down/across: unlike a dig it does not pop the ball
    # back up (so the bounce test misses it) and it need not flip the ball's
    # horizontal direction (so the redirect test misses it). What it always does
    # is change the ball's velocity in a way free flight cannot -- a ball under
    # gravity keeps a near-constant horizontal speed and accelerates downward, so
    # a sharp horizontal impulse OR a sudden check of the downward speed marks a
    # contact. Velocities are per-frame so thresholds are frame-rate consistent.
    DRIVE_MIN_SPEED = 8.0    # px/frame; ball must be genuinely in flight
    DRIVE_DECEL = 8.0        # px/frame drop in downward speed gravity can't explain
    DRIVE_XIMPULSE = 12.0    # px/frame horizontal-velocity change (a sideways hit)
    DRIVE_RISE_TOL = 3.0     # px/frame; a spike sends the ball down/flat -- if it
                             # rises after the contact it is a dig/pass (a bounce)

    # --- Classification tuning ---
    NEAR_NET_PX = 120        # |y - midcourt| under this counts as "near the net"
    DRIVE_MIN_PX = 55.0      # min outgoing horizontal speed for an attack drive
    RISE_MIN_PX = 30.0       # outgoing vertical speed treated as "ball rising"
    HANDS_OVERHEAD = 1.0     # avg_wrist_height_ratio above this = hands overhead
    RALLY_RESET_GAP = 90     # frames of no contact after which a new rally starts

    def __init__(
        self,
        pose_estimator: PoseEstimator,
        temporal_window: int = 10,
        confidence_threshold: float = 0.4,
        court_calibration=None,
        # --- Team-aware attribution (which team may touch next) ---
        team_aware: bool = True,
        width_side_enabled: bool = True,
        width_window: int = 8,
        width_far_px: float = 26.0,
        width_near_px: float = 35.0,
        near_net_exempt_m: float = 2.5,
        # Accept but ignore legacy params
        enhanced_validation_config: Optional[Dict[str, Any]] = None,
    ):
        self.pose_estimator = pose_estimator
        self.temporal_window = temporal_window
        self.confidence_threshold = confidence_threshold
        self.court = court_calibration

        self._team_aware = team_aware
        self._width_side_enabled = width_side_enabled
        self._width_window = width_window
        self._width_far_px = width_far_px
        self._width_near_px = width_near_px
        self._near_net_exempt_m = near_net_exempt_m

        # Ball trajectory of REAL (non-predicted) positions:
        # (frame, x, y, w, h) -- width feeds the near/far side estimate.
        self._ball_history: deque = deque(maxlen=120)
        self._last_contact_frame: int = -1000

        # Possession memory (attribution only; the context layer keeps its own
        # attack-based possession for labels). ``_last_touch_team`` is the
        # foot-side team of the last ATTRIBUTED contact; whether that touch
        # sent the ball over (attack/serve/block gesture) decides flip vs
        # carry for the next contact's expectation.
        self._last_touch_team: Optional[str] = None
        self._last_touch_frame: Optional[int] = None
        self._last_touch_went_over: bool = False

        # Per-player pose/position history for temporal features. Kept long
        # enough to look back to a contact confirmed CONTACT_DELAY frames ago.
        self._pose_hist_len = max(temporal_window, self.CONTACT_DELAY + self.NEIGH + 4)
        self._player_pose_history: Dict[int, deque] = {}

        # Context layer: turns the visual gestures this class emits into
        # canonical actions using rally state. A one-contact look-ahead is
        # needed (set vs overpass), so each contact is finalised when the next
        # one arrives; the pending contact waits in ``self._pending``.
        self._resolver = ActionContextResolver(rally_reset_gap=self.RALLY_RESET_GAP)
        self._pending: Optional[Dict[str, Any]] = None

        self.logger = logging.getLogger(__name__)

    def set_court_calibration(self, court) -> None:
        """Set court calibration for spatial reasoning."""
        self.court = court

    def reset(self) -> None:
        """Reset all per-video state."""
        self._ball_history.clear()
        self._player_pose_history.clear()
        self._last_contact_frame = -1000
        self._last_touch_team = None
        self._last_touch_frame = None
        self._last_touch_went_over = False
        self._resolver.reset()
        self._pending = None

    def classify_actions(
        self,
        frame: np.ndarray,
        player_detections: List[Dict[str, Any]],
        ball_info: Optional[Dict[str, Any]] = None,
        frame_number: Optional[int] = None,
        court_info: Optional[Dict[str, Any]] = None,
        game_state_info: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Classify actions for the current frame.

        Returns a list of action dicts. Most frames return empty -- actions are
        only emitted at ball-contact events. An emitted event's ``frame_number``
        is the true contact frame, which is ``CONTACT_DELAY`` frames before the
        current one.
        """
        if frame_number is None:
            frame_number = 0

        # Track the ball only when it is really detected (not tracker-predicted).
        if ball_info and not ball_info.get("is_predicted", False):
            center = ball_info.get("center")
            if center and center[0] is not None:
                bb = ball_info.get("bbox")
                if bb and len(bb) == 4:
                    w, h = float(bb[2] - bb[0]), float(bb[3] - bb[1])
                else:
                    w = h = 0.0
                self._ball_history.append(
                    (frame_number, float(center[0]), float(center[1]), w, h)
                )

        # Estimate + store poses for players OBSERVED this frame. Ghost boxes
        # (tracker-coasted, predicted=True) are extrapolations, not sightings:
        # pose-estimating them is garbage and their drifted bboxes pollute
        # closest-player attribution (seen on entreno_3: a ghost riding a jump's
        # upward velocity steals the contact). _closest_player_at still finds
        # each player via their last REAL snapshot within the history window.
        observed = [d for d in player_detections if not d.get("predicted", False)]
        poses = self.pose_estimator.estimate_poses_batch(frame, observed)
        for det, pose in zip(observed, poses):
            tid = det.get("track_id")
            if tid is None:
                continue
            if tid not in self._player_pose_history:
                self._player_pose_history[tid] = deque(maxlen=self._pose_hist_len)
            self._player_pose_history[tid].append({
                "frame": frame_number,
                "pose": pose,
                "center": det.get("center"),
                "bbox": det.get("bbox"),
                "team": det.get("team"),
            })

        # Confirm a contact that happened CONTACT_DELAY frames ago (we now have
        # trajectory on both sides of it).
        contact_frame = frame_number - self.CONTACT_DELAY
        contact = self._detect_contact(contact_frame)
        if contact is None:
            return []

        # The reentry band manufactures its own contact frame (the gap
        # midpoint): the event must not carry the re-entry sighting frame.
        contact_point, kind, inc, out, contact_frame = contact

        # Which team may be touching now, read from the ball itself (see
        # _attribution_target): constrains the candidate set below.
        target_team, side_info = self._attribution_target(contact_frame)

        chosen = self._closest_player_at(contact_frame, contact_point, target_team)
        if chosen is None:
            return []
        pdata, distance, lr_index = chosen
        if distance > self.CONTACT_REACH:
            return []

        if kind == "reentry":
            # The contact frame is manufactured, so the snapshot AT it is
            # mid-jump by construction and its airborne feet project deep
            # (wrong side). Read the emitted team from the last pre-contact
            # stance instead (SpikeAnalyzer's takeoff-window fix, scoped to
            # this contact kind).
            stance = self._takeoff_stance(pdata.get("track_id"), contact_frame)
            if stance is not None:
                pdata = stance

        self._last_contact_frame = contact_frame

        # Layer 1: read the context-free visual gesture at this contact.
        contact_evt = self._build_contact(
            pdata, lr_index, contact_point, kind, inc, out, contact_frame, side_info
        )
        self._last_touch_team = contact_evt.get("team")
        self._last_touch_frame = contact_frame
        # Did this touch send the ball over the net? Attacks, blocks and the
        # serve do; a dig/set keeps the ball on this side (an overpass is the
        # width-side override's job to catch).
        gesture = contact_evt.get("gesture")
        self._last_touch_went_over = (
            gesture in (VisualGesture.ATTACK, VisualGesture.BLOCK)
            or (bool(contact_evt.get("behind_baseline"))
                and bool(side_info.get("first_of_rally")))
        )

        # Layer 2 (streaming): finalise the *previous* contact now that we know
        # its successor, and hold this one back until its own successor arrives.
        emitted: List[Dict[str, Any]] = []
        if self._pending is not None:
            emitted.append(self._finalize(self._pending, contact_evt))
        self._pending = contact_evt
        return [e for e in emitted if e is not None]

    def flush(self) -> List[Dict[str, Any]]:
        """Finalise the last pending contact at end of video (no successor)."""
        if self._pending is None:
            return []
        event = self._finalize(self._pending, None)
        self._pending = None
        return [event] if event is not None else []

    def _finalize(
        self, contact_evt: Dict[str, Any], next_contact: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Resolve a gesture-contact to a canonical action event, or None if
        it falls below the confidence threshold."""
        resolved = self._resolver.resolve(contact_evt, next_contact)
        if resolved["confidence"] < self.confidence_threshold:
            return None
        cp = contact_evt["contact_point"]
        return {
            "track_id": contact_evt["track_id"],
            "player_id": contact_evt["player_id"],   # left-to-right index (GT convention)
            "action": resolved["action"],
            "gesture": contact_evt["gesture"].value,
            "confidence": resolved["confidence"],
            "frame_number": contact_evt["frame"],
            "contact_point": [round(cp[0], 1), round(cp[1], 1)],
            "player_center": contact_evt["player_center"],
            # The TOUCHER's per-contact foot team -- not the resolver's latched
            # possession, which hid wrong-team thefts behind an inherited label
            # (entreno_3 f244 emitted B for an A-side contact).
            "team": contact_evt.get("team"),
            "team_in_possession": resolved["team_in_possession"],
            "touch_number": resolved["touch_number"],
            "rally_id": resolved["rally_id"],
            "contact_kind": contact_evt["contact_kind"],
        }

    # --- Ball-contact detection ---

    def _real_points(self, lo: int, hi: int) -> List[Tuple]:
        """Real ball points (frame, x, y, w, h) with frame in [lo, hi]."""
        return [p for p in self._ball_history if lo <= p[0] <= hi]

    def _point_at(self, f: int) -> Optional[Tuple]:
        for p in self._ball_history:
            if p[0] == f:
                return p
        return None

    def _takeoff_stance(self, track_id: Optional[int], frame: int) -> Optional[Dict[str, Any]]:
        """Nearest real snapshot of ``track_id`` in [frame-REENTRY_TEAM_BACK,
        frame-REENTRY_TEAM_END] -- the last grounded read before a manufactured
        reentry contact (airborne contact-time feet project deep)."""
        if track_id is None:
            return None
        hist = self._player_pose_history.get(track_id)
        if not hist:
            return None
        lo = frame - self.REENTRY_TEAM_BACK
        hi = frame - self.REENTRY_TEAM_END
        window = [h for h in hist
                  if h.get("center") is not None and lo <= h["frame"] <= hi]
        if not window:
            return None
        snap = dict(min(window, key=lambda h: abs(h["frame"] - hi)))
        snap["track_id"] = track_id
        return snap

    def _reentry_contact(self, c: int, vertex: Tuple):
        """Manufacture a contact across an out-of-frame excursion (see the
        REENTRY_* constants). Called like :meth:`_bridge_contact` at ``c`` =
        the first ball sighting after the gap. Returns the contact tuple with
        the event frame at the gap MIDPOINT -- the touch happened inside the
        excursion, and carrying ``c`` would misdate it by the whole unseen
        flight -- or None when the gap/run/geometry does not qualify."""
        before = [p for p in self._ball_history if p[0] < c]
        if not before:
            return None
        a = before[-1]
        gap = c - a[0]
        if not (self.REENTRY_MIN_GAP <= gap <= self.REENTRY_MAX_GAP):
            return None
        run = self._real_points(c + 1, c + self.REENTRY_RUN_WINDOW)
        if len(run) < self.REENTRY_MIN_RUN:
            return None
        span = run[-1][0] - c
        if span <= 0:
            return None
        v_run = ((run[-1][1] - vertex[1]) / span,
                 (run[-1][2] - vertex[2]) / span)
        speed = float(np.hypot(*v_run))
        # A lob that exits the top re-descends VERTICALLY and free-flight
        # connectible; an attack-scale impulse leaves a fast horizontal run.
        if speed < self.REENTRY_MIN_SPEED or abs(v_run[0]) <= abs(v_run[1]):
            return None
        if not self._court_ready():
            return None
        if not self.court.is_above_net((int(vertex[1]), int(vertex[2]))):
            return None
        # Identity break: where would the run's own velocity have put the ball
        # back at the pre-gap frame? If that prediction lands on the pre-gap
        # sighting the flight is connectible (a bridged apex, e2 f149: 34px)
        # and any touch inside the gap is the bridges' business, not ours.
        px = vertex[1] - v_run[0] * gap
        py = vertex[2] - v_run[1] * gap
        if float(np.hypot(px - a[1], py - a[2])) < self.REENTRY_JUMP_PX:
            return None
        back = max(1, gap // 2)
        cx = vertex[1] - v_run[0] * back
        cy = vertex[2] - v_run[1] * back
        if not self.court.is_above_net((int(cx), int(cy))):
            return None
        inc = (0.0, speed)          # manufactured: vertical from above
        out = (run[-1][1] - vertex[1], run[-1][2] - vertex[2])
        return [cx, cy], "reentry", inc, out, c - back

    def _bridge_contact(self, c: int, vertex: Tuple):
        """Bounce whose bottom the detector never saw (ball occluded at the touch).

        Called from :meth:`_detect_contact` at ``c`` = the FIRST ball sighting
        after a sighting gap. The touch itself happened inside the gap: real
        sightings stop DESCENDING just before it and resume ASCENDING at ``c``
        (entreno_5 f111: fall to f102, gap, rising again at f114 -- the set was
        invisible). Returns the contact tuple with the touch point interpolated
        into the gap, or None when the gap/shape does not qualify.

        Two bands, both A/B-validated byte-neutral on entreno_1/3/4/5:

        * classic, gap in [BRIDGE_MIN_GAP, BRIDGE_MAX_GAP]: >=2 real sightings
          each side, decisive net descent into / ascent out of the gap. The
          ascent gate is deliberately high -- a ball rebounding off the SAND
          rises far less than a set toss (e5 f332-340: 25px vs f111's 142px).

        * SHORT, gap in [BRIDGE_SHORT_MIN_GAP, BRIDGE_MIN_GAP): the occlusion
          at the toucher's arms can be brief (e2 f206: 6f, e6 f212: 6f) yet
          still leave the normal tests without their >=2-points-within-NEIGH
          on a side. Extra gates, because short gaps are otherwise the normal
          detector's turf (e6 f265 fires normally at gap 6):
            - the normal path PROVABLY cannot fire: fewer than 2 real points
              within NEIGH on at least one side of ``c``;
            - ball identity continuity: |dx| across the gap within
              BRIDGE_X_CONT_* (a spare ball appearing elsewhere after a
              game-ball gap must not bridge);
            - when the right window is empty (sparse re-acquisition, e6: the
              dug ball is seen once more 8f later), no future points exist at
              decision time -- contacts are confirmed at c+CONTACT_DELAY and
              the window ends at c+BRIDGE_WINDOW. Evidence needing no future:
              the CROSS-GAP RISE, first post-gap sighting decisively higher
              than the last pre-gap one. Physically tight: a sand rebound
              cannot rise 60px in <=6 frames and a free-flight apex cannot
              produce it from a >=20px descent.
        """
        before = [p for p in self._ball_history if p[0] < c]
        if not before:
            return None
        a = before[-1]
        gap = c - a[0]
        short = self.BRIDGE_SHORT_MIN_GAP <= gap < self.BRIDGE_MIN_GAP
        if short:
            if (len(self._real_points(c - self.NEIGH, c - 1)) >= 2
                    and len(self._real_points(c + 1, c + self.NEIGH)) >= 2):
                return None  # dense both sides: the normal detector's turf
            if abs(vertex[1] - a[1]) > max(
                    self.BRIDGE_X_CONT_PX, self.BRIDGE_X_CONT_PER_F * gap):
                return None  # identity discontinuity: a different ball
        elif not (self.BRIDGE_MIN_GAP <= gap <= self.BRIDGE_MAX_GAP):
            return None
        left = self._real_points(a[0] - self.BRIDGE_WINDOW, a[0] - 1)
        right = self._real_points(c + 1, c + self.BRIDGE_WINDOW)
        drop = a[2] - left[0][2] if left else None
        # SHORT band, sparse right side: fall back to the cross-gap rise.
        if len(right) < 2 and short:
            cross_rise = a[2] - vertex[2]
            if (len(left) >= 2 and drop is not None
                    and drop >= self.BRIDGE_MIN_DROP
                    and cross_rise >= self.BRIDGE_MIN_RISE):
                v_in = max(drop / max(1, a[0] - left[0][0]), 1.0)
                v_out = max(cross_rise / gap, 1.0)
                v = a[0] + gap * v_in / (v_in + v_out)
                x = a[1] + (vertex[1] - a[1]) * (v - a[0]) / gap
                y = (a[2] + v_in * (v - a[0]) + vertex[2] + v_out * (c - v)) / 2.0
                inc = (a[1] - left[0][1], a[2] - left[0][2])
                out = (vertex[1] - a[1], vertex[2] - a[2])
                return [x, y], "bounce", inc, out
            return None
        if len(left) < 2 or len(right) < 2:
            return None
        # Screen y grows downward: a descent ADDS y, an ascent SUBTRACTS it,
        # so both magnitudes are positive here.
        ascent = vertex[2] - right[-1][2]
        if drop < self.BRIDGE_MIN_DROP or ascent < self.BRIDGE_MIN_RISE:
            return None
        # Where in the gap the bottom sat: the descent run out of `a` and the
        # ascent run into `c` meet earlier when the ball fell slower than it
        # rose. Used only to place the touch point (the event keeps frame c;
        # the reach gate forgives ~140px of interpolation error).
        v_in = max(drop / max(1, a[0] - left[0][0]), 1.0)
        v_out = max(ascent / max(1, right[-1][0] - c), 1.0)
        v = a[0] + gap * v_in / (v_in + v_out)
        x = a[1] + (vertex[1] - a[1]) * (v - a[0]) / gap
        y = (a[2] + v_in * (v - a[0]) + vertex[2] + v_out * (c - v)) / 2.0
        inc = (a[1] - left[0][1], a[2] - left[0][2])
        out = (right[-1][1] - vertex[1], right[-1][2] - vertex[2])
        return [x, y], "bounce", inc, out

    @staticmethod
    def _mean_velocity(
        points: List[Tuple[int, float, float]]
    ) -> Tuple[float, float]:
        """Mean per-frame velocity (dx/dt, dy/dt) across ordered (frame,x,y) points.

        Dividing by the frame span (not the point count) keeps the estimate
        correct across the gaps left by undetected ball frames.
        """
        if len(points) < 2:
            return (0.0, 0.0)
        dt = points[-1][0] - points[0][0]
        if dt <= 0:
            return (0.0, 0.0)
        return ((points[-1][1] - points[0][1]) / dt, (points[-1][2] - points[0][2]) / dt)

    def _detect_contact(
        self, c: int
    ) -> Optional[Tuple[List[float], str, Tuple[float, float], Tuple[float, float], int]]:
        """Test whether frame ``c`` is a ball contact.

        Returns (contact_point, kind, incoming_vec, outgoing_vec, frame) or
        None. ``kind`` is "bounce" (fall-and-rise), "redirect" (horizontal
        deflect), "drive" (attacking hit), or "reentry" (manufactured across
        an out-of-frame excursion). ``frame`` is the event's contact frame:
        ``c`` for the detected kinds, the gap midpoint for a reentry.
        """
        if c <= self.NEIGH:
            return None
        if c - self._last_contact_frame < self.MIN_CONTACT_GAP:
            return None

        vertex = self._point_at(c)
        if vertex is None:
            return None

        # Gap-bridged bounce first (see the BRIDGE_* constants): if c is the
        # first sighting after a qualifying gap, the normal tests below cannot
        # fire (the gap leaves no left-side points within NEIGH) and only the
        # bridge can see the touch that happened inside the gap.
        bridged = self._bridge_contact(c, vertex)
        if bridged is not None:
            return bridged[0], bridged[1], bridged[2], bridged[3], c
        # Reentry band next (see the REENTRY_* constants): an out-of-frame
        # excursion the tracker never bridged -- the gap endpoints are not
        # free-flight connectible and the outgoing run is attack-fast.
        reentry = self._reentry_contact(c, vertex)
        if reentry is not None:
            return reentry
        vx, vy = vertex[1], vertex[2]

        left = self._real_points(c - self.NEIGH, c - 1)
        right = self._real_points(c + 1, c + self.NEIGH)
        if len(left) < 2 or len(right) < 2:
            return None

        contact_point = [vx, vy]
        inc = (vx - left[0][1], vy - left[0][2])       # net incoming vector
        out = (right[-1][1] - vx, right[-1][2] - vy)    # net outgoing vector

        # Bottom-of-arc: vertex is the lowest point and the ball rises (smaller
        # y) by MIN_PROMINENCE on both sides.
        lowest = all(p[2] <= vy for p in left + right)
        if lowest:
            rise_l = vy - min(p[2] for p in left)
            rise_r = vy - min(p[2] for p in right)
            if rise_l >= self.MIN_PROMINENCE and rise_r >= self.MIN_PROMINENCE:
                return contact_point, "bounce", inc, out, c

        # Horizontal redirect: ball arrives from one side and leaves to the
        # other (block/spike drive) without a clean bounce.
        if inc[0] * out[0] < 0 and abs(inc[0]) > self.XREV_MIN and abs(out[0]) > self.XREV_MIN:
            return contact_point, "redirect", inc, out, c

        # Attacking DRIVE: the ball's motion is checked in a way free flight
        # cannot produce -- its downward speed is sharply cut (a ball hit down
        # into the sand / driven flat) or it gets a strong horizontal impulse --
        # yet it does not pop cleanly back up like a dig. This is the spike
        # signature the two tests above miss (no rise, no horizontal sign flip).
        #
        # Estimate the velocity from points within +/-3 frames of the vertex: a
        # bounce/apex further out (or one pulled close by a run of undetected
        # ball frames) would otherwise fake a deceleration on a dig's approach.
        left3 = [p for p in left if p[0] >= c - 3]
        right3 = [p for p in right if p[0] <= c + 3]
        if left3 and right3:
            vin = self._mean_velocity(left3 + [vertex])
            vout = self._mean_velocity([vertex] + right3)
            dvx = vout[0] - vin[0]
            dvy = vout[1] - vin[1]
            speed = max(float(np.hypot(*vin)), float(np.hypot(*vout)))
            # A dig rebounds the ball back up above the contact within a few
            # frames; a spike keeps it at or below. Checking the full outgoing
            # window rejects the 1-2 frames just before a dig's bottom, where the
            # short window alone still looks like a downward check.
            stays_down = (right[-1][2] - vy) >= 0.0
            pops_up = vout[1] < -self.DRIVE_RISE_TOL
            if speed >= self.DRIVE_MIN_SPEED and stays_down and not pops_up:
                if dvy <= -self.DRIVE_DECEL or abs(dvx) >= self.DRIVE_XIMPULSE:
                    return contact_point, "drive", inc, out, c

        return None

    # --- Team-aware attribution: possession + ball-size side ---

    def _court_ready(self) -> bool:
        return self.court is not None and getattr(self.court, "is_calibrated", False)

    def _width_side(self, frame: int) -> Tuple[Optional[str], int]:
        """Court side implied by the ball's pixel width just before ``frame``.

        The ball looks bigger on the near half: on entreno_3 the far-half
        rally ball is 14-28px wide and the near-half one 30-55px. This is a
        RELATIVE discriminator, not a metric depth -- a 2D ground homography
        cannot turn size into depth for an airborne ball (the camera is closer
        to any airborne ball than to the ground under it, so a ground-scale
        inversion reads everything as near). What the width CAN say, reliably,
        is "far half" vs "near half" with an abstain band in between.

        Commits only when the last ``_width_window`` real samples with a size
        agree (any sample on the other side blocks the commit -- mixed
        evidence means mid-flight or near the net).
        """
        if not self._width_side_enabled:
            return None, 0
        n_a = n_b = 0
        for p in self._ball_history:
            if not (frame - self._width_window <= p[0] <= frame - 1):
                continue
            w = p[3]
            if w <= 0:
                continue
            if w < self._width_far_px:
                n_b += 1
            elif w > self._width_near_px:
                n_a += 1
        if n_a and not n_b:
            return "A", n_a
        if n_b and not n_a:
            return "B", n_b
        return None, max(n_a, n_b)

    def _attribution_target(self, frame: int) -> Tuple[Optional[str], Dict[str, Any]]:
        """Which team is expected to touch at ``frame`` (None = unconstrained).

        Two signals, in priority order (validated on entreno_3 GT, 14/14):

        1. **Ball width side** -- direct evidence of which half the ball is
           approaching from. Catches the two transitions pure alternation
           cannot: an over-set/overpass dig that crosses (width flips to the
           other regime) and a block rebound (width stays in the spiker's
           regime, overriding the after-attack flip).
        2. **Possession alternation** -- after an attack/serve/block gesture
           the ball is presumed over the net: expect the OTHER team; after a
           bump-set (dig/set) expect the SAME team. Survives missed blocks
           whenever the width side abstains (no ball data) by ... only via the
           width override; alternation alone would misread a rebound.

        Image-plane trajectory side was evaluated and REJECTED (2026-08-16
        diagnostic): an airborne ball over the near half projects above the
        midcourt line, so every high ball reads "far"; and the ball is often
        entirely undetected on near-half approaches (occlusion), leaving no
        window to vote over.
        """
        info: Dict[str, Any] = {"ball_side": None, "side_votes": 0, "source": None,
                                "first_of_rally": False}
        if not self._team_aware or not self._court_ready():
            return None, info

        side, votes = self._width_side(frame)
        info["ball_side"], info["side_votes"] = side, votes
        if side is not None:
            info["source"] = "width"
            return side, info

        if self._last_touch_team is None or self._last_touch_frame is None:
            return None, info
        rally_reset = frame - self._last_touch_frame > self.RALLY_RESET_GAP
        info["first_of_rally"] = rally_reset
        if rally_reset:
            # New rally (dead-ball gap): a serve from either side may open it --
            # stay unconstrained and let containment pick the server.
            return None, info
        if self._last_touch_went_over:
            info["source"] = "flip"
            return ("B" if self._last_touch_team == "A" else "A"), info
        info["source"] = "carry"
        return self._last_touch_team, info

    def _closest_player_at(
        self, frame: int, point: List[float], target_team: Optional[str] = None
    ) -> Optional[Tuple[Dict[str, Any], float, Optional[int]]]:
        """Find the tracked player closest to ``point`` around ``frame``.

        Returns (player_snapshot, distance, left_to_right_index) or None. The
        snapshot is the history entry nearest ``frame`` for that player; the
        L-R index ranks all players present near ``frame`` by x (matching the
        ground-truth annotation convention).

        When ``target_team`` is set, candidates whose FEET (per-contact, via
        ``court.get_team_for_bbox`` -- the smoothed tracker team is wrong near
        the midcourt band) sit on the other side are excluded. The one
        exception is BLOCK geometry: a player at the net within
        ``near_net_exempt_m`` GROUND metres whose contact point is ABOVE the
        net-top line (an image-pixel band would swallow the whole
        perspective-compressed far half; and without the above-net condition a
        net-standing opponent steals every set -- entreno_3 f488: thief's feet
        0.5m from the net, contact well below the tape). If the filter would
        empty the candidate set it is dropped -- a wrong team estimate must
        not delete a contact outright.
        """
        snapshots: List[Dict[str, Any]] = []
        for tid, hist in self._player_pose_history.items():
            if not hist:
                continue
            snap = min(hist, key=lambda h: abs(h["frame"] - frame))
            if abs(snap["frame"] - frame) > self.NEIGH + 2:
                continue
            if snap.get("center") is None:
                continue
            snap = dict(snap)
            snap["track_id"] = tid
            snapshots.append(snap)

        if not snapshots:
            return None

        if target_team is not None and self._court_ready():
            contact_above_net = self.court.is_above_net(
                (int(point[0]), int(point[1])))
            eligible: List[Dict[str, Any]] = []
            for s in snapshots:
                bbox = s.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue
                if self.court.get_team_for_bbox(bbox) == target_team:
                    eligible.append(s)
                    continue
                foot = (int((bbox[0] + bbox[2]) / 2), int(bbox[3]))
                dist_m = self.court.world_dist_from_net(foot)
                if (dist_m is not None and dist_m <= self._near_net_exempt_m
                        and contact_above_net):
                    eligible.append(s)
            if eligible:
                snapshots = eligible
            else:
                # Team filter matched nobody: keep every candidate rather than
                # lose the contact (side estimate was probably wrong).
                self.logger.debug(
                    "attribution: team filter (%s) matched no candidate at f%d",
                    target_team, frame,
                )

        ordered = sorted(snapshots, key=lambda s: s["center"][0])
        # Distance to the player's BODY, not their torso centre: a player
        # digging low or reaching overhead at the net contacts the ball far
        # from their centre, but close to their bounding box (which spans
        # feet to raised hands). Centre distance would reject those touches.
        # Ties on bbox distance (e.g. ball inside two overlapping boxes) break
        # by centre distance so the choice is deterministic.
        best = None
        best_key = (float("inf"), float("inf"))
        best_dist = float("inf")
        for s in ordered:
            d = self._point_to_bbox_distance(point, s.get("bbox"), s["center"])
            c = s["center"]
            cd = float(np.hypot(c[0] - point[0], c[1] - point[1]))
            if (d, cd) < best_key:
                best_key = (d, cd)
                best = s
                best_dist = d
        lr_index = ordered.index(best) + 1
        return best, best_dist, lr_index

    @staticmethod
    def _point_to_bbox_distance(
        point: List[float], bbox: Optional[List[float]], center: List[float]
    ) -> float:
        """Distance from ``point`` to a bbox: 0 inside, else to the nearest edge.

        Falls back to centre distance when no bbox is available.
        """
        if not bbox or len(bbox) != 4:
            return float(np.hypot(center[0] - point[0], center[1] - point[1]))
        x1, y1, x2, y2 = bbox
        dx = max(x1 - point[0], 0.0, point[0] - x2)
        dy = max(y1 - point[1], 0.0, point[1] - y2)
        return float(np.hypot(dx, dy))

    # --- Layer 1: visual gesture detection (context-free) ---

    def _build_contact(
        self,
        pdata: Dict[str, Any],
        lr_index: Optional[int],
        contact_point: List[float],
        kind: str,
        inc: Tuple[float, float],
        out: Tuple[float, float],
        frame: int,
        side_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Assemble a gesture-contact: the visual gesture plus the court/spatial
        facts the context layer needs. No rally reasoning happens here."""
        bbox = pdata.get("bbox") or [0, 0, 0, 0]
        foot = (int((bbox[0] + bbox[2]) / 2), int(bbox[3]))

        # Court context. "Near the net" is judged on the player's FEET, not their
        # torso centre: a net player has feet on the midcourt line but a torso
        # that sits high in the frame, so a centre-based test reads "far".
        team = pdata.get("team")
        near_net = False
        behind_baseline = False
        if self.court is not None and getattr(self.court, "is_calibrated", False):
            foot_team = self.court.get_team_for_bbox(bbox)
            team = foot_team or team
            near_net = self.court.is_near_net(foot, threshold_px=self.NEAR_NET_PX)
            if foot_team:
                behind_baseline = self.court.is_behind_baseline(foot, foot_team)

        gesture, gconf = self._detect_gesture(pdata, kind, inc, out, near_net)

        contact = {
            "frame": frame,
            "gesture": gesture,
            "gesture_confidence": gconf,
            "track_id": pdata.get("track_id"),
            "player_id": lr_index,
            "team": team,
            "near_net": near_net,
            "behind_baseline": behind_baseline,
            "contact_point": contact_point,
            "contact_kind": kind,
            "ball_in": inc,
            "ball_out": out,
            "player_center": pdata.get("center"),
        }
        if side_info:
            contact["ball_side"] = side_info.get("ball_side")
            contact["attribution_source"] = side_info.get("source")
        return contact

    def _detect_gesture(
        self,
        pdata: Dict[str, Any],
        kind: str,
        inc: Tuple[float, float],
        out: Tuple[float, float],
        near_net: bool,
    ) -> Tuple[VisualGesture, float]:
        """Classify the context-free visual gesture at a contact.

        Only ball motion (around the contact), whether the player is at the net,
        and pose are used -- never rally position. The bump-set gesture is
        intentionally coarse; the context layer decides dig/set/overpass/serve.
        """
        # REENTRY -- a manufactured contact across an out-of-frame excursion.
        # The identity-break + fast-horizontal-run-above-tape gates already
        # prove an attack-scale impulse; the pose block read is unreliable
        # here (the toucher is airborne by construction), so the gesture is
        # ATTACK and the context layer labels the action.
        if kind == "reentry":
            return VisualGesture.ATTACK, 0.55

        out_x, out_y = out
        horiz = abs(out_x)
        vert = abs(out_y)
        going_up = out_y < -self.RISE_MIN_PX
        driven_sideways = horiz >= self.DRIVE_MIN_PX and horiz >= vert * 0.8
        driven_down = out_y > self.RISE_MIN_PX

        feats: Dict[str, Any] = {}
        pose = pdata.get("pose")
        if pose and "pose_features" in pose:
            feats = pose["pose_features"]
        avg_wrist = feats.get("avg_wrist_height_ratio")
        hands_overhead = avg_wrist is not None and avg_wrist > self.HANDS_OVERHEAD

        # DRIVE -- the drive test only exists to ADD a contact the bounce and
        # redirect tests miss (a ball hit down/across that never pops up). Its
        # label is left to the context layer (touch number + court position): a
        # 3rd-ball drive at the net resolves to a spike, while a hard, flat set
        # or dig keeps its true label. Forcing ATTACK here turned every driven
        # set/dig into a spike (regressed the net-rally drills). Overhead hands
        # at the net over a non-rising horizontal ball is still a block.
        if kind == "drive":
            if near_net and hands_overhead and not going_up and horiz > vert:
                return VisualGesture.BLOCK, 0.6
            return VisualGesture.BUMP_SET, 0.5

        # BLOCK -- at the net, ball redirected roughly horizontally (not rising)
        # with hands overhead or a clean sideways redirect (a stuffed attack).
        if near_net and not going_up and horiz > self.DRIVE_MIN_PX:
            if hands_overhead or kind == "redirect":
                return VisualGesture.BLOCK, (0.7 if hands_overhead else 0.55)

        # ATTACK -- an attacking drive: ball leaves strongly sideways or is
        # driven downward near the net.
        if near_net and (driven_sideways or driven_down):
            return VisualGesture.ATTACK, 0.6

        # BUMP_SET -- a controlled up-touch (ball fell in and is sent back up).
        if kind == "bounce" or going_up or vert > self.DRIVE_MIN_PX:
            return VisualGesture.BUMP_SET, 0.55

        # Fallback: a sideways redirect near the net looks like an attack drive.
        if near_net and horiz > vert:
            return VisualGesture.ATTACK, 0.4
        return VisualGesture.BUMP_SET, 0.4
