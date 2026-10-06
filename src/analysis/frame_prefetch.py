"""Decode and detector inference a few frames ahead of the frame loop.

The per-frame pipeline is strictly sequential (the trackers are online
filters), but two of its inputs depend on the frame alone: the decoded image
and each detector's YOLO boxes (``BallDetector.infer`` /
``PlayerDetector.infer``). ``FramePrefetcher`` computes those on background
threads, in decode order, at most ``depth`` frames ahead, and hands them to
``FrameProcessor.process_frame(frame, i, inference=...)``.

Only WHEN they are computed changes, never what: the same functions run on the
same frames, so the output is identical to the inline loop (``depth=0``).
Decoding stays one sequential ``cap.read()`` stream (no seeks, AGENTS.md §9).
Measured 2026-10-06 (M3 Pro / MPS, together with the detector fast path):
the 20260920 match 75 -> 32 ms/frame, every artifact byte-identical. The
sequential consumer (MediaPipe pose) is the bound after that.
"""

import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterator, NamedTuple, Optional, Tuple

import numpy as np

_END = object()


class FrameInference(NamedTuple):
    """Read-ahead detector output for one frame (``infer()`` results, or the
    exception one raised) and the worker seconds they cost."""

    ball: Any
    player: Any
    seconds: float


def _timed_infer(infer: Callable, frame: np.ndarray) -> Tuple[Any, float]:
    """One ``infer(frame)``. A failure is returned instead of raised so it
    surfaces inside the detector's own ``detect()`` error handling."""
    start = time.perf_counter()
    try:
        result = infer(frame)
    except Exception as exc:  # re-raised by BaseDetector._resolved
        result = exc
    return result, time.perf_counter() - start


class FramePrefetcher:
    """Iterate ``(frame, inference)`` over a ``cv2.VideoCapture`` in order.

    ``depth > 0``: one thread decodes and one worker per detector runs
    ``infer`` ahead of the consumer, bounded to ``depth`` queued frames.
    ``depth == 0``: plain inline ``cap.read()``; ``inference`` is None and
    ``process_frame`` runs the detectors itself.

    Use as a context manager, and release the capture only after it exits.
    """

    def __init__(self, cap, frame_processor, depth: int = 8):
        self._cap = cap
        self._depth = max(0, int(depth))
        self._infer = (frame_processor.ball_detector.infer,
                       frame_processor.player_detector.infer)
        self._queue: "queue.Queue" = queue.Queue(maxsize=max(1, self._depth))
        self._stop = threading.Event()
        self._reader: Optional[threading.Thread] = None
        self._workers: Tuple[ThreadPoolExecutor, ...] = ()

    def __enter__(self) -> "FramePrefetcher":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def __iter__(self) -> Iterator[Tuple[np.ndarray, Optional[FrameInference]]]:
        if self._depth == 0:
            while True:
                ret, frame = self._cap.read()
                if not ret:
                    return
                yield frame, None
        self._start()
        while True:
            item = self._queue.get()
            if item is _END:
                return
            if isinstance(item, BaseException):
                raise item
            frame, ball, player = item
            (ball_boxes, ball_s), (player_boxes, player_s) = ball.result(), player.result()
            yield frame, FrameInference(ball_boxes, player_boxes, ball_s + player_s)

    def close(self) -> None:
        """Stop reading ahead and reap the threads (idempotent)."""
        self._stop.set()
        if self._reader is not None:
            self._reader.join()
            self._reader = None
        for worker in self._workers:
            worker.shutdown(wait=True, cancel_futures=True)
        self._workers = ()

    # -- background side -------------------------------------------------------

    def _start(self) -> None:
        # One thread per detector: each model is driven by a single thread, and
        # every frame's boxes come back in submission (= decode) order.
        self._workers = tuple(
            ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"prefetch-{name}")
            for name in ("ball", "player")
        )
        self._reader = threading.Thread(
            target=self._read_ahead, name="prefetch-reader", daemon=True)
        self._reader.start()

    def _read_ahead(self) -> None:
        try:
            while not self._stop.is_set():
                ret, frame = self._cap.read()
                if not ret:
                    break
                futures = [worker.submit(_timed_infer, infer, frame)
                           for worker, infer in zip(self._workers, self._infer)]
                if not self._put((frame, *futures)):
                    return
            self._put(_END)
        except BaseException as exc:  # surfaces in the consumer's loop
            self._put(exc)

    def _put(self, item) -> bool:
        """Blocking put that gives up once the consumer has closed us."""
        while not self._stop.is_set():
            try:
                self._queue.put(item, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False
