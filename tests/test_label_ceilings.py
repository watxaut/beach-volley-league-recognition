"""Pins for the G3 label-lever ceiling probe (session #76).

The probe's whole value is that it reuses the REAL matcher, so these tests
pin the two facts every later claim rests on:

1. ``evaluate_timed.match_events`` is CLASS-AGNOSTIC, so a pure relabel
   cannot move contact F1 -- the G3 bar moves only through class accuracy.
2. The ``90/139 = 0.647`` "label-only ceiling" in STATUS item 0a is a
   TOUCH-accuracy figure (``docs/g3_reach_cascade.md:43``), not a label
   ceiling: the label-only oracle on the same 139 found contacts is
   139/139 = 1.000.

Fixture-based where possible: the arm plumbing is exercised on synthetic
events so no pipeline dump is pinned; the recorded baselines are pinned as a
range assertion inside the probe itself (not here), since the dumps are
git-ignored artifacts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_timed as et  # noqa: E402
import probe_label_ceilings as plc  # noqa: E402


# ----------------------------------------------------------------------
# 1. the matcher is class-agnostic

def _ev(frame, action):
    return et.normalize_event({"frame": frame, "action": action, "team": "A"})


@pytest.fixture
def toy_pairs():
    gt = [_ev(100, "dig"), _ev(200, "overpass"), _ev(300, "set")]
    pred = [_ev(102, "spike"), _ev(205, "set"), _ev(301, "block")]
    return gt, pred


def test_relabeling_cannot_change_the_pairing(toy_pairs):
    """The same contacts, relabeled, must match the same way.

    This is what makes a "label-only ceiling" measurable by rewriting one
    field, and what makes a lever's effect show up ONLY in class accuracy.
    """
    gt, pred = toy_pairs
    tb = et.TimeBase(fps=30.0)
    m0 = et.match_events(gt, pred, tb, base_tolerance_s=0.2)
    relabeled = [dict(e, action="serve") for e in pred]
    m1 = et.match_events(gt, relabeled, tb, base_tolerance_s=0.2)
    assert [(g["frame"], p["frame"]) for g, p, _ in m0["pairs"]] == \
           [(g["frame"], p["frame"]) for g, p, _ in m1["pairs"]]
    assert len(m0["pairs"]) == len(m1["pairs"]) == 3


def test_relabel_moves_class_accuracy_only(toy_pairs):
    gt, pred = toy_pairs
    tb = et.TimeBase(fps=30.0)
    m0 = et.match_events(gt, pred, tb, base_tolerance_s=0.2)
    m1 = et.match_events(gt, [dict(e, action="serve") for e in pred],
                         tb, base_tolerance_s=0.2)
    assert et.score_contacts(m0) == et.score_contacts(m1)
    assert et.score_labels(m0)["class_accuracy"] == 0.0
    assert et.score_labels(m1)["class_accuracy"] == 0.0


def test_oracle_relabel_scores_one(toy_pairs):
    """Relabeling each prediction to its GT class is a perfect class score."""
    gt, pred = toy_pairs
    tb = et.TimeBase(fps=30.0)
    m = et.match_events(gt, pred, tb, base_tolerance_s=0.2)
    fixed = [dict(e, action=g["action"]) for g, e in
             ((g, p) for g, p, _d in m["pairs"])]
    m2 = et.match_events(gt, fixed, tb, base_tolerance_s=0.2)
    assert et.score_labels(m2)["class_accuracy"] == 1.0


# ----------------------------------------------------------------------
# 2. the probe's own helpers

def test_apply_relabel_only_touches_named_frames():
    ev = [{"frame": 10, "action": "dig"}, {"frame": 20, "action": "set"}]
    out = plc.apply_relabel(ev, {20: "overpass"})
    assert out[0] == {"frame": 10, "action": "dig"}
    assert out[1] == {"frame": 20, "action": "overpass"}
    # the input is not mutated
    assert ev[1]["action"] == "set"


def test_apply_relabel_on_empty_map_is_identity():
    ev = [{"frame": 10, "action": "dig"}]
    assert plc.apply_relabel(ev, {}) == ev


def test_emittable_vocabulary_excludes_freeball():
    """`freeball` is a GT class the enum cannot emit (#74d).

    Pinned so a future rename cannot silently make the `never_emitted` arm a
    no-op that looks like "no GT class is unreachable".
    """
    assert "freeball" not in plc.EMITTABLE
    assert {"dig", "set", "spike", "serve", "overpass"} <= plc.EMITTABLE


def test_matched_pairs_uses_the_real_matcher(toy_pairs):
    gt = [{"frame": 100, "final_action": "dig", "frame_tolerance": 15,
           "player_team": "A"}]
    pred = [{"frame": 105, "action": "spike", "team": "A"}]
    pairs = plc._matched_pairs(gt, pred, 30.0, 0.2)
    assert pairs == [(100, "dig", 105, "spike")]


def test_coarse_frame_tolerance_is_honoured():
    """An owner contact with frame_tolerance=15 is reachable at +/-15 f."""
    gt = [{"frame": 1000, "final_action": "dig", "frame_tolerance": 15,
           "player_team": "A"}]
    assert plc._matched_pairs(gt, [{"frame": 1014, "action": "dig"}], 30.0, 0.2)
    assert not plc._matched_pairs(gt, [{"frame": 1040, "action": "dig"}], 30.0, 0.2)


# ----------------------------------------------------------------------
# 3. the dump loaders

def test_diag_accepted_reads_only_accepted_stage(tmp_path):
    diag = tmp_path / "d.jsonl"
    diag.write_text("\n".join(json.dumps(r) for r in [
        {"frame": 5, "candidates": [
            {"stage": "rejected", "reason": "reach", "frame": 5},
            {"stage": "accepted", "frame": 5, "action": "dig", "team": "A",
             "player_id": 1, "touch_number": 1}]},
        {"frame": 6, "candidates": [
            {"stage": "candidate_found", "frame": 6, "action": "set"}]},
        {"meta": {}},
    ]) + "\n", encoding="utf-8")
    rows = plc.diag_accepted(str(diag))
    assert [(r["frame"], r["action"]) for r in rows] == [(5, "dig")]


def test_diag_accepted_is_frame_sorted(tmp_path):
    diag = tmp_path / "d.jsonl"
    diag.write_text("\n".join(json.dumps({"frame": f, "candidates": [
        {"stage": "accepted", "frame": f, "action": "dig"}]})
        for f in (90, 10, 50)) + "\n", encoding="utf-8")
    assert [r["frame"] for r in plc.diag_accepted(str(diag))] == [10, 50, 90]


def test_dump_actions_maps_frame_number(tmp_path):
    dump = tmp_path / "pipeline_output.json"
    dump.write_text(json.dumps({"actions": [
        {"frame_number": 7, "action": "dig", "team": "A", "player_id": 2},
        {"action": "set"},  # no frame -> dropped
    ]}), encoding="utf-8")
    rows = plc.dump_actions(str(dump))
    assert rows == [{"frame": 7, "action": "dig", "team": "A",
                     "player_id": 2, "touch_number": None}]
