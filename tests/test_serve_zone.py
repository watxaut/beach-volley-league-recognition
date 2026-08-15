"""Tests for serve-zone admission + bootstrap seed dedup + vertical coast damping.

Serve-zone admission exists because the serving player stands OFF-court behind
their baseline at video/rally start: strict foot-in-court admission can never
track them (entreno_3: the server was detected at conf ~0.9 continuously yet
untracked f10-175, holding the whole serve window out of action recognition).
The serve zone is the single sanctioned off-court admission path.
"""
from __future__ import annotations

import numpy as np

from src.detection.court_calibration import CourtCalibration
from src.tracking.player_tracker import PlayerTracker


# Real entreno_3 calibration (perspective trapezoid) -- keeps the geometry
# honest against the video that motivated the feature.
_CORNERS = [[532, 486], [1217, 498], [1913, 950], [7, 910]]
_MIDCOURT = [[386, 592], [1386, 613]]
_FRAME = (1080, 1920)


def _real_court() -> CourtCalibration:
    court = CourtCalibration()
    court.calibrate_from_points(_CORNERS, _MIDCOURT, _FRAME)
    return court


# --- Court geometry ---

class TestServeZoneGeometry:
    def test_point_behind_near_baseline_is_team_a_zone(self):
        court = _real_court()
        # entreno_3 f0: the server's actual foot (~0.3m behind the near baseline,
        # within the sidelines).
        assert court.is_in_serve_zone((1299, 999)) == "A"

    def test_point_behind_far_baseline_is_team_b_zone(self):
        court = _real_court()
        # ~0.3m beyond the far baseline (the far side is perspective-compressed,
        # so this is only a few pixels above the baseline).
        assert court.is_in_serve_zone((874, 489)) == "B"

    def test_in_court_point_is_not_in_zone(self):
        court = _real_court()
        assert court.is_in_serve_zone((900, 700)) is None

    def test_deep_behind_baseline_is_outside_zone(self):
        court = _real_court()
        # ~4m behind the near baseline (beyond the 3m depth).
        assert court.is_in_serve_zone((1300, 1900)) is None

    def test_beside_the_court_is_outside_zone(self):
        court = _real_court()
        # ~1.1m beyond the sideline (past the 1m side margin), just behind the
        # near baseline: laterally out, not a serve spot.
        assert court.is_in_serve_zone((-300, 930)) is None
        assert court.is_in_serve_zone((2200, 950)) is None

    def test_corner_serve_positions_are_in_zone(self):
        court = _real_court()
        # Within the 1m side margin behind the baseline: a legal corner serve.
        assert court.is_in_serve_zone((-250, 940)) == "A"
        assert court.is_in_serve_zone((1700, 960)) == "A"

    def test_uncalibrated_court_has_no_zone(self):
        assert CourtCalibration().is_in_serve_zone((100, 100)) is None


# --- Tracker admission ---

class _ServeCourt:
    """Fake court: foot x in [400, 1200] is on the court; x in [1220, 1340] is
    the (near-baseline) serve zone; anything else is bystander territory."""

    is_calibrated = True

    def foot_point(self, bbox):
        return (int((bbox[0] + bbox[2]) / 2), int(bbox[3]))

    def is_point_in_court(self, point):
        return 400 <= point[0] <= 1200

    def is_in_serve_zone(self, point, depth_m=3.0, side_margin_m=1.0):
        return "A" if 1220 <= point[0] <= 1340 else None

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
        court_calibration=_ServeCourt(),
        off_court_grace_frames=5,
    )
    params.update(overrides)
    tracker = PlayerTracker(**params)
    tracker._initialized = True
    tracker.frame_count = 100
    return tracker


IN_COURT = [(500, 400), (700, 400), (900, 400)]
SERVER_X = 1280  # inside the fake serve zone
BYSTANDER_X = 1500  # off-court, outside the zone


class TestServeZoneAdmission:
    def test_server_admitted_when_slot_free(self):
        """The entreno_3 scenario: 3 players tracked, the server detected at
        conf 0.9 behind the baseline -> gets the free 4th slot immediately."""
        tracker = _make_tracker()
        for cx, cy in IN_COURT:
            tracker._create_track(_det(cx, cy), require_court_admission=False)

        server = _det(SERVER_X, 400)
        out = tracker.update([_det(cx, cy) for cx, cy in IN_COURT] + [server], None)
        server_tracks = [o for o in out if o["bbox"] == server["bbox"]]
        assert server_tracks, "serve-zone detection must open a track when a slot is free"
        assert not server_tracks[0].get("predicted", False)

    def test_server_not_admitted_when_roster_full(self):
        tracker = _make_tracker()
        for cx, cy in IN_COURT + [(1100, 400)]:
            tracker._create_track(_det(cx, cy), require_court_admission=False)

        out = tracker.update(
            [_det(cx, cy) for cx, cy in IN_COURT + [(1100, 400)]] + [_det(SERVER_X, 400)],
            None,
        )
        assert len(tracker.tracks) == 4
        assert _det(SERVER_X, 400)["bbox"] not in [tuple(o["bbox"]) for o in out]

    def test_out_of_zone_off_court_detection_still_rejected(self):
        """The bystander guard must not regress: off-court AND outside the serve
        zone can never open a track, even with a free slot."""
        tracker = _make_tracker()
        for cx, cy in IN_COURT:
            tracker._create_track(_det(cx, cy), require_court_admission=False)

        bystander = _det(BYSTANDER_X, 400)
        out = tracker.update([_det(cx, cy) for cx, cy in IN_COURT] + [bystander], None)
        assert len(tracker.tracks) == 3
        assert bystander["bbox"] not in [o["bbox"] for o in out]

    def test_admission_can_be_disabled(self):
        tracker = _make_tracker(serve_zone_enabled=False)
        for cx, cy in IN_COURT:
            tracker._create_track(_det(cx, cy), require_court_admission=False)

        out = tracker.update(
            [_det(cx, cy) for cx, cy in IN_COURT] + [_det(SERVER_X, 400)], None
        )
        assert len(tracker.tracks) == 3

    def test_inadmissible_detection_does_not_burn_dormant_slot(self):
        """Create-loop ordering: eviction may only run for a detection that
        would pass admission -- an off-court bystander must not force a dormant
        id out of the gallery and then be rejected itself."""
        tracker = _make_tracker(max_disappeared=3, gallery_evict_min_hold_frames=5)
        ids = [tracker._create_track(_det(cx, cy), require_court_admission=False)
               for cx, cy in IN_COURT + [(1100, 400)]]
        lost = ids[3]
        for _ in range(12):  # id 4 retires dormant, past its min-hold
            tracker.update([_det(cx, cy) for cx, cy in IN_COURT], None)
        assert lost in tracker.gallery

        tracker.update(
            [_det(cx, cy) for cx, cy in IN_COURT] + [_det(BYSTANDER_X, 400)], None
        )
        assert lost in tracker.gallery, "inadmissible detection must not evict a dormant id"

    def test_server_keeps_id_when_walking_into_court(self):
        """Admission behind the baseline is not a dead end: the same id must
        survive the walk into court (continuous observation)."""
        tracker = _make_tracker()
        for cx, cy in IN_COURT:
            tracker._create_track(_det(cx, cy), require_court_admission=False)

        out = tracker.update(
            [_det(cx, cy) for cx, cy in IN_COURT] + [_det(SERVER_X, 400)], None
        )
        server_id = next(o["track_id"] for o in out if o["center"][0] == SERVER_X)

        # Server steps in (foot in court), right edge of the court.
        out = tracker.update(
            [_det(cx, cy) for cx, cy in IN_COURT] + [_det(1180, 400)], None
        )
        by_id = {o["track_id"]: o for o in out}
        assert server_id in by_id
        assert by_id[server_id]["center"][0] == 1180
        assert not by_id[server_id].get("predicted", False)


class TestServeZoneFeeding:
    def test_never_in_court_track_refeeds_only_from_zone(self):
        """A serve-zone seed (never in court) may be continued out-of-court
        only from the serve zone itself after a gap -- not by an arbitrary
        off-court bystander (the entreno_1 hijack vector)."""
        tracker = _make_tracker()
        for cx, cy in IN_COURT:
            tracker._create_track(_det(cx, cy), require_court_admission=False)
        out = tracker.update(
            [_det(cx, cy) for cx, cy in IN_COURT] + [_det(SERVER_X, 400)], None
        )
        server_id = next(o["track_id"] for o in out if o["center"][0] == SERVER_X)
        track = tracker.tracks[server_id]
        assert track["last_in_court_frame"] is None

        # Gap (server undetected for 2 frames -> no continuous match), then an
        # in-zone detection: OK.
        tracker.frame_count += 2
        assert tracker._may_feed_track(track, _det(SERVER_X + 10, 400)) is True
        # Same gap, but an out-of-zone off-court detection: blocked.
        assert tracker._may_feed_track(track, _det(BYSTANDER_X, 400)) is False


# --- Bootstrap seed dedup ---

class TestBootstrapSeedDedup:
    def test_split_cluster_does_not_inflate_roster(self):
        """k-means is forced to k=4 even with one person on court; the duplicate
        clusters resolve to the SAME seed detection and must not lock 4 tracks
        (the entreno_3 phantom-slot bug that kept the server out)."""
        tracker = PlayerTracker(
            max_players=4,
            court_calibration=_ServeCourt(),
            bootstrap_min_window=8,
            bootstrap_ball_required=True,
            init_frames=60,
        )
        for _ in range(10):
            out = tracker.update([_det(600, 400)], None, ball_active=True)
        assert tracker._initialized
        assert len(tracker.tracks) == 1, "duplicate seeds on one person must be deduped"

    def test_four_distinct_people_still_lock_four(self):
        tracker = PlayerTracker(
            max_players=4,
            court_calibration=_ServeCourt(),
            bootstrap_min_window=8,
            bootstrap_ball_required=True,
            init_frames=60,
        )
        four = [(500, 400), (700, 400), (900, 400), (1100, 400)]
        for _ in range(10):
            tracker.update([_det(cx, cy) for cx, cy in four], None, ball_active=True)
        assert tracker._initialized
        assert len(tracker.tracks) == 4


# --- Vertical coast damping ---

class TestCoastVerticalDamping:
    def test_ghost_does_not_ride_jump_velocity(self):
        """A track lost mid-jump must not keep floating upward: vertical coast
        velocity is damped far harder than horizontal (players land near their
        takeoff spot)."""
        tracker = _make_tracker(serve_zone_enabled=False, court_calibration=None)
        tracker._initialized = True
        (tid,) = [tracker._create_track(_det(600, 400), require_court_admission=False)]
        track = tracker.tracks[tid]
        track["velocity"] = [10.0, -20.0]  # moving right and UP (jump takeoff)
        y0 = track["center"][1]
        x0 = track["center"][0]

        for _ in range(5):
            tracker._coast_step(track)

        rise = y0 - track["center"][1]
        run = track["center"][0] - x0
        # Without damping the rise over 5 steps would be ~68px (decay 0.85);
        # with damping=0.5 it is ~21px. Horizontal keeps most of its motion.
        assert rise < 30, f"ghost box rose {rise}px -- upward coast is not damped"
        assert run > 25, "horizontal coast motion must survive (re-acquisition gating)"

    def test_downward_coast_is_not_damped(self):
        """Running toward the camera along the court axis is image-DOWNWARD:
        it is real ground-plane motion and must coast at the normal decay
        (damping it fragmented far-side ids through occlusions on entreno_1)."""
        tracker = _make_tracker(coast_vertical_damping=0.5, court_calibration=None)
        tracker._initialized = True
        (tid,) = [tracker._create_track(_det(600, 400), require_court_admission=False)]
        track = tracker.tracks[tid]
        track["velocity"] = [0.0, 20.0]
        y0 = track["center"][1]
        for _ in range(5):
            tracker._coast_step(track)
        assert (track["center"][1] - y0) > 50  # ~68px: normal decay only

    def test_damping_one_recovers_old_behaviour(self):
        tracker = _make_tracker(coast_vertical_damping=1.0, court_calibration=None)
        tracker._initialized = True
        (tid,) = [tracker._create_track(_det(600, 400), require_court_admission=False)]
        track = tracker.tracks[tid]
        track["velocity"] = [0.0, -20.0]
        y0 = track["center"][1]
        for _ in range(5):
            tracker._coast_step(track)
        assert (y0 - track["center"][1]) > 50  # ~68px with decay only
