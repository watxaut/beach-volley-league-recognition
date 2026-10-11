#!/usr/bin/env python3
"""How wrong may a court calibration be before the post-run layer changes?

    venv/bin/python scripts/probe_calibration_sensitivity.py \
        output/postrun/20260920_match output/20261010_1000_vall_dhebron_jesus_sara_joan_loida

Moves the calibration of a finished run one quantity at a time (baseline
widths, baseline rows, single corners, the net clicks) and reconstructs the
match again from the run's diag dump, in memory. Nothing is written into the
run directory. A row is DECISION-neutral when no point is lost or invented
and no serving team or winner changes; it is fully neutral when no touch,
label or credited player changes either.

The causal pass is NOT re-run: the dump's tracks were made with the run's own
calibration, so this reads the tolerance of ``src/postrun`` only (what turns a
calibration into points, winners and stats). It is the pass bar for an
automatic calibration (``docs/auto_calibration.md``).
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.postrun.geometry import CourtGeometry  # noqa: E402
from src.postrun.reconstruct import (FRAME_TIMES_NAME, load_frame_times,  # noqa: E402
                                     reconstruct)
from src.postrun.stream import load_stream  # noqa: E402

#: Points of two reconstructions are the same point when their serves are
#: this close (the tolerance every contact score uses).
PAIR_FRAMES = 15

WIDTH_STEPS = (0.005, 0.01, 0.015, 0.02, 0.03, 0.04, 0.06)
ROW_STEPS = (2, 4, 6, 8, 12, 16)
NET_STEPS = (4, 8, 16)

#: kind -> (unit, steps). Widths are a fraction of the baseline's own width;
#: rows are pixels and reported as a fraction of the court's depth too.
KINDS: Dict[str, Tuple[str, Tuple[float, ...]]] = {
    "far_width": ("frac", WIDTH_STEPS),
    "near_width": ("frac", WIDTH_STEPS),
    "far_row": ("px", ROW_STEPS),
    "near_row": ("px", ROW_STEPS),
    "far_left_row": ("px", ROW_STEPS),
    "far_right_row": ("px", ROW_STEPS),
    "net_ground_row": ("px", NET_STEPS),
    "net_top_row": ("px", NET_STEPS),
}


def perturb(calibration: Dict[str, Any], kind: str, value: float) -> Dict[str, Any]:
    """A copy of ``calibration`` with one quantity moved by ``value``."""
    out = copy.deepcopy(calibration)
    corners = np.asarray(out["court_corners"], dtype=float)   # FL, FR, NR, NL
    ground = np.asarray(out["midcourt_points"], dtype=float)
    top = np.asarray(out["net_top_points"], dtype=float)
    if kind == "far_width":
        centre = corners[:2, 0].mean()
        corners[:2, 0] = centre + (corners[:2, 0] - centre) * (1.0 + value)
    elif kind == "near_width":
        centre = corners[2:, 0].mean()
        corners[2:, 0] = centre + (corners[2:, 0] - centre) * (1.0 + value)
    elif kind == "far_row":
        corners[:2, 1] += value
    elif kind == "near_row":
        corners[2:, 1] += value
    elif kind == "far_left_row":
        corners[0, 1] += value
    elif kind == "far_right_row":
        corners[1, 1] += value
    elif kind == "net_ground_row":
        ground[:, 1] += value
    elif kind == "net_top_row":
        top[:, 1] += value
    else:
        raise ValueError(f"unknown perturbation {kind!r}")
    out["court_corners"] = corners.tolist()
    out["midcourt_points"] = ground.tolist()
    out["net_top_points"] = top.tolist()
    return out


# -- one reconstruction ------------------------------------------------------ #

def run_inputs(run_dir: Path, calibration: Optional[str] = None) -> Dict[str, Any]:
    """What ``python -m src.postrun <run_dir>`` would read."""
    payload: Dict[str, Any] = {}
    pipeline = run_dir / "pipeline_output.json"
    if pipeline.exists():
        payload = json.loads(pipeline.read_text())
    video = payload.get("video") or {}
    path = calibration or (video.get("calibration_readiness") or {}).get("calibration_path")
    if not path:
        raise SystemExit(f"{run_dir}: no calibration recorded; pass --calibration")
    path = Path(path)
    if not path.is_absolute() and not path.exists():
        path = ROOT / path
    if not path.exists():
        raise SystemExit(f"{run_dir}: calibration {path} not found")
    return {
        "run": str(run_dir), "diag": str(run_dir / "diag.jsonl"),
        "calibration_path": str(path), "calibration": json.loads(path.read_text()),
        "fps": video.get("fps"),
        "frame_size": (int(video.get("width") or 1920), int(video.get("height") or 1080)),
    }


def reconstruct_run(inputs: Dict[str, Any], calibration: Dict[str, Any]) -> Dict[str, Any]:
    """The run's reconstruction with ``calibration`` (nothing is written)."""
    stream = load_stream(inputs["diag"], fps=inputs["fps"])
    stream.frame_times = load_frame_times(
        Path(inputs["diag"]).parent / FRAME_TIMES_NAME, stream.n_frames)
    geometry = CourtGeometry(calibration["court_corners"],
                             calibration.get("net_top_points"),
                             calibration.get("midcourt_points"))
    return reconstruct(stream, geometry, frame_size=inputs["frame_size"])


def digest(inputs: Dict[str, Any], calibration: Dict[str, Any]) -> Dict[str, Any]:
    """Reconstruct with ``calibration`` and keep what a comparison needs."""
    return digest_of(reconstruct_run(inputs, calibration))


def digest_of(result: Dict[str, Any]) -> Dict[str, Any]:
    points = [{"frame": p["start_frame"], "serve_team": p["serve"]["team"],
               "winner": p["winner"]} for p in result["points"]]
    touches = {t["frame"]: (t["action"], t["player"])
               for p in result["points"] for t in p["touches"]}
    return {"points": points, "touches": touches,
            "score": result["checks"]["final_score"],
            "net_top_height_m": result["geometry"]["net_top_height_m"]}


def compare(base: Dict[str, Any], other: Dict[str, Any]) -> Dict[str, Any]:
    """What changed from ``base`` to ``other``."""
    left = sorted(base["points"], key=lambda p: p["frame"])
    used: set = set()
    lost = serve_changed = winner_changed = 0
    for p in left:
        match = None
        for j, q in enumerate(other["points"]):
            if j not in used and abs(q["frame"] - p["frame"]) <= PAIR_FRAMES:
                match = j
                break
        if match is None:
            lost += 1
            continue
        used.add(match)
        q = other["points"][match]
        serve_changed += q["serve_team"] != p["serve_team"]
        winner_changed += q["winner"] != p["winner"]
    invented = len(other["points"]) - len(used)
    b, o = base["touches"], other["touches"]
    common = set(b) & set(o)
    out = {
        "points": len(other["points"]), "points_lost": lost, "points_invented": invented,
        "serve_team_changed": serve_changed, "winner_changed": winner_changed,
        "score": other["score"],
        "touches_lost": len(set(b) - set(o)), "touches_new": len(set(o) - set(b)),
        "label_changed": sum(b[f][0] != o[f][0] for f in common),
        "player_changed": sum(b[f][1] != o[f][1] for f in common),
        "net_top_height_m": other["net_top_height_m"],
    }
    out["decision_neutral"] = not (lost or invented or serve_changed or winner_changed)
    out["neutral"] = out["decision_neutral"] and not (
        out["touches_lost"] or out["touches_new"] or out["label_changed"]
        or out["player_changed"])
    return out


def _job(args: Tuple[Dict[str, Any], str, float]) -> Dict[str, Any]:
    inputs, kind, value = args
    logging.disable(logging.CRITICAL)
    try:
        return {"kind": kind, "value": value,
                "digest": digest(inputs, perturb(inputs["calibration"], kind, value))}
    except Exception as exc:                       # a calibration the layer refuses
        return {"kind": kind, "value": value, "error": f"{type(exc).__name__}: {exc}"}


# -- one run ----------------------------------------------------------------- #

def safe_up_to(rows: List[Dict[str, Any]], key: str) -> float:
    """Largest size such that every row of that size or less passes ``key``
    in both directions (0 when the smallest step already fails)."""
    safe = 0.0
    for size in sorted({abs(r["value"]) for r in rows}):
        if all(r.get(key) for r in rows if abs(r["value"]) == size):
            safe = size
        else:
            break
    return safe


def sweep_run(inputs: Dict[str, Any], pool: ProcessPoolExecutor,
              kinds: List[str]) -> Dict[str, Any]:
    logging.disable(logging.CRITICAL)
    base = digest(inputs, inputs["calibration"])
    logging.disable(logging.NOTSET)
    geometry = CourtGeometry(inputs["calibration"]["court_corners"])
    corners = geometry.corners
    depth_px = float(corners[2:, 1].mean() - corners[:2, 1].mean())
    jobs = [(inputs, kind, sign * step) for kind in kinds
            for step in KINDS[kind][1] for sign in (-1.0, 1.0)]
    rows: List[Dict[str, Any]] = []
    for res in pool.map(_job, jobs):
        row = {"kind": res["kind"], "value": res["value"]}
        if "error" in res:
            row.update(error=res["error"], decision_neutral=False, neutral=False)
        else:
            row.update(compare(base, res["digest"]))
        rows.append(row)
    summary = {}
    for kind in kinds:
        of_kind = [r for r in rows if r["kind"] == kind]
        summary[kind] = {"unit": KINDS[kind][0],
                         "decision_safe": safe_up_to(of_kind, "decision_neutral"),
                         "fully_safe": safe_up_to(of_kind, "neutral")}
    return {
        "run": inputs["run"], "calibration": inputs["calibration_path"],
        "base": {"points": len(base["points"]), "score": base["score"],
                 "touches": len(base["touches"]),
                 "net_top_height_m": base["net_top_height_m"]},
        "court_px": {"depth": round(depth_px, 1), "far_width": round(geometry.far_px, 1),
                     "near_width": round(geometry.near_px, 1)},
        "summary": summary, "rows": rows,
    }


def _size(unit: str, value: float) -> str:
    return f"{value * 100:+.1f} %" if unit == "frac" else f"{value:+.0f} px"


def format_run(report: Dict[str, Any], verbose: bool) -> str:
    base, px = report["base"], report["court_px"]
    lines = [
        f"== {Path(report['run']).name}",
        f"   base: {base['points']} points, score {base['score']}, {base['touches']} touches, "
        f"net {base['net_top_height_m']} m; court {px['depth']:.0f} px deep, "
        f"baselines {px['far_width']:.0f} / {px['near_width']:.0f} px",
        f"   {'quantity':16s} {'decisions hold up to':>22s} {'nothing moves up to':>22s}",
    ]
    for kind, s in report["summary"].items():
        def cell(v: float) -> str:
            if v == 0:
                return "< smallest step"
            text = f"{v * 100:.1f} %" if s["unit"] == "frac" else f"{v:.0f} px"
            if s["unit"] == "px" and kind.endswith("row") and "net" not in kind:
                text += f" ({v / px['depth'] * 100:.1f} % depth)"
            return text
        lines.append(f"   {kind:16s} {cell(s['decision_safe']):>22s} {cell(s['fully_safe']):>22s}")
    if verbose:
        for r in report["rows"]:
            unit = KINDS[r["kind"]][0]
            if "error" in r:
                lines.append(f"     {r['kind']:16s} {_size(unit, r['value']):>9s}  {r['error']}")
                continue
            if r["neutral"]:
                continue
            lines.append(
                f"     {r['kind']:16s} {_size(unit, r['value']):>9s}  points {r['points']} "
                f"(-{r['points_lost']} +{r['points_invented']}) serve {r['serve_team_changed']} "
                f"winner {r['winner_changed']} score {r['score']} | touches "
                f"-{r['touches_lost']} +{r['touches_new']} label {r['label_changed']} "
                f"who {r['player_changed']}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", nargs="+", help="run directories holding diag.jsonl")
    parser.add_argument("--calibration", help="calibration JSON (one run only)")
    parser.add_argument("--kinds", nargs="*", default=list(KINDS), choices=list(KINDS))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--rows", action="store_true", help="print every row that moves")
    parser.add_argument("--json", help="write the full table here")
    args = parser.parse_args(argv)
    if args.calibration and len(args.runs) != 1:
        raise SystemExit("--calibration needs exactly one run")

    reports = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for run in args.runs:
            report = sweep_run(run_inputs(Path(run), args.calibration), pool, args.kinds)
            reports.append(report)
            print(format_run(report, args.rows), flush=True)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(reports, indent=1))
        print(f"written: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
