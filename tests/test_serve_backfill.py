"""T5 serve-admission mechanisms: (A) weak-speed lock tier, (B) backfill.

Both live in ``BallTracker`` behind config keys that default OFF (the A/B
replay in ``scripts/probe_serve_mechanisms.py`` measured them against the dev
clip: see ``docs/t5_serve_admission_diagnosis.md``).

* A adds a WEAKER motion bar for far-band balls while UNLOCKED, so a far-side
  toss (1.6-6.7 px/f) can lock before the contact. Measured and REFUTED as a
  recovery mechanism: it adds ~17 bootstrap locks per 4968 frames and still
  recovers no far serve -- kept only so the A/B replay stays reproducible.
* B retro-extends a FRESH lock backwards through the raw-detection buffer so
  the contact probe finally sees the pre-contact history. It creates NO new
  lock opportunities (the whole point), but on the dev clip it converts the
  `no_ball_sighting` probe rejections at the far serves into
  `no_contact_geometry` -- the evidence gap closes, the contact probe's own
  serve signature (fed ascent) still refuses the far float toss.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.recognition.action_classifier import ActionClassifier
from src.tracking.ball_tracker import BallTracker


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


class TestWeakSpeedTier(unittest.TestCase):
    """Mechanism A: the second, weaker UNLOCKED motion bar."""

    def _toss(self, speed, width, n=6):
        """A slow far-side toss: `speed` px/frame upward, `width` px wide."""
        return [[det(900, 500 - speed * i, conf=0.5, w=width)]
                for i in range(n)]

    def test_off_by_default(self):
        tracker = BallTracker()
        self.assertEqual(tracker.weak_min_speed, 0.0)
        self.assertEqual(lock_frames(tracker, self._toss(4.0, 16)), [])

    def test_weak_tier_locks_a_slow_far_toss(self):
        tracker = BallTracker(weak_min_speed=3.0, weak_max_width=30.0)
        self.assertEqual(lock_frames(tracker, self._toss(4.0, 16)), [1])

    def test_width_gate_keeps_near_side_balls_byte_identical(self):
        """A 50 px near-side ball must still need the full 8 px/f."""
        wide = BallTracker(weak_min_speed=3.0, weak_max_width=30.0)
        self.assertEqual(lock_frames(wide, self._toss(4.0, 50)), [])
        fast = BallTracker(weak_min_speed=3.0, weak_max_width=30.0)
        self.assertEqual(lock_frames(fast, self._toss(20.0, 50)), [1])

    def test_weak_tier_never_locks_a_stationary_spare(self):
        tracker = BallTracker(weak_min_speed=3.0, weak_max_width=30.0)
        frames = [[det(300, 700, conf=0.9, w=16, suspect=True)]
                  for _ in range(6)]
        # jitter of 3 px/frame on a flagged spare: still refused
        frames = [[det(300 + 3 * i, 700, conf=0.9, w=16, suspect=True)]
                  for i in range(6)]
        self.assertEqual(lock_frames(tracker, frames), [])

    def test_fast_path_is_untouched_when_the_tier_is_on(self):
        """Same lock frame as production on a fast far ball."""
        frames = [[det(900 - 30 * i, 500 - 30 * i, conf=0.9, w=16)]
                  for i in range(5)]
        self.assertEqual(lock_frames(BallTracker(), frames),
                         lock_frames(BallTracker(weak_min_speed=3.0,
                                                 weak_max_width=30.0), frames))


class TestBackfillOnFreshLock(unittest.TestCase):
    """Mechanism B: retro-extend a fresh lock through the raw detections."""

    def _serve(self, tracker):
        """A far serve: slow 2 px/f toss (f0-f9) then a fast 20 px/f hit."""
        return lock_frames(tracker, self._serve_frames())

    @staticmethod
    def _serve_frames():
        frames = [[det(900, 470 - 2 * i, conf=0.5, w=15)] for i in range(10)]
        for i in range(1, 5):
            frames.append([det(900 + 20 * i, 452 - 20 * i, conf=0.8, w=15)])
        return frames

    def test_off_by_default_creates_no_buffer_and_no_points(self):
        tracker = BallTracker()
        self.assertEqual(tracker.backfill_lookback, 0)
        self.assertEqual(self._serve(tracker), [10])
        self.assertEqual(tracker._det_buffer.maxlen, 2)   # deque never filled
        self.assertEqual(tracker.pop_backfill(), [])

    def test_creates_no_new_lock_opportunities(self):
        """Same lock frame with and without the mechanism, over a long clip."""
        base = BallTracker()
        on = BallTracker(backfill_lookback=20)
        clip = []
        for i in range(30):
            if i in (0, 1, 2, 12):                  # a couple of static spares
                clip.append([det(200, 800, conf=0.9, w=16, suspect=True)])
            clip[-1].append(det(900 + (2 if i < 10 else 20) * (i % 7),
                                470 - 3 * (i % 7), conf=0.5, w=15))
        self.assertEqual(lock_frames(base, clip), lock_frames(on, clip))

    def test_chain_follows_the_toss_back_to_the_first_sighting(self):
        tracker = BallTracker(backfill_lookback=20, backfill_max_width=30.0)
        lock_frame = self._serve(tracker)[0]
        chain = tracker.pop_backfill()
        self.assertEqual([p["frame_offset"] for p in chain], list(range(-10, 0)))
        self.assertEqual(chain[0]["center"], [900.0, 470.0])     # oldest
        self.assertEqual(chain[-1]["center"], [900.0, 452.0])    # nearest the lock
        self.assertTrue(all(p["source"] == "backfill" for p in chain))
        self.assertTrue(all(p["width"] == 15.0 for p in chain))
        self.assertEqual(lock_frame, 10)

    def test_chain_prefers_the_point_nearest_the_lock(self):
        """A second, farther candidate in the same frame must not be taken."""
        frames = [[det(900, 470 - 2 * i, conf=0.5, w=15),
                   det(1500, 300, conf=0.9, w=15)] for i in range(10)]
        for i in range(1, 5):
            frames.append([det(900 + 20 * i, 452 - 20 * i, conf=0.8, w=15)])
        tracker = BallTracker(backfill_lookback=20, backfill_max_width=30.0)
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
        kept = BallTracker(backfill_lookback=20)
        skipped = BallTracker(backfill_lookback=20, backfill_skip_suspect=True)
        lock_frames(kept, frames)
        lock_frames(skipped, frames)
        self.assertEqual(len(tracker_chain(kept)), 10)
        # every other frame is flagged -> only the odd toss frames survive,
        # and the chain can bridge at most backfill_max_gap (2) empty frames
        self.assertEqual([p["frame_offset"] for p in tracker_chain(skipped)],
                         [-9, -7, -5, -3, -1])

    def test_chain_stops_at_the_gap_and_respects_lookback(self):
        short = BallTracker(backfill_lookback=4)
        lock_frames(short, self._serve_frames())
        self.assertEqual([p["frame_offset"] for p in tracker_chain(short)],
                         [-4, -3, -2, -1])
        gapped = BallTracker(backfill_lookback=20, backfill_max_gap=0)
        frames = [[det(900, 470 - 2 * i, conf=0.5, w=15)] for i in range(4)]
        frames += [[]] * 3
        for i in range(1, 5):
            frames.append([det(900 + 20 * i, 452 - 20 * i, conf=0.8, w=15)])
        lock_frames(gapped, frames)
        # only the frame right before the lock; the 3 empty frames end it
        self.assertEqual([p["frame_offset"] for p in tracker_chain(gapped)], [-1])

    def test_width_gate_keeps_near_side_chains_empty(self):
        """A 50 px near-side lock backfills nothing (far-band gate)."""
        tracker = BallTracker(backfill_lookback=20, backfill_max_width=30.0)
        frames = [[det(900 - 20 * i, 500 - 20 * i, conf=0.9, w=50)]
                  for i in range(6)]
        lock_frames(tracker, frames)
        self.assertEqual(tracker_chain(tracker), [])

    def test_reentry_and_reset_paths_are_untouched(self):
        """The chain is additive: last_position/trajectory stay at the lock."""
        tracker = BallTracker(backfill_lookback=20)
        self._serve(tracker)
        chain = tracker.pop_backfill()
        self.assertEqual(len(chain), 10)
        self.assertEqual(tracker.last_position, [980.0, 372.0])
        # the trajectory itself is NOT rewritten: it holds only the real
        # sightings from the lock onwards (4 frames), never the 10 backfilled
        self.assertEqual(len(tracker.trajectory), 4)


def tracker_chain(tracker):
    """pop_backfill() without clearing it (helper for the assertions above)."""
    out = tracker._backfill_out
    tracker._backfill_out = []
    return out


class TestClassifierBackfillIngest(unittest.TestCase):
    """ActionClassifier.add_ball_sightings (the contact probe's side)."""

    def _classifier(self):
        return ActionClassifier(pose_estimator=None, court_calibration=None)

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


class TestWiring(unittest.TestCase):
    """The shared FrameProcessor path must own both hooks."""

    def test_frame_processor_passes_the_frame_and_feeds_the_probe(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "src",
                                "analysis", "frame_processor.py")).read()
        self.assertIn("self.ball_tracker.update(ball_detections,\n"
                      "                                                     "
                      "frame_number=frame_index)", src)
        self.assertIn("self.ball_tracker.pop_backfill()", src)
        self.assertIn("self.action_classifier.add_ball_sightings(", src)


if __name__ == "__main__":
    unittest.main()
