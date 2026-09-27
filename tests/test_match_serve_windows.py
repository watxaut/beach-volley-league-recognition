"""Tests for scripts/derive_match_serve_windows.py (open point 22 scoping).

Derives per-point serve team (winner-of-previous rule, cross-checked against
descriptions naming a server), court side (fixed squads + side-switch map)
and anchored serve windows (gt_point_start_end.txt format). The real 20260920
match GT is a repo fixture; the derived table must stay stable.
"""

import json
import os
import sys

import pytest

REPO = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS = os.path.join(REPO, "scripts")
for p in (REPO, SCRIPTS):
    if p not in sys.path:
        sys.path.insert(0, p)

import derive_match_serve_windows as dsw  # noqa: E402

MATCH_JSON = os.path.join(REPO, "ground_truth", "20260920_match_points.json")
ANCHORS_TXT = os.path.join(REPO, "ground_truth", "gt_point_start_end.txt")


# ----------------------------------------------------------------------
# mechanical derivations
# ----------------------------------------------------------------------

class TestDeriveServeTeams:
    def test_real_match_winner_serves(self):
        gt = json.load(open(MATCH_JSON, encoding="utf-8"))
        teams = dsw.derive_serve_teams(gt["points"])
        # point 1 has no previous winner and no server named in its text
        assert teams[1] is None
        # every dictated mention must agree with the rule (the function
        # raises on mismatch, so reaching here means 6/6 agree)
        assert teams[2] == "B"   # "Team B fails serve goes outside bounds"
        assert teams[9] == "B"   # "Team B serves, team A returns ..."
        assert teams[17] == "A"  # "Team A ace"
        assert teams[32] == "B"  # "Team B fails serve against the net."
        assert teams[4] == "B"   # "P1 fails serve" (winner A => server was B)
        assert teams[5] == "A"   # "serve out of bounds" (winner B)

    def test_description_mismatch_is_hard_error(self):
        pts = [
            {"point": 1, "winner": "A", "description": "x"},
            {"point": 2, "winner": "A", "description": "Team B serves out"},
        ]
        with pytest.raises(ValueError, match="point 2"):
            dsw.derive_serve_teams(pts)

    def test_description_fills_point1(self):
        pts = [
            {"point": 1, "winner": "A", "description": "Team B serves, A scores"},
            {"point": 2, "winner": "A", "description": "x"},
        ]
        teams = dsw.derive_serve_teams(pts)
        assert teams[1] == "B"

    def test_player_serve_form_validates(self):
        pts = [
            {"point": 1, "winner": "B", "description": "x"},
            {"point": 2, "winner": "A", "description": "P3 fails serve"},
        ]
        # winner-serves says B served pt2; description names a PLAYER, no clash
        assert dsw.derive_serve_teams(pts)[2] == "B"


class TestDeriveSides:
    def test_real_match_switch_map(self):
        gt = json.load(open(MATCH_JSON, encoding="utf-8"))
        sides = dsw.derive_sides(gt["points"])
        assert sides[1] == {"A": "near", "B": "far"}    # start
        assert sides[7] == {"A": "near", "B": "far"}    # switch AFTER 7
        assert sides[8] == {"A": "far", "B": "near"}
        assert sides[14] == {"A": "far", "B": "near"}
        assert sides[15] == {"A": "near", "B": "far"}
        assert sides[28] == {"A": "far", "B": "near"}
        assert sides[29] == {"A": "near", "B": "far"}
        assert sides[33] == {"A": "near", "B": "far"}   # 4 switches -> back


class TestParsePointMoments:
    def test_pairs(self):
        text = "00:10 point starts\n00:18 point stops\n\n4:05 point starts\n4:11 point stops\n"
        assert dsw.parse_point_moments(text) == [(10, 18), (245, 251)]

    def test_errors(self):
        with pytest.raises(ValueError, match="before 'stops'"):
            dsw.parse_point_moments("00:10 point starts\n00:12 point starts\n")
        with pytest.raises(ValueError, match="before 'starts'"):
            dsw.parse_point_moments("00:12 point stops\n")
        with pytest.raises(ValueError, match="unterminated"):
            dsw.parse_point_moments("00:10 point starts\n")


class TestBuildServeWindows:
    @classmethod
    def setup_class(cls):
        cls.gt = json.load(open(MATCH_JSON, encoding="utf-8"))
        cls.anchors = open(ANCHORS_TXT, encoding="utf-8").read()
        cls.fps = 25.6702272643995
        cls.records = dsw.build_serve_windows(cls.gt, cls.anchors, cls.fps)

    def test_anchor_split(self):
        # the committed anchor file covers exactly points 1..13
        assert all(r["anchored"] for r in self.records[:13])
        assert not any(r["anchored"] for r in self.records[13:])
        assert [r["flags"] for r in self.records[13:]] == [
            [dsw.F_UNANCHORED]] * 20

    def test_point1_flags(self):
        r1 = self.records[0]
        assert r1["serve_team"] is None
        assert r1["serve_side"] is None
        assert dsw.F_NO_SERVER in r1["flags"]

    def test_serve_frame_conversion(self):
        # GT pt2 serves at 00:21 -> 21 s * fps
        r2 = self.records[1]
        assert r2["serve_team"] == "B" and r2["serve_side"] == "far"
        assert r2["serve_frame"] == round(21 * self.fps)
        assert r2["window_frames"] == [round(21 * self.fps), round(32 * self.fps)]

    def test_far_side_serve_census(self):
        # 17 far-side serves among the 32 with a derived server
        srv = [r for r in self.records if r["serve_team"]]
        far = [r for r in srv if r["serve_side"] == "far"]
        assert len(srv) == 32
        assert len(far) == 16
        # P11 near (B serves, B is near P8-14); P22/P23 far (A serves, A is
        # far P22-28); P30 near (A serves, A is near P29-33)
        assert [r["point"] for r in far] == [2, 4, 6, 8, 13, 14, 15, 21, 22,
                                             23, 25, 26, 27, 28, 31, 32]


# ----------------------------------------------------------------------
# pipeline cross-checks (synthetic pipeline outputs)
# ----------------------------------------------------------------------

def _rec(point, serve_team, serve_side, window):
    return {"point": point, "winner": "A", "serve_team": serve_team,
            "serve_side": serve_side, "description": "x",
            "anchored": window is not None, "window_frames": window,
            "serve_frame": window[0] if window else None, "flags": []}


class TestAttachServeActions:
    def test_match_and_mismatch(self):
        recs = [_rec(2, "B", "far", [500, 800]),
                _rec(3, "A", "near", [1000, 1200])]
        actions = [
            {"action": "serve", "frame_number": 520, "team": "B", "confidence": 0.75},
            {"action": "serve", "frame_number": 1040, "team": "A", "confidence": 0.75},
            {"action": "dig", "frame_number": 600, "team": "B", "confidence": 0.6},
        ]
        dsw.attach_serve_actions(recs, actions)
        assert recs[0]["emitted_serves"] == [
            {"frame": 520, "team": "B", "confidence": 0.75}]
        assert recs[0]["flags"] == []
        assert [e["frame"] for e in recs[1]["emitted_serves"]] == [1040]
        assert recs[1]["flags"] == []

    def test_no_serve_and_wrong_team(self):
        recs = [_rec(4, "B", "far", [1300, 1500]),
                _rec(5, "A", "near", [1600, 1800])]
        actions = [{"action": "serve", "frame_number": 1330, "team": "A"}]
        dsw.attach_serve_actions(recs, actions)
        assert dsw.F_SERVE_TEAM_MISMATCH in recs[0]["flags"]
        assert dsw.F_NO_SERVE in recs[1]["flags"]

    def test_tolerance_band(self):
        recs = [_rec(6, "B", "far", [1000, 1100])]
        dsw.attach_serve_actions(recs, [{"action": "serve",
                                         "frame_number": 1000 - 41, "team": "B"}])
        assert recs[0]["emitted_serves"] == []
        assert dsw.F_NO_SERVE in recs[0]["flags"]
        dsw.attach_serve_actions(recs, [{"action": "serve",
                                         "frame_number": 1100 + 40, "team": "B"}])
        assert recs[0]["emitted_serves"]

    def test_unanchored_records_untouched(self):
        recs = [_rec(14, "A", "far", None)]
        dsw.attach_serve_actions(recs, [{"action": "serve",
                                         "frame_number": 9999, "team": "A"}])
        assert "emitted_serves" not in recs[0]
        assert recs[0]["flags"] == []  # flags are the builder's job


class TestAttachEpisodeOverlap:
    def test_overlap_and_gap(self, tmp_path):
        csv_path = tmp_path / "gs.csv"
        rows = ["Frame_Index,Game_State"]
        rows += [f"{f},game_off" for f in range(0, 400)]
        rows += [f"{f},game_on" for f in range(400, 500)]   # covers pt A only
        rows += [f"{f},game_off" for f in range(500, 2000)]
        csv_path.write_text("\n".join(rows) + "\n")
        recs = [_rec(2, "B", "far", [420, 480]),
                _rec(3, "A", "near", [900, 1000])]
        dsw.attach_episode_overlap(recs, str(csv_path))
        assert recs[0]["flags"] == []
        assert dsw.F_NO_EPISODE in recs[1]["flags"]


class TestSummarizeRealMatch:
    def test_side_split_on_real_fixture(self):
        gt = json.load(open(MATCH_JSON, encoding="utf-8"))
        anchors = open(ANCHORS_TXT, encoding="utf-8").read()
        records = dsw.build_serve_windows(gt, anchors, 25.6702272643995)
        summary = dsw.summarize(records)
        assert summary["n_anchored"] == 13
        assert summary["n_unanchored"] == 20
        far = summary["far_side"]
        near = summary["near_side"]
        assert far["points"] == [2, 4, 6, 8, 13]
        assert near["points"] == [3, 5, 7, 9, 10, 11, 12]
        assert far["n_points"] + near["n_points"] == 12  # pt1 has no server
