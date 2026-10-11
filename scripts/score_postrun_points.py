#!/usr/bin/env python3
"""Score a post-run reconstruction against an owner SCORE TABLE.

    venv/bin/python scripts/score_postrun_points.py \
        output/20261010_1100_vall_dhebron_jesus_sara_joan_loida \
        ground_truth/20261010_1100_vall_dhebron_points.json

A match without contact-level GT can still be scored when the owner wrote the
running score with the time of every point (``match-points-v2``: serve time on
the video player's clock, serving team, winner). Reports the points found,
missed and invented, the serving team, the winners, the final score and the
side switches. Add ``--sweep`` to move every serve / rally constant one at a
time and see which rows lose a point or a winner (needs the run's diag dump).

Points are paired by serve time, so the run needs ``frame_times.json``
(``scripts/write_frame_times.py``): on frame / average fps a camera that
changed its rate is up to 50 s off and nothing pairs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

#: The owner writes whole seconds, read off a player; a far serve's launch
#: is dated from the track's birth (up to 15 frames early).
TOLERANCE_S = 4.0


def pair_points(recon: List[Dict[str, Any]], gt: List[Dict[str, Any]],
                tolerance_s: float = TOLERANCE_S) -> Dict[int, int]:
    """recon index -> gt index, 1:1, nearest serve time first."""
    pairs = sorted(
        (abs(r["start_time_s"] - g["serve_time_s"]), i, j)
        for i, r in enumerate(recon) for j, g in enumerate(gt)
        if abs(r["start_time_s"] - g["serve_time_s"]) <= tolerance_s)
    out: Dict[int, int] = {}
    used = set()
    for _, i, j in pairs:
        if i in out or j in used:
            continue
        out[i] = j
        used.add(j)
    return out


def score_points(recon: Dict[str, Any], gt: Dict[str, Any],
                 tolerance_s: float = TOLERANCE_S) -> Dict[str, Any]:
    points, truth = recon["points"], gt["points"]
    pairing = pair_points(points, truth, tolerance_s)
    found = set(pairing.values())
    serve_ok = sum(points[i]["serve"]["team"] == truth[j]["serve_team"]
                   for i, j in pairing.items())
    wrong = [truth[j]["point"] for i, j in sorted(pairing.items())
             if points[i]["winner"] != truth[j]["winner"]]
    return {
        "recon": len(points), "gt": len(truth), "matched": len(pairing),
        "false": [p["point"] for i, p in enumerate(points) if i not in pairing],
        "missed": [g["point"] for j, g in enumerate(truth) if j not in found],
        "serve_team_ok": serve_ok,
        "winners_ok": len(pairing) - len(wrong), "winners_wrong": wrong,
        "final_score": recon["checks"]["final_score"], "gt_final_score": gt["final_score"],
        "switches": recon["checks"]["side_switch_after_point"],
        "gt_switches": gt["side_switch_after_point"],
    }


def summarise(s: Dict[str, Any]) -> str:
    return (f"points {s['recon']:>2} found {s['matched']:>2}/{s['gt']}  false {s['false']}  "
            f"missed {s['missed']}  serve-team {s['serve_team_ok']}/{s['matched']}  "
            f"winners {s['winners_ok']}/{s['matched']} wrong {s['winners_wrong']}  "
            f"final {s['final_score']}  switches {s['switches']}")


def _sweep(run_dir: Path, gt: Dict[str, Any], tolerance_s: float) -> None:
    from src.postrun import ball_flights, rallies, touches
    from src.postrun.geometry import CourtGeometry
    from src.postrun.reconstruct import FRAME_TIMES_NAME, load_frame_times, reconstruct
    from src.postrun.stream import load_stream
    from sweep_postrun import SWEEP

    with open(run_dir / "pipeline_output.json") as f:
        video = json.load(f).get("video") or {}
    stream = load_stream(str(run_dir / "diag.jsonl"), fps=video.get("fps"))
    stream.frame_times = load_frame_times(run_dir / FRAME_TIMES_NAME, stream.n_frames)
    geometry = CourtGeometry.from_file(
        (video.get("calibration_readiness") or {}).get("calibration_path"))
    size = (int(video.get("width") or 1920), int(video.get("height") or 1080))

    def run() -> str:
        recon = json.loads(json.dumps(reconstruct(stream, geometry, frame_size=size)))
        return summarise(score_points(recon, gt, tolerance_s))

    print(f"{'shipped':<34} {run()}")
    for module, name, values in SWEEP:
        if module not in (rallies, ball_flights, touches):
            continue
        shipped = getattr(module, name)
        for value in values:
            setattr(module, name, value)
            try:
                line = run()
            finally:
                setattr(module, name, shipped)
            print(f"{name + '=' + str(value):<34.34} {line}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run_dir", help="run directory (match_reconstruction.json; "
                        "diag.jsonl + pipeline_output.json for --sweep)")
    parser.add_argument("points_gt", help="owner score table (match-points-v2)")
    parser.add_argument("--tolerance", type=float, default=TOLERANCE_S,
                        help="seconds between a point's serve and the owner's time")
    parser.add_argument("--sweep", action="store_true",
                        help="re-reconstruct with each constant moved, one at a time")
    args = parser.parse_args(argv)
    run_dir = Path(args.run_dir)
    with open(args.points_gt) as f:
        gt = json.load(f)
    if args.sweep:
        _sweep(run_dir, gt, args.tolerance)
        return 0
    with open(run_dir / "match_reconstruction.json") as f:
        recon = json.load(f)
    if recon.get("clock") != "video":
        print("warning: the run has no frame_times.json -- its times are frame / average "
              "fps and may not pair with the owner's", file=sys.stderr)
    score = score_points(recon, gt, args.tolerance)
    print(summarise(score))
    print(f"owner: final {score['gt_final_score']}  switches {score['gt_switches']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
