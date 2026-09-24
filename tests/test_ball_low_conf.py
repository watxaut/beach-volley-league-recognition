"""Tests for the BallTracker low-confidence floor (2026-09-24 mechanism).

The 20260920 match probe showed the detector's confidence is background-
dependent (sky-backed candidates med 0.90 vs sand-backed 0.20), so the ball
routinely drops below ``low_confidence_threshold`` (0.4) mid-rally and the
track starved on real footage (the largest measured loss class). Two floors
let the tracker keep a ball it still SEES, without touching any validated
P0 semantic:

- ``locked_low_conf_floor``: LOCKED admission ONLY on frames with zero
  >=0.4 candidates -- best non-suspect in-gate candidate, proximity first
  with the suspect-fallback's confidence tie-break. The trusted coast (a
  moving high candidate that left the gate) is never overridden.
- ``boot_low_conf_floor``: UNLOCKED motion-pair evidence may use low-tier
  sightings (same geometric gates) when no high-tier pair exists.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tracking.ball_tracker import BallTracker


class TestLockedLowFloor(unittest.TestCase):
    """LOCKED admission on zero-high frames (the 'blue sky' drop)."""

    def _det(self, x, y, conf=0.8, suspect=False):
        d = {"bbox": [int(x) - 10, int(y) - 10, int(x) + 10, int(y) + 10],
             "center": [float(x), float(y)], "confidence": conf,
             "class_name": "sports_ball"}
        if suspect:
            d["stationary_suspect"] = True
        return d

    def _lock(self, tracker, x=500, y=400, speed=20.0, frames=4):
        out = None
        for i in range(frames + 1):
            out = tracker.update([self._det(x + speed * i, y)])
        return out

    def test_low_conf_in_gate_keeps_the_track(self):
        """Ball drops to 0.25 against sand, still in gate: track survives."""
        tracker = BallTracker(max_missing_frames=10)
        self._lock(tracker)
        last = tracker.last_position
        out = tracker.update([self._det(last[0] + 25, last[1], conf=0.25)])
        self.assertIsNotNone(out)
        self.assertFalse(out["is_predicted"])
        self.assertEqual(out["center"], [last[0] + 25.0, float(last[1])])
        self.assertEqual(tracker.missing_count, 0)

    def test_off_by_default_valve(self):
        """locked_low_conf_floor=0 restores P0: a zero-high frame coasts
        (predicted output, no acceptance -- missing_count advances)."""
        tracker = BallTracker(max_missing_frames=10, locked_low_conf_floor=0.0)
        self._lock(tracker)
        last = tracker.last_position
        out = tracker.update([self._det(last[0] + 25, last[1], conf=0.25)])
        self.assertTrue(out["is_predicted"])
        self.assertEqual(tracker.missing_count, 1)

    def test_out_of_gate_low_conf_coasts(self):
        """A low-conf candidate outside the gate is not an acceptance: the
        track coasts on the prediction instead."""
        tracker = BallTracker(max_missing_frames=10)
        self._lock(tracker)
        last = tracker.last_position
        out = tracker.update([self._det(last[0] + 200, last[1], conf=0.25)])
        self.assertTrue(out["is_predicted"])
        self.assertEqual(tracker.missing_count, 1)

    def test_suspect_low_conf_never_accepted(self):
        tracker = BallTracker(max_missing_frames=10)
        self._lock(tracker)
        last = tracker.last_position
        out = tracker.update([self._det(last[0] + 25, last[1], conf=0.25,
                                        suspect=True)])
        self.assertTrue(out["is_predicted"])
        self.assertEqual(tracker.missing_count, 1)

    def test_nearest_wins_conf_tiebreak_within_window(self):
        """Proximity first; within the selection window confidence breaks ties."""
        tracker = BallTracker(max_missing_frames=10)
        self._lock(tracker)
        last = tracker.last_position
        near_low = self._det(last[0] + 10, last[1], conf=0.16)
        far_lower = self._det(last[0] + 50, last[1], conf=0.39)
        out = tracker.update([far_lower, near_low])
        self.assertIsNotNone(out)
        self.assertEqual(out["center"], [near_low["center"][0],
                                         near_low["center"][1]])

    def test_high_candidate_present_keeps_p0_semantics(self):
        """THE safety property: with ANY >=0.4 candidate in frame, the low
        tier never fires -- the trusted coast stays byte-exact P0."""
        tracker = BallTracker(max_missing_frames=10)
        self._lock(tracker)
        last = tracker.last_position
        # high candidate far away (trusted coast), low candidate in gate
        out = tracker.update([
            self._det(last[0] + 25, last[1], conf=0.25),
            self._det(last[0] + 300, last[1] - 200, conf=0.45),
        ])
        # coast, exactly as P0: a PREDICTED position, never the low pick
        self.assertTrue(out["is_predicted"])
        self.assertEqual(out["center"], [last[0] + 20.0, float(last[1])])
        self.assertEqual(tracker.missing_count, 1)

    def test_reentry_wait_never_traded_for_low_conf(self):
        """While the out-of-view re-entry window holds, the low tier is off."""
        tracker = BallTracker(max_missing_frames=10)
        self._lock(tracker, speed=-90.0)  # fast leftward flight toward exit
        # drive the track out of court bounds so the reentry window arms
        tracker.set_court_bounds((400, 300, 1500, 700))
        out = None
        for i in range(3):
            out = tracker.update([])  # coast out of view
        # after leaving bounds the tracker waits for re-entry (returns None,
        # _await_reentry True); a low-conf candidate near the anchor must not
        # take the track
        if tracker._await_reentry:
            anchor = tracker._reentry_anchor
            out = tracker.update([self._det(anchor[0] + 20, anchor[1],
                                            conf=0.25)])
            self.assertIsNone(out)


class TestBootLowFloor(unittest.TestCase):
    """UNLOCKED motion-pair evidence at the low floor."""

    def _det(self, x, y, conf=0.8, suspect=False):
        d = {"bbox": [int(x) - 10, int(y) - 10, int(x) + 10, int(y) + 10],
             "center": [float(x), float(y)], "confidence": conf,
             "class_name": "sports_ball"}
        if suspect:
            d["stationary_suspect"] = True
        return d

    def test_low_pair_bootstraps_when_no_high_pair(self):
        """A 0.25 toss moving 30 px/f locks (no high candidate in sight)."""
        tracker = BallTracker(max_missing_frames=10)
        out = tracker.update([self._det(924, 595, conf=0.25)])
        self.assertIsNone(out)  # first sighting: no pair yet
        out = tracker.update([self._det(933, 566, conf=0.25)])  # 30 px -> lock
        self.assertIsNotNone(out)
        self.assertTrue(tracker.locked)

    def test_high_pair_still_wins_over_low(self):
        """A high-tier pair fires first (P0 scan order untouched)."""
        tracker = BallTracker(max_missing_frames=10)
        tracker.update([self._det(924, 595, conf=0.25),   # low toss
                        self._det(1000, 400, conf=0.5)])  # high, elsewhere
        out = tracker.update([self._det(933, 566, conf=0.25),   # low pair
                              self._det(1020, 400, conf=0.5)])  # high pair
        self.assertIsNotNone(out)
        self.assertEqual(out["center"], [1020.0, 400.0])  # high pair won

    def test_off_by_default_valve(self):
        """boot_low_conf_floor=0 restores P0: low pair never locks."""
        tracker = BallTracker(max_missing_frames=10, boot_low_conf_floor=0.0)
        tracker.update([self._det(924, 595, conf=0.25)])
        out = tracker.update([self._det(933, 566, conf=0.25)])
        self.assertIsNone(out)
        self.assertFalse(tracker.locked)

    def test_low_static_spare_never_bootstraps(self):
        """Motion is still required: a drifting-at-2px/f low spare cannot lock."""
        tracker = BallTracker(max_missing_frames=10)
        for i in range(20):
            out = tracker.update([self._det(1765 + 2 * i, 747, conf=0.25)])
            self.assertIsNone(out)
        self.assertFalse(tracker.locked)

    def test_low_suspect_never_bootstraps(self):
        tracker = BallTracker(max_missing_frames=10)
        tracker.update([self._det(924, 595, conf=0.25, suspect=True)])
        out = tracker.update([self._det(933, 566, conf=0.25, suspect=True)])
        self.assertIsNone(out)
        self.assertFalse(tracker.locked)


if __name__ == "__main__":
    unittest.main()
