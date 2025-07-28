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
from ..tracking.wilson_ball_tracker import WilsonBallTracker
from .wilson_template_detector import WilsonTemplateDetector
from .wilson_feature_detector import WilsonFeatureDetector
from .wilson_hybrid_detector import WilsonHybridDetector


class BallDetector(BaseDetector):
    """Detector for volleyball balls in video frames.

    Uses YOLO model for detecting volleyball balls with high accuracy.
    Handles various ball states (in motion, stationary, partially occluded).
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.05,  # Very low threshold for volleyball detection
        device: str = "cpu",
        use_wilson_tracker: bool = False,
        wilson_ball_dir: Optional[str] = None,
        detection_method: str = "hybrid",
        enable_multiple_methods: bool = True
    ):
        """Initialize the ball detector.

        Args:
            model_path: Path to custom YOLO model, uses pretrained if None
            confidence_threshold: Minimum confidence for ball detections
            device: Device to run inference on ("cpu" or "cuda")
            use_wilson_tracker: Whether to use Wilson ball tracker for enhanced detection
            wilson_ball_dir: Path to Wilson ball reference images directory
            detection_method: Primary detection method ("yolo", "template", "features", "hybrid", "fusion")
            enable_multiple_methods: Whether to enable multiple detection methods for fusion
        """
        super().__init__(confidence_threshold, device)
        # Use volleyball-optimized YOLOv8 model
        self.model_path = model_path or "yolov8n.pt"
        # Use sports ball class from COCO dataset
        self._ball_class_ids = {32}  # COCO class ID for sports ball

        # Motion-based detection parameters
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(detectShadows=False)
        self.prev_frame = None
        self.motion_threshold = 10

        # Multi-scale detection parameters
        self.detection_scales = [0.5, 0.75, 1.0, 1.25]  # Different scales to try

        # Optical flow tracking for ball continuity
        self.optical_flow_points = None
        self.optical_flow_mask = None
        self.lk_params = dict(winSize=(15, 15),
                             maxLevel=2,
                             criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

        # Color-based detection parameters (volleyball is typically white/bright)
        self.color_detection_enabled = True

        # Detection method configuration
        self.detection_method = detection_method
        self.enable_multiple_methods = enable_multiple_methods
        self.wilson_dir = wilson_ball_dir or "resources/wilson_ball"
        
        # Initialize Wilson-specific detectors
        self.wilson_detectors = {}
        self._initialize_wilson_detectors()
        
        # Initialize Wilson ball tracker
        self.use_wilson_tracker = use_wilson_tracker
        self.wilson_tracker = None
        if self.use_wilson_tracker:
            try:
                self.wilson_tracker = WilsonBallTracker(self.wilson_dir, device=self.device)
                self.logger.info("Wilson ball tracker initialized successfully")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Wilson tracker: {e}")
                self.use_wilson_tracker = False

        self.load_model()
        
        self.logger.info(f"Ball detector initialized with method: {self.detection_method}")

    def _initialize_wilson_detectors(self) -> None:
        """Initialize Wilson-specific detection methods."""
        try:
            if self.detection_method in ["template", "fusion"] or self.enable_multiple_methods:
                self.wilson_detectors['template'] = WilsonTemplateDetector(
                    template_dir=self.wilson_dir,
                    confidence_threshold=self.confidence_threshold
                )
                self.logger.info("Wilson template detector initialized")
        except Exception as e:
            self.logger.warning(f"Failed to initialize template detector: {e}")
        
        try:
            if self.detection_method in ["features", "fusion"] or self.enable_multiple_methods:
                self.wilson_detectors['features'] = WilsonFeatureDetector(
                    template_dir=self.wilson_dir,
                    confidence_threshold=self.confidence_threshold
                )
                self.logger.info("Wilson feature detector initialized")
        except Exception as e:
            self.logger.warning(f"Failed to initialize feature detector: {e}")
        
        try:
            if self.detection_method in ["hybrid", "fusion"] or self.enable_multiple_methods:
                self.wilson_detectors['hybrid'] = WilsonHybridDetector(
                    template_dir=self.wilson_dir,
                    confidence_threshold=self.confidence_threshold,
                    device=self.device
                )
                self.logger.info("Wilson hybrid detector initialized")
        except Exception as e:
            self.logger.warning(f"Failed to initialize hybrid detector: {e}")

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
        """Detect volleyball balls in a frame using configured detection method(s).

        Args:
            frame: Input frame as numpy array (H, W, C)

        Returns:
            List of ball detection dictionaries with bbox, confidence, etc.
        """
        if not self.validate_frame(frame):
            return []

        try:
            # If Wilson tracker is enabled, prioritize it
            if self.use_wilson_tracker and self.wilson_tracker:
                wilson_detection = self.wilson_tracker.detect_wilson_ball(frame)
                if wilson_detection:
                    detection = self._convert_wilson_detection(wilson_detection)
                    self.logger.debug("Ball detected using Wilson tracker")
                    return [detection]

            # Use configured detection method(s)
            if self.detection_method == "fusion":
                return self._fusion_detection(frame)
            elif self.detection_method == "template":
                return self._template_detection(frame)
            elif self.detection_method == "features":
                return self._feature_detection(frame)
            elif self.detection_method == "hybrid":
                return self._hybrid_detection(frame)
            else:  # "yolo" or fallback
                return self._yolo_detection(frame)

        except Exception as e:
            self.logger.error(f"Ball detection failed: {e}")
            return []

    def _fusion_detection(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect using fusion of multiple methods."""
        all_detections = []
        
        # Collect detections from all available methods
        if 'template' in self.wilson_detectors:
            template_dets = self.wilson_detectors['template'].detect(frame)
            all_detections.extend(template_dets)
        
        if 'features' in self.wilson_detectors:
            feature_dets = self.wilson_detectors['features'].detect(frame)
            all_detections.extend(feature_dets)
        
        if 'hybrid' in self.wilson_detectors:
            hybrid_dets = self.wilson_detectors['hybrid'].detect(frame)
            all_detections.extend(hybrid_dets)
        
        # Add YOLO detections as fallback
        yolo_dets = self._yolo_detection(frame)
        all_detections.extend(yolo_dets)
        
        # Fuse detections
        fused_detections = self._fuse_multiple_detections(all_detections)
        
        self.logger.debug(f"Fusion detection: {len(all_detections)} -> {len(fused_detections)} detections")
        return fused_detections

    def _template_detection(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect using template matching."""
        if 'template' in self.wilson_detectors:
            detections = self.wilson_detectors['template'].detect(frame)
            self.logger.debug(f"Template detection: {len(detections)} balls")
            return detections
        return []

    def _feature_detection(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect using feature matching."""
        if 'features' in self.wilson_detectors:
            detections = self.wilson_detectors['features'].detect(frame)
            self.logger.debug(f"Feature detection: {len(detections)} balls")
            return detections
        return []

    def _hybrid_detection(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect using hybrid CNN + classical CV."""
        if 'hybrid' in self.wilson_detectors:
            detections = self.wilson_detectors['hybrid'].detect(frame)
            self.logger.debug(f"Hybrid detection: {len(detections)} balls")
            return detections
        return []

    def _yolo_detection(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect using YOLO (original method)."""
        # Preprocess frame
        processed_frame = self.preprocess_frame(frame)

        # Run YOLO inference
        results = self._model(processed_frame, verbose=False)

        # Process detections
        detections = self.postprocess_detections(results)

        # Filter by confidence and ball-specific criteria
        filtered_detections = self.filter_ball_detections(detections)

        self.logger.debug(f"YOLO detection: {len(filtered_detections)} balls")
        return filtered_detections

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

    def _convert_wilson_detection(self, wilson_detection: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Wilson tracker detection to standard ball detection format.

        Args:
            wilson_detection: Detection from Wilson ball tracker

        Returns:
            Standard ball detection dictionary
        """
        center = wilson_detection['center']
        bbox = wilson_detection.get('bbox', [center[0] - 15, center[1] - 15, center[0] + 15, center[1] + 15])
        
        detection = {
            "bbox": bbox,
            "confidence": wilson_detection['confidence'],
            "class_id": 32,  # Sports ball class ID
            "class_name": "volleyball",
            "center": center,
            "area": (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]),
            "method": wilson_detection.get('method', 'wilson_tracker')
        }
        
        return detection

    def _fuse_multiple_detections(self, all_detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fuse detections from multiple detection methods.

        Args:
            all_detections: List of detections from different methods

        Returns:
            Fused and filtered detections
        """
        if not all_detections:
            return []

        # Group detections by spatial proximity
        groups = []
        used_indices = set()

        for i, det1 in enumerate(all_detections):
            if i in used_indices:
                continue

            group = [det1]
            used_indices.add(i)

            for j, det2 in enumerate(all_detections[i+1:], i+1):
                if j in used_indices:
                    continue

                # Check spatial overlap
                iou = self._calculate_iou(det1['bbox'], det2['bbox'])
                center_dist = np.sqrt(
                    (det1['center'][0] - det2['center'][0])**2 + 
                    (det1['center'][1] - det2['center'][1])**2
                )

                # Group if significant overlap or centers are close
                if iou > 0.2 or center_dist < 50:
                    group.append(det2)
                    used_indices.add(j)

            groups.append(group)

        # Fuse each group into a single detection
        fused_detections = []
        for group in groups:
            if len(group) == 1:
                fused_detections.append(group[0])
            else:
                fused_detection = self._fuse_detection_group(group)
                fused_detections.append(fused_detection)

        # Sort by confidence and apply final filtering
        fused_detections.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Return top detections only - max 2 for ball detection
        return fused_detections[:2]

    def _fuse_detection_group(self, group: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fuse a group of detections into a single detection."""
        # Calculate weighted average based on confidence
        total_confidence = sum(d['confidence'] for d in group)
        
        if total_confidence == 0:
            total_confidence = len(group)
            weights = [1.0] * len(group)
        else:
            weights = [d['confidence'] for d in group]
        
        # Weighted center
        center_x = sum(d['center'][0] * w for d, w in zip(group, weights)) / total_confidence
        center_y = sum(d['center'][1] * w for d, w in zip(group, weights)) / total_confidence
        
        # Union bounding box
        all_bboxes = [d['bbox'] for d in group]
        x1 = min(bbox[0] for bbox in all_bboxes)
        y1 = min(bbox[1] for bbox in all_bboxes)
        x2 = max(bbox[2] for bbox in all_bboxes)
        y2 = max(bbox[3] for bbox in all_bboxes)
        
        # Boost confidence for multi-method agreement
        confidence_boost = 1.0 + (len(group) - 1) * 0.1  # 10% boost per additional method
        max_confidence = max(d['confidence'] for d in group)
        fused_confidence = min(1.0, max_confidence * confidence_boost)
        
        # Collect methods used
        methods = [d.get('method', 'unknown') for d in group]
        
        return {
            'center': [center_x, center_y],
            'bbox': [x1, y1, x2, y2],
            'confidence': fused_confidence,
            'method': f"fused_{len(group)}_methods",
            'source_methods': methods,
            'group_size': len(group)
        }

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
