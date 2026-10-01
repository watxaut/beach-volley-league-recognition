"""Serve-evidence EVENT emitters (E1 far flight + E2 serve runway).

Why (STATUS open point G2, 2026-10-01).  The far serve is the loss G1 and G3
share: 12/12 held-out far-serve contacts are missed (baseline F1 0.772), and
every mechanism tried so far (T5 tracker admission, R1 departure gate, S1
looming *discriminator*, pass-2 re-labelling) was refuted.  The owner's
proposal is different in kind: instead of another per-contact classifier, emit
the two pieces of EVIDENCE a far serve physically must leave, and decide with
them afterwards.

* ``FarFlightDetector``  (E1 ``far_flight``) -- after a far-side contact the
  ball flies TOWARD the fixed long-axis camera, so its apparent bbox width
  GROWS.  That is monocular and needs no toss.  S1 refuted using ``L`` to
  *separate* serves from other far lofts; here it is only an event, combined
  with E2 rather than used alone.
* ``ServeRunwayWatcher`` (E2 ``runway_occupant``) -- the server stands OFF the
  court behind the far baseline, so strict foot-in-court admission can never
  track them (``PlayerTracker`` locks exactly 4 in-court tracks; AGENTS.md §1).
  The region is the owner's: behind the far line, inside the two sidelines
  CONTINUED TO INFINITY, not extending behind the near line.
* ``ServeEventEmitter`` -- the conjunction the owner specified: a serve must
  come from a player IN the runway WITH the ball and WITH a contact.  Emitted
  as a ``serve_candidate`` event, never as an action.

Geometry is IMAGE-SPACE, built from the 8 calibration clicks only.  Two reasons:

1. The 4-corner ground homography assumes a 16x8 m beach court; on the beach
   match it is badly wrong at the far end (it predicts a 1.8 m person ~7 px
   tall at the far baseline, where the detector actually returns 90-160 px
   boxes), so metre-based gates there are meaningless.  The clicked pixels are
   what the owner actually vouches for.
2. A "strip between the sidelines, continued to infinity" is a PROJECTIVE
   wedge: the two sidelines converge at an apex (1055, 504) on the beach match
   and close the region by themselves.  No cap constant is needed, and the
   half-plane test excludes everything beyond the apex automatically.

The band is straddling the far baseline by default (``serve_runway_front_frac``
/ ``back_frac``, as a FRACTION of the court's projected depth, because px
constants are venue-coupled -- the court projects 206 px deep on the beach vs
464-479 px at the practice venue, AGENTS.md §7).  Measured over the 17 GT far
serves of the beach match: a STRICT behind-the-line region sees a person at
7/17; the straddling band sees one at 17/17.  ``front_frac`` is therefore the
one knob that decides the emitter's recall, and it is exposed, not baked in.

Inert by construction: ``FrameProcessor`` only builds the emitter when
``serve_events_enabled`` is set (default OFF), it reads detections the
detectors already produced, and it never mutates the action/tracker streams.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

Point = Tuple[float, float]
BBox = Sequence[float]


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def _cross(a: Point, b: Point, p: Point) -> float:
    """Signed 2D cross product (b-a) x (p-a) in image coordinates."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _perp_distance(p: Point, a: Point, b: Point) -> float:
    """Distance from ``p`` to the infinite line through ``a`` and ``b``."""
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length < 1e-9:
        return float("inf")
    return abs(_cross(a, b, p)) / length


class ServeRunway:
    """The far-side serve runway: behind the far line, inside the extended lines.

    ``court_corners`` is the calibration order (far-left, far-right, near-right,
    near-left).  Every test is a half-plane sign test, so a point beyond the
    wedge apex (where the extended sidelines have crossed) is rejected without
    any explicit height cap.
    """

    def __init__(
        self,
        court_corners: Sequence[Sequence[float]],
        midcourt_points: Optional[Sequence[Sequence[float]]] = None,
        front_frac: float = 0.15,
        back_frac: float = 0.30,
        side_margin_frac: float = 0.0,
    ) -> None:
        fl, fr, nr, nl = (tuple(float(v) for v in c) for c in court_corners[:4])
        self.far_left, self.far_right = fl, fr
        self.near_right, self.near_left = nr, nl
        self.far_line = (fl, fr)
        # Sidelines oriented court-ward so "inside" is the court-side sign.
        self.left_line = (nl, fl)
        self.right_line = (nr, fr)
        mid = ((nl[0] + nr[0]) / 2.0, (nl[1] + nr[1]) / 2.0)
        self._left_inside = _cross(*self.left_line, mid)
        self._right_inside = _cross(*self.right_line, mid)
        far_mid_y = (fl[1] + fr[1]) / 2.0
        self.depth_px = abs((nl[1] + nr[1]) / 2.0 - far_mid_y) or 1.0
        self.front_px = float(front_frac) * self.depth_px
        self.back_px = float(back_frac) * self.depth_px
        self.side_margin_px = float(side_margin_frac) * self.depth_px
        self.apex = self._apex()
        # The net (midcourt) line.  Perspective does NOT map ground midpoints to
        # image midpoints, so the calibration's own midcourt clicks are used when
        # available and the corner-midpoint line is only the fallback.
        if midcourt_points is not None and len(midcourt_points) >= 2:
            self.net_line = ((float(midcourt_points[0][0]), float(midcourt_points[0][1])),
                             (float(midcourt_points[1][0]), float(midcourt_points[1][1])))
        else:
            self.net_line = (((fl[0] + nl[0]) / 2.0, (fl[1] + nl[1]) / 2.0),
                             ((fr[0] + nr[0]) / 2.0, (fr[1] + nr[1]) / 2.0))
        far_mid = ((fl[0] + fr[0]) / 2.0, (fl[1] + fr[1]) / 2.0)
        self._far_side_sign = _cross(*self.net_line, far_mid)
        self.net_line_is_calibrated = midcourt_points is not None

    def _apex(self) -> Optional[Point]:
        """Intersection of the two extended sidelines (None if parallel)."""
        (x1, y1), (x2, y2) = self.left_line
        (x3, y3), (x4, y4) = self.right_line
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) < 1e-9:
            return None
        a = x1 * y2 - y1 * x2
        b = x3 * y4 - y3 * x4
        return ((a * (x3 - x4) - (x1 - x2) * b) / den,
                (a * (y3 - y4) - (y1 - y2) * b) / den)

    def offset_far_line(self, point: Point) -> float:
        """Signed px above the far baseline (+ = behind the far line, off court)."""
        return -_cross(*self.far_line, point) / max(
            math.hypot(self.far_right[0] - self.far_left[0],
                       self.far_right[1] - self.far_left[1]), 1e-9)

    def lateral_margin_px(self, point: Point) -> float:
        """Distance inside the extended sidelines (+ = between them)."""
        dl = _perp_distance(point, *self.left_line)
        dr = _perp_distance(point, *self.right_line)
        side = _cross(*self.left_line, point)
        left_gap = dl if side * self._left_inside > 0 else -dl
        side_r = _cross(*self.right_line, point)
        right_gap = dr if side_r * self._right_inside > 0 else -dr
        return min(left_gap, right_gap)

    def is_far_side(self, point: Point, lateral: bool = False) -> bool:
        """True when the point is above the net (midcourt) line, i.e. far side.

        This -- not the ground band -- is the right gate for the BALL.  Two
        measured facts forced it: a contact happens at hand height, tens of px
        above the server's own foot line (a foot band rejects the very contact
        we hunt), and the ball is AIRBORNE afterwards, so the ground-plane
        wedge says nothing about it -- a far serve at the beach match rises to
        y~306, well above the wedge apex (504), and a lateral test would throw
        the entire flight away.  Pass ``lateral=True`` for a point that really
        does lie on the ground.
        """
        if _cross(*self.net_line, point) * self._far_side_sign <= 0:
            return False
        return self.lateral_margin_px(point) >= -self.side_margin_px if lateral else True

    def classify(self, point: Point) -> Optional[str]:
        """``"runway"`` (off court, behind the far line), ``"court"`` (the band
        inside the court), or None when the point is outside the wedge.

        The band spans ``[-front_px, +back_px]`` around the far baseline, so a
        server standing on or just inside the line is still an occupant -- the
        measurement that made this 17/17 instead of 7/17.
        """
        off = self.offset_far_line(point)
        if off < -self.front_px or off > self.back_px:
            return None
        if self.lateral_margin_px(point) < -self.side_margin_px:
            return None
        return "runway" if off > 0 else "court"


def foot_point(bbox: BBox) -> Point:
    """Bottom-centre of a bbox -- the player's ground contact (shared convention)."""
    return ((float(bbox[0]) + float(bbox[2])) / 2.0, float(bbox[3]))


def bbox_gap(bbox: BBox, point: Point) -> float:
    """Distance from ``point`` to the bbox (0 when inside)."""
    dx = max(float(bbox[0]) - point[0], 0.0, point[0] - float(bbox[2]))
    dy = max(float(bbox[1]) - point[1], 0.0, point[1] - float(bbox[3]))
    return math.hypot(dx, dy)


# ---------------------------------------------------------------------------
# E2 -- serve runway occupancy
# ---------------------------------------------------------------------------


class ServeRunwayWatcher:
    """Emits one ``runway_occupant`` event per presence RUN in the band.

    Runs (not per-frame rows) keep the event stream small; the event carries the
    peak evidence so the owner can tell a standing server from a passer-by.
    """

    def __init__(self, runway: ServeRunway, min_conf: float = 0.15,
                 min_frames: int = 3) -> None:
        self.runway = runway
        self.min_conf = float(min_conf)
        self.min_frames = int(min_frames)
        self._run: Optional[Dict[str, Any]] = None
        self.events: List[Dict[str, Any]] = []

    def observe(self, frame_index: int, detections: Sequence[Dict[str, Any]]) -> int:
        """Feed one frame's raw person detections; returns the occupant count."""
        best: Optional[Dict[str, Any]] = None
        for det in detections:
            conf = float(det.get("confidence", 0.0))
            bbox = det.get("bbox")
            if not bbox or len(bbox) != 4 or conf < self.min_conf:
                continue
            region = self.runway.classify(foot_point(bbox))
            if region is None:
                continue
            if best is None or conf > best["confidence"]:
                best = {"bbox": [round(float(v), 1) for v in bbox],
                        "confidence": round(conf, 3),
                        "region": region,
                        "off_far_line_px": round(self.runway.offset_far_line(foot_point(bbox)), 1)}

        if best is None:
            self.close(frame_index - 1)
            return 0

        if self._run is None:
            self._run = {"start": frame_index, "end": frame_index, "frames": 0,
                         "peak_conf": 0.0, "off_far_line_px": best["off_far_line_px"],
                         "bbox": best["bbox"], "regions": {}}
        run = self._run
        run["end"] = frame_index
        run["frames"] += 1
        if best["confidence"] > run["peak_conf"]:
            run["peak_conf"] = best["confidence"]
            run["bbox"] = best["bbox"]
            run["off_far_line_px"] = best["off_far_line_px"]
        run["regions"][best["region"]] = run["regions"].get(best["region"], 0) + 1
        return 1

    def close(self, frame_index: int) -> None:
        """Close an open run (emitting it when long enough)."""
        run, self._run = self._run, None
        if run is None or run["frames"] < self.min_frames:
            return
        self.events.append({
            "type": "runway_occupant",
            "frame": run["start"],
            "start_frame": run["start"],
            "end_frame": run["end"],
            "frames": run["frames"],
            "peak_conf": round(run["peak_conf"], 3),
            "bbox": run["bbox"],
            "off_far_line_px": run["off_far_line_px"],
            "off_court_frames": run["regions"].get("runway", 0),
        })

    def flush(self) -> None:
        self.close(None)


# ---------------------------------------------------------------------------
# E1 -- far flight
# ---------------------------------------------------------------------------


class FarFlightDetector:
    """Emits a ``far_flight`` event per growing-width window starting in the band.

    One ball sighting per frame (the highest-confidence detection -- the ball in
    play is the top candidate; a spare is noise here).  Windows are cut every
    ``span_s`` seconds; a window is an event when its apparent width GREW
    (``L = slope of ln(width) vs seconds > 0``), which for a fixed long-axis
    camera means the ball is approaching the lens: the far-serve signature.
    """

    def __init__(self, runway: ServeRunway, fps: float = 30.0, span_s: float = 0.5,
                 min_points: int = 3, min_growth: float = 0.0,
                 min_conf: float = 0.15, max_gap: int = 3) -> None:
        self.runway = runway
        self.fps = float(fps) or 30.0
        self.span_s = float(span_s)
        self.span_frames = max(2, int(round(float(span_s) * self.fps)))
        self.min_points = int(min_points)
        self.min_growth = float(min_growth)
        self.min_conf = float(min_conf)
        # A far ball is detected on roughly 1 frame in 4 (measured on the beach
        # match), so requiring CONSECUTIVE sightings throws the flight away;
        # the run only breaks when the ball has really gone (or moved elsewhere).
        self.max_gap = max(1, int(max_gap))
        self._seq: List[Dict[str, Any]] = []
        self._prev_frame: Optional[int] = None
        self.events: List[Dict[str, Any]] = []

    def _sighting(self, frame_index: int, detections: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        best = None
        for det in detections:
            conf = float(det.get("confidence", 0.0))
            bbox = det.get("bbox")
            if not bbox or len(bbox) != 4 or conf < self.min_conf:
                continue
            if best is None or conf > best["conf"]:
                center = det.get("center")
                best = {"frame": frame_index, "conf": round(conf, 3),
                        "center": [round(float(center[0]), 1),
                                   round(float(center[1]), 1)] if center else
                                  [round((float(bbox[0]) + float(bbox[2])) / 2, 1),
                                   round((float(bbox[1]) + float(bbox[3])) / 2, 1)],
                        "bbox": [round(float(v), 1) for v in bbox],
                        "width": float(bbox[2] - bbox[0]),
                        "height": float(bbox[3] - bbox[1])}
        return best

    def _slope(self, window: Sequence[Dict[str, Any]]) -> Optional[float]:
        """OLS slope of ln(width) against time in SECONDS."""
        if len(window) < self.min_points:
            return None
        ts = [(s["frame"] - window[0]["frame"]) / self.fps for s in window]
        ys = [math.log(max(s["width"], 1e-6)) for s in window]
        n = len(ts)
        mt = sum(ts) / n
        my = sum(ys) / n
        den = sum((t - mt) ** 2 for t in ts)
        if den < 1e-9:
            return None
        return sum((t - mt) * (y - my) for t, y in zip(ts, ys)) / den

    def observe(self, frame_index: int, detections: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Feed one frame's raw ball detections; returns the events emitted now."""
        sighting = self._sighting(frame_index, detections)
        broken = sighting is None or (
            self._prev_frame is not None and frame_index - self._prev_frame > self.max_gap)
        emitted: List[Dict[str, Any]] = []
        if broken:
            # A flight is a CONTINUOUS widening: a missing frame or a gap closes
            # whatever is pending before the new run starts.
            emitted = self._close(final=True)
            self._seq, self._prev_frame = [], None
            if sighting is None:
                return emitted
        self._seq.append(sighting)
        self._prev_frame = frame_index
        return emitted + self._close(final=False)

    def _close(self, final: bool) -> List[Dict[str, Any]]:
        """Emit every window that has run its course (all of them when final)."""
        emitted: List[Dict[str, Any]] = []
        while self._seq:
            window = [s for s in self._seq
                      if s["frame"] - self._seq[0]["frame"] < self.span_frames]
            last_frame = window[-1]["frame"]
            if not final and self._prev_frame - last_frame < self.span_frames:
                break  # still inside the live window: wait for more sightings
            self._seq = [s for s in self._seq if s["frame"] > last_frame]
            onset = window[0]
            if not self.runway.is_far_side(tuple(onset["center"])):
                continue  # did not start on the far side: not a far-side flight
            slope = self._slope(window)
            if slope is None or slope <= self.min_growth:
                continue
            event = {
                "type": "far_flight",
                "frame": onset["frame"],
                "onset_frame": onset["frame"],
                "end_frame": last_frame,
                "sightings": len(window),
                "growth": round(slope, 3),
                "width_start": round(onset["width"], 1),
                "width_end": round(window[-1]["width"], 1),
                "mean_conf": round(sum(s["conf"] for s in window) / len(window), 3),
                "onset_center": onset["center"],
            }
            self.events.append(event)
            emitted.append(event)
        return emitted

    def flush(self) -> List[Dict[str, Any]]:
        """Close the trailing window (end of video / end of stream)."""
        emitted = self._close(final=True)
        self._seq, self._prev_frame = [], None
        return emitted


# ---------------------------------------------------------------------------
# Structural contact proposer (session 53)
# ---------------------------------------------------------------------------


class ServeContactProposer:
    """``serve_contact`` -- a far-side contact proposed from the RAW detections.

    The conjunction above needs a ``far_flight`` run (>=3 sightings with a
    positive width growth) before it will place a contact, and its reach is 1.0
    bbox heights. Session 53 measured why that is a bad trade: on the 17 GT far
    serves of the beach match the conjunction scores 11/17 once the opener gate
    is applied, but six real serves have a far-side ball in reach and no growing
    run, and the same reach value that rejects all nine owner FALSE/OFFGAME
    moments is what rejects them.

    So this arm drops the flight requirement and widens the reach, and keeps
    only what the false positives cannot fake:

    * the ball must be **ball-sized** (8-60 px). The venue fires the detector at
      ~2 candidates/frame on sand and lines, and the far-band junk measures 3 px
      unscaled -- the size gate is what stops a magnified patch of ground from
      reading as a ball;
    * the person must be in the **runway** region proper (``classify`` returns
      ``"runway"``, i.e. behind or on the far line), not merely in the court
      band -- the band exists to keep the *occupancy* measurement at 17/17, and
      admitting ``"court"`` here is what costs the two owner false positives;
    * the ball must be on the **far side of the net line** (``is_far_side``),
      because the contact happens at hand height and the ball is airborne after
      it (a ground-plane wedge throws the whole flight away);
    * the contact is placed at the **last qualifying sighting of a run**, which
      is the frame the ball is still with the server. No lookahead: a run closes
      on its own, so the proposer is causal and belongs in ``process_frame``.

    Emitting one candidate per run (not per frame) is what keeps the stream
    small. Everything it emits is EVIDENCE: the opener gate (a serve opens a
    rally) is structural bookkeeping the post-hoc layer applies, because only it
    has the whole action stream. Measured frontier:
    ``docs/g4_structural_serve.md``.
    """

    def __init__(self, runway: ServeRunway, min_conf: float = 0.15,
                 ball_min_conf: float = 0.15, reach_factor: float = 1.5,
                 ball_w_min: int = 8, ball_w_max: int = 60,
                 max_gap: int = 3) -> None:
        self.runway = runway
        self.min_conf = float(min_conf)
        self.ball_min_conf = float(ball_min_conf)
        self.reach_factor = float(reach_factor)
        self.ball_w_min = int(ball_w_min)
        self.ball_w_max = int(ball_w_max)
        self.max_gap = int(max_gap)
        self._run: Optional[Dict[str, Any]] = None
        self.events: List[Dict[str, Any]] = []

    def observe(self, frame_index: int, person_detections: Sequence[Dict[str, Any]],
                ball_detections: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """One frame; returns a ``serve_contact`` event when a run closes."""
        best = self._best_pair(frame_index, person_detections, ball_detections)
        if best is None:
            if self._run is not None and frame_index - self._run["last_frame"] > self.max_gap:
                return self._close()
            return []
        if self._run is None:
            self._run = {"start_frame": frame_index, "sightings": 1,
                         "last_frame": frame_index, "best": best}
            return []
        self._run["sightings"] += 1
        self._run["last_frame"] = frame_index
        if best["gap_norm"] < self._run["best"]["gap_norm"]:
            self._run["best"] = best
        return []

    def _best_pair(self, frame_index: int, person_detections: Sequence[Dict[str, Any]],
                   ball_detections: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """The closest ball-in-reach pair this frame, or None."""
        best: Optional[Dict[str, Any]] = None
        for det in person_detections:
            bbox = det.get("bbox")
            conf = float(det.get("confidence", 0.0))
            if not bbox or len(bbox) != 4 or conf < self.min_conf:
                continue
            if self.runway.classify(foot_point(bbox)) != "runway":
                continue
            height = float(bbox[3] - bbox[1])
            if height <= 0:
                continue
            for ball in ball_detections:
                if float(ball.get("confidence", 0.0)) < self.ball_min_conf:
                    continue
                box = ball.get("bbox")
                if not box or len(box) != 4:
                    continue
                width = float(box[2] - box[0])
                if not (self.ball_w_min <= width <= self.ball_w_max):
                    continue
                center = ball.get("center")
                if not center:
                    continue
                point = (float(center[0]), float(center[1]))
                if not self.runway.is_far_side(point):
                    continue
                gap = bbox_gap(bbox, point) / height
                if gap > self.reach_factor:
                    continue
                if best is None or gap < best["gap_norm"]:
                    best = {"frame": frame_index, "gap_norm": round(gap, 3),
                            "occupant_bbox": [round(float(v), 1) for v in bbox],
                            "occupant_conf": round(conf, 3),
                            "ball_width": round(width, 1),
                            "ball_conf": round(float(ball.get("confidence", 0.0)), 3),
                            "ball_center": [round(point[0], 1), round(point[1], 1)]}
        return best

    def _close(self) -> List[Dict[str, Any]]:
        run, self._run = self._run, None
        if run is None or run["sightings"] < 2:
            return []          # a single frame is a phantom, not a contact
        best = run["best"]
        event = {
            "type": "serve_contact",
            # The contact is where the ball is still WITH the server: the last
            # frame of the run, not the frame of the closest approach (which can
            # be earlier, while the ball is being held).
            "frame": run["last_frame"],
            "contact_frame": run["last_frame"],
            "evidence_frame": best["frame"],
            "start_frame": run["start_frame"],
            "sightings": run["sightings"],
            "occupant_bbox": best["occupant_bbox"],
            "occupant_region": "runway",
            "occupant_conf": best["occupant_conf"],
            "ball_gap_norm": best["gap_norm"],
            "ball_width": best["ball_width"],
            "ball_conf": best["ball_conf"],
            "ball_center": best["ball_center"],
        }
        self.events.append(event)
        return [event]

    def flush(self) -> List[Dict[str, Any]]:
        return self._close()


# ---------------------------------------------------------------------------
# Combiner -- the owner's rule
# ---------------------------------------------------------------------------


class ServeEventEmitter:
    """Owns both emitters and the conjunction: runway occupant + ball + contact.

    "The serve must come from a player in this area with the ball and with a
    contact" -> a ``serve_candidate`` event is emitted when a ``far_flight``
    onset has, within ``lookback_s``, an occupant of the runway whose box the
    ball was inside-or-next-to (gap <= ``reach_factor`` x occupant height).
    The event carries its evidence, never a decision: scoring against the owner
    GT is a separate, explicit step.
    """

    def __init__(
        self,
        court_corners: Sequence[Sequence[float]],
        midcourt_points: Optional[Sequence[Sequence[float]]] = None,
        fps: float = 30.0,
        front_frac: float = 0.15,
        back_frac: float = 0.30,
        side_margin_frac: float = 0.0,
        runway_min_conf: float = 0.15,
        runway_min_frames: int = 3,
        ball_min_conf: float = 0.15,
        far_flight_span_s: float = 0.5,
        far_flight_min_points: int = 3,
        far_flight_min_growth: float = 0.0,
        far_flight_max_gap: int = 3,
        reach_factor: float = 1.0,
        lookback_s: float = 5.0,
        structural_enabled: bool = True,
        structural_reach_factor: float = 1.5,
        structural_ball_w_min: int = 8,
        structural_ball_w_max: int = 60,
        structural_max_gap: int = 3,
    ) -> None:
        self.runway = ServeRunway(court_corners, midcourt_points,
                                  front_frac, back_frac, side_margin_frac)
        self.watcher = ServeRunwayWatcher(self.runway, runway_min_conf, runway_min_frames)
        self.flight = FarFlightDetector(self.runway, fps, far_flight_span_s,
                                        far_flight_min_points, far_flight_min_growth,
                                        ball_min_conf, far_flight_max_gap)
        self.reach_factor = float(reach_factor)
        self.lookback_s = float(lookback_s)
        self.lookback_frames = int(round(float(lookback_s) * (float(fps) or 30.0)))
        self.ball_min_conf = float(ball_min_conf)
        self._reach: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []
        # The structural arm (session 53): the same runway occupant and a
        # ball-SIZED far-side detection in reach, WITHOUT requiring a
        # ``far_flight`` run.  It is a separate event type so the post-hoc
        # consumer can union the two; see docs/g4_structural_serve.md for the
        # measured frontier (11/17 at precision 1.00 on its own, 14/17 unioned
        # with the gated conjunction, vs 0/17 in the action stream).
        self.contacts = ServeContactProposer(
            runway=self.runway,
            min_conf=self.watcher.min_conf,
            ball_min_conf=self.ball_min_conf,
            reach_factor=float(structural_reach_factor),
            ball_w_min=int(structural_ball_w_min),
            ball_w_max=int(structural_ball_w_max),
            max_gap=int(structural_max_gap),
        ) if structural_enabled else None

    def observe(
        self,
        frame_index: int,
        person_detections: Sequence[Dict[str, Any]],
        ball_detections: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """One frame of evidence; returns the events emitted on this frame."""
        occupied = self.watcher.observe(frame_index, person_detections)
        emitted = self.flight.observe(frame_index, ball_detections)
        if occupied:
            self._record_reach(frame_index, person_detections, ball_detections)
        if self.contacts is not None:
            emitted.extend(self.contacts.observe(frame_index, person_detections,
                                                 ball_detections))
        for flight in list(emitted):  # snapshot: candidates are appended below
            if flight.get("type") != "far_flight":
                continue
            candidate = self._combine(frame_index, flight)
            if candidate is not None:
                self.events.append(candidate)
                emitted.append(candidate)
        return emitted

    def _record_reach(self, frame_index: int,
                      person_detections: Sequence[Dict[str, Any]],
                      ball_detections: Sequence[Dict[str, Any]]) -> None:
        """'the ball is with the occupant' -- nearest ball within reach of the box."""
        for det in person_detections:
            bbox = det.get("bbox")
            conf = float(det.get("confidence", 0.0))
            if not bbox or len(bbox) != 4 or conf < self.watcher.min_conf:
                continue
            if self.runway.classify(foot_point(bbox)) is None:
                continue
            height = float(bbox[3] - bbox[1])
            if height <= 0:
                continue
            for ball in ball_detections:
                if float(ball.get("confidence", 0.0)) < self.ball_min_conf:
                    continue
                center = ball.get("center")
                if not center:
                    continue
                gap = bbox_gap(bbox, (float(center[0]), float(center[1])))
                norm = gap / height
                if norm > self.reach_factor:
                    continue
                self._reach.append({
                    "frame": frame_index,
                    "gap_norm": round(norm, 3),
                    "occupant_conf": round(conf, 3),
                    "ball_conf": round(float(ball.get("confidence", 0.0)), 3),
                    "bbox": [round(float(v), 1) for v in bbox],
                    "region": self.runway.classify(foot_point(bbox)),
                })

    def _combine(self, frame_index: int, flight: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        onset = int(flight["onset_frame"])
        window = [r for r in self._reach if onset - self.lookback_frames <= r["frame"] <= onset]
        if not window:
            return None
        # Closest approach wins; ties go to the most recent (the pre-contact hold).
        best = min(window, key=lambda r: (r["gap_norm"], -r["frame"]))
        return {
            "type": "serve_candidate",
            # The contact proxy is the ball BEING WITH the player (nearest
            # approach inside the lookback), not the flight onset: the ball only
            # starts growing once it is already on its way at the camera, which
            # is a few frames AFTER the contact. Both frames are reported.
            "frame": best["frame"],
            "contact_frame": best["frame"],
            "flight_onset_frame": onset,
            "evidence_frame": best["frame"],
            "onset_lead_frames": onset - best["frame"],
            "occupant_bbox": best["bbox"],
            "occupant_region": best["region"],
            "occupant_conf": best["occupant_conf"],
            "ball_gap_norm": best["gap_norm"],
            "ball_conf": best["ball_conf"],
            "flight_growth": flight["growth"],
            "flight_sightings": flight["sightings"],
        }

    def finish(self) -> List[Dict[str, Any]]:
        """Close open runs/trailing windows and return everything emitted."""
        self.flight.flush()
        self.watcher.flush()
        if self.contacts is not None:
            self.contacts.flush()
        self.events = self.watcher.events + self.flight.events + [
            e for e in self.events if e["type"] == "serve_candidate"]
        if self.contacts is not None:
            self.events.extend(self.contacts.events)
        self.events.sort(key=lambda e: e["frame"])
        return self.events

    @classmethod
    def from_config(cls, config: Dict[str, Any], court_corners: Sequence[Sequence[float]],
                    fps: float = 30.0,
                    midcourt_points: Optional[Sequence[Sequence[float]]] = None
                    ) -> "ServeEventEmitter":
        """Build from the pipeline config (the keys live in DEFAULT_CONFIG).

        ``fps`` comes from the caller (FrameProcessor.setup_video_fps), not from
        the config: video_info only reaches the config late in a CLI run.
        """
        return cls(
            court_corners=court_corners,
            midcourt_points=midcourt_points,
            fps=fps,
            front_frac=config.get("serve_runway_front_frac", 0.15),
            back_frac=config.get("serve_runway_back_frac", 0.30),
            side_margin_frac=config.get("serve_runway_side_margin_frac", 0.0),
            runway_min_conf=config.get("serve_runway_min_conf", 0.15),
            runway_min_frames=config.get("serve_runway_min_frames", 3),
            ball_min_conf=config.get("serve_ball_min_conf", 0.15),
            far_flight_span_s=config.get("far_flight_span_s", 0.5),
            far_flight_min_points=config.get("far_flight_min_points", 3),
            far_flight_min_growth=config.get("far_flight_min_growth", 0.0),
            far_flight_max_gap=config.get("far_flight_max_gap", 3),
            reach_factor=config.get("serve_candidate_reach_factor", 1.0),
            lookback_s=config.get("serve_candidate_lookback_s", 5.0),
            structural_enabled=config.get("serve_structural_enabled", True),
            structural_reach_factor=config.get("serve_structural_reach_factor", 1.5),
            structural_ball_w_min=config.get("serve_structural_ball_w_min", 8),
            structural_ball_w_max=config.get("serve_structural_ball_w_max", 60),
            structural_max_gap=config.get("serve_structural_max_gap", 3),
        )
