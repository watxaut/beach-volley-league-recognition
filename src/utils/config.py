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

        # Detection settings
        "detection_method": "template",  # Default to Wilson ball template matching
        "ball_confidence": 0.7,  # Much lower for better ball detection
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
        "player_max_disappeared": 30,
        "tracking_max_distance": 100.0,

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
        "player_gallery_evict_min_hold_frames": 60,  # protect a freshly-retired id for this long before it's reclaimable
        "player_bootstrap_min_window": 8,       # consecutive ball-active frames with a stable 4-roster to lock
        "player_bootstrap_ball_required": True,  # skip the warmup opening (only lock once the ball is live)
        "player_signature_color_weight": 0.4,   # torso HSV histogram (existing)
        "player_signature_height_weight": 0.3,  # relative body size from the ground plane (uniform-independent)
        "player_signature_head_weight": 0.15,   # head/hair HSV histogram
        "player_signature_proportions_weight": 0.15,  # body height/width ratio
        "player_signature_height_smoothing": 30,  # rolling-median window (frames) for the world body-size estimate

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
        "attribution_near_net_exempt_m": 1.5,  # wrong-team candidates at the net (ground metres) stay eligible only when the CONTACT is above the net-top line (block geometry); image-px would swallow the far half

        # Processing settings
        "batch_size": 1,
        "frame_skip": 1,  # Process every nth frame
        "save_debug_frames": False,
        "debug_output_dir": "./debug",

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
        
        # Game state detection settings
        "game_state_detection": {
            "enabled": True,
            "serve_threshold": 0.4,
            "point_end_threshold": 0.6,
            "min_state_duration_frames": 10,
            "activity_gap_threshold_seconds": 3.0,
            
            # Action sequence analysis
            "action_sequence": {
                "serve_pattern_window": 30,  # frames
                "rally_end_inactivity_threshold": 90,  # frames
                "action_confidence_threshold": 0.6
            },
            
            # Trajectory analysis
            "trajectory_analysis": {
                "serve_trajectory_features": {
                    "min_arc_height": 50,  # pixels
                    "horizontal_distance_threshold": 200,
                    "velocity_pattern_weight": 0.7
                },
                "point_end_detection": {
                    "ground_contact_threshold": 20,  # pixels from court bottom
                    "out_of_bounds_margin": 30,     # pixels beyond court
                    "velocity_drop_threshold": 0.3   # relative velocity drop
                }
            },
            
            # Temporal analysis
            "temporal_analysis": {
                "activity_smoothing_window": 15,     # frames
                "pause_classification_thresholds": {
                    "short_pause": 1.0,   # seconds - between-point pause
                    "medium_pause": 5.0,  # seconds - timeout/break
                    "long_pause": 15.0    # seconds - extended break
                }
            },
            
            # Score tracking
            "score_tracking": {
                "max_score_per_set": 25,
                "service_rotation_enabled": True,
                "point_detection_methods": ["trajectory", "action_sequence"]
            }
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
