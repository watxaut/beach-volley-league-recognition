"""Unit tests for scripts/action_evidence.py (G3 task 1: diagnose only).

Synthetic, small inputs only -- the point is to pin the OUTCOME labelling
(cases: correct / wrong_label / wrong_team / wrong_label_and_team / duplicate /
fp_in_point / fp_dead_time) and the FEATURE extraction windows/gates, not to
reproduce pipeline behaviour.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from action_evidence import (  # noqa: E402
    CORRECT,
    OUTCOME_ORDER,
    SPEED_F,
    _applicable_reach,
    _ball_speeds,
    _bin_label,
    _nearest_ball_det,
    _point_bbox_distance,
    _track_continuity,
    best_split,
    build_rows,
    calibration_check,
    extract_features,
    outcome_counts,
    outcome_labels,
    per_clip_split_consistency,
    precision_table,
)
from src.recognition.action_classifier import ActionClassifier  # noqa: E402


# ---------------------------------------------------------------- fixtures --

def _write(tmp_path, name, blob):
    p = tmp_path / name
    p.write_text(json.dumps(blob))
    return str(p)


def _gt(events, points=None, fps=25.0):
    blob = {"fps": fps, "annotated_frames": {"actions": {"events": events}}}
    if points is not None:
        blob["points"] = points
    return blob


def _pred(actions, fps=25.0):
    return {"video": {"fps": fps}, "actions": actions}


def _e(frame, action=None, team=None, tol=None):
    ev = {"frame": frame, "final_action": action, "player_team": team}
    if tol is not None:
        ev["frame_tolerance"] = tol
    return ev


def _a(frame, action, team=None, conf=0.55):
    return {"frame_number": frame, "action": action, "team": team,
            "confidence": conf, "gesture": "bump_set", "contact_kind": "drive",
            "touch_number": 1, "rally_id": 1}


# ------------------------------------------------------------ outcome label --

def test_outcome_correct_wrong_label_wrong_team(tmp_path):
    gt = _write(tmp_path, "gt.json", _gt([
        _e(100, "dig", "A"), _e(300, "set", "B"), _e(500, "spike", "A")]))
    pred = _write(tmp_path, "pred.json", _pred([
        _a(102, "dig", "A"),      # correct
        _a(302, "dig", "B"),      # matched, wrong label, right team
        _a(502, "spike", "B"),    # matched, right label, wrong team
    ]))
    lab = outcome_labels(gt, pred)
    assert lab[102]["outcome"] == CORRECT
    assert lab[302]["outcome"] == "wrong_label"
    assert lab[502]["outcome"] == "wrong_team"
    assert lab[302]["gt_frame"] == 300


def test_outcome_wrong_label_and_team_and_gt_nulls(tmp_path):
    gt = _write(tmp_path, "gt.json", _gt([
        _e(100, "dig", "A"), _e(200, "set", None)]))
    pred = _write(tmp_path, "pred.json", _pred([
        _a(101, "set", "B"),     # both wrong
        _a(201, "set", "B"),     # GT team null -> team not scored -> correct
    ]))
    lab = outcome_labels(gt, pred)
    assert lab[101]["outcome"] == "wrong_label_and_team"
    assert lab[201]["outcome"] == CORRECT


def test_outcome_duplicate_and_fps_tolerance(tmp_path):
    # 15 fps: 0.2 s base tolerance = 3 frames; both preds match f100's window
    gt = _write(tmp_path, "gt.json", _gt([_e(100, "dig", "A")], fps=15.0))
    pred = _write(tmp_path, "pred.json", _pred([
        _a(100, "dig", "A"), _a(102, "dig", "A")], fps=15.0))
    lab = outcome_labels(gt, pred)
    assert lab[100]["outcome"] == CORRECT
    assert lab[102]["outcome"] == "duplicate"
    assert lab[102]["gt_frame"] == 100


def test_outcome_fp_in_point_vs_dead_time(tmp_path):
    points = [{"clip_start_frame": 100, "clip_end_frame": 300}]
    gt = _write(tmp_path, "gt.json", _gt([_e(150, "dig", "A")], points=points))
    pred = _write(tmp_path, "pred.json", _pred([
        _a(152, "dig", "A"),   # correct
        _a(200, "dig", "A"),   # unmatched, inside GT point -> fp_in_point
        _a(900, "dig", "A"),   # unmatched, outside -> fp_dead_time
    ]))
    lab = outcome_labels(gt, pred)
    assert lab[152]["outcome"] == CORRECT
    assert lab[200]["outcome"] == "fp_in_point"
    assert lab[900]["outcome"] == "fp_dead_time"


def test_outcome_uses_gt_frame_tolerance(tmp_path):
    # coarse GT tolerance (25f @ 25fps = 1 s) pulls the pred into the match
    gt = _write(tmp_path, "gt.json", _gt([_e(100, "dig", "A", tol=25)]))
    pred = _write(tmp_path, "pred.json", _pred([_a(115, "dig", "A")]))
    lab = outcome_labels(gt, pred)
    assert lab[115]["outcome"] == CORRECT
    assert lab[115]["delta_frames"] == 15


# ---------------------------------------------------------------- features --

def _rec(frame, dets=None, track=None, players=None, candidates=None):
    rec = {"frame": frame}
    if dets is not None:
        rec["ball_dets"] = dets
    if track is not None:
        rec["ball_track"] = track
    if players is not None:
        rec["players"] = players
    if candidates is not None:
        rec["candidates"] = candidates
    return rec


def test_point_bbox_distance_mirrors_classifier_metric():
    # inside -> 0; outside -> axis distance; matches _point_to_bbox_distance
    bbox = [100, 100, 200, 200]
    assert _point_bbox_distance([150, 150], bbox, [0, 0]) == 0.0
    assert _point_bbox_distance([230, 150], bbox, [0, 0]) == pytest.approx(30.0)
    assert _point_bbox_distance([230, 240], bbox, [0, 0]) == pytest.approx(50.0)
    assert _point_bbox_distance([150, 150], None, [150, 180]) == pytest.approx(30.0)


def test_nearest_ball_det_prefers_closest_frame_and_ignores_removed():
    frames = {
        100: _rec(100, dets=[{"center": [1, 1], "conf": 0.9, "bbox": [0, 0, 20, 20],
                              "removed": True}]),
        103: _rec(103, dets=[{"center": [5, 5], "conf": 0.4, "bbox": [0, 0, 30, 30],
                              "removed": False}]),
    }
    det, off = _nearest_ball_det(frames, 100)
    assert det["conf"] == 0.4 and off == 3


def test_track_continuity_fraction_and_max_missing_run():
    frames = {}
    states = ["tracked"] * 5 + ["predicted"] * 2 + ["tracked"] * 10 + \
             ["predicted"] * 4 + ["tracked"] * 9 + ["none"]
    for i, s in enumerate(states):
        frames[100 - 15 + i] = _rec(100 - 15 + i, track={"state": s})
    frac, longest = _track_continuity(frames, 100)
    # 31 window frames, 24 tracked (state == 'tracked' only)
    assert frac == pytest.approx(24 / 31)
    assert longest == 4  # the 'predicted' run of 4
    # frames absent from the dump are not counted
    frac2, longest2 = _track_continuity({100: _rec(100, track={"state": "tracked"})}, 100)
    assert frac2 == 1.0 and longest2 == 0


def test_ball_speeds_from_consecutive_track_centres():
    frames = {}
    for i in range(-8, 9):
        x = 500 + 4 * i          # 4 px/f to the right, every frame
        frames[100 + i] = _rec(100 + i, track={"state": "tracked", "center": [x, 400]})
    vin, vout = _ball_speeds(frames, 100)
    assert vin == pytest.approx(4.0)
    assert vout == pytest.approx(4.0)
    # a gap: consecutive pairs only
    del frames[101]
    vin2, vout2 = _ball_speeds(frames, 100)
    assert vin2 == pytest.approx(4.0)
    assert vout2 == pytest.approx(4.0)


def test_ball_speeds_out_window_is_contact_delay_causal():
    # the out window must equal ActionClassifier.CONTACT_DELAY (read from the
    # classifier code, never hard-coded): the classifier confirms a contact
    # at contact_frame + CONTACT_DELAY, so ball_speed_out_* only consumes
    # frames already seen at confirmation time (causal emission-time signal).
    assert SPEED_F == ActionClassifier.CONTACT_DELAY


def test_ball_speed_bw_f_scale_invariant_none_without_width_or_speed():
    def mk(width_px, step_px=4):
        frames = {}
        for i in range(-8, 9):
            x = 500 + step_px * i   # step_px px/f to the right, every frame
            frames[100 + i] = _rec(100 + i, track={"state": "tracked",
                                                   "center": [x, 400]})
        if width_px is not None:
            h = width_px / 2
            frames[100]["ball_dets"] = [
                {"center": [500, 400], "conf": 0.8,
                 "bbox": [500 - h, 400 - h, 500 + h, 400 + h], "removed": False}]
        return frames

    action = _a(100, "dig", "A")
    near = extract_features(mk(40, step_px=8), action, [action], [], None)
    far = extract_features(mk(20, step_px=4), action, [action], [], None)
    # near moves 2x the pixels AND is 2x as wide -> identical bw/f
    assert near["ball_width_px"] == 40.0 and far["ball_width_px"] == 20.0
    assert near["ball_speed_out_px_f"] == pytest.approx(
        2 * far["ball_speed_out_px_f"])
    assert near["ball_speed_out_bw_f"] == pytest.approx(8.0 / 40)
    assert near["ball_speed_out_bw_f"] == pytest.approx(far["ball_speed_out_bw_f"])
    assert near["ball_speed_in_bw_f"] == pytest.approx(far["ball_speed_in_bw_f"])
    # missing width -> bw/f is None even though px/f exists
    nowidth = extract_features(mk(None), action, [action], [], None)
    assert nowidth["ball_speed_out_px_f"] == pytest.approx(4.0)
    assert nowidth["ball_speed_in_bw_f"] is None
    assert nowidth["ball_speed_out_bw_f"] is None
    # missing speed (single frame) -> both forms None
    only = extract_features({100: _rec(100, track={"state": "tracked",
                                                   "center": [1.0, 1.0]})},
                            action, [action], [], None)
    assert only["ball_speed_out_px_f"] is None
    assert only["ball_speed_out_bw_f"] is None


def test_applicable_reach_serve_branch_uses_wider_gate():
    assert _applicable_reach("drive", 100, None) == \
        float(ActionClassifier.SERVE_REACH_PX)
    assert _applicable_reach("drive", 100, 5) == \
        float(ActionClassifier.SERVE_REACH_PX)  # gap > RALLY_RESET_GAP
    assert _applicable_reach("drive", 100, 50) == \
        float(ActionClassifier.CONTACT_REACH)
    assert _applicable_reach("bounce", 100, None) == \
        float(ActionClassifier.CONTACT_REACH)


def _feature_frames():
    frames = {}
    for i in range(-15, 16):
        f = 200 + i
        frames[f] = _rec(f, track={"state": "tracked", "center": [400 + 3 * i, 300],
                                   "conf": 0.5})
    frames[200]["ball_dets"] = [
        {"center": [400, 300], "conf": 0.66, "bbox": [392, 292, 408, 308],
         "removed": False}]
    frames[200]["players"] = [
        {"track_id": 1, "bbox": [500, 200, 600, 400], "center": [550, 300]},
        {"track_id": 2, "bbox": [700, 200, 800, 400], "center": [750, 300]},
    ]
    frames[200]["candidates"] = [
        {"stage": "accepted", "frame": 200, "action": "dig", "gesture": "bump_set",
         "kind": "drive", "attribution_source": "width", "near_net": True,
         "ball_side": "near", "confidence": 0.55},
        {"stage": "candidate_passed_gates", "frame": 200, "gesture_confidence": 0.6,
         "behind_baseline": False, "near_net": True,
         "contact_point": [420.0, 300.0]},
    ]
    # rejections inside the window, and one outside it
    frames[195]["candidates"] = [{"stage": "rejected", "frame": 195,
                                  "reason": "min_contact_gap"}]
    frames[192]["candidates"] = [{"stage": "rejected", "frame": 192,
                                  "reason": "min_contact_gap"}]
    frames[210]["candidates"] = [{"stage": "rejected", "frame": 210,
                                  "reason": "reach", "distance": 180.0,
                                  "reach": 140}]
    frames[180] = _rec(180, candidates=[{"stage": "rejected", "frame": 180,
                                          "reason": "reach"}])  # outside +/- 15f
    return frames


def test_extract_features_reads_diag_and_pipeline_values():
    frames = _feature_frames()
    action = _a(200, "dig", "A")
    action["contact_point"] = [420.0, 300.0]
    feats = extract_features(frames, action, [action], [(100.0, 250.0)],
                             prev_accepted_frame=5)
    assert feats["action"] == "dig"
    assert feats["gesture"] == "bump_set"
    assert feats["gesture_confidence"] == 0.6
    assert feats["resolver_confidence"] == 0.55
    assert feats["contact_kind"] == "drive"
    assert feats["attribution_source"] == "width"
    assert feats["near_net"] is True and feats["behind_baseline"] is False
    assert feats["ball_side"] == "near"
    assert feats["ball_width_px"] == 16.0          # 408 - 392
    assert feats["ball_det_conf"] == 0.66
    assert feats["ball_det_frame_offset"] == 0
    assert feats["track_frac_15f"] == 1.0
    assert feats["max_missing_run_15f"] == 0
    assert feats["ball_speed_in_px_f"] == pytest.approx(3.0)
    assert feats["ball_speed_out_px_f"] == pytest.approx(3.0)
    assert feats["ball_speed_in_bw_f"] == pytest.approx(3.0 / 16.0, abs=1e-3)
    assert feats["ball_speed_out_bw_f"] == pytest.approx(3.0 / 16.0, abs=1e-3)
    # player 1's bbox starts at x=500, contact at x=420 -> 80 px
    assert feats["actor_distance_px"] == 80.0
    assert feats["reach_gate_px"] == float(ActionClassifier.SERVE_REACH_PX)
    assert feats["reach_margin_px"] == pytest.approx(
        80.0 - float(ActionClassifier.SERVE_REACH_PX))
    assert feats["players_within_reach"] == 1     # only player 1 within 160 px
    assert feats["n_min_contact_gap_rejects_15f"] == 2
    assert feats["n_reach_rejects_15f"] == 1      # f210 inside, f180 outside
    assert feats["frames_since_prev_action"] is None  # first action
    assert feats["in_point_pred"] is True


def test_extract_features_frames_since_prev_and_out_of_point():
    frames = _feature_frames()
    a1, a2 = _a(150, "dig", "A"), _a(200, "dig", "A")
    feats = extract_features(frames, a2, [a1, a2], [(100.0, 175.0)],
                             prev_accepted_frame=150)
    assert feats["frames_since_prev_action"] == 50
    assert feats["in_point_pred"] is False


def test_extract_features_no_evidence_is_unavailable_not_invented():
    feats = extract_features({200: _rec(200)}, _a(200, "dig", "A"), [_a(200, "dig", "A")],
                             [], None)
    assert feats["ball_width_px"] is None
    assert feats["ball_det_conf"] is None
    assert feats["ball_det_frame_offset"] is None
    assert feats["track_frac_15f"] is None
    assert feats["ball_speed_in_px_f"] is None
    assert feats["actor_distance_px"] is None
    assert feats["players_within_reach"] is None


# ---------------------------------------------------------------- analysis --

def _row(clip, outcome, **feat):
    base = {k: None for k in (
        "action", "gesture", "gesture_confidence", "resolver_confidence",
        "contact_kind", "touch_number", "attribution_source", "near_net",
        "behind_baseline", "ball_side", "ball_width_px", "ball_det_conf",
        "ball_det_frame_offset", "ball_track_conf", "track_frac_15f",
        "max_missing_run_15f", "ball_speed_in_px_f", "ball_speed_out_px_f",
        "ball_speed_in_bw_f", "ball_speed_out_bw_f",
        "actor_distance_px", "reach_gate_px", "reach_margin_px",
        "players_within_reach", "n_min_contact_gap_rejects_15f",
        "n_reach_rejects_15f", "frames_since_prev_action", "in_point_pred")}
    base.update(feat)
    return {"clip": clip, "frame": 1, "outcome": outcome, "features": base}


def test_precision_table_bins_and_counts():
    rows = [
        _row("x", CORRECT, ball_width_px=15.0),
        _row("x", "fp_in_point", ball_width_px=22.0),
        _row("x", CORRECT, ball_width_px=40.0),
        _row("x", "wrong_label", ball_width_px=None),
    ]
    tbl = precision_table(rows, "ball_width_px")
    assert tbl["<20"] == {"n": 1, "correct": 1, "frac_correct": 1.0}
    assert tbl["20-26"] == {"n": 1, "correct": 0, "frac_correct": 0.0}
    assert tbl["35-45"]["n"] == 1
    assert tbl["unavailable"]["n"] == 1
    assert set(tbl) <= {"<20", "20-26", "26-35", "35-45", ">=45", "unavailable"}


def test_bin_label_touch_number_and_first():
    assert _bin_label("touch_number", 2) == "2"
    assert _bin_label("touch_number", 5) == "3+"
    assert _bin_label("frames_since_prev_action", None) == "first"
    assert _bin_label("near_net", True) == "True"


def test_best_split_categorical_and_numeric():
    rows = ([_row("x", CORRECT, contact_kind="redirect")] * 3
            + [_row("x", "fp_in_point", contact_kind="drive")] * 5)
    bs = best_split(rows, "contact_kind")
    assert bs["split"] == "!= drive"
    assert bs["accuracy"] == pytest.approx(8 / 8)
    assert bs["correct_kept"] == 3 and bs["correct_dropped"] == 0

    rows = ([_row("x", CORRECT, ball_det_conf=0.9)] * 2
            + [_row("x", "fp_in_point", ball_det_conf=0.1)] * 2)
    bs = best_split(rows, "ball_det_conf")
    assert bs["split"].startswith("> ")
    assert bs["accuracy"] == pytest.approx(1.0)
    # majority baseline when the feature carries no signal
    rows = [_row("x", CORRECT, ball_det_conf=0.9), _row("x", CORRECT, ball_det_conf=0.1)]
    bs = best_split(rows, "ball_det_conf")
    assert bs["baseline_accuracy"] == pytest.approx(1.0)


def test_outcome_counts_and_calibration():
    rows = [
        _row("a", CORRECT, resolver_confidence=0.55),
        _row("a", "wrong_label", resolver_confidence=0.55),
        _row("b", "fp_in_point", resolver_confidence=0.6),
        _row("b", CORRECT, resolver_confidence=0.6),
        _row("b", CORRECT, resolver_confidence=0.6),
    ]
    oc = outcome_counts(rows)
    assert oc["total"][CORRECT] == 3
    assert oc["per_clip"]["b"]["fp_in_point"] == 1
    assert oc["total_n"] == 5
    cal = calibration_check(rows)
    assert cal["0.55"] == {"n": 2, "correct": 1, "frac_correct": 0.5}
    assert cal["0.6"] == {"n": 3, "correct": 2, "frac_correct": pytest.approx(0.667)}


def test_build_rows_end_to_end_synthetic(tmp_path):
    # one tiny clip: diag + predictions + GT, wired through build_rows
    gt = _write(tmp_path, "gt.json", _gt([_e(200, "dig", "A"),
                                          _e(400, "set", "B", tol=25)]))
    frames = _feature_frames()
    frames[400] = _rec(400, track={"state": "tracked", "center": [1.0, 1.0]},
                       candidates=[{"stage": "accepted", "frame": 400,
                                    "action": "serve", "gesture": "bump_set",
                                    "kind": "redirect", "near_net": False}])
    diag_lines = ([json.dumps({"meta": {"schema_version": 1,
                                       "kind": "volley_recognition_diag_dump",
                                       "fps": 25.0, "total_frames": 500}})]
                 + [json.dumps(frames[f]) for f in sorted(frames)])
    diag = str(tmp_path / "diag.jsonl")
    Path(diag).write_text("\n".join(diag_lines))
    pred_blob = {"video": {"fps": 25.0},
                 "actions": [_a(200, "dig", "A"), _a(402, "spike", "B")],
                 "game_state": {"points": [{"start_frame": 100, "end_frame": 450}]}}
    pred = _write(tmp_path, "pred.json", pred_blob)
    rows = build_rows([{"name": "synth", "diag": diag, "predictions": pred,
                        "ground_truth": gt}])
    by_frame = {r["frame"]: r for r in rows}
    assert by_frame[200]["outcome"] == CORRECT
    assert by_frame[200]["features"]["ball_width_px"] == 16.0
    assert by_frame[200]["features"]["in_point_pred"] is True
    assert by_frame[402]["outcome"] == "wrong_label"   # inside tol=25f of GT 400
    assert by_frame[402]["gt_frame"] == 400
    # sparse window: absent frames are not counted, the one present frame is tracked
    assert by_frame[402]["features"]["track_frac_15f"] == 1.0


def test_outcome_order_is_total():
    assert OUTCOME_ORDER[0] == CORRECT and len(OUTCOME_ORDER) == 7


def test_per_clip_split_consistency_suspect_worse_semantics():
    rows = [
        # clip a: the suspect set (x < 10) is strictly worse
        _row("a", CORRECT, ball_speed_out_px_f=50.0),
        _row("a", CORRECT, ball_speed_out_px_f=50.0),
        _row("a", "fp_in_point", ball_speed_out_px_f=5.0),
        # clip b: suspect set empty -> frac None, not 'worse'
        _row("b", CORRECT, ball_speed_out_px_f=50.0),
    ]
    out = per_clip_split_consistency(
        rows, "speed_out < 10",
        lambda f: f["ball_speed_out_px_f"] is not None and f["ball_speed_out_px_f"] < 10)
    assert out["label"] == "speed_out < 10"
    by_clip = {c["clip"]: c for c in out["clips"]}
    assert by_clip["a"]["suspect_n"] == 1
    assert by_clip["a"]["suspect_frac_correct"] == 0.0
    assert by_clip["a"]["rest_frac_correct"] == 1.0
    assert by_clip["a"]["suspect_worse"] is True
    assert by_clip["b"]["suspect_frac_correct"] is None
    assert by_clip["b"]["suspect_worse"] is False
