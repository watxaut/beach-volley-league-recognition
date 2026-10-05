"""Point segmentation: where a rally starts (the serve) and where it ends.

A point is a SERVE plus everything the ball does until it dies. Both ends are
read from physics the causal pass cannot use because they need hindsight:

* **Serve** = a launch that starts beside a baseline, climbs above net height
  and travels to the other half (or dies at the net). Dead-time ball handling
  never looks like that: a pre-serve bounce routine stays at the baseline, a
  ball rolled or tossed back to the server stays below net height, and a lob
  back from mid-court does not start at the baseline. The far serve has no
  trajectory vertex of its own (the online tracker locks a few frames after
  the ball leaves the hand), so its launch is the BIRTH of the track.
* **End** = the first of: the ball on the sand, the ball dropping at the net,
  or no touch for longer than a ball can stay in the air.

Everything between two points is discarded -- that is where the causal
stream's false contacts live (ball pick-ups, bounce routines, throws).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from .ball_flights import (
    EVENT_BIRTH,
    EVENT_CONTACT,
    EVENT_DEATH,
    MIN_DEPTH_SAMPLES,
    BallEvent,
    BallTimeline,
    Flight,
)
from .geometry import COURT_LENGTH_M, COURT_WIDTH_M, NET_Y_M, SIDE_FAR, SIDE_NEAR

# -- serve launch --------------------------------------------------------- #
# A serve must clear a 2.24-2.43 m net; one that fails was still aimed over.
SERVE_MIN_PEAK_M = 2.2
# Highest a serve leaves the hand (a jump serve is hit at ~3.2 m).
SERVE_MAX_CONTACT_M = 4.2
# Near launches are depth-precise: the server stands at / behind the line.
NEAR_SERVE_MIN_Y = COURT_LENGTH_M - 2.0
# Far launches are not (2 px of width is ~2 m there): anywhere in the far half.
FAR_SERVE_MAX_Y = NET_Y_M - 0.5
# Court-axis speed of a serve that reaches the other half (slowest float
# serve measured ~6.7 m/s; a lob back to the server ~4.5 m/s).
SERVE_MIN_SPEED_MS = 5.5
SERVE_MIN_TRAVEL_M = 5.0
# A serve into the net stops within this band around the net plane.
NET_ZONE_M = 2.5
# The online tracker locks ~0.2 s after a far serve leaves the hand.
FAR_SERVE_LOCK_DELAY_S = 0.2
# A serve stays in the air at least this long (into the net included) and is
# seen on at least this many frames; shorter "flights" are toss fragments.
SERVE_MIN_FLIGHT_S = 0.45
SERVE_MIN_SAMPLES = 6
# A ball that came from another touch this far away was passed, not tossed.
PASS_MIN_TRAVEL_M = 1.5
# A toss stays within this depth of where the track began.
TOSS_DEPTH_M = 2.0
# A hit after a tracked toss: image-plane velocity step (BallTimeline.impulse).
SERVE_HIT_IMPULSE_MS = 4.0

# -- rallies without a visible serve -------------------------------------- #
ORPHAN_MIN_TOUCHES = 4
ORPHAN_MIN_CROSSINGS = 2
ORPHAN_MIN_CROSS_M = 3.0
ORPHAN_SERVE_FLIGHT_S = 1.15      # typical serve flight (serve -> reception)
ORPHAN_SPLIT_BIAS_M = 1.3         # same depth split as touches.DEPTH_SPLIT_BIAS_M

# -- rally life ----------------------------------------------------------- #
# Shortest dead time between two points (retrieve the ball, walk back, serve;
# the owner's match never goes under 12 s).
MIN_DEAD_TIME_S = 5.0
# Longest a ball stays up between two touches (a 10 m lob hangs ~2.9 s).
MAX_AIR_S = 3.2
# Ball centre this low at a vertex is on the sand (radius 0.1 m + read noise).
GROUND_EVENT_HEIGHT_M = 0.6
# Below this the ball is ON the sand whatever it does next.
GROUND_CERTAIN_HEIGHT_M = 0.35
# A vertex below this followed by a ball that never leaves the sand again.
ROLL_START_HEIGHT_M = 1.0
# Sand kills a bounce: after touching it the ball never climbs back this high.
SAND_REBOUND_MAX_M = 1.3
# A flight with this many resting/skimming samples has hit the sand.
GROUND_FLIGHT_FRAMES = 4
# A ball that reappears mid-rally must be at least this high to still be live.
LIVE_MIN_PEAK_M = 1.5
# Net fault: a vertex this soon after the previous touch, at the net plane,
# at or below the tape, after which the ball only drops.
NET_FAULT_MAX_S = 0.8
NET_TAPE_SLACK_M = 0.25

END_GROUND = "ground"        # ball seen on the sand
END_NET = "net"              # ball stopped by the net
END_LOST = "lost"            # ball not seen again within air time


@dataclass
class ServeLaunch:
    frame: int                 # estimated contact frame
    side: str                  # serving side (near / far)
    event_index: int           # the launch event in ``timeline.events``
    observed: bool             # a contact vertex was seen (else track birth)
    into_net: bool = False
    inferred: bool = False     # no launch seen at all: the rally implies it


@dataclass
class RallyEnd:
    kind: str
    frame: int
    court_xy: Optional[Tuple[float, float]] = None   # where the ball died (m)
    side: Optional[str] = None       # half the ball died in (None = unknown)
    in_court: Optional[bool] = None  # ground ends only; None = too close to call


@dataclass
class Rally:
    serve: ServeLaunch
    touches: List[BallEvent] = field(default_factory=list)   # after the serve
    end: Optional[RallyEnd] = None

    @property
    def start_frame(self) -> int:
        return self.serve.frame

    @property
    def end_frame(self) -> int:
        return self.end.frame if self.end is not None else self.serve.frame


class RallySegmenter:
    def __init__(self, timeline: BallTimeline) -> None:
        self.tl = timeline
        self.stream = timeline.stream
        self.geometry = timeline.geometry
        self.net_height_m = timeline.geometry.net_top_height_m() or 2.43

    # -- serves ------------------------------------------------------------ #

    def find_serves(self) -> List[ServeLaunch]:
        serves: List[ServeLaunch] = []
        for i, e in enumerate(self.tl.events):
            launch = self._serve_launch(i, e)
            if launch is not None:
                serves.append(launch)
        return serves

    def _serve_launch(self, index: int, e: BallEvent) -> Optional[ServeLaunch]:
        fl = e.flight_out
        if fl is None or e.kind == EVENT_DEATH:
            return None
        if not np.isfinite(fl.peak_height_m) or fl.peak_height_m < SERVE_MIN_PEAK_M:
            return None
        if not fl.start_height_m <= SERVE_MAX_CONTACT_M:
            return None                     # nobody serves from up there
        if (fl.n < SERVE_MIN_SAMPLES
                or self.stream.seconds(fl.end - fl.start) < SERVE_MIN_FLIGHT_S):
            return None
        if self._fed_by_pass(index):
            return None                     # a teammate set it up: an attack
        fps = self.stream.fps
        speed = fl.axis_speed_ms(fps)
        travel = fl.y_end - fl.y_start
        if fl.y_start >= NEAR_SERVE_MIN_Y:
            side, toward_net = SIDE_NEAR, -1.0
        elif fl.y_start <= FAR_SERVE_MAX_Y:
            side, toward_net = SIDE_FAR, +1.0
        else:
            return None
        reaches = (toward_net * travel >= SERVE_MIN_TRAVEL_M
                   and toward_net * speed >= SERVE_MIN_SPEED_MS)
        # A serve that comes down at the net plane. Depth cannot tell the tape
        # from the first metre behind it; the serve that follows settles it.
        into_net = (toward_net * travel > 0
                    and abs(fl.y_end - NET_Y_M) <= NET_ZONE_M
                    and self._ends_on_ground(index))
        if not (reaches or into_net):
            return None
        frame, observed = e.frame, e.kind == EVENT_CONTACT
        if e.kind == EVENT_BIRTH:
            hit = self._hit_after_toss(fl)
            if hit is not None:
                frame, observed = hit, True
            else:
                # The online tracker locks a few frames after the hit. (When
                # it locked during the toss instead, this is early by the
                # rest of the toss -- measured within 15 frames, the owner
                # GT's own tolerance; image speed cannot tell a toss apex
                # from a serve flying straight at the lens.)
                frame = max(0, e.frame - self.stream.frames(FAR_SERVE_LOCK_DELAY_S))
        return ServeLaunch(frame=frame, side=side, event_index=index,
                           observed=observed, into_net=into_net)

    def _fed_by_pass(self, index: int) -> bool:
        """Did the ball reach this launch from ANOTHER touch a few metres
        away? A server tosses to himself (the ball stays on the spot, and a
        bounce routine before the toss stays there too); an attacker is fed
        by a pass. Only matters when a rally's own serve went unseen -- its
        first attack must not be taken for one."""
        events = self.tl.events
        e = events[index]
        arriving = e.flight_in
        if (e.kind != EVENT_CONTACT or arriving is None or index == 0
                or arriving.n < MIN_DEPTH_SAMPLES):
            return False
        feeder = events[index - 1]
        if feeder.kind != EVENT_CONTACT or feeder.frame != arriving.start:
            return False
        if self.stream.seconds(arriving.end - arriving.start) > MAX_AIR_S:
            return False
        if not (np.isfinite(feeder.u) and np.isfinite(e.u)):
            return False
        x0, y0, _ = self.geometry.ball_world(feeder.u, feeder.v, arriving.y_start)
        x1, y1, _ = self.geometry.ball_world(e.u, e.v, arriving.y_end)
        return float(np.hypot(x1 - x0, y1 - y0)) >= PASS_MIN_TRAVEL_M

    def _ends_on_ground(self, index: int) -> bool:
        """Does the flight leaving event ``index`` end with the ball down?"""
        events = self.tl.events
        fl = events[index].flight_out
        if fl is None:
            return False
        if fl.end_height_m <= GROUND_EVENT_HEIGHT_M:
            return True                 # last sample is at sand level
        if index + 1 >= len(events):
            return False
        nxt = events[index + 1]
        return nxt.kind == EVENT_CONTACT and self._is_ground_event(nxt)

    def _hit_after_toss(self, fl: Flight) -> Optional[int]:
        """Serve contact inside a birth flight whose toss was tracked."""
        window = self.stream.frames(1.2)
        best, best_frame = SERVE_HIT_IMPULSE_MS, None
        for f in range(fl.first + 2, min(fl.last - 2, fl.first + window)):
            # Only while the ball is still where it was tossed: further out
            # the image-plane step is perspective (a ball closing on the
            # lens speeds up in the picture without anyone touching it).
            y = self.tl.court_y[f]
            if not np.isfinite(y) or abs(y - fl.y_start) > TOSS_DEPTH_M:
                continue
            j = self.tl.impulse(f)
            if j is not None and j > best:
                best, best_frame = j, f
        return best_frame

    # -- rallies ----------------------------------------------------------- #

    def segment(self) -> List[Rally]:
        rallies: List[Rally] = []
        busy_until = -1
        events, s = self.tl.events, self.stream
        for serve in self.find_serves():
            if serve.frame <= busy_until:
                continue                    # a launch inside a live rally
            prev = rallies[-1] if rallies else None
            if prev is not None and s.seconds(
                    serve.frame - prev.end_frame) < MIN_DEAD_TIME_S:
                # Nobody retrieves the ball, walks to the baseline and serves
                # this fast: the "serve" is a deep pass of the SAME rally,
                # whose track broke for longer than a ball stays in the air.
                if prev.end is not None and prev.end.kind != END_LOST:
                    continue                # the ball was seen dead: stray throw
                tail = self._walk(serve)
                launch = events[serve.event_index]
                if launch.kind == EVENT_CONTACT:
                    prev.touches.append(launch)
                prev.touches.extend(tail.touches)
                prev.end = tail.end
                busy_until = prev.end_frame
                continue
            rally = self._walk(serve)
            rallies.append(rally)
            busy_until = rally.end_frame
        rallies.extend(self._orphan_rallies(rallies))
        rallies.sort(key=lambda r: r.start_frame)
        return rallies

    def _orphan_rallies(self, rallies: List[Rally]) -> List[Rally]:
        """Rallies whose serve was never seen (hidden, off-screen, or the
        video starts mid-point). Dead-time ball handling is a throw or two;
        only real play strings several touches together with the ball going
        over the net more than once."""
        events, s = self.tl.events, self.stream
        spans = [(r.start_frame, r.end_frame) for r in rallies]
        dead = s.frames(MIN_DEAD_TIME_S)
        found: List[Rally] = []
        busy_until = -1
        for i, e in enumerate(events):
            if e.kind != EVENT_BIRTH or e.frame <= busy_until:
                continue
            if any(a - dead <= e.frame <= b + dead for a, b in spans):
                continue
            first = next((ev for ev in events[i + 1:] if ev.kind == EVENT_CONTACT), None)
            if first is None:
                continue
            y = first.court_y()
            if y is None:
                continue
            reception = SIDE_NEAR if y > NET_Y_M + ORPHAN_SPLIT_BIAS_M else SIDE_FAR
            serve = ServeLaunch(
                frame=max(0, first.frame - s.frames(ORPHAN_SERVE_FLIGHT_S)),
                side=SIDE_FAR if reception == SIDE_NEAR else SIDE_NEAR,
                event_index=i, observed=False, inferred=True)
            rally = self._walk(serve)
            if any(a <= rally.end_frame and rally.start_frame <= b for a, b in spans):
                continue
            crossings = sum(
                1 for t in rally.touches
                if t.flight_out is not None and t.flight_out.crosses_net
                and t.flight_out.peak_height_m >= SERVE_MIN_PEAK_M
                and abs(t.flight_out.y_end - t.flight_out.y_start) >= ORPHAN_MIN_CROSS_M)
            if len(rally.touches) >= ORPHAN_MIN_TOUCHES and crossings >= ORPHAN_MIN_CROSSINGS:
                found.append(rally)
                busy_until = rally.end_frame
        return found

    def _walk(self, serve: ServeLaunch) -> Rally:
        events, s = self.tl.events, self.stream
        rally = Rally(serve=serve)
        launch = events[serve.event_index]
        prev, prev_frame = launch, serve.frame
        touch_frame = serve.frame           # last real hit (serve or touch)
        i = serve.event_index + 1
        while i < len(events):
            e = events[i]
            if e.kind == EVENT_DEATH:
                # The track broke. Play goes on if the ball is seen again, in
                # the air, before it could have come down (a touch hidden by
                # the player's body is the usual cause; the solver counts it).
                resume = self._resume_after(i)
                if resume is None:
                    rally.end = self._lost_end(e, prev)
                    return rally
                if resume < 0:
                    rally.end = self._ground_end(events[-resume].frame)
                    return rally
                # The air-time clock restarts where the ball reappears.
                prev_frame = events[resume].frame
                i = resume + 1
                continue
            if e.kind == EVENT_BIRTH:
                i += 1
                continue
            if s.seconds(e.frame - prev_frame) > MAX_AIR_S:
                rally.end = self._lost_end(e, prev, frame=prev_frame + s.frames(MAX_AIR_S))
                return rally
            arriving = e.flight_in
            if arriving is not None and arriving.ground_frames >= GROUND_FLIGHT_FRAMES:
                rally.end = self._ground_end(self._first_ground_frame(arriving) or e.frame)
                return rally
            if self._stays_down(e) or (
                    self._is_ground_event(e) and not self._play_follows(i)):
                rally.end = self._ground_end(e.frame)
                return rally
            if self._is_net_fault(e, touch_frame) and not self._play_follows(i):
                rally.end = RallyEnd(kind=END_NET, frame=e.frame,
                                     side=None, court_xy=None)
                return rally
            rally.touches.append(e)
            prev, prev_frame, touch_frame = e, e.frame, e.frame
            i += 1
        last = events[-1]
        rally.end = RallyEnd(kind=END_LOST, frame=last.frame)
        return rally

    # -- helpers ----------------------------------------------------------- #

    def _resume_after(self, index: int) -> Optional[int]:
        """Where play is seen again after the track death at ``index``.

        Returns the index of the first airborne re-sighting within air time,
        the NEGATED index of a re-sighting on the sand (the ball came down),
        or None when the ball is not seen in time.
        """
        events, s = self.tl.events, self.stream
        last_seen = events[index].frame
        for j in range(index + 1, len(events)):
            ev = events[j]
            if s.seconds(ev.frame - last_seen) > MAX_AIR_S:
                return None
            if ev.kind != EVENT_BIRTH:
                continue
            if self._starts_on_ground(ev):
                return -j
            if self._is_live(ev):
                return j
        return None

    def _height_at(self, e: BallEvent) -> Optional[float]:
        f = self.tl._nearest_tracked(e.frame, reach=self.stream.frames(0.4))
        if f is None:
            return None
        h = self.tl.height_m[f]
        return float(h) if np.isfinite(h) else None

    def _is_ground_event(self, e: BallEvent) -> bool:
        """A vertex at sand level whose rebound never climbs back up."""
        h = self._height_at(e)
        if h is None or h > GROUND_EVENT_HEIGHT_M:
            return False
        if h <= GROUND_CERTAIN_HEIGHT_M:
            return True                 # nobody plays a ball lying on the sand
        out = e.flight_out
        return out is None or not (out.peak_height_m > SAND_REBOUND_MAX_M)

    def _stays_down(self, e: BallEvent) -> bool:
        """A low vertex after which the ball only rolls: it landed there."""
        h = self._height_at(e)
        out = e.flight_out
        return (h is not None and out is not None and h <= ROLL_START_HEIGHT_M
                and out.peak_height_m <= ROLL_START_HEIGHT_M
                and out.ground_frames >= GROUND_FLIGHT_FRAMES)

    def _run_frames(self, frame: int) -> np.ndarray:
        """Tracked frames of the run that starts at ``frame``."""
        for a, b in self.tl.runs:
            if a == frame:
                idx = np.arange(a, b + 1)
                return idx[self.stream.tracked[idx]]
        return np.array([], dtype=int)

    def _starts_on_ground(self, birth: BallEvent) -> bool:
        """The reappearing ball lies / rolls on the sand."""
        idx = self._run_frames(birth.frame)
        if idx.size < GROUND_FLIGHT_FRAMES:
            return False                # a glimpse proves nothing
        head = idx[:max(GROUND_FLIGHT_FRAMES, self.stream.frames(0.5))]
        heights = self.tl.height_m[head]
        return (int(self.tl.grounded[head].sum()) >= GROUND_FLIGHT_FRAMES
                and float(np.nanmax(heights)) <= SAND_REBOUND_MAX_M)

    def _is_live(self, birth: BallEvent) -> bool:
        """A reappearing ball that is plausibly still in the rally: up in the
        air, not rolling or carried."""
        out = birth.flight_out
        if out is not None:
            return out.peak_height_m >= LIVE_MIN_PEAK_M
        idx = self._run_frames(birth.frame)
        heights = self.tl.height_m[idx] if idx.size else np.array([])
        heights = heights[np.isfinite(heights)]
        return bool(heights.size and heights.max() >= LIVE_MIN_PEAK_M
                    and not self.tl.grounded[idx].any())

    def _play_follows(self, index: int) -> bool:
        """Is there live play after event ``index`` (a later vertex reached by
        a real flight)? A dig can be at sand level; the ball death cannot be
        followed by a ball that climbs again."""
        events, s = self.tl.events, self.stream
        e = events[index]
        out = e.flight_out
        if out is None or not (out.peak_height_m > SAND_REBOUND_MAX_M):
            return False
        if out.ground_frames >= GROUND_FLIGHT_FRAMES:
            return False
        for j in range(index + 1, len(events)):
            nxt = events[j]
            if s.seconds(nxt.frame - e.frame) > MAX_AIR_S:
                return False
            if nxt.kind == EVENT_CONTACT:
                # ...and the ball is up again after THAT vertex too: a ball
                # dropping to the sand passes one more vertex on its way.
                after = nxt.flight_out
                return (not self._is_ground_event(nxt) and after is not None
                        and after.peak_height_m >= LIVE_MIN_PEAK_M
                        and after.ground_frames < GROUND_FLIGHT_FRAMES)
        return False

    def _is_net_fault(self, e: BallEvent, touch_frame: int) -> bool:
        """A vertex right after a hit, at the net plane and no higher than the
        tape, after which the ball only drops: the hit went into the net."""
        if self.stream.seconds(e.frame - touch_frame) > NET_FAULT_MAX_S:
            return False
        arriving, out = e.flight_in, e.flight_out
        if arriving is None or arriving.n < MIN_DEPTH_SAMPLES:
            return False                # no depth read: cannot place it at the net
        y = arriving.y_end
        h = self._height_at(e)
        if h is None or abs(y - NET_Y_M) > NET_ZONE_M:
            return False
        if h > self.net_height_m + NET_TAPE_SLACK_M:
            return False
        if out is None:
            return True
        return out.n >= MIN_DEPTH_SAMPLES and out.peak_height_m <= h + 0.3

    def _first_ground_frame(self, flight: Flight) -> Optional[int]:
        for f in range(flight.first, flight.last + 1):
            if self.tl.grounded[f]:
                return f
        return None

    def _ground_end(self, frame: int) -> RallyEnd:
        f = self.tl._nearest_tracked(frame)
        xy = self.tl.ground_world(f) if f is not None else None
        side = in_court = None
        if xy is not None:
            side, in_court = classify_landing(xy)
        return RallyEnd(kind=END_GROUND, frame=frame, court_xy=xy,
                        side=side, in_court=in_court)

    def _lost_end(self, e: BallEvent, prev: BallEvent,
                  frame: Optional[int] = None) -> RallyEnd:
        y = e.y_in if e.y_in is not None else prev.y_out
        side = None
        if y is not None and abs(y - NET_Y_M) > LANDING_NET_MARGIN_M:
            side = SIDE_NEAR if y > NET_Y_M else SIDE_FAR
        return RallyEnd(kind=END_LOST, frame=frame if frame is not None else e.frame,
                        side=side)


# Ground-plane landing calls. The 4-corner homography is ~0.3-0.5 m off at
# the far end and a ball's bottom point is read off a blurred box: only a
# landing this far from a line is called; closer ones stay undecided.
LANDING_LINE_MARGIN_M = 0.8
LANDING_NET_MARGIN_M = 1.5


def classify_landing(xy: Tuple[float, float]
                     ) -> Tuple[Optional[str], Optional[bool]]:
    """(side, in_court) of a ground-plane landing; None = too close to call."""
    x, y = xy
    side: Optional[str] = None
    if abs(y - NET_Y_M) > LANDING_NET_MARGIN_M:
        side = SIDE_NEAR if y > NET_Y_M else SIDE_FAR
    m = LANDING_LINE_MARGIN_M
    inside = (m <= x <= COURT_WIDTH_M - m) and (m <= y <= COURT_LENGTH_M - m)
    outside = (x < -m or x > COURT_WIDTH_M + m or y < -m or y > COURT_LENGTH_M + m)
    in_court: Optional[bool] = True if inside else (False if outside else None)
    return side, in_court
