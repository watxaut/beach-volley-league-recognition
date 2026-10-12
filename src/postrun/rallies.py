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
from typing import Dict, List, Optional, Tuple

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
from .geometry import (
    BALL_DIAMETER_M,
    COURT_LENGTH_M,
    COURT_WIDTH_M,
    NET_Y_M,
    SIDE_FAR,
    SIDE_NEAR,
)
from .stream import BALL_TRACKED

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

# -- reception formation --------------------------------------------------- #
# A team waiting for a serve stands side by side; a team about to SERVE has
# one player on the way to the line and the other up the court. A ball sent
# over to them between points flies like a serve (it can even start behind
# the baseline, where it was fetched) but lands on a staggered pair that does
# not play it. Depth between the two receivers, measured at every serve with
# both of them read (20260920 + 20261010 + practice clips, 52 serves):
# <= 0.84 m at 51 of them and 1.37 m in one drill (played on, six touches);
# the ball sent back on 20261010: 2.2 m.
FORMATION_MAX_STAGGER_M = 1.5
# Where each receiver stood over this long before the launch, seen at least
# FORMATION_MIN_SEEN_S of it ...
FORMATION_WINDOW_S = 0.6
FORMATION_MIN_SEEN_S = 0.15
# ... and only when the ground read of the feet is this good (the far half of
# a low camera is not: +-0.7-0.9 m on the beach, where nothing is refused).
FORMATION_MAX_READ_ERR_M = 0.5
# Feet this close to the net line may belong to either half (a player at the
# net projects across it): not a receiver.
FORMATION_NET_CLEAR_M = 1.0
# A launch the other half answers with this many touches was played: it is
# a serve wherever the receivers stood.
PLAYED_MIN_TOUCHES = 2
REFUSED_FORMATION = "receivers_not_in_formation"
CONFIRMED_FORMATION = "formation"

# -- a still court ---------------------------------------------------------- #
# Owner's observation (2026-10-11): at a serve everybody but the server stands
# still -- the receivers wait in formation, the partner at the net -- while in
# a rally, and when a ball is passed around between points, bodies move. Read
# as how far the feet of the third-stillest body strayed from their own median
# spot over the two seconds before the launch, in that body's own heights
# (scale-free: far players are small). On 20260920 and the three 20261010
# videos: <= 0.10 before 114 of 138 serves (83 %) and before 1 of 211 attacks
# (a serve sent straight back by its receiver); <= 0.15: 89 % / 3 attacks.
# So a still court CONFIRMS a serve the ball alone leaves open; a court that
# is not still refuses nothing (one serve in six is read with somebody
# walking or a box flickering).
STILL_WINDOW_S = 2.0
# The launch frame is an estimate, and the receivers move as the ball is hit.
STILL_LEAD_S = 0.2
STILL_MAX_SWAY = 0.10               # body heights
STILL_MIN_SEEN = 0.5                # of the window, as a real (not coasting) box
STILL_BODIES = 3                    # everybody but the server
CONFIRMED_STILL = "still_court"

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
# A ball still coming down this fast in the picture (in its own scale) has not
# landed: a 0.5 m drop arrives at 3 m/s, a ball rolling on the sand moves a
# fraction of that across the image rows.
LANDED_MAX_FALL_MS = 1.5
# A flight "followed all the way": tracked on this share of its frames.
SEEN_TO_NEXT_SHARE = 0.7
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
    #: What let a launch the ball alone leaves open through (None: nothing
    #: was needed) -- see ``RallySegmenter.court_sway``.
    confirmed_by: Optional[str] = None


@dataclass
class RallyEnd:
    kind: str
    frame: int
    court_xy: Optional[Tuple[float, float]] = None   # where the ball died (m)
    court_xy_err: Optional[Tuple[float, float]] = None   # (across, along) m it may be off
    pos_xy: Optional[Tuple[float, float]] = None       # the same spot as the maps draw
    pos_xy_err: Optional[Tuple[float, float]] = None   # it (``positions``, net-anchored)
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


@dataclass
class RefusedLaunch:
    """A launch that flew like a serve and was not taken for one."""

    frame: int
    side: str
    reason: str
    stagger_m: float


class RallySegmenter:
    def __init__(self, timeline: BallTimeline) -> None:
        self.tl = timeline
        self.stream = timeline.stream
        self.geometry = timeline.geometry
        self.net_height_m = timeline.geometry.net_top_height_m() or 2.43
        #: Filled by ``segment``: serve-shaped launches refused, for the report.
        self.refused: List[RefusedLaunch] = []

    # -- serves ------------------------------------------------------------ #

    def find_serves(self) -> List[ServeLaunch]:
        serves: List[ServeLaunch] = []
        for i, e in enumerate(self.tl.events):
            launch = self._serve_launch(i, e)
            if launch is not None:
                serves.append(launch)
        return serves

    def _serve_past_the_frame(self, index: int, e: BallEvent) -> Optional[ServeLaunch]:
        """A serve whose hit was not seen because the ball left the picture:
        the track of a toss beside a baseline dies, and the ball is next seen
        already on its way to the other half, where a serve hit at the end of
        that toss would be. (A high tripod cuts the top of a near serve.)"""
        events, s = self.tl.events, self.stream
        fl = e.flight_out
        if e.kind != EVENT_BIRTH or fl is None or index < 2:
            return None
        death, toss_birth = events[index - 1], events[index - 2]
        # The hit itself may have been seen, as a vertex, a frame or two
        # before the ball was gone.
        hit: Optional[BallEvent] = None
        if toss_birth.kind == EVENT_CONTACT and index >= 3:
            hit, toss_birth = toss_birth, events[index - 3]
        toss = toss_birth.flight_out
        launch = death.frame if hit is None else hit.frame
        if (death.kind != EVENT_DEATH or toss_birth.kind != EVENT_BIRTH or toss is None
                or toss.end != launch or toss.n < SERVE_MIN_SAMPLES):
            return None
        gap = s.seconds(e.frame - launch)
        if not 0 < gap <= MAX_AIR_S or abs(toss.y_end - toss.y_start) > TOSS_DEPTH_M:
            return None
        # What the ball shows without help: a toss AT a baseline whose track
        # dies, and a flight past the net fast enough to be measured. Anything
        # short of that needs the court to say "serve" too (``court_sway``).
        firm_toss = True
        if toss.y_end >= NEAR_SERVE_MIN_Y:
            side, toward_net = SIDE_NEAR, -1.0
        elif toss.y_end <= 0.0:
            side, toward_net = SIDE_FAR, +1.0
        elif toss.y_end <= FAR_SERVE_MAX_Y:
            # 2 px of ball width is ~2 m at the far end: a far toss reads up
            # to 4 m inside the court (as a far launch does, FAR_SERVE_MAX_Y).
            side, toward_net, firm_toss = SIDE_FAR, +1.0, False
        else:
            return None
        firm = firm_toss and hit is None
        # From the toss to where the ball is seen again, and on from there,
        # at serve speed and to the other half.
        hidden = toward_net * (fl.y_start - toss.y_end)
        if hidden <= 0 or hidden / gap < SERVE_MIN_SPEED_MS:
            return None
        if (toward_net * (fl.y_end - toss.y_end) < SERVE_MIN_TRAVEL_M
                or toward_net * (fl.y_end - NET_Y_M) <= 0):
            return None
        if toward_net * fl.axis_speed_ms(s.fps) < SERVE_MIN_SPEED_MS:
            # Seen again too briefly to carry a speed. Any ball glimpsed past
            # the net would do (another court's, a spare one): only the one
            # seen INSIDE the court as it is received, after a toss placed
            # without doubt.
            receivers_line = 0.0 if side == SIDE_NEAR else COURT_LENGTH_M
            nxt = events[index + 1] if index + 1 < len(events) else None
            if (fl.n >= SERVE_MIN_SAMPLES or not firm_toss
                    or nxt is None or nxt.kind != EVENT_CONTACT
                    or toward_net * (fl.y_start - receivers_line) > TOSS_DEPTH_M):
                return None
            firm = False
        if not firm and not self._court_still(launch):
            return None
        return ServeLaunch(frame=launch, side=side, event_index=index,
                           observed=hit is not None,
                           confirmed_by=None if firm else CONFIRMED_STILL)

    def _serve_at_the_tape(self, index: int, e: BallEvent) -> Optional[ServeLaunch]:
        """A serve whose whole flight went unseen and whose ball is first
        picked up AT the tape, above what the sand can send up, moving away
        from the net and down onto the other half: a net-cord serve (the far
        ball is a few pixels wide, and the cord kills its speed). Nothing in
        the ball says "serve" there -- it is a slow ball a metre past the
        net -- so only a STILL COURT lets it through, never the ball alone."""
        fl = e.flight_out
        if e.kind != EVENT_BIRTH or fl is None:
            return None
        if (fl.n < SERVE_MIN_SAMPLES
                or self.stream.seconds(fl.end - fl.start) < SERVE_MIN_FLIGHT_S
                or abs(fl.y_start - NET_Y_M) > NET_ZONE_M
                or not fl.start_height_m >= LIVE_MIN_PEAK_M):
            return None
        toward_net = 1.0 if fl.y_end > fl.y_start else -1.0
        if toward_net * (fl.y_end - NET_Y_M) <= 0 or not (
                self._ends_on_ground(index) or self._received(index)):
            return None                     # it never got past the tape / was not dropped
        if not self._court_still(e.frame):
            return None
        side = SIDE_FAR if toward_net > 0 else SIDE_NEAR
        hit = max(0, e.frame - self.stream.frames(ORPHAN_SERVE_FLIGHT_S / 2))
        return ServeLaunch(frame=hit, side=side, event_index=index, observed=False,
                           confirmed_by=CONFIRMED_STILL)

    def _serve_launch(self, index: int, e: BallEvent) -> Optional[ServeLaunch]:
        fl = e.flight_out
        if fl is None or e.kind == EVENT_DEATH:
            return None
        past = self._serve_past_the_frame(index, e)
        if past is not None:
            return past
        by_flight = self._serve_by_flight(index, e)
        if by_flight is not None:
            return by_flight
        # Last resort, after the flight itself said "not a serve".
        return self._serve_at_the_tape(index, e)

    def _serve_by_flight(self, index: int, e: BallEvent) -> Optional[ServeLaunch]:
        fl = e.flight_out
        fl = self._airborne(fl)
        if not np.isfinite(fl.peak_height_m) or fl.peak_height_m < SERVE_MIN_PEAK_M:
            return None
        if not fl.start_height_m <= SERVE_MAX_CONTACT_M:
            return None                     # nobody serves from up there
        if (fl.n < SERVE_MIN_SAMPLES
                or self.stream.seconds(fl.end - fl.start) < SERVE_MIN_FLIGHT_S):
            return None
        confirmed: Optional[str] = None
        if self._fed_by_pass(index):
            if not self._own_toss(index):
                return None                 # a teammate set it up: an attack
            confirmed = CONFIRMED_STILL
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
        at_net = toward_net * travel > 0 and abs(fl.y_end - NET_Y_M) <= NET_ZONE_M
        into_net = at_net and self._ends_on_ground(index)
        if not (reaches or into_net):
            # ... or that the tape stops and drops, on either side of the net
            # (the ball gets there slower than a serve that clears it).
            if (at_net and self._dropped_by_the_tape(index)
                    and self._court_still(e.frame)):
                into_net, confirmed = True, CONFIRMED_STILL
            elif (toward_net * travel >= SERVE_MIN_TRAVEL_M and toward_net * speed > 0
                    and toward_net * (fl.y_end - NET_Y_M) > 0 and not at_net   # over the tape, and past it
                    and self._lob_to_a_formation(index, e.frame, side)):
                confirmed = CONFIRMED_FORMATION
            else:
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
                           observed=observed, into_net=into_net,
                           confirmed_by=confirmed)

    def _airborne(self, fl: Flight) -> Flight:
        """``fl`` up to where the ball reached the sand. A ball that lies
        where it fell is still tracked: one line through the flight AND the
        rest reads neither end (a serve into the net from the near baseline
        read as leaving 2 m inside the court at 4 m/s)."""
        if fl.ground_frames < GROUND_FLIGHT_FRAMES:
            return fl
        landed = self._landing_frame(fl, fl.end)
        if landed is None or landed >= fl.end:
            return fl
        return self.tl.fit_span(fl.start, landed) or fl

    def _received(self, index: int) -> bool:
        """Does the flight leaving event ``index`` end in a touch (a dig)?"""
        events = self.tl.events
        if index + 1 >= len(events):
            return False
        nxt = events[index + 1]
        return nxt.kind == EVENT_CONTACT and nxt.accepted

    def _lob_to_a_formation(self, index: int, frame: int, side: str) -> bool:
        """A slow serve (a lob, 4-5 m/s: not a ball sent back to the server,
        which lands on a team that is not waiting): it reaches the other half
        over the tape, the two receivers stand side by side as for a serve
        (both read, ``FORMATION_MAX_STAGGER_M``) and play goes on."""
        stagger = self._receivers_stagger_m(
            ServeLaunch(frame=frame, side=side, event_index=index, observed=False))
        return (stagger is not None and stagger <= FORMATION_MAX_STAGGER_M
                and self._play_follows(index))

    def _own_toss(self, index: int) -> bool:
        """Is the "pass" that reached this launch the server's own toss? It
        stayed on his half, and nobody around him moved: a jump serve is
        tossed forward, along the axis the far end cannot measure, and a toss
        tracked in two pieces can be joined to a ball seen elsewhere."""
        e = self.tl.events[index]
        toss = e.flight_in
        return (toss is not None and not toss.crosses_net
                and self._court_still(e.frame))

    def _dropped_by_the_tape(self, index: int) -> bool:
        """Does the flight leaving event ``index`` end AT the net, at or under
        the tape, the ball then falling to the sand untouched?"""
        events = self.tl.events
        if index + 1 >= len(events):
            return False
        nxt = events[index + 1]
        return (nxt.kind == EVENT_CONTACT and self._at_the_tape(nxt)
                and self._ends_on_ground(index + 1))

    # -- a still court ------------------------------------------------------ #

    def court_sway(self, frame: int) -> Optional[float]:
        """How still the court was before ``frame``: the p90 distance of the
        feet of the third-stillest body from their own median spot, in body
        heights (None: fewer than three bodies were seen long enough)."""
        s = self.stream
        hi = min(frame - s.frames(STILL_LEAD_S), s.n_frames - 1)
        lo = max(0, hi - s.frames(STILL_WINDOW_S))
        if hi <= lo:
            return None
        seen: Dict[int, List[Tuple[float, float, float]]] = {}
        for f in range(lo, hi + 1):
            for p in s.players[f]:
                if not p.predicted:
                    seen.setdefault(p.track_id, []).append((*p.foot, p.height_px))
        sways: List[float] = []
        for rows in seen.values():
            if len(rows) < STILL_MIN_SEEN * (hi - lo + 1):
                continue
            u, v, h = (np.asarray(c, dtype=np.float64) for c in zip(*rows))
            height = float(np.median(h))
            if height <= 0:
                continue
            off = np.hypot(u - np.median(u), v - np.median(v)) / height
            sways.append(float(np.percentile(off, 90)))
        if len(sways) < STILL_BODIES:
            return None
        return sorted(sways)[STILL_BODIES - 1]

    def _court_still(self, frame: int) -> bool:
        sway = self.court_sway(frame)
        return sway is not None and sway <= STILL_MAX_SWAY

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
        if feeder.flight_in is None or feeder.flight_in.n < MIN_DEPTH_SAMPLES:
            # A pass reaches its toucher: the ball was seen coming. A "touch"
            # the ball reached in fewer samples than a depth read needs is the
            # first sight of the ball -- a toss released at the server's hand
            # (20261010_1230 f41851: tracked 5 frames before the hit).
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
        self.refused = []
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
                if (s.seconds(serve.frame - prev.end_frame) > MAX_AIR_S
                        and len(tail.touches) < PLAYED_MIN_TOUCHES):
                    # ... or the ball going back to whoever serves next: it
                    # came after the rally's ball had to be down, and nobody
                    # played it. (Merged, its landing would be read as the
                    # landing of the rally's last attack.)
                    continue
                launch = events[serve.event_index]
                if launch.kind == EVENT_CONTACT:
                    prev.touches.append(launch)
                prev.touches.extend(tail.touches)
                prev.end = tail.end
                busy_until = prev.end_frame
                continue
            rally = self._walk(serve)
            busy_until = rally.end_frame
            stagger = self._receivers_stagger_m(serve)
            if (stagger is not None and stagger > FORMATION_MAX_STAGGER_M
                    and len(rally.touches) < PLAYED_MIN_TOUCHES):
                # Sent over to a team that was not waiting for a serve and
                # did not play it: the ball going back between two points.
                self.refused.append(RefusedLaunch(
                    frame=serve.frame, side=serve.side, reason=REFUSED_FORMATION,
                    stagger_m=stagger))
                continue
            rallies.append(rally)
        rallies.extend(self._orphan_rallies(rallies))
        rallies.sort(key=lambda r: r.start_frame)
        return rallies

    def _receivers_stagger_m(self, serve: ServeLaunch) -> Optional[float]:
        """Depth between the two receivers when the ball is launched (None:
        they cannot both be read). The receivers are the two bodies deepest
        in the other half; a third one at the net is the serving team's."""
        s, g = self.stream, self.geometry
        receiving_near = serve.side == SIDE_FAR
        last = min(serve.frame, s.n_frames - 1)
        feet: Dict[int, List[Tuple[float, float]]] = {}
        for f in range(max(0, last - s.frames(FORMATION_WINDOW_S)), last + 1):
            for p in s.players[f]:
                xy = None if p.predicted else g.foot_world(p.bbox)
                if xy is not None:
                    feet.setdefault(p.track_id, []).append(xy)
        depths: List[float] = []
        for seen in feet.values():
            if len(seen) < max(2, s.frames(FORMATION_MIN_SEEN_S)):
                continue
            x, y = (float(np.median(v)) for v in zip(*seen))
            depth = abs(y - NET_Y_M)
            if (y > NET_Y_M) != receiving_near or depth < FORMATION_NET_CLEAR_M:
                continue
            err = g.ground_read_error_m(*g.world_to_image(x, y))
            if err is not None and err[1] <= FORMATION_MAX_READ_ERR_M:
                depths.append(depth)
        if len(depths) < 2:
            return None
        depths.sort(reverse=True)
        return depths[0] - depths[1]

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
            if arriving is not None and arriving.landed_frames >= GROUND_FLIGHT_FRAMES:
                rally.end = self._ground_end(self._landing_frame(arriving, e.frame) or e.frame)
                return rally
            if self._stays_down(e) or (
                    self._is_ground_event(e) and not self._play_follows(i)):
                rally.end = self._ground_end(e.frame, arriving)
                return rally
            # (A serve takes longer to reach the net than an attack: the
            # vertex that made it a serve into the net is that net.)
            net = self._is_net_fault(e, touch_frame) or (
                serve.into_net and i == serve.event_index + 1 and self._at_the_tape(e))
            if net and not self._play_follows(i):
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
        if out is None or out.landed_frames >= GROUND_FLIGHT_FRAMES:
            return False
        if not (out.peak_height_m > SAND_REBOUND_MAX_M) and not self._seen_to_next(index):
            # No higher than sand sends a ball, and lost on the way: a bounce.
            # (Followed all the way to the next vertex without coming to
            # rest, it is a low pass to the partner -- what he does with it
            # decides, below.)
            return False
        for j in range(index + 1, len(events)):
            nxt = events[j]
            if s.seconds(nxt.frame - e.frame) > MAX_AIR_S:
                return False
            if nxt.kind == EVENT_CONTACT:
                # ...and the ball is up again after a LATER vertex too: a ball
                # dropping to the sand passes one more vertex on its way and
                # then only rolls, while a rally keeps sending it up (a short
                # low flight between two touches is not the end of it).
                after = nxt.flight_out
                if after is None or after.ground_frames >= GROUND_FLIGHT_FRAMES:
                    return False
                if after.peak_height_m >= LIVE_MIN_PEAK_M:
                    return True
        return False

    def _seen_to_next(self, index: int) -> bool:
        """Was the ball tracked from event ``index`` right up to the next
        vertex (most of the frames in between)?"""
        events = self.tl.events
        out = events[index].flight_out
        if out is None or index + 1 >= len(events):
            return False
        nxt = events[index + 1]
        return (nxt.kind == EVENT_CONTACT and out.end == nxt.frame
                and out.n >= SEEN_TO_NEXT_SHARE * (out.end - out.start))

    def _is_net_fault(self, e: BallEvent, touch_frame: int) -> bool:
        """A vertex right after a hit, at the net plane and no higher than the
        tape, after which the ball only drops: the hit went into the net."""
        if self.stream.seconds(e.frame - touch_frame) > NET_FAULT_MAX_S:
            return False
        return self._at_the_tape(e)

    def _at_the_tape(self, e: BallEvent) -> bool:
        """A vertex at the net plane, no higher than the tape, after which the
        ball does not climb."""
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

    def _landing_frame(self, flight: Flight, until: int) -> Optional[int]:
        """Frame the ball of ``flight`` reaches the sand (None: never seen on it).

        The width test fires while the ball is still coming down: a falling
        ball lines up with sand well behind where it will land, and for a
        frame or two its width fits that sand as well. Read there, a landing
        is metres too deep (a cut shot inside the line reads behind the
        baseline). The ball is down where it stops falling."""
        s = self.stream
        frames = [f for f in range(flight.first, min(until, s.n_frames - 1) + 1)
                  if s.ball_state[f] == BALL_TRACKED]
        # A ball dug at sand level is low for a frame or two as it LEAVES:
        # once it has climbed higher than sand can send it, those are behind.
        up = next((i for i, f in enumerate(frames)
                   if self.tl.height_m[f] > SAND_REBOUND_MAX_M), 0)
        first = next((i for i, f in enumerate(frames)
                      if i >= up and self.tl.grounded[f]), None)
        if first is None:
            return None
        landed = frames[first]
        for a, b in zip(frames[first:], frames[first + 1:]):
            px_per_m = s.ball_w[a] / BALL_DIAMETER_M
            fall = (s.ball_bbox[b, 3] - s.ball_bbox[a, 3]) / (b - a) * s.fps / px_per_m
            if not fall >= LANDED_MAX_FALL_MS:
                break
            landed = b
        return landed

    def _ground_end(self, frame: int, arriving: Optional[Flight] = None) -> RallyEnd:
        f = self.tl._nearest_tracked(frame)
        if f is None and arriving is not None:
            # A vertex read in a tracking gap has no ball of its own: the
            # flight that reached it shows where the ball came down.
            f = self._landing_frame(arriving, frame)
        xy = self.tl.ground_world(f) if f is not None else None
        side = in_court = err = None
        if xy is not None:
            side, in_court = classify_landing(xy)
            err = self.tl.ground_world_error(f)
        return RallyEnd(kind=END_GROUND, frame=frame, court_xy=xy, court_xy_err=err,
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
