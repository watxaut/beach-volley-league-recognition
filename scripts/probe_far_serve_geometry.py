#!/usr/bin/env python3
"""Which switch does not flip at a far serve? (G4 follow-up, diagnose-only)

``probe_far_serve_tracking.py`` shows the far serve dies before any label, most
often with ``no_contact_geometry``: the classifier saw a TRACKED ball and still
found no contact.  ``_normal_contact_at`` offers exactly four ways to call a
contact -- bounce (vertex is the lowest point, ball rises), redirect
(horizontal sign flip within +-3 f), drive (downward speed cut / horizontal
impulse), and the rally-opening SERVE branch (fed ascent).  This probe replays
each recorded far-serve ball track through the PRODUCTION classifier (the same
``ActionClassifier`` instance, fed from the diag dump's ``ball_track``) and
records, per frame, which test fired or why none did.

It then reports the same quantities for the NEAR-side serve control, because
the question is a contrast: a near serve has the same physical event and the
same code path, so whatever differs between the two sides IS the signal.

No ``src/`` change: the classifier is imported and driven, never reimplemented.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.recognition.action_classifier import ActionClassifier  # noqa: E402
from src.recognition.pose_estimator import PoseEstimator  # noqa: E402
from src.utils.config import Config  # noqa: E402


def classifier() -> ActionClassifier:
    """A production ActionClassifier (same defaults the pipeline builds)."""
    cfg = Config.default().config
    return ActionClassifier(
        # The contact geometry is pure ball history; the pose estimator is
        # never consulted here, so a real (unused) one keeps the constructor
        # honest instead of a stub that could drift.
        pose_estimator=PoseEstimator(
            min_detection_confidence=cfg.get("pose_confidence", 0.5),
            model_complexity=cfg.get("pose_complexity", 0),
        ),
        temporal_window=cfg.get("temporal_window", 10),
        confidence_threshold=cfg.get("action_confidence", 0.3),
        team_aware=cfg.get("attribution_team_aware", True),
        width_side_enabled=cfg.get("attribution_width_side", True),
        width_window=cfg.get("attribution_width_window", 8),
        width_far_px=cfg.get("attribution_width_far_px", 26.0),
        width_near_px=cfg.get("attribution_width_near_px", 35.0),
        near_net_exempt_m=cfg.get("attribution_near_net_exempt_m", 2.5),
    )


def analyse(track: List[Dict[str, Any]], contact_frame: int, window: int = 40
            ) -> Dict[str, Any]:
    """Run the production contact tests over one recorded ball track."""
    clf = classifier()
    lo = max(p["frame"] for p in track) - window if track else 0
    for point in track:
        center = point.get("center") or [None, None]
        if center[0] is None:
            continue
        w = max(1.0, float(point.get("width", 10)))
        h = max(1.0, float(point.get("height", w)))
        clf._ball_history.append((int(point["frame"]), float(center[0]),
                                 float(center[1]), w, h))
    fired: List[Dict[str, Any]] = []
    reasons: Dict[str, int] = {}
    per_frame = {}
    for frame in sorted(p["frame"] for p in track):
        if abs(frame - contact_frame) > 15:
            continue
        # The classifier asks at every sighting it has history for; the reason
        # it records is exactly what production would record.
        clf._diag_records = []
        result = clf._detect_contact(frame)
        record = {"frame": frame}
        if result is not None:
            record["kind"] = result[1]
            fired.append(record)
        for rec in clf._diag_records:
            reason = str(rec.get("reason"))
            reasons[reason] = reasons.get(reason, 0) + 1
            record.setdefault("reason", reason)
        # The four tests' own numbers at this vertex (same formulas as
        # _normal_contact_at, read-only).
        vertex = clf._point_at(frame)
        if vertex is not None:
            left = clf._real_points(frame - clf.NEIGH, frame - 1)
            right = clf._real_points(frame + 1, frame + clf.NEIGH)
            numbers = {"left": len(left), "right": len(right)}
            if len(left) >= 2 and len(right) >= 2:
                vx, vy = vertex[1], vertex[2]
                # Net incoming/outgoing displacement, exactly as
                # _normal_contact_at builds them for the redirect test.
                numbers["inc"] = [round(vx - left[0][1], 1), round(vy - left[0][2], 1)]
                numbers["out"] = [round(right[-1][1] - vx, 1), round(right[-1][2] - vy, 1)]
                left3 = [p for p in left if p[0] >= frame - 3]
                right3 = [p for p in right if p[0] <= frame + 3]
                numbers["is_lowest"] = all(p[2] <= vy for p in left + right)
                numbers["rise_left"] = round(vy - min(p[2] for p in left), 1)
                numbers["rise_right"] = round(vy - min(p[2] for p in right), 1)
                numbers["min_prominence"] = clf.MIN_PROMINENCE
                if left3 and right3:
                    vin = clf._mean_velocity(left3 + [vertex])
                    vout = clf._mean_velocity([vertex] + right3)
                    speed = max(float(vin[0] ** 2 + vin[1] ** 2) ** 0.5,
                                float(vout[0] ** 2 + vout[1] ** 2) ** 0.5)
                    vin6 = None
                    if any(p[0] >= frame - 6 for p in left):
                        vin6 = clf._mean_velocity(
                            [p for p in left if p[0] >= frame - 6] + [vertex])
                    numbers.update({
                        "vin": [round(vin[0], 1), round(vin[1], 1)],
                        "vout": [round(vout[0], 1), round(vout[1], 1)],
                        "dvx": round(vout[0] - vin[0], 1),
                        "dvy": round(vout[1] - vin[1], 1),
                        "speed": round(speed, 1),
                        "drive_min_speed": clf.DRIVE_MIN_SPEED,
                        "stays_down": (right[-1][2] - vy) >= 0.0,
                        "pops_up": vout[1] < -clf.DRIVE_RISE_TOL,
                        "fed_ascent": (None if vin6 is None else
                                       round(abs(vin[1]) - abs(vin6[1]), 1)),
                        "serve_accel_margin": clf.SERVE_ACCEL_MARGIN_PX,
                        "xrev_min": clf.XREV_MIN,
                        "dx_impulse_min": clf.DRIVE_XIMPULSE,
                    })
            per_frame[frame] = numbers
    return {"fired": fired, "reasons": reasons, "per_frame": per_frame,
            "frames_analysed": len(per_frame)}


def verdict(info: Dict[str, Any]) -> str:
    """One line naming the test that SHOULD have fired and did not."""
    if info["fired"]:
        return f"contact fired: {info['fired'][0]['kind']} @f{info['fired'][0]['frame']}"
    frames = info["per_frame"]
    complete = {f: n for f, n in frames.items()
                if "vin" in n and n.get("left", 0) >= 2 and n.get("right", 0) >= 2}
    if not complete:
        return "no vertex with left>=2 and right>=2 real points (the tests cannot run)"
    worst = max(complete.items(), key=lambda kv: abs(kv[0] - min(complete)))
    f, n = worst
    failed = []
    if not (n["is_lowest"] and n["rise_left"] >= n["min_prominence"]
            and n["rise_right"] >= n["min_prominence"]):
        failed.append(f"bounce (lowest={n['is_lowest']}, rise {n['rise_left']}/"
                      f"{n['rise_right']} < {n['min_prominence']})")
    if not (n["vin"][0] * n["vout"][0] < 0 and abs(n["vin"][0]) > n["xrev_min"]):
        failed.append(f"redirect (vx {n['vin'][0]}->{n['vout'][0]}, no sign flip)")
    if not (n["speed"] >= n["drive_min_speed"] and n["stays_down"] and not n["pops_up"]):
        failed.append(f"drive (speed {n['speed']}, stays_down={n['stays_down']}, "
                      f"pops_up={n['pops_up']})")
    elif not (n["dvy"] <= -clf_DRIVE_DECEL() or abs(n["dvx"]) >= n["dx_impulse_min"]):
        failed.append(f"drive impulse (dvy {n['dvy']}, dvx {n['dvx']})")
    if not (n["pops_up"] and n["fed_ascent"] is not None
            and n["fed_ascent"] >= n["serve_accel_margin"]):
        failed.append(f"SERVE branch (pops_up={n['pops_up']}, fed_ascent="
                      f"{n['fed_ascent']} < {n['serve_accel_margin']})")
    return f"@f{f}: " + "; ".join(failed)


_CLF = classifier()
_DRIVE_DECEL = _CLF.DRIVE_DECEL


def clf_DRIVE_DECEL() -> float:
    return _DRIVE_DECEL


def best_vertex(info: Dict[str, Any], contact_frame: int) -> Optional[tuple]:
    """The complete vertex closest to the contact (where the tests COULD run)."""
    complete = {f: n for f, n in info["per_frame"].items() if "vin" in n}
    if not complete:
        return None
    return min(complete.items(), key=lambda kv: abs(kv[0] - contact_frame))


def gt_side(frame: int) -> str:
    """Side of this GT serve (read from the GT, never guessed from the file)."""
    blob = json.loads((ROOT / "ground_truth" / "20260920_match_contacts.json").read_text())
    for point in blob["points"]:
        for event in point.get("events", []):
            if event.get("action") == "serve" and int(event["match_frame"]) == frame:
                return str(event.get("owner_side"))
    return "?"


def summary_line(path: Path) -> str:
    """One line per serve: what each contact test could reach in the window.

    Thresholds come from the classifier instance itself (MIN_PROMINENCE 26 px,
    XREV_MIN 20 px, DRIVE_DECEL 8 px/f, DRIVE_XIMPULSE 12 px/f,
    SERVE_ACCEL_MARGIN_PX 10 px), so the numbers are comparable to production
    and cannot drift from it.
    """
    stem = path.stem            # pNNN_fFFFFF
    point = int(stem[1:4])
    frame = int(stem.split("_f")[1])
    frames = {}
    for line in path.read_text().splitlines():
        rec = json.loads(line)
        if "ball_track" in rec:
            frames[int(rec["frame"])] = rec["ball_track"]
    track = []
    for f in sorted(frames):
        bt = frames[f] or {}
        if bt.get("state") != "tracked":
            continue
        center = bt.get("center")
        if not center or center[0] is None:
            continue
        bbox = bt.get("bbox") or [center[0] - 5, center[1] - 5, center[0] + 5, center[1] + 5]
        track.append({"frame": f, "center": center,
                      "width": max(1, bbox[2] - bbox[0]), "height": max(1, bbox[3] - bbox[1])})
    side = gt_side(frame)
    # Apparent ball width from the RAW detections (the diag's track record has
    # no bbox). This is the quantity every contact threshold implicitly assumes:
    # 26 px of rise, a 20 px flip, an 8 px/f decel all scale with ball size.
    widths = []
    for line in path.read_text().splitlines():
        rec = json.loads(line)
        if not (frame - 40 <= int(rec.get("frame", -1)) <= frame + 15):
            continue
        for det in rec.get("ball_dets") or []:
            bbox = det.get("bbox")
            if bbox and len(bbox) == 4:
                widths.append(max(1, bbox[2] - bbox[0]))
    info = analyse(track, frame)
    widths = widths or [0]
    fired = ", ".join(f"{k}@f{f['frame']}({f['frame'] - frame:+d})" for k, f in
                      [(e["kind"], e) for e in info["fired"][:3]]) or "none"
    nums = [n for n in info["per_frame"].values() if "vin" in n]
    if not nums:
        return (f"{side:>4} P{point:<3} f{frame:<6} trk={len(track):<3} w~{max(widths):<3} "
                f"FIRED: {fired} | no usable vertex in +-15f")
    rise = max((min(n["rise_left"], n["rise_right"]) for n in nums if n["is_lowest"]),
               default=float("nan"))
    n_lowest = sum(1 for n in nums if n["is_lowest"])
    # Production redirect test: a horizontal SIGN FLIP in the net displacement,
    # both sides above XREV_MIN (and, in code, >= 2 sightings within +-3f).
    flips = sum(1 for n in nums if n["inc"][0] * n["out"][0] < 0
                and abs(n["inc"][0]) > n["xrev_min"] and abs(n["out"][0]) > n["xrev_min"])
    best_flip = max((min(abs(n["inc"][0]), abs(n["out"][0]))
                     for n in nums if n["inc"][0] * n["out"][0] < 0), default=0.0)
    best_dvy = min(n["dvy"] for n in nums)
    best_dvx = max(abs(n["dvx"]) for n in nums)
    best_fed = max((n["fed_ascent"] for n in nums if n["fed_ascent"] is not None),
                   default=float("nan"))
    n_pop = sum(1 for n in nums if n["pops_up"])
    # Pre-contact ball speed (px/frame) on the TRACKED sightings: the tracker's
    # lock floor is ball_lock_min_speed = 8 px/f, so this is the admission test.
    pre = [t for t in track if frame - 40 <= t["frame"] < frame]
    speeds = []
    for a, b in zip(pre, pre[1:]):
        dt = b["frame"] - a["frame"]
        if dt <= 0:
            continue
        speeds.append((((b["center"][0] - a["center"][0]) ** 2
                        + (b["center"][1] - a["center"][1]) ** 2) ** 0.5) / dt)
    top = max(speeds) if speeds else float("nan")
    return (f"{side:>4} P{point:<3} f{frame:<6} trk={len(track):<3} w~{max(widths):<3} "
            f"FIRED: {fired:<24} | vertices={len(nums):<3} "
            f"lowest={n_lowest:<3} best_rise={rise:6.0f}/26 | flips={flips}(best {best_flip:.0f}/20) | "
            f"best_dvy={best_dvy:+5.0f}/-8 best_dvx={best_dvx:4.0f}/12 | "
            f"pops_up={n_pop:<3} best_fed={best_fed:+5.0f}/10 | "
            f"pre_contact_speed_max={top:5.1f}/8 px-f")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default="",
                    help="diag JSONL from probe_far_serve_tracking (needs ball_track)")
    ap.add_argument("--dir", default="",
                    help="directory of such dumps: prints the whole table")
    ap.add_argument("--side", default="far")
    ap.add_argument("--point", type=int, default=0)
    ap.add_argument("--frame", type=int, default=0)
    args = ap.parse_args()

    if args.dir:
        print("side P    contact  trk   w   at f    the four contact tests at the closest usable vertex")
        for path in sorted(Path(args.dir).glob("*.jsonl")):
            print(summary_line(path))
        return 0
    if not args.dump:
        ap.error("need --dump or --dir")

    frames = {}
    for line in Path(args.dump).read_text().splitlines():
        rec = json.loads(line)
        if "ball_track" in rec:
            frames[int(rec["frame"])] = rec["ball_track"]
    track = []
    for frame in sorted(frames):
        bt = frames[frame] or {}
        if bt.get("state") not in ("tracked",):
            continue
        center = bt.get("center")
        if not center or center[0] is None:
            continue
        bbox = bt.get("bbox") or [center[0] - 5, center[1] - 5, center[0] + 5, center[1] + 5]
        track.append({"frame": frame, "center": center,
                      "width": max(1, bbox[2] - bbox[0]),
                      "height": max(1, bbox[3] - bbox[1])})
    print(f"P{args.point} contact f{args.frame}: {len(track)} tracked sightings")
    info = analyse(track, args.frame)
    print("reasons:", info["reasons"])
    print(verdict(info))
    for frame, numbers in sorted(info["per_frame"].items())[:14]:
        print(f"  f{frame}: {numbers}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
