"""Unit tests for team-aware contact attribution (open point 2).

Exercise the attribution machinery in isolation against the REAL entreno_3
calibration geometry (midcourt line (386,592)-(1386,613), so at x=900 the
split is y~601; net top (374,293)-(1363,313)). Ball histories and player
snapshots are injected directly -- no video needed.

What is being protected here (all GT-verified on entreno_3, 2026-08-16):
- adjacent same-line players stole sets/digs when closest-player won
  (f211/f244/f378/f488) -> the team filter must exclude wrong-foot candidates;
- the emitted team is the toucher's per-contact FOOT team, not the resolver's
  latched possession (which masked thefts behind an inherited label);
- the ball's pixel width is the near/far side signal (image-plane trajectory
  side was tried and REJECTED: airborne balls over the near half project
  above the midcourt line).
"""

from pathlib import Path

import pytest

from src.detection.court_calibration import CourtCalibration
from src.recognition.action_classifier import ActionClassifier
from src.recognition.volleyball_actions import VisualGesture

COURT_JSON = Path(__file__).resolve().parent.parent / "calibrations" / "video_entreno_3.json"


class _StubPose:
    """PoseEstimator stand-in: no pose -> classifier falls back to ball motion."""

    def estimate_poses_batch(self, frame, detections):
        return [None] * len(detections)


@pytest.fixture()
def court():
    c = CourtCalibration(str(COURT_JSON))
    assert c.is_calibrated, f"missing calibration: {COURT_JSON}"
    return c


@pytest.fixture()
def clf(court):
    return ActionClassifier(
        pose_estimator=_StubPose(),
        confidence_threshold=0.3,
        court_calibration=court,
    )


def _ball(clf, points):
    """points: list of (frame, x, y, w)."""
    clf._ball_history.clear()
    for f, x, y, w in points:
        clf._ball_history.append((f, x, y, w, w))


def _snap(clf, tid, frame, bbox, team):
    """One observed snapshot for track ``tid`` at ``frame``."""
    x1, y1, x2, y2 = bbox
    hist = clf._player_pose_history.setdefault(tid, [])
    hist.append({
        "frame": frame, "pose": None,
        "center": [(x1 + x2) / 2, (y1 + y2) / 2],
        "bbox": list(bbox), "team": team,
    })


# Player geometry (checked against the real homography; midcourt at x~1040
# is y~607.6, net top y~294.4):
A_DEEP = (860, 700, 940, 880)     # feet (900,880) -> team A, 6.5m from net
A_THIEF = (1100, 560, 1180, 740)  # feet (1140,740) -> team A
B_NET = (1000, 410, 1080, 590)    # feet (1040,590) -> team B, ~0.9m from net
B_DEEP = (700, 380, 780, 560)     # feet (740,560) -> team B, 2.4m from net


# --- Ball-width side estimation ---

def test_width_side_far_ball(clf):
    _ball(clf, [(f, 900, 400, 22) for f in range(92, 100)])
    side, votes = clf._width_side(100)
    assert side == "B" and votes == 8


def test_width_side_near_ball(clf):
    _ball(clf, [(f, 900, 700, 45) for f in range(92, 100)])
    side, votes = clf._width_side(100)
    assert side == "A" and votes == 8


def test_width_side_abstains_in_band_and_on_mixed_evidence(clf):
    _ball(clf, [(f, 900, 500, 30) for f in range(92, 100)])
    assert clf._width_side(100)[0] is None
    # One far-regime + one near-regime sample: mixed -> no commit.
    _ball(clf, [(92, 900, 500, 22), (93, 900, 500, 45)] + [
        (f, 900, 500, 30) for f in range(94, 100)])
    assert clf._width_side(100)[0] is None


def test_width_side_respects_window_and_disable(clf):
    # Samples older than the 8-frame window are ignored.
    _ball(clf, [(80, 900, 400, 22)] + [(f, 900, 400, 30) for f in range(93, 100)])
    assert clf._width_side(100)[0] is None
    clf._width_side_enabled = False
    _ball(clf, [(f, 900, 400, 22) for f in range(92, 100)])
    assert clf._width_side(100)[0] is None


# --- Attribution target: width override, flip, carry, reset ---

def test_target_prefers_width_over_alternation(clf):
    # Possession says carry A, but the ball width says far half.
    _ball(clf, [(f, 900, 400, 22) for f in range(92, 100)])
    clf._last_touch_team, clf._last_touch_frame = "A", 60
    clf._last_touch_went_over = False
    target, info = clf._attribution_target(100)
    assert target == "B" and info["source"] == "width"


def test_target_flips_after_attack_when_width_abstains(clf):
    _ball(clf, [(f, 900, 700, 30) for f in range(92, 100)])  # abstain band
    clf._last_touch_team, clf._last_touch_frame = "A", 60
    clf._last_touch_went_over = True
    target, info = clf._attribution_target(100)
    assert target == "B" and info["source"] == "flip"


def test_target_carries_after_bump_set(clf):
    _ball(clf, [(f, 900, 700, 30) for f in range(92, 100)])
    clf._last_touch_team, clf._last_touch_frame = "B", 60
    clf._last_touch_went_over = False
    target, info = clf._attribution_target(100)
    assert target == "B" and info["source"] == "carry"


def test_target_unconstrained_on_new_rally_and_without_memory(clf):
    # No memory at all + abstaining width -> None (nothing to go on).
    _ball(clf, [(f, 900, 500, 30) for f in range(92, 100)])
    clf._last_touch_team, clf._last_touch_frame = None, None
    assert clf._attribution_target(100)[0] is None
    # No memory but a committing width still works -- a serve toss is in the
    # server's half, so the width directly gives their side.
    _ball(clf, [(f, 900, 700, 45) for f in range(92, 100)])
    assert clf._attribution_target(100)[0] == "A"
    # Dead-ball gap -> new rally -> unconstrained even after an attack
    # (width abstains here, else it would correctly target the server's half).
    _ball(clf, [(f, 900, 500, 30) for f in range(92, 100)])
    clf._last_touch_team, clf._last_touch_frame = "A", 5
    clf._last_touch_went_over = True
    assert clf._attribution_target(100)[0] is None


def test_target_disabled_without_court_or_flag(court):
    clf = ActionClassifier(pose_estimator=_StubPose(), court_calibration=None)
    assert clf._attribution_target(100)[0] is None
    clf2 = ActionClassifier(pose_estimator=_StubPose(), court_calibration=court,
                            team_aware=False)
    _ball(clf2, [(f, 900, 400, 22) for f in range(92, 100)])
    assert clf2._attribution_target(100)[0] is None


# --- Candidate filtering in _closest_player_at ---

def _four_players(clf, frame=100):
    _snap(clf, 1, frame, A_DEEP, "A")
    _snap(clf, 2, frame, A_THIEF, "A")
    _snap(clf, 3, frame, B_NET, "B")
    _snap(clf, 4, frame, B_DEEP, "B")


def test_team_filter_excludes_wrong_foot_candidate(clf):
    """The f488/f378 theft scenario: ball inside a wrong-team player's box."""
    _snap(clf, 1, 100, A_DEEP, "A")
    _snap(clf, 4, 100, B_DEEP, "B")
    # Ball contact point inside the deep-B player's box (closest by far)...
    point = [(B_DEEP[0] + B_DEEP[2]) / 2, (B_DEEP[1] + B_DEEP[3]) / 2]
    snap, dist, lr = clf._closest_player_at(100, point, target_team="A")
    # ...but team A is expected -> the nearest A-foot player wins instead.
    assert snap["track_id"] == 1 and dist > 0


def test_block_geometry_stays_eligible_under_filter(clf):
    """A wrong-team player AT the net (feet 0.9m away) keeps eligibility when
    the contact is ABOVE the net-top line (block geometry) and wins."""
    _four_players(clf)
    point = [1040, 280]  # above the net-top line (~294 at x=1040)
    snap, dist, lr = clf._closest_player_at(100, point, target_team="A")
    assert snap["track_id"] == 3 and dist > 0


def test_net_standing_setter_cannot_steal_below_net_contact(clf):
    """The f488 theft: same at-the-net wrong-team player, but the contact is a
    SET (below the tape) -> not block geometry -> excluded by the filter."""
    _four_players(clf)
    point = [1040, 500]  # inside B_NET's box, below the net-top line
    snap, dist, lr = clf._closest_player_at(100, point, target_team="A")
    assert snap["track_id"] != 3


def test_far_players_are_not_near_net(clf):
    """The image-pixel band swallowed the whole far half (it is only ~110px
    deep); the exemption must be ground-plane metres (B_DEEP = 2.4m away)."""
    _four_players(clf)
    foot = (B_DEEP[0] + B_DEEP[2]) // 2, B_DEEP[3]
    assert clf.court.world_dist_from_net(foot) > clf._near_net_exempt_m


def test_filter_relaxes_when_no_candidate_matches(clf):
    _snap(clf, 4, 100, B_DEEP, "B")
    point = [(B_DEEP[0] + B_DEEP[2]) / 2, (B_DEEP[1] + B_DEEP[3]) / 2]
    snap, dist, lr = clf._closest_player_at(100, point, target_team="A")
    assert snap["track_id"] == 4  # kept rather than losing the contact


def test_containment_tie_breaks_by_center_distance(clf):
    # Two A players whose boxes both contain the point: the one whose CENTRE
    # is nearer wins (deterministic, not dict-insertion order).
    _snap(clf, 1, 100, (800, 500, 1000, 700), "A")   # centre (900,600), cd=50
    _snap(clf, 2, 100, (850, 600, 950, 760), "A")    # centre (900,680), cd=30
    snap, dist, lr = clf._closest_player_at(100, [900, 650], target_team="A")
    assert snap["track_id"] == 2 and dist == 0.0


def test_stale_snapshots_excluded(clf):
    _snap(clf, 1, 85, A_DEEP, "A")   # 15 frames stale (> NEIGH+2)
    _snap(clf, 2, 100, B_DEEP, "B")
    snap, _, _ = clf._closest_player_at(100, [900, 830])
    assert snap["track_id"] == 2


# --- Emission: foot team, not the latched possession ---

def test_finalize_emits_foot_team_and_keeps_possession(clf):
    _four_players(clf)
    contact = clf._build_contact(
        {"track_id": 1, "center": [900, 790], "bbox": list(A_DEEP), "team": "A",
         "pose": None},
        lr_index=1, contact_point=[900, 780], kind="bounce",
        inc=(-10, -20), out=(5, -30), frame=100,
        side_info={"ball_side": "A", "source": "carry", "side_votes": 3},
    )
    assert contact["team"] == "A"          # per-contact foot team
    assert contact["ball_side"] == "A" and contact["attribution_source"] == "carry"
    out = clf._finalize(contact, None)
    assert out["team"] == "A"
    assert "team_in_possession" in out     # resolver's latched value, observability


# --- Court helpers ---

def test_midcourt_helpers(court):
    assert court.midcourt_y_at_x(900) == pytest.approx(602.8, abs=1.0)
    assert court.signed_midcourt_offset((900, 700)) == pytest.approx(97.2, abs=1.5)
    assert court.signed_midcourt_offset((900, 500)) == pytest.approx(-102.8, abs=1.5)
    uncal = CourtCalibration()
    assert uncal.midcourt_y_at_x(900) is None
    assert uncal.signed_midcourt_offset((900, 700)) is None


# --- evaluate.py team / player attribution scoring ---

def test_evaluate_match_action_events_spatial_player_gate():
    """Per-action TP gating is spatial + convention-agnostic.

    The pred's player_center must land in the GT box the event names, matched
    under EITHER id convention (canonical id or L-R index) -- pred player_id
    numbering need not equal GT ids, so raw equality would mis-gate files
    whose convention differs (e1/e3 = L-R, e4/e5 = canonical).
    """
    from scripts.evaluate import _match_action_events

    gt = [{"frame": 100, "player_id": 2, "final_action": "dig"}]
    gt_players = {
        "100": [{"id": 1, "bbox": [850, 700, 950, 880], "visible": True},
                {"id": 2, "bbox": [650, 380, 750, 560], "visible": True},
                {"id": 3, "bbox": [1050, 700, 1150, 880], "visible": True}],
    }
    # centre in canonical-GT1's box == L-R 2 -> matches player_id 2 (L-R conv)
    tp, fp, fn = _match_action_events(
        gt, [{"frame": 101, "player_id": 9, "action": "dig",
              "player_center": [900, 800]}], 15, True, gt_players)
    assert (tp, fp, fn) == (1, 0, 0)
    # same pair expressed with a canonical-convention GT id (player_id 1)
    tp, fp, fn = _match_action_events(
        [{"frame": 100, "player_id": 1, "final_action": "dig"}],
        [{"frame": 101, "player_id": 9, "action": "dig",
          "player_center": [900, 800]}], 15, True, gt_players)
    assert (tp, fp, fn) == (1, 0, 0)
    # centre in GT2's box (canonical 2, L-R 1) while the GT names player 3
    # under neither convention -> FP+FN
    tp, fp, fn = _match_action_events(
        [{"frame": 100, "player_id": 3, "final_action": "dig"}],
        [{"frame": 101, "player_id": 2, "action": "dig",
          "player_center": [700, 450]}], 15, True, gt_players)
    assert (tp, fp, fn) == (0, 1, 1)
    # centre in no box -> no spatial evidence, gate fails (conservative)
    tp, fp, fn = _match_action_events(
        gt, [{"frame": 101, "player_id": 9, "action": "dig",
              "player_center": [10, 10]}], 15, True, gt_players)
    assert (tp, fp, fn) == (0, 1, 1)
    # no gt_players -> falls back to raw player_id equality
    tp, fp, fn = _match_action_events(
        gt, [{"frame": 101, "player_id": 2, "action": "dig"}], 15, True, None)
    assert (tp, fp, fn) == (1, 0, 0)


def test_evaluate_action_attribution_metrics():
    from scripts.evaluate import evaluate_actions

    gt = [
        # player_id is the L-R index among visible players at the annotated
        # frame; at f100 GT2 (x650) is leftmost, so GT1 (x850) is L-R 2.
        {"frame": 100, "player_id": 2, "final_action": "dig", "player_team": "A"},
        # stored out of order on purpose (entreno_3 does this)
        {"frame": 300, "player_id": 2, "final_action": "set", "player_team": "B"},
        {"frame": 200, "player_id": 3, "final_action": "spike", "player_team": "A"},
    ]
    preds = [
        # f100: right team, right player (centre inside GT player 1's box)
        {"frame": 101, "player_id": 9, "action": "dig", "team": "A",
         "player_center": [900, 800]},
        # f200: wrong team, wrong player
        {"frame": 205, "player_id": 9, "action": "spike", "team": "B",
         "player_center": [700, 450]},
        # f300: right team, centre not inside any GT box -> player unscored
        {"frame": 298, "player_id": 9, "action": "set", "team": "B"},
    ]
    gt_players = {
        "100": [{"id": 1, "team": "A", "bbox": [850, 700, 950, 880], "visible": True},
                {"id": 2, "team": "B", "bbox": [650, 380, 750, 560], "visible": True}],
        "200": [{"id": 3, "team": "A", "bbox": [850, 700, 950, 880], "visible": True},
                {"id": 4, "team": "B", "bbox": [650, 380, 750, 560], "visible": True}],
        "300": [{"id": 1, "team": "A", "bbox": [850, 700, 950, 880], "visible": True},
                {"id": 2, "team": "B", "bbox": [650, 380, 750, 560], "visible": True}],
    }
    res = evaluate_actions(preds, gt, match_player=False, gt_players=gt_players)
    assert res["matched_pairs"] == 3
    assert res["team_scored"] == 3
    assert res["team_accuracy"] == round(2 / 3, 3)   # f100 A ok, f200 B!=A, f300 B ok
    assert res["player_scored_spatial"] == 2         # f300's centre in no box
    # Both id conventions are scored (e1/e3 GT ids are L-R indices, e4/e5 are
    # canonical ids). f100: centre in canonical-GT1's box, which is L-R 2.
    assert res["player_accuracy_spatial"] == 0.0     # canonical 1 != player_id 2
    assert res["player_accuracy_spatial_lr"] == 0.5  # L-R 2 == player_id 2
    # f200: centre in canonical-GT4's box (L-R 1), player_id 3 -> wrong either way

    # Without players-frames, team scoring still works, player scoring absent.
    res2 = evaluate_actions(preds, gt, match_player=False)
    assert res2["team_accuracy"] == round(2 / 3, 3)
    assert "player_accuracy_spatial" not in res2
