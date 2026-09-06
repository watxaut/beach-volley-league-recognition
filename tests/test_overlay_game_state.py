"""Tests for the game-state badge rendering (overlay.draw_game_state).

Owner report (2026-09-05): the badge overprinted the court overlay's
"Court: CALIBRATED" text (both live at the top-left corner) and had no
background, making it unreadable over bright sand. Locked here: the badge
sits on a solid black plate on its own line BELOW the CALIBRATED baseline.
"""

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.output_gen import overlay

# The court overlay draws "Court: CALIBRATED" at baseline y=30 (font 0.6,
# thickness 2) -- its ink reaches down to about y=34.
CALIBRATED_BOTTOM_Y = 34


def make_frame():
    return np.full((120, 360, 3), (40, 90, 160), np.uint8)  # sand-ish bg


def plate_rect(label):
    """The black plate the badge draws, derived the same way as the code."""
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    x, y = 12, 62
    return (x - 8, y - th - 8, x + tw + 8, y + 8)


def test_badge_has_solid_black_plate():
    frame = make_frame()
    overlay.draw_game_state(frame, "game_on", points=3)
    x0, y0, x1, y1 = plate_rect("GAME ON  P3")
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    # some plate pixel away from the glyph strokes is pure black
    assert frame[cy, x0 + 3].tolist() == [0, 0, 0]
    assert frame[y1 - 2, cx].tolist() == [0, 0, 0]
    # and the frame outside the plate keeps the background colour
    assert frame[cy, x1 + 20].tolist() == [40, 90, 160]


def test_badge_clears_the_calibrated_line():
    for state in ("game_on", "game_off"):
        frame = make_frame()
        overlay.draw_game_state(frame, state)
        x0, y0, _, _ = plate_rect("GAME OFF")
        assert y0 > CALIBRATED_BOTTOM_Y, "badge plate must sit below CALIBRATED"
        # no badge ink in the CALIBRATED text band (x<=260, y<=CALIBRATED_BOTTOM_Y)
        band = frame[: CALIBRATED_BOTTOM_Y + 1, :260]
        assert band.sum() > 0 and not (band == 0).all()


def test_badge_states_and_provisional_tint():
    frame = make_frame()
    overlay.draw_game_state(frame, "game_on", provisional=True)
    x0, y0, x1, y1 = plate_rect("GAME ON ~")
    crop = frame[y0 : y1 + 1, x0 : x1 + 1]
    # provisional green tint (120, 200, 120) BGR present on the plate
    assert (crop == np.array([120, 200, 120], np.uint8)).any(axis=2).any()

    frame = make_frame()
    overlay.draw_game_state(frame, "game_off")
    x0, y0, x1, y1 = plate_rect("GAME OFF")
    crop = frame[y0 : y1 + 1, x0 : x1 + 1]
    assert (crop == np.array([160, 160, 160], np.uint8)).any(axis=2).any()
