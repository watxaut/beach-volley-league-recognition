"""Court calibration without clicks (``src/detection/court_autocalibration``).

No footage in the repo, so the detector is exercised on DRAWN courts: a known
pinhole camera looks at a 16 x 8 m court of line tape on noisy sand, a net
(tape, bottom band, posts) and a cluttered background, and the 8 points it
returns are compared with where that camera puts them. The real-footage
record is ``docs/auto_calibration.md`` (``scripts/score_autocalibration.py``).

What is pinned: the points are right when the tape shows, a corner outside
the frame is extrapolated, a far baseline seen by ONE read is a proposal and
not a calibration (precision first), the known focal length turns it into
one, and a picture without a court is refused.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import pytest

from src.detection import court_autocalibration as ac
from src.detection.court_calibration import CourtCalibration
from src.postrun.geometry import CourtGeometry

W, H = 1920, 1080
SAND = (150, 195, 222)          # BGR
TAPE = (205, 120, 45)
NET_H = 2.43


class Camera:
    """Pinhole camera behind the near baseline, looking down the court."""

    def __init__(self, focal: float = 1900.0, height: float = 3.3, behind: float = 8.0,
                 across: float = 4.3, roll_deg: float = 0.7, aim: Tuple[float, float] = (4.1, 6.5)
                 ) -> None:
        self.focal = focal
        centre = np.array([across, 16.0 + behind, height])
        forward = np.array([aim[0], aim[1], 1.0]) - centre
        forward /= np.linalg.norm(forward)
        right = np.cross(np.array([0.0, 0.0, 1.0]), forward)       # world x = 0 is image-left
        right /= np.linalg.norm(right)
        down = np.cross(right, forward)
        r = math.radians(roll_deg)
        right, down = (math.cos(r) * right + math.sin(r) * down,
                       -math.sin(r) * right + math.cos(r) * down)
        self.R = np.stack([right, down, forward])
        self.centre = centre

    def project(self, point: Sequence[float]) -> np.ndarray:
        p = self.R @ (np.asarray(point, dtype=float) - self.centre)
        return np.array([W / 2 + self.focal * p[0] / p[2], H / 2 + self.focal * p[1] / p[2]])

    def quad(self, corners: Sequence[Sequence[float]]) -> np.ndarray:
        return np.array([self.project(c) for c in corners]).round().astype(np.int32)


def _ground_strip(cam: Camera, a: Sequence[float], b: Sequence[float], width: float = 0.05
                  ) -> np.ndarray:
    """A tape on the sand from ``a`` to ``b`` (metres)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = (b - a) / np.linalg.norm(b - a)
    n = np.array([-d[1], d[0]]) * width / 2.0
    return cam.quad([[*(a + n), 0], [*(b + n), 0], [*(b - n), 0], [*(a - n), 0]])


def draw_court(cam: Camera, far_tape: bool = True, buried: Sequence[Tuple[str, float, float]] = (),
               tape: bool = True, seed: int = 3, tape_bgr: Tuple[int, int, int] = TAPE
               ) -> np.ndarray:
    """The scene. ``buried``: (line, from_m, to_m) stretches of tape under the sand;
    lines are ``left`` / ``right`` (metres from the near corner) and ``near``."""
    rng = np.random.default_rng(seed)
    img = np.zeros((H, W, 3), np.uint8)
    # a cluttered background: blocks of dark, varied colour
    blocks = rng.integers(20, 150, size=(H // 12, W // 12, 3), dtype=np.uint8)
    img[:] = cv2.resize(blocks, (W, H), interpolation=cv2.INTER_NEAREST)
    # the sand: everything below the foot of a wall behind the far baseline
    wall_y = -3.0
    a, b = cam.project([-30, wall_y, 0]), cam.project([38, wall_y, 0])
    xs = np.arange(W)
    foot = a[1] + (xs - a[0]) * (b[1] - a[1]) / (b[0] - a[0])
    sand = (np.arange(H)[:, None] > foot[None, :]).astype(np.uint8) * 255
    shade = cv2.resize(rng.normal(0, 1, (H // 6, W // 6)).astype(np.float32), (W, H))
    shade = np.clip(1.0 + 0.10 * shade + 0.03 * rng.normal(0, 1, (H, W)), 0.6, 1.3)
    for c in range(3):                               # footprints change brightness, not colour
        img[:, :, c] = np.where(sand > 0, np.clip(SAND[c] * shade, 0, 255), img[:, :, c])
    # a dark banner along the wall
    cv2.fillPoly(img, [cam.quad([[-30, wall_y, 0], [38, wall_y, 0], [38, wall_y, 1.0],
                                 [-30, wall_y, 1.0]])], (38, 36, 34))
    if tape:
        lines: Dict[str, Tuple[Tuple[float, float], Tuple[float, float]]] = {
            "near": ((0, 16), (8, 16)), "left": ((0, 16), (0, 0)), "right": ((8, 16), (8, 0))}
        if far_tape:
            lines["far"] = ((0, 0), (8, 0))
        for name, (a, b) in lines.items():
            length = math.dist(a, b)
            cuts = sorted((lo, hi) for ln, lo, hi in buried if ln == name)
            start = 0.0
            for lo, hi in cuts + [(length, length)]:
                if lo > start:
                    p = np.asarray(a) + (np.asarray(b) - a) * start / length
                    q = np.asarray(a) + (np.asarray(b) - a) * lo / length
                    cv2.fillPoly(img, [_ground_strip(cam, p, q)], tape_bgr, lineType=cv2.LINE_AA)
                start = max(start, hi)
    # the net: posts, tape, bottom band
    for x in (-0.9, 8.9):
        cv2.fillPoly(img, [cam.quad([[x - 0.1, 8, 0], [x + 0.1, 8, 0], [x + 0.1, 8, 2.6],
                                     [x - 0.1, 8, 2.6]])], (40, 200, 235))
    for top in (NET_H, NET_H - 1.0 + 0.07):
        cv2.fillPoly(img, [cam.quad([[-0.8, 8, top - 0.07], [8.8, 8, top - 0.07], [8.8, 8, top],
                                     [-0.8, 8, top]])], (235, 235, 235), lineType=cv2.LINE_AA)
    return cv2.GaussianBlur(img, (3, 3), 0)


def truth(cam: Camera) -> np.ndarray:
    """The 8 points as the camera sees them, in calibration order."""
    return np.array([cam.project(p) for p in (
        (0, 0, 0), (8, 0, 0), (8, 16, 0), (0, 16, 0),
        (0, 8, 0), (8, 8, 0), (0, 8, NET_H), (8, 8, NET_H))])


def eight(points: Dict) -> np.ndarray:
    return np.array(points["court_corners"] + points["midcourt_points"]
                    + points["net_top_points"], dtype=float)


def corner_errors(points: Dict, cam: Camera) -> np.ndarray:
    return np.linalg.norm(eight(points)[:4] - truth(cam)[:4], axis=1)


@pytest.fixture(scope="module")
def cam() -> Camera:
    return Camera()


@pytest.fixture(scope="module")
def full(cam: Camera) -> ac.AutoCalibration:
    return ac.detect(draw_court(cam))


def test_a_court_whose_tape_shows_is_found_and_accepted(full, cam):
    assert full.accepted, full.reasons
    assert corner_errors(full.points, cam).max() <= 4.0
    got, want = eight(full.points), truth(cam)
    # under the net: the middle of the court; on the tape: its top edge
    assert np.abs(got[4:6] - want[4:6]).max() <= 5.0
    assert np.abs(got[6:, 1] - want[6:, 1]).max() <= 5.0
    assert full.points["frame_dimensions"] == [H, W]
    assert "far_tape" in full.checks["far_baseline"]["agreeing"]


def test_the_net_reads_its_height_and_the_camera_is_recovered(full, cam):
    assert abs(full.checks["net_top_height_m"] - NET_H) <= 0.12
    camera = full.checks["camera"]
    assert abs(camera["focal_px"] - cam.focal) / cam.focal <= 0.04
    assert abs(camera["height_m"] - 3.3) <= 0.25
    assert abs(camera["behind_near_baseline_m"] - 8.0) <= 0.6


def test_tape_colour_is_read_off_the_picture_not_assumed(cam):
    """A court taped in another colour is found the same way."""
    img = draw_court(cam)
    yellow = img.copy()
    blue = np.all(np.abs(img.astype(int) - np.array(TAPE)) < 60, axis=2)
    yellow[blue] = (30, 215, 250)
    result = ac.detect(yellow)
    assert result.accepted, result.reasons
    assert result.checks["tape_colour_lab_ab"][1] > result.checks["sand_colour_lab_ab"][1]
    assert corner_errors(result.points, cam).max() <= 6.0


def test_a_black_tape_with_no_colour_of_its_own_is_found_by_lightness():
    """Masnou (20261012): black tape on pale sand, a low tripod. The chroma pass
    sees no tape at all; the court is found by lightness, read in L, a and b."""
    low = Camera(focal=1780.0, height=1.6, behind=8.7, across=4.1, aim=(4.0, 4.0))
    # dark, of the sand's own hue (masnou reads Lab a/b 128/140 on a sand of 128/141)
    result = ac.detect(draw_court(low, tape_bgr=(32, 71, 90)))
    assert result.accepted, result.reasons
    assert result.checks["court_found_by"] == "lightness"
    sand_l, tape_l = result.checks["sand_colour_lab"][0], result.checks["tape_colour_lab"][0]
    assert tape_l < sand_l - 40
    assert corner_errors(result.points, low).max() <= 6.0


def test_a_coloured_tape_never_takes_the_lightness_path(full):
    assert "court_found_by" not in full.checks


def test_buried_far_baseline_two_sideline_ends_agree(cam):
    result = ac.detect(draw_court(cam, far_tape=False))
    assert result.accepted, result.reasons
    assert sorted(result.checks["far_baseline"]["agreeing"]) == ["left_end", "right_end"]
    assert corner_errors(result.points, cam).max() <= 5.0


def test_one_read_of_the_far_baseline_is_a_proposal_not_a_calibration(cam):
    """Right sideline buried for its last 2.5 m: only the left tape reaches the
    far corner. The points are still right; nothing confirms them."""
    img = draw_court(cam, far_tape=False, buried=[("right", 13.5, 16.0)])
    result = ac.detect(img)
    assert not result.accepted
    assert any("one read only" in r for r in result.reasons)
    # the farther end is taken: a tape ends short of its corner, never beyond
    assert corner_errors(result.points, cam).max() <= 6.0


def test_the_known_focal_length_confirms_a_single_read(cam):
    img = draw_court(cam, far_tape=False, buried=[("right", 13.5, 16.0)])
    result = ac.detect(img, focals=[cam.focal * 1.01])
    assert result.accepted, result.reasons
    assert "camera" in result.checks["far_baseline"]["agreeing"]
    assert corner_errors(result.points, cam).max() <= 6.0


def test_a_wrong_focal_length_cannot_side_with_a_tape_that_ends_short(cam):
    """A focal length 12 % off puts the far baseline 2 m nearer, right where
    the buried right tape stops. The two would agree -- but the LEFT tape is
    seen running on beyond that line, and a tape cannot pass its own corner."""
    img = draw_court(cam, far_tape=False, buried=[("right", 13.5, 16.0)])
    result = ac.detect(img, focals=[cam.focal * 1.12])
    assert not result.accepted
    assert result.checks["far_baseline"]["agreeing"] == ["left_end"]
    assert corner_errors(result.points, cam).max() <= 6.0


def test_both_far_ends_buried_alike_is_caught_by_nothing_but_the_camera(cam):
    """Both tapes end 2 m short of the far baseline: they agree with each
    other on a baseline that is not there. This is the detector's blind spot
    (docs/auto_calibration.md); the known focal length does not take its side."""
    img = draw_court(cam, far_tape=False, buried=[("left", 14.0, 16.0), ("right", 14.0, 16.0)])
    result = ac.detect(img, focals=[cam.focal])
    assert "camera" not in result.checks["far_baseline"]["agreeing"]


def test_a_near_corner_outside_the_frame_is_extrapolated():
    aside = Camera(across=5.4, aim=(4.6, 6.5))       # the tripod stands right of the axis
    want = truth(aside)
    assert want[3, 0] < -100                         # near-left corner is not in the picture
    result = ac.detect(draw_court(aside))
    assert result.accepted, result.reasons
    assert result.points["court_corners"][3][0] < -100
    assert corner_errors(result.points, aside).max() <= 6.0


def test_plain_sand_is_refused(cam):
    result = ac.detect(draw_court(cam, tape=False))
    assert result.points is None and not result.accepted
    assert result.reasons


def test_the_calibration_file_is_read_by_every_consumer(full, tmp_path):
    doc = ac.calibration_document(full)
    assert doc["source"] == "auto" and doc["auto"]["accepted_by"] == "checks"
    assert doc["auto"]["version"] == ac.VERSION
    path = tmp_path / "20261011_1000_court_x.json"
    path.write_text(json.dumps(doc))
    calibration = CourtCalibration(str(path))
    assert calibration.is_calibrated
    assert calibration.court_corners.tolist() == doc["court_corners"]
    geometry = CourtGeometry.from_file(str(path))
    assert abs(geometry.net_top_height_m() - NET_H) <= 0.12


def test_no_document_without_a_court(cam):
    with pytest.raises(ValueError):
        ac.calibration_document(ac.detect(draw_court(cam, tape=False)))


# -- the camera's focal length from earlier calibrations --------------------- #

def _write(path: Path, cam_: Camera, dims: Optional[List[int]] = None) -> None:
    pts = truth(cam_)
    path.write_text(json.dumps({
        "court_corners": pts[:4].round().astype(int).tolist(),
        "midcourt_points": pts[4:6].round().astype(int).tolist(),
        "net_top_points": pts[6:].round().astype(int).tolist(),
        "frame_dimensions": dims or [H, W]}))


def test_focal_priors_need_three_views_that_agree(tmp_path):
    for i, (focal, behind) in enumerate([(1900, 8.0), (1880, 7.6), (1925, 8.4)]):
        _write(tmp_path / f"day_{i}.json", Camera(focal=focal, behind=behind))
    _write(tmp_path / "night.json", Camera(focal=2150))          # another lens setting, once
    priors = ac.focal_priors(tmp_path, W, H)
    assert len(priors) == 1 and abs(priors[0] - 1900) <= 30
    # a video never reads its own file, and two views are not enough
    assert ac.focal_priors(tmp_path, W, H, exclude_stem="day_0") == []


def test_a_venues_settings_do_not_swallow_a_neighbours(tmp_path):
    """Grouping from the smallest focal let two views of a second venue take
    the first venue's lowest view and leave it short of three."""
    for i, focal in enumerate([1838, 1888, 1893]):
        _write(tmp_path / f"vall_{i}.json", Camera(focal=focal))
    for i, focal in enumerate([1776, 1790]):
        _write(tmp_path / f"beach_{i}.json", Camera(focal=focal))
    priors = ac.focal_priors(tmp_path, W, H)
    assert len(priors) == 1 and abs(priors[0] - 1888) <= 15


def test_focal_priors_ignore_copies_and_other_frame_sizes(tmp_path):
    for name in ("clip_1", "clip_2", "clip_3"):                 # one recording, cut in three
        _write(tmp_path / f"{name}.json", Camera())
    _write(tmp_path / "portrait.json", Camera(focal=1900, behind=7.7), dims=[2978, 1564])
    (tmp_path / "broken.json").write_text("{not json")
    assert ac.focal_priors(tmp_path, W, H) == []


# -- pieces ------------------------------------------------------------------ #

def test_a_bowed_tape_is_followed_not_cut_straight():
    """A tape that strays 12 px from its straight line over its length."""
    base = ac.Line(np.array([100.0, 500.0]), np.array([1.0, 0.0]))
    xs = np.arange(100, 1100, 1.0)
    bow = 12.0 * np.sin((xs - 100) / 1000.0 * math.pi)
    pts = np.stack([xs, 500.0 + bow], axis=1)
    nodes = np.arange(0.0, 1000.0, 20.0)
    curve = ac.fit_curve(base, pts, nodes, start=0)
    for t in (100.0, 500.0, 900.0):
        want = 500.0 + 12.0 * math.sin(t / 1000.0 * math.pi)
        assert abs(curve.point(t)[1] - want) <= 1.5


def test_sideline_ends_bridge_a_buried_stretch_and_stop_at_quiet_sand():
    step = ac.Sideline.q_step()
    on = np.zeros(400, dtype=bool)
    on[0:60] = True
    on[64:150] = True                                # 0.4 m buried: bridged
    on[177:179] = True                               # a speck 2.7 m on: not tape
    side = ac.Sideline(ac.Curve(ac.Line(np.zeros(2), np.array([1.0, 0.0]))), 0.0, 1000.0,
                       on=on, valid=np.ones(400, dtype=bool))
    assert side.ends() == pytest.approx([150 * step])


def test_the_sheet_shows_all_eight_points_even_outside_the_frame(full):
    plate = np.zeros((H, W, 3), np.uint8)
    points = json.loads(json.dumps(full.points))
    points["court_corners"][3] = [-150, 1100]
    sheet = ac.contact_sheet(plate, points, full.points)
    assert sheet.shape == (2 * 560, 4 * 560, 3)


def test_compare_reports_what_the_post_run_layer_reads(full):
    moved = json.loads(json.dumps(full.points))
    for i in (0, 1):
        moved["court_corners"][i][1] += 6
    moved["court_corners"][1][0] += 10
    diff = ac.compare(moved, full.points)
    assert diff["far_row_px"] == 6.0 and diff["near_row_px"] == 0.0
    width = full.points["court_corners"][1][0] - full.points["court_corners"][0][0]
    assert diff["far_width_frac"] == pytest.approx(10 / width, abs=1e-4)
