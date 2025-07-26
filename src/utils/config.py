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
        "device": "cpu",  # or "cuda" if GPU available

        # Detection settings
        "ball_confidence": 0.3,
        "player_confidence": 0.5,
        "max_players": 4,

        # Tracking settings
        "ball_max_missing": 10,
        "trajectory_smoothing": 5,
        "player_max_disappeared": 30,
        "tracking_max_distance": 100.0,

        # Recognition settings
        "pose_confidence": 0.5,
        "pose_complexity": 1,
        "temporal_window": 10,
        "action_confidence": 0.6,

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
        device = self.get("device", "cpu")
        if device not in ["cpu", "cuda"]:
            logging.error("device must be 'cpu' or 'cuda'")
            valid = False

        # Validate pose complexity
        pose_complexity = self.get("pose_complexity", 1)
        if pose_complexity not in [0, 1, 2]:
            logging.error("pose_complexity must be 0, 1, or 2")
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
