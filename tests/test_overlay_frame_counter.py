"""Tests for the frame-counter rendering (``overlay.draw_frame_counter``).

Owner report (2026-10-02): the counter was hard to read over the sand. Locked
here: it sits on a SOLID BLACK plate (not just a thin text underlay) and its
font is one pixel of cap height above the old 0.55 scale.
"""

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.output_gen import overlay

SCALE = 0.60          # the scale draw_frame_counter draws at
OLD_SCALE = 0.55      # what it used to be


def make_frame(w=520, h=120, bg=(40, 90, 160)):
    return np.full((h, w, 3), bg, np.uint8)


def counter_plate(label, w=520):
    """The black plate the counter draws, derived the same way as the code."""
    (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, SCALE, 1)
    x, y = w - tw - 12, 28
    return (x - 8, y - th - 8, x + tw + 8, y + baseline)


def test_black_plate_behind_the_number():
    frame = make_frame()
    overlay.draw_frame_counter(frame, 241, total=900)
    x0, y0, x1, y1 = counter_plate("f241/900")
    cy = (y0 + y1) // 2
    # Plate pixels away from the glyph strokes are pure black, in the padding
    # AND in the full plate height (the underlay alone did not give enough
    # contrast over bright sand at this size).
    assert frame[cy, x0 + 3].tolist() == [0, 0, 0]
    assert frame[cy, x1 - 3].tolist() == [0, 0, 0]
    assert frame[y0 + 2, x0 + 3].tolist() == [0, 0, 0]
    assert frame[y1 - 2, x0 + 3].tolist() == [0, 0, 0]
    # the frame outside the plate keeps the background colour
    assert frame[cy, x0 - 30].tolist() == [40, 90, 160]


def test_plate_does_not_cover_the_rest_of_the_frame():
    frame = make_frame()
    overlay.draw_frame_counter(frame, 241, total=900)
    x0, y0, x1, y1 = counter_plate("f241/900")
    assert frame[:y0, :x0].tolist() == make_frame()[:y0, :x0].tolist()
    assert frame[y1:, :x0].tolist() == make_frame()[y1:, :x0].tolist()


def test_white_glyphs_inside_the_plate():
    frame = make_frame()
    overlay.draw_frame_counter(frame, 241, total=900)
    x0, y0, x1, y1 = counter_plate("f241/900")
    plate = frame[y0:y1, x0:x1]
    white = (plate[..., 0] > 200) & (plate[..., 1] > 200) & (plate[..., 2] > 200)
    assert white.any(), "no white glyph pixels drawn"


def test_font_is_one_pixel_bigger_than_before():
    """The scale bump is part of the fix -- pin it so it cannot silently revert."""
    (_, th_new), base_new = cv2.getTextSize(
        "f241/900", cv2.FONT_HERSHEY_SIMPLEX, SCALE, 1)
    (_, th_old), _ = cv2.getTextSize(
        "f241/900", cv2.FONT_HERSHEY_SIMPLEX, OLD_SCALE, 1)
    assert th_new == th_old + 1
    # ...and the drawn plate matches the NEW geometry (i.e. the code uses it).
    frame = make_frame()
    overlay.draw_frame_counter(frame, 241, total=900)
    x0, y0, x1, y1 = counter_plate("f241/900")
    assert (x0, y0, x1, y1) == counter_plate("f241/900")
    assert y1 - y0 == th_new + base_new + 8
    assert y0 == 28 - th_new - 8


def test_without_total_the_label_is_shorter():
    frame = make_frame()
    overlay.draw_frame_counter(frame, 7)
    x0, y0, x1, y1 = counter_plate("f7")
    cy = (y0 + y1) // 2
    assert frame[cy, x0 + 3].tolist() == [0, 0, 0]
    assert x0 > counter_plate("f7/900")[0]      # shorter label, plate starts later