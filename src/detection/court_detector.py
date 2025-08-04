"""
Court detection module for volleyball video analysis.

This module implements court boundary detection to filter out players
and actions that occur outside the volleyball court area.
"""

from typing import List, Tuple, Optional, Dict, Any
import cv2
import numpy as np
import logging
from scipy import ndimage
from .yolo_court_detector import YoloCourtDetector


class CourtDetector:
    """Detects volleyball court boundaries to define the region of interest.

    Uses configurable geometric assumptions or computer vision techniques
    to identify the court boundaries and create a mask for filtering detections.
    """

    def __init__(self, config: Dict[str, Any], debug_mode: bool = False):
        """Initialize the court detector.

        Args:
            config: Configuration dictionary with court detection settings
            debug_mode: Enable debug visualizations
        """
        self.config = config
        self.debug_mode = debug_mode
        self.logger = logging.getLogger(__name__)

        # Court detection parameters from config
        self.detection_method = config.get("court_detection_method", "yolo")  # Default to YOLO
        self.court_height_ratio = config.get("court_height_ratio", 0.6)
        self.court_width_ratio = config.get("court_width_ratio", 0.8)
        self.court_vertical_offset = config.get("court_vertical_offset", 0.2)
        self.court_horizontal_center = config.get("court_horizontal_center", 0.5)
        self.court_margin = config.get("court_margin", 0.05)
        self.use_adaptive_court = config.get("use_adaptive_court", True)
        self.court_yolo_only_start = config.get("court_yolo_only_start", True)

        # YOLO court detection parameters
        self.yolo_model_path = config.get("court_model_path", "weights/court/court_best.pt")
        self.yolo_confidence = config.get("court_confidence", 0.5)
        self.yolo_device = config.get("device", "auto")

        # Perspective correction parameters
        self.perspective_enabled = config.get("court_perspective_enabled", True)
        self.perspective_top_width = config.get("court_perspective_top_width", 0.6)
        self.perspective_bottom_width = config.get("court_perspective_bottom_width", 0.8)
        self.perspective_skew = config.get("court_perspective_skew", 0.0)
        self.perspective_depth = config.get("court_perspective_depth", 0.15)

        # Court state
        self.court_mask = None
        self.court_bounds = None
        self.frame_dimensions = None
        self.adaptive_bounds = None

        # Player position history for adaptive court
        self.player_positions_history = []
        
        # Frame counting for YOLO-only-start mode
        self.frame_count = 0
        self.cached_court_mask = None
        self.cached_court_bounds = None
        self.yolo_detection_frames = 10  # Number of frames to run YOLO detection

        # Initialize YOLO court detector
        self.yolo_detector = None
        if self.detection_method == "yolo":
            try:
                self.yolo_detector = YoloCourtDetector(
                    model_path=self.yolo_model_path,
                    confidence_threshold=self.yolo_confidence,
                    device=self.yolo_device
                )
                if self.yolo_detector.is_model_loaded():
                    self.logger.info(f"YOLO court detector loaded successfully: {self.yolo_model_path}")
                else:
                    self.logger.warning("YOLO model not available, falling back to geometric detection")
                    self.detection_method = "geometric"
            except Exception as e:
                self.logger.error(f"Failed to initialize YOLO court detector: {e}")
                self.detection_method = "geometric"

        self.logger.info(f"Court detector initialized: method={self.detection_method}, "
                        f"height_ratio={self.court_height_ratio}, width_ratio={self.court_width_ratio}")

    def detect_court(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Detect the volleyball court in the frame.

        Args:
            frame: Input video frame

        Returns:
            Binary mask of the court area, or None if detection failed
        """
        self.frame_dimensions = frame.shape[:2]  # (height, width)
        self.frame_count += 1

        if self.detection_method == "yolo" and self.yolo_detector is not None:
            return self._detect_court_yolo(frame)
        elif self.detection_method == "geometric":
            return self._detect_court_geometric(frame)
        else:
            # Fallback to original vision-based method
            return self._detect_court_vision_based(frame)

    def _detect_court_yolo(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Detect court using YOLO11 model.

        Args:
            frame: Input video frame

        Returns:
            Binary mask of the court area or None if detection failed
        """
        # If court_yolo_only_start is enabled and we have cached results, use them
        if (self.court_yolo_only_start and 
            self.frame_count > self.yolo_detection_frames and 
            self.cached_court_mask is not None):
            
            self.logger.debug(f"Using cached YOLO court detection (frame {self.frame_count})")
            self.court_mask = self.cached_court_mask
            self.court_bounds = self.cached_court_bounds
            return self.cached_court_mask
        
        try:
            detection = self.yolo_detector.detect_court(frame)
            
            if detection is None:
                self.logger.debug("YOLO court detection failed, falling back to geometric")
                return self._detect_court_geometric(frame)
            
            # Extract court mask
            court_mask = detection.get('mask')
            if court_mask is None:
                self.logger.debug("No mask from YOLO detection, falling back to geometric")
                return self._detect_court_geometric(frame)
            
            # Store detection results for other methods to use
            self.court_bounds = detection.get('bbox')
            self.court_mask = court_mask
            
            # Apply margin if specified
            if self.court_margin > 0:
                h, w = frame.shape[:2]
                margin_pixels = int(min(h, w) * self.court_margin)
                kernel = np.ones((margin_pixels * 2, margin_pixels * 2), np.uint8)
                court_mask = cv2.dilate(court_mask, kernel, iterations=1)
                self.court_mask = court_mask
            
            # Cache the results if we're in the initial detection phase
            if (self.court_yolo_only_start and 
                self.frame_count <= self.yolo_detection_frames):
                self.cached_court_mask = court_mask.copy()
                self.cached_court_bounds = self.court_bounds
                self.logger.debug(f"Cached YOLO court detection for frame {self.frame_count}")
            
            confidence = detection.get('confidence', 0.0)
            self.logger.debug(f"YOLO court detected with confidence: {confidence:.3f}")
            
            return court_mask
            
        except Exception as e:
            self.logger.error(f"YOLO court detection error: {e}")
            return self._detect_court_geometric(frame)

    def _detect_court_geometric(self, frame: np.ndarray) -> np.ndarray:
        """Detect court using geometric assumptions with perspective correction.

        Args:
            frame: Input video frame

        Returns:
            Binary mask of the court area
        """
        h, w = frame.shape[:2]

        if self.perspective_enabled:
            return self._detect_court_with_perspective(frame)
        else:
            return self._detect_court_rectangular(frame)

    def _detect_court_rectangular(self, frame: np.ndarray) -> np.ndarray:
        """Detect court using simple rectangular bounds (no perspective).

        Args:
            frame: Input video frame

        Returns:
            Binary mask of the court area
        """
        h, w = frame.shape[:2]

        # Calculate court boundaries based on configuration
        court_height = int(h * self.court_height_ratio)
        court_width = int(w * self.court_width_ratio)

        # Vertical positioning
        court_top = int(h * self.court_vertical_offset)
        court_bottom = court_top + court_height

        # Horizontal positioning (centered)
        court_center_x = int(w * self.court_horizontal_center)
        court_left = court_center_x - court_width // 2
        court_right = court_left + court_width

        # Ensure bounds are within frame
        court_left = max(0, court_left)
        court_right = min(w, court_right)
        court_top = max(0, court_top)
        court_bottom = min(h, court_bottom)

        # Store court bounds
        self.court_bounds = (court_left, court_top, court_right, court_bottom)

        # Create binary mask
        court_mask = np.zeros((h, w), dtype=np.uint8)
        court_mask[court_top:court_bottom, court_left:court_right] = 255

        # Apply margin if specified
        if self.court_margin > 0:
            margin_pixels = int(min(h, w) * self.court_margin)
            kernel = np.ones((margin_pixels * 2, margin_pixels * 2), np.uint8)
            court_mask = cv2.dilate(court_mask, kernel, iterations=1)

        self.court_mask = court_mask

        self.logger.debug(f"Rectangular court detected: bounds=({court_left}, {court_top}, {court_right}, {court_bottom})")
        return court_mask

    def _detect_court_with_perspective(self, frame: np.ndarray) -> np.ndarray:
        """Detect court using perspective-aware geometric assumptions.

        Args:
            frame: Input video frame

        Returns:
            Binary mask of the court area
        """
        h, w = frame.shape[:2]

        # Calculate basic court positioning
        court_height = int(h * self.court_height_ratio)
        court_top = int(h * self.court_vertical_offset)
        court_bottom = court_top + court_height

        # Calculate perspective-adjusted widths
        top_width = int(w * self.perspective_top_width)
        bottom_width = int(w * self.perspective_bottom_width)

        # Calculate horizontal center with skew
        base_center_x = int(w * self.court_horizontal_center)

        # Apply perspective depth effect (court appears to recede into distance)
        depth_offset = int(h * self.perspective_depth)
        perspective_top = max(0, court_top - depth_offset)
        perspective_bottom = min(h, court_bottom + depth_offset)

        # Create trapezoid points for perspective court
        # Top of court (far end) - narrower
        top_skew = int(w * self.perspective_skew)
        top_left = base_center_x - top_width // 2 + top_skew
        top_right = base_center_x + top_width // 2 + top_skew

        # Bottom of court (near end) - wider
        bottom_left = base_center_x - bottom_width // 2
        bottom_right = base_center_x + bottom_width // 2

        # Ensure bounds are within frame
        top_left = max(0, min(w, top_left))
        top_right = max(0, min(w, top_right))
        bottom_left = max(0, min(w, bottom_left))
        bottom_right = max(0, min(w, bottom_right))

        # Store court bounds (use bottom bounds as main bounds for compatibility)
        self.court_bounds = (bottom_left, court_top, bottom_right, court_bottom)

        # Create perspective court mask using polygon
        court_mask = np.zeros((h, w), dtype=np.uint8)

        # Define trapezoid points (clockwise from top-left)
        court_points = np.array([
            [top_left, perspective_top],      # Top-left (far)
            [top_right, perspective_top],     # Top-right (far)
            [bottom_right, perspective_bottom], # Bottom-right (near)
            [bottom_left, perspective_bottom]   # Bottom-left (near)
        ], dtype=np.int32)

        # Fill the trapezoid
        cv2.fillPoly(court_mask, [court_points], 255)

        # Apply margin if specified
        if self.court_margin > 0:
            margin_pixels = int(min(h, w) * self.court_margin)
            kernel = np.ones((margin_pixels * 2, margin_pixels * 2), np.uint8)
            court_mask = cv2.dilate(court_mask, kernel, iterations=1)

        self.court_mask = court_mask

        # Store perspective points for visualization
        self.perspective_points = court_points

        self.logger.debug(f"Perspective court detected: top_width={top_width}, bottom_width={bottom_width}, skew={top_skew}")
        return court_mask

    def update_adaptive_court(self, player_detections: List[Dict[str, Any]]) -> None:
        """Update court boundaries based on player positions (adaptive mode).

        Args:
            player_detections: List of player detection dictionaries
        """
        if not self.use_adaptive_court or not player_detections:
            return

        # Extract player centers
        player_centers = []
        for detection in player_detections:
            bbox = detection.get("bbox", [])
            if len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                player_centers.append((center_x, center_y))

        if not player_centers:
            return

        # Add to history (keep last 50 positions)
        self.player_positions_history.extend(player_centers)
        if len(self.player_positions_history) > 50:
            self.player_positions_history = self.player_positions_history[-50:]

        # Calculate adaptive bounds if we have enough data
        if len(self.player_positions_history) >= 10:
            positions = np.array(self.player_positions_history)

            # Calculate bounding box of all player positions
            min_x, min_y = np.min(positions, axis=0)
            max_x, max_y = np.max(positions, axis=0)

            # Add some padding
            h, w = self.frame_dimensions
            padding_x = w * 0.1  # 10% padding
            padding_y = h * 0.1

            adaptive_left = max(0, int(min_x - padding_x))
            adaptive_right = min(w, int(max_x + padding_x))
            adaptive_top = max(0, int(min_y - padding_y))
            adaptive_bottom = min(h, int(max_y + padding_y))

            self.adaptive_bounds = (adaptive_left, adaptive_top, adaptive_right, adaptive_bottom)

            self.logger.debug(f"Adaptive court updated: bounds=({adaptive_left}, {adaptive_top}, {adaptive_right}, {adaptive_bottom})")

    def filter_detections_by_court(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter detections to only include those within the court.

        Args:
            detections: List of detection dictionaries

        Returns:
            Filtered detections
        """
        if self.court_mask is None and self.adaptive_bounds is None:
            return detections  # No filtering if court not detected

        filtered_detections = []

        for detection in detections:
            bbox = detection.get("bbox", [])
            if len(bbox) != 4:
                continue

            x1, y1, x2, y2 = bbox
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2

            # Check geometric court bounds
            in_geometric_court = self._is_point_in_geometric_court((center_x, center_y))

            # Check adaptive court bounds if available
            in_adaptive_court = True
            if self.adaptive_bounds and self.use_adaptive_court:
                in_adaptive_court = self._is_point_in_adaptive_court((center_x, center_y))

            # Include detection if it's in either court area
            if in_geometric_court or in_adaptive_court:
                filtered_detections.append(detection)
            else:
                self.logger.debug(f"Filtered out detection at ({center_x:.1f}, {center_y:.1f}) - outside court")

        return filtered_detections

    def _is_point_in_geometric_court(self, point: Tuple[float, float]) -> bool:
        """Check if a point is within the geometric court area.

        Args:
            point: (x, y) coordinates

        Returns:
            True if point is in geometric court
        """
        if self.court_mask is None:
            return True

        x, y = point
        h, w = self.court_mask.shape

        # Check bounds
        if x < 0 or x >= w or y < 0 or y >= h:
            return False

        # Use the mask for accurate point-in-polygon detection
        return self.court_mask[int(y), int(x)] > 0

    def _is_point_in_adaptive_court(self, point: Tuple[float, float]) -> bool:
        """Check if a point is within the adaptive court area.

        Args:
            point: (x, y) coordinates

        Returns:
            True if point is in adaptive court
        """
        if self.adaptive_bounds is None:
            return True

        x, y = point
        left, top, right, bottom = self.adaptive_bounds

        return left <= x <= right and top <= y <= bottom

    def is_point_in_court(self, point: Tuple[int, int]) -> bool:
        """Check if a point is within any detected court area.

        Args:
            point: (x, y) coordinates

        Returns:
            True if point is in court
        """
        # If we have YOLO detection, use the court mask for precise point checking
        if (self.detection_method == "yolo" and self.yolo_detector is not None 
            and self.court_mask is not None):
            x, y = point
            h, w = self.court_mask.shape
            if 0 <= x < w and 0 <= y < h:
                return self.court_mask[y, x] > 0
            return False
        
        # Fallback to geometric and adaptive court checking
        return (self._is_point_in_geometric_court(point) or
                self._is_point_in_adaptive_court(point))

    def draw_court_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Draw court boundary overlay on frame for debugging.

        Args:
            frame: Input frame

        Returns:
            Frame with court overlay
        """
        overlay = frame.copy()
        h, w = frame.shape[:2]

        # Draw court mask as semi-transparent overlay
        if self.court_mask is not None:
            court_colored = np.zeros_like(frame)
            
            # Use different colors based on detection method
            if self.detection_method == "yolo":
                court_colored[:, :, 0] = self.court_mask  # Blue channel for YOLO
            else:
                court_colored[:, :, 1] = self.court_mask  # Green channel for geometric

            # Blend with original frame
            alpha = 0.2
            cv2.addWeighted(overlay, 1 - alpha, court_colored, alpha, 0, overlay)

        # Draw perspective court boundary if available
        if hasattr(self, 'perspective_points') and self.perspective_enabled:
            cv2.polylines(overlay, [self.perspective_points], True, (0, 255, 0), 3)

            # Add perspective info
            perspective_info = f"Perspective: {self.perspective_top_width:.1%} → {self.perspective_bottom_width:.1%}"
            if self.perspective_skew != 0:
                perspective_info += f" | Skew: {self.perspective_skew:+.2f}"
            cv2.putText(overlay, perspective_info, (10, 140),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Draw rectangular court bounds if not using perspective
        elif self.court_bounds:
            left, top, right, bottom = self.court_bounds
            cv2.rectangle(overlay, (left, top), (right, bottom), (0, 255, 0), 3)

            # Add court info text
            court_info = f"Rectangular Court: {self.court_width_ratio:.1%}x{self.court_height_ratio:.1%}"
            cv2.putText(overlay, court_info, (left, top - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Draw adaptive court bounds if available
        if self.adaptive_bounds and self.use_adaptive_court:
            left, top, right, bottom = self.adaptive_bounds

            # Cyan boundary for adaptive court
            cv2.rectangle(overlay, (left, top), (right, bottom), (255, 255, 0), 2)

            # Add adaptive court info
            adaptive_info = f"Adaptive Court (based on {len(self.player_positions_history)} positions)"
            cv2.putText(overlay, adaptive_info, (left, bottom + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # Add YOLO detection info if applicable
        if self.detection_method == "yolo" and self.yolo_detector is not None:
            yolo_info = f"YOLO Court Detection"
            if self.yolo_detector.is_model_loaded():
                confidence = self.yolo_detector.get_detection_confidence()
                yolo_info += f" | Confidence: {confidence:.2f}"
                
                # Add cached detection info
                if (self.court_yolo_only_start and 
                    self.frame_count > self.yolo_detection_frames and 
                    self.cached_court_mask is not None):
                    yolo_info += f" | CACHED (Frame {self.frame_count})"
                    color = (0, 255, 255)  # Yellow for cached
                elif self.court_yolo_only_start and self.frame_count <= self.yolo_detection_frames:
                    yolo_info += f" | DETECTING ({self.frame_count}/{self.yolo_detection_frames})"
                    color = (255, 0, 0)  # Blue for detecting
                else:
                    color = (255, 0, 0)  # Blue for YOLO
            else:
                yolo_info += " | Model Not Loaded"
                color = (0, 0, 255)  # Red for error
            
            cv2.putText(overlay, yolo_info, (10, 100),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Add configuration info
        config_text = f"Method: {self.detection_method} | Perspective: {'ON' if self.perspective_enabled else 'OFF'} | Margin: {self.court_margin:.1%}"
        cv2.putText(overlay, config_text, (10, 120),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return overlay

    def get_court_statistics(self) -> Dict[str, Any]:
        """Get statistics about the detected court.

        Returns:
            Dictionary with court statistics
        """
        stats = {
            "court_detected": self.court_bounds is not None,
            "detection_method": self.detection_method,
            "court_bounds": self.court_bounds,
            "adaptive_bounds": self.adaptive_bounds,
            "use_adaptive": self.use_adaptive_court,
            "player_history_count": len(self.player_positions_history) if self.player_positions_history else 0
        }

        # Add YOLO-specific statistics
        if self.detection_method == "yolo" and self.yolo_detector is not None:
            yolo_stats = self.yolo_detector.get_model_info()
            stats.update({
                "yolo_model_loaded": self.yolo_detector.is_model_loaded(),
                "yolo_model_path": yolo_stats.get("model_path"),
                "yolo_confidence_threshold": yolo_stats.get("confidence_threshold"),
                "yolo_device": yolo_stats.get("device"),
                "yolo_detection_confidence": self.yolo_detector.get_detection_confidence(),
                "court_yolo_only_start": self.court_yolo_only_start,
                "yolo_detection_frames": self.yolo_detection_frames,
                "current_frame_count": self.frame_count,
                "using_cached_detection": (self.court_yolo_only_start and 
                                         self.frame_count > self.yolo_detection_frames and 
                                         self.cached_court_mask is not None)
            })

        if self.court_bounds and self.frame_dimensions:
            left, top, right, bottom = self.court_bounds
            h, w = self.frame_dimensions
            court_area = (right - left) * (bottom - top)
            total_area = h * w

            stats.update({
                "court_area_pixels": int(court_area),
                "court_area_ratio": float(court_area / total_area),
                "configured_height_ratio": self.court_height_ratio,
                "configured_width_ratio": self.court_width_ratio,
                "vertical_offset": self.court_vertical_offset,
                "horizontal_center": self.court_horizontal_center
            })

        return stats
