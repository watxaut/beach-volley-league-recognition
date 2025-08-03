"""
Enhanced ball tracker using multiple tracking methods for volleyball analysis.

This module implements advanced ball tracking using Kalman filters, template matching,
and optical flow to maintain ball continuity throughout volleyball points.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2
from collections import deque
import logging


class EnhancedBallTracker:
    """Enhanced tracker for volleyball ball with multiple tracking methods.

    Combines YOLO detections with Kalman filtering, template matching, and optical flow
    to maintain ball tracking continuity even when detections are missed.
    """

    def __init__(
        self,
        max_missing_frames: int = 45,  # Even longer persistence
        template_update_interval: int = 5,
        optical_flow_quality: float = 0.01,
        kalman_process_noise: float = 0.1,
        kalman_measurement_noise: float = 1.0
    ):
        """Initialize the enhanced ball tracker.

        Args:
            max_missing_frames: Maximum frames ball can be missing before reset
            template_update_interval: How often to update ball template
            optical_flow_quality: Quality level for optical flow feature detection
            kalman_process_noise: Process noise for Kalman filter
            kalman_measurement_noise: Measurement noise for Kalman filter
        """
        self.max_missing_frames = max_missing_frames
        self.template_update_interval = template_update_interval
        self.optical_flow_quality = optical_flow_quality

        # Tracking state
        self.trajectory = deque(maxlen=300)  # Even longer trajectory
        self.missing_count = 0
        self.last_detection_frame = None
        self.frame_count = 0

        # Template matching
        self.ball_template = None
        self.template_update_counter = 0
        self.template_size = 30

        # Kalman filter for smooth tracking
        self.kalman = self._initialize_kalman_filter(kalman_process_noise, kalman_measurement_noise)
        self.kalman_initialized = False

        # Optical flow tracking
        self.optical_flow_points = None
        self.prev_gray = None
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )

        # Multi-method tracking results
        self.detection_methods = {
            'yolo': None,
            'template': None,
            'optical_flow': None,
            'kalman': None
        }

        self.logger = logging.getLogger(__name__)

    def _initialize_kalman_filter(self, process_noise: float, measurement_noise: float) -> cv2.KalmanFilter:
        """Initialize Kalman filter for ball tracking."""
        kalman = cv2.KalmanFilter(4, 2)  # 4 state variables (x, y, vx, vy), 2 measurements (x, y)

        # State transition matrix (constant velocity model)
        kalman.transitionMatrix = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], dtype=np.float32)

        # Measurement matrix
        kalman.measurementMatrix = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], dtype=np.float32)

        # Process noise covariance
        kalman.processNoiseCov = process_noise * np.eye(4, dtype=np.float32)

        # Measurement noise covariance
        kalman.measurementNoiseCov = measurement_noise * np.eye(2, dtype=np.float32)

        # Error covariance
        kalman.errorCovPost = np.eye(4, dtype=np.float32)

        return kalman

    def update(self, detections: List[Dict[str, Any]], frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """Update tracker with new detections and frame.

        Args:
            detections: List of ball detections from YOLO
            frame: Current frame

        Returns:
            Tracked ball with enhanced info, or None if no valid ball
        """
        self.frame_count += 1
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Try multiple detection methods
        self._detect_with_yolo(detections)
        self._detect_with_template_matching(gray_frame)
        self._detect_with_optical_flow(gray_frame)
        self._predict_with_kalman()

        # Combine results from all methods
        best_detection = self._combine_detection_methods(frame)

        if best_detection:
            self._update_tracking_state(best_detection, gray_frame)
            return self._create_enhanced_detection(best_detection)
        else:
            return self._handle_missing_ball()

    def _detect_with_yolo(self, detections: List[Dict[str, Any]]) -> None:
        """Process YOLO detections with improved ball-specific filtering."""
        if detections:
            # Sort by both confidence and area (similar to volleyball_analytics approach)
            sorted_detections = sorted(detections,
                                     key=lambda x: (x.get("confidence", 0), x.get("area", 0)),
                                     reverse=True)

            # Select best detection (highest confidence AND largest area)
            best_detection = sorted_detections[0]

            # Additional validation: ensure detection looks like a ball
            area = best_detection.get("area", 0)
            bbox = best_detection.get("bbox", [])

            # Check aspect ratio (balls should be roughly circular)
            if len(bbox) == 4:
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                aspect_ratio = width / height if height > 0 else 0

                # Ball should have aspect ratio close to 1.0 (circular)
                if 0.5 <= aspect_ratio <= 2.0:  # Allow some tolerance
                    # Preserve original detection data and enhance it
                    enhanced_detection = best_detection.copy()
                    enhanced_detection.update({
                        'confidence': best_detection['confidence'] * 1.3,  # Boost validated detections
                        'area': area,
                        'aspect_ratio': aspect_ratio
                    })
                    self.detection_methods['yolo'] = enhanced_detection
                else:
                    self.detection_methods['yolo'] = None
            else:
                self.detection_methods['yolo'] = None
        else:
            self.detection_methods['yolo'] = None

    def _detect_with_template_matching(self, gray_frame: np.ndarray) -> None:
        """Detect ball using template matching."""
        if self.ball_template is None:
            self.detection_methods['template'] = None
            return

        try:
            # Perform template matching
            result = cv2.matchTemplate(gray_frame, self.ball_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # If match is good enough
            if max_val > 0.6:  # Threshold for template matching
                template_h, template_w = self.ball_template.shape
                center_x = max_loc[0] + template_w // 2
                center_y = max_loc[1] + template_h // 2

                self.detection_methods['template'] = {
                    'center': [center_x, center_y],
                    'confidence': max_val * 0.8,  # Slightly lower confidence than YOLO
                    'method': 'template',
                    'bbox': [max_loc[0], max_loc[1], max_loc[0] + template_w, max_loc[1] + template_h]
                }
            else:
                self.detection_methods['template'] = None

        except Exception as e:
            self.logger.debug(f"Template matching failed: {e}")
            self.detection_methods['template'] = None

    def _detect_with_optical_flow(self, gray_frame: np.ndarray) -> None:
        """Track ball using optical flow."""
        if self.prev_gray is None or self.optical_flow_points is None:
            self.detection_methods['optical_flow'] = None
            self.prev_gray = gray_frame.copy()
            return

        try:
            # Calculate optical flow
            new_points, status, error = cv2.calcOpticalFlowPyrLK(
                self.prev_gray, gray_frame, self.optical_flow_points, None, **self.lk_params
            )

            # Select good points
            good_new = new_points[status == 1]

            if len(good_new) > 0:
                # Use mean of good points as ball center
                center = np.mean(good_new, axis=0)

                # Calculate confidence based on tracking quality
                confidence = min(len(good_new) / len(self.optical_flow_points), 1.0) * 0.7

                self.detection_methods['optical_flow'] = {
                    'center': [float(center[0]), float(center[1])],
                    'confidence': confidence,
                    'method': 'optical_flow',
                    'bbox': self._estimate_bbox_from_center(center)
                }

                # Update points for next frame
                self.optical_flow_points = good_new.reshape(-1, 1, 2)
            else:
                self.detection_methods['optical_flow'] = None
                self.optical_flow_points = None

        except Exception as e:
            self.logger.debug(f"Optical flow tracking failed: {e}")
            self.detection_methods['optical_flow'] = None

        self.prev_gray = gray_frame.copy()

    def _predict_with_kalman(self) -> None:
        """Predict ball position using Kalman filter."""
        if not self.kalman_initialized:
            self.detection_methods['kalman'] = None
            return

        try:
            # Predict next state
            prediction = self.kalman.predict()
            predicted_center = [float(prediction[0]), float(prediction[1])]

            self.detection_methods['kalman'] = {
                'center': predicted_center,
                'confidence': 0.5,  # Medium confidence for predictions
                'method': 'kalman',
                'bbox': self._estimate_bbox_from_center(predicted_center)
            }

        except Exception as e:
            self.logger.debug(f"Kalman prediction failed: {e}")
            self.detection_methods['kalman'] = None

    def _combine_detection_methods(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """Combine results from all detection methods to get best estimate."""
        valid_detections = [det for det in self.detection_methods.values() if det is not None]

        if not valid_detections:
            return None

        # PRIORITIZE YOLO detections - they are most reliable for ball detection
        yolo_detection = self.detection_methods['yolo']
        if yolo_detection and yolo_detection['confidence'] > 0.2:  # Lower threshold but still prioritize YOLO
            return yolo_detection

        # Only use other methods if they have reasonable confidence AND are consistent with recent trajectory
        filtered_detections = []
        for detection in valid_detections:
            # Skip low-confidence non-YOLO detections
            if detection['method'] != 'yolo' and detection['confidence'] < 0.4:
                continue

            # Check if detection is consistent with recent trajectory
            if len(self.trajectory) >= 2:
                last_pos = self.trajectory[-1]
                distance = np.sqrt(
                    (detection['center'][0] - last_pos[0])**2 +
                    (detection['center'][1] - last_pos[1])**2
                )
                # Reject detections too far from recent trajectory (likely false positives)
                if distance > 150:  # Maximum reasonable ball movement per frame
                    continue

            filtered_detections.append(detection)

        if not filtered_detections:
            return None

        # If we have multiple valid detections, use weighted average
        if len(filtered_detections) > 1:
            total_weight = sum(det['confidence'] for det in filtered_detections)
            if total_weight > 0:
                weighted_x = sum(det['center'][0] * det['confidence'] for det in filtered_detections) / total_weight
                weighted_y = sum(det['center'][1] * det['confidence'] for det in filtered_detections) / total_weight
                avg_confidence = total_weight / len(filtered_detections)

                return {
                    'center': [weighted_x, weighted_y],
                    'confidence': avg_confidence,
                    'method': 'combined',
                    'bbox': self._estimate_bbox_from_center([weighted_x, weighted_y])
                }

        # Return the highest confidence detection
        return max(filtered_detections, key=lambda x: x['confidence'])

    def _update_tracking_state(self, detection: Dict[str, Any], gray_frame: np.ndarray) -> None:
        """Update all tracking state with new detection."""
        center = detection['center']

        # Update trajectory
        self.trajectory.append(center)
        self.missing_count = 0

        # Update Kalman filter
        if not self.kalman_initialized:
            # Initialize Kalman filter with first detection
            self.kalman.statePre = np.array([center[0], center[1], 0, 0], dtype=np.float32)
            self.kalman.statePost = np.array([center[0], center[1], 0, 0], dtype=np.float32)
            self.kalman_initialized = True
        else:
            # Update Kalman filter with measurement
            measurement = np.array([[center[0]], [center[1]]], dtype=np.float32)
            self.kalman.correct(measurement)

        # Update template
        if self.template_update_counter % self.template_update_interval == 0:
            self._update_ball_template(gray_frame, center)
        self.template_update_counter += 1

        # Update optical flow points
        self._update_optical_flow_points(gray_frame, center)

    def _update_ball_template(self, gray_frame: np.ndarray, center: List[float]) -> None:
        """Update ball template for template matching."""
        try:
            x, y = int(center[0]), int(center[1])
            half_size = self.template_size // 2

            # Extract template around ball center
            y1, y2 = max(0, y - half_size), min(gray_frame.shape[0], y + half_size)
            x1, x2 = max(0, x - half_size), min(gray_frame.shape[1], x + half_size)

            if y2 - y1 > 10 and x2 - x1 > 10:  # Ensure minimum template size
                self.ball_template = gray_frame[y1:y2, x1:x2].copy()

        except Exception as e:
            self.logger.debug(f"Template update failed: {e}")

    def _update_optical_flow_points(self, gray_frame: np.ndarray, center: List[float]) -> None:
        """Update optical flow tracking points around ball."""
        try:
            x, y = int(center[0]), int(center[1])

            # Create a small region around the ball
            region_size = 20
            y1, y2 = max(0, y - region_size), min(gray_frame.shape[0], y + region_size)
            x1, x2 = max(0, x - region_size), min(gray_frame.shape[1], x + region_size)

            mask = np.zeros_like(gray_frame)
            mask[y1:y2, x1:x2] = 255

            # Detect corners for optical flow tracking
            corners = cv2.goodFeaturesToTrack(
                gray_frame, maxCorners=10, qualityLevel=self.optical_flow_quality,
                minDistance=3, mask=mask
            )

            if corners is not None and len(corners) > 0:
                self.optical_flow_points = corners

        except Exception as e:
            self.logger.debug(f"Optical flow points update failed: {e}")

    def _estimate_bbox_from_center(self, center: List[float], size: int = 20) -> List[float]:
        """Estimate bounding box from center point."""
        x, y = center
        half_size = size // 2
        return [x - half_size, y - half_size, x + half_size, y + half_size]

    def _create_enhanced_detection(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """Create enhanced detection with tracking information."""
        # Calculate velocity from trajectory
        velocity = [0, 0]
        if len(self.trajectory) >= 2:
            prev_pos = self.trajectory[-2]
            curr_pos = detection['center']
            velocity = [curr_pos[0] - prev_pos[0], curr_pos[1] - prev_pos[1]]

        # Start with original detection to preserve all metadata
        enhanced_detection = detection.copy()
        
        # Add or update enhanced tracking information
        enhanced_detection.update({
            'velocity': velocity,
            'trajectory_length': len(self.trajectory),
            'ball_state': self._classify_ball_state(velocity),
            'tracking_method': detection['method'],
            'is_predicted': detection['method'] in ['kalman', 'optical_flow'],
            'missing_frames': self.missing_count,
            'class_name': 'volleyball'
        })
        
        return enhanced_detection

    def _handle_missing_ball(self) -> Optional[Dict[str, Any]]:
        """Handle frame where ball was not detected by any method."""
        self.missing_count += 1

        # If missing for too long, reset tracker
        if self.missing_count > self.max_missing_frames:
            self._reset_tracker()
            return None

        # Try to use Kalman prediction as fallback
        kalman_result = self.detection_methods.get('kalman')
        if kalman_result:
            kalman_result['confidence'] = max(0.1, kalman_result['confidence'] - 0.1 * self.missing_count)
            return self._create_enhanced_detection(kalman_result)

        return None

    def _classify_ball_state(self, velocity: List[float]) -> str:
        """Classify ball state based on velocity."""
        if not velocity:
            return "stationary"

        vx, vy = velocity
        speed = np.sqrt(vx**2 + vy**2)

        if speed < 2:
            return "stationary"
        elif abs(vy) < 2:
            return "horizontal"
        elif vy < 0:
            return "ascending"
        else:
            return "descending"

    def _reset_tracker(self) -> None:
        """Reset all tracking state."""
        self.trajectory.clear()
        self.missing_count = 0
        self.ball_template = None
        self.optical_flow_points = None
        self.kalman_initialized = False
        self.kalman = self._initialize_kalman_filter(0.1, 1.0)

        for method in self.detection_methods:
            self.detection_methods[method] = None

        self.logger.debug("Enhanced ball tracker reset")

    def get_trajectory(self) -> List[List[float]]:
        """Get complete ball trajectory."""
        return list(self.trajectory)

    def get_tracking_statistics(self) -> Dict[str, Any]:
        """Get detailed tracking statistics."""
        method_counts = {}
        for method in ['yolo', 'template', 'optical_flow', 'kalman', 'combined']:
            method_counts[method] = 0

        # This would need to be tracked during operation
        # For now, return basic stats
        return {
            'trajectory_length': len(self.trajectory),
            'missing_count': self.missing_count,
            'kalman_initialized': self.kalman_initialized,
            'has_template': self.ball_template is not None,
            'has_optical_flow': self.optical_flow_points is not None,
            'method_usage': method_counts
        }
