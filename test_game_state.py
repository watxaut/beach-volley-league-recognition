#!/usr/bin/env python3
"""
Test script for game state detection on avp_front_2.mp4
Tests the first 100 frames where serve is expected in first 95 frames.
"""

import sys
import cv2
from pathlib import Path
from src.analysis.video_processor import VideoProcessor
from src.utils.config import Config
from src.output_gen.csv_exporter import CSVExporter

def main():
    # Setup
    video_path = "resources/avp_front_2.mp4"
    output_dir = Path("./test_game_state_output")
    output_dir.mkdir(exist_ok=True)
    
    print("Testing Game State Detection on avp_front_2.mp4")
    print("=" * 50)
    
    # Initialize processor with game state detection enabled
    config = Config.default()
    print(f"Game state detection enabled: {config.get('game_state_detection', {}).get('enabled', False)}")
    
    processor = VideoProcessor(config.to_dict())
    
    # Test with first 100 frames
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return 1
    
    # Video info
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"Video: {fps:.1f} FPS, {width}x{height}")
    
    # Update processor with video info
    processor.game_state_manager.set_video_info(fps, width, height)
    
    # Results storage
    results = {
        'frame_results': [],
        'video_info': {
            'fps': fps,
            'total_frames': 100,
            'width': width,
            'height': height
        }
    }
    
    # Process first 100 frames
    frame_count = 0
    serve_detected_frames = []
    game_state_transitions = []
    
    print("\nProcessing first 100 frames...")
    print("Looking for serves (expected in first 95 frames)")
    print("-" * 50)
    
    while frame_count < 100:
        ret, frame = cap.read()
        if not ret:
            break
        
        try:
            # Process frame
            frame_result = processor._process_frame(frame)
            frame_result["frame_index"] = frame_count
            results['frame_results'].append(frame_result)
            
            # Check for game state info
            game_state = frame_result.get('game_state', {})
            current_state = game_state.get('current_state', 'unknown')
            
            # Look for serves in actions
            actions = frame_result.get('actions', [])
            for action in actions:
                if action.get('action') == 'serve':
                    serve_detected_frames.append(frame_count)
                    print(f"  🏐 SERVE detected at frame {frame_count} (t={frame_count/fps:.2f}s, confidence: {action.get('confidence', 0):.3f})")
            
            # Track game state transitions
            transitions = game_state.get('transitions', [])
            for transition in transitions:
                if transition['frame'] == frame_count:
                    game_state_transitions.append(transition)
                    print(f"  🎯 STATE: {transition['from_state']} → {transition['to_state']} at frame {frame_count} (t={frame_count/fps:.2f}s, confidence: {transition['confidence']:.3f})")
            
            # Show current state occasionally
            if frame_count % 25 == 0:
                state_conf = game_state.get('state_confidence', 0.0)
                score_info = game_state.get('score_info', {})
                score = f"{score_info.get('team_a_score', 0)}-{score_info.get('team_b_score', 0)}"
                print(f"  Frame {frame_count:3d}: State={current_state:<10} (conf={state_conf:.3f}) Score={score}")
            
            frame_count += 1
            
        except Exception as e:
            print(f"  ❌ Error processing frame {frame_count}: {e}")
            frame_count += 1
            continue
    
    cap.release()
    
    # Results summary
    print("\n" + "=" * 50)
    print("RESULTS SUMMARY")
    print("=" * 50)
    print(f"Processed {frame_count} frames")
    print(f"Serves detected: {len(serve_detected_frames)} at frames {serve_detected_frames}")
    print(f"Game state transitions: {len(game_state_transitions)}")
    
    for transition in game_state_transitions:
        t = transition['frame'] / fps
        print(f"  - {transition['from_state']} → {transition['to_state']} at {t:.2f}s (frame {transition['frame']})")
    
    # Final score
    if results['frame_results']:
        final_frame = results['frame_results'][-1]
        final_game_state = final_frame.get('game_state', {})
        final_score = final_game_state.get('score_info', {})
        print(f"Final score: {final_score.get('team_a_score', 0)}-{final_score.get('team_b_score', 0)}")
        print(f"Final state: {final_game_state.get('current_state', 'unknown')}")
    
    # Export results
    print(f"\nExporting results to {output_dir}...")
    try:
        csv_exporter = CSVExporter()
        csv_exporter.export(results, output_dir / 'test_results.csv')
        print(f"✅ Results exported successfully")
        print(f"   - Main results: {output_dir}/test_results.csv")
        print(f"   - Detailed actions: {output_dir}/test_results_detailed.csv")
        print(f"   - Game state timeline: {output_dir}/test_results_game_state.csv")
        print(f"   - Statistics: {output_dir}/test_results_statistics.csv")
    except Exception as e:
        print(f"❌ Export failed: {e}")
    
    # Validation against expected behavior
    print(f"\n" + "=" * 50)
    print("VALIDATION")
    print("=" * 50)
    
    # Check if serve was detected in first 95 frames as expected
    serves_in_expected_range = [f for f in serve_detected_frames if f <= 95]
    if serves_in_expected_range:
        print(f"✅ Serve detection: Found {len(serves_in_expected_range)} serves in expected range (frames 0-95)")
    else:
        print(f"❌ Serve detection: No serves found in expected range (frames 0-95)")
        if serve_detected_frames:
            print(f"   However, serves were detected at frames: {serve_detected_frames}")
    
    # Check if game state transitions occurred
    if game_state_transitions:
        print(f"✅ Game state transitions: {len(game_state_transitions)} transitions detected")
        # Check for GAME_OFF → GAME_ON transition (expected for serve)
        game_on_transitions = [t for t in game_state_transitions if t['to_state'] == 'game_on']
        if game_on_transitions:
            print(f"✅ Game ON transitions: Found {len(game_on_transitions)} transitions to active play")
        else:
            print(f"⚠️ Game ON transitions: No transitions to active play detected")
    else:
        print(f"❌ Game state transitions: No transitions detected")
    
    print(f"\nTest completed. Check {output_dir} for detailed results.")
    return 0

if __name__ == "__main__":
    sys.exit(main())