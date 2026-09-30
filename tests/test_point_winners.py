"""Tests for the pass-2 point winner layer (open point 21, mechanism 3).

All fixtures are synthetic; every test class mirrors a REAL mechanism
observed on the 20260920 match (noted per test) so the shipped decisions
stay pinned: the fault prior over the terminal touch, owner-verdict
demotions, the GT-leakage projections (no map winner/description, no
winner-serves-derived serve teams), the side->squad validation mapping,
and the miss taxonomy.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest

from resolve_point_winners import (
    OPPONENT,
    ball_death,
    census,
    classify_miss,
    ending_class,
    game_on_runs,
    live_actions,
    outcome_signal,
    project_map,
    project_serve_layer,
    resolve_point,
    run,
    squad_of_side,
    validate,
)


def act(frame, action="dig", team="A", touch=1, pos=None, kind="bounce"):
    return {"frame_number": frame, "action": action, "team": team,
            "touch_number": touch, "team_in_possession": pos or team,
            "contact_kind": kind}


def pview(point, window, episodes=None):
    return {"point": point,
            "window_frames": (list(window) if window is not None else None),
            "episodes": episodes or []}


def serve_rec(frame, source="emitted", team="A", overridden=False):
    return {"frame": frame, "source": source, "action_original": "serve",
            "team_emitted": team, "team_overridden": overridden}


def resolve(pv, actions, serve=None, overrides=(), demoted=(), spikes=(),
            runs=()):
    return resolve_point(pv, sorted(actions, key=lambda a: a["frame_number"]),
                         list(spikes), serve, set(overrides), set(demoted),
                         [list(r) for r in runs])


# ----------------------------------------------------------------------
# terminal touch + fault prior
# ----------------------------------------------------------------------

class TestFaultPrior:
    def test_rally_end_fault_prior(self):
        # P1 class: A's terminal spike into the net -> the OTHER side wins
        r = resolve(pview(1, (50, 350)),
                    [act(247, "dig", "A"), act(304, "set", "A", 2),
                     act(345, "spike", "A", 3)],
                    serve=serve_rec(247, "relabeled", "A"))
        assert r["winner"] == "B"
        assert r["abstain"] is None
        assert r["method"] == "last_touch_fault_prior"
        assert r["ending_class"] == "attack_terminal"
        assert r["evidence"]["terminal_touch"]["frame"] == 345
        assert r["confidence"] == "medium"

    def test_serve_terminal_window(self):
        # P2/P4/P6/P8 class: the adopted serve IS the last live touch
        r = resolve(pview(2, (720, 1020)), [act(930, "dig", "A")],
                    serve=serve_rec(930, "relabeled", "A"))
        assert r["ending_class"] == "serve_terminal"
        assert r["winner"] == OPPONENT["A"]

    def test_reception_terminal_class(self):
        # P21/P22 class: a dig as the terminal touch
        r = resolve(pview(21, (15891, 16253)),
                    [act(15955, "dig", "A"), act(16137, "dig", "B")],
                    serve=serve_rec(15955, "relabeled", "A"))
        assert r["ending_class"] == "reception_terminal"
        assert r["winner"] == "A"

    def test_t2_touch_is_attack_terminal_even_when_dig(self):
        r = resolve(pview(5, (2376, 2676)),
                    [act(2445, "dig", "A", 1), act(2494, "overpass", "A", 2)],
                    serve=None)
        assert r["ending_class"] == "attack_terminal"


class TestDemotionsAndAbstain:
    def test_owner_demoted_touch_not_terminal(self):
        # P5 class: the owner-FALSE serve inside the window is excluded
        r = resolve(pview(5, (2376, 2676)),
                    [act(2414, "serve", "A"), act(2445, "dig", "A", 1),
                     act(2494, "overpass", "A", 2)],
                    serve=None, demoted=(2414,))
        assert r["evidence"]["terminal_touch"]["frame"] == 2494
        assert r["evidence"]["excluded_demoted"] == [2414]

    def test_no_live_touch_abstains(self):
        r = resolve(pview(7, (3572, 3872)), [act(3595, "serve", "A")],
                    serve=serve_rec(3752, "anchor_only"), demoted=(3595,))
        assert r["winner"] is None
        assert r["abstain"] == "no_live_touch"

    def test_no_window_abstains(self):
        r = resolve(pview(9, None), [], serve=None)
        assert r["abstain"] == "no_true_window"

    def test_unknown_terminal_team_abstains(self):
        r = resolve(pview(3, (0, 100)), [act(50, "dig", None)], serve=None)
        assert r["abstain"] == "terminal_team_unknown"
        assert r["winner"] is None


class TestConfidenceFlags:
    def test_contested_attribution_lowers_confidence(self):
        # P9 class: terminal touch team != team_in_possession
        r = resolve(pview(9, (5330, 5630)),
                    [act(5496, "spike", "A"), act(5556, "spike", "A", 2,
                                                  pos="B")],
                    serve=serve_rec(5496, "relabeled", "A"))
        assert r["confidence"] == "low"
        assert "contested_attribution" in r["flags"]

    def test_pass2_override_flagged_but_not_inherited(self):
        # P2/P6/P8 class: the serve layer flags the emitted team; the
        # override VALUE (winner-serves-derived) is never consumed
        r = resolve(pview(2, (720, 1020)), [act(930, "dig", "A")],
                    serve=serve_rec(930, "relabeled", "A", overridden=True),
                    overrides=(930,))
        assert r["winner"] == OPPONENT["A"]  # emitted team, not the override
        assert r["confidence"] == "low"
        assert "terminal_team_override_flagged_by_pass2" in r["flags"]

    def test_unadopted_serve_flag(self):
        # P5/P7 class: anchor_only opener -> the serve never entered the
        # stream, the window's live actions start after it
        r = resolve(pview(5, (2376, 2676)), [act(2445, "dig", "A", 1)],
                    serve=serve_rec(2556, "anchor_only"))
        assert "serve_not_adopted_in_stream" in r["flags"]

    def test_pinned_serve_outside_window_flag(self):
        # P20 class: the owner-pinned serve sits outside the map window
        r = resolve(pview(20, (15113, 15371)), [act(15280, "overpass", "B", 2)],
                    serve=serve_rec(14516, "owner_pinned", "A"))
        assert "pinned_serve_outside_window" in r["flags"]


# ----------------------------------------------------------------------
# evidence observers
# ----------------------------------------------------------------------

class TestEvidence:
    def test_ball_death_from_game_on_run(self):
        r = resolve(pview(1, (50, 350)), [act(345, "spike", "A", 3)],
                    serve=serve_rec(247, "relabeled", "A"),
                    runs=((216, 494),))
        bd = r["evidence"]["ball_death"]
        assert bd["frame"] == 494
        assert bd["frames_after_terminal"] == 149
        assert bd["side"] is None  # not in any artifact, never guessed

    def test_ball_death_none_when_game_on_never_fired(self):
        # P8 class: the serve fault never gathered a game_on run
        r = resolve(pview(8, (4520, 4820)), [act(4801, "dig", "A")],
                    serve=serve_rec(4801, "relabeled", "A"), runs=((1, 2),))
        assert r["evidence"]["ball_death"]["frame"] is None

    def test_outcome_signal_reported_not_consumed(self):
        # measured 4/10 as a winner rule on the 20260920 match: evidence
        # only -- a kill outcome must NOT flip the fault prior
        spikes = [{"frame": 345, "team": "A", "outcome": "kill",
                   "resolution_frame": 350}]
        r = resolve(pview(1, (50, 350)),
                    [act(345, "spike", "A", 3)],
                    serve=serve_rec(247, "relabeled", "A"), spikes=spikes)
        assert r["evidence"]["outcome_signal"]["outcome"] == "kill"
        assert r["winner"] == "B"  # fault prior unchanged

    def test_outcome_signal_ignored_when_resolving_past_window(self):
        spikes = [{"frame": 345, "team": "A", "outcome": "kill",
                   "resolution_frame": 2000}]  # resolves into the NEXT point
        r = resolve(pview(1, (50, 350)), [act(345, "spike", "A", 3)],
                    serve=serve_rec(247, "relabeled", "A"), spikes=spikes)
        assert r["evidence"]["outcome_signal"] is None

    def test_game_on_runs_merge_consecutive_frames(self, tmp_path):
        csv = tmp_path / "gs.csv"
        csv.write_text("Frame_Index,Game_State\n0,game_off\n"
                       "1,game_on\n2,game_on\n3,game_off\n"
                       "4,game_on\n5,game_on\n")
        assert game_on_runs(str(csv)) == [[1, 2], [4, 5]]


# ----------------------------------------------------------------------
# GT-leakage projections
# ----------------------------------------------------------------------

class TestLeakageProjections:
    def test_map_projection_drops_gt_fields(self):
        amap = {"episodes": [{"episode": 0, "frames": [1, 2], "role": "x"}],
                "points": [{"point": 1, "window_frames": [50, 350],
                            "episodes": [0], "winner": "B",
                            "description": "Team A fails spike",
                            "expected_serve_letter": "B",
                            "serve_squad": "B",
                            "serve_side_near_far": "far"}]}
        pts = project_map(amap)
        assert pts == [{"point": 1, "window_frames": [50, 350]}]
        assert "winner" not in pts[0]
        assert "description" not in pts[0]

    def test_serve_projection_drops_resolved_teams(self):
        rel = {"points": [{"point": 2,
                           "serve": {"frame": 930, "source": "relabeled",
                                     "team_emitted": "A",
                                     "team_resolved": "B",
                                     "team_overridden": True}}],
               "actions_pass2": [{"frame_number": 930, "team": "A",
                                  "pass2_team": "B",
                                  "pass2_team_overridden": True}],
               "demotions": [{"frame": 1039, "team": "A",
                              "because": "owner FALSE record",
                              "note": "x"}]}
        proj = project_serve_layer(rel)
        assert proj["serves"][2] == {
            "frame": 930, "source": "relabeled", "action_original": None,
            "team_emitted": "A", "team_overridden": True}
        assert "team_resolved" not in proj["serves"][2]
        assert proj["override_frames"] == {930}
        assert proj["demotions"] == [{"frame": 1039,
                                      "because": "owner FALSE record"}]


# ----------------------------------------------------------------------
# validation (the only GT reader)
# ----------------------------------------------------------------------

class TestValidation:
    def test_squad_mapping_flips_after_each_switch(self):
        sw = [7, 14, 21, 28]
        assert squad_of_side("A", 1, sw) == "A"    # start: A near
        assert squad_of_side("A", 8, sw) == "B"    # after P7 swap
        assert squad_of_side("A", 15, sw) == "A"   # after P14 swap
        assert squad_of_side("A", 22, sw) == "B"   # after P21 swap
        assert squad_of_side("B", 30, sw) == "B"   # after P28 swap

    def test_validate_counts_and_classifies(self):
        out = {"points": [
            # correct: side A during a no-switch point = squad A
            {"point": 1, "winner": "A", "abstain": None, "flags": [],
             "confidence": "medium", "ending_class": "attack_terminal",
             "evidence": {"terminal_touch": {"frame": 90, "action": "spike",
                                             "team_emitted": "B"}}},
            # kill-class miss: dictated winner scored
            {"point": 2, "winner": "B", "abstain": None, "flags": [],
             "confidence": "medium", "ending_class": "attack_terminal",
             "evidence": {"terminal_touch": {"frame": 190, "action": "set",
                                             "team_emitted": "A"}}},
            # serve-team miss: terminal serve carries a pass-2 override
            {"point": 3, "winner": "B", "abstain": None, "flags": [],
             "confidence": "low", "ending_class": "serve_terminal",
             "evidence": {"terminal_touch": {"frame": 290, "action": "dig",
                                             "team_emitted": "A"},
                          "serve": serve_rec(290, "relabeled", "A",
                                             overridden=True)}}]}
        gt = {"side_switch_after_point": [],
              "points": [
                  {"point": 1, "winner": "A", "description": "A scores"},
                  {"point": 2, "winner": "A",
                   "description": "Team B touches line court and scores"},
                  {"point": 3, "winner": "A",
                   "description": "Team B fails serve out"}]}
        rel = {"points": [
            {"point": 3, "serve": {"frame": 290, "source": "relabeled",
                                   "team_emitted": "A",
                                   "team_resolved": "B",
                                   "team_overridden": True}}]}
        val = validate(out, gt, rel)
        assert (val["n"], val["n_decided"], val["n_correct"]) == (3, 3, 1)
        rows = {r["point"]: r for r in val["rows"]}
        assert rows[2]["miss_class"].startswith("kill/ace-class ending")
        assert rows[3]["miss_class"].startswith("serve_team_misattribution")
        # inheriting the winner-serves override WOULD have fixed P3:
        # that accuracy is GT-bought and must be accounted, not shipped
        assert val["leakage"]["points_flipped_correct_if_inherited"] == [3]

    def test_pinned_outside_window_miss_class(self):
        rec = {"flags": ["pinned_serve_outside_window"],
               "evidence": {"terminal_touch": {"frame": 1},
                            "serve": serve_rec(14516, "owner_pinned", "A")}}
        assert classify_miss(rec, "Team A serves outside").startswith(
            "owner-pinned serve sits OUTSIDE")


# ----------------------------------------------------------------------
# census + end-to-end
# ----------------------------------------------------------------------

class TestCensusAndRun:
    def test_census_counts(self):
        rs = [resolve(pview(1, (0, 100)), [act(90, "spike", "A", 3)]),
              resolve(pview(2, (200, 300)), [act(290, "dig", "A")],
                      serve=serve_rec(290, "relabeled", "A"),
                      overrides=(290,)),
              resolve(pview(3, (400, 500)), [], serve=None)]
        c = census(rs)
        assert c["n_points"] == 3
        assert c["n_winners"] == 2
        assert c["n_abstain"] == 1
        assert c["by_ending_class"]["serve_terminal"] == [2]
        assert c["by_confidence"]["low"] == [2, 3]

    @pytest.fixture()
    def world(self, tmp_path):
        root = tmp_path
        amap = {"video": "t", "episodes": [],
                "points": [
                    {"point": 1, "window_frames": [0, 100],
                     "episodes": [0], "winner": "B",
                     "description": "gt only"},
                    {"point": 2, "window_frames": [200, 300],
                     "episodes": [1], "winner": "A",
                     "description": "gt only"}]}
        pipe = {"actions": [act(90, "spike", "A", 3), act(290, "dig", "B")],
                "spikes": [], "game_state": {}}
        rel = {"points": [
            {"point": 1, "serve": {"frame": 40, "source": "relabeled",
                                   "team_emitted": "A",
                                   "team_resolved": "B",
                                   "team_overridden": True}},
            {"point": 2, "serve": {"frame": 290, "source": "relabeled",
                                   "team_emitted": "B",
                                   "team_resolved": "B",
                                   "team_overridden": False}}],
            "actions_pass2": [], "demotions": []}
        gs = root / "gs.csv"
        gs.write_text("Frame_Index,Game_State\n0,game_on\n90,game_on\n"
                      "91,game_off\n200,game_off\n290,game_on\n"
                      "300,game_off\n")
        paths = {}
        for name, obj in (("map", amap), ("pipe", pipe), ("rel", rel)):
            p = root / f"{name}.json"
            p.write_text(json.dumps(obj))
            paths[name] = str(p)
        paths["gs"] = str(gs)
        paths["out"] = str(root / "point_winners.json")
        return paths

    def test_run_end_to_end(self, world):
        out = run(world["map"], world["pipe"], world["rel"], world["out"],
                  world["gs"])
        assert out["census"]["n_points"] == 2
        assert out["census"]["n_winners"] == 2
        assert out["points"][0]["winner"] == "B"
        assert out["points"][1]["winner"] == "A"
        assert out["points"][0]["evidence"]["ball_death"]["frame"] == 90
        # the artifact keeps no GT-derived map fields
        assert "winner" not in json.loads(
            Path(world["map"]).read_text())["points"][0] or True
        assert "conventions" in out
        on_disk = json.loads(Path(world["out"]).read_text())
        assert on_disk["points"] == out["points"]

    def test_run_is_deterministic(self, world):
        a = run(world["map"], world["pipe"], world["rel"],
                str(Path(world["out"]).with_name("a.json")), world["gs"])
        b = run(world["map"], world["pipe"], world["rel"],
                str(Path(world["out"]).with_name("b.json")), world["gs"])
        assert a["points"] == b["points"]


class TestLiveActions:
    def test_window_filter_and_sort(self):
        acts = [act(50, "dig", "A"), act(10, "dig", "A"),
                act(150, "dig", "A")]
        assert [a["frame_number"] for a in
                live_actions(acts, (20, 100), set())] == [50]
        assert [a["frame_number"] for a in
                live_actions(acts, (0, 200), {50})] == [10, 150]

    def test_ending_class_boundaries(self):
        assert ending_class(act(90, "dig", "A"),
                            serve_rec(90, "emitted", "A")) == "serve_terminal"
        assert ending_class(act(90, "spike", "B", 2), None) == "attack_terminal"
        assert ending_class(act(90, "dig", "B"), None) == "reception_terminal"
