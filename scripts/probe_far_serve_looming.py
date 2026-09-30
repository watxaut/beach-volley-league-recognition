#!/usr/bin/env python3
"""G3 plan S1 -- far-side serve LOOMING probe.  DIAGNOSE ONLY: no src/ change.

Background (STATUS #42, open point 22).  The far serve is the loss G3 and G1
share: at CONTACT level the pass-2 layer is 0/5 on dev P1-P8 (the point-level
"8/8" census is bookkeeping).  T5 refuted the ball-track admission fixes, R1
refuted the departure gate, and the contact probe's own serve branch wants a
FED ASCENT the far toss does not have.  The one measured asymmetry left is
LOOMING: after the contact the far serve flies toward the (fixed, long-axis)
camera, so its apparent bbox WIDTH grows; the pre-contact toss is absent at
~3/5 of the dev far serves (T5).  Looming is a *monocular* signal that does
not need the toss.

Mechanism measured here (spec frozen by the owner, #42).  In the new-rally
state (no emitted contact within ``ActionClassifier.RALLY_RESET_GAP``):

* a ball SEGMENT is a run of production-tracked sightings (the tracker's own
  ``state == "tracked"`` frames, merged across gaps <= ``ball_max_missing``,
  its identity horizon);
* its ONSET is the first tracked frame; the onset width must be <= 26 px
  (below the 26-35 near/far abstain band -- a FAR ball);
* ``L`` = OLS slope of ``ln(bbox width)`` against time in SECONDS over
  ``[onset, onset + 0.5 s]``.  A looming (approaching) ball has ``L > 0``;
* ``L*`` = midpoint of the EMPTY gap between the lowest dev far-serve ``L``
  and the highest dev new-rally NON-serve ``L``.

Inputs are existing artifacts only.  The dev/e1-e7 dumps already carry the
production ``ball_track``; the match dump is REPLAYED through the production
``BallTracker`` (imported from ``scripts/probe_serve_mechanisms.py`` -- never
reimplemented), and the replay must reproduce the dumped ``locked`` flag and
track centre on every frame or the probe stops.

Pre-registered KILLS (#42):
  1. <4/5 dev far serves (f210/880/2154/3038/4770) have >=5 far-band sightings
     in [c, c+0.5 s]  -> the far flight is undetected; the lever is detection.
  2. no empty gap on dev, or gap ratio < 1.5x  -> ``L`` does not separate.
  3. any fire on e1-e7 (all entreno serves are near-side, >26 px).
  4. match P9-P33 at frozen ``L*``: >=9/12 far-serve windows before the
     pass-2 reception, precision >=0.75 over all new-rally fires.

Kill 4 needs the owner's S0 contact GT (P9-P33, open point 24) and is reported
PENDING until it lands; kills 1-3 run today.  The secondary feature
``nearest far-team player is_behind_baseline at onset`` is DECLARED BEFORE the
held-out look (a dead-time throw-back can also loom); it is reported, never
fit.

Usage (defaults reproduce the doc)::

    venv/bin/python scripts/probe_far_serve_looming.py
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.detection.court_calibration import CourtCalibration  # noqa: E402
from src.recognition.action_classifier import ActionClassifier  # noqa: E402
from src.utils.config import Config  # noqa: E402
from src.utils.diagnostics import load_diag  # noqa: E402

# The production replay (detections -> BallTracker) is imported, never copied:
# the T5 harness owns the fidelity-pinned implementation.
from probe_serve_mechanisms import det_rows, make_tracker  # noqa: E402

#: Onset apparent width ceiling: below the 26-35 near/far abstain band, i.e. a
#: FAR-side ball (constant from ``attribution_width_near_px`` semantics).
FAR_MAX_WIDTH = 26.0
#: Looming-window length in SECONDS (spec).
LOOMING_SPAN_S = 0.5
#: Minimum real sightings inside the window for an OLS slope to mean anything.
MIN_LOOMING_POINTS = 3
#: Empty-gap kill (spec kill 2).
GAP_RATIO_MIN = 1.5
#: Kill 1 (spec).
KILL1_MIN_SERVES = 4
KILL1_MIN_SIGHTINGS = 5
#: Owner's dev far serves (ground_truth/video_ari_joan_8_first_points...).
DEV_FAR_SERVES = [210, 880, 2154, 3038, 4770]

DEFAULT_DEV = "output/t4/dev_diag.jsonl"
DEFAULT_MATCH = "output/g3r1/match_bw03_diag.jsonl"
DEFAULT_MATCH_CAL = "calibrations/20260920_match_ari_joan_lost.json"
DEFAULT_DEV_CAL = "calibrations/video_ari_joan_8_first_points.json"
DEFAULT_DEV_GT = "ground_truth/video_ari_joan_8_first_points_annotations.json"


# ---------------------------------------------------------------------------
# sightings: production ball_track + the admitted detection's apparent width
# ---------------------------------------------------------------------------

def nearest_det_width(record: Dict[str, Any], center: List[float]
                      ) -> Optional[float]:
    """Apparent bbox width of the detection the tracker admitted.

    The admitted detection's centre equals the emitted track centre, so the
    match is exact (the same recovery ``action_evidence._tracked_widths`` uses);
    coasted/predicted frames have no admitted detection and return None.
    """
    best: Optional[Tuple[float, Dict[str, Any]]] = None
    for d in record.get("ball_dets", []) or []:
        if d.get("removed") or not d.get("bbox") or not d.get("center"):
            continue
        dc = d["center"]
        dist = math.hypot(dc[0] - center[0], dc[1] - center[1])
        if best is None or dist < best[0]:
            best = (dist, d)
    if best is None or best[0] > 1e-6:
        return None
    bbox = best[1]["bbox"]
    return float(bbox[2] - bbox[0]) if len(bbox) >= 4 else None


def dump_sightings(frames: Dict[int, Dict[str, Any]]
                   ) -> Dict[int, Dict[str, Any]]:
    """Dumped production ``ball_track`` -> ``{frame: sighting}``."""
    out: Dict[int, Dict[str, Any]] = {}
    for f, rec in frames.items():
        bt = rec.get("ball_track") or {}
        center = bt.get("center")
        if not center or center[0] is None:
            continue
        out[int(f)] = {
            "state": bt.get("state"),
            "center": [float(center[0]), float(center[1])],
            "width": nearest_det_width(rec, center),
            "conf": bt.get("conf"),
        }
    return out


def replay_sightings(frames: Dict[int, Dict[str, Any]], cfg: Config,
                     court: Optional[CourtCalibration]
                     ) -> Tuple[Dict[int, Dict[str, Any]], Dict[str, int]]:
    """Replay the match dump through production ``BallTracker``.

    Returns ``(sightings, fidelity)`` where fidelity counts the frames on which
    the replay's ``locked`` flag or (for real sightings) centre diverge from
    the dumped production track.  Any divergence is a hard stop -- the probe
    must see exactly what production saw.
    """
    bounds = (court.court_bounds
              if court is not None and court.is_calibrated else None)
    tracker = make_tracker(cfg, {}, bounds)
    out: Dict[int, Dict[str, Any]] = {}
    locked_mismatch = center_mismatch = 0
    for f in sorted(frames):
        rec = frames[f]
        det = tracker.update(det_rows(rec), frame_number=f)
        bt = rec.get("ball_track") or {}
        if bool(bt.get("locked")) != bool(tracker.locked):
            locked_mismatch += 1
        elif bt.get("center") and det is not None and not det.get("is_predicted"):
            if (abs(bt["center"][0] - det["center"][0]) > 1e-6
                    or abs(bt["center"][1] - det["center"][1]) > 1e-6):
                center_mismatch += 1
        if det is not None and not det.get("is_predicted"):
            bbox = det.get("bbox") or []
            width = float(bbox[2] - bbox[0]) if len(bbox) >= 4 else None
            out[int(f)] = {
                "state": "tracked",
                "center": [float(det["center"][0]), float(det["center"][1])],
                "width": width,
                "conf": det.get("confidence"),
            }
        else:
            out[int(f)] = {"state": bt.get("state"), "center": None,
                           "width": None, "conf": bt.get("conf")}
    return out, {"frames": len(frames), "locked_mismatch": locked_mismatch,
                 "center_mismatch": center_mismatch}


# ---------------------------------------------------------------------------
# segments + the looming feature
# ---------------------------------------------------------------------------

def build_segments(sightings: Dict[int, Dict[str, Any]], merge_gap: int
                   ) -> List[Dict[str, Any]]:
    """Runs of REAL tracked sightings merged across ``merge_gap``-frame holes.

    ``merge_gap`` is the tracker's coast horizon (``ball_max_missing``): short
    detection dropouts do not end the same flight, so one flight is one
    segment.  Onset is the first real sighting.
    """
    frames = sorted(f for f, s in sightings.items()
                    if s.get("state") == "tracked" and s.get("width"))
    if not frames:
        return []
    segs: List[List[int]] = []
    cur = [frames[0]]
    for f in frames[1:]:
        if f - cur[-1] <= merge_gap:
            cur.append(f)
        else:
            segs.append(cur)
            cur = [f]
    segs.append(cur)
    return [{"onset": s[0], "frames": s} for s in segs]


def looming_rate(sightings: Dict[int, Dict[str, Any]], onset: int, fps: float,
                 span_s: float = LOOMING_SPAN_S) -> Optional[float]:
    """OLS slope of ``ln(width)`` vs time (seconds) over the looming window.

    Returns None when fewer than ``MIN_LOOMING_POINTS`` real sightings with a
    positive width fall inside ``[onset, onset + span_s]``.
    """
    if fps <= 0:
        return None
    hi = onset + int(round(span_s * fps))
    pts = [(f, float(sightings[f]["width"]))
           for f in sorted(sightings)
           if onset <= f <= hi and (sightings[f].get("width") or 0) > 0]
    if len(pts) < MIN_LOOMING_POINTS:
        return None
    xs = [(f - onset) / fps for f, _w in pts]
    ys = [math.log(w) for _f, w in pts]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def contact_frames(frames: Dict[int, Dict[str, Any]]) -> List[int]:
    """Emitted contact frames (the diag ``actions`` sections' ``frame_number``)."""
    out = set()
    for rec in frames.values():
        for a in rec.get("actions", []) or []:
            fn = a.get("frame_number")
            if fn is not None:
                out.add(int(fn))
    return sorted(out)


def is_new_rally(onset: int, contacts: List[int], gap: int) -> bool:
    """True when no emitted contact falls in ``[onset - gap, onset)``.

    Mirrors ``ActionContextResolver``'s ``new_rally = gap > rally_reset_gap``
    (``gap`` = frames since the previous emitted contact).
    """
    return not any(onset - gap <= c <= onset for c in contacts)


def gt_far_serve_for(onset: int, far_serves: List[int], tol: int) -> Optional[int]:
    """The GT far serve whose contact-to-onset interval contains ``onset``.

    T5 measured the first post-contact sighting 2-4 f after the contact; the
    matcher allows the GT ``frame_tolerance`` (default 15).
    """
    for c in far_serves:
        if c <= onset <= c + tol:
            return c
    return None


def behind_baseline_at_onset(frames: Dict[int, Dict[str, Any]], onset: int,
                             court: Optional[CourtCalibration],
                             team: str = "B") -> Optional[bool]:
    """Secondary (declared-before-holdout) feasance: nearest far-team player.

    Uses the player's FEET (bbox bottom-centre) against the baseline of the
    far team, exactly the attribution convention.
    """
    if court is None or not court.is_calibrated:
        return None
    rec = frames.get(onset) or {}
    ball = (rec.get("ball_track") or {}).get("center")
    if not ball:
        return None
    best = None
    for p in rec.get("players", []) or []:
        if p.get("predicted") or p.get("team") != team:
            continue
        bbox = p.get("bbox")
        if not bbox:
            continue
        feet = ((bbox[0] + bbox[2]) / 2.0, bbox[3])
        d = math.hypot(feet[0] - ball[0], feet[1] - ball[1])
        if best is None or d < best[0]:
            best = (d, feet)
    if best is None:
        return None
    feet = best[1]
    return bool(court.is_behind_baseline((int(feet[0]), int(feet[1])), team))


def build_candidates(frames: Dict[int, Dict[str, Any]],
                     sightings: Dict[int, Dict[str, Any]], fps: float,
                     merge_gap: int, far_serves: List[int], tol: int,
                     court: Optional[CourtCalibration] = None
                     ) -> List[Dict[str, Any]]:
    """Every far-band new-rally segment -> its looming candidate row."""
    contacts = contact_frames(frames)
    rows: List[Dict[str, Any]] = []
    for seg in build_segments(sightings, merge_gap):
        onset = seg["onset"]
        width = sightings[onset].get("width")
        if width is None or width > FAR_MAX_WIDTH:
            continue
        nr = is_new_rally(onset, contacts, ActionClassifier.RALLY_RESET_GAP)
        if not nr:
            continue
        rows.append({
            "onset": onset,
            "width_px": round(float(width), 1),
            "n_sightings": len(seg["frames"]),
            "L": looming_rate(sightings, onset, fps),
            "segment_end": seg["frames"][-1],
            "gt_far_serve": gt_far_serve_for(onset, far_serves, tol),
            "behind_baseline": behind_baseline_at_onset(frames, onset, court),
        })
    return rows


# ---------------------------------------------------------------------------
# kill evaluation
# ---------------------------------------------------------------------------

def kill1(frames: Dict[int, Dict[str, Any]],
          sightings: Dict[int, Dict[str, Any]], fps: float,
          far_serves: List[int]) -> Dict[str, Any]:
    """Far-band tracked sightings inside ``[c, c + 0.5 s]`` per dev far serve."""
    hi = int(round(LOOMING_SPAN_S * fps))
    per: Dict[str, Any] = {}
    met = 0
    for c in far_serves:
        ws = [float(sightings[f]["width"]) for f in range(c, c + hi + 1)
              if f in sightings and sightings[f].get("state") == "tracked"
              and sightings[f].get("width")]
        n_far = sum(1 for w in ws if w <= FAR_MAX_WIDTH)
        per[str(c)] = {"tracked": len(ws), "far_band": n_far,
                       "ok": n_far >= KILL1_MIN_SIGHTINGS}
        met += int(n_far >= KILL1_MIN_SIGHTINGS)
    return {
        "per_serve": per,
        "serves_meeting": met,
        "serves_total": len(far_serves),
        "threshold_serves": KILL1_MIN_SERVES,
        "threshold_sightings": KILL1_MIN_SIGHTINGS,
        "fired": met < KILL1_MIN_SERVES,
    }


def separation(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The dev ``L`` gap between far serves and new-rally non-serve segments."""
    far = sorted(r["L"] for r in rows
                 if r["gt_far_serve"] is not None and r["L"] is not None)
    non = sorted(r["L"] for r in rows
                 if r["gt_far_serve"] is None and r["L"] is not None)
    lowest_far = far[0] if far else None
    highest_non = non[-1] if non else None
    if lowest_far is None or highest_non is None:
        gap = None
        ratio = None
        l_star = None
    else:
        gap = lowest_far - highest_non
        ratio = (lowest_far / highest_non) if highest_non > 0 else None
        l_star = (lowest_far + highest_non) / 2.0 if gap > 0 else None
    return {
        "far_L": far,
        "non_serve_L": non,
        "lowest_far_L": lowest_far,
        "highest_non_serve_L": highest_non,
        "gap": gap,
        "gap_ratio": ratio,
        "L_star": l_star,
        "kill2_fired": (lowest_far is None or highest_non is None
                        or gap is None or gap <= 0
                        or ratio is None or ratio < GAP_RATIO_MIN),
    }


def entreno_fires(rows_by_clip: Dict[str, List[Dict[str, Any]]],
                  l_star: Optional[float]) -> Dict[str, Any]:
    """Kill 3: entreno far-band new-rally segments that would fire at L*."""
    fires: Dict[str, List[int]] = {}
    total = 0
    for name, rows in rows_by_clip.items():
        hit = [r["onset"] for r in rows
               if r["L"] is not None and l_star is not None and r["L"] >= l_star]
        fires[name] = hit
        total += len(hit)
    return {
        "l_star": l_star,
        "fires": fires,
        "total": total,
        "evaluable": l_star is not None,
        "fired": bool(total > 0) if l_star is not None else False,
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def analyze_clip(frames: Dict[int, Dict[str, Any]], fps: float, merge_gap: int,
                 far_serves: List[int], tol: int,
                 court: Optional[CourtCalibration] = None) -> Dict[str, Any]:
    sightings = dump_sightings(frames)
    return {
        "fps": fps,
        "frames": len(frames),
        "tracked_frames": sum(1 for s in sightings.values()
                              if s.get("state") == "tracked"),
        "candidates": build_candidates(frames, sightings, fps, merge_gap,
                                       far_serves, tol, court),
        "kill1": kill1(frames, sightings, fps, far_serves),
    }


def run(dev: str = DEFAULT_DEV, match: str = DEFAULT_MATCH,
        dev_cal: Optional[str] = DEFAULT_DEV_CAL,
        match_cal: Optional[str] = DEFAULT_MATCH_CAL,
        dev_gt: str = DEFAULT_DEV_GT,
        entreno: Optional[List[str]] = None,
        config: Optional[str] = None) -> Dict[str, Any]:
    cfg = Config(config) if config else Config()
    merge_gap = int(cfg.get("ball_max_missing", 10))

    dev_meta, dev_frames = _load(dev)
    court_dev = _load_cal(dev_cal)
    tol = _gt_tolerance(dev_gt)
    far_serves = _gt_far_serves(dev_gt, DEV_FAR_SERVES)
    dev = analyze_clip(dev_frames, dev_meta.get("fps") or 30.0, merge_gap,
                       far_serves, tol, court_dev)

    sep = separation(dev["candidates"])

    if entreno is None:
        entreno = [f"output/g3/e{n}_diag.jsonl" for n in range(1, 8)]
    entreno_rows: Dict[str, List[Dict[str, Any]]] = {}
    entreno_meta: Dict[str, Any] = {}
    for path in entreno:
        name = Path(path).stem.replace("_diag", "")
        meta, frames = _load(path)
        rows = build_candidates(frames, dump_sightings(frames),
                                meta.get("fps") or 30.0, merge_gap, [], 0)
        entreno_rows[name] = rows
        entreno_meta[name] = {"fps": meta.get("fps"), "frames": len(frames),
                              "tracked_frames": sum(
                                  1 for s in dump_sightings(frames).values()
                                  if s.get("state") == "tracked"),
                              "candidates": len(rows)}
    kill3 = entreno_fires(entreno_rows, sep["L_star"])

    match_summ: Dict[str, Any] = {"pending_s0": True}
    if match and os.path.exists(match):
        m_meta, m_frames = _load(match)
        m_court = _load_cal(match_cal)
        m_sight, fidelity = replay_sightings(m_frames, cfg, m_court)
        if fidelity["locked_mismatch"] or fidelity["center_mismatch"]:
            raise SystemExit(
                "STOP: match replay diverged from the dumped production "
                f"ball_track ({fidelity}); the probe must see exactly what "
                "production saw.")
        m_rows = build_candidates(m_frames, m_sight,
                                  m_meta.get("fps") or 30.0, merge_gap, [], 0,
                                  m_court)
        match_summ = {
            "pending_s0": True,
            "frames": len(m_frames),
            "fidelity": fidelity,
            "tracked_frames": sum(1 for s in m_sight.values()
                                  if s.get("state") == "tracked"),
            "far_band_new_rally_segments": len(m_rows),
            "would_fire_at_L_star": ([r["onset"] for r in m_rows
                                      if r["L"] is not None
                                      and sep["L_star"] is not None
                                      and r["L"] >= sep["L_star"]]
                                     if sep["L_star"] is not None else []),
            "candidates": m_rows,
        }

    verdict = _verdict(dev["kill1"], sep, kill3)
    return {
        "dev": dev,
        "separation": sep,
        "entreno": {"clips": entreno_meta, "kill3": kill3},
        "match": match_summ,
        "verdict": verdict,
        "params": {
            "far_max_width_px": FAR_MAX_WIDTH,
            "looming_span_s": LOOMING_SPAN_S,
            "gap_ratio_min": GAP_RATIO_MIN,
            "merge_gap_frames": merge_gap,
            "rally_reset_gap_frames": ActionClassifier.RALLY_RESET_GAP,
            "dev_gt": dev_gt,
            "far_serves": far_serves,
            "gt_tolerance": tol,
        },
    }


def _verdict(k1: Dict[str, Any], sep: Dict[str, Any],
             k3: Dict[str, Any]) -> Dict[str, Any]:
    if k1["fired"]:
        return {"status": "REFUTED", "reason": "kill 1: far flight undetected",
                "kills": {"1": True, "2": sep["kill2_fired"], "3": k3["fired"]}}
    if sep["kill2_fired"]:
        return {"status": "REFUTED", "reason": "kill 2: no separable L gap",
                "kills": {"1": False, "2": True, "3": k3["fired"]}}
    if k3["fired"]:
        return {"status": "REFUTED", "reason": "kill 3: fires on entreno",
                "kills": {"1": False, "2": False, "3": True}}
    return {"status": "SURVIVES (kills 1-3)",
            "reason": "L* frozen; kill 4 pending owner S0 contact GT",
            "kills": {"1": False, "2": False, "3": False}}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _load(path: str) -> Tuple[Dict[str, Any], Dict[int, Dict[str, Any]]]:
    d = load_diag(path)
    return d["meta"], d["frames"]


def _load_cal(path: Optional[str]) -> Optional[CourtCalibration]:
    if not path or not os.path.exists(path):
        return None
    court = CourtCalibration()
    court.load(path)
    return court if court.is_calibrated else None


def _gt_tolerance(path: str) -> int:
    try:
        blob = json.loads(open(path, encoding="utf-8").read())
    except Exception:
        return 15
    for pt in blob.get("points", []):
        for ev in pt.get("events", []):
            if ev.get("frame_tolerance"):
                return int(ev["frame_tolerance"])
    return 15


def _gt_far_serves(path: str, fallback: List[int]) -> List[int]:
    try:
        blob = json.loads(open(path, encoding="utf-8").read())
    except Exception:
        return list(fallback)
    out = []
    for pt in blob.get("points", []):
        for ev in pt.get("events", []):
            act = ev.get("final_action") or ev.get("action")
            if act == "serve" and ev.get("owner_side") == "far":
                out.append(int(ev["frame"]))
    return sorted(out) or list(fallback)


def markdown(report: Dict[str, Any]) -> str:
    dev = report["dev"]
    sep = report["separation"]
    ent = report["entreno"]
    k1 = dev["kill1"]
    v = report["verdict"]
    p = report["params"]
    L = []
    L.append("# G3 S1 - far-side serve looming probe (diagnose only)\n")
    L.append("**Status: " + v["status"] + "** - " + v["reason"] + ".\n")
    L.append("No `src/` change; the mechanism, if it had survived, would have "
             "required the owner-gated S2 band (STATUS #42).\n")
    L.append("## Frozen spec\n")
    L.append(f"* far-band onset width <= {p['far_max_width_px']:.0f} px; "
             f"looming window {p['looming_span_s']} s; "
             f"merge gap {p['merge_gap_frames']} f "
             f"(`ball_max_missing`); new-rally gap "
             f"{p['rally_reset_gap_frames']} f.")
    L.append(f"* dev far serves {p['far_serves']} (GT tolerance "
             f"+-{p['gt_tolerance']} f).\n")
    L.append("## Kill 1 - far flight detected?\n")
    L.append(f"Far-band tracked sightings in [c, c+0.5 s]; need "
             f">= {k1['threshold_sightings']} at "
             f">= {k1['threshold_serves']}/{k1['serves_total']} serves. "
             f"**met at {k1['serves_meeting']}/{k1['serves_total']}; "
             f"{'FIRED' if k1['fired'] else 'not fired'}.**\n")
    L.append("| GT far serve | tracked | far-band | ok |")
    L.append("|---|---|---|---|")
    for c, row in k1["per_serve"].items():
        L.append(f"| f{c} | {row['tracked']} | {row['far_band']} | "
                 f"{'yes' if row['ok'] else 'NO'} |")
    L.append("")
    L.append("## Kill 2 - does L separate far serves from new-rally non-serves?\n")
    L.append(f"* lowest far-serve L = "
             f"**{_fmt(sep['lowest_far_L'])}**; highest new-rally non-serve L = "
             f"**{_fmt(sep['highest_non_serve_L'])}**.")
    L.append(f"* gap = {_fmt(sep['gap'])}, ratio = "
             f"{_fmt(sep['gap_ratio'])} (need >= {p['gap_ratio_min']}x); "
             f"L* = {_fmt(sep['L_star'])}; **"
             f"{'FIRED' if sep['kill2_fired'] else 'not fired'}.**\n")
    if sep["kill2_fired"] and sep["lowest_far_L"] is not None:
        overlaps = [r for r in dev["candidates"]
                    if r["gt_far_serve"] is None and r["L"] is not None
                    and r["L"] >= sep["lowest_far_L"]]
        L.append(f"{len(overlaps)} new-rally non-serve segment(s) loom at or "
                 "above the weakest far serve, so no threshold can admit all "
                 "five without false fires:\n")
        L.append("| onset | width px | L | behind baseline |")
        L.append("|---|---|---|---|")
        for r in sorted(overlaps, key=lambda r: -r["L"]):
            L.append(f"| f{r['onset']} | {r['width_px']} | {r['L']:.3f} | "
                     f"{r['behind_baseline']} |")
        L.append("")
    L.append("Dev candidates (new-rally, far-band):\n")
    L.append("| onset | width px | L | GT far serve | behind baseline |")
    L.append("|---|---|---|---|---|")
    for r in sorted(dev["candidates"], key=lambda r: r["onset"]):
        L.append(f"| f{r['onset']} | {r['width_px']} | {_fmt(r['L'], 3)} | "
                 f"{('f' + str(r['gt_far_serve'])) if r['gt_far_serve'] else '-'} | "
                 f"{r['behind_baseline']} |")
    L.append("")
    L.append("## Kill 3 - entreno neutrality\n")
    if not ent["kill3"]["evaluable"]:
        L.append("Not evaluable: L* is undefined (kill 2 fired), so no "
                 "threshold could fire.  Census of far-band new-rally "
                 "segments per entreno clip:\n")
    else:
        L.append(f"Fires at L* = {_fmt(ent['kill3']['l_star'])}: "
                 f"**{ent['kill3']['total']}** "
                 f"({'FIRED' if ent['kill3']['fired'] else 'not fired'}).\n")
    L.append("| clip | tracked | far-band new-rally segments |")
    L.append("|---|---|---|")
    for name, m in ent["clips"].items():
        L.append(f"| {name} | {m['tracked_frames']} | {m['candidates']} |")
    L.append("")
    L.append("## Kill 4 - held-out match (PENDING S0)\n")
    m = report["match"]
    if m.get("pending_s0"):
        L.append("Owner S0 contact GT (P9-P33) does not exist yet; this kill "
                 "cannot be scored.  The match replay (production parity) and "
                 "the new-rally far-band census are reported for when it "
                 "lands:\n")
        if "fidelity" in m:
            f = m["fidelity"]
            L.append(f"* replay fidelity: {f['locked_mismatch']} locked / "
                     f"{f['center_mismatch']} centre mismatches over "
                     f"{f['frames']} frames.")
            L.append(f"* far-band new-rally segments: "
                     f"{m['far_band_new_rally_segments']}; would fire at L*: "
                     f"{len(m['would_fire_at_L_star'])}.")
        else:
            L.append("* match dump not found; kill 4 unmeasured.")
    L.append("")
    L.append("## Reading the result\n")
    L.append("A negative result here is the same class as T5 and R1: the "
             "far-serve CONTACT stays open, and the owner decides the next "
             "lever (targeted detector mining per #42 vs another mechanism). "
             "The secondary `behind_baseline` feature is reported above but "
             "was never used to move L*, so no threshold was fit to it.\n")
    return "\n".join(L)


def _fmt(v: Optional[float], nd: int = 3) -> str:
    return "None" if v is None else f"{v:.{nd}f}"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dev", default=DEFAULT_DEV)
    ap.add_argument("--match", default=DEFAULT_MATCH)
    ap.add_argument("--dev-gt", default=DEFAULT_DEV_GT)
    ap.add_argument("--dev-calibration", default=DEFAULT_DEV_CAL)
    ap.add_argument("--match-calibration", default=DEFAULT_MATCH_CAL)
    ap.add_argument("--config", default=None)
    ap.add_argument("--json", default="output/s1/far_serve_looming.json")
    ap.add_argument("--markdown", default="docs/g3_far_serve_looming.md")
    args = ap.parse_args(argv)

    report = run(dev=args.dev, match=args.match, dev_cal=args.dev_calibration,
                 match_cal=args.match_calibration, dev_gt=args.dev_gt,
                 config=args.config)
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(markdown(report))

    k1 = report["dev"]["kill1"]
    sep = report["separation"]
    print(f"S1 verdict: {report['verdict']['status']} - "
          f"{report['verdict']['reason']}")
    print(f"  kill 1: {k1['serves_meeting']}/{k1['serves_total']} serves "
          f"with >={k1['threshold_sightings']} far-band sightings")
    print(f"  kill 2: lowest far L {_fmt(sep['lowest_far_L'])} vs highest "
          f"non-serve L {_fmt(sep['highest_non_serve_L'])} "
          f"(gap {_fmt(sep['gap'])})")
    print(f"  kill 3: entreno fires {report['entreno']['kill3']['total']} "
          f"(evaluable {report['entreno']['kill3']['evaluable']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
