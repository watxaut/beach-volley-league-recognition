"""Post-run reconstruction layer (src/postrun): points, touches, match.

Synthetic rallies are scripted in court metres and rendered through the same
pinhole model the layer inverts (tests/postrun_sim.py), so every rule is
exercised on a stream with a known answer:

* geometry -- depth from ball width, height above the sand, the net height
  the calibration implies;
* ball timeline -- a tracking gap is the same flight, a hidden touch or a
  break;
* segmentation -- a serve starts a point, dead-time ball handling does not,
  the ball on the sand ends it;
* touches -- half, touch number and alternating players solved jointly;
  hidden touches keep the count right and are never credited;
* match -- the next serve names the winner, the score closes the set, the
  service order names the server nobody saw.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "scripts"))

import postrun_sim as sim  # noqa: E402
from score_postrun import (  # noqa: E402
    load_gt,
    match_touches,
    rule_violations,
    score_reconstruction,
)
from src.postrun import ball_flights  # noqa: E402
from src.postrun.ball_flights import (  # noqa: E402
    EVENT_BIRTH,
    EVENT_CONTACT,
    EVENT_DEATH,
    GAP_FLIGHT,
    GAP_TOUCH,
    SOURCE_GAP,
    BallTimeline,
)
from src.postrun.geometry import (  # noqa: E402
    BALL_DIAMETER_M,
    NET_Y_M,
    CourtGeometry,
    other_side,
)
from src.postrun.match import death_winner  # noqa: E402
from src.postrun.rallies import (  # noqa: E402
    END_GROUND,
    RallyEnd,
    RallySegmenter,
    classify_landing,
)
from src.postrun.reconstruct import reconstruct  # noqa: E402
from src.postrun.stream import load_stream  # noqa: E402
from src.postrun.touches import reach_in_body_heights  # noqa: E402


def _actions(point):
    return [(t["side"], t["touch_number"], t["action"], t["player"])
            for t in point["touches"]]


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #

def test_ball_width_gives_depth_on_both_baselines_and_the_net():
    g = sim.geometry()
    assert g.court_y_from_width(g.ball_px_far) == pytest.approx(0.0, abs=1e-6)
    assert g.court_y_from_width(g.ball_px_near) == pytest.approx(16.0, abs=1e-6)
    assert g.court_y_from_width(g.ball_px_net) == pytest.approx(NET_Y_M, abs=1e-6)
    # behind the near baseline the ball is bigger than on the line
    assert g.court_y_from_width(g.ball_px_near * 1.1) > 16.0
    # owner formula (#77): D * w_near * w_far / (4 * (w_near + w_far))
    expected = BALL_DIAMETER_M * g.near_px * g.far_px / (4 * (g.near_px + g.far_px))
    assert g.ball_px_net == pytest.approx(expected)


def test_calibration_implies_a_regulation_net():
    # Independent check of the pinhole model: the two net-top clicks were
    # never used to build it, yet they land on a men's net (2.43 m).
    assert sim.geometry().net_top_height_m() == pytest.approx(2.43, abs=0.05)


def test_ball_world_inverts_the_projection():
    b = sim.StreamBuilder(1.0)
    for x, y, z in [(2.0, 3.0, 1.0), (6.5, 8.0, 2.43), (4.0, 14.0, 0.11)]:
        u, v, w = b.project(x, y, z)
        got = b.g.ball_world(u, v, float(b.g.court_y_from_width(w)))
        assert got == pytest.approx((x, y, z), abs=1e-6)


def test_homography_maps_the_clicked_corners():
    g = sim.geometry()
    assert g.image_to_world(*sim.CORNERS[0]) == pytest.approx((0.0, 0.0), abs=1e-6)
    assert g.image_to_world(*sim.CORNERS[2]) == pytest.approx((8.0, 16.0), abs=1e-6)
    assert g.image_to_world(900, 100) is None        # above the horizon
    assert other_side("near") == "far" and other_side(None) is None


def test_long_axis_view_is_required():
    with pytest.raises(ValueError):
        CourtGeometry([[0, 700], [1800, 700], [1200, 500], [600, 500]])


def test_reach_is_zero_inside_the_arm_box_and_scale_free():
    box = (100.0, 100.0, 160.0, 300.0)               # 200 px tall
    assert reach_in_body_heights(130, 200, box) == 0.0
    assert reach_in_body_heights(130, 40, box) == 0.0          # arms overhead
    assert reach_in_body_heights(130, -30, box) == pytest.approx(0.3)
    small = (100.0, 100.0, 130.0, 200.0)             # same pose, half the size
    assert reach_in_body_heights(115, 35, small) == pytest.approx(0.3)


# --------------------------------------------------------------------------- #
# ball timeline: gaps
# --------------------------------------------------------------------------- #

def _lob(builder, f0=10, f1=70):
    builder.fly(f0, (2.0, 12.0, 1.0), f1, (6.0, 4.0, 1.0), first=0, last_offset=1)


def test_gap_in_free_flight_is_the_same_flight():
    b = sim.StreamBuilder(4.0)
    _lob(b)
    b.hide(30, 40)
    tl = BallTimeline(b.build(), b.g)
    assert tl._gap_kind(29, 41) == GAP_FLIGHT
    assert [e.kind for e in tl.events] == [EVENT_BIRTH, EVENT_DEATH]


def test_gap_hiding_a_direction_change_becomes_a_vertex():
    b = sim.StreamBuilder(4.0)
    b.fly(10, (2.0, 12.0, 1.0), 40, (4.0, 5.0, 1.0), first=0)
    b.fly(40, (4.0, 5.0, 1.0), 80, (5.0, 5.5, 1.7), first=0, last_offset=1)
    b.hide(36, 46)                                    # the touch itself is hidden
    tl = BallTimeline(b.build(), b.g)
    assert tl._gap_kind(35, 47) == GAP_TOUCH
    gap_vertices = [e for e in tl.events if e.source == SOURCE_GAP]
    assert len(gap_vertices) == 1 and gap_vertices[0].kind == EVENT_CONTACT
    assert 36 <= gap_vertices[0].frame <= 46


def test_long_gap_is_a_break_and_a_classifier_vertex_suppresses_the_gap_vertex():
    b = sim.StreamBuilder(6.0)
    b.fly(10, (2.0, 12.0, 1.0), 40, (4.0, 5.0, 1.0), first=0)
    b.fly(40, (4.0, 5.0, 1.0), 120, (5.0, 5.5, 1.7), first=0, last_offset=1)
    b.hide(36, 36 + int(ball_flights.GAP_TOUCH_MAX_S * sim.FPS) + 5)
    tl = BallTimeline(b.build(), b.g)
    assert [e.kind for e in tl.events] == [EVENT_BIRTH, EVENT_DEATH, EVENT_BIRTH, EVENT_DEATH]

    b = sim.StreamBuilder(4.0)
    b.fly(10, (2.0, 12.0, 1.0), 40, (4.0, 5.0, 1.0), first=0)
    b.fly(40, (4.0, 5.0, 1.0), 80, (5.0, 5.5, 1.7), first=0, last_offset=1)
    b.hide(36, 46)
    b.vertex(41, (4.0, 5.0, 1.0))                     # perception saw it
    tl = BallTimeline(b.build(), b.g)
    assert [e.source for e in tl.events if e.kind == EVENT_CONTACT] == ["classifier"]


def test_flight_fit_reads_both_ends_in_metres():
    b = sim.StreamBuilder(4.0)
    b.vertex(10, (2.0, 13.0, 1.0))
    b.fly(10, (2.0, 13.0, 1.0), 50, (6.0, 4.0, 1.0), first=0, last_offset=1)
    b.vertex(50, (6.0, 4.0, 1.0))
    tl = BallTimeline(b.build(), b.g)
    flight = next(e for e in tl.events if e.kind == EVENT_CONTACT).flight_out
    assert flight.y_start == pytest.approx(13.0, abs=0.3)
    assert flight.y_end == pytest.approx(4.0, abs=0.3)
    assert flight.crosses_net
    assert flight.axis_speed_ms(sim.FPS) == pytest.approx(-9.0 / (40 / sim.FPS), abs=0.5)
    assert flight.peak_height_m == pytest.approx(1.0 + 9.81 * (40 / sim.FPS) ** 2 / 8, abs=0.15)


def test_clipped_boxes_are_not_depth_reads():
    b = sim.StreamBuilder(2.0)
    b.put_ball(5, 4.0, 10.0, 1.0)
    stream = b.build()
    stream.ball_bbox[5] = (0.0, 100.0, 20.0, 130.0)   # cut by the left edge
    assert BallTimeline(stream, b.g).clipped[5]


# --------------------------------------------------------------------------- #
# segmentation
# --------------------------------------------------------------------------- #

def _segment(builder):
    tl = BallTimeline(builder.build(), builder.g)
    return tl, RallySegmenter(tl).segment()


def test_near_serve_rally_is_one_point_with_its_touches():
    b = sim.StreamBuilder(12.0)
    frames = b.rally(sim.standard_rally(2.0, "near", sim.NEAR_A))
    _, found = _segment(b)
    assert len(found) == 1
    rally = found[0]
    assert rally.serve.side == "near" and rally.serve.observed
    assert rally.serve.frame == frames[0]
    assert [t.frame for t in rally.touches] == frames[1:]
    assert rally.end.kind == END_GROUND and rally.end.side == "near"
    assert rally.end.in_court is True


def test_far_serve_is_found_from_the_track_birth():
    b = sim.StreamBuilder(12.0)
    frames = b.rally(sim.standard_rally(2.0, "far", sim.NEAR_A))
    _, found = _segment(b)
    assert len(found) == 1
    serve = found[0].serve
    assert serve.side == "far" and not serve.observed
    assert abs(serve.frame - frames[0]) <= 3          # birth minus the lock delay
    assert [t.frame for t in found[0].touches] == frames[1:]


def test_dead_time_ball_handling_starts_no_point():
    b = sim.StreamBuilder(30.0)
    b.bounce_routine(2.0, (6.0, 16.8))                # pre-serve bounces at the line
    b.roll_back(6.0, (4.0, 5.0), (4.0, 15.0))         # rolled back under the net
    b.fly(300, (4.0, 12.5, 1.9), 345, (4.0, 4.0, 1.0), first=0, last_offset=1)  # lob from mid-court
    b.put_players(0, 899, sim.NEAR_A)
    _, found = _segment(b)
    assert found == []


def test_serve_into_the_net_and_serve_out_are_points_without_touches():
    b = sim.StreamBuilder(30.0)
    b.rally(sim.RallyScript(start_s=2.0, serve_xy=(2.0, -0.6), hits=[],
                            landing=(3.0, 7.6), landing_dt=1.0))
    b.rally(sim.RallyScript(start_s=14.0, serve_xy=(6.0, 16.8), hits=[],
                            landing=(-2.5, 3.0), landing_dt=1.3))
    _, found = _segment(b)
    assert [(r.serve.side, len(r.touches)) for r in found] == [("far", 0), ("near", 0)]
    assert found[0].serve.into_net and not found[1].serve.into_net
    assert found[1].end.kind == END_GROUND and found[1].end.in_court is False


def test_touches_after_the_ball_is_down_are_not_part_of_the_point():
    b = sim.StreamBuilder(14.0)
    script = sim.standard_rally(2.0, "near", sim.NEAR_A)
    frames = b.rally(script)
    land = frames[-1] + int(script.landing_dt * sim.FPS)
    # a player picks the dead ball up 1 s later and the classifier calls it a touch
    b.fly(land + 30, (4.0, 12.5, 0.2), land + 50, (4.2, 12.6, 1.1), first=0)
    b.vertex(land + 30, (4.0, 12.5, 0.2))
    _, found = _segment(b)
    assert len(found) == 1
    assert [t.frame for t in found[0].touches] == frames[1:]


def test_track_break_inside_a_rally_does_not_split_the_point():
    b = sim.StreamBuilder(16.0)
    frames = b.rally(sim.standard_rally(2.0, "near", sim.NEAR_A, exchanges=2))
    # the tracker loses the ball for 2 s around the far set
    b.hide(frames[2] - 20, frames[2] + 40)
    _, found = _segment(b)
    assert len(found) == 1
    assert found[0].touches[0].frame == frames[1]
    assert found[0].touches[-1].frame == frames[-1]


def test_rally_without_a_visible_serve_is_still_a_point():
    b = sim.StreamBuilder(16.0)
    frames = b.rally(sim.standard_rally(2.0, "near", sim.NEAR_A, exchanges=2))
    b.hide(0, frames[1] - 12)                         # serve and most of its flight unseen
    _, found = _segment(b)
    assert len(found) == 1
    assert found[0].serve.inferred and found[0].serve.side == "near"
    assert [t.frame for t in found[0].touches] == frames[1:]


def test_landing_calls_abstain_near_the_lines():
    assert classify_landing((4.0, 12.0)) == ("near", True)
    assert classify_landing((4.0, 2.0)) == ("far", True)
    assert classify_landing((-2.0, 3.0)) == ("far", False)
    assert classify_landing((0.3, 12.0)) == ("near", None)      # on the line
    assert classify_landing((4.0, 8.4)) == (None, True)         # at the net


# --------------------------------------------------------------------------- #
# touches
# --------------------------------------------------------------------------- #

def _reconstruct(builder, **kwargs):
    return reconstruct(builder.build(), builder.g, **kwargs)


def test_dig_set_spike_with_alternating_players():
    b = sim.StreamBuilder(12.0)
    b.rally(sim.standard_rally(2.0, "near", sim.NEAR_A))
    point = _reconstruct(b)["points"][0]
    assert _actions(point) == [
        ("near", 0, "serve", None),
        ("far", 1, "dig", "P1B"), ("far", 2, "set", "P2B"), ("far", 3, "spike", "P1B")]
    assert point["serve"]["team"] == "A" and point["near_team"] == "A"
    assert all(t["team"] == "B" for t in point["touches"][1:])
    assert rule_violations(point["touches"]) == {
        "same_player_twice": 0, "fourth_touch": 0, "reception_on_serving_half": 0}


def test_overpass_on_first_touch_and_attack_on_two():
    b = sim.StreamBuilder(14.0)
    hits = [
        sim.Hit(1.15, "P1B", sim.DIG_Z),              # reception goes straight back over
        sim.Hit(1.3, "P1A", sim.DIG_Z),
        sim.Hit(1.4, "P2A", sim.SPIKE_Z),             # attack on two
    ]
    b.rally(sim.RallyScript(start_s=2.0, serve_xy=(6.0, 16.8), hits=hits,
                            landing=(4.0, 3.5)))
    point = _reconstruct(b)["points"][0]
    assert _actions(point)[1:] == [
        ("far", 1, "overpass", "P1B"), ("near", 1, "dig", "P1A"),
        ("near", 2, "spike", "P2A")]


def test_low_third_touch_over_the_net_is_an_overpass_not_a_spike():
    b = sim.StreamBuilder(14.0)
    hits = [sim.Hit(1.15, "P1B", sim.DIG_Z), sim.Hit(1.6, "P2B", sim.SET_Z),
            sim.Hit(1.6, "P1B", 1.2),                 # bump pass over the net
            sim.Hit(1.5, "P1A", sim.DIG_Z)]
    b.rally(sim.RallyScript(start_s=2.0, serve_xy=(6.0, 16.8), hits=hits,
                            landing=(1.0, 14.0), landing_dt=0.8))
    actions = [a[2] for a in _actions(_reconstruct(b)["points"][0])]
    assert actions == ["serve", "dig", "set", "overpass", "dig"]


def test_unseen_touch_keeps_the_count_and_is_never_credited():
    b = sim.StreamBuilder(12.0)
    script = sim.standard_rally(2.0, "near", sim.NEAR_A)
    script.hits[1].seen = False                       # the set leaves no vertex...
    frames = b.rally(script)
    b.hide(frames[2] - 18, frames[2] + 22)            # ...the track broke for 1.3 s
    point = _reconstruct(b)["points"][0]
    body = point["touches"][1:]
    assert [(t["touch_number"], t["action"], t["evidence"]) for t in body] == [
        (1, "dig", "vertex"), (2, "set", "structure"), (3, "spike", "vertex")]
    assert body[1]["player"] is None                  # inferred, not credited
    assert body[0]["player"] == body[2]["player"] == "P1B"   # alternation still holds


def test_touch_hidden_in_a_short_gap_is_recovered_as_a_gap_vertex():
    b = sim.StreamBuilder(12.0)
    script = sim.standard_rally(2.0, "near", sim.NEAR_A)
    script.hits[1].seen = False
    frames = b.rally(script)
    b.hide(frames[2] - 6, frames[2] + 8)              # half a second around the set
    body = _reconstruct(b)["points"][0]["touches"][1:]
    assert [(t["action"], t["evidence"]) for t in body] == [
        ("dig", "vertex"), ("set", "gap"), ("spike", "vertex")]
    assert abs(body[1]["frame"] - frames[2]) <= 8


def test_touch_far_from_every_player_is_kept_but_not_credited():
    b = sim.StreamBuilder(12.0)
    script = sim.standard_rally(2.0, "near", sim.NEAR_A)
    script.hits[1].xy = (0.3, 2.0)                    # nobody stands there
    b.rally(script)
    body = _reconstruct(b)["points"][0]["touches"][1:]
    assert [t["action"] for t in body] == ["dig", "set", "spike"]
    assert body[1]["observed"] and body[1]["player"] is None


def test_perception_vertices_the_reach_gate_refused_are_touches_too():
    b = sim.StreamBuilder(12.0)
    script = sim.standard_rally(2.0, "near", sim.NEAR_A)
    script.hits[1].accepted = False
    b.rally(script)
    body = _reconstruct(b)["points"][0]["touches"][1:]
    assert [(t["action"], t["player"]) for t in body] == [
        ("dig", "P1B"), ("set", "P2B"), ("spike", "P1B")]


# --------------------------------------------------------------------------- #
# match
# --------------------------------------------------------------------------- #

def _match(serving_sides, switch_after=()):
    """One short point per entry; the winner is whoever serves next."""
    b = sim.StreamBuilder(12.0 * len(serving_sides) + 5.0)
    positions = sim.NEAR_A
    for i, side in enumerate(serving_sides):
        if i in switch_after:
            positions = sim.NEAR_B if positions is sim.NEAR_A else sim.NEAR_A
        b.rally(sim.standard_rally(2.0 + 12.0 * i, side, positions))
    return b


def test_next_serve_names_the_winner_and_the_score_follows():
    # near(A) serves, B attacks and it lands on A's half -> B serves next.
    result = _reconstruct(_match(["near", "far", "far", "near"]), points_to_win=3)
    points = result["points"]
    assert [p["serve"]["team"] for p in points] == ["A", "B", "B", "A"]
    assert [p["winner"] for p in points[:3]] == ["B", "B", "A"]
    assert [p["winner_source"] for p in points[:3]] == ["next_serve"] * 3
    assert points[2]["score_after"] == {"A": 1, "B": 2}
    # last point: A serves, B attacks, ball lands in on A's half -> B closes 3-1
    assert points[3]["winner"] == "B"
    assert result["checks"]["final_score"] == {"A": 1, "B": 3}
    assert result["checks"]["set_complete"]


def test_side_switch_is_where_the_near_half_changes_squad():
    result = _reconstruct(_match(["near", "far", "near", "far"], switch_after=(2,)),
                          points_to_win=21, switch_every=2)
    points = result["points"]
    assert [p["near_team"] for p in points] == ["A", "A", "B", "B"]
    # same squads serve from the other end after the switch
    assert [p["serve"]["team"] for p in points] == ["A", "B", "B", "A"]
    assert result["checks"]["side_switch_after_point"] == [2]
    assert result["checks"]["switch_blocks_ok"]


def test_ball_death_read():
    def rally(side, into_net=False):
        return type("R", (), {"serve": type("S", (), {"side": side, "into_net": into_net})(),
                              "end": None})()

    def touch(side, number):
        return type("T", (), {"side": side, "touch_number": number})()

    r = rally("near")
    r.end = RallyEnd(kind=END_GROUND, frame=1, side="far", in_court=True)
    assert death_winner(r, [touch("near", 0)]) == ("near", "ace")
    r.end = RallyEnd(kind=END_GROUND, frame=1, side="far", in_court=False)
    assert death_winner(r, [touch("near", 0)]) == ("far", "serve_out")
    net_serve = rally("far", into_net=True)
    net_serve.end = RallyEnd(kind=END_GROUND, frame=1, side=None, in_court=True)
    assert death_winner(net_serve, [touch("far", 0)]) == ("near", "serve_into_net")
    assert death_winner(rally("far"), [touch("far", 0)]) == (None, None)   # end unseen
    r.end = RallyEnd(kind=END_GROUND, frame=1, side="near", in_court=True)
    assert death_winner(r, [touch("near", 0), touch("far", 3)]) == ("far", "landed_in")
    assert death_winner(r, [touch("near", 0), touch("near", 2)]) == ("far", "died_on_own_half")
    r.end = RallyEnd(kind=END_GROUND, frame=1, side="near", in_court=None)
    assert death_winner(r, [touch("near", 0), touch("far", 3)]) == (None, None)


def test_service_order_names_the_server_nobody_saw():
    # A serves points 1-2 (same server), B 3, A 4 (the OTHER A player), B 5.
    sides = ["near", "near", "far", "near", "far", "near"]
    b = sim.StreamBuilder(12.0 * len(sides) + 5.0)
    for i, side in enumerate(sides):
        positions = dict(sim.NEAR_A)
        squad = "A" if side == "near" else "B"
        turn = [0, 0, 0, 1, 1, 2][i]
        server = f"P{1 + turn % 2}{squad}"
        partner = f"P{2 - turn % 2}{squad}"
        deep = 16.5 if side == "near" else -0.5
        positions[server] = (positions[server][0], deep)        # behind the line
        positions[partner] = (positions[partner][0], 9.5 if side == "near" else 6.5)
        if i == 3:
            # the server is out of the picture on this point
            positions[server] = (positions[server][0], 30.0)
        script = sim.standard_rally(2.0 + 12.0 * i, side, sim.NEAR_A)
        script.positions = positions
        b.rally(script)
    result = _reconstruct(b, points_to_win=21)
    servers = [p["serve"]["player"] for p in result["points"]]
    assert servers == ["P1A", "P1A", "P1B", "P2A", "P2B", "P1A"]
    order = result["checks"]["service_order"]
    assert order["A"]["first_server"] == "P1A" and order["A"]["applied"]


def test_touch_credited_after_the_ball_died_is_dropped_by_the_next_serve():
    b = sim.StreamBuilder(40.0)
    # Point 1: A serves, B's attack goes into the net and drops on B's half;
    # an A player then swats the dead ball (a vertex, in the air, on A's half).
    script = sim.standard_rally(2.0, "near", sim.NEAR_A, landing=(4.0, 7.0))
    frames = b.rally(script)
    b.rally(sim.standard_rally(16.0, "near", sim.NEAR_A))      # A serves again: A won
    b.rally(sim.standard_rally(28.0, "far", sim.NEAR_A))
    points = _reconstruct(b, points_to_win=21)["points"]
    assert points[0]["winner"] == "A"
    assert [t["frame"] for t in points[0]["touches"]] == frames


# --------------------------------------------------------------------------- #
# scorer
# --------------------------------------------------------------------------- #

def test_touch_matching_is_one_to_one_and_nearest_first():
    pred = [{"frame": 100}, {"frame": 110}, {"frame": 300}]
    gt = [{"frame": 108}, {"frame": 121}, {"frame": 400}]
    # 110 is nearest to 108 and takes it; 100 is then 21 f from the next GT
    assert match_touches(pred, gt) == [(1, 0)]
    assert match_touches([{"frame": 100}], [{"frame": 116}]) == []


def test_rule_violations_are_counted():
    touches = [
        {"side": "near", "player": None},
        {"side": "near", "player": "P1A"},            # reception on the serving half
        {"side": "near", "player": "P1A"},            # same player twice
        {"side": "near", "player": "P2A"},
        {"side": "near", "player": "P1A"},            # fourth touch
    ]
    assert rule_violations(touches) == {
        "same_player_twice": 1, "fourth_touch": 1, "reception_on_serving_half": 1}


# --------------------------------------------------------------------------- #
# the real match (skips when the run is not on disk)
# --------------------------------------------------------------------------- #

MATCH_RUN = REPO / "output" / "postrun" / "20260920_match"
MATCH_CAL = REPO / "calibrations" / "20260920_match_ari_joan_lost.json"


@pytest.fixture(scope="module")
def match_score():
    if not (MATCH_RUN / "diag.jsonl").exists() or not MATCH_CAL.exists():
        pytest.skip("20260920 match run (output/postrun/20260920_match) not on disk")
    stream = load_stream(str(MATCH_RUN / "diag.jsonl"))
    recon = json.loads(json.dumps(reconstruct(stream, CourtGeometry.from_file(str(MATCH_CAL)))))
    gt = load_gt(str(REPO / "ground_truth/20260920_match_contacts.json"),
                 str(REPO / "ground_truth/20260920_match_points.json"))
    return recon, score_reconstruction(recon, gt)


def test_match_points_serves_winners_and_score(match_score):
    recon, score = match_score
    assert score["points"] == {"recon": 33, "gt": 33, "matched": 33, "false": 0, "missed": []}
    assert score["serve"]["side_ok"] == 33 and score["serve"]["team_ok"] == 33
    assert score["winners"]["ok"] == 33
    assert recon["checks"]["final_score"] == {"A": 21, "B": 12}
    assert recon["checks"]["side_switch_after_point"] == [7, 14, 21, 28]
    assert recon["checks"]["set_complete"] and recon["checks"]["switch_blocks_ok"]


def test_match_touches_beat_the_bar_and_break_no_rule(match_score):
    _, score = match_score
    t = score["touches"]
    assert t["matched"] / t["pred"] >= 0.95           # precision first (owner rule)
    assert t["matched"] / t["gt"] >= 0.88
    assert t["action_ok"] / t["action_n"] >= 0.95
    assert t["side_ok"] == t["matched"]               # never a touch on the wrong half
    assert score["rules"] == {"same_player_twice": 0, "fourth_touch": 0,
                              "reception_on_serving_half": 0}
