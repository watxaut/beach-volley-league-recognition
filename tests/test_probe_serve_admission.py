"""Unit tests for the T5 step-1 serve-admission probe (synthetic + real GT).

The probe is a diagnostic: the point of these tests is that its offline replay
of the bootstrap is (a) faithful to the production gates and (b) honest about
the counterfactuals it reports, so the numbers in
``docs/t5_serve_admission_diagnosis.md`` can be trusted and re-derived.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from probe_serve_admission import (  # noqa: E402
    DEFAULTS,
    HAND_MARKER,
    _weak_ok,
    det_rows,
    gt_serves,
    nearest_player_dist,
    replay,
    scan,
    speed_gate,
    tiers,
    tracker_params,
    write_markdown,
)


def _det(x, y, conf=0.6, width=16, persist=0.05, suspect=False, removed=False):
    return {"center": [float(x), float(y)], "conf": conf, "width": width,
            "persist": persist, "suspect": suspect, "removed": removed}


def _params(**over):
    p = dict(DEFAULTS)
    p.update(over)
    return p


# --- scan: the production gates --------------------------------------------

def test_scan_locks_on_motion_above_lock_min_speed():
    p = _params()
    res = scan([_det(100, 100)], [[[90.0, 100.0]]], p)
    assert res["hit"] and res["speed"] == pytest.approx(10.0)
    assert res["fail"] is None


def test_scan_names_the_speed_failure():
    """A far-side toss: 4 px/f with the 8 px/f bar -> speed, not gap/jump."""
    p = _params()
    res = scan([_det(100, 100)], [[[96.0, 100.0]]], p)
    assert not res["hit"]
    assert res["fail"] == "speed_below_lock_min_speed"
    assert res["speed"] == pytest.approx(4.0)


def test_scan_names_the_jump_failure():
    p = _params()
    res = scan([_det(300, 100)], [[[100.0, 100.0]]], p)
    assert not res["hit"]
    assert res["fail"] == "pair_farther_than_lock_max_jump"


def test_scan_names_the_pair_gap_failure():
    """pair_gap 2: an age-3 pair (post-contact 39 px / 3f) is not evidence."""
    p = _params()
    res = scan([_det(100, 100)], [[[100.0, 139.0]], [], []], p)
    assert not res["hit"]
    assert res["fail"] == "no_pair_within_lock_max_pair_gap"
    assert scan([_det(100, 100)], [[[100.0, 139.0]], [], []],
                _params(lock_max_pair_gap=3))["hit"]


def test_tiers_exclude_static_survivors_and_split_on_confidence():
    """`scan` consumes already-filtered tiers, exactly like `_try_lock`."""
    rows = [_det(100, 100, conf=0.9, removed=True),
            _det(120, 120, conf=0.9, suspect=True),
            _det(100, 100, conf=0.9),          # high tier
            _det(140, 140, conf=0.3)]          # low tier (boot_low_conf_floor)
    hi, lo = tiers(rows, _params())
    assert [d["conf"] for d in hi] == [0.9]
    assert [d["conf"] for d in lo] == [0.3]
    assert all(not d["removed"] and not d["suspect"] for d in hi + lo)


# --- apparent-size normalised gate -----------------------------------------

def test_speed_gate_is_flat_without_a_reference():
    assert speed_gate(_params(), _det(0, 0, width=15), None) == 8.0


def test_speed_gate_scales_with_apparent_width():
    p = _params(speed_width_ref=50.0)
    assert speed_gate(p, _det(0, 0, width=50), None) == pytest.approx(8.0)
    assert speed_gate(p, _det(0, 0, width=15), None) == pytest.approx(2.4)
    assert speed_gate(p, _det(0, 0, width=90), None) == pytest.approx(8.0)


def test_size_normalised_gate_admits_a_slow_small_ball():
    p = _params(speed_width_ref=50.0)
    res = scan([_det(100, 100, width=15)], [[[96.0, 100.0]]], p)
    assert res["hit"]


# --- weak-lock gates (counterfactual only) ----------------------------------

def test_weak_gate_ascending_rejects_a_descending_pair():
    p = _params(lock_min_speed=3.0, weak_ascending=True)
    hit = {"speed": 4.0, "ascending": False}
    assert not _weak_ok(_det(0, 0), hit, [], {}, p)
    hit["ascending"] = True
    assert _weak_ok(_det(0, 0), hit, [], {}, p)


def test_weak_gate_requires_sustained_sightings():
    p = _params(lock_min_speed=3.0, weak_radius=20.0, weak_sightings=3)
    hist = [[[10.0, 10.0]], [[12.0, 10.0]], [[900.0, 900.0]]]
    assert not _weak_ok(_det(11, 10), {"speed": 4.0, "ascending": True},
                        hist, {}, p)
    hist[2] = [[11.0, 11.0]]
    assert _weak_ok(_det(11, 10), {"speed": 4.0, "ascending": True}, hist, {}, p)


def test_weak_gate_persist_and_player_proximity():
    p = _params(lock_min_speed=3.0, weak_max_persist=0.25)
    hit = {"speed": 4.0, "ascending": True}
    assert not _weak_ok(_det(0, 0, persist=0.4), hit, [], {}, p)
    assert _weak_ok(_det(0, 0, persist=0.1), hit, [], {}, p)
    p2 = _params(lock_min_speed=3.0, weak_player_radius=100.0)
    rec = {"players": [{"center": [300.0, 300.0], "predicted": False}]}
    assert not _weak_ok(_det(0, 0), hit, [], rec, p2)
    rec = {"players": [{"center": [50.0, 0.0], "predicted": False}]}
    assert _weak_ok(_det(0, 0), hit, [], rec, p2)
    assert nearest_player_dist(rec, [0.0, 0.0]) == pytest.approx(50.0)
    assert nearest_player_dist({}, [0.0, 0.0]) is None


# --- replay ------------------------------------------------------------------

def _frame(dets, locked=False, reason="unlocked_no_motion", players=None):
    return {"frame": 0, "ball_dets": [
        {"center": d["center"], "conf": d["conf"], "bbox": [0, 0, d["width"], 0],
         "persist": d["persist"], "suspect": d["suspect"], "removed": d["removed"]}
        for d in dets],
        "ball_track": {"locked": locked, "state": "none", "reason": reason},
        "players": players or []}


def test_replay_locks_on_a_moving_pair_and_resyncs_on_the_dump():
    frames = {
        0: _frame([_det(100, 100, width=15)]),
        1: _frame([_det(120, 100, width=15)]),
        2: _frame([]),
    }
    dec = replay(frames, _params())
    assert not dec[0]["locked"]
    assert dec[1]["locked"] and dec[1]["reason"] == "bootstrap_locked"
    # the lock stays in force until the real tracker reports locked again
    assert dec[2]["locked"]


def test_replay_never_locks_on_a_static_spare():
    frames = {f: _frame([_det(100, 100, conf=0.9, persist=0.4, suspect=True)])
              for f in range(6)}
    dec = replay(frames, _params())
    assert not any(dec[f]["locked"] for f in frames)


def test_replay_diagnoses_an_empty_frame_as_no_detections():
    dec = replay({0: _frame([])}, _params())
    assert dec[0]["fail"] == "no_detections"


def test_det_rows_reads_the_diag_schema():
    rows = det_rows(_frame([_det(10, 20, conf=0.5, width=15)]))
    assert rows[0]["center"] == [10.0, 20.0] and rows[0]["width"] == 15


# --- real artifacts ----------------------------------------------------------

def test_tracker_params_match_the_production_config():
    p = tracker_params()
    assert p["lock_min_speed"] == 8.0
    assert p["lock_max_jump"] == 90.0
    assert p["lock_max_pair_gap"] == 2
    assert p["low_confidence_threshold"] == 0.4
    assert p["boot_low_conf_floor"] == 0.15


def test_dev_gt_has_eight_serves_with_the_side_the_owner_dictated():
    serves = gt_serves(str(ROOT / "ground_truth"
                           / "video_ari_joan_8_first_points_annotations.json"))
    assert [s["frame"] for s in serves] == [210, 880, 1395, 2154, 2575,
                                            3038, 3747, 4770]
    # the diagnosis' core claim: every far-side serve is in the list
    assert [s["side"] for s in serves] == ["far", "far", "near", "far",
                                           "near", "far", "near", "far"]


def test_committed_doc_keeps_the_measured_headline():
    doc = (ROOT / "docs" / "t5_serve_admission_diagnosis.md").read_text()
    assert "far-side serves" in doc
    assert "5 of the 5" in doc
    assert HAND_MARKER in doc


def test_write_markdown_preserves_the_hand_analysis(tmp_path):
    path = tmp_path / "d.md"
    report = {"diag": "x", "ground_truth": "y", "params": dict(DEFAULTS),
              "serves": [], "window": 40}
    path.write_text("generated\n\n" + HAND_MARKER + "\nhand prose\n")
    write_markdown(str(path), report)
    out = path.read_text()
    assert out.startswith("# T5 step 1")
    assert "hand prose" in out
    json.dumps({"ok": True})  # the report stays JSON-serialisable
