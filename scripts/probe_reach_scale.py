"""Reach-gate px -> side-scale diagnosis (diagnose-only, no src change).

The reach gate in ``ActionClassifier`` scores a contact as ``distance`` px
(ball -> player bbox) against the side-blind constant
``ActionClassifier.CONTACT_REACH = 140.0`` (``src/recognition/action_classifier.py:53``;
gate at :416-426, player choice at :1018-1110). All 7 recorded rejections on
the losing entreno drills target team B, the far half, and never A
(``logs/entreno_buckets_report.md:236-242``).

This module MEASURES whether that asymmetry is explained by pixel scale. It
designs NO mechanism: a ground-metre reach rule is owner-gated (the px->m move
was GT-refuted for ``near_net``, F1 0.929 -> 0.857). The result only quantifies
the asymmetry for that decision.

Reads committed artifacts only: ``output/sr1/entreno_{1,2,7}_diag.jsonl``,
``calibrations/video_entreno_{1,2,7}.json`` and the read-only GT frame lists in
``ground_truth/video_entreno_{1,2,7}_annotations.json``. No decode, no seek
(``cv2.CAP_PROP_POS_FRAMES``), no pipeline re-run.

WHICH CALIBRATION SCALE IS USABLE, AND WHICH IS NOT
---------------------------------------------------
The conversion is built on the IMPORTED ``CourtCalibration.image_to_world``, but
on ONE of its two components. A ground homography has an ACROSS and an ALONG
scale at a point, and they differ by ~6x here:

* ACROSS = ``world(world_x + 1) - world_x`` at the sample point.
  **Validated**: multiplied into the detector's median player bbox width it
  gives 0.58 m (far bands) and 0.67 m (near bands) -- a plausible shoulder span,
  and the ratio is stable across the clip. This is the component used.
* ALONG = the depth scale. **Rejected**: it multiplies the same median width to
  5.2-6.3 m, which is not a body. Its depth behaviour is also inconsistent with
  the court itself -- the calibration puts the depth VANISHING ROW at y = 246,
  while its own 8-point fit needs y = 271 to satisfy the three court rows
  (492 / 602 / 930 px for world depth 0 / 8 / 16 m), and the ball-size and
  player-size laws both put it at y = 250-320.

``CourtCalibration.world_scale_at`` is the MEAN of the two components, so it
inherits the broken one: it reports 4.8 m for a near-side body and 5.9-6.2 m for
a far-side one, has poles at y = 192-193 and y = 302-303 (577 m/px at y = 250),
and yields a far/near metres-per-pixel ratio of 0.49x -- the WRONG SIGN, since
under a perspective projection a far player's image is smaller, so the far side
must have FEWER pixels per metre. Every metre reading here therefore comes from
the ACROSS component, and ``world_scale_at`` is reported only as the refuted
alternative.

CORNER ORDER: checked and CORRECT as shipped. ``CORNER_WORLD`` reproduces
``CourtCalibration.compute_ground_homography`` to 0.0 elementwise, the
sidelines stay at world x = 0 / 8 to 3 decimals along their whole length, and the
``midcourt_points`` reproject to world y = 7.69 / 7.82 m against a nominal 8.0.
No refit is applied.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from src.detection.court_calibration import CourtCalibration
from src.recognition.action_classifier import ActionClassifier

ROOT = Path(__file__).resolve().parents[1]
CLIPS = (1, 2, 7)

# The four calibration corners with the world point each one is. Far baseline
# is y = 486-498 in these clips and near baseline y = 910-950, so this IS depth
# order; asserted equal to the shipped assignment in ``corner_order_is_valid``.
CORNER_WORLD = ((0.0, 0.0), (8.0, 0.0), (8.0, 16.0), (0.0, 16.0))

SCALE_BAND = 80.0          # foot_y bin width for the scale validation
SCALE_MIN_PER_BAND = 15
SHADOW = 3.0               # px, scale probe separation along the tested axis


# ----------------------------------------------------------------------
# calibration: imported loader, one validated component


def calibration(clip: int) -> CourtCalibration:
    """The IMPORTED loader on ``calibrations/video_entreno_{clip}.json``."""
    return CourtCalibration(str(ROOT / f"calibrations/video_entreno_{clip}.json"))


def corner_order_is_valid(cal: CourtCalibration) -> bool:
    """Does the depth-order ``CORNER_WORLD`` reproduce the shipped homography?

    ``CourtCalibration.compute_ground_homography`` maps the corner array to
    (0,0), (W,0), (W,L), (0,L). If that array is already in depth order, the
    refit is a no-op and the shipped mapping stands. Verified: the two matrices
    are elementwise identical.
    """
    corners = np.array([tuple(p) for p in cal.court_corners[:4]], dtype=np.float32)
    if corners.shape != (4, 2):
        return False
    world = np.array(
        [(x * CourtCalibration.BEACH_COURT_WIDTH_M / 8.0,
          y * CourtCalibration.BEACH_COURT_LENGTH_M / 16.0)
         for x, y in CORNER_WORLD], dtype=np.float32)
    image_pts = corners.reshape(-1, 1, 2)
    world_pts = world.reshape(-1, 1, 2)
    h, _ = _find_homography(image_pts, world_pts)
    return bool(h is not None and
                np.abs(h - cal.compute_ground_homography()).max() < 1e-9)


def _find_homography(src: np.ndarray, dst: np.ndarray):
    import cv2
    return cv2.findHomography(src, dst)


def across_m_per_px(cal: CourtCalibration, point: Sequence[float]
                    ) -> Optional[float]:
    """Ground metres per image pixel ACROSS the court, at an image point.

    Finite difference of the IMPORTED ``image_to_world`` along x, so it is the
    homography's own across component with no Jacobian and no re-implementation.
    The sample point is a player's foot (``CourtCalibration.foot_point``), the
    same ground convention the tracker uses for ``get_team``.
    """
    base = cal.image_to_world((int(point[0]), int(point[1])))
    probe = cal.image_to_world((int(point[0]) + SHADOW, int(point[1])))
    if base is None or probe is None:
        return None
    span = abs(probe[0] - base[0]) / SHADOW
    return float(span) if span > 0 else None


def along_m_per_px(cal: CourtCalibration, point: Sequence[float]
                   ) -> Optional[float]:
    """Ground metres per image pixel DOWN the image (the depth component).

    Reported for the validation record only. It is the component that fails
    the player-width check, so no metre reading uses it.
    """
    base = cal.image_to_world((int(point[0]), int(point[1])))
    probe = cal.image_to_world((int(point[0]), int(point[1]) + SHADOW))
    if base is None or probe is None:
        return None
    span = abs(probe[1] - base[1]) / SHADOW
    return float(span) if span > 0 else None


def px_to_metres(cal: CourtCalibration, px: float, foot: Sequence[float]
                 ) -> Optional[float]:
    """THE conversion: an image-plane px distance at a foot position, in metres.

    ``metres = px * across_m_per_px(foot)``. For a displacement between two
    points at the same depth (a lateral ball-to-player gap, which is 5 of the 7
    rejections) this is exact. For a VERTICAL image displacement -- the ball
    above or below the player -- it is the ground-plane scale standing in for a
    vertical 3-D one; the camera's focal length is not recoverable from these
    6 calibration points (the 6-point DLT is degenerate: the net height is the
    only vertical information and every net height 1.8-3.4 m fits to 0.64 px),
    so those rows are flagged ``vertical`` in the report.
    """
    m_per_px = across_m_per_px(cal, foot)
    return float(px) * m_per_px if m_per_px else None


def scale_validation(clip: int) -> Dict[str, object]:
    """Check the ACROSS component against the detector's own player widths.

    ``median bbox width px * m_per_px`` must land near a real shoulder span at
    EVERY depth, otherwise the component is not a metric scale.
    """
    cal = calibration(clip)
    acc: Dict[int, List[Tuple[float, float, float]]] = {}
    for _frame, rec in sorted(records(clip).items()):
        for p in (rec.get("players") or []):
            bb = p.get("bbox")
            if not bb or p.get("predicted"):
                continue
            width = float(bb[2]) - float(bb[0])
            if width <= 0:
                continue
            foot = cal.foot_point(_as_bbox(bb))
            acc.setdefault(int(foot[1] // SCALE_BAND) * SCALE_BAND,
                           []).append((foot[1], width, float(bb[3] - bb[1])))
    bands = []
    for key in sorted(acc):
        grp = acc[key]
        if len(grp) < SCALE_MIN_PER_BAND:
            continue
        foot_y = float(median([g[0] for g in grp]))
        width = float(median([g[1] for g in grp]))
        height = float(median([g[2] for g in grp]))
        foot = cal.foot_point([960 - SHADOW, 960 + SHADOW,
                               960 + SHADOW, int(round(foot_y))])
        bands.append({
            "foot_y": round(foot_y, 1), "n": len(grp),
            "width_px": round(width, 1), "height_px": round(height, 1),
            "across_m": round(width * across_m_per_px(cal, foot), 3),
            "along_m": round(width * along_m_per_px(cal, foot), 3),
            "mean_m": round(width * float(cal.world_scale_at(foot)), 3),
        })
    return {"clip": clip, "bands": bands}


def rejected_components(clip: int = 1) -> List[Dict[str, float]]:
    """Where the shipped scale's poles sit, for the validation record."""
    cal = calibration(clip)
    rows = [cal.world_scale_at((960, y)) for y in range(0, 1080)]
    return {"pole_rows": [y for y, v in enumerate(rows)
                          if v is not None and v > 1.0],
            "at_250": rows[250], "at_300": rows[300],
            "far_over_near_mean": _mean_ratio(rows)}


def _mean_ratio(rows: Sequence[Optional[float]]) -> Optional[float]:
    """world_scale_at far/near ratio; <1 is the wrong-sign tell."""
    far = median([v for v in rows[450:600] if v is not None])
    near = median([v for v in rows[750:950] if v is not None])
    return round(far / near, 3) if far and near else None


# ----------------------------------------------------------------------
# rows


@dataclass
class ReachRow:
    clip: int
    frame: int
    stage: str                     # "rejected" | "accepted"
    reason: Optional[str]
    kind: Optional[str]
    px: float
    reach_px: float
    track_id: Optional[int]
    player_id: Optional[int]
    team_flag: Optional[str]
    ball_point: Optional[List[float]]
    bbox: Optional[List[float]]
    action: Optional[str] = None
    side_cal: Optional[str] = None    # calibration's read of the bbox feet
    foot_y: Optional[int] = None
    dx: Optional[float] = None
    dy: Optional[float] = None
    metres: Optional[float] = None
    mean_metres: Optional[float] = None   # refuted world_scale_at reading
    recomputed_px: Optional[float] = None

    @property
    def side(self) -> str:
        """Side from the toucher's own feet; never from the flag under test."""
        if self.side_cal in ("A", "B"):
            return "far" if self.side_cal == "B" else "near"
        return "far" if self.team_flag == "B" else "near"

    @property
    def vertical_fraction(self) -> float:
        """Fraction of the px distance that is image-vertical."""
        if not self.px:
            return 0.0
        return abs(float(self.dy or 0.0)) / float(self.px)

    @property
    def geometry(self) -> str:
        return "vertical" if self.vertical_fraction >= 0.9 else "lateral"


_RECORDS: Dict[int, Dict[int, Dict]] = {}


def records(clip: int) -> Dict[int, Dict]:
    """``{frame: diag record}`` for one clip's committed dump."""
    if clip not in _RECORDS:
        path = ROOT / f"output/sr1/entreno_{clip}_diag.jsonl"
        out: Dict[int, Dict] = {}
        for line in path.read_text(encoding="utf-8").strip().split("\n")[1:]:
            if line.strip():
                rec = json.loads(line)
                out[int(rec["frame"])] = rec
        _RECORDS[clip] = out
    return _RECORDS[clip]


def _player_at(rec: Dict, track_id) -> Dict:
    for p in (rec.get("players") or []):
        if p.get("track_id") == track_id:
            return p
    return {}


def _fill(row: ReachRow) -> ReachRow:
    if not row.bbox:
        return row
    cal = calibration(row.clip)
    bbox = _as_bbox(row.bbox)
    row.side_cal = cal.get_team_for_bbox(bbox)
    foot = cal.foot_point(bbox)
    row.foot_y = int(foot[1])
    if row.ball_point:
        bx, by = float(row.ball_point[0]), float(row.ball_point[1])
        cx = min(max(bx, bbox[0]), bbox[2])
        cy = min(max(by, bbox[1]), bbox[3])
        row.dx = round(bx - cx, 1)
        row.dy = round(by - cy, 1)
        row.metres = px_to_metres(cal, row.px, foot)
        scale = cal.world_scale_at(foot)
        row.mean_metres = float(row.px) * scale if scale else None
    return row


def reach_rows(clips: Sequence[int] = CLIPS) -> List[ReachRow]:
    """Every ``reason="reach"`` rejection in the dumps (7: e1 2, e2 4, e7 1)."""
    out: List[ReachRow] = []
    for clip in clips:
        recs = records(clip)
        for _frame, rec in sorted(recs.items()):
            for c in (rec.get("candidates") or []):
                if c.get("stage") != "rejected" or c.get("reason") != "reach":
                    continue
                cf = int(c["frame"])
                pl = _player_at(recs.get(cf, rec), c.get("track_id"))
                ball = (rec.get("ball_track") or {}).get("center")
                bbox = list(pl["bbox"]) if pl.get("bbox") else None
                row = ReachRow(
                    clip=clip, frame=cf, stage="rejected", reason="reach",
                    kind=c.get("kind"), px=float(c["distance"]),
                    reach_px=float(c.get("reach")
                                   or ActionClassifier.CONTACT_REACH),
                    track_id=c.get("track_id"), player_id=c.get("player_id"),
                    team_flag=c.get("target_team"), ball_point=ball, bbox=bbox,
                )
                if bbox and ball:
                    row.recomputed_px = point_to_bbox_distance(ball, bbox)
                out.append(_fill(row))
    return out


def accepted_rows(clips: Sequence[int] = CLIPS) -> List[ReachRow]:
    """Every accepted contact, scored as the gate would have scored it.

    The ``accepted`` row itself carries no ``contact_point``; the contact
    geometry lives on its sibling ``candidate_passed_gates`` row (same frame,
    same track_id, same record). The player's bbox is read at the CONTACT
    frame, not at the ``seen_at`` frame the row was written at.
    """
    out: List[ReachRow] = []
    for clip in clips:
        recs = records(clip)
        for _frame, rec in sorted(recs.items()):
            cands = rec.get("candidates") or []
            passed = [c for c in cands
                      if c.get("stage") == "candidate_passed_gates"]
            for c in (c for c in cands if c.get("stage") == "accepted"):
                geo = next((p for p in passed
                            if p.get("frame") == c.get("frame")
                            and p.get("track_id") == c.get("track_id")), None)
                if geo is None or not geo.get("contact_point"):
                    continue
                cf = int(geo["frame"])
                pl = _player_at(recs.get(cf, rec), geo.get("track_id"))
                if not pl.get("bbox"):
                    continue
                out.append(_fill(ReachRow(
                    clip=clip, frame=cf, stage="accepted", reason=None,
                    kind=c.get("kind") or geo.get("kind"),
                    px=point_to_bbox_distance(geo["contact_point"], pl["bbox"]),
                    reach_px=ActionClassifier.CONTACT_REACH,
                    track_id=geo.get("track_id"),
                    player_id=geo.get("player_id"),
                    team_flag=geo.get("team") or geo.get("ball_side"),
                    ball_point=list(geo["contact_point"]),
                    bbox=list(pl["bbox"]), action=c.get("action"),
                )))
    return out


def all_rows(clips: Sequence[int] = CLIPS) -> List[ReachRow]:
    return reach_rows(clips) + accepted_rows(clips)


def point_to_bbox_distance(point: Sequence[float],
                           bbox: Optional[Sequence[float]] = None) -> float:
    """Ball point -> player bbox distance, 0 inside.

    Mirrors ``ActionClassifier._point_to_bbox_distance`` (0 inside, else to the
    nearest edge), so an ACCEPTED contact is scored the way the gate scores a
    rejected one. Rejection rows keep the gate's own recorded number;
    ``ReachRow.recomputed_px`` is the audit.
    """
    x, y = float(point[0]), float(point[1])
    if not bbox:
        return float("inf")
    x0, y0, x1, y1 = (float(v) for v in bbox)
    return float(np.hypot(max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1)))


def _as_bbox(seq: Sequence[float]) -> List[int]:
    return [int(round(float(v))) for v in seq]


# ----------------------------------------------------------------------
# stats


def cliffs_delta(a: Sequence[Optional[float]],
                 b: Sequence[Optional[float]]) -> float:
    """Cliff's delta of ``a`` over ``b``: P(a>b) - P(a<b) over all pairs.

    -1 / +1 are total separation; ties score 0.0. An empty arm returns 0.0 so a
    missing population can never fake a verdict.
    """
    xs = [float(x) for x in a if x is not None]
    ys = [float(y) for y in b if y is not None]
    if not xs or not ys:
        return 0.0
    gt = lt = 0
    for x in xs:
        for y in ys:
            if x > y:
                gt += 1
            elif x < y:
                lt += 1
    return (gt - lt) / float(len(xs) * len(ys))


def describe(values: Sequence[Optional[float]]) -> Dict[str, Optional[float]]:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return {"n": 0, "min": None, "median": None, "max": None}
    return {"n": len(vals), "min": round(min(vals), 3),
            "median": round(median(vals), 3), "max": round(max(vals), 3)}


def count_in_band(values: Sequence[Optional[float]], hi: float) -> int:
    return sum(1 for v in values if v is not None and 0.0 <= float(v) <= hi)


# ----------------------------------------------------------------------
# verdict


VERDICT_COLUMNS = ("verdict", "far-rejected (m)", "near-accepted (m)",
                   "far-accepted (m)", "far/near m-per-px", "Cliff's d (px)",
                   "Cliff's d (m)", "inside near range?")


@dataclass
class Verdict:
    label: str
    _rows: Optional[List[ReachRow]] = field(default=None, repr=False)
    far_rejected_m: Dict[str, Optional[float]] = field(default_factory=dict)
    near_accepted_m: Dict[str, Optional[float]] = field(default_factory=dict)
    far_accepted_m: Dict[str, Optional[float]] = field(default_factory=dict)
    delta_px: Optional[float] = None
    delta_m: Optional[float] = None
    m_per_px_ratio: Optional[float] = None

    @property
    def inside_near_range(self) -> Optional[bool]:
        """Is the whole far-rejected metre range inside the near-accepted one?"""
        lo, hi = self.near_accepted_m.get("min"), self.near_accepted_m.get("max")
        flo, fhi = self.far_rejected_m.get("min"), self.far_rejected_m.get("max")
        if None in (lo, hi, flo, fhi):
            return None
        return bool(lo <= flo and fhi <= hi)

    def header(self) -> List[str]:
        return list(VERDICT_COLUMNS)

    @property
    def lateral_refined(self) -> Dict[str, object]:
        """The decisive comparison on rows whose metre reading is VALID.

        A lateral gap (dx = the whole px distance, dy = 0) is a ground-plane
        displacement, so the across component converts it exactly. An
        image-vertical gap (the ball above the player) is not: the camera's
        focal length is not recoverable from these 6 calibration points, so a
        vertical px span has no ground-metre reading and is EXCLUDED from this
        arm rather than converted at the ground scale.
        """
        rows = self._rows or []
        rej = [r for r in rows if r.stage == "rejected" and r.side == "far"]
        near = [r for r in rows if r.stage == "accepted" and r.side == "near"
                and r.geometry == "lateral"]
        far = [r for r in rows if r.stage == "accepted" and r.side == "far"
               and r.geometry == "lateral"]
        near_stat = describe([r.metres for r in near])
        far_stat = describe([r.metres for r in far])
        lo = near_stat.get("min")
        hi = near_stat.get("max")
        inside = (None if lo is None or hi is None
                  else bool(lo <= far_stat["min"] and far_stat["max"] <= hi))
        return {"far_rejected": describe([r.metres for r in rej]),
                "near_accepted": near_stat, "far_accepted": far_stat,
                "n_vertical_excluded": sum(
                    1 for r in rows if r.stage == "accepted"
                    and r.geometry == "vertical"),
                "delta_m": cliffs_delta([r.metres for r in rej],
                                        [r.metres for r in near]) or None,
                "inside_near_range": inside}

    def as_row(self) -> List[str]:
        def rng(d):
            return "-" if not d or not d.get("n") else \
                f"{d['min']}-{d['max']} m (n={d['n']})"

        def cd(v):
            return "-" if v is None else f"{v:+.3f}"

        return [self.label, rng(self.far_rejected_m), rng(self.near_accepted_m),
                rng(self.far_accepted_m),
                "-" if self.m_per_px_ratio is None
                else f"{self.m_per_px_ratio:.2f}x",
                cd(self.delta_px), cd(self.delta_m),
                str(self.inside_near_range)]


def m_per_px_ratio(rows: Sequence[ReachRow]) -> Optional[float]:
    """MEDIAN far/near metres-per-pixel over the measured rows themselves.

    A value above 1.0 means the far side's ground metre spans MORE pixels, so a
    fixed px threshold is a SHORTER physical reach on the far side. Measured,
    not proposed.
    """
    far = [abs(r.metres) / r.px for r in rows
           if r.metres and r.side == "far"]
    near = [abs(r.metres) / r.px for r in rows
            if r.metres and r.side == "near"]
    if not far or not near:
        return None
    return float(median(far)) / float(median(near))


def build_verdict(rows: Optional[Sequence[ReachRow]] = None) -> Verdict:
    rows = all_rows() if rows is None else list(rows)
    rej = [r for r in rows if r.stage == "rejected"]
    acc = [r for r in rows if r.stage == "accepted"]
    pick = lambda rs, s: [r for r in rs if r.side == s]  # noqa: E731
    far_rej, near_acc, far_acc = (pick(rej, "far"), pick(acc, "near"),
                                  pick(acc, "far"))
    v = Verdict(
        label="NOT ANSWERABLE",
        _rows=list(rows),
        far_rejected_m=describe([r.metres for r in far_rej]),
        near_accepted_m=describe([r.metres for r in near_acc]),
        far_accepted_m=describe([r.metres for r in far_acc]),
        delta_px=(cliffs_delta([r.px for r in far_rej],
                               [r.px for r in near_acc])
                  if far_rej and near_acc else None),
        delta_m=(cliffs_delta([r.metres for r in far_rej],
                              [r.metres for r in near_acc])
                 if far_rej and near_acc else None),
        m_per_px_ratio=m_per_px_ratio(rows),
    )
    if far_rej and near_acc and v.inside_near_range is not None:
        v.label = ("SCALE-EXPLAINED" if v.inside_near_range
                   else "NOT SCALE-EXPLAINED")
    return v


# ----------------------------------------------------------------------
# sensitivity


@dataclass
class SensitivityRow:
    reach_px: float
    far_rej_admitted: int
    far_rej_n: int
    near_acc_still_in: int
    near_acc_n: int
    near_noncontact_admitted: int
    near_noncontact_n: int
    near_dropped_admitted: int = 0
    near_dropped_n: int = 0


def sensitivity(rows: Optional[Sequence[ReachRow]] = None,
                window_f: int = 15) -> List[SensitivityRow]:
    """What reach threshold admits the far rejections, and what it exposes.

    Non-contact exposure counts near-side candidate rows REJECTED at a LATER
    gate than the reach gate (``no_contact_geometry``, ``min_contact_gap``)
    within ``window_f`` of a ground-truth contact: a real contact the pipeline
    does not emit today, which a wider reach gate would newly let past the
    reach stage. Rows whose reason is ``no_ball_sighting`` are excluded -- no
    reach value can admit a contact that never reached the gate. Counts only;
    no rule is proposed.
    """
    rows = all_rows() if rows is None else list(rows)
    rej = [r for r in rows if r.stage == "rejected" and r.side == "far"]
    near_acc = [r for r in rows if r.stage == "accepted" and r.side == "near"]
    near_all = near_noncontact_rows(window_f, rejected_only=False)
    near_dropped = [r for r in near_all
                    if r.reason in ("no_contact_geometry", "min_contact_gap")]
    # the scale-corrected threshold, DERIVED from the measured far/near ratio
    ratio = m_per_px_ratio(rows)
    thresholds = sorted({140.0, 180.0, 200.0, 250.0, 320.0,
                         (round(140.0 * ratio, 1) if ratio else None),
                         max((r.px for r in rej), default=140.0)} - {None})
    return [SensitivityRow(
        reach_px=thr,
        far_rej_admitted=sum(1 for r in rej if r.px <= thr),
        far_rej_n=len(rej),
        near_acc_still_in=sum(1 for r in near_acc if r.px <= thr),
        near_acc_n=len(near_acc),
        near_noncontact_admitted=count_in_band([r.px for r in near_all], thr),
        near_noncontact_n=len(near_all),
        near_dropped_admitted=count_in_band([r.px for r in near_dropped], thr),
        near_dropped_n=len(near_dropped),
    ) for thr in thresholds]


def near_noncontact_rows(window_f: int = 15,
                         clips: Sequence[int] = CLIPS,
                         rejected_only: bool = True) -> List[ReachRow]:
    """Near-side rows near a GT contact, scored as the reach gate would.

    One row per near-side candidate record within ``window_f`` of a GT contact,
    holding that ball's distance to the NEAREST near-side player bbox -- so the
    count answers "how many real near-side contacts would a reach threshold of
    T have let past the reach stage".

    ``rejected_only=True`` restricts to candidates the pipeline ALREADY drops
    (``no_contact_geometry`` / ``min_contact_gap`` -- the only reasons reached
    after the reach gate), i.e. the near-side rows a wider gate would newly
    admit. ``False`` returns every near-side candidate near a GT contact,
    accepted ones included, which is the whole denominator.
    """
    out: List[ReachRow] = []
    for clip in clips:
        frames = bucket_gt_frames(clip)
        cal = calibration(clip)
        for _frame, rec in sorted(records(clip).items()):
            ball = (rec.get("ball_track") or {}).get("center")
            players = [p for p in (rec.get("players") or []) if p.get("bbox")]
            if not ball or not players:
                continue
            near_players = [p for p in players
                            if cal.get_team_for_bbox(_as_bbox(p["bbox"])) == "A"]
            if not near_players:
                continue
            if _nearest_frame(int(rec["frame"]), frames, window_f) is None:
                continue
            pl = min(near_players, key=lambda p: point_to_bbox_distance(
                ball, p["bbox"]))
            cands = rec.get("candidates") or []
            if rejected_only:
                picked = [c for c in cands if c.get("stage") == "rejected"
                          and c.get("reason") in ("no_contact_geometry",
                                                   "min_contact_gap")]
                if not picked:
                    continue
                reason = picked[0].get("reason")
            else:
                picked = [c for c in cands if c.get("stage") != "accepted"]
                if not picked:
                    continue
                reason = picked[0].get("reason")
            out.append(_fill(ReachRow(
                clip=clip, frame=int(rec["frame"]), stage="rejected",
                reason=reason, kind=None,
                px=point_to_bbox_distance(ball, pl["bbox"]),
                reach_px=ActionClassifier.CONTACT_REACH,
                track_id=pl.get("track_id"), player_id=None,
                team_flag=None, ball_point=list(ball),
                bbox=list(pl["bbox"]))))
    return out


def gt_contact_rows(clips: Sequence[int] = CLIPS
                    ) -> List[ReachRow]:
    """At every GT contact frame, the ball to the NEAREST same-side player.

    The censoring-free yardstick. The accepted-arm distance is CENSORED: a
    contact the pipeline emits has, by construction, its ball inside the
    player's bbox, so 7 of 13 near accepted rows read 0.0 px. This arm has no
    such selection effect -- it is scored on ALL GT contacts, emitted or not,
    per side. ``stage`` is ``"gt_contact"``, never ``"accepted"``, so it never
    enters the accepted-arm statistics by accident.
    """
    out: List[ReachRow] = []
    for clip in clips:
        cal = calibration(clip)
        recs = records(clip)
        for g in bucket_gt_frames(clip):
            rec = recs.get(g) or recs.get(g + 1) or recs.get(g - 1)
            if rec is None:
                continue
            ball = (rec.get("ball_track") or {}).get("center")
            if not ball:
                continue
            players = [p for p in (rec.get("players") or []) if p.get("bbox")]
            if not players:
                continue
            best = min(players, key=lambda p: point_to_bbox_distance(
                ball, p["bbox"]))
            out.append(_fill(ReachRow(
                clip=clip, frame=g, stage="gt_contact", reason="gt_frame",
                kind=None,
                px=point_to_bbox_distance(ball, best["bbox"]),
                reach_px=ActionClassifier.CONTACT_REACH,
                track_id=best.get("track_id"), player_id=None,
                team_flag=None, ball_point=list(ball),
                bbox=list(best["bbox"]))))
    return out


def gt_frames(clip: int) -> List[int]:
    """Ground-truth contact frames of a drill (read-only, never edited)."""
    path = ROOT / f"ground_truth/video_entreno_{clip}_annotations.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    events = (data.get("actions") or data.get("events")
              or data.get("annotations") or [])
    return [int(e["frame"]) for e in events if e.get("frame") is not None]


def _nearest_frame(frame: int, gt_frames: Sequence[int],
                   window_f: int) -> Optional[int]:
    best = None
    for g in gt_frames:
        if abs(g - frame) <= window_f and (
                best is None or abs(g - frame) < abs(best - frame)):
            best = g
    return best


# ----------------------------------------------------------------------
# report data


def bucket_reach_rows() -> Dict[str, List[Dict[str, float]]]:
    """Reach rows as they survive in ``output/entreno_buckets/buckets.json``.

    They sit inside each GT event's ``gate`` block, under ``reach_rows`` --
    not at the top level of the drill.
    """
    data = json.loads(
        (ROOT / "output/entreno_buckets/buckets.json").read_text())
    out: Dict[str, List[Dict[str, float]]] = {}
    for drill in ("e1", "e2", "e7"):
        rows: List[Dict[str, float]] = []
        for event in (data.get(drill, {}).get("rows") or []):
            rows.extend((event.get("gate") or {}).get("reach_rows") or [])
        if rows:
            out[drill] = rows
    return out


def bucket_gt_frames(clip: int) -> List[int]:
    """GT event frames, as bucketed (the +-15 f census windows are built on these)."""
    data = json.loads(
        (ROOT / "output/entreno_buckets/buckets.json").read_text())
    return [int(r["gt_frame"]) for r in
            (data.get(f"e{clip}", {}).get("rows") or [])
            if r.get("gt_frame") is not None]


if __name__ == "__main__":  # pragma: no cover
    rej, acc = reach_rows(), accepted_rows()
    print("reach rejections:", len(rej), "accepted:", len(acc))
    v = build_verdict()
    print(" | ".join(v.header()))
    print(" | ".join(v.as_row()))