"""
Context layer for action recognition.

The visual layer (`action_classifier.py`) reports a context-free
:class:`VisualGesture` at each ball contact. This module turns a sequence of
those gestures into canonical :class:`VolleyballAction` labels using rally
context -- the piece that a single frame can never provide.

Why a separate layer? A forearm bump-set is visually identical whether it is a
dig, a set, or an overpass; the only thing that distinguishes them is *when in
the rally it happened and what happens next*:

- the **first** touch of a side's possession is a reception -> ``dig``;
- the **second** touch, when a team-mate then plays the ball, is a ``set``;
- a second touch that instead goes over the net (nobody follows up) is an
  ``overpass``;
- a contact behind the baseline that opens a rally is a ``serve``.

Touches are counted per possession under the 3-touch rule: an attack
(spike/serve/block) sends the ball over, so the count resets after one, as does
a long dead-ball gap. This attack-based counting avoids depending on per-player
team assignment, which is unreliable for players straddling the net.

The resolver needs a one-contact look-ahead (to tell a set from an overpass), so
it finalises each contact when the next one arrives; :func:`resolve_actions`
applies it over a full list, and :class:`ActionContextResolver` supports the
same streaming use from the live classifier.
"""

from typing import Any, Dict, List, Optional

from .volleyball_actions import VisualGesture, VolleyballAction

ATTACK_ACTIONS = {
    VolleyballAction.SPIKE,
    VolleyballAction.SERVE,
    VolleyballAction.BLOCK,
}


class ActionContextResolver:
    """Resolve context-free gestures into canonical actions using rally state."""

    def __init__(self, rally_reset_gap: int = 90):
        self.rally_reset_gap = rally_reset_gap
        self.reset()

    def reset(self) -> None:
        self._prev_frame: Optional[int] = None
        self._prev_action: Optional[VolleyballAction] = None
        self._poss_touch = 0
        self._rally_id = 0
        self._possession_team: Optional[str] = None

    def resolve(
        self, contact: Dict[str, Any], next_contact: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Finalise one gesture-contact given the following contact (or None).

        ``contact`` must carry ``frame`` (int), ``gesture`` (:class:`VisualGesture`),
        ``near_net`` (bool) and ``behind_baseline`` (bool). ``next_contact`` is the
        chronologically following contact, used only to tell a set from an
        overpass; pass None for the last contact of a video.

        Returns a dict with ``action`` (canonical string), ``confidence`` and the
        rally context (``touch_number``, ``rally_id``, ``team_in_possession``).
        """
        frame = contact["frame"]
        gesture = contact.get("gesture", VisualGesture.UNKNOWN)
        near_net = bool(contact.get("near_net"))
        behind_baseline = bool(contact.get("behind_baseline"))
        team = contact.get("team")

        gap = None if self._prev_frame is None else frame - self._prev_frame
        new_rally = gap is None or gap > self.rally_reset_gap
        attack_before = self._prev_action in ATTACK_ACTIONS
        new_possession = new_rally or attack_before

        if new_rally:
            self._rally_id += 1

        if new_possession:
            self._poss_touch = 1
        else:
            self._poss_touch += 1
            if self._poss_touch > 3:
                # A side gets at most 3 touches; a 4th means the ball crossed and
                # we are now watching the other side's reception.
                self._poss_touch = 1
                new_possession = True
        touch = self._poss_touch

        if new_possession:
            self._possession_team = team

        action, confidence = self._decide(
            gesture, touch, near_net, behind_baseline, new_rally, next_contact, frame
        )

        self._prev_frame = frame
        self._prev_action = action

        return {
            "action": action.value,
            "confidence": round(confidence, 3),
            "touch_number": touch,
            "rally_id": self._rally_id,
            "team_in_possession": self._possession_team,
            "new_possession": new_possession,
        }

    def _decide(self, gesture, touch, near_net, behind_baseline, rally_start,
                next_contact, frame):
        # Attacks and blocks are already unambiguous from the gesture.
        if gesture == VisualGesture.ATTACK:
            if behind_baseline and rally_start:
                return VolleyballAction.SERVE, 0.8
            return VolleyballAction.SPIKE, 0.65 if touch >= 3 else 0.55
        if gesture == VisualGesture.BLOCK:
            return VolleyballAction.BLOCK, 0.7

        # A bump-set: resolve by where we are in the possession.
        if behind_baseline and rally_start:
            return VolleyballAction.SERVE, 0.75
        if touch == 1:
            # Reception of the incoming ball.
            return VolleyballAction.DIG, 0.55
        if touch == 2:
            # A set feeds a team-mate; if no one follows up in this rally the
            # ball went over instead -> overpass.
            has_follow = (
                next_contact is not None
                and (next_contact["frame"] - frame) <= self.rally_reset_gap
            )
            if has_follow:
                return VolleyballAction.SET, 0.6
            return VolleyballAction.OVERPASS, 0.45
        # Third (or later) soft touch: in open/defensive play this is another
        # dig. A genuine third-touch attack arrives as an ATTACK gesture above.
        return VolleyballAction.DIG, 0.5


def resolve_actions(
    contacts: List[Dict[str, Any]], rally_reset_gap: int = 90
) -> List[Dict[str, Any]]:
    """Resolve a full, chronologically-ordered list of gesture-contacts.

    Returns each input contact merged with its resolved ``action`` and rally
    context. Non-mutating: input dicts are copied.
    """
    ordered = sorted(contacts, key=lambda c: c["frame"])
    resolver = ActionContextResolver(rally_reset_gap=rally_reset_gap)
    out: List[Dict[str, Any]] = []
    for i, contact in enumerate(ordered):
        nxt = ordered[i + 1] if i + 1 < len(ordered) else None
        resolved = resolver.resolve(contact, nxt)
        merged = dict(contact)
        merged.update(resolved)
        # Keep the visual gesture as a readable string alongside the final label.
        g = merged.get("gesture")
        merged["gesture"] = g.value if isinstance(g, VisualGesture) else g
        out.append(merged)
    return out
