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
from .rallies import Rally
from .stream import MatchStream, PlayerObs

if TYPE_CHECKING:
    from .attack_shape import AttackLaunch

ACTION_SERVE = "serve"
ACTION_DIG = "dig"
ACTION_SET = "set"
ACTION_SPIKE = "spike"
ACTION_OVERPASS = "overpass"

# Touch.player_source: how a touch got its player.
SOURCE_REACH = "reach"              # the player's body was at the ball
SOURCE_ALTERNATION = "alternation"  # the rules: two players alternate in a possession

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
# Attack vs bump when a touch sends the ball over: contact height relative to
# the net tape. Measured (20260920, 59 possession-ending touches): every
# spike / poke was hit above 2.2 m and bump passes below 2.07 m, with soft
# "rainbow" attacks and high two-handed passes overlapping around 2.05 m.
# The split sits above that overlap: an ambiguous touch is an overpass,
# never an invented attack.
ATTACK_BELOW_TAPE_M = 0.28


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
        lo = max(0, start - stream.frames(1.5))
        hi = min(stream.n_frames - 1, end + stream.frames(0.5))
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

    def squad_on(self, side: str) -> Optional[int]:
        votes: Dict[int, int] = {}
        for key in self.by_side.get(side, []):
            sq = self.squad.get(key)
            if sq is not None:
                votes[sq] = votes.get(sq, 0) + len(self.obs[key])
        return max(votes, key=votes.get) if votes else None


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


class TouchSolver:
    def __init__(self, timeline: BallTimeline) -> None:
        self.tl = timeline
        self.stream = timeline.stream
        self.geometry = timeline.geometry
        net = timeline.geometry.net_top_height_m() or 2.43
        self.attack_min_height_m = net - ATTACK_BELOW_TAPE_M

    # -- public ----------------------------------------------------------- #

    def solve(self, rally: Rally) -> Tuple[List[Touch], RallyRoster]:
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
        skip = [SKIP_COST_GAP_VERTEX if e.source == SOURCE_GAP else SKIP_COST
                for e in events]
        skip_prefix = np.concatenate([[0.0], np.cumsum(skip)])
        gaps = self._gap_prefix(rally)

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
                    for yi, y in enumerate(states):
                        if best[j][yi] >= INF:
                            continue
                        step = self._transition(y, x, dt, has_gap)
                        if step is None:
                            continue
                        c = best[j][yi] + skipped + step.cost + emis[i][xi]
                        if c < best[i][xi]:
                            best[i][xi], back[i][xi] = c, (j, yi, step)

        # Best final touch (later vertices skipped); "no touch at all" is the
        # baseline every path must beat.
        end_cost, end = float(skip_prefix[n]), None
        for i in range(n):
            tail = skip_prefix[n] - skip_prefix[i + 1]
            for xi in range(len(states)):
                if best[i][xi] + tail < end_cost:
                    end_cost, end = best[i][xi] + tail, (i, xi)
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
        for i, (side, k, p), step in chain:
            e = events[i]
            for h, (hs, hk) in enumerate(step.hidden):
                frac = (h + 1) / (len(step.hidden) + 1)
                touches.append(Touch(
                    frame=int(round(prev_frame + frac * (e.frame - prev_frame))),
                    side=hs, touch_number=hk, action="", observed=False,
                    squad=roster.squad_on(hs)))
            touches.append(self._observed_touch(e, side, k, p, roster))
            prev_frame = e.frame
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

    def _emission(self, e: BallEvent, state: State, roster: RallyRoster) -> float:
        side, _, p = state
        cost = 0.0
        y = e.court_y()
        if y is not None:
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

    def _transition(self, y: State, x: State, dt: float, has_gap: bool
                    ) -> Optional[_Step]:
        (s0, k0, p0), (s1, k1, p1) = y, x
        hidden_cost = HIDDEN_COST_GAP if has_gap else HIDDEN_COST_TRACKED
        best: Optional[_Step] = None

        def consider(cost: Optional[float], hidden: List[Tuple[str, int]]) -> None:
            nonlocal best
            if cost is not None and (best is None or cost < best.cost):
                best = _Step(cost=cost, hidden=hidden)

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
        return Touch(
            frame=e.frame, side=side, touch_number=k, action="", observed=True,
            player=credited, squad=roster.squad_on(side), reach=d,
            height_m=height, court_y=y, court_x=x, court_err=err,
            player_source=SOURCE_REACH if credited else None,
            perception_action=e.candidate.action if e.candidate else None, event=e)

    def _label(self, touches: List[Touch]) -> None:
        """dig / set / spike / overpass from the possession structure.

        A touch the same half follows is a dig (touch 1) or a set. A touch
        that ends the possession sent the ball over: on touch 1 that is an
        overpass; on touch 2 or 3 it is a spike when hit at attack height and
        an overpass otherwise (owner GT rule: every non-attack that goes over
        is an overpass). The last touch of the rally is labelled as if the
        ball stayed on its half; the match layer, which knows who won the
        point, turns it into an overpass when it did not.
        """
        for i, t in enumerate(touches):
            if t.touch_number == 0:
                continue
            nxt = touches[i + 1] if i + 1 < len(touches) else None
            stays = nxt is not None and nxt.side == t.side
            t.ends_possession = not stays
            if t.height_m is not None:
                attack = t.height_m >= self.attack_min_height_m
            else:
                # No height read. Only an UNSEEN third touch defaults to the
                # usual attack (nobody is credited with it); a seen one never
                # becomes an attack on a guess.
                attack = not t.observed and t.touch_number == 3
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
