"""Ball events and the flights between them, in metres and seconds.

The causal pass leaves two things the post-run layer needs: the tracked ball
(position + bbox per frame) and the trajectory VERTICES the classifier found
(accepted contacts and vertices its reach gate refused). This module turns
them into a time-ordered event list and fits every flight between two events:

* a flight is ballistic, so its speed along the court axis is constant and
  ``1 / ball_width`` is LINEAR in time. One robust line through a whole
  flight gives the depth at both of its ends far better than any single
  width sample (a 2 px error is ~2 m at the far end);
* a BIRTH is a tracked run that starts with no ball before it (the online
  tracker locks a few frames after a far serve leaves the hand, so the far
  serve has no vertex of its own -- the birth IS its evidence);
* a tracking gap is bridged when the ball provably kept flying (it left and
  re-entered through the top of the frame, or it was briefly occluded).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from .geometry import BALL_DIAMETER_M, NET_Y_M, CourtGeometry
from .stream import BALL_TRACKED, ContactCandidate, MatchStream

# A tracked run tolerates holes this long (the tracker coasts / low-conf frames).
RUN_HOLE_S = 0.16
# Tracking gaps (see BallTimeline._gap_kind). A gap up to GAP_TOUCH_MAX_S is
# either the same flight (the ball reappears where gravity puts it, within
# GAP_MISS_M (+ per second of gap) and GAP_STEP_MS of velocity) or hides a
# touch; a longer one is a break in the track.
GAP_TOUCH_MAX_S = 0.8
GAP_MISS_M = 1.0
GAP_MISS_M_PER_S = 1.5
GAP_STEP_MS = 4.0
GAP_BLINK_S = 0.25
GAP_MIN_FLIGHT_MS = 1.5
OCCLUSION_REACH_BALLS = 6.0        # per 0.1 s of gap, in ball widths
GAP_FLIGHT, GAP_TOUCH, GAP_BREAK = "flight", "touch", "break"
SOURCE_GAP = "gap"                 # a vertex inferred from a GAP_TOUCH
# Top-of-frame exit/re-entry (a set or a lob flies above the picture).
REENTRY_GAP_S = 3.2
TOP_BAND_BALLS = 2.5
# Samples this close to an event are occluded by hands/body: skip them in fits.
EVENT_SKIP_FRAMES = 1
# Window for a flight's launch speed (see Flight.launch_speed_ms).
LAUNCH_WINDOW_S = 0.5
# Duplicate vertices (accepted + refused on neighbouring frames).
MERGE_EVENTS_S = 0.25

# A flight needs this many width samples before its depth is trusted.
MIN_DEPTH_SAMPLES = 3

EVENT_CONTACT = "contact"          # classifier vertex
EVENT_BIRTH = "birth"              # tracked run starts from nothing
EVENT_DEATH = "death"              # tracked run ends and nothing follows


@dataclass
class BallEvent:
    frame: int
    kind: str                                  # contact | birth | death
    candidate: Optional[ContactCandidate] = None
    source: str = "classifier"                 # who found a contact vertex
    u: float = float("nan")                    # ball centre at the event
    v: float = float("nan")
    # Court-axis position read from the flight that ARRIVES at the event and
    # the one that LEAVES it (None when that flight has no usable samples).
    y_in: Optional[float] = None
    y_out: Optional[float] = None
    flight_in: Optional["Flight"] = None
    flight_out: Optional["Flight"] = None

    @property
    def accepted(self) -> bool:
        return bool(self.candidate is not None and self.candidate.accepted)

    def _depth_reads(self) -> List[Tuple[float, int]]:
        ys = [(self.y_in, self.flight_in), (self.y_out, self.flight_out)]
        vals = [(y, fl.n) for y, fl in ys
                if y is not None and fl is not None and fl.n >= MIN_DEPTH_SAMPLES]
        if not vals:                    # a couple of samples beat no read at all
            vals = [(y, fl.n) for y, fl in ys if y is not None and fl is not None]
        return vals

    def court_y(self) -> Optional[float]:
        """Best single read of where along the court the event happened."""
        vals = self._depth_reads()
        if not vals:
            return None
        total = sum(n for _, n in vals)
        return sum(y * n for y, n in vals) / total

    def depth_samples(self) -> int:
        """Flight samples behind ``court_y()``."""
        return sum(n for _, n in self._depth_reads())


@dataclass
class Flight:
    """Tracked samples between two consecutive events."""

    start: int                 # event frame it leaves
    end: int                   # event frame it arrives at
    n: int                     # tracked samples used by the fit
    y_start: float             # fitted court_y at ``start``
    y_end: float               # fitted court_y at ``end``
    first: int                 # first / last sample frame
    last: int
    peak_height_m: float       # highest sample (metres above the sand)
    ground_frames: int         # samples resting on / skimming the sand
    last_u: float = float("nan")
    last_v: float = float("nan")
    # Court-axis speed over the flight's first LAUNCH_WINDOW_S (m/s, + =
    # toward the camera): a serve into the net stops there, so the whole-
    # flight line under-reads how hard it left the hand.
    launch_speed_ms: float = 0.0
    start_height_m: float = float("nan")   # first sample
    end_height_m: float = float("nan")     # last sample

    @property
    def crosses_net(self) -> bool:
        return (self.y_start - NET_Y_M) * (self.y_end - NET_Y_M) < 0

    def axis_speed_ms(self, fps: float) -> float:
        """Court-axis speed, + = toward the camera (near baseline)."""
        frames = max(self.end - self.start, 1)
        return (self.y_end - self.y_start) / frames * fps


class BallTimeline:
    """Events + flights of one video, built once from a ``MatchStream``."""

    def __init__(self, stream: MatchStream, geometry: CourtGeometry,
                 frame_size: Tuple[int, int] = (1920, 1080)) -> None:
        self.stream = stream
        self.geometry = geometry
        self.frame_w, self.frame_h = frame_size
        self.fps = stream.fps
        w = stream.ball_w
        self.court_y = geometry.court_y_from_width(w)          # per-frame, noisy
        self.inv_w = np.where(np.isfinite(w) & (w > 0), 1.0 / w, np.nan)
        self.clipped = self._clipped_mask()
        self.height_m = self._height()
        self.grounded = self._grounded_mask()
        self.runs = self._tracked_runs()
        self.events: List[BallEvent] = self._build_events()
        self.flights: List[Flight] = self._fit_flights()

    # -- per-frame reads -------------------------------------------------- #

    def _clipped_mask(self) -> np.ndarray:
        """Ball bbox cut by the picture edge: its width is not a depth read."""
        b = self.stream.ball_bbox
        with np.errstate(invalid="ignore"):
            return ((b[:, 0] <= 1) | (b[:, 1] <= 1)
                    | (b[:, 2] >= self.frame_w - 2) | (b[:, 3] >= self.frame_h - 2))

    def _height(self) -> np.ndarray:
        """Metres above the sand per tracked frame (from its own width)."""
        s = self.stream
        out = np.full(s.n_frames, np.nan)
        for f in np.flatnonzero(np.isfinite(self.court_y)):
            out[f] = self.geometry.ball_world(
                s.ball_xy[f, 0], s.ball_xy[f, 1], float(self.court_y[f]))[2]
        return out

    def _grounded_mask(self) -> np.ndarray:
        """The #80 local-scale test, recomputed offline per tracked frame.

        A ball on the sand measures the width the ground homography predicts
        at its own bottom point (ratio ~1); an airborne ball is nearer the
        lens than the ground behind it (ratio > 1). Clipped boxes never count.
        """
        s, g = self.stream, self.geometry
        out = np.zeros(s.n_frames, dtype=bool)
        for f in np.flatnonzero(s.tracked & ~self.clipped):
            b = s.ball_bbox[f]
            world = g.image_to_world((b[0] + b[2]) / 2.0, b[3])
            if world is None or not (-40.0 < world[1] < 60.0):
                continue
            ratio = (b[2] - b[0]) / float(g.width_at(world[1]))
            out[f] = ratio <= GROUND_RATIO_MAX
        return out

    def ground_world(self, frame: int) -> Optional[Tuple[float, float]]:
        """Ground-plane position of a GROUNDED ball (its bottom point)."""
        b = self.stream.ball_bbox[frame]
        if not np.isfinite(b[0]):
            return None
        return self.geometry.image_to_world((b[0] + b[2]) / 2.0, b[3])

    def ground_world_error(self, frame: int) -> Optional[Tuple[float, float]]:
        """(across, along) metres ``ground_world(frame)`` may be off by."""
        b = self.stream.ball_bbox[frame]
        if not np.isfinite(b[0]):
            return None
        return self.geometry.ground_read_error_m((b[0] + b[2]) / 2.0, b[3])

    # -- runs and gaps ---------------------------------------------------- #

    def _tracked_runs(self) -> List[Tuple[int, int]]:
        frames = np.flatnonzero(self.stream.ball_state == BALL_TRACKED)
        if frames.size == 0:
            return []
        hole = max(1, self.stream.frames(RUN_HOLE_S))
        runs, start, prev = [], int(frames[0]), int(frames[0])
        for f in frames[1:]:
            f = int(f)
            if f - prev > hole + 1:
                runs.append((start, prev))
                start = f
            prev = f
        runs.append((start, prev))
        return runs

    def _velocity(self, frame: int, direction: int, span: int = 3
                  ) -> Optional[np.ndarray]:
        """px/frame from the samples on one side of ``frame`` (direction -1 =
        the samples before it, +1 = after it)."""
        xy = self.stream.ball_xy
        pts = []
        for k in range(0, span + 2):
            f = frame + direction * k
            if 0 <= f < self.stream.n_frames and self.stream.ball_state[f] == BALL_TRACKED:
                pts.append((f, xy[f]))
        if len(pts) < 2:
            return None
        (f0, p0), (f1, p1) = pts[0], pts[-1]
        return (p1 - p0) / (f1 - f0)

    def impulse(self, frame: int, span: int = 3) -> Optional[float]:
        """Image-plane velocity change at ``frame`` in m/s, gravity removed.

        Free flight changes the image velocity only by gravity; a hit adds a
        step. Scaled by the ball's own width, so the read is the same at
        either end of the court.
        """
        s = self.stream
        lo, hi = frame - span, frame + span
        if lo < 0 or hi >= s.n_frames:
            return None
        if not (s.ball_state[lo] == s.ball_state[frame] == s.ball_state[hi] == BALL_TRACKED):
            return None
        w = s.ball_w[frame]
        if not np.isfinite(w) or w <= 0:
            return None
        px_per_m = w / BALL_DIAMETER_M
        v_pre = (s.ball_xy[frame] - s.ball_xy[lo]) / span
        v_post = (s.ball_xy[hi] - s.ball_xy[frame]) / span
        gravity = np.array([0.0, 9.81 / (self.fps ** 2) * px_per_m * span])
        return float(np.hypot(*(v_post - v_pre - gravity)) / px_per_m * self.fps)

    def _gap_kind(self, end: int, start: int) -> str:
        """What happened across the tracking gap (end, start).

        * ``GAP_FLIGHT`` -- the ball kept flying: where and how fast it
          reappears is what gravity predicts from how it vanished (or it left
          and re-entered through the top of the frame);
        * ``GAP_TOUCH`` -- a short gap the ball came out of on a different
          trajectory: it was touched while hidden (hands and body occlude the
          ball exactly at a contact, and the tracker's gate drops it on the
          direction change);
        * ``GAP_BREAK`` -- anything else: the track died and a new one began.
        """
        s = self.stream
        gap = start - end
        gap_s = s.seconds(gap)
        w = np.nanmean([s.ball_w[end], s.ball_w[start]])
        if not np.isfinite(w) or w <= 0:
            return GAP_BREAK
        v_out = self._velocity(end, -1)
        v_in = self._velocity(start, +1)
        # Top-of-frame excursion: left rising near the top, came back falling.
        top = TOP_BAND_BALLS * w
        if (gap_s <= REENTRY_GAP_S and s.ball_xy[end, 1] <= top
                and s.ball_xy[start, 1] <= top
                and (v_out is None or v_out[1] < 0)
                and (v_in is None or v_in[1] > 0)):
            return GAP_FLIGHT
        if gap_s > GAP_TOUCH_MAX_S:
            return GAP_BREAK
        moved = float(np.hypot(*(s.ball_xy[start] - s.ball_xy[end])))
        if v_out is None or v_in is None:
            # No velocity to compare: only a blink is taken as the same flight.
            near = moved <= OCCLUSION_REACH_BALLS * w * max(gap_s / 0.1, 1.0)
            return GAP_FLIGHT if (gap_s <= GAP_BLINK_S and near) else GAP_BREAK
        px_per_m = w / BALL_DIAMETER_M
        g = 9.81 / (self.fps ** 2) * px_per_m            # px / frame^2
        predicted = s.ball_xy[end] + v_out * gap + np.array([0.0, 0.5 * g * gap * gap])
        miss_m = float(np.hypot(*(s.ball_xy[start] - predicted))) / px_per_m
        step_ms = float(np.hypot(*(v_in - v_out - np.array([0.0, g * gap])))
                        ) / px_per_m * self.fps
        if (miss_m <= GAP_MISS_M + GAP_MISS_M_PER_S * gap_s
                and step_ms <= GAP_STEP_MS):
            return GAP_FLIGHT
        # A touch redirects a ball that IS flying. A resting ball that
        # "reappears" somewhere else is another ball (the tracker re-locked
        # from a spare one) or somebody picking it up -- a break either way.
        to_ms = self.fps / px_per_m
        if min(float(np.hypot(*v_out)), float(np.hypot(*v_in))) * to_ms < GAP_MIN_FLIGHT_MS:
            return GAP_BREAK
        return GAP_TOUCH

    # -- events ----------------------------------------------------------- #

    def _build_events(self) -> List[BallEvent]:
        s = self.stream
        events: List[BallEvent] = []
        merge = max(1, s.frames(MERGE_EVENTS_S))
        for cand in s.candidates:
            if not (0 <= cand.frame < s.n_frames):
                continue
            # accepted rows sort first: a refused twin within the merge window
            # is the same vertex.
            twin = next((e for e in events if abs(e.frame - cand.frame) <= merge), None)
            if twin is not None:
                if cand.accepted and not twin.accepted:
                    twin.candidate, twin.frame = cand, cand.frame
                continue
            events.append(BallEvent(frame=cand.frame, kind=EVENT_CONTACT, candidate=cand))
        contact_frames = np.array(sorted(e.frame for e in events), dtype=int)

        def has_vertex(end: int, start: int) -> bool:
            return bool(((contact_frames >= end - 1) & (contact_frames <= start + 1)).any())

        for i, (a, b) in enumerate(self.runs):
            if i == 0:
                events.append(BallEvent(frame=a, kind=EVENT_BIRTH))
            if i == len(self.runs) - 1:
                events.append(BallEvent(frame=b, kind=EVENT_DEATH))
                continue
            nxt = self.runs[i + 1][0]
            kind = self._gap_kind(b, nxt)
            if kind == GAP_FLIGHT:
                continue
            if has_vertex(b, nxt) and s.seconds(nxt - b) <= REENTRY_GAP_S:
                continue                    # the classifier already placed it
            if kind == GAP_TOUCH:
                events.append(BallEvent(frame=(b + nxt) // 2, kind=EVENT_CONTACT,
                                        source=SOURCE_GAP))
                continue
            events.append(BallEvent(frame=b, kind=EVENT_DEATH))
            events.append(BallEvent(frame=nxt, kind=EVENT_BIRTH))
        events.sort(key=lambda e: (e.frame, {EVENT_DEATH: 0, EVENT_BIRTH: 1,
                                             EVENT_CONTACT: 2}[e.kind]))
        for e in events:
            f = self._nearest_tracked(e.frame, reach=s.frames(GAP_TOUCH_MAX_S))
            if f is not None:
                e.u, e.v = float(s.ball_xy[f, 0]), float(s.ball_xy[f, 1])
            if e.candidate is not None and e.candidate.point is not None:
                e.u, e.v = e.candidate.point
        return events

    def _nearest_tracked(self, frame: int, reach: int = 4) -> Optional[int]:
        s = self.stream
        for d in range(0, reach + 1):
            for f in (frame - d, frame + d):
                if 0 <= f < s.n_frames and s.ball_state[f] == BALL_TRACKED:
                    return f
        return None

    # -- flights ---------------------------------------------------------- #

    def _fit_flights(self) -> List[Flight]:
        flights: List[Flight] = []
        for a, b in zip(self.events, self.events[1:]):
            if a.kind == EVENT_DEATH or b.kind == EVENT_BIRTH:
                continue                      # nothing tracked in between
            flight = self.fit_span(a.frame, b.frame)
            if flight is None:
                continue
            flights.append(flight)
            a.flight_out, a.y_out = flight, flight.y_start
            b.flight_in, b.y_in = flight, flight.y_end
        return flights

    def fit_span(self, start: int, end: int) -> Optional[Flight]:
        """Robust court-axis line through the tracked samples of (start, end)."""
        s = self.stream
        lo, hi = start + EVENT_SKIP_FRAMES, end - EVENT_SKIP_FRAMES
        if hi - lo < 1:
            lo, hi = start, end
        idx = np.arange(max(lo, 0), min(hi, s.n_frames - 1) + 1)
        ok = idx[np.isfinite(self.inv_w[idx]) & ~self.clipped[idx]]
        if ok.size == 0:
            ok = idx[np.isfinite(self.inv_w[idx])]
        if ok.size == 0:
            return None
        t = ok.astype(np.float64)
        z = self.inv_w[ok]
        if ok.size >= 4 and t[-1] - t[0] >= 3:
            slope = _theil_sen_slope(t, z)
            intercept = float(np.median(z - slope * t))
        else:
            slope, intercept = 0.0, float(np.median(z))

        def y_at(frame: float) -> float:
            inv = intercept + slope * frame
            # Extrapolating past the camera (inv <= 0) is a degenerate fit.
            inv = max(inv, 1.0 / (4.0 * self.geometry.ball_px_near))
            return float(self.geometry.court_y_from_width(1.0 / inv))

        all_idx = idx[np.isfinite(self.inv_w[idx])]
        heights = self.height_m[all_idx]
        head = ok[ok <= ok[0] + s.frames(LAUNCH_WINDOW_S)]
        launch_speed = 0.0
        if head.size >= 4:
            th, zh = head.astype(np.float64), self.inv_w[head]
            sl = _theil_sen_slope(th, zh)
            ic = float(np.median(zh - sl * th))
            y0 = float(self.geometry.court_y_from_width(1.0 / max(ic + sl * th[0], 1e-4)))
            y1 = float(self.geometry.court_y_from_width(1.0 / max(ic + sl * th[-1], 1e-4)))
            launch_speed = (y1 - y0) / (th[-1] - th[0]) * self.fps
        return Flight(
            launch_speed_ms=launch_speed,
            start_height_m=float(heights[0]), end_height_m=float(heights[-1]),
            start=start, end=end, n=int(ok.size),
            y_start=y_at(start), y_end=y_at(end),
            first=int(all_idx[0]), last=int(all_idx[-1]),
            peak_height_m=float(np.nanmax(heights)) if heights.size else float("nan"),
            ground_frames=int(self.grounded[all_idx].sum()),
            last_u=float(s.ball_xy[all_idx[-1], 0]),
            last_v=float(s.ball_xy[all_idx[-1], 1]),
        )


# Ground test band (the #80 observer enters GROUND at 1.25; resting balls in
# this camera measure 0.93-0.98 of the homography prediction).
GROUND_RATIO_MAX = 1.2


def _theil_sen_slope(t: np.ndarray, z: np.ndarray) -> float:
    """Median of pairwise slopes (robust to occlusion-clipped widths)."""
    n = t.size
    if n > 60:                                 # bound the O(n^2) pair count
        pick = np.linspace(0, n - 1, 60).round().astype(int)
        t, z = t[pick], z[pick]
    dt = t[None, :] - t[:, None]
    dz = z[None, :] - z[:, None]
    mask = dt > 0
    return float(np.median(dz[mask] / dt[mask]))
