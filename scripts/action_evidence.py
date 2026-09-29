#!/usr/bin/env python3
"""G3 task 1: which already-computed signals separate CORRECT emitted actions
from WRONG ones?  DIAGNOSE ONLY -- no production change, no GT edit.

For every PREDICTED action on the 8 clips (dev + entreno 1-7) this script:

1. labels the OUTCOME using ``evaluate_timed``'s matching (imported, never
   reimplemented; ``--ignore-player`` semantics, same tolerance) and
   ``waterfall``'s false-positive source classification (imported):
   correct / wrong_label / wrong_team / wrong_label_and_team / duplicate /
   fp_in_point / fp_dead_time;
2. extracts FEATURES strictly from values the pipeline already computed
   (the ``--diag-dump`` JSONL + ``pipeline_output.json``) -- nothing is
   re-detected or re-derived from pixels;
3. writes ``output/g3/evidence.json`` (one row per prediction) and
   ``docs/g3_action_evidence.md`` with the precision tables, the
   single-feature separability ranking, the calibration check of the hand-set
   confidence constants, and the "what this suggests" section.

Usage (defaults reproduce the doc)::

    python scripts/action_evidence.py            # the 8 canonical clips
    python scripts/action_evidence.py --clip dev:diag.jsonl:pred.json:gt.json ...
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluate_timed import (  # noqa: E402
    BASE_TOLERANCE_S,
    extract_events,
    load_ground_truth,
    load_predictions,
    match_events,
    point_intervals,
    resolve_timebase,
)
import waterfall  # noqa: E402  (FP source classification, imported not copied)
from src.recognition.action_classifier import ActionClassifier  # noqa: E402
from src.utils.diagnostics import load_diag  # noqa: E402

#: Window (frames, each side of the contact) for track-continuity / rejection
#: counts -- fixed by the task spec.
WINDOW_F = 15
#: Frames each side used for the in/out ball speed.  The OUT window is exactly
#: ``ActionClassifier.CONTACT_DELAY`` (read from the code, never hard-coded):
#: the classifier confirms a contact at ``contact_frame + CONTACT_DELAY``, so
#: every frame of the [contact, contact+SPEED_F] window is already seen at
#: confirmation time -- ball_speed_out_* is a CAUSAL emission-time signal.
SPEED_F = ActionClassifier.CONTACT_DELAY

CORRECT = "correct"
OUTCOME_ORDER = [
    CORRECT, "wrong_label", "wrong_team", "wrong_label_and_team",
    "duplicate", "fp_in_point", "fp_dead_time",
]


# --- default clip set -------------------------------------------------------

def default_clips() -> List[Dict[str, str]]:
    clips = [{
        "name": "dev",
        "diag": "output/g3/dev_verify_diag.jsonl",
        "predictions": "output/g3/dev_verify/pipeline_output.json",
        "ground_truth": "ground_truth/video_ari_joan_8_first_points_annotations.json",
    }]
    for n in range(1, 8):
        clips.append({
            "name": f"e{n}",
            "diag": f"output/g3/e{n}_diag.jsonl",
            "predictions": f"output/g3/e{n}/pipeline_output.json",
            "ground_truth": f"ground_truth/video_entreno_{n}_annotations.json",
        })
    return clips


# --- outcome labelling (evaluate_timed's matching, waterfall's FP source) ----

def outcome_labels(ground_truth_path: str, predictions_path: str,
                   tolerance_s: float = BASE_TOLERANCE_S) -> Dict[int, Dict[str, Any]]:
    """Per predicted frame -> outcome label + what it was matched to.

    Matching is ``evaluate_timed.match_events`` (one-to-one optimal assignment
    on time distance, tolerance ``max(base, GT frame_tolerance/fps)``); actor
    identity is ignored (``--ignore-player`` semantics: team is scored only
    when both sides carry one, player_id never).
    """
    gt = load_ground_truth(ground_truth_path)
    pred_blob, _used = load_predictions(predictions_path)
    pred_events = extract_events(pred_blob)
    timebase = resolve_timebase(gt["blob"], pred_blob)
    match = match_events(gt["events"], pred_events, timebase, tolerance_s)

    out: Dict[int, Dict[str, Any]] = {}
    for g, p, _d in match["pairs"]:
        gt_team = g.get("team")
        pr_team = p.get("team")
        team_ok = not (gt_team and pr_team and gt_team != pr_team)
        label_ok = not (g.get("action") and p.get("action") and g["action"] != p["action"])
        if label_ok and team_ok:
            outcome = CORRECT
        elif not label_ok and not team_ok:
            outcome = "wrong_label_and_team"
        elif not label_ok:
            outcome = "wrong_label"
        else:
            outcome = "wrong_team"
        out[p["frame"]] = {"outcome": outcome, "gt_frame": g["frame"],
                           "gt_action": g.get("action"), "gt_team": gt_team,
                           "delta_frames": int(p["frame"]) - int(g["frame"])}

    intervals = point_intervals(gt["blob"])
    dup_of = {d["pred_frame"]: d["gt_frame"] for d in match["duplicates"]}
    matched_pred_frames = {p["frame"] for _, p, _d in match["pairs"]}
    for p in match["unmatched_pred"]:
        fp = waterfall.classify_false_positive(
            p, {}, duplicate_of=dup_of.get(p["frame"]),
            in_point=waterfall._in_point(p["frame"], intervals,
                                         waterfall.POINT_SLACK_FRAMES))
        source = fp["source"]
        outcome = {"duplicate": "duplicate",
                   "dead_time": "fp_dead_time",
                   "in_point_spurious": "fp_in_point"}[source]
        out[p["frame"]] = {"outcome": outcome,
                           "gt_frame": fp.get("duplicate_of_gt_frame"),
                           "gt_action": None, "gt_team": None, "delta_frames": None}
    return out


# --- feature extraction (diag dump + pipeline_output only) ------------------

def _point_bbox_distance(point: Sequence[float], bbox: Optional[Sequence[float]],
                         center: Optional[Sequence[float]]) -> Optional[float]:
    """Same metric as ``ActionClassifier._point_to_bbox_distance`` (static)."""
    if bbox and len(bbox) == 4:
        x1, y1, x2, y2 = bbox
        dx = max(x1 - point[0], 0.0, point[0] - x2)
        dy = max(y1 - point[1], 0.0, point[1] - y2)
        return float(math.hypot(dx, dy))
    if center:
        return float(math.hypot(center[0] - point[0], center[1] - point[1]))
    return None


def _nearest_ball_det(frames: Dict[int, Dict[str, Any]], contact: int
                      ) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
    """Nearest non-removed raw ball detection to the contact frame (<= WINDOW_F)."""
    for off in range(0, WINDOW_F + 1):
        for f in ((contact - off, contact + off) if off else (contact,)):
            rec = frames.get(f)
            if not rec:
                continue
            track_center = (rec.get("ball_track") or {}).get("center")
            dets = [d for d in rec.get("ball_dets", []) if not d.get("removed")]
            if not dets:
                continue
            if track_center:
                det = min(dets, key=lambda d: math.hypot(
                    d["center"][0] - track_center[0], d["center"][1] - track_center[1]))
            else:
                det = dets[0]
            return det, off
    return None, None


def _track_continuity(frames: Dict[int, Dict[str, Any]], contact: int
                      ) -> Tuple[Optional[float], Optional[int]]:
    """(fraction of tracked frames, longest non-tracked run) in +/- WINDOW_F."""
    states = []
    for f in range(contact - WINDOW_F, contact + WINDOW_F + 1):
        rec = frames.get(f)
        if rec is None or "ball_track" not in rec:
            continue  # frame absent from the dump: not counted either way
        states.append((rec.get("ball_track") or {}).get("state") == "tracked")
    if not states:
        return None, None
    frac = sum(states) / len(states)
    longest = run = 0
    for s in states:
        run = 0 if s else run + 1
        longest = max(longest, run)
    return frac, longest


def _ball_speeds(frames: Dict[int, Dict[str, Any]], contact: int
                 ) -> Tuple[Optional[float], Optional[float]]:
    """Mean per-frame ball displacement (px/f) just before / after the contact,
    from consecutive diag track centres (real or coasted -- both are values the
    tracker already computed)."""
    def speed(lo: int, hi: int) -> Optional[float]:
        steps = []
        for f in range(lo, hi):
            a = (frames.get(f) or {}).get("ball_track") or {}
            b = (frames.get(f + 1) or {}).get("ball_track") or {}
            ca, cb = a.get("center"), b.get("center")
            if ca and cb:
                steps.append(math.hypot(cb[0] - ca[0], cb[1] - ca[1]))
        return round(sum(steps) / len(steps), 2) if steps else None

    return speed(contact - SPEED_F, contact), speed(contact, contact + SPEED_F)


def _applicable_reach(kind: Optional[str], contact: int,
                      prev_accepted_frame: Optional[int]) -> float:
    """The gate the classifier actually applied (serve branch = wider reach)."""
    if kind == "drive" and (prev_accepted_frame is None
                            or contact - prev_accepted_frame > ActionClassifier.RALLY_RESET_GAP):
        return float(ActionClassifier.SERVE_REACH_PX)
    return float(ActionClassifier.CONTACT_REACH)


def _rejection_counts(frames: Dict[int, Dict[str, Any]], contact: int
                      ) -> Tuple[int, int]:
    gap = reach = 0
    for f in range(contact - WINDOW_F, contact + WINDOW_F + 1):
        for c in (frames.get(f) or {}).get("candidates", []) or []:
            if c.get("frame") is None or abs(c["frame"] - contact) > WINDOW_F:
                continue
            if c.get("reason") == "min_contact_gap":
                gap += 1
            elif c.get("reason") == "reach":
                reach += 1
    return gap, reach


def _round_opt(v: Optional[float], nd: int = 3) -> Optional[float]:
    return round(v, nd) if v is not None else None


def extract_features(frames: Dict[int, Dict[str, Any]], action: Dict[str, Any],
                     actions_sorted: List[Dict[str, Any]],
                     pred_intervals: List[Tuple[float, float]],
                     prev_accepted_frame: Optional[int]) -> Dict[str, Any]:
    """One prediction -> the feature dict (diag dump + pipeline output only)."""
    f = int(action["frame_number"])
    rec = frames.get(f, {})
    acc = next((c for c in rec.get("candidates", []) or []
                if c.get("stage") == "accepted" and c.get("frame") == f), {})
    passed = next((c for c in rec.get("candidates", []) or []
                   if c.get("stage") == "candidate_passed_gates" and c.get("frame") == f), {})

    det, det_off = _nearest_ball_det(frames, f)
    track_frac, max_missing = _track_continuity(frames, f)
    vin, vout = _ball_speeds(frames, f)
    # scale-invariant speeds: px/f divided by the ball's apparent width
    # (ball widths per frame).  Width 0/missing -> None; the raw px/f speed
    # is scale-DEPENDENT (far-side balls move fewer pixels), bw/f is not.
    width = (det["bbox"][2] - det["bbox"][0]) if det and det.get("bbox") else None

    contact_point = acc.get("contact_point") or passed.get("contact_point") \
        or action.get("contact_point")
    players = rec.get("players", []) or []
    distances = []
    if contact_point:
        for p in players:
            d = _point_bbox_distance(contact_point, p.get("bbox"), p.get("center"))
            if d is not None:
                distances.append((d, p))
    kind = acc.get("kind") or action.get("contact_kind")
    reach = _applicable_reach(kind, f, prev_accepted_frame)
    actor_distance = min((d for d, _p in distances), default=None)
    n_within_reach = sum(1 for d, _p in distances if d <= reach)

    gap_rej, reach_rej = _rejection_counts(frames, f)

    idx = next((i for i, a in enumerate(actions_sorted)
                if int(a["frame_number"]) == f), None)
    frames_since_prev = (None if idx in (None, 0)
                         else f - int(actions_sorted[idx - 1]["frame_number"]))

    in_point = any(a <= f <= b for a, b in pred_intervals)

    return {
        # emitted-stream fields (pipeline_output.json)
        "action": action.get("action"),
        "gesture": action.get("gesture") or acc.get("gesture"),
        "resolver_confidence": action.get("confidence"),
        "contact_kind": kind,
        "touch_number": action.get("touch_number"),
        "attribution_source": acc.get("attribution_source"),
        "team": action.get("team"),
        "rally_id": action.get("rally_id"),
        # candidate diag record fields
        "gesture_confidence": passed.get("gesture_confidence"),
        "near_net": acc.get("near_net", passed.get("near_net")),
        "behind_baseline": passed.get("behind_baseline"),
        "ball_side": acc.get("ball_side", passed.get("ball_side")),
        # ball evidence around the contact
        "ball_width_px": round(width, 1) if width else None,
        "ball_det_conf": round(det["conf"], 3) if det else None,
        "ball_det_frame_offset": det_off,
        "ball_track_conf": (_round_opt(
            ((frames.get(f) or {}).get("ball_track") or {}).get("conf"))),
        "track_frac_15f": round(track_frac, 3) if track_frac is not None else None,
        "max_missing_run_15f": max_missing,
        "ball_speed_in_px_f": vin,
        "ball_speed_out_px_f": vout,
        "ball_speed_in_bw_f": (round(vin / width, 3)
                               if vin is not None and width else None),
        "ball_speed_out_bw_f": (round(vout / width, 3)
                                if vout is not None and width else None),
        # actor / gate geometry
        "actor_distance_px": round(actor_distance, 1) if actor_distance is not None else None,
        "reach_gate_px": reach,
        "reach_margin_px": (round(actor_distance - reach, 1)
                            if actor_distance is not None else None),
        "players_within_reach": n_within_reach if distances else None,
        # local context
        "n_min_contact_gap_rejects_15f": gap_rej,
        "n_reach_rejects_15f": reach_rej,
        "frames_since_prev_action": frames_since_prev,
        "in_point_pred": in_point,
    }


# --- rows -------------------------------------------------------------------

def build_rows(clips: Sequence[Dict[str, str]],
               tolerance_s: float = BASE_TOLERANCE_S) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for clip in clips:
        diag = load_diag(clip["diag"])
        frames = diag["frames"]
        pred_blob, _used = load_predictions(clip["predictions"])
        actions = [a for a in (pred_blob.get("actions") or [])
                   if isinstance(a, dict) and a.get("frame_number") is not None]
        actions_sorted = sorted(actions, key=lambda a: int(a["frame_number"]))
        gs = pred_blob.get("game_state") or {}
        pred_intervals = [(float(p["start_frame"]), float(p["end_frame"]))
                          for p in (gs.get("points") or []) if isinstance(p, dict)]
        labels = outcome_labels(clip["ground_truth"], clip["predictions"], tolerance_s)

        # accepted-candidate frames in order -> the serve-reach branch's
        # "_last_contact_frame" reconstruction
        accepted_frames = sorted({
            c["frame"] for rec in frames.values()
            for c in (rec.get("candidates") or []) or []
            if c.get("stage") == "accepted" and c.get("frame") is not None})
        prev_of: Dict[int, Optional[int]] = {}
        for i, fr in enumerate(accepted_frames):
            prev_of[fr] = accepted_frames[i - 1] if i else None

        for a in actions_sorted:
            f = int(a["frame_number"])
            lab = labels.get(f, {"outcome": "fp_in_point"})  # defensive only
            rows.append({
                "clip": clip["name"], "frame": f,
                "outcome": lab["outcome"], "gt_frame": lab.get("gt_frame"),
                "gt_action": lab.get("gt_action"), "gt_team": lab.get("gt_team"),
                "delta_frames": lab.get("delta_frames"),
                "features": extract_features(frames, a, actions_sorted,
                                             pred_intervals, prev_of.get(f)),
            })
    return rows


# --- analysis ---------------------------------------------------------------

def outcome_counts(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    per_clip: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        per_clip[r["clip"]][r["outcome"]] += 1
    total = Counter(r["outcome"] for r in rows)
    return {
        "per_clip": {c: {o: per_clip[c].get(o, 0) for o in OUTCOME_ORDER}
                     for c in sorted(per_clip)},
        "per_clip_n": {c: sum(per_clip[c].values()) for c in sorted(per_clip)},
        "total": {o: total.get(o, 0) for o in OUTCOME_ORDER},
        "total_n": len(rows),
    }


#: feature -> (bin function, kind).  Bins are FIXED (interpretable), not
#: data-dependent, so the tables are comparable across reruns.
NUMERIC_BINS: Dict[str, List[Tuple[str, float, float]]] = {
    # name: [(label, lo, hi)] with hi=None meaning +inf
    "ball_width_px": [("<20", 0, 20), ("20-26", 20, 26), ("26-35", 26, 35),
                      ("35-45", 35, 45), (">=45", 45, None)],
    "ball_det_conf": [("<0.3", 0, 0.3), ("0.3-0.5", 0.3, 0.5),
                      ("0.5-0.7", 0.5, 0.7), (">=0.7", 0.7, None)],
    "track_frac_15f": [("<0.5", 0, 0.5), ("0.5-0.8", 0.5, 0.8),
                       ("0.8-0.95", 0.8, 0.95), (">=0.95", 0.95, None)],
    "max_missing_run_15f": [("0", 0, 1), ("1-3", 1, 4), ("4-10", 4, 11),
                            (">10", 11, None)],
    "ball_speed_in_px_f": [("<5", 0, 5), ("5-10", 5, 10), ("10-20", 10, 20),
                           (">=20", 20, None)],
    "ball_speed_out_px_f": [("<5", 0, 5), ("5-10", 5, 10), ("10-20", 10, 20),
                            (">=20", 20, None)],
    # bw/f bins straddle the measured empty gap (0.198, 0.423): the 0.2-0.4
    # bin comes out EMPTY -- the gap is visible as a hole in the table.
    "ball_speed_in_bw_f": [("<0.2", 0, 0.2), ("0.2-0.4", 0.2, 0.4),
                           ("0.4-0.6", 0.4, 0.6), (">=0.6", 0.6, None)],
    "ball_speed_out_bw_f": [("<0.2", 0, 0.2), ("0.2-0.4", 0.2, 0.4),
                            ("0.4-0.6", 0.4, 0.6), (">=0.6", 0.6, None)],
    "reach_margin_px": [("<=-40", -1e9, -40), ("-40..-20", -40, -20),
                        ("-20..-5", -20, -5), (">-5", -5, 1e9)],
    "actor_distance_px": [("<40", 0, 40), ("40-80", 40, 80), ("80-110", 80, 110),
                          (">=110", 110, None)],
    "players_within_reach": [("1", 1, 2), ("2", 2, 3), ("3+", 3, None)],
    "n_min_contact_gap_rejects_15f": [("0", 0, 1), ("1", 1, 2), ("2+", 2, None)],
    "n_reach_rejects_15f": [("0", 0, 1), ("1", 1, 2), ("2+", 2, None)],
    "frames_since_prev_action": [("first", -1, 0), ("<15", 0, 15), ("15-50", 15, 50),
                                 ("50-90", 50, 91), (">90", 91, None)],
}
CATEGORICAL_FEATURES = [
    "action", "gesture", "gesture_confidence", "resolver_confidence",
    "contact_kind", "touch_number", "attribution_source", "near_net",
    "behind_baseline", "ball_side", "in_point_pred", "reach_gate_px",
]
ALL_FEATURES = list(NUMERIC_BINS) + CATEGORICAL_FEATURES


def _bin_label(feature: str, value: Any) -> str:
    if value is None:
        # "no previous emitted action" is informative, not missing
        if feature == "frames_since_prev_action":
            return "first"
        return "unavailable"
    if feature in NUMERIC_BINS:
        v = float(value)
        for label, lo, hi in NUMERIC_BINS[feature]:
            if v >= lo and (hi is None or v < hi):
                return label
        return "unavailable"
    if isinstance(value, bool):
        return str(value)
    if feature == "touch_number":
        return str(value) if int(value) < 3 else "3+"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _bin_order(feature: str, labels) -> List[str]:
    """Numeric bins in DEFINED order (not alphabetical); 'unavailable' last."""
    if feature in NUMERIC_BINS:
        order = [lab for lab, _lo, _hi in NUMERIC_BINS[feature]]
        return [l for l in order if l in labels] + \
            [l for l in labels if l not in order]
    return sorted(labels, key=lambda l: (l == "unavailable", l))


def precision_table(rows: List[Dict[str, Any]], feature: str) -> Dict[str, Dict[str, Any]]:
    """Per category/bin: n and fraction CORRECT (everything else is a mistake)."""
    bins: Dict[str, Dict[str, int]] = defaultdict(lambda: {"n": 0, "correct": 0})
    for r in rows:
        lab = _bin_label(feature, r["features"].get(feature))
        bins[lab]["n"] += 1
        bins[lab]["correct"] += int(r["outcome"] == CORRECT)
    out: Dict[str, Dict[str, Any]] = {}
    for lab in _bin_order(feature, bins):
        b = bins[lab]
        out[lab] = {"n": b["n"], "correct": b["correct"],
                    "frac_correct": round(b["correct"] / b["n"], 3) if b["n"] else None}
    return out


def _split_eval(rows: List[Dict[str, Any]], keep) -> Dict[str, int]:
    ck = wk = cd = wd = 0
    for r in rows:
        correct = r["outcome"] == CORRECT
        if keep(r):
            ck += correct
            wk += not correct
        else:
            cd += correct
            wd += not correct
    return {"correct_kept": ck, "wrong_kept": wk, "correct_dropped": cd,
            "wrong_dropped": wd}


def best_split(rows: List[Dict[str, Any]], feature: str) -> Dict[str, Any]:
    """Best ONE-threshold/category split on a single feature.

    Candidates: for categorical features each category value v gives two splits
    (keep == v, keep != v); for numeric features every midpoint between
    consecutive sorted observed values gives two splits (keep <= t, keep > t).
    Score: accuracy; ties broken by correct_kept, then by the split string
    (deterministic).
    """
    values = sorted({r["features"].get(feature) for r in rows}
                    - {None}, key=lambda v: (isinstance(v, bool), str(v)))
    splits: List[Tuple[str, Any]] = []
    if feature in NUMERIC_BINS:
        nums = sorted(float(v) for v in values if isinstance(v, (int, float))
                      and not isinstance(v, bool))
        for a, b in zip(nums, nums[1:]):
            t = round((a + b) / 2.0, 3)
            if t == a or t == b:
                continue
            splits.append((f"<= {t:g}", lambda r, t=t: r["features"].get(feature) is not None
                           and float(r["features"][feature]) <= t))
            splits.append((f"> {t:g}", lambda r, t=t: r["features"].get(feature) is None
                           or float(r["features"][feature]) > t))
    for v in values:
        splits.append((f"== {v:g}" if isinstance(v, (int, float)) and not isinstance(v, bool)
                       else f"== {v}", lambda r, v=v: r["features"].get(feature) == v))
        splits.append((f"!= {v:g}" if isinstance(v, (int, float)) and not isinstance(v, bool)
                       else f"!= {v}", lambda r, v=v: r["features"].get(feature) != v))

    n = len(rows)
    n_correct = sum(1 for r in rows if r["outcome"] == CORRECT)
    baseline = max(n_correct, n - n_correct) / n if n else None
    best: Optional[Dict[str, Any]] = None
    for name, keep in splits:
        ev = _split_eval(rows, keep)
        acc = (ev["correct_kept"] + ev["wrong_dropped"]) / n if n else 0.0
        key = (round(acc, 6), ev["correct_kept"])
        cand = {"split": name, **ev,
                "accuracy": round(acc, 4), "baseline_accuracy": round(baseline, 4)
                if baseline is not None else None,
                "gain_vs_majority": round(acc - baseline, 4) if baseline is not None else None}
        if best is None or key > (best["accuracy"], best["correct_kept"]):
            best = cand
    return best or {"split": None}


def separability_ranking(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked = []
    for feature in ALL_FEATURES:
        bs = best_split(rows, feature)
        bs["feature"] = feature
        ranked.append(bs)
    ranked.sort(key=lambda b: (-b.get("accuracy", 0), -b.get("correct_kept", 0),
                               b["feature"]))
    return ranked


def per_clip_split_consistency(rows: List[Dict[str, Any]], label: str,
                               keep) -> Dict[str, Any]:
    """Per clip: is the SUSPECT set (the split's keep-set) WORSE than the rest?"""
    out: Dict[str, Any] = {"label": label, "clips": []}
    for clip in sorted({r["clip"] for r in rows}):
        sub = [r for r in rows if r["clip"] == clip]
        ks = [r for r in sub if keep(r["features"])]
        ds = [r for r in sub if not keep(r["features"])]

        def frac(rs):
            return round(sum(1 for r in rs if r["outcome"] == CORRECT) / len(rs), 3) if rs else None
        out["clips"].append({"clip": clip, "suspect_n": len(ks), "suspect_frac_correct": frac(ks),
                             "rest_n": len(ds), "rest_frac_correct": frac(ds),
                             "suspect_worse": (frac(ks) is not None and frac(ds) is not None
                                               and frac(ks) < frac(ds))})
    return out


#: Robust, interpretable splits whose per-clip consistency is reported in (e).
#: Chosen by hand from the measured (b) tables -- deliberately NOT the tiny
#: pure subsets the automatic search in (c) prefers.
CONSISTENCY_SPLITS: Dict[str, Tuple[str, Any]] = {
    "ball_speed_out_px_f": ("ball_speed_out < 10 px/f",
                            lambda f: f["ball_speed_out_px_f"] is not None
                            and f["ball_speed_out_px_f"] < 10),
    "track_frac_15f": ("track_frac_15f < 0.8",
                       lambda f: f["track_frac_15f"] is not None and f["track_frac_15f"] < 0.8),
    "frames_since_prev_action": ("frames_since_prev_action > 90 (serve-timing class)",
                                 lambda f: f["frames_since_prev_action"] is not None
                                 and f["frames_since_prev_action"] > 90),
    "gesture_confidence": ("gesture_confidence <= 0.5",
                           lambda f: f["gesture_confidence"] is not None
                           and f["gesture_confidence"] <= 0.5),
    "contact_kind": ("contact_kind == drive",
                     lambda f: f["contact_kind"] == "drive"),
    "in_point_pred": ("outside the pipeline's own point window",
                      lambda f: f["in_point_pred"] is False),
}


def calibration_check(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """(d): fraction CORRECT per hand-set confidence value (emitted stream)."""
    return precision_table(rows, "resolver_confidence")


# --- markdown ---------------------------------------------------------------

def render_markdown(res: Dict[str, Any], suggests: str) -> str:
    oc = res["outcome_counts"]
    L: List[str] = [
        "# G3 action evidence: what separates CORRECT emitted actions from WRONG ones",
        "",
        "Generated by `scripts/action_evidence.py` (diagnose only: no `src/` change,",
        "no GT edit). One row per PREDICTED action on the 8 clips (dev + entreno 1-7),",
        "outcomes from `evaluate_timed`'s matching (`--ignore-player` semantics,",
        "tolerance `max(0.2 s, GT frame_tolerance/fps)`) and FP sources imported from",
        "`scripts/waterfall.py`; features only from values the pipeline already",
        "computed (`--diag-dump` JSONL + `pipeline_output.json`).",
        "",
        "Runs: HEAD, `--device cpu --skip-visualization`, one `--diag-dump` per clip",
        "(`output/g3/eN_diag.jsonl`, dev = `output/g3/dev_verify_diag.jsonl`). The dev",
        "clip was RE-RUN at HEAD for this task and verified byte-identical to the T4",
        "baseline artifacts (`scripts/compare_runs.py output/t4/hookson_dev",
        "output/g3/dev_verify` -> IDENTICAL; the diag JSONLs diff empty), so the two",
        "are interchangeable; the fresh run is what this doc reads.",
        "",
        "## (a) Outcome counts",
        "",
        "| clip | " + " | ".join(OUTCOME_ORDER) + " | total |",
        "|------|" + "---:|" * (len(OUTCOME_ORDER) + 1),
    ]
    for clip in sorted(oc["per_clip"]):
        c = oc["per_clip"][clip]
        L.append(f"| {clip} | " + " | ".join(str(c[o]) for o in OUTCOME_ORDER)
                 + f" | {oc['per_clip_n'][clip]} |")
    t = oc["total"]
    L.append("| **total** | " + " | ".join(f"**{t[o]}**" for o in OUTCOME_ORDER)
             + f" | **{oc['total_n']}** |")
    L += [
        "",
        f"'correct' = matched to a GT contact with the right action AND team. n = "
        f"{oc['total_n']} predictions (~90; see caveats in (e)).",
        "Note: entreno GTs carry no point windows, so their non-duplicate FPs are all",
        "`fp_in_point` by construction (dead-time is only distinguishable on the dev clip).",
        "",
        "## (b) Precision table per feature (n and fraction CORRECT per bin)",
        "",
    ]
    for feature in ALL_FEATURES:
        tbl = res["precision_tables"][feature]
        L.append(f"### `{feature}`")
        L.append("")
        L.append("| bin | n | correct | frac correct |")
        L.append("|-----|---:|--------:|-------------:|")
        for lab, b in tbl.items():
            fr = "-" if b["frac_correct"] is None else f"{b['frac_correct']:.3f}"
            L.append(f"| {lab} | {b['n']} | {b['correct']} | {fr} |")
        L.append("")
    L += ["## (c) Single-feature separability ranking (best one-threshold/category split)", "",
          "Accuracy of 'predict correct iff the split keeps the action' vs the majority",
          "baseline; 'correct thrown away' = correct actions the split would discard.",
          "Kept-n is the support of the keep-set -- a split kept alive by 2 actions is",
          "overfit at this n; read it with the per-bin tables in (b).",
          "",
          "| rank | feature | split | accuracy | baseline | gain | kept n | correct kept | wrong kept | correct thrown |",
          "|-----:|---------|-------|---------:|---------:|-----:|-------:|-------------:|-----------:|---------------:|"]
    for i, b in enumerate(res["separability"], 1):
        L.append(f"| {i} | `{b['feature']}` | {b['split']} | {b['accuracy']:.3f} "
                 f"| {b['baseline_accuracy']:.3f} | {b['gain_vs_majority']:+.3f} "
                 f"| {b['correct_kept'] + b['wrong_kept']} "
                 f"| {b['correct_kept']} | {b['wrong_kept']} | {b['correct_dropped']} |")
    L += ["", "## (d) Calibration of the existing hand-set confidence", "",
          "Fraction CORRECT per emitted `confidence` value (the 0.45-0.75 constants):",
          "", "| confidence | n | correct | frac correct |", "|-----------:|---:|--------:|-------------:|"]
    for v, b in res["calibration"].items():
        fr = "-" if b["frac_correct"] is None else f"{b['frac_correct']:.3f}"
        L.append(f"| {v} | {b['n']} | {b['correct']} | {fr} |")
    L += ["", "## (e) What this suggests", "", suggests, "",
          "### Per-clip consistency of the headline splits", "",
          "A signal that works on one clip only is not evidence. The keep-set here is",
          "the SUSPECT set named by the split; 'suspect worse' = its fraction correct is",
          "strictly below the rest of that clip.", ""]
    for feature, entry in res["consistency"].items():
        L += [f"#### `{feature}` ({entry['label']})", "",
              "| clip | suspect n | suspect frac correct | rest n | rest frac correct | suspect worse |",
              "|------|----------:|---------------------:|-------:|------------------:|--------------:|"]
        for c in entry["clips"]:
            kf = "-" if c["suspect_frac_correct"] is None else f"{c['suspect_frac_correct']:.3f}"
            df = "-" if c["rest_frac_correct"] is None else f"{c['rest_frac_correct']:.3f}"
            L.append(f"| {c['clip']} | {c['suspect_n']} | {kf} | {c['rest_n']} | {df} "
                     f"| {c['suspect_worse']} |")
        L.append("")
    return "\n".join(L)


# --- main -------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--clip", action="append", default=[],
                   help="name:diag.jsonl:predictions.json:gt.json (repeatable; "
                        "defaults to the 8 canonical clips)")
    p.add_argument("--tolerance-s", type=float, default=BASE_TOLERANCE_S)
    p.add_argument("--json", default="output/g3/evidence.json")
    p.add_argument("--markdown", default="docs/g3_action_evidence.md")
    args = p.parse_args()

    clips = default_clips()
    if args.clip:
        clips = [{
            "name": c[0], "diag": c[1], "predictions": c[2], "ground_truth": c[3]}
            for c in (spec.split(":", 3) for spec in args.clip)]

    rows = build_rows(clips, args.tolerance_s)
    ranked = separability_ranking(rows)
    res = {
        "clips": clips,
        "tolerance_s": args.tolerance_s,
        "outcome_counts": outcome_counts(rows),
        "precision_tables": {f: precision_table(rows, f) for f in ALL_FEATURES},
        "separability": ranked,
        "calibration": calibration_check(rows),
        "consistency": {f: per_clip_split_consistency(rows, label, keep)
                        for f, (label, keep) in CONSISTENCY_SPLITS.items()},
        "rows": rows,
    }
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(res, indent=1))
    Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
    Path(args.markdown).write_text(render_markdown(res, SUGGESTS))
    print(f"rows: {len(rows)} -> {args.json}, {args.markdown}")
    oc = res["outcome_counts"]["total"]
    print("outcomes:", {k: v for k, v in oc.items() if v})
    return 0


#: 'what this suggests' text for section (e) -- measured numbers quoted from
#: the tables this script generates (85 rows: dev 29 + entreno 56).
SUGGESTS = """**Caveats first.** n = 85 predictions (~90 as briefed), but the mistakes are
not evenly placed: dev carries 21/31 non-correct outcomes (8/29 correct) while
entreno carries 10/56 wrong (46/56 correct). Any feature that differs
systematically between the dev clip and the entreno drills (ball pixel width,
resolution-dependent distances, dead-time structure) therefore separates the
POOLED table without being causal -- read (b)/(c) together with the per-clip
consistency tables below. Dead-time is only distinguishable on dev (entreno GTs
have no point windows), the duplicate class has n=1, and the automatic search
in (c) prefers tiny pure subsets (kept-n column) that are overfit at this n.

What still stands out:

1. **Outgoing-trajectory evidence is the cleanest FP signal available:**
   `ball_speed_out_px_f < 10` over the +/-15f window marks 6 of the 14
   FP/duplicate rows (dev f2195/f2414/f2445/f2494/f3265/f3639 -- dead or lost
   balls with no real post-contact departure) and ZERO of the 54 correct and
   ZERO of the 17 matched-wrong actions. Normalized by ball width it is
   cleaner still: all six sit at <= 0.198 bw/f while the lowest correct action
   is 0.423 bw/f -- an empty gap, x2.1 margin (raw px: x1.26; see R1).
   Caveat: all 6 hits are on the dev clip
   (entreno never produces the class), so per-clip consistency cannot be
   checked -- it is one clip's evidence, n=6.
2. **The serve-timing class (`frames_since_prev_action > 90` = a contact after
   a rally-reset gap):** pooled 2/12 correct vs 52/73; it holds 4 of the 4
   mislabeled serve FPs (f1039/f2195/f2414/f3595, all `drive` candidates) plus
   f3265 -- but it also flags 4 matched-wrong and kills 2 correct actions, and
   within entreno the class is almost empty (1 hit on e1). `contact_kind ==
   drive` is the same family: pooled 4/12 correct, dev 0/8.
3. **Ball-track continuity (`track_frac_15f`)** is the only pre-computed
   feature with a monotone pooled gradient (0.333 / 0.444 / 0.703 / 0.704
   across its four bins; best split > 0.726: accuracy 0.718 vs 0.635 baseline,
   3 correct thrown). Within dev it holds (0.10 vs 0.37); within entreno the
   <0.8 bin holds only 11 of 56 actions and the per-clip tables below never
   show a REVERSAL (3 clips confirm, 4 have <=2 suspect rows) -- the pooled
   entreno gradient (0.778 -> 0.889 across bins) is real but sparse, and it
   lives where the pipeline is already right 82% of the time.
4. **Game-state agreement** (`outside the pipeline's own point window`):
   catches 6 dev FPs, but ALSO 3 correct entreno actions (e3 f29/f74, e5 f68 --
   drill clips whose game-state windows under-cover) -- direction REVERSES on
   entreno, so it is not a safe veto on its own; as a low-weight flag it is
   fine.
5. **Gesture confidence carries a weak FP gradient** (`gesture_confidence <=
   0.5`: 8/14 FPs flagged, but 4/54 correct and 3/17 matched-wrong flagged too)
   -- and the per-clip tables below show it REVERSES on entreno (all 4 entreno
   suspect rows are correct, e.g. e1 1/1 vs a 0.571 clip average). Usable as
   one input to a score, never as a rule.
6. **Attribution signals barely separate**: `attribution_source == width`
   45/64 correct vs carry 7/14, None 2/6, flip 0/1; `near_net` 40/62 vs 14/23 --
   both inside the noise at this n.

**(d) says the hand-set confidence is not a confidence.** The fraction-correct
per constant is non-monotone and near-flat: 0.45 -> 0/3, 0.5 -> 0.667,
0.55 -> 0.622, 0.6 -> 0.800, 0.65 -> 0.750, 0.7 -> 0/1, 0.75 -> 0.500. The
HIGHEST constant (0.75) is less trustworthy than 0.55, and on entreno alone
the two workhorse constants are indistinguishable (0.55 -> 0.864, 0.6 -> 0.875).
No ordering of correctness exists along the emitted `confidence` axis.

### Recommended next mechanisms (max 2, ranked, NOT implemented)

**R1 (FP removal): an outgoing-trajectory evidence requirement at emission,
measured in BALL WIDTHS PER FRAME (scale-invariant).** An emitted action must
show post-contact ball departure in the window it was confirmed in, normalized
by the ball's apparent width: `ball_speed_out_bw_f = ball_speed_out_px_f /
ball_width_px`. The 6 FPs the raw-px gate flagged (`speed_out < 10 px/f`) all
sit at <= 0.198 bw/f while the LOWEST correct action is 0.423 bw/f (dev f1396
w=51 px, e4 f327 w=36 px) -- an EMPTY gap: across all 85 rows no outcome class
whatsoever falls in (0.198, 0.423), so a threshold anywhere inside it (e.g.
0.3 bw/f) flags 6/14 FP/duplicate rows with zero collateral of any kind (0/54
correct, 0/17 matched-wrong, 0/1 duplicate). The margin is x2.1; raw px has
only x1.26 (9.07 max flagged FP vs 11.44 min correct) AND its "gap" is
occupied by non-correct rows (dev f355 duplicate at 10.37 px/f, f398 fp at
11.05 px/f). A raw-px gate is scale-DEPENDENT: far-side balls (widths
13-28 px) move fewer pixels for the same real speed, so a px threshold is
biased against far-side contacts. The correct actions nearest the normalized
gap (the 8 correct < 0.6 bw/f, widths 54/51/49/36/36/29/25/21 px) split
5 near / 2 far / 1 ambiguous (26-35 px); the two far-side ones (0.470, 0.545
bw/f) still clear the gap by >2x -- whereas in raw px those same two are the
closest to a 10 px/f line (11.44/11.75 px/f), i.e. the px gate would sit
right on top of them and the bw/f gate does not. Per-clip: all 6 suspects are
dev (fp_in_point f2195/f2414/f2445/f2494 + fp_dead_time f3265/f3639);
e1-e7 contribute 0 suspects at < 0.3 bw/f, so per-clip consistency remains
uncheckable -- one clip's evidence. Causality: the out window is
SPEED_F = ActionClassifier.CONTACT_DELAY frames (read from the classifier
code, 7 at HEAD), and the classifier confirms a contact at
contact_frame + CONTACT_DELAY -- so the normalized departure signal is fully
computable from frames already seen at confirmation time and can gate
emission without lookahead. Optionally still OR'd with the game-state
agreement flag (`outside own point window`) -> 9/14, but that half costs 3
correct entreno actions, so it should FLAG, not drop. Honest scope: dev-only
evidence (n=6 hits, one clip), leaves 8/14 (dev f355/f398/f4067/f930/f1039/
f3595 + e4 f284/f388).

**R2 (per-action confidence): replace the hand-set constants with a calibrated
continuity-weighted score.** Start from the two signals with a measured
gradient -- ball-track continuity (`track_frac_15f`, 0.44 -> 0.70 pooled) and
the gesture tier (`gesture_confidence <= 0.5` holds 8/14 FPs but 4/54 correct)
-- as an ordinal 3-tier score, calibrated leave-one-clip-out on these 85 rows
and re-measured on the next match clip before shipping. The current constants
carry no information about correctness ((d): 0.75 -> 0.5 vs 0.55 -> 0.622), so
any monotone use of continuity is already an improvement; the exact weighting
needs more wrong outcomes than these 31 to fit.
"""

if __name__ == "__main__":
    sys.exit(main())
