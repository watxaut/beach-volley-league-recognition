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
* Bands are PER-VIDEO, derived from the calibration via the owner's
  pinhole model (#77): with w_near/w_far the projected baseline widths and
  D = 0.67/pi m the ball's ideal pixel diameter at the net plane is

      d_net = D * w_near * w_far / (4 * (w_near + w_far))

  Measured detector widths at the net run ~1.15x-1.55x of d_net on this
  footage (match: d_net 22.8 px -> measured abstain band 26-35 px, i.e.
  exactly the classifier's constants), so the crossing band is
  [FAR_FACTOR, NEAR_FACTOR] * d_net. CAVEAT (recorded, #77): the factors
  were fit on the MATCH; the practice venue's measured far regime tops at
  ~28 px while 1.15x * d_net there is ~30.9 px, so drills may read
  "crossing" while still deep far-side. Display-only v1; validate before
  anything acts on it. Uncalibrated falls back to 26/35 px.
"""

import math
from typing import Any, Dict, Optional

# Beach volleyball ball: circumference 66-68 cm -> diameter ~0.67/pi m.
_BALL_DIAMETER_M = 0.67 / math.pi

# Measured bbox-vs-ideal bias at the net plane (fit on the 20260920 match).
FAR_FACTOR = 1.15
NEAR_FACTOR = 1.55

# Uncalibrated fallback: the validated classifier abstain band (venue-coupled
# constants, AGENTS §5 / src/recognition constants for the match geometry).
FALLBACK_FAR_PX = 26.0
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

    Committed sides persist (last-known); a crossing is only announced once
    a previously committed side is seen INSIDE the net band, and only a
    completed transition to the OPPOSITE side increments ``crossings``
    (flap-backs to the same side do not count).
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
            if width >= self.near_px:
                self._commit(SIDE_NEAR)
            elif width <= self.far_px:
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
