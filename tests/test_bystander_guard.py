"""Tests for the off-court bystander-hijack guard (assignment-level court
membership): an out-of-court detection can only CONTINUE a recently-in-court
track (server step-out grace window); gallery restores and stale tracks require
a strictly in-court detection."""
from __future__ import annotations

from src.tracking.player_tracker import PlayerTracker


class _SideCourt:
    """Fake court: foot x in [400, 1200] is on the court, else off it."""

    is_calibrated = True

    def foot_point(self, bbox):
        return (int((bbox[0] + bbox[2]) / 2), int(bbox[3]))

    def is_point_in_court(self, point):
        return 400 <= point[0] <= 1200

    def get_team_for_bbox(self, bbox):
        return "A" if self.is_point_in_court(self.foot_point(bbox)) else "B"

    def world_body_size(self, bbox):
        return None


def _det(cx, cy, conf=0.9):
    w, h = 40, 80
    return {
        "bbox": [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
        "center": [float(cx), float(cy)],
        "confidence": conf,
    }


def _make_tracker(**overrides):
    params = dict(
        max_players=4,
        max_disappeared=10,
        max_distance=250.0,
        coast_extrapolation_cap=4,
        gallery_reacquire_distance_px=300.0,
        gallery_reacquire_min_appearance=0.15,
        court_calibration=_SideCourt(),
        off_court_grace_frames=5,
    )
    params.update(overrides)
    tracker = PlayerTracker(**params)
    tracker._initialized = True
    tracker.frame_count = 100
    return tracker


def _seed_four(tracker, positions):
    ids = []
    for cx, cy in positions:
        ids.append(tracker._create_track(_det(cx, cy), require_court_admission=False))
    return ids


# In-court positions / an out-of-court bystander position
IN_COURT = [(500, 400), (700, 400), (900, 400), (1100, 400)]
BYSTANDER_X = 1400  # foot outside the [400, 1200] court


class TestMayFeedTrack:
    def test_in_court_detection_always_allowed(self):
        tracker = _make_tracker()
        (tid,) = _seed_four(tracker, [(500, 400)])
        track = tracker.tracks[tid]
        # stale last-in-court, but the detection is in court -> allowed
        track["last_in_court_frame"] = tracker.frame_count - 999
        assert tracker._may_feed_track(track, _det(500, 400)) is True

    def test_out_of_court_within_grace_allowed(self):
        tracker = _make_tracker(off_court_grace_frames=5)
        (tid,) = _seed_four(tracker, [(500, 400)])
        track = tracker.tracks[tid]
        track["last_in_court_frame"] = tracker.frame_count - 5
        assert tracker._may_feed_track(track, _det(BYSTANDER_X, 400)) is True

    def test_out_of_court_beyond_grace_blocked(self):
        tracker = _make_tracker(off_court_grace_frames=5)
        (tid,) = _seed_four(tracker, [(500, 400)])
        track = tracker.tracks[tid]
        track["last_in_court_frame"] = tracker.frame_count - 6
        track["last_matched_frame"] = tracker.frame_count - 2  # a gap, not continuous
        assert tracker._may_feed_track(track, _det(BYSTANDER_X, 400)) is False

    def test_continuous_off_court_tracking_survives_beyond_grace(self):
        """The entreno_3 server regression: a player who walks out and keeps
        being detected every frame stays tracked indefinitely -- continuous
        observation means no gap for a bystander to hijack through."""
        tracker = _make_tracker(max_disappeared=4, off_court_grace_frames=5)
        ids = _seed_four(tracker, IN_COURT)
        server = ids[3]
        for _ in range(4):
            tracker.update([_det(cx, cy) for cx, cy in IN_COURT], None, ball_active=True)

        # Server walks out; fed by an off-court detection EVERY frame for far
        # longer than the grace window.
        others = [_det(cx, cy) for cx, cy in IN_COURT[:3]]
        off_det = _det(1210, 400)  # foot off-court, near player 4
        for _ in range(20):  # >> grace (5)
            out = tracker.update(others + [off_det], None, ball_active=True)
        by_id = {o["track_id"]: o for o in out}
        assert server in by_id, "continuously-observed off-court player must stay tracked"
        assert not by_id[server].get("predicted", False)

    def test_uncalibrated_never_blocks(self):
        tracker = _make_tracker(court_calibration=None)
        assert tracker._detection_in_court(_det(BYSTANDER_X, 400)) is None


class TestOffCourtHoldHorizon:
    """The hold horizon on CONTINUOUS out-of-court feeding (entreno_2's
    right-side bystander: seeded while straddling the sideline, then detected
    continuously OUT of court for 415 frames, holding a roster slot while two
    real near-side players shared the rest)."""

    def test_continuous_off_court_within_hold_allowed(self):
        tracker = _make_tracker(off_court_hold_frames=90)
        (tid,) = _seed_four(tracker, [(500, 400)])
        track = tracker.tracks[tid]
        track["last_in_court_frame"] = tracker.frame_count - 60
        track["last_matched_frame"] = tracker.frame_count - 1  # continuous
        assert tracker._may_feed_track(track, _det(BYSTANDER_X, 400)) is True

    def test_continuous_off_court_beyond_hold_blocked(self):
        """The e2 bystander: continuously detected, but not seen IN court for
        longer than the horizon -> no more feeding; the track must retire so
        strict in-court admission can take the slot."""
        tracker = _make_tracker(off_court_hold_frames=90)
        (tid,) = _seed_four(tracker, [(500, 400)])
        track = tracker.tracks[tid]
        track["last_in_court_frame"] = tracker.frame_count - 91
        track["last_matched_frame"] = tracker.frame_count - 1  # continuous
        assert tracker._may_feed_track(track, _det(BYSTANDER_X, 400)) is False

    def test_zone_seed_continuous_is_governed_by_zone_rules(self):
        """Never-in-court tracks (serve-zone seeds) keep their existing
        regime: continuous matching still feeds them; the zone trial expiry
        (2026-08-18) is their eviction path, not this horizon."""
        tracker = _make_tracker(off_court_hold_frames=90)
        (tid,) = _seed_four(tracker, [(500, 400)])
        track = tracker.tracks[tid]
        track["last_in_court_frame"] = None
        track["last_matched_frame"] = tracker.frame_count - 1
        assert tracker._may_feed_track(track, _det(BYSTANDER_X, 400)) is True

    def test_bystander_slot_freed_beyond_hold(self):
        """End to end: the squatter is seeded in court, steps out, keeps being
        detected every frame past the horizon -> the track retires and a new
        IN-COURT player takes the freed slot (the off-court detection itself
        must never become a track)."""
        tracker = _make_tracker(
            max_disappeared=4, off_court_grace_frames=5, off_court_hold_frames=10
        )
        ids = _seed_four(tracker, IN_COURT)
        squatter = ids[3]
        others = [_det(cx, cy) for cx, cy in IN_COURT[:3]]
        off_det = _det(1300, 400)  # foot x=1300, well off-court

        for _ in range(10):  # within the horizon: still tracked
            out = tracker.update(others + [off_det], None, ball_active=True)
        assert squatter in {o["track_id"] for o in out}

        for _ in range(8):  # horizon (10) + max_disappeared (4): retired
            out = tracker.update(others + [off_det], None, ball_active=True)
        assert squatter not in {o["track_id"] for o in out}
        assert squatter not in tracker.tracks
        assert squatter in tracker.gallery  # dormant, id reserved

        # A new player appears IN court, far from the survivors -> takes the
        # freed slot (here via the dormant gallery's in-court restore, which
        # is the designed path -- the box is on the real player). The
        # off-court bystander itself still never gets a track.
        newcomer = _det(1100, 600)  # dist ~283px from (900,400) > max_distance
        out = tracker.update(others + [off_det, newcomer], None, ball_active=True)
        boxes = {tuple(o["bbox"]) for o in out}
        assert len({o["track_id"] for o in out}) == 4
        assert tuple(newcomer["bbox"]) in boxes, "in-court newcomer takes the slot"
        assert tuple(off_det["bbox"]) not in boxes, "bystander never tracked"


class TestOngoingAssignment:
    def test_server_step_out_is_tracked_within_grace(self):
        """A player who steps just off-court keeps their id while young (the
        off-court server case the grace window exists for)."""
        tracker = _make_tracker()
        ids = _seed_four(tracker, IN_COURT)
        for _ in range(6):
            tracker.update([_det(cx, cy) for cx, cy in IN_COURT], None, ball_active=True)

        stepper = ids[3]  # rightmost player, closest to the court edge
        stepped_out = _det(1210, 400)  # foot x=1210: off-court, near player 4
        out = tracker.update(
            [_det(cx, cy) for cx, cy in IN_COURT[:3]] + [stepped_out], None, ball_active=True
        )
        by_id = {o["track_id"]: o for o in out}
        assert stepper in by_id, "stepped-out player should still be tracked"
        assert by_id[stepper]["bbox"] == stepped_out["bbox"]
        assert not by_id[stepper].get("predicted", False)

    def test_bystander_cannot_inherit_stale_track(self):
        """Player 4 disappears; long after, a bystander appears (foot off-court)
        right where player 4 used to be. The bystander must NOT get id 4 --
        not via Hungarian, not via the IoU re-attach, not via the gallery."""
        tracker = _make_tracker(max_disappeared=3)
        ids = _seed_four(tracker, IN_COURT)
        p4 = ids[3]
        for _ in range(6):
            tracker.update([_det(cx, cy) for cx, cy in IN_COURT], None, ball_active=True)

        # Player 4 gone for well past the grace window (and past
        # max_disappeared -> id 4 retires dormant).
        three = [_det(cx, cy) for cx, cy in IN_COURT[:3]]
        for _ in range(12):
            tracker.update(list(three), None, ball_active=True)
        assert p4 not in tracker.tracks and p4 in tracker.gallery

        # Bystander materialises at player 4's exact last position, off-court.
        bystander = _det(1195 + 40, 400)  # center 1235 -> foot x=1235, off-court
        out = tracker.update(list(three) + [bystander], None, ball_active=True)
        out_ids = {o["track_id"] for o in out}
        assert p4 not in out_ids, "bystander must not inherit player 4's id"
        assert p4 not in tracker.tracks
        assert p4 in tracker.gallery, "dormant id stays reserved for the real player"
        # And the bystander itself must not be tracked at all.
        boxes = [tuple(o["bbox"]) for o in out]
        assert tuple(bystander["bbox"]) not in boxes


class TestGalleryRestore:
    def test_gallery_restore_requires_in_court_detection(self):
        """A dormant id cannot be resurrected by an off-court detection -- not
        by position (pass 1) and not by appearance (pass 2). This is the exact
        entreno_1 hijack vector (frame 97, gallery_appearance)."""
        tracker = _make_tracker(max_disappeared=3)
        ids = _seed_four(tracker, IN_COURT)
        p4 = ids[3]
        for _ in range(6):
            tracker.update([_det(cx, cy) for cx, cy in IN_COURT], None, ball_active=True)
        three = [_det(cx, cy) for cx, cy in IN_COURT[:3]]
        for _ in range(12):
            tracker.update(list(three), None, ball_active=True)
        assert p4 in tracker.gallery

        # Off-court detection right at the dormant player's last position:
        # inside the position gate (same spot), so only the court rule blocks it.
        hijacker = _det(1235, 400)
        out = tracker.update(list(three) + [hijacker], None, ball_active=True)
        assert p4 not in {o["track_id"] for o in out}
        assert p4 in tracker.gallery

        # The real player 4 comes back ON court -> original id restored.
        out = tracker.update(
            [_det(cx, cy) for cx, cy in IN_COURT], None, ball_active=True
        )
        assert p4 in {o["track_id"] for o in out}
        assert p4 in tracker.tracks


class TestInCourtPreference:
    """Association-cost preference for in-court detections (entreno_6, open
    point 16). _may_feed_track decides whether an off-court feeding is ALLOWED
    at all; off_court_cost_penalty_px decides which candidate WINS when the
    track has a choice: identity is anchored on the court, so a court detection
    must beat an off-court one even at a longer gate distance. Without it a
    walkway bystander takes a coasting track the instant the player's own
    detection blips (e6 f142: the far-left digger's track was grabbed at a
    105 px jump and never returned -- 200 frames untracked), and the squat
    cascades into chain-swaps (e6 f305/f311, team vote flip A->B)."""

    def test_cost_unit_prefers_in_court_over_closer_off_court(self):
        tracker = _make_tracker(max_distance=250.0)
        (tid,) = _seed_four(tracker, [(500, 400)])
        track = tracker.tracks[tid]
        player = _det(620, 400)    # in court, 120 px away
        walker = _det(390, 400)    # off court (x<400), 110 px away -- closer
        c_player = tracker._compute_assignment_cost(track, player)
        c_walker = tracker._compute_assignment_cost(track, walker)
        assert c_player is not None and c_walker is not None
        assert c_player < c_walker, (c_player, c_walker)

    def test_update_takes_in_court_player_over_closer_bystander(self):
        """The e6 f311 shape at one-track scale: the track's player (in court,
        farther) and a bystander (off court, closer) are both detected; the
        track must stay on its player."""
        tracker = _make_tracker(max_distance=250.0)
        (tid,) = _seed_four(tracker, [(500, 400)])
        out = tracker.update([_det(390, 400), _det(620, 400)], None, ball_active=True)
        by_id = {o["track_id"]: o for o in out}
        assert by_id[tid]["center"] == [620.0, 400.0]
        # the bystander is not admitted as a new track either
        assert len(out) == 1

    def test_f146_recovery_track_steps_back_to_returning_player(self):
        """The e6 f142->f146 sequence: the player's detection blips one frame
        and a bystander takes the track (no in-court alternative -- allowed);
        when the player is detected in court again while the bystander is still
        there, the track must step back onto the player."""
        tracker = _make_tracker(max_distance=250.0)
        (tid,) = _seed_four(tracker, [(500, 400)])
        # player blips; only the nearby off-court walker is detected
        out = tracker.update([_det(390, 400)], None, ball_active=True)
        by_id = {o["track_id"]: o for o in out}
        assert by_id[tid]["center"] == [390.0, 400.0]
        # player returns while the walker is still detected: court wins
        out = tracker.update([_det(390, 400), _det(500, 400)], None, ball_active=True)
        by_id = {o["track_id"]: o for o in out}
        assert by_id[tid]["center"] == [500.0, 400.0]

    def test_off_court_continuation_still_works_without_in_court_option(self):
        """The penalty only reorders preferences; with NO in-court detection
        the off-court continuation proceeds exactly as before (grace/hold
        rules in _may_feed_track are untouched)."""
        tracker = _make_tracker(max_distance=250.0)
        (tid,) = _seed_four(tracker, [(500, 400)])
        out = tracker.update([_det(390, 400)], None, ball_active=True)
        by_id = {o["track_id"]: o for o in out}
        assert by_id[tid]["center"] == [390.0, 400.0]
        assert not by_id[tid].get("predicted", False)

    def test_zero_penalty_restores_distance_only_preference(self):
        tracker = _make_tracker(max_distance=250.0, off_court_cost_penalty_px=0.0)
        (tid,) = _seed_four(tracker, [(500, 400)])
        out = tracker.update([_det(390, 400), _det(620, 400)], None, ball_active=True)
        by_id = {o["track_id"]: o for o in out}
        assert by_id[tid]["center"] == [390.0, 400.0]

    def test_uncalibrated_court_has_no_penalty(self):
        tracker = _make_tracker(max_distance=250.0, court_calibration=None)
        (tid,) = _seed_four(tracker, [(500, 400)])
        out = tracker.update([_det(390, 400), _det(620, 400)], None, ball_active=True)
        by_id = {o["track_id"]: o for o in out}
        assert by_id[tid]["center"] == [390.0, 400.0]

    def test_chain_swap_still_prefers_full_matching(self):
        """The penalty must not break Hungarian's global structure: a second
        track whose player is gone may still chain onto the off-court
        detection (that beats leaving it unmatched) -- but the first track
        keeps its in-court player."""
        tracker = _make_tracker(max_distance=250.0)
        ids = _seed_four(tracker, [(500, 400), (300, 400)])
        tid_a, tid_b = ids[0], ids[1]
        out = tracker.update([_det(390, 400), _det(620, 400)], None, ball_active=True)
        by_id = {o["track_id"]: o for o in out}
        assert by_id[tid_a]["center"] == [620.0, 400.0]   # in-court player
        assert by_id[tid_b]["center"] == [390.0, 400.0]   # off-court chain
