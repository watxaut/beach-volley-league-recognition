"""
Player tracker for beach volleyball video analysis.

Tracks exactly 4 players with stable IDs (1-4). Uses spatial proximity
and color histogram appearance features to maintain identity across frames.
Integrates with CourtCalibration for team assignment (2 per side of net).
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2
from scipy.optimize import linear_sum_assignment
from collections import defaultdict
import logging


class PlayerTracker:
    """Tracks exactly 4 beach volleyball players with stable IDs.

    Key design decisions:
    - Never creates a 5th track. Unmatched detections beyond 4 are discarded.
    - Uses color histogram of torso crop for appearance matching to prevent
      ID swaps when players cross paths.
    - No aspect ratio filter (diving players have unusual aspect ratios).
    - High max_velocity (150 px/frame) to handle diving.
    """

    def __init__(
        self,
        max_disappeared: int = 30,
        max_distance: float = 150.0,
        max_velocity: float = 150.0,
        max_players: int = 4,
        appearance_weight: float = 0.4,
        init_frames: int = 30,
        court_calibration=None,
    ):
        """Initialize the player tracker.

        Args:
            max_disappeared: Max frames a player can be missing before re-init.
            max_distance: Max centroid distance (px) for association.
            max_velocity: Max allowed velocity (px/frame).
            max_players: Maximum number of tracked players (4 for beach volleyball).
            appearance_weight: Weight of appearance cost vs distance cost [0-1].
            init_frames: Number of initial frames to collect detections for
                stable initialization.
            court_calibration: Optional CourtCalibration instance for team assignment.
        """
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.max_velocity = max_velocity
        self.max_players = max_players
        self.appearance_weight = appearance_weight
        self.init_frames = init_frames
        self.court_calibration = court_calibration

        # Tracking state
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.disappeared: Dict[int, int] = {}
        self.next_id = 1  # IDs start at 1
        self.frame_count = 0
        self._initialized = False

        # Initialization buffer: collect detections from first N frames
        self._init_buffer: List[List[Dict[str, Any]]] = []
        # Current frame for appearance extraction
        self._current_frame: Optional[np.ndarray] = None

        self.logger = logging.getLogger(__name__)

    def update(
        self, detections: List[Dict[str, Any]], frame: Optional[np.ndarray] = None
    ) -> List[Dict[str, Any]]:
        """Update tracker with new detections.

        Args:
            detections: List of player detections with 'bbox', 'center', 'confidence'.
            frame: Current video frame (needed for appearance features).

        Returns:
            List of tracked players with stable 'track_id' and 'team' fields.
        """
        self._current_frame = frame
        self.frame_count += 1

        if not self._initialized:
            return self._initialization_phase(detections)

        if not detections:
            return self._handle_no_detections()

        return self._associate_detections(detections)

    # --- Initialization ---

    def _initialization_phase(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Collect detections for init_frames, then pick the best 4 tracks."""
        self._init_buffer.append(detections)

        if self.frame_count < self.init_frames and len(self._init_buffer) < self.init_frames:
            # Still collecting -- return detections with temporary IDs
            return self._temp_track_output(detections)

        # Cluster all collected detections to find 4 most persistent players
        self._initialize_from_buffer()
        self._initialized = True
        self._init_buffer = []

        # Now do a normal association for this frame
        if detections:
            return self._associate_detections(detections)
        return self._get_current_tracks()

    def _initialize_from_buffer(self) -> None:
        """Initialize exactly max_players tracks from the buffered detections."""
        # Collect all detection centers
        all_centers = []
        for frame_dets in self._init_buffer:
            for det in frame_dets:
                all_centers.append(det["center"])

        if len(all_centers) < self.max_players:
            # Not enough detections -- initialize with whatever we have
            for det in (self._init_buffer[-1] if self._init_buffer else []):
                self._create_track(det)
            return

        # K-means clustering to find player positions
        centers_arr = np.array(all_centers, dtype=np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1.0)
        k = min(self.max_players, len(centers_arr))
        _, labels, cluster_centers = cv2.kmeans(
            centers_arr, k, None, criteria, 10, cv2.KMEANS_PP_CENTERS
        )

        # Count points per cluster to rank by persistence
        cluster_counts = np.bincount(labels.flatten(), minlength=k)
        top_clusters = np.argsort(-cluster_counts)[:self.max_players]

        # For each cluster, pick the detection from the last frame closest to center
        last_frame_dets = self._init_buffer[-1] if self._init_buffer else []
        for cluster_idx in top_clusters:
            center = cluster_centers[cluster_idx]
            # Find closest detection in last frame
            best_det = None
            best_dist = float("inf")
            for det in last_frame_dets:
                d = np.linalg.norm(np.array(det["center"]) - center)
                if d < best_dist:
                    best_dist = d
                    best_det = det

            if best_det is not None:
                self._create_track(best_det)
            else:
                # No detection near this cluster in last frame, create a synthetic one
                self._create_track({
                    "bbox": [int(center[0]-30), int(center[1]-60), int(center[0]+30), int(center[1]+60)],
                    "center": center.tolist(),
                    "confidence": 0.5,
                })

        self.logger.info(f"Initialized {len(self.tracks)} player tracks from {len(self._init_buffer)} frames")

    def _temp_track_output(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """During initialization, return detections with temporary track IDs."""
        result = []
        for i, det in enumerate(detections[:self.max_players]):
            d = det.copy()
            d["track_id"] = i + 1
            d["team"] = None
            result.append(d)
        return result

    # --- Core association ---

    def _associate_detections(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Associate detections with existing tracks using Hungarian algorithm."""
        track_ids = list(self.tracks.keys())
        n_tracks = len(track_ids)
        n_dets = len(detections)

        if n_tracks == 0:
            return []

        # Build cost matrix: rows=tracks, cols=detections
        cost_matrix = np.full((n_tracks, n_dets), 1e6)

        for i, tid in enumerate(track_ids):
            track = self.tracks[tid]
            for j, det in enumerate(detections):
                cost = self._compute_assignment_cost(track, det)
                if cost is not None:
                    cost_matrix[i, j] = cost

        # Hungarian assignment
        row_indices, col_indices = linear_sum_assignment(cost_matrix)

        matched_tracks = set()
        matched_dets = set()
        tracked_players = []

        for row, col in zip(row_indices, col_indices):
            if cost_matrix[row, col] >= 1e6:
                continue
            tid = track_ids[row]
            det = detections[col]
            self._update_track(tid, det)
            matched_tracks.add(tid)
            matched_dets.add(col)

            out = det.copy()
            out["track_id"] = tid
            out["team"] = self._get_team(det["center"])
            tracked_players.append(out)

        # Unmatched tracks: increment disappeared
        for i, tid in enumerate(track_ids):
            if tid not in matched_tracks:
                self.disappeared[tid] = self.disappeared.get(tid, 0) + 1
                if self.disappeared[tid] > self.max_disappeared:
                    self._remove_track(tid)
                else:
                    # Keep track in output with predicted position
                    track = self.tracks.get(tid)
                    if track:
                        out = {
                            "bbox": track["bbox"],
                            "center": track["center"],
                            "confidence": max(0.1, track["confidence"] - 0.05),
                            "track_id": tid,
                            "team": self._get_team(track["center"]),
                            "predicted": True,
                        }
                        tracked_players.append(out)

        # Unmatched detections: DISCARD (never create 5th track)
        # Only create new track if we have fewer than max_players
        for j in range(n_dets):
            if j not in matched_dets and len(self.tracks) < self.max_players:
                det = detections[j]
                tid = self._create_track(det)
                out = det.copy()
                out["track_id"] = tid
                out["team"] = self._get_team(det["center"])
                tracked_players.append(out)

        return tracked_players

    def _compute_assignment_cost(
        self, track: Dict[str, Any], detection: Dict[str, Any]
    ) -> Optional[float]:
        """Compute cost of assigning a detection to a track.

        Returns None if assignment is invalid (too far or too fast).
        """
        track_center = np.array(track["center"])
        det_center = np.array(detection["center"])

        # Distance cost
        distance = float(np.linalg.norm(track_center - det_center))
        if distance > self.max_distance:
            return None

        # Velocity check
        velocity = distance  # per frame
        if velocity > self.max_velocity:
            return None

        # Appearance cost (color histogram similarity)
        appearance_cost = 0.0
        if self._current_frame is not None and "histogram" in track:
            det_hist = self._compute_histogram(detection["bbox"])
            if det_hist is not None and track["histogram"] is not None:
                similarity = cv2.compareHist(track["histogram"], det_hist, cv2.HISTCMP_CORREL)
                appearance_cost = 1.0 - max(0.0, similarity)  # 0=identical, 1=different

        # Combined cost
        cost = (1.0 - self.appearance_weight) * distance + self.appearance_weight * appearance_cost * self.max_distance
        return cost

    # --- Appearance features ---

    def _compute_histogram(self, bbox: List[float]) -> Optional[np.ndarray]:
        """Compute HSV color histogram of the torso region within a bbox."""
        if self._current_frame is None:
            return None

        h, w = self._current_frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return None

        # Torso = middle third vertically
        box_h = y2 - y1
        torso_y1 = y1 + box_h // 4
        torso_y2 = y1 + 3 * box_h // 4
        crop = self._current_frame[torso_y1:torso_y2, x1:x2]

        if crop.size == 0:
            return None

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [18, 8], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist

    # --- Track management ---

    def _create_track(self, detection: Dict[str, Any]) -> int:
        """Create a new track. Respects max_players limit."""
        if len(self.tracks) >= self.max_players:
            self.logger.debug("Max players reached, not creating new track")
            return -1

        tid = self.next_id
        self.next_id += 1

        hist = self._compute_histogram(detection["bbox"]) if self._current_frame is not None else None

        self.tracks[tid] = {
            "bbox": detection["bbox"],
            "center": detection["center"],
            "confidence": detection["confidence"],
            "history": [detection["center"]],
            "velocity": [0.0, 0.0],
            "histogram": hist,
        }
        self.disappeared[tid] = 0
        self.logger.debug(f"Created track {tid}")
        return tid

    def _update_track(self, tid: int, detection: Dict[str, Any]) -> None:
        """Update an existing track with a new detection."""
        track = self.tracks[tid]
        old_center = track["center"]
        new_center = detection["center"]

        # Smooth velocity
        vx = new_center[0] - old_center[0]
        vy = new_center[1] - old_center[1]
        alpha = 0.3
        track["velocity"] = [
            alpha * vx + (1 - alpha) * track["velocity"][0],
            alpha * vy + (1 - alpha) * track["velocity"][1],
        ]

        track["bbox"] = detection["bbox"]
        track["center"] = new_center
        track["confidence"] = detection["confidence"]
        track["history"].append(new_center)
        # Keep last 60 positions
        if len(track["history"]) > 60:
            track["history"] = track["history"][-60:]

        # Update appearance histogram periodically
        if self._current_frame is not None and self.frame_count % 10 == 0:
            hist = self._compute_histogram(detection["bbox"])
            if hist is not None:
                if track["histogram"] is not None:
                    # Blend old and new histogram
                    track["histogram"] = 0.7 * track["histogram"] + 0.3 * hist
                else:
                    track["histogram"] = hist

        self.disappeared[tid] = 0

    def _remove_track(self, tid: int) -> None:
        """Remove a track."""
        self.tracks.pop(tid, None)
        self.disappeared.pop(tid, None)
        self.logger.debug(f"Removed track {tid}")

    def _handle_no_detections(self) -> List[Dict[str, Any]]:
        """Handle frame with no detections."""
        result = []
        for tid in list(self.tracks.keys()):
            self.disappeared[tid] = self.disappeared.get(tid, 0) + 1
            if self.disappeared[tid] > self.max_disappeared:
                self._remove_track(tid)
            else:
                track = self.tracks[tid]
                result.append({
                    "bbox": track["bbox"],
                    "center": track["center"],
                    "confidence": max(0.1, track["confidence"] - 0.05),
                    "track_id": tid,
                    "team": self._get_team(track["center"]),
                    "predicted": True,
                })
        return result

    # --- Team assignment ---

    def _get_team(self, center: List[float]) -> Optional[str]:
        """Get team assignment based on court calibration."""
        if self.court_calibration is not None and hasattr(self.court_calibration, "get_team"):
            return self.court_calibration.get_team((int(center[0]), int(center[1])))
        return None

    def set_court_calibration(self, calibration) -> None:
        """Set or update court calibration for team assignment."""
        self.court_calibration = calibration

    # --- Public API ---

    def get_track_history(self, track_id: int) -> List[List[float]]:
        """Get position history for a specific track."""
        if track_id in self.tracks:
            return list(self.tracks[track_id]["history"])
        return []

    def get_active_tracks(self) -> Dict[int, Dict[str, Any]]:
        """Get all currently active tracks."""
        return dict(self.tracks)

    def _get_current_tracks(self) -> List[Dict[str, Any]]:
        """Return current track states as tracked player list."""
        result = []
        for tid, track in self.tracks.items():
            result.append({
                "bbox": track["bbox"],
                "center": track["center"],
                "confidence": track["confidence"],
                "track_id": tid,
                "team": self._get_team(track["center"]),
            })
        return result
