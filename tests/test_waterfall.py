"""Unit tests for the T4 loss-waterfall stage classification (synthetic data).

The point of these tests is the *classifier*, not the pipeline: given a
synthetic diag window and (optionally) a paired prediction, which stage does
:classify_contact` blame, and where does an unmatched prediction come from?

Stage order (see scripts/waterfall.py):
    1 raw detection -> 2 track admission -> 3 candidate -> 4 candidate gate
    -> 5 actor/team -> 6 gesture/context label -> 7 survives correct
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from waterfall import (  # noqa: E402
    GATE_REASON_TEXT,
    STAGE_ADMISSION,
    STAGE_ATTRIBUTION,
    STAGE_CANDIDATE,
    STAGE_DETECTION,
    STAGE_GATE,
    STAGE_LABEL,
    STAGE_ORDER,
    STAGE_SURVIVED,
    classify_contact,
    classify_false_positive,
    render_markdown,
)

CENTER = [100.0, 200.0]


def _frame(frame, *, dets=True, state="tracked", reason="locked_admitted",
           candidates=None, actions=None, players=None):
    return {
        "frame": frame,
        "ball_dets": ([{"center": CENTER, "conf": 0.8, "suspect": False,
                        "removed": False, "persist": 0.05}] if dets else []),
        "ball_track": {"state": state, "locked": state != "unlocked",
                       "missing": 0, "center": CENTER, "conf": 0.8, "reason": reason},
        "players": players if players is not None else
                   [{"track_id": 2, "team": "A", "bbox": [90, 150, 110, 250]}],
        "actions": actions or [],
        "candidates": candidates or [],
    }


def _window(lo, hi, **kw):
    return {f: _frame(f, **kw) for f in range(lo, hi + 1)}


ACCEPTED = {"frame": 100, "seen_at": 107, "stage": "accepted", "kind": "bounce",
            "gesture": "bump_set", "track_id": 2, "player_id": 1, "team": "A",
            "touch_number": 1, "rally_id": 5, "confidence": 0.55,
            "attribution_source": "width"}


def _pred(action="dig", team="A"):
    return {"frame": 100, "action": action, "team": team,
            "raw": {"action": action, "team": team, "touch_number": 1, "rally_id": 5}}


# --- stage 1: raw detection -------------------------------------------------

def test_dead_at_raw_detection_when_no_ball_detection():
    frames = _window(90, 110, dets=False, state="none", reason="unlocked_no_motion")
    res = classify_contact(100, "dig", "A", 10, frames)
    assert res["stage"] == STAGE_DETECTION
    assert "no raw ball detection" in res["detail"]


def test_raw_detection_window_is_looked_up_as_a_range():
    # a single detection anywhere in the +-tol window is enough
    frames = _window(90, 110, dets=False, state="none", reason="x")
    frames[100]["ball_dets"] = [{"center": CENTER, "conf": 0.5}]
    res = classify_contact(100, "dig", "A", 10, frames)
    assert res["stage"] != STAGE_DETECTION


# --- stage 2: track admission ----------------------------------------------

def test_dead_at_track_admission_when_only_predictions():
    frames = _window(90, 110, state="predicted", reason="coast_predicted")
    res = classify_contact(100, "dig", "A", 10, frames)
    assert res["stage"] == STAGE_ADMISSION
    assert "coast_predicted" in res["detail"]


def test_dead_at_track_admission_when_never_locked():
    frames = _window(90, 110, state="unlocked", reason="unlocked_no_motion")
    res = classify_contact(100, "dig", "A", 10, frames)
    assert res["stage"] == STAGE_ADMISSION
    assert "unlocked_no_motion" in res["detail"]


# --- stage 3: candidate -----------------------------------------------------

def test_dead_at_candidate_when_no_inflection():
    probe = {"frame": 100, "seen_at": 107, "stage": "rejected",
             "reason": "no_contact_geometry"}
    frames = _window(90, 110, candidates=[probe])
    res = classify_contact(100, "dig", "A", 10, frames)
    assert res["stage"] == STAGE_CANDIDATE
    assert "no_contact_geometry" in res["detail"]


def test_no_ball_sighting_probe_is_stage_three_not_two():
    probe = {"frame": 100, "stage": "rejected", "reason": "no_ball_sighting"}
    frames = _window(90, 110, candidates=[probe])
    res = classify_contact(100, "dig", "A", 10, frames)
    assert res["stage"] == STAGE_CANDIDATE


# --- stage 4: candidate gate ------------------------------------------------

@pytest.mark.parametrize("reason", sorted(GATE_REASON_TEXT))
def test_dead_at_gate_names_the_gate(reason):
    frames = _window(90, 110, candidates=[{"frame": 100, "stage": "rejected",
                                            "reason": reason}])
    res = classify_contact(100, "dig", "A", 10, frames)
    assert res["stage"] == STAGE_GATE
    assert res["detail"] == GATE_REASON_TEXT[reason]
    assert res["candidate_frame"] == 100


def test_gate_loses_to_an_accepted_candidate_in_the_same_window():
    frames = _window(90, 110, candidates=[
        {"frame": 95, "stage": "rejected", "reason": "reach"},
        ACCEPTED,
    ])
    res = classify_contact(100, "dig", "A", 10, frames, matched_pred=_pred())
    assert res["stage"] == STAGE_SURVIVED


def test_accepted_but_never_emitted_is_reported_as_candidate():
    frames = _window(90, 110, candidates=[ACCEPTED])
    res = classify_contact(100, "dig", "A", 10, frames, matched_pred=None)
    assert res["stage"] == STAGE_CANDIDATE
    assert "never emitted" in res["detail"]


# --- stage 5: attribution ---------------------------------------------------

def test_dead_at_attribution_when_team_is_wrong():
    frames = _window(90, 110, candidates=[ACCEPTED])
    res = classify_contact(100, "dig", "B", 10, frames, matched_pred=_pred(team="A"))
    assert res["stage"] == STAGE_ATTRIBUTION
    assert "emitted team A vs GT B" in res["detail"]


def test_team_unknown_on_prediction_skips_the_attribution_check():
    frames = _window(90, 110, candidates=[ACCEPTED])
    pred = _pred()
    pred["raw"] = {"action": "dig"}  # no team emitted
    res = classify_contact(100, "dig", "A", 10, frames, matched_pred=pred)
    assert res["stage"] == STAGE_SURVIVED


# --- stage 6: label ---------------------------------------------------------

def test_dead_at_label_when_action_is_wrong():
    frames = _window(90, 110, candidates=[ACCEPTED])
    res = classify_contact(100, "dig", "A", 10, frames, matched_pred=_pred(action="set"))
    assert res["stage"] == STAGE_LABEL
    assert "pred set" in res["detail"] and "GT dig" in res["detail"]


def test_attribution_is_reported_before_label():
    frames = _window(90, 110, candidates=[ACCEPTED])
    res = classify_contact(100, "dig", "B", 10, frames,
                           matched_pred=_pred(action="set", team="A"))
    assert res["stage"] == STAGE_ATTRIBUTION


# --- stage 7 ---------------------------------------------------------------

def test_survives_correct():
    frames = _window(90, 110, candidates=[ACCEPTED])
    res = classify_contact(100, "dig", "A", 10, frames, matched_pred=_pred())
    assert res["stage"] == STAGE_SURVIVED
    assert res["candidate_frame"] == 100 and res["gesture"] == "bump_set"


# --- false positives --------------------------------------------------------

def test_duplicate_fp():
    frames = {100: _frame(100, candidates=[ACCEPTED])}
    fp = classify_false_positive(_pred(), frames, duplicate_of=98, in_point=True)
    assert fp["source"] == "duplicate" and fp["duplicate_of_gt_frame"] == 98
    assert fp["candidate_kind"] == "bounce" and fp["gesture"] == "bump_set"


def test_dead_time_fp():
    frames = {100: _frame(100)}
    assert classify_false_positive(_pred(), frames, in_point=False)["source"] == "dead_time"


def test_in_point_spurious_fp_is_annotated_with_its_candidate():
    frames = {100: _frame(100, candidates=[ACCEPTED])}
    fp = classify_false_positive(_pred(action="serve"), frames, in_point=True)
    assert fp["source"] == "in_point_spurious"
    assert fp["pred_action"] == "serve" and fp["track_id"] == 2
    assert fp["touch_number"] == 1 and fp["rally_id"] == 5


def test_fp_without_diag_record_still_classifies():
    fp = classify_false_positive(_pred(), {}, in_point=None)
    assert fp["source"] == "in_point_spurious" and fp["candidate_kind"] is None


# --- rendering --------------------------------------------------------------

def test_render_markdown_contains_table_and_counts():
    res = {
        "diag": "d.jsonl", "predictions": "p.json", "ground_truth": "g.json",
        "time": {"source": "frame/fps", "fps": 30.0, "tolerance_base_s": 0.2},
        "counts": {"gt_contacts": 1, "predictions": 2, "matched": 1, "duplicates": 1,
                   "unmatched_gt": 0, "unmatched_pred": 1},
        "stage_counts": {s: 0 for s in STAGE_ORDER},
        "fp_summary": {"duplicate": 1},
        "rows": [{"point": 1, "gt_frame": 100, "gt_action": "dig", "gt_team": "A",
                  "owner_track_id": 2, "stage": STAGE_SURVIVED, "detail": "ok"}],
        "false_positives": [classify_false_positive(_pred(), {}, duplicate_of=98,
                                                    in_point=True)],
    }
    res["stage_counts"][STAGE_SURVIVED] = 1
    md = render_markdown(res)
    assert "| 7_survives_correct | 1 |" in md
    assert "| 1 | 100 | dig | A | 2 |" in md
    assert "duplicate" in md
