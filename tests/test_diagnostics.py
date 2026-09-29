"""Tests for the off-by-default diagnostic recorder (T4).

These pin the *inertness* contract: the sinks are plain attributes that default
to off, and the recorder only ever stores what it is handed (no re-computation
happens inside it).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.recognition.action_classifier import ActionClassifier
from src.tracking.ball_tracker import BallTracker
from src.utils.diagnostics import SCHEMA_VERSION, DiagRecorder, load_diag

ROOT = Path(__file__).resolve().parents[1]


def test_hooks_are_off_by_default():
    # BallDetector is skipped here: it loads YOLO weights on construction. Its
    # flag is pinned by the source check below.
    assert BallTracker().diag_enabled is False
    clf = ActionClassifier(pose_estimator=None)
    assert clf.diag_enabled is False


@pytest.mark.parametrize("rel", ["src/detection/ball_detector.py",
                                 "src/tracking/ball_tracker.py",
                                 "src/recognition/action_classifier.py"])
def test_every_component_declares_the_flag(rel):
    assert "self.diag_enabled = False" in (ROOT / rel).read_text()


def test_recorder_merges_sections_onto_past_frames(tmp_path):
    path = tmp_path / "d.jsonl"
    rec = DiagRecorder(str(path), video="v.mp4", fps=30.0)
    rec.add_frame(10, {"ball_dets": [{"center": [1.0, 2.0], "conf": 0.9}],
                       "ball_track": {"state": "tracked", "reason": "locked_admitted"}})
    # A candidate confirmed at frame 10 is confirmed 7 frames later and keyed
    # by its CONTACT frame, i.e. a frame already written.
    rec.add_section("candidates", [{"frame": 10, "seen_at": 17, "stage": "accepted"}])
    rec.add_frame(11, {"ball_dets": [], "ball_track": None})
    rec.write()

    out = load_diag(str(path))
    assert out["meta"]["schema_version"] == SCHEMA_VERSION
    assert out["meta"]["fps"] == 30.0
    assert out["frames"][10]["candidates"][0]["seen_at"] == 17
    assert out["frames"][10]["ball_track"]["state"] == "tracked"
    # empty containers are dropped, the frame itself is not
    assert "ball_dets" not in out["frames"][11]


def test_recorder_is_jsonl_with_one_meta_header(tmp_path):
    path = tmp_path / "d.jsonl"
    rec = DiagRecorder(str(path))
    rec.add_frame(0, {"players": [{"track_id": 1}]})
    rec.write()
    lines = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    assert lines[0] == {"meta": lines[0]["meta"]}
    assert lines[0]["meta"]["kind"] == "volley_recognition_diag_dump"
    assert lines[1]["frame"] == 0


def test_recorder_write_is_idempotent(tmp_path):
    path = tmp_path / "d.jsonl"
    rec = DiagRecorder(str(path))
    rec.add_frame(1, {"players": [{"track_id": 1}]})
    rec.write()
    first = path.read_text()
    assert rec.write() == str(path)
    assert path.read_text() == first


def test_load_diag_returns_empty_frames_for_metadata_only(tmp_path):
    path = tmp_path / "d.jsonl"
    rec = DiagRecorder(str(path))
    rec.write()
    out = load_diag(str(path))
    assert out["frames"] == {} and out["meta"]["kind"] == "volley_recognition_diag_dump"


# --- gate helper: scripts/compare_runs.py -----------------------------------

import sys as _sys  # noqa: E402

_sys.path.insert(0, str(ROOT / "scripts"))
from compare_runs import VOLATILE_CSV_ROWS, compare  # noqa: E402


def _write_run(path, *, stamp="t0", seconds="1.0"):
    path.mkdir(parents=True, exist_ok=True)
    (path / "pipeline_output.json").write_text(json.dumps(
        {"processed_at": stamp, "pipeline_version": "abc", "actions": [{"frame": 1}],
         "spikes": [], "snapshots": [], "game_state": {}}))
    for name in ("results.csv", "results_detailed.csv", "results_game_state.csv",
                 "results_spikes.csv"):
        (path / name).write_text("k,v\na,1\n")
    (path / "results_statistics.csv").write_text(
        "Metric,Value,Unit\nVideo_Total_Frames,10,frames\n"
        f"Total_Processing_Time,{seconds},seconds\n"
        "Average_Frame_Processing_Time,0.1,seconds\n"
        "Processing_FPS_Achieved,9.9,fps\n")


def test_compare_runs_accepts_only_metadata_and_wall_clock_drift(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _write_run(a, stamp="t0", seconds="1.0")
    _write_run(b, stamp="t1", seconds="2.0")
    res = compare(str(a), str(b))
    assert res["json_identical"] is True
    assert res["csv_diff"] == []
    assert set(res["volatile_diff"]) == {"processed_at"}
    assert VOLATILE_CSV_ROWS  # the ignored metrics are explicit, not hidden


def test_compare_runs_flags_a_real_action_change(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _write_run(a)
    _write_run(b)
    blob = json.loads((b / "pipeline_output.json").read_text())
    blob["actions"] = [{"frame": 2}]
    (b / "pipeline_output.json").write_text(json.dumps(blob))
    res = compare(str(a), str(b))
    assert res["json_identical"] is False
    assert res["action_diff_count"] == 1


def test_compare_runs_flags_a_real_csv_change(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _write_run(a)
    _write_run(b)
    (b / "results.csv").write_text("k,v\na,2\n")
    assert compare(str(a), str(b))["csv_diff"]
