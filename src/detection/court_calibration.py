"""
Court calibration module for fixed-camera volleyball analysis.

Instead of detecting the court every frame, the user clicks 8 points on the
first frame. The calibration is saved to JSON and reused across sessions.

Camera is perpendicular to the net (front view). Layout from bottom to top
of the frame: camera -> Team A (near) -> midcourt line / net -> Team B (far).

Calibration points (8 total):
  1-4: Court corners (clockwise from far-left)
  5-6: Midcourt ground-line points (left, right) -- for team assignment
  7-8: Net top points (left, right) -- for block detection, ball analysis
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
    drop-in replacement in the pipeline. The court polygon, midcourt line,
    net top, and team zones are computed once and reused for all frames.
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
        self.midcourt_points: Optional[np.ndarray] = None  # 2 points on midcourt ground line
        self.midcourt_line: Optional[Tuple[np.ndarray, np.ndarray]] = None
        self.net_top_points: Optional[np.ndarray] = None  # 2 points at top of net
        self.net_top_line: Optional[Tuple[np.ndarray, np.ndarray]] = None
        self.court_polygon: Optional[np.ndarray] = None

        # Backward compat aliases
        self.net_posts: Optional[np.ndarray] = None
        self.net_line: Optional[Tuple[np.ndarray, np.ndarray]] = None

        # Derived zones
        self.team_a_polygon: Optional[np.ndarray] = None  # near side (closer to camera)
        self.team_b_polygon: Optional[np.ndarray] = None  # far side (behind net)
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
        """Open an interactive window for the user to click 8 calibration points.

        Click order:
            1-4: Court corners (clockwise from far-left)
            5-6: Midcourt ground-line points (left, right)
            7-8: Net top points (left, right)

        Args:
            frame: First video frame.
            save_path: If provided, save calibration JSON here.

        Returns:
            True if calibration succeeded (8 points collected).
        """
        points: List[Tuple[int, int]] = []
        total_steps = 8

        steps = [
            {
                "label": "Step 1/8: Court corner - FAR LEFT",
                "hint": "Click the far-left corner of the court (back-left sideline intersection).",
                "color": (0, 255, 0),
            },
            {
                "label": "Step 2/8: Court corner - FAR RIGHT",
                "hint": "Click the far-right corner of the court (back-right sideline intersection).",
                "color": (0, 255, 0),
            },
            {
                "label": "Step 3/8: Court corner - NEAR RIGHT",
                "hint": "Click the near-right corner of the court (front-right sideline intersection, closest to camera).",
                "color": (0, 255, 0),
            },
            {
                "label": "Step 4/8: Court corner - NEAR LEFT",
                "hint": "Click the near-left corner of the court (front-left sideline intersection, closest to camera).",
                "color": (0, 255, 0),
            },
            {
                "label": "Step 5/8: Midcourt line - LEFT",
                "hint": (
                    "Click on the SAND at the LEFT sideline where the court changes sides "
                    "(directly below the net, on the ground). This is the midcourt line."
                ),
                "color": (0, 0, 255),
            },
            {
                "label": "Step 6/8: Midcourt line - RIGHT",
                "hint": (
                    "Click on the SAND at the RIGHT sideline where the court changes sides "
                    "(directly below the net, on the ground). Same line, other side."
                ),
                "color": (0, 0, 255),
            },
            {
                "label": "Step 7/8: Net top - LEFT",
                "hint": (
                    "Click the TOP of the net on the LEFT side "
                    "(where the net tape meets the left post/antenna)."
                ),
                "color": (0, 165, 255),
            },
            {
                "label": "Step 8/8: Net top - RIGHT",
                "hint": (
                    "Click the TOP of the net on the RIGHT side "
                    "(where the net tape meets the right post/antenna)."
                ),
                "color": (0, 165, 255),
            },
        ]

        display = frame.copy()
        self.frame_dimensions = frame.shape[:2]
        h_frame, w_frame = frame.shape[:2]

        def _on_click(event, x, y, flags, param):
            if event != cv2.EVENT_LBUTTONDOWN:
                return
            if len(points) >= total_steps:
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
            # Midcourt line
            if len(points) == 6:
                cv2.line(display, points[4], points[5], (0, 0, 255), 2)
            # Net top line
            if len(points) == 8:
                cv2.line(display, points[6], points[7], (0, 165, 255), 2)
            cv2.imshow("Court Calibration", display)

        window_name = "Court Calibration"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window_name, _on_click)

        while len(points) < total_steps:
            step = steps[len(points)]
            info = display.copy()

            # Top bar: step label
            cv2.putText(info, step["label"], (10, 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

            # Bottom hint area
            hint_text = step["hint"]
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.1
            line_height = 40
            max_chars = max(30, w_frame // 18)

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

            display_lines = lines[-4:]
            hint_area_height = len(display_lines) * line_height + 60
            hint_y_start = h_frame - hint_area_height + 20
            cv2.rectangle(info, (0, hint_y_start - 15), (w_frame, h_frame), (0, 0, 0), -1)

            for i, line in enumerate(display_lines):
                cv2.putText(info, line, (15, hint_y_start + i * line_height),
                            font, font_scale, (200, 200, 200), 2)

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
                display = frame.copy()
                for idx, pt in enumerate(points):
                    c = steps[idx]["color"]
                    cv2.circle(display, pt, 6, c, -1)
                    cv2.putText(display, str(idx + 1), (pt[0] + 10, pt[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, c, 2)
                    if 1 <= idx <= 3:
                        cv2.line(display, points[idx - 1], pt, (0, 255, 0), 2)
                if len(points) >= 4:
                    cv2.line(display, points[3], points[0], (0, 255, 0), 2)
                if len(points) >= 6:
                    cv2.line(display, points[4], points[5], (0, 0, 255), 2)
                if len(points) >= 8:
                    cv2.line(display, points[6], points[7], (0, 165, 255), 2)

        cv2.destroyWindow(window_name)

        self._apply_points(points, frame.shape[:2])

        if save_path:
            self.save(save_path)

        return True

    def calibrate_from_points(
        self,
        court_corners: List[List[int]],
        midcourt_points: List[List[int]],
        frame_shape: Tuple[int, int],
        net_top_points: Optional[List[List[int]]] = None,
    ) -> None:
        """Calibrate programmatically from known points.

        Args:
            court_corners: 4 corners as [[x,y], ...] clockwise from far-left.
            midcourt_points: 2 midcourt ground-line points as [[x,y], [x,y]].
            frame_shape: (height, width) of the video frames.
            net_top_points: 2 net top points as [[x,y], [x,y]]. Optional.
        """
        points = [tuple(p) for p in court_corners] + [tuple(p) for p in midcourt_points]
        if net_top_points:
            points += [tuple(p) for p in net_top_points]
        self._apply_points(points, frame_shape)

    def _apply_points(self, points: List[Tuple[int, int]], frame_shape: Tuple[int, int]) -> None:
        """Compute all derived geometry from the calibration points."""
        self.frame_dimensions = frame_shape
        h, w = frame_shape

        self.court_corners = np.array(points[:4], dtype=np.int32)
        self.midcourt_points = np.array(points[4:6], dtype=np.int32)
        self.midcourt_line = (self.midcourt_points[0], self.midcourt_points[1])

        # Net top points (optional -- may not be present in old calibrations)
        if len(points) >= 8:
            self.net_top_points = np.array(points[6:8], dtype=np.int32)
            self.net_top_line = (self.net_top_points[0], self.net_top_points[1])
        else:
            self.net_top_points = None
            self.net_top_line = None

        # Backward compat aliases
        self.net_posts = self.midcourt_points
        self.net_line = self.midcourt_line

        # Court polygon (the 4 corners)
        self.court_polygon = self.court_corners.copy()

        # Bounding box
        xs = self.court_corners[:, 0]
        ys = self.court_corners[:, 1]
        self.court_bounds = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))

        # Court mask
        self.court_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(self.court_mask, [self.court_corners], 255)

        # Team zones
        self._compute_team_zones(h, w)

        self._calibrated = True
        self.logger.info("Court calibration applied successfully")

    def _compute_team_zones(self, h: int, w: int) -> None:
        """Split court into two halves using the midcourt ground line."""
        if self.midcourt_points is None or self.court_corners is None:
            return

        mid_y = (float(self.midcourt_points[0][1]) + float(self.midcourt_points[1][1])) / 2

        near_corners = []
        far_corners = []
        for corner in self.court_corners:
            if corner[1] >= mid_y:
                near_corners.append(corner)
            else:
                far_corners.append(corner)

        mc_left = self.midcourt_points[0] if self.midcourt_points[0][0] < self.midcourt_points[1][0] else self.midcourt_points[1]
        mc_right = self.midcourt_points[1] if self.midcourt_points[0][0] < self.midcourt_points[1][0] else self.midcourt_points[0]

        if near_corners:
            pts = [c.tolist() for c in near_corners]
            pts.append(mc_left.tolist())
            pts.append(mc_right.tolist())
            arr = np.array(pts, dtype=np.int32)
            self.team_a_polygon = cv2.convexHull(arr).reshape(-1, 2)

        if far_corners:
            pts = [c.tolist() for c in far_corners]
            pts.append(mc_left.tolist())
            pts.append(mc_right.tolist())
            arr = np.array(pts, dtype=np.int32)
            self.team_b_polygon = cv2.convexHull(arr).reshape(-1, 2)

    # --- Team assignment ---

    def _midcourt_y_at_x(self, x: int) -> float:
        """Interpolate the midcourt ground-line y at a given x position."""
        x0, y0 = float(self.midcourt_points[0][0]), float(self.midcourt_points[0][1])
        x1, y1 = float(self.midcourt_points[1][0]), float(self.midcourt_points[1][1])
        if abs(x1 - x0) < 1e-6:
            return (y0 + y1) / 2
        t = max(0.0, min(1.0, (x - x0) / (x1 - x0)))
        return y0 + t * (y1 - y0)

    def get_team(self, point: Tuple[int, int]) -> Optional[str]:
        """Return 'A' or 'B' based on which side of the midcourt line the point is on.

        Args:
            point: (x, y) pixel coordinates.

        Returns:
            'A' for near side (below midcourt, closer to camera),
            'B' for far side (above midcourt, farther from camera).
        """
        if self.midcourt_points is None:
            return None
        mid_y = self._midcourt_y_at_x(point[0])
        if point[1] >= mid_y:
            return "A"
        return "B"

    def get_team_for_bbox(self, bbox: List[int]) -> Optional[str]:
        """Return team using player's foot position (bottom-center of bbox)."""
        foot_x = (bbox[0] + bbox[2]) / 2
        foot_y = bbox[3]
        return self.get_team((int(foot_x), int(foot_y)))

    def get_net_y(self) -> Optional[int]:
        """Return the y-coordinate of the midcourt line center."""
        if self.midcourt_points is None:
            return None
        return int((self.midcourt_points[0][1] + self.midcourt_points[1][1]) / 2)

    def get_net_top_y_at_x(self, x: int) -> Optional[float]:
        """Interpolate the net top y-coordinate at a given x position.

        Useful for block detection (checking if arms are above net height).
        """
        if self.net_top_points is None:
            return None
        x0, y0 = float(self.net_top_points[0][0]), float(self.net_top_points[0][1])
        x1, y1 = float(self.net_top_points[1][0]), float(self.net_top_points[1][1])
        if abs(x1 - x0) < 1e-6:
            return (y0 + y1) / 2
        t = max(0.0, min(1.0, (x - x0) / (x1 - x0)))
        return y0 + t * (y1 - y0)

    def is_above_net(self, point: Tuple[int, int]) -> bool:
        """Check if a point is above the net top (lower y in pixel coords).

        Useful for block detection -- checking if a player's hands are above net height.
        """
        if self.net_top_points is None:
            return False
        net_y = self.get_net_top_y_at_x(point[0])
        return point[1] < net_y

    # --- CourtDetector-compatible interface ---

    def detect_court(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """No-op for calibrated court. Returns the pre-computed mask."""
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
        """Check if a point is near the midcourt/net line."""
        if self.midcourt_points is None:
            return False
        mid_y = self._midcourt_y_at_x(point[0])
        return abs(point[1] - mid_y) < threshold_px

    def is_behind_baseline(self, point: Tuple[int, int], team: str, margin_px: int = 30) -> bool:
        """Check if a point is behind the baseline for a given team.

        Team A (near/bottom): behind baseline means y > max y of near-side corners.
        Team B (far/top): behind baseline means y < min y of far-side corners.
        """
        if self.court_corners is None:
            return False
        ys = self.court_corners[:, 1]
        if team == "A":
            return point[1] > int(ys.max()) - margin_px
        else:
            return point[1] < int(ys.min()) + margin_px

    def get_court_statistics(self) -> Dict[str, Any]:
        """Return court statistics."""
        stats = {
            "court_detected": self._calibrated,
            "detection_method": "calibration",
            "court_bounds": self.court_bounds,
            "has_net_top": self.net_top_points is not None,
        }
        if self._calibrated and self.court_bounds and self.frame_dimensions:
            x1, y1, x2, y2 = self.court_bounds
            h, w = self.frame_dimensions
            area = (x2 - x1) * (y2 - y1)
            stats.update({
                "court_area_pixels": area,
                "court_area_ratio": area / (h * w),
                "net_y": self.get_net_y(),
                "boundaries": {
                    "left": x1, "top": y1, "right": x2, "bottom": y2,
                },
            })
        return stats

    def draw_court_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Draw court polygon, midcourt line, and net on frame."""
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

        # Midcourt line (red)
        if self.midcourt_line is not None:
            pt1, pt2 = self.midcourt_line
            cv2.line(overlay, tuple(pt1), tuple(pt2), (0, 0, 255), 2)

        # Net top line (orange)
        if self.net_top_line is not None:
            pt1, pt2 = self.net_top_line
            cv2.line(overlay, tuple(pt1), tuple(pt2), (0, 165, 255), 3)
            # Draw vertical lines connecting net top to midcourt (net "posts")
            mc1, mc2 = self.midcourt_line
            cv2.line(overlay, tuple(pt1), tuple(mc1), (0, 165, 255), 1)
            cv2.line(overlay, tuple(pt2), tuple(mc2), (0, 165, 255), 1)

        # Team zone labels: place at midpoint of each half (not polygon centroid)
        if self.midcourt_line is not None and self.court_corners is not None:
            mid_y = self.get_net_y()
            ys = self.court_corners[:, 1]
            court_cx = int(self.court_corners[:, 0].mean())

            # Team A label: midpoint between midcourt and near baseline
            near_baseline_y = int(ys.max())
            label_a_y = (mid_y + near_baseline_y) // 2
            cv2.putText(overlay, "Team A", (court_cx - 40, label_a_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

            # Team B label: midpoint between midcourt and far baseline
            far_baseline_y = int(ys.min())
            label_b_y = (mid_y + far_baseline_y) // 2
            cv2.putText(overlay, "Team B", (court_cx - 40, label_b_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        # Team zone outlines
        if self.team_a_polygon is not None:
            cv2.polylines(overlay, [self.team_a_polygon], True, (255, 0, 0), 1)
        if self.team_b_polygon is not None:
            cv2.polylines(overlay, [self.team_b_polygon], True, (0, 165, 255), 1)

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
            "midcourt_points": self.midcourt_points.tolist(),
            "net_top_points": self.net_top_points.tolist() if self.net_top_points is not None else None,
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
        # Support old format ("net_posts") and new ("midcourt_points")
        midcourt = data.get("midcourt_points") or data.get("net_posts")
        net_top = data.get("net_top_points")
        self.calibrate_from_points(
            data["court_corners"],
            midcourt,
            frame_shape,
            net_top_points=net_top,
        )
        self.logger.info(f"Court calibration loaded from {path}")
