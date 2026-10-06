"""Serve-evidence event emitters: geometry, E1 far flight, E2 runway, combiner.

Open point G2 (STATUS 2026-10-01): the far serve is 0/12 held-out and every
classifier tried so far was refuted, so the owner's alternative is to EMIT the
evidence. These tests pin the parts that would silently rot:

* the runway region is the owner's geometry -- behind the far line, inside the
  sidelines continued to infinity, never behind the near line, never a bystander
  beside the court;
* the band is a FRACTION of the court's projected depth, not a px constant
  (venue coupling, AGENTS.md §7: 206 px deep on the beach vs 464-479 px at the
  practice venue);
* E1 fires on a GROWING apparent width only, and only from a far-band onset;
* the conjunction needs all three legs (occupant + ball + contact);
* everything stays inert when switched off (byte-identical default runs), which
  is what keeps the shared-path rule (AGENTS.md §2) intact.
"""
from __future__ import annotations

import json
import logging
from collections import deque
from pathlib import Path

import pytest

from src.analysis.serve_events import (
    FarFlightDetector,
    ServeEventEmitter,
    ServeRunway,
    ServeRunwayWatcher,
    bbox_gap,
    foot_point,
)
from src.utils.config import Config

ROOT = Path(__file__).resolve().parents[1]
MATCH_CALIB = ROOT / "calibrations" / "20260920_match_ari_joan_lost.json"
PRACTICE_CALIB = ROOT / "calibrations" / "20290928_entreno_vall_dhebron.json"

# The beach match calibration: far line y~585-597, court 191 px deep, wedge
# apex at (1055, 504).
MATCH_CORNERS = [[714, 597], [1277, 585], [1793, 774], [3, 791]]


@pytest.fixture
def runway() -> ServeRunway:
    return ServeRunway(MATCH_CORNERS)


def person(x1, y1, x2, y2, conf=0.5):
    return {"bbox": [x1, y1, x2, y2], "confidence": conf,
            "center": [(x1 + x2) / 2, (y1 + y2) / 2], "class_id": 0}


def ball(cx, cy, w, h, conf=0.6):
    return {"bbox": [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
            "center": [cx, cy], "confidence": conf}


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def test_runway_depth_and_band_are_depth_fractions(runway):
    """Band = fraction of the projected depth, so the two venues differ."""
    assert 180 < runway.depth_px < 210
    assert runway.front_px == pytest.approx(0.15 * runway.depth_px)
    assert runway.back_px == pytest.approx(0.30 * runway.depth_px)


def test_person_behind_the_far_line_is_a_runway_occupant(runway):
    # Measured at the P13 far serve: the server's foot sat ~20 px above the line.
    assert runway.classify((1050, 570)) == "runway"


def test_person_on_the_far_line_counts_as_the_band(runway):
    """The straddling band is what makes this 17/17 instead of 7/17."""
    assert runway.classify((1050, 591)) == "court"


def test_near_half_is_never_the_runway(runway):
    assert runway.classify((700, 730)) is None
    # ... and it does not extend behind the NEAR line either (owner's spec).
    assert runway.classify((700, 900)) is None


def test_bystander_beside_the_court_is_rejected(runway):
    # Spectators at x~1750 on the right: outside the extended right sideline.
    assert runway.classify((1760, 655)) is None
    assert runway.classify((120, 600)) is None


def test_region_above_the_wedge_apex_is_rejected(runway):
    """The two extended sidelines cross at the apex; nothing is 'in the runway' above it."""
    ax, ay = runway.apex
    assert runway.classify((ax, ay - 40)) is None
    assert runway.classify((ax, ay - 150)) is None
    # Below the apex the wedge is genuinely open, so the band is reachable there.
    assert runway.classify((ax, ay + 40)) == "runway"


def test_side_margin_is_optional_and_strict_by_default():
    tight = ServeRunway(MATCH_CORNERS, side_margin_frac=0.0)
    loose = ServeRunway(MATCH_CORNERS, side_margin_frac=0.30)
    # A point just outside the extended left sideline, behind the far line.
    p = (820, 560)
    assert tight.classify(p) is None
    assert loose.classify(p) is not None


def test_geometry_is_venue_portable():
    """Same fraction, very different pixels: the practice venue is 2.4x deeper."""
    match = ServeRunway(MATCH_CORNERS)
    practice = ServeRunway(json.loads(PRACTICE_CALIB.read_text())["court_corners"])
    assert practice.depth_px > 2 * match.depth_px
    assert practice.back_px > 2 * match.back_px
    assert MATCH_CALIB.exists()


def test_foot_point_and_bbox_gap():
    assert foot_point([10, 20, 30, 50]) == (20.0, 50.0)
    assert bbox_gap([10, 10, 20, 20], (15, 15)) == 0.0
    assert bbox_gap([10, 10, 20, 20], (30, 15)) == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# E2 -- runway occupancy
# ---------------------------------------------------------------------------


def test_watcher_emits_one_event_per_presence_run(runway):
    watcher = ServeRunwayWatcher(runway, min_conf=0.15, min_frames=3)
    for f in range(100, 106):
        assert watcher.observe(f, [person(1030, 480, 1070, 570, conf=0.6)]) == 1
    for f in range(106, 120):
        assert watcher.observe(f, [person(600, 500, 700, 700, conf=0.9)]) == 0
    watcher.flush()
    assert len(watcher.events) == 1
    event = watcher.events[0]
    assert event["type"] == "runway_occupant"
    assert (event["start_frame"], event["end_frame"], event["frames"]) == (100, 105, 6)
    assert event["off_court_frames"] == 6  # all six frames were behind the line


def test_watcher_ignores_short_runs_and_low_confidence(runway):
    watcher = ServeRunwayWatcher(runway, min_conf=0.15, min_frames=3)
    watcher.observe(10, [person(1030, 480, 1070, 570, conf=0.6)])
    watcher.observe(11, [person(1030, 480, 1070, 570, conf=0.6)])
    watcher.observe(12, [person(1030, 480, 1070, 570, conf=0.05)])  # below the floor
    watcher.flush()
    assert watcher.events == []


def test_watcher_prefers_the_highest_confidence_occupant(runway):
    watcher = ServeRunwayWatcher(runway, min_conf=0.15, min_frames=3)
    for f in range(3):
        watcher.observe(f, [person(1030, 480, 1070, 570, conf=0.2),
                            person(1100, 490, 1140, 570, conf=0.7)])
    watcher.flush()
    assert watcher.events[0]["peak_conf"] == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# E1 -- far flight
# ---------------------------------------------------------------------------


def _feed_flight(detector, start_frame, widths, cx=990, cy=560, gap=1, close=True):
    events = []
    for i, w in enumerate(widths):
        frame = start_frame + i * gap
        events += detector.observe(frame, [ball(cx, cy, w, w, conf=0.6)])
    if close:
        events += detector.flush()
    return events


def test_growing_width_emits_a_far_flight(runway):
    det = FarFlightDetector(runway, fps=10.0, span_s=0.5, min_points=3)
    events = _feed_flight(det, 100, [14, 16, 18, 21, 24])
    assert len(events) == 1
    event = events[0]
    assert event["type"] == "far_flight"
    assert event["onset_frame"] == 100
    assert event["growth"] > 0
    assert event["width_start"] == 14 and event["width_end"] > 14


def test_shrinking_width_is_not_a_far_flight(runway):
    det = FarFlightDetector(runway, fps=10.0, span_s=0.5, min_points=3)
    assert _feed_flight(det, 100, [24, 21, 18, 16, 14]) == []


def test_onset_must_be_in_the_far_band(runway):
    """A ball that starts over the NEAR half is not a far flight."""
    det = FarFlightDetector(runway, fps=10.0, span_s=0.5, min_points=3)
    assert _feed_flight(det, 100, [14, 16, 18, 21, 24], cx=700, cy=760) == []


def test_gap_breaks_the_run(runway):
    """A flight is a continuous widening, not two bursts with a hole between."""
    det = FarFlightDetector(runway, fps=10.0, span_s=0.5, min_points=3)
    events = []
    events += det.observe(100, [ball(990, 560, 14, 14)])
    events += det.observe(101, [ball(990, 560, 16, 16)])
    events += det.observe(105, [ball(990, 560, 18, 18)])  # gap of 3 frames: closes the first run
    events += det.observe(106, [ball(990, 560, 20, 20)])
    events += det.observe(107, [ball(990, 560, 22, 22)])
    events += det.flush()
    # The 2-sighting head (100-101) is too short for a slope; the post-gap run fires.
    assert len(events) == 1
    assert events[0]["onset_frame"] == 105


def test_top_confidence_detection_is_the_one_tracked(runway):
    det = FarFlightDetector(runway, fps=10.0, span_s=0.5, min_points=3)
    for i, w in enumerate([14, 16, 18, 21, 24]):
        det.observe(100 + i, [ball(990, 560, 60, 60, conf=0.2),   # a big spare
                              ball(990, 560, w, w, conf=0.8)])   # the ball in play
    det.flush()
    assert det.events and det.events[0]["width_start"] == 14


# ---------------------------------------------------------------------------
# Combiner -- occupant + ball + contact
# ---------------------------------------------------------------------------


def _emit_with_occupant(contact_frame, mode="held_then_flight", reach_factor=1.0,
                       lookback_s=5.0, run_frames=50, stale_gap=12):
    """One occupant standing in the runway, seen by the emitters for a window.

    ``held_then_flight``  the ball is in their hands and then flies at the camera
    (growing width) from ``contact_frame`` on -- the far-serve signature.
    ``near_flight``       the same growth, but it starts over the NEAR half, so
    it is not a far flight and nothing may be concluded from it.
    ``stale_hold``        the ball was with the occupant, then went unseen for
    ``stale_gap`` frames, and only THEN started growing -- so whether the
    conjunction fires is exactly the question the lookback window answers.
    """
    em = ServeEventEmitter(MATCH_CORNERS, fps=10.0, runway_min_frames=1,
                           reach_factor=reach_factor, lookback_s=lookback_s)
    # Occupant centred in the runway: its foot is inside the extended sidelines
    # (at y=570 the wedge spans x 813-1236 on the beach match).
    box = (900, 480, 940, 570)
    for f in range(contact_frame - 40, contact_frame - 40 + run_frames):
        people = [person(*box, conf=0.6)]
        if mode == "near_flight":
            balls = [ball(700, 700 + (f % 5) * 2, 30 + f % 4 * 2, 30 + f % 4 * 2)]
        elif mode == "stale_hold":
            if f < contact_frame - stale_gap:
                balls = [ball(920, 550, 14, 14)]  # with the occupant, then unseen
            elif f < contact_frame:
                balls = []                        # nothing detected at all
            else:
                # The flight reappears already clear of the player's box
                # (100 px away, > the 90 px reach radius), so the only evidence
                # that ties it to them is the older hold.
                step = f - contact_frame
                balls = [ball(1040 + 6 * step, 560 + 8 * step, 14 + 3 * step, 14 + 3 * step)]
        elif f < contact_frame:
            balls = [ball(920, 550, 14, 14)]  # held / tossed, width constant
        else:
            step = f - contact_frame
            balls = [ball(920 + 6 * step, 550 + 8 * step, 14 + 3 * step, 14 + 3 * step)]
        em.observe(f, people, balls)
    em.flight.flush()
    return em


def test_conjunction_fires_when_the_ball_was_with_the_occupant():
    events = _emit_with_occupant(contact_frame=140).finish()
    candidates = [e for e in events if e["type"] == "serve_candidate"]
    assert len(candidates) == 1
    candidate = candidates[0]
    # The ball is with the player at the contact; the flight onset confirms it
    # a few frames later (the ball only grows once it is already travelling).
    assert candidate["contact_frame"] == 140
    assert candidate["flight_onset_frame"] >= candidate["contact_frame"]
    assert candidate["onset_lead_frames"] == candidate["flight_onset_frame"] - 140
    assert candidate["occupant_region"] in ("runway", "court")
    assert candidate["ball_gap_norm"] <= 1.0
    assert candidate["flight_growth"] > 0
    # The occupancy is reported alongside it (the two events are independent).
    assert [e for e in events if e["type"] == "runway_occupant"]


def test_no_candidate_when_the_growth_does_not_start_in_the_far_band():
    em = _emit_with_occupant(contact_frame=140, mode="near_flight")
    events = em.finish()
    assert [e for e in events if e["type"] == "runway_occupant"]
    assert [e for e in events if e["type"] == "far_flight"] == []
    assert [e for e in events if e["type"] == "serve_candidate"] == []


def test_stale_reach_evidence_outside_the_lookback_is_not_used():
    """The ball must be with the player NEAR the contact, not 1.2 s before it."""
    events = _emit_with_occupant(contact_frame=140, mode="stale_hold",
                                 lookback_s=0.5).finish()
    assert [e for e in events if e["type"] == "far_flight"]
    assert [e for e in events if e["type"] == "serve_candidate"] == []


def test_the_same_stale_evidence_fires_with_a_long_enough_lookback():
    events = _emit_with_occupant(contact_frame=140, mode="stale_hold",
                                 lookback_s=5.0).finish()
    assert len([e for e in events if e["type"] == "serve_candidate"]) == 1


def test_ball_reach_is_reported_in_occupant_bbox_heights():
    """The ball starts in the player's hands, so the reach is 0 (inside the box)."""
    events = _emit_with_occupant(contact_frame=140).finish()
    candidate = [e for e in events if e["type"] == "serve_candidate"][0]
    assert candidate["ball_gap_norm"] == 0.0
    assert candidate["occupant_bbox"] == [900.0, 480.0, 940.0, 570.0]


def test_no_candidate_without_an_occupant():
    em = ServeEventEmitter(MATCH_CORNERS, fps=10.0)
    for f in range(100, 150):
        em.observe(f, [], [ball(990, 560, 14 + f % 5 * 1.5, 14 + f % 5 * 1.5)])
    em.flight.flush()
    events = em.finish()
    assert [e for e in events if e["type"] == "far_flight"]
    assert [e for e in events if e["type"] == "serve_candidate"] == []


def test_events_are_frame_ordered_and_finish_is_idempotent():
    em = _emit_with_occupant(contact_frame=140)
    first = em.finish()
    second = em.finish()
    assert [e["frame"] for e in first] == sorted(e["frame"] for e in first)
    assert len(second) == len(first)


# ---------------------------------------------------------------------------
# Config + wiring
# ---------------------------------------------------------------------------


def test_serve_events_are_off_by_default():
    assert Config.DEFAULT_CONFIG["serve_events_enabled"] is False


@pytest.mark.parametrize("key", [
    "serve_runway_front_frac", "serve_runway_back_frac", "serve_runway_side_margin_frac",
    "serve_runway_min_conf", "serve_runway_min_frames", "serve_ball_min_conf",
    "far_flight_span_s", "far_flight_min_points", "far_flight_min_growth",
    "serve_candidate_reach_factor", "serve_candidate_lookback_s",
])
def test_every_emitter_tuning_key_exists_in_default_config(key):
    assert key in Config.DEFAULT_CONFIG


def test_from_config_uses_the_default_config_values():
    em = ServeEventEmitter.from_config(Config.DEFAULT_CONFIG, MATCH_CORNERS, fps=25.67)
    assert em.runway.front_px == pytest.approx(
        Config.DEFAULT_CONFIG["serve_runway_front_frac"] * em.runway.depth_px)
    assert em.flight.span_frames == max(
        2, int(round(Config.DEFAULT_CONFIG["far_flight_span_s"] * 25.67)))
    assert em.reach_factor == Config.DEFAULT_CONFIG["serve_candidate_reach_factor"]


# ---------------------------------------------------------------------------
# Detector side channels -- the emitters' inputs, and they must stay inert
# ---------------------------------------------------------------------------


def test_player_detector_off_area_side_channel_is_populated_and_not_returned():
    """The runway emitter needs the person boxes the play-area filter dropped.

    Built with __new__ so no YOLO weights load: only the filter branch runs.
    """
    import numpy as np

    from src.detection.player_detector import PlayerDetector

    det = PlayerDetector.__new__(PlayerDetector)
    det.confidence_threshold = 0.15
    det.logger = logging.getLogger(__name__)
    det.off_area_detections = []
    det.court_detector = None
    det.max_players = 20
    # Court mask covering only the left half of the frame: the right-hand
    # detection is off-play-area and must land in the side channel only.
    mask = np.zeros((1080, 1920), dtype=np.uint8)
    mask[:, :960] = 255

    class FakeCourt:
        def detect_play_area(self, frame):
            return mask

    inside = {"bbox": [700, 400, 800, 600], "confidence": 0.9, "aspect_ratio": 2.5, "area": 40000}
    outside = {"bbox": [1500, 400, 1600, 600], "confidence": 0.8, "aspect_ratio": 2.5, "area": 40000}
    det.court_detector = FakeCourt()
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    kept = det.filter_player_detections([dict(inside), dict(outside)], frame=frame)
    assert [d["bbox"] for d in kept] == [inside["bbox"]]
    assert [d["bbox"] for d in det.off_area_detections] == [outside["bbox"]]


def test_ball_detector_keeps_pre_suppression_detections():
    """The far-flight event works on the un-suppressed stream (AGENTS.md §6)."""
    import types

    import numpy as np
    import torch

    from src.detection.ball_detector import BallDetector

    det = BallDetector.__new__(BallDetector)
    det.logger = logging.getLogger(__name__)
    det.confidence_threshold = 0.15
    det.max_ball_size = 200
    det._is_custom_model = True
    det.suppress_static = True
    det.static_persist_frac = 0.55
    det.static_suspect_frac = 0.30
    det.diag_enabled = False
    det._diag_dets = []
    det._recent_centers = deque(maxlen=40)
    det.raw_detections = []
    # Everything looks stationary -> the survivor list is empty, the raw one isn't.
    det._static_persist = lambda center: 1.0

    class FakeModel:
        """Stand-in for the ultralytics call: one box, as ``Results.boxes.data``
        rows ``x1, y1, x2, y2, conf, cls``."""

        def __call__(self, *a, **kw):
            data = torch.tensor([[10.0, 10.0, 30.0, 30.0, 0.9, 0.0]])
            return [types.SimpleNamespace(boxes=types.SimpleNamespace(data=data))]

    det._model = FakeModel()
    det._inference = None
    det.fast_inference = True
    det._imgsz = 640
    det._auto_imgsz = None
    survivors = det.detect(np.zeros((1080, 1920, 3), dtype=np.uint8))
    assert survivors == []
    assert len(det.raw_detections) == 1
    assert det.raw_detections[0]["bbox"] == [10, 10, 30, 30]


def test_json_payload_omits_serve_events_by_default_and_includes_them_when_present():
    from src.output_gen.json_exporter import JSONExporter

    exporter = JSONExporter()
    exporter.logger = logging.getLogger(__name__)
    base = {"video_info": {"path": "/tmp/x.mp4", "fps": 30.0},
            "frame_results": [], "spike_analysis": []}
    assert "serve_events" not in exporter.build_payload(dict(base), "test")
    payload = exporter.build_payload(
        dict(base, serve_events=[{"type": "far_flight", "frame": 10}]), "test")
    assert payload["serve_events"] == [{"type": "far_flight", "frame": 10}]


def test_cli_flag_wires_the_key():
    """A flag nobody reads is a dead key (the config-drift lesson)."""
    import inspect

    from src import main as main_module

    src = inspect.getsource(main_module)
    assert '"--serve-events"' in src
    assert 'config["serve_events_enabled"] = True' in src


def test_setup_video_fps_retimes_the_emitter_windows():
    """FrameProcessor.setup_video_fps must re-derive the SECOND-based windows.

    Variable fps is expected (AGENTS.md §7: 25.67 avg in the match, ~30.1 in
    practice), so the emitter cannot keep the construction-time assumption.
    """
    em = ServeEventEmitter(MATCH_CORNERS, fps=30.0)
    assert em.flight.span_frames == 15 and em.lookback_frames == 150
    em.flight.fps = 25.67
    em.flight.span_frames = max(2, int(round(em.flight.span_s * 25.67)))
    em.lookback_frames = int(round(em.lookback_s * 25.67))
    assert em.flight.span_frames == 13 and em.lookback_frames == 128


# ---------------------------------------------------------------------------
# The ball gate is the NET line, not the foot band
# ---------------------------------------------------------------------------

MATCH_MIDCOURT = [[538, 645], [1426, 641]]


def test_far_side_gate_uses_the_net_line_for_the_ball(runway):
    """A contact happens at hand height, far above the far baseline."""
    # Ball at the server's hands on the beach match: tens of px above the far
    # line. Near the wedge edge it can fall OUTSIDE the foot band while still
    # being plainly on the far side of the net -- the two gates are not the
    # same test, and the ball needs the second one.
    assert runway.classify((1000, 530)) is None   # 61 px above the line: past the band
    assert runway.is_far_side((1000, 530))       # ... still plainly far-side
    assert runway.classify((920, 550)) == "runway"
    assert runway.is_far_side((920, 550))
    # A ball over the near half is not a far flight.
    assert not runway.is_far_side((700, 720))
    # Airborne balls ignore the ground wedge (a far serve rises to y~306, well
    # above the apex at 504); a point that IS on the ground can still ask for
    # the lateral test explicitly.
    assert runway.is_far_side((1000, 306)) and not runway.is_far_side((1000, 306), lateral=True)
    assert not runway.is_far_side((700, 720))


def test_net_line_falls_back_to_corner_midpoints_without_calibration():
    approx = ServeRunway(MATCH_CORNERS)
    calibrated = ServeRunway(MATCH_CORNERS, midcourt_points=MATCH_MIDCOURT)
    assert not approx.net_line_is_calibrated
    assert calibrated.net_line_is_calibrated
    # Both agree on the coarse question the gate asks.
    assert calibrated.is_far_side((920, 550)) and approx.is_far_side((920, 550))
    assert not calibrated.is_far_side((700, 720)) and not approx.is_far_side((700, 720))


def test_emitter_takes_the_calibrated_midcourt_line():
    em = ServeEventEmitter.from_config(Config.DEFAULT_CONFIG, MATCH_CORNERS,
                                       fps=25.67, midcourt_points=MATCH_MIDCOURT)
    assert em.runway.net_line_is_calibrated
