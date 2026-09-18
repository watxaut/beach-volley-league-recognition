"""Unit tests for the context layer (action_context.py).

These exercise the gesture -> canonical-action disambiguation in isolation from
the visual layer, which is the whole point of the two-layer split: given a
sequence of visual gestures + spatial flags, the resolver must apply the rally
rules (touch counting, dig/set/overpass, serve) correctly.
"""

from src.recognition.volleyball_actions import VisualGesture
from src.recognition.action_context import resolve_actions, ActionContextResolver


def _contact(frame, gesture, near_net=True, behind_baseline=False, team="A",
            ball_side=None, contact_kind=None):
    return {
        "frame": frame,
        "gesture": gesture,
        "near_net": near_net,
        "behind_baseline": behind_baseline,
        "team": team,
        "ball_side": ball_side,
        "contact_kind": contact_kind,
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


def test_block_gesture_at_touch3_is_a_poke_spike():
    """A block is definitionally the FIRST touch after an attack: at the 3rd
    touch of a CONTINUING possession nothing exists to block, so a
    hands-overhead horizontal redirect there is the beach poke over the block
    (owner, e6 f309/311: soft tip deep to the back corner). The pose jitter
    that read the poke as BLOCK on the production path must not flip the
    label. Touch 1 keeps the block; touch 2 keeps it too (e1's joust
    emission sits there and must not cascade)."""
    dig_set_poke = [
        _contact(10, VisualGesture.BUMP_SET, near_net=False),  # dig
        _contact(40, VisualGesture.BUMP_SET),                  # set
        _contact(65, VisualGesture.BLOCK),                     # poke -> spike
    ]
    assert _labels(dig_set_poke) == ["dig", "set", "spike"]
    assert _labels([_contact(100, VisualGesture.BLOCK)]) == ["block"]  # touch 1
    assert _labels([
        _contact(10, VisualGesture.BUMP_SET),
        _contact(40, VisualGesture.BLOCK),                     # touch 2: keep
    ]) == ["dig", "block"]


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


def _e7_rally():
    """The e7 shape the width-confirmed cross fixes (2026-09-12): B's dig+set
    are emitted, B's 3rd-touch spike (GT f160) is NOT (its toucher is
    untracked, attribution by design), so A's reception (GT f197) lands on the
    would-be 3rd count and A's hands-overhead set at the net (GT f243) reads
    as a 4th-touch wrap -> touch 1 -> kept as a block by the touch-1 block
    gate. With the ball's width side on A's toucher at both contacts, the
    possession flips at the reception and the set reads set."""
    return [
        _contact(25, VisualGesture.BUMP_SET, near_net=False, behind_baseline=True,
                 team="A"),
        _contact(59, VisualGesture.BUMP_SET, team="B", ball_side="B"),
        _contact(112, VisualGesture.BUMP_SET, team="B", ball_side="B"),
        _contact(195, VisualGesture.BUMP_SET, near_net=False, team="A",
                 ball_side="A"),
        _contact(242, VisualGesture.BLOCK, team="A", ball_side="A",
                 contact_kind="drive"),
        _contact(316, VisualGesture.BUMP_SET, team="B", ball_side="B"),
    ]


def test_width_confirmed_cross_flips_possession_at_the_crossing_contact():
    """e7 f195/f242: the would-be-3rd touch by the other team with the ball's
    width side on the toucher flips the possession THERE (the wrap fired one
    contact late), so the reception is t1 and the next touch is t2 -- and the
    own-side drive-band block read falls through to the touch-2 set rule."""
    out = resolve_actions(_e7_rally())
    assert [(e["action"], e["touch_number"]) for e in out] == [
        ("serve", 1), ("dig", 1), ("set", 2),
        ("dig", 1), ("set", 2), ("dig", 1),
    ]


def test_cross_flip_needs_width_evidence():
    """Without ball_side (width abstains / uncalibrated court) the old wrap
    behavior stands: the would-be-3rd cross stays touch 3 and the next touch
    wraps to touch 1 -- where the drive-band block read stays a block."""
    contacts = [dict(c, ball_side=None) for c in _e7_rally()]
    out = resolve_actions(contacts)
    assert [(e["action"], e["touch_number"]) for e in out] == [
        ("serve", 1), ("dig", 1), ("set", 2),
        ("dig", 3), ("block", 1), ("dig", 1),
    ]


def test_cross_flip_refused_at_would_be_touch_2():
    """e2 f118 protection: a team change on the would-be 2ND touch does not
    flip -- the real possession opener (e2's f90 dig) may simply be missing,
    and the touch-2 set must keep its read."""
    contacts = [
        _contact(32, VisualGesture.BUMP_SET, near_net=False, team="A"),
        _contact(118, VisualGesture.BUMP_SET, team="B", ball_side="B"),
        _contact(204, VisualGesture.BUMP_SET, near_net=False, team="A",
                 ball_side="A"),
    ]
    out = resolve_actions(contacts)
    assert [(e["action"], e["touch_number"]) for e in out] == [
        ("dig", 1), ("set", 2), ("dig", 3),
    ]


def test_cross_flip_needs_team_change():
    """Same team on the would-be 3rd touch is an ordinary 3rd touch (e6 f309:
    A digs, A sets, A's touch-3 block gesture still resolves via the
    touch-3-at-net spike rule)."""
    contacts = [
        _contact(10, VisualGesture.BUMP_SET, near_net=False, team="A"),
        _contact(40, VisualGesture.BUMP_SET, team="A", ball_side="A"),
        _contact(65, VisualGesture.BLOCK, team="A", ball_side="A",
                 contact_kind="drive"),
    ]
    out = resolve_actions(contacts)
    assert [e["action"] for e in out] == ["dig", "set", "spike"]


def test_own_side_drive_block_falls_through_redirect_band_kept():
    """The own-side refutation is scoped to the DRIVE band with positive
    width evidence: a redirect-band block (the stuffed-attack shape, e1's
    joust) keeps the block even when width commits, and a drive-band block
    with width abstaining keeps it too (e6 f309 shape at touch 1)."""
    redirect = [
        _contact(10, VisualGesture.BUMP_SET, near_net=False, team="A",
                 ball_side="A"),
        _contact(58, VisualGesture.BLOCK, team="A", ball_side="A",
                 contact_kind="redirect"),
    ]
    assert [e["action"] for e in resolve_actions(redirect)] == ["dig", "block"]

    abstaining = [
        _contact(10, VisualGesture.BUMP_SET, near_net=False, team="A"),
        _contact(58, VisualGesture.BLOCK, team="A", ball_side=None,
                 contact_kind="drive"),
    ]
    assert [e["action"] for e in resolve_actions(abstaining)] == ["dig", "block"]


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
