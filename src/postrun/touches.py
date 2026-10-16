"""Touches of one rally: side, touch number, player and label, solved JOINTLY.

The causal classifier decides every contact alone, a few frames after it
happens. With the whole rally in hand the volleyball rules become hard
constraints and the answer is a shortest path:

* the ball is on ONE half at a time and only a touch on that half is possible;
* a possession has at most three touches and its players ALTERNATE (the same
  player never touches twice in a row while the ball stays up);
* the first touch after a net crossing is touch 1.

State per touch = (half, touch number, which of that half's two players).
The path cost adds, per touch, how well the ball's depth fits the half and
how far the ball is from that player's body, and per step, how plausible the
time between two touches is. Trajectory vertices that fit nowhere are SKIPPED
(not every vertex is a touch), and touches the stream never saw -- the ball
was occluded or untracked -- are allowed as HIDDEN touches so the ones that
were seen still get the right number. Hidden touches are never credited to a
player (owner rule: a missing action is fine, an invented one is not). A SEEN
touch nobody was within reach of is credited only when the rules pin it down:
inside a possession the two players of that half alternate, so one credited
touch names every other one (`credit_by_alternation`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .ball_flights import EVENT_DEATH, SOURCE_GAP, BallEvent, BallTimeline
from .geometry import NET_Y_M, SIDE_FAR, SIDE_NEAR, other_side
from .rallies import END_GROUND, Rally
from .stream import MatchStream, PlayerObs

if TYPE_CHECKING:
    from .attack_shape import AttackLaunch

ACTION_SERVE = "serve"
ACTION_DIG = "dig"
ACTION_SET = "set"
ACTION_SPIKE = "spike"
ACTION_OVERPASS = "overpass"
ACTION_BLOCK = "block"

# Touch.player_source: how a touch got its player.
SOURCE_REACH = "reach"              # the player's body was at the ball
SOURCE_ALTERNATION = "alternation"  # the rules: two players alternate in a possession
SOURCE_AT_NET = "at_the_net"        # a block: the one defender standing at the net

# -- timing priors (seconds between two consecutive touches) ----------------- #
# Measured on the owner's 211-contact match GT: same-half 0.9-2.7 s (median
# 1.7), across the net 0.4-1.75 s (median 1.2), serve to reception 0.6-1.6 s.
SAME_SIDE_INTERVAL_S = (1.65, 0.55)
CROSS_INTERVAL_S = (1.15, 0.50)
SERVE_FLIGHT_S = (1.15, 0.40)
MIN_INTERVAL_S = 0.30

# -- costs (negative-log-likelihood scale) ----------------------------------- #
# A hidden touch is cheap where the track broke (the ball was occluded by the
# player touching it) and expensive under a continuous track.
HIDDEN_COST_GAP = 1.2
HIDDEN_COST_TRACKED = 4.0
DOUBLE_CROSS_COST = 2.0
# Sending the ball over on touch 1 or 2 is the exception (GT possessions:
# 3 touches 71 %, 2 touches 11 %, 1 touch 17 %).
POSSESSION_END_COST = {1: 1.8, 2: 2.2, 3: 0.3}
# The ball crosses the net ABOVE the tape. A last touch after which the ball
# was tracked down to the sand without ever getting within this of the tape
# was made on the half it came down on: the one read that still holds in the
# metre around the net, where depth cannot tell the halves apart (heights are
# read to ~0.15 m there).
UNDER_TAPE_MARGIN_M = 0.5
UNDER_TAPE_MIN_COVERAGE = 0.5      # of the frames in between, tracked
UNDER_TAPE_COST = 6.0
# Not every vertex is a touch (tape brushes, tracker jitter) -- but inside a
# live rally nearly all are, including the ones perception's reach gate
# refused (20260920: 169 of 170 in-rally vertices are owner-GT touches; the
# refused ones are real touches by a player whose box was stale).
SKIP_COST = 4.0
# A vertex inferred from a tracking gap is weaker evidence than a seen one.
SKIP_COST_GAP_VERTEX = 2.0
DEPTH_COST_CAP = 5.0
# Depth -> half. A ball in play reads ~1.3 m nearer the lens than it is (blur
# widens the box): measured at GT contacts, near-half touches read >= 8.8 m
# and far-half touches <= 9.9 m, so the split sits past the net plane and
# only that last metre is ambiguous.
DEPTH_SPLIT_BIAS_M = 1.3
DEPTH_SIGMA_M = 0.6
# Ball-to-body distance in BODY HEIGHTS (scale-free: far players are small).
# Capped low: a far player's box is often stale or missing, and a vertex with
# nobody in reach is still a touch -- it is kept, just not credited.
REACH_SIGMA = 0.35
REACH_UNKNOWN_COST = 2.0
# Everything a PLAYER contributes (reach + stance depth) is capped: a touch
# with nobody plausible near it costs as much as "that player's track is
# wrong", never enough to deny the touch itself.
PLAYER_COST_CAP = 2.5
# The ball is touched AT its toucher: its depth must match where that player
# stands. Measured at GT touches, ball depth minus the toucher's stance depth
# stays within -2..+2.7 m for the true toucher and beyond +-3.2 m for the
# nearest player of the other half -- the strongest half read there is, and
# the one that still works in the metre around the net.
STANCE_SIGMA_M = 1.3
# A jump lifts the feet off the ground plane (they project deep): stand depth
# is read before take-off.
STANCE_WINDOW_S = (0.6, 0.3)
# A player this far from the ball is not credited with the touch.
REACH_CREDIT_MAX = 0.6
# Arms extend the body box: above the head and to each side (body heights).
ARM_UP = 0.35
ARM_SIDE = 0.25
# Server identification (metres from the net).
SERVER_MIN_DEPTH_GAP_M = 1.5        # server vs partner must differ this much
SERVER_PARTNER_MAX_DEPTH_M = 5.0    # a lone visible player this close is the partner
SERVER_MIN_DEPTH_M = 7.0            # a lone visible player this deep is the server
# Attack vs bump when a touch sends the ball over: was it hit with the arm
# up, above the head? Contact height (where the ball leaves its arc,
# ``BallTimeline.arc_exit``) in units of the toucher's own STANDING height:
# a short player's attack is as far above his head as a tall one's. Measured
# on the 91 labelled possession-ending second / third touches of 20260920
# (owner GT) and 20261010 (owner feedback): passes read 0.5-1.19, swings and
# pokes 1.27 and up; two passes played with the arms above the head read
# 1.27 / 1.29 and are the misses. The split is the middle of the empty band.
# The tape is the wrong ruler: two players of 20261010 attack at 1.85-2.05 m,
# under any tape, and read as attacks only when the vertex was dated early.
ATTACK_REACH_RATIO = 1.23
# Standing height of a player: this percentile of his box heights in metres
# (a player waits crouched and jumps with his arms up; the box reads ~10 %
# under his real height, the same for everyone), seen at least this long.
STANDING_PERCENTILE = 75.0
STANDING_MIN_SEEN_S = 0.7
# Without a player to measure against, the old ruler: contact height under
# the net tape (20260920: every attack above 2.2 m at the vertex).
ATTACK_BELOW_TAPE_M = 0.28
# A BLOCK: the attack and the block are 2-6 frames apart (owner reviews of
# 20261010_1000 / 1100 / 1200), one vertex for the tracker, and the ball's
# depth at the net reads +-1.5 m, so no reversal can be read off the ball.
# What a block leaves is the RALLY: a ball hit above the tape at the net
# comes back to the hitter's own half well inside one crossing's time
# (0.4-1.1 s to the next touch on the 6 reviewed blocks; a crossing is
# ``CROSS_INTERVAL_S``) and the same team starts a new possession. That
# return is a step of the path: the block is a HIDDEN touch of the other
# half (never credited), the touch after it is touch 1 again. Somebody must
# be there to block: a player of the other half standing at the net (the
# reviewed blockers stood 0.7-1.3 m from it; a dig taken at the net after a
# spike that crossed had nobody closer than 4.5 m when the ball was hit).
BLOCK_NET_ZONE_M = 1.5             # vertex depth read this close to the net
BLOCKER_NET_M = 1.5                # blocker's stance this close to the net
BLOCK_RETURN_S = (0.75, 0.35)      # attack -> the hitter's team's next touch
BLOCK_COST = 1.0
# The block is credited (owner, 2026-10-15) to the defender standing at the
# net when the ball was hit -- only when ONE of the half's two players is
# there (a double block names nobody: precision first). The gate reads the
# ball's height at the net, never what the hit was labelled, so a free ball
# or an overpass that is blocked is credited the same way.
# The NET STOPPED IT: a ball hit above the tape whose next vertex is read on
# the net line, close along the court to the hit and sooner than a crossing,
# went into the net or off a block -- it never reached the other half, so
# that vertex is not the other half's touch (it is the hitter's team playing
# the block, or the ball falling off the net). Owner reviews: the 5 such
# vertices of 20261010_1000 / 1100 / 1200 were all read as the other team's
# overpass or dig and all corrected (0-0.5 m from the net, 0.3-1.9 m from
# the hit, 0.43-0.96 s); the closest real touch of the other half after a
# hit above the tape is 0.70 m from the net at 1.33 s (masnou P25), and a
# spike dug at the net line had travelled 4.9 m (entreno_2 f327).
NET_STOP_ZONE_M = 0.6              # vertex depth read this close to the net
NET_STOP_TRAVEL_M = 3.0            # ... and this close along the court to the hit
NET_STOP_S = CROSS_INTERVAL_S[0]   # ... sooner than a crossing takes


@dataclass
class Touch:
    frame: int
    side: str                         # half the touch happened in
    touch_number: int                 # 1..3 within the possession (0 = serve)
    action: str
    observed: bool                    # a trajectory vertex was seen
    player: Optional[str] = None      # identity label (None = not credited)
    squad: Optional[int] = None
    reach: Optional[float] = None     # body heights between ball and player
    height_m: Optional[float] = None
    #: Ball height where it left its arc, and that height in units of the
    #: toucher's standing height (attack vs bump; None: no player to measure).
    contact_height_m: Optional[float] = None
    contact_ratio: Optional[float] = None
    court_y: Optional[float] = None
    court_x: Optional[float] = None   # ball at the touch, camera frame (0 = image-left line)
    court_err: Optional[Tuple[float, float]] = None   # (across, along) m it may be off
    # Where the maps draw it (``positions``: net-anchored, box offset removed).
    # ``court_y`` above stays the read the decisions were made on.
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    pos_err: Optional[Tuple[float, float]] = None
    ends_possession: bool = False     # the ball crosses (or dies) after it
    outcome: Optional[str] = None     # ace | kill | error (match layer)
    player_source: Optional[str] = None   # how the player was decided
    perception_action: Optional[str] = None
    spike_type: Optional[str] = None      # attacks: hard | touch (attack_shape)
    launch: Optional["AttackLaunch"] = field(default=None, repr=False)
    event: Optional[BallEvent] = field(default=None, repr=False)


# --------------------------------------------------------------------------- #
# Roster: who is on which half during one rally
# --------------------------------------------------------------------------- #

class RallyRoster:
    """Players never change halves inside a point, so a body's half is read
    ONCE per rally (majority of its feet) and airborne contacts -- whose feet
    project deep into the wrong half -- cannot flip it."""

    def __init__(self, stream: MatchStream, start: int, end: int) -> None:
        self.stream = stream
        lo, hi = stream.rally_window(start, end)
        self.lo, self.hi = lo, hi
        track_votes: Dict[int, Dict[str, int]] = {}
        for f in range(lo, hi + 1):
            for p in stream.players[f]:
                if p.label:
                    votes = track_votes.setdefault(p.track_id, {})
                    votes[p.label] = votes.get(p.label, 0) + 1
        self._track_label = {tid: max(v, key=v.get) for tid, v in track_votes.items()}
        self.obs: Dict[str, Dict[int, PlayerObs]] = {}
        side_votes: Dict[str, Dict[str, int]] = {}
        squads: Dict[str, int] = {}
        for f in range(lo, hi + 1):
            for p in stream.players[f]:
                key = self.key_of(p)
                row = self.obs.setdefault(key, {})
                # A real box beats a coasting one when a key shows up twice.
                if f not in row or (row[f].predicted and not p.predicted):
                    row[f] = p
                if p.court_side:
                    votes = side_votes.setdefault(key, {})
                    votes[p.court_side] = votes.get(p.court_side, 0) + (0 if p.predicted else 1)
                if p.squad is not None and p.label == key:
                    squads[key] = int(p.squad)
        self.side: Dict[str, str] = {
            k: max(v, key=v.get) for k, v in side_votes.items() if sum(v.values()) > 0}
        self.squad = squads
        self.by_side: Dict[str, List[str]] = {SIDE_NEAR: [], SIDE_FAR: []}
        for key, side in self.side.items():
            self.by_side[side].append(key)
        for side in self.by_side:
            # Exactly two play per half; keep the two most observed bodies.
            self.by_side[side].sort(key=lambda k: -len(self.obs[k]))
            self.by_side[side] = sorted(self.by_side[side][:2])

    def key_of(self, p: PlayerObs) -> str:
        return p.label or self._track_label.get(p.track_id) or f"T{p.track_id}"

    def box_at(self, key: str, frame: int, search: int = 8) -> Optional[PlayerObs]:
        row = self.obs.get(key)
        if not row:
            return None
        for d in range(0, search + 1):
            for f in ((frame,) if d == 0 else (frame - d, frame + d)):
                if f in row:
                    return row[f]
        return None

    def stance_depth(self, key: str, frame: int, geometry) -> Optional[float]:
        """court_y of where the player stood just before ``frame``."""
        row = self.obs.get(key)
        if not row:
            return None
        early, late = (self.stream.frames(t) for t in STANCE_WINDOW_S)
        ys = []
        for f in range(frame - early, frame - late + 1):
            obs = row.get(f)
            if obs is not None and not obs.predicted:
                y = geometry.foot_court_y(obs.bbox)
                if y is not None and -6.0 < y < 24.0:
                    ys.append(y)
        if ys:
            return float(np.median(ys))
        obs = self.box_at(key, frame)
        if obs is None:
            return None
        y = geometry.foot_court_y(obs.bbox)
        return y if (y is not None and -6.0 < y < 24.0) else None

    def standing_height_m(self, key: str, geometry) -> Optional[float]:
        """How tall the player stands, in metres of his own picture scale."""
        heights = []
        for obs in self.obs.get(key, {}).values():
            if obs.predicted:
                continue
            y = geometry.foot_court_y(obs.bbox)
            if y is not None and -6.0 < y < 24.0:
                heights.append(obs.height_px / float(geometry.px_per_metre(y)))
        if len(heights) < max(1, self.stream.frames(STANDING_MIN_SEEN_S)):
            return None
        return float(np.percentile(heights, STANDING_PERCENTILE))

    def squad_on(self, side: str) -> Optional[int]:
        votes: Dict[int, int] = {}
        for key in self.by_side.get(side, []):
            sq = self.squad.get(key)
            if sq is not None:
                votes[sq] = votes.get(sq, 0) + len(self.obs[key])
        return max(votes, key=votes.get) if votes else None


def standing_heights(rosters: Sequence[RallyRoster], geometry) -> Dict[str, float]:
    """Standing height of every IDENTIFIED player over the whole video: the
    median of his per-rally reads (one rally is +-10 %: an ace leaves two
    seconds of a crouched receiver). A body without an identity label is
    measured in its own rally only -- a track id is not a person."""
    reads: Dict[str, List[float]] = {}
    for roster in rosters:
        for key in roster.squad:
            height = roster.standing_height_m(key, geometry)
            if height is not None:
                reads.setdefault(key, []).append(height)
    return {key: float(np.median(v)) for key, v in reads.items()}


def reach_in_body_heights(u: float, v: float, bbox: Sequence[float]) -> float:
    """Distance from the ball to a player's reachable box, in body heights."""
    x1, y1, x2, y2 = bbox
    h = max(y2 - y1, 1.0)
    dx = max(x1 - ARM_SIDE * h - u, 0.0, u - (x2 + ARM_SIDE * h))
    dy = max(y1 - ARM_UP * h - v, 0.0, v - y2)
    return math.hypot(dx, dy) / h


# --------------------------------------------------------------------------- #
# The solver
# --------------------------------------------------------------------------- #

State = Tuple[str, int, int]           # (side, touch number, player index)


@dataclass
class _Step:
    cost: float
    hidden: List[Tuple[str, int]]      # (side, touch number) of hidden touches, in order
    block: bool = False                # hidden[0] is a block (``_transition``)


class TouchSolver:
    def __init__(self, timeline: BallTimeline,
                 body_heights: Optional[Dict[str, float]] = None) -> None:
        self.tl = timeline
        self.stream = timeline.stream
        self.geometry = timeline.geometry
        net = timeline.geometry.net_top_height_m() or 2.43
        self.attack_min_height_m = net - ATTACK_BELOW_TAPE_M
        self.crossing_min_height_m = net - UNDER_TAPE_MARGIN_M
        #: Standing height per identified player (``standing_heights``); a
        #: player not in it is measured in the rally being solved.
        self.body_heights: Dict[str, float] = dict(body_heights or {})

    # -- public ----------------------------------------------------------- #

    def solve(self, rally: Rally, roster: Optional[RallyRoster] = None
              ) -> Tuple[List[Touch], RallyRoster]:
        if roster is None:
            roster = RallyRoster(self.stream, rally.start_frame, rally.end_frame)
        serve_side = rally.serve.side
        events = rally.touches
        touches: List[Touch] = [self._serve_touch(rally, roster)]
        if not events:
            return touches, roster

        states: List[State] = [(s, k, p) for s in (SIDE_NEAR, SIDE_FAR)
                               for k in (1, 2, 3) for p in (0, 1)]
        n = len(events)
        emis = [[self._emission(e, st, roster) for st in states] for e in events]
        # stopped[i] = earlier vertices whose hit the net stopped before i: a
        # step from one of them stays on its half, and the ball's depth read
        # on the net line says nothing about the half (``_net_stopped``).
        stopped = [{j for j in range(i) if self._net_stopped(
            events[j], e, self.stream.seconds(e.frame - events[j].frame))}
            for i, e in enumerate(events)]
        emis_net = [[self._emission(e, st, roster, depth=False) for st in states]
                    if stopped[i] else None for i, e in enumerate(events)]
        skip = [SKIP_COST_GAP_VERTEX if e.source == SOURCE_GAP else SKIP_COST
                for e in events]
        skip_prefix = np.concatenate([[0.0], np.cumsum(skip)])
        gaps = self._gap_prefix(rally)
        at_net = [self._blockable(e, roster) for e in events]

        INF = float("inf")
        best = [[INF] * len(states) for _ in range(n)]
        back: List[List[Optional[Tuple[int, int, _Step]]]] = [
            [None] * len(states) for _ in range(n)]
        for i, e in enumerate(events):
            for xi, x in enumerate(states):
                if emis[i][xi] >= INF:
                    continue
                # From the serve (all earlier vertices skipped).
                step = self._from_serve(serve_side, x, self.stream.seconds(
                    e.frame - rally.serve.frame), gaps[i + 1] - gaps[0] > 0)
                if step is not None:
                    c = step.cost + skip_prefix[i] + emis[i][xi]
                    if c < best[i][xi]:
                        best[i][xi], back[i][xi] = c, (-1, -1, step)
                for j in range(i):
                    dt = self.stream.seconds(e.frame - events[j].frame)
                    has_gap = gaps[i + 1] - gaps[j + 1] > 0
                    skipped = skip_prefix[i] - skip_prefix[j + 1]
                    net = j in stopped[i]
                    emission = emis_net[i][xi] if net else emis[i][xi]
                    for yi, y in enumerate(states):
                        if best[j][yi] >= INF or (net and x[0] != y[0]):
                            continue
                        step = self._transition(y, x, dt, has_gap, y[0] in at_net[j])
                        if step is None:
                            continue
                        c = best[j][yi] + skipped + step.cost + emission
                        if c < best[i][xi]:
                            best[i][xi], back[i][xi] = c, (j, yi, step)

        # Best final touch (later vertices skipped); "no touch at all" is the
        # baseline every path must beat.
        end_cost, end = float(skip_prefix[n]), None
        died_on = self._died_on(rally)
        low = self._under_tape_to_end(events) if died_on is not None else [False] * n
        for i in range(n):
            tail = skip_prefix[n] - skip_prefix[i + 1]
            for xi in range(len(states)):
                cost = best[i][xi] + tail
                if low[i] and states[xi][0] != died_on:
                    cost += UNDER_TAPE_COST     # it came down where it was touched
                if cost < end_cost:
                    end_cost, end = cost, (i, xi)
        if end is None:
            return touches, roster

        chain: List[Tuple[int, State, _Step]] = []
        cur = end
        while cur is not None and cur[0] >= 0:
            i, xi = cur
            j, yi, step = back[i][xi]
            chain.append((i, states[xi], step))
            cur = (j, yi) if j >= 0 else None
        chain.reverse()

        prev_frame = rally.serve.frame
        prev_event: Optional[BallEvent] = None
        for i, (side, k, p), step in chain:
            e = events[i]
            for h, (hs, hk) in enumerate(step.hidden):
                frac = (h + 1) / (len(step.hidden) + 1)
                frame = int(round(prev_frame + frac * (e.frame - prev_frame)))
                block = step.block and h == 0
                blocker = None
                if block:               # right after the attack it stopped
                    frame = prev_frame + max(1, int(round(0.1 * self.stream.fps)))
                    if prev_event is not None:
                        blocker = self._blocker(prev_event, hs, roster)
                touches.append(Touch(
                    frame=frame, side=hs, touch_number=hk,
                    action=ACTION_BLOCK if block else "", observed=False,
                    squad=roster.squad_on(hs), player=blocker,
                    player_source=SOURCE_AT_NET if blocker else None))
            touches.append(self._observed_touch(e, side, k, p, roster))
            prev_frame, prev_event = e.frame, e
        self._label(touches)
        return touches, roster

    # -- serve ------------------------------------------------------------ #

    def _serve_touch(self, rally: Rally, roster: RallyRoster) -> Touch:
        side = rally.serve.side
        frame = rally.serve.frame
        player = self._server(side, frame, roster)
        return Touch(
            frame=frame, side=side, touch_number=0, action=ACTION_SERVE,
            observed=rally.serve.observed, player=player,
            squad=roster.squad_on(side), ends_possession=True)

    def _server(self, side: str, frame: int, roster: RallyRoster) -> Optional[str]:
        """The serving half's player farther from the net at the serve. When
        only the partner at the net is in view, the server is the other one
        (two play per half)."""
        keys = roster.by_side.get(side, [])
        depth: Dict[str, float] = {}
        for key in keys:
            obs = roster.box_at(key, frame, search=self.stream.frames(0.6))
            if obs is None:
                continue
            y = self.geometry.foot_court_y(obs.bbox)
            if y is not None:
                depth[key] = abs(y - NET_Y_M)
        if len(depth) == 2:
            a, b = keys
            if abs(depth[a] - depth[b]) < SERVER_MIN_DEPTH_GAP_M:
                return None                  # both equally deep: do not guess
            return a if depth[a] > depth[b] else b
        if len(depth) == 1 and len(keys) == 2:
            seen = next(iter(depth))
            if depth[seen] < SERVER_PARTNER_MAX_DEPTH_M:
                return keys[0] if keys[1] == seen else keys[1]
            return seen if depth[seen] >= SERVER_MIN_DEPTH_M else None
        return None

    # -- costs ------------------------------------------------------------ #

    def _emission(self, e: BallEvent, state: State, roster: RallyRoster,
                  depth: bool = True) -> float:
        """``depth`` False: the ball is on the net line (``_net_stopped``),
        where its depth read cannot tell the halves apart."""
        side, _, p = state
        cost = 0.0
        y = e.court_y()
        if y is not None and depth:
            z = (y - (NET_Y_M + DEPTH_SPLIT_BIAS_M)) / DEPTH_SIGMA_M
            p_near = 1.0 / (1.0 + math.exp(-z))
            prob = p_near if side == SIDE_NEAR else 1.0 - p_near
            cost += min(-math.log(max(prob, 1e-9)), DEPTH_COST_CAP)
        player = self._reach_cost(e, side, p, roster)
        keys = roster.by_side.get(side, [])
        if y is not None and p < len(keys):
            stance = roster.stance_depth(keys[p], e.frame, self.geometry)
            if stance is not None:
                player += 0.5 * ((y - stance) / STANCE_SIGMA_M) ** 2
        return cost + min(player, PLAYER_COST_CAP)

    def _reach(self, e: BallEvent, side: str, p: int, roster: RallyRoster
               ) -> Tuple[Optional[str], Optional[float]]:
        keys = roster.by_side.get(side, [])
        if p >= len(keys) or not np.isfinite(e.u):
            return (keys[p] if p < len(keys) else None), None
        obs = roster.box_at(keys[p], e.frame)
        if obs is None:
            return keys[p], None
        return keys[p], reach_in_body_heights(e.u, e.v, obs.bbox)

    def _reach_cost(self, e: BallEvent, side: str, p: int, roster: RallyRoster) -> float:
        _, d = self._reach(e, side, p, roster)
        if d is None:
            return REACH_UNKNOWN_COST
        return 0.5 * (d / REACH_SIGMA) ** 2

    @staticmethod
    def _timing(dt: float, parts: Sequence[Tuple[float, float]]) -> Optional[float]:
        if dt < MIN_INTERVAL_S * len(parts):
            return None
        mean = sum(m for m, _ in parts)
        var = sum(s * s for _, s in parts)
        return 0.5 * (dt - mean) ** 2 / var

    def _from_serve(self, serve_side: str, x: State, dt: float, has_gap: bool
                    ) -> Optional[_Step]:
        side, k, _ = x
        hidden_cost = HIDDEN_COST_GAP if has_gap else HIDDEN_COST_TRACKED
        receiving = other_side(serve_side)
        if side != receiving:
            return None                      # the serve's first touch is the receivers'
        n = k - 1
        t = self._timing(dt, [SERVE_FLIGHT_S] + [SAME_SIDE_INTERVAL_S] * n)
        if t is None:
            return None
        return _Step(cost=t + hidden_cost * n,
                     hidden=[(side, q) for q in range(1, k)])

    def _blockable(self, e: BallEvent, roster: RallyRoster) -> Tuple[str, ...]:
        """Halves a hit at this vertex could have been blocked FROM: the ball
        was above the tape at the net and the other half had a player
        standing at the net."""
        y = e.court_y()
        if y is None or abs(y - NET_Y_M) > BLOCK_NET_ZONE_M or not np.isfinite(e.u):
            return ()
        if self.geometry.ball_world(e.u, e.v, y)[2] < self.attack_min_height_m:
            return ()
        return tuple(side for side in (SIDE_NEAR, SIDE_FAR)
                     if self._at_the_net(e, other_side(side), roster))

    def _at_the_net(self, e: BallEvent, side: str, roster: RallyRoster) -> List[str]:
        """Players of ``side`` standing at the net when the ball was hit."""
        out = []
        for key in roster.by_side.get(side, []):
            stance = roster.stance_depth(key, e.frame, self.geometry)
            if stance is not None and abs(stance - NET_Y_M) <= BLOCKER_NET_M:
                out.append(key)
        return out

    def _blocker(self, hit: BallEvent, side: str, roster: RallyRoster) -> Optional[str]:
        """The block's player: the one defender at the net, nobody otherwise."""
        at_net = self._at_the_net(hit, side, roster)
        return at_net[0] if len(at_net) == 1 else None

    def _net_stopped(self, hit: BallEvent, e: BallEvent, dt: float) -> bool:
        """The ball hit above the tape at ``hit`` was next seen at ``e`` on
        the net line UNDER the tape (so not on its way over), not far from
        the hit, sooner than a crossing: the net or a block stopped it, and
        ``e`` is not the other half's touch."""
        y0, y1 = hit.court_y(), e.court_y()
        if (y0 is None or y1 is None or dt >= NET_STOP_S
                or not (np.isfinite(hit.u) and np.isfinite(e.u))
                or abs(y1 - NET_Y_M) > NET_STOP_ZONE_M
                or abs(y1 - y0) > NET_STOP_TRAVEL_M):
            return False
        return (self.geometry.ball_world(hit.u, hit.v, y0)[2] >= self.attack_min_height_m
                and self.geometry.ball_world(e.u, e.v, y1)[2] < self.crossing_min_height_m)

    def _transition(self, y: State, x: State, dt: float, has_gap: bool,
                    blockable: bool = False) -> Optional[_Step]:
        (s0, k0, p0), (s1, k1, p1) = y, x
        hidden_cost = HIDDEN_COST_GAP if has_gap else HIDDEN_COST_TRACKED
        best: Optional[_Step] = None

        def consider(cost: Optional[float], hidden: List[Tuple[str, int]],
                     block: bool = False) -> None:
            nonlocal best
            if cost is not None and (best is None or cost < best.cost):
                best = _Step(cost=cost, hidden=hidden, block=block)

        if s1 == s0 and blockable:
            # Blocked: back to the hitter's half, a new possession there.
            n = k1 - 1
            t = self._timing(dt, [BLOCK_RETURN_S] + [SAME_SIDE_INTERVAL_S] * n)
            if t is not None:
                consider(t + BLOCK_COST + hidden_cost * n,
                         [(other_side(s0), 1)] + [(s1, q) for q in range(1, k1)],
                         block=True)
        if s1 == s0:
            # Same possession: h hidden touches in between, players alternate.
            h = k1 - k0 - 1
            if h >= 0 and (p1 == p0) == (h % 2 == 1):
                t = self._timing(dt, [SAME_SIDE_INTERVAL_S] * (h + 1))
                if t is not None:
                    consider(t + hidden_cost * h, [(s0, k0 + q) for q in range(1, h + 1)])
            # Away and back: a whole possession on the other half went unseen.
            for m in range(0, 3 - k0 + 1):
                for j in range(1, 4):
                    n = k1 - 1
                    h = m + j + n
                    parts = ([SAME_SIDE_INTERVAL_S] * m + [CROSS_INTERVAL_S]
                             + [SAME_SIDE_INTERVAL_S] * (j - 1) + [CROSS_INTERVAL_S]
                             + [SAME_SIDE_INTERVAL_S] * n)
                    t = self._timing(dt, parts)
                    if t is None:
                        continue
                    o = other_side(s0)
                    hidden = ([(s0, k0 + q) for q in range(1, m + 1)]
                              + [(o, q) for q in range(1, j + 1)]
                              + [(s1, q) for q in range(1, k1)])
                    consider(t + hidden_cost * h + DOUBLE_CROSS_COST
                             + POSSESSION_END_COST[k0 + m] + POSSESSION_END_COST[j],
                             hidden)
        else:
            # One crossing: m more hidden touches before it, k1-1 after it.
            for m in range(0, 3 - k0 + 1):
                n = k1 - 1
                parts = ([SAME_SIDE_INTERVAL_S] * m + [CROSS_INTERVAL_S]
                         + [SAME_SIDE_INTERVAL_S] * n)
                t = self._timing(dt, parts)
                if t is None:
                    continue
                hidden = ([(s0, k0 + q) for q in range(1, m + 1)]
                          + [(s1, q) for q in range(1, k1)])
                consider(t + hidden_cost * (m + n) + POSSESSION_END_COST[k0 + m], hidden)
        return best

    def _under_tape_to_end(self, events: Sequence[BallEvent]) -> List[bool]:
        """Per vertex: from it to the end of the rally the ball was tracked
        and never got near the tape."""
        n = len(events)
        low = [False] * n
        peak, seen, end = float("-inf"), 0, None
        for i in range(n - 1, -1, -1):
            out = events[i].flight_out
            if out is None or not math.isfinite(out.peak_height_m):
                break
            end = out.end if end is None else end
            peak, seen = max(peak, out.peak_height_m), seen + out.n
            if peak >= self.crossing_min_height_m:
                break
            low[i] = seen >= UNDER_TAPE_MIN_COVERAGE * (end - events[i].frame)
        return low

    @staticmethod
    def _died_on(rally: Rally) -> Optional[str]:
        """Half the ball was SEEN coming down on, in the flight that left the
        rally's last vertex (None: too close to the net to say, or the ball
        was only found lying somewhere later -- it rolls under the net)."""
        end = rally.end
        last = rally.touches[-1].flight_out if rally.touches else None
        if (end is None or end.kind != END_GROUND or last is None
                or end.frame > last.end):
            return None
        return end.side

    def _gap_prefix(self, rally: Rally) -> np.ndarray:
        """gaps[i] = number of unbridged tracking gaps before vertex i-1's
        frame (index 0 = the serve), so a difference tells whether the track
        broke between two vertices."""
        frames = [rally.serve.frame] + [e.frame for e in rally.touches]
        deaths = np.array(sorted(
            ev.frame for ev in self.tl.events
            if ev.kind == EVENT_DEATH
            and rally.serve.frame <= ev.frame <= rally.end_frame),
            dtype=int)
        return np.array([0] + [int((deaths < f).sum()) for f in frames[1:]])

    # -- output ----------------------------------------------------------- #

    def _observed_touch(self, e: BallEvent, side: str, k: int, p: int,
                        roster: RallyRoster) -> Touch:
        key, d = self._reach(e, side, p, roster)
        credited = key if (key is not None and d is not None
                           and d <= REACH_CREDIT_MAX) else None
        y = e.court_y()
        x = height = err = None
        if y is not None and np.isfinite(e.u):
            x, _, height = self.geometry.ball_world(e.u, e.v, y)
            err = self.geometry.ball_read_error_m(e.u, e.v, y, e.depth_samples())
        contact, ratio = height, None
        hit = self.tl.arc_exit(e) if y is not None else None
        if hit is not None:
            contact = self.geometry.ball_world(*self.stream.ball_xy[hit], y)[2]
        tall = self._standing_height(key, roster)
        if contact is not None and tall:
            ratio = contact / tall
        return Touch(
            frame=e.frame, side=side, touch_number=k, action="", observed=True,
            player=credited, squad=roster.squad_on(side), reach=d,
            height_m=height, contact_height_m=contact, contact_ratio=ratio,
            court_y=y, court_x=x, court_err=err,
            player_source=SOURCE_REACH if credited else None,
            perception_action=e.candidate.action if e.candidate else None, event=e)

    def _standing_height(self, key: Optional[str], roster: RallyRoster) -> Optional[float]:
        if key is None:
            return None
        known = self.body_heights.get(key)
        return known if known else roster.standing_height_m(key, self.geometry)

    def _is_attack(self, t: Touch) -> bool:
        """Was the ball hit with the arm up (a swing, a poke, a roll shot)
        and not passed with the forearms?"""
        if t.contact_ratio is not None:
            return t.contact_ratio >= ATTACK_REACH_RATIO
        height = t.contact_height_m if t.contact_height_m is not None else t.height_m
        if height is not None:
            return height >= self.attack_min_height_m
        # No height read. Only an UNSEEN third touch defaults to the usual
        # attack (nobody is credited with it); a seen one never becomes an
        # attack on a guess.
        return not t.observed and t.touch_number == 3

    def _label(self, touches: List[Touch]) -> None:
        """dig / set / spike / overpass from the possession structure.

        A touch the same half follows is a dig (touch 1) or a set. A touch
        that ends the possession sent the ball over: on touch 1 that is an
        overpass; on touch 2 or 3 it is a spike when hit with the arm up and
        an overpass otherwise (owner GT rule: every non-attack that goes over
        is an overpass). The last touch of the rally is labelled as if the
        ball stayed on its half; the match layer, which knows who won the
        point, turns it into an overpass when it did not.
        """
        for i, t in enumerate(touches):
            if t.touch_number == 0:
                continue
            nxt = touches[i + 1] if i + 1 < len(touches) else None
            if t.action == ACTION_BLOCK:
                t.ends_possession = True
                continue
            stays = nxt is not None and nxt.side == t.side
            t.ends_possession = not stays
            attack = self._is_attack(t)
            if stays:
                t.action = ACTION_DIG if t.touch_number == 1 else ACTION_SET
            elif t.touch_number == 1:
                t.action = ACTION_DIG if nxt is None else ACTION_OVERPASS
            elif attack:
                t.action = ACTION_SPIKE
            elif nxt is None and t.touch_number == 2:
                t.action = ACTION_SET
            else:
                t.action = ACTION_OVERPASS


# --------------------------------------------------------------------------- #
# Players the rules pin down
# --------------------------------------------------------------------------- #

def possessions(touches: Sequence[Touch]) -> List[List[Touch]]:
    """Runs of consecutive touches by one half (touch numbers 1, 2, 3...).

    The serve (touch 0) belongs to no run: its half's first body touch comes
    after the ball has crossed."""
    runs: List[List[Touch]] = []
    prev: Optional[Touch] = None
    for t in touches:
        if t.touch_number == 0:
            prev = None
            continue
        if prev is not None and prev.side == t.side and prev.touch_number + 1 == t.touch_number:
            runs[-1].append(t)
        else:
            runs.append([t])
        prev = t
    return runs


def credit_by_alternation(touches: Sequence[Touch], roster: RallyRoster) -> List[Touch]:
    """Credit the SEEN touches nobody was within reach of when the rules decide.

    Two players per half and nobody touches twice in a row: inside one
    possession the touch numbers alternate between the pair, so a single
    credited touch names every other touch of that possession (dig by P2B,
    set by P1B -> the third is P2B's; a dig by P2A followed by two touches
    out of anyone's reach on the same half is set P1A, attack P2A). Three
    guards keep it honest: the half must have exactly two known players, the
    possession needs a touch credited by reach to anchor it, and the credited
    touches must already agree with alternation (otherwise the possession is
    left as it is). A hidden touch counts in the parity but is never credited.
    """
    credited: List[Touch] = []
    for run in possessions(touches):
        pair = roster.by_side.get(run[0].side, [])
        anchors = [t for t in run if t.player]
        if len(pair) != 2 or not anchors:
            continue
        first = anchors[0]
        if any(t.player not in pair
               or (t.player == first.player) != ((t.touch_number - first.touch_number) % 2 == 0)
               for t in anchors):
            continue
        partner = pair[0] if pair[1] == first.player else pair[1]
        for t in run:
            if t.player is None and t.observed:
                same = (t.touch_number - first.touch_number) % 2 == 0
                t.player = first.player if same else partner
                t.player_source = SOURCE_ALTERNATION
                credited.append(t)
    return credited
