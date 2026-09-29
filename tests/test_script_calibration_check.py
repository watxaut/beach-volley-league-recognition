"""Script-level calibration readiness gate (probe scripts).

``scripts/test_action_recognition.py`` (and the sibling probes) are where every
GT-validated number comes from; an uncalibrated run used to be produced silently
and then compared against calibrated baselines. They now share main.py's gate via
``resolve_script_calibration``.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.detection.calibration_readiness import resolve_script_calibration

WIDTH, HEIGHT = 64, 48


@pytest.fixture
def video(tmp_path: Path) -> Path:
    """A tiny clip named like a probe target: <calibrations_dir>/<stem>.json."""
    path = tmp_path / "video_entreno_x.mp4"
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (WIDTH, HEIGHT)
    )
    assert writer.isOpened()
    for _ in range(3):
        writer.write(np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8))
    writer.release()
    return path


@pytest.fixture
def calibrations(tmp_path: Path) -> Path:
    return tmp_path / "calibrations"


def write_calibration(path: Path, frame_dimensions=(48, 64)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "court_corners": [[0, 40], [40, 38], [63, 44], [1, 45]],
        "midcourt_points": [[15, 41], [45, 40]],
        "net_top_points": [[16, 22], [46, 21]],
        "frame_dimensions": list(frame_dimensions),
    }))
    return path


# --- usable / missing / waived ---------------------------------------------


def test_auto_detected_calibration_is_usable(video, calibrations, capsys):
    calib = write_calibration(calibrations / "video_entreno_x.json")

    path = resolve_script_calibration(
        str(video), None, False, calibrations_dir=calibrations,
        script_name="test_action_recognition.py",
    )

    assert path == str(calib)
    out = capsys.readouterr().out
    assert "usable           : True" in out
    assert "DEGRADED" not in out


def test_missing_calibration_exits_nonzero(video, calibrations, capsys):
    with pytest.raises(SystemExit) as exc:
        resolve_script_calibration(
            str(video), None, False, calibrations_dir=calibrations,
            script_name="test_action_recognition.py",
        )

    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "no court calibration found" in err
    assert "calibrations/video_entreno_x.json" in err
    assert "--allow-uncalibrated" in err


def test_allow_uncalibrated_flag_waives_the_gate(video, calibrations, capsys):
    path = resolve_script_calibration(
        str(video), None, True, calibrations_dir=calibrations,
        script_name="test_action_recognition.py",
    )

    # The script keeps running uncalibrated (court=None downstream).
    assert path is None
    assert "usable           : False" in capsys.readouterr().out


def test_mismatched_calibration_exits_nonzero(video, calibrations, capsys):
    # 1080p calibration on a 64x48 clip: the mask would be the wrong size.
    calib = write_calibration(calibrations / "video_entreno_x.json",
                              frame_dimensions=(1080, 1920))

    with pytest.raises(SystemExit) as exc:
        resolve_script_calibration(str(video), None, False, calibrations_dir=calibrations)

    assert exc.value.code != 0
    assert "do not fit the video" in capsys.readouterr().err
    # ... and the waiver still runs, on purpose, degraded.
    assert resolve_script_calibration(
        str(video), None, True, calibrations_dir=calibrations
    ) == str(calib)


def test_unreadable_explicit_calibration_exits_nonzero(video, calibrations, capsys):
    with pytest.raises(SystemExit):
        resolve_script_calibration(
            str(video), str(calibrations / "nope.json"), False,
            calibrations_dir=calibrations,
        )
    assert "could not be read" in capsys.readouterr().err


def test_explicit_calibration_is_not_taken_from_calibrations_dir(video, calibrations, capsys):
    # Borrowed calibration, different name: usable, but reported as not
    # stem-matched (it only works if the two views share a camera).
    calib = write_calibration(calibrations / "other_camera.json")
    path = resolve_script_calibration(
        str(video), str(calib), False, calibrations_dir=calibrations
    )

    assert path == str(calib)
    assert "stem matched: False" in capsys.readouterr().out


def test_upscaled_cache_stem_resolves_back_to_the_source_calibration(
    video, calibrations, tmp_path, capsys
):
    # ensure_1080 caches sub-1080p sources as <stem>_up<target>.mp4; a run
    # pointed at the cache must still auto-detect calibrations/<stem>.json.
    calib = write_calibration(calibrations / "video_entreno_x.json")
    cached = tmp_path / "video_entreno_x_up1080.mp4"
    cached.write_bytes(video.read_bytes())

    path = resolve_script_calibration(
        str(cached), None, False, calibrations_dir=calibrations
    )

    assert path == str(calib)
    assert "video_entreno_x.json" in capsys.readouterr().out


# --- the gate is actually wired into the probe scripts ----------------------

PROBE_SCRIPTS = [
    "test_action_recognition.py",
    "test_player_tracking.py",
    "test_pose_estimation.py",
    "test_ball_tracking.py",
    "dump_player_tracks.py",
]

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("script", PROBE_SCRIPTS)
def test_probe_script_applies_the_gate(script):
    source = (ROOT / "scripts" / script).read_text()
    assert "resolve_script_calibration" in source, (
        f"{script} loads a calibration but no longer applies the readiness gate"
    )
    assert '"--allow-uncalibrated"' in source, (
        f"{script} has no --allow-uncalibrated escape hatch"
    )


def test_main_still_owns_the_same_check():
    # main.py's behaviour is unchanged: it keeps calling the same functions
    # (now imported from the shared module) with the same flag.
    source = (ROOT / "src" / "main.py").read_text()
    assert "validate_calibration_readiness(readiness, args.allow_uncalibrated)" in source
