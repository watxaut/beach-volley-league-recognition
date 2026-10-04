"""G3 -- OVERPASS via POST-CONTACT NET CROSSING in y (the physically correct test).

Session #76, fourth step.  The three measurements so far:

1. ``scripts/probe_label_ceilings.py``  -- the PRIZE is +0.0949 and crosses
   the 0.70 bar alone.
2. ``scripts/probe_overpass_separator.py`` -- no kinematic separator exists
   (16 features, all 120 two-feature AND-rules: best |delta| 0.413 / 0.333).
3. ``scripts/probe_overpass_budget.py`` -- the precision budget: the rule must
   fire on at most ``2k - 12`` matched contacts to recover ``k`` of the 16
   in-scope GT overpasses, i.e. >= 80-100% precision, and all seven
   possession-refaming rules are NET-NEGATIVE (34 fires / 0 hits for the best).

The gap in all three: they key on the contact's own kinematics and on the
NEXT EMITTED CONTACT. Neither is how a cross is physically defined. A cross is
the ball's trajectory passing through the net plane after the contact, and the
stream has the ball tracked on ~91 of 91 frames in the +-45 f window at 12 of
the 18 in-scope overpasses (dense: median frame gap 1). **The evidence is
there; it has simply never been read off in this frame.**

So this probe reads it: for every contact, walk the tracked ball forward from
the contact frame and ask whether the trajectory CROSSES the net plane, using
the PRODUCTION calibration (``CourtCalibration.get_net_top_y_at_x`` on
``calibrations/20260920_match_ari_joan_lost.json``). Near the net plane an
image-space y crossing is unambiguous: the net top runs at y ~376 and the
midcourt at y ~643, so the plane is a near-horizontal band 267 px deep in the
frame's centre, and crossing it is not a depth inference but a sign change in
``y - net_y_at_x``.

Two variants are scored, because "crossed" and "crossed AND stayed over" are
different claims:

* ``cross``   -- the trajectory's side sign flips within POST_SPAN frames.
* ``cross_lo`` -- same, with a LOWER threshold: the ball only has to reach the
  far half of the net band (``y > net_y + CROSS_DEEP_FRACTION``), which is what
  "sent over" actually needs and is robust to the tape.

Controls are the ``dig`` / ``set`` / ``spike`` matched contacts, each judged by
its OWN GT class, so a dig that sits deep and a set that sits high are both
counted against the rule.

DIAGNOSE ONLY: no ``src/`` change, no decode, no seek, no GT edit; the read-only
calibration JSON is used, nothing is written back to it.

Usage:
    venv/bin/python scripts/probe_overpass_netcross.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import evaluate_timed as et  # noqa: E402
from src.detection.court_calibration import CourtCalibration  # noqa: E402
from src.utils.diagnostics import load_diag  # noqa: E402

DEFAULT_GT = "ground_truth/20260920_match_contacts.json"
DEFAULT_DIAG = "output/g3r1/match_bw03_diag.jsonl"
DEFAULT_CALIB = "calibrations/20260920_match_ari_joan_lost.json"
DEFAULT_JSON = "output/g3_overpass/netcross.json"

POST_SPAN = 60
#: Fraction of the net band the ball must clear past the net line.
CROSS_DEEP_FRACTION = 0.25
#: Minimum tracked frames after the contact for the test to be decidable.
MIN_POST_FRAMES = 12
CONTROLS = ("dig", "set", "spike")


# ----------------------------------------------------------------------
# ball trajectory
# ----------------------------------------------------------------------

def tracked_centers(frames: Dict[int, Dict[str, Any]]) -> Dict[int, Tuple[float, float]]:
    """frame -> locked ball centre. A predicted centre has no detection but
    IS still a position estimate, so it is kept and flagged by the caller
    through coverage counts (never used to fabricate a width)."""
    out: Dict[int, Tuple[float, float]] = {}
    for f, rec in frames.items():
        bt = rec.get("ball_track") or {}
        c = bt.get("center")
        if bt.get("locked") and c:
            out[int(f)] = (float(c[0]), float(c[1]))
    return out


def net_band(calib: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """(y0, y1) net-top line at the frame centre, and the band half-depth.

    The net TOP line is the plane the ball must pass to be over; the midcourt
    line is the far limit of the ambiguous band.
    """
    nt = calib["net_top_points"]
    mc = calib["midcourt_points"]
    x_c = (nt[0][0] + nt[1][0]) / 2.0
    y_top = (nt[0][1] + nt[1][1]) / 2.0
    y_mid = (mc[0][1] + mc[1][1]) / 2.0
    return x_c, y_top, y_mid, abs(y_mid - y_top)


def side_sign(y: float, net_y: float, deep: float) -> int:
    """-1 above the net, +1 past ``net_y + deep``, 0 inside the ambiguous band."""
    if y < net_y:
        return -1
    if y > net_y + deep:
        return 1
    return 0


def crossing_test(centers: Dict[int, Tuple[float, float]], frame: int,
                  net_y_at_x, deep: float, post_span: int = POST_SPAN
                  ) -> Dict[str, Any]:
    """Walk forward from ``frame``; report whether the side sign flips."""
    seq: List[Tuple[int, int, float]] = []
    for k in range(0, post_span + 1):
        f = frame + k
        c = centers.get(f)
        if c is None:
            continue
        seq.append((f, side_sign(c[1], net_y_at_x(c[0]), deep), c[1]))
    signs = [s for _f, s, _y in seq]
    observed = len(signs)
    start = signs[0] if signs else 0
    # first frame whose committed sign differs from the contact sign
    crossed_at = None
    for f, s, _y in seq:
        if start and s and s != start:
            crossed_at = f
            break
    committed = [s for s in signs if s]
    return {
        "observed_post_frames": observed,
        "committed_post": len(committed),
        "start_sign": start,
        "crossed": crossed_at is not None,
        "crossed_at_frame": crossed_at,
        "end_sign": signs[-1] if signs else 0,
        "decidable": observed >= MIN_POST_FRAMES,
    }


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def build_rows(frames: Dict[int, Dict[str, Any]], centers, calib_path: str,
               gt_path: str, from_point: int, to_point: int, fps: float,
               tolerance_s: float = 0.2) -> List[Dict[str, Any]]:
    calib = json.loads(Path(calib_path).read_text(encoding="utf-8"))
    # the production class, loaded from the read-only calibration JSON
    court = CourtCalibration(calib_path)
    x_c, y_top, y_mid, band = net_band(calib)
    deep = band * CROSS_DEEP_FRACTION

    def net_y_at_x(x: float) -> float:
        v = court.get_net_top_y_at_x(int(round(x)))
        return float(v) if v is not None else y_top

    contacts: List[Dict[str, Any]] = []
    for rec in frames.values():
        for c in rec.get("candidates") or []:
            if c.get("stage") == "accepted":
                contacts.append(dict(c, _frame=int(rec["frame"])))
    contacts.sort(key=lambda c: c["_frame"])

    blob = json.loads(Path(gt_path).read_text(encoding="utf-8"))
    ev = (blob.get("annotated_frames") or {}).get("actions", {}).get("events") or []
    gt_all = [{
        "frame": int(e["frame"]),
        "action": e.get("final_action") or e.get("action"),
        "raw": dict(e, frame_tolerance=e.get("frame_tolerance", 15)),
    } for e in ev if e.get("frame") is not None]
    pr = [et.normalize_event({"frame": c["_frame"], "action": c.get("action"),
                              "team": c.get("team")}) for c in contacts]
    m = et.match_events([et.normalize_event(g) for g in gt_all], pr,
                        et.TimeBase(fps=fps), base_tolerance_s=tolerance_s)
    gt_by_frame = {g["frame"]: g["action"] for g in gt_all}
    in_scope = from_point <= to_point

    rows: List[Dict[str, Any]] = []
    for g, p, _d in m["pairs"]:
        ga = g["action"]
        row = next(c for c in contacts if c["_frame"] == int(p["frame"]))
        # scope: the contact frame must lie inside the scored region
        if not (in_scope and gt_by_frame.get(int(g["frame"])) is not None):
            continue
        t_shallow = crossing_test(centers, int(p["frame"]), net_y_at_x, deep)
        t_deep = crossing_test(centers, int(p["frame"]), net_y_at_x, deep * 2.0)
        rows.append({
            "frame": int(p["frame"]), "gt_action": ga,
            "pred_action": p["action"], "team": p.get("team"),
            "gesture": row.get("gesture"), "kind": row.get("kind"),
            "touch_number": row.get("touch_number"),
            "near_net": row.get("near_net"),
            "shallow": t_shallow, "deep": t_deep,
        })
    return rows, {"x_centre": x_c, "net_top_y": y_top, "midcourt_y": y_mid,
                  "band_px": band, "deep_px": deep}


def report(rows: Sequence[Dict[str, Any]], geom: Dict[str, Any],
           key: str = "shallow") -> Dict[str, Any]:
    """Rate the cross signal per GT class (overpass vs controls)."""
    def rate(klass: str) -> Dict[str, Any]:
        rs = [r for r in rows if r["gt_action"] == klass]
        n = len(rs)
        fired = sum(1 for r in rs if r[key]["crossed"])
        dec = sum(1 for r in rs if r[key]["decidable"])
        both = sum(1 for r in rs if r[key]["crossed"] and r[key]["decidable"])
        return {"n": n, "decidable": dec, "crossed": fired,
                "crossed_and_decidable": both,
                "rate": round(fired / n, 4) if n else None,
                "rate_decidable": round(both / dec, 4) if dec else None}
    out = {k: rate(k) for k in ("overpass",) + CONTROLS}
    op, ctrl = out["overpass"], {k: out[k] for k in CONTROLS}
    tot_c = sum(v["crossed_and_decidable"] for v in ctrl.values())
    tot_d = sum(v["decidable"] for v in ctrl.values())
    out["control_pool"] = {
        "n": sum(v["n"] for v in ctrl.values()),
        "decidable": tot_d, "crossed_and_decidable": tot_c,
        "rate_decidable": round(tot_c / tot_d, 4) if tot_d else None,
    }
    op_rate = op["crossed_and_decidable"] / op["decidable"] if op["decidable"] else None
    c_rate = tot_c / tot_d if tot_d else None
    # rule = "crossed and decidable", fired on controls counted as losses
    if op_rate is not None and c_rate is not None:
        m = op["crossed_and_decidable"] + (
            tot_c - sum(v["crossed_and_decidable"] for v in
                        [ctrl[c] for c in CONTROLS]))
        out["verdict"] = {
            "k_recovered": op["crossed_and_decidable"],
            "fires_on_matched": op["crossed_and_decidable"] + tot_c,
            "precision": round(op["crossed_and_decidable"] /
                               (op["crossed_and_decidable"] + tot_c), 4),
            "max_fires_allowed_at_k": 2 * op["crossed_and_decidable"] - 12,
            "budget_respected": bool(
                op["crossed_and_decidable"] + tot_c
                <= 2 * op["crossed_and_decidable"] - 12),
            "n_total_matched": len(rows),
        }
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gt", default=DEFAULT_GT)
    ap.add_argument("--diag", default=DEFAULT_DIAG)
    ap.add_argument("--calib", default=DEFAULT_CALIB)
    ap.add_argument("--json", default=DEFAULT_JSON)
    args = ap.parse_args(argv)

    blob = json.loads(Path(args.gt).read_text(encoding="utf-8"))
    fps = float(blob.get("fps") or 30.0)
    frames = load_diag(args.diag)["frames"]
    centers = tracked_centers(frames)
    rows, geom = build_rows(frames, centers, args.calib, args.gt, 9, 33, fps)

    shallow = report(rows, geom, "shallow")
    deep = report(rows, geom, "deep")

    out = {"generated_from": {"gt": args.gt, "diag": args.diag,
                              "calib": args.calib},
           "geometry": geom,
           "post_span": POST_SPAN, "min_post_frames": MIN_POST_FRAMES,
           "n_matched": len(rows),
           "shallow": shallow, "deep": deep,
           "rows": rows}
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")

    print("=" * 78)
    print("  OVERPASS VIA POST-CONTACT NET CROSSING IN y  (calibration net plane)")
    print("=" * 78)
    print(f"  net top y={geom['net_top_y']:.0f}  midcourt y={geom['midcourt_y']:.0f}"
          f"  band={geom['band_px']:.0f}px  deep threshold={geom['deep_px']:.0f}px")
    print(f"  matched contacts {len(rows)}   POST_SPAN {POST_SPAN}f"
          f"   min decidable {MIN_POST_FRAMES}f")
    for name, rep in (("shallow (0.25 band)", shallow), ("deep (0.50 band)", deep)):
        print(f"\n  --- {name}")
        print(f"    {'class':<10}{'n':>4}{'decid':>7}{'cross':>7}{'rate':>8}")
        for k in ("overpass",) + CONTROLS:
            v = rep[k]
            print(f"    {k:<10}{v['n']:>4}{v['decidable']:>7}{v['crossed']:>7}"
                  f"{('-' if v['rate'] is None else format(v['rate'], '.3f')):>8}")
        cp = rep["control_pool"]
        print(f"    {'POOL':<10}{cp['n']:>4}{cp['decidable']:>7}"
              f"{cp['crossed_and_decidable']:>7}"
              f"{('-' if cp['rate_decidable'] is None else format(cp['rate_decidable'], '.3f')):>8}")
        v = rep.get("verdict")
        if v:
            print(f"    rule fires {v['fires_on_matched']} matched "
                  f"(k={v['k_recovered']}), precision {v['precision']:.3f}; "
                  f"budget allows {v['max_fires_allowed_at_k']} "
                  f"-> {'RESPECTED' if v['budget_respected'] else 'VIOLATED'}")
    print("=" * 78)
    print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
