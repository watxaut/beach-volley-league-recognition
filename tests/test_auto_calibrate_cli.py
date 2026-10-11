"""The automatic calibration around the detector: the CLI (`make
autocalibrate`), the proposal `make calibrate` can take with one key, and
what a run says about a calibration nobody clicked. Drawn courts only (the
renderer of ``test_court_autocalibration``)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))

import auto_calibrate  # noqa: E402
import test_court_calibration as clicks  # noqa: E402  (the `make calibrate` script)
from src.detection.calibration_readiness import (  # noqa: E402
    build_calibration_readiness, format_readiness)
from src.detection.court_calibration import CourtCalibration  # noqa: E402
from test_court_autocalibration import Camera, H, W, corner_errors, draw_court  # noqa: E402

KEY = "20261011_1000_drawn_court"


def _video(path: Path, frame) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (W, H))
    assert writer.isOpened()
    for _ in range(8):
        writer.write(frame)
    writer.release()
    return path


@pytest.fixture(scope="module")
def court_video(tmp_path_factory) -> Path:
    return _video(tmp_path_factory.mktemp("videos") / f"{KEY}.mp4", draw_court(Camera()))


def _run(video: Path, tmp_path: Path, *flags: str) -> int:
    return auto_calibrate.main([str(video), "--calibrations", str(tmp_path / "calibrations"),
                                "--debug-dir", str(tmp_path / "proposal"), *flags])


def test_a_proposal_is_written_and_nothing_else(court_video, tmp_path, capsys):
    assert _run(court_video, tmp_path) == 0                  # the detector accepted it
    proposal = tmp_path / "proposal"
    for name in ("plate.png", "auto_overlay.jpg", "auto_points.jpg", "auto_calibration.json",
                 auto_calibrate.PROPOSAL_NAME):
        assert (proposal / name).exists(), name
    assert not (tmp_path / "calibrations").exists()          # no --write, no calibration
    report = json.loads(capsys.readouterr().out)
    assert report["stem"] == KEY and report["accepted"] is True


def test_write_saves_an_accepted_calibration_the_pipeline_reads(court_video, tmp_path):
    assert _run(court_video, tmp_path, "--write") == 0
    target = tmp_path / "calibrations" / f"{KEY}.json"
    doc = json.loads(target.read_text())
    assert doc["source"] == "auto" and doc["auto"]["accepted_by"] == "checks"
    assert doc["frame_dimensions"] == [H, W]
    assert corner_errors(doc, Camera()).max() <= 6.0         # through a lossy video too
    assert CourtCalibration(str(target)).is_calibrated


def test_write_never_replaces_a_calibration(court_video, tmp_path):
    target = tmp_path / "calibrations" / f"{KEY}.json"
    target.parent.mkdir()
    target.write_text('{"clicked": "by the owner"}')
    _run(court_video, tmp_path, "--write", "--no-camera-prior")
    assert json.loads(target.read_text()) == {"clicked": "by the owner"}


def test_a_video_without_a_court_exits_2_and_writes_no_calibration(tmp_path):
    video = _video(tmp_path / "20261011_1100_just_sand.mp4", draw_court(Camera(), tape=False))
    assert _run(video, tmp_path, "--write") == 2
    assert not (tmp_path / "calibrations").exists()
    assert not (tmp_path / "proposal" / auto_calibrate.PROPOSAL_NAME).exists()
    assert json.loads((tmp_path / "proposal" / "auto_calibration.json").read_text())["points"] is None


def test_an_unreadable_video_is_an_error(tmp_path):
    missing = tmp_path / "20261011_1200_nothing.mp4"
    missing.write_bytes(b"not a video")
    assert _run(missing, tmp_path) == 1


# -- `make calibrate` takes a proposal ---------------------------------------- #

def test_the_owner_accepts_a_proposal_with_one_key(court_video, tmp_path):
    _run(court_video, tmp_path)
    path = tmp_path / "proposal" / auto_calibrate.PROPOSAL_NAME
    doc = clicks.load_proposal(path, (H, W))
    assert doc is not None and doc["auto"]["accepted_by"] == "checks"
    target = tmp_path / "calibrations" / f"{KEY}.json"
    clicks.save_accepted_proposal(doc, target)
    saved = json.loads(target.read_text())
    assert saved["auto"]["accepted_by"] == "owner" and saved["source"] == "auto"
    assert saved["court_corners"] == doc["court_corners"]
    assert clicks.calibration_from(saved).is_calibrated


def test_a_proposal_for_another_picture_is_not_offered(court_video, tmp_path):
    _run(court_video, tmp_path)
    path = tmp_path / "proposal" / auto_calibrate.PROPOSAL_NAME
    assert clicks.load_proposal(path, (720, 1280)) is None   # found on other pixels
    assert clicks.load_proposal(tmp_path / "nothing.json", (H, W)) is None
    path.write_text("{broken")
    assert clicks.load_proposal(path, (H, W)) is None


def test_the_proposal_lives_where_the_inbox_says(tmp_path):
    video = "resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4"
    assert clicks.proposal_path(video, tmp_path) == (
        tmp_path / "20260920_match_ari_joan_lost" / "calibration_auto" / "calibration_auto.json")
    assert (auto_calibrate.PROPOSAL_DIR, auto_calibrate.PROPOSAL_NAME) == clicks.PROPOSAL


# -- what a run reports -------------------------------------------------------- #

def test_only_an_automatic_calibration_says_how_it_was_found(court_video, tmp_path):
    _run(court_video, tmp_path, "--write")
    auto = tmp_path / "calibrations" / f"{KEY}.json"
    readiness = build_calibration_readiness(str(auto), KEY, court_video)
    assert readiness["usable"] and readiness["calibration_method"] == "auto"
    assert readiness["calibration_auto"]["accepted_by"] == "checks"
    assert "found by" in format_readiness(readiness)

    clicked = tmp_path / "clicked.json"
    doc = json.loads(auto.read_text())
    clicked.write_text(json.dumps({k: doc[k] for k in (
        "court_corners", "midcourt_points", "net_top_points", "frame_dimensions")}))
    manual = build_calibration_readiness(str(clicked), KEY, court_video, origin="explicit")
    assert "calibration_method" not in manual and "calibration_auto" not in manual
    assert "found by" not in format_readiness(manual)
