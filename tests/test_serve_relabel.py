"""Tests for the pass-2 serve re-labeling layer (open point 22, mech 3).

All fixtures are synthetic; every test class mirrors a REAL mechanism
observed on the 20260920 match (noted per test) so the ratified decisions
stay pinned: gap-chasm classification, anchor precedence, owner FALSE /
OFFGAME demotions, the P32 fault-contradiction guard, the P20 owner pin,
and the structural team fix.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest

from map_episodes_to_points import parse_serve_anchors
from relabel_serves import (
    GAP_SERVE_MIN,
    _DECISIONS,
    census,
    contact_half,
    find_demotions,
    gates,
    owner_marked_frames,
    prefix_census_before,
    resolve_point,
    run,
)


def act(frame, action="dig", team="A", touch=1, cp=None, gesture=None):
    a = {"frame_number": frame, "action": action, "team": team,
         "touch_number": touch}
    if cp is not None:
        a["contact_point"] = cp
    if gesture is not None:
        a["gesture"] = gesture
    return a


def pview(point, expected, side, window, desc="", attribution="dp",
          anchor_frame=None, anchor_verdict=None):
    return {
        "point": point, "expected_serve_letter": expected,
        "serve_side_near_far": side,
        "window_frames": list(window) if window is not None else None,
        "description": desc, "attribution": attribution,
        "anchor_frame": anchor_frame, "anchor_verdict": anchor_verdict,
    }


def anchors_dict(false_frames=(), offgame=(), points=None):
    return {
        "points": points or {}, "order": sorted((points or {}).keys()),
        "false": [{"frame": f, "note": "test false"} for f in false_frames],
        "offgame": [{"start": a, "end": b, "note": "test offgame"}
                    for a, b in offgame],
    }


def gaps_of(actions):
    prev, out = None, {}
    for a in sorted(actions, key=lambda x: x["frame_number"]):
        f = a["frame_number"]
        out[f] = None if prev is None else f - prev["frame_number"]
        prev = a
    return out


def resolve(pv, actions, anchors=None, marked=None, midcourt=None):
    anchors = anchors or anchors_dict()
    marked = owner_marked_frames(anchors, []) if marked is None else marked
    return resolve_point(pv, sorted(actions, key=lambda x: x["frame_number"]),
                         gaps_of(actions), anchors, midcourt, marked)


def anchored(k, verify_frame, verdict="NOT_TRACKED"):
    return {k: {"frame": verify_frame, "side": None, "verdict": verdict,
                "note": ""}}


class TestGapChasmClassification:
    def test_serve_position_gap_relabeled(self):
        # P6 class: only action in the window, dig t1 after a 576f gap.
        r = resolve(pview(6, "B", "far", [100, 400]),
                    [act(300, "dig", "A", 1)])
        assert r["decision"] == "relabeled"
        assert r["serve"]["frame"] == 300
        assert r["serve"]["action_original"] == "dig"
        assert r["serve"]["team_emitted"] == "A"
        assert r["serve"]["team_resolved"] == "B"
        assert r["serve"]["team_overridden"] is True

    def test_emitted_serve_kept(self):
        # P3 class.
        r = resolve(pview(3, "A", "near", [100, 400]),
                    [act(300, "serve", "A", 1), act(330, "dig", "B", 1)])
        assert r["decision"] == "emitted"
        assert r["serve"]["team_overridden"] is False

    def test_reception_gap_rejected_without_anchor(self):
        # Mid-rally t1 after a 40f gap is a reception, never a serve.
        r = resolve(pview(9, "A", "near", [100, 400]),
                    [act(260, "spike", "B", 3), act(300, "dig", "A", 1),
                     act(340, "dig", "B", 1)])
        assert r["decision"] == "report_only"
        assert r["serve"] is None

    def test_gap_threshold_sits_in_measured_chasm(self):
        # Measured on the 20260920 match: non-opening t1 gaps <= 134,
        # serve-position openers >= 153.
        assert 134 < GAP_SERVE_MIN < 153

    def test_t2_opener_rejected(self):
        # P11's set@7160 class (t2 can never be the serve).
        r = resolve(pview(11, "A", "near", [100, 400]),
                    [act(300, "set", "B", 2)])
        assert r["decision"] == "report_only"

    def test_video_start_gap_is_none_and_adopted(self):
        # P1 class: first action of the video (gap None = infinite).
        r = resolve(pview(1, "B", "far", [0, 400]),
                    [act(247, "dig", "A", 1)])
        assert r["decision"] == "relabeled"
        assert r["opener_evidence"]["gap_before"] is None


class TestAnchorPrecedence:
    def test_anchor_overrides_rejected_opener(self):
        # P7 class: walk-to-line dig at gap 44 before the real anchor.
        r = resolve(pview(7, "A", "near", [100, 500], attribution="anchored",
                          anchor_frame=400, anchor_verdict="NOT_TRACKED"),
                    [act(156, "set", "A", 2), act(200, "dig", "A", 1)],
                    anchors=anchors_dict(points=anchored(7, 400)))
        assert r["decision"] == "anchor_only"
        assert r["serve"]["frame"] == 400
        assert r["serve"]["source"] == "anchor_only"

    def test_anchor_with_no_action_at_all(self):
        # P5 class: the serve flew out; nothing was ever emitted.
        r = resolve(pview(5, "A", "near", [100, 500], attribution="anchored",
                          anchor_frame=300, anchor_verdict="NOT_TRACKED"), [],
                    anchors=anchors_dict(points=anchored(5, 300)))
        assert r["decision"] == "anchor_only"
        assert r["serve"]["frame"] == 300

    def test_no_window_is_missing(self):
        r = resolve(pview(9, "A", "near", None), [])
        assert r["decision"] == "missing"


class TestDemotions:
    def test_owner_false_record_demoted(self):
        # 1039/2414/5130 class.
        anchors = anchors_dict(false_frames=(1039,))
        actions = [act(1039, "serve", "A", 1), act(1500, "serve", "B", 1)]
        d = find_demotions(actions, anchors,
                           owner_marked_frames(anchors, []))
        assert [x["frame"] for x in d] == [1039]
        assert d[0]["because"] == "owner FALSE record"

    def test_map_false_mark_covering_owner_record(self):
        # 3595A + 3856B: the FALSE@3650 record covers them via the map's
        # adjudicated false_serve_candidates note.
        anchors = anchors_dict(false_frames=(3650,))
        cands = [{"frame": 3595, "team": "A",
                  "note": "near owner FALSE mark f3650: covers 3595A"},
                 {"frame": 3856, "team": "B",
                  "note": "near owner FALSE mark f3650: covers 3856B"}]
        marked = owner_marked_frames(anchors, cands)
        assert marked == {3650, 3595, 3856}
        d = find_demotions([act(3595, "serve", "A", 1),
                            act(3856, "serve", "B", 1)],
                           anchors, marked)
        assert [x["frame"] for x in d] == [3595, 3856]

    def test_structural_false_candidate_not_demoted(self):
        # 6928 class: map structural note, NO owner verdict -> report only.
        anchors = anchors_dict()
        cands = [{"frame": 6928, "team": "A",
                  "note": "serve action inside the point span but outside "
                          "the anchored emission window"}]
        marked = owner_marked_frames(anchors, cands)
        assert 6928 not in marked
        assert find_demotions([act(6928, "serve", "A", 1)],
                              anchors, marked) == []

    def test_offgame_serve_demoted(self):
        # 14387A class: serve-typed action inside an owner OFFGAME range.
        anchors = anchors_dict(offgame=((14373, 14479),))
        d = find_demotions([act(14387, "serve", "A", 1)], anchors,
                           owner_marked_frames(anchors, []))
        assert [x["frame"] for x in d] == [14387]
        assert d[0]["because"] == "owner OFFGAME range"

    def test_non_serve_actions_never_demoted(self):
        anchors = anchors_dict(false_frames=(2445,))
        assert find_demotions([act(2445, "dig", "A", 1)], anchors,
                              owner_marked_frames(anchors, [])) == []


class TestFaultContradiction:
    def test_p32_class_report_only(self):
        # P32: fault desc + a full post-serve rally + no owner verdict.
        acts = [act(300, "dig", "A", 1), act(340, "set", "A", 2),
                act(380, "spike", "A", 3), act(420, "dig", "B", 1)]
        r = resolve(pview(32, "B", "far", [250, 500],
                          desc="Team B fails serve against the net."), acts)
        assert r["decision"] == "report_only"
        assert "serve-fault description" in r["report"][0]

    def test_owner_emission_verdict_beats_contradiction(self):
        # P12: desc is a fault ("serves out of bounds") but the owner's
        # MISCLASSIFIED verdict says the serve WAS emitted -> re-label.
        acts = [act(7780, "spike", "A", 1), act(7815, "spike", "B", 1)]
        pv = pview(12, "A", "near", [7600, 7900], attribution="anchored",
                   desc="Team B serves out of bounds",
                   anchor_frame=7780, anchor_verdict="MISCLASSIFIED")
        r = resolve(pv, acts,
                    anchors=anchors_dict(
                        points={12: {"frame": 7780, "side": "near",
                                     "verdict": "MISCLASSIFIED",
                                     "note": ""}}))
        assert r["decision"] == "relabeled"
        assert r["serve"]["frame"] == 7780
        assert r["serve"]["team_overridden"] is False

    def test_fault_desc_with_only_the_opener_relabeled(self):
        # P2 class: 'fails serve goes outside bounds', no post-serve rally.
        r = resolve(pview(2, "B", "far", [250, 500],
                          desc="Team B fails serve goes outside bounds"),
                    [act(300, "dig", "A", 1)])
        assert r["decision"] == "relabeled"


class TestOwnerPin:
    def test_pinned_serve_adopted_window_not_relabeled(self, monkeypatch):
        # P20 class: the owner's q5 verdict pins the serve OUTSIDE the
        # DP-inferred window; the window opener must not be re-labeled.
        import relabel_serves as rs
        actions = [act(4516, "serve", "A", 1), act(5168, "dig", "A", 1),
                   act(5200, "set", "A", 2)]
        pv = pview(30, "A", "near", [5113, 5371],
                   desc="Team A serves outside of the court")
        gaps = gaps_of(actions)
        r = rs.resolve_point(pv, actions, gaps, anchors_dict(), None,
                             set())
        # No pin installed for synthetic point 30 -> behaves unpinned.
        assert r["decision"] == "report_only"  # fault desc + rally

        monkeypatch.setattr(rs, "OWNER_PINNED_SERVES",
                            {30: {"frame": 4516, "team": "A",
                                  "provenance": "test"}})
        r2 = rs.resolve_point(pv, actions, gaps, anchors_dict(), None,
                              set())
        assert r2["decision"] == "owner_pinned"
        assert r2["serve"]["frame"] == 4516
        assert "not adopted" in r2["report"][0]

    def test_pinned_frame_must_be_serve_typed(self, monkeypatch):
        import relabel_serves as rs
        monkeypatch.setattr(rs, "OWNER_PINNED_SERVES",
                            {30: {"frame": 5168, "team": "A",
                                  "provenance": "test"}})
        actions = [act(5168, "dig", "A", 1)]
        pv = pview(30, "A", "near", [5100, 5200])
        r = rs.resolve_point(pv, actions, gaps_of(actions),
                             anchors_dict(), None, set())
        assert r["decision"] == "report_only"
        assert "not a serve-typed action" in r["report"][0]


class TestCensusAndGates:
    def test_far_prefix_census_scoped_to_anchored(self):
        pts = [
            pview(1, "B", "far", [0, 100], attribution="anchored"),
            pview(13, "B", "far", [0, 100], attribution="anchored"),
            pview(15, "B", "far", [0, 100], attribution="anchored"),
            pview(18, "B", "far", [0, 100], attribution="dp"),
        ]
        before = prefix_census_before(pts)
        assert before["far"] == {"n_window": 3, "n_side_match": 0}

    def test_census_counts_side_matched_resolutions(self):
        res = [
            {"point": 1, "attribution": "anchored", "decision": "relabeled",
             "expected_serve_letter": "B", "serve_side_near_far": "far",
             "serve": {"team_resolved": "B"}},
            {"point": 13, "attribution": "anchored", "decision": "emitted",
             "expected_serve_letter": "B", "serve_side_near_far": "far",
             "serve": {"team_resolved": "B"}},
            {"point": 2, "attribution": "anchored", "decision": "anchor_only",
             "expected_serve_letter": "B", "serve_side_near_far": "far",
             "serve": {"frame": 900, "source": "anchor_only"}},
        ]
        c = census(res)
        assert c["far"]["n_points"] == 3
        # anchor_only has no team_resolved -> not side-match counted.
        assert c["far"]["n_resolved_side_match"] == 2
        assert c["far"]["by_decision"]["anchor_only"] == [2]

    def test_gates_math(self):
        before = {"near": {"n_window": 9, "n_side_match": 3},
                  "far": {"n_window": 8, "n_side_match": 2}}
        after = {"near": {"n_resolved_side_match": 8, "n_points": 9},
                 "far": {"n_resolved_side_match": 8, "n_points": 8}}
        g = gates(before, after, 20, 6, 17, 2)
        assert g["far_prefix_census"]["before"] == "2/8"
        assert g["far_prefix_census"]["after"] == "8/8"
        assert g["far_prefix_census"]["pass"] is True
        assert g["serve_action_count"]["after"] == 20 - 6 + 17

    def test_gates_fail_below_target(self):
        before = {"near": {"n_window": 9, "n_side_match": 3},
                  "far": {"n_window": 8, "n_side_match": 2}}
        after = {"near": {"n_resolved_side_match": 8, "n_points": 9},
                 "far": {"n_resolved_side_match": 5, "n_points": 8}}
        assert gates(before, after, 20, 6, 17, 2)[
            "far_prefix_census"]["pass"] is False


class TestContactHalfEvidence:
    def test_near_and_far(self):
        mid = [[538, 645], [1426, 641]]
        assert contact_half([960, 700], mid) == "near"   # below the line
        assert contact_half([960, 500], mid) == "far"    # above the line

    def test_safety_without_data(self):
        assert contact_half(None, [[0, 0], [1, 1]]) is None
        assert contact_half([1, 2], None) is None


class TestFullRun:
    @pytest.fixture()
    def world(self, tmp_path):
        amap = {
            "video": "fake.mp4",
            "points": [
                pview(1, "B", "far", [100, 400], desc="rally",
                      attribution="anchored", anchor_frame=200,
                      anchor_verdict="NOT_TRACKED"),
                pview(2, "A", "near", [600, 900], desc="rally",
                      attribution="anchored", anchor_frame=700,
                      anchor_verdict="TRACKED"),
                pview(3, "B", "far", [1200, 1500],
                      desc="Team A fails serve against the net."),
            ],
            "false_serve_candidates": [
                {"frame": 640, "team": "A",
                 "note": "near owner FALSE mark f640: walking"},
            ],
            "census": {"near": {}, "far": {}},
        }
        pipe = {"actions": [
            act(300, "dig", "A", 1),          # P1 bump serve (relabeled)
            act(330, "dig", "B", 1),          # reception, untouched
            act(640, "serve", "A", 1),        # FALSE-marked (demoted)
            act(700, "serve", "A", 1),        # P2 emitted
            act(1250, "dig", "B", 1),         # P3 fault contradiction
            act(1290, "set", "B", 2),
        ]}
        anchors = (
            "# test anchors\n"
            "P1 200 far NOT_TRACKED test\n"
            "P2 700 near TRACKED test\n"
            "FALSE 640 owner-marked walking\n"
        )
        (tmp_path / "map.json").write_text(json.dumps(amap))
        (tmp_path / "pipe.json").write_text(json.dumps(pipe))
        (tmp_path / "anchors.txt").write_text(anchors)
        return tmp_path, amap, pipe

    def test_run_end_to_end(self, world):
        tmp, amap, pipe = world
        out = run(str(tmp / "map.json"), str(tmp / "pipe.json"),
                  str(tmp / "anchors.txt"), str(tmp / "out.json"))
        by_point = {r["point"]: r for r in out["points"]}
        assert by_point[1]["decision"] == "relabeled"
        assert by_point[1]["serve"]["team_resolved"] == "B"
        assert by_point[2]["decision"] == "emitted"
        assert by_point[3]["decision"] == "report_only"
        assert [d["frame"] for d in out["demotions"]] == [640]
        # stream untouched, pass-2 annotations beside the originals
        pa = {a["frame_number"]: a for a in out["actions_pass2"]}
        assert pa[300]["action"] == "dig"
        assert pa[300]["pass2_action"] == "serve"
        assert pa[300]["pass2_team"] == "B"
        assert pa[330].get("pass2_action") is None
        assert pa[640].get("pass2_demoted") is True
        assert pa[700]["pass2_source"] == "emitted"
        assert (tmp / "out.json").exists()

    def test_run_is_deterministic(self, world):
        tmp, _, _ = world
        a = run(str(tmp / "map.json"), str(tmp / "pipe.json"),
                str(tmp / "anchors.txt"), str(tmp / "o1.json"))
        b = run(str(tmp / "map.json"), str(tmp / "pipe.json"),
                str(tmp / "anchors.txt"), str(tmp / "o2.json"))
        assert json.dumps(a["points"]) == json.dumps(b["points"])
        assert json.dumps(a["gates"]) == json.dumps(b["gates"])

    def test_parse_anchors_contiguity_still_enforced(self, tmp_path):
        (tmp_path / "bad.txt").write_text("P1 100 near\nP3 300 far\n")
        with pytest.raises(ValueError):
            parse_serve_anchors(str(tmp_path / "bad.txt"))

    def test_decision_vocabulary_closed(self):
        assert set(_DECISIONS) == {
            "emitted", "relabeled", "owner_pinned", "anchor_only",
            "report_only", "missing"}
