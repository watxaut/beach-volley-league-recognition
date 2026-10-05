"""Team-structured identity resolver: P1A/P2A/P1B/P2B across side switches.

Display/attribution-only pure observer over the tracker's per-frame output
(the GT-validated tracker never reads it). It re-derives, every frame, which
enrolled player each tracked body is, and is built around the one structural
fact that survives every venue, camera height and kit: **during play the two
players of a team are on the same side of the net, opposite the other team.**
That splits identity into three small decisions instead of one 4-way guess:

1. **Orientation** -- which squad is on the NEAR side. Piecewise constant: it
   only changes at a side switch (minutes apart). Decided by a one-sided CUSUM
   change-point test over the whole frame's evidence (both players of both
   sides, every frame), with a minimum dwell between flips. A single bad frame
   or an occluded player cannot flip it; a real switch flips it within ~1-3 s
   of the players settling on their new sides.
2. **Near slot / far slot** -- which of the side's two bodies is which
   teammate, by per-tracklet appearance evidence (EMA, reset when the tracker
   id jumps to another body) with a hysteresis bonus for the current holder
   and "by elimination" when the partner is clear.

**View bias, and why scores are standardised.** The camera sees the near
pair large and from behind, the far pair small and from the front. Enrollment
watches squad 1 only near and squad 2 only far, so at the FIRST switch the
comparisons that matter are cross-view, and raw similarities are biased toward
"nothing changed". Every similarity is therefore turned into two standardised
scores, both calibrated on this video's own enrollment samples (no constant
here is tuned on one clip, venue or kit):

* DISCRIMINATION ``z``: against the impostor distribution -- every OTHER
  player's samples (both views) scored against this player's model, as in
  speaker-verification Z-norm. Cross-view impostors exist from frame 0.
* FIT ``f``: against this player's OWN samples in the same view. Same-view, so
  free of view bias: at a side switch the near pair's fit collapses on both
  sides of the net at once, which is what makes the first switch detectable
  even when cross-view similarity is weak.

**Second view.** After a confident orientation (no doubt, settled since the
last flip), bodies that are clearly assigned and isolated add prototypes to
their player's model for the view they are seen in. The enrollment anchors are
never replaced, so the model cannot drift away from the person it started as.

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
class _PlayerModel:
    label: str
    squad: int
    slot: str
    anchor_view: str
    protos: Dict[str, List[Descriptor]] = field(default_factory=lambda: {NEAR: [], FAR: []})
    n_anchor: Dict[str, int] = field(default_factory=lambda: {NEAR: 0, FAR: 0})
    heights: Dict[str, Deque[float]] = field(
        default_factory=lambda: {NEAR: deque(maxlen=200), FAR: deque(maxlen=200)}
    )
    last_learn: Dict[str, int] = field(default_factory=lambda: {NEAR: -10**9, FAR: -10**9})


@dataclass
class _PoolEntry:
    desc: Descriptor
    height: Optional[float]


@dataclass
class _Stats:
    imp_mu: float
    imp_sd: float
    gen_mu: Optional[float] = None
    gen_sd: Optional[float] = None


@dataclass
class _TidState:
    center: Tuple[float, float]
    width: float
    last_frame: int
    side: Optional[str]
    ema: Optional[np.ndarray] = None
    fast: Optional[np.ndarray] = None  # quick EMA: breaks a hold on a silent swap
    n: int = 0
    heights: Deque[float] = field(default_factory=lambda: deque(maxlen=15))
    hold: Optional[int] = None  # player index held by this track id


def _other(view: str) -> str:
    return FAR if view == NEAR else NEAR


class TeamIdentityResolver:
    """Per-frame P1A/P2A/P1B/P2B labels that survive side switches.

    Evidence that body ``b`` (seen in view ``v``) is player ``p`` is
    ``e = z + f``, both from one similarity ``s`` (appearance + height):

    * ``z`` -- DISCRIMINATION: ``s`` standardised against the impostor
      distribution, i.e. every OTHER player's samples (both views) scored
      against ``p``'s model for ``v``. "More like p than the others are."
    * ``f`` -- FIT: ``s`` standardised against ``p``'s OWN samples in ``v``
      (only when ``p`` has a native model for ``v``; 0 otherwise), capped at
      +1. "As typical for p as p usually is." A same-view comparison, so it is
      free of the near/far view bias: when the near pair is replaced at a side
      switch, the near pair's fit collapses on both sides even before any
      cross-view comparison is trusted.
    """

    # Similarity / normalisation
    HEIGHT_WEIGHT = 0.25
    HEIGHT_SIGMA_M = 0.15
    Z_CAP = 6.0
    FIT_CAP = 1.0
    SIGMA_FLOOR = 0.04
    MIN_IMPOSTORS = 5
    MIN_GENUINE = 8
    FALLBACK_MU, FALLBACK_SIGMA = 0.3, 0.15
    POOL_PER_PLAYER_VIEW = 80
    N_ANCHOR_SAMPLES = 4
    MAX_PROTOS = 12
    MIN_NATIVE_PROTOS = 3
    # Per-tracklet evidence
    EMA_ALPHA = 0.1
    FAST_EMA_ALPHA = 0.5
    HOLD_BONUS = 1.0
    HOLD_FLOOR = -1.0
    HOLD_GAP_FRAMES = 30       # an id unseen this long may come back on anyone
    CLAIM_MIN_FRAMES = 5       # a fresh tracklet needs a few frames of evidence
    # Orientation change-point detector
    D_CLIP = 4.0
    DOUBT_FRACTION = 0.25
    INSTANT_DOUBT_D = 3.0      # one frame this strongly for the swap = blank now
    INSTANT_DOUBT_MIN_BODIES = 2
    # Learning
    LEARN_MIN_EVIDENCE = 1.5
    LEARN_MIN_FRAMES = 10
    LEARN_INTERVAL = 90
    LEARN_SETTLE_FRAMES = 60
    LEARN_MAX_IOU = 0.05
    LEARN_MAX_CUSUM_FRACTION = 0.1
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
        switch_threshold: float = 40.0,
        switch_drift: float = 0.5,
        min_switch_interval_frames: int = 900,
        claim_evidence: float = 1.0,
        learn_margin: float = 2.0,
    ):
        if len(references) != 4:
            raise ValueError("TeamIdentityResolver needs exactly 4 references")
        self.court = court_calibration
        self.court_slack_px = float(court_slack_px)
        self.serve_zone_eligible = bool(serve_zone_eligible)
        self.switch_threshold = float(switch_threshold)
        self.switch_drift = float(switch_drift)
        self.min_switch_interval_frames = int(min_switch_interval_frames)
        self.claim_evidence = float(claim_evidence)
        self.learn_margin = float(learn_margin)

        self.players: List[_PlayerModel] = []
        self._pool: Dict[Tuple[int, str], Deque[_PoolEntry]] = {
            (i, v): deque(maxlen=self.POOL_PER_PLAYER_VIEW) for i in range(4) for v in VIEWS
        }
        for i, ref in enumerate(references):
            view = NEAR if int(ref["squad"]) == 1 else FAR
            model = _PlayerModel(
                label=ref["label"], squad=int(ref["squad"]), slot=ref["slot"],
                anchor_view=view,
            )
            samples = [s for s in (ref.get("identity_samples") or []) if s is not None]
            heights = list(ref.get("identity_heights") or [])
            if len(heights) != len(samples):
                heights = [None] * len(samples)
            anchors: List[Descriptor] = []
            mean = mean_descriptor(samples)
            if mean is not None:
                anchors.append(mean)
            if samples:
                n_pick = min(self.N_ANCHOR_SAMPLES, len(samples))
                for k in np.linspace(0, len(samples) - 1, n_pick):
                    anchors.append(samples[int(round(k))])
            model.protos[view] = anchors
            model.n_anchor[view] = len(anchors)
            model.heights[view].extend(h for h in heights if h)
            self.players.append(model)
            for desc, h in zip(samples, heights):
                self._pool[(i, view)].append(_PoolEntry(desc, h))
        self._squad_players = {
            q: [i for i, p in enumerate(self.players) if p.squad == q] for q in (1, 2)
        }
        if any(len(v) != 2 for v in self._squad_players.values()):
            raise ValueError("TeamIdentityResolver needs a 2+2 squad split")

        self._proto_cache: Dict[Tuple[int, str], Tuple[List[Descriptor], np.ndarray, np.ndarray]] = {}
        self._height_cache: Dict[Tuple[int, str], Optional[float]] = {}
        self._stats: Dict[Tuple[int, str], _Stats] = {}
        self._dirty = {(i, v) for i in range(4) for v in VIEWS}
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

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    def reset_state(self) -> None:
        self.near_squad = 1
        self.cusum = 0.0
        self._onset: Optional[int] = None
        self.last_flip_frame = 0
        self.flips: List[Dict[str, Any]] = []
        self.doubt = False
        self.last_evidence: Optional[float] = None
        self._tids: Dict[int, _TidState] = {}
        self._labels: Dict[int, Tuple[str, int, str]] = {}
        self._history: Dict[int, Dict[int, Tuple[str, int, str]]] = {}
        self._history_order: Deque[int] = deque()

    def set_court_calibration(self, court) -> None:
        self.court = court

    def squad_on(self, side: str) -> int:
        return self.near_squad if side == NEAR else 3 - self.near_squad

    def state(self) -> Dict[str, Any]:
        """Diagnostics for logs / probes / the live panel."""
        return {
            "near_squad": self.near_squad,
            "cusum": round(self.cusum, 2),
            "evidence": None if self.last_evidence is None else round(self.last_evidence, 2),
            "doubt": self.doubt,
            "flips": list(self.flips),
            "learned": {
                p.label: {v: len(p.protos[v]) - p.n_anchor[v] for v in VIEWS}
                for p in self.players
            },
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
    # Scoring
    # ------------------------------------------------------------------ #

    def _protos_for(self, p: int, view: str):
        """(descriptor list, stacked parts, stacked mask) used for ``view``:
        the native prototypes once there are enough, else native + the other
        view's (cross-view)."""
        cached = self._proto_cache.get((p, view))
        if cached is not None:
            return cached
        model = self.players[p]
        native = model.protos[view]
        descs = list(native)
        if len(native) < self.MIN_NATIVE_PROTOS:
            descs += model.protos[_other(view)]
        parts, mask = stack_descriptors(descs)
        self._proto_cache[(p, view)] = (descs, parts, mask)
        return self._proto_cache[(p, view)]

    def _is_native(self, p: int, view: str) -> bool:
        return len(self.players[p].protos[view]) >= self.MIN_NATIVE_PROTOS

    def _ref_height(self, p: int, view: str) -> Optional[float]:
        if (p, view) in self._height_cache:
            return self._height_cache[(p, view)]
        model = self.players[p]
        ref = None
        for v in (view, _other(view)):
            if len(model.heights[v]) >= 3:
                ref = float(np.median(model.heights[v]))
                break
        self._height_cache[(p, view)] = ref
        return ref

    def _similarities(
        self, p: int, view: str, entries: Sequence[_PoolEntry], leave_out: bool = False,
    ) -> np.ndarray:
        """Similarity of each entry to player ``p``'s model for ``view``.

        ``leave_out`` drops, per entry, the prototype that IS that entry (a
        player's own samples are also its anchors), so genuine statistics are
        not inflated by self-matches.
        """
        descs, pp, pm = self._protos_for(p, view)
        if not entries or pp.shape[0] == 0:
            return np.zeros(len(entries))
        parts, mask = stack_descriptors([e.desc for e in entries])
        dots = np.einsum("kpb,npb->knp", pp, parts)
        valid = pm[:, None, :] & mask[None, :, :]
        w = PART_WEIGHTS[None, None, :] * valid
        denom = w.sum(axis=2)
        sims = np.where(denom > 0, (dots * w).sum(axis=2) / np.maximum(denom, 1e-9), 0.0)
        if leave_out:
            proto_ids = np.array([id(d) for d in descs])
            entry_ids = np.array([id(e.desc) for e in entries])
            sims = np.where(proto_ids[:, None] == entry_ids[None, :], -np.inf, sims)
        app = sims.max(axis=0)
        app = np.where(np.isfinite(app), app, 0.0)
        ref_h = self._ref_height(p, view)
        if ref_h is None:
            return app
        out = app.copy()
        for n, e in enumerate(entries):
            if e.height is None:
                continue
            s_h = float(np.exp(-0.5 * ((e.height - ref_h) / self.HEIGHT_SIGMA_M) ** 2))
            out[n] = (1.0 - self.HEIGHT_WEIGHT) * app[n] + self.HEIGHT_WEIGHT * s_h
        return out

    def _refresh_stats(self) -> None:
        """Re-standardise after the models or pools changed (enrollment, or
        a learning event -- at most one per player and view per
        LEARN_INTERVAL). Immediately: scores and their statistics must come
        from the same prototype set."""
        for p, view in sorted(self._dirty):
            imps = [
                e for (q, _v), dq in self._pool.items() if q != p for e in dq
            ]
            if len(imps) >= self.MIN_IMPOSTORS:
                s = self._similarities(p, view, imps)
                st = _Stats(float(s.mean()), max(float(s.std()), self.SIGMA_FLOOR))
            else:
                st = _Stats(self.FALLBACK_MU, self.FALLBACK_SIGMA)
            gen = list(self._pool[(p, view)])
            if self._is_native(p, view) and len(gen) >= self.MIN_GENUINE:
                g = self._similarities(p, view, gen, leave_out=True)
                st.gen_mu = float(g.mean())
                st.gen_sd = max(float(g.std()), self.SIGMA_FLOOR)
            self._stats[(p, view)] = st
        self._dirty.clear()

    def evidence(self, desc: Descriptor, view: str, height: Optional[float]) -> np.ndarray:
        """``e = z + f`` for each of the 4 players (see class docstring)."""
        entry = [_PoolEntry(desc, height)]
        out = np.zeros(4)
        for p in range(4):
            s = float(self._similarities(p, view, entry)[0])
            st = self._stats[(p, view)]
            z = float(np.clip((s - st.imp_mu) / st.imp_sd, -self.Z_CAP, self.Z_CAP))
            f = 0.0
            if st.gen_mu is not None:
                f = float(np.clip((s - st.gen_mu) / st.gen_sd, -self.Z_CAP, self.FIT_CAP))
            out[p] = z + f
        return out

    # ------------------------------------------------------------------ #
    # Geometry
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

    # ------------------------------------------------------------------ #
    # Per-frame update
    # ------------------------------------------------------------------ #

    def update(
        self, frame_index: int, frame: Optional[np.ndarray], players: List[Dict[str, Any]]
    ) -> Dict[int, Tuple[str, int, str]]:
        """Resolve labels for this frame's tracked players; returns tid->label."""
        if self._dirty:
            self._refresh_stats()

        bodies = self._observe(frame_index, frame, players)
        self._update_orientation(frame_index, bodies)

        taken: Dict[int, int] = {}  # player index -> tid
        if not self.doubt:
            for side in VIEWS:
                taken.update(
                    self._assign_side(side, [b for b in bodies if b["side"] == side])
                )
            self._maybe_learn(frame_index, bodies, taken, players)

        labels: Dict[int, Tuple[str, int, str]] = {}
        for p, tid in taken.items():
            m = self.players[p]
            labels[tid] = (m.label, m.squad, m.slot)
        # Tracks not evaluated this frame (coasting, or off court -- e.g. the
        # server behind the baseline) keep their label while nobody else
        # claims it and they are still on that squad's side of the net.
        evaluated = {b["tid"] for b in bodies}
        for p_dict in players:
            tid = p_dict.get("track_id")
            st = self._tids.get(tid) if tid is not None else None
            if st is None or tid in evaluated or st.hold is None:
                continue
            if st.hold in taken:
                st.hold = None
                continue
            bbox = p_dict.get("bbox")
            side = self._side(bbox) if bbox else None
            if side is not None and self.squad_on(side) != self.players[st.hold].squad:
                st.hold = None
                continue
            if not self.doubt:
                m = self.players[st.hold]
                labels[tid] = (m.label, m.squad, m.slot)

        self._labels = labels
        self._history[frame_index] = labels
        self._history_order.append(frame_index)
        while len(self._history_order) > self.HISTORY_FRAMES:
            self._history.pop(self._history_order.popleft(), None)
        stale = [t for t, s in self._tids.items() if frame_index - s.last_frame > self.TID_STATE_TTL]
        for tid in stale:
            self._tids.pop(tid)
        return labels

    def _observe(self, frame_index, frame, players) -> List[Dict[str, Any]]:
        """Evidence for every real, eligible body; maintains per-id state."""
        bodies: List[Dict[str, Any]] = []
        for p_dict in players:
            tid = p_dict.get("track_id")
            bbox = p_dict.get("bbox")
            if tid is None or not bbox or p_dict.get("predicted"):
                continue
            eligible, in_court = self._eligibility(bbox)
            if not eligible:
                continue
            side = self._side(bbox)
            if side is None:
                continue
            desc = compute_descriptor(frame, bbox)
            if desc is None:
                continue
            x1, y1, x2, y2 = (float(v) for v in bbox)
            center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
            width = max(1.0, x2 - x1)
            st = self._tids.get(tid)
            if st is None:
                st = _TidState(center=center, width=width, last_frame=frame_index, side=side)
                self._tids[tid] = st
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
                    or st.side != side
                )
            if reset:
                st.ema, st.fast, st.n, st.hold = None, None, 0, None
                st.heights.clear()
            st.center, st.width, st.last_frame, st.side = center, width, frame_index, side
            h = lateral_height_m(self.court, bbox)
            if h is not None:
                st.heights.append(h)
            height = float(np.median(st.heights)) if st.heights else None
            e = self.evidence(desc, side, height)
            st.ema = e.copy() if st.ema is None else (
                (1.0 - self.EMA_ALPHA) * st.ema + self.EMA_ALPHA * e
            )
            st.fast = e.copy() if st.fast is None else (
                (1.0 - self.FAST_EMA_ALPHA) * st.fast + self.FAST_EMA_ALPHA * e
            )
            st.n += 1
            bodies.append({
                "tid": tid, "bbox": [x1, y1, x2, y2], "side": side,
                "in_court": in_court, "desc": desc, "height": height,
                "e": e, "state": st, "pair_margin": None,
            })
        return bodies

    def _side_total(self, side_bodies, squad: int) -> Tuple[float, int]:
        """Best assignment total of a side's bodies to a squad's 2 players."""
        if not side_bodies:
            return 0.0, 0
        cols = self._squad_players[squad]
        m = np.array([[b["e"][p] for p in cols] for b in side_bodies])
        rows, cs = linear_sum_assignment(-m)
        return float(m[rows, cs].sum()), len(rows)

    def _update_orientation(self, frame_index: int, bodies) -> None:
        """One-sided CUSUM on the per-body advantage of the swapped
        orientation; flips only past the threshold and the minimum dwell.
        Doubt (labels withheld) starts at a fraction of the threshold, or at
        once on a single frame where the swap is strongly better for several
        bodies (ids silently swapped across the net)."""
        cur = alt = 0.0
        n = 0
        for side in VIEWS:
            side_bodies = [b for b in bodies if b["side"] == side]
            q = self.squad_on(side)
            sc, k = self._side_total(side_bodies, q)
            sa, _ = self._side_total(side_bodies, 3 - q)
            cur, alt, n = cur + sc, alt + sa, n + k
        self.last_evidence = None
        instant = False
        if n > 0:
            d = float(np.clip((alt - cur) / n, -self.D_CLIP, self.D_CLIP))
            self.last_evidence = d
            instant = d >= self.INSTANT_DOUBT_D and n >= self.INSTANT_DOUBT_MIN_BODIES
            before = self.cusum
            self.cusum = max(0.0, self.cusum + d - self.switch_drift)
            if before == 0.0 and self.cusum > 0.0:
                self._onset = frame_index
            elif self.cusum == 0.0:
                self._onset = None
        if self.cusum >= self.switch_threshold:
            if frame_index - self.last_flip_frame >= self.min_switch_interval_frames:
                self._flip(frame_index)
                instant = False  # this frame's evidence was FOR the new orientation
            else:
                self.cusum = self.switch_threshold
        # Labels go blank while the orientation is in doubt: a missing label
        # costs an unattributed action, a wrong one corrupts a player's stats.
        self.doubt = instant or self.cusum >= self.DOUBT_FRACTION * self.switch_threshold

    def _flip(self, frame_index: int) -> None:
        self.near_squad = 3 - self.near_squad
        event = {
            "frame": frame_index,
            "onset": self._onset if self._onset is not None else frame_index,
            "near_squad": self.near_squad,
        }
        self.flips.append(event)
        logger.info(
            "Identity: side switch detected at frame %d (onset %d) -- squad %d now near",
            frame_index, event["onset"], self.near_squad,
        )
        self.cusum = 0.0
        self._onset = None
        self.last_flip_frame = frame_index
        for st in self._tids.values():
            st.hold = None

    def _assign_side(self, side: str, side_bodies) -> Dict[int, int]:
        """Which of the side's bodies is which teammate; player index -> tid.

        Hungarian on the per-id evidence (EMA) plus a hysteresis bonus for the
        current holder. A body keeps a held label down to HOLD_FLOOR; a new
        claim needs CLAIM_MIN_FRAMES of tracklet and ``claim_evidence`` -- or,
        with exactly two bodies, a decided partner plus the pair beating its
        swap by ``claim_evidence`` (by elimination). A hold whose quick EMA falls
        below HOLD_FLOOR is broken first: the id silently moved to another
        body (an overlap swap, no box jump) and must not carry the label.
        """
        if not side_bodies:
            return {}
        for b in side_bodies:
            st = b["state"]
            if st.hold is not None and float(st.fast[st.hold]) < self.HOLD_FLOOR:
                st.hold = None
                st.ema = st.fast.copy()  # the slow memory belongs to the old body
        cols = self._squad_players[self.squad_on(side)]
        ev = np.array([[b["state"].ema[p] for p in cols] for b in side_bodies])
        bonus = np.array([
            [self.HOLD_BONUS if b["state"].hold == p else 0.0 for p in cols]
            for b in side_bodies
        ])
        rows, cs = linear_sum_assignment(-(ev + bonus))
        pair_margin = None
        if len(side_bodies) == 2 and len(rows) == 2:
            chosen = sum(ev[r, c] for r, c in zip(rows, cs))
            swapped = sum(ev[r, 1 - c] for r, c in zip(rows, cs))
            pair_margin = float(chosen - swapped)
        # Pass 1: strong decisions (held, or a clear claim on its own).
        decided: Dict[int, bool] = {}
        for r, c in zip(rows, cs):
            st, p = side_bodies[r]["state"], cols[c]
            e = float(ev[r, c])
            if st.hold == p:
                decided[int(r)] = e >= self.HOLD_FLOOR
            else:
                decided[int(r)] = st.n >= self.CLAIM_MIN_FRAMES and e >= self.claim_evidence
        # Pass 2, by elimination: with exactly two bodies, a weak body takes
        # the remaining player when its partner is decided AND the pair beats
        # its swap clearly. Never on the pair margin alone -- the man/woman
        # structure of mixed teams gives a margin whichever team it is.
        for r, c in zip(rows, cs):
            r = int(r)
            if decided[r] or pair_margin is None:
                continue
            partner = next(int(o) for o in rows if int(o) != r)
            e = float(ev[r, c])
            decided[r] = (
                decided[partner]
                and side_bodies[r]["state"].n >= self.CLAIM_MIN_FRAMES
                and pair_margin >= self.claim_evidence
                and e >= self.HOLD_FLOOR
            )
        out: Dict[int, int] = {}
        assigned_rows = set()
        for r, c in zip(rows, cs):
            b = side_bodies[r]
            b["pair_margin"] = pair_margin
            if decided[int(r)]:
                out[cols[c]] = b["tid"]
                b["state"].hold = cols[c]
                assigned_rows.add(int(r))
            else:
                b["state"].hold = None
        for r, b in enumerate(side_bodies):
            if r not in assigned_rows:
                b["state"].hold = None
        side_tids = {b["tid"] for b in side_bodies}
        for tid, st in self._tids.items():
            if tid not in side_tids and st.hold in out:
                st.hold = None
        return out

    def _maybe_learn(self, frame_index, bodies, taken, players) -> None:
        """Add prototypes from confidently identified, isolated, in-court
        bodies -- this is how each player acquires the view they were not
        enrolled in. Never during orientation doubt or right after a flip."""
        if self.cusum > self.LEARN_MAX_CUSUM_FRACTION * self.switch_threshold:
            return
        if self.flips and frame_index - self.last_flip_frame < self.LEARN_SETTLE_FRAMES:
            return
        tid_to_player = {tid: p for p, tid in taken.items()}
        for b in bodies:
            p = tid_to_player.get(b["tid"])
            if p is None or not b["in_court"]:
                continue
            st = b["state"]
            if st.n < self.LEARN_MIN_FRAMES:
                continue
            model = self.players[p]
            view = b["side"]
            if frame_index - model.last_learn[view] < self.LEARN_INTERVAL:
                continue
            own = float(st.ema[p])
            if b["pair_margin"] is not None:
                if b["pair_margin"] < self.learn_margin or own < 0.0:
                    continue
            else:
                mate = next(q for q in self._squad_players[model.squad] if q != p)
                if own - float(st.ema[mate]) < self.learn_margin or own < self.LEARN_MIN_EVIDENCE:
                    continue
            if any(
                self._iou(b["bbox"], o["bbox"]) > self.LEARN_MAX_IOU
                for o in players
                if o.get("bbox") and o.get("track_id") != b["tid"]
            ):
                continue
            self._add_proto(p, view, b["desc"])
            if b["height"] is not None:
                model.heights[view].append(b["height"])
            self._pool[(p, view)].append(_PoolEntry(b["desc"], b["height"]))
            model.last_learn[view] = frame_index
            self._height_cache.clear()
            self._dirty.update((q, v) for q in range(4) for v in VIEWS)
            logger.debug(
                "Identity: learned %s %s prototype at frame %d", model.label, view, frame_index,
            )

    def _add_proto(self, p: int, view: str, desc: Descriptor) -> None:
        """Append, or replace the learned prototype most similar to ``desc``
        (keeps the set diverse). Enrollment anchors are never replaced."""
        model = self.players[p]
        protos = model.protos[view]
        self._proto_cache.pop((p, NEAR), None)
        self._proto_cache.pop((p, FAR), None)
        if len(protos) < self.MAX_PROTOS:
            protos.append(desc)
            return
        start = model.n_anchor[view]
        if start >= len(protos):
            return
        parts, mask = stack_descriptors(protos[start:])
        dparts, dmask = stack_descriptors([desc])
        sims = [
            float(appearance_scores(parts[k:k + 1], mask[k:k + 1], dparts, dmask)[0])
            for k in range(parts.shape[0])
        ]
        protos[start + int(np.argmax(sims))] = desc
