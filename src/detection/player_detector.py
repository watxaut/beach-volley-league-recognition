"""
Player detector for volleyball video analysis.

This module implements player detection using YOLO models for identifying
volleyball players in video frames.
"""

from typing import List, Dict, Any, Optional
import numpy as np
import cv2
from ultralytics import YOLO

from .base_detector import BaseDetector


class PlayerDetector(BaseDetector):
    """Detector for volleyball players in video frames.

    Uses YOLO model for detecting human players with high accuracy.
    Handles multiple players and various poses/orientations.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
        device: str = "auto",
        max_players: int = 20,
        imgsz: int = 1280
    ):
        """Initialize the player detector.

        Args:
            model_path: Path to custom YOLO model, uses pretrained if None
            confidence_threshold: Minimum confidence for player detections
            device: Device to run inference on -- "auto" (CUDA > MPS > CPU),
                "cpu", "cuda", or "mps". Resolved by BaseDetector.
            max_players: Safety cap on how many person detections to return. This
                is a DETECTION limit, not the team size -- it must stay well above
                the number of people who can be on/around the court, otherwise the
                top-N-by-confidence cull drops real players (courtside bystanders
                near the camera outscore distant players). Downstream stages
                (court filter, tracker, ball proximity) do the real selection.
        """
        super().__init__(confidence_threshold, device)
        self.model_path = model_path or "yolov8n.pt"
        self.max_players = max_players
        # Inference resolution. Video is 1920x1080; YOLO's default 640 shrinks the
        # small, backlit far-side players below the detection floor. 1280 recovers
        # them at the cost of ~2x inference time.
        self.imgsz = imgsz
        self._person_class_ids = {0}  # COCO class ID for person
        self.court_detector = None  # Will be set later via set_court_detector
        self.load_model()

    def load_model(self) -> None:
        """Load the YOLO model for player detection."""
        try:
            self.logger.info(f"Loading YOLO model from {self.model_path}")
            self._model = YOLO(self.model_path)

            # self.device is already resolved to an available backend by
            # BaseDetector.__init__ (CUDA > MPS > CPU).
            if self.device in ("cuda", "mps"):
                self._model.to(self.device)
                self.logger.info(f"Using {self.device.upper()} for player detection")
            else:
                self.logger.info("Using CPU for player detection")

        except Exception as e:
            self.logger.error(f"Failed to load YOLO model: {e}")
            raise

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect volleyball players in a frame.

        Args:
            frame: Input frame as numpy array (H, W, C)

        Returns:
            List of player detection dictionaries with bbox, confidence, etc.
        """
        if not self.validate_frame(frame):
            return []

        try:
            # Preprocess frame
            processed_frame = self.preprocess_frame(frame)

            # Run YOLO inference
            results = self._model(processed_frame, verbose=False, imgsz=self.imgsz)

            # Process detections
            detections = self.postprocess_detections(results)

            # Filter and rank detections
            filtered_detections = self.filter_player_detections(detections, frame)

            self.logger.debug(f"Detected {len(filtered_detections)} players in frame")
            return filtered_detections

        except Exception as e:
            self.logger.error(f"Player detection failed: {e}")
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

                # Only process person detections
                if class_id in self._person_class_ids:
                    detection = {
                        "bbox": box.tolist(),  # [x1, y1, x2, y2]
                        "confidence": confidence,
                        "class_id": class_id,
                        "class_name": "player",
                        "center": self._calculate_center(box),
                        "area": self._calculate_area(box),
                        "aspect_ratio": self._calculate_aspect_ratio(box)
                    }
                    detections.append(detection)

        return detections

    def filter_player_detections(self, detections: List[Dict[str, Any]], frame: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
        """Apply player-specific filtering to detections.

        Args:
            detections: Raw player detections
            frame: Input frame for court filtering

        Returns:
            Filtered and ranked player detections
        """
        # First apply base confidence filtering
        filtered = self.filter_detections(detections)

        # Additional player-specific filtering
        player_filtered = []

        for detection in filtered:
            # Filter by aspect ratio (players should be taller than wide)
            aspect_ratio = detection.get("aspect_ratio", 0)
            if self._is_valid_player_aspect_ratio(aspect_ratio):
                # Filter by area (players should have reasonable size)
                area = detection.get("area", 0)
                if self._is_valid_player_size(area):
                    player_filtered.append(detection)
                else:
                    self.logger.debug(f"Filtered player with invalid area: {area}")
            else:
                self.logger.debug(f"Filtered player with invalid aspect ratio: {aspect_ratio}")

        # Court filtering: keep players inside/intersecting the PLAY AREA (court
        # + margin) so a player who steps off-court (server behind the baseline,
        # a chaser) is still detected. Strict foot-in-court admission is applied
        # later in PlayerTracker, so bystanders outside the play area are still
        # rejected from becoming tracks.
        if self.court_detector and frame is not None:
            court_filtered = []
            if hasattr(self.court_detector, "detect_play_area"):
                court_mask = self.court_detector.detect_play_area(frame)
            else:
                court_mask = self.court_detector.detect_court(frame)

            if court_mask is not None:
                for detection in player_filtered:
                    if self._is_player_in_court(detection, court_mask):
                        court_filtered.append(detection)
                    else:
                        self.logger.debug(f"Filtered player outside play area")
                player_filtered = court_filtered
            else:
                self.logger.warning("Court detection failed, keeping all players")

        # Sort by confidence and limit to max_players
        player_filtered.sort(key=lambda x: x["confidence"], reverse=True)

        if len(player_filtered) > self.max_players:
            self.logger.debug(f"Limiting detections from {len(player_filtered)} to {self.max_players}")
            player_filtered = player_filtered[:self.max_players]

        # Assign player IDs based on detection order
        for i, detection in enumerate(player_filtered):
            detection["player_id"] = i

        return player_filtered

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

    def _calculate_aspect_ratio(self, bbox: np.ndarray) -> float:
        """Calculate aspect ratio (height/width) of bounding box.

        Args:
            bbox: Bounding box coordinates [x1, y1, x2, y2]

        Returns:
            Aspect ratio (height/width)
        """
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        return float(height / width) if width > 0 else 0.0

    def _is_valid_player_aspect_ratio(self, aspect_ratio: float) -> bool:
        """Check if aspect ratio is reasonable for a standing player.

        Args:
            aspect_ratio: Height/width ratio

        Returns:
            True if aspect ratio is reasonable for a player
        """
        # Players should be taller than wide, but not extremely thin
        min_ratio = 0.6  # Allow wider bboxes for crouching/diving/close-to-camera players
        max_ratio = 5.0  # Very tall and thin
        return min_ratio <= aspect_ratio <= max_ratio

    def _is_valid_player_size(self, area: float, frame_area: Optional[float] = None) -> bool:
        """Check if detected player has reasonable size.

        Args:
            area: Bounding box area
            frame_area: Total frame area (optional)

        Returns:
            True if player size is reasonable
        """
        # Minimum and maximum reasonable player sizes (in pixels^2)
        min_area = 1000   # Small distant player
        max_area = 200000 # Very large close player

        # If frame area is provided, use relative thresholds
        if frame_area:
            min_ratio = 0.005  # 0.5% of frame
            max_ratio = 0.8    # 80% of frame
            min_area = max(min_area, frame_area * min_ratio)
            max_area = min(max_area, frame_area * max_ratio)

        return min_area <= area <= max_area

    def _is_player_in_court(self, detection: Dict[str, Any], court_mask: np.ndarray) -> bool:
        """Check if a player detection intersects with the court area.

        Args:
            detection: Player detection dictionary with bbox
            court_mask: Binary mask of court area (255 = court, 0 = outside)

        Returns:
            True if player intersects with court area
        """
        bbox = detection["bbox"]
        x1, y1, x2, y2 = map(int, bbox)

        # Ensure bbox is within frame bounds
        h, w = court_mask.shape
        x1 = max(0, min(x1, w-1))
        y1 = max(0, min(y1, h-1))
        x2 = max(0, min(x2, w-1))
        y2 = max(0, min(y2, h-1))

        if x2 <= x1 or y2 <= y1:
            return False

        # Check if any part of the player's bbox overlaps with court area
        player_region = court_mask[y1:y2, x1:x2]
        return np.any(player_region == 255)

    def set_court_detector(self, court_detector) -> None:
        """Set the court detector for filtering players by court boundaries.

        Args:
            court_detector: CourtDetector instance
        """
        self.court_detector = court_detector
