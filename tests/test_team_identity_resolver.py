"""TeamIdentityResolver: P1A/P2A/P1B/P2B labels that survive side switches.

Synthetic beach scene: four drawn players (hair / top / bottom / skin legs)
on sand, the near pair large and seen "from behind", the far pair small and
seen "from the front" -- each player's top differs between the two views (a
bikini from behind is mostly skin + a strap; from the front it is the cups),
the cross-view gap the resolver must survive. A fake long-axis court splits
near/far at MID_Y and gives a ground scale whose LATERAL height is
view-consistent, like the real homography.

What is pinned:
  * descriptor: background-weighted (sand does not dominate), resolution-
    normalised (near and far crops of one look agree), discriminative;
  * a stable rally: every label right, no flip, CUSUM pinned at 0, occlusion
    of a far player cannot flip the orientation;
  * a side switch with SCRAMBLED tracker ids: detected within ~1 s, ZERO
    wrong labels across it (a short blackout instead), the moved squad then
    learns its new view; a second switch back is detected too;
  * min dwell: a too-early switch is held in doubt (blank labels), never
    mislabelled, and accepted once the interval has passed;
  * a silent teammate id swap (overlap, no box jump) is corrected;
  * strangers in court stay unlabeled; an off-court server keeps the label;
  * label history for actions emitted after their contact;
  * tracker integration: output labels from the team resolver, tracking
    outputs IDENTICAL to legacy mode (labels never feed back), legacy
    fallback when refs carry no identity samples; enrollment emits samples.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import pytest

from src.tracking.identity_resolver import (
    TeamIdentityResolver,
    appearance_scores,
    compute_descriptor,
    lateral_height_m,
    stack_descriptors,
)
from src.tracking.player_enrollment import PlayerEnrollment
from src.tracking.player_tracker import PlayerTracker

# --------------------------------------------------------------------------- #
# Synthetic scene
# --------------------------------------------------------------------------- #

W, H = 640, 360
MID_Y = 190
COURT = (40, 70, 600, 345)   # x1, y1, x2, y2 of the in-court rectangle
NEAR_FOOT_Y, FAR_FOOT_Y = 300, 130
NEAR_H = 150                 # pixel height of a 1.0-scale player near
SAND = np.array([150, 190, 215], dtype=np.uint8)   # BGR


def _lateral_scale(y: float) -> float:
    return 0.012 * (NEAR_FOOT_Y / max(float(y), 1.0))


def pixel_height(foot_y: float, stature: float) -> float:
    """Pixel height of a player of relative stature at a foot row."""
    return NEAR_H * stature * _lateral_scale(NEAR_FOOT_Y) / _lateral_scale(foot_y)


class FakeCourt:
    is_calibrated = True

    @staticmethod
    def foot_point(bbox):
        return (int((bbox[0] + bbox[2]) / 2), int(bbox[3]))

    def is_point_in_court(self, point):
        x, y = point
        return COURT[0] <= x <= COURT[2] and COURT[1] <= y <= COURT[3]

    def distance_to_court_px(self, point):
        x, y = point
        dx = max(COURT[0] - x, 0, x - COURT[2])
        dy = max(COURT[1] - y, 0, y - COURT[3])
        if dx == 0 and dy == 0:
            return -1.0
        return float(np.hypot(dx, dy))

    def get_team_for_bbox(self, bbox):
        return "A" if bbox[3] >= MID_Y else "B"

    def get_team(self, point):
        return "A" if point[1] >= MID_Y else "B"

    def image_to_world(self, point):
        x, y = float(point[0]), float(point[1])
        return ((x - W / 2) * _lateral_scale(y), y * 0.05)

    def world_body_size(self, bbox):
        # The tracker's ensemble signature; colour channels suffice here.
        return None


# Player look: hair, top as seen from BEHIND (near), top seen from the FRONT
# (far), bottom, stature. BGR.
SKIN = (120, 160, 210)
CAST: Dict[str, Dict] = {
    # squad 1 (near at the start): blue-shirt man + dark-bikini woman
    "P1A": dict(hair=(30, 40, 60), back=(230, 180, 90), front=(220, 175, 95),
                bottom=(60, 160, 60), stature=1.05),
    "P2A": dict(hair=(15, 15, 15), back=SKIN, front=(30, 30, 45),
                bottom=(30, 30, 40), stature=0.95, strap=(30, 30, 45)),
    # squad 2 (far at the start): teal-rashguard man + maroon-bikini woman
    "P1B": dict(hair=(40, 50, 70), back=(120, 100, 20), front=(125, 105, 30),
                bottom=(80, 40, 20), stature=1.07),
    "P2B": dict(hair=(40, 70, 110), back=SKIN, front=(40, 20, 120),
                bottom=(20, 20, 20), stature=0.93, strap=(40, 20, 120)),
}
LABELS = ["P1A", "P2A", "P1B", "P2B"]
SQUAD = {"P1A": 1, "P2A": 1, "P1B": 2, "P2B": 2}
SLOT = {"P1A": "A", "P2A": "B", "P1B": "A", "P2B": "B"}


def body_bbox(cx: float, foot_y: float, stature: float) -> List[float]:
    h = pixel_height(foot_y, stature)
    w = 0.38 * h
    return [cx - w / 2, foot_y - h, cx + w / 2, foot_y]


def draw_player(frame: np.ndarray, label: str, bbox: Sequence[float], view: str) -> None:
    look = CAST[label]
    x1, y1, x2, y2 = (int(round(v)) for v in bbox)
    h = y2 - y1
    cx = (x1 + x2) // 2
    bw = x2 - x1
    tw = max(2, int(bw * 0.7))        # torso width
    hw = max(2, int(bw * 0.4))        # head width
    lw = max(1, int(bw * 0.18))       # leg width

    def rect(xa, ya, xb, yb, color):
        frame[max(0, ya):max(0, yb), max(0, xa):max(0, xb)] = color

    rect(cx - hw // 2, y1, cx + hw // 2, y1 + int(0.15 * h), look["hair"])
    top = look["back"] if view == "near" else look["front"]
    rect(cx - tw // 2, y1 + int(0.15 * h), cx + tw // 2, y1 + int(0.45 * h), top)
    if "strap" in look and view == "near":
        rect(cx - tw // 2, y1 + int(0.25 * h), cx + tw // 2, y1 + int(0.28 * h), look["strap"])
    if "strap" in look:
        # Bikini: skin between the top and the bottom.
        rect(cx - tw // 2, y1 + int(0.36 * h), cx + tw // 2, y1 + int(0.5 * h), SKIN)
    rect(cx - tw // 2, y1 + int(0.5 * h), cx + tw // 2, y1 + int(0.68 * h), look["bottom"])
    rect(cx - tw // 2 + 1, y1 + int(0.68 * h), cx - tw // 2 + 1 + lw, y2, SKIN)
    rect(cx + tw // 2 - 1 - lw, y1 + int(0.68 * h), cx + tw // 2 - 1, y2, SKIN)


_NOISE_BANK: List[np.ndarray] = []


def _noise(rng: np.random.Generator, sigma: float) -> np.ndarray:
    """Sensor noise from a small precomputed bank (rendering cost, not
    realism, is what this saves -- the resolver still sees noisy pixels)."""
    if not _NOISE_BANK:
        bank_rng = np.random.default_rng(1234)
        _NOISE_BANK.extend(
            bank_rng.normal(0.0, 1.0, (H, W, 3)).astype(np.float32) for _ in range(6)
        )
    return _NOISE_BANK[int(rng.integers(len(_NOISE_BANK)))] * sigma


def scene(
    placements: Sequence[Tuple[str, float, float]], rng: np.random.Generator,
    noise: float = 6.0,
) -> np.ndarray:
    """Frame with sand + the given (label, cx, foot_y) players."""
    frame = np.empty((H, W, 3), dtype=np.uint8)
    frame[:] = SAND
    frame[: H // 5] = (200, 150, 90)   # sky / dunes band
    for label, cx, fy in sorted(placements, key=lambda t: t[2]):
        view = "near" if fy >= MID_Y else "far"
        draw_player(frame, label, body_bbox(cx, fy, CAST[label]["stature"]), view)
    if noise:
        frame = np.clip(frame.astype(np.float32) + _noise(rng, noise), 0, 255).astype(np.uint8)
    return frame


def positions(near_squad: int, t: int, rng: np.random.Generator) -> List[Tuple[str, float, float]]:
    """Rally positions: near pair left/right on the near half, far pair on
    the far half, with a little jitter."""
    near = [l for l in LABELS if SQUAD[l] == near_squad]
    far = [l for l in LABELS if SQUAD[l] != near_squad]
    out = []
    for i, label in enumerate(near):
        out.append((label, 200 + 240 * i + 8 * np.sin(t / 7 + i), NEAR_FOOT_Y + rng.normal(0, 2)))
    for i, label in enumerate(far):
        out.append((label, 230 + 180 * i + 5 * np.cos(t / 9 + i), FAR_FOOT_Y + rng.normal(0, 1)))
    return out


def tracked(placements, tid_of: Dict[str, int]) -> List[Dict]:
    """Tracker-output dicts for the placements under a label->tid map."""
    out = []
    for label, cx, fy in placements:
        bbox = body_bbox(cx, fy, CAST[label]["stature"])
        out.append({
            "track_id": tid_of[label], "bbox": bbox,
            "center": [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2],
            "confidence": 0.9, "_truth": label,
        })
    return out


def enrollment_refs(n_frames: int = 40, seed: int = 0) -> List[Dict]:
    """References like PlayerEnrollment builds: squad 1 near, squad 2 far."""
    rng = np.random.default_rng(seed)
    court = FakeCourt()
    samples: Dict[str, List] = {l: [] for l in LABELS}
    heights: Dict[str, List] = {l: [] for l in LABELS}
    for t in range(n_frames):
        pl = positions(1, t * 5, rng)
        frame = scene(pl, rng)
        for label, cx, fy in pl:
            bbox = body_bbox(cx, fy, CAST[label]["stature"])
            samples[label].append(compute_descriptor(frame, bbox))
            heights[label].append(lateral_height_m(court, bbox))
    return [
        {
            "label": l, "squad": SQUAD[l], "slot": SLOT[l],
            "identity_samples": samples[l], "identity_heights": heights[l],
        }
        for l in LABELS
    ]


def truth_labels(players: List[Dict], labels: Dict[int, Tuple[str, int, str]]):
    """(n_correct, n_wrong, n_none) of resolver labels vs the drawn truth."""
    ok = wrong = none = 0
    for p in players:
        got = labels.get(p["track_id"])
        if got is None:
            none += 1
        elif got[0] == p["_truth"]:
            ok += 1
        else:
            wrong += 1
    return ok, wrong, none


def run(
    resolver, frames: int, near_squad: int, tid_of: Dict[str, int], start: int,
    rng: np.random.Generator, record: Optional[List] = None,
):
    """Feed ``frames`` rally frames; returns per-frame (ok, wrong, none)."""
    stats = []
    for t in range(start, start + frames):
        pl = positions(near_squad, t, rng)
        frame = scene(pl, rng)
        players = tracked(pl, tid_of)
        labels = resolver.update(t, frame, players)
        stats.append(truth_labels(players, labels))
        if record is not None:
            record.append((t, dict(labels), resolver.state()))
    return stats


TIDS = {"P1A": 1, "P2A": 2, "P1B": 3, "P2B": 4}


def _resolver(**kw) -> TeamIdentityResolver:
    params = dict(min_switch_interval_frames=150)
    params.update(kw)
    res = TeamIdentityResolver(enrollment_refs(), FakeCourt(), **params)
    res.LEARN_INTERVAL = 30          # learn the new view in fewer synthetic frames
    res.ORIENT_WARMUP_FRAMES = 100   # synthetic openings are short
    return res


def _blank(resolver, start: int, n: int, rng) -> int:
    """Players off camera (walking around the post): no bodies at all."""
    for t in range(start, start + n):
        resolver.update(t, scene([], rng), [])
    return start + n


def _totals(stats) -> np.ndarray:
    return np.array(stats).sum(axis=0)


# --------------------------------------------------------------------------- #
# Descriptor
# --------------------------------------------------------------------------- #

def _sim(a, b) -> float:
    pa, ma = stack_descriptors([a])
    pb, mb = stack_descriptors([b])
    return float(appearance_scores(pa, ma, pb, mb)[0])


def test_descriptor_is_resolution_normalised_and_discriminative():
    rng = np.random.default_rng(0)
    near_box = body_bbox(320, NEAR_FOOT_Y, 1.0)
    big = scene([], rng, noise=0)
    draw_player(big, "P1A", near_box, "near")
    small = scene([], rng, noise=0)
    small_box = [320 - 0.38 * 60 / 2, NEAR_FOOT_Y - 60, 320 + 0.38 * 60 / 2, NEAR_FOOT_Y]
    draw_player(small, "P1A", small_box, "near")
    other = scene([], rng, noise=0)
    draw_player(other, "P1B", near_box, "near")
    d_big = compute_descriptor(big, near_box)
    d_small = compute_descriptor(small, small_box)
    d_other = compute_descriptor(other, near_box)
    assert _sim(d_big, d_small) > 0.85          # same look at 150 px and 60 px
    assert _sim(d_big, d_other) < _sim(d_big, d_small) - 0.2


def test_descriptor_down_weights_the_background_colour():
    """A box twice as wide as the body (lots of sand inside) still matches
    the tight box: the band beside the box tells the sand apart."""
    rng = np.random.default_rng(0)
    frame = scene([], rng, noise=0)
    box = body_bbox(320, NEAR_FOOT_Y, 1.0)
    draw_player(frame, "P1B", box, "near")
    w = box[2] - box[0]
    loose = [box[0] - w / 2, box[1], box[2] + w / 2, box[3]]
    tight_d, loose_d = compute_descriptor(frame, box), compute_descriptor(frame, loose)
    assert _sim(tight_d, loose_d) > 0.8


def test_descriptor_rejects_degenerate_boxes():
    frame = np.zeros((50, 50, 3), np.uint8)
    assert compute_descriptor(frame, [10, 10, 12, 40]) is None
    assert compute_descriptor(frame, [60, 60, 90, 99]) is None
    assert compute_descriptor(None, [0, 0, 10, 10]) is None


def test_lateral_height_is_view_consistent():
    court = FakeCourt()
    near = lateral_height_m(court, body_bbox(320, NEAR_FOOT_Y, 1.0))
    far = lateral_height_m(court, body_bbox(320, FAR_FOOT_Y, 1.0))
    assert near == pytest.approx(far, rel=0.02)
    assert lateral_height_m(object(), [0, 0, 10, 10]) is None


# --------------------------------------------------------------------------- #
# Resolver behaviour
# --------------------------------------------------------------------------- #

def test_stable_rally_labels_everyone_and_never_flips():
    res = _resolver()
    rng = np.random.default_rng(1)
    stats = run(res, 200, 1, TIDS, 0, rng)
    ok, wrong, none = _totals(stats)
    assert wrong == 0
    # Only the fresh-tracklet claim delay leaves anyone unlabeled.
    assert none <= 4 * res.CLAIM_MIN_FRAMES
    assert res.flips == [] and not res.doubt
    assert res.cusum < 0.25 * res.switch_threshold
    assert all(s == (4, 0, 0) for s in stats[10:])


def test_side_switch_with_scrambled_ids_has_no_wrong_labels():
    res = _resolver()
    rng = np.random.default_rng(1)
    run(res, 200, 1, TIDS, 0, rng)
    t = _blank(res, 200, 60, rng)
    scrambled = {"P1A": 3, "P2A": 1, "P1B": 4, "P2B": 2}
    stats = run(res, 250, 2, scrambled, t, rng)
    ok, wrong, none = _totals(stats)
    assert wrong == 0
    assert len(res.flips) == 1 and res.near_squad == 2
    flip = res.flips[0]
    assert t <= flip["onset"] and flip["frame"] - t <= 30   # ~1 s at 30 fps
    assert all(s == (4, 0, 0) for s in stats[40:])
    # The moved squads learned the view they were never enrolled in.
    learned = res.state()["learned"]
    assert learned["P1A"]["far"] > 0 and learned["P2A"]["far"] > 0
    assert learned["P1B"]["near"] > 0 and learned["P2B"]["near"] > 0


def test_second_switch_back_is_detected():
    res = _resolver()
    rng = np.random.default_rng(2)
    run(res, 150, 1, TIDS, 0, rng)
    t = _blank(res, 150, 40, rng)
    run(res, 320, 2, {"P1A": 3, "P2A": 1, "P1B": 4, "P2B": 2}, t, rng)
    t = _blank(res, t + 320, 40, rng)
    stats = run(res, 120, 1, {"P1A": 2, "P2A": 4, "P1B": 1, "P2B": 3}, t, rng)
    learned = res.state()["learned"]
    assert all(v[view] >= 2 for v in learned.values() for view in v)
    assert [f["near_squad"] for f in res.flips] == [2, 1]
    assert _totals(stats)[1] == 0
    assert all(s == (4, 0, 0) for s in stats[40:])


def test_too_early_switch_waits_in_doubt_without_wrong_labels():
    res = _resolver(min_switch_interval_frames=400)
    rng = np.random.default_rng(3)
    run(res, 150, 1, TIDS, 0, rng)   # past the baseline warm-up
    t = _blank(res, 150, 20, rng)
    stats = run(res, 400, 2, {"P1A": 3, "P2A": 1, "P1B": 4, "P2B": 2}, t, rng)
    assert _totals(stats)[1] == 0
    flip = res.flips[0]
    assert flip["frame"] >= 400                       # not before the dwell
    blocked = stats[: 400 - t - 1]
    assert all(s[0] == 0 for s in blocked)            # doubt: blank, not wrong
    assert all(s == (4, 0, 0) for s in stats[400 - t + 40:])


def test_silent_teammate_swap_is_corrected():
    """Near teammates cross; the tracker swaps their ids at full overlap
    (no box jump). Labels must return to the right bodies quickly."""
    res = _resolver()
    rng = np.random.default_rng(4)
    t = 150
    run(res, t, 1, TIDS, 0, rng)
    wrong_frames = []
    for k in range(60):
        a, b = 200 + 4 * k, 440 - 4 * k
        pl = [("P1A", a, NEAR_FOOT_Y), ("P2A", b, NEAR_FOOT_Y + 3),
              ("P1B", 230, FAR_FOOT_Y), ("P2B", 410, FAR_FOOT_Y)]
        tid = dict(TIDS)
        if k >= 30:
            tid["P1A"], tid["P2A"] = TIDS["P2A"], TIDS["P1A"]
        players = tracked(pl, tid)
        labels = res.update(t, scene(pl, rng), players)
        if truth_labels(players, labels)[1]:
            wrong_frames.append(k)
        t += 1
    # While the boxes merge the labels are withheld; after they separate the
    # occluded crop is ignored and the slow evidence turns within ~0.5 s.
    assert len(wrong_frames) <= 15 and all(30 <= k <= 50 for k in wrong_frames)
    assert truth_labels(players, labels) == (4, 0, 0)
    assert res.flips == []


def test_far_player_occluded_by_a_near_body_does_not_flip():
    res = _resolver()
    rng = np.random.default_rng(5)
    run(res, 100, 1, TIDS, 0, rng)
    for t in range(100, 200):
        pl = positions(1, t, rng)
        if 120 <= t < 180:   # P2B's box slides over the far-left player's column
            pl = [(l, (pl[2][1] + 6 if l == "P2B" else cx), fy) for l, cx, fy in pl]
        res.update(t, scene(pl, rng), tracked(pl, TIDS))
    assert res.flips == [] and not res.doubt
    assert res.cusum < 0.25 * res.switch_threshold


def test_clean_bodies_carry_their_anchor_similarities():
    """What the post-run identity read works from: the similarity of every
    clean body to each player's fixed anchors, as the decision computed it."""
    res = _resolver()
    rng = np.random.default_rng(6)
    run(res, 30, 1, TIDS, 0, rng)
    order = [m.label for m in res.players]
    seen = {o.tid: o for o in res.last_observations}
    assert len(seen) == 4
    for label, tid in TIDS.items():
        sims = seen[tid].anchor_sims
        assert sims is not None and len(sims) == 4
        assert order[int(np.argmax(sims))] == label      # enrolled view: own anchor wins
    # two far bodies merged into one another show two people each: no
    # similarities for them, the near pair keeps its own
    pl = positions(1, 30, rng)
    pl = [(l, (pl[2][1] + 6 if l == "P2B" else cx), fy) for l, cx, fy in pl]
    res.update(30, scene(pl, rng), tracked(pl, TIDS))
    seen = {o.tid: o for o in res.last_observations}
    assert seen[TIDS["P1B"]].anchor_sims is None and seen[TIDS["P2B"]].anchor_sims is None
    assert seen[TIDS["P1A"]].anchor_sims is not None


def test_stranger_in_court_stays_unlabeled():
    res = _resolver()
    rng = np.random.default_rng(6)
    for t in range(60):
        pl = positions(1, t, rng)
        frame = scene(pl, rng)
        box = body_bbox(560, NEAR_FOOT_Y, 1.0)
        frame[int(box[1]):int(box[3]), int(box[0]):int(box[2])] = (0, 140, 255)
        players = tracked(pl, TIDS) + [{
            "track_id": 9, "bbox": box, "center": [560, 250], "_truth": None,
        }]
        labels = res.update(t, frame, players)
    assert 9 not in labels
    assert sorted(l[0] for l in labels.values()) == ["P1A", "P1B", "P2A", "P2B"]


def test_off_court_server_keeps_the_label_until_its_side_disagrees():
    res = _resolver()
    rng = np.random.default_rng(7)
    run(res, 60, 1, TIDS, 0, rng)
    pl = positions(1, 60, rng)
    players = tracked(pl, TIDS)
    server = next(p for p in players if p["_truth"] == "P1A")
    h = server["bbox"][3] - server["bbox"][1]
    server["bbox"] = [server["bbox"][0], 350 - h, server["bbox"][2], 350]  # behind the baseline
    labels = res.update(60, scene(pl, rng), players)
    assert labels[TIDS["P1A"]][0] == "P1A"
    # The same id now reported on the FAR side: a near-squad label cannot be there.
    server["bbox"] = [300, 20, 330, 60]
    labels = res.update(61, scene(pl, rng), players)
    assert TIDS["P1A"] not in labels


def test_label_history_answers_for_the_contact_frame():
    res = _resolver()
    rng = np.random.default_rng(8)
    run(res, 30, 1, TIDS, 0, rng)
    assert res.label_at(TIDS["P1A"], 20)[0] == "P1A"
    assert res.label_at(TIDS["P1A"], 2) is None       # before the claim delay
    assert res.label_at(TIDS["P1A"])[0] == "P1A"      # current
    assert res.label_at(None) is None


def test_from_references_needs_identity_samples_and_a_2_plus_2_split():
    refs = enrollment_refs(n_frames=10)
    assert TeamIdentityResolver.from_references(refs, FakeCourt()) is not None
    bare = [{k: v for k, v in r.items() if not k.startswith("identity")} for r in refs]
    assert TeamIdentityResolver.from_references(bare, FakeCourt()) is None
    lopsided = [dict(r, squad=1) for r in refs]
    assert TeamIdentityResolver.from_references(lopsided, FakeCourt()) is None
    assert TeamIdentityResolver.from_references(refs[:3], FakeCourt()) is None


# --------------------------------------------------------------------------- #
# Tracker integration
# --------------------------------------------------------------------------- #

def _tracker_refs(tracker) -> List[Dict]:
    """Full enrollment refs: legacy signature keys + identity samples."""
    rng = np.random.default_rng(0)
    pl = positions(1, 0, rng)
    frame = scene(pl, rng)
    by_label = {r["label"]: r for r in enrollment_refs()}
    refs = []
    for label, cx, fy in pl:
        sig = tracker.compute_enrollment_signature(
            frame, body_bbox(cx, fy, CAST[label]["stature"]))
        refs.append({**by_label[label], **sig})
    return refs


def _det(bbox):
    return {"bbox": list(bbox), "center": [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2],
            "confidence": 0.9}


def _run_tracker(mode: str, n_before=150, n_after=100):
    cv2.setRNGSeed(0)  # AGENTS.md §3: per-instance RNG for A/B harnesses
    rng = np.random.default_rng(11)
    tracker = PlayerTracker(
        court_calibration=FakeCourt(), max_players=4, max_disappeared=90,
        max_distance=250.0, identity_mode=mode, identity_min_switch_interval_frames=100,
    )
    tracker.set_enrollment(_tracker_refs(tracker))
    if tracker.team_identity is not None:
        tracker.team_identity.ORIENT_WARMUP_FRAMES = 100   # short synthetic opening
    tracker._initialized = True
    pl = positions(1, 0, rng)
    tracker._current_frame = scene(pl, rng)
    for label, cx, fy in pl:
        tracker._create_track(_det(body_bbox(cx, fy, CAST[label]["stature"])),
                              require_court_admission=False)
    outs, truth = [], []
    for t in range(n_before + 30 + n_after):
        if n_before <= t < n_before + 30:
            pl = []
        else:
            pl = positions(1 if t < n_before else 2, t, rng)
        frame = scene(pl, rng)
        dets = [_det(body_bbox(cx, fy, CAST[l]["stature"])) for l, cx, fy in pl]
        out = tracker.update(dets, frame, frame_index=t)
        outs.append(out)
        truth.append(pl)
    return tracker, outs, truth


def test_tracking_is_identical_in_team_and_legacy_modes():
    label_keys = ("player_label", "squad", "slot")
    _, team, _ = _run_tracker("team")
    _, legacy, _ = _run_tracker("legacy")
    strip = lambda outs: [[{k: v for k, v in p.items() if k not in label_keys} for p in o]
                          for o in outs]
    assert strip(team) == strip(legacy)


def test_tracker_output_labels_come_from_the_team_resolver_across_a_switch():
    tracker, outs, truth = _run_tracker("team")
    assert tracker.team_identity is not None
    assert tracker.identity_state()["flips"], "the switch was not detected"

    def label_of_truth(out, pl):
        got = {}
        for p in out:
            if p.get("predicted"):
                continue
            cx = (p["bbox"][0] + p["bbox"][2]) / 2
            fy = p["bbox"][3]
            nearest = min(pl, key=lambda q: abs(q[1] - cx) + abs(q[2] - fy))
            got[nearest[0]] = p["player_label"]
        return got

    wrong = 0
    for out, pl in zip(outs, truth):
        if not pl:
            continue
        for who, label in label_of_truth(out, pl).items():
            wrong += label is not None and label != who
    assert wrong == 0
    final = label_of_truth(outs[-1], truth[-1])
    assert final == {l: l for l in ("P1A", "P2A", "P1B", "P2B")}
    # label_for answers at a past frame from the history.
    tid = next(p["track_id"] for p in outs[60] if p["player_label"] == "P1A")
    assert tracker.label_for(tid, frame=60) == "P1A"


def test_tracker_falls_back_to_legacy_labels_without_identity_samples():
    tracker = PlayerTracker(court_calibration=FakeCourt(), max_players=4)
    refs = [{k: v for k, v in r.items() if not k.startswith("identity")}
            for r in _tracker_refs(tracker)]
    tracker.set_enrollment(refs)
    assert tracker.team_identity is None and tracker.identity_state() is None
    tracker._track_labels = {7: ("P2B", 2, "B")}
    assert tracker.label_for(7, frame=123) == "P2B"


def test_tracker_reset_rebuilds_a_fresh_resolver():
    tracker, _, _ = _run_tracker("team", n_before=60, n_after=0)
    before = tracker.team_identity
    tracker.reset()
    assert tracker.team_identity is not None and tracker.team_identity is not before
    assert tracker.identity_state()["flips"] == []


def test_enrollment_references_carry_identity_samples(tmp_path):
    """The pre-pass stores per-sample descriptors + heights for the resolver."""
    rng = np.random.default_rng(0)
    path = os.path.join(str(tmp_path), "synth.mp4")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 30, (W, H))
    assert writer.isOpened()
    placements = [positions(1, 5 * k, rng) for k in range(20)]
    for pl in placements:
        frame = scene(pl, rng, noise=0)
        for _ in range(5):
            writer.write(frame)
    writer.release()

    class _Detector:
        def __init__(self):
            self.calls = 0

        def detect(self, frame):
            pl = placements[min(self.calls, len(placements) - 1)]
            self.calls += 1
            return [_det(body_bbox(cx, fy, CAST[l]["stature"])) for l, cx, fy in pl]

    court = FakeCourt()
    enroller = PlayerEnrollment(
        court_calibration=court, player_detector=_Detector(),
        tracker=PlayerTracker(court_calibration=court, max_players=4),
        max_frames=100, stride=5, min_observations=8,
    )
    refs = enroller.enroll(path)
    assert refs is not None and len(refs) == 4
    for ref in refs:
        assert len(ref["identity_samples"]) == ref["n_observations"] == 20
        assert len(ref["identity_heights"]) == 20
        assert all(h is not None for h in ref["identity_heights"])
    assert TeamIdentityResolver.from_references(refs, court) is not None
