#!/usr/bin/env python3
"""M3' -- can a STRUCTURAL far-serve contact be recovered from the raw stream?

Reads the seek-free recording of ``scripts/probe_serve_events_seq.py`` (one
sequential pass, no decode) and sweeps a grid of candidate rules for the far
serve, against three negative sets:

* **17 GT far serves** -- the positives (5 dev P1-P8, 12 held-out P9-P33);
* **24 mid-rally non-serve contacts** -- false positives by construction;
* **6 owner FALSE frames + 4 owner OFFGAME ranges** -- the HARD negatives, from
  ``ground_truth/20260920_match_serve_anchors.txt``.  They are a player with a
  ball in dead time ("walking to the serve line with the ball in her hands",
  "throw from one near player to the server", "ball handling after the point
  ended"), i.e. physically the same situation as a far serve minus the toss and
  the hit.  A rule that cannot separate these is not a serve detector.

Why structural at all: the measured failure chain is that the far ball IS
detected (15-21 px in 14-31 of 31 frames at the serve, ``probe_far_roi_ball.py``)
but the tracker will not lock it (a far toss creeps 1.6-6.7 px/f under
``lock_min_speed = 8``) and the four contact-geometry tests cannot reach their
px thresholds at the far end (``docs/g4_far_serve_failure_mode.md``).  So the
proposal must not depend on the tracker or on the shape tests.

Rule axes (each optional, so the contribution of every one is measurable):

* ``gap``     -- no emitted contact in the previous N frames (the rally is
  opening).  Structural on this match: openers >= 153 f, mid-rally <= 134 f.
* ``occupant``-- a raw person box whose ground point classifies as ``runway``
  (behind/straddling the far line) near the contact.
* ``ball``    -- a ball-sized (8-60 px) raw detection on the FAR side of the net
  line near the contact.
* ``motion``  -- the discriminator, and the whole difficulty:
  ``none`` / ``approach`` (image-y descending while far side: the ball coming at
  the camera) / ``grow`` (apparent-width growth, the G4 ``far_flight`` idea) /
  ``speed`` (image speed floor: a ball in hands creeps, a served ball travels).
* ``bias``    -- frames subtracted from the motion onset to place the contact
  (the onset is post-contact by construction).

Pre-registered kills (from the owner's plan, session 53):

* K1 >= 12/17 far serves fired at +-15 f (production: 0/17);
* K2 <= 3/24 control FPs and <= 2/10 owner FALSE/OFFGAME FPs (precision >= 0.8);
* K3 the timing must be systematic: median |offset| small, not "somewhere in the
  window".

Usage::

    venv/bin/python scripts/sweep_structural_serve.py \
        --recording output/g4/serve_events_seq_recording.json
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.serve_events import ServeRunway  # noqa: E402

MATCH_GT = "ground_truth/20260920_match_contacts.json"
MATCH_CALIB = "calibrations/20260920_match_ari_joan_lost.json"
ANCHORS = "ground_truth/20260920_match_serve_anchors.txt"

BALL_W_MIN, BALL_W_MAX = 8, 60      # the venue's far/near ball range (AGENTS §5)
WINDOW_BEFORE, WINDOW_AFTER = 90, 60
TOLERANCE = 15


# --------------------------------------------------------------------------- data


def load_positives() -> List[Dict[str, Any]]:
    data = json.loads((ROOT / MATCH_GT).read_text())
    out = []
    for point in data["points"]:
        for event in point.get("events", []):
            if event.get("action") == "serve" and event.get("owner_side") == "far":
                out.append({"point": point["point"],
                            "frame": int(event["match_frame"]),
                            "held_out": point["point"] > 8})
    out.sort(key=lambda s: s["frame"])
    return out


def load_controls(limit: int = 24) -> List[Dict[str, Any]]:
    data = json.loads((ROOT / MATCH_GT).read_text())
    out = []
    for point in data["points"]:
        contacts = [c for c in point.get("events", [])
                    if c.get("action") not in ("serve", None)
                    and c.get("owner_side") not in (None, "")]
        if len(contacts) < 2:
            continue
        contact = contacts[len(contacts) // 2]
        out.append({"point": point["point"],
                    "frame": int(contact["match_frame"]),
                    "kind": contact.get("action"),
                    "held_out": point["point"] > 8})
        if len(out) >= limit:
            break
    return out


def load_owner_negatives() -> List[Dict[str, Any]]:
    """The owner's FALSE frames and OFFGAME ranges: a player with a ball, no serve."""
    text = (ROOT / ANCHORS).read_text()
    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^FALSE\s+(\d+)\s*(.*)$", line)
        if m:
            out.append({"frame": int(m.group(1)), "why": m.group(2)[:60],
                        "held_out": int(m.group(1)) > 5240})
            continue
        m = re.match(r"^OFFGAME\s+(\d+)-(\d+)\s*(.*)$", line)
        if m:
            out.append({"frame": (int(m.group(1)) + int(m.group(2))) // 2,
                        "range": [int(m.group(1)), int(m.group(2))],
                        "why": m.group(3)[:60],
                        "held_out": int(m.group(1)) > 5240})
    out.sort(key=lambda s: s["frame"])
    return out


# ----------------------------------------------------------------- rule machinery


class Replay:
    """All rule features over the recorded stream, computed once."""

    def __init__(self, recording: Dict[str, Any]) -> None:
        self.per_frame: Dict[int, Dict[str, Any]] = {
            int(k): v for k, v in recording["per_frame"].items()}
        self.actions = sorted(recording["actions"], key=lambda a: (a["frame"], a["seen_at"]))
        self.action_frames = [a["frame"] for a in self.actions]
        calib = json.loads((ROOT / MATCH_CALIB).read_text())
        self.runway = ServeRunway(calib["court_corners"], calib.get("midcourt_points"))

    # -- features ---------------------------------------------------------
    def prev_action(self, frame: int) -> Optional[int]:
        import bisect
        i = bisect.bisect_left(self.action_frames, frame)
        return self.action_frames[i - 1] if i else None

    def occupants(self, frame: int, lookback: int, regions: Sequence[str]) -> int:
        n = 0
        for f in range(frame - lookback, frame + 1):
            for person in self.per_frame.get(f, {}).get("people", ()):
                if person[5] in regions:
                    n += 1
        return n

    def ball_person_pairs(self, frame: int, lookback: int,
                          regions: Sequence[str]) -> List[Tuple[int, float, float, int, float]]:
        """``(frame, cx, cy, width, normalized_gap)`` for far-side ball sightings.

        ``normalized_gap`` is the distance from the ball centre to the nearest
        person box of an accepted region, in units of that person's bbox HEIGHT
        -- the same normalisation the G4 ``serve_candidate`` uses
        (``ball_gap_norm``).  It is the reach axis of the sweep: the G4
        conjunction's 1.0 rejects all 9 owner FALSE/OFFGAME negatives but also
        6 real serves, so the question is whether ANY value separates them.
        """
        people: List[Tuple[float, float, float, float]] = []
        for f in range(frame - lookback, frame + 1):
            for cx, yb, w, h, _conf, region in self.per_frame.get(f, {}).get("people", ()):
                if region in regions and h > 0:
                    people.append((cx, yb, w, float(h)))
        if not people:
            return []
        out = []
        for f in range(frame - lookback, frame + 1):
            for cx, cy, w, _conf in self.per_frame.get(f, {}).get("ball", ()):
                if not (BALL_W_MIN <= w <= BALL_W_MAX):
                    continue
                if not self.runway.is_far_side((cx, cy)):
                    continue
                best = None
                for pcx, pyb, pw, ph in people:
                    dx = max(abs(cx - pcx) - pw / 2.0, 0.0)
                    dy = max((pyb - ph) - cy, 0.0, cy - pyb)
                    gap = (dx * dx + dy * dy) ** 0.5 / ph
                    if best is None or gap < best:
                        best = gap
                if best is not None:
                    out.append((f, cx, cy, w, best))
        return out

    def far_balls(self, frame: int, lookback: int, min_w: int, max_w: int) -> List[Tuple[float, float, int]]:
        """Ball-sized raw detections on the FAR side of the net line, newest first."""
        out = []
        for f in range(frame - lookback, frame + 1):
            for cx, cy, w, _conf in self.per_frame.get(f, {}).get("ball", ()):
                if min_w <= w <= max_w and self.runway.is_far_side((cx, cy)):
                    out.append((f, cx, cy, w))
        return out

    def track(self, frame: int) -> Optional[Tuple[int, float, float, int]]:
        t = self.per_frame.get(frame, {}).get("ball_track")
        return None if not t else (frame, t[0], t[1], t[2])

    # -- motion discriminators -------------------------------------------
    def approach_onset(self, near: Sequence[Tuple[int, float, float, int]],
                       span: int, min_px: float) -> Optional[int]:
        """First frame of a monotone image-y descent (toward the camera).

        A ball carried in hands does not descend for ``span`` frames by
        ``min_px``; a ball hit at the far end crosses the frame while growing.
        """
        best: Optional[int] = None
        for i, (f, _cx, cy, _w) in enumerate(near):
            later = [(ff, cyy) for ff, _cx2, cyy, _w2 in near
                     if f < ff <= f + span]
            if len(later) < 2:
                continue
            y0 = cy
            ys = [y0] + [y for _f, y in later]
            if all(b >= a - 1.0 for a, b in zip(ys, ys[1:])) and ys[-1] - ys[0] >= min_px:
                if best is None or f < best:
                    best = f
            if f == near[-1][0]:
                break
        return best

    def grow_onset(self, frame: int, span: int, min_ratio: float) -> Optional[int]:
        """Apparent-width growth over ``span`` frames (the G4 far_flight idea),
        measured on the RAW detections, not on a tracker."""
        best: Optional[int] = None
        for f in range(frame - span, frame + 1):
            first = self._nearest_ball(f)
            last = self._nearest_ball(f + span)
            if not first or not last:
                continue
            if first[0] <= 0 or last[0] <= 0:
                continue
            if last[0] / first[0] >= min_ratio and self.runway.is_far_side((last[1], last[2])):
                if best is None or f < best:
                    best = f
        return best

    def _nearest_ball(self, frame: int) -> Optional[Tuple[int, float, float]]:
        balls = self.per_frame.get(frame, {}).get("ball", ())
        best = None
        for cx, cy, w, _conf in balls:
            if BALL_W_MIN <= w <= BALL_W_MAX and self.runway.is_far_side((cx, cy)):
                if best is None or w > best[0]:
                    best = (w, cx, cy)
        return best

    def speed_onset(self, near: Sequence[Tuple[int, float, float, int]],
                    min_px_f: float) -> Optional[int]:
        """First frame whose displacement to a later far-side sighting clears
        ``min_px_f`` per frame (a served ball travels; a carried ball creeps)."""
        best: Optional[int] = None
        for i, (f, cx, cy, _w) in enumerate(near):
            for ff, cx2, cy2, _w2 in near:
                if ff <= f:
                    continue
                span = ff - f
                if span and ((cx2 - cx) ** 2 + (cy2 - cy) ** 2) ** 0.5 / span >= min_px_f:
                    if best is None or f < best:
                        best = f
                    break
        return best

    def net_crossing(self, center: int, span: int = 120) -> Optional[int]:
        """The frame the ball crosses the NET line toward the camera.

        The strongest physical constraint available: a far serve is the LAST
        contact before the ball crosses the net, so ``net_gate`` keeps only the
        candidates before a crossing (and takes the last of them).  Built from
        the raw detections with continuity-by-proximity, so it needs no track.
        """
        lo, hi = center - span // 2, center + span // 2
        prev: Optional[Tuple[int, float, float]] = None
        for f in range(lo, hi + 1):
            best = None
            for cx, cy, w, _conf in self.per_frame.get(f, {}).get("ball", ()):
                if not (BALL_W_MIN <= w <= BALL_W_MAX):
                    continue
                if prev is None:
                    best = (f, cx, cy)
                else:
                    gap = ((cx - prev[1]) ** 2 + (cy - prev[2]) ** 2) ** 0.5
                    if gap <= 60 and (best is None or gap < best[0]):
                        best = (gap, f, cx, cy)  # type: ignore[assignment]
            if best is None:
                continue
            if len(best) == 4:
                _gap, f, cx, cy = best
            else:
                _f, cx, cy = best
            if prev is not None:
                was_far = self.runway.is_far_side((prev[1], prev[2]))
                now_near = not self.runway.is_far_side((cx, cy))
                if was_far and now_near and f - prev[0] <= 8:
                    return f
            prev = (f, cx, cy)
        return None


def fire(replay: Replay, center: int, rule: Dict[str, Any]) -> Optional[int]:
    """The contact frame this rule proposes for a window centred on ``center``.

    Returns None when the rule does not fire, else the proposed contact frame.
    """
    gap = rule["gap"]
    if gap is not None:
        prev = replay.prev_action(center)
        if prev is not None and center - prev <= gap:
            return None
    if rule["occupant_regions"]:
        if not replay.occupants(center, rule["occupant_lookback"],
                                rule["occupant_regions"]):
            return None
    reach = rule["reach"]
    if rule["occupant_regions"] and reach is not None:
        pairs = replay.ball_person_pairs(center, rule["ball_lookback"],
                                         rule["occupant_regions"])
        near = [p for p in pairs if p[4] <= reach]
    else:
        near = replay.far_balls(center, rule["ball_lookback"],
                                rule["ball_w_min"], rule["ball_w_max"])
    if not near:
        return None
    motion = rule["motion"]
    crossing = None
    if rule["net_gate"]:
        crossing = replay.net_crossing(center, rule["net_span"])
        if crossing is None:
            return None
    onsets = []
    if motion == "none":
        onsets = [near[-1][0]]
    elif motion == "approach":
        one = replay.approach_onset(near, rule["motion_span"], rule["motion_px"])
        onsets = [] if one is None else [one]
    elif motion == "grow":
        one = replay.grow_onset(center, rule["motion_span"], rule["motion_px"])
        onsets = [] if one is None else [one]
    elif motion == "speed":
        one = replay.speed_onset(near, rule["motion_px"])
        onsets = [] if one is None else [one]
    elif motion == "approach_all":
        # Every frame that starts a monotone descent -- the net gate then picks
        # the LAST one before the crossing (the serve is the last contact before
        # the ball crosses; a pre-serve handling pass is not).
        for entry in near:
            f, cy = entry[0], entry[2]
            later = [(ee[0], ee[2]) for ee in near if f < ee[0] <= f + rule["motion_span"]]
            ys = [cy] + [y for _ee, y in later]
            if len(ys) >= 3 and all(b >= a - 1.0 for a, b in zip(ys, ys[1:])) \
                    and ys[-1] - ys[0] >= rule["motion_px"]:
                onsets.append(f)
    if not onsets:
        return None
    if crossing is not None:
        before = [f for f in onsets if f <= crossing]
        if not before:
            return None
        onset = max(before)
    else:
        onset = min(onsets)
    if onset > center + rule["max_late"]:
        return None
    return onset - rule["bias"]


def evaluate(replay: Replay, rule: Dict[str, Any], positives, controls, negatives):
    hits, offsets, missed = 0, [], []
    per_positive = []
    for row in positives:
        got = fire(replay, row["frame"], rule)
        ok = got is not None and abs(got - row["frame"]) <= TOLERANCE
        per_positive.append({"point": row["point"], "frame": row["frame"],
                             "held_out": row["held_out"], "got": got, "hit": ok})
        if ok:
            hits += 1
            offsets.append(got - row["frame"])
        else:
            missed.append({"point": row["point"], "frame": row["frame"], "got": got})
    fp_control, fp_owner = [], []
    for row in controls:
        got = fire(replay, row["frame"], rule)
        if got is not None and abs(got - row["frame"]) <= TOLERANCE:
            fp_control.append({"point": row["point"], "frame": row["frame"], "got": got})
    for row in negatives:
        lo, hi = row.get("range", [row["frame"], row["frame"]])
        got = fire(replay, lo, rule)
        if got is not None and lo - TOLERANCE <= got <= hi + TOLERANCE:
            fp_owner.append({"frame": row["frame"], "got": got, "why": row["why"]})
    total_fp = len(fp_control) + len(fp_owner)
    precision = hits / (hits + total_fp) if hits + total_fp else 0.0
    return {
        "hits": hits, "n": len(positives),
        "held_out_hits": sum(1 for r in per_positive if r["hit"] and r["held_out"]),
        "dev_hits": sum(1 for r in per_positive if r["hit"] and not r["held_out"]),
        "offsets": sorted(offsets),
        "median_abs_offset": round(statistics.median([abs(o) for o in offsets]), 1) if offsets else None,
        "fp_control": len(fp_control), "fp_owner": len(fp_owner),
        "precision": round(precision, 3),
        "recall": round(hits / len(positives), 3) if positives else 0.0,
        "missed": missed, "fp_control_rows": fp_control, "fp_owner_rows": fp_owner,
        "per_positive": per_positive,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recording", default="output/g4/serve_events_seq_recording.json")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--min-precision", type=float, default=1.0)
    ap.add_argument("--out", default="output/g4/structural_serve_sweep.json")
    args = ap.parse_args()

    recording = json.loads((ROOT / args.recording).read_text())
    replay = Replay(recording)
    positives = load_positives()
    controls = load_controls()
    negatives = load_owner_negatives()
    print(f"{len(positives)} far serves, {len(controls)} mid-rally controls, "
          f"{len(negatives)} owner FALSE/OFFGAME negatives; "
          f"{len(replay.action_frames)} emitted contacts in the recording")

    results = []
    for gap in (90, 143, 180):
        for regions in (("runway",), ("runway", "court")):
            for reach in (None, 0.5, 1.0, 1.5, 2.5, 4.0):
                for motion in ("none", "approach_all", "grow"):
                    for px in ((40.0,) if motion == "approach_all" else
                               (1.6,) if motion == "grow" else (0.0,)):
                        for bias in (0, 4, 8):
                            for net_gate in (False, True):
                                rule = {
                                    "gap": gap, "occupant_regions": regions,
                                    "occupant_lookback": 15, "ball_lookback": 30,
                                    "ball_w_min": BALL_W_MIN, "ball_w_max": BALL_W_MAX,
                                    "reach": reach,
                                    "motion": motion, "motion_span": 15, "motion_px": px,
                                    "bias": bias, "max_late": 30,
                                    "net_gate": net_gate, "net_span": 120,
                                }
                                res = evaluate(replay, rule, positives, controls, negatives)
                                res["rule"] = rule
                                results.append(res)

    results.sort(key=lambda r: (-r["precision"], -r["recall"]))
    print(f"\n{len(results)} rule combinations; top {args.top} by hits with "
          f"precision >= {args.min_precision}:")
    print(f"{'gap':>5} {'occupant':>12} {'reach':>6} {'motion':>13} {'net':>4} {'bias':>4} | "
          f"{'hits':>7} {'dev':>4} {'held':>5} {'FPctl':>5} {'FPown':>5} {'prec':>5} {'|off|':>5}")
    shown = 0
    for res in results:
        if res["precision"] < args.min_precision:
            continue
        rule = res["rule"]
        occ = "+".join(rule["occupant_regions"]) or "-"
        print(f"{str(rule['gap']):>5} {occ:>12} {str(rule['reach']):>6} "
              f"{rule['motion']:>13} {int(rule['net_gate']):>4} {rule['bias']:>4} | "
              f"{res['hits']:>3}/{res['n']:<3} {res['dev_hits']:>4} "
              f"{res['held_out_hits']:>5} {res['fp_control']:>5} "
              f"{res['fp_owner']:>5} {res['precision']:>5} "
              f"{str(res['median_abs_offset']):>5}")
        shown += 1
        if shown >= args.top:
            break

    best = results[0]
    print("\nBEST BY PRECISION")
    print(json.dumps({k: v for k, v in best.items()
                      if k not in ("missed", "fp_control_rows", "fp_owner_rows",
                                   "per_positive")}, indent=1))
    print("missed:", json.dumps(best["missed"]))
    print("owner FP:", json.dumps(best["fp_owner_rows"], indent=1))
    print("control FP:", json.dumps(best["fp_control_rows"]))

    (ROOT / args.out).write_text(json.dumps({"results": results}, indent=1))
    print(f"wrote {ROOT / args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
