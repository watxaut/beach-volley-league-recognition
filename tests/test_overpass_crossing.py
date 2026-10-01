"""Tests for the G3 overpass net-crossing probe (diagnose only).

Synthetic inputs only.  The point is to pin the PURE mechanism -- the width
side, the crossing evidence, track coverage, the next-emitted lookup, the
per-action bucket and the K1-K4 arithmetic -- not to reproduce pipeline
behaviour.  The probe itself runs against the committed match GT + diag dump
and writes ``output/g3_overpass/overpass_crossing.json`` +
``docs/g3_overpass_crossing.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from probe_overpass_crossing import (  # noqa: E402
    MIN_TRACK_SIDE,
    ball_width,
    bucket_by_action,
    crossing_evidence,
    is_tracked,
    kill_verdict,
    next_emitted_after,
    side_of_width,
    track_coverage,
)


# ---------------------------------------------------------------- helpers --

def rec(locked=True, center=(100.0, 100.0), dets=None):
    return {
        "ball_track": {"locked": locked, "center": list(center) if center else None},
        "ball_dets": dets or [],
    }


def det(cx, cy, w):
    return {"center": [cx, cy], "bbox": [cx - w / 2, cy - 10, cx + w / 2, cy + 10]}


# ------------------------------------------------------------------ widths --

def test_side_of_width_bands():
    assert side_of_width(40.0) == "A"
    assert side_of_width(20.0) == "B"
    assert side_of_width(30.0) is None      # abstain between 26 and 35
    assert side_of_width(None) is None
    assert side_of_width(35.0) is None      # strict > near
    assert side_of_width(26.0) is None      # strict < far


def test_ball_width_matches_tracked_center():
    r = rec(center=(100.0, 100.0), dets=[det(100.0, 100.0, 30.0), det(50.0, 50.0, 12.0)])
    assert ball_width(r) == 30.0


def test_ball_width_none_when_predicted_center_has_no_det():
    r = rec(center=(100.0, 100.0), dets=[det(10.0, 10.0, 30.0)])
    assert ball_width(r) is None


def test_ball_width_none_when_unlocked():
    assert ball_width(rec(locked=False, dets=[det(100.0, 100.0, 30.0)])) is None


def test_is_tracked():
    assert is_tracked(rec())
    assert not is_tracked(rec(locked=False))
    assert not is_tracked(rec(center=None))


# --------------------------------------------------------- crossing logic --

def widths_of(mapping):
    return dict(mapping)


def test_crossing_evidence_flip():
    # far before the contact, near after -> crossing.
    w = {f: 20.0 for f in range(85, 100)}
    w.update({f: 40.0 for f in range(101, 146)})
    ev = crossing_evidence(w, 100)
    assert ev["crossing"] is True
    assert ev["pre_sides"] == ["B"] and ev["post_sides"] == ["A"]


def test_crossing_evidence_same_side_is_not_a_crossing():
    w = {f: 20.0 for f in range(85, 146)}
    ev = crossing_evidence(w, 100)
    assert ev["crossing"] is False
    assert ev["covered"] is True


def test_crossing_evidence_uncovered_when_one_side_absent():
    w = {f: 20.0 for f in range(85, 100)}  # nothing after
    ev = crossing_evidence(w, 100)
    assert ev["covered"] is False
    assert ev["crossing"] is False


def test_crossing_evidence_abstain_band_does_not_commit():
    w = {f: 30.0 for f in range(85, 146)}  # all in the 26-35 abstain band
    ev = crossing_evidence(w, 100)
    assert ev["covered"] is False


# -------------------------------------------------------------- coverage --

def test_track_coverage_counts_locked_frames():
    recs = {f: rec() for f in range(85, 146)}
    recs[90] = rec(locked=False)  # one gap
    pre, post = track_coverage(recs, 100)
    assert pre == 14  # 85..99 = 15 frames, one unlocked
    assert post == 45


def test_track_coverage_ignores_frames_outside_dump():
    pre, post = track_coverage({}, 100)
    assert (pre, post) == (0, 0)


# ---------------------------------------------------------- next emitted --

def test_next_emitted_after_picks_nearest_later():
    actions = [{"frame_number": 90, "team": "A"},
               {"frame_number": 130, "team": "B"},
               {"frame_number": 110, "team": "A"}]
    assert next_emitted_after(actions, 100)["frame_number"] == 110


def test_next_emitted_after_none_when_nothing_later():
    assert next_emitted_after([{"frame_number": 90}], 100) is None


# ---------------------------------------------------------------- buckets --

def row(gt_action, crossing, tr_pre=10, tr_post=10, gt_team="A", next_team=None):
    return {"gt_action": gt_action, "crossing": crossing,
            "covered": True, "tracked_pre": tr_pre, "tracked_post": tr_post,
            "gt_team": gt_team, "next_team": next_team}


def test_bucket_by_action_rates():
    rows = [row("overpass", True), row("overpass", False),
            row("dig", False), row("dig", False)]
    b = bucket_by_action(rows)
    assert b["overpass"]["n"] == 2 and b["overpass"]["crossing"] == 1
    assert b["overpass"]["crossing_rate"] == 0.5
    assert b["dig"]["crossing_rate"] == 0.0


def test_kill_verdict_refutes_when_signal_absent_and_unseparated():
    # 3/18 overpass crossings, controls similar -> K1 + K2 fire.
    rows = ([row("overpass", i < 3) for i in range(18)]
            + [row("dig", i < 3) for i in range(18)]
            + [row("set", i < 1) for i in range(18)])
    v = kill_verdict(bucket_by_action(rows))
    assert v["K1_signal_present"]["fired"] is True
    assert v["K2_separation"]["fired"] is True
    assert v["K3_detection"]["fired"] is False  # all tracked
    assert v["resolver_lever_dead"] is True
    assert v["verdict"].startswith("REFUTED")


def test_kill_verdict_survives_when_crossing_present_and_separated():
    # 15/18 overpass crossings, controls near zero -> K1/K2 clean.
    rows = ([row("overpass", i < 15) for i in range(18)]
            + [row("dig", False) for i in range(18)]
            + [row("set", False) for i in range(18)])
    v = kill_verdict(bucket_by_action(rows))
    assert v["K1_signal_present"]["fired"] is False
    assert v["K2_separation"]["fired"] is False
    assert v["resolver_lever_dead"] is False
    assert v["verdict"].startswith("SURVIVES")


def test_kill_verdict_detection_fires_when_untracked():
    rows = [row("overpass", False, tr_pre=0, tr_post=0) for _ in range(18)]
    v = kill_verdict(bucket_by_action(rows))
    assert v["K3_detection"]["fired"] is True


def test_kill_verdict_next_team_separation():
    # overpass next-team flips never; dig flips often -> K4 fires (<1.5x).
    rows = ([row("overpass", False, next_team="A") for _ in range(10)]
            + [row("dig", False, next_team="B") for _ in range(10)])
    v = kill_verdict(bucket_by_action(rows))
    assert v["K4_next_team"]["fired"] is True


def test_min_track_side_constant_is_sane():
    assert MIN_TRACK_SIDE == 5
