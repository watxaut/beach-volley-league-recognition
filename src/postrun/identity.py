"""Who is who, read per rally in hindsight (the squads survive a side switch).

The causal identity resolver decides, frame by frame, which squad is on the
near half. It has to assume what the unseen orientation will look like and it
keeps adapting while the players walk around the net, so a switch can pass it
by (20261010: none of the first two, then ten flips). After the run nothing
has to be assumed:

* **which squad is near** is one fact per RALLY (nobody changes halves while
  the ball is up). Each rally gives one number -- how much better the bodies
  on each half match the squad that was enrolled there than the other squad --
  and over a match those numbers sit at two levels, one per orientation. The
  levels are read from the match itself; the opening is the enrolled one;
* **who is who** inside a rally is one shortest path over frames: every
  tracked body is one of the four players, two per half, and a track id
  changes player only when the evidence pays for it (an id that moved to
  another body).

Input: the per-body similarities to the four enrolled players that the causal
resolver already computed (``id_sims`` in the diag dump, schema 5). A dump
without them is left exactly as it was. Output: the ``label`` / ``squad`` /
``slot`` / ``court_side`` of the players inside each rally window, rewritten
in place before the touches are solved.

A body's half comes from its squad, not from its feet: a blocker at the net
stands on the net line in the picture, and a jump projects the feet metres
deep. The feet only anchor the read where they are clear of the net.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .geometry import COURT_WIDTH_M, NET_Y_M, SIDE_FAR, SIDE_NEAR, CourtGeometry, other_side
from .stream import MatchStream, PlayerObs

logger = logging.getLogger(__name__)

# -- which squad is near ------------------------------------------------------ #
# Feet this close to the net line do not say which half a body is on.
NET_CLEAR_M = 1.0
# A half's evidence needs this much body time in the rally.
MIN_SIDE_SECONDS = 0.5
# Two orientations exist in a match only if the rallies sit at two levels this
# many spreads apart ...
SPLIT_MIN_SIGMAS = 4.0
# ... and the lower one explains the enrolled layout at most this share as
# well as the upper one (a drift of light or pose moves a level, it does not
# halve it).
SPLIT_MAX_SHARE = 0.5
LEVEL_SIGMA_FLOOR = 0.02            # similarity
# One rally's evidence never weighs more than this (nats) ...
RALLY_COST_CAP = 6.0
# ... and a side switch has to be paid for: one odd rally does not make two.
SWITCH_COST = 4.0

# -- who is who --------------------------------------------------------------- #
# A body clear of the net on the half of the other squad (similarity per frame:
# the whole scale is 0..1, so this outweighs any look-alike).
SIDE_PENALTY = 0.5
# A track id changes player when the evidence beats this margin for this long.
SWAP_MARGIN = 0.15                  # similarity
SWAP_SECONDS = 1.0
# The two players of a half are told apart only above this mean margin per
# body and frame; below it that half gets no labels in the rally.
SLOT_MIN_MARGIN = 0.02              # similarity
MIN_SLOT_SECONDS = 0.5

REASON_NO_OBSERVATIONS = "no_identity_observations"
REASON_NO_RALLY_READ = "no_rally_read"
REASON_OPENING = "opening_not_at_enrolled_level"

SOURCE_EVIDENCE = "evidence"
SOURCE_NEIGHBOURS = "neighbours"      # no read of its own: the rallies around it


@dataclass
class _Player:
    label: str
    squad: int
    slot: int


@dataclass
class _Obs:
    frame: int
    track_id: int
    sims: np.ndarray                  # (4,) similarity to each player's anchors
    side: Optional[str]               # half by the feet; None inside the net band


@dataclass
class RallyIdentity:
    """What was read for one rally."""

    start_frame: int
    end_frame: int
    lo: int
    hi: int
    evidence: Optional[float] = None
    near_squad: Optional[int] = None
    source: Optional[str] = None
    slot_margin: Dict[str, Optional[float]] = field(default_factory=dict)
    withheld: List[str] = field(default_factory=list)
    id_changes: int = 0
    # frame -> {track id: (player index, half)}: what ``apply`` writes.
    plan: Optional[Tuple[List[int], List[Dict[int, Tuple[int, str]]]]] = field(
        default=None, repr=False)

    def payload(self) -> Dict[str, Any]:
        return {
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "evidence": None if self.evidence is None else round(self.evidence, 3),
            "near_squad": self.near_squad,
            "source": self.source,
            "slot_margin": {k: (None if v is None else round(v, 3))
                            for k, v in self.slot_margin.items()},
            "withheld": list(self.withheld),
            "id_changes": self.id_changes,
        }


@dataclass
class IdentityRead:
    applied: bool
    reason: Optional[str] = None
    levels: Optional[Dict[str, float]] = None
    two_levels: bool = False
    rallies: List[RallyIdentity] = field(default_factory=list)

    def payload(self) -> Dict[str, Any]:
        return {
            "applied": self.applied,
            "reason": self.reason,
            "levels": self.levels,
            "two_orientations": self.two_levels,
            "rallies": [r.payload() for r in self.rallies],
        }


def parse_players(labels: Optional[Sequence[str]]) -> Optional[List[_Player]]:
    """``P1A`` -> slot 1 of squad 1. Needs two players in each of two squads."""
    if not labels or len(labels) != 4:
        return None
    out: List[_Player] = []
    for lab in labels:
        if not (isinstance(lab, str) and len(lab) == 3 and lab[0] == "P"
                and lab[1] in "12" and lab[2] in "AB"):
            return None
        out.append(_Player(lab, 1 if lab[2] == "A" else 2, int(lab[1])))
    if sorted((p.squad, p.slot) for p in out) != [(1, 1), (1, 2), (2, 1), (2, 2)]:
        return None
    return out


class _NetLine:
    """Signed metres from the net to a player's feet (+ = near half)."""

    def __init__(self, geometry: CourtGeometry) -> None:
        self.geometry = geometry
        clicks = geometry.net_ground_points
        if clicks is None:
            clicks = np.array([geometry.world_to_image(0.0, NET_Y_M),
                               geometry.world_to_image(COURT_WIDTH_M, NET_Y_M)])
        self.a, self.b = sorted((np.asarray(clicks[0], float), np.asarray(clicks[1], float)),
                                key=lambda p: p[0])

    def offset_m(self, bbox: Sequence[float]) -> Optional[float]:
        u, v = (bbox[0] + bbox[2]) / 2.0, bbox[3]
        du = self.b[0] - self.a[0]
        if abs(du) < 1e-6:
            return None
        v_net = self.a[1] + (u - self.a[0]) * (self.b[1] - self.a[1]) / du
        foot = self.geometry.image_to_world(u, v)
        net = self.geometry.image_to_world(u, v_net)
        if foot is None or net is None:
            return None
        return float(foot[1] - net[1])

    def side(self, bbox: Sequence[float]) -> Optional[str]:
        d = self.offset_m(bbox)
        if d is None or abs(d) < NET_CLEAR_M:
            return None
        return SIDE_NEAR if d > 0 else SIDE_FAR


def _split(values: np.ndarray) -> Optional[Tuple[float, float, float]]:
    """The best two-level split of ``values``: (upper mean, lower mean, spread)."""
    order = np.sort(values)
    best = None
    for k in range(1, len(order)):
        lo, hi = order[:k], order[k:]
        within = float(((lo - lo.mean()) ** 2).sum() + ((hi - hi.mean()) ** 2).sum())
        if best is None or within < best[0]:
            best = (within, float(hi.mean()), float(lo.mean()))
    if best is None:
        return None
    sigma = max(float(np.sqrt(best[0] / len(order))), LEVEL_SIGMA_FLOOR)
    return best[1], best[2], sigma


class IdentityReader:
    def __init__(self, stream: MatchStream, geometry: CourtGeometry) -> None:
        self.stream = stream
        self.players = parse_players(stream.identity_players)
        self.net = _NetLine(geometry)
        if self.players is not None:
            self.squad_idx = {q: [i for i, p in enumerate(self.players) if p.squad == q]
                              for q in (1, 2)}

    # -- public ----------------------------------------------------------- #

    def read(self, spans: Sequence[Tuple[int, int]]) -> IdentityRead:
        """Read every rally (``spans`` = serve frame, end frame). Nothing is
        written until ``apply`` is called for a rally."""
        if self.players is None or not spans:
            return IdentityRead(False, REASON_NO_OBSERVATIONS)
        rallies = [RallyIdentity(s, e, *self.stream.rally_window(s, e)) for s, e in spans]
        obs = [self._observations(r) for r in rallies]
        if not any(obs):
            return IdentityRead(False, REASON_NO_OBSERVATIONS)
        for r, o in zip(rallies, obs):
            r.evidence = self._evidence(o)
        read = self._orient(rallies)
        if not read.applied:
            return read
        centre = self._centres(rallies, obs)
        for r, o in zip(rallies, obs):
            self._assign(r, o, centre[r.near_squad])
        read.rallies = rallies
        return read

    # -- observations ------------------------------------------------------ #

    def _observations(self, rally: RallyIdentity) -> List[_Obs]:
        out: List[_Obs] = []
        for f in range(rally.lo, rally.hi + 1):
            for p in self.stream.players[f]:
                if p.id_sims is None or p.predicted:
                    continue
                out.append(_Obs(f, p.track_id, np.asarray(p.id_sims, dtype=np.float64),
                                self.net.side(p.bbox)))
        return out

    # -- which squad is near ------------------------------------------------ #

    def _evidence(self, obs: List[_Obs]) -> Optional[float]:
        """Mean, over the two halves, of how much better their bodies match
        squad 1 (near half) / squad 2 (far half) than the other squad."""
        need = max(1, self.stream.frames(MIN_SIDE_SECONDS))
        q1, q2 = self.squad_idx[1], self.squad_idx[2]
        sides = []
        for side, sign in ((SIDE_NEAR, 1.0), (SIDE_FAR, -1.0)):
            x = [o.sims[q1].max() - o.sims[q2].max() for o in obs if o.side == side]
            if len(x) >= need:
                sides.append(sign * float(np.mean(x)))
        return float(np.mean(sides)) if sides else None

    def _orient(self, rallies: List[RallyIdentity]) -> IdentityRead:
        known = [i for i, r in enumerate(rallies) if r.evidence is not None]
        if not known:
            return IdentityRead(False, REASON_NO_RALLY_READ)
        values = np.array([rallies[i].evidence for i in known])
        split = _split(values) if len(values) >= 2 else None
        two = (split is not None and split[0] > 0
               and split[0] - split[1] >= SPLIT_MIN_SIGMAS * split[2]
               and split[1] <= SPLIT_MAX_SHARE * split[0])
        if not two:
            # One level: the squads never left the halves they were enrolled on.
            for r in rallies:
                r.near_squad = 1
                r.source = SOURCE_EVIDENCE if r.evidence is not None else SOURCE_NEIGHBOURS
            return IdentityRead(True, levels={"squad_1_near": round(float(values.mean()), 3)},
                                rallies=rallies)
        upper, lower, sigma = split
        if abs(values[0] - lower) < abs(values[0] - upper):
            # The first read rally is the enrolled layout by construction; if
            # it sits at the lower level the levels are not what they seem.
            return IdentityRead(False, REASON_OPENING)
        # Two states over the rallies; a switch costs SWITCH_COST.
        cost = np.zeros((len(rallies), 2))
        for i in known:
            for k, level in enumerate((upper, lower)):
                cost[i, k] = min(0.5 * ((rallies[i].evidence - level) / sigma) ** 2,
                                 RALLY_COST_CAP)
        best = np.array([0.0, np.inf])        # the opening is the enrolled orientation
        back = np.zeros((len(rallies), 2), dtype=int)
        for i in range(len(rallies)):
            new = np.empty(2)
            for k in (0, 1):
                stay, move = best[k], best[1 - k] + SWITCH_COST
                back[i, k] = k if stay <= move else 1 - k
                new[k] = min(stay, move) + cost[i, k]
            best = new
        k = int(np.argmin(best))
        for i in range(len(rallies) - 1, -1, -1):
            rallies[i].near_squad = 1 + k
            rallies[i].source = (SOURCE_EVIDENCE if rallies[i].evidence is not None
                                 else SOURCE_NEIGHBOURS)
            k = int(back[i, k])
        return IdentityRead(
            True, two_levels=True, rallies=rallies,
            levels={"squad_1_near": round(upper, 3), "squad_2_near": round(lower, 3),
                    "spread": round(sigma, 3)})

    # -- who is who --------------------------------------------------------- #

    def _side_of(self, player: int, near_squad: int) -> str:
        return SIDE_NEAR if self.players[player].squad == near_squad else SIDE_FAR

    def _centres(self, rallies: List[RallyIdentity], obs: List[List[_Obs]]
                 ) -> Dict[int, np.ndarray]:
        """Per orientation and player: the similarity to that player's anchors
        half way between the two bodies of its half. A view shifts both
        teammates' similarities alike; taking this off leaves what tells one
        from the other, so a body seen without its teammate is read unbiased."""
        out: Dict[int, np.ndarray] = {}
        for near_squad in (1, 2):
            pair: List[List[float]] = [[] for _ in self.players]
            single: List[List[float]] = [[] for _ in self.players]
            for r, o in zip(rallies, obs):
                if r.near_squad != near_squad:
                    continue
                by_frame: Dict[Tuple[int, str], List[_Obs]] = {}
                for ob in o:
                    if ob.side is not None:
                        by_frame.setdefault((ob.frame, ob.side), []).append(ob)
                for (_, side), group in by_frame.items():
                    for a in range(len(self.players)):
                        if self._side_of(a, near_squad) != side:
                            continue
                        if len(group) == 2:
                            pair[a].append((group[0].sims[a] + group[1].sims[a]) / 2.0)
                        for ob in group:
                            single[a].append(ob.sims[a])
            out[near_squad] = np.array([
                float(np.mean(pair[a])) if pair[a]
                else (float(np.mean(single[a])) if single[a] else 0.0)
                for a in range(len(self.players))])
        return out

    def _assign(self, rally: RallyIdentity, obs: List[_Obs], centre: np.ndarray) -> None:
        """One shortest path over the rally's frames: which player each track
        id is."""
        near_squad = rally.near_squad
        counts: Dict[int, int] = {}
        for o in obs:
            counts[o.track_id] = counts.get(o.track_id, 0) + 1
        tids = sorted(sorted(counts, key=lambda t: -counts[t])[:len(self.players)])
        frames = sorted({o.frame for o in obs if o.track_id in tids})
        if not tids or not frames:
            rally.withheld = [SIDE_NEAR, SIDE_FAR]
            return
        states = list(itertools.permutations(range(len(self.players)), len(tids)))
        row = {f: i for i, f in enumerate(frames)}
        col = {t: j for j, t in enumerate(tids)}
        # value[frame, tid, player]: centred similarity, less the side penalty.
        value = np.zeros((len(frames), len(tids), len(self.players)))
        seen = np.zeros((len(frames), len(tids)), dtype=bool)
        sides = [self._side_of(a, near_squad) for a in range(len(self.players))]
        for o in obs:
            if o.track_id not in col:
                continue
            v = o.sims - centre
            if o.side is not None:
                v = v - SIDE_PENALTY * np.array([s != o.side for s in sides])
            value[row[o.frame], col[o.track_id]] = v
            seen[row[o.frame], col[o.track_id]] = True
        emis = np.zeros((len(frames), len(states)))
        for si, st in enumerate(states):
            emis[:, si] = sum(value[:, j, a] for j, a in enumerate(st))
        swap = SWAP_MARGIN * SWAP_SECONDS * self.stream.fps
        score = emis[0].copy()
        back = np.zeros((len(frames), len(states)), dtype=int)
        for i in range(1, len(frames)):
            top = int(np.argmax(score))
            stay = score >= score[top] - swap
            back[i] = np.where(stay, np.arange(len(states)), top)
            score = np.where(stay, score, score[top] - swap) + emis[i]
        path = np.zeros(len(frames), dtype=int)
        path[-1] = int(np.argmax(score))
        for i in range(len(frames) - 1, 0, -1):
            path[i - 1] = back[i, path[i]]
        rally.id_changes = int((np.diff(path) != 0).sum())

        # How clearly each half's two players were told apart.
        mate = {a: next(b for b, q in enumerate(self.players)
                        if q.squad == p.squad and b != a)
                for a, p in enumerate(self.players)}
        need = max(1, self.stream.frames(MIN_SLOT_SECONDS))
        margins: Dict[str, List[float]] = {SIDE_NEAR: [], SIDE_FAR: []}
        for i in range(len(frames)):
            st = states[path[i]]
            for j, a in enumerate(st):
                if seen[i, j]:
                    margins[sides[a]].append(value[i, j, a] - value[i, j, mate[a]])
        for side in (SIDE_NEAR, SIDE_FAR):
            m = margins[side]
            rally.slot_margin[side] = float(np.mean(m)) if len(m) >= need else None
            if rally.slot_margin[side] is None or rally.slot_margin[side] < SLOT_MIN_MARGIN:
                rally.withheld.append(side)

        steps: List[Dict[int, Tuple[int, str]]] = []
        for i in range(len(frames)):
            if i and path[i] == path[i - 1]:
                steps.append(steps[-1])
            else:
                st = states[path[i]]
                steps.append({t: (st[j], sides[st[j]]) for t, j in col.items()})
        rally.plan = (frames, steps)

    def apply(self, rally: RallyIdentity) -> None:
        """Write the rally's read into the stream: label, squad, slot and half
        of every player inside its window. Frames between two observed ones
        keep the path's state; a body outside the four tracked ids, or on a
        half whose two players could not be told apart, gets no label."""
        frames, steps = rally.plan if rally.plan is not None else ([], [])
        for f in range(rally.lo, rally.hi + 1):
            k = int(np.searchsorted(frames, f, side="right")) - 1
            step = steps[max(k, 0)] if steps else {}
            for p in self.stream.players[f]:
                hit = step.get(p.track_id)
                if hit is None:
                    _set(p, None, None)
                    continue
                player, side = hit
                _set(p, None if side in rally.withheld else self.players[player], side)


def _set(p: PlayerObs, player: Optional[_Player], side: Optional[str]) -> None:
    if player is None:
        p.label, p.squad, p.slot = None, None, None
    else:
        p.label, p.squad, p.slot = player.label, player.squad, player.slot
    if side is not None:
        p.court_side = side


def relabel(stream: MatchStream, geometry: CourtGeometry,
            spans: Sequence[Tuple[int, int]]) -> IdentityRead:
    """Read every rally and write all of them into the stream: the labels
    the reconstruction credited its touches with (same stream, same rallies,
    same read)."""
    read, reader = read_identities(stream, geometry, spans)
    if reader is not None:
        for rally in read.rallies:
            reader.apply(rally)
    return read


def read_identities(stream: MatchStream, geometry: CourtGeometry,
                    spans: Sequence[Tuple[int, int]]
                    ) -> Tuple[IdentityRead, Optional[IdentityReader]]:
    """Read who is who in every rally. Returns the read and, when it applies,
    the reader whose ``apply(rally)`` writes one rally into the stream. A
    stream without identity observations is not read: its labels stay."""
    if not stream.has_identity_observations:
        return IdentityRead(False, REASON_NO_OBSERVATIONS), None
    reader = IdentityReader(stream, geometry)
    read = reader.read(spans)
    if read.applied:
        switches = sum(1 for a, b in zip(read.rallies, read.rallies[1:])
                       if a.near_squad != b.near_squad)
        logger.info("Post-run identity: %d rallies, %d side switches, levels %s",
                    len(read.rallies), switches, read.levels)
        return read, reader
    logger.warning("Post-run identity not applied: %s", read.reason)
    return read, None
