"""
Court calibration module for fixed-camera volleyball analysis.

Instead of detecting the court every frame, the user clicks 4 court corners
and 2 net post positions on the first frame. The calibration is saved to JSON
and reused across sessions. This replaces court_detector.py for fixed cameras.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import cv2
import numpy as np


class CourtCalibration:
    """One-time court calibration for fixed-camera setups.

    Provides the same interface as CourtDetector so it can be used as a
    drop-in replacement in the pipeline. The court polygon, net line, and
    team zones are computed once and reused for all frames.
    """

    def __init__(self, calibration_path: Optional[str] = None):
        """Initialize court calibration.

        Args:
            calibration_path: Path to existing calibration JSON. If provided
                and the file exists, the calibration is loaded automatically.
        """
        self.logger = logging.getLogger(__name__)

        # Calibration data
        self.court_corners: Optional[np.ndarray] = None  # 4 corners, shape (4, 2)
        self.net_posts: Optional[np.ndarray] = None  # 2 posts, shape (2, 2)
        self.net_line: Optional[Tuple[np.ndarray, np.ndarray]] = None  # (pt1, pt2)
        self.court_polygon: Optional[np.ndarray] = None  # convex hull of corners

        # Derived zones
        self.team_a_polygon: Optional[np.ndarray] = None  # left of net
        self.team_b_polygon: Optional[np.ndarray] = None  # right of net
        self.court_mask: Optional[np.ndarray] = None
        self.court_bounds: Optional[Tuple[int, int, int, int]] = None  # x1, y1, x2, y2
        self.frame_dimensions: Optional[Tuple[int, int]] = None  # (h, w)

        self._calibrated = False

        if calibration_path and Path(calibration_path).exists():
            self.load(calibration_path)

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated

    # --- Interactive calibration ---

    def calibrate_from_frame(self, frame: np.ndarray, save_path: Optional[str] = None) -> bool:
        """Open an interactive window for the user to click court corners and net posts.

        Click order:
            1-4: Court corners (clockwise from top-left)
            5-6: Net posts (left post, right post)

        Args:
            frame: First video frame.
            save_path: If provided, save calibration JSON here.

        Returns:
            True if calibration succeeded (6 points collected).
        """
        points: List[Tuple[int, int]] = []

        # Step definitions: label shown at top, detailed hint shown at bottom
        steps = [
            {
                "label": "Step 1/6: Court corner - FAR LEFT",
                "hint": "Click the far-left corner of the court (back-left sideline intersection).",
                "color": (0, 255, 0),
            },
            {
                "label": "Step 2/6: Court corner - FAR RIGHT",
                "hint": "Click the far-right corner of the court (back-right sideline intersection).",
                "color": (0, 255, 0),
            },
            {
                "label": "Step 3/6: Court corner - NEAR RIGHT",
                "hint": "Click the near-right corner of the court (front-right sideline intersection, closest to camera).",
                "color": (0, 255, 0),
            },
            {
                "label": "Step 4/6: Court corner - NEAR LEFT",
                "hint": "Click the near-left corner of the court (front-left sideline intersection, closest to camera).",
                "color": (0, 255, 0),
            },
            {
                "label": "Step 5/6: Net-sideline intersection - LEFT",
                "hint": (
                    "Click where the net meets the LEFT sideline at GROUND level. "
                    "This is NOT the post itself -- click where the net plane crosses the court boundary on the sand."
                ),
                "color": (0, 0, 255),
            },
            {
                "label": "Step 6/6: Net-sideline intersection - RIGHT",
                "hint": (
                    "Click where the net meets the RIGHT sideline at GROUND level. "
                    "Same idea: where the net crosses the court boundary, not the post."
                ),
                "color": (0, 0, 255),
            },
        ]

        display = frame.copy()
        self.frame_dimensions = frame.shape[:2]
        h_frame, w_frame = frame.shape[:2]

        def _on_click(event, x, y, flags, param):
            if event != cv2.EVENT_LBUTTONDOWN:
                return
            if len(points) >= 6:
                return
            points.append((x, y))
            step = steps[len(points) - 1]
            color = step["color"]
            cv2.circle(display, (x, y), 6, color, -1)
            cv2.putText(display, str(len(points)), (x + 10, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            # Draw lines between court corners
            if 2 <= len(points) <= 4:
                cv2.line(display, points[-2], (x, y), (0, 255, 0), 2)
            if len(points) == 4:
                cv2.line(display, points[3], points[0], (0, 255, 0), 2)
            if len(points) == 6:
                cv2.line(display, points[4], points[5], (0, 0, 255), 2)
            cv2.imshow("Court Calibration", display)

        window_name = "Court Calibration"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window_name, _on_click)

        while len(points) < 6:
            step = steps[len(points)]
            info = display.copy()

            # Top bar: step label
            cv2.putText(info, step["label"], (10, 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

            # Bottom hint area: dark background + wrapped hint text
            hint_text = step["hint"]
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.1
            line_height = 40
            max_chars = max(30, w_frame // 18)  # fewer chars per line at larger font

            words = hint_text.split()
            lines = []
            current = ""
            for word in words:
                test = f"{current} {word}".strip()
                if len(test) > max_chars:
                    lines.append(current)
                    current = word
                else:
                    current = test
            if current:
                lines.append(current)

            # Use up to 4 lines
            display_lines = lines[-4:]
            hint_area_height = len(display_lines) * line_height + 60
            hint_y_start = h_frame - hint_area_height + 20
            cv2.rectangle(info, (0, hint_y_start - 15), (w_frame, h_frame), (0, 0, 0), -1)

            for i, line in enumerate(display_lines):
                cv2.putText(info, line, (15, hint_y_start + i * line_height),
                            font, font_scale, (200, 200, 200), 2)

            # Controls hint
            cv2.putText(info, "[R] Reset  [U] Undo last  [Q] Cancel", (15, h_frame - 10),
                        font, 0.8, (128, 128, 128), 2)

            cv2.imshow(window_name, info)
            key = cv2.waitKey(50) & 0xFF
            if key == ord("q"):
                cv2.destroyWindow(window_name)
                return False
            if key == ord("r"):
                points.clear()
                display = frame.copy()
            if key == ord("u") and points:
                points.pop()
                # Redraw from scratch
                display = frame.copy()
                for idx, pt in enumerate(points):
                    c = steps[idx]["color"]
                    cv2.circle(display, pt, 6, c, -1)
                    cv2.putText(display, str(idx + 1), (pt[0] + 10, pt[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, c, 2)
                    if 1 <= idx <= 3:
                        cv2.line(display, points[idx - 1], pt, (0, 255, 0), 2)
                if len(points) == 4:
                    cv2.line(display, points[3], points[0], (0, 255, 0), 2)
                if len(points) == 6:
                    cv2.line(display, points[4], points[5], (0, 0, 255), 2)

        cv2.destroyWindow(window_name)

        self._apply_points(points, frame.shape[:2])

        if save_path:
            self.save(save_path)

        return True

    def calibrate_from_points(
        self,
        court_corners: List[List[int]],
        net_posts: List[List[int]],
        frame_shape: Tuple[int, int],
    ) -> None:
        """Calibrate programmatically from known points.

        Args:
            court_corners: 4 corners as [[x,y], ...] clockwise from top-left.
            net_posts: 2 net posts as [[x,y], [x,y]].
            frame_shape: (height, width) of the video frames.
        """
        points = [tuple(p) for p in court_corners] + [tuple(p) for p in net_posts]
        self._apply_points(points, frame_shape)

    def _apply_points(self, points: List[Tuple[int, int]], frame_shape: Tuple[int, int]) -> None:
        """Compute all derived geometry from the 6 calibration points."""
        self.frame_dimensions = frame_shape
        h, w = frame_shape

        self.court_corners = np.array(points[:4], dtype=np.int32)
        self.net_posts = np.array(points[4:6], dtype=np.int32)
        self.net_line = (self.net_posts[0], self.net_posts[1])

        # Court polygon (the 4 corners)
        self.court_polygon = self.court_corners.copy()

        # Bounding box
        xs = self.court_corners[:, 0]
        ys = self.court_corners[:, 1]
        self.court_bounds = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))

        # Court mask
        self.court_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(self.court_mask, [self.court_corners], 255)

        # Team zones: split court by net line
        self._compute_team_zones(h, w)

        self._calibrated = True
        self.logger.info("Court calibration applied successfully")

    def _compute_team_zones(self, h: int, w: int) -> None:
        """Split court into two halves using the net line."""
        if self.net_posts is None or self.court_corners is None:
            return

        net_x = int((self.net_posts[0][0] + self.net_posts[1][0]) / 2)

        # Team A = corners left of net, Team B = corners right of net
        left_corners = []
        right_corners = []
        for corner in self.court_corners:
            if corner[0] <= net_x:
                left_corners.append(corner)
            else:
                right_corners.append(corner)

        # Add net post intersections to close each polygon
        net_top = self.net_posts[0] if self.net_posts[0][1] < self.net_posts[1][1] else self.net_posts[1]
        net_bottom = self.net_posts[1] if self.net_posts[0][1] < self.net_posts[1][1] else self.net_posts[0]

        if left_corners:
            left_corners.append(net_bottom.tolist())
            left_corners.append(net_top.tolist())
            self.team_a_polygon = np.array(left_corners, dtype=np.int32)
            # Reorder as convex hull
            hull = cv2.convexHull(self.team_a_polygon)
            self.team_a_polygon = hull.reshape(-1, 2)

        if right_corners:
            right_corners.append(net_top.tolist())
            right_corners.append(net_bottom.tolist())
            self.team_b_polygon = np.array(right_corners, dtype=np.int32)
            hull = cv2.convexHull(self.team_b_polygon)
            self.team_b_polygon = hull.reshape(-1, 2)

    # --- Team assignment ---

    def get_team(self, point: Tuple[int, int]) -> Optional[str]:
        """Return 'A' or 'B' based on which side of the net the point is on.

        Args:
            point: (x, y) pixel coordinates.

        Returns:
            'A' for left of net, 'B' for right of net, None if outside court.
        """
        if self.net_posts is None:
            return None
        net_x = int((self.net_posts[0][0] + self.net_posts[1][0]) / 2)
        if point[0] <= net_x:
            return "A"
        return "B"

    def get_net_x(self) -> Optional[int]:
        """Return the x-coordinate of the net center."""
        if self.net_posts is None:
            return None
        return int((self.net_posts[0][0] + self.net_posts[1][0]) / 2)

    # --- CourtDetector-compatible interface ---

    def detect_court(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """No-op for calibrated court. Returns the pre-computed mask.

        This exists so CourtCalibration can be used as a drop-in replacement
        for CourtDetector in the pipeline.
        """
        if not self._calibrated:
            self.frame_dimensions = frame.shape[:2]
            return None
        return self.court_mask

    def filter_detections_by_court(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter detections to only include those within the court polygon."""
        if not self._calibrated:
            return detections

        filtered = []
        for det in detections:
            bbox = det.get("bbox", [])
            if len(bbox) != 4:
                continue
            x1, y1, x2, y2 = bbox
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            if self.is_point_in_court((int(cx), int(cy))):
                filtered.append(det)
        return filtered

    def is_point_in_court(self, point: Tuple[int, int]) -> bool:
        """Check if a point is inside the court polygon."""
        if self.court_mask is None:
            return True
        x, y = point
        h, w = self.court_mask.shape
        if x < 0 or x >= w or y < 0 or y >= h:
            return False
        return self.court_mask[int(y), int(x)] > 0

    def is_near_net(self, point: Tuple[int, int], threshold_px: int = 80) -> bool:
        """Check if a point is near the net line."""
        if self.net_posts is None:
            return False
        net_x = self.get_net_x()
        return abs(point[0] - net_x) < threshold_px

    def is_behind_baseline(self, point: Tuple[int, int], team: str, margin_px: int = 30) -> bool:
        """Check if a point is behind the baseline for a given team.

        For team A (left side), behind baseline means x < leftmost court corner x.
        For team B (right side), behind baseline means x > rightmost court corner x.
        """
        if self.court_corners is None:
            return False
        xs = self.court_corners[:, 0]
        if team == "A":
            return point[0] < int(xs.min()) + margin_px
        else:
            return point[0] > int(xs.max()) - margin_px

    def get_court_statistics(self) -> Dict[str, Any]:
        """Return court statistics compatible with CourtDetector interface."""
        stats = {
            "court_detected": self._calibrated,
            "detection_method": "calibration",
            "court_bounds": self.court_bounds,
            "adaptive_bounds": None,
            "use_adaptive": False,
        }
        if self._calibrated and self.court_bounds and self.frame_dimensions:
            x1, y1, x2, y2 = self.court_bounds
            h, w = self.frame_dimensions
            area = (x2 - x1) * (y2 - y1)
            stats.update({
                "court_area_pixels": area,
                "court_area_ratio": area / (h * w),
                "net_x": self.get_net_x(),
                "boundaries": {
                    "left": x1, "top": y1, "right": x2, "bottom": y2,
                },
            })
        return stats

    def draw_court_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Draw court polygon and net line on frame."""
        overlay = frame.copy()
        if not self._calibrated:
            cv2.putText(overlay, "Court NOT calibrated", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            return overlay

        # Court polygon (green)
        cv2.polylines(overlay, [self.court_corners], True, (0, 255, 0), 2)

        # Semi-transparent court fill
        court_fill = np.zeros_like(frame)
        cv2.fillPoly(court_fill, [self.court_corners], (0, 80, 0))
        cv2.addWeighted(overlay, 1.0, court_fill, 0.3, 0, overlay)

        # Net line (red)
        if self.net_line is not None:
            pt1, pt2 = self.net_line
            cv2.line(overlay, tuple(pt1), tuple(pt2), (0, 0, 255), 3)

        # Team zones
        if self.team_a_polygon is not None:
            cv2.polylines(overlay, [self.team_a_polygon], True, (255, 0, 0), 1)
            centroid_a = self.team_a_polygon.mean(axis=0).astype(int)
            cv2.putText(overlay, "Team A", tuple(centroid_a), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        if self.team_b_polygon is not None:
            cv2.polylines(overlay, [self.team_b_polygon], True, (0, 165, 255), 1)
            centroid_b = self.team_b_polygon.mean(axis=0).astype(int)
            cv2.putText(overlay, "Team B", tuple(centroid_b), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        # Corner labels
        for i, corner in enumerate(self.court_corners):
            cv2.circle(overlay, tuple(corner), 5, (0, 255, 0), -1)
            cv2.putText(overlay, f"C{i+1}", (corner[0]+8, corner[1]-8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        cv2.putText(overlay, "Court: CALIBRATED", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        return overlay

    # --- Persistence ---

    def save(self, path: str) -> None:
        """Save calibration to JSON."""
        if not self._calibrated:
            raise ValueError("Cannot save: not calibrated yet")
        data = {
            "court_corners": self.court_corners.tolist(),
            "net_posts": self.net_posts.tolist(),
            "frame_dimensions": list(self.frame_dimensions) if self.frame_dimensions else None,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        self.logger.info(f"Court calibration saved to {path}")

    def load(self, path: str) -> None:
        """Load calibration from JSON."""
        with open(path, "r") as f:
            data = json.load(f)
        frame_shape = tuple(data["frame_dimensions"]) if data.get("frame_dimensions") else (1080, 1920)
        self.calibrate_from_points(
            data["court_corners"],
            data["net_posts"],
            frame_shape,
        )
        self.logger.info(f"Court calibration loaded from {path}")
