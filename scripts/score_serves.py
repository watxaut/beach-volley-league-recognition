#!/usr/bin/env python3
"""SR0 -- ONE serve scorer, per side, dev vs held-out (open point 30).

Fifty-five sessions in, every serve number in this project was measured by a
different script with a different scope, and the plan that follows from that
(`docs/serve_reliability_plan.md`) starts by fixing the measurement.  This is
that measurement: one scorer, one matching rule, every stream, every session
that has serve GT.

What it scores (streams are DECLARED, not discovered, so a stream can never be
silently swapped):

==================  ========================================================
``production``      the emitted ``serve`` actions of a pipeline run
``pass2``           ``actions_pass2`` of ``relabel_serves.py``
``serve_evidence``  every record of ``consume_serve_evidence.py`` (coverage)
``serve_evidence_bound``  the record that consumer bound to a point (binding)
``game_on``         ``game_state.points[].start_frame`` -- the rally ONSET,
                    a TIME proposer, not a serve claim
``serve_records``   the SR4 per-point record, when it exists
==================  ========================================================

Two numbers per stream, never one (the #54 lesson): **evidence coverage**
(a record exists near the GT contact) and **binding** (the layer that consumed
it put one on the right point).  A stream that was FIT on the same serves it is
scored on is marked ``in_sample`` in the artifact, because the far-serve
evidence numbers are exactly that (#53 swept all 17 match far serves; the
out-of-sample signal is the held-out column).

Matching rule, one for every stream: **greedy one-to-one, nearest first,
within the owner contact's own frame tolerance** (``frame_tolerance``, 15 f on
every owner contact; ``--tolerance`` overrides).  Side-correct matching is the
default because a serve emitted on the wrong side is not a serve on that side;
the position-only count is reported next to it so nothing is hidden.

NO video is decoded, NO ``src/`` file is touched: this is post-hoc scoring
(AGENTS.md §6).  A serve GT that arrives as wall-clock time is converted with
the session's PTS/fps timebase -- never by seeking (AGENTS.md §9).

Usage::

    venv/bin/python scripts/score_serves.py                     # everything
    venv/bin/python scripts/score_serves.py --session match_20260920
    venv/bin/python scripts/score_serves.py --stream production --detail
    venv/bin/python scripts/score_serves.py --json output/serves/sr0.json
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import resolve_side_switches as rs  # noqa: E402  (path set above)

REPO = Path(__file__).resolve().parent.parent

#: Owner contact frames are coarse (the GT file says +-10-15 f).
DEFAULT_TOLERANCE = 15
#: How far a false emission may be from an owner contact before it is called
#: "dead-time" rather than "a rally contact with the wrong label".
DEAD_TIME_SEARCH_F = 80

MATCH_GT = "ground_truth/20260920_match_contacts.json"
MATCH_PIPELINE = "output/20260920_match_ari_joan_lost/pipeline_output.json"
MATCH_RELABEL = "output/serve_relabel.json"
MATCH_EVIDENCE = "output/serve_evidence.json"
SERVE_RECORDS = "output/serve_records.json"


# ---------------------------------------------------------------------------
# GT rows
# ---------------------------------------------------------------------------

def _frame_of(event: Dict[str, Any]) -> Optional[int]:
    for key in ("match_frame", "frame_number", "frame", "clip_frame"):
        if event.get(key) is not None:
            return int(event[key])
    return None


def _action_of(event: Dict[str, Any]) -> Optional[str]:
    return event.get("final_action") or event.get("action")


def contact_gt_events(blob: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every GT contact of a contact-GT blob (match and entreno dialects)."""
    events = (blob.get("annotated_frames") or {}).get("actions", {}).get("events")
    if events is None:
        events = blob.get("events") or []
    return [e for e in events if isinstance(e, dict) and _frame_of(e) is not None]


def serve_rows_from_contact_gt(blob: Dict[str, Any],
                               split_of: Optional[Callable[[Optional[int]], str]] = None,
                               squad_to_side: Optional[Callable[[Optional[str]], Optional[str]]] = None,
                               tolerance: int = DEFAULT_TOLERANCE
                               ) -> List[Dict[str, Any]]:
    """GT serve contacts as scorer rows.

    ``side`` comes from the owner's ``owner_side`` when the file has it (the
    match), else from ``squad_to_side`` (the entreno captures carry squad
    letters only, and A played near on those recordings).  ``side_source`` is
    kept so a reader can see which convention produced the number.
    """
    rows = []
    for event in contact_gt_events(blob):
        if _action_of(event) != "serve":
            continue
        frame = _frame_of(event)
        point = event.get("point")
        side = event.get("owner_side")
        source = "owner_side"
        if side is None and squad_to_side is not None:
            side = squad_to_side(event.get("player_team"))
            source = "squad (side mapping)"
        rows.append({
            "frame": int(frame),
            "point": int(point) if point is not None else None,
            "side": side,
            "squad": event.get("player_team"),
            "side_source": source,
            "tolerance": int(event.get("frame_tolerance") or tolerance),
            "split": split_of(point) if split_of else "all",
        })
    rows.sort(key=lambda r: r["frame"])
    return rows


#: SR3's serve-only dictation: ``mm:ss.s near|far [server] [outcome]``.
SR3_LINE = re.compile(
    r"^\s*(?P<time>\d+):(?P<sec>\d+(?:\.\d+)?)\s+(?P<side>near|far)\b"
    r"(?P<rest>.*)$")


def parse_serve_gt_text(text: str, timebase: Callable[[float], int],
                        point_of: Optional[Callable[[int], Optional[int]]] = None,
                        split: str = "new") -> List[Dict[str, Any]]:
    """The SR3 serve-only GT format -> scorer rows.

    ``timebase`` maps seconds to a frame index.  On a VFR recording that MUST be
    a PTS-derived index and never a seek (AGENTS.md §9), which is why the
    conversion is injected rather than computed here from a nominal fps.
    """
    rows = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = SR3_LINE.match(stripped)
        if not m:
            continue
        seconds = int(m.group("time")) * 60 + float(m.group("sec"))
        frame = timebase(seconds)
        rest = m.group("rest").split()
        rows.append({
            "frame": int(frame),
            "point": point_of(int(frame)) if point_of else None,
            "side": m.group("side"),
            "squad": None,
            "side_source": "owner dictation",
            "tolerance": DEFAULT_TOLERANCE,
            "split": split,
            "line": lineno,
            "note": " ".join(rest),
        })
    rows.sort(key=lambda r: r["frame"])
    return rows


# ---------------------------------------------------------------------------
# candidate streams
# ---------------------------------------------------------------------------

#: Owner side words -> the COURT-SIDE letters the perception stack speaks
#: (``CourtCalibration.get_team``: A = near half, B = far half).  Squads are a
#: different vocabulary that flips at a side switch, so the two are never
#: interchanged silently (STATUS: raw team 0.518 was exactly this confound).
COURT_TO_SIDE_LETTER = {"near": "A", "far": "B"}


def _candidate(frame: int, side: Optional[str] = None, squad: Optional[str] = None,
               point: Optional[int] = None, **meta: Any) -> Dict[str, Any]:
    return {"frame": int(frame), "side": side, "squad": squad, "point": point,
            **meta}


def production_candidates(pipeline: Dict[str, Any],
                          point_of: Optional[Callable[[int], Optional[int]]] = None
                          ) -> List[Dict[str, Any]]:
    """Emitted ``serve`` actions.  ``team`` is a COURT-SIDE letter (A=near)."""
    out = []
    for action in pipeline.get("actions") or []:
        if action.get("action") != "serve":
            continue
        frame = action.get("frame_number", action.get("frame"))
        if frame is None:
            continue
        side = rs.side_letter_to_court(action.get("team"))
        out.append(_candidate(int(frame), side=side, squad=None,
                              point=point_of(int(frame)) if point_of else None,
                              team=action.get("team"),
                              track_id=action.get("track_id"),
                              confidence=action.get("confidence")))
    out.sort(key=lambda c: c["frame"])
    return out


def pass2_candidates(relabel: Dict[str, Any],
                     point_of: Optional[Callable[[int], Optional[int]]] = None
                     ) -> List[Dict[str, Any]]:
    """``actions_pass2`` serves.

    Two vocabularies live in one action: ``pass2_team`` is a SQUAD letter and
    it is GT-derived (winner-serves), while ``team`` is the emitted COURT-SIDE
    letter, which is not.  The side read used for matching is therefore the
    emitted one and the squad is carried separately and flagged, so the pass-2
    side number cannot be bought by its own GT-derived squad.
    """
    out = []
    for action in relabel.get("actions_pass2") or []:
        if action.get("pass2_action", action.get("action")) != "serve":
            continue
        if action.get("pass2_demoted"):
            continue
        frame = action.get("frame_number")
        if frame is None:
            continue
        point = point_of(int(frame)) if point_of else None
        out.append(_candidate(int(frame),
                              side=rs.side_letter_to_court(action.get("team")),
                              squad=action.get("pass2_team"), point=point,
                              pass2_source=action.get("pass2_source")))
    out.sort(key=lambda c: c["frame"])
    return out


def evidence_record_candidates(evidence: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every serve-EVIDENCE record: the coverage number (#53's 14/17 lives here)."""
    out = []
    for record in evidence.get("records") or []:
        frame = record.get("frame")
        if frame is None:
            continue
        out.append(_candidate(int(frame), side="far",
                              sources=record.get("sources")))
    out.sort(key=lambda c: c["frame"])
    return out


def evidence_bound_candidates(evidence: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The record the consumer bound to a point: the binding number (9/17)."""
    out = []
    for row in evidence.get("points") or []:
        record = row.get("serve_evidence")
        if not record:
            continue
        frame = record.get("frame")
        if frame is None:
            continue
        out.append(_candidate(int(frame), side="far", point=row.get("point"),
                              sources=record.get("sources")))
    out.sort(key=lambda c: c["frame"])
    return out


def game_on_candidates(pipeline: Dict[str, Any],
                       point_of: Optional[Callable[[int], Optional[int]]] = None
                       ) -> List[Dict[str, Any]]:
    """Rally ONSETS (the backdated burst start of every confirmed GAME_ON point).

    This stream knows NOTHING about sides -- it is a pure TIME proposer, and its
    unmatched candidates are unmatched ONSETS, not false serves.
    """
    out = []
    points = (pipeline.get("game_state") or {}).get("points") or []
    for entry in points:
        frame = entry.get("start_frame")
        if frame is None:
            continue
        out.append(_candidate(int(frame), side=None,
                              point=point_of(int(frame)) if point_of else None,
                              end_frame=entry.get("end_frame"),
                              n_actions=entry.get("n_actions")))
    out.sort(key=lambda c: c["frame"])
    return out


def serve_record_candidates(blob: Dict[str, Any],
                            point_of: Optional[Callable[[int], Optional[int]]] = None
                            ) -> List[Dict[str, Any]]:
    """The SR4 per-point serve record (``output/serve_records.json``)."""
    records = blob.get("records") or blob.get("serve_records") or []
    out = []
    for record in records:
        frame = record.get("t_contact_frame", record.get("frame"))
        if frame is None:
            continue
        out.append(_candidate(int(frame), side=record.get("side"),
                              squad=record.get("squad"), point=record.get("point"),
                              outcome=record.get("outcome"),
                              confidence=record.get("confidence")))
    out.sort(key=lambda c: c["frame"])
    return out


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------

def match_candidates(gt_rows: Sequence[Dict[str, Any]],
                     candidates: Sequence[Dict[str, Any]],
                     require_side: bool = True,
                     point_bound: bool = False) -> Dict[str, Any]:
    """Greedy one-to-one matching, nearest pair first, inside each row's tolerance.

    Nearest-first is the natural order for serves: a GT serve has one true
    emission, and the closest one to it is the match even when a second
    emission is nearby (the post-contact echo, #54).

    ``require_side`` makes a hit side-correct, which is the right headline for
    a per-side recall; the positional match is run alongside it so side accuracy
    is measured and not assumed (``side_ok`` is trivially true otherwise).

    ``point_bound`` reproduces what a CONSUMER of the evidence actually claims:
    a record bound to the wrong point is a binding miss even when it sits on the
    serve.  That distinction is the whole 13-vs-9 gap between coverage and
    binding (#54), so it cannot be left to a frame comparison.
    """
    pairs = []
    for gi, gt in enumerate(gt_rows):
        for ci, cand in enumerate(candidates):
            delta = cand["frame"] - gt["frame"]
            if abs(delta) > gt["tolerance"]:
                continue
            if require_side and cand.get("side") and gt.get("side") \
                    and cand["side"] != gt["side"]:
                continue
            if point_bound and (cand.get("point") is None
                                or gt.get("point") is None
                                or cand["point"] != gt["point"]):
                continue
            pairs.append((abs(delta), gi, ci))
    pairs.sort()
    used_gt, used_cand = set(), set()
    matched = []
    for _, gi, ci in pairs:
        if gi in used_gt or ci in used_cand:
            continue
        used_gt.add(gi)
        used_cand.add(ci)
        gt, cand = gt_rows[gi], candidates[ci]
        matched.append({"gt": gi, "candidate": ci,
                        "delta_f": cand["frame"] - gt["frame"],
                        "side_ok": (None if not cand.get("side")
                                    else cand["side"] == gt.get("side"))})
    unmatched_gt = [i for i in range(len(gt_rows)) if i not in used_gt]
    unmatched_cand = [i for i in range(len(candidates)) if i not in used_cand]
    return {"matched": matched, "unmatched_gt": unmatched_gt,
            "unmatched_candidates": unmatched_cand}


def classify_false_positives(candidates: Sequence[Dict[str, Any]],
                             unmatched: Sequence[int],
                             gt_contacts: Sequence[Dict[str, Any]],
                             search_f: int = DEAD_TIME_SEARCH_F) -> List[Dict[str, Any]]:
    """Why each unmatched emission is unmatched -- the SR1 taxonomy, in embryo.

    An emission next to an owner contact that is NOT a serve is a label
    problem; one with no contact within ``search_f`` is a dead-time handling
    (the two known ones, f2414 / f5130).  Both are needed before any rule is
    designed (SR1).
    """
    rows = []
    for index in unmatched:
        cand = candidates[index]
        frame = cand["frame"]
        near = [c for c in gt_contacts if abs(int(c["frame"]) - frame) <= search_f]
        near.sort(key=lambda c: abs(int(c["frame"]) - frame))
        nearest = near[0] if near else None
        if nearest is None:
            kind = "dead_time_handling"
        elif _action_of(nearest) == "serve":
            kind = "serve_outside_tolerance"
        else:
            kind = "rally_contact_mislabeled"
        rows.append({
            "frame": frame,
            "side": cand.get("side"),
            "point": cand.get("point"),
            "meta": {k: v for k, v in cand.items()
                     if k not in ("frame", "side", "squad", "point")},
            "nearest_contact": None if nearest is None else {
                "frame": int(nearest["frame"]),
                "action": nearest.get("action"),
                "delta_f": int(nearest["frame"]) - frame,
                "side": nearest.get("owner_side"),
            },
            "kind": kind,
        })
    return rows


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def _rate(ok: Optional[int], total: int) -> Optional[float]:
    if total <= 0:
        return None
    return round(float(ok) / float(total), 4)


def _offset_stats(deltas: Sequence[int]) -> Dict[str, Any]:
    if not deltas:
        return {"n": 0, "median": None, "min": None, "max": None,
                "abs_median": None}
    absolute = sorted(abs(d) for d in deltas)
    return {"n": len(deltas), "median": int(statistics.median(deltas)),
            "min": int(min(deltas)), "max": int(max(deltas)),
            "abs_median": int(statistics.median(absolute))}


def _cell(gt_n: int, hits: int, fp: int, points: int, side_ok: Optional[int],
          side_n: Optional[int], squad_ok: Optional[int], squad_n: Optional[int],
          deltas: Sequence[int], proposes_serve: bool = True) -> Dict[str, Any]:
    """One (side, split) cell.

    ``emitted`` / ``precision`` exist only for a stream that actually CLAIMS a
    serve per candidate.  A proposal stream (raw evidence records) and a
    time-only stream (the rally onset) report their unmatched candidates
    separately: calling 74 evidence records "74 false serves" or calling the
    rally onset "precision 1.000" would both be fiction.

    ``side_n`` / ``squad_n`` are their OWN denominators (positional hits, hits
    with a squad call), never the side-correct hit count: under side-aware
    matching that count is tautologically right and would report 1.00 - or
    nothing at all - for a stream that gets the side wrong every time.
    """
    return {
        "gt_serves": gt_n,
        "hits": hits,
        "recall": _rate(hits, gt_n),
        "proposes_serve": proposes_serve,
        "emitted": (hits + fp) if proposes_serve else None,
        "tp": hits if proposes_serve else None,
        "false_positives": fp if proposes_serve else None,
        "unmatched": fp,
        "precision": _rate(hits, hits + fp) if proposes_serve else None,
        "points": points,
        "fp_per_point": round(float(fp) / points, 4) if (points and proposes_serve) else None,
        "side_accuracy": _rate(side_ok, side_n) if side_n else None,
        "side_scored": side_n,
        "squad_accuracy": _rate(squad_ok, squad_n) if squad_n else None,
        "squad_scored": squad_n,
        "offsets_f": _offset_stats(deltas),
    }


def score_stream(stream: Dict[str, Any], gt_rows: Sequence[Dict[str, Any]],
                 gt_contacts: Sequence[Dict[str, Any]], switches: Sequence[int],
                 near_served: Dict[str, str]) -> Dict[str, Any]:
    """One stream against every GT serve, split by side and by dev/held-out.

    ``near_served`` maps a point number to the squad playing NEAR in that point,
    which is what turns a court-side letter into a squad (and a squad into a
    court side) across a side switch.  Both accuracies are reported because the
    streams disagree about which vocabulary they speak: the action stream says
    SIDE, pass-2 says SQUAD (and its squad is winner-serves-derived, i.e. GT
    derived -- ``gt_derived`` says so).
    """
    candidates = stream["candidates"]
    requires_side = bool(stream.get("side_aware", True))
    point_bound = bool(stream.get("point_bound", False))
    match = match_candidates(gt_rows, candidates, require_side=requires_side,
                             point_bound=point_bound)
    # The positional match answers "was a serve emitted near this serve AT ALL",
    # which is what side accuracy has to be measured against.
    positional = match_candidates(gt_rows, candidates, require_side=False,
                                  point_bound=point_bound)
    pos_side_ok = [e for e in positional["matched"]
                   if e["side_ok"] is not None and e["side_ok"]]
    pos_side_scored = [e for e in positional["matched"] if e["side_ok"] is not None]

    tp_by_gt: Dict[int, Dict[str, Any]] = {}
    for entry in match["matched"]:
        tp_by_gt[entry["gt"]] = entry

    def squad_of(gt: Dict[str, Any], cand: Dict[str, Any]) -> Optional[bool]:
        """True = the stream's squad call matches the GT squad (None = unknown)."""
        gt_squad = gt.get("squad")
        point = gt.get("point")
        near = near_served.get(point) if point is not None else None
        if gt_squad is None or near is None:
            return None
        cand_squad = cand.get("squad")
        if cand_squad is None:
            letter = COURT_TO_SIDE_LETTER.get(cand.get("side") or "")
            if letter is None:
                return None
            cand_squad = rs.side_to_squad(letter, point, switches)
        if cand_squad is None:
            return None
        return cand_squad == gt_squad

    def in_fp_scope(cand: Dict[str, Any]) -> bool:
        """A candidate counts as a false POSITIVE in the side it claims.

        A stream that claims the far side and lands on a near serve is not a
        far false positive -- it is a far emission whose side was wrong, which
        the hit table already shows as a miss.  Charging it as a far FP as well
        would double-count one event.
        """
        if not stream.get("proposes_serve", True):
            return False
        point = cand.get("point")
        if cand.get("side") and point is not None and near_served.get(point):
            return rs.side_letter_to_court(cand["side"]) != cand["side"]
        return True

    groups: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for index, gt in enumerate(gt_rows):
        key = (gt.get("side") or "unknown", gt.get("split") or "all")
        groups.setdefault(key, {"gt": [], "hits": 0, "deltas": [],
                                "pos": 0, "pos_side_ok": 0, "squad_ok": 0,
                                "squad_n": 0})
        groups[key]["gt"].append(index)
        entry = tp_by_gt.get(index)
        if entry is not None:
            cand = candidates[entry["candidate"]]
            groups[key]["hits"] += 1
            groups[key]["deltas"].append(entry["delta_f"])
            verdict = squad_of(gt, cand)
            if verdict is not None:
                groups[key]["squad_n"] += 1
                groups[key]["squad_ok"] += 1 if verdict else 0
        pos = next((e for e in positional["matched"] if e["gt"] == index), None)
        if pos is not None:
            groups[key]["pos"] += 1
            groups[key]["pos_side_ok"] += 1 if pos["side_ok"] else 0

    fp_rows = classify_false_positives(
        candidates, match["unmatched_candidates"], gt_contacts)

    def emitted_for(side: Optional[str], split: str) -> List[int]:
        """Candidates charged to a (side, split) cell for the FP accounting."""
        matched_candidates = {e["candidate"] for e in match["matched"]}
        out = []
        for index, cand in enumerate(candidates):
            if index in matched_candidates:
                continue
            if not in_fp_scope(cand):
                continue
            point = cand.get("point")
            cand_split = "all"
            if point is not None:
                cand_split = next((g["split"] for g in gt_rows if g["point"] == point),
                                  "all")
            if split not in ("all", cand_split):
                continue
            if side in (None, "unknown"):
                out.append(index)
            elif cand.get("side") == side:
                out.append(index)
        return out

    n_points = len({g["point"] for g in gt_rows if g.get("point") is not None})
    claims = bool(stream.get("proposes_serve", True))
    cells: Dict[str, Any] = {}
    for (side, split), bucket in sorted(groups.items()):
        idx = emitted_for(side, split)
        cells[f"{side}/{split}"] = _cell(
            len(bucket["gt"]), bucket["hits"], len(idx),
            n_points if split == "all" else 0,
            bucket["pos_side_ok"] if (requires_side and bucket["pos"]) else None,
            bucket["pos"] if requires_side else None,
            bucket["squad_ok"] if bucket["squad_n"] else None,
            bucket["squad_n"] or None,
            bucket["deltas"], proposes_serve=claims)

    # Side totals across splits (the SR4 acceptance view: recall on EACH side).
    totals: Dict[str, Any] = {}
    for side in sorted({g["side"] for g in gt_rows if g.get("side")}):
        gt_n = sum(1 for g in gt_rows if g.get("side") == side)
        hits = sum(1 for e in match["matched"]
                   if gt_rows[e["gt"]].get("side") == side)
        deltas = [e["delta_f"] for e in match["matched"]
                  if gt_rows[e["gt"]].get("side") == side]
        side_scored = [e for e in positional["matched"]
                       if gt_rows[e["gt"]].get("side") == side
                       and e["side_ok"] is not None]
        side_ok = [e for e in side_scored if e["side_ok"]]
        squad_hits = [e for e in match["matched"]
                      if gt_rows[e["gt"]].get("side") == side
                      and squad_of(gt_rows[e["gt"]], candidates[e["candidate"]]) is not None]
        squad_ok = [e for e in squad_hits
                    if squad_of(gt_rows[e["gt"]], candidates[e["candidate"]])]
        fp = len(emitted_for(side, "all"))
        totals[side] = _cell(gt_n, hits, fp, n_points,
                             len(side_ok) if side_scored else None,
                             len(side_scored) if requires_side else None,
                             len(squad_ok) if squad_hits else None,
                             len(squad_hits) or None,
                             deltas, proposes_serve=claims)

    overall_gt = len(gt_rows)
    overall_fp = len(emitted_for(None, "all"))
    overall = _cell(overall_gt, len(match["matched"]), overall_fp, n_points,
                    len(pos_side_ok) if (requires_side and pos_side_scored) else None,
                    len(pos_side_scored) if requires_side else None,
                    None, None,
                    [e["delta_f"] for e in match["matched"]],
                    proposes_serve=claims)

    # Split totals (dev vs held-out) -- the column that decides in-sample claims.
    splits: Dict[str, Any] = {}
    for split in sorted({g.get("split") or "all" for g in gt_rows}):
        idx = [i for i, g in enumerate(gt_rows) if (g.get("split") or "all") == split]
        hits = sum(1 for e in match["matched"] if e["gt"] in idx)
        deltas = [e["delta_f"] for e in match["matched"] if e["gt"] in idx]
        splits[split] = _cell(len(idx), hits, len(emitted_for(None, split)), 0,
                              None, None, None, None, deltas,
                              proposes_serve=claims)

    per_serve = []
    for index, gt in enumerate(gt_rows):
        entry = tp_by_gt.get(index)
        nearest = (min(candidates,
                       key=lambda c: (abs(c["frame"] - gt["frame"]),
                                      c["frame"] - gt["frame"]))
                   if candidates else None)
        per_serve.append({
            "point": gt.get("point"), "frame": gt["frame"], "side": gt.get("side"),
            "squad": gt.get("squad"), "split": gt.get("split"),
            "hit": entry is not None,
            "candidate_frame": None if entry is None else candidates[entry["candidate"]]["frame"],
            "delta_f": None if entry is None else entry["delta_f"],
            "side_ok": None if entry is None else entry["side_ok"],
            "nearest_candidate_f": None if nearest is None else nearest["frame"],
            "nearest_candidate_delta_f": (
                None if nearest is None else nearest["frame"] - gt["frame"]),
        })

    return {
        "proposes_serve": claims,
        "side_aware": requires_side,
        "point_bound": point_bound,
        "gt_derived": bool(stream.get("gt_derived", False)),
        "in_sample": bool(stream.get("in_sample", False)),
        "provenance": stream.get("provenance", {}),
        "source": stream.get("source"),
        "emitted_total": len(candidates),
        "unmatched_total": len(match["unmatched_candidates"]),
        "positional_hits": len(positional["matched"]),
        "positional_hits_wrong_side": len(pos_side_scored) - len(pos_side_ok),
        "overall": overall,
        "by_side": totals,
        "by_split": splits,
        "by_side_split": cells,
        "per_serve": per_serve,
        "false_positives": fp_rows,
        "unmatched_gt_frames": [gt_rows[i]["frame"] for i in match["unmatched_gt"]],
    }


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------

def match_split(point: Optional[int]) -> str:
    """P1-P8 are the DEV half of the match; P9-P33 the held-out half."""
    if point is None:
        return "unknown"
    return "dev" if int(point) <= 8 else "held_out"


def entreno_split(point: Optional[int]) -> str:
    """The entreno captures were the working validation set: dev, by definition."""
    return "dev"


def entreno_squad_to_side(squad: Optional[str]) -> Optional[str]:
    """On the entreno captures A played the NEAR half (owner GT convention)."""
    return {"A": "near", "B": "far"}.get(squad or "")


def _read(path: str) -> Optional[Dict[str, Any]]:
    p = REPO / path
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _source_meta(blob: Optional[Dict[str, Any]], path: str) -> Dict[str, Any]:
    meta: Dict[str, Any] = {"path": path, "present": blob is not None}
    if blob:
        video = blob.get("video") or {}
        if isinstance(video, dict):
            meta["fps"] = video.get("fps")
        meta["pipeline_version"] = blob.get("pipeline_version")
        meta["processed_at"] = blob.get("processed_at")
    return meta


def _match_point_of(relabel: Dict[str, Any]) -> Callable[[int], Optional[int]]:
    windows = rs.point_windows(relabel)
    return lambda frame: rs.point_for_frame(frame, windows) if windows else None


def build_match_session() -> Dict[str, Any]:
    gt = _read(MATCH_GT)
    pipeline = _read(MATCH_PIPELINE)
    relabel = _read(MATCH_RELABEL)
    evidence = _read(MATCH_EVIDENCE)
    records = _read(SERVE_RECORDS)
    point_of = _match_point_of(relabel or {})
    switches = rs.derive_switches([int(p["point"]) for p in (gt or {}).get("points", [])])

    streams = []
    if pipeline is not None:
        streams.append({
            "name": "production",
            "candidates": production_candidates(pipeline, point_of),
            "source": _source_meta(pipeline, MATCH_PIPELINE),
            "provenance": {"speaks": "court side (team A=near)",
                           "note": "the emitted serve labels themselves"},
        })
    if relabel is not None:
        streams.append({
            "name": "pass2",
            "candidates": pass2_candidates(relabel, point_of),
            "source": _source_meta(relabel, MATCH_RELABEL),
            "gt_derived": True,
            "provenance": {
                "speaks": "squad",
                "note": ("`pass2_team` is the winner-serves-derived structural "
                         "squad, i.e. GT-derived; owner anchors/verdicts are in "
                         "this artifact too"),
            },
        })
    if pipeline is not None:
        streams.append({
            "name": "game_on",
            "candidates": game_on_candidates(pipeline, point_of),
            "source": _source_meta(pipeline, MATCH_PIPELINE),
            "proposes_serve": False,
            "side_aware": False,
            "provenance": {"speaks": "time only",
                           "note": ("the backdated burst start of every confirmed "
                                    "GAME_ON point: unmatched candidates are "
                                    "unmatched ONSETS, not false serves")},
        })
    if evidence is not None:
        streams.append({
            "name": "serve_evidence",
            "candidates": evidence_record_candidates(evidence),
            "source": _source_meta(evidence, MATCH_EVIDENCE),
            "in_sample": True,
            "proposes_serve": False,
            "provenance": {
                "speaks": "far side only",
                "in_sample_reason": ("the #53 operating point was swept on ALL 17 "
                                     "match far serves, held-out included; only the "
                                     "held_out column is out-of-sample"),
                "note": ("coverage: every gated record, bound to nothing. A record is a "
                     "PROPOSAL, so its unmatched count is not a false-serve count; "
                     "the claim is the bound stream below and the precision that "
                     "matters for this layer is the owner FALSE/OFFGAME one "
                     "(#53/#54: 1 FP on 9 moments)"),
            },
        })
        streams.append({
            "name": "serve_evidence_bound",
            "candidates": evidence_bound_candidates(evidence),
            "source": _source_meta(evidence, MATCH_EVIDENCE),
            "in_sample": True,
            "point_bound": True,
            "provenance": {
                "speaks": "far side only",
                "in_sample_reason": ("the #53 operating point was swept on ALL 17 "
                                     "match far serves, held-out included"),
                "note": ("binding: the record the consumer put ON A POINT. A record "
                         "that lands on the serve but was bound to the wrong point "
                         "is a binding miss, which is what separates this 9/17 from "
                         "the 13/17 coverage above"),
            },
        })
    if records is not None:
        streams.append({
            "name": "serve_records",
            "candidates": serve_record_candidates(records, point_of),
            "source": _source_meta(records, SERVE_RECORDS),
            "provenance": {"speaks": "side + squad (SR4 product)"},
        })

    return {
        "key": "match_20260920",
        "label": "20260920 match (33 owner points, 25.67 fps VFR, 720p->up1080)",
        "gt": MATCH_GT,
        "gt_kind": "contact",
        "split_of": match_split,
        "squad_to_side": None,
        "switches": switches,
        "streams": streams,
        "missing": [path for path in (MATCH_PIPELINE, MATCH_RELABEL, MATCH_EVIDENCE)
                    if not (REPO / path).exists()],
    }


def build_entreno_session(n: int) -> Dict[str, Any]:
    gt_path = f"ground_truth/video_entreno_{n}_annotations.json"
    pipeline_path = f"output/video_entreno_{n}/pipeline_output.json"
    gt = _read(gt_path)
    pipeline = _read(pipeline_path)
    streams = []
    if pipeline is not None:
        streams.append({
            "name": "production",
            "candidates": production_candidates(pipeline),
            "source": _source_meta(pipeline, pipeline_path),
            "provenance": {"speaks": "court side (team A=near)"},
        })
    return {
        "key": f"entreno_{n}",
        "label": f"video_entreno_{n} (practice, ~30.0 fps)",
        "gt": gt_path,
        "gt_kind": "contact",
        "split_of": entreno_split,
        "squad_to_side": entreno_squad_to_side,
        "switches": [],
        "streams": streams,
        "missing": [path for path in (gt_path, pipeline_path)
                    if not (REPO / path).exists()],
    }


def build_sessions() -> List[Dict[str, Any]]:
    sessions = [build_match_session()]
    sessions += [build_entreno_session(n) for n in (1, 2, 3, 4, 5, 6, 7)]
    return sessions


def score_session(session: Dict[str, Any]) -> Dict[str, Any]:
    gt_blob = _read(session["gt"])
    if gt_blob is None:
        return {"key": session["key"], "label": session["label"],
                "error": f"missing GT {session['gt']}",
                "missing": session["missing"]}
    gt_rows = serve_rows_from_contact_gt(
        gt_blob, split_of=session["split_of"],
        squad_to_side=session["squad_to_side"])
    gt_contacts = contact_gt_events(gt_blob)
    switches = session["switches"] or rs.derive_switches(
        [int(p["point"]) for p in gt_blob.get("points", [])])
    near_served = {int(p["point"]): rs.near_squad(int(p["point"]), switches)
                   for p in gt_blob.get("points", []) if p.get("point") is not None}
    if not near_served:
        # No point map (the entreno captures): the GT squad letter that plays
        # near IS the squad playing near, which is what squad_to_side read.
        near_served = {row["point"]: row["squad"] for row in gt_rows
                       if row.get("point") is not None and row.get("squad")}

    out: Dict[str, Any] = {
        "key": session["key"],
        "label": session["label"],
        "gt": session["gt"],
        "fps": gt_blob.get("fps"),
        "gt_serves": len(gt_rows),
        "gt_by_side": {side: sum(1 for r in gt_rows if r.get("side") == side)
                       for side in sorted({r.get("side") for r in gt_rows if r.get("side")})},
        "gt_by_split": {split: sum(1 for r in gt_rows if r.get("split") == split)
                        for split in sorted({r.get("split") for r in gt_rows if r.get("split")})},
        "switches": switches,
        "missing": session["missing"],
        "streams": {},
    }
    if not gt_rows:
        out["note"] = "no serve contacts in this GT file"
        return out
    for stream in session["streams"]:
        out["streams"][stream["name"]] = score_stream(
            stream, gt_rows, gt_contacts, switches, near_served)
    return out


# ---------------------------------------------------------------------------
# the SR0 gate (pre-registered in docs/serve_reliability_plan.md)
# ---------------------------------------------------------------------------

GATE = {
    "session": "match_20260920",
    "stream": "production",
    "near": (8, 16),
    "far": (0, 17),
    "false_positives": 12,
}


def gate_check(report: Dict[str, Any]) -> Dict[str, Any]:
    """Reproduce the plan's baseline, or the numbers disagree and everything else is void."""
    session = (report.get("sessions") or {}).get(GATE["session"], {})
    stream = (session.get("streams") or {}).get(GATE["stream"], {})
    by_side = stream.get("by_side") or {}
    observed = {
        "near_hits": (by_side.get("near") or {}).get("hits"),
        "near_n": (by_side.get("near") or {}).get("gt_serves"),
        "far_hits": (by_side.get("far") or {}).get("hits"),
        "far_n": (by_side.get("far") or {}).get("gt_serves"),
        "false_positives": (stream.get("overall") or {}).get("false_positives"),
    }
    checks = {
        "near": observed["near_hits"] == GATE["near"][0]
        and observed["near_n"] == GATE["near"][1],
        "far": observed["far_hits"] == GATE["far"][0]
        and observed["far_n"] == GATE["far"][1],
        "false_positives": observed["false_positives"] == GATE["false_positives"],
    }
    return {"expected": {"near": f"{GATE['near'][0]}/{GATE['near'][1]}",
                         "far": f"{GATE['far'][0]}/{GATE['far'][1]}",
                         "false_positives": GATE["false_positives"]},
            "observed": observed,
            "checks": checks,
            "pass": all(checks.values()),
            "source": "docs/serve_reliability_plan.md SR0 gate"}


def run(sessions: Optional[Sequence[Dict[str, Any]]] = None,
        only_session: Optional[str] = None,
        only_stream: Optional[str] = None) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "tolerance_frames": DEFAULT_TOLERANCE,
        "matching": ("greedy one-to-one, nearest first, inside each GT contact's "
                     "own frame_tolerance; side-correct by default"),
        "sessions": {},
    }
    for session in (sessions if sessions is not None else build_sessions()):
        if only_session and session["key"] != only_session:
            continue
        scored = score_session(session)
        if only_stream:
            scored["streams"] = {k: v for k, v in (scored.get("streams") or {}).items()
                                 if k == only_stream}
        report["sessions"][session["key"]] = scored
    report["gate"] = gate_check(report)
    return report


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def _fmt(value: Optional[float], spec: str = ".3f") -> str:
    return "  n/a" if value is None else format(value, spec)


def _int(value: Optional[int]) -> str:
    return "  n/a" if value is None else str(value)


def _row(label: str, cell: Dict[str, Any]) -> str:
    offsets = cell["offsets_f"]
    return (f"  {label:<26}{cell['gt_serves']:>4}{cell['hits']:>5}"
            f"{_fmt(cell['recall']):>8}{_int(cell['emitted']):>7}"
            f"{_int(cell['tp']):>5}{_int(cell['false_positives']):>5}"
            f"{_fmt(cell['precision']):>8}"
            f"{_fmt(cell['fp_per_point'], '.2f'):>7}"
            f"{_fmt(offsets['median'], '+4d'):>7}"
            f"{_fmt(offsets['abs_median'], '3d'):>5}"
            f"{_fmt(cell['side_accuracy'], '.2f'):>7}"
            f"{_fmt(cell['squad_accuracy'], '.2f'):>7}")


HEADER = (f"  {'stream/side':<26}{'gt':>4}{'hit':>5}{'rec':>8}{'emis':>7}"
          f"{'tp':>5}{'fp':>5}{'prec':>8}{'fp/pt':>7}{'dmed':>7}{'|d|':>5}"
          f"{'side':>7}{'squad':>7}")


def format_report(report: Dict[str, Any], detail: bool = False) -> str:
    lines = ["=" * 110,
             "  SR0 SERVE SCORE -- one scorer, per side, dev vs held-out (open point 30)",
             "=" * 110,
             f"  matching: {report['matching']}"]
    for key, session in report["sessions"].items():
        lines.append("")
        lines.append(f"  SESSION {key} -- {session.get('label','')}")
        if session.get("error"):
            lines.append(f"    ERROR {session['error']}")
            continue
        lines.append(f"    GT {session['gt']}: {session['gt_serves']} serve contacts "
                     f"{session['gt_by_side']} {session['gt_by_split']}")
        if session.get("missing"):
            lines.append(f"    MISSING artifacts: {session['missing']}")
        if not session.get("streams"):
            lines.append(f"    {session.get('note', 'no streams to score')}")
            continue
        for name, stream in session["streams"].items():
            flags = [f for f, on in (("GT-DERIVED", stream["gt_derived"]),
                                     ("IN-SAMPLE", stream["in_sample"]),
                                     ("time-only", not stream["side_aware"]),
                                     ("no serve claim", not stream["proposes_serve"]))
                     if on]
            lines.append("")
            lines.append(f"    STREAM {name}  emitted={stream['emitted_total']}"
                         f"  {'  '.join('[' + f + ']' for f in flags)}")
            prov = stream.get("provenance") or {}
            if prov:
                lines.append(f"      speaks {prov.get('speaks','?')}"
                             + (f" -- {prov['note']}" if prov.get("note") else ""))
                if prov.get("in_sample_reason"):
                    lines.append(f"      IN SAMPLE: {prov['in_sample_reason']}")
            source = stream.get("source") or {}
            if source:
                lines.append(f"      source {source.get('path')}"
                             f"  run={source.get('processed_at') or 'n/a'}"
                             f"  commit={source.get('pipeline_version') or 'n/a'}"
                             + ("" if source.get("present", True)
                                else "  [MISSING]"))
            lines.append(HEADER)
            for side in ("near", "far"):
                if side in stream["by_side"]:
                    lines.append(_row(f"{name} {side}", stream["by_side"][side]))
            lines.append(_row(f"{name} ALL", stream["overall"]))
            if len(stream["by_split"]) > 1:
                for split in sorted(stream["by_split"]):
                    lines.append(_row(f"{name} [{split}]", stream["by_split"][split]))
            lines.append("      per (side, split):")
            for cell_name, cell in stream["by_side_split"].items():
                lines.append(_row(cell_name, cell))
            if not stream["proposes_serve"]:
                lines.append(f"      proposals, not claims: "
                             f"{stream['unmatched_total']} of "
                             f"{stream['emitted_total']} candidates are unmatched "
                             f"(no precision is claimed for this stream)")
            if stream["false_positives"] and stream["proposes_serve"]:
                kinds: Dict[str, int] = {}
                for row in stream["false_positives"]:
                    kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
                lines.append(f"      false emissions: {kinds}")
                for row in stream["false_positives"][:12]:
                    near = row["nearest_contact"]
                    where = f"P{row['point']}" if row.get("point") is not None else "-"
                    lines.append(
                        f"        f{row['frame']:<7} {row['side'] or '?':<5}{where:>5} "
                        + ("no owner contact within "
                           f"{DEAD_TIME_SEARCH_F}f" if near is None
                           else f"nearest contact f{near['frame']} {near['action']}"
                                f" ({near['delta_f']:+d} f)"))
            if detail:
                lines.append("      per GT serve:")
                for row in stream["per_serve"]:
                    lines.append(
                        f"        P{str(row['point']):<4} f{row['frame']:<7}"
                        f" {row['side'] or '?':<5} {row['split'] or '?':<8}"
                        + (f"hit f{row['candidate_frame']} ({row['delta_f']:+d} f)"
                           if row["hit"]
                           else f"miss nearest {row['nearest_candidate_delta_f']:+d} f"
                           if row["nearest_candidate_delta_f"] is not None
                           else "miss no candidate"))
    gate = report["gate"]
    lines += ["", "-" * 110,
              f"  SR0 GATE (pre-registered) -- {'PASS' if gate['pass'] else 'FAIL'}",
              f"    expected {gate['expected']}",
              f"    observed {gate['observed']}",
              f"    checks   {gate['checks']}",
              "=" * 110]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--session", default=None, help="score only this session key")
    ap.add_argument("--stream", default=None, help="score only this stream name")
    ap.add_argument("--detail", action="store_true",
                    help="also print the per-GT-serve table for every stream")
    ap.add_argument("--json", default="output/serves/sr0.json")
    args = ap.parse_args(argv)

    report = run(only_session=args.session, only_stream=args.stream)
    print(format_report(report, detail=args.detail))
    if args.json:
        out = REPO / args.json
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {out}")
    return 0 if report["gate"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())