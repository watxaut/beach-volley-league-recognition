"""
Court position validation for volleyball action recognition.

This module validates player positions relative to court boundaries
and ensures actions are appropriate for the player's court location.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import logging

from .volleyball_actions import VolleyballAction


class CourtRegion:
    """Represents a region of the volleyball court."""
    
    def __init__(self, name: str, bounds: Dict[str, float], properties: Dict[str, Any]):
        """Initialize court region.
        
        Args:
            name: Region name (e.g., "front_court", "back_court", "serving_area")
            bounds: Region boundaries {"left": x, "right": x, "top": y, "bottom": y}
            properties: Region properties (e.g., allowed actions, special rules)
        """
        self.name = name
        self.bounds = bounds
        self.properties = properties


class CourtPositionValidator:
    """Validates player positions and actions relative to court boundaries."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the court position validator.
        
        Args:
            config: Configuration dictionary with court parameters
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Court configuration
        self.court_enabled = self.config.get("enabled", True)
        self.serve_boundary_margin = self.config.get("serve_boundary_margin", 50)
        self.court_geometry_source = self.config.get("court_geometry", "from_config")
        
        # Court dimensions (will be set from court detection or config)
        self.court_boundaries = None
        self.court_regions = {}
        
        # Default court geometry (normalized coordinates)
        self._initialize_default_court_geometry()
        
    def set_court_boundaries(self, court_boundaries: Dict[str, Any]) -> None:
        """Set court boundaries from court detection system.
        
        Args:
            court_boundaries: Court boundary information from court detector
        """
        self.court_boundaries = court_boundaries
        self._initialize_court_regions()
    
    def validate_position_for_action(
        self,
        player_position: Tuple[float, float],
        action_type: VolleyballAction,
        player_bbox: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """Validate if player position is appropriate for the action type.
        
        Args:
            player_position: Player center position (x, y)
            action_type: Volleyball action type
            player_bbox: Player bounding box (optional, for more precise validation)
            
        Returns:
            Position validation results
        """
        if not self.court_enabled or not self.court_boundaries:
            return self._create_validation_result(True, 1.0, "Court validation disabled")
        
        # Determine current court region
        current_region = self._determine_player_region(player_position)
        
        # Validate action for current region
        action_validation = self._validate_action_for_region(action_type, current_region)
        
        # Specific validations for different actions
        specific_validation = self._validate_action_specific_position(
            player_position, action_type, player_bbox
        )
        
        # Combine validation results
        overall_confidence = (
            action_validation.get("confidence", 1.0) * 0.6 +
            specific_validation.get("confidence", 1.0) * 0.4
        )
        
        is_valid = (action_validation.get("valid", True) and 
                   specific_validation.get("valid", True))
        
        return self._create_validation_result(
            is_valid,
            overall_confidence,
            f"Position validation for {action_type.value}",
            {
                "current_region": current_region,
                "action_validation": action_validation,
                "specific_validation": specific_validation,
                "player_position": player_position
            }
        )
    
    def validate_serve_position(
        self,
        player_position: Tuple[float, float],
        ball_position: Optional[Tuple[float, float]] = None,
        serve_phase: str = "preparation"
    ) -> Dict[str, Any]:
        """Validate serving player position and ball location.
        
        Args:
            player_position: Server position
            ball_position: Ball position (for toss validation)
            serve_phase: Phase of serve ("preparation", "toss", "contact")
            
        Returns:
            Serve position validation results
        """
        if not self.court_enabled or not self.court_boundaries:
            return self._create_validation_result(True, 1.0, "Court validation disabled")
        
        validation_results = {}
        overall_confidence = 1.0
        
        # Validate server is behind baseline
        baseline_validation = self._validate_behind_baseline(player_position)
        validation_results["baseline"] = baseline_validation
        if not baseline_validation.get("valid", True):
            overall_confidence *= 0.3
        
        # Validate server is within court width
        width_validation = self._validate_within_court_width(player_position)
        validation_results["court_width"] = width_validation
        if not width_validation.get("valid", True):
            overall_confidence *= 0.5
        
        # Phase-specific validations
        if serve_phase == "toss" and ball_position:
            toss_validation = self._validate_serve_toss_position(player_position, ball_position)
            validation_results["toss"] = toss_validation
            overall_confidence *= toss_validation.get("confidence", 1.0)
        
        elif serve_phase == "contact" and ball_position:
            contact_validation = self._validate_serve_contact_position(player_position, ball_position)
            validation_results["contact"] = contact_validation
            overall_confidence *= contact_validation.get("confidence", 1.0)
        
        is_valid = all(result.get("valid", True) for result in validation_results.values())
        
        return self._create_validation_result(
            is_valid,
            overall_confidence,
            f"Serve position validation ({serve_phase})",
            {
                "serve_phase": serve_phase,
                "validations": validation_results,
                "player_position": player_position,
                "ball_position": ball_position
            }
        )
    
    def _initialize_default_court_geometry(self) -> None:
        """Initialize default court geometry from configuration."""
        # Get court configuration (using the existing config format)
        court_config = self.config.get("court_geometry_config", {})
        
        # Default normalized court dimensions (0.0 to 1.0)
        self.default_court = {
            "width_ratio": court_config.get("court_width_ratio", 0.7),
            "height_ratio": court_config.get("court_height_ratio", 0.6),
            "horizontal_center": court_config.get("court_horizontal_center", 0.5),
            "vertical_offset": court_config.get("court_vertical_offset", 0.3),
            "baseline_margin": self.serve_boundary_margin
        }
    
    def _initialize_court_regions(self) -> None:
        """Initialize court regions based on current court boundaries."""
        if not self.court_boundaries:
            return
        
        # Extract court bounds
        bounds = self.court_boundaries.get("bounds", {})
        if not bounds:
            return
        
        court_left = bounds.get("left", 0)
        court_right = bounds.get("right", 1920)
        court_top = bounds.get("top", 0)
        court_bottom = bounds.get("bottom", 1080)
        
        court_width = court_right - court_left
        court_height = court_bottom - court_top
        
        # Define court regions
        net_y = court_top + court_height * 0.5  # Net at court center
        
        # Front court (near the net)
        self.court_regions["front_court"] = CourtRegion(
            "front_court",
            {
                "left": court_left,
                "right": court_right,
                "top": court_top,
                "bottom": net_y + court_height * 0.1  # Slightly past net
            },
            {
                "preferred_actions": [VolleyballAction.SPIKE, VolleyballAction.BLOCK, VolleyballAction.SET],
                "restricted_actions": [VolleyballAction.SERVE]
            }
        )
        
        # Back court (away from net)
        self.court_regions["back_court"] = CourtRegion(
            "back_court",
            {
                "left": court_left,
                "right": court_right,
                "top": net_y - court_height * 0.1,  # Slightly before net
                "bottom": court_bottom
            },
            {
                "preferred_actions": [VolleyballAction.DIG, VolleyballAction.SERVE],
                "allowed_actions": [VolleyballAction.SET]
            }
        )
        
        # Serving area (behind baseline)
        serve_area_top = court_bottom
        serve_area_bottom = court_bottom + self.serve_boundary_margin
        
        self.court_regions["serving_area"] = CourtRegion(
            "serving_area",
            {
                "left": court_left,
                "right": court_right,
                "top": serve_area_top,
                "bottom": serve_area_bottom
            },
            {
                "required_actions": [VolleyballAction.SERVE],
                "restricted_actions": [VolleyballAction.SPIKE, VolleyballAction.BLOCK, VolleyballAction.DIG, VolleyballAction.SET]
            }
        )
        
        # Out of bounds areas
        self.court_regions["out_of_bounds"] = CourtRegion(
            "out_of_bounds",
            {
                "left": float('-inf'),
                "right": float('inf'),
                "top": float('-inf'),
                "bottom": float('inf')
            },
            {
                "restricted_actions": list(VolleyballAction)
            }
        )
    
    def _determine_player_region(self, player_position: Tuple[float, float]) -> str:
        """Determine which court region the player is in.
        
        Args:
            player_position: Player center position
            
        Returns:
            Region name
        """
        x, y = player_position
        
        # Check each region (except out_of_bounds)
        for region_name, region in self.court_regions.items():
            if region_name == "out_of_bounds":
                continue
                
            bounds = region.bounds
            if (bounds["left"] <= x <= bounds["right"] and 
                bounds["top"] <= y <= bounds["bottom"]):
                return region_name
        
        return "out_of_bounds"
    
    def _validate_action_for_region(
        self, 
        action_type: VolleyballAction, 
        region_name: str
    ) -> Dict[str, Any]:
        """Validate if action is appropriate for the court region.
        
        Args:
            action_type: Volleyball action type
            region_name: Court region name
            
        Returns:
            Region-based action validation
        """
        if region_name not in self.court_regions:
            return {"valid": False, "confidence": 0.0, "reason": "unknown_region"}
        
        region = self.court_regions[region_name]
        properties = region.properties
        
        # Check required actions
        required_actions = properties.get("required_actions", [])
        if required_actions and action_type not in required_actions:
            return {
                "valid": False,
                "confidence": 0.2,
                "reason": f"Action {action_type.value} not required in {region_name}",
                "required_actions": [a.value for a in required_actions]
            }
        
        # Check restricted actions
        restricted_actions = properties.get("restricted_actions", [])
        if action_type in restricted_actions:
            return {
                "valid": False,
                "confidence": 0.1,
                "reason": f"Action {action_type.value} restricted in {region_name}",
                "restricted_actions": [a.value for a in restricted_actions]
            }
        
        # Check preferred actions
        preferred_actions = properties.get("preferred_actions", [])
        allowed_actions = properties.get("allowed_actions", [])
        
        if action_type in preferred_actions:
            confidence = 1.0
        elif action_type in allowed_actions:
            confidence = 0.8
        else:
            # Not explicitly restricted, but not preferred
            confidence = 0.6
        
        return {
            "valid": True,
            "confidence": confidence,
            "reason": f"Action {action_type.value} validated for {region_name}",
            "region_properties": properties
        }
    
    def _validate_action_specific_position(
        self,
        player_position: Tuple[float, float],
        action_type: VolleyballAction,
        player_bbox: Optional[List[float]]
    ) -> Dict[str, Any]:
        """Validate action-specific position requirements.
        
        Args:
            player_position: Player position
            action_type: Action type
            player_bbox: Player bounding box
            
        Returns:
            Action-specific position validation
        """
        if action_type == VolleyballAction.SERVE:
            return self._validate_serve_specific_position(player_position)
        elif action_type == VolleyballAction.BLOCK:
            return self._validate_block_specific_position(player_position)
        elif action_type == VolleyballAction.SPIKE:
            return self._validate_spike_specific_position(player_position)
        else:
            # For dig and set, position is less critical
            return {"valid": True, "confidence": 1.0, "reason": "No specific position requirements"}
    
    def _validate_serve_specific_position(self, player_position: Tuple[float, float]) -> Dict[str, Any]:
        """Validate serve-specific position requirements."""
        # Server must be behind baseline
        behind_baseline = self._validate_behind_baseline(player_position)
        within_width = self._validate_within_court_width(player_position)
        
        confidence = 1.0
        if not behind_baseline.get("valid", True):
            confidence *= 0.2
        if not within_width.get("valid", True):
            confidence *= 0.5
        
        is_valid = behind_baseline.get("valid", True) and within_width.get("valid", True)
        
        return {
            "valid": is_valid,
            "confidence": confidence,
            "reason": "Serve position validation",
            "behind_baseline": behind_baseline,
            "within_width": within_width
        }
    
    def _validate_block_specific_position(self, player_position: Tuple[float, float]) -> Dict[str, Any]:
        """Validate block-specific position requirements."""
        # Blocks should be near the net (front court)
        region = self._determine_player_region(player_position)
        
        if region == "front_court":
            confidence = 1.0
        elif region == "back_court":
            confidence = 0.4  # Possible but less likely
        else:
            confidence = 0.1
        
        return {
            "valid": confidence > 0.3,
            "confidence": confidence,
            "reason": f"Block position validation in {region}",
            "region": region
        }
    
    def _validate_spike_specific_position(self, player_position: Tuple[float, float]) -> Dict[str, Any]:
        """Validate spike-specific position requirements."""
        # Spikes are most common in front court, but can occur in back court
        region = self._determine_player_region(player_position)
        
        if region == "front_court":
            confidence = 1.0
        elif region == "back_court":
            confidence = 0.7  # Back court spikes are less common but valid
        else:
            confidence = 0.2
        
        return {
            "valid": confidence > 0.5,
            "confidence": confidence,
            "reason": f"Spike position validation in {region}",
            "region": region
        }
    
    def _validate_behind_baseline(self, player_position: Tuple[float, float]) -> Dict[str, Any]:
        """Validate that player is behind the baseline for serving.
        
        Args:
            player_position: Player position
            
        Returns:
            Baseline validation result
        """
        if not self.court_boundaries:
            return {"valid": True, "confidence": 1.0, "reason": "No court boundaries available"}
        
        bounds = self.court_boundaries.get("bounds", {})
        court_bottom = bounds.get("bottom", 1080)
        
        x, y = player_position
        
        # Player should be below (behind) the baseline
        behind_baseline = y > court_bottom
        
        if behind_baseline:
            # Calculate how far behind baseline
            distance_behind = y - court_bottom
            confidence = min(1.0, distance_behind / self.serve_boundary_margin)
        else:
            # Player is in front of baseline - not valid for serving
            distance_ahead = court_bottom - y
            confidence = max(0.0, 1.0 - (distance_ahead / self.serve_boundary_margin))
        
        return {
            "valid": behind_baseline,
            "confidence": confidence,
            "distance_from_baseline": abs(y - court_bottom),
            "behind_baseline": behind_baseline,
            "reason": "Baseline position validation"
        }
    
    def _validate_within_court_width(self, player_position: Tuple[float, float]) -> Dict[str, Any]:
        """Validate that player is within court width boundaries.
        
        Args:
            player_position: Player position
            
        Returns:
            Court width validation result
        """
        if not self.court_boundaries:
            return {"valid": True, "confidence": 1.0, "reason": "No court boundaries available"}
        
        bounds = self.court_boundaries.get("bounds", {})
        court_left = bounds.get("left", 0)
        court_right = bounds.get("right", 1920)
        
        x, y = player_position
        
        # Allow some margin for serving
        margin = 20  # pixels
        within_width = (court_left - margin) <= x <= (court_right + margin)
        
        if within_width:
            # Calculate distance from court center
            court_center = (court_left + court_right) / 2
            distance_from_center = abs(x - court_center)
            court_half_width = (court_right - court_left) / 2
            confidence = max(0.7, 1.0 - (distance_from_center / (court_half_width + margin)))
        else:
            # Outside court width
            if x < court_left:
                distance_outside = court_left - x
            else:
                distance_outside = x - court_right
            confidence = max(0.0, 1.0 - (distance_outside / 100))  # Decrease confidence with distance
        
        return {
            "valid": within_width,
            "confidence": confidence,
            "within_court_width": within_width,
            "distance_from_center": abs(x - (court_left + court_right) / 2),
            "reason": "Court width validation"
        }
    
    def _validate_serve_toss_position(
        self, 
        player_position: Tuple[float, float], 
        ball_position: Tuple[float, float]
    ) -> Dict[str, Any]:
        """Validate ball toss position relative to server.
        
        Args:
            player_position: Server position
            ball_position: Ball position during toss
            
        Returns:
            Toss position validation
        """
        px, py = player_position
        bx, by = ball_position
        
        # Ball should be relatively close to player during toss
        distance = np.sqrt((bx - px)**2 + (by - py)**2)
        
        # Reasonable toss distance
        max_toss_distance = 100  # pixels
        within_distance = distance <= max_toss_distance
        
        # Ball should be above or level with player for toss
        ball_above_player = by <= py
        
        # Calculate confidence
        if within_distance and ball_above_player:
            confidence = max(0.7, 1.0 - (distance / max_toss_distance))
        elif within_distance:
            confidence = 0.5
        else:
            confidence = max(0.0, 1.0 - (distance / (max_toss_distance * 2)))
        
        return {
            "valid": within_distance and ball_above_player,
            "confidence": confidence,
            "distance": distance,
            "within_distance": within_distance,
            "ball_above_player": ball_above_player,
            "reason": "Serve toss position validation"
        }
    
    def _validate_serve_contact_position(
        self, 
        player_position: Tuple[float, float], 
        ball_position: Tuple[float, float]
    ) -> Dict[str, Any]:
        """Validate ball contact position during serve.
        
        Args:
            player_position: Server position
            ball_position: Ball position during contact
            
        Returns:
            Contact position validation
        """
        px, py = player_position
        bx, by = ball_position
        
        # Ball should be in front of player for contact
        ball_in_front = bx != px  # Allow any horizontal position
        
        # Ball should be at reasonable height for contact
        height_difference = abs(by - py)
        reasonable_height = height_difference <= 150  # Within arm reach
        
        # Distance validation
        distance = np.sqrt((bx - px)**2 + (by - py)**2)
        within_reach = distance <= 120  # Within arm reach
        
        # Calculate confidence
        validations = [ball_in_front, reasonable_height, within_reach]
        confidence = sum(validations) / len(validations)
        
        return {
            "valid": all(validations),
            "confidence": confidence,
            "distance": distance,
            "height_difference": height_difference,
            "ball_in_front": ball_in_front,
            "reasonable_height": reasonable_height,
            "within_reach": within_reach,
            "reason": "Serve contact position validation"
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
            confidence: Confidence score
            message: Validation message
            details: Optional additional details
            
        Returns:
            Standardized validation result
        """
        return {
            "valid": is_valid,
            "confidence": max(0.0, min(1.0, confidence)),
            "message": message,
            "court_validation": True,
            "details": details or {}
        }
    
    def get_court_regions(self) -> Dict[str, CourtRegion]:
        """Get current court regions.
        
        Returns:
            Dictionary of court regions
        """
        return self.court_regions.copy()
    
    def is_court_available(self) -> bool:
        """Check if court boundaries are available for validation.
        
        Returns:
            True if court boundaries are set
        """
        return self.court_boundaries is not None
    
    def reset_court_boundaries(self) -> None:
        """Reset court boundaries and regions."""
        self.court_boundaries = None
        self.court_regions.clear()