#!/usr/bin/env python3
"""Entreno failure buckets: which mechanisms lose the 0.90 bar?

Diagnose-only probe. Classifies every GT action event of a drill as
found-correct / found-mislabeled / not-found against the REFERENCE action
stream (``scripts/test_action_recognition.py``'s ``<stem>_action_log.json``,
scored by ``scripts/evaluate.py --ignore-player``), matches at +-15 f with the
EXISTING matcher IMPORTED from ``scripts/probe_touch_rules.py`` (#68 semantics:
nearest-within-tolerance, non-exclusive) -- never re-implemented.

Evidence fields per mislabeled / not-found row come from the ``--diag-dump``
JSONL (``output/sr1/entreno_N_diag.jsonl``, a src.main run of the SAME
processors). Where the reference stream has no row inside tolerance, the
nearest accepted contact is looked up in that dump for its touch_number /
team / near_net / behind_baseline / kind; the dump is a DIFFERENT path, so the
helper states which source each column came from and never mixes them silently.

No cv2, no decode, no seek. Reads committed artifacts only.

Usage:
    venv/bin/python scripts/probe_entreno_buckets.py --drills 1 2 7
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

# The matcher, the GT loader and the clip F1 scorer are IMPORTED, never
# re-implemented (AGENTS.md section 6; CARD TC1 "read first").
import probe_touch_rules as pt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]

#: STATUS.md *Learnings* "Entreno gate record" -- the per-drill
#: ``evaluate --ignore-player`` action F1 of the reference path.
ENTRENO_BASELINE: Dict[int, float] = {1: 0.706, 2: 0.571, 3: 1.0, 4: 0.933,
                                       5: 0.923, 6: 0.933, 7: 0.75}

#: The drills under the 0.90 bar (the task's bucket set).
UNDER_BAR: Tuple[int, ...] = (1, 2, 7)

#: Frame-key adapter for the two stream shapes. ``pipeline_output.json`` writes
#: ``frame_number``; ``test_action_recognition.py``'s log writes ``frame``.
#: AGENTS.md: never edit the GT for this -- adapt the PREDICTION side.
def adapt_stream(actions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for a in actions:
        q = dict(a)
        q["frame"] = int(a.get("frame", a.get("frame_number")))
        out.append(q)
    return out


def load_reference_log(n: int, run_dir: Path) -> List[Dict[str, Any]]:
    """The record stream: ``test_action_recognition.py``'s action log."""
    path = run_dir / f"e{n}" / f"video_entreno_{n}_action_log.json"
    if not path.exists():
        raise SystemExit(f"missing reference log: {path} "
                         "(run scripts/test_action_recognition.py first)")
    return adapt_stream(json.loads(path.read_text(encoding="utf-8")))


def load_diag_rows(n: int) -> List[Dict[str, Any]]:
    """Accepted contacts of the ``--diag-dump`` JSONL (evidence only)."""
    path = REPO / f"output/sr1/entreno_{n}_diag.jsonl"
    if not path.exists():
        return []
    return pt.load_diag_accepted(str(path))


def load_diag_candidates(n: int) -> List[Dict[str, Any]]:
    """ALL ``candidates[]`` rows (every stage) of the diag dump.

    Data reader, not matching machinery: it reads the committed JSONL written
    by ``src/utils/diagnostics.py`` (header ``meta``, then one record per frame
    with ``frame`` and ``candidates``). Needed because ``pt.load_diag_accepted``
    returns accepted rows only, while the mechanism tag for a not-found event
    depends on WHY the contact was not emitted (reach gate / geometry /
    ball-sighting), which lives on the rejected / passed-gates rows.
    """
    path = REPO / f"output/sr1/entreno_{n}_diag.jsonl"
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    for line in lines[1:]:  # skip the meta header
        if not line.strip():
            continue
        rec = json.loads(line)
        for c in rec.get("candidates") or []:
            rows.append({**c, "frame": c.get("frame", rec.get("frame"))})
    return rows


def load_ball_track_frames(n: int) -> Dict[int, Optional[str]]:
    """Per-frame ball-track ``state`` of the diag dump.

    ``ball_track`` is non-None even when the track is LOST, so liveness must
    come from ``state``: ``tracked`` is a real sighting, ``predicted`` is a
    dead-reckoned coast with a decaying confidence (no detection), ``none`` is
    no track at all. Counting ``is not None`` as "tracked" would have hidden
    the very loss it must expose (it did once -- fixed here).
    """
    path = REPO / f"output/sr1/entreno_{n}_diag.jsonl"
    if not path.exists():
        return {}
    out: Dict[int, Optional[str]] = {}
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    for line in lines[1:]:
        if not line.strip():
            continue
        rec = json.loads(line)
        bt = rec.get("ball_track")
        out[int(rec["frame"])] = str(bt.get("state")) if bt else None
    return out


def window_census(candidates: Sequence[Dict[str, Any]],
                  track: Dict[int, Optional[str]], frame: int,
                  w: int = pt.TOLERANCE_F) -> Dict[str, Any]:
    """Why a contact was (not) emitted in the +-w window around ``frame``."""
    lo, hi = frame - w, frame + w
    rows = [c for c in candidates if c.get("frame") is not None
            and lo <= int(c["frame"]) <= hi]
    reasons = Counter(str(c.get("reason")) for c in rows
                      if c.get("stage") == "rejected" and c.get("reason"))
    found = [c for c in rows if c.get("stage") == "candidate_found"]
    passed = [c for c in rows if c.get("stage") == "candidate_passed_gates"]
    accepted = [c for c in rows if c.get("stage") == "accepted"]
    reach = [c for c in rows if c.get("stage") == "rejected"
             and c.get("reason") == "reach"]
    states = Counter(track.get(f) or "no_record" for f in range(lo, hi + 1))
    window_frames = sum(1 for f in range(lo, hi + 1) if f in track)
    # Only a real ``tracked`` state is a sighting; ``predicted`` is a coast on
    # a dead track and ``none`` is no track (AGENTS.md: BallTracker returns
    # None when lost -- never hallucinates).
    sighted = states.get("tracked", 0)
    return {
        "window": [lo, hi],
        "reasons": dict(reasons),
        "candidate_found_n": len(found),
        "passed_gates_n": len(passed),
        "passed_gates_rows": [
            {"frame": c.get("frame"), "behind_baseline": c.get("behind_baseline"),
             "near_net": c.get("near_net"), "team": c.get("team"),
             "kind": c.get("kind"), "target_team": c.get("target_team"),
             "contact_point": c.get("contact_point")}
            for c in passed],
        "accepted_n": len(accepted),
        "reach_rejects_n": len(reach),
        "reach_rows": [{"frame": c.get("frame"), "distance": c.get("distance"),
                        "reach": c.get("reach"), "target_team": c.get("target_team")}
                       for c in reach],
        "ball_track_states": dict(states),
        "ball_sighted_frames": sighted,
        "ball_track_window_frames": window_frames,
        "ball_sighted_ratio": (round(sighted / window_frames, 2)
                               if window_frames else None),
    }


def gt_no_touch_block(event: Dict[str, Any]) -> bool:
    """GT signature of a no-touch block: the owner-anchored convention that a
    no-touch block is a physical event the pipeline legitimately cannot emit
    (``ground_truth/README.md``; e6 f314 / e7 f300 precedent)."""
    return (event.get("final_action") == "block"
            and event.get("player_id") is None
            and bool(event.get("preceded_by_attack")))


# ----------------------------------------------------------------------
# the bucket classifier
# ----------------------------------------------------------------------

CLASS_FOUND_CORRECT = "found_correct"
CLASS_MISLABELED = "found_mislabeled"
CLASS_NOT_FOUND = "not_found"


def classify_drills(n: int, events: Sequence[Dict[str, Any]],
                    stream: Sequence[Dict[str, Any]],
                    accepted: Sequence[Dict[str, Any]],
                    candidates: Sequence[Dict[str, Any]] = (),
                    track: Optional[Dict[int, Optional[str]]] = None,
                    tolerance_f: int = pt.TOLERANCE_F) -> Dict[str, Any]:
    """Every GT event -> found-correct / found-mislabeled / not-found.

    Matching is the IMPORTED ``pt.match_contacts`` (nearest-within-tolerance,
    non-exclusive, #68 semantics) applied to (GT events, reference actions).
    A row is found-correct when the matched action's class equals the GT
    ``final_action``, found-mislabeled when the class differs, not-found when
    no action lies within tolerance.

    The FP side (actions matching no GT event) uses the same nearest-within-
    tolerance relation: an action is a FP when the nearest GT event is outside
    tolerance OR its class differs from that event's -- the mirror of the
    ``evaluate.py`` accounting, whose per-class tp+fp must equal the number of
    predictions of that class.
    """
    pairs, stats = pt.match_contacts(events, stream, tolerance_f)
    rows: List[Dict[str, Any]] = []
    used_stream: set = set()

    for e, a in pairs:
        gt_frame, gt_act = int(e["frame"]), str(e["final_action"])
        tn = e.get("touch_number")
        if a is None:
            near, near_d = _nearest(stream, gt_frame)
            ev = _evidence(accepted, gt_frame, tolerance_f)
            rows.append({
                "gt_frame": gt_frame, "gt_action": gt_act, "gt_touch": tn,
                "gt_team": e.get("player_team"),
                "bucket": "not_found",
                # NOTHING was emitted within tolerance; the nearest emission is
                # kept in its own fields (never overloaded onto pred_*).
                "pred_frame": None, "pred_action": None,
                "nearest_frame": int(near["frame"]) if near else None,
                "nearest_action": str(near["action"]) if near else None,
                "nearest_offset_f": near_d,
                "pred_touch": None, "pred_team": None, "gesture": None,
                "gt_player_id": e.get("player_id"),
                "gt_note": _gt_note(e),
                "gt_non_emittable": gt_no_touch_block(e),
                "gate": window_census(candidates, track or {}, gt_frame, tolerance_f),
                "evidence": ev,
            })
            continue
        used_stream.add(id(a))
        pred_act = str(a["action"])
        ok = pred_act == gt_act
        rows.append({
            "gt_frame": gt_frame, "gt_action": gt_act, "gt_touch": tn,
            "gt_team": e.get("player_team"),
            "bucket": "found_correct" if ok else "found_mislabeled",
            "pred_frame": int(a["frame"]), "pred_action": pred_act,
            "pred_offset_f": int(a["frame"]) - gt_frame,
            "pred_touch": a.get("touch_number"),
            "pred_team": a.get("team"),
            "pred_player_id": a.get("player_id"),
            "gesture": a.get("gesture"),
            "gt_player_id": e.get("player_id"),
            "gt_note": _gt_note(e),
            "gt_non_emittable": gt_no_touch_block(e),
            "gate": window_census(candidates, track or {}, gt_frame, tolerance_f),
            "evidence": _evidence(accepted, int(a["frame"]), tolerance_f),
        })

    # --- FP side: reference actions that earned no correct-class TP -----------
    fp_rows: List[Dict[str, Any]] = []
    for a in stream:
        near, near_d = _nearest(events, int(a["frame"]))
        matched_correct = any(r["pred_frame"] == int(a["frame"])
                              and r["bucket"] == "found_correct" for r in rows)
        if matched_correct:
            continue
        fp_rows.append({
            "pred_frame": int(a["frame"]), "pred_action": str(a["action"]),
            "pred_touch": a.get("touch_number"), "pred_team": a.get("team"),
            "gesture": a.get("gesture"),
            "nearest_gt_frame": int(near["frame"]) if near else None,
            "nearest_gt_action": str(near["final_action"]) if near else None,
            "nearest_offset_f": near_d,
            "class_matches_nearest": bool(
                near is not None and str(near["final_action"]) == str(a["action"])),
            "gate": window_census(candidates, track or {}, int(a["frame"]),
                                  tolerance_f),
            "evidence": _evidence(accepted, int(a["frame"]), tolerance_f),
        })

    counts = Counter(r["bucket"] for r in rows)
    gt_classes = Counter(str(e["final_action"]) for e in events)
    fp_classes = Counter(r["pred_action"] for r in fp_rows)

    # The reconcile invariant: for every predicted class, the reference stream's
    # count must equal correct + FP for that class. This is exactly what
    # evaluate.py's per-action tp+fp==total_pred means, so a violation would
    # mean the two accountings disagree.
    correct_by_class = Counter(r["pred_action"] for r in rows
                               if r["bucket"] == "found_correct")
    reconcile = {c: {"correct": correct_by_class.get(c, 0),
                     "fp": fp_classes.get(c, 0),
                     "predicted": sum(1 for a in stream if str(a["action"]) == c)}
                 for c in sorted(set(gt_classes) | set(str(a["action"]) for a in stream))}

    return {
        "drill": n,
        "gt_events": len(events),
        "predicted_actions": len(stream),
        "matcher_stats": stats,
        "counts": {k: counts.get(k, 0) for k in
                   ("found_correct", "found_mislabeled", "not_found")},
        "gt_classes": dict(sorted(gt_classes.items())),
        "fp_actions": len(fp_rows),
        "fp_classes": dict(sorted(fp_classes.items())),
        "rows": rows,
        "fp_rows": fp_rows,
        "reconcile": reconcile,
        "accepted_evidence_n": len(accepted),
    }


def _nearest(items: Sequence[Dict[str, Any]], frame: int
             ) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
    best: Optional[Tuple[int, Dict[str, Any]]] = None
    for it in items:
        d = abs(int(it["frame"]) - frame)
        if best is None or d < best[0]:
            best = (d, it)
    if best is None:
        return None, None
    return best[1], best[0]


def _evidence(accepted: Sequence[Dict[str, Any]], frame: int,
              tolerance_f: int) -> Dict[str, Any]:
    """Dump evidence for the contact nearest ``frame``.

    The dump's accepted rows carry NO ``behind_baseline`` (the key is absent on
    accepted rows -- it only appears on rejected ones), so that column is
    reported as ``None`` rather than inferred, and ball staleness is reported
    as the contact's ``kind`` (the classifier's own staleness bucket) rather
    than a number the artifact does not carry.
    """
    c, d = _nearest(accepted, frame)
    if c is None:
        return {"source": None}
    return {
        "source": "diag_dump",
        "dump_frame": int(c["frame"]),
        "dump_offset_f": int(c["frame"]) - frame,
        "dump_action": c.get("action"),
        "touch_number": c.get("touch_number"),
        "team": c.get("team"),
        "team_in_possession": c.get("team_in_possession"),
        "rally_id": c.get("rally_id"),
        "near_net": c.get("near_net"),
        "behind_baseline": None,
        "kind_staleness": c.get("kind") or c.get("contact_kind"),
        "attribution_source": c.get("attribution_source"),
        "ball_side": c.get("ball_side"),
        "within_tolerance": d <= tolerance_f,
    }


# ----------------------------------------------------------------------
# mechanism tagging (STATUS #74a/#74b's four known match-side mechanisms)
# ----------------------------------------------------------------------

#: The four KNOWN match-side mechanisms, verbatim from the task brief /
#: STATUS #74a/#74b, with the canonical STATUS bucket names they cover.
KNOWN_MECHANISMS = {
    "count_error": "possession-count error (STATUS under_counted / over_counted "
                   "-- _decide keys the bump_set label on `touch` alone)",
    "landing_artefact": "behind_baseline landing artefact (the SERVE branch needs "
                        "behind_baseline AND rally_start)",
    "rally_start": "rally_start cascade (the possession wrap that would reset "
                   "the count)",
    "attribution_swap": "attribution swap (wrong toucher / wrong side; on the "
                        "match this is far-side contacts never emitted)",
}

#: Tag bucket for events the GT itself declares un-emittable: the owner-anchored
#: no-touch-block convention (ground_truth/README.md; e6 f314 / e7 f300).
CEILING_TAG = "ceiling:gt_non_emittable"

#: Tag bucket for the one not-found event whose contact the src.main dump DOES
#: accept, i.e. it is only absent from the record stream.
DIVERGENCE_TAG = "ceiling:path_divergence"


def _gt_note(event: Dict[str, Any]) -> Optional[str]:
    """The owner's own note on a GT event, if any (from ``overrides.note``)."""
    note = (event.get("overrides") or {}).get("note")
    return str(note) if note else None


def tag_mechanism(row: Dict[str, Any]) -> Tuple[str, str]:
    """Tag one FAILING row (mislabeled or not-found) with a mechanism.

    Returns ``(tag, evidence)``. Precedence is fixed so the partition is total
    and deterministic -- it is NOT a tuning knob:

    found_mislabeled (the contact WAS emitted; only the label is wrong)
      1. ``count_error`` -- the emitted touch number differs from the GT's, or
         the GT is a touch-1 set that came in on a ``bump_set`` gesture. The
         resolver (``ActionContextResolver._decide``,
         ``src/recognition/action_context.py:175-219``) keys dig/set/spike/
         serve/overpass on ``touch`` ALONE for ``bump_set``, so a wrong count
         IS a label error. Matches STATUS #74b.
      2. ``new:gesture_miss`` -- count and team are RIGHT and only the class is
         wrong: the Layer-1 gesture decided ``bump_set`` where the GT action
         needs another gesture. (e1 f206 set read bump_set; e7 f243 set read
         block.) NOT a match mechanism: on the match this shows up as a count
         error, here the count was already correct.
      3. ``new:emitted_vocabulary`` -- the GT class is not in
         ``VolleyballAction`` at all (e1 f114 ``freeball``), so the label
         layer cannot express it at any count. Matches STATUS open point 9
         (the #50 diagnosis) but is a VOCABULARY ceiling, not a count error.

    not_found (nothing was emitted)
      4. ``ceiling:gt_non_emittable`` -- the GT declares the event a physical
         event the pipeline cannot emit (owner no-touch-block convention).
      5. ``ceiling:path_divergence`` -- the contact IS accepted in the
         src.main dump but absent from the record stream (the known e2
         f167 gesture-flip divergence; do not chase).
      6. ``new:contact_gate`` -- the contact was never accepted: the window
         census shows the gate that stopped it (reach / no_contact_geometry /
         no_ball_sighting) and whether the ball was even tracked. This is
         the UPSTREAM layer (STATUS open points 2/5: emit the missing
         contacts), named for its reachable events.
      7. ``landing_artefact`` -- a GT serve that was emitted as something else,
         or never emitted, where the candidate's ``behind_baseline`` was True
         and only ``rally_start`` failed (the SERVE branch's two conditions).
      8. ``new:no_emission`` -- nothing emitted within tolerance and none of
         the signatures above apply (offset reported).
    """
    gt_touch = row.get("gt_touch")
    gate = row.get("gate") or {}

    if row["bucket"] == CLASS_MISLABELED:
        pred_touch = row.get("pred_touch")
        touch_wrong = (pred_touch is not None and gt_touch is not None
                       and int(pred_touch) != int(gt_touch))
        team_wrong = (row.get("pred_team") and row.get("gt_team")
                      and str(row["pred_team"]) != str(row["gt_team"]))
        who = f"f{row['gt_frame']} {row['gt_action']}(tn={gt_touch}," \
              f"{row.get('gt_team')}) -> {row['pred_action']}@" \
              f"f{row['pred_frame']}(tn={row.get('pred_touch')}," \
              f"{row.get('pred_team')}, gesture={row.get('gesture')})"
        if touch_wrong:
            return ("count_error",
                    f"{who}; the emitted count differs so _decide's count-keyed "
                    f"branch chose the wrong class")
        if row.get("gt_action") not in _EMITTED_VOCABULARY:
            return ("new:emitted_vocabulary",
                    f"{who}; GT class '{row['gt_action']}' is not a member of "
                    f"VolleyballAction, so no count/gesture could emit it")
        if row.get("gt_action") == "serve":
            bb = _passed_gates_behind_baseline(row)
            return ("landing_artefact",
                    f"{who}; the SERVE branch of _decide needs behind_baseline "
                    f"AND rally_start, and behind_baseline was {bb} on the "
                    f"passed-gates row, so the serve label is unreachable here "
                    f"(same gate as the match's behind_baseline artefact, "
                    f"INVERTED polarity: on the match the flag is spuriously "
                    f"True at landings, here it is False at a real serve)")
        if team_wrong:
            return ("attribution_swap",
                    f"{who}; same count, wrong team attributed")
        return ("new:gesture_miss",
                f"{who}; count and team are correct and only the class is "
                f"wrong -- the Layer-1 gesture read "
                f"'{row.get('gesture')}' where the GT action needs another "
                f"gesture, and the resolver's {row.get('gesture')} branch "
                f"cannot express it at count {gt_touch}")

    # ---- not_found -----------------------------------------------------
    off = row.get("nearest_offset_f")
    near_desc = (f"nearest action {row.get('nearest_action')} at f"
                 f"{row.get('nearest_frame')} ({off:+d} f)"
                 if off is not None else "no emission anywhere in the clip")
    gate = row.get("gate") or {}
    reasons = gate.get("reasons") or {}
    ratio = gate.get("ball_sighted_ratio")
    states = gate.get("ball_track_states") or {}
    reached = (gate.get("candidate_found_n", 0) > 0
               or gate.get("reach_rejects_n", 0) > 0)
    win = gate.get("window") or [row["gt_frame"], row["gt_frame"]]
    lost = states.get("none", 0) + states.get("predicted", 0)

    if row.get("gt_non_emittable"):
        return (CEILING_TAG,
                f"GT f{row['gt_frame']} {row['gt_action']} is an owner-anchored "
                f"no-touch event (player_id null): '{row.get('gt_note')}' "
                f"-- un-emittable by construction, not a pipeline loss")

    if gate.get("accepted_n"):
        return (DIVERGENCE_TAG,
                f"GT f{row['gt_frame']} {row['gt_action']}(tn={gt_touch}) has no "
                f"emission in the record stream, but the src.main dump ACCEPTS a "
                f"contact in f{win[0]}-{win[1]} "
                f"({near_desc}) -- the known path divergence, not counted")

    # The SERVE branch of _decide needs behind_baseline AND rally_start. A GT
    # serve that was EMITTED as something else is therefore a serve-branch miss:
    # which of the two conditions failed is measured, not assumed.
    bb = _passed_gates_behind_baseline(row)
    if row.get("gt_action") == "serve":
        detail = ("behind_baseline was True on the passed-gates row, so the "
                  "rally_start condition is the one that failed"
                  if bb is True else
                  f"behind_baseline was {bb} on the passed-gates row, so the "
                  f"SERVE branch of _decide could not fire (it needs "
                  f"behind_baseline AND rally_start)")
        return ("landing_artefact",
                f"GT serve f{row['gt_frame']} emitted as "
                f"{row.get('pred_action')} at f{row.get('pred_frame')} "
                f"(count {gt_touch}, gesture {row.get('gesture')}); {detail}")

    if reached:
        detail = (f"reach gate at "
                  f"{gate['reach_rows']}" if gate.get("reach_rejects_n")
                  else f"geometry fired ({gate.get('candidate_found_n')} "
                       f"candidate_found) but no contact passed")
        return ("new:contact_gate",
                f"GT f{row['gt_frame']} {row['gt_action']}(tn={gt_touch}, "
                f"player {row.get('gt_player_id')}) never emitted; "
                f"window f{win[0]}-{win[1]}: "
                f"{detail}; rejections {reasons}; ball sighted "
                f"{gate.get('ball_sighted_frames')}/"
                f"{gate.get('ball_track_window_frames')} frames"
                + (f" ({ratio})" if ratio is not None else "")
                + (f"; GT note: {row['gt_note']}" if row.get("gt_note") else ""))

    if lost:
        dominant = (max(reasons.items(), key=lambda kv: kv[1])[0]
                    if reasons else "none")
        return ("new:contact_gate",
                f"GT f{row['gt_frame']} {row['gt_action']}(tn={gt_touch}, "
                f"player {row.get('gt_player_id')}) never emitted; "
                f"window f{win[0]}-{win[1]}: no gate fired, dominant rejection "
                f"'{dominant}' ({reasons or 'none'}); ball sight "
                f"{gate.get('ball_sighted_frames')}/"
                f"{gate.get('ball_track_window_frames')} frames"
                f"{lost}/{gate.get('ball_track_window_frames')} frames "
                f"(track states {states})"
                + (f"; GT note: {row['gt_note']}" if row.get("gt_note") else ""))

    return ("new:contact_gate",
            f"GT f{row['gt_frame']} {row['gt_action']}(tn={gt_touch}, "
            f"player {row.get('gt_player_id')}) never emitted; "
            f"window f{win[0]}-{win[1]}: no gate fired and no candidate was "
            f"even proposed, dominant rejection "
            f"'{(max(reasons.items(), key=lambda kv: kv[1])[0] if reasons else 'none')}'"
            f" ({reasons or 'none'}); ball sighted "
            f"{gate.get('ball_sighted_frames')}/"
            f"{gate.get('ball_track_window_frames')} frames "
            f"(states {states})"
            + (f"; GT note: {row['gt_note']}" if row.get("gt_note") else ""))

    return ("new:no_emission",
            f"GT f{row['gt_frame']} {row['gt_action']}(tn={gt_touch}) not "
            f"emitted; {near_desc}; window rejections {reasons or 'none'} "
            f"without a gate signature")


def _passed_gates_behind_baseline(row: Dict[str, Any]) -> Optional[bool]:
    """``behind_baseline`` on the contact this row matched, if the artifact
    records it. Present on ``candidate_passed_gates`` rows, ABSENT on accepted
    rows -- so ``None`` means "not recorded", never "False by inference"."""
    gate = row.get("gate") or {}
    rows = gate.get("passed_gates_rows") or []
    if not rows:
        return None
    return rows[0].get("behind_baseline")


#: The classes ``VolleyballAction`` can emit (src/recognition/volleyball_actions.py).
_EMITTED_VOCABULARY = {"dig", "set", "spike", "block", "ace", "serve",
                       "overpass", "unknown"}


def mechanism_split(res: Dict[str, Any]) -> Dict[str, Any]:
    """Tag every failing row and summarise known-vs-new, with the ceiling
    events (GT-un-emittable + path divergence) held out of the reachable
    denominator because no perception change can recover them."""
    tagged = []
    for r in res["rows"]:
        if r["bucket"] == CLASS_FOUND_CORRECT:
            continue
        tag, why = tag_mechanism(r)
        tagged.append({**r, "mechanism": tag, "mechanism_evidence": why})

    known = [t for t in tagged if t["mechanism"] in KNOWN_MECHANISMS]
    new = [t for t in tagged if t["mechanism"].startswith("new:")]
    ceiling = [t for t in tagged if t["mechanism"].startswith("ceiling:")]
    reachable = len(known) + len(new)
    return {
        "tagged": tagged,
        "n_failing_events": len(tagged),
        "known_n": len(known),
        "new_n": len(new),
        "ceiling_n": len(ceiling),
        "known_pct": round(100.0 * len(known) / reachable, 1) if reachable else None,
        "new_pct": round(100.0 * len(new) / reachable, 1) if reachable else None,
        "known_pct_of_all": round(100.0 * len(known) / len(tagged), 1) if tagged else None,
        "new_pct_of_all": round(100.0 * len(new) / len(tagged), 1) if tagged else None,
        "by_mechanism": dict(sorted(Counter(t["mechanism"] for t in tagged).items())),
        "known_by_mechanism": dict(sorted(Counter(t["mechanism"] for t in known).items())),
        "new_by_mechanism": dict(sorted(Counter(t["mechanism"] for t in new).items())),
    }


# ----------------------------------------------------------------------
# driver
# ----------------------------------------------------------------------

def analyse(n: int, run_dir: Path) -> Dict[str, Any]:
    events = pt.load_clip_events(
        f"ground_truth/video_entreno_{n}_annotations.json")
    stream = load_reference_log(n, run_dir)
    accepted = load_diag_rows(n)
    candidates = load_diag_candidates(n)
    track = load_ball_track_frames(n)
    res = classify_drills(n, events, stream, accepted, candidates, track)
    res["baseline_f1"] = ENTRENO_BASELINE[n]
    res["mechanisms"] = mechanism_split(res)
    return res


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--drills", type=int, nargs="+", default=list(UNDER_BAR))
    ap.add_argument("--run-dir", default="output/entreno_buckets")
    ap.add_argument("--out", default="output/entreno_buckets/buckets.json")
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    out = {}
    for n in args.drills:
        res = analyse(n, run_dir)
        out[f"e{n}"] = res
        m = res["mechanisms"]
        print(f"=== e{n}  baseline F1 {res['baseline_f1']}  "
              f"gt={res['gt_events']} pred={res['predicted_actions']}")
        print(f"    buckets: {res['counts']}   FP actions: {res['fp_actions']} {res['fp_classes']}")
        print(f"    reconcile: {json.dumps(res['reconcile'])}")
        print(f"    mechanisms: {m['by_mechanism']}  known {m['known_n']}/"
              f"{m['n_failing_events']} = {m['known_pct']}% of reachable "
              f"({m['new_n']} new, {m['ceiling_n']} ceiling)")
        for r in res["rows"]:
            off = r.get("pred_offset_f", r.get("nearest_offset_f"))
            emitted = (f"{r.get('pred_action')}@{r.get('pred_frame')}"
                       if r.get("pred_frame") is not None
                       else f"none within {pt.TOLERANCE_F} f "
                            f"(nearest {r.get('nearest_action')}"
                            f"@{r.get('nearest_frame')})")
            print(f"      f{r['gt_frame']:<5d} {r['gt_action']:<9s} tn={r['gt_touch']} "
                  f"{r['bucket']:<17s} {emitted:<42s} off={off} "
                  f"tn={r.get('pred_touch')} team={r.get('pred_team')}")
        for t in m["tagged"]:
            print(f"      TAG {t['mechanism']:<28s} f{t['gt_frame']:<5d} "
                  f"{t['gt_action']} -> {t['mechanism_evidence']}")
        for r in res["fp_rows"]:
            print(f"      FP  f{r['pred_frame']:<5d} {r['pred_action']:<9s} "
                  f"nearest GT f{r['nearest_gt_frame']} {r['nearest_gt_action']} "
                  f"off={r['nearest_offset_f']} class_match={r['class_matches_nearest']}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())