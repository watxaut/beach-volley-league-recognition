#!/usr/bin/env python3
"""G3 -- the set<->dig swaps: WHAT distinguishes them? (diagnose-only)

The #68 lever table (`docs/g3_touch_count_lever.md` section 3) lists "the 15
set<->dig swaps" as the largest surviving measured label lever (+0.106
in-sample) after the touch-count routes were closed (#70 TC1, #72 reach). This
probe characterises them from COMMITTED ARTIFACTS ONLY: no ``src/`` change, no
decode, no seek (AGENTS.md section 9), no GT edit, no new pipeline run, no new
Config key. The held-out session 20260928_entreno_vall_dhebron is never read.

Pre-registered decision rule (stated BEFORE looking, per the diagnose-first
protocol): the swap set is re-derived on the 139 found contacts (the dump
accepted rows matched to the in-region GT events, #68 semantics -- nearest
emission within +-15 f, non-exclusive, matcher and replay IMPORTED from
``scripts/probe_touch_rules.py``). G1 must reproduce exactly (185 accepted /
139 found / touch 96/139 / R0 replay control 79/139) before ANY swap is read;
a mismatch exits 2. A signal SEPARATES only if the GT-set group and the
GT-dig group have ZERO overlap on it (or a stated margin); anything else is
reported as overlapping and the verdict is NO SEPARATOR. No rule is designed,
nothing is implemented.

Known trap handled: gestures are passed to ``_decide`` as the
``VisualGesture`` enum via ``probe_touch_rules.replay_decide`` (a plain
string silently skips the ATTACK/BLOCK branches).

Usage::

    venv/bin/python scripts/probe_set_dig_swaps.py
    venv/bin/python scripts/probe_set_dig_swaps.py --json output/swaps/report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The matcher, the loaders and the replay are IMPORTED, never re-implemented.
import probe_touch_rules as pt  # noqa: E402
import evaluate_timed as et  # noqa: E402
import score_heldout_contacts as sh  # noqa: E402

from src.detection.court_calibration import CourtCalibration  # noqa: E402

REPO = pt.REPO
MATCH_CALIB = "calibrations/20260920_match_ari_joan_lost.json"

#: Kinematics window, in frames (~0.31 s at the match's 25.67 fps). The pairs
#: that STRADDLE the contact ((f-1,f) and (f,f+1)) are excluded from both the
#: "before" and the "after" window so neither side contains the deflection
#: itself. Fixed, not tuned.
WINDOW_F = 8

#: G1 -- the four numbers this session must reproduce EXACTLY before reading
#: any swap (#68 / CARD TC1's corrected baseline).
G1_EXPECT = {"accepted": 185, "found": 139, "touch_correct": 96,
             "r0_correct": 79}

#: #68's swap count, measured on the production stream -- reconciled against,
#: never forced onto, the dump-derived count.
N68_PRODUCTION_SWAPS = 15

SWAP_PAIRS = {("set", "dig"), ("dig", "set")}


# ----------------------------------------------------------------------
# loaders
# ----------------------------------------------------------------------

def load_frame_index(path: str) -> Dict[int, Dict[str, Any]]:
    """frame -> {ball, players} of the per-frame diag records (one pass)."""
    out: Dict[int, Dict[str, Any]] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        fr = rec.get("frame")
        if fr is None or int(fr) < 0:
            continue
        out[int(fr)] = {"ball": rec.get("ball_track") or {},
                        "players": rec.get("players") or []}
    return out


def ball_center(frames: Dict[int, Dict[str, Any]],
                f: int) -> Optional[Tuple[float, float]]:
    bt = frames.get(f, {}).get("ball") or {}
    c = bt.get("center")
    return (float(c[0]), float(c[1])) if c else None


def nearest_ball_center(frames, f: int,
                        slack: int = 2) -> Tuple[Optional[Tuple[float, float]], Optional[int]]:
    """The ball center at ``f`` or the nearest frame within +-slack."""
    for d in (0, -1, 1, -2, 2):
        c = ball_center(frames, f + d)
        if c is not None:
            return c, f + d
    return None, None


def kinematics(frames: Dict[int, Dict[str, Any]], f: int,
               w: int = WINDOW_F) -> Dict[str, Any]:
    """Vertical/horizontal ball motion strictly before vs strictly after ``f``.

    vy is in px/frame on the dumped image axis (y grows DOWNWARD): negative =
    rising, positive = dropping. Pairs straddling the contact frame are
    excluded from both sides (see WINDOW_F). Speeds are mean per-frame
    displacement magnitudes over the same pairs. Only frames the tracker
    actually reported are used; ``n_in``/``n_out`` record how many.
    """
    cin: List[Tuple[float, float]] = []
    cout: List[Tuple[float, float]] = []
    for i in range(f - w, f + w + 1):
        c = ball_center(frames, i)
        if c is not None:
            cin.append((i, c)) if i < f else cout.append((i, c))
    pairs_in = [(a, b) for (fa, a), (fb, b) in zip(cin, cin[1:])
                if fb == fa + 1 and fb < f]
    pairs_out = [(a, b) for (fa, a), (fb, b) in zip(cout, cout[1:])
                 if fb == fa + 1 and fa >= f]

    def _vy(pairs):
        return (sum(b[1] - a[1] for a, b in pairs) / len(pairs)) if pairs else None

    def _sp(pairs):
        return (sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
                    for a, b in pairs) / len(pairs)) if pairs else None

    at, at_f = nearest_ball_center(frames, f)
    return {"ball_xy_px": at, "ball_at_frame": at_f,
            "n_in": len(pairs_in), "n_out": len(pairs_out),
            "vy_in": _vy(pairs_in), "vy_out": _vy(pairs_out),
            "speed_in": _sp(pairs_in), "speed_out": _sp(pairs_out)}


def taker_position(frames: Dict[int, Dict[str, Any]], f: int, track_id: int,
                   calib: CourtCalibration,
                   net_top: Tuple[Tuple[float, float], Tuple[float, float]]
                   ) -> Dict[str, Any]:
    """The touching player's bbox center / feet world point / zone at ``f``."""
    rec = None
    for d in (0, -1, 1, -2, 2):
        pl = frames.get(f + d, {}).get("players") or []
        if any(p.get("track_id") == track_id for p in pl):
            rec = next(p for p in pl if p.get("track_id") == track_id)
            f_used = f + d
            break
    if rec is None:
        return {"found": False}
    x1, y1, x2, y2 = [float(v) for v in rec["bbox"]]
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    feet = ((x1 + x2) / 2.0, y2)
    world = calib.image_to_world((int(feet[0]), int(feet[1])))
    zone = calib.world_point_to_zone(*world) if world else None
    return {"found": True, "frame": f_used, "bbox_center_px": (cx, cy),
            "feet_world_m": (round(world[0], 2), round(world[1], 2))
            if world else None,
            "zone": zone, "predicted": bool(rec.get("predicted"))}


def net_top_y(net_top: Tuple[Tuple[float, float], Tuple[float, float]],
              x: float) -> float:
    """Linear interpolation of the net-top line's y at image x."""
    (xa, ya), (xb, yb) = net_top
    if xb == xa:
        return ya
    return ya + (x - xa) * (yb - ya) / (xb - xa)


def load_net_top() -> Tuple[Tuple[float, float], Tuple[float, float]]:
    blob = json.loads((REPO / MATCH_CALIB).read_text(encoding="utf-8"))
    a, b = blob["net_top_points"][:2]
    return (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))


# ----------------------------------------------------------------------
# G1 -- reproduce #68 BEFORE any swap is read
# ----------------------------------------------------------------------

def g1() -> Tuple[Dict[str, Any], Dict[str, int]]:
    contacts = pt.load_diag_accepted(str(REPO / pt.MATCH_DIAG))
    events = pt.load_match_events(str(REPO / pt.MATCH_GT), *pt.HELDOUT_REGION)
    pairs, mstats = pt.match_contacts(events, contacts)
    r0_touch = pt.rule_r0(contacts)
    touch_acc = pt.touch_accuracy(contacts, pairs, r0_touch)
    r0_labels = pt.replay_decide(contacts, r0_touch)
    r0_score = pt.score_labels(pairs, contacts, r0_labels)
    got = {"accepted": len(contacts), "found": mstats["n_found"],
           "touch_correct": touch_acc["correct"],
           "r0_correct": r0_score["correct"]}
    mismatch = {k: (v, G1_EXPECT[k]) for k, v in got.items() if v != G1_EXPECT[k]}
    return {"contacts": contacts, "events": events, "pairs": pairs,
            "r0_labels": r0_labels, "got": got, "mismatch": mismatch}, mismatch


# ----------------------------------------------------------------------
# the swap set
# ----------------------------------------------------------------------

def swap_rows(data: Dict[str, Any], frames, calib, net_top
              ) -> List[Dict[str, Any]]:
    """One row per set<->dig swap among the found contacts, with all signals.

    The label compared is the dump's OWN ``action`` field; the R0 replay label
    is computed too and asserted IDENTICAL on the swap set (both streams swap
    the same contacts, verified in-session before this probe was written).
    """
    contacts, events, pairs = data["contacts"], data["events"], data["pairs"]
    by_point: Dict[int, List[Dict[str, Any]]] = {}
    for e in events:
        by_point.setdefault(int(e["point"]), []).append(e)
    for pt_ in by_point:
        by_point[pt_].sort(key=lambda x: int(x["frame"]))

    rows: List[Dict[str, Any]] = []
    for e, c in pairs:
        if c is None:
            continue
        gt_act, pred_act = e["final_action"], c["action"]
        if (gt_act, pred_act) not in SWAP_PAIRS:
            continue
        i = pt.index_of(contacts, c)
        replay_label = data["r0_labels"][i]
        assert replay_label == pred_act, (
            f"dump/replay label disagree on swap f{c['frame']}: "
            f"{pred_act} vs {replay_label}")

        f = int(c["frame"])
        kin = kinematics(frames, f)
        taker = taker_position(frames, f, int(c["track_id"]), calib, net_top)
        ball = kin["ball_xy_px"]
        above_net = None
        if ball is not None:
            above_net = round(net_top_y(net_top, ball[0]) - ball[1], 1)

        evs = by_point[int(e["point"])]
        k = next((j for j, x in enumerate(evs)
                  if int(x["frame"]) == int(e["frame"])), None)
        prev_ev = evs[k - 1] if (k is not None and k > 0) else None
        next_ev = evs[k + 1] if (k is not None and k + 1 < len(evs)) else None

        rows.append({
            "point": int(e["point"]),
            "gt_frame": int(e["frame"]), "contact_frame": f,
            "delta_f": int(e["frame"]) - f,
            "gt_action": gt_act, "pred_action": pred_act,
            "group": f"GT-{gt_act}",
            "gt_touch": int(e["touch_number"]),
            "emitted_touch": int(c["touch_number"]),
            "touch_correct": int(c["touch_number"]) == int(e["touch_number"]),
            "gt_team": e.get("player_team"), "emitted_team": c.get("team"),
            "team_match": e.get("player_team") == c.get("team"),
            "gesture": c["gesture"], "near_net": bool(c["near_net"]),
            "ball_side": c.get("ball_side"), "kind": c.get("kind"),
            "rally_id": int(c["rally_id"]),
            "ball_xy_px": [round(v, 1) for v in ball] if ball else None,
            "ball_above_net_px": above_net,
            "vy_in": round(kin["vy_in"], 2) if kin["vy_in"] is not None else None,
            "vy_out": round(kin["vy_out"], 2) if kin["vy_out"] is not None else None,
            "speed_in": round(kin["speed_in"], 2) if kin["speed_in"] is not None else None,
            "speed_out": round(kin["speed_out"], 2) if kin["speed_out"] is not None else None,
            "n_in": kin["n_in"], "n_out": kin["n_out"],
            "taker_zone": taker.get("zone"),
            "taker_feet_world_m": taker.get("feet_world_m"),
            "taker_center_px": [round(v, 1) for v in taker["bbox_center_px"]]
            if taker.get("found") else None,
            "prev_gt": None if prev_ev is None else
            (int(prev_ev["frame"]), prev_ev["final_action"],
             int(prev_ev["touch_number"])),
            "next_gt": None if next_ev is None else
            (int(next_ev["frame"]), next_ev["final_action"],
             int(next_ev["touch_number"])),
        })
    rows.sort(key=lambda r: (r["gt_frame"], r["point"]))
    return rows


def production_stream_swaps() -> List[Dict[str, Any]]:
    """The #68 count: set<->dig confusion on the pipeline_output.json stream.

    One-to-one ``evaluate_timed`` matching (the 83/141 = 0.589 base the #68
    lever table was measured on), imported -- the same machinery
    ``probe_touch_rules.pipeline_output_score`` uses.
    """
    blob = json.loads((REPO / pt.MATCH_GT).read_text(encoding="utf-8"))
    scoped = sh.scoped_gt_blob(blob, pt.SHALLOW_PT_LO, pt.SHALLOW_PT_HI)
    timebase = et.resolve_timebase(scoped, scoped)
    gt_events = [et.normalize_event(e) for e in sh.gt_contacts(scoped)]
    acts = [a for a in pt.load_pipeline_actions(str(REPO / pt.MATCH_PIPELINE))
            if pt.HELDOUT_REGION[0] <= a["frame"] <= pt.HELDOUT_REGION[1]]
    m = et.match_events(gt_events,
                        [{"frame": int(a["frame"]), "action": a["action"]}
                         for a in acts], timebase, 0.2)
    out = []
    for g, p, _d in m["pairs"]:
        if (g["action"], p["action"]) in SWAP_PAIRS:
            out.append({"gt_frame": int(g["frame"]), "gt_action": g["action"],
                        "pred_action": p["action"],
                        "pred_frame": int(p["frame"])})
    out.sort(key=lambda r: r["gt_frame"])
    return out


def reconcile(prod_swaps: Sequence[Dict[str, Any]],
              rows: Sequence[Dict[str, Any]],
              contacts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Where the #68 production-stream count and the dump count differ."""
    dump_frames = {r["gt_frame"] for r in rows}
    prod_frames = {s["gt_frame"] for s in prod_swaps}
    extras = sorted(prod_frames - dump_frames)
    missing = sorted(dump_frames - prod_frames)
    detail = []
    for gf in extras:
        near = [c for c in contacts if abs(int(c["frame"]) - gf) <= pt.TOLERANCE_F]
        prod = [s for s in prod_swaps if s["gt_frame"] == gf]
        detail.append({
            "gt_frame": gf,
            "gt_action": prod[0]["gt_action"],
            "production_action": prod[0]["pred_action"],
            "production_pred_frame": prod[0]["pred_frame"],
            "dump_accepted_nearby": [
                {"frame": int(c["frame"]), "action": c["action"],
                 "touch": int(c["touch_number"]), "team": c.get("team")}
                for c in near],
        })
    return {"production_count": len(prod_frames),
            "dump_count": len(dump_frames),
            "extras_in_production_only": extras,
            "in_dump_only": missing,
            "extra_detail": detail}


# ----------------------------------------------------------------------
# group comparison
# ----------------------------------------------------------------------

def cliffs_delta(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    if not xs or not ys:
        return None
    gt_ = sum(1 for x in xs for y in ys if x > y)
    lt_ = sum(1 for x in xs for y in ys if x < y)
    return round((gt_ - lt_) / (len(xs) * len(ys)), 3)


NUMERIC_SIGNALS = ("ball_above_net_px", "vy_in", "vy_out",
                   "speed_in", "speed_out")
CATEGORICAL_SIGNALS = ("gesture", "near_net", "ball_side", "kind",
                       "team_match", "touch_correct", "taker_zone")


def _vals(rows: Sequence[Dict[str, Any]], key: str) -> List[Any]:
    return [r[key] for r in rows if r.get(key) is not None]


def _median(v: Sequence[float]) -> float:
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def compare_groups(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    gs = [r for r in rows if r["gt_action"] == "set"]
    gd = [r for r in rows if r["gt_action"] == "dig"]
    out: Dict[str, Any] = {"n_gt_set": len(gs), "n_gt_dig": len(gd),
                           "numeric": {}, "categorical": {}}
    for key in NUMERIC_SIGNALS:
        vs, vd = _vals(gs, key), _vals(gd, key)
        entry = {
            "gt_set": {"n": len(vs), "median": _median(vs) if vs else None,
                       "min": min(vs) if vs else None,
                       "max": max(vs) if vs else None},
            "gt_dig": {"n": len(vd), "median": _median(vd) if vd else None,
                       "min": min(vd) if vd else None,
                       "max": max(vd) if vd else None},
            "cliffs_delta": cliffs_delta(vs, vd),
        }
        if vs and vd:
            lo_gap = min(max(vs), max(vd)) - max(min(vs), min(vd))
            entry["overlap_span"] = round(lo_gap, 2)
            entry["zero_overlap"] = (max(min(vs), min(vd))
                                     > min(max(vs), max(vd)))
        out["numeric"][key] = entry
    for key in CATEGORICAL_SIGNALS:
        out["categorical"][key] = {
            "gt_set": dict(Counter(str(r.get(key)) for r in gs)),
            "gt_dig": dict(Counter(str(r.get(key)) for r in gd)),
        }
    return out


def verdict(cmp_: Dict[str, Any]) -> Dict[str, Any]:
    """The pre-registered decision: zero-overlap numeric signal, or none."""
    seps = [k for k, v in cmp_["numeric"].items() if v.get("zero_overlap")]
    tried = (list(cmp_["numeric"]) + list(cmp_["categorical"]))
    if seps:
        return {"verdict": "SEPARATOR FOUND", "signals": seps,
                "evidence": {k: cmp_["numeric"][k] for k in seps},
                "tried": tried}
    return {"verdict": "NO SEPARATOR", "signals": [], "tried": tried}


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def derive() -> Dict[str, Any]:
    """Everything, deterministically, from the committed artifacts."""
    data, mismatch = g1()
    if mismatch:
        return {"gate": "G1_FAILED", "mismatch": mismatch}
    frames = load_frame_index(str(REPO / pt.MATCH_DIAG))
    calib = CourtCalibration(calibration_path=str(REPO / MATCH_CALIB))
    net_top = load_net_top()
    rows = swap_rows(data, frames, calib, net_top)
    prod = production_stream_swaps()
    rec = reconcile(prod, rows, data["contacts"])
    cmp_ = compare_groups(rows)
    v = verdict(cmp_)
    return {"gate": "G1_GREEN", "g1": data["got"], "swaps": rows,
            "reconciliation": rec, "comparison": cmp_, "verdict": v}


def _fmt(v: Any) -> str:
    return "-" if v is None else str(v)


def print_report(res: Dict[str, Any]) -> None:
    if res["gate"] != "G1_GREEN":
        print("GATE G1 FAILED:", res["mismatch"])
        return
    g = res["g1"]
    print("=== G1 -- #68 reproduced BEFORE any swap is read ===")
    print(f"  accepted {g['accepted']} / found {g['found']} / "
          f"touch {g['touch_correct']}/{g['found']} / "
          f"R0 replay control {g['r0_correct']}/{g['found']}"
          f"   (expect 185 / 139 / 96/139 / 79/139)")
    print("  GATE G1 GREEN")
    print("")
    rows = res["swaps"]
    rec = res["reconciliation"]
    print("=== the set<->dig swap set (the 139 found contacts) ===")
    print(f"  dump-derived swaps : {len(rows)}  "
          f"(GT-set->dig {sum(1 for r in rows if r['gt_action'] == 'set')}, "
          f"GT-dig->set {sum(1 for r in rows if r['gt_action'] == 'dig')})")
    print(f"  #68 production-stream count: {rec['production_count']}"
          f"   (reconciled: {rec['extras_in_production_only'] or 'none'} "
          f"production-only, {rec['in_dump_only'] or 'none'} dump-only)")
    print("  columns: P | GTf->cf d | GT->pred | tGt/tEm ok | teamGT/teamEm "
          "match | gesture near side kind | ballY aboveNet vyIn vyOut spIn "
          "spOut (nIn/nOut) | zone | feet_m | prevGT | nextGT")
    for r in rows:
        print("   P%-3d f%-6d->%-6d %+3d | %-3s->%-3s | %d/%d %-3s | "
              "%s/%s %-5s | %-8s %-5s %-4s %-6s | y=%-7s %+6.1f | "
              "vy %+-7s -> %+-7s | sp %-6s -> %-6s (%d/%d) | %-4s | %-9s | "
              "%s | %s" % (
                  r["point"], r["gt_frame"], r["contact_frame"], r["delta_f"],
                  r["gt_action"], r["pred_action"], r["gt_touch"],
                  r["emitted_touch"], "OK" if r["touch_correct"] else "BAD",
                  r["gt_team"], r["emitted_team"],
                  "same" if r["team_match"] else "DIFF",
                  r["gesture"], r["near_net"], r["ball_side"], r["kind"],
                  r["ball_xy_px"][1] if r["ball_xy_px"] else None,
                  r["ball_above_net_px"] or 0,
                  r["vy_in"], r["vy_out"], r["speed_in"], r["speed_out"],
                  r["n_in"], r["n_out"],
                  "%s%s" % (r["taker_zone"][1], r["taker_zone"][0])
                  if r["taker_zone"] else None,
                  r["taker_feet_world_m"],
                  "%s@f%d t%d" % (r["prev_gt"][1], r["prev_gt"][0],
                                     r["prev_gt"][2])
                  if r["prev_gt"] else "none",
                  "%s@f%d t%d" % (r["next_gt"][1], r["next_gt"][0],
                                     r["next_gt"][2])
                  if r["next_gt"] else "none"))
    print("")
    for d in rec["extra_detail"]:
        print("  [reconciled production-only swap] GT f%d %s: production "
              "emitted %s at f%d; dump accepted nearby: %s" % (
                  d["gt_frame"], d["gt_action"], d["production_action"],
                  d["production_pred_frame"], d["dump_accepted_nearby"]))
    print("")
    cmp_ = res["comparison"]
    print("=== group comparison (GT-set swaps n=%d vs GT-dig swaps n=%d) ==="
          % (cmp_["n_gt_set"], cmp_["n_gt_dig"]))
    print("  numeric (median [min..max], Cliff's delta; vy in px/f, "
          "y grows DOWN):")
    for k, v in cmp_["numeric"].items():
        s, d = v["gt_set"], v["gt_dig"]
        print("    %-18s set: %s [%s..%s]  dig: %s [%s..%s]  delta %+0.3f"
              "  overlap_span %s  zero-overlap %s" % (
                  k, _fmt(s["median"]), _fmt(s["min"]), _fmt(s["max"]),
                  _fmt(d["median"]), _fmt(d["min"]), _fmt(d["max"]),
                  v.get("cliffs_delta") if v.get("cliffs_delta") is not None
                  else float("nan"),
                  _fmt(v.get("overlap_span")), v.get("zero_overlap")))
    print("  categorical (counts):")
    for k, v in cmp_["categorical"].items():
        print("    %-14s set: %-46s dig: %s" % (k, v["gt_set"], v["gt_dig"]))
    print("")
    v = res["verdict"]
    print("=== verdict (pre-registered: zero overlap or a stated margin) ===")
    if v["verdict"] == "SEPARATOR FOUND":
        for k in v["signals"]:
            e = v["evidence"][k]
            print(f"  SEPARATOR FOUND: {k} -- set [{e['gt_set']['min']}.."
                  f"{e['gt_set']['max']}] vs dig [{e['gt_dig']['min']}.."
                  f"{e['gt_dig']['max']}], Cliff's delta "
                  f"{e['cliffs_delta']:+.3f}")
    else:
        print("  NO SEPARATOR -- signals tried: " + ", ".join(v["tried"]))
    print("")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", default=None, help="write the full report here")
    args = ap.parse_args(argv)

    res = derive()
    print_report(res)
    if args.json:
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, indent=1, default=str) + "\n",
                     encoding="utf-8")
        print(f"wrote {p}")
    return 0 if res["gate"] == "G1_GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
