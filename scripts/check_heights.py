#!/usr/bin/env python3
"""V2: do the camera's heights deserve a "±0.2 m" label?

    venv/bin/python scripts/check_heights.py [output/postrun/20260920_match] \
        [--heights P1A=1.80,P2A=1.75,P1B=1.82,P2B=1.78]

Contact height (the net view of attack heights, brainstorm O3) comes from the
ball row against the sand at the ball's depth. There is no direct ground
truth of any ball height, so three indirect checks, read offline from the
diag dump + post-run output (no decode):

1. STATURE  a player's box height, scaled at their feet's depth, is a standing
            height. Per player, the near-half and far-half values must agree
            (the vertical scale is right at both depths); with --heights (the
            owner's real heights, metres) each must also be within 8 %.
2. NET      a ball crossing the net plane must clear the tape. The ball
            centre may sit at most the ball's radius plus read error below
            it: >= 90 % of crossings within 0.15 m under the tape or higher,
            none more than 0.40 m under. Only LIVE-ball crossings count (inside
            a post-run rally: a ball rolling across the net line in dead time
            sits on the sand, 2.3 m under the tape) and only WELL-CONDITIONED
            ones: the crossing frame comes from the depth fit (about +-0.7 m
            along the court), so a ball moving fast vertically while it
            crosses is read at the wrong height by timing alone. A crossing
            counts when that timing error is <= 0.15 m. (Both filters were added
            after the first run, which scored every crossing and failed on
            exactly these; the bars did not change and the unfiltered numbers
            are still printed.)
3. CONTACTS the median contact height of an action must be the same on the near
            and the far half (|difference| <= 0.20 m, actions with >= 8
            contacts on each side): the far half has the weaker depth.

PASS RULES are fixed here, before the first run. O3 may say "approximate
(±0.2 m)" only if every applicable check passes; otherwise it says what failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.postrun.ball_flights import BallTimeline  # noqa: E402
from src.postrun.geometry import BALL_DIAMETER_M, NET_Y_M, CourtGeometry  # noqa: E402
from src.postrun.stream import BALL_TRACKED, load_stream  # noqa: E402

SLOTS = ("P1A", "P2A", "P1B", "P2B")
DEPTH_ERR_M = 0.7             # along-court error of a fitted depth (geometry.BALL_ERR_FLOOR_M)
TIMING_ERR_MAX_M = 0.15       # a crossing is well-conditioned when timing alone moves its height <= this
STATURE_AGREE = 0.08          # near vs far, and vs the real height
NET_CLEAR_M = -0.15           # centre height above the tape that still counts as clearing
NET_BAD_M = -0.40
NET_SHARE = 0.90
CONTACT_DIFF_M = 0.20
CONTACT_MIN_N = 8
MIN_FLIGHT_SAMPLES = 4
FRAME_EDGE_PX = 3


# --------------------------------------------------------------------------- #
# 1. stature
# --------------------------------------------------------------------------- #

def stature(stream, geometry: CourtGeometry, frame_size: Tuple[int, int]) -> Dict[str, Dict[str, Any]]:
    """slot -> {"near": {...}, "far": {...}}: box height in metres at the feet's
    depth, 75th percentile (the upright frames: a crouch or a dive only lowers
    the box)."""
    w, h = frame_size
    heights: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    for frame_players in stream.players:
        for p in frame_players:
            if p.predicted or p.label not in SLOTS:
                continue
            x0, y0, x1, y1 = p.bbox
            if x0 <= FRAME_EDGE_PX or y0 <= FRAME_EDGE_PX or x1 >= w - FRAME_EDGE_PX or y1 >= h - FRAME_EDGE_PX:
                continue
            depth = geometry.foot_court_y(p.bbox)
            if depth is None or not -2.0 <= depth <= 18.0:
                continue
            scale = float(geometry.px_per_metre(depth))
            heights[(p.label, "near" if depth > NET_Y_M else "far")].append(p.height_px / scale)
    out: Dict[str, Dict[str, Any]] = {}
    for (slot, half), values in heights.items():
        v = np.asarray(values)
        out.setdefault(slot, {})[half] = {
            "n": int(v.size), "p50": float(np.percentile(v, 50)), "p75": float(np.percentile(v, 75)),
        }
    return out


def stature_verdict(stat: Dict[str, Dict[str, Any]], real: Optional[Dict[str, float]]) -> Dict[str, Any]:
    rows, ok = [], True
    for slot in SLOTS:
        halves = stat.get(slot, {})
        near, far = halves.get("near"), halves.get("far")
        if not near or not far:
            rows.append({"slot": slot, "note": "needs frames on both halves"})
            ok = False
            continue
        gap = abs(near["p75"] - far["p75"]) / ((near["p75"] + far["p75"]) / 2)
        row = {"slot": slot, "near": near["p75"], "far": far["p75"], "gap": gap, "agree": gap <= STATURE_AGREE}
        ok &= row["agree"]
        if real and slot in real:
            err = {half: stat[slot][half]["p75"] / real[slot] - 1 for half in ("near", "far")}
            row["vs_real"] = err
            row["real_ok"] = all(abs(e) <= STATURE_AGREE for e in err.values())
            ok &= row["real_ok"]
        rows.append(row)
    return {"rows": rows, "pass": ok, "with_real_heights": bool(real)}


# --------------------------------------------------------------------------- #
# 2. net crossings
# --------------------------------------------------------------------------- #

def net_crossings(stream, geometry: CourtGeometry, timeline: BallTimeline,
                  rallies: Optional[List[Tuple[int, int]]] = None) -> List[Dict[str, Any]]:
    """Centre height of the ball above the net tape at every flight that crosses
    the net plane (negative = under the tape). ``live`` marks a crossing inside
    a rally ``(start_frame, end_frame)``."""
    if geometry.net_top_points is None:
        raise SystemExit("the calibration has no net_top_points: cannot place the tape")
    scale = float(geometry.px_per_metre(NET_Y_M))
    x_lo, x_hi = sorted(float(x) for x in geometry.net_top_points[:, 0])
    out = []
    for fl in timeline.flights:
        if not fl.crosses_net or fl.n < MIN_FLIGHT_SAMPLES or fl.end <= fl.start:
            continue
        t = fl.start + (NET_Y_M - fl.y_start) / (fl.y_end - fl.y_start) * (fl.end - fl.start)
        best = None
        for f in range(int(round(t)) - 3, int(round(t)) + 4):
            if 0 <= f < stream.n_frames and stream.ball_state[f] == BALL_TRACKED \
                    and not timeline.clipped[f] and np.isfinite(stream.ball_xy[f, 0]):
                if best is None or abs(f - t) < abs(best - t):
                    best = f
        if best is None:
            continue
        u, v = stream.ball_xy[best]
        if not x_lo - 40 <= u <= x_hi + 40:           # past the tape's clicked ends
            continue
        v_tape = geometry.net_top_v_at(float(u))
        if v_tape is None:
            continue
        # What a wrong crossing time does: the ball's vertical speed times the
        # time its depth error is worth (depth error / court-axis speed).
        lo, hi = best - 2, best + 2
        if lo < 0 or hi >= stream.n_frames or not (np.isfinite(stream.ball_xy[lo, 1]) and np.isfinite(stream.ball_xy[hi, 1])):
            timing_err = float("inf")
        else:
            v_speed = abs(stream.ball_xy[hi, 1] - stream.ball_xy[lo, 1]) / 4.0 / scale       # m / frame
            axis_speed = abs(fl.y_end - fl.y_start) / (fl.end - fl.start)                      # m / frame
            timing_err = v_speed * DEPTH_ERR_M / max(axis_speed, 1e-6)
        out.append({"frame": int(best), "u": float(u), "clearance_m": float((v_tape - v) / scale),
                    "samples": int(fl.n), "timing_err_m": float(timing_err),
                    "live": rallies is None or any(a <= best <= b for a, b in rallies)})
    return out


MIN_NET_CROSSINGS = 20


def _net_stats(crossings: List[Dict[str, Any]]) -> Dict[str, Any]:
    c = np.asarray([x["clearance_m"] for x in crossings])
    return {"n": len(c), "share_clear": float((c >= NET_CLEAR_M).mean()), "worst_m": float(c.min()),
            "median_m": float(np.median(c)), "p10_m": float(np.percentile(c, 10))}


def net_verdict(crossings: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not crossings:
        return {"n": 0, "pass": False, "note": "no usable crossings"}
    live = [x for x in crossings if x["live"]]
    good = [x for x in live if x["timing_err_m"] <= TIMING_ERR_MAX_M]
    out: Dict[str, Any] = {"n": len(crossings), "all": _net_stats(crossings), "good": None,
                           "live": _net_stats(live) if live else None}
    if len(good) < MIN_NET_CROSSINGS:
        out.update({"pass": False, "note": f"only {len(good)} well-conditioned crossings (need {MIN_NET_CROSSINGS})"})
        return out
    out["good"] = _net_stats(good)
    out["pass"] = out["good"]["share_clear"] >= NET_SHARE and out["good"]["worst_m"] >= NET_BAD_M
    return out


# --------------------------------------------------------------------------- #
# 3. contact heights
# --------------------------------------------------------------------------- #

def contact_heights(recon: Dict[str, Any]) -> Dict[str, Any]:
    by_action: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    by_player: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    for p in recon["points"]:
        for t in p["touches"]:
            if t.get("height_m") is None or t.get("side") not in ("near", "far") or not t.get("observed"):
                continue
            by_action[(t["action"], t["side"])].append(float(t["height_m"]))
            if t.get("player") in SLOTS:
                by_player[(t["player"], t["action"])].append(float(t["height_m"]))
    rows, ok = [], True
    for action in sorted({a for a, _ in by_action}):
        near, far = by_action.get((action, "near"), []), by_action.get((action, "far"), [])
        row: Dict[str, Any] = {"action": action, "near_n": len(near), "far_n": len(far),
                               "near": median(near) if near else None, "far": median(far) if far else None}
        if len(near) >= CONTACT_MIN_N and len(far) >= CONTACT_MIN_N:
            row["diff"] = abs(row["near"] - row["far"])
            row["ok"] = row["diff"] <= CONTACT_DIFF_M
            ok &= row["ok"]
        rows.append(row)
    players = [{"slot": s, "action": a, "n": len(v), "median": median(v)}
               for (s, a), v in sorted(by_player.items()) if len(v) >= 5]
    return {"rows": rows, "players": players, "pass": ok and any("ok" in r for r in rows)}


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #

def report(stat_v, net_v, contact_v) -> str:
    lines = ["1. STATURE (75th percentile of box height at the feet's depth; bar: near vs far within "
             f"{STATURE_AGREE:.0%}" + (", and vs the real height" if stat_v["with_real_heights"] else "") + ")"]
    for r in stat_v["rows"]:
        if "note" in r:
            lines.append(f"   {r['slot']}: {r['note']}")
            continue
        extra = ""
        if "vs_real" in r:
            extra = f"   vs real: near {r['vs_real']['near']:+.1%}, far {r['vs_real']['far']:+.1%}"
        lines.append(f"   {r['slot']}: near {r['near']:.2f} m, far {r['far']:.2f} m, gap {r['gap']:.1%} "
                     f"{'ok' if r['agree'] else 'FAIL'}{extra}")
    if not stat_v["with_real_heights"]:
        lines.append("   (no --heights given: only the near/far self-check ran; give the four real heights for the absolute one)")
    lines.append(f"   -> {'PASS' if stat_v['pass'] else 'FAIL'}")
    lines.append("2. NET CROSSINGS (ball-centre height above the tape; bar: "
                 f">= {NET_SHARE:.0%} at or above {NET_CLEAR_M:+.2f} m, none below {NET_BAD_M:+.2f} m)")
    def net_line(label: str, st: Dict[str, Any]) -> str:
        return (f"   {label}: {st['n']} crossings, {st['share_clear']:.0%} clear, median {st['median_m']:+.2f} m, "
                f"10th percentile {st['p10_m']:+.2f} m, worst {st['worst_m']:+.2f} m")
    if net_v["n"]:
        lines.append(net_line("every crossing, dead time included", net_v["all"]))
        if net_v["live"]:
            lines.append(net_line("live ball (inside a rally)", net_v["live"]))
        if net_v["good"]:
            lines.append(net_line(f"live and well-conditioned (timing error <= {TIMING_ERR_MAX_M:.2f} m)", net_v["good"])
                         + f" -> {'PASS' if net_v['pass'] else 'FAIL'}")
        else:
            lines.append(f"   {net_v['note']} -> FAIL")
    else:
        lines.append(f"   {net_v['note']} -> FAIL")
    lines.append(f"3. CONTACT HEIGHTS (median per action, near vs far half; bar: within {CONTACT_DIFF_M:.2f} m "
                 f"with >= {CONTACT_MIN_N} contacts each side)")
    for r in contact_v["rows"]:
        near = "-" if r["near"] is None else f"{r['near']:.2f}"
        far = "-" if r["far"] is None else f"{r['far']:.2f}"
        verdict = "" if "ok" not in r else f"  diff {r['diff']:.2f} {'ok' if r['ok'] else 'FAIL'}"
        lines.append(f"   {r['action']:<9} near {near} m (n={r['near_n']}), far {far} m (n={r['far_n']}){verdict}")
    lines.append(f"   -> {'PASS' if contact_v['pass'] else 'FAIL'}")
    ok = stat_v["pass"] and net_v["pass"] and contact_v["pass"]
    lines.append("VERDICT: " + ("PASS -> O3 may say \"approximate (±0.2 m)\"" if ok else
                                "FAIL -> O3 may not claim ±0.2 m; show relative heights only (rounded to 0.1 m, "
                                "compared between players, no absolute claim)"))
    return "\n".join(lines)


def parse_heights(text: Optional[str]) -> Optional[Dict[str, float]]:
    if not text:
        return None
    out = {}
    for part in text.split(","):
        slot, _, value = part.partition("=")
        if slot.strip() not in SLOTS or not value:
            raise SystemExit(f"--heights wants P1A=1.80,P2A=...: got {part!r}")
        out[slot.strip()] = float(value)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_dir", nargs="?", default="output/postrun/20260920_match")
    ap.add_argument("--heights", help="owner's real heights in metres, e.g. P1A=1.80,P2A=1.75,P1B=1.82,P2B=1.78")
    args = ap.parse_args(argv)
    run = Path(args.run_dir)
    pipeline = json.loads((run / "pipeline_output.json").read_text())
    video = pipeline.get("video") or {}
    geometry = CourtGeometry.from_file(video["calibration_readiness"]["calibration_path"])
    frame_size = (int(video.get("width") or 1920), int(video.get("height") or 1080))
    print(f"loading {run}/diag.jsonl ...", flush=True)
    stream = load_stream(str(run / "diag.jsonl"), fps=video.get("fps"))
    timeline = BallTimeline(stream, geometry, frame_size)
    recon = json.loads((run / "match_reconstruction.json").read_text())

    stat_v = stature_verdict(stature(stream, geometry, frame_size), parse_heights(args.heights))
    rallies = [(int(p["start_frame"]), int(p["end_frame"])) for p in recon["points"]]
    net_v = net_verdict(net_crossings(stream, geometry, timeline, rallies))
    contact_v = contact_heights(recon)
    print(f"net tape from the calibration: {geometry.net_top_height_m():.2f} m "
          f"(ball radius {BALL_DIAMETER_M / 2:.3f} m)")
    print(report(stat_v, net_v, contact_v))
    return 0 if (stat_v["pass"] and net_v["pass"] and contact_v["pass"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
