"""Scale-aware + mirror-aware contact geometry, as a SUBCLASS of production.

Deliberately OUTSIDE ``src/``: this is an unvalidated mechanism (owner asked
"let's try scale-aware geometry"), and the repo rule is that a refuted or
unvalidated mechanism never lives in the production package -- same pattern as
``scripts/serve_mechanism_harness.py`` (T5 A/B).

WHY (docs/g4_far_serve_failure_mode.md).  The far serve dies because the four
contact tests cannot reach their thresholds at the far end:

    bounce   vertex must be the LOWEST point of +-7f, then rise >= 26 px both sides
    redirect horizontal sign flip >= 20 px on both sides
    drive    downward-speed cut <= -8 px/f, or lateral impulse >= 12 px/f
    serve    fed ascent |vin3| >= |vin6| + 10 px, only at a rally opening

At the far end the ball's image motion is DEPTH-dominated: it grows and
descends as it approaches the fixed long-axis camera, and the toss DECAYS like
gravity. Measured far vs near: 0 lowest vertices vs 0-4, 0 px of flip vs 38-65,
dvy +4/-1 vs -42, dvx 2 px vs 20-29, fed ascent +0..+4 px vs +13..+20.

Two independent hypotheses follow, and the probe separates them:

* **SCALE** -- every threshold is a near-half-scale px constant; expressing it
  as a multiple of the ball's own apparent width should recover the margin.
  Expected to help the *marginal* tests only (the serve branch's fed ascent).
* **MIRROR** -- a far-side serve is structurally MIRRORED: the ball is hit
  TOWARD the camera, so at the contact it sits at an image-space PEAK (y is
  minimal) and descends on both sides, the mirror of what `bounce` demands.
  No threshold change can help a test whose structural precondition never
  holds, so the mirrored shape is a separate mechanism.

Arms (all inert at their defaults; ``arm="px"`` calls ``super()`` and IS
production):

* ``px``            untouched production geometry (the fidelity baseline)
* ``scale``         thresholds as ``k * ball_width`` at the vertex
* ``mirror``        production + mirrored vertex tests (peak-and-drop, mirrored
                    drive impulse, mirrored serve branch)
* ``scale+mirror``  both
"""

from __future__ import annotations

import math
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.recognition.action_classifier import ActionClassifier  # noqa: E402

__all__ = ["ScaleAwareActionClassifier", "ARMS"]

ARMS = ("px", "scale", "mirror", "scale+mirror")


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class ScaleAwareActionClassifier(ActionClassifier):
    """``ActionClassifier`` with scale-aware and mirrored contact geometry.

    Scale units are the ball's own apparent width at the vertex (mean of the
    vertex and its +-3f real neighbours, clamped to the detection range where a
    bbox is trustworthy).  ``k_*`` are multiples of that width; ``None`` keeps
    the production px constant for that test.
    """

    def __init__(self, *args: Any,
                 arm: str = "px",
                 k_prominence: Optional[float] = None,
                 k_xrev: Optional[float] = None,
                 k_decel: Optional[float] = None,
                 k_ximpulse: Optional[float] = None,
                 k_rise_tol: Optional[float] = None,
                 k_serve_margin: Optional[float] = None,
                 width_min_px: float = 8.0,
                 width_max_px: float = 60.0,
                 mirror_min_speed_bw: Optional[float] = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        if arm not in ARMS:
            raise ValueError(f"unknown arm {arm!r}; expected one of {ARMS}")
        self.arm = arm
        self.scale = arm.startswith("scale")
        self.mirror = "mirror" in arm
        self.k_prominence = k_prominence
        self.k_xrev = k_xrev
        self.k_decel = k_decel
        self.k_ximpulse = k_ximpulse
        self.k_rise_tol = k_rise_tol
        self.k_serve_margin = k_serve_margin
        self.width_min_px = float(width_min_px)
        self.width_max_px = float(width_max_px)
        # A mirrored contact is only believable if the ball is genuinely in
        # flight afterwards; in ball widths per frame.
        self.mirror_min_speed_bw = mirror_min_speed_bw

    # -- scale ---------------------------------------------------------

    def _scale_at(self, c: int, points: Sequence[Tuple]) -> float:
        """Apparent ball width (px) at the vertex, clamped to the bbox range."""
        if not points:
            return self.width_min_px
        w = _mean([max(1.0, float(p[3])) for p in points])
        return max(self.width_min_px, min(self.width_max_px, w))

    def _thresholds(self, bw: float) -> Dict[str, float]:
        """Threshold set for this arm at this scale."""
        def k(value, production):
            if value is None:
                return production
            return float(value) * bw
        return {
            "prominence": k(self.k_prominence, self.MIN_PROMINENCE),
            "xrev": k(self.k_xrev, self.XREV_MIN),
            "decel": k(self.k_decel, self.DRIVE_DECEL),
            "ximpulse": k(self.k_ximpulse, self.DRIVE_XIMPULSE),
            "rise_tol": k(self.k_rise_tol, self.DRIVE_RISE_TOL),
            "serve_margin": k(self.k_serve_margin, self.SERVE_ACCEL_MARGIN_PX),
            "min_speed": k(self.k_decel, self.DRIVE_MIN_SPEED),
        }

    # -- the tests -----------------------------------------------------

    def _normal_contact_at(self, c: int):
        """Production tests (scaled when the arm asks) plus the mirrored ones."""
        if not self.scale:
            found = super()._normal_contact_at(c)
            if found is not None or not self.mirror:
                return found
            return self._mirrored_contact_at(c)

        vertex = self._point_at(c)
        if vertex is None:
            return None
        vx, vy = vertex[1], vertex[2]
        left = self._real_points(c - self.NEIGH, c - 1)
        right = self._real_points(c + 1, c + self.NEIGH)
        if len(left) < 2 or len(right) < 2:
            return None
        left3 = [p for p in left if p[0] >= c - 3]
        right3 = [p for p in right if p[0] <= c + 3]
        bw = self._scale_at(c, left3[-3:] + [vertex] + right3[:3])
        th = self._thresholds(bw)

        contact_point = [vx, vy]
        inc = (vx - left[0][1], vy - left[0][2])
        out = (right[-1][1] - vx, right[-1][2] - vy)

        # --- bounce (scale-aware rise) ---
        if all(p[2] <= vy for p in left + right):
            rise_l = vy - min(p[2] for p in left)
            rise_r = vy - min(p[2] for p in right)
            if rise_l >= th["prominence"] and rise_r >= th["prominence"]:
                return contact_point, "bounce", inc, out, c

        # --- redirect (scale-aware flip) ---
        if inc[0] * out[0] < 0 and abs(inc[0]) > th["xrev"] and abs(out[0]) > th["xrev"]:
            if len(right3) >= 2:
                out_local = self._mean_velocity([vertex] + right3)
                if inc[0] * out_local[0] <= 0:
                    return contact_point, "redirect", inc, out, c

        # --- drive + serve branch (scale-aware) ---
        if left3 and right3:
            vin = self._mean_velocity(left3 + [vertex])
            vout = self._mean_velocity([vertex] + right3)
            dvx = vout[0] - vin[0]
            dvy = vout[1] - vin[1]
            speed = max(math.hypot(*vin), math.hypot(*vout))
            stays_down = (right[-1][2] - vy) >= 0.0
            pops_up = vout[1] < -th["rise_tol"]
            if speed >= th["min_speed"] and stays_down and not pops_up:
                if dvy <= -th["decel"] or abs(dvx) >= th["ximpulse"]:
                    return contact_point, "drive", inc, out, c
            vin6 = None
            if any(p[0] >= c - 6 for p in left):
                vin6 = self._mean_velocity([p for p in left if p[0] >= c - 6] + [vertex])
            if (pops_up and speed >= th["min_speed"] and vin6 is not None
                    and abs(vin[1]) >= abs(vin6[1]) + th["serve_margin"]
                    and c - self._last_contact_frame > self.RALLY_RESET_GAP):
                return contact_point, "drive", inc, out, c

        if self.mirror:
            return self._mirrored_contact_at(c, scale=bw, th=th)
        return None

    def _mirrored_contact_at(self, c: int, scale: Optional[float] = None,
                             th: Optional[Dict[str, float]] = None):
        """The same three tests on the VERTICALLY FLIPPED trajectory.

        A far-side serve is the mirror of the shapes production looks for: the
        ball is struck toward the camera, so at the contact it is at an
        image-space PEAK (smallest y) and DESCENDS on both sides, while the
        production bounce wants a trough that rises.  Implemented by negating
        every y, so the production formulas are reused rather than re-derived.
        """
        vertex = self._point_at(c)
        if vertex is None:
            return None
        left = self._real_points(c - self.NEIGH, c - 1)
        right = self._real_points(c + 1, c + self.NEIGH)
        if len(left) < 2 or len(right) < 2:
            return None
        left3 = [p for p in left if p[0] >= c - 3]
        right3 = [p for p in right if p[0] <= c + 3]
        if scale is None:
            scale = self._scale_at(c, left3[-3:] + [vertex] + right3[:3])
        if th is None:
            th = self._thresholds(scale)
        vy = vertex[2]
        # Peak on the flipped axis == the real trajectory's SMALLEST y here.
        drop_l = min(p[2] for p in left) - vy
        drop_r = min(p[2] for p in right) - vy
        is_peak = all(p[2] >= vy for p in left + right)
        # A ball that merely lobs over the net also peaks: require the drop on
        # both sides AND a genuinely driven outcome.
        if is_peak and drop_l >= th["prominence"] and drop_r >= th["prominence"]:
            if self.mirror_min_speed_bw is None or self._driven_after(c, scale):
                inc = (vertex[1] - left[0][1], vy - left[0][2])
                out = (right[-1][1] - vertex[1], right[-1][2] - vy)
                return [vertex[1], vy], "far_flight", inc, out, c
        if left3 and right3:
            vin = self._mean_velocity(left3 + [vertex])
            vout = self._mean_velocity([vertex] + right3)
            speed = max(math.hypot(*vin), math.hypot(*vout))
            vin6 = None
            if any(p[0] >= c - 6 for p in left):
                vin6 = self._mean_velocity([p for p in left if p[0] >= c - 6] + [vertex])
            # Mirror of the serve branch: the toss DECAYS into the contact
            # (|vin3| < |vin6|) and the ball leaves DOWNWARD-FAST toward the
            # lens -- the float-serve signature the production branch rejects.
            decaying = vin6 is not None and abs(vin[1]) <= abs(vin6[1])
            drops_fast = vout[1] > th["rise_tol"]
            if (is_peak and speed >= th["min_speed"] and decaying and drops_fast
                    and c - self._last_contact_frame > self.RALLY_RESET_GAP):
                inc = (vertex[1] - left[0][1], vy - left[0][2])
                out = (right[-1][1] - vertex[1], right[-1][2] - vy)
                return [vertex[1], vy], "far_serve", inc, out, c
        return None

    def _driven_after(self, c: int, scale: float) -> bool:
        """Is the ball leaving the mirrored vertex fast (a served ball does)?"""
        if self.mirror_min_speed_bw is None:
            return True
        right3 = [p for p in self._real_points(c + 1, c + self.NEIGH) if p[0] <= c + 3]
        vertex = self._point_at(c)
        if vertex is None or not right3:
            return False
        vout = self._mean_velocity([vertex] + right3)
        return math.hypot(*vout) >= self.mirror_min_speed_bw * scale
