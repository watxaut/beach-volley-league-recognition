"""G3 -- the OVERPASS lever, signal-mined against a matched control set.

Session #76, second half.  #76 first half established the PRIZE exactly
(`scripts/probe_label_ceilings.py`): relabelling the 13 matched GT-overpass
contacts lifts the held-out bar arm 0.6131 -> 0.7080, i.e. ONE rule on ONE
class crosses the 0.70 goal bar on its own.  The MECHANISM is unsolved:
`probe_overpass_crossing.py` refuted the ball-width net-crossing lever (present
at 3/18 held-out GT overpasses vs set 4/46, dig 10/55) and the perceived
next-team lever (flip 8/18 = 0.444 vs controls 0.582), and all three replayable
rule variants were net-negative on the stream.

This probe asks the question those probes did not: **is there ANY signal in
the diag dump's per-frame context that separates an overpass contact from a
dig/set/spike contact?**  It mines a bank of per-contact features over a
MATCHED control set (same rally, same taker team, same Layer-1 gesture) and
reports, for each feature, the overpass-vs-control separation with an exact
two-sided Fisher test, so a lever is chosen on evidence rather than on taste.

DIAGNOSE ONLY: no ``src/`` change, no decode, no seek, no GT edit.  The held-out
region is not touched: everything here is IN-SAMPLE on the matched controls.

Usage:
    venv/bin/python scripts/probe_overpass_separator.py
    venv/bin/python scripts/probe_overpass_separator.py --json output/g3_overpass/separator.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from itertools import combinations

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import evaluate_timed as et  # noqa: E402
from src.utils.diagnostics import load_diag  # noqa: E402

DEFAULT_GT = "ground_truth/20260920_match_contacts.json"
DEFAULT_DIAG = "output/g3r1/match_bw03_diag.jsonl"
DEFAULT_JSON = "output/g3_overpass/separator.json"

#: Classes that must NOT be relabelled -- the false-positive control.
CONTROL_CLASSES = ("dig", "set")
PRE_SPAN = 20
POST_SPAN = 60


# ----------------------------------------------------------------------
# matching
# ----------------------------------------------------------------------

def accepted(diag_path: str) -> List[Dict[str, Any]]:
    """`stage == "accepted"` contact rows, frame-sorted."""
    out: List[Dict[str, Any]] = []
    for rec in load_diag(diag_path)["frames"].values():
        for c in rec.get("candidates") or []:
            if c.get("stage") == "accepted":
                out.append(dict(c, _frame=rec["frame"]))
    out.sort(key=lambda c: c["_frame"])
    return out


def match_to_gt(diag_path: str, gt_path: str, fps: float,
                tolerance_s: float = 0.2) -> List[Tuple[Dict[str, Any],
                                                        Dict[str, Any]]]:
    """[(contact row, GT event)] through the IMPORTED matcher."""
    blob = json.loads(Path(gt_path).read_text(encoding="utf-8"))
    ev = blob["annotated_frames"]["actions"]["events"]
    gt = [et.normalize_event(e) for e in ev if e.get("frame") is not None]
    rows = accepted(diag_path)
    by_frame = {int(c["_frame"]): c for c in rows}
    pr = [et.normalize_event({"frame": c["_frame"], "action": c.get("action"),
                              "team": c.get("team")}) for c in rows]
    tb = et.TimeBase(fps=fps)
    m = et.match_events(gt, pr, tb, base_tolerance_s=tolerance_s)
    # ``pairs`` yields the event OBJECTS, not indices.
    return [(by_frame[int(p["frame"])], g) for g, p, _d in m["pairs"]]


# ----------------------------------------------------------------------
# per-contact features
# ----------------------------------------------------------------------

def ball_series(frames: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    return frames


def width_at(frames: Dict[int, Dict[str, Any]], f: int) -> Optional[float]:
    rec = frames.get(f) or {}
    bt = rec.get("ball_track") or {}
    if not bt.get("locked") or not bt.get("center"):
        return None
    cx, cy = bt["center"]
    for det in rec.get("ball_dets") or []:
        c = det.get("center")
        if c and abs(c[0] - cx) < 1.0 and abs(c[1] - cy) < 1.0:
            b = det.get("bbox") or []
            if len(b) == 4:
                return float(b[2] - b[0])
    return None


def center_at(frames: Dict[int, Dict[str, Any]], f: int) -> Optional[Tuple[float, float]]:
    rec = frames.get(f) or {}
    bt = rec.get("ball_track") or {}
    if bt.get("locked") and bt.get("center"):
        return float(bt["center"][0]), float(bt["center"][1])
    return None


def _slope_at(frames: Dict[int, Dict[str, Any]], f: int, back: int = 3
              ) -> Optional[Tuple[float, float]]:
    """(vx, vy) px/frame from a `back`-frame regression ending at `f`.

    Gaps are bridged by the widest usable run (a tracked frame at both ends is
    required); an all-gap span yields None rather than a guess.
    """
    pts = [center_at(frames, f - k) for k in range(0, back + 1)]
    if pts[0] is None or pts[-1] is None:
        return None
    # (t, x, y) for every interior tracked frame, t counted back from `f`.
    obs = [(back - k, p[0], p[1]) for k, p in enumerate(pts)
           if p is not None]
    if len(obs) < 2:
        return None
    n = len(obs)
    mt = sum(o[0] for o in obs) / n
    mx = sum(o[1] for o in obs) / n
    my = sum(o[2] for o in obs) / n
    den = sum((o[0] - mt) ** 2 for o in obs)
    if den == 0:
        return None
    vx = sum((o[0] - mt) * (o[1] - mx) for o in obs) / den
    vy = sum((o[0] - mt) * (o[2] - my) for o in obs) / den
    return vx, vy


def features(frames: Dict[int, Dict[str, Any]], row: Dict[str, Any],
             taker: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    f = int(row["_frame"])
    cp = row.get("contact_point") or []
    cx, cy = (float(cp[0]), float(cp[1])) if len(cp) >= 2 else (None, None)

    w_pre = [width_at(frames, k) for k in range(f - PRE_SPAN, f)]
    w_post = [width_at(frames, k) for k in range(f + 1, f + POST_SPAN + 1)]
    w_pre_v = [w for w in w_pre if w is not None]
    w_post_v = [w for w in w_post if w is not None]

    v_in = _slope_at(frames, f)
    v_out = _slope_at(frames, f + 4, back=4)

    pre_x = [center_at(frames, k) for k in range(f - PRE_SPAN, f)]
    post_x = [center_at(frames, k) for k in range(f + 1, f + POST_SPAN + 1)]
    pre_x_v = [p for p in pre_x if p is not None]
    post_x_v = [p for p in post_x if p is not None]

    # image-space net crossing: the net is a near-horizontal band; use the
    # calibrated net row if the contact row carries one, else the raw y trend.
    dy_pre = (pre_x_v[-1][1] - pre_x_v[0][1]) if len(pre_x_v) >= 2 else None
    dy_post = (post_x_v[-1][1] - post_x_v[0][1]) if len(post_x_v) >= 2 else None
    dx_pre = (pre_x_v[-1][0] - pre_x_v[0][0]) if len(pre_x_v) >= 2 else None
    dx_post = (post_x_v[-1][0] - post_x_v[0][0]) if len(post_x_v) >= 2 else None

    speed_in = math.hypot(*v_in) if v_in else None
    speed_out = math.hypot(*v_out) if v_out else None
    straightness = (abs(dx_pre) / math.hypot(dx_pre, dy_pre)
                    if (dx_pre is not None and dy_pre is not None
                        and math.hypot(dx_pre, dy_pre) > 1e-6) else None)

    fy = float(row.get("departure_bw_f") or 0.0) or None
    return {
        "frame": f,
        "width_pre": sum(w_pre_v) / len(w_pre_v) if w_pre_v else None,
        "width_post": sum(w_post_v) / len(w_post_v) if w_post_v else None,
        "width_delta": ((sum(w_post_v) / len(w_post_v) - sum(w_pre_v) / len(w_pre_v))
                        if (w_pre_v and w_post_v) else None),
        "n_width_post": len(w_post_v),
        "speed_in": speed_in,
        "speed_out": speed_out,
        "speed_ratio": (speed_out / speed_in if (speed_in and speed_out
                                                 and speed_in > 1e-6) else None),
        "vy_in": v_in[1] if v_in else None,
        "vy_out": v_out[1] if v_out else None,
        "dy_pre": dy_pre,
        "dy_post": dy_post,
        "dx_pre": dx_pre,
        "dx_post": dx_post,
        "straightness": straightness,
        "departure_bw_f": fy,
        "near_net": row.get("near_net"),
        "ball_side": row.get("ball_side"),
        "kind": row.get("kind"),
        "touch_number": row.get("touch_number"),
        "gesture": row.get("gesture"),
        "team": row.get("team"),
        "reach": row.get("reach"),
        "contact_y": cy,
    }


def taker_at(frames: Dict[int, Dict[str, Any]], row: Dict[str, Any]
             ) -> Optional[Dict[str, Any]]:
    """The player whose bbox contains the contact point at that frame."""
    f = int(row["_frame"])
    cp = row.get("contact_point") or []
    if len(cp) < 2:
        return None
    rec = frames.get(f) or {}
    px, py = float(cp[0]), float(cp[1])
    best = None
    for p in rec.get("players") or []:
        b = p.get("bbox")
        if not b or len(b) != 4:
            continue
        # contact_point is the BALL's position; the taker is the NEAREST player
        dx = max(b[0] - px, 0.0, px - b[2])
        dy = max(b[1] - py, 0.0, py - b[3])
        d = math.hypot(dx, dy)
        if best is None or d < best[0]:
            best = (d, p)
    return best[1] if best else None


# ----------------------------------------------------------------------
# separation statistics
# ----------------------------------------------------------------------

def fisher_exact_2x2(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for [[a,b],[c,d]] (no scipy dependency)."""
    def logc(n, k):
        return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    n = a + b + c + d
    r1, c1 = a + b, a + c
    def prob(x):
        return math.exp(logc(r1, x) + logc(n - r1, c1 - x) - logc(n, c1))
    lo = max(0, c1 - (n - r1))
    hi = min(r1, c1)
    obs = prob(a)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1)
                         if prob(x) <= obs * (1 + 1e-9)))


def cliffs_delta(xs: Sequence[float], ys: Sequence[float]) -> float:
    """P(xs > ys) - P(xs < ys); +1 = every overpass above every control."""
    if not xs or not ys:
        return 0.0
    gt = lt = 0
    for x in xs:
        for y in ys:
            if x > y:
                gt += 1
            elif x < y:
                lt += 1
    return (gt - lt) / float(len(xs) * len(ys))


def cliff_magnitude(delta: float) -> str:
    a = abs(delta)
    if a >= 0.8:
        return "LARGE"
    if a >= 0.5:
        return "medium"
    if a >= 0.147:
        return "small"
    return "negligible"


def rank_features(rows: Sequence[Dict[str, Any]], numeric: Sequence[str]
                  ) -> List[Dict[str, Any]]:
    pos = [r for r in rows if r["_gt_action"] == "overpass"]
    neg = [r for r in rows if r["_gt_action"] in CONTROL_CLASSES]
    out = []
    for key in numeric:
        xs = [r[key] for r in pos if isinstance(r.get(key), (int, float))]
        ys = [r[key] for r in neg if isinstance(r.get(key), (int, float))]
        if len(xs) < 3 or len(ys) < 5:
            continue
        med_x = sorted(xs)[len(xs) // 2]
        med_y = sorted(ys)[len(ys) // 2]
        thr = (med_x + med_y) / 2.0
        a = sum(1 for v in xs if v > thr)
        b = len(xs) - a
        c = sum(1 for v in ys if v > thr)
        d = len(ys) - c
        delta = cliffs_delta(xs, ys)
        p = fisher_exact_2x2(a, b, c, d) if (a + b and c + d) else 1.0
        out.append({
            "feature": key,
            "n_overpass": len(xs), "n_control": len(ys),
            "median_overpass": round(med_x, 3),
            "median_control": round(med_y, 3),
            "cliff_delta": round(delta, 3),
            "magnitude": cliff_magnitude(delta),
            "fisher_p": round(p, 5),
            "threshold_at_median_midpoint": round(thr, 3),
            "overpass_above": a, "overpass_below": b,
            "control_above": c, "control_below": d,
        })
    out.sort(key=lambda r: (-abs(r["cliff_delta"]), r["fisher_p"]))
    return out


def cliffs_delta_2d(xs: Sequence[Tuple[float, ...]],
                    ys: Sequence[Tuple[float, ...]]) -> float:
    """Cliff's delta for VECTORS: fraction of (overpass, control) pairs where
    the overpass point dominates on BOTH coordinates (ties count as neither)."""
    if not xs or not ys:
        return 0.0
    gt = lt = 0
    for x in xs:
        for y in ys:
            a = sum(1 for i in range(len(x)) if x[i] > y[i])
            b = sum(1 for i in range(len(x)) if x[i] < y[i])
            if a > b:
                gt += 1
            elif b > a:
                lt += 1
    return (gt - lt) / float(len(xs) * len(ys))


def rank_pairs(rows: Sequence[Dict[str, Any]], numeric: Sequence[str],
               min_p: float = 0.05) -> List[Dict[str, Any]]:
    """Every 2-feature AND-conjunction: `x > tx AND y > ty`.

    A pair of individually-weak features can be a strong separator, so the bank
    is scanned exhaustively rather than greedily. Thresholds are placed at the
    midpoint of the two class medians (no label peeking beyond the medians
    themselves), and each rule is scored with the SAME Fisher test so pair and
    single-feature rows are directly comparable.
    """
    pos = [r for r in rows if r["_gt_action"] == "overpass"]
    neg = [r for r in rows if r["_gt_action"] in CONTROL_CLASSES]
    out: List[Dict[str, Any]] = []
    for a, b in combinations(numeric, 2):
        def usable(rs):
            return [r for r in rs
                    if isinstance(r.get(a), (int, float))
                    and isinstance(r.get(b), (int, float))]
        p_rows, n_rows = usable(pos), usable(neg)
        if len(p_rows) < 3 or len(n_rows) < 5:
            continue
        tx = (sorted(r[a] for r in p_rows)[len(p_rows) // 2]
              + sorted(r[a] for r in n_rows)[len(n_rows) // 2]) / 2.0
        ty = (sorted(r[b] for r in p_rows)[len(p_rows) // 2]
              + sorted(r[b] for r in n_rows)[len(n_rows) // 2]) / 2.0
        hit_p = sum(1 for r in p_rows if r[a] > tx and r[b] > ty)
        hit_n = sum(1 for r in n_rows if r[a] > tx and r[b] > ty)
        delta = cliffs_delta_2d([(r[a], r[b]) for r in p_rows],
                               [(r[a], r[b]) for r in n_rows])
        p = fisher_exact_2x2(hit_p, len(p_rows) - hit_p,
                             hit_n, len(n_rows) - hit_n) \
            if (hit_p and hit_n) else 1.0
        out.append({
            "feature": f"{a}&{b}", "pair": [a, b],
            "n_overpass": len(p_rows), "n_control": len(n_rows),
            "rule": f"{a} > {round(tx, 3)} AND {b} > {round(ty, 3)}",
            "threshold": [round(tx, 3), round(ty, 3)],
            "hits_overpass": hit_p, "hits_control": hit_n,
            "missed_overpass": len(p_rows) - hit_p,
            "cliff_delta": round(delta, 3),
            "magnitude": cliff_magnitude(delta),
            "fisher_p": round(p, 5),
        })
    out.sort(key=lambda r: (-abs(r["cliff_delta"]), r["fisher_p"]))
    return [r for r in out if r["fisher_p"] <= min_p]


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

NUMERIC_FEATURES = [
    "width_pre", "width_post", "width_delta", "n_width_post",
    "speed_in", "speed_out", "speed_ratio", "vy_in", "vy_out",
    "dy_pre", "dy_post", "dx_pre", "dx_post", "straightness",
    "departure_bw_f", "contact_y",
]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gt", default=DEFAULT_GT)
    ap.add_argument("--diag", default=DEFAULT_DIAG)
    ap.add_argument("--json", default=DEFAULT_JSON)
    args = ap.parse_args(argv)

    gt_blob = json.loads(Path(args.gt).read_text(encoding="utf-8"))
    fps = float(gt_blob.get("fps") or 30.0)
    frames = load_diag(args.diag)["frames"]
    pairs = match_to_gt(args.diag, args.gt, fps)

    rows: List[Dict[str, Any]] = []
    for row, g in pairs:
        f = features(frames, row, taker_at(frames, row))
        f["_gt_action"] = g["action"]
        f["_gt_frame"] = g["frame"]
        f["_gt_team"] = (g["raw"] or {}).get("player_team")
        f["_pred_action"] = row.get("action")
        f["_rally_id"] = row.get("rally_id")
        taker = taker_at(frames, row)
        f["_taker_track"] = (taker or {}).get("track_id")
        f["_taker_team"] = (taker or {}).get("team")
        rows.append(f)

    ranked = rank_features(rows, NUMERIC_FEATURES)
    pairs = rank_pairs(rows, NUMERIC_FEATURES)

    pos = [r for r in rows if r["_gt_action"] == "overpass"]
    neg = [r for r in rows if r["_gt_action"] in CONTROL_CLASSES]

    out = {
        "generated_from": {"gt": args.gt, "diag": args.diag},
        "n_matched": len(rows),
        "n_overpass": len(pos), "n_control": len(neg),
        "control_classes": list(CONTROL_CLASSES),
        "numeric_features": ranked,
        "feature_pairs": pairs,
        "overpass_rows": pos,
        "control_rows": neg,
        "label_status": {
            "overpass_predicted_as": _dist([r["_pred_action"] for r in pos]),
            "control_predicted_as": _dist([r["_pred_action"] for r in neg]),
        },
    }
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")

    print("=" * 78)
    print("  OVERPASS SEPARATOR -- matched contacts, overpass vs dig/set controls")
    print("=" * 78)
    print(f"  matched {len(rows)}   overpass {len(pos)}   controls {len(neg)}")
    print(f"  overpass predicted as: {out['label_status']['overpass_predicted_as']}")
    print(f"  controls predicted as: {out['label_status']['control_predicted_as']}")
    print()
    print(f"  {'feature':<16}{'n+':>4}{'n-':>4}{'med+':>9}{'med-':>9}"
          f"{'delta':>8}{'mag':>9}{'p':>9}")
    for r in ranked[:18]:
        print(f"  {r['feature']:<16}{r['n_overpass']:>4}{r['n_control']:>4}"
              f"{r['median_overpass']:>9.2f}{r['median_control']:>9.2f}"
              f"{r['cliff_delta']:>+8.3f}{r['magnitude']:>9}{r['fisher_p']:>9.4f}")
    print("=" * 78)
    big = [r for r in ranked if r["magnitude"] == "LARGE"]
    if big:
        print("  LARGE separators: " + ", ".join(
            f"{r['feature']} (delta {r['cliff_delta']:+.3f}, p={r['fisher_p']})"
            for r in big))
    else:
        print("  NO LARGE separator: no feature in the bank separates overpass"
              " from dig/set by >=0.8 Cliff's delta.")
    print()
    print(f"  2-feature AND-rules scanned: "
          f"{len(NUMERIC_FEATURES) * (len(NUMERIC_FEATURES) - 1) // 2}, "
          f"significant at Fisher p<=0.05: {len(pairs)}")
    for r in pairs[:15]:
        print(f"  {r['feature']:<34}{r['cliff_delta']:>+8.3f}{r['magnitude']:>9}"
              f"{r['fisher_p']:>9.4f}  {r['rule']}")
        print(f"      hits {r['hits_overpass']}/{r['n_overpass']} overpass, "
              f"{r['hits_control']}/{r['n_control']} control")
    print("=" * 78)
    if not pairs:
        print("  NO significant 2-feature separator either: overpass is not"
              " separable from dig/set by any AND of two bank features.")
    print(f"wrote {args.json}")
    return 0


def _dist(vals: Sequence[Any]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for v in vals:
        k = str(v)
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


if __name__ == "__main__":
    raise SystemExit(main())
