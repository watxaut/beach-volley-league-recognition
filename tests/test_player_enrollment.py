"""Tests for the player-enrollment pre-pass (E1) + tracker label stamping.

Two surfaces:
  * PlayerEnrollment.chaining/merge/squad-slot logic on SYNTHETIC videos
    (tiny mp4s written on the fly; a scripted detector keyed by call order
    -- deterministic because the pre-pass detects every stride-th frame in
    increasing order). Distinct torso colours give the histograms something
    to discriminate; the fake court splits near/far at a fixed y.
  * PlayerTracker.set_enrollment / _maybe_assign_label / _stamp_identities:
    labels attach by signature, are STICKY (never reassigned while a track
    lives), survive retire-to-gallery + restore (same tid -> same label),
    are cleared by set_enrollment/hard-removal/reset, and -- the parity
    promise -- tracking outputs are BYTE-IDENTICAL with enrollment off vs
    on once the three display keys are dropped (labels never touch a
    tracking decision; the entreno F1 gate covers the same claim end-to-end).
"""
from __future__ import annotations

import os

import cv2
import numpy as np
import pytest

from src.tracking.player_enrollment import PlayerEnrollment
from src.tracking.player_tracker import PlayerTracker

W, H = 320, 240
MID_Y = 120          # fake midcourt: foot y >= MID_Y -> near side "A"
BOX_W, BOX_H = 40, 80


class _FakeCourt:
    """Minimal court stand-in: everything is 'in court'; near/far split at
    MID_Y by the foot point (long-axis camera: near half = team A)."""

    is_calibrated = True

    def foot_point(self, bbox):
        return (int((bbox[0] + bbox[2]) / 2), int(bbox[3]))

    def is_point_in_court(self, point):
        return True

    def get_team_for_bbox(self, bbox):
        return "A" if (bbox[0] + bbox[2]) / 2 >= 0 and bbox[3] >= MID_Y else "B"

    def get_team(self, point):
        return "A" if point[1] >= MID_Y else "B"

    def world_body_size(self, bbox):
        # No ground plane -> height/proportions channels are dropped;
        # tests exercise position + colour.
        return None

    def filter_detections_by_court(self, detections):
        return [d for d in detections if self.is_point_in_court(self.foot_point(d["bbox"]))]


class _ScriptedDetector:
    """Returns scripted detections per SAMPLED frame (call order = sample
    order; the pre-pass detects every stride-th frame in increasing order)."""

    def __init__(self, samples, stride):
        self._samples = samples   # list per sampled frame of [(cx, cy, color)]
        self._stride = stride
        self.calls = 0

    def detect(self, frame):
        idx = self.calls
        self.calls += 1
        if idx >= len(self._samples):
            return []
        dets = []
        for p in self._samples[idx]:
            if p is None:
                continue
            cx, cy, _color = p
            dets.append({
                "bbox": [float(cx - BOX_W / 2), float(cy - BOX_H / 2),
                          float(cx + BOX_W / 2), float(cy + BOX_H / 2)],
                "center": [float(cx), float(cy)],
                "confidence": 0.9,
            })
        return dets


def _draw_sample(players):
    """Frame + detection list for one sampled position set.

    players: list of (cx, cy, (b, g, r)) or None for an absent (occluded)
    player. Each present player is a solid coloured box -- the torso
    histogram therefore identifies the colour.
    """
    frame = np.zeros((H, W, 3), np.uint8)
    dets = []
    for p in players:
        if p is None:
            continue
        cx, cy, color = p
        x1, y1 = int(cx - BOX_W / 2), int(cy - BOX_H / 2)
        x2, y2 = x1 + BOX_W, y1 + BOX_H
        frame[y1:y2, x1:x2] = color
        dets.append({
            "bbox": [float(x1), float(y1), float(x2), float(y2)],
            "center": [float(cx), float(cy)],
            "confidence": 0.9,
        })
    return frame, dets


def _write_video(path, samples):
    """Write one tiny mp4: sampled frames in order, stride-1 filler frames
    between them (the pre-pass only detects on stride multiples)."""
    stride = 5
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 30, (W, H))
    assert writer.isOpened()
    for players in samples:
        frame, _ = _draw_sample(players)
        for _ in range(stride):
            writer.write(frame)
    writer.release()


BLUE, TEAL, RED, YELLOW = (255, 0, 0), (255, 255, 0), (0, 0, 255), (0, 255, 255)

# The standard 4-player cast: near pair (foot below MID_Y), far pair above.
# Static positions + distinct hues: chains form on position, histograms
# discriminate, left/right within a squad is the x order.
CAST = [
    (80, 170, BLUE),    # near left
    (240, 170, TEAL),   # near right
    (100, 40, RED),     # far left
    (260, 40, YELLOW),  # far right
]
N_SAMPLES = 30


def _standard_samples():
    return [[(cx, cy, color) for cx, cy, color in CAST] for _ in range(N_SAMPLES)]


def _make_enroller(tmp_path, samples, **overrides):
    video = os.path.join(str(tmp_path), "synth.mp4")
    _write_video(video, samples)
    court = _FakeCourt()
    tracker = PlayerTracker(court_calibration=court, max_players=4)
    params = dict(
        court_calibration=court,
        player_detector=_ScriptedDetector(samples, stride=5),
        tracker=tracker,
        max_frames=len(samples) * 5,
        stride=5,
        min_observations=8,
        chain_gate_px=120.0,
        chain_gap_samples=6,
        merge_gap_frames=60,
    )
    params.update(overrides)
    return PlayerEnrollment(**params)


# --------------------------------------------------------------------------- #
# Enrollment pre-pass on synthetic videos
# --------------------------------------------------------------------------- #

def test_enroll_builds_four_references_with_labels_and_squads(tmp_path):
    enroller = _make_enroller(tmp_path, _standard_samples())
    refs = enroller.enroll(os.path.join(str(tmp_path), "synth.mp4"))

    assert refs is not None
    assert sorted(r["label"] for r in refs) == ["P1A", "P1B", "P2A", "P2B"]
    squads = {r["label"]: r["squad"] for r in refs}
    assert squads["P1A"] == 1 and squads["P1B"] == 1
    assert squads["P2A"] == 2 and squads["P2B"] == 2
    # Near pair = squad 1; far pair = squad 2 (fake court: foot y vs MID_Y).
    by_label = {r["label"]: r for r in refs}
    assert by_label["P1A"]["last_foot"][1] >= MID_Y
    assert by_label["P1B"]["last_foot"][1] >= MID_Y
    assert by_label["P2A"]["last_foot"][1] < MID_Y
    assert by_label["P2B"]["last_foot"][1] < MID_Y
    # Slot A = left of slot B within the squad (x at the shared frame).
    assert by_label["P1A"]["last_foot"][0] < by_label["P1B"]["last_foot"][0]
    assert by_label["P2A"]["last_foot"][0] < by_label["P2B"]["last_foot"][0]
    # Every reference carries the ensemble signature channels the tracker's
    # _signature_similarity consumes.
    for r in refs:
        assert r["histogram"] is not None
        assert r["head_histogram"] is not None
        assert "world_height_samples" in r and "world_width_samples" in r
        assert r["n_observations"] >= 8
    assert enroller.last_result["reason"] == "enrolled"


def test_enroll_falls_back_when_fewer_than_4_persistent_chains(tmp_path):
    three = CAST[:3]
    samples = [[(cx, cy, c) for cx, cy, c in three] for _ in range(N_SAMPLES)]
    enroller = _make_enroller(tmp_path, samples)
    refs = enroller.enroll(os.path.join(str(tmp_path), "synth.mp4"))
    assert refs is None
    assert enroller.last_result["reason"] == "fewer_than_4_persistent_chains"


def test_enroll_falls_back_without_2_plus_2_side_split(tmp_path):
    # Four persistent chains, all on the NEAR side: no clean split -> None.
    cast = [(80, 170, BLUE), (240, 170, TEAL), (120, 175, RED), (260, 175, YELLOW)]
    samples = [[(cx, cy, c) for cx, cy, c in cast] for _ in range(N_SAMPLES)]
    enroller = _make_enroller(tmp_path, samples)
    refs = enroller.enroll(os.path.join(str(tmp_path), "synth.mp4"))
    assert refs is None
    assert enroller.last_result["reason"] == "no_2_plus_2_side_split"


def test_enroll_merges_occlusion_fragments_of_the_same_player(tmp_path):
    # The near-left player vanishes for 10 samples (> chain_gap_samples=6)
    # then reappears at the same spot with the same colour. Without the
    # merge pass this yields 5 persistent chains and a fragment in the top 4.
    samples = _standard_samples()
    for s in range(10, 20):
        samples[s][0] = None
    enroller = _make_enroller(tmp_path, samples)
    refs = enroller.enroll(os.path.join(str(tmp_path), "synth.mp4"))

    assert refs is not None
    # The occluded player (blue = near left = P1A) saw samples 0-9 and 20-29:
    # its two 10-observation fragments were merged back into one 20-obs
    # chain, while the ever-present three kept all 30 samples.
    by_label = {r["label"]: r["n_observations"] for r in refs}
    assert by_label["P1A"] == 20, by_label
    assert by_label["P1B"] == 30 and by_label["P2A"] == 30 and by_label["P2B"] == 30


def test_enroll_disabled_returns_none(tmp_path):
    enroller = _make_enroller(tmp_path, _standard_samples(), enabled=False)
    refs = enroller.enroll(os.path.join(str(tmp_path), "synth.mp4"))
    assert refs is None
    assert enroller.last_result["reason"] == "disabled"


# --------------------------------------------------------------------------- #
# Tracker label assignment (set_enrollment / _maybe_assign_label / stamping)
# --------------------------------------------------------------------------- #

def _tracker(**overrides):
    params = dict(
        max_players=4,
        max_disappeared=4,
        max_distance=250.0,
        gallery_reacquire_distance_px=300.0,
        gallery_reacquire_min_appearance=0.15,
        court_calibration=_FakeCourt(),
    )
    params.update(overrides)
    t = PlayerTracker(**params)
    t._initialized = True
    t.frame_count = 100
    return t


def _det(cx, cy, conf=0.9):
    return {
        "bbox": [cx - BOX_W / 2, cy - BOX_H / 2, cx + BOX_W / 2, cy + BOX_H / 2],
        "center": [float(cx), float(cy)],
        "confidence": conf,
    }


def _frame_with(players):
    """players: [(cx, cy, color)] -> (frame, dets)."""
    frame = np.zeros((H, W, 3), np.uint8)
    dets = []
    for cx, cy, color in players:
        x1, y1 = int(cx - BOX_W / 2), int(cy - BOX_H / 2)
        frame[y1:y1 + BOX_H, x1:x1 + BOX_W] = color
        dets.append(_det(cx, cy))
    return frame, dets


def _refs_from_cast(tracker, players, labels):
    """Build enrollment refs by signing the cast's coloured boxes."""
    refs = []
    frame, _ = _frame_with(players)
    for (cx, cy, color), (label, squad, slot) in zip(players, labels):
        sig = tracker.compute_enrollment_signature(
            frame, [cx - BOX_W / 2, cy - BOX_H / 2, cx + BOX_W / 2, cy + BOX_H / 2]
        )
        refs.append({"label": label, "squad": squad, "slot": slot, **sig})
    return refs


CAST_LABELS = [("P1A", 1, "A"), ("P1B", 1, "B"), ("P2A", 2, "A"), ("P2B", 2, "B")]


def _seed(tracker, players):
    """Create one track per (cx, cy, color) via the production creation path
    (_create_track -- the bootstrap-lock equivalent used by the gallery
    tests; _associate_detections early-returns while 0 tracks are active)."""
    frame, _ = _frame_with(players)
    tracker._current_frame = frame  # histograms come from the live frame
    return [
        tracker._create_track(_det(cx, cy), require_court_admission=False)
        for cx, cy, _ in players
    ]


def test_tracker_labels_follow_signature_and_are_sticky():
    tracker = _tracker()
    tracker.set_enrollment(_refs_from_cast(tracker, CAST, CAST_LABELS))
    _seed(tracker, CAST)

    frame, dets = _frame_with(CAST)
    out = tracker.update(dets, frame)
    assert len(out) == 4
    labeled = {p["player_label"]: p for p in out}
    assert sorted(labeled) == ["P1A", "P1B", "P2A", "P2B"]
    # Colour -> label mapping is the geometric one (near pair = squad 1,
    # left = A): blue is P1A, teal P1B, red P2A, yellow P2B.
    def _cx(label):
        return labeled[label]["center"][0]
    def _cy(label):
        return labeled[label]["center"][1]
    assert _cx("P1A") == 80 and _cy("P1A") == 170
    assert _cx("P1B") == 240 and _cy("P1B") == 170
    assert _cx("P2A") == 100 and _cy("P2A") == 40
    assert _cx("P2B") == 260 and _cy("P2B") == 40

    # Stickiness: swap the near pair's positions for several frames. The
    # tracker's ids follow MOTION (they cross), and the labels follow the
    # ids -- P1A must still ride the blue (teal-coloured-now) player's track,
    # never get reassigned to whichever player now stands on the left.
    first_map = {p["track_id"]: p["player_label"] for p in out}
    # label_for(): the tracker-side accessor the frame processor uses to
    # stamp actions with the enrolled player label.
    for tid, lab in first_map.items():
        assert tracker.label_for(tid) == lab
    assert tracker.label_for(999) is None
    players = [
        (80, 170, TEAL), (240, 170, BLUE),
        (100, 40, RED), (260, 40, YELLOW),
    ]
    for step in range(6):
        frame, dets = _frame_with(players)
        out = tracker.update(dets, frame)
    for p in out:
        assert p["player_label"] == first_map[p["track_id"]]
    # And the two near labels are still on DIFFERENT tracks (no steal).
    assert len({p["track_id"] for p in out if p["squad"] == 1}) == 2


def test_tracker_output_unlabeled_without_enrollment():
    tracker = _tracker()
    _seed(tracker, CAST)
    frame, dets = _frame_with(CAST)
    out = tracker.update(dets, frame)
    assert len(out) == 4
    for p in out:
        assert p["player_label"] is None
        assert p["squad"] is None
        assert p["slot"] is None


def test_set_enrollment_clears_existing_labels():
    tracker = _tracker()
    tracker.set_enrollment(_refs_from_cast(tracker, CAST, CAST_LABELS))
    _seed(tracker, CAST)
    frame, dets = _frame_with(CAST)
    out = tracker.update(dets, frame)
    assert any(p["player_label"] for p in out)

    tracker.set_enrollment(None)
    assert tracker._track_labels == {}
    assert not tracker.enrollment_active
    frame, dets = _frame_with(CAST)
    out = tracker.update(dets, frame)
    assert all(p["player_label"] is None for p in out)


def test_label_survives_gallery_retire_and_restore():
    """The owner's core promise: a player who disappears keeps number+colour.

    The tid is preserved through retire-to-gallery + restore; the label map
    is keyed by tid and only cleared on HARD removal, so the restored track
    comes back with its label."""
    tracker = _tracker(max_disappeared=3)
    tracker.set_enrollment(_refs_from_cast(tracker, CAST, CAST_LABELS))
    _seed(tracker, CAST)
    frame, dets = _frame_with(CAST)
    out = tracker.update(dets, frame)
    target = next(p for p in out if p["player_label"] == "P1A")
    tid = target["track_id"]

    # Empty frames retire the track into the gallery (appearance intact)
    # while its three teammates keep being fed (the gallery-restore path
    # only runs while active tracks exist).
    others = CAST[1:]
    for _ in range(6):
        frame3, dets3 = _frame_with(others)
        tracker.update(dets3, frame3)
    assert tid not in tracker.tracks

    # The blue player reappears where they left: gallery restore -> SAME tid.
    frame, dets = _frame_with(CAST)
    out = tracker.update(dets, frame)
    restored = [p for p in out if p["track_id"] == tid]
    assert restored, "gallery restore must bring back the original tid"
    assert restored[0]["player_label"] == "P1A"
    assert restored[0]["squad"] == 1
    assert restored[0]["slot"] == "A"


def test_tracking_outputs_byte_identical_with_and_without_enrollment():
    """Parity guard (unit level; entreno F1 gate covers it end-to-end):
    enrollment labels are display-only -- association, admission and
    retirement must not feel them."""
    label_keys = ("player_label", "squad", "slot")

    def run(with_refs):
        cv2.setRNGSeed(0)  # AGENTS.md §3: per-instance RNG for A/B harnesses
        tracker = _tracker()
        if with_refs:
            tracker.set_enrollment(_refs_from_cast(tracker, CAST, CAST_LABELS))
        _seed(tracker, CAST)
        outs = []
        # Same scripted motion for both arms: gather, drift, swap, occlude.
        seq = [CAST] * 4
        seq += [[(cx + 10 * i, cy, c) for cx, cy, c in CAST] for i in range(1, 6)]
        swap = [(240, 170, TEAL), (80, 170, BLUE), (100, 40, RED), (260, 40, YELLOW)]
        seq += [swap] * 5
        seq += [[(80, 170, BLUE), (100, 40, RED), (260, 40, YELLOW)]] * 3
        seq += [CAST] * 5
        for players in seq:
            frame, dets = _frame_with(players)
            outs.append([
                {k: v for k, v in p.items() if k not in label_keys}
                for p in tracker.update(dets, frame)
            ])
        return outs

    plain, enrolled = run(False), run(True)
    assert plain == enrolled
    # Sanity: the enrolled arm really does label things (else the comparison
    # above would be vacuous).
    cv2.setRNGSeed(0)
    t = _tracker()
    t.set_enrollment(_refs_from_cast(t, CAST, CAST_LABELS))
    _seed(t, CAST)
    frame, dets = _frame_with(CAST)
    assert any(p["player_label"] for p in t.update(dets, frame))
