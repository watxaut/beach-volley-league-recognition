"""
Ball detector for volleyball video analysis.

This module implements ball detection using Wilson volleyball template matching
for accurate detection of volleyballs in video frames.
"""

from typing import List, Dict, Any, Optional
import numpy as np

from .base_detector import BaseDetector
from .wilson_template_detector import WilsonTemplateDetector


class BallDetector(BaseDetector):
    """Detector for volleyball balls in video frames.

    Uses Wilson volleyball template matching for detecting volleyball balls 
    with high accuracy across different scales and lighting conditions.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.03,  # Very low threshold for volleyball detection
        device: str = "cpu",
        wilson_ball_dir: Optional[str] = None,
        detection_method: str = "template",
    ):
        """Initialize the ball detector.

        Args:
            model_path: Unused (kept for compatibility)
            confidence_threshold: Minimum confidence for ball detections
            device: Device to run inference on ("cpu" or "cuda")
            wilson_ball_dir: Path to Wilson ball reference images directory
            detection_method: Detection method (only "template" supported)
        """
        super().__init__(confidence_threshold, device)
        
        # Template detection configuration
        self.detection_method = detection_method
        self.wilson_dir = wilson_ball_dir or "resources/wilson_ball"
        
        # Initialize Wilson template detector
        self.wilson_detectors = {}
        self._initialize_wilson_detectors()
        
        self.logger.info(f"Ball detector initialized with method: {self.detection_method}")

    def load_model(self) -> None:
        """Load model - not needed for template detection."""
        pass

    def _initialize_wilson_detectors(self) -> None:
        """Initialize Wilson template detector only."""
        try:
            self.wilson_detectors['template'] = WilsonTemplateDetector(
                template_dir=self.wilson_dir,
                confidence_threshold=self.confidence_threshold
            )
            self.logger.info("Wilson template detector initialized")
        except Exception as e:
            self.logger.warning(f"Failed to initialize template detector: {e}")
            raise


    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect volleyball balls in a frame using configured detection method(s).

        Args:
            frame: Input frame as numpy array (H, W, C)

        Returns:
            List of ball detection dictionaries with bbox, confidence, etc.
        """
        if not self.validate_frame(frame):
            return []

        try:
            # Only use template detection
            return self._template_detection(frame)

        except Exception as e:
            self.logger.error(f"Ball detection failed: {e}")
            return []


    def _template_detection(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect using template matching."""
        if 'template' in self.wilson_detectors:
            detections = self.wilson_detectors['template'].detect(frame)
            self.logger.debug(f"Template detection: {len(detections)} balls")
            return detections
        return []






    def get_ball_trajectory(self, detections_sequence: List[List[Dict[str, Any]]]) -> List[List[float]]:
        """Extract ball trajectory from sequence of detections.

        Args:
            detections_sequence: List of detection lists for each frame

        Returns:
            List of [x, y] coordinates representing ball trajectory
        """
        trajectory = []

        for frame_detections in detections_sequence:
            if frame_detections:
                # Take the first (and hopefully only) ball detection
                ball = frame_detections[0]
                center = ball.get("center", [0, 0])
                trajectory.append(center)
            else:
                # No ball detected in this frame
                trajectory.append([None, None])

        return trajectory

    def _calculate_iou(self, box1: List[int], box2: List[int]) -> float:
        """Calculate Intersection over Union (IoU) of two bounding boxes.
        
        Args:
            box1: First bounding box [x1, y1, x2, y2]
            box2: Second bounding box [x1, y1, x2, y2]
            
        Returns:
            IoU value between 0 and 1
        """
        x1_inter = max(box1[0], box2[0])
        y1_inter = max(box1[1], box2[1])
        x2_inter = min(box1[2], box2[2])
        y2_inter = min(box1[3], box2[3])

        if x2_inter <= x1_inter or y2_inter <= y1_inter:
            return 0.0

        inter_area = (x2_inter - x1_inter) * (y2_inter - y1_inter)
        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])

        union_area = box1_area + box2_area - inter_area
        return inter_area / union_area if union_area > 0 else 0.0
