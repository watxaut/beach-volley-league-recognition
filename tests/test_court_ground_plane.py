"""Tests for the ground-plane geometry added in phase 1c (relative body-size
signature). These verify the image->world homography math directly, since real
match footage (side changes) is scarce."""
from __future__ import annotations

import pytest

from src.detection.court_calibration import CourtCalibration


def _calib(corners, frame=(720, 720)):
    """Build a calibration from 4 corners (far-L, far-R, near-R, near-L)."""
    c = CourtCalibration()
    fl, fr, nr, nl = corners
    # Midcourt ground line = halfway between the far and near edges.
    midcourt = [
        [(fl[0] + nl[0]) / 2, (fl[1] + nl[1]) / 2],
        [(fr[0] + nr[0]) / 2, (fr[1] + nr[1]) / 2],
    ]
    c.calibrate_from_points(list(corners), list(midcourt), frame)
    return c


def test_homography_maps_corners_to_world_rectangle():
    corners = [(100, 100), (500, 100), (500, 500), (100, 500)]  # axis-aligned
    c = _calib(corners)
    W = CourtCalibration.BEACH_COURT_WIDTH_M
    L = CourtCalibration.BEACH_COURT_LENGTH_M

    assert c.image_to_world((100, 100)) == pytest.approx((0.0, 0.0), abs=1e-3)
    assert c.image_to_world((500, 100)) == pytest.approx((W, 0.0), abs=1e-3)
    assert c.image_to_world((500, 500)) == pytest.approx((W, L), abs=1e-3)
    assert c.image_to_world((100, 500)) == pytest.approx((0.0, L), abs=1e-3)
    # Centre maps to the centre of the court.
    assert c.image_to_world((300, 300)) == pytest.approx((W / 2, L / 2), abs=1e-2)


def test_world_scale_and_body_size_positive():
    c = _calib([(100, 100), (500, 100), (500, 500), (100, 500)])
    scale = c.world_scale_at((300, 300))
    assert scale is not None and scale > 0
    size = c.world_body_size([280, 260, 320, 340])  # 40x80 px box at centre
    assert size is not None
    assert size["world_height"] > 0 and size["world_width"] > 0
    assert size["ratio"] == pytest.approx(size["world_height"] / size["world_width"])
    assert size["foot_world"] is not None


def test_perspective_compensated_far_edge_has_larger_metres_per_pixel():
    # Trapezoid: near edge wider in image than far edge (front-view perspective).
    corners = [(200, 100), (400, 100), (550, 500), (50, 500)]
    c = _calib(corners)
    # Corners still map to the world rectangle despite perspective.
    assert c.image_to_world((200, 100)) == pytest.approx((0.0, 0.0), abs=1e-2)
    assert c.image_to_world((50, 500)) == pytest.approx((0.0, CourtCalibration.BEACH_COURT_LENGTH_M), abs=1e-2)
    # A pixel covers MORE metres far away (objects look smaller) -> larger m/px.
    s_far = c.world_scale_at((300, 120))
    s_near = c.world_scale_at((300, 480))
    assert s_far > s_near > 0


def test_uncalibrated_returns_none():
    c = CourtCalibration()
    assert c.compute_ground_homography() is None
    assert c.image_to_world((10, 10)) is None
    assert c.world_scale_at((10, 10)) is None
    assert c.world_body_size([0, 0, 10, 20]) is None
