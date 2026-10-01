#!/usr/bin/env python3
"""M1 -- does a MAGNIFIED far-end crop recover the far ball?

Root cause under test
---------------------
`docs/g4_far_serve_failure_mode.md` §3 measured two independent losses: the far
ball is *absent* (8/17 far-serve windows have 0-1 tracked frames, 2/17 have no raw
detection at conf 0.15) and, where it is present, its image motion is
depth-dominated so no shape test can fire.  The second half was attacked twice
and refuted (scale-aware geometry, session #52).  This probes the FIRST half,
which has never been attacked:

    the 20260920 match is natively 1280x720, upscaled once to 1920x1080, and
    the ball detector runs at imgsz 1280 on the 1920-wide frame.  A far ball
    measuring 14-28 px in the working frame was 9-19 px natively and is 9-19 px
    again inside YOLO -- at the stride-8 detection floor.  Nothing about the
    *weights* is wrong; the object is simply too small at the input scale.

So: run the SAME production weights on a SMALL SQUARE crop of the far band.
Ultralytics letterboxes by the max dimension, so only a crop that is small in
BOTH axes buys resolution -- a full-width band crop gains nothing.  With
``--tile 320`` a 14 px ball arrives at imgsz 1280 as 56 px (4x).

Three pre-registered kills (same style as T5/R1/S1):

* K1 -- the tiled pass must give a ball sighting within c+-15 f in at least
  **5 of the 8** far-serve windows that the full-frame pass leaves empty.
* K2 -- it must not cost false positives: the 24 mid-rally control windows may
  gain at most **1** window with a band sighting, and the extra detections must
  be a small fraction of the far-serve gain (reported as a ratio).
* K3 -- the measurement must be honest about width: the tiled arm's bbox width
  is compared with the full-frame arm's on the frames where both fire, because
  ``far_flight``'s depth cue (ln(width) slope) is only as good as the width.

Usage::

    venv/bin/python scripts/probe_far_roi_ball.py --device mps
    venv/bin/python scripts/probe_far_roi_ball.py --tile 480 --device cpu
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.detection.ball_detector import BallDetector  # noqa: E402
from src.utils.config import Config  # noqa: E402


def _load_scorer():
    spec = importlib.util.spec_from_file_location(
        "score_serve_events", ROOT / "scripts" / "score_serve_events.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_S = _load_scorer()
MATCH_CALIB, MATCH_GT = _S.MATCH_CALIB, _S.MATCH_GT
MATCH_VIDEO, BALL_MODEL = _S.MATCH_VIDEO, _S.BALL_MODEL
load_control_contacts = _S.load_control_contacts
load_far_serves = _S.load_far_serves
production_config = _S.production_config

WINDOW_BEFORE = 90
WINDOW_AFTER = 60


def band_tiles(calibration: Dict[str, Any], tile: int, y_margin_frac: float = 0.35) -> List[Tuple[int, int, int]]:
    """Square tiles covering the far runway band, from the 8 calibration clicks.

    The runway is ``front_frac`` above and ``back_frac`` below the far line as a
    FRACTION of the court's projected depth (AGENTS.md §7: px constants are
    venue-coupled).  x is the far line widened by the tile half-width, because
    the court is narrowest at the far line, so that span contains the whole
    runway.  Tiles are SQUARE so the letterbox has no padding and the un-scale
    is exact (``x_full = x0 + x_crop * tile / imgsz``).
    """
    fl, fr, nr, nl = (tuple(float(v) for v in c) for c in calibration["court_corners"][:4])
    far_mid_y = (fl[1] + fr[1]) / 2.0
    depth = abs((nl[1] + nr[1]) / 2.0 - far_mid_y) or 1.0
    band_top = far_mid_y - 0.15 * depth - y_margin_frac * depth
    band_bottom = far_mid_y + 0.30 * depth + y_margin_frac * depth
    # Vertically centre the band inside the first tile row.
    y0 = int(round((band_top + band_bottom) / 2.0 - tile / 2.0))
    x_lo = int(min(fl[0], fr[0]) - tile / 2)
    x_hi = int(max(fl[0], fr[0]) + tile / 2)
    tiles = []
    x = x_lo
    while x < x_hi:
        tiles.append((x, y0, tile))
        x += tile
    return tiles


def _inside_band(cal: Dict[str, Any], point: Tuple[float, float],
                 front_frac: float = 0.15, back_frac: float = 0.30) -> bool:
    """Runway-band membership in image space (x inside the far-line span + slack)."""
    fl, fr, nr, nl = (tuple(float(v) for v in c) for c in cal["court_corners"][:4])
    far_mid_y = (fl[1] + fr[1]) / 2.0
    depth = abs((nl[1] + nr[1]) / 2.0 - far_mid_y) or 1.0
    y = point[1]
    if not (far_mid_y - front_frac * depth <= y <= far_mid_y + back_frac * depth):
        return False
    # Interpolate the court's half-width at this depth and allow 25% slack, so
    # a server standing on the line is inside.
    t = (y - far_mid_y) / ((((nl[1] + nr[1]) / 2.0) - far_mid_y) or 1.0)
    left = fl[0] + t * (nl[0] - fl[0])
    right = fr[0] + t * (nr[0] - fr[0])
    slack = 0.25 * (right - left)
    return left - slack <= point[0] <= right + slack


class Arms:
    """Full-frame production arm + the tiled magnified arm."""

    def __init__(self, calibration: Dict[str, Any], device: str, tile: int,
                 conf: float = 0.15, imgsz: int = 1280) -> None:
        model = str(BALL_MODEL) if BALL_MODEL.exists() else None
        self.tile = tile
        self.imgsz = imgsz
        # Full-frame arm: the production detector, static suppression off so the
        # comparison is about PRESENCE, not about the phantom filter.
        self.full = BallDetector(model_path=model, confidence_threshold=conf,
                                 device=device, imgsz=imgsz, suppress_static=False)
        # Tile arm: same weights, fixed imgsz (the auto rule would pick 640 for a
        # 320 px crop and halve the magnification), no size filter -- the filter
        # is applied after un-scaling, in full-frame px.
        self.small = BallDetector(model_path=model, confidence_threshold=conf,
                                  device=device, imgsz=imgsz, suppress_static=False,
                                  max_ball_size=10 ** 6)
        self.tiles = band_tiles(calibration, tile)
        self.cal = calibration
        self.ms = {"full": 0.0, "tiled": 0.0, "frames": 0}

    def run(self, image: np.ndarray) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        t0 = time.time()
        full = self.full.detect(image)
        t1 = time.time()
        tiled: List[Dict[str, Any]] = []
        h, w = image.shape[:2]
        scale = self.tile / self.imgsz
        for x0, y0, side in self.tiles:
            x1, y1 = min(w, x0 + side), min(h, y0 + side)
            if x1 - x0 < 32 or y1 - y0 < 32:
                continue
            crop = image[y0:y1, x0:x1]
            for det in self.small.detect(crop):
                cx, cy = det["center"]
                bw = (det["bbox"][2] - det["bbox"][0]) * scale
                tiled.append({
                    "center": (x0 + cx * scale, y0 + cy * scale),
                    "width": bw,
                    "confidence": det["confidence"],
                    "tile": (x0, y0),
                })
        t2 = time.time()
        self.ms["full"] += t1 - t0
        self.ms["tiled"] += t2 - t1
        self.ms["frames"] += 1
        return full, tiled

    def timing(self) -> Dict[str, float]:
        n = max(1, self.ms["frames"])
        return {
            "frames": self.ms["frames"],
            "ms_full": round(1000 * self.ms["full"] / n, 1),
            "ms_tiled": round(1000 * self.ms["tiled"] / n, 1),
            "ms_tiled_per_tile": round(1000 * self.ms["tiled"] / n / max(1, len(self.tiles)), 1),
            "tiles": len(self.tiles),
        }


def empty_row(window: Dict[str, Any], start: int, end: int) -> Dict[str, Any]:
    return {
        "point": window["point"], "frame": window["frame"],
        "kind": window.get("action") or "serve", "held_out": window["held_out"],
        "window": [start, end], "frames_decoded": 0,
        "full_contact": 0, "tiled_contact": 0,
        "full_band_contact": 0, "tiled_band_contact": 0,
        "tiled_only_contact": 0, "tiled_extra_window": 0,
        "full_window": 0, "tiled_window": 0,
        "widths_full": [], "widths_tiled": [],
        "conf_full": [], "conf_tiled": [],
        "tiled_centers_contact": [],
    }


def observe(arms: Arms, row: Dict[str, Any], image: np.ndarray, frame: int,
            center: int, tolerance: int) -> None:
    """Accumulate one window's ball-presence evidence for one frame."""
    full, tiled = arms.run(image)
    in_contact = abs(frame - center) <= tolerance
    row["frames_decoded"] += 1
    if full:
        row["full_window"] += 1
    if tiled:
        row["tiled_window"] += 1
    if tiled and not full:
        row["tiled_extra_window"] += 1
    if not in_contact:
        return
    full_band = [d for d in full if _inside_band(arms.cal, d["center"])]
    tiled_band = [d for d in tiled if _inside_band(arms.cal, d["center"])]
    # Production also filters absurd sizes; mirror it after un-scaling.
    tiled_band = [d for d in tiled_band if d["width"] <= arms.full.max_ball_size]
    if full:
        row["full_contact"] += 1
    if tiled:
        row["tiled_contact"] += 1
    if tiled and not full:
        row["tiled_only_contact"] += 1
    if full_band:
        row["full_band_contact"] += 1
    if tiled_band:
        row["tiled_band_contact"] += 1
        row["tiled_centers_contact"].append([round(c) for c in tiled_band[0]["center"]])
    row["widths_full"] += [d["bbox"][2] - d["bbox"][0] for d in full]
    row["conf_full"] += [d["confidence"] for d in full]
    row["widths_tiled"] += [d["width"] for d in tiled]
    row["conf_tiled"] += [d["confidence"] for d in tiled]


def _unused_probe_window(arms: Arms, frames: Dict[int, np.ndarray], center: int,
                         tolerance: int = 15) -> Dict[str, Any]:
    """Ball presence per arm, in the contact window and in the wide window."""
    lo, hi = center - WINDOW_BEFORE, center + WINDOW_AFTER
    out: Dict[str, Any] = {
        "frames_in_contact": 0, "frames_in_window": 0,
        "full_contact": 0, "tiled_contact": 0,
        "full_window": 0, "tiled_window": 0,
        "full_band_contact": 0, "tiled_band_contact": 0,
        "tiled_only_contact": 0, "tiled_extra_window": 0,
        "widths_full": [], "widths_tiled": [],
        "conf_full": [], "conf_tiled": [],
        "tiled_centers_contact": [],
    }
    for frame, image in frames.items():
        if not (lo <= frame <= hi):
            continue
        out["frames_in_window"] += 1
        full, tiled = arms.run(image)
        in_contact = abs(frame - center) <= tolerance
        if in_contact:
            out["frames_in_contact"] += 1
        full_band = [d for d in full if _inside_band(arms.cal, d["center"])]
        tiled_band = [d for d in tiled if _inside_band(arms.cal, d["center"])]
        # Production also filters absurd sizes; mirror it after un-scaling.
        tiled_band = [d for d in tiled_band if d["width"] <= arms.full.max_ball_size]
        if full:
            out["full_window"] += 1
        if tiled:
            out["tiled_window"] += 1
        if full_band and in_contact:
            out["full_band_contact"] += 1
        if tiled_band:
            if in_contact:
                out["tiled_band_contact"] += 1
                out["tiled_centers_contact"].append(
                    [round(c) for c in tiled_band[0]["center"]])
        if in_contact:
            if full:
                out["full_contact"] += 1
            if tiled:
                out["tiled_contact"] += 1
            if tiled and not full:
                out["tiled_only_contact"] += 1
            for d in full:
                out["widths_full"].append(d["bbox"][2] - d["bbox"][0])
                out["conf_full"].append(d["confidence"])
            for d in tiled:
                out["widths_tiled"].append(d["width"])
                out["conf_tiled"].append(d["confidence"])
            # window-level extras
        if tiled and not full:
            out["tiled_extra_window"] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="mps")
    ap.add_argument("--tile", type=int, default=320)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--tolerance", type=int, default=15)
    ap.add_argument("--control-limit", type=int, default=24)
    ap.add_argument("--out", default="output/g4/far_roi_ball.json")
    args = ap.parse_args()

    calibration = json.loads((ROOT / MATCH_CALIB).read_text())
    arms = Arms(calibration, args.device, args.tile, imgsz=args.imgsz)
    mag = args.imgsz / args.tile
    print(f"tile {args.tile}px, imgsz {args.imgsz} -> magnification {mag:.2f}x; "
          f"{len(arms.tiles)} tiles: {arms.tiles}")

    serves = load_far_serves(ROOT / MATCH_GT)
    controls = load_control_contacts(ROOT / MATCH_GT, args.control_limit)
    windows = serves + controls

    cap = cv2.VideoCapture(str(MATCH_VIDEO))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {MATCH_VIDEO}")

    # ONE seek-free sequential pass (the AGENTS.md VFR rule): the frame index
    # used for scoring is the true decode index, so the +-15 f contact window is
    # exact.  A seek per window lands +-25 f off on this file, which would empty
    # the very windows this probe measures.
    wanted: Dict[int, List[int]] = {}
    rows: Dict[int, Dict[str, Any]] = {}
    for window in windows:
        center = window["frame"]
        start, end = center - WINDOW_BEFORE, center + WINDOW_AFTER
        rows[center] = empty_row(window, start, end)
        for frame in range(start, end + 1):
            wanted.setdefault(frame, []).append(center)

    t0 = time.time()
    frame = 0
    while True:
        ok, image = cap.read()
        if not ok:
            break
        for center in wanted.get(frame, ()):
            observe(arms, rows[center], image, frame, center, args.tolerance)
        if frame in wanted:
            done = sum(1 for r in rows.values() if r["frames_decoded"] > 0)
            print(f"  f{frame}  window {done}/{len(rows)}  "
                  f"[{time.time()-t0:.0f}s]", flush=True)
        frame += 1
    cap.release()
    report = [rows[w["frame"]] for w in windows]
    for row in report:
        print(f"P{row['point']:<3} f{row['frame']:<6} {row['kind']:<8} "
              f"{'held-out' if row['held_out'] else 'dev     '} "
              f"ball(c) full={row['full_contact']:<3} tiled={row['tiled_contact']:<3} "
              f"band(c) full={row['full_band_contact']:<3} tiled={row['tiled_band_contact']:<3} "
              f"tiled_only={row['tiled_only_contact']:<3} "
              f"extra_w={row['tiled_extra_window']:<3}")

    def agg(subset: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "n": len(subset),
            "empty_full": sum(1 for r in subset if r["full_contact"] == 0),
            "empty_tiled": sum(1 for r in subset if r["tiled_contact"] == 0),
            "recovered": sum(1 for r in subset
                             if r["full_contact"] == 0 and r["tiled_contact"] > 0),
            "band_empty_full": sum(1 for r in subset if r["full_band_contact"] == 0),
            "band_recovered": sum(1 for r in subset
                                  if r["full_band_contact"] == 0 and r["tiled_band_contact"] > 0),
            "tiled_only_frames": sum(r["tiled_only_contact"] for r in subset),
            "extra_window_frames": sum(r["tiled_extra_window"] for r in subset),
        }

    serves_rows = [r for r in report if r["kind"] == "serve"]
    control_rows = [r for r in report if r["kind"] != "serve"]
    empty_full = [r for r in serves_rows if r["full_contact"] == 0]
    recovered = [r for r in empty_full if r["tiled_contact"] > 0]
    control_new = [r for r in control_rows if r["tiled_contact"] > 0 and r["full_contact"] == 0]
    band_recovered = [r for r in serves_rows
                      if r["full_band_contact"] == 0 and r["tiled_band_contact"] > 0]
    control_band_new = [r for r in control_rows
                        if r["tiled_band_contact"] > 0 and r["full_band_contact"] == 0]
    widths_full = [w for r in serves_rows for w in r["widths_full"]]
    widths_tiled = [w for r in serves_rows for w in r["widths_tiled"]]
    summary = {
        "tile": args.tile, "imgsz": args.imgsz, "magnification": round(mag, 2),
        "device": args.device, "tiles": len(arms.tiles), "timing": arms.timing(),
        "far_serves": agg(serves_rows), "controls": agg(control_rows),
        "serve_windows_empty_full": len(empty_full),
        "serve_windows_recovered_by_tiles": len(recovered),
        "recovered_points": [f"P{r['point']}f{r['frame']}" for r in recovered],
        "band_serve_windows_recovered": len(band_recovered),
        "band_recovered_points": [f"P{r['point']}f{r['frame']}" for r in band_recovered],
        "control_windows_newly_seen": len(control_new),
        "control_windows_newly_seen_points": [f"P{r['point']}f{r['frame']}" for r in control_new],
        "control_band_windows_newly_seen": len(control_band_new),
        "kill_1_recover_5_of_empty": len(recovered) >= 5,
        "kill_2_control_cost_le_1_window": len(control_new) <= 1,
        "width_full_median": round(statistics.median(widths_full), 1) if widths_full else None,
        "width_tiled_median": round(statistics.median(widths_tiled), 1) if widths_tiled else None,
        "seconds": round(time.time() - t0, 1),
    }
    print("\nSUMMARY", json.dumps(summary, indent=1))

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": report}, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
