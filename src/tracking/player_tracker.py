"""
Player tracker for beach volleyball video analysis.

Tracks exactly 4 players with stable IDs (1-4). Uses spatial proximity
and color histogram appearance features to maintain identity across frames.
Integrates with CourtCalibration for team assignment (2 per side of net).
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2
from scipy.optimize import linear_sum_assignment
from collections import defaultdict, deque, Counter
import logging


class PlayerTracker:
    """Tracks exactly 4 beach volleyball players with stable IDs.

    Key design decisions:
    - Never creates a 5th track. Unmatched detections beyond 4 are discarded.
    - Uses color histogram of torso crop for appearance matching to prevent
      ID swaps when players cross paths.
    - No aspect ratio filter (diving players have unusual aspect ratios).
    - High max_velocity (150 px/frame) to handle diving.
    """

    # Squatter review samples a track's world foot position every 10th fed
    # frame into a deque of this length -- 12 samples span the 120-frame
    # review window, so the expulsion cooldown covers the straddler's whole
    # drift path, not just the expulsion point.
    _SQUATTER_SAMPLE_MAXLEN = 12
    _SQUATTER_SAMPLE_EVERY = 10

    def __init__(
        self,
        max_disappeared: int = 90,
        max_distance: float = 150.0,
        max_velocity: float = 150.0,
        max_players: int = 4,
        appearance_weight: float = 0.4,
        init_frames: int = 60,
        court_calibration=None,
        team_vote_window: int = 15,
        coast_extrapolation_cap: int = 15,
        coast_velocity_decay: float = 0.85,
        gallery_enabled: bool = True,
        gallery_reacquire_distance_px: float = 120.0,
        gallery_reacquire_min_appearance: float = 0.15,
        gallery_reacquire_appearance_min: float = 0.5,
        gallery_evict_min_hold_frames: int = 60,
        bootstrap_min_window: int = 8,
        bootstrap_ball_required: bool = True,
        signature_color_weight: float = 0.4,
        signature_head_weight: float = 0.15,
        signature_height_weight: float = 0.3,
        signature_proportions_weight: float = 0.15,
        signature_height_smoothing: int = 30,
        off_court_grace_frames: int = 45,
        off_court_hold_frames: int = 90,
        off_court_cost_penalty_px: float = 300.0,
        squatter_enabled: bool = True,
        squatter_review_frames: int = 120,
        squatter_min_fed_frames: int = 20,
        squatter_min_in_court_frac: float = 0.35,
        squatter_cooldown_radius_m: float = 0.5,
        serve_zone_enabled: bool = True,
        serve_zone_depth_m: float = 3.0,
        serve_zone_side_margin_m: float = 1.0,
        serve_zone_trial_frames: int = 90,
        serve_zone_ball_votes: int = 2,
        coast_vertical_damping: float = 0.5,
        debug_assignments: bool = False,
        label_min_similarity: float = 0.35,
    ):
        """Initialize the player tracker.

        Args:
            max_disappeared: Max frames a player can be missing before re-init.
            max_distance: Max centroid distance (px) for association.
            max_velocity: Max allowed velocity (px/frame).
            max_players: Maximum number of tracked players (4 for beach volleyball).
            appearance_weight: Weight of appearance cost vs distance cost [0-1].
            init_frames: Number of initial frames to collect detections for
                stable initialization.
            court_calibration: Optional CourtCalibration instance for team assignment.
            debug_assignments: Record every detection-to-track assignment (path,
                frame, id, foot-in-court) into self.assignment_log. Off by
                default; used to audit which association path admits whom.
            off_court_grace_frames: How long a track may be fed by foot-out-of-
                court detections after its last in-court sighting (a player who
                stepped out -- server behind the baseline). Beyond the grace
                window, out-of-court detections can no longer drive the track,
                so a bystander standing just off-court can never inherit it
                (bystander-hijack guard, complements the new-track admission
                test).
            off_court_hold_frames: Horizon on CONTINUOUS out-of-court feeding.
                The grace window above is bypassed while the track is matched
                frame-to-frame with no gap (a player who walked out and keeps
                being detected) -- without a horizon that exception lets a
                person who straddled the sideline at bootstrap hold a roster
                slot forever (entreno_2: right-side bystander fed for 415
                frames while two real near-side players shared the remaining
                slots). Past the horizon the track stops feeding, retires
                through the normal missing-frames path, and strict in-court
                admission can take the slot. Real players stay far below it:
                the longest measured out-of-court streak on the GT videos is
                46 frames (e6 t3); the default matches serve_zone_trial_frames.
            off_court_cost_penalty_px: Association-cost penalty (px-equivalent)
                added to OUT-OF-COURT detections in the Hungarian cost matrix.
                _may_feed_track decides whether an out-of-court feeding is
                ALLOWED at all; this decides which candidate WINS when the
                track has a choice: identity is anchored on the court, so a
                court detection must beat an off-court one even at a longer
                gate distance. Without it a walkway bystander re-attaches to
                a coasting track the instant the player's own detection blips
                (entreno_6 f142: the far-left digger's track was taken at a
                105 px jump and never returned -- the digger sat detected
                in court for 200 frames), and the squat then cascades into
                chain-swaps where several tracks rotate onto bystanders
                (e6 f305/f311; P1's team vote flipped A->B). Must stay below
                the 1e6 invalid sentinel so an off-court chain is still
                preferred over leaving a track unmatched when NO in-court
                option exists; 0 restores strict distance-only preference;
                uncalibrated courts are unaffected (in_court is None).
            serve_zone_enabled: Admit a NEW track for a detection whose foot is
                in a serve zone (just behind a baseline, on the ground plane)
                when a roster slot is free -- the serving player at video/rally
                start is off-court and would otherwise never be tracked (they
                also hold the 4th slot closed for everyone else).
            serve_zone_depth_m / serve_zone_side_margin_m: serve-zone geometry
                in metres (see CourtCalibration.is_in_serve_zone).
            serve_zone_trial_frames: A serve-zone seed that has not entered the
                strict court within this many frames is hard-removed (NOT
                gallery'd): a stationary serve-zone bystander is continuously
                detected, so neither the off-court grace nor retirement ever
                fires, and it would hold a roster slot forever (entreno_5: a
                bottom-left bystander held the 4th slot the whole video while
                the real server went untracked).
            serve_zone_ball_votes: How many recent ball sightings inside a
                serve-zone candidate's column (x-span, above the waist --
                held at the chest or tossed above the head) qualify that
                candidate as the server. A sand-level spare ball beside a
                bystander never enters their column; a held/tossed serve ball
                stays in the server's column frame after frame.
            squatter_enabled: Review each track's LIFETIME in-court feeding
                fraction once it is old enough, and expire the persistent
                sideline straddler: a bystander who seeds a track while
                straddling the sideline reads "in court" for a dense early run
                (e7: f47-79 at 7.87-7.99 m), so neither strict admission nor
                the hold horizon can touch them while they squat a roster slot
                forever. Expiry is to the GALLERY with a squatter flag (a real
                player off-court between points on match footage stays
                fail-safe recoverable) -- hard-remove stays reserved for
                never-in-court seeds (e5 precedent).
            squatter_review_frames: Track age (frames since creation) at which
                the review may first fire. 120 = the e7 straddler's own tick
                (34/120 = 28% in-court fed); their dense early in-court run
                forbids anything earlier.
            squatter_min_fed_frames: Noise floor on real feedings before the
                fraction may expire a track; barely-fed tracks coast toward
                normal retirement instead.
            squatter_min_in_court_frac: Expire when in_court_fed / fed stays
                below this at/after the review tick (lifetime fraction, not
                rolling -- occluded real players keep their fraction frozen at
                100%). Worst real case measured is ~0.62 (e6, 46f off-court
                streak); the e7 straddler sits at 0.28.
            squatter_cooldown_radius_m: After an expiry, the expelled track's
                sampled world foot positions block NEW-track admission within
                this ground radius -- including in-court candidates (the
                straddler's re-admission attempts read 7.84-7.99 m). Never
                affects existing tracks.
            coast_vertical_damping: Extra per-step multiplier on the UPWARD
                coast velocity. A track lost mid-jump would otherwise ride its
                upward velocity for the whole coast window, drifting the ghost
                box far above the player; players land near their takeoff spot,
                so upward coasting decays fast (cosmetic for ghost boxes and
                keeps re-acquisition gating honest after jumps). Downward
                velocity is court-axis running and coasts normally.
        """
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.max_velocity = max_velocity
        self.max_players = max_players
        self.appearance_weight = appearance_weight
        self.init_frames = init_frames
        self.court_calibration = court_calibration
        self.team_vote_window = team_vote_window
        self.coast_extrapolation_cap = coast_extrapolation_cap
        self.coast_velocity_decay = coast_velocity_decay

        # --- Identity (continuity-first) config (1a/1b/1c) ---
        self.gallery_enabled = gallery_enabled
        self.gallery_reacquire_distance_px = gallery_reacquire_distance_px
        self.gallery_reacquire_min_appearance = gallery_reacquire_min_appearance
        self.gallery_reacquire_appearance_min = gallery_reacquire_appearance_min
        self.gallery_evict_min_hold_frames = gallery_evict_min_hold_frames
        self.bootstrap_min_window = bootstrap_min_window
        self.bootstrap_ball_required = bootstrap_ball_required
        self.bootstrap_max_wait = init_frames  # fallback: never block the whole video
        self.signature_weights = {
            "color": signature_color_weight,
            "head": signature_head_weight,
            "height": signature_height_weight,
            "proportions": signature_proportions_weight,
        }
        self.signature_height_smoothing = signature_height_smoothing

        # Tracking state
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.disappeared: Dict[int, int] = {}
        # 1b: dormant gallery -- retired (lost) tracks held match-long so their
        # original id can be restored on re-acquisition. The hard cap counts
        # active + dormant together, so a dormant id can't be stolen. Empty
        # until _retire_track is wired (phase 1b).
        self.gallery: Dict[int, Dict[str, Any]] = {}
        # No next_id — IDs are recycled from range 1..max_players
        self.frame_count = 0
        self._initialized = False

        # Bootstrap (1a): accumulate foot-in-court detections on ball-active
        # frames, then lock the 4 most persistent as the roster.
        self._bootstrap_buffer: List[List[Dict[str, Any]]] = []
        self._bootstrap_qualifying = 0
        self._last_strict_detections: List[Dict[str, Any]] = []
        # Current frame for appearance extraction
        self._current_frame: Optional[np.ndarray] = None

        # Optional audit trail of every detection-to-track assignment
        self.debug_assignments = debug_assignments
        self.assignment_log: List[Dict[str, Any]] = []
        self.off_court_grace_frames = off_court_grace_frames
        self.off_court_hold_frames = off_court_hold_frames
        self.off_court_cost_penalty_px = off_court_cost_penalty_px
        self.squatter_enabled = squatter_enabled
        self.squatter_review_frames = squatter_review_frames
        self.squatter_min_fed_frames = squatter_min_fed_frames
        self.squatter_min_in_court_frac = squatter_min_in_court_frac
        self.squatter_cooldown_radius_m = squatter_cooldown_radius_m
        self.serve_zone_enabled = serve_zone_enabled
        self.serve_zone_depth_m = serve_zone_depth_m
        self.serve_zone_side_margin_m = serve_zone_side_margin_m
        self.serve_zone_trial_frames = serve_zone_trial_frames
        self.serve_zone_ball_votes = serve_zone_ball_votes
        self.label_min_similarity = label_min_similarity

        # Enrollment references (E1): stable appearance anchors + labels
        # (P1A/P1B/P2A/P2B) built by the PlayerEnrollment pre-pass. Labels are
        # DISPLAY-ONLY: they never influence association, admission or
        # retirement, so tracking is byte-identical with or without them.
        self._enrollment_refs: List[Dict[str, Any]] = []
        # tid -> (label, squad, slot); survives retire-to-gallery + restore
        # (same player, same id), cleared when an id is hard-removed or
        # reclaimed so a recycled id never inherits the old player's label.
        self._track_labels: Dict[int, Tuple[str, int, str]] = {}

        # Trial-expiry cooldown: last bboxes of hard-removed serve-zone
        # squatters, so the same stationary person is not re-admitted from the
        # zone right after removal (in-court admission is never blocked -- if
        # they ever step in, they are tracked like anyone else).
        self._serve_zone_cooldown: deque = deque(maxlen=8)
        # Squatter-expiry cooldown: world foot points sampled from expired
        # sideline straddlers (a POINT CLOUD per expulsion -- the e7 straddler
        # drifted 7.87->8.9 m, so a single expulsion point would be missed and
        # the track would oscillate back). Blocks NEW-track admission near the
        # expulsion site; existing tracks are never affected.
        self._squatter_cooldown: deque = deque(maxlen=96)
        self._last_ball_position: Optional[List[float]] = None
        # Recent ball sightings (x, y), for the server vote -- see
        # _filter_serve_zone_candidates.
        self._ball_history: deque = deque(maxlen=12)
        self.coast_vertical_damping = max(0.0, min(1.0, coast_vertical_damping))

        self.logger = logging.getLogger(__name__)

    def _log_assignment(self, path: str, tid: int, detection: Dict[str, Any]) -> None:
        """Record one assignment (path, frame, id, foot-in-court) when auditing."""
        if not self.debug_assignments:
            return
        foot_in_court = None
        if self.court_calibration is not None and getattr(
            self.court_calibration, "is_calibrated", False
        ):
            foot = self.court_calibration.foot_point(detection["bbox"])
            foot_in_court = self.court_calibration.is_point_in_court((float(foot[0]), float(foot[1])))
        self.assignment_log.append({
            "frame": self.frame_count,
            "path": path,
            "track_id": tid,
            "foot_in_court": foot_in_court,
        })

    def _detection_in_court(self, detection: Dict[str, Any]) -> Optional[bool]:
        """Strict foot-in-court test for a detection. None when uncalibrated
        (no gating possible -- behave as before)."""
        if self.court_calibration is None or not getattr(
            self.court_calibration, "is_calibrated", False
        ):
            return None
        foot = self.court_calibration.foot_point(detection["bbox"])
        return bool(
            self.court_calibration.is_point_in_court((float(foot[0]), float(foot[1])))
        )

    def _detection_in_serve_zone(self, detection: Dict[str, Any]) -> Optional[bool]:
        """Serve-zone test for a detection (see CourtCalibration.is_in_serve_zone).
        None when the court offers no serve-zone geometry (uncalibrated or a
        test double) -- then nothing is ever in the zone."""
        court = self.court_calibration
        fn = getattr(court, "is_in_serve_zone", None)
        if court is None or not getattr(court, "is_calibrated", False) or fn is None:
            return None
        foot = court.foot_point(detection["bbox"])
        return fn(
            (float(foot[0]), float(foot[1])),
            depth_m=self.serve_zone_depth_m,
            side_margin_m=self.serve_zone_side_margin_m,
        ) is not None

    def _detection_world_foot(self, detection: Dict[str, Any]) -> Optional[Tuple[float, float]]:
        """World (ground-plane, metres) position of a detection's foot.
        None when the court offers no ground homography (uncalibrated or a
        test double without image_to_world)."""
        court = self.court_calibration
        fn = getattr(court, "image_to_world", None)
        if court is None or not getattr(court, "is_calibrated", False) or fn is None:
            return None
        return fn(court.foot_point(detection["bbox"]))

    def _in_squatter_cooldown(self, detection: Dict[str, Any]) -> bool:
        """True when the detection's world foot sits within
        squatter_cooldown_radius_m of a sampled position from an expired
        squatter. Blocks NEW-track admission -- deliberately INCLUDING
        strictly in-court candidates: the straddler's re-admission attempts
        read 7.84-7.99 m, just inside the sideline. Existing tracks never hit
        this path (they associate, not admit)."""
        if not self._squatter_cooldown:
            return False
        world = self._detection_world_foot(detection)
        if world is None:
            return False
        r2 = self.squatter_cooldown_radius_m ** 2
        return any(
            (world[0] - cx) ** 2 + (world[1] - cy) ** 2 <= r2
            for cx, cy in self._squatter_cooldown
        )

    def _track_admission_ok(self, detection: Dict[str, Any]) -> bool:
        """May this detection ever become a NEW track? Foot strictly in court,
        or (server admission) in a serve zone -- but never within the squatter
        cooldown radius of an expired sideline straddler's sampled positions.
        Established tracks never hit this path -- they associate via
        Hungarian/IoU/gallery, which have their own (stricter for off-court)
        rules."""
        if self._in_squatter_cooldown(detection):
            return False
        if self._detection_in_court(detection) is not False:
            return True
        return bool(self.serve_zone_enabled and self._detection_in_serve_zone(detection))

    def _may_feed_track(self, track: Dict[str, Any], detection: Dict[str, Any]) -> bool:
        """Bystander-hijack guard for ONGOING assignment (new tracks have their
        own admission test in _create_track).

        An out-of-court detection may continue a track while identity is still
        OBSERVED, not inferred:
          * within the grace window of the track's last in-court sighting
            (a player who just stepped out, e.g. a server behind the baseline),
            OR
          * the track was matched by a detection on the previous frame too --
            continuous out-of-court tracking (the player walked out and keeps
            being seen; there is no observation gap to hijack through), but
            only for ``off_court_hold_frames`` since the last IN-COURT
            sighting: identity observed out of court is borrowable, not
            owned, and a person never seen in court is not holding a player
            slot (entreno_2's right-side bystander, seeded while straddling
            the sideline, was continuously detected and fed for 415 frames).
        After a detection gap the identity is inferred, so re-feeding requires
        an in-court sighting: a bystander standing just off-court can then
        neither inherit a coasting/dormant track nor keep one alive. Both
        hijack vectors observed on entreno_1 (hungarian onto a coasting track,
        gallery_appearance onto a dormant id) started from exactly such a gap.
        """
        in_court = self._detection_in_court(detection)
        if in_court is None or in_court:
            return True
        if track.get("last_matched_frame") == self.frame_count - 1:
            # Continuous observation -- no gap to hijack through, but the
            # hold horizon still applies (see docstring).
            last_in = track.get("last_in_court_frame")
            if last_in is None:
                return True  # never in court: zone-seed rules govern (trial expiry)
            return (self.frame_count - last_in) <= self.off_court_hold_frames
        last_in = track.get("last_in_court_frame")
        if last_in is None:
            # Never in court yet: a serve-zone seed. Identity may continue
            # out-of-court only from the serve zone itself (where it was
            # admitted) -- not from an arbitrary gap-filling bystander.
            return bool(self._detection_in_serve_zone(detection))
        return (self.frame_count - last_in) <= self.off_court_grace_frames

    def update(
        self,
        detections: List[Dict[str, Any]],
        frame: Optional[np.ndarray] = None,
        *,
        strict_detections: Optional[List[Dict[str, Any]]] = None,
        ball_active: bool = False,
        n_court_det: Optional[int] = None,
        ball_position: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Update tracker with new detections.

        Args:
            detections: Player detections within the PLAY AREA (court + margin)
                -- the wider set, so an established track can match a player who
                has stepped off-court (server behind baseline, chaser).
            frame: Current video frame (needed for appearance features).
            strict_detections: Foot-in-court detections only -- the admission
                pool for NEW tracks and the persistence source for the bootstrap.
                If None (legacy callers), falls back to `detections`.
            ball_active: True when the ball is in play this frame -- gates the
                bootstrap to skip the warmup opening.
            n_court_det: Strict in-court count (live/dead-ball signal); stored
                for diagnostics, not used in association.
            ball_position: Center of the top-1 ball detection this frame, if
                any. Anchors serve-zone admission to the likely server (see
                serve_zone_ball_anchor_px); None keeps the previous
                confidence-order behaviour.

        Returns:
            List of tracked players with stable 'track_id' and 'team' fields.
        """
        self._current_frame = frame
        self.frame_count += 1
        self._last_n_court_det = n_court_det
        self._last_ball_position = list(ball_position) if ball_position else None
        if self._last_ball_position:
            self._ball_history.append(
                (float(self._last_ball_position[0]), float(self._last_ball_position[1]))
            )
        # Admission/persistence reference: strict foot-in-court set, falling back
        # to all detections for legacy callers (single-zone behaviour).
        self._last_strict_detections = (
            strict_detections if strict_detections is not None else detections
        )

        if not self._initialized:
            return self._stamp_identities(
                self._bootstrap_phase(detections, self._last_strict_detections, ball_active)
            )

        if not detections:
            return self._stamp_identities(self._handle_no_detections())

        return self._stamp_identities(self._associate_detections(detections))

    # --- Initialization ---

    @staticmethod
    def _iou(b1: List[float], b2: List[float]) -> float:
        """Intersection-over-union of two [x1,y1,x2,y2] boxes."""
        x1 = max(b1[0], b2[0]); y1 = max(b1[1], b2[1])
        x2 = min(b1[2], b2[2]); y2 = min(b1[3], b2[3])
        inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        a1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
        a2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
        union = a1 + a2 - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _deduplicate_detections(detections: List[Dict[str, Any]], iou_threshold: float = 0.4) -> List[Dict[str, Any]]:
        """Remove overlapping detections, keeping the higher confidence one."""
        if len(detections) <= 1:
            return detections

        # Sort by confidence descending
        dets = sorted(detections, key=lambda d: d.get("confidence", 0), reverse=True)
        keep = []
        for det in dets:
            b1 = det["bbox"]
            is_dup = False
            for kept in keep:
                b2 = kept["bbox"]
                # Compute IoU
                x1 = max(b1[0], b2[0])
                y1 = max(b1[1], b2[1])
                x2 = min(b1[2], b2[2])
                y2 = min(b1[3], b2[3])
                inter = max(0, x2 - x1) * max(0, y2 - y1)
                a1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
                a2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
                union = a1 + a2 - inter
                iou = inter / union if union > 0 else 0
                if iou > iou_threshold:
                    is_dup = True
                    break
            if not is_dup:
                keep.append(det)
        return keep

    def _bootstrap_phase(
        self,
        detections: List[Dict[str, Any]],
        strict_detections: List[Dict[str, Any]],
        ball_active: bool,
    ) -> List[Dict[str, Any]]:
        """Skip the warmup; lock the 4-roster at the first reliable rally.

        Persistence-on-court decides WHO the 4 are: only foot-in-court
        (`strict_detections`) centers accumulate, so an off-court bystander can
        never bootstrap into the roster. The ball-active gate skips the opening
        warmup where players are not in position / partly off-frame. Falls back
        to locking with whatever is available at `bootstrap_max_wait` so a missed
        ball signal never blocks the whole video.
        """
        detections = self._deduplicate_detections(detections)
        strict = (
            self._deduplicate_detections(strict_detections)
            if strict_detections is not None
            else detections
        )

        # Accumulate persistence only on qualifying (ball-active) frames.
        qualify = bool(ball_active) or (not self.bootstrap_ball_required)
        if qualify:
            self._bootstrap_buffer.append(strict)
            self._bootstrap_qualifying += 1

        ready = (
            self._bootstrap_qualifying >= self.bootstrap_min_window
            and sum(len(f) for f in self._bootstrap_buffer) >= self.max_players
        )
        timed_out = self.frame_count >= self.bootstrap_max_wait

        if not (ready or timed_out):
            return self._temp_track_output(detections)

        # Lock the roster, then run a normal association for this frame.
        qualifying = self._bootstrap_qualifying
        self._lock_roster_from_buffer()
        self._initialized = True
        self._bootstrap_buffer = []
        self._bootstrap_qualifying = 0
        self.logger.info(
            f"Bootstrap locked {len(self.tracks)} tracks at frame {self.frame_count} "
            f"(qualifying={qualifying}, ball_active={ball_active}, "
            f"timed_out={timed_out})"
        )
        if detections:
            return self._associate_detections(detections)
        return self._get_current_tracks()

    def _lock_roster_from_buffer(self) -> None:
        """Create exactly max_players tracks from the accumulated on-court frames.

        K-means over the buffered foot-in-court centers finds the most
        persistent positions; each cluster is seeded from its closest detection
        in the last buffered frame (a real bbox, so team assignment is sound).
        """
        frames = self._bootstrap_buffer
        all_centers = [det["center"] for frame_dets in frames for det in frame_dets]

        if len(all_centers) < self.max_players:
            # Not enough persistence yet (e.g. the ball signal never fired, so
            # the buffer only has a frame or two). Seed from the most recent
            # on-court detections so the tracker is never left empty -- note
            # _associate_detections returns early when there are zero tracks, so
            # a failed seed here would leave the tracker stuck for the video.
            seed = frames[-1] if frames else self._last_strict_detections
            for det in seed:
                self._create_track(det, require_court_admission=False)
            return

        centers_arr = np.array(all_centers, dtype=np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1.0)
        k = min(self.max_players, len(centers_arr))
        _, labels, cluster_centers = cv2.kmeans(
            centers_arr, k, None, criteria, 10, cv2.KMEANS_PP_CENTERS
        )

        # Rank clusters by persistence (point count) -- the 4 most persistent
        # on-court positions are the players; sporadic bystanders fall out.
        cluster_counts = np.bincount(labels.flatten(), minlength=k)
        top_clusters = np.argsort(-cluster_counts)[: self.max_players]

        last_frame_dets = frames[-1] if frames else []
        locked_boxes: List[List[float]] = []
        for cluster_idx in top_clusters:
            center = cluster_centers[cluster_idx]
            best_det, best_dist = None, float("inf")
            for det in last_frame_dets:
                d = np.linalg.norm(np.array(det["center"]) - center)
                if d < best_dist:
                    best_dist, best_det = d, det

            if best_det is None:
                # Synthetic seed around the cluster centre (last resort).
                best_det = {
                    "bbox": [int(center[0] - 30), int(center[1] - 60),
                             int(center[0] + 30), int(center[1] + 60)],
                    "center": center.tolist(),
                    "confidence": 0.5,
                }
            # k-means is forced to k=max_players even when fewer people are on
            # court, which splits one person into two clusters ~10px apart. Both
            # clusters then resolve to the SAME seed detection; seeding both
            # inflates the roster with a phantom that never matches, retires
            # dormant, and blocks the real missing player (the server) from the
            # slot (observed on entreno_3: t3/t4 locked 10px apart, t4 never
            # matched once). Same stacking threshold as the create-loop.
            if any(self._iou(best_det["bbox"], lb) > 0.35 for lb in locked_boxes):
                self.logger.debug(
                    "Bootstrap: skipped duplicate seed (overlaps an already-locked player)"
                )
                continue
            if self._create_track(best_det, require_court_admission=False) >= 0:
                locked_boxes.append(best_det["bbox"])

        self.logger.info(
            f"Bootstrap: initialized {len(self.tracks)} tracks from "
            f"{len(frames)} qualifying frames"
        )

    def _temp_track_output(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """During bootstrap, return detections with temporary track IDs.

        Sorted by center-x so temp IDs 1..N stay spatially stable frame-to-frame
        (instead of shuffling by detection order) while we wait for the rally lock.
        """
        result = []
        ordered = sorted(
            detections[: self.max_players],
            key=lambda d: d.get("center", [0, 0])[0],
        )
        for i, det in enumerate(ordered):
            d = det.copy()
            d["track_id"] = i + 1
            d["team"] = None
            result.append(d)
        return result

    # --- Core association ---

    def _associate_detections(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Associate detections with existing tracks using Hungarian algorithm."""
        detections = self._deduplicate_detections(detections)
        self._expire_serve_zone_trials()
        self._expire_squatters()
        track_ids = list(self.tracks.keys())
        n_tracks = len(track_ids)
        n_dets = len(detections)

        if n_tracks == 0:
            return []

        # Build cost matrix: rows=tracks, cols=detections
        cost_matrix = np.full((n_tracks, n_dets), 1e6)

        for i, tid in enumerate(track_ids):
            track = self.tracks[tid]
            for j, det in enumerate(detections):
                cost = self._compute_assignment_cost(track, det)
                if cost is not None:
                    cost_matrix[i, j] = cost

        # Hungarian assignment
        row_indices, col_indices = linear_sum_assignment(cost_matrix)

        matched_tracks = set()
        matched_dets = set()
        tracked_players = []

        for row, col in zip(row_indices, col_indices):
            if cost_matrix[row, col] >= 1e6:
                continue
            tid = track_ids[row]
            det = detections[col]
            self._log_assignment("hungarian", tid, det)
            self._update_track(tid, det)
            matched_tracks.add(tid)
            matched_dets.add(col)

            out = det.copy()
            out["track_id"] = tid
            out["team"] = self._get_smoothed_team(tid)
            tracked_players.append(out)

        # Second pass -- re-acquisition: a leftover detection that overlaps a
        # still-unmatched track is almost certainly that same player (the
        # Hungarian pass missed it on appearance/cost). Re-attach it to the SAME
        # id instead of leaving the track to coast or spawning a duplicate. This
        # is the main defence against ID churn and stacked boxes under occlusion.
        for j in range(n_dets):
            if j in matched_dets:
                continue
            det = detections[j]
            best_tid, best_iou = None, 0.35
            for tid in track_ids:
                if tid in matched_tracks:
                    continue
                ov = self._iou(det["bbox"], self.tracks[tid]["bbox"])
                if ov > best_iou:
                    best_iou, best_tid = ov, tid
            if best_tid is not None and self._may_feed_track(self.tracks[best_tid], det):
                self._log_assignment("iou_reattach", best_tid, det)
                self._update_track(best_tid, det)
                matched_tracks.add(best_tid)
                matched_dets.add(j)
                out = det.copy()
                out["track_id"] = best_tid
                out["team"] = self._get_smoothed_team(best_tid)
                tracked_players.append(out)

        matched_boxes = [p["bbox"] for p in tracked_players]

        # Unmatched tracks: coast with a predicted box -- but suppress a ghost
        # that sits on top of a player already matched to another id (a duplicate).
        for tid in track_ids:
            if tid in matched_tracks:
                continue
            self.disappeared[tid] = self.disappeared.get(tid, 0) + 1
            if self.disappeared[tid] > self.max_disappeared:
                self._retire_track(tid)
                continue
            track = self.tracks.get(tid)
            if not track:
                continue
            # Coast: extrapolate the box along its (decaying) velocity for up to
            # coast_extrapolation_cap frames so a moving player who re-emerges is
            # still gated to the SAME id. Beyond the cap the box freezes.
            if self.disappeared[tid] <= self.coast_extrapolation_cap:
                self._coast_step(track)
            # Suppress a coasting ghost that now sits on a player matched to another
            # id (uses the extrapolated box -- preserves 42e35dd duplicate suppression).
            if any(self._iou(track["bbox"], mb) > 0.4 for mb in matched_boxes):
                continue
            tracked_players.append({
                "bbox": track["bbox"],
                "center": track["center"],
                "confidence": max(0.1, track["confidence"] - 0.05),
                "track_id": tid,
                "team": self._get_smoothed_team(tid),
                "predicted": True,
            })

        # Gallery re-acquisition (phase 1b): an unmatched detection that lines up
        # with a DORMANT player's last trajectory restores that player's ORIGINAL
        # id. This is what holds identity across gaps longer than max_disappeared
        # (long occlusions; the backbone of surviving side changes once continuity
        # is also maintained through the walk-around). Runs after IoU
        # re-acquisition and the coast/retire loop, before new-track creation.
        if self.gallery_enabled and self.gallery:
            for _j, _gid, out in self._reacquire_from_gallery(
                detections, matched_dets, matched_tracks
            ):
                tracked_players.append(out)
                matched_boxes.append(out["bbox"])

        # Unmatched detections: create a new track only if there is room AND the
        # detection is not already covered by an existing track (never stack two
        # ids on one player). If every slot is reserved (active + dormant), first
        # reclaim the stalest dormant id past its min-hold so an on-court player
        # is tracked rather than dropped (the trap avoidance). Recent retirements
        # are protected so a genuinely-occluded player's id isn't stolen.
        existing_boxes = [t["bbox"] for t in self.tracks.values()]
        candidates: List[Tuple[int, Dict[str, Any]]] = []
        for j in range(n_dets):
            if j in matched_dets:
                continue
            det = detections[j]
            if any(self._iou(det["bbox"], eb) > 0.35 for eb in existing_boxes):
                continue
            # Admission BEFORE eviction: a detection that could never pass the
            # new-track gate must not force a dormant id out of its slot only
            # to then be rejected itself.
            if not self._track_admission_ok(det):
                continue
            candidates.append((j, det))

        candidates = self._filter_serve_zone_candidates(candidates)

        for j, det in candidates:
            # Re-check coverage: a candidate may overlap a track created from
            # an earlier candidate THIS frame (never stack two ids on one
            # player -- the collection-time check cannot see later creations).
            if any(self._iou(det["bbox"], eb) > 0.35 for eb in existing_boxes):
                continue
            if len(self.tracks) + len(self.gallery) >= self.max_players:
                if not (self.gallery_enabled and self._evict_stalest_dormant()):
                    continue
            tid = self._create_track(det)
            if tid < 0:
                continue
            self._log_assignment("new_track", tid, det)
            existing_boxes.append(det["bbox"])
            out = det.copy()
            out["track_id"] = tid
            out["team"] = self._get_smoothed_team(tid)
            tracked_players.append(out)

        return tracked_players

    def _ball_hold_votes(self, det: Dict[str, Any]) -> int:
        """Recent ball sightings that sit in det's column and above its waist.

        A ball held at the chest or tossed above the head lands inside the
        holder's x-span, above the waist, frame after frame. A spare ball
        lying on the sand near a bystander can ALSO land in their column
        (perspective: the bystander is close to the camera, so sand behind
        them projects at chest height -- entreno_5's spare at (633,794) voted
        6 times for the bystander), which is why admission alone is not
        enough: the contested-server swap below re-adjudicates once the ball
        evidence moves.
        """
        x1, y1, x2, y2 = det["bbox"]
        waist = y1 + 0.6 * (y2 - y1)
        return sum(
            1 for bx, by in self._ball_history if x1 <= bx <= x2 and by < waist
        )

    def _ball_in_column_now(self, bbox: List[float], window: int = 3) -> bool:
        """Is the ball in bbox's column (x-span, above the waist) in the last
        `window` sightings? The NOW-test for who holds the ball, immune to
        stale history (the 12-frame vote window deliberately is not)."""
        x1, y1, x2, y2 = bbox
        waist = y1 + 0.6 * (y2 - y1)
        recent = list(self._ball_history)[-window:]
        return any(x1 <= bx <= x2 and by < waist for bx, by in recent)

    def _filter_serve_zone_candidates(
        self, candidates: List[Tuple[int, Dict[str, Any]]]
    ) -> List[Tuple[int, Dict[str, Any]]]:
        """Order/restrict serve-zone NEW-track candidates.

        Two guards, both from entreno_5 (two people standing in serve zones;
        the stationary bystander out-confidenced the real server and held the
        4th slot for the whole video):
          * cooldown -- a trial-expired squatter's bbox blocks re-admission
            from the zone (in-court admission is never blocked);
          * server vote -- when recent ball sightings exist, a zone candidate
            is only admissible with >= serve_zone_ball_votes sightings inside
            its column above the waist (the server holds/tosses the ball; a
            bystander does not). With a live ball history but no qualifying
            candidate, zone admission DEFERS this frame -- nobody in the zone
            is serving. With no ball history at all (ball never seen), the
            previous confidence-order behaviour stands.

        In-court candidates pass through untouched, in their original order.
        """
        keep: List[Tuple[int, Dict[str, Any]]] = []
        serve_zone: List[Tuple[int, Dict[str, Any]]] = []
        for item in candidates:
            det = item[1]
            if self._detection_in_court(det) is False and self._detection_in_serve_zone(det):
                serve_zone.append(item)
            else:
                keep.append(item)

        if not serve_zone:
            return keep

        if self._ball_history:
            best = max(serve_zone, key=lambda item: self._ball_hold_votes(item[1]))
            if self._ball_hold_votes(best[1]) >= self.serve_zone_ball_votes:
                self._reassign_contested_server(best[1])
                serve_zone = [best]
            else:
                self.logger.debug(
                    "Serve-zone admission deferred: no candidate holds the ball"
                )
                serve_zone = []

        for item in serve_zone:
            det = item[1]
            if any(self._iou(det["bbox"], cb) > 0.4 for cb in self._serve_zone_cooldown):
                self.logger.debug("Serve-zone admission blocked: trial-expired squatter")
                continue
            keep.append(item)
        return keep

    def _reassign_contested_server(self, winner: Dict[str, Any]) -> None:
        """Swap out a serve-zone seed that stopped holding the ball.

        entreno_5: a spare ball on the sand voted the bystander in as
        "server" on the admission frame; three frames later the spare was
        static-suppressed and the toss ball sat over the REAL server. The
        seed's own column had gone quiet while another candidate had the
        votes -- at that point the admission was provably wrong. Remove the
        seed (hard, with cooldown, exactly like a trial expiry) so the
        create loop can admit the true server into the freed slot.

        Fires only while the seed has never entered the court (a serving
        player who walked in is a normal track and untouchable here) and the
        ball is NOT in the seed's column right now.
        """
        for tid in [
            t for t, tr in self.tracks.items()
            if tr.get("last_in_court_frame") is None
        ]:
            seed = self.tracks[tid]
            if self._iou(seed["bbox"], winner["bbox"]) > 0.4:
                continue  # the winner IS the seed's person, already tracked
            if self._ball_in_column_now(seed["bbox"]):
                continue  # seed still holds the ball -- no contest
            self.tracks.pop(tid)
            self.disappeared.pop(tid, None)
            self._serve_zone_cooldown.append(list(seed["bbox"]))
            self.logger.info(
                f"Serve-zone seed {tid} reassigned: ball left its column for "
                f"another candidate; slot handed to the ball holder"
            )

    def _compute_assignment_cost(
        self, track: Dict[str, Any], detection: Dict[str, Any]
    ) -> Optional[float]:
        """Compute cost of assigning a detection to a track.

        Returns None if assignment is invalid (too far or too fast).
        """
        track_center = np.array(track["center"])
        det_center = np.array(detection["center"])

        # Bystander-hijack guard: an out-of-court detection can only continue
        # a recently-in-court track (see _may_feed_track).
        if not self._may_feed_track(track, detection):
            return None

        # Gate on the actual gap to the last known position.
        distance = float(np.linalg.norm(track_center - det_center))
        if distance > self.max_distance:
            return None

        # Rank by the gap to the MOTION-PREDICTED position (constant velocity).
        # Anticipating motion is what keeps crossing/converging players from
        # swapping IDs -- the detection that continues a track's trajectory wins.
        predicted = track_center + np.array(track.get("velocity", [0.0, 0.0]))
        pred_distance = float(np.linalg.norm(predicted - det_center))

        # Appearance cost (ensemble signature similarity -- phase 1c). When the
        # track has a real signature and the detection looks very different AND
        # is far away, reject (blocks appearance-driven ID swaps).
        appearance_cost = 0.0
        if self._current_frame is not None:
            similarity = self._signature_similarity(track, detection)
            appearance_cost = 1.0 - similarity  # 0=identical, 1=different
            if (
                track.get("histogram") is not None
                and similarity < 0.15
                and pred_distance > 0.35 * self.max_distance
            ):
                return None

        # Combined cost
        cost = (1.0 - self.appearance_weight) * pred_distance + self.appearance_weight * appearance_cost * self.max_distance
        # In-court preference (see off_court_cost_penalty_px): an out-of-court
        # detection may CONTINUE a track (allowance rules live in
        # _may_feed_track), but it must never WIN a track whose own player is
        # detected in court the same frame. Only a court detection that is
        # in-gate for this track outranks the off-court one; with no in-court
        # option the off-court feeding proceeds exactly as before (the penalty
        # is far below the 1e6 invalid sentinel, so Hungarian still prefers
        # any feasible chain over leaving a track unmatched).
        if self._detection_in_court(detection) is False:
            cost += self.off_court_cost_penalty_px
        return cost

    # --- Appearance features ---

    def _compute_histogram(self, bbox: List[float]) -> Optional[np.ndarray]:
        """Compute HSV color histogram of the torso region within a bbox."""
        if self._current_frame is None:
            return None

        h, w = self._current_frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return None

        # Torso = middle third vertically
        box_h = y2 - y1
        torso_y1 = y1 + box_h // 4
        torso_y2 = y1 + 3 * box_h // 4
        crop = self._current_frame[torso_y1:torso_y2, x1:x2]

        if crop.size == 0:
            return None

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [18, 8], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist

    def _compute_head_histogram(self, bbox: List[float]) -> Optional[np.ndarray]:
        """HSV histogram of the top ~20% of a bbox (hair/hat region).

        A uniform-independent-ish channel that helps tell partners apart even
        when their torsos share a jersey colour (phase 1c).
        """
        if self._current_frame is None:
            return None
        h, w = self._current_frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return None
        box_h = y2 - y1
        head_y2 = y1 + max(1, box_h // 5)
        crop = self._current_frame[y1:head_y2, x1:x2]
        if crop.size == 0:
            return None
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [18, 8], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist

    # --- Track management ---

    def _create_track(
        self, detection: Dict[str, Any], require_court_admission: bool = True
    ) -> int:
        """Create a new track.

        Two continuity-first safeguards (see plan "two-zone policy" + "exactly 4"):
          * Admission gate: a brand-new track must start with a foot inside the
            STRICT court, so an off-court bystander can never bootstrap in. The
            one exception is the serve zone (just behind a baseline): the
            serving player stands off-court at video/rally start, and a
            serve-zone detection may open a track when a slot is free.
            Established tracks roaming the play area never hit this path (they
            match via the Hungarian pass, not creation). Skipped for bootstrap
            seeds (which already come from the foot-in-court set) and when no
            court calibration is available.
          * Active+dormant cap: counts active tracks AND the dormant gallery, so
            a dormant (lost-but-not-forgotten) id cannot be recycled onto a new
            player.

        Args:
            detection: Detection dict with bbox, center, confidence.
            require_court_admission: If True, reject detections whose foot is
                outside the strict court AND outside the serve zones (the
                bystander guard for new tracks).
        """
        serve_zone_seed = False
        if (
            require_court_admission
            and self.court_calibration is not None
            and getattr(self.court_calibration, "is_calibrated", False)
        ):
            foot = self.court_calibration.foot_point(detection["bbox"])
            if not self.court_calibration.is_point_in_court(foot):
                serve_zone_seed = bool(
                    self.serve_zone_enabled and self._detection_in_serve_zone(detection)
                )
                if not serve_zone_seed:
                    self.logger.debug("Reject new track: foot outside court (bystander guard)")
                    return -1

        committed = len(self.tracks) + len(self.gallery)
        if committed >= self.max_players:
            self.logger.debug("Max players reached (active+dormant), not creating new track")
            return -1

        # Recycle IDs: pick the lowest unused ID in 1..max_players that is neither
        # active nor dormant (a dormant id is reserved for its original player).
        available = sorted(
            set(range(1, self.max_players + 1))
            - set(self.tracks.keys())
            - set(self.gallery.keys())
        )
        if not available:
            self.logger.debug("No available IDs in 1..max_players range")
            return -1
        tid = available[0]

        hist = self._compute_histogram(detection["bbox"]) if self._current_frame is not None else None
        head_hist = self._compute_head_histogram(detection["bbox"]) if self._current_frame is not None else None
        world_h: deque = deque(maxlen=self.signature_height_smoothing)
        world_w: deque = deque(maxlen=self.signature_height_smoothing)
        if self.court_calibration is not None:
            size = self.court_calibration.world_body_size(detection["bbox"])
            if size:
                world_h.append(size["world_height"])
                world_w.append(size["world_width"])
        # Team is derived per-frame from foot position (side of the midcourt line,
        # per project spec) and smoothed over a vote window -- NOT locked at
        # creation. Seed the window with the creation-time reading.
        team = self._get_team_from_calibration(detection["bbox"])
        team_votes: deque = deque(maxlen=self.team_vote_window)
        if team is not None:
            team_votes.append(team)

        self.tracks[tid] = {
            "bbox": detection["bbox"],
            "center": detection["center"],
            "confidence": detection["confidence"],
            "history": [detection["center"]],
            "velocity": [0.0, 0.0],
            "histogram": hist,
            "head_histogram": head_hist,
            "world_height_samples": world_h,
            "world_width_samples": world_w,
            "team_votes": team_votes,
            # A serve-zone seed starts OFF-court: identity is admitted behind
            # the baseline, so the off-court grace window must not count from
            # here -- it opens at the first real in-court sighting (None means
            # never-in-court-yet, see _may_feed_track).
            "last_in_court_frame": None if serve_zone_seed else self.frame_count,
            "last_matched_frame": self.frame_count,
            "created_frame": self.frame_count,
            # Squatter-review counters (real feedings only, incremented in
            # _update_track -- ghost/coast frames never dilute the in-court
            # fraction). Bootstrap seeds start at zero.
            "fed_frames": 0,
            "in_court_fed_frames": 0,
            "foot_world_samples": deque(maxlen=self._SQUATTER_SAMPLE_MAXLEN),
        }
        self.disappeared[tid] = 0
        self.logger.debug(f"Created track {tid}")
        self._maybe_assign_label(tid, detection)
        return tid

    def _expire_serve_zone_trials(self) -> None:
        """Hard-remove serve-zone seeds that never entered the court within
        serve_zone_trial_frames.

        A stationary serve-zone bystander is continuously detected, so neither
        the off-court grace nor retirement ever fires and it holds a roster
        slot forever (observed on entreno_5: a bottom-left bystander kept the
        4th slot for the whole video while the real server went untracked).
        NOT retired to the gallery -- a never-in-court track was never
        validated as a player, so its id frees immediately. The last bbox goes
        on the cooldown list so the same person is not re-admitted from the
        zone right away; in-court admission is unaffected (if they ever step
        in, they are tracked like anyone else).
        """
        expired = [
            tid for tid, tr in self.tracks.items()
            if tr.get("last_in_court_frame") is None
            and self.frame_count - tr.get("created_frame", 0) > self.serve_zone_trial_frames
        ]
        for tid in expired:
            track = self.tracks.pop(tid)
            self.disappeared.pop(tid, None)
            self._track_labels.pop(tid, None)
            self._serve_zone_cooldown.append(list(track.get("bbox", [0, 0, 0, 0])))
            self.logger.info(
                f"Serve-zone trial expired for track {tid}: never entered the "
                f"court in {self.frame_count - track.get('created_frame', 0)} "
                f"frames, slot freed"
            )

    def _expire_squatters(self) -> None:
        """Expire sideline straddlers: tracks whose LIFETIME feeding has mostly
        happened out of court, once they are old enough for the fraction to be
        meaningful (entreno_7: a bystander seeds a track while straddling the
        sideline, reads "in court" for a dense early run at 7.87-7.99 m, then
        squats a roster slot for 400+ frames while the real 4th player waits).

        Strict admission cannot refuse them (the seed reads in court); the
        off-court hold horizon only stops CONTINUOUS feeding and its expiry is
        a normal retire -- which the gallery then undoes by re-acquiring the
        same id onto whoever stands near the old position (e7 f263: the real
        4th player colonizes the squatter's id). The review is the local
        signal that fires where the others cannot.

        Conditions (all required): age >= squatter_review_frames,
        fed_frames >= squatter_min_fed_frames, and lifetime
        in_court_fed/fed < squatter_min_in_court_frac. Counters count REAL
        feedings only (ghost/coast frames never dilute the fraction). No-op
        without a calibrated court. Expiry is to the gallery with a
        `squatter` flag -- NOT a hard-remove: on match footage a real player
        off-court between points can look squatter-like, and the flagged
        entry keeps their id as a fail-safe; the flag blocks every restore
        path and makes the entry immediately evictable for a real candidate.
        The expelled track's sampled world foot positions go on the admission
        cooldown so the same straddler cannot re-seed nearby.
        """
        if not self.squatter_enabled:
            return
        if self.court_calibration is None or not getattr(
            self.court_calibration, "is_calibrated", False
        ):
            return  # no ground plane -> no in-court fraction -> no-op
        expired = []
        for tid, tr in self.tracks.items():
            fed = tr.get("fed_frames", 0)
            if fed < self.squatter_min_fed_frames:
                continue
            if (
                self.frame_count - tr.get("created_frame", self.frame_count)
                < self.squatter_review_frames
            ):
                continue
            in_court = tr.get("in_court_fed_frames", 0)
            if in_court / fed >= self.squatter_min_in_court_frac:
                continue
            expired.append(tid)
        for tid in expired:
            self._expire_squatter(tid)

    def _expire_squatter(self, tid: int) -> None:
        """Expire one squatter track to the flagged gallery + admission cooldown."""
        track = self.tracks.pop(tid, None)
        if track is None:
            return
        self.disappeared.pop(tid, None)
        self._track_labels.pop(tid, None)
        samples = track.get("foot_world_samples") or []
        self._squatter_cooldown.extend(samples)
        self._retire_track_from(track, tid, squatter=True)
        self.logger.info(
            f"Squatter review expired track {tid}: in-court fed "
            f"{track.get('in_court_fed_frames', 0)}/{track.get('fed_frames', 0)} "
            f"after {self.frame_count - track.get('created_frame', self.frame_count)} "
            f"frames; id flagged in gallery, {len(samples)} foot samples on cooldown"
        )

    def _update_track(self, tid: int, detection: Dict[str, Any]) -> None:
        """Update an existing track with a new detection."""
        # Label retry (E1): a track created before its enrollment reference
        # freed up (e.g. admission before a wrong-player track retired) gets
        # another chance on every real feeding while unlabeled. Sticky once
        # assigned -- an assigned label is never reconsidered.
        if self._enrollment_refs and tid not in self._track_labels:
            self._maybe_assign_label(tid, detection)
        track = self.tracks[tid]
        old_center = track["center"]
        new_center = detection["center"]

        # Smooth velocity
        vx = new_center[0] - old_center[0]
        vy = new_center[1] - old_center[1]
        alpha = 0.3
        track["velocity"] = [
            alpha * vx + (1 - alpha) * track["velocity"][0],
            alpha * vy + (1 - alpha) * track["velocity"][1],
        ]

        track["bbox"] = detection["bbox"]
        track["center"] = new_center
        track["confidence"] = detection["confidence"]
        track["history"].append(new_center)

        # Bystander-hijack guard bookkeeping: remember when this track was last
        # fed by a detection (continuity) and last genuinely on the court (the
        # off-court grace window). Squatter-review counters count the same real
        # feedings -- ghost/coast frames never reach this method, so they
        # cannot dilute the lifetime in-court fraction.
        track["last_matched_frame"] = self.frame_count
        track["fed_frames"] = track.get("fed_frames", 0) + 1
        if self._detection_in_court(detection) is not False:
            track["last_in_court_frame"] = self.frame_count
            track["in_court_fed_frames"] = track.get("in_court_fed_frames", 0) + 1
        if track["fed_frames"] % self._SQUATTER_SAMPLE_EVERY == 0:
            world = self._detection_world_foot(detection)
            if world is not None:
                track.setdefault(
                    "foot_world_samples", deque(maxlen=self._SQUATTER_SAMPLE_MAXLEN)
                ).append((float(world[0]), float(world[1])))

        # Re-evaluate team from the new foot position and add it to the smoothing
        # window (majority vote read via _get_smoothed_team).
        team_vote = self._get_team_from_calibration(detection["bbox"])
        if team_vote is not None:
            track.setdefault("team_votes", deque(maxlen=self.team_vote_window)).append(team_vote)
        # Keep last 60 positions
        if len(track["history"]) > 60:
            track["history"] = track["history"][-60:]

        # Refresh the appearance ensemble (phase 1c): torso + head histograms
        # blend slowly (every 10 frames); a fresh world body-size sample is
        # pushed every update and median-smoothed for stability.
        if self._current_frame is not None and self.frame_count % 10 == 0:
            hist = self._compute_histogram(detection["bbox"])
            if hist is not None:
                if track.get("histogram") is not None:
                    track["histogram"] = 0.7 * track["histogram"] + 0.3 * hist
                else:
                    track["histogram"] = hist
            head_hist = self._compute_head_histogram(detection["bbox"])
            if head_hist is not None:
                if track.get("head_histogram") is not None:
                    track["head_histogram"] = 0.7 * track["head_histogram"] + 0.3 * head_hist
                else:
                    track["head_histogram"] = head_hist
        if self.court_calibration is not None:
            size = self.court_calibration.world_body_size(detection["bbox"])
            if size:
                track.setdefault(
                    "world_height_samples", deque(maxlen=self.signature_height_smoothing)
                ).append(size["world_height"])
                track.setdefault(
                    "world_width_samples", deque(maxlen=self.signature_height_smoothing)
                ).append(size["world_width"])

        self.disappeared[tid] = 0

    def _coast_step(self, track: Dict[str, Any]) -> Tuple[List[float], List[float]]:
        """Advance a lost track one frame by (decaying) constant velocity, in place.

        Shifts the stored bbox/center along the track's velocity and decays the
        velocity by coast_velocity_decay, so a player who is briefly missed (dive,
        net occlusion) keeps moving with their trajectory instead of freezing on a
        stale box. The UPWARD component is damped harder
        (coast_vertical_damping): a track lost mid-jump would otherwise ride its
        upward velocity for the whole coast window and drift the ghost box far
        above the player (players land near their takeoff spot), which also
        mis-sets the re-acquisition gate for the landing. Downward motion is
        court-axis running and coasts normally. Advancing the STORED position is
        what lets the re-emerging detection stay gated to the same id next frame
        (constant-velocity gate at _compute_assignment_cost). Box size is
        preserved and clamped to the frame.
        Returns the updated (bbox, center).
        """
        vx, vy = track.get("velocity", [0.0, 0.0])
        # Damp only UPWARD velocity: a jump is transient (it self-reverses at
        # the apex), so riding it coasts the box far above the player. Downward
        # velocity is legitimate ground-plane motion (running toward the camera
        # along the court axis is image-vertical) and must keep coasting --
        # damping it fragmented ids through long far-side occlusions.
        if vy < 0:
            vy = vy * self.coast_vertical_damping
        cx, cy = track["center"]
        w = track["bbox"][2] - track["bbox"][0]
        h = track["bbox"][3] - track["bbox"][1]
        ncx, ncy = cx + vx, cy + vy
        nb = [ncx - w / 2, ncy - h / 2, ncx + w / 2, ncy + h / 2]
        if self._current_frame is not None:
            fh, fw = self._current_frame.shape[:2]
            nb = [max(0.0, min(nb[0], fw - 1)), max(0.0, min(nb[1], fh - 1)),
                  max(0.0, min(nb[2], fw - 1)), max(0.0, min(nb[3], fh - 1))]
            ncx, ncy = (nb[0] + nb[2]) / 2, (nb[1] + nb[3]) / 2
        track["bbox"] = nb
        track["center"] = [ncx, ncy]
        # `vy` was already damped for this step; decay both for the next one.
        track["velocity"] = [vx * self.coast_velocity_decay, vy * self.coast_velocity_decay]
        return nb, [ncx, ncy]

    def _retire_track(self, tid: int, squatter: bool = False) -> None:
        """Retire a track to the dormant gallery (match-long) instead of deleting.

        The id is NEVER freed -- it stays reserved so a later re-acquisition
        restores the original id rather than recycling it onto a new player. The
        hard cap (_create_track) counts active + dormant, so a dormant id cannot
        be stolen by a bystander-driven new track either. `squatter=True` marks
        a squatter-review expiry: the entry keeps the id fail-safe but is
        skipped by every restore path and is immediately evictable.
        """
        track = self.tracks.pop(tid, None)
        self.disappeared.pop(tid, None)
        if track is not None:
            self._retire_track_from(track, tid, squatter=squatter)

    def _retire_track_from(
        self, track: Dict[str, Any], tid: int, squatter: bool = False
    ) -> None:
        """Build the gallery entry for an already-popped track (shared by normal
        retirement and squatter expiry)."""
        if self.gallery_enabled:
            self.gallery[tid] = {
                "bbox": track.get("bbox"),
                "center": track.get("center"),
                "velocity": track.get("velocity", [0.0, 0.0]),
                "histogram": track.get("histogram"),
                "head_histogram": track.get("head_histogram"),
                "world_height_samples": track.get("world_height_samples"),
                "world_width_samples": track.get("world_width_samples"),
                "team_votes": track.get("team_votes"),
                "retired_frame": self.frame_count,
                # Squatter-review bookkeeping rides along so a legitimate
                # restore resumes the lifetime counters (no fresh review
                # window) and age keeps accruing (no fresh amnesty).
                "created_frame": track.get("created_frame", self.frame_count),
                "fed_frames": track.get("fed_frames", 0),
                "in_court_fed_frames": track.get("in_court_fed_frames", 0),
                "foot_world_samples": track.get("foot_world_samples"),
                "squatter": squatter,
            }
            self.logger.debug(
                f"Retired track {tid} to gallery (size={len(self.gallery)})"
            )
        else:
            self.logger.debug(f"Removed track {tid}")

    def _evict_stalest_dormant(self) -> bool:
        """Reclaim a dormant id to free a slot for an on-court detection that
        would otherwise be dropped. Returns True if a slot was freed.

        Squatter-flagged entries go FIRST and bypass the min-hold entirely:
        their id must never block a real player (e7: the flagged straddler
        entry would otherwise keep slot 4 closed for gallery_evict_min_hold
        frames past the review tick). Normal entries stay protected for
        gallery_evict_min_hold_frames (they may still be re-acquired by
        position), then the stalest retirement is reclaimed -- least likely
        to re-acquire. Only ever called when the create-loop is actually
        forced (a detection needs the slot).
        """
        if not self.gallery:
            return False
        flagged = [
            (gid, g) for gid, g in self.gallery.items() if g.get("squatter")
        ]
        normal = [
            (gid, g)
            for gid, g in self.gallery.items()
            if not g.get("squatter")
            and self.frame_count - g.get("retired_frame", self.frame_count)
            >= self.gallery_evict_min_hold_frames
        ]
        if not (flagged or normal):
            return False
        pool = sorted(flagged, key=lambda kv: kv[1].get("retired_frame", 0)) + sorted(
            normal, key=lambda kv: kv[1].get("retired_frame", 0)
        )
        gid = pool[0][0]
        self.gallery.pop(gid, None)
        self._track_labels.pop(gid, None)
        self.logger.debug(
            f"Evicted stale dormant id {gid} to free a slot for a new detection"
        )
        return True

    def _reacquire_from_gallery(
        self,
        detections: List[Dict[str, Any]],
        matched_dets: set,
        matched_tracks: set,
    ) -> List[Tuple[int, int, Dict[str, Any]]]:
        """Match still-unmatched detections to dormant gallery tracks.

        Position+motion is the primary gate (continuity-first): a dormant track
        is searched near its last coasted position. The stored colour signature
        is a tie-break and flags the restore low-confidence when weak. Each
        detection and each gallery id is used at most once (greedy, nearest
        first). Restored tracks come back under their ORIGINAL id.
        """
        results: List[Tuple[int, int, Dict[str, Any]]] = []
        if not self.gallery:
            return results

        candidates = []
        for j in range(len(detections)):
            if j in matched_dets:
                continue
            # A restore re-admits the id -- same rule as a new track: the foot
            # must be strictly in court (a bystander just off-court must not be
            # able to resurrect a dormant id, position OR appearance matched).
            if self._detection_in_court(detections[j]) is False:
                continue
            dc = np.array(detections[j]["center"])
            for gid, g in self.gallery.items():
                if g.get("squatter"):
                    continue  # a squatter flag blocks every restore path
                dormant = max(0, self.frame_count - g.get("retired_frame", self.frame_count))
                base = np.array(g.get("center", [0.0, 0.0]))
                # Trust motion only over short gaps; clamp the extrapolation so a
                # long-dormant player is searched near their last known position
                # (a side-change reappearance on the far side won't match here --
                # that needs the appearance signature, phase 1c).
                vel = np.array(g.get("velocity", [0.0, 0.0]))
                steps = min(dormant, self.coast_extrapolation_cap)
                pred = base + vel * steps
                dist = float(np.linalg.norm(pred - dc))
                if dist <= self.gallery_reacquire_distance_px:
                    sim = self._signature_similarity(g, detections[j])
                    # sort key: nearest first, then highest similarity
                    candidates.append((dist, -sim, j, gid))

        candidates.sort()
        used_dets: set = set()
        used_gids: set = set()
        for dist, neg_sim, j, gid in candidates:
            if j in used_dets or gid in used_gids:
                continue
            g = self.gallery.pop(gid)
            sim = -neg_sim
            self._log_assignment("gallery_position", gid, detections[j])
            self._restore_track(gid, g, detections[j])
            matched_dets.add(j)
            matched_tracks.add(gid)
            used_dets.add(j)
            used_gids.add(gid)
            out = detections[j].copy()
            out["track_id"] = gid
            out["team"] = self._get_smoothed_team(gid)
            out["reacquired"] = True
            out["low_confidence"] = sim < self.gallery_reacquire_min_appearance
            results.append((j, gid, out))

        # Pass 2: appearance-based (phase 1c). A detection that did NOT line up
        # by position with any dormant id -- a player who reappeared elsewhere,
        # e.g. after walking around for a side change -- can still reclaim its
        # original id by ensemble signature, but only when the match is strong
        # (>= gallery_reacquire_appearance_min) to avoid stealing a same-colour
        # partner's id.
        if self.gallery:
            for j in range(len(detections)):
                if j in matched_dets or j in used_dets:
                    continue
                # Same re-admission rule as pass 1 (bystander-hijack guard).
                if self._detection_in_court(detections[j]) is False:
                    continue
                best_gid, best_sim = None, self.gallery_reacquire_appearance_min
                for gid in list(self.gallery.keys()):
                    if gid in used_gids or self.gallery[gid].get("squatter"):
                        continue  # a squatter flag blocks every restore path
                    sim = self._signature_similarity(self.gallery[gid], detections[j])
                    if sim > best_sim:
                        best_sim, best_gid = sim, gid
                if best_gid is not None:
                    g = self.gallery.pop(best_gid)
                    self._log_assignment("gallery_appearance", best_gid, detections[j])
                    self._restore_track(best_gid, g, detections[j])
                    matched_dets.add(j)
                    matched_tracks.add(best_gid)
                    used_dets.add(j)
                    used_gids.add(best_gid)
                    out = detections[j].copy()
                    out["track_id"] = best_gid
                    out["team"] = self._get_smoothed_team(best_gid)
                    out["reacquired"] = True
                    out["appearance_matched"] = True
                    out["low_confidence"] = False
                    results.append((j, best_gid, out))

        if results:
            self.logger.debug(
                f"Gallery re-acquired {len(results)} tracks: {[g for _, g, _ in results]}"
            )
        return results

    def _restore_track(
        self, gid: int, gallery_entry: Dict[str, Any], detection: Dict[str, Any]
    ) -> None:
        """Resurrect a dormant gallery track under its original id, then refresh
        it from the re-acquiring detection."""
        center = gallery_entry.get("center")
        self.tracks[gid] = {
            "bbox": gallery_entry.get("bbox"),
            "center": center,
            "confidence": gallery_entry.get("confidence", 0.5),
            "history": [center] if center is not None else [],
            "velocity": gallery_entry.get("velocity", [0.0, 0.0]),
            "histogram": gallery_entry.get("histogram"),
            "head_histogram": gallery_entry.get("head_histogram"),
            "world_height_samples": deque(
                gallery_entry.get("world_height_samples") or [],
                maxlen=self.signature_height_smoothing,
            ),
            "world_width_samples": deque(
                gallery_entry.get("world_width_samples") or [],
                maxlen=self.signature_height_smoothing,
            ),
            "team_votes": gallery_entry.get("team_votes") or deque(maxlen=self.team_vote_window),
            # Squatter-review bookkeeping reloads with the track: a legitimate
            # restore resumes the lifetime counters and the age clock -- no
            # fresh review window, no fresh amnesty.
            "created_frame": gallery_entry.get("created_frame", self.frame_count),
            "fed_frames": gallery_entry.get("fed_frames", 0),
            "in_court_fed_frames": gallery_entry.get("in_court_fed_frames", 0),
            "foot_world_samples": deque(
                gallery_entry.get("foot_world_samples") or [],
                maxlen=self._SQUATTER_SAMPLE_MAXLEN,
            ),
            # Restores are gated to in-court detections (bystander-hijack
            # guard), so the restored track counts as freshly on-court.
            "last_in_court_frame": self.frame_count,
            "last_matched_frame": self.frame_count,
        }
        self.disappeared[gid] = 0
        # Re-anchor the appearance signature to the current detection so future
        # gallery/association matches reflect where the player is now.
        if self._current_frame is not None:
            new_hist = self._compute_histogram(detection["bbox"])
            if new_hist is not None:
                old = gallery_entry.get("histogram")
                self.tracks[gid]["histogram"] = (
                    0.5 * old + 0.5 * new_hist if old is not None else new_hist
                )
        # Refresh bbox/center/velocity (histogram handled above).
        self._update_track(gid, detection)

    # Tolerances for the biometric channels of the ensemble signature. height:
    # metres difference at which two players score 0 height-similarity (~0.4m
    # spans most of the adult range, so that = "clearly different build"). ratio:
    # body h/w-ratio difference for 0 similarity.
    _SIG_HEIGHT_TOL_M = 0.4
    _SIG_RATIO_TOL = 1.0

    @staticmethod
    def _median(values) -> Optional[float]:
        if not values:
            return None
        return float(np.median(list(values)))

    def _track_ratio(self, track: Dict[str, Any]) -> Optional[float]:
        mh = self._median(track.get("world_height_samples"))
        mw = self._median(track.get("world_width_samples"))
        if mh is None or mw is None or mw <= 0:
            return None
        return mh / mw

    def _detection_signature(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """On-the-fly signature for a detection (compared against a track/gallery)."""
        sig: Dict[str, Any] = {
            "color": None, "head": None,
            "world_height": None, "world_width": None, "ratio": None,
        }
        if self._current_frame is not None:
            sig["color"] = self._compute_histogram(detection["bbox"])
            sig["head"] = self._compute_head_histogram(detection["bbox"])
        if self.court_calibration is not None:
            size = self.court_calibration.world_body_size(detection["bbox"])
            if size:
                sig["world_height"] = size["world_height"]
                sig["world_width"] = size["world_width"]
                sig["ratio"] = size["ratio"]
        return sig

    def _signature_similarity(
        self, track_or_gallery: Dict[str, Any], detection: Dict[str, Any]
    ) -> float:
        """Confidence-weighted ensemble similarity in [0,1]: torso colour +
        head/hair + relative body height + body proportions.

        Each channel contributes only when both sides have it (a channel is
        silently dropped when unavailable -- no frame, or too few samples).
        When nothing discriminates, returns 0 -- callers then defer to motion.
        """
        sig = self._detection_signature(detection)
        w = self.signature_weights
        sim_sum = 0.0
        total_w = 0.0

        if sig["color"] is not None and track_or_gallery.get("histogram") is not None:
            c = cv2.compareHist(track_or_gallery["histogram"], sig["color"], cv2.HISTCMP_CORREL)
            sim_sum += w["color"] * max(0.0, float(c))
            total_w += w["color"]
        if sig["head"] is not None and track_or_gallery.get("head_histogram") is not None:
            h = cv2.compareHist(track_or_gallery["head_histogram"], sig["head"], cv2.HISTCMP_CORREL)
            sim_sum += w["head"] * max(0.0, float(h))
            total_w += w["head"]
        th = self._median(track_or_gallery.get("world_height_samples"))
        if sig.get("world_height") is not None and th is not None:
            diff = abs(sig["world_height"] - th)
            sim_sum += w["height"] * max(0.0, 1.0 - diff / self._SIG_HEIGHT_TOL_M)
            total_w += w["height"]
        tr = self._track_ratio(track_or_gallery)
        if sig.get("ratio") is not None and tr is not None:
            diff = abs(sig["ratio"] - tr)
            sim_sum += w["proportions"] * max(0.0, 1.0 - diff / self._SIG_RATIO_TOL)
            total_w += w["proportions"]

        return float(sim_sum / total_w) if total_w > 0 else 0.0

    def _handle_no_detections(self) -> List[Dict[str, Any]]:
        """Handle frame with no detections."""
        result = []
        for tid in list(self.tracks.keys()):
            self.disappeared[tid] = self.disappeared.get(tid, 0) + 1
            if self.disappeared[tid] > self.max_disappeared:
                self._retire_track(tid)
            else:
                track = self.tracks[tid]
                if self.disappeared[tid] <= self.coast_extrapolation_cap:
                    self._coast_step(track)
                result.append({
                    "bbox": track["bbox"],
                    "center": track["center"],
                    "confidence": max(0.1, track["confidence"] - 0.05),
                    "track_id": tid,
                    "team": self._get_smoothed_team(tid),
                    "predicted": True,
                })
        return result

    # --- Team assignment ---

    def _get_team_from_calibration(self, bbox: List[float]) -> Optional[str]:
        """Get team from court calibration based on foot position. Used only at track creation."""
        if self.court_calibration is not None and hasattr(self.court_calibration, "get_team_for_bbox"):
            return self.court_calibration.get_team_for_bbox([int(v) for v in bbox])
        return None

    def _get_smoothed_team(self, tid: int) -> Optional[str]:
        """Team for a track: majority vote of recent foot-position readings.

        Team is the side of the midcourt line the feet fall on (project spec),
        smoothed over a window so a transient dive/step across the line does not
        flip the label. Recomputed every frame -- never locked at creation.
        """
        track = self.tracks.get(tid)
        if not track:
            return None
        votes = [t for t in track.get("team_votes", ()) if t is not None]
        if not votes:
            return None
        return Counter(votes).most_common(1)[0][0]

    def set_court_calibration(self, calibration) -> None:
        """Set or update court calibration for team assignment."""
        self.court_calibration = calibration

    # --- Enrollment labels (E1) ---

    def set_enrollment(self, references: Optional[List[Dict[str, Any]]]) -> None:
        """Store enrollment references for label assignment.

        The references (from PlayerEnrollment) carry the ensemble signature
        keys used by _signature_similarity, so each one can be scored against
        a live detection exactly like a track or gallery entry.
        """
        self._enrollment_refs = list(references or [])
        self._track_labels = {}
        if self._enrollment_refs:
            self.logger.info(
                "Enrollment active: %s", [r.get("label") for r in self._enrollment_refs]
            )

    @property
    def enrollment_active(self) -> bool:
        return bool(self._enrollment_refs)

    def label_for(self, track_id: int) -> Optional[str]:
        """Enrolled label (e.g. ``P1A``) for a track id, else None.

        Labels are sticky per tid for the life of the tracker, so this is
        safe to call for any emitted action keyed by track_id.
        """
        entry = self._track_labels.get(track_id)
        return entry[0] if entry else None

    def compute_enrollment_signature(
        self, frame: np.ndarray, bbox: List[float]
    ) -> Dict[str, Any]:
        """Public appearance signature for enrollment references.

        Same channels as the ensemble (torso/head histograms + ground-plane
        world sizes); used by PlayerEnrollment so the pre-pass and the
        in-stream signature can never drift apart.
        """
        saved = self._current_frame
        self._current_frame = frame
        try:
            hist = self._compute_histogram(bbox)
            head_hist = self._compute_head_histogram(bbox)
        finally:
            self._current_frame = saved
        world_height_samples: List[float] = []
        world_width_samples: List[float] = []
        if self.court_calibration is not None:
            size = self.court_calibration.world_body_size(bbox)
            if size:
                world_height_samples.append(size["world_height"])
                world_width_samples.append(size["world_width"])
        return {
            "histogram": hist,
            "head_histogram": head_hist,
            "world_height_samples": world_height_samples,
            "world_width_samples": world_width_samples,
        }

    def _maybe_assign_label(self, tid: int, detection: Dict[str, Any]) -> None:
        """Attach an enrollment label to an unlabeled track, if one fits.

        Greedy best-of-unclaimed: the reference with the highest ensemble
        similarity to the creating/feeding detection wins, provided it beats
        label_min_similarity and is not already claimed by an ACTIVE track.
        Sticky: a labeled track keeps its label for life (restores keep the
        tid, so the label follows the gallery id).
        """
        if not self._enrollment_refs or tid in self._track_labels:
            return
        claimed = {
            self._track_labels[t][0]
            for t in self.tracks
            if t in self._track_labels
        }
        best_ref, best_sim = None, self.label_min_similarity
        for ref in self._enrollment_refs:
            if ref.get("label") in claimed:
                continue
            sim = self._signature_similarity(ref, detection)
            if sim > best_sim:
                best_sim, best_ref = sim, ref
        if best_ref is not None:
            self._track_labels[tid] = (
                best_ref["label"], best_ref["squad"], best_ref["slot"],
            )
            self.logger.info(
                "Assigned enrollment label %s to track %d (sim %.3f)",
                best_ref["label"], tid, best_sim,
            )

    def _stamp_identities(
        self, players: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Add player_label/squad/slot to tracked-player dicts (in place).

        Every output path funnels through update()'s three returns, so this
        is the single place identity display metadata is attached. Tracks
        without a label (pre-lock temps, fallback videos, low-similarity
        creations) get None -- the overlay then shows today's green P<id>.
        """
        for p in players:
            tid = p.get("track_id")
            label_info = self._track_labels.get(tid) if tid is not None else None
            if label_info:
                p["player_label"], p["squad"], p["slot"] = label_info
            else:
                p["player_label"] = None
                p["squad"] = None
                p["slot"] = None
        return players

    # --- Public API ---

    def get_track_history(self, track_id: int) -> List[List[float]]:
        """Get position history for a specific track."""
        if track_id in self.tracks:
            return list(self.tracks[track_id]["history"])
        return []

    def get_active_tracks(self) -> Dict[int, Dict[str, Any]]:
        """Get all currently active tracks."""
        return dict(self.tracks)

    def reset(self) -> None:
        """Wipe all tracking state (active tracks, dormant gallery, bootstrap).

        Used by FrameProcessor.reset_trackers so re-running on a new video does
        not inherit the previous match's dormant ids or bootstrap buffer.
        """
        self.tracks = {}
        self.disappeared = {}
        self.gallery = {}
        self._track_labels = {}
        self._squatter_cooldown.clear()
        self.frame_count = 0
        self._initialized = False
        self._bootstrap_buffer = []
        self._bootstrap_qualifying = 0
        self._last_strict_detections = []
        self._current_frame = None
        self.logger.debug("Player tracker reset")

    def _get_current_tracks(self) -> List[Dict[str, Any]]:
        """Return current track states as tracked player list."""
        result = []
        for tid, track in self.tracks.items():
            result.append({
                "bbox": track["bbox"],
                "center": track["center"],
                "confidence": track["confidence"],
                "track_id": tid,
                "team": self._get_smoothed_team(tid),
            })
        return result
