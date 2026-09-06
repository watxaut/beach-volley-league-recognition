"""
Game on/off state machine for volleyball video analysis.

Two layers, both driven only by signals the pipeline already produces
(conservative ball tracker velocity + the emitted action stream -- pure
observer, never feeds back into detection/tracking/classification):

**Episode layer (causal, per frame).** The ball is *in flight* when it is
tracked and moving at >= ``flight_speed_px`` px/frame. A flight burst that
follows >= ``arm_quiet_frames`` without flight (serve-like onset: quiet
retrieval/held ball, then the serve toss+hit) arms a candidate episode. The
candidate is CONFIRMED (state GAME_ON, backdated to the burst start) if it
accumulates >= ``confirm_flight_frames`` flight frames within
``confirm_frames`` -- a real rally keeps producing ball flight, while an
isolated practice hit/serve cannot. Once ON, the state persists while the
rolling ``density_window_frames`` window holds >= ``density_min_flights``
flight frames (real rallies contain occlusion gaps of up to ~2 s, so a
single quiet gap must not end the episode); it ends when the window drains
(density starvation -- the ball is dead/rolling/retrieved) or when the ball
is tracked-but-static for ``static_off_frames`` (held ball).

**Live view (provisional, badge only).** The live state reports GAME_ON
(provisional, drawn dimmed) once the ball has been in sustained flight --
>= ``fast_confirm_flights`` flight frames in the rolling
``fast_confirm_window_frames`` window, or via the armed candidate. This
exists because a tracked serve toss splits the pre-serve quiet (the toss's
slow apex frames reset the quiet run), so the burst gate can never arm on
the serve itself and a candidate-only badge waited for the NEXT contact's
burst (~3.5 s after the serve hit on entreno_3). The provisional flag
never feeds the episode/point layers -- segmentation is unaffected.

**Point layer (grouping).** Consecutive episodes separated by <=
``group_gap_frames`` merge into one rally group (a rally whose tracking
dropped for ~2 s is one point, not two). Each group is then SPLIT at
contact silences longer than ``contact_chain_frames`` -- two rallies that
one ball-episode swallowed (practice volleying between points keeps the
ball flying) separate there, because a real rally's contacts recur quickly
(<=215 f measured) while the between-points practice produces a long
contact silence. A piece counts as a POINT when at least
``point_min_actions`` classifier actions were detected inside it -- this
is what separates counted points from uncounted practice exchanges, which
are ball-motion-indistinguishable from rallies (validated on
resources/video_entreno_game_state.mp4 vs
ground_truth/gt_point_start_end.txt: 11/13 points, 0 false, 0 merged;
the two misses are action-recall-limited, not machine logic).

All frame-based parameters assume ~30 fps (the project's videos are 30 fps).
"""

from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

from .game_state import GamePoint, GameState, GameStateInfo

# The action classifier releases a contact only when the NEXT contact
# arrives (or after its reset gap) -- measured emission lags on the
# game-state video reach ~400 frames (median 60), so a group must not be
# finalized before a still-pending action could land in it.
_ACTION_LOOKAHEAD_FRAMES = 450


class GameStateManager:
    """Game on/off state machine (episode + point layers)."""

    def __init__(self, config: Dict[str, Any]):
        cfg = config.get("game_state_detection", {})
        self.enabled = cfg.get("enabled", True)
        # Episode layer
        self.flight_speed_px = cfg.get("flight_speed_px", 8.0)
        self.arm_quiet_frames = cfg.get("arm_quiet_frames", 10)
        self.serve_burst_frames = cfg.get("serve_burst_frames", 8)
        self.burst_gap_frames = cfg.get("burst_gap_frames", 6)
        self.confirm_frames = cfg.get("confirm_frames", 90)
        self.confirm_flight_frames = cfg.get("confirm_flight_frames", 20)
        self.density_window_frames = cfg.get("density_window_frames", 90)
        self.density_min_flights = cfg.get("density_min_flights", 20)
        self.static_off_frames = cfg.get("static_off_frames", 40)
        # Point layer
        self.group_gap_frames = cfg.get("group_gap_frames", 60)
        self.point_min_actions = cfg.get("point_min_actions", 2)
        self.contact_chain_frames = cfg.get("contact_chain_frames", 240)
        # Serve-init semantics (owner, 2026-09-05): the LIVE state should turn
        # ON at the serve (~1s), not after the 90f confirmation window; and a
        # classifier serve action arms a candidate instantly. Neither affects
        # point segmentation (that keeps the validated delayed confirm).
        # fast_confirm_window_frames backs the rolling-flight provisional
        # (2026-09-05, round 3): the badge must keep up with a tracked-toss
        # serve even when the burst gate cannot arm (quiet split by the toss).
        self.fast_confirm_flights = cfg.get("fast_confirm_flights", 20)
        self.fast_confirm_window_frames = cfg.get("fast_confirm_window_frames", 90)
        self.serve_action_arms = cfg.get("serve_action_arms", True)

        self._reset_state()

    # ------------------------------------------------------------------
    # state
    # ------------------------------------------------------------------

    def _reset_state(self) -> None:
        self.state = GameState.GAME_OFF
        self.provisional = False   # fast serve-track ON (points unaffected)
        self.last_frame_seen: Optional[int] = None
        # flight bookkeeping
        self._last_flight_frame: Optional[int] = None
        self._no_flight_run = 0
        self._static_run = 0
        self._burst_start: Optional[int] = None
        self._burst_quiet = 0
        # candidate episode (arming/confirming)
        self._candidate: Optional[int] = None
        self._candidate_flights = 0
        # active episode
        self._episode_start: Optional[int] = None
        self._density: Deque[bool] = deque(maxlen=self.density_window_frames)
        # live-view rolling flight window (provisional badge only -- never
        # feeds the episode/point layers)
        self._live_flights: Deque[bool] = deque(maxlen=self.fast_confirm_window_frames)
        # rally group under construction: [start, last_episode_end]
        self._group: Optional[List[int]] = None
        # contact frames of every action observed so far (the point layer
        # counts them at group-finalize time by contact frame -- an action's
        # emission is delayed by the classifier's look-ahead, so counting at
        # arrival time would drop a rally's early contacts)
        self._seen_action_frames: List[int] = []
        # finalized output
        self.points: List[GamePoint] = []

    def reset(self) -> None:
        """Reset all state (live-debug restart)."""
        self._reset_state()

    # ------------------------------------------------------------------
    # per-frame update
    # ------------------------------------------------------------------

    def analyze_frame(self, frame_result: Dict[str, Any], frame_number: int) -> GameStateInfo:
        """Advance the machine one frame.

        Must be called once per frame, AFTER action classification (the
        point layer counts the frame's emitted actions).
        """
        if not self.enabled:
            return GameStateInfo(GameState.GAME_OFF, frame_number, points=list(self.points))

        ball = frame_result.get("tracked_ball")
        speed = self._ball_speed(ball)
        tracked = (
            ball is not None
            and ball.get("center") is not None
            and ball["center"][0] is not None
        )
        # frames where the tracker reports a position but no velocity (first
        # frame after re-acquisition) count as tracked-but-not-flight
        actions = frame_result.get("actions") or []
        self._step(frame_number, tracked, speed, actions)
        self.last_frame_seen = frame_number

        effective_state = (
            GameState.GAME_ON
            if (self.state == GameState.GAME_ON or self.provisional)
            else GameState.GAME_OFF
        )
        eff_start = (
            self._episode_start
            if self.state == GameState.GAME_ON
            else (self._candidate if self.provisional else None)
        )
        return GameStateInfo(
            current_state=effective_state,
            frame_number=frame_number,
            episode_start_frame=eff_start,
            episode_frames=(frame_number - eff_start + 1) if eff_start is not None else 0,
            points=list(self.points),
            provisional=(self.provisional and self.state == GameState.GAME_OFF),
        )

    @staticmethod
    def _ball_speed(ball: Optional[Dict[str, Any]]) -> Optional[float]:
        if not ball:
            return None
        v = ball.get("velocity")
        if not v:
            return None
        return (v[0] ** 2 + v[1] ** 2) ** 0.5

    # ------------------------------------------------------------------
    # episode layer
    # ------------------------------------------------------------------

    def _step(
        self,
        f: int,
        tracked: bool,
        speed: Optional[float],
        actions: List[Dict[str, Any]],
    ) -> None:
        flight = tracked and speed is not None and speed >= self.flight_speed_px
        static = tracked and speed is not None and speed < 3.0
        quiet_before = self._no_flight_run

        if flight:
            if self._last_flight_frame is None or f - self._last_flight_frame > self.burst_gap_frames:
                self._burst_start = f
                self._burst_quiet = quiet_before
            self._no_flight_run = 0
            self._static_run = 0
            self._last_flight_frame = f
        else:
            self._no_flight_run += 1
            self._static_run = self._static_run + 1 if static else 0

        # rolling flight-density window (episode-layer continuation check)
        self._density.append(flight)
        while len(self._density) > self.density_window_frames:
            self._density.popleft()
        # rolling flight window for the live-view provisional badge
        self._live_flights.append(flight)
        while len(self._live_flights) > self.fast_confirm_window_frames:
            self._live_flights.popleft()

        if self.state == GameState.GAME_OFF:
            # -- serve-init semantics: a classifier serve action arms a
            # candidate instantly (no burst/quiet gate) -- the pipeline's own
            # serve detection is the strongest point-start signal we have.
            # Only recent contacts qualify (emission lags reach ~400f).
            if self.serve_action_arms and self._candidate is None:
                for a in actions:
                    if a.get("action") == "serve":
                        af = self._action_frame(a)
                        if af is not None and 0 <= f - af <= 45:
                            self._candidate = af
                            self._candidate_flights = 1 if flight else 0
                            break
            if flight:
                if self._candidate is None:
                    burst_len = f - (self._burst_start or f) + 1
                    if (
                        burst_len >= self.serve_burst_frames
                        and self._burst_quiet >= self.arm_quiet_frames
                    ):
                        self._candidate = self._burst_start
                        self._candidate_flights = 1
                else:
                    self._candidate_flights += 1
            if self._candidate is not None and f - self._candidate >= self.confirm_frames:
                if self._candidate_flights >= self.confirm_flight_frames:
                    self._episode_start = self._candidate
                    self._group_start(self._episode_start)
                    self.state = GameState.GAME_ON
                self._candidate = None
                self._candidate_flights = 0
                self.provisional = False
        else:
            end_episode = False
            if (
                len(self._density) >= self.density_window_frames
                and sum(self._density) < self.density_min_flights
            ):
                end_episode = True  # density starvation: ball dead/retrieved
            elif self._static_run >= self.static_off_frames:
                end_episode = True  # held ball
            if end_episode:
                end = (self._last_flight_frame + 1) if self._last_flight_frame is not None else f
                self._group_episode_end(end)
                self.state = GameState.GAME_OFF
                self._episode_start = None
                self._candidate = None
                self._candidate_flights = 0
                self._density.clear()

        # -- point layer bookkeeping (after transitions: same-frame actions
        # must land in the group the transition opened/extended) --
        self._group_step(f, actions)
        # -- provisional fast ON: report GAME_ON in the live view once the
        # ball has been in sustained flight -- EITHER via the armed candidate
        # (burst-after-quiet shape) OR via the rolling flight window. The
        # window is what makes the badge keep up with a serve whose toss is
        # tracked: the toss's slow apex frames split the pre-serve quiet, the
        # burst gate can then never arm (measured quiet 6 < 10 on entreno_3)
        # and the candidate-only badge waited for the NEXT contact's burst
        # (~3.5s after the serve hit). Points still wait for the validated
        # candidate confirmation; this flag drives only the live badge/CSV
        # state, so segmentation is unaffected.
        if self.fast_confirm_flights > 0 and self.state == GameState.GAME_OFF:
            sustained = sum(self._live_flights) >= self.fast_confirm_flights
            armed = (
                self._candidate is not None
                and self._candidate_flights >= self.fast_confirm_flights
            )
            self.provisional = sustained or armed

    # ------------------------------------------------------------------
    # point layer
    # ------------------------------------------------------------------

    def _group_start(self, episode_start: int) -> None:
        if self._group is not None:
            if episode_start - self._group[1] > self.group_gap_frames:
                # gap too large: the previous rally group is closed
                self._finalize_group()
        if self._group is None:
            self._group = [episode_start, episode_start]
        else:
            self._group[1] = max(self._group[1], episode_start)

    def _group_episode_end(self, episode_end: int) -> None:
        if self._group is not None:
            self._group[1] = max(self._group[1], episode_end)

    def _group_step(self, f: int, actions: List[Dict[str, Any]]) -> None:
        """Record action contact frames; finalize stale groups."""
        for a in actions:
            af = self._action_frame(a)
            if af is not None:
                self._seen_action_frames.append(af)
        # A group finalizes once neither a new episode can extend it (gap
        # expired) nor a still-pending classifier action can land in it.
        if self._group is not None and self.state == GameState.GAME_OFF:
            finalize_after = max(self.group_gap_frames, _ACTION_LOOKAHEAD_FRAMES)
            if self._candidate is None and f - self._group[1] > finalize_after:
                self._finalize_group()

    def _finalize_group(self) -> None:
        if self._group is None:
            return
        start, end = self._group
        contacts = sorted(
            af for af in self._seen_action_frames if start <= af <= end
        )
        # Split at contact gaps: a rally's contacts recur quickly (measured
        # <=215f in-rally on the game-state video); two rallies inside one
        # ball-episode group are separated by a long contact silence (the
        # between-points practice produces no/few contacts). First piece
        # keeps the group start, last keeps the group end.
        pieces = []
        if len(contacts) >= 2:
            cuts = [k for k in range(1, len(contacts)) if contacts[k] - contacts[k - 1] > self.contact_chain_frames]
            starts = [start] + [contacts[k] for k in cuts]
            ends = [contacts[k - 1] for k in cuts] + [end]
            pieces = list(zip(starts, ends))
        else:
            pieces = [(start, end)]
        for (p0, p1) in pieces:
            n = sum(1 for af in contacts if p0 <= af <= p1)
            if n >= self.point_min_actions:
                self.points.append(GamePoint(p0, p1, n))
        # seen-action frames before the group can never matter again
        self._seen_action_frames = [af for af in self._seen_action_frames if af > end]
        self._group = None

    def observe_flushed_actions(self, actions: List[Dict[str, Any]]) -> None:
        """Feed the classifier's flushed (lookahead-released) actions.

        Called once after the last frame; their contact frames join the
        seen-action list before finish() finalizes the trailing group.
        """
        for a in actions:
            af = self._action_frame(a)
            if af is not None:
                self._seen_action_frames.append(af)

    @staticmethod
    def _action_frame(a: Dict[str, Any]) -> Optional[int]:
        """An action's CONTACT frame (``frame_number``; ``frame`` accepted)."""
        return a.get("frame_number", a.get("frame"))

    def finish(self) -> List[GamePoint]:
        """Finalize the trailing group. Call once after the last frame."""
        if self._group is not None:
            # a video that ends mid-rally: the group extends to the last
            # flight (mirrors the episode-end convention). Only while the
            # episode is still ACTIVE -- stray flights after the episode
            # closed (rolling balls in the tail) must not extend it.
            if self.state == GameState.GAME_ON and self._last_flight_frame is not None:
                self._group[1] = max(self._group[1], self._last_flight_frame + 1)
        self._finalize_group()
        return list(self.points)

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def get_current_state(self) -> GameState:
        return self.state

    def get_points(self) -> List[GamePoint]:
        return list(self.points)

    def is_point_frame(self, frame_number: int) -> Optional[int]:
        """Index of the point containing ``frame_number``, else None."""
        for i, p in enumerate(self.points):
            if p.start_frame <= frame_number <= p.end_frame:
                return i
        return None
