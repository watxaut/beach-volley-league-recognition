#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.analysis.game_state_manager import GameStateManager
from src.utils.config_loader import load_config

# Load config
config = load_config()

# Create game state manager
game_state_manager = GameStateManager(config)

# Create minimal frame result
frame_result = {
    'frame_index': 50,
    'ball_detections': [],
    'player_detections': [],
    'tracked_players': [],
    'tracked_ball': None,
    'actions': [],
    'processing_time': 0.0
}

try:
    # Try to analyze one frame
    game_state_info = game_state_manager.analyze_frame(frame_result, 50)
    print("Game state analysis successful!")
    print(f"State: {game_state_info.current_state}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()