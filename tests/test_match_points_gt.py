"""Tests for the match GT text parser and the match point-layer evaluator.

The owner dictates match GT as free text (point descriptions + a running
score table with Side switch markers); scripts/parse_match_gt_text.py
transcribes it mechanically into ground_truth/<stem>_match_points.json and
scripts/evaluate_match_points.py scores the pipeline's point layer against
it. The real 20260920 match file is a repo fixture -- the transcription
must stay byte-stable against owner edits.
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

import evaluate_match_points as emp  # noqa: E402
import parse_match_gt_text as pgt  # noqa: E402

MATCH_TXT = os.path.join(REPO, "ground_truth", "20260920_match_ari_joan_lost.txt")
MATCH_JSON = os.path.join(REPO, "ground_truth", "20260920_match_points.json")


# ----------------------------------------------------------------------
# parser
# ----------------------------------------------------------------------

class TestParseRealMatchGT:
    """The committed 20260920 match GT transcribes to the ratified numbers."""

    @classmethod
    def setup_class(cls):
        with open(MATCH_TXT, encoding="utf-8") as f:
            cls.gt = pgt.parse_match_gt_text(f.read())

    def test_counts_and_final(self):
        assert len(self.gt["points"]) == 33
        assert self.gt["final_score"] == {"A": 21, "B": 12}

    def test_switches(self):
        # every-7-combined-points beach format; owner marked 4 switches
        assert self.gt["side_switch_after_point"] == [7, 14, 21, 28]
        flagged = [p["point"] for p in self.gt["points"] if p["side_switch_after"]]
        assert flagged == [7, 14, 21, 28]

    def test_winners_mechanical(self):
        winners = "".join(p["winner"] for p in self.gt["points"])
        assert winners == "BABABAABBBBAABAAAAABAABAAAAAABBAA"
        assert self.gt["points"][0]["winner"] == "B"   # A fails spike into the net
        assert self.gt["points"][32]["winner"] == "A"  # B spikes outside

    def test_scores_monotone(self):
        prev = {"A": 0, "B": 0}
        for p in self.gt["points"]:
            cur = p["score_after"]
            assert (cur["A"] - prev["A"], cur["B"] - prev["B"]) in ((0, 1), (1, 0))
            prev = cur

    def test_descriptions_verbatim(self):
        pts = self.gt["points"]
        assert pts[0]["description"] == "Team A fails spike into the net"
        assert pts[3]["description"] == "P1 fails serve"  # P1 = player, not point
        assert pts[32]["description"] == "Team B spikes outside of the court."

    def test_committed_json_matches_reparse(self):
        """The committed JSON must be exactly what the text parses to."""
        committed = json.loads(open(MATCH_JSON, encoding="utf-8").read())
        for key in ("final_score", "side_switch_after_point", "points"):
            assert committed[key] == self.gt[key], key


class TestParseSynthetic:
    def test_switch_placement(self):
        text = (
            "Team A near, Team B far\n"
            "P1: alpha\nP2: beta\nP3: gamma\n"
            "Points\nA  B\n0  1\n0  2\nSide switch\n1  2\n"
        )
        gt = pgt.parse_match_gt_text(text)
        assert gt["side_switch_after_point"] == [2]
        # the flag sits on the point AFTER WHICH the switch happens
        assert [p["side_switch_after"] for p in gt["points"]] == [
            False, True, False,
        ]
        assert gt["final_score"] == {"A": 1, "B": 2}

    def test_mismatched_counts_raise(self):
        text = "P1: alpha\nPoints\nA  B\n0  1\n1  1\n"
        with pytest.raises(ValueError, match="descriptions vs"):
            pgt.parse_match_gt_text(text)

    def test_non_incrementing_row_raises(self):
        text = "P1: alpha\nP2: beta\nPoints\nA  B\n0  1\n0  1\n"
        with pytest.raises(ValueError, match="does not increment"):
            pgt.parse_match_gt_text(text)

    def test_garbage_table_line_raises(self):
        text = "P1: alpha\nPoints\nA  B\n0  1\nnonsense\n"
        with pytest.raises(ValueError, match="unparsed table line"):
            pgt.parse_match_gt_text(text)


# ----------------------------------------------------------------------
# evaluator
# ----------------------------------------------------------------------

class TestEpisodeReconstruction:
    def test_spans(self, tmp_path):
        rows = ["Frame_Index,Timestamp_Seconds,Game_State,Episode_Start_Frame,"
                "Episode_Frames,Points_So_Far,Point_Index"]
        states = ["game_off"] * 3 + ["game_on"] * 4 + ["game_off"] * 2 + ["game_on"] * 2
        for i, s in enumerate(states):
            rows.append(f"{i},{i / 30.0:.2f},{s},,0,0,-1")
        csv_path = tmp_path / "gs.csv"
        csv_path.write_text("\n".join(rows) + "\n")
        assert emp.episodes_from_game_state_csv(str(csv_path)) == [(3, 6), (9, 10)]

    def test_video_ends_on(self, tmp_path):
        rows = ["Frame_Index,Timestamp_Seconds,Game_State,Episode_Start_Frame,"
                "Episode_Frames,Points_So_Far,Point_Index"]
        for i in range(3):
            rows.append(f"{i},{i / 30.0:.2f},game_on,,0,0,-1")
        csv_path = tmp_path / "gs.csv"
        csv_path.write_text("\n".join(rows) + "\n")
        assert emp.episodes_from_game_state_csv(str(csv_path)) == [(0, 2)]


GT_FIXTURE = {
    "format": "match-points-v1",
    "video": "v",
    "final_score": {"A": 2, "B": 1},
    "side_switch_after_point": [2],
    "points": [
        {"point": 1, "winner": "B", "score_after": {"A": 0, "B": 1},
         "side_switch_after": False, "description": "a"},
        {"point": 2, "winner": "A", "score_after": {"A": 1, "B": 1},
         "side_switch_after": True, "description": "b"},
        {"point": 3, "winner": "A", "score_after": {"A": 2, "B": 1},
         "side_switch_after": False, "description": "c"},
    ],
}


class TestSummarize:
    def test_quantifies_first_confirmed(self):
        # episodes at f100 (GT pt1), f200 (GT pt2), f300 (GT pt3);
        # only the third is confirmed by the pipeline.
        episodes = [(100, 150), (200, 240), (300, 380)]
        confirmed = [{"start_frame": 300, "end_frame": 380, "n_actions": 2}]
        rep = emp.summarize(GT_FIXTURE, confirmed, episodes, fps=30.0)
        pl = rep["pipeline"]
        assert pl["n_episodes"] == 3
        assert pl["n_confirmed_points"] == 1
        assert pl["episodes_before_first_confirmed"] == 2
        assert pl["implied_first_confirmed_ordinal"] == 3
        assert pl["confirmation_ratio"] == round(1 / 3, 3)
        assert [e["confirmed"] for e in pl["episodes"]] == [False, False, True]

    def test_confirmation_tolerance(self):
        # episode start 20f BEFORE the confirmed point's backdated start
        episodes = [(280, 380)]
        confirmed = [{"start_frame": 300, "end_frame": 380, "n_actions": 2}]
        rep = emp.summarize(GT_FIXTURE, confirmed, episodes, fps=30.0)
        assert rep["pipeline"]["episodes"][0]["confirmed"] is True

    def test_no_confirmed_points(self):
        rep = emp.summarize(GT_FIXTURE, [], [(100, 150)], fps=30.0)
        pl = rep["pipeline"]
        assert pl["implied_first_confirmed_ordinal"] is None
        assert pl["episodes_before_first_confirmed"] == 1
        assert pl["confirmation_ratio"] == 0.0


class TestLoadMatchGT:
    def test_real_file_loads(self):
        gt = emp.load_match_gt(MATCH_JSON)
        assert gt["format"] == "match-points-v1"
        assert len(gt["points"]) == 33

    def test_bad_format_raises(self, tmp_path):
        p = tmp_path / "gt.json"
        p.write_text(json.dumps({"format": "nope", "points": []}))
        with pytest.raises(ValueError, match="unexpected format"):
            emp.load_match_gt(str(p))

    def test_final_score_mismatch_raises(self, tmp_path):
        bad = dict(GT_FIXTURE)
        bad["final_score"] = {"A": 9, "B": 9}
        p = tmp_path / "gt.json"
        p.write_text(json.dumps(bad))
        with pytest.raises(ValueError, match="final_score"):
            emp.load_match_gt(str(p))
