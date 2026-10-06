"""src/publish/inbox.py with a fake command runner (no Drive, no real run)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.publish.inbox import Inbox, InboxConfig, _parse_utc  # noqa: E402

DRIVE_ID = "1AbCdEf"


class FakeRunner:
    """Plays rclone / ffprobe / make / the publisher / pmset."""

    def __init__(self, root: Path, files, creation_time="2026-10-04T16:05:12.000000Z",
                 on_ac=True, run_fails=False):
        self.root = root
        self.files = files                       # Drive inbox listing
        self.creation_time = creation_time
        self.on_ac = on_ac
        self.run_fails = run_fails
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        ok = lambda out="": subprocess.CompletedProcess(cmd, 0, out, "")  # noqa: E731
        if cmd[0] == "caffeinate":
            cmd = cmd[2:]
        if cmd[:2] == ["rclone", "lsjson"]:
            return ok(json.dumps(self.files))
        if cmd[:2] == ["rclone", "copyto"]:
            Path(cmd[3]).write_bytes(b"video")
            return ok()
        if cmd[:2] == ["rclone", "moveto"]:
            self.files = [f for f in self.files if not cmd[2].endswith(f["Path"])]
            return ok()
        if cmd[0] == "ffprobe":
            tags = {"creation_time": self.creation_time} if self.creation_time else {}
            return ok(json.dumps({"format": {"tags": tags}, "streams": []}))
        if cmd[0] == "pmset":
            return ok("Now drawing from 'AC Power'" if self.on_ac else "Now drawing from 'Battery Power'")
        if cmd[0] == "make" and cmd[1] == "run-match":
            if self.run_fails:
                return subprocess.CompletedProcess(cmd, 2, "", "boom")
            key = Path(cmd[2].split("=", 1)[1]).stem
            (self.root / "output" / key / "match_reconstruction.json").write_text("{}")
            return ok()
        if cmd[1:3] == ["-m", "src.publish"]:
            return ok("score     A 21 - B 12   points 33\npublished: applied")
        raise AssertionError(f"unexpected command {cmd}")

    def names(self):
        return [" ".join(c[:2]) for c in self.calls]


def _inbox(tmp_path, runner, require_ac=True):
    cfg = InboxConfig(root=tmp_path, require_ac=require_ac, python="python")
    inbox = Inbox(cfg, run=runner, notify_cmd=None)
    return inbox


def _listing(name="IMG_1234.MOV"):
    return [{"Path": name, "Name": name, "Size": 5, "ID": DRIVE_ID,
             "ModTime": "2026-10-04T18:30:00.123456789Z", "IsDir": False}]


def test_new_video_is_named_then_waits_for_calibration(tmp_path):
    runner = FakeRunner(tmp_path, _listing())
    inbox = _inbox(tmp_path, runner)
    inbox.run_once()
    key = "20261004_1805_img_1234"         # 16:05 UTC = 18:05 Madrid (CEST)
    assert (tmp_path / "resources" / f"{key}.mov").exists()
    source = json.loads((tmp_path / "output" / key / "source.json").read_text())
    assert source["video_url"] == f"https://drive.google.com/file/d/{DRIVE_ID}/view"
    assert source["time_source"] == "creation_time"
    state = json.loads((tmp_path / "data" / "inbox_state.json").read_text())
    assert state["files"][DRIVE_ID]["status"] == "needs_calibration"
    assert sum("needs its court calibration" in m for m in inbox.log) == 1
    # a second pass neither downloads again nor nags again
    runner.calls.clear()
    inbox.run_once()
    assert "rclone copyto" not in runner.names()
    assert sum("needs its court calibration" in m for m in inbox.log) == 1


def test_calibrated_video_is_run_published_and_archived(tmp_path):
    runner = FakeRunner(tmp_path, _listing("20261004_1805_bogatell_ari_joan.mp4"))
    inbox = _inbox(tmp_path, runner)
    (tmp_path / "calibrations").mkdir()
    (tmp_path / "calibrations" / "20261004_1805_bogatell_ari_joan.json").write_text("{}")
    inbox.run_once()
    names = runner.names()
    assert names.index("make run-match") < names.index("python -m") < names.index("rclone moveto")
    move = next(c for c in runner.calls if c[:2] == ["rclone", "moveto"])
    assert move[3] == "gdrive:VolleyArchive/20261004_1805_bogatell_ari_joan.mp4"
    state = json.loads((tmp_path / "data" / "inbox_state.json").read_text())
    assert state["files"][DRIVE_ID]["status"] == "archived"
    assert any("Draft ready to review" in m and "A 21 - B 12" in m for m in inbox.log)


def test_legacy_dated_name_gains_the_time(tmp_path):
    runner = FakeRunner(tmp_path, _listing("20261004_bogatell.mp4"))
    _inbox(tmp_path, runner).run_once()
    assert (tmp_path / "resources" / "20261004_1805_bogatell.mp4").exists()


def test_no_metadata_falls_back_to_the_drive_time(tmp_path):
    runner = FakeRunner(tmp_path, _listing(), creation_time=None)
    _inbox(tmp_path, runner).run_once()
    # 18:30:00.123456789Z (nanoseconds) = 20:30 in Madrid
    assert (tmp_path / "resources" / "20261004_2030_img_1234.mov").exists()
    state = json.loads((tmp_path / "data" / "inbox_state.json").read_text())
    assert state["files"][DRIVE_ID]["time_source"] == "drive_modtime"


def test_battery_defers_the_run(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/" + name
                        if name == "pmset" else None)
    runner = FakeRunner(tmp_path, _listing("20261004_1805_court.mp4"), on_ac=False)
    inbox = _inbox(tmp_path, runner)
    (tmp_path / "calibrations").mkdir()
    (tmp_path / "calibrations" / "20261004_1805_court.json").write_text("{}")
    inbox.run_once()
    assert "make run-match" not in runner.names()
    state = json.loads((tmp_path / "data" / "inbox_state.json").read_text())
    assert state["files"][DRIVE_ID]["status"] == "waiting_for_power"


def test_failed_run_is_reported_and_not_retried_automatically(tmp_path):
    runner = FakeRunner(tmp_path, _listing("20261004_1805_court.mp4"), run_fails=True)
    inbox = _inbox(tmp_path, runner)
    (tmp_path / "calibrations").mkdir()
    (tmp_path / "calibrations" / "20261004_1805_court.json").write_text("{}")
    inbox.run_once()
    state = json.loads((tmp_path / "data" / "inbox_state.json").read_text())
    assert state["files"][DRIVE_ID]["status"] == "failed"
    assert any("FAILED" in m for m in inbox.log)
    runner.calls.clear()
    inbox.run_once()
    assert "make run-match" not in runner.names(), "a failed video waits for --retry"


def test_a_second_pass_while_one_runs_does_nothing(tmp_path):
    import fcntl

    runner = FakeRunner(tmp_path, _listing())
    inbox = _inbox(tmp_path, runner)
    inbox.cfg.lock_path.parent.mkdir(parents=True)
    with open(inbox.cfg.lock_path, "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        inbox.run_once()
    assert runner.calls == []


@pytest.mark.parametrize("raw,expected", [
    ("2026-10-04T16:05:12.000000Z", "2026-10-04T16:05:12+00:00"),
    ("2026-10-04T16:05:12.123456789Z", "2026-10-04T16:05:12.123456+00:00"),
    ("2026-10-04T16:05:12+02:00", "2026-10-04T16:05:12+02:00"),
])
def test_parse_utc(raw, expected):
    assert _parse_utc(raw).isoformat() == expected
