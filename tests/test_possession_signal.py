"""Tests for the parked possession-signal harness + probe.

Synthetic inputs only.  Pins the PURE mechanism -- the width trend, the
motion convergence, the tie-break, the harness defaults-OFF guarantee, and the
probe's scoring helpers -- not pipeline behaviour.  The probe itself replays
the committed match dump and writes ``output/possession_signal/`` +
``docs/g3_possession_signal.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from possession_signal_harness import (  # noqa: E402
    MotionTiebreakClassifier,
    PossessionSignalClassifier,
    WidthTrendClassifier,
)
from probe_possession_signal import (  # noqa: E402
    _PrevAction,
    _went_over,
    ball_width,
    load_dump,
    score,
)
from src.detection.court_calibration import CourtCalibration  # noqa: E402
from src.recognition.action_classifier import ActionClassifier  # noqa: E402

COURT_JSON = ROOT / "calibrations" / "video_entreno_3.json"


class _StubPose:
    def estimate_poses_batch(self, frame, detections):
        return [None] * len(detections)

    def estimate_pose(self, frame, bbox):
        return None


@pytest.fixture()
def court():
    c = CourtCalibration(str(COURT_JSON))
    assert c.is_calibrated
    return c


def _trend_clf(court, **kw):
    return WidthTrendClassifier(pose_estimator=_StubPose(),
                                confidence_threshold=0.3,
                                court_calibration=court, **kw)


def _motion_clf(court, **kw):
    return MotionTiebreakClassifier(pose_estimator=_StubPose(),
                                    confidence_threshold=0.3,
                                    court_calibration=court, **kw)


def _ball(clf, points):
    clf._ball_history.clear()
    for f, x, y, w in points:
        clf._ball_history.append((f, x, y, w, w))


def _width_ramp(clf, start, end, lo=85, hi=100):
    n = hi - lo
    k = max(1, n // 3)
    clf._ball_history.clear()
    for i, f in enumerate(range(lo, hi)):
        if i < k:
            w = start
        elif i >= n - k:
            w = end
        else:
            t = (i - k) / max(n - 2 * k, 1)
            w = start + (end - start) * t
        clf._ball_history.append((f, 900.0, 500.0, w, w))


def _snap(clf, tid, frame, bbox, team):
    x1, y1, x2, y2 = bbox
    clf._player_pose_history.setdefault(tid, []).append({
        "frame": frame, "pose": None,
        "center": [(x1 + x2) / 2, (y1 + y2) / 2],
        "bbox": list(bbox), "team": team,
    })


# ------------------------------------------------------- defaults OFF ----

def test_harness_defaults_are_off(court):
    assert _trend_clf(court).width_trend_enabled is False
    assert _motion_clf(court).motion_tiebreak_enabled is False
    both = PossessionSignalClassifier(pose_estimator=_StubPose(),
                                      court_calibration=court)
    assert both.width_trend_enabled is False
    assert both.motion_tiebreak_enabled is False


def test_combined_harness_takes_explicit_flags(court):
    both = PossessionSignalClassifier(pose_estimator=_StubPose(),
                                      court_calibration=court,
                                      width_trend_enabled=True,
                                      motion_tiebreak_enabled=True)
    assert both.width_trend_enabled is True
    assert both.motion_tiebreak_enabled is True


# ------------------------------------------------------- width trend ----

def test_width_trend_growing_is_near(court):
    clf = _trend_clf(court, width_trend_enabled=True)
    _width_ramp(clf, 28.0, 34.8)
    side, dln = clf.width_side_trend(100)
    assert side == "A" and dln > 0.15


def test_width_trend_shrinking_is_far(court):
    clf = _trend_clf(court, width_trend_enabled=True)
    _width_ramp(clf, 34.8, 28.0)
    side, dln = clf.width_side_trend(100)
    assert side == "B" and dln < -0.15


def test_width_trend_flat_and_short_do_not_guess(court):
    clf = _trend_clf(court, width_trend_enabled=True)
    _width_ramp(clf, 30.0, 30.0)
    assert clf.width_side_trend(100)[0] is None
    _ball(clf, [(98, 900, 500, 28), (99, 900, 500, 34)])
    assert clf.width_side_trend(100)[0] is None


def test_width_trend_disabled(court):
    clf = _trend_clf(court, width_trend_enabled=False)
    _width_ramp(clf, 28.0, 34.8)
    assert clf.width_side_trend(100)[0] is None


def test_target_uses_trend_when_strict_abstains(court):
    clf = _trend_clf(court, width_trend_enabled=True)
    _width_ramp(clf, 28.0, 34.8)
    clf._last_touch_team, clf._last_touch_frame = "B", 60
    clf._last_touch_went_over = False
    target, info = clf._attribution_target(100)
    assert target == "A" and info["source"] == "width_trend"


def test_target_strict_width_beats_trend(court):
    clf = _trend_clf(court, width_trend_enabled=True)
    _ball(clf, [(f, 900, 700, 45) for f in range(92, 100)])
    clf._last_touch_team, clf._last_touch_frame = "B", 60
    target, info = clf._attribution_target(100)
    assert target == "A" and info["source"] == "width"


def test_target_without_mechanism_is_production(court):
    clf = _trend_clf(court, width_trend_enabled=False)
    _width_ramp(clf, 28.0, 34.8)
    clf._last_touch_team, clf._last_touch_frame = "B", 60
    clf._last_touch_went_over = False
    target, info = clf._attribution_target(100)
    assert target == "B" and info["source"] == "carry"


# -------------------------------------------------- motion tie-break ----

def test_motion_convergence_signs(court):
    clf = _motion_clf(court, motion_tiebreak_enabled=True)
    point = [900.0, 700.0]
    for f, c in [(94, (800, 600)), (100, (880, 680))]:
        _snap(clf, 1, f, (c[0] - 40, c[1] - 40, c[0] + 40, c[1] + 40), "A")
    conv, speed = clf.motion_convergence(1, 100, point, [880.0, 680.0])
    assert conv > 0.5 and speed > 0
    clf._player_pose_history.clear()
    for f, c in [(94, (980, 780)), (100, (880, 680))]:
        _snap(clf, 2, f, (c[0] - 40, c[1] - 40, c[0] + 40, c[1] + 40), "A")
    conv2, _ = clf.motion_convergence(2, 100, point, [880.0, 680.0])
    assert conv2 < -0.5


def test_motion_convergence_neutral_when_still_or_short(court):
    clf = _motion_clf(court, motion_tiebreak_enabled=True)
    point = [900.0, 700.0]
    _snap(clf, 1, 100, (860, 660, 940, 740), "A")
    assert clf.motion_convergence(1, 100, point, [900.0, 700.0])[0] == 0.0
    for f in (94, 100):
        _snap(clf, 2, f, (820, 620, 900, 700), "A")
    conv, speed = clf.motion_convergence(2, 100, point, [860.0, 660.0])
    assert conv == 0.0 and speed == 0.0


def test_motion_tiebreak_prefers_converging_player(court):
    clf = _motion_clf(court, motion_tiebreak_enabled=True)
    point = [900.0, 700.0]
    for f, c in [(94, (980, 760)), (100, (900, 680))]:     # diverging, cd 20
        _snap(clf, 1, f, (c[0] - 60, c[1] - 60, c[0] + 60, c[1] + 60), "A")
    for f, c in [(94, (1040, 840)), (100, (960, 760))]:    # converging, cd 85
        _snap(clf, 2, f, (c[0] - 60, c[1] - 60, c[0] + 60, c[1] + 60), "A")
    snap, _, _ = clf._closest_player_at(100, point, target_team="A")
    assert snap["track_id"] == 2


def test_motion_tiebreak_leaves_clear_winner(court):
    clf = _motion_clf(court, motion_tiebreak_enabled=True)
    point = [900.0, 700.0]
    _snap(clf, 1, 100, (860, 660, 940, 740), "A")
    _snap(clf, 2, 100, (1120, 920, 1280, 1080), "A")
    snap, dist, _ = clf._closest_player_at(100, point, target_team="A")
    assert snap["track_id"] == 1 and dist == 0.0


def test_motion_tiebreak_disabled_keeps_distance_order(court):
    clf = _motion_clf(court, motion_tiebreak_enabled=False)
    point = [900.0, 700.0]
    for f, c in [(94, (980, 760)), (100, (900, 680))]:
        _snap(clf, 1, f, (c[0] - 60, c[1] - 60, c[0] + 60, c[1] + 60), "A")
    for f, c in [(94, (1040, 840)), (100, (960, 760))]:
        _snap(clf, 2, f, (c[0] - 60, c[1] - 60, c[0] + 60, c[1] + 60), "A")
    snap, _, _ = clf._closest_player_at(100, point, target_team="A")
    assert snap["track_id"] == 1


# ------------------------------------------------------- probe helpers ----

def test_ball_width_matches_tracked_center():
    rec = {"ball_track": {"locked": True, "center": [100.0, 100.0]},
           "ball_dets": [{"center": [100.0, 100.0], "bbox": [85, 90, 115, 110]},
                         {"center": [10.0, 10.0], "bbox": [5, 5, 15, 15]}]}
    assert ball_width(rec) == 30.0


def test_ball_width_none_when_unlocked_or_no_matching_det():
    assert ball_width({"ball_track": {"locked": False, "center": [1, 1]},
                       "ball_dets": []}) is None
    assert ball_width({"ball_track": {"locked": True, "center": [100.0, 100.0]},
                       "ball_dets": [{"center": [10.0, 10.0], "bbox": [0, 0, 9, 9]}]}) is None


def test_load_dump_only_takes_passed_gates(tmp_path):
    dump = tmp_path / "d.jsonl"
    dump.write_text("\n".join([
        '{"meta": {"fps": 30.0}}',
        '{"frame": 10, "candidates": ['
        '{"stage": "candidate_passed_gates", "frame": 9, "kind": "bounce"},'
        '{"stage": "rejected", "frame": 9, "reason": "reach"}]}',
    ]))
    frames, contacts = load_dump(str(dump))
    assert 10 in frames and len(contacts) == 1 and contacts[0]["frame"] == 9


def test_prev_action_and_went_over():
    pa = _PrevAction([{"frame_number": 100, "action": "dig", "gesture": "bump_set"},
                      {"frame_number": 200, "action": "spike", "gesture": "attack"}])
    assert pa.before(150)["frame_number"] == 100
    assert pa.before(50) is None
    assert _went_over(pa.before(150)) is False
    assert _went_over(pa.before(250)) is True
    assert _went_over({"action": "serve", "gesture": "bump_set"}) is True
    assert _went_over(None) is False


def test_score_matches_gt_side_within_tolerance():
    rows = [{"frame": 100, "team": "A", "target": "A", "source": "width",
             "point": 1, "trend_dln": None, "kind": "bounce",
             "prev_action": None, "prev_team": None},
            {"frame": 300, "team": "B", "target": "B", "source": "carry",
             "point": 2, "trend_dln": None, "kind": "bounce",
             "prev_action": None, "prev_team": None},
            {"frame": 500, "team": "A", "target": None, "source": None,
             "point": 3, "trend_dln": None, "kind": "bounce",
             "prev_action": None, "prev_team": None}]
    gt = {102: {"owner_side": "near"}, 300: {"owner_side": "near"}}
    st = score(rows, gt, tol=15)
    assert st["n"] == 2 and st["correct"] == 1
    assert len(st["misses"]) == 1 and st["misses"][0]["want"] == "A"


def test_score_counts_trend_fires_on_correct_side():
    rows = [{"frame": 100, "team": "A", "target": "A", "source": "width_trend",
             "point": 1, "trend_dln": 0.22, "kind": "bounce",
             "prev_action": None, "prev_team": None}]
    gt = {100: {"owner_side": "near", "final_action": "dig"}}
    st = score(rows, gt)
    assert st["trend_fires"][0]["team"] == "A"
