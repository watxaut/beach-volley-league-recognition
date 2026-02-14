#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.analysis.action_sequence_analyzer import ActionSequenceAnalyzer

# Simple test config
action_config = {
    'history_window_size': 50,
    'serve_confidence_threshold': 0.5,
    'inactivity_threshold_frames': 90
}

# Create analyzer
analyzer = ActionSequenceAnalyzer(action_config)

# Simulate detected serve action (like frame 25 from results)
serve_action = {
    "action": "serve",
    "confidence": 1.0,
    "track_id": "player_0"
}

# Test frame 25 with serve action
frame_25_result = {
    "actions": [serve_action],
    "frame_index": 25
}
result = analyzer.analyze_frame(frame_25_result, 25)

print(f"Frame 25 Analysis Results:")
print(f"Serve Detected: {result.confidence_scores.get('serve_detected', 0.0)}")
print(f"Rally Active: {result.confidence_scores.get('rally_active', 0.0)}")
print(f"Recent Actions: {result.metadata.get('recent_actions', [])}")

# Test frame 26 (one frame after serve)
frame_26_result = {
    "actions": [],  # No actions detected
    "frame_index": 26
}
result2 = analyzer.analyze_frame(frame_26_result, 26)

print(f"\nFrame 26 Analysis Results:")
print(f"Serve Detected: {result2.confidence_scores.get('serve_detected', 0.0)}")
print(f"Rally Active: {result2.confidence_scores.get('rally_active', 0.0)}")
print(f"Recent Actions: {result2.metadata.get('recent_actions', [])}")