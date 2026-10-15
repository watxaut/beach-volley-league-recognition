"""Owner review page (src/web/review.py): the verdict rules, on a drawn match.

No video, no run on disk: a two-point reconstruction and a rally copy index
written by hand. The page's JS mirrors ``label_map``; these are its
definition.
"""

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.publish.clips import RallyCopy
from src.publish.gaps import GapCopy, dead_spans
from src.web import review as R


def _touch(frame, action, player, **extra):
    return {"frame": frame, "action": action, "player": player, "team": player[2] if player else None,
            "side": "near", "outcome": None, "observed": True, "spike_type": None, **extra}


def _recon():
    return {
        "fps": 25.0,
        "checks": {"final_score": {"A": 1, "B": 1}, "side_switch_after_point": [],
                   "points_between_switches": [2], "undecided_points": []},
        "identity": {"applied": False},
        "points": [
            {"point": 1, "start_frame": 100, "end_frame": 200, "start_time_s": 4.0,
             "near_team": "A", "serve": {"team": "B", "player": "P2B"}, "end": {"kind": "ground"},
             "winner": "A", "winner_source": "next_serve", "score_after": {"A": 1, "B": 0},
             "flags": [], "touches": [_touch(100, "serve", "P2B"), _touch(130, "dig", "P1A"),
                                      _touch(150, "set", "P2A"), _touch(170, "spike", "P1A")]},
            {"point": 2, "start_frame": 400, "end_frame": 460, "start_time_s": 16.0,
             "near_team": "A", "serve": {"team": "A", "player": "P1A"}, "end": {"kind": "ground"},
             "winner": "B", "winner_source": "ball_death", "score_after": {"A": 1, "B": 1},
             "flags": ["unseen_final_attack"], "touches": [_touch(400, "serve", "P1A")]},
        ],
    }


def _copy():
    # 1 s before each serve, 2 s after each end, at 25 fps.
    return RallyCopy(path=Path("rallies.mp4"), fps=25.0, size=(640, 444),
                     crop=(370, 0, 1030, 716), spans=[(75, 250), (375, 510)])


@pytest.fixture
def points():
    return R.match_view(_recon(), _copy())["points"]


# --------------------------------------------------------------------------- #
# the rally copy
# --------------------------------------------------------------------------- #

def test_copy_position_counts_only_kept_frames():
    copy = _copy()
    assert copy.position(75) == 0
    assert copy.position(250) == 175
    assert copy.position(375) == 176              # the second stretch follows the first
    assert copy.position(300) is None             # dead time is not in the copy


def test_a_point_plays_from_its_own_stretch(points):
    assert points[0]["segment"] == {"first": 75, "last": 250, "copy_first": 0}
    assert points[1]["segment"] == {"first": 375, "last": 510, "copy_first": 176}
    assert points[1]["score_before"] == {"A": 1, "B": 0}


def test_rallies_that_run_together_keep_their_own_padding():
    copy = RallyCopy(path=Path("x"), fps=25.0, size=(640, 444), crop=(0, 0, 10, 10),
                     spans=[(75, 400)])
    assert R.copy_segment(copy, 100, 200) == (75, 250, 0)
    assert R.copy_segment(copy, 260, 350) == (235, 400, 160)
    assert R.copy_segment(copy, 900, 950) is None


def test_a_match_without_a_copy_still_lists_its_points():
    view = R.match_view(_recon(), None)
    assert [p["segment"] for p in view["points"]] == [None, None]
    assert view["crop"] is None


# --------------------------------------------------------------------------- #
# who is who
# --------------------------------------------------------------------------- #

def test_no_label_fix_maps_every_label_to_itself():
    assert R.label_map("A", {}) == {p: p for p in R.PLAYERS}


def test_a_pair_swap_touches_only_that_half():
    near = R.label_map("A", {"near_swapped": True})
    assert near == {"P1A": "P2A", "P2A": "P1A", "P1B": "P1B", "P2B": "P2B"}
    far = R.label_map("A", {"far_swapped": True})
    assert far == {"P1A": "P1A", "P2A": "P2A", "P1B": "P2B", "P2B": "P1B"}
    # the same key means the other squad once that squad is near
    assert R.label_map("B", {"near_swapped": True})["P1B"] == "P2B"


def test_squads_on_the_wrong_halves_rename_every_body():
    assert R.label_map("A", {"sides_swapped": True}) == {
        "P1A": "P1B", "P2A": "P2B", "P1B": "P1A", "P2B": "P2A"}


def test_a_pair_swap_is_read_on_the_half_as_it_really_is():
    # The run says A is near; really B is. The bodies labelled A are B's, and
    # "near pair swapped" is about them.
    names = R.label_map("A", {"sides_swapped": True, "near_swapped": True})
    assert names == {"P1A": "P2B", "P2A": "P1B", "P1B": "P1A", "P2B": "P2A"}


def test_other_is_a_flag_and_maps_nothing():
    assert R.label_map("A", {"other": True}) == {p: p for p in R.PLAYERS}


# --------------------------------------------------------------------------- #
# verdicts
# --------------------------------------------------------------------------- #

def test_all_right_keeps_the_runs_read_as_the_truth(points):
    v = R.clean_verdict({"status": "ok"}, points[0])
    assert v["status"] == "ok" and not R.has_corrections(v)
    assert v["truth"] == {
        "is_point": True, "winner": "A", "near_team": "A", "serve_team": "B",
        "labels_unclear": False,
        "touches": [{"frame": 100, "action": "serve", "player": "P2B"},
                    {"frame": 130, "action": "dig", "player": "P1A"},
                    {"frame": 150, "action": "set", "player": "P2A"},
                    {"frame": 170, "action": "spike", "player": "P1A"}]}
    assert v["run"]["touches"][0] == [100, "serve", "P2B"]


def test_ok_with_a_correction_is_stored_as_corrected(points):
    v = R.clean_verdict({"status": "ok", "note": "the set is a bump"}, points[0])
    assert v["status"] == "corrected"


def test_a_label_fix_moves_the_touches_unless_the_owner_named_the_player(points):
    v = R.clean_verdict({"status": "corrected", "labels": {"near_swapped": True},
                         "touches": {"170": {"player": "P1A"}}}, points[0])
    players = [t["player"] for t in v["truth"]["touches"]]
    assert players == ["P2B", "P2A", "P1A", "P1A"]


def test_touch_corrections_removed_retyped_added(points):
    v = R.clean_verdict({"status": "corrected",
                         "touches": {"150": {"remove": True}, "170": {"action": "overpass"},
                                     "130": {"player": None}},
                         "added": [{"frame": 190, "action": "block", "player": "P1B"}]},
                        points[0])
    assert v["truth"]["touches"] == [
        {"frame": 100, "action": "serve", "player": "P2B"},
        {"frame": 130, "action": "dig", "player": None},
        {"frame": 170, "action": "overpass", "player": "P1A"},
        {"frame": 190, "action": "block", "player": "P1B"}]


def test_an_unnamed_body_takes_the_name_the_owner_gives_it(points):
    point = dict(points[0])
    point["touches"] = [dict(t) for t in point["touches"]]
    point["touches"][1]["player"] = "T4"          # a half the identity read withheld
    v = R.clean_verdict({"status": "ok"}, point)
    assert v["status"] == "ok" and v["truth"]["touches"][1]["player"] == "T4"
    v = R.clean_verdict({"status": "ok", "names": {"T4": "P1A"}}, point)
    assert v["status"] == "corrected" and v["truth"]["touches"][1]["player"] == "P1A"
    for bad in ({"P1A": "P2A"}, {"T4": "T5"}, {"T4": None}):
        with pytest.raises(ValueError):
            R.clean_verdict({"status": "ok", "names": bad}, point)


def test_winner_override_and_not_a_point(points):
    assert R.clean_verdict({"status": "corrected", "winner": "B"}, points[0])["truth"]["winner"] == "B"
    assert R.clean_verdict({"status": "corrected", "winner": "none"},
                           points[0])["truth"]["winner"] is None
    v = R.clean_verdict({"status": "corrected", "not_a_point": True}, points[0])
    assert v["truth"] == {"is_point": False}


def test_squads_swapped_flips_the_near_team_and_the_server(points):
    v = R.clean_verdict({"status": "corrected", "labels": {"sides_swapped": True}}, points[0])
    assert v["truth"]["near_team"] == "B"
    assert v["truth"]["serve_team"] == "A"            # the body labelled P2B is P2A
    assert v["truth"]["winner"] == "A"                # a winner is only changed by the owner


@pytest.mark.parametrize("raw", [
    {"status": "maybe"},
    {"status": "ok", "winner": "C"},
    {"status": "corrected", "touches": {"131": {"action": "dig"}}},        # no such touch
    {"status": "corrected", "touches": {"130": {"action": "smash"}}},
    {"status": "corrected", "touches": {"130": {"player": "P3A"}}},
    {"status": "corrected", "added": [{"frame": 5000, "action": "dig", "player": None}]},
    {"status": "corrected", "added": [{"frame": 190, "player": "P1A"}]},   # no action
])
def test_what_is_not_a_verdict_is_refused(points, raw):
    with pytest.raises((ValueError, KeyError)):
        R.clean_verdict(raw, points[0])


# --------------------------------------------------------------------------- #
# a review against a run that moved
# --------------------------------------------------------------------------- #

def _review(points, *raws):
    review = R.empty_review("k")
    for point, raw in zip(points, raws):
        R.put_verdict(review, R.clean_verdict(raw, point), point["start_frame"])
    return review


def test_verdicts_attach_to_their_points(points):
    review = _review(points, {"status": "ok"}, {"status": "corrected", "winner": "A"})
    by_point, orphans = R.attach(review, points)
    assert sorted(by_point) == [1, 2] and not orphans
    assert not by_point[1]["run_changed"] and not by_point[2]["run_changed"]


def test_a_verdict_follows_its_rally_when_the_points_are_renumbered(points):
    review = _review(points, {"status": "ok"}, {"status": "ok"})
    # a rules change finds a rally before the first one and moves a serve frame
    recon = _recon()
    recon["points"][0]["start_frame"] = 96
    for p in recon["points"]:
        p["point"] += 1
    recon["points"].insert(0, {**recon["points"][0], "point": 1, "start_frame": 10,
                               "end_frame": 40, "touches": []})
    moved = R.match_view(recon, None)["points"]
    by_point, orphans = R.attach(review, moved)
    assert sorted(by_point) == [2, 3] and not orphans
    assert by_point[2]["run"]["point"] == 1          # reviewed as point 1
    assert not by_point[2]["run_changed"]            # same winner, server, touches


def test_a_changed_read_is_flagged_and_a_lost_rally_is_an_orphan(points):
    review = _review(points, {"status": "ok"}, {"status": "ok"})
    recon = _recon()
    recon["points"][0]["winner"] = "B"
    del recon["points"][1]
    by_point, orphans = R.attach(review, R.match_view(recon, None)["points"])
    assert by_point[1]["run_changed"]
    assert [o["start_frame"] for o in orphans] == [400]


def test_the_score_follows_the_corrections(points):
    review = _review(points, {"status": "corrected", "winner": "B"},
                     {"status": "corrected", "not_a_point": True})
    by_point, _ = R.attach(review, points)
    missing = [{"after_point": 1, "winner": "A"}, {"after_point": 2, "winner": None}]
    assert R.reviewed_score(points, by_point, missing) == {"A": 1, "B": 1, "undecided": 1}
    assert R.reviewed_score(points, {}, []) == {"A": 1, "B": 1, "undecided": 0}


def _rows(*rows):
    return [{"point": n, "after_point": after, "serve_team": s, "winner": w, "near_team": near}
            for n, after, s, w, near in rows]


def test_the_reviewed_sequence_holds_added_and_dropped_points(points):
    review = _review(points, {"status": "corrected", "winner": "B"},
                     {"status": "corrected", "not_a_point": True})
    by_point, _ = R.attach(review, points)
    rows = R.sequence(points, by_point, [{"after_point": 1, "winner": "A", "serve_team": "B"},
                                         {"after_point": 0, "winner": None}])
    assert [(r["point"], r["winner"], r["serve_team"]) for r in rows] == [
        (None, None, None), (1, "B", "B"), (None, "A", "B")]
    assert rows[2]["near_team"] == "A"                  # an added point is played where the last was


def test_the_winner_of_a_point_serves_the_next_one():
    rows = _rows((1, 0, "A", "A", "A"), (2, 0, "A", "B", "A"), (3, 0, "A", "A", "A"),
                 (None, 3, "B", "A", "A"), (4, 0, "A", None, "A"))
    assert R.consistency(rows) == [
        "Point 3 is served by A, but point 2 was won by B: one of the two is wrong, "
        "or a point is missing between them.",
        "The point you added after point 3 is served by B, but point 3 was won by A: "
        "one of the two is wrong, or a point is missing between them."]


def test_the_ends_change_every_seven_points():
    def block(first, n, near):
        return [(first + i, 0, None, None, near) for i in range(n)]
    assert R.consistency(_rows(*block(1, 7, "A"), *block(8, 7, "B"), *block(15, 3, "A"))) == []
    short = R.consistency(_rows(*block(1, 6, "A"), *block(7, 8, "B"), *block(15, 3, "A")))
    assert short == [
        "6 points between point 1 and the side switch after point 6 (7 expected): "
        "a point may be missing there, or the players changed ends on another point.",
        "8 points between point 7 and the side switch after point 14 (7 expected): "
        "a rally there may be no point, or the players changed ends on another point."]


def test_match_fields(points):
    out = R.clean_match_fields(
        {"owner_final_score": {"A": "21", "B": 15},
         "missing_points": [{"after_point": 2, "winner": "B", "note": " a serve into the net "},
                            {"after_point": 0, "winner": None}]}, points)
    assert out["owner_final_score"] == {"A": 21, "B": 15}
    assert out["missing_points"] == [
        {"after_point": 0, "after_frame": 0, "winner": None, "note": ""},
        {"after_point": 2, "after_frame": 400, "winner": "B", "note": "a serve into the net"}]
    with pytest.raises(ValueError):
        R.clean_match_fields({"missing_points": [{"after_point": 9}]}, points)


# --------------------------------------------------------------------------- #
# the dead time: is a point missing?
# --------------------------------------------------------------------------- #

def test_dead_spans_are_what_the_rally_copy_leaves_out():
    assert dead_spans([(75, 250), (375, 510)]) == [(0, 74), (251, 374), (511, None)]
    assert dead_spans([(0, 10), (11, 20)]) == [(21, None)]       # rallies that touch


def test_a_gap_copy_knows_which_frame_each_of_its_frames_is():
    gaps = GapCopy(path=Path("gaps.mp4"), fps=25.0, size=(640, 360), step=3,
                   spans=[(0, 72), (251, 374), (511, 598)])      # kept: 0, 3 ... 72 | 251 ...
    assert gaps.segment(0, 74) == (0, 0, 25)
    assert gaps.segment(251, 374) == (251, 25, 42)               # 25 frames before it
    assert gaps.segment(260, 270) == (260, 28, 4)                # 260, 263, 266, 269
    assert gaps.segment(100, 200) is None                        # inside a rally
    assert gaps.to_json()["frames"] == 25 + 42 + 30


def _gaps(points, contacts=None, copy=None):
    return R.gaps_view(points, n_frames=600, fps=25.0, copy=copy, contacts=contacts)


def test_gaps_are_the_stretches_around_the_points(points):
    gaps = _gaps(points)
    assert [(g["after_point"], g["before_point"], g["first"], g["last"]) for g in gaps] == [
        (0, 1, 0, 74), (1, 2, 251, 374), (2, None, 511, 599)]
    assert gaps[1]["seconds"] == 5.0 and gaps[1]["segment"] is None
    assert not any(g["flagged"] for g in gaps)


def test_a_gap_is_flagged_where_the_ball_was_played(points):
    gaps = _gaps(points, contacts=[20, 300, 310, 320, 560])
    assert [g["contacts"] for g in gaps] == [1, 3, 1]
    assert [g["flagged"] for g in gaps] == [False, True, False]
    assert "played 3 times" in gaps[1]["why"][0]


def test_a_gap_is_flagged_when_the_pause_is_much_longer_than_usual():
    recon = _recon()
    base = recon["points"][1]
    recon["points"] += [{**base, "point": 3, "start_frame": 600, "end_frame": 650},
                        {**base, "point": 4, "start_frame": 1500, "end_frame": 1550},
                        {**base, "point": 5, "start_frame": 1700, "end_frame": 1750}]
    gaps = R.gaps_view(R.match_view(recon, None)["points"], 2000, 25.0)
    assert [g["after_point"] for g in gaps if g["flagged"]] == [3]     # 34 s against 8 s
    assert not gaps[0]["flagged"] and not gaps[-1]["flagged"]          # the ends are no pause


def test_a_gap_gets_its_picture_from_the_gap_copy(points):
    copy = GapCopy(path=Path("gaps.mp4"), fps=25.0, size=(640, 360), step=3,
                   spans=[(0, 72), (251, 374), (511, 598)])
    assert _gaps(points, copy=copy)[1]["segment"] == {
        "first": 251, "copy_first": 25, "n": 42, "step": 3}


def test_a_checked_gap_stays_checked_when_its_edges_move(points):
    review = R.empty_review("k")
    gaps = _gaps(points)
    R.put_gap(review, gaps[1], True)
    assert R.gap_states(review, gaps) == {1: "checked"}
    moved = dict(gaps[1], first=262, last=380)                   # a rules change moved a serve
    assert R.gap_states(review, [gaps[0], moved, gaps[2]]) == {1: "checked"}
    R.put_gap(review, moved, False)
    assert review["gaps"] == [] and R.gap_states(review, gaps) == {}


def test_a_gap_can_be_the_rest_of_the_point_before_it(points):
    """The run ended a rally too early: what plays on in the dead time is the
    same point, not a missing one."""
    review = R.empty_review("k")
    gaps = _gaps(points)
    R.put_gap(review, gaps[1], True, tail_frame=300)
    assert review["gaps"] == [{"first": 251, "last": 374, "status": "tail",
                               "rally_goes_on_to": 300}]
    assert R.gap_states(review, gaps) == {1: "tail"}
    R.put_gap(review, gaps[1], True)                             # changed his mind
    assert R.gap_states(review, gaps) == {1: "checked"}


def test_a_missing_point_keeps_the_frame_the_owner_marked(points):
    out = R.clean_match_fields({"missing_points": [
        {"after_point": 1, "winner": "A", "at_frame": 300.0, "serve_team": "B"}]}, points)
    assert out["missing_points"][0]["at_frame"] == 300
    assert out["missing_points"][0]["serve_team"] == "B"
    with pytest.raises(ValueError):
        R.clean_match_fields({"missing_points": [{"after_point": 1, "serve_team": "C"}]}, points)


# --------------------------------------------------------------------------- #
# on disk, through the routes
# --------------------------------------------------------------------------- #

def _run_dir(root: Path, key: str = "20990101_1000_test_a_b_c_d") -> Path:
    run = root / "output" / key
    run.mkdir(parents=True)
    (run / R.RECON_NAME).write_text(json.dumps(_recon()))
    (run / "rallies.json").write_text(json.dumps(_copy().to_json()))
    (run / "rallies.mp4").write_bytes(b"")
    (run / R.DIAG_NAME).write_text("")
    return run


def _endpoint(router, name):
    return next(r.endpoint for r in router.routes if r.endpoint.__name__ == name)


def test_runs_are_found_with_what_they_lack(tmp_path):
    run = _run_dir(tmp_path)
    bare = tmp_path / "output" / "20990102_1000_no_copy"
    bare.mkdir()
    (bare / R.RECON_NAME).write_text("{}")
    (tmp_path / "output" / "not_a_run").mkdir()
    runs = R.find_runs(tmp_path / "output")
    assert [(r["key"], r["reviewable"]) for r in runs] == [
        ("20990102_1000_no_copy", False), (run.name, True)]


def test_saving_a_point_writes_the_owner_file_and_undo_removes_it(tmp_path):
    run = _run_dir(tmp_path)
    gt = tmp_path / "ground_truth"
    router = R.create_router(tmp_path / "output", gt)
    save_point, save_match = _endpoint(router, "save_point"), _endpoint(router, "save_match")

    state = save_point(run.name, 1, {"status": "ok"})
    assert state["verdicts"][1]["status"] == "ok"
    state = save_point(run.name, 2, {"status": "corrected", "winner": "A"})
    assert state["reviewed_score"] == {"A": 2, "B": 0, "undecided": 0}
    state = save_match(run.name, {"owner_final_score": {"A": 2, "B": 1},
                                  "missing_points": [{"after_point": 2, "winner": "B"}]})
    assert state["reviewed_score"] == {"A": 2, "B": 1, "undecided": 0}

    stored = json.loads(R.review_path(gt, run.name).read_text())
    assert stored["format"] == R.REVIEW_FORMAT and stored["match_key"] == run.name
    assert [v["start_frame"] for v in stored["points"]] == [100, 400]
    assert stored["points"][1]["truth"]["winner"] == "A"
    assert not list(gt.glob("*.tmp"))

    save_gap = _endpoint(router, "save_gap")
    assert save_gap(run.name, 1, {"checked": True})["gaps"] == {1: "checked"}
    assert json.loads(R.review_path(gt, run.name).read_text())["gaps"] == [
        {"first": 251, "last": 374, "status": "checked"}]
    assert save_gap(run.name, 1, {"checked": True, "tail_frame": 300})["gaps"] == {1: "tail"}
    with pytest.raises(HTTPException):
        save_gap(run.name, 1, {"checked": True, "tail_frame": 9999})    # not in that gap
    assert save_gap(run.name, 1, {"checked": False})["gaps"] == {}
    with pytest.raises(HTTPException):
        save_gap(run.name, 7, {"checked": True})

    state = save_point(run.name, 1, {"status": None})
    assert sorted(state["verdicts"]) == [2]
    with pytest.raises(HTTPException) as bad:
        save_point(run.name, 2, {"status": "ok", "winner": "Z"})
    assert bad.value.status_code == 400
    with pytest.raises(HTTPException):
        save_point("../etc", 1, {"status": "ok"})
    with pytest.raises(HTTPException):
        save_point("20990102_1000_no_copy", 1, {"status": "ok"})


def test_a_file_that_is_not_a_review_is_never_overwritten(tmp_path):
    run = _run_dir(tmp_path)
    gt = tmp_path / "ground_truth"
    gt.mkdir()
    R.review_path(gt, run.name).write_text('{"format": "something-else"}')
    router = R.create_router(tmp_path / "output", gt)
    with pytest.raises(ValueError):
        _endpoint(router, "save_point")(run.name, 1, {"status": "ok"})
    assert json.loads(R.review_path(gt, run.name).read_text()) == {"format": "something-else"}


# --------------------------------------------------------------------------- #
# the service order after the owner's corrections
# --------------------------------------------------------------------------- #

def _served(rows):
    """Points of (serving team, server as the run names it, server seen, winner)."""
    points = []
    for i, (team, player, seen, winner) in enumerate(rows):
        start = 100 + 100 * i
        flags = [f"server_from_rotation:{seen}->{player}"] if seen != player else []
        points.append({"point": i + 1, "start_frame": start, "end_frame": start + 50,
                       "near_team": "A", "serve": {"team": team, "player": player},
                       "end": {"kind": "ground"}, "winner": winner, "winner_source": "next_serve",
                       "score_after": {"A": 0, "B": 0}, "flags": flags,
                       "touches": [_touch(start, "serve", player)]})
    return R.match_view({"fps": 25.0, "checks": {}, "points": points}, None)["points"]


def _missed_point_match():
    # Point 5 was B's (the run says A's) and a point B served is missing after
    # it: A serves 6 and 7 in a NEW turn, by the teammate the camera saw.
    return _served([("A", "P1A", "P1A", "B"), ("B", "P1B", "P1B", "A"),
                    ("A", "P2A", "P2A", "B"), ("B", "P2B", "P2B", "A"),
                    ("A", "P1A", "P1A", "A"), ("A", "P1A", "P2A", "A"),
                    ("A", "P1A", "P2A", "B"), ("B", "P1B", "P1B", "A")])


def test_a_point_the_owner_adds_moves_the_servers_after_it():
    points = _missed_point_match()
    assert R.rotation_servers(points, {}, []) == {}            # nothing corrected: nothing moves
    review = R.empty_review("k")
    R.put_verdict(review, R.clean_verdict({"status": "corrected", "winner": "B"}, points[4]), 500)
    by_point, _ = R.attach(review, points)
    missing = [{"after_point": 5, "winner": "A"}]           # served by B, the winner of point 5
    assert R.rotation_servers(points, by_point, missing) == {6: "P2A", 7: "P2A"}


def test_a_server_the_owner_named_is_never_suggested_over():
    points = _missed_point_match()
    review = R.empty_review("k")
    R.put_verdict(review, R.clean_verdict({"status": "corrected", "winner": "B"}, points[4]), 500)
    R.put_verdict(review, R.clean_verdict(
        {"status": "corrected", "touches": {"600": {"player": "P1A"}}}, points[5]), 600)
    by_point, _ = R.attach(review, points)
    out = R.rotation_servers(points, by_point, [{"after_point": 5, "winner": "A"}])
    assert 6 not in out
