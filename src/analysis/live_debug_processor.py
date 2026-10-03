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
- ``--debug-live`` (real-time): a **producer/consumer** render. A producer
  thread runs the EXACT shared processing loop in frame order (same calls,
  same sequence as batch -- only the thread differs); the main thread renders
  cached overlay data a fixed ~3s behind -- so a contact's label, emitted up
  to ~2s late, is already known when its frame is shown -- and owns the
  window pacing, so display never serialises behind processing.
"""

import logging
import queue
import threading
import time
from typing import Dict, Any, Optional, List, Tuple

import cv2
import numpy as np

from .frame_processor import FrameProcessor
from ..recognition.action_classifier import ActionClassifier
from . import debug_panel
from src.output_gen import overlay

# Overlay data cached per frame for the deferred render.
BallOverlay = Optional[Tuple[int, int, bool]]           # (x, y, is_predicted)
PlayerOverlay = List[Tuple[int, List[int]]]             # [(track_id, [x1,y1,x2,y2]), ...]

# Sentinel the producer thread queues after its final flush; tells the
# consumer the source is exhausted and the label plan is final.
_PRODUCER_DONE = object()

# cv2 window name (shared by the live consumer loop and the panel's resizable
# window setup).
WINDOW_NAME = "Volleyball Analysis"


class _ThreadSafeLabelPlan(overlay.LabelPlan):
    """``LabelPlan`` with a lock around ``add``/``active`` for the decoupled
    live render: the producer thread ingests labels while the main thread
    reads them per rendered frame. Presentation-only -- the shared pipeline
    never touches this subclass.
    """

    def __init__(self, persist: int = overlay.LABEL_PERSIST):
        super().__init__(persist)
        self._lock = threading.Lock()

    def add(self, track_id: Optional[int], contact_frame: Optional[int],
            action: str, confidence: Optional[float] = None) -> None:
        with self._lock:
            super().add(track_id, contact_frame, action, confidence)

    def active(self, track_id: int, frame_idx: int) -> Optional[Tuple[str, Optional[float]]]:
        with self._lock:
            return super().active(track_id, frame_idx)


def _zone_str(zone: Optional[Dict[str, Any]]) -> Optional[str]:
    """'A1'/'B7'-style zone label from a side/zone dict."""
    if not zone or zone.get("side") is None or zone.get("zone") is None:
        return None
    return "{}{}".format(zone["side"], zone["zone"])


def describe_spike_record(rec: Dict[str, Any]) -> str:
    """Compact origin/destination summary for a spike record, e.g.
    ``from B2 -> lands A7 (kill)`` / ``from A1 -> dug at B8 (dug)``.
    Used by the live-debug resolution log lines."""
    origin = _zone_str(rec.get("attack_zone")) or "?"
    outcome = rec.get("outcome") or "unknown"
    landing = _zone_str(rec.get("landing_zone"))
    dug = _zone_str(rec.get("dug_zone"))
    if outcome in ("kill", "out"):
        dest = "lands {}".format(landing) if landing else "lands out of bounds"
    elif outcome == "dug":
        dest = "dug at {}".format(dug) if dug else "dug (zone unknown)"
    elif outcome == "blocked":
        dest = "blocked"
    elif outcome == "kept":
        dest = "kept up by the attack team"
    else:
        dest = "no landing within horizon"
    return "from {} -> {} ({})".format(origin, dest, outcome)


class LiveDebugProcessor:
    """Processor that draws a clean, contact-anchored action overlay onto each frame.

    Overlays, matching ``test_action_recognition.py``:
    - Court boundary lines
    - Tracked ball as a single circle (green detected / red predicted)
    - Player boxes with ``P<id>``; the box + label take the action colour while
      a recent action for that player is on screen, anchored on its contact frame
    - A small frame counter, top-right (this processor only; the standalone
      action script does not draw one)
    - ``--debug-live`` only: a signal/event side panel on the right (toggle
      with ``p``), composited from data cached by the producer -- see
      ``debug_panel``. Display-only: it never touches the saved video or the
      processing path.
    - ``--debug-live`` only, ``b`` toggle: a hollow box + confidence on every
      ball the detector returned this frame (see :attr:`_candidates_enabled`).
      ON by default; ``b`` turns it off and back on.
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

        # (contact_frame, outcome) already logged per resolved spike record.
        self._spike_log_state: List[Tuple[int, str]] = []

        # --- signal/event side panel (--debug-live display only) ---
        # ON by default in the live window; the saved video never carries it.
        self._panel_enabled: bool = True
        self._event_plan = debug_panel.EventPlan()
        # The panel also mirrors the classifier's contact probe; enabled once
        # the live path starts (skipped when a DiagRecorder owns those
        # records). See _enable_probe_mirror.
        self._probe_mirror: bool = False
        # Last real ball sighting + its point, so the panel can hold the ball
        # readout while the track is dropped instead of blanking it.
        self._last_ball: Optional[Dict[str, Any]] = None
        self._last_ball_pt: Optional[Tuple[float, float]] = None

        # --- every ball the detector saw (--debug-live display only) ---
        # ON by default; 'b' toggles. Draws each candidate the tracker
        # actually received this frame (hollow box + confidence) so a lost ball
        # can be read as "seen but not admitted" instead of "detector missed".
        self._candidates_enabled: bool = True

        # Court calibration, used to draw the court boundary each frame.
        self.court_detector = self.frame_processor.get_court_detector()

    def process_video_live(
        self,
        video_path: str,
        save_video: Optional[str] = None,
        display: bool = True,
    ) -> None:
        """Process a video and render the contact-anchored overlay.

        Picks the render strategy from ``display``: decoupled producer/consumer
        real-time when a window is shown, otherwise a two-pass headless save.

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

    def _ingest_typed_spikes(self, plan: overlay.LabelPlan) -> None:
        """Re-ingest spike labels with their FINAL touch/hard type.

        A hard spike's type is only decidable once its outcome resolves (a
        touch locks early from its arc, hard is the complement), so at
        emission time the plain "spike" label goes up. After the analyzer has
        flushed, this upgrades the label; LabelPlan.add replaces same-contact
        entries, so frames still to be rendered show the typed label.
        """
        for rec in self.frame_processor.spike_analyzer.spike_records():
            if rec["spike_type"] in ("hard", "touch") and rec["track_id"] is not None:
                plan.add(rec["track_id"], rec["frame"], f"spike {rec['spike_type']}")

    def _ingest_actions(self, actions: List[Dict[str, Any]], plan: overlay.LabelPlan) -> None:
        """Feed emitted actions into the label plan at their true contact frame.

        Also mirrors each action into the panel's event plan, keyed the same
        way (its true contact frame), so the panel shows the event on the frame
        the contact happened instead of the frame the look-ahead released it.
        """
        for action in actions:
            tid = action.get("track_id")
            name = action.get("action", "?")
            if name == "spike":
                # Typed spike label ("spike hard"/"spike touch") when the
                # analyzer already has enough post-contact sightings.
                stype = self.frame_processor.spike_analyzer.spike_type_for(
                    action.get("frame_number")
                )
                if stype in ("hard", "touch"):
                    name = f"spike {stype}"
            # The panel wants EVERY action (it is keyed on the contact frame,
            # not a track), so it is recorded before the track-id guard that
            # the label plan and the log below have always had.
            self._record_action_event(action, name)
            if tid is None:
                continue
            plan.add(tid, action.get("frame_number"), name,
                     action.get("confidence", 0.0))
            detail = ""
            if action.get("action") == "spike":
                # Where the spike comes from (takeoff zone, known at emission).
                origin = _zone_str(self.frame_processor.spike_analyzer.spike_zone_for(
                    action.get("frame_number")))
                if origin:
                    detail = " from " + origin
            self.logger.info(
                "Action: contact frame %s player %s -> %s (%.2f)%s",
                action.get("frame_number"), tid,
                action.get("action"), action.get("confidence", 0.0), detail,
            )

    # --- signal/event panel data -------------------------------------------

    def _record_action_event(self, action: Dict[str, Any], label: str) -> None:
        """Mirror one emitted action into the panel's contact-frame event log.

        The second row carries the signals that produced the label -- gesture,
        contact kind, court context and the attribution evidence (ball side +
        source) -- plus the ball's pixel width AT THE CONTACT, looked up in the
        classifier's ball history (the width-side signal the classifier itself
        reads). That is the row to read when a label looks wrong.
        """
        cf = action.get("frame_number")
        conf = action.get("confidence")
        conf_txt = "-" if conf is None else f"{float(conf):.2f}"
        title = "f{}  {}  {}  t{}  {}".format(
            cf, label.upper(), conf_txt, action.get("touch_number", "?"),
            action.get("team") or "?")

        width = self._ball_width_at(cf)
        details = [
            "{}/{}".format(action.get("gesture") or "?", action.get("contact_kind") or "?"),
            "net={}".format(int(bool(action.get("near_net")))),
            "behind={}".format(int(bool(action.get("behind_baseline")))),
            "bbl={}".format(action.get("ball_side") or "-"),
            "src={}".format(action.get("attribution_source") or "-"),
        ]
        if width is not None:
            details.append("w={}px".format(int(width)))
        self._event_plan.add(cf, title, " ".join(details),
                             overlay.ACTION_COLORS.get(label, (225, 225, 225)))

    def _ball_width_at(self, contact_frame: Optional[int]) -> Optional[float]:
        """Ball bbox width (px) at a contact frame, from the classifier's history.

        Render-side read of a value the classifier already keeps; ``None`` when
        the ball was not seen then. Never raises.
        """
        ac = getattr(self.frame_processor, "action_classifier", None)
        if ac is None or contact_frame is None:
            return None
        try:
            for p in ac._ball_history:
                if p[0] == contact_frame:
                    return float(p[3])
        except Exception:      # pragma: no cover - defensive, render-only
            return None
        return None

    def _signals(self, frame_result: Dict[str, Any], frame_idx: int) -> Dict[str, Any]:
        """Snapshot this frame's signals for the panel (render-only mirror).

        Reads ONLY what ``process_frame`` just produced -- tracked ball
        position/size/velocity/confidence, the tracked players' court team and
        distance to the ball, the game-state badge -- plus the classifier's own
        already-computed reads: its ball-width side verdict, the frames since
        the last real ball sighting, the contact it is holding back for
        look-ahead, and its contact-probe records (popped here; see
        :meth:`_enable_probe_mirror`). No threshold is duplicated and no
        inference is re-run, so the panel cannot drift from the pipeline's
        decisions. Every read is guarded: a missing field renders as "-" and
        never breaks the render.
        """
        fp = self.frame_processor
        ac = getattr(fp, "action_classifier", None)
        snapshot: Dict[str, Any] = {
            "frame": frame_idx,
            "ball": None,
            "players": [],
            "game": frame_result.get("game_state") or {},
            "probe": [],
            "pending": None,
            "candidates": (self._ball_candidates(frame_result)
                          if getattr(self, "_candidates_enabled", False) else []),
        }

        # --- ball: position, pixel size, speed, classifier's width-side read
        # A dropped track does NOT blank the panel: the last real sighting is
        # carried forward (``present: False`` + the frame it happened on), so
        # pos / size / width / speed stay readable with an age instead of the
        # block vanishing mid-rally. Predicted points still update it (the
        # tracker is coasting, not lost) and keep their own PREDICTED flag.
        tb = frame_result.get("tracked_ball") or {}
        center = tb.get("center") or [None, None]
        ball_pt: Optional[Tuple[float, float]] = None
        if center and center[0] is not None and center[1] is not None:
            ball_pt = (float(center[0]), float(center[1]))
            bbox = tb.get("bbox") or []
            w = int(round(bbox[2] - bbox[0])) if len(bbox) == 4 else 0
            h = int(round(bbox[3] - bbox[1])) if len(bbox) == 4 else 0
            vel = tb.get("velocity") or []
            speed = (float(np.hypot(float(vel[0]), float(vel[1])))
                     if len(vel) >= 2 else None)
            side = side_name = None
            votes, stale = 0, None
            if ac is not None:
                try:
                    side, votes = ac._width_side(frame_idx)
                    side_name = {"A": "near", "B": "far"}.get(side)
                    stale = ac._ball_stale_frames(frame_idx)
                except Exception:      # pragma: no cover - defensive, render-only
                    side = None
            snapshot["ball"] = {
                "present": True,
                "x": int(ball_pt[0]), "y": int(ball_pt[1]),
                "w": w, "h": h,
                "predicted": bool(tb.get("is_predicted", False)),
                "conf": tb.get("confidence"),
                "speed": speed,
                "side": side, "side_name": side_name,
                "side_votes": votes, "stale": stale,
            }
            self._last_ball = dict(snapshot["ball"], held_from=frame_idx)
            self._last_ball_pt = ball_pt
        elif self._last_ball is not None:
            snapshot["ball"] = dict(
                self._last_ball, present=False,
                stale=frame_idx - self._last_ball["held_from"])
            # Player distances keep measuring against the last known point.
            ball_pt = self._last_ball_pt

        # --- players: court team, near-net, distance from the ball
        reach_px = getattr(ac, "CONTACT_REACH", ActionClassifier.CONTACT_REACH)
        for p in frame_result.get("tracked_players", []):
            bbox = p.get("bbox") or []
            if len(bbox) != 4:
                continue
            near_net = False
            court = self.court_detector
            if court is not None and getattr(court, "is_calibrated", False):
                try:
                    foot = (int((bbox[0] + bbox[2]) / 2), int(bbox[3]))
                    near_net = bool(court.is_near_net(
                        foot, threshold_px=ActionClassifier.NEAR_NET_PX))
                except Exception:      # pragma: no cover - defensive
                    near_net = False
            dist = None
            if ball_pt is not None:
                try:
                    dist = float(ActionClassifier._point_to_bbox_distance(
                        list(ball_pt), bbox, p.get("center")))
                except Exception:      # pragma: no cover - defensive
                    dist = None
            snapshot["players"].append({
                "tid": p.get("track_id"),
                "team": p.get("team"),
                "near_net": near_net,
                "predicted": bool(p.get("predicted", False)),
                "dist": dist,
                "reach": None if dist is None else bool(dist <= reach_px),
            })

        # --- classifier probe: what fired at t-7, or which gate refused it
        if self._probe_mirror and ac is not None:
            try:
                snapshot["probe"] = ac.pop_diag() or []
            except Exception:          # pragma: no cover - defensive
                snapshot["probe"] = []
        if ac is not None:
            pend = getattr(ac, "_pending", None)
            if isinstance(pend, dict):
                gest = pend.get("gesture")
                snapshot["pending"] = {
                    "frame": pend.get("frame"),
                    "player_id": pend.get("player_id"),
                    "gesture": getattr(gest, "value", gest),
                    "team": pend.get("team"),
                    "kind": pend.get("contact_kind"),
                }
        return snapshot

    def _ball_candidates(self, frame_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Every ball candidate the DETECTOR produced this frame, with the
        detector's own verdict on each (``""`` / ``"sus"`` / ``"rm"``).

        Reads the pipeline's two already-computed lists, no re-inference: the
        survivors of static suppression (what the tracker was handed) and
        ``BallDetector.raw_detections``, the pre-suppression side channel that
        keeps the candidates the tracker never saw. The two lists share dict
        objects, so an entry missing from the survivor list is exactly the one
        suppression removed -- the flag is looked up, never re-derived. Empty
        when the detector produced nothing or a component is absent (the stubs
        in tests, a partially built processor).
        """
        raw = list(getattr(getattr(self.frame_processor, "ball_detector", None),
                           "raw_detections", None) or [])
        survivors = {id(d) for d in (frame_result.get("ball_detections") or [])}
        out: List[Dict[str, Any]] = []
        for d in raw:
            center = d.get("center") or []
            bbox = d.get("bbox")
            if not ((len(center) >= 2 and center[0] is not None)
                    or (bbox and len(bbox) == 4)):
                continue
            if id(d) not in survivors:
                flag = "rm"                    # dropped by static suppression
            elif d.get("stationary_suspect"):
                flag = "sus"                   # kept, but distrusted downstream
            else:
                flag = ""
            out.append({
                "center": [float(center[0]), float(center[1])] if len(center) >= 2 else None,
                "bbox": list(bbox) if bbox and len(bbox) == 4 else None,
                "conf": d.get("confidence"),
                "flag": flag,
            })
        return out

    def _enable_probe_mirror(self) -> bool:
        """Turn the classifier's contact-probe mirror on for the panel.

        ``ActionClassifier._diag`` is the pipeline's own inert probe record
        (the ``diag_dump`` writer is its other consumer): a few dicts per
        frame, read by no threshold, branch or return value. Skipped when a
        ``DiagRecorder`` owns those records, so live debug can never steal
        entries from a dump, and never enabled outside this live path.
        """
        fp = self.frame_processor
        ac = getattr(fp, "action_classifier", None)
        if ac is None or getattr(fp, "diag", None) is not None:
            return False
        ac.diag_enabled = True
        return True

    def _compose_panel(self, frame: np.ndarray, snapshot: Optional[Dict[str, Any]],
                       total: Optional[int]) -> np.ndarray:
        """Composite the side panel for DISPLAY (the writer gets the bare frame).

        Failures degrade to the plain annotated frame: the panel is a debugging
        convenience and must never take the live window down.
        """
        if not self._panel_enabled:
            return frame
        snap = dict(snapshot or {})
        snap.setdefault("total", total)
        try:
            events = self._event_plan.at(snap.get("frame"))
            return debug_panel.compose(frame, snap, events)
        except Exception as e:
            self.logger.error("Debug panel failed at frame %s: %s",
                              snap.get("frame"), e)
            return frame

    def _setup_window(self, width: int, height: int) -> None:
        """Resizable window sized to hold the panel strip beside the frame.

        An autosized window wider than the display clips its RIGHT edge -- which
        is exactly where the panel lives -- so the live path asks for a
        resizable window and fits the composed width to the screen.
        """
        try:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(
                WINDOW_NAME,
                min(width + debug_panel.PANEL_WIDTH, 1900),
                min(height, 1000),
            )
        except cv2.error as e:      # headless / no window system
            self.logger.warning("Could not resize the debug window: %s", e)

    def _log_resolved_spikes(self) -> None:
        """Log each spike record once its outcome resolves -- origin zone plus
        where the ball ended up. A pending-dug record that later flips to
        kill (the defenders fail the set) is re-logged with its final outcome.
        """
        records = self.frame_processor.spike_analyzer.spike_records()
        for i, rec in enumerate(records):
            sig = (rec.get("frame"), rec.get("outcome"))
            if i >= len(self._spike_log_state) or self._spike_log_state[i] != sig:
                self.logger.info(
                    "Spike resolved: contact frame %s player %s %s",
                    rec.get("frame"), rec.get("track_id"),
                    describe_spike_record(rec),
                )
                # Same row in the panel, on the spike's contact frame.
                self._event_plan.add(
                    rec.get("frame"),
                    "f{}  SPIKE {}".format(rec.get("frame"),
                                           str(rec.get("spike_type") or "?").upper()),
                    describe_spike_record(rec),
                    overlay.ACTION_COLORS.get(rec.get("spike_type") or "spike",
                                              (225, 225, 225)),
                )
                if i >= len(self._spike_log_state):
                    self._spike_log_state.append(sig)
                else:
                    self._spike_log_state[i] = sig

    @staticmethod
    def _overlay_data(frame_result: Dict[str, Any]) -> Tuple[BallOverlay, PlayerOverlay, Optional[Dict[str, Any]]]:
        """Extract the lightweight ball + player boxes + game state snapshot."""
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
        game_state = frame_result.get("game_state") or None
        return ball, players, game_state

    def _render_frame(self, frame: np.ndarray, frame_idx: int, ball: BallOverlay,
                      players: PlayerOverlay, plan: overlay.LabelPlan,
                      total_frames: Optional[int] = None,
                      game_state: Optional[Dict[str, Any]] = None,
                      candidates: Optional[List[Dict[str, Any]]] = None
                      ) -> np.ndarray:
        """Draw court + ball + player boxes (labels anchored on contact frames)."""
        out = frame
        try:
            if self.court_detector is not None:
                out = self.court_detector.draw_court_overlay(out)
        except Exception as e:
            self.logger.error(f"Error rendering frame {frame_idx}: {e}")
            cv2.putText(out, f"Render Error: {str(e)[:50]}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return self._draw_overlay(out, frame_idx, ball, players, plan,
                                  total_frames=total_frames, game_state=game_state,
                                  candidates=candidates)

    def _draw_overlay(self, frame: np.ndarray, frame_idx: int, ball: BallOverlay,
                      players: PlayerOverlay, plan: overlay.LabelPlan,
                      total_frames: Optional[int] = None,
                      game_state: Optional[Dict[str, Any]] = None,
                      candidates: Optional[List[Dict[str, Any]]] = None
                      ) -> np.ndarray:
        """Draw everything EXCEPT the court lines, in ``_render_frame`` order.

        Split so the buffered live render can draw the court on the producer
        thread -- which owns the calibration state -- and the rest on the main
        thread from cached data, without changing the composited result.
        (The two-pass save still draws everything via ``_render_frame``.)
        """
        out = frame
        try:
            # Every detector candidate, under the tracked ball so the filled
            # circle stays readable. Empty list / None = overlay off.
            for cand in candidates or []:
                overlay.draw_ball_candidate(
                    out, cand.get("bbox"), cand.get("center"),
                    cand.get("conf"), cand.get("flag", ""))

            if ball is not None:
                bx, by, pred = ball
                overlay.draw_ball(out, bx, by, predicted=pred)

            # Spike flights: red fading trail + KILL marker at the landing.
            # Render-only reads of the pipeline's SpikeAnalyzer (the analyzer
            # itself is wired inside FrameProcessor, so live debug stays
            # byte-identical to the shared pipeline).
            analyzer = self.frame_processor.spike_analyzer
            overlay.draw_ball_trail(out, analyzer.trail_points(frame_idx))
            kill = analyzer.kill_annotation(frame_idx)
            if kill is not None:
                overlay.draw_kill_marker(out, kill[0], kill[1], kill[2])

            for track_id, bbox in players:
                lab = plan.active(track_id, frame_idx)
                overlay.draw_player(
                    out, track_id, bbox,
                    action=lab[0] if lab else None,
                    confidence=lab[1] if lab else None,
                )

            overlay.draw_frame_counter(out, frame_idx, total_frames)
            if game_state:
                overlay.draw_game_state(
                    out,
                    game_state.get("current_state", "game_off"),
                    len(game_state.get("points", [])),
                    provisional=bool(game_state.get("provisional", False)),
                )
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
            self._log_resolved_spikes()
            cache.append(self._overlay_data(result))
            frame_idx += 1
        # Finalise the last contact held back for its look-ahead.
        self._ingest_actions(self.frame_processor.flush_actions(), plan)
        self._log_resolved_spikes()
        self._ingest_typed_spikes(plan)
        cap.release()

        if not save_video:
            return

        # ---- Pass 2: re-read frames and draw contact-anchored labels.
        cap, *_ = self._open(video_path)
        writer = cv2.VideoWriter(save_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        for frame_idx, (ball, players, gs) in enumerate(cache):
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(self._render_frame(frame, frame_idx, ball, players, plan,
                                            total_frames=total, game_state=gs))
        cap.release()
        writer.release()
        self.logger.info(f"Annotated video written: {save_video}")

    # ------------------------------------------------------------------ #
    # Producer/consumer real-time render (--debug-live)
    # ------------------------------------------------------------------ #

    def _produce_frames(self, cap: cv2.VideoCapture, out_queue: "queue.Queue",
                        stop: threading.Event, paused: threading.Event,
                        plan: overlay.LabelPlan,
                        done: threading.Event) -> None:
        """Producer thread body: the EXACT shared processing loop, in order.

        Mirrors the batch pipeline call-for-call (``cap.read`` ->
        ``FrameProcessor.process_frame`` -> action ingest -> spike log ->
        cache overlay data); only the thread it runs on differs -- the parity
        rule is about the processing path, which this does not touch. The
        court overlay is drawn HERE, right after each frame's processing, so
        the consumer renders from cached data only and never reads
        calibration state mid-update (byte-identical compositing: court is
        still drawn first, from exactly this frame's post-process state).

        ``out_queue`` (bounded) throttles the producer to the consumer's
        delay window. The per-frame signal snapshot (``_signals``) is taken
        HERE, on the pipeline's own thread, so the consumer only ever reads a
        cached plain dict and never touches tracker/classifier state from the
        render thread. ``stop`` ends the loop WITHOUT a flush (restart/quit
        discard the tail, like the old serial loop); the natural end of
        source flushes the held-back contact and typed spikes exactly as the
        serial loop did. A sentinel follows every exit path, and ``done`` is
        set strictly AFTER it is queued -- so the consumer that observes
        ``done`` knows every frame is already enqueued and can drain without
        the delay gate (the gate alone would deadlock on the sentinel: it
        sits at the queue's back and can never be counted past the bound).
        """
        frame_idx = 0
        try:
            while not stop.is_set():
                if paused.is_set():
                    if stop.wait(0.05):
                        break
                    continue
                ret, frame = cap.read()
                if not ret:
                    # Input over: finalise the last held-back contact, then drain.
                    self._ingest_actions(self.frame_processor.flush_actions(), plan)
                    self._log_resolved_spikes()
                    self._ingest_typed_spikes(plan)
                    break
                result = self.frame_processor.process_frame(frame, frame_idx, enable_court_redetection=True)
                self._ingest_actions(result.get("actions", []), plan)
                self._log_resolved_spikes()
                ball, players, gs = self._overlay_data(result)
                signals = self._signals(result, frame_idx)
                if self.court_detector is not None:
                    frame = self.court_detector.draw_court_overlay(frame)
                out_queue.put((frame, frame_idx, ball, players, gs, signals))
                frame_idx += 1
        except Exception:
            self.logger.exception("Producer thread failed at frame %s", frame_idx)
        finally:
            out_queue.put(_PRODUCER_DONE)
            done.set()

    @staticmethod
    def _stop_producer(thread: threading.Thread, out_queue: "queue.Queue",
                       stop: threading.Event) -> None:
        """Signal the producer to stop and reap it. Draining unblocks a
        producer parked on a full queue; the sentinel marks its exit."""
        stop.set()
        while thread.is_alive():
            try:
                item = out_queue.get_nowait()
            except queue.Empty:
                item = None
            if item is _PRODUCER_DONE:
                break
            time.sleep(0.002)
        thread.join(timeout=5.0)
        if thread.is_alive():
            logging.getLogger(__name__).warning("Producer thread did not stop cleanly")

    def _process_buffered_live(self, video_path: str, save_video: Optional[str] = None) -> None:
        """Show (and optionally write) frames on a fixed delay so labels land on
        their contact frame once the classifier has emitted them.

        Decoupled producer/consumer (open point 23): the producer thread runs
        the shared processing loop ahead of display; the main thread renders
        cached overlay data at the video's pace. Displaying a frame is gated
        on the producer being a full delay deep -- the same label-latency
        guarantee as the old serial loop, but throughput is no longer
        processing + pacing: it is max(processing, pacing).
        """
        self.logger.info(f"Starting buffered live processing: {video_path}")
        cap, fps, width, height, total = self._open(video_path)
        frame_delay = (1.0 / fps) / self.debug_speed if fps > 0 else 0.033
        frame_delay_ms = max(1, int(frame_delay * 1000))
        self.logger.info(f"Video: {total} frames, {fps} FPS, {width}x{height}")
        self.frame_processor.setup_video_fps(fps)
        self.frame_processor.setup_video_dimensions(width, height)

        writer = None
        if save_video:
            writer = cv2.VideoWriter(save_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

        delay_frames = min(int(round((fps or 30) * self.LIVE_DELAY_SECONDS)), self.LIVE_DELAY_MAX_FRAMES)
        self.logger.info(
            "Press 'q' to quit, SPACE to pause/resume, 'r' to restart, "
            "'p' to toggle the signal panel, 'b' to toggle the ball-candidate "
            "overlay (labels shown on a %d-frame delay so they land on the "
            "contact frame)",
            delay_frames,
        )
        self._probe_mirror = self._enable_probe_mirror()
        self._setup_window(width, height)

        restart = True
        while restart:
            restart = False
            # Fresh per-run state: the producer owns the pipeline and all
            # writes; the main thread only renders from cached data (plus the
            # locked label-plan reads).
            plan = _ThreadSafeLabelPlan()
            frames_out: queue.Queue = queue.Queue(maxsize=delay_frames + 1)
            stop = threading.Event()
            paused = threading.Event()
            done = threading.Event()
            producer = threading.Thread(
                target=self._produce_frames,
                args=(cap, frames_out, stop, paused, plan, done),
                name="live-debug-producer",
                daemon=True,
            )
            producer.start()

            shown = None
            drained = False
            while True:
                # 1. Show the next frame once the producer is a full delay
                #    deep (same guarantee as the old serial buffer); once the
                #    producer is done (everything enqueued), drain the rest.
                item = None
                if not paused.is_set():
                    if drained or done.is_set():
                        drained = True
                        try:
                            item = frames_out.get_nowait()
                        except queue.Empty:
                            item = None
                    elif frames_out.qsize() > delay_frames:
                        item = frames_out.get()

                showed = False
                if item is _PRODUCER_DONE:
                    drained = True
                elif item is not None:
                    frame, idx, ball, players, gs, signals = item
                    shown = self._draw_overlay(frame, idx, ball, players, plan,
                                               total_frames=total, game_state=gs,
                                               candidates=(signals or {}).get("candidates"))
                    if writer is not None:
                        writer.write(shown)   # the saved video stays unpanelled
                    display = self._compose_panel(shown, signals, total)
                    cv2.imshow(WINDOW_NAME, display)
                    key = cv2.waitKey(frame_delay_ms) & 0xFF
                    showed = True
                elif drained and frames_out.empty() and not paused.is_set():
                    break  # source exhausted, buffer drained: processing ended

                if not showed:
                    # No frame shown this pass (producer still filling the
                    # delay window, or paused): keep polling controls without
                    # pacing so the window stays responsive. (waitKey returns
                    # -1 without a key -- hence the flag, not the value.)
                    key = cv2.waitKey(1) & 0xFF

                # 2. Controls.
                if key == ord('q'):
                    self._stop_producer(producer, frames_out, stop)
                    break
                elif key == ord(' '):
                    if paused.is_set():
                        paused.clear()
                        self.logger.info("Resumed")
                    else:
                        paused.set()
                        self.logger.info("Paused")
                elif key == ord('r'):
                    self._stop_producer(producer, frames_out, stop)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.frame_processor.reset_trackers()
                    self._spike_log_state = []
                    self._event_plan.reset()
                    # Fresh run: the held ball readout must not survive into
                    # the restarted video.
                    self._last_ball = None
                    self._last_ball_pt = None
                    self.logger.info("Video restarted")
                    restart = True
                    break
                elif key == ord('p'):
                    self._panel_enabled = not self._panel_enabled
                    self.logger.info("Signal panel %s",
                                     "ON" if self._panel_enabled else "OFF")
                    if self._panel_enabled:
                        self._setup_window(width, height)
                elif key == ord('b'):
                    self._candidates_enabled = not self._candidates_enabled
                    self.logger.info(
                        "Ball candidates %s (every detector ball with its "
                        "confidence; sus = stationary suspect, rm = removed by "
                        "static suppression)",
                        "ON" if self._candidates_enabled else "OFF")

        cap.release()
        if writer is not None:
            writer.release()
            self.logger.info(f"Annotated video written: {save_video}")
        cv2.destroyAllWindows()
        self.logger.info("Processing ended")
