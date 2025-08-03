"""
Motion-based ball tracker for reducing template matching false positives.

This module implements physics-aware ball tracking that distinguishes real volleyballs
from t-shirt patterns and background objects using optical flow and trajectory validation.
"""

import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import deque
import math


class MotionBallTracker:
    """
    Physics-aware ball tracker that filters template detections using motion analysis.
    
    Combines Wilson template matching with optical flow tracking and gravity-based
    trajectory validation to eliminate false positives on clothing and static objects.
    """

    def __init__(
        self,
        trajectory_window: int = 5,
        min_velocity: float = 5.0,  # m/s (pixels/frame * fps conversion)
        max_velocity: float = 30.0,  # m/s 
        gravity_tolerance: float = 0.3,  # ±30% tolerance for gravity acceleration
        motion_weight: float = 0.6,  # Weight for motion score vs template confidence
        min_movement: float = 10.0,  # Minimum pixels/frame to exclude static objects
        fps: float = 30.0  # Frames per second for velocity calculations
    ):
        """
        Initialize motion-based ball tracker.

        Args:
            trajectory_window: Number of frames to analyze for motion patterns
            min_velocity: Minimum velocity for valid volleyball (m/s)
            max_velocity: Maximum velocity for valid volleyball (m/s)
            gravity_tolerance: Tolerance for gravity acceleration validation
            motion_weight: Weight for motion score in final scoring
            min_movement: Minimum movement to exclude static objects (pixels/frame)
            fps: Video frame rate for velocity calculations
        """
        self.trajectory_window = trajectory_window
        self.min_velocity = min_velocity
        self.max_velocity = max_velocity
        self.gravity_tolerance = gravity_tolerance
        self.motion_weight = motion_weight
        self.template_weight = 1.0 - motion_weight
        self.min_movement = min_movement
        self.fps = fps
        
        self.logger = logging.getLogger(__name__)
        
        # Track candidate detections across frames
        self.candidate_tracks = {}  # track_id -> detection history
        self.next_track_id = 0
        self.max_track_age = trajectory_window * 2
        
        # Optical flow parameters
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        
        # Previous frame for optical flow
        self.prev_frame = None
        
        # Physics constants
        self.gravity_px_per_frame2 = self._calculate_gravity_pixels()
        
        self.logger.info("Motion-based ball tracker initialized")

    def _calculate_gravity_pixels(self) -> float:
        """
        Calculate gravity acceleration in pixels per frame squared.
        
        Assumes typical volleyball court dimensions and camera setup.
        Court height ~8m, typical frame height ~1080px, fps=30.
        
        Returns:
            Gravity acceleration in pixels/frame²
        """
        # Rough conversion: 1 meter ≈ 135 pixels (1080px / 8m court height)
        pixels_per_meter = 135
        gravity_m_per_s2 = 9.81
        
        # Convert to pixels per frame²
        gravity_px_per_s2 = gravity_m_per_s2 * pixels_per_meter
        gravity_px_per_frame2 = gravity_px_per_s2 / (self.fps ** 2)
        
        self.logger.debug(f"Gravity: {gravity_px_per_frame2:.2f} pixels/frame²")
        return gravity_px_per_frame2

    def filter_detections(
        self, 
        template_detections: List[Dict[str, Any]], 
        frame: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        Filter template detections using motion analysis and physics validation.

        Args:
            template_detections: Raw detections from Wilson template matching
            frame: Current video frame

        Returns:
            Filtered detections with motion scores
        """
        if not template_detections:
            return []

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Update candidate tracks with new detections
        self._update_tracks(template_detections, gray_frame)
        
        # Age out old tracks
        self._cleanup_old_tracks()
        
        # Validate tracks using motion analysis
        validated_detections = self._validate_tracks_motion()
        
        # Store current frame for next iteration
        self.prev_frame = gray_frame.copy()
        
        return validated_detections

    def _update_tracks(self, detections: List[Dict[str, Any]], gray_frame: np.ndarray) -> None:
        """Update candidate tracks with new detections using improved matching."""
        if self.prev_frame is None:
            # First frame - initialize tracks
            for detection in detections:
                track_id = self.next_track_id
                self.next_track_id += 1
                
                self.candidate_tracks[track_id] = {
                    'detections': deque([detection], maxlen=self.trajectory_window),
                    'positions': deque([detection['center']], maxlen=self.trajectory_window),
                    'timestamps': deque([0], maxlen=self.trajectory_window),  # Frame indices
                    'age': 1,
                    'motion_score': 0.0,
                    'last_matched_frame': 0,
                    'template_consistency': [detection.get('template_name', 'unknown')]
                }
            return

        # Enhanced track matching with motion prediction and consistency scoring
        matched_tracks = set()
        detection_track_scores = []  # (detection_idx, track_id, score)
        
        for det_idx, detection in enumerate(detections):
            center = detection['center']
            template_name = detection.get('template_name', 'unknown')
            template_conf = detection.get('confidence', 0.0)
            
            # Calculate matching scores for all tracks
            for track_id, track_data in self.candidate_tracks.items():
                if track_id in matched_tracks:
                    continue
                
                # Skip tracks that were matched too recently (prevent rapid switching)
                frames_since_match = track_data['timestamps'][-1] - track_data.get('last_matched_frame', -999)
                if frames_since_match < 2:  # Must wait at least 2 frames before switching
                    continue
                    
                score = self._calculate_track_match_score(
                    detection, track_data, center, template_name, template_conf
                )
                
                if score > 0.3:  # Minimum matching threshold
                    detection_track_scores.append((det_idx, track_id, score))
        
        # Sort by score and assign best matches
        detection_track_scores.sort(key=lambda x: x[2], reverse=True)
        
        used_detections = set()
        
        for det_idx, track_id, score in detection_track_scores:
            if det_idx in used_detections or track_id in matched_tracks:
                continue
                
            # Update existing track
            detection = detections[det_idx]
            track_data = self.candidate_tracks[track_id]
            
            track_data['detections'].append(detection)
            track_data['positions'].append(detection['center'])
            track_data['timestamps'].append(track_data['timestamps'][-1] + 1)
            track_data['age'] += 1
            track_data['last_matched_frame'] = track_data['timestamps'][-1]
            track_data['template_consistency'].append(detection.get('template_name', 'unknown'))
            
            matched_tracks.add(track_id)
            used_detections.add(det_idx)
        
        # Create new tracks for unmatched detections
        for det_idx, detection in enumerate(detections):
            if det_idx not in used_detections:
                track_id = self.next_track_id
                self.next_track_id += 1
                
                self.candidate_tracks[track_id] = {
                    'detections': deque([detection], maxlen=self.trajectory_window),
                    'positions': deque([detection['center']], maxlen=self.trajectory_window),
                    'timestamps': deque([0], maxlen=self.trajectory_window),
                    'age': 1,
                    'motion_score': 0.0,
                    'last_matched_frame': 0,
                    'template_consistency': [detection.get('template_name', 'unknown')]
                }

    def _calculate_track_match_score(
        self, 
        detection: Dict[str, Any], 
        track_data: Dict[str, Any],
        center: List[float],
        template_name: str,
        template_conf: float
    ) -> float:
        """Calculate comprehensive matching score between detection and track."""
        scores = []
        
        # 1. Distance score (most important for continuity)
        last_pos = track_data['positions'][-1]
        distance = np.sqrt((center[0] - last_pos[0])**2 + (center[1] - last_pos[1])**2)
        
        # Predict next position if track has motion history
        if len(track_data['positions']) >= 2:
            velocity = self._calculate_current_velocity(track_data)
            predicted_pos = [last_pos[0] + velocity[0], last_pos[1] + velocity[1]]
            predicted_distance = np.sqrt((center[0] - predicted_pos[0])**2 + (center[1] - predicted_pos[1])**2)
            distance = min(distance, predicted_distance)  # Use best of actual or predicted
        
        # Distance scoring: closer = better, but penalize very large jumps
        if distance > 150:  # Reject very large jumps
            return 0.0
        elif distance < 20:  # Very close
            distance_score = 1.0
        else:
            distance_score = max(0.0, 1.0 - (distance - 20) / 130)  # Linear decay
        scores.append(('distance', distance_score, 0.5))
        
        # 2. Template consistency score
        recent_templates = list(track_data['template_consistency'])[-3:]  # Last 3 templates
        if recent_templates:
            template_consistency = recent_templates.count(template_name) / len(recent_templates)
        else:
            template_consistency = 0.5
        scores.append(('template', template_consistency, 0.2))
        
        # 3. Motion consistency score
        motion_score = track_data.get('motion_score', 0.0)
        if motion_score > 0.5:  # Strong motion tracks get priority
            motion_consistency = 1.0
        elif motion_score > 0.2:
            motion_consistency = 0.7
        else:
            motion_consistency = 0.3
        scores.append(('motion', motion_consistency, 0.2))
        
        # 4. Track maturity bonus (older tracks are more stable)
        track_age = track_data['age']
        if track_age >= 5:
            maturity_bonus = 1.0
        elif track_age >= 3:
            maturity_bonus = 0.8
        else:
            maturity_bonus = 0.5
        scores.append(('maturity', maturity_bonus, 0.1))
        
        # Calculate weighted score
        total_score = sum(score * weight for _, score, weight in scores)
        
        self.logger.debug(f"Track match scores: {scores} -> {total_score:.3f}")
        return total_score
    
    def _cleanup_old_tracks(self) -> None:
        """Remove tracks that are too old or haven't been updated."""
        tracks_to_remove = []
        current_frame = max([track['timestamps'][-1] for track in self.candidate_tracks.values()]) if self.candidate_tracks else 0
        
        for track_id, track_data in self.candidate_tracks.items():
            # Remove tracks that haven't been updated in many frames
            frames_since_update = current_frame - track_data['timestamps'][-1]
            if frames_since_update > 10 or track_data['age'] > self.max_track_age:
                tracks_to_remove.append(track_id)
        
        for track_id in tracks_to_remove:
            del self.candidate_tracks[track_id]
            self.logger.debug(f"Removed old track {track_id}")

    def _validate_tracks_motion(self) -> List[Dict[str, Any]]:
        """Validate tracks using motion analysis and physics."""
        validated_detections = []
        
        for track_id, track_data in self.candidate_tracks.items():
            # Skip tracks with no recent activity
            if len(track_data['positions']) < 1:
                continue
            
            # Calculate motion score
            motion_score = self._calculate_motion_score(track_data)
            track_data['motion_score'] = motion_score
            
            # Get latest detection
            latest_detection = track_data['detections'][-1].copy()
            
            # Enhanced scoring with track persistence bonus
            template_confidence = latest_detection['confidence']
            track_length = len(track_data['positions'])
            track_age = track_data['age']
            
            # Calculate track persistence score
            persistence_score = self._calculate_track_persistence_score(track_data)
            
            # Multi-factor scoring
            if track_length < 3:
                # New tracks: primarily template confidence with small motion bonus
                final_score = (0.8 * template_confidence + 
                              0.1 * motion_score + 
                              0.1 * persistence_score)
            elif track_length < 6:
                # Growing tracks: balanced scoring
                final_score = (0.4 * template_confidence + 
                              0.4 * motion_score + 
                              0.2 * persistence_score)
            else:
                # Mature tracks: prioritize consistency and motion
                final_score = (0.2 * template_confidence + 
                              0.5 * motion_score + 
                              0.3 * persistence_score)
            
            # Add motion analysis results to detection
            latest_detection.update({
                'motion_score': motion_score,
                'template_confidence': template_confidence,
                'persistence_score': persistence_score,
                'final_confidence': final_score,
                'track_id': track_id,
                'track_length': track_length,
                'track_age': track_age,
                'velocity': self._calculate_current_velocity(track_data),
                'acceleration': self._calculate_current_acceleration(track_data)
            })
            
            # Apply validation thresholds based on track maturity
            should_include = False
            
            if track_length < 3:
                # New tracks: lenient threshold
                should_include = final_score > 0.3
            elif track_length < 6:
                # Growing tracks: moderate threshold  
                should_include = final_score > 0.4 or motion_score > 0.2
            else:
                # Mature tracks: require good motion or very high template confidence
                should_include = motion_score > 0.25 or template_confidence > 0.9
            
            if should_include:
                validated_detections.append(latest_detection)
            
            self.logger.debug(f"Track {track_id}: motion={motion_score:.3f}, template={template_confidence:.3f}, persistence={persistence_score:.3f}, final={final_score:.3f}, age={track_age}, included={should_include}")
        
        # Sort by final confidence and return top detections
        validated_detections.sort(key=lambda x: x['final_confidence'], reverse=True)
        
        # Limit to top 2 detections but prefer mature tracks
        if len(validated_detections) > 2:
            # Prioritize mature tracks in top 2
            mature_tracks = [d for d in validated_detections if d['track_length'] >= 5]
            immature_tracks = [d for d in validated_detections if d['track_length'] < 5]
            
            validated_detections = (mature_tracks[:1] + immature_tracks[:1])[:2]
        
        return validated_detections

    def _calculate_track_persistence_score(self, track_data: Dict[str, Any]) -> float:
        """Calculate track persistence score based on consistency and longevity."""
        track_length = len(track_data['positions'])
        track_age = track_data['age']
        
        # Length score: longer tracks are more persistent
        if track_length >= 5:
            length_score = 1.0
        elif track_length >= 3:
            length_score = 0.7
        else:
            length_score = 0.3
        
        # Template consistency score
        templates = track_data.get('template_consistency', [])
        if len(templates) > 1:
            most_common_template = max(set(templates), key=templates.count)
            consistency_ratio = templates.count(most_common_template) / len(templates)
        else:
            consistency_ratio = 1.0
        
        # Age bonus: older tracks are more established
        if track_age >= 8:
            age_score = 1.0
        elif track_age >= 5:
            age_score = 0.8
        else:
            age_score = 0.5
        
        # Combine scores
        persistence_score = (0.4 * length_score + 0.4 * consistency_ratio + 0.2 * age_score)
        return min(1.0, persistence_score)

    def _calculate_motion_score(self, track_data: Dict[str, Any]) -> float:
        """
        Calculate motion score based on physics validation.
        
        Returns:
            Motion score between 0 and 1 (1 = perfect volleyball motion)
        """
        positions = list(track_data['positions'])
        if len(positions) < 3:
            return 0.0
        
        scores = []
        
        # 1. Velocity validation
        velocity_score = self._validate_velocity(positions)
        scores.append(velocity_score)
        
        # 2. Movement validation (exclude static objects)
        movement_score = self._validate_movement(positions)
        scores.append(movement_score)
        
        # 3. Trajectory smoothness (volleyballs have smooth trajectories)
        smoothness_score = self._validate_trajectory_smoothness(positions)
        scores.append(smoothness_score)
        
        # 4. Gravity validation (if enough points)
        if len(positions) >= 4:
            gravity_score = self._validate_gravity(positions)
            scores.append(gravity_score)
        
        # 5. Direction consistency (balls don't change direction rapidly like humans)
        direction_score = self._validate_direction_consistency(positions)
        scores.append(direction_score)
        
        # Weighted average of all scores
        weights = [0.3, 0.2, 0.2, 0.2, 0.1][:len(scores)]  # Adjust weights based on available scores
        
        weighted_score = sum(score * weight for score, weight in zip(scores, weights))
        return min(1.0, max(0.0, weighted_score))

    def _validate_velocity(self, positions: List[List[float]]) -> float:
        """Validate velocity is in reasonable range for volleyballs."""
        velocities = []
        
        for i in range(1, len(positions)):
            prev_pos = positions[i-1]
            curr_pos = positions[i]
            
            # Calculate velocity in pixels per frame
            velocity_px = np.sqrt((curr_pos[0] - prev_pos[0])**2 + (curr_pos[1] - prev_pos[1])**2)
            
            # Convert to m/s (rough conversion)
            velocity_ms = velocity_px * self.fps / 135  # 135 pixels ≈ 1 meter
            velocities.append(velocity_ms)
        
        if not velocities:
            return 0.0
        
        avg_velocity = np.mean(velocities)
        
        # Score based on volleyball velocity range
        if self.min_velocity <= avg_velocity <= self.max_velocity:
            return 1.0
        elif avg_velocity < self.min_velocity:
            # Penalize slow movement (likely human/static)
            return max(0.0, avg_velocity / self.min_velocity)
        else:
            # Penalize excessive speed
            return max(0.0, 1.0 - (avg_velocity - self.max_velocity) / self.max_velocity)

    def _validate_movement(self, positions: List[List[float]]) -> float:
        """Validate object is moving sufficiently to be a ball."""
        if len(positions) < 2:
            return 0.0
        
        total_movement = 0.0
        for i in range(1, len(positions)):
            prev_pos = positions[i-1]
            curr_pos = positions[i]
            movement = np.sqrt((curr_pos[0] - prev_pos[0])**2 + (curr_pos[1] - prev_pos[1])**2)
            total_movement += movement
        
        avg_movement = total_movement / (len(positions) - 1)
        
        # Score based on minimum movement threshold
        if avg_movement >= self.min_movement:
            return 1.0
        else:
            return avg_movement / self.min_movement

    def _validate_trajectory_smoothness(self, positions: List[List[float]]) -> float:
        """Validate trajectory smoothness (balls have smoother motion than humans)."""
        if len(positions) < 3:
            return 0.5  # Neutral score
        
        # Calculate direction changes
        direction_changes = []
        
        for i in range(2, len(positions)):
            # Vectors for consecutive segments
            v1 = [positions[i-1][0] - positions[i-2][0], positions[i-1][1] - positions[i-2][1]]
            v2 = [positions[i][0] - positions[i-1][0], positions[i][1] - positions[i-1][1]]
            
            # Calculate angle between vectors
            dot_product = v1[0]*v2[0] + v1[1]*v2[1]
            magnitude1 = np.sqrt(v1[0]**2 + v1[1]**2)
            magnitude2 = np.sqrt(v2[0]**2 + v2[1]**2)
            
            if magnitude1 > 0 and magnitude2 > 0:
                cos_angle = dot_product / (magnitude1 * magnitude2)
                cos_angle = max(-1, min(1, cos_angle))  # Clamp to valid range
                angle = math.acos(cos_angle)
                direction_changes.append(angle)
        
        if not direction_changes:
            return 0.5
        
        # Lower average direction change = smoother trajectory = higher score
        avg_direction_change = np.mean(direction_changes)
        smoothness_score = max(0.0, 1.0 - avg_direction_change / math.pi)
        
        return smoothness_score

    def _validate_gravity(self, positions: List[List[float]]) -> float:
        """Validate trajectory follows gravity (parabolic motion)."""
        if len(positions) < 4:
            return 0.5  # Neutral score
        
        # Calculate vertical accelerations
        accelerations = []
        
        for i in range(2, len(positions)):
            # Get three consecutive Y positions
            y1, y2, y3 = positions[i-2][1], positions[i-1][1], positions[i][1]
            
            # Calculate acceleration (second derivative)
            acceleration = (y3 - 2*y2 + y1)  # In pixels/frame²
            accelerations.append(acceleration)
        
        if not accelerations:
            return 0.5
        
        avg_acceleration = np.mean(accelerations)
        
        # Compare with expected gravity acceleration
        expected_gravity = self.gravity_px_per_frame2
        gravity_error = abs(avg_acceleration - expected_gravity) / expected_gravity
        
        # Score based on gravity tolerance
        if gravity_error <= self.gravity_tolerance:
            gravity_score = 1.0 - (gravity_error / self.gravity_tolerance)
        else:
            gravity_score = max(0.0, 1.0 - gravity_error)
        
        return gravity_score

    def _validate_direction_consistency(self, positions: List[List[float]]) -> float:
        """Validate direction consistency (balls don't zigzag like humans)."""
        if len(positions) < 3:
            return 0.5
        
        # Calculate overall direction vs local directions
        overall_direction = [
            positions[-1][0] - positions[0][0],
            positions[-1][1] - positions[0][1]
        ]
        overall_magnitude = np.sqrt(overall_direction[0]**2 + overall_direction[1]**2)
        
        if overall_magnitude == 0:
            return 0.0  # No movement
        
        # Normalize overall direction
        overall_unit = [overall_direction[0] / overall_magnitude, overall_direction[1] / overall_magnitude]
        
        # Calculate consistency with local directions
        consistencies = []
        
        for i in range(1, len(positions)):
            local_direction = [
                positions[i][0] - positions[i-1][0],
                positions[i][1] - positions[i-1][1]
            ]
            local_magnitude = np.sqrt(local_direction[0]**2 + local_direction[1]**2)
            
            if local_magnitude > 0:
                local_unit = [local_direction[0] / local_magnitude, local_direction[1] / local_magnitude]
                dot_product = overall_unit[0]*local_unit[0] + overall_unit[1]*local_unit[1]
                consistencies.append(max(0, dot_product))  # 0 to 1 range
        
        if not consistencies:
            return 0.5
        
        return np.mean(consistencies)

    def _calculate_current_velocity(self, track_data: Dict[str, Any]) -> Tuple[float, float]:
        """Calculate current velocity vector."""
        positions = list(track_data['positions'])
        if len(positions) < 2:
            return (0.0, 0.0)
        
        last_pos = positions[-1]
        prev_pos = positions[-2]
        
        velocity_x = last_pos[0] - prev_pos[0]
        velocity_y = last_pos[1] - prev_pos[1]
        
        return (velocity_x, velocity_y)

    def _calculate_current_acceleration(self, track_data: Dict[str, Any]) -> Tuple[float, float]:
        """Calculate current acceleration vector."""
        positions = list(track_data['positions'])
        if len(positions) < 3:
            return (0.0, 0.0)
        
        # Calculate acceleration from last three positions
        p1, p2, p3 = positions[-3], positions[-2], positions[-1]
        
        # Second derivative (acceleration)
        acc_x = p3[0] - 2*p2[0] + p1[0]
        acc_y = p3[1] - 2*p2[1] + p1[1]
        
        return (acc_x, acc_y)

    def get_track_statistics(self) -> Dict[str, Any]:
        """Get statistics about current tracks."""
        return {
            'active_tracks': len(self.candidate_tracks),
            'track_ages': [track['age'] for track in self.candidate_tracks.values()],
            'motion_scores': [track['motion_score'] for track in self.candidate_tracks.values()]
        }