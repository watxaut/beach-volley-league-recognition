"""
YOLO11-based Court Detection for Volleyball Courts.

This module implements court detection using a trained YOLO11 model
that can directly detect volleyball court boundaries as polygons.
"""

import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import torch


class YoloCourtDetector:
    """
    YOLO11-based volleyball court detector.
    
    Uses a trained YOLO11 model to detect court boundaries directly,
    providing more accurate and robust detection than geometric methods.
    """

    def __init__(
        self,
        model_path: str = "weights/court/court_best.pt",
        confidence_threshold: float = 0.5,
        device: str = "auto",
        input_size: int = 640
    ):
        """
        Initialize YOLO court detector.

        Args:
            model_path: Path to trained YOLO11 court detection model
            confidence_threshold: Minimum confidence for court detection
            device: Device for inference ("cpu", "cuda", or "auto")
            input_size: Input image size for YOLO model
        """
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self.input_size = input_size
        
        self.logger = logging.getLogger(__name__)
        self.device = self._setup_device(device)
        
        # Detection state
        self.model = None
        self.is_loaded = False
        self.last_detection = None
        self.detection_confidence = 0.0
        
        # Initialize model
        self._load_model()

    def _setup_device(self, device: str) -> str:
        """Setup computation device for YOLO inference."""
        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        
        self.logger.info(f"Using device: {device}")
        return device

    def _load_model(self) -> None:
        """Load YOLO11 court detection model."""
        try:
            if not self.model_path.exists():
                self.logger.warning(f"YOLO court model not found at {self.model_path}")
                self.logger.warning("Court detection will fallback to geometric method")
                self.is_loaded = False
                return
            
            # Import YOLO (ultralytics)
            try:
                from ultralytics import YOLO
            except ImportError:
                self.logger.error("ultralytics not installed. Install with: pip install ultralytics")
                self.is_loaded = False
                return
            
            # Load model
            self.model = YOLO(str(self.model_path))
            self.model.to(self.device)
            
            # Verify model is for court detection
            if hasattr(self.model, 'names'):
                class_names = self.model.names
                self.logger.info(f"Loaded YOLO court model with classes: {class_names}")
                
                # Verify court-related classes exist
                court_classes = ['court', 'volleyball_court', 'court_boundary']
                if not any(cls in str(class_names).lower() for cls in court_classes):
                    self.logger.warning("Model may not be trained for court detection")
            
            self.is_loaded = True
            self.logger.info(f"Successfully loaded YOLO court model from {self.model_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to load YOLO court model: {e}")
            self.is_loaded = False

    def detect_court(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Detect volleyball court in frame using YOLO model.

        Args:
            frame: Input video frame

        Returns:
            Court detection result or None if detection failed
        """
        if not self.is_loaded or self.model is None:
            return None
        
        try:
            # Run inference
            results = self.model(frame, conf=self.confidence_threshold, verbose=False)
            
            if not results or len(results) == 0:
                return None
            
            # Process first result
            result = results[0]
            
            # Extract court detection
            court_detection = self._process_yolo_result(result, frame.shape)
            
            if court_detection:
                self.last_detection = court_detection
                self.detection_confidence = court_detection['confidence']
                
            return court_detection
            
        except Exception as e:
            self.logger.error(f"YOLO court detection failed: {e}")
            return None

    def _process_yolo_result(self, result, frame_shape: Tuple[int, int]) -> Optional[Dict[str, Any]]:
        """
        Process YOLO detection result to extract court information.

        Args:
            result: YOLO detection result
            frame_shape: Frame dimensions (height, width)

        Returns:
            Processed court detection data
        """
        h, w = frame_shape[:2]
        
        # Check if we have detections
        if result.boxes is None or len(result.boxes) == 0:
            return None
        
        # Find best court detection
        best_detection = None
        best_confidence = 0.0
        
        for i, box in enumerate(result.boxes):
            confidence = float(box.conf[0])
            class_id = int(box.cls[0])
            
            if confidence > best_confidence and confidence >= self.confidence_threshold:
                best_confidence = confidence
                best_detection = {
                    'box': box,
                    'confidence': confidence,
                    'class_id': class_id,
                    'index': i
                }
        
        if best_detection is None:
            return None
        
        # Extract bounding box coordinates
        box = best_detection['box']
        xyxy = box.xyxy[0].cpu().numpy()  # [x1, y1, x2, y2]
        x1, y1, x2, y2 = map(int, xyxy)
        
        # Create court detection result
        court_data = {
            'bbox': [x1, y1, x2, y2],
            'confidence': best_confidence,
            'class_id': best_detection['class_id'],
            'center': [(x1 + x2) // 2, (y1 + y2) // 2],
            'area': (x2 - x1) * (y2 - y1),
            'detection_method': 'yolo'
        }
        
        # Extract polygon if available (for segmentation models)
        if hasattr(result, 'masks') and result.masks is not None:
            court_polygon = self._extract_court_polygon(result.masks, best_detection['index'], frame_shape)
            if court_polygon:
                court_data['polygon'] = court_polygon
                court_data['mask'] = self._create_mask_from_polygon(court_polygon, frame_shape)
        else:
            # Create approximate trapezoid from bounding box
            court_data['polygon'] = self._bbox_to_trapezoid(court_data['bbox'], frame_shape)
            court_data['mask'] = self._create_mask_from_polygon(court_data['polygon'], frame_shape)
        
        return court_data

    def _extract_court_polygon(self, masks, detection_index: int, frame_shape: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        """
        Extract court polygon from YOLO segmentation mask.

        Args:
            masks: YOLO segmentation masks
            detection_index: Index of the court detection
            frame_shape: Frame dimensions

        Returns:
            List of polygon points or None
        """
        try:
            if detection_index >= len(masks.xy):
                return None
            
            # Get mask coordinates
            mask_coords = masks.xy[detection_index]
            
            if len(mask_coords) == 0:
                return None
            
            # Convert to integer coordinates
            polygon = [(int(x), int(y)) for x, y in mask_coords]
            
            # Simplify polygon if too many points
            if len(polygon) > 10:
                polygon = self._simplify_polygon(polygon, epsilon=5.0)
            
            return polygon
            
        except Exception as e:
            self.logger.debug(f"Failed to extract court polygon: {e}")
            return None

    def _bbox_to_trapezoid(self, bbox: List[int], frame_shape: Tuple[int, int]) -> List[Tuple[int, int]]:
        """
        Convert bounding box to approximate trapezoid shape for court.

        Args:
            bbox: Bounding box [x1, y1, x2, y2]
            frame_shape: Frame dimensions

        Returns:
            Trapezoid polygon points
        """
        x1, y1, x2, y2 = bbox
        h, w = frame_shape[:2]
        
        # Calculate perspective adjustment based on position in frame
        # Assume perspective makes top narrower than bottom
        width = x2 - x1
        height = y2 - y1
        
        # Perspective factor: closer to top = more perspective
        perspective_factor = max(0.1, min(0.4, (h - y1) / h))
        top_width_reduction = int(width * perspective_factor)
        
        # Create trapezoid points
        trapezoid = [
            (x1 + top_width_reduction // 2, y1),  # Top-left
            (x2 - top_width_reduction // 2, y1),  # Top-right
            (x2, y2),                              # Bottom-right
            (x1, y2)                               # Bottom-left
        ]
        
        return trapezoid

    def _simplify_polygon(self, polygon: List[Tuple[int, int]], epsilon: float = 2.0) -> List[Tuple[int, int]]:
        """
        Simplify polygon using Douglas-Peucker algorithm.

        Args:
            polygon: Input polygon points
            epsilon: Simplification tolerance

        Returns:
            Simplified polygon
        """
        try:
            polygon_array = np.array(polygon, dtype=np.int32)
            simplified = cv2.approxPolyDP(polygon_array, epsilon, closed=True)
            return [(int(x), int(y)) for x, y in simplified.reshape(-1, 2)]
        except:
            return polygon

    def _create_mask_from_polygon(self, polygon: List[Tuple[int, int]], frame_shape: Tuple[int, int]) -> np.ndarray:
        """
        Create binary mask from polygon.

        Args:
            polygon: Polygon points
            frame_shape: Frame dimensions

        Returns:
            Binary mask array
        """
        h, w = frame_shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        
        if len(polygon) >= 3:
            polygon_array = np.array(polygon, dtype=np.int32)
            cv2.fillPoly(mask, [polygon_array], 255)
        
        return mask

    def get_court_mask(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Get binary mask of detected court area.

        Args:
            frame: Input frame

        Returns:
            Binary mask or None if no court detected
        """
        detection = self.detect_court(frame)
        if detection and 'mask' in detection:
            return detection['mask']
        return None

    def get_court_polygon(self, frame: np.ndarray) -> Optional[List[Tuple[int, int]]]:
        """
        Get polygon points of detected court.

        Args:
            frame: Input frame

        Returns:
            Polygon points or None if no court detected
        """
        detection = self.detect_court(frame)
        if detection and 'polygon' in detection:
            return detection['polygon']
        return None

    def is_point_in_court(self, point: Tuple[int, int], frame: np.ndarray) -> bool:
        """
        Check if point is within detected court area.

        Args:
            point: (x, y) coordinates
            frame: Current frame for detection

        Returns:
            True if point is in court
        """
        mask = self.get_court_mask(frame)
        if mask is None:
            return True  # Default to allowing all points if no court detected
        
        x, y = point
        h, w = mask.shape
        
        if 0 <= x < w and 0 <= y < h:
            return mask[y, x] > 0
        
        return False

    def draw_court_overlay(self, frame: np.ndarray, detection: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """
        Draw court detection overlay on frame.

        Args:
            frame: Input frame
            detection: Court detection data (if None, will detect on frame)

        Returns:
            Frame with court overlay
        """
        overlay = frame.copy()
        
        if detection is None:
            detection = self.detect_court(frame)
        
        if detection is None:
            return overlay
        
        # Draw bounding box
        if 'bbox' in detection:
            x1, y1, x2, y2 = detection['bbox']
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Draw polygon
        if 'polygon' in detection:
            polygon = np.array(detection['polygon'], dtype=np.int32)
            cv2.polylines(overlay, [polygon], True, (255, 0, 0), 3)
            
            # Fill with semi-transparent overlay
            mask = np.zeros_like(frame)
            cv2.fillPoly(mask, [polygon], (0, 255, 0))
            overlay = cv2.addWeighted(overlay, 0.8, mask, 0.2, 0)
        
        # Add detection info
        confidence = detection.get('confidence', 0.0)
        method = detection.get('detection_method', 'unknown')
        
        info_text = f"YOLO Court: {confidence:.2f}"
        cv2.putText(overlay, info_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        return overlay

    def get_detection_confidence(self) -> float:
        """Get confidence of last court detection."""
        return self.detection_confidence

    def is_model_loaded(self) -> bool:
        """Check if YOLO model is successfully loaded."""
        return self.is_loaded

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded model."""
        return {
            'model_path': str(self.model_path),
            'is_loaded': self.is_loaded,
            'device': self.device,
            'confidence_threshold': self.confidence_threshold,
            'input_size': self.input_size,
            'model_exists': self.model_path.exists()
        }