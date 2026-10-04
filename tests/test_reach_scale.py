"""Pins for the reach-scale conversion helper and the verdict table structure.

Deliberately fixture-based: the px->metre conversion is pinned on SYNTHETIC
points against the IMPORTED ``CourtCalibration`` loader (no pipeline output is
pinned), and the verdict table is pinned on hand-built rows so the label logic
is testable without re-reading the diag dumps.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import probe_reach_scale as prs  # noqa: E402


# ----------------------------------------------------------------------
# the conversion helper, on a synthetic fixture pair

# A synthetic pair: a foot 100 px apart in image x at the same image row, where
# the across component is a known analytic quantity of the imported calibration.
@pytest.fixture
def foot_pair():
    cal = prs.calibration(1)
    foot_a = (960, 700)
    foot_b = (1060, 700)
    return cal, foot_a, foot_b


def test_across_scale_is_almost_row_constant(foot_pair):
    """Two feet 100 px apart on one row: same scale to within 1%.

    Not exactly equal -- a court row is not parallel to the image plane, so the
    scale drifts slightly across it. Measured drift over 100 px at y=700: 0.7%.
    """
    cal, foot_a, foot_b = foot_pair
    scale_a = prs.across_m_per_px(cal, foot_a)
    scale_b = prs.across_m_per_px(cal, foot_b)
    assert scale_a is not None and scale_b is not None
    assert scale_a == pytest.approx(scale_b, rel=0.01)


def test_across_scale_matches_the_finite_difference_it_wraps(foot_pair):
    """It is exactly |world(x+SHADOW) - world(x)| / SHADOW from the loader."""
    cal, foot_a, _ = foot_pair
    base = cal.image_to_world(foot_a)
    probe = cal.image_to_world((foot_a[0] + prs.SHADOW, foot_a[1]))
    expected = abs(probe[0] - base[0]) / prs.SHADOW
    assert prs.across_m_per_px(cal, foot_a) == pytest.approx(expected, rel=1e-12)


def test_across_scale_decreases_toward_the_camera(foot_pair):
    """Nearer the camera a ground metre spans MORE pixels: fewer m per px."""
    cal, _, _ = foot_pair
    far = prs.across_m_per_px(cal, (960, 520))
    near = prs.across_m_per_px(cal, (960, 900))
    assert far > near > 0


def test_along_component_differs_from_across(foot_pair):
    """The two components are not interchangeable: the depth one is the refuted one."""
    cal, foot_a, _ = foot_pair
    across = prs.across_m_per_px(cal, foot_a)
    along = prs.along_m_per_px(cal, foot_a)
    assert along > 3 * across


def test_px_to_metres_is_px_times_the_across_scale(foot_pair):
    """The helper is linear in px, with no hidden factor."""
    cal, foot_a, _ = foot_pair
    assert prs.px_to_metres(cal, 100.0, foot_a) == pytest.approx(
        100.0 * prs.across_m_per_px(cal, foot_a), rel=1e-12)
    assert prs.px_to_metres(cal, 200.0, foot_a) == pytest.approx(
        2 * prs.px_to_metres(cal, 100.0, foot_a), rel=1e-12)


def test_px_to_metres_of_zero_is_zero(foot_pair):
    cal, foot_a, _ = foot_pair
    assert prs.px_to_metres(cal, 0.0, foot_a) == 0.0


def test_foot_point_needs_a_bbox_not_a_point():
    """Guard the foot convention: ``foot_point`` is bbox-shaped (regression)."""
    cal = prs.calibration(1)
    with pytest.raises(IndexError):
        cal.foot_point([960, 700])
    assert cal.foot_point([950, 600, 970, 700]) == (960, 700)


# ----------------------------------------------------------------------
# corner order: the refit must be a no-op on the shipped calibration

def test_corner_order_reproduces_the_shipped_homography():
    """CORNER_WORLD is depth order, so no refit is applied (measured 0.0 diff)."""
    assert prs.corner_order_is_valid(prs.calibration(1)) is True
    assert prs.corner_order_is_valid(prs.calibration(7)) is True


# ----------------------------------------------------------------------
# point -> bbox distance, mirroring the gate


def test_point_to_bbox_distance_is_zero_inside():
    assert prs.point_to_bbox_distance([100, 200], [50, 150, 150, 250]) == 0.0


def test_point_to_bbox_distance_is_to_the_nearest_edge():
    bbox = [50, 150, 150, 250]
    assert prs.point_to_bbox_distance([200, 200], bbox) == pytest.approx(50.0)
    assert prs.point_to_bbox_distance([100, 100], bbox) == pytest.approx(50.0)
    # diagonal: nearest-edge distance, not centre distance
    assert prs.point_to_bbox_distance([180, 280], bbox) == pytest.approx(
        (30 ** 2 + 30 ** 2) ** 0.5)


# ----------------------------------------------------------------------
# Cliff's delta

def test_cliffs_delta_total_separation_and_ties():
    assert prs.cliffs_delta([3, 4], [1, 2]) == pytest.approx(1.0)
    assert prs.cliffs_delta([1, 2], [3, 4]) == pytest.approx(-1.0)
    assert prs.cliffs_delta([1, 2], [1, 2]) == 0.0


def test_cliffs_delta_ignores_none_and_empties_are_neutral():
    assert prs.cliffs_delta([3, None, 4], [1, 2]) == pytest.approx(1.0)
    assert prs.cliffs_delta([], [1, 2]) == 0.0
    assert prs.cliffs_delta([1, 2], []) == 0.0


# ----------------------------------------------------------------------
# verdict table structure and label logic, on synthetic rows


def _row(stage, side, px, metres):
    r = prs.ReachRow(clip=1, frame=0, stage=stage, reason=None, kind=None,
                      px=px, reach_px=140.0, track_id=1, player_id=1,
                      team_flag="B" if side == "far" else "A",
                      ball_point=[0.0, 0.0], bbox=[0, 0, 1, 1])
    r.metres = metres
    return r


def test_verdict_table_has_a_cell_for_every_column():
    rows = [_row("rejected", "far", 200.0, 2.0),
            _row("accepted", "near", 50.0, 0.5)]
    v = prs.build_verdict(rows)
    assert len(v.as_row()) == len(v.header()) == len(prs.VERDICT_COLUMNS)
    assert all(cell != "" for cell in v.as_row())


def test_verdict_is_scale_explained_when_the_far_range_fits_inside_the_near():
    rows = [_row("rejected", "far", 200.0, 0.6),
            _row("rejected", "far", 210.0, 0.7),
            _row("accepted", "near", 50.0, 0.5),
            _row("accepted", "near", 60.0, 0.9)]
    v = prs.build_verdict(rows)
    assert v.label == "SCALE-EXPLAINED"
    assert v.inside_near_range is True


def test_verdict_is_not_scale_explained_when_the_far_range_is_outside():
    rows = [_row("rejected", "far", 200.0, 2.0),
            _row("accepted", "near", 50.0, 0.5)]
    v = prs.build_verdict(rows)
    assert v.label == "NOT SCALE-EXPLAINED"
    assert v.inside_near_range is False


def test_verdict_is_not_answerable_without_both_arms():
    assert prs.build_verdict([_row("rejected", "far", 200.0, 2.0)]).label \
        == "NOT ANSWERABLE"
    assert prs.build_verdict([]).label == "NOT ANSWERABLE"


def test_verdict_rows_render_the_ranges_it_was_given():
    rows = [_row("rejected", "far", 200.0, 1.4), _row("rejected", "far", 300.0, 4.5),
            _row("accepted", "near", 50.0, 0.1), _row("accepted", "near", 90.0, 0.7)]
    cells = prs.build_verdict(rows).as_row()
    assert "1.4-4.5 m (n=2)" == cells[1]
    assert "0.1-0.7 m (n=2)" == cells[2]