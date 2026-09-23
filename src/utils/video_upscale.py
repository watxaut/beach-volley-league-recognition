"""One-time local upscale of sub-1080p videos to 1080p.

Why this exists: every pixel-space constant in the pipeline (ball pixel-width
side signal ``attribution_width_far_px``/``near_px``, ``NEAR_NET_PX``,
``TOUCH_RISE_PX``, tracker gates in px and px/frame, ...) was measured on
1080p/30fps footage. A 720p source shrinks all of those measures by 2/3 and
silently breaks them (near balls read "far", spikes read "hard", ...).
Detection itself is unaffected (YOLO runs at a fixed imgsz), so the cheap and
safe fix is to put sub-1080p sources back into the geometry the constants were
tuned in, once, at ingest time.

Behaviour:
- sources already at/above the target height pass through untouched (so all
  GT-validated 1080p videos keep byte-identical behaviour);
- otherwise the video is transcoded ONCE (Lanczos, x264 CRF 18, exact frame
  count preserved via ``-vsync 0``) to ``<stem>_up<target>.mp4`` next to the
  source, and that cached file is reused on every later run;
- the transcode lands via an atomic rename, so an interrupted run can never
  leave a truncated file that a later run would trust; the cached file is only
  accepted after a decoded-frame-count parity check against the source.

Not handled here (known, deferred): the source fps is preserved as-is. The
2026-09-20 match recording is ~25.7fps effective vs the 30fps entreno tuning;
frames-based windows therefore span ~17% more wall-time. Revisit only if
contact-window misses show up on real footage.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Union

import cv2

logger = logging.getLogger(__name__)


def _frame_size(path: Path) -> tuple:
    """(width, height) of the video, via container metadata."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return width, height


def _count_decoded_frames(path: Path) -> int:
    """Decode-count frames (container metadata lies on VFR phone footage)."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {path}")
    count = 0
    while True:
        ret, _ = cap.read()
        if not ret:
            break
        count += 1
    cap.release()
    return count


def _transcode(source: Path, output: Path, target_height: int) -> None:
    """Lanczos-upscale ``source`` to ``target_height`` into ``output``.

    ``-vsync 0`` keeps every source frame exactly once (no CFR dup/drop on
    VFR input), so the pipeline's frame indices stay faithful to the original
    recording. Audio is stream-copied; the pipeline never reads it but the
    cached file stays watchable for GT annotation.
    """
    scale = f"scale=-2:{target_height}:flags=lanczos"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-vf", scale,
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-vsync", "0",
        "-map", "0:v:0", "-map", "0:a?",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output),
    ]
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffmpeg not found on PATH; it is required to upscale sub-1080p "
            "videos. Install ffmpeg or pre-upscale the video manually."
        ) from exc


def ensure_1080(video_path: Union[str, Path], target_height: int = 1080) -> Path:
    """Return a video path whose height is at least ``target_height``.

    Sub-1080p sources are transcoded once to ``<stem>_up<target>.mp4`` next to
    the original and the cached file is returned on every later call. Sources
    already at/above the target are returned unchanged. ``target_height <= 0``
    disables the mechanism entirely.

    Returns the ORIGINAL path when no upscale is needed, so 1080p videos are
    byte-for-byte unaffected (entreno baselines).
    """
    path = Path(video_path)
    if target_height is None or target_height <= 0:
        return path

    width, height = _frame_size(path)
    if height >= target_height:
        return path

    upscaled = path.with_name(f"{path.stem}_up{target_height}{path.suffix}")
    if upscaled.exists():
        logger.info(
            "Using cached upscaled video: %s (source %dx%d)",
            upscaled.name, width, height,
        )
        return upscaled

    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            f"Video is {width}x{height}, below the {target_height}p the "
            "pipeline's pixel constants are tuned for, and ffmpeg is not "
            "available to upscale it. Install ffmpeg or pass a pre-upscaled "
            "video / set config 'upscale_to_height': 0 to override."
        )

    logger.info(
        "Video is %dx%d, below the %dp the px constants are tuned for -- "
        "upscaling once to %s (Lanczos, CRF 18; cached for future runs)",
        width, height, target_height, upscaled.name,
    )
    part = upscaled.with_name(f"{upscaled.stem}.part{upscaled.suffix}")
    try:
        _transcode(path, part, target_height)

        # Integrity gate: the cache must hold exactly the source's frames
        # before it is allowed to shadow the original on future runs.
        src_frames = _count_decoded_frames(path)
        out_frames = _count_decoded_frames(part)
        if src_frames != out_frames:
            part.unlink(missing_ok=True)
            raise RuntimeError(
                f"Upscaled video frame-count mismatch: source {src_frames}, "
                f"output {out_frames}. Cache not written."
            )
        os.replace(part, upscaled)  # atomic: cache implies complete+verified
    finally:
        part.unlink(missing_ok=True)

    out_w, out_h = _frame_size(upscaled)
    logger.info(
        "Upscaled video ready: %s (%dx%d, %d frames, verified)",
        upscaled.name, out_w, out_h, out_frames,
    )
    return upscaled
