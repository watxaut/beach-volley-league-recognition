"""The detector fast path must return exactly what the public ultralytics call
returns (src/detection/yolo_inference.py).

What is being protected:
- EQUIVALENCE: ``YoloInference`` (predictor stage methods, CPU post-processing
  on MPS) is bit-identical to ``model(frame, ...)`` on real frames, for both
  detectors, on whatever device this machine resolves to. This is the test to
  re-run before adding a release to ``VERIFIED_ULTRALYTICS``.
- THE CERTIFICATE: CPU post-processing is only trusted when no NMS decision
  sits near a rounding boundary (IoU close to the threshold, tied scores, tied
  class maximum). "Not proven" must send the frame back to the device.
- THE HANDOVER: an unverified ultralytics release, or predict arguments that
  changed behind the runner's back, fall back to the public call.
"""

from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
import torch

from src.detection import yolo_inference as yi
from src.detection.base_detector import resolve_device

ROOT = Path(__file__).resolve().parent.parent
BALL_WEIGHTS = ROOT / "models" / "volleyball_ball_best.pt"
PLAYER_WEIGHTS = ROOT / "yolov8n.pt"
CLIP = ROOT / "resources" / "video_entreno_3.mp4"
# The kwargs BallDetector.infer / PlayerDetector.infer pass on 1080p footage.
BALL_KWARGS = dict(classes=None, conf=0.15, imgsz=1280)
PLAYER_KWARGS = dict(imgsz=1280)

needs_weights = pytest.mark.skipif(
    not (BALL_WEIGHTS.exists() and PLAYER_WEIGHTS.exists()),
    reason="detector weights not on disk",
)


# --------------------------------------------------------------------------- #
# The certificate
# --------------------------------------------------------------------------- #

def _head(boxes, scores):
    """Raw head output (1, 4 + classes, anchors) from cx,cy,w,h rows and
    per-anchor class-score rows."""
    rows = [list(b) + list(s) for b, s in zip(boxes, scores)]
    return torch.tensor(rows, dtype=torch.float32).T[None].contiguous()


def _stable(head, conf=0.25, iou=0.7):
    return yi.selection_is_implementation_independent(head, conf, iou)


SQUARE = (50.0, 50.0, 100.0, 100.0)
# Shifted so IoU with SQUARE = (100 - d) / (100 + d) is 0.7 to within 1e-6.
BORDERLINE = (50.0 + 300.0 / 17.0, 50.0, 100.0, 100.0)


def test_no_candidate_and_clear_decisions_are_stable():
    assert _stable(_head([SQUARE], [[0.1]]))                      # nothing above conf
    assert _stable(_head([SQUARE], [[0.9]]))                      # a single box
    near_duplicate = (52.0, 50.0, 100.0, 100.0)                   # IoU 0.96: clearly suppressed
    far_away = (600.0, 400.0, 80.0, 160.0)                        # IoU 0: clearly kept
    assert _stable(_head([SQUARE, near_duplicate, far_away], [[0.9], [0.8], [0.7]]))


def test_an_iou_on_the_threshold_is_not_trusted():
    assert not _stable(_head([SQUARE, BORDERLINE], [[0.9], [0.8]]))
    # ...but only for boxes that are compared: other classes never meet in NMS
    # (the per-class offset), and sub-threshold anchors are not candidates.
    assert _stable(_head([SQUARE, BORDERLINE], [[0.9, 0.0], [0.0, 0.8]]))
    assert _stable(_head([SQUARE, BORDERLINE], [[0.9], [0.2]]))


def test_ties_are_not_trusted():
    far_away = (600.0, 400.0, 80.0, 160.0)
    assert not _stable(_head([SQUARE, far_away], [[0.8], [0.8]]))   # output order
    assert not _stable(_head([SQUARE], [[0.8, 0.8]]))               # class argmax
    assert _stable(_head([SQUARE, far_away], [[0.8, 0.3], [0.7, 0.3]]))


def test_too_many_candidates_are_left_to_the_device(monkeypatch):
    monkeypatch.setattr(yi, "MAX_CHECKED_CANDIDATES", 2)
    boxes = [(100.0 + 200.0 * i, 100.0, 50.0, 50.0) for i in range(3)]
    assert not _stable(_head(boxes, [[0.9], [0.8], [0.7]]))


def test_cpu_arithmetic_matches_itself():
    assert yi.device_arithmetic_matches_cpu(torch.device("cpu"), (736, 1280), (1080, 1920, 3))


# --------------------------------------------------------------------------- #
# Routing without a real model
# --------------------------------------------------------------------------- #

def test_a_model_without_a_predictor_always_takes_the_public_call():
    data = torch.tensor([[1.0, 2.0, 3.0, 4.0, 0.9, 0.0]])
    calls = []

    def fake_model(frame, **kwargs):
        calls.append(kwargs)
        return [SimpleNamespace(boxes=SimpleNamespace(data=data)), SimpleNamespace(boxes=None)]

    run = yi.YoloInference(fake_model)
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    for _ in range(3):
        np.testing.assert_array_equal(run(frame, imgsz=640), data.numpy())
    assert run.stats == {"cpu_post": 0, "device_post": 0, "public": 3}
    assert calls == [{"verbose": False, "imgsz": 640}] * 3
    assert yi.boxes_array([SimpleNamespace(boxes=None)]).shape == (0, 6)


# --------------------------------------------------------------------------- #
# Equivalence on the real detectors
# --------------------------------------------------------------------------- #

def _frames(n=10):
    """Real footage when the clip is on disk (sequential decode, AGENTS.md §9),
    plus one synthetic frame so the test never depends on the clip alone."""
    frames = [np.random.RandomState(7).randint(0, 255, (1080, 1920, 3), dtype=np.uint8)]
    if CLIP.exists():
        cap = cv2.VideoCapture(str(CLIP))
        for i in range(8 * n):
            ok, frame = cap.read()
            if not ok:
                break
            if i % 8 == 0:
                frames.append(frame)
        cap.release()
    return frames


def _load(weights):
    from ultralytics import YOLO

    model = YOLO(str(weights))
    device = resolve_device("auto")
    if device != "cpu":
        model.to(device)
    return model


@pytest.fixture(scope="module")
def frames():
    return _frames()


@needs_weights
@pytest.mark.parametrize("weights,kwargs", [(BALL_WEIGHTS, BALL_KWARGS),
                                            (PLAYER_WEIGHTS, PLAYER_KWARGS)],
                         ids=["ball", "player"])
def test_fast_path_is_bit_identical_to_the_public_call(weights, kwargs, frames, monkeypatch):
    public = yi.YoloInference(_load(weights), fast=False)
    reference = [public(f, **kwargs) for f in frames]
    assert public.stats["public"] == len(frames)

    fast = yi.YoloInference(_load(weights))
    for frame, expected in zip(frames, reference):
        np.testing.assert_array_equal(fast(frame, **kwargs), expected)
    if yi.ultralytics.__version__ in yi.VERIFIED_ULTRALYTICS:
        # Only the first frame (which configures the predictor) is a public call.
        assert fast.stats["public"] == 1
        assert fast.stats["cpu_post"] + fast.stats["device_post"] == len(frames) - 1

    # A refused certificate post-processes on the device: still the same boxes.
    monkeypatch.setattr(yi, "selection_is_implementation_independent", lambda *a: False)
    refused = yi.YoloInference(_load(weights))
    for frame, expected in zip(frames, reference):
        np.testing.assert_array_equal(refused(frame, **kwargs), expected)
    assert refused.stats["cpu_post"] == 0


@needs_weights
def test_changed_arguments_and_unverified_releases_fall_back(frames, monkeypatch):
    if yi.ultralytics.__version__ not in yi.VERIFIED_ULTRALYTICS:
        pytest.skip("fast path is off on this ultralytics release")
    model = _load(PLAYER_WEIGHTS)
    run = yi.YoloInference(model)
    frame = frames[-1]
    run(frame, imgsz=1280)
    run(frame, imgsz=1280)
    assert run.stats["public"] == 1

    # Different kwargs: public call again, then the stages follow the new ones.
    public = yi.YoloInference(_load(PLAYER_WEIGHTS), fast=False)
    np.testing.assert_array_equal(run(frame, imgsz=640), public(frame, imgsz=640))
    assert run.stats["public"] == 2
    run(frame, imgsz=640)
    assert run.stats["public"] == 2

    # Someone else reconfigures the predictor (scripts call ``_model`` directly):
    # the stale configuration must not be reused.
    model(frame, verbose=False, imgsz=640, conf=0.6)
    np.testing.assert_array_equal(run(frame, imgsz=640), public(frame, imgsz=640))
    assert run.stats["public"] == 3

    # An ultralytics release nobody verified: public call only, for good.
    monkeypatch.setattr(yi, "VERIFIED_ULTRALYTICS", ())
    unverified = yi.YoloInference(_load(PLAYER_WEIGHTS))
    for _ in range(3):
        unverified(frame, imgsz=1280)
    assert unverified.stats == {"cpu_post": 0, "device_post": 0, "public": 3}
    assert unverified.fast is False
