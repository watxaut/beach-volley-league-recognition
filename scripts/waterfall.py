#!/usr/bin/env python3
"""Loss waterfall: for every GT contact, the FIRST stage where it dies (T4).

The pipeline is a chain; this walks it in order and reports the first failure:

    1 raw detection    - BallDetector: does anything pass its filters?
    2 track admission  - BallTracker: does it hold a REAL (non-predicted) ball?
    3 candidate        - ActionClassifier: a trajectory inflection exists?
    4 candidate gate   - a player within reach / context confidence
    5 actor / team     - attribution
    6 gesture/context  - the emitted label
    7 survives correct

Evidence comes from the off-by-default diag dump (src/utils/diagnostics.py);
the GT/prediction pairing is imported from scripts/evaluate_timed.py (T3) so
both agree on what "the same contact" means inside
``max(--tolerance-s, GT frame_tolerance / fps)``.

Unmatched predictions are classified by where they came from (duplicate /
dead-time / in-point spurious) plus the candidate that produced them.

Usage::

    python scripts/waterfall.py --diag output/t4/dev_diag.jsonl \
        --predictions output/video_ari_joan_8_first_points/pipeline_output.json \
        --ground-truth ground_truth/video_ari_joan_8_first_points_annotations.json \
        --json output/t4/dev_waterfall.json --markdown docs/t4_loss_waterfall_dev_clip.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# The repo root (for src.utils.diagnostics) plus this dir (for the T3
# evaluator, imported rather than reimplemented -- see the module docstring).
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

STAGE_DETECTION = "1_raw_detection"
STAGE_ADMISSION = "2_track_admission"
STAGE_CANDIDATE = "3_candidate"
STAGE_GATE = "4_candidate_gate"
STAGE_ATTRIBUTION = "5_actor_team"
STAGE_LABEL = "6_gesture_context_label"
STAGE_SURVIVED = "7_survives_correct"

STAGE_ORDER = [STAGE_DETECTION, STAGE_ADMISSION, STAGE_CANDIDATE, STAGE_GATE,
               STAGE_ATTRIBUTION, STAGE_LABEL, STAGE_SURVIVED]

#: "there was no contact here" reasons -> the contact died at stage 3.
NO_CANDIDATE_REASONS = (
    "pre_history", "min_contact_gap", "no_ball_sighting", "no_contact_geometry",
    "bridge_declined", "reentry_declined", "no_players_tracked",
)

#: gate reasons -> human text (stage 4).
GATE_REASON_TEXT = {
    "no_player_snapshot": "no player snapshot within NEIGH+2 frames of the contact",
    "reach": "ball-to-box distance above the reach gate",
    "low_departure": "post-contact ball departure below contact_min_departure_bw (bw/f)",
    "context_confidence": "resolved action below the action_confidence threshold",
    "action_filtered": "emitted action dropped by the process_frame filter",
}


def _records(frames: Dict[int, Dict[str, Any]], lo: int, hi: int) -> List[Dict[str, Any]]:
    return [frames[f] for f in range(lo, hi + 1) if f in frames]


def _has_detection(records: Sequence[Dict[str, Any]]) -> bool:
    return any(r.get("ball_dets") for r in records)


def _tracked(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in records
            if (r.get("ball_track") or {}).get("state") == "tracked"]


def _candidates(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Accepted contacts plus gate rejections (both mean a candidate existed)."""
    out = []
    for r in records:
        for c in r.get("candidates", []) or []:
            if c.get("stage") == "accepted" or c.get("reason") in GATE_REASON_TEXT:
                out.append(c)
    return out


def _probe_reasons(records: Sequence[Dict[str, Any]], lo: int, hi: int) -> str:
    """Most common 'why nothing happened' reason in the window.

    Contact-probe reasons (the classifier asked and found no contact) explain
    stage 3 directly, so they outrank the tracker state, which is only the
    fallback explanation when no probe was recorded.
    """
    probes: Counter = Counter()
    states: Counter = Counter()
    for r in records:
        bt = r.get("ball_track") or {}
        if bt.get("reason"):
            states[str(bt["reason"])] += 1
        for c in r.get("candidates", []) or []:
            if c.get("stage") != "accepted" and c.get("reason") in NO_CANDIDATE_REASONS:
                probes[str(c["reason"])] += 1
    counts = probes or states
    if not counts:
        return f"no diagnostic records in the {hi - lo + 1}f window"
    reason, n = counts.most_common(1)[0]
    return f"{reason} x{n}/{hi - lo + 1}f"


def _detection_summary(records: Sequence[Dict[str, Any]]) -> str:
    if not _has_detection(records):
        return "no raw ball detection in the window"
    n = sum(len(r.get("ball_dets", [])) for r in records)
    confs = [float(d.get("conf", 0.0)) for r in records for d in r.get("ball_dets", [])]
    return f"{n} raw detections, max conf {max(confs):.2f}" if confs else f"{n} detections"


def classify_contact(gt_frame: int, gt_action: Optional[str], gt_team: Optional[str],
                     tol: int, frames: Dict[int, Dict[str, Any]],
                     matched_pred: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """First stage at which the GT contact dies. See the module docstring."""
    lo, hi = max(0, gt_frame - tol), gt_frame + tol
    records = _records(frames, lo, hi)
    out: Dict[str, Any] = {"gt_frame": gt_frame, "gt_action": gt_action,
                           "gt_team": gt_team, "window": [lo, hi],
                           "matched": matched_pred is not None}
    if not records:
        out.update(stage=STAGE_DETECTION, detail="no diagnostic records in the window")
        return out
    if not _has_detection(records):
        out.update(stage=STAGE_DETECTION, detail=_detection_summary(records))
        return out
    if not _tracked(records):
        out.update(stage=STAGE_ADMISSION,
                   detail=f"{_detection_summary(records)}; tracker {_probe_reasons(records, lo, hi)}")
        return out

    cands = _candidates(records)
    accepted = [c for c in cands if c.get("stage") == "accepted"]
    gated = [c for c in cands if c.get("stage") != "accepted"]
    if not accepted:
        if gated:
            best = min(gated, key=lambda c: abs((c.get("frame") or 0) - gt_frame))
            reason = best.get("reason")
            out.update(stage=STAGE_GATE, candidate_frame=best.get("frame"),
                       detail=GATE_REASON_TEXT.get(reason, reason or "unknown gate"))
            return out
        out.update(stage=STAGE_CANDIDATE,
                   detail="ball tracked, no contact candidate: " + _probe_reasons(records, lo, hi))
        return out

    cand = min(accepted, key=lambda c: abs((c.get("frame") or 0) - gt_frame))
    if matched_pred is None:
        out.update(stage=STAGE_CANDIDATE, candidate_frame=cand.get("frame"),
                   detail=(f"contact accepted at f{cand.get('frame')} "
                           f"({cand.get('kind')}, {cand.get('gesture')}) but never emitted"))
        return out

    raw = matched_pred.get("raw") or {}
    out.update(candidate_frame=cand.get("frame"), kind=cand.get("kind"),
               gesture=cand.get("gesture"),
               pred_action=raw.get("action") or raw.get("final_action"),
               pred_team=raw.get("team"), pred_track_id=cand.get("track_id"),
               pred_player_id=cand.get("player_id"),
               attribution_source=cand.get("attribution_source"),
               touch_number=cand.get("touch_number"),
               rally_id=cand.get("rally_id"), confidence=cand.get("confidence"))

    if gt_team and out["pred_team"] and out["pred_team"] != gt_team:
        out.update(stage=STAGE_ATTRIBUTION,
                   detail=(f"emitted team {out['pred_team']} vs GT {gt_team} "
                           f"(actor track {out['pred_track_id']}, attribution "
                           f"{out['attribution_source']}, touch {out['touch_number']})"))
        return out
    if gt_action and out["pred_action"] != gt_action:
        out.update(stage=STAGE_LABEL,
                   detail=(f"pred {out['pred_action']} (gesture {out['gesture']}, "
                           f"touch {out['touch_number']}, team {out['pred_team']}) "
                           f"vs GT {gt_action}"))
        return out
    out.update(stage=STAGE_SURVIVED,
               detail=(f"{out['pred_action']} @ f{out['candidate_frame']} "
                       f"(gesture {out['gesture']}, touch {out['touch_number']})"))
    return out


def classify_false_positive(pred: Dict[str, Any], frames: Dict[int, Dict[str, Any]],
                            duplicate_of: Optional[int] = None,
                            in_point: Optional[bool] = None) -> Dict[str, Any]:
    """Where an unmatched prediction came from, and which candidate made it."""
    raw = pred.get("raw") or {}
    frame = pred.get("frame")
    rec = frames.get(frame, {}) if frame is not None else {}
    cand = next((c for c in (rec.get("candidates") or [])
                 if c.get("stage") == "accepted"), None) or {}
    if duplicate_of is not None:
        source = "duplicate"
    elif in_point is False:
        source = "dead_time"
    else:
        source = "in_point_spurious"
    return {"pred_frame": frame, "pred_action": pred.get("action"), "source": source,
            "duplicate_of_gt_frame": duplicate_of,
            "candidate_kind": cand.get("kind"), "gesture": cand.get("gesture"),
            "team": raw.get("team"), "track_id": cand.get("track_id"),
            "touch_number": raw.get("touch_number"), "rally_id": raw.get("rally_id"),
            "confidence": raw.get("confidence")}


# --- orchestration ----------------------------------------------------------

#: Frames of slack around a GT point interval when deciding "inside a point".
POINT_SLACK_FRAMES = 30


def _in_point(frame: Optional[int], intervals, slack: int) -> Optional[bool]:
    if frame is None or not intervals:
        return None
    return any(a - slack <= frame <= b + slack for a, b in intervals)


def run_waterfall(diag_path: str, predictions_path: str, ground_truth_path: str,
                  tolerance_s: float = BASE_TOLERANCE_S) -> Dict[str, Any]:
    from src.utils.diagnostics import load_diag

    diag = load_diag(diag_path)
    frames = diag["frames"]
    gt = load_ground_truth(ground_truth_path)
    pred_blob, pred_used = load_predictions(predictions_path)
    pred_events = extract_events(pred_blob)
    timebase = resolve_timebase(gt["blob"], pred_blob)
    match = match_events(gt["events"], pred_events, timebase, tolerance_s)
    fps = timebase.fps or 30.0

    matched_by_gt_frame, matched_pred_frames = {}, set()
    for g, p, _d in match["pairs"]:
        matched_by_gt_frame[g["frame"]] = p
        matched_pred_frames.add(p["frame"])

    rows = []
    for g in sorted(gt["events"], key=lambda e: e["frame"]):
        raw = g.get("raw") or {}
        ftol = raw.get("frame_tolerance") or 0
        tol = max(1, int(round(max(tolerance_s, ftol / fps) * fps)))
        row = classify_contact(g["frame"], raw.get("action") or raw.get("final_action"),
                               raw.get("player_team") or raw.get("team"), tol, frames,
                               matched_pred=matched_by_gt_frame.get(g["frame"]))
        row.update(point=raw.get("point"), gt_player_id=raw.get("player_id"),
                   owner_track_id=raw.get("owner_track_id"),
                   owner_note=raw.get("owner_note"), tol_frames=tol)
        rows.append(row)

    # -- false positives ----------------------------------------------------
    intervals = point_intervals(gt["blob"])
    dup_of: Dict[int, int] = {}
    for d in match["duplicates"]:
        dup_of[d["pred_frame"]] = d["gt_frame"]
    fp_rows = []
    for p in pred_events:
        if p["frame"] in matched_pred_frames:
            continue
        fp_rows.append(classify_false_positive(
            p, frames, duplicate_of=dup_of.get(p["frame"]),
            in_point=_in_point(p["frame"], intervals, POINT_SLACK_FRAMES)))

    stage_counts = Counter(r["stage"] for r in rows)
    fp_counts = Counter(f["source"] for f in fp_rows)
    return {
        "diag": diag_path, "predictions": pred_used, "ground_truth": ground_truth_path,
        "time": {"source": timebase.source, "fps": round(fps, 4),
                 "tolerance_base_s": tolerance_s},
        "counts": {"gt_contacts": len(rows), "predictions": len(pred_events),
                   "matched": len(match["pairs"]), "duplicates": len(match["duplicates"]),
                   "unmatched_gt": len(match["unmatched_gt"]),
                   "unmatched_pred": len(match["unmatched_pred"])},
        "stage_counts": {s: stage_counts.get(s, 0) for s in STAGE_ORDER},
        "fp_summary": dict(fp_counts),
        "rows": rows, "false_positives": fp_rows,
    }


# --- rendering --------------------------------------------------------------

def _md_escape(text: Any) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def render_markdown(res: Dict[str, Any]) -> str:
    c = res["counts"]
    out = [
        "# T4 loss waterfall - dev clip `video_ari_joan_8_first_points.mp4`",
        "",
        "Generated by `scripts/waterfall.py` from the off-by-default diag dump",
        f"(`{res['diag']}`) and the pipeline output (`{res['predictions']}`),",
        f"against `{res['ground_truth']}`.",
        "",
        f"* GT contacts **{c['gt_contacts']}**, predictions **{c['predictions']}**, "
        f"matched **{c['matched']}**, duplicates **{c['duplicates']}**, "
        f"unmatched GT **{c['unmatched_gt']}**, unmatched predictions "
        f"**{c['unmatched_pred']}**.",
        f"* Matching tolerance: {res['time']['tolerance_base_s']} s base, maxed with each GT",
        f"  event's `frame_tolerance / fps` ({res['time']['fps']} fps, "
        f"time base `{res['time']['source']}`) - identical to `scripts/evaluate_timed.py`.",
        "",
        "## Stage counts (first stage where each GT contact dies)",
        "",
        "| stage | contacts |",
        "|-------|---------:|",
    ]
    for s in STAGE_ORDER:
        out.append(f"| {s} | {res['stage_counts'].get(s, 0)} |")
    out += [
        "",
        "## Per-contact rows",
        "",
        "| point | gt frame | GT action | GT team | owner | stage | detail |",
        "|-------|---------:|-----------|---------|-------|-------|--------|",
    ]
    for r in res["rows"]:
        out.append(
            f"| {r.get('point')} | {r['gt_frame']} | {r['gt_action']} | {r['gt_team']} "
            f"| {r.get('owner_track_id')} | {r['stage']} | {_md_escape(r.get('detail'))} |")
    out += ["", "## False positives by source stage", ""]
    if not res["false_positives"]:
        out.append("No unmatched predictions.")
    else:
        out += ["| pred frame | action | source | candidate kind | gesture | team | touch | rally |",
                "|-----------:|--------|--------|---------------|---------|------|-------|-------|"]
        for f in res["false_positives"]:
            out.append(
                f"| {f['pred_frame']} | {f['pred_action']} | {f['source']} "
                f"| {f['candidate_kind']} | {f['gesture']} | {f['team']} "
                f"| {f['touch_number']} | {f['rally_id']} |")
        out += ["", "Source counts: " + ", ".join(
            f"**{k}** {v}" for k, v in sorted(res["fp_summary"].items()))]
    return "\n".join(out) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--diag", required=True, help="diag JSONL dump (--diag-dump)")
    p.add_argument("--predictions", required=True, help="pipeline_output.json")
    p.add_argument("--ground-truth", required=True, help="GT annotations JSON")
    p.add_argument("--tolerance-s", type=float, default=BASE_TOLERANCE_S)
    p.add_argument("--json", help="write the full result dict here")
    p.add_argument("--markdown", help="write the markdown table here")
    args = p.parse_args()

    res = run_waterfall(args.diag, args.predictions, args.ground_truth, args.tolerance_s)
    md = render_markdown(res)
    if args.markdown:
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(md)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(res, indent=2))
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
