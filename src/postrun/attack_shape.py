"""Attack shape: was the ball DRIVEN (hard) or PLACED (touch)?

The causal ``SpikeAnalyzer`` decides this from how many image pixels the ball
rises after the contact. That is a pixel rule (AGENTS.md §7: venue-coupled)
and, on a long-axis camera, a depth-blind one: a ball above the lens climbs
in the picture just by flying toward it. Here the same question is asked of
the flight in METRES and SECONDS:

* the flight from the attack to whatever stops it (the next touch, the sand,
  the end of the track) is ballistic, so with gravity known the heights give
  the VERTICAL launch speed. It is the well-measured number: three ways of
  reading the depth agree on it within 0.2 m/s;
* the HORIZONTAL speed is the weak one, because most of it is depth (ball
  width) and a ball flying away from the lens is seen through the net, where
  the box under-reads its width. So it is read twice -- from the width trend
  over the flight, and from where the attack and the next touch happened --
  and a type is given only when both reads say the same.

A lofted ball (launch elevation at or above ``LOFT_ANGLE_DEG``) was placed
whatever its speed; so was a ball that left slowly. Everything else was
driven. Owner rule (AGENTS.md §11): no type is better than a wrong one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence

import numpy as np

from .ball_flights import BallTimeline, _theil_sen_slope
from .stream import BALL_TRACKED
from .touches import ACTION_OVERPASS, ACTION_SPIKE, Touch

TYPE_HARD = "hard"
TYPE_TOUCH = "touch"
ATTACK_ACTIONS = (ACTION_SPIKE, ACTION_OVERPASS)

GRAVITY_MS2 = 9.81
# Launch elevation that splits a drive from a lob. Measured (20260920 + the
# practice clips, 37 owner-typed attacks with a launch): 13 of 15 drives
# leave below 24 deg, 19 of 22 placed balls at 26 deg or above; any split in
# 24-26 scores the same. The classes overlap for real between ~19 and ~31 deg
# (a third way of reading depth, gravity as the ruler, puts the same attacks
# there), so this is not a number to tune further on the same labels.
LOFT_ANGLE_DEG = 25.0
# A ball that leaves slower than this was placed, however flat (a drop just
# over the tape, 1.8 m/s on the match). The slowest owner-typed drive leaves
# at 6.2 m/s; anything from 3 to 6 scores the same.
PLACED_SPEED_MS = 5.0
# The classifier dates a vertex a few frames before the picture shows the
# turn; the hit is where the image velocity steps most inside this window
# (seconds before, after the vertex).
CONTACT_SEARCH_S = (0.08, 0.25)
# A flight shorter than this reads no launch (a joust, a ball lost at the hit).
MIN_FLIGHT_SAMPLES = 5
MIN_FLIGHT_S = 0.15


@dataclass
class AttackLaunch:
    """How the ball left one attack (metres, seconds)."""

    frame: int                      # the hit (refined vertex)
    samples: int                    # tracked frames behind the fit
    rise_ms: float                       # vertical launch speed, + = upward
    horizontal_ms: float                 # depth from the width trend
    horizontal_ends_ms: Optional[float]  # attack position -> next touch

    @property
    def elevation_deg(self) -> float:
        return _elevation(self.rise_ms, self.horizontal_ms)

    @property
    def elevation_ends_deg(self) -> Optional[float]:
        if self.horizontal_ends_ms is None:
            return None
        return _elevation(self.rise_ms, self.horizontal_ends_ms)

    @property
    def speed_ms(self) -> float:
        return math.hypot(self.rise_ms, self.horizontal_ms)

    def spike_type(self) -> Optional[str]:
        """``hard`` / ``touch``, or None when the two speed reads disagree."""
        reads = {_read(self.rise_ms, self.horizontal_ms)}
        if self.horizontal_ends_ms is not None:
            reads.add(_read(self.rise_ms, self.horizontal_ends_ms))
        return reads.pop() if len(reads) == 1 else None


def _elevation(rise_ms: float, horizontal_ms: float) -> float:
    return math.degrees(math.atan2(rise_ms, horizontal_ms))


def _read(rise_ms: float, horizontal_ms: float) -> str:
    if math.hypot(rise_ms, horizontal_ms) < PLACED_SPEED_MS:
        return TYPE_TOUCH
    return TYPE_TOUCH if _elevation(rise_ms, horizontal_ms) >= LOFT_ANGLE_DEG else TYPE_HARD


def hit_frame(timeline: BallTimeline, vertex: int) -> int:
    """Frame of the largest image-velocity step around a classifier vertex."""
    s = timeline.stream
    before, after = (s.frames(x) for x in CONTACT_SEARCH_S)
    best, best_step = vertex, -1.0
    for f in range(vertex - before, vertex + after + 1):
        step = timeline.impulse(f, span=2)
        if step is not None and step > best_step:
            best, best_step = f, step
    return best


def flight_frames(timeline: BallTimeline, hit: int) -> np.ndarray:
    """Tracked, unclipped frames between the hit and whatever stops the ball
    (the next event, or its first frame on the sand)."""
    s = timeline.stream
    stop = next((e.frame for e in timeline.events if e.frame > hit + 2), s.n_frames)
    idx = np.arange(hit + 1, min(stop, s.n_frames))
    ok = idx[(s.ball_state[idx] == BALL_TRACKED) & np.isfinite(timeline.inv_w[idx])
             & ~timeline.clipped[idx]]
    down = ok[timeline.grounded[ok]]
    return ok[ok < down[0]] if down.size else ok


def launch_of(timeline: BallTimeline, touch: Touch,
              next_touch: Optional[Touch] = None) -> Optional[AttackLaunch]:
    """Launch of the ball off ``touch``; None when the flight is too short."""
    s, g = timeline.stream, timeline.geometry
    hit = hit_frame(timeline, touch.frame)
    ok = flight_frames(timeline, hit)
    if ok.size < MIN_FLIGHT_SAMPLES:
        return None
    t = (ok - hit) / s.fps
    if t[-1] - t[0] < MIN_FLIGHT_S:
        return None
    # Depth: one robust line through 1 / width (constant court-axis speed).
    z = timeline.inv_w[ok]
    slope = _theil_sen_slope(t, z)
    inv = np.maximum(float(np.median(z - slope * t)) + slope * t,
                     1.0 / (4.0 * g.ball_px_near))
    court_y = g.court_y_from_width(1.0 / inv)
    world = np.array([g.ball_world(s.ball_xy[f, 0], s.ball_xy[f, 1], float(y))
                      for f, y in zip(ok, court_y)])
    line = np.vstack([np.ones_like(t), t]).T
    (_, vx), *_ = np.linalg.lstsq(line, world[:, 0], rcond=None)
    # Height is ballistic: h + g t^2 / 2 is a line whose slope is the launch.
    (_, vz), *_ = np.linalg.lstsq(line, world[:, 2] + 0.5 * GRAVITY_MS2 * t * t, rcond=None)
    vy = (court_y[-1] - court_y[0]) / (t[-1] - t[0])
    return AttackLaunch(
        frame=int(hit), samples=int(ok.size), rise_ms=float(vz),
        horizontal_ms=float(math.hypot(vx, vy)),
        horizontal_ends_ms=_speed_between(touch, next_touch, s.fps))


def _speed_between(touch: Touch, nxt: Optional[Touch], fps: float) -> Optional[float]:
    """Horizontal speed from where the attack was hit to where the ball was
    next touched. A landing is not used: its depth is the layer's weak read."""
    if nxt is None or not nxt.observed:
        return None
    if None in (touch.court_x, touch.court_y, nxt.court_x, nxt.court_y):
        return None
    seconds = (nxt.frame - touch.frame) / fps
    if seconds < MIN_FLIGHT_S:
        return None
    return math.hypot(nxt.court_x - touch.court_x, nxt.court_y - touch.court_y) / seconds


def type_attacks(timeline: BallTimeline, touches: Sequence[Touch]) -> List[Touch]:
    """Stamp ``launch`` and ``spike_type`` on the observed attacks of one
    rally; returns the touches it typed."""
    typed = []
    for i, t in enumerate(touches):
        if t.action not in ATTACK_ACTIONS or not t.observed:
            continue
        nxt = touches[i + 1] if i + 1 < len(touches) else None
        t.launch = launch_of(timeline, t, nxt)
        t.spike_type = t.launch.spike_type() if t.launch is not None else None
        if t.spike_type is not None:
            typed.append(t)
    return typed
