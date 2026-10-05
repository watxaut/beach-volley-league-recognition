"""Player enrollment pre-pass (E1): stable P1A/P1B/P2A/P2B identity anchors.

Runs ONCE per video, before the per-frame pipeline: a sequential decode of the
first ``max_frames`` frames (VFR-safe -- plain ``cap.read()`` from frame 0, no
``CAP_PROP_POS_FRAMES`` seeks, per AGENTS.md §9), the player DETECTOR on every
``stride``-th frame only (no tracking, no pose), foot-strictly-in-court
detections kept (same admission pool as the tracker's strict set).

The sampled detections are grouped into identity chains by greedy
nearest-neighbour matching over consecutive samples (position gate + torso
histogram tie-break; a chain dies after ``chain_gap_samples`` consecutive
misses). Fragmented chains of the same player (occlusions) are merged back
together (endpoint proximity + histogram correlation, best pair first). The 4
most persistent chains become ENROLLMENT REFERENCES: each carries an ensemble
appearance signature (torso/head HSV histograms, ground-plane world height and
width samples -- the same channels as PlayerTracker's ensemble, built from
MANY crops instead of the single crop the in-stream bootstrap sees) plus its
label:

* squad 1 = the pair whose majority side over the window is NEAR ("A"),
  squad 2 = the far ("B") pair. Team 1 is "the team that starts on the near
  side" (owner convention). If the window does not show a clean 2+2 split,
  enrollment returns None and the pipeline falls back to today's behaviour
  (labels None, ``P<tid>`` display).
* within a squad, slot A/B = left-to-right by foot x at the EARLIEST sampled
  frame where both teammates are simultaneously observed (fallback: mean foot
  x over the window).

The references are consumed by PlayerTracker.set_enrollment: they map onto
whatever the GT-validated in-stream bootstrap locks (labels are attached by
signature matching; bootstrap/admission machinery is untouched) and become the
permanent appearance anchors for label assignment of later-created tracks.

Display metadata only: enrollment NEVER changes a tracking decision. The
tracked output gains ``player_label`` / ``squad`` / ``slot``; association,
admission and retirement are byte-identical with enrollment off (guarded by
tests).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Chain-merge appearance floor: mean-torso-histogram correlation above which
# two chains whose endpoints are close may be joined (same player across an
# occlusion). Same-player values measured well above this; partners differ.
_MERGE_MIN_CORREL = 0.45


@dataclass
class _Chain:
    """One identity hypothesis: an ordered run of strict in-court detections."""

    observations: List[Dict[str, Any]] = field(default_factory=list)
    misses: int = 0  # consecutive sampled frames without a match
    hist_sum: Optional[np.ndarray] = None  # running sum of torso histograms
    head_sum: Optional[np.ndarray] = None
    hist_n: int = 0

    def add(self, obs: Dict[str, Any]) -> None:
        self.observations.append(obs)
        self.misses = 0
        hist = obs.get("histogram")
        if hist is not None:
            self.hist_sum = hist.copy() if self.hist_sum is None else self.hist_sum + hist
            self.hist_n += 1
        head = obs.get("head_histogram")
        if head is not None:
            self.head_sum = head.copy() if self.head_sum is None else self.head_sum + head

    @property
    def last(self) -> Dict[str, Any]:
        return self.observations[-1]

    @property
    def last_foot(self) -> np.ndarray:
        return np.array(self.last["foot"], dtype=float)

    def mean_hist(self) -> Optional[np.ndarray]:
        if self.hist_sum is None or self.hist_n == 0:
            return None
        mean = self.hist_sum / self.hist_n
        cv2.normalize(mean, mean, 0, 1, cv2.NORM_MINMAX)
        return mean

    def mean_head(self) -> Optional[np.ndarray]:
        if self.head_sum is None:
            return None
        mean = self.head_sum / max(1, self.hist_n)
        cv2.normalize(mean, mean, 0, 1, cv2.NORM_MINMAX)
        return mean

    def correl(self, hist: Optional[np.ndarray]) -> float:
        """Histogram correlation of ``hist`` against the chain's running mean."""
        mean = self.mean_hist()
        if mean is None or hist is None:
            return 0.0
        return float(max(0.0, cv2.compareHist(mean, hist, cv2.HISTCMP_CORREL)))


class PlayerEnrollment:
    """Build the 4 enrollment references from the opening of a video."""

    def __init__(
        self,
        court_calibration,
        player_detector,
        tracker,
        max_frames: int = 600,
        stride: int = 5,
        min_observations: int = 8,
        chain_gate_px: float = 120.0,
        chain_gap_samples: int = 6,
        merge_gap_frames: int = 60,
        enabled: bool = True,
    ):
        self.court_calibration = court_calibration
        self.player_detector = player_detector
        self.tracker = tracker  # PlayerTracker: signature feature provider
        self.max_frames = max_frames
        self.stride = max(1, stride)
        self.min_observations = min_observations
        self.chain_gate_px = chain_gate_px
        self.chain_gap_samples = chain_gap_samples
        self.merge_gap_frames = merge_gap_frames
        self.enabled = enabled
        # Diagnostics of the last enroll() call (tests + logs).
        self.last_result: Dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #

    def enroll(self, video_path: str) -> Optional[List[Dict[str, Any]]]:
        """Run the pre-pass. Returns 4 reference dicts, or None on fallback.

        Fallback reasons: disabled, uncalibrated court, unreadable video,
        fewer than 4 persistent in-court chains, or no clean 2-near + 2-far
        split. None means "no enrollment" -- the pipeline behaves exactly as
        before (unlabeled tracks).
        """
        self.last_result = {}
        if not self.enabled:
            self.last_result["reason"] = "disabled"
            return None
        if self.court_calibration is None or not getattr(
            self.court_calibration, "is_calibrated", False
        ):
            self.last_result["reason"] = "no_court_calibration"
            logger.warning("Player enrollment skipped: court not calibrated")
            return None

        sampled = self._sample_frames(video_path)
        if not sampled:
            self.last_result["reason"] = "no_frames_sampled"
            return None

        chains = self._build_chains(sampled)
        chains = self._merge_chains(chains)
        persistent = [c for c in chains if len(c.observations) >= self.min_observations]
        persistent.sort(key=lambda c: len(c.observations), reverse=True)
        self.last_result["n_chains"] = len(chains)
        self.last_result["n_persistent"] = len(persistent)
        self.last_result["n_samples"] = len(sampled)

        if len(persistent) < 4:
            self.last_result["reason"] = "fewer_than_4_persistent_chains"
            logger.info(
                "Player enrollment fallback: %d persistent chains (< 4) from "
                "%d samples", len(persistent), len(sampled),
            )
            return None

        top4 = persistent[:4]
        refs = self._assign_squads_and_slots(top4)
        if refs is None:
            self.last_result["reason"] = "no_2_plus_2_side_split"
            logger.info(
                "Player enrollment fallback: top-4 chains are not a 2-near + "
                "2-far split (sides: %s)",
                [(c.last.get("team"), len(c.observations)) for c in top4],
            )
            return None

        self.last_result["reason"] = "enrolled"
        self.last_result["labels"] = [r["label"] for r in refs]
        logger.info(
            "Player enrollment: %s from %d samples / %d chains (%s)",
            self.last_result["labels"], len(sampled), len(chains),
            ", ".join(f"{r['label']}:{r['n_observations']}obs" for r in refs),
        )
        return refs

    # ------------------------------------------------------------------ #
    # Stage 1: sequential sample of strict in-court detections
    # ------------------------------------------------------------------ #

    def _sample_frames(self, video_path: str) -> List[Dict[str, Any]]:
        """Sequential decode of the first ``max_frames`` frames; detect on
        every ``stride``-th. NO seeks: plain cap.read() from frame 0 (VFR
        rule, AGENTS.md §9)."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning("Player enrollment: cannot open %s", video_path)
            return []

        sampled: List[Dict[str, Any]] = []
        frame_idx = 0
        try:
            while frame_idx < self.max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % self.stride == 0:
                    sampled.extend(self._sample_one(frame, frame_idx))
                frame_idx += 1
        finally:
            cap.release()
        return sampled

    def _sample_one(self, frame: np.ndarray, frame_idx: int) -> List[Dict[str, Any]]:
        """Detect players on one sampled frame; keep foot-strictly-in-court."""
        detections = self.player_detector.detect(frame)
        if not detections:
            return []
        strict = self.court_calibration.filter_detections_by_court(detections)
        obs: List[Dict[str, Any]] = []
        for det in strict:
            bbox = det.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            foot = self.court_calibration.foot_point(bbox)
            sig = self.tracker.compute_enrollment_signature(frame, bbox)
            obs.append(
                {
                    "frame": frame_idx,
                    "bbox": bbox,
                    "foot": (float(foot[0]), float(foot[1])),
                    "confidence": det.get("confidence", 0.5),
                    "team": self.court_calibration.get_team_for_bbox(
                        [int(v) for v in bbox]
                    ),
                    "histogram": sig.get("histogram"),
                    "head_histogram": sig.get("head_histogram"),
                    "world_height": self._first_or_none(sig.get("world_height_samples")),
                    "world_width": self._first_or_none(sig.get("world_width_samples")),
                }
            )
        return obs

    @staticmethod
    def _first_or_none(values: Optional[List[float]]) -> Optional[float]:
        if not values:
            return None
        return float(values[0])

    # ------------------------------------------------------------------ #
    # Stage 2: identity chaining + fragment merge
    # ------------------------------------------------------------------ #

    def _build_chains(self, sampled: List[Dict[str, Any]]) -> List[_Chain]:
        """Greedy nearest-neighbour chaining over consecutive sampled frames.

        Stride frames are ~0.2 s apart, so a player moves well under the gate;
        the appearance histogram breaks ties when two players sit close. Each
        sampled frame is a ONE-TO-ONE match (best (correlation, -distance)
        pair first; every chain takes at most one observation per frame) so
        two players who project within the gate cannot both feed one chain.
        A chain unmatched for ``chain_gap_samples`` consecutive samples dies
        (occlusion fragments are re-joined by _merge_chains).
        """
        chains: List[_Chain] = []
        by_frame: Dict[int, List[Dict[str, Any]]] = {}
        for obs in sampled:
            by_frame.setdefault(obs["frame"], []).append(obs)

        for frame_idx in sorted(by_frame.keys()):
            obs_list = by_frame[frame_idx]
            pairs = []  # (score, obs_index, chain)
            for oi, obs in enumerate(obs_list):
                foot = np.array(obs["foot"], dtype=float)
                for chain in chains:
                    if chain.misses >= self.chain_gap_samples:
                        continue
                    dist = float(np.linalg.norm(chain.last_foot - foot))
                    if dist > self.chain_gate_px:
                        continue
                    # Score: appearance first, distance as tie-break.
                    pairs.append((
                        (chain.correl(obs.get("histogram")), -dist), oi, chain,
                    ))
            pairs.sort(key=lambda t: t[0], reverse=True)
            used_obs: set = set()
            fed: List[_Chain] = []
            for _score, oi, chain in pairs:
                if oi in used_obs or chain in fed:
                    continue
                chain.add(obs_list[oi])
                used_obs.add(oi)
                fed.append(chain)
            for oi, obs in enumerate(obs_list):
                if oi in used_obs:
                    continue
                chain = _Chain()
                chain.add(obs)
                chains.append(chain)
                fed.append(chain)
            for chain in chains:
                if chain not in fed:
                    chain.misses += 1
        return chains

    def _merge_chains(self, chains: List[_Chain]) -> List[_Chain]:
        """Re-join occlusion fragments of the same player.

        Two chains merge when the earlier one's END sits within the gate of
        the later one's START, the time gap is short, and their torso
        histograms correlate. The best-correlated pair merges first, then the
        loop re-runs (a merge can enable the next one).
        """
        merged = True
        while merged and len(chains) > 1:
            merged = False
            best = None  # (correl, -gap, i, j)
            for i in range(len(chains)):
                for j in range(len(chains)):
                    if i == j:
                        continue
                    a, b = chains[i], chains[j]
                    gap = b.observations[0]["frame"] - a.last["frame"]
                    if gap <= 0 or gap > self.merge_gap_frames:
                        continue
                    dist = float(
                        np.linalg.norm(
                            a.last_foot - np.array(b.observations[0]["foot"])
                        )
                    )
                    if dist > self.chain_gate_px:
                        continue
                    corr = min(a.correl(b.mean_hist()), b.correl(a.mean_hist()))
                    if corr < _MERGE_MIN_CORREL:
                        continue
                    key = (corr, -gap)
                    if best is None or key > best[0]:
                        best = (key, i, j)
            if best is not None:
                _, i, j = best
                chains[i].observations.extend(chains[j].observations)
                chains[i].misses = chains[j].misses
                chains[i].hist_sum = (
                    chains[i].hist_sum
                    if chains[j].hist_sum is None
                    else (
                        chains[j].hist_sum
                        if chains[i].hist_sum is None
                        else chains[i].hist_sum + chains[j].hist_sum
                    )
                )
                chains[i].head_sum = (
                    chains[i].head_sum
                    if chains[j].head_sum is None
                    else (
                        chains[j].head_sum
                        if chains[i].head_sum is None
                        else chains[i].head_sum + chains[j].head_sum
                    )
                )
                chains[i].hist_n += chains[j].hist_n
                chains.pop(j)
                merged = True
        return chains

    # ------------------------------------------------------------------ #
    # Stage 3: squads, slots, reference signatures
    # ------------------------------------------------------------------ #

    def _assign_squads_and_slots(
        self, top4: List[_Chain]
    ) -> Optional[List[Dict[str, Any]]]:
        """Squad = majority side over the window (team 1 = the near pair);
        slot A/B = left-to-right at the earliest frame both teammates are seen.

        Requires a clean 2-near + 2-far split, else None (no enrollment).
        """
        sides: List[str] = []
        for chain in top4:
            votes = [
                o["team"] for o in chain.observations if o.get("team") in ("A", "B")
            ]
            if not votes:
                return None
            sides.append(max(set(votes), key=votes.count))

        near = [c for c, s in zip(top4, sides) if s == "A"]
        far = [c for c, s in zip(top4, sides) if s == "B"]
        if len(near) != 2 or len(far) != 2:
            return None

        refs: List[Dict[str, Any]] = []
        for squad, pair in ((1, near), (2, far)):
            slot_a, slot_b = self._left_right(pair)
            for slot, chain in (("A", slot_a), ("B", slot_b)):
                refs.append(self._build_reference(chain, squad, slot))
        return refs

    def _left_right(self, pair: List[_Chain]) -> Tuple[_Chain, _Chain]:
        """Return (left, right) chains. Left-to-right decided at the earliest
        sampled frame where both are simultaneously observed; fallback mean-x
        over the window."""
        a, b = pair
        a_frames = {o["frame"]: o for o in a.observations}
        b_frames = {o["frame"]: o for o in b.observations}
        shared = sorted(set(a_frames) & set(b_frames))
        if shared:
            f = shared[0]
            if a_frames[f]["foot"][0] <= b_frames[f]["foot"][0]:
                return a, b
            return b, a
        mean_ax = float(np.mean([o["foot"][0] for o in a.observations]))
        mean_bx = float(np.mean([o["foot"][0] for o in b.observations]))
        return (a, b) if mean_ax <= mean_bx else (b, a)

    def _build_reference(self, chain: _Chain, squad: int, slot: str) -> Dict[str, Any]:
        """Ensemble reference signature from ALL of the chain's crops."""
        heights = [
            o["world_height"] for o in chain.observations if o.get("world_height")
        ]
        widths = [o["world_width"] for o in chain.observations if o.get("world_width")]
        return {
            "label": f"P{squad}{slot}",
            "squad": squad,
            "slot": slot,
            "histogram": chain.mean_hist(),
            "head_histogram": chain.mean_head(),
            "world_height_samples": heights,
            "world_width_samples": widths,
            "n_observations": len(chain.observations),
            "first_frame": chain.observations[0]["frame"],
            "last_frame": chain.last["frame"],
            "last_foot": list(chain.last["foot"]),
        }
