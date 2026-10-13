"""The owner's review applied at publish (src/publish/reviewed.py).

A drawn rally with a known answer, then the same synthetic match
``tests/test_publish.py`` publishes: the review must change only what the
owner changed, and the web's credits must stay the reviewed post-run stats.
"""

import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import postrun_sim as sim  # noqa: E402
from src.postrun.reconstruct import format_report, reconstruct  # noqa: E402
from src.publish.bundle import build_bundle  # noqa: E402
from src.publish.fantasy import score_actions  # noqa: E402
from src.publish.reviewed import (apply_review, derive_outcomes, describe,  # noqa: E402
                                  reviewed_point)
from src.web import review as R  # noqa: E402

KEY = "20260920_1830_test_court"


def _touch(frame, action, player, number, team=None, **extra):
    team = team or (player[2] if player else None)
    return {"frame": frame, "action": action, "side": "near" if team == "A" else "far",
            "team": team, "player": player, "player_source": "reach", "touch_number": number,
            "observed": True, "evidence": "vertex", "ends_possession": False, "outcome": None,
            "height_m": 1.0, "contact_height_m": 1.0, "contact_ratio": 0.7, "court_x_m": 4.0,
            "court_y_m": 12.0, "court_err_m": [0.4, 0.7], "reach_body_heights": 0.0,
            "perception_action": action, "spike_type": None, "launch": None, **extra}


def _point(n, start, touches, winner, serve_team="B"):
    return {"point": n, "start_frame": start, "end_frame": touches[-1]["frame"] + 40,
            "start_time_s": start / 25.0, "end_time_s": (touches[-1]["frame"] + 40) / 25.0,
            "rally": {"touches": len(touches), "net_crossings": 1, "duration_s": 5.0},
            "near_team": "A",
            "serve": {"frame": start, "side": "far", "team": serve_team,
                      "player": touches[0]["player"], "player_source": None, "outcome": None,
                      "observed": True, "inferred": False, "into_net": False,
                      "confirmed_by": None},
            "end": {"kind": "ground", "frame": touches[-1]["frame"] + 30, "side": "far",
                    "in_court": True, "court_xy_m": [4.0, 3.0], "court_xy_err_m": [0.4, 0.9]},
            "winner": winner, "winner_source": "next_serve",
            "ball_death_read": {"winner": winner, "reason": "ground"},
            "score_after": {"A": 0, "B": 0}, "flags": [], "touches": touches}


def _recon():
    """Two points. P1: B serves, A digs, sets, spikes -- read as the attacker's
    spike and an overpass by B, really B's block and A's dig, then A's kill.
    P2: A serves, B's reception fails (an ace)."""
    p1 = _point(1, 100, [
        _touch(100, "serve", "P2B", 0), _touch(140, "dig", "P1A", 1),
        _touch(180, "set", "P2A", 2),
        _touch(220, "spike", "P1A", 3, spike_type="hard", launch={"frame": 222}),
        _touch(232, "overpass", "P1B", 1), _touch(260, "overpass", "P2A", 1, outcome="kill"),
    ], "A")
    p2 = _point(2, 600, [_touch(600, "serve", "P1A", 0, outcome="ace"),
                         _touch(640, "dig", "P1B", 1)], "A", serve_team="A")
    p1["score_after"], p2["score_after"] = {"A": 1, "B": 0}, {"A": 2, "B": 0}
    return {"schema_version": 7, "fps": 25.0, "n_frames": 1000, "clock": "video",
            "checks": {"points": 2, "final_score": {"A": 2, "B": 0}, "set_complete": False,
                       "undecided_points": [], "side_switch_after_point": [],
                       "points_between_switches": [], "switch_blocks_ok": True,
                       "flagged_points": {}, "longest_rally": None},
            "identity": {"applied": False}, "points": [p1, p2],
            "player_stats": {"_uncredited_observed_touches": {"count": 0}}}


def _review(recon, verdicts, missing=()):
    """A review file as the page writes it: raw verdicts by point number."""
    view = R.match_view(recon, None)["points"]
    review = R.empty_review(KEY)
    for number, raw in verdicts.items():
        point = view[number - 1]
        R.put_verdict(review, R.clean_verdict(raw, point), point["start_frame"])
    review.update(R.clean_match_fields({"missing_points": list(missing)}, view))
    return review


BLOCK = {"status": "corrected",
         "touches": {"220": {"action": "block", "player": "P1B"},
                     "232": {"action": "dig", "player": "P1A"},
                     "260": {"action": "spike"}}}


# --------------------------------------------------------------------------- #
# outcomes
# --------------------------------------------------------------------------- #

def _rally(*rows):
    return [{"action": a, "team": t, "touch_number": n, "outcome": "stale"} for a, t, n in rows]


def _outcomes(touches, winner):
    derive_outcomes(touches, winner)
    return [t["outcome"] for t in touches]


def test_the_last_ball_of_the_winners_is_a_kill():
    rally = _rally(("serve", "B", 0), ("dig", "A", 1), ("set", "A", 2), ("spike", "A", 3))
    assert _outcomes(rally, "A") == [None, None, None, "kill"]
    assert _outcomes(rally, "B") == [None, None, None, "error"]


def test_a_failed_first_touch_credits_the_hit_before_it():
    assert _outcomes(_rally(("serve", "A", 0), ("dig", "B", 1)), "A") == ["ace", None]
    rally = _rally(("serve", "B", 0), ("dig", "A", 1), ("spike", "A", 2), ("dig", "B", 1))
    assert _outcomes(rally, "A") == [None, None, "kill", None]


def test_a_serve_nobody_touches():
    assert _outcomes(_rally(("serve", "A", 0)), "A") == ["ace"]
    assert _outcomes(_rally(("serve", "A", 0)), "B") == ["error"]


def test_only_a_block_that_wins_the_point_is_a_kill():
    won = _rally(("serve", "B", 0), ("dig", "A", 1), ("spike", "A", 2), ("block", "B", 1))
    assert _outcomes(won, "B") == [None, None, None, "kill"]
    # the blocker's touch fails: the attack it met is the kill, the block is nothing
    assert _outcomes(won, "A") == [None, None, "kill", None]
    soft = _rally(("serve", "B", 0), ("spike", "A", 1), ("block", "B", 1), ("dig", "A", 1),
                  ("spike", "A", 2))
    assert _outcomes(soft, "A") == [None, None, None, None, "kill"]


def test_a_set_that_loses_the_point_is_a_handling_error():
    rally = _rally(("serve", "B", 0), ("dig", "A", 1), ("set", "A", 2))
    assert _outcomes(rally, "B") == [None, None, "error"]
    assert _outcomes(rally, None) == [None, None, None]


# --------------------------------------------------------------------------- #
# one point
# --------------------------------------------------------------------------- #

def test_all_right_leaves_the_point_as_the_run_has_it():
    recon = _recon()
    verdict = R.clean_verdict({"status": "ok"}, R.match_view(recon, None)["points"][0])
    new, changes = reviewed_point(recon["points"][0], verdict["truth"], 25.0)
    assert new == recon["points"][0] and not any(changes.values())


def test_a_block_read_as_a_spike_is_put_right():
    recon = _recon()
    verdict = R.clean_verdict(BLOCK, R.match_view(recon, None)["points"][0])
    new, changes = reviewed_point(recon["points"][0], verdict["truth"], 25.0)
    got = [(t["frame"], t["action"], t["player"], t["team"], t["side"], t["touch_number"],
            t["outcome"]) for t in new["touches"]]
    assert got == [
        (100, "serve", "P2B", "B", "far", 0, None),
        (140, "dig", "P1A", "A", "near", 1, None),
        (180, "set", "P2A", "A", "near", 2, None),
        (220, "block", "P1B", "B", "far", 1, None),      # a soft block: no outcome
        (232, "dig", "P1A", "A", "near", 1, None),
        (260, "spike", "P2A", "A", "near", 2, "kill"),
    ]
    assert changes["touches_changed"] == 3 and not changes["winner_changed"]
    block = new["touches"][3]
    assert block["spike_type"] is None and block["launch"] is None     # typed as a spike
    assert block["player_source"] == "owner" and block["court_x_m"] == 4.0
    assert [t["ends_possession"] for t in new["touches"]] == [True, False, True, True, False, True]
    assert new["touches"][1] == recon["points"][0]["touches"][1]       # left alone: untouched


def test_an_added_touch_is_seen_and_has_no_position():
    recon = _recon()
    raw = {"status": "corrected", "touches": {"232": {"remove": True}, "260": {"remove": True}},
           "added": [{"frame": 300, "action": "dig", "player": "P2B"}]}
    verdict = R.clean_verdict(raw, R.match_view(recon, None)["points"][0])
    new, changes = reviewed_point(recon["points"][0], verdict["truth"], 25.0)
    added = new["touches"][-1]
    assert (added["frame"], added["action"], added["player"], added["team"]) == (300, "dig", "P2B", "B")
    assert added["observed"] and added["evidence"] == "owner" and added["court_x_m"] is None
    assert changes == {"touches_changed": 0, "touches_added": 1, "touches_removed": 2,
                       "winner_changed": 0, "sides_changed": 0}
    # A's spike is now followed by B's failed first touch: A's kill
    assert new["touches"][3]["outcome"] == "kill" and added["outcome"] is None


def test_another_winner_derives_the_outcomes_again():
    recon = _recon()
    verdict = R.clean_verdict({"status": "corrected", "winner": "B"},
                              R.match_view(recon, None)["points"][1])
    new, changes = reviewed_point(recon["points"][1], verdict["truth"], 25.0)
    assert new["winner"] == "B" and new["winner_source"] == "owner" and changes["winner_changed"]
    # the reception stood, so the serve was no ace; nothing says how B won it
    assert [t["outcome"] for t in new["touches"]] == [None, None]
    assert new["serve"]["outcome"] is None


def test_squads_on_the_wrong_halves_move_teams_and_keep_the_halves():
    recon = _recon()
    verdict = R.clean_verdict({"status": "corrected", "labels": {"sides_swapped": True}},
                              R.match_view(recon, None)["points"][1])
    new, changes = reviewed_point(recon["points"][1], verdict["truth"], 25.0)
    assert changes["sides_changed"] and new["near_team"] == "B"
    assert [(t["player"], t["team"], t["side"]) for t in new["touches"]] == [
        ("P1B", "B", "near"), ("P1A", "A", "far")]
    assert new["serve"]["team"] == "B" and new["serve"]["player"] == "P1B"


def test_a_truth_frame_a_little_off_still_takes_the_runs_measurements():
    recon = _recon()
    point = recon["points"][0]
    truth = {"is_point": True, "winner": "A", "near_team": "A", "serve_team": "B",
             "touches": [{"frame": t["frame"] + (3 if t["frame"] == 180 else 0),
                          "action": t["action"], "player": t["player"]} for t in point["touches"]]}
    new, changes = reviewed_point(point, truth, 25.0)       # a rules change moved the set by 3 f
    assert not any(changes.values()) and new == point


# --------------------------------------------------------------------------- #
# the match
# --------------------------------------------------------------------------- #

def test_no_review_and_an_all_right_review_change_nothing():
    recon = _recon()
    assert apply_review(recon, None) == (recon, {"applied": False, "points": 2})
    out, report = apply_review(recon, _review(recon, {1: {"status": "ok"}, 2: {"status": "ok"}}))
    assert out is recon
    assert report["applied"] and report["reviewed"] == 2 and report["corrected"] == 0
    assert "published as the run reads it" in describe({"applied": False})


def test_a_corrected_match_is_renumbered_rescored_and_restated():
    recon = _recon()
    review = _review(recon, {1: BLOCK, 2: {"status": "corrected", "not_a_point": True}},
                     missing=[{"after_point": 0, "winner": "B"},
                              {"after_point": 1, "winner": "B", "at_frame": 450}])
    out, report = apply_review(recon, review)
    assert out is not recon and recon["points"][0]["touches"][3]["action"] == "spike"
    assert [(p["point"], p["start_frame"], p["winner"], p["flags"]) for p in out["points"]] == [
        (1, 0, "B", ["owner_added"]), (2, 100, "A", []), (3, 450, "B", ["owner_added"])]
    assert [p["score_after"] for p in out["points"]] == [
        {"A": 0, "B": 1}, {"A": 1, "B": 1}, {"A": 1, "B": 2}]
    assert out["points"][2]["serve"]["team"] == "A"          # the winner of the point before
    assert out["checks"]["points"] == 3 and out["checks"]["final_score"] == {"A": 1, "B": 2}
    assert out["checks"]["flagged_points"] == {1: ["owner_added"], 3: ["owner_added"]}
    assert (report["corrected"], report["dropped"], report["added"]) == (1, 1, 2)
    assert "2 missing points added" in describe(report) and "A 2 – B 0 -> A 1 – B 2" in describe(report)
    stats = out["player_stats"]
    assert stats["P1B"]["blocks"] == 1 and "block_kills" not in stats["P1B"]
    assert stats["P2A"]["kills"] == 1 and stats["P1A"]["digs"] == 2
    format_report(out)                                       # the owner's play-by-play still prints


def test_a_kill_block_scores_and_a_soft_block_does_not():
    recon = _recon()
    raw = {"status": "corrected", "winner": "B",
           "touches": {"220": {"action": "block", "player": "P1B"},
                       "232": {"remove": True}, "260": {"remove": True}}}
    out, _ = apply_review(recon, _review(recon, {1: raw}))
    assert out["points"][0]["touches"][-1]["outcome"] == "kill"
    assert out["player_stats"]["P1B"]["block_kills"] == 1
    assert out["player_stats"]["P1B"]["fantasy"] == 2.0      # the block + her dig in point 2
    soft, _ = apply_review(recon, _review(recon, {1: BLOCK}))
    assert soft["player_stats"]["P1B"]["fantasy"] == 1.0     # the dig alone


def test_a_verdict_that_fits_no_rally_is_reported_not_applied():
    recon = _recon()
    review = _review(recon, {1: BLOCK})
    review["points"][0].update(start_frame=5000, end_frame=5100)
    out, report = apply_review(recon, review)
    assert out is recon and report["orphans"] == 1 and report["reviewed"] == 0
    assert "fit no rally" in describe(report)


# --------------------------------------------------------------------------- #
# through the bundle: the web's numbers are the reviewed post-run numbers
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def sim_recon():
    b = sim.StreamBuilder(12.0 * 4 + 5.0)
    for i, side in enumerate(["near", "far", "far", "near"]):
        b.rally(sim.standard_rally(2.0 + 12.0 * i, side, sim.NEAR_A, exchanges=2))
    return json.loads(json.dumps(reconstruct(b.build(), b.g, points_to_win=3)))


def _run_dir(tmp_path, recon):
    run = tmp_path / f"{KEY}_up1080"
    run.mkdir()
    (run / "match_reconstruction.json").write_text(json.dumps(recon))
    (run / "pipeline_output.json").write_text(json.dumps({
        "pipeline_version": "abc1234",
        "video": {"key": f"{KEY}_up1080", "path": f"resources/{KEY}_up1080.mp4", "fps": 30.0,
                  "width": 1920, "height": 1080, "total_frames": recon["n_frames"]},
        "spikes": []}))
    return run


def _corrected(sim_recon):
    """The owner turns the first attack of the match into the rival's block
    and names the touch after it."""
    view = R.match_view(sim_recon, None)["points"]
    point = next(p for p in view if sum(t["action"] == "spike" for t in p["touches"]) >= 2)
    spike = next(t for t in point["touches"] if t["action"] == "spike")
    rival = next(p for p in R.PLAYERS if p[2] != spike["team"])
    raw = {"status": "corrected", "touches": {str(spike["frame"]): {"action": "block",
                                                                 "player": rival}}}
    return _review(sim_recon, {point["point"]: raw}), point["point"], spike["frame"], rival


def test_an_all_right_review_publishes_the_same_bundle(tmp_path, sim_recon):
    run = _run_dir(tmp_path, sim_recon)
    review = _review(sim_recon, {p["point"]: {"status": "ok"} for p in sim_recon["points"]})
    reviewed, _ = apply_review(sim_recon, review)
    assert build_bundle(run, recon=reviewed)["content_sha256"] == build_bundle(run)["content_sha256"]


def test_credits_and_fantasy_equal_the_reviewed_stats(tmp_path, sim_recon):
    review, number, frame, rival = _corrected(sim_recon)
    reviewed, report = apply_review(copy.deepcopy(sim_recon), review)
    assert report["corrected"] == 1
    run = _run_dir(tmp_path, sim_recon)
    bundle = build_bundle(run, recon=reviewed)
    assert bundle["content_sha256"] != build_bundle(run)["content_sha256"]
    block = next(a for a in bundle["actions"] if a["action"] == "block")
    assert (block["point_no"], block["frame"], block["slot"]) == (number, frame, rival)
    assert block["spike_type"] is None and "clip" not in block["extra"]
    fantasy = score_actions(bundle["actions"])
    for slot, row in reviewed["player_stats"].items():
        if slot.startswith("_"):
            continue
        mine = [a for a in bundle["actions"] if a["slot"] == slot]
        count = lambda f: sum(1 for a in mine if f(a))  # noqa: E731
        assert count(lambda a: a["action"] == "dig") == row["digs"]
        assert count(lambda a: a["action"] == "spike") == row["spikes"]
        assert count(lambda a: a["action"] == "block") == row.get("blocks", 0)
        assert count(lambda a: a["is_assist"]) == row["assists"]
        assert count(lambda a: a["action"] in ("spike", "overpass")
                     and a["outcome"] == "kill") == row["kills"]
        assert fantasy.get(slot, {"fantasy": 0.0})["fantasy"] == row["fantasy"], slot
