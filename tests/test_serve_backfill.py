"""T5 serve-admission mechanisms A and B, in their PROBE-HARNESS home.

Both were REFUTED as a recovery (0/5 far serves each; see
``docs/t5_mechanism_ab.md``), so they deliberately live OUTSIDE ``src/``, in
``scripts/serve_mechanism_harness.py`` as default-off subclasses of
``BallTracker`` / ``ActionClassifier``. These tests keep them honest --
inert-by-default, mirror-of-production -- and the A/B replay in
``scripts/probe_serve_mechanisms.py`` stays reproducible.

* A adds a WEAKER motion bar for far-band balls while UNLOCKED, so a far-side
  toss (1.6-6.7 px/f) can lock before the contact. ~19 new bootstrap locks per
  4968 dev-clip frames and still no far-serve contact candidate.
* B retro-extends a FRESH lock backwards through the raw-detection buffer so
  the contact probe sees the pre-contact history. It creates NO new lock
  opportunities (the whole point), and on the dev clip it converts the
  `no_ball_sighting` probe rejections at the far serves into
  `no_contact_geometry` -- the evidence gap closes, the contact probe's own
  serve signature (fed ascent) still refuses the far float toss.
"""

import inspect
import os
import random
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from serve_mechanism_harness import (  # noqa: E402
    ProbeClassifier, ServeMechanismBallTracker)
from src.recognition.action_classifier import ActionClassifier  # noqa: E402
from src.tracking.ball_tracker import BallTracker  # noqa: E402
from src.utils.config import Config  # noqa: E402

SRC = os.path.join(ROOT, "src")


def det(x, y, conf=0.8, w=16, suspect=False, persist=0.0):
    """Detector-shaped candidate (w = apparent pixel width)."""
    d = {"bbox": [int(x - w / 2), int(y - w / 2), int(x + w / 2), int(y + w / 2)],
         "center": [float(x), float(y)], "confidence": conf,
         "class_name": "sports_ball"}
    if suspect:
        d["stationary_suspect"] = True
    d["persist"] = persist
    return d


def lock_frames(tracker, frames):
    """Feed frames (lists of detections); return the frames that lock."""
    out, prev = [], False
    for i, dets in enumerate(frames):
        tracker.update(dets, frame_number=i)
        if tracker.locked and not prev:
            out.append(i)
        prev = tracker.locked
    return out


def lock_frames_prod(tracker, frames):
    """Same, through the production ``update()`` (no frame_number)."""
    out, prev = [], False
    for i, dets in enumerate(frames):
        tracker.update(dets)
        if tracker.locked and not prev:
            out.append(i)
        prev = tracker.locked
    return out


def chain_of(tracker):
    """peek at the pending backfill chain without clearing it."""
    return list(tracker._backfill_out)


class TestHarnessLivesOutsideSrc(unittest.TestCase):
    """The refuted mechanisms must not be (re)introduced into src/."""

    FORBIDDEN = ("weak_min_speed", "weak_max_width", "backfill_lookback",
                 "backfill_radius", "backfill_max_gap", "backfill_max_width",
                 "backfill_min_conf", "backfill_skip_suspect",
                 "add_ball_sightings", "pop_backfill",
                 "ball_weak_min_speed", "ball_backfill_lookback")

    def test_no_mechanism_hook_in_src(self):
        for dirpath, _dirs, files in os.walk(SRC):
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                text = open(path, encoding="utf-8").read()
                for token in self.FORBIDDEN:
                    self.assertNotIn(
                        token, text,
                        f"{os.path.relpath(path, ROOT)} must not mention the "
                        f"refuted T5 mechanism token {token!r} -- it lives in "
                        f"scripts/serve_mechanism_harness.py")

    def test_config_does_not_expose_mechanism_keys(self):
        defaults = Config.DEFAULT_CONFIG
        for key in defaults:
            self.assertNotIn("weak_min_speed", key)
            self.assertNotIn("backfill", key)


class TestHarnessMirrorsProduction(unittest.TestCase):
    """Inert by default, and the copy of the motion scan cannot drift."""

    def test_defaults_are_off(self):
        tracker = ServeMechanismBallTracker()
        self.assertEqual(tracker.weak_min_speed, 0.0)
        self.assertEqual(tracker.weak_max_width, 0.0)
        self.assertEqual(tracker.backfill_lookback, 0)

    def test_harness_with_defaults_behaves_like_the_production_tracker(self):
        rng = random.Random(7)
        clip = []
        for i in range(120):
            dets = []
            if i % 17 == 0:                     # a static spare
                dets.append(det(200, 800, conf=0.9, w=16, suspect=True))
            if rng.random() < 0.6:
                speed = 4.0 if i % 3 else 25.0
                dets.append(det(900 + speed * i, 400 + 2 * speed * (i % 5),
                                conf=rng.choice([0.2, 0.5, 0.9]),
                                w=rng.choice([12, 16, 45])))
            clip.append(dets)
        prod, harness = BallTracker(), ServeMechanismBallTracker()
        self.assertEqual(lock_frames_prod(prod, clip), lock_frames(harness, clip))
        for dets in clip:
            self.assertEqual(BallTracker().update(dets),
                             ServeMechanismBallTracker().update(dets))

    def test_scan_copy_equals_the_production_scan(self):
        """At the production bar the copied loop returns exactly what
        ``BallTracker._scan_motion_pair`` returns (no silent drift)."""
        rng = random.Random(11)
        tracker = ServeMechanismBallTracker()
        for _ in range(200):
            plausible = [{"center": [rng.uniform(0, 1920), rng.uniform(0, 1080)],
                          "confidence": rng.uniform(0.1, 0.9)} for _ in range(3)]
            history = [[[rng.uniform(0, 1920), rng.uniform(0, 1080)]
                        for _ in range(2)] for _ in range(tracker.lock_motion_window)]
            a = BallTracker._scan_motion_pair(tracker, plausible, history)
            b = tracker._scan_motion_pair_with_bar(plausible, history,
                                                   tracker.lock_min_speed)
            self.assertEqual(a, b)

    def test_production_constructor_signature_is_untouched(self):
        params = inspect.signature(BallTracker.__init__).parameters
        for token in ("weak_min_speed", "backfill_lookback"):
            self.assertNotIn(token, params)


class TestWeakSpeedTier(unittest.TestCase):
    """Mechanism A: the second, weaker UNLOCKED motion bar."""

    def _toss(self, speed, width, n=6):
        """A slow far-side toss: `speed` px/frame upward, `width` px wide."""
        return [[det(900, 500 - speed * i, conf=0.5, w=width)]
                for i in range(n)]

    def test_off_by_default(self):
        tracker = ServeMechanismBallTracker()
        self.assertEqual(lock_frames(tracker, self._toss(4.0, 16)), [])

    def test_weak_tier_locks_a_slow_far_toss(self):
        tracker = ServeMechanismBallTracker(weak_min_speed=3.0,
                                            weak_max_width=30.0)
        self.assertEqual(lock_frames(tracker, self._toss(4.0, 16)), [1])

    def test_width_gate_keeps_near_side_balls_byte_identical(self):
        """A 50 px near-side ball must still need the full 8 px/f."""
        wide = ServeMechanismBallTracker(weak_min_speed=3.0,
                                         weak_max_width=30.0)
        self.assertEqual(lock_frames(wide, self._toss(4.0, 50)), [])
        fast = ServeMechanismBallTracker(weak_min_speed=3.0,
                                         weak_max_width=30.0)
        self.assertEqual(lock_frames(fast, self._toss(20.0, 50)), [1])

    def test_weak_tier_never_locks_a_stationary_spare(self):
        tracker = ServeMechanismBallTracker(weak_min_speed=3.0,
                                            weak_max_width=30.0)
        frames = [[det(300 + 3 * i, 700, conf=0.9, w=16, suspect=True)]
                  for i in range(6)]
        self.assertEqual(lock_frames(tracker, frames), [])

    def test_fast_path_is_untouched_when_the_tier_is_on(self):
        """Same lock frame as production on a fast far ball."""
        frames = [[det(900 - 30 * i, 500 - 30 * i, conf=0.9, w=16)]
                  for i in range(5)]
        self.assertEqual(lock_frames(ServeMechanismBallTracker(), frames),
                         lock_frames(ServeMechanismBallTracker(
                             weak_min_speed=3.0, weak_max_width=30.0), frames))


class TestBackfillOnFreshLock(unittest.TestCase):
    """Mechanism B: retro-extend a fresh lock through the raw detections."""

    @staticmethod
    def _serve_frames():
        frames = [[det(900, 470 - 2 * i, conf=0.5, w=15)] for i in range(10)]
        for i in range(1, 5):
            frames.append([det(900 + 20 * i, 452 - 20 * i, conf=0.8, w=15)])
        return frames

    def test_off_by_default_creates_no_buffer_and_no_points(self):
        tracker = ServeMechanismBallTracker()
        self.assertEqual(tracker.backfill_lookback, 0)
        self.assertEqual(lock_frames(tracker, self._serve_frames()), [10])
        self.assertEqual(len(tracker._det_buffer), 0)   # never filled
        self.assertEqual(tracker.pop_backfill(), [])

    def test_creates_no_new_lock_opportunities(self):
        """Same lock frame with and without the mechanism, over a long clip."""
        on = ServeMechanismBallTracker(backfill_lookback=20)
        clip = []
        for i in range(30):
            frame = []
            if i in (0, 1, 2, 12):                  # a couple of static spares
                frame.append(det(200, 800, conf=0.9, w=16, suspect=True))
            frame.append(det(900 + (2 if i < 10 else 20) * (i % 7),
                             470 - 3 * (i % 7), conf=0.5, w=15))
            clip.append(frame)
        self.assertEqual(lock_frames(ServeMechanismBallTracker(), clip),
                         lock_frames(on, clip))

    def test_chain_follows_the_toss_back_to_the_first_sighting(self):
        tracker = ServeMechanismBallTracker(backfill_lookback=20,
                                            backfill_max_width=30.0)
        self.assertEqual(lock_frames(tracker, self._serve_frames()), [10])
        chain = tracker.pop_backfill()
        self.assertEqual([p["frame_offset"] for p in chain], list(range(-10, 0)))
        self.assertEqual(chain[0]["center"], [900.0, 470.0])     # oldest
        self.assertEqual(chain[-1]["center"], [900.0, 452.0])    # nearest lock
        self.assertTrue(all(p["source"] == "backfill" for p in chain))
        self.assertTrue(all(p["width"] == 15.0 for p in chain))

    def test_chain_prefers_the_point_nearest_the_lock(self):
        """A second, farther candidate in the same frame must not be taken."""
        frames = [[det(900, 470 - 2 * i, conf=0.5, w=15),
                   det(1500, 300, conf=0.9, w=15)] for i in range(10)]
        for i in range(1, 5):
            frames.append([det(900 + 20 * i, 452 - 20 * i, conf=0.8, w=15)])
        tracker = ServeMechanismBallTracker(backfill_lookback=20,
                                            backfill_max_width=30.0)
        lock_frames(tracker, frames)
        chain = tracker.pop_backfill()
        self.assertEqual(len(chain), 10)
        self.assertTrue(all(abs(p["center"][0] - 900.0) < 1e-6 for p in chain))

    def test_chain_excludes_static_detections(self):
        """persist >= static_suspect is refused when the flag says so."""
        frames = [[det(900, 470 - 2 * i, conf=0.5, w=15,
                       suspect=(i % 2 == 0), persist=0.3 if i % 2 == 0 else 0.0)]
                  for i in range(10)]
        for i in range(1, 5):
            frames.append([det(900 + 20 * i, 452 - 20 * i, conf=0.8, w=15)])
        kept = ServeMechanismBallTracker(backfill_lookback=20)
        skipped = ServeMechanismBallTracker(backfill_lookback=20,
                                            backfill_skip_suspect=True)
        lock_frames(kept, frames)
        lock_frames(skipped, frames)
        self.assertEqual(len(chain_of(kept)), 10)
        # every other frame is flagged -> only the odd toss frames survive,
        # and the chain can bridge at most backfill_max_gap (2) empty frames
        self.assertEqual([p["frame_offset"] for p in chain_of(skipped)],
                         [-9, -7, -5, -3, -1])

    def test_chain_stops_at_the_gap_and_respects_lookback(self):
        short = ServeMechanismBallTracker(backfill_lookback=4)
        lock_frames(short, self._serve_frames())
        self.assertEqual([p["frame_offset"] for p in chain_of(short)],
                         [-4, -3, -2, -1])
        gapped = ServeMechanismBallTracker(backfill_lookback=20,
                                           backfill_max_gap=0)
        frames = [[det(900, 470 - 2 * i, conf=0.5, w=15)] for i in range(4)]
        frames += [[]] * 3
        for i in range(1, 5):
            frames.append([det(900 + 20 * i, 452 - 20 * i, conf=0.8, w=15)])
        lock_frames(gapped, frames)
        # only the frame right before the lock; the 3 empty frames end it
        self.assertEqual([p["frame_offset"] for p in chain_of(gapped)], [-1])

    def test_width_gate_keeps_near_side_chains_empty(self):
        """A 50 px near-side lock backfills nothing (far-band gate)."""
        tracker = ServeMechanismBallTracker(backfill_lookback=20,
                                            backfill_max_width=30.0)
        frames = [[det(900 - 20 * i, 500 - 20 * i, conf=0.9, w=50)]
                  for i in range(6)]
        lock_frames(tracker, frames)
        self.assertEqual(chain_of(tracker), [])

    def test_reentry_and_reset_paths_are_untouched(self):
        """The chain is additive: last_position/trajectory stay at the lock."""
        tracker = ServeMechanismBallTracker(backfill_lookback=20)
        lock_frames(tracker, self._serve_frames())
        chain = tracker.pop_backfill()
        self.assertEqual(len(chain), 10)
        self.assertEqual(tracker.last_position, [980.0, 372.0])
        # the trajectory itself is NOT rewritten: it holds only the real
        # sightings from the lock onwards (4 frames), never the 10 backfilled
        self.assertEqual(len(tracker.trajectory), 4)
        tracker.reset()
        self.assertEqual(len(tracker._det_buffer), 0)
        self.assertEqual(tracker._backfill_out, [])


class TestClassifierBackfillIngest(unittest.TestCase):
    """ProbeClassifier.add_ball_sightings (the contact probe's side)."""

    def _classifier(self):
        return ProbeClassifier(pose_estimator=None, court_calibration=None)

    def test_production_classifier_has_no_hook(self):
        self.assertFalse(hasattr(ActionClassifier, "add_ball_sightings"))

    def test_inserts_sorted_and_never_overwrites_a_real_point(self):
        ac = self._classifier()
        ac._ball_history.append((10, 100.0, 100.0, 20.0, 20.0))
        ac.add_ball_sightings([
            {"frame": 8, "x": 80.0, "y": 90.0, "w": 16.0, "h": 16.0},
            {"frame": 10, "x": 999.0, "y": 999.0, "w": 1.0, "h": 1.0},
            {"frame": 9, "x": 90.0, "y": 95.0, "w": 16.0, "h": 16.0},
        ])
        self.assertEqual([p[0] for p in ac._ball_history], [8, 9, 10])
        self.assertEqual(ac._ball_history[-1][1], 100.0)   # real point kept
        self.assertEqual(ac._backfill_frames, {8, 9})

    def test_backfilled_points_feed_the_contact_geometry(self):
        """A backfilled left side is what lets the probe see a vertex."""
        ac = self._classifier()
        ac._ball_history.extend([
            (10, 900.0, 470.0, 15.0, 15.0),
            (11, 900.0, 466.0, 15.0, 15.0),
            (12, 900.0, 462.0, 15.0, 15.0),
            (13, 900.0, 458.0, 15.0, 15.0),
            (20, 700.0, 300.0, 15.0, 15.0),
            (21, 660.0, 280.0, 15.0, 15.0),
        ])
        self.assertIsNone(ac._point_at(8))
        ac.add_ball_sightings([
            {"frame": 8, "x": 900.0, "y": 480.0, "w": 15.0, "h": 15.0},
            {"frame": 9, "x": 900.0, "y": 475.0, "w": 15.0, "h": 15.0},
        ])
        self.assertIsNotNone(ac._point_at(8))
        self.assertEqual(ac._real_points(8, 9), [
            (8, 900.0, 480.0, 15.0, 15.0), (9, 900.0, 475.0, 15.0, 15.0)])

    def test_reset_clears_the_backfill_flag(self):
        ac = self._classifier()
        ac.add_ball_sightings([{"frame": 5, "x": 1.0, "y": 2.0}])
        self.assertEqual(ac._backfill_frames, {5})
        ac.reset()
        self.assertEqual(ac._backfill_frames, set())


class TestProbeHarnessImports(unittest.TestCase):
    """The A/B replay must import the harness, not a src-local mechanism."""

    def test_probe_script_uses_the_harness(self):
        src = open(os.path.join(ROOT, "scripts", "probe_serve_mechanisms.py"),
                   encoding="utf-8").read()
        self.assertIn("from serve_mechanism_harness import", src)
        self.assertIn("ServeMechanismBallTracker", src)
        self.assertIn("ProbeClassifier", src)
        self.assertNotIn("from src.tracking.ball_tracker import BallTracker", src)


if __name__ == "__main__":
    unittest.main()
