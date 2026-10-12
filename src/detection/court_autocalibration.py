"""Court calibration without clicks.

Finds the 8 calibration points of ``CourtCalibration`` (4 court corners, the 2
points under the net, the 2 on the net tape) from the picture itself, for the
standing recording setup (AGENTS.md §7: fixed camera on the court's long axis,
net facing the lens). No model: the court is line tape on sand.

    plate      temporal median of frames decoded in order: players and ball
               vanish, tape and net stay.
    tape       thin structures on the sand whose COLOUR is not the sand's (a
               shadow only changes brightness). Half-buried tape is barely
               above the sand's own noise, so lines are found by what adds up
               along them, then once more on the tape's own colour, which is
               read off the court just found and never assumed.
    court      the near baseline and the two sidelines that leave its ends and
               converge upwards: the triple with the most tape on it. Each tape
               is then followed as it lies (it bows); a corner is where two
               tapes cross.
    net        a tape is ONE object of one colour from sideline to sideline in
               front of trees, fences and buildings: along its line the colour
               hardly varies, just above and below it varies a lot. Its two
               edges then say exactly where it runs.
    far end    the near baseline and the net tape are parallel in the world, so
               they fix the direction of every line ACROSS the court. The far
               baseline is the one of those lines the picture supports: where
               a sideline's tape ends (short of the corner when its last
               stretch is buried, never beyond), far tape where it shows. One
               such read is a proposal; two that agree are a calibration. The
               camera being the same one from video to video, the focal length
               earlier calibrations imply is one more read.

Everything it could not see, or that its reads disagree on, is reported in
``checks`` and makes the result ``accepted: false``: a calibration nobody
looked at must rather be refused than be wrong (AGENTS.md §11, §14). Measured
record: ``docs/auto_calibration.md``; scorer: ``scripts/score_autocalibration.py``.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from src.utils.video_upscale import ensure_1080, resolve_source_stem

COURT_LENGTH_M = 16.0
COURT_WIDTH_M = 8.0

VERSION = 6

# -- plate ------------------------------------------------------------------- #
PLATE_SPAN_S = 180.0          # where the plate's frames come from (start of the video)
PLATE_FRAMES = 45

# -- tape -------------------------------------------------------------------- #
#: Rows (fraction of the height, from the top) that are sand on a long-axis view.
SAND_ROWS_FROM = 0.55
#: Evidence threshold = this percentile of the evidence on plain sand, clamped
#: (robust standard deviations of the sand's own colour). Weak tape is only a
#: little above the sand; what tells it apart is that it adds up along a line.
RIDGE_SAND_PERCENTILE = 97.0
RIDGE_Z_RANGE = (2.0, 5.0)
#: Blurred colour this close to the sand's (robust sd) is sand.
SAND_Z = 4.0
#: Largest thing lying on the sand that is still part of it (share of the frame).
SAND_HOLE_FRAC = 0.01
#: Widest structure that still counts as thin, as a fraction of the frame width
#: (a 5 cm tape is ~12 px at the near baseline of a 1080p frame).
RIDGE_WIDTH_FRAC = 15.0 / 1920.0

# -- lines ------------------------------------------------------------------- #
HOUGH_VOTES_FRAC = 0.07       # accumulator votes for a line, fraction of the frame width
SPECKLE_MAX_PX = 8            # a ridge shorter than this in both directions is sand noise
HOUGH_KEEP = 60               # strongest distinct lines kept
LINE_BAND_PX = 5.0            # ridge pixels this close to a line belong to it
BASELINE_MAX_SLOPE = 0.105    # |dy/dx| of a line across the court (6 degrees)
SIDELINE_MIN_SLOPE = 0.14     # |dy/dx| of a sideline (8 degrees)
#: A sideline is scored on this first part of its way to the vanishing point
#: (the far corner lies beyond it on every long-axis view).
SIDELINE_SCORED_SHARE = 0.5
SIDELINE_MIN_COVERAGE = 0.25
SIDELINE_ACCEPT_COVERAGE = 0.5  # tape seen on this much of a sideline, up to its far corner
NEAR_MIN_COVERAGE = 0.35

# -- depth along a sideline -------------------------------------------------- #
#: Walking a sideline from its near corner towards the vanishing point, the
#: world distance covered is ``Z * q`` with ``q = s / (T - s)`` (s px walked,
#: T px to the vanishing point) and Z the near corner's distance from the lens
#: plane. Tolerances below are metres at a nominal Z: they bridge and separate,
#: they measure nothing.
NOMINAL_Z_M = 8.0
Q_BIN_M = 0.1                 # resolution of the walk
TAPE_BRIDGE_M = 0.5           # buried stretch that does not end a run of tape
TAPE_RUN_MIN_M = 0.4          # shortest stretch that counts as tape
TAPE_QUIET_M = 1.2            # sand without tape that makes a run's end a candidate corner
TAPE_RUN_DENSITY = 0.6        # share of a run that must be tape seen, not bridged
WALK_BAND_PX = 3.0            # tape this close to the sideline's curve is on it
CURVE_BAND_PX = 5.0           # tape this close to where the curve points extends it
CURVE_MAX_SLOPE = 0.08        # a tape strays from its straight line by 4.5 degrees at most
CURVE_MIN_STEP_PX = 0.6       # ... and moves sideways by this, per step, where steps are short
CURVE_NODE_M = 0.25           # the tape is followed in steps of this
SAND_Z_LOCAL = 6.0            # colour beside the line this close to the sand's = on the sand
#: The tape is also read by its darkness when, on the court's own lines, it is
#: this many times darker than the sand's strongest shadows (floodlit sand).
DARK_TAPE_FACTOR = 1.6
Q_FAR_RANGE = (0.9, 4.5)      # far corner: 16 m beyond the near one, lens 3.5-18 m behind it
FAR_AGREE_M = 1.0             # two reads of the far baseline closer than this agree
#: The camera is the same one from video to video (AGENTS.md §7), so the focal
#: length earlier calibrations imply is known. Where the far baseline must be
#: for THIS court to imply it too is one more read of the far baseline.
CAMERA_AGREE_M = 0.6          # ... and a tape read this close to it is confirmed by it
FOCAL_CLUSTER = 0.04          # focal lengths this close (relative) are one lens setting
FOCAL_MIN_VIDEOS = 3          # views that must share a setting before it is trusted
FAR_TAPE_MIN_COVERAGE = 0.20  # of the far baseline, in unbroken stretches of tape
FAR_TAPE_RUN_M = 0.25         # shortest such stretch
FAR_TAPE_MIN_EXCESS = 0.15    # over the typical across-line there

# -- net --------------------------------------------------------------------- #
NET_HEIGHT_RANGE_M = (1.95, 2.75)   # where a net's top can be (2.24 women, 2.43 men)
NET_TAPE_MAX_M = 0.20               # a band thicker than this is not a tape
NET_BESIDE_M = 0.30                 # what is behind a tape shows within this, above and below
NET_MAX_SPREAD = 30.0               # colour range along a tape (Lab units)
NET_MIN_CONTRAST = 2.5              # ... and how many times more just above and below it
NET_NEAR_BEST = 0.4                 # bands this clear (of the clearest) may be the tape
NET_REFINE_PX = 14.0                # the tape's edges are looked for this close to the band found
NET_REFINE_SLOPE = 0.014
NET_HEIGHT_OK_M = (2.10, 2.60)      # read through the finished calibration


def _hom(p: Sequence[float]) -> np.ndarray:
    return np.array([float(p[0]), float(p[1]), 1.0])


@dataclass
class Line:
    """An image line with the ridge pixels that support it."""
    point: np.ndarray                 # a point on the line
    direction: np.ndarray             # unit vector, x component >= 0
    pixels: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    residual: float = 0.0             # median |distance| of the support, px

    @property
    def hom(self) -> np.ndarray:
        return np.cross(_hom(self.point), _hom(self.point + self.direction))

    @property
    def slope(self) -> float:
        dx, dy = self.direction
        return float(dy / dx) if abs(dx) > 1e-9 else math.copysign(1e9, dy)

    def along(self, pts: np.ndarray) -> np.ndarray:
        return (np.asarray(pts, dtype=float) - self.point) @ self.direction

    def offset(self, pts: np.ndarray) -> np.ndarray:
        normal = np.array([-self.direction[1], self.direction[0]])
        return (np.asarray(pts, dtype=float) - self.point) @ normal

    def at(self, t: float) -> np.ndarray:
        return self.point + t * self.direction

    def y_at(self, x: float) -> float:
        return float(self.point[1] + (x - self.point[0]) * self.slope)

    def x_at(self, y: float) -> float:
        return float(self.point[0] + (y - self.point[1]) / self.slope)

    @property
    def extent(self) -> Tuple[float, float]:
        if not len(self.pixels):
            return 0.0, 0.0
        t = self.along(self.pixels)
        return float(t.min()), float(t.max())

    def coverage(self, lo: float, hi: float, bin_px: float = 4.0) -> float:
        """Share of [lo, hi] along the line that has ridge pixels."""
        if not len(self.pixels) or hi - lo < bin_px:
            return 0.0
        t = self.along(self.pixels)
        bins = np.unique(((t[(t >= lo) & (t <= hi)] - lo) // bin_px).astype(int))
        return float(len(bins) / math.ceil((hi - lo) / bin_px))

    def in_frame(self, frame_w: int) -> Tuple[float, float]:
        """The stretch of the line (as ``along`` values) inside the frame's columns."""
        ts = self.along(np.array([[x, self.y_at(x)] for x in (0.0, frame_w - 1.0)]))
        return float(ts.min()), float(ts.max())


@dataclass
class Curve:
    """A line tape as it lies: its straight line plus how far the tape strays
    from it, followed step by step."""
    base: Line
    nodes: np.ndarray = field(default_factory=lambda: np.zeros(1))    # ``along``, increasing
    stray: np.ndarray = field(default_factory=lambda: np.zeros(1))    # offset from the base there
    pixels: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    residual: float = 0.0

    def bow(self, t):
        t = np.asarray(t, dtype=float)
        out = np.interp(t, self.nodes, self.stray)
        if len(self.nodes) >= 2:                     # beyond the ends: carry on straight
            for edge, inner, side in ((0, 1, t < self.nodes[0]), (-1, -2, t > self.nodes[-1])):
                slope = (self.stray[edge] - self.stray[inner]) / (self.nodes[edge] - self.nodes[inner])
                out = np.where(side, self.stray[edge] + slope * (t - self.nodes[edge]), out)
        return out

    def point(self, t: float) -> np.ndarray:
        normal = np.array([-self.base.direction[1], self.base.direction[0]])
        return self.base.at(t) + float(self.bow(t)) * normal

    def tangent(self, t: float) -> Line:
        a, b = self.point(t - 4.0), self.point(t + 4.0)
        d = (b - a) / np.linalg.norm(b - a)
        return Line(self.point(t), d if d[0] >= 0 else -d)

    def meet(self, other: Line, t0: float) -> Tuple[float, np.ndarray]:
        """Where the curve crosses ``other``, starting the search at ``t0``."""
        t = t0
        for _ in range(8):
            p = intersect(self.tangent(t), other)
            if p is None:
                break
            new = float(self.base.along(p))
            done = abs(new - t) < 0.05
            t = new
            if done:
                break
        return t, self.point(t)


def fit_curve(line: Line, pts: np.ndarray, nodes: np.ndarray, start: int,
              band: float = CURVE_BAND_PX) -> Curve:
    """Follow the tape along ``line``, from ``nodes[start]`` (where the
    straight line fits the tape best) outwards in both directions: at every
    node the tape is looked for beside where the last metres of tape point to.
    Where there is none (buried, or the tape is over) the direction is kept."""
    t_all, o_all = line.along(pts), line.offset(pts)
    close = np.abs(o_all) <= 60.0
    t_all, o_all, kept = t_all[close], o_all[close], pts[close]
    stray = np.zeros(len(nodes))
    found = np.zeros(len(nodes), dtype=bool)
    used = np.zeros(len(t_all), dtype=bool)
    for step in (1, -1):
        offset, slope = (stray[start], 0.0) if step == -1 else (0.0, 0.0)
        order = range(start, len(nodes)) if step == 1 else range(start - 1, -1, -1)
        prev = start
        trail: List[int] = [start] if (step == -1 and found[start]) else []
        for k in order:
            t_k = nodes[k]
            half = max(12.0, abs(nodes[min(k + 2, len(nodes) - 1)] - nodes[max(k - 2, 0)]) / 2.0)
            offset += slope * (t_k - nodes[prev])
            sel = (np.abs(t_all - t_k) <= half) & \
                  (np.abs(o_all - (offset + slope * (t_all - t_k))) <= band)
            if sel.sum() >= 6:
                seen = float(np.median(o_all[sel] - slope * (t_all[sel] - t_k)))
                if trail:
                    # A tape bows, it does not turn: at a corner the OTHER tape
                    # starts beside this one and must not be followed.
                    limit = max(CURVE_MIN_STEP_PX, 2.0 * CURVE_MAX_SLOPE * abs(t_k - nodes[prev]))
                    seen = float(np.clip(seen, offset - limit, offset + limit))
                offset = seen
                found[k] = True
                used |= sel
                trail.append(k)
            stray[k] = offset
            recent = trail[-8:]
            if len(recent) >= 4:                     # where the last metres of tape point
                fit = np.polyfit(nodes[recent], stray[recent], 1)
                slope = float(np.clip(fit[0], -CURVE_MAX_SLOPE, CURVE_MAX_SLOPE))
            prev = k
    order = np.argsort(nodes)
    curve = Curve(line, nodes[order], stray[order], kept[used])
    if used.any():
        curve.residual = float(np.median(np.abs(o_all[used] - curve.bow(t_all[used]))))
    return curve


def intersect(a: Line, b: Line) -> Optional[np.ndarray]:
    p = np.cross(a.hom, b.hom)
    if abs(p[2]) < 1e-9:
        return None
    return p[:2] / p[2]


def line_through(p: np.ndarray, q_hom: np.ndarray) -> Line:
    """The line through image point ``p`` and homogeneous point ``q_hom``
    (which may be a point at infinity)."""
    if abs(q_hom[2]) < 1e-12 * max(1.0, float(np.abs(q_hom[:2]).max())):
        d = q_hom[:2].astype(float)
    else:
        d = q_hom[:2] / q_hom[2] - p
    d = d / np.linalg.norm(d)
    if d[0] < 0:
        d = -d
    return Line(np.asarray(p, dtype=float), d)


# -- plate ------------------------------------------------------------------- #

def read_frames(video: Path, span_s: float = PLATE_SPAN_S, n: int = PLATE_FRAMES
                ) -> List[np.ndarray]:
    """``n`` frames spread over the first ``span_s`` seconds, decoded in order
    (never positioned by a seek: AGENTS.md §9)."""
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or int(span_s * fps)
    last = int(min(total - 1, span_s * fps))
    stride = max(1, last // max(n, 1))
    frames: List[np.ndarray] = []
    index = 0
    while index <= last:
        if not cap.grab():
            break
        if index % stride == 0:
            ok, frame = cap.retrieve()
            if ok:
                frames.append(frame)
        index += 1
    cap.release()
    if not frames:
        raise RuntimeError(f"no frame decoded from {video}")
    return frames


def median_plate(frames: Sequence[np.ndarray]) -> np.ndarray:
    return np.median(np.stack(frames), axis=0).astype(np.uint8)


# -- tape -------------------------------------------------------------------- #

@dataclass
class TapeMaps:
    lab: np.ndarray
    sand_ab: np.ndarray
    sand_mad: np.ndarray
    sand: np.ndarray                  # uint8 mask: the sand the court lies on, rim included
    sand_core: np.ndarray             # uint8 mask: the sand proper
    z: np.ndarray                     # float: colour distance from the sand (robust sd)
    evidence: np.ndarray              # float: thin + not sand-coloured
    threshold: float
    ridge: np.ndarray                 # uint8 mask: evidence over threshold, on the sand
    tape: np.ndarray                  # uint8 mask: the same for the tape's own colour
    tape_ab: Optional[np.ndarray] = None
    tape_evidence: Optional[np.ndarray] = None
    tape_threshold: float = 0.0
    dark_tape: bool = False
    any_evidence: Optional[np.ndarray] = None


def _kernel(frame_w: int) -> np.ndarray:
    k = max(7, int(round(RIDGE_WIDTH_FRAC * frame_w)) | 1)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))


def _sand_region(z: np.ndarray) -> np.ndarray:
    """The connected sand the lower part of the picture belongs to."""
    h, w = z.shape
    k = max(9, int(round(15 / 1920 * w)) | 1)
    smooth = cv2.GaussianBlur(z, (k, k), 0)
    sand = (smooth < SAND_Z).astype(np.uint8)
    sand = cv2.morphologyEx(sand, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    count, labels, _, _ = cv2.connectedComponentsWithStats(sand, connectivity=4)
    if count <= 1:
        return np.zeros((h, w), np.uint8)
    lower = labels[int(h * SAND_ROWS_FROM):, :]
    ids, votes = np.unique(lower[lower > 0], return_counts=True)
    if not len(ids):
        return np.zeros((h, w), np.uint8)
    keep = (labels == ids[np.argmax(votes)]).astype(np.uint8)
    # what lies ON the sand (tape, a bag, a ball) is part of it; a net, a
    # stand or a building the sand merely surrounds is not
    holes, hole_labels, hole_stats, _ = cv2.connectedComponentsWithStats(1 - keep, connectivity=4)
    for i in range(1, holes):
        if hole_stats[i, cv2.CC_STAT_AREA] <= SAND_HOLE_FRAC * h * w:
            keep[hole_labels == i] = 1
    return keep * 255


def _threshold(evidence: np.ndarray, sand: np.ndarray) -> float:
    values = evidence[sand > 0]
    if not len(values):
        return RIDGE_Z_RANGE[0]
    return float(np.clip(np.percentile(values, RIDGE_SAND_PERCENTILE), *RIDGE_Z_RANGE))


def chroma_ridges(plate: np.ndarray) -> TapeMaps:
    """Thin structures on the sand whose colour is not the sand's."""
    h, w = plate.shape[:2]
    lab = cv2.cvtColor(plate, cv2.COLOR_BGR2LAB).astype(np.float32)
    rows = lab[int(h * SAND_ROWS_FROM):, :, 1:].reshape(-1, 2)
    med = np.median(rows, axis=0)
    mad = np.maximum(np.median(np.abs(rows - med), axis=0), 0.75)
    z = np.sqrt((((lab[:, :, 1:] - med) / (1.4826 * mad)) ** 2).sum(axis=2))
    core = _sand_region(z)
    k = max(9, int(round(15 / 1920 * w)) | 1)
    sand = cv2.dilate(core, np.ones((k, k), np.uint8))     # tape on the sand's rim counts
    evidence = cv2.morphologyEx(z, cv2.MORPH_TOPHAT, _kernel(w))
    thr = _threshold(evidence, sand)
    ridge = ((evidence > thr) & (sand > 0)).astype(np.uint8) * 255
    return TapeMaps(lab=lab, sand_ab=med, sand_mad=mad, sand=sand, sand_core=core, z=z,
                    evidence=evidence, threshold=thr, ridge=ridge, tape=ridge.copy())


def tape_colour(maps: TapeMaps, lines: Sequence["Line"]) -> None:
    """Read the tape's colour off the court's own lines and keep, in
    ``maps.tape``, only what departs from the sand TOWARDS that colour."""
    px = np.concatenate([ln.pixels for ln in lines]).astype(int)
    if not len(px):
        return
    scale = 1.4826 * maps.sand_mad
    zs = (maps.lab[px[:, 1], px[:, 0], 1:] - maps.sand_ab) / scale
    strength = np.linalg.norm(zs, axis=1)
    core = zs[strength >= np.median(strength)]      # the pixels that are tape for sure
    axis = np.median(core, axis=0)
    norm = float(np.linalg.norm(axis))
    if norm < 1e-6:
        return
    maps.tape_ab = maps.sand_ab + axis * scale
    along = np.maximum(((maps.lab[:, :, 1:] - maps.sand_ab) / scale) @ (axis / norm), 0.0)
    w = maps.lab.shape[1]
    colour = cv2.morphologyEx(along.astype(np.float32), cv2.MORPH_TOPHAT, _kernel(w))
    evidence = colour / max(_threshold(colour, maps.sand), 1e-6)       # 1.0 = threshold
    # A tape that is much darker than any shadow on the sand (floodlights) is
    # read by its darkness too: buried, it keeps no colour but stays dark.
    dark = cv2.morphologyEx(maps.lab[:, :, 0], cv2.MORPH_BLACKHAT, _kernel(w))
    shadows = float(np.percentile(dark[maps.sand > 0], 99.0)) if (maps.sand > 0).any() else 0.0
    on_tape = float(np.median(dark[px[:, 1], px[:, 0]]))
    maps.dark_tape = shadows > 0 and on_tape >= DARK_TAPE_FACTOR * shadows
    if maps.dark_tape:
        evidence = np.maximum(evidence, dark / (0.5 * (shadows + on_tape)))
    maps.tape_evidence = evidence
    maps.tape_threshold = 1.0
    maps.tape = ((evidence > 1.0) & (maps.sand > 0)).astype(np.uint8) * 255
    # Far from the lens the tape is faded, dirty or half buried and no longer
    # of that exact colour: where the court's own lines say WHERE to look, any
    # thin thing that is not sand-coloured counts.
    maps.any_evidence = np.maximum(evidence, maps.evidence / max(maps.threshold, 1e-6))


# -- lines ------------------------------------------------------------------- #

def fit_line(pixels: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    vx, vy, x0, y0 = cv2.fitLine(pixels.astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
    d = np.array([vx, vy], dtype=float)
    if d[0] < 0:
        d = -d
    p = np.array([x0, y0], dtype=float)
    r = np.abs((pixels - p) @ np.array([-d[1], d[0]]))
    return p, d, float(np.median(r)) if len(r) else 0.0


def refit(line: Line, pts: np.ndarray, bands: Sequence[float] = (7.0, LINE_BAND_PX, 3.5),
          lo: float = -math.inf, hi: float = math.inf) -> Optional[Line]:
    """``line`` moved onto the ridge pixels beside it (between ``lo`` and
    ``hi`` along it)."""
    for band in bands:
        t = line.along(pts)
        sel = (np.abs(line.offset(pts)) <= band) & (t >= lo) & (t <= hi)
        if sel.sum() < 25:
            return None
        anchor = line.point
        p, d, res = fit_line(pts[sel])
        # anchored at the foot of the old anchor, so ``lo`` / ``hi`` keep their meaning
        foot = p + float((anchor - p) @ d) * d
        line = Line(foot, d, pts[sel], res)
    return line


def thin(mask: np.ndarray) -> np.ndarray:
    """The middle of every ridge: a tape is 12 px wide near the lens, and a
    line fitted on all of it can lie anywhere inside."""
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
    peak = cv2.dilate(dist, np.ones((3, 3), np.uint8))
    return ((dist >= peak - 1e-6) & (mask > 0)).astype(np.uint8) * 255


def despeckle(mask: np.ndarray, max_px: int = SPECKLE_MAX_PX) -> np.ndarray:
    """``mask`` without the specks no tape is made of."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    small = np.maximum(stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT]) < max_px
    small[0] = True                                  # the background
    out = mask.copy()
    out[small[labels]] = 0
    return out


def mask_points(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(mask)
    return np.stack([xs, ys], axis=1).astype(float)


def strong_lines(mask: np.ndarray, votes_frac: float = HOUGH_VOTES_FRAC,
                 keep: int = HOUGH_KEEP, bands: Sequence[float] = (7.0, LINE_BAND_PX, 3.5),
                 ridges: bool = True) -> List[Line]:
    """The lines most ridge pixels lie on, however broken (accumulator
    voting: a half-buried tape still adds up over its whole length)."""
    w = mask.shape[1]
    if ridges:                                       # ``False``: already one pixel wide
        mask = despeckle(mask)
    found = cv2.HoughLines(mask, 1, np.pi / 720, int(votes_frac * w))
    if found is None:
        return []
    pts = mask_points(thin(mask) if ridges else mask)
    lines: List[Line] = []
    for rho, theta in found[:, 0][:600]:
        c, s_ = math.cos(theta), math.sin(theta)
        d = np.array([-s_, c]) if -s_ >= 0 else np.array([s_, -c])
        seed = Line(np.array([c * rho, s_ * rho]), d)
        probe = np.array([seed.at(t) for t in (-w / 2.0, 0.0, w / 2.0)])
        if any(np.abs(ln.offset(probe)).max() < 14.0 for ln in lines):
            continue                                # a line already kept runs here
        fitted = refit(seed, pts, bands)
        if fitted is None:
            continue
        lo, hi = fitted.extent
        probe = np.array([fitted.at(t) for t in (lo, (lo + hi) / 2.0, hi)])
        if any(np.abs(ln.offset(probe)).max() < 6.0 for ln in lines):
            continue
        lines.append(fitted)
        if len(lines) >= keep:
            break
    return lines


# -- court ------------------------------------------------------------------- #

@dataclass
class CourtLines:
    near: Line
    left: Line
    right: Line
    near_left: np.ndarray
    near_right: np.ndarray
    vanishing: np.ndarray             # where the sidelines meet


def find_court(lines: Sequence[Line], frame_w: int, frame_h: int) -> Optional[CourtLines]:
    """The near baseline and the two sidelines that leave its ends: the triple
    with the most tape on it."""
    level = [ln for ln in lines if abs(ln.slope) <= BASELINE_MAX_SLOPE
             and ln.y_at(frame_w / 2.0) > 0.4 * frame_h]
    steep = [ln for ln in lines if abs(ln.slope) >= SIDELINE_MIN_SLOPE]
    best: Optional[Tuple[float, CourtLines]] = None
    for near in level:
        lefts, rights = [], []
        for ln in steep:
            corner = intersect(ln, near)
            if corner is None:
                continue
            if ln.slope < 0 and -0.3 * frame_w <= corner[0] <= 0.5 * frame_w:
                lefts.append((ln, corner))
            elif ln.slope > 0 and 0.5 * frame_w <= corner[0] <= 1.3 * frame_w:
                rights.append((ln, corner))
        f_lo, f_hi = near.in_frame(frame_w)
        for left, nl in lefts:
            for right, nr in rights:
                v = intersect(left, right)
                if nr[0] - nl[0] < 0.5 * frame_w or v is None:
                    continue
                if v[1] > near.y_at(v[0]) - 0.2 * frame_h or not (nl[0] < v[0] < nr[0]):
                    continue
                lo = max(float(near.along(nl)), f_lo)
                hi = min(float(near.along(nr)), f_hi)
                cov_near = near.coverage(lo, hi)
                if cov_near < NEAR_MIN_COVERAGE:
                    continue
                score = cov_near * (hi - lo)
                ok = True
                for side, corner in ((left, nl), (right, nr)):
                    t0, tv = float(side.along(corner)), float(side.along(v))
                    t1 = t0 + SIDELINE_SCORED_SHARE * (tv - t0)
                    s_lo, s_hi = side.in_frame(frame_w)
                    lo_s, hi_s = max(min(t0, t1), s_lo), min(max(t0, t1), s_hi)
                    cov = side.coverage(lo_s, hi_s) if hi_s > lo_s else 0.0
                    if cov < SIDELINE_MIN_COVERAGE:
                        ok = False
                        break
                    score += cov * (hi_s - lo_s)
                if ok and (best is None or score > best[0]):
                    best = (score, CourtLines(near, left, right, nl, nr, v))
    return None if best is None else best[1]


# -- walking a sideline ------------------------------------------------------ #

@dataclass
class Sideline:
    """One sideline's tape, walked from its near corner towards the vanishing point."""
    curve: Curve
    t_near: float                     # ``along`` of the near corner on the base line
    t_van: float                      # ... of the vanishing point
    on: np.ndarray = field(default_factory=lambda: np.zeros(0, bool))     # per q bin: tape there
    valid: np.ndarray = field(default_factory=lambda: np.zeros(0, bool))  # per q bin: sand there

    @property
    def sign(self) -> float:
        return 1.0 if self.t_van > self.t_near else -1.0

    @property
    def total(self) -> float:
        return abs(self.t_van - self.t_near)

    @staticmethod
    def q_step() -> float:
        return Q_BIN_M / NOMINAL_Z_M

    def t_of_q(self, q: float) -> float:
        return self.t_near + self.sign * self.total * q / (1.0 + q)

    def point_at(self, q: float) -> np.ndarray:
        return self.curve.point(self.t_of_q(q))

    def q_of(self, point: np.ndarray) -> float:
        s = self.sign * float(self.curve.base.along(point) - self.t_near)
        return s / max(self.total - s, 1e-6)

    def meet(self, other: Line, q0: float) -> Tuple[float, np.ndarray]:
        t, p = self.curve.meet(other, self.t_of_q(q0))
        return self.q_of(p), p

    def coverage(self, q_to: float, q_from: float = 0.0) -> float:
        a, b = int(q_from / self.q_step()), int(q_to / self.q_step())
        seen = self.valid[a:b]
        return float(self.on[a:b][seen].mean()) if seen.any() else 0.0

    def runs_beyond(self, q: float, ends: Sequence[float]) -> float:
        """How far (q) this sideline's tape runs on, unbroken, beyond ``q``:
        a tape cannot pass its own far corner, so a far baseline at ``q`` with
        tape well beyond it is not the far baseline."""
        beyond = [e for e in ends if e > q and self.coverage(e, q) >= TAPE_RUN_DENSITY]
        return max(beyond) - q if beyond else 0.0

    def ends(self) -> List[float]:
        """q of every place the tape stops for good: the far edge of a solid
        run followed by sand without tape."""
        step = self.q_step()
        bridge, run_min, quiet = (int(round(v / Q_BIN_M)) for v in
                                  (TAPE_BRIDGE_M, TAPE_RUN_MIN_M, TAPE_QUIET_M))
        on = self.on.copy()
        idx = np.flatnonzero(on)
        for a, b in zip(idx[:-1], idx[1:]):          # bridge buried stretches
            if 1 < b - a <= bridge + 1:
                on[a:b] = True
        out: List[float] = []
        i, n = 0, len(on)
        while i < n:
            if not on[i]:
                i += 1
                continue
            j = i
            while j + 1 < n and on[j + 1]:
                j += 1
            real = int(self.on[i:j + 1].sum())
            if real >= run_min and real >= TAPE_RUN_DENSITY * (j - i + 1):
                after = self.on[j + 1:j + 1 + quiet]
                seen = self.valid[j + 1:j + 1 + quiet]
                # quiet sand behind it (or the sand itself ends there)
                if len(after) == 0 or after[seen].sum() <= max(1, int(0.15 * max(1, seen.sum()))):
                    out.append((j + 1) * step)
            i = j + 1
        return out


class SandTest:
    """Is the picture sand on BOTH sides of a point? (a banner's edge, a net
    band or a wall have sand on one side at most)."""
    FLANK = np.array([9.0, 13.0, 17.0])

    def __init__(self, maps: TapeMaps) -> None:
        self.beside = cv2.GaussianBlur(maps.z, (5, 5), 0)
        self.core = maps.sand_core
        self.h, self.w = self.beside.shape

    def __call__(self, centre: np.ndarray, normal: np.ndarray) -> bool:
        for side in (-1.0, 1.0):
            pts = centre + np.outer(side * self.FLANK, normal)
            xi, yi = np.round(pts[:, 0]).astype(int), np.round(pts[:, 1]).astype(int)
            inside = (xi >= 0) & (xi < self.w) & (yi >= 0) & (yi < self.h)
            sandy = (self.beside[yi[inside], xi[inside]] < SAND_Z_LOCAL) & \
                    (self.core[yi[inside], xi[inside]] > 0)
            if sandy.sum() < 2:
                return False
        return True


def walk_sideline(side: Sideline, maps: TapeMaps, sand: SandTest,
                  band: float = WALK_BAND_PX) -> None:
    """Fill ``side.on`` / ``side.valid``: tape seen along the curve, per q bin."""
    evidence, thr = maps.any_evidence, 1.0
    h, w = evidence.shape
    step = Sideline.q_step()
    n_bins = int(Q_FAR_RANGE[1] / step) + 1
    on = np.zeros(n_bins, dtype=bool)
    valid = np.zeros(n_bins, dtype=bool)
    normal = np.array([-side.curve.base.direction[1], side.curve.base.direction[0]])
    offsets = np.arange(-band, band + 0.5, 1.0)
    for k in range(n_bins):
        t0, t1 = side.t_of_q(k * step), side.t_of_q((k + 1) * step)
        n = max(1, int(math.ceil(abs(t1 - t0))))
        hits, seen = 0, 0
        for t in np.linspace(t0, t1, n, endpoint=False):
            centre = side.curve.point(float(t))
            if not (0 <= centre[0] < w and 0 <= centre[1] < h) or not sand(centre, normal):
                continue
            pts = centre + np.outer(offsets, normal)
            xi, yi = np.round(pts[:, 0]).astype(int), np.round(pts[:, 1]).astype(int)
            inside = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
            seen += 1
            hits += bool((evidence[yi[inside], xi[inside]] > thr).any())
        valid[k] = seen > 0
        on[k] = seen > 0 and hits >= max(1, int(math.ceil(0.5 * seen)))
    side.on, side.valid = on, valid


@dataclass
class Court:
    near: Curve
    left: Sideline
    right: Sideline
    near_left: np.ndarray
    near_right: np.ndarray


#: The tape is followed from this far along a sideline (q), where the straight
#: fit is at its best, and from the middle of the near baseline.
FOLLOW_FROM_Q = 0.45
NEAR_TAIL_Q = -0.08                    # ... and a little past the near corner


def _meet(side: Curve, near: Curve, t_side: float, t_near: float) -> Tuple[float, float, np.ndarray]:
    """Where two tapes cross: each one as it lies there."""
    p = side.point(t_side)
    for _ in range(4):
        t_side, p = side.meet(near.tangent(t_near), t_side)
        t_near = float(near.base.along(p))
    return t_side, t_near, p


def follow_court(lines: CourtLines, maps: TapeMaps, frame_w: int) -> Court:
    """The court's lines as the tape lies: followed along their bow, near
    corners where a sideline's tape crosses the near baseline's."""
    pts = mask_points(thin(despeckle(maps.tape)))
    lo, hi = float(lines.near.along(lines.near_left)), float(lines.near.along(lines.near_right))
    near_line = refit(lines.near, pts, (LINE_BAND_PX, 3.5), lo - 15, hi + 15) or lines.near
    px_per_m = (hi - lo) / COURT_WIDTH_M
    nodes = np.arange(lo - 0.5 * px_per_m, hi + 0.5 * px_per_m, CURVE_NODE_M * px_per_m)
    near = fit_curve(near_line, pts, nodes, int(np.argmin(np.abs(nodes - (lo + hi) / 2.0))))
    sand = SandTest(maps)
    sides, corners = [], []
    for base, corner in ((lines.left, lines.near_left), (lines.right, lines.near_right)):
        t_near, t_van = float(base.along(corner)), float(base.along(lines.vanishing))
        qs = np.arange(NEAR_TAIL_Q, Q_FAR_RANGE[1], CURVE_NODE_M / NOMINAL_Z_M)
        nodes = t_near + (t_van - t_near) * qs / (1.0 + qs)
        curve = fit_curve(base, pts, nodes, int(np.argmin(np.abs(qs - FOLLOW_FROM_Q))))
        t_near, _, corner = _meet(curve, near, t_near, float(near.base.along(corner)))
        side = Sideline(curve, t_near, t_van)
        walk_sideline(side, maps, sand)
        sides.append(side)
        corners.append(corner)
    return Court(near, sides[0], sides[1], corners[0], corners[1])


# -- net tape ---------------------------------------------------------------- #

def _sheared_rows(image: np.ndarray, slope: float, x_ref: float, cols: np.ndarray,
                  rows: np.ndarray) -> np.ndarray:
    """``image`` sampled on the lines of ``slope`` through (x_ref, row): one
    row of the result per line, one column per ``cols``."""
    h = image.shape[0]
    yy = np.round(rows[:, None] + slope * (cols[None, :] - x_ref)).astype(int)
    return image[np.clip(yy, 0, h - 1), cols[None, :]]


def _colour_spread(lab: np.ndarray, slope: float, x_ref: float, cols: np.ndarray,
                   rows: np.ndarray) -> np.ndarray:
    """How much the colour varies along each line (robust range, all three
    channels): small on ONE object that spans the columns, large on a background."""
    total = np.zeros(len(rows))
    for ch in range(3):
        lo, hi = np.percentile(_sheared_rows(lab[:, :, ch], slope, x_ref, cols, rows),
                               [20.0, 80.0], axis=1)
        total += (hi - lo) ** 2
    return np.sqrt(total)


def find_net_tape(plate: np.ndarray, near: Line, x_l: float, x_r: float,
                  rows: Tuple[float, float]) -> Tuple[Optional[Line], Dict[str, Any]]:
    """The net's top tape, between ``rows``, over the court's columns
    ``x_l`` .. ``x_r``.

    A tape is one object of one colour from sideline to sideline, a hand wide,
    in front of trees, fences, buildings and other courts: along its line the
    colour hardly varies, a few pixels above and below it varies a lot. That
    holds whether the tape is brighter or darker than what is behind it, by
    day and under floodlights. The topmost such line is the tape (the net's
    bottom band is another, a net's height below)."""
    h, w = plate.shape[:2]
    width = x_r - x_l
    px_per_m = width / COURT_WIDTH_M
    info: Dict[str, Any] = {"search_rows": [round(rows[0], 1), round(rows[1], 1)]}
    reach = int(math.ceil(NET_BESIDE_M * px_per_m))
    lo, hi = max(float(reach), rows[0]), min(h - 1.0 - reach, rows[1])
    if hi - lo < 4 or width < 50:
        return None, info
    lab = cv2.cvtColor(cv2.blur(plate, (9, 1)), cv2.COLOR_BGR2LAB).astype(np.float32)
    x_ref = (x_l + x_r) / 2.0
    cols = np.arange(max(0, int(x_l)), min(w, int(x_r) + 1), 2)
    row_values = np.arange(lo - reach, hi + reach + 1.0)
    inner = max(2, int(round(NET_TAPE_MAX_M * px_per_m / 2.0)))
    found: List[Tuple[float, float, float, float]] = []       # contrast, row, slope, spread
    for slope in near.slope + np.arange(-0.07, 0.0701, 0.0025):
        spread = _colour_spread(lab, float(slope), x_ref, cols, row_values)
        for j in range(reach, len(row_values) - reach):
            own = float(spread[j])
            if own > NET_MAX_SPREAD or own > spread[j - 1] or own > spread[j + 1]:
                continue
            above = float(spread[j - reach:j - inner + 1].max())
            below = float(spread[j + inner:j + reach + 1].max())
            contrast = min(above, below) / max(own, 1.0)
            if contrast >= NET_MIN_CONTRAST:
                found.append((contrast, float(row_values[j]), float(slope), own))
    if not found:
        return None, info
    # one line per band: the slope at which it is most uniform
    found.sort(reverse=True)
    bands: List[Tuple[float, float, float, float]] = []
    for cand in found:
        half = cand[2] * width / 2.0
        if any(abs((cand[1] - half) - (b[1] - b[2] * width / 2.0)) < NET_TAPE_MAX_M * px_per_m and
               abs((cand[1] + half) - (b[1] + b[2] * width / 2.0)) < NET_TAPE_MAX_M * px_per_m
               for b in bands):
            continue
        bands.append(cand)
    strong = [b for b in bands if b[0] >= NET_NEAR_BEST * bands[0][0]]
    contrast, row, slope, own = min(strong, key=lambda b: b[1])     # the topmost
    # Where exactly: the tape's two edges, top and bottom, run the whole way
    # even where its colour is close to what is behind it. The weakest third of
    # the court decides, so a line that leaves the tape half way scores nothing.
    grey = cv2.cvtColor(cv2.blur(plate, (15, 1)), cv2.COLOR_BGR2LAB)[:, :, 0].astype(np.float32)
    edges = np.abs(cv2.Sobel(grey, cv2.CV_32F, 0, 1, ksize=3))
    xs_all = np.arange(max(0, int(x_l)), min(w, int(x_r) + 1))
    thirds = np.array_split(np.arange(len(xs_all)), 3)
    around = np.arange(max(1.0, row - NET_REFINE_PX), min(h - 2.0, row + NET_REFINE_PX) + 1.0)
    thick = range(3, max(5, int(round(NET_TAPE_MAX_M * px_per_m))) + 1)
    best_fit: Optional[Tuple[float, float, float, int]] = None
    for sl in slope + np.arange(-NET_REFINE_SLOPE, NET_REFINE_SLOPE + 1e-9, 0.001):
        sampled = _sheared_rows(edges, float(sl), x_ref, xs_all, around)
        weakest = np.stack([sampled[:, t].mean(axis=1) for t in thirds]).min(axis=0)
        for j in range(len(around)):
            for t in thick:
                if j + t >= len(around):
                    break
                value = float(weakest[j] + weakest[j + t])
                if best_fit is None or value > best_fit[0]:
                    best_fit = (value, float(sl), float(around[j]), t)
    _, slope, top, thickness = best_fit
    a, b = 0, thickness - 1
    d = np.array([1.0, slope]) / math.hypot(1.0, slope)
    xs = np.arange(max(0, int(x_l)), min(w, int(x_r) + 1))
    line = Line(np.array([x_ref, top]), d,
                np.stack([xs, top + slope * (xs - x_ref)], axis=1).astype(float))
    below_m = sorted((b[1] - row) / px_per_m for b in bands if b[1] > row + inner)
    info.update(colour_spread=round(own, 1), contrast=round(contrast, 1),
                band_rows=int(b - a + 1), row_at_centre=round(line.y_at(w / 2.0), 1),
                slope=round(slope, 4), other_bands_m_below=[round(v, 2) for v in below_m[:3]])
    return line, info


# -- far baseline ------------------------------------------------------------ #

def far_tape_profile(maps: TapeMaps, court: Court, across: np.ndarray, sand: SandTest,
                     q_range: Tuple[float, float]) -> List[Tuple[float, float]]:
    """(q on the left sideline, share covered by tape) of every across-line
    that lies on sand. Only unbroken stretches count: trampled sand is full of
    specks that are not sand-coloured, a tape is a line."""
    evidence = maps.any_evidence
    h, w = evidence.shape
    up = np.array([0.0, 1.0])
    out = []
    for q in np.arange(q_range[0], q_range[1], Sideline.q_step() / 2.0):
        p = court.left.point_at(float(q))
        _, other = court.right.meet(line_through(p, across), float(q))
        n = int(max(2, abs(other[0] - p[0])))
        min_run = max(8, int(FAR_TAPE_RUN_M * n / COURT_WIDTH_M))
        xs, ys = np.linspace(p[0], other[0], n), np.linspace(p[1], other[1], n)
        hit = np.zeros(n, dtype=bool)
        seen = np.zeros(n, dtype=bool)
        for i in range(int(0.08 * n), int(0.92 * n)):       # not the sidelines themselves
            xi, yi = int(round(xs[i])), int(round(ys[i]))
            if not (0 <= xi < w and 1 <= yi < h - 1):
                continue
            if i % 4 == 0:
                seen[i:i + 4] = sand(np.array([xs[i], ys[i]]), up)
            hit[i] = seen[i] and bool((evidence[yi - 1:yi + 2, xi] > 1.0).any())
        if seen.sum() < 0.5 * 0.84 * n:
            continue
        covered, run = 0, 0
        for value in np.append(hit, False):
            if value:
                run += 1
            else:
                if run >= min_run:
                    covered += run
                run = 0
        out.append((float(q), covered / float(seen.sum())))
    return out


# -- camera ------------------------------------------------------------------ #

def camera_from_corners(corners: np.ndarray, frame_w: int, frame_h: int
                        ) -> Optional[Dict[str, float]]:
    """The pinhole camera (square pixels, centre in the middle) a 16 x 8 m
    court with these corners implies. A plausibility read, not an input."""
    world = np.array([[0, 0], [COURT_WIDTH_M, 0], [COURT_WIDTH_M, COURT_LENGTH_M],
                      [0, COURT_LENGTH_M]], dtype=np.float64)
    H, _ = cv2.findHomography(world, np.asarray(corners, dtype=np.float64))
    if H is None:
        return None
    G = np.array([[1, 0, -frame_w / 2.0], [0, 1, -frame_h / 2.0], [0, 0, 1.0]]) @ H
    h1, h2, h3 = G[:, 0], G[:, 1], G[:, 2]
    den = h2[2] ** 2 - h1[2] ** 2
    if abs(den) < 1e-18:
        return None
    f2 = ((h1[0] ** 2 + h1[1] ** 2) - (h2[0] ** 2 + h2[1] ** 2)) / den
    if not f2 > 0:
        return None
    f = math.sqrt(f2)
    Ki = np.diag([1.0 / f, 1.0 / f, 1.0])
    a, b, c = Ki @ h1, Ki @ h2, Ki @ h3
    lam = (np.linalg.norm(a) + np.linalg.norm(b)) / 2.0
    r1, r2, t = a / lam, b / lam, c / lam
    if t[2] < 0:
        r1, r2, t = -r1, -r2, -t
    R = np.stack([r1, r2, np.cross(r1, r2)], axis=1)
    U, _, Vt = np.linalg.svd(R)
    R = U @ Vt
    centre = -R.T @ t
    return {"focal_px": float(f), "height_m": float(abs(centre[2])),
            "behind_near_baseline_m": float(centre[1] - COURT_LENGTH_M),
            "across_m": float(centre[0])}


def focal_priors(calibrations_dir: Path, frame_w: int, frame_h: int,
                 exclude_stem: Optional[str] = None) -> List[float]:
    """Focal lengths (px) the calibrations on disk agree on: one per lens
    setting that at least ``FOCAL_MIN_VIDEOS`` different views share."""
    focals, seen = [], set()
    for path in sorted(Path(calibrations_dir).glob("*.json")):
        if path.stem == exclude_stem:
            continue
        try:
            data = json.loads(path.read_text())
            corners = np.asarray(data["court_corners"], dtype=float).reshape(4, 2)
        except (OSError, ValueError, KeyError):
            continue
        if tuple(data.get("frame_dimensions") or (1080, 1920)) != (frame_h, frame_w):
            continue
        key = corners.tobytes()
        if key in seen:                              # clips cut from one recording
            continue
        seen.add(key)
        camera = camera_from_corners(corners, frame_w, frame_h)
        if camera is not None and 0.45 * frame_w <= camera["focal_px"] <= 1.8 * frame_w:
            focals.append(camera["focal_px"])
    focals.sort()
    out, group = [], []
    for f in focals + [math.inf]:
        if group and f > group[0] * (1.0 + FOCAL_CLUSTER):
            if len(group) >= FOCAL_MIN_VIDEOS:
                out.append(float(np.median(group)))
            group = []
        group.append(f)
    return out


def q_for_focal(court: "Court", across: np.ndarray, focal: float, frame_w: int,
                frame_h: int) -> Optional[float]:
    """Where on the left sideline the far baseline must leave for the court's
    corners to imply ``focal``."""
    best: Optional[Tuple[float, float]] = None
    for q in np.arange(Q_FAR_RANGE[0], Q_FAR_RANGE[1], 0.01):
        camera = camera_from_corners(_far_corners(court, across, float(q)), frame_w, frame_h)
        if camera is None:
            continue
        miss = abs(camera["focal_px"] - focal) / focal
        if best is None or miss < best[0]:
            best = (miss, float(q))
    return best[1] if best is not None and best[0] <= 0.01 else None


# -- the whole read ---------------------------------------------------------- #

@dataclass
class AutoCalibration:
    points: Optional[Dict[str, Any]]
    accepted: bool
    checks: Dict[str, Any]
    reasons: List[str]
    debug: Dict[str, Any] = field(default_factory=dict)


def _homography(corners: np.ndarray) -> np.ndarray:
    world = np.array([[0, 0], [COURT_WIDTH_M, 0], [COURT_WIDTH_M, COURT_LENGTH_M],
                      [0, COURT_LENGTH_M]], dtype=np.float32)
    return cv2.getPerspectiveTransform(world, corners.astype(np.float32))


def _project(H: np.ndarray, x: float, y: float) -> np.ndarray:
    p = H @ np.array([x, y, 1.0])
    return p[:2] / p[2]


def _far_corners(court: Court, across: np.ndarray, q_left: float) -> np.ndarray:
    """FL, FR, NR, NL for the far baseline that leaves the left sideline at ``q_left``."""
    fl = court.left.point_at(q_left)
    _, fr = court.right.meet(line_through(fl, across), q_left)
    return np.array([fl, fr, court.near_right, court.near_left], dtype=float)


def _points(corners: np.ndarray, net: Optional[Line], frame_h: int, frame_w: int
            ) -> Dict[str, Any]:
    H = _homography(corners)
    ground = np.array([_project(H, 0.0, COURT_LENGTH_M / 2),
                       _project(H, COURT_WIDTH_M, COURT_LENGTH_M / 2)])
    if net is not None:
        top = np.array([[g[0], net.y_at(g[0])] for g in ground])
    else:
        px_per_m = float(np.linalg.norm(ground[1] - ground[0])) / COURT_WIDTH_M
        top = ground - np.array([0.0, 2.43 * px_per_m])
    return {
        "court_corners": [[int(round(x)), int(round(y))] for x, y in corners],
        "midcourt_points": [[int(round(x)), int(round(y))] for x, y in ground],
        "net_top_points": [[int(round(x)), int(round(y))] for x, y in top],
        "frame_dimensions": [frame_h, frame_w],
    }


def _net_height(points: Dict[str, Any]) -> Optional[float]:
    """The net-top height the post-run layer will read from these points."""
    from src.postrun.geometry import CourtGeometry
    try:
        return float(CourtGeometry(points["court_corners"], points["net_top_points"],
                                   points["midcourt_points"]).net_top_height_m())
    except ValueError:
        return None


def detect(plate: np.ndarray, focals: Sequence[float] = ()) -> AutoCalibration:
    """The 8 calibration points of ``plate``. ``focals``: focal lengths (px)
    this camera is known to have (``focal_priors``)."""
    h, w = plate.shape[:2]
    reasons: List[str] = []
    checks: Dict[str, Any] = {}
    debug: Dict[str, Any] = {}

    maps = chroma_ridges(plate)
    lines = strong_lines(maps.ridge)
    debug.update(maps=maps, lines=lines)
    found = find_court(lines, w, h)
    if found is None:
        return AutoCalibration(None, False, checks,
                               ["no court: near baseline + two sidelines not found"], debug)
    # Second pass on the tape's own colour, read off the court just found.
    tape_colour(maps, (found.near, found.left, found.right))
    if maps.tape_ab is None:
        return AutoCalibration(None, False, checks, ["the tape has no colour of its own"], debug)
    lines = strong_lines(maps.tape)
    found = find_court(lines, w, h) or found
    debug["lines"] = lines
    court = follow_court(found, maps, w)
    sand = SandTest(maps)
    debug["court"] = court
    checks["sand_colour_lab_ab"] = [round(float(v), 1) for v in maps.sand_ab]
    checks["tape_colour_lab_ab"] = [round(float(v), 1) for v in maps.tape_ab]
    checks["tape_read_by_darkness_too"] = bool(maps.dark_tape)
    near_line = court.near.base
    f_lo, f_hi = near_line.in_frame(w)
    checks["near_baseline"] = {
        "residual_px": round(court.near.residual, 2),
        "bow_px": round(float(np.abs(court.near.stray).max()), 1),
        "coverage": round(near_line.coverage(max(float(near_line.along(court.near_left)), f_lo),
                                             min(float(near_line.along(court.near_right)), f_hi)), 2)}
    # the near baseline as one straight line through its two corners
    near_chord = Line(court.near_left, (court.near_right - court.near_left)
                      / np.linalg.norm(court.near_right - court.near_left))

    # Where each sideline's tape stops.
    sides = {"left": court.left, "right": court.right}
    ends = {name: [q for q in side.ends() if Q_FAR_RANGE[0] <= q <= Q_FAR_RANGE[1]]
            for name, side in sides.items()}
    debug["ends"] = ends
    for name, side in sides.items():
        checks[f"{name}_sideline"] = {
            "residual_px": round(side.curve.residual, 2),
            "bow_px": round(float(np.abs(side.curve.stray).max()), 1),
            "tape_ends": [[round(float(v), 1) for v in side.point_at(q)] for q in ends[name]]}
    if not ends["left"] and not ends["right"]:
        return AutoCalibration(None, False, checks, ["no sideline's tape end was found"], debug)

    # The net, searched above every far baseline the tape ends allow (level
    # with the near baseline for now).
    level = np.array([near_chord.direction[0], near_chord.direction[1], 0.0])
    rough = list(ends["left"]) + [court.left.meet(line_through(court.right.point_at(q), level), q)[0]
                                  for q in ends["right"]]
    windows, columns = [], []
    for q in rough:
        H = _homography(_far_corners(court, level, q))
        ground = np.array([_project(H, 0.0, COURT_LENGTH_M / 2),
                           _project(H, COURT_WIDTH_M, COURT_LENGTH_M / 2)])
        px_per_m = float(np.linalg.norm(ground[1] - ground[0])) / COURT_WIDTH_M
        row = float(ground[:, 1].mean())
        windows.append((row - NET_HEIGHT_RANGE_M[1] * px_per_m, row - NET_HEIGHT_RANGE_M[0] * px_per_m))
        columns.append((float(ground[0, 0]), float(ground[1, 0])))
    net, net_info = find_net_tape(
        plate, near_chord, float(np.median([c[0] for c in columns])),
        float(np.median([c[1] for c in columns])),
        (min(wd[0] for wd in windows), max(wd[1] for wd in windows)))
    debug["net"] = net
    checks["net_tape"] = net_info
    if net is None:
        across = level
        reasons.append("net tape not found")
    else:
        # Lines across the court meet where the near baseline meets the net tape.
        across = np.cross(near_chord.hom, net.hom)
    debug["across"] = across

    # Every read of the far baseline, as q on the left sideline.
    reads: List[Tuple[str, float, float]] = [("left_end", q, 1.0) for q in ends["left"]]
    reads += [("right_end", court.left.meet(line_through(court.right.point_at(q), across), q)[0], 1.0)
              for q in ends["right"]]
    q_all = [q for _, q, _ in reads]
    profile = far_tape_profile(maps, court, across, sand,
                               (max(Q_FAR_RANGE[0], min(q_all) - 0.4),
                                min(Q_FAR_RANGE[1], max(q_all) + 0.4)))
    debug["far_profile"] = profile
    if profile:
        covers = np.array([c for _, c in profile])
        k = int(np.argmax(covers))
        base = float(np.median(covers))
        checks["far_tape"] = {"coverage": round(float(covers[k]), 2), "typical": round(base, 2)}
        if covers[k] >= FAR_TAPE_MIN_COVERAGE and covers[k] - base >= FAR_TAPE_MIN_EXCESS:
            a = b = k                                # the middle of the band that answers
            while a > 0 and covers[a - 1] >= 0.9 * covers[k]:
                a -= 1
            while b < len(covers) - 1 and covers[b + 1] >= 0.9 * covers[k]:
                b += 1
            reads.append(("far_tape", (profile[a][0] + profile[b][0]) / 2.0, 1.5))
    seen_reads = list(reads)
    for focal in focals:
        q_cam = q_for_focal(court, across, focal, w, h)
        if q_cam is not None:
            reads.append(("camera", q_cam, 1.0))
    agree = FAR_AGREE_M / NOMINAL_Z_M
    agree_camera = CAMERA_AGREE_M / NOMINAL_Z_M
    best: Optional[Tuple[Tuple, float, List[str], Optional[float]]] = None
    def overrun(q_left: float) -> float:
        """Tape seen running on beyond a far baseline at ``q_left`` (q, the worse sideline)."""
        corners = _far_corners(court, across, q_left)
        return max(court.left.runs_beyond(q_left, ends["left"]),
                   court.right.runs_beyond(court.right.q_of(corners[1]), ends["right"]))

    for _, q0, _ in seen_reads:                      # the picture decides, the camera confirms
        group = [r for r in reads if abs(r[1] - q0) <= (agree_camera if r[0] == "camera" else agree)]
        sources = sorted({r[0] for r in group})
        tape = [r[1] for r in group if r[0] == "far_tape"]
        # A tape's end is seen short of the corner when its last stretch is
        # buried, hardly ever beyond it: of two ends that agree, the farther.
        q_far = tape[0] if tape else float(max(r[1] for r in group if r[0] != "camera"))
        net_h = _net_height(_points(_far_corners(court, across, q_far), net, h, w))
        plausible = net is None or (net_h is not None and NET_HEIGHT_OK_M[0] <= net_h <= NET_HEIGHT_OK_M[1])
        # ... and a baseline some tape runs on beyond is nobody's far baseline
        clear = overrun(q_far) <= agree
        key = (clear, plausible, len(sources),
               sum(max(r[2] for r in group if r[0] == s) for s in sources), q_far)
        if best is None or key > best[0]:
            best = (key, q_far, sources, net_h)
    (clear, *_), q_far, sources, net_h = best
    if not clear:
        reasons.append("a sideline's tape runs on beyond the far baseline "
                       f"({overrun(q_far) * NOMINAL_Z_M:.1f} m)")
    row = lambda q: round(float(court.left.point_at(q)[1]), 1)       # noqa: E731
    checks["far_baseline"] = {
        "reads": [{"from": name, "row_on_left_sideline": row(q)}
                  for name, q, _ in sorted(reads, key=lambda r: r[1])],
        "agreeing": sources, "row_on_left_sideline": row(q_far)}
    checks["far_baseline"]["known_focals_px"] = [round(float(f)) for f in focals]
    if len(sources) < 2:
        reasons.append(f"far baseline seen by one read only ({sources[0]})")

    corners = _far_corners(court, across, q_far)
    points = _points(corners, net, h, w)
    checks["net_top_height_m"] = None if net_h is None else round(net_h, 2)
    if net is not None and not (net_h is not None and NET_HEIGHT_OK_M[0] <= net_h <= NET_HEIGHT_OK_M[1]):
        reasons.append(f"net reads {net_h if net_h is None else round(net_h, 2)} m high")
    for name, side in sides.items():
        q_corner = q_far if name == "left" else side.q_of(corners[1])
        cover = side.coverage(q_corner)
        checks[f"{name}_sideline"]["coverage"] = round(cover, 2)
        if cover < SIDELINE_ACCEPT_COVERAGE:
            reasons.append(f"{name} sideline: tape seen on {cover:.0%} of it only")
    camera = camera_from_corners(corners, w, h)
    checks["camera"] = None if camera is None else {k: round(v, 2) for k, v in camera.items()}
    if camera is None or not (0.8 <= camera["height_m"] <= 4.5
                              and 3.0 <= camera["behind_near_baseline_m"] <= 18.0
                              and 0.45 * w <= camera["focal_px"] <= 1.8 * w):
        reasons.append("the corners imply no plausible camera")
    return AutoCalibration(points, not reasons, checks, reasons, debug)


# -- pictures ---------------------------------------------------------------- #

def draw(plate: np.ndarray, result: AutoCalibration,
         manual: Optional[Dict[str, Any]] = None) -> np.ndarray:
    out = plate.copy()
    dbg = result.debug
    maps: Optional[TapeMaps] = dbg.get("maps")
    if maps is not None:
        out[maps.tape > 0] = (0, 255, 255)
    net = dbg.get("net")
    if net is not None:
        lo, hi = net.extent
        cv2.line(out, tuple(int(v) for v in net.at(lo)), tuple(int(v) for v in net.at(hi)),
                 (0, 128, 255), 2)
    court: Optional[Court] = dbg.get("court")
    if court is not None:
        for name, side in (("left", court.left), ("right", court.right)):
            pts = np.array([side.point_at(q) for q in np.arange(0.0, Q_FAR_RANGE[1], 0.05)], np.int32)
            cv2.polylines(out, [pts], False, (255, 0, 255), 1)
            for q in (dbg.get("ends") or {}).get(name, []):
                cv2.circle(out, tuple(int(v) for v in side.point_at(q)), 9, (255, 255, 0), 2)
    if result.points:
        c = np.array(result.points["court_corners"], dtype=np.int32)
        cv2.polylines(out, [c], True, (0, 255, 0), 2)
        for p in result.points["midcourt_points"] + result.points["net_top_points"]:
            cv2.circle(out, tuple(p), 6, (0, 255, 0), 2)
    if manual:
        c = np.array(manual["court_corners"], dtype=np.int32)
        cv2.polylines(out, [c], True, (0, 0, 255), 1)
        for p in manual["midcourt_points"] + (manual.get("net_top_points") or []):
            cv2.drawMarker(out, tuple(p), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 12, 1)
    return out


POINT_NAMES = ("far left", "far right", "near right", "near left",
               "under the net, left", "under the net, right", "net tape, left", "net tape, right")


def _eight(points: Dict[str, Any]) -> np.ndarray:
    return np.array(points["court_corners"] + points["midcourt_points"]
                    + (points.get("net_top_points") or [[0, 0], [0, 0]]), dtype=float)


def contact_sheet(plate: np.ndarray, points: Dict[str, Any],
                  manual: Optional[Dict[str, Any]] = None, half: int = 70, zoom: int = 4
                  ) -> np.ndarray:
    """The 8 points, each on a zoomed piece of the plate: automatic = green
    ring, manual = red cross. What an owner looks at to say which is right."""
    h, w = plate.shape[:2]
    auto = _eight(points)
    hand = _eight(manual) if manual else None
    pad = 3 * half                     # a corner may lie outside the frame
    padded = cv2.copyMakeBorder(plate, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(40, 40, 40))
    tiles = []
    for i, name in enumerate(POINT_NAMES):
        cx = int(round(min(max(auto[i, 0], -2 * half), w + 2 * half)))
        cy = int(round(min(max(auto[i, 1], -2 * half), h + 2 * half)))
        x0, y0 = cx + pad - half, cy + pad - half
        tile = padded[y0:y0 + 2 * half, x0:x0 + 2 * half].copy()
        tile = cv2.resize(tile, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_CUBIC)

        def place(pt: np.ndarray) -> Tuple[int, int]:
            return (int(round((pt[0] - cx + half) * zoom)), int(round((pt[1] - cy + half) * zoom)))
        cv2.circle(tile, place(auto[i]), 14, (0, 255, 0), 2)
        cv2.circle(tile, place(auto[i]), 1, (0, 255, 0), -1)
        label = name
        if hand is not None:
            cv2.drawMarker(tile, place(hand[i]), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 22, 2)
            d = auto[i] - hand[i]
            label += f"   auto - manual: {d[0]:+.0f}, {d[1]:+.0f} px"
        cv2.rectangle(tile, (0, 0), (tile.shape[1], 26), (0, 0, 0), -1)
        cv2.putText(tile, label, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(tile)
    rows = [np.hstack(tiles[k:k + 4]) for k in (0, 4)]
    return np.vstack(rows)


def compare(points: Dict[str, Any], manual: Dict[str, Any]) -> Dict[str, Any]:
    """Auto minus manual, in the quantities the post-run layer reads."""
    a = np.array(points["court_corners"], dtype=float)
    m = np.array(manual["court_corners"], dtype=float)
    out = {
        "corner_delta_px": {name: [round(float(a[i, 0] - m[i, 0]), 1), round(float(a[i, 1] - m[i, 1]), 1)]
                            for i, name in enumerate(("far_left", "far_right", "near_right", "near_left"))},
        "far_width_frac": round(float((a[1, 0] - a[0, 0]) / (m[1, 0] - m[0, 0]) - 1.0), 4),
        "near_width_frac": round(float((a[2, 0] - a[3, 0]) / (m[2, 0] - m[3, 0]) - 1.0), 4),
        "far_row_px": round(float(a[:2, 1].mean() - m[:2, 1].mean()), 1),
        "near_row_px": round(float(a[2:, 1].mean() - m[2:, 1].mean()), 1),
    }
    for key in ("midcourt_points", "net_top_points"):
        if manual.get(key):
            d = np.array(points[key], dtype=float) - np.array(manual[key], dtype=float)
            out[f"{key}_delta_px"] = [[round(float(v), 1) for v in row] for row in d]
    return out


def jsonable(checks: Dict[str, Any]) -> Dict[str, Any]:
    return json.loads(json.dumps(checks, default=float))


def calibrate_video(video: Path, calibrations_dir: Optional[Path] = None
                    ) -> Tuple[str, np.ndarray, AutoCalibration]:
    """(source stem, plate, result) for ``video``, read on the frames the
    pipeline will process (``ensure_1080``). ``calibrations_dir``: where
    earlier calibrations live (their focal length; the video's own file is
    never read)."""
    video = ensure_1080(Path(video))
    stem = resolve_source_stem(video)
    plate = median_plate(read_frames(video))
    focals = [] if calibrations_dir is None else focal_priors(
        calibrations_dir, plate.shape[1], plate.shape[0], exclude_stem=stem)
    return stem, plate, detect(plate, focals)


def calibration_document(result: AutoCalibration, accepted_by: str = "checks") -> Dict[str, Any]:
    """The calibration JSON of ``result``: the four keys every reader uses plus
    where it came from. ``accepted_by``: ``checks`` (its own reads agreed) or
    ``owner`` (a person looked at the proposal and took it)."""
    if result.points is None:
        raise ValueError("no court was found: nothing to write")
    doc = dict(result.points)
    doc["source"] = "auto"
    doc["auto"] = {"version": VERSION, "accepted": bool(result.accepted),
                   "accepted_by": accepted_by, "reasons": list(result.reasons),
                   "checks": jsonable(result.checks)}
    return doc
