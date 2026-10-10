"""Synthetic match stream for the post-run tests (helper, not a test module).

A rally is scripted in COURT METRES (who touches the ball, where, when) and
rendered through the same pinhole model ``src/postrun/geometry`` inverts: a
ball at (x, court_y, height) shows up at the pixel and with the width the
geometry predicts, flying ballistic arcs between touches. The stream then
looks like what the causal pass leaves behind: a tracked ball, the vertices
the classifier found, four labelled players.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.postrun.geometry import CourtGeometry
from src.postrun.stream import (
    BALL_TRACKED,
    ContactCandidate,
    MatchStream,
    PlayerObs,
)

FPS = 30.0
# The 20260920 match calibration (beach venue).
CORNERS = [[714, 597], [1277, 585], [1793, 774], [3, 791]]
NET_TOP = [[558, 384], [1467, 369]]

#: label -> (court_x, court_y) where the player stands; squad 1 = A.
NEAR_A = {"P1A": (2.5, 11.0), "P2A": (5.5, 11.0), "P1B": (2.5, 5.0), "P2B": (5.5, 5.0)}
#: After a side switch squad B is near.
NEAR_B = {"P1B": (2.5, 11.0), "P2B": (5.5, 11.0), "P1A": (2.5, 5.0), "P2A": (5.5, 5.0)}

DIG_Z, SET_Z, SPIKE_Z, SERVE_Z = 0.9, 1.7, 2.8, 2.6
PLAYER_HEIGHT_M = 1.85


def geometry() -> CourtGeometry:
    return CourtGeometry(CORNERS, NET_TOP)


@dataclass
class Hit:
    """One contact: seconds after the previous hit, by whom, how high."""

    dt: float
    player: Optional[str]            # None = nobody (the serve position is given)
    z: float
    xy: Optional[Tuple[float, float]] = None
    seen: bool = True                # the classifier found the vertex
    accepted: bool = True


@dataclass
class RallyScript:
    start_s: float
    serve_xy: Tuple[float, float]            # where the server hits it
    hits: List[Hit]
    landing: Tuple[float, float]             # where the ball comes down (m)
    landing_dt: float = 0.9
    positions: Dict[str, Tuple[float, float]] = field(default_factory=lambda: dict(NEAR_A))
    far_lock_delay: int = 5                  # frames the tracker needs on a far serve
    toss_frames: int = 12                    # tracked toss before a near serve
    heights: Dict[str, float] = field(default_factory=dict)   # label -> metres (else 1.85)


class StreamBuilder:
    def __init__(self, seconds: float) -> None:
        self.g = geometry()
        n = int(seconds * FPS)
        self.n = n
        self.state = np.zeros(n, dtype=np.int8)
        self.xy = np.full((n, 2), np.nan)
        self.bbox = np.full((n, 4), np.nan)
        self.players: List[List[PlayerObs]] = [[] for _ in range(n)]
        self.candidates: List[ContactCandidate] = []

    # -- rendering -------------------------------------------------------- #

    def project(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        scale = float(self.g.px_per_metre(y))
        uc, vg = self.g.world_to_image(4.0, y)
        return uc + (x - 4.0) * scale, vg - z * scale, float(self.g.width_at(y))

    def put_ball(self, frame: int, x: float, y: float, z: float) -> None:
        if not 0 <= frame < self.n:
            return
        u, v, w = self.project(x, y, z)
        self.state[frame] = BALL_TRACKED
        self.xy[frame] = (u, v)
        self.bbox[frame] = (u - w / 2, v - w / 2, u + w / 2, v + w / 2)

    def player_box(self, x: float, y: float, height: float = PLAYER_HEIGHT_M
                   ) -> Tuple[float, float, float, float]:
        scale = float(self.g.px_per_metre(y))
        u, v = self.g.world_to_image(x, y)
        return (u - 0.3 * scale, v - height * scale, u + 0.3 * scale, v)

    def put_players(self, first: int, last: int,
                    positions: Dict[str, Tuple[float, float]],
                    heights: Optional[Dict[str, float]] = None) -> None:
        heights = heights or {}
        for f in range(max(first, 0), min(last, self.n - 1) + 1):
            self.players[f] = [
                PlayerObs(track_id=i + 1,
                          bbox=self.player_box(*positions[label],
                                               heights.get(label, PLAYER_HEIGHT_M)),
                          predicted=False,
                          court_side="near" if positions[label][1] > 8.0 else "far",
                          label=label, squad=1 if label.endswith("A") else 2,
                          slot=int(label[1]))
                for i, label in enumerate(sorted(positions))]

    def fly(self, f0: int, p0, f1: int, p1, first: int = 1, last_offset: int = 0) -> None:
        """Ballistic arc from p0 at frame f0 to p1 at frame f1 (exclusive ends
        unless asked): constant ground velocity, gravity in height."""
        t_total = (f1 - f0) / FPS
        vz = (p1[2] - p0[2] + 0.5 * 9.81 * t_total ** 2) / t_total
        for f in range(f0 + first, f1 + last_offset):
            t = (f - f0) / FPS
            a = t / t_total
            self.put_ball(f, p0[0] + a * (p1[0] - p0[0]), p0[1] + a * (p1[1] - p0[1]),
                          max(p0[2] + vz * t - 0.5 * 9.81 * t * t, 0.11))

    def vertex(self, frame: int, p, accepted: bool = True) -> None:
        u, v, _ = self.project(*p)
        self.candidates.append(ContactCandidate(
            frame=frame, accepted=accepted, kind="bounce", point=(u, v),
            action="dig" if accepted else None))

    # -- scripts ---------------------------------------------------------- #

    def rally(self, script: RallyScript) -> List[int]:
        """Render one rally; returns the contact frames (serve first)."""
        f = int(script.start_s * FPS)
        serve = (*script.serve_xy, SERVE_Z)
        near_serve = script.serve_xy[1] > 8.0
        frames = [f]
        if near_serve:
            for k in range(script.toss_frames, 0, -1):          # tracked toss
                self.put_ball(f - k, serve[0], serve[1], SERVE_Z - 0.03 * k)
            self.put_ball(f, *serve)
            self.vertex(f, serve)
        prev_f, prev_p = f, serve
        points = []
        for hit in script.hits:
            xy = hit.xy or script.positions[hit.player]
            points.append((prev_f + int(round(hit.dt * FPS)), (xy[0], xy[1], hit.z), hit))
            prev_f = points[-1][0]
        prev_f = f
        for k, (hf, hp, hit) in enumerate(points):
            start = script.far_lock_delay if (k == 0 and not near_serve) else 1
            self.fly(prev_f, prev_p, hf, hp, first=start)
            if hit.seen:
                self.put_ball(hf, *hp)
                self.vertex(hf, hp, accepted=hit.accepted)
            frames.append(hf)
            prev_f, prev_p = hf, hp
        land_f = prev_f + int(round(script.landing_dt * FPS))
        land = (*script.landing, 0.11)
        start = script.far_lock_delay if (not points and not near_serve) else 1
        self.fly(prev_f, prev_p, land_f, land, first=start)
        self.put_ball(land_f, *land)
        self.vertex(land_f, land, accepted=False)            # nobody near: refused
        for k in range(1, 9):                                # rolls to a stop
            self.put_ball(land_f + k, land[0] + 0.03 * k, land[1], 0.11)
        self.put_players(f - int(3 * FPS), land_f + int(2 * FPS), script.positions,
                         script.heights)
        return frames

    def hide(self, first: int, last: int) -> None:
        """The tracker loses the ball on [first, last] (and sees no vertex)."""
        self.state[first:last + 1] = 0
        self.xy[first:last + 1] = np.nan
        self.bbox[first:last + 1] = np.nan
        self.candidates = [c for c in self.candidates if not first <= c.frame <= last]

    def bounce_routine(self, start_s: float, xy: Tuple[float, float], bounces: int = 3) -> None:
        """A server bouncing the ball at the baseline before serving: vertices
        the classifier happily emits, a ball that never goes anywhere."""
        f = int(start_s * FPS)
        for _ in range(bounces):
            top, low = (xy[0], xy[1], 1.2), (xy[0], xy[1], 0.2)
            self.fly(f, top, f + 8, low, first=0)
            self.vertex(f + 8, low, accepted=True)
            self.fly(f + 8, low, f + 16, top, first=0)
            f += 16

    def roll_back(self, start_s: float, a: Tuple[float, float], b: Tuple[float, float],
                  seconds: float = 1.5) -> None:
        """The ball rolled under the net back to the server."""
        f0 = int(start_s * FPS)
        f1 = f0 + int(seconds * FPS)
        for f in range(f0, f1):
            t = (f - f0) / (f1 - f0)
            self.put_ball(f, a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), 0.11)

    def build(self) -> MatchStream:
        return MatchStream(
            fps=FPS, n_frames=self.n, ball_state=self.state, ball_xy=self.xy,
            ball_bbox=self.bbox, ball_conf=np.full(self.n, 0.8),
            raw_dets=[[] for _ in range(self.n)], players=self.players,
            candidates=sorted(self.candidates, key=lambda c: (c.frame, not c.accepted)),
            schema_version=4)


def standard_rally(start_s: float, serving: str, positions: Dict[str, Tuple[float, float]],
                   exchanges: int = 1, landing: Optional[Tuple[float, float]] = None
                   ) -> RallyScript:
    """Serve + ``exchanges`` dig/set/spike possessions, alternating halves.

    ``serving`` is "near" or "far". The last attack lands in the middle of
    the other half unless ``landing`` says otherwise.
    """
    near = sorted(k for k, v in positions.items() if v[1] > 8.0)
    far = sorted(k for k, v in positions.items() if v[1] <= 8.0)
    side = far if serving == "near" else near
    hits: List[Hit] = []
    for k in range(exchanges):
        a, b = side
        hits += [Hit(1.15 if k == 0 else 0.9, a, DIG_Z), Hit(1.6, b, SET_Z),
                 Hit(1.6, a, SPIKE_Z)]
        side = near if side is far else far
    last_y = positions[hits[-1].player][1]
    default_landing = (4.0, 12.5) if last_y <= 8.0 else (4.0, 3.5)
    serve_xy = (6.0, 16.8) if serving == "near" else (2.0, -0.6)
    return RallyScript(start_s=start_s, serve_xy=serve_xy, hits=hits,
                       landing=landing or default_landing, positions=dict(positions))
