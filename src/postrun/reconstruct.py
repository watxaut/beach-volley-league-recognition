"""Post-run reconstruction: stream -> points -> touches -> match.

    python -m src.postrun output/<video>/            # reads diag.jsonl there
    python -m src.postrun --diag run.jsonl --calibration calibrations/x.json

Reads the ``--diag-dump`` sidecar of a normal run (never the video) and
writes ``match_reconstruction.json``: one entry per point with its serve,
its touches (half, squad, player, action, touch number) and its winner, plus
the running score and the consistency checks.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .attack_shape import type_attacks
from .ball_flights import SOURCE_GAP, BallTimeline
from .geometry import CourtGeometry
from .match import SQUAD_LETTER, MatchAssembler, Point
from .positions import publish_positions
from .rallies import RallySegmenter
from .stream import MatchStream, load_stream
from .touches import SOURCE_ALTERNATION, Touch, TouchSolver

#: 2 = touches carry ``court_x_m`` + ``court_err_m``, ground ends ``court_xy_err_m``.
#: 3 = attacks carry ``spike_type`` + ``launch`` (attack_shape).
#: 4 = ``court_x_m`` / ``court_y_m`` / ``court_xy_m`` are the ``positions`` reads
#:     (net-anchored, box offset removed); ``positions`` says how they were made.
SCHEMA_VERSION = 4
logger = logging.getLogger(__name__)


def reconstruct(stream: MatchStream, geometry: CourtGeometry,
                frame_size=(1920, 1080), points_to_win: int = 21,
                switch_every: int = 7) -> Dict[str, Any]:
    timeline = BallTimeline(stream, geometry, frame_size=frame_size)
    rallies = RallySegmenter(timeline).segment()
    solver = TouchSolver(timeline)
    points: List[Point] = []
    for rally in rallies:
        touches, roster = solver.solve(rally)
        points.append(Point(rally=rally, touches=touches, roster=roster))
    checks = MatchAssembler(points_to_win=points_to_win,
                            switch_every=switch_every).assemble(points)
    for pt in points:                     # after the match layer: labels are final
        type_attacks(timeline, pt.touches)
    # Output only, after every decision: the same players must have played
    # both halves for the box offset to be read off the end switches.
    positions = publish_positions(
        timeline, points, switched=bool(checks.get("side_switch_after_point")))
    payload = [_point_payload(i + 1, pt) for i, pt in enumerate(points)]
    return {
        "schema_version": SCHEMA_VERSION,
        "fps": stream.fps,
        "n_frames": stream.n_frames,
        "geometry": {
            "ball_px_far_baseline": round(geometry.ball_px_far, 2),
            "ball_px_net": round(geometry.ball_px_net, 2),
            "ball_px_near_baseline": round(geometry.ball_px_near, 2),
            "net_top_height_m": _round(geometry.net_top_height_m(), 2),
        },
        "positions": positions.payload(),
        "checks": checks,
        "points": payload,
        "player_stats": player_stats(payload),
    }


#: Owner-ratified fantasy values (STATUS north-star G1). A block is not a
#: post-run label yet. Errors = service fault + attack error + ball handling
#: (a set or dig the layer marks ``error``, e.g. P6 f3229 -- open point 32f).
#: The web platform scores from its own rule table (supabase/migrations,
#: ``fantasy_rules``); ``src/publish/fantasy.py`` mirrors this G1 set.
FANTASY = {"kill": 1.0, "ace": 1.0, "dig": 1.0, "assist": 0.5, "error": -1.0}

#: Actions whose ``error`` outcome is a ball-handling error.
HANDLING_ACTIONS = ("set", "dig")


def player_stats(points: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Per-player counts over the touches CREDITED to a player.

    Precision first (owner rule): a touch the stream did not see, or one with
    nobody plausibly at the ball, is in the point's touch list but in nobody's
    stats. ``uncredited`` says how many observed touches that leaves out.
    """
    stats: Dict[str, Dict[str, Any]] = {}
    uncredited = 0

    def row(player: str) -> Dict[str, Any]:
        return stats.setdefault(player, {k: 0 for k in (
            "serves", "aces", "serve_errors", "digs", "sets", "assists",
            "spikes", "overpasses", "kills", "attack_errors", "handling_errors")})

    for pt in points:
        serve = pt["serve"]
        if serve["player"]:
            r = row(serve["player"])
            r["serves"] += 1
            r["aces"] += serve["outcome"] == "ace"
            r["serve_errors"] += serve["outcome"] == "error"
        body = [t for t in pt["touches"] if t["touch_number"] > 0]
        for i, t in enumerate(body):
            if not t["observed"]:
                continue
            if not t["player"]:
                uncredited += 1
                continue
            r = row(t["player"])
            key = {"dig": "digs", "set": "sets", "spike": "spikes",
                   "overpass": "overpasses"}.get(t["action"])
            if key:
                r[key] += 1
            attack = t["action"] in ("spike", "overpass")
            r["kills"] += attack and t["outcome"] == "kill"
            r["attack_errors"] += attack and t["outcome"] == "error"
            r["handling_errors"] += (t["action"] in HANDLING_ACTIONS
                                     and t["outcome"] == "error")
            nxt = body[i + 1] if i + 1 < len(body) else None
            if (t["action"] == "set" and nxt is not None and nxt["observed"]
                    and nxt["side"] == t["side"] and nxt["outcome"] == "kill"):
                r["assists"] += 1
    for r in stats.values():
        r["fantasy"] = round(
            FANTASY["kill"] * r["kills"] + FANTASY["ace"] * r["aces"]
            + FANTASY["dig"] * r["digs"] + FANTASY["assist"] * r["assists"]
            + FANTASY["error"] * (r["attack_errors"] + r["serve_errors"]
                                  + r["handling_errors"]), 1)
    out: Dict[str, Dict[str, Any]] = dict(sorted(stats.items()))
    out["_uncredited_observed_touches"] = {"count": uncredited}
    return out


def _clock(frame: int, fps: float) -> str:
    seconds = int(frame / fps)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def format_report(result: Dict[str, Any]) -> str:
    """Play-by-play text of a reconstruction (what the owner reads)."""
    fps = result["fps"]
    checks = result["checks"]
    lines = [
        f"Points {checks['points']}   final score {checks['final_score']}   "
        f"set complete: {checks['set_complete']}",
        f"Side switches after points {checks['side_switch_after_point']} "
        f"(points per block {checks['points_between_switches']})",
        "",
    ]
    for pt in result["points"]:
        serve = pt["serve"]
        score = pt["score_after"]
        lines.append(
            f"P{pt['point']:<2} {_clock(pt['start_frame'], fps)} f{pt['start_frame']}-"
            f"{pt['end_frame']}  {serve['team'] or '?'} serves from the {serve['side']} "
            f"half  ->  {pt['winner'] or '?'} wins ({pt['winner_source']})  "
            f"A {score.get('A', 0)} - B {score.get('B', 0)}"
            + (f"  [{', '.join(pt['flags'])}]" if pt["flags"] else ""))
        for t in pt["touches"]:
            who = t["player"] or ("(not credited)" if t["observed"] else "(unseen)")
            if t["player"] and t.get("player_source") == SOURCE_ALTERNATION:
                who += " (by alternation)"
            tag = f" {t['outcome'].upper()}" if t.get("outcome") else ""
            if t.get("spike_type"):
                tag += f"  ({t['spike_type']})"
            lines.append(f"      f{t['frame']:<6} {t['team'] or '?'} {t['action']:<8} "
                         f"{who}{tag}")
    lines.append("")
    lines.append(f"{'player':<8}{'srv':>4}{'ace':>4}{'sErr':>5}{'dig':>4}{'set':>4}"
                 f"{'ast':>4}{'spk':>4}{'ovr':>4}{'kill':>5}{'aErr':>5}{'hErr':>5}"
                 f"{'fantasy':>8}")
    for player, r in result["player_stats"].items():
        if player.startswith("_"):
            continue
        lines.append(f"{player:<8}{r['serves']:>4}{r['aces']:>4}{r['serve_errors']:>5}"
                     f"{r['digs']:>4}{r['sets']:>4}{r['assists']:>4}{r['spikes']:>4}"
                     f"{r['overpasses']:>4}{r['kills']:>5}{r['attack_errors']:>5}"
                     f"{r['handling_errors']:>5}{r['fantasy']:>8}")
    lines.append(f"observed touches not credited to anyone: "
                 f"{result['player_stats']['_uncredited_observed_touches']['count']}")
    return "\n".join(lines) + "\n"


def _round(value: Optional[float], digits: int) -> Optional[float]:
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), digits)


def _err(err) -> Optional[List[float]]:
    """(across, along) position error in metres, or None when unknown."""
    if err is None or not all(np.isfinite(v) for v in err):
        return None
    return [round(float(err[0]), 2), round(float(err[1]), 2)]


def _letter(squad: Optional[int]) -> Optional[str]:
    return SQUAD_LETTER.get(squad) if squad is not None else None


def _evidence(t: Touch) -> str:
    """What the touch rests on: a trajectory vertex the stream saw, a
    trajectory change across a short tracking gap, or the rally structure
    alone (never credited to a player)."""
    if not t.observed:
        return "structure"
    if t.event is not None and t.event.source == SOURCE_GAP:
        return "gap"
    return "vertex"


def _touch_payload(pt: Point, t: Touch) -> Dict[str, Any]:
    return {
        "frame": int(t.frame),
        "action": t.action,
        "side": t.side,
        "team": _letter(pt.squad_on(t.side)),
        "player": t.player,
        "player_source": t.player_source,
        "touch_number": int(t.touch_number),
        "observed": bool(t.observed),
        "evidence": _evidence(t),
        "ends_possession": bool(t.ends_possession),
        "outcome": t.outcome,
        "height_m": _round(t.height_m, 2),
        "court_x_m": _round(t.pos_x, 1),
        "court_y_m": _round(t.pos_y, 1),
        "court_err_m": _err(t.pos_err),
        "reach_body_heights": _round(t.reach, 2),
        "perception_action": t.perception_action,
        "spike_type": t.spike_type,
        "launch": _launch_payload(t),
    }


def _launch_payload(t: Touch) -> Optional[Dict[str, Any]]:
    if t.launch is None:
        return None
    return {
        "frame": int(t.launch.frame),
        "samples": int(t.launch.samples),
        "speed_ms": _round(t.launch.speed_ms, 1),
        "rise_ms": _round(t.launch.rise_ms, 1),
        "elevation_deg": _round(t.launch.elevation_deg, 1),
        "elevation_ends_deg": _round(t.launch.elevation_ends_deg, 1),
    }


def _point_payload(index: int, pt: Point) -> Dict[str, Any]:
    end = pt.rally.end
    return {
        "point": index,
        "start_frame": int(pt.rally.start_frame),
        "end_frame": int(pt.rally.end_frame),
        "near_team": _letter(pt.near_squad),
        "serve": {
            "frame": int(pt.rally.serve.frame),
            "side": pt.rally.serve.side,
            "team": _letter(pt.serve_squad),
            "player": pt.touches[0].player,
            "player_source": pt.touches[0].player_source,
            "outcome": pt.touches[0].outcome,
            "observed": bool(pt.rally.serve.observed),
            "inferred": bool(pt.rally.serve.inferred),
            "into_net": bool(pt.rally.serve.into_net),
        },
        "end": None if end is None else {
            "kind": end.kind,
            "frame": int(end.frame),
            "side": end.side,
            "in_court": end.in_court,
            "court_xy_m": None if end.pos_xy is None else [
                _round(end.pos_xy[0], 1), _round(end.pos_xy[1], 1)],
            "court_xy_err_m": _err(end.pos_xy_err),
        },
        "winner": _letter(pt.winner_squad),
        "winner_source": pt.winner_source,
        "ball_death_read": {
            "winner": _letter(pt.squad_on(pt.death_winner_side)),
            "reason": pt.death_reason,
        },
        "score_after": {SQUAD_LETTER[k]: v for k, v in pt.score_after.items()},
        "flags": list(pt.flags),
        "touches": [_touch_payload(pt, t) for t in pt.touches],
    }


def _resolve_inputs(args: argparse.Namespace) -> Dict[str, Any]:
    out_dir = Path(args.output_dir) if args.output_dir else None
    diag = Path(args.diag) if args.diag else (out_dir / "diag.jsonl" if out_dir else None)
    if diag is None or not diag.exists():
        raise SystemExit(f"diag dump not found ({diag}); run src.main with --diag-dump")
    payload: Dict[str, Any] = {}
    pipeline = Path(args.pipeline_output) if args.pipeline_output else (
        diag.parent / "pipeline_output.json")
    if pipeline.exists():
        with open(pipeline) as f:
            payload = json.load(f)
    video = payload.get("video") or {}
    calibration = args.calibration or (video.get("calibration_readiness") or {}).get(
        "calibration_path")
    if not calibration or not Path(calibration).exists():
        raise SystemExit("court calibration not found; pass --calibration")
    frame_size = (int(video.get("width") or 1920), int(video.get("height") or 1080))
    return {"diag": diag, "calibration": calibration, "fps": video.get("fps"),
            "frame_size": frame_size,
            "out": Path(args.out) if args.out else diag.parent / "match_reconstruction.json"}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("output_dir", nargs="?", help="run directory holding diag.jsonl "
                        "and pipeline_output.json")
    parser.add_argument("--diag", help="--diag-dump JSONL of the run")
    parser.add_argument("--pipeline-output", help="pipeline_output.json of the run")
    parser.add_argument("--calibration", help="court calibration JSON")
    parser.add_argument("--out", help="where to write match_reconstruction.json")
    parser.add_argument("--points-to-win", type=int, default=21)
    parser.add_argument("--switch-every", type=int, default=7,
                        help="points between side switches (7 for sets to 21)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    inputs = _resolve_inputs(args)
    stream = load_stream(str(inputs["diag"]), fps=inputs["fps"])
    geometry = CourtGeometry.from_file(inputs["calibration"])
    result = reconstruct(stream, geometry, frame_size=inputs["frame_size"],
                         points_to_win=args.points_to_win,
                         switch_every=args.switch_every)
    result["inputs"] = {"diag": str(inputs["diag"]),
                        "calibration": str(inputs["calibration"])}
    with open(inputs["out"], "w") as f:
        json.dump(result, f, indent=1)
    report_path = Path(inputs["out"]).with_suffix(".txt")
    report_path.write_text(format_report(result))
    checks = result["checks"]
    logger.info("points: %s  final score: %s  set complete: %s",
                checks["points"], checks["final_score"], checks["set_complete"])
    logger.info("side switches after points %s (blocks %s)",
                checks["side_switch_after_point"], checks["points_between_switches"])
    if checks["flagged_points"]:
        logger.info("flagged: %s", checks["flagged_points"])
    logger.info("written: %s (+ %s)", inputs["out"], report_path.name)
    return 0
