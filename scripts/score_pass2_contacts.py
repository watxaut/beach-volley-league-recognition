"""S0b -- contact-level score of the pass-2 serve re-label stream (G3).

`output/serve_relabel.json` reports a POINT-level census ("far prefix 8/8",
"31 serve-typed actions").  This script measures the same stream at CONTACT
level, against the owner-dictated contact GT of match P1-P8, with the
time-matched matcher of `scripts/evaluate_timed.py` (imported, never
re-implemented -- same matcher as the T4 waterfall, so the numbers are
comparable).

Two arms over the SAME scoped action list:

  perception : the production stream exactly as emitted (`action` / `team`)
  pass2      : `actions_pass2` (demoted serves dropped, `pass2_action` /
               `pass2_team` applied)

Scope = the first N GT point windows, padded by `--pad` frames on each side
(default 90 = `rally_reset_gap`).  The point windows themselves are NOT
rally-inclusive (7 of the 28 owner contacts fall outside them, the P1 serve
f210 among them), so scoring inside them would manufacture false negatives;
padding by the rally-reset gap reproduces the dev-clip T4 baseline exactly
(P 0.586 / R 0.607 / F1 0.597), which is asserted as a parity gate.

NO video is decoded, NO `src/` file is touched: this is pass-2 post-hoc
scoring (AGENTS.md section 6).  `--autonomous` is deliberately NOT used --
the pass-2 stream carries owner anchors/verdicts -- but the GT-derived-input
findings are recorded in the report instead of being silently ignored.

Usage:
    venv/bin/python scripts/score_pass2_contacts.py
    venv/bin/python scripts/score_pass2_contacts.py --json output/pass2_contacts/s0b.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import evaluate_timed as et  # noqa: E402  (path set above)

REPO = Path(__file__).resolve().parent.parent

DEFAULT_RELABEL = "output/serve_relabel.json"
DEFAULT_GT = ("ground_truth/video_ari_joan_8_first_points_annotations.json")
DEFAULT_WORKDIR = "output/pass2_contacts"
DEFAULT_PAD = 90  # rally_reset_gap frames

ARMS = ("perception", "pass2")

# The T4 dev-clip baseline (session 36).  The perception arm must reproduce
# it: same matcher, same tolerance, same scope definition.  If it does not,
# the scope or the stream drifted and every other number here is void.
# The record is 3-dp rounded, so parity is asserted at 1e-3.
PARITY_TOL = 1e-3
T4_BASELINE = {
    "precision": 0.586,
    "recall": 0.607,
    "f1": 0.597,
    "duplicates": 1,
    "fp_per_dead_minute": 2.703,
    "class_accuracy": 0.7059,
    "team_accuracy": 0.7059,
}

# GT far-side serve contacts (owner dictation, match P1-P8).  Sessions 42/44
# tracked these as the far-serve CONTACT gap.
FAR_SERVE_GT_FRAMES = (210, 880, 2154, 3038, 4770)


# ----------------------------------------------------------------------
# pure helpers
# ----------------------------------------------------------------------

def gt_point_windows(gt_blob: Dict[str, Any], n_points: Optional[int] = None
                     ) -> List[Tuple[int, int]]:
    """[(start_frame, end_frame)] of the first `n_points` GT points.

    Prefers the MATCH frame axis (`match_start_frame`), falling back to the
    clip-local one, so the scope is comparable with the match-frame actions.
    """
    out: List[Tuple[int, int]] = []
    for p in (gt_blob.get("points") or []):
        start = p.get("match_start_frame", p.get("clip_start_frame"))
        end = p.get("match_end_frame", p.get("clip_end_frame"))
        if start is None or end is None:
            continue
        out.append((int(start), int(end)))
        if n_points is not None and len(out) >= n_points:
            break
    return out


def region(windows: Sequence[Tuple[int, int]], pad: int = DEFAULT_PAD
           ) -> Tuple[int, int]:
    """Scoring region: first window start - pad .. last window end + pad."""
    if not windows:
        raise ValueError("no GT point windows")
    return windows[0][0] - pad, windows[-1][1] + pad


def in_region(frame: int, lo: int, hi: int) -> bool:
    return lo <= frame <= hi


def gt_contacts(gt_blob: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The owner-dictated contact events (the authoritative contact list)."""
    ev = (gt_blob.get("annotated_frames") or {}).get("actions", {}).get("events")
    if ev is None:
        ev = gt_blob.get("events") or []
    return [e for e in ev if isinstance(e, dict) and e.get("frame") is not None]


def scoped_actions(actions: Sequence[Dict[str, Any]], lo: int, hi: int
                   ) -> List[Dict[str, Any]]:
    return [a for a in actions
            if a.get("frame_number") is not None and in_region(int(a["frame_number"]), lo, hi)]


def arm_events(actions: Sequence[Dict[str, Any]], arm: str) -> List[Dict[str, Any]]:
    """Prediction events for one arm, in `evaluate_timed`'s expected shape.

    perception: the production stream verbatim (no pass-2 field is read).
    pass2:      owner-FALSE demotions removed, `pass2_action` / `pass2_team`
                applied (the fields the downstream layers are told to consume).
    """
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r} (expected one of {ARMS})")
    out: List[Dict[str, Any]] = []
    for a in actions:
        f = a.get("frame_number")
        if f is None:
            continue
        if arm == "pass2" and a.get("pass2_demoted"):
            continue
        ev = {
            "frame": int(f),
            "action": a.get("action"),
            "team": a.get("team"),
            "player_id": a.get("player_id"),
            "touch_number": a.get("touch_number"),
        }
        if arm == "pass2":
            ev["action"] = a.get("pass2_action", a.get("action"))
            ev["team"] = a.get("pass2_team", a.get("team"))
        out.append(ev)
    return out


def prediction_blob(events: Sequence[Dict[str, Any]], video: str,
                    fps: Optional[float]) -> Dict[str, Any]:
    blob: Dict[str, Any] = {"video": video, "actions": list(events)}
    if fps:
        blob["fps"] = float(fps)
    return blob


def nearest_actions(frame: int, actions: Sequence[Dict[str, Any]],
                    search_f: int = 80) -> List[Dict[str, Any]]:
    """Actions within +/-`search_f` of a GT contact, nearest first."""
    near = [a for a in actions if abs(int(a["frame_number"]) - frame) <= search_f]
    return sorted(near, key=lambda a: abs(int(a["frame_number"]) - frame))


def serve_rows(gt_events: Sequence[Dict[str, Any]],
               actions: Sequence[Dict[str, Any]], search_f: int = 80
               ) -> List[Dict[str, Any]]:
    """Per GT serve contact: the emitted / relabeled action nearest to it."""
    rows = []
    for e in gt_events:
        if e.get("final_action") != "serve" and e.get("action") != "serve":
            continue
        f = int(e["frame"])
        cands = []
        for a in nearest_actions(f, actions, search_f):
            cands.append({
                "frame": int(a["frame_number"]),
                "delta_f": int(a["frame_number"]) - f,
                "action": a.get("action"),
                "pass2_action": a.get("pass2_action", a.get("action")),
                "pass2_source": a.get("pass2_source"),
                "pass2_demoted": bool(a.get("pass2_demoted")),
            })
        rows.append({
            "gt_frame": f,
            "gt_side": e.get("owner_side"),
            "candidates": cands,
            "nearest_far_serve_f": next(
                (c["frame"] for c in cands if c["pass2_action"] == "serve"), None),
        })
    return rows


def far_serve_score(rows: Sequence[Dict[str, Any]], tolerance_s: float,
                    fps: float) -> Dict[str, Any]:
    """How many GT far-side serves does the pass-2 stream hit in tolerance?"""
    tol_f = tolerance_s * fps
    far = [r for r in rows if r["gt_side"] == "far"]
    hits = [r for r in far
            if r["nearest_far_serve_f"] is not None
            and abs(r["nearest_far_serve_f"] - r["gt_frame"]) <= tol_f]
    return {
        "gt_far_serves": len(far),
        "hit_within_tolerance": len(hits),
        "hit_frames": [r["gt_frame"] for r in hits],
        "tolerance_f": round(tol_f, 2),
        "rows": [
            {"gt_frame": r["gt_frame"],
             "nearest_far_serve_f": r["nearest_far_serve_f"],
             "delta_f": (None if r["nearest_far_serve_f"] is None
                         else r["nearest_far_serve_f"] - r["gt_frame"])}
            for r in far
        ],
    }


def per_contact_rows(gt_blob: Dict[str, Any], gt_path: str, arm_preds: Dict[str, List[Dict[str, Any]]],
                     tolerance_s: float) -> List[Dict[str, Any]]:
    """One row per GT contact: what each arm matched there, and what changed.

    Built from `evaluate_timed`'s own matcher (not a re-implementation) so the
    rows cannot disagree with the scores above.
    """
    gt = et.load_ground_truth(gt_path)
    fps = float(gt_blob.get("fps") or 0.0)
    timebase = et.resolve_timebase(gt_blob, {"fps": fps} if fps else {})
    by_gt_frame: Dict[int, Dict[int, Any]] = {}
    for arm, events in arm_preds.items():
        match = et.match_events(gt["events"], events, timebase, tolerance_s)
        for g, p, dt in match["pairs"]:
            by_gt_frame.setdefault(int(g["frame"]), {})[arm] = {
                "frame": p["frame"],
                "action": p["action"],
                "label_ok": p["action"] == g["action"],
                "team_ok": (None if g.get("team") is None or p.get("team") is None
                            else p["team"] == g["team"]),
                "delta_s": round(dt, 3),
            }
        for g in match["unmatched_gt"]:
            by_gt_frame.setdefault(int(g["frame"]), {}).setdefault(arm, None)
    rows = []
    for e in gt_contacts(gt_blob):
        f = int(e["frame"])
        entry = by_gt_frame.get(f, {})
        perc, p2 = entry.get("perception"), entry.get("pass2")
        change = "same"
        if perc is None and p2 is None:
            change = "missed by both"
        elif perc is None:
            change = "GAINED by pass2"
        elif p2 is None:
            change = "LOST by pass2"
        elif not perc["label_ok"] and p2["label_ok"]:
            change = "label FIXED by pass2"
        elif perc["label_ok"] and not p2["label_ok"]:
            change = "label BROKEN by pass2"
        elif p2["action"] != perc["action"] or p2["frame"] != perc["frame"]:
            change = "relabelled/moved by pass2"
        rows.append({
            "gt_frame": f,
            "gt_action": e.get("final_action") or e.get("action"),
            "gt_team": e.get("player_team"),
            "gt_side": e.get("owner_side"),
            "perception": perc,
            "pass2": p2,
            "change": change,
        })
    return rows


def parity(res: Dict[str, Any], baseline: Dict[str, Any] = T4_BASELINE
           ) -> Dict[str, Any]:
    """Does the perception arm reproduce the recorded T4 dev-clip numbers?"""
    got = {
        "precision": res["contact"]["precision"],
        "recall": res["contact"]["recall"],
        "f1": res["contact"]["f1"],
        "duplicates": res["contact"]["duplicates"],
        "fp_per_dead_minute": res["dead_time"].get("fp_per_dead_minute"),
        "class_accuracy": res["labels"]["class_accuracy"],
        "team_accuracy": res["attribution"]["team_accuracy"],
    }
    diffs = {k: (None if got[k] is None or baseline.get(k) is None
                 else round(got[k] - baseline[k], 4)) for k in baseline}
    return {"baseline": dict(baseline), "observed": got, "delta": diffs,
            "tolerance": PARITY_TOL,
            "parity": all(d is not None and abs(d) <= PARITY_TOL
                          for d in diffs.values())}


def arm_delta(perception: Dict[str, Any], pass2: Dict[str, Any]) -> Dict[str, Any]:
    def d(a: Optional[float], b: Optional[float]) -> Optional[float]:
        return None if a is None or b is None else round(b - a, 4)
    return {
        "contact_f1": d(perception["contact"]["f1"], pass2["contact"]["f1"]),
        "contact_precision": d(perception["contact"]["precision"],
                               pass2["contact"]["precision"]),
        "contact_recall": d(perception["contact"]["recall"],
                            pass2["contact"]["recall"]),
        "class_accuracy": d(perception["labels"]["class_accuracy"],
                            pass2["labels"]["class_accuracy"]),
        "team_accuracy": d(perception["attribution"]["team_accuracy"],
                           pass2["attribution"]["team_accuracy"]),
        "tp": pass2["contact"]["tp"] - perception["contact"]["tp"],
        "fp": pass2["contact"]["fp"] - perception["contact"]["fp"],
        "fn": pass2["contact"]["fn"] - perception["contact"]["fn"],
    }


# ----------------------------------------------------------------------
# orchestration
# ----------------------------------------------------------------------

def run(relabel_path: str = DEFAULT_RELABEL, gt_path: str = DEFAULT_GT,
        workdir: str = DEFAULT_WORKDIR, n_points: Optional[int] = 8,
        pad: int = DEFAULT_PAD, tolerance_s: float = 0.2,
        search_f: int = 80) -> Dict[str, Any]:
    relabel = json.loads(Path(relabel_path).read_text(encoding="utf-8"))
    gt_blob = json.loads(Path(gt_path).read_text(encoding="utf-8"))

    windows = gt_point_windows(gt_blob, n_points)
    lo, hi = region(windows, pad)
    all_actions = relabel.get("actions_pass2") or []
    if not all_actions:
        raise SystemExit(f"Error: no actions_pass2 in {relabel_path}")
    actions = scoped_actions(all_actions, lo, hi)
    gt_ev = gt_contacts(gt_blob)

    fps = float(gt_blob.get("fps") or 0.0)
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)

    results: Dict[str, Any] = {}
    arm_preds: Dict[str, List[Dict[str, Any]]] = {}
    for arm in ARMS:
        events = arm_events(actions, arm)
        arm_preds[arm] = events
        pred_path = work / f"pred_{arm}.json"
        pred_path.write_text(
            json.dumps(prediction_blob(events, relabel.get("video", ""), fps),
                       indent=1) + "\n", encoding="utf-8")
        res = et.evaluate_timed(str(pred_path), gt_path,
                                tolerance_s=tolerance_s, ignore_player=True,
                                autonomous=False)
        results[arm] = res
        results[arm]["_predictions"] = str(pred_path)

    rows = serve_rows(gt_ev, all_actions, search_f)
    out = {
        "generated_from": {"relabel": relabel_path, "ground_truth": gt_path},
        "scope": {
            "definition": "first N GT point windows padded by `pad` frames each side",
            "points": len(windows),
            "windows": [list(w) for w in windows],
            "pad_f": pad,
            "region": [lo, hi],
            "gt_contacts_in_region": sum(1 for e in gt_ev if in_region(int(e["frame"]), lo, hi)),
            "gt_contacts_total": len(gt_ev),
            "actions_in_region": len(actions),
            "actions_total": len(all_actions),
            "note": ("the raw GT point windows are not rally-inclusive: "
                     f"{len(gt_ev) - sum(1 for e in gt_ev if in_region(int(e['frame']), lo, hi))}"
                     " owner contacts fall outside them (P1 serve f210 among them), "
                     "so the padded region is the scope; it reproduces the T4 "
                     "dev-clip baseline exactly (see parity)"),
        },
        "time": {"tolerance_base_s": tolerance_s,
                 "note": "GT frame_tolerance=15 on every owner contact raises the "
                         "effective tolerance to 15/fps per event"},
        "gt_derived_inputs": {
            "autonomous_mode_used": False,
            "reason": "the pass-2 stream carries owner serve anchors / verdicts / "
                      "map attribution, so evaluate_timed --autonomous would refuse; "
                      "the findings are audited on the relabel artifact itself "
                      "(`generated_from.relabel`) instead of being ignored",
            "findings": et.find_gt_derived_inputs(relabel),
        },
        "arms": {arm: _arm_summary(results[arm]) for arm in ARMS},
        "delta_pass2_minus_perception": arm_delta(results["perception"],
                                                  results["pass2"]),
        "parity_vs_t4_dev_clip": parity(results["perception"]),
        "per_contact": per_contact_rows(gt_blob, gt_path, arm_preds, tolerance_s),
        "serves": {
            "rows": rows,
            "gt_serves": len(rows),
            "gt_serves_with_any_action_within_search_f": sum(
                1 for r in rows if r["candidates"]),
            "search_f": search_f,
            "far_serve_score": far_serve_score(rows, tolerance_s, fps or 30.0),
        },
    }
    return out


def _arm_summary(res: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "predictions": res["_predictions"],
        "counts": res["counts"],
        "contact": res["contact"],
        "class_accuracy": res["labels"]["class_accuracy"],
        "confusion_matrix": res["labels"]["confusion_matrix"],
        "team_accuracy": res["attribution"]["team_accuracy"],
        "fp_per_dead_minute": res["dead_time"].get("fp_per_dead_minute"),
        "unmatched_gt": res["details"]["unmatched_gt"],
        "unmatched_pred": res["details"]["unmatched_pred"],
        "duplicates": res["details"]["duplicates"],
    }


def format_report(out: Dict[str, Any]) -> str:
    s = out["scope"]
    lines = [
        "=" * 70,
        "  PASS-2 CONTACT-LEVEL SCORE (S0b) -- match P1-P8, owner contact GT",
        "=" * 70,
        f"  scope            : {s['points']} points, region f{s['region'][0]}-"
        f"{s['region'][1]} (pad {s['pad_f']}f)",
        f"  GT contacts      : {s['gt_contacts_in_region']}/{s['gt_contacts_total']} in region",
        f"  actions          : {s['actions_in_region']}/{s['actions_total']} in region",
        f"  autonomous mode  : {out['gt_derived_inputs']['autonomous_mode_used']}",
        "",
        f"  {'arm':<12}{'P':>8}{'R':>8}{'F1':>8}{'cls':>8}{'team':>8}{'FP':>6}{'FN':>6}{'dup':>6}{'FP/deadmin':>12}",
    ]
    for arm in ARMS:
        a = out["arms"][arm]
        c = a["contact"]
        lines.append(
            f"  {arm:<12}{c['precision']:>8.3f}{c['recall']:>8.3f}{c['f1']:>8.3f}"
            f"{(a['class_accuracy'] or 0):>8.3f}{(a['team_accuracy'] or 0):>8.3f}"
            f"{c['fp']:>6d}{c['fn']:>6d}{c['duplicates']:>6d}"
            f"{(a['fp_per_dead_minute'] or 0):>12.3f}")
    d = out["delta_pass2_minus_perception"]
    lines += [
        "",
        f"  pass2 - perception: F1 {d['contact_f1']:+.3f}  P {d['contact_precision']:+.3f}"
        f"  R {d['contact_recall']:+.3f}  cls {d['class_accuracy']:+.3f}"
        f"  team {d['team_accuracy']:+.3f}  TP {d['tp']:+d} FP {d['fp']:+d} FN {d['fn']:+d}",
        f"  T4 parity (perception arm vs recorded dev-clip baseline): "
        f"{'OK' if out['parity_vs_t4_dev_clip']['parity'] else 'MISMATCH'}",
        "",
        "  confusion (GT -> pred), pass2 arm:",
    ]
    for g, row in sorted(out["arms"]["pass2"]["confusion_matrix"].items()):
        lines.append(f"    {g:<10} {row}")
    fs = out["serves"]["far_serve_score"]
    sv = out["serves"]
    lines += [
        "",
        f"  serves: {sv['gt_serves_with_any_action_within_search_f']}/{sv['gt_serves']} "
        f"GT serves have ANY action within +/-{sv['search_f']}f",
        f"  far serves: {fs['hit_within_tolerance']}/{fs['gt_far_serves']} hit within "
        f"+/-{fs['tolerance_f']}f",
        "    GT serve frame -> nearest pass-2 serve action (delta)",
    ]
    for r in fs["rows"]:
        d = r["delta_f"]
        lines.append(f"    f{r['gt_frame']:<6} -> "
                     f"{'none' if r['nearest_far_serve_f'] is None else r['nearest_far_serve_f']}"
                     f"{'' if d is None else f'  ({d:+d} f)'}")
    changed = [r for r in out["per_contact"]
               if r["change"] not in ("same", "missed by both")]
    lines += ["", "  contacts changed by pass-2:"]
    for r in changed:
        p, q = r["perception"], r["pass2"]
        fmt = lambda m: "miss" if m is None else f"f{m['frame']} {m['action']}"
        lines.append(f"    f{r['gt_frame']:<6} GT {r['gt_action']:<9} "
                     f"perception {fmt(p):<18} pass2 {fmt(q):<18} {r['change']}")
    missed = [r for r in out["per_contact"] if r["change"] == "missed by both"]
    lines.append("    missed by both arms: "
                 + ", ".join(f"f{r['gt_frame']} {r['gt_action']}" for r in missed))
    lines.append("=" * 70)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--relabel", default=DEFAULT_RELABEL)
    ap.add_argument("--ground-truth", default=DEFAULT_GT)
    ap.add_argument("--workdir", default=DEFAULT_WORKDIR)
    ap.add_argument("--points", type=int, default=8,
                    help="number of leading GT points to score (default 8 = P1-P8)")
    ap.add_argument("--pad", type=int, default=DEFAULT_PAD,
                    help="frames of padding each side of the point-window span")
    ap.add_argument("--tolerance-s", type=float, default=0.2)
    ap.add_argument("--search-f", type=int, default=80,
                    help="+/- frame search for the serve-nearest-action table")
    ap.add_argument("--json", default=None, help="write the full result to this path")
    args = ap.parse_args(argv)

    out = run(relabel_path=args.relabel, gt_path=args.ground_truth,
              workdir=args.workdir, n_points=args.points, pad=args.pad,
              tolerance_s=args.tolerance_s, search_f=args.search_f)
    print(format_report(out))
    if args.json:
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
