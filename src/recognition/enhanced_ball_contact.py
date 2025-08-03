"""
Enhanced ball contact validation for volleyball action recognition.

This module provides sophisticated ball-player contact validation using
body part-specific contact zones and adaptive proximity thresholds.
"""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import logging
from enum import Enum

from .volleyball_actions import VolleyballAction


class ContactZone:
    """Represents a contact zone for a specific volleyball action."""
    
    def __init__(
        self,
        height_range: Tuple[float, float],
        width_expansion: float,
        base_threshold: float
    ):
        """Initialize contact zone.
        
        Args:
            height_range: (min, max) relative height range (0.0 = shoulders, 1.0 = feet)
            width_expansion: Multiplier for arm reach extension
            base_threshold: Base proximity threshold in pixels
        """
        self.height_range = height_range
        self.width_expansion = width_expansion
        self.base_threshold = base_threshold


class EnhancedBallContactValidator:
    """Enhanced validator for ball-player contact using pose-aware contact zones."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the enhanced ball contact validator.
        
        Args:
            config: Configuration dictionary with validation parameters
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize contact zones for each action
        self._initialize_contact_zones()
        
        # Validation parameters
        self.strict_mode = self.config.get("strict_mode", True)
        self.min_contact_confidence = self.config.get("min_contact_confidence", 0.7)
        
    def _initialize_contact_zones(self) -> None:
        """Initialize contact zones for each volleyball action."""
        default_zones = {
            VolleyballAction.DIG: ContactZone(
                height_range=(0.6, 1.0),  # Lower body/arms
                width_expansion=1.2,
                base_threshold=80
            ),
            VolleyballAction.SET: ContactZone(
                height_range=(0.0, 0.4),  # Above shoulders
                width_expansion=1.0,
                base_threshold=100
            ),
            VolleyballAction.SPIKE: ContactZone(
                height_range=(-0.2, 0.3),  # Extended above head
                width_expansion=1.5,
                base_threshold=120
            ),
            VolleyballAction.BLOCK: ContactZone(
                height_range=(0.0, 0.3),  # Arms up at net
                width_expansion=1.2,
                base_threshold=90
            ),
            VolleyballAction.SERVE: ContactZone(
                height_range=(0.2, 0.8),  # Ball toss and contact area
                width_expansion=2.0,
                base_threshold=150
            )
        }
        
        # Override with config values if provided
        config_zones = self.config.get("contact_zones", {})
        self.contact_zones = {}
        
        for action, default_zone in default_zones.items():
            if action.value in config_zones:
                zone_config = config_zones[action.value]
                self.contact_zones[action] = ContactZone(
                    height_range=tuple(zone_config.get("height_range", default_zone.height_range)),
                    width_expansion=zone_config.get("width_expansion", default_zone.width_expansion),
                    base_threshold=zone_config.get("base_threshold", default_zone.base_threshold)
                )
            else:
                self.contact_zones[action] = default_zone
    
    def validate_ball_contact(
        self,
        ball_data: Dict[str, Any],
        pose_data: Dict[str, Any],
        action_type: VolleyballAction,
        player_bbox: List[float]
    ) -> Dict[str, Any]:
        """Validate ball contact for a specific action type.
        
        Args:
            ball_data: Ball position and tracking data
            pose_data: Player pose estimation data
            action_type: Type of volleyball action to validate
            player_bbox: Player bounding box [x1, y1, x2, y2]
            
        Returns:
            Validation results with contact confidence and metrics
        """
        if not ball_data or not pose_data:
            return self._create_validation_result(False, 0.0, "Missing data")
        
        # Get contact zone for this action
        contact_zone = self.contact_zones.get(action_type)
        if not contact_zone:
            return self._create_validation_result(False, 0.0, f"No contact zone for {action_type}")
        
        # Calculate adaptive proximity threshold
        proximity_threshold = self._calculate_adaptive_threshold(
            player_bbox, contact_zone, pose_data
        )
        
        # Define body part-specific contact zone
        zone_coords = self._calculate_contact_zone_coordinates(
            pose_data, contact_zone, player_bbox
        )
        
        if not zone_coords:
            return self._create_validation_result(False, 0.0, "Could not calculate contact zone")
        
        # Check ball position relative to contact zone
        ball_center = ball_data.get("center", [0, 0])
        contact_validation = self._validate_ball_in_zone(
            ball_center, zone_coords, proximity_threshold
        )
        
        # Calculate contact confidence
        confidence = self._calculate_contact_confidence(
            ball_center, zone_coords, proximity_threshold, contact_validation
        )
        
        # Additional validation based on action type
        action_specific_validation = self._validate_action_specific_requirements(
            ball_data, pose_data, action_type, contact_validation
        )
        
        # Combine validation results
        final_confidence = confidence * action_specific_validation.get("confidence_multiplier", 1.0)
        is_valid = (final_confidence >= self.min_contact_confidence and 
                   contact_validation["in_zone"] and 
                   action_specific_validation.get("valid", True))
        
        return self._create_validation_result(
            is_valid, 
            final_confidence,
            f"Ball contact validation for {action_type.value}",
            {
                "proximity_threshold": proximity_threshold,
                "contact_zone": zone_coords,
                "ball_center": ball_center,
                "distance_to_zone": contact_validation.get("distance", float('inf')),
                "action_specific": action_specific_validation
            }
        )
    
    def _calculate_adaptive_threshold(
        self, 
        player_bbox: List[float], 
        contact_zone: ContactZone,
        pose_data: Dict[str, Any]
    ) -> float:
        """Calculate adaptive proximity threshold based on player size and camera distance.
        
        Args:
            player_bbox: Player bounding box
            contact_zone: Contact zone configuration
            pose_data: Pose estimation data
            
        Returns:
            Adaptive proximity threshold in pixels
        """
        # Base threshold from contact zone
        base_threshold = contact_zone.base_threshold
        
        # Player size factor (larger players = larger reach)
        bbox_width = player_bbox[2] - player_bbox[0]
        bbox_height = player_bbox[3] - player_bbox[1]
        player_size_factor = np.sqrt(bbox_width * bbox_height) / 100.0  # Normalize to ~1.0
        
        # Camera distance estimate (smaller players = farther away = smaller threshold)
        camera_distance_factor = max(0.5, min(2.0, bbox_height / 200.0))  # Clamp between 0.5-2.0
        
        # Pose visibility factor (better pose = more confident threshold)
        visible_keypoints = sum(1 for kp in pose_data.get("keypoints", []) 
                              if kp.get("visibility", 0) > 0.5)
        total_keypoints = len(pose_data.get("keypoints", []))
        visibility_factor = visible_keypoints / max(1, total_keypoints) if total_keypoints > 0 else 0.5
        
        # Calculate adaptive threshold
        adaptive_threshold = (base_threshold * 
                            player_size_factor * 
                            camera_distance_factor * 
                            (0.7 + 0.3 * visibility_factor))  # 70-100% based on visibility
        
        return max(30, min(300, adaptive_threshold))  # Clamp to reasonable range
    
    def _calculate_contact_zone_coordinates(
        self,
        pose_data: Dict[str, Any],
        contact_zone: ContactZone,
        player_bbox: List[float]
    ) -> Optional[Dict[str, Any]]:
        """Calculate contact zone coordinates based on pose keypoints.
        
        Args:
            pose_data: Pose estimation data
            contact_zone: Contact zone configuration
            player_bbox: Player bounding box
            
        Returns:
            Contact zone coordinates or None if calculation fails
        """
        keypoints_dict = pose_data.get("keypoints_dict", {})
        
        # Key body landmarks for zone calculation
        key_landmarks = {
            "left_shoulder": 11,
            "right_shoulder": 12,
            "left_elbow": 13,
            "right_elbow": 14,
            "left_wrist": 15,
            "right_wrist": 16,
            "left_hip": 23,
            "right_hip": 24
        }
        
        # Check if we have sufficient keypoints
        available_landmarks = {name: idx for name, idx in key_landmarks.items() 
                             if idx in keypoints_dict and keypoints_dict[idx].get("visibility", 0) > 0.5}
        
        if len(available_landmarks) < 4:  # Need at least 4 visible landmarks
            return None
        
        # Calculate reference points
        shoulder_center = self._get_center_point(
            keypoints_dict, [key_landmarks["left_shoulder"], key_landmarks["right_shoulder"]]
        )
        hip_center = self._get_center_point(
            keypoints_dict, [key_landmarks["left_hip"], key_landmarks["right_hip"]]
        )
        
        if not shoulder_center or not hip_center:
            return None
        
        # Calculate body reference measurements
        body_height = abs(hip_center[1] - shoulder_center[1])
        shoulder_width = self._calculate_shoulder_width(keypoints_dict, key_landmarks)
        
        if body_height <= 0 or shoulder_width <= 0:
            return None
        
        # Calculate zone boundaries based on height range
        zone_top_y = shoulder_center[1] + contact_zone.height_range[0] * body_height
        zone_bottom_y = shoulder_center[1] + contact_zone.height_range[1] * body_height
        
        # Calculate zone width based on shoulder width and expansion
        zone_width = shoulder_width * contact_zone.width_expansion
        zone_left_x = shoulder_center[0] - zone_width / 2
        zone_right_x = shoulder_center[0] + zone_width / 2
        
        return {
            "center": shoulder_center,
            "bounds": {
                "left": zone_left_x,
                "right": zone_right_x,
                "top": zone_top_y,
                "bottom": zone_bottom_y
            },
            "width": zone_width,
            "height": abs(zone_bottom_y - zone_top_y),
            "reference_points": {
                "shoulder_center": shoulder_center,
                "hip_center": hip_center,
                "body_height": body_height,
                "shoulder_width": shoulder_width
            }
        }
    
    def _get_center_point(
        self, 
        keypoints_dict: Dict[int, Dict[str, float]], 
        landmark_indices: List[int]
    ) -> Optional[List[float]]:
        """Calculate center point of given landmarks.
        
        Args:
            keypoints_dict: Dictionary of keypoints
            landmark_indices: Indices of landmarks to average
            
        Returns:
            Center point [x, y] or None if insufficient data
        """
        valid_points = []
        for idx in landmark_indices:
            if idx in keypoints_dict:
                kp = keypoints_dict[idx]
                if kp.get("visibility", 0) > 0.5:
                    valid_points.append([kp["x"], kp["y"]])
        
        if not valid_points:
            return None
        
        center = np.mean(valid_points, axis=0)
        return [float(center[0]), float(center[1])]
    
    def _calculate_shoulder_width(
        self, 
        keypoints_dict: Dict[int, Dict[str, float]], 
        key_landmarks: Dict[str, int]
    ) -> float:
        """Calculate shoulder width from keypoints.
        
        Args:
            keypoints_dict: Dictionary of keypoints
            key_landmarks: Mapping of landmark names to indices
            
        Returns:
            Shoulder width in pixels
        """
        left_shoulder_idx = key_landmarks.get("left_shoulder")
        right_shoulder_idx = key_landmarks.get("right_shoulder")
        
        if (left_shoulder_idx not in keypoints_dict or 
            right_shoulder_idx not in keypoints_dict):
            return 0.0
        
        left_shoulder = keypoints_dict[left_shoulder_idx]
        right_shoulder = keypoints_dict[right_shoulder_idx]
        
        if (left_shoulder.get("visibility", 0) < 0.5 or 
            right_shoulder.get("visibility", 0) < 0.5):
            return 0.0
        
        width = abs(left_shoulder["x"] - right_shoulder["x"])
        return float(width)
    
    def _validate_ball_in_zone(
        self,
        ball_center: List[float],
        zone_coords: Dict[str, Any],
        proximity_threshold: float
    ) -> Dict[str, Any]:
        """Validate if ball is within the contact zone.
        
        Args:
            ball_center: Ball center coordinates [x, y]
            zone_coords: Contact zone coordinates
            proximity_threshold: Maximum allowed distance
            
        Returns:
            Validation results with distance and zone status
        """
        bounds = zone_coords["bounds"]
        
        # Calculate distance to zone (0 if inside, positive if outside)
        dx = max(0, max(bounds["left"] - ball_center[0], ball_center[0] - bounds["right"]))
        dy = max(0, max(bounds["top"] - ball_center[1], ball_center[1] - bounds["bottom"]))
        distance_to_zone = np.sqrt(dx * dx + dy * dy)
        
        # Check if ball is within proximity threshold
        in_zone = distance_to_zone <= proximity_threshold
        
        # Additional checks
        center_distance = np.sqrt(
            (ball_center[0] - zone_coords["center"][0]) ** 2 +
            (ball_center[1] - zone_coords["center"][1]) ** 2
        )
        
        return {
            "in_zone": in_zone,
            "distance": distance_to_zone,
            "center_distance": center_distance,
            "ball_position": ball_center,
            "zone_bounds": bounds
        }
    
    def _calculate_contact_confidence(
        self,
        ball_center: List[float],
        zone_coords: Dict[str, Any],
        proximity_threshold: float,
        contact_validation: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for ball contact.
        
        Args:
            ball_center: Ball center coordinates
            zone_coords: Contact zone coordinates
            proximity_threshold: Proximity threshold
            contact_validation: Contact validation results
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not contact_validation["in_zone"]:
            # Ball outside zone - confidence decreases with distance
            distance = contact_validation["distance"]
            max_distance = proximity_threshold * 2  # Double threshold as max
            confidence = max(0.0, 1.0 - (distance / max_distance))
            return confidence * 0.3  # Max 30% confidence if outside zone
        
        # Ball inside zone - calculate confidence based on position
        center_distance = contact_validation["center_distance"]
        zone_radius = min(zone_coords["width"], zone_coords["height"]) / 2
        
        # Higher confidence for balls closer to zone center
        if center_distance <= zone_radius * 0.5:
            confidence = 1.0  # Very close to center
        elif center_distance <= zone_radius:
            confidence = 0.8 + 0.2 * (1.0 - (center_distance / zone_radius))
        else:
            # Inside zone but far from center
            confidence = 0.6 + 0.2 * (1.0 - min(1.0, center_distance / zone_radius))
        
        return max(0.0, min(1.0, confidence))
    
    def _validate_action_specific_requirements(
        self,
        ball_data: Dict[str, Any],
        pose_data: Dict[str, Any],
        action_type: VolleyballAction,
        contact_validation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate action-specific requirements beyond basic contact.
        
        Args:
            ball_data: Ball tracking data
            pose_data: Pose estimation data
            action_type: Volleyball action type
            contact_validation: Basic contact validation results
            
        Returns:
            Action-specific validation results
        """
        validation_result = {"valid": True, "confidence_multiplier": 1.0, "details": {}}
        
        # Action-specific validations
        if action_type == VolleyballAction.DIG:
            validation_result.update(self._validate_dig_requirements(ball_data, pose_data))
            
        elif action_type == VolleyballAction.SET:
            validation_result.update(self._validate_set_requirements(ball_data, pose_data))
            
        elif action_type == VolleyballAction.SPIKE:
            validation_result.update(self._validate_spike_requirements(ball_data, pose_data))
            
        elif action_type == VolleyballAction.BLOCK:
            validation_result.update(self._validate_block_requirements(ball_data, pose_data))
            
        elif action_type == VolleyballAction.SERVE:
            validation_result.update(self._validate_serve_requirements(ball_data, pose_data))
        
        return validation_result
    
    def _validate_dig_requirements(
        self, 
        ball_data: Dict[str, Any], 
        pose_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate dig-specific requirements."""
        # Dig typically involves lower ball position and forward body lean
        ball_relative_height = ball_data.get("relative_height", 0.5)
        body_lean = pose_data.get("pose_features", {}).get("body_lean", 0)
        
        confidence_multiplier = 1.0
        
        # Prefer balls at mid-to-low height for digs
        if 0.3 <= ball_relative_height <= 0.8:
            confidence_multiplier *= 1.1
        elif ball_relative_height < 0.2:  # Very high balls unlikely for digs
            confidence_multiplier *= 0.7
        
        # Forward lean is typical for digs
        if body_lean > 15:
            confidence_multiplier *= 1.1
        
        return {
            "valid": True,
            "confidence_multiplier": confidence_multiplier,
            "details": {
                "ball_height_appropriate": 0.3 <= ball_relative_height <= 0.8,
                "body_lean_forward": body_lean > 15
            }
        }
    
    def _validate_set_requirements(
        self, 
        ball_data: Dict[str, Any], 
        pose_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate set-specific requirements."""
        # Sets typically involve overhead ball position and upward arm extension
        ball_relative_height = ball_data.get("relative_height", 0.5)
        pose_features = pose_data.get("pose_features", {})
        left_arm_height = pose_features.get("left_arm_height", 500)
        right_arm_height = pose_features.get("right_arm_height", 500)
        
        confidence_multiplier = 1.0
        
        # Prefer balls at overhead height for sets
        if ball_relative_height < 0.4:
            confidence_multiplier *= 1.2
        elif ball_relative_height > 0.7:  # Low balls unlikely for sets
            confidence_multiplier *= 0.6
        
        # High arm position typical for sets
        if left_arm_height < 200 or right_arm_height < 200:
            confidence_multiplier *= 1.1
        
        return {
            "valid": True,
            "confidence_multiplier": confidence_multiplier,
            "details": {
                "ball_height_appropriate": ball_relative_height < 0.4,
                "arms_raised": left_arm_height < 200 or right_arm_height < 200
            }
        }
    
    def _validate_spike_requirements(
        self, 
        ball_data: Dict[str, Any], 
        pose_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate spike-specific requirements."""
        # Spikes involve very high ball position and jumping motion
        ball_relative_height = ball_data.get("relative_height", 0.5)
        pose_features = pose_data.get("pose_features", {})
        max_arm_height = min(
            pose_features.get("left_arm_height", 500),
            pose_features.get("right_arm_height", 500)
        )
        
        confidence_multiplier = 1.0
        
        # Prefer very high balls for spikes
        if ball_relative_height < 0.3:
            confidence_multiplier *= 1.3
        elif ball_relative_height > 0.6:
            confidence_multiplier *= 0.5
        
        # Very high arm extension for spikes
        if max_arm_height < 150:
            confidence_multiplier *= 1.2
        
        return {
            "valid": True,
            "confidence_multiplier": confidence_multiplier,
            "details": {
                "ball_height_appropriate": ball_relative_height < 0.3,
                "arm_extended_high": max_arm_height < 150
            }
        }
    
    def _validate_block_requirements(
        self, 
        ball_data: Dict[str, Any], 
        pose_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate block-specific requirements."""
        # Blocks involve high ball position and both arms raised
        ball_relative_height = ball_data.get("relative_height", 0.5)
        pose_features = pose_data.get("pose_features", {})
        left_arm_height = pose_features.get("left_arm_height", 500)
        right_arm_height = pose_features.get("right_arm_height", 500)
        
        confidence_multiplier = 1.0
        
        # Prefer high balls for blocks
        if ball_relative_height < 0.4:
            confidence_multiplier *= 1.2
        
        # Both arms should be raised for blocks
        if left_arm_height < 200 and right_arm_height < 200:
            confidence_multiplier *= 1.3
        elif left_arm_height > 300 or right_arm_height > 300:
            confidence_multiplier *= 0.7
        
        return {
            "valid": True,
            "confidence_multiplier": confidence_multiplier,
            "details": {
                "ball_height_appropriate": ball_relative_height < 0.4,
                "both_arms_raised": left_arm_height < 200 and right_arm_height < 200
            }
        }
    
    def _validate_serve_requirements(
        self, 
        ball_data: Dict[str, Any], 
        pose_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate serve-specific requirements."""
        # Serves have specific ball trajectory and arm swing patterns
        ball_velocity = ball_data.get("velocity", [0, 0])
        ball_speed = np.linalg.norm(ball_velocity) if ball_velocity else 0
        
        confidence_multiplier = 1.0
        
        # Serves typically have significant ball movement
        if ball_speed > 20:
            confidence_multiplier *= 1.2
        elif ball_speed < 5:
            confidence_multiplier *= 0.8
        
        return {
            "valid": True,
            "confidence_multiplier": confidence_multiplier,
            "details": {
                "ball_moving": ball_speed > 5,
                "ball_speed_appropriate": ball_speed > 20
            }
        }
    
    def _create_validation_result(
        self,
        is_valid: bool,
        confidence: float,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create standardized validation result.
        
        Args:
            is_valid: Whether validation passed
            confidence: Confidence score (0.0 to 1.0)
            message: Validation message
            details: Optional additional details
            
        Returns:
            Standardized validation result dictionary
        """
        return {
            "valid": is_valid,
            "confidence": max(0.0, min(1.0, confidence)),
            "message": message,
            "details": details or {}
        }