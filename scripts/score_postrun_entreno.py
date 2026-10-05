#!/usr/bin/env python3
"""Out-of-sample check of the post-run layer on the practice clips.

    venv/bin/python scripts/score_postrun_entreno.py output/postrun

``video_entreno_1..7`` are one drill point each, shot at a different venue
with the tripod ~2.3x higher than on the beach (AGENTS.md §7) -- nothing in
``src/postrun`` was fitted on them. Each ``<root>/entreno_<n>/diag.jsonl`` is
reconstructed with that clip's own calibration and compared with its GT
(``ground_truth/video_entreno_<n>_annotations.json``: actions keyed by court
half, A = near).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_postrun import TOLERANCE, match_touches  # noqa: E402
from src.postrun.geometry import CourtGeometry  # noqa: E402
from src.postrun.reconstruct import reconstruct  # noqa: E402
from src.postrun.stream import load_stream  # noqa: E402

SIDE = {"A": "near", "B": "far"}
#: GT vocabulary -> the match dialect ("every action that goes over is an
#: overpass"); a block has no post-run label and is scored as a touch only.
ACTION = {"freeball": "overpass"}


def load_clip_gt(index: int):
    with open(f"ground_truth/video_entreno_{index}_annotations.json") as f:
        events = json.load(f)["annotated_frames"]["actions"]["events"]
    out = []
    for e in sorted(events, key=lambda e: e["frame"]):
        action = e.get("final_action") or e.get("action")
        out.append({"frame": e["frame"], "action": ACTION.get(action, action),
                    "side": SIDE.get(e.get("player_team") or e.get("team"))})
    return out


def score_clip(index: int, root: Path):
    run = root / f"entreno_{index}"
    stream = load_stream(str(run / "diag.jsonl"))
    geometry = CourtGeometry.from_file(f"calibrations/video_entreno_{index}.json")
    recon = reconstruct(stream, geometry)
    gt = load_clip_gt(index)
    gt_serve = next((g for g in gt if g["action"] == "serve"), None)
    gt_touches = [g for g in gt if g["action"] != "serve"]
    pred = [t for p in recon["points"] for t in p["touches"]
            if t["touch_number"] > 0 and t["observed"]]
    matched = match_touches(pred, gt_touches)
    labelled = [(i, j) for i, j in matched if gt_touches[j]["action"] != "block"]
    serves = [p["serve"] for p in recon["points"]]
    serve_ok = None
    if gt_serve is not None:
        serve_ok = any(abs(sv["frame"] - gt_serve["frame"]) <= TOLERANCE
                       and sv["side"] == gt_serve["side"] for sv in serves)
    return {
        "clip": index, "points": len(recon["points"]),
        "gt_serve": None if gt_serve is None else (gt_serve["frame"], gt_serve["side"]),
        "serves": [(sv["frame"], sv["side"]) for sv in serves], "serve_ok": serve_ok,
        "pred": len(pred), "gt": len(gt_touches), "matched": len(matched),
        "action_ok": sum(pred[i]["action"] == gt_touches[j]["action"] for i, j in labelled),
        "action_n": len(labelled),
        "side_ok": sum(pred[i]["side"] == gt_touches[j]["side"] for i, j in matched),
        "net_height_m": recon["geometry"]["net_top_height_m"],
        "sequence": " ".join(f"{t['frame']}:{t['side'][0]}{t['touch_number']}:{t['action'][:4]}"
                             + ("" if t["observed"] else "?")
                             for p in recon["points"] for t in p["touches"]),
        "gt_sequence": " ".join(f"{g['frame']}:{(g['side'] or '?')[0]}:{g['action'][:4]}"
                                for g in gt),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("root", help="directory holding entreno_<n>/diag.jsonl")
    parser.add_argument("--clips", default="1,2,3,4,5,6,7")
    args = parser.parse_args()
    total = {"pred": 0, "gt": 0, "matched": 0, "action_ok": 0, "action_n": 0, "side_ok": 0}
    serve_n = serve_ok = 0
    for index in (int(c) for c in args.clips.split(",")):
        row = score_clip(index, Path(args.root))
        for k in total:
            total[k] += row[k]
        if row["serve_ok"] is not None:
            serve_n += 1
            serve_ok += bool(row["serve_ok"])
        print(f"e{index}: points {row['points']}  serve gt {row['gt_serve']} -> "
              f"{row['serves']} ok={row['serve_ok']}  touches {row['matched']}/"
              f"{row['pred']} pred, /{row['gt']} gt  action {row['action_ok']}/"
              f"{row['action_n']}  half {row['side_ok']}/{row['matched']}  "
              f"net {row['net_height_m']} m")
        print(f"     out: {row['sequence']}")
        print(f"     gt : {row['gt_sequence']}")
    m = total["matched"]
    print(f"TOTAL serves {serve_ok}/{serve_n}   precision {m}/{total['pred']} = "
          f"{m / max(total['pred'], 1):.3f}   recall {m}/{total['gt']} = "
          f"{m / max(total['gt'], 1):.3f}   action {total['action_ok']}/"
          f"{total['action_n']} = {total['action_ok'] / max(total['action_n'], 1):.3f}   "
          f"half {total['side_ok']}/{m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
