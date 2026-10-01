#!/usr/bin/env python3
"""Possession-signal harness (open point 9 enabler) -- PARKED, default OFF.

Diagnosed and REFUTED as a needle-mover (session 52, 2026-10-01): see
``docs/g3_possession_signal.md`` and ``scripts/probe_possession_signal.py``.
The mechanisms live HERE, never in ``src/`` (the T5/R1 rule: a refuted
mechanism must not carry a config surface / ctor signature / drift guard
forever).  The probe imports these subclasses to reproduce the A/B numbers.

Two default-off mechanisms, both causal and single-pass:

* :class:`WidthTrendClassifier` -- **ball-field arriving side**.  When the
  strict width regime abstains (the 26-35 px band, typically at the net), the
  DIRECTION the apparent width moves still names the arriving half: a ball
  growing toward the camera is coming to the near half.  Median split of
  ``ln(width)`` over the last ``width_trend_span`` real samples, committing
  only at ``|dln| >= width_trend_min_dln``.  Used by ``_attribution_target``
  after the strict width step.

* :class:`MotionTiebreakClassifier` -- **motion-history tie-break** (owner
  spec, open point 5: "with players together, attribute by the past and the
  ball field").  Candidates within ``motion_tie_margin_px`` of the closest are
  re-ranked by the cosine between their recent trajectory and the direction to
  the contact; a clear distance winner is untouched.

Measured on the 20260920 match (offline replay of the real methods on the
``match_bw03_diag.jsonl`` dump, 157 GT-side contacts): base **121/157**
(0.771) -> both-on **122/157** (0.777).  The trend fires 11x and is 11/11 on
the correct side, but mostly REDUNDANT (the base already resolved those
contacts); motion changes only same-team actor picks (0 team changes).  The
carry errors it was meant to fix mostly have NO ball signal at all (ball
lost), which no ball-field rule can fix.  Hence parked.

Reproduce::

    venv/bin/python scripts/probe_possession_signal.py
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.recognition.action_classifier import ActionClassifier

#: Strict width regime constants (mirror src/utils/config.py defaults).
WIDTH_FAR_PX = 26.0
WIDTH_NEAR_PX = 35.0


class WidthTrendClassifier(ActionClassifier):
    """ActionClassifier + the ball-field width-trend fallback.  OFF by default."""

    def __init__(self, *args: Any,
                 width_trend_enabled: bool = False,
                 width_trend_span: int = 15,
                 width_trend_min_dln: float = 0.20,
                 **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.width_trend_enabled = width_trend_enabled
        self.width_trend_span = width_trend_span
        self.width_trend_min_dln = width_trend_min_dln

    def width_side_trend(self, frame: int) -> Tuple[Optional[str], float]:
        """Court side implied by the ball's apparent-width TREND (see module)."""
        if not self.width_trend_enabled:
            return None, 0.0
        pts = [
            (p[0], p[3]) for p in self._ball_history
            if frame - self.width_trend_span <= p[0] <= frame - 1 and p[3] > 0
        ]
        if len(pts) < max(4, self.width_trend_span // 3):
            return None, 0.0
        n = len(pts)
        k = max(2, n // 3)
        first = float(np.median([np.log(w) for _, w in pts[:k]]))
        last = float(np.median([np.log(w) for _, w in pts[-k:]]))
        dln = last - first
        if abs(dln) < self.width_trend_min_dln:
            return None, dln
        return ("A" if dln > 0 else "B"), dln

    def _attribution_target(self, frame: int
                            ) -> Tuple[Optional[str], Dict[str, Any]]:
        # Strict width first (base); only if it abstains does the trend speak.
        if self.width_trend_enabled and self._width_side(frame)[0] is None:
            side, dln = self.width_side_trend(frame)
            if side is not None:
                return side, {
                    "ball_side": side, "side_votes": 0, "source": "width_trend",
                    "first_of_rally": False, "trend_dln": round(dln, 4),
                }
        return super()._attribution_target(frame)


class MotionTiebreakClassifier(ActionClassifier):
    """ActionClassifier + the motion-convergence tie-break.  OFF by default.

    ``_closest_player_at`` is a faithful copy of the base method with the
    tie-break inserted (harness-local per the T5/R1 convention: the parked
    mechanism never lives in ``src/``).
    """

    def __init__(self, *args: Any,
                 motion_tiebreak_enabled: bool = False,
                 motion_tie_margin_px: float = 60.0,
                 motion_lookback_f: int = 6,
                 motion_min_speed: float = 2.0,
                 **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.motion_tiebreak_enabled = motion_tiebreak_enabled
        self.motion_tie_margin_px = motion_tie_margin_px
        self.motion_lookback_f = motion_lookback_f
        self.motion_min_speed = motion_min_speed

    def motion_convergence(self, track_id: Optional[int], frame: int,
                           point: List[float], center: List[float]
                           ) -> Tuple[float, float]:
        """Cosine of the player's recent motion vs the direction to the contact."""
        hist = self._player_pose_history.get(track_id)
        if not hist:
            return 0.0, 0.0
        past = [h for h in hist
                if frame - self.motion_lookback_f <= h["frame"] <= frame
                and h.get("center") is not None]
        if len(past) < 2:
            return 0.0, 0.0
        past.sort(key=lambda h: h["frame"])
        first, last = past[0], past[-1]
        dt = float(last["frame"] - first["frame"])
        if dt <= 0:
            return 0.0, 0.0
        vx = (last["center"][0] - first["center"][0]) / dt
        vy = (last["center"][1] - first["center"][1]) / dt
        speed = float(np.hypot(vx, vy))
        if speed < self.motion_min_speed:
            return 0.0, speed
        fx, fy = point[0] - center[0], point[1] - center[1]
        fn = float(np.hypot(fx, fy))
        if fn < 1e-6:
            return 0.0, speed
        return float((vx * fx + vy * fy) / (speed * fn)), speed

    def _closest_player_at(
        self, frame: int, point: List[float], target_team: Optional[str] = None
    ) -> Optional[Tuple[Dict[str, Any], float, Optional[int]]]:
        # --- base candidate assembly + team filter (verbatim from HEAD) ---
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
                self.logger.debug(
                    "attribution: team filter (%s) matched no candidate at f%d",
                    target_team, frame,
                )

        ordered = sorted(snapshots, key=lambda s: s["center"][0])
        dists: Dict[Any, Tuple[float, float]] = {}
        for s in ordered:
            d = self._point_to_bbox_distance(point, s.get("bbox"), s["center"])
            c = s["center"]
            cd = float(np.hypot(c[0] - point[0], c[1] - point[1]))
            dists[s.get("track_id")] = (d, cd)
        best = min(ordered, key=lambda s: dists[s.get("track_id")])
        best_dist = dists[best.get("track_id")][0]

        # --- the parked tie-break ---
        if self.motion_tiebreak_enabled and len(ordered) > 1:
            near = [s for s in ordered
                    if dists[s.get("track_id")][0] <= best_dist + self.motion_tie_margin_px]
            if len(near) > 1:
                def _key(s: Dict[str, Any]) -> Tuple[float, float, float]:
                    conv, _sp = self.motion_convergence(
                        s.get("track_id"), frame, point, s["center"])
                    d, cd = dists[s.get("track_id")]
                    return (conv, -d, -cd)
                best = max(near, key=_key)
                best_dist = dists[best.get("track_id")][0]

        lr_index = ordered.index(best) + 1
        return best, best_dist, lr_index


class PossessionSignalClassifier(WidthTrendClassifier, MotionTiebreakClassifier):
    """Both parked mechanisms together (what the probe's "new" arm runs)."""

    def __init__(self, *args: Any,
                 width_trend_enabled: bool = False,
                 motion_tiebreak_enabled: bool = False,
                 **kwargs: Any) -> None:
        kwargs.pop("width_trend_enabled", None)
        kwargs.pop("motion_tiebreak_enabled", None)
        super().__init__(*args,
                         width_trend_enabled=width_trend_enabled,
                         motion_tiebreak_enabled=motion_tiebreak_enabled,
                         **kwargs)
