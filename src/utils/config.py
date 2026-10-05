"""
Configuration management for volleyball video analysis.

This module handles loading and managing configuration settings
for the video analysis pipeline.
"""

from typing import Dict, Any, Optional
import json
import yaml
from pathlib import Path
import logging


class Config:
    """Configuration manager for volleyball analysis system."""

    DEFAULT_CONFIG = {
        # Device settings
        "device": "auto",  # auto-selects CUDA > MPS (Apple GPU) > CPU; force with "cpu"/"cuda"/"mps"

        # Sub-1080p sources are upscaled once (ffmpeg Lanczos, cached as
        # <stem>_up1080.mp4 next to the original, see src/utils/video_upscale.py):
        # every px constant downstream (ball width side signal, NEAR_NET_PX,
        # TOUCH_RISE_PX, tracker gates) was measured at 1080p. 0 disables.
        "upscale_to_height": 1080,

        # Detection settings
        "detection_method": "template",  # Default to Wilson ball template matching
        "ball_confidence": 0.15,  # MUST match scripts/test_action_recognition.py: the fine-tuned model
                                  #   + conservative tracker are tuned here, and every GT-validated action
                                  #   number was measured at 0.15. At 0.7 the ball history starves and
                                  #   gestures flip in production/live-debug vs the script (f539 block).
        "player_confidence": 0.5,  # 0.35 lifts recall ~3pp on far-side players but adds false detections; kept at 0.5
        "player_imgsz": 1280,   # YOLO inference size; 640 default loses small far-side players
        "max_players": 4,       # exactly 4 for match identity (gallery/bootstrap assume a 4-roster).
                                #   NOTE: training drills with >4 on court need a separate profile.
        "max_detections": 20,   # detector safety cap (must exceed people on court)
        "ball_horizontal_margin_percent": 0.25,  # Horizontal margin to exclude from ball detection (15% on each side)

        # Tracking settings -- tuned for the conservative BallTracker used by
        # FrameProcessor (matches scripts/test_action_recognition.py). Loose
        # values here let the tracker chase noise and break contact detection.
        "ball_max_missing": 10,
        "trajectory_smoothing": 5,
        # Ball-matching (2026-09-06): the tracker owns identity via trajectory
        # gates; the detector returns ALL candidates (no top-1 cull). A lock
        # (bootstrap or re-lock) requires demonstrated motion so static spares
        # (sand/rack balls) can never own the track; while coasting the gate
        # follows the velocity prediction.
        "ball_lock_min_speed": 8.0,        # px/f of demonstrated motion to (re)lock
        "ball_lock_motion_window": 5,      # frames of sightings consulted for motion
        "ball_lock_max_jump": 90.0,        # px: two sightings this close may be one ball
        "ball_lock_max_pair_gap": 2,       # frames: motion pair must be near-consecutive
        # 20260920 "blue sky" mechanism (probe: sky-backed candidates med 0.90
        # vs sand-backed 0.20 -- the 0.4 floor starved the track off-sky):
        "ball_locked_low_conf_floor": 0.15,  # LOCKED, only on frames with NO >=low_confidence_threshold candidate: accept the best non-suspect in-gate candidate >= this floor (0=off)
        "ball_boot_low_conf_floor": 0.15,    # UNLOCKED: motion-pair evidence may use sightings >= this floor when no high-tier pair exists (0=off)
        "ball_selection_conf_window": 10.0,  # px: confidence breaks ties only within this
        # Detector-side stationarity: surviving detections at/above this
        # windowed persistence are flagged stationary_suspect for the tracker
        # (full suppression still happens at ball_static_persist above it).
        "ball_static_suspect_frac": 0.30,
        "ball_selection_conf_window": 10.0,  # px: confidence breaks ties only within this
        # player_max_disappeared / tracking_max_distance: PlayerTracker ctor defaults
        # (what every validated script path runs: test_action_recognition,
        # dump_player_tracks). The old 30/100 diverged production/live-debug
        # from the script (tracks retired sooner, associations tighter).
        "player_max_disappeared": 90,
        "tracking_max_distance": 150.0,

        # Player tracker: team smoothing + coast extrapolation
        "player_team_vote_window": 15,   # frames of foot-position votes for team label
        "coast_extrapolation_cap": 15,   # max frames to extrapolate a lost track's box
        "coast_velocity_decay": 0.85,    # per-frame velocity decay while coasting
        "coast_vertical_damping": 0.5,   # extra per-step decay of UPWARD coast velocity (ghost boxes must not ride a jump upward; downward = court-axis running, undamped)

        # Server admission: the serving player stands off-court behind their
        # baseline at video/rally start and strict foot-in-court admission can
        # never track them (entreno_3: server detected at conf ~0.9 the whole
        # time yet untracked f10-175). A serve-zone detection may open a NEW
        # track when a roster slot is free.
        "player_serve_zone_enabled": True,
        "player_serve_zone_depth_m": 3.0,       # how far behind the baseline (ground-plane metres) counts as the serve zone
        "player_serve_zone_side_margin_m": 1.0, # how far beyond each sideline (metres) the zone extends
        "player_serve_zone_trial_frames": 90,   # a serve-zone seed must enter the court within this window or the slot is freed (stationary-bystander guard, entreno_5)
        "player_serve_zone_ball_votes": 2,      # recent ball sightings inside a zone candidate's column (x-span, above the waist) required to admit them as the server; a sand-level spare ball beside a bystander never votes

        # Player identity (continuity-first re-ID). See plan "Consistent 4-Player
        # Identity". Identity is propagated by motion continuity; the keys below
        # tune the two-zone admission, the rally bootstrap, the dormant gallery,
        # and the enriched appearance+biometric signature.
        "player_appearance_weight": 0.4,        # surface of PlayerTracker ctor default
        "player_init_frames": 60,               # surface of ctor default; = bootstrap_max_wait fallback
        "player_play_area_margin_px": 100,      # how far beyond the court polygon ESTABLISHED tracks may roam
        "player_gallery_enabled": True,         # match-long dormant gallery (never delete a player)
        "player_gallery_reacquire_distance_px": 120.0,  # motion/position gate to re-acquire a dormant id
        "player_gallery_reacquire_min_appearance": 0.15,  # signature floor below which a re-acquire is flagged low-confidence
        "player_gallery_reacquire_appearance_min": 0.5,  # ensemble similarity bar for appearance-only re-acquire (moved player / side change)
        "player_off_court_grace_frames": 45,   # how long an off-court detection may continue a track after its last in-court sighting (server step-out); blocks bystander hijack
        "player_off_court_hold_frames": 90,    # horizon on CONTINUOUS out-of-court feeding: a track not seen in court for this long stops feeding (retires, slot freed for in-court admission). Real players max out at 46f (e6); kills e2's sideline-straddling bystander that held a slot for 415f
        "player_off_court_cost_penalty_px": 300.0,  # association-cost penalty (px-equivalent) on OUT-OF-COURT detections: identity is anchored in court, so when a track's own player is detected in court the same frame, the in-court detection wins the assignment even if the off-court one is closer. Without it a walkway bystander re-attaches to a coasting track the moment the player's detection blips (e6 f142: the far-left digger's track was taken at 105 px and never returned -- 200 frames untracked), and the squat cascades into chain-swaps (e6 f305/f311, team flip A->B). Below the invalid sentinel (1e6) so an off-court chain is still preferred over leaving a track unmatched when no in-court option exists; 0 disables; uncalibrated courts unaffected
        "player_gallery_evict_min_hold_frames": 60,  # protect a freshly-retired id for this long before it's reclaimable (a squatter-flagged entry bypasses this -- evictable immediately)
        "player_squatter_enabled": True,        # expire a track whose lifetime in-court FEEDING fraction stays under min_in_court_frac past review_frames (sideline straddler, e7): expired to the gallery with a squatter flag that blocks restore, and its sampled foot positions block re-admission nearby
        "player_squatter_review_frames": 120,   # track age at which the squatter review first fires (e7 straddler: 34/120 = 28% in-court fed at its own tick; its dense f47-63 in-court run forbids earlier)
        "player_squatter_min_fed_frames": 20,   # noise floor on real feedings before the fraction may expire a track (barely-fed tracks coast toward normal retirement)
        "player_squatter_min_in_court_frac": 0.35,  # lifetime in-court-fed / fed below this = squatter. Worst real case measured ~0.62 (e6 46f off-court streak); e7 straddler sits at 0.28
        "player_squatter_cooldown_radius_m": 0.5,   # new-track admission refused within this ground radius of an expired squatter's foot samples (in-court re-admission attempts read 7.84-7.99 m)
        "player_bootstrap_min_window": 8,       # consecutive ball-active frames with a stable 4-roster to lock
        "player_bootstrap_ball_required": True,  # skip the warmup opening (only lock once the ball is live)
        "player_signature_color_weight": 0.4,   # torso HSV histogram (existing)
        "player_signature_height_weight": 0.3,  # relative body size from the ground plane (uniform-independent)
        "player_signature_head_weight": 0.15,   # head/hair HSV histogram
        "player_signature_proportions_weight": 0.15,  # body height/width ratio
        "player_signature_height_smoothing": 30,  # rolling-median window (frames) for the world body-size estimate

        # Player enrollment pre-pass (E1): stable P1A/P1B/P2A/P2B identity
        # anchors. A pre-pipeline pass decodes the opening of the video
        # SEQUENTIALLY (no seeks, AGENTS.md §9), runs the player detector on
        # every stride-th frame, keeps foot-strictly-in-court detections and
        # chains them into identities; the 4 most persistent chains become
        # enrollment references (multi-crop ensemble signatures + labels:
        # squad 1 = the near-side pair at video start, squad 2 = far; slot
        # A/B = left-to-right). References attach DISPLAY-ONLY labels to the
        # in-stream tracks by signature matching -- bootstrap/admission
        # machinery is untouched, so tracking is byte-identical with
        # enrollment off or on. Fallback (<4 persistent chains, no 2+2 side
        # split): no enrollment, today's green P<id> display.
        "player_enrollment_enabled": True,     # run the enrollment pre-pass (labels + squad colors)
        "player_enrollment_frames": 600,       # opening window to sample (frames, ~23 s at 26 fps)
        "player_enrollment_stride": 5,         # run the detector every Nth frame of the window (~0.2 s between samples)
        "player_enrollment_min_obs": 8,        # observations a chain needs to count as a player
        "player_enrollment_chain_gate_px": 120.0,  # foot-distance gate between consecutive samples of one chain (VENUE-COUPLED px: beach court is 206 px deep vs 464-479 at the practice venue)
        "player_enrollment_chain_gap_samples": 6,  # consecutive missed samples before a chain dies (occlusion fragments re-join in the merge pass)
        "player_enrollment_merge_gap_frames": 60,  # max time gap for merging a chain fragment back into its predecessor (~2.3 s)
        "player_enrollment_court_slack_px": 16.0,  # accept samples whose foot sits this far OUTSIDE the strict court (on-line players read ~0-3 px out; bystanders >=100 px)
        "player_enrollment_max_start_frame": 150,  # a reference chain must START within this frame (walkers/bystanders arriving late lose the slot to waiting players)
        "player_label_min_similarity": 0.35,   # ensemble-similarity floor to attach an enrollment label to a track (greedy best-of-unclaimed; sticky once assigned)
        "player_label_new_track_min_similarity": 0.55,  # stricter floor for labels claimed AFTER the bootstrap lock (a recycled track must clearly match its reference)
        "player_identity_resolver": True,       # per-frame display-only identity resolver: labels follow the body (appearance + continuity), not the tracker id, so an id swap never moves a label
        "player_identity_court_slack_px": 16.0, # a body only competes for a label when its foot is in court or within this many px of the line
        "player_identity_mode": "team",          # OUTPUT label source: "team" = side-switch-aware TeamIdentityResolver (src/tracking/identity_resolver.py), "legacy" = the #82 per-frame resolver; tracking is identical either way
        "player_identity_switch_threshold": 8.0,   # team resolver: accumulated log-likelihood (tempered) for the other orientation at which a side switch is accepted
        "player_identity_switch_temper": 0.2,      # team resolver: weight of one frame's evidence (consecutive frames are far from independent)
        "player_identity_min_switch_interval_frames": 300,  # team resolver: min frames between two accepted switches (safety net; the 20260920 replay needs none)

        # Enhanced trajectory-based tracking settings
        "low_confidence_threshold": 0.4,  # Min confidence for the tracker to accept a detection
        "trajectory_confidence_boost": 0.3,  # Boost confidence for trajectory-consistent detections
        "max_trajectory_gap": 60.0,  # Maximum distance to consider trajectory continuation
        "velocity_consistency_weight": 0.4,  # Weight for velocity consistency in scoring
        "acceleration_consistency_weight": 0.2,  # Weight for acceleration consistency
        "trajectory_prediction_frames": 5,  # Number of frames to predict ahead
        "fast_ball_velocity_threshold": 50.0,  # Velocity threshold for fast ball mode

        # Recognition settings
        "pose_confidence": 0.5,
        # 0 (lite) is ~1.6x faster per pose batch and produced byte-identical
        # action logs vs 1 on the entreno_1/3 GT A/B (2026-08-16); raise to 1/2
        # only if a future video shows gesture (hands-overhead) misses.
        "pose_complexity": 0,
        # Pose gating (perf, adopted 2026-09-27 after a byte-identical A/B on
        # all 7 entrenos): skip MediaPipe pose once the ball has been untracked
        # this many frames (dead time -- no contact can consume pose past the
        # reentry horizon), and when the ball IS tracked only pose players
        # within this many px of a ball point in the last NEIGH+2 frames
        # (measured bound of consumed snapshots: 155 px max). 0 disables either.
        "pose_gate_stale_frames": 30,
        "pose_near_ball_radius_px": 300.0,
        "temporal_window": 10,
        "action_confidence": 0.3,  # Min confidence to emit an action; matches scripts/test_action_recognition.py (classifier scores ~0.3-0.8)

        # Team-aware contact attribution: which team may touch next is read from
        # the ball's pixel WIDTH (bigger = nearer half) when it commits, else
        # from possession alternation (attack/serve/block went over -> flip,
        # dig/set -> carry); candidates' teams come from their per-contact foot
        # position (the smoothed tracker team is wrong near the midcourt band).
        # Image-plane trajectory side was tried and REJECTED: airborne balls
        # over the near half project above the midcourt line (entreno_3
        # f211/f244/f453/f488 all read "far"), and near-half approaches are
        # often not detected at all (occlusion).
        "attribution_team_aware": True,       # False = legacy closest-player, no team filter
        "attribution_width_side": True,       # ball-width near/far override on possession alternation
        "attribution_width_window": 8,        # frames of incoming ball samples consulted
        "attribution_width_far_px": 26.0,     # ball width under this = far half (B)
        "attribution_width_near_px": 35.0,    # ball width over this = near half (A); between = abstain
        "attribution_near_net_exempt_m": 2.5,  # wrong-team candidates at the net (ground metres) stay eligible only when the CONTACT is above the net-top line; 2.5m so a beach spiker taking off ~2m back stays eligible (e5 f300: 2.14m) — a set thief stays excluded via the above-net gate

        # Processing settings
        "batch_size": 1,
        "frame_skip": 1,  # Process every nth frame
        "save_debug_frames": False,
        "debug_output_dir": "./debug",
        # T4 diagnostic capture: path to write a per-frame JSONL dump
        # (raw ball dets + suppression flags, ball-tracker state/reason,
        # player tracks, contact candidates incl. rejections + gate reason,
        # actor/team, gesture + resolved label) or None = OFF. Off by default
        # and inert when off: the hooks are `if self.diag_enabled:` guards
        # around values the pipeline already computed, so batch/live/probe
        # output is byte-identical either way. Read by
        # scripts/waterfall.py (see src/utils/diagnostics.py).
        "diag_dump": None,

        # Serve-evidence event emitters (open point G2: the far serve is 0/12
        # held-out and every classifier tried so far was refuted; the owner's
        # alternative is to EMIT the evidence and decide with it afterwards).
        # Pure observers in FrameProcessor.process_frame, OFF by default, so
        # batch/live/probe output stays byte-identical until they are switched
        # on deliberately (--serve-events). They never touch the action stream.
        "serve_events_enabled": False,
        # Runway band around the FAR BASELINE as a FRACTION of the court's
        # projected depth (px constants are venue-coupled: 206 px deep on the
        # beach vs 464-479 px at the practice venue, AGENTS.md §7). Measured
        # over the 17 GT far serves: strictly-behind-the-line sees a person at
        # 7/17, this straddling band at 17/17 (a far server often stands ON the
        # line). The lateral bound is the two sidelines continued to infinity.
        "serve_runway_front_frac": 0.15,    # how far IN FRONT of the far line the band reaches
        "serve_runway_back_frac": 0.30,     # how far BEHIND it reaches (the wedge apex closes it)
        "serve_runway_side_margin_frac": 0.0,  # extra lateral slack (0 = strictly inside the lines)
        "serve_runway_min_conf": 0.15,      # a far server sits at conf 0.2-0.45, far below player_confidence
        "serve_runway_min_frames": 3,       # presence run length before a runway_occupant event
        "serve_ball_min_conf": 0.15,        # floor on raw (pre-static-suppression) ball dets
        # E1 far flight: apparent bbox width GROWING = approaching the long-axis
        # camera. S1 refuted this as a SEPARATOR (L overlaps non-serve far lofts);
        # as an event combined with the runway it is still informative evidence.
        "far_flight_span_s": 0.5,           # window length in seconds
        "far_flight_min_points": 3,         # real sightings needed for a slope
        "far_flight_min_growth": 0.0,       # L = slope of ln(width) vs seconds must exceed this
        "far_flight_max_gap": 3,            # frames a run may skip: a far ball is detected ~1 frame in 4
        # Conjunction ("a player in the runway, with the ball, and a contact").
        "serve_candidate_reach_factor": 1.0,  # ball-to-box gap, in occupant bbox heights
        "serve_candidate_lookback_s": 5.0,    # how far back from the flight onset to look for that ball

        # Structural contact arm (session 53): the same runway occupant and a
        # ball-SIZED far-side detection in reach, WITHOUT the far_flight
        # requirement. Measured on the 17 GT far serves: 11/17 at precision 1.00
        # on its own and 14/17 unioned with the gated conjunction, against 0/17
        # in the action stream (docs/g4_structural_serve.md). The opener gate
        # that makes it safe is applied post-hoc, not here.
        "serve_structural_enabled": True,       # inside the --serve-events envelope
        "serve_structural_reach_factor": 1.5,   # ball-to-box gap, in occupant bbox heights
        "serve_structural_ball_w_min": 8,        # venue far/near ball range; below this it is sand
        "serve_structural_ball_w_max": 60,
        "serve_structural_max_gap": 3,          # frames a run may skip (far ball ~1 frame in 4)

        # Model paths (optional - uses defaults if not specified)
        "ball_model_path": None,
        "player_model_path": None,

        # Output settings
        "output_format": ["csv", "png"],
        "visualization_dpi": 300,

        # Logging
        "log_level": "INFO",
        "log_file": None,

        # Court detection settings
        # LEGACY/unused: court is now the interactive CourtCalibration JSON
        # (calibrations/<video>.json), not a detected/model-based court. Kept only
        # so Config.validate() and old configs don't break; "yolo" was invalid.
        "court_detection_method": "geometric",  # "geometric" or "vision" (unused)
        "court_model_path": "weights/court/court_best.pt",  # Path to YOLO court model
        "court_confidence": 0.5,  # Confidence threshold for YOLO court detection
        "court_height_ratio": 0.2,  # Court takes 60% of frame height (fallback for geometric)
        "court_width_ratio": 0.7,   # Court takes 80% of frame width (fallback for geometric)
        "court_vertical_offset": 0.6,  # Court starts at 20% from top (fallback for geometric)
        "court_horizontal_center": 0.52,  # Court centered horizontally (fallback for geometric)

        # Perspective correction settings
        "court_perspective_enabled": True,  # Enable perspective-aware court detection
        "court_perspective_top_width": 0.5,  # Width ratio at top of court (far end)
        "court_perspective_bottom_width": 0.8,  # Width ratio at bottom of court (near end)
        "court_perspective_skew": 0.0,  # Horizontal skew (-0.2 to 0.2, negative = left skew)
        "court_perspective_depth": 0.20,  # How much perspective depth to apply (0.0 to 0.3)

        # Advanced court detection settings
        "court_margin": 0.01,  # 5% margin around detected court
        "use_adaptive_court": False,  # Adapt court based on player positions
        "court_yolo_only_start": True,  # Only run YOLO court detection on first 10 frames, then reuse
        
        # Enhanced Ball-Player Proximity Validation Settings
        "enhanced_validation": {
            "enabled": True,
            "strict_mode": True,  # Enforce stricter validation to reduce over-detection
            
            # Ball contact validation settings
            "ball_contact": {
                "min_contact_confidence": 0.6,  # Higher threshold to reduce over-detection
                "contact_zones": {
                    "dig": {
                        "height_range": [0.6, 1.0],  # Relative to player height
                        "width_expansion": 1.5,      # Increased arm reach
                        "base_threshold": 120        # More lenient proximity
                    },
                    "set": {
                        "height_range": [0.0, 0.4],  # Above shoulders
                        "width_expansion": 1.5,      # Increased reach for sets
                        "base_threshold": 150        # Much more lenient for sets
                    },
                    "spike": {
                        "height_range": [-0.2, 0.3], # Extended above head
                        "width_expansion": 1.8,      # Increased spike reach
                        "base_threshold": 140        # More lenient proximity
                    },
                    "block": {
                        "height_range": [0.0, 0.3],
                        "width_expansion": 1.5,      # Increased reach
                        "base_threshold": 130        # More lenient proximity
                    },
                    "serve": {
                        "height_range": [0.2, 0.8],
                        "width_expansion": 2.0,      # Increased serve reach
                        "base_threshold": 180        # Higher for serves
                    }
                }
            },
            
            # Temporal validation settings
            "temporal": {
                "window_size": 5,
                "min_frames_in_contact": 2,     # Require fewer frames for contact
                "confidence_decay_rate": 0.2,   # Faster decay
                "contact_stability_threshold": 0.4  # Lower threshold for stability
            },
            
            # Ball trajectory analysis settings
            "trajectory": {
                "trajectory_window": 10,
                "min_velocity_change": 50.0,      # pixels/frame
                "min_direction_change": 30.0,     # degrees
                "velocity_spike_threshold": 2.0,   # multiplier
                "smoothing_window": 3,
                "gravity_acceleration": 9.8,      # pixels/frame^2
                "air_resistance_factor": 0.98,
                "bounce_energy_loss": 0.7
            },
            
            # Court position validation settings
            "court": {
                "enabled": True,
                "serve_boundary_margin": 50,      # pixels behind baseline
                "court_geometry": "from_config",   # Use existing court detection
                "court_geometry_config": {
                    "court_width_ratio": 0.7,
                    "court_height_ratio": 0.6,
                    "court_horizontal_center": 0.5,
                    "court_vertical_offset": 0.3
                }
            }
        },
        
        # Game state detection settings (on/off state machine -- params are
        # frames at ~30 fps; validated on video_entreno_game_state vs
        # gt_point_start_end.txt: 12/13 points, 0 false, 0 merged)
        "game_state_detection": {
            "enabled": True,
            # Episode layer (ball flight)
            "flight_speed_px": 8.0,        # px/frame: ball is "in flight"
            "arm_quiet_frames": 10,        # no-flight frames before a burst may arm
            "serve_burst_frames": 8,       # burst length that arms a candidate
            "burst_gap_frames": 6,         # untracked gap tolerated inside a burst
            "confirm_frames": 90,          # confirmation window after arming
            "confirm_flight_frames": 20,   # flight frames needed to confirm ON
            "density_window_frames": 90,   # rolling continuation window
            "density_min_flights": 20,     # min flight frames in window to stay ON
            "static_off_frames": 40,       # tracked-but-static frames that end ON
            # Point layer (episode grouping + action confirmation)
            "group_gap_frames": 60,        # max gap merging episodes into one group
            "point_min_actions": 2,        # actions needed for a group to be a point
            "contact_chain_frames": 240,   # contact silence that splits a group into rallies
            # Serve-init semantics: live ON at the serve (~1s) instead of the
            # 90f confirm window; classifier serve actions arm instantly.
            # Point segmentation keeps the delayed confirm either way.
            "fast_confirm_flights": 20,    # candidate flights that show provisional GAME_ON (0=off)
            "fast_confirm_window_frames": 90,  # rolling window for the sustained-flight provisional
            "serve_action_arms": True      # a serve action arms a candidate without quiet/burst gates
        }
    }

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """Initialize configuration.

        Args:
            config_dict: Optional configuration dictionary
        """
        self.config = self.DEFAULT_CONFIG.copy()
        if config_dict:
            self.config.update(config_dict)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> 'Config':
        """Load configuration from file.

        Args:
            config_path: Path to configuration file (JSON or YAML)

        Returns:
            Config instance
        """
        if config_path is None:
            return cls()

        config_file = Path(config_path)
        if not config_file.exists():
            logging.warning(f"Config file not found: {config_path}, using defaults")
            return cls()

        try:
            with open(config_file, 'r') as f:
                if config_file.suffix.lower() in ['.yaml', '.yml']:
                    config_dict = yaml.safe_load(f)
                elif config_file.suffix.lower() == '.json':
                    config_dict = json.load(f)
                else:
                    logging.error(f"Unsupported config file format: {config_file.suffix}")
                    return cls()

            logging.info(f"Loaded configuration from: {config_path}")
            return cls(config_dict)

        except Exception as e:
            logging.error(f"Failed to load config file {config_path}: {e}")
            return cls()

    @classmethod
    def default(cls) -> 'Config':
        """Create default configuration.

        Returns:
            Config instance with default settings
        """
        return cls()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        self.config[key] = value

    def update(self, config_dict: Dict[str, Any]) -> None:
        """Update configuration with new values.

        Args:
            config_dict: Dictionary of configuration updates
        """
        self.config.update(config_dict)

    def save(self, config_path: str) -> None:
        """Save configuration to file.

        Args:
            config_path: Path where to save configuration
        """
        config_file = Path(config_path)

        try:
            with open(config_file, 'w') as f:
                if config_file.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(self.config, f, default_flow_style=False, indent=2)
                elif config_file.suffix.lower() == '.json':
                    json.dump(self.config, f, indent=2)
                else:
                    # Default to JSON
                    json.dump(self.config, f, indent=2)

            logging.info(f"Configuration saved to: {config_path}")

        except Exception as e:
            logging.error(f"Failed to save config to {config_path}: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary.

        Returns:
            Configuration dictionary
        """
        return self.config.copy()

    def validate(self) -> bool:
        """Validate configuration settings.

        Returns:
            True if configuration is valid
        """
        valid = True

        # Validate numeric ranges
        if not 0 <= self.get("ball_confidence", 0.3) <= 1:
            logging.error("ball_confidence must be between 0 and 1")
            valid = False

        if not 0 <= self.get("player_confidence", 0.5) <= 1:
            logging.error("player_confidence must be between 0 and 1")
            valid = False

        if not 0 <= self.get("action_confidence", 0.6) <= 1:
            logging.error("action_confidence must be between 0 and 1")
            valid = False

        if self.get("max_players", 4) <= 0:
            logging.error("max_players must be positive")
            valid = False

        if self.get("temporal_window", 10) <= 0:
            logging.error("temporal_window must be positive")
            valid = False

        # Validate device setting
        device = self.get("device", "auto")
        if device not in ["auto", "cpu", "cuda", "mps"]:
            logging.error("device must be 'auto', 'cpu', 'cuda', or 'mps'")
            valid = False

        # Validate pose complexity
        pose_complexity = self.get("pose_complexity", 1)
        if pose_complexity not in [0, 1, 2]:
            logging.error("pose_complexity must be 0, 1, or 2")
            valid = False

        # Validate court detection settings
        court_detection_method = self.get("court_detection_method", "geometric")
        if court_detection_method not in ["geometric", "vision"]:
            logging.error("court_detection_method must be 'geometric' or 'vision'")
            valid = False

        if not 0 < self.get("court_height_ratio", 0.6) <= 1:
            logging.error("court_height_ratio must be between 0 and 1")
            valid = False

        if not 0 < self.get("court_width_ratio", 0.8) <= 1:
            logging.error("court_width_ratio must be between 0 and 1")
            valid = False

        if not 0 <= self.get("court_vertical_offset", 0.2) <= 1:
            logging.error("court_vertical_offset must be between 0 and 1")
            valid = False

        if not 0 <= self.get("court_horizontal_center", 0.5) <= 1:
            logging.error("court_horizontal_center must be between 0 and 1")
            valid = False

        if not 0 <= self.get("court_margin", 0.05) <= 1:
            logging.error("court_margin must be between 0 and 1")
            valid = False

        if not 0 <= self.get("ball_horizontal_margin_percent", 0.15) < 0.5:
            logging.error("ball_horizontal_margin_percent must be between 0 and 0.5 (exclusive)")
            valid = False

        return valid

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access to configuration."""
        return self.config[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dictionary-style assignment to configuration."""
        self.config[key] = value

    def __contains__(self, key: str) -> bool:
        """Allow 'in' operator for configuration keys."""
        return key in self.config

    def __str__(self) -> str:
        """String representation of configuration."""
        return f"Config({len(self.config)} settings)"

    def __repr__(self) -> str:
        """Detailed string representation of configuration."""
        return f"Config({self.config})"
