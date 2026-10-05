"""Squad-colour/label styling tests for the E3 overlay path.

player_box_style() maps a tracked-player dict (player_label/squad/slot) to a
stable per-squad box colour + display label; draw_player() must honour an
explicit colour/label over the legacy green/action tint. These are pure
functions over frames -- no weights, no video.
"""
import numpy as np
import pytest

from src.output_gen import overlay


def _player(label=None, squad=None, slot=None, tid=2):
    return {"track_id": tid, "player_label": label, "squad": squad, "slot": slot}


def test_box_style_requires_the_full_triple():
    # A label without squad/slot (shouldn't happen, but be safe) falls back
    # to (None, None) so draw_player uses the legacy green path.
    assert overlay.player_box_style(_player(label="P1A")) == (None, None)
    assert overlay.player_box_style(_player(squad=1, slot="A")) == (None, None)
    assert overlay.player_box_style(_player()) == (None, None)


@pytest.mark.parametrize(
    "label,squad,slot",
    [("P1A", 1, "A"), ("P1B", 1, "B"), ("P2A", 2, "A"), ("P2B", 2, "B")],
)
def test_every_enrolled_player_gets_its_squad_colour(label, squad, slot):
    color, shown = overlay.player_box_style(_player(label, squad, slot))
    assert shown == label
    assert color == overlay.PLAYER_SQUAD_COLORS[(squad, slot)]


def test_squad_colours_are_four_distinct_two_family_shades():
    colors = set(overlay.PLAYER_SQUAD_COLORS.values())
    assert len(colors) == 4
    blues = [overlay.PLAYER_SQUAD_COLORS[k] for k in ((1, "A"), (1, "B"))]
    reds = [overlay.PLAYER_SQUAD_COLORS[k] for k in ((2, "A"), (2, "B"))]
    # BGR: blues keep B the dominant channel, reds keep R dominant, and the
    # clear/dark variants of each family differ substantially in brightness.
    for b, r in zip(blues, reds):
        assert b[0] > b[2]
        assert r[2] > r[0]
    assert abs(blues[0][1] - blues[1][1]) > 100 or abs(blues[0][0] - blues[1][0]) > 50


def test_draw_player_explicit_colour_overrides_action_tint():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    bbox = [50, 50, 150, 200]
    gold = (50, 200, 250)  # BGR, deliberately unlike any ACTION_COLOURS entry

    out = overlay.draw_player(frame, 7, bbox, action="dig", color=gold, label="P1B")
    assert out is None  # draws in place
    hit = int(frame[52, 51, 0])  # just inside the box top-left border
    assert hit == 50 or (frame[52, 51] == np.array(gold)).all()

    # Without an explicit colour the action tint path is unchanged (legacy).
    frame2 = np.zeros((240, 320, 3), dtype=np.uint8)
    overlay.draw_player(frame2, 7, bbox, action="dig")
    assert not (frame2[52, 51] == np.array(gold)).all()
