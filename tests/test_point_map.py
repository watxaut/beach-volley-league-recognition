"""PM1 -- pins for the point-map probe (card PM1, open point 30).

What is pinned here is the card's DECISION, so a later re-run of
``scripts/probe_point_map.py`` cannot move a serve from inside a window to
outside one, or turn ``FAIL=blocked`` into ``PASS=bypass``, by editing a
threshold, a binding rule or an import.

Three kinds of pin:

* **mechanical** -- the probe imports no ``cv2``, opens no ``VideoCapture``,
  seeks nothing, and never redefines ``GAP_SERVE_MIN`` (AGENTS.md sections 6
  and 9: this card reads committed artifacts only);
* **literal** -- the counts the architect call (#63) states, re-measured on the
  committed artifacts: 31 pipeline points against 33 GT points, and 0 of the
  17 far serves inside their OWN point window;
* **rule** -- the three binding rules and the pre-registered verdict, on
  synthetic windows, so the decision logic is readable without the artifacts.

Every artifact number here is [measured] from
``output/20260920_match_ari_joan_lost/pipeline_output.json`` (commit 133d87c)
and ``ground_truth/20260920_match_contacts.json``.  The held-out session
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
import relabel_serves  # noqa: E402
import score_serves  # noqa: E402

PROBE_PATH = REPO / "scripts" / "probe_point_map.py"


# ---------------------------------------------------------------------------
# mechanical pins: nothing is decoded, nothing is re-tuned
# ---------------------------------------------------------------------------

def test_probe_imports_no_cv2():
    tree = ast.parse(PROBE_PATH.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "cv2" not in imported


def test_probe_never_opens_a_capture_or_seeks():
    """A seek would land on a keyframe on this VFR match (AGENTS.md section 9)."""
    tree = ast.parse(PROBE_PATH.read_text())
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not (called & {"VideoCapture", "CAP_PROP_POS_FRAMES", "set",
                           "CAP_PROP_POS_MSEC"})
    assert not (called & {"grab", "retrieve"})


def test_gap_serve_min_is_imported_not_redefined():
    assert P.GAP_SERVE_MIN is relabel_serves.GAP_SERVE_MIN
    tree = ast.parse(PROBE_PATH.read_text())
    offenders = [getattr(n, "lineno", "?") for n in tree.body
                 if isinstance(n, ast.Assign)
                 and "GAP_SERVE_MIN" in [t.id for t in n.targets
                                         if isinstance(t, ast.Name)]]
    assert offenders == []


def test_width_cut_is_the_cards_fixed_28():
    """The card fixes the far-side cut; the plateau is what makes it safe."""
    assert P.WIDTH_CUT == 28
    assert P.WIDTH_CUTS_SENSITIVITY == (26, 28, 30, 32)


def test_scorer_helpers_are_imported_with_their_own_names():
    """Card "read first": import ``match_split``/``serve_record_candidates``/
    ``classify_false_positives``, never re-implement them."""
    for name in ("match_split", "serve_record_candidates", "classify_false_positives",
                 "match_candidates", "serve_rows_from_contact_gt",
                 "contact_gt_events"):
        assert callable(getattr(score_serves, name)), name
    source = PROBE_PATH.read_text()
    assert "import score_serves as S" in source


# ---------------------------------------------------------------------------
# literal pins: the #63 counts, re-measured on the committed artifacts
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def probe():
    return P.run()


def test_g1_baseline_reproduced(probe):
    g1 = probe["gates"]["g1"]
    assert g1["observed"] == {"near": "8/16", "far": "0/17", "false_positives": 12}
    assert g1["pass"] is True


def test_point_count_is_31_against_33_gt_points(probe):
    counts = probe["counts"]
    assert counts["pipeline_points"] == 31
    assert counts["gt_points"] == 33
    assert counts["gt_serves"] == 33
    assert counts["far_n"] == 17 and counts["near_n"] == 16


def test_zero_of_the_seventeen_far_serves_inside_their_own_window(probe):
    """The #63 root cause, on the ordinal pairing (GT point P <-> pipeline
    point P-1): no far serve sits inside the window that is nominally its own."""
    summary = probe["alignment_summary"]
    assert summary["own_aligned_far_inside"] == 0
    assert summary["own_aligned_far_inside_points"] == []
    # and nothing at all does, near included
    assert summary["own_serve_inside_aligned_window"] == 0
    # GT P32/P33 have no pipeline point at all (the 31-vs-33 shortfall)
    assert summary["gt_points_without_pipeline_point"] == [32, 33]


def test_every_point_start_frame_sits_after_its_own_serve(probe):
    """The offset is one-signed: +6 f at the tightest, +3153 f at the loosest."""
    summary = probe["alignment_summary"]
    assert summary["offset_min"] == 6
    assert summary["offset_max"] == 3153
    assert all(a["offset"] > 0 for a in probe["alignment"] if a["offset"] is not None)


def test_far_serves_are_almost_never_inside_any_window(probe):
    """2 of 17 far serves (P23, P25) sit inside SOME window; 14 of 16 near do."""
    counts = probe["counts"]
    assert counts["far_inside_any"] == 2
    assert counts["near_inside_any"] == 14
    assert counts["serves_inside_any_window"] == 16


def test_width_plateau_edges(probe):
    """Far onsets measure 16-27 px, the three near onsets 39/50/48 px, so every
    cut in 26-32 claims 16 far and 0 near."""
    g2 = probe["gates"]["g2"]
    assert g2["pass"] is True
    assert g2["far_width_min"] == 16.0
    assert g2["far_width_max"] == 27.0
    assert g2["far_n"] == 17 and len(g2["far_widths_with_events"]) == 16
    assert g2["near_widths_with_events"] == [(12, [39.0]), (18, [50.0]), (24, [48.0])]
    for cut in (26, 28, 30, 32):
        assert g2["per_cut"][str(cut)] == {"far_claimed": 16, "near_misclaimed": 0}


def test_verdict_is_fail_blocked_on_the_committed_artifacts(probe):
    """[measured] no binding rule reaches 12/17 far hits with <= 3 false
    positives, and the unbound form carries 294 false serves, so SR4-FAR is
    BLOCKED on open point 22."""
    v = probe["verdict"]
    assert v["verdict"] == "FAIL=blocked"
    assert v["passing_rules"] == []
    assert v["per_rule"]["contain"]["far_hits"] == 10
    assert v["per_rule"]["first_after"]["far_hits"] == 16
    assert v["per_rule"]["gap"]["far_hits"] == 11
    assert probe["bypass"]["unbound"]["far_hits"] == 16
    assert probe["bypass"]["unbound"]["near_hits"] == 0
    assert probe["bypass"]["unbound"]["false_serves_narrow"] > 0


# ---------------------------------------------------------------------------
# the binding rules, on synthetic windows
# ---------------------------------------------------------------------------

def pt(start, end):
    return {"start_frame": start, "end_frame": end, "n_actions": 3}


POINTS = [pt(1000, 1500), pt(2000, 2500), pt(3000, 3500)]


def test_contain_binds_only_a_frame_inside_a_window():
    assert P.containing(POINTS, 1200) == 0
    assert P.containing(POINTS, 1700) is None


def test_first_after_binds_to_the_first_start_after_the_event():
    assert P.first_start_after(POINTS, 1200) == 1
    assert P.first_start_after(POINTS, 2999) == 2
    assert P.first_start_after(POINTS, 9999) is None


def test_gap_is_previous_end_to_this_start():
    assert P.gap_of(POINTS, 1) == (1500, 2000)
    assert P.gap_of(POINTS, 0) is None


def test_binding_rules_on_a_synthetic_record_set():
    """A serve before the first window, one inside it, one in the gap."""
    records = [{"frame": 600, "side": "far"}, {"frame": 1200, "side": "far"},
               {"frame": 1700, "side": "far"}]
    contain = P.bind_records(records, POINTS, "contain")
    assert [r["frame"] for r in contain] == [1200]
    assert contain[0]["point"] == 0
    after = P.bind_records(records, POINTS, "first_after")
    assert [(r["frame"], r["point"]) for r in after] == [(600, 0), (1200, 1), (1700, 1)]
    gap = P.bind_records(records, POINTS, "gap")
    assert [(r["frame"], r["point"]) for r in gap] == [(1700, 1)]
    with pytest.raises(ValueError):
        P.bind_records(records, POINTS, "fourth_rule")


def test_unbound_records_carry_no_point_number():
    """The unbound form is (frame, side) only: that IS the bypass under test."""
    events = [{"frame": 100, "width_start": 18.0, "type": "far_flight"},
              {"frame": 200, "width_start": 45.0, "type": "far_flight"}]
    records = P.narrow_flight_records(events, cut=28)
    assert [r["frame"] for r in records] == [100]
    assert records[0]["side"] == "far"
    assert records[0]["point"] is None


# ---------------------------------------------------------------------------
# the pre-registered verdict rule
# ---------------------------------------------------------------------------

def _cell(far_hits, fp, records=10, points=3):
    return {"records": records, "far_hits": far_hits, "near_hits": 0,
            "far_n": 17, "near_n": 16, "unmatched_records": records - far_hits,
            "false_serves_narrow": fp, "fp_kinds": {}, "points_covered": points}


def test_verdict_passes_only_with_15_unbound_and_a_clean_binding_rule():
    ok = P.verdict(_cell(15, 0), {"contain": _cell(12, 3)})
    assert ok["verdict"] == "PASS=bypass"
    assert ok["passing_rules"] == ["contain"]


def test_verdict_fails_on_a_single_binding_rule_far_hits_short():
    assert P.verdict(_cell(16, 0), {"contain": _cell(11, 0)})["verdict"] == "FAIL=blocked"


def test_verdict_fails_on_false_serves_in_the_unbound_form():
    assert P.verdict(_cell(16, 1), {"contain": _cell(12, 3)})["verdict"] == "FAIL=blocked"


def test_verdict_fails_when_a_binding_rule_over_produces():
    assert P.verdict(_cell(15, 0), {"gap": _cell(13, 4)})["verdict"] == "FAIL=blocked"


def test_verdict_fails_on_a_near_misclaim():
    unbound = _cell(15, 0)
    unbound["near_hits"] = 1
    assert P.verdict(unbound, {"contain": _cell(12, 3)})["verdict"] == "FAIL=blocked"


# ---------------------------------------------------------------------------
# FP accounting
# ---------------------------------------------------------------------------

def test_false_serve_count_is_the_two_rally_kinds_only():
    """Dead time is not a false SERVE; a mislabeled rally contact is."""
    gt_contacts = [{"frame": 1200, "action": "dig", "owner_side": "near"},
                   {"frame": 3200, "action": "serve", "owner_side": "far"}]
    records = [{"frame": 1200, "side": "far", "point": None},
               {"frame": 3220, "side": "far", "point": None},
               {"frame": 5000, "side": "far", "point": None}]
    gt_rows = [{"frame": 3200, "side": "far", "tolerance": 15}]
    cell = P.score_records(gt_rows, records, gt_contacts)
    assert cell["fp_kinds"] == {"rally_contact_mislabeled": 1,
                                "serve_outside_tolerance": 1,
                                "dead_time_handling": 1}
    assert cell["false_serves_narrow"] == 2
    assert cell["records"] == 3