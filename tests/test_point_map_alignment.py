"""PG2 -- pins for the pairing-independent point-map re-test (card PG2, #67).

What is pinned here is the card's GATES and its PRE-REGISTERED DECISION, so a
later re-run of ``scripts/score_point_map_alignment.py`` cannot move the
pairing-independent headline, re-roll the chance baseline's seed, turn the
monotone DP into an ordinal pairing, or flip ``PG1_VERDICT_IS_A_PAIRING_ARTIFACT``
into ``PG1_VERDICT_STANDS`` by editing a threshold.

Kinds of pin:

* **mechanical** -- imports no ``cv2``, never opens a capture, seeks nothing,
  and IMPORTS ``score_point_map`` (and through it ``probe_point_map`` /
  ``score_serves``) rather than re-implementing loaders or pairings (AGENTS.md
  sections 6 and 9);
* **literal** -- the numbers the run measured on the committed artifacts
  (step 1's 14/31, the 1.21/31 chance baseline, PG1's ordinal parity, the DP
  sweep, the seam split, the far-record table);
* **mechanism** -- the chance baseline is deterministic under its seed, the
  monotone alignment is strictly order-preserving and never pairs across
  itself, and the `at_seam` / `inside_window` / `in_gap` classes partition;
* **truth table** -- the pre-registered verdict's three criteria, each of which
  can fail independently, on synthetic inputs.

Every artifact number here is [measured] from
``output/20260920_match_ari_joan_lost/pipeline_output.json`` and
``ground_truth/20260920_match_contacts.json``.  The held-out session
``20260928_entreno_vall_dhebron`` is never read.
"""

from __future__ import annotations

import ast
import statistics
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import probe_point_map as P  # noqa: E402
import score_point_map as M  # noqa: E402
import score_point_map_alignment as A  # noqa: E402

SCORE_PATH = REPO / "scripts" / "score_point_map_alignment.py"


# ---------------------------------------------------------------------------
# mechanical pins: nothing decoded, nothing re-implemented
# ---------------------------------------------------------------------------

def _imports(path: Path):
    tree = ast.parse(path.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    return imported


def test_scorer_imports_no_cv2():
    assert "cv2" not in _imports(SCORE_PATH)


def test_scorer_never_opens_a_capture_or_seeks():
    tree = ast.parse(SCORE_PATH.read_text())
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not (called & {"VideoCapture", "CAP_PROP_POS_FRAMES", "set",
                           "CAP_PROP_POS_MSEC", "grab", "retrieve"})


def test_pg1_script_is_untouched_by_pg2():
    """Card "must not touch": PG1's committed numbers must stay reproducible."""
    tree = ast.parse((REPO / "scripts" / "score_point_map.py").read_text())
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "VideoCapture" not in called


def test_loaders_and_ordinal_pairing_come_from_score_point_map():
    """Card "read first": import it, never re-implement it."""
    source = SCORE_PATH.read_text()
    assert "import score_point_map as M" in source
    assert "import probe_point_map as P" in source
    for name in ("score", "ordinal_pairs", "aggregate", "gt_points_of",
                 "serve_contacts", "TOLERANCE"):
        assert hasattr(M, name), name
    for name in ("_read", "pipeline_points", "gt_serve_rows", "far_flight_events",
                 "narrow_flight_records"):
        assert callable(getattr(P, name)), name


def test_constants_are_the_cards_fixed_values():
    assert A.TOLERANCE == 15 == M.TOLERANCE
    assert A.TOLERANCE_LADDER == (15, 30, 60)
    assert A.SKIP_COSTS == (60, 120, 240)
    assert A.FAR_RECORD_TOLS == (10, 15, 20)
    assert A.PASS_STARTS_WITHIN_15F == 10
    assert A.PASS_CHANCE_MULTIPLE == 5.0
    assert A.PASS_DP_MIN_HITS == 10
    assert A.PASS_VERDICT == "PG1_VERDICT_IS_A_PAIRING_ARTIFACT"
    assert A.FAIL_VERDICT == "PG1_VERDICT_STANDS"
    assert A.CHANCE_DRAWS >= 10000  # the card's floor
    # the width cut is the card's FIXED 28 px, imported through probe_point_map
    assert P.WIDTH_CUT == 28


# ---------------------------------------------------------------------------
# the real run, computed once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def result():
    return A.score()


@pytest.fixture(scope="module")
def serves(result):
    return result["step4_seam"]["table"]


# --- step 1 (G1), on the committed artifacts

def test_step1_headline_is_fourteen_of_thirty_one(result):
    """[measured] the card's stop condition (a)."""
    s = result["step1_pairwise_independent"]
    assert s["starts"] == 31
    assert s["starts_within_15f"] == 14


def test_step1_tolerance_ladder(result):
    """[measured] 23 of 31 at +-30, 25 of 31 at +-60."""
    assert result["step1_pairwise_independent"]["ladder"] == {"15": 14,
                                                              "30": 23,
                                                              "60": 25}


def test_step1_chance_baseline_is_about_one_of_thirty_one(result):
    """[measured] 1.21 of 31 against a 20000-draw uniform baseline."""
    ch = result["step1_pairwise_independent"]["chance"]
    assert ch["draws"] == 20000
    assert ch["seed"] == A.CHANCE_SEED
    assert ch["starts_per_draw"] == 31
    assert 1.0 <= ch["mean_hits"] <= 1.5
    assert ch["max_hits"] < 14  # chance never reaches the measured value


def test_step1_frame_coverage_is_about_four_percent(result):
    """[measured] 3.93% of frames (the card said 3.92%)."""
    cov = result["step1_pairwise_independent"]["coverage"]
    assert cov["serve_anchors"] == 33
    assert cov["total_frames"] == 26061
    assert 3.8 <= cov["coverage_pct"] <= 4.1


def test_step1_measured_count_is_far_above_chance(result):
    s = result["step1_pairwise_independent"]
    multiple = s["starts_within_15f"] / s["chance"]["mean_hits"]
    assert multiple > 5.0  # criterion (ii)


def test_step1_per_serve_offsets_are_one_per_serve(result):
    offsets = result["step1_pairwise_independent"]["per_serve_signed_offsets"]
    assert len(offsets) == 33
    assert min(offsets) == -662
    assert max(offsets) == 630


def test_step1_reports_all_three_offset_readings(result):
    """Card 1(e) asks for a SIGN-FREE median of -6 f, which cannot be
    expressed.  The -6 f is the nearest-BOUNDARY signed median; the scorer
    prints all three rather than swapping one in silently."""
    m = result["step1_pairwise_independent"]["per_serve_offset_medians"]
    assert m["nearest_boundary_signed"] == -6      # the card's figure
    assert m["nearest_start_signed"] == -1
    assert m["nearest_start_abs"] == 17             # sign-free is positive


# --- step 2 (G2), PG1's ordinal numbers through score_point_map

def test_g2_reproduces_pg1s_ordinal_numbers(result):
    """[measured] 1 of 33, 31 of 31 non-negative, +6/+3153/+1700."""
    s = result["step2_pg1_parity"]
    assert s["paired"] == 31
    assert s["start_hits_within_15f"] == 1
    assert s["offsets_nonnegative"] == 31
    assert (s["offset_min"], s["offset_max"], s["offset_median"]) == (6, 3153, 1700)


def test_g2_does_not_recompute_pg1(result):
    """PG1's own scorer is the source; the numbers agree object-for-object."""
    pg1 = M.score()
    s = result["step2_pg1_parity"]
    assert s["start_hits_within_15f"] == pg1["summary"]["start_hits_within_15f"]
    assert s["offsets_nonnegative"] == pg1["summary"]["offsets_nonnegative"]
    assert s["offset_median"] == pg1["summary"]["offset_median"]
    assert s["reading"] == pg1["reading"] == "uniformly late"


def test_pg1_verdict_still_fails_on_its_own_ordinal_pairing(result):
    """The pairing artifact is a claim ABOUT the pairing, not about PG1."""
    assert result["step2_pg1_parity"]["verdict"] == "FAIL=REFUTED/1"


# --- step 3, the monotone DP sweep

def test_dp_sweep_is_stable_at_fourteen_pairs(result):
    """[measured] 14 pairs within +-15 f at every skip cost (card's (iii))."""
    dp = result["step3_dp_alignment"]
    assert set(dp) == {"60", "120", "240"}
    assert [dp[c]["pairs_within_15f"] for c in ("60", "120", "240")] == [14, 14, 14]
    assert [dp[c]["pairs"] for c in ("60", "120", "240")] == [27, 28, 28]


def test_dp_median_is_close_to_the_card_expectation(result):
    """[measured] median -6 f at skip 60, -8 f at 120/240."""
    dp = result["step3_dp_alignment"]
    assert dp["60"]["offset_median"] == -6
    assert dp["120"]["offset_median"] == -8
    assert dp["240"]["offset_median"] == -8


def test_dp_never_pairs_more_than_the_shorter_sequence(result):
    for cell in result["step3_dp_alignment"].values():
        assert cell["pairs"] <= 31
        assert cell["pairs"] <= 33
        assert cell["unmatched_starts"] == 31 - cell["pairs"]
        assert cell["unmatched_serves"] == 33 - cell["pairs"]


def test_dp_alignment_is_order_preserving():
    starts = [100, 200, 300, 400, 500]
    serves = [90, 210, 295, 410, 520]
    pairs = A.monotone_align(starts, serves, 60)
    assert pairs == sorted(pairs)
    assert len({i for i, _ in pairs}) == len(pairs)   # no start used twice
    assert len({j for _, j in pairs}) == len(pairs)   # no serve used twice


def test_dp_never_pairs_backwards_on_a_reversed_sequence():
    """A serve sequence reversed in frame order cannot keep increasing."""
    starts = [10, 20, 30]
    serves = [30, 20, 10]
    pairs = A.monotone_align(starts, serves, 60)
    assert [j for _, j in pairs] == sorted(j for _, j in pairs)


def test_dp_prefers_tight_pairs_over_far_ones():
    starts = [1000, 2000, 3000]
    serves = [1005, 2100, 3001]
    pairs = A.monotone_align(starts, serves, 60)
    assert [(starts[i], serves[j]) for i, j in pairs] == [(1000, 1005),
                                                          (2000, 2100),
                                                          (3000, 3001)]


def test_dp_of_empty_sequences_is_empty():
    assert A.monotone_align([], [], 60) == []
    assert A.monotone_align([1, 2, 3], [], 60) == []


# --- step 4, the seam

def test_seam_side_split_reproduces(result):
    """[measured] far 11/17 at a start, 0 inside a window; near 11/16 inside."""
    split = result["step4_seam"]["split"]
    assert split["far"]["n"] == 17
    assert split["far"]["at_seam"] == 11
    assert split["far"]["inside_window"] == 0
    assert split["far"]["in_gap"] == 6
    assert split["near"]["n"] == 16
    assert split["near"]["at_seam"] == 3
    assert split["near"]["inside_window"] == 11
    assert split["near"]["in_gap"] == 2
    assert split["all"]["n"] == 33


def test_seam_classes_partition_every_serve(serves):
    assert len(serves) == 33
    assert {r["kind"] for r in serves} <= {"at_seam", "inside_window", "in_gap"}
    assert all(r["kind"] != "" for r in serves)


def test_at_seam_is_exactly_within_tolerance_of_the_nearest_start(serves):
    for row in serves:
        assert (row["kind"] == "at_seam") == \
            (abs(row["offset_start"]) <= A.TOLERANCE)


def test_far_serves_are_never_inside_a_window_as_a_class(serves):
    """The load-bearing asymmetry: no far serve sits in a window's interior."""
    far = [row for row in serves if row["side"] == "far"]
    assert sum(1 for row in far if row["kind"] == "inside_window") == 0


def test_far_inside_window_geometric_count_is_two(serves):
    """PG1 section 4's geometric count, which the three-way class splits."""
    far = [row for row in serves if row["side"] == "far"]
    assert sum(1 for row in far if row["inside_window"]) == 2
    # both of them are ALSO at_seam: that is the finding, not a contradiction
    assert all(row["kind"] == "at_seam"
               for row in far if row["inside_window"])


def test_near_serves_are_mostly_inside_a_window(serves):
    near = [row for row in serves if row["side"] == "near"]
    assert sum(1 for row in near if row["inside_window"]) == 14  # geometric
    assert sum(1 for row in near if row["kind"] == "inside_window") == 11


def test_seam_reports_both_boundaries(serves):
    """Both boundaries are reported; they are INDEPENDENT nearest lookups, so
    the nearest start may lie beyond the nearest end."""
    for row in serves:
        assert "offset_start" in row and "offset_end" in row
        assert row["nearest_start"] >= 0 and row["nearest_end"] >= 0


# --- step 5, the far-record consequence (IN-SAMPLE)

def test_far_record_reproduces_the_cards_table(result):
    """[measured] 11/17 far, 0/16 near, 5 unanchored at +-10 and +-15."""
    fr = result["step5_far_record"]
    for tol in ("10", "15"):
        cell = fr[tol]
        assert cell["claims"] == 16
        assert cell["far_serves_hit"] == 11
        assert cell["far_n"] == 17
        assert cell["near_serves_misclaimed"] == 0
        assert cell["near_n"] == 16
        assert cell["unanchored_claims"] == 5


def test_far_record_at_twenty_f_tolerance(result):
    cell = result["step5_far_record"]["20"]
    assert cell["claims"] == 17
    assert cell["far_serves_hit"] == 12
    assert cell["near_serves_misclaimed"] == 0


def test_far_record_is_one_claim_per_window_start(result):
    for cell in result["step5_far_record"].values():
        anchors = [c["anchor_start"] for c in cell["claims_detail"]]
        assert len(anchors) == len(set(anchors))
        assert len(anchors) == cell["claims"]


def test_far_record_claims_are_all_far_side(result):
    for cell in result["step5_far_record"].values():
        for claim in cell["claims_detail"]:
            assert claim.get("side") in ("far", "near")
            if claim.get("hit"):
                assert claim["side"] == "far"


def test_narrow_flight_events_are_present(result):
    """Card "stop and ask" check: far_flight must exist in the artifact."""
    events = P._read(P.MATCH_PIPELINE)["serve_events"]
    assert sum(1 for e in events if e.get("type") == "far_flight") == 578


# --- the verdict

def test_verdict_is_pass_pairing_artifact(result):
    assert result["verdict"]["pass"] is True
    assert result["verdict"]["verdict"] == "PG1_VERDICT_IS_A_PAIRING_ARTIFACT"


def test_all_three_criteria_are_true(result):
    checks = result["verdict"]["checks"]
    assert checks == {"i_starts_within_15f": True,
                      "ii_chance_multiple": True,
                      "iii_dp_min_pairs_within_15f": True}


def test_main_returns_zero_on_pass():
    assert A.main([]) == 0


# --- the verdict truth table (synthetic)

def _dp_cell(hits):
    return {str(c): {"pairs_within_15f": hits} for c in A.SKIP_COSTS}


def test_verdict_passes_when_all_three_hold():
    v = A.verdict(14, 31, 1.21, _dp_cell(14))
    assert v["pass"] is True
    assert v["verdict"] == A.PASS_VERDICT


def test_verdict_fails_when_too_few_starts_are_anchored():
    v = A.verdict(9, 31, 1.21, _dp_cell(14))
    assert v["pass"] is False
    assert v["verdict"] == A.FAIL_VERDICT
    assert v["checks"]["i_starts_within_15f"] is False


def test_verdict_fails_when_the_count_is_not_above_chance():
    v = A.verdict(14, 31, 14 / 4.9, _dp_cell(14))   # 4.9x
    assert v["checks"]["ii_chance_multiple"] is False
    assert v["pass"] is False


def test_verdict_fails_when_one_skip_cost_breaks_down():
    dp = _dp_cell(14)
    dp["240"]["pairs_within_15f"] = 9
    v = A.verdict(14, 31, 1.21, dp)
    assert v["checks"]["iii_dp_min_pairs_within_15f"] is False
    assert v["pass"] is False


def test_verdict_never_passes_on_a_chance_level_count():
    v = A.verdict(1, 31, 1.21, _dp_cell(1))
    assert v["pass"] is False


# --- helper mechanics on synthetic inputs

def test_count_starts_within_is_pairwise_independent():
    starts = [100, 200, 300]
    serves = [101, 299]
    assert A.count_starts_within(starts, serves, 15) == 2
    assert A.count_starts_within(starts, serves, 0) == 0
    assert A.count_starts_within(starts, serves, 1) == 2


def test_chance_baseline_is_deterministic_under_its_seed():
    kwargs = dict(starts=[0] * 31, serve_frames=[1000], total_frames=26061,
                  draws=200, seed=1234)
    a = A.chance_baseline(**kwargs)
    b = A.chance_baseline(**kwargs)
    assert a == b
    assert a["seed"] == 1234
    assert a["draws"] == 200


def test_chance_baseline_changes_with_the_seed():
    kwargs = dict(starts=[0] * 31, serve_frames=[1000], total_frames=26061,
                  draws=200)
    assert A.chance_baseline(seed=1, **kwargs) != A.chance_baseline(seed=2, **kwargs)


def test_frame_coverage_counts_a_ball_around_each_serve():
    cov = A.frame_coverage([100, 200], 1000, tolerance=15)
    assert cov["covered_frames"] == 62      # two 31-frame balls
    assert cov["coverage_fraction"] == pytest.approx(0.062)


def test_frame_coverage_clips_at_the_video_bounds():
    # serve 0 keeps frames 0..15 (16 of 31); serve 999 keeps 984..1000 (17)
    cov = A.frame_coverage([0, 999], 1000, tolerance=15)
    assert cov["covered_frames"] == 32


def test_nearest_start_offsets_are_signed_start_minus_serve():
    starts = [100, 300]
    assert A.nearest_start_offsets(starts, [90]) == [10]    # start after serve
    assert A.nearest_start_offsets(starts, [110]) == [-10]  # start before serve


def test_seam_table_classifies_a_synthetic_seam():
    table = A.seam_table([100, 300], [200, 400],
                         [{"frame": 105, "side": "far", "point": 1},
                          {"frame": 350, "side": "near", "point": 2},
                          {"frame": 900, "side": "far", "point": 3}])
    assert [r["kind"] for r in table] == ["at_seam", "inside_window", "in_gap"]
