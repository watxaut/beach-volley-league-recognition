"""Tests for the --debug-live producer/consumer decoupling (open point 23).

The producer thread must run the EXACT shared processing sequence in frame
order (cap.read -> process_frame -> ingest -> spike log -> cache overlay data
-> court overlay), flush + typed spikes on natural end only, and always emit
the done sentinel/event. The consumer must drain in order and terminate --
including the regression where the sentinel parked behind the depth gate
never opened (fixed with the done-event set strictly after the sentinel is
queued).

Everything runs GUI-less: cv2's imshow/waitKey/destroyAllWindows and
VideoWriter are patched, and ``_open`` is stubbed, so no window or video file
is needed. The pipeline itself is NOT touched by the decoupling (parity
rule); these tests pin the thread plumbing around it.
"""

import logging
import queue
import threading
import time

import numpy as np
import pytest

import src.analysis.live_debug_processor as lldp
from src.output_gen import overlay


N_FRAMES = 120  # > LIVE_DELAY cap at 30 fps (90): exercises the drain path


def _frame(i):
    return np.full((48, 64, 3), i % 251, dtype=np.uint8)


class StubSpikeAnalyzer:
    def __init__(self):
        self.records = []

    def spike_records(self):
        return self.records

    def spike_type_for(self, frame):
        return None

    def spike_zone_for(self, frame):
        return None

    def trail_points(self, frame_idx):
        return []

    def kill_annotation(self, frame_idx):
        return None


class StubBallDetector:
    """The detector side channel the 'b' overlay reads (raw_detections)."""

    def __init__(self):
        # One dict that survives static suppression and one that it removed --
        # the same objects, distinguished by identity exactly as production is.
        self.play = {"bbox": [16, 16, 24, 24], "center": [20.0, 20.0],
                     "confidence": 0.81}
        self.spare = {"bbox": [40, 30, 46, 36], "center": [43.0, 33.0],
                      "confidence": 0.62, "stationary_suspect": True}
        self.removed = {"bbox": [8, 40, 14, 46], "center": [11.0, 43.0],
                        "confidence": 0.93}
        self.raw_detections = [self.play, self.spare, self.removed]


class StubFrameProcessor:
    def __init__(self):
        self.spike_analyzer = StubSpikeAnalyzer()
        self.ball_detector = StubBallDetector()
        self.process_calls = []
        self.flush_calls = 0
        self.reset_calls = 0
        self.setup_fps_calls = []
        self.setup_dim_calls = []
        # No action_classifier / diag: the panel's guarded reads must degrade
        # to "-" instead of raising on a component that lacks them.

    def process_frame(self, frame, idx, enable_court_redetection=True):
        self.process_calls.append(idx)
        actions = []
        if idx % 10 == 0:
            actions.append({"track_id": 1, "frame_number": idx,
                            "action": "bump", "confidence": 0.9})
        bd = self.ball_detector
        return {"actions": actions, "tracked_ball": None,
                "tracked_players": [], "game_state": None,
                # static suppression keeps the play ball + the suspect, drops
                # the third (same dict objects as raw_detections).
                "ball_detections": [bd.play, bd.spare]}

    def flush_actions(self):
        self.flush_calls += 1
        return []

    def reset_trackers(self):
        self.reset_calls += 1

    def setup_video_fps(self, fps):
        self.setup_fps_calls.append(fps)

    def setup_video_dimensions(self, w, h):
        self.setup_dim_calls.append((w, h))

    def enroll_from_video(self, video_path):
        self.enroll_calls = getattr(self, "enroll_calls", []) + [video_path]
        return None


class StubCourtDetector:
    def __init__(self):
        self.calls = []

    def draw_court_overlay(self, frame):
        self.calls.append(1)
        return frame


class StubCap:
    def __init__(self, n, slow=0.0):
        self.n = n
        self.i = 0
        self.slow = slow          # per-read pause; lets a test outrun the producer
        self.set_calls = []
        self.released = False

    def read(self):
        if self.slow:
            time.sleep(self.slow)
        if self.i < self.n:
            self.i += 1
            return True, _frame(self.i - 1)
        return False, None

    def set(self, attr, value):
        self.set_calls.append((attr, value))
        if attr == lldp.cv2.CAP_PROP_POS_FRAMES:
            self.i = value  # a real capture rewinds here

    def release(self):
        self.released = True


class RecordingWriter:
    instances = []

    def __init__(self, *a, **k):
        self.frames = []
        self.released = False
        RecordingWriter.instances.append(self)

    def write(self, frame):
        self.frames.append(frame)

    def release(self):
        self.released = True


def make_processor(n=N_FRAMES, panel=False, candidates=False, slow=0.0):
    """A LiveDebugProcessor skeleton without the heavy __init__ (parity: the
    real __init__ only wires FrameProcessor/court detector, which the stubs
    replace)."""
    proc = object.__new__(lldp.LiveDebugProcessor)
    proc.config = {}
    proc.debug_speed = 1.0
    proc.logger = logging.getLogger("test_live_debug_decoupling")
    proc.frame_processor = StubFrameProcessor()
    proc.court_detector = StubCourtDetector()
    proc._spike_log_state = []
    # Signal panel state the live path owns (tests exercise it separately).
    proc._panel_enabled = panel
    proc._candidates_enabled = candidates
    proc._event_plan = lldp.debug_panel.EventPlan()
    proc._probe_mirror = False
    proc._last_ball = None
    proc._last_ball_pt = None
    cap = StubCap(n, slow=slow)
    return proc, cap


@pytest.fixture()
def guiless(monkeypatch):
    """Patch out cv2 GUI + VideoWriter for the whole test."""
    monkeypatch.setattr(lldp.cv2, "imshow", lambda *a, **k: None)
    monkeypatch.setattr(lldp.cv2, "waitKey", lambda *a, **k: -1)
    monkeypatch.setattr(lldp.cv2, "destroyAllWindows", lambda *a, **k: None)
    monkeypatch.setattr(lldp.cv2, "namedWindow", lambda *a, **k: None)
    monkeypatch.setattr(lldp.cv2, "resizeWindow", lambda *a, **k: None)
    RecordingWriter.instances = []
    monkeypatch.setattr(lldp.cv2, "VideoWriter", RecordingWriter)
    return None


def patch_open(monkeypatch, cap, fps=30.0, w=64, h=48):
    monkeypatch.setattr(
        lldp.LiveDebugProcessor, "_open",
        lambda self, path: (cap, fps, w, h, cap.n))


# --------------------------------------------------------------------- #
# Producer: exact sequence, flush-on-natural-end, sentinel
# --------------------------------------------------------------------- #

class TestProducer:
    def test_frames_in_order_flush_once_sentinel_last(self):
        proc, cap = make_processor()
        fp = proc.frame_processor
        q = queue.Queue()
        stop, paused, done = threading.Event(), threading.Event(), threading.Event()
        plan = overlay.LabelPlan()
        proc._produce_frames(cap, q, stop, paused, plan, done)
        items = []
        while True:
            item = q.get(timeout=5)
            if item is lldp._PRODUCER_DONE:
                break
            items.append(item)
        assert [it[1] for it in items] == list(range(cap.n))  # frame order
        assert all(it[0] is not None for it in items)         # frames carried
        assert fp.process_calls == list(range(cap.n))         # exact sequence
        assert fp.flush_calls == 1                            # natural end only
        assert done.is_set()

    def test_stop_without_flush_discards_tail(self):
        # slow: the producer must not reach the (naturally ending) source before
        # stop.set() lands -- at full stub speed the 50 frames finish in
        # microseconds and the natural-end flush wins the race (flaky ~1/10).
        proc, cap = make_processor(n=50, slow=0.002)
        fp = proc.frame_processor
        q = queue.Queue()
        stop, paused, done = threading.Event(), threading.Event(), threading.Event()
        plan = overlay.LabelPlan()
        t = threading.Thread(target=proc._produce_frames,
                             args=(cap, q, stop, paused, plan, done))
        t.start()
        stop.set()
        t.join(timeout=5)
        assert not t.is_alive()
        assert done.is_set()
        assert fp.flush_calls == 0  # stop path: no flush, like the old loop

    def test_paused_producer_parks_then_resumes(self):
        proc, cap = make_processor()
        q = queue.Queue()
        stop, paused, done = threading.Event(), threading.Event(), threading.Event()
        paused.set()
        plan = overlay.LabelPlan()
        t = threading.Thread(target=proc._produce_frames,
                             args=(cap, q, stop, paused, plan, done))
        t.start()
        time.sleep(0.15)
        assert q.qsize() == 0 and cap.i == 0  # nothing processed while paused
        assert proc.frame_processor.process_calls == []
        paused.clear()
        t.join(timeout=10)
        assert not t.is_alive()
        assert proc.frame_processor.process_calls == list(range(cap.n))

    def test_stop_producer_unblocks_full_queue(self):
        proc, cap = make_processor()
        q = queue.Queue(maxsize=2)
        q.put(("full", 1)), q.put(("full", 2))
        stop, paused, done = threading.Event(), threading.Event(), threading.Event()
        plan = overlay.LabelPlan()
        t = threading.Thread(target=proc._produce_frames,
                             args=(cap, q, stop, paused, plan, done))
        t.start()
        time.sleep(0.05)  # let it block on the first put
        t0 = time.perf_counter()
        lldp.LiveDebugProcessor._stop_producer(t, q, stop)
        assert time.perf_counter() - t0 < 4.0  # well under the join timeout
        assert not t.is_alive()

    def test_candidates_snapshotted_only_when_enabled(self):
        """The 'b' overlay's data is cached on the producer thread (like every
        other signal) and is EMPTY while the toggle is off, so the default live
        run costs nothing extra."""
        proc, cap = make_processor(n=3)
        q = queue.Queue()
        stop, paused, done = threading.Event(), threading.Event(), threading.Event()
        plan = overlay.LabelPlan()
        proc._produce_frames(cap, q, stop, paused, plan, done)
        while q.get(timeout=5) is not lldp._PRODUCER_DONE:
            pass
        assert proc._ball_candidates({"ball_detections": []})  # data available

        proc2, cap2 = make_processor(n=3, candidates=True)
        q2 = queue.Queue()
        proc2._produce_frames(cap2, q2, stop, paused, plan, done)
        cands = None
        while True:
            item = q2.get(timeout=5)
            if item is lldp._PRODUCER_DONE:
                break
            cands = item[5]["candidates"]
        assert [(c["conf"], c["flag"]) for c in cands] == [
            (0.81, ""), (0.62, "sus"), (0.93, "rm")]

    def test_typed_spikes_ingested_on_flush(self):
        proc, cap = make_processor(n=5)
        rec = {"spike_type": "hard", "track_id": 3, "frame": 2}
        proc.frame_processor.spike_analyzer.records = [rec]
        q = queue.Queue()
        stop, paused, done = threading.Event(), threading.Event(), threading.Event()
        plan = overlay.LabelPlan()
        proc._produce_frames(cap, q, stop, paused, plan, done)
        # The typed label landed on the contact frame via plan.add.
        assert plan.active(3, 2) == ("spike hard", None)


# --------------------------------------------------------------------- #
# Consumer loop: completion, quit, restart (GUI-less)
# --------------------------------------------------------------------- #

class TestConsumerLoop:
    def test_run_to_completion_in_order(self, guiless, monkeypatch):
        proc, cap = make_processor()
        patch_open(monkeypatch, cap)
        shown_idx = []
        monkeypatch.setattr(lldp.LiveDebugProcessor, "_draw_overlay",
                            lambda self, f, i, *a, **k: shown_idx.append(i) or f)
        proc._process_buffered_live("fake.mp4", save_video="fake_out.mp4")
        assert RecordingWriter.instances, "writer created for save_video"
        writer = RecordingWriter.instances[-1]
        assert shown_idx == list(range(cap.n))  # every frame, in order
        assert len(writer.frames) == cap.n      # all written
        assert writer.released and cap.released
        assert proc.frame_processor.flush_calls == 1

    def test_sentinel_deadlock_regression_long_video(self, guiless, monkeypatch):
        """N > delay window: the consumer must drain the tail once the
        producer is done (the sentinel parks at the queue's back and the
        depth gate alone would never open -- regression for the done-event)."""
        proc, cap = make_processor(n=200)
        patch_open(monkeypatch, cap)
        shown = []
        monkeypatch.setattr(lldp.LiveDebugProcessor, "_draw_overlay",
                            lambda self, f, i, *a, **k: shown.append(i) or f)
        proc._process_buffered_live("fake.mp4")
        assert shown == list(range(200))

    def test_quit_key_stops_producer_and_ends(self, guiless, monkeypatch):
        proc, cap = make_processor()
        patch_open(monkeypatch, cap)
        monkeypatch.setattr(lldp.cv2, "waitKey", lambda *a, **k: ord('q'))
        proc._process_buffered_live("fake.mp4")
        assert cap.released
        assert RecordingWriter.instances == []  # save_video=None: no writer
        names = [t.name for t in threading.enumerate()]
        assert "live-debug-producer" not in names

    def test_restart_reruns_pipeline_and_resets(self, guiless, monkeypatch):
        proc, cap = make_processor()
        patch_open(monkeypatch, cap)
        state = {"shown": 0, "restarted": 0}
        shown = []

        def rec_draw(self, f, i, *a, **k):
            state["shown"] += 1
            shown.append(i)
            return f

        def key(*a, **k):
            # 'r' on the first post-show poll: after exactly one shown frame,
            # whatever the producer/consumer timing is.
            if state["shown"] >= 1 and state["restarted"] == 0:
                state["restarted"] = 1
                return ord('r')
            return -1

        monkeypatch.setattr(lldp.cv2, "waitKey", key)
        monkeypatch.setattr(lldp.LiveDebugProcessor, "_draw_overlay", rec_draw)
        proc._process_buffered_live("fake.mp4")
        fp = proc.frame_processor
        assert fp.reset_calls == 1
        assert cap.set_calls == [(lldp.cv2.CAP_PROP_POS_FRAMES, 0)]
        # Exactly one frame shown before the restart, then the complete
        # second pass in order (the pass-1 tail was discarded).
        assert shown == [0] + list(range(cap.n))

    def test_short_video_fully_drains(self, guiless, monkeypatch):
        """N < delay window: everything shows despite the gate never filling."""
        proc, cap = make_processor(n=20)
        patch_open(monkeypatch, cap)
        shown = []
        monkeypatch.setattr(lldp.LiveDebugProcessor, "_draw_overlay",
                            lambda self, f, i, *a, **k: shown.append(i) or f)
        proc._process_buffered_live("fake.mp4")
        assert shown == list(range(20))

    def test_panel_is_display_only(self, guiless, monkeypatch):
        """The side panel widens the window but never the saved video, and it
        does not touch the processing path (the producer call sequence is the
        same as with the panel off)."""
        proc, cap = make_processor(panel=True)
        patch_open(monkeypatch, cap)
        displayed = []
        monkeypatch.setattr(lldp.cv2, "imshow",
                            lambda _n, img: displayed.append(img.shape))
        monkeypatch.setattr(lldp.LiveDebugProcessor, "_draw_overlay",
                            lambda self, f, i, *a, **k: f)
        proc._process_buffered_live("fake.mp4", save_video="fake_out.mp4")
        writer = RecordingWriter.instances[-1]
        w, h = 64, 48
        assert all(f.shape == (h, w, 3) for f in writer.frames)      # unpanelled
        assert all(s == (h, w + lldp.debug_panel.PANEL_WIDTH, 3) for s in displayed)
        assert proc.frame_processor.process_calls == list(range(cap.n))

    def test_panel_toggle_key_p(self, guiless, monkeypatch):
        """'p' flips the panel; the run continues and the flag persists."""
        proc, cap = make_processor(panel=True)
        patch_open(monkeypatch, cap)
        shapes = []
        state = {"shown": 0}

        def show(_n, img):
            shapes.append(img.shape[1])
            state["shown"] += 1

        def key_once(*a, **k):
            if state["shown"] >= 2 and not state.get("sent"):
                state["sent"] = True
                return ord('p')
            return -1

        monkeypatch.setattr(lldp.cv2, "imshow", show)
        monkeypatch.setattr(lldp.cv2, "waitKey", key_once)
        monkeypatch.setattr(lldp.LiveDebugProcessor, "_draw_overlay",
                            lambda self, f, i, *a, **k: f)
        proc._process_buffered_live("fake.mp4")
        assert proc._panel_enabled is False
        assert 64 in shapes and 64 + lldp.debug_panel.PANEL_WIDTH in shapes

    def test_candidates_toggle_key_b(self, guiless, monkeypatch):
        """'b' flips the ball-candidate overlay; the saved video stays bare."""
        proc, cap = make_processor()
        patch_open(monkeypatch, cap)
        drawn = []
        state = {"shown": 0}

        def rec_draw(self, f, i, *a, **kw):
            cands = kw.get("candidates")
            drawn.append(cands)
            state["shown"] += 1
            return f

        def key(*a, **k):
            if state["shown"] >= 2 and not state.get("sent"):
                state["sent"] = True
                return ord('b')
            return -1

        monkeypatch.setattr(lldp.cv2, "waitKey", key)
        monkeypatch.setattr(lldp.LiveDebugProcessor, "_draw_overlay", rec_draw)
        proc._process_buffered_live("fake.mp4", save_video="fake_out.mp4")
        assert proc._candidates_enabled is True
        assert drawn[0] == [] and len(drawn[-1]) == 3   # off, then all three
        assert all(f.shape == (48, 64, 3) for f in RecordingWriter.instances[-1].frames)

    def test_candidates_toggle_survives_restart(self, guiless, monkeypatch):
        proc, cap = make_processor()
        patch_open(monkeypatch, cap)
        state = {"shown": 0}

        def key(*a, **k):
            state["shown"] += 1
            if state["shown"] == 1:
                return ord('b')
            if state["shown"] == 2:
                return ord('r')
            return -1

        monkeypatch.setattr(lldp.cv2, "waitKey", key)
        monkeypatch.setattr(lldp.LiveDebugProcessor, "_draw_overlay",
                            lambda self, f, i, *a, **k: f)
        proc._process_buffered_live("fake.mp4")
        assert proc._candidates_enabled is True
        assert proc.frame_processor.reset_calls == 1

    def test_panel_toggle_survives_restart(self, guiless, monkeypatch):
        proc, cap = make_processor(panel=False)
        patch_open(monkeypatch, cap)
        state = {"shown": 0, "restarted": 0}

        def key(*a, **k):
            state["shown"] += 1
            if state["shown"] == 1:
                return ord('p')
            if state["shown"] == 2:
                state["restarted"] = 1
                return ord('r')
            return -1

        monkeypatch.setattr(lldp.cv2, "waitKey", key)
        monkeypatch.setattr(lldp.LiveDebugProcessor, "_draw_overlay",
                            lambda self, f, i, *a, **k: f)
        proc._process_buffered_live("fake.mp4")
        assert proc._panel_enabled is True      # the toggle is a session setting
        assert proc.frame_processor.reset_calls == 1


# --------------------------------------------------------------------- #
# Render split: court first, then the overlay elements (compositing parity)
# --------------------------------------------------------------------- #

class TestRenderSplit:
    def test_court_drawn_before_overlay_elements(self, monkeypatch):
        proc, _ = make_processor()
        order = []
        monkeypatch.setattr(overlay, "draw_ball",
                            lambda *a, **k: order.append("ball"))
        frame = _frame(0)
        plan = overlay.LabelPlan()
        out = proc._render_frame(frame, 7, (10, 10, False),
                                 [(1, [0, 0, 5, 5])], plan)
        assert order == ["ball"]
        assert proc.court_detector.calls == [1]  # court drawn exactly once...
        # ...and on THIS frame object before the overlay elements.
        assert out is not None

    def test_draw_overlay_does_not_touch_court(self, monkeypatch):
        proc, _ = make_processor()
        monkeypatch.setattr(overlay, "draw_ball", lambda *a, **k: None)
        frame = _frame(0)
        proc._draw_overlay(frame, 7, (10, 10, False), [], overlay.LabelPlan())
        assert proc.court_detector.calls == []


# --------------------------------------------------------------------- #
# Thread-safe label plan
# --------------------------------------------------------------------- #

class TestThreadSafeLabelPlan:
    def test_matches_base_semantics(self):
        p = lldp._ThreadSafeLabelPlan()
        p.add(1, 10, "set", 0.8)
        p.add(1, 10, "set", 0.9)          # replace same (track, frame)
        assert p.active(1, 10) == ("set", 0.9)
        assert p.active(1, 10 + overlay.LABEL_PERSIST) is None  # window ends
        p.add(None, 5, "dig")             # ignored like the base class
        assert p.active(9, 5) is None

    def test_concurrent_add_and_active(self):
        p = lldp._ThreadSafeLabelPlan()
        errors = []

        def writer(tid):
            try:
                for i in range(2000):
                    p.add(tid, i, "bump")
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        deadline = time.time() + 5
        while any(t.is_alive() for t in threads) and time.time() < deadline:
            for tid in range(4):
                lab = p.active(tid, 1999)
                assert lab is None or lab[0] == "bump"
        for t in threads:
            t.join()
        assert not errors
        for tid in range(4):
            assert p.active(tid, 1999) == ("bump", None)
