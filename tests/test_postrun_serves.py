"""Post-run layer: the serves and rally ends the 20261010_1100 match lost.

The owner's score table of that video (35 points) against the first run (31)
gave four lost points and one serve read from the wrong half, each a serve
the ball alone leaves open:

* a near serve whose hit is seen and whose flight then leaves the picture;
* a far toss that reads inside the court, the ball next seen past the net;
* a toss the tracker joined to a ball seen elsewhere ("a teammate's pass");
* a serve into the net, the ball lying where it fell;
* a serve the tape stops and drops.

What lets them through is the owner's own cue -- at a serve everybody but the
server stands still -- so every scenario below is run twice: on a still
court, and with the players walking. The rest pins what the same review
changed downstream: a rally that goes on after a dig at sand level, a ball
thrown back after the point, the half of a last touch under the tape, and
"dug but never set is a kill".

Synthetic streams only (``postrun_sim``); the real videos are scored by
``scripts/score_postrun.py`` and ``scripts/score_postrun_points.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import postrun_sim as sim  # noqa: E402
import score_postrun_points  # noqa: E402
import write_frame_times  # noqa: E402
from src.postrun import rallies, touches  # noqa: E402
from src.postrun.ball_flights import BallTimeline  # noqa: E402
from src.postrun.geometry import CourtGeometry  # noqa: E402
from src.postrun.rallies import (  # noqa: E402
    CONFIRMED_STILL,
    END_GROUND,
    END_LOST,
    END_NET,
    RallySegmenter,
)
from src.postrun.reconstruct import (  # noqa: E402
    CLOCK_AVERAGE,
    CLOCK_VIDEO,
    format_report,
    load_frame_times,
    longest_rally,
    rally_shape,
    reconstruct,
)

#: The 20261010 calibration: a tripod at ~3 m, where a ball under half a
#: metre lines up with the sand right behind it (on the beach it never does).
HIGH_TRIPOD = ([[586, 419], [1229, 423], [1815, 911], [32, 899]],
               [[455, 266], [1386, 276]])


def _segment(builder):
    tl = BallTimeline(builder.build(), builder.g)
    segmenter = RallySegmenter(tl)
    return segmenter, segmenter.segment()


def _walk_about(builder, first, last, labels=("P1A", "P1B", "P2B"), positions=sim.NEAR_A):
    """The named players pace a metre to each side of their spot."""
    for f in range(max(first, 0), min(last, builder.n - 1) + 1):
        drift = float(np.sin(2.0 * np.pi * f / (1.5 * sim.FPS)))
        builder.put_players(f, f, {
            k: ((x + drift, y) if k in labels else (x, y))
            for k, (x, y) in positions.items()})


# --------------------------------------------------------------------------- #
# a still court
# --------------------------------------------------------------------------- #

def test_court_is_still_when_all_but_one_body_stand():
    b = sim.StreamBuilder(8.0)
    b.put_players(0, b.n - 1, sim.NEAR_A)
    segmenter, _ = _segment(b)
    assert segmenter.court_sway(150) == pytest.approx(0.0, abs=1e-6)
    # the server runs up to a jump serve: three still bodies are enough
    _walk_about(b, 60, 150, labels=("P2A",))
    segmenter, _ = _segment(b)
    assert segmenter._court_still(150)
    # two of them walking is a rally, or the ball going back between points
    _walk_about(b, 60, 150, labels=("P2A", "P1B"))
    segmenter, _ = _segment(b)
    assert segmenter.court_sway(150) > rallies.STILL_MAX_SWAY
    assert not segmenter._court_still(150)


def test_court_nobody_was_seen_on_is_not_still():
    b = sim.StreamBuilder(8.0)
    b.put_players(0, b.n - 1, {"P1A": sim.NEAR_A["P1A"], "P1B": sim.NEAR_A["P1B"]})
    segmenter, _ = _segment(b)
    assert segmenter.court_sway(150) is None and not segmenter._court_still(150)


# --------------------------------------------------------------------------- #
# serves the ball alone leaves open
# --------------------------------------------------------------------------- #

def _near_serve_out_of_the_picture(walking):
    """Toss and hit seen; the ball is next seen three frames before the
    reception (it flew over the top of the frame)."""
    b = sim.StreamBuilder(14.0)
    frames = b.rally(sim.standard_rally(2.0, "near", sim.NEAR_A))
    b.hide(frames[0] + 3, frames[1] - 4)
    if walking:
        _walk_about(b, frames[0] - 80, b.n - 1)
    return frames, _segment(b)[1]


def test_near_serve_leaving_the_picture_at_the_hit_is_found_on_a_still_court():
    frames, found = _near_serve_out_of_the_picture(walking=False)
    assert len(found) == 1
    serve = found[0].serve
    assert (serve.side, serve.frame, serve.observed) == ("near", frames[0], True)
    assert serve.confirmed_by == CONFIRMED_STILL and not serve.inferred
    assert [t.frame for t in found[0].touches] == frames[1:]
    # the same ball with the players walking about: not enough to call a serve
    _, found = _near_serve_out_of_the_picture(walking=True)
    assert found == []


def _far_toss_inside_the_court(walking, toss_y=1.5):
    """A far server whose toss the tracker follows (it reads 1.5 m inside the
    court: 2 px of ball width); the track dies at the hit and the ball is
    next seen past the net."""
    b = sim.StreamBuilder(14.0)
    script = sim.standard_rally(2.0, "far", sim.NEAR_A)
    script.hits[0].dt = 1.4
    frames = b.rally(script)
    hit = frames[0]
    b.hide(hit, hit + 31)
    for k in range(12, 0, -1):
        b.put_ball(hit - k, 2.0, toss_y, sim.SERVE_Z - 0.03 * k)
    if walking:
        _walk_about(b, hit - 80, hit)
    return frames, _segment(b)[1]


def test_far_toss_read_inside_the_court_is_a_serve_on_a_still_court():
    frames, found = _far_toss_inside_the_court(walking=False)
    assert len(found) == 1
    serve = found[0].serve
    assert serve.side == "far" and abs(serve.frame - frames[0]) <= 1
    assert serve.confirmed_by == CONFIRMED_STILL
    assert [t.frame for t in found[0].touches] == frames[1:]
    _, found = _far_toss_inside_the_court(walking=True)
    assert found == []
    # a toss placed without doubt, behind the baseline, needs nobody's help
    _, found = _far_toss_inside_the_court(walking=True, toss_y=-0.6)
    assert len(found) == 1 and found[0].serve.confirmed_by is None


def test_glimpse_past_the_net_after_a_far_toss_is_not_a_serve():
    # a far ball seen for half a second, then a ball glimpsed at the near
    # baseline (its server's toss): two balls, nobody moving -- no serve
    b = sim.StreamBuilder(10.0)
    b.put_players(0, b.n - 1, sim.NEAR_A)
    for k in range(12):
        b.put_ball(100 + k, 2.0, 2.4, 1.8 + 0.01 * k)
    for k in range(3):
        b.put_ball(135 + k, 6.0, 17.5, 2.0)
    b.vertex(138, (6.0, 17.5, 2.0))
    assert _segment(b)[1] == []


def test_toss_taken_for_a_pass_is_the_servers_own_on_a_still_court(monkeypatch):
    # the tracker joined the toss to a ball seen elsewhere: "fed by a pass"
    monkeypatch.setattr(RallySegmenter, "_fed_by_pass", lambda self, index: True)
    b = sim.StreamBuilder(14.0)
    frames = b.rally(sim.standard_rally(2.0, "near", sim.NEAR_A))
    _, found = _segment(b)
    assert len(found) == 1 and found[0].serve.frame == frames[0]
    assert found[0].serve.confirmed_by == CONFIRMED_STILL
    # with bodies moving it stays what the ball says, a pass: no launch is a
    # serve (the rally is still found, from its touches, without one)
    _walk_about(b, frames[0] - 80, b.n - 1)
    assert [r for r in _segment(b)[1] if not r.serve.inferred] == []


def _serve_into_the_net_left_lying(builder):
    """A near serve into the net; no vertex at the landing, the ball tracked
    for two more seconds where it fell."""
    script = sim.RallyScript(start_s=2.0, serve_xy=(6.0, 16.8), hits=[],
                             landing=(5.0, 8.7), landing_dt=1.0)
    frames = builder.rally(script)
    land = frames[0] + int(script.landing_dt * sim.FPS)
    builder.candidates = [c for c in builder.candidates if c.frame != land]
    for k in range(9, 60):
        builder.put_ball(land + k, 5.27, 8.7, 0.11)
    return frames


def test_serve_into_the_net_is_read_before_the_ball_lies_there(monkeypatch):
    b = sim.StreamBuilder(12.0)
    frames = _serve_into_the_net_left_lying(b)
    _, found = _segment(b)
    assert len(found) == 1
    serve = found[0].serve
    assert (serve.side, serve.frame, serve.into_net) == ("near", frames[0], True)
    assert found[0].touches == []
    # one line through the flight AND the rest reads the launch inside the court
    monkeypatch.setattr(RallySegmenter, "_airborne", lambda self, fl: fl)
    assert _segment(b)[1] == []


def _net_cord(walking):
    """A soft far serve the tape stops; the ball drops beside the net."""
    b = sim.StreamBuilder(12.0)
    tape = sim.Hit(1.7, None, 2.3, xy=(3.0, 8.0), accepted=False)
    frames = b.rally(sim.RallyScript(start_s=2.0, serve_xy=(2.0, -0.6), hits=[tape],
                                     landing=(3.0, 8.9), landing_dt=0.6))
    if walking:
        _walk_about(b, frames[0] - 80, frames[0])
    return frames, _segment(b)[1]


def test_serve_the_tape_stops_and_drops_is_a_point_on_a_still_court():
    frames, found = _net_cord(walking=False)
    assert len(found) == 1
    rally = found[0]
    assert rally.serve.side == "far" and rally.serve.into_net
    assert rally.serve.confirmed_by == CONFIRMED_STILL
    # the tape is where it ends: nobody "dug" it there
    assert rally.touches == [] and rally.end.kind == END_NET
    assert rally.end.frame == frames[1]
    _, found = _net_cord(walking=True)
    assert found == []


# --------------------------------------------------------------------------- #
# rally ends
# --------------------------------------------------------------------------- #

def _thrown_back_after(gap_s, played):
    b = sim.StreamBuilder(40.0)
    frames = b.rally(sim.standard_rally(2.0, "near", sim.NEAR_A))
    b.hide(frames[-1] + 6, frames[-1] + 60)           # the attack is never seen landing
    lost = frames[-1] + 5
    hits = [sim.Hit(1.2, "P1A", sim.DIG_Z), sim.Hit(1.6, "P2A", sim.SET_Z),
            sim.Hit(1.6, "P1A", sim.SPIKE_Z)] if played else []
    b.rally(sim.RallyScript(start_s=lost / sim.FPS + gap_s, serve_xy=(2.0, -0.6), hits=hits,
                            landing=(4.0, 12.5) if not played else (4.0, 3.5),
                            landing_dt=1.3))
    return lost, _segment(b)[1]


def test_ball_thrown_back_after_the_point_is_not_the_rallys_landing():
    # four seconds after the last sighting, to nobody: the ball going back
    lost, found = _thrown_back_after(4.0, played=False)
    assert len(found) == 1
    assert found[0].end.kind == END_LOST and found[0].end.frame <= lost + 1
    # played on, it is the same rally whose track broke
    lost, found = _thrown_back_after(4.0, played=True)
    assert len(found) == 1 and found[0].end.frame > lost + 60
    assert len(found[0].touches) == 6
    # ... and within one flight of the last sighting it can only be that ball
    lost, found = _thrown_back_after(2.0, played=False)
    assert len(found) == 1 and found[0].end.kind == END_GROUND


def _dive_dig():
    b = sim.StreamBuilder(16.0)
    b.g = CourtGeometry(*HIGH_TRIPOD)
    script = sim.standard_rally(2.0, "near", sim.NEAR_A, exchanges=2)
    script.hits[0].z = 0.12                           # dug off the sand ...
    script.hits[1].z, script.hits[1].dt = 0.2, 1.1    # ... and bumped up from the knees
    return b, b.rally(script)


def test_dig_at_sand_level_does_not_end_the_rally(monkeypatch):
    b, frames = _dive_dig()
    tl, found = _segment(b)[0].tl, _segment(b)[1]
    assert len(found) == 1
    assert [t.frame for t in found[0].touches] == frames[1:]
    # the ball is low for a few frames as it LEAVES the dig: no landing
    out = next(e for e in tl.events if e.frame == frames[1]).flight_out
    assert out.ground_frames >= rallies.GROUND_FLIGHT_FRAMES > out.landed_frames
    assert out.peak_height_m > 1.3
    # counted as a landing, those frames cut the rally at its reception
    monkeypatch.setattr(type(out), "landed_frames",
                        property(lambda self: self.ground_frames, lambda self, v: None))
    _, cut = _segment(b)
    assert [t.frame for t in cut[0].touches] != frames[1:]


def test_low_pass_followed_to_the_partner_does_not_end_the_rally(monkeypatch):
    # a dig off the sand that only pops the ball knee-high to the partner,
    # who sends it up: no bounce rises like that AND is played on
    b = sim.StreamBuilder(16.0)
    script = sim.standard_rally(2.0, "near", sim.NEAR_A, exchanges=2)
    script.hits[0].z = 0.3
    script.hits[1].z, script.hits[1].dt = 0.5, 0.6
    frames = b.rally(script)
    tl, found = _segment(b)[0].tl, _segment(b)[1]
    out = next(e for e in tl.events if e.frame == frames[1]).flight_out
    assert out.peak_height_m < rallies.SAND_REBOUND_MAX_M
    assert [t.frame for t in found[0].touches] == frames[1:]
    # the same low flight with the ball lost on the way is a bounce
    monkeypatch.setattr(rallies, "SEEN_TO_NEXT_SHARE", 1.5)
    assert [t.frame for t in _segment(b)[1][0].touches] == []


# --------------------------------------------------------------------------- #
# touches and outcomes
# --------------------------------------------------------------------------- #

def _dug_then(second_z, third_z=sim.SPIKE_Z, landing_dt=0.45, second_xy=(5.5, 8.2)):
    """A serves; B digs, sets and sends it over at ``third_z``; P1A digs and
    P2A gets a hand to it (at the net unless told otherwise), ``second_z``
    up -- the ball comes down on A's half. Then B serves (B won)."""
    b = sim.StreamBuilder(34.0)
    hits = [sim.Hit(1.15, "P1B", sim.DIG_Z), sim.Hit(1.6, "P2B", sim.SET_Z),
            sim.Hit(1.6, "P1B", third_z),
            sim.Hit(1.1, "P1A", sim.DIG_Z),
            sim.Hit(1.3, "P2A", second_z, xy=second_xy)]
    # B's setter stays at the net, a step from where P2A reaches the ball
    b.rally(sim.RallyScript(start_s=2.0, serve_xy=(6.0, 16.8), hits=hits,
                            landing=(5.2, 10.8), landing_dt=landing_dt,
                            positions={**sim.NEAR_A, "P2A": (5.5, 9.6), "P2B": (5.5, 7.3)}))
    b.rally(sim.standard_rally(20.0, "far", sim.NEAR_A))
    return reconstruct(b.build(), b.g)["points"][0]


def test_last_touch_under_the_tape_is_on_the_half_the_ball_fell_on(monkeypatch):
    # half a metre from the net the ball's depth says "far"; it never rose to
    # the tape after the touch and came down on the near half
    point = _dug_then(second_z=0.9)
    last = point["touches"][-1]
    assert (last["side"], last["touch_number"], last["player"]) == ("near", 2, "P2A")
    assert point["touches"][-2]["action"] == "dig"
    monkeypatch.setattr(touches, "UNDER_TAPE_COST", 0.0)
    assert _dug_then(second_z=0.9)["touches"][-1]["side"] == "far"


def test_spike_dug_and_never_set_is_a_kill():
    point = _dug_then(second_z=0.9)
    spike, dig, last = point["touches"][-3:]
    assert point["winner"] == "B"
    assert (spike["action"], spike["outcome"]) == ("spike", "kill")
    assert dig["outcome"] is None and last["outcome"] is None    # nobody's error
    # a real set that then drops is the setter's own (the ball went up)
    point = _dug_then(second_z=sim.SET_Z, landing_dt=1.7, second_xy=(5.5, 10.2))
    assert point["touches"][-1]["outcome"] == "error"
    assert point["touches"][-3]["outcome"] is None
    # an easy ball dug and dropped by the setter is his handling error
    point = _dug_then(second_z=0.9, third_z=1.2, second_xy=(5.5, 10.2))
    assert point["touches"][-3]["action"] == "overpass"
    assert point["touches"][-3]["outcome"] is None
    assert point["touches"][-1]["outcome"] == "error"


def test_serve_dug_and_never_set_is_an_ace():
    b = sim.StreamBuilder(34.0)
    hits = [sim.Hit(1.15, "P1A", sim.DIG_Z), sim.Hit(1.3, "P2A", 0.9, xy=(5.5, 9.5))]
    b.rally(sim.RallyScript(start_s=2.0, serve_xy=(2.0, -0.6), hits=hits,
                            landing=(5.2, 10.8), landing_dt=0.45))
    b.rally(sim.standard_rally(20.0, "far", sim.NEAR_A))
    point = reconstruct(b.build(), b.g)["points"][0]
    assert point["serve"]["outcome"] == "ace" and point["winner"] == "B"
    assert [t["outcome"] for t in point["touches"][1:]] == [None, None]


# --------------------------------------------------------------------------- #
# what the owner reads: the longest rally, the video's clock
# --------------------------------------------------------------------------- #

def _t(side, team):
    return {"side": side, "team": team}


def test_rally_shape_counts_touches_and_net_crossings():
    serve, dig, set_, spike = _t("near", "A"), _t("far", "B"), _t("far", "B"), _t("far", "B")
    # serve over, attack back over and down: two crossings
    assert rally_shape([serve, dig, set_, spike], "B") == {"touches": 4, "net_crossings": 2}
    # the attack goes into the net: only the serve crossed
    assert rally_shape([serve, dig, set_, spike], "A") == {"touches": 4, "net_crossings": 1}
    assert rally_shape([serve], "A") == {"touches": 1, "net_crossings": 1}      # an ace
    assert rally_shape([serve], "B") == {"touches": 1, "net_crossings": 0}      # into the net


def test_longest_rally_is_in_the_checks_and_the_report():
    b = sim.StreamBuilder(40.0)
    b.rally(sim.standard_rally(2.0, "near", sim.NEAR_A))
    b.rally(sim.standard_rally(14.0, "far", sim.NEAR_A, exchanges=3))
    result = json.loads(json.dumps(reconstruct(b.build(), b.g)))
    assert [p["rally"]["touches"] for p in result["points"]] == [4, 10]
    longest = result["checks"]["longest_rally"]
    assert (longest["point"], longest["touches"], longest["net_crossings"]) == (2, 10, 4)
    assert longest == longest_rally(result["points"])
    report = format_report(result)
    assert "Longest rally: P2, 10 touches, the ball crossed the net 4 times" in report


def test_report_clock_is_the_videos_own_when_it_is_on_disk():
    b = sim.StreamBuilder(14.0)
    frames = b.rally(sim.standard_rally(2.0, "near", sim.NEAR_A))
    stream = b.build()
    plain = json.loads(json.dumps(reconstruct(stream, b.g)))
    assert plain["clock"] == CLOCK_AVERAGE
    assert plain["points"][0]["start_time_s"] == pytest.approx(frames[0] / sim.FPS, abs=0.05)
    assert "average frame rate" in format_report(plain)
    # the camera ran at 25 fps: every frame is later on the player's clock
    stream.frame_times = np.arange(stream.n_frames) / 25.0
    timed = json.loads(json.dumps(reconstruct(stream, b.g)))
    assert timed["clock"] == CLOCK_VIDEO
    assert timed["points"][0]["start_time_s"] == pytest.approx(frames[0] / 25.0, abs=0.05)
    assert "average frame rate" not in format_report(timed)
    # ... and nothing but the clock moved
    for key in ("start_time_s", "end_time_s", "rally"):
        plain["points"][0].pop(key), timed["points"][0].pop(key)
    assert plain["points"] == timed["points"]


def test_frame_times_of_another_video_are_refused(tmp_path):
    path = tmp_path / "frame_times.json"
    assert load_frame_times(path, 3) is None                     # no file
    path.write_text(json.dumps({"times_s": [0.0, 0.04, 0.08]}))
    assert list(load_frame_times(path, 3)) == [0.0, 0.04, 0.08]
    assert load_frame_times(path, 4) is None                     # not this run's frames
    path.write_text(json.dumps({"times_s": [0.0, 0.08, 0.04]}))
    assert load_frame_times(path, 3) is None                     # not a clock


def test_frame_times_are_the_packets_the_decoder_shows(monkeypatch):
    class Done:
        stdout = "0.080000\n-0.040000\n0.000000\n0.040000,\nN/A\n"

    monkeypatch.setattr(write_frame_times.subprocess, "run", lambda *a, **k: Done())
    # presentation order, without the frames before time zero
    assert write_frame_times.packet_times(Path("x.mp4")) == [0.0, 0.04, 0.08]


def test_score_table_pairs_points_by_serve_time():
    def point(n, t, team, winner):
        return {"point": n, "start_time_s": t, "serve": {"team": team}, "winner": winner}

    recon = {"points": [point(1, 4.2, "B", "A"), point(2, 41.0, "A", "B"),
                        point(3, 60.0, "B", "B"), point(4, 69.3, "B", "A")],
             "checks": {"final_score": {"A": 2, "B": 2}, "side_switch_after_point": []}}
    gt = {"final_score": {"A": 1, "B": 3}, "side_switch_after_point": [],
          "points": [
              {"point": 1, "serve_time_s": 4, "serve_team": "B", "winner": "A"},
              {"point": 2, "serve_time_s": 43, "serve_team": "A", "winner": "B"},
              {"point": 3, "serve_time_s": 69, "serve_team": "B", "winner": "B"},
              {"point": 4, "serve_time_s": 94, "serve_team": "B", "winner": "B"}]}
    score = score_postrun_points.score_points(recon, gt)
    assert (score["matched"], score["false"], score["missed"]) == (3, [3], [4])
    assert score["serve_team_ok"] == 3
    assert (score["winners_ok"], score["winners_wrong"]) == (2, [3])
