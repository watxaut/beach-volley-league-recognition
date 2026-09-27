"""Unit tests for the pose gating levers (perf, adopted 2026-09-27).

What is being protected:
- LEVER 1 (staleness): once the ball has been untracked for more than
  ``pose_gate_stale_frames`` (30 = REENTRY_MAX_GAP), no contact can consume
  pose, so the MediaPipe call is skipped -- but a history entry is STILL
  appended for every observed player (snapshot selection / L-R index /
  takeoff-stance reads use center+bbox+team only and must not move).
- LEVER 2 (near-ball radius): when the ball is tracked, only players within
  ``pose_near_ball_radius_px`` of a ball point in the last POSE_TRAIL_WINDOW
  frames are posed; the trail (not just the current point) is load-bearing
  because the consuming snapshot can sit a few frames off the contact vertex.
- OCCLUSION FALLBACK: a ball lost 1..30 frames ago (in-rally gap) still poses
  everyone -- bridge contacts fire at the first re-sighting and may consume a
  snapshot from inside the gap.
- Disabling both gates (0/0) restores unconditional pose.

The measured design bound (see the POSE_TRAIL_WINDOW block in
action_classifier.py): every pose-consuming snapshot on the 7 entrenos + a
match slice sits within 155 px of a last-9-frames ball point -> 300 px radius.
"""

from pathlib import Path

import pytest

from src.detection.court_calibration import CourtCalibration
from src.recognition.action_classifier import ActionClassifier

COURT_JSON = Path(__file__).resolve().parent.parent / "calibrations" / "video_entreno_3.json"


class _CountingPose:
    """Counts estimate_pose calls; returns a minimal hands-overhead pose."""

    def __init__(self):
        self.calls = 0

    def estimate_pose(self, frame, bbox):
        self.calls += 1
        return {"pose_features": {"avg_wrist_height_ratio": 1.5}}

    def estimate_poses_batch(self, frame, detections):
        return [self.estimate_pose(frame, d.get("bbox", [])) for d in detections]


def _det(tid, bbox, team="A"):
    x1, y1, x2, y2 = bbox
    return {
        "track_id": tid,
        "bbox": list(bbox),
        "center": [(x1 + x2) / 2, (y1 + y2) / 2],
        "team": team,
        "predicted": False,
    }


def _ball_info(x, y, w=30):
    return {
        "center": [x, y],
        "bbox": [x - w / 2, y - w / 2, x + w / 2, y + w / 2],
        "is_predicted": False,
    }


@pytest.fixture()
def clf():
    court = CourtCalibration(str(COURT_JSON))
    pose = _CountingPose()
    clf = ActionClassifier(
        pose_estimator=pose,
        confidence_threshold=0.3,
        court_calibration=court,
    )
    clf._pose = pose
    return clf


# --- LEVER 1: staleness ---

def test_dead_ball_skips_pose_but_appends_entry(clf):
    # Ball last seen at f100; classify at f131 -> stale 31 > 30.
    for f in range(90, 101):
        clf._ball_history.append((f, 900.0, 500.0, 30.0, 30.0))
    det = _det(1, (860, 700, 940, 880))
    clf.classify_actions(None, [det], None, frame_number=131)
    assert clf._pose.calls == 0
    assert clf.pose_gate_stats["skipped_stale"] == 1
    # History entry still appended (snapshot selection must not move).
    hist = clf._player_pose_history[1]
    assert len(hist) == 1
    entry = hist[0]
    assert entry["frame"] == 131 and entry["pose"] is None
    assert entry["bbox"] == det["bbox"] and entry["team"] == "A"


def test_no_ball_ever_seen_skips_pose(clf):
    det = _det(1, (860, 700, 940, 880))
    clf.classify_actions(None, [det], None, frame_number=50)
    assert clf._pose.calls == 0
    assert len(clf._player_pose_history[1]) == 1


def test_stale_gate_boundary_30_frames(clf):
    # stale == 30 exactly: still the occlusion window -> pose everyone.
    clf._ball_history.append((100, 900.0, 500.0, 30.0, 30.0))
    clf.classify_actions(None, [_det(1, (860, 700, 940, 880))], None, frame_number=130)
    assert clf._pose.calls == 1
    # stale == 31: dead -> skip.
    clf._ball_history.clear()
    clf._ball_history.append((100, 900.0, 500.0, 30.0, 30.0))
    clf.pose_gate_stats = {"posed": 0, "skipped_stale": 0, "skipped_radius": 0}
    clf.classify_actions(None, [_det(1, (860, 700, 940, 880))], None, frame_number=131)
    assert clf._pose.calls == 1  # unchanged


# --- OCCLUSION FALLBACK ---

def test_occlusion_window_poses_everyone(clf):
    # Ball lost 5 frames ago (in-rally gap): even a far player is posed.
    clf._ball_history.append((95, 900.0, 500.0, 30.0, 30.0))
    far = _det(1, (100, 100, 200, 300))
    near = _det(2, (860, 700, 940, 880))
    clf.classify_actions(None, [far, near], None, frame_number=100)
    assert clf._pose.calls == 2
    assert clf.pose_gate_stats["skipped_radius"] == 0


# --- LEVER 2: near-ball radius ---

def test_radius_poses_only_near_players(clf):
    near = _det(1, (860, 700, 940, 880))     # ~0 px from ball (900,790)
    far = _det(2, (100, 100, 200, 300))      # ~800 px away
    clf.classify_actions(None, [near, far], _ball_info(900, 790), frame_number=100)
    assert clf._pose.calls == 1
    assert clf.pose_gate_stats["skipped_radius"] == 1
    # Both players still got history entries.
    assert len(clf._player_pose_history[1]) == 1
    assert len(clf._player_pose_history[2]) == 1
    assert clf._player_pose_history[2][0]["pose"] is None
    assert clf._player_pose_history[1][0]["pose"] is not None


def test_radius_keys_on_ball_trail_not_just_current_point(clf):
    # Player 900 px from the CURRENT ball point but 120 px from the point
    # seen 5 frames ago: must still be posed (the consuming snapshot can sit
    # a few frames off the contact vertex -- measured max offset 3 frames).
    for f in range(96, 101):
        clf._ball_history.append((f, 100.0 + 160 * (f - 96), 500.0, 30.0, 30.0))
    # Trail points: (100,500),(260,500),(420,500),(580,500),(740,500); the
    # classify frame appends (900,500) via ball_info -> trail max is (740,500).
    player = _det(1, (700, 460, 860, 640))   # ~0 px from (740..900? bbox covers)
    clf.classify_actions(None, [player], _ball_info(900, 500), frame_number=101)
    # Trail for f=101 spans [92,101]: includes (740,500) and (900,500);
    # the bbox edge is at x=860 -> distance to (740,500) is 0 -> posed.
    assert clf._pose.calls == 1


def test_radius_ignores_ball_points_older_than_trail_window(clf):
    # Ball point 12 frames ago near the player, current ball far away: NOT
    # posed (POSE_TRAIL_WINDOW == NEIGH+2 == 9).
    clf._ball_history.append((88, 800.0, 500.0, 30.0, 30.0))
    player = _det(1, (760, 460, 880, 640))   # ~0 px from the OLD point
    clf.classify_actions(None, [player], _ball_info(1600, 500), frame_number=100)
    assert clf._pose.calls == 0
    assert clf.pose_gate_stats["skipped_radius"] == 1


# --- Gate disabled -> legacy behavior ---

def test_disabled_gates_pose_everyone(clf):
    clf = ActionClassifier(
        pose_estimator=_CountingPose(),
        confidence_threshold=0.3,
        court_calibration=CourtCalibration(str(COURT_JSON)),
        pose_gate_stale_frames=0,
        pose_near_ball_radius_px=0,
    )
    pose = clf.pose_estimator
    # Dead ball AND far player: still posed (legacy).
    clf._ball_history.append((50, 900.0, 500.0, 30.0, 30.0))
    clf.classify_actions(None, [_det(1, (100, 100, 200, 300))], None, frame_number=500)
    assert pose.calls == 1


def test_gate_counters_reset(clf):
    clf._ball_history.append((50, 900.0, 500.0, 30.0, 30.0))
    clf.classify_actions(None, [_det(1, (860, 700, 940, 880))], None, frame_number=200)
    assert clf.pose_gate_stats["skipped_stale"] == 1
    clf.reset()
    assert clf.pose_gate_stats == {"posed": 0, "skipped_stale": 0, "skipped_radius": 0}
