"""Tests for the spike outcome/zone analyzer and its overlay rendering.

Fixtures follow tests/test_team_attribution.py: the real entreno_3 court
calibration, synthetic frame-ordered ball/player streams fed through
``SpikeAnalyzer.observe``. Flights are synthetic but obey the physics the
analyzer keys on: descent >= DESCENT_MIN_PX per frame, bounces rise >=
BOUNCE_RISE_PX, dig lofts >= DIG_LOFT_PX.
"""

import numpy as np
import pytest

from src.analysis.spike_analyzer import SpikeAnalyzer
from src.detection.court_calibration import CourtCalibration
from src.output_gen import overlay


@pytest.fixture
def court():
    return CourtCalibration("calibrations/video_entreno_3.json")


@pytest.fixture
def analyzer(court):
    return SpikeAnalyzer(court)


def _ball(x, y, w=24):
    return {"center": (x, y), "bbox": [x - w, y - w, x + w, y + w],
            "is_predicted": False}


def _player(tid, x, y, team, predicted=False):
    return {"track_id": tid, "bbox": [x - 30, y - 90, x + 30, y],
            "center": (x, y - 45), "team": team, "predicted": predicted}


def _spike_ev(contact, tid=1, team="B", player_id=2, cp=(900.0, 520.0)):
    return {"action": "spike", "frame_number": contact, "track_id": tid,
            "player_id": player_id, "team": team, "contact_point": list(cp),
            "player_center": (cp[0], cp[1])}


# --------------------------------------------------------------------- #
# Zone grid
# --------------------------------------------------------------------- #

class TestWorldPointToZone:
    def test_all_eighteen_zones(self, court):
        # Side A (near, wy >= 8): columns run 3-2-1 for wx low-mid-high.
        assert court.world_point_to_zone(1.0, 8.5) == (3, "A")
        assert court.world_point_to_zone(4.0, 8.5) == (2, "A")
        assert court.world_point_to_zone(7.0, 8.5) == (1, "A")
        assert court.world_point_to_zone(1.0, 11.0) == (6, "A")
        assert court.world_point_to_zone(4.0, 11.0) == (5, "A")
        assert court.world_point_to_zone(7.0, 11.0) == (4, "A")
        assert court.world_point_to_zone(1.0, 14.5) == (9, "A")
        assert court.world_point_to_zone(4.0, 14.5) == (8, "A")
        assert court.world_point_to_zone(7.0, 14.5) == (7, "A")
        # Side B (far): columns run 1-2-3 (mirrored the other way).
        assert court.world_point_to_zone(1.0, 7.5) == (1, "B")
        assert court.world_point_to_zone(4.0, 7.5) == (2, "B")
        assert court.world_point_to_zone(7.0, 7.5) == (3, "B")
        assert court.world_point_to_zone(1.0, 5.0) == (4, "B")
        assert court.world_point_to_zone(4.0, 5.0) == (5, "B")
        assert court.world_point_to_zone(7.0, 5.0) == (6, "B")
        assert court.world_point_to_zone(1.0, 2.5) == (7, "B")
        assert court.world_point_to_zone(4.0, 2.5) == (8, "B")
        assert court.world_point_to_zone(7.0, 2.5) == (9, "B")

    def test_180_degree_symmetry(self, court):
        """Turning the court 180 degrees preserves the zone NUMBER (each side
        numbers from its own facing direction) while swapping the side."""
        W, L = court.BEACH_COURT_WIDTH_M, court.BEACH_COURT_LENGTH_M
        for wx in (1.0, 4.0, 7.0):
            for wy in (8.5, 11.0, 14.5):
                a = court.world_point_to_zone(wx, wy)
                b = court.world_point_to_zone(W - wx, L - wy)
                assert a[0] == b[0]
                assert {a[1], b[1]} == {"A", "B"}

    def test_boundaries_and_outside(self, court):
        assert court.world_point_to_zone(4.0, 8.0) == (2, "A")   # on the net line -> A
        assert court.world_point_to_zone(8.0, 12.0) == (4, "A")  # right sideline clamps
        assert court.world_point_to_zone(20.0, 8.0) is None
        assert court.world_point_to_zone(4.0, 20.0) is None
        assert court.world_point_to_zone(-0.9, 12.0)[1] == "A"   # margin clamps in


class TestGetCourtZone:
    def test_real_calibration_probes(self, court):
        # Probes verified against the entreno_3 homography: near-centre maps
        # to ~(4.2, 13.0), far-centre to ~(3.9, 4.8).
        assert court.get_court_zone((960, 760)) == (5, "A")
        assert court.get_court_zone((870, 550)) == (5, "B")

    def test_uncalibrated_returns_none(self):
        assert CourtCalibration().get_court_zone((100, 100)) is None


# --------------------------------------------------------------------- #
# Spike type (ascent-based)
# --------------------------------------------------------------------- #

def _feed_flight(an, contact, points, spiker=None, spike_cp=(900.0, 400.0)):
    """Feed pre-contact frames, the flight, and the (late) spike event."""
    for f in range(contact - 14, contact + 1):
        an.observe(f, _ball(880 - (contact - f), 300 + (contact - f) * 6),
                   [spiker or _player(1, 870, 550, "B")], [])
    for (i, (x, y)) in enumerate(points):
        an.observe(contact + 1 + i, _ball(x, y), [_player(1, 870, 550, "B")], [])
    an.observe(contact + 15, None, [_player(1, 870, 550, "B")],
               [_spike_ev(contact, cp=spike_cp)])


class TestSpikeType:
    def test_rainbow_is_touch(self, analyzer):
        # Rises 250 px above the contact, then descends into the near half.
        arc = [(900, 380), (905, 330), (910, 280), (915, 220), (920, 170),
               (925, 150), (930, 180), (935, 240), (940, 320), (945, 420),
               (948, 520), (950, 610), (952, 700)]
        _feed_flight(analyzer, 100, arc, spike_cp=(900.0, 400.0))
        for f in range(113, 126):
            analyzer.observe(f, None, [_player(1, 870, 550, "B")], [])
        rec = analyzer.spike_records()[0]
        assert rec["spike_type"] == "touch"
        assert rec["outcome"] == "kill"  # descends into the near half, quiet
        assert rec["landing_zone"]["side"] == "A"

    def test_flat_drive_is_hard(self, analyzer):
        # Never rises more than ~30 px; steep descent into the near half.
        drive = [(905, 545), (915, 575), (925, 610), (935, 650), (945, 695),
                 (952, 745), (956, 790)]
        _feed_flight(analyzer, 100, drive, spike_cp=(900.0, 520.0))
        for f in range(108, 122):
            analyzer.observe(f, None, [_player(1, 870, 550, "B")], [])
        rec = analyzer.spike_records()[0]
        assert rec["spike_type"] == "hard"
        assert rec["outcome"] == "kill"
        assert rec["landing_zone"]["side"] == "A"

    def test_type_known_early_for_touch(self, analyzer):
        arc = [(900, 380), (905, 300), (910, 220), (915, 160)]
        for f in range(86, 101):
            an2 = analyzer
            an2.observe(f, _ball(880, 340 + (f - 86) * 5), [_player(1, 870, 550, "B")], [])
        for (i, (x, y)) in enumerate(arc):
            an2.observe(101 + i, _ball(x, y), [_player(1, 870, 550, "B")], [])
        # Event arrives with the arc already developed -> type resolvable.
        an2.observe(116, None, [_player(1, 870, 550, "B")], [_spike_ev(100, cp=(900.0, 400.0))])
        assert analyzer.spike_type_for(100) == "touch"


# --------------------------------------------------------------------- #
# Outcome resolution
# --------------------------------------------------------------------- #

class TestOutcomes:
    def _drive_to_kill(self, an, landing_xy=(952, 760)):
        for f in range(86, 101):
            an.observe(f, _ball(890 - (100 - f), 380 + (100 - f) * 8),
                       [_player(1, 870, 550, "B")], [])
        flight = [(905, 545), (915, 580), (925, 620), (935, 665), (945, 710)]
        for (i, (x, y)) in enumerate(flight):
            an.observe(101 + i, _ball(x, y), [_player(1, 870, 550, "B")], [])
        return flight

    def test_bounce_in_court_is_kill(self, analyzer):
        self._drive_to_kill(analyzer)
        # Max-y sighting at f105 (945, 710) -> in court; bounce rises 25 px.
        analyzer.observe(106, _ball(948, 685), [_player(1, 870, 550, "B")], [])
        analyzer.observe(114, None, [_player(1, 870, 550, "B")],
                         [_spike_ev(100, cp=(900.0, 520.0))])
        rec = analyzer.spike_records()[0]
        assert rec["outcome"] == "kill"
        assert rec["landing_zone"]["side"] == "A"
        assert analyzer.kill_annotation(105) is not None
        assert analyzer.kill_annotation(105)[2].startswith("KILL A")
        assert analyzer.kill_annotation(140) is None  # past LABEL_PERSIST

    def test_landing_outside_is_out(self, analyzer):
        # Drive off the right sideline: x beyond the court's right edge.
        for f in range(86, 101):
            analyzer.observe(f, _ball(1500 - (100 - f) * 3, 400 + (100 - f) * 5),
                             [_player(1, 870, 550, "B")], [])
        flight = [(1560, 560), (1590, 610), (1620, 660), (1650, 715), (1675, 760)]
        for (i, (x, y)) in enumerate(flight):
            analyzer.observe(101 + i, _ball(x, y), [_player(1, 870, 550, "B")], [])
        analyzer.observe(106, _ball(1680, 735), [_player(1, 870, 550, "B")], [])
        analyzer.observe(114, None, [_player(1, 870, 550, "B")],
                         [_spike_ev(100, cp=(1540.0, 480.0))])
        rec = analyzer.spike_records()[0]
        assert rec["outcome"] == "out"

    def test_dig_loft_retroconverts_kill_to_dug(self, analyzer):
        self._drive_to_kill(analyzer)
        # Bounce signature closes the record as a kill at f105...
        analyzer.observe(106, _ball(948, 685), [_player(1, 870, 550, "B")], [])
        analyzer.observe(114, None, [_player(1, 870, 550, "B")],
                         [_spike_ev(100, cp=(900.0, 520.0))])
        assert analyzer.spike_records()[0]["outcome"] == "kill"
        # ...then the ball lofts high (a dig redirect, not a sand bounce) and
        # the opponent's dig event lands within the retro window.
        loft = [(945, 640), (940, 570), (935, 500), (930, 440)]
        for (i, (x, y)) in enumerate(loft):
            analyzer.observe(115 + i, _ball(x, y), [_player(2, 960, 780, "A")], [])
        analyzer.observe(130, None, [_player(2, 960, 780, "A")],
                         [{"action": "dig", "frame_number": 108, "track_id": 2,
                           "player_id": 1, "team": "A",
                           "contact_point": [948.0, 685.0],
                           "player_center": (948, 685)}])
        rec = analyzer.spike_records()[0]
        assert rec["outcome"] == "dug"
        assert rec["dug_zone"] == {"side": "A", "zone": 5}
        assert rec["landing_zone"] is None
        assert analyzer.kill_annotation(125) is None  # mark withdrawn

    def test_low_bounce_survives_later_contact(self, analyzer):
        """A real kill (small bounce, roll) must NOT convert on the next
        rally's reception contact."""
        self._drive_to_kill(analyzer)
        analyzer.observe(106, _ball(948, 690), [_player(1, 870, 550, "B")], [])
        analyzer.observe(107, _ball(950, 675), [_player(1, 870, 550, "B")], [])
        # Roll: tail not descending, small bounce only.
        analyzer.observe(108, _ball(952, 668), [_player(1, 870, 550, "B")], [])
        analyzer.observe(114, None, [_player(1, 870, 550, "B")],
                         [_spike_ev(100, cp=(900.0, 520.0))])
        assert analyzer.spike_records()[0]["outcome"] == "kill"
        analyzer.observe(130, None, [_player(2, 960, 780, "A")],
                         [{"action": "dig", "frame_number": 112, "track_id": 2,
                           "player_id": 1, "team": "A",
                           "contact_point": [952.0, 668.0],
                           "player_center": (960, 730)}])
        assert analyzer.spike_records()[0]["outcome"] == "kill"

    def test_block_follow_is_blocked(self, analyzer):
        for f in range(86, 101):
            analyzer.observe(f, _ball(890 - (100 - f), 380 + (100 - f) * 8),
                             [_player(1, 870, 550, "B"), _player(2, 900, 620, "A")], [])
        for (i, (x, y)) in enumerate([(905, 545), (915, 580), (925, 610), (930, 630)]):
            analyzer.observe(101 + i, _ball(x, y),
                             [_player(1, 870, 550, "B"), _player(2, 900, 620, "A")], [])
        analyzer.observe(115, None, [_player(1, 870, 550, "B")],
                         [_spike_ev(100, cp=(900.0, 520.0)),
                          {"action": "block", "frame_number": 104, "track_id": 2,
                           "player_id": 1, "team": "A",
                           "contact_point": [925.0, 610.0],
                           "player_center": (900, 570)}])
        rec = analyzer.spike_records()[0]
        assert rec["outcome"] == "blocked"
        assert rec["dug_zone"]["side"] == "A"

    def test_horizon_expires_to_unknown(self, analyzer):
        for f in range(86, 101):
            analyzer.observe(f, _ball(900, 400 + (f - 86) * 2),
                             [_player(1, 870, 550, "B")], [])
        analyzer.observe(115, None, [_player(1, 870, 550, "B")],
                         [_spike_ev(100, cp=(900.0, 430.0))])
        # Flat drifting ball: no descent, no bounce, no follow -> horizon.
        for f in range(116, 220):
            analyzer.observe(f, _ball(900 + (f - 116), 430), [_player(1, 870, 550, "B")], [])
        rec = analyzer.spike_records()[0]
        assert rec["outcome"] == "unknown"
        assert rec["spike_type"] == "hard"

    def test_dug_ball_dying_without_set_is_kill(self, analyzer):
        """Owner semantics: a dig that dies (ball falls, no set) makes the
        attack a KILL at the fall point."""
        self._drive_to_kill(analyzer)
        analyzer.observe(106, _ball(948, 685), [_player(1, 870, 550, "B")], [])
        analyzer.observe(114, None, [_player(1, 870, 550, "B")],
                         [_spike_ev(100, cp=(900.0, 520.0))])
        # Dig loft (retro-converts the bounce-kill to dug)...
        loft = [(945, 640), (940, 570), (935, 500), (930, 440), (928, 400),
                (927, 380)]
        for (i, (x, y)) in enumerate(loft):
            analyzer.observe(115 + i, _ball(x, y), [_player(2, 960, 780, "A")], [])
        analyzer.observe(130, None, [_player(2, 960, 780, "A")],
                         [{"action": "dig", "frame_number": 108, "track_id": 2,
                           "player_id": 1, "team": "A",
                           "contact_point": [948.0, 685.0],
                           "player_center": (948, 685)}])
        rec = analyzer.spike_records()[0]
        assert rec["outcome"] == "dug"
        # ...then the dug ball comes down and dies with NO set following.
        fall = [(926, 420), (924, 470), (922, 530), (920, 600), (918, 680),
                (917, 740), (916, 770), (918, 760)]
        for (i, (x, y)) in enumerate(fall):
            analyzer.observe(122 + i, _ball(x, y), [_player(2, 960, 780, "A")], [])
        rec = analyzer.spike_records()[0]
        assert rec["outcome"] == "dug"  # inside the confirmation window yet
        # After DUG_DEATH_CONFIRM_FRAMES with no loft and no set: KILL.
        for f in range(130, 150):
            analyzer.observe(f, None, [_player(2, 960, 780, "A")], [])
        rec = analyzer.spike_records()[0]
        assert rec["outcome"] == "kill"
        assert rec["landing_zone"]["side"] == "A"
        assert analyzer.kill_annotation(145) is not None
        assert analyzer.kill_annotation(145)[2].startswith("KILL A")

    def test_dug_ball_kept_up_by_set_stays_dug(self, analyzer):
        self._drive_to_kill(analyzer)
        analyzer.observe(106, _ball(948, 685), [_player(1, 870, 550, "B")], [])
        analyzer.observe(114, None, [_player(1, 870, 550, "B")],
                         [_spike_ev(100, cp=(900.0, 520.0))])
        loft = [(945, 640), (940, 570), (935, 500), (930, 440), (928, 400)]
        for (i, (x, y)) in enumerate(loft):
            analyzer.observe(115 + i, _ball(x, y), [_player(2, 960, 780, "A")], [])
        analyzer.observe(130, None, [_player(2, 960, 780, "A")],
                         [{"action": "dig", "frame_number": 108, "track_id": 2,
                           "player_id": 1, "team": "A",
                           "contact_point": [948.0, 685.0],
                           "player_center": (948, 685)}])
        # The defence sets the dug ball: the attack stays a plain dig.
        analyzer.observe(145, None, [_player(2, 960, 780, "A")],
                         [{"action": "set", "frame_number": 124, "track_id": 2,
                           "player_id": 1, "team": "A",
                           "contact_point": [928.0, 400.0],
                           "player_center": (960, 730)}])
        rec = analyzer.spike_records()[0]
        assert rec["outcome"] == "dug"
        assert analyzer.kill_annotation(129) is None

    def test_flush_resolves_trailing_flight(self, analyzer):
        for f in range(86, 101):
            analyzer.observe(f, _ball(890 - (100 - f), 380 + (100 - f) * 8),
                             [_player(1, 870, 550, "B")], [])
        for (i, (x, y)) in enumerate([(905, 545), (915, 580), (925, 620), (935, 665)]):
            analyzer.observe(101 + i, _ball(x, y), [_player(1, 870, 550, "B")], [])
        analyzer.observe(110, None, [_player(1, 870, 550, "B")],
                         [_spike_ev(100, cp=(900.0, 520.0))])
        analyzer.flush()
        rec = analyzer.spike_records()[0]
        assert rec["outcome"] == "kill"
        assert rec["landing_zone"]["side"] == "A"


class TestOriginZone:
    def test_takeoff_window_beats_airborne_contact_feet(self, analyzer):
        """A jumping spiker's feet at contact project deep; the pre-contact
        stance (closest to the net in TAKEOFF_WINDOW) is the true origin."""
        # Stance at (870, 550) = B5 for f88..f98; airborne/deeper from f99.
        for f in range(88, 99):
            analyzer.observe(f, None, [_player(1, 870, 550, "B")], [])
        for f in range(99, 103):
            analyzer.observe(f, None, [_player(1, 860, 460, "B")], [])
        analyzer.observe(115, None, [], [_spike_ev(100, cp=(900.0, 520.0))])
        analyzer.flush()
        rec = analyzer.spike_records()[0]
        assert rec["attack_zone"] == {"side": "B", "zone": 5}

    def test_falls_back_to_event_geometry(self, analyzer):
        analyzer.observe(115, None, [], [_spike_ev(100, cp=(870.0, 550.0))])
        analyzer.flush()
        rec = analyzer.spike_records()[0]
        assert rec["attack_zone"] == {"side": "B", "zone": 5}


# --------------------------------------------------------------------- #
# Trail rendering
# --------------------------------------------------------------------- #

class TestTrailRendering:
    def test_draw_ball_trail_fades_with_age(self):
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        # Age deltas between consecutive points stay under the gap limit.
        pts = [(50, 50, 0), (58, 58, 2), (66, 66, 4), (74, 74, 6), (82, 82, 60)]
        overlay.draw_ball_trail(frame, pts, max_age=45)
        fresh = frame[52:56, 52:56, 2].max()
        old = frame[68:72, 68:72, 2].max()
        dropped = frame[80:84, 80:84, 2].max()
        assert fresh > old > 0
        assert dropped == 0  # beyond max_age: nothing drawn

    def test_draw_ball_trail_leaves_background_untouched(self):
        """Regression (2026-09-01): blending must touch the LINE's pixels only
        -- an unmasked addWeighted darkened the whole ROI rectangle to a
        visible black box behind each segment."""
        frame = np.full((200, 200, 3), 200, dtype=np.uint8)
        overlay.draw_ball_trail(frame, [(50, 50, 0), (90, 50, 2)], max_age=45)
        # The line itself blends toward red...
        assert frame[48:53, 55:85, 2].max() > 210
        assert frame[48:53, 55:85, 0].min() < 190
        # ...while pixels inside the segment's ROI but off the line stay 200.
        assert (frame[45:47, 55:85] == 200).all()
        assert (frame[54:57, 55:85] == 200).all()

    def test_draw_ball_trail_skips_big_gaps(self):
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        pts = [(50, 100, 0), (60, 100, 2), (140, 100, 30)]  # 28f gap to the last
        overlay.draw_ball_trail(frame, pts, max_age=45)
        # Midpoint of the skipped segment must stay untouched.
        assert frame[95:105, 95:105, 2].max() == 0

    def test_typed_spike_colors_exist(self):
        assert overlay.ACTION_COLORS["spike hard"] == (0, 0, 255)
        assert overlay.ACTION_COLORS["spike touch"] == (0, 0, 255)

    def test_label_plan_re_add_upgrades(self):
        plan = overlay.LabelPlan()
        plan.add(1, 100, "spike", 0.5)
        plan.add(1, 100, "spike hard")
        assert plan.active(1, 105) == ("spike hard", None)
        # A different contact frame on the same track is untouched.
        plan.add(1, 140, "dig", 0.55)
        assert plan.active(1, 145) == ("dig", 0.55)

    def test_draw_kill_marker_paints(self):
        frame = np.zeros((200, 400, 3), dtype=np.uint8)
        overlay.draw_kill_marker(frame, 100, 100, "KILL A7")
        assert frame[80:130, 110:260, 2].max() > 0

    def test_trail_points_respect_render_frame(self, analyzer):
        for f in range(86, 101):
            analyzer.observe(f, _ball(890 - (100 - f), 380 + (100 - f) * 8),
                             [_player(1, 870, 550, "B")], [])
        for (i, (x, y)) in enumerate([(905, 545), (915, 580), (925, 620)]):
            analyzer.observe(101 + i, _ball(x, y), [_player(1, 870, 550, "B")], [])
        analyzer.observe(110, None, [_player(1, 870, 550, "B")],
                         [_spike_ev(100, cp=(900.0, 520.0))])
        early = analyzer.trail_points(102)   # only points at/before f102
        assert all(age >= 0 for (_x, _y, age) in early)
        assert len(early) <= 4
        late = analyzer.trail_points(103)
        assert len(late) == len(early) + 1
