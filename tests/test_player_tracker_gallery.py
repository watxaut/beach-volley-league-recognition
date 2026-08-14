"""Tests for the continuity-first identity features in PlayerTracker.

These directly exercise the phase-1b dormant gallery, since real match footage
(side changes, long occlusions) is scarce -- the entreno drills barely trigger
resurrections. The gallery's two core promises under test:
  * a player lost longer than max_disappeared re-acquires their ORIGINAL id
    (no recycling onto someone else);
  * a dormant id cannot be stolen by a bystander while its owner is away.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.tracking.player_tracker import PlayerTracker


class _FakeCourt:
    """Minimal court stand-in: everything is 'in court', team always 'A'."""
    is_calibrated = True

    def foot_point(self, bbox):
        return (int((bbox[0] + bbox[2]) / 2), int(bbox[3]))

    def is_point_in_court(self, point):
        return True

    def get_team_for_bbox(self, bbox):
        return "A"

    def world_body_size(self, bbox):
        # No ground plane in the fake court -> the height/proportions channels
        # of the ensemble signature are dropped; tests exercise motion + colour.
        return None


def _det(cx, cy, conf=0.9):
    w, h = 40, 80
    return {
        "bbox": [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
        "center": [float(cx), float(cy)],
        "confidence": conf,
    }


def _make_tracker(**overrides):
    params = dict(
        max_players=4,
        max_disappeared=4,
        max_distance=250.0,
        coast_extrapolation_cap=4,
        gallery_reacquire_distance_px=300.0,
        gallery_reacquire_min_appearance=0.15,
        court_calibration=_FakeCourt(),
    )
    params.update(overrides)
    tracker = PlayerTracker(**params)
    # Skip the rally bootstrap: lock 4 known tracks deterministically.
    tracker._initialized = True
    tracker.frame_count = 100
    return tracker


def _seed_four(tracker, positions):
    """Create one track per (cx, cy), returning the list of assigned ids in order."""
    ids = []
    for cx, cy in positions:
        ids.append(tracker._create_track(_det(cx, cy), require_court_admission=False))
    return ids


def test_gallery_restores_original_id_after_long_gap():
    tracker = _make_tracker()
    positions = [(300, 400), (700, 400), (1000, 400), (1300, 400)]
    ids = _seed_four(tracker, positions)
    assert sorted(ids) == [1, 2, 3, 4]
    p1_id, p1_pos = ids[0], positions[0]

    # Hold all four steady so velocities settle to ~0 (clean predicted positions).
    all_dets = [_det(cx, cy) for cx, cy in positions]
    for _ in range(8):
        tracker.update(list(all_dets), None, ball_active=True)

    # Drop player 1 long enough to retire to the gallery (> max_disappeared).
    without_p1 = [_det(cx, cy) for cx, cy in positions[1:]]
    for _ in range(12):
        tracker.update(list(without_p1), None, ball_active=True)

    assert p1_id not in tracker.tracks, "P1 should have retired out of active tracks"
    assert p1_id in tracker.gallery, "P1 should be dormant in the gallery"

    # Re-introduce P1 near its old position -> the SAME id must come back.
    out = tracker.update(list(all_dets), None, ball_active=True)
    out_ids = {o["track_id"] for o in out}
    assert p1_id in out_ids, f"P1 should be re-acquired as id {p1_id}, got {sorted(out_ids)}"
    assert p1_id in tracker.tracks
    assert p1_id not in tracker.gallery, "gallery entry must be consumed on restore"


def test_gallery_blocks_bystander_from_stealing_dormant_id():
    tracker = _make_tracker()
    positions = [(300, 400), (700, 400), (1000, 400), (1300, 400)]
    ids = _seed_four(tracker, positions)
    p1_id, p1_pos = ids[0], positions[0]
    for _ in range(8):
        tracker.update([_det(cx, cy) for cx, cy in positions], None, ball_active=True)

    # Retire P1.
    without_p1 = [_det(cx, cy) for cx, cy in positions[1:]]
    for _ in range(12):
        tracker.update(list(without_p1), None, ball_active=True)
    assert p1_id in tracker.gallery

    # A bystander appears far from P1's last position while P1 is dormant.
    bystander = _det(1500, 800)  # well outside the gallery reacquire gate
    out = tracker.update(list(without_p1) + [bystander], None, ball_active=True)
    out_ids = {o["track_id"] for o in out}
    assert p1_id not in out_ids, "bystander must not steal the dormant id"
    assert len(tracker.tracks) == 3, "no 4th track should be created for the bystander"
    assert p1_id in tracker.gallery, "dormant id must stay reserved for its owner"
    assert set(tracker.tracks) == set(ids[1:])

    # Now the real P1 returns -> reclaim the original id.
    out = tracker.update([_det(*p1_pos)] + list(without_p1), None, ball_active=True)
    assert p1_id in {o["track_id"] for o in out}
    assert p1_id in tracker.tracks


def test_gallery_disabled_falls_back_to_delete():
    """With the gallery off, a lost track is deleted (no dormant reservation)."""
    tracker = _make_tracker(gallery_enabled=False)
    positions = [(300, 400), (700, 400), (1000, 400), (1300, 400)]
    _seed_four(tracker, positions)
    for _ in range(8):
        tracker.update([_det(cx, cy) for cx, cy in positions], None, ball_active=True)
    for _ in range(12):
        tracker.update([_det(cx, cy) for cx, cy in positions[1:]], None, ball_active=True)
    assert tracker.gallery == {}, "gallery must stay empty when disabled"


def test_gallery_evicts_stale_dormant_to_avoid_dropping_new_player():
    """A stale dormant id (past min-hold) is reclaimed when a new on-court
    detection would otherwise be dropped for lack of a slot -- the trap fix."""
    tracker = _make_tracker(
        gallery_evict_min_hold_frames=5, gallery_reacquire_distance_px=80.0
    )
    positions = [(300, 400), (700, 400), (1000, 400), (1300, 400)]
    _seed_four(tracker, positions)
    for _ in range(8):
        tracker.update([_det(cx, cy) for cx, cy in positions], None, ball_active=True)

    # Retire player 1 well past the 5-frame min-hold.
    for _ in range(20):
        tracker.update([_det(cx, cy) for cx, cy in positions[1:]], None, ball_active=True)
    assert 1 in tracker.gallery  # player 1 dormant

    # A brand-new player appears far from player 1's last position (no gallery
    # match) while all four slots are reserved -> the stale dormant id must be
    # reclaimed so the new player is tracked instead of dropped.
    new_player = _det(1600, 200)
    out = tracker.update(
        [_det(cx, cy) for cx, cy in positions[1:]] + [new_player], None, ball_active=True
    )
    ids = {o["track_id"] for o in out}
    assert len(tracker.tracks) == 4, "new player must be tracked (slot reclaimed)"
    assert max(ids) <= 4, "no 5th id should be created"
    assert 1 not in tracker.gallery, "stale dormant id was reclaimed"


def _two_colour_frame():
    """200x200 BGR frame: left half blue, right half red."""
    f = np.zeros((200, 200, 3), dtype=np.uint8)
    f[:, :100] = (200, 0, 0)  # blue
    f[:, 100:] = (0, 0, 200)  # red
    return f


def test_signature_similarity_prefers_same_colour():
    """The ensemble's colour channel rates same-colour high, different low."""
    frame = _two_colour_frame()
    tracker = PlayerTracker(max_players=4, court_calibration=_FakeCourt())
    tracker._current_frame = frame
    blue_track = {
        "histogram": tracker._compute_histogram([30, 10, 70, 90]),
        "head_histogram": tracker._compute_head_histogram([30, 10, 70, 90]),
        "world_height_samples": [],
        "world_width_samples": [],
    }
    same = tracker._signature_similarity(blue_track, {"bbox": [30, 110, 70, 190]})  # blue
    diff = tracker._signature_similarity(blue_track, {"bbox": [130, 10, 170, 90]})  # red
    assert same > 0.7, f"same-colour similarity should be high, got {same}"
    assert diff < 0.3, f"different-colour similarity should be low, got {diff}"


def test_gallery_appearance_reacquire_after_move():
    """A player who reappears elsewhere (position gate fails) is re-acquired by
    colour -- the side-change mechanism (phase 1c, gallery pass 2)."""
    frame = _two_colour_frame()
    tracker = PlayerTracker(
        max_players=4,
        max_disappeared=4,
        max_distance=250.0,
        coast_extrapolation_cap=4,
        gallery_reacquire_distance_px=40.0,  # tight: a ~100px move won't pass the position gate
        gallery_reacquire_appearance_min=0.5,
        court_calibration=_FakeCourt(),
    )
    tracker._initialized = True
    tracker.frame_count = 100
    tracker._current_frame = frame
    p1_id = tracker._create_track({"bbox": [30, 10, 70, 90], "center": [50.0, 50.0], "confidence": 0.9})
    p2_id = tracker._create_track({"bbox": [130, 10, 170, 90], "center": [150.0, 50.0], "confidence": 0.9})
    assert p1_id != p2_id

    p1_det = {"bbox": [30, 10, 70, 90], "center": [50.0, 50.0], "confidence": 0.9}
    p2_det = {"bbox": [130, 10, 170, 90], "center": [150.0, 50.0], "confidence": 0.9}
    for _ in range(6):
        tracker.update([p1_det, p2_det], frame, ball_active=True)

    # Retire player 1.
    for _ in range(10):
        tracker.update([p2_det], frame, ball_active=True)
    assert p1_id in tracker.gallery

    # Player 1 reappears ~100px away, still in the BLUE region (same colour).
    moved = {"bbox": [30, 110, 70, 190], "center": [50.0, 150.0], "confidence": 0.9}
    out = tracker.update([p2_det, moved], frame, ball_active=True)
    ids = {o["track_id"] for o in out}
    assert p1_id in ids, f"P1 should be re-acquired by appearance, got {sorted(ids)}"
    assert p1_id in tracker.tracks

