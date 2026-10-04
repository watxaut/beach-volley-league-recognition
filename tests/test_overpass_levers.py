"""Pins for the overpass-lever probes (session #76, steps 2-4).

Three pure things are pinned here because the conclusions rest on them:

1. ``precision_budget`` -- the algebra that decides whether ANY overpass rule
   can clear 0.70. A sign error here would silently report "infeasible" for
   everything (which is what the first draft did).
2. ``crossing_test`` / ``side_sign`` -- the net-plane crossing instrument.
3. ``fisher_exact_2x2`` / ``cliffs_delta`` -- the statistics the separator
   ranking is expressed in.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import probe_overpass_budget as pb  # noqa: E402
import probe_overpass_netcross as pn  # noqa: E402
import probe_overpass_separator as ps  # noqa: E402


# ----------------------------------------------------------------------
# 1. the precision budget

def test_budget_needs_twelve_labels_on_the_bar_arm():
    b = pb.precision_budget(137, 84)
    assert b["labels_needed_for_bar"] == 12   # ceil(0.70*137) - 84 = 96 - 84


def test_budget_matches_the_measured_relabel():
    """The oracle arm's +13 on 137 must satisfy the budget at k=13.

    ``probe_label_ceilings`` measured 0.6131 -> 0.7080 for a rule that fires on
    exactly 13 matched contacts and all 13 are GT overpasses. If the algebra
    were wrong this would disagree.
    """
    b = pb.precision_budget(137, 84, n_gt_target=16)
    row = next(r for r in b["by_k"] if r["k_recovered"] == 13)
    assert row["max_fires"] == 14          # 2*13 - 12
    assert row["precision_floor"] == pytest.approx(13 / 14, abs=1e-4)
    assert row["feasible"] is True


@pytest.mark.parametrize("k", [0, 1, 2, 3, 4, 5, 6])
def test_budget_is_infeasible_below_half_the_requirement(k):
    """m >= k always, so any k with 2k - 12 < k cannot be reached."""
    b = pb.precision_budget(137, 84)
    row = next(r for r in b["by_k"] if r["k_recovered"] == k)
    assert row["max_fires"] < k
    assert row["feasible"] is False
    assert row["precision_floor"] is None


def test_budget_would_have_been_satisfied_by_the_mistaken_formula():
    """Regression guard for the first draft's algebra error.

    Using ``bar * n_matched`` (95.9) instead of the 12 labels actually needed
    makes every k infeasible, i.e. a probe that "proves" impossibility for the
    wrong reason. The two forms agree only when the base is already at the bar.
    """
    good = pb.precision_budget(137, 84, n_gt_target=16)
    bad_need = 0.70 * 137
    row = next(r for r in good["by_k"] if r["k_recovered"] == 16)
    assert row["max_fires"] > 0
    assert 2 * 16 - bad_need < 0      # what the wrong formula would report


def test_budget_tracks_a_higher_base():
    """A stronger arm needs fewer labels, so a smaller k suffices."""
    assert pb.precision_budget(137, 90)["labels_needed_for_bar"] == 6
    assert pb.precision_budget(137, 95)["labels_needed_for_bar"] == 1


# ----------------------------------------------------------------------
# 2. the net-plane crossing instrument

def test_side_sign_three_way():
    assert pn.side_sign(300.0, 400.0, 50.0) == -1     # above the net
    assert pn.side_sign(430.0, 400.0, 50.0) == 0      # inside the band
    assert pn.side_sign(460.0, 400.0, 50.0) == 1      # past the net


def test_crossing_detected_on_a_sign_change():
    centers = {f: (500.0, 300.0 if f <= 100 else 500.0)
               for f in range(100, 161)}
    t = pn.crossing_test(centers, 100, lambda x: 400.0, 50.0, post_span=60)
    assert t["crossed"] is True
    assert t["crossed_at_frame"] == 101
    assert t["start_sign"] == -1
    assert t["end_sign"] == 1


def test_no_crossing_when_the_ball_stays_put():
    centers = {f: (500.0, 300.0) for f in range(100, 161)}
    t = pn.crossing_test(centers, 100, lambda x: 400.0, 50.0, post_span=60)
    assert t["crossed"] is False
    assert t["crossed_at_frame"] is None


def test_undecided_when_the_ball_is_lost_too_soon():
    centers = {100: (500.0, 300.0), 101: (500.0, 300.0)}
    t = pn.crossing_test(centers, 100, lambda x: 400.0, 50.0, post_span=60)
    assert t["crossed"] is False
    assert t["decidable"] is False      # < MIN_POST_FRAMES


def test_deeper_threshold_suppresses_marginal_crosses():
    """The `deep` variant must be a strict subset of the shallow one.

    Otherwise the two reported variants are not comparable and the 0.25/0.50
    band comparison in the report is meaningless.
    """
    centers = {f: (500.0, 300.0 if f <= 100 else 460.0)
               for f in range(100, 161)}
    shallow = pn.crossing_test(centers, 100, lambda x: 400.0, 50.0, 60)
    deep = pn.crossing_test(centers, 100, lambda x: 400.0, 100.0, 60)
    assert shallow["crossed"] is True
    assert deep["crossed"] is False


# ----------------------------------------------------------------------
# 3. the statistics

def test_fisher_is_one_for_identical_columns():
    assert ps.fisher_exact_2x2(5, 5, 50, 50) == pytest.approx(1.0)


def test_fisher_is_small_for_a_clean_split():
    assert ps.fisher_exact_2x2(13, 0, 0, 100) < 1e-6


def test_fisher_is_symmetric():
    assert ps.fisher_exact_2x2(9, 2, 30, 60) == \
        pytest.approx(ps.fisher_exact_2x2(2, 9, 60, 30))


def test_cliffs_delta_extremes():
    assert ps.cliffs_delta([10, 11], [1, 2]) == 1.0
    assert ps.cliffs_delta([1, 2], [10, 11]) == -1.0
    assert ps.cliffs_delta([1], [1]) == 0.0


def test_cliff_magnitude_bands():
    assert ps.cliff_magnitude(1.0) == "LARGE"
    assert ps.cliff_magnitude(0.6) == "medium"
    assert ps.cliff_magnitude(0.3) == "small"
    assert ps.cliff_magnitude(0.01) == "negligible"


def test_cliffs_delta_2d_requires_both_coordinates():
    xs = [(5, 5), (6, 6)]
    ys = [(1, 1), (2, 2)]
    assert ps.cliffs_delta_2d(xs, ys) == 1.0
    # one coordinate reversed -> counts as neither, so the magnitude drops
    mixed = ps.cliffs_delta_2d([(5, 5)], [(1, 9)])
    assert mixed == 0.0
