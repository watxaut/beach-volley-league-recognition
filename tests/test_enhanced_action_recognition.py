"""
Tests for enhanced action recognition system.

This module tests the enhanced ball-player proximity validation,
temporal contact validation, ball trajectory analysis, and court position validation.
"""

import pytest
import numpy as np
from typing import Dict, Any, List
from unittest.mock import Mock, patch

from src.recognition.action_classifier import ActionClassifier, VolleyballAction
from src.recognition.enhanced_ball_contact import EnhancedBallContactValidator
from src.recognition.temporal_contact_validator import TemporalContactValidator, ContactState
from src.recognition.ball_trajectory_analyzer import BallTrajectoryAnalyzer
from src.recognition.court_position_validator import CourtPositionValidator
from src.recognition.pose_estimator import PoseEstimator


class TestEnhancedBallContactValidator:
    """Test suite for enhanced ball contact validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            "contact_zones": {
                "dig": {
                    "height_range": [0.6, 1.0],
                    "width_expansion": 1.2,
                    "base_threshold": 80
                }
            }
        }
        self.validator = EnhancedBallContactValidator(self.config)
    
    def test_initialization(self):
        """Test validator initialization."""
        assert self.validator is not None
        assert VolleyballAction.DIG in self.validator.contact_zones
        assert self.validator.strict_mode is True
    
    def test_adaptive_threshold_calculation(self):
        """Test adaptive proximity threshold calculation."""
        player_bbox = [100, 200, 200, 400]  # 100x200 bbox
        contact_zone = self.validator.contact_zones[VolleyballAction.DIG]
        pose_data = {"keypoints": [{"visibility": 0.8} for _ in range(33)]}
        
        threshold = self.validator._calculate_adaptive_threshold(
            player_bbox, contact_zone, pose_data
        )
        
        assert 30 <= threshold <= 300  # Should be within reasonable range
        assert isinstance(threshold, float)
    
    def test_contact_zone_calculation(self):
        """Test contact zone coordinate calculation."""
        pose_data = {
            "keypoints_dict": {
                11: {"x": 150, "y": 100, "visibility": 0.9},  # Left shoulder
                12: {"x": 200, "y": 100, "visibility": 0.9},  # Right shoulder
                23: {"x": 160, "y": 250, "visibility": 0.9},  # Left hip
                24: {"x": 190, "y": 250, "visibility": 0.9},  # Right hip
            }
        }
        player_bbox = [100, 50, 250, 300]
        contact_zone = self.validator.contact_zones[VolleyballAction.DIG]
        
        zone_coords = self.validator._calculate_contact_zone_coordinates(
            pose_data, contact_zone, player_bbox
        )
        
        assert zone_coords is not None
        assert "center" in zone_coords
        assert "bounds" in zone_coords
        assert len(zone_coords["center"]) == 2
    
    def test_ball_contact_validation_valid(self):
        """Test valid ball contact scenario."""
        ball_data = {"center": [175, 180]}  # Near player center
        pose_data = self._create_mock_pose_data()
        player_bbox = [100, 50, 250, 300]
        
        result = self.validator.validate_ball_contact(
            ball_data, pose_data, VolleyballAction.DIG, player_bbox
        )
        
        assert result["valid"] is True
        assert result["confidence"] > 0.5
    
    def test_ball_contact_validation_invalid(self):
        """Test invalid ball contact scenario."""
        ball_data = {"center": [500, 500]}  # Far from player
        pose_data = self._create_mock_pose_data()
        player_bbox = [100, 50, 250, 300]
        
        result = self.validator.validate_ball_contact(
            ball_data, pose_data, VolleyballAction.DIG, player_bbox
        )
        
        assert result["valid"] is False
        assert result["confidence"] < 0.5
    
    def test_action_specific_validation_dig(self):
        """Test dig-specific validation requirements."""
        ball_data = {"relative_height": 0.5}  # Mid-height ball
        pose_data = {"pose_features": {"body_lean": 20}}  # Forward lean
        
        result = self.validator._validate_dig_requirements(ball_data, pose_data)
        
        assert result["valid"] is True
        assert result["confidence_multiplier"] >= 1.0
    
    def _create_mock_pose_data(self) -> Dict[str, Any]:
        """Create mock pose data for testing."""
        return {
            "keypoints_dict": {
                11: {"x": 150, "y": 100, "visibility": 0.9},
                12: {"x": 200, "y": 100, "visibility": 0.9},
                23: {"x": 160, "y": 250, "visibility": 0.9},
                24: {"x": 190, "y": 250, "visibility": 0.9},
            },
            "pose_features": {
                "left_arm_height": 180,
                "right_arm_height": 185,
                "body_lean": 10
            }
        }


class TestTemporalContactValidator:
    """Test suite for temporal contact validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            "window_size": 5,
            "min_frames_in_contact": 3,
            "confidence_decay_rate": 0.1
        }
        self.validator = TemporalContactValidator(self.config)
    
    def test_initialization(self):
        """Test validator initialization."""
        assert self.validator.window_size == 5
        assert self.validator.min_frames_in_contact == 3
        assert len(self.validator.player_histories) == 0
    
    def test_contact_state_transitions(self):
        """Test contact state transitions."""
        player_id = 1
        ball_data = {"center": [100, 100]}
        
        # Start with valid contact
        validation = {"valid": True, "confidence": 0.8}
        result = self.validator.validate_temporal_contact(
            player_id, ball_data, validation, VolleyballAction.DIG
        )
        
        assert player_id in self.validator.player_states
        assert self.validator.player_states[player_id] in [
            ContactState.APPROACHING, ContactState.IN_CONTACT
        ]
    
    def test_sustained_contact_validation(self):
        """Test sustained contact over multiple frames."""
        player_id = 1
        ball_data = {"center": [100, 100]}
        
        # Simulate multiple frames of valid contact
        for frame in range(5):
            validation = {"valid": True, "confidence": 0.8}
            result = self.validator.validate_temporal_contact(
                player_id, ball_data, validation, VolleyballAction.DIG, frame
            )
        
        # Should have sustained contact
        assert result["valid"] is True
        assert result["confidence"] > 0.5
    
    def test_contact_stability_calculation(self):
        """Test contact stability calculation."""
        # Create mock history with stable contact
        from src.recognition.temporal_contact_validator import ContactFrame
        
        history = []
        for i in range(5):
            frame = ContactFrame(
                frame_number=i,
                ball_data={"center": [100, 100]},
                validation_result={"valid": True},
                confidence=0.8,
                timestamp=i
            )
            history.append(frame)
        
        stability = self.validator._calculate_contact_stability(history)
        assert stability > 0.8  # Should be highly stable
    
    def test_confidence_trend_analysis(self):
        """Test confidence trend analysis."""
        # Increasing confidence trend
        increasing_values = [0.3, 0.4, 0.5, 0.6, 0.7]
        trend = self.validator._calculate_confidence_trend(increasing_values)
        assert trend == "increasing"
        
        # Decreasing confidence trend
        decreasing_values = [0.7, 0.6, 0.5, 0.4, 0.3]
        trend = self.validator._calculate_confidence_trend(decreasing_values)
        assert trend == "decreasing"


class TestBallTrajectoryAnalyzer:
    """Test suite for ball trajectory analysis."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            "trajectory_window": 10,
            "min_velocity_change": 50.0,
            "min_direction_change": 30.0
        }
        self.analyzer = BallTrajectoryAnalyzer(self.config)
    
    def test_initialization(self):
        """Test analyzer initialization."""
        assert self.analyzer.trajectory_window == 10
        assert self.analyzer.min_velocity_change == 50.0
        assert len(self.analyzer.trajectory_history) == 0
    
    def test_trajectory_point_creation(self):
        """Test trajectory point creation."""
        ball_data = {"center": [100, 150]}
        frame_number = 1
        
        point = self.analyzer._create_trajectory_point(ball_data, frame_number, None)
        
        assert point is not None
        assert point.position == (100.0, 150.0)
        assert point.frame_number == frame_number
    
    def test_velocity_calculation(self):
        """Test velocity calculation from position history."""
        # Add first point
        ball_data1 = {"center": [100, 150]}
        self.analyzer.analyze_trajectory(ball_data1, 0)
        
        # Add second point (moved right and down)
        ball_data2 = {"center": [120, 170]}
        result = self.analyzer.analyze_trajectory(ball_data2, 1)
        
        # Should have calculated velocity
        assert len(self.analyzer.trajectory_history) == 2
        last_point = self.analyzer.trajectory_history[-1]
        assert last_point.velocity[0] > 0  # Moving right
        assert last_point.velocity[1] > 0  # Moving down
    
    def test_contact_event_detection(self):
        """Test contact event detection from trajectory changes."""
        # Simulate trajectory with sudden velocity change
        positions = [(100, 150), (120, 170), (140, 190), (180, 200), (220, 210)]
        
        for i, pos in enumerate(positions):
            ball_data = {"center": list(pos)}
            self.analyzer.analyze_trajectory(ball_data, i)
        
        # Analyze for contact events
        recent_points = list(self.analyzer.trajectory_history)
        velocity_changes = self.analyzer._analyze_velocity_changes(recent_points)
        
        assert "significant_changes" in velocity_changes
        assert velocity_changes["max_change"] > 0
    
    def test_dig_trajectory_validation(self):
        """Test trajectory validation for dig action."""
        # Simulate upward trajectory after contact
        analysis = {
            "velocity_analysis": {"is_accelerating": True},
            "contact_detection": {"contact_detected": True}
        }
        
        # Mock trajectory with upward motion
        from src.recognition.ball_trajectory_analyzer import TrajectoryPoint
        upward_point = TrajectoryPoint(
            position=(100, 150),
            velocity=(10, -20),  # Negative Y is upward
            timestamp=1.0,
            frame_number=1
        )
        self.analyzer.trajectory_history.append(upward_point)
        
        result = self.analyzer._validate_dig_trajectory(analysis)
        
        assert result["action_type"] == "dig"
        assert result["upward_motion"] is True
    
    def test_physics_validation(self):
        """Test physics validation of trajectory."""
        # Create realistic trajectory points
        points = [
            (100, 100), (110, 105), (120, 112), (130, 121), (140, 132)
        ]
        
        for i, pos in enumerate(points):
            ball_data = {"center": list(pos)}
            self.analyzer.analyze_trajectory(ball_data, i)
        
        physics = self.analyzer._validate_trajectory_physics()
        
        assert "valid" in physics
        assert "confidence" in physics


class TestCourtPositionValidator:
    """Test suite for court position validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            "enabled": True,
            "serve_boundary_margin": 50
        }
        self.validator = CourtPositionValidator(self.config)
        
        # Set up mock court boundaries
        court_boundaries = {
            "bounds": {
                "left": 200,
                "right": 800,
                "top": 100,
                "bottom": 500
            }
        }
        self.validator.set_court_boundaries(court_boundaries)
    
    def test_initialization(self):
        """Test validator initialization."""
        assert self.validator.court_enabled is True
        assert self.validator.serve_boundary_margin == 50
    
    def test_court_region_determination(self):
        """Test court region determination."""
        # Front court position
        front_position = (400, 200)
        region = self.validator._determine_player_region(front_position)
        assert region == "front_court"
        
        # Back court position
        back_position = (400, 450)
        region = self.validator._determine_player_region(back_position)
        assert region == "back_court"
        
        # Serving area position
        serve_position = (400, 520)
        region = self.validator._determine_player_region(serve_position)
        assert region == "serving_area"
    
    def test_serve_position_validation(self):
        """Test serve position validation."""
        # Valid serve position (behind baseline)
        serve_position = (400, 520)
        result = self.validator.validate_serve_position(serve_position)
        
        assert result["valid"] is True
        assert "baseline" in result["details"]["validations"]
        assert "court_width" in result["details"]["validations"]
    
    def test_behind_baseline_validation(self):
        """Test behind baseline validation."""
        # Position behind baseline
        behind_position = (400, 520)
        result = self.validator._validate_behind_baseline(behind_position)
        
        assert result["valid"] is True
        assert result["behind_baseline"] is True
        
        # Position in front of baseline
        front_position = (400, 400)
        result = self.validator._validate_behind_baseline(front_position)
        
        assert result["valid"] is False
        assert result["behind_baseline"] is False
    
    def test_action_region_validation(self):
        """Test action validation for different court regions."""
        # Spike in front court (should be valid)
        result = self.validator._validate_action_for_region(
            VolleyballAction.SPIKE, "front_court"
        )
        assert result["valid"] is True
        
        # Serve in serving area (should be valid)
        result = self.validator._validate_action_for_region(
            VolleyballAction.SERVE, "serving_area"
        )
        assert result["valid"] is True
        
        # Serve in front court (should be invalid)
        result = self.validator._validate_action_for_region(
            VolleyballAction.SERVE, "front_court"
        )
        assert result["valid"] is False


class TestEnhancedActionClassifier:
    """Test suite for enhanced action classifier integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock pose estimator
        self.pose_estimator = Mock(spec=PoseEstimator)
        
        # Enhanced validation config
        self.config = {
            "enabled": True,
            "strict_mode": True,
            "ball_contact": {"min_contact_confidence": 0.7},
            "temporal": {"window_size": 5},
            "trajectory": {"trajectory_window": 10},
            "court": {"enabled": True}
        }
        
        self.classifier = ActionClassifier(
            pose_estimator=self.pose_estimator,
            enhanced_validation_config=self.config
        )
    
    def test_initialization_with_enhanced_validation(self):
        """Test classifier initialization with enhanced validation."""
        assert self.classifier.enhanced_validation_enabled is True
        assert self.classifier.ball_contact_validator is not None
        assert self.classifier.temporal_validator is not None
        assert self.classifier.trajectory_analyzer is not None
        assert self.classifier.court_validator is not None
    
    def test_enhanced_classification_with_valid_contact(self):
        """Test enhanced classification with valid ball contact."""
        # Mock pose estimator to return valid pose
        mock_pose = self._create_mock_pose_data()
        self.pose_estimator.estimate_poses_batch.return_value = [mock_pose]
        
        # Prepare test data
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        player_detections = [{
            "track_id": 1,
            "bbox": [100, 50, 250, 300],
            "confidence": 0.8
        }]
        ball_info = {"center": [175, 180], "velocity": [10, -5]}
        
        # Test classification
        results = self.classifier.classify_actions(
            frame, player_detections, ball_info, frame_number=1
        )
        
        assert len(results) > 0
        result = results[0]
        assert "enhanced_validation_enabled" in result
        assert "validation_results" in result
        assert "enhanced_confidence" in result
    
    def test_enhanced_confidence_calculation(self):
        """Test enhanced confidence calculation."""
        base_confidence = 0.7
        validation_results = {
            "ball_contact": {"valid": True, "confidence": 0.8},
            "temporal_contact": {"valid": True, "confidence": 0.7},
            "court_position": {"valid": True, "confidence": 0.9}
        }
        
        enhanced_confidence = self.classifier._calculate_enhanced_confidence(
            base_confidence, validation_results, VolleyballAction.DIG
        )
        
        assert 0.0 <= enhanced_confidence <= 1.0
        assert enhanced_confidence > base_confidence * 0.5  # Should be reasonable
    
    def test_action_validity_determination(self):
        """Test action validity determination."""
        # Valid case
        valid_results = {
            "ball_contact": {"valid": True, "confidence": 0.8},
            "temporal_contact": {"valid": True, "confidence": 0.7}
        }
        is_valid = self.classifier._determine_action_validity(
            valid_results, VolleyballAction.DIG
        )
        assert is_valid is True
        
        # Invalid case (no ball contact)
        invalid_results = {
            "ball_contact": {"valid": False, "confidence": 0.2},
            "temporal_contact": {"valid": False, "confidence": 0.1}
        }
        is_valid = self.classifier._determine_action_validity(
            invalid_results, VolleyballAction.DIG
        )
        assert is_valid is False
    
    def test_strict_mode_filtering(self):
        """Test strict mode action filtering."""
        # Set up classifier with strict mode
        self.config["strict_mode"] = True
        classifier = ActionClassifier(
            pose_estimator=self.pose_estimator,
            enhanced_validation_config=self.config
        )
        
        # Mock classification to return invalid action
        with patch.object(classifier, '_classify_player_action') as mock_classify:
            mock_classify.return_value = {
                "action": "dig",
                "confidence": 0.8,
                "features": {},
                "action_scores": {}
            }
            
            with patch.object(classifier, '_determine_action_validity') as mock_validity:
                mock_validity.return_value = False  # Invalid action
                
                result = classifier._classify_player_action_enhanced(
                    track_id=1,
                    detection={"bbox": [100, 50, 250, 300]},
                    pose_data=self._create_mock_pose_data(),
                    ball_info={"center": [500, 500]},  # Far from player
                    frame_number=1
                )
                
                # Should be filtered out in strict mode
                assert result["action"] == "unknown"
                assert result["confidence"] <= 0.1
    
    def test_validation_statistics(self):
        """Test validation statistics retrieval."""
        stats = self.classifier.get_validation_statistics()
        
        assert "enhanced_validation_enabled" in stats
        assert stats["enhanced_validation_enabled"] is True
        assert "temporal_validation" in stats
        assert "trajectory_analysis" in stats
        assert "court_validation" in stats
    
    def _create_mock_pose_data(self) -> Dict[str, Any]:
        """Create mock pose data for testing."""
        return {
            "keypoints": [{"x": 100 + i*10, "y": 100 + i*5, "visibility": 0.8} for i in range(33)],
            "keypoints_dict": {
                11: {"x": 150, "y": 100, "visibility": 0.9},
                12: {"x": 200, "y": 100, "visibility": 0.9},
                15: {"x": 140, "y": 180, "visibility": 0.9},
                16: {"x": 210, "y": 185, "visibility": 0.9},
                23: {"x": 160, "y": 250, "visibility": 0.9},
                24: {"x": 190, "y": 250, "visibility": 0.9},
            },
            "pose_features": {
                "left_arm_height": 180,
                "right_arm_height": 185,
                "body_lean": 10,
                "left_arm_angle": 120,
                "right_arm_angle": 115
            },
            "track_id": 1,
            "bbox": [100, 50, 250, 300]
        }


# Integration tests
class TestEnhancedActionRecognitionIntegration:
    """Integration tests for the complete enhanced action recognition system."""
    
    def setup_method(self):
        """Set up integration test fixtures."""
        self.pose_estimator = Mock(spec=PoseEstimator)
        
        self.config = {
            "enabled": True,
            "strict_mode": False,  # More lenient for integration tests
            "ball_contact": {"min_contact_confidence": 0.5},
            "temporal": {"window_size": 3, "min_frames_in_contact": 2},
            "trajectory": {"trajectory_window": 5},
            "court": {"enabled": True}
        }
        
        self.classifier = ActionClassifier(
            pose_estimator=self.pose_estimator,
            enhanced_validation_config=self.config
        )
    
    def test_complete_dig_scenario(self):
        """Test complete dig action scenario with all validation modules."""
        # Set up court boundaries
        court_info = {
            "boundaries": {
                "bounds": {"left": 200, "right": 800, "top": 100, "bottom": 500}
            }
        }
        
        # Mock pose data for dig action
        mock_pose = {
            "keypoints_dict": {
                11: {"x": 400, "y": 200, "visibility": 0.9},  # Shoulders
                12: {"x": 450, "y": 200, "visibility": 0.9},
                15: {"x": 380, "y": 280, "visibility": 0.9},  # Arms low for dig
                16: {"x": 470, "y": 285, "visibility": 0.9},
                23: {"x": 410, "y": 350, "visibility": 0.9},  # Hips
                24: {"x": 440, "y": 350, "visibility": 0.9},
            },
            "pose_features": {
                "left_arm_height": 280,
                "right_arm_height": 285,
                "body_lean": 25,  # Forward lean for dig
            },
            "bbox": [350, 150, 500, 400]
        }
        
        self.pose_estimator.estimate_poses_batch.return_value = [mock_pose]
        
        # Simulate dig scenario over multiple frames
        frame = np.zeros((600, 1000, 3), dtype=np.uint8)
        player_detections = [{
            "track_id": 1,
            "bbox": [350, 150, 500, 400],
            "confidence": 0.8
        }]
        
        # Ball trajectory for dig (coming down, then going up)
        ball_trajectories = [
            {"center": [425, 240], "velocity": [5, 15]},   # Ball coming down
            {"center": [430, 255], "velocity": [3, 12]},   # Slowing down
            {"center": [433, 265], "velocity": [2, -8]},   # Contact and upward
            {"center": [435, 257], "velocity": [1, -15]},  # Ball going up
        ]
        
        results = []
        for frame_num, ball_info in enumerate(ball_trajectories):
            result = self.classifier.classify_actions(
                frame, player_detections, ball_info, 
                frame_number=frame_num, court_info=court_info
            )
            if result:
                results.append(result[0])
        
        # Verify final result shows enhanced validation
        if results:
            final_result = results[-1]
            assert "validation_results" in final_result
            assert "enhanced_confidence" in final_result
            
            # Check that validation modules were engaged
            validation = final_result["validation_results"]
            assert "ball_contact" in validation or "temporal_contact" in validation
    
    def test_serve_position_validation_integration(self):
        """Test serve action with court position validation."""
        # Set up court with serving area
        court_info = {
            "boundaries": {
                "bounds": {"left": 200, "right": 800, "top": 100, "bottom": 500}
            }
        }
        
        # Player behind baseline (valid serve position)
        mock_pose = {
            "keypoints_dict": {
                11: {"x": 400, "y": 300, "visibility": 0.9},
                12: {"x": 450, "y": 300, "visibility": 0.9},
                15: {"x": 380, "y": 250, "visibility": 0.9},  # High arm for serve
                16: {"x": 470, "y": 245, "visibility": 0.9},
                23: {"x": 410, "y": 450, "visibility": 0.9},
                24: {"x": 440, "y": 450, "visibility": 0.9},
            },
            "pose_features": {
                "left_arm_height": 250,
                "right_arm_height": 245,
                "arm_height_stability": 60,  # Variable for serve
            },
            "bbox": [350, 250, 500, 550]
        }
        
        self.pose_estimator.estimate_poses_batch.return_value = [mock_pose]
        
        # Serve scenario
        frame = np.zeros((600, 1000, 3), dtype=np.uint8)
        player_detections = [{
            "track_id": 1,
            "bbox": [350, 250, 500, 550],  # Player behind baseline
            "confidence": 0.8
        }]
        ball_info = {"center": [425, 320], "velocity": [10, -5]}  # Ball near player
        
        results = self.classifier.classify_actions(
            frame, player_detections, ball_info, 
            frame_number=0, court_info=court_info
        )
        
        assert len(results) > 0
        result = results[0]
        
        # Should have court validation results
        if "validation_results" in result:
            validation = result["validation_results"]
            if "court_position" in validation:
                assert validation["court_position"]["valid"] is True
            if "serve_position" in validation:
                assert validation["serve_position"]["valid"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])