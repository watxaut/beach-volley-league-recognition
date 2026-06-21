"""
Ball detector for volleyball video analysis.

Uses YOLO sports ball detection (class 32) + frisbee (class 29) as the
ball often gets classified as either.

Key design decisions:
- Low confidence threshold (0.05): YOLO detects the ball in ~87% of frames
  at this level but only ~13% at 0.15. The ball tracker handles false positive
  rejection via trajectory consistency.
- Auto-scaled input resolution: YOLO's default 640px input makes the ball
  invisible in high-res video (a 40px ball in a 3K frame becomes ~9px).
  We scale the input to ensure the ball is at least ~20px in the YOLO input.
- Size filter: rejects detections too large to be a ball.
"""

from typing import List, Dict, Any, Optional

import numpy as np
import torch
from ultralytics import YOLO

from .base_detector import BaseDetector


class BallDetector(BaseDetector):
    """Detects volleyballs using YOLO.

    Uses classes 32 (sports ball) and 29 (frisbee) since YOLO frequently
    classifies volleyballs as either.
    """

    # COCO classes that can match a volleyball
    BALL_CLASSES = [32, 29]  # sports ball, frisbee

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.05,
        device: str = "cpu",
        max_ball_size: int = 80,
        imgsz: Optional[int] = None,
        keep_all: bool = False,
        # Legacy params accepted but ignored for backward compatibility
        **kwargs,
    ):
        """Initialize the ball detector.

        Args:
            model_path: Path to YOLO model weights. Defaults to yolov8n.pt.
            confidence_threshold: Minimum confidence for detections.
            device: Device for inference ("cpu" or "cuda").
            max_ball_size: Max width/height in pixels for a valid ball detection.
            imgsz: YOLO input resolution. If None, auto-computed from frame size
                to ensure ~20px ball visibility (capped at 1920).
            keep_all: If True, return every detection passing the confidence and
                size filters instead of culling to the single highest-confidence
                one. Intended for validation/diagnostic use -- production callers
                should leave this False since there is only one ball in play.
        """
        super().__init__(confidence_threshold, device)
        self.model_path = model_path or "yolov8n.pt"
        self.max_ball_size = max_ball_size
        self._imgsz = imgsz  # None = auto
        self._auto_imgsz: Optional[int] = None
        self._is_custom_model = model_path is not None
        self.keep_all = keep_all
        self.load_model()

    def load_model(self) -> None:
        """Load the YOLO model."""
        try:
            self.logger.info(f"Loading YOLO ball detector from {self.model_path}")
            self._model = YOLO(self.model_path)

            if self.device == "cuda" and torch.cuda.is_available():
                self._model.to("cuda")
                self.logger.info("Using CUDA for ball detection")
            else:
                self.device = "cpu"
                self.logger.info("Using CPU for ball detection")

        except Exception as e:
            self.logger.error(f"Failed to load YOLO model: {e}")
            raise

    def _get_imgsz(self, frame: np.ndarray) -> int:
        """Compute YOLO input size based on frame resolution.

        Goal: a ~50px ball in the original frame should be at least ~20px
        in the YOLO input. For a 1920px frame, 640 is fine (50 * 640/1920 = 17px).
        For a 3000px frame, we need ~1280 (50 * 1280/3000 = 21px).

        Returns a multiple of 32 (YOLO requirement), capped at 1920.
        """
        if self._imgsz is not None:
            return self._imgsz

        if self._auto_imgsz is not None:
            return self._auto_imgsz

        h, w = frame.shape[:2]
        max_dim = max(h, w)

        # For high-res video (>1080p), use at least half the original resolution.
        # For 1080p or lower, 640 is sufficient.
        # Capped at 1920 to avoid excessive memory/compute.
        if max_dim <= 1200:
            target = 640
        else:
            target = max(1280, max_dim // 2)

        # Round up to nearest 32, clamp at 1920
        target = min(1920, ((target + 31) // 32) * 32)

        self._auto_imgsz = target
        self.logger.info(
            f"Auto imgsz={target} for {w}x{h} frame "
            f"(50px ball -> {50 * target / max_dim:.0f}px in YOLO input)"
        )
        return target

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect volleyballs in a frame.

        Args:
            frame: Input frame as numpy array (H, W, C).

        Returns:
            List of ball detection dicts with bbox, center, confidence.
        """
        if not self.validate_frame(frame):
            return []

        try:
            imgsz = self._get_imgsz(frame)
            # Custom model: all classes are balls, no filtering needed.
            # Pretrained COCO model: filter to sports ball (32) + frisbee (29).
            classes = None if self._is_custom_model else self.BALL_CLASSES
            results = self._model(
                frame,
                verbose=False,
                classes=classes,
                conf=self.confidence_threshold,
                imgsz=imgsz,
            )
            detections = []

            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue

                for i in range(len(boxes)):
                    conf = float(boxes.conf[i])
                    if conf < self.confidence_threshold:
                        continue

                    x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().astype(int)
                    w = x2 - x1
                    h = y2 - y1

                    # Size filter: reject detections too large to be a ball
                    if w > self.max_ball_size or h > self.max_ball_size:
                        continue

                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2

                    detections.append({
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "center": [float(cx), float(cy)],
                        "confidence": conf,
                        "class_id": int(boxes.cls[i]),
                        "class_name": "sports_ball",
                    })

            # Keep only the highest confidence detection (there's only one ball).
            # Skipped when keep_all=True so validation tooling can see every
            # confident detection, including false positives.
            if len(detections) > 1 and not self.keep_all:
                detections.sort(key=lambda d: d["confidence"], reverse=True)
                detections = detections[:1]

            self.logger.debug(f"Ball detection: {len(detections)} balls")
            return detections

        except Exception as e:
            self.logger.error(f"Ball detection failed: {e}")
            return []

    def get_ball_trajectory(
        self, detections_sequence: List[List[Dict[str, Any]]]
    ) -> List[List[float]]:
        """Extract ball trajectory from sequence of detections."""
        trajectory = []
        for frame_detections in detections_sequence:
            if frame_detections:
                center = frame_detections[0].get("center", [0, 0])
                trajectory.append(center)
            else:
                trajectory.append([None, None])
        return trajectory
