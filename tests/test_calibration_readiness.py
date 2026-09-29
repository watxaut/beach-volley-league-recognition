"""Calibration / view readiness (Stage 0, T1).

The pipeline silently dropped every court-derived feature when no calibration
loaded; the readiness report makes that state explicit and, unless
``--allow-uncalibrated`` is passed, refuses to start.

Note the load-bearing fact pinned by ``test_mismatched_frame_dimensions_*``:
``frame_dimensions`` is NOT a scale hint. ``CourtCalibration._apply_points``
uses it only to SIZE ``court_mask`` (court_calibration.py:316-320) and the
stored points are consumed verbatim, so a calibration whose frame_dimensions
differ from the video yields a wrong-sized court mask.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.db.ingest import ingest_payload
from src.db.schema import connect, init_db
from src.main import (
    DEGRADED_OUTPUTS_WITHOUT_CALIBRATION,
    build_calibration_readiness,
    format_readiness,
    validate_calibration_readiness,
)
from src.output_gen.json_exporter import JSONExporter

WIDTH, HEIGHT = 64, 48  # tiny synthetic clip: readiness never needs real pixels


@pytest.fixture
def video(tmp_path: Path) -> Path:
    path = tmp_path / "video_entreno_x.mp4"
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (WIDTH, HEIGHT)
    )
    assert writer.isOpened()
    for _ in range(5):
        writer.write(np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8))
    writer.release()
    assert path.exists()
    return path


def write_calibration(path: Path, frame_dimensions=(48, 64)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "court_corners": [[0, 40], [40, 38], [63, 44], [1, 45]],
        "midcourt_points": [[15, 41], [45, 40]],
        "net_top_points": [[16, 22], [46, 21]],
        "frame_dimensions": list(frame_dimensions),
    }))
    return path


# --- readiness states -------------------------------------------------------


def test_explicit_calibration_is_usable(tmp_path, video):
    calib = write_calibration(tmp_path / "other_video.json")
    readiness = build_calibration_readiness(
        str(calib), "video_entreno_x", video, origin="explicit"
    )

    assert readiness["calibration_source"] == "explicit"
    assert readiness["stem_matched"] is False  # borrowed from another recording
    assert readiness["dimensions_match"] and readiness["aspect_ratio_match"]
    assert readiness["usable"] is True
    assert readiness["degraded_outputs"] == []
    # The code never rescales a calibration onto the processed frame.
    assert readiness["calibration_scaled_to_video"] is False
    assert readiness["calibration_frame_dimensions"] == {"height": 48, "width": 64}
    assert readiness["video_dimensions"] == {"width": WIDTH, "height": HEIGHT}
    # usable -> no error, with or without the waiver flag
    validate_calibration_readiness(readiness, allow_uncalibrated=False)
    validate_calibration_readiness(readiness, allow_uncalibrated=True)


def test_auto_stem_calibration_is_usable(tmp_path, video):
    calib = write_calibration(tmp_path / "video_entreno_x.json")
    readiness = build_calibration_readiness(
        str(calib), "video_entreno_x", video, origin="auto_stem"
    )

    assert readiness["calibration_source"] == "auto_stem"
    assert readiness["stem_matched"] is True
    assert readiness["usable"] is True
    validate_calibration_readiness(readiness, allow_uncalibrated=False)


def test_explicit_calibration_named_after_the_source_stem(tmp_path, video):
    # Origin, not stem equality, decides calibration_source: an explicit
    # --court that happens to be named after the video is still "explicit".
    calib = write_calibration(tmp_path / "video_entreno_x.json")
    readiness = build_calibration_readiness(
        str(calib), "video_entreno_x", video, origin="explicit"
    )

    assert readiness["calibration_source"] == "explicit"
    assert readiness["stem_matched"] is True
    assert readiness["usable"] is True
    validate_calibration_readiness(readiness, allow_uncalibrated=False)


def test_missing_calibration_is_degraded_and_reported(tmp_path, video):
    readiness = build_calibration_readiness(None, "video_entreno_x", video)

    assert readiness["calibration_path"] is None
    assert readiness["calibration_source"] == "none"
    assert readiness["stem_matched"] is False
    assert readiness["usable"] is False
    assert readiness["degraded_outputs"] == list(DEGRADED_OUTPUTS_WITHOUT_CALIBRATION)
    for feature in ("team_attribution", "near_net_gesture_context", "serve_zone_admission"):
        assert feature in readiness["degraded_outputs"]
    assert "NONE" in format_readiness(readiness)


def test_missing_calibration_errors_without_the_flag(tmp_path, video):
    readiness = build_calibration_readiness(None, "video_entreno_x", video)

    with pytest.raises(ValueError, match="no court calibration found"):
        validate_calibration_readiness(readiness, allow_uncalibrated=False)
    with pytest.raises(ValueError, match="calibrations/video_entreno_x.json"):
        validate_calibration_readiness(readiness, allow_uncalibrated=False)
    # The waiver keeps the run going (as today) but only warns.
    validate_calibration_readiness(readiness, allow_uncalibrated=True)


def test_mismatched_frame_dimensions_error(tmp_path, video):
    # Same aspect ratio (4:3), smaller frame_dimensions: the mask is built at
    # half size and every bbox is clamped into it
    # (player_detector._is_player_in_court) while is_point_in_court rejects
    # everything below the mask height.
    calib = write_calibration(tmp_path / "video_entreno_x.json", frame_dimensions=(24, 32))
    readiness = build_calibration_readiness(str(calib), "video_entreno_x", video)

    assert readiness["dimensions_match"] is False
    assert readiness["aspect_ratio_match"] is True
    assert readiness["usable"] is False
    assert readiness["degraded_outputs"] == list(DEGRADED_OUTPUTS_WITHOUT_CALIBRATION)

    with pytest.raises(ValueError, match="are NOT rescaled|do not fit the video"):
        validate_calibration_readiness(readiness, allow_uncalibrated=False)
    validate_calibration_readiness(readiness, allow_uncalibrated=True)


def test_aspect_ratio_mismatch_errors(tmp_path, video):
    # 16:9 calibration on the 4:3 synthetic clip: a different view entirely.
    calib = write_calibration(tmp_path / "video_entreno_x.json", frame_dimensions=(36, 64))
    readiness = build_calibration_readiness(str(calib), "video_entreno_x", video)

    assert readiness["aspect_ratio_match"] is False
    assert readiness["usable"] is False
    with pytest.raises(ValueError, match="do not fit the video"):
        validate_calibration_readiness(readiness, allow_uncalibrated=False)
    validate_calibration_readiness(readiness, allow_uncalibrated=True)


def test_calibration_without_frame_dimensions_defaults_to_1080p(tmp_path, video):
    calib = tmp_path / "video_entreno_x.json"
    calib.write_text(json.dumps({
        "court_corners": [[0, 40], [40, 38], [63, 44], [1, 45]],
        "midcourt_points": [[15, 41], [45, 40]],
    }))
    readiness = build_calibration_readiness(str(calib), "video_entreno_x", video)

    # CourtCalibration.load() falls back to (1080, 1920) too.
    assert readiness["calibration_frame_dimensions"] == {"height": 1080, "width": 1920}
    assert readiness["usable"] is False


# --- the readiness block travels with the exported payload ------------------


def _results(readiness):
    return {
        "video_info": {
            "path": "resources/video_entreno_3.mp4",
            "fps": 30.0,
            "width": 1920,
            "height": 1080,
            "total_frames": 10,
            "calibration_readiness": readiness,
        },
        "frame_results": [],
    }


def test_json_payload_carries_readiness(tmp_path):
    readiness = build_calibration_readiness(None, "video_entreno_3", Path("x.mp4"))
    payload = JSONExporter().build_payload(_results(readiness))

    assert payload["video"]["calibration_readiness"] == readiness
    # Everything else about the payload is untouched.
    assert payload["schema_version"] == 1
    assert payload["video"]["key"] == "video_entreno_3"
    assert payload["actions"] == [] and payload["spikes"] == []


def test_json_payload_without_readiness_stays_null(tmp_path):
    payload = JSONExporter().build_payload({
        "video_info": {"path": "resources/video_entreno_3.mp4"},
        "frame_results": [],
    })
    assert payload["video"]["calibration_readiness"] is None


def test_db_ingest_tolerates_the_readiness_key(tmp_path):
    readiness = build_calibration_readiness(None, "video_entreno_3", Path("x.mp4"))
    payload = JSONExporter().build_payload(_results(readiness))

    conn = connect(tmp_path / "test.db")
    init_db(conn)
    ingest_payload(conn, payload)
    row = conn.execute(
        "SELECT video_key, width, height FROM videos WHERE video_key = ?",
        ("video_entreno_3",),
    ).fetchone()
    assert tuple(row) == ("video_entreno_3", 1920, 1080)
    conn.close()


def test_unreadable_calibration_file_is_reported(tmp_path, video):
    missing = tmp_path / "does_not_exist.json"
    readiness = build_calibration_readiness(str(missing), "video_entreno_x", video)

    assert readiness["read_error"]
    assert readiness["calibration_frame_dimensions"] is None
    assert readiness["usable"] is False
    with pytest.raises(ValueError, match="could not be read"):
        validate_calibration_readiness(readiness, allow_uncalibrated=False)
    validate_calibration_readiness(readiness, allow_uncalibrated=True)


# --- CLI exit code ----------------------------------------------------------


def _run_main(monkeypatch, tmp_path, video, extra_args=()):
    """Run ``src.main.main()`` in a cwd with no calibrations/ dir."""
    import sys

    import src.main as main_mod

    # The synthetic clip is 64x48; the upscale guard would otherwise transcode it.
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"upscale_to_height": 0}))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv",
        ["src.main", str(video), "--output-dir", str(tmp_path / "out"),
         "--config", str(cfg), *extra_args],
    )
    return main_mod.main()


def test_cli_exits_nonzero_without_a_calibration(monkeypatch, tmp_path, video):
    assert _run_main(monkeypatch, tmp_path, video) == 1
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").glob("*.json"))


def test_cli_unusable_calibration_is_fatal_even_when_supplied(monkeypatch, tmp_path, video):
    calib = write_calibration(tmp_path / "cal" / "video_entreno_x.json", frame_dimensions=(24, 32))
    assert _run_main(monkeypatch, tmp_path, video, ["--court", str(calib)]) == 1

