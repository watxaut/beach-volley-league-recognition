"""
Pose estimator for volleyball video analysis.

This module implements pose estimation using MediaPipe to extract
human pose keypoints for action recognition.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2
import mediapipe as mp
import logging


class PoseEstimator:
    """Pose estimator using MediaPipe for volleyball action recognition.

    Extracts human pose keypoints from player bounding boxes to enable
    action classification and movement analysis.
    """

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 1
    ):
        """Initialize the pose estimator.

        Args:
            min_detection_confidence: Minimum confidence for pose detection
            min_tracking_confidence: Minimum confidence for pose tracking
            model_complexity: Model complexity (0, 1, or 2)
        """
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.model_complexity = model_complexity

        # Initialize MediaPipe pose
        # static_image_mode=False enables temporal smoothing across frames,
        # reducing keypoint jitter that causes false action detections.
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=model_complexity,
            enable_segmentation=False,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )

        # Define keypoint connections for volleyball-relevant body parts
        self.volleyball_keypoints = {
            'head': [0, 1, 2, 3, 4],  # Nose, eyes, ears
            'shoulders': [11, 12],     # Left/right shoulder
            'arms': [13, 14, 15, 16], # Elbows and wrists
            'torso': [11, 12, 23, 24], # Shoulders and hips
            'legs': [23, 24, 25, 26, 27, 28] # Hips, knees, ankles
        }

        self.logger = logging.getLogger(__name__)

    def estimate_pose(self, frame: np.ndarray, player_bbox: List[float]) -> Optional[Dict[str, Any]]:
        """Estimate pose for a single player in the frame.

        Args:
            frame: Input frame as numpy array
            player_bbox: Player bounding box [x1, y1, x2, y2]

        Returns:
            Pose estimation results or None if estimation failed
        """
        try:
            # Extract player region
            player_region = self._extract_player_region(frame, player_bbox)
            if player_region is None:
                return None

            # Convert BGR to RGB for MediaPipe
            rgb_region = cv2.cvtColor(player_region, cv2.COLOR_BGR2RGB)

            # Run pose estimation
            results = self.pose.process(rgb_region)

            if results.pose_landmarks is None:
                self.logger.debug("No pose landmarks detected")
                return None

            # Process pose landmarks
            pose_data = self._process_landmarks(results.pose_landmarks, player_bbox)

            return pose_data

        except Exception as e:
            self.logger.error(f"Pose estimation failed: {e}")
            return None

    def estimate_poses_batch(
        self,
        frame: np.ndarray,
        player_detections: List[Dict[str, Any]]
    ) -> List[Optional[Dict[str, Any]]]:
        """Estimate poses for multiple players in the frame.

        Args:
            frame: Input frame as numpy array
            player_detections: List of player detection dictionaries

        Returns:
            List of pose estimation results (None for failed estimations)
        """
        poses = []

        for detection in player_detections:
            bbox = detection.get("bbox", [])
            if len(bbox) == 4:
                pose_data = self.estimate_pose(frame, bbox)
                if pose_data:
                    pose_data["track_id"] = detection.get("track_id")
                poses.append(pose_data)
            else:
                poses.append(None)

        return poses

    def _extract_player_region(self, frame: np.ndarray, bbox: List[float]) -> Optional[np.ndarray]:
        """Extract player region from frame using bounding box.

        Args:
            frame: Input frame
            bbox: Bounding box [x1, y1, x2, y2]

        Returns:
            Extracted player region or None
        """
        if len(bbox) != 4:
            return None

        x1, y1, x2, y2 = map(int, bbox)
        h, w = frame.shape[:2]

        # Clamp coordinates to frame bounds
        x1 = max(0, min(x1, w))
        y1 = max(0, min(y1, h))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))

        if x2 <= x1 or y2 <= y1:
            return None

        return frame[y1:y2, x1:x2]

    def _process_landmarks(
        self,
        landmarks,
        player_bbox: List[float]
    ) -> Dict[str, Any]:
        """Process MediaPipe landmarks into usable format.

        Args:
            landmarks: MediaPipe pose landmarks
            player_bbox: Original player bounding box for coordinate transformation

        Returns:
            Processed pose data
        """
        x1, y1, x2, y2 = player_bbox
        bbox_width = x2 - x1
        bbox_height = y2 - y1

        # Extract keypoints
        keypoints = []
        keypoints_dict = {}

        for i, landmark in enumerate(landmarks.landmark):
            # Transform coordinates back to original frame
            x = x1 + landmark.x * bbox_width
            y = y1 + landmark.y * bbox_height
            z = landmark.z  # Relative depth
            visibility = landmark.visibility

            keypoint = {
                "x": float(x),
                "y": float(y),
                "z": float(z),
                "visibility": float(visibility)
            }

            keypoints.append(keypoint)
            keypoints_dict[i] = keypoint

        # Calculate body part positions
        body_parts = self._calculate_body_parts(keypoints_dict)

        # Calculate pose features
        pose_features = self._calculate_pose_features(keypoints_dict)

        return {
            "keypoints": keypoints,
            "keypoints_dict": keypoints_dict,
            "body_parts": body_parts,
            "pose_features": pose_features,
            "bbox": player_bbox
        }

    def _calculate_body_parts(self, keypoints_dict: Dict[int, Dict[str, float]]) -> Dict[str, Any]:
        """Calculate positions and orientations of major body parts.

        Args:
            keypoints_dict: Dictionary of keypoint ID to keypoint data

        Returns:
            Body part information
        """
        body_parts = {}

        # Calculate center points for each body part group
        for part_name, keypoint_ids in self.volleyball_keypoints.items():
            visible_points = []

            for kp_id in keypoint_ids:
                if kp_id in keypoints_dict:
                    kp = keypoints_dict[kp_id]
                    if kp["visibility"] > 0.5:  # Only use visible keypoints
                        visible_points.append([kp["x"], kp["y"]])

            if visible_points:
                center = np.mean(visible_points, axis=0)
                body_parts[part_name] = {
                    "center": center.tolist(),
                    "visible_points": len(visible_points),
                    "total_points": len(keypoint_ids)
                }

        return body_parts

    def _calculate_pose_features(self, keypoints_dict: Dict[int, Dict[str, float]]) -> Dict[str, float]:
        """Calculate volleyball-relevant pose features.

        All spatial features are normalized relative to the player's body
        (shoulder-to-hip distance) so they're independent of the player's
        distance from the camera.

        Args:
            keypoints_dict: Dictionary of keypoint data

        Returns:
            Calculated pose features
        """
        features = {}

        try:
            # Compute body reference measurements for normalization
            hip_y = None
            shoulder_y = None
            torso_height = None

            if all(kp_id in keypoints_dict for kp_id in [11, 12, 23, 24]):
                left_shoulder = keypoints_dict[11]
                right_shoulder = keypoints_dict[12]
                left_hip = keypoints_dict[23]
                right_hip = keypoints_dict[24]

                shoulder_y = (left_shoulder["y"] + right_shoulder["y"]) / 2
                hip_y = (left_hip["y"] + right_hip["y"]) / 2
                torso_height = abs(hip_y - shoulder_y)
                if torso_height < 1:
                    torso_height = 1  # prevent division by zero

                features["shoulder_width"] = abs(left_shoulder["x"] - right_shoulder["x"])
                features["body_lean"] = self._calculate_body_lean(keypoints_dict)

            # Arm angles (important for spiking, setting)
            if all(kp_id in keypoints_dict for kp_id in [11, 13, 15]):
                features["left_arm_angle"] = self._calculate_arm_angle(
                    keypoints_dict[11], keypoints_dict[13], keypoints_dict[15]
                )

            if all(kp_id in keypoints_dict for kp_id in [12, 14, 16]):
                features["right_arm_angle"] = self._calculate_arm_angle(
                    keypoints_dict[12], keypoints_dict[14], keypoints_dict[16]
                )

            # Normalized arm heights: wrist position relative to body
            # Positive = above shoulders, negative = below hips
            if torso_height and shoulder_y and hip_y:
                left_wrist_y = keypoints_dict.get(15, {}).get("y")
                right_wrist_y = keypoints_dict.get(16, {}).get("y")

                if left_wrist_y is not None:
                    # In image coords, y increases downward
                    # ratio > 1 means wrist above shoulders, < 0 means below hips
                    features["left_wrist_height_ratio"] = (hip_y - left_wrist_y) / torso_height
                if right_wrist_y is not None:
                    features["right_wrist_height_ratio"] = (hip_y - right_wrist_y) / torso_height

                # Average wrist height for symmetry detection
                if "left_wrist_height_ratio" in features and "right_wrist_height_ratio" in features:
                    features["avg_wrist_height_ratio"] = (
                        features["left_wrist_height_ratio"] + features["right_wrist_height_ratio"]
                    ) / 2
                    features["wrist_height_diff"] = abs(
                        features["left_wrist_height_ratio"] - features["right_wrist_height_ratio"]
                    )

                # Elbow height (normalized)
                left_elbow_y = keypoints_dict.get(13, {}).get("y")
                right_elbow_y = keypoints_dict.get(14, {}).get("y")
                if left_elbow_y is not None:
                    features["left_elbow_height_ratio"] = (hip_y - left_elbow_y) / torso_height
                if right_elbow_y is not None:
                    features["right_elbow_height_ratio"] = (hip_y - right_elbow_y) / torso_height

            # Legacy: raw arm height (kept for backward compat but should not be used)
            features["left_arm_height"] = keypoints_dict.get(15, {}).get("y", 0)
            features["right_arm_height"] = keypoints_dict.get(16, {}).get("y", 0)

            # Leg bend (important for jumping, digging)
            if all(kp_id in keypoints_dict for kp_id in [23, 25, 27]):
                features["left_leg_bend"] = self._calculate_leg_bend(
                    keypoints_dict[23], keypoints_dict[25], keypoints_dict[27]
                )

            if all(kp_id in keypoints_dict for kp_id in [24, 26, 28]):
                features["right_leg_bend"] = self._calculate_leg_bend(
                    keypoints_dict[24], keypoints_dict[26], keypoints_dict[28]
                )

        except Exception as e:
            self.logger.debug(f"Error calculating pose features: {e}")

        return features

    def _calculate_arm_angle(self, shoulder: Dict, elbow: Dict, wrist: Dict) -> float:
        """Calculate arm angle at elbow joint.

        Args:
            shoulder: Shoulder keypoint
            elbow: Elbow keypoint
            wrist: Wrist keypoint

        Returns:
            Arm angle in degrees
        """
        # Vector from elbow to shoulder
        v1 = np.array([shoulder["x"] - elbow["x"], shoulder["y"] - elbow["y"]])
        # Vector from elbow to wrist
        v2 = np.array([wrist["x"] - elbow["x"], wrist["y"] - elbow["y"]])

        # Calculate angle
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        angle = np.arccos(np.clip(cos_angle, -1, 1))

        return float(np.degrees(angle))

    def _calculate_leg_bend(self, hip: Dict, knee: Dict, ankle: Dict) -> float:
        """Calculate leg bend angle at knee joint.

        Args:
            hip: Hip keypoint
            knee: Knee keypoint
            ankle: Ankle keypoint

        Returns:
            Leg bend angle in degrees
        """
        # Vector from knee to hip
        v1 = np.array([hip["x"] - knee["x"], hip["y"] - knee["y"]])
        # Vector from knee to ankle
        v2 = np.array([ankle["x"] - knee["x"], ankle["y"] - knee["y"]])

        # Calculate angle
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        angle = np.arccos(np.clip(cos_angle, -1, 1))

        return float(np.degrees(angle))

    def _calculate_body_lean(self, keypoints_dict: Dict) -> float:
        """Calculate body lean angle from vertical.

        Args:
            keypoints_dict: Dictionary of keypoints

        Returns:
            Body lean angle in degrees
        """
        # Calculate center of shoulders and hips
        left_shoulder = keypoints_dict[11]
        right_shoulder = keypoints_dict[12]
        left_hip = keypoints_dict[23]
        right_hip = keypoints_dict[24]

        shoulder_center = [
            (left_shoulder["x"] + right_shoulder["x"]) / 2,
            (left_shoulder["y"] + right_shoulder["y"]) / 2
        ]

        hip_center = [
            (left_hip["x"] + right_hip["x"]) / 2,
            (left_hip["y"] + right_hip["y"]) / 2
        ]

        # Calculate lean from vertical
        body_vector = np.array([
            shoulder_center[0] - hip_center[0],
            shoulder_center[1] - hip_center[1]
        ])

        vertical_vector = np.array([0, -1])  # Pointing up

        cos_angle = np.dot(body_vector, vertical_vector) / (np.linalg.norm(body_vector) + 1e-6)
        angle = np.arccos(np.clip(cos_angle, -1, 1))

        return float(np.degrees(angle))
