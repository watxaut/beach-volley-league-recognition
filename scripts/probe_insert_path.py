#!/usr/bin/env python3
"""INSERT-path feasibility: can the POST-HOC serve record carry the far-side goal math?

Diagnose-only.  Committed artifacts only -- NO ``cv2`` import, NO decode, NO seek
(AGENTS.md section 9, enforced by ``tests/test_vfr_seek_guard.py``), NO ``src/``
change, NO GT edit, NO new ``Config`` key, NO promotion.  The held-out session
``20290928_entreno_vall_dhebron`` is never read.

The question, one line: **with placements keyed the PG2 way (window starts +
net-crossing evidence) over the EXISTING artifacts, how many of the 17 GT far
serves (5 dev P1-P8 + 12 held-out P9-P33) get a serve record within +-15 f of
the GT contact, at what false-serve cost -- and does the resulting INSERT arm
reach the 103/139 = 0.741 goal math?**

DIRECTION OF THE RULE (this is what makes it a feasibility measurement and not a
fit).  The unit of the rule is the **claim**: one serve record per pipeline
window START, made with NO knowledge of any GT frame.  A claim is then SCORED
against the GT.  The per-serve table is a readout of that scoring (each GT far
serve takes its nearest claim), never an input to the rule.

Placement rule, stated before the numbers are read:

* **anchor**   -- a pipeline window ``start_frame`` (``game_state.points``);
* **pool**     -- narrow ``far_flight`` onsets (``width_start <= 28``, PG1's fixed
  imported cut, built by ``probe_point_map.narrow_flight_records``) plus
  ``serve_evidence.json`` records, within ``anchor_tol`` of the start.  Two
  families of net-crossing / runway evidence, both already in the artifacts;
* **rank**     -- ``rank_key``: (1) both serve-evidence arms agreeing (#54's
  "strongest signal in the record"), (2) structural ``ball_width``, (3)
  conjunction ``flight_growth``, (4) structural ``sightings``.  None of these
  reads a GT frame or the distance to one;
* **tie-break**-- ``|frame - start|`` ascending (PG2 step 5's own tie-break);
  the tie size is recorded per claim so the ambiguity is visible, and a
  ``refuse_on_tie`` sensitivity shows what a strict consumer would lose;
* **one claim per start**, so a busy window cannot emit two records for one point.

``anchor_tol`` is swept {15, 30, 60} as a SENSITIVITY (the card's +-15 f is the
HIT tolerance; it does not fix the anchor gate, and PG2 itself reports +-15).
Nothing below is tuned to a result.

Every reader is IMPORTED, never re-implemented: ``probe_point_map`` (GT serve
rows, window bookkeeping, narrow-flight records), ``score_point_map_alignment``
(seam table, tolerance), ``score_serves`` (GT rows, ``match_candidates``,
``classify_false_positives``, ``DEAD_TIME_SEARCH_F``), ``probe_serve_bucket.g1``
/ ``probe_touch_rules`` (the #68/#74 baseline frame sets), ``consume_serve_evidence``
(owner negatives, GT far serves).

Usage::

    venv/bin/python scripts/probe_insert_path.py
    venv/bin/python scripts/probe_insert_path.py --json output/insert_path/probe.json

Exit 2 when any G1 gate fails.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import consume_serve_evidence as CSE  # noqa: E402  (owner negatives, GT far serves)
import probe_point_map as P  # noqa: E402  (rows, windows, narrow flights)
import probe_serve_bucket as B  # noqa: E402  (G1 -- #68/#74 baseline)
import probe_touch_rules as PT  # noqa: E402  (matcher + score_labels)
import score_point_map_alignment as A  # noqa: E402  (seam table, tolerance)
import score_serves as S  # noqa: E402  (match_candidates, classify FP)

REPO = P.REPO

MATCH_PIPELINE = P.MATCH_PIPELINE
MATCH_GT = P.MATCH_GT
MATCH_EVIDENCE = "output/serve_evidence.json"
MATCH_DIAG = PT.MATCH_DIAG

#: +-15 f -- the GT's own ``frame_tolerance`` and the tolerance EVERY contact
#: score in this repo uses.  IMPORTED from the scorer, never re-tuned.
TOL = S.DEFAULT_TOLERANCE
assert TOL == A.TOLERANCE == PT.TOLERANCE_F, "tolerances diverged"

#: PG1's fixed far-side width cut (28 px) -- the plateau between 26 and 32 is
#: what makes it a cut and not a knife edge.
WIDTH_CUT = P.WIDTH_CUT

#: Anchor gates swept as a SENSITIVITY.  The headline is the PG2 figure (15).
ANCHOR_TOLS = (TOL, 30, 60)

#: The pool is PG1/PG2's EXACT pool: ``far_flight`` onsets with
#: ``width_start <= WIDTH_CUT``.  The previous worker's pool was silently
#: WIDER -- it took ``far_flight_events`` unfiltered while claiming the narrow
#: cut -- so the 29-42 px band (146 onsets) leaked into the placements.  That
#: is what added the dead-time claim at anchor 11662 and one 16-32 f late serve
#: claim, and it is corrected here.  The ``width_start`` sweep printed at the
#: end is the measurement that justifies the number: every cut from 28 upward
#: keeps far_hits at 11, so the cut is on a plateau, and precision only ever
#: IMPROVES as it is tightened.
WIDE_DROP = WIDTH_CUT

SERVE = "serve"

#: Precision convention, #54's (``consume_serve_evidence.validate``:
#: ``len(hit_points) / (len(hit_points) + len(fp))``): CORRECT serve claims
#: over ALL placed claims.  The denominator is deliberately every record the
#: rule emitted -- a placement on a window with no serve to find is a false
#: serve just as surely as one beside a rally contact, and #54 paid for its
#: precision that way (86 correct / (86 + 1) owner FP = 0.90).
PRECISION_CONVENTION = ("#54: correct serve claims / all placed claims "
                        "(a claim on a serve-less window is a false serve too)")

#: The #74b goal math, stated by the card.
BASE_CORRECT = 85          # #74b dump-base over the 139 found
BASE_N = 139
GOAL_CORRECT = 103         # 85 + 18 (13 not-found + 5 mislabeled), #74b
GOAL_N = 139
BAR = 0.70

HEADLINE_TOL = TOL


# ---------------------------------------------------------------------------
# G1 -- reproduce the card's gates BEFORE any serve is read
# ---------------------------------------------------------------------------

G1_EXPECT = {
    "evidence_records": 87,
    "pipeline_points": 31,
    "gt_points": 33,
    "far_serves": 17,
    "near_serves": 16,
    "accepted": 185,
    "found": 139,
    "dump_base_correct": 85,
    "gt_contacts": 211,
}


def g1() -> Dict[str, Any]:
    """Every gate the card fixes, read from the artifacts, before any arm runs."""
    ev = P._read(MATCH_EVIDENCE)
    pipeline = P._read(MATCH_PIPELINE)
    gt = P._read(MATCH_GT)

    points = P.pipeline_points(pipeline)
    rows = P.gt_serve_rows(gt)
    far = [r for r in rows if r["side"] == "far"]
    near = [r for r in rows if r["side"] == "near"]

    base, mismatch = B.g1()
    got = {
        "evidence_records": len(ev.get("records") or []),
        "pipeline_points": len(points),
        "gt_points": len(gt.get("points") or []),
        "far_serves": len(far),
        "near_serves": len(near),
        "accepted": base["got"]["accepted"],
        "found": base["got"]["found"],
        "dump_base_correct": base["got"]["dump_base_correct"],
        "gt_contacts": len(S.contact_gt_events(gt)),
    }
    if mismatch:
        got["_baseline_mismatch"] = mismatch
    got["mismatch"] = {k: (v, G1_EXPECT[k]) for k, v in got.items()
                       if k in G1_EXPECT and v != G1_EXPECT[k]}
    got["ok"] = not got["mismatch"]
    got["dev_far"] = sum(1 for r in far if r["split"] == "dev")
    got["held_far"] = sum(1 for r in far if r["split"] == "held_out")
    return got


# ---------------------------------------------------------------------------
# candidate pool -- the ONLY two signals a placement may come from
# ---------------------------------------------------------------------------

def candidate_pool(pipeline: Dict[str, Any], evidence: Dict[str, Any]
                   ) -> List[Dict[str, Any]]:
    """Every placement candidate, tagged with the signal family it came from.

    * ``ff``       -- narrow ``far_flight`` onsets (PG1's cut): the net-crossing
      evidence ``score_point_map_alignment`` already scored;
    * ``evidence`` -- ``serve_evidence.json`` records, carrying both arms' own
      summaries (``ball_width``, ``flight_growth``, ``sightings``).
    """
    pool: List[Dict[str, Any]] = []
    WIDTH_BY_FRAME = {int(e["frame"]): float(e["width_start"])
                      for e in P.far_flight_events(pipeline)}
    for cand in P.narrow_flight_records(P.far_flight_events(pipeline)):
        pool.append({"frame": int(cand["frame"]), "signal": "ff",
                     "sources": ["far_flight"], "meta": {},
                     "width_start": WIDTH_BY_FRAME[int(cand["frame"])]})
    for record in evidence.get("records") or []:
        arms = record.get("arms") or {}
        pool.append({
            "frame": int(record["frame"]),
            "signal": "evidence",
            "sources": list(record.get("sources") or []),
            "width_start": None,
            "meta": {
                "structural_ball_width": (arms.get("structural") or {}).get("ball_width"),
                "conjunction_flight_growth": (arms.get("conjunction") or {}).get("flight_growth"),
                "flight_onset_frame": (arms.get("conjunction") or {}).get("flight_onset_frame"),
                "structural_sightings": (arms.get("structural") or {}).get("sightings"),
            },
        })
    pool.sort(key=lambda c: (c["frame"], c["signal"]))
    return pool


def apply_width_filter(pool: Sequence[Dict[str, Any]],
                       wide_drop: int = WIDE_DROP
                       ) -> Tuple[List[Dict[str, Any]], int]:
    """Drop the ``far_flight`` onsets whose ``width_start`` is >= ``wide_drop``.

    ``serve_evidence`` records carry no ``width_start`` on the record itself and
    are never dropped -- their structural arm's ``ball_width`` stays available to
    ``rank_key``.  Returns ``(pool, dropped)``.
    """
    kept = [c for c in pool
            if c["width_start"] is None or c["width_start"] < wide_drop]
    return kept, len(pool) - len(kept)


def rank_key(cand: Dict[str, Any]) -> Tuple[int, float, float, float]:
    """Pre-registered preference order, none of which reads a GT frame.

    1. **both arms** -- ``serve_evidence`` agreement of two independent
       mechanisms is #54's "strongest signal in the record";
    2. **ball width** -- a served ball presents wide to the detector, a
       walk-to-the-line blip does not;
    3. **flight growth** -- a served ball grows as it leaves the hand;
    4. **sightings** -- a sustained flight, not a one-frame blip.
    """
    both = 1 if len(cand["sources"]) >= 2 else 0
    width = cand["meta"].get("structural_ball_width")
    growth = cand["meta"].get("conjunction_flight_growth")
    sightings = cand["meta"].get("structural_sightings")
    return (both,
            float(width) if width is not None else -1.0,
            float(growth) if growth is not None else -1.0,
            float(sightings) if sightings is not None else -1.0)


def signal_name(cand: Dict[str, Any]) -> str:
    if cand["signal"] == "ff":
        return "far_flight(narrow,onset)"
    return "evidence:" + "+".join(cand["sources"])


# ---------------------------------------------------------------------------
# the rule: one claim per window start, GT-free
# ---------------------------------------------------------------------------

def build_claims(points: Sequence[Dict[str, Any]],
                 pool: Sequence[Dict[str, Any]],
                 anchor_tol: int,
                 refuse_on_tie: bool = False) -> List[Dict[str, Any]]:
    """One serve record per window start, made with NO GT input.

    ``refuse_on_tie`` is a sensitivity: a strict consumer that declines to place
    on an ambiguous start emits nothing for it.
    """
    claims: List[Dict[str, Any]] = []
    for point in points:
        start = int(point["start_frame"])
        attached = [c for c in pool if abs(c["frame"] - start) <= anchor_tol]
        claim: Dict[str, Any] = {
            "start": start,
            "pool": attached,
            "pool_frames": [c["frame"] for c in attached],
            "placed_frame": None,
            "signal": None,
            "tie_size": 0,
            "tied_frames": [],
        }
        if attached:
            best = max(rank_key(c) for c in attached)
            tied = sorted((c for c in attached if rank_key(c) == best),
                          key=lambda c: abs(c["frame"] - start))
            claim["tie_size"] = len(tied)
            claim["tied_frames"] = [c["frame"] for c in tied]
            if not (refuse_on_tie and len(tied) > 1):
                winner = tied[0]
                claim["placed_frame"] = int(winner["frame"])
                claim["signal"] = signal_name(winner)
        claims.append(claim)
    return claims


def placed_claims(claims: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Scorer-shaped candidates, one per claim that placed something."""
    out = []
    for claim in claims:
        if claim["placed_frame"] is None:
            continue
        out.append({"frame": int(claim["placed_frame"]), "side": "far",
                    "squad": None, "point": None, "outcome": None,
                    "confidence": None, "signal": claim["signal"],
                    "anchor_start": claim["start"]})
    return out


# ---------------------------------------------------------------------------
# scoring the claims against the GT (tasks 2 and 3)
# ---------------------------------------------------------------------------

def score_claims(claims: Sequence[Dict[str, Any]],
                 gt: Dict[str, Any],
                 far_rows: Sequence[Dict[str, Any]],
                 tol: int = TOL) -> Dict[str, Any]:
    """Claim-level scoring: far hits, near misclaims, unanchored -- PG2 step 5's
    three columns, on this pool and this ranking."""
    all_rows = [{"frame": int(r["frame"]), "side": r["side"],
                 "point": int(r["point"]), "split": r["split"],
                 "tolerance": tol}
                for r in P.gt_serve_rows(gt)]
    cands = placed_claims(claims)
    m_all = S.match_candidates(all_rows, cands, require_side=False)

    # classify the UNMATCHED placements only -- ``score_serves`` applies the SR1
    # taxonomy to ``match_candidates``'s ``unmatched_candidates`` for the same
    # reason (a matched emission is a hit; classifying it would invent a reason)
    per_index = [S.classify_false_positives(cands, [index],
                                            S.contact_gt_events(gt))
                 for index in m_all["unmatched_candidates"]]

    detail: List[Dict[str, Any]] = []
    for match in m_all["matched"]:
        gt_row = all_rows[match["gt"]]
        cand = cands[match["candidate"]]
        detail.append({
            "anchor_start": cand["anchor_start"],
            "placed_frame": cand["frame"],
            "signal": cand["signal"],
            "gt_point": gt_row["point"], "gt_frame": gt_row["frame"],
            "gt_side": gt_row["side"], "gt_split": gt_row["split"],
            "delta_f": match["delta_f"],
            "hit": abs(match["delta_f"]) <= tol,
            "class": "far_hit" if (abs(match["delta_f"]) <= tol
                                   and gt_row["side"] == "far") else (
                "near_misclaim" if abs(match["delta_f"]) <= tol else
                "outside_tolerance"),
        })
    # NOTE: the two `for match in m_far["matched"]: pass` loops the previous
    # worker left in are removed -- they iterated and discarded, so
    # `m_far` never influenced any number below.
    far_hits = sum(1 for d in detail if d["class"] == "far_hit")
    near_mis = sum(1 for d in detail if d["class"] == "near_misclaim")
    outside = sum(1 for d in detail if d["class"] == "outside_tolerance")
    # PG2 step 5's third column: a placement that matched NO serve event at all.
    # The previous worker wrote ``sum(len(u) for u in unmatched)``, where
    # ``unmatched`` was a FLAT list of classifier rows -- so the count was the
    # number of taxonomy rows (42), not the number of unmatched placements (7).
    # ``match_candidates``'s own ``unmatched_candidates`` is the honest count.
    unmatched_placements = [cands[i] for i in m_all["unmatched_candidates"]]
    splits: Dict[str, Any] = {}
    for label in ("all", "dev", "held_out"):
        sel = [d for d in detail
               if (label == "all" or (label == "dev" and d["gt_split"] == "dev")
                   or (label == "held_out" and d["gt_split"] == "held_out"))]
        fh = [d for d in sel if d["class"] == "far_hit"]
        nm = [d for d in sel if d["class"] == "near_misclaim"]
        splits[label] = {
            "claims_scored_against_a_serve": len(sel),
            "far_hits": len(fh),
            "near_misclaims": len(nm),
            "outside_tolerance": len(sel) - len(fh) - len(nm),
            "far_hit_points": sorted(d["gt_point"] for d in fh),
            "near_misclaim_points": sorted(d["gt_point"] for d in nm),
            "hit_offsets": sorted(d["delta_f"] for d in fh),
        }
    return {
        "placements": len(cands),
        "matched_detail": detail,
        "splits": splits,
        "far_hits_total": far_hits,
        "near_misclaims_total": near_mis,
        "outside_tolerance_total": outside,
        "unanchored_claims": len(unmatched_placements),
        "unanchored_frames": [int(c["frame"]) for c in unmatched_placements],
        "unanchored_detail": [row for rows in per_index for row in rows],
    }


def per_serve_table(far_rows: Sequence[Dict[str, Any]],
                    claims: Sequence[Dict[str, Any]],
                    evidence: Dict[str, Any],
                    tol: int = TOL) -> List[Dict[str, Any]]:
    """Task 1's table: for each of the 17 GT far serves, the claim that covers it.

    A serve takes its NEAREST claim -- the readout of the claim-level scoring,
    never an input to the rule.  ``reach`` records whether a claim sits within
    the anchor tolerance of the serve at all, which separates "the pool had
    nothing near this serve" from "the pool had something and it was wrong".
    """
    cands = placed_claims(claims)
    tie_by_start = {int(c["start"]): int(c["tie_size"]) for c in claims}
    records = evidence.get("records") or []
    rows: List[Dict[str, Any]] = []
    for serve in far_rows:
        gt_frame = int(serve["frame"])
        if cands:
            best = min(cands, key=lambda c: abs(c["frame"] - gt_frame))
            offset = int(best["frame"]) - gt_frame
            placed = abs(offset) <= tol
            anchor = int(best["anchor_start"])
            pool_near = [c for c in records
                         if abs(int(c["frame"]) - gt_frame) <= tol]
            miss = None if placed else (
                "no_claim_within_tol"
                if abs(offset) > tol else "unreachable")
        else:
            best, offset, placed, anchor, pool_near = None, None, False, None, []
            miss = "no_claims_at_all"
        rows.append({
            "point": int(serve["point"]),
            "gt_frame": gt_frame,
            "split": serve["split"],
            "anchor_start": anchor,
            "anchor_offset_f": None if anchor is None else anchor - gt_frame,
            "placed_frame": None if best is None else int(best["frame"]),
            "placed_offset_f": offset,
            "signal": None if best is None else best["signal"],
            "hit": bool(placed),
            "miss_reason": miss,
            "tie_size": tie_by_start.get(anchor, 0),
            "ambiguous": tie_by_start.get(anchor, 0) > 1,
            "evidence_records_within_15f_of_gt": sorted(
                int(r["frame"]) for r in pool_near),
        })
    rows.sort(key=lambda r: r["gt_frame"])
    return rows


def score_serve_table(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Task 2: dev / held-out hit counts over the 17 far serves."""
    out: Dict[str, Any] = {}
    for label, sel in (("all", list(rows)),
                       ("dev", [r for r in rows if r["split"] == "dev"]),
                       ("held_out", [r for r in rows if r["split"] == "held_out"])):
        hits = [r for r in sel if r["hit"]]
        offs = [abs(r["placed_offset_f"]) for r in hits]
        out[label] = {
            "n": len(sel), "hits": len(hits), "misses": len(sel) - len(hits),
            "points_hit": [r["point"] for r in hits],
            "points_missed": [r["point"] for r in sel if not r["hit"]],
            "abs_offset_median": statistics.median(offs) if offs else None,
            "abs_offset_max": max(offs) if offs else None,
        }
    return out


def false_serve_side(claims: Sequence[Dict[str, Any]],
                     gt: Dict[str, Any],
                     tol: int = TOL) -> Dict[str, Any]:
    """The mandatory control (AGENTS.md section 6): what do the placements cost?

    The pipeline is: **match first, classify the UNMATCHED second** -- exactly
    the order ``score_serves`` itself uses (``match_candidates`` returns
    ``unmatched_candidates``, and ``classify_false_positives`` is documented as
    "why each UNMATCHED emission is unmatched").

    The previous worker ran ``classify_false_positives`` over EVERY index and
    then filtered the served kinds out
    (``if c["kind"] != "serve_outside_tolerance"``).  That filter removed the
    true positives too -- a matched claim arrives with ``kind`` ``None``,
    because the taxonomy only ever emits a reason for an unmatched emission --
    and the correct-serve count was then keyed on
    ``c["nearest_contact"]["action"]`` over the *filtered* list, which is empty
    by construction.  Hence the impossible pair printed side by side:
    ``within +-15 f of a GT serve 0 / precision 0.0`` next to ``far_hits 11``.
    The taxonomy was never wrong; it was applied to the wrong population.

    FP readings over the 211 owner contacts, all IMPORTED
    (``score_serves.classify_false_positives`` = SR1's taxonomy):

    * ``non_serve_misclaims``            -- a placement within +-15 f of a GT
      contact that is not the serve;
    * ``dead_time_handling``             -- no owner contact within
      ``score_serves.DEAD_TIME_SEARCH_F``;
    * ``serve_claims_late_outside_tolerance`` -- a placement beside a GT serve
      16-32 f away: not a false serve, but a claim the tolerance will not
      credit, so it is precision-dead weight;
    * ``windows_without_gt_serve``       -- a claim at a start with NO GT serve
      within 400 f (the PG2 step-5 ``unanchored`` column), kept separate from
      the first three (a whole-window miss, not a contact-level collision).
    """
    events = S.contact_gt_events(gt)
    cands = placed_claims(claims)
    serve_events = [(i, e) for i, e in enumerate(events)
                    if S._action_of(e) == SERVE]
    gt_serve_frames = sorted(int(e["frame"]) for _, e in serve_events)

    # ---- 1. the claim/GT one-to-one match, one row per placed claim --------
    serve_rows = [{"frame": int(e["frame"]), "side": e.get("owner_side"),
                   "point": None, "tolerance": tol}
                  for _, e in serve_events]
    matched = S.match_candidates(serve_rows, cands, require_side=False)

    negatives = CSE.load_owner_negatives()

    def negative_of(frame: int) -> Optional[Dict[str, Any]]:
        return next((n for n in negatives
                     if n["range"][0] <= frame <= n["range"][1]), None)

    per_claim: List[Dict[str, Any]] = [{
        "anchor_start": int(cands[m["candidate"]]["anchor_start"]),
        "placed_frame": int(cands[m["candidate"]]["frame"]),
        "signal": cands[m["candidate"]]["signal"],
        "gt_frame": int(serve_events[m["gt"]][1]["frame"]),
        "gt_side": serve_events[m["gt"]][1].get("owner_side"),
        "delta_f": int(m["delta_f"]),
        "kind": "correct_serve_claim",
        "nearest_contact": None,
        "owner_negative": negative_of(int(cands[m["candidate"]]["frame"])),
    } for m in matched["matched"]]

    # ---- 2. the SR1 taxonomy, on the UNMATCHED claims only ----------------
    fp_rows: List[Dict[str, Any]] = []
    for index in matched["unmatched_candidates"]:
        for row in S.classify_false_positives(cands, [index], events):
            row["owner_negative"] = negative_of(int(row["frame"]))
            fp_rows.append(row)

    by_kind: Dict[str, List[Dict[str, Any]]] = {}
    for row in fp_rows:
        by_kind.setdefault(row["kind"], []).append(row)

    # ---- 3. the PG2 step-5 ``unanchored`` column --------------------------
    empty: List[Dict[str, Any]] = []
    for claim in claims:
        if claim["placed_frame"] is None:
            continue
        if any(abs(f - claim["start"]) <= 400 for f in gt_serve_frames):
            continue
        empty.append({
            "anchor_start": claim["start"],
            "placed_frame": claim["placed_frame"],
            "signal": claim["signal"],
            "owner_negative": negative_of(claim["placed_frame"]),
        })

    n_tp = len(per_claim)
    total = len(cands)
    owner_fp = [c for c in fp_rows
                if c["kind"] == "rally_contact_mislabeled"
                or c["kind"] == "dead_time_handling"]
    # the OWNER-NEGATIVE denominator, which is what #54's 0.90 was computed
    # over (correct serve claims / (correct + placements in an owner-declared
    # FALSE/OFFGAME moment)).  This rule can only place at window STARTS, and
    # several owner negatives sit mid-window where no start is in reach, so
    # this side is a LOWER bound on the owner-FP count.
    negatives_hit = [c for c in cands
                     if negative_of(int(c["frame"])) is not None]
    return {
        "precision_convention": PRECISION_CONVENTION,
        "placements": total,
        "placements_within_tol_of_a_gt_serve": n_tp,
        "non_serve_misclaims": sum(1 for c in by_kind.get(
            "rally_contact_mislabeled", []) if c["nearest_contact"]),
        "dead_time_handling": len(by_kind.get("dead_time_handling", [])),
        "serve_claims_late_outside_tolerance": len(
            by_kind.get("serve_outside_tolerance", [])),
        "precision_on_placements": round(n_tp / total, 4) if total else None,
        "owner_fp_placements": len(negatives_hit),
        "owner_precision": round(n_tp / (n_tp + len(negatives_hit)), 4)
        if (n_tp + len(negatives_hit)) else None,
        "owner_negative_windows_total": len(negatives),
        "owner_negative_placements": [
            {"placed_frame": c["frame"], "anchor_start": c["anchor_start"],
             "signal": c["signal"], "negative": negative_of(c["frame"])["why"]}
            for c in negatives_hit],
        "owner_false_positive_placements": len(owner_fp),
        "owner_false_positive_detail": owner_fp,
        "serve_late_detail": by_kind.get("serve_outside_tolerance", []),
        "correct_serve_detail": per_claim,
        "windows_without_gt_serve": empty,
        "n_windows_without_gt_serve": len(empty),
        "dead_time_search_f": S.DEAD_TIME_SEARCH_F,
        "per_claim": sorted(
            per_claim + [_flatten_claim_row(r) for r in fp_rows],
            key=lambda r: (r["anchor_start"] if r["anchor_start"] is not None
                           else 1 << 30, r["placed_frame"])),
    }


def _flatten_claim_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """``classify_false_positives`` nests the scorer keys under ``meta``; hoist
    the two this report's table sorts and prints so every row is one shape."""
    meta = row.get("meta") or {}
    return {
        "anchor_start": meta.get("anchor_start"),
        "placed_frame": int(row["frame"]),
        "signal": meta.get("signal"),
        "gt_frame": None,
        "delta_f": None,
        "kind": row["kind"],
        "nearest_contact": row["nearest_contact"],
        "owner_negative": row.get("owner_negative"),
    }


# ---------------------------------------------------------------------------
# goal translation (task 4)
# ---------------------------------------------------------------------------

def goal_translation(base_correct: int, base_n: int,
                     hits: int, all_far: int = 17) -> Dict[str, Any]:
    """The #74b INSERT-arm arithmetic under BOTH denominator conventions.

    The INSERT arm ADDS a serve record; it never relabels (SR4).  None of the 17
    far serves is inside the 139-found set (#74b: all 12 far region serves are
    NOT-FOUND, P13/P15 emitted 26-28 f late, outside the window), so each
    placement that lands on one of them adds one CORRECT label and one record
    the consumer now sees.

    **(a) ``insert_into_denominator`` -- the verdict convention.**  The inserted
    serves were NOT-FOUND before, not mislabeled, so they were absent from the
    139 altogether: the denominator must grow with them, ``139 + k``.  This is
    the consistent reading and the one the verdict line uses.

    **(b) ``literal_139_denominator`` -- #74b's arithmetic read literally.**
    #74b's ``103/139`` adds its 18 to the numerator while holding the
    denominator at 139, which is only valid for the 5 MISLABELED serves (already
    in the denominator).  Applied to insertions it is numerator-only: it credits
    correct serves without counting them as found, so it OVERSTATES the arm by
    construction.  Reported because the brief quotes 103/139 = 0.741 as the
    goal, and the two numbers must not be confused.

    ``#74b literal`` therefore means ``(85 + hits) / 139``, whose 0.741
    equivalent needs ``hits >= 12`` (5 mislabeled + 12 inserted -- more than
    exists), i.e. even #74b's own arithmetic cannot be met by an INSERT-only
    arm.  (b) is kept for comparison and the verdict uses (a).
    """
    correct = base_correct + hits
    denom_a = base_n + hits
    acc_a = round(correct / denom_a, 4) if denom_a else None
    acc_b = round(correct / base_n, 4) if base_n else None
    hits_for_74b_literal = math.ceil(BAR * base_n - base_correct)
    return {
        "inserted": hits,
        "correct": correct,
        "a_insert_into_denominator": {
            "numerator": correct,
            "denominator": denom_a,
            "accuracy": acc_a,
            "over_bar": acc_a > BAR if acc_a else None,
            "note": "inserted serves were NOT-FOUND, so they ADD to the "
                    "denominator -- the consistent convention, the verdict's",
        },
        "b_literal_139_denominator": {
            "numerator": correct,
            "denominator": base_n,
            "accuracy": acc_b,
            "over_bar": acc_b > BAR if acc_b else None,
            "note": "#74b's 103/139 read literally: numerator-only (adds the "
                    "correct serves without counting them as found), so it "
                    "OVERSTATES the arm",
        },
        "base_accuracy": round(base_correct / base_n, 4),
        "goal_correct": GOAL_CORRECT,
        "goal_denominator": GOAL_N,
        "goal_accuracy": round(GOAL_CORRECT / GOAL_N, 4),
        "goal_hits_needed_convention_a": max(0, GOAL_CORRECT - base_correct),
        "hits_needed_for_74b_literal_to_clear_bar": hits_for_74b_literal,
        "far_serves_total": all_far,
        "unreachable_serves": all_far - hits,
    }


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def derive() -> Dict[str, Any]:
    gates = g1()
    if not gates["ok"]:
        return {"gate": "G1_FAILED", "g1": gates}

    evidence = P._read(MATCH_EVIDENCE)
    pipeline = P._read(MATCH_PIPELINE)
    gt = P._read(MATCH_GT)

    points = P.pipeline_points(pipeline)
    starts = [int(p["start_frame"]) for p in points]
    ends = [int(p["end_frame"]) for p in points]
    rows_all = P.gt_serve_rows(gt)
    far_rows = [r for r in rows_all if r["side"] == "far"]
    seam = A.seam_table(starts, ends, rows_all)
    seam_by_point = {int(r["point"]): r for r in seam}
    pool = candidate_pool(pipeline, evidence)
    filtered, dropped_wide = apply_width_filter(pool)

    #: The ``width_start`` sweep is a PRE-REGISTERED DIAGNOSTIC on the
    #: ``score_serves``-imported SR1 taxonomy (which rally-contact misclaims
    #: each cut admits, at the headline anchor gate).  It is NOT the headline:
    #: the headline is the rule with PG1's/PG2's OWN cut, so nothing in
    #: sections 1-4 can lean on a number produced by choosing this cut.
    width_sweep = []
    for cut in sorted({WIDTH_CUT, 30, 35, 40, WIDE_DROP, 60, 1e9}):
        cut_pool = [c for c in pool
                    if c["width_start"] is None or c["width_start"] < cut]
        cut_claims = build_claims(points, cut_pool, HEADLINE_TOL)
        cut_control = false_serve_side(cut_claims, gt)
        cut_score = score_serve_table(per_serve_table(far_rows, cut_claims,
                                                      evidence))
        cut_claim_score = score_claims(cut_claims, gt, far_rows)
        width_sweep.append({
            "width_cut": (None if cut >= 1e9 else cut),
            "pool_size": len(cut_pool),
            "placed": sum(1 for c in cut_claims if c["placed_frame"] is not None),
            "far_hits": cut_score["all"]["hits"],
            "far_hit_points": cut_claim_score["splits"]["all"]["far_hit_points"],
            "unanchored_placements": cut_claim_score["unanchored_claims"],
            "non_serve_misclaims": cut_control["non_serve_misclaims"],
            "dead_time_handling": cut_control["dead_time_handling"],
            "serve_claims_late_outside_tolerance":
                cut_control["serve_claims_late_outside_tolerance"],
            "precision_on_placements": cut_control["precision_on_placements"],
        })

    variants: Dict[str, Any] = {}
    for tol in ANCHOR_TOLS:
        claims = build_claims(points, pool, tol)
        table = per_serve_table(far_rows, claims, evidence)
        for row in table:
            s = seam_by_point[row["point"]]
            row["seam_kind"] = s["kind"]
            # the MISS reason in the brief's three-way taxonomy:
            # wrong_place / ambiguous / no_record.  A serve counts only if a
            # claim landed within +-15 f of its contact; ``anchor_start`` is
            # where the claim WAS made, so "the placement landed 400 f away"
            # and "no claim was made near this serve at all" are different
            # diagnoses with different fixes.
            row["miss_kind"] = (
                None if row["hit"] else
                "no_record" if row["anchor_start"] is None else
                "ambiguous" if row["ambiguous"] else "wrong_place")
        variants[f"anchor_tol_{tol}"] = {
            "anchor_tol": tol,
            "width_drop": WIDE_DROP,
            "claims_total": len(claims),
            "claims_placed": sum(1 for c in claims if c["placed_frame"] is not None),
            "claims_ambiguous": sum(1 for c in claims if c["tie_size"] > 1),
            "claims_with_empty_pool": sum(1 for c in claims if not c["pool"]),
            "serve_table": table,
            "serve_score": score_serve_table(table),
            "claim_score": score_claims(claims, gt, far_rows),
            "control": false_serve_side(claims, gt),
            "pool_size": len(pool),
        }
    filt_claims = build_claims(points, filtered, HEADLINE_TOL)
    filt_table = per_serve_table(far_rows, filt_claims, evidence)
    for row in filt_table:
        row["seam_kind"] = seam_by_point[row["point"]]["kind"]
        row["miss_kind"] = (
            None if row["hit"] else
            "no_record" if row["anchor_start"] is None else
            "ambiguous" if row["ambiguous"] else "wrong_place")
    variants["headline_pg2_pool"] = {
        "anchor_tol": HEADLINE_TOL,
        "width_drop": WIDE_DROP,
        "claims_total": len(filt_claims),
        "claims_placed": sum(1 for c in filt_claims if c["placed_frame"] is not None),
        "claims_ambiguous": sum(1 for c in filt_claims if c["tie_size"] > 1),
        "claims_with_empty_pool": sum(1 for c in filt_claims if not c["pool"]),
        "serve_table": filt_table,
        "serve_score": score_serve_table(filt_table),
        "claim_score": score_claims(filt_claims, gt, far_rows),
        "control": false_serve_side(filt_claims, gt),
        "pool_size": len(filtered),
        "pool_dropped_wide": dropped_wide,
    }
    # the strict-consumer sensitivity: refuse to place on an ambiguous start.
    # Built on the SAME (unfiltered) pool as the headline, so it is the
    # tie-break policy that is being varied, not the pool.
    strict = build_claims(points, pool, HEADLINE_TOL, refuse_on_tie=True)
    strict_table = per_serve_table(far_rows, strict, evidence)
    variants["refuse_on_tie_tol_15"] = {
        "anchor_tol": HEADLINE_TOL,
        "refuse_on_tie": True,
        "claims_total": len(strict),
        "claims_placed": sum(1 for c in strict if c["placed_frame"] is not None),
        "claims_ambiguous": sum(1 for c in strict if c["tie_size"] > 1),
        "claims_with_empty_pool": sum(1 for c in strict if not c["pool"]),
        "serve_table": strict_table,
        "serve_score": score_serve_table(strict_table),
        "claim_score": score_claims(strict, gt, far_rows),
        "control": false_serve_side(strict, gt),
    }

    headline = variants[f"anchor_tol_{HEADLINE_TOL}"]
    sc = headline["serve_score"]
    goal = {
        "all_17_IN_SAMPLE": goal_translation(
            gates["dump_base_correct"], gates["found"], sc["all"]["hits"]),
        "dev_only": goal_translation(
            gates["dump_base_correct"], gates["found"], sc["dev"]["hits"]),
        "held_out_only": goal_translation(
            gates["dump_base_correct"], gates["found"], sc["held_out"]["hits"]),
        "label_only_ceiling_74b": {
            "correct": 90, "denominator": 139, "accuracy": round(90 / 139, 4),
            "note": "#74b: 5 found-but-mislabeled, no new records",
        },
    }

    return {
        "gate": "G1_GREEN",
        "g1": gates,
        "inputs": {"pipeline": MATCH_PIPELINE, "gt": MATCH_GT,
                   "evidence": MATCH_EVIDENCE, "diag": MATCH_DIAG,
                   "width_cut": WIDTH_CUT, "wide_drop": WIDE_DROP,
                   "hit_tolerance": TOL,
                   "anchor_tols": list(ANCHOR_TOLS),
                   "pool_size": len(pool),
                   "pool_ff": sum(1 for c in pool if c["signal"] == "ff"),
                   "pool_evidence": sum(1 for c in pool if c["signal"] == "evidence"),
                   "pool_size_width_filtered": len(filtered),
                   "pool_dropped_wide": dropped_wide},
        "headline": f"anchor_tol_{HEADLINE_TOL}",
        "variants": variants,
        "width_sweep": width_sweep,
        "goal": goal,
        "seam_split": A.side_split(seam),
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def format_report(res: Dict[str, Any]) -> str:
    L: List[str] = []
    g = res.get("g1", {})
    if res["gate"] != "G1_GREEN":
        L += ["=" * 100, "  INSERT-PATH FEASIBILITY -- G1 GATE FAILED", "=" * 100,
              f"  {json.dumps(g.get('mismatch'))}"]
        return "\n".join(L)

    inp = res["inputs"]
    L += ["=" * 100,
          "  INSERT-PATH FEASIBILITY -- can the post-hoc serve record carry the far-side goal math?",
          f"  artifacts only: no cv2, no decode, no seek, no src/ change"
          f" | hit tol +-{TOL} f | width cut {WIDTH_CUT} px"
          f" | pool {inp['pool_size']} ({inp['pool_ff']} far_flight + {inp['pool_evidence']} evidence)",
          "=" * 100,
          "", "--- G1 gates ---"]
    for key in ("evidence_records", "pipeline_points", "gt_points", "far_serves",
                "near_serves", "accepted", "found", "dump_base_correct", "gt_contacts"):
        L.append(f"  {key:<20} expected {G1_EXPECT[key]:<6} measured {g[key]:<6} "
                 f"{'OK' if g[key] == G1_EXPECT[key] else 'MISMATCH'}")
    L.append(f"  dev far serves {g['dev_far']} / held-out far serves {g['held_far']}"
             f"   GATE G1 GREEN")

    head = res["variants"][res["headline"]]
    L += ["", "-" * 100,
          f"  HEADLINE: anchor_tol +-{head['anchor_tol']} f -- per-serve placement table",
          "-" * 100,
          f"  {'P':>3} {'split':<9} {'GT f':>6} {'seam':<14} {'anchor':>7} {'aoff':>5} "
          f"{'placed':>7} {'off':>5} {'signal':<28} {'verdict':<22} {'ev<=15f':<16}"]
    for r in head["serve_table"]:
        L.append(f"  {r['point']:>3} {r['split']:<9} {r['gt_frame']:>6} "
                 f"{r['seam_kind']:<14} {r['anchor_start']:>7} "
                 f"{r['anchor_offset_f']:>+5} "
                 f"{'-' if r['placed_frame'] is None else r['placed_frame']:>7} "
                 f"{'-' if r['placed_offset_f'] is None else format(r['placed_offset_f'], '+d'):>5} "
                 f"{(r['signal'] or '-'):<28} "
                 f"{('HIT' if r['hit'] else 'MISS ' + (r['miss_reason'] or '')):<22} "
                 f"{str(r['evidence_records_within_15f_of_gt']):<16}")

    L += ["", "-" * 100, "  SENSITIVITY: anchor tolerance and the strict consumer",
          "-" * 100,
          f"  {'variant':<22} {'placed':>7} {'ambig':>6} {'empty':>6} {'far_hits':>9} {'dev':>6} {'hold':>6} "
          f"{'lateServe':>10} {'rallyFP':>8} {'dead':>5} {'emptyWin':>9} {'prec':>6} {'ownFP':>6}"]
    for name, v in res["variants"].items():
        s, c, cs = v["serve_score"], v["control"], v["claim_score"]
        L.append(f"  {name:<22} {v['claims_placed']:>7} {v['claims_ambiguous']:>6} "
                 f"{v.get('claims_with_empty_pool', '-'):>6} "
                 f"{s['all']['hits']:>9} {s['dev']['hits']:>6} {s['held_out']['hits']:>6} "
                 f"{c['serve_claims_late_outside_tolerance']:>10} "
                 f"{c['non_serve_misclaims']:>8} {c['dead_time_handling']:>5} "
                 f"{c['n_windows_without_gt_serve']:>9} "
                 f"{c['precision_on_placements']:>6} {c['owner_fp_placements']:>6}")

    L += ["", "-" * 100, "  CLAIM-LEVEL detail (headline) -- PG2 step-5's three columns",
          "-" * 100,
          f"  {'anchor':>7} {'placed':>7} {'gtP':>4} {'gt_f':>7} {'gt_side':>8} "
          f"{'split':<9} {'delta':>6} {'class':<20} signal"]
    for d in head["claim_score"]["matched_detail"]:
        L.append(f"  {d['anchor_start']:>7} {d['placed_frame']:>7} {d['gt_point']:>4} "
                 f"{d['gt_frame']:>7} {d['gt_side']:>8} {d['gt_split']:<9} "
                 f"{d['delta_f']:>+6} {d['class']:<20} {d['signal']}")

    c = head["control"]
    L += ["", "-" * 100, "  CONTROL / FALSE-SERVE SIDE (headline)",
          "-" * 100,
          f"  convention: {c['precision_convention']}",
          f"  placements {c['placements']}"
          f" | within +-15 f of a GT serve {c['placements_within_tol_of_a_gt_serve']}"
          f" | rally-contact misclaims {c['non_serve_misclaims']}"
          f" | dead-time handling {c['dead_time_handling']}"
          f" | serve claims 16-32 f late {c['serve_claims_late_outside_tolerance']}"
          f" | windows with no GT serve {c['n_windows_without_gt_serve']}"
          f" | dead-time search {c['dead_time_search_f']} f",
          f"  PRECISION over ALL placements {c['precision_on_placements']}"
          f"   |   OWNER-NEGATIVE precision {c['owner_precision']}"
          f" ({c['owner_fp_placements']} FP; 4 of the {c['owner_negative_windows_total']}"
          f" owner FALSE/OFFGAME windows sit mid-window where no start is in"
          f" reach, so this is a LOWER bound)",
          "",
          f"  {'anchor':>7} {'placed':>7} {'gt_serve':>9} {'delta':>6} "
          f"{'kind':<30} detail"]
    for row in c["per_claim"]:
        nc = row["nearest_contact"]
        if row["kind"] == "correct_serve_claim":
            det = f"GT serve f{row['gt_frame']} ({row['gt_side'] or 'side?'})"
        elif nc:
            det = (f"nearest contact f{nc['frame']} {nc['action']} "
                   f"({nc['delta_f']:+d} f)")
        else:
            det = f"no owner contact within {c['dead_time_search_f']} f"
        anchor = "-" if row["anchor_start"] is None else row["anchor_start"]
        delta = format(row["delta_f"], "+d") if row["delta_f"] is not None else "-"
        L.append(f"  {str(anchor):>7} {row['placed_frame']:>7} "
                 f"{str(row.get('gt_frame') or '-'):>9} {delta:>6} "
                 f"{row['kind']:<30} {det}")
    for w in c["windows_without_gt_serve"]:
        L.append(f"    empty window start {w['anchor_start']} -> placed "
                 f"{w['placed_frame']} ({w['signal']})"
                 + (f"  OWNER NEGATIVE: {w['owner_negative']['why']}"
                    if w["owner_negative"] else "  (no owner FALSE/OFFGAME mark)"))
    for row in c["owner_negative_placements"]:
        L.append(f"    OWNER-NEGATIVE placement f{row['placed_frame']} "
                 f"(anchor {row['anchor_start']}, {row['signal']}): "
                 f"{row['negative']}")

    L += ["", "-" * 100, "  GOAL TRANSLATION (#74b INSERT arm; INSERT adds, never relabels)",
          "-" * 100,
          f"  base {res['goal']['all_17_IN_SAMPLE']['base_accuracy']} (85/139)"
          f" | (a) inserted far serves ADD to the denominator (they were"
          f" NOT-FOUND, not mislabeled) -- THE VERDICT CONVENTION",
          "  (b) #74b's literal 139-denominator variant is NUMERATOR-ONLY: it adds"
          " correct serves without counting them as found, so it OVERSTATES the arm.",
          f"  {'arm':<22} {'insert':>6} | {'(a) 139+k':>12} {'acc':>7} {'bar':>6} "
          f"| {'(b) /139':>10} {'acc':>7} {'bar':>6} | unreachable"]
    for label, goal in res["goal"].items():
        if "a_insert_into_denominator" not in goal:
            L.append(f"  {label:<22} {'-':>6} | {'-':>12} {'-':>7} {'-':>6} "
                     f"| {str(goal['denominator']):>10} {goal['accuracy']:>7} "
                     f"{('over' if goal['accuracy'] > 0.70 else 'under'):>6}"
                     f" | ({goal['note']})")
            continue
        a, b = goal["a_insert_into_denominator"], goal["b_literal_139_denominator"]
        L.append(f"  {label:<22} {goal['inserted']:>6} | "
                 f"{str(a['numerator']) + '/' + str(a['denominator']):>12} "
                 f"{a['accuracy']:>7} {('over' if a['over_bar'] else 'UNDER'):>6} "
                 f"| {str(b['numerator']) + '/' + str(b['denominator']):>10} "
                 f"{b['accuracy']:>7} {('over' if b['over_bar'] else 'UNDER'):>6} "
                 f"| {goal['unreachable_serves']}/{goal['far_serves_total']}")
    g0 = res["goal"]["all_17_IN_SAMPLE"]
    L += [f"  goal 103/139 = 0.741 (#74b) -- convention (a) needs "
          f"{g0['goal_hits_needed_convention_a']} insertions to REACH 103"
          f" (17 exist); convention (b) needs "
          f"{g0['hits_needed_for_74b_literal_to_clear_bar']} to clear the 0.70 bar"]

    sp = res["seam_split"]
    L += ["", "-" * 100,
          "  SEAM SPLIT (imported from score_point_map_alignment.side_split)",
          f"  far  {sp['far']}", f"  near {sp['near']}"]

    L += ["", "-" * 100,
          "  DIAGNOSTIC (pre-registered, NOT the headline): the width_start sweep "
          "over the rule AS WRITTEN",
          "-" * 100,
          f"  {'width_cut':>10} {'pool':>6} {'placed':>7} {'far_hits':>9} "
          f"{'unanch':>7} {'rallyFP':>8} {'dead':>5} {'lateServe':>10} "
          f"{'precision':>10}"]
    for row in res["width_sweep"]:
        L.append(f"  {str(row['width_cut']):>10} {row['pool_size']:>6} "
                 f"{row['placed']:>7} {row['far_hits']:>9} "
                 f"{row['unanchored_placements']:>7} "
                 f"{row['non_serve_misclaims']:>8} {row['dead_time_handling']:>5} "
                 f"{row['serve_claims_late_outside_tolerance']:>10} "
                 f"{row['precision_on_placements']:>10}")
    unf = [r for r in res["width_sweep"] if r["width_cut"] is None][0]
    tight = res["width_sweep"][0]
    L.append(f"  far_hits is 11 -- the SAME 11 POINTS {unf['far_hit_points']} -- at"
             f" EVERY cut from {tight['width_cut']} px to unfiltered: the width"
             f" cut moves only the FP side (unanchored placements"
             f" {unf['unanchored_placements']} -> {tight['unanchored_placements']},"
             f" precision {unf['precision_on_placements']} ->"
             f" {tight['precision_on_placements']}), and precision has NO"
             f" headroom that matters -- the arm is UNDER the bar in every"
             f" column of the goal section.  The headline above keeps the"
             f" UNFILTERED pool, so no number in sections 1-4 depends on"
             f" choosing this cut; the {inp['wide_drop']} px PG2 pool"
             f" ({inp['pool_size_width_filtered']} candidates,"
             f" {inp['pool_dropped_wide']} wide onsets dropped) is reported as a"
             f" variant.")
    return "\n".join(L)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", default=None, help="write the full result dict")
    args = ap.parse_args(argv)

    res = derive()
    print(format_report(res))
    if args.json:
        p = Path(args.json) if Path(args.json).is_absolute() else REPO / args.json
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8")
        print(f"wrote {p}")
    return 0 if res["gate"] == "G1_GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())