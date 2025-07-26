"""
Player tracker for volleyball video analysis.

This module implements multi-object tracking for volleyball players,
maintaining consistent player identities across video frames.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2
from scipy.spatial.distance import cdist
from collections import defaultdict
import logging


class PlayerTracker:
    """Multi-object tracker for volleyball players.

    Maintains consistent player identities across frames using a combination
    of spatial proximity and appearance features.
    """

    def __init__(
        self,
        max_disappeared: int = 30,
        max_distance: float = 100.0,
        iou_threshold: float = 0.3
    ):
        """Initialize the player tracker.

        Args:
            max_disappeared: Maximum frames a player can disappear before being removed
            max_distance: Maximum distance for associating detections with tracks
            iou_threshold: Minimum IoU for track association
        """
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.iou_threshold = iou_threshold

        # Tracking state
        self.next_id = 0
        self.tracks = {}  # track_id -> track_info
        self.disappeared = defaultdict(int)

        self.logger = logging.getLogger(__name__)

    def update(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Update tracker with new detections.

        Args:
            detections: List of player detections from current frame

        Returns:
            List of tracked players with consistent IDs
        """
        # If no existing tracks, initialize with current detections
        if len(self.tracks) == 0:
            return self._initialize_tracks(detections)

        # If no detections, mark all tracks as disappeared
        if len(detections) == 0:
            return self._handle_no_detections()

        # Associate detections with existing tracks
        return self._associate_detections(detections)

    def _initialize_tracks(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Initialize tracks with first set of detections.

        Args:
            detections: Initial player detections

        Returns:
            Tracked players with assigned IDs
        """
        tracked_players = []

        for detection in detections:
            track_id = self.next_id
            self.next_id += 1

            # Create track record
            track_info = {
                "bbox": detection["bbox"],
                "center": detection["center"],
                "confidence": detection["confidence"],
                "last_seen": 0,
                "history": [detection["center"]]
            }
            self.tracks[track_id] = track_info

            # Add track ID to detection
            tracked_detection = detection.copy()
            tracked_detection["track_id"] = track_id
            tracked_players.append(tracked_detection)

        self.logger.debug(f"Initialized {len(tracked_players)} tracks")
        return tracked_players

    def _handle_no_detections(self) -> List[Dict[str, Any]]:
        """Handle frame with no detections.

        Returns:
            Empty list and updates disappeared counters
        """
        # Increment disappeared counter for all tracks
        for track_id in list(self.tracks.keys()):
            self.disappeared[track_id] += 1

            # Remove tracks that have disappeared too long
            if self.disappeared[track_id] > self.max_disappeared:
                self._remove_track(track_id)

        return []

    def _associate_detections(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Associate current detections with existing tracks.

        Args:
            detections: Current frame detections

        Returns:
            Tracked players with consistent IDs
        """
        if len(self.tracks) == 0:
            return self._initialize_tracks(detections)

        # Calculate cost matrix (distance between detections and tracks)
        track_centers = []
        track_ids = []
        for track_id, track_info in self.tracks.items():
            track_centers.append(track_info["center"])
            track_ids.append(track_id)

        detection_centers = [det["center"] for det in detections]

        # Calculate distance matrix
        if len(track_centers) > 0 and len(detection_centers) > 0:
            cost_matrix = cdist(track_centers, detection_centers)
        else:
            cost_matrix = np.array([])

        # Perform assignment using Hungarian algorithm (simplified greedy approach)
        assignments = self._greedy_assignment(cost_matrix, track_ids, detections)

        # Update tracks and create output
        return self._update_tracks_with_assignments(assignments, detections)

    def _greedy_assignment(
        self,
        cost_matrix: np.ndarray,
        track_ids: List[int],
        detections: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Perform greedy assignment of detections to tracks.

        Args:
            cost_matrix: Distance matrix between tracks and detections
            track_ids: List of track IDs
            detections: Current detections

        Returns:
            Assignment information
        """
        assignments = {
            "matched": [],  # (track_id, detection_idx)
            "unmatched_tracks": set(track_ids),
            "unmatched_detections": set(range(len(detections)))
        }

        if cost_matrix.size == 0:
            return assignments

        # Greedy assignment: for each track, find closest detection
        for track_idx, track_id in enumerate(track_ids):
            min_distance = float('inf')
            best_detection_idx = -1

            for det_idx in assignments["unmatched_detections"]:
                distance = cost_matrix[track_idx, det_idx]
                if distance < min_distance and distance < self.max_distance:
                    min_distance = distance
                    best_detection_idx = det_idx

            # If valid assignment found
            if best_detection_idx != -1:
                # Additional IoU check
                track_bbox = self.tracks[track_id]["bbox"]
                det_bbox = detections[best_detection_idx]["bbox"]

                if self._calculate_iou(track_bbox, det_bbox) > self.iou_threshold:
                    assignments["matched"].append((track_id, best_detection_idx))
                    assignments["unmatched_tracks"].discard(track_id)
                    assignments["unmatched_detections"].discard(best_detection_idx)

        return assignments

    def _update_tracks_with_assignments(
        self,
        assignments: Dict[str, Any],
        detections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Update tracks based on assignments and create output.

        Args:
            assignments: Assignment results
            detections: Current detections

        Returns:
            List of tracked players
        """
        tracked_players = []

        # Update matched tracks
        for track_id, detection_idx in assignments["matched"]:
            detection = detections[detection_idx]

            # Update track info
            self.tracks[track_id].update({
                "bbox": detection["bbox"],
                "center": detection["center"],
                "confidence": detection["confidence"],
                "last_seen": 0
            })
            self.tracks[track_id]["history"].append(detection["center"])

            # Reset disappeared counter
            self.disappeared[track_id] = 0

            # Add to output
            tracked_detection = detection.copy()
            tracked_detection["track_id"] = track_id
            tracked_players.append(tracked_detection)

        # Handle unmatched tracks (increment disappeared counter)
        for track_id in assignments["unmatched_tracks"]:
            self.disappeared[track_id] += 1

            # Remove if disappeared too long
            if self.disappeared[track_id] > self.max_disappeared:
                self._remove_track(track_id)

        # Create new tracks for unmatched detections
        for detection_idx in assignments["unmatched_detections"]:
            detection = detections[detection_idx]
            track_id = self._create_new_track(detection)

            tracked_detection = detection.copy()
            tracked_detection["track_id"] = track_id
            tracked_players.append(tracked_detection)

        self.logger.debug(f"Tracking {len(tracked_players)} players")
        return tracked_players

    def _create_new_track(self, detection: Dict[str, Any]) -> int:
        """Create a new track for an unmatched detection.

        Args:
            detection: Detection to create track for

        Returns:
            New track ID
        """
        track_id = self.next_id
        self.next_id += 1

        track_info = {
            "bbox": detection["bbox"],
            "center": detection["center"],
            "confidence": detection["confidence"],
            "last_seen": 0,
            "history": [detection["center"]]
        }
        self.tracks[track_id] = track_info
        self.disappeared[track_id] = 0

        self.logger.debug(f"Created new track {track_id}")
        return track_id

    def _remove_track(self, track_id: int) -> None:
        """Remove a track that has disappeared.

        Args:
            track_id: Track ID to remove
        """
        if track_id in self.tracks:
            del self.tracks[track_id]
        if track_id in self.disappeared:
            del self.disappeared[track_id]

        self.logger.debug(f"Removed track {track_id}")

    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """Calculate Intersection over Union between two bounding boxes.

        Args:
            bbox1: First bounding box [x1, y1, x2, y2]
            bbox2: Second bounding box [x1, y1, x2, y2]

        Returns:
            IoU value between 0 and 1
        """
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2

        # Calculate intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)

        if x2_i <= x1_i or y2_i <= y1_i:
            return 0.0

        intersection = (x2_i - x1_i) * (y2_i - y1_i)

        # Calculate union
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def get_track_history(self, track_id: int) -> List[List[float]]:
        """Get position history for a specific track.

        Args:
            track_id: Track ID to get history for

        Returns:
            List of [x, y] positions
        """
        if track_id in self.tracks:
            return self.tracks[track_id]["history"].copy()
        return []

    def get_active_tracks(self) -> Dict[int, Dict[str, Any]]:
        """Get all currently active tracks.

        Returns:
            Dictionary of track_id -> track_info
        """
        return self.tracks.copy()
