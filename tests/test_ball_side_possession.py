"""Ball-side possession observer (#77): bands, hysteresis, last-known hold.

Pins the parts that would silently rot:

* the net-plane width formula is the owner's pinhole model (#77 derivation):
  match corners -> d_net ~22.8 px, and the 1.15x/1.55x factors reproduce the
  measured 26/35 px abstain band that the action classifier already uses;
* side commits are WIDTH-only hysteresis: far band, near band, crossing only
  once a committed side is seen inside the net band;
* predicted/lost frames HOLD the last known side (owner instruction) and an
  ESTIMATED (predicted) bbox is never width evidence;
* a crossing only counts when the OPPOSITE side commits (no flap-backs);
* the observer is a pure read (never mutates the tracked-ball dict);
* the diag dump persists the row (schema v2 key) and live debug carries it
  through the overlay cache; the exporter contract (no new
  ``pipeline_output.json`` key) is asserted from the exporter's own source.
"""
from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest

from src.analysis.ball_side_possession import (
    FALLBACK_FAR_PX,
    FALLBACK_NEAR_PX,
    FAR_FACTOR,
    NEAR_FACTOR,
    SIDE_FAR,
    SIDE_NEAR,
    BallSidePossessionObserver,
    net_plane_width_px,
)
from src.output_gen import overlay
from src.utils.diagnostics import SCHEMA_VERSION, DiagRecorder, _new_frame_record

ROOT = Path(__file__).resolve().parents[1]
MATCH_CORNERS = [[714, 597], [1277, 585], [1793, 774], [3, 791]]
# Same geometry shuffled: the near pair must be found by y, not by order.
MATCH_CORNERS_SHUFFLED = [[3, 791], [714, 597], [1793, 774], [1277, 585]]


class _Calib:
    """Smallest court-calibration stand-in the observer reads."""

    def __init__(self, corners):
        self.court_corners = corners


def tb(width, predicted=False):
    """A tracked-ball dict whose bbox spans `width` px."""
    return {
        "bbox": [100.0, 200.0, 100.0 + width, 200.0 + width],
        "center": [100.0 + width / 2, 200.0 + width / 2],
        "is_predicted": predicted,
        "confidence": 0.9,
    }


# --------------------------------------------------------------------- #
# net-plane width formula
# --------------------------------------------------------------------- #

def test_net_plane_width_match_corners():
    d = net_plane_width_px(MATCH_CORNERS)
    assert d is not None
    assert 22.5 < d < 23.2  # 22.84 measured in #77


def test_net_plane_width_corner_order_invariant():
    assert net_plane_width_px(MATCH_CORNERS) == net_plane_width_px(MATCH_CORNERS_SHUFFLED)


def test_net_plane_width_rejects_bad_geometry():
    assert net_plane_width_px(None) is None
    assert net_plane_width_px([[0, 0]]) is None
    # near pair NOT wider than far pair -> calibration is suspect
    assert net_plane_width_px([[0, 0], [10, 0], [10, 5], [0, 5]]) is None


# --------------------------------------------------------------------- #
# bands: calibrated vs fallback
# --------------------------------------------------------------------- #

def test_bands_scale_with_calibration():
    obs = BallSidePossessionObserver()
    obs.set_calibration(_Calib(MATCH_CORNERS))
    d = net_plane_width_px(MATCH_CORNERS)
    assert obs.net_width_px == pytest.approx(d)
    assert obs.far_px == pytest.approx(FAR_FACTOR * d)   # ~26.3
    assert obs.near_px == pytest.approx(NEAR_FACTOR * d)  # ~35.4
    # The 20260920 match factors reproduce the measured 26/35 abstain band.
    assert abs(obs.far_px - 26.0) < 0.6
    assert abs(obs.near_px - 35.0) < 0.6


def test_fallback_bands_uncalibrated():
    obs = BallSidePossessionObserver()
    assert obs.far_px == FALLBACK_FAR_PX == 26.0
    assert obs.near_px == FALLBACK_NEAR_PX == 35.0
    assert obs.net_width_px is None
    # A calibration the formula rejects must leave the fallback in place.
    obs.set_calibration(_Calib(None))
    assert obs.far_px == FALLBACK_FAR_PX


# --------------------------------------------------------------------- #
# side commits + crossing
# --------------------------------------------------------------------- #

def test_far_to_near_crossing_sequence():
    obs = BallSidePossessionObserver()
    r0 = obs.observe(0, tb(20))    # deep far
    assert r0["side"] == SIDE_FAR and not r0["crossing"]
    r1 = obs.observe(1, tb(30))    # inside the net band
    assert r1["side"] == SIDE_FAR and r1["crossing"]
    r2 = obs.observe(2, tb(40))    # commits near
    assert r2["side"] == SIDE_NEAR and not r2["crossing"]
    assert obs.crossings == 1


def test_band_before_any_side_is_not_crossing():
    obs = BallSidePossessionObserver()
    r = obs.observe(0, tb(30))
    assert r["side"] is None and not r["crossing"]


def test_flap_back_does_not_count():
    obs = BallSidePossessionObserver()
    obs.observe(0, tb(20))   # far
    obs.observe(1, tb(30))   # crossing (from far)
    r = obs.observe(2, tb(20))  # back to far: flap-back
    assert r["side"] == SIDE_FAR and not r["crossing"]
    assert obs.crossings == 0


def test_far_to_near_without_band_still_transitions():
    # Detector dropout can hide the band; the sides still flip (no double
    # count), the crossing just was never announced.
    obs = BallSidePossessionObserver()
    obs.observe(0, tb(20))
    r = obs.observe(1, tb(40))
    assert r["side"] == SIDE_NEAR and not r["crossing"]
    assert obs.crossings == 0


# --------------------------------------------------------------------- #
# last-known hold + predicted bboxes
# --------------------------------------------------------------------- #

def test_lost_ball_holds_last_known():
    obs = BallSidePossessionObserver()
    obs.observe(0, tb(20))
    r = obs.observe(1, None)  # ball lost
    assert r["side"] == SIDE_FAR and not r["crossing"]
    assert r["width_px"] == 20.0 and r["width_frame"] == 0


def test_predicted_bbox_is_not_width_evidence():
    obs = BallSidePossessionObserver()
    obs.observe(0, tb(40))  # near committed, width 40
    r = obs.observe(1, tb(10, predicted=True))  # ESTIMATED bbox: must not read
    assert r["side"] == SIDE_NEAR
    assert r["width_px"] == 40.0 and r["width_frame"] == 0


def test_crossing_holds_through_dropout():
    obs = BallSidePossessionObserver()
    obs.observe(0, tb(20))   # far
    obs.observe(1, tb(30))   # crossing
    r = obs.observe(2, None)  # lost mid-crossing: stay crossing
    assert r["crossing"] and r["side"] == SIDE_FAR


def test_observe_never_mutates_tracked_ball():
    obs = BallSidePossessionObserver()
    ball = tb(30)
    snapshot = copy.deepcopy(ball)
    obs.observe(0, ball)
    obs.observe(1, ball)
    assert ball == snapshot


# --------------------------------------------------------------------- #
# diag dump + live-debug cache + exporter contract
# --------------------------------------------------------------------- #

def test_diag_persists_ball_possession(tmp_path):
    assert SCHEMA_VERSION == 2
    rec = _new_frame_record(3)
    assert "ball_possession" in rec and rec["ball_possession"] is None
    d = DiagRecorder(str(tmp_path / "diag.jsonl"))
    row = BallSidePossessionObserver().observe(3, tb(20))
    d.add_frame(3, {"ball_possession": row})
    d.write()
    text = (tmp_path / "diag.jsonl").read_text()
    assert '"ball_possession"' in text
    assert '"side": "far"' in text


def test_overlay_data_carries_possession():
    from src.analysis.live_debug_processor import LiveDebugProcessor
    frame_result = {
        "tracked_ball": {"center": [10, 20], "is_predicted": False, "bbox": [0, 0, 30, 30]},
        "tracked_players": [{"track_id": 1, "bbox": [1, 2, 3, 4]}],
        "game_state": {"current_state": "game_on"},
        "ball_possession": {"side": "far", "crossing": True},
    }
    ball, players, gs, poss = LiveDebugProcessor._overlay_data(frame_result)
    assert poss == {"side": "far", "crossing": True}
    empty = LiveDebugProcessor._overlay_data({})
    assert empty[3] is None


def test_frame_processor_wiring_source():
    # The wiring contract (AGENTS §2 shared path): one observe call in
    # process_frame, calibration + reset hooks, and the diag pass-through.
    src = (ROOT / "src" / "analysis" / "frame_processor.py").read_text()
    assert 'frame_result["ball_possession"] = self.ball_possession.observe(' in src
    assert "self.ball_possession.set_calibration(calibration)" in src
    assert "self.ball_possession.reset()" in src
    assert "ball_possession=frame_result.get(\"ball_possession\")" in src


def test_exporter_never_reads_ball_possession():
    # §6: the per-frame key is display/diag only; the JSON exporter must not
    # pick it up into pipeline_output.json.
    src = (ROOT / "src" / "output_gen" / "json_exporter.py").read_text()
    assert "ball_possession" not in src


# --------------------------------------------------------------------- #
# overlay label
# --------------------------------------------------------------------- #

def _pixels(frame):
    return int(frame.sum())


def test_draw_possession_label_and_crossing():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    overlay.draw_possession(frame, {"side": "near", "crossing": False})
    assert _pixels(frame) > 0
    frame2 = np.zeros((240, 320, 3), dtype=np.uint8)
    overlay.draw_possession(frame2, {"side": "far", "crossing": True})
    # The crossing plate is strictly larger (extra CROSSING segment).
    assert _pixels(frame2) > _pixels(frame)


def test_draw_possession_none_and_unknown_safe():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    overlay.draw_possession(frame, None)          # no crash, no draw
    assert _pixels(frame) == 0
    overlay.draw_possession(frame, {"side": None, "crossing": False})
    assert _pixels(frame) > 0                      # draws the "--" label
