"""Tests for the squatter review (sideline straddlers, entreno_7 class).

A bystander who seeds a track while STRADDLING the sideline reads "in court"
for a dense early run (e7: f47-79 at 7.87-7.99 m), so strict admission cannot
refuse the seed and the off-court hold horizon only stops the continuous
feeding long after. The review expires a track whose LIFETIME in-court FEEDING
fraction stays under min_in_court_frac once it is review_frames old. Expiry is
to the gallery with a ``squatter`` flag -- NOT a hard-remove (a real player
off-court between points on match footage stays fail-safe recoverable): every
restore path skips the flagged entry, it is immediately evictable for a real
candidate, and the expelled track's sampled world foot positions block
NEW-track admission nearby (in-court re-admission attempts read 7.84-7.99 m).
"""
from __future__ import annotations

from collections import deque

from src.tracking.player_tracker import PlayerTracker


class _WorldCourt:
    """Fake calibrated court WITH a ground mapping: image x 400..1200 is the
    court (world x 0..8 m, 100 px per metre); y maps at 100 px per metre.
    world_body_size is constant so the ensemble signature has its
    frame-independent channels (height + proportions) at full similarity."""

    is_calibrated = True

    def foot_point(self, bbox):
        return (int((bbox[0] + bbox[2]) / 2), int(bbox[3]))

    def is_point_in_court(self, point):
        return 400 <= point[0] <= 1200

    def get_team_for_bbox(self, bbox):
        return "A" if self.is_point_in_court(self.foot_point(bbox)) else "B"

    def world_body_size(self, bbox):
        return {"world_height": 1.8, "world_width": 0.5, "ratio": 3.6}

    def image_to_world(self, point):
        return ((point[0] - 400) / 100.0, point[1] / 100.0)


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
        max_disappeared=200,  # long: tests must reach the review, not retirement
        max_distance=250.0,
        coast_extrapolation_cap=4,
        court_calibration=_WorldCourt(),
        off_court_grace_frames=5,
        off_court_hold_frames=90,
    )
    params.update(overrides)
    tracker = PlayerTracker(**params)
    tracker._initialized = True
    tracker.frame_count = 100
    return tracker


def _flagged_entry(tracker, cx, cy, samples=(9.0, 4.0)):
    """A squatter-flagged gallery entry. Foot samples default FAR from the
    entry position so the restore-skip is tested in isolation from the
    admission cooldown."""
    det = _det(cx, cy)
    return {
        "bbox": det["bbox"],
        "center": [float(cx), float(cy)],
        "velocity": [0.0, 0.0],
        "histogram": None,
        "head_histogram": None,
        "world_height_samples": deque([1.8], maxlen=30),
        "world_width_samples": deque([0.5], maxlen=30),
        "team_votes": deque(["A"], maxlen=15),
        "retired_frame": tracker.frame_count,
        "created_frame": tracker.frame_count - 300,
        "fed_frames": 100,
        "in_court_fed_frames": 10,
        "foot_world_samples": deque([samples], maxlen=12),
        "squatter": True,
    }


class _NoSizeCourt(_WorldCourt):
    """Same court without the ground-plane body size: the ensemble signature
    loses its frame-independent channels, so appearance re-acquisition can
    never fire and tests reach the NEW-track/eviction path they target."""

    def world_body_size(self, bbox):
        return None


class TestReviewFires:
    def test_straddler_expired_at_review_tick_and_flagged(self):
        """Continuously-fed out-of-court track: active one frame before its
        review tick, expired + flagged exactly at the tick, foot samples on
        the admission cooldown."""
        tracker = _make_tracker()
        tid = tracker._create_track(_det(1300, 400), require_court_admission=False)
        assert tid == 1

        for _ in range(119):  # one frame short of the review tick
            tracker.update([_det(1300, 400)], None, ball_active=True)
        assert tid in tracker.tracks, "must survive until the review tick"

        tracker.update([_det(1300, 400)], None, ball_active=True)
        assert tid not in tracker.tracks, "expired at the review tick"
        assert tid in tracker.gallery
        assert tracker.gallery[tid]["squatter"] is True
        assert len(tracker._squatter_cooldown) > 0, "foot samples on cooldown"
        assert all(abs(cx - 9.0) < 1e-6 for cx, _ in tracker._squatter_cooldown)

    def test_min_fed_frames_floor(self):
        """fed < min_fed: the fraction has no floor -- survive even with age
        past the tick and a 0% in-court fraction."""
        tracker = _make_tracker()
        tid = tracker._create_track(_det(1300, 400), require_court_admission=False)
        track = tracker.tracks[tid]
        track["fed_frames"] = 19
        track["in_court_fed_frames"] = 0
        track["created_frame"] = tracker.frame_count - 200  # age >> tick
        tracker._expire_squatters()
        assert tid in tracker.tracks, "below the fed-frames noise floor"

        track["fed_frames"] = 20
        tracker._expire_squatters()
        assert tid in tracker.gallery
        assert tracker.gallery[tid]["squatter"] is True

    def test_real_player_eighty_percent_survives(self):
        """A real player in court 4 of every 5 frames (80% >> 35%) must never
        be expired, even continuously past the review tick."""
        tracker = _make_tracker()
        tid = tracker._create_track(_det(1100, 400), require_court_admission=False)
        for k in range(130):
            pos = (1300, 400) if k % 5 == 4 else (1100, 400)  # 1 off, 4 in
            tracker.update([_det(*pos)], None, ball_active=True)
        track = tracker.tracks[tid]
        assert track["fed_frames"] == 130
        assert track["in_court_fed_frames"] == 104
        assert tid in tracker.tracks and tid not in tracker.gallery

    def test_offcourt_then_incourt_survives(self):
        """The server path: seeded off-court, fed there for 60 frames, then
        plays in court. Lifetime fraction 80/140 = 57% -> survives."""
        tracker = _make_tracker()
        tid = tracker._create_track(_det(1300, 400), require_court_admission=False)
        for _ in range(60):
            tracker.update([_det(1300, 400)], None, ball_active=True)
        for _ in range(80):
            tracker.update([_det(1100, 400)], None, ball_active=True)
        track = tracker.tracks[tid]
        assert track["in_court_fed_frames"] / track["fed_frames"] > 0.35
        assert tid in tracker.tracks and tid not in tracker.gallery

    def test_ghost_coast_frames_never_dilute(self):
        """Fed 40 in-court frames, then occluded for 100 (ghost/coast): the
        counters must freeze -- if coast frames diluted the fraction it would
        read 40/141 < 0.35 and wrongly expire a 100%-in-court track."""
        tracker = _make_tracker()
        tid = tracker._create_track(_det(900, 400), require_court_admission=False)
        for _ in range(40):
            tracker.update([_det(900, 400)], None, ball_active=True)
        for _ in range(100):
            tracker.update([], None, ball_active=False)
        assert tracker.tracks[tid]["fed_frames"] == 40, "coast must not feed"

        tracker.update([_det(900, 400)], None, ball_active=True)  # player back
        track = tracker.tracks[tid]
        assert track["fed_frames"] == 41
        assert track["in_court_fed_frames"] == 41
        assert tid in tracker.tracks and tid not in tracker.gallery

    def test_uncalibrated_court_is_a_noop(self):
        """No ground plane -> no in-court fraction -> the review can never
        fire (and _track_admission_ok stays court-free)."""
        tracker = _make_tracker(court_calibration=None)
        tid = tracker._create_track(_det(900, 400), require_court_admission=False)
        track = tracker.tracks[tid]
        track["fed_frames"] = 500
        track["in_court_fed_frames"] = 0
        track["created_frame"] = tracker.frame_count - 400
        tracker._expire_squatters()
        assert tid in tracker.tracks

    def test_disabled_flag_restores_old_behaviour(self):
        """squatter_enabled=False: identical forced-squatter state survives
        (the documented rollback)."""
        tracker = _make_tracker(squatter_enabled=False)
        tid = tracker._create_track(_det(1300, 400), require_court_admission=False)
        track = tracker.tracks[tid]
        track["fed_frames"] = 500
        track["in_court_fed_frames"] = 0
        track["created_frame"] = tracker.frame_count - 400
        tracker._expire_squatters()
        assert tid in tracker.tracks


class TestFlagInterlocks:
    def test_position_restore_pass_skips_flagged(self):
        """A detection exactly on a flagged entry's position would restore it
        via the position pass -- the flag must block that; the detection goes
        through new-track admission instead."""
        tracker = _make_tracker()
        tracker._create_track(_det(500, 400), require_court_admission=False)
        tracker.gallery[2] = _flagged_entry(tracker, 900, 400)

        out = tracker.update([_det(500, 400), _det(900, 400)], None, ball_active=True)
        by_id = {o["track_id"]: o for o in out}
        assert 2 not in by_id and 2 not in tracker.tracks, "no restore of a flagged id"
        assert tracker.gallery[2]["squatter"] is True, "flagged entry survives"
        assert 3 in by_id, "the person is tracked under a NEW id instead"
        assert not by_id[3].get("reacquired", False)
        assert by_id[3]["center"] == [900.0, 400.0]

    def test_appearance_restore_pass_skips_flagged(self):
        """Same via the appearance pass: position gate fails (400 px away) but
        the ensemble signature matches perfectly (height+proportions channels)
        -- the flag must still block the restore."""
        tracker = _make_tracker()
        tracker._create_track(_det(500, 400), require_court_admission=False)
        tracker.gallery[2] = _flagged_entry(tracker, 500, 400)

        out = tracker.update([_det(500, 400), _det(900, 400)], None, ball_active=True)
        by_id = {o["track_id"]: o for o in out}
        assert 2 not in by_id and 2 not in tracker.tracks
        assert tracker.gallery[2]["squatter"] is True
        assert 3 in by_id and not by_id[3].get("appearance_matched", False)

    def test_flagged_entry_evictable_immediately(self):
        """Slot pressure + a flagged entry: evicted on the spot (bypassing
        gallery_evict_min_hold_frames) so the real in-court candidate gets the
        slot NOW (e7: otherwise slot 4 stays closed past the review tick)."""
        tracker = _make_tracker(court_calibration=_NoSizeCourt())
        for cx in (500, 700, 900):
            tracker._create_track(_det(cx, 400), require_court_admission=False)
        tracker.gallery[4] = _flagged_entry(tracker, 1100, 400)

        newcomer = _det(1100, 700)
        out = tracker.update(
            [_det(cx, 400) for cx in (500, 700, 900)] + [newcomer],
            None,
            ball_active=True,
        )
        by_id = {o["track_id"]: o for o in out}
        assert 4 in tracker.tracks, "flagged entry evicted, slot taken now"
        assert tracker.gallery == {}, "flagged entry did not linger"
        assert tuple(newcomer["bbox"]) in {tuple(o["bbox"]) for o in out}
        assert not by_id[4].get("reacquired", False), "slot taken by NEW track"

    def test_eviction_prefers_flagged_over_protected_normal(self):
        """With both a fresh (min-hold-protected) normal entry and a flagged
        entry in the gallery, the flagged one is the one evicted."""
        tracker = _make_tracker(court_calibration=_NoSizeCourt())
        for cx in (500, 700):
            tracker._create_track(_det(cx, 400), require_court_admission=False)
        tracker.gallery[3] = {
            **_flagged_entry(tracker, 900, 400),
            "squatter": False,
            "retired_frame": tracker.frame_count,  # fresh: normally protected
        }
        tracker.gallery[4] = _flagged_entry(tracker, 1100, 400)

        tracker.update(
            [_det(500, 400), _det(700, 400), _det(1100, 700)], None, ball_active=True
        )
        assert 4 not in tracker.gallery, "flagged entry evicted first"
        assert 3 in tracker.gallery, "protected normal entry survives"
        assert 4 in tracker.tracks

    def test_restored_track_reloads_counters(self):
        """A LEGITIMATE restore resumes the lifetime counters and the age
        clock -- no fresh 120-frame review amnesty."""
        tracker = _make_tracker()
        tracker._create_track(_det(500, 400), require_court_admission=False)
        created_before = tracker.frame_count - 300
        tracker.gallery[2] = {
            **_flagged_entry(tracker, 900, 400),
            "squatter": False,
            "fed_frames": 100,
            "in_court_fed_frames": 90,
            "created_frame": created_before,
        }
        tracker.update([_det(500, 400), _det(900, 400)], None, ball_active=True)
        assert 2 in tracker.tracks, "unflagged entry restores normally"
        track = tracker.tracks[2]
        assert track["fed_frames"] == 101, "counter resumed (+1 for the restore feed)"
        assert track["in_court_fed_frames"] == 91
        assert track["created_frame"] == created_before, "age kept"


class TestCooldown:
    def _straddler_with_drift(self):
        """Run the e7-shaped scenario: in-court-straddling start near the
        sideline (world 7.6 m), then a drift out to 9.0 m, continuously fed
        until the review expires it. Returns the tracker post-expiry."""
        tracker = _make_tracker()
        tid = tracker._create_track(_det(1160, 400), require_court_admission=False)
        for _ in range(35):  # in-court straddle: world x = 7.6 m
            tracker.update([_det(1160, 400)], None, ball_active=True)
        for _ in range(120 - 35):  # drifts out: world x = 9.0 m (tick at #120)
            tracker.update([_det(1300, 400)], None, ball_active=True)
        assert tid not in tracker.tracks, "drifting straddler expired"
        assert tracker.gallery[tid]["squatter"] is True
        return tracker

    def test_cooldown_blocks_incourt_readmission_within_radius(self):
        tracker = self._straddler_with_drift()
        # In-court candidate (x=1190 -> world 7.9 m) within 0.5 m of the 7.6 m
        # samples: blocked, DESPITE the foot reading strictly in court.
        assert tracker._detection_in_court(_det(1190, 400)) is True
        assert tracker._track_admission_ok(_det(1190, 400)) is False

    def test_cooldown_admits_far_away(self):
        tracker = self._straddler_with_drift()
        assert tracker._track_admission_ok(_det(600, 400)) is True

    def test_cooldown_never_touches_existing_tracks(self):
        """The cooldown gates NEW-track admission only -- a track that already
        exists at the blocked spot keeps being fed."""
        tracker = self._straddler_with_drift()
        tid = tracker._create_track(_det(1190, 400), require_court_admission=False)
        out = tracker.update([_det(1190, 400)], None, ball_active=True)
        assert tid in {o["track_id"] for o in out}
        assert not out[0].get("predicted", False), "fed, not coasted"


class TestBootstrapSeeds:
    def test_seed_counters_start_at_zero(self):
        tracker = _make_tracker()
        tracker.frame_count = 177
        tid = tracker._create_track(_det(900, 400), require_court_admission=False)
        track = tracker.tracks[tid]
        assert track["fed_frames"] == 0
        assert track["in_court_fed_frames"] == 0
        assert list(track["foot_world_samples"]) == []
        assert track["created_frame"] == 177

    def test_bootstrap_lock_sets_created_frame(self):
        """A bootstrap-created squatter is covered: created_frame is the lock
        frame, so the review clock starts at the lock (not at frame 0)."""
        tracker = PlayerTracker(
            max_players=4,
            bootstrap_min_window=2,
            bootstrap_ball_required=False,
            court_calibration=_WorldCourt(),
        )
        dets = [_det(cx, cy) for cx, cy in [(500, 400), (700, 400), (900, 400), (1100, 400)]]
        tracker.update(dets, None, ball_active=True)
        tracker.update(dets, None, ball_active=True)  # lock happens here
        assert tracker._initialized
        assert len(tracker.tracks) == 4
        for track in tracker.tracks.values():
            assert track["created_frame"] == tracker.frame_count
            assert track["fed_frames"] >= 0  # counters exist from the seed
