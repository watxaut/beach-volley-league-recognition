"""
Ball tracker for volleyball video analysis.

Conservative tracker: when the ball is lost, returns None instead of
hallucinating positions. Predictions are limited to a few frames and
validated against court bounds.

Ball-matching design (2026-09-06 rework -- "always track the ball in play"):

Practice and tournament footage contains many balls: spares on the sand,
ball carts on the sidelines, other courts in view. The old tracker trusted
the detector's top-1-confidence cull and picked candidates by confidence,
so a high-confidence spare (courtside ball, rack ball) could bootstrap the
track or steal it mid-rally (entreno_6: the whole serve was lost to a
bottom-right spare; entreno_7: a static rack ball stole the f244 set).

The tracker is now the sole decision maker and uses trajectory, not
confidence, as the identity signal:

- UNLOCKED (bootstrap / after a reset): no ball is emitted until some
  candidate demonstrates MOTION (>= ``lock_min_speed`` px/f across the
  recent sighting window). Static spares can never bootstrap the track,
  and the serve toss locks the tracker within ~1-2 frames of appearing.
- LOCKED: the primary candidate is the highest-confidence one -- exactly the
  detection the old top-1 cull would have handed over -- validated against a
  trajectory gate around the last position (growing with missing frames, as
  before). One divergence: when that primary candidate is flagged
  ``stationary_suspect`` by the detector (a possibly-parked ball -- a parked
  ball cannot be the continuation of a moving one) and it fails the gate,
  the tracker re-acquires on the best in-gate plausible candidate instead of
  starving behind it. A moving top-1 that merely left the gate is trusted:
  the tracker coasts and waits for it, exactly as before.
- After ``max_missing_frames`` the tracker resets to UNLOCKED (and the
  re-lock again requires motion -- a drifting spare cannot be re-locked).

Low-confidence floor (2026-09-24, the 20260920 "blue sky" mechanism):

The match probe showed the detector's confidence is background-dependent --
sky-backed candidates read med 0.90 (92% >= 0.4) while sand/building-backed
read med 0.20 (9% >= 0.4) -- so on real match footage the ball routinely
DROPS below ``low_confidence_threshold`` mid-rally and the track starves
(the largest measured loss class: 33-68% of frames in starved episodes).
Two floors (both non-suspect-only, both 0 = off) let the tracker keep the
ball it still SEES:

- ``locked_low_conf_floor``: while LOCKED, when the frame contains NO
  candidate at ``low_confidence_threshold``, the best non-suspect candidate
  >= this floor inside the SAME growing trajectory gate is accepted. Frames
  with any high-tier candidate keep the P0 semantics untouched -- in
  particular the trusted coast (a moving top candidate that left the gate
  is waited for, never traded for an in-gate low-conf maybe).
- ``boot_low_conf_floor``: while UNLOCKED, if no motion pair exists among
  high-tier sightings, the same motion-pair gates (>= ``lock_min_speed``,
  <= ``lock_max_jump``, pair gap <= ``lock_max_pair_gap``) may use
  sightings >= this floor. Static spares still can never bootstrap
  (stationary_suspect excluded, motion still required).

T5 serve admission (2026-09-29, both DEFAULT OFF -- measured, not adopted;
see ``docs/t5_serve_admission_diagnosis.md``):

- ``weak_min_speed`` / ``weak_max_width`` (mechanism A): a second, WEAKER
  motion tier for far-band balls while UNLOCKED, so a far-side serve toss
  (1.6-6.7 px/f, 3-4x slower in pixels than a near-side one) can lock. Refuted
  as a recovery mechanism: ~19 new bootstrap locks per 4968 dev-clip frames and
  still no far-serve contact candidate.
- ``backfill_lookback`` and friends (mechanism B): on a FRESH lock, walk the
  recent RAW-detection buffer backwards from the lock point, frame by frame,
  taking the nearest plausible detection inside a radius that grows with age.
  This gives the contact probe the pre-contact history the lock arrived too
  late to observe, and creates NO new lock opportunity (it is purely additive
  and never touches the trajectory the locked path gates on). It closes the
  step-1 evidence gap (the probe's ``no_ball_sighting`` rejections at the far
  serves) but the contact probe's own serve signature still refuses the far
  float toss, so the mechanism ships OFF.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from collections import deque
import logging


class BallTracker:
    """Tracks a single volleyball across video frames.

    Design principles:
    - When ball is lost, return None (don't hallucinate).
    - Short prediction window (max 10 frames).
    - Minimum confidence threshold (0.4) to accept a detection.
    - Trajectory gates keep identity; confidence never selects identity.
    - Only a MOVING detection can (re-)bootstrap the track: "in play" means
      moving, so spares/rack balls cannot own the track.
    - Optional court bounds check to reject out-of-bounds predictions.
    """

    def __init__(
        self,
        max_missing_frames: int = 10,
        trajectory_smoothing: int = 5,
        velocity_threshold: float = 200.0,
        low_confidence_threshold: float = 0.4,
        max_trajectory_gap: float = 60.0,
        court_bounds: Optional[tuple] = None,
        lock_min_speed: float = 8.0,
        lock_motion_window: int = 5,
        lock_max_jump: float = 90.0,
        lock_max_pair_gap: int = 2,
        selection_conf_window: float = 10.0,
        locked_low_conf_floor: float = 0.15,
        boot_low_conf_floor: float = 0.15,
        # --- T5 serve-admission mechanisms (both 0/False = OFF) ---
        # (A) weak-speed lock tier: while UNLOCKED, a far-band candidate
        # (apparent width < ``weak_max_width``) may bootstrap the track on a
        # SLOWER motion pair (``weak_min_speed`` px/f) than the fast
        # ``lock_min_speed`` bar. Off unless ``weak_min_speed`` > 0.
        weak_min_speed: float = 0.0,
        weak_max_width: float = 0.0,
        # (B) backfill on a FRESH lock: retro-extend the track backwards
        # through the recent raw-detection buffer so the contact probe gets the
        # PRE-contact history a far-side toss never locked in real time.
        # ``backfill_lookback`` frames back (0 = off).
        backfill_lookback: int = 0,
        backfill_radius: float = 30.0,
        backfill_radius_growth: float = 10.0,
        backfill_max_gap: int = 2,
        backfill_max_width: float = 0.0,
        backfill_min_conf: float = 0.15,
        backfill_skip_suspect: bool = False,
    ):
        """Initialize the ball tracker.

        Args:
            max_missing_frames: Max frames before returning None.
            trajectory_smoothing: Window size for position smoothing.
            velocity_threshold: Max velocity magnitude (px/frame).
            low_confidence_threshold: Min confidence to accept a detection.
            max_trajectory_gap: Base distance (px) for trajectory continuation.
            court_bounds: Optional (x1, y1, x2, y2) to reject out-of-bounds predictions.
            lock_min_speed: Min speed (px/f) a candidate must demonstrate to
                bootstrap the track (an "in play" ball moves; a spare doesn't).
            lock_motion_window: Frames of recent sightings consulted for that
                motion evidence while unlocked.
            lock_max_jump: Max displacement (px) between two sightings of the
                same candidate for them to count as one moving ball.
            lock_max_pair_gap: Max frame gap between the two sightings that
                prove motion. Intermittently-detected spares show apparent
                speed across multi-frame gaps; real in-play sightings are
                dense, so the motion pair must be near-consecutive.
            selection_conf_window: Distance (px) under which a higher-confidence
                in-gate candidate beats a marginally closer one when
                re-acquiring past a stationary-suspect blocker.
            locked_low_conf_floor: LOCKED admission floor for frames with NO
                >= ``low_confidence_threshold`` candidate: the best non-suspect
                candidate >= this floor inside the trajectory gate is accepted
                (sand/building-backed balls read low-confidence; the 20260920
                probe). 0 disables.
            boot_low_conf_floor: UNLOCKED motion-pair floor when no high-tier
                pair exists (same geometric gates). 0 disables.
            weak_min_speed: T5 mechanism A -- a second, WEAKER motion tier for
                the UNLOCKED bootstrap, so a far-side serve toss (1.6-6.7 px/f,
                3-4x slower in pixels than a near-side one) can lock before
                contact. 0 disables the tier entirely.
            weak_max_width: apparent pixel width ceiling for the weak tier
                (far band). 0 disables the width gate.
            backfill_lookback: T5 mechanism B -- how many PAST frames a fresh
                lock may retro-extend through the raw-detection buffer. 0 = off.
            backfill_radius: chain-association radius (px) for the frame right
                before the lock point.
            backfill_radius_growth: extra radius (px) per frame of age, so the
                slow pre-contact toss (and the direction change at contact) can
                still be followed.
            backfill_max_gap: frames the chain may pass with no plausible
                detection before it is abandoned.
            backfill_max_width: apparent width ceiling for a backfilled point
                (far band). 0 disables the width gate.
            backfill_min_conf: confidence floor for a backfilled point.
            backfill_skip_suspect: also refuse ``stationary_suspect`` points
                (detector persist >= ``static_suspect_frac``) in the chain.
        """
        self.max_missing_frames = max_missing_frames
        self.trajectory_smoothing = trajectory_smoothing
        self.velocity_threshold = velocity_threshold
        self.low_confidence_threshold = low_confidence_threshold
        self.max_trajectory_gap = max_trajectory_gap
        self.court_bounds = court_bounds

        self.lock_min_speed = lock_min_speed
        self.lock_motion_window = lock_motion_window
        self.lock_max_jump = lock_max_jump
        self.lock_max_pair_gap = lock_max_pair_gap
        self.selection_conf_window = selection_conf_window
        self.locked_low_conf_floor = locked_low_conf_floor
        self.boot_low_conf_floor = boot_low_conf_floor

        self.weak_min_speed = weak_min_speed
        self.weak_max_width = weak_max_width
        self.backfill_lookback = backfill_lookback
        self.backfill_radius = backfill_radius
        self.backfill_radius_growth = backfill_radius_growth
        self.backfill_max_gap = backfill_max_gap
        self.backfill_max_width = backfill_max_width
        self.backfill_min_conf = backfill_min_conf
        self.backfill_skip_suspect = backfill_skip_suspect

        # State
        self.locked = False
        self.trajectory: deque = deque(maxlen=120)
        self.velocities: deque = deque(maxlen=10)
        self.missing_count = 0
        self.last_position: Optional[List[float]] = None
        self.last_velocity: Optional[List[float]] = None
        # Per-frame candidate centers while UNLOCKED (motion evidence). One
        # entry per frame, oldest first; empty frames advance the window.
        self._recent_centers: deque = deque(maxlen=max(2, lock_motion_window))
        # Parallel window at the low floor (superset when
        # boot_low_conf_floor < low_confidence_threshold): the low-tier motion
        # pair needs the previous frames' LOW-TIER sightings, which the high
        # window never saw.
        self._recent_centers_low: deque = deque(maxlen=max(2, lock_motion_window))
        # Out-of-view re-entry window (see _handle_missing): the ball left the
        # observable court region; wait for it near the exit point instead of
        # resetting into whatever moves next.
        self._await_reentry = False
        self._reentry_anchor: Optional[List[float]] = None

        # T5 mechanism B state. ``_det_buffer`` keeps the RAW detections of the
        # last ``backfill_lookback`` frames (the only history a fresh lock is
        # allowed to reach back into -- strictly past frames, so the mechanism
        # stays causal and live-debug parity is untouched). ``_backfill_out``
        # holds the chain produced by the most recent fresh lock until the
        # caller takes it.
        self._frame_seq = 0
        self._current_frame: int = 0
        self._det_buffer: deque = deque(maxlen=max(2, backfill_lookback + 1))
        self._backfill_out: List[Dict[str, Any]] = []

        # T4 diagnostics: OFF by default. `update` records the branch it took
        # (lock / admission / coast / gate miss / re-entry wait) in
        # `_diag_reason`; `pop_diag` hands the mirror to FrameProcessor. Pure
        # observation -- no branch, threshold or return value depends on it.
        self.diag_enabled = False
        self._diag_reason: str = "none"
        self._diag_last: Optional[Dict[str, Any]] = None

        self.logger = logging.getLogger(__name__)

    def set_court_bounds(self, bounds: tuple) -> None:
        """Set court bounds for out-of-bounds rejection.

        Args:
            bounds: (x1, y1, x2, y2) court bounding box.
        """
        self.court_bounds = bounds

    def update(self, detections: List[Dict[str, Any]],
               frame_number: Optional[int] = None
               ) -> Optional[Dict[str, Any]]:
        """Update tracker with new detections (thin diagnostic wrapper).

        ``frame_number`` is the caller's frame index (the shared
        ``FrameProcessor.process_frame`` path passes it); when omitted an
        internal per-update counter is used, so bare callers (tests, probe
        scripts) keep working. It is only consumed by the T5 backfill
        mechanism (OFF by default), which labels the raw-detection buffer it
        may reach back into.
        """
        self._current_frame = (self._frame_seq if frame_number is None
                               else int(frame_number))
        self._frame_seq += 1
        self._diag_reason = "locked" if self.locked else "unlocked"
        result = self._update(detections)
        if self.diag_enabled:
            self._diag_last = {
                "state": ("tracked" if result is not None and not result.get("is_predicted")
                          else "predicted" if result is not None
                          else "none"),
                "locked": self.locked,
                "missing": self.missing_count,
                "await_reentry": self._await_reentry,
                "center": (result or {}).get("center"),
                "conf": (result or {}).get("confidence"),
                "reason": self._diag_reason,
                "backfill": len(self._backfill_out),
            }
        return result

    def pop_diag(self) -> Optional[Dict[str, Any]]:
        """Take the diagnostic mirror of the last update (None when diag off)."""
        last, self._diag_last = self._diag_last, None
        return last

    def pop_backfill(self) -> List[Dict[str, Any]]:
        """Take the backfilled past sightings of the last fresh lock.

        Each entry is ``{"frame_offset", "center", "width", "height",
        "confidence", "source": "backfill"}`` where ``frame_offset`` is
        negative (frames before the lock frame). Empty when the mechanism is
        off or the chain found nothing.
        """
        out, self._backfill_out = self._backfill_out, []
        return out

    def _update(self, detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Update tracker with new detections.

        Args:
            detections: Ball detections from current frame (ALL candidates
                passing the detector's filters -- the tracker picks).

        Returns:
            Tracked ball dict or None if ball is lost / not yet locked.
        """
        valid = [d for d in detections
                 if d.get("confidence", 0.0) >= self.low_confidence_threshold]
        boot_low = self._tier(detections, self.boot_low_conf_floor)
        lock_low = self._tier(detections, self.locked_low_conf_floor)

        # T5 mechanism B: keep this frame's RAW detections (only while the
        # mechanism is on) so a fresh lock can retro-extend through them.
        if self.backfill_lookback > 0:
            self._det_buffer.append((self._current_frame, list(detections)))

        if not self.locked:
            out = self._try_lock(valid, boot_low)
            self._diag_reason = "bootstrap_locked" if out is not None else "unlocked_no_motion"
            return out

        if not valid:
            # No high-tier candidate this frame: the ball most likely dropped
            # below ``low_confidence_threshold`` against a sand/building
            # background. If it is still inside the trajectory gate at the low
            # floor, keep it; otherwise coast as before. (A re-entry wait is
            # never traded: while the ball is provably out of view, anything
            # moving is a distractor by the re-entry rule.)
            if not self._await_reentry:
                low = self._select_low_candidate(lock_low)
                if low is not None:
                    self._diag_reason = "low_floor_admitted"
                    return self._accept_detection(low)
            self._diag_reason = ("await_reentry" if self._await_reentry
                                 else "no_high_tier_candidate")
            return self._handle_missing()

        if self._await_reentry:
            best = self._select_reentry(valid)
            self._diag_reason = "reentry_gate_admitted" if best is not None else "reentry_gate"
        else:
            best = self._select_candidate(valid)
        if best is None:
            if self._diag_reason in ("locked", "reentry_gate_admitted"):
                self._diag_reason = "trajectory_gate_miss"
            return self._handle_missing()

        self._diag_reason = "locked_admitted"
        return self._accept_detection(best)

    def _tier(self, detections: List[Dict[str, Any]],
              floor: float) -> List[Dict[str, Any]]:
        """Candidates between ``floor`` and the high threshold (or [] when the
        mechanism is off / the floors coincide)."""
        if floor <= 0 or floor >= self.low_confidence_threshold:
            return []
        return [d for d in detections
                if floor <= d.get("confidence", 0.0)
                < self.low_confidence_threshold]

    # ------------------------------------------------------------------
    # Locking (bootstrap / re-lock after a reset)
    # ------------------------------------------------------------------

    def _try_lock(self, candidates: List[Dict[str, Any]],
                  low_candidates: Optional[List[Dict[str, Any]]] = None
                  ) -> Optional[Dict[str, Any]]:
        """Unlock state: watch for a candidate that demonstrably moves.

        A spare ball sitting on the sand or in a rack produces near-static
        sightings and can never bootstrap the track. The first candidate with
        a sighting ``lock_max_jump``-close in a previous windowed frame at
        >= ``lock_min_speed`` px/f is locked (usually the serve toss).
        """
        centers = [d["center"] for d in candidates
                   if not d.get("stationary_suspect")]
        history = list(self._recent_centers)  # oldest first, excludes current
        self._recent_centers.append(centers)

        low_scan = (low_candidates is not None and self.boot_low_conf_floor > 0)
        if low_scan:
            low_centers = [d["center"] for d in low_candidates
                           if not d.get("stationary_suspect")]
            self._recent_centers_low.append(low_centers)

        # Highest-confidence plausible candidates first (a possibly-parked
        # ball can never bootstrap the track). The motion pair must be
        # near-consecutive (see lock_max_pair_gap).
        plausible = [d for d in candidates if not d.get("stationary_suspect")]
        hit = self._scan_motion_pair(plausible, history)
        if hit is not None:
            return self._bootstrap_detection(*hit)

        # Low-floor bootstrap: same gates over the low tier's own window (a
        # superset history -- it contains the high-tier sightings too, so a
        # high-current x low-previous pair still fires). Off by default-valve
        # ``boot_low_conf_floor = 0``; a spare still cannot lock (motion
        # required, suspects excluded).
        if low_scan and self.boot_low_conf_floor < self.low_confidence_threshold:
            low_plausible = [d for d in low_candidates
                             if not d.get("stationary_suspect")]
            low_history = list(self._recent_centers_low)[:-1]
            hit = self._scan_motion_pair(low_plausible, low_history)
            if hit is not None:
                return self._bootstrap_detection(*hit)

        # T5 mechanism A -- WEAK-SPEED TIER (off unless weak_min_speed > 0).
        # A far-side toss rises 1.6-6.7 px/f (the same toss is 7-17 px/f near
        # the camera), so the fast 8 px/f bar -- measured on near-side balls --
        # is above what a far serve can ever produce and the contact probe
        # loses its pre-contact history. This tier adds NO geometry the fast
        # path lacks, only a lower bar, gated on the far apparent-width band
        # so near-side behaviour is untouched.
        if self.weak_min_speed > 0 and self.weak_min_speed < self.lock_min_speed:
            weak_candidates = [d for d in (plausible + (low_plausible if low_scan else []))
                               if self._width_ok(d, self.weak_max_width)]
            weak_history = (history if not low_scan else
                            self._merge_history(history,
                                                list(self._recent_centers_low)[:-1]))
            hit = self._scan_motion_pair(
                weak_candidates, weak_history, min_speed=self.weak_min_speed)
            if hit is not None:
                return self._bootstrap_detection(*hit)
        return None

    @staticmethod
    def _merge_history(high: List[List[List[float]]],
                       low: List[List[List[float]]]
                       ) -> List[List[List[float]]]:
        """Union two same-length sighting windows, oldest first.

        The high and low bootstrap windows advance one entry per frame, so they
        align index-wise; concatenating them would put empty low-tier frames
        between real high-tier ones and MIS-AGE the motion pairs (a pair two
        entries apart reads as half the speed).
        """
        if not low:
            return high
        if not high:
            return low
        n = min(len(high), len(low))
        merged: List[List[List[float]]] = []
        for i in range(len(high) - n, len(high)):
            merged.append(list(high[i]) + list(low[i - (len(high) - n)]))
        return merged

    @staticmethod
    def _width_ok(det: Dict[str, Any], max_width: float) -> bool:
        """Apparent-width band gate (0 = disabled)."""
        if not max_width or max_width <= 0:
            return True
        bbox = det.get("bbox") or []
        if len(bbox) < 4:
            return True
        return (float(bbox[2]) - float(bbox[0])) <= max_width

    def _scan_motion_pair(
            self, plausible: List[Dict[str, Any]],
            history: List[List[List[float]]],
            min_speed: Optional[float] = None,
    ) -> Optional[Tuple[Dict[str, Any], List[float], int]]:
        """First (det, old_sighting, gap) proving >= lock_min_speed motion.

        Shared by the high-tier and low-floor bootstrap scans; the caller owns
        the candidate window (``history`` excludes the current frame).
        ``min_speed`` overrides the bar (T5 mechanism A's weak tier).
        """
        bar = self.lock_min_speed if min_speed is None else min_speed
        for det in sorted(plausible, key=lambda d: d.get("confidence", 0.0),
                          reverse=True):
            c = det["center"]
            for age, frame_centers in enumerate(
                    reversed(history), start=1):
                if age > self.lock_max_pair_gap:
                    break
                for old in frame_centers:
                    dist = float(np.hypot(c[0] - old[0], c[1] - old[1]))
                    if dist <= self.lock_max_jump:
                        speed = dist / age
                        if speed >= bar:
                            return det, old, age
                    # A jump this large means the oldest matching sighting
                    # does not belong to this candidate; keep scanning older
                    # frames only via the loop above (older = larger age).
        return None

    def _bootstrap_detection(self, det: Dict[str, Any], old: List[float],
                             gap: int) -> Dict[str, Any]:
        """Lock onto a moving candidate; velocity from the motion evidence."""
        self._await_reentry = False
        self._reentry_anchor = None
        center = det["center"]
        velocity = [(center[0] - old[0]) / gap, (center[1] - old[1]) / gap]
        mag = float(np.hypot(*velocity))
        if mag > self.velocity_threshold:
            velocity = None

        self.locked = True
        self.trajectory.clear()
        self.velocities.clear()
        self._recent_centers.clear()
        self._recent_centers_low.clear()
        self.trajectory.append(center)
        self.last_position = center
        self.last_velocity = velocity
        self.missing_count = 0

        result = det.copy()
        result.update({
            "velocity": velocity,
            "trajectory_length": len(self.trajectory),
            "smoothed_position": center,
            "ball_state": self._classify_state(),
            "is_predicted": False,
        })
        # T5 mechanism B: retro-extend through the raw-detection buffer so the
        # contact probe sees the pre-contact history this lock arrived too late
        # to observe. Purely ADDITIVE and off by default; it never touches the
        # trajectory the locked path gates on, so no tracking decision moves.
        if self.backfill_lookback > 0:
            self._backfill_out = self._chain_backfill(self._current_frame, det)
        self.logger.debug("Ball tracker locked (speed %.1f px/f)", mag)
        return result

    # ------------------------------------------------------------------
    # T5 mechanism B -- backfill on a fresh lock
    # ------------------------------------------------------------------

    def _chain_backfill(self, lock_frame: int,
                        lock_det: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Walk the raw-detection buffer BACKWARDS from a fresh lock point.

        The lock proves the ball moved fast AFTER the contact; what the contact
        probe needs is the slow toss BEFORE it. The chain therefore does not
        extrapolate the post-contact line (a serve reverses direction at the
        contact) -- it walks frame by frame, each step taking the detection
        NEAREST the point accepted before it, inside a radius that grows with
        age (so a 2-7 px/f toss and the direction change are both reachable).

        Stops at the first stretch of ``backfill_max_gap`` frames with no
        plausible detection. Detections the detector removed as static
        (``persist >= ball_static_persist``) never reach the tracker, and
        ``backfill_skip_suspect`` additionally refuses the flagged ones.

        Causal by construction: only frames already seen are consulted.
        """
        lookback = int(self.backfill_lookback)
        if lookback <= 0:
            return []
        anchor = list(lock_det["center"])
        chain: List[Tuple[int, Dict[str, Any]]] = []
        misses = 0
        entries = list(self._det_buffer)          # oldest first
        for frame, dets in reversed(entries):
            age = lock_frame - frame
            if age <= 0:
                continue                           # the lock frame itself
            if age > lookback:
                break
            radius = self.backfill_radius + self.backfill_radius_growth * (age - 1)
            best = None
            for det in dets:
                if det.get("confidence", 0.0) < self.backfill_min_conf:
                    continue
                if self.backfill_skip_suspect and det.get("stationary_suspect"):
                    continue
                if not self._width_ok(det, self.backfill_max_width):
                    continue
                c = det["center"]
                dist = float(np.hypot(c[0] - anchor[0], c[1] - anchor[1]))
                if dist <= radius and (best is None or dist < best[0]):
                    best = (dist, det)
            if best is None:
                misses += 1
                if misses > self.backfill_max_gap:
                    break
                continue
            misses = 0
            chain.append((frame, best[1]))
            anchor = list(best[1]["center"])

        out: List[Dict[str, Any]] = []
        for frame, det in reversed(chain):        # oldest first
            bbox = det.get("bbox") or []
            w = float(bbox[2] - bbox[0]) if len(bbox) >= 4 else 0.0
            h = float(bbox[3] - bbox[1]) if len(bbox) >= 4 else 0.0
            out.append({
                "frame_offset": frame - lock_frame,
                "center": [float(det["center"][0]), float(det["center"][1])],
                "width": w,
                "height": h,
                "confidence": float(det.get("confidence", 0.0)),
                "source": "backfill",
            })
        return out

    # ------------------------------------------------------------------
    # Locked-state candidate selection
    # ------------------------------------------------------------------

    def _select_candidate(self, detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select the best detection, validated against the trajectory.

        Primary candidate = highest-confidence detection (what the old top-1
        cull handed the tracker), accepted when inside the growing gate
        around the last position. When the primary is a stationary-suspect
        (a possibly-parked ball cannot continue a moving trajectory) and it
        fails the gate, the best in-gate plausible candidate is taken
        instead of starving behind the parked ball. A moving primary that
        merely left the gate is trusted: return None and coast.
        """
        gate = self.max_trajectory_gap * (1 + self.missing_count * 0.5)
        ref = self.last_position

        def _dist(det):
            c = det["center"]
            return float(np.hypot(c[0] - ref[0], c[1] - ref[1]))

        top_all = max(detections, key=lambda d: d.get("confidence", 0.0))
        if _dist(top_all) <= gate:
            return top_all
        if not top_all.get("stationary_suspect"):
            self._diag_reason = "primary_out_of_gate"
            return None

        plausible = [d for d in detections if not d.get("stationary_suspect")]
        in_gate = [(_dist(d), d) for d in plausible if _dist(d) <= gate]
        if not in_gate:
            self._diag_reason = "suspect_blocker_no_candidate"
            return None
        min_dist = min(dist for dist, _ in in_gate)
        tied = [d for dist, d in in_gate
                if dist <= min_dist + self.selection_conf_window]
        return max(tied, key=lambda d: d.get("confidence", 0.0))

    def _select_low_candidate(
            self, detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """LOCKED low-floor admission for frames with NO high-tier candidate.

        The real ball often drops below ``low_confidence_threshold`` against
        sand/buildings while its GEOMETRY is unchanged (the 20260920 probe:
        sky-backed candidates med 0.90 vs sand-backed 0.20). When the frame
        contains no high-tier candidate at all, accept the closest
        non-suspect candidate >= ``locked_low_conf_floor`` inside the SAME
        growing gate around the last position -- proximity first, the
        suspect-blocker fallback's confidence tie-break. Frames WITH a
        high-tier candidate never reach this method, so the trusted coast and
        the suspect override keep their P0 semantics exactly.
        """
        if (self.locked_low_conf_floor <= 0
                or self.locked_low_conf_floor >= self.low_confidence_threshold
                or not detections):
            return None
        gate = self.max_trajectory_gap * (1 + self.missing_count * 0.5)
        ref = self.last_position
        if ref is None:
            return None

        def _dist(det):
            c = det["center"]
            return float(np.hypot(c[0] - ref[0], c[1] - ref[1]))

        in_gate = [(_dist(d), d) for d in detections
                   if not d.get("stationary_suspect") and _dist(d) <= gate]
        if not in_gate:
            return None
        min_dist = min(dist for dist, _ in in_gate)
        tied = [d for dist, d in in_gate
                if dist <= min_dist + self.selection_conf_window]
        return max(tied, key=lambda d: d.get("confidence", 0.0))

    def _select_reentry(self, detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Out-of-view re-entry: admit only plausible candidates near the exit
        point. Anything else moving while the ball is provably out of view is
        a distractor (a sand spare, a drill ball) and must not take the track.
        """
        if self._reentry_anchor is None:
            return None
        reach = 2 * self.max_trajectory_gap
        ax, ay = self._reentry_anchor
        in_reach = []
        for det in detections:
            if det.get("stationary_suspect"):
                continue
            c = det["center"]
            dist = float(np.hypot(c[0] - ax, c[1] - ay))
            if dist <= reach:
                in_reach.append((dist, det))
        if not in_reach:
            return None
        min_dist = min(dist for dist, _ in in_reach)
        tied = [d for dist, d in in_reach
                if dist <= min_dist + self.selection_conf_window]
        return max(tied, key=lambda d: d.get("confidence", 0.0))

    def _accept_detection(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """Accept a detection and update trajectory state."""
        self._await_reentry = False
        self._reentry_anchor = None
        center = detection["center"]

        # Compute velocity
        velocity = None
        if self.last_position is not None:
            vx = center[0] - self.last_position[0]
            vy = center[1] - self.last_position[1]
            mag = np.sqrt(vx ** 2 + vy ** 2)
            if mag <= self.velocity_threshold:
                velocity = [vx, vy]
                self.velocities.append(velocity)
                self.last_velocity = velocity

        self.trajectory.append(center)
        self.last_position = center
        self.missing_count = 0

        result = detection.copy()
        result.update({
            "velocity": velocity,
            "trajectory_length": len(self.trajectory),
            "smoothed_position": self._smoothed_position(),
            "ball_state": self._classify_state(),
            "is_predicted": False,
        })
        return result

    def _handle_missing(self) -> Optional[Dict[str, Any]]:
        """Handle frame with no valid detection."""
        self.missing_count += 1

        # Out-of-view re-entry window: when the coast prediction has left the
        # observable court region, the ball is provably out of the frame (a
        # lob over the camera's view). Resetting here would hand the track to
        # whatever spare moves next; instead hold a wide re-entry gate around
        # the exit point for a bounded horizon.
        if self.court_bounds is not None and self.last_position is not None \
                and self.last_velocity is not None and len(self.trajectory) >= 3:
            predicted = self._predict_position()
            if predicted is not None and not self._in_court_bounds(predicted):
                if not self._await_reentry:
                    self._await_reentry = True
                    self._reentry_anchor = list(self.last_position)
                if self.missing_count > 2 * self.max_missing_frames:
                    self._reset_tracker()
                    self._diag_reason = "track_reset_lost"
                else:
                    self._diag_reason = "out_of_view_reentry_wait"
                return None

        if self.missing_count > self.max_missing_frames:
            self._reset_tracker()
            self._diag_reason = "track_reset_lost"
            return None

        # Conservative prediction: only if we have good velocity data
        if self.last_position is None or self.last_velocity is None:
            self._diag_reason = "coast_no_velocity"
            return None
        if len(self.trajectory) < 3:
            self._diag_reason = "coast_short_trajectory"
            return None

        predicted = self._predict_position()
        if predicted is None:
            return None

        # Reject if outside court bounds
        if not self._in_court_bounds(predicted):
            self._diag_reason = "prediction_out_of_bounds"
            return None

        confidence = max(0.05, 0.3 - 0.03 * self.missing_count)
        self._diag_reason = "coast_predicted"

        return {
            "center": predicted,
            "confidence": confidence,
            "bbox": self._estimate_bbox(predicted),
            "class_name": "sports_ball",
            "velocity": self.last_velocity,
            "trajectory_length": len(self.trajectory),
            "smoothed_position": predicted,
            "ball_state": "predicted",
            "is_predicted": True,
            "missing_frames": self.missing_count,
        }

    def _in_court_bounds(self, point: List[float]) -> bool:
        """Court-bounds membership with the same small margin as before."""
        if self.court_bounds is None:
            return True
        x1, y1, x2, y2 = self.court_bounds
        margin = 50  # small margin
        return (x1 - margin <= point[0] <= x2 + margin and
                y1 - margin <= point[1] <= y2 + margin)

    def _predict_position(self) -> Optional[List[float]]:
        """Predict next position using linear velocity."""
        if self.last_position is None or self.last_velocity is None:
            return None

        t = self.missing_count
        px = self.last_position[0] + self.last_velocity[0] * t
        py = self.last_position[1] + self.last_velocity[1] * t
        return [px, py]

    def _smoothed_position(self) -> List[float]:
        """Weighted average of recent positions."""
        if not self.trajectory:
            return [0.0, 0.0]
        recent = list(self.trajectory)[-self.trajectory_smoothing:]
        weights = np.linspace(0.5, 1.0, len(recent))
        weights /= weights.sum()
        sx = float(np.average([p[0] for p in recent], weights=weights))
        sy = float(np.average([p[1] for p in recent], weights=weights))
        return [sx, sy]

    def _classify_state(self) -> str:
        """Classify ball state from velocity."""
        if not self.last_velocity:
            return "unknown"
        vx, vy = self.last_velocity
        if abs(vy) < 2:
            return "horizontal"
        return "ascending" if vy < 0 else "descending"

    def _estimate_bbox(self, center: List[float], size: int = 20) -> List[float]:
        half = size // 2
        return [center[0] - half, center[1] - half, center[0] + half, center[1] + half]

    def _reset_tracker(self) -> None:
        """Reset all state (back to the unlocked watch mode)."""
        self.locked = False
        self.trajectory.clear()
        self.velocities.clear()
        self._recent_centers.clear()
        self._recent_centers_low.clear()
        self._await_reentry = False
        self._reentry_anchor = None
        self.missing_count = 0
        self.last_position = None
        self.last_velocity = None
        self.logger.debug("Ball tracker reset (unlocked; waiting for motion)")

    def reset(self) -> None:
        """Public reset method (per-video)."""
        self._reset_tracker()
        self._det_buffer.clear()
        self._backfill_out = []
        self._frame_seq = 0
        self._current_frame = 0

    def get_trajectory(self) -> List[List[float]]:
        """Get full trajectory."""
        return list(self.trajectory)

    def get_ball_statistics(self) -> Dict[str, Any]:
        """Get trajectory statistics."""
        if len(self.trajectory) < 2:
            return {}
        positions = np.array(self.trajectory)
        distances = np.sqrt(np.sum(np.diff(positions, axis=0) ** 2, axis=1))
        return {
            "total_distance": float(np.sum(distances)),
            "average_speed": float(np.mean(distances)),
            "max_speed": float(np.max(distances)),
            "trajectory_points": len(self.trajectory),
            "x_range": [float(positions[:, 0].min()), float(positions[:, 0].max())],
            "y_range": [float(positions[:, 1].min()), float(positions[:, 1].max())],
            "current_state": self._classify_state(),
        }
