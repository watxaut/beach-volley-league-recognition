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
from collections import deque

import numpy as np
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
        device: str = "auto",
        max_ball_size: int = 80,
        imgsz: Optional[int] = None,
        keep_all: bool = True,  # deprecated: accepted, ignored (always all)
        suppress_static: bool = True,
        static_radius: float = 25.0,
        static_window: int = 40,
        static_min_frames: int = 8,
        static_persist_frac: float = 0.55,
        static_suspect_frac: float = 0.30,
        # Legacy params accepted but ignored for backward compatibility
        **kwargs,
    ):
        """Initialize the ball detector.

        Args:
            model_path: Path to YOLO model weights. Defaults to yolov8n.pt.
            confidence_threshold: Minimum confidence for detections.
            device: Device for inference -- "auto" (CUDA > MPS > CPU), "cpu",
                "cuda", or "mps". Resolved by BaseDetector.
            max_ball_size: Max width/height in pixels for a valid ball detection.
            imgsz: YOLO input resolution. If None, auto-computed from frame size
                to ensure ~20px ball visibility (capped at 1920).
            keep_all: Deprecated. Accepted for backward compatibility and
                ignored: the detector always returns every detection passing
                the confidence and size filters. Candidate SELECTION belongs
                to the BallTracker (trajectory gates), not to confidence --
                the old top-1 cull let a high-confidence courtside/rack ball
                hide the ball in play (entreno_6 serve, entreno_7 f244 set).
            suppress_static: If True, drop detections that stay near-stationary
                across a rolling window of recent frames. Beach practice courts
                often have spare balls sitting on the sand or in a ball cart; a
                fine-tuned model detects these at high confidence every frame, so
                the top-1 cull below would lock onto a courtside ball instead of
                the ball in play. Suppression removes them before the cull.
            static_radius: Max pixel distance for two detections to count as the
                same (stationary) object across frames.
            static_window: Number of recent frames considered when deciding
                whether a detection is stationary.
            static_min_frames: Minimum frames of history required before
                suppression activates (warmup).
            static_persist_frac: Fraction of windowed frames a location must be
                present in to be judged static and REMOVED (0-1).
            static_suspect_frac: Lower threshold: surviving detections at or
                above this persistence are kept but flagged
                ``stationary_suspect`` -- possibly-parked balls the BallTracker
                may distrust for identity decisions (it must never re-lock
                onto a ball that is not in play) without the removal cost of
                full suppression.
        """
        super().__init__(confidence_threshold, device)
        self.model_path = model_path or "yolov8n.pt"
        self.max_ball_size = max_ball_size
        self._imgsz = imgsz  # None = auto
        self._auto_imgsz: Optional[int] = None
        self._is_custom_model = model_path is not None
        self.keep_all = keep_all

        self.suppress_static = suppress_static
        self.static_radius = static_radius
        self.static_min_frames = static_min_frames
        self.static_persist_frac = static_persist_frac
        self.static_suspect_frac = static_suspect_frac
        # Rolling history of per-frame detection centers (all passing detections,
        # pre-suppression) used to detect stationary courtside balls.
        self._recent_centers: deque = deque(maxlen=static_window)
        # T4 diagnostics: OFF by default. When FrameProcessor enables it, every
        # candidate (including the ones static suppression removes) is mirrored
        # here with its persistence fraction, so the loss waterfall can see what
        # the suppression stage dropped. Pure observation -- no effect on the
        # returned detections.
        self.diag_enabled = False
        self._diag_dets: List[Dict[str, Any]] = []
        # Side channel (read-only): the detections BEFORE static suppression,
        # kept every frame so an observer can work on the un-suppressed stream
        # without a second decode.  The AGENTS.md §6 escalation path for
        # windows the stream mis-serves (far-flight mining) needs exactly this;
        # ``detect()``'s return value is unchanged either way.
        self.raw_detections: List[Dict[str, Any]] = []

        self.load_model()

    def load_model(self) -> None:
        """Load the YOLO model."""
        try:
            self.logger.info(f"Loading YOLO ball detector from {self.model_path}")
            self._model = YOLO(self.model_path)

            # self.device is already resolved to an available backend by
            # BaseDetector.__init__ (CUDA > MPS > CPU).
            if self.device in ("cuda", "mps"):
                self._model.to(self.device)
                self.logger.info(f"Using {self.device.upper()} for ball detection")
            else:
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

        if self.diag_enabled:
            self._diag_dets = []
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

            # Stationary courtside balls: removed entirely at the suppression
            # threshold; weaker stationarity is only FLAGGED so the tracker
            # can distrust those candidates (see __init__). The full
            # pre-suppression center list is what we remember, so a phantom
            # keeps being counted even on frames where it's suppressed.
            self.raw_detections = list(detections)
            if self.suppress_static:
                survivors = []
                for d in detections:
                    persist = self._static_persist(d["center"])
                    if self.diag_enabled:
                        self._diag_dets.append({
                            "center": [float(d["center"][0]), float(d["center"][1])],
                            "conf": float(d.get("confidence", 0.0)),
                            "bbox": list(d.get("bbox", [])),
                            "persist": round(float(persist), 3),
                            "suspect": persist >= self.static_suspect_frac,
                            "removed": persist >= self.static_persist_frac,
                        })
                    if persist >= self.static_persist_frac:
                        continue
                    if persist >= self.static_suspect_frac:
                        d["stationary_suspect"] = True
                    survivors.append(d)
                self._recent_centers.append([d["center"] for d in detections])
                detections = survivors

            # NO top-1 cull: every surviving candidate goes to the tracker,
            # which owns identity via trajectory gates. Culling by confidence
            # here once let a static rack ball (conf 0.9) hide the real ball
            # (conf 0.79-0.92) for the entreno_7 f244 set.
            self.logger.debug(f"Ball detection: {len(detections)} balls")
            return detections

        except Exception as e:
            self.logger.error(f"Ball detection failed: {e}")
            return []

    def _static_persist(self, center: List[float]) -> float:
        """Return how stationary ``center`` is: the fraction of the rolling
        window's frames that contain a detection within ``static_radius`` of
        it. A ball in play moves every frame, so its neighbourhood count stays
        low; a ball resting on the sand stays put and accumulates hits across
        the whole window.
        """
        n = len(self._recent_centers)
        if n < self.static_min_frames:
            return 0.0
        r2 = self.static_radius ** 2
        cx, cy = center
        hits = 0
        for frame_centers in self._recent_centers:
            for (ox, oy) in frame_centers:
                if (ox - cx) ** 2 + (oy - cy) ** 2 <= r2:
                    hits += 1
                    break
        return hits / n

    def reset(self) -> None:
        """Clear rolling static-suppression history (call between videos)."""
        self._recent_centers.clear()

    def pop_diag(self) -> List[Dict[str, Any]]:
        """Take the diagnostic mirror of the last frame's candidates.

        Empty unless :attr:`diag_enabled` was set by FrameProcessor; the caller
        (FrameProcessor) is the only consumer, and only when diag is on.
        """
        dets, self._diag_dets = self._diag_dets, []
        return dets

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
