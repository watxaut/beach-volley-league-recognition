#!/usr/bin/env python3
"""Try scale-aware (and mirror-aware) contact geometry on the GT serves.

Arms (scripts/scale_aware_harness.py): ``px`` = untouched production (the
fidelity baseline), ``scale`` = thresholds as multiples of the ball's apparent
width, ``mirror`` = production + mirrored vertex tests (a far-side serve is
STRUCTURALLY mirrored: struck at the camera, the ball peaks and descends),
``scale+mirror`` = both.

Every arm is replayed over the SAME recorded ball tracks the production run
produced (the diag dumps from ``scripts/probe_far_serve_tracking.py``), so the
only thing that changes between arms is the geometry.  Reported per arm:

* far serves: a contact firing within +-TOL of the owner frame (recall), split
  dev (P1-P8) / held-out (P9-PP33);
* near serves: the same, as the NON-REGRESSION side (the near geometry is the
  validated one);
* control windows (mid-rally non-serve GT contacts): a contact firing within
  +-TOL is a FALSE POSITIVE.

Fit discipline: the ``k`` grid is read on the DEV split; the held-out split is
the check, and both are printed so a dev-only win cannot hide.

Usage::

    venv/bin/python scripts/probe_scale_aware_geometry.py --dir output/g4/serve_dumps
    venv/bin/python scripts/probe_scale_aware_geometry.py --dir ... --k 0.5 --arm scale
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scale_aware_harness import ARMS, ScaleAwareActionClassifier  # noqa: E402
from src.recognition.pose_estimator import PoseEstimator  # noqa: E402
from src.utils.config import Config  # noqa: E402

GT_PATH = ROOT / "ground_truth" / "20260920_match_contacts.json"
DEFAULT_TOL = 15


def gt_contacts() -> Dict[int, Dict[str, Any]]:
    """frame -> {side, action, point, held_out} for every owner serve/contact."""
    blob = json.loads(GT_PATH.read_text())
    out: Dict[int, Dict[str, Any]] = {}
    for point in blob["points"]:
        for event in point.get("events", []):
            if not event.get("action"):
                continue
            frame = int(event["match_frame"])
            out.setdefault(frame, {
                "side": event.get("owner_side"),
                "action": event.get("action"),
                "point": point["point"],
                "held_out": point["point"] > 8,
            })
    return out


def build(arm: str, ks: Dict[str, Optional[float]], mirror_speed_bw: Optional[float]):
    cfg = Config.default().config
    return ScaleAwareActionClassifier(
        pose_estimator=PoseEstimator(
            min_detection_confidence=cfg.get("pose_confidence", 0.5),
            model_complexity=cfg.get("pose_complexity", 0),
        ),
        temporal_window=cfg.get("temporal_window", 10),
        confidence_threshold=cfg.get("action_confidence", 0.3),
        team_aware=cfg.get("attribution_team_aware", True),
        width_side_enabled=cfg.get("attribution_width_side", True),
        width_window=cfg.get("attribution_width_window", 8),
        width_far_px=cfg.get("attribution_width_far_px", 26.0),
        width_near_px=cfg.get("attribution_width_near_px", 35.0),
        near_net_exempt_m=cfg.get("attribution_near_net_exempt_m", 2.5),
        arm=arm,
        k_prominence=ks.get("prominence"),
        k_xrev=ks.get("xrev"),
        k_decel=ks.get("decel"),
        k_ximpulse=ks.get("ximpulse"),
        k_rise_tol=ks.get("rise_tol"),
        k_serve_margin=ks.get("serve_margin"),
        mirror_min_speed_bw=mirror_speed_bw,
    )


def load_window(path: Path) -> Dict[str, Any]:
    """Tracked ball history (with the REAL apparent width) + raw det widths."""
    frame = int(path.stem.split("_f")[1])
    history: List[tuple] = []
    raw_width: Dict[int, List[int]] = {}
    for line in path.read_text().splitlines():
        rec = json.loads(line)
        f = int(rec.get("frame", -1))
        for det in rec.get("ball_dets") or []:
            bbox = det.get("bbox")
            if bbox and len(bbox) == 4:
                raw_width.setdefault(f, []).append(max(1, bbox[2] - bbox[0]))
        bt = rec.get("ball_track") or {}
        if bt.get("state") != "tracked":
            continue
        center = bt.get("center")
        if not center or center[0] is None:
            continue
        history.append((f, float(center[0]), float(center[1])))
    widths: Dict[int, int] = {}
    for f in [p[0] for p in history]:
        cands = raw_width.get(f) or []
        if not cands:                      # nearest frame with a detection
            near = [raw_width[g] for g in sorted(raw_width) if abs(g - f) <= 2 and raw_width[g]]
            cands = near[0] if near else [20]
        widths[f] = max(cands)
    return {"frame": frame, "history": history, "widths": widths}


def run_arm(window: Dict[str, Any], arm: str, ks: Dict[str, Optional[float]],
            tol: int, mirror_speed_bw: Optional[float]) -> List[Dict[str, Any]]:
    """Contacts the arm fires within +-TOL of the GT frame."""
    if not window["history"]:
        return []
    clf = build(arm, ks, mirror_speed_bw)
    for f, x, y in window["history"]:
        w = window["widths"].get(f, 20)
        clf._ball_history.append((f, x, y, float(w), float(w)))
    contact = window["frame"]
    fired: List[Dict[str, Any]] = []
    # Sequential, the way production asks: every sighting in order, and
    # ``_last_contact_frame`` advanced on every fire so MIN_CONTACT_GAP applies
    # (otherwise a run of adjacent vertices would each count as a contact).
    for f in sorted(p[0] for p in window["history"]):
        result = clf._detect_contact(f)
        if result is None:
            continue
        clf._last_contact_frame = f
        fired.append({"kind": result[1], "frame": result[4],
                      "offset": result[4] - contact, "in_window": abs(result[4] - contact) <= tol})
    return fired


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    def rate(subset, key="hit"):
        return (sum(1 for r in subset if r[key]), len(subset))
    far = [r for r in rows if r["kind"] == "far_serve"]
    near = [r for r in rows if r["kind"] == "near_serve"]
    ctrl = [r for r in rows if r["kind"] == "control"]
    far_dev = [r for r in far if not r["held_out"]]
    far_held = [r for r in far if r["held_out"]]
    near_dev = [r for r in near if not r["held_out"]]
    near_held = [r for r in near if r["held_out"]]
    out = {
        "far_dev": rate(far_dev), "far_held": rate(far_held),
        "near_dev": rate(near_dev), "near_held": rate(near_held),
        "control": rate(ctrl),
    }
    kinds = Counter(r["kind_fired"] for r in rows if r["hit"] and r.get("kind_fired"))
    out["kinds"] = dict(kinds)
    # Exposure: how many contacts the arm invents ELSEWHERE in the same windows
    # (outside +-TOL). A mechanism that only works by firing more cannot be read
    # without this, even before the non-serve control windows exist.
    out["extra_fires"] = sum(max(0, r.get("fires_total", 0) - int(r["hit"]))
                             for r in rows)
    out["fires_total"] = sum(r.get("fires_total", 0) for r in rows)
    out["median_fires_per_window"] = sorted(r.get("fires_total", 0) for r in rows)[len(rows) // 2]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="output/g4/serve_dumps")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--k", type=float, default=None,
                    help="one k for every scaled threshold (ball widths)")
    ap.add_argument("--k-prominence", type=float, default=None)
    ap.add_argument("--k-serve-margin", type=float, default=None)
    ap.add_argument("--k-decel", type=float, default=None)
    ap.add_argument("--k-ximpulse", type=float, default=None)
    ap.add_argument("--k-xrev", type=float, default=None)
    ap.add_argument("--mirror-speed-bw", type=float, default=None,
                    help="require the mirrored vertex to leave at >= k ball-widths/frame")
    ap.add_argument("--tolerance", type=int, default=DEFAULT_TOL)
    ap.add_argument("--sweep", default="",
                    help="comma list of k values in ball widths, e.g. 0.3,0.5,0.7")
    ap.add_argument("--sweep-arms", default="scale,scale+mirror")
    ap.add_argument("--out", default="output/g4/scale_aware_geometry.json")
    args = ap.parse_args()

    ks = {
        "prominence": args.k if args.k is not None else args.k_prominence,
        "serve_margin": args.k if args.k is not None else args.k_serve_margin,
        "decel": args.k if args.k is not None else args.k_decel,
        "ximpulse": args.k if args.k is not None else args.k_ximpulse,
        "xrev": args.k if args.k is not None else args.k_xrev,
    }
    ks = {key: (None if value is None else float(value)) for key, value in ks.items()}

    gt = gt_contacts()
    windows = []
    for path in sorted(Path(args.dir).glob("*.jsonl")):
        window = load_window(path)
        info = gt.get(window["frame"])
        if info is None:
            continue
        if info["action"] == "serve":
            kind = "far_serve" if info["side"] == "far" else "near_serve"
        else:
            kind = "control"
        windows.append({**window, "kind": kind, "held_out": info["held_out"],
                        "action": info["action"], "point": info["point"]})
    if not windows:
        print(f"no GT-matching windows in {args.dir}")
        return 1
    print(f"{len(windows)} windows: "
          f"{sum(1 for w in windows if w['kind']=='far_serve')} far serves, "
          f"{sum(1 for w in windows if w['kind']=='near_serve')} near serves, "
          f"{sum(1 for w in windows if w['kind']=='control')} control")

    def sweep(label: str, sweep_ks: Dict[str, Optional[float]], arm: Optional[str] = None):
        arm = arm or label
        rows = []
        for window in windows:
            fired = run_arm(window, arm, sweep_ks, args.tolerance, args.mirror_speed_bw)
            rows.append({
                "point": window["point"], "frame": window["frame"],
                "kind": window["kind"], "held_out": window["held_out"],
                "action": window["action"],
                "hit": any(f["in_window"] for f in fired),
                "kind_fired": next((f["kind"] for f in fired if f["in_window"]), None),
                "offset": next((f["offset"] for f in fired if f["in_window"]), None),
                "fires_total": len(fired),
                "tracked": len(window["history"]),
            })
        summary = summarise(rows)
        report["arms"][label] = {"summary": summary, "rows": rows}
        print(f"\nARM {label}")
        for key in ("far_dev", "far_held", "near_dev", "near_held", "control"):
            hit, n = summary[key]
            print(f"  {key:<10} {hit:>2}/{n:<3}"
                  + ("   <- false positives" if key == "control" else ""))
        print(f"  kinds fired: {summary['kinds']} | extra fires outside +-TOL: "
              f"{summary['extra_fires']} of {summary['fires_total']} total")
        return summary

    report: Dict[str, Any] = {"k": ks, "mirror_speed_bw": args.mirror_speed_bw,
                              "tolerance": args.tolerance, "arms": {}}
    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        sweep(arm, ks)

    if args.sweep:
        # One multiplier for every scaled threshold: the trade-off curve the
        # owner reads (far recall vs control false positives vs near recall).
        print("\nSWEEP  k (ball widths) -> far_dev far_held near_dev near_held control")
        report["sweep"] = []
        for value in [float(x) for x in args.sweep.split(",")]:
            sweep_ks = {key: value for key in ("prominence", "serve_margin",
                                                "decel", "ximpulse", "xrev")}
            for arm in [a.strip() for a in args.sweep_arms.split(",") if a.strip()]:
                key_name = f"{arm}@k={value}"
                summary = sweep(key_name, sweep_ks, arm=arm)
                report["sweep"].append({"arm": arm, "k": value, **{
                    k2: summary[k2][0] for k2 in
                    ("far_dev", "far_held", "near_dev", "near_held", "control")}})

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
