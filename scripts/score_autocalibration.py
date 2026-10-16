#!/usr/bin/env python3
"""Score the automatic court calibration on every video that has a manual one.

    venv/bin/python scripts/score_autocalibration.py            # all views
    venv/bin/python scripts/score_autocalibration.py --views 20261010_1100_vall_dhebron_jesus_sara_joan_loida

For each view: the 8 points of ``scripts/auto_calibrate.py`` against the
owner's clicks (the quantities the post-run layer reads), then what the match
becomes when the finished run is reconstructed with them instead -- against
the owner's GT where there is one, and point by point against the manual
reconstruction everywhere. Nothing is written into a run directory; plates,
overlays and the 8-point sheets go to ``output/auto_calibration/<view>/``.

The clicks are not ground truth (``docs/auto_calibration.md``): a difference
is a place to LOOK at on the sheet, and the bar is what the match becomes.
The causal pass is not re-run, so this is the post-run half of the bar only.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.detection import court_autocalibration as ac  # noqa: E402
from probe_calibration_sensitivity import (compare as compare_runs, digest_of,  # noqa: E402
                                           reconstruct_run, run_inputs)
from score_postrun import (GT_CONTACTS, GT_POINTS, load_gt, match_touches,  # noqa: E402
                           score_reconstruction)
from score_postrun_entreno import load_clip_gt  # noqa: E402
from score_postrun_points import score_points  # noqa: E402

OUT = ROOT / "output" / "auto_calibration"

#: view -> video, the runs calibrated by that view's file, the owner GT of each.
#: ``dev`` = the detector was developed looking at this view.
VIEWS: Dict[str, Dict[str, Any]] = {
    "20260920_match_ari_joan_lost": {
        "video": "resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4", "dev": True,
        "runs": [("output/postrun/20260920_match", "contacts")]},
    "20261010_1000_vall_dhebron_jesus_sara_joan_loida": {
        "video": "resources/full_videos/20261010_1000_vall_dhebron_jesus_sara_joan_loida.mp4",
        "dev": True,
        "runs": [("output/20261010_1000_vall_dhebron_jesus_sara_joan_loida", None)]},
    "20261010_1100_vall_dhebron_jesus_sara_joan_loida": {
        "video": "resources/full_videos/20261010_1100_vall_dhebron_jesus_sara_joan_loida.mp4",
        "dev": False,
        "runs": [("output/20261010_1100_vall_dhebron_jesus_sara_joan_loida",
                  "ground_truth/20261010_1100_vall_dhebron_points.json")]},
    "20261010_1200_vall_dhebron_jesus_sara_joan_loida": {
        "video": "resources/full_videos/20261010_1200_vall_dhebron_jesus_sara_joan_loida.mp4",
        "dev": False,
        "runs": [("output/20261010_1200_vall_dhebron_jesus_sara_joan_loida", None)]},
    "20261010_1230_vall_dhebron_jesus_sara_joan_loida": {
        "video": "resources/full_videos/20261010_1230_vall_dhebron_jesus_sara_joan_loida.mp4",
        "dev": False, "runs": []},
    # masnou (beach, BLACK tape, low tripod): the court is found by lightness
    "20261012_1130_masnou_loida_joan_pere_aitana": {
        "video": "resources/full_videos/20261012_1130_masnou_loida_joan_pere_aitana.mp4",
        "dev": True,
        "runs": [("output/20261012_1130_masnou_loida_joan_pere_aitana", None)]},
    "20261012_1200_masnou_loida_joan_pere_aitana": {
        "video": "resources/full_videos/20261012_1200_masnou_loida_joan_pere_aitana.mp4",
        "dev": True,
        "runs": [("output/20261012_1200_masnou_loida_joan_pere_aitana", None)]},
    "video_entreno_3": {
        "video": "resources/video_entreno_3.mp4", "dev": True,
        "runs": [(f"output/postrun/entreno_{i}", f"clip:{i}") for i in range(1, 8)]},
}


def plate_of(view: str, video: str) -> Any:
    cached = OUT / view / "plate.png"
    if cached.exists():
        return cv2.imread(str(cached))
    plate = ac.median_plate(ac.read_frames(ac.ensure_1080(ROOT / video)))
    cached.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(cached), plate)
    return plate


def clip_score(recon: Dict[str, Any], index: int) -> Dict[str, Any]:
    """``score_postrun_entreno.score_clip`` for a reconstruction already made."""
    gt = load_clip_gt(index)
    gt_serve = next((g for g in gt if g["action"] == "serve"), None)
    gt_touches = [g for g in gt if g["action"] != "serve"]
    pred = [t for p in recon["points"] for t in p["touches"]
            if t["touch_number"] > 0 and t["observed"]]
    matched = match_touches(pred, gt_touches)
    labelled = [(i, j) for i, j in matched if gt_touches[j]["action"] != "block"]
    serve_ok = None
    if gt_serve is not None:
        serve_ok = any(abs(p["serve"]["frame"] - gt_serve["frame"]) <= 15
                       and p["serve"]["side"] == gt_serve["side"] for p in recon["points"])
    return {"serve_ok": serve_ok, "pred": len(pred), "gt": len(gt_touches),
            "matched": len(matched), "action_n": len(labelled),
            "action_ok": sum(pred[i]["action"] == gt_touches[j]["action"] for i, j in labelled)}


def gt_score(recon: Dict[str, Any], gt_kind: Optional[str]) -> Optional[Dict[str, Any]]:
    if gt_kind is None:
        return None
    if gt_kind == "contacts":
        s = score_reconstruction(recon, load_gt(str(ROOT / GT_CONTACTS), str(ROOT / GT_POINTS)))
        t = s["touches"]
        return {"points": f"{s['points']['matched']}/{s['points']['gt']}",
                "false": s["points"]["false"],
                "winners": f"{s['winners']['ok']}/{s['winners']['n']}",
                "precision": round(t.get("matched", 0) / max(t.get("pred", 0), 1), 3),
                "recall": round(t.get("matched", 0) / max(t.get("gt", 0), 1), 3),
                "action": round(t.get("action_ok", 0) / max(t.get("action_n", 0), 1), 3),
                "half": round(t.get("side_ok", 0) / max(t.get("matched", 0), 1), 3),
                "rule_breaks": sum(s["rules"].values())}
    if gt_kind.startswith("clip:"):
        return clip_score(recon, int(gt_kind.split(":")[1]))
    s = score_points(recon, json.loads((ROOT / gt_kind).read_text()))
    return {"points": f"{s['matched']}/{s['gt']}", "false": len(s["false"]),
            "missed": s["missed"], "serve_team": f"{s['serve_team_ok']}/{s['matched']}",
            "winners": f"{s['winners_ok']}/{s['matched']}", "wrong": s["winners_wrong"]}


def score_view(view: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    plate = plate_of(view, spec["video"])
    # the camera's focal length from every OTHER calibration on disk
    focals = ac.focal_priors(ROOT / "calibrations", plate.shape[1], plate.shape[0],
                             exclude_stem=view)
    result = ac.detect(plate, focals)
    manual_path = ROOT / "calibrations" / f"{view}.json"
    manual = json.loads(manual_path.read_text()) if manual_path.exists() else None
    out_dir = OUT / view
    out_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_dir / "auto_overlay.jpg"), ac.draw(plate, result, manual))
    report: Dict[str, Any] = {"view": view, "dev": spec["dev"], "accepted": result.accepted,
                              "reasons": result.reasons, "checks": ac.jsonable(result.checks),
                              "points": result.points}
    if result.points is None:
        return report
    cv2.imwrite(str(out_dir / "auto_points.jpg"), ac.contact_sheet(plate, result.points, manual))
    (out_dir / "auto_calibration.json").write_text(json.dumps(report, indent=1))
    if manual is None:
        return report
    report["vs_manual"] = ac.compare(result.points, manual)
    report["runs"] = []
    for run, gt_kind in spec["runs"]:
        if not (ROOT / run / "diag.jsonl").exists():
            continue
        logging.disable(logging.CRITICAL)
        inputs = run_inputs(ROOT / run, str(manual_path))
        by_hand = reconstruct_run(inputs, manual)
        by_auto = reconstruct_run(inputs, result.points)
        logging.disable(logging.NOTSET)
        diff = compare_runs(digest_of(by_hand), digest_of(by_auto))
        report["runs"].append({
            "run": run, "manual_score": by_hand["checks"]["final_score"],
            "auto_score": by_auto["checks"]["final_score"],
            "points_manual": len(by_hand["points"]), "diff": diff,
            "gt_manual": gt_score(by_hand, gt_kind), "gt_auto": gt_score(by_auto, gt_kind)})
    return report


def format_view(r: Dict[str, Any]) -> str:
    lines = [f"== {r['view']}  ({'dev' if r['dev'] else 'HELD OUT'})   "
             f"accepted: {r['accepted']}" + ("" if r["accepted"] else f"   {r['reasons']}")]
    v = r.get("vs_manual")
    if v:
        c = v["corner_delta_px"]
        lines.append(
            "   vs clicks  far L {0} R {1}  near R {2} L {3}   widths far {4:+.1f} % near {5:+.1f} %"
            "   rows far {6:+.1f} near {7:+.1f} px".format(
                c["far_left"], c["far_right"], c["near_right"], c["near_left"],
                v["far_width_frac"] * 100, v["near_width_frac"] * 100,
                v["far_row_px"], v["near_row_px"]))
        lines.append(f"              under the net {v.get('midcourt_points_delta_px')}   "
                     f"net tape {v.get('net_top_points_delta_px')}   "
                     f"net reads {r['checks'].get('net_top_height_m')} m")
    for run in r.get("runs", []):
        d = run["diff"]
        lines.append(
            f"   {Path(run['run']).name}: {run['points_manual']} points {run['manual_score']} -> "
            f"{d['points']} points {run['auto_score']}   lost {d['points_lost']} invented "
            f"{d['points_invented']} serve-team {d['serve_team_changed']} winner "
            f"{d['winner_changed']} | touches -{d['touches_lost']} +{d['touches_new']} "
            f"label {d['label_changed']} who {d['player_changed']}")
        if run["gt_manual"] is not None:
            lines.append(f"      owner GT  clicks: {run['gt_manual']}")
            lines.append(f"                auto  : {run['gt_auto']}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--views", nargs="*", default=list(VIEWS), choices=list(VIEWS))
    parser.add_argument("--json", default=str(OUT / "score.json"))
    args = parser.parse_args(argv)
    reports = []
    for view in args.views:
        report = score_view(view, VIEWS[view])
        reports.append(report)
        print(format_view(report), flush=True)
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(reports, indent=1))
    print(f"written: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
