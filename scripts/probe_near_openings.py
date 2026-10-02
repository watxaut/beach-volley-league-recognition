#!/usr/bin/env python3
"""SR4a -- the near-opening table: what the pipeline emitted around every serve.

One question, four buckets, pre-registered in STATUS.md card SR4a: of the 8 match
near serve MISSES, how many are *repairable after the fact* (the contact was
emitted, under another label or inside another rally) and how many were *never
produced* (no action at all on the serve's own side).  That split decides
whether SR4 -- the post-hoc per-point serve record -- can be built without
touching ``src/``, and it reopens the parked tracking exemption (M-b) only on a
pre-registered count.

Nothing is decoded.  There is NO ``cv2`` import in this file, by design
(AGENTS.md section 9: this card reads artifacts, it never seeks a window).  The
inputs are the emitted ``actions``/``game_state`` keys of pipeline artifacts, the
owner contact GT, and the SR1c player-track diag dump (read line by line,
sequential, keyed on its ``frame`` field).

The scorer's names are IMPORTED from ``scripts/score_serves.py`` and the window
threshold is IMPORTED from ``scripts/relabel_serves.py`` as ``GAP_SERVE_MIN``
(143, never re-tuned, never redefined here): the gap rule that decides where a
point's window opens is SR's own, not this card's.

Usage::

    venv/bin/python scripts/probe_near_openings.py              # G1 + tables
    venv/bin/python scripts/probe_near_openings.py --json output/sr4a/table.json
    venv/bin/python scripts/probe_near_openings.py --g1-only     # gate only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import resolve_side_switches as rs  # noqa: E402  (path set above)
import score_serves as S  # noqa: E402  (path set above)

#: Reused AS IS from relabel_serves.py -- a window opener is the last action
#: before the GT frame whose own t1 gap reaches the dead-ball-gap chasm.  This
#: module never re-tunes it; the import IS the contract.
from relabel_serves import GAP_SERVE_MIN  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

MATCH_PIPELINE = "output/20260920_match_ari_joan_lost/pipeline_output.json"
MATCH_DIAG = "output/sr1c/match_full_diag.jsonl"
DRILLS = (2, 3, 4, 5, 6, 7)
DRILL_PIPELINE = "output/sr1d/base/entreno_{n}/pipeline_output.json"
DRILL_PIPELINE_ALT = "output/sr1/entreno_{n}/pipeline_output.json"

#: Card SR4a step 4: side-correct, inside the owner's own frame tolerance.
TOLERANCE = S.DEFAULT_TOLERANCE

#: Card SR4a step 7, pre-registered.
MISS_NEAR = 8
G2_SR4_THRESHOLD = 4       # emitted_mislabeled_opener + emitted_not_opener >= 4
G2_MB_THRESHOLD = 3       # not_emitted >= 3 ...
G2_MB_COASTING = 2        # ... and >= 2 of those with the server coasting

BUCKETS = ("hit", "emitted_mislabeled_opener", "emitted_not_opener", "not_emitted")


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------

def _read_json(rel: str) -> Dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _side_of_team(team: Optional[str]) -> Optional[str]:
    """Emitted ``team`` letter -> owner side word (A = near half)."""
    return rs.side_letter_to_court(team)


def sorted_actions(pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Emitted actions in frame order, with the fields this card records."""
    out = []
    for action in pipeline.get("actions") or []:
        frame = action.get("frame_number", action.get("frame"))
        if frame is None:
            continue
        out.append({
            "index": None,           # filled below, position in the frame-sorted list
            "frame_number": int(frame),
            "action": action.get("action"),
            "team": action.get("team"),
            "side": _side_of_team(action.get("team")),
            "touch_number": action.get("touch_number"),
            "rally_id": action.get("rally_id"),
            "track_id": (action.get("track_id") if action.get("track_id") is not None
                         else action.get("player_id")),
            "gap_prev": None,        # frames since the previous action of ANY kind
        })
    out.sort(key=lambda a: a["frame_number"])
    for i, action in enumerate(out):
        action["index"] = i
        action["gap_prev"] = (None if i == 0
                              else action["frame_number"] - out[i - 1]["frame_number"])
    return out


# ---------------------------------------------------------------------------
# the window (card step 3)
# ---------------------------------------------------------------------------

def window_for_serve_on_side(actions: Sequence[Dict[str, Any]], gt_frame: int,
                             own_side: Optional[str]) -> Optional[Tuple[int, int]]:
    """``(first_index, last_index)`` of the opening window around a GT serve.

    START: the last action before the GT frame whose gap to its own predecessor
    is >= GAP_SERVE_MIN -- SR's own window-opener rule, imported, never re-tuned
    here.  ``gap_prev is None`` (video start / anchored prefix) qualifies, which
    is exactly how ``relabel_serves.resolve_point`` reads it: it rejects an
    opener only when ``gap is not None and gap < GAP_SERVE_MIN``.  When NO action
    precedes the GT frame at all (a clip-opening serve) the window opens at the
    first action of the stream -- video start is the anchor prefix, and dropping
    the opening serve out of its own window would read every clip-opening serve
    as never emitted.  END: the first action after the GT frame on the OTHER
    team, so the window is "the opening exchange", not the whole rally; when the
    own side is unknown the end falls back to the first action after the GT frame
    on a known team, and when no other-team action exists the window is
    open-ended.
    """
    before = [a for a in actions if a["frame_number"] < gt_frame]
    start = None
    for action in before:
        if action["gap_prev"] is None or action["gap_prev"] >= GAP_SERVE_MIN:
            start = action["index"]
    if start is None and actions and actions[0]["frame_number"] >= gt_frame:
        # Nothing precedes the serve: the clip's first action IS its window.
        start = actions[0]["index"]
    if start is None:
        return None
    end = None
    for action in actions:
        if action["frame_number"] > gt_frame and action["frame_number"] >= 0:
            if own_side is None:
                if action["side"] is not None:
                    end = action["index"]
                    break
            elif action["side"] is not None and action["side"] != own_side:
                end = action["index"]
                break
    return (start, end)


def window_actions(actions: Sequence[Dict[str, Any]],
                   span: Optional[Tuple[int, int]]) -> List[Dict[str, Any]]:
    if span is None:
        return []
    start, end = span
    return [a for a in actions if start <= a["index"] and (end is None or a["index"] <= end)]


# ---------------------------------------------------------------------------
# buckets (card step 4)
# ---------------------------------------------------------------------------

def bucket_of(serve_frame: int, side: Optional[str], window: Sequence[Dict[str, Any]],
              tolerance: int = TOLERANCE) -> Tuple[str, List[Dict[str, Any]]]:
    """One of ``hit`` / ``emitted_mislabeled_opener`` / ``emitted_not_opener`` /
    ``not_emitted`` for ONE GT serve, plus the actions that decided it.

    * ``hit`` -- an emitted ``serve`` within +-tolerance f on the serve's own side.
    * ``emitted_mislabeled_opener`` -- no ``serve`` in tolerance, but an action on
      the serve's own side in tolerance that IS the window's first action.
    * ``emitted_not_opener`` -- an action on the serve's own side in tolerance that
      is NOT the window's first action (inside an earlier rally: the P5/P33 class).
    * ``not_emitted`` -- no action on the serve's own side in tolerance.
    """
    own = [a for a in window
           if a["side"] == side and abs(a["frame_number"] - serve_frame) <= tolerance]
    if any(a["action"] == "serve" for a in own):
        return "hit", own
    if not own:
        return "not_emitted", own
    first = window[0]["index"] if window else None
    if any(a["index"] == first for a in own):
        return "emitted_mislabeled_opener", own
    return "emitted_not_opener", own


def far_trap(serve_frame: int, window: Sequence[Dict[str, Any]],
             onsets: Sequence[Dict[str, Any]], tolerance: int = TOLERANCE) -> Dict[str, Any]:
    """``far_unseen_near_reception_first`` -- the trap guard, per FAR serve.

    A near-side action within +-tolerance f of the far serve AND no rally onset
    within +-tolerance f.  It is NOT a bucket of the near table: it says a far
    serve can be preceded by a near-side emission with no rally opening at all,
    so any near-opener rule must carry an onset-side guard.
    """
    near = [a for a in window if a["side"] == "near"
            and abs(a["frame_number"] - serve_frame) <= tolerance]
    onset_near = [o for o in onsets if abs(o["frame"] - serve_frame) <= tolerance]
    return {
        "near_actions": [a["frame_number"] for a in near],
        "onsets": [o["frame"] for o in onset_near],
        "flagged": bool(near) and not onset_near,
    }


def onset_offset(onsets: Sequence[Dict[str, Any]], gt_frame: int
                 ) -> Tuple[Optional[int], Optional[int]]:
    """``(offset, onset_frame)`` of the rally onset nearest a GT frame."""
    if not onsets:
        return (None, None)
    best = min(onsets, key=lambda o: (abs(o["frame"] - gt_frame), o["frame"]))
    return (best["frame"] - gt_frame, best["frame"])


def nearest_rally_id(actions: Sequence[Dict[str, Any]], gt_frame: int
                     ) -> Tuple[Optional[int], Optional[int]]:
    """``(rally_id, frame)`` of the action nearest a GT frame."""
    if not actions:
        return (None, None)
    best = min(actions, key=lambda a: (abs(a["frame_number"] - gt_frame),
                                       a["frame_number"] - gt_frame))
    return (best["rally_id"], best["frame_number"])


# ---------------------------------------------------------------------------
# the per-serve row
# ---------------------------------------------------------------------------

def serve_row(serve: Dict[str, Any], actions: Sequence[Dict[str, Any]],
              onsets: Sequence[Dict[str, Any]], tolerance: int = TOLERANCE
              ) -> Dict[str, Any]:
    """Everything the card asks for, for ONE GT serve."""
    span = window_for_serve_on_side(actions, serve["frame"], serve.get("side"))
    window = window_actions(actions, span)
    bucket, deciding = bucket_of(serve["frame"], serve.get("side"), window, tolerance)
    offset, onset = onset_offset(onsets, serve["frame"])
    rally_id, rally_frame = nearest_rally_id(actions, serve["frame"])
    row = {
        "point": serve.get("point"),
        "frame": serve["frame"],
        "side": serve.get("side"),
        "squad": serve.get("squad"),
        "split": serve.get("split"),
        "bucket": bucket,
        "window_start_frame": None if span is None else window[0]["frame_number"],
        "window_end_frame": None if not window else window[-1]["frame_number"],
        "window_n_actions": len(window),
        "deciding_frames": [a["frame_number"] for a in deciding],
        "onset_offset_f": offset,
        "onset_frame": onset,
        "nearest_action_rally_id": rally_id,
        "nearest_action_frame": rally_frame,
        "window": [
            {"frame_number": a["frame_number"], "action": a["action"],
             "team": a["team"], "side": a["side"], "touch_number": a["touch_number"],
             "rally_id": a["rally_id"], "track_id": a["track_id"],
             "gap_prev": a["gap_prev"],
             "d_gt": a["frame_number"] - serve["frame"]}
            for a in window
        ],
    }
    if serve.get("side") == "far":
        row["far_unseen_near_reception_first"] = far_trap(
            serve["frame"], window, onsets, tolerance)["flagged"]
    return row


# ---------------------------------------------------------------------------
# coasting read (card step 6)
# ---------------------------------------------------------------------------

def read_coasting(frames: Dict[int, Dict[str, Any]], rows: Sequence[Dict[str, Any]]
                  ) -> List[Dict[str, Any]]:
    """For each match near MISS at its GT frame, the lowest-foot same-team track.

    "Lowest foot" = the player nearest the camera on that side, which is where a
    server waiting behind their own line stands.  The reading is reported per
    serve with the frame's full ``predicted`` list so it can be re-cut without a
    re-run.  A GT frame with no line in the dump is reported as ``diag_absent``
    and is NOT counted as coasting.
    """
    out = []
    for row in rows:
        if row["side"] != "near" or row["bucket"] == "hit":
            continue
        line = frames.get(row["frame"])
        if line is None:
            out.append({"frame": row["frame"], "point": row["point"],
                        "bucket": row["bucket"], "diag": "diag_absent",
                        "predicted": None, "players": None})
            continue
        same_side = [p for p in (line.get("players") or [])
                     if p.get("team") == row["_own_team_letter"]]
        if not same_side:
            out.append({"frame": row["frame"], "point": row["point"],
                        "bucket": row["bucket"], "diag": "no_same_team_player",
                        "predicted": None, "players": None})
            continue
        lowest = max(same_side, key=lambda p: (p.get("bbox") or [0, 0, 0, 0])[3])
        out.append({
            "frame": row["frame"], "point": row["point"], "bucket": row["bucket"],
            "diag": "ok",
            "track_id": lowest.get("track_id"),
            "team": lowest.get("team"),
            "foot_y": (lowest.get("bbox") or [None] * 4)[3],
            "predicted": lowest.get("predicted"),
            "confidence": lowest.get("confidence"),
            "n_same_team": len(same_side),
            "players": [{"track_id": p.get("track_id"), "team": p.get("team"),
                         "foot_y": (p.get("bbox") or [None] * 4)[3],
                         "predicted": p.get("predicted")}
                        for p in (line.get("players") or [])],
        })
    return out


def load_diag_frames(path_rel: str, wanted: Iterable[int]
                     ) -> Tuple[Dict[int, Dict[str, Any]], int]:
    """Sequential single pass over the diag dump; keep only the wanted frames."""
    wanted_set = {int(f) for f in wanted}
    out: Dict[int, Dict[str, Any]] = {}
    total = 0
    for line in (REPO / path_rel).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        total += 1
        if '"players"' not in line:
            continue
        blob = json.loads(line)
        frame = blob.get("frame")
        if frame is None or int(frame) not in wanted_set:
            continue
        out.setdefault(int(frame), blob)
    return out, total


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------

def match_serves() -> List[Dict[str, Any]]:
    gt = _read_json("ground_truth/20260920_match_contacts.json")
    return S.serve_rows_from_contact_gt(gt, S.match_split)


def drill_gt(n: int) -> Dict[str, Any]:
    return _read_json(f"ground_truth/video_entreno_{n}_annotations.json")


def drill_pipeline(n: int) -> Tuple[Dict[str, Any], str]:
    """The ACTIONS come from the sr1d BASE arm, explicitly (never sr1's path)."""
    rel = DRILL_PIPELINE.format(n=n)
    return _read_json(rel), rel


def drill_files_agree(n: int) -> Optional[Dict[str, Any]]:
    """#61 measured the two drill action files identical; verify, do not assume."""
    base, base_rel = drill_pipeline(n)
    alt_rel = DRILL_PIPELINE_ALT.format(n=n)
    alt_path = REPO / alt_rel
    if not alt_path.exists():
        return {"n": n, "alt_present": False, "identical": None}
    alt = _read_json(alt_rel)
    key = lambda blob: [(a.get("frame_number"), a.get("action"), a.get("team"))
                        for a in blob.get("actions") or []]
    kb, ka = key(base), key(alt)
    return {"n": n, "alt_present": True, "identical": kb == ka,
            "base_n": len(kb), "alt_n": len(ka),
            "only_in_base": [k for k in kb if k not in ka],
            "only_in_alt": [k for k in ka if k not in kb],
            "base": base_rel, "alt": alt_rel}


def analyse(name: str, label: str, pipeline: Dict[str, Any],
            serves: Sequence[Dict[str, Any]], source: str) -> Dict[str, Any]:
    actions = sorted_actions(pipeline)
    onsets = S.game_on_candidates(pipeline)
    rows = [serve_row(serve, actions, onsets) for serve in serves]
    buckets: Dict[str, int] = {b: 0 for b in BUCKETS}
    for row in rows:
        buckets[row["bucket"]] = buckets.get(row["bucket"], 0) + 1
    return {
        "name": name, "label": label, "source": source,
        "n_serves": len(serves), "n_actions": len(actions), "n_onsets": len(onsets),
        "buckets": buckets,
        "rows": rows,
        "actions": actions,
        "onsets": onsets,
    }


# ---------------------------------------------------------------------------
# G1 (card step 5)
# ---------------------------------------------------------------------------

def g1(tables: Dict[str, Any]) -> Dict[str, Any]:
    """Reproduce the recorded baseline: near 8/16, far 0/17, 12 FP, drills 3/5.

    Two independent counts: the scorer's own cells (from the imported
    ``score_stream``) and this probe's bucket table.  Both must agree with the
    pre-registered numbers or nothing in the card's reading counts.
    """
    match = tables["match"]
    near_rows = [r for r in match["rows"] if r["side"] == "near"]
    far_rows = [r for r in match["rows"] if r["side"] == "far"]
    probe_near_hits = sum(1 for r in near_rows if r["bucket"] == "hit")
    probe_far_hits = sum(1 for r in far_rows if r["bucket"] == "hit")
    drill_hits = sum(tables[f"entreno_{n}"]["buckets"]["hit"] for n in DRILLS)
    drill_gt = sum(1 for n in DRILLS
                   for r in tables[f"entreno_{n}"]["rows"] if r["side"] == "near")

    # scorer side
    session = S.build_match_session()
    scored = S.score_session(session)
    prod = scored["streams"]["production"]
    near_cell = prod["by_side"].get("near") or {}
    far_cell = prod["by_side"].get("far") or {}
    observed = {
        "scorer_near": [near_cell.get("hits"), near_cell.get("gt_serves")],
        "scorer_far": [far_cell.get("hits"), far_cell.get("gt_serves")],
        "scorer_false_positives": (prod.get("overall") or {}).get("false_positives"),
        "probe_near": [probe_near_hits, len(near_rows)],
        "probe_far": [probe_far_hits, len(far_rows)],
        "probe_drills_near": [drill_hits, drill_gt],
    }
    checks = {
        "scorer_near": observed["scorer_near"] == [8, 16],
        "scorer_far": observed["scorer_far"] == [0, 17],
        "scorer_false_positives": observed["scorer_false_positives"] == 12,
        "probe_near": observed["probe_near"] == [8, 16],
        "probe_far": observed["probe_far"] == [0, 17],
        "probe_drills_near": observed["probe_drills_near"] == [3, 5],
    }
    return {"expected": {"near": "8/16", "far": "0/17", "false_positives": 12,
                         "drills_near": "3/5"},
            "observed": observed, "checks": checks, "pass": all(checks.values()),
            "source": "STATUS.md card SR4a step 5"}


# ---------------------------------------------------------------------------
# G2 (card step 7) -- descriptive, decides ORDER only
# ---------------------------------------------------------------------------

def g2(match_table: Dict[str, Any], coasting: Sequence[Dict[str, Any]]
       ) -> Dict[str, Any]:
    """The card's G2, over the NEAR MISSES ONLY.

    ``MISS_NEAR`` is the near-miss count (8, reproduced by G1).  Every count in
    the verdict is taken over those misses and NOT over the whole 33-serve
    table: ``not_emitted`` over the misses is the number the M-b rule reads, and
    the far table's own ``not_emitted`` rows are a different population that must
    not be pooled into it.  ``all_serves_buckets`` is carried alongside so the two
    scopes can never be confused when the numbers are read off the report.
    """
    misses = [r for r in match_table["rows"]
              if r["side"] == "near" and r["bucket"] != "hit"]
    b = {k: 0 for k in BUCKETS}
    for row in misses:
        b[row["bucket"]] += 1
    repairable = b["emitted_mislabeled_opener"] + b["emitted_not_opener"]
    never = b["not_emitted"]
    coasting_hits = sum(1 for c in coasting if c.get("predicted") is True)
    trap = sum(1 for r in match_table["rows"] if r.get("far_unseen_near_reception_first"))
    return {
        "miss_near": len(misses),
        "buckets_over_misses": b,
        "repairable": repairable,
        "sr4_near_proceeds_after_the_fact": repairable >= G2_SR4_THRESHOLD,
        "never_produced": never,
        "coasting_predicted_true": coasting_hits,
        "coasting_readable": sum(1 for c in coasting if c.get("diag") == "ok"),
        "coasting_not_emitted": sum(
            1 for c in coasting
            if c.get("diag") == "ok" and c.get("bucket") == "not_emitted"
            and c.get("predicted") is True),
        "mb_reopened": (never >= G2_MB_THRESHOLD
                        and coasting_hits >= G2_MB_COASTING),
        "far_unseen_near_reception_first": trap,
        "all_serves_buckets": match_table["buckets"],
        "rule": ("SR4 proceeds after the fact iff repairable >= 4 of the 8 near "
                 "misses; M-b reopens iff not_emitted >= 3 of those 8 AND >= 2 "
                 "of those not_emitted have the lowest-foot same-team track "
                 "predicted:true at the GT frame"),
    }


# ---------------------------------------------------------------------------
# false serves (card deliverables)
# ---------------------------------------------------------------------------

def false_serve_rows(scored: Dict[str, Any], table: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The 12 false emissions, each with its window neighbours.

    "Neighbours" = the emitted actions around it in frame order (the same sorted
    action list the window builder walks), so a reader can see whether the false
    serve opened a window, sat inside a rally, or is dead-time handling.
    """
    actions = table["actions"]
    out = []
    for row in scored["streams"]["production"]["false_positives"]:
        frame = row["frame"]
        pos = next((i for i, a in enumerate(actions)
                    if a["frame_number"] == frame), None)
        neighbours = []
        if pos is not None:
            for a in actions[max(0, pos - 3):pos + 4]:
                neighbours.append({"frame_number": a["frame_number"],
                                   "action": a["action"], "team": a["team"],
                                   "touch_number": a["touch_number"],
                                   "rally_id": a["rally_id"],
                                   "track_id": a["track_id"],
                                   "gap_prev": a["gap_prev"]})
        out.append({
            "frame": frame, "side": row.get("side"), "point": row.get("point"),
            "kind": row["kind"], "nearest_contact": row["nearest_contact"],
            "window_opener": None if pos is None else (
                actions[pos]["gap_prev"] is None
                or actions[pos]["gap_prev"] >= GAP_SERVE_MIN),
            "neighbours": neighbours,
        })
    return out


# ---------------------------------------------------------------------------
# build everything
# ---------------------------------------------------------------------------

def build() -> Dict[str, Any]:
    tables: Dict[str, Any] = {}

    pipeline = _read_json(MATCH_PIPELINE)
    tables["match"] = analyse("match", "20260920 match (production run)",
                              pipeline, match_serves(), MATCH_PIPELINE)

    agreement = []
    for n in DRILLS:
        drill, rel = drill_pipeline(n)
        rows = S.serve_rows_from_contact_gt(drill_gt(n), S.entreno_split,
                                            S.entreno_squad_to_side)
        tables[f"entreno_{n}"] = analyse(
            f"entreno_{n}", f"video_entreno_{n} (sr1d BASE arm)", drill, rows, rel)
        agreement.append(drill_files_agree(n))

    g = g1(tables)
    if not g["pass"]:
        return {"g1": g, "g1_failed": True}

    # G2 inputs.  The coasting read needs the emitted COURT-SIDE letter of the
    # near half, which is the constant the calibration itself uses (A = near).
    own_letter = S.COURT_TO_SIDE_LETTER["near"]
    for row in tables["match"]["rows"]:
        row["_own_team_letter"] = own_letter

    diag_frames, diag_lines = load_diag_frames(
        MATCH_DIAG, [r["frame"] for r in tables["match"]["rows"]])
    coasting = read_coasting(diag_frames, tables["match"]["rows"])
    for row in tables["match"]["rows"]:
        row.pop("_own_team_letter", None)

    session = S.build_match_session()
    scored = S.score_session(session)
    verdicts = g2(tables["match"], coasting)
    return {
        "gap_serve_min": GAP_SERVE_MIN,
        "tolerance_f": TOLERANCE,
        "g1": g,
        "g2": verdicts,
        "drill_action_files": agreement,
        "diag": {"path": MATCH_DIAG, "lines": diag_lines,
                 "frames_kept": len(diag_frames),
                 "arm": "NOT ESTABLISHED in any recorded log for this dump "
                        "(output/sr1c/match_full_run.log records only the run's "
                        "own parity_vs_reference); see docs/sr4a_near_openings.md"},
        "tables": tables,
        "coasting": coasting,
        "false_serves": false_serve_rows(scored, tables["match"]),
        "scored": {"gate": scored.get("gate")},
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def _window_line(entry: Dict[str, Any]) -> str:
    return (f"f{entry['frame_number']:<6} {entry['action']:<8} {entry['team'] or '?':<2}"
            f" t{str(entry['touch_number']):<3} R{str(entry['rally_id']):<3}"
            f" tr{str(entry['track_id']):<3} gap{str(entry['gap_prev']):<6}"
            f" d{entry['d_gt']:+d}")


def format_report(data: Dict[str, Any]) -> str:
    lines: List[str] = []
    g1d = data["g1"]
    lines.append("=" * 110)
    lines.append("  SR4a -- THE NEAR-OPENING TABLE (card SR4a; no decode, no src/ change)")
    lines.append("=" * 110)
    lines.append(f"  window rule: last action before the GT frame with gap_prev >= "
                 f"GAP_SERVE_MIN ({data['gap_serve_min']}, imported from "
                 f"relabel_serves) .. first action after it on the other team")
    lines.append(f"  tolerance: +-{data['tolerance_f']} f, side-correct")
    lines.append("")
    lines.append(f"  GATE G1 -- {'PASS' if g1d['pass'] else 'FAIL'}")
    lines.append(f"    expected {g1d['expected']}")
    lines.append(f"    observed {g1d['observed']}")
    lines.append(f"    checks   {g1d['checks']}")
    if g1d.get("pass") is not True:
        lines.append("    G1 FAILED -- every bucket below is VOID (card step 5)")
        return "\n".join(lines)

    for key in ("match",) + tuple(f"entreno_{n}" for n in DRILLS):
        table = data["tables"][key]
        lines.append("")
        lines.append("-" * 110)
        lines.append(f"  {table['label']}   GT serves {table['n_serves']}"
                     f"   emitted actions {table['n_actions']}"
                     f"   rally onsets {table['n_onsets']}")
        lines.append(f"    buckets {table['buckets']}")
        lines.append("    pt  frame  side  bucket                      onset  nearest-raid  window")
        for row in table["rows"]:
            lines.append(
                f"    {str(row['point'] or '-'):<4} f{row['frame']:<6} "
                f"{(row['side'] or '?'):<5} {row['bucket']:<27} "
                f"{str(row['onset_offset_f'] if row['onset_offset_f'] is not None else '-'):>5}  "
                f"{str(row['nearest_action_rally_id']):>7}          "
                f"f{row['window_start_frame']}..f{row['window_end_frame']}"
                f" ({row['window_n_actions']} actions)")
            for entry in row["window"]:
                lines.append("        " + _window_line(entry))
            if row.get("far_unseen_near_reception_first"):
                lines.append("        far_unseen_near_reception_first: TRAP FLAGGED")

    lines.append("")
    lines.append("=" * 110)
    lines.append("  COASTING READ (diag dump; lowest-foot same-team track at each near miss)")
    diag = data["diag"]
    lines.append(f"    {diag['path']}  lines {diag['lines']}  frames kept {diag['frames_kept']}")
    lines.append(f"    arm: {diag['arm']}")
    for entry in data["coasting"]:
        lines.append(f"    P{str(entry['point']):<4} f{entry['frame']:<6} "
                     f"{entry['bucket']:<27} diag={entry['diag']}")
        if entry["diag"] == "ok":
            lines.append(f"      lowest-foot same-team track {entry['track_id']} "
                         f"team {entry['team']} foot_y {entry['foot_y']:.1f} "
                         f"predicted {entry['predicted']} "
                         f"conf {entry['confidence']}  "
                         f"(same-team players {entry['n_same_team']})")
            lines.append("      frame players: " + ", ".join(
                f"tr{p['track_id']}/{p['team'] or '?'}/foot"
                f"{(p['foot_y'] if p['foot_y'] is not None else float('nan')):.0f}"
                f"/pred{p['predicted']}" for p in entry["players"]))
        else:
            lines.append("      players: n/a")

    lines.append("")
    lines.append("=" * 110)
    lines.append("  FALSE SERVES (the scorer's unmatched emissions) + window neighbours")
    for row in data["false_serves"]:
        near = row["nearest_contact"]
        lines.append(f"    f{row['frame']:<6} {row['side'] or '?':<5} "
                     f"P{str(row['point']):<4} {row['kind']:<26} "
                     f"opener={row['window_opener']}  "
                     + ("no contact within 80f" if near is None
                        else f"nearest f{near['frame']} {near['action']} "
                             f"({near['delta_f']:+d} f)"))
        for entry in row["neighbours"]:
            lines.append(f"        f{entry['frame_number']:<7} {entry['action']:<8}"
                         f" {entry['team'] or '?':<2} t{str(entry['touch_number']):<3}"
                         f" R{str(entry['rally_id']):<3} tr{str(entry['track_id']):<3}"
                         f" gap{str(entry['gap_prev']):<6}")

    g2d = data["g2"]
    lines.append("")
    lines.append("=" * 110)
    lines.append("  GATE G2 (descriptive; decides order, nothing ships)")
    lines.append(f"    MISS_NEAR = {g2d['miss_near']}")
    lines.append(f"    buckets over the misses {g2d['buckets_over_misses']}")
    lines.append(f"    repairable (mislabeled_opener + not_opener) = {g2d['repairable']}"
                 f"  -> SR4 near side proceeds after the fact: "
                 f"{'YES' if g2d['sr4_near_proceeds_after_the_fact'] else 'NO'}"
                 f" (rule: >= {G2_SR4_THRESHOLD})")
    lines.append(f"    never produced (not_emitted) = {g2d['never_produced']}"
                 f"  coasting predicted:true = {g2d['coasting_predicted_true']}"
                 f" (readable {g2d['coasting_readable']})"
                 f"  -> M-b reopened: {'YES' if g2d['mb_reopened'] else 'NO'}"
                 f" (rule: >= {G2_MB_THRESHOLD} AND >= {G2_MB_COASTING})")
    lines.append(f"    far_unseen_near_reception_first = "
                 f"{g2d['far_unseen_near_reception_first']}")
    lines.append(f"    scope guard: all-33-serve buckets {g2d['all_serves_buckets']}"
                 f"  (NEVER pooled into the misses above)")
    drill_agree = data["drill_action_files"]
    lines.append(f"    drill action files sr1d/base vs sr1: "
                 f"{[ (d['n'], d['identical']) for d in drill_agree]}")
    lines.append("=" * 110)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", default="output/sr4a/near_openings.json")
    ap.add_argument("--g1-only", action="store_true",
                    help="print the G1 gate and stop")
    args = ap.parse_args(argv)

    data = build()
    if args.g1_only:
        g1d = data["g1"]
        print(json.dumps(g1d, indent=1))
        return 0 if g1d["pass"] else 1
    print(format_report(data))
    out = REPO / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0 if data["g1"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())