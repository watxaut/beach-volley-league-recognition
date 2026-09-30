"""Tests for the S0b pass-2 contact-level scorer (scripts/score_pass2_contacts.py).

Two layers:

* pure-function tests over synthetic fixtures (scope padding, arm
  construction, serve-nearest table, far-serve tally, parity gate);
* artifact tests over the real 20260920 outputs, which pin the MEASURED
  findings of session 45: the perception arm reproduces the T4 dev-clip
  baseline, the pass-2 far-serve contact score is 0/5, and pass-2 breaks
  three correct dig labels.  They skip when the artifacts are absent.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from score_pass2_contacts import (  # noqa: E402
    ARMS,
    DEFAULT_GT,
    DEFAULT_RELABEL,
    FAR_SERVE_GT_FRAMES,
    T4_BASELINE,
    arm_delta,
    arm_events,
    far_serve_score,
    gt_contacts,
    gt_point_windows,
    in_region,
    parity,
    per_contact_rows,
    prediction_blob,
    region,
    run,
    scoped_actions,
    serve_rows,
)

RELABEL_FILE = REPO / DEFAULT_RELABEL
GT_FILE = REPO / DEFAULT_GT


def act(frame, action="dig", team="A", **kw):
    a = {"frame_number": frame, "action": action, "team": team,
         "player_id": 1, "touch_number": 1}
    a.update(kw)
    return a


def gt_blob(windows, contacts, fps=30.0):
    return {
        "fps": fps,
        "points": [{"point": i + 1, "match_start_frame": s,
                    "match_end_frame": e} for i, (s, e) in enumerate(windows)],
        "annotated_frames": {"actions": {"events": contacts}},
    }


def contact(frame, action="serve", side="far", team="B"):
    return {"frame": frame, "match_frame": frame, "action": action,
            "final_action": action, "player_team": team, "owner_side": side,
            "frame_tolerance": 15}


# --- scope -----------------------------------------------------------------

def test_region_pads_the_window_span():
    assert region([(216, 495), (4520, 4820)], pad=90) == (126, 4910)


def test_region_needs_windows():
    with pytest.raises(ValueError):
        region([], pad=90)


def test_gt_point_windows_prefers_match_axis_and_limits_count():
    blob = {"points": [
        {"match_start_frame": 10, "match_end_frame": 20, "clip_start_frame": 1,
         "clip_end_frame": 11},
        {"match_start_frame": 30, "match_end_frame": 40},
    ]}
    assert gt_point_windows(blob) == [(10, 20), (30, 40)]
    assert gt_point_windows(blob, 1) == [(10, 20)]


def test_gt_point_windows_falls_back_to_clip_axis():
    blob = {"points": [{"clip_start_frame": 5, "clip_end_frame": 9}]}
    assert gt_point_windows(blob) == [(5, 9)]


def test_point_windows_are_not_rally_inclusive_padded_scope_is():
    """The 7 owner contacts outside the raw windows are the reason for pad."""
    blob = gt_blob([(216, 495)], [contact(210), contact(245)])
    lo, hi = region(gt_point_windows(blob, 1), pad=90)
    assert in_region(210, lo, hi) and in_region(245, lo, hi)
    # inside the raw window alone, the serve contact would be a false negative
    assert not in_region(210, *gt_point_windows(blob, 1)[0])


def test_scoped_actions_filters_and_ignores_frameless():
    acts = [act(100), act(200), {"action": "dig"}]
    assert [a["frame_number"] for a in scoped_actions(acts, 150, 250)] == [200]


def test_gt_contacts_reads_annotated_frames_and_flat_shape():
    assert gt_contacts(gt_blob([], [contact(10)])) == [contact(10)]
    assert gt_contacts({"events": [contact(11)]}) == [contact(11)]


# --- arms ------------------------------------------------------------------

def test_perception_arm_reads_no_pass2_field():
    acts = [act(100, "dig", "A", pass2_action="serve", pass2_team="B",
                pass2_demoted=True)]
    got = arm_events(acts, "perception")
    assert got == [{"frame": 100, "action": "dig", "team": "A",
                    "player_id": 1, "touch_number": 1}]


def test_pass2_arm_drops_demotions_and_applies_overrides():
    acts = [act(100, "dig", "A", pass2_action="serve", pass2_team="B"),
            act(200, "serve", "A", pass2_demoted=True),
            act(300, "set", "A")]  # untouched contact keeps its own fields
    got = arm_events(acts, "pass2")
    assert [e["frame"] for e in got] == [100, 300]
    assert (got[0]["action"], got[0]["team"]) == ("serve", "B")
    assert (got[1]["action"], got[1]["team"]) == ("set", "A")


def test_pass2_arm_is_a_subset_of_perception():
    acts = [act(100, "dig", "A", pass2_action="serve"),
            act(200, "serve", "A", pass2_demoted=True),
            act(300, "set", "A")]
    p2 = arm_events(acts, "pass2")
    assert len(p2) == len(arm_events(acts, "perception")) - 1


def test_unknown_arm_raises():
    with pytest.raises(ValueError):
        arm_events([act(1)], "pass3")


def test_prediction_blob_shape_is_evaluate_timed_compatible():
    blob = prediction_blob([{"frame": 1, "action": "dig", "team": "A"}], "v.mp4", 30.0)
    assert blob["video"] == "v.mp4" and blob["fps"] == 30.0
    assert blob["actions"][0]["frame"] == 1
    assert "fps" not in prediction_blob([], "v.mp4", None)


# --- serve table + far-serve tally -----------------------------------------

def test_serve_rows_pick_the_nearest_action_per_gt_serve():
    acts = [act(200), act(247, "dig", pass2_action="serve", pass2_source="relabeled"),
            act(1400, "serve")]
    rows = serve_rows([contact(210), contact(1395)], acts, search_f=80)
    assert rows[0]["nearest_far_serve_f"] == 247
    assert rows[1]["nearest_far_serve_f"] == 1400
    assert [c["delta_f"] for c in rows[0]["candidates"]] == [-10, 37]  # nearest first


def test_serve_rows_ignore_non_serve_gt_contacts():
    assert serve_rows([contact(300, "dig")], [act(300)], search_f=80) == []


def test_far_serve_score_counts_only_within_tolerance():
    rows = [
        {"gt_frame": 210, "gt_side": "far", "nearest_far_serve_f": 212,
         "candidates": []},
        {"gt_frame": 880, "gt_side": "far", "nearest_far_serve_f": 930,
         "candidates": []},
        {"gt_frame": 1395, "gt_side": "near", "nearest_far_serve_f": 1396,
         "candidates": []},
    ]
    got = far_serve_score(rows, tolerance_s=0.5, fps=30.0)
    assert got["gt_far_serves"] == 2
    assert got["hit_within_tolerance"] == 1 and got["hit_frames"] == [210]
    assert got["tolerance_f"] == 15.0
    assert [r["delta_f"] for r in got["rows"]] == [2, 50]


def test_far_serve_score_handles_a_missing_candidate():
    rows = [{"gt_frame": 4770, "gt_side": "far", "nearest_far_serve_f": None,
             "candidates": []}]
    got = far_serve_score(rows, tolerance_s=0.5, fps=30.0)
    assert got["hit_within_tolerance"] == 0 and got["rows"][0]["delta_f"] is None


# --- parity gate + delta ---------------------------------------------------

def test_parity_passes_within_tolerance_and_fails_outside():
    res = {"contact": {"precision": 0.586, "recall": 0.607, "f1": 0.597,
                       "duplicates": 1},
           "dead_time": {"fp_per_dead_minute": 2.703},
           "labels": {"class_accuracy": 0.7059},
           "attribution": {"team_accuracy": 0.7059}}
    assert parity(res)["parity"] is True
    res["contact"]["f1"] = 0.55
    out = parity(res)
    assert out["parity"] is False and out["delta"]["f1"] == pytest.approx(-0.047)


def test_parity_tolerates_missing_numbers_as_failure():
    res = {"contact": {"precision": None, "recall": 0.607, "f1": 0.597,
                       "duplicates": 1},
           "dead_time": {"fp_per_dead_minute": None},
           "labels": {"class_accuracy": 0.7059},
           "attribution": {"team_accuracy": 0.7059}}
    assert parity(res)["parity"] is False


def test_arm_delta_signs_pass2_minus_perception():
    def arm(f1, cls, team, tp, fp, fn):
        return {"contact": {"f1": f1, "precision": 0.5, "recall": 0.5,
                            "tp": tp, "fp": fp, "fn": fn},
                "labels": {"class_accuracy": cls},
                "attribution": {"team_accuracy": team}}
    d = arm_delta(arm(0.597, 0.706, 0.706, 17, 12, 11),
                  arm(0.604, 0.562, 0.625, 16, 9, 12))
    assert d["contact_f1"] == pytest.approx(0.007)
    assert d["class_accuracy"] == pytest.approx(-0.144)
    assert (d["tp"], d["fp"], d["fn"]) == (-1, -3, 1)


def test_arm_delta_handles_none():
    a = {"contact": {"f1": 0.5, "precision": None, "recall": None, "tp": 0,
                     "fp": 0, "fn": 0},
         "labels": {"class_accuracy": None},
         "attribution": {"team_accuracy": None}}
    d = arm_delta(a, a)
    assert d["contact_precision"] is None and d["class_accuracy"] is None


def test_per_contact_rows_classify_each_change_kind(tmp_path):
    sys.path.insert(0, str(REPO / "scripts"))
    import evaluate_timed as et
    gt = gt_blob([(0, 1000)], [contact(100, "dig", side="near", team="A"),
                               contact(200, "set", side="near", team="A"),
                               contact(300, "dig", side="near", team="A")],
                  fps=30.0)
    gt_path = tmp_path / "gt.json"
    gt_path.write_text(json.dumps(gt), encoding="utf-8")
    perception = [{"frame": 100, "action": "dig", "team": "A"},
                  {"frame": 200, "action": "spike", "team": "A"},
                  {"frame": 300, "action": "dig", "team": "A"}]
    pass2 = [{"frame": 100, "action": "serve", "team": "A"},
             {"frame": 200, "action": "spike", "team": "A"}]
    rows = per_contact_rows(gt, str(gt_path),
                            {"perception": perception, "pass2": pass2}, 0.2)
    kinds = {r["gt_frame"]: r["change"] for r in rows}
    assert kinds[100] == "label BROKEN by pass2"
    assert kinds[200] == "same"          # wrong label in both arms
    assert kinds[300] == "LOST by pass2"
    assert et  # matcher imported by the module under test


# --- real artifacts --------------------------------------------------------

needs_artifacts = pytest.mark.skipif(
    not (RELABEL_FILE.exists() and GT_FILE.exists()),
    reason="pass-2 artifacts not built (run scripts/relabel_serves.py)")


@pytest.fixture(scope="module")
def measured(tmp_path_factory):
    return run(workdir=str(tmp_path_factory.mktemp("pass2")))


@needs_artifacts
def test_measured_scope_covers_every_owner_contact(measured):
    s = measured["scope"]
    assert s["gt_contacts_in_region"] == s["gt_contacts_total"] == 28
    assert s["points"] == 8


@needs_artifacts
def test_perception_arm_reproduces_the_t4_dev_clip_baseline(measured):
    p = measured["parity_vs_t4_dev_clip"]
    assert p["parity"], p["delta"]
    for k, v in T4_BASELINE.items():
        assert p["observed"][k] == pytest.approx(v, abs=1e-3)


@needs_artifacts
def test_pass2_far_serve_contact_score_is_zero_of_five(measured):
    fs = measured["serves"]["far_serve_score"]
    assert fs["gt_far_serves"] == len(FAR_SERVE_GT_FRAMES) == 5
    assert fs["hit_within_tolerance"] == 0
    # the relabeled contacts sit 31-50 f late -- the owner-coarse tolerance
    # (15 f) cannot absorb that
    deltas = sorted(abs(r["delta_f"]) for r in fs["rows"])
    assert deltas == [31, 32, 37, 41, 50]


@needs_artifacts
def test_pass2_breaks_three_correct_dig_labels(measured):
    broken = [r for r in measured["per_contact"]
              if r["change"] == "label BROKEN by pass2"]
    assert [r["gt_frame"] for r in broken] == [245, 3071, 4800]
    assert all(r["gt_action"] == "dig" for r in broken)


@needs_artifacts
def test_pass2_contact_scores_are_flat_while_class_accuracy_drops(measured):
    d = measured["delta_pass2_minus_perception"]
    assert abs(d["contact_f1"]) < 0.01
    assert d["class_accuracy"] < -0.10
    assert measured["arms"]["perception"]["contact"]["f1"] == pytest.approx(0.597,
                                                                          abs=1e-3)
    assert measured["arms"]["pass2"]["contact"]["f1"] == pytest.approx(0.604,
                                                                      abs=1e-3)


@needs_artifacts
def test_scoring_is_gt_assisted_and_says_so(measured):
    g = measured["gt_derived_inputs"]
    assert g["autonomous_mode_used"] is False
    assert g["findings"], "pass-2 carries owner anchors -- record must show them"


@needs_artifacts
def test_run_is_reproducible(tmp_path):
    a = run(workdir=str(tmp_path / "a"))
    b = run(workdir=str(tmp_path / "b"))
    for out in (a, b):
        for arm in ARMS:
            out["arms"][arm].pop("predictions", None)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
