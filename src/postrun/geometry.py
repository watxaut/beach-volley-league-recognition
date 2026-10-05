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
