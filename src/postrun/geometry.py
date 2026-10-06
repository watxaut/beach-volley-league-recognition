"""Metric reads for the post-run layer (pinhole model, long-axis camera).

Every threshold in ``src/postrun`` is stated in METRES and SECONDS so the same
rules hold on any video shot with the standing recording setup (AGENTS.md §7:
long axis, net facing the lens, tripod height changing per video). The only
per-video input is the 8-click court calibration:

* ``court_y`` -- position along the court's long axis in the calibration's
  world frame (0 = FAR baseline, 8 = net, 16 = NEAR baseline, the convention
  of ``CourtCalibration.compute_ground_homography``).
* Ball DEPTH comes from its pixel width (owner pinhole model, #77): a ball on
  a baseline measures ``D * baseline_px / 8`` px, and ``1 / width`` is linear
  in depth between the two baselines (and beyond them -- a server stands
  behind the line).
* Ball HEIGHT comes from the ground row at that depth: the ball hangs
  ``(v_ground - v_ball) / px_per_metre`` above the sand.

Depth from one width sample is coarse (a 2 px error is ~2 m at the far end);
callers fit it over a whole flight (see ``ball_flights``) and never read a
single frame as a side verdict.
"""

from __future__ import annotations

import json
import math
from typing import Any, Optional, Sequence, Tuple

import numpy as np

BALL_DIAMETER_M = 0.67 / math.pi
COURT_LENGTH_M = 16.0
COURT_WIDTH_M = 8.0
NET_Y_M = COURT_LENGTH_M / 2.0

SIDE_NEAR = "near"
SIDE_FAR = "far"

# How far off a court position may be, as (across, along) metres -- about one
# sigma, a best effort and never a guarantee. The lens sits ~1.5 m up, so the
# court's long axis is squeezed into few image rows and DEPTH is the weak axis
# of every read; a higher tripod shrinks the ground-plane numbers by itself.
#
# Ground reads (a ball on the sand): what a +-GROUND_READ_PX slip of the box's
# bottom point moves on the sand (blurred box edge + calibration clicks), never
# below the floor (a ball rolls / is caught a frame late).
GROUND_READ_PX = 4.0
GROUND_ERR_FLOOR_M = 0.3
# Ball reads (depth from its pixel width, fitted over a flight). Measured
# (20260920, 136 credited touches, ball position vs the toucher's feet): the
# width noise averages out over a flight (median 54+ samples) and what is left
# -- blur, arm reach, the fit's straight line -- is ~0.4 m across and ~0.7 m
# along; with these floors 68-80 % of touches fall within the error and
# 83-96 % within twice it. The feet are a noisy reference, not ground truth.
BALL_WIDTH_READ_PX = 1.5
BALL_ERR_FLOOR_M = (0.4, 0.7)


def other_side(side: Optional[str]) -> Optional[str]:
    if side == SIDE_NEAR:
        return SIDE_FAR
    if side == SIDE_FAR:
        return SIDE_NEAR
    return None


def _homography(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Exact 4-point homography (DLT) -- no cv2 dependency in the post-run layer."""
    rows = []
    for (x, y), (u, v) in zip(src, dst):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.asarray(rows, dtype=np.float64))
    return vt[-1].reshape(3, 3)


class CourtGeometry:
    """Calibration-derived metric model of one video's court view."""

    def __init__(
        self,
        court_corners: Sequence[Sequence[float]],
        net_top_points: Optional[Sequence[Sequence[float]]] = None,
    ) -> None:
        corners = np.asarray(court_corners, dtype=np.float64).reshape(4, 2)
        # Calibration order: far-left, far-right, near-right, near-left.
        self.corners = corners
        world = np.array(
            [[0, 0], [COURT_WIDTH_M, 0], [COURT_WIDTH_M, COURT_LENGTH_M],
             [0, COURT_LENGTH_M]], dtype=np.float64)
        H = _homography(corners, world)
        # A homography's overall sign is arbitrary: normalise so ON-court
        # pixels give w > 0, which makes ``w <= 0`` a true horizon test.
        centre = corners.mean(axis=0)
        if H[2, 0] * centre[0] + H[2, 1] * centre[1] + H[2, 2] < 0:
            H = -H
        self.H_i2w = H
        self.H_w2i = np.linalg.inv(H)
        self.far_px = float(abs(corners[1, 0] - corners[0, 0]))
        self.near_px = float(abs(corners[2, 0] - corners[3, 0]))
        if not self.near_px > self.far_px > 0:
            raise ValueError("calibration is not a long-axis view (near baseline "
                             "must project wider than the far baseline)")
        #: Ball px width on each baseline and at the net plane.
        self.ball_px_far = BALL_DIAMETER_M * self.far_px / COURT_WIDTH_M
        self.ball_px_near = BALL_DIAMETER_M * self.near_px / COURT_WIDTH_M
        self.ball_px_net = 2.0 / (1.0 / self.ball_px_far + 1.0 / self.ball_px_near)
        self.net_top_points = (
            np.asarray(net_top_points, dtype=np.float64).reshape(2, 2)
            if net_top_points is not None else None)

    # -- construction ---------------------------------------------------- #

    @classmethod
    def from_file(cls, path: str) -> "CourtGeometry":
        with open(path) as f:
            data = json.load(f)
        return cls(data["court_corners"], data.get("net_top_points"))

    @classmethod
    def from_calibration(cls, calibration: Any) -> "CourtGeometry":
        return cls(calibration.court_corners,
                   getattr(calibration, "net_top_points", None))

    # -- depth ----------------------------------------------------------- #

    def court_y_from_width(self, width_px):
        """Ball pixel width -> court_y (0 far baseline .. 16 near baseline).

        Vectorised; NaN in, NaN out. Values outside [0, 16] are real (a ball
        behind a baseline) and are not clipped.
        """
        w = np.asarray(width_px, dtype=np.float64)
        inv_far, inv_near = 1.0 / self.ball_px_far, 1.0 / self.ball_px_near
        with np.errstate(divide="ignore", invalid="ignore"):
            return COURT_LENGTH_M * (1.0 / w - inv_far) / (inv_near - inv_far)

    def width_at(self, court_y):
        """Expected ball pixel width at a court_y (vectorised)."""
        y = np.asarray(court_y, dtype=np.float64)
        inv_far, inv_near = 1.0 / self.ball_px_far, 1.0 / self.ball_px_near
        return 1.0 / (inv_far + (y / COURT_LENGTH_M) * (inv_near - inv_far))

    def px_per_metre(self, court_y):
        """Image scale of the fronto-parallel plane at a court_y."""
        return self.width_at(court_y) / BALL_DIAMETER_M

    @staticmethod
    def side_of(court_y: float) -> str:
        return SIDE_NEAR if court_y > NET_Y_M else SIDE_FAR

    # -- ground plane ---------------------------------------------------- #

    def world_to_image(self, wx: float, wy: float) -> Tuple[float, float]:
        p = self.H_w2i @ np.array([wx, wy, 1.0])
        return float(p[0] / p[2]), float(p[1] / p[2])

    def image_to_world(self, u: float, v: float) -> Optional[Tuple[float, float]]:
        p = self.H_i2w @ np.array([u, v, 1.0])
        if p[2] <= 1e-9:
            return None                      # at / above the horizon
        return float(p[0] / p[2]), float(p[1] / p[2])

    def ball_world(self, u: float, v: float, court_y: float
                   ) -> Tuple[float, float, float]:
        """(court_x, court_y, height) of a ball seen at pixel (u, v) whose
        depth is already known. Height is metres above the sand."""
        scale = float(self.px_per_metre(court_y))
        uc, vg = self.world_to_image(COURT_WIDTH_M / 2.0, court_y)
        return (COURT_WIDTH_M / 2.0 + (u - uc) / scale, court_y, (vg - v) / scale)

    def ground_read_error_m(self, u: float, v: float) -> Optional[Tuple[float, float]]:
        """(across, along) error of the ground-plane read at pixel (u, v).
        None when the slip reaches the horizon (no usable position)."""
        px = GROUND_READ_PX
        up, down = self.image_to_world(u, v - px), self.image_to_world(u, v + px)
        left, right = self.image_to_world(u - px, v), self.image_to_world(u + px, v)
        if up is None or down is None or left is None or right is None:
            return None
        return (math.hypot(abs(right[0] - left[0]) / 2.0, GROUND_ERR_FLOOR_M),
                math.hypot(abs(up[1] - down[1]) / 2.0, GROUND_ERR_FLOOR_M))

    def ball_read_error_m(self, u: float, v: float, court_y: float, samples: int
                          ) -> Tuple[float, float]:
        """(across, along) error of ``ball_world(u, v, court_y)`` when the
        depth was fitted over ``samples`` width reads."""
        w = float(self.width_at(court_y))
        dw = min(BALL_WIDTH_READ_PX * 2.0 / math.sqrt(max(samples, 1)), 0.5 * w)
        along = abs(float(self.court_y_from_width(w - dw))
                    - float(self.court_y_from_width(w + dw))) / 2.0
        across = abs(self.ball_world(u, v, court_y + along)[0]
                     - self.ball_world(u, v, court_y - along)[0]) / 2.0
        return (math.hypot(across, BALL_ERR_FLOOR_M[0]),
                math.hypot(along, BALL_ERR_FLOOR_M[1]))

    def net_top_height_m(self) -> Optional[float]:
        """Net-top height implied by the calibration clicks (sanity read:
        2.43 m men / 2.24 m women; a value far from that flags a bad click)."""
        if self.net_top_points is None:
            return None
        mid = self.net_top_points.mean(axis=0)
        return self.ball_world(float(mid[0]), float(mid[1]), NET_Y_M)[2]

    def net_top_v_at(self, u: float) -> Optional[float]:
        """Image row of the net tape at image column ``u``."""
        if self.net_top_points is None:
            return None
        (x0, y0), (x1, y1) = self.net_top_points
        if abs(x1 - x0) < 1e-6:
            return float((y0 + y1) / 2.0)
        return float(y0 + (u - x0) * (y1 - y0) / (x1 - x0))

    def foot_court_y(self, bbox: Sequence[float]) -> Optional[float]:
        """court_y of a standing player's feet (bbox bottom-centre)."""
        w = self.image_to_world((bbox[0] + bbox[2]) / 2.0, bbox[3])
        return None if w is None else w[1]

    def foot_world(self, bbox: Sequence[float]) -> Optional[Tuple[float, float]]:
        return self.image_to_world((bbox[0] + bbox[2]) / 2.0, bbox[3])
