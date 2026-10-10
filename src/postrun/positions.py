"""Where a touch happened and where a ball came down (output only).

The maps on the web plot these positions. Nothing here decides a point, a
touch, a label or a winner: those layers keep their own depth read
(``BallEvent.court_y`` and the split bias in ``touches``), which is tuned as a
whole and scored by ``scripts/score_postrun.py``.

Two things separate a published position from that decision read (measured on
the 20260920 match, ``docs/postrun_reconstruction.md``):

* **The net is where it was clicked.** The four corner clicks alone put the
  net on their midline; the calibration's two net-ground clicks say where it
  stands (on the beach 0.05 m off that midline at one sideline, 1.3 m at the
  other). Depth is read against three anchors -- far baseline, net, near
  baseline -- and the ground plane is two homographies sharing the net line.
* **The ball's box is wider than the ball.** Blur and box padding add pixels,
  which reads as nearer the lens: next to nothing at the near baseline (a near
  serve sits on its server), about a metre at the net, more beyond it. The
  number belongs to the video and comes from the end switches: the same
  players play both halves, so one kind of touch sits at one distance from the
  net whichever half it is played from, and a single width offset has to close
  that gap for every kind at once. A video that cannot show it (no switch, too
  few touches, kinds that disagree) is left uncorrected and says so.

What stays out of reach: one pixel of ball width is ~0.6 m at the net from the
beach tripod, so a single position is good to +-0.6-0.8 m along the court.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from .geometry import (
    BALL_DIAMETER_M,
    BALL_ERR_FLOOR_M,
    BALL_WIDTH_READ_PX,
    COURT_WIDTH_M,
    GROUND_ERR_FLOOR_M,
    GROUND_READ_PX,
    NET_Y_M,
    SIDE_FAR,
    SIDE_NEAR,
    CourtGeometry,
    _homography,
)

NET_ANCHOR_CLICKS = "net_ground_clicks"
NET_ANCHOR_MIDLINE = "corner_midline"
#: Where along the court (0 = far baseline, 1 = near) a clicked net line may
#: stand and still be taken for the net.
NET_DEPTH_SHARE = (0.3, 0.7)

#: Kinds of touch whose distance from the net cannot depend on the half.
SYMMETRY_ACTIONS = ("spike", "overpass", "set", "dig")
#: A kind counts once it has this many touches on EACH half ...
MIN_TOUCHES_PER_HALF = 5
#: ... and the offset needs this many kinds to agree on it.
MIN_KINDS = 2
#: The offset is looked for within this share of the ball's width at the net
#: (boxes are a little loose, not a different size) ...
MAX_BIAS_SHARE = 0.12
#: ... and is kept only if it leaves every kind's near/far gap below this.
KIND_AGREEMENT_M = 0.6

REASON_NO_SWITCH = "no_side_switch"
REASON_TOO_FEW = "too_few_touches"
REASON_OUTSIDE_CAP = "outside_cap"
REASON_DISAGREE = "kinds_disagree"

_FAR_HALF = np.array([[0, 0], [COURT_WIDTH_M, 0], [COURT_WIDTH_M, NET_Y_M],
                      [0, NET_Y_M]], dtype=np.float64)
_NEAR_HALF = np.array([[0, NET_Y_M], [COURT_WIDTH_M, NET_Y_M],
                       [COURT_WIDTH_M, 2 * NET_Y_M], [0, 2 * NET_Y_M]],
                      dtype=np.float64)


def _onto_line(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Foot of ``p`` on the line through ``a`` and ``b``."""
    d = b - a
    return a + d * float(np.dot(p - a, d) / np.dot(d, d))


def _image_to_world(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Homography of one half, signed so that on-court pixels give w > 0."""
    H = _homography(src, dst)
    centre = src.mean(axis=0)
    if H[2, 0] * centre[0] + H[2, 1] * centre[1] + H[2, 2] < 0:
        H = -H
    return H


class CourtPositions:
    """Net-anchored court frame: far baseline 0, net 8, near baseline 16 m."""

    def __init__(self, geometry: CourtGeometry, width_bias_px: float = 0.0) -> None:
        self.geometry = geometry
        #: Pixels the ball's box is wider than the ball (``calibrate_width_bias``).
        self.width_bias_px = float(width_bias_px)
        self.inv_far = 1.0 / geometry.ball_px_far
        self.inv_near = 1.0 / geometry.ball_px_near
        left, right = self._midline_ends()
        self.net_anchor = NET_ANCHOR_MIDLINE
        self.ball_px_net = geometry.ball_px_net
        clicked = self._clicked_ends()
        if clicked is not None:
            width = BALL_DIAMETER_M * float(np.hypot(*(clicked[1] - clicked[0]))) / COURT_WIDTH_M
            # Depth of that line as a share of the court (1 / width is linear
            # in depth). A net stands about half way; a line near a baseline
            # is a slipped click, not a net.
            share = (self.inv_far - 1.0 / width) / (self.inv_far - self.inv_near)
            if NET_DEPTH_SHARE[0] <= share <= NET_DEPTH_SHARE[1]:
                left, right = clicked
                self.net_anchor = NET_ANCHOR_CLICKS
                self.ball_px_net = width
        self.inv_net = 1.0 / self.ball_px_net
        self.net_left, self.net_right = left, right
        c = geometry.corners
        self._far_i2w = _image_to_world(np.array([c[0], c[1], right, left]), _FAR_HALF)
        self._near_i2w = _image_to_world(np.array([left, right, c[2], c[3]]), _NEAR_HALF)
        self._far_w2i = np.linalg.inv(self._far_i2w)
        self._near_w2i = np.linalg.inv(self._near_i2w)
        # Which side of the net line the near half is on, in the image.
        self._near_sign = math.copysign(1.0, self._net_side(*c[3]))

    # -- the net line ------------------------------------------------------ #

    def _midline_ends(self) -> Tuple[np.ndarray, np.ndarray]:
        g = self.geometry
        return (np.array(g.world_to_image(0.0, NET_Y_M)),
                np.array(g.world_to_image(COURT_WIDTH_M, NET_Y_M)))

    def _clicked_ends(self) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """The two net-ground clicks, each moved onto its own sideline (a
        click lands a pixel or two off the tape)."""
        clicks = self.geometry.net_ground_points
        if clicks is None:
            return None
        c = self.geometry.corners
        a, b = sorted((clicks[0], clicks[1]), key=lambda p: p[0])
        return _onto_line(a, c[0], c[3]), _onto_line(b, c[1], c[2])

    def _net_side(self, u: float, v: float) -> float:
        d = self.net_right - self.net_left
        return float(d[0] * (v - self.net_left[1]) - d[1] * (u - self.net_left[0]))

    # -- ground plane ------------------------------------------------------ #

    def image_to_world(self, u: float, v: float) -> Optional[Tuple[float, float]]:
        near = self._net_side(u, v) * self._near_sign >= 0
        p = (self._near_i2w if near else self._far_i2w) @ np.array([u, v, 1.0])
        if p[2] <= 1e-9:
            return None                      # at / above the horizon
        return float(p[0] / p[2]), float(p[1] / p[2])

    def world_to_image(self, wx: float, wy: float) -> Tuple[float, float]:
        p = (self._near_w2i if wy >= NET_Y_M else self._far_w2i) @ np.array([wx, wy, 1.0])
        return float(p[0] / p[2]), float(p[1] / p[2])

    def ground_read_error_m(self, u: float, v: float) -> Optional[Tuple[float, float]]:
        """(across, along) error of ``image_to_world(u, v)`` -- the same read
        slip as ``CourtGeometry.ground_read_error_m``, in this frame."""
        px = GROUND_READ_PX
        up, down = self.image_to_world(u, v - px), self.image_to_world(u, v + px)
        left, right = self.image_to_world(u - px, v), self.image_to_world(u + px, v)
        if up is None or down is None or left is None or right is None:
            return None
        return (math.hypot(abs(right[0] - left[0]) / 2.0, GROUND_ERR_FLOOR_M),
                math.hypot(abs(up[1] - down[1]) / 2.0, GROUND_ERR_FLOOR_M))

    # -- depth from the ball's width ---------------------------------------- #

    def court_y_from_width(self, width_px: float, bias_px: Optional[float] = None) -> float:
        """Box width -> court_y. ``1 / width`` is linear in depth on each
        half; values past a baseline are real (a server stands behind it)."""
        w = float(width_px) - (self.width_bias_px if bias_px is None else bias_px)
        if not w > 0:
            return float("nan")
        inv = 1.0 / w
        if inv >= self.inv_net:
            return NET_Y_M * (inv - self.inv_far) / (self.inv_net - self.inv_far)
        return NET_Y_M + NET_Y_M * (inv - self.inv_net) / (self.inv_near - self.inv_net)

    def width_at(self, court_y: float) -> float:
        """The ball's own pixel width at a court_y (no box offset)."""
        if court_y < NET_Y_M:
            inv = self.inv_far + (court_y / NET_Y_M) * (self.inv_net - self.inv_far)
        else:
            inv = self.inv_net + (court_y / NET_Y_M - 1.0) * (self.inv_near - self.inv_net)
        # Past the lens (inv <= 0) there is no width: hold a huge one.
        return 1.0 / max(inv, self.inv_near / 4.0)

    def _ball_x(self, u: float, court_y: float) -> float:
        scale = self.width_at(court_y) / BALL_DIAMETER_M
        uc = self.world_to_image(COURT_WIDTH_M / 2.0, court_y)[0]
        return COURT_WIDTH_M / 2.0 + (u - uc) / scale

    def ball_position(self, u: float, width_px: float,
                      side: Optional[str] = None) -> Tuple[float, float, bool]:
        """(court_x, court_y, clamped) of a ball seen at column ``u`` with a
        box ``width_px`` wide. A touch is played on its own half (rally
        rule), so with ``side`` a read that lands across the net is held at
        the net and reported as clamped."""
        y = self.court_y_from_width(width_px)
        clamped = False
        if side == SIDE_NEAR and y < NET_Y_M or side == SIDE_FAR and y > NET_Y_M:
            y, clamped = NET_Y_M, True
        return self._ball_x(u, y), y, clamped

    def ball_read_error_m(self, u: float, width_px: float, samples: int
                          ) -> Tuple[float, float]:
        """(across, along) error of ``ball_position`` when the width was
        fitted over ``samples`` reads -- ``CourtGeometry.ball_read_error_m``
        in this frame."""
        y = self.court_y_from_width(width_px)
        w = float(width_px) - self.width_bias_px
        dw = min(BALL_WIDTH_READ_PX * 2.0 / math.sqrt(max(samples, 1)), 0.5 * w)
        along = abs(self.court_y_from_width(width_px - dw)
                    - self.court_y_from_width(width_px + dw)) / 2.0
        across = abs(self._ball_x(u, y + along) - self._ball_x(u, y - along)) / 2.0
        return (math.hypot(across, BALL_ERR_FLOOR_M[0]),
                math.hypot(along, BALL_ERR_FLOOR_M[1]))


# --------------------------------------------------------------------------- #
# the width offset, from the end switches
# --------------------------------------------------------------------------- #

@dataclass
class WidthSample:
    """One observed touch: its kind, its half and the fitted box width."""

    action: str
    side: str
    width_px: float


@dataclass
class PositionCalibration:
    net_anchor: str
    ball_px_net: float
    width_bias_px: float = 0.0
    applied: bool = False
    reason: Optional[str] = None             # why no offset was applied
    #: kind -> touches per half and the near-minus-far gap before / after.
    kinds: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    clamped_to_half: int = 0                 # positions held at the net

    def payload(self) -> Dict[str, Any]:
        return {
            "net_anchor": self.net_anchor,
            "ball_px_net": round(self.ball_px_net, 2),
            "width_bias_px": round(self.width_bias_px, 2) if self.applied else None,
            "width_bias_applied": self.applied,
            "width_bias_reason": self.reason,
            "kinds": self.kinds,
            "clamped_to_half": self.clamped_to_half,
        }


def _gaps(model: CourtPositions, kinds: Dict[str, Dict[str, List[float]]],
          bias_px: float) -> Dict[str, float]:
    """Median distance from the net, near half minus far half, per kind."""
    out = {}
    for kind, halves in kinds.items():
        near = [model.court_y_from_width(w, bias_px) - NET_Y_M for w in halves[SIDE_NEAR]]
        far = [NET_Y_M - model.court_y_from_width(w, bias_px) for w in halves[SIDE_FAR]]
        out[kind] = float(np.nanmedian(near) - np.nanmedian(far))
    return out


def calibrate_width_bias(model: CourtPositions, samples: Iterable[WidthSample],
                         switched: bool) -> PositionCalibration:
    """The box-width offset that makes every kind of touch sit at the same
    distance from the net on both halves, or a refusal with its reason."""
    cal = PositionCalibration(net_anchor=model.net_anchor, ball_px_net=model.ball_px_net)
    kinds: Dict[str, Dict[str, List[float]]] = {}
    for s in samples:
        if s.action in SYMMETRY_ACTIONS and s.side in (SIDE_NEAR, SIDE_FAR) \
                and np.isfinite(s.width_px):
            kinds.setdefault(s.action, {SIDE_NEAR: [], SIDE_FAR: []})[s.side].append(
                float(s.width_px))
    kinds = {k: h for k, h in kinds.items()
             if min(len(h[SIDE_NEAR]), len(h[SIDE_FAR])) >= MIN_TOUCHES_PER_HALF}
    before = _gaps(model, kinds, 0.0)
    cal.kinds = {k: {"near": len(h[SIDE_NEAR]), "far": len(h[SIDE_FAR]),
                     "gap_before_m": round(before[k], 2), "gap_after_m": None}
                 for k, h in kinds.items()}
    if not switched:
        cal.reason = REASON_NO_SWITCH
        return cal
    if len(kinds) < MIN_KINDS:
        cal.reason = REASON_TOO_FEW
        return cal
    weight = {k: min(len(h[SIDE_NEAR]), len(h[SIDE_FAR])) for k, h in kinds.items()}
    total = float(sum(weight.values()))

    def pooled(bias: float) -> float:
        gaps = _gaps(model, kinds, bias)
        return sum(weight[k] * gaps[k] for k in kinds) / total

    # A wider assumed box moves every read away from the lens: the near half
    # closes on the net, the far half leaves it, so the gap falls with it.
    lo, hi = -MAX_BIAS_SHARE * model.ball_px_net, MAX_BIAS_SHARE * model.ball_px_net
    if pooled(lo) <= 0 or pooled(hi) >= 0:
        cal.reason = REASON_OUTSIDE_CAP
        return cal
    for _ in range(40):
        mid = (lo + hi) / 2.0
        lo, hi = (mid, hi) if pooled(mid) > 0 else (lo, mid)
    bias = (lo + hi) / 2.0
    after = _gaps(model, kinds, bias)
    for k in kinds:
        cal.kinds[k]["gap_after_m"] = round(after[k], 2)
    if max(abs(g) for g in after.values()) > KIND_AGREEMENT_M:
        cal.reason = REASON_DISAGREE
        return cal
    cal.width_bias_px, cal.applied = bias, True
    return cal


# --------------------------------------------------------------------------- #
# positions of a reconstruction
# --------------------------------------------------------------------------- #

def _fitted_width(geometry: CourtGeometry, touch) -> Optional[float]:
    """The box width behind a touch's decision depth (its flight fits)."""
    if touch.court_y is None or touch.event is None or not np.isfinite(touch.event.u):
        return None
    return float(geometry.width_at(touch.court_y))


def publish_positions(timeline, points: Sequence, switched: bool) -> PositionCalibration:
    """Fill ``pos_x`` / ``pos_y`` / ``pos_err`` on every observed touch and
    ``pos_xy`` / ``pos_xy_err`` on every ground end. Reads the decision
    layers' results; changes none of them."""
    geometry = timeline.geometry
    widths = [(t, _fitted_width(geometry, t)) for pt in points for t in pt.touches]
    base = CourtPositions(geometry)
    cal = calibrate_width_bias(
        base, (WidthSample(t.action, t.side, w) for t, w in widths if w is not None),
        switched)
    model = CourtPositions(geometry, cal.width_bias_px) if cal.applied else base
    for t, w in widths:
        if w is None:
            continue
        x, y, clamped = model.ball_position(t.event.u, w, t.side)
        t.pos_x, t.pos_y = x, y
        t.pos_err = model.ball_read_error_m(t.event.u, w, t.event.depth_samples())
        cal.clamped_to_half += int(clamped)
    for pt in points:
        end = pt.rally.end
        if end is None or end.court_xy is None:
            continue
        f = timeline._nearest_tracked(end.frame)
        if f is None:
            continue
        b = timeline.stream.ball_bbox[f]
        u, v = (b[0] + b[2]) / 2.0, b[3]
        end.pos_xy = model.image_to_world(u, v)
        end.pos_xy_err = model.ground_read_error_m(u, v) if end.pos_xy else None
    return cal
