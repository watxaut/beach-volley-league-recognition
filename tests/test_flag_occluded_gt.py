"""Tests for occlusion flagging (scripts/flag_occluded_gt.py) and evaluate.py's
handling of invisible GT players."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from flag_occluded_gt import containment, flag_occluded_frames  # noqa: E402
from evaluate import evaluate_player_tracking  # noqa: E402


def _p(pid, bbox, visible=None):
    d = {"id": pid, "team": "A", "bbox": bbox}
    if visible is not None:
        d["visible"] = visible
    return d


class TestContainment:
    def test_identical_boxes(self):
        assert containment([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0

    def test_disjoint_boxes(self):
        assert containment([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0

    def test_half_covered(self):
        # inner [0,0,10,10] covered on its left half by [0,0,5,10]
        assert abs(containment([0, 0, 10, 10], [0, 0, 5, 10]) - 0.5) < 1e-9


class TestFlagOccludedFrames:
    def test_occluded_flagged(self):
        frames = {
            "0": [
                _p(1, [0, 0, 100, 400]),    # occluder (near side, big box)
                _p(3, [10, 50, 90, 380]),   # ~80% inside player 1
            ]
        }
        flags = flag_occluded_frames(frames, 0.5)
        assert flags["0"] == {1: True, 3: False}

    def test_partial_overlap_stays_visible(self):
        frames = {
            "0": [
                _p(1, [0, 0, 100, 400]),
                _p(3, [60, 20, 200, 390]),  # only a sliver overlaps
            ]
        }
        flags = flag_occluded_frames(frames, 0.5)
        assert flags["0"] == {1: True, 3: True}

    def test_empty_and_none_frames(self):
        flags = flag_occluded_frames({"5": [], "7": None}, 0.5)
        assert flags == {"5": {}, "7": {}}


class TestEvaluateSkipsInvisible:
    GT = {"frames": {
        "0": [
            _p(1, [0, 0, 50, 100]),
            _p(2, [100, 0, 150, 100], visible=False),  # occluded
        ]
    }}

    def test_invisible_not_counted_as_miss(self):
        preds = {"0": [
            {"id": 9, "bbox": [1, 1, 51, 101], "team": "A"},   # matches GT 1
            {"id": 8, "bbox": [300, 300, 350, 400], "team": "B"},  # ghost over GT 2's spot
        ]}
        m = evaluate_player_tracking(preds, self.GT)
        # GT 2 is invisible: not in the denominator, ghost still counted
        assert m["total_gt_players"] == 1
        assert m["total_gt_occluded"] == 1
        assert m["detection_rate"] == 1.0
        assert m["id_consistency"]["per_player"].keys() == {"1"}

    def test_all_visible_by_default(self):
        gt = {"frames": {"0": [_p(1, [0, 0, 50, 100])]}}
        m = evaluate_player_tracking({"0": []}, gt)
        assert m["total_gt_players"] == 1
        assert m["total_gt_occluded"] == 0
        assert m["detection_rate"] == 0.0
