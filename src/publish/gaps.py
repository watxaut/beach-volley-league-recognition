"""The dead time of a match, for the owner's review: is a point missing?

    venv/bin/python -m src.publish.gaps output/<run_dir> [--video <file>]
    venv/bin/python -m src.publish.gaps --all          # every run that lacks one

The rally copy (``rallies.mp4``, src/publish/clips.py) holds only the rallies
the reconstruction found, so a rally it missed cannot be seen there. This is
the other half: ``<run_dir>/gaps.mp4`` + ``gaps.json``, every stretch the
rally copy leaves out, the whole frame scaled down, one frame in ``STEP``
(played at the same rate it is ``STEP`` times faster: 15 minutes of dead time
are watched in 5).

Like the rally copy it is written while the video is on disk, by ONE
sequential decode indexed by frame number (never a seek, AGENTS.md §9); the
index says which source frame each of its frames is. Only the review page
(src/web/review.py) reads it: nothing here is published, and a run without it
is reviewed exactly as before.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .clips import _Encoder, fit_size, load_rally_copy, rally_spans

GAPS_NAME = "gaps.mp4"
INDEX_NAME = "gaps.json"
INDEX_VERSION = 1
#: One frame in this many is kept.
STEP = 3
#: The whole frame is scaled to fit this box: enough to see a serve and a
#: rally, small enough to keep next to the diag dump.
BOX = (640, 360)
CRF = 30
#: Where the videos wait until they are archived (``make inbox``).
VIDEO_DIR = Path("resources/full_videos")


@dataclass
class GapCopy:
    """``gaps.mp4`` and which source frame each of its frames is."""

    path: Path
    fps: float
    size: Tuple[int, int]
    step: int
    #: First and last KEPT source frame of every stretch, in order.
    spans: List[Tuple[int, int]]

    def segment(self, first: int, last: int) -> Optional[Tuple[int, int, int]]:
        """The kept frames with ``first`` <= source frame <= ``last``: the
        first one's source frame, its position in the copy and how many
        follow each other there (they are ``step`` source frames apart).
        None when the copy holds none; a range over two stretches gives the
        first one's part."""
        offset = 0
        for a, b in self.spans:
            n = (b - a) // self.step + 1
            lo = max(0, -(-(first - a) // self.step))          # ceil
            hi = min(n - 1, (last - a) // self.step)
            if lo <= hi:
                return a + lo * self.step, offset + lo, hi - lo + 1
            offset += n
        return None

    def to_json(self) -> dict:
        return {"version": INDEX_VERSION, "fps": self.fps, "size": list(self.size),
                "step": self.step, "spans": [list(s) for s in self.spans],
                "frames": sum((b - a) // self.step + 1 for a, b in self.spans)}


def load_gap_copy(run_dir: Path) -> Optional[GapCopy]:
    path, index = Path(run_dir) / GAPS_NAME, Path(run_dir) / INDEX_NAME
    if not path.exists() or not index.exists():
        return None
    try:
        data = json.loads(index.read_text())
        if data.get("version") != INDEX_VERSION:
            return None
        return GapCopy(path=path, fps=float(data["fps"]),
                       size=(int(data["size"][0]), int(data["size"][1])),
                       step=int(data["step"]),
                       spans=[(int(a), int(b)) for a, b in data["spans"]])
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return None


def dead_spans(rallies: Sequence[Tuple[int, int]]) -> List[Tuple[int, Optional[int]]]:
    """The stretches between the rally stretches (inclusive), from the first
    frame to the end of the video (``None``: until it ends)."""
    out: List[Tuple[int, Optional[int]]] = []
    at = 0
    for first, last in sorted(rallies):
        if first > at:
            out.append((at, first - 1))
        at = max(at, last + 1)
    out.append((at, None))
    return out


def build_gap_copy(video: Path, run_dir: Path, rallies: Sequence[Tuple[int, int]],
                   fps: float, step: int = STEP) -> Optional[GapCopy]:
    """Write ``gaps.mp4`` + ``gaps.json`` from the run's video: one sequential
    pass over the whole video, only the kept frames are decoded to pixels."""
    import cv2

    run_dir = Path(run_dir)
    if fps <= 0 or step < 1:
        return None
    todo = dead_spans(rallies)
    cap = cv2.VideoCapture(str(video))
    try:
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if frame_w <= 0 or frame_h <= 0:
            return None
        size = fit_size(frame_w, frame_h, BOX)
        enc = _Encoder(run_dir / GAPS_NAME, size, fps, CRF, "medium")
        done: List[Tuple[int, int]] = []
        idx, k = 0, 0
        while k < len(todo):
            if not cap.grab():
                break
            first, last = todo[k]
            if idx >= first and (idx - first) % step == 0:
                ok, frame = cap.retrieve()
                if not ok:
                    break
                enc.write(cv2.resize(frame, size, interpolation=cv2.INTER_AREA))
                if done and done[-1][0] == first:
                    done[-1] = (first, idx)
                else:
                    done.append((first, idx))
            if last is not None and idx == last:
                k += 1
            idx += 1
    finally:
        cap.release()
    if not enc.close(keep=bool(done)):
        return None
    copy = GapCopy(path=run_dir / GAPS_NAME, fps=float(fps), size=size, step=step, spans=done)
    (run_dir / INDEX_NAME).write_text(json.dumps(copy.to_json(), indent=1))
    return copy


def rallies_of(run_dir: Path) -> Optional[Tuple[List[Tuple[int, int]], float]]:
    """The stretches the rally copy holds (so the two copies cover the video
    between them) and the frame rate; from the reconstruction when the run
    has no rally copy."""
    copy = load_rally_copy(run_dir)
    if copy is not None:
        return list(copy.spans), copy.fps
    try:
        recon = json.loads((Path(run_dir) / "match_reconstruction.json").read_text())
        fps = float(recon["fps"])
        return rally_spans(recon["points"], fps, recon.get("n_frames")), fps
    except (OSError, ValueError, KeyError, TypeError):
        return None


def find_video(run_dir: Path, video_dir: Path = VIDEO_DIR) -> Optional[Path]:
    path = Path(video_dir) / f"{Path(run_dir).name}.mp4"
    return path if path.is_file() else None


def make_gap_copy(run_dir: Path, video: Optional[Path] = None, say=print) -> bool:
    run_dir = Path(run_dir)
    video = Path(video) if video else find_video(run_dir)
    if video is None or not video.is_file():
        say(f"{run_dir.name}: video not on disk, no dead-time copy")
        return False
    if shutil.which("ffmpeg") is None:
        say("ffmpeg is not installed (brew install ffmpeg): no dead-time copy")
        return False
    known = rallies_of(run_dir)
    if known is None:
        say(f"{run_dir.name}: no reconstruction, no dead-time copy")
        return False
    say(f"{run_dir.name}: dead-time copy (sequential decode of {video.name}) ...")
    copy = build_gap_copy(video, run_dir, known[0], known[1])
    if copy is None:
        say(f"{run_dir.name}: the dead-time copy could not be written")
        return False
    data = copy.to_json()
    say(f"{run_dir.name}: {data['frames']} frames in {len(copy.spans)} stretches, "
        f"{copy.path.stat().st_size / 1e6:.0f} MB")
    return True


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run_dir", nargs="?", help="run directory (output/<match_key>)")
    parser.add_argument("--video", help="the run's video (default: "
                        f"{VIDEO_DIR}/<run directory name>.mp4)")
    parser.add_argument("--all", action="store_true",
                        help="every run under --output-root that has a reconstruction, "
                             "a video on disk and no dead-time copy yet")
    parser.add_argument("--output-root", default="output")
    parser.add_argument("--force", action="store_true", help="rebuild an existing copy")
    args = parser.parse_args(argv)
    if args.all:
        runs = [p for p in sorted(Path(args.output_root).iterdir())
                if (p / "match_reconstruction.json").is_file() and find_video(p)]
    elif args.run_dir:
        runs = [Path(args.run_dir)]
    else:
        parser.error("give a run directory or --all")
    ok = True
    for run in runs:
        if load_gap_copy(run) is not None and not args.force:
            print(f"{run.name}: has a dead-time copy (--force rebuilds it)")
            continue
        ok = make_gap_copy(run, Path(args.video) if args.video and not args.all else None) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
