"""Rally-state tracking for volleyball action labeling.

Computes team_in_possession, touch_number, preceded_by_attack, and rally_id
for a sequence of action events. Used by `scripts/annotate_video.py` to
auto-fill rally context for the labeller; will also feed the future
context-disambiguator layer of the action classifier (distinguishing e.g.
dig vs set, which are visually identical but differ by rally context).
"""

from typing import Any, Dict, List, Optional


class RallyStateTracker:
    """Streaming version of :func:`compute_rally_state` for the live classifier.

    Feed it one ball-contact at a time (in chronological order) via
    :meth:`observe`; it returns the rally context that contact inherits
    (rally_id, team_in_possession, touch_number, preceded_by_attack) using the
    same state machine as the batch function. After the contact's action label
    is decided, call :meth:`commit` so ``preceded_by_attack`` can be computed
    for the next contact.

    A gap-based rally reset is added on top of the batch semantics: if more than
    ``rally_reset_gap`` frames pass with no contact, the ball is assumed dead and
    the next contact starts a fresh rally (possession/touch reset). The batch
    labeller never needs this because a human segments rallies by hand.
    """

    def __init__(self, rally_reset_gap: int = 90):
        self.rally_reset_gap = rally_reset_gap
        self.rally_id = 0
        self.current_possession: Optional[str] = None
        self.current_touch = 0
        self._prev_action: Optional[str] = None
        self._prev_team: Optional[str] = None
        self._prev_frame: Optional[int] = None

    def observe(self, frame: int, team: Optional[str]) -> Dict[str, Any]:
        """Register a contact by ``team`` at ``frame``; return its rally context."""
        team = team or "?"

        rally_reset = (
            self._prev_frame is not None
            and frame - self._prev_frame > self.rally_reset_gap
        )
        if rally_reset:
            self.current_possession = None

        if self.current_possession is None or team != self.current_possession:
            if self.current_possession is None:
                self.rally_id += 1
            self.current_possession = team
            self.current_touch = 1
        else:
            self.current_touch += 1

        preceded_by_attack = bool(
            self._prev_action in ("spike", "serve")
            and self._prev_team is not None
            and self._prev_team != team
            and not rally_reset
        )

        self._prev_team = team
        self._prev_frame = frame
        return {
            "rally_id": self.rally_id,
            "team_in_possession": self.current_possession,
            "touch_number": self.current_touch,
            "preceded_by_attack": preceded_by_attack,
        }

    def commit(self, action: str) -> None:
        """Record the label chosen for the most recent contact."""
        self._prev_action = action

    def reset(self) -> None:
        self.__init__(self.rally_reset_gap)


def compute_rally_state(events: List[Dict[str, Any]]) -> None:
    """Walk events chronologically and fill rally-state fields in place.

    State machine: IDLE -> TEAM_X_POSSESSION -> TEAM_Y_POSSESSION -> IDLE.
    A new possession starts when the current event's player_team differs
    from the previous event's team_in_possession; touch_number resets to 1
    on each possession change, otherwise increments. preceded_by_attack is
    True when the previous event was a spike or serve by the other team.
    rally_id increments on the first event of each new rally.

    Per-event overrides (event["overrides"]) are applied after auto-
    computation and cascade into the state used for the next event, so a
    manual correction propagates forward through the sequence.

    Args:
        events: List of action event dicts. Each must have at least "frame"
            (int), "final_action" (str), and "player_team" (str, "A"/"B"/"?").
            Rally-state fields are written on the dict in place.
    """
    if not events:
        return

    indexed = sorted(enumerate(events), key=lambda iv: iv[1]["frame"])

    rally_id = 0
    current_possession: Optional[str] = None
    current_touch = 0
    prev_event: Optional[Dict[str, Any]] = None

    for _, event in indexed:
        team = event.get("player_team") or "?"
        prev_final = prev_event.get("final_action") if prev_event else None
        prev_possession = prev_event.get("team_in_possession") if prev_event else None

        if current_possession is None or team != current_possession:
            if current_possession is None:
                rally_id += 1
            current_possession = team
            current_touch = 1
        else:
            current_touch += 1

        preceded_by_attack = bool(
            prev_final in ("spike", "serve")
            and prev_possession is not None
            and prev_possession != team
        )

        event["team_in_possession"] = current_possession
        event["touch_number"] = current_touch
        event["preceded_by_attack"] = preceded_by_attack
        event["rally_id"] = rally_id

        overrides = event.get("overrides") or {}
        if "team_in_possession" in overrides:
            event["team_in_possession"] = overrides["team_in_possession"]
            current_possession = overrides["team_in_possession"]
        if "touch_number" in overrides:
            event["touch_number"] = overrides["touch_number"]
            current_touch = overrides["touch_number"]

        prev_event = event
