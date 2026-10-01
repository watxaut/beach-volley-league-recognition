#!/usr/bin/env python3
"""Possession-signal probe -- offline A/B of the parked mechanisms.

The possession signal (open point 9 enabler) was built, wired, and REFUTED as
a needle-mover in session 52 (2026-10-01); the mechanisms live default-OFF in
``scripts/possession_signal_harness.py``, never in ``src/`` (T5/R1 rule).

This probe is the reproducible evidence.  It replays the REAL
``ActionClassifier._attribution_target`` + ``_closest_player_at`` (via the
harness subclasses) against the 20260920 match diag dump, which carries the
per-frame player boxes and the ball track/detections the pipeline already
computed, plus the raw contact inputs (``candidate_passed_gates``).  No video
decode, no pipeline run, no ``src/`` change.

For every raw contact it picks the toucher under four arms and scores the
selected player's court SIDE against the owner GT side (near/far):

* ``base``   -- production attribution (both mechanisms OFF);
* ``trend``  -- + ball-field width-trend arriving side;
* ``motion`` -- + motion-convergence tie-break;
* ``both``   -- the two together.

Caveat (recorded, not hidden): the dump is the R1 ``bw=0.3`` run, whose
departure gate differs; its PLAYER boxes and ball track are gate-independent,
and only the contacts that passed that gate are replayable (5 GT overpasses
are absent, consistent with the G1 "missed" set).  The replay also cannot
reproduce the gesture read (poses are not in the dump), so the possession
memory for the carry/flip branch is taken from the PRODUCTION stream's
previous action (attack/block/serve => went over).

Verdict (157 GT-side contacts): base 121/157 (0.771) -> both 122/157 (0.777);
trend fires 11x, 11/11 correct side but mostly redundant; motion changes no
team attribution.  See ``docs/g3_possession_signal.md``.

Usage (defaults reproduce the doc)::

    venv/bin/python scripts/probe_possession_signal.py
"""

from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_left
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.detection.court_calibration import CourtCalibration  # noqa: E402
from src.recognition.action_classifier import ActionClassifier  # noqa: E402
from possession_signal_harness import (  # noqa: E402
    MotionTiebreakClassifier,
    PossessionSignalClassifier,
    WidthTrendClassifier,
)

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DIAG = "output/g3r1/match_bw03_diag.jsonl"
DEFAULT_CAL = "calibrations/20260920_match_ari_joan_lost.json"
DEFAULT_GT = "ground_truth/20260920_match_contacts.json"
DEFAULT_RELABEL = "output/serve_relabel.json"
DEFAULT_JSON = "output/possession_signal/possession_signal.json"
DEFAULT_REPORT = "docs/g3_possession_signal.md"
TOL = 15

ARMS = ("base", "trend", "motion", "both")


class _StubPose:
    """Pose estimator stand-in: the dump has no poses and attribution never
    reads them (only box geometry + motion history)."""

    def estimate_poses_batch(self, frame: Any, detections: Any) -> List[Any]:
        return [None] * len(detections)

    def estimate_pose(self, frame: Any, bbox: Any) -> None:
        return None


# ----------------------------------------------------------------------
# dump + geometry helpers
# ----------------------------------------------------------------------

def load_dump(path: str) -> Tuple[Dict[int, Dict[str, Any]], List[Dict[str, Any]]]:
    """``(frames, contacts)`` -- per-frame records + raw contact inputs."""
    frames: Dict[int, Dict[str, Any]] = {}
    contacts: List[Dict[str, Any]] = []
    with open(path) as fh:
        for line in fh:
            d = json.loads(line)
            f = d.get("frame")
            if f is None:
                continue
            frames[int(f)] = d
            for c in d.get("candidates") or []:
                if c.get("stage") == "candidate_passed_gates":
                    contacts.append(c)
    return frames, sorted(contacts, key=lambda c: int(c["frame"]))


def ball_width(rec: Dict[str, Any]) -> Optional[float]:
    """Detected ball width (px) for one dump frame, or None (never guessed)."""
    bt = rec.get("ball_track") or {}
    if not bt.get("locked") or not bt.get("center"):
        return None
    cx, cy = bt["center"]
    for det in rec.get("ball_dets") or []:
        c = det.get("center")
        if c and abs(c[0] - cx) < 1.0 and abs(c[1] - cy) < 1.0:
            b = det.get("bbox")
            if b and len(b) == 4:
                return float(b[2] - b[0])
    return None


def side_of_team(team: Optional[str]) -> Optional[str]:
    """Court side (A=near, B=far) from a team letter (the stack's convention)."""
    return None if team is None else team


class _PrevAction:
    """Previous production action lookup (for the possession memory)."""

    def __init__(self, actions: Sequence[Dict[str, Any]]) -> None:
        self.actions = sorted(actions, key=lambda a: int(a["frame_number"]))
        self.frames = [int(a["frame_number"]) for a in self.actions]

    def before(self, frame: int) -> Optional[Dict[str, Any]]:
        i = bisect_left(self.frames, frame)
        return self.actions[i - 1] if i > 0 else None


def _went_over(prev: Optional[Dict[str, Any]]) -> bool:
    if prev is None:
        return False
    if prev.get("action") == "serve":
        return True
    return prev.get("gesture") in ("attack", "block")


# ----------------------------------------------------------------------
# replay
# ----------------------------------------------------------------------

def replay(clf: ActionClassifier, frames: Dict[int, Dict[str, Any]],
           contacts: Sequence[Dict[str, Any]], court: CourtCalibration,
           prev: _PrevAction, back: int = 120) -> List[Dict[str, Any]]:
    """Replay attribution for every raw contact; returns per-contact rows."""
    rows: List[Dict[str, Any]] = []
    last: Optional[Tuple[str, int, bool]] = None
    for c in contacts:
        f = int(c["frame"])
        clf._ball_history.clear()
        for g in range(f - back, f):
            rec = frames.get(g)
            if not rec:
                continue
            w = ball_width(rec)
            bt = rec.get("ball_track") or {}
            if w is not None and bt.get("center"):
                cx, cy = bt["center"]
                clf._ball_history.append((g, cx, cy, w, w))
        clf._player_pose_history.clear()
        for g in range(max(0, f - 40), f + 1):
            rec = frames.get(g)
            if not rec:
                continue
            for p in rec.get("players") or []:
                tid = p.get("track_id")
                if tid is None or p.get("center") is None:
                    continue
                clf._player_pose_history.setdefault(tid, []).append({
                    "frame": g, "pose": None, "center": p.get("center"),
                    "bbox": p.get("bbox"), "team": p.get("team"),
                    "predicted": p.get("predicted"),
                })
        if last is not None:
            clf._last_touch_team, clf._last_touch_frame, clf._last_touch_went_over = last

        target, info = clf._attribution_target(f)
        chosen = clf._closest_player_at(f, c.get("contact_point") or [0.0, 0.0], target)
        team = None
        if chosen is not None:
            snap, _dist, _lr = chosen
            bbox = snap.get("bbox")
            team = (court.get_team_for_bbox(bbox) if bbox else None) or snap.get("team")

        pa = prev.before(f)
        rows.append({
            "frame": f,
            "point": c.get("point"),
            "kind": c.get("kind"),
            "team": team,
            "target": target,
            "source": info.get("source"),
            "trend_dln": info.get("trend_dln"),
            "prev_action": None if pa is None else pa.get("action"),
            "prev_team": None if pa is None else pa.get("team"),
        })
        last = (pa.get("team"), pa.get("frame_number"), _went_over(pa)) if pa else None
    return rows


def score(rows: Sequence[Dict[str, Any]], gt_by_frame: Dict[int, Dict[str, Any]],
          tol: int = TOL) -> Dict[str, Any]:
    """Team-side accuracy of the selected toucher vs the owner GT side."""
    n = ok = 0
    misses: List[Dict[str, Any]] = []
    trend_fires: List[Dict[str, Any]] = []
    for r in rows:
        f = int(r["frame"])
        cand = [g for g in gt_by_frame if abs(g - f) <= tol]
        gtf = min(cand, key=lambda g: abs(g - f)) if cand else None
        if gtf is None or r["team"] is None:
            continue
        want = {"near": "A", "far": "B"}.get(gt_by_frame[gtf].get("owner_side"))
        if want is None:
            continue
        n += 1
        if r["team"] == want:
            ok += 1
        else:
            misses.append({"frame": f, "gt_frame": gtf, "point": r["point"],
                           "team": r["team"], "want": want, "source": r["source"]})
        if r["source"] == "width_trend":
            trend_fires.append({"frame": f, "gt_frame": gtf, "team": r["team"],
                                "want": want, "dln": r["trend_dln"],
                                "gt_action": (gt_by_frame[gtf].get("final_action")
                                              or gt_by_frame[gtf].get("action"))})
    return {"n": n, "correct": ok, "accuracy": round(ok / n, 4) if n else None,
            "misses": misses, "trend_fires": trend_fires}


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def build_arms(court: CourtCalibration) -> Dict[str, ActionClassifier]:
    common = dict(pose_estimator=_StubPose(), confidence_threshold=0.3,
                  court_calibration=court)
    return {
        "base": ActionClassifier(**common),
        "trend": WidthTrendClassifier(width_trend_enabled=True, **common),
        "motion": MotionTiebreakClassifier(motion_tiebreak_enabled=True, **common),
        "both": PossessionSignalClassifier(width_trend_enabled=True,
                                           motion_tiebreak_enabled=True, **common),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--diag", default=DEFAULT_DIAG)
    ap.add_argument("--calibration", default=DEFAULT_CAL)
    ap.add_argument("--gt", default=DEFAULT_GT)
    ap.add_argument("--relabel", default=DEFAULT_RELABEL)
    ap.add_argument("--json", default=DEFAULT_JSON)
    ap.add_argument("--report", default=DEFAULT_REPORT)
    args = ap.parse_args(argv)

    court = CourtCalibration(args.calibration)
    if not court.is_calibrated:
        raise SystemExit(f"Error: calibration not usable: {args.calibration}")
    frames, contacts = load_dump(args.diag)
    gt_blob = json.loads(Path(args.gt).read_text())
    gt_by_frame = {
        int(e["frame"]): e
        for e in gt_blob["annotated_frames"]["actions"]["events"]
        if e.get("frame") is not None and e.get("owner_side")
    }
    relabel = json.loads(Path(args.relabel).read_text())
    prev = _PrevAction(relabel.get("actions_pass2") or [])

    result: Dict[str, Any] = {
        "sources": {"diag": args.diag, "calibration": args.calibration,
                    "gt": args.gt, "relabel": args.relabel},
        "n_raw_contacts": len(contacts),
        "n_gt_side_contacts": len(gt_by_frame),
        "arms": {},
    }
    for name, clf in build_arms(court).items():
        rows = replay(clf, frames, contacts, court, prev)
        result["arms"][name] = score(rows, gt_by_frame)

    base = result["arms"]["base"]
    both = result["arms"]["both"]
    result["verdict"] = {
        "base_accuracy": base["accuracy"],
        "both_accuracy": both["accuracy"],
        "delta_correct": both["correct"] - base["correct"],
        "trend_fires": len(both["trend_fires"]),
        "trend_fires_correct": sum(1 for t in both["trend_fires"] if t["team"] == t["want"]),
        "refuted": (both["correct"] - base["correct"]) <= 1,
    }

    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    report = render_report(result)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(report)
    print(report)
    print(f"[wrote {out}]")
    return 0


def render_report(result: Dict[str, Any]) -> str:
    lines = [
        "# Possession-signal probe — offline A/B (no `src/` change)",
        "",
        "Mechanisms parked default-OFF in `scripts/possession_signal_harness.py`;",
        "replayed through the REAL `ActionClassifier` attribution methods against",
        f"`{result['sources']['diag']}` ({result['n_raw_contacts']} raw contacts).",
        "",
        "| arm | correct | n | accuracy |",
        "|---|---:|---:|---:|",
    ]
    for name in ARMS:
        a = result["arms"].get(name)
        if a:
            lines.append(f"| {name} | {a['correct']} | {a['n']} | {a['accuracy']} |")
    v = result["verdict"]
    lines += [
        "",
        f"**Verdict:** base {v['base_accuracy']} → both {v['both_accuracy']} "
        f"(delta {v['delta_correct']:+d}); trend fires {v['trend_fires']}x, "
        f"{v['trend_fires_correct']} on the correct side. "
        f"{'REFUTED as a needle-mover.' if v['refuted'] else 'SURVIVES.'}",
        "",
        "## Reading the result",
        "",
        "The ball-field trend is PRECISE but mostly REDUNDANT: it fires only on",
        "strict-abstain contacts and names the right arriving side, yet the base",
        "attribution already resolves most of them by other means. The carry",
        "errors it was meant to fix mostly have NO ball signal at all (ball lost",
        "mid-flight), which no ball-field rule can recover. The motion tie-break",
        "changes only same-team actor picks — zero team attribution. Hence the",
        "mechanisms are parked in the harness (T5/R1 precedent): no config key,",
        "ctor signature or drift-guard surface in `src/`.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
