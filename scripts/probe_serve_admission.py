"""Diagnose WHY the ball tracker (re-)locks, or fails to, at serve tosses.

Task T5 step 1 (DIAGNOSE ONLY -- this script never changes `src/`). It reads an
OFF-BY-DEFAULT ``--diag-dump`` JSONL (T4) plus a GT file, and for every GT
`serve` contact it measures, per frame in a +-N frame window around the owner
frame:

* the RAW ball detections (center, pixel width, confidence, static
  `persist`, `stationary_suspect` / static-removed flags),
* the tracker's state + decision reason as the pipeline recorded it,
* the frame-to-frame pixel speed between the plausible detections exactly as
  the bootstrap computes it (`_scan_motion_pair`: age <= `lock_max_pair_gap`,
  distance <= `lock_max_jump`, speed >= `lock_min_speed`),

and, for the bootstrap failure, WHICH condition failed on each frame.

The bootstrap decision is REPLAYED offline over the whole clip (the tracker is
inert outside the lock decision; the dumped `ball_track.locked` flag resyncs
the replay whenever the real tracker owned the ball), so a hypothetical
threshold can be evaluated for its effect on (a) every GT serve window and
(b) every other lock in the clip -- i.e. what a weaker rule would let a rack
ball / held ball steal.

Usage::

    venv/bin/python scripts/probe_serve_admission.py \
        --diag output/t4/dev_diag.jsonl \
        --ground-truth ground_truth/video_ari_joan_8_first_points_annotations.json \
        --json output/t5/dev_serve_admission.json \
        --markdown docs/t5_serve_admission_diagnosis.md
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import Config  # noqa: E402
from src.utils.diagnostics import load_diag  # noqa: E402


# ---------------------------------------------------------------------------
# parameters (identical names to the BallTracker ctor)
# ---------------------------------------------------------------------------

DEFAULTS = {
    "lock_min_speed": 8.0,
    "lock_motion_window": 5,
    "lock_max_jump": 90.0,
    "lock_max_pair_gap": 2,
    "low_confidence_threshold": 0.4,
    "boot_low_conf_floor": 0.15,
    "locked_low_conf_floor": 0.15,
    # T5 step-1 COUNTERFACTUALS ONLY (never wired into src/): the extra
    # conditions a weak-motion lock could be gated on, so the proposal can be
    # measured instead of guessed.
    "weak_ascending": False,
    "weak_player_radius": 0.0,
    "weak_min_speed": 0.0,       # weak-lock motion floor (0 = off)
    "weak_radius": 0.0,          # px: same-candidate association radius (0 = off)
    "weak_sightings": 0,         # of the last ``weak_sightings`` frames (0 = off)
    "weak_max_persist": 1.0,      # detector static-persist ceiling (1 = off)
    "speed_width_ref": 0.0,       # px: apparent-size-normalised motion gate
}


def tracker_params(config: Optional[str] = None) -> Dict[str, Any]:
    """Ball-tracker constants from DEFAULT_CONFIG (or ``--config``)."""
    cfg = Config(config) if config else Config()
    get = cfg.get
    return {
        "lock_min_speed": float(get("ball_lock_min_speed",
                                    DEFAULTS["lock_min_speed"])),
        "lock_motion_window": int(get("ball_lock_motion_window",
                                      DEFAULTS["lock_motion_window"])),
        "lock_max_jump": float(get("ball_lock_max_jump",
                                   DEFAULTS["lock_max_jump"])),
        "lock_max_pair_gap": int(get("ball_lock_max_pair_gap",
                                     DEFAULTS["lock_max_pair_gap"])),
        "low_confidence_threshold": float(
            get("low_confidence_threshold", DEFAULTS["low_confidence_threshold"])),
        "boot_low_conf_floor": float(get("ball_boot_low_conf_floor",
                                         DEFAULTS["boot_low_conf_floor"])),
        "locked_low_conf_floor": float(get("ball_locked_low_conf_floor",
                                           DEFAULTS["locked_low_conf_floor"])),
    }


# ---------------------------------------------------------------------------
# detections
# ---------------------------------------------------------------------------


def det_rows(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Diag detections -> uniform rows the bootstrap can be replayed on."""
    rows = []
    for d in record.get("ball_dets", []) or []:
        bbox = d.get("bbox") or [0, 0, 0, 0]
        rows.append({
            "center": [float(d["center"][0]), float(d["center"][1])],
            "width": int(bbox[2] - bbox[0]) if len(bbox) >= 4 else 0,
            "conf": float(d.get("conf", 0.0)),
            "persist": float(d.get("persist", 0.0)),
            "suspect": bool(d.get("suspect", False)),
            "removed": bool(d.get("removed", False)),
        })
    return rows


def plausible(rows: List[Dict[str, Any]], floor: float,
              params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Survivors the tracker may use at confidence tier ``floor``."""
    return [r for r in rows
            if not r["removed"] and not r["suspect"] and r["conf"] >= floor]


def tiers(rows: List[Dict[str, Any]], params: Dict[str, Any]
          ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(high-tier, low-tier) -- the two windows `_try_lock` maintains."""
    hi = plausible(rows, params["low_confidence_threshold"], params)
    lo = ([r for r in rows
           if not r["removed"] and not r["suspect"]
           and params["boot_low_conf_floor"] <= r["conf"]
           < params["low_confidence_threshold"]]
          if 0 < params["boot_low_conf_floor"] < params["low_confidence_threshold"]
          else [])
    return hi, lo


def speed_gate(params: Dict[str, Any], det: Dict[str, Any],
               old: List[float]) -> float:
    """Motion gate for a pair, optionally normalised by APPARENT ball size.

    ``speed_width_ref`` > 0 makes the required speed proportional to the ball's
    pixel width (a far-side ball is ~half the px size of a near-side one, so
    its toss rises at ~half the px/f -- a flat px/f bar cannot serve both).
    """
    base = params["lock_min_speed"]
    ref = params.get("speed_width_ref", 0.0)
    if not ref:
        return base
    return base * min(1.0, max(det.get("width", 0), 1) / ref)


def scan(dets: List[Dict[str, Any]], history: List[List[List[float]]],
         params: Dict[str, Any]) -> Dict[str, Any]:
    """`_scan_motion_pair` replay + a diagnosis of the failing condition.

    Returns ``{"hit", "det", "old", "age", "speed", "dist", "fail"}`` where
    ``fail`` names the first gate that rejected the best available evidence.
    """
    best: Optional[Dict[str, Any]] = None      # best pair passing max_jump
    min_dist = None                           # closest previous sighting, any age
    min_in_gap = None                         # ... within lock_max_pair_gap
    for det in sorted(dets, key=lambda d: d["conf"], reverse=True):
        c = det["center"]
        gate = speed_gate(params, det, None)
        for age, frame_centers in enumerate(reversed(history), start=1):
            for old in frame_centers:
                dist = math.hypot(c[0] - old[0], c[1] - old[1])
                if min_dist is None or dist < min_dist:
                    min_dist = dist
            if age > params["lock_max_pair_gap"]:
                continue                      # too old to be motion evidence
            for old in frame_centers:
                dist = math.hypot(c[0] - old[0], c[1] - old[1])
                if min_in_gap is None or dist < min_in_gap:
                    min_in_gap = dist
                if dist > params["lock_max_jump"]:
                    continue
                speed = dist / age
                if best is None or speed > best["speed"]:
                    best = {"det": det, "old": old, "age": age,
                            "dist": dist, "speed": speed, "gate": gate,
                            "ascending": c[1] < old[1]}
    top = best or {}
    if best is not None and best["speed"] >= best.get("gate", params["lock_min_speed"]):
        return dict(hit=True, fail=None, **best)
    if best is not None:
        return dict(hit=False, fail="speed_below_lock_min_speed", **best)
    if min_dist is None:
        return {"hit": False, "fail": "no_previous_sighting_in_window",
                "speed": None, "dist": None, "min_dist": None}
    if min_in_gap is None or min_in_gap > params["lock_max_jump"]:
        if min_in_gap is not None:
            return {"hit": False, "fail": "pair_farther_than_lock_max_jump",
                    "speed": None, "dist": None, "min_dist": min_dist}
        # a nearby sighting exists, but only older than lock_max_pair_gap
        return {"hit": False, "fail": "no_pair_within_lock_max_pair_gap",
                "speed": None, "dist": None, "min_dist": min_dist}
    return {"hit": False, "fail": "no_pair_within_lock_max_pair_gap",
            "speed": None, "dist": None, "min_dist": min_dist}


# ---------------------------------------------------------------------------
# replay of the unlock/lock decision over the whole clip
# ---------------------------------------------------------------------------


def nearest_player_dist(record: Dict[str, Any], center: List[float]) -> Optional[float]:
    """Distance from ``center`` to the nearest PLAYER detection (dump)."""
    best = None
    for p in record.get("players", []) or []:
        if p.get("predicted"):
            continue
        c = p.get("center")
        if not c:
            continue
        d = math.hypot(center[0] - c[0], center[1] - c[1])
        best = d if best is None else min(best, d)
    return best


def _weak_ok(det: Dict[str, Any], hit: Dict[str, Any], frames_hist: List[List[List[float]]],
             record: Dict[str, Any], params: Dict[str, Any]) -> bool:
    """Extra conditions a WEAK (slow-pair) lock must satisfy.

    Measured candidates for the T5 mechanism: sustained same-candidate
    sightings (a hand-held tossed ball is detected every frame while a
    coincidence of two sparse blips is not), a low static-persist (the
    detector's own "this thing does not move" counter -- a parked spare
    climbs past 0.30) and proximity to a player (the server holds it).
    """
    if params.get("weak_ascending") and not hit.get("ascending"):
        return False
    radius = params.get("weak_radius", 0.0)
    need = int(params.get("weak_sightings", 0) or 0)
    if need and radius:
        c = det["center"]
        seen = 0
        for fc in frames_hist[:need]:
            if any(math.hypot(c[0] - o[0], c[1] - o[1]) <= radius for o in fc):
                seen += 1
        if seen < need:
            return False
    mp = params.get("weak_max_persist", 1.0)
    if mp < 1.0 and det.get("persist", 0.0) > mp:
        return False
    pr = params.get("weak_player_radius", 0.0)
    if pr:
        d = nearest_player_dist(record, det["center"])
        if d is None or d > pr:
            return False
    return True


def replay(frames: Dict[int, Dict[str, Any]], params: Dict[str, Any]
           ) -> Dict[int, Dict[str, Any]]:
    """Per-frame bootstrap decision for every frame of the dump.

    The tracker only makes ONE decision while UNLOCKED (`_try_lock`), so the
    dump fully determines it. The dumped ``ball_track.locked`` flag resyncs the
    replay whenever the real tracker owned the ball (its LOCKED-path state is
    not in the dump, and the bootstrap windows are cleared on every lock).
    """
    win = max(2, params["lock_motion_window"])
    out: Dict[int, Dict[str, Any]] = {}
    hi_hist: List[List[List[float]]] = []
    lo_hist: List[List[List[float]]] = []
    locked = False
    # `following` = the replay is mirroring a dump-owned lock cycle (and must
    # therefore follow the dump's own unlocks). A lock the REPLAY fired stays
    # in force until the real tracker next reports locked, which is where the
    # replay resyncs and starts mirroring again.
    following = False
    for frame in sorted(frames):
        rec = frames[frame]
        rows = det_rows(rec)
        hi, lo = tiers(rows, params)
        bt = rec.get("ball_track") or {}
        if bt.get("locked"):
            locked = True
            following = True
        elif locked and following:
            # the dump-owned lock cycle the replay was mirroring has ended
            locked = False
        if locked and bt.get("locked"):
            out[frame] = {"locked": True, "hit": None, "reason": "locked_in_dump",
                          "best": None, "fail": None, "n_dets": len(rows)}
            hi_hist, lo_hist = [], []
            continue
        if locked:
            # a lock the REPLAY itself fired: it stays in force until the real
            # tracker next reports locked (the resync above). No bootstrap
            # decision is taken while the ball is held.
            out[frame] = {"locked": True, "hit": None, "reason": "lock_replay_held",
                          "best": None, "fail": None, "n_dets": len(rows)}
            hi_hist, lo_hist = [], []
            continue
        hi_res = scan(hi, list(hi_hist), params)
        # the tracker appends the CURRENT frame to both windows before
        # scanning, so both histories here exclude the current frame
        lo_res = scan(lo, list(lo_hist), params)
        hit = hi_res if hi_res["hit"] else (lo_res if lo_res["hit"] else None)
        best = hi_res if hi_res.get("speed") is not None else (
            lo_res if lo_res.get("speed") is not None else hi_res)
        # counterfactual gates on a WEAK (slow-pair) lock -- measurement only
        gate_now = (hit or {}).get("gate", params["lock_min_speed"])
        if hit is not None and hit["speed"] < gate_now:
            hist = list(hi_hist) + list(lo_hist)
            if not _weak_ok(hit["det"], hit, hist, rec, params):
                hit = None
        if hit is not None:
            locked = True
            following = False
            out[frame] = {"locked": True, "hit": True, "reason": "bootstrap_locked",
                          "best": hit, "fail": None, "n_dets": len(rows)}
            hi_hist, lo_hist = [], []
            continue
        if rows:
            fail = hi_res["fail"] if (hi or lo) else "no_plausible_survivor"
        else:
            fail = "no_detections"
        best["fail"] = fail
        out[frame] = {"locked": False, "hit": False,
                      "reason": bt.get("reason") or "unlocked_no_motion",
                      "best": best, "fail": fail, "n_dets": len(rows)}
        hi_hist.append([d["center"] for d in hi])
        del hi_hist[:-win]
        lo_hist.append([d["center"] for d in lo])
        del lo_hist[:-win]
    return out


def lock_frames(decisions: Dict[int, Dict[str, Any]]) -> List[int]:
    """Frames where the replay transitioned unlocked -> locked."""
    out, prev = [], False
    for frame in sorted(decisions):
        cur = decisions[frame]["locked"]
        if cur and not prev:
            out.append(frame)
        prev = cur
    return out


# ---------------------------------------------------------------------------
# GT serves
# ---------------------------------------------------------------------------


def gt_serves(gt_path: str) -> List[Dict[str, Any]]:
    """Every GT `serve` contact, with its point and the owner side word."""
    gt = json.loads(open(gt_path, encoding="utf-8").read())
    serves = []
    for point in gt.get("points", []):
        for ev in point.get("events", []):
            if ev.get("final_action") != "serve" and ev.get("action") != "serve":
                continue
            serves.append({
                "point": point.get("point"),
                "frame": int(ev["frame"]),
                "match_frame": int(ev.get("match_frame", ev["frame"])),
                "team": ev.get("player_team") or ev.get("team_in_possession"),
                "side": ev.get("owner_side"),
                "tolerance": int(ev.get("frame_tolerance", 15)),
            })
    serves.sort(key=lambda s: s["frame"])
    return serves


# ---------------------------------------------------------------------------
# per-serve report
# ---------------------------------------------------------------------------


def frame_row(frame: int, record: Dict[str, Any], decision: Dict[str, Any],
              params: Dict[str, Any]) -> Dict[str, Any]:
    rows = det_rows(record)
    best = decision.get("best") or {}
    bt = record.get("ball_track") or {}
    return {
        "frame": frame,
        "dets": rows,
        "track_state": bt.get("state"),
        "track_reason": bt.get("reason"),
        "locked_dump": bool(bt.get("locked")),
        "locked_replay": bool(decision.get("locked")),
        "hit": bool(decision.get("hit")),
        "fail": decision.get("fail"),
        "best_speed": best.get("speed"),
        "best_pair_dist": best.get("dist"),
        "best_pair_age": best.get("age"),
        "ascending": best.get("ascending"),
        "best_conf": (best.get("det") or {}).get("conf"),
        "min_dist": best.get("min_dist"),
        "best_det": best.get("det"),
    }


def serve_report(serve: Dict[str, Any], frames: Dict[int, Dict[str, Any]],
                 decisions: Dict[int, Dict[str, Any]], window: int,
                 params: Dict[str, Any]) -> Dict[str, Any]:
    f = serve["frame"]
    lo, hi = f - window, f + window
    rows = [frame_row(x, frames.get(x, {}), decisions.get(x, {}), params)
            for x in range(lo, hi + 1) if x in frames]
    # OBSERVED speed series, independent of tracker state: consecutive
    # (gap-1) distance between the best plausible detection of two adjacent
    # frames -- the quantity `lock_min_speed` is compared against.
    prev_best = None
    for r in rows:
        det = None
        pool = [d for d in r["dets"] if not d["removed"] and not d["suspect"]
                and d["conf"] >= params["boot_low_conf_floor"]]
        if pool:
            det = max(pool, key=lambda d: d["conf"])["center"]
        r["obs_speed"] = (None if (det is None or prev_best is None)
                          else math.hypot(det[0] - prev_best[0],
                                          det[1] - prev_best[1]))
        prev_best = det if det is not None else prev_best
    # first lock AFTER the serve frame (dump and replay agree by construction)
    first_lock = next((r["frame"] for r in rows if r["locked_dump"] and r["frame"] >= f),
                      None)
    first_replay_lock = next((r["frame"] for r in rows if r["locked_replay"]
                              and r["frame"] >= f), None)
    unlocked_at_owner = [r for r in rows
                         if abs(r["frame"] - f) <= serve["tolerance"]
                         and not r["locked_replay"]]
    fails: Dict[str, int] = {}
    for r in rows:
        if not r["locked_replay"] and r["fail"]:
            fails[r["fail"]] = fails.get(r["fail"], 0) + 1
    obs = [r["obs_speed"] for r in rows if r["obs_speed"] is not None]
    pre = [r for r in rows if r["frame"] < f]
    pre_obs = [r["obs_speed"] for r in pre if r["obs_speed"] is not None]
    pre_w = [d["width"] for r in pre for d in r["dets"]
             if not d["removed"] and not d["suspect"]]
    first_seen = next((r["frame"] for r in pre if r["dets"]), None)
    at_contact = next((r for r in rows if r["frame"] == f), None)
    locked_at_owner = next((r["locked_replay"] for r in rows
                            if r["frame"] == f), None)
    return {
        **serve,
        "window": [lo, hi],
        "frames": rows,
        "first_lock_after_serve": first_lock,
        "first_lock_replay_after_serve": first_replay_lock,
        "locked_at_owner_frame": locked_at_owner,
        "frames_locked_at_owner": len(rows) - len(unlocked_at_owner),
        "unlocked_frames_in_tolerance": len(unlocked_at_owner),
        "lock_latency": (None if first_lock is None else first_lock - f),
        "failure_counts": dict(sorted(fails.items(), key=lambda kv: -kv[1])),
        "max_obs_speed_in_window": max(obs) if obs else None,
        "median_obs_speed_in_window": (sorted(obs)[len(obs) // 2] if obs else None),
        "median_pre_contact_obs_speed": (sorted(pre_obs)[len(pre_obs) // 2]
                                         if pre_obs else None),
        "median_pre_contact_det_width": (sorted(pre_w)[len(pre_w) // 2]
                                         if pre_w else None),
        "first_pre_contact_sighting": first_seen,
        "dets_at_contact_frame": len(at_contact["dets"]) if at_contact else None,
    }


# ---------------------------------------------------------------------------
# counterfactual sweep
# ---------------------------------------------------------------------------


def _serve_metrics(dec: Dict[int, Dict[str, Any]], serves: List[Dict[str, Any]],
                   frames: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """Per serve: first replay lock after the contact and how much of the
    +-tolerance window the tracker OWNS the ball on."""
    out = {}
    for s in serves:
        tol = s["tolerance"]
        win = [x for x in range(s["frame"] - tol, s["frame"] + tol + 1) if x in frames]
        first = next((x for x in range(s["frame"], s["frame"] + tol + 1)
                      if x in frames and dec.get(x, {}).get("locked")), None)
        out[s["frame"]] = {
            "point": s["point"],
            "first_lock_after": first,
            "latency": None if first is None else first - s["frame"],
            "locked_frames_in_tol": sum(1 for x in win if dec.get(x, {}).get("locked")),
            "window_frames": len(win),
        }
    return out


def sweep(frames: Dict[int, Dict[str, Any]], serves: List[Dict[str, Any]],
          base_params: Dict[str, Any], variants: List[Dict[str, Any]],
          window: int) -> List[Dict[str, Any]]:
    """For each hypothetical rule: serves recovered + locks gained elsewhere."""
    results = []
    base_dec = replay(frames, base_params)
    base_locks = set(lock_frames(base_dec))
    base_metrics = _serve_metrics(base_dec, serves, frames)
    for var in variants:
        params = dict(base_params)
        params.update(var.get("params", {}))
        dec = replay(frames, params)
        locks = set(lock_frames(dec))
        new_locks = sorted(locks - base_locks)
        metrics = _serve_metrics(dec, serves, frames)
        # "recovered" = the tracker owns the ball on >= 60% of the +-15f window
        # (and baseline did not), with the first lock no later than 5f after
        # the contact.
        recovered = []
        for f, m in metrics.items():
            frac = m["locked_frames_in_tol"] / max(1, m["window_frames"])
            was = base_metrics[f]["locked_frames_in_tol"] / max(1, base_metrics[f]["window_frames"])
            if frac >= 0.6 and was < 0.6 and (m["latency"] is None or m["latency"] <= 5):
                recovered.append(f)
        gains = []
        for lf in new_locks:
            d = frames.get(lf, {})
            best = (dec[lf].get("best") or {}).get("det") or {}
            near = [s for s in serves if abs(s["frame"] - lf) <= window]
            pdist = nearest_player_dist(d, best["center"]) if best else None
            gains.append({
                "frame": lf,
                "conf": best.get("conf"),
                "width": best.get("width"),
                "speed": (dec[lf].get("best") or {}).get("speed"),
                "persist": best.get("persist"),
                "ascending": (dec[lf].get("best") or {}).get("ascending"),
                "nearest_player_px": None if pdist is None else round(pdist, 1),
                "near_serve": near[0]["frame"] if near else None,
            })
        results.append({
            "name": var["name"],
            "params": var.get("params", {}),
            "serves": metrics,
            "serves_recovered": sorted(recovered),
            "new_lock_count": len(new_locks),
            "new_locks": gains,
            "window": window,
        })
    results[0]["serves_recovered_vs_baseline"] = []
    return results


DEFAULT_VARIANTS = [
    {"name": "baseline", "params": {}},
    {"name": "min_speed=6", "params": {"lock_min_speed": 6.0}},
    {"name": "min_speed=5", "params": {"lock_min_speed": 5.0}},
    {"name": "min_speed=4", "params": {"lock_min_speed": 4.0}},
    {"name": "min_speed=3", "params": {"lock_min_speed": 3.0}},
    {"name": "min_speed=2", "params": {"lock_min_speed": 2.0}},
    {"name": "min_speed=1", "params": {"lock_min_speed": 1.0}},
    {"name": "pair_gap=3", "params": {"lock_max_pair_gap": 3}},
    {"name": "pair_gap=4", "params": {"lock_max_pair_gap": 4}},
    {"name": "min_speed=4 + pair_gap=3", "params": {"lock_min_speed": 4.0,
                                                    "lock_max_pair_gap": 3}},
    {"name": "min_speed=4 + pair_gap=4", "params": {"lock_min_speed": 4.0,
                                                    "lock_max_pair_gap": 4}},
    # targeted (weak-motion lock gated on the toss signature)
    {"name": "min3 + ascending", "params": {"lock_min_speed": 3.0,
                                            "weak_ascending": True}},
    {"name": "min4 + ascending", "params": {"lock_min_speed": 4.0,
                                            "weak_ascending": True}},
    {"name": "min3 + ascending + near player 200px",
     "params": {"lock_min_speed": 3.0, "weak_ascending": True,
                "weak_player_radius": 200.0}},
    {"name": "min3 + ascending + near player 120px",
     "params": {"lock_min_speed": 3.0, "weak_ascending": True,
                "weak_player_radius": 120.0}},
    # the PROPOSED mechanism: keep the 8 px/f rule untouched and add a
    # "weak-motion lock" for the toss (sustained sightings + low persist)
    {"name": "WEAK lock >=3px/f (plain)",
     "params": {"lock_min_speed": 3.0}},
    {"name": "WEAK lock >=3px/f + 3-of-3 sightings @20px",
     "params": {"lock_min_speed": 3.0, "weak_radius": 20.0, "weak_sightings": 3}},
    {"name": "WEAK lock >=3px/f + 3-of-3 + persist<0.25",
     "params": {"lock_min_speed": 3.0, "weak_radius": 20.0, "weak_sightings": 3,
                "weak_max_persist": 0.25}},
    {"name": "WEAK lock >=3px/f + 3-of-3 + persist<0.25 + player<250px",
     "params": {"lock_min_speed": 3.0, "weak_radius": 20.0, "weak_sightings": 3,
                "weak_max_persist": 0.25, "weak_player_radius": 250.0}},
    {"name": "WEAK lock >=4px/f + 3-of-3 + persist<0.25",
     "params": {"lock_min_speed": 4.0, "weak_radius": 20.0, "weak_sightings": 3,
                "weak_max_persist": 0.25}},
    # apparent-size-normalised motion gate: 8 px/f at a 50 px-wide ball,
    # proportionally weaker for the ~15 px far-side ball
    {"name": "size-normalised gate ref=60", "params": {"speed_width_ref": 60.0}},
    {"name": "size-normalised gate ref=50", "params": {"speed_width_ref": 50.0}},
    {"name": "size-normalised gate ref=40", "params": {"speed_width_ref": 40.0}},
    {"name": "size-normalised ref=50 + 3-of-3 + persist<0.25",
     "params": {"speed_width_ref": 50.0, "weak_radius": 20.0,
                "weak_sightings": 3, "weak_max_persist": 0.25}},
]


# ---------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------


def _fmt(v: Optional[float], nd: int = 1) -> str:
    return "-" if v is None else f"{v:.{nd}f}"


HAND_MARKER = "## Hand analysis (authored, kept on regeneration)"


def write_markdown(path: str, report: Dict[str, Any]) -> None:
    """Write the generated sections, preserving anything the hand analysis
    appended after ``HAND_MARKER`` across regenerations."""
    body = markdown(report)
    tail = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            existing = fh.read()
        if HAND_MARKER in existing:
            tail = HAND_MARKER + existing.split(HAND_MARKER, 1)[1]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body + tail)


def markdown(report: Dict[str, Any]) -> str:
    p = report["params"]
    pt = {s["frame"]: s["point"] for s in report["serves"]}
    lines = [
        "# T5 step 1 - serve-time ball-track (re-)admission: DIAGNOSIS",
        "",
        f"Diagnostic only: no `src/` behaviour changed. Numbers come from "
        f"`{report['diag']}` (T4 off-by-default `--diag-dump`), the GT serves in "
        f"`{report['ground_truth']}`, and the offline bootstrap replay in "
        f"`scripts/probe_serve_admission.py`.",
        "",
        "## Tracker gates in force",
        "",
        f"`lock_min_speed` = **{p['lock_min_speed']} px/f**, "
        f"`lock_motion_window` = {p['lock_motion_window']}f, "
        f"`lock_max_jump` = {p['lock_max_jump']} px, "
        f"`lock_max_pair_gap` = {p['lock_max_pair_gap']}f, "
        f"high tier >= {p['low_confidence_threshold']}, "
        f"`boot_low_conf_floor` = {p['boot_low_conf_floor']}. "
        "A bootstrap lock needs ONE pair of surviving (non-suspect, non-removed) "
        "sightings with `age <= lock_max_pair_gap`, `distance <= lock_max_jump` "
        "and `distance/age >= lock_min_speed`.",
        "",
        "## Per-serve summary",
        "",
        "| point | serve f | side | locked AT f? | first lock after serve "
        "(latency) | pre-contact toss: median px/f, det width px, first sighting "
        "| dets at contact f | dominant failing condition |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in report["serves"]:
        dom = ", ".join(f"{k} x{v}" for k, v in list(s["failure_counts"].items())[:2]) or "-"
        lock = ("never" if s["first_lock_after_serve"] is None
                else f"f{s['first_lock_after_serve']} (+{s['lock_latency']}f)")
        lines.append(
            f"| {s['point']} | {s['frame']} | {s['side'] or '-'} | "
            f"{'yes' if s['locked_at_owner_frame'] else '**NO**'} | {lock} | "
            f"{_fmt(s['median_pre_contact_obs_speed'])} px/f, "
            f"w{_fmt(s['median_pre_contact_det_width'], 0)}, "
            f"f{s['first_pre_contact_sighting']} | "
            f"{s['dets_at_contact_frame']} | {dom} |")
    lines += ["", "## Per-frame detail (each serve window)", ""]
    for s in report["serves"]:
        lines += [
            f"### P{s['point']} serve f{s['frame']} ({s['side']} team "
            f"{s['team']}), window f{s['window'][0]}-f{s['window'][1]}",
            "",
            "| f | dets (x,y w conf persist flags) | tracker | replay | obs "
            "gap-1 speed | best pair speed | dist | fail |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in s["frames"]:
            dets = " ".join(
                f"({d['center'][0]:.0f},{d['center'][1]:.0f} w{d['width']} "
                f"c{d['conf']:.2f} p{d['persist']:.2f}"
                f"{'S' if d['suspect'] else ''}{'R' if d['removed'] else ''})"
                for d in r["dets"]) or "-"
            lines.append(
                f"| {r['frame']} | {dets} | {r['track_state']}/"
                f"{r['track_reason']} | {'lock' if r['locked_replay'] else '-'} | "
                f"{_fmt(r['obs_speed'])} | "
                f"{_fmt(r['best_speed'])} | {_fmt(r['best_pair_dist'], 0)} | "
                f"{r['fail'] or '-'} |")
        lines.append("")
    if report.get("sweep"):
        lines += [
            "## Counterfactual sweep (offline replay of the bootstrap)",
            "",
            "| rule | serves recovered (P# f) | new locks elsewhere | "
            "new-lock frames |",
            "|---|---|---|---|",
        ]
        for v in report["sweep"]:
            gained = ", ".join(str(g["frame"]) for g in v["new_locks"]) or "-"
            rec = ", ".join(f"P{pt[f]} f{f}" for f in v["serves_recovered"]) or "-"
            lines.append(
                f"| {v['name']} | {rec} | "
                f"{v['new_lock_count']} | {gained} |")
        lines.append("")
        lines += ["| rule | " + " | ".join(
            f"P{s['point']} f{s['frame']} lock/latency, locked frames in +-{s['tolerance']}f"
            for s in report["serves"]) + " |",
            "|---|" + "---|" * len(report["serves"])]
        for v in report["sweep"]:
            cells = []
            for s in report["serves"]:
                m = v["serves"][s["frame"]]
                fl = "-" if m["first_lock_after"] is None else f"{m['first_lock_after']}"
                lat = "" if m["latency"] is None else f"/{m['latency']:+d}f"
                cells.append(f"{fl}{lat} · {m['locked_frames_in_tol']}/"
                             f"{m['window_frames']}")
            lines.append(f"| {v['name']} | " + " | ".join(cells) + " |")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--diag", required=True, help="T4 --diag-dump JSONL")
    ap.add_argument("--ground-truth", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--window", type=int, default=40,
                    help="frames either side of the owner serve frame")
    ap.add_argument("--json", default=None)
    ap.add_argument("--markdown", default=None)
    ap.add_argument("--serve-frames", default=None,
                    help="comma-separated serve frames to analyse instead of the "
                         "GT ones (entreno GT carries no action labels)")
    ap.add_argument("--serve-labels", default=None,
                    help="comma-separated labels for --serve-frames")
    ap.add_argument("--no-sweep", action="store_true")
    args = ap.parse_args(argv)

    diag = load_diag(args.diag)
    frames = diag["frames"]
    params = tracker_params(args.config)
    if args.serve_frames:
        labels = (args.serve_labels or "").split(",")
        serves = []
        for i, tok in enumerate(args.serve_frames.split(",")):
            tok = tok.strip()
            if not tok:
                continue
            serves.append({
                "point": labels[i].strip() if i < len(labels) else None,
                "frame": int(tok), "match_frame": int(tok), "team": None,
                "side": None, "tolerance": 15,
            })
    else:
        serves = gt_serves(args.ground_truth)
    decisions = replay(frames, params)
    report = {
        "diag": args.diag,
        "ground_truth": args.ground_truth,
        "fps": diag["meta"].get("fps"),
        "params": params,
        "window": args.window,
        "serves": [serve_report(s, frames, decisions, args.window, params)
                   for s in serves],
    }
    if not args.no_sweep:
        report["sweep"] = sweep(frames, serves, params, DEFAULT_VARIANTS, args.window)

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)
    if args.markdown:
        write_markdown(args.markdown, report)
    print(f"serves: {len(serves)}  frames: {len(frames)}  "
          f"lock_min_speed={params['lock_min_speed']}")
    for s in report["serves"]:
        print(f"  P{s['point']} f{s['frame']:<5} locked@f="
              f"{'Y' if s['locked_at_owner_frame'] else 'N'} first_lock="
              f"{s['first_lock_after_serve']} obs_max="
              f"{_fmt(s['max_obs_speed_in_window'])} obs_med="
              f"{_fmt(s['median_obs_speed_in_window'])} fails={s['failure_counts']}")
    if not args.no_sweep:
        for v in report["sweep"]:
            print(f"  sweep {v['name']:<24} recovered={v['serves_recovered']} "
                  f"new_locks={v['new_lock_count']} "
                  f"{[g['frame'] for g in v['new_locks']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
