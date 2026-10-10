"""Post-run input: the per-frame stream the single causal pass already produced.

AGENTS.md §6: hindsight work never re-decodes the video. Everything here is
read from the ``--diag-dump`` JSONL sidecar (schema >= 4 carries the ball
bbox/velocity and the per-frame identity labels) plus, optionally,
``pipeline_output.json`` for the fps and the calibration path.

Older dumps (schema 1-3) still load: the ball width is recovered from the
matching raw detection, velocity from finite differences, and the possession
/ ground rows are simply absent -- the post-run layer derives its own depth
and ground reads from the bbox, so those rows are corroboration, not input.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .geometry import SIDE_FAR, SIDE_NEAR

# ball_state codes
BALL_NONE, BALL_PREDICTED, BALL_TRACKED = 0, 1, 2

#: A rally is read with the stretch around it where the players already /
#: still stand in formation: seconds before the serve, after the ball is dead.
RALLY_WINDOW_S = (1.5, 0.5)

#: Perception's court-side letters (AGENTS.md: near half = "A", far = "B").
#: They name a HALF, never a squad -- squads come from the identity labels.
_SIDE_OF_LETTER = {"A": SIDE_NEAR, "B": SIDE_FAR}


@dataclass
class PlayerObs:
    """One tracked player on one frame."""

    track_id: int
    bbox: Tuple[float, float, float, float]
    predicted: bool
    court_side: Optional[str]          # near / far, from the feet
    label: Optional[str] = None        # P1A ... (identity resolver, this frame)
    squad: Optional[int] = None
    slot: Optional[int] = None
    #: Similarity to each enrolled player's anchors, in the dump's
    #: ``identity_players`` order (schema 5; clean, real bodies only).
    id_sims: Optional[Tuple[float, ...]] = None

    @property
    def foot(self) -> Tuple[float, float]:
        return ((self.bbox[0] + self.bbox[2]) / 2.0, self.bbox[3])

    @property
    def height_px(self) -> float:
        return float(self.bbox[3] - self.bbox[1])


@dataclass
class ContactCandidate:
    """A ball-trajectory vertex the classifier found (accepted or refused by
    the reach gate). Keyed by its CONTACT frame."""

    frame: int
    accepted: bool
    kind: Optional[str] = None               # bounce | drive | redirect | reentry
    point: Optional[Tuple[float, float]] = None
    track_id: Optional[int] = None           # perception's toucher / nearest track
    distance_px: Optional[float] = None      # reach-refused only
    action: Optional[str] = None             # perception label (accepted only)
    gesture: Optional[str] = None
    court_side: Optional[str] = None         # perception's side for the toucher
    near_net: Optional[bool] = None


@dataclass
class MatchStream:
    fps: float
    n_frames: int
    ball_state: np.ndarray                   # (N,) int8
    ball_xy: np.ndarray                      # (N, 2) centre, NaN when no ball
    ball_bbox: np.ndarray                    # (N, 4) NaN unless TRACKED
    ball_conf: np.ndarray                    # (N,)
    raw_dets: List[List[Tuple[float, float, float, float, float, bool]]]
    players: List[List[PlayerObs]]
    candidates: List[ContactCandidate]
    obs_side: List[Optional[str]] = field(default_factory=list)     # #77 row
    obs_ground: List[Optional[str]] = field(default_factory=list)   # #80 row
    schema_version: int = 0
    #: Labels the ``id_sims`` columns stand for (None: the dump has none).
    identity_players: Optional[List[str]] = None

    # -- derived reads ---------------------------------------------------- #

    @property
    def ball_w(self) -> np.ndarray:
        return self.ball_bbox[:, 2] - self.ball_bbox[:, 0]

    @property
    def tracked(self) -> np.ndarray:
        return self.ball_state == BALL_TRACKED

    @property
    def has_identity_observations(self) -> bool:
        return bool(self.identity_players) and any(
            p.id_sims is not None for row in self.players for p in row)

    def seconds(self, frames: float) -> float:
        return float(frames) / self.fps

    def frames(self, seconds: float) -> int:
        return int(round(seconds * self.fps))

    def rally_window(self, start_frame: int, end_frame: int) -> Tuple[int, int]:
        """First and last frame a rally's players are read on."""
        before, after = (self.frames(s) for s in RALLY_WINDOW_S)
        return max(0, start_frame - before), min(self.n_frames - 1, end_frame + after)

    def players_at(self, frame: int, search: int = 0) -> List[PlayerObs]:
        """Players on ``frame``; with ``search`` > 0 fall back to the nearest
        frame within that many frames that has any."""
        for d in range(0, search + 1):
            for f in ((frame,) if d == 0 else (frame - d, frame + d)):
                if 0 <= f < self.n_frames and self.players[f]:
                    return self.players[f]
        return []


def _bbox_from_dets(center, dets) -> Optional[List[float]]:
    for d in dets:
        c = d.get("center")
        if c and abs(c[0] - center[0]) < 1.0 and abs(c[1] - center[1]) < 1.0:
            return d.get("bbox")
    return None


def load_stream(diag_path: str, fps: Optional[float] = None) -> MatchStream:
    """Read a ``--diag-dump`` JSONL into dense per-frame arrays."""
    meta: Dict[str, Any] = {}
    records: Dict[int, Dict[str, Any]] = {}
    with open(diag_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "meta" in rec and len(rec) == 1:
                meta = rec["meta"]
                continue
            records[int(rec["frame"])] = rec
    if not records:
        raise ValueError(f"empty diag dump: {diag_path}")
    n = max(records) + 1
    fps = float(fps or meta.get("fps") or 30.0)

    state = np.zeros(n, dtype=np.int8)
    xy = np.full((n, 2), np.nan)
    bbox = np.full((n, 4), np.nan)
    conf = np.full(n, np.nan)
    raw: List[List[Tuple[float, float, float, float, float, bool]]] = [[] for _ in range(n)]
    players: List[List[PlayerObs]] = [[] for _ in range(n)]
    obs_side: List[Optional[str]] = [None] * n
    obs_ground: List[Optional[str]] = [None] * n
    candidates: Dict[Tuple[int, bool], ContactCandidate] = {}

    for frame, rec in records.items():
        for cand in rec.get("candidates") or []:
            _collect_candidate(cand, candidates)
        if frame < 0:
            continue
        dets = rec.get("ball_dets") or []
        for d in dets:
            b = d.get("bbox")
            if b:
                raw[frame].append((float(b[0]), float(b[1]), float(b[2]), float(b[3]),
                                   float(d.get("conf") or 0.0), bool(d.get("removed"))))
        bt = rec.get("ball_track") or {}
        center = bt.get("center")
        if center and center[0] is not None:
            xy[frame] = center
            conf[frame] = bt.get("conf") if bt.get("conf") is not None else np.nan
            if bt.get("state") == "tracked":
                state[frame] = BALL_TRACKED
                b = bt.get("bbox") or _bbox_from_dets(center, dets)
                if b:
                    bbox[frame] = b
            else:
                state[frame] = BALL_PREDICTED
        for p in rec.get("players") or []:
            b = p.get("bbox")
            if not b or p.get("track_id") is None:
                continue
            sims = p.get("id_sims")
            players[frame].append(PlayerObs(
                track_id=int(p["track_id"]),
                bbox=(float(b[0]), float(b[1]), float(b[2]), float(b[3])),
                predicted=bool(p.get("predicted")),
                court_side=_SIDE_OF_LETTER.get(p.get("team")),
                label=p.get("player_label"), squad=p.get("squad"), slot=p.get("slot"),
                id_sims=tuple(float(v) for v in sims) if sims else None,
            ))
        pos = rec.get("ball_possession") or {}
        obs_side[frame] = pos.get("side")
        ground = rec.get("ball_ground") or {}
        if not ground.get("held", True):
            obs_ground[frame] = ground.get("state")

    return MatchStream(
        fps=fps, n_frames=n, ball_state=state, ball_xy=xy, ball_bbox=bbox,
        ball_conf=conf, raw_dets=raw, players=players,
        candidates=sorted(candidates.values(), key=lambda c: (c.frame, not c.accepted)),
        obs_side=obs_side, obs_ground=obs_ground,
        schema_version=int(meta.get("schema_version") or 0),
        identity_players=list(meta.get("identity_players") or []) or None,
    )


def _collect_candidate(cand: Dict[str, Any],
                       out: Dict[Tuple[int, bool], ContactCandidate]) -> None:
    """Fold one classifier diag row into the candidate table.

    A contact shows up as ``candidate_passed_gates`` (carries the contact
    point) and later as ``accepted`` (carries the resolved label); a vertex
    with no player in reach shows up once as ``rejected / reach``.
    """
    stage, reason = cand.get("stage"), cand.get("reason")
    frame = cand.get("frame")
    if frame is None:
        return
    frame = int(frame)
    if stage in ("accepted", "candidate_passed_gates"):
        row = out.setdefault((frame, True), ContactCandidate(frame=frame, accepted=True))
        row.kind = cand.get("kind") or row.kind
        row.track_id = cand.get("track_id", row.track_id)
        row.gesture = cand.get("gesture") or row.gesture
        row.court_side = _SIDE_OF_LETTER.get(cand.get("team")) or row.court_side
        if cand.get("near_net") is not None:
            row.near_net = bool(cand.get("near_net"))
        if stage == "accepted":
            row.action = cand.get("action")
        point = cand.get("contact_point")
        if point:
            row.point = (float(point[0]), float(point[1]))
    elif stage == "rejected" and reason == "reach":
        out[(frame, False)] = ContactCandidate(
            frame=frame, accepted=False, kind=cand.get("kind"),
            track_id=cand.get("track_id"), distance_px=cand.get("distance"),
        )
