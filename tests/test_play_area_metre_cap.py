"""The play-area zone is capped in metres (#118): a px band alone is venue-coupled
(100 px past the far baseline is ~16 m of ground at a high camera, ~180 m behind
a low one)."""
from __future__ import annotations

import numpy as np

from src.detection.court_calibration import CourtCalibration
from src.utils.config import Config


def _calib(corners, frame=(1080, 1920)):
    c = CourtCalibration()
    fl, fr, nr, nl = corners
    mid = [[(fl[0] + nl[0]) / 2, (fl[1] + nl[1]) / 2], [(fr[0] + nr[0]) / 2, (fr[1] + nr[1]) / 2]]
    c.calibrate_from_points(list(corners), mid, frame)
    return c


HIGH = [(626, 338), (1299, 337), (1717, 830), (106, 856)]    # deep court (high camera)
LOW = [(626, 838), (1199, 837), (1717, 1030), (106, 1056)]   # shallow court (low camera)


def _mask(corners, margin_m):
    c = _calib(corners)
    c.set_play_area_margin(100, margin_m)
    return c._play_area_mask


def test_unset_cap_is_the_px_band_only():
    c = _calib(LOW)
    c.set_play_area_margin(100)
    assert c.play_area_margin_m is None
    px_rows = np.where(c._play_area_mask.any(1))[0].min()
    assert px_rows <= 838 - 95


def test_cap_leaves_a_high_camera_untouched():
    c = _calib(HIGH)
    c.set_play_area_margin(100)
    px = c._play_area_mask.copy()
    c.set_play_area_margin(100, Config.DEFAULT_CONFIG["player_play_area_margin_m"])
    assert np.array_equal(px, c._play_area_mask)


def test_cap_trims_the_band_behind_a_low_camera():
    capped_top = np.where(_mask(LOW, 20.0).any(1))[0].min()
    px_top = np.where(_mask(LOW, None).any(1))[0].min()
    assert capped_top > px_top + 30
    # a tighter cap keeps trimming
    assert np.where(_mask(LOW, 8.0).any(1))[0].min() > capped_top


def test_cap_never_adds_pixels():
    px = _mask(LOW, None)
    capped = _mask(LOW, 20.0)
    assert not np.any((capped > 0) & (px == 0))
