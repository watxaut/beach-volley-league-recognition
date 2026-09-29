#!/usr/bin/env python3
"""T5 serve-admission mechanisms A and B, as SUBCLASSES of the production
components -- deliberately OUTSIDE ``src/``.

The T5 step-2 A/B replay (``scripts/probe_serve_mechanisms.py``) measured two
candidate fixes for the far-side serve loss, and BOTH were refuted as a
recovery: they recover 0/5 far serves (see ``docs/t5_mechanism_ab.md`` and
``docs/t5_serve_admission_diagnosis.md``). A refuted mechanism must not live
in ``src/``, so the probe harness keeps it reproducible here:

* **A -- weak-speed lock tier** (``weak_min_speed`` / ``weak_max_width``): a
  second, WEAKER motion bar for far-band balls while UNLOCKED, so a far-side
  serve toss (1.6-6.7 px/f, 3-4x slower in pixels than a near-side one) can
  lock before the contact. Refuted: ~19 new bootstrap locks per 4968 dev-clip
  frames, and still no far-serve contact candidate.
* **B -- backfill on a fresh lock** (``backfill_*``): on a FRESH lock, walk the
  recent RAW-detection buffer backwards from the lock point, taking the nearest
  plausible detection inside a radius that grows with age. It hands the contact
  probe the pre-contact history the lock arrived too late to observe. Refuted
  as a recovery too: it closes the ``no_ball_sighting`` evidence gap but the
  contact probe's own serve signature still refuses the far float toss, and it
  creates no new lock (by construction).

Both are INERT at their defaults: a harness tracker built with the production
constructor arguments and no mechanism flag behaves exactly like
``BallTracker`` (the ``base`` arm of the replay is the fidelity gate that
proves it, and ``tests/test_serve_backfill.py`` pins it).

Why the root blocker is NOT here: both mechanisms feed the contact probe
better ball history, but the probe still needs a *fed ascent* (the ball rising
towards the contact) and the far serve is a DECELERATING float. That is a
geometry/serve-branch question, not a tracker-admission one -- see the T5 row
in ``docs/action_reliability_plan.md``.
"""

from __future__ import annotations

import os
import sys
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from src.recognition.action_classifier import ActionClassifier  # noqa: E402
from src.tracking.ball_tracker import BallTracker  # noqa: E402

__all__ = ["ServeMechanismBallTracker", "ProbeClassifier", "width_ok"]


def width_ok(det: Dict[str, Any], max_width: float) -> bool:
    """Apparent-width band gate (0 / negative = disabled)."""
    if not max_width or max_width <= 0:
        return True
    bbox = det.get("bbox") or []
    if len(bbox) < 4:
        return True
    return (float(bbox[2]) - float(bbox[0])) <= max_width


def merge_history(high: List[List[List[float]]],
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


class ServeMechanismBallTracker(BallTracker):
    """``BallTracker`` + T5 mechanism A and B, both default-off.

    Every added branch is guarded by its own parameter
    (``weak_min_speed > 0`` / ``backfill_lookback > 0``); with the defaults the
    overrides only call ``super()``, so the object is a plain ``BallTracker``
    (the probe's ``base`` arm verifies that frame by frame).
    """

    def __init__(self, *args: Any,
                 weak_min_speed: float = 0.0,
                 weak_max_width: float = 0.0,
                 backfill_lookback: int = 0,
                 backfill_radius: float = 30.0,
                 backfill_radius_growth: float = 10.0,
                 backfill_max_gap: int = 2,
                 backfill_max_width: float = 0.0,
                 backfill_min_conf: float = 0.15,
                 backfill_skip_suspect: bool = False,
                 **kwargs):
        super().__init__(*args, **kwargs)
        # (A) weak-speed lock tier
        self.weak_min_speed = weak_min_speed
        self.weak_max_width = weak_max_width
        # (B) backfill on a fresh lock
        self.backfill_lookback = backfill_lookback
        self.backfill_radius = backfill_radius
        self.backfill_radius_growth = backfill_radius_growth
        self.backfill_max_gap = backfill_max_gap
        self.backfill_max_width = backfill_max_width
        self.backfill_min_conf = backfill_min_conf
        self.backfill_skip_suspect = backfill_skip_suspect

        # Mechanism B state. ``_det_buffer`` keeps the RAW detections of the
        # last ``backfill_lookback`` frames (the only history a fresh lock may
        # reach back into -- strictly PAST frames, so the probe stays causal);
        # ``_backfill_out`` holds the chain of the most recent fresh lock until
        # the caller takes it.
        self._frame_seq = 0
        self._current_frame: int = 0
        self._det_buffer: deque = deque(maxlen=max(2, backfill_lookback + 1))
        self._backfill_out: List[Dict[str, Any]] = []

    # -- plumbing ------------------------------------------------------

    def update(self, detections: List[Dict[str, Any]],
               frame_number: Optional[int] = None
               ) -> Optional[Dict[str, Any]]:
        """Production ``BallTracker.update`` plus the caller's frame index.

        ``frame_number`` only labels the raw-detection buffer mechanism B may
        reach back into; when omitted an internal per-update counter is used.
        """
        self._current_frame = (self._frame_seq if frame_number is None
                               else int(frame_number))
        self._frame_seq += 1
        return super().update(detections)

    def pop_backfill(self) -> List[Dict[str, Any]]:
        """Take the backfilled past sightings of the last fresh lock.

        Each entry is ``{"frame_offset", "center", "width", "height",
        "confidence", "source": "backfill"}`` with a negative
        ``frame_offset``. Empty when the mechanism is off or the chain found
        nothing.
        """
        out, self._backfill_out = self._backfill_out, []
        return out

    def reset(self) -> None:
        super().reset()
        self._det_buffer.clear()
        self._backfill_out = []
        self._frame_seq = 0
        self._current_frame = 0

    # -- mechanism A: weak-speed lock tier -----------------------------

    def _try_lock(self, candidates: List[Dict[str, Any]],
                  low_candidates: Optional[List[Dict[str, Any]]] = None
                  ) -> Optional[Dict[str, Any]]:
        """Production bootstrap; if it finds nothing, retry with a lower bar.

        The fast path is tried FIRST and untouched, so a production lock always
        wins and the extra locks mechanism A adds can only be extra. The weak
        scan then reuses the windows ``super()._try_lock`` has just appended
        to (``_recent_centers`` / ``_recent_centers_low``, current frame
        excluded), so it sees exactly the evidence production saw.
        """
        out = super()._try_lock(candidates, low_candidates)
        if out is not None or not (0 < self.weak_min_speed
                                   < self.lock_min_speed):
            return out

        plausible = [d for d in candidates if not d.get("stationary_suspect")]
        low_scan = (low_candidates is not None
                    and self.boot_low_conf_floor > 0)
        low_plausible = ([d for d in low_candidates
                          if not d.get("stationary_suspect")] if low_scan else [])
        history = list(self._recent_centers)[:-1]        # excludes current
        low_history = list(self._recent_centers_low)[:-1]

        weak_candidates = [d for d in (plausible + low_plausible)
                           if width_ok(d, self.weak_max_width)]
        weak_history = (history if not low_scan
                        else merge_history(history, low_history))
        hit = self._scan_motion_pair_with_bar(weak_candidates, weak_history,
                                              self.weak_min_speed)
        if hit is not None:
            return self._bootstrap_detection(*hit)
        return None

    def _scan_motion_pair_with_bar(
            self, plausible: List[Dict[str, Any]],
            history: List[List[List[float]]],
            bar: float,
    ) -> Optional[Tuple[Dict[str, Any], List[float], int]]:
        """``BallTracker._scan_motion_pair`` with the speed bar overridden.

        Byte-for-byte the production loop with ``self.lock_min_speed`` replaced
        by ``bar`` (``tests/test_serve_backfill.py`` pins the equality at
        ``bar == lock_min_speed`` so this copy cannot drift from the source).
        """
        for det in sorted(plausible, key=lambda d: d.get("confidence", 0.0),
                          reverse=True):
            c = det["center"]
            for age, frame_centers in enumerate(reversed(history), start=1):
                if age > self.lock_max_pair_gap:
                    break
                for old in frame_centers:
                    dist = float(np.hypot(c[0] - old[0], c[1] - old[1]))
                    if dist <= self.lock_max_jump:
                        speed = dist / age
                        if speed >= bar:
                            return det, old, age
        return None

    # -- mechanism B: backfill on a fresh lock -------------------------

    def _update(self, detections: List[Dict[str, Any]]
                ) -> Optional[Dict[str, Any]]:
        if self.backfill_lookback > 0:
            self._det_buffer.append((self._current_frame, list(detections)))
        return super()._update(detections)

    def _bootstrap_detection(self, det: Dict[str, Any], old: List[float],
                             gap: int) -> Dict[str, Any]:
        result = super()._bootstrap_detection(det, old, gap)
        # Purely ADDITIVE: the trajectory the locked path gates on is
        # untouched, so no tracking decision moves.
        if self.backfill_lookback > 0:
            self._backfill_out = self._chain_backfill(self._current_frame, det)
        return result

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
        plausible detection, or at ``backfill_lookback`` frames of age.
        Detections the detector removed as static (``persist >=
        ball_static_persist``) never reach the tracker, and
        ``backfill_skip_suspect`` additionally refuses the flagged ones.

        Causal by construction: only frames already seen are consulted.
        """
        lookback = int(self.backfill_lookback)
        if lookback <= 0:
            return []
        anchor = list(lock_det["center"])
        chain: List[Tuple[int, Dict[str, Any]]] = []
        misses = 0
        for frame, dets in reversed(list(self._det_buffer)):   # oldest first
            age = lock_frame - frame
            if age <= 0:
                continue                                    # the lock frame
            if age > lookback:
                break
            radius = self.backfill_radius + self.backfill_radius_growth * (age - 1)
            best = None
            for det in dets:
                if det.get("confidence", 0.0) < self.backfill_min_conf:
                    continue
                if self.backfill_skip_suspect and det.get("stationary_suspect"):
                    continue
                if not width_ok(det, self.backfill_max_width):
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
        for frame, det in reversed(chain):                   # oldest first
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


class ProbeClassifier(ActionClassifier):
    """``ActionClassifier`` + the contact probe's backfilled-sighting ingest.

    T5 mechanism B: when the ball tracker locks it can be several frames AFTER
    the contact, so the pre-contact history the contact probe needs was never
    emitted in real time. The tracker retro-extends it from the raw detections
    of frames it has already seen and hands it over here as
    ``(frame, x, y, w, h)``; the points are consumed exactly like real
    sightings (the frame stamps are what the geometry reads) and flagged in
    ``_backfill_frames`` for diagnostics.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._backfill_frames: set = set()

    def reset(self) -> None:
        super().reset()
        self._backfill_frames.clear()

    def add_ball_sightings(self, points: List[Dict[str, Any]]) -> None:
        """Insert PAST ball sightings (tracker backfill) into the history.

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
