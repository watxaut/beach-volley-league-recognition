"""Tests for the G1 held-out contact scorer (scripts/score_heldout_contacts.py).

Two layers, matching `test_pass2_contact_score.py`:

* pure-function tests over synthetic fixtures (point/event scoping, window
  drift, the contact miss taxonomy, the serve hit table);
* artifact tests over the real 20260920 match, which pin the MEASURED
  held-out findings of the G1 session: P9-P33 contact F1 0.772 / class 0.590 /
  team 0.518, the miss taxonomy (46 correct / 57 wrong_label / 36 wrong_team /
  44 missed) and the 12 held-out far serves at 0/12.  They skip when the
  artifacts are absent.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from score_heldout_contacts import (  # noqa: E402
    DEFAULT_MATCH_GT,
    DEFAULT_RELABEL,
    contact_status_rows,
    episode_window_drift,
    miss_taxonomy,
    point_windows,
    region_of,
    scoped_gt_blob,
    select_events,
    select_points,
    serve_hit_table,
    run,
)

MATCH_GT_FILE = REPO / DEFAULT_MATCH_GT
RELABEL_FILE = REPO / DEFAULT_RELABEL


def contact(frame, point, action="dig", side="near", team="A", tol=15):
    return {"frame": frame, "match_frame": frame, "action": action,
            "final_action": action, "player_team": team, "owner_side": side,
            "point": point, "frame_tolerance": tol}


def match_blob():
    return {
        "fps": 25.0,
        "video": "match.mp4",
        "points": [
            {"point": 1, "match_start_frame": 0, "match_end_frame": 100,
             "match_frame_range": [10, 90]},
            {"point": 9, "match_start_frame": 1000, "match_end_frame": 1100,
             "match_frame_range": [1020, 1090]},
            {"point": 10, "match_start_frame": 1200, "match_end_frame": 1300,
             "match_frame_range": [1190, 1310]},  # window does NOT cover contacts
        ],
        "annotated_frames": {"actions": {"events": [
            contact(10, 1, "serve", "near", "A"),
            contact(1020, 9, "dig", "near", "A"),
            contact(1050, 9, "set", "near", "A"),
            contact(1190, 10, "serve", "far", "B"),
            contact(1310, 10, "dig", "near", "A"),
        ]}},
    }


# --- scope -----------------------------------------------------------------

def test_select_points_and_events_are_inclusive():
    blob = match_blob()
    pts = select_points(blob, 9, 10)
    assert [p["point"] for p in pts] == [9, 10]
    ev = select_events(blob, 9, 10)
    assert [e["frame"] for e in ev] == [1020, 1050, 1190, 1310]


def test_point_windows_and_region():
    assert point_windows(select_points(match_blob(), 9, 10)) == [(1000, 1100), (1200, 1300)]
    assert region_of([(1000, 1100), (1200, 1300)], 90) == (910, 1390)


def test_scoped_gt_blob_restricts_and_adds_clip_frames():
    scoped = scoped_gt_blob(match_blob(), 9, 10)
    assert [p["point"] for p in scoped["points"]] == [9, 10]
    assert len(scoped["annotated_frames"]["actions"]["events"]) == 4
    # clip_start/end added so evaluate_timed.point_intervals can read them
    assert scoped["points"][0]["clip_start_frame"] == 1000
    assert scoped["points"][0]["clip_end_frame"] == 1100


def test_scoped_gt_blob_does_not_mutate_source():
    blob = match_blob()
    scoped_gt_blob(blob, 9, 10)
    assert "clip_start_frame" not in blob["points"][1]


def test_episode_window_drift_measures_coverage():
    drift = episode_window_drift(select_points(match_blob(), 9, 10))
    rows = {r["point"]: r for r in drift["points"]}
    assert rows[9]["window_covers_contacts"] is True
    assert rows[10]["window_covers_contacts"] is False
    assert rows[10]["start_delta_f"] == 10   # 1200 - 1190
    assert rows[10]["end_delta_f"] == -10    # 1300 - 1310
    assert drift["windows_covering_owner_contacts"] == 1
    assert drift["points_scored"] == 2


# --- contact taxonomy ------------------------------------------------------

def _scoped_path(tmp_path, blob):
    p = tmp_path / "gt.json"
    p.write_text(json.dumps(blob), encoding="utf-8")
    return p


def test_contact_status_rows_labels_each_kind(tmp_path):
    blob = scoped_gt_blob(match_blob(), 9, 10)
    path = _scoped_path(tmp_path, blob)
    events = [
        {"frame": 1020, "action": "dig", "team": "A"},    # correct
        {"frame": 1050, "action": "spike", "team": "A"},  # wrong label
        {"frame": 1190, "action": "serve", "team": "A"},  # wrong team (GT B)
    ]
    rows = contact_status_rows(blob, str(path), events, 0.2, search_f=130)
    by = {r["gt_frame"]: r for r in rows}
    assert by[1020]["status"] == "correct"
    assert by[1050]["status"] == "wrong_label"
    assert by[1190]["status"] == "wrong_team"
    assert by[1310]["status"] == "missed"
    # a missed contact still reports its nearest emitted action
    assert by[1310]["nearest"][0]["action"] == "serve"
    assert by[1310]["nearest"][0]["delta_f"] == 1190 - 1310

def test_contact_status_rows_unspecified_action_is_class_agnostic(tmp_path):
    blob = match_blob()
    blob["annotated_frames"]["actions"]["events"][1]["owner_action_unspecified"] = True
    blob["annotated_frames"]["actions"]["events"][1]["action"] = None
    blob["annotated_frames"]["actions"]["events"][1]["final_action"] = None
    scoped = scoped_gt_blob(blob, 9, 10)
    path = _scoped_path(tmp_path, scoped)
    rows = contact_status_rows(scoped, str(path),
                               [{"frame": 1020, "action": "anything", "team": "A"}],
                               0.2, search_f=80)
    row = {r["gt_frame"]: r for r in rows}[1020]
    assert row["gt_unspecified"] is True
    assert row["status"] == "correct"    # no label to judge


def test_miss_taxonomy_buckets_and_splits(tmp_path):
    blob = scoped_gt_blob(match_blob(), 9, 10)
    path = _scoped_path(tmp_path, blob)
    # one correct, one wrong label, one wrong team, one missed (1310)
    events = [{"frame": 1020, "action": "dig", "team": "A"},
              {"frame": 1050, "action": "spike", "team": "A"},
              {"frame": 1190, "action": "serve", "team": "A"}]
    rows = contact_status_rows(blob, str(path), events, 0.2, search_f=130)
    tax = miss_taxonomy(rows)
    assert tax["status_counts"] == {"correct": 1, "wrong_label": 1,
                                    "wrong_team": 1, "missed": 1}
    assert tax["n_gt_contacts"] == 4
    assert tax["by_side"]["far"]["n"] == 1
    assert tax["missed_by_action"] == {"dig": 1}
    assert tax["missed_with_nearby_action"] == 1
    assert tax["missed_with_no_action_within_search"] == 0
    assert tax["wrong_label_confusion"] == {"set -> spike": 1}


def test_miss_taxonomy_counts_a_far_from_any_action(tmp_path):
    blob = scoped_gt_blob(match_blob(), 9, 10)
    path = _scoped_path(tmp_path, blob)
    rows = contact_status_rows(blob, str(path), [], 0.2, search_f=80)
    tax = miss_taxonomy(rows)
    assert tax["status_counts"]["missed"] == 4
    assert tax["missed_with_no_action_within_search"] == 4
    assert tax["contact_recall"] == 0.0


# --- serve hit table -------------------------------------------------------

def serve_row(frame, side, candidates):
    return {"gt_frame": frame, "gt_side": side, "gt_track_id": 1,
            "candidates": candidates}


def cand(frame, action="serve"):
    return {"frame": frame, "delta_f": frame, "action": action,
            "pass2_action": action}


def test_serve_hit_table_splits_far_and_near():
    rows = [
        serve_row(100, "near", [cand(102)]),           # hit (2f)
        serve_row(200, "far", [cand(230)]),            # miss (30f)
        serve_row(300, "far", []),                     # no serve at all
    ]
    out = serve_hit_table(rows, tolerance_f=15.0, search_f=80)
    assert out["near_serves"] == {"n": 1, "hits": 1, "hit_rate": 1.0}
    assert out["far_serves"] == {"n": 2, "hits": 0, "hit_rate": 0.0}
    assert out["all_serves"] == {"n": 3, "hits": 1, "hit_rate": pytest.approx(1 / 3, abs=1e-4)}
    far = [r for r in out["rows"] if r["gt_side"] == "far"]
    assert far[0]["delta_f"] == 30 and far[0]["hit"] is False
    assert far[1]["nearest_serve_f"] is None and far[1]["delta_f"] is None


# --- real artifacts --------------------------------------------------------

needs_artifacts = pytest.mark.skipif(
    not (MATCH_GT_FILE.exists() and RELABEL_FILE.exists()),
    reason="held-out match artifacts not built (run scripts/build_match_contact_gt.py)")


@pytest.fixture(scope="module")
def measured(tmp_path_factory):
    return run(workdir=str(tmp_path_factory.mktemp("heldout")))


@needs_artifacts
def test_measured_scope_is_p9_p33_and_covers_every_contact(measured):
    s = measured["scope"]
    assert s["point_from"] == 9 and s["point_to"] == 33
    assert s["points"] == 25
    assert s["gt_contacts_in_region"] == s["gt_contacts_total_scoped"] == 183
    assert s["region"] == [5240, 26147]
    assert measured["time"]["effective_tolerance_f"] == 15.0


@needs_artifacts
def test_perception_heldout_headline_numbers(measured):
    p = measured["arms"]["perception"]
    assert p["contact"]["precision"] == pytest.approx(0.7853, abs=1e-3)
    assert p["contact"]["recall"] == pytest.approx(0.7596, abs=1e-3)
    assert p["contact"]["f1"] == pytest.approx(0.7722, abs=1e-3)
    assert p["class_accuracy"] == pytest.approx(0.5899, abs=1e-3)
    assert p["team_accuracy"] == pytest.approx(0.5180, abs=1e-3)
    assert p["contact"]["fn"] == 44


@needs_artifacts
def test_pass2_is_flat_but_moves_class_and_team(measured):
    d = measured["delta_pass2_minus_perception"]
    assert abs(d["contact_f1"]) < 0.01
    assert d["class_accuracy"] < 0
    assert measured["arms"]["pass2"]["contact"]["f1"] == pytest.approx(0.7744, abs=1e-3)
    assert measured["arms"]["pass2"]["team_accuracy"] == pytest.approx(0.5612, abs=1e-3)


@needs_artifacts
def test_heldout_miss_taxonomy(measured):
    tax = measured["perception_miss_taxonomy"]
    assert tax["n_gt_contacts"] == 183
    assert tax["status_counts"] == {"correct": 46, "wrong_label": 57,
                                    "wrong_team": 36, "missed": 44}
    assert tax["contact_recall"] == pytest.approx(0.7596, abs=1e-3)
    assert tax["label_accuracy_on_found"] == pytest.approx(0.5899, abs=1e-3)
    # label errors dominate the held-out loss (57 > missed 44 > team 36)
    assert tax["wrong_label_confusion"]["spike -> block"] == 7
    assert tax["wrong_label_confusion"]["set -> dig"] == 10


@needs_artifacts
def test_overpass_class_is_never_emitted_correctly_heldout(measured):
    b = measured["perception_miss_taxonomy"]["by_action"]["overpass"]
    assert b["n"] == 18
    assert b["correct"] == 0 and b["wrong_team"] == 0
    assert b["recall"] == 0.0


@needs_artifacts
def test_heldout_far_serves_are_zero_of_twelve(measured):
    sh = measured["serves"]["serve_hits"]
    assert sh["far_serves"] == {"n": 12, "hits": 0, "hit_rate": 0.0}
    assert sh["near_serves"] == {"n": 13, "hits": 11,
                                 "hit_rate": pytest.approx(11 / 13, abs=1e-4)}
    assert sh["all_serves"]["hits"] == 11
    # every far serve that has a nearby emitted "serve" is the GT reception of
    # the same rally, 26-34 f later (pass-2 relabels the reception)
    deltas = sorted(abs(r["delta_f"]) for r in sh["rows"]
                    if r["gt_side"] == "far" and r["delta_f"] is not None)
    assert deltas == [26, 26, 27, 28, 28, 29, 30, 34]


@needs_artifacts
def test_episode_window_drift_is_flagged(measured):
    drift = measured["episode_window_drift"]
    assert drift["windows_covering_owner_contacts"] == 12
    assert drift["points_scored"] == 25


@needs_artifacts
def test_waterfall_is_declared_unavailable(measured):
    assert measured["waterfall"]["available"] is False
    assert "match_bw03_diag" in measured["generated_from"]["r1_match_diag"]


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
        for arm in ("perception", "pass2"):
            out["arms"][arm].pop("predictions", None)
        out["generated_from"].pop("scoped_gt", None)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
