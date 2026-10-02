#!/usr/bin/env python3
"""PG1 -- the point-map scorer: is the pipeline's point map aligned to the GT?

Card PG1 (STATUS.md "## Next task cards"), open point 22 / 21.3.  This is a
MEASUREMENT card: it scores ``game_state.points`` starts against the owner's
existing per-point start frames -- the serve frames -- and puts the map behind
the card's pre-registered pass/fail gate.

Everything is post-hoc: committed artifacts only, NO ``cv2`` import, NO decode,
NO seek (AGENTS.md sections 6 and 9), no ``src/`` change, no new pipeline run,
no GT edit.  The loaders and the ordinal ``alignment`` logic are IMPORTED from
``scripts/probe_point_map.py`` (#64's committed output is the parity target,
gate G2), never re-implemented.

Anchor (card step 1, corrected by the owner 2026-10-02): in
``ground_truth/20260920_match_contacts.json`` every point carries exactly one
``serve`` contact and the serve IS that point's earliest contact, so the serve
frame (+-15 f by construction) is the owner-dictated point start.  Explicitly
NOT the anchor: ``points[].match_start_frame`` (all 33 are
``window_source: "episode_map_emission_window"`` + ``window_is_prediction:
true``, i.e. a pipeline prediction) and
``ground_truth/gt_point_start_end.txt`` (the game-state VIDEO's GT).

Gates / steps:

* **step 1** the anchor rule reproduces (one serve per point, serve earliest),
  else STOP;
* **G1** the metric run -- per-point signed offset ``pipeline start_frame -
  serve_frame``, offset min/max/median, ``offsets_nonnegative``, and
  ``start_hits_within_15f`` (the headline);
* **G2** parity with ``output/pm1/probe.json``'s ``alignment`` (paired count 31,
  ``gt_points_without_pipeline_point == [32, 33]``, identical offsets);
* **step 4** the #64 gap-side claim scored: serve frame inside ANY pipeline
  window, and inside the inter-point gap preceding the point that holds its own
  contacts.

Usage::

    venv/bin/python scripts/score_point_map.py
    venv/bin/python scripts/score_point_map.py --json output/pg1/score.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import probe_point_map as P  # noqa: E402  (path set above)

REPO = Path(__file__).resolve().parent.parent

MATCH_PIPELINE = P.MATCH_PIPELINE
MATCH_GT = P.MATCH_GT
#: #64's committed probe output -- the parity target for gate G2.  Never
#: re-tuned, only compared.
PM1_PROBE = "output/pm1/probe.json"

#: +-15 f, the GT's own per-contact tolerance (``frame_tolerance``), fixed by
#: the card and by the ground truth.
TOLERANCE = 15

#: Pre-registered decision (card "pre-registered decision"), fixed.
PASS_START_HITS = 20
PASS_OFFSETS_NONNEG = 31


# ---------------------------------------------------------------------------
# step 1 -- the anchor rule (STOP if it does not reproduce)
# ---------------------------------------------------------------------------

def serve_contacts(point: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The point's ``serve`` contacts (``action_token``/``action`` prefix)."""
    return [c for c in (point.get("contacts") or [])
            if str(c.get("action_token") or c.get("action") or "").startswith("serve")]


def check_anchor_rule(gt_blob: Dict[str, Any]) -> Dict[str, Any]:
    """One serve per point, and the serve is the point's earliest contact."""
    problems: List[Dict[str, Any]] = []
    for point in gt_blob.get("points") or []:
        serves = serve_contacts(point)
        label = point.get("point")
        if len(serves) != 1:
            problems.append({"point": label, "issue": "serve_count",
                             "n_serves": len(serves)})
            continue
        serve_frame = int(serves[0]["match_frame"])
        earliest = min(int(c["match_frame"]) for c in point["contacts"])
        if serve_frame != earliest:
            problems.append({"point": label, "issue": "serve_not_earliest",
                             "serve_frame": serve_frame, "earliest": earliest})
    return {"points": len(gt_blob.get("points") or []),
            "exceptions": problems,
            "pass": not problems}


# ---------------------------------------------------------------------------
# G1 -- the metric
# ---------------------------------------------------------------------------

def ordinal_pairs(points: List[Dict[str, Any]],
                  gt_serve_frames: Dict[int, int]) -> List[Dict[str, Any]]:
    """GT point ``P`` <-> pipeline point ``P-1`` (the card's ordinal pairing).

    This is #64's pairing, reproduced through ``probe_point_map``'s own
    ``alignment`` construction so gate G2 can compare offsets exactly.
    """
    out: List[Dict[str, Any]] = []
    for index, point in enumerate(points):
        gt_point = index + 1
        serve_frame = gt_serve_frames.get(gt_point)
        offset = (None if serve_frame is None
                  else int(point["start_frame"]) - int(serve_frame))
        out.append({
            "index": index,
            "gt_point": gt_point,
            "serve_frame": serve_frame,
            "pipeline_start_frame": int(point["start_frame"]),
            "pipeline_end_frame": int(point["end_frame"]),
            "offset": offset,
            "start_hit": (None if offset is None else abs(offset) <= TOLERANCE),
            "serve_inside_own_window": (None if serve_frame is None else
                                        int(point["start_frame"]) <= int(serve_frame)
                                        <= int(point["end_frame"])),
        })
    return out


def aggregate(pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Offset triple, ``offsets_nonnegative`` and ``start_hits_within_15f``."""
    offsets = [int(p["offset"]) for p in pairs if p["offset"] is not None]
    return {
        "paired": len(offsets),
        "offset_min": min(offsets) if offsets else None,
        "offset_max": max(offsets) if offsets else None,
        "offset_median": statistics.median(offsets) if offsets else None,
        "offsets_nonnegative": sum(1 for o in offsets if o >= 0),
        "start_hits_within_15f": sum(1 for o in offsets if abs(o) <= TOLERANCE),
        "tolerance": TOLERANCE,
    }


# ---------------------------------------------------------------------------
# step 4 -- the #64 claim scored: in-window vs in-gap
# ---------------------------------------------------------------------------

def gap_side_measure(points: List[Dict[str, Any]],
                     gt_blob: Dict[str, Any],
                     gt_serve_frames: Dict[int, int],
                     rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Per GT point: is its serve frame inside ANY window, and inside the gap
    preceding the point that holds its own contacts?"""
    gap_table = P.point_gap_table(points, rows)
    gaps = {row["index"]: row for row in gap_table}
    side_by_frame = {int(r["frame"]): r.get("side") for r in rows}

    def _in_any_gap(frame: int) -> bool:
        return any(row["gap_lo"] is not None
                   and int(row["gap_lo"]) <= frame <= int(row["gap_hi"])
                   for row in gap_table)
    per_point: List[Dict[str, Any]] = []
    for gt_point in sorted(gt_points_of(gt_blob)):
        serve_frame = gt_serve_frames.get(gt_point)
        entry: Dict[str, Any] = {"point": gt_point, "serve_frame": serve_frame}
        if serve_frame is None:
            entry["side"] = None
            per_point.append(entry)
            continue
        entry["side"] = side_by_frame.get(serve_frame)
        inside = P.containing(points, serve_frame)
        entry["inside_any_window"] = inside is not None
        entry["inside_any_window_index"] = inside
        # the point that HOLDS this GT point's own contacts = the pipeline point
        # paired by ordinal (P-1), the same vocabulary G2 pins.
        holder = gt_point - 1
        gap = gaps.get(holder)
        in_gap = (None if (gap is None or gap["gap_lo"] is None)
                  else bool(int(gap["gap_lo"]) <= serve_frame <= int(gap["gap_hi"])))
        entry["gap_before_holder_index"] = holder
        entry["gap_lo"] = None if gap is None else gap["gap_lo"]
        entry["gap_hi"] = None if gap is None else gap["gap_hi"]
        entry["inside_gap_before_holder"] = in_gap
        # #64's gap figure was "16 of 33 serves sit in inter-point gaps" -- ANY
        # gap, reported alongside the holder-specific one the card asks for.
        entry["inside_any_gap"] = _in_any_gap(serve_frame)
        per_point.append(entry)

    def _side_figure(side: str) -> Dict[str, Any]:
        sel = [e for e in per_point if e.get("side") == side]
        return {
            "n": len(sel),
            "inside_any_window": sum(1 for e in sel if e["inside_any_window"]),
            "inside_gap_before_holder": sum(1 for e in sel if e["inside_gap_before_holder"]),
            "inside_any_gap": sum(1 for e in sel if e.get("inside_any_gap")),
        }

    return {
        "per_point": per_point,
        "total": {
            "n": len(per_point),
            "inside_any_window": sum(1 for e in per_point if e["inside_any_window"]),
            "inside_gap_before_holder": sum(1 for e in per_point
                                            if e["inside_gap_before_holder"]),
            "inside_any_gap": sum(1 for e in per_point if e.get("inside_any_gap")),
        },
        "by_side": {"far": _side_figure("far"), "near": _side_figure("near")},
    }


def gt_points_of(gt_blob: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    return P.gt_point_frames(gt_blob)


# ---------------------------------------------------------------------------
# G2 -- parity with #64's committed output
# ---------------------------------------------------------------------------

def gate_g2(pairs: List[Dict[str, Any]],
            summary: Dict[str, Any]) -> Dict[str, Any]:
    probe_path = REPO / PM1_PROBE
    if not probe_path.exists():
        return {"pass": None, "reason": f"{PM1_PROBE} is absent"}
    pm1 = json.loads(probe_path.read_text(encoding="utf-8"))
    pm1_align = pm1.get("alignment") or []
    pm1_summary = pm1.get("alignment_summary") or {}
    mine = [(p["gt_point"], p["offset"]) for p in pairs if p["offset"] is not None]
    theirs = [(a["gt_point"], a["offset"]) for a in pm1_align
              if a.get("offset") is not None]
    if len(mine) != len(theirs):
        mismatches: List[Dict[str, Any]] = [
            {"length_mismatch": {"mine": len(mine), "pm1": len(theirs)}}]
    else:
        mismatches = [{"gt_point": g, "mine": m, "pm1": t}
                      for (g, m), (_, t) in zip(mine, theirs) if m != t]
    checks = {
        "paired_is_31": summary["paired"] == 31,
        "gt_points_without_pipeline_point": (
            summary["gt_points_without_pipeline_point"] == [32, 33]),
        "offsets_match_pm1": not mismatches,
    }
    return {"expected": {"paired": 31, "gt_points_without_pipeline_point": [32, 33]},
            "observed": {"paired": summary["paired"],
                         "gt_points_without_pipeline_point":
                             summary["gt_points_without_pipeline_point"],
                         "pm1_aligned_pairs": pm1_summary.get("aligned_pairs")},
            "mismatches": mismatches,
            "checks": checks,
            "pass": all(checks.values())}


# ---------------------------------------------------------------------------
# the pre-registered verdict
# ---------------------------------------------------------------------------

def verdict(summary: Dict[str, Any]) -> Dict[str, Any]:
    """PASS = >= 20 of 33 start hits within +-15 f AND 31 of 31 offsets >= 0."""
    ok = (summary["start_hits_within_15f"] >= PASS_START_HITS
          and summary["offsets_nonnegative"] == PASS_OFFSETS_NONNEG)
    return {
        "pass_criteria": {"start_hits_within_15f": f">= {PASS_START_HITS} of 33",
                          "offsets_nonnegative": f"== {PASS_OFFSETS_NONNEG} of 31 paired"},
        "observed": {"start_hits_within_15f": summary["start_hits_within_15f"],
                     "offsets_nonnegative": summary["offsets_nonnegative"]},
        "verdict": "PASS" if ok else f"FAIL=REFUTED/{summary['start_hits_within_15f']}",
    }


def reading(offsets: List[int]) -> str:
    """One of the three readings the card lists: one point behind / uniformly
    late / noise -- decided by the sign of the offset distribution."""
    if not offsets:
        return "noise"
    nonneg = sum(1 for o in offsets if o >= 0)
    if nonneg == len(offsets):
        return "uniformly late"
    if nonneg == 0:
        return "one point behind"
    return "noise"


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------

def score() -> Dict[str, Any]:
    pipeline = P._read(MATCH_PIPELINE)
    gt_blob = P._read(MATCH_GT)

    anchor = check_anchor_rule(gt_blob)
    if not anchor["pass"]:
        raise SystemExit(f"STOP: anchor rule does not reproduce: {anchor['exceptions']}")

    points = P.pipeline_points(pipeline)
    if not points:
        raise SystemExit("STOP: game_state.points absent from the pipeline artifact")

    gt_points = gt_points_of(gt_blob)
    if not gt_points:
        raise SystemExit("STOP: no GT points in the match contacts file")
    gt_serve_frames = {int(p): int(serve_contacts(gp)[0]["match_frame"])
                       for p, gp in gt_points.items()}

    rows = P.gt_serve_rows(gt_blob)
    if len(rows) != len(gt_points):
        raise SystemExit(f"STOP: {len(rows)} GT serve rows vs {len(gt_points)} GT points")

    pairs = ordinal_pairs(points, gt_serve_frames)
    summary = aggregate(pairs)
    unpaired = sorted(set(gt_points) - {p["gt_point"] for p in pairs})
    summary["gt_points_without_pipeline_point"] = unpaired
    summary["unpaired_serve_frames"] = {str(p): gt_serve_frames[p] for p in unpaired}
    summary["gt_points"] = len(gt_points)
    summary["pipeline_points"] = len(points)

    gap = gap_side_measure(points, gt_blob, gt_serve_frames, rows)
    g2 = gate_g2(pairs, summary)
    v = verdict(summary)

    return {"anchor": anchor,
            "pairs": pairs,
            "summary": summary,
            "gap_side": gap,
            "gate_g2": g2,
            "verdict": v,
            "reading": reading([int(p["offset"]) for p in pairs
                                if p["offset"] is not None])}


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def format_report(score: Dict[str, Any]) -> str:
    s = score["summary"]
    g = score["gap_side"]
    v = score["verdict"]
    g2 = score["gate_g2"]
    L = ["=" * 104,
         "  PG1 -- POINT-MAP SCORING (card PG1, open point 22 / 21.3)",
         "  committed artifacts only: no cv2, no decode, no seek, no src/ change",
         "=" * 104,
         f"  pipeline {MATCH_PIPELINE}",
         f"  gt       {MATCH_GT}",
         f"  anchor   every GT point's serve contact (earliest contact), "
         f"+-{TOLERANCE} f by construction",
         f"  pairing  ordinal: GT point P <-> pipeline point P-1"]
    L += ["", f"  step 1 anchor rule: {'REPRODUCED' if score['anchor']['pass'] else 'FAILED'}"
              f" over {score['anchor']['points']} GT points (one serve each, serve earliest)"]

    L += ["", "-" * 104,
          "  G1 -- per point: serve frame vs the pipeline point's start_frame",
          f"  {'P':>3} {'serve f':>9} {'pipe start':>10} {'pipe end':>9} "
          f"{'offset':>8} {'hit +-15':>9} {'serve in own win':>18}"]
    for p in score["pairs"]:
        L.append(f"  {p['gt_point']:>3} {p['serve_frame']:>9} "
                 f"{p['pipeline_start_frame']:>10} {p['pipeline_end_frame']:>9} "
                 f"{p['offset']:>8} {str(p['start_hit']):>9} "
                 f"{str(p['serve_inside_own_window']):>18}")
    for p, serve_frame in s["unpaired_serve_frames"].items():
        L.append(f"  {p:>3} {serve_frame:>9} {'-':>10} {'-':>9} "
                 f"{'-':>8} {'-':>9} {'no pipeline point':>18}")

    L += ["", f"    paired                          : {s['paired']} of {s['gt_points']} GT points",
          f"    offset min / max / median       : {s['offset_min']} / {s['offset_max']} / "
          f"{s['offset_median']}",
          f"    offsets_nonnegative              : {s['offsets_nonnegative']} of {s['paired']}",
          f"    start_hits_within_15f (HEADLINE) : {s['start_hits_within_15f']} of "
          f"{s['gt_points']} (need >= {PASS_START_HITS} for PASS)",
          f"    reading of the offset sign      : {score['reading']}"]

    L += ["", "-" * 104,
          f"  G2 (parity with {PM1_PROBE}, decides nothing) -- "
          f"{'PASS' if g2['pass'] else ('FAIL' if g2['pass'] is False else 'NOT RUN')}",
          f"    expected {g2['expected']}",
          f"    observed {g2['observed']}",
          f"    checks   {g2['checks']}",
          f"    mismatches {g2['mismatches']}"]
    if g2["pass"] is False:
        L.append("    GATE G2 FAILED -- the two tools disagree (report, do not re-tune)")

    L += ["", "-" * 104,
          "  step 4 -- the #64 claim scored: where does each point's serve frame sit?",
          f"  {'P':>3} {'serve f':>9} {'side':<5} {'in any window':>14} "
          f"{'in gap before holder':>22} {'in any gap':>12} {'gap span':>15}"]
    for e in g["per_point"]:
        gap_span = ("-" if e.get("gap_lo") is None
                    else f"[{e['gap_lo']}, {e['gap_hi']}]")
        L.append(f"  {e['point']:>3} {str(e['serve_frame']):>9} "
                 f"{str(e.get('side')):<5} {str(e.get('inside_any_window')):>14} "
                 f"{str(e.get('inside_gap_before_holder')):>22} "
                 f"{str(e.get('inside_any_gap')):>12} {gap_span:>15}")
    t, f_, n_ = g["total"], g["by_side"]["far"], g["by_side"]["near"]
    L += [f"    inside ANY pipeline window : {t['inside_any_window']} of {t['n']}"
              f"   (far {f_['inside_any_window']} of {f_['n']},"
              f" near {n_['inside_any_window']} of {n_['n']})",
          f"    inside the gap before holder: {t['inside_gap_before_holder']} of {t['n']}"
              f"   (far {f_['inside_gap_before_holder']} of {f_['n']},"
              f" near {n_['inside_gap_before_holder']} of {n_['n']})",
          f"    inside ANY inter-point gap  : {t['inside_any_gap']} of {t['n']}"
              f"   (far {f_['inside_any_gap']} of {f_['n']},"
              f" near {n_['inside_any_gap']} of {n_['n']})"]

    L += ["", "-" * 104,
          f"  PRE-REGISTERED VERDICT: {v['verdict']}",
          f"    {v['pass_criteria']}",
          f"    observed {v['observed']}"]
    if v["verdict"] == "PASS":
        L += ["    PASS -- the map's alignment is measured and an architect card for a"
              " corrected opener is justified"]
    else:
        L += ["    FAIL -- the map's STRUCTURE is the suspect (not its offset);"
              " SR4-FAR stays BLOCKED on open point 22"]
    L += ["=" * 104]
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
    return 0 if result["verdict"]["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())