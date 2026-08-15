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
        # Accept but ignore legacy params
        enhanced_validation_config: Optional[Dict[str, Any]] = None,
    ):
        self.pose_estimator = pose_estimator
        self.temporal_window = temporal_window
        self.confidence_threshold = confidence_threshold
        self.court = court_calibration

        # Ball trajectory of REAL (non-predicted) positions: (frame, x, y).
        self._ball_history: deque = deque(maxlen=120)
        self._last_contact_frame: int = -1000

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
                self._ball_history.append((frame_number, float(center[0]), float(center[1])))

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

        contact_point, kind, inc, out = contact

        chosen = self._closest_player_at(contact_frame, contact_point)
        if chosen is None:
            return []
        pdata, distance, lr_index = chosen
        if distance > self.CONTACT_REACH:
            return []

        self._last_contact_frame = contact_frame

        # Layer 1: read the context-free visual gesture at this contact.
        contact_evt = self._build_contact(
            pdata, lr_index, contact_point, kind, inc, out, contact_frame
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
            "team": resolved["team_in_possession"],
            "touch_number": resolved["touch_number"],
            "rally_id": resolved["rally_id"],
            "contact_kind": contact_evt["contact_kind"],
        }

    # --- Ball-contact detection ---

    def _real_points(self, lo: int, hi: int) -> List[Tuple[int, float, float]]:
        """Real ball points with frame in [lo, hi], ordered by frame."""
        return [p for p in self._ball_history if lo <= p[0] <= hi]

    def _point_at(self, f: int) -> Optional[Tuple[int, float, float]]:
        for p in self._ball_history:
            if p[0] == f:
                return p
        return None

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
    ) -> Optional[Tuple[List[float], str, Tuple[float, float], Tuple[float, float]]]:
        """Test whether frame ``c`` is a ball contact.

        Returns (contact_point, kind, incoming_vec, outgoing_vec) or None.
        ``kind`` is "bounce" (fall-and-rise) or "redirect" (horizontal deflect).
        """
        if c <= self.NEIGH:
            return None
        if c - self._last_contact_frame < self.MIN_CONTACT_GAP:
            return None

        vertex = self._point_at(c)
        if vertex is None:
            return None
        _, vx, vy = vertex

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
                return contact_point, "bounce", inc, out

        # Horizontal redirect: ball arrives from one side and leaves to the
        # other (block/spike drive) without a clean bounce.
        if inc[0] * out[0] < 0 and abs(inc[0]) > self.XREV_MIN and abs(out[0]) > self.XREV_MIN:
            return contact_point, "redirect", inc, out

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
                    return contact_point, "drive", inc, out

        return None

    def _closest_player_at(
        self, frame: int, point: List[float]
    ) -> Optional[Tuple[Dict[str, Any], float, Optional[int]]]:
        """Find the tracked player closest to ``point`` around ``frame``.

        Returns (player_snapshot, distance, left_to_right_index) or None. The
        snapshot is the history entry nearest ``frame`` for that player; the
        L-R index ranks all players present near ``frame`` by x (matching the
        ground-truth annotation convention).
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

        ordered = sorted(snapshots, key=lambda s: s["center"][0])
        best = None
        best_dist = float("inf")
        for s in snapshots:
            # Distance to the player's BODY, not their torso centre: a player
            # digging low or reaching overhead at the net contacts the ball far
            # from their centre, but close to their bounding box (which spans
            # feet to raised hands). Centre distance would reject those touches.
            d = self._point_to_bbox_distance(point, s.get("bbox"), s["center"])
            if d < best_dist:
                best_dist = d
                best = s
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

        return {
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
