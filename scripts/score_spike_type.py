#!/usr/bin/env python3
"""V1: score hard / touch attacks against the owner GT (match + practice clips).

    venv/bin/python scripts/score_spike_type.py \
        [output/postrun/20260920_match] [--clips output/postrun] [--rows]

Why: the web wants to draw hard and touch attacks differently
(docs/stats_feature_brainstorm.md O2). 32 match spikes carry an owner label
(13 hard, 19 touch), 8 practice spikes do (4 + 4). Two reads are scored:

* ``postrun`` -- ``src/postrun/attack_shape`` (launch elevation + speed of the
  flight in metres, #97), recomputed here from the run's ``diag.jsonl``;
* ``causal``  -- the ``SpikeAnalyzer`` record the publisher joined to the
  attack before #97 (``bundle._nearest_spike``), kept as the baseline.

PASS RULE, fixed before the first run (brainstorm V1): accuracy >= 0.85 AND
coverage >= 0.80 over the owner-labelled MATCH spikes, scored the way the web
sees them -- GT spike -> the post-run attack within +-15 f -> its type. Below
either bar the hard / touch encoding stays off the web. The ``postrun`` read
was designed ON these labels (the two constants sit in the measured gap), so
its match score is in-sample; the practice clips are the other venue.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_postrun import GT_CONTACTS, TOLERANCE, match_touches  # noqa: E402
from src.postrun.geometry import CourtGeometry  # noqa: E402
from src.postrun.reconstruct import reconstruct  # noqa: E402
from src.postrun.stream import load_stream  # noqa: E402
from src.publish.bundle import ATTACKS, _nearest_spike  # noqa: E402

TYPES = ("hard", "touch")
ACCURACY_BAR = 0.85
COVERAGE_BAR = 0.80
READ_CAUSAL, READ_POSTRUN = "causal", "postrun"


def gt_spikes(contacts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every owner-dictated spike with its frame, point and (maybe) type."""
    out = []
    for p in contacts["points"]:
        for c in p["contacts"]:
            if c.get("action") == "spike":
                out.append({"point": p["point"], "frame": c["match_frame"],
                            "type": c.get("spike_type"), "outcome": c.get("outcome")})
    return out


def clip_gt_spikes(index: int) -> List[Dict[str, Any]]:
    """Owner-typed spikes of one practice clip (the type may sit in ``overrides``)."""
    path = REPO / "ground_truth" / f"video_entreno_{index}_annotations.json"
    events = json.loads(path.read_text())["annotated_frames"]["actions"]["events"]
    return [{"point": index, "frame": e["frame"], "outcome": e.get("outcome"),
             "type": e.get("spike_type") or (e.get("overrides") or {}).get("spike_type")}
            for e in events if (e.get("final_action") or e.get("action")) == "spike"]


def score(recon: Dict[str, Any], spikes: List[Dict[str, Any]],
          gt: List[Dict[str, Any]], tolerance: int = TOLERANCE,
          read: str = READ_CAUSAL) -> Dict[str, Any]:
    """Pure scoring: ``recon`` is match_reconstruction.json, ``spikes`` the
    causal records of pipeline_output.json, ``gt`` from :func:`gt_spikes`.
    ``read`` picks whose type is scored (the touch's own, or the joined record)."""
    attacks = [t for p in recon["points"] for t in p["touches"] if t["action"] in ATTACKS]
    labelled = [g for g in gt if g["type"] in TYPES]

    def typed(attack: Optional[Dict[str, Any]]) -> Optional[str]:
        if attack is None:
            return None
        if read == READ_POSTRUN:
            return attack.get("spike_type")
        rec = _nearest_spike(attack["frame"], spikes)
        return rec.get("spike_type") if rec else None

    # GT spike -> the post-run attack touch (1:1 by frame distance)
    pairing = dict(match_touches(attacks, [{"frame": g["frame"]} for g in labelled], tolerance))
    to_gt = {j: i for i, j in pairing.items()}

    confusion = {g: {"hard": 0, "touch": 0, "none": 0} for g in TYPES}
    covered = correct = 0
    direct_covered = direct_correct = 0
    rows = []
    for j, g in enumerate(labelled):
        attack = attacks[to_gt[j]] if j in to_gt else None
        pred = typed(attack)
        confusion[g["type"]][pred if pred in TYPES else "none"] += 1
        if pred in TYPES:
            covered += 1
            correct += pred == g["type"]
        raw = _nearest_spike(g["frame"], spikes)
        raw_pred = raw.get("spike_type") if raw else None
        if raw_pred in TYPES:
            direct_covered += 1
            direct_correct += raw_pred == g["type"]
        rows.append({"point": g["point"], "frame": g["frame"], "gt": g["type"],
                     "attack_found": attack is not None, "published": pred, "direct": raw_pred,
                     "launch": (attack or {}).get("launch")})
    n = len(labelled)
    accuracy = correct / covered if covered else 0.0
    coverage = covered / n if n else 0.0
    return {
        "read": read,
        "n_gt_spikes": len(gt), "n_labelled": n,
        "attack_matched": len(pairing), "covered": covered, "correct": correct,
        "accuracy": accuracy, "coverage": coverage, "confusion": confusion,
        "direct": {"covered": direct_covered, "correct": direct_correct},
        "attacks": {"n": len(attacks),
                    "with_record": sum(1 for a in attacks if typed(a) in TYPES)},
        "pass": accuracy >= ACCURACY_BAR and coverage >= COVERAGE_BAR,
        "rows": rows,
    }


def wilson(k: int, n: int, z: float = 1.96) -> Optional[tuple]:
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def report(r: Dict[str, Any]) -> str:
    lo, hi = wilson(r["correct"], r["covered"]) or (0, 0)
    lines = [
        f"[{r['read']}] GT spikes {r['n_gt_spikes']}, owner-labelled hard/touch {r['n_labelled']}; "
        f"matched to a post-run attack within +-{TOLERANCE} f: {r['attack_matched']}",
        f"coverage (a type is given for the spike): {r['covered']}/{r['n_labelled']} = {r['coverage']:.3f}   "
        f"(bar {COVERAGE_BAR})",
        f"accuracy (type == owner type):            {r['correct']}/{r['covered']} = {r['accuracy']:.3f}   "
        f"(bar {ACCURACY_BAR}; 95% range {lo:.2f}-{hi:.2f})",
        "confusion (rows = owner, columns = read):",
        f"            {'hard':>6}{'touch':>7}{'none':>6}",
    ]
    for g in TYPES:
        c = r["confusion"][g]
        lines.append(f"  {g:<9} {c['hard']:>6}{c['touch']:>7}{c['none']:>6}")
    if r["read"] == READ_CAUSAL:
        d = r["direct"]
        lines.append(f"diagnostic, record nearest the GT frame: {d['correct']}/{d['covered']} right, "
                     f"{d['covered']}/{r['n_labelled']} covered")
    lines += [
        f"all post-run attacks with a type: {r['attacks']['with_record']}/{r['attacks']['n']}",
        f"VERDICT [{r['read']}]: {'PASS' if r['pass'] else 'FAIL'}",
    ]
    return "\n".join(lines)


def rows_report(r: Dict[str, Any]) -> str:
    out = []
    for row in r["rows"]:
        la = row.get("launch") or {}
        shape = (f"  {la['speed_ms']:>5} m/s  rise {la['rise_ms']:>5}  elev {la['elevation_deg']:>5} / "
                 f"{la['elevation_ends_deg']}  n={la['samples']}" if la else "")
        mark = "" if row["published"] is None else ("  ok" if row["published"] == row["gt"] else "  WRONG")
        out.append(f"  P{row['point']:<3} f{row['frame']:<6} gt={row['gt']:<6} attack={row['attack_found']!s:<5} "
                   f"read={row['published']!s:<5}{mark}{shape}")
    return "\n".join(out)


def load_run(run: Path, calibration: Optional[str] = None) -> Dict[str, Any]:
    """Reconstruct a run in memory (never a stale match_reconstruction.json)."""
    payload = json.loads((run / "pipeline_output.json").read_text())
    video = payload.get("video") or {}
    calibration = calibration or (video.get("calibration_readiness") or {}).get("calibration_path")
    stream = load_stream(str(run / "diag.jsonl"), fps=video.get("fps"))
    size = (int(video.get("width") or 1920), int(video.get("height") or 1080))
    recon = reconstruct(stream, CourtGeometry.from_file(calibration), frame_size=size)
    return {"recon": json.loads(json.dumps(recon)), "spikes": payload.get("spikes") or []}


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("run_dir", nargs="?", default="output/postrun/20260920_match",
                   help="directory with diag.jsonl + pipeline_output.json")
    p.add_argument("--gt", default=GT_CONTACTS)
    p.add_argument("--calibration", help="court calibration JSON (default: the run's own)")
    p.add_argument("--clips", help="directory holding entreno_<n>/ runs: also score the practice spikes")
    p.add_argument("--rows", action="store_true", help="print every labelled spike")
    args = p.parse_args(argv)
    run = load_run(Path(args.run_dir), args.calibration)
    gt = gt_spikes(json.loads(Path(args.gt).read_text()))
    results = {read: score(run["recon"], run["spikes"], gt, read=read)
               for read in (READ_CAUSAL, READ_POSTRUN)}
    for read in (READ_CAUSAL, READ_POSTRUN):
        print(report(results[read]))
        print()
    if args.rows:
        print(rows_report(results[READ_POSTRUN]))
    if args.clips:
        total = {READ_CAUSAL: [0, 0, 0], READ_POSTRUN: [0, 0, 0]}
        for index in range(1, 8):
            clip = Path(args.clips) / f"entreno_{index}"
            if not (clip / "diag.jsonl").exists():
                continue
            data = load_run(clip, f"calibrations/video_entreno_{index}.json")
            clip_gt = clip_gt_spikes(index)
            for read in total:
                r = score(data["recon"], data["spikes"], clip_gt, read=read)
                total[read][0] += r["correct"]
                total[read][1] += r["covered"]
                total[read][2] += r["n_labelled"]
                if read == READ_POSTRUN and args.rows and r["n_labelled"]:
                    print(rows_report(r).replace("  P", "  e"))
        for read, (ok, covered, n) in total.items():
            print(f"practice clips [{read}]: {ok}/{covered} right, {covered}/{n} covered")
    verdict = results[READ_POSTRUN]
    print(f"VERDICT: {'PASS' if verdict['pass'] else 'FAIL'} -> "
          + ("the hard / touch encoding may ship" if verdict["pass"]
             else "the hard / touch encoding stays off the web"))
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
