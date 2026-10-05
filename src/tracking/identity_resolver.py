"""Team-structured identity resolver: P1A/P2A/P1B/P2B across side switches.

Display/attribution-only pure observer over the tracker's per-frame output
(the GT-validated tracker never reads it). It re-derives, every frame, which
enrolled player each tracked body is, and is built around the one structural
fact that survives every venue, camera height and kit: **during play the two
players of a team are on the same side of the net, opposite the other team.**
That splits identity into small decisions instead of one 4-way guess:

1. **Orientation** -- which squad is on the NEAR side. Piecewise constant: it
   only changes at a side switch (minutes apart). Every clean in-court body
   gives evidence ``x = best squad-1 - best squad-2 similarity`` on FIXED
   enrollment anchors (sign-flipped on the far side). Per side that evidence
   sits at one level when squad 1 is near and another when squad 2 is; a
   two-state log-likelihood test (per-body clipped, tempered, accumulated
   CUSUM-style) flips the orientation when the other state explains all the
   bodies better for long enough. The current state's levels are measured in
   the opening (the enrolled orientation) and follow slow drift; the unseen
   state starts mirrored and is measured once it has held. On the owner's
   20260920 match (#85 replay, ``scripts/replay_identity.py``) this gives
   exactly the 4 real switches, each inside its GT window, and 0
   wrong-orientation frames -- where #83's absolute comparison gave 18 flips
   and #84's "any shift from baseline" test 16 (a 1-sigma drift of pose and
   light froze its baseline and pinned it at threshold).
2. **Who is who within a side** -- per-tracklet EMAs of the similarity to each
   player (anchors + prototypes learned in that view + height), the better
   permutation with hysteresis scaled by this video's own teammate-margin
   spread, a quick override for silent id swaps, crops behind or merged with
   another body ignored. Every in-court body gets a label unless the
   orientation is in doubt (labels are withheld then -- a blank costs an
   unattributed action, a wrong label corrupts a player's stats).

Measurement (``measure``: side, eligibility, descriptor, height per tracked
player) is separate from the decision (``update_observed``), so a run can be
dumped once and the decision replayed offline (``scripts/replay_identity.py``).

**Second view.** While the orientation is settled, clearly assigned, isolated
in-court bodies add prototypes to their player's model for the view they are
seen in. They serve the within-side decision only; the orientation statistic
never reads them, so a wrong label cannot feed back into the orientation.

Descriptor: per body part (head / upper / lower), a 40-bin HSV histogram --
12 hue x 3 saturation bins for chromatic pixels plus 4 value bins for
achromatic ones (black/white/grey kit that a hue-saturation histogram cannot
see) -- background-weighted against a band OUTSIDE the box (sand/dunes are
the commonest colour in every crop), on a crop resampled to a fixed height so
near (300 px) and far (100 px) players are compared at the same detail.
Similarity is the Bhattacharyya coefficient. Height uses the LATERAL ground
scale at the foot (metres per pixel across the image at the player's depth),
which is roughly view-consistent unlike the area-averaged world size.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

logger = logging.getLogger(__name__)

NEAR, FAR = "near", "far"
VIEWS = (NEAR, FAR)

# --------------------------------------------------------------------------- #
# Descriptor
# --------------------------------------------------------------------------- #

# (name, top fraction, bottom fraction, weight) of the box height.
_PARTS: Tuple[Tuple[str, float, float, float], ...] = (
    ("head", 0.00, 0.15, 0.20),
    ("upper", 0.15, 0.45, 0.45),
    ("lower", 0.45, 0.72, 0.35),
)
PART_WEIGHTS = np.array([p[3] for p in _PARTS], dtype=np.float64)
N_PARTS = len(_PARTS)
_H_BINS, _S_BINS, _V_BINS = 12, 3, 4
N_BINS = _H_BINS * _S_BINS + _V_BINS
_CHROMA_MIN_S = 50
_CHROMA_MIN_V = 50
_CANON_H = 64            # crops resampled to this height (near and far alike)
_FG_COLS = (0.2, 0.8)    # central columns of the box: the body, not its margin
_BG_BAND = 0.25          # background band width beside the box (x box width)


@dataclass
class Descriptor:
    """Per-part sqrt-normalised histograms (rows sum-of-squares to 1)."""

    parts: np.ndarray  # (N_PARTS, N_BINS) float64
    mask: np.ndarray   # (N_PARTS,) bool -- part had foreground pixels


def _bin_index(hsv: np.ndarray) -> np.ndarray:
    """Per-pixel bin: chromatic H x S, or one of 4 achromatic V bins."""
    h = hsv[..., 0].astype(np.int32)
    s = hsv[..., 1].astype(np.int32)
    v = hsv[..., 2].astype(np.int32)
    chroma = (s >= _CHROMA_MIN_S) & (v >= _CHROMA_MIN_V)
    h_bin = np.minimum(h * _H_BINS // 180, _H_BINS - 1)
    s_bin = np.minimum(
        (s - _CHROMA_MIN_S) * _S_BINS // (256 - _CHROMA_MIN_S), _S_BINS - 1
    )
    s_bin = np.maximum(s_bin, 0)
    v_bin = np.minimum(v * _V_BINS // 256, _V_BINS - 1)
    return np.where(chroma, h_bin * _S_BINS + s_bin, _H_BINS * _S_BINS + v_bin)


def compute_descriptor(frame: Optional[np.ndarray], bbox: Sequence[float]) -> Optional[Descriptor]:
    """Background-weighted, resolution-normalised part histograms of a body.

    Returns None when the box is degenerate or outside the frame.
    """
    if frame is None or bbox is None or len(bbox) != 4:
        return None
    fh, fw = frame.shape[:2]
    x1, y1, x2, y2 = (float(v) for v in bbox)
    x1i, y1i = max(0, int(round(x1))), max(0, int(round(y1)))
    x2i, y2i = min(fw, int(round(x2))), min(fh, int(round(y2)))
    bw, bh = x2i - x1i, y2i - y1i
    if bw < 4 or bh < 8:
        return None
    band = max(1, int(round(_BG_BAND * bw)))
    ex1, ex2 = max(0, x1i - band), min(fw, x2i + band)
    crop = frame[y1i:y2i, ex1:ex2]
    if crop.size == 0:
        return None
    scale = _CANON_H / float(bh)
    cw = max(4, int(round(crop.shape[1] * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    crop = cv2.resize(crop, (cw, _CANON_H), interpolation=interp)
    idx = _bin_index(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV))

    # Box columns inside the extended crop (after the resample).
    bx1 = int(round((x1i - ex1) * scale))
    bx2 = int(round((x2i - ex1) * scale))
    bx1, bx2 = max(0, min(cw, bx1)), max(0, min(cw, bx2))
    if bx2 - bx1 < 2:
        return None
    fg1 = bx1 + int(round(_FG_COLS[0] * (bx2 - bx1)))
    fg2 = bx1 + max(int(round(_FG_COLS[1] * (bx2 - bx1))), 1)

    # Background-weighted histogram (Comaniciu et al.): bins that dominate the
    # band beside the box are down-weighted by o_min / o_u.
    bg_pixels = np.concatenate([idx[:, :bx1].ravel(), idx[:, bx2:].ravel()])
    weights = np.ones(N_BINS, dtype=np.float64)
    if bg_pixels.size >= 8:
        bg = np.bincount(bg_pixels, minlength=N_BINS).astype(np.float64)
        bg /= bg.sum()
        nz = bg > 0
        weights[nz] = np.minimum(1.0, bg[nz].min() / bg[nz])

    parts = np.zeros((N_PARTS, N_BINS), dtype=np.float64)
    mask = np.zeros(N_PARTS, dtype=bool)
    for i, (_name, top, bottom, _w) in enumerate(_PARTS):
        r1 = int(round(top * _CANON_H))
        r2 = max(r1 + 1, int(round(bottom * _CANON_H)))
        region = idx[r1:r2, fg1:fg2]
        if region.size == 0:
            continue
        hist = np.bincount(region.ravel(), minlength=N_BINS).astype(np.float64) * weights
        total = hist.sum()
        if total <= 0:
            continue
        parts[i] = np.sqrt(hist / total)
        mask[i] = True
    if not mask.any():
        return None
    return Descriptor(parts=parts, mask=mask)


def lateral_height_m(court, bbox: Sequence[float]) -> Optional[float]:
    """Body height in metres from the LATERAL ground scale at the foot.

    A standing person is roughly fronto-parallel, so pixel height times the
    metres-per-pixel ACROSS the image at their depth approximates real height
    the same way near and far (the depth axis of the homography is what makes
    ``world_body_size`` view-dependent). None without a ground homography.
    """
    if court is None or not hasattr(court, "image_to_world"):
        return None
    try:
        fx = (float(bbox[0]) + float(bbox[2])) / 2.0
        fy = float(bbox[3])
        a = court.image_to_world((fx, fy))
        b = court.image_to_world((fx + 1.0, fy))
    except Exception:  # pragma: no cover - defensive: odd calibrations
        return None
    if a is None or b is None:
        return None
    sx = float(np.hypot(b[0] - a[0], b[1] - a[1]))
    pixel_h = float(bbox[3]) - float(bbox[1])
    if sx <= 0 or pixel_h <= 0:
        return None
    return pixel_h * sx


def stack_descriptors(descs: Sequence[Descriptor]) -> Tuple[np.ndarray, np.ndarray]:
    if not descs:
        return np.zeros((0, N_PARTS, N_BINS)), np.zeros((0, N_PARTS), dtype=bool)
    return (
        np.stack([d.parts for d in descs]),
        np.stack([d.mask for d in descs]),
    )


def appearance_scores(
    proto_parts: np.ndarray, proto_mask: np.ndarray,
    parts: np.ndarray, mask: np.ndarray,
) -> np.ndarray:
    """Max-over-prototypes part-weighted Bhattacharyya similarity.

    proto_*: (K, P, B) / (K, P); parts/mask: (N, P, B) / (N, P).
    Returns (N,) in [0, 1] (0 when nothing comparable).
    """
    if proto_parts.shape[0] == 0 or parts.shape[0] == 0:
        return np.zeros(parts.shape[0])
    dots = np.einsum("kpb,npb->knp", proto_parts, parts)
    valid = proto_mask[:, None, :] & mask[None, :, :]
    w = PART_WEIGHTS[None, None, :] * valid
    denom = w.sum(axis=2)
    num = (dots * w).sum(axis=2)
    sims = np.where(denom > 0, num / np.maximum(denom, 1e-9), 0.0)
    return sims.max(axis=0)


def mean_descriptor(descs: Sequence[Descriptor]) -> Optional[Descriptor]:
    """Average of the (squared) histograms, re-square-rooted, per part."""
    if not descs:
        return None
    parts, mask = stack_descriptors(descs)
    out = np.zeros((N_PARTS, N_BINS))
    out_mask = np.zeros(N_PARTS, dtype=bool)
    for i in range(N_PARTS):
        rows = parts[mask[:, i], i, :]
        if rows.shape[0] == 0:
            continue
        mean = (rows ** 2).mean(axis=0)
        total = mean.sum()
        if total > 0:
            out[i] = np.sqrt(mean / total)
            out_mask[i] = True
    if not out_mask.any():
        return None
    return Descriptor(out, out_mask)


# --------------------------------------------------------------------------- #
# Resolver
# --------------------------------------------------------------------------- #


@dataclass
class BodyObs:
    """One tracked player in one frame, as MEASURED (no identity decision).

    ``measure`` produces these from a frame; ``update_observed`` decides from
    them alone -- so a run can be dumped once and the decision layer replayed
    offline (``scripts/replay_identity.py``) without the video or weights.
    """

    tid: int
    bbox: List[float]
    side: Optional[str]          # NEAR / FAR by the foot, None if unknown
    predicted: bool = False      # coasting box (no detection behind it)
    eligible: bool = False       # foot in court (+slack) or in a serve zone
    in_court: bool = False       # foot in court (+slack): learnable
    desc: Optional[Descriptor] = None   # only for real, eligible bodies
    height: Optional[float] = None


@dataclass
class _PlayerModel:
    label: str
    squad: int
    slot: str
    anchor_view: str
    anchors: List[Descriptor] = field(default_factory=list)   # fixed, enrolled view
    learned: Dict[str, List[Descriptor]] = field(default_factory=lambda: {NEAR: [], FAR: []})
    heights: List[float] = field(default_factory=list)
    last_learn: Dict[str, int] = field(default_factory=lambda: {NEAR: -10**9, FAR: -10**9})


@dataclass
class _Level:
    """Running mean / spread (EMA once warmed up, plain average before)."""

    mu: float = 0.0
    var: float = 0.0
    n: int = 0

    def add(self, x: float, alpha: float) -> None:
        self.n += 1
        a = max(1.0 / self.n, alpha)
        d = x - self.mu
        self.mu += a * d
        self.var = (1.0 - a) * self.var + a * d * (x - self.mu)

    def sigma(self, floor: float) -> float:
        return float(np.sqrt(max(self.var, floor * floor)))


@dataclass
class _TidState:
    center: Tuple[float, float]
    width: float
    last_frame: int
    side: Optional[str]
    ema: Optional[np.ndarray] = None    # slow EMA of the 4 player similarities
    fast: Optional[np.ndarray] = None   # quick EMA: catches a silent swap
    n: int = 0
    heights: Deque[float] = field(default_factory=lambda: deque(maxlen=15))
    hold: Optional[int] = None          # player index held by this track id


def _other(view: str) -> str:
    return FAR if view == NEAR else NEAR


class TeamIdentityResolver:
    """Per-frame P1A/P2A/P1B/P2B labels that survive side switches.

    ORIENTATION (which squad is near): a two-state likelihood test on
    per-body evidence from the FIXED enrollment anchors (see
    ``_update_orientation``). Learned prototypes never enter it, so a wrong
    label cannot feed back into the orientation.

    WHO IS WHO within a side: per-tracklet EMAs of the similarity to each
    player (anchors + prototypes learned in that view + height), assigned by
    the better permutation with hysteresis scaled by the video's own teammate
    margin spread. Every in-court body on a side gets one of that side's two
    labels (strangers excepted), so labels are shown whenever the orientation
    is not in doubt.
    """

    HEIGHT_WEIGHT = 0.25
    HEIGHT_SIGMA_M = 0.15
    N_ANCHOR_SAMPLES = 4
    MAX_LEARNED = 10
    # Orientation: two-state likelihood test (per-body evidence, see class doc)
    ORIENT_WARMUP_FRAMES = 300   # the opening is the enrolled orientation (E1)
    ORIENT_WARMUP_MIN_OBS = 30   # per side, before the test is armed
    LLR_CLIP = 2.0               # nats per body: one odd crop cannot decide
    LEVEL_ALPHA = 0.002          # current state's level follows slow drift
    LEVEL_SIGMA_FLOOR = 0.01
    MIN_SEPARATION_SIGMA = 1.0   # the two states' levels never drift closer
    ADAPT_MAX_CUSUM = 0.5        # adapt / learn only while the test is quiet
    DOUBT_FRACTION = 0.5
    INSTANT_DOUBT_LLR = 1.0      # mean per-body LLR on ONE frame that withholds
    INSTANT_DOUBT_MIN_BODIES = 2 # labels at once (ids swapped across the net);
                                 # fires on 11 of 23 176 settled frames (20260920)
    # Per-tracklet evidence
    EMA_ALPHA = 0.1
    FAST_EMA_ALPHA = 0.5
    OCCLUDED_IOU = 0.15          # behind another body: crop is not this player
    MIXED_IOU = 0.3              # two same-side bodies this merged: both crops mixed
    HOLD_GAP_FRAMES = 30         # an id unseen this long may come back on anyone
    CLAIM_MIN_FRAMES = 5         # a fresh tracklet needs a few frames of evidence
    HYST_K = 0.5                 # hysteresis, in teammate-margin spreads (a swap
                                 # reverses a pair's margin to at most its own size,
                                 # so this must stay well under 1)
    SWAP_K = 2.0                 # quick-EMA swap override, same units: only very
                                 # clear reversals (1.0 fired on far-side noise:
                                 # 760 vs 51 label flips on the 20260920 replay)
    MARGIN_SIGMA_FLOOR = 0.01
    MARGIN_ALPHA = 0.01
    STRANGER_K = 4.0             # best similarity this many spreads below usual
    STRANGER_SIGMA_FLOOR = 0.05  # (overlaps and blur move it by ~0.1 legitimately)
    STRANGER_MIN_N = 50
    # Learning (within-side models only)
    LEARN_K = 0.75               # learn when the margin is a solid share of the usual one
    LEARN_MIN_FRAMES = 10
    LEARN_INTERVAL = 90
    LEARN_SETTLE_FRAMES = 150
    LEARN_MAX_IOU = 0.05
    # Housekeeping
    HISTORY_FRAMES = 900
    TID_STATE_TTL = 900

    def __init__(
        self,
        references: List[Dict[str, Any]],
        court_calibration=None,
        *,
        court_slack_px: float = 16.0,
        serve_zone_eligible: bool = True,
        switch_threshold: float = 8.0,
        switch_temper: float = 0.2,
        min_switch_interval_frames: int = 300,
    ):
        if len(references) != 4:
            raise ValueError("TeamIdentityResolver needs exactly 4 references")
        self.court = court_calibration
        self.court_slack_px = float(court_slack_px)
        self.serve_zone_eligible = bool(serve_zone_eligible)
        self.switch_threshold = float(switch_threshold)
        self.switch_temper = float(switch_temper)
        self.min_switch_interval_frames = int(min_switch_interval_frames)

        self.players: List[_PlayerModel] = []
        samples_by_player: List[List[Descriptor]] = []
        for ref in references:
            view = NEAR if int(ref["squad"]) == 1 else FAR
            model = _PlayerModel(
                label=ref["label"], squad=int(ref["squad"]), slot=ref["slot"],
                anchor_view=view,
            )
            samples = [d for d in (ref.get("identity_samples") or []) if d is not None]
            mean = mean_descriptor(samples)
            if mean is not None:
                model.anchors.append(mean)
            if samples:
                n_pick = min(self.N_ANCHOR_SAMPLES, len(samples))
                for k in np.linspace(0, len(samples) - 1, n_pick):
                    model.anchors.append(samples[int(round(k))])
            model.heights = [float(h) for h in (ref.get("identity_heights") or []) if h]
            self.players.append(model)
            samples_by_player.append(samples)
        self._squad_players = {
            q: [i for i, p in enumerate(self.players) if p.squad == q] for q in (1, 2)
        }
        if any(len(v) != 2 for v in self._squad_players.values()):
            raise ValueError("TeamIdentityResolver needs a 2+2 squad split")
        if not all(p.anchors for p in self.players):
            raise ValueError("TeamIdentityResolver needs identity samples for all 4 players")
        self._anchor_all = self._stack_all([p.anchors for p in self.players])
        self._model_all: Dict[str, Tuple[np.ndarray, np.ndarray, List[slice]]] = {}
        self._ref_h = [
            float(np.median(p.heights)) if len(p.heights) >= 3 else None for p in self.players
        ]
        self._init_margin_scale(samples_by_player)
        self.reset_state()

    @classmethod
    def from_references(cls, references, court_calibration=None, **kwargs):
        """Build from enrollment refs, or None when they lack identity
        samples (refs from an older enrollment / hand-built test refs)."""
        refs = list(references or [])
        if len(refs) != 4 or not all(r.get("identity_samples") for r in refs):
            return None
        try:
            return cls(refs, court_calibration, **kwargs)
        except ValueError as exc:
            logger.warning("Team identity resolver disabled: %s", exc)
            return None

    def _init_margin_scale(self, samples_by_player) -> None:
        """Teammate-margin and best-similarity spreads per view, seeded from
        the enrollment samples (each sample vs its own and its mate's model)
        and then tracked online. They scale hysteresis, learning and the
        stranger test to this video's own separability."""
        self._margin_level = {NEAR: _Level(), FAR: _Level()}
        self._best_level = {NEAR: _Level(), FAR: _Level()}
        for p, samples in enumerate(samples_by_player):
            if not samples:
                continue
            view = self.players[p].anchor_view
            mate = self._mate(p)
            parts, mask = stack_descriptors(samples)
            own = self._sims_from_stack(self._model_stack(p, view), parts, mask)
            other = self._sims_from_stack(self._model_stack(mate, view), parts, mask)
            for o, m in zip(own, other):
                self._margin_level[view].add(float(o - m) ** 2, self.MARGIN_ALPHA)
                self._best_level[view].add(float(max(o, m)), self.MARGIN_ALPHA)

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    def reset_state(self) -> None:
        self.near_squad = 1
        # Per state (squad near) and side: mean evidence; per side: spread.
        self._mu: Dict[int, Dict[str, Optional[float]]] = {
            1: {NEAR: None, FAR: None}, 2: {NEAR: None, FAR: None}}
        self._var: Dict[str, Optional[float]] = {NEAR: None, FAR: None}
        self._warm: Dict[str, List[float]] = {NEAR: [], FAR: []}
        self._cusum_value = 0.0
        self._onset: Optional[int] = None
        self.last_flip_frame = 0
        self.flips: List[Dict[str, Any]] = []
        self.doubt = False
        self.last_x: Dict[str, Optional[float]] = {NEAR: None, FAR: None}
        self._tids: Dict[int, _TidState] = {}
        self._labels: Dict[int, Tuple[str, int, str]] = {}
        self._history: Dict[int, Dict[int, Tuple[str, int, str]]] = {}
        self._history_order: Deque[int] = deque()
        self.last_observations: List[BodyObs] = []

    def set_court_calibration(self, court) -> None:
        self.court = court

    def squad_on(self, side: str) -> int:
        return self.near_squad if side == NEAR else 3 - self.near_squad

    def _mate(self, p: int) -> int:
        return next(q for q in self._squad_players[self.players[p].squad] if q != p)

    @property
    def cusum(self) -> float:
        """Accumulated (tempered, clipped) log-likelihood for the OTHER
        orientation; a switch is accepted at ``switch_threshold``."""
        return self._cusum_value

    @property
    def armed(self) -> bool:
        return self._var[NEAR] is not None

    def separability(self) -> Optional[Dict[str, float]]:
        """Per side, how many spreads apart the two orientations' evidence
        levels sit (d'). Around 1 or less, the teams look alike from that side
        and a switch cannot be read from appearance (the 20260920 match: ~3
        near, ~2 far)."""
        if not self.armed:
            return None
        return {
            v: round(abs(self._mu[1][v] - self._mu[2][v]) / float(np.sqrt(self._var[v])), 2)
            for v in VIEWS
        }

    def state(self) -> Dict[str, Any]:
        """Diagnostics for logs / probes / the live panel."""
        return {
            "near_squad": self.near_squad,
            "cusum": round(self.cusum, 2),
            "armed": self.armed,
            "separability": self.separability(),
            "x_near": None if self.last_x[NEAR] is None else round(self.last_x[NEAR], 4),
            "x_far": None if self.last_x[FAR] is None else round(self.last_x[FAR], 4),
            "doubt": self.doubt,
            "flips": list(self.flips),
            "learned": {p.label: {v: len(p.learned[v]) for v in VIEWS} for p in self.players},
        }

    def labels(self) -> Dict[int, Tuple[str, int, str]]:
        return dict(self._labels)

    def label_at(self, tid: Optional[int], frame_index: Optional[int] = None):
        """Label tuple for ``tid`` at ``frame_index`` (current when unknown)."""
        if tid is None:
            return None
        if frame_index is not None and frame_index in self._history:
            return self._history[frame_index].get(tid)
        return self._labels.get(tid)

    # ------------------------------------------------------------------ #
    # Similarities
    # ------------------------------------------------------------------ #

    @staticmethod
    def _stack_all(per_player: List[List[Descriptor]]):
        """All players' prototypes in one stack + each player's slice."""
        descs, slices, k = [], [], 0
        for protos in per_player:
            descs.extend(protos)
            slices.append(slice(k, k + len(protos)))
            k += len(protos)
        parts, mask = stack_descriptors(descs)
        return parts, mask, slices

    def _model_stack(self, p: int, view: str) -> Tuple[np.ndarray, np.ndarray]:
        """Anchors + the prototypes learned in ``view`` (the within-side model)."""
        model = self.players[p]
        return stack_descriptors(model.anchors + model.learned[view])

    @staticmethod
    def _sims_from_stack(stack, parts, mask) -> np.ndarray:
        return appearance_scores(stack[0], stack[1], parts, mask)

    @staticmethod
    def _per_player(stack, desc: Descriptor) -> np.ndarray:
        """Max similarity of ``desc`` to each player's slice of ``stack``."""
        parts, mask, slices = stack
        dots = np.einsum("kpb,pb->kp", parts, desc.parts)
        w = PART_WEIGHTS[None, :] * (mask & desc.mask[None, :])
        den = w.sum(axis=1)
        sims = np.where(den > 0, (dots * w).sum(axis=1) / np.maximum(den, 1e-9), 0.0)
        return np.array([float(sims[sl].max()) if sl.stop > sl.start else 0.0
                         for sl in slices])

    def _anchor_sims(self, desc: Descriptor) -> np.ndarray:
        """Appearance similarity to each player's FIXED anchors (orientation)."""
        return self._per_player(self._anchor_all, desc)

    def _model_sims(self, desc: Descriptor, view: str, height: Optional[float]) -> np.ndarray:
        """Similarity to each player's within-side model (+ height)."""
        if view not in self._model_all:
            self._model_all[view] = self._stack_all(
                [p.anchors + p.learned[view] for p in self.players])
        out = self._per_player(self._model_all[view], desc)
        if height is not None:
            for p in range(4):
                ref_h = self._ref_h[p]
                if ref_h is not None:
                    s_h = float(np.exp(-0.5 * ((height - ref_h) / self.HEIGHT_SIGMA_M) ** 2))
                    out[p] = (1.0 - self.HEIGHT_WEIGHT) * out[p] + self.HEIGHT_WEIGHT * s_h
        return out

    # ------------------------------------------------------------------ #
    # Measurement
    # ------------------------------------------------------------------ #

    def _side(self, bbox) -> Optional[str]:
        court = self.court
        if court is None or not hasattr(court, "get_team_for_bbox"):
            return None
        team = court.get_team_for_bbox([int(v) for v in bbox])
        if team == "A":
            return NEAR
        if team == "B":
            return FAR
        return None

    def _eligibility(self, bbox) -> Tuple[bool, bool]:
        """(eligible, in_court). Eligible = foot in court (+ slack for players
        on the line) or in a serve zone (the server); only in-court bodies
        are learned from."""
        court = self.court
        if court is None or not getattr(court, "is_calibrated", False):
            return True, True
        foot = court.foot_point(bbox)
        point = (float(foot[0]), float(foot[1]))
        if court.is_point_in_court(point):
            return True, True
        dist_fn = getattr(court, "distance_to_court_px", None)
        if self.court_slack_px > 0 and dist_fn is not None:
            dist = dist_fn(point)
            if dist is not None and dist <= self.court_slack_px:
                return True, True
        if self.serve_zone_eligible and hasattr(court, "is_in_serve_zone"):
            if court.is_in_serve_zone(point):
                return True, False
        return False, False

    def measure(self, frame: Optional[np.ndarray], players: List[Dict[str, Any]]) -> List[BodyObs]:
        """Everything the decision needs from a frame, per tracked player."""
        obs: List[BodyObs] = []
        for p_dict in players:
            tid = p_dict.get("track_id")
            bbox = p_dict.get("bbox")
            if tid is None or not bbox:
                continue
            box = [float(v) for v in bbox]
            o = BodyObs(tid=tid, bbox=box, side=self._side(box),
                        predicted=bool(p_dict.get("predicted")))
            if not o.predicted:
                o.eligible, o.in_court = self._eligibility(box)
                if o.eligible and o.side is not None:
                    o.desc = compute_descriptor(frame, box)
                    o.height = lateral_height_m(self.court, box)
            obs.append(o)
        return obs

    # ------------------------------------------------------------------ #
    # Per-frame decision
    # ------------------------------------------------------------------ #

    def update(
        self, frame_index: int, frame: Optional[np.ndarray], players: List[Dict[str, Any]]
    ) -> Dict[int, Tuple[str, int, str]]:
        """Measure this frame's tracked players and resolve their labels."""
        return self.update_observed(frame_index, self.measure(frame, players))

    def update_observed(
        self, frame_index: int, observations: List[BodyObs]
    ) -> Dict[int, Tuple[str, int, str]]:
        """Resolve labels from measured observations; returns tid -> label."""
        self.last_observations = observations
        bodies = self._track_states(frame_index, observations)
        self._update_orientation(frame_index, bodies)

        taken: Dict[int, int] = {}  # player index -> tid
        if not self.doubt:
            for side in VIEWS:
                taken.update(self._assign_side(side, [b for b in bodies if b["side"] == side]))
            self._maybe_learn(frame_index, bodies, taken, observations)

        labels: Dict[int, Tuple[str, int, str]] = {}
        for p, tid in taken.items():
            m = self.players[p]
            labels[tid] = (m.label, m.squad, m.slot)
        # Tracks not evaluated this frame (coasting, or off court) keep their
        # label while nobody else claims it and they are on that squad's side.
        evaluated = {b["tid"] for b in bodies}
        for o in observations:
            st = self._tids.get(o.tid)
            if st is None or o.tid in evaluated or st.hold is None:
                continue
            if st.hold in taken:
                st.hold = None
                continue
            if o.side is not None and self.squad_on(o.side) != self.players[st.hold].squad:
                st.hold = None
                continue
            if not self.doubt:
                m = self.players[st.hold]
                labels[o.tid] = (m.label, m.squad, m.slot)

        self._labels = labels
        self._history[frame_index] = labels
        self._history_order.append(frame_index)
        while len(self._history_order) > self.HISTORY_FRAMES:
            self._history.pop(self._history_order.popleft(), None)
        stale = [t for t, s in self._tids.items() if frame_index - s.last_frame > self.TID_STATE_TTL]
        for tid in stale:
            self._tids.pop(tid)
        return labels

    def _track_states(self, frame_index: int, observations: List[BodyObs]) -> List[Dict[str, Any]]:
        """Per-id evidence for every measured, eligible body.

        A crop behind another body (occluded) or merged with a same-side body
        (mixed) shows two people: it neither updates the evidence nor, when
        mixed, gets a label -- the hold is kept until the boxes separate.
        """
        bodies: List[Dict[str, Any]] = []
        real = [o for o in observations if not o.predicted]
        for o in observations:
            if o.desc is None or o.side is None or not o.eligible:
                continue
            occluded = mixed = False
            for other in real:
                if other.tid == o.tid:
                    continue
                iou = self._iou(o.bbox, other.bbox)
                if iou > self.MIXED_IOU and other.side == o.side:
                    mixed = True
                if iou > self.OCCLUDED_IOU and other.bbox[3] > o.bbox[3]:
                    occluded = True
            x1, y1, x2, y2 = o.bbox
            center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
            width = max(1.0, x2 - x1)
            st = self._tids.get(o.tid)
            if st is None:
                st = _TidState(center=center, width=width, last_frame=frame_index, side=o.side)
                self._tids[o.tid] = st
                reset = True
            else:
                gap = max(1, frame_index - st.last_frame)
                dist = float(np.hypot(center[0] - st.center[0], center[1] - st.center[1]))
                # The id now rides another body (a tracker swap), crossed the
                # net, or was away long enough to come back on anyone (gallery
                # re-acquisition): its accumulated evidence and label are void.
                reset = (
                    gap > self.HOLD_GAP_FRAMES
                    or dist > max(60.0, st.width) + 12.0 * (gap - 1)
                    or st.side != o.side
                )
            if reset:
                st.ema, st.fast, st.n, st.hold = None, None, 0, None
                st.heights.clear()
            st.center, st.width, st.last_frame, st.side = center, width, frame_index, o.side
            if o.height is not None:
                st.heights.append(o.height)
            height = float(np.median(st.heights)) if st.heights else None
            clean = not (occluded or mixed)
            if clean or st.ema is None:
                sims = self._model_sims(o.desc, o.side, height)
                st.ema = sims.copy() if st.ema is None else (
                    (1.0 - self.EMA_ALPHA) * st.ema + self.EMA_ALPHA * sims)
                st.fast = sims.copy() if st.fast is None else (
                    (1.0 - self.FAST_EMA_ALPHA) * st.fast + self.FAST_EMA_ALPHA * sims)
                st.n += 1
            body = {
                "tid": o.tid, "bbox": o.bbox, "side": o.side, "in_court": o.in_court,
                "desc": o.desc, "height": height, "state": st, "mixed": mixed,
                "clean": clean, "x": None,
            }
            if clean:
                anchor = self._anchor_sims(o.desc)
                q1, q2 = self._squad_players[1], self._squad_players[2]
                body["x"] = float(anchor[q1].max() - anchor[q2].max())
            bodies.append(body)
        return bodies

    # --- orientation ------------------------------------------------------ #

    def _update_orientation(self, frame_index: int, bodies) -> None:
        """Two-state test on per-body evidence for "squad 1 is near".

        Each clean in-court body gives ``e = x`` on the near side and
        ``e = -x`` on the far side (``x`` = best squad-1 minus best squad-2
        anchor similarity). Per side, ``e`` has one level when squad 1 is near
        and another when squad 2 is: the current state's levels are measured
        in the opening (the enrolled orientation) and then follow slow drift;
        the unseen state starts MIRRORED (the only prior: no view bias) and is
        replaced by its measured level once it has held. Each body adds its
        log-likelihood ratio for the other state (clipped, tempered), a CUSUM
        accumulates it, and the orientation flips at ``switch_threshold``.
        A whole team moves at a switch, so the evidence comes from all four
        bodies at once; one occluded or mis-sided body is capped.
        """
        obs = [(b["side"], b["x"] if b["side"] == NEAR else -b["x"])
               for b in bodies if b["x"] is not None and b["in_court"]]
        self.last_x = {
            side: (float(np.mean([b["x"] for b in bodies if b["side"] == side
                                  and b["x"] is not None])) if any(
                b["side"] == side and b["x"] is not None for b in bodies) else None)
            for side in VIEWS
        }
        if not self.armed:
            for side, e in obs:
                self._warm[side].append(e)
            if (frame_index >= self.ORIENT_WARMUP_FRAMES
                    and all(len(self._warm[v]) >= self.ORIENT_WARMUP_MIN_OBS for v in VIEWS)):
                for v in VIEWS:
                    mu = float(np.mean(self._warm[v]))
                    self._mu[1][v], self._mu[2][v] = mu, -mu
                    self._var[v] = max(float(np.var(self._warm[v])),
                                       self.LEVEL_SIGMA_FLOOR ** 2)
                self._warm = {NEAR: [], FAR: []}
            self.doubt = False
            return

        cur, other = self.near_squad, 3 - self.near_squad
        llr = 0.0
        for side, e in obs:
            var = self._var[side]
            d = ((e - self._mu[cur][side]) ** 2 - (e - self._mu[other][side]) ** 2) / (2.0 * var)
            llr += float(np.clip(d, -self.LLR_CLIP, self.LLR_CLIP))
        instant = (len(obs) >= self.INSTANT_DOUBT_MIN_BODIES
                   and llr / len(obs) >= self.INSTANT_DOUBT_LLR)
        before = self._cusum_value
        self._cusum_value = max(0.0, before + self.switch_temper * llr)
        if self._cusum_value == 0.0:
            self._onset = None
        elif before == 0.0:
            self._onset = frame_index
        if self._cusum_value >= self.switch_threshold:
            if frame_index - self.last_flip_frame >= self.min_switch_interval_frames:
                self._flip(frame_index)
                instant = False   # this frame's evidence was FOR the new state
            else:
                self._cusum_value = self.switch_threshold
        elif self._cusum_value <= self.ADAPT_MAX_CUSUM:
            self._adapt_levels(obs)
        self.doubt = instant or (
            self._cusum_value >= self.DOUBT_FRACTION * self.switch_threshold)

    def _adapt_levels(self, obs) -> None:
        """Follow slow drift of the current state's levels (light, kit, pose
        mix), never closer to the other state's than MIN_SEPARATION_SIGMA."""
        cur, other = self.near_squad, 3 - self.near_squad
        a = self.LEVEL_ALPHA
        sign = 1.0 if cur == 1 else -1.0   # squad 1 near -> the HIGHER level
        for side, e in obs:
            mu = self._mu[cur][side] + a * (e - self._mu[cur][side])
            self._var[side] = max(
                (1.0 - a) * self._var[side] + a * (e - mu) ** 2, self.LEVEL_SIGMA_FLOOR ** 2)
            gap = self.MIN_SEPARATION_SIGMA * float(np.sqrt(self._var[side]))
            if sign * (mu - self._mu[other][side]) < gap:
                mu = self._mu[other][side] + sign * gap
            self._mu[cur][side] = mu

    def _flip(self, frame_index: int) -> None:
        new = 3 - self.near_squad
        self.near_squad = new
        onset = self._onset if self._onset is not None else frame_index
        event = {"frame": frame_index, "onset": onset, "near_squad": new}
        self.flips.append(event)
        logger.info(
            "Identity: side switch detected at frame %d (onset %d) -- squad %d now near",
            frame_index, onset, new,
        )
        self._cusum_value = 0.0
        self._onset = None
        self.last_flip_frame = frame_index
        for st in self._tids.values():
            st.hold = None

    # --- who is who within a side ------------------------------------------ #

    def _margin_sigma(self, view: str) -> float:
        """RMS teammate margin in ``view`` (the level tracks squared margins)."""
        return float(np.sqrt(max(self._margin_level[view].mu, self.MARGIN_SIGMA_FLOOR ** 2)))

    def _is_stranger(self, best: float, view: str) -> bool:
        level = self._best_level[view]
        if level.n < self.STRANGER_MIN_N:
            return False
        return best < level.mu - self.STRANGER_K * level.sigma(self.STRANGER_SIGMA_FLOOR)

    def _assign_side(self, side: str, side_bodies) -> Dict[int, int]:
        """Which of the side's bodies is which teammate; player index -> tid.

        A body merged with its teammate's box (``mixed``) keeps its hold but
        is not labeled, and its player is reserved. The others: tracklets
        with CLAIM_MIN_FRAMES of evidence or a held label, at most as many as
        free players (the ones that look most like the squad), strangers
        dropped. They take the better assignment of the free players, leaving
        the held one only when the slow evidence beats it by HYST_K
        teammate-margin spreads per body, or one clean body's quick evidence
        by SWAP_K (an id that silently moved to the other body).
        """
        cols = self._squad_players[self.squad_on(side)]
        hyst = self.HYST_K * self._margin_sigma(side)
        swap = self.SWAP_K * self._margin_sigma(side)
        reserved = set()
        for b in side_bodies:
            if b["mixed"]:
                if b["state"].hold in cols:
                    reserved.add(b["state"].hold)
                else:
                    b["state"].hold = None
        free = [c for c in range(2) if cols[c] not in reserved]
        bodies = [b for b in side_bodies if not b["mixed"]]
        cands = [
            b for b in bodies
            if b["state"].n >= self.CLAIM_MIN_FRAMES or b["state"].hold in cols
        ]
        cands.sort(key=lambda b: -float(b["state"].ema[cols].max()))
        kept = []
        for b in cands:
            best = float(b["state"].ema[cols].max())
            self._best_level[side].add(best, self.MARGIN_ALPHA)
            # A stranger by the slow AND the quick evidence (right after a
            # swap the slow memory is mixed and reads low on its own).
            quick = float(b["state"].fast[cols].max())
            if len(kept) < len(free) and not self._is_stranger(max(best, quick), side):
                kept.append(b)
        for b in bodies:
            if b not in kept:
                b["state"].hold = None
        if not kept:
            return {}

        def total(perm, key):
            return sum(float(getattr(b["state"], key)[cols[c]]) for b, c in zip(kept, perm))

        perms = [(free[0], free[1]), (free[1], free[0])] if len(kept) == 2 else [(c,) for c in free]
        held = [
            perm for perm in perms
            if all(b["state"].hold in (None, cols[c]) for b, c in zip(kept, perm))
            and any(b["state"].hold == cols[c] for b, c in zip(kept, perm))
        ]
        n = len(kept)
        base = held[0] if held else max(perms, key=lambda perm: total(perm, "ema"))
        choice = base
        if len(perms) == 2:
            other = next(perm for perm in perms if perm != base)
            # Quick override, judged per CLEAN body (an occluded partner's
            # evidence is frozen; with two bodies, one clear verdict decides
            # both by elimination).
            turned = any(
                float(b["state"].fast[cols[co]] - b["state"].fast[cols[cb]]) > swap
                for b, cb, co in zip(kept, base, other) if b["clean"]
            )
            if turned:
                # The quick evidence has clearly turned: an id silently moved
                # to the other body. Its slow memory belongs to the old body.
                choice = other
                for b in kept:
                    b["state"].ema = b["state"].fast.copy()
            elif held and total(other, "ema") - total(base, "ema") > hyst * n:
                choice = other
            runner_up = next(perm for perm in perms if perm != choice)
            pair_margin = (total(choice, "ema") - total(runner_up, "ema")) / n
        else:
            pair_margin = None   # one free player: nothing to compare against
        out: Dict[int, int] = {}
        for b, c in zip(kept, choice):
            p = cols[c]
            out[p] = b["tid"]
            b["state"].hold = p
            b["pair_margin"] = pair_margin
            m = float(b["state"].ema[p] - b["state"].ema[cols[1 - c]])
            self._margin_level[side].add(m * m, self.MARGIN_ALPHA)
        side_tids = {b["tid"] for b in side_bodies}
        for tid, st in self._tids.items():
            if tid not in side_tids and st.hold in out:
                st.hold = None
        return out

    # --- learning (within-side models only) ----------------------------- #

    def _maybe_learn(self, frame_index, bodies, taken, observations) -> None:
        """Add prototypes from confidently identified, isolated, in-court
        bodies: how each player acquires the view it was not enrolled in.
        Only while the orientation is settled; the orientation statistic
        never reads these prototypes."""
        if not self.armed or self._cusum_value > self.ADAPT_MAX_CUSUM:
            return
        if frame_index - self.last_flip_frame < self.LEARN_SETTLE_FRAMES and self.flips:
            return
        tid_to_player = {tid: p for p, tid in taken.items()}
        for b in bodies:
            p = tid_to_player.get(b["tid"])
            if p is None or not b["in_court"] or b.get("pair_margin") is None:
                continue
            st = b["state"]
            view = b["side"]
            model = self.players[p]
            if st.n < self.LEARN_MIN_FRAMES:
                continue
            if frame_index - model.last_learn[view] < self.LEARN_INTERVAL:
                continue
            if b["pair_margin"] < self.LEARN_K * self._margin_sigma(view):
                continue
            if any(
                self._iou(b["bbox"], o.bbox) > self.LEARN_MAX_IOU
                for o in observations if o.tid != b["tid"]
            ):
                continue
            learned = model.learned[view]
            if len(learned) < self.MAX_LEARNED:
                learned.append(b["desc"])
            else:
                parts, mask = stack_descriptors(learned)
                dparts, dmask = stack_descriptors([b["desc"]])
                sims = [float(appearance_scores(parts[k:k + 1], mask[k:k + 1], dparts, dmask)[0])
                        for k in range(len(learned))]
                learned[int(np.argmax(sims))] = b["desc"]   # keep the set diverse
            self._model_all.pop(view, None)
            model.last_learn[view] = frame_index
            logger.debug("Identity: learned %s %s prototype at frame %d",
                         model.label, view, frame_index)

    @staticmethod
    def _iou(a, b) -> float:
        x1, y1 = max(a[0], b[0]), max(a[1], b[1])
        x2, y2 = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        if inter <= 0:
            return 0.0
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        return inter / max(1e-9, area_a + area_b - inter)
