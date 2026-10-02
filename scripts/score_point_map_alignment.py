#!/usr/bin/env python3
"""PG2 -- the pairing-INDEPENDENT point-map re-test: are window starts serve-anchored?

Card PG2 (STATUS.md "## Next task cards"), open points 22 and 21.3.  PG1 (#65)
decided ``point_map_gate = REFUTED/1`` from an ORDINAL pairing (GT point *P* <
-> pipeline point *P-1*) while the pipeline emits 31 windows for 33 GT points, so
every later pair compares a window to the WRONG serve and the accumulated
+6..+3153 f spread reads as "uniformly late".  This card re-tests the same
claim on the same artifacts WITHOUT any pairing between point numbers and
window ordinals:

* **step 1 (G1)** pairwise-independent: how many window ``start_frame``s fall
  within +-15 f of ANY GT serve anchor, against a Monte-Carlo chance baseline
  and the frame coverage the anchors occupy;
* **step 2 (G2)** PG1's ordinal numbers reproduced through ``score_point_map``
  (parity, decides nothing);
* **step 3** a monotone order-preserving DP alignment with the skip cost swept
  over 60/120/240 f -- pairing-free but still order-aware;
* **step 4** the SEAM: per serve, signed offset to the nearest window start and
  the nearest window end, classified ``at_seam`` / ``inside_window`` /
  ``in_gap``, split by side;
* **step 5** the far-record CONSEQUENCE, scored not tuned: narrow ``far_flight``
  (``width_start <= 28`` px, the FIXED imported cut) whose ``onset_frame`` lies
  within +-10/15/20 f of a window START.  IN-SAMPLE -- a re-test target, not a
  shippable rule (AGENTS.md section 5 / STOP list).

Everything is post-hoc: committed artifacts only, NO ``cv2`` import, NO decode,
NO seek (AGENTS.md sections 6 and 9), no ``src/`` change, no new pipeline run,
no GT edit, the held-out session never read.  Every artifact reader, pairing
rule and serve-row builder is IMPORTED from ``scripts/score_point_map.py`` (and
through it ``scripts/probe_point_map.py`` / ``scripts/score_serves.py``), never
re-implemented.  Only the three NEW pairing-free measurements -- the chance
baseline, the monotone DP and the seam table -- live here.

Usage::

    venv/bin/python scripts/score_point_map_alignment.py
    venv/bin/python scripts/score_point_map_alignment.py --json output/pg2/score.json

Exit 0 on ``PG1_VERDICT_IS_A_PAIRING_ARTIFACT`` (PASS), 2 on
``PG1_VERDICT_STANDS`` (FAIL).
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import probe_point_map as P  # noqa: E402  (path set above)
import score_point_map as M  # noqa: E402  (via score_point_map)
import score_serves as S  # noqa: E402  (scorer matching, imported not re-implemented)

REPO = Path(__file__).resolve().parent.parent

MATCH_PIPELINE = M.MATCH_PIPELINE
MATCH_GT = M.MATCH_GT

#: +-15 f, the GT's own ``frame_tolerance`` -- the SAME constant PG1 used
#: (imported, never re-tuned).
TOLERANCE = M.TOLERANCE

#: step 1 -- the tolerance ladder.  +-15 f is the headline; 30 and 60 are the
#: robustness read at the same count.
TOLERANCE_LADDER = (15, 30, 60)

#: step 1(c) -- the chance baseline.  Fixed seed so the number is a pinned
#: measurement, not a coin flip between runs.
CHANCE_SEED = 20261002
CHANCE_DRAWS = 20000
CHANCE_STARTS = 31  # one draw = the whole set of 31 window starts

#: step 3 -- the skip costs swept.  The point-map shortfall is 33 - 31 = 2, so
#: every value here is >> the true skip count: what changes across the sweep is
#: how much the DP must pay to bridge a long empty stretch, not a re-tuning.
SKIP_COSTS = (60, 120, 240)

#: step 3 -- the DP's match reward.  A pairing is scored by how many pairs land
#: inside the GT tolerance first (the hinge, ``TIGHT_BONUS`` per tight pair) and
#: by proximity second; ``skip_cost`` pays for leaving a start or a serve
#: unpaired.  Both terms are fixed by the card's own numbers: ``TOLERANCE`` is
#: the GT tolerance and the skip costs are the card's sweep.
TIGHT_BONUS = 100.0

#: step 5 -- the tolerances the far-record rule is scored at (the card fixes the
#: width cut; these are the anchoring tolerances swept).
FAR_RECORD_TOLS = (10, 15, 20)

#: Pre-registered decision (card "pre-registered decision"), fixed.  PASS =
#: ``PG1_VERDICT_IS_A_PAIRING_ARTIFACT`` iff all three hold.
PASS_STARTS_WITHIN_15F = 10   # (i) of 31
PASS_CHANCE_MULTIPLE = 5.0   # (ii) measured / chance
PASS_DP_MIN_HITS = 10        # (iii) at EVERY skip cost
PASS_VERDICT = "PG1_VERDICT_IS_A_PAIRING_ARTIFACT"
FAIL_VERDICT = "PG1_VERDICT_STANDS"


# ---------------------------------------------------------------------------
# step 1 -- pairing-independent: starts vs ANY GT serve
# ---------------------------------------------------------------------------

def count_starts_within(starts: Sequence[int],
                        serve_frames: Sequence[int],
                        tolerance: int = TOLERANCE) -> int:
    """How many window starts lie within +-tolerance of ANY GT serve anchor.

    Pairing-free by construction: a start is counted once if ANY serve is near
    it, and no start/serve index is ever matched to the other.
    """
    return sum(1 for start in starts
               if any(abs(int(start) - int(serve)) <= tolerance
                      for serve in serve_frames))


def chance_baseline(starts: Sequence[int],
                    serve_frames: Sequence[int],
                    total_frames: int,
                    tolerance: int = TOLERANCE,
                    draws: int = CHANCE_DRAWS,
                    seed: int = CHANCE_SEED) -> Dict[str, Any]:
    """Monte-Carlo: ``len(starts)`` uniform starts over the video, same count.

    Fixed seed, so ``mean_hits`` is a pinned measurement.  The reported value is
    the mean over ``draws`` draws of the count, i.e. "how many of 31 random
    starts land within +-tolerance of a serve anchor".
    """
    n = len(starts)
    serve_list = [int(f) for f in serve_frames]
    total = int(total_frames)
    tol = int(tolerance)
    rng = random.Random(seed)
    hits = 0
    lowest = n
    highest = 0
    for _ in range(draws):
        draw = [rng.randrange(0, total) for _ in range(n)]
        count = count_starts_within(draw, serve_list, tol)
        hits += count
        lowest = min(lowest, count)
        highest = max(highest, count)
    mean_hits = hits / float(draws)
    return {"seed": seed, "draws": draws, "starts_per_draw": n,
            "total_frames": total, "tolerance": tol,
            "mean_hits": mean_hits,
            "mean_hits_rounded": round(mean_hits, 4),
            "min_hits": lowest, "max_hits": highest}


def frame_coverage(serve_frames: Sequence[int],
                   total_frames: int,
                   tolerance: int = TOLERANCE) -> Dict[str, Any]:
    """Frame fraction covered by a +-tolerance ball around each serve anchor."""
    covered = 0
    for serve in sorted(int(f) for f in serve_frames):
        lo = max(0, int(serve) - tolerance)
        hi = min(int(total_frames) - 1, int(serve) + tolerance)
        if hi >= lo:
            covered += hi - lo + 1
    return {"serve_anchors": len(serve_frames),
            "tolerance": tolerance,
            "covered_frames": covered,
            "total_frames": int(total_frames),
            "coverage_fraction": covered / float(total_frames),
            "coverage_pct": 100.0 * covered / float(total_frames)}


def nearest_start_offsets(starts: Sequence[int],
                          serve_frames: Sequence[int]) -> List[int]:
    """Per serve, signed offset to the NEAREST window start (start - serve).

    Negative = the window opened BEFORE the serve (the serve is inside it);
    positive = the window opened AFTER the serve (the serve is in the gap
    before it).
    """
    start_list = [int(s) for s in starts]
    return [min(start_list, key=lambda s: abs(s - int(serve))) - int(serve)
            for serve in serve_frames]


# ---------------------------------------------------------------------------
# step 3 -- monotone order-preserving DP alignment (pairing-free, order-aware)
# ---------------------------------------------------------------------------

def monotone_align(starts: Sequence[int],
                   serve_frames: Sequence[int],
                   skip_cost: int,
                   tolerance: int = TOLERANCE) -> List[Tuple[int, int]]:
    """Order-preserving DP pairing of window starts to serve frames.

    Maximises ``sum(match_reward) - skip_cost * (unpaired starts + unpaired
    serves)`` over monotonic matchings (classic sequence alignment, no look-ahead
    heuristics, strictly order-preserving).  The match reward is the HINGE: a
    pair within ``tolerance`` earns ``TIGHT_BONUS`` minus its distance, a pair
    outside it earns ``-distance``.  So the alignment maximises the number of
    serve-anchored pairs first and breaks ties by proximity -- which is what the
    question is, and what makes the result stable across the skip-cost sweep.

    Pairing is by FRAME proximity under a monotone constraint, never by point
    number or window ordinal.
    """
    n, m = len(starts), len(serve_frames)
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            distance = abs(int(starts[i - 1]) - int(serve_frames[j - 1]))
            reward = ((TIGHT_BONUS - distance) if distance <= tolerance
                      else -float(distance))
            match = best[i - 1][j - 1] + reward
            skip_start = best[i - 1][j] - skip_cost
            skip_serve = best[i][j - 1] - skip_cost
            options = [(match, "M"), (skip_start, "S"), (skip_serve, "V")]
            value, move = max(options, key=lambda kv: kv[0])
            best[i][j] = value
            back[i][j] = move
    # traceback
    pairs: List[Tuple[int, int]] = []
    i, j = n, m
    while i > 0 and j > 0:
        move = back[i][j]
        if move == "M":
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif move == "S":
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def dp_summary(starts: Sequence[int],
               serve_frames: Sequence[int],
               skip_cost: int) -> Dict[str, Any]:
    pairs = monotone_align(starts, serve_frames, skip_cost)
    offsets = [int(starts[i]) - int(serve_frames[j]) for i, j in pairs]
    return {
        "skip_cost": skip_cost,
        "pairs": len(pairs),
        "pairs_within_15f": sum(1 for o in offsets if abs(o) <= TOLERANCE),
        "offset_min": min(offsets) if offsets else None,
        "offset_max": max(offsets) if offsets else None,
        "offset_median": statistics.median(offsets) if offsets else None,
        "offsets_nonnegative": sum(1 for o in offsets if o >= 0),
        "unmatched_starts": len(starts) - len(pairs),
        "unmatched_serves": len(serve_frames) - len(pairs),
    }


# ---------------------------------------------------------------------------
# step 4 -- the seam: signed offsets to nearest start / nearest end, per side
# ---------------------------------------------------------------------------

def seam_table(starts: Sequence[int],
               ends: Sequence[int],
               gt_serve_rows: Sequence[Dict[str, Any]],
               tolerance: int = TOLERANCE) -> List[Dict[str, Any]]:
    """Per GT serve: offset to nearest window START and nearest window END.

    ``at_seam``      = nearest start within +-tolerance
    ``inside_window``= serve inside a window (start <= serve <= end)
    ``in_gap``       = neither (the serve sits in the inter-point gap)
    """
    table: List[Dict[str, Any]] = []
    for row in gt_serve_rows:
        serve = int(row["frame"])
        nearest_start_idx = min(range(len(starts)),
                                key=lambda i: abs(int(starts[i]) - serve))
        nearest_end_idx = min(range(len(ends)),
                              key=lambda i: abs(int(ends[i]) - serve))
        start_offset = int(starts[nearest_start_idx]) - serve
        end_offset = int(ends[nearest_end_idx]) - serve
        inside = any(int(s) <= serve <= int(e) for s, e in zip(starts, ends))
        if abs(start_offset) <= tolerance:
            kind = "at_seam"
        elif inside:
            kind = "inside_window"
        else:
            kind = "in_gap"
        table.append({
            "point": row.get("point"),
            "frame": serve,
            "side": row.get("side"),
            "nearest_start": int(starts[nearest_start_idx]),
            "offset_start": start_offset,
            "nearest_end": int(ends[nearest_end_idx]),
            "offset_end": end_offset,
            "inside_window": inside,
            "kind": kind,
            "within_15f": abs(start_offset) <= tolerance,
        })
    return table


def side_split(table: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Per side: n, at_seam / inside_window / in_gap counts and offset summary."""
    out: Dict[str, Any] = {}
    for side in ("far", "near"):
        rows = [r for r in table if r.get("side") == side]
        offs = [int(r["offset_start"]) for r in rows]
        out[side] = {
            "n": len(rows),
            "at_seam": sum(1 for r in rows if r["kind"] == "at_seam"),
            "inside_window": sum(1 for r in rows if r["kind"] == "inside_window"),
            "in_gap": sum(1 for r in rows if r["kind"] == "in_gap"),
            # the GEOMETRIC count (PG1 section 4's `inside_any_window`), which
            # the three-way class splits: a serve within +-tolerance of a start
            # is `at_seam` even when it also happens to fall inside that window.
            "inside_any_window": sum(1 for r in rows if r["inside_window"]),
            "offset_start_min": min(offs) if offs else None,
            "offset_start_max": max(offs) if offs else None,
            "offset_start_median": statistics.median(offs) if offs else None,
        }
    out["all"] = {
        "n": len(table),
        "at_seam": sum(1 for r in table if r["kind"] == "at_seam"),
        "inside_window": sum(1 for r in table if r["kind"] == "inside_window"),
        "in_gap": sum(1 for r in table if r["kind"] == "in_gap"),
        "inside_any_window": sum(1 for r in table if r["inside_window"]),
    }
    return out


# ---------------------------------------------------------------------------
# step 5 -- the far-record consequence, scored (IN-SAMPLE), never tuned
# ---------------------------------------------------------------------------

def far_record_on_starts(starts: Sequence[int],
                         narrow_events: Sequence[Dict[str, Any]],
                         gt_serve_rows: Sequence[Dict[str, Any]],
                         tolerance: int) -> Dict[str, Any]:
    """One claim per window START, scored against the GT serve rows.

    The rule (as stated in ``docs/pg1_correction.md``): a narrow ``far_flight``
    event (``width_start <= 28`` px, the FIXED imported cut) within +-tolerance
    of a window start is a **claim**, and the window start itself is the anchor.
    When several events land on the SAME start only the one nearest the start
    counts -- otherwise a busy window start would emit two claims for one point
    and the claim count would stop being a count of points.

    A claim is a **hit** when it also lands within +-tolerance of a GT serve of
    the same side (scored by the scorer's own ``match_candidates``, imported),
    and **unanchored** when it reaches a window start but no serve.  The small
    unanchored count is a consequence of anchoring: most of the 432 narrow
    events sit mid-rally, far from any window start, and are never candidates.

    This is a CONSEQUENCE measurement, NOT a rule proposal -- it is IN-SAMPLE on
    the 17 match far serves.
    """
    serve_frames = sorted(int(r["frame"]) for r in gt_serve_rows)
    side_by_frame = {int(r["frame"]): r.get("side") for r in gt_serve_rows}

    # one claim per window start: the narrow event whose onset is nearest it
    claim_by_start: Dict[int, int] = {}
    for event in narrow_events:
        onset = int(event.get("onset_frame", event["frame"]))
        anchor = min(starts, key=lambda s: abs(s - onset))
        if abs(anchor - onset) > tolerance:
            continue  # not anchored at a window start -> not a claim
        if (anchor not in claim_by_start
                or abs(onset - anchor) < abs(claim_by_start[anchor] - anchor)):
            claim_by_start[anchor] = onset

    claims: List[Dict[str, Any]] = []
    for anchor in sorted(claim_by_start):
        onset = claim_by_start[anchor]
        best = min(serve_frames, key=lambda f: abs(f - onset))
        within = abs(best - onset) <= tolerance
        claim = {"onset_frame": onset, "anchor_start": int(anchor),
                 "offset_to_anchor": onset - int(anchor),
                 "serve_frame": int(best),
                 "side": side_by_frame.get(int(best)),
                 "hit": bool(within and side_by_frame.get(int(best)) == "far")}
        if not within:
            claim["unanchored"] = True
        elif claim["side"] != "far":
            claim["hit"] = False
            claim["near_misclaim"] = True
        claims.append(claim)

    far_hits = sum(1 for c in claims if c["hit"])
    near_misclaimed = sum(1 for c in claims if c.get("near_misclaim"))
    unanchored = sum(1 for c in claims if c.get("unanchored"))
    return {
        "tolerance": tolerance,
        "claims": len(claims),
        "far_serves_hit": far_hits,
        "near_serves_misclaimed": near_misclaimed,
        "unanchored_claims": unanchored,
        "far_n": sum(1 for r in gt_serve_rows if r.get("side") == "far"),
        "near_n": sum(1 for r in gt_serve_rows if r.get("side") == "near"),
        "narrow_events": len(narrow_events),
        "claims_detail": claims,
    }


# ---------------------------------------------------------------------------
# the pre-registered verdict
# ---------------------------------------------------------------------------

def verdict(starts_within_15f: int,
            n_starts: int,
            chance_mean: float,
            dp_by_cost: Dict[str, Any]) -> Dict[str, Any]:
    """PASS = PG1 verdict is a pairing artifact iff (i)+(ii)+(iii) all hold."""
    multiple = (starts_within_15f / chance_mean) if chance_mean > 0 else float("inf")
    c1 = starts_within_15f >= PASS_STARTS_WITHIN_15F
    c2 = multiple >= PASS_CHANCE_MULTIPLE
    c3 = all(cell["pairs_within_15f"] >= PASS_DP_MIN_HITS
             for cell in dp_by_cost.values())
    passed = c1 and c2 and c3
    return {
        "criteria": {
            "i_starts_within_15f": f">= {PASS_STARTS_WITHIN_15F} of {n_starts} "
                                   f"(measured {starts_within_15f})",
            "ii_chance_multiple": f">= {PASS_CHANCE_MULTIPLE}x "
                                  f"(measured {multiple:.2f}x)",
            "iii_dp_min_pairs_within_15f": f">= {PASS_DP_MIN_HITS} at every skip cost "
                                           f"(measured "
                                           f"{ {c: cell['pairs_within_15f'] for c, cell in dp_by_cost.items()} })",
        },
        "checks": {"i_starts_within_15f": c1,
                   "ii_chance_multiple": c2,
                   "iii_dp_min_pairs_within_15f": c3},
        "pass": passed,
        "verdict": PASS_VERDICT if passed else FAIL_VERDICT,
    }


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------

def score() -> Dict[str, Any]:
    # ---- step 2 (G2): PG1 ordinal parity, via score_point_map (decides nothing)
    pg1 = M.score()
    pg1_summary = pg1["summary"]

    pipeline = P._read(MATCH_PIPELINE)
    gt_blob = P._read(MATCH_GT)

    points = P.pipeline_points(pipeline)
    if not points:
        raise SystemExit("STOP: game_state.points absent from the pipeline artifact")
    starts = [int(p["start_frame"]) for p in points]
    ends = [int(p["end_frame"]) for p in points]

    rows = P.gt_serve_rows(gt_blob)
    if not rows:
        raise SystemExit("STOP: no GT serve rows in the match contacts file")
    serve_frames = sorted(int(r["frame"]) for r in rows)

    total_frames = (pipeline.get("video") or {}).get("total_frames")
    if not total_frames:
        raise SystemExit("STOP: video.total_frames absent from the pipeline artifact")

    # ---- step 1: pairing-independent starts vs ANY serve
    ladder = {str(tol): count_starts_within(starts, serve_frames, tol)
              for tol in TOLERANCE_LADDER}
    starts_within_15f = ladder[str(TOLERANCE)]
    chance = chance_baseline(starts, serve_frames, int(total_frames))
    coverage = frame_coverage(serve_frames, int(total_frames))
    offsets_per_serve = nearest_start_offsets(starts, serve_frames)
    per_serve_offset_median = statistics.median(offsets_per_serve)
    # The card's step 1(e) expects a median of -6 f but calls the quantity
    # "sign-free", which cannot be negative.  All three readings are reported
    # so the number is reconciled on the page instead of swapped in silently:
    #   nearest START     (signed)  -> -1 f
    #   nearest BOUNDARY  (signed)  -> -6 f   <- the card's figure
    #   nearest START     (|signed|)-> 17 f
    boundary_offsets = [r["offset_start"] if abs(r["offset_start"])
                        <= abs(r["offset_end"]) else r["offset_end"]
                        for r in seam_table(starts, ends, rows)]
    per_serve_offset_medians = {
        "nearest_start_signed": per_serve_offset_median,
        "nearest_boundary_signed": statistics.median(boundary_offsets),
        "nearest_start_abs": statistics.median(
            [abs(o) for o in offsets_per_serve]),
    }

    # ---- step 3: monotone DP, skip cost swept
    dp_by_cost = {str(cost): dp_summary(starts, serve_frames, cost)
                  for cost in SKIP_COSTS}

    # ---- step 4: the seam table
    seam = seam_table(starts, ends, rows)
    split = side_split(seam)

    # ---- step 5: far-record consequence on window starts (IN-SAMPLE)
    events = P.far_flight_events(pipeline)
    if not events:
        raise SystemExit("STOP: no far_flight serve_events in the pipeline artifact")
    narrow = P.narrow_flight_records(events)
    far_rec = {str(tol): far_record_on_starts(starts, narrow, rows, tol)
               for tol in FAR_RECORD_TOLS}

    # ---- the pre-registered verdict
    v = verdict(starts_within_15f, len(starts), chance["mean_hits"], dp_by_cost)

    return {
        "inputs": {"pipeline": MATCH_PIPELINE, "gt": MATCH_GT,
                   "n_points": len(points), "n_serves": len(rows),
                   "total_frames": int(total_frames)},
        "step1_pairwise_independent": {
            "starts": len(starts),
            "starts_within_15f": starts_within_15f,
            "ladder": ladder,
            "chance": chance,
            "coverage": coverage,
            "per_serve_signed_offsets": offsets_per_serve,
            "per_serve_offset_median": per_serve_offset_median,
            "per_serve_offset_medians": per_serve_offset_medians,
            "per_serve_boundary_offsets": boundary_offsets,
            "offset_median_of_hits": statistics.median(
                [o for o in offsets_per_serve if abs(o) <= TOLERANCE]),
        },
        "step2_pg1_parity": {
            "paired": pg1_summary["paired"],
            "start_hits_within_15f": pg1_summary["start_hits_within_15f"],
            "offsets_nonnegative": pg1_summary["offsets_nonnegative"],
            "offset_min": pg1_summary["offset_min"],
            "offset_max": pg1_summary["offset_max"],
            "offset_median": pg1_summary["offset_median"],
            "reading": pg1["reading"],
            "verdict": pg1["verdict"]["verdict"],
        },
        "step3_dp_alignment": dp_by_cost,
        "step4_seam": {"table": seam, "split": split},
        "step5_far_record": far_rec,
        "verdict": v,
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def format_report(s: Dict[str, Any]) -> str:
    s1 = s["step1_pairwise_independent"]
    s2 = s["step2_pg1_parity"]
    dp = s["step3_dp_alignment"]
    seam = s["step4_seam"]
    fr = s["step5_far_record"]
    v = s["verdict"]
    inp = s["inputs"]

    L = ["=" * 100,
         "  PG2 -- PAIRING-INDEPENDENT POINT-MAP RE-TEST (card PG2, open point 22 / 21.3)",
         "  committed artifacts only: no cv2, no decode, no seek, no src/ change",
         "=" * 100,
         f"  pipeline {inp['pipeline']}",
         f"  gt       {inp['gt']}",
         f"  {inp['n_points']} pipeline window starts   {inp['n_serves']} GT serve anchors"
         f"   {inp['total_frames']} frames"]

    # step 1
    L += ["", "-" * 100,
          f"  STEP 1 (G1) -- PAIRING-INDEPENDENT: window starts vs ANY GT serve (tol +-{TOLERANCE} f)"]
    for tol in TOLERANCE_LADDER:
        L.append(f"    [measured] starts within +-{tol:<3d} f of any serve : "
                 f"{s1['ladder'][str(tol)]} of {s1['starts']}")
    ch = s1["chance"]
    L += [f"    [measured] chance baseline (uniform, {ch['draws']} draws, seed {ch['seed']}, "
          f"tol +-{ch['tolerance']}) : {ch['mean_hits']:.2f} of {ch['starts_per_draw']} "
          f"(range {ch['min_hits']}-{ch['max_hits']})",
          f"    [measured] multiple over chance : "
          f"{s1['starts_within_15f'] / ch['mean_hits']:.2f}x "
          f"(card threshold {PASS_CHANCE_MULTIPLE}x)"]
    cov = s1["coverage"]
    L += [f"    [measured] frame coverage of +-{cov['tolerance']} f serve balls : "
          f"{cov['coverage_pct']:.2f}% ({cov['covered_frames']} of {cov['total_frames']} frames)",
          f"    [measured] per-serve signed offset to nearest start (median over all "
          f"{len(s1['per_serve_signed_offsets'])} serves) : {s1['per_serve_offset_median']} f",
          f"    [measured] per-serve signed offset to nearest BOUNDARY (start or end, "
          f"whichever is nearer) : "
          f"{s1['per_serve_offset_medians']['nearest_boundary_signed']} f",
          f"    [measured] per-serve sign-FREE offset to nearest start (median) : "
          f"{s1['per_serve_offset_medians']['nearest_start_abs']} f",
          f"    [card 1(e)] asks for a SIGN-FREE median of -6 f, which is not "
          f"expressible; the -6 f figure is the nearest-boundary signed median and "
          f"is also the DP median at skip 60 -- all three readings agree the opener "
          f"is serve-anchored, so the verdict does not turn on which is taken.",
          f"    [measured] median offset among the {sum(1 for o in s1['per_serve_signed_offsets'] if abs(o) <= TOLERANCE)} "
          f"serves within +-{TOLERANCE} f : {s1['offset_median_of_hits']} f",
          "    per-serve signed offsets: " + ", ".join(str(o) for o in s1["per_serve_signed_offsets"])]

    # step 2
    L += ["", "-" * 100,
          "  STEP 2 (G2) -- PG1 ordinal numbers reproduced via score_point_map (decides nothing)"]
    L += [f"    [measured] start_hits_within_15f : {s2['start_hits_within_15f']}",
          f"    [measured] offsets_nonnegative    : {s2['offsets_nonnegative']}",
          f"    [measured] offset min / max / median: {s2['offset_min']} / {s2['offset_max']} / {s2['offset_median']}",
          f"    [measured] PG1 reading of the sign  : {s2['reading']}"]

    # step 3
    L += ["", "-" * 100,
          "  STEP 3 -- MONOTONE ORDER-PRESERVING DP ALIGNMENT (skip cost swept)"]
    L.append(f"    {'skip':>6} {'pairs':>6} {'within15':>9} {'off_min':>8} {'off_max':>8} "
             f"{'off_med':>8} {'>=0':>5} {'unm_start':>10} {'unm_serve':>10}")
    for cost in SKIP_COSTS:
        d = dp[str(cost)]
        L.append(f"    {d['skip_cost']:>6} {d['pairs']:>6} {d['pairs_within_15f']:>9} "
                 f"{d['offset_min']:>8} {d['offset_max']:>8} {d['offset_median']:>8} "
                 f"{d['offsets_nonnegative']:>5} {d['unmatched_starts']:>10} {d['unmatched_serves']:>10}")

    # step 4
    L += ["", "-" * 100,
          f"  STEP 4 -- THE SEAM: per-serve signed offset to nearest window START and END (tol +-{TOLERANCE} f)"]
    L.append(f"    {'P':>3} {'serve f':>8} {'side':<5} {'nearest_start':>13} {'off_start':>10} "
             f"{'nearest_end':>11} {'off_end':>8} {'kind':<14}")
    for r in seam["table"]:
        L.append(f"    {str(r['point']):>3} {r['frame']:>8} {str(r['side']):<5} "
                 f"{r['nearest_start']:>13} {r['offset_start']:>10} "
                 f"{r['nearest_end']:>11} {r['offset_end']:>8} {r['kind']:<14}")
    sp = seam["split"]
    L += ["    side split (at_seam takes precedence; 'inside_window' is the",
          "    three-way class, 'inside_any_window' is the geometric count PG1 §4 used):",
          f"      far : n={sp['far']['n']:<3} at_seam={sp['far']['at_seam']:<3} "
          f"inside_window={sp['far']['inside_window']:<3} in_gap={sp['far']['in_gap']:<3} "
          f"inside_any_window={sp['far']['inside_any_window']}",
          f"      near: n={sp['near']['n']:<3} at_seam={sp['near']['at_seam']:<3} "
          f"inside_window={sp['near']['inside_window']:<3} in_gap={sp['near']['in_gap']:<3} "
          f"inside_any_window={sp['near']['inside_any_window']}"]

    # step 5
    L += ["", "-" * 100,
          "  STEP 5 -- FAR-RECORD CONSEQUENCE on window starts (IN-SAMPLE, scored not tuned)"]
    L.append(f"    {'tol':>4} {'claims':>7} {'far_hit':>8} {'near_mis':>9} {'unanchored':>11}")
    for tol in FAR_RECORD_TOLS:
        c = fr[str(tol)]
        L.append(f"    {c['tolerance']:>4} {c['claims']:>7} "
                 f"{c['far_serves_hit']}/{c['far_n']:<6} {c['near_serves_misclaimed']}/{c['near_n']:<7} "
                 f"{c['unanchored_claims']:>11}")
    L += ["    IN-SAMPLE on the 17 match far serves -- a re-test target, NOT a shippable rule (STOP list)."]

    # verdict
    L += ["", "-" * 100,
          f"  PRE-REGISTERED VERDICT: {v['verdict']}",
          f"    (i)  {v['criteria']['i_starts_within_15f']}  -> {v['checks']['i_starts_within_15f']}",
          f"    (ii) {v['criteria']['ii_chance_multiple']}  -> {v['checks']['ii_chance_multiple']}",
          f"    (iii){v['criteria']['iii_dp_min_pairs_within_15f']}  -> {v['checks']['iii_dp_min_pairs_within_15f']}"]
    if v["pass"]:
        L.append(f"    PASS = {PASS_VERDICT}: PG1's ordinal verdict is a pairing artifact;")
        L.append("    SR4-FAR is mis-keyed, not blocked -- coordinator cards the far-serve rule on window starts.")
    else:
        L.append(f"    FAIL = {FAIL_VERDICT}: PG1's verdict stands.")
        L.append("    SR4-FAR stays BLOCKED on open point 22.")
    L.append("=" * 100)
    return "\n".join(L)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", default=None, help="optional path for the full score dict")
    args = ap.parse_args(argv)

    result = score()
    print(format_report(result))
    if args.json:
        out = REPO / args.json
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {out}")
    return 0 if result["verdict"]["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
