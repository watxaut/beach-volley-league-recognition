#!/usr/bin/env python3
"""Write the video's own timestamp of every frame next to a run's diag dump.

    venv/bin/python scripts/write_frame_times.py output/<run dir>
    venv/bin/python scripts/write_frame_times.py output/<run dir> --video path.mp4

The camera drops its frame rate on its own (AGENTS.md §7): one video of
2026-10-10 runs at 25 fps for 14 minutes and at 30 after, so "frame / average
fps" is up to 50 s off the clock the video player shows. The post-run layer
reads ``frame_times.json`` when it is there and prints the player's clock; it
never decides anything with it.

No decode: the timestamps are the packets' (``ffprobe``), in presentation
order, without the ones before time zero (the decoder does not show those).
The file is refused by the reader unless it holds exactly one timestamp per
frame of the run, so a video that does not follow that rule costs nothing but
the clock.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.postrun.reconstruct import FRAME_TIMES_NAME  # noqa: E402


def packet_times(video: Path) -> List[float]:
    """Presentation timestamps (s) of the frames a decoder shows, in order."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(video)],
        check=True, capture_output=True, text=True).stdout
    times = sorted(float(line.split(",")[0]) for line in out.split()
                   if line and line.split(",")[0] not in ("", "N/A"))
    return [t for t in times if t >= 0.0]


def run_video(run_dir: Path) -> Optional[Path]:
    """The video the run read (recorded in its ``pipeline_output.json``)."""
    pipeline = run_dir / "pipeline_output.json"
    if not pipeline.exists():
        return None
    with open(pipeline) as f:
        path = (json.load(f).get("video") or {}).get("path")
    return Path(path) if path else None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run_dir", help="run directory (holds diag.jsonl)")
    parser.add_argument("--video", help="the video the run read "
                        "(default: the path in pipeline_output.json)")
    args = parser.parse_args(argv)
    run_dir = Path(args.run_dir)
    video = Path(args.video) if args.video else run_video(run_dir)
    if video is None or not video.exists():
        print(f"video not found ({video}); pass --video", file=sys.stderr)
        return 1
    times = packet_times(video)
    if not times:
        print(f"no video timestamps in {video}", file=sys.stderr)
        return 1
    out = run_dir / FRAME_TIMES_NAME
    with open(out, "w") as f:
        json.dump({"source": "ffprobe packet pts, presentation order, t >= 0",
                   "video": video.name, "n_frames": len(times),
                   "times_s": [round(t, 3) for t in times]}, f)
    print(f"{out}: {len(times)} frames, {times[-1]:.1f} s "
          f"({len(times) / times[-1]:.2f} fps on average)" if times[-1] > 0 else out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
