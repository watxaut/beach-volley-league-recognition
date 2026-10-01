#!/usr/bin/env python3
"""S3 -- pass-2 side-switch / squad layer (open point 21.4).

One mechanism, hindsight-only (AGENTS.md section 6): a pure observer over the
EXISTING JSON artifacts -- the episode->point map's point order + windows, the
pass-2 serve stream, and (optionally) a diagnostic player dump for the
cross-check.  No video is decoded, nothing under src/ is touched, entreno
neutrality holds by construction.

Mechanism: the whole perception stack speaks COURT-SIDE letters (A = near
half, B = far half -- ``CourtCalibration.get_team``).  The owner/GT convention
is SQUAD letters (A = the squad that started near; squads swap halves at side
switches).  The two differ exactly across a side switch, which is why the raw
G1 ``team 0.518`` is a side-vs-squad confound, not a side-attribution failure.
This layer restores the missing mapping.

Switch schedule (primary): the beach cadence -- sides change ends after every
``--interval`` points played (7).  This is sport rules, NOT ground truth, and
it is read from the point order alone.  ``--validate`` compares it against the
owner's ``side_switch_after_point`` (the ONLY reader of that GT field).

Cross-check (evidence only, never overrides the cadence): with ``--evidence
<diag.jsonl>`` the dense per-frame player boxes are reduced to a per-point
median signed midcourt offset per track, and each boundary's player-crossing
support is reported.  The support is measured, not trusted: the tracker's ids
hop (open point 2), so the evidence is recorded and explicitly NOT used to
place switches.

Output (``output/side_switches.json``): the derived switches, the per-point
``near_squad`` / ``side_to_squad`` map, and ``actions_pass2`` augmented with
``pass2_squad`` (the squad letter downstream fantasy/stat layers consume).
The layer speaks squad identity; the side letter is kept as provenance.

Usage:
    venv/bin/python scripts/resolve_side_switches.py
    venv/bin/python scripts/resolve_side_switches.py --validate \\
        ground_truth/20260920_match_points.json
    venv/bin/python scripts/resolve_side_switches.py \\
        --evidence output/g3r1/match_bw03_diag.jsonl
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

OPPONENT = {"A": "B", "B": "A"}

#: Default beach cadence: change ends every 7 points played.
DEFAULT_INTERVAL = 7

#: Default player-side deadband (px) for the crossing cross-check.  A player
#: whose foot point is within this distance of the midcourt line is treated as
#: "ambiguous" and excluded from the flip support.
DEFAULT_DEADBAND_PX = 20

DEFAULT_MAP = "output/episode_point_map.json"
DEFAULT_SERVE_RELABEL = "output/serve_relabel.json"
DEFAULT_OUT = "output/side_switches.json"
DEFAULT_GT = "ground_truth/20260920_match_points.json"
DEFAULT_G1 = "output/heldout_contacts/g1.json"
DEFAULT_REPORT = "logs/side_switch_report.md"
DEFAULT_DIAG = "output/g3r1/match_bw03_diag.jsonl"


# ----------------------------------------------------------------------
# switch cadence (pure)
# ----------------------------------------------------------------------

def derive_switches(point_numbers: Sequence[int],
                    interval: int = DEFAULT_INTERVAL) -> List[int]:
    """Points AFTER which the sides change ends, by the beach cadence.

    Sides change after every ``interval`` points played: for a 33-point match
    and interval 7 that is ``[7, 14, 21, 28]``.  Derived from the point order
    alone -- no GT.
    """
    if interval <= 0:
        raise ValueError("interval must be positive")
    return sorted(int(p) for p in point_numbers if int(p) > 0 and int(p) % interval == 0)


def n_switches_before(point: int, switches: Sequence[int]) -> int:
    return sum(1 for s in switches if int(point) > int(s))


def near_squad(point: int, switches: Sequence[int]) -> str:
    """Which squad is on the NEAR half at ``point`` (A starts near)."""
    return "A" if n_switches_before(point, switches) % 2 == 0 else "B"


def side_to_squad(side: Optional[str], point: int,
                  switches: Sequence[int]) -> Optional[str]:
    """Court-side letter (A=near, B=far) -> squad letter at ``point``."""
    if side not in ("A", "B"):
        return None
    ns = near_squad(point, switches)
    return ns if side == "A" else OPPONENT[ns]


def side_letter_to_court(side: Optional[str]) -> Optional[str]:
    """Court-side letter -> owner side word (for the side-accuracy metric)."""
    return {"A": "near", "B": "far"}.get(side)


# ----------------------------------------------------------------------
# point placement (pure)
# ----------------------------------------------------------------------

def point_windows(map_blob: Dict[str, Any]
                  ) -> List[Tuple[int, List[int]]]:
    """[(point, window_frames)] in point order (windows that are present)."""
    out = []
    for p in map_blob.get("points") or []:
        w = p.get("window_frames")
        if w and len(w) == 2:
            out.append((int(p["point"]), [int(w[0]), int(w[1])]))
    return sorted(out, key=lambda x: x[0])


def point_for_frame(frame: int, windows: Sequence[Tuple[int, List[int]]]
                    ) -> Optional[int]:
    """The point whose window contains ``frame``; else the nearest window."""
    if not windows:
        return None
    for point, (w0, w1) in windows:
        if w0 <= frame <= w1:
            return point

    def distance(pw: Tuple[int, List[int]]) -> float:
        w0, w1 = pw[1]
        if frame < w0:
            return w0 - frame
        return frame - w1  # frame > w1 here

    # Tie-break toward the LATER window (forward assignment preserves point
    # order for a drifted action on a boundary).
    best = min(windows, key=lambda pw: (distance(pw), -pw[0]))
    return best[0]


# ----------------------------------------------------------------------
# layer construction (pure)
# ----------------------------------------------------------------------

def build_point_map(point_numbers: Sequence[int], switches: Sequence[int]
                    ) -> List[Dict[str, Any]]:
    return [{"point": int(p), "near_squad": near_squad(p, switches),
             "side_to_squad": {"A": near_squad(p, switches),
                               "B": OPPONENT[near_squad(p, switches)]}}
            for p in sorted(int(p) for p in point_numbers)]


def annotate_actions(actions: Sequence[Dict[str, Any]],
                     windows: Sequence[Tuple[int, List[int]]],
                     switches: Sequence[int]) -> List[Dict[str, Any]]:
    """Every pass-2 action + its derived squad letter.

    ``pass2_team`` (or ``team``) is the side letter; ``pass2_squad`` is the
    squad identity at the action's point.  ``pass2_point`` records the point
    used (nearest window when a drifted action sits outside every window).
    """
    out = []
    for a in actions:
        b = dict(a)
        f = b.get("frame_number")
        pt = point_for_frame(int(f), windows) if f is not None else None
        side = b.get("pass2_team", b.get("team"))
        b["pass2_point"] = pt
        b["pass2_squad"] = side_to_squad(side, pt, switches) if pt else None
        out.append(b)
    return out


def build_layer(map_blob: Dict[str, Any], actions: Sequence[Dict[str, Any]],
                switches: Sequence[int]) -> Dict[str, Any]:
    wins = point_windows(map_blob)
    points = [p for p, _ in wins]
    return {
        "video": map_blob.get("video"),
        "rule": {"kind": "beach_cadence", "interval": DEFAULT_INTERVAL,
                 "note": "sides change ends after every N points played; "
                         "sport rules, not ground truth"},
        "switches": list(switches),
        "points": build_point_map(points, switches),
        "actions_pass2": annotate_actions(actions, wins, switches),
    }


# ----------------------------------------------------------------------
# validation (the ONLY reader of GT side-switch fields)
# ----------------------------------------------------------------------

def validate_switches(derived: Sequence[int], gt_switches: Sequence[int]
                      ) -> Dict[str, Any]:
    d, g = set(int(x) for x in derived), set(int(x) for x in gt_switches)
    return {
        "derived": sorted(d),
        "gt": sorted(g),
        "exact_match": d == g,
        "missing": sorted(g - d),
        "extra": sorted(d - g),
    }


def contact_team_metric(rows: Sequence[Dict[str, Any]],
                        switches: Sequence[int]) -> Dict[str, Any]:
    """Correct the side-vs-squad confound on the G1 per-contact rows.

    ``raw`` = the recorded G1 metric (pred side letter vs GT squad).  ``squad``
    = the same prediction mapped through the derived schedule.  ``side`` =
    prediction vs the owner's observed side (what the layer actually emits).
    A contact counts only when it was matched and both teams are present.
    """
    usable = [r for r in rows
              if r.get("matched") and r.get("pred_team") in ("A", "B")
              and r.get("gt_team") in ("A", "B")]
    n = len(usable)
    raw = squad = side = 0
    residuals: List[Dict[str, Any]] = []
    for r in usable:
        pt = int(r["gt_point"])
        mapped = side_to_squad(r["pred_team"], pt, switches)
        raw_ok = r["pred_team"] == r["gt_team"]
        sq_ok = mapped == r["gt_team"]
        sd_ok = side_letter_to_court(r["pred_team"]) == r.get("gt_side")
        raw += raw_ok
        squad += sq_ok
        side += sd_ok
        if not sq_ok:
            residuals.append({"point": pt, "gt_frame": r.get("gt_frame"),
                              "gt_action": r.get("gt_action"),
                              "gt_team": r["gt_team"], "gt_side": r.get("gt_side"),
                              "pred_side": r["pred_team"],
                              "pred_squad": mapped,
                              "label_ok": r.get("label_ok")})
    return {
        "n_found": n,
        "raw_correct": raw,
        "raw_accuracy": round(raw / n, 4) if n else None,
        "squad_correct": squad,
        "squad_accuracy": round(squad / n, 4) if n else None,
        "side_correct": side,
        "side_accuracy": round(side / n, 4) if n else None,
        "residual_team_errors": residuals,
    }


# ----------------------------------------------------------------------
# cross-check evidence (optional diag dump; never places switches)
# ----------------------------------------------------------------------

def _midcourt_y_at(x: float, midcourt_points: Sequence[Sequence[float]]) -> float:
    x0, y0 = float(midcourt_points[0][0]), float(midcourt_points[0][1])
    x1, y1 = float(midcourt_points[1][0]), float(midcourt_points[1][1])
    if abs(x1 - x0) < 1e-6:
        return (y0 + y1) / 2.0
    t = max(0.0, min(1.0, (x - x0) / (x1 - x0)))
    return y0 + t * (y1 - y0)


def footprint_offsets(diag: Any, calibration: Dict[str, Any]
                      ) -> Dict[int, List[Tuple[int, float]]]:
    """(track_id, signed midcourt offset) per frame from a diag dump iterator.

    ``+`` = near (team A) side, ``-`` = far (team B) side.  The offset uses the
    bbox foot point.  ``diag`` is any iterable of parsed per-frame records;
    the ``meta`` header is skipped.
    """
    mc = calibration["midcourt_points"]
    out: Dict[int, List[Tuple[int, float]]] = {}
    for rec in diag:
        if "players" not in rec:
            continue
        frame = int(rec["frame"])
        for p in rec["players"]:
            b = p.get("bbox")
            if not b:
                continue
            x = (float(b[0]) + float(b[2])) / 2.0
            y = float(b[3])
            out.setdefault(int(p["track_id"]), []).append(
                (frame, y - _midcourt_y_at(x, mc)))
    return out


def median_offsets_by_point(offsets: Dict[int, List[Tuple[int, float]]],
                            point_numbers: Sequence[int],
                            windows: Dict[int, List[int]]
                            ) -> Dict[int, Dict[int, float]]:
    """{point: {track_id: median signed offset}} over each point window."""
    out: Dict[int, Dict[int, float]] = {}
    for pt in point_numbers:
        w = windows.get(pt)
        if not w:
            continue
        row: Dict[int, float] = {}
        for tid, series in offsets.items():
            vals = [v for f, v in series if w[0] <= f <= w[1]]
            if vals:
                row[tid] = round(statistics.median(vals), 1)
        out[pt] = row
    return out


def crossing_support(before: Dict[int, float], after: Dict[int, float],
                     deadband: float = DEFAULT_DEADBAND_PX) -> Dict[str, Any]:
    """Did the tracks present in both points credibly change side?

    Only tracks with |offset| > ``deadband`` in BOTH points vote.  Support is
    ``flipped / confident``; ``None`` when no track is confident in both.
    """
    confident = [t for t in set(before) & set(after)
                 if abs(before[t]) > deadband and abs(after[t]) > deadband]
    flipped = [t for t in confident
               if (before[t] > 0) != (after[t] > 0)]
    return {
        "confident_tracks": sorted(confident),
        "flipped_tracks": sorted(flipped),
        "n_confident": len(confident),
        "n_flipped": len(flipped),
        "support": (round(len(flipped) / len(confident), 3)
                    if confident else None),
    }


def boundary_evidence(medians: Dict[int, Dict[int, float]],
                      point_numbers: Sequence[int],
                      switches: Sequence[int],
                      deadband: float = DEFAULT_DEADBAND_PX) -> List[Dict[str, Any]]:
    """Per consecutive-point boundary: crossing support + whether cadence says switch."""
    rows = []
    pts = sorted(int(p) for p in point_numbers)
    for i in range(len(pts) - 1):
        k, k2 = pts[i], pts[i + 1]
        ev = crossing_support(medians.get(k, {}), medians.get(k2, {}), deadband)
        ev.update({"after_point": k, "next_point": k2,
                   "cadence_says_switch": k in set(int(s) for s in switches)})
        rows.append(ev)
    return rows


def evidence_summary(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Does the crossing evidence place the switches the cadence places?"""
    sw = [r for r in rows if r["cadence_says_switch"]]
    nsw = [r for r in rows if not r["cadence_says_switch"]]
    return {
        "boundaries": len(rows),
        "switch_boundaries": len(sw),
        "switch_boundaries_with_support": sum(1 for r in sw if r["n_flipped"] > 0),
        "non_switch_boundaries_with_support": sum(1 for r in nsw if r["n_flipped"] > 0),
        "note": "player ids hop (open point 2), so this evidence is recorded "
                "and NOT used to place switches",
    }


# ----------------------------------------------------------------------
# orchestration
# ----------------------------------------------------------------------

def run(map_path: str = DEFAULT_MAP, relabel_path: str = DEFAULT_SERVE_RELABEL,
        out_path: str = DEFAULT_OUT, interval: int = DEFAULT_INTERVAL
        ) -> Dict[str, Any]:
    map_blob = json.loads(Path(map_path).read_text(encoding="utf-8"))
    relabel = json.loads(Path(relabel_path).read_text(encoding="utf-8"))
    wins = point_windows(map_blob)
    points = [p for p, _ in wins]
    switches = derive_switches(points, interval)

    out = build_layer(map_blob, relabel.get("actions_pass2") or [], switches)
    out["rule"]["interval"] = interval
    out["generated_from"] = {
        "map": map_path, "serve_relabel": relabel_path,
        "note": "pass-2 squad/side-switch layer (AGENTS.md section 6); "
                "perception untouched, no video decoded",
    }
    Path(out_path).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--map", default=DEFAULT_MAP)
    ap.add_argument("--serve-relabel", default=DEFAULT_SERVE_RELABEL)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    ap.add_argument("--validate", default=None, metavar="GT_MATCH_POINTS")
    ap.add_argument("--g1", default=DEFAULT_G1,
                    help="G1 per-contact artifact for the metric correction")
    ap.add_argument("--evidence", default=None, metavar="DIAG_JSONL",
                    help="optional player diag dump for the crossing cross-check")
    ap.add_argument("--calibration", default=None,
                    help="calibration JSON (default: from --map's video)")
    ap.add_argument("--deadband-px", type=float, default=DEFAULT_DEADBAND_PX)
    ap.add_argument("--report", default=DEFAULT_REPORT)
    args = ap.parse_args(argv)

    out = run(args.map, args.serve_relabel, args.out, args.interval)
    switches = out["switches"]
    print(f"derived switches (interval {args.interval}): {switches}")
    print(f"points mapped: {len(out['points'])}; "
          f"actions annotated: {len(out['actions_pass2'])}")

    lines: List[str] = ["# Side-switch / squad layer (S3, open point 21.4)", ""]
    lines.append(f"- derived switches: `{switches}` (beach cadence, "
                 f"interval {args.interval})")
    lines.append(f"- points mapped: {len(out['points'])}; "
                 f"actions carried `pass2_squad`: "
                 f"{sum(1 for a in out['actions_pass2'] if a.get('pass2_squad'))}")
    lines.append("")

    if args.validate:
        gt = json.loads(Path(args.validate).read_text(encoding="utf-8"))
        gt_sw = gt.get("side_switch_after_point", [])
        v = validate_switches(switches, gt_sw)
        print(f"validate vs GT switches {v['gt']}: "
              f"exact_match={v['exact_match']} missing={v['missing']} "
              f"extra={v['extra']}")
        lines.append(f"## Cadence vs GT\n\n"
                     f"- GT `side_switch_after_point`: `{v['gt']}`\n"
                     f"- exact match: **{v['exact_match']}** "
                     f"(missing {v['missing']}, extra {v['extra']})\n")

    if args.g1 and Path(args.g1).exists():
        g1 = json.loads(Path(args.g1).read_text(encoding="utf-8"))
        rows = g1.get("perception_contact_rows") or []
        m = contact_team_metric(rows, switches)
        print(f"G1 team metric on {m['n_found']} found contacts: "
              f"raw (side vs squad) {m['raw_correct']}={m['raw_accuracy']}; "
              f"squad-mapped {m['squad_correct']}={m['squad_accuracy']}; "
              f"side-vs-owner-side {m['side_correct']}={m['side_accuracy']}")
        lines.append("## G1 team metric correction\n")
        lines.append(f"- matched contacts: {m['n_found']}")
        lines.append(f"- recorded G1 raw (pred side vs GT squad): "
                     f"**{m['raw_correct']}/{m['n_found']} = {m['raw_accuracy']}**")
        lines.append(f"- squad-mapped (this layer): "
                     f"**{m['squad_correct']}/{m['n_found']} = {m['squad_accuracy']}**")
        lines.append(f"- pred side vs owner side (what is actually emitted): "
                     f"**{m['side_correct']}/{m['n_found']} = {m['side_accuracy']}**")
        lines.append(f"- residual genuine team errors: "
                     f"**{len(m['residual_team_errors'])}**")
        lines.append("")
        for r in m["residual_team_errors"]:
            lines.append(f"  - P{r['point']} f{r['gt_frame']} {r['gt_action']}: "
                         f"GT {r['gt_team']}/{r['gt_side']}, "
                         f"pred side {r['pred_side']} -> squad {r['pred_squad']}")
        lines.append("")

    if args.evidence and Path(args.evidence).exists():
        cal_path = args.calibration
        if not cal_path:
            cal_path = f"calibrations/{out['video']}.json"
        if Path(cal_path).exists():
            cal = json.loads(Path(cal_path).read_text(encoding="utf-8"))
            with open(args.evidence, encoding="utf-8") as fh:
                recs = []
                for i, line in enumerate(fh):
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    recs.append(rec)
            offsets = footprint_offsets(recs, cal)
            wins = dict(point_windows(
                json.loads(Path(args.map).read_text(encoding="utf-8"))))
            medians = median_offsets_by_point(offsets, list(wins), wins)
            ev = boundary_evidence(medians, list(wins), switches, args.deadband_px)
            summ = evidence_summary(ev)
            print(f"crossing evidence: {summ['switch_boundaries_with_support']}"
                  f"/{summ['switch_boundaries']} cadence switches show support; "
                  f"{summ['non_switch_boundaries_with_support']} non-switch "
                  f"boundaries also show support")
            lines.append("## Crossing cross-check (evidence only)\n")
            lines.append(f"- {summ['switch_boundaries_with_support']}/"
                         f"{summ['switch_boundaries']} cadence switches show "
                         f"player-crossing support")
            lines.append(f"- {summ['non_switch_boundaries_with_support']} "
                         f"non-switch boundaries also show support "
                         f"({summ['boundaries']} total)")
            lines.append(f"- {summ['note']}")
            lines.append("")
        else:
            print(f"evidence skipped: no calibration at {cal_path}")

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
