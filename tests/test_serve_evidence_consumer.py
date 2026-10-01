"""The structural serve-contact arm (session 53) and the S4 consumer.

Two things are pinned here, because both are the difference between a serve
EVIDENCE record and a false-positive machine:

* ``ServeContactProposer`` (inside the default-off ``--serve-events`` envelope)
  must fire on a ball-sized far-side detection in reach of a person in the
  RUNWAY, and must refuse each of the four ways the same scene produces noise:
  a 3 px patch of ground, a ball on the NEAR side of the net, a person merely
  inside the court band rather than in the runway, and a lone frame with no run.
* ``scripts/consume_serve_evidence.py`` must apply the OPENER GATE to the two
  arms, union them, place the record at the EARLIEST candidate in the point
  window, and never touch the action stream.

The measured frontier these encode is in ``docs/g4_structural_serve.md``:
11/17 at precision 1.00 for the structural arm alone, 14/17 for the union with
the gated conjunction, against 0/17 in the action stream.
"""

import importlib.util
import json
import unittest
from pathlib import Path

import pytest

from src.analysis.serve_events import ServeContactProposer, ServeRunway
from src.utils.config import Config

ROOT = Path(__file__).resolve().parents[1]
MATCH_CORNERS = [[714, 597], [1277, 585], [1793, 774], [3, 791]]
MATCH_MIDCOURT = [[538, 645], [1426, 641]]


def _load_consumer():
    spec = importlib.util.spec_from_file_location(
        "consume_serve_evidence", ROOT / "scripts" / "consume_serve_evidence.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


C = _load_consumer()


def person(x1, y1, x2, y2, conf=0.5):
    return {"bbox": [x1, y1, x2, y2], "confidence": conf,
            "center": [(x1 + x2) / 2, (y1 + y2) / 2], "class_id": 0}


def ball(cx, cy, w, h, conf=0.6):
    return {"bbox": [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
            "center": [cx, cy], "confidence": conf}


@pytest.fixture
def proposer():
    return ServeContactProposer(
        ServeRunway(MATCH_CORNERS, MATCH_MIDCOURT), min_conf=0.15,
        ball_min_conf=0.15, reach_factor=1.5, ball_w_min=8, ball_w_max=60,
        max_gap=3)


# A server standing in the runway: box top y=470, foot y=580 (behind the far
# line at y~591). Height 110, so the reach of 1.5 is 165 px.
SERVER = person(965, 470, 1025, 580, conf=0.4)
SERVER_BALL = ball(995, 500, 16, 16)          # far side, at hand height


class TestStructuralArm:
    def test_fires_on_a_run_and_places_the_contact_at_the_last_sighting(self, proposer):
        events = []
        for frame in range(100, 105):
            events += proposer.observe(frame, [SERVER], [SERVER_BALL])
        events += proposer.flush()
        assert len(events) == 1
        event = events[0]
        assert event["type"] == "serve_contact"
        assert event["contact_frame"] == 104, "the ball is still with the server"
        assert event["sightings"] == 5
        assert event["occupant_region"] == "runway"
        assert event["ball_width"] == 16

    def test_a_lone_frame_is_a_phantom_not_a_contact(self, proposer):
        assert proposer.observe(100, [SERVER], [SERVER_BALL]) == []
        assert proposer.flush() == []

    def test_refuses_three_px_of_ground(self, proposer):
        """The venue fires the detector at ~2 candidates/frame; 3 px is sand."""
        for frame in range(100, 105):
            proposer.observe(frame, [SERVER], [ball(995, 500, 3, 3, conf=0.4)])
        assert proposer.flush() == []

    def test_refuses_a_ball_on_the_near_side_of_the_net(self, proposer):
        """A contact happens at hand height and the ball is airborne after it,
        so the gate is the NET line, not the ground wedge."""
        for frame in range(100, 105):
            proposer.observe(frame, [SERVER], [ball(995, 700, 30, 30)])
        assert proposer.flush() == []

    def test_refuses_a_person_merely_inside_the_court_band(self, proposer):
        """The band exists to keep the occupancy measurement at 17/17; the
        structural arm must be stricter, because admitting "court" here is
        exactly what costs the two owner false positives."""
        inside = person(965, 480, 1025, 600)   # foot y=600, in front of the line
        for frame in range(100, 105):
            proposer.observe(frame, [inside], [SERVER_BALL])
        assert proposer.flush() == []

    def test_refuses_a_ball_outside_the_reach(self, proposer):
        far = ball(400, 480, 16, 16)
        for frame in range(100, 105):
            proposer.observe(frame, [SERVER], [far])
        assert proposer.flush() == []

    def test_tolerates_a_short_detection_gap(self, proposer):
        """A far ball is seen on most but not all frames; a run may skip
        ``max_gap`` frames without closing."""
        for frame in list(range(100, 103)) + [106, 107, 108]:
            proposer.observe(frame, [SERVER], [SERVER_BALL])
        events = proposer.flush()
        assert len(events) == 1 and events[0]["contact_frame"] == 108

    def test_a_blank_stretch_over_budget_closes_the_run(self, proposer):
        """``max_gap`` is a budget on BLANK frames, not on the spacing of the
        sightings: a ball seen on 100 and again on 104 is continuous, but a
        ball that vanishes for four frames ends the run."""
        assert proposer.observe(100, [SERVER], [SERVER_BALL]) == []
        for frame in (101, 102, 103, 104):        # 4 blank frames > max_gap 3
            assert proposer.observe(frame, [SERVER], []) == []
        assert proposer.observe(105, [SERVER], [SERVER_BALL]) == []
        assert proposer.observe(106, [SERVER], [SERVER_BALL]) == []
        flushed = proposer.flush()
        assert len(flushed) == 1
        assert flushed[0]["start_frame"] == 105, "the single-sighting run was dropped"
        assert flushed[0]["sightings"] == 2 and flushed[0]["contact_frame"] == 106

    def test_sightings_two_frames_apart_stay_one_run(self, proposer):
        for frame in (100, 102, 104):
            proposer.observe(frame, [SERVER], [SERVER_BALL])
        flushed = proposer.flush()
        assert len(flushed) == 1 and flushed[0]["sightings"] == 3


class TestConfigDrift:
    def test_structural_defaults_match_default_config(self):
        """The bare-constructor scripts must not fork from production."""
        import inspect
        defaults = Config.default().config
        params = inspect.signature(ServeContactProposer).parameters
        for key, param in (("serve_structural_reach_factor", "reach_factor"),
                           ("serve_structural_ball_w_min", "ball_w_min"),
                           ("serve_structural_ball_w_max", "ball_w_max"),
                           ("serve_structural_max_gap", "max_gap")):
            assert defaults[key] == params[param].default, key

    def test_the_arm_rides_inside_the_default_off_envelope(self):
        assert Config.default().config["serve_events_enabled"] is False, (
            "the structural arm must stay behind the --serve-events switch")
        assert Config.default().config["serve_structural_enabled"] is True


class TestOpenerGate:
    FRAMES = [700, 900, 1500]

    def test_open_after_a_long_gap(self):
        assert C.gate_open(self.FRAMES, 1700, 143)
        assert C.gate_open(self.FRAMES, 1100, 143)

    def test_closed_inside_a_rally(self):
        assert not C.gate_open(self.FRAMES, 950, 143)     # 50 f after a contact
        assert not C.gate_open(self.FRAMES, 1034, 143)   # the 134 f mid-rally max
        assert C.gate_open(self.FRAMES, 1053, 143)        # 153 f: the smallest opener

    def test_the_measured_chasm_is_where_the_gate_sits(self):
        """Openers >= 153 f, largest mid-rally gap 134 f: the constant sits in
        the middle, so it is a structural fact and not a fit."""
        assert C.gate_open(self.FRAMES, 700 + 153, 143)
        assert not C.gate_open(self.FRAMES, 900 + 134, 143)

    def test_no_prior_contact_counts_as_open(self):
        assert C.gate_open([], 100, 143)


class TestConsumer:
    EVENTS = [
        {"type": "serve_candidate", "frame": 300, "contact_frame": 302,
         "occupant_bbox": [1, 2, 3, 4], "ball_gap_norm": 0.4},
        {"type": "serve_contact", "frame": 305, "contact_frame": 304,
         "occupant_bbox": [1, 2, 3, 4], "ball_gap_norm": 0.5, "sightings": 4},
        {"type": "serve_contact", "frame": 900, "contact_frame": 900,
         "occupant_bbox": [1, 2, 3, 4], "ball_gap_norm": 0.5, "sightings": 3},
        {"type": "far_flight", "frame": 306, "onset_frame": 306},
    ]

    def test_union_of_both_arms_is_one_record(self):
        records = C.group_evidence(self.EVENTS, [100], 143, 90, 60)
        assert len(records) == 2
        assert records[0]["sources"] == ["conjunction", "structural"]
        assert records[0]["frame"] == 304, "the structural arm's timing wins"
        assert records[1]["sources"] == ["structural"]

    def test_the_gate_drops_a_mid_rally_candidate(self):
        records = C.group_evidence(self.EVENTS, [880], 143, 90, 60)
        assert [r["frame"] for r in records] == [304]

    def test_only_the_two_arms_are_read(self):
        records = C.group_evidence(self.EVENTS, [100], 143, 90, 60)
        assert all("far_flight" not in r["sources"] for r in records)

    def test_the_serve_binds_to_the_point_owning_the_reception(self):
        actions = [100, 700, 1000]
        records = C.group_evidence(self.EVENTS, actions, 143, 90, 60)
        points = [{"point": 1, "window_frames": [250, 600]},
                  {"point": 2, "window_frames": [800, 1200]}]
        rows = C.attach_to_points(records, points, actions, 90, 60)
        # The 304/305 pair opens a rally 396 f before the next contact, so it is
        # dead-time evidence that never became a serve; the 900 record opens the
        # next episode and binds to the point that owns its reception.
        assert rows[1]["serve_evidence"] is not None
        assert rows[1]["serve_evidence"]["frame"] == 900
        assert rows[0]["serve_evidence"] is None
        assert rows[0]["records"], "the evidence is still reported for the point"

    def test_the_record_carries_its_provenance(self):
        records = C.group_evidence(self.EVENTS, [100], 143, 90, 60)
        record = records[0]
        assert set(record["arms"]) == {"conjunction", "structural"}
        assert record["arms"]["structural"]["sightings"] == 4

    def test_owner_negatives_parse_from_the_anchor_file(self):
        negatives = C.load_owner_negatives()
        assert len(negatives) == 9
        assert sum(1 for n in negatives
                   if n["range"][0] != n["range"][1]) == 4, "4 OFFGAME ranges"

    def test_gt_far_serves_are_the_17_owner_contacts(self):
        serves = C.load_gt_far_serves()
        assert len(serves) == 17
        assert sum(1 for s in serves if s["held_out"]) == 12


class TestSelector(unittest.TestCase):
    """Which record IS the serve, without knowing the answer.

    A dead-time episode holds three kinds of record -- the walk to the line, the
    serve, and the echo of the ball still inside the server's bbox just after the
    hit -- and the emitted stream says only "a rally contact follows". The
    selector's whole job is to order them, and the numbers in
    ``docs/g4_serve_evidence.md`` are its honest score.
    """

    FRAMES = [0, 300]

    @staticmethod
    def _rec(frame, arm="structural"):
        return {"frame": frame, "sources": [arm], "arms": {arm: {}}}

    def test_the_closest_record_that_is_not_an_echo_is_the_serve(self):
        """The echo sits a handful of frames before the reception, so it falls
        under ``min_next_gap``; among the rest the serve is the nearest one."""
        records = [self._rec(87), self._rec(200), self._rec(296)]
        got = C.select_serve(records, self.FRAMES, 20, 140)
        assert got["frame"] == 200, "296 is 4 f away: the post-contact echo"

    def test_the_walk_to_the_line_is_too_far_back(self):
        records = [self._rec(20), self._rec(200)]
        assert C.select_serve(records, self.FRAMES, 20, 140)["frame"] == 200

    def test_no_qualifying_record_means_no_serve(self):
        self.assertIsNone(C.select_serve([self._rec(296)], self.FRAMES, 20, 140),
                          "only an echo")
        self.assertIsNone(C.select_serve([self._rec(20)], self.FRAMES, 20, 140),
                          "only the walk to the line")
        self.assertIsNone(C.select_serve([], self.FRAMES, 20, 140))

    def test_episodes_partition_the_records_between_contacts(self):
        records = [self._rec(50), self._rec(200), self._rec(400)]
        episodes = C.build_episodes(records, self.FRAMES)
        assert [len(e["records"]) for e in episodes] == [2, 1]
        assert episodes[0]["first_action"] == 300 and episodes[1]["first_action"] is None

    def test_a_record_before_the_first_contact_is_an_episode(self):
        episodes = C.build_episodes([self._rec(50)], [300])
        assert len(episodes) == 1 and episodes[0]["start_frame"] is None

    def test_point_lookup_falls_back_to_the_nearest_window(self):
        points = [{"point": 1, "window_frames": [0, 200]},
                  {"point": 2, "window_frames": [1000, 1200]}]
        assert C.point_of_frame(points, 150) == 1
        assert C.point_of_frame(points, 1100) == 2
        # A reception just past the end of a window still binds to that point.
        assert C.point_of_frame(points, 260) == 1
        assert C.point_of_frame(points, 9000) is None
