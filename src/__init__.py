"""
Beach Volleyball Video Analysis System

A comprehensive computer vision system for analyzing beach volleyball videos,
detecting players and ball, tracking movements, and recognizing actions.
"""

__version__ = "0.1.0"
__author__ = "Joan Heredia"

from src.analysis.video_processor import VideoProcessor
from src.detection.ball_detector import BallDetector
from src.detection.player_detector import PlayerDetector
from src.tracking.player_tracker import PlayerTracker
from src.recognition.action_classifier import ActionClassifier

__all__ = [
    "VideoProcessor",
    "BallDetector",
    "PlayerDetector",
    "PlayerTracker",
    "ActionClassifier",
]
