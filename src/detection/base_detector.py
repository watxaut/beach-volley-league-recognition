"""
Base detector class for volleyball video analysis.

This module provides the abstract base class for all detection components,
ensuring consistent interface and common functionality.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import cv2
import logging


class BaseDetector(ABC):
    """Abstract base class for all object detectors in the volleyball analysis system.

    This class defines the common interface and shared functionality for detecting
    objects (players, balls) in volleyball video frames.
    """

    def __init__(self, confidence_threshold: float = 0.5, device: str = "cpu"):
        """Initialize the base detector.

        Args:
            confidence_threshold: Minimum confidence score for detections
            device: Device to run inference on ("cpu" or "cuda")
        """
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.logger = logging.getLogger(self.__class__.__name__)
        self._model = None

    @abstractmethod
    def load_model(self) -> None:
        """Load the detection model.

        This method must be implemented by subclasses to load their specific models.
        """
        pass

    @abstractmethod
    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect objects in a single frame.

        Args:
            frame: Input frame as numpy array (H, W, C)

        Returns:
            List of detection dictionaries, each containing:
            - bbox: Bounding box coordinates [x1, y1, x2, y2]
            - confidence: Detection confidence score
            - class_id: Object class identifier
            - class_name: Human-readable class name
        """
        pass

    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame before detection.

        Args:
            frame: Input frame as numpy array

        Returns:
            Preprocessed frame
        """
        # Default preprocessing: ensure frame is in RGB format
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            # Convert BGR to RGB if needed (OpenCV uses BGR by default)
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame

    def postprocess_detections(self, raw_detections: Any) -> List[Dict[str, Any]]:
        """Postprocess raw model detections.

        Args:
            raw_detections: Raw detections from the model

        Returns:
            Processed detections in standard format
        """
        # Default implementation - should be overridden by subclasses
        return []

    def filter_detections(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter detections based on confidence threshold and other criteria.

        Args:
            detections: List of detection dictionaries

        Returns:
            Filtered detections
        """
        filtered = []
        for detection in detections:
            if detection.get("confidence", 0.0) >= self.confidence_threshold:
                filtered.append(detection)

        self.logger.debug(f"Filtered {len(detections)} -> {len(filtered)} detections")
        return filtered

    def validate_frame(self, frame: np.ndarray) -> bool:
        """Validate that the input frame is valid for processing.

        Args:
            frame: Input frame to validate

        Returns:
            True if frame is valid, False otherwise
        """
        if frame is None:
            self.logger.warning("Received None frame")
            return False

        if not isinstance(frame, np.ndarray):
            self.logger.warning(f"Frame is not numpy array: {type(frame)}")
            return False

        if len(frame.shape) != 3:
            self.logger.warning(f"Frame has wrong dimensions: {frame.shape}")
            return False

        if frame.shape[2] not in [1, 3, 4]:  # Grayscale, RGB, or RGBA
            self.logger.warning(f"Frame has wrong number of channels: {frame.shape[2]}")
            return False

        return True

    def draw_detections(self, frame: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
        """Draw detection bounding boxes on frame for visualization.

        Args:
            frame: Input frame
            detections: List of detections to draw

        Returns:
            Frame with drawn detections
        """
        frame_copy = frame.copy()

        for detection in detections:
            bbox = detection.get("bbox", [])
            confidence = detection.get("confidence", 0.0)
            class_name = detection.get("class_name", "Unknown")

            if len(bbox) == 4:
                x1, y1, x2, y2 = map(int, bbox)

                # Draw bounding box
                cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Draw label
                label = f"{class_name}: {confidence:.2f}"
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                cv2.rectangle(
                    frame_copy,
                    (x1, y1 - label_size[1] - 10),
                    (x1 + label_size[0], y1),
                    (0, 255, 0),
                    -1
                )
                cv2.putText(
                    frame_copy,
                    label,
                    (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 0),
                    2
                )

        return frame_copy
