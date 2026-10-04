"""Per-frame ball ground-contact observer (GROUND / AIR / OUT + bounce events).

Owner-requested (#80): "a signal to know when the ball at play is on the
ground or bounces out of the ground [court]" -- it marks a rally as over /
not yet started -- plus a live-debug label on the ball(s) to CHECK when the
ball falls to the ground. video_entreno has many parked/carried balls, so
the signal must be readable per ball, not only for the tracked one.

Design constraints (AGENTS.md §2/§6, mirrors the ratified #77 possession
observer):

* PURE observer inside ``FrameProcessor.process_frame`` -- the ONE shared
  path (batch, scripts, live debug all run it). It reads the tracked ball
  and the calibration's ground homography; it mutates nothing, never feeds
  back into the trackers or classifier, and adds NO key to
  ``pipeline_output.json`` (the per-frame ``frame_result["ball_ground"]``
  dict is display/diag only; the exporter reads only
  actions/spikes/game_state).
* Geometry (owner-provided derivation, verified on a synthetic pinhole
  camera before building): with H the image<->ground homography from the 4
  clicked court corners, the bbox-bottom of a ball RESTING on the sand maps
  onto its contact point. The measurable form used here is a LOCAL SCALE
  test. Let P be the mapped ground point of the bbox bottom-center and
  w_pred the projected length of a ball diameter laid on the ground at P; a
  grounded ball must measure

      ratio = bbox_width / w_pred  ~=  1.0

  An AIRBORNE ball is closer to the camera than its mapped ground point
  (its bottom ray hits the ground BEHIND the ball), so it measures WIDER
  than predicted: ratio > 1 and grows with height (owner's synthetic check:
  a ball 0.5 m up maps ~2.4 m beyond its true ground position, 1 m up
  already maps past a mid-court position). Both measured noise sources push
  the ratio UP, never down -- occlusion clips the bbox bottom (bottom edge
  higher in the image -> mapped point farther -> smaller w_pred) and motion
  blur widens the bbox -- so errors move AWAY from a false GROUND, the safe
  direction for a rally-end signal.
* Ball-at-play selection is the TRACKED BALL only: parked balls are
  stationary-suspect and distrusted by the tracker, and predicted/coasting
  frames carry an ESTIMATED bbox that is never read as evidence -- on those
  frames the observer HOLDS the last state (mirrors #77). The per-box
  verdict helper (:func:`measure_box`) lets live debug tag every DETECTOR
  candidate with its own groundedness, so parked balls can be told from the
  ball in play by eye.
* Hysteresis: enter GROUND/OUT at ratio <= GROUND_ENTER_RATIO, return to
  AIR only at ratio >= AIR_EXIT_RATIO (the band between holds the previous
  state). OUT = grounded AND the mapped point outside the court rect
  inflated by OUT_MARGIN_M. BOUNCE = image-vy sign reversal + -> - (falling
  -> rising; a lob APEX reverses the opposite way, - -> +, and never
  fires) on consecutive real frames, gated on a near-ground ratio at the
  reversal frame, re-armed only by another fast-falling frame.
* CAVEAT (recorded): display/diag-only v1 -- nothing ends a rally on it.
  Wiring into game-state point endings is a later, GT-validated step.
"""

import math
from typing import Any, Dict, Optional, Tuple

import numpy as np

# Beach volleyball ball: circumference 66-68 cm -> diameter ~0.67/pi m.
# (Same value as ball_side_possession._BALL_DIAMETER_M; kept local so both
# observer modules stand alone.)
BALL_DIAMETER_M = 0.67 / math.pi

# Hysteresis band (see module docstring). Measured regimes on the synthetic
# pinhole check: grounded 0.99-1.03; 0.3 m up ~1.15; 1 m up ~1.7. Occlusion
# and blur only inflate. Enter ground conservatively (1.25), leave at 1.45.
GROUND_ENTER_RATIO = 1.25
AIR_EXIT_RATIO = 1.45

# The bounce gate is slightly looser than the GROUND enter edge: at the
# impact frame the bbox is at its widest (impact smear), so a real bounce
# can measure a little above the entry threshold.
BOUNCE_RATIO_MAX = 1.35

# A bounce needs a real fall into and a real rise out of the contact:
# |vy| below this is tracker jitter, not ballistics (px/frame).
MIN_BOUNCE_VY_PXF = 2.0

# OUT margin (m) around the court rect: the mapped contact point must be
# this far outside the 8 x 16 m rect for the OUT state.
OUT_MARGIN_M = 0.25

# Mapped points beyond these bounds are homography garbage (the bbox bottom
# crossed the horizon / wrapped through the line at infinity), not places a
# ball can rest: forced AIR with ``degenerate`` set.
_WORLD_X_BOUNDS = (-120.0, 150.0)
_WORLD_Y_BOUNDS = (-25.0, 400.0)

STATE_AIR = "air"
STATE_GROUND = "ground"
STATE_OUT = "out"


def _apply_h(H: np.ndarray, u: float, v: float) -> Optional[Tuple[float, float]]:
    """Apply a 3x3 homography to one pixel; None past the horizon (w <= 0).

    A ground-plane image->world H maps pixels BELOW the horizon to finite
    world points; at the horizon w -> 0 and above it the point inverts
    through the line at infinity (negative w). Those cannot be grounded
    contact points.
    """
    w = H[2, 0] * u + H[2, 1] * v + H[2, 2]
    if w <= 1e-9:
        return None
    return (
        (H[0, 0] * u + H[0, 1] * v + H[0, 2]) / w,
        (H[1, 0] * u + H[1, 1] * v + H[1, 2]) / w,
    )


def _sane_world(wx: float, wy: float) -> bool:
    return (
        math.isfinite(wx) and math.isfinite(wy)
        and _WORLD_X_BOUNDS[0] <= wx <= _WORLD_X_BOUNDS[1]
        and _WORLD_Y_BOUNDS[0] <= wy <= _WORLD_Y_BOUNDS[1]
    )


def measure_box(H_i2w: Optional[np.ndarray], H_w2i: Optional[np.ndarray],
                bbox) -> Optional[Dict[str, Any]]:
    """Pure geometry for ONE box: the ground-contact measurement row.

    Maps the bbox bottom-center through the ground homography, predicts the
    pixel width of a ball resting on the ground there (a diameter laid on
    the ground along the court's width axis), and returns

        {"ratio", "width_px", "w_pred_px", "world", "in_court",
         "degenerate"}

    ``degenerate`` marks an unusable mapped point (above horizon / garbage
    magnitude) -- a state caller, not this function, decides it means AIR.
    Returns None when the homographies are missing or the bbox is not a
    usable rectangle.
    """
    if H_i2w is None or H_w2i is None or bbox is None or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(x1) and math.isfinite(x2)
            and math.isfinite(y1) and math.isfinite(y2)):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    width_px = x2 - x1
    u, v = (x1 + x2) / 2.0, y2

    world = _apply_h(H_i2w, u, v)
    if world is None or not _sane_world(*world):
        return {"ratio": None, "width_px": width_px, "w_pred_px": None,
                "world": None, "in_court": None, "degenerate": True}

    wx, wy = world
    p0 = _apply_h(H_w2i, wx, wy)
    p1 = _apply_h(H_w2i, wx + BALL_DIAMETER_M, wy)
    if p0 is None or p1 is None:
        return {"ratio": None, "width_px": width_px, "w_pred_px": None,
                "world": None, "in_court": None, "degenerate": True}
    w_pred = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    if w_pred <= 1e-6:
        return {"ratio": None, "width_px": width_px, "w_pred_px": None,
                "world": None, "in_court": None, "degenerate": True}

    m = OUT_MARGIN_M
    in_court = (-m <= wx <= 8.0 + m) and (-m <= wy <= 16.0 + m)
    return {
        "ratio": width_px / w_pred,
        "width_px": width_px,
        "w_pred_px": w_pred,
        "world": [float(wx), float(wy)],
        "in_court": bool(in_court),
        "degenerate": False,
    }


class BallGroundContactObserver:
    """Hysteresis GROUND/AIR/OUT state + bounce events for the tracked ball.

    Reads only ``tracked_ball`` (bbox + velocity) and the calibration's
    ground homography. Predicted/lost frames hold the last state. A bounce
    is announced once per +vy -> -vy reversal on consecutive real frames
    (gated near the ground, re-armed by the next fast fall), so repeated
    bounces count and vy jitter around zero never does.
    """

    def __init__(self) -> None:
        self._H_i2w: Optional[np.ndarray] = None
        self._H_w2i: Optional[np.ndarray] = None
        self._state: Optional[str] = None
        self.bounces: int = 0
        self._armed = True
        self._prev_vy: Optional[float] = None
        self._prev_vy_frame: Optional[int] = None

    # -- configuration -------------------------------------------------- #

    def set_calibration(self, court_calibration: Any) -> None:
        """(Re)build the ground homographies from a CourtCalibration."""
        self._H_i2w = None
        self._H_w2i = None
        self._H_i2w, self._H_w2i = self.calibration_homographies(court_calibration)

    @staticmethod
    def _sign_normalized(H: np.ndarray, court_calibration: Any) -> np.ndarray:
        """Normalize the homography's arbitrary overall sign.

        findHomography's scale is arbitrary: normalize so ON-court points
        give w > 0. That makes _apply_h's w <= 0 guard a true horizon test
        (points across the vanishing line invert through it and must read
        degenerate, not garbage).
        """
        corners = getattr(court_calibration, "court_corners", None)
        if corners is not None and len(corners) >= 4:
            c = np.mean(np.asarray(corners[:4], dtype=np.float64).reshape(-1, 2), axis=0)
            w = float(H[2, 0] * c[0] + H[2, 1] * c[1] + H[2, 2])
            if w < 0:
                H = -H
        return H

    @staticmethod
    def calibration_homographies(court_calibration: Any
                                 ) -> Tuple[Optional[np.ndarray],
                                            Optional[np.ndarray]]:
        """(image->world, world->image) pair for render-side reads.

        Live debug tags detector candidates with :func:`measure_box` on the
        producer thread; this is the sanctioned read-only path to the same
        homographies the observer uses (no calibration state is mutated).
        """
        getter = getattr(court_calibration, "compute_ground_homography", None)
        H = getter() if callable(getter) else None
        if H is None:
            return None, None
        H = BallGroundContactObserver._sign_normalized(np.asarray(H, dtype=np.float64),
                                                       court_calibration)
        try:
            return H, np.linalg.inv(H)
        except np.linalg.LinAlgError:
            return None, None

    def reset(self) -> None:
        """Forget all per-video state (homographies stay)."""
        self._state = None
        self.bounces = 0
        self._armed = True
        self._prev_vy = None
        self._prev_vy_frame = None

    # -- per-frame observation ------------------------------------------ #

    def observe(self, frame_index: int,
                tracked_ball: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Observe one frame; returns the display/diag row (never mutates
        ``tracked_ball``)."""
        tb = tracked_ball or {}
        bbox = tb.get("bbox")
        usable = (bbox is not None and len(bbox) == 4
                  and not tb.get("is_predicted"))

        row: Dict[str, Any] = {
            "state": self._state,
            "held": True,
            "ratio": None,
            "width_px": None,
            "w_pred_px": None,
            "world": None,
            "in_court": None,
            "degenerate": False,
            "bounce": False,
            "bounces": self.bounces,
            "vy": None,
        }
        meas = measure_box(self._H_i2w, self._H_w2i, bbox) if usable else None
        if meas is None:
            return row                     # lost / predicted / uncalibrated

        ratio = meas["ratio"]
        degenerate = meas["degenerate"]
        exit_air = degenerate or (ratio is not None
                                  and ratio >= AIR_EXIT_RATIO)
        enter_ground = (not degenerate and ratio is not None
                        and ratio <= GROUND_ENTER_RATIO)
        if exit_air:
            self._state = STATE_AIR
        elif enter_ground:
            self._state = STATE_GROUND if meas["in_court"] else STATE_OUT
        elif self._state in (STATE_GROUND, STATE_OUT):
            # Hysteresis band: keep the grounded state, but re-locate in/out
            # (a rolling ball can cross the line while it stays grounded).
            self._state = STATE_GROUND if meas["in_court"] else STATE_OUT
        # else: band with a prior AIR (or unknown) -> hold.

        # Bounce: +vy -> -vy reversal (falling -> rising) on consecutive
        # real frames, near the ground, armed by the previous fast fall.
        vy = tb.get("velocity")
        vy = float(vy[1]) if (isinstance(vy, (list, tuple)) and len(vy) >= 2
                              and vy[1] is not None) else None
        consecutive = (self._prev_vy_frame is not None
                       and frame_index - self._prev_vy_frame == 1)
        if (vy is not None and self._prev_vy is not None and consecutive
                and self._armed
                and self._prev_vy >= MIN_BOUNCE_VY_PXF
                and vy <= -MIN_BOUNCE_VY_PXF
                and ratio is not None and ratio <= BOUNCE_RATIO_MAX):
            self.bounces += 1
            row["bounce"] = True
            self._armed = False
        if vy is not None:
            if vy >= MIN_BOUNCE_VY_PXF:
                self._armed = True         # fell again: next reversal counts
            self._prev_vy = vy
            self._prev_vy_frame = int(frame_index)

        row.update({
            "state": self._state,
            "held": False,
            "ratio": ratio,
            "width_px": meas["width_px"],
            "w_pred_px": meas["w_pred_px"],
            "world": meas["world"],
            "in_court": meas["in_court"],
            "degenerate": degenerate,
            "bounces": self.bounces,
            "vy": vy,
        })
        return row

    # -- display helpers ------------------------------------------------- #

    @staticmethod
    def box_verdict(H_i2w: Optional[np.ndarray],
                    H_w2i: Optional[np.ndarray], bbox) -> Optional[str]:
        """Per-box groundedness verdict for detector candidates (no
        trajectory, no hysteresis): "ground" / "air" / None (band or
        unmeasurable). Lets live debug tag parked balls vs the ball in
        play; it is a per-box geometric read, never pipeline state."""
        m = measure_box(H_i2w, H_w2i, bbox)
        if m is None or m["degenerate"] or m["ratio"] is None:
            return None
        if m["ratio"] <= GROUND_ENTER_RATIO:
            return STATE_GROUND
        if m["ratio"] >= AIR_EXIT_RATIO:
            return STATE_AIR
        return None
