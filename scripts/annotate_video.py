#!/usr/bin/env python3
"""
Interactive ground truth annotation tool for volleyball videos.

Three annotation modes switchable via keyboard:
  1 - Ball mode:   click the ball in play among YOLO detections
  2 - Player mode: assign player IDs (1-4) to detected bounding boxes
  3 - Action mode: mark actions during playback, then click the player

Usage:
    python scripts/annotate_video.py resources/video.mp4 \
        --court calibrations/court.json \
        --ball-model models/volleyball_ball_best.pt \
        --output ground_truth/video_annotations.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.ball_detector import BallDetector
from src.detection.court_calibration import CourtCalibration
from src.detection.player_detector import PlayerDetector
from src.recognition.rally_state import compute_rally_state

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# --- Constants ---

MODE_BALL = 1
MODE_PLAYER = 2
MODE_ACTION = 3

MODE_NAMES = {MODE_BALL: "BALL", MODE_PLAYER: "PLAYER", MODE_ACTION: "ACTION"}

ACTION_KEYS = {
    ord("s"): "serve",
    ord("d"): "dig",
    ord("t"): "set",
    ord("k"): "spike",
    ord("b"): "block",
    ord("o"): "overpass",
}

BALL_STRIDE = 5
PLAYER_STRIDE = 10

# Colors
COLOR_BALL = (0, 255, 255)       # Yellow
COLOR_BALL_SELECTED = (0, 0, 255)  # Red
COLOR_PLAYER = (0, 255, 0)       # Green
COLOR_PLAYER_SELECTED = (255, 0, 255)  # Magenta
COLOR_HUD_BG = (30, 30, 30)
COLOR_HUD_TEXT = (220, 220, 220)
COLOR_MODE_BALL = (0, 255, 255)
COLOR_MODE_PLAYER = (0, 255, 0)
COLOR_MODE_ACTION = (255, 100, 100)


class AnnotationTool:
    def __init__(
        self,
        video_path: str,
        output_path: str,
        court_path: Optional[str] = None,
        ball_model_path: Optional[str] = None,
        ball_confidence: float = 0.15,
    ):
        self.video_path = video_path
        self.output_path = output_path

        # Video state
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.current_frame_idx = 0
        self.current_frame: Optional[np.ndarray] = None

        # Mode
        self.mode = MODE_BALL
        self.paused = True  # Start paused in ball/player mode

        # Detectors
        self.ball_detector = BallDetector(
            model_path=ball_model_path,
            confidence_threshold=ball_confidence,
        )
        # For annotation, return ALL ball detections (not just top-1)
        self.player_detector = PlayerDetector(confidence_threshold=0.5)

        # Court calibration
        self.court: Optional[CourtCalibration] = None
        if court_path and Path(court_path).exists():
            self.court = CourtCalibration(court_path)
            logger.info(f"Court calibration loaded from {court_path}")

        # Current detections cache (refreshed per frame)
        self.ball_detections: List[Dict[str, Any]] = []
        self.player_detections: List[Dict[str, Any]] = []

        # Player mode state
        self.pending_player_id: Optional[int] = None

        # Action mode state
        self.pending_action: Optional[str] = None
        # Additional raw-visual labels to attach to the next action event
        # alongside final_action (filled by pressing 'v' then a label key).
        self.pending_raw_visual_actions: List[str] = []
        # When True, next S/D/T/K/B keypress adds to pending_raw_visual_actions
        # instead of replacing pending_action.
        self.pending_raw_add: bool = False

        # Mouse click state
        self.click_pos: Optional[Tuple[int, int]] = None

        # Annotations
        self.annotations = self._load_or_create_annotations()
        self._migrate_action_events()
        self._recompute_rally_state()

        # Undo stack: list of (category, key/index, old_value)
        self.undo_stack: List[Tuple[str, Any, Any]] = []

        # Display scale for window (handle high-res video)
        self.display_scale = 1.0
        if self.width > 1920:
            self.display_scale = 1920 / self.width

    def _load_or_create_annotations(self) -> Dict[str, Any]:
        """Load existing annotations or create empty structure."""
        if Path(self.output_path).exists():
            with open(self.output_path) as f:
                data = json.load(f)
            logger.info(f"Resumed annotations from {self.output_path}")
            return data

        annotations = {
            "video": self.video_path,
            "fps": self.fps,
            "resolution": [self.width, self.height],
            "annotated_frames": {
                "ball": {
                    "description": "Ball center position every 5 frames",
                    "frames": {},
                },
                "players": {
                    "description": "Player bounding boxes + IDs every 10 frames",
                    "frames": {},
                },
                "actions": {
                    "description": (
                        "Action events with rally-state context. Each event has: "
                        "frame, player_id, final_action (canonical label), "
                        "raw_visual_actions (open-vocabulary multi-label), "
                        "player_team, team_in_possession, touch_number, "
                        "preceded_by_attack, rally_id, overrides."
                    ),
                    "events": [],
                },
            },
            "court": {
                "corners": self.court.court_corners.tolist() if self.court and self.court.is_calibrated else [],
                "net_posts": self.court.midcourt_points.tolist() if self.court and self.court.is_calibrated else [],
            },
        }
        return annotations

    def _save_annotations(self):
        Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w") as f:
            json.dump(self.annotations, f, indent=2)
        logger.info(f"Saved annotations to {self.output_path}")

    # --- Detection helpers ---

    def _detect_balls_all(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run ball detector but return ALL detections (not just top-1).

        Drops detections whose center is outside the court polygon when a
        court calibration is loaded -- avoids labeling balls on adjacent
        courts or the surrounding beach.
        """
        if not self.ball_detector.validate_frame(frame):
            return []
        imgsz = self.ball_detector._get_imgsz(frame)
        classes = None if self.ball_detector._is_custom_model else BallDetector.BALL_CLASSES
        results = self.ball_detector._model(
            frame, verbose=False, classes=classes,
            conf=self.ball_detector.confidence_threshold, imgsz=imgsz,
        )
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for i in range(len(boxes)):
                conf = float(boxes.conf[i])
                x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().astype(int)
                w, h = x2 - x1, y2 - y1
                if w > self.ball_detector.max_ball_size or h > self.ball_detector.max_ball_size:
                    continue
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                detections.append({
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "center": [float(cx), float(cy)],
                    "confidence": conf,
                })
        if self.court and self.court.is_calibrated:
            detections = [
                d for d in detections
                if self.court.is_point_in_court((int(d["center"][0]), int(d["center"][1])))
            ]
        detections.sort(key=lambda d: d["confidence"], reverse=True)
        return detections

    def _detect_players(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run player detector and return in-court detections sorted by x position."""
        detections = self.player_detector.detect(frame)
        if self.court and self.court.is_calibrated:
            detections = self.court.filter_detections_by_court(detections)
        detections.sort(key=lambda d: d["center"][0])
        return detections

    # --- Click handling ---

    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            # Scale back to original coords if display is scaled
            if self.display_scale != 1.0:
                x = int(x / self.display_scale)
                y = int(y / self.display_scale)
            self.click_pos = (x, y)

    def _find_nearest_detection(
        self, click: Tuple[int, int], detections: List[Dict[str, Any]], max_dist: float = 100
    ) -> Optional[int]:
        """Find the index of the detection closest to click point."""
        best_idx, best_dist = None, max_dist
        for i, det in enumerate(detections):
            cx, cy = det["center"]
            dist = np.sqrt((click[0] - cx) ** 2 + (click[1] - cy) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        return best_idx

    # --- Annotation logic ---

    def _handle_ball_click(self):
        """Handle a click in ball mode: select the ball in play."""
        if self.click_pos is None:
            return
        idx = self._find_nearest_detection(self.click_pos, self.ball_detections)
        if idx is not None:
            det = self.ball_detections[idx]
            cx, cy = det["center"]
            frame_key = str(self.current_frame_idx)
            old_val = self.annotations["annotated_frames"]["ball"]["frames"].get(frame_key)
            self.annotations["annotated_frames"]["ball"]["frames"][frame_key] = {
                "x": round(cx, 1),
                "y": round(cy, 1),
                "visible": True,
            }
            self.undo_stack.append(("ball", frame_key, old_val))
            logger.info(f"Ball annotated at frame {self.current_frame_idx}: ({cx:.0f}, {cy:.0f})")
            self._advance_frame(BALL_STRIDE)
        self.click_pos = None

    def _handle_ball_not_visible(self):
        """Mark current frame as no ball visible."""
        frame_key = str(self.current_frame_idx)
        old_val = self.annotations["annotated_frames"]["ball"]["frames"].get(frame_key)
        self.annotations["annotated_frames"]["ball"]["frames"][frame_key] = None
        self.undo_stack.append(("ball", frame_key, old_val))
        logger.info(f"Ball marked not visible at frame {self.current_frame_idx}")
        self._advance_frame(BALL_STRIDE)

    def _handle_player_click(self):
        """Handle a click in player mode: assign pending player ID to nearest detection."""
        if self.click_pos is None or self.pending_player_id is None:
            self.click_pos = None
            return

        idx = self._find_nearest_detection(self.click_pos, self.player_detections, max_dist=150)
        if idx is not None:
            det = self.player_detections[idx]
            bbox = [int(v) for v in det["bbox"]]
            team = "?"
            if self.court and self.court.is_calibrated:
                team = self.court.get_team_for_bbox(bbox) or "?"

            frame_key = str(self.current_frame_idx)
            players_frames = self.annotations["annotated_frames"]["players"]["frames"]
            if frame_key not in players_frames:
                players_frames[frame_key] = []

            # Remove existing entry for this player_id in this frame
            old_list = [p for p in players_frames[frame_key]]
            players_frames[frame_key] = [
                p for p in players_frames[frame_key] if p["id"] != self.pending_player_id
            ]
            players_frames[frame_key].append({
                "id": self.pending_player_id,
                "team": team,
                "bbox": bbox,
            })
            self.undo_stack.append(("player", frame_key, old_list))
            logger.info(
                f"Player {self.pending_player_id} (Team {team}) annotated at frame {self.current_frame_idx}"
            )

        self.pending_player_id = None
        self.click_pos = None

    def _handle_action_click(self):
        """Handle a click in action mode: assign pending action to nearest player detection."""
        if self.click_pos is None or self.pending_action is None:
            self.click_pos = None
            return

        idx = self._find_nearest_detection(self.click_pos, self.player_detections, max_dist=150)
        if idx is not None:
            det = self.player_detections[idx]
            bbox = [int(v) for v in det["bbox"]]
            player_team = "?"
            if self.court and self.court.is_calibrated:
                player_team = self.court.get_team_for_bbox(bbox) or "?"

            player_id = idx + 1

            raw_labels = list(self.pending_raw_visual_actions)
            if self.pending_action not in raw_labels:
                raw_labels.insert(0, self.pending_action)

            event = {
                "frame": self.current_frame_idx,
                "player_id": player_id,
                "final_action": self.pending_action,
                "raw_visual_actions": raw_labels,
                "player_team": player_team,
                # Rally-state fields populated by _recompute_rally_state.
                "team_in_possession": None,
                "touch_number": 0,
                "preceded_by_attack": False,
                "rally_id": 0,
                # Per-event overrides survive rally-state recompute.
                "overrides": {},
            }
            events = self.annotations["annotated_frames"]["actions"]["events"]
            old_len = len(events)
            events.append(event)
            self.undo_stack.append(("action", old_len, None))
            self._recompute_rally_state()
            logger.info(
                f"Action '{self.pending_action}' (raw={raw_labels}) by Player {player_id} "
                f"(Team {player_team}) at frame {self.current_frame_idx}"
            )

        self.pending_action = None
        self.pending_raw_visual_actions = []
        self.click_pos = None

    def _recompute_rally_state(self) -> None:
        """Recompute rally state across all action events.

        Thin wrapper around `src.recognition.rally_state.compute_rally_state`
        so the labeller and the future action classifier share one
        implementation. See that function for the state-machine spec.
        """
        events = self.annotations["annotated_frames"]["actions"]["events"]
        compute_rally_state(events)

    def _migrate_action_events(self) -> None:
        """Migrate old {action: ...} events to the new schema in place."""
        events = (
            self.annotations.get("annotated_frames", {})
            .get("actions", {})
            .get("events", [])
        )
        for event in events:
            if "final_action" not in event and "action" in event:
                event["final_action"] = event["action"]
                del event["action"]
            event.setdefault("final_action", "unknown")
            event.setdefault("raw_visual_actions", [event["final_action"]])
            event.setdefault("player_team", "?")
            event.setdefault("team_in_possession", None)
            event.setdefault("touch_number", 0)
            event.setdefault("preceded_by_attack", False)
            event.setdefault("rally_id", 0)
            event.setdefault("overrides", {})

    def _current_rally_context(self) -> Dict[str, Any]:
        """Rally context the next action event would inherit at this frame.

        Reads the most recent event before current_frame_idx and reports
        what the next labeler-added event would naturally take as its
        rally_id / team_in_possession / touch_number / preceded_by_attack,
        assuming it's by the same team as the last event. The actual
        values get recomputed once the event is added.
        """
        events = self.annotations["annotated_frames"]["actions"]["events"]
        past = [e for e in events if e["frame"] < self.current_frame_idx]
        if not past:
            return {
                "rally_id": 0,
                "team": None,
                "next_touch": 1,
                "prev": None,
                "prev_team": None,
            }
        last = max(past, key=lambda e: e["frame"])
        return {
            "rally_id": last.get("rally_id", 0),
            "team": last.get("team_in_possession"),
            "next_touch": last.get("touch_number", 0) + 1,
            "prev": last.get("final_action"),
            "prev_team": last.get("player_team"),
        }

    def _last_action_event(self) -> Optional[Dict[str, Any]]:
        """Return the most recent action event by frame, or None."""
        events = self.annotations["annotated_frames"]["actions"]["events"]
        if not events:
            return None
        return max(events, key=lambda e: e["frame"])

    def _bump_touch_number(self, delta: int) -> None:
        """Adjust the last event's touch_number via override; recompute state."""
        event = self._last_action_event()
        if not event:
            logger.info("No action events to override")
            return
        overrides = event.setdefault("overrides", {})
        base = overrides.get("touch_number", event.get("touch_number", 0))
        new_val = max(1, base + delta)
        overrides["touch_number"] = new_val
        self._recompute_rally_state()
        logger.info(f"Overrode touch_number -> {new_val}")

    def _flip_possession(self) -> None:
        """Flip the last event's team_in_possession via override; recompute."""
        event = self._last_action_event()
        if not event:
            logger.info("No action events to override")
            return
        overrides = event.setdefault("overrides", {})
        current = overrides.get("team_in_possession", event.get("team_in_possession"))
        new_val = "B" if current == "A" else "A"
        overrides["team_in_possession"] = new_val
        self._recompute_rally_state()
        logger.info(f"Overrode team_in_possession -> {new_val}")

    def _undo(self):
        """Undo the last annotation."""
        if not self.undo_stack:
            logger.info("Nothing to undo")
            return

        category, key, old_val = self.undo_stack.pop()

        if category == "ball":
            if old_val is None:
                self.annotations["annotated_frames"]["ball"]["frames"].pop(key, None)
            else:
                self.annotations["annotated_frames"]["ball"]["frames"][key] = old_val
            logger.info(f"Undid ball annotation at frame {key}")

        elif category == "player":
            if old_val is not None:
                self.annotations["annotated_frames"]["players"]["frames"][key] = old_val
            else:
                self.annotations["annotated_frames"]["players"]["frames"].pop(key, None)
            logger.info(f"Undid player annotation at frame {key}")

        elif category == "action":
            events = self.annotations["annotated_frames"]["actions"]["events"]
            if key < len(events):
                events.pop(key)
            self._recompute_rally_state()
            logger.info("Undid last action annotation")

    # --- Frame navigation ---

    def _seek_frame(self, frame_idx: int):
        """Seek to a specific frame."""
        frame_idx = max(0, min(frame_idx, self.total_frames - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = self.cap.read()
        if ret:
            self.current_frame_idx = frame_idx
            self.current_frame = frame
            self._refresh_detections()

    def _advance_frame(self, stride: int = 1):
        """Advance by stride frames."""
        self._seek_frame(self.current_frame_idx + stride)

    def _refresh_detections(self):
        """Re-run detectors on the current frame."""
        if self.current_frame is None:
            return
        if self.mode == MODE_BALL:
            self.ball_detections = self._detect_balls_all(self.current_frame)
        elif self.mode == MODE_PLAYER or self.mode == MODE_ACTION:
            self.player_detections = self._detect_players(self.current_frame)

    # --- Drawing ---

    def _draw_hud(self, frame: np.ndarray) -> np.ndarray:
        """Draw the HUD overlay on the frame."""
        overlay = frame.copy()
        h, w = frame.shape[:2]

        # --- Top-left: mode + frame info ---
        mode_color = {
            MODE_BALL: COLOR_MODE_BALL,
            MODE_PLAYER: COLOR_MODE_PLAYER,
            MODE_ACTION: COLOR_MODE_ACTION,
        }[self.mode]

        # Background panel
        cv2.rectangle(overlay, (0, 0), (420, 80), COLOR_HUD_BG, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        overlay = frame

        mode_str = MODE_NAMES[self.mode]
        cv2.putText(overlay, f"Mode: {mode_str}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, mode_color, 2)
        cv2.putText(overlay, f"Frame: {self.current_frame_idx}/{self.total_frames}",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_HUD_TEXT, 1)

        # --- Top-right: annotation counts (+ rally state in ACTION mode) ---
        ball_count = len(self.annotations["annotated_frames"]["ball"]["frames"])
        player_count = len(self.annotations["annotated_frames"]["players"]["frames"])
        action_count = len(self.annotations["annotated_frames"]["actions"]["events"])

        stats_x = w - 280
        panel_h = 140 if self.mode == MODE_ACTION else 80
        cv2.rectangle(overlay, (stats_x - 10, 0), (w, panel_h), COLOR_HUD_BG, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        overlay = frame

        cv2.putText(overlay, f"Balls: {ball_count}  Players: {player_count}",
                    (stats_x, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_HUD_TEXT, 1)
        cv2.putText(overlay, f"Actions: {action_count}",
                    (stats_x, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_HUD_TEXT, 1)

        if self.mode == MODE_ACTION:
            ctx = self._current_rally_context()
            rally_team = ctx["team"] or "-"
            cv2.putText(overlay, f"Rally {ctx['rally_id']} | Poss: {rally_team}",
                        (stats_x, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_HUD_TEXT, 1)
            cv2.putText(
                overlay,
                f"Next touch: {ctx['next_touch']} | Prev: {ctx['prev'] or '-'}",
                (stats_x, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_HUD_TEXT, 1,
            )

        # --- Bottom: keybindings for current mode ---
        if self.mode == MODE_BALL:
            keys_str = "Click=select ball | N=not visible | LEFT/RIGHT=step | W=save | U=undo | Q=quit"
        elif self.mode == MODE_PLAYER:
            keys_str = "1-4=select ID, then click player | LEFT/RIGHT=step | W=save | U=undo | Q=quit"
            if self.pending_player_id:
                keys_str = f">> Click player for ID {self.pending_player_id} << | ESC=cancel"
        else:
            keys_str = "S/D/T/K/B/O=action, click | V=raw +/-=touch# P=flip poss | SPACE=pause Q=quit"
            if self.pending_action:
                raw_str = ""
                if self.pending_raw_visual_actions:
                    raw_str = f" + raw={self.pending_raw_visual_actions}"
                keys_str = f">> Click player for '{self.pending_action}'{raw_str} << | V=more raw | ESC=cancel"

        bar_y = h - 35
        cv2.rectangle(overlay, (0, bar_y - 5), (w, h), COLOR_HUD_BG, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        overlay = frame

        cv2.putText(overlay, keys_str, (10, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_HUD_TEXT, 1)

        # Mode switch hint
        cv2.putText(overlay, "1=Ball  2=Player  3=Action", (w - 260, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)

        return overlay

    def _draw_ball_detections(self, frame: np.ndarray) -> np.ndarray:
        """Draw numbered ball detections."""
        for i, det in enumerate(self.ball_detections):
            cx, cy = int(det["center"][0]), int(det["center"][1])
            conf = det["confidence"]
            x1, y1, x2, y2 = det["bbox"]

            cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_BALL, 2)
            cv2.circle(frame, (cx, cy), 6, COLOR_BALL, -1)

            label = f"{i+1} ({conf:.2f})"
            cv2.putText(frame, label, (cx + 10, cy - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_BALL, 2)

        # Show existing annotation for this frame
        frame_key = str(self.current_frame_idx)
        ann = self.annotations["annotated_frames"]["ball"]["frames"].get(frame_key)
        if ann is not None:
            ax, ay = int(ann["x"]), int(ann["y"])
            cv2.circle(frame, (ax, ay), 10, COLOR_BALL_SELECTED, 3)
            cv2.putText(frame, "ANNOTATED", (ax + 15, ay),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_BALL_SELECTED, 2)
        elif frame_key in self.annotations["annotated_frames"]["ball"]["frames"]:
            cv2.putText(frame, "NO BALL (annotated)", (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        return frame

    def _draw_player_detections(self, frame: np.ndarray) -> np.ndarray:
        """Draw numbered player detections with any existing annotations."""
        for i, det in enumerate(self.player_detections):
            bbox = [int(v) for v in det["bbox"]]
            x1, y1, x2, y2 = bbox
            cx, cy = int(det["center"][0]), int(det["center"][1])

            color = COLOR_PLAYER
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            label = f"Det {i+1}"
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Show existing player annotations for this frame
        frame_key = str(self.current_frame_idx)
        players = self.annotations["annotated_frames"]["players"]["frames"].get(frame_key, [])
        for p in players:
            bbox = p["bbox"]
            x1, y1, x2, y2 = bbox
            pid = p["id"]
            team = p.get("team", "?")
            cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_PLAYER_SELECTED, 3)
            cv2.putText(frame, f"P{pid} (T{team})", (x1, y2 + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_PLAYER_SELECTED, 2)

        # Show pending player ID
        if self.pending_player_id:
            cv2.putText(frame, f"Assigning Player {self.pending_player_id} - click a detection",
                        (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_PLAYER_SELECTED, 2)

        return frame

    def _draw_action_detections(self, frame: np.ndarray) -> np.ndarray:
        """Draw player detections with numbers for action assignment."""
        for i, det in enumerate(self.player_detections):
            bbox = [int(v) for v in det["bbox"]]
            x1, y1, x2, y2 = bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_MODE_ACTION, 2)
            cv2.putText(frame, f"P{i+1}", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_MODE_ACTION, 2)

        # Show pending action
        if self.pending_action:
            cv2.putText(frame, f"Action: {self.pending_action} - click player",
                        (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_MODE_ACTION, 2)

        # Show recent action annotations near current frame
        events = self.annotations["annotated_frames"]["actions"]["events"]
        for ev in events:
            if abs(ev["frame"] - self.current_frame_idx) < 30:
                raw = ev.get("raw_visual_actions", [])
                raw_str = f" (raw={','.join(raw)})" if len(raw) > 1 else ""
                cv2.putText(
                    frame,
                    f"[F{ev['frame']}] P{ev['player_id']}: {ev['final_action']}{raw_str}",
                    (10, self.height - 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_MODE_ACTION, 1,
                )

        return frame

    # --- Main loop ---

    def run(self):
        """Run the annotation tool."""
        window_name = "Volleyball Annotation Tool"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        if self.display_scale != 1.0:
            cv2.resizeWindow(
                window_name,
                int(self.width * self.display_scale),
                int(self.height * self.display_scale),
            )
        cv2.setMouseCallback(window_name, self._on_mouse)

        # Load first frame
        self._seek_frame(self._find_resume_frame())
        logger.info(f"Starting at frame {self.current_frame_idx}")

        while True:
            if self.current_frame is None:
                break

            # Build display frame
            display = self.current_frame.copy()

            # Court overlay
            if self.court and self.court.is_calibrated:
                display = self.court.draw_court_overlay(display)

            # Mode-specific drawing
            if self.mode == MODE_BALL:
                display = self._draw_ball_detections(display)
            elif self.mode == MODE_PLAYER:
                display = self._draw_player_detections(display)
            elif self.mode == MODE_ACTION:
                display = self._draw_action_detections(display)

            # HUD
            display = self._draw_hud(display)

            # Scale for display if needed
            if self.display_scale != 1.0:
                display = cv2.resize(
                    display, None,
                    fx=self.display_scale, fy=self.display_scale,
                    interpolation=cv2.INTER_AREA,
                )

            cv2.imshow(window_name, display)

            # Handle clicks
            if self.click_pos is not None:
                if self.mode == MODE_BALL:
                    self._handle_ball_click()
                elif self.mode == MODE_PLAYER:
                    self._handle_player_click()
                elif self.mode == MODE_ACTION:
                    self._handle_action_click()

            # Wait for key
            wait_ms = 1 if self.paused else max(1, int(1000 / self.fps))
            key = cv2.waitKey(wait_ms) & 0xFF

            if key == ord("q"):
                self._save_annotations()
                break

            elif key == ord("w"):
                self._save_annotations()

            elif key == ord("u"):
                self._undo()
                self._refresh_detections()

            # Mode switching
            elif key == ord("1"):
                self.mode = MODE_BALL
                self.paused = True
                self.pending_player_id = None
                self.pending_action = None
                self._refresh_detections()
                logger.info("Switched to BALL mode")

            elif key == ord("2"):
                self.mode = MODE_PLAYER
                self.paused = True
                self.pending_player_id = None
                self.pending_action = None
                self._refresh_detections()
                logger.info("Switched to PLAYER mode")

            elif key == ord("3"):
                self.mode = MODE_ACTION
                self.paused = False
                self.pending_player_id = None
                self.pending_action = None
                self._refresh_detections()
                logger.info("Switched to ACTION mode (playing)")

            # Space: pause/resume
            elif key == ord(" "):
                self.paused = not self.paused
                if not self.paused and self.mode == MODE_ACTION:
                    self._refresh_detections()

            # Arrow keys: step frames (LEFT=81/2, RIGHT=83/3 on macOS)
            elif key in (81, 2):  # LEFT
                self._seek_frame(self.current_frame_idx - 1)
            elif key in (83, 3):  # RIGHT
                self._seek_frame(self.current_frame_idx + 1)

            # ESC: cancel pending selection
            elif key == 27:
                self.pending_player_id = None
                self.pending_action = None
                self.pending_raw_visual_actions = []
                self.pending_raw_add = False
                self.click_pos = None

            # Ball mode: N = not visible
            elif key == ord("n") and self.mode == MODE_BALL:
                self._handle_ball_not_visible()

            # Player mode: 1-4 to select player ID before clicking
            elif self.mode == MODE_PLAYER and key in (
                ord("1"), ord("2"), ord("3"), ord("4")
            ):
                # In player mode, these select player ID (not switch mode)
                pass  # Handled below

            # Action mode: action keys
            elif self.mode == MODE_ACTION and key in ACTION_KEYS:
                label = ACTION_KEYS[key]
                if self.pending_raw_add and self.pending_action:
                    if label not in self.pending_raw_visual_actions:
                        self.pending_raw_visual_actions.append(label)
                        logger.info(
                            f"Added '{label}' to raw labels: {self.pending_raw_visual_actions}"
                        )
                else:
                    self.pending_action = label
                    self.paused = True
                    self._refresh_detections()
                    logger.info(f"Selected action: {self.pending_action} - click the player")

            # Action mode: override last event's rally state
            elif self.mode == MODE_ACTION and key in (ord("="), ord("+")):
                self._bump_touch_number(+1)
            elif self.mode == MODE_ACTION and key == ord("-"):
                self._bump_touch_number(-1)
            elif self.mode == MODE_ACTION and key == ord("p"):
                self._flip_possession()

            # Action mode: toggle raw-label add mode (after final_action is picked)
            elif self.mode == MODE_ACTION and key == ord("v"):
                if not self.pending_action:
                    logger.info("Pick final_action first (S/D/T/K/B), then V to add raw labels")
                else:
                    self.pending_raw_add = not self.pending_raw_add
                    state = "ON" if self.pending_raw_add else "OFF"
                    logger.info(f"Raw-label add mode: {state}")

            # Non-paused: advance frame
            if not self.paused:
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                    self.current_frame = frame
                    # Refresh detections periodically in action mode
                    if self.mode == MODE_ACTION and self.current_frame_idx % 5 == 0:
                        self._refresh_detections()
                else:
                    logger.info("End of video")
                    break

            # Handle player ID selection (must be after mode switch check)
            if self.mode == MODE_PLAYER and key in (
                ord("1"), ord("2"), ord("3"), ord("4")
            ):
                self.pending_player_id = int(chr(key))
                logger.info(f"Selected player ID {self.pending_player_id} - click a detection")

        self.cap.release()
        cv2.destroyAllWindows()
        logger.info("Annotation session ended")

    def _find_resume_frame(self) -> int:
        """Find the frame to resume from based on existing annotations."""
        max_frame = 0
        ball_frames = self.annotations["annotated_frames"]["ball"]["frames"]
        if ball_frames:
            max_frame = max(max_frame, max(int(k) for k in ball_frames.keys()))

        player_frames = self.annotations["annotated_frames"]["players"]["frames"]
        if player_frames:
            max_frame = max(max_frame, max(int(k) for k in player_frames.keys()))

        events = self.annotations["annotated_frames"]["actions"]["events"]
        if events:
            max_frame = max(max_frame, max(e["frame"] for e in events))

        return max_frame


def main():
    parser = argparse.ArgumentParser(
        description="Interactive ground truth annotation tool for volleyball videos"
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument(
        "--court", default=None, help="Path to court calibration JSON"
    )
    parser.add_argument(
        "--ball-model", default=None, help="Path to fine-tuned ball detection model"
    )
    parser.add_argument(
        "--ball-confidence", type=float, default=0.15,
        help="Ball detection confidence threshold (default: 0.15)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Output annotation JSON path (default: ground_truth/<video_name>_annotations.json)"
    )

    args = parser.parse_args()

    # Default output path
    if args.output is None:
        video_stem = Path(args.video).stem
        args.output = f"ground_truth/{video_stem}_annotations.json"

    tool = AnnotationTool(
        video_path=args.video,
        output_path=args.output,
        court_path=args.court,
        ball_model_path=args.ball_model,
        ball_confidence=args.ball_confidence,
    )
    tool.run()


if __name__ == "__main__":
    main()
