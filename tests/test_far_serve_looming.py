"""Tests for the G3 S1 far-serve looming probe (diagnose only).

Synthetic inputs only.  The point is to pin the PURE mechanism -- segment
formation, the OLS looming slope, the new-rally state, the GT matcher, the
kill arithmetic and the verdict precedence -- not to reproduce pipeline
behaviour.  The probe itself runs against the committed diag dumps and writes
``output/s1/far_serve_looming.json`` + ``docs/g3_far_serve_looming.md``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from probe_far_serve_looming import (  # noqa: E402
    FAR_MAX_WIDTH,
    _verdict,
    build_candidates,
    build_segments,
    contact_frames,
    dump_sightings,
    entreno_fires,
    gt_far_serve_for,
    is_new_rally,
    kill1,
    looming_rate,
    nearest_det_width,
    separation,
)
from src.recognition.action_classifier import ActionClassifier  # noqa: E402


# ---------------------------------------------------------------- helpers --

def tracked(width, state="tracked", center=(100.0, 100.0)):
    return {"state": state, "center": list(center), "width": width,
            "conf": 0.8}


def sighting_map(widths):
    """``{frame: sighting}`` from ``{frame: width}`` (all tracked)."""
    return {f: tracked(w) for f, w in widths.items()}


def seg(onset, L, width=20.0, far=False, behind=None):
    return {"onset": onset, "width_px": width, "L": L,
            "gt_far_serve": onset if far else None, "behind_baseline": behind}


# ---------------------------------------------------------------- width ----

def test_nearest_det_width_matches_admitted_detection():
    rec = {
        "ball_dets": [
            {"center": [10.0, 10.0], "bbox": [0, 0, 30, 30], "removed": False},
            {"center": [100.0, 100.0], "bbox": [90, 90, 110, 110],
             "removed": False},
        ],
    }
    assert nearest_det_width(rec, [100.0, 100.0]) == 20.0


def test_nearest_det_width_ignores_removed_and_nonmatching():
    rec = {"ball_dets": [
        {"center": [100.0, 100.0], "bbox": [90, 90, 110, 110],
         "removed": True}]}
    assert nearest_det_width(rec, [100.0, 100.0]) is None
    assert nearest_det_width({"ball_dets": []}, [1.0, 1.0]) is None


def test_dump_sightings_reads_state_center_width():
    frames = {7: {"ball_track": {"state": "tracked", "center": [5.0, 6.0],
                                 "conf": 0.7},
                  "ball_dets": [{"center": [5.0, 6.0], "bbox": [1, 2, 9, 12],
                                 "removed": False}]}}
    s = dump_sightings(frames)
    assert s[7]["state"] == "tracked"
    assert s[7]["width"] == 8.0
    assert s[7]["center"] == [5.0, 6.0]


def test_dump_sightings_skips_no_center():
    frames = {1: {"ball_track": {"state": "none", "center": None}}}
    assert dump_sightings(frames) == {}


# ------------------------------------------------------------ segments ----

def test_build_segments_merges_within_gap_and_splits_beyond():
    widths = {0: 10.0, 1: 11.0, 4: 12.0, 20: 13.0}
    segs = build_segments(sighting_map(widths), merge_gap=5)
    assert [s["onset"] for s in segs] == [0, 20]
    assert segs[0]["frames"] == [0, 1, 4]


def test_build_segments_ignores_predicted_and_zero_width():
    widths = {0: 10.0, 1: 0.0, 2: None, 3: 12.0}
    m = {f: tracked(w, state=("predicted" if f == 2 else "tracked"))
         for f, w in widths.items()}
    segs = build_segments(m, merge_gap=5)
    assert segs[0]["frames"] == [0, 3]


def test_build_segments_empty():
    assert build_segments({}, merge_gap=5) == []


# ------------------------------------------------------------- looming ----

def test_looming_rate_recovers_log_slope():
    # widths exp(0.2 t) sampled at 1 fps -> slope = 0.2 exactly.
    widths = {f: math.exp(0.2 * f) * 10 for f in range(3)}
    assert looming_rate(sighting_map(widths), onset=0, fps=1.0,
                        span_s=2.0) == pytest.approx(0.2, abs=1e-9)


def test_looming_rate_flat_ball_is_zero():
    widths = {f: 15.0 for f in range(5)}
    assert looming_rate(sighting_map(widths), onset=0, fps=5.0,
                        span_s=0.5) == pytest.approx(0.0)


def test_looming_rate_abstains_below_min_points():
    assert looming_rate(sighting_map({0: 10.0, 1: 11.0}), 0, fps=10.0) is None


def test_looming_rate_ignores_points_outside_window():
    # Only the first two frames are inside a 1-frame window at 1 fps.
    widths = {0: 10.0, 1: 20.0, 100: 1000.0}
    assert looming_rate(sighting_map(widths), onset=0, fps=1.0,
                        span_s=1.0) is None


# ------------------------------------------------------------ new rally ----

def test_is_new_rally_boundary_matches_action_context():
    contacts = [100]
    # gap = 90: contact exactly 90 back is NOT a new rally (gap not > 90).
    assert is_new_rally(190, contacts, 90) is False
    assert is_new_rally(191, contacts, 90) is True
    assert is_new_rally(100, contacts, 90) is False
    assert is_new_rally(1, contacts, 90) is True


def test_contact_frames_reads_actions():
    frames = {1: {"actions": [{"frame_number": 30}, {"frame_number": 10}]},
              2: {"actions": [{"frame_number": 30}]}}
    assert contact_frames(frames) == [10, 30]


# --------------------------------------------------------------- matcher --

def test_gt_far_serve_for_uses_tolerance():
    assert gt_far_serve_for(216, [210], 15) == 210
    assert gt_far_serve_for(225, [210], 15) == 210
    assert gt_far_serve_for(226, [210], 15) is None
    assert gt_far_serve_for(209, [210], 15) is None


# ------------------------------------------------------------ separation --

def test_separation_finds_empty_gap_and_l_star():
    rows = [seg(0, 0.8, far=True), seg(1, 0.6, far=True),
            seg(2, 0.2), seg(3, 0.1)]
    s = separation(rows)
    assert s["lowest_far_L"] == 0.6
    assert s["highest_non_serve_L"] == 0.2
    assert s["gap"] == pytest.approx(0.4)
    assert s["gap_ratio"] == pytest.approx(3.0)
    assert s["L_star"] == pytest.approx(0.4)
    assert s["kill2_fired"] is False


def test_separation_overlap_fires_kill2():
    rows = [seg(0, 0.338, far=True), seg(1, 0.945)]
    s = separation(rows)
    assert s["L_star"] is None
    assert s["kill2_fired"] is True


def test_separation_requires_1_5x_ratio():
    # gap exists but the ratio is only 1.2x -> kill 2 still fires.
    rows = [seg(0, 0.6, far=True), seg(1, 0.5)]
    s = separation(rows)
    assert s["gap"] > 0
    assert s["gap_ratio"] == pytest.approx(1.2)
    assert s["kill2_fired"] is True


def test_separation_missing_class_fires():
    assert separation([seg(0, 0.8, far=True)])["kill2_fired"] is True
    assert separation([seg(0, 0.1)])["kill2_fired"] is True


# ------------------------------------------------------------------ kill1 --

def test_kill1_counts_far_band_sightings_in_window():
    fps = 10.0            # window is 5 frames: [0, 5]
    sightings = {f: tracked(15.0) for f in range(0, 6)}
    sightings[2] = tracked(40.0)        # near-band, not counted
    k = kill1({}, sightings, fps, far_serves=[0])
    assert k["per_serve"]["0"]["far_band"] == 5
    assert k["per_serve"]["0"]["ok"] is True
    assert k["fired"] is True           # 0/1 < 4/5


def test_kill1_not_fired_at_four_of_five():
    fps = 10.0            # window is 5 frames
    sightings = {40: tracked(15.0)}
    # Give only the first four serves the required 5 sightings.
    for c in (0, 10, 20, 30):
        for f in range(c, c + 5):
            sightings[f] = tracked(15.0)
    k = kill1({}, sightings, fps, far_serves=[0, 10, 20, 30, 40])
    assert k["serves_meeting"] == 4
    assert k["fired"] is False


# ------------------------------------------------------------- kill 3/4 ---

def test_entreno_fires_none_when_l_star_undefined():
    k = entreno_fires({"e1": [seg(0, 5.0)]}, None)
    assert k["evaluable"] is False
    assert k["total"] == 0
    assert k["fired"] is False


def test_entreno_fires_counts_at_or_above_threshold():
    k = entreno_fires({"e1": [seg(0, 0.6), seg(1, 0.4)]}, 0.5)
    assert k["fires"]["e1"] == [0]
    assert k["fired"] is True


# -------------------------------------------------------------- verdict ---

def test_verdict_prefers_kill1():
    v = _verdict({"fired": True}, {"kill2_fired": True}, {"fired": True})
    assert v["reason"].startswith("kill 1")


def test_verdict_kill2_when_kill1_passes():
    v = _verdict({"fired": False}, {"kill2_fired": True}, {"fired": False})
    assert v["reason"].startswith("kill 2")


def test_verdict_kill3_when_1_and_2_pass():
    v = _verdict({"fired": False}, {"kill2_fired": False}, {"fired": True})
    assert v["reason"].startswith("kill 3")


def test_verdict_survives_when_all_pass():
    v = _verdict({"fired": False}, {"kill2_fired": False}, {"fired": False})
    assert v["status"].startswith("SURVIVES")


# ------------------------------------------------------------ candidates --

def test_build_candidates_applies_new_rally_and_width_gate():
    # A far serve at f100, a looming post-contact segment at f104, a near-band
    # segment at f110 (excluded), and a mid-rally far segment at f120.
    frames = {104: {"actions": []}}
    sightings = sighting_map({104: 16.0, 105: 17.0, 106: 18.0})
    rows = build_candidates(frames, sightings, fps=10.0, merge_gap=10,
                            far_serves=[100], tol=15)
    assert len(rows) == 1
    assert rows[0]["onset"] == 104
    assert rows[0]["gt_far_serve"] == 100

    wide = sighting_map({104: 40.0, 105: 41.0, 106: 42.0})
    assert build_candidates(frames, wide, fps=10.0, merge_gap=10,
                            far_serves=[100], tol=15) == []


def test_build_candidates_excludes_mid_rally_segment():
    # The last emitted contact is 50 f before the onset; RALLY_RESET_GAP=90.
    frames = {154: {"actions": [{"frame_number": 150}]}}
    sightings = sighting_map({154: 16.0, 155: 17.0, 156: 18.0})
    assert build_candidates(frames, sightings, fps=10.0, merge_gap=10,
                            far_serves=[], tol=0) == []


def test_far_max_width_is_below_abstain_band():
    assert FAR_MAX_WIDTH < 26.0 + 1e-9
