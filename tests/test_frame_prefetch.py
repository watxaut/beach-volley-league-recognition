"""Read-ahead must change WHEN detector inference runs, never what the frame
loop sees (src/analysis/frame_prefetch.py).

What is being protected:
- ORDER: frames come out in decode order, each paired with ITS inference, and
  every frame is inferred exactly once per detector.
- ``depth=0`` is the plain inline loop (no threads, no inference handed over).
- EQUIVALENCE: ``detect(frame, inference=infer(frame))`` is ``detect(frame)``,
  including the ball detector's rolling static-suppression state.
- FAILURES keep their place: an ``infer`` error surfaces inside that frame's
  ``detect()`` (same log + empty result as inline); a decode error surfaces in
  the consumer's loop.
- BOUNDED and REAPED: at most ``depth`` frames are queued ahead, and leaving
  the loop early stops the reader and workers.
"""

import logging
import threading
import time
from collections import deque
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from src.analysis.frame_prefetch import FramePrefetcher
from src.detection.ball_detector import BallDetector
from src.detection.player_detector import PlayerDetector


def _frame(i):
    return np.full((4, 4, 3), i, dtype=np.uint8)


class _Cap:
    """cv2.VideoCapture stand-in: ``n`` frames whose pixels carry their index."""

    def __init__(self, n, fail_at=None):
        self.n, self.fail_at, self.reads = n, fail_at, 0

    def read(self):
        if self.reads == self.fail_at:
            raise RuntimeError("decode broke")
        if self.reads >= self.n:
            return False, None
        self.reads += 1
        return True, _frame(self.reads - 1)


class _Detector:
    def __init__(self, name, fail_on=()):
        self.name, self.fail_on = name, fail_on
        self.seen, self.threads = [], set()

    def infer(self, frame):
        index = int(frame[0, 0, 0])
        self.seen.append(index)
        self.threads.add(threading.current_thread().name)
        if index in self.fail_on:
            raise ValueError(f"{self.name} failed on {index}")
        return (self.name, index)


def _processor(**kwargs):
    return SimpleNamespace(ball_detector=_Detector("ball", **kwargs),
                           player_detector=_Detector("player"))


def test_frames_come_out_in_order_with_their_own_inference():
    processor, cap = _processor(), _Cap(40)
    with FramePrefetcher(cap, processor, depth=4) as frames:
        out = list(frames)
    assert [int(f[0, 0, 0]) for f, _ in out] == list(range(40))
    assert [inf.ball for _, inf in out] == [("ball", i) for i in range(40)]
    assert [inf.player for _, inf in out] == [("player", i) for i in range(40)]
    assert all(inf.seconds >= 0 for _, inf in out)
    # One dedicated thread per detector, never the consumer's.
    for det in (processor.ball_detector, processor.player_detector):
        assert det.seen == list(range(40))
        assert len(det.threads) == 1
        assert threading.current_thread().name not in det.threads


def test_depth_zero_is_the_inline_loop():
    processor, cap = _processor(), _Cap(5)
    before = threading.active_count()
    with FramePrefetcher(cap, processor, depth=0) as frames:
        out = list(frames)
        assert threading.active_count() == before
    assert [int(f[0, 0, 0]) for f, _ in out] == list(range(5))
    assert all(inf is None for _, inf in out)
    assert processor.ball_detector.seen == []


def test_an_infer_failure_stays_with_its_frame():
    processor = _processor(fail_on=(2,))
    with FramePrefetcher(_Cap(5), processor, depth=3) as frames:
        out = list(frames)
    assert len(out) == 5
    assert isinstance(out[2][1].ball, ValueError)
    assert out[2][1].player == ("player", 2)
    assert out[3][1].ball == ("ball", 3)
    with pytest.raises(ValueError, match="ball failed on 2"):
        BallDetector._resolved(out[2][1].ball)


def test_a_decode_failure_reaches_the_consumer():
    with FramePrefetcher(_Cap(10, fail_at=3), _processor(), depth=2) as frames:
        seen = []
        with pytest.raises(RuntimeError, match="decode broke"):
            for frame, _ in frames:
                seen.append(int(frame[0, 0, 0]))
    assert seen == [0, 1, 2]


def test_read_ahead_is_bounded_and_reaped_on_early_exit():
    processor, cap = _processor(), _Cap(1000)
    before = threading.active_count()
    with FramePrefetcher(cap, processor, depth=4) as frames:
        for i, _ in enumerate(frames):
            time.sleep(0.02)  # a slow consumer: the reader must wait, not run away
            if i == 2:
                break
        # 3 consumed + `depth` queued + one held by the reader + one in hand.
        assert cap.reads <= 3 + 4 + 2
    assert threading.active_count() == before
    reads = cap.reads
    time.sleep(0.05)
    assert cap.reads == reads


# --------------------------------------------------------------------------- #
# detect(frame, inference=infer(frame)) == detect(frame)
# --------------------------------------------------------------------------- #

class _BoxesByFrame:
    """Fake ultralytics model: the boxes depend on the frame's index only."""

    def __init__(self, boxes_for):
        self.boxes_for = boxes_for

    def __call__(self, frame, **kwargs):
        data = torch.tensor(self.boxes_for(int(frame[0, 0, 0])), dtype=torch.float32).reshape(-1, 6)
        return [SimpleNamespace(boxes=SimpleNamespace(data=data))]


def _ball_detector():
    det = BallDetector.__new__(BallDetector)
    det.logger = logging.getLogger("test_frame_prefetch")
    det.confidence_threshold, det.max_ball_size = 0.15, 80
    det._is_custom_model, det._imgsz, det._auto_imgsz = True, 640, None
    det.suppress_static, det.static_radius, det.static_min_frames = True, 25.0, 8
    det.static_persist_frac, det.static_suspect_frac = 0.55, 0.30
    det._recent_centers = deque(maxlen=40)
    det.diag_enabled, det._diag_dets, det.raw_detections = False, [], []
    det._inference, det.fast_inference = None, True
    # A parked ball every frame (suppressed after warmup), a moving ball, and
    # one oversized / one under-confident box that the filters drop.
    det._model = _BoxesByFrame(lambda i: [
        [400.4, 300.6, 430.2, 331.9, 0.91, 0],
        [100.5 + 9 * i, 200.5 + 4 * i, 128.5 + 9 * i, 229.5 + 4 * i, 0.62, 0],
        [10, 10, 200, 60, 0.80, 0],
        [700, 700, 720, 720, 0.05, 0],
    ])
    return det


def _player_detector():
    det = PlayerDetector.__new__(PlayerDetector)
    det.logger = logging.getLogger("test_frame_prefetch")
    det.confidence_threshold, det.max_players, det.imgsz = 0.5, 20, 1280
    det._person_class_ids, det.court_detector, det.off_area_detections = {0}, None, []
    det._inference, det.fast_inference = None, True
    det._model = _BoxesByFrame(lambda i: [
        [100.25 + i, 100.5, 180.75 + i, 380.125, 0.93, 0],     # a player
        [300.0, 200.0, 340.0, 300.0, 0.41, 0],                 # under-confident
        [500.0, 500.0, 560.0, 640.0, 0.88, 32],                # not a person
        [900.5, 120.5, 960.5, 330.5, 0.77, 0],                 # a second player
    ])
    return det


@pytest.mark.parametrize("make", [_ball_detector, _player_detector], ids=["ball", "player"])
def test_detect_with_read_ahead_inference_equals_detect(make):
    inline, ahead = make(), make()
    frames = [np.full((1080, 1920, 3), i, dtype=np.uint8) for i in range(30)]
    inferred = [ahead.infer(f) for f in frames]       # all computed before any detect()
    for frame, boxes in zip(frames, inferred):
        assert ahead.detect(frame, inference=boxes) == inline.detect(frame)
        if make is _ball_detector:
            assert ahead.raw_detections == inline.raw_detections
    if make is _ball_detector:
        # The parked ball was suppressed in both: the state really evolved.
        assert len(inline.detect(frames[-1])) == 1


@pytest.mark.parametrize("make", [_ball_detector, _player_detector], ids=["ball", "player"])
def test_a_read_ahead_failure_is_handled_like_an_inline_one(make, caplog):
    det = make()
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    with caplog.at_level(logging.ERROR):
        assert det.detect(frame, inference=RuntimeError("model blew up")) == []
    assert "model blew up" in caplog.text
