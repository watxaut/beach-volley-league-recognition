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
B_DEEP = (700, 380, 780, 560)     # feet (740,560) -> team B, 2.4m from net (inside
                                  # the 2.5m exemption: a spiker taking off ~2m back
                                  # is legitimately eligible, e5 f300 was at 2.14m)
B_VERY_DEEP = (520, 365, 600, 545)  # feet (560,545) -> team B, 3.2m from net


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
    deep); the exemption must be ground-plane metres. 2.5m deliberately
    includes take-off spots ~2m back (e5 f300's spiker: 2.14m, exempt) but
    not genuine back-court defenders (B_VERY_DEEP = 3.2m)."""
    _four_players(clf)
    foot = (B_VERY_DEEP[0] + B_VERY_DEEP[2]) // 2, B_VERY_DEEP[3]
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


# --- Gap-bridged bounce (contact inside a sighting gap) ---

def _bridge_history(clf, gap=12, rise=142, drop=97):
    """The e5-f111 shape: ball descends to f102, vanishes for `gap` frames
    (occluded at the toucher's hands), reappears at f114 rising."""
    b = 102 + gap
    y0 = 330
    _ball(clf, [(96, 1016, 275 - drop, 22), (100, 1015, 238, 22),
                (101, 1014, 256, 22), (102, 1013, 275, 22),
                (b, 1018, y0, 24), (b + 2, 1022, y0 - rise * 2 / 6, 24),
                (b + 4, 1026, y0 - rise * 4 / 6, 24), (b + 6, 1040, y0 - rise, 24)])


def test_bridge_fires_on_occluded_contact(clf):
    """Real sightings stop descending at f102 and resume rising at f114: the
    touch inside the gap must be seen (as a bounce, touch point interpolated
    into the gap)."""
    _bridge_history(clf)
    r = clf._detect_contact(114)
    assert r is not None
    point, kind, inc, out, _ = r
    assert kind == "bounce"
    assert 1013 <= point[0] <= 1018          # x interpolated inside the gap
    assert point[1] > 275                    # bottom sits below both endpoints
    assert inc[1] > 0 and out[1] < 0         # descending in, ascending out


def test_bridge_requires_long_gap(clf):
    """Gaps below BRIDGE_SHORT_MIN_GAP stay the normal detector's turf (it
    can still fire there); bridging them would double-report the same touch."""
    _bridge_history(clf, gap=4)
    vertex = clf._point_at(106)
    assert vertex is not None
    assert clf._bridge_contact(106, vertex) is None


def test_bridge_rejects_gap_too_long(clf):
    _bridge_history(clf, gap=18)
    vertex = clf._point_at(120)
    assert clf._bridge_contact(120, vertex) is None


def test_bridge_rejects_sand_bounce(clf):
    """A ball rebounding off the sand rises far less than a set toss
    (e5 f332-340: 25px) and must not read as a touch."""
    _bridge_history(clf, rise=25)
    vertex = clf._point_at(114)
    assert clf._bridge_contact(114, vertex) is None


def test_bridge_requires_descent_into_gap(clf):
    _bridge_history(clf, drop=8)
    vertex = clf._point_at(114)
    assert clf._bridge_contact(114, vertex) is None


def test_bridge_respects_min_contact_gap(clf):
    _bridge_history(clf)
    clf._last_contact_frame = 110          # a confirmed contact 4 frames earlier
    assert clf._detect_contact(114) is None


# --- Short-gap bridge (5-7 frame occlusion at the toucher's arms) ---

def _short_history(clf, gap=7, rise=142, drop=97, post_x=1018, post_ys=None):
    """The e2-f206 shape: ball descends to f102, a brief occlusion (5-7f),
    then reappears at b=102+gap rising with dense post-gap sightings."""
    b = 102 + gap
    y0 = 330
    ys = post_ys or [y0, y0 - rise * 2 / 6, y0 - rise * 4 / 6, y0 - rise]
    _ball(clf, [(96, 1016, 275 - drop, 22), (100, 1015, 238, 22),
                (101, 1014, 256, 22), (102, 1013, 275, 22),
                (b, post_x, ys[0], 24), (b + 2, post_x + 4, ys[1], 24),
                (b + 4, post_x + 8, ys[2], 24), (b + 6, post_x + 22, ys[3], 24)])


def test_short_gap_bridge_fires_dense_right(clf):
    """e2 f206: a 7-frame occlusion at the digger's arms leaves the normal
    tests without 2 left points within NEIGH, so the short-gap bridge recovers
    the touch (measured on video: +f209 dig, and the f256 dig->set cascade
    heals)."""
    _short_history(clf, gap=7)
    r = clf._detect_contact(109)
    assert r is not None
    point, kind, inc, out, _ = r
    assert kind == "bounce"
    assert 1013 <= point[0] <= 1018          # x interpolated inside the gap
    assert point[1] > 275                    # bottom sits below both endpoints
    assert inc[1] > 0 and out[1] < 0         # descending in, ascending out


def test_short_gap_bridge_fires_sparse_right_cross_rise(clf):
    """e6 f212: post-gap sightings are sparse (the dug ball reappears once,
    8f later -- beyond the decision-time window, which ends at c+6). The
    CROSS-GAP RISE -- the first post-gap sighting already 144px above the
    last pre-gap one -- is the only usable ascent evidence, and it needs no
    future points."""
    _ball(clf, [(96, 1016, 178, 22), (100, 1015, 238, 22),
                (101, 1014, 256, 22), (102, 1013, 275, 22),
                (108, 1018, 131, 24)])
    r = clf._detect_contact(108)
    assert r is not None
    point, kind, inc, out, _ = r
    assert kind == "bounce"
    assert inc[1] > 0 and out[1] < -60       # descending in, rising hard out


def test_short_gap_bridge_leaves_dense_gaps_to_normal_path(clf):
    """Gap 6 but >=2 real points within NEIGH on BOTH sides: the normal vertex
    tests can fire (e6 f265 does exactly this), so the bridge must not
    relocate the contact."""
    _ball(clf, [(96, 1016, 178, 22), (101, 1014, 256, 22), (102, 1013, 275, 22),
                (108, 1018, 330, 24), (110, 1022, 283, 24),
                (112, 1026, 235, 24), (114, 1040, 188, 24)])
    vertex = clf._point_at(108)
    assert vertex is not None
    assert clf._bridge_contact(108, vertex) is None
    # ... while the normal bounce test does fire here (it is its turf).
    assert clf._detect_contact(108) is not None


def test_short_gap_bridge_rejects_ball_identity_jump(clf):
    """A spare ball appearing ~700px away after a game-ball gap must not
    bridge (e6 f236/f289 and e5 f320/f325 classes, all refused by this gate
    in the six-video A/B)."""
    _ball(clf, [(96, 1016, 178, 22), (100, 1015, 238, 22),
                (101, 1014, 256, 22), (102, 1013, 275, 22),
                (108, 1718, 131, 24)])
    vertex = clf._point_at(108)
    assert vertex is not None
    assert clf._bridge_contact(108, vertex) is None


def test_short_gap_bridge_requires_descent_into_gap(clf):
    """A rising ball with a detection dropout is not a touch: no descent into
    the gap, however steep the cross-gap rise."""
    _ball(clf, [(96, 1016, 285, 22), (100, 1015, 255, 22),
                (101, 1014, 236, 22), (102, 1013, 218, 22),
                (108, 1018, 74, 24)])
    vertex = clf._point_at(108)
    assert vertex is not None
    assert clf._bridge_contact(108, vertex) is None


def test_classic_band_still_requires_two_right_points(clf):
    """The cross-gap-rise fallback is SHORT-band only: a classic 12f gap with
    no post-gap sightings still refuses (pre-change behaviour)."""
    _ball(clf, [(96, 1016, 178, 22), (100, 1015, 238, 22),
                (101, 1014, 256, 22), (102, 1013, 275, 22),
                (114, 1018, 131, 24)])
    vertex = clf._point_at(114)
    assert vertex is not None
    assert clf._bridge_contact(114, vertex) is None


# --- Reentry contact (out-of-frame excursion, e6 f308 joust) ---

def _reentry_history(clf, c=288, gap=12, run=None, junk=(34, 118, 30)):
    """The e6 shape: the set toss exits the frame top, SPARE junk is the last
    thing in the history before the gap (the tracker adopted it), then the
    game ball re-enters into a fast horizontal run above the net tape. At
    x~1150 the e3 calibration's net top is y~308.7, midcourt y~608.

    Default run: f288 (1152,278) -> f291 (1002,278), i.e. -50px/f flat.
    """
    if run is None:
        run = [(c, 1152, 278), (c + 1, 1102, 276), (c + 2, 1051, 276),
               (c + 3, 1002, 278)]
    toss = [(248, 1090, 380, 34), (250, 1098, 350, 34), (252, 1106, 316, 34),
            (254, 1114, 278, 34), (256, 1122, 236, 34), (258, 1130, 190, 34),
            (260, 1138, 140, 34), (262, 1146, 86, 34), (264, 1154, 28, 34)]
    jx, jy, jw = junk
    junk_pts = [(c - gap - 2, jx, jy, jw), (c - gap, jx - 12, jy - 40, jw)]
    _ball(clf, toss + junk_pts + [(f, x, y, 45) for f, x, y in run])


def test_reentry_fires_on_identity_break(clf):
    """e6 f308: the pre-gap point (spare junk) is 1695px from where the run's
    own velocity predicts it -- free flight cannot connect, so the joust touch
    inside the excursion is manufactured, dated at the gap midpoint."""
    _reentry_history(clf)
    r = clf._detect_contact(288)
    assert r is not None
    point, kind, inc, out, frame = r
    assert kind == "reentry"
    assert frame == 282                       # 288 - gap//2 (GT f308 shape)
    assert point[0] == pytest.approx(1452.0)  # back-extrapolated along the run
    assert inc[1] > 0 and inc[0] == 0.0       # manufactured vertical-from-above
    assert out[0] == -150.0                   # the real outgoing drive (net px)


def test_reentry_rejects_connectible_gap(clf):
    """e2 f149 (the refuted instance #2): the tracker bridged the toss apex,
    so the pre-gap point IS velocity-consistent with the run (34px off) -- no
    identity break, no manufactured touch."""
    run = [(288, 1152, 278), (290, 1060, 278), (292, 968, 278)]
    _reentry_history(clf, c=288, gap=8, run=run, junk=(1152 + 46 * 8, 278, 30))
    assert clf._detect_contact(288) is None


def test_reentry_rejects_vertical_run(clf):
    """A lob that exits the top re-descends vertically -- that is not an
    attack impulse and must stay untouched (ordinary flight)."""
    run = [(288, 1152, 100), (290, 1154, 140), (292, 1156, 180)]
    _reentry_history(clf, c=288, gap=12, run=run)
    assert clf._detect_contact(288) is None


def test_reentry_rejects_slow_run(clf):
    _reentry_history(clf, c=288, gap=12,
                     run=[(288, 1152, 278), (290, 1140, 279), (292, 1128, 280)])
    assert clf._detect_contact(288) is None


def test_reentry_rejects_below_tape_run(clf):
    """The run must re-enter at/above the net tape; a run already below it is
    ordinary rally flight, not a joust signature."""
    run = [(288, 1152, 420), (290, 1100, 424), (292, 1048, 428)]
    _reentry_history(clf, c=288, gap=12, run=run)
    assert clf._detect_contact(288) is None


def test_reentry_respects_gap_band(clf):
    _reentry_history(clf, c=288, gap=6)
    vertex = clf._point_at(288)
    assert clf._reentry_contact(288, vertex) is None    # short band: bridges' turf
    _reentry_history(clf, c=318, gap=34)
    vertex = clf._point_at(318)
    assert clf._reentry_contact(318, vertex) is None    # dead-ball territory


def test_reentry_emits_spike_with_takeoff_team(clf):
    """End to end: the manufactured contact resolves to a SPIKE dated at the
    gap midpoint, and the emitted team comes from the GROUNDED takeoff stance
    (the contact-time snapshot is mid-jump; its airborne feet read the wrong
    side -- GT A vs the airborne B read)."""
    _reentry_history(clf)
    _snap(clf, 3, 282, [1280, 380, 1420, 598], "A")   # contact time: airborne
    _snap(clf, 3, 279, [1300, 420, 1440, 640], "A")   # takeoff stance: grounded
    det = {"track_id": 3, "bbox": [1300, 420, 1440, 640], "center": [1370, 530],
           "team": "A", "predicted": False}
    events = []
    for f in range(283, 296):
        events += clf.classify_actions(None, [det], None, frame_number=f)
    events += clf.flush()
    assert len(events) == 1
    ev = events[0]
    assert ev["frame_number"] == 282
    assert ev["action"] == "spike"
    assert ev["contact_kind"] == "reentry"
    assert ev["team"] == "A"                  # stance read, not the airborne B
    assert ev["track_id"] == 3


def test_reentry_needs_a_player_in_reach(clf):
    """No candidate within CONTACT_REACH of the manufactured point: no event
    (a wrong-court re-entry must not invent a toucher)."""
    _reentry_history(clf)
    _snap(clf, 4, 282, [100, 700, 200, 900], "A")
    det = {"track_id": 4, "bbox": [100, 700, 200, 900], "center": [150, 800],
           "team": "A", "predicted": False}
    events = []
    for f in range(283, 296):
        events += clf.classify_actions(None, [det], None, frame_number=f)
    events += clf.flush()
    assert events == []


# --- Poke-class drive: level-horizontal exit reads the takeoff stance -----

def test_poke_signature_gate(clf):
    """_is_poke_drive keys on the PER-FRAME level-horizontal exit. ``out`` is
    the NEIGH-window SUM, so the gate divides by NEIGH (conservative): the
    measured e6 f309 poke is (-279, 39.5) -> (-39.9, +5.6)/frame. Driven
    balls exit downward or nearly straight and must not qualify."""
    assert clf._is_poke_drive("drive", (-279.0, 39.5)) is True   # the e6 poke
    assert clf._is_poke_drive("drive", (-7 * 30.0, 7 * 20.0)) is False  # vy too big
    assert clf._is_poke_drive("drive", (-7 * 10.0, 7 * 5.0)) is False   # vx too small
    assert clf._is_poke_drive("bounce", (-7 * 47.0, 0.0)) is False      # wrong band


def test_poke_constants_mirror_spike_analyzer():
    """The classifier's attribution gate and the analyzer's type rule are ONE
    measured discriminator (probe over all GT spikes, 2026-09-06); they must
    not drift apart."""
    from src.analysis.spike_analyzer import SpikeAnalyzer
    assert ActionClassifier.POKE_EXIT_VX_PX == SpikeAnalyzer.POKE_EXIT_VX_PX
    assert ActionClassifier.POKE_EXIT_VY_PX == SpikeAnalyzer.POKE_EXIT_VY_PX


def test_takeoff_stance_majority_beats_landing_drift(clf):
    """The nearest-to-contact stance can be the FIRST frame whose grounded
    foot has drifted across the net ground line (e6 f307 reads B off the
    GT-A spiker; f297-306 all read A): the window majority outvotes it and
    picks the nearest MAJORITY-team snapshot."""
    for f in range(297, 307):
        _snap(clf, 1, f, [1300, 420, 1440, 640], "A")
    _snap(clf, 1, 307, [1290, 380, 1430, 598], "B")   # nearest c-2, minority
    stance = clf._takeoff_stance(1, 309)
    assert stance["frame"] == 306
    assert clf.court.get_team_for_bbox(stance["bbox"]) == "A"


def test_takeoff_stance_tie_falls_back_to_nearest(clf):
    """No strict majority (or no team reads): the old nearest-to-contact
    behavior."""
    _snap(clf, 1, 300, [1300, 420, 1440, 640], "A")
    _snap(clf, 1, 307, [1290, 380, 1430, 598], "B")
    assert clf._takeoff_stance(1, 309)["frame"] == 307


def test_poke_drive_emits_spike_with_takeoff_team(clf):
    """End to end (the e6 f309 shape through the DRIVE band): a fast descent
    checked level into a strongly horizontal run at the net. The contact-time
    toucher is airborne (feet project deep, court team reads B); the emitted
    team must come from the grounded takeoff stance (A) and the resolver must
    land SPIKE even though the pose reads hands-overhead (BLOCK gesture at
    touch 3 = the poke fall-through)."""
    descent = [(f, 1330 + 2 * (309 - f), 19 + 28 * (f - 302), 30)
               for f in range(302, 310)]          # fast descent into the vertex
    run = [(310, 1332, 268, 45), (312, 1262, 286, 55), (314, 1152, 278, 51),
           (315, 1098, 276, 47), (316, 1051, 276, 46)]   # level, -40..46 px/f
    _ball(clf, descent + run)
    _snap(clf, 1, 309, [1280, 380, 1420, 598], "A")   # contact time: airborne
    for f in range(300, 308):
        _snap(clf, 1, f, [1300, 420, 1440, 640], "A")  # takeoff stance: grounded
    det = {"track_id": 1, "bbox": [1280, 380, 1420, 598], "center": [1350, 490],
           "team": "A", "predicted": False}
    # Rally context: the poke is the THIRD touch of A's continuing
    # possession (serve/dig ... set f262 ... poke) -- that touch number is
    # what makes the BLOCK-gesture fall-through land on spike.
    from src.recognition.volleyball_actions import VisualGesture
    clf._resolver.resolve({"frame": 240, "gesture": VisualGesture.BUMP_SET,
                           "near_net": False, "behind_baseline": False,
                           "team": "A"}, None)
    clf._resolver.resolve({"frame": 262, "gesture": VisualGesture.BUMP_SET,
                           "near_net": True, "behind_baseline": False,
                           "team": "A"}, None)
    events = []
    for f in range(310, 322):
        events += clf.classify_actions(None, [det], None, frame_number=f)
    events += clf.flush()
    assert len(events) == 1
    ev = events[0]
    assert ev["contact_kind"] == "drive"
    assert ev["action"] == "spike"
    assert ev["team"] == "A"                  # stance read, not the airborne B
    assert ev["track_id"] == 1


# --- Rally-opening serve gate + redirect locality (e7 ratified retune) ---

def _serve_history(clf):
    """e7 f25 shape: a short dip, then a FED ascent through the contact --
    the incoming +/-3f slope (-42 px/f) beats the preceding +/-6f slope."""
    _ball(clf, [(21, 904, 394, 30), (22, 904, 413, 30), (23, 908, 372, 30),
                (24, 912, 334, 30), (25, 915, 286, 30), (26, 916, 254, 30),
                (27, 919, 224, 30), (28, 922, 200, 30)])


def test_serve_gate_fires_on_fed_ascent(clf):
    _serve_history(clf)
    r = clf._detect_contact(25)
    assert r is not None and r[1] == "drive" and r[4] == 25


def test_serve_gate_refuses_gravity_arc(clf):
    """e4's opening: a pure free arc -- the ascent DECELERATES into every
    candidate vertex (gravity can only decay an ascent); no contact."""
    _ball(clf, [(12, 834, 600, 24), (13, 836, 572, 24), (14, 836, 538, 24),
                (15, 835, 504, 24), (16, 832, 475, 24), (17, 832, 449, 24),
                (18, 830, 426, 24), (19, 828, 404, 24), (20, 826, 386, 24),
                (21, 824, 370, 24), (22, 822, 358, 24), (23, 820, 347, 24),
                (24, 818, 340, 24), (25, 816, 335, 24), (26, 814, 332, 24),
                (27, 813, 332, 24), (28, 810, 334, 24), (29, 808, 340, 24)])
    for c in (14, 15, 20, 25, 27):
        assert clf._detect_contact(c) is None


def test_serve_gate_needs_rally_start(clf):
    _serve_history(clf)
    clf._last_contact_frame = 20          # a recent contact: no rally opening
    assert clf._detect_contact(25) is None


def test_redirect_flip_must_be_local(clf):
    """e7 f239: a mid-descent vertex whose only flip evidence lives 6f ahead
    (the f243 set's rightward impulse) must refuse -- and the REAL set
    contact fires at f242 via the drive band's downward-speed cut."""
    pts = [(231, 928, 82, 24), (232, 919, 106, 24), (237, 880, 248, 24),
           (238, 872, 279, 24), (239, 864, 316, 24), (240, 860, 346, 24),
           (241, 852, 380, 24), (242, 844, 419, 24), (245, 936, 466, 30),
           (246, 936, 465, 30), (250, 940, 380, 30), (253, 944, 300, 30)]
    _ball(clf, pts)
    assert clf._detect_contact(239) is None
    r = clf._detect_contact(242)
    assert r is not None and r[1] == "drive" and r[4] == 242


def test_local_redirect_still_fires(clf):
    """A genuine block/redirect: the reversal is visible inside the vertex's
    own +/-3f window."""
    _ball(clf, [(50, 760, 300, 24), (52, 800, 300, 24), (54, 840, 300, 24),
                (55, 860, 300, 24), (56, 880, 300, 24), (58, 840, 300, 24),
                (60, 800, 300, 24), (62, 760, 300, 24)])
    r = clf._detect_contact(55)
    assert r is not None and r[1] == "redirect"


def test_serve_reach_allows_toss_apex(clf):
    """End to end (the e7 f25 shape): the server meets the ball at the top of
    an extended toss -- ball-to-box 147.5px, over the 140 dig/spike reach but
    inside the serve-scoped 160 -- and the resolver labels SERVE off the
    grounded behind-baseline stance."""
    _serve_history(clf)
    for f in (23, 24, 25, 26, 27):
        _snap(clf, 3, f, [788, 434, 939, 966], "A")   # real f25 server box
    det = {"track_id": 3, "bbox": [788, 434, 939, 966], "center": [863, 700],
           "team": "A", "predicted": False}
    events = []
    for f in range(26, 40):
        events += clf.classify_actions(None, [det], None, frame_number=f)
    events += clf.flush()
    assert len(events) == 1
    ev = events[0]
    assert ev["frame_number"] == 25
    assert ev["action"] == "serve"
    assert ev["team"] == "A"
    assert ev["track_id"] == 3
