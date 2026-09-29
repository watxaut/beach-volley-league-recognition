"""Unit tests for scripts/evaluate_timed.py (task T3, time-matched evaluator)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import evaluate_timed as et  # noqa: E402


def ev(frame, action="dig", team="A", player_id=1, **extra):
    e = {"frame": frame, "action": action, "team": team, "player_id": player_id}
    e.update(extra)
    return et.normalize_event(e)


def tb(fps=30.0, pts=None):
    return et.TimeBase(fps, pts)


# --- one-to-one matching ----------------------------------------------------

def test_one_to_one_matching_two_gt_one_pred():
    """Two GT events 2f apart, ONE prediction between them: only one may match."""
    gts = [ev(100), ev(102)]
    preds = [ev(101)]
    m = et.match_events(gts, preds, tb(), 0.2)
    assert len(m["pairs"]) == 1
    assert len(m["unmatched_gt"]) == 1
    assert m["unmatched_pred"] == []


def test_optimal_assignment_beats_greedy():
    """Predictions A=[t0+0.1, t1+0.1] with a pred between: the OPTIMAL total
    distance is picked (greedy-nearest-first would strand the far event)."""
    #  GT: 100 and 200 ; preds: 106, 196  -> both match (dist 6f/4f)
    m = et.match_events([ev(100), ev(200)], [ev(196), ev(106)], tb(), 0.2)
    assert len(m["pairs"]) == 2
    # each pred is paired with its own nearest GT, not crossed
    assert [p[0]["frame"] for p in m["pairs"]] == [100, 200]
    assert [p[1]["frame"] for p in m["pairs"]] == [106, 196]


def test_class_agnostic_contact_counts_label_mistake_as_a_hit():
    gts = [ev(100, "spike")]
    preds = [ev(100, "dig")]
    m = et.match_events(gts, preds, tb(), 0.2)
    c = et.score_contacts(m)
    assert c["tp"] == 1 and c["fp"] == 0 and c["fn"] == 0
    assert c["f1"] == 1.0
    assert et.score_labels(m)["class_accuracy"] == 0.0


# --- tolerance edge ---------------------------------------------------------

def test_tolerance_edge_inclusive_and_exclusive():
    # 0.2 s @ 30 fps = 6 frames exactly -> inclusive
    m = et.match_events([ev(100)], [ev(106)], tb(30.0), 0.2)
    assert len(m["pairs"]) == 1
    # 7 frames = 0.2333 s -> outside
    m = et.match_events([ev(100)], [ev(107)], tb(30.0), 0.2)
    assert m["pairs"] == [] and len(m["unmatched_pred"]) == 1


def test_tolerance_s_scales_with_fps_not_frames():
    """A 12-frame gap is 0.4 s at 30 fps (OUTSIDE 0.2 s) but 0.2 s at 60 fps
    (INSIDE) -- tolerance is a TIME, not a frame count (VFR-safe)."""
    assert et.match_events([ev(100)], [ev(112)], tb(30.0), 0.2)["pairs"] == []
    assert len(et.match_events([ev(100)], [ev(112)], tb(60.0), 0.2)["pairs"]) == 1


def test_pts_timebase_is_used_over_frame_fps():
    """VFR: PTS says frame 100 is at 1.0 s and 106 at 1.2 s -> inside 0.2 s
    even though frame/fps@30 would also say 0.2; make the gap 10 frames where
    the two models disagree."""
    pts = [i / 100.0 for i in range(400)]  # 100 fps container
    t_pts = et.TimeBase(30.0, pts)          # nominal fps deliberately wrong
    t_fps = et.TimeBase(30.0)
    assert t_pts.source == "pts"
    # 10 frames = 0.1 s at 100 fps (PTS) but 0.333 s at 30 fps (frame/fps)
    assert len(et.match_events([ev(100)], [ev(110)], t_pts, 0.2)["pairs"]) == 1
    assert et.match_events([ev(100)], [ev(110)], t_fps, 0.2)["pairs"] == []
    assert t_pts.t(100) == pytest.approx(1.0)
    assert t_pts.t(105) == pytest.approx(1.05)  # interpolated, VFR-aware


# --- per-event GT tolerance -------------------------------------------------

def test_per_event_frame_tolerance_widens_the_window():
    """Coarse owner GT (frame_tolerance 15 @30 fps = 0.5 s) beats the 0.2 s base."""
    # 13 frames = 0.4333 s away: outside the 0.2 s base, inside 15f/fps = 0.5 s
    m2 = et.match_events([ev(100, frame_tolerance=15)], [ev(113)], tb(30.0), 0.2)
    assert len(m2["pairs"]) == 1  # per-event max() lifts the base
    # ...and a tighter per-event tolerance cannot NARROW below the base
    m3 = et.match_events([ev(100, frame_tolerance=1)], [ev(120)], tb(30.0), 0.2)
    assert m3["pairs"] == []


# --- duplicates -------------------------------------------------------------

def test_duplicate_prediction_is_flagged_not_double_counted():
    """A second prediction next to an already-matched GT event = duplicate."""
    gts = [ev(100)]
    preds = [ev(101), ev(103)]  # both inside 0.2 s of the SAME GT event
    m = et.match_events(gts, preds, tb(), 0.2)
    c = et.score_contacts(m)
    assert len(m["pairs"]) == 1
    assert len(m["unmatched_pred"]) == 1
    assert len(m["duplicates"]) == 1
    assert c["duplicates"] == 1
    assert c["fp"] == 1 and c["fp_excluding_duplicates"] == 0
    assert m["duplicates"][0]["gt_frame"] == 100


def test_extra_prediction_far_away_is_a_plain_false_positive():
    m = et.match_events([ev(100)], [ev(101), ev(400)], tb(), 0.2)
    c = et.score_contacts(m)
    assert c["duplicates"] == 0
    assert c["fp"] == 1 and c["fp_excluding_duplicates"] == 1


# --- confusion matrix / attribution -----------------------------------------

def test_confusion_matrix_and_attribution():
    gts = [ev(100, "spike", team="A", player_id=1),
           ev(200, "set", team="B", player_id=2)]
    preds = [ev(101, "dig", team="A", player_id=1),
             ev(199, "set", team="A", player_id=3)]
    m = et.match_events(gts, preds, tb(), 0.2)
    lab = et.score_labels(m)
    assert lab["class_accuracy"] == 0.5 and lab["class_scored"] == 2
    assert lab["confusion_matrix"] == {"spike": {"dig": 1}, "set": {"set": 1}}
    at = et.score_attribution(m, ignore_player=False)
    assert at["team_accuracy"] == 0.5 and at["team_scored"] == 2
    assert at["actor_accuracy"] == 0.5 and at["actor_scored"] == 2
    at_ig = et.score_attribution(m, ignore_player=True)
    assert at_ig["actor_accuracy"] is None and "ignore-player" in at_ig["actor_scoring"]


def test_actor_accuracy_na_when_gt_player_id_null():
    gts = [et.normalize_event({"frame": 100, "final_action": "dig", "player_id": None,
                               "player_team": "A"})]
    preds = [ev(100, "dig", "A", player_id=2)]
    m = et.match_events(gts, preds, tb(), 0.2)
    at = et.score_attribution(m, ignore_player=False)
    assert at["actor_scored"] == 0 and at["actor_accuracy"] is None


# --- dead time + point IoU --------------------------------------------------

def test_fp_per_dead_time_minute():
    """GT point spans 0-10 s of a 60 s clip: 59 dead seconds."""
    gt_iv = [(0, 250)]  # 10 s of play at 25 fps
    m = et.match_events([ev(0, "serve")], [ev(0, "serve"), ev(30 * 25, "dig")],
                        tb(25.0), 0.2)
    dt = et.dead_time_score(m, gt_iv, 60.0, tb(25.0))
    assert dt["available"] and dt["dead_minutes"] == pytest.approx(50 / 60, abs=1e-3)
    assert dt["fp_in_dead_time"] == 1
    assert dt["fp_per_dead_minute"] == pytest.approx(1 / (50 / 60), abs=0.01)


def test_fp_inside_a_point_is_not_dead_time():
    m = et.match_events([ev(0, "serve")], [ev(0, "serve"), ev(100, "dig")], tb(25.0), 0.2)
    dt = et.dead_time_score(m, [(0, 1500)], 60.0, tb(25.0))  # point covers the clip
    assert dt["fp_in_dead_time"] == 0
    assert dt["dead_minutes"] == 0.0


def test_dead_time_unavailable_without_gt_intervals():
    dt = et.dead_time_score({"unmatched_pred": []}, [], 60.0, tb(30.0))
    assert dt["available"] is False and "no GT point" in dt["reason"]


def test_point_interval_iou_matching_matched_missed_spurious():
    gt_iv = [(0, 100), (200, 300), (400, 500)]
    pred_iv = [(0, 90), (205, 295), (900, 950)]   # 2 match, 1 spurious
    s = et.score_points(gt_iv, pred_iv, tb(30.0))
    assert (s["matched"], s["missed"], s["spurious"]) == (2, 1, 1)
    assert 0.7 < s["mean_iou"] < 0.95


def test_point_iou_is_one_to_one():
    """Two predicted windows overlapping one GT point: only one may match."""
    s = et.score_points([(0, 100)], [(0, 100), (10, 110)], tb(30.0))
    assert (s["matched"], s["missed"], s["spurious"]) == (1, 0, 1)


def test_temporal_iou_values():
    assert et.temporal_iou((0, 10), (0, 10)) == pytest.approx(1.0)
    assert et.temporal_iou((0, 10), (20, 30)) == 0.0
    assert et.temporal_iou((0, 10), (5, 15)) == pytest.approx(5 / 15)


def test_point_intervals_extracted_from_game_state_and_clip_frames():
    assert et.point_intervals({"game_state": {"points": [{"start_frame": 5,
                                                          "end_frame": 9}]}}) == [(5, 9)]
    assert et.point_intervals({"points": [{"clip_start_frame": 1,
                                           "clip_end_frame": 3}]}) == [(1, 3)]


# --- autonomous guard -------------------------------------------------------

def test_autonomous_refuses_gt_derived_prediction_file():
    blob = {"actions": [{"frame": 10, "action": "serve", "serve_anchor_frame": 9}],
            "points": [{"point": 1, "winner": "B", "start_frame": 5, "end_frame": 20}]}
    findings = et.find_gt_derived_inputs(blob)
    keys = {f["key"] for f in findings}
    assert {"serve_anchor_frame", "winner"} <= keys
    assert "game_state" not in keys  # the key itself is not evidence


def test_autonomous_allows_a_clean_prediction_file():
    blob = {"video": {"fps": 30.0}, "actions": [{"frame": 10, "action": "serve",
                                                 "team": "A", "rally_id": 1}],
            "game_state": {"points": [{"start_frame": 5, "end_frame": 20, "n_actions": 3}]}}
    assert et.find_gt_derived_inputs(blob) == []


def test_autonomous_error_exits_on_real_dev_clip_gt_used_as_predictions(tmp_path):
    gt_path = REPO / "ground_truth" / "video_ari_joan_8_first_points_annotations.json"
    if not gt_path.exists():
        pytest.skip("dev clip GT not present")
    res = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "evaluate_timed.py"),
         "--predictions", str(gt_path), "--ground-truth", str(gt_path),
         "--autonomous", "--ignore-player"],
        capture_output=True, text=True)
    assert res.returncode != 0
    assert "Autonomous mode refused" in (res.stdout + res.stderr)


# --- end-to-end -------------------------------------------------------------

def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj))
    return str(p)


def test_evaluate_timed_end_to_end(tmp_path):
    gt = {
        "video": "x.mp4", "fps": 30.0,
        "annotated_frames": {"actions": {"events": [
            {"frame": 30, "final_action": "serve", "player_id": 1, "player_team": "A"},
            {"frame": 90, "final_action": "dig", "player_id": 2, "player_team": "A",
             "overrides": {"final_action": "spike"}},   # ratified correction merged
            {"frame": 200, "final_action": "set", "player_id": 3, "player_team": "B"},
        ]}},
    }
    pred = [{"frame": 31, "action": "serve", "team": "A", "player_id": 1},
            {"frame": 89, "action": "dig", "team": "B", "player_id": 2},
            {"frame": 201, "action": "set", "team": "B", "player_id": 3},
            {"frame": 500, "action": "dig", "team": "A", "player_id": 1}]
    res = et.evaluate_timed(_write(tmp_path, "p.json", pred), _write(tmp_path, "g.json", gt),
                            ignore_player=False)
    assert res["counts"] == {"gt_events": 3, "pred_events": 4}
    assert res["contact"]["tp"] == 3 and res["contact"]["fp"] == 1
    # the GT override (dig -> spike) is what gets graded
    assert res["labels"]["confusion_matrix"]["spike"] == {"dig": 1}
    assert res["attribution"]["team_accuracy"] == pytest.approx(2 / 3, abs=0.01)
    assert "CONTACT" in et.format_report(res)


def test_evaluate_timed_reports_time_source(tmp_path):
    gt = {"fps": 30.0, "annotated_frames": {"actions": {"events": [
        {"frame": 30, "final_action": "serve"}]}}}
    pred = [{"frame": 30, "action": "serve"}]
    res = et.evaluate_timed(_write(tmp_path, "p.json", pred), _write(tmp_path, "g.json", gt))
    assert res["time"]["source"] == "frame/fps"
    gt_pts = dict(gt, frame_timestamps=[i / 30.0 for i in range(400)])
    res2 = et.evaluate_timed(_write(tmp_path, "p.json", pred),
                             _write(tmp_path, "g.json", gt_pts))
    assert res2["time"]["source"] == "pts"
