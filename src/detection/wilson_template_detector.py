"""
Wilson Volleyball Template-Based Detection - Approach 1

This module implements enhanced template matching for Wilson volleyball detection
using multi-scale, rotation-invariant matching with color space analysis.
"""

import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import math


class WilsonTemplateDetector:
    """
    Enhanced template matching detector for Wilson volleyballs.
    
    Uses multiple reference templates with multi-scale matching,
    color space analysis, and confidence scoring.
    """

    def __init__(
        self,
        template_dir: str = "resources/wilson_ball",
        confidence_threshold: float = 0.6,
        scales: List[float] = None,
        match_methods: List[int] = None
    ):
        """
        Initialize Wilson template detector.

        Args:
            template_dir: Directory containing Wilson ball reference images
            confidence_threshold: Minimum confidence for detection
            scales: Scales to test for template matching
            match_methods: OpenCV template matching methods to use
        """
        self.template_dir = Path(template_dir)
        self.confidence_threshold = confidence_threshold
        self.scales = scales or [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5]
        self.match_methods = match_methods or [cv2.TM_CCOEFF_NORMED, cv2.TM_CCORR_NORMED]
        
        self.logger = logging.getLogger(__name__)
        
        # Load and preprocess templates
        self.templates = []
        self.templates_hsv = []
        self.templates_gray = []
        
        self._load_templates()
        
        # Wilson ball color ranges in HSV
        # Yellow range (primary color)
        self.yellow_lower = np.array([20, 100, 100])
        self.yellow_upper = np.array([30, 255, 255])
        
        # Orange/Red range (accent color)
        self.orange_lower = np.array([10, 150, 150])
        self.orange_upper = np.array([20, 255, 255])

    def _load_templates(self) -> None:
        """Load Wilson ball template images."""
        template_files = list(self.template_dir.glob("*.png")) + \
                        list(self.template_dir.glob("*.jpg"))
        
        for template_path in template_files:
            try:
                # Load original template
                template = cv2.imread(str(template_path))
                if template is not None:
                    self.templates.append(template)
                    
                    # Convert to HSV and grayscale
                    template_hsv = cv2.cvtColor(template, cv2.COLOR_BGR2HSV)
                    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                    
                    self.templates_hsv.append(template_hsv)
                    self.templates_gray.append(template_gray)
                    
            except Exception as e:
                self.logger.warning(f"Failed to load template {template_path}: {e}")
        
        self.logger.info(f"Loaded {len(self.templates)} Wilson ball templates")

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect Wilson volleyball in frame using template matching.

        Args:
            frame: Input video frame

        Returns:
            List of detection dictionaries
        """
        if len(self.templates) == 0:
            return []

        # Convert frame to different color spaces
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Pre-filter frame using Wilson ball colors
        color_mask = self._create_color_mask(frame_hsv)
        
        # Find potential regions using color filtering
        contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours by size and shape
        ball_regions = self._filter_ball_regions(contours, frame.shape)
        
        detections = []
        
        # For each potential region, perform template matching
        for region in ball_regions:
            x, y, w, h = region
            
            # Expand region slightly
            expand = 20
            x = max(0, x - expand)
            y = max(0, y - expand)
            w = min(frame.shape[1] - x, w + 2 * expand)
            h = min(frame.shape[0] - y, h + 2 * expand)
            
            roi = frame[y:y+h, x:x+w]
            roi_gray = frame_gray[y:y+h, x:x+w]
            
            # Perform multi-scale template matching on ROI
            best_match = self._multi_scale_template_match(roi, roi_gray, (x, y))
            
            if best_match and best_match['confidence'] >= self.confidence_threshold:
                detections.append(best_match)
        
        # Non-maximum suppression to remove overlapping detections
        final_detections = self._non_max_suppression(detections)
        
        return final_detections

    def _create_color_mask(self, frame_hsv: np.ndarray) -> np.ndarray:
        """Create color mask for Wilson ball colors."""
        # Create mask for yellow (primary ball color)
        yellow_mask = cv2.inRange(frame_hsv, self.yellow_lower, self.yellow_upper)
        
        # Create mask for orange/red (accent colors)
        orange_mask = cv2.inRange(frame_hsv, self.orange_lower, self.orange_upper)
        
        # Combine masks
        color_mask = cv2.bitwise_or(yellow_mask, orange_mask)
        
        # Apply morphological operations to clean up mask
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_CLOSE, kernel)
        color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_OPEN, kernel)
        
        return color_mask

    def _filter_ball_regions(self, contours: List, frame_shape: Tuple) -> List[Tuple[int, int, int, int]]:
        """Filter contours to find potential ball regions."""
        ball_regions = []
        
        for contour in contours:
            # Calculate bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by size (reasonable ball sizes)
            area = w * h
            frame_area = frame_shape[0] * frame_shape[1]
            
            if area < 100 or area > frame_area * 0.1:  # Too small or too large
                continue
            
            # Filter by aspect ratio (balls should be roughly circular)
            aspect_ratio = w / h
            if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                continue
            
            # Filter by contour area vs bounding box area (circularity check)
            contour_area = cv2.contourArea(contour)
            if contour_area < area * 0.3:  # Too sparse
                continue
            
            ball_regions.append((x, y, w, h))
        
        return ball_regions

    def _multi_scale_template_match(
        self, 
        roi: np.ndarray, 
        roi_gray: np.ndarray, 
        offset: Tuple[int, int]
    ) -> Optional[Dict[str, Any]]:
        """
        Perform multi-scale template matching on ROI.

        Args:
            roi: Region of interest (color)
            roi_gray: Region of interest (grayscale)
            offset: Offset of ROI in original frame

        Returns:
            Best match dictionary or None
        """
        best_match = None
        best_confidence = 0
        
        for template_idx, (template, template_gray) in enumerate(zip(self.templates, self.templates_gray)):
            for scale in self.scales:
                # Resize template
                template_h, template_w = template.shape[:2]
                new_w = int(template_w * scale)
                new_h = int(template_h * scale)
                
                if new_w > roi.shape[1] or new_h > roi.shape[0]:
                    continue
                
                scaled_template = cv2.resize(template_gray, (new_w, new_h))
                
                # Template matching with multiple methods
                for method in self.match_methods:
                    try:
                        result = cv2.matchTemplate(roi_gray, scaled_template, method)
                        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                        
                        # Use max_val for TM_CCOEFF_NORMED and TM_CCORR_NORMED
                        confidence = max_val
                        match_loc = max_loc
                        
                        if confidence > best_confidence:
                            # Calculate absolute position
                            abs_x = offset[0] + match_loc[0]
                            abs_y = offset[1] + match_loc[1]
                            center_x = abs_x + new_w // 2
                            center_y = abs_y + new_h // 2
                            
                            # Additional validation using color information
                            color_score = self._validate_color_match(roi, match_loc, (new_w, new_h))
                            
                            # Combined confidence score
                            combined_confidence = confidence * 0.7 + color_score * 0.3
                            
                            if combined_confidence > best_confidence:
                                best_confidence = combined_confidence
                                best_match = {
                                    'center': [center_x, center_y],
                                    'bbox': [abs_x, abs_y, abs_x + new_w, abs_y + new_h],
                                    'confidence': combined_confidence,
                                    'method': f'template_{template_idx}_scale_{scale:.1f}',
                                    'template_size': (new_w, new_h)
                                }
                    
                    except Exception as e:
                        self.logger.debug(f"Template matching failed: {e}")
                        continue
        
        return best_match

    def _validate_color_match(
        self, 
        roi: np.ndarray, 
        match_loc: Tuple[int, int], 
        template_size: Tuple[int, int]
    ) -> float:
        """
        Validate match using color information.

        Args:
            roi: Region of interest
            match_loc: Match location within ROI
            template_size: Size of matched template

        Returns:
            Color match score (0-1)
        """
        try:
            x, y = match_loc
            w, h = template_size
            
            # Extract matched region
            matched_region = roi[y:y+h, x:x+w]
            
            if matched_region.size == 0:
                return 0.0
            
            # Convert to HSV
            matched_hsv = cv2.cvtColor(matched_region, cv2.COLOR_BGR2HSV)
            
            # Check for Wilson ball colors
            yellow_pixels = cv2.inRange(matched_hsv, self.yellow_lower, self.yellow_upper)
            orange_pixels = cv2.inRange(matched_hsv, self.orange_lower, self.orange_upper)
            
            total_pixels = matched_region.shape[0] * matched_region.shape[1]
            yellow_ratio = np.sum(yellow_pixels > 0) / total_pixels
            orange_ratio = np.sum(orange_pixels > 0) / total_pixels
            
            # Wilson balls should have significant yellow and some orange
            color_score = min(1.0, yellow_ratio * 2 + orange_ratio)
            
            return color_score
            
        except Exception as e:
            self.logger.debug(f"Color validation failed: {e}")
            return 0.0

    def _non_max_suppression(
        self, 
        detections: List[Dict[str, Any]], 
        iou_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Apply non-maximum suppression to remove overlapping detections."""
        if not detections:
            return []
        
        # Sort by confidence
        detections = sorted(detections, key=lambda x: x['confidence'], reverse=True)
        
        keep = []
        while detections:
            # Keep the highest confidence detection
            current = detections.pop(0)
            keep.append(current)
            
            # Remove overlapping detections
            remaining = []
            for det in detections:
                iou = self._calculate_iou(current['bbox'], det['bbox'])
                if iou < iou_threshold:
                    remaining.append(det)
            
            detections = remaining
        
        return keep

    def _calculate_iou(self, box1: List[int], box2: List[int]) -> float:
        """Calculate Intersection over Union (IoU) of two bounding boxes."""
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