"""Build the match bundle: one JSON document per match, everything the web
needs from a finished run (docs/web_platform_design.md §3).

Pure: reads ``output/<key>/match_reconstruction.json`` (required) and, when
present, ``pipeline_output.json`` (video facts, causal spike zones) and
``source.json`` (the inbox runner's Drive link). Never decodes video, never
talks to the network. Point / action keys are the database COLUMN names --
``ingest_match_bundle`` inserts them with ``jsonb_populate_recordset``.

Credit rule (the one that keeps the web equal to the owner-ratified
``postrun.player_stats``): an action carries a ``slot`` exactly when
player_stats credits it -- a named server always (service-order servers
included), a rally touch only when it was observed. Every stat in SQL counts
``slot IS NOT NULL`` rows only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.postrun.geometry import COURT_LENGTH_M, COURT_WIDTH_M, SIDE_NEAR

from .naming import MatchKeyError, parse_match_key

BUNDLE_VERSION = 1
SLOTS = ("P1A", "P2A", "P1B", "P2B")
ACTIONS = ("serve", "dig", "set", "spike", "overpass", "block", "ball_handling")
ATTACKS = ("spike", "overpass")
#: What became of an attack (``landing_result``); None = the run cannot tell.
LANDING_RESULTS = ("kill", "dug", "out", "net", "error")
#: Causal SpikeAnalyzer record <-> post-run attack touch: same vertex, so the
#: frames normally agree; ±15 f is the contact-scoring tolerance.
SPIKE_JOIN_FRAMES = 15


class BundleError(ValueError):
    """The run directory cannot produce a valid bundle."""


# --------------------------------------------------------------------------- #
# geometry helpers: camera frame -> the acting team's own frame
# --------------------------------------------------------------------------- #

def to_own_frame(x: Optional[float], y: Optional[float],
                 side: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Camera-frame court metres (x 0..8 image-left -> right, y 0 far
    baseline .. 16 near baseline) -> the frame of a player on ``side``
    standing at their own baseline facing the net: y = metres from their own
    baseline (8 = net, 16 = the opponents' baseline), x = metres from their
    left sideline. Teams switch ends every 7 points; heatmaps need this."""
    if side is None:
        return None, None
    near = side == SIDE_NEAR
    own_y = None if y is None else round((COURT_LENGTH_M - y) if near else y, 2)
    own_x = None if x is None else round(x if near else (COURT_WIDTH_M - x), 2)
    return own_x, own_y


def _zone(z: Any) -> Optional[int]:
    """1-9 zone number from ``{"side": "A", "zone": 2}`` (in-memory spike record)
    or the ``"A2"`` label that ``pipeline_output.json`` stores."""
    if isinstance(z, str) and len(z) == 2 and z[0] in "AB" and z[1].isdigit():
        z = {"zone": int(z[1])}
    if isinstance(z, dict) and isinstance(z.get("zone"), int) and 1 <= z["zone"] <= 9:
        return z["zone"]
    return None


def _nearest_spike(frame: int, spikes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    best, best_d = None, SPIKE_JOIN_FRAMES + 1
    for s in spikes:
        f = s.get("frame")
        if f is None:
            continue
        d = abs(int(f) - frame)
        if d < best_d:
            best, best_d = s, d
    return best


# --------------------------------------------------------------------------- #
# rows
# --------------------------------------------------------------------------- #

def _assist_flags(touches: List[Dict[str, Any]]) -> List[bool]:
    """``is_assist`` per touch, the postrun.player_stats rule: a set whose
    NEXT rally touch is observed, on the same half, and a kill."""
    flags = [False] * len(touches)
    body = [(i, t) for i, t in enumerate(touches) if t["touch_number"] > 0]
    for k, (i, t) in enumerate(body):
        if not t["observed"] or t["action"] != "set":
            continue
        nxt = body[k + 1][1] if k + 1 < len(body) else None
        if (nxt is not None and nxt["observed"] and nxt["side"] == t["side"]
                and nxt.get("outcome") == "kill"):
            flags[i] = True
    return flags


def _credited_slot(t: Dict[str, Any]) -> Optional[str]:
    player = t.get("player")
    if player not in SLOTS:
        return None
    if t["touch_number"] == 0 or t["action"] == "serve":
        return player
    return player if t["observed"] else None


def _err(err: Any) -> Tuple[Optional[float], Optional[float]]:
    """``[across, along]`` metres from the reconstruction (schema >= 2)."""
    if isinstance(err, (list, tuple)) and len(err) == 2:
        return err[0], err[1]
    return None, None


def _landing_result(t: Dict[str, Any], nxt: Optional[Dict[str, Any]],
                    end: Optional[Dict[str, Any]]) -> Optional[str]:
    """What became of an attack. ``out`` and ``net`` are only said when the
    run saw it (ball-death line call / net stop); an attack error it cannot
    place is a plain ``error``, and a ball nobody ruled on is None."""
    if t.get("outcome") == "kill":
        return "kill"
    if nxt is not None:
        return "dug" if nxt["side"] != t["side"] else None
    if t.get("outcome") != "error":
        return None
    kind = (end or {}).get("kind")
    if kind == "net":
        return "net"
    if kind == "ground" and (end or {}).get("in_court") is False:
        return "out"
    return "error"


def _landing(i: int, touches: List[Dict[str, Any]],
             end: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Where an attack came down, in the ATTACKER's own frame: where the
    other half played it (``next_touch``, the ball at that touch), else the
    point's ball-death read (``ball_death``; line calls are weak, open point
    31), else nothing. ``landing_err_*`` is how far off that may be (about
    one sigma; depth is the weak axis from a low tripod) -- None on runs
    reconstructed before the error was recorded."""
    t = touches[i]
    nxt = touches[i + 1] if i + 1 < len(touches) else None
    out: Dict[str, Any] = {"landing_result": _landing_result(t, nxt, end)}
    if nxt is not None:
        if nxt["side"] != t["side"] and nxt.get("court_y_m") is not None:
            x, y = to_own_frame(nxt.get("court_x_m"), nxt["court_y_m"], t["side"])
            ex, ey = _err(nxt.get("court_err_m"))
            out.update({"landing_x_m": x, "landing_y_m": y, "landing_err_x_m": ex,
                        "landing_err_y_m": ey, "landing_source": "next_touch"})
        return out
    if end and end.get("kind") == "ground" and end.get("court_xy_m"):
        x, y = end["court_xy_m"]
        own_x, own_y = to_own_frame(x, y, t["side"])
        ex, ey = _err(end.get("court_xy_err_m"))
        out.update({"landing_x_m": own_x, "landing_y_m": own_y,
                    "landing_err_x_m": ex, "landing_err_y_m": ey,
                    "landing_in": end.get("in_court"), "landing_source": "ball_death"})
    return out


def build_actions(points: List[Dict[str, Any]],
                  spikes: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    spikes = spikes or []
    rows: List[Dict[str, Any]] = []
    for pt in points:
        touches = pt["touches"]
        assists = _assist_flags(touches)
        for i, t in enumerate(touches):
            action = t["action"]
            if action not in ACTIONS:
                raise BundleError(f"point {pt['point']} f{t['frame']}: unknown action {action!r}")
            own_x, own_y = to_own_frame(t.get("court_x_m"), t.get("court_y_m"),
                                        t.get("side"))
            row: Dict[str, Any] = {
                "point_no": pt["point"],
                "seq": i,
                "frame": int(t["frame"]),
                "slot": _credited_slot(t),
                "team": t.get("team"),
                "side": t.get("side"),
                "action": action,
                "touch_number": t["touch_number"],
                "outcome": t.get("outcome"),
                "is_assist": assists[i],
                "observed": bool(t["observed"]),
                "evidence": t.get("evidence"),
                "player_source": t.get("player_source"),
                "ends_possession": t.get("ends_possession"),
                "height_m": t.get("height_m"),
                "own_x_m": own_x,
                "own_y_m": own_y,
                "attack_zone": None,
                "spike_type": None,
                "landing_x_m": None,
                "landing_y_m": None,
                "landing_err_x_m": None,
                "landing_err_y_m": None,
                "landing_in": None,
                "landing_source": None,
                "landing_result": None,
                "dug_zone": None,
                "extra": {
                    "player": t.get("player"),
                    "court_y_m": t.get("court_y_m"),
                    "court_err_m": t.get("court_err_m"),
                    "reach_body_heights": t.get("reach_body_heights"),
                    "perception_action": t.get("perception_action"),
                },
            }
            if action in ATTACKS:
                row.update(_landing(i, touches, pt.get("end")))
                spike = _nearest_spike(row["frame"], spikes)
                if spike is not None:
                    row["attack_zone"] = _zone(spike.get("attack_zone"))
                    row["spike_type"] = spike.get("spike_type")
                    row["extra"]["causal_spike"] = {
                        "frame": spike.get("frame"), "outcome": spike.get("outcome"),
                        "landing_zone": spike.get("landing_zone"),
                        "dug_zone": spike.get("dug_zone"),
                    }
            rows.append(row)
    return rows


def build_points(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for pt in points:
        end = pt.get("end") or {}
        xy = end.get("court_xy_m") or [None, None]
        score = pt.get("score_after") or {}
        rows.append({
            "point_no": pt["point"],
            "set_no": 1,
            "start_frame": int(pt["start_frame"]),
            "end_frame": int(pt["end_frame"]),
            "serving_team": pt["serve"].get("team"),
            "server_slot": pt["serve"].get("player") if pt["serve"].get("player") in SLOTS else None,
            "near_team": pt.get("near_team"),
            "winner_team": pt.get("winner"),
            "winner_source": pt.get("winner_source"),
            "end_kind": end.get("kind"),
            "end_x_m": xy[0],
            "end_y_m": xy[1],
            "end_in_court": end.get("in_court"),
            "score_a_after": int(score.get("A", 0)),
            "score_b_after": int(score.get("B", 0)),
            "flags": [str(f) for f in pt.get("flags") or []],
        })
    return rows


# --------------------------------------------------------------------------- #
# bundle
# --------------------------------------------------------------------------- #

def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_sha256(bundle: Dict[str, Any]) -> str:
    """Hash of what the web shows -- never provenance, notes or timestamps,
    so rebuilding an unchanged run is a recorded no-op."""
    content = {k: bundle[k] for k in ("match", "slots", "points", "actions")}
    return hashlib.sha256(canonical_json(content).encode()).hexdigest()


def _load(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def default_match_key(run_dir: Path, pipeline: Optional[Dict[str, Any]]) -> str:
    """The source stem of the run (``_up1080`` cache suffix stripped)."""
    from src.utils.video_upscale import resolve_source_stem

    key = ((pipeline or {}).get("video") or {}).get("key")
    return resolve_source_stem(key) if key else run_dir.name


def build_bundle(run_dir: Path, *, match_key: Optional[str] = None,
                 video_url: Optional[str] = None, video_sha256: Optional[str] = None,
                 video_filename: Optional[str] = None,
                 thumb_paths: Optional[Dict[str, str]] = None,
                 provenance: Optional[Dict[str, Any]] = None,
                 note: Optional[str] = None, replace_video: bool = False) -> Dict[str, Any]:
    run_dir = Path(run_dir)
    recon = _load(run_dir / "match_reconstruction.json")
    if recon is None:
        raise BundleError(f"{run_dir}/match_reconstruction.json not found "
                          f"(run `make run-match` or `make postrun` first)")
    pipeline = _load(run_dir / "pipeline_output.json") or {}
    source = _load(run_dir / "source.json") or {}
    video = pipeline.get("video") or {}

    key = match_key or default_match_key(run_dir, pipeline)
    try:
        parsed = parse_match_key(key)
    except MatchKeyError as exc:
        raise BundleError(f"{exc}. Pass --match-key YYYYMMDD_HHMM_<venue>_<text> "
                          f"(or rename the video before calibrating)") from exc

    points = recon.get("points") or []
    checks = recon.get("checks") or {}
    final = checks.get("final_score") or {}
    score_a, score_b = int(final.get("A", 0)), int(final.get("B", 0))
    fps = float(recon.get("fps") or video.get("fps") or 0.0)
    n_frames = recon.get("n_frames") or video.get("total_frames")

    match = {
        "match_key": parsed.key,
        "match_date": parsed.match_date.isoformat(),
        "start_time": parsed.start_time.strftime("%H:%M"),
        "points_to_win": 21,
        "score_a": score_a,
        "score_b": score_b,
        "winner_team": "A" if score_a > score_b else ("B" if score_b > score_a else None),
        "n_points": len(points),
        "set_complete": bool(checks.get("set_complete")),
        "duration_s": round(n_frames / fps, 1) if fps and n_frames else None,
        "checks": checks,
        "video": {
            "filename": video_filename or source.get("original_name")
                        or (Path(video["path"]).name if video.get("path") else None),
            "url": video_url or source.get("video_url"),
            "sha256": video_sha256,
            "fps": round(fps, 3) if fps else None,
            "width": video.get("width"),
            "height": video.get("height"),
        },
    }
    thumbs = thumb_paths or {}
    bundle: Dict[str, Any] = {
        "bundle_version": BUNDLE_VERSION,
        "match": match,
        "slots": [{"slot": s, "thumb_path": thumbs.get(s)} for s in SLOTS],
        "points": build_points(points),
        "actions": build_actions(points, pipeline.get("spikes")),
        "provenance": {
            "pipeline_version": pipeline.get("pipeline_version"),
            "postrun_schema": recon.get("schema_version"),
            **(provenance or {}),
        },
    }
    if note:
        bundle["note"] = note
    if replace_video:
        bundle["replace_video"] = True
    validate_bundle(bundle)
    bundle["content_sha256"] = content_sha256(bundle)
    return bundle


def validate_bundle(bundle: Dict[str, Any]) -> None:
    """The invariants the database would otherwise reject mid-transaction."""
    if bundle.get("bundle_version") != BUNDLE_VERSION:
        raise BundleError(f"bundle_version must be {BUNDLE_VERSION}")
    parse_match_key(bundle["match"]["match_key"])
    point_nos = [p["point_no"] for p in bundle["points"]]
    if len(set(point_nos)) != len(point_nos):
        raise BundleError("duplicate point numbers")
    known = set(point_nos)
    seen = set()
    for a in bundle["actions"]:
        if a["point_no"] not in known:
            raise BundleError(f"action f{a['frame']} belongs to unknown point {a['point_no']}")
        if (a["point_no"], a["seq"]) in seen:
            raise BundleError(f"duplicate action (point {a['point_no']}, seq {a['seq']})")
        seen.add((a["point_no"], a["seq"]))
        if a["action"] not in ACTIONS:
            raise BundleError(f"unknown action {a['action']!r}")
        if a["slot"] is not None and a["slot"] not in SLOTS:
            raise BundleError(f"unknown slot {a['slot']!r}")
        if a["outcome"] not in (None, "ace", "kill", "error"):
            raise BundleError(f"unknown outcome {a['outcome']!r}")
        if a["landing_result"] not in (None, *LANDING_RESULTS):
            raise BundleError(f"unknown landing_result {a['landing_result']!r}")
        if a["attack_zone"] is not None and not 1 <= a["attack_zone"] <= 9:
            raise BundleError(f"attack_zone {a['attack_zone']} outside 1-9")
    if sorted(s["slot"] for s in bundle["slots"]) != sorted(SLOTS):
        raise BundleError("slots must be exactly P1A, P2A, P1B, P2B")
