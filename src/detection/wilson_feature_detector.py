"""
Wilson Volleyball Feature-Based Detection - Approach 2

This module implements feature-based detection for Wilson volleyball using
SIFT/ORB features with robust matching and geometric verification.
"""

import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
from collections import defaultdict


class WilsonFeatureDetector:
    """
    Feature-based detector for Wilson volleyballs.
    
    Uses SIFT and ORB features with robust matching algorithms,
    geometric verification, and multi-reference matching.
    """

    def __init__(
        self,
        template_dir: str = "resources/wilson_ball",
        confidence_threshold: float = 0.5,
        min_match_count: int = 8,
        use_sift: bool = True,
        use_orb: bool = True
    ):
        """
        Initialize Wilson feature detector.

        Args:
            template_dir: Directory containing Wilson ball reference images
            confidence_threshold: Minimum confidence for detection
            min_match_count: Minimum number of feature matches required
            use_sift: Whether to use SIFT features
            use_orb: Whether to use ORB features
        """
        self.template_dir = Path(template_dir)
        self.confidence_threshold = confidence_threshold
        self.min_match_count = min_match_count
        self.use_sift = use_sift
        self.use_orb = use_orb
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize feature detectors
        self.detectors = {}
        self.matchers = {}
        
        if self.use_sift:
            try:
                self.detectors['sift'] = cv2.SIFT_create()
                self.matchers['sift'] = cv2.FlannBasedMatcher()
                self.logger.info("SIFT detector initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize SIFT: {e}")
                self.use_sift = False
        
        if self.use_orb:
            try:
                self.detectors['orb'] = cv2.ORB_create(nfeatures=1000)
                # Use BFMatcher for ORB (binary descriptors)
                self.matchers['orb'] = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                self.logger.info("ORB detector initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize ORB: {e}")
                self.use_orb = False
        
        # Reference features storage
        self.reference_features = defaultdict(list)  # {detector_name: [feature_data]}
        
        self._extract_reference_features()

    def _extract_reference_features(self) -> None:
        """Extract features from Wilson ball reference images."""
        template_files = list(self.template_dir.glob("*.png")) + \
                        list(self.template_dir.glob("*.jpg"))
        
        for template_path in template_files:
            try:
                img = cv2.imread(str(template_path))
                if img is None:
                    continue
                
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                # Extract features with each detector
                for detector_name, detector in self.detectors.items():
                    try:
                        if detector_name == 'sift':
                            keypoints, descriptors = detector.detectAndCompute(gray, None)
                        else:  # ORB
                            keypoints, descriptors = detector.detectAndCompute(gray, None)
                        
                        if descriptors is not None and len(keypoints) > 0:
                            self.reference_features[detector_name].append({
                                'keypoints': keypoints,
                                'descriptors': descriptors,
                                'image_shape': gray.shape,
                                'template_path': str(template_path)
                            })
                            
                            self.logger.debug(
                                f"Extracted {len(keypoints)} {detector_name} features from {template_path.name}"
                            )
                    
                    except Exception as e:
                        self.logger.warning(f"Feature extraction failed for {detector_name}: {e}")
            
            except Exception as e:
                self.logger.warning(f"Failed to process template {template_path}: {e}")
        
        total_refs = sum(len(refs) for refs in self.reference_features.values())
        self.logger.info(f"Extracted features from {total_refs} reference images")

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect Wilson volleyball using feature matching.

        Args:
            frame: Input video frame

        Returns:
            List of detection dictionaries
        """
        if not self.reference_features:
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        all_detections = []
        
        # Try each feature detector
        for detector_name, detector in self.detectors.items():
            try:
                # Extract features from current frame
                keypoints, descriptors = detector.detectAndCompute(gray, None)
                
                if descriptors is None or len(keypoints) < self.min_match_count:
                    continue
                
                # Match against all reference images for this detector
                detector_detections = self._match_features(
                    detector_name, keypoints, descriptors, frame.shape[:2]
                )
                
                all_detections.extend(detector_detections)
                
            except Exception as e:
                self.logger.debug(f"Feature detection failed for {detector_name}: {e}")
        
        # Combine and filter detections
        final_detections = self._merge_detections(all_detections)
        
        return final_detections

    def _match_features(
        self,
        detector_name: str,
        query_keypoints: List,
        query_descriptors: np.ndarray,
        frame_shape: Tuple[int, int]
    ) -> List[Dict[str, Any]]:
        """
        Match features against reference images.

        Args:
            detector_name: Name of the feature detector used
            query_keypoints: Keypoints from query image
            query_descriptors: Descriptors from query image
            frame_shape: Shape of the frame (height, width)

        Returns:
            List of detection candidates
        """
        detections = []
        matcher = self.matchers[detector_name]
        
        for ref_data in self.reference_features[detector_name]:
            try:
                ref_descriptors = ref_data['descriptors']
                ref_keypoints = ref_data['keypoints']
                
                # Perform matching
                if detector_name == 'sift':
                    # FLANN matching for SIFT
                    if len(ref_descriptors) < 2:
                        continue
                    
                    matches = matcher.knnMatch(ref_descriptors, query_descriptors, k=2)
                    
                    # Apply Lowe's ratio test
                    good_matches = []
                    for match_pair in matches:
                        if len(match_pair) == 2:
                            m, n = match_pair
                            if m.distance < 0.7 * n.distance:
                                good_matches.append(m)
                else:
                    # BF matching for ORB
                    matches = matcher.match(ref_descriptors, query_descriptors)
                    
                    # Sort by distance and take best matches
                    matches = sorted(matches, key=lambda x: x.distance)
                    good_matches = matches[:min(50, len(matches))]
                    
                    # Filter by distance threshold
                    good_matches = [m for m in good_matches if m.distance < 50]
                
                if len(good_matches) >= self.min_match_count:
                    # Extract matched points
                    ref_pts = np.float32([ref_keypoints[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                    query_pts = np.float32([query_keypoints[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                    
                    # Find homography with RANSAC
                    homography, mask = cv2.findHomography(
                        ref_pts, query_pts, 
                        cv2.RANSAC, 
                        ransacReprojThreshold=5.0
                    )
                    
                    if homography is not None:
                        # Calculate inlier ratio
                        inlier_count = np.sum(mask)
                        inlier_ratio = inlier_count / len(good_matches)
                        
                        if inlier_ratio >= 0.3:  # At least 30% inliers
                            # Transform reference image corners to query image
                            ref_shape = ref_data['image_shape']
                            corners = np.float32([
                                [0, 0], [ref_shape[1], 0], 
                                [ref_shape[1], ref_shape[0]], [0, ref_shape[0]]
                            ]).reshape(-1, 1, 2)
                            
                            transformed_corners = cv2.perspectiveTransform(corners, homography)
                            
                            # Calculate bounding box from transformed corners
                            bbox = self._corners_to_bbox(transformed_corners, frame_shape)
                            
                            if bbox:
                                confidence = self._calculate_feature_confidence(
                                    good_matches, inlier_ratio, len(query_keypoints)
                                )
                                
                                center_x = (bbox[0] + bbox[2]) / 2
                                center_y = (bbox[1] + bbox[3]) / 2
                                
                                detection = {
                                    'center': [center_x, center_y],
                                    'bbox': bbox,
                                    'confidence': confidence,
                                    'method': f'features_{detector_name}',
                                    'match_count': len(good_matches),
                                    'inlier_ratio': inlier_ratio,
                                    'reference': ref_data['template_path']
                                }
                                
                                detections.append(detection)
            
            except Exception as e:
                self.logger.debug(f"Feature matching failed: {e}")
                continue
        
        return detections

    def _corners_to_bbox(
        self, 
        corners: np.ndarray, 
        frame_shape: Tuple[int, int]
    ) -> Optional[List[int]]:
        """
        Convert transformed corners to bounding box.

        Args:
            corners: Transformed corner points
            frame_shape: Shape of the frame (height, width)

        Returns:
            Bounding box [x1, y1, x2, y2] or None if invalid
        """
        try:
            corners = corners.reshape(-1, 2)
            
            # Check if corners form a reasonable quadrilateral
            area = cv2.contourArea(corners)
            if area < 100:  # Too small
                return None
            
            # Calculate bounding box
            x_coords = corners[:, 0]
            y_coords = corners[:, 1]
            
            x1, y1 = np.min(x_coords), np.min(y_coords)
            x2, y2 = np.max(x_coords), np.max(y_coords)
            
            # Clamp to frame boundaries
            x1 = max(0, int(x1))
            y1 = max(0, int(y1))
            x2 = min(frame_shape[1], int(x2))
            y2 = min(frame_shape[0], int(y2))
            
            # Check aspect ratio (should be roughly square for a ball)
            width = x2 - x1
            height = y2 - y1
            
            if width <= 0 or height <= 0:
                return None
            
            aspect_ratio = width / height
            if aspect_ratio < 0.3 or aspect_ratio > 3.0:
                return None
            
            return [x1, y1, x2, y2]
            
        except Exception as e:
            self.logger.debug(f"Corner to bbox conversion failed: {e}")
            return None

    def _calculate_feature_confidence(
        self,
        matches: List,
        inlier_ratio: float,
        total_query_features: int
    ) -> float:
        """
        Calculate confidence score for feature-based detection.

        Args:
            matches: List of good matches
            inlier_ratio: Ratio of inlier matches
            total_query_features: Total number of features in query image

        Returns:
            Confidence score (0-1)
        """
        # Base confidence from number of matches
        match_score = min(1.0, len(matches) / 50.0)  # Normalize to 50 matches
        
        # Inlier ratio contribution
        geometric_score = inlier_ratio
        
        # Feature density score (matches relative to total features)
        density_score = min(1.0, len(matches) / max(1, total_query_features * 0.1))
        
        # Combined confidence
        confidence = (match_score * 0.4 + geometric_score * 0.4 + density_score * 0.2)
        
        return min(1.0, confidence)

    def _merge_detections(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge and filter detections from multiple feature detectors.

        Args:
            detections: List of all detections

        Returns:
            Filtered and merged detections
        """
        if not detections:
            return []
        
        # Filter by confidence threshold
        filtered = [d for d in detections if d['confidence'] >= self.confidence_threshold]
        
        if not filtered:
            return []
        
        # Group nearby detections
        merged = []
        used = set()
        
        for i, det1 in enumerate(filtered):
            if i in used:
                continue
            
            group = [det1]
            used.add(i)
            
            for j, det2 in enumerate(filtered[i+1:], i+1):
                if j in used:
                    continue
                
                # Check if detections overlap significantly
                iou = self._calculate_iou(det1['bbox'], det2['bbox'])
                if iou > 0.3:
                    group.append(det2)
                    used.add(j)
            
            # Merge group into single detection
            if len(group) == 1:
                merged.append(group[0])
            else:
                merged_detection = self._merge_detection_group(group)
                merged.append(merged_detection)
        
        # Sort by confidence and return top detections
        merged.sort(key=lambda x: x['confidence'], reverse=True)
        
        return merged[:3]  # Return top 3 detections max

    def _merge_detection_group(self, group: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge a group of overlapping detections."""
        # Weight by confidence
        total_confidence = sum(d['confidence'] for d in group)
        
        # Weighted average of centers
        center_x = sum(d['center'][0] * d['confidence'] for d in group) / total_confidence
        center_y = sum(d['center'][1] * d['confidence'] for d in group) / total_confidence
        
        # Union of bounding boxes
        all_bboxes = [d['bbox'] for d in group]
        x1 = min(bbox[0] for bbox in all_bboxes)
        y1 = min(bbox[1] for bbox in all_bboxes)
        x2 = max(bbox[2] for bbox in all_bboxes)
        y2 = max(bbox[3] for bbox in all_bboxes)
        
        # Use highest confidence
        best_detection = max(group, key=lambda x: x['confidence'])
        
        merged = {
            'center': [center_x, center_y],
            'bbox': [x1, y1, x2, y2],
            'confidence': best_detection['confidence'],
            'method': f"merged_{len(group)}_detections",
            'match_count': sum(d.get('match_count', 0) for d in group),
            'group_size': len(group)
        }
        
        return merged

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