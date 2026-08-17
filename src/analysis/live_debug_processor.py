"""
Annotated-video processor for volleyball analysis.

Renders a minimal overlay -- court lines, a single ball marker, and player
boxes that take the action colour while an action is on screen -- shared with
``scripts/test_action_recognition.py`` via ``src.output_gen.overlay``.

Action labels are anchored on their *true contact frame*, not the later frame
the two-layer classifier emits them on (it holds each contact until the next
one arrives; see ``action_classifier.py``). Two render strategies remove that
~1.5s emission lag:

- ``--save-video`` (headless): a **two-pass** render. Pass 1 processes every
  frame, caches lightweight overlay data, and builds the label plan; pass 2
  re-reads frames from disk and draws labels on their contact frames. Exact and
  low-memory.
- ``--debug-live`` (real-time): a **buffered** render. Frames are shown/written
  with a fixed ~3s delay so a contact's label -- emitted up to ~2s late -- is
  already known by the time that frame is displayed.
"""

import logging
from collections import deque
from typing import Dict, Any, Optional, List, Tuple

import cv2
import numpy as np

from .frame_processor import FrameProcessor
from src.output_gen import overlay

# Overlay data cached per frame for the deferred render.
BallOverlay = Optional[Tuple[int, int, bool]]           # (x, y, is_predicted)
PlayerOverlay = List[Tuple[int, List[int]]]             # [(track_id, [x1,y1,x2,y2]), ...]


class LiveDebugProcessor:
    """Processor that draws a clean, contact-anchored action overlay onto each frame.

    Overlays, matching ``test_action_recognition.py``:
    - Court boundary lines
    - Tracked ball as a single circle (green detected / red predicted)
    - Player boxes with ``P<id>``; the box + label take the action colour while
      a recent action for that player is on screen, anchored on its contact frame
    - A small frame counter, top-right (this processor only; the standalone
      action script does not draw one)
    """

    # Live display/write lag, in seconds. Must exceed the classifier's worst
    # emission delay (~2s) so a contact's label is known before its frame shows.
    LIVE_DELAY_SECONDS = 3.0
    LIVE_DELAY_MAX_FRAMES = 150  # cap the frame buffer (memory) regardless of fps

    def __init__(self, config: Dict[str, Any], debug_speed: float = 1.0):
        """Initialize the processor.

        Args:
            config: Configuration dictionary
            debug_speed: Live playback speed multiplier (1.0 = normal speed)
        """
        self.config = config
        self.debug_speed = debug_speed
        self.logger = logging.getLogger(__name__)

        # Shared frame processor (live mode - use enhanced ball tracker)
        self.frame_processor = FrameProcessor(config, use_enhanced_ball_tracker=True)

        # Court calibration, used to draw the court boundary each frame.
        self.court_detector = self.frame_processor.get_court_detector()

    def process_video_live(
        self,
        video_path: str,
        save_video: Optional[str] = None,
        display: bool = True,
    ) -> None:
        """Process a video and render the contact-anchored overlay.

        Picks the render strategy from ``display``: buffered real-time when a
        window is shown, otherwise a two-pass headless save.

        Args:
            video_path: Path to the video file.
            save_video: If set, write the annotated frames to this path.
            display: If True, show the live window (needs a display) with
                q/space/r controls. Set False for headless save-only runs.
        """
        if display:
            self._process_buffered_live(video_path, save_video)
        else:
            self._process_two_pass(video_path, save_video)

    # ------------------------------------------------------------------ #
    # Shared helpers
    # ------------------------------------------------------------------ #

    def _ingest_actions(self, actions: List[Dict[str, Any]], plan: overlay.LabelPlan) -> None:
        """Feed emitted actions into the label plan at their true contact frame."""
        for action in actions:
            tid = action.get("track_id")
            if tid is None:
                continue
            plan.add(tid, action.get("frame_number"),
                     action.get("action", "?"), action.get("confidence", 0.0))
            self.logger.info(
                "Action: contact frame %s player %s -> %s (%.2f)",
                action.get("frame_number"), tid,
                action.get("action"), action.get("confidence", 0.0),
            )

    @staticmethod
    def _overlay_data(frame_result: Dict[str, Any]) -> Tuple[BallOverlay, PlayerOverlay]:
        """Extract the lightweight ball + player boxes needed to redraw a frame."""
        ball: BallOverlay = None
        tb = frame_result.get("tracked_ball")
        if tb:
            center = tb.get("center") or [None, None]
            if center[0] is not None and center[1] is not None:
                ball = (int(center[0]), int(center[1]), bool(tb.get("is_predicted", False)))

        players: PlayerOverlay = []
        for p in frame_result.get("tracked_players", []):
            bbox = p.get("bbox", [])
            if len(bbox) == 4:
                players.append((p.get("track_id", -1), [int(v) for v in bbox]))
        return ball, players

    def _render_frame(self, frame: np.ndarray, frame_idx: int, ball: BallOverlay,
                      players: PlayerOverlay, plan: overlay.LabelPlan,
                      total_frames: Optional[int] = None) -> np.ndarray:
        """Draw court + ball + player boxes (labels anchored on contact frames)."""
        out = frame
        try:
            if self.court_detector is not None:
                out = self.court_detector.draw_court_overlay(out)

            if ball is not None:
                bx, by, pred = ball
                overlay.draw_ball(out, bx, by, predicted=pred)

            for track_id, bbox in players:
                lab = plan.active(track_id, frame_idx)
                overlay.draw_player(
                    out, track_id, bbox,
                    action=lab[0] if lab else None,
                    confidence=lab[1] if lab else None,
                )

            overlay.draw_frame_counter(out, frame_idx, total_frames)
        except Exception as e:
            self.logger.error(f"Error rendering frame {frame_idx}: {e}")
            cv2.putText(out, f"Render Error: {str(e)[:50]}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return out

    def _open(self, video_path: str) -> Tuple[cv2.VideoCapture, float, int, int, int]:
        """Open a video and return (cap, fps, width, height, total_frames)."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return cap, fps, width, height, total

    # ------------------------------------------------------------------ #
    # Two-pass headless save (--save-video)
    # ------------------------------------------------------------------ #

    def _process_two_pass(self, video_path: str, save_video: Optional[str]) -> None:
        """Pass 1: detect/track/classify + cache overlay data. Pass 2: redraw."""
        self.logger.info(f"Starting two-pass annotated save: {video_path}")
        cap, fps, width, height, total = self._open(video_path)
        self.logger.info(f"Video: {total} frames, {fps} FPS, {width}x{height}")
        self.frame_processor.setup_video_fps(fps)
        self.frame_processor.setup_video_dimensions(width, height)

        plan = overlay.LabelPlan()
        cache: List[Tuple[BallOverlay, PlayerOverlay]] = []

        # ---- Pass 1: process every frame, cache overlay data, build the plan.
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            result = self.frame_processor.process_frame(frame, frame_idx, enable_court_redetection=True)
            self._ingest_actions(result.get("actions", []), plan)
            cache.append(self._overlay_data(result))
            frame_idx += 1
        # Finalise the last contact held back for its look-ahead.
        self._ingest_actions(self.frame_processor.flush_actions(), plan)
        cap.release()

        if not save_video:
            return

        # ---- Pass 2: re-read frames and draw contact-anchored labels.
        cap, *_ = self._open(video_path)
        writer = cv2.VideoWriter(save_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        for frame_idx, (ball, players) in enumerate(cache):
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(self._render_frame(frame, frame_idx, ball, players, plan,
                                            total_frames=total))
        cap.release()
        writer.release()
        self.logger.info(f"Annotated video written: {save_video}")

    # ------------------------------------------------------------------ #
    # Buffered real-time render (--debug-live)
    # ------------------------------------------------------------------ #

    def _process_buffered_live(self, video_path: str, save_video: Optional[str]) -> None:
        """Show (and optionally write) frames on a fixed delay so labels land on
        their contact frame once the classifier has emitted them."""
        self.logger.info(f"Starting buffered live processing: {video_path}")
        cap, fps, width, height, total = self._open(video_path)
        frame_delay = (1.0 / fps) / self.debug_speed if fps > 0 else 0.033
        self.logger.info(f"Video: {total} frames, {fps} FPS, {width}x{height}")
        self.frame_processor.setup_video_fps(fps)
        self.frame_processor.setup_video_dimensions(width, height)

        writer = None
        if save_video:
            writer = cv2.VideoWriter(save_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

        delay_frames = min(int(round((fps or 30) * self.LIVE_DELAY_SECONDS)), self.LIVE_DELAY_MAX_FRAMES)
        self.logger.info(
            "Press 'q' to quit, SPACE to pause/resume, 'r' to restart "
            "(labels shown on a %d-frame delay so they land on the contact frame)",
            delay_frames,
        )

        plan = overlay.LabelPlan()
        buffer: deque = deque()  # (frame, frame_idx, ball, players)
        frame_idx = 0
        paused = False
        source_done = False
        shown = None

        while True:
            # 1. Read + process the next source frame (unless paused / exhausted).
            if not paused and not source_done:
                ret, frame = cap.read()
                if ret:
                    result = self.frame_processor.process_frame(frame, frame_idx, enable_court_redetection=True)
                    self._ingest_actions(result.get("actions", []), plan)
                    ball, players = self._overlay_data(result)
                    buffer.append((frame, frame_idx, ball, players))
                    frame_idx += 1
                else:
                    source_done = True
                    # Input over: finalise the last held-back contact, then drain.
                    self._ingest_actions(self.frame_processor.flush_actions(), plan)

            # 2. Release one frame once the buffer is a full delay deep (or draining).
            if not paused and buffer and (len(buffer) > delay_frames or source_done):
                f, i, ball, players = buffer.popleft()
                shown = self._render_frame(f, i, ball, players, plan, total_frames=total)
                if writer is not None:
                    writer.write(shown)

            # 3. Display + controls (block on key while paused).
            if shown is not None:
                cv2.imshow('Volleyball Analysis', shown)
                key = cv2.waitKey(0 if paused else max(1, int(frame_delay * 1000))) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord(' '):
                    paused = not paused
                    self.logger.info("Paused" if paused else "Resumed")
                elif key == ord('r'):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    frame_idx = 0
                    source_done = False
                    buffer.clear()
                    shown = None
                    plan = overlay.LabelPlan()
                    self.frame_processor.reset_trackers()
                    self.logger.info("Video restarted")

            # 4. Done once the source is exhausted and the buffer has drained.
            if source_done and not buffer:
                break

        cap.release()
        if writer is not None:
            writer.release()
            self.logger.info(f"Annotated video written: {save_video}")
        cv2.destroyAllWindows()
        self.logger.info("Processing ended")
