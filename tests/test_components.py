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
        """Test tracker update with single detection."""
        detection = {
            "bbox": [100, 100, 120, 120],
            "center": [110, 110],
            "confidence": 0.7,
            "class_name": "volleyball"
        }

        result = self.tracker.update([detection])
        self.assertIsNotNone(result)
        self.assertIn("center", result)


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
