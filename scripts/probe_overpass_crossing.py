#!/usr/bin/env python3
"""G3 -- OVERPASS net-crossing probe.  DIAGNOSE ONLY: no ``src/`` change.

Background (STATUS #48/#49, open point 9).  The largest held-out contact loss
is the gesture LABEL bucket (57/183); the single worst class in it is
``overpass``: **0/18** correct on P9-P33 (13 found, all emitted dig/set/spike;
5 missed).  The owner's GT overpass is a NON-ATTACK touch whose ball CROSSES
the net (touch-1/2 bump pass); the pipeline's own ``ActionContextResolver``
emits ``overpass`` in exactly one place -- a bump-set at touch 2 with NO
following contact within ``rally_reset_gap``.  Open point 9 states the fix must
thread the ball-crossing signal into the resolver "or not at all".

This probe asks the pre-registered question: **is the net crossing visible in
the ball data at the owner's overpass contacts?**  The validated crossing
signal is the ball's apparent WIDTH regime (near half: >35 px, far half:
<26 px; 26-35 abstains -- ``attribution_width_far_px`` / ``_near_px``).  A ball
that crosses the net changes regime; a ball that stays does not.

Inputs are existing artifacts only (no video decode):

* GT contacts -- ``ground_truth/20260920_match_contacts.json``;
* the PRODUCTION perception stream -- ``actions_pass2`` in
  ``output/serve_relabel.json`` (ball tracking is gate-independent, so the
  labels are read from production, never from the dump's own actions);
* ball sightings + detected widths -- ``output/g3r1/match_bw03_diag.jsonl``,
  the only full-match diag dump (its departure gate differs, but the
  ``BallTracker`` that produced ``ball_track`` / ``ball_dets`` is the shared
  production one).

Pre-registered KILLS (frozen before the held-out look):

  **K1 (signal present).**  < 12/18 held-out GT overpasses show a width-regime
  crossing across the contact -> the crossing signal is absent and the
  resolver lever is dead (same class as the S1 looming refutation).
  **K2 (separation).**  overpass crossing rate < 1.5x the highest rate among
  the NON-attack controls (GT dig / GT set), measured the same way -> even if
  present, the signal does not separate crossing from staying.
  **K3 (detection).**  < 15/18 overpasses have >= 5 tracked frames both before
  and after the contact -> the lever is detection/tracking, not a resolver
  rule (reported, not a pass/fail for the resolver lever).
  **K4 (secondary, context).**  the perceived NEXT contact's team flips vs the
  toucher's team at overpasses < 1.5x the controls -> the structural
  next-possession signal is also unavailable in the stream.

As a second step the probe REPLAYS the production ``ActionContextResolver``
(imported, never reimplemented) over the diag dump's raw
``candidate_passed_gates`` contacts with three candidate overpass rules; all
are net-negative on P9-P33, which is why no ``src/`` change ships.

Usage (defaults reproduce the doc)::

    venv/bin/python scripts/probe_overpass_crossing.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import evaluate_timed as et  # noqa: E402
from src.recognition.action_context import ActionContextResolver  # noqa: E402
from src.recognition.volleyball_actions import VisualGesture, VolleyballAction  # noqa: E402
from src.utils.diagnostics import load_diag  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

#: Ball-width near/far thresholds (px), matching ``ActionClassifier``'s
#: ``attribution_width_far_px`` / ``attribution_width_near_px``.
WIDTH_FAR_PX = 26.0
WIDTH_NEAR_PX = 35.0
#: Frames before/after a contact searched for width-regime evidence.
PRE_SPAN = 15
POST_SPAN = 45
#: Minimum tracked frames either side needed to call a contact "covered".
MIN_TRACK_SIDE = 5

DEFAULT_GT = "ground_truth/20260920_match_contacts.json"
DEFAULT_RELABEL = "output/serve_relabel.json"
DEFAULT_DIAG = "output/g3r1/match_bw03_diag.jsonl"
DEFAULT_JSON = "output/g3_overpass/overpass_crossing.json"
DEFAULT_REPORT = "docs/g3_overpass_crossing.md"

#: Non-attack controls: contacts that should NOT cross at the contact itself.
NON_ATTACK_CONTROLS = ("dig", "set")
#: Attack control: crosses by definition, but the gesture already marks it.
ATTACK_CONTROLS = ("spike",)


# ----------------------------------------------------------------------
# pure helpers
# ----------------------------------------------------------------------

def ball_width(rec: Dict[str, Any]) -> Optional[float]:
    """Detected ball width (px) for one diag frame, or None.

    Only a LOCKED tracker with a real detection contributes: the width of the
    detection whose centre equals the tracked centre.  A ``predicted`` centre
    (no detection) has no width and is skipped -- never guessed.
    """
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


def is_tracked(rec: Dict[str, Any]) -> bool:
    bt = rec.get("ball_track") or {}
    return bool(bt.get("locked") and bt.get("center"))


def side_of_width(w: Optional[float]) -> Optional[str]:
    """Per-sample width side: 'A' near (>35), 'B' far (<26), else None."""
    if w is None:
        return None
    if w > WIDTH_NEAR_PX:
        return "A"
    if w < WIDTH_FAR_PX:
        return "B"
    return None


def crossing_evidence(widths: Dict[int, float], frame: int,
                      pre_span: int = PRE_SPAN,
                      post_span: int = POST_SPAN) -> Dict[str, Any]:
    """Width-regime evidence around ``frame``.

    ``pre`` and ``post`` are the sets of committed sides ('A'/'B') observed in
    ``[frame-pre_span, frame-1]`` and ``[frame+1, frame+post_span]``.  A
    CROSSING is when both sides are committed AND the two sets differ (i.e.
    the ball changed regime across the contact).
    """
    pre = {s for s in (side_of_width(widths.get(f))
                       for f in range(frame - pre_span, frame)) if s}
    post = {s for s in (side_of_width(widths.get(f))
                        for f in range(frame + 1, frame + post_span + 1)) if s}
    covered = bool(pre) and bool(post)
    crossing = covered and pre != post
    return {
        "pre_sides": sorted(pre),
        "post_sides": sorted(post),
        "covered": covered,
        "crossing": crossing,
    }


def track_coverage(recs: Dict[int, Dict[str, Any]], frame: int,
                   pre_span: int = PRE_SPAN,
                   post_span: int = POST_SPAN) -> Tuple[int, int]:
    """(#tracked frames in [f-pre, f-1], #tracked in [f+1, f+post])."""
    pre = sum(1 for f in range(frame - pre_span, frame)
              if f in recs and is_tracked(recs[f]))
    post = sum(1 for f in range(frame + 1, frame + post_span + 1)
               if f in recs and is_tracked(recs[f]))
    return pre, post


def next_emitted_after(actions: Sequence[Dict[str, Any]],
                       frame: int) -> Optional[Dict[str, Any]]:
    later = [a for a in actions
             if a.get("frame_number") is not None
             and int(a["frame_number"]) > frame]
    if not later:
        return None
    return min(later, key=lambda a: int(a["frame_number"]))


def bucket_by_action(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Per-GT-action aggregate of crossing / coverage / next-team flip."""
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = r.get("gt_action") or "<none>"
        b = out.setdefault(k, {"n": 0, "crossing": 0, "covered": 0,
                               "tracked_ok": 0, "next_flip": 0,
                               "next_flip_n": 0})
        b["n"] += 1
        if r["crossing"]:
            b["crossing"] += 1
        if r["covered"]:
            b["covered"] += 1
        if r["tracked_pre"] >= MIN_TRACK_SIDE and r["tracked_post"] >= MIN_TRACK_SIDE:
            b["tracked_ok"] += 1
        if r.get("next_team") is not None and r.get("gt_team") is not None:
            b["next_flip_n"] += 1
            if r["next_team"] != r["gt_team"]:
                b["next_flip"] += 1
    for b in out.values():
        b["crossing_rate"] = round(b["crossing"] / b["n"], 4) if b["n"] else None
    return out


def _rate(b: Optional[Dict[str, Any]]) -> float:
    return float(b["crossing_rate"]) if b and b.get("crossing_rate") else 0.0


def kill_verdict(by_action: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Apply the pre-registered K1-K4 to the per-action aggregate."""
    op = by_action.get("overpass") or {"n": 0, "crossing": 0, "tracked_ok": 0}
    n_op = op["n"]
    op_rate = _rate(op)
    control_rate = max(_rate(by_action.get(c)) for c in NON_ATTACK_CONTROLS)
    control_label = max(NON_ATTACK_CONTROLS, key=lambda c: _rate(by_action.get(c)))

    k1_fire = n_op > 0 and op["crossing"] < 12
    k2_fire = n_op > 0 and op_rate < 1.5 * control_rate
    k3_fire = n_op > 0 and op["tracked_ok"] < 15

    op_flip = op.get("next_flip", 0)
    op_flip_n = op.get("next_flip_n", 1) or 1
    ctrl_flip = max((by_action.get(c) or {}).get("next_flip", 0) for c in NON_ATTACK_CONTROLS)
    ctrl_flip_n = max((by_action.get(c) or {}).get("next_flip_n", 1) for c in NON_ATTACK_CONTROLS)
    op_flip_rate = op_flip / op_flip_n
    ctrl_flip_rate = ctrl_flip / ctrl_flip_n if ctrl_flip_n else 0.0
    k4_fire = n_op > 0 and op_flip_rate < 1.5 * ctrl_flip_rate

    resolver_lever_dead = k1_fire or k2_fire
    return {
        "K1_signal_present": {
            "fired": k1_fire, "detail": f"overpass crossing {op['crossing']}/{n_op} (< 12 -> fired)"},
        "K2_separation": {
            "fired": k2_fire,
            "detail": f"overpass rate {op_rate:.3f} vs control {control_label} "
                      f"{control_rate:.3f} (need >= 1.5x)"},
        "K3_detection": {
            "fired": k3_fire, "detail": f"overpass tracked-both-sides {op['tracked_ok']}/{n_op} (< 15 -> fired)"},
        "K4_next_team": {
            "fired": k4_fire,
            "detail": f"overpass next-team flip {op_flip}/{op_flip_n} "
                      f"({op_flip_rate:.3f}) vs control {ctrl_flip_rate:.3f}"},
        "resolver_lever_dead": resolver_lever_dead,
        "verdict": ("REFUTED: ball-width net-crossing is not available at the "
                    "overpass contacts" if resolver_lever_dead else
                    "SURVIVES: crossing signal / separation present"),
    }


# ----------------------------------------------------------------------
# data assembly
# ----------------------------------------------------------------------

def gt_overpass_contacts(gt_blob: Dict[str, Any],
                         lo_point: int, hi_point: int) -> List[Dict[str, Any]]:
    ev = (gt_blob.get("annotated_frames") or {}).get("actions", {}).get("events") or []
    out = []
    for e in ev:
        if e.get("frame") is None:
            continue
        p = e.get("point")
        if not (lo_point <= int(p) <= hi_point):
            continue
        act = e.get("final_action") or e.get("action")
        if act == "overpass":
            out.append(e)
    return sorted(out, key=lambda e: e["frame"])


def build_rows(gt_contacts: Sequence[Dict[str, Any]],
               recs: Dict[int, Dict[str, Any]],
               pred_pairs: Dict[int, Dict[str, Any]],
               actions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One diagnostic row per GT overpass contact."""
    rows: List[Dict[str, Any]] = []
    for e in gt_contacts:
        f = int(e["frame"])
        widths = {g: w for g, w in ((g, ball_width(recs[g])) for g in recs
                                    if abs(g - f) <= POST_SPAN + PRE_SPAN)}
        ev = crossing_evidence(widths, f)
        tr_pre, tr_post = track_coverage(recs, f)
        pred = pred_pairs.get(f)
        nxt = next_emitted_after(actions, f)
        rows.append({
            "point": e.get("point"),
            "gt_frame": f,
            "gt_action": e.get("final_action") or e.get("action"),
            "gt_gesture": e.get("gesture"),
            "gt_team": e.get("player_team"),
            "gt_touch": e.get("touch_number"),
            "owner_raw": e.get("owner_raw"),
            "tracked_pre": tr_pre,
            "tracked_post": tr_post,
            "pre_sides": ev["pre_sides"],
            "post_sides": ev["post_sides"],
            "covered": ev["covered"],
            "crossing": ev["crossing"],
            "pred_action": None if pred is None else pred.get("action"),
            "pred_gesture": None if pred is None else (pred.get("raw") or {}).get("gesture"),
            "pred_team": None if pred is None else pred.get("team"),
            "pred_touch": None if pred is None else (pred.get("raw") or {}).get("touch_number"),
            "pred_kind": None if pred is None else (pred.get("raw") or {}).get("contact_kind"),
            "pred_delta_s": None if pred is None else round(float(pred.get("_delta_s", 0.0)), 3),
            "next_team": None if nxt is None else nxt.get("team"),
            "next_action": None if nxt is None else nxt.get("action"),
            "next_frame": None if nxt is None else nxt.get("frame_number"),
        })
    return rows


def build_pairs(gt_contacts: Sequence[Dict[str, Any]],
                gt_blob: Dict[str, Any],
                pred_events: Sequence[Dict[str, Any]],
                tolerance_s: float) -> Dict[int, Dict[str, Any]]:
    """GT frame -> matched prediction (``evaluate_timed``'s own matcher)."""
    fps = float(gt_blob.get("fps") or 25.6702272643995)
    tb = et.resolve_timebase(gt_blob, {"fps": fps})
    gt_norm = [et.normalize_event(e) for e in gt_contacts]
    m = et.match_events(gt_norm, list(pred_events), tb,
                        base_tolerance_s=tolerance_s)
    out: Dict[int, Dict[str, Any]] = {}
    for g, p, d in m["pairs"]:
        p = dict(p)
        p["_delta_s"] = d
        out[int(g["frame"])] = p
    return out


# ----------------------------------------------------------------------
# resolver rule replay (offline; no src/ change)
# ----------------------------------------------------------------------

_GESTURES = {
    "bump_set": VisualGesture.BUMP_SET,
    "attack": VisualGesture.ATTACK,
    "block": VisualGesture.BLOCK,
    "unknown": VisualGesture.UNKNOWN,
}


def load_raw_contacts(diag_path: str) -> List[Dict[str, Any]]:
    """The resolver's INPUT contacts from the diag dump.

    ``candidate_passed_gates`` records carry exactly what ``_decide`` reads
    (gesture, near_net, behind_baseline, team, ball_side, kind) -- so the
    resolver can be replayed offline instead of reimplemented.  Caveat: the
    dump is the bw03 run, so contacts its departure gate removed are absent.
    """
    recs = load_diag(diag_path)["frames"]
    out: List[Dict[str, Any]] = []
    for rec in recs.values():
        for c in rec.get("candidates") or []:
            if c.get("stage") != "candidate_passed_gates":
                continue
            out.append({
                "frame": int(c["frame"]),
                "gesture": _GESTURES.get(c.get("gesture"), VisualGesture.UNKNOWN),
                "near_net": bool(c.get("near_net")),
                "behind_baseline": bool(c.get("behind_baseline")),
                "team": c.get("team"),
                "ball_side": c.get("ball_side"),
                "contact_kind": c.get("kind"),
            })
    return sorted(out, key=lambda c: c["frame"])


def _rule_next_team_crossing(c, nxt, resolved, resolver):
    """Rule A: any bump-set whose NEXT contact is the opposite team crosses."""
    if (c["gesture"] == VisualGesture.BUMP_SET and nxt is not None
            and nxt["frame"] - c["frame"] <= resolver.rally_reset_gap
            and nxt.get("team") != c.get("team")):
        return VolleyballAction.OVERPASS
    return None


def _rule_no_follow_touch(c, nxt, resolved, resolver):
    """Rule C/D: a net bump-set with NO follow is overpass (t1/t3 too)."""
    no_follow = nxt is None or nxt["frame"] - c["frame"] > resolver.rally_reset_gap
    if (c["gesture"] == VisualGesture.BUMP_SET and c["near_net"] and no_follow
            and not (c["behind_baseline"] and resolved.get("new_possession"))):
        return VolleyballAction.OVERPASS
    return None


def _rule_next_team_with_side(c, nxt, resolved, resolver):
    """Rule E: Rule A additionally requiring ball-side evidence on the ball."""
    if (c["gesture"] == VisualGesture.BUMP_SET and nxt is not None
            and nxt["frame"] - c["frame"] <= resolver.rally_reset_gap
            and nxt.get("team") != c.get("team")
            and nxt.get("ball_side") == c.get("team")):
        return VolleyballAction.OVERPASS
    return None


RULES = {
    "ruleA_next_team": _rule_next_team_crossing,
    "ruleCD_no_follow": _rule_no_follow_touch,
    "ruleE_next_team_side": _rule_next_team_with_side,
}


def replay_resolver(contacts: Sequence[Dict[str, Any]],
                    rule=None) -> List[Dict[str, Any]]:
    """Replay ``ActionContextResolver`` over raw contacts, optionally applying
    a candidate overpass rule when the baseline did NOT emit ``overpass``."""
    resolver = ActionContextResolver()
    out: List[Dict[str, Any]] = []
    for i, c in enumerate(contacts):
        nxt = contacts[i + 1] if i + 1 < len(contacts) else None
        r = resolver.resolve(c, nxt)
        action = r["action"]
        if rule is not None and action != VolleyballAction.OVERPASS.value:
            override = rule(c, nxt, r, resolver)
            if override is not None:
                action = override.value
        out.append({"frame": c["frame"], "action": action, "team": c.get("team")})
    return out


def label_status(emitted: Sequence[Dict[str, Any]],
                 gt_contacts: Sequence[Dict[str, Any]],
                 tol: int = 15) -> Dict[str, Any]:
    """Match each GT contact to the nearest emission within ``tol`` frames and
    score the label: correct / wrong_label / missed."""
    out = {"correct": 0, "wrong_label": 0, "missed": 0, "overpass_recovered": 0}
    n_op = 0
    for e in gt_contacts:
        ga = e.get("final_action") or e.get("action")
        f = int(e["frame"])
        cands = [p for p in emitted if abs(p["frame"] - f) <= tol]
        best = min(cands, key=lambda p: abs(p["frame"] - f)) if cands else None
        if ga == "overpass":
            n_op += 1
        if best is None:
            out["missed"] += 1
            continue
        if ga is None or best["action"] == ga:
            out["correct"] += 1
            if ga == "overpass":
                out["overpass_recovered"] += 1
        else:
            out["wrong_label"] += 1
    out["n_overpass"] = n_op
    return out


def replay_rule_candidates(diag_path: str,
                           gt_contacts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Replay the baseline + every candidate rule and score each on the GT."""
    raw = load_raw_contacts(diag_path)
    result: Dict[str, Any] = {
        "n_raw_contacts": len(raw),
        "baseline": label_status(replay_resolver(raw), gt_contacts),
        "candidates": {},
    }
    for name, rule in RULES.items():
        result["candidates"][name] = label_status(
            replay_resolver(raw, rule), gt_contacts)
    return result


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt", default=DEFAULT_GT)
    ap.add_argument("--relabel", default=DEFAULT_RELABEL)
    ap.add_argument("--diag", default=DEFAULT_DIAG)
    ap.add_argument("--from-point", type=int, default=9)
    ap.add_argument("--to-point", type=int, default=33)
    ap.add_argument("--tolerance", type=float, default=et.BASE_TOLERANCE_S,
                    help="base matcher tolerance in seconds")
    ap.add_argument("--json", default=DEFAULT_JSON)
    ap.add_argument("--report", default=DEFAULT_REPORT)
    args = ap.parse_args(argv)

    gt_blob = json.loads(Path(args.gt).read_text())
    gt_contacts = gt_overpass_contacts(gt_blob, args.from_point, args.to_point)

    relabel = json.loads(Path(args.relabel).read_text())
    actions = relabel.get("actions_pass2") or []
    pred_events = [et.normalize_event(a) for a in actions]

    diag = load_diag(args.diag)
    recs = diag["frames"]
    if not recs:
        raise SystemExit(f"Error: no frames in diag dump {args.diag}")

    pairs = build_pairs(gt_contacts, gt_blob, pred_events, args.tolerance)
    rows = build_rows(gt_contacts, recs, pairs, actions)

    by_action = bucket_by_action(rows)
    # Controls: all GT contacts in scope (each contact's own class), for the
    # crossing / next-team rates that K2/K4 compare against.
    ev = (gt_blob.get("annotated_frames") or {}).get("actions", {}).get("events") or []
    scope = [e for e in ev if e.get("frame") is not None
             and args.from_point <= int(e.get("point")) <= args.to_point]
    all_pairs = build_pairs(scope, gt_blob, pred_events, args.tolerance)
    control_rows = build_rows(scope, recs, all_pairs, actions)
    control_by_action = bucket_by_action(control_rows)

    verdict = kill_verdict(control_by_action)
    rules = replay_rule_candidates(args.diag, scope)

    result = {
        "scope": {"from_point": args.from_point, "to_point": args.to_point,
                  "n_overpass": len(rows), "n_scope_contacts": len(scope)},
        "constants": {"width_far_px": WIDTH_FAR_PX, "width_near_px": WIDTH_NEAR_PX,
                      "pre_span": PRE_SPAN, "post_span": POST_SPAN,
                      "min_track_side": MIN_TRACK_SIDE},
        "sources": {"gt": args.gt, "relabel": args.relabel, "diag": args.diag,
                    "diag_note": ("ball tracking is gate-independent; action "
                                  "labels are read from the production stream, "
                                  "not the bw03 dump's own actions")},
        "overpass_emitted": dict(Counter(
            r["pred_action"] or "<missed>" for r in rows)),
        "overpass_by_action": by_action,
        "control_by_action": control_by_action,
        "resolver_rules": rules,
        "verdict": verdict,
        "rows": rows,
    }

    out_json = Path(args.json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2))

    report = render_report(result)
    out_rep = Path(args.report)
    out_rep.parent.mkdir(parents=True, exist_ok=True)
    out_rep.write_text(report)
    print(report)
    print(f"[wrote {out_json}]")
    return 0


def render_report(result: Dict[str, Any]) -> str:
    rows = result["rows"]
    ba = result["overpass_by_action"]["overpass"]
    cb = result["control_by_action"]
    lines = [
        "# G3 overpass net-crossing probe — diagnosis (no `src/` change)",
        "",
        f"Scope P{result['scope']['from_point']}–P{result['scope']['to_point']}: "
        f"**{result['scope']['n_overpass']} GT overpasses** "
        f"({result['scope']['n_scope_contacts']} contacts in scope).",
        "",
        "Crossing signal = ball apparent WIDTH regime (near > 35 px / far < 26 px) "
        f"across the contact, pre `[f-{PRE_SPAN}, f-1]` vs post "
        f"`[f+1, f+{POST_SPAN}]`.",
        "",
        "## Aggregate",
        "",
        "| GT action | n | crossing | covered | tracked both sides | next-team flip |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for k in sorted(cb, key=lambda x: (-cb[x]["n"], str(x))):
        b = cb[k]
        lines.append(f"| {k} | {b['n']} | {b['crossing']} | {b['covered']} "
                     f"| {b['tracked_ok']} | {b['next_flip']}/{b['next_flip_n']} |")
    lines += [
        "",
        f"**GT overpass**: crossing **{ba['crossing']}/{ba['n']}** "
        f"({ba['crossing_rate']}), tracked both sides {ba['tracked_ok']}/{ba['n']}.",
        "",
        "## Pre-registered kills",
        "",
    ]
    for name in ("K1_signal_present", "K2_separation", "K3_detection", "K4_next_team"):
        v = result["verdict"][name]
        lines.append(f"- **{name}** — {'FIRED' if v['fired'] else 'clean'}: {v['detail']}")
    lines += ["", f"**Verdict: {result['verdict']['verdict']}**", "",
              "## Resolver read at the overpass contacts", "",
              "Emitted labels near the 18 GT overpasses (production stream): "
              f"{result['overpass_emitted']}.", "",
              "## Candidate overpass RULES replayed offline", "",
              "The diag dump's `candidate_passed_gates` records carry the "
              "resolver's own inputs, so `ActionContextResolver` was replayed "
              "(imported, not reimplemented) with each candidate rule overriding "
              "a non-overpass baseline decision. Scored against the GT contacts "
              "nearest within +-15 f:", "",
              "| arm | correct | wrong_label | missed | overpass recovered |",
              "|---|---:|---:|---:|---:|"]
    rr = result.get("resolver_rules") or {}
    for name, st in ([("baseline", rr.get("baseline"))] + list(rr.get("candidates", {}).items())):
        if st:
            lines.append(f"| {name} | {st['correct']} | {st['wrong_label']} "
                         f"| {st['missed']} | {st['overpass_recovered']}/{st['n_overpass']} |")
    lines += [
              "",
              "## Reading the result", "",
              "A negative result, the same class as S1/T5/R1: the ball-width "
              "net-crossing signal is NOT available at the owner's overpass "
              "contacts (3/18), while the ball is tracked on BOTH sides at "
              "18/18 — so this is not a detection gap either. The crossing is "
              "measured at the net/tape, where the width regime abstains, and "
              "a high lob reads ambiguously on both sides of the contact.",
              "",
              "The loss is therefore a LABEL/RULE problem, not a geometry one: "
              "the resolver emits `overpass` in exactly one place (a bump-set "
              "at touch 2 with no follow), but GT overpasses occur at touch 1 "
              "and touch 3 as well, and the emitted touch/gesture read sends "
              "them to dig/spike/set. The perceived next-contact team does NOT "
              "provide the missing signal either (overpass next-team flip 8/18 "
              "= 0.444, controls 0.582) because the stream's own possession/team "
              "read is noisy (G1 side-level team 0.755). Any overpass lever "
              "must therefore be a gesture/touch-rule change plus a reliable "
              "possession signal — an owner/architect decision, not a ball-"
              "width threshold.", "",
              "Caveat: the ball sightings come from the only full-match diag "
              "dump (`match_bw03_diag.jsonl`). Its departure gate differs, but "
              "the `BallTracker` that produced `ball_track` / `ball_dets` is the "
              "shared production one, and the action labels are read from the "
              "production stream (`serve_relabel.json`), never the dump.", "",
              "## Per-contact rows", "",
              "| pt | f | GT team/touch | tracked pre/post | pre→post sides | crossing "
              "| emitted (action/gesture/team/touch) |",
              "|---|---:|---|---:|---|---|---|"]
    for r in rows:
        pred = (f"{r['pred_action']}/{r['pred_gesture']}/{r['pred_team']}/t{r['pred_touch']}"
                if r["pred_action"] else "MISSED ±tol")
        lines.append(
            f"| P{r['point']} | {r['gt_frame']} | {r['gt_team']}/t{r['gt_touch']} "
            f"| {r['tracked_pre']}/{r['tracked_post']} "
            f"| {','.join(r['pre_sides'])}→{','.join(r['post_sides'])} "
            f"| {'X' if r['crossing'] else '.'} | {pred} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
