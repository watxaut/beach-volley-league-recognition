"""
Test suite for volleyball video analysis system.

This module contains unit tests for all components of the video analysis pipeline.
"""

import unittest
import numpy as np
import cv2
from pathlib import Path
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.detection.ball_detector import BallDetector
from src.detection.player_detector import PlayerDetector
from src.tracking.player_tracker import PlayerTracker
from src.tracking.ball_tracker import BallTracker
from src.utils.config import Config


class TestBallDetector(unittest.TestCase):
    """Test cases for ball detector."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = BallDetector(confidence_threshold=0.3)

    def test_initialization(self):
        """Test detector initialization."""
        self.assertIsNotNone(self.detector)
        self.assertEqual(self.detector.confidence_threshold, 0.3)

    def test_validate_frame(self):
        """Test frame validation."""
        # Valid frame
        valid_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        self.assertTrue(self.detector.validate_frame(valid_frame))

        # Invalid frames
        self.assertFalse(self.detector.validate_frame(None))
        self.assertFalse(self.detector.validate_frame("not_an_array"))

    def test_detect_empty_frame(self):
        """Test detection on empty frame."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = self.detector.detect(frame)
        self.assertIsInstance(detections, list)


class TestPlayerDetector(unittest.TestCase):
    """Test cases for player detector."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = PlayerDetector(confidence_threshold=0.5, max_players=4)

    def test_initialization(self):
        """Test detector initialization."""
        self.assertIsNotNone(self.detector)
        self.assertEqual(self.detector.confidence_threshold, 0.5)
        self.assertEqual(self.detector.max_players, 4)

    def test_validate_frame(self):
        """Test frame validation."""
        valid_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        self.assertTrue(self.detector.validate_frame(valid_frame))


class TestPlayerTracker(unittest.TestCase):
    """Test cases for player tracker."""

    def setUp(self):
        """Set up test fixtures."""
        self.tracker = PlayerTracker(max_disappeared=30, max_distance=100.0)

    def test_initialization(self):
        """Test tracker initialization."""
        self.assertIsNotNone(self.tracker)
        self.assertEqual(self.tracker.max_disappeared, 30)
        self.assertEqual(self.tracker.max_distance, 100.0)

    def test_update_empty_detections(self):
        """Test tracker update with empty detections."""
        result = self.tracker.update([])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_update_single_detection(self):
        """Test tracker update with single detection."""
        detection = {
            "bbox": [100, 100, 200, 300],
            "center": [150, 200],
            "confidence": 0.8,
            "class_name": "player"
        }

        result = self.tracker.update([detection])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertIn("track_id", result[0])


class TestBallTracker(unittest.TestCase):
    """Test cases for ball tracker."""

    def setUp(self):
        """Set up test fixtures."""
        self.tracker = BallTracker(max_missing_frames=10)

    def test_initialization(self):
        """Test tracker initialization."""
        self.assertIsNotNone(self.tracker)
        self.assertEqual(self.tracker.max_missing_frames, 10)

    def test_update_empty_detections(self):
        """Test tracker update with empty detections."""
        result = self.tracker.update([])
        self.assertIsNone(result)

    def test_update_single_detection(self):
        """A single static detection must NOT bootstrap the track.

        The 2026-09-06 ball-matching rework: only a MOVING candidate may
        lock the tracker (a spare/rack ball can never own the track), so a
        lone detection with no motion evidence returns None.
        """
        detection = {
            "bbox": [100, 100, 120, 120],
            "center": [110, 110],
            "confidence": 0.7,
            "class_name": "volleyball"
        }

        result = self.tracker.update([detection])
        self.assertIsNone(result)  # unlocked: no motion evidence yet

        # Same static spot next frame: still no lock.
        self.assertIsNone(self.tracker.update([dict(detection, center=[110.5, 110])]))

        # Motion over the next frame: the tracker locks.
        result = self.tracker.update([dict(detection, center=[122, 110])])
        self.assertIsNotNone(result)
        self.assertIn("center", result)
        self.assertTrue(self.tracker.locked)


class TestBallMatching(unittest.TestCase):
    """Ball-matching rework (2026-09-06): identity by trajectory, not confidence.

    Distilled from the entreno_6 / entreno_7 wrong-ball failures:
    static spares must never bootstrap or re-lock the track; a mid-rally
    higher-confidence spare must not steal the track; a coasting tracker
    must follow its velocity prediction, not sit on the last position.
    """

    def _det(self, x, y, conf=0.8, suspect=False):
        d = {"bbox": [int(x) - 10, int(y) - 10, int(x) + 10, int(y) + 10],
             "center": [float(x), float(y)], "confidence": conf,
             "class_name": "sports_ball"}
        if suspect:
            d["stationary_suspect"] = True
        return d

    def _lock_moving(self, tracker, x=500, y=400, speed=20.0, frames=4):
        """Feed frames of rightward motion so the tracker locks."""
        out = None
        for i in range(frames + 1):
            out = tracker.update([self._det(x + speed * i, y)])
        return out

    def test_static_spare_never_bootstraps(self):
        """entreno_6 f0: the bottom-right spare (2 px/f drift) must not lock."""
        tracker = BallTracker(max_missing_frames=10)
        for i in range(20):
            out = tracker.update([
                self._det(1765 + 2 * i, 747 + 0.7 * i, conf=0.94),  # drifting spare
                self._det(936, 465, conf=0.92),                     # static rack ball
            ])
            self.assertIsNone(out)
        self.assertFalse(tracker.locked)

    def test_serve_toss_locks_within_two_frames(self):
        """entreno_6/7: the toss (30 px/f) locks the tracker immediately."""
        tracker = BallTracker(max_missing_frames=10)
        for i in range(10):
            tracker.update([self._det(936, 465, conf=0.92)])  # static rack ball
        out = tracker.update([self._det(924, 595)])           # toss, 1st sighting
        self.assertIsNone(out)
        out = tracker.update([self._det(933, 566)])           # moved 30 px -> lock
        self.assertIsNotNone(out)
        self.assertEqual(out["center"], [933.0, 566.0])

    def test_in_gate_higher_confidence_wins_when_plausible(self):
        """KEPT old semantics: among plausible in-gate candidates the
        highest-confidence one wins (the old cull+select rule). The suspect
        flag is what handles off-trajectory parked balls -- a moving ball in
        gate is indistinguishable from the tracked ball by any local rule.
        (Known residual class: a fast-moving distractor crossing the flight
        path; revisit only with GT evidence.)"""
        tracker = BallTracker(max_missing_frames=10)
        self._lock_moving(tracker, x=800, y=300, speed=30.0)
        out = tracker.update([
            self._det(950, 300, conf=0.79),   # real ball, on trajectory
            self._det(936, 350, conf=0.90),   # plausible ball, in gate, higher conf
        ])
        self.assertIsNotNone(out)
        self.assertEqual(out["center"], [936.0, 350.0])

    def test_coast_gate_keeps_old_contact_recovery(self):
        """entreno_5/e3 contact dropouts: the outgoing ball near the touch
        point is still admitted by the growing gate around the last position
        (old, GT-validated behavior), while far-off distractors are not."""
        tracker = BallTracker(max_missing_frames=10)
        self._lock_moving(tracker, x=1000, y=400, speed=30.0)
        # Ball goes missing; the tracker coasts a conservative prediction.
        pred = tracker.update([])
        self.assertIsNotNone(pred)
        self.assertTrue(pred["is_predicted"])
        # A far-off spare is refused (old behavior) -- the frame stays a
        # prediction.
        out = tracker.update([self._det(1010, 640, conf=0.87)])
        self.assertIsNotNone(out)
        self.assertTrue(out["is_predicted"])
        # The outgoing ball near the last position is admitted.
        out = tracker.update([self._det(1150, 400, conf=0.87)])
        self.assertIsNotNone(out)
        self.assertFalse(out["is_predicted"])
        self.assertEqual(out["center"], [1150.0, 400.0])

    def test_stationary_suspect_top1_does_not_starve_the_track(self):
        """entreno_7 f241-244: the static rack ball out-confides the real
        ball. Old code starved (culled stream had only the rack ball); now
        the suspect top-1 off-trajectory is overridden by the in-gate real
        ball."""
        tracker = BallTracker(max_missing_frames=10)
        self._lock_moving(tracker, x=800, y=300, speed=30.0)
        out = tracker.update([
            self._det(950, 300, conf=0.79),                   # real ball, in gate
            self._det(1050, 350, conf=0.90, suspect=True),    # rack ball, off-gate
        ])
        self.assertIsNotNone(out)
        self.assertFalse(out["is_predicted"])
        self.assertEqual(out["center"], [950.0, 300.0])

    def test_moving_top1_out_of_gate_is_trusted_over_distractor(self):
        """entreno_1 f77: a slow far-side drill ball sits inside the grown
        gate while the REAL ball (higher confidence) has left it. The real
        ball is a plausible top-1: trust it and coast -- do NOT grab the
        distractor (the old grown-gate + all-candidates failure)."""
        tracker = BallTracker(max_missing_frames=10)
        self._lock_moving(tracker, x=1332, y=214, speed=8.0)
        out = tracker.update([])  # flight ends; coast
        self.assertIsNotNone(out)
        out = tracker.update([
            self._det(1016, 102, conf=0.91),               # real ball, far off-gate
            self._det(1375, 225, conf=0.41),               # distractor, IN gate
        ])
        self.assertIsNotNone(out)
        self.assertTrue(out["is_predicted"])               # distractor refused

    def test_suspect_never_bootstraps_or_relocks(self):
        tracker = BallTracker(max_missing_frames=10)
        # A suspect-flagged ball pair moving fast still cannot lock.
        d1 = self._det(500, 400); d1["stationary_suspect"] = True
        d2 = self._det(540, 400); d2["stationary_suspect"] = True
        self.assertIsNone(tracker.update([d1]))
        self.assertIsNone(tracker.update([d2]))
        self.assertFalse(tracker.locked)

    def test_relock_requires_motion(self):
        """entreno_6 f17: after a reset, a drifting spare (2-3 px/f) must not
        be re-locked; the next genuinely moving ball is."""
        tracker = BallTracker(max_missing_frames=2)
        self._lock_moving(tracker, frames=3)
        for _ in range(4):  # exceed max_missing_frames -> reset
            tracker.update([])
        self.assertFalse(tracker.locked)
        for i in range(6):  # slow-drifting spare
            self.assertIsNone(tracker.update([self._det(1790 + 3 * i, 775)]))
        out = tracker.update([self._det(926, 422)])  # fast ball appears
        self.assertIsNone(out)                        # 1st sighting: no motion yet
        out = tracker.update([self._det(926, 452)])   # 30 px down -> lock
        self.assertIsNotNone(out)

    def test_contact_reversal_within_gate(self):
        """A hard contact reverses the ball within one frame; the tight gate
        measured from the last position must admit the outgoing ball."""
        tracker = BallTracker(max_missing_frames=10)
        # Ball descending 30 px/f, then spikes upward at 55 px/f.
        for i in range(5):
            tracker.update([self._det(500, 400 + 30 * i)])
        out = tracker.update([self._det(500, 400 + 150 - 55)])
        self.assertIsNotNone(out)
        self.assertEqual(out["center"], [500.0, 495.0])

    def test_override_tie_nearest_trajectory_then_confidence(self):
        """On the override path (suspect blocker off-gate), the in-gate
        plausible candidate closest to the trajectory wins; confidence only
        breaks near-ties."""
        tracker = BallTracker(max_missing_frames=10)
        self._lock_moving(tracker, x=500, y=400, speed=20.0)
        out = tracker.update([
            self._det(590, 405, conf=0.55),                    # 11 px off
            self._det(575, 455, conf=0.95),                    # 55 px off
            self._det(700, 500, conf=0.99, suspect=True),      # blocker, off-gate
        ])
        self.assertIsNotNone(out)
        self.assertEqual(out["center"], [590.0, 405.0])

    def test_near_tie_goes_to_higher_confidence(self):
        tracker = BallTracker(max_missing_frames=10)
        self._lock_moving(tracker, x=500, y=400, speed=20.0)
        out = tracker.update([
            self._det(588, 402, conf=0.55),   # 2 px off
            self._det(590, 406, conf=0.95),   # 6 px off -- within the 10 px tie window
        ])
        self.assertEqual(out["center"], [590.0, 406.0])


class TestConfig(unittest.TestCase):
    """Test cases for configuration management."""

    def test_default_config(self):
        """Test default configuration creation."""
        config = Config.default()
        self.assertIsNotNone(config)
        self.assertEqual(config.get("device"), "auto")
        self.assertEqual(config.get("ball_confidence"), 0.15)  # must match scripts/test_action_recognition.py (see config comment)

    def test_config_validation(self):
        """Test configuration validation."""
        config = Config.default()
        self.assertTrue(config.validate())

        # Invalid configuration
        config.set("ball_confidence", 1.5)  # Invalid range
        self.assertFalse(config.validate())

    def test_config_access(self):
        """Test configuration access methods."""
        config = Config()

        # Test get/set
        config.set("test_key", "test_value")
        self.assertEqual(config.get("test_key"), "test_value")

        # Test dictionary-style access
        config["test_key2"] = "test_value2"
        self.assertEqual(config["test_key2"], "test_value2")

        # Test contains
        self.assertTrue("test_key" in config)
        self.assertFalse("nonexistent_key" in config)


def create_test_video(output_path: str, duration_seconds: int = 5) -> None:
    """Create a simple test video for testing purposes.

    Args:
        output_path: Path where to save the test video
        duration_seconds: Duration of the video in seconds
    """
    # Video properties
    width, height = 640, 480
    fps = 30
    total_frames = duration_seconds * fps

    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    for frame_idx in range(total_frames):
        # Create a simple test frame with moving objects
        frame = np.random.randint(50, 200, (height, width, 3), dtype=np.uint8)

        # Add a moving "ball" (white circle)
        ball_x = int((frame_idx / total_frames) * width)
        ball_y = height // 2 + int(50 * np.sin(frame_idx * 0.1))
        cv2.circle(frame, (ball_x, ball_y), 10, (255, 255, 255), -1)

        # Add "players" (colored rectangles)
        player1_x = width // 4
        player1_y = height // 2 + int(20 * np.sin(frame_idx * 0.05))
        cv2.rectangle(frame, (player1_x-20, player1_y-40), (player1_x+20, player1_y+40), (0, 255, 0), -1)

        player2_x = 3 * width // 4
        player2_y = height // 2 + int(20 * np.cos(frame_idx * 0.07))
        cv2.rectangle(frame, (player2_x-20, player2_y-40), (player2_x+20, player2_y+40), (0, 0, 255), -1)

        out.write(frame)

    out.release()
    print(f"Test video created: {output_path}")


class TestVideoProcessing(unittest.TestCase):
    """Integration tests for video processing pipeline."""

    @classmethod
    def setUpClass(cls):
        """Set up test video for integration tests."""
        cls.test_video_path = "test_video.mp4"
        create_test_video(cls.test_video_path, duration_seconds=2)

    @classmethod
    def tearDownClass(cls):
        """Clean up test video."""
        if os.path.exists(cls.test_video_path):
            os.remove(cls.test_video_path)

    def test_video_loading(self):
        """Test video file loading."""
        cap = cv2.VideoCapture(self.test_video_path)
        self.assertTrue(cap.isOpened())

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.assertGreater(frame_count, 0)

        cap.release()


if __name__ == "__main__":
    # Run all tests
    unittest.main(verbosity=2)


class TestOutOfViewReentry(unittest.TestCase):
    """entreno_6 f225-256: a dig lob exits the frame top; the old reset handed
    the track to a drifting spare, losing the f262 set. While the ball is
    provably out of view (court-bounds-rejected predictions), the tracker
    holds a re-entry window at the exit point instead of resetting."""

    def _det(self, x, y, conf=0.8):
        return {"bbox": [int(x) - 10, int(y) - 10, int(x) + 10, int(y) + 10],
                "center": [float(x), float(y)], "confidence": conf,
                "class_name": "sports_ball"}

    def test_lob_exit_then_reentry(self):
        tracker = BallTracker(max_missing_frames=10,
                              court_bounds=(100, 400, 1800, 950))
        # Ball rising fast toward the frame top (y decreasing).
        for i in range(6):
            out = tracker.update([self._det(1130, 300 - 40 * i)])
        self.assertIsNotNone(out)
        # Ball leaves the observable region; predictions get rejected. The
        # tracker must NOT reset into unlocked blind acceptance.
        for _ in range(15):
            out = tracker.update([])
            if out is not None:
                self.assertTrue(out["is_predicted"])
        self.assertTrue(tracker.locked)          # still holding the track
        self.assertTrue(tracker._await_reentry)
        # A drifting spare far from the exit point must not take the track.
        self.assertIsNone(tracker.update([self._det(1732, 854, conf=0.9)]))
        # The real ball re-enters near the exit point.
        out = tracker.update([self._det(1086, 190, conf=0.9)])
        self.assertIsNotNone(out)
        self.assertFalse(out["is_predicted"])
        self.assertEqual(out["center"], [1086.0, 190.0])
        self.assertFalse(tracker._await_reentry)

    def test_reentry_window_expires(self):
        tracker = BallTracker(max_missing_frames=5,
                              court_bounds=(100, 400, 1800, 950))
        for i in range(6):
            tracker.update([self._det(1130, 300 - 40 * i)])
        # Beyond 2x max_missing the window expires and the tracker resets.
        for _ in range(13):
            tracker.update([])
        self.assertFalse(tracker.locked)
        self.assertFalse(tracker._await_reentry)
