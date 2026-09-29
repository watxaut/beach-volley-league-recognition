#!/usr/bin/env python3
"""Time-matched evaluator (sibling of ``scripts/evaluate.py``).

``evaluate.py`` matches actions by FRAME NUMBER and scores one number per
action class.  This script keeps that behaviour available (the loaders are
imported, the file is never modified) and adds the *time* axis the action
reliability plan asks for (task T3):

* timestamps in SECONDS -- per-frame PTS when the prediction/GT blob carries
  one (VFR-aware, no video decoded), otherwise ``frame / fps``;
* ONE-TO-ONE optimal assignment on time distance (scipy linear_sum_assignment)
  with a tolerance of ``max(--tolerance-s, GT frame_tolerance / fps)``;
* SEPARATE scores instead of one blended F1:
    - contact detection P/R/F1 (class-agnostic: "was the contact found at all")
    - class accuracy + full confusion matrix on the matched pairs
    - team accuracy on the matched pairs
    - actor accuracy on the matched pairs (n/a when the GT ``player_id`` is
      null or ``--ignore-player``)
    - duplicates: extra predictions within tolerance of an ALREADY matched GT
      event (the double-emission class, invisible in a count-based F1)
    - false positives per DEAD-TIME MINUTE (outside the GT point intervals),
      which is the metric that is not flattered by long games
* point intervals matched to GT points by temporal IoU (matched / missed /
  spurious) -- not a count ratio;
* ``--autonomous``: refuse to score a prediction file that carries GT-derived
  inputs (point winners, serve anchors, owner pins/verdicts).  What is checked
  is documented in :func:`find_gt_derived_inputs`.

Usage::

    python scripts/evaluate_timed.py \
        --predictions output/e15e/post_actions/video_entreno_1_action_log.json \
        --ground-truth ground_truth/video_entreno_1_annotations.json \
        --ignore-player --json output/t3_e1.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:  # scipy is the reference assignment solver
    from scipy.optimize import linear_sum_assignment
except Exception:  # pragma: no cover - exercised only without scipy
    linear_sum_assignment = None

# --- tunables ---------------------------------------------------------------

BASE_TOLERANCE_S = 0.2
#: cost used for pairs outside tolerance; any assignment paying it is dropped.
INFEASIBLE = 1e6

#: Metadata keys that betray a GT-derived input in a PREDICTION file.
#: Matched case-insensitively against any key of the blob's top level,
#: ``metadata``/``video``/``game_state``/``map`` sub-dicts, and every action /
#: spike / point dict.  Rationale per group in the docstring of
#: :func:`find_gt_derived_inputs`.
GT_DERIVED_KEY_PATTERNS = (
    "winner",           # point/scoreboard outcome (owner-dictated)
    "score",
    "serve_anchor",     # ground_truth/*_serve_anchors.txt
    "anchor",           # generic frame anchor
    "owner_pin",        # OWNER_PINNED_SERVES
    "owner_verdict",    # owner adjudication sheet verdicts
    "owner_contact",    # dictated contact list
    "map_attribution",  # episode->point map (anchored)
    "serve_relabel",    # pass-2 re-label decisions
    "gt_",              # anything literally prefixed gt_
    "ground_truth",
)
#: Keys that are NOT evidence of a GT input even though they look similar.
GT_DERIVED_KEY_ALLOW = ("anchor_only", "owner_note", "source_detail")

#: Candidate key names for a per-frame PTS / timestamp vector.
PTS_KEYS = (
    "frame_timestamps", "frame_pts", "frame_times", "timestamps", "pts",
    "presentation_timestamps", "timebase",
)


# --- loading ----------------------------------------------------------------

try:  # reuse evaluate.py's loader so both scripts read files identically
    from evaluate import load_json  # type: ignore
except ImportError:  # pragma: no cover - when run outside the repo root
    def load_json(path: str) -> Any:
        with open(path, "r") as f:
            return json.load(f)


def _first(d: Dict[str, Any], *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return default


def _frame_of(evt: Dict[str, Any]) -> Optional[int]:
    f = _first(evt, "frame", "frame_number", "frame_idx", "frame_index")
    return int(f) if f is not None else None


def normalize_event(evt: Dict[str, Any]) -> Dict[str, Any]:
    """Prediction/GT event -> {frame, action, team, player_id, raw}."""
    return {
        "frame": _frame_of(evt),
        "action": _first(evt, "action", "final_action", default=None),
        "team": _first(evt, "team", "player_team", "pass2_team"),
        "player_id": _first(evt, "player_id", "track_id"),
        "raw": evt,
    }


def extract_events(blob: Any) -> List[Dict[str, Any]]:
    """Pull the action-event list out of any prediction/GT layout.

    Accepts: a bare list (the ``*_action_log.json`` files), ``{"actions": [...]}``,
    ``{"actions": {"events": [...]}}``, and a ``pipeline_output.json``
    (``{"actions": [{"frame_number": ...}]}``).
    """
    if isinstance(blob, list):
        events = blob
    elif isinstance(blob, dict):
        events = _first(blob, "actions", "action_events", "events", default=[])
        if isinstance(events, dict):
            events = _first(events, "events", "actions", default=[])
    else:
        events = []
    out = []
    for e in events or []:
        if isinstance(e, dict) and _frame_of(e) is not None:
            out.append(normalize_event(e))
    return out


def load_predictions(path: str) -> Tuple[Any, str]:
    """Load predictions from a file or a directory (same shapes as evaluate.py).

    A directory is scanned for ``*.json``; the first file that yields events
    wins, else the first JSON is returned (so the autonomous/GT-input check can
    still see a metadata-only file).
    """
    p = Path(path)
    if p.is_file():
        return load_json(str(p)), str(p)
    if p.is_dir():
        fallback = None
        for f in sorted(p.glob("*.json")):
            try:
                blob = load_json(str(f))
            except Exception:
                continue
            if fallback is None:
                fallback = (blob, str(f))
            if extract_events(blob):
                return blob, str(f)
        if fallback is None:
            raise SystemExit(f"Error: no JSON predictions found in {path}")
        return fallback
    raise SystemExit(f"Error: predictions path not found: {path}")


def load_ground_truth(path: str) -> Dict[str, Any]:
    """GT blob + events, with owner-ratified ``overrides`` merged (as evaluate.py)."""
    gt = load_json(path)
    events = extract_events(gt.get("annotated_frames", gt) if isinstance(gt, dict) else gt)
    # evaluate.py grades the RATIFIED truth: merge each event's `overrides`
    # block over it (e5 f300 poke, e6 f310 hard spike, ...).
    merged = []
    for ev in events:
        raw = ev["raw"]
        if isinstance(raw, dict) and isinstance(raw.get("overrides"), dict):
            merged.append(normalize_event({**raw, **raw["overrides"]}))
        else:
            merged.append(ev)
    return {"blob": gt, "events": merged}


# --- time base --------------------------------------------------------------

class TimeBase:
    """frame -> seconds.  PTS-aware (VFR) with a frame/fps fallback.

    No video is decoded: when a PTS vector is present we interpolate inside it
    (that is all a VFR file needs to convert an arbitrary frame index), else we
    divide by the nominal fps.
    """

    def __init__(self, fps: float, pts: Optional[Sequence[float]] = None):
        self.fps = float(fps) if fps else 0.0
        self.pts = list(pts) if pts else None
        self.source = "pts" if self.pts else "frame/fps"

    def t(self, frame: Optional[float]) -> Optional[float]:
        if frame is None:
            return None
        if self.pts:
            if frame < 0:
                return None
            if frame >= len(self.pts) - 1:
                return float(self.pts[-1]) + (frame - (len(self.pts) - 1)) / (self.fps or 1.0)
            lo = int(frame)
            frac = frame - lo
            return float(self.pts[lo]) + frac * (float(self.pts[lo + 1]) - float(self.pts[lo]))
        if not self.fps:
            return None
        return float(frame) / self.fps


def _find_pts(blob: Any) -> Optional[List[float]]:
    """Locate a per-frame PTS/timestamp vector in a blob (list or {frame: t})."""
    if not isinstance(blob, dict):
        return None
    containers = [blob]
    for k in ("metadata", "video", "frame_indexing", "provenance"):
        if isinstance(blob.get(k), dict):
            containers.append(blob[k])
    for c in containers:
        for k in PTS_KEYS:
            v = c.get(k)
            if isinstance(v, dict):
                try:
                    return [float(v[i]) for i in sorted(int(i) for i in v)]
                except Exception:
                    continue
            if isinstance(v, (list, tuple)) and len(v) > 1:
                if all(isinstance(x, (int, float)) for x in v):
                    return [float(x) for x in v]
    return None


def _find_fps(*blobs) -> Optional[float]:
    for b in blobs:
        if not isinstance(b, dict):
            continue
        for c in (b, b.get("video") if isinstance(b.get("video"), dict) else None,
                  b.get("metadata") if isinstance(b.get("metadata"), dict) else None):
            if not isinstance(c, dict):
                continue
            f = _first(c, "fps", "average_fps", "avg_fps", "nominal_fps", "frame_rate")
            if f:
                try:
                    return float(f)
                except (TypeError, ValueError):
                    continue
    return None


def resolve_timebase(gt_blob: Any, pred_blob: Any) -> TimeBase:
    pts = _find_pts(pred_blob) or _find_pts(gt_blob)
    fps = _find_fps(pred_blob, gt_blob)
    if pts is None and not fps:
        raise SystemExit("Error: no fps and no PTS vector in predictions/ground truth")
    return TimeBase(fps or 0.0, pts)


# --- matching ---------------------------------------------------------------

def _optimal_pairs(cost: List[List[float]]) -> List[Tuple[int, int]]:
    """Min-cost one-to-one assignment, dropping infeasible (INFEASIBLE) pairs."""
    if not cost or not cost[0]:
        return []
    if linear_sum_assignment is not None:
        import numpy as np
        m = np.asarray(cost, dtype=float)
        r, c = linear_sum_assignment(m)
        return [(int(i), int(j)) for i, j in zip(r, c) if m[i, j] < INFEASIBLE]
    # Greedy fallback (deterministic, same answer on well-separated events).
    flat = sorted(
        ((cost[i][j], i, j) for i in range(len(cost)) for j in range(len(cost[i]))
         if cost[i][j] < INFEASIBLE),
    )
    used_r, used_c, out = set(), set(), []
    for _, i, j in flat:
        if i in used_r or j in used_c:
            continue
        used_r.add(i)
        used_c.add(j)
        out.append((i, j))
    return sorted(out)


def event_tolerance_s(gt_event: Dict[str, Any], base_tolerance_s: float,
                      timebase: TimeBase) -> float:
    """max(base, per-event GT frame_tolerance / fps) -- the coarse-±15f case."""
    tol = base_tolerance_s
    ftol = (gt_event["raw"] or {}).get("frame_tolerance")
    if ftol and timebase.fps:
        tol = max(tol, float(ftol) / timebase.fps)
    return float(tol)


def match_events(gt_events: List[Dict[str, Any]], pred_events: List[Dict[str, Any]],
                 timebase: TimeBase, base_tolerance_s: float = BASE_TOLERANCE_S
                 ) -> Dict[str, Any]:
    """One-to-one optimal matching of predictions to GT events on time distance.

    Class-agnostic on purpose: the CONTACT was found or it was not; whether the
    label is right is scored separately (class accuracy + confusion matrix).
    """
    gt = sorted([e for e in gt_events if e["frame"] is not None], key=lambda e: e["frame"])
    pr = sorted([e for e in pred_events if e["frame"] is not None], key=lambda e: e["frame"])
    gt_t = [timebase.t(e["frame"]) for e in gt]
    pr_t = [timebase.t(e["frame"]) for e in pr]
    tols = [event_tolerance_s(e, base_tolerance_s, timebase) for e in gt]

    cost: List[List[float]] = []
    for i, t in enumerate(gt_t):
        row = []
        for j, u in enumerate(pr_t):
            row.append(abs(u - t) if (t is not None and u is not None and abs(u - t) <= tols[i])
                       else INFEASIBLE)
        cost.append(row)

    pairs = _optimal_pairs(cost)
    matched_gt = {i for i, _ in pairs}
    matched_pr = {j for _, j in pairs}

    # Duplicates: an UNMATCHED prediction sitting inside the tolerance of a GT
    # event that already consumed another prediction (double emission).
    duplicates: List[Dict[str, Any]] = []
    for j, p in enumerate(pr):
        if j in matched_pr or pr_t[j] is None:
            continue
        for i in range(len(gt)):
            if i not in matched_gt or gt_t[i] is None:
                continue
            d = abs(pr_t[j] - gt_t[i])
            if d <= tols[i]:
                duplicates.append({
                    "pred_frame": p["frame"], "pred_action": p["action"],
                    "gt_frame": gt[i]["frame"], "gt_action": gt[i]["action"],
                    "delta_s": round(d, 4),
                })
                break

    return {
        "pairs": [(gt[i], pr[j], abs(pr_t[j] - gt_t[i])) for i, j in pairs],
        "unmatched_gt": [gt[i] for i in range(len(gt)) if i not in matched_gt],
        "unmatched_pred": [pr[j] for j in range(len(pr)) if j not in matched_pr],
        "duplicates": duplicates,
        "n_gt": len(gt), "n_pred": len(pr),
        "tolerances_s": tols,
    }


# --- scoring ----------------------------------------------------------------

def _prf(tp: int, fp: int, fn: int) -> Dict[str, Any]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn}


def score_contacts(match: Dict[str, Any]) -> Dict[str, Any]:
    tp = len(match["pairs"])
    fp = len(match["unmatched_pred"])
    fn = len(match["unmatched_gt"])
    out = _prf(tp, fp, fn)
    out["duplicates"] = len(match["duplicates"])
    out["fp_excluding_duplicates"] = max(0, fp - len(match["duplicates"]))
    return out


def score_labels(match: Dict[str, Any]) -> Dict[str, Any]:
    """Class accuracy + confusion matrix on the matched (time-aligned) pairs."""
    ok = scored = 0
    matrix: Dict[str, Dict[str, int]] = {}
    for gt, pr, _d in match["pairs"]:
        g = gt["action"] or "<none>"
        p = pr["action"] or "<none>"
        matrix.setdefault(g, {})
        matrix[g][p] = matrix[g].get(p, 0) + 1
        if pr["action"] is not None and gt["action"] is not None:
            scored += 1
            ok += int(pr["action"] == gt["action"])
    return {
        "class_accuracy": round(ok / scored, 4) if scored else None,
        "class_scored": scored,
        "confusion_matrix": matrix,
    }


def score_attribution(match: Dict[str, Any], ignore_player: bool) -> Dict[str, Any]:
    team_scored = team_ok = 0
    pl_scored = pl_ok = 0
    for gt, pr, _d in match["pairs"]:
        if gt["team"] is not None and pr["team"] is not None:
            team_scored += 1
            team_ok += int(gt["team"] == pr["team"])
        if ignore_player:
            continue
        if gt["player_id"] is not None and pr["player_id"] is not None:
            pl_scored += 1
            pl_ok += int(gt["player_id"] == pr["player_id"])
    return {
        "team_accuracy": round(team_ok / team_scored, 4) if team_scored else None,
        "team_scored": team_scored,
        "actor_accuracy": (round(pl_ok / pl_scored, 4)
                           if (pl_scored and not ignore_player) else None),
        "actor_scored": pl_scored,
        "actor_scoring": "skipped (--ignore-player)" if ignore_player
                         else ("no GT/pred player_id on matched pairs" if not pl_scored
                               else "scored"),
    }


# --- point intervals --------------------------------------------------------

def point_intervals(blob: Any) -> List[Tuple[float, float]]:
    """Extract [(start_s, end_s)] point windows from a blob (frames or seconds)."""
    if not isinstance(blob, dict):
        return []
    pts = blob.get("points")
    if pts is None:
        gs = blob.get("game_state")
        if isinstance(gs, dict):
            pts = gs.get("points")
    if not isinstance(pts, list):
        return []
    out = []
    for p in pts:
        if not isinstance(p, dict):
            continue
        a = _first(p, "start_frame", "clip_start_frame", "start", "start_time_s",
                   "start_s", "first_frame")
        b = _first(p, "end_frame", "clip_end_frame", "end", "end_time_s",
                   "end_s", "last_frame")
        if a is None or b is None:
            continue
        try:
            out.append((float(a), float(b)))
        except (TypeError, ValueError):
            continue
    return out


def point_intervals_from_rallies(pred_events: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
    """Fallback: one interval per rally_id, spanning its action frames."""
    by_rally: Dict[Any, List[int]] = {}
    for e in pred_events:
        rid = (e["raw"] or {}).get("rally_id")
        if rid is None or e["frame"] is None:
            continue
        by_rally.setdefault(rid, []).append(e["frame"])
    return [(min(v), max(v)) for _, v in sorted(by_rally.items(), key=lambda kv: min(kv[1]))]


def temporal_iou(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    inter = max(0.0, hi - lo)
    union = (a[1] - a[0]) + (b[1] - b[0]) - inter
    return inter / union if union > 0 else 0.0


def score_points(gt_iv: List[Tuple[float, float]], pred_iv: List[Tuple[float, float]],
                 timebase: TimeBase) -> Dict[str, Any]:
    """One-to-one matching of predicted points to GT points by temporal IoU."""
    g = [tuple(timebase.t(f) for f in iv) for iv in gt_iv]
    p = [tuple(timebase.t(f) for f in iv) for iv in pred_iv]
    g = [iv for iv in g if iv[0] is not None and iv[1] is not None]
    p = [iv for iv in p if iv[0] is not None and iv[1] is not None]
    if not gt_iv:
        return {"available": False,
                "reason": "no GT point intervals (GT has no points/clip_start-end)"}
    if not p:
        return {"available": True, "gt_points": len(g), "predicted_points": 0,
                "matched": 0, "missed": len(g), "spurious": 0, "mean_iou": None,
                "ious": []}
    cost = [[(1.0 - temporal_iou(a, b)) if temporal_iou(a, b) > 0 else INFEASIBLE
             for b in p] for a in g]
    pairs = _optimal_pairs(cost)
    ious = [temporal_iou(g[i], p[j]) for i, j in pairs]
    return {
        "available": True,
        "gt_points": len(g), "predicted_points": len(p),
        "matched": len(pairs), "missed": len(g) - len(pairs),
        "spurious": len(p) - len(pairs),
        "mean_iou": round(sum(ious) / len(ious), 4) if ious else None,
        "ious": [round(v, 3) for v in ious],
    }


def clip_duration_s(gt_blob: Any, pred_blob: Any, timebase: TimeBase,
                    events: List[Dict[str, Any]], intervals: List[Tuple[float, float]]
                    ) -> Optional[float]:
    """Best available clip length in seconds, from metadata or the last frame."""
    for blob in (gt_blob, pred_blob):
        if not isinstance(blob, dict):
            continue
        cands = [blob, blob.get("video")] if isinstance(blob.get("video"), dict) else [blob]
        for c in cands:
            d = _first(c, "duration_s", "duration")
            if d:
                return float(d)
            nf = _first(c, "total_frames", "n_frames", "frame_count", "clip_container_frames")
            if nf:
                return timebase.t(float(nf) - 1) or (float(nf) - 1) / (timebase.fps or 1.0)
    frames = [e["frame"] for e in events if e["frame"] is not None]
    frames += [f for iv in intervals for f in iv]
    if frames and timebase.fps:
        return max(max(frames) / timebase.fps, timebase.t(max(frames)) or 0.0)
    return None


def dead_time_score(match: Dict[str, Any], gt_iv: List[Tuple[float, float]],
                    duration_s: Optional[float], timebase: TimeBase) -> Dict[str, Any]:
    """False positives per minute OUTSIDE the GT point intervals."""
    if not gt_iv or duration_s is None:
        return {"available": False,
                "reason": ("no GT point intervals" if not gt_iv
                           else "no clip duration in predictions/GT metadata")}
    iv = [(timebase.t(a), timebase.t(b)) for a, b in gt_iv]
    iv = [(a, b) for a, b in iv if a is not None and b is not None]
    live = 0.0
    for a, b in sorted(iv):
        start = max(a, 0.0)
        end = min(b, duration_s)
        if end > start:
            live += end - start
    dead_min = max(0.0, duration_s - live) / 60.0
    fp_dead = 0
    for p in match["unmatched_pred"]:
        t = timebase.t(p["frame"])
        if t is None:
            continue
        if not any(a <= t <= b for a, b in iv):
            fp_dead += 1
    return {
        "available": True,
        "duration_s": round(duration_s, 2),
        "live_s": round(live, 2),
        "dead_s": round(duration_s - live, 2),
        "dead_minutes": round(dead_min, 3),
        "fp_in_dead_time": fp_dead,
        "fp_per_dead_minute": (round(fp_dead / dead_min, 3) if dead_min > 0 else None),
    }


# --- autonomous guard -------------------------------------------------------

def find_gt_derived_inputs(blob: Any, _path: str = "$",
                           _depth: int = 0) -> List[Dict[str, Any]]:
    """Walk a PREDICTION blob and report keys that betray GT-derived inputs.

    Checked (case-insensitive substring match on dict keys, at any depth <= 6):
      * ``winner`` / ``score``            -- owner-dictated point outcome
      * ``serve_anchor`` / ``anchor``     -- serve-anchor file consumption
      * ``owner_pin`` / ``owner_verdict`` / ``owner_contact`` -- owner adjudication
      * ``map_attribution`` / ``serve_relabel*`` -- the pass-2 map/re-label layers
      * ``gt_*`` / ``ground_truth*``      -- any explicitly GT-named input
    Keys in ``GT_DERIVED_KEY_ALLOW`` are exempt (provenance notes, not inputs).
    """
    findings: List[Dict[str, Any]] = []
    if _depth > 6:
        return findings
    if isinstance(blob, dict):
        for k, v in blob.items():
            kl = str(k).lower()
            hit = next((p for p in GT_DERIVED_KEY_PATTERNS if p in kl), None)
            if hit and not any(a in kl for a in GT_DERIVED_KEY_ALLOW):
                findings.append({"path": f"{_path}.{k}", "key": k, "pattern": hit,
                                 "value": _short(v)})
            findings += find_gt_derived_inputs(v, f"{_path}.{k}", _depth + 1)
    elif isinstance(blob, list):
        for i, v in enumerate(blob[:200]):
            findings += find_gt_derived_inputs(v, f"{_path}[{i}]", _depth + 1)
    return findings


def _short(v: Any) -> Any:
    s = v if isinstance(v, (str, int, float, bool, type(None))) else str(v)
    return s if not isinstance(s, str) or len(s) <= 80 else s[:77] + "..."


# --- orchestration ----------------------------------------------------------

def evaluate_timed(predictions_path: str, ground_truth_path: str,
                   tolerance_s: float = BASE_TOLERANCE_S, ignore_player: bool = False,
                   autonomous: bool = False,
                   pred_points_source: str = "auto") -> Dict[str, Any]:
    gt = load_ground_truth(ground_truth_path)
    pred_blob, pred_used = load_predictions(predictions_path)
    pred_events = extract_events(pred_blob)

    if autonomous:
        findings = find_gt_derived_inputs(pred_blob)
        if findings:
            raise SystemExit(
                "Autonomous mode refused: the prediction file carries GT-derived inputs:\n"
                + "\n".join(f"  {f['path']} = {f['value']!r} (matched '{f['pattern']}')"
                            for f in findings[:40])
                + "\nAutonomous scoring requires predictions derived WITHOUT GT "
                  "(no point winners, no serve anchors, no owner pins/verdicts). "
                  "Re-run without --autonomous to score it as GT-assisted."
            )

    timebase = resolve_timebase(gt["blob"], pred_blob)
    match = match_events(gt["events"], pred_events, timebase, tolerance_s)

    gt_iv = point_intervals(gt["blob"])
    if pred_points_source in ("auto", "intervals"):
        pred_iv = point_intervals(pred_blob)
    else:
        pred_iv = []
    if not pred_iv and pred_points_source == "auto":
        pred_iv = point_intervals_from_rallies(pred_events)
    elif not pred_iv and pred_points_source == "rallies":
        pred_iv = point_intervals_from_rallies(pred_events)

    duration = clip_duration_s(gt["blob"], pred_blob, timebase,
                               gt["events"] + pred_events, gt_iv)

    res = {
        "predictions": pred_used,
        "ground_truth": ground_truth_path,
        "time": {
            "source": timebase.source,
            "fps": round(timebase.fps, 4) if timebase.fps else None,
            "tolerance_base_s": tolerance_s,
            "note": ("per-frame PTS vector found in predictions/GT metadata"
                     if timebase.source == "pts"
                     else "no PTS vector found -> frame/fps (VFR frame spacing assumed uniform)"),
        },
        "autonomous": bool(autonomous),
        "ignore_player": bool(ignore_player),
        "counts": {"gt_events": match["n_gt"], "pred_events": match["n_pred"]},
        "contact": score_contacts(match),
        "labels": score_labels(match),
        "attribution": score_attribution(match, ignore_player),
        "dead_time": dead_time_score(match, gt_iv, duration, timebase),
        "points": score_points(gt_iv, pred_iv, timebase),
    }
    if res["points"].get("available"):
        res["points"]["pred_source"] = pred_points_source
    res["details"] = {
        "unmatched_gt": [{"frame": e["frame"], "action": e["action"]}
                         for e in match["unmatched_gt"]],
        "unmatched_pred": [{"frame": e["frame"], "action": e["action"]}
                           for e in match["unmatched_pred"]],
        "duplicates": match["duplicates"],
    }
    return res


def format_report(res: Dict[str, Any]) -> str:
    c, lab, at = res["contact"], res["labels"], res["attribution"]
    lines = [
        "=" * 68,
        f"  TIME-MATCHED EVALUATION  ({Path(res['predictions']).name})",
        "=" * 68,
        f"  time source        : {res['time']['source']}"
        + (f" @ {res['time']['fps']} fps" if res["time"]["fps"] else ""),
        f"  base tolerance     : {res['time']['tolerance_base_s']} s"
        " (per-event max with GT frame_tolerance/fps)",
        f"  events             : GT {res['counts']['gt_events']} /"
        f" pred {res['counts']['pred_events']}",
        "",
        f"  CONTACT (class-agnostic)  P {c['precision']:.3f}  R {c['recall']:.3f}"
        f"  F1 {c['f1']:.3f}",
        f"    tp {c['tp']}  fp {c['fp']} (duplicates {c['duplicates']})"
        f"  fn {c['fn']}",
    ]
    lines.append("  CLASS accuracy on matched pairs : "
                 + (f"{lab['class_accuracy']:.3f} (n={lab['class_scored']})"
                    if lab["class_accuracy"] is not None else "n/a"))
    if lab["confusion_matrix"]:
        lines.append("    confusion (gt -> pred):")
        for g, row in sorted(lab["confusion_matrix"].items()):
            lines.append(f"      {g:<10} " + "  ".join(f"{p}={n}" for p, n in sorted(row.items())))
    lines += [
        "  TEAM accuracy on matched pairs  : "
        + (f"{at['team_accuracy']:.3f} (n={at['team_scored']})"
           if at["team_accuracy"] is not None else "n/a"),
        "  ACTOR accuracy on matched pairs : "
        + (f"{at['actor_accuracy']:.3f} (n={at['actor_scored']})"
           if at["actor_accuracy"] is not None else f"n/a ({at['actor_scoring']})"),
    ]
    dt = res["dead_time"]
    lines.append("  FP per DEAD-TIME minute       : "
                 + (f"{dt['fp_per_dead_minute']} ({dt['fp_in_dead_time']} FP over"
                    f" {dt['dead_minutes']} min of {dt['duration_s']} s)"
                    if dt.get("available") else f"n/a ({dt.get('reason')})"))
    pt = res["points"]
    lines.append("  POINT intervals (temporal IoU) : "
                 + (f"matched {pt['matched']}  missed {pt['missed']}"
                    f"  spurious {pt['spurious']}  mean IoU {pt['mean_iou']}"
                    if pt.get("available") else f"n/a ({pt.get('reason')})"))
    if res.get("details", {}).get("duplicates"):
        lines.append("  duplicates:")
        for d in res["details"]["duplicates"][:10]:
            lines.append(f"    pred f{d['pred_frame']} {d['pred_action']} vs GT f"
                         f"{d['gt_frame']} {d['gt_action']} ({d['delta_s']}s)")
    lines.append("=" * 68)
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(
        description="Time-matched evaluation of volleyball action predictions (sibling of evaluate.py)")
    p.add_argument("--predictions", required=True,
                   help="Prediction JSON file or directory (same shapes as evaluate.py)")
    p.add_argument("--ground-truth", required=True, help="GT annotations JSON")
    p.add_argument("--tolerance-s", type=float, default=BASE_TOLERANCE_S,
                   help="Base matching tolerance in seconds (default 0.2)")
    p.add_argument("--ignore-player", action="store_true",
                   help="Do not score actor accuracy (GT player_id is a per-frame L-R index)")
    p.add_argument("--autonomous", action="store_true",
                   help="Refuse to score a prediction file carrying GT-derived inputs "
                        "(winners, serve anchors, owner pins/verdicts)")
    p.add_argument("--pred-points", choices=["auto", "intervals", "rallies"],
                   default="auto",
                   help="Where predicted point windows come from: game_state/points "
                        "intervals, rally_id groups, or auto (default)")
    p.add_argument("--json", help="Write the full result dict to this path")
    args = p.parse_args()

    res = evaluate_timed(args.predictions, args.ground_truth, args.tolerance_s,
                         ignore_player=args.ignore_player, autonomous=args.autonomous,
                         pred_points_source=args.pred_points)
    print(format_report(res))
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json, "w") as f:
            json.dump(res, f, indent=2)
        print(f"\nResults saved to {args.json}")


if __name__ == "__main__":
    main()
