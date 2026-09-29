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

    # Level-horizontal exit gate for the TAKEOFF-STANCE team read. It keys
    # the AIRBORNE-net-contact shape, not the spike type (typing is
    # SpikeAnalyzer's ascent rule): the toucher of a level-exit net contact
    # is airborne by construction -- redirecting a fast descent level across
    # the court takes a jump -- so the contact-time feet project deep and
    # the court team read flips sides; the emitted team comes from the
    # takeoff-stance majority instead. Poster child: e6 f310, the ratified
    # HARD joust spike (exit vx -47 px/f, vy +1.5) whose team must read A.
    # Driven balls excluded by the same gates as measured 2026-09-06: they
    # exit downward and nearly straight (e3 f431 vx 5, f539 vx 14). The
    # historical "poke" name survives in the identifiers; the 2026-09-09
    # ratification moved THE poke to e5 f300 (analyzer-side, ascent-based).
    POKE_EXIT_VX_PX = 25.0    # |mean exit vx| at/above this ...
    POKE_EXIT_VY_PX = 12.0    # ... with |exit vy| at/below this = airborne

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
    # Rally-opening serve gate: the ascent must be FED -- the incoming ±3f
    # slope beats the preceding ±6f slope by this margin (gravity only
    # decays an ascent). Measured: e7 f25 +29; e4's gravity arc never
    # reaches +10 (its best is -5.8, i.e. decelerating).
    SERVE_ACCEL_MARGIN_PX = 10.0
    # Toss-apex reach allowance for the rally-opening serve (see the reach
    # gate in classify_actions): e7 f25 measured 147.5px ball-to-box.
    SERVE_REACH_PX = 160.0
    RISE_MIN_PX = 30.0       # outgoing vertical speed treated as "ball rising"
    HANDS_OVERHEAD = 1.0     # avg_wrist_height_ratio above this = hands overhead
    RALLY_RESET_GAP = 90     # frames of no contact after which a new rally starts

    # --- Pose gating (perf, adopted 2026-09-27 after a byte-identical A/B) ---
    # Pose is ONLY ever consumed by `_gesture` via the snapshot `_closest_player_at`
    # chooses for an ACCEPTED (reach-passing, non-reentry) contact; reentry
    # gestures return ATTACK without pose, and takeoff-stance team reads use
    # bbox/team only. The chosen snapshot sits within NEIGH+2 frames of the
    # contact vertex, and the vertex itself is a REAL ball point that passed
    # the reach test (<=140/160 px to that snapshot's bbox). Measured on all
    # 7 entrenos + a 2500-frame match slice (output/diag_pose_gate_probe_*): the
    # chosen snapshot's bbox is at most 155 px from SOME ball point in the last
    # NEIGH+2 frames -- so a 300 px trail radius covers every consumed snapshot
    # with 2x margin while posing ~1.8 of 3.5 observed players on live frames.
    POSE_TRAIL_WINDOW = NEIGH + 2  # frames of ball trail the radius keys on

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
        # --- Pose gating (perf; see POSE_TRAIL_WINDOW block for the design) ---
        # pose_gate_stale_frames: skip pose entirely once the ball has been
        #   untracked this long (no contact can consume pose past the reentry
        #   horizon). <=0 disables the staleness gate.
        # pose_near_ball_radius_px: when the ball IS tracked, only estimate
        #   pose for players within this distance of a recent ball point
        #   (point-to-bbox, POSE_TRAIL_WINDOW trail). <=0 disables the radius.
        pose_gate_stale_frames: int = 30,
        pose_near_ball_radius_px: float = 300.0,
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

        self._pose_gate_stale_frames = pose_gate_stale_frames
        self._pose_radius = pose_near_ball_radius_px
        # Diagnostics (how much pose the gate skipped; tests + perf reports).
        self.pose_gate_stats = {"posed": 0, "skipped_stale": 0, "skipped_radius": 0}

        # Ball trajectory of REAL (non-predicted) positions:
        # (frame, x, y, w, h) -- width feeds the near/far side estimate.
        # ``_backfill_frames`` flags the frames whose point was retro-extended
        # by the BallTracker's T5 backfill mechanism (flag only: a backfilled
        # point is consumed exactly like a real sighting).
        self._ball_history: deque = deque(maxlen=120)
        self._backfill_frames: set = set()
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

        # T4 diagnostics: OFF by default. When FrameProcessor enables it, every
        # contact probe (accepted or refused) is mirrored into `_diag_records`
        # keyed by its CONTACT frame, with the gate that refused it. Pure
        # observation -- no threshold, branch or return value reads these.
        self.diag_enabled = False
        self._diag_records: List[Dict[str, Any]] = []
        self._diag_seen_at: Optional[int] = None

        self.logger = logging.getLogger(__name__)

    def _diag(self, **record: Any) -> None:
        """Mirror one contact-probe result (no-op unless diag is enabled)."""
        if self.diag_enabled:
            self._diag_records.append(record)

    def pop_diag(self) -> List[Dict[str, Any]]:
        """Take the contact-probe records collected since the last call."""
        recs, self._diag_records = self._diag_records, []
        return recs

    def set_court_calibration(self, court) -> None:
        """Set court calibration for spatial reasoning."""
        self.court = court

    def reset(self) -> None:
        """Reset all per-video state."""
        self._ball_history.clear()
        self._backfill_frames.clear()
        self._player_pose_history.clear()
        self._last_contact_frame = -1000
        self._last_touch_team = None
        self._last_touch_frame = None
        self._last_touch_went_over = False
        self.pose_gate_stats = {"posed": 0, "skipped_stale": 0, "skipped_radius": 0}
        self._resolver.reset()
        self._pending = None
        self._diag_records = []

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

        if self.diag_enabled:
            self._diag_records = []
            self._diag_seen_at = frame_number

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
        #
        # PERF GATE (2026-09-27): a history entry is appended for EVERY observed
        # player regardless -- snapshot selection, the L-R index and the
        # takeoff-stance read only use center/bbox/team, and they must stay
        # byte-identical. Only the expensive MediaPipe call is gated:
        #   - ball untracked > pose_gate_stale_frames (dead time; no contact
        #     can consume pose past the reentry horizon): skip pose;
        #   - ball tracked: pose players within pose_near_ball_radius_px of a
        #     ball point in the last POSE_TRAIL_WINDOW frames (see the class
        #     constant block for the measured bound);
        #   - ball lost 1..stale_frames ago (in-rally occlusion gap): pose
        #     everyone -- bridge contacts fire at the first re-sighting and may
        #     consume a snapshot from inside the gap (the recorded
        #     "occlusion-window fallback").
        observed = [d for d in player_detections if not d.get("predicted", False)]
        trail = None
        if observed:
            stale = self._ball_stale_frames(frame_number)
            pose_all = True
            if stale > self._pose_gate_stale_frames > 0:
                pose_all = False  # dead ball: nobody needs pose
                self.pose_gate_stats["skipped_stale"] += len(observed)
            elif stale > 0 or self._pose_radius <= 0:
                # occlusion window (or radius disabled): keep posing everyone
                pass
            else:
                pose_all = False
                trail = [
                    (p[1], p[2]) for p in self._ball_history
                    if frame_number - self.POSE_TRAIL_WINDOW <= p[0] <= frame_number
                ]
        for det in observed:
            tid = det.get("track_id")
            pose = None
            bbox = det.get("bbox", [])
            near_ball = pose_all
            if trail is not None:
                if len(bbox) == 4 and det.get("center") is not None:
                    near_ball = any(
                        self._point_to_bbox_distance(list(pt), bbox, det.get("center"))
                        <= self._pose_radius
                        for pt in trail
                    )
                    if not near_ball:
                        self.pose_gate_stats["skipped_radius"] += 1
            if pose_all or near_ball:
                if len(bbox) == 4:
                    pose = self.pose_estimator.estimate_pose(frame, bbox)
                    if pose:
                        pose["track_id"] = tid
                        self.pose_gate_stats["posed"] += 1
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
            self._diag(seen_at=frame_number, frame=contact_frame, stage="rejected",
                       reason="no_player_snapshot", kind=kind,
                       contact_point=[round(float(contact_point[0]), 1),
                                      round(float(contact_point[1]), 1)],
                       target_team=target_team, attribution_source=side_info.get("source"))
            return []
        pdata, distance, lr_index = chosen
        # Rally-opening serve reach: the server meets the ball at the top of
        # an extended toss -- arms overhead, box lagging below the hands --
        # so the ball-to-box distance overshoots the dig/spike reach (e7 f25:
        # 147.5 vs 140). Scoped to the rally-opening drive (the serve branch's
        # own gate); mid-rally reach rules are untouched (e2 f167's deliberate
        # 4px refusal sits there).
        reach = self.CONTACT_REACH
        if (kind == "drive"
                and contact_frame - self._last_contact_frame > self.RALLY_RESET_GAP):
            reach = self.SERVE_REACH_PX
        if distance > reach:
            self._diag(seen_at=frame_number, frame=contact_frame, stage="rejected",
                       reason="reach", kind=kind, distance=round(float(distance), 1),
                       reach=reach, track_id=pdata.get("track_id"),
                       player_id=lr_index, target_team=target_team)
            return []

        if kind == "reentry" or self._is_poke_drive(kind, out):
            # The contact-time snapshot is mid-jump by construction (a
            # manufactured reentry contact, or a poke-class drive: level
            # horizontal redirect of a fast descent) and its airborne feet
            # project deep (wrong side). Read the emitted team from the
            # takeoff stance instead (SpikeAnalyzer's takeoff-window fix).
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
        self._diag(seen_at=frame_number, frame=contact_frame,
                   stage="candidate_passed_gates", kind=kind,
                   gesture=contact_evt["gesture"].value,
                   gesture_confidence=contact_evt.get("gesture_confidence"),
                   track_id=contact_evt.get("track_id"),
                   player_id=contact_evt.get("player_id"),
                   team=contact_evt.get("team"),
                   near_net=contact_evt.get("near_net"),
                   behind_baseline=contact_evt.get("behind_baseline"),
                   ball_side=contact_evt.get("ball_side"),
                   attribution_source=contact_evt.get("attribution_source"),
                   contact_point=[round(float(contact_point[0]), 1),
                                  round(float(contact_point[1]), 1)])
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
            self._diag(stage="rejected", reason="context_confidence",
                       frame=contact_evt["frame"],
                       candidate_action=resolved.get("action"),
                       confidence=round(float(resolved.get("confidence", 0.0)), 3),
                       threshold=self.confidence_threshold,
                       gesture=contact_evt["gesture"].value,
                       kind=contact_evt.get("contact_kind"),
                       track_id=contact_evt.get("track_id"),
                       team=contact_evt.get("team"))
            return None
        cp = contact_evt["contact_point"]
        self._diag(stage="accepted", frame=contact_evt["frame"],
                   action=resolved["action"], gesture=contact_evt["gesture"].value,
                   track_id=contact_evt["track_id"], player_id=contact_evt["player_id"],
                   team=contact_evt.get("team"),
                   team_in_possession=resolved.get("team_in_possession"),
                   touch_number=resolved.get("touch_number"),
                   rally_id=resolved.get("rally_id"), kind=contact_evt.get("contact_kind"),
                   attribution_source=contact_evt.get("attribution_source"),
                   ball_side=contact_evt.get("ball_side"),
                   near_net=contact_evt.get("near_net"),
                   confidence=round(float(resolved["confidence"]), 3))
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

    def add_ball_sightings(self, points: List[Dict[str, Any]]) -> None:
        """Insert PAST ball sightings (tracker backfill) into the history.

        T5 mechanism B: when the ball tracker locks it can be several frames
        AFTER the contact, so the pre-contact history the contact probe needs
        was never emitted in real time. The tracker retro-extends it from the
        raw detections of frames it has already seen and hands it over here as
        ``(frame, x, y, w, h)`` tuples; they are consumed exactly like real
        sightings (the frame stamps are what the geometry reads) and flagged in
        ``_backfill_frames`` for diagnostics.

        Insertion keeps the history sorted by frame and never overwrites a
        point that already exists for that frame, so every window helper
        (``left[0]``, ``right[-1]``, ``before[-1]``) keeps its meaning.
        """
        if not points:
            return
        have = {p[0] for p in self._ball_history}
        fresh = []
        for p in points:
            frame = int(p["frame"])
            if frame in have:
                continue
            have.add(frame)
            fresh.append((frame, float(p["x"]), float(p["y"]),
                          float(p.get("w", 0.0)), float(p.get("h", 0.0))))
            self._backfill_frames.add(frame)
        if not fresh:
            return
        merged = sorted(list(self._ball_history) + fresh, key=lambda t: t[0])
        self._ball_history = deque(merged, maxlen=self._ball_history.maxlen)

    def _ball_stale_frames(self, frame_number: int) -> int:
        """Frames since the last REAL ball sighting in history (inf if none)."""
        if not self._ball_history:
            return frame_number + 1  # no sighting ever: certainly "dead"
        return frame_number - self._ball_history[-1][0]

    def _point_at(self, f: int) -> Optional[Tuple]:
        for p in self._ball_history:
            if p[0] == f:
                return p
        return None

    def _is_poke_drive(self, kind: str, out: Tuple[float, float]) -> bool:
        """True for a drive-band contact whose outgoing ball is LEVEL and
        strongly HORIZONTAL per frame -- the airborne-net-contact shape for
        the takeoff-stance team read (see POKE_EXIT_*; NOT the spike type,
        which SpikeAnalyzer decides by post-contact ascent). ``out`` is the
        net outgoing vector summed over the vertex's NEIGH window; dividing
        by NEIGH is the conservative (lower-bound) per-frame rate."""
        if kind != "drive":
            return False
        vx, vy = out[0] / self.NEIGH, out[1] / self.NEIGH
        return (abs(vx) >= self.POKE_EXIT_VX_PX
                and abs(vy) <= self.POKE_EXIT_VY_PX)

    def _takeoff_stance(self, track_id: Optional[int], frame: int) -> Optional[Dict[str, Any]]:
        """Nearest snapshot of the window's MAJORITY court team in
        [frame-REENTRY_TEAM_BACK, frame-REENTRY_TEAM_END] -- the last grounded
        read before a manufactured reentry contact (airborne contact-time feet
        project deep). The plain nearest-to-contact pick lands on the FIRST
        frame whose grounded foot has drifted across the net ground line (e6
        f307 reads B off the GT-A spiker whose f297-306 stances all read A);
        the majority over the window outvotes that 1-frame landing drift.
        Ties, an uncalibrated court, or no team reads: nearest snapshot (the
        old behavior)."""
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
        pick = None
        if self.court is not None and getattr(self.court, "is_calibrated", False):
            team_snaps = []
            for h in window:
                bbox = h.get("bbox")
                if not bbox:
                    continue
                team = self.court.get_team_for_bbox(bbox)
                if team:
                    team_snaps.append((team, h))
            counts: Dict[str, int] = {}
            for team, _h in team_snaps:
                counts[team] = counts.get(team, 0) + 1
            ordered = sorted(counts.items(), key=lambda kv: -kv[1])
            if ordered and (len(ordered) == 1
                            or ordered[0][1] > ordered[1][1]):
                majority = ordered[0][0]
                pool = [h for team, h in team_snaps if team == majority]
                pick = dict(min(pool, key=lambda h: abs(h["frame"] - hi)))
        if pick is None:
            pick = dict(min(window, key=lambda h: abs(h["frame"] - hi)))
        pick["track_id"] = track_id
        return pick

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
                    and len(self._real_points(c + 1, c + self.NEIGH)) >= 2
                    and self._normal_vertex_in_range(a[0], c)):
                return None  # dense both sides AND a fireable vertex there:
                # the normal detector's turf (e6 f265). Dense sides ALONE are
                # not enough to defer: the normal tests can still be provably
                # unable to host the touch. v3 e3 f379-384 (round-2 drift):
                # the arc's bottom was SEEN at a=f379, but the extra sighting
                # made f378 non-lowest while f379's right side went sparse
                # (two blind frames), and c=f384 is not a bottom (pre-gap
                # points sit lower) with an empty left3 killing the drive --
                # no frame can host the touch, and deferring dropped the set
                # (spike->dig->set->dig->block touch-chain cascade).
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

    def _normal_vertex_in_range(self, lo: int, hi: int) -> bool:
        """True when some real sighting in ``[lo, hi]`` can host a normal-path
        contact (the bridge may only defer a dense short gap to the normal
        detector if the normal detector can actually place the vertex). The
        touch itself sits inside the sighting gap; the only real sightings in
        range are its edges (``lo`` = last pre-gap, ``hi`` = first post-gap),
        and the normal tests are pure geometry over already-decided history,
        so checking those edges is exact."""
        return any(
            lo <= p[0] <= hi and self._normal_contact_at(p[0]) is not None
            for p in self._ball_history
        )

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
            self._diag(seen_at=self._diag_seen_at, frame=c, stage="rejected",
                       reason="pre_history")
            return None
        if c - self._last_contact_frame < self.MIN_CONTACT_GAP:
            self._diag(seen_at=self._diag_seen_at, frame=c, stage="rejected",
                       reason="min_contact_gap",
                       gap=c - self._last_contact_frame)
            return None

        vertex = self._point_at(c)
        if vertex is None:
            self._diag(seen_at=self._diag_seen_at, frame=c, stage="rejected",
                       reason="no_ball_sighting")
            return None

        # Gap-bridged bounce first (see the BRIDGE_* constants): if c is the
        # first sighting after a qualifying gap, the normal tests below cannot
        # fire (the gap leaves no left-side points within NEIGH) and only the
        # bridge can see the touch that happened inside the gap.
        bridged = self._bridge_contact(c, vertex)
        if bridged is not None:
            self._diag(seen_at=self._diag_seen_at, frame=c, stage="candidate_found",
                       kind="bounce", source="bridge")
            return bridged[0], bridged[1], bridged[2], bridged[3], c
        # Reentry band next (see the REENTRY_* constants): an out-of-frame
        # excursion the tracker never bridged -- the gap endpoints are not
        # free-flight connectible and the outgoing run is attack-fast.
        reentry = self._reentry_contact(c, vertex)
        if reentry is not None:
            self._diag(seen_at=self._diag_seen_at, frame=reentry[4],
                       stage="candidate_found", kind="reentry", source="reentry")
            return reentry
        normal = self._normal_contact_at(c)
        if normal is None:
            self._diag(seen_at=self._diag_seen_at, frame=c, stage="rejected",
                       reason="no_contact_geometry", bridge_considered=True,
                       reentry_considered=True)
        return normal

    def _normal_contact_at(
        self, c: int
    ) -> Optional[Tuple[List[float], str, Tuple[float, float], Tuple[float, float], int]]:
        """The normal vertex tests at a REAL sighting ``c``: bounce
        (fall-and-rise), redirect (horizontal deflect), drive (attacking hit)
        and the rally-opening serve branch. Pure geometry -- no gating beyond
        the data itself -- so :meth:`_bridge_contact` can reuse it to ask
        "could the normal path actually host this touch?" without duplicating
        (and drifting from) the thresholds."""
        vertex = self._point_at(c)
        if vertex is None:
            return None
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
        #
        # left3/right3 (±3f of the vertex) are shared with the drive test
        # below. LOCALITY (e7 f239, ratified-retune session): the reversal
        # must be visible in the vertex's OWN ±3f window -- a flip measured
        # only over the full NEIGH window can be a NEIGHBOR contact's
        # impulse leaking in (there: the f243 set's rightward drive, 6f
        # ahead, stole a mid-descent vertex and mislabeled it block).
        left3 = [p for p in left if p[0] >= c - 3]
        right3 = [p for p in right if p[0] <= c + 3]
        if inc[0] * out[0] < 0 and abs(inc[0]) > self.XREV_MIN and abs(out[0]) > self.XREV_MIN:
            # Fewer than 2 sightings within ±3f: locality is unprovable --
            # fall through (the drive test still gets its say).
            if len(right3) >= 2:
                out_local = self._mean_velocity([vertex] + right3)
                if inc[0] * out_local[0] <= 0:
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
            # Rally-opening SERVE hit (e7 f25, ratified-retune session): an
            # overhand toss flows THROUGH the contact -- ascent into ascent --
            # so the bounce test has no descent and the drive test above
            # refuses a pop-up (a dig's signature). The serve's own signature:
            # the ascent is FED -- the incoming slope exceeds the preceding
            # window's, which free flight (gravity) can only decay. Measured
            # openings: e7 f25 vin3 -42 vs vin6 -13 (fires); e4's pure gravity
            # arc decelerates 25->1 px/f (vin3 < vin6, refuses everywhere);
            # e2's slow arc and e1's fed descent never qualify. Fires only
            # before ANY contact (c - last > rally gap); the resolver's
            # behind-baseline + rally-start rule does the labeling.
            vin6 = self._mean_velocity(
                [p for p in left if p[0] >= c - 6] + [vertex]) \
                if any(p[0] >= c - 6 for p in left) else None
            if (pops_up and speed >= self.DRIVE_MIN_SPEED
                    and vin6 is not None
                    and abs(vin[1]) >= abs(vin6[1]) + self.SERVE_ACCEL_MARGIN_PX
                    and c - self._last_contact_frame > self.RALLY_RESET_GAP):
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
