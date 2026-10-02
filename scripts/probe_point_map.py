#!/usr/bin/env python3
"""PM1 -- the point-map probe: can SR4-FAR bypass ``game_state.points``?

Card PM1 (STATUS.md "## Next task cards"), open point 30.  The architect call
``docs/sr4_architect_call.md`` (#63) named the root cause of the far-serve
failure: ``game_state.points`` has 31 entries against the ground truth's 33 and
**0 of 17 far serves fall inside their own point window**, because a point's
``start_frame`` sits AFTER its own serve (the session-56 rally-onset
backdating).  This probe measures that claim from the committed artifacts and
answers ONE question -- is the far-serve record a one-rule job that bypasses the
point map, or is it blocked on open point 22 (episode->point map)?

Everything is post-hoc: committed artifacts only, NO ``cv2`` import, NO decode,
NO seek (AGENTS.md sections 6 and 9), no ``src/`` change, no new pipeline run.
The scorer's names are IMPORTED from ``scripts/score_serves.py`` and the
window-opener chasm threshold is IMPORTED from ``scripts/relabel_serves.py``
as ``GAP_SERVE_MIN`` (143, never re-tuned, never redefined here).

Gates, in order -- the probe STOPS on a failed gate:

* **G1** ``score_serves.py --detail`` must still read near 8/16, far 0/17,
  12 false serves (the #56/#62 baseline) and the probe's own recount must agree.
* **G2** the ``far_flight.width_start`` plateau must re-derive at 16/17 far
  claimed and 0/16 near misclaimed at EVERY cut in 26-32 px.

The far-side width cut is FIXED at 28 px for the bypass/binding test (imported
value, never re-tuned here); the other cuts are reported as sensitivity only and
decide nothing.

Usage::

    venv/bin/python scripts/probe_point_map.py
    venv/bin/python scripts/probe_point_map.py --json output/pm1/probe.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import score_serves as S  # noqa: E402  (path set above)
from relabel_serves import GAP_SERVE_MIN  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

MATCH_PIPELINE = "output/20260920_match_ari_joan_lost/pipeline_output.json"
MATCH_GT = "ground_truth/20260920_match_contacts.json"

#: The #56/#62 baseline, restated so the gate can be evaluated from inside the
#: probe and compared with what ``score_serves`` itself computed.
G1_BASELINE = {"near": (8, 16), "far": (0, 17), "false_positives": 12}

#: The far-side width cut.  FIXED by the card, never re-tuned here; the plateau
#: between 26 and 32 px is what makes it a cut rather than a knife edge.
WIDTH_CUT = 28
WIDTH_CUTS_SENSITIVITY = (26, 28, 30, 32)

#: Pre-registered decision (card "pre-registered decision").
PASS_UNBOUND_FAR_HITS = 15
PASS_UNBOUND_NEW_FP = 0
PASS_BOUND_FAR_HITS = 12
PASS_BOUND_FP = 3


# ---------------------------------------------------------------------------
# inputs (committed artifacts only)
# ---------------------------------------------------------------------------

def _read(rel: str) -> Dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def gt_serve_rows(gt_blob: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The 33 owner serve contacts as scorer rows (imported builder)."""
    return S.serve_rows_from_contact_gt(gt_blob, split_of=S.match_split)


def pipeline_points(pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
    points = (pipeline.get("game_state") or {}).get("points") or []
    return sorted(points, key=lambda p: int(p["start_frame"]))


def far_flight_events(pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
    events = [e for e in (pipeline.get("serve_events") or [])
              if e.get("type") == "far_flight"]
    return sorted(events, key=lambda e: int(e["frame"]))


def gt_point_frames(gt_blob: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    return {int(p["point"]): p for p in (gt_blob.get("points") or [])}


# ---------------------------------------------------------------------------
# window bookkeeping
# ---------------------------------------------------------------------------

def containing(points: Sequence[Dict[str, Any]], frame: int) -> Optional[int]:
    for index, point in enumerate(points):
        if int(point["start_frame"]) <= frame <= int(point["end_frame"]):
            return index
    return None


def first_start_after(points: Sequence[Dict[str, Any]], frame: int) -> Optional[int]:
    """Index of the first point whose ``start_frame`` is AFTER ``frame``."""
    for index, point in enumerate(points):
        if int(point["start_frame"]) > frame:
            return index
    return None


def gap_of(points: Sequence[Dict[str, Any]], index: int) -> Optional[Tuple[int, int]]:
    """``(gap_start, gap_end)`` = ``[prev_end, start]`` of point ``index``."""
    if index is None or index <= 0:
        return None
    return int(points[index - 1]["end_frame"]), int(points[index]["start_frame"])


# ---------------------------------------------------------------------------
# the emit rule (frame, side) -- never a point number in the unbound form
# ---------------------------------------------------------------------------

def narrow_flight_records(events: Sequence[Dict[str, Any]],
                          cut: int = WIDTH_CUT) -> List[Dict[str, Any]]:
    """Scorer-shaped ``(frame, side)`` records for every narrow ``far_flight``.

    The records are built by handing a records blob to the scorer's OWN
    ``serve_record_candidates`` builder (``point`` stays ``None`` -- the unbound
    form carries no point number at all).
    """
    blob = {"records": [{"t_contact_frame": int(e["frame"]), "side": "far",
                         "point": None}
                        for e in events
                        if float(e["width_start"]) <= float(cut)]}
    return S.serve_record_candidates(blob)


def bind_records(records: Sequence[Dict[str, Any]],
                 points: Sequence[Dict[str, Any]],
                 rule: str) -> List[Dict[str, Any]]:
    """Apply ONE binding rule; the surviving records carry a point index.

    ``contain``  -- (i) only records inside a window, bound to it.
    ``first_after`` -- (ii) bound to the first point whose start is after the
    event (records after the last start_frame do not bind).
    ``gap``     -- (iii) only records inside that point's ``[prev_end, start]``
    gap, bound to it.
    """
    out: List[Dict[str, Any]] = []
    for record in records:
        frame = int(record["frame"])
        if rule == "contain":
            index = containing(points, frame)
            if index is None:
                continue
        elif rule == "first_after":
            index = first_start_after(points, frame)
            if index is None:
                continue
        elif rule == "gap":
            index = first_start_after(points, frame)
            span = gap_of(points, index)
            if span is None or not (span[0] <= frame < span[1]):
                continue
        else:
            raise ValueError(f"unknown binding rule {rule!r}")
        bound = dict(record)
        bound["point"] = index
        out.append(bound)
    return out


# ---------------------------------------------------------------------------
# scoring helpers (every name from ``score_serves``, none re-implemented)
# ---------------------------------------------------------------------------

def score_records(gt_rows: Sequence[Dict[str, Any]],
                  records: Sequence[Dict[str, Any]],
                  gt_contacts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Far/near hits, unmatched records and the SR1 false-emission taxonomy."""
    match = S.match_candidates(gt_rows, records, require_side=True)
    far_rows = {i for i, g in enumerate(gt_rows) if g.get("side") == "far"}
    near_rows = {i for i, g in enumerate(gt_rows) if g.get("side") == "near"}
    far_hits = sum(1 for e in match["matched"] if e["gt"] in far_rows)
    near_hits = sum(1 for e in match["matched"] if e["gt"] in near_rows)
    fps = S.classify_false_positives(records, match["unmatched_candidates"],
                                     gt_contacts)
    kinds: Dict[str, int] = {}
    for row in fps:
        kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
    bound_points = {r["point"] for r in records if r.get("point") is not None}
    # A record is a "false SERVE" in the narrow sense when it sits on a rally
    # contact that is not a serve; the wide sense counts every unmatched record.
    rally_kinds = ("rally_contact_mislabeled", "serve_outside_tolerance")
    return {
        "records": len(records),
        "far_hits": far_hits,
        "near_hits": near_hits,
        "far_n": len(far_rows),
        "near_n": len(near_rows),
        "unmatched_records": len(fps),
        "false_serves_narrow": sum(v for k, v in kinds.items() if k in rally_kinds),
        "fp_kinds": kinds,
        "points_covered": len(bound_points),
    }


# ---------------------------------------------------------------------------
# step 1 -- where does each serve sit relative to the pipeline point map
# ---------------------------------------------------------------------------

def serve_offsets(gt_rows: Sequence[Dict[str, Any]],
                  points: Sequence[Dict[str, Any]],
                  gt_points: Dict[int, Dict[str, Any]],
                  total_frames: Optional[int]) -> List[Dict[str, Any]]:
    """Per-serve row: nearest window, signed offset, inside-any, own-GT window."""
    serve_frames = sorted(int(g["frame"]) for g in gt_rows)
    rows: List[Dict[str, Any]] = []
    for row in gt_rows:
        frame = int(row["frame"])
        nearest = min(
            points,
            key=lambda p: min(abs(frame - int(p["start_frame"])),
                              abs(frame - int(p["end_frame"]))))
        inside = containing(points, frame)
        # the GT point's OWN implied window: from its serve to the next GT serve
        own = gt_points.get(int(row["point"])) if row.get("point") else None
        idx = serve_frames.index(frame)
        own_end = (serve_frames[idx + 1] - 1 if idx + 1 < len(serve_frames)
                   else (total_frames - 1 if total_frames else None))
        own_span = None if own_end is None else [frame, own_end]
        after = first_start_after(points, frame)
        rows.append({
            "point": row.get("point"),
            "frame": frame,
            "side": row.get("side"),
            "split": row.get("split"),
            "nearest_window": [int(nearest["start_frame"]), int(nearest["end_frame"])],
            "nearest_window_index": points.index(nearest),
            "offset_start_minus_serve": int(nearest["start_frame"]) - frame,
            "inside_any_window": inside is not None,
            "inside_index": inside,
            "own_gt_window": own_span,
            "inside_own_gt_window": (None if own_span is None
                                      else own_span[0] <= frame <= own_span[1]),
            "gt_contacts_in_own_point": (None if own is None
                                         else len(own.get("contacts") or [])),
            "first_start_after_index": after,
            "bound_window_contains_contacts": (
                None if (after is None or own is None) else
                bool(any(int(p["start_frame"]) <= int(c["match_frame"]) <= int(p["end_frame"])
                         for c in (own.get("contacts") or [])
                         for p in [points[after]]))),
            "in_frame_range": (None if total_frames is None else 0 <= frame < total_frames),
        })
    return rows


def point_gap_table(points: Sequence[Dict[str, Any]],
                    gt_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per pipeline point: the inter-point gap and whether a GT serve is in it."""
    serves = sorted((int(g["frame"]), g.get("point"), g.get("side")) for g in gt_rows)
    table: List[Dict[str, Any]] = []
    for index, point in enumerate(points):
        start, end = int(point["start_frame"]), int(point["end_frame"])
        if index == 0:
            gap_lo, gap_hi, gap = None, None, None
        else:
            gap_lo = int(points[index - 1]["end_frame"])
            gap_hi = start
            gap = gap_hi - gap_lo
        inside = [s for s in serves if gap_lo is not None and gap_lo <= s[0] <= gap_hi]
        table.append({
            "index": index,
            "start_frame": start,
            "end_frame": end,
            "n_actions": point.get("n_actions"),
            "gap_lo": gap_lo,
            "gap_hi": gap_hi,
            "gap": gap,
            "gap_reaches_chasm": (None if gap is None else bool(gap >= GAP_SERVE_MIN)),
            "serves_in_gap": [s[0] for s in inside],
            "n_serves_in_gap": len(inside),
        })
    return table


# ---------------------------------------------------------------------------
# G1 / G2
# ---------------------------------------------------------------------------

def gate_g1() -> Dict[str, Any]:
    report = S.run(only_session="match_20260920", only_stream="production")
    stream = report["sessions"]["match_20260920"]["streams"]["production"]
    by_side = stream["by_side"]
    observed = {
        "near": (by_side["near"]["hits"], by_side["near"]["gt_serves"]),
        "far": (by_side["far"]["hits"], by_side["far"]["gt_serves"]),
        "false_positives": stream["overall"]["false_positives"],
    }
    checks = {
        "near": observed["near"] == G1_BASELINE["near"],
        "far": observed["far"] == G1_BASELINE["far"],
        "false_positives": observed["false_positives"] == G1_BASELINE["false_positives"],
        "scorer_gate": bool(report["gate"]["pass"]),
    }
    return {"expected": {"near": "%d/%d" % G1_BASELINE["near"],
                         "far": "%d/%d" % G1_BASELINE["far"],
                         "false_positives": G1_BASELINE["false_positives"]},
            "observed": {"near": "%d/%d" % observed["near"],
                         "far": "%d/%d" % observed["far"],
                         "false_positives": observed["false_positives"]},
            "checks": checks, "pass": all(checks.values())}


def width_bands(rows: Sequence[Dict[str, Any]],
                events: Sequence[Dict[str, Any]],
                tolerance: int = S.DEFAULT_TOLERANCE) -> Dict[int, List[float]]:
    """``width_start`` of every ``far_flight`` within +-tolerance of each serve."""
    bands: Dict[int, List[float]] = {}
    for row in rows:
        frame = int(row["frame"])
        bands[frame] = sorted(float(e["width_start"]) for e in events
                              if abs(int(e["frame"]) - frame) <= tolerance)
    return bands


def gate_g2(rows: Sequence[Dict[str, Any]],
            events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    bands = width_bands(rows, events)
    per_cut: Dict[str, Any] = {}
    for cut in WIDTH_CUTS_SENSITIVITY:
        far_claimed = sum(1 for row in rows
                          if row["side"] == "far" and any(w <= cut for w in bands[row["frame"]]))
        near_misclaimed = sum(1 for row in rows
                              if row["side"] == "near" and any(w <= cut for w in bands[row["frame"]]))
        per_cut[str(cut)] = {"far_claimed": far_claimed, "near_misclaimed": near_misclaimed}
    far_widths = [max(bands[int(r["frame"])]) for r in rows
                  if r["side"] == "far" and bands[int(r["frame"])]]
    near_widths = [(r["point"], bands[int(r["frame"])]) for r in rows
                   if r["side"] == "near" and bands[int(r["frame"])]]
    far_n = sum(1 for r in rows if r["side"] == "far")
    near_n = sum(1 for r in rows if r["side"] == "near")
    checks = {c: (v["far_claimed"] == far_n - 1 and v["near_misclaimed"] == 0)
              for c, v in per_cut.items()}
    return {"far_n": far_n, "near_n": near_n,
            "far_widths_with_events": far_widths,
            "far_width_min": min(far_widths), "far_width_max": max(far_widths),
            "near_widths_with_events": near_widths,
            "per_cut": per_cut, "checks": checks,
            "pass": all(checks.values())}


# ---------------------------------------------------------------------------
# the pre-registered verdict
# ---------------------------------------------------------------------------

def verdict(unbound: Dict[str, Any],
            bound: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    unbound_ok = (unbound["far_hits"] >= PASS_UNBOUND_FAR_HITS
                  and unbound["false_serves_narrow"] <= PASS_UNBOUND_NEW_FP
                  and unbound["near_hits"] == 0)
    per_rule = {name: {
        "far_hits": s["far_hits"],
        "false_positives": s["false_serves_narrow"],
        "records": s["records"],
        "points_covered": s["points_covered"],
        "passes": (s["far_hits"] >= PASS_BOUND_FAR_HITS
                   and s["false_serves_narrow"] <= PASS_BOUND_FP),
    } for name, s in bound.items()}
    bound_ok = [n for n, v in per_rule.items() if v["passes"]]
    passed = bool(unbound_ok and bound_ok)
    return {"unbound": unbound_ok, "per_rule": per_rule, "passing_rules": bound_ok,
            "verdict": "PASS=bypass" if passed else "FAIL=blocked"}


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def format_report(probe: Dict[str, Any]) -> str:
    L = ["=" * 108,
         "  PM1 -- THE POINT-MAP PROBE (card PM1, open point 30)",
         "  committed artifacts only: no cv2, no decode, no seek, no src/ change",
         "=" * 108,
         f"  pipeline {MATCH_PIPELINE}",
         f"  gt       {MATCH_GT}",
         f"  width cut FIXED at {WIDTH_CUT} px (plateau 26-32); GAP_SERVE_MIN imported "
         f"= {GAP_SERVE_MIN}"]

    g1 = probe["gates"]["g1"]
    L += ["", "-" * 108,
          f"  GATE G1 (score_serves baseline reproduction) -- {'PASS' if g1['pass'] else 'FAIL'}",
          f"    expected {g1['expected']}",
          f"    observed {g1['observed']}",
          f"    checks   {g1['checks']}"]
    if not g1["pass"]:
        L += ["    GATE G1 FAILED -- STOP (do not proceed)"]
        return "\n".join(L)

    counts = probe["counts"]
    L += ["", f"  pipeline points: {counts['pipeline_points']}   gt points: {counts['gt_points']}"
          f"   gt serves: {counts['gt_serves']} (far {counts['far_n']} / near {counts['near_n']})"]

    L += ["", "-" * 108,
          "  STEP 1b/1d -- every GT serve vs the pipeline point map",
          f"  {'P':>3} {'frame':>7} {'side':<5} {'split':<9} {'nearest window':>17} "
          f"{'start-serve':>12} {'in any':>7} {'own GT win':>12} {'in own':>7} {'gap->':>6}"]
    for row in probe["serves"]:
        own = "-" if row["own_gt_window"] is None else str(row["own_gt_window"])
        after = "-" if row["first_start_after_index"] is None else str(row["first_start_after_index"])
        L.append(f"  {str(row['point']):>3} {row['frame']:>7} {row['side']:<5} "
                 f"{row['split'] or '?':<9} {str(row['nearest_window']):>17} "
                 f"{row['offset_start_minus_serve']:>12} "
                 f"{str(row['inside_any_window']):>7} {own:>12} "
                 f"{str(row['inside_own_gt_window']):>7} {after:>6}")
    L += [f"    inside ANY pipeline window : {counts['serves_inside_any_window']} of {counts['gt_serves']}"
          f"   (far {counts['far_inside_any']} of {counts['far_n']},"
          f" near {counts['near_inside_any']} of {counts['near_n']})",
          f"    inside OWN GT window      : {counts['serves_inside_own_gt_window']}"
          f" of {counts['gt_serves']} (GT window = serve .. next GT serve)",
          f"    bound-window contains the whole GT contact set: "
          f"{counts['bound_window_contains_contacts']} of {counts['gt_serves']}"]
    if counts["frames_out_of_range"]:
        L += [f"    !! serves outside the artifact frame range: {counts['frames_out_of_range']}"]

    L += ["", "-" * 108,
          "  STEP 1c -- pipeline point windows vs GT point contact frames, side by side",
          f"  {'idx':>3} {'start':>7} {'end':>7} {'nact':>5} | "
          f"{'gtP':>4} {'serve_f':>7} {'gt range':>15} {'offset':>8} {'in':>3}"]
    for pair in probe["alignment"]:
        if pair["pipeline"] is None:
            L.append(f"  {pair['index']:>3} {'-':>7} {'-':>7} {'-':>5} | "
                     f"{str(pair['gt_point']):>4} {'-':>7} "
                     f"{str(pair['gt_range']):>15} {'-':>8} {'-':>3}")
            continue
        p = pair["pipeline"]
        serve_frame = ("-" if pair["serve_frame"] is None else str(pair["serve_frame"]))
        offset = ("-" if pair["offset"] is None else str(pair["offset"]))
        inside = "-" if pair["inside"] is None else str(pair["inside"])
        L.append(f"  {pair['index']:>3} {p['start_frame']:>7} {p['end_frame']:>7} "
                 f"{str(p['n_actions']):>5} | {pair['gt_point']:>4} {serve_frame:>7} "
                 f"{str(pair['gt_range']):>15} {offset:>8} {inside:>3}")

    L += ["", "-" * 108,
          "  STEP 1e -- inter-point gaps (start_frame - previous end_frame) and GT serves in them",
          f"  {'idx':>3} {'start':>7} {'end':>7} {'gap':>7} {'>=GAP_SERVE_MIN':>16} "
          f"{'serves in gap':>32}"]
    for row in probe["gaps"]:
        serves = ",".join(str(f) for f in row["serves_in_gap"]) or "-"
        L.append(f"  {row['index']:>3} {row['start_frame']:>7} {row['end_frame']:>7} "
                 f"{str(row['gap']):>7} {str(row['gap_reaches_chasm']):>16} {serves:>32}")
    L.append(f"    gaps holding >= 1 GT serve: {probe['gap_summary']['gaps_with_serve']} of "
             f"{probe['gap_summary']['gaps']};  serves inside a gap: "
             f"{probe['gap_summary']['serves_in_gaps']} of {counts['gt_serves']}")

    g2 = probe["gates"]["g2"]
    L += ["", "-" * 108,
          f"  GATE G2 (width plateau, re-derived, decides nothing) -- {'PASS' if g2['pass'] else 'FAIL'}",
          f"    far widths at the {g2['far_n']} far serves with an event: "
          f"{g2['far_width_min']:.0f}-{g2['far_width_max']:.0f} px "
          f"(n={len(g2['far_widths_with_events'])})",
          f"    near widths with an event: {g2['near_widths_with_events']}",
          "    cut | far claimed | near misclaimed"]
    for cut, cell in sorted(g2["per_cut"].items(), key=lambda kv: int(kv[0])):
        L.append(f"    {cut:>3} | {cell['far_claimed']:>11} | {cell['near_misclaimed']:>15}")
    if not g2["pass"]:
        L += ["    GATE G2 FAILED -- STOP (do not proceed)"]
        return "\n".join(L)

    unbound = probe["bypass"]["unbound"]
    L += ["", "-" * 108,
          "  STEP 4 -- BYPASS TEST: unbound (frame, side) records, then one binding rule at a time",
          "  (the width cut is FIXED at 28 px; other cuts are sensitivity only and decide nothing)"]
    for label, cell, records in probe["bypass"]["rows"]:
        L.append(f"    {label:<34} records={cell['records']:<5} far hits={cell['far_hits']:>2}/17"
                 f"  near hits={cell['near_hits']:>2}/16  unmatched records={cell['unmatched_records']:<5}"
                 f" false serves={cell['false_serves_narrow']:<4} points covered={cell['points_covered']}")
        L.append(f"    {'':<34} fp kinds: {cell['fp_kinds']}")
    L += ["", "    sensitivity (other plateau cuts, unbound form only, decide nothing):"]
    for line in probe["bypass"]["sensitivity"]:
        L.append(f"      cut {line['cut']:>3}: records={line['records']:<5} far hits={line['far_hits']:>2}/17"
                 f"  near hits={line['near_hits']:>2}/16  false serves={line['false_serves_narrow']}")

    v = probe["verdict"]
    L += ["", "-" * 108,
          f"  PRE-REGISTERED VERDICT: {v['verdict']}",
          f"    unbound far hits {unbound['far_hits']}/17 (>= {PASS_UNBOUND_FAR_HITS} required), "
          f"new false serves {unbound['false_serves_narrow']} (<= {PASS_UNBOUND_NEW_FP} required), "
          f"near misclaims {unbound['near_hits']} -> {'ok' if v['unbound'] else 'NOT ok'}",
          "    binding rules (need >= 12/17 far hits and <= 3 false positives):"]
    for name, cell in sorted(v["per_rule"].items()):
        L.append(f"      {name:<12} far hits {cell['far_hits']:>2}/17  false positives "
                 f"{cell['false_positives']:<4} records {cell['records']:<5} points covered "
                 f"{cell['points_covered']:<3} -> {'passes' if cell['passes'] else 'fails'}")
    L += ["=" * 108]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# probe
# ---------------------------------------------------------------------------

def run() -> Dict[str, Any]:
    pipeline = _read(MATCH_PIPELINE)
    gt_blob = _read(MATCH_GT)

    points = pipeline_points(pipeline)
    if not points:
        raise SystemExit("STOP: game_state.points absent from the pipeline artifact")
    events = far_flight_events(pipeline)
    missing_width = [e for e in events if e.get("width_start") is None]
    if missing_width:
        raise SystemExit(f"STOP: {len(missing_width)} far_flight events without width_start")

    rows = gt_serve_rows(gt_blob)
    gt_points = gt_point_frames(gt_blob)
    total_frames = (pipeline.get("video") or {}).get("total_frames")
    gt_contacts = S.contact_gt_events(gt_blob)
    missing_frames = [r["frame"] for r in rows if not r.get("frame")]
    if missing_frames:
        raise SystemExit(f"STOP: GT serve frames absent: {missing_frames}")
    out_of_range = [r["frame"] for r in rows
                    if total_frames is not None and not 0 <= int(r["frame"]) < int(total_frames)]

    probe: Dict[str, Any] = {"gates": {"g1": gate_g1()}}
    serves = serve_offsets(rows, points, gt_points, total_frames)
    far_n = sum(1 for r in rows if r["side"] == "far")
    near_n = sum(1 for r in rows if r["side"] == "near")
    probe["counts"] = {
        "pipeline_points": len(points),
        "gt_points": len(gt_points),
        "gt_serves": len(rows),
        "far_n": far_n,
        "near_n": near_n,
        "serves_inside_any_window": sum(1 for r in serves if r["inside_any_window"]),
        "far_inside_any": sum(1 for r in serves if r["side"] == "far" and r["inside_any_window"]),
        "near_inside_any": sum(1 for r in serves if r["side"] == "near" and r["inside_any_window"]),
        "serves_inside_own_gt_window": sum(1 for r in serves
                                           if r["inside_own_gt_window"]),
        "bound_window_contains_contacts": sum(1 for r in serves
                                              if r["bound_window_contains_contacts"]),
        "frames_out_of_range": out_of_range,
    }
    probe["serves"] = serves

    # 1c: ordinal alignment, pipeline point i against GT point i+1 (a LABEL for
    # the reader, never used for scoring -- the GT point number and the pipeline
    # point index are not the same vocabulary).
    ordered_serves = sorted(rows, key=lambda r: int(r["frame"]))
    alignment = []
    for index, point in enumerate(points):
        gt_point = gt_points.get(index + 1)
        if gt_point is None:
            alignment.append({"index": index, "pipeline": point, "gt_point": None,
                              "serve_frame": None, "gt_range": None,
                              "offset": None, "inside": None})
            continue
        serve_frame = None
        serve_row = next((r for r in ordered_serves
                          if r.get("point") == index + 1), None)
        if serve_row is not None:
            serve_frame = int(serve_row["frame"])
        alignment.append({
            "index": index, "pipeline": point, "gt_point": index + 1,
            "serve_frame": serve_frame,
            "gt_range": gt_point.get("match_frame_range"),
            "offset": (None if serve_frame is None else int(point["start_frame"]) - serve_frame),
            "inside": (None if serve_frame is None else
                       int(point["start_frame"]) <= serve_frame <= int(point["end_frame"])),
        })
    probe["alignment"] = alignment
    # The #63 wording, "0 of 17 far serves fall inside their OWN point window",
    # read on the ORDINAL pairing (pipeline point i <-> GT point i+1): the
    # architect's claim is a claim about each point's OWN window, not about any
    # window, so this is the count that reproduces it.
    far_by_point = {int(r["point"]): int(r["frame"]) for r in rows
                    if r["side"] == "far" and r.get("point") is not None}
    own_aligned_far = [(p, f) for p, f in sorted(far_by_point.items())
                       if p - 1 < len(points)
                       and int(points[p - 1]["start_frame"]) <= f <= int(points[p - 1]["end_frame"])]
    probe["alignment_summary"] = {
        "aligned_pairs": sum(1 for a in alignment if a["serve_frame"] is not None),
        "own_serve_inside_aligned_window": sum(1 for a in alignment if a["inside"]),
        "own_aligned_far_pairs": sum(1 for p, f in far_by_point.items() if p - 1 < len(points)),
        "own_aligned_far_inside": len(own_aligned_far),
        "own_aligned_far_inside_points": [p for p, _ in own_aligned_far],
        "offset_min": min([a["offset"] for a in alignment if a["offset"] is not None],
                          default=None),
        "offset_max": max([a["offset"] for a in alignment if a["offset"] is not None],
                          default=None),
        "gt_points_without_pipeline_point": sorted(
            set(gt_points) - {a["index"] + 1 for a in alignment}),
        "gt_points_without_a_serve_contact": sorted(
            p for p, gp in gt_points.items()
            if not any(str(c.get("action_token") or c.get("action") or "").startswith("serve")
                       for c in (gp.get("contacts") or []))),
    }

    gaps = point_gap_table(points, rows)
    probe["gaps"] = gaps
    probe["gap_summary"] = {
        "gaps": sum(1 for g in gaps if g["gap"] is not None),
        "gaps_with_serve": sum(1 for g in gaps if g["n_serves_in_gap"]),
        "serves_in_gaps": sum(g["n_serves_in_gap"] for g in gaps),
        "gaps_reaching_chasm": sum(1 for g in gaps if g["gap_reaches_chasm"]),
    }

    probe["gates"]["g2"] = gate_g2(rows, events)

    # step 4: the bypass test
    records = narrow_flight_records(events)
    unbound = score_records(rows, records, gt_contacts)
    bound_scores = {rule: score_records(rows, bind_records(records, points, rule), gt_contacts)
                    for rule in ("contain", "first_after", "gap")}
    probe["bypass"] = {
        "cut": WIDTH_CUT,
        "far_flight_events": len(events),
        "unbound": unbound,
        "rows": [
            ("UNBOUND (frame, side) only", unbound, records),
            ("(i) bind: window CONTAINS", bound_scores["contain"],
             bind_records(records, points, "contain")),
            ("(ii) bind: first start_frame after", bound_scores["first_after"],
             bind_records(records, points, "first_after")),
            ("(iii) bind: gap [prev_end, start]", bound_scores["gap"],
             bind_records(records, points, "gap")),
        ],
        "sensitivity": [
            dict(cut=cut, **score_records(rows, narrow_flight_records(events, cut), gt_contacts))
            for cut in WIDTH_CUTS_SENSITIVITY
        ],
    }
    probe["verdict"] = verdict(unbound, bound_scores)
    return probe


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", default=None, help="optional path for the full probe dict")
    args = ap.parse_args(argv)

    probe = run()
    print(format_report(probe))
    if args.json:
        out = REPO / args.json
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(probe, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {out}")
    return 0 if probe["verdict"]["verdict"] == "PASS=bypass" else 2


if __name__ == "__main__":
    raise SystemExit(main())