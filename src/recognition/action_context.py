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
a long dead-ball gap. A cross on a NON-attack touch is caught two ways: the
4th-touch wrap (a side gets at most 3 touches) and, when the contact carries
the ball's width-side evidence, the WIDTH-CONFIRMED CROSS -- a would-be-3rd+
touch by the other team with the ball demonstrably on the toucher's side
flips the possession at the crossing contact itself instead of one contact
late (e7 f195/f242: the unemitted f160 spike starved the count and the late
wrap mislabeled the next set as a possession-opening block).

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

    def __init__(self, rally_reset_gap: int = 90, spike_on_net_touch3: bool = True):
        self.rally_reset_gap = rally_reset_gap
        # Whether a soft 3rd touch at the net is read as an attack (spike) rather
        # than a dig. True fits beach doubles (the 3rd ball almost always goes
        # over); set False for drills where players rally the ball up at the net.
        self.spike_on_net_touch3 = spike_on_net_touch3
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
        ``near_net`` (bool) and ``behind_baseline`` (bool). It may also carry
        ``team`` (per-contact foot team), ``ball_side`` (the ball's width-side
        evidence, when team-aware attribution is on) and ``contact_kind``
        (bounce/redirect/drive/reentry) -- used by the width-confirmed cross
        and the own-side drive-block rules below. ``next_contact`` is the
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
        ball_side = contact.get("ball_side")
        kind = contact.get("contact_kind")

        gap = None if self._prev_frame is None else frame - self._prev_frame
        new_rally = gap is None or gap > self.rally_reset_gap
        attack_before = self._prev_action in ATTACK_ACTIONS

        # Width-confirmed cross (e7 f195, 2026-09-12): a NON-attack touch that
        # would be the 3rd-or-later of the latched possession, by the OTHER
        # team, with the ball's width side ON the toucher's side, means the
        # ball crossed at an earlier unemitted touch -- the possession flips
        # HERE. This fires the old 4th-touch wrap rule at the actual crossing
        # contact instead of one contact late (the wrap's late reset is what
        # read e7's f242 set as a possession-opening touch 1). Gates:
        #   * would-be touch >= 3: the latched side demonstrably played >=2
        #     touches first; a would-be-2 team change is more often a missed
        #     reception or an attribution wobble (e2 f118's GT set must keep
        #     its touch-2 read even though its team field differs from the
        #     latched possession -- the real possession opener, e2's f90 dig,
        #     is structurally invisible);
        #   * ball_side == team (positive width evidence, no abstain): the
        #     ball is demonstrably on the toucher's side (e5 f298's flip is
        #     refused because its over-set ball still reads the setter's
        #     regime; its GT t1 stays cosmetic);
        #   * not attack_before / not new_rally: those resets already exist.
        cross_flip = (
            not attack_before
            and not new_rally
            and team is not None
            and self._possession_team is not None
            and team != self._possession_team
            and self._poss_touch + 1 >= 3
            and ball_side is not None
            and ball_side == team
        )
        new_possession = new_rally or attack_before or cross_flip

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

        # A drive-band overhead read with the ball demonstrably on the
        # TOUCHER'S OWN side cannot be a block: you cannot block your own
        # side's ball. e7 f242 -- A's hands-overhead set at the net (drive
        # band, width committed A on A's toucher) read block and the wrap's
        # late reset made it touch 1, so the block gate kept it. Redirect-band
        # blocks keep the block unconditionally: that is the stuffed-attack
        # shape (e1's joust emission sits there), and its width usually
        # abstains at the tape anyway (e6 f309). Width-abstaining drive-band
        # reads keep the block too -- only positive own-side evidence
        # refutes it.
        own_side_drive_block = (
            kind == "drive"
            and ball_side is not None
            and team is not None
            and ball_side == team
        )

        action, confidence = self._decide(
            gesture, touch, near_net, behind_baseline, new_rally, next_contact,
            frame, own_side_drive_block,
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
                next_contact, frame, own_side_drive_block=False):
        # Attacks and blocks are already unambiguous from the gesture.
        if gesture == VisualGesture.ATTACK:
            if behind_baseline and rally_start:
                return VolleyballAction.SERVE, 0.8
            return VolleyballAction.SPIKE, 0.65 if touch >= 3 else 0.55
        if gesture == VisualGesture.BLOCK:
            # A block is definitionally the FIRST touch after an attack. At
            # the third touch of a continuing possession there is nothing to
            # block: a hands-overhead horizontal redirect there is the beach
            # POKE over the block (owner, e6 f309/311 -- soft tip floating
            # deep to the back corner), so let it fall through to the
            # touch-3 attack rule below. Touch 1 keeps the block; touch 2
            # keeps it too (no counterevidence; e1's joust emission sits
            # there and must not cascade) -- except the own-side drive-band
            # read, which is a set misread as a block (e7 f242) and falls
            # through to the touch-position rules.
            if touch < 3 and not own_side_drive_block:
                return VolleyballAction.BLOCK, 0.7
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
        # Third (or later) touch. At the net a soft third touch is still an
        # attack -- in beach doubles the third ball almost always goes over, and
        # a poke/roll/"cobra" clears the net without the driven trajectory that
        # the ATTACK gesture keys on. Deep in the court it is a defensive dig.
        if near_net and self.spike_on_net_touch3:
            return VolleyballAction.SPIKE, 0.5
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
