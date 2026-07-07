"""Unit tests for the context layer (action_context.py).

These exercise the gesture -> canonical-action disambiguation in isolation from
the visual layer, which is the whole point of the two-layer split: given a
sequence of visual gestures + spatial flags, the resolver must apply the rally
rules (touch counting, dig/set/overpass, serve) correctly.
"""

from src.recognition.volleyball_actions import VisualGesture
from src.recognition.action_context import resolve_actions, ActionContextResolver


def _contact(frame, gesture, near_net=True, behind_baseline=False, team="A"):
    return {
        "frame": frame,
        "gesture": gesture,
        "near_net": near_net,
        "behind_baseline": behind_baseline,
        "team": team,
    }


def _labels(contacts):
    return [e["action"] for e in resolve_actions(contacts)]


def test_receive_set_attack_possession():
    """The canonical beach pattern: dig (1st), set (2nd feeding a team-mate),
    spike (3rd, arrives as an ATTACK gesture)."""
    contacts = [
        _contact(10, VisualGesture.BUMP_SET),
        _contact(40, VisualGesture.BUMP_SET),
        _contact(70, VisualGesture.ATTACK),
    ]
    assert _labels(contacts) == ["dig", "set", "spike"]


def test_third_soft_touch_backcourt_is_dig():
    """A soft 3rd touch (bump-set) away from the net is a defensive dig -- the
    ball was kept up in open/backcourt play, not attacked."""
    contacts = [
        _contact(10, VisualGesture.BUMP_SET, near_net=False),
        _contact(40, VisualGesture.BUMP_SET, near_net=False),
        _contact(65, VisualGesture.BUMP_SET, near_net=False),
    ]
    assert _labels(contacts) == ["dig", "set", "dig"]


def test_third_soft_touch_at_net_is_spike():
    """A soft 3rd touch AT the net is an attack (a poke/roll/"cobra" that clears
    the net without a driven trajectory) -- in beach doubles the 3rd ball goes
    over. This recovers entreno_3's spike@178, which pops up softly."""
    contacts = [
        _contact(10, VisualGesture.BUMP_SET, near_net=False),  # dig (reception, deep)
        _contact(40, VisualGesture.BUMP_SET),                  # set (near net)
        _contact(65, VisualGesture.BUMP_SET),                  # 3rd at net -> spike
    ]
    assert _labels(contacts) == ["dig", "set", "spike"]


def test_second_touch_over_net_is_overpass():
    """A 2nd touch with no team-mate follow-up went over the net -> overpass."""
    contacts = [
        _contact(10, VisualGesture.BUMP_SET),   # dig (reception)
        _contact(40, VisualGesture.BUMP_SET),   # 2nd touch, nobody follows
    ]
    assert _labels(contacts) == ["dig", "overpass"]


def test_block_gesture_is_block():
    contacts = [_contact(100, VisualGesture.BLOCK)]
    assert _labels(contacts) == ["block"]


def test_serve_behind_baseline_at_rally_start():
    """A contact behind the baseline that opens a rally is a serve, whether the
    gesture is a bump (underhand) or an attack (jump serve)."""
    assert _labels([_contact(5, VisualGesture.BUMP_SET, near_net=False,
                             behind_baseline=True)]) == ["serve"]
    assert _labels([_contact(5, VisualGesture.ATTACK, near_net=False,
                             behind_baseline=True)]) == ["serve"]


def test_attack_resets_possession_touch_count():
    """After an attack the ball crosses, so the next side's touch count restarts
    -> its first bump-set is a dig, not a set."""
    contacts = [
        _contact(10, VisualGesture.BUMP_SET),   # dig
        _contact(40, VisualGesture.BUMP_SET),   # set
        _contact(70, VisualGesture.ATTACK),     # spike (resets)
        _contact(95, VisualGesture.BUMP_SET),   # dig (new possession, touch 1)
    ]
    assert _labels(contacts) == ["dig", "set", "spike", "dig"]


def test_gap_starts_new_rally():
    """A long dead-ball gap starts a fresh rally: touch count resets."""
    contacts = [
        _contact(10, VisualGesture.BUMP_SET),
        _contact(40, VisualGesture.BUMP_SET),
        _contact(400, VisualGesture.BUMP_SET),  # >reset gap later -> dig again
    ]
    labels = _labels(contacts)
    assert labels[0] == "dig" and labels[2] == "dig"


def test_streaming_matches_batch():
    """The streaming resolver (resolve one at a time + flush) matches the batch
    helper, so live and offline use agree."""
    contacts = [
        _contact(10, VisualGesture.BUMP_SET),
        _contact(40, VisualGesture.BUMP_SET),
        _contact(70, VisualGesture.ATTACK),
    ]
    batch = _labels(contacts)

    r = ActionContextResolver()
    streamed = []
    pending = None
    for c in contacts:
        if pending is not None:
            streamed.append(r.resolve(pending, c)["action"])
        pending = c
    if pending is not None:
        streamed.append(r.resolve(pending, None)["action"])

    assert streamed == batch
