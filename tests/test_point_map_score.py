"""PG1 -- pins for the point-map scorer (card PG1, open point 22 / 21.3).

What is pinned here is the card's GATES and its ANCHOR RULE, so a later re-run
of ``scripts/score_point_map.py`` cannot move the headline number, swap the
anchor for the predicted ``match_start_frame``, change the pairing, or flip
``FAIL=REFUTED`` into ``PASS`` by editing a threshold.

Kinds of pin:

* **mechanical** -- the scorer imports no ``cv2``, never opens a capture, seeks
  nothing, and imports ``probe_point_map``'s loaders/alignment helpers instead
  of re-implementing them (AGENTS.md sections 6 and 9);
* **anchor rule** -- on the REAL GT: exactly one ``serve`` contact per point and
  the serve is the earliest contact, for all 33 points; and the predicted
  ``match_start_frame`` is NOT the anchor;
* **literal** -- the numbers the run measured on the committed artifacts;
* **rule** -- the aggregates, the sign reading and the verdict truth table on
  synthetic offsets.

Every artifact number here is [measured] from
``output/20260920_match_ari_joan_lost/pipeline_output.json`` and
``ground_truth/20260920_match_contacts.json``.  The held-out session
``20260928_entreno_vall_dhebron`` is never read.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import probe_point_map as P  # noqa: E402
import score_point_map as G  # noqa: E402

SCORE_PATH = REPO / "scripts" / "score_point_map.py"


# ---------------------------------------------------------------------------
# mechanical pins: nothing decoded, nothing re-implemented
# ---------------------------------------------------------------------------

def test_scorer_imports_no_cv2():
    tree = ast.parse(SCORE_PATH.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "cv2" not in imported


def test_scorer_never_opens_a_capture_or_seeks():
    tree = ast.parse(SCORE_PATH.read_text())
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not (called & {"VideoCapture", "CAP_PROP_POS_FRAMES", "set",
                           "CAP_PROP_POS_MSEC", "grab", "retrieve"})


def test_loaders_and_alignment_come_from_probe_point_map():
    """Card "read first": import the loaders and the alignment logic."""
    source = SCORE_PATH.read_text()
    assert "import probe_point_map as P" in source
    for name in ("_read", "pipeline_points", "gt_serve_rows", "gt_point_frames",
                 "point_gap_table", "containing"):
        assert callable(getattr(P, name)), name


def test_tolerance_and_gate_thresholds_are_the_cards_fixed_values():
    assert G.TOLERANCE == 15
    assert G.PASS_START_HITS == 20
    assert G.PASS_OFFSETS_NONNEG == 31
    assert G.PM1_PROBE == "output/pm1/probe.json"
    assert (REPO / G.PM1_PROBE).exists()


# ---------------------------------------------------------------------------
# the anchor rule, on the real ground truth (card step 1)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def gt_blob():
    return P._read(G.MATCH_GT)


@pytest.fixture(scope="module")
def result():
    return G.score()


def test_anchor_rule_reproduces_on_the_real_gt(gt_blob):
    """[measured] all 33 points: exactly one serve, and the serve is earliest."""
    anchor = G.check_anchor_rule(gt_blob)
    assert anchor["pass"] is True
    assert anchor["exceptions"] == []
    assert anchor["points"] == 33
    for point in gt_blob["points"]:
        serves = G.serve_contacts(point)
        assert len(serves) == 1, point["point"]
        serve_frame = int(serves[0]["match_frame"])
        earliest = min(int(c["match_frame"]) for c in point["contacts"])
        assert serve_frame == earliest, point["point"]


def test_anchor_rule_rejects_a_broken_point():
    broken = {"points": [
        {"point": 1, "contacts": [
            {"match_frame": 100, "action_token": "serve"},
            {"match_frame": 300, "action_token": "dig"}]},          # ok
        {"point": 2, "contacts": [
            {"match_frame": 300, "action_token": "dig"},
            {"match_frame": 400, "action_token": "serve"}]},          # not earliest
        {"point": 3, "contacts": [{"match_frame": 500, "action_token": "dig"},
                                  {"match_frame": 520, "action_token": "dig"}]},  # no serve
    ]}
    anchor = G.check_anchor_rule(broken)
    assert anchor["pass"] is False
    assert {p["issue"] for p in anchor["exceptions"]} == {"serve_not_earliest",
                                                          "serve_count"}


def test_match_start_frame_is_not_the_anchor(gt_blob):
    """The card excludes it explicitly: all 33 are a pipeline prediction."""
    flagged = [(p["point"], p["match_start_frame"])
               for p in gt_blob["points"]
               if p.get("window_is_prediction") is True
               and p.get("window_source") == "episode_map_emission_window"]
    assert len(flagged) == 33
    serve_frames = {int(p["point"]): int(G.serve_contacts(p)[0]["match_frame"])
                    for p in gt_blob["points"]}
    # the prediction differs from the owner anchor on most points, so pinning
    # the anchor on the serve is not the same measurement
    differing = [n for n, f in flagged if f != serve_frames[n]]
    assert len(differing) >= 20
    # the scorer never READS that field (only the docstring names it)
    tree = ast.parse(SCORE_PATH.read_text())
    used = [n for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and n.value == "match_start_frame"]
    assert used == []


# ---------------------------------------------------------------------------
# the pairing is ordinal (card step 2 / G2)
# ---------------------------------------------------------------------------

def pt(start, end):
    return {"start_frame": start, "end_frame": end, "n_actions": 3}


def test_pairing_is_ordinal_gt_point_p_maps_to_pipeline_index_p_minus_1():
    points = [pt(1000, 1500), pt(2000, 2500), pt(3000, 3500)]
    serves = {1: 1100, 2: 2100, 3: 3100}
    pairs = G.ordinal_pairs(points, serves)
    assert [(p["gt_point"], p["index"], p["offset"]) for p in pairs] == [
        (1, 0, -100), (2, 1, -100), (3, 2, -100)]
    # it is NOT nearest-frame pairing: moving a window far away does not
    # re-target it, the offset just grows
    assert G.ordinal_pairs(points, {1: 10, 2: 2100, 3: 3100})[0]["offset"] == 990


def test_pairing_marks_the_tolerance_hit():
    points = [pt(1000, 1500), pt(2000, 2500)]
    pairs = G.ordinal_pairs(points, {1: 1000, 2: 2015})
    assert [p["start_hit"] for p in pairs] == [True, True]
    pairs = G.ordinal_pairs(points, {1: 984, 2: 2016})
    assert [p["start_hit"] for p in pairs] == [False, False]


# ---------------------------------------------------------------------------
# literal pins: the run on the committed artifacts
# ---------------------------------------------------------------------------

def test_anchor_and_counts(result):
    assert result["anchor"]["pass"] is True
    s = result["summary"]
    assert s["pipeline_points"] == 31
    assert s["gt_points"] == 33
    assert s["paired"] == 31
    assert s["gt_points_without_pipeline_point"] == [32, 33]
    assert s["unpaired_serve_frames"] == {"32": 25375, "33": 25807}


def test_offset_triple_and_sign(result):
    """[measured] one-signed late: +6 f tightest, +3153 f loosest, median 1700."""
    s = result["summary"]
    assert (s["offset_min"], s["offset_max"], s["offset_median"]) == (6, 3153, 1700)
    assert s["offsets_nonnegative"] == 31
    assert all(p["offset"] > 0 for p in result["pairs"])


def test_headline_start_hits_is_one_of_thirty_three(result):
    """[measured] the headline the card asked for -- far below the PASS bar."""
    assert result["summary"]["start_hits_within_15f"] == 1
    assert result["pairs"][0]["gt_point"] == 1
    assert result["pairs"][0]["offset"] == 6


def test_no_serve_falls_inside_its_own_ordinal_window(result):
    assert all(p["serve_inside_own_window"] is False for p in result["pairs"])


def test_gap_side_split_reproduces_the_64_claim(result):
    """[measured] far 2/17 in-window vs near 14/16; 16 of 33 serves in a gap."""
    g = result["gap_side"]
    assert g["total"]["inside_any_window"] == 16
    assert g["by_side"]["far"]["inside_any_window"] == 2
    assert g["by_side"]["far"]["n"] == 17
    assert g["by_side"]["near"]["inside_any_window"] == 14
    assert g["by_side"]["near"]["n"] == 16
    assert g["total"]["inside_any_gap"] == 16
    assert g["by_side"]["far"]["inside_any_gap"] == 14
    assert g["by_side"]["near"]["inside_any_gap"] == 2
    # the holder-specific gap (the card's wording) is a different, much
    # smaller set -- only P2 -- which is why both are reported
    assert g["total"]["inside_gap_before_holder"] == 1


def test_gate_g2_parity_with_the_pm1_probe(result):
    g2 = result["gate_g2"]
    assert g2["pass"] is True
    assert g2["mismatches"] == []
    assert g2["checks"] == {"paired_is_31": True,
                            "gt_points_without_pipeline_point": True,
                            "offsets_match_pm1": True}


def test_verdict_is_fail_refuted(result):
    assert result["verdict"]["verdict"] == "FAIL=REFUTED/1"
    assert result["reading"] == "uniformly late"


# ---------------------------------------------------------------------------
# the aggregates and the verdict rule, on synthetic offsets
# ---------------------------------------------------------------------------

def _pairs(offsets):
    return [{"gt_point": i + 1, "offset": o} for i, o in enumerate(offsets)]


def test_aggregate_computes_the_triple_and_both_counts():
    agg = G.aggregate(_pairs([6, 100, 3153]))
    assert (agg["offset_min"], agg["offset_max"], agg["offset_median"]) == (6, 3153, 100)
    assert agg["offsets_nonnegative"] == 3
    assert agg["start_hits_within_15f"] == 1
    assert agg["paired"] == 3


def test_aggregate_of_nothing_is_safe():
    agg = G.aggregate([])
    assert agg == {"paired": 0, "offset_min": None, "offset_max": None,
                   "offset_median": None, "offsets_nonnegative": 0,
                   "start_hits_within_15f": 0, "tolerance": 15}


def test_reading_of_the_offset_sign():
    assert G.reading([6, 100, 3153]) == "uniformly late"
    assert G.reading([-6, -100, -3153]) == "one point behind"
    assert G.reading([-6, 100]) == "noise"
    assert G.reading([]) == "noise"


def test_verdict_passes_only_with_20_hits_and_31_nonnegative():
    ok = G.verdict({"start_hits_within_15f": 20, "offsets_nonnegative": 31})
    assert ok["verdict"] == "PASS"


def test_verdict_fails_on_hits_short_of_twenty():
    assert G.verdict({"start_hits_within_15f": 19,
                      "offsets_nonnegative": 31})["verdict"] == "FAIL=REFUTED/19"


def test_verdict_fails_when_the_sign_is_not_uniform():
    assert G.verdict({"start_hits_within_15f": 33,
                      "offsets_nonnegative": 30})["verdict"] == "FAIL=REFUTED/33"


def test_verdict_never_passes_on_the_committed_aggregates(result):
    """The pinned run must not be able to satisfy its own PASS bar."""
    s = result["summary"]
    assert G.verdict(s)["verdict"] == "FAIL=REFUTED/1"