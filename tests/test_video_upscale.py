"""Tests for the one-time sub-1080p upscale cache (src/utils/video_upscale.py)."""

import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.utils.video_upscale import ensure_1080

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH"
)


def _write_video(path: Path, width: int, height: int, frames: int = 10) -> Path:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 30.0, (width, height))
    assert writer.isOpened()
    for i in range(frames):
        frame = np.full((height, width, 3), i * 20 % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return path


def _dimensions(path: Path):
    cap = cv2.VideoCapture(str(path))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return w, h


def test_subtarget_video_upscaled_with_frame_count_preserved(tmp_path):
    src = _write_video(tmp_path / "tiny.mp4", 128, 72, frames=10)
    out = ensure_1080(src, target_height=144)
    assert out.name == "tiny_up144.mp4"
    assert _dimensions(out) == (256, 144)
    # every source frame must survive the transcode (-vsync 0)
    assert _decoded_frames(out) == 10
    # the atomic .part intermediate must not linger
    assert not list(tmp_path.glob("*.part*"))


def _decoded_frames(path):
    cap = cv2.VideoCapture(str(path))
    n = 0
    while True:
        ret, _ = cap.read()
        if not ret:
            break
        n += 1
    cap.release()
    return n


def test_cached_upscale_reused_without_reencode(tmp_path, monkeypatch):
    src = _write_video(tmp_path / "tiny.mp4", 128, 72, frames=8)
    first = ensure_1080(src, target_height=144)
    mtime_first = first.stat().st_mtime_ns

    # a second call must be a pure cache hit: any ffmpeg invocation fails the test
    def _boom(*args, **kwargs):
        raise AssertionError("ffmpeg ran on a cache hit")
    monkeypatch.setattr(shutil, "which", _boom)
    second = ensure_1080(src, target_height=144)
    assert second == first
    assert first.stat().st_mtime_ns == mtime_first


def test_at_target_video_passthrough_untouched(tmp_path):
    src = _write_video(tmp_path / "full.mp4", 256, 144, frames=6)
    out = ensure_1080(src, target_height=144)
    assert out == src  # same path, no new file written
    assert not list(tmp_path.glob("*_up*"))


def test_disabled_returns_original(tmp_path):
    src = _write_video(tmp_path / "tiny.mp4", 128, 72, frames=4)
    assert ensure_1080(src, target_height=0) == src
    assert ensure_1080(src, target_height=None) == src
    assert not list(tmp_path.glob("*_up*"))
