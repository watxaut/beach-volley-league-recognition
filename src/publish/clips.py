"""Attack clips for the player page: pick an attack on the map, watch it.

A clip is the second before a credited attack and the 1.5 s after it, cropped
around the net, scaled into 640x480, H.264, no sound: about 0.3 MB.

The video is not kept (AGENTS.md §13) and the attacks of a match change when
the post-run rules do, so the clips are cut in two steps:

1. ``<run_dir>/rallies.mp4`` + ``rallies.json`` -- every rally of the match
   in that crop, written while the video is on disk. The video is decoded
   SEQUENTIALLY and indexed by frame number, never positioned with a seek
   (-28..+30 frames off on this VFR camera, AGENTS.md §9); the index says
   which source frame each frame of the copy is.
2. ``<run_dir>/clips/<frame>.mp4`` -- cut from that copy (decoded from its
   first frame again), so a re-publish after a rules change gets a clip for
   an attack the first publish never saw, without the video.

KEEP ``rallies.mp4`` next to the diag dump of every published match. Encoding
needs the ``ffmpeg`` binary; without it a publish carries no clips.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

#: A clip runs from this long before the contact to this long after it.
BEFORE_S, AFTER_S = 1.0, 1.5
#: The rally copy holds each point from this long before its serve to this
#: long after its end: every clip of an attack inside the point fits.
RALLY_PAD_S = (1.0, 2.0)
#: A clip is scaled to fit this box (never enlarged).
BOX = (640, 480)
#: The crop is this many net heights tall: one above the tape (the set), the
#: net itself, one below its ground line (the near half).
NET_HEIGHTS = 3.0
#: x264 quality: the copy is the source of every later cut, a clip is what a
#: phone downloads.
RALLY_CRF, CLIP_CRF = 25, 28

RALLIES_NAME = "rallies.mp4"
INDEX_NAME = "rallies.json"
CLIPS_DIR = "clips"
MANIFEST_NAME = "index.json"
INDEX_VERSION = 1

Box = Tuple[int, int, int, int]            # x, y, width, height
Say = Callable[[str], None]


def _say(text: str) -> None:
    print(text, flush=True)


# --------------------------------------------------------------------------- #
# geometry (pure)
# --------------------------------------------------------------------------- #

def crop_box(calibration: Optional[Dict[str, Any]], frame_w: int, frame_h: int) -> Box:
    """The part of the frame a clip shows.

    Sized by how big the net projects, so it follows the camera's distance
    and height on any venue: ``NET_HEIGHTS`` net heights tall, as wide as the
    clip box asks, centred on the net, clamped to the frame. The outer
    corners of the near half fall outside on purpose: a box that holds the
    whole court is the whole frame, with the players a third of the size.
    Without the net clicks the whole frame is used.
    """
    whole = (0, 0, frame_w - frame_w % 2, frame_h - frame_h % 2)
    try:
        tape = [(float(x), float(y)) for x, y in calibration["net_top_points"]]
        ground = [(float(x), float(y)) for x, y in calibration["midcourt_points"]]
        dims = calibration.get("frame_dimensions") or (frame_h, frame_w)
        sx, sy = frame_w / float(dims[1]), frame_h / float(dims[0])
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return whole
    if len(tape) < 2 or len(ground) < 2:
        return whole
    top = sum(y for _, y in tape) / len(tape) * sy
    base = sum(y for _, y in ground) / len(ground) * sy
    centre = sum(x for x, _ in tape + ground) / (len(tape) + len(ground)) * sx
    net = base - top
    if net <= 0:
        return whole
    margin = net * (NET_HEIGHTS - 1.0) / 2.0
    width = NET_HEIGHTS * net * BOX[0] / BOX[1]
    x0, x1 = max(0.0, centre - width / 2.0), min(float(frame_w), centre + width / 2.0)
    y0, y1 = max(0.0, top - margin), min(float(frame_h), base + margin)
    x, y = int(round(x0)), int(round(y0))
    w, h = int(x1 - x) // 2 * 2, int(y1 - y) // 2 * 2
    return (x, y, w, h) if w >= 2 and h >= 2 else whole


def fit_size(width: int, height: int, box: Tuple[int, int] = BOX) -> Tuple[int, int]:
    """``width`` x ``height`` scaled to fit ``box`` (never enlarged), even."""
    scale = min(box[0] / width, box[1] / height, 1.0)
    return (max(2, int(round(width * scale / 2.0)) * 2),
            max(2, int(round(height * scale / 2.0)) * 2))


def rally_spans(points: Sequence[Dict[str, Any]], fps: float,
                n_frames: Optional[int] = None) -> List[Tuple[int, int]]:
    """First and last source frame of every stretch the copy keeps (inclusive,
    in order, overlaps merged): each point with ``RALLY_PAD_S`` around it."""
    before, after = (int(round(s * fps)) for s in RALLY_PAD_S)
    spans: List[List[int]] = []
    for first, last in sorted((int(p["start_frame"]) - before, int(p["end_frame"]) + after)
                              for p in points):
        first = max(0, first)
        if n_frames:
            last = min(last, int(n_frames) - 1)
        if last < first:
            continue
        if spans and first <= spans[-1][1] + 1:
            spans[-1][1] = max(spans[-1][1], last)
        else:
            spans.append([first, last])
    return [(a, b) for a, b in spans]


@dataclass
class RallyCopy:
    """``rallies.mp4`` and which source frame each of its frames is."""

    path: Path
    fps: float
    size: Tuple[int, int]
    crop: Box
    spans: List[Tuple[int, int]]

    def window(self, frame: int) -> Optional[Tuple[int, int]]:
        """First and last position IN THE COPY of the clip of an attack at
        source ``frame``; None when the copy does not hold that frame. A clip
        never leaves its own stretch, so it is shorter at a stretch's edge."""
        before, after = int(round(BEFORE_S * self.fps)), int(round(AFTER_S * self.fps))
        offset = 0
        for first, last in self.spans:
            if first <= frame <= last:
                return (offset + max(first, frame - before) - first,
                        offset + min(last, frame + after) - first)
            offset += last - first + 1
        return None

    def to_json(self) -> Dict[str, Any]:
        return {"version": INDEX_VERSION, "fps": self.fps, "size": list(self.size),
                "crop": list(self.crop), "spans": [list(s) for s in self.spans],
                "frames": sum(b - a + 1 for a, b in self.spans)}


def load_rally_copy(run_dir: Path) -> Optional[RallyCopy]:
    path, index = Path(run_dir) / RALLIES_NAME, Path(run_dir) / INDEX_NAME
    if not path.exists() or not index.exists():
        return None
    try:
        data = json.loads(index.read_text())
        if data.get("version") != INDEX_VERSION:
            return None
        return RallyCopy(path=path, fps=float(data["fps"]),
                         size=(int(data["size"][0]), int(data["size"][1])),
                         crop=tuple(int(v) for v in data["crop"]),      # type: ignore[arg-type]
                         spans=[(int(a), int(b)) for a, b in data["spans"]])
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return None


# --------------------------------------------------------------------------- #
# encoding
# --------------------------------------------------------------------------- #

class _Encoder:
    """BGR frames in, one H.264 MP4 out. The file appears under its name only
    when ffmpeg finished cleanly (an interrupted cut leaves nothing behind)."""

    def __init__(self, path: Path, size: Tuple[int, int], fps: float, crf: int,
                 preset: str) -> None:
        self.path = Path(path)
        self.part = self.path.with_name(self.path.name + ".part")
        self.proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
             "-s", f"{size[0]}x{size[1]}", "-r", f"{fps:.6f}", "-i", "-", "-an",
             "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", "-map_metadata", "-1", "-fflags", "+bitexact",
             "-flags:v", "+bitexact", "-f", "mp4", str(self.part)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        self.broken = False

    def write(self, frame) -> None:
        if self.broken:
            return
        try:
            self.proc.stdin.write(frame.tobytes())
        except (BrokenPipeError, OSError):
            self.broken = True

    def close(self, keep: bool = True) -> bool:
        _, err = self.proc.communicate()
        ok = keep and not self.broken and self.proc.returncode == 0 and self.part.exists()
        if ok:
            self.part.replace(self.path)
        else:
            self.part.unlink(missing_ok=True)
            if keep:
                _say(f"  ffmpeg failed on {self.path.name}: {(err or b'').decode(errors='replace').strip()[:200]}")
        return ok


def build_rally_copy(video: Path, run_dir: Path, spans: Sequence[Tuple[int, int]],
                     calibration: Optional[Dict[str, Any]], fps: float) -> Optional[RallyCopy]:
    """Write ``rallies.mp4`` + ``rallies.json`` from the run's video: one
    sequential pass up to the last rally, only the kept frames are decoded to
    pixels. A video that ends early gives a copy of what it had."""
    import cv2

    run_dir = Path(run_dir)
    if not spans or fps <= 0:
        return None
    cap = cv2.VideoCapture(str(video))
    try:
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if frame_w <= 0 or frame_h <= 0:
            return None
        x, y, w, h = crop = crop_box(calibration, frame_w, frame_h)
        size = fit_size(w, h)
        enc = _Encoder(run_dir / RALLIES_NAME, size, fps, RALLY_CRF, "slow")
        done: List[Tuple[int, int]] = []
        idx, k = 0, 0
        while k < len(spans):
            if not cap.grab():
                break
            first, last = spans[k]
            if idx >= first:
                ok, frame = cap.retrieve()
                if not ok:
                    break
                enc.write(cv2.resize(frame[y:y + h, x:x + w], size, interpolation=cv2.INTER_AREA))
                if done and done[-1][0] == first:
                    done[-1] = (first, idx)
                else:
                    done.append((first, idx))
                if idx == last:
                    k += 1
            idx += 1
    finally:
        cap.release()
    if not enc.close(keep=bool(done)):
        return None
    copy = RallyCopy(path=run_dir / RALLIES_NAME, fps=float(fps), size=size, crop=crop, spans=done)
    (run_dir / INDEX_NAME).write_text(json.dumps(copy.to_json(), indent=1))
    return copy


def cut_clips(copy: RallyCopy, frames: Iterable[int], out_dir: Path) -> Dict[int, Path]:
    """``<out_dir>/<frame>.mp4`` for every attack frame the copy holds: one
    sequential pass over the copy, each clip encoded as its frames go by."""
    import cv2

    wanted = {int(f): w for f in frames if (w := copy.window(int(f))) is not None}
    if not wanted:
        return {}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    starts = sorted(wanted, key=lambda f: wanted[f][0])
    last = max(w[1] for w in wanted.values())
    running: Dict[int, _Encoder] = {}
    made: Dict[int, Path] = {}
    cap = cv2.VideoCapture(str(copy.path))
    try:
        pos, nxt = 0, 0
        while pos <= last:
            if not cap.grab():
                break
            while nxt < len(starts) and wanted[starts[nxt]][0] == pos:
                f = starts[nxt]
                running[f] = _Encoder(out_dir / f"{f}.mp4", copy.size, copy.fps, CLIP_CRF, "slow")
                nxt += 1
            if running:
                ok, frame = cap.retrieve()
                if not ok:
                    break
                for f in list(running):
                    running[f].write(frame)
                    if wanted[f][1] == pos:
                        if running.pop(f).close():
                            made[f] = out_dir / f"{f}.mp4"
            pos += 1
    finally:
        cap.release()
        for enc in running.values():           # the copy ended inside these
            enc.close(keep=False)
    return made


# --------------------------------------------------------------------------- #
# the publish step
# --------------------------------------------------------------------------- #

def _stamp(copy: RallyCopy) -> str:
    """What a cut depends on: the copy and the clip settings."""
    index = copy.path.with_name(INDEX_NAME)
    body = json.dumps([copy.to_json(), index.stat().st_mtime_ns, copy.path.stat().st_size,
                       BEFORE_S, AFTER_S, CLIP_CRF], sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _local_clips(clips_dir: Path, frames: Iterable[int]) -> Dict[int, Path]:
    return {f: clips_dir / f"{f}.mp4" for f in frames if (clips_dir / f"{f}.mp4").exists()}


def make_attack_clips(run_dir: Path, frames: Iterable[int], *,
                      points: Sequence[Dict[str, Any]], fps: float,
                      video: Optional[Path] = None,
                      calibration: Optional[Dict[str, Any]] = None,
                      n_frames: Optional[int] = None, say: Say = _say) -> Dict[int, Path]:
    """Attack frame -> its clip, for every attack that has one after this call.

    The rally copy is (re)built only when it does not hold every attack and
    the video is on disk; a clip is cut only when it is missing or was cut
    from another copy, so re-publishing an unchanged match changes no file.
    Clips no attack points at any more are removed from the run directory.
    """
    run_dir = Path(run_dir)
    frames = sorted({int(f) for f in frames})
    clips_dir = run_dir / CLIPS_DIR
    if not frames:
        return {}
    if shutil.which("ffmpeg") is None:
        kept = _local_clips(clips_dir, frames)
        say(f"ffmpeg is not installed (brew install ffmpeg): no attack clip cut, {len(kept)} kept")
        return kept

    copy = load_rally_copy(run_dir)
    missing = [f for f in frames if copy is None or copy.window(f) is None]
    if missing and video is not None and Path(video).exists():
        say(f"rally copy for the attack clips (sequential decode of {Path(video).name}) ...")
        copy = build_rally_copy(Path(video), run_dir, rally_spans(points, fps, n_frames),
                                calibration, fps) or load_rally_copy(run_dir)
    if copy is None:
        kept = _local_clips(clips_dir, frames)
        say("video not on disk and no rally copy: "
            + (f"keeping the {len(kept)} attack clips of an earlier publish" if kept
               else "no attack clips"))
        return kept

    stamp = _stamp(copy)
    try:
        manifest = json.loads((clips_dir / MANIFEST_NAME).read_text())
    except (OSError, ValueError):
        manifest = {}
    cut_before = manifest.get("clips") or {} if manifest.get("stamp") == stamp else {}
    have = {f: p for f, p in _local_clips(clips_dir, frames).items()
            if cut_before.get(str(f)) == list(copy.window(f) or ())}
    todo = [f for f in frames if f not in have]
    made = cut_clips(copy, todo, clips_dir) if todo else {}
    clips = {**have, **made}

    if clips_dir.exists():
        for stale in clips_dir.glob("*.mp4"):
            if not (stale.stem.isdigit() and int(stale.stem) in clips):
                stale.unlink()
        (clips_dir / MANIFEST_NAME).write_text(json.dumps(
            {"stamp": stamp, "clips": {str(f): list(copy.window(f) or ()) for f in sorted(clips)}},
            indent=1))
    without = len(frames) - len(clips)
    say(f"attack clips: {len(clips)} of {len(frames)} attacks ({len(made)} cut now"
        + (f"; {without} outside the rally copy, the video is needed for them" if without else "")
        + ")")
    return clips


def storage_path(match_key: str, frame: int, clip: Path) -> str:
    """Where a clip lives in the media bucket. The name carries the content,
    so a path never changes what it shows and an upload is needed only once."""
    digest = hashlib.sha256(Path(clip).read_bytes()).hexdigest()[:12]
    return f"{CLIPS_DIR}/{match_key}/{int(frame)}-{digest}.mp4"


def local_clip(run_dir: Path, path: str) -> Optional[Path]:
    """The file in the run directory a storage path was made from, when it
    still is that file."""
    name = Path(path).name
    frame, _, rest = name.partition("-")
    local = Path(run_dir) / CLIPS_DIR / f"{frame}.mp4"
    if not frame.isdigit() or not local.exists():
        return None
    digest = hashlib.sha256(local.read_bytes()).hexdigest()[:12]
    return local if rest == f"{digest}.mp4" else None
