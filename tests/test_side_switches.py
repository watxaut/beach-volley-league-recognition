"""Tests for the pass-2 side-switch / squad layer (S3, open point 21.4).

Two layers, matching the other pass-2 test modules:

* pure-function tests over synthetic fixtures (the beach cadence, side->squad
  parity, point placement, action annotation, validation, the G1 metric
  correction, and the crossing evidence);
* artifact tests over the real 20260920 match that pin the session finding:
  the derived cadence `[7, 14, 21, 28]` reproduces the owner schedule, and the
  recorded G1 team number (0.518, side-vs-squad) corrects to 0.755 once the
  layer maps side letters to squads.  They skip when the artifacts are absent.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from resolve_side_switches import (  # noqa: E402
    annotate_actions,
    boundary_evidence,
    build_layer,
    build_point_map,
    contact_team_metric,
    crossing_support,
    derive_switches,
    evidence_summary,
    footprint_offsets,
    median_offsets_by_point,
    n_switches_before,
    near_squad,
    point_for_frame,
    point_windows,
    run,
    side_letter_to_court,
    side_to_squad,
    validate_switches,
)

MATCH_MAP = REPO / "output/episode_point_map.json"
MATCH_RELABEL = REPO / "output/serve_relabel.json"
MATCH_POINTS_GT = REPO / "ground_truth/20260920_match_points.json"
G1_ARTIFACT = REPO / "output/heldout_contacts/g1.json"


# --- cadence ---------------------------------------------------------------

def test_derive_switches_beach_cadence_33_points():
    assert derive_switches(range(1, 34), 7) == [7, 14, 21, 28]


def test_derive_switches_interval_and_order():
    assert derive_switches([3, 1, 14, 7, 21], 7) == [7, 14, 21]


def test_derive_switches_rejects_bad_interval():
    with pytest.raises(ValueError):
        derive_switches(range(1, 10), 0)


def test_n_switches_before_and_near_squad_parity():
    sw = [7, 14, 21, 28]
    assert n_switches_before(7, sw) == 0
    assert n_switches_before(8, sw) == 1
    assert near_squad(1, sw) == "A"
    assert near_squad(7, sw) == "A"
    assert near_squad(8, sw) == "B"     # first switch: A squad is now FAR
    assert near_squad(15, sw) == "A"    # second switch
    assert near_squad(29, sw) == "A"    # fourth switch: parity restored


def test_side_to_squad_matches_owner_parity_at_p9():
    # Owner GT P9 f5496: near side, squad B (a real annotated contact).
    assert side_to_squad("A", 9, [7, 14, 21, 28]) == "B"
    assert side_to_squad("B", 9, [7, 14, 21, 28]) == "A"
    assert side_to_squad("A", 1, [7, 14, 21, 28]) == "A"


def test_side_to_squad_handles_missing_side():
    assert side_to_squad(None, 1, []) is None
    assert side_to_squad("?", 1, []) is None


def test_side_letter_to_court():
    assert side_letter_to_court("A") == "near"
    assert side_letter_to_court("B") == "far"
    assert side_letter_to_court(None) is None


# --- point placement -------------------------------------------------------

def test_point_windows_sorted_and_skips_missing():
    blob = {"points": [
        {"point": 2, "window_frames": [200, 300]},
        {"point": 1, "window_frames": [0, 100]},
        {"point": 3, "window_frames": None},
    ]}
    assert point_windows(blob) == [(1, [0, 100]), (2, [200, 300])]


def test_point_for_frame_inside_and_nearest():
    wins = [(1, [0, 100]), (2, [200, 300])]
    assert point_for_frame(50, wins) == 1
    assert point_for_frame(90, wins) == 1
    assert point_for_frame(150, wins) == 2   # nearest window (gap)
    assert point_for_frame(999, wins) == 2
    assert point_for_frame(5, []) is None


# --- layer construction ----------------------------------------------------

def test_build_point_map_maps_both_sides():
    pm = build_point_map([1, 8], [7])
    assert pm[0] == {"point": 1, "near_squad": "A",
                     "side_to_squad": {"A": "A", "B": "B"}}
    assert pm[1] == {"point": 8, "near_squad": "B",
                     "side_to_squad": {"A": "B", "B": "A"}}


def _action(frame, team="A", pass2_team=None):
    a = {"frame_number": frame, "team": team, "action": "dig"}
    if pass2_team is not None:
        a["pass2_team"] = pass2_team
    return a


def test_annotate_actions_prefers_pass2_team_and_sets_squad():
    wins = [(1, [0, 100]), (8, [700, 800])]
    sw = [7]
    out = annotate_actions([_action(10, "A"), _action(710, "A", "B")], wins, sw)
    assert out[0]["pass2_point"] == 1
    assert out[0]["pass2_squad"] == "A"
    assert out[1]["pass2_point"] == 8
    assert out[1]["pass2_squad"] == "A"   # pass2_team B = far -> squad A at P8


def test_annotate_actions_uses_nearest_window_for_drifted_action():
    wins = [(1, [0, 100]), (2, [200, 300])]
    out = annotate_actions([_action(160)], wins, [])
    assert out[0]["pass2_point"] == 2


def test_build_layer_shape():
    mblob = {"video": "m.mp4", "points": [
        {"point": 1, "window_frames": [0, 100]},
        {"point": 8, "window_frames": [700, 800]}]}
    layer = build_layer(mblob, [_action(10), _action(710)], [7])
    assert layer["video"] == "m.mp4"
    assert layer["switches"] == [7]
    assert [p["point"] for p in layer["points"]] == [1, 8]
    assert layer["actions_pass2"][1]["pass2_squad"] == "B"


# --- validation ------------------------------------------------------------

def test_validate_switches_exact_and_diffs():
    assert validate_switches([7, 14, 21, 28], [7, 14, 21, 28])["exact_match"]
    v = validate_switches([7, 14], [7, 14, 21, 28])
    assert not v["exact_match"]
    assert v["missing"] == [21, 28] and v["extra"] == []


# --- G1 metric correction --------------------------------------------------

def _g1row(point, pred, gt_team, gt_side, frame=0, action="dig", matched=True):
    return {"matched": matched, "gt_point": point, "pred_team": pred,
            "gt_team": gt_team, "gt_side": gt_side, "gt_frame": frame,
            "gt_action": action, "label_ok": True}


def test_contact_team_metric_separates_side_from_squad():
    sw = [7]
    rows = [
        _g1row(1, "A", "A", "near"),    # raw ok, mapped ok, side ok
        _g1row(8, "A", "B", "near"),    # raw mismatch, mapped ok (side correct)
        _g1row(8, "B", "A", "far"),     # raw mismatch, mapped ok (side correct)
        _g1row(8, "B", "B", "near"),    # raw ok BY COINCIDENCE, mapped/side wrong
        _g1row(8, "A", "A", "far", matched=False),  # unmatched -> ignored
    ]
    m = contact_team_metric(rows, sw)
    assert m["n_found"] == 4
    assert (m["raw_correct"], m["squad_correct"], m["side_correct"]) == (2, 3, 3)
    assert m["raw_accuracy"] == pytest.approx(0.5)
    assert m["squad_accuracy"] == pytest.approx(0.75)
    assert len(m["residual_team_errors"]) == 1
    assert m["residual_team_errors"][0]["point"] == 8


def test_contact_team_metric_empty():
    m = contact_team_metric([], [7])
    assert m["n_found"] == 0 and m["raw_accuracy"] is None


# --- crossing evidence -----------------------------------------------------

def test_crossing_support_full_flip_and_deadband():
    before = {1: 90.0, 2: -60.0, 3: 90.0, 4: -60.0, 5: 5.0}
    after = {1: -70.0, 2: 80.0, 3: -65.0, 4: 90.0, 5: 3.0}
    ev = crossing_support(before, after, deadband=20)
    assert ev["n_confident"] == 4       # track 5 is inside the deadband
    assert ev["n_flipped"] == 4
    assert ev["support"] == 1.0


def test_crossing_support_no_confidence():
    ev = crossing_support({1: 5.0}, {1: -5.0}, deadband=20)
    assert ev["n_confident"] == 0 and ev["support"] is None


def test_boundary_evidence_marks_cadence_switch():
    medians = {1: {1: 90.0}, 2: {1: -90.0}, 3: {1: -90.0}}
    rows = boundary_evidence(medians, [1, 2, 3], switches=[1], deadband=20)
    assert rows[0]["cadence_says_switch"] is True
    assert rows[0]["n_flipped"] == 1
    assert rows[1]["cadence_says_switch"] is False


def test_evidence_summary_counts_support():
    rows = [
        {"cadence_says_switch": True, "n_flipped": 2},
        {"cadence_says_switch": True, "n_flipped": 0},
        {"cadence_says_switch": False, "n_flipped": 1},
    ]
    s = evidence_summary(rows)
    assert s["switch_boundaries_with_support"] == 1
    assert s["non_switch_boundaries_with_support"] == 1


def test_footprint_offsets_uses_foot_point_and_skips_meta():
    cal = {"midcourt_points": [[0, 100], [100, 100]]}
    diag = [
        {"meta": {}},
        {"frame": 5, "players": [
            {"track_id": 1, "bbox": [0, 0, 10, 90]},   # foot y=90 < 100 -> far
            {"track_id": 2, "bbox": [0, 0, 10, 130]},  # foot y=130 -> near
        ]},
    ]
    off = footprint_offsets(diag, cal)
    assert off[1] == [(5, -10.0)]
    assert off[2] == [(5, 30.0)]


def test_median_offsets_by_point():
    off = {1: [(10, 90.0), (11, 70.0), (12, -5.0)]}
    med = median_offsets_by_point(off, [1], {1: [10, 12]})
    assert med[1][1] == pytest.approx(70.0)


# --- end to end (synthetic files) ------------------------------------------

def test_run_writes_layer(tmp_path):
    mblob = {"video": "m.mp4", "points": [
        {"point": p, "window_frames": [p * 100, p * 100 + 90]}
        for p in range(1, 9)]}
    relblob = {"actions_pass2": [
        {"frame_number": 10, "team": "A", "pass2_team": "B"},
        {"frame_number": 810, "team": "A", "pass2_team": "A"}]}
    map_p = tmp_path / "map.json"
    rel_p = tmp_path / "rel.json"
    out_p = tmp_path / "out.json"
    map_p.write_text(json.dumps(mblob))
    rel_p.write_text(json.dumps(relblob))
    layer = run(str(map_p), str(rel_p), str(out_p), interval=7)
    assert layer["switches"] == [7]
    written = json.loads(out_p.read_text())
    assert written["actions_pass2"][0]["pass2_squad"] == "B"  # P1, near squad A
    assert written["actions_pass2"][1]["pass2_squad"] == "B"  # P8, side A is far


# --- real artifacts (skip when absent) -------------------------------------

@pytest.mark.skipif(not MATCH_POINTS_GT.exists() or not MATCH_MAP.exists(),
                    reason="20260920 artifacts absent")
def test_real_cadence_reproduces_owner_schedule():
    gt = json.loads(MATCH_POINTS_GT.read_text())
    mblob = json.loads(MATCH_MAP.read_text())
    points = [p["point"] for p in mblob["points"]]
    assert derive_switches(points, 7) == gt["side_switch_after_point"]


@pytest.mark.skipif(not G1_ARTIFACT.exists(), reason="G1 artifact absent")
def test_real_g1_team_metric_correction():
    g1 = json.loads(G1_ARTIFACT.read_text())
    rows = g1["perception_contact_rows"]
    # the pin: recorded raw team is a side-vs-squad confound
    assert len(rows) == 183
    from score_heldout_contacts import miss_taxonomy
    tax = miss_taxonomy(rows)
    assert tax["status_counts"]["wrong_team"] == 36
    m = contact_team_metric(rows, [7, 14, 21, 28])
    assert m["n_found"] == 139
    # raw reproduces the G1 headline (0.518), mapped corrects to 0.755
    assert m["raw_correct"] == 72
    assert m["squad_correct"] == 105
    assert m["side_correct"] == 105
    assert m["squad_accuracy"] == pytest.approx(0.7554, abs=1e-4)
    assert len(m["residual_team_errors"]) == 34
