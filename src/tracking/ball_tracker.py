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
  re-lock again requires motion -- a drifting spare cannot be re-locked)."""

from typing import List, Dict, Any, Optional
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
        # Out-of-view re-entry window (see _handle_missing): the ball left the
        # observable court region; wait for it near the exit point instead of
        # resetting into whatever moves next.
        self._await_reentry = False
        self._reentry_anchor: Optional[List[float]] = None

        self.logger = logging.getLogger(__name__)

    def set_court_bounds(self, bounds: tuple) -> None:
        """Set court bounds for out-of-bounds rejection.

        Args:
            bounds: (x1, y1, x2, y2) court bounding box.
        """
        self.court_bounds = bounds

    def update(self, detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Update tracker with new detections.

        Args:
            detections: Ball detections from current frame (ALL candidates
                passing the detector's filters -- the tracker picks).

        Returns:
            Tracked ball dict or None if ball is lost / not yet locked.
        """
        valid = [d for d in detections
                 if d.get("confidence", 0.0) >= self.low_confidence_threshold]

        if not self.locked:
            return self._try_lock(valid)

        if not valid:
            return self._handle_missing()

        if self._await_reentry:
            best = self._select_reentry(valid)
        else:
            best = self._select_candidate(valid)
        if best is None:
            return self._handle_missing()

        return self._accept_detection(best)

    # ------------------------------------------------------------------
    # Locking (bootstrap / re-lock after a reset)
    # ------------------------------------------------------------------

    def _try_lock(self, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
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

        # Highest-confidence plausible candidates first (a possibly-parked
        # ball can never bootstrap the track). The motion pair must be
        # near-consecutive (see lock_max_pair_gap).
        plausible = [d for d in candidates if not d.get("stationary_suspect")]
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
                        if speed >= self.lock_min_speed:
                            return self._bootstrap_detection(det, old, age)
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
        self.logger.debug("Ball tracker locked (speed %.1f px/f)", mag)
        return result

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
            return None

        plausible = [d for d in detections if not d.get("stationary_suspect")]
        in_gate = [(_dist(d), d) for d in plausible if _dist(d) <= gate]
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
                return None

        if self.missing_count > self.max_missing_frames:
            self._reset_tracker()
            return None

        # Conservative prediction: only if we have good velocity data
        if self.last_position is None or self.last_velocity is None:
            return None
        if len(self.trajectory) < 3:
            return None

        predicted = self._predict_position()
        if predicted is None:
            return None

        # Reject if outside court bounds
        if not self._in_court_bounds(predicted):
            return None

        confidence = max(0.05, 0.3 - 0.03 * self.missing_count)

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
        self._await_reentry = False
        self._reentry_anchor = None
        self.missing_count = 0
        self.last_position = None
        self.last_velocity = None
        self.logger.debug("Ball tracker reset (unlocked; waiting for motion)")

    def reset(self) -> None:
        """Public reset method."""
        self._reset_tracker()

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
