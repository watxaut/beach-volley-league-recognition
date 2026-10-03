"""Tests for the live-debug signal/event side panel.

The panel is a DISPLAY-ONLY mirror of what ``FrameProcessor.process_frame``
already produced (``src/analysis/debug_panel.py`` + the snapshot plumbing in
``live_debug_processor``). These tests pin the three things that make it
trustworthy:

1. events are anchored on each action's TRUE contact frame, not the frame the
   look-ahead released it (the panel is only readable because the live render
   is ~3 s behind the producer);
2. the per-frame signals it prints are the pipeline's own values, read through
   guarded lookups that degrade to "-" instead of raising;
3. composing the panel never touches the video pixels or the saved file.
"""

import threading

import types

import cv2
import numpy as np
import pytest

import src.analysis.debug_panel as dp
from src.analysis.debug_panel import EventPlan, build_rows, compose
from src.analysis.live_debug_processor import LiveDebugProcessor
from src.output_gen import overlay
from src.recognition.action_classifier import ActionClassifier


def _frame(w=200, h=120):
    return np.full((h, w, 3), 200, dtype=np.uint8)


# --------------------------------------------------------------------- #
# EventPlan: contact-frame keying, window, ordering, thread safety
# --------------------------------------------------------------------- #

class TestEventPlan:
    def test_event_visible_on_its_contact_frame_only_after_ingest(self):
        p = EventPlan()
        p.add(241, "f241 SPIKE")
        assert p.at(241)[0][0] == 241
        assert p.at(240) == []                 # never before its own frame
        assert p.at(241 + p.persist) == []     # and it expires

    def test_newest_first_and_limited(self):
        p = EventPlan()
        for cf in (100, 150, 200, 250):
            p.add(cf, f"f{cf} DIG")
        rows = p.at(255, limit=2)
        assert [cf for cf, _ in rows] == [250, 200]

    def test_multiple_events_same_frame_are_all_kept(self):
        p = EventPlan()
        p.add(241, "f241 SPIKE")
        p.add(241, "f241 SPIKE touch")
        assert len(p.at(241)) == 2

    def test_none_contact_frame_ignored_and_none_query_safe(self):
        p = EventPlan()
        p.add(None, "f? DIG")
        assert p.at(None) == []
        assert p.at(10) == []

    def test_reset_clears(self):
        p = EventPlan()
        p.add(10, "a")
        p.reset()
        assert p.at(10) == []

    def test_concurrent_add_and_read(self):
        """Producer writes while the consumer reads: no lost/garbled rows."""
        p = EventPlan()
        errors = []

        def writer(tid):
            try:
                for i in range(500):
                    p.add(i, f"P{tid} DIG")
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        while any(t.is_alive() for t in threads):
            for cf, entry in p.at(250):
                assert entry["title"].startswith("P")
        for t in threads:
            t.join()
        assert not errors
        # Every writer's row survives; the window is wide, so `limit` caps it.
        assert len(p.at(499, limit=8)) == 8


# --------------------------------------------------------------------- #
# build_rows: the signals actually reach the panel
# --------------------------------------------------------------------- #

def _snapshot(**kw):
    base = {
        "frame": 241, "total": 900,
        "ball": {"x": 1187, "y": 392, "w": 21, "h": 21, "predicted": False,
                 "conf": 0.42, "speed": 14.2, "side": "A", "side_name": "near",
                 "side_votes": 8, "stale": 0},
        "players": [{"tid": 1, "team": "A", "near_net": True, "predicted": False,
                     "dist": 118.0, "reach": True},
                    {"tid": 2, "team": "B", "near_net": False, "predicted": False,
                     "dist": 640.0, "reach": False}],
        "game": {"state": "game_on", "points": 1, "provisional": False},
        "probe": [{"frame": 241, "stage": "candidate_found", "kind": "drive",
                   "distance": 41.0, "reach": 140.0}],
        "pending": {"frame": 240, "player_id": 2, "gesture": "bump_set",
                    "team": "B", "kind": "bounce"},
    }
    base.update(kw)
    return base


def _text(rows):
    return "\n".join(r[0] for r in rows)


class TestBuildRows:
    def test_ball_signals_present(self):
        text = _text(build_rows(_snapshot()))
        assert "size 21x21px" in text
        assert "width-side read: A (near)" in text
        assert "14.2 px/f" in text
        assert "track real" in text

    def test_projected_ball_and_stale_are_flagged(self):
        ball = dict(_snapshot()["ball"], predicted=True, stale=6)
        text = _text(build_rows(_snapshot(ball=ball)))
        assert "PREDICTED" in text and "stale 6f" in text

    def test_no_ball_track_renders_dash_not_crash(self):
        text = _text(build_rows(_snapshot(ball=None)))
        assert "no track" in text

    def test_refused_probe_shows_the_gate(self):
        probe = [{"frame": 241, "stage": "rejected", "reason": "reach",
                  "distance": 448.0, "reach": 140.0}]
        assert "refused: reach" in _text(build_rows(_snapshot(probe=probe)))

    def test_held_back_contact_visible(self):
        assert "held back: f240 P2 bump_set B" in _text(build_rows(_snapshot()))

    def test_players_show_team_net_and_reach(self):
        text = _text(build_rows(_snapshot()))
        assert "P1 A net" in text and "P2 B" in text

    def test_missing_values_show_dash(self):
        snap = _snapshot(ball=None, players=[], game={}, probe=[], pending=None)
        text = _text(build_rows(snap))
        assert "no contact probed" in text
        assert "held back: -" in text
        assert "none yet" in text
        assert "-   points 0" in text

    def test_event_on_this_frame_is_marked(self):
        events = [(241, {"title": "f241  SPIKE  0.65", "detail": "attack/drive",
                         "color": (0, 0, 255)}),
                  (200, {"title": "f200  DIG  0.55", "detail": "", "color": (0, 255, 255)})]
        rows = build_rows(_snapshot(), events)
        assert any(r[0].startswith(">> f241") for r in rows)
        assert any(r[0].startswith("   f200") for r in rows)

    def test_short_frame_still_draws_something(self):
        rows = build_rows(_snapshot())
        out = compose(np.zeros((40, 60, 3), np.uint8), _snapshot(),
                      [(241, {"title": "x", "detail": "", "color": (255, 255, 255)})])
        assert out.shape == (40, 60 + dp.PANEL_WIDTH, 3)
        assert rows

    def test_long_row_is_clipped_inside_the_strip(self):
        """A dense detail row must not run off the strip (measured, not counted)."""
        long_detail = "attack/drive net=1 behind=0 bbl=A src=width w=21px " * 3
        frame = _frame(w=200, h=200)
        out = compose(frame, _snapshot(), [
            (241, {"title": "f241 SPIKE", "detail": long_detail, "color": (0, 0, 255)})])
        # nothing was drawn past the panel's right edge: the strip keeps its
        # background colour on its final column
        assert (out[:, -1, :] == np.array(dp.BG, np.uint8)).all()
        assert dp._clip("x" * 200, 80).endswith("~")


# --------------------------------------------------------------------- #
# compose: video pixels untouched, panel appended on the right
# --------------------------------------------------------------------- #

class TestCompose:
    def test_video_region_is_copied_verbatim(self):
        frame = _frame()
        out = compose(frame, _snapshot())
        assert out.shape == (120, 200 + dp.PANEL_WIDTH, 3)
        np.testing.assert_array_equal(out[:, :200], frame)

    def test_panel_strip_is_filled(self):
        out = compose(_frame(), _snapshot())
        strip = out[:, 200:]
        assert not (strip == 200).all()          # not a copy of the frame
        assert (strip == np.array(dp.BG, np.uint8)).any()


# --------------------------------------------------------------------- #
# LiveDebugProcessor plumbing: snapshot + event anchoring
# --------------------------------------------------------------------- #

class _FakeActionClassifier:
    """The classifier reads the panel makes: already-computed values only."""

    def __init__(self, width=21.0, side=("A", 8), stale=0, pending=None):
        self._ball_history = [(240, 900.0, 400.0, width, width),
                              (241, 910.0, 395.0, width, width)]
        self._side, self._stale = side, stale
        self._pending = pending
        self._probe = [{"frame": 241, "stage": "candidate_found", "kind": "drive"}]
        self.diag_enabled = False
        self.popped = 0

    def _width_side(self, frame):
        return self._side

    def _ball_stale_frames(self, frame):
        return self._stale

    def pop_diag(self):
        self.popped += 1
        recs, self._probe = self._probe, []
        return recs


class _StubCourt:
    is_calibrated = False
    court_corners = None


class _StubFrameProcessor:
    def __init__(self, ac=None):
        self.action_classifier = ac
        self.diag = None
        self.spike_analyzer = type("A", (), {
            "spike_type_for": staticmethod(lambda f: None),
            "spike_zone_for": staticmethod(lambda f: None),
            "spike_records": staticmethod(list),
        })()


def _processor(ac=None):
    proc = object.__new__(LiveDebugProcessor)
    proc.config = {}
    proc.debug_speed = 1.0
    proc.logger = pytest.importorskip("logging").getLogger("test_debug_panel")
    proc.frame_processor = _StubFrameProcessor(ac)
    proc.court_detector = _StubCourt()
    proc._spike_log_state = []
    proc._panel_enabled = True
    proc._candidates_enabled = False
    proc._probe_mirror = False
    proc._last_ball = None
    proc._last_ball_pt = None
    from src.analysis.debug_panel import EventPlan as _EP
    proc._event_plan = _EP()
    return proc


def _lost_frame_result():
    """Same frame with the ball tracker returning nothing."""
    res = _frame_result()
    res["tracked_ball"] = None
    return res


def _frame_result():
    return {
        "tracked_ball": {"center": [260, 300], "bbox": [250, 290, 271, 311],
                         "velocity": [10.0, 10.0], "confidence": 0.42,
                         "is_predicted": False},
        "tracked_players": [
            {"track_id": 1, "team": "A", "center": [200, 300],
             "bbox": [180, 250, 220, 350]},
            {"track_id": 2, "team": "B", "center": [900, 300],
             "bbox": [880, 250, 920, 350], "predicted": True},
        ],
        "game_state": {"current_state": "game_on", "points": 1, "provisional": False},
        "actions": [],
    }


class TestSignalsSnapshot:
    def test_ball_signals_mirrored(self):
        proc = _processor(_FakeActionClassifier())
        snap = proc._signals(_frame_result(), 241)
        assert snap["frame"] == 241
        assert (snap["ball"]["x"], snap["ball"]["y"]) == (260, 300)
        assert (snap["ball"]["w"], snap["ball"]["h"]) == (21, 21)
        assert snap["ball"]["speed"] == pytest.approx(14.14, abs=0.01)
        assert (snap["ball"]["side"], snap["ball"]["side_name"]) == ("A", "near")
        assert snap["ball"]["stale"] == 0

    def test_player_reach_flags_use_the_classifier_reach(self):
        proc = _processor(_FakeActionClassifier())
        snap = proc._signals(_frame_result(), 241)
        near, far = snap["players"]
        # Ball at (260,300): inside player 1's reach, far outside player 2's.
        assert 0 < near["dist"] <= ActionClassifier.CONTACT_REACH
        assert near["reach"] is True and far["reach"] is False
        assert far["dist"] > ActionClassifier.CONTACT_REACH
        assert far["predicted"] is True

    def test_probe_only_popped_when_mirror_on(self):
        ac = _FakeActionClassifier()
        proc = _processor(ac)
        assert proc._signals(_frame_result(), 241)["probe"] == []
        assert ac.popped == 0
        proc._probe_mirror = True
        recs = proc._signals(_frame_result(), 241)["probe"]
        assert recs and recs[0]["kind"] == "drive"
        assert proc._signals(_frame_result(), 241)["probe"] == []   # drained

    def test_missing_classifier_degrades_instead_of_raising(self):
        proc = _processor(None)
        snap = proc._signals(_frame_result(), 241)
        assert snap["ball"]["side"] is None
        assert snap["players"] and snap["pending"] is None

    def test_no_ball_snapshot_before_any_sighting(self):
        proc = _processor(_FakeActionClassifier())
        snap = proc._signals(_lost_frame_result(), 241)
        assert snap["ball"] is None
        assert "no track yet" in _text(build_rows(snap))


class TestOverlayHelpers:
    def test_candidate_box_and_label(self):
        frame = _frame()
        overlay.draw_ball_candidate(frame, [10, 20, 30, 40], [20.0, 30.0], 0.42)
        # the hollow box is drawn on the frame (hollow => the centre stays out)
        assert frame[20, 20, 0] == _frame()[20, 20, 0]
        assert (frame[18, 20, :] != _frame()[18, 20, :]).any()

    def test_candidate_without_bbox_uses_center(self):
        frame = _frame()
        overlay.draw_ball_candidate(frame, None, [50.0, 50.0], None)
        # hollow box around the centre point: the edge is drawn, the middle is not
        assert (frame[50, 50 - overlay.CANDIDATE_HALF - 2, :] != _frame()[50, 50, :]).any()
        np.testing.assert_array_equal(frame[50, 50, :], _frame()[50, 50, :])

    def test_unplaceable_candidate_is_skipped(self):
        frame = _frame()
        overlay.draw_ball_candidate(frame, None, None, 0.9)
        np.testing.assert_array_equal(frame, _frame())


class TestBallCandidates:
    def _det(self):
        play = {"bbox": [10, 10, 20, 20], "center": [15.0, 15.0], "confidence": 0.9}
        suspect = {"bbox": [30, 30, 38, 38], "center": [34.0, 34.0],
                   "confidence": 0.44, "stationary_suspect": True}
        removed = {"bbox": [50, 50, 58, 58], "center": [54.0, 54.0],
                   "confidence": 0.22}
        det = types.SimpleNamespace(raw_detections=[play, suspect, removed])
        proc = _processor()
        proc.frame_processor.ball_detector = det
        return proc, play, suspect, removed

    def test_flags_reflect_detector_stage(self):
        proc, play, suspect, removed = self._det()
        cands = proc._ball_candidates(
            {"ball_detections": [play, suspect]})
        assert [c["flag"] for c in cands] == ["", "sus", "rm"]
        assert cands[0]["conf"] == 0.9
        assert cands[0]["bbox"] == [10, 10, 20, 20]

    def test_missing_detector_degrades_to_empty(self):
        proc = _processor()
        proc.frame_processor.ball_detector = None
        assert proc._ball_candidates({}) == []

    def test_snapshot_carries_candidates_only_when_enabled(self):
        proc, play, suspect, removed = self._det()
        res = _frame_result()
        res["ball_detections"] = [play, suspect]
        proc._candidates_enabled = False
        assert proc._signals(res, 241)["candidates"] == []
        proc._candidates_enabled = True
        assert len(proc._signals(res, 241)["candidates"]) == 3


class TestHeldBallReadout:
    """A dropped track must not blank the panel: the last known pos / size /
    width stay on screen, flagged, with the age in frames."""

    def test_lost_track_keeps_last_values_and_ages_them(self):
        proc = _processor(_FakeActionClassifier())
        seen = proc._signals(_frame_result(), 241)
        assert seen["ball"]["present"] is True
        lost = proc._signals(_lost_frame_result(), 248)
        b = lost["ball"]
        assert b["present"] is False
        assert b["held_from"] == 241 and b["stale"] == 7
        for key in ("x", "y", "w", "h", "speed", "side", "side_name",
                    "side_votes", "conf"):
            assert b[key] == seen["ball"][key]

    def test_reacquisition_updates_the_hold(self):
        proc = _processor(_FakeActionClassifier())
        proc._signals(_frame_result(), 241)
        proc._signals(_lost_frame_result(), 248)
        back = proc._signals(_frame_result(), 249)
        assert back["ball"]["present"] is True
        assert back["ball"]["stale"] == 0
        # a later loss ages from the NEW sighting, not the old one
        again = proc._signals(_lost_frame_result(), 255)["ball"]
        assert again["held_from"] == 249 and again["stale"] == 6

    def test_predicted_points_still_update_the_readout(self):
        proc = _processor(_FakeActionClassifier())
        proc._signals(_frame_result(), 241)
        res = _frame_result()
        res["tracked_ball"]["center"] = [400, 200]
        res["tracked_ball"]["is_predicted"] = True
        snap = proc._signals(res, 245)["ball"]
        assert snap["present"] is True and snap["predicted"] is True
        assert (snap["x"], snap["y"]) == (400, 200)

    def test_player_distances_survive_a_dropped_ball(self):
        proc = _processor(_FakeActionClassifier())
        proc._signals(_frame_result(), 241)
        snap = proc._signals(_lost_frame_result(), 248)
        near, far = snap["players"]
        assert near["dist"] is not None and near["reach"] is True
        assert far["dist"] is not None

    def test_panel_marks_the_hold_on_the_header_line(self):
        proc = _processor(_FakeActionClassifier())
        proc._signals(_frame_result(), 241)
        snap = proc._signals(_lost_frame_result(), 248)
        rows = build_rows(snap)
        text = _text(rows)
        # the flag rides ON the section header: no extra row is added
        assert "-- BALL -- NOT TRACKED (last f241, 7f ago)" in text
        assert text.count("-- BALL") == 1
        assert "LOST -" not in text
        assert "size 21x21px" in text                    # values kept
        assert "width-side read: A (near)" in text
        assert "track HELD   stale 7f" in text
        assert "[ball not tracked]" in text              # players flagged
        # the player rows are dimmed while the ball reference is stale
        player_rows = [r for r in rows if r[0].startswith("P1 ")]
        assert player_rows and player_rows[0][1] == dp.DIM

    def test_held_block_has_the_same_row_count_as_the_tracked_one(self):
        proc = _processor(_FakeActionClassifier())
        seen = build_rows(proc._signals(_frame_result(), 241))
        proc._signals(_frame_result(), 241)
        held = build_rows(proc._signals(_lost_frame_result(), 248))
        assert len(held) == len(seen)

    def test_enable_probe_mirror_skipped_when_diag_dumper_present(self):
        proc = _processor(_FakeActionClassifier())
        proc.frame_processor.diag = object()
        assert proc._enable_probe_mirror() is False
        assert proc.frame_processor.action_classifier.diag_enabled is False

    def test_enable_probe_mirror_turns_it_on_otherwise(self):
        proc = _processor(_FakeActionClassifier())
        assert proc._enable_probe_mirror() is True
        assert proc.frame_processor.action_classifier.diag_enabled is True


class TestActionEventRecording:
    def _action(self, **kw):
        base = {"track_id": 2, "player_id": 2, "action": "spike",
                "gesture": "attack", "confidence": 0.65, "frame_number": 241,
                "team": "A", "touch_number": 3, "near_net": True,
                "behind_baseline": False, "contact_kind": "drive",
                "ball_side": "A", "attribution_source": "width",
                "rally_id": 1}
        base.update(kw)
        return base

    def test_event_anchored_on_contact_frame_not_emission_frame(self):
        """Ingested at emission (frame 300) but shows on frame 241."""
        proc = _processor(_FakeActionClassifier())
        from src.output_gen import overlay
        proc._ingest_actions([self._action()], overlay.LabelPlan())
        rows = proc._event_plan.at(241)
        assert len(rows) == 1 and rows[0][0] == 241
        assert proc._event_plan.at(240) == []
        title, detail = rows[0][1]["title"], rows[0][1]["detail"]
        assert "SPIKE" in title and "0.65" in title and "t3" in title and title.endswith("A")
        # the signals that produced it, including the ball width at contact
        assert "attack/drive" in detail and "net=1" in detail
        assert "bbl=A" in detail and "src=width" in detail
        assert "w=21px" in detail

    def test_player_label_plan_still_keyed_by_track(self):
        proc = _processor(_FakeActionClassifier())
        from src.output_gen import overlay
        plan = overlay.LabelPlan()
        proc._ingest_actions([self._action()], plan)
        assert plan.active(2, 241) == ("spike", 0.65)

    def test_missing_width_omits_the_field(self):
        proc = _processor(_FakeActionClassifier())
        proc.frame_processor.action_classifier._ball_history = []
        from src.output_gen import overlay
        proc._ingest_actions([self._action()], overlay.LabelPlan())
        assert "w=" not in proc._event_plan.at(241)[0][1]["detail"]

    def test_no_classifier_still_records_the_event(self):
        proc = _processor(None)
        from src.output_gen import overlay
        proc._ingest_actions([self._action()], overlay.LabelPlan())
        assert proc._event_plan.at(241)[0][1]["title"].startswith("f241")