"""G1 -- first HELD-OUT contact-level score of the perception / pass-2 streams.

The S0b scorer (`scripts/score_pass2_contacts.py`) measured the *dev-clip*
windows P1-P8 -- the same footage every mechanism was fit on.  G0 (#47) made
the rest of the 20260920 match machine-readable, so this script scores the
**held-out** points P9-P33 against
`ground_truth/20260920_match_contacts.json` with the SAME scope discipline:

* scope = the P9-P33 point windows' span padded by ``--pad`` frames each side
  (default 90 = ``rally_reset_gap``);
* the GT file handed to `evaluate_timed` is SCOPED to P9-P33 (a temp copy),
  so P1-P8 events can never be charged as false negatives;
* two arms over the identical action list -- ``perception`` (the production
  stream) and ``pass2`` (``actions_pass2``: demotions dropped, overrides
  applied), both from ``output/serve_relabel.json``;
* `evaluate_timed`'s time-matched matcher (imported, never re-implemented),
  ``--ignore-player``, effective tolerance ``max(base, GT frame_tolerance/fps)``
  = 15/25.67 s ~= 15 frames per owner contact.

Beyond the contact P/R/F1 the report splits the miss taxonomy at contact
level (correct / wrong-label / wrong-team / missed), the per-action-class and
per-side recall, and the 12 held-out FAR serves specifically.  The
candidate/reach/gate stage waterfall is NOT reproduced here: it needs an
off-by-default diag dump from a *production* match run, which does not exist
(the only match dump is the R1 ``bw=0.3`` run, whose gate decisions differ);
that is flagged, not faked.

NO video is decoded, NO ``src/`` file is touched: pass-2 post-hoc scoring
(AGENTS.md section 6).

Usage:
    venv/bin/python scripts/score_heldout_contacts.py
    venv/bin/python scripts/score_heldout_contacts.py --json output/heldout_contacts/g1.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import evaluate_timed as et  # noqa: E402  (path set above)
from score_pass2_contacts import (  # noqa: E402
    ARMS,
    _arm_summary,
    arm_delta,
    arm_events,
    far_serve_score,
    gt_contacts,
    in_region,
    per_contact_rows,
    prediction_blob,
    scoped_actions,
    serve_rows,
)

REPO = Path(__file__).resolve().parent.parent

DEFAULT_RELABEL = "output/serve_relabel.json"
DEFAULT_MATCH_GT = "ground_truth/20260920_match_contacts.json"
DEFAULT_WORKDIR = "output/heldout_contacts"
DEFAULT_PAD = 90  # rally_reset_gap frames
DEFAULT_FROM = 9
DEFAULT_TO = 33

#: The R1 departure-gate artifact is the only full-match diag dump; it was
#: produced with contact_min_departure_bw=0.3, so its gate decisions do NOT
#: match production and cannot feed a production waterfall.
R1_MATCH_DIAG = "output/g3r1/match_bw03_diag.jsonl"


# ----------------------------------------------------------------------
# scope
# ----------------------------------------------------------------------

def select_points(gt_blob: Dict[str, Any], lo_point: int, hi_point: int
                  ) -> List[Dict[str, Any]]:
    """The GT point records in [lo_point, hi_point] (order preserved)."""
    return [p for p in (gt_blob.get("points") or [])
            if lo_point <= int(p.get("point", -1)) <= hi_point]


def select_events(gt_blob: Dict[str, Any], lo_point: int, hi_point: int
                  ) -> List[Dict[str, Any]]:
    """GT contact events whose ``point`` is in [lo_point, hi_point]."""
    ev = (gt_blob.get("annotated_frames") or {}).get("actions", {}).get("events")
    if ev is None:
        ev = gt_blob.get("events") or []
    return [e for e in ev
            if isinstance(e, dict) and lo_point <= int(e.get("point", -1)) <= hi_point]


def point_windows(points: Sequence[Dict[str, Any]]) -> List[Tuple[int, int]]:
    """[(start, end)] from the match-axis prediction windows."""
    out = []
    for p in points:
        s = p.get("match_start_frame", p.get("clip_start_frame"))
        e = p.get("match_end_frame", p.get("clip_end_frame"))
        if s is None or e is None:
            continue
        out.append((int(s), int(e)))
    return out


def region_of(windows: Sequence[Tuple[int, int]], pad: int) -> Tuple[int, int]:
    if not windows:
        raise ValueError("no GT point windows")
    return windows[0][0] - pad, windows[-1][1] + pad


def scoped_gt_blob(gt_blob: Dict[str, Any], lo_point: int, hi_point: int
                   ) -> Dict[str, Any]:
    """A GT blob restricted to P<lo>-P<hi>, evaluate_timed-compatible.

    ``clip_start_frame`` / ``clip_end_frame`` are added from the match-axis
    emission windows so `evaluate_timed.point_intervals` can read them (the
    match blobs only carry the ``match_*`` names).  Those windows are
    PREDICTIONS (``window_is_prediction``) and some drift far from the owner
    contact range; the drift is measured separately and the affected
    dead-time/points metrics are flagged.
    """
    points = []
    for p in select_points(gt_blob, lo_point, hi_point):
        q = dict(p)
        q.setdefault("clip_start_frame", p.get("match_start_frame"))
        q.setdefault("clip_end_frame", p.get("match_end_frame"))
        points.append(q)
    scoped = {
        "status": f"scoped P{lo_point}-P{hi_point}",
        "video": gt_blob.get("video"),
        "fps": gt_blob.get("fps"),
        "resolution": gt_blob.get("resolution"),
        "frame_indexing": gt_blob.get("frame_indexing"),
        "points": points,
        "annotated_frames": {"actions": {"events": select_events(
            gt_blob, lo_point, hi_point)}},
        "provenance": {
            "scoped_from": "ground_truth/20260920_match_contacts.json",
            "point_from": lo_point,
            "point_to": hi_point,
            "clip_frames_note": "match axis == clip axis for the full-match video",
        },
    }
    return scoped


def episode_window_drift(points: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Predicted emission window vs the owner contact range, per point.

    The episode->point map (open point 22) is a PREDICTION; later match points
    drift by hundreds of frames.  The scoring REGION is the padded span of the
    windows, which still covers every owner contact (the first window starts
    before the first contact and the last ends after the last), but the
    point-interval / dead-time metrics inherit the drift.
    """
    rows = []
    for p in points:
        rng = p.get("match_frame_range")
        s, e = p.get("match_start_frame"), p.get("match_end_frame")
        row = {"point": p.get("point"),
               "window": [s, e] if s is not None else None,
               "contact_range": list(rng) if rng else None}
        if rng and s is not None:
            row["start_delta_f"] = int(s) - int(rng[0])
            row["end_delta_f"] = int(e) - int(rng[1])
            row["window_covers_contacts"] = bool(int(s) <= int(rng[0])
                                                 and int(e) >= int(rng[1]))
        rows.append(row)
    covered = sum(1 for r in rows if r.get("window_covers_contacts"))
    return {
        "points": rows,
        "windows_covering_owner_contacts": covered,
        "points_scored": len(rows),
        "note": ("episode-map emission windows are predictions; the SCORED "
                 "region is their padded span, the contact P/R/F1 is "
                 "window-independent"),
    }


# ----------------------------------------------------------------------
# contact-level miss taxonomy
# ----------------------------------------------------------------------

def contact_status_rows(gt_blob: Dict[str, Any], gt_path: str,
                        events: Sequence[Dict[str, Any]], tolerance_s: float,
                        search_f: int = 80) -> List[Dict[str, Any]]:
    """One row per GT contact: status + the nearest emitted action if missed.

    Uses `evaluate_timed`'s own matcher/timebase so it cannot disagree with
    the headline scores.  ``gt_action is None`` (the P30 unspecified touch)
    is class-agnostic: a match counts as ``correct``, never as a label error.
    """
    gt = et.load_ground_truth(gt_path)
    fps = float(gt_blob.get("fps") or 0.0)
    timebase = et.resolve_timebase(gt_blob, {"fps": fps} if fps else {})
    match = et.match_events(gt["events"], list(events), timebase, tolerance_s)
    by_frame = {int(g["frame"]): (p, d) for g, p, d in match["pairs"]}

    rows = []
    for e in gt_contacts(gt_blob):
        f = int(e["frame"])
        gt_action = e.get("final_action") or e.get("action")
        gt_team = e.get("player_team")
        pair = by_frame.get(f)
        row: Dict[str, Any] = {
            "gt_frame": f,
            "gt_action": gt_action,
            "gt_team": gt_team,
            "gt_side": e.get("owner_side"),
            "gt_point": e.get("point"),
            "gt_unspecified": bool(e.get("owner_action_unspecified")),
            "matched": pair is not None,
        }
        if pair is not None:
            p, d = pair
            row["pred_frame"] = int(p["frame"])
            row["pred_action"] = p["action"]
            row["pred_team"] = p["team"]
            row["delta_s"] = round(float(d), 3)
            label_ok = (gt_action is None or p["action"] is None
                        or p["action"] == gt_action)
            team_ok = (gt_team is None or p["team"] is None
                       or p["team"] == gt_team)
            row["label_ok"] = label_ok
            row["team_ok"] = team_ok
            if not label_ok:
                row["status"] = "wrong_label"
            elif not team_ok:
                row["status"] = "wrong_team"
            else:
                row["status"] = "correct"
        else:
            row["status"] = "missed"
            cands = sorted(
                (a for a in events
                 if (a.get("frame", a.get("frame_number")) is not None)
                 and abs(int(a.get("frame", a.get("frame_number"))) - f) <= search_f),
                key=lambda a: abs(int(a.get("frame", a.get("frame_number"))) - f))
            row["nearest"] = ([{"frame": int(a.get("frame", a.get("frame_number"))),
                                "action": a.get("action"),
                                "delta_f": int(a.get("frame", a.get("frame_number"))) - f,
                                "team": a.get("team")} for a in cands[:3]]
                              or [])
        rows.append(row)
    return rows


def _rate(ok: int, total: int) -> Optional[float]:
    return round(ok / total, 4) if total else None


def miss_taxonomy(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Bucket the GT contacts and split recall by class and by side."""
    from collections import Counter

    status = Counter(r["status"] for r in rows)
    total = len(rows)

    def split(key_fn) -> Dict[str, Any]:
        out: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            k = key_fn(r) or "<none>"
            b = out.setdefault(k, {"n": 0, "correct": 0, "wrong_label": 0,
                                   "wrong_team": 0, "missed": 0})
            b["n"] += 1
            b[r["status"]] += 1
        for b in out.values():
            b["recall"] = _rate(b["correct"] + b["wrong_team"], b["n"])
            b["contact_found"] = _rate(b["n"] - b["missed"], b["n"])
        return out

    missed = [r for r in rows if r["status"] == "missed"]
    label_errs = [r for r in rows if r["status"] == "wrong_label"]
    team_errs = [r for r in rows if r["status"] == "wrong_team"]
    near_missed = [r for r in missed if r.get("nearest")]
    missed_by_nearest = Counter(
        (r["nearest"][0].get("action") or "<none>") for r in near_missed)
    missed_delta = sorted(abs(r["nearest"][0]["delta_f"]) for r in near_missed)
    return {
        "n_gt_contacts": total,
        "status_counts": {s: status.get(s, 0) for s in
                          ("correct", "wrong_label", "wrong_team", "missed")},
        "contact_recall": _rate(total - status.get("missed", 0), total),
        "label_accuracy_on_found": _rate(
            total - status.get("missed", 0) - status.get("wrong_label", 0),
            total - status.get("missed", 0)),
        "team_accuracy_on_found": _rate(
            total - status.get("missed", 0) - status.get("wrong_label", 0)
            - status.get("wrong_team", 0),
            total - status.get("missed", 0)),
        "by_action": split(lambda r: r["gt_action"]),
        "by_side": split(lambda r: r["gt_side"]),
        "missed_by_action": dict(Counter(r["gt_action"] or "<none>"
                                        for r in missed)),
        "wrong_label_confusion": dict(Counter(
            f"{r['gt_action']} -> {r['pred_action']}" for r in label_errs)),
        "wrong_team_gt": dict(Counter(
            f"GT {r['gt_team']} / pred {r['pred_team']}" for r in team_errs)),
        "missed_with_no_action_within_search": sum(
            1 for r in missed if not r.get("nearest")),
        "missed_with_nearby_action": len(near_missed),
        "missed_nearby_action_class": dict(missed_by_nearest),
        "missed_nearby_delta_f": {
            "min": missed_delta[0] if missed_delta else None,
            "max": missed_delta[-1] if missed_delta else None,
        },
    }


def serve_hit_table(rows: Sequence[Dict[str, Any]], tolerance_f: float,
                    search_f: int) -> Dict[str, Any]:
    """Per GT serve contact: does any emitted serve land within tolerance?

    Tolerance is the EFFECTIVE matcher tolerance (``max(base, 15/fps)`` frames),
    not the bare 0.2 s base, so the serve tally can never contradict the
    contact matching.  ``nearest_far_serve_f`` is the nearest emitted serve of
    any team within ``search_f``.
    """
    out_rows = []
    for r in rows:
        nearest = next((c for c in r["candidates"]
                        if c["pass2_action"] == "serve"), None)
        d = None if nearest is None else nearest["frame"] - r["gt_frame"]
        out_rows.append({
            "gt_frame": r["gt_frame"],
            "gt_track_id": r.get("gt_track_id"),
            "gt_side": r["gt_side"],
            "nearest_serve_f": None if nearest is None else nearest["frame"],
            "delta_f": d,
            "hit": d is not None and abs(d) <= tolerance_f,
            "n_candidates_within_search": len(r["candidates"]),
        })
    far = [r for r in out_rows if r["gt_side"] == "far"]
    near = [r for r in out_rows if r["gt_side"] == "near"]

    def tally(rs):
        return {"n": len(rs), "hits": sum(1 for r in rs if r["hit"]),
                "hit_rate": _rate(sum(1 for r in rs if r["hit"]), len(rs))}

    return {
        "tolerance_f": round(tolerance_f, 2),
        "search_f": search_f,
        "all_serves": tally(out_rows),
        "far_serves": tally(far),
        "near_serves": tally(near),
        "rows": out_rows,
    }


# ----------------------------------------------------------------------
# orchestration
# ----------------------------------------------------------------------

def run(relabel_path: str = DEFAULT_RELABEL, match_gt: str = DEFAULT_MATCH_GT,
        workdir: str = DEFAULT_WORKDIR, point_from: int = DEFAULT_FROM,
        point_to: int = DEFAULT_TO, pad: int = DEFAULT_PAD,
        tolerance_s: float = 0.2, search_f: int = 80) -> Dict[str, Any]:
    relabel = json.loads(Path(relabel_path).read_text(encoding="utf-8"))
    match = json.loads(Path(match_gt).read_text(encoding="utf-8"))

    points = select_points(match, point_from, point_to)
    if not points:
        raise SystemExit(f"Error: no points {point_from}-{point_to} in {match_gt}")
    windows = point_windows(points)
    lo, hi = region_of(windows, pad)
    scoped = scoped_gt_blob(match, point_from, point_to)

    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    scoped_path = work / f"gt_p{point_from}_p{point_to}.json"
    scoped_path.write_text(json.dumps(scoped, indent=1) + "\n", encoding="utf-8")

    all_actions = relabel.get("actions_pass2") or []
    if not all_actions:
        raise SystemExit(f"Error: no actions_pass2 in {relabel_path}")
    actions = scoped_actions(all_actions, lo, hi)
    gt_ev = gt_contacts(scoped)

    fps = float(match.get("fps") or 0.0)
    # Effective per-event matcher tolerance (all owner contacts carry the
    # coarse frame_tolerance=15), used for the serve tally so it cannot
    # contradict the contact matcher.
    gt_frame_tol = max((e.get("frame_tolerance") or 0) for e in gt_ev) if gt_ev else 0
    effective_tol_f = max(tolerance_s * (fps or 30.0),
                          float(gt_frame_tol)) if fps else float(gt_frame_tol)

    results: Dict[str, Any] = {}
    arm_preds: Dict[str, List[Dict[str, Any]]] = {}
    for arm in ARMS:
        events = arm_events(actions, arm)
        arm_preds[arm] = events
        pred_path = work / f"pred_{arm}.json"
        pred_path.write_text(
            json.dumps(prediction_blob(events, relabel.get("video", ""), fps),
                       indent=1) + "\n", encoding="utf-8")
        res = et.evaluate_timed(str(pred_path), str(scoped_path),
                                tolerance_s=tolerance_s, ignore_player=True,
                                autonomous=False)
        results[arm] = res
        results[arm]["_predictions"] = str(pred_path)

    taxonomy = contact_status_rows(scoped, str(scoped_path), arm_preds["perception"],
                                   tolerance_s, search_f)
    all_serves = serve_rows(gt_ev, all_actions, search_f)
    for r in all_serves:
        r["gt_track_id"] = next(
            (e.get("owner_track_id") or e.get("player_id")
             for e in gt_ev if int(e["frame"]) == r["gt_frame"]), None)

    out = {
        "generated_from": {"relabel": relabel_path, "match_gt": match_gt,
                           "scoped_gt": str(scoped_path),
                           "r1_match_diag": R1_MATCH_DIAG},
        "scope": {
            "definition": f"points P{point_from}-P{point_to}, padded by `pad` frames each side",
            "points": len(points),
            "point_from": point_from,
            "point_to": point_to,
            "windows": [list(w) for w in windows],
            "pad_f": pad,
            "region": [lo, hi],
            "gt_contacts_in_region": sum(1 for e in gt_ev if in_region(int(e["frame"]), lo, hi)),
            "gt_contacts_total_scoped": len(gt_ev),
            "actions_in_region": len(actions),
            "actions_total": len(all_actions),
            "search_f": search_f,
        },
        "time": {
            "fps": fps,
            "tolerance_base_s": tolerance_s,
            "gt_frame_tolerance_f": gt_frame_tol,
            "effective_tolerance_f": round(effective_tol_f, 2),
            "note": ("owner contact frames are coarse (-+10-15f); every event "
                     "carries frame_tolerance=15, so the matcher tolerance is "
                     "max(base, 15/fps)"),
        },
        "episode_window_drift": episode_window_drift(points),
        "gt_derived_inputs": {
            "autonomous_mode_used": False,
            "reason": ("the pass-2 stream carries owner serve anchors / verdicts / "
                       "map attribution, so evaluate_timed --autonomous would "
                       "refuse; findings are audited on the relabel artifact"),
            "findings": et.find_gt_derived_inputs(relabel),
        },
        "arms": {arm: _arm_summary(results[arm]) for arm in ARMS},
        "delta_pass2_minus_perception": arm_delta(results["perception"],
                                                  results["pass2"]),
        "per_contact": per_contact_rows(scoped, str(scoped_path), arm_preds,
                                        tolerance_s),
        "perception_miss_taxonomy": miss_taxonomy(taxonomy),
        "perception_contact_rows": taxonomy,
        "serves": {
            "rows": all_serves,
            "gt_serves": len(all_serves),
            "serve_hits": serve_hit_table(all_serves, effective_tol_f, search_f),
            "base_tolerance_far_serve_score": far_serve_score(
                all_serves, tolerance_s, fps or 30.0),
        },
        "waterfall": {
            "available": False,
            "reason": ("the only full-match diag dump is the R1 bw=0.3 run "
                       "(output/g3r1/match_bw03_diag.jsonl); its low_departure "
                       "gate decisions differ from production, so a production "
                       "stage waterfall needs a fresh production diag dump"),
        },
    }
    return out


def format_report(out: Dict[str, Any]) -> str:
    s = out["scope"]
    t = out["time"]
    lines = [
        "=" * 74,
        "  G1 HELD-OUT CONTACT SCORE -- match P9-P33 (first points never fit on)",
        "=" * 74,
        f"  scope        : {s['points']} points P{s['point_from']}-P{s['point_to']}, "
        f"region f{s['region'][0]}-{s['region'][1]} (pad {s['pad_f']}f)",
        f"  GT contacts  : {s['gt_contacts_in_region']}/{s['gt_contacts_total_scoped']} in region",
        f"  actions      : {s['actions_in_region']}/{s['actions_total']} in region",
        f"  timebase     : {t['fps']:.3f} fps, effective tolerance "
        f"{t['effective_tolerance_f']}f (GT frame_tolerance {t['gt_frame_tolerance_f']}f)",
        f"  window drift : episode-map windows cover owner contacts for "
        f"{out['episode_window_drift']['windows_covering_owner_contacts']}"
        f"/{out['episode_window_drift']['points_scored']} points",
        "",
        f"  {'arm':<12}{'P':>8}{'R':>8}{'F1':>8}{'cls':>8}{'team':>8}"
        f"{'FP':>6}{'FN':>6}{'dup':>6}{'FP/deadmin':>12}",
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
        "",
        "  PERCEPTION miss taxonomy (held-out GT contacts):",
    ]
    tax = out["perception_miss_taxonomy"]
    sc = tax["status_counts"]
    lines.append(f"    correct {sc['correct']}  wrong_label {sc['wrong_label']}"
                 f"  wrong_team {sc['wrong_team']}  missed {sc['missed']}"
                 f"  (n={tax['n_gt_contacts']})")
    lines.append(f"    contact recall {tax['contact_recall']}  "
                 f"label acc on found {tax['label_accuracy_on_found']}  "
                 f"team acc on found {tax['team_accuracy_on_found']}")
    lines.append("    by side:")
    for side, b in sorted(tax["by_side"].items()):
        lines.append(f"      {side:<6} n={b['n']:<4} found={b['contact_found']}"
                     f"  correct={b['correct']}  wl={b['wrong_label']}"
                     f"  wt={b['wrong_team']}  miss={b['missed']}")
    lines.append("    by action (recall = correct+wrong_team / n):")
    for act, b in sorted(tax["by_action"].items()):
        lines.append(f"      {act:<9} n={b['n']:<4} recall={b['recall']}"
                     f"  found={b['contact_found']}  correct={b['correct']}"
                     f"  wl={b['wrong_label']}  wt={b['wrong_team']}  miss={b['missed']}")
    if tax["wrong_label_confusion"]:
        lines.append("    label confusion (GT -> pred): " + ", ".join(
            f"{k} x{v}" for k, v in sorted(tax["wrong_label_confusion"].items())))
    lines.append(f"    missed with NO action within +/-{out['scope']['search_f']}f: "
                 f"{tax['missed_with_no_action_within_search']}"
                 f"   | nearby action within search: {tax['missed_with_nearby_action']}"
                 f" {tax['missed_nearby_action_class']}")
    if tax["missed_nearby_delta_f"]["min"] is not None:
        lines.append(f"      nearby-miss delta_f range: "
                     f"{tax['missed_nearby_delta_f']['min']}-{tax['missed_nearby_delta_f']['max']}")
    sh = out["serves"]["serve_hits"]
    lines += [
        "",
        f"  SERVES (effective +/-{sh['tolerance_f']}f tolerance):",
        f"    all  {sh['all_serves']['hits']}/{sh['all_serves']['n']}"
        f"   near {sh['near_serves']['hits']}/{sh['near_serves']['n']}"
        f"   FAR  {sh['far_serves']['hits']}/{sh['far_serves']['n']}"
        "    GT frame -> nearest emitted serve (delta)",
    ]
    for r in sh["rows"]:
        if r["gt_side"] != "far":
            continue
        dl = r["delta_f"]
        lines.append(f"      f{r['gt_frame']:<6} ({r['gt_side']}) -> "
                     f"{'none' if r['nearest_serve_f'] is None else r['nearest_serve_f']}"
                     f"{'' if dl is None else f'  ({dl:+d} f)'}")
    lines += ["", f"  waterfall        : unavailable -- {out['waterfall']['reason']}",
              "=" * 74]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--relabel", default=DEFAULT_RELABEL)
    ap.add_argument("--match-gt", default=DEFAULT_MATCH_GT)
    ap.add_argument("--workdir", default=DEFAULT_WORKDIR)
    ap.add_argument("--point-from", type=int, default=DEFAULT_FROM,
                    help="first GT point to score (default 9)")
    ap.add_argument("--point-to", type=int, default=DEFAULT_TO,
                    help="last GT point to score (default 33)")
    ap.add_argument("--pad", type=int, default=DEFAULT_PAD)
    ap.add_argument("--tolerance-s", type=float, default=0.2)
    ap.add_argument("--search-f", type=int, default=80)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    out = run(relabel_path=args.relabel, match_gt=args.match_gt,
              workdir=args.workdir, point_from=args.point_from,
              point_to=args.point_to, pad=args.pad,
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
