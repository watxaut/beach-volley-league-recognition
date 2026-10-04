"""Per-frame ball-side possession observer (near/far + net crossing).

Owner-ratified 2026-10-04 (#77, STATUS open point 9): the post-hoc layer
needs a continuous per-frame read of WHICH half the ball is in and WHEN it
crosses the net plane, and live debug must show it ("possession" label plus a
"crossing" label; last known location while the ball is unknown).

Design constraints (AGENTS.md §2/§5/§6):

* PURE observer inside ``FrameProcessor.process_frame`` — the ONE shared
  path (batch, scripts, live debug all run it). It reads the tracked ball
  and the calibration; it mutates nothing, never feeds back into the
  trackers or classifier, and adds NO key to ``pipeline_output.json`` (the
  per-frame ``frame_result["ball_possession"]`` dict is display/diag only;
  the exporter reads only actions/spikes/game_state).
* Ball pixel WIDTH is the depth signal in this long-axis geometry (§5:
  image-plane ball side is unusable; width regimes ~14-28 px far vs
  ~30-55 px near). Predicted/coasting frames carry an ESTIMATED bbox and
  are never read as width evidence; on those frames the observer HOLDS the
  last known state (owner instruction).
* Bands are PER-VIDEO, derived from the calibration via the owner's pinhole
  model (#77): with w_near/w_far the projected baseline widths and
  D = 0.67/pi m the ball's ideal pixel diameter at the net plane is

      d_net = D * w_near * w_far / (4 * (w_near + w_far))

  MEASURED REGIMES (session #78, owner-flagged windows on the match and the
  full practice video, `scripts/probe_possession_feedback.py`): a FLYING
  near-half ball measures 1.55-1.6x d_net; a ball AT the net plane (tape
  dribble, mesh, resting/rolled) and a motion-blurred FAR flight BOTH
  measure 1.0-1.35x d_net -- width cannot split those two; a crisp FAR
  ground bounce measures 0.5-0.8x d_net. The original factors (1.15/1.55,
  fit on flying balls) put the far threshold INSIDE the net-plane regime,
  so occlusion dips on the near side committed FAR -- the owner-reported
  bias. Recalibrated: FAR_FACTOR 0.85 (only genuine far-ground/low-far
  evidence commits far), NEAR_FACTOR 1.55 unchanged; the overlap regime
  reads as CROSSING (band) and HOLDS the last committed side.
* Owner instruction (#78, "do the greatest of the sides"): all band
  decisions use the MAXIMUM width seen in the last EVIDENCE_WINDOW_FRAMES
  measured frames, so an occluded near-side ball (tape/mesh/player clipping
  the bbox) cannot out-vote a recent larger measurement. Evidence ages out
  by frame index (predicted stretches freeze it, so a long dropout still
  holds).

CAVEAT (recorded, #77): display-only v1 -- nothing acts on this signal and
no Config key exists. The far-flight/net-rest overlap means far commits land
at deep-far/bounce moments by design (owner chose the near/crossing bias).
"""

import math
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

# Beach volleyball ball: circumference 66-68 cm -> diameter ~0.67/pi m.
_BALL_DIAMETER_M = 0.67 / math.pi

# Measured width regimes (session #78; see module docstring).
FAR_FACTOR = 0.85
NEAR_FACTOR = 1.55

# Owner instruction (#78): band decisions use the max width over this many
# measured frames, so occlusion dips cannot out-vote a recent larger
# measurement.
EVIDENCE_WINDOW_FRAMES = 12

# Uncalibrated fallback = the factors applied to a nominal d_net of ~22.6 px
# (the match value). Venue-coupled by definition; bands are recomputed from
# the calibration the moment one is set.
FALLBACK_FAR_PX = 19.0
FALLBACK_NEAR_PX = 35.0

SIDE_NEAR = "near"
SIDE_FAR = "far"


def net_plane_width_px(court_corners) -> Optional[float]:
    """Ideal ball px width at the net plane from the 4 court corners.

    Corners follow the CourtCalibration convention (clockwise from
    far-left): the NEAR baseline is the pair with the 2 largest y. Returns
    None unless the near pair projects wider than the far pair (sanity).
    """
    if court_corners is None:
        return None
    try:
        pts = [(float(x), float(y)) for x, y in court_corners]
    except (TypeError, ValueError):
        return None
    if len(pts) != 4:
        return None
    order = sorted(range(4), key=lambda i: pts[i][1])
    near = [pts[order[2]], pts[order[3]]]  # largest y = closest to camera
    far = [pts[order[0]], pts[order[1]]]
    w_near = abs(near[0][0] - near[1][0])
    w_far = abs(far[0][0] - far[1][0])
    if w_near <= 0 or w_far <= 0 or w_near <= w_far:
        return None
    return _BALL_DIAMETER_M * w_near * w_far / (4.0 * (w_near + w_far))


class BallSidePossessionObserver:
    """Hysteresis near/far side read + crossing flag, from ball bbox width.

    All band decisions read the ROLLING MAX of the measured widths
    ("greatest of the sides", owner #78), so near-side occlusion dips
    cannot commit far behind a recent larger measurement. Committed sides
    persist (last-known); a crossing is announced once a previously
    committed side is seen INSIDE the net band; a genuine crossing counts
    in ``crossings`` when the OPPOSITE side commits -- which the rolling
    max DELAYS by up to EVIDENCE_WINDOW_FRAMES (the label shows CROSSING
    while the evidence decays; flap-backs to the same side never count).
    """

    def __init__(self) -> None:
        self.net_width_px: Optional[float] = None
        self.far_px: float = FALLBACK_FAR_PX
        self.near_px: float = FALLBACK_NEAR_PX
        self.crossings: int = 0
        self._side: Optional[str] = None
        self._crossing: bool = False
        self._crossing_from: Optional[str] = None
        self._last_width: Optional[float] = None
        self._last_width_frame: Optional[int] = None
        self._evidence: List[Tuple[int, float]] = []  # (frame, width) window

    # -- configuration -------------------------------------------------- #

    def set_calibration(self, court_calibration: Any) -> None:
        """Recompute the band from a CourtCalibration's court corners."""
        d = net_plane_width_px(getattr(court_calibration, "court_corners", None))
        if d is not None and d > 0:
            self.net_width_px = float(d)
            self.far_px = FAR_FACTOR * d
            self.near_px = NEAR_FACTOR * d
        # else: keep the fallback bands (uncalibrated).

    def reset(self) -> None:
        """Forget all per-video state (bands stay)."""
        self.crossings = 0
        self._side = None
        self._crossing = False
        self._crossing_from = None
        self._last_width = None
        self._last_width_frame = None
        self._evidence.clear()

    # -- per-frame observation ------------------------------------------ #

    def observe(self, frame_index: int, tracked_ball: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Observe one frame; returns the display/diag row (never mutates
        ``tracked_ball``)."""
        tb = tracked_ball or {}
        bbox = tb.get("bbox")
        width = None
        if (bbox is not None and len(bbox) == 4
                and not tb.get("is_predicted")):
            try:
                width = float(bbox[2]) - float(bbox[0])
            except (TypeError, ValueError):
                width = None

        if width is not None and width > 0:
            self._last_width = width
            self._last_width_frame = int(frame_index)
            # "Greatest of the sides" (owner #78): decisions read the rolling
            # max. Entries age out by FRAME index on the next measurement, so
            # a predicted stretch freezes the evidence (holds) and stale
            # widths drop once real measurements resume.
            self._evidence.append((int(frame_index), width))
            cutoff = int(frame_index) - EVIDENCE_WINDOW_FRAMES
            while self._evidence and self._evidence[0][0] < cutoff:
                self._evidence.pop(0)
            evidence = max(w for _, w in self._evidence)
            if evidence >= self.near_px:
                self._commit(SIDE_NEAR)
            elif evidence <= self.far_px:
                self._commit(SIDE_FAR)
            elif self._side is not None:
                # Inside the net band with a prior committed side.
                if not self._crossing:
                    self._crossing = True
                    self._crossing_from = self._side
        # else: no width evidence (ball lost / predicted) -> HOLD the last
        # known side and crossing state (owner instruction).

        return {
            "side": self._side,
            "crossing": self._crossing,
            "width_px": self._last_width,
            "width_frame": self._last_width_frame,
            "evidence_width_px": (max(w for _, w in self._evidence)
                                  if self._evidence else None),
            "net_width_px": self.net_width_px,
            "far_px": self.far_px,
            "near_px": self.near_px,
        }

    def _commit(self, side: str) -> None:
        if self._crossing and side != self._crossing_from:
            self.crossings += 1
        self._side = side
        self._crossing = False
        self._crossing_from = None
