"""Tests for the ball ground-contact observer (#80).

Geometry tests run on a synthetic pinhole camera (owner's derivation,
2026-10-05): world X right / Y depth away / Z up, court 16 m x 8 m,
camera pitched down. Ball boxes are built by SAMPLING the sphere
silhouette and projecting it, so ratios, in/out verdicts and mapped world
points go through the real homography path
(``CourtCalibration.compute_ground_homography`` on the projected corners)
-- no mocked calibration.

Physics being pinned: a resting ball's bbox bottom-center lands on its
ground contact point (silhouette bottom == contact point, ~0.2 px), so
mapping it through the ground homography recovers the true court point
and the bbox width matches the projected ground diameter (ratio ~1). An
airborne ball's bottom maps BEYOND its true ground position (toward the
horizon), so its width compares against a nearer-ground scale -> ratio
grows with height. Mapping-outside-court alone therefore never means
OUT; only grounded + outside does.
"""

import math
from pathlib import Path

import numpy as np
import pytest

from src.analysis.ball_ground_contact import (
    AIR_EXIT_RATIO,
    BALL_DIAMETER_M,
    BOUNCE_RATIO_MAX,
    GROUND_ENTER_RATIO,
    MIN_BOUNCE_VY_PXF,
    OUT_MARGIN_M,
    STATE_AIR,
    STATE_GROUND,
    STATE_OUT,
    BallGroundContactObserver,
    measure_box,
)
from src.detection.court_calibration import CourtCalibration
from src.output_gen import overlay
from src.utils.diagnostics import DiagRecorder, SCHEMA_VERSION, _new_frame_record

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------- #
# constants
# --------------------------------------------------------------------- #

def test_threshold_pins():
    assert GROUND_ENTER_RATIO == 1.25
    assert AIR_EXIT_RATIO == 1.45
    assert AIR_EXIT_RATIO > GROUND_ENTER_RATIO   # hysteresis band: no flicker
    assert BOUNCE_RATIO_MAX < AIR_EXIT_RATIO     # a bounce cannot fire airborne
    assert MIN_BOUNCE_VY_PXF == 2.0
    assert OUT_MARGIN_M == 0.25
    assert abs(BALL_DIAMETER_M - 0.67 / math.pi) < 1e-9


# --------------------------------------------------------------------- #
# synthetic long-axis camera
# --------------------------------------------------------------------- #

F_PX = 1100.0
CX, CY = 960.0, 540.0
CAM_POS = (4.0, -5.0, 2.4)   # mid-width, 5 m behind the near baseline, 2.4 m up
PITCH_DEG = 18.0
HORIZON_V = CY - F_PX * math.tan(math.radians(PITCH_DEG))  # ~183 px


def _w2c():
    p = math.radians(PITCH_DEG)
    R = np.array([
        [1.0, 0.0, 0.0],
        [0.0, math.sin(p), math.cos(p)],
        [0.0, -math.cos(p), math.sin(p)],
    ])
    return R, -R @ np.array(CAM_POS)


def _project(pt3):
    R, t = _w2c()
    pc = R @ np.asarray(pt3, dtype=float) + t
    return (F_PX * pc[0] / pc[2] + CX, F_PX * pc[1] / pc[2] + CY)


def _calibration():
    cal = CourtCalibration()
    cal.court_corners = np.array(
        [_project([x, y, 0.0]) for x, y in ((0, 0), (8, 0), (8, 16), (0, 16))],
        dtype=np.float32,
    )
    return cal


def _observer():
    obs = BallGroundContactObserver()
    obs.set_calibration(_calibration())
    return obs


def _sphere_bbox(center3, radius=BALL_DIAMETER_M / 2.0, n=28):
    pts = []
    for phi in np.linspace(-math.pi / 2, math.pi / 2, n):
        for th in np.linspace(0, 2 * math.pi, 2 * n):
            pts.append([
                center3[0] + radius * math.cos(phi) * math.cos(th),
                center3[1] + radius * math.cos(phi) * math.sin(th),
                center3[2] + radius * math.sin(phi),
            ])
    img = np.array([_project(p) for p in pts])
    (x1, y1), (x2, y2) = img.min(axis=0), img.max(axis=0)
    return (float(x1), float(y1), float(x2), float(y2))


def _tb(wx, wy, h=0.0, velocity=(0.0, 0.0), predicted=False):
    """A tracked-ball dict for a sphere whose BOTTOM rests h metres up."""
    center3 = (wx, wy, h + BALL_DIAMETER_M / 2.0)
    bbox = _sphere_bbox(center3)
    return {
        "center": list(_project(center3)),
        "bbox": bbox,
        "confidence": 0.9,
        "velocity": [float(velocity[0]), float(velocity[1])],
        "is_predicted": predicted,
    }


def _widened_tb(k, wx=4.0, wy=8.0):
    """Same grounded box with the width scaled by k (ratio scales with it)."""
    tb = _tb(wx, wy)
    x1, y1, x2, y2 = tb["bbox"]
    cx = (x1 + x2) / 2.0
    w = (x2 - x1) * k
    tb["bbox"] = (cx - w / 2.0, y1, cx + w / 2.0, y2)
    return tb


# --------------------------------------------------------------------- #
# geometry on the synthetic camera
# --------------------------------------------------------------------- #

class TestGeometryOnSyntheticCamera:

    def test_grounded_ball_reads_ground_with_unit_ratio_and_accurate_world(self):
        obs = _observer()
        row = obs.observe(5, _tb(4.0, 8.0))
        assert row["state"] == STATE_GROUND
        assert row["held"] is False
        assert 0.9 <= row["ratio"] <= GROUND_ENTER_RATIO
        assert abs(row["width_px"] - row["w_pred_px"]) / row["w_pred_px"] < 0.1
        wx, wy = row["world"]
        assert abs(wx - 4.0) < 0.15 and abs(wy - 8.0) < 0.15
        assert row["in_court"] is True

    def test_grounded_ball_reads_ground_deep_in_the_far_half(self):
        obs = _observer()
        row = obs.observe(5, _tb(4.0, 15.5))
        assert row["state"] == STATE_GROUND
        assert row["in_court"] is True

    def test_airborne_ball_stays_air_even_when_its_map_leaves_the_court(self):
        # 1 m up at mid-court: the bottom maps ~9 m beyond the true point,
        # OUTSIDE the far baseline -- but the state must be AIR, not OUT
        # (mapped-outside alone cannot mean OUT; the owner's derivation).
        obs = _observer()
        row = obs.observe(5, _tb(4.0, 8.0, h=1.0))
        assert row["state"] == STATE_AIR
        assert row["ratio"] > AIR_EXIT_RATIO
        assert row["in_court"] is False
        assert 16.5 < row["world"][1] < 60.0   # beyond the far baseline, sane

    def test_grounded_outside_court_reads_out(self):
        obs = _observer()
        assert obs.observe(5, _tb(4.0, 17.5))["state"] == STATE_OUT
        assert obs.observe(6, _tb(-0.6, 8.0))["state"] == STATE_OUT

    def test_out_margin_tolerance_at_the_lines(self):
        obs = _observer()
        assert obs.observe(5, _tb(4.0, 16.0 + OUT_MARGIN_M - 0.05))["state"] == STATE_GROUND
        assert obs.observe(6, _tb(4.0, 16.0 + OUT_MARGIN_M + 0.15))["state"] == STATE_OUT

    def test_uncalibrated_observer_is_safe(self):
        obs = BallGroundContactObserver()
        row = obs.observe(5, _tb(4.0, 8.0))
        assert row["held"] is True
        assert row["state"] is None
        assert row["ratio"] is None
        assert row["bounce"] is False

    def test_measure_box_pure_helper_matches_observer(self):
        cal = _calibration()
        h_i2w, h_w2i = BallGroundContactObserver.calibration_homographies(cal)
        m = measure_box(h_i2w, h_w2i, _tb(4.0, 8.0)["bbox"])
        assert m["degenerate"] is False
        assert 0.9 <= m["ratio"] <= GROUND_ENTER_RATIO
        assert m["in_court"] is True
        assert BallGroundContactObserver.box_verdict(h_i2w, h_w2i, _tb(4.0, 8.0, h=1.0)["bbox"]) == "air"
        assert BallGroundContactObserver.box_verdict(h_i2w, h_w2i, _tb(4.0, 8.0)["bbox"]) == "ground"
        assert BallGroundContactObserver.box_verdict(None, None, _tb(4.0, 8.0)["bbox"]) is None


# --------------------------------------------------------------------- #
# hysteresis + hold
# --------------------------------------------------------------------- #

class TestHysteresisAndHold:

    def test_band_keeps_ground_and_exit_commits_air(self):
        obs = _observer()
        assert obs.observe(0, _tb(4.0, 8.0))["state"] == STATE_GROUND
        # Band (ratio ~1.35, between 1.25 and 1.45): ground holds.
        assert obs.observe(1, _widened_tb(1.32))["state"] == STATE_GROUND
        # Above AIR_EXIT: commit AIR.
        assert obs.observe(2, _widened_tb(1.50))["state"] == STATE_AIR
        # Band with prior AIR: stays AIR.
        assert obs.observe(3, _widened_tb(1.32))["state"] == STATE_AIR
        # Back under GROUND_ENTER: ground again.
        assert obs.observe(4, _tb(4.0, 8.0))["state"] == STATE_GROUND

    def test_predicted_frame_holds_and_flags_held(self):
        obs = _observer()
        obs.observe(0, _tb(4.0, 8.0))
        row = obs.observe(1, _tb(4.0, 8.0, velocity=(0.0, -4.0), predicted=True))
        assert row["held"] is True
        assert row["state"] == STATE_GROUND
        assert row["ratio"] is None and row["world"] is None

    def test_missing_ball_holds_state(self):
        obs = _observer()
        obs.observe(0, _tb(4.0, 8.0))
        row = obs.observe(1, None)
        assert row["held"] is True and row["state"] == STATE_GROUND

    def test_first_frame_without_a_committed_state_is_none(self):
        obs = _observer()
        assert obs.observe(0, _widened_tb(1.32))["state"] is None  # band, no prior

    def test_degenerate_mapping_forces_air(self):
        # Box bottom-center above the horizon (v < ~183): the homography
        # inverts through the vanishing line -> unusable -> AIR, never OUT.
        assert HORIZON_V < 200
        obs = _observer()
        tb = _tb(4.0, 8.0)
        tb["bbox"] = (940.0, 60.0, 980.0, HORIZON_V - 80)
        row = obs.observe(0, tb)
        assert row["degenerate"] is True
        assert row["state"] == STATE_AIR


# --------------------------------------------------------------------- #
# bounce
# --------------------------------------------------------------------- #

class TestBounce:

    def test_fall_then_rise_fires_once_and_counts(self):
        obs = _observer()
        assert obs.observe(10, _tb(4.0, 8.0, velocity=(0.0, 3.0)))["bounce"] is False
        r = obs.observe(11, _tb(4.0, 8.0, velocity=(0.0, -3.0)))
        assert r["bounce"] is True and r["bounces"] == 1
        assert obs.observe(12, _tb(4.0, 8.0, velocity=(0.0, 0.0)))["bounce"] is False
        assert obs.observe(13, _tb(4.0, 8.0))["bounces"] == 1

    def test_apex_flip_does_not_fire(self):
        obs = _observer()
        obs.observe(10, _tb(4.0, 8.0, velocity=(0.0, -3.0)))   # rising
        r = obs.observe(11, _tb(4.0, 8.0, velocity=(0.0, 3.0)))  # apex -> fall
        assert r["bounce"] is False and r["bounces"] == 0

    def test_disarm_requires_a_new_fast_fall(self):
        obs = _observer()
        obs.observe(10, _tb(4.0, 8.0, velocity=(0.0, 3.0)))    # arm
        assert obs.observe(11, _tb(4.0, 8.0, velocity=(0.0, -3.0)))["bounce"] is True
        assert obs.observe(12, _tb(4.0, 8.0, velocity=(0.0, -3.0)))["bounce"] is False
        assert obs.observe(13, _tb(4.0, 8.0, velocity=(0.0, 3.0)))["bounce"] is False  # re-arm
        assert obs.observe(14, _tb(4.0, 8.0, velocity=(0.0, -3.0)))["bounce"] is True
        assert obs.observe(15, _tb(4.0, 8.0))["bounces"] == 2

    def test_bounce_blocked_when_ratio_too_high(self):
        obs = _observer()
        tb_fall = _widened_tb(1.50)
        tb_fall["velocity"] = [0.0, 3.0]
        tb_rise = _widened_tb(1.50)
        tb_rise["velocity"] = [0.0, -3.0]
        obs.observe(10, tb_fall)
        r = obs.observe(11, tb_rise)
        assert r["bounce"] is False and r["bounces"] == 0
        assert r["state"] == STATE_AIR   # ratio above cap reads AIR anyway

    def test_predicted_frame_breaks_consecutiveness(self):
        obs = _observer()
        obs.observe(10, _tb(4.0, 8.0, velocity=(0.0, 3.0)))
        obs.observe(11, _tb(4.0, 8.0, velocity=(0.0, 3.0), predicted=True))  # held
        r = obs.observe(12, _tb(4.0, 8.0, velocity=(0.0, -3.0)))
        assert r["bounce"] is False   # gap 2 in REAL frames: not consecutive

    def test_small_flips_do_not_fire(self):
        obs = _observer()
        obs.observe(10, _tb(4.0, 8.0, velocity=(0.0, 1.0)))
        r = obs.observe(11, _tb(4.0, 8.0, velocity=(0.0, -1.0)))
        assert r["bounce"] is False


# --------------------------------------------------------------------- #
# reset + purity
# --------------------------------------------------------------------- #

def test_reset_clears_state_and_bounces_keeps_calibration():
    obs = _observer()
    obs.observe(10, _tb(4.0, 8.0, velocity=(0.0, 3.0)))
    obs.observe(11, _tb(4.0, 8.0, velocity=(0.0, -3.0)))
    obs.reset()
    row = obs.observe(12, _tb(4.0, 8.0))
    assert row["bounces"] == 0 and row["bounce"] is False
    # Calibration survives reset (set once per video).
    row2 = obs.observe(13, _tb(4.0, 8.0, h=1.0))
    assert row2["state"] == STATE_AIR and row2["ratio"] > AIR_EXIT_RATIO


def test_observe_is_pure():
    corners = _calibration().court_corners.copy()

    def run():
        obs = _observer()
        return [
            obs.observe(0, _tb(4.0, 8.0)),
            obs.observe(1, _tb(4.0, 8.0, h=1.0)),
            obs.observe(2, _tb(4.0, 17.5)),
            obs.observe(3, None),
            obs.observe(4, _tb(4.0, 8.0, velocity=(0.0, 3.0))),
            obs.observe(5, _tb(4.0, 8.0, velocity=(0.0, -3.0))),
        ]

    rows_a, rows_b = run(), run()
    assert rows_a == rows_b
    assert np.array_equal(_calibration().court_corners, corners)
    # And the input dicts are not mutated.
    tb = _tb(4.0, 8.0)
    tb_snapshot = dict(tb)
    _observer().observe(0, tb)
    assert tb == tb_snapshot


# --------------------------------------------------------------------- #
# diag dump + exporter contract
# --------------------------------------------------------------------- #

def test_schema_bumped_and_ground_persisted(tmp_path):
    assert SCHEMA_VERSION == 5  # 3 = #80 ball_ground row; 4 = post-run ball bbox/velocity + player labels; 5 = id_sims
    rec = _new_frame_record(7)
    assert "ball_ground" in rec and rec["ball_ground"] is None
    d = DiagRecorder(str(tmp_path / "diag.jsonl"))
    row = _observer().observe(7, _tb(4.0, 8.0))
    d.add_frame(7, {"ball_ground": row})
    d.write()
    text = (tmp_path / "diag.jsonl").read_text()
    assert '"ball_ground"' in text
    assert '"state": "ground"' in text


def test_ground_row_never_enters_pipeline_output():
    # Same contract as ball_possession: display/diag only, the JSON exporter
    # must not pick it up into pipeline_output.json.
    src = (ROOT / "src" / "output_gen" / "json_exporter.py").read_text()
    assert "ball_ground" not in src


# --------------------------------------------------------------------- #
# wiring sources (AGENTS §2: one shared path)
# --------------------------------------------------------------------- #

def test_frame_processor_wiring_source():
    src = (ROOT / "src" / "analysis" / "frame_processor.py").read_text()
    assert 'frame_result["ball_ground"] = self.ball_ground.observe(' in src
    assert "self.ball_ground.set_calibration(calibration)" in src
    assert "self.ball_ground.reset()" in src
    assert 'ball_ground=frame_result.get("ball_ground")' in src
    # Ground observation is wired AFTER possession, reading the same
    # tracked_ball (one shared path, one read per frame).
    poss_at = src.find('frame_result["ball_possession"] = self.ball_possession.observe(')
    ground_at = src.find('frame_result["ball_ground"] = self.ball_ground.observe(')
    assert 0 < poss_at < ground_at
    # The INIT-TIME calibration must reach both observers: the batch path
    # never calls set_court_calibration (probe regression, 2026-10-04).
    assert "self.ball_ground.set_calibration(self.court_calibration)" in src
    assert "self.ball_possession.set_calibration(self.court_calibration)" in src


def test_live_debug_and_panel_sources():
    ld = (ROOT / "src" / "analysis" / "live_debug_processor.py").read_text()
    assert "overlay.draw_ball_ground(out" in ld          # tracked-ball label
    assert "box_verdict" in ld                           # per-candidate tag
    dp = (ROOT / "src" / "analysis" / "debug_panel.py").read_text()
    assert 'f"ground: {g_txt}"' in dp                    # panel line
    ov = (ROOT / "src" / "output_gen" / "overlay.py").read_text()
    assert "def draw_ball_ground" in ov


# --------------------------------------------------------------------- #
# live-debug overlay plumbing
# --------------------------------------------------------------------- #

def test_overlay_data_carries_ground():
    from src.analysis.live_debug_processor import LiveDebugProcessor
    frame_result = {
        "tracked_ball": {"center": [10, 20], "is_predicted": False, "bbox": [0, 0, 30, 30]},
        "tracked_players": [{"track_id": 1, "bbox": [1, 2, 3, 4]}],
        "game_state": {"current_state": "game_on"},
        "ball_possession": {"side": "far", "crossing": True},
        "ball_ground": {"state": "ground", "held": False, "ratio": 1.02},
    }
    ball, players, gs, poss, ground = LiveDebugProcessor._overlay_data(frame_result)
    assert ground == {"state": "ground", "held": False, "ratio": 1.02}
    empty = LiveDebugProcessor._overlay_data({})
    assert empty[3] is None and empty[4] is None


# --------------------------------------------------------------------- #
# overlay labels
# --------------------------------------------------------------------- #

def _pixels(frame):
    return int(frame.sum())


def test_draw_ball_ground_states():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    overlay.draw_ball_ground(frame, 100, 100, {"state": "ground", "held": False, "ratio": 1.02})
    assert _pixels(frame) > 0
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    overlay.draw_ball_ground(frame, 100, 100, {"state": "out", "held": False, "ratio": 1.01})
    assert _pixels(frame) > 0
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    overlay.draw_ball_ground(frame, 100, 100, {"state": "air", "held": False, "ratio": 1.7})
    assert _pixels(frame) > 0
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    overlay.draw_ball_ground(frame, 100, 100, {"state": "air", "held": False, "ratio": None})
    assert _pixels(frame) > 0


def test_draw_ball_ground_none_unknown_and_held():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    overlay.draw_ball_ground(frame, 100, 100, None)
    assert _pixels(frame) == 0            # nothing to say -> no draw
    overlay.draw_ball_ground(frame, 100, 100, {"state": "weird"})
    assert _pixels(frame) == 0
    overlay.draw_ball_ground(frame, 100, 100, {"state": "ground", "held": True, "ratio": None})
    assert _pixels(frame) > 0             # held row still shows the short state


def test_draw_ball_candidate_ground_tag():
    frame1 = np.zeros((240, 320, 3), dtype=np.uint8)
    overlay.draw_ball_candidate(frame1, (10, 10, 50, 50), None, 0.8, "")
    frame2 = np.zeros((240, 320, 3), dtype=np.uint8)
    overlay.draw_ball_candidate(frame2, (10, 10, 50, 50), None, 0.8, "", ground="ground")
    assert _pixels(frame2) > _pixels(frame1)   # GND suffix is extra text
