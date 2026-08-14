"""Unit tests for the non-interactive parts of scripts/annotate_player_gt.py."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from annotate_player_gt import (  # noqa: E402
    load_tracks_boxes,
    load_or_create_gt,
    sample_frames,
    write_frame_gt,
)


class _FakeCalib:
    """Duck-typed stand-in for CourtCalibration."""

    _calibrated = True

    def __init__(self, team="A"):
        self.team = team

    def get_team_for_bbox(self, bbox):
        return self.team


def _write_tracks(tmp_path, frames):
    path = tmp_path / "tracks.json"
    path.write_text(json.dumps({
        "video": "v.mp4",
        "frames": [
            {"frame": f, "players": [
                {"track_id": tid, "bbox": [1.2, 2.5, 3.7, 4.9], "foot_team": "A"}
                for tid in pids
            ]}
            for f, pids in frames
        ],
    }))
    return str(path)


class TestLoadTracksBoxes:
    def test_loads_and_intifies(self, tmp_path):
        path = _write_tracks(tmp_path, [(0, [1, 2]), (7, [3])])
        boxes = load_tracks_boxes(path)
        assert set(boxes) == {0, 7}
        assert boxes[0][0]["bbox"] == [1, 2, 3, 4]  # floats -> int
        assert boxes[0][0]["track_id"] == 1

    def test_frame_without_players(self, tmp_path):
        path = _write_tracks(tmp_path, [(3, [])])
        assert load_tracks_boxes(path)[3] == []


class TestSampleFrames:
    def test_basic_stride(self):
        assert sample_frames(441, 10, 0, None) == list(range(0, 441, 10))

    def test_end_is_exclusive_and_capped(self):
        assert sample_frames(100, 30, 0, 200) == [0, 30, 60, 90]

    def test_start_offset(self):
        assert sample_frames(100, 10, 25, 50) == [25, 35, 45]

    def test_every_zero_is_clamped(self):
        assert sample_frames(10, 0, 0, None) == list(range(10))


class TestWriteFrameGt:
    def test_writes_assigned_skips_dropped(self):
        gt = {"annotated_frames": {"players": {"frames": {}}}}
        boxes = [
            {"track_id": 1, "bbox": [0, 0, 10, 40]},
            {"track_id": 2, "bbox": [50, 0, 60, 40]},
            {"track_id": 3, "bbox": [100, 0, 110, 40]},
        ]
        ids = write_frame_gt(gt, 42, boxes, {0: 2, 2: 1}, _FakeCalib("B"))
        assert ids == [2, 1]
        written = gt["annotated_frames"]["players"]["frames"]["42"]
        assert len(written) == 2
        assert written[0] == {"id": 2, "team": "B", "bbox": [0, 0, 10, 40]}

    def test_duplicate_ids_reported(self):
        gt = {"annotated_frames": {"players": {"frames": {}}}}
        boxes = [{"track_id": t, "bbox": [0, 0, 1, 1]} for t in (1, 2)]
        ids = write_frame_gt(gt, 0, boxes, {0: 1, 1: 1}, _FakeCalib())
        assert ids == [1, 1]

    def test_team_none_without_calib(self):
        gt = {"annotated_frames": {"players": {"frames": {}}}}
        boxes = [{"track_id": 1, "bbox": [0, 0, 1, 1]}]
        write_frame_gt(gt, 0, boxes, {0: 1}, None)
        assert gt["annotated_frames"]["players"]["frames"]["0"][0]["team"] is None


class TestLoadOrCreateGt:
    def test_creates_skeleton(self, tmp_path):
        path = tmp_path / "gt.json"
        gt = load_or_create_gt(path, "v.mp4", 30.0, 1920, 1080)
        assert gt["video"] == "v.mp4"
        assert gt["resolution"] == [1920, 1080]
        for comp in ("ball", "players", "actions"):
            assert comp in gt["annotated_frames"]
        assert gt["annotated_frames"]["players"]["frames"] == {}

    def test_preserves_existing_content(self, tmp_path):
        path = tmp_path / "gt.json"
        existing = {
            "video": "old.mp4",
            "fps": 29.97,
            "actions_in_other_place": {"kept": True},
            "annotated_frames": {
                "ball": {"frames": {"5": {"x": 1, "y": 2, "visible": True}}},
                "actions": {"events": [{"frame": 10, "player_id": 1, "action": "serve"}]},
                "players": {"frames": {"100": [{"id": 1, "team": "A", "bbox": [0, 0, 1, 1]}]}},
            },
        }
        path.write_text(json.dumps(existing))
        gt = load_or_create_gt(path, "new.mp4", 30.0, 1920, 1080)
        assert gt["video"] == "old.mp4"  # untouched
        assert gt["annotated_frames"]["ball"]["frames"]["5"]["x"] == 1
        assert gt["annotated_frames"]["players"]["frames"]["100"][0]["id"] == 1
        assert gt["actions_in_other_place"] == {"kept": True}
