"""
Ball detector for volleyball video analysis.

This module implements ball detection using YOLO models specifically trained
or adapted for sports ball detection in volleyball videos.
"""

from typing import List, Dict, Any, Optional
import numpy as np
import cv2
from ultralytics import YOLO
import torch

from .base_detector import BaseDetector


class BallDetector(BaseDetector):
    """Detector for volleyball balls in video frames.

    Uses YOLO model for detecting volleyball balls with high accuracy.
    Handles various ball states (in motion, stationary, partially occluded).
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.1,  # Much lower threshold for debugging
        device: str = "cpu"
    ):
        """Initialize the ball detector.

        Args:
            model_path: Path to custom YOLO model, uses pretrained if None
            confidence_threshold: Minimum confidence for ball detections
            device: Device to run inference on ("cpu" or "cuda")
        """
        super().__init__(confidence_threshold, device)
        self.model_path = model_path or "yolov8n.pt"  # Use nano model as default
        # Expand ball class IDs to include more potential ball objects
        self._ball_class_ids = {32, 37}  # COCO: 32=sports ball, 37=frisbee (similar round objects)
        self.load_model()

    def load_model(self) -> None:
        """Load the YOLO model for ball detection."""
        try:
            self.logger.info(f"Loading YOLO model from {self.model_path}")
            self._model = YOLO(self.model_path)

            # Set device
            if self.device == "cuda" and torch.cuda.is_available():
                self._model.to("cuda")
                self.logger.info("Using CUDA for ball detection")
            else:
                self.device = "cpu"
                self.logger.info("Using CPU for ball detection")

        except Exception as e:
            self.logger.error(f"Failed to load YOLO model: {e}")
            raise

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect volleyball balls in a frame.

        Args:
            frame: Input frame as numpy array (H, W, C)

        Returns:
            List of ball detection dictionaries with bbox, confidence, etc.
        """
        if not self.validate_frame(frame):
            return []

        try:
            # Preprocess frame
            processed_frame = self.preprocess_frame(frame)

            # Run YOLO inference
            results = self._model(processed_frame, verbose=False)

            # Process detections
            detections = self.postprocess_detections(results)

            # Filter by confidence and ball-specific criteria
            filtered_detections = self.filter_ball_detections(detections)

            self.logger.debug(f"Detected {len(filtered_detections)} balls in frame")
            return filtered_detections

        except Exception as e:
            self.logger.error(f"Ball detection failed: {e}")
            return []

    def postprocess_detections(self, results) -> List[Dict[str, Any]]:
        """Convert YOLO results to standard detection format.

        Args:
            results: YOLO detection results

        Returns:
            List of detection dictionaries
        """
        detections = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for i in range(len(boxes)):
                # Get box coordinates and convert to xyxy format
                box = boxes.xyxy[i].cpu().numpy()
                confidence = float(boxes.conf[i].cpu().numpy())
                class_id = int(boxes.cls[i].cpu().numpy())

                # Only process sports ball detections
                if class_id in self._ball_class_ids:
                    detection = {
                        "bbox": box.tolist(),  # [x1, y1, x2, y2]
                        "confidence": confidence,
                        "class_id": class_id,
                        "class_name": "volleyball",
                        "center": self._calculate_center(box),
                        "area": self._calculate_area(box)
                    }
                    detections.append(detection)

        return detections

    def filter_ball_detections(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply ball-specific filtering to detections.

        Args:
            detections: Raw ball detections

        Returns:
            Filtered ball detections
        """
        # First apply base confidence filtering
        filtered = self.filter_detections(detections)

        # Additional ball-specific filtering
        ball_filtered = []

        for detection in filtered:
            # Filter by area (balls shouldn't be too large or too small)
            area = detection.get("area", 0)
            if self._is_valid_ball_size(area):
                ball_filtered.append(detection)
            else:
                self.logger.debug(f"Filtered ball with invalid area: {area}")

        # If multiple balls detected, keep the one with highest confidence
        if len(ball_filtered) > 1:
            ball_filtered = [max(ball_filtered, key=lambda x: x["confidence"])]
            self.logger.debug("Multiple balls detected, keeping highest confidence")

        return ball_filtered

    def _calculate_center(self, bbox: np.ndarray) -> List[float]:
        """Calculate center point of bounding box.

        Args:
            bbox: Bounding box coordinates [x1, y1, x2, y2]

        Returns:
            Center point [x, y]
        """
        x1, y1, x2, y2 = bbox
        return [float((x1 + x2) / 2), float((y1 + y2) / 2)]

    def _calculate_area(self, bbox: np.ndarray) -> float:
        """Calculate area of bounding box.

        Args:
            bbox: Bounding box coordinates [x1, y1, x2, y2]

        Returns:
            Bounding box area
        """
        x1, y1, x2, y2 = bbox
        return float((x2 - x1) * (y2 - y1))

    def _is_valid_ball_size(self, area: float, frame_area: Optional[float] = None) -> bool:
        """Check if detected ball has reasonable size.

        Args:
            area: Bounding box area
            frame_area: Total frame area (optional)

        Returns:
            True if ball size is reasonable
        """
        # Minimum and maximum reasonable ball sizes (in pixels^2)
        min_area = 50  # Very small ball
        max_area = 10000  # Very large ball

        # If frame area is provided, use relative thresholds
        if frame_area:
            min_ratio = 0.0001  # 0.01% of frame
            max_ratio = 0.05    # 5% of frame
            min_area = max(min_area, frame_area * min_ratio)
            max_area = min(max_area, frame_area * max_ratio)

        return min_area <= area <= max_area

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
