"""Match-level sense: who won each point, the score, and the side switches.

Two independent reads of a point's winner exist and they check each other:

* **the next serve** -- rally scoring: whoever wins a point serves the next
  one. The serving half of every rally is the best-measured fact the post-run
  layer has (a serve is a 9-17 m flight from a baseline), so this is the
  primary read for every point except the last;
* **the ball's death** -- where the ball came down relative to the last
  toucher's half (into the net / own half = error, opponents' sand = kill,
  outside the lines = out). It is the only read for the last point and the
  cross-check for all the others.

When the two disagree and the death read is a confident one, the usual cause
is a touch credited AFTER the ball was already dead (a pick-up, a ball thrown
back): trailing touches are dropped until the point agrees with the serve
that followed it. Squads (1 = A, 2 = B) come from the identity labels, so a
side switch is simply the rally where the near half changes squad.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .geometry import SIDE_FAR, SIDE_NEAR, other_side
from .rallies import END_GROUND, END_NET, Rally
from .touches import (
    ACTION_DIG,
    ACTION_OVERPASS,
    ACTION_SET,
    ACTION_SPIKE,
    RallyRoster,
    Touch,
    credit_by_alternation,
)

SQUAD_LETTER = {1: "A", 2: "B"}

WINNER_NEXT_SERVE = "next_serve"
WINNER_BALL_DEATH = "ball_death"
WINNER_SCORE = "score_closes"       # last point: the only winner that ends the set

#: Ball-death reads that hinge on an in/out line call.
LINE_CALL_REASONS = ("ace", "serve_out", "landed_in", "landed_out")

OUTCOME_ACE = "ace"
OUTCOME_KILL = "kill"
OUTCOME_ERROR = "error"

# One ballistic arc from a touch to the sand takes the time gravity gives it.
# A ball that needed this much longer was touched again on the way (the
# attack the stream did not see).
ARC_SLACK_S = 0.35
# Service order is applied only when the observed servers back it this well.
ROTATION_MIN_VOTES = 4
ROTATION_MIN_AGREEMENT = 0.7


@dataclass
class Point:
    rally: Rally
    touches: List[Touch]
    roster: RallyRoster
    near_squad: Optional[int] = None
    winner_squad: Optional[int] = None
    winner_source: Optional[str] = None
    death_winner_side: Optional[str] = None     # the ball-death read (half)
    death_reason: Optional[str] = None
    flags: List[str] = field(default_factory=list)
    score_after: Dict[int, int] = field(default_factory=dict)

    @property
    def far_squad(self) -> Optional[int]:
        return None if self.near_squad is None else 3 - self.near_squad

    def squad_on(self, side: Optional[str]) -> Optional[int]:
        if side == SIDE_NEAR:
            return self.near_squad
        if side == SIDE_FAR:
            return self.far_squad
        return None

    def side_of(self, squad: Optional[int]) -> Optional[str]:
        if squad is None or self.near_squad is None:
            return None
        return SIDE_NEAR if squad == self.near_squad else SIDE_FAR

    @property
    def serve_squad(self) -> Optional[int]:
        return self.squad_on(self.rally.serve.side)


def death_winner(rally: Rally, touches: List[Touch]
                 ) -> Tuple[Optional[str], Optional[str]]:
    """(winning half, reason) from how the ball died; (None, None) = no call."""
    last = touches[-1]
    hitter = last.side
    rival = other_side(hitter)
    end = rally.end
    if end is None:
        return None, None
    if last.touch_number == 0:                        # nothing after the serve
        if rally.serve.into_net or end.kind == END_NET:
            return rival, "serve_into_net"
        if end.kind == END_GROUND and end.side == rival:
            if end.in_court is True:
                return hitter, "ace"
            if end.in_court is False:
                return rival, "serve_out"
        if end.kind == END_GROUND and end.side == hitter:
            return rival, "serve_short"
        return None, None
    if end.kind == END_NET:
        return rival, "into_net"
    if end.side == hitter:
        return rival, "died_on_own_half"
    if end.side == rival and end.kind == END_GROUND:
        if end.in_court is True:
            return hitter, "landed_in"
        if end.in_court is False:
            return rival, "landed_out"
    return None, None


class MatchAssembler:
    def __init__(self, points_to_win: int = 21, win_by: int = 2,
                 switch_every: int = 7) -> None:
        self.points_to_win = points_to_win
        self.win_by = win_by
        self.switch_every = switch_every

    def assemble(self, points: List[Point]) -> Dict[str, object]:
        self._orient(points)
        for i, pt in enumerate(points):
            nxt = points[i + 1] if i + 1 < len(points) else None
            self._decide(pt, nxt)
        score = {1: 0, 2: 0}
        for pt in points[:-1]:
            if pt.winner_squad in score:
                score[pt.winner_squad] += 1
            pt.score_after = dict(score)
        if points:
            self._decide_last(points[-1], score)
            if points[-1].winner_squad in score:
                score[points[-1].winner_squad] += 1
            points[-1].score_after = dict(score)
        for pt in points:
            self._finish_labels(pt)
            self._outcomes(pt)
            credit_by_alternation(pt.touches, pt.roster)
        rotation = self._service_order(points)
        checks = self._checks(points, score)
        checks["service_order"] = rotation
        return checks

    # -- orientation ------------------------------------------------------ #

    def _orient(self, points: List[Point]) -> None:
        for pt in points:
            near = pt.roster.squad_on(SIDE_NEAR)
            far = pt.roster.squad_on(SIDE_FAR)
            if near is None and far is not None:
                near = 3 - far
            pt.near_squad = near
        # A rally with no identity read inherits its neighbour's orientation.
        known = [pt.near_squad for pt in points]
        for i, pt in enumerate(points):
            if pt.near_squad is None:
                before = next((k for k in reversed(known[:i]) if k is not None), None)
                after = next((k for k in known[i + 1:] if k is not None), None)
                pt.near_squad = before if before is not None else after
                if pt.near_squad is not None:
                    pt.flags.append("orientation_inherited")

    # -- winners ---------------------------------------------------------- #

    def _decide(self, pt: Point, nxt: Optional[Point]) -> None:
        side, reason = death_winner(pt.rally, pt.touches)
        pt.death_winner_side, pt.death_reason = side, reason
        if nxt is None:
            return
        served = nxt.serve_squad
        if served is None:
            if side is not None:
                pt.winner_squad, pt.winner_source = pt.squad_on(side), WINNER_BALL_DEATH
            return
        pt.winner_squad, pt.winner_source = served, WINNER_NEXT_SERVE
        if side is None or pt.squad_on(side) == served:
            return
        if reason in LINE_CALL_REASONS:
            # In/out is the weakest read the layer has (a blurred box mapped
            # through a 4-click homography): the serve that followed wins.
            pt.flags.append(f"line_call_overridden:{reason}")
            return
        # The ball's death contradicts the serve that followed. Touches
        # credited after the ball was dead (a pick-up, a ball thrown back)
        # are the usual cause: drop trailing ones until it no longer does.
        trimmed = list(pt.touches)
        while len(trimmed) > 1:
            dropped = trimmed.pop()
            if not dropped.observed:
                continue
            s2, r2 = death_winner(_RallyView(pt.rally), trimmed)
            if s2 is None or pt.squad_on(s2) == served:
                pt.touches = trimmed
                pt.death_winner_side, pt.death_reason = s2, r2
                pt.flags.append("trailing_touch_dropped")
                return
        pt.flags.append(f"death_disagrees:{reason}")

    def _decide_last(self, pt: Point, score: Dict[int, int]) -> None:
        closers = [sq for sq in (1, 2) if self._is_final(
            {**score, sq: score[sq] + 1})]
        side = pt.death_winner_side
        death_squad = pt.squad_on(side) if side is not None else None
        if len(closers) == 1:
            pt.winner_squad, pt.winner_source = closers[0], WINNER_SCORE
            if death_squad is not None and death_squad != closers[0]:
                pt.flags.append(f"death_disagrees:{pt.death_reason}")
        elif death_squad is not None:
            pt.winner_squad, pt.winner_source = death_squad, WINNER_BALL_DEATH

    def _is_final(self, score: Dict[int, int]) -> bool:
        hi, lo = max(score.values()), min(score.values())
        return hi >= self.points_to_win and hi - lo >= self.win_by

    # -- labels that need the winner --------------------------------------- #

    def _finish_labels(self, pt: Point) -> None:
        """A last touch whose team WON the point: the ball came down on the
        other half. Either that touch sent it over (owner GT rule: every
        action that goes over is an overpass) or a later attack did, unseen."""
        last = pt.touches[-1]
        if last.touch_number == 0 or pt.winner_squad is None:
            return
        if pt.squad_on(last.side) != pt.winner_squad or last.action not in (
                ACTION_DIG, ACTION_SET):
            return
        if last.touch_number < 3 and self._second_arc(pt, last):
            last.ends_possession = False
            end = pt.rally.end
            pt.touches.append(Touch(
                frame=int((last.frame + end.frame) // 2), side=last.side,
                touch_number=last.touch_number + 1, action=ACTION_SPIKE,
                observed=False, squad=last.squad, ends_possession=True))
            pt.flags.append("unseen_final_attack")
        else:
            last.action = ACTION_OVERPASS

    @staticmethod
    def _second_arc(pt: Point, last: Touch) -> bool:
        """Did the ball stay up longer than ONE arc from ``last`` allows?"""
        end = pt.rally.end
        out = last.event.flight_out if last.event is not None else None
        if (end is None or end.kind != END_GROUND or out is None
                or last.height_m is None or not math.isfinite(out.peak_height_m)):
            return False
        peak = max(out.peak_height_m, last.height_m, 0.0)
        arc = (math.sqrt(2.0 * max(peak - last.height_m, 0.0) / 9.81)
               + math.sqrt(2.0 * peak / 9.81))
        stream = pt.roster.stream
        return stream.seconds(end.frame - last.frame) > arc + ARC_SLACK_S

    # -- outcomes ---------------------------------------------------------- #

    @staticmethod
    def _outcomes(pt: Point) -> None:
        """ace / kill / error on the hit that decided the point.

        Owner semantics (2026-08-31): a kill falls directly OR is dug and
        dies without a set -- so a failed FIRST touch credits the hit before
        it (the serve: ace; an attack: kill), and only a team's own second or
        third touch is its error. A touch the stream did not see decides
        nothing.
        """
        if pt.winner_squad is None:
            return
        serve, last = pt.touches[0], pt.touches[-1]
        if last.touch_number == 0:
            serve.outcome = (OUTCOME_ACE if pt.serve_squad == pt.winner_squad
                             else OUTCOME_ERROR)
            return
        if not last.observed:
            return
        if pt.squad_on(last.side) == pt.winner_squad:
            # A kill needs the ball SEEN coming down. When the track simply
            # ends after the attack, the rivals may have dug it and lost the
            # point two touches later -- their error, not this player's kill.
            end = pt.rally.end
            landed = end is not None and end.kind in (END_GROUND, END_NET)
            if landed and last.action in (ACTION_SPIKE, ACTION_OVERPASS):
                last.outcome = OUTCOME_KILL
            return
        if last.touch_number > 1:
            last.outcome = OUTCOME_ERROR
            return
        before = pt.touches[-2]
        if before.side == last.side or not before.observed:
            return
        if before.touch_number == 0:
            before.outcome = OUTCOME_ACE
        elif before.action in (ACTION_SPIKE, ACTION_OVERPASS):
            before.outcome = OUTCOME_KILL

    # -- service order ----------------------------------------------------- #

    def _service_order(self, points: List[Point]) -> Dict[str, object]:
        """Teammates alternate serving each time their team wins the serve
        back, and a server keeps serving while the team scores. The only
        freedom is who served first in each squad: one bit per squad, voted
        by every serve whose server was seen. The rotation then names the
        server of every point, including the ones nobody saw."""
        turn: Dict[int, int] = {}
        turns: List[Optional[int]] = []
        prev_squad = None
        for pt in points:
            sq = pt.serve_squad
            if sq is None:
                turns.append(None)
                prev_squad = None
                continue
            if sq != prev_squad:
                turn[sq] = turn.get(sq, -1) + 1
            turns.append(turn[sq])
            prev_squad = sq
        report: Dict[str, object] = {}
        for squad in (1, 2):
            letter = SQUAD_LETTER[squad]
            votes = {1: 0, 2: 0}        # slot that served this squad's turn 0
            for pt, t in zip(points, turns):
                player = pt.touches[0].player
                if pt.serve_squad != squad or t is None or not _is_label(player, letter):
                    continue
                slot = int(player[1])
                votes[slot if t % 2 == 0 else 3 - slot] += 1
            total = votes[1] + votes[2]
            first = 1 if votes[1] >= votes[2] else 2
            agreement = votes[first] / total if total else 0.0
            applied = total >= ROTATION_MIN_VOTES and agreement >= ROTATION_MIN_AGREEMENT
            report[letter] = {"first_server": f"P{first}{letter}" if total else None,
                              "votes": total, "agreement": round(agreement, 2),
                              "applied": applied}
            if not applied:
                continue
            for pt, t in zip(points, turns):
                if pt.serve_squad != squad or t is None:
                    continue
                slot = first if t % 2 == 0 else 3 - first
                expected = f"P{slot}{letter}"
                serve = pt.touches[0]
                if serve.player != expected:
                    pt.flags.append(f"server_from_rotation:{serve.player}->{expected}")
                    serve.player = expected
                    serve.player_source = "service_order"
        return report

    # -- checks ----------------------------------------------------------- #

    def _checks(self, points: List[Point], score: Dict[int, int]) -> Dict[str, object]:
        switches = [i for i in range(1, len(points))
                    if points[i].near_squad != points[i - 1].near_squad
                    and None not in (points[i].near_squad, points[i - 1].near_squad)]
        blocks, prev = [], 0
        for i in switches:
            blocks.append(i - prev)
            prev = i
        return {
            "points": len(points),
            "final_score": {SQUAD_LETTER[k]: v for k, v in score.items()},
            "set_complete": self._is_final(score),
            "undecided_points": [i + 1 for i, p in enumerate(points)
                                 if p.winner_squad is None],
            "side_switch_after_point": switches,
            "points_between_switches": blocks,
            "switch_blocks_ok": all(b == self.switch_every for b in blocks),
            "flagged_points": {i + 1: p.flags for i, p in enumerate(points) if p.flags},
        }


def _is_label(player: Optional[str], letter: str) -> bool:
    return bool(player and len(player) == 3 and player[0] == "P"
                and player[1] in "12" and player[2] == letter)


class _RallyView:
    """A rally whose observed end no longer applies: once its last touches are
    dropped, the landing that followed them says nothing about the rest."""

    def __init__(self, rally: Rally) -> None:
        self.serve = rally.serve
        self.end = None
