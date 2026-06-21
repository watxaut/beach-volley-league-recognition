# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands for Development

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies using uv (preferred)
pip install uv
uv pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"
```

### Running the Application
```bash
# Basic video analysis
python -m src.main path/to/video.mp4

# With court calibration (recommended -- click 6 points once, reuse forever)
python -m src.main path/to/video.mp4 --court court_calibration.json

# With custom output directory and configuration
python -m src.main path/to/video.mp4 --output-dir ./results --config volleyball_detection_config.yaml

# Enable live debug mode with real-time visualization
python -m src.main path/to/video.mp4 --debug-live --debug-speed 0.5

# Skip visualization generation
python -m src.main path/to/video.mp4 --skip-visualization
```

### Per-Component Test Scripts
```bash
# Court calibration (interactive -- click 4 corners + 2 net points)
python scripts/test_court_calibration.py resources/video.mp4

# Ball detection (frame-by-frame YOLO detection rate)
python scripts/test_ball_detection.py resources/video.mp4 --max-frames 500 --save-video

# Ball tracking (detection + trajectory tracking)
python scripts/test_ball_tracking.py resources/video.mp4 --save-video

# Player tracking (4-player lock with stable IDs)
python scripts/test_player_tracking.py resources/video.mp4 --court court_calibration.json --save-video

# Pose estimation (skeleton overlays)
python scripts/test_pose_estimation.py resources/video.mp4 --save-video

# Action recognition (full pipeline)
python scripts/test_action_recognition.py resources/video.mp4 --court court_calibration.json --save-video

# Evaluation against ground truth
python scripts/evaluate.py --predictions output/results/ --ground-truth ground_truth/
```

### Testing
```bash
# Run all tests with coverage
pytest tests/ -v

# Generate coverage report
pytest --cov=src --cov-report=html
```

### Testing with Sample Videos
Use videos in the `resources/` directory for testing:
- `resources/avp_front_1.mp4` - Front view volleyball match
- `resources/video_front.mov` - Another front view sample
- `resources/video_side.mov` - Side view volleyball

## Project Architecture

### Core Pipeline Architecture
The system follows a modular computer vision pipeline designed for a **fixed camera on the long axis of the court, with the net facing the camera** (camera looks down the length of the court). The near half of the court is Team A, the far half is Team B; team assignment is by which side of the midcourt line a player's feet fall on.

1. **Detection Layer** (`src/detection/`): YOLO-based ball and player detection + one-time court calibration
2. **Tracking Layer** (`src/tracking/`): 4-player locked tracking + conservative ball tracking
3. **Recognition Layer** (`src/recognition/`): MediaPipe pose estimation + event-driven action classification
4. **Analysis Layer** (`src/analysis/`): Orchestrates the pipeline via `FrameProcessor`
5. **Output Layer** (`src/output_gen/`): Exports results to CSV and generates visualizations

### Key Components

#### Detection System
- **BallDetector** (`ball_detector.py`): YOLO-based. Loads either COCO `yolov8n.pt` (filters to sports ball class 32 + frisbee class 29) or a custom fine-tuned model via `model_path` (e.g., `models/volleyball_ball_best.pt`, no class filter needed). Auto-scales input resolution for high-res video. Size filtering rejects too-large detections. The `keep_all` flag (default `False`) returns every passing detection instead of the top-1 cull the tracker relies on -- used by `test_ball_detection.py` for validation.
- **PlayerDetector** (`player_detector.py`): YOLO person detection with court-boundary filtering (foot position inside court polygon). Aspect-ratio floor lowered to 0.6 so diving/crouching and close-to-camera players are not rejected.
- **CourtCalibration** (`court_calibration.py`): One-time interactive calibration -- user clicks 4 court corners + 2 midcourt ground-line points (where the net tape meets the sand at each sideline) + 2 net-top points (where the net tape meets each post/antenna). Saves to JSON for reuse. Provides court polygon, midcourt/net lines, team zones, and spatial queries (`is_near_net`, `is_behind_baseline`, `get_team`, `is_above_net`).

#### Tracking System
- **BallTracker** (`ball_tracker.py`): Conservative tracker. Returns None when ball is lost (no hallucinated positions). Court-bounds rejection. Settings: max_missing_frames=10, low_confidence_threshold=0.4, max_trajectory_gap=60px.
- **PlayerTracker** (`player_tracker.py`): Locks to exactly 4 players after initialization. K-means clustering from first N frames, Hungarian algorithm assignment, color histogram appearance features. IDs 1-4, never creates 5th track. Team assignment via court calibration.

#### Action Recognition
- **PoseEstimator** (`pose_estimator.py`): MediaPipe in video mode (temporal smoothing). Outputs body-relative normalized features (wrist_height_ratio, elbow_height_ratio, etc.) instead of raw pixel coordinates.
- **ActionClassifier** (`action_classifier.py`): Event-driven -- only classifies at ball trajectory inflection points. Finds closest player, classifies by pose + court position + ball direction. Tiered: Tier 1 spatial (serve, block), Tier 2 pose+ball (dig, set, spike).

#### Pipeline
- **FrameProcessor** (`frame_processor.py`): Orchestrates detection -> tracking -> recognition per frame.
- **VideoProcessor** (`video_processor.py`): Processes full videos using FrameProcessor.
- **LiveDebugProcessor** (`live_debug_processor.py`): Real-time visualization for development.

### Video Processing Flow
1. Court calibration (one-time, saved to JSON)
2. Ball + player detection using YOLO
3. 4-player locked tracking with appearance features
4. Conservative ball tracking (returns None when lost)
5. Pose estimation with body-relative features
6. Event-driven action classification at ball contact points
7. Statistical aggregation and result export

### Configuration
- Defaults live in `src/utils/config.py` (`Config.DEFAULT_CONFIG`). Override by passing `--config <file>` (YAML or JSON) on the CLI.
- Key settings: `ball_confidence` (0.7), `player_confidence` (0.5), `max_players` (4), `ball_model_path` (optional -- points to a fine-tuned ball model)
- Supports CPU/CUDA device selection

### Output
- **CSV Export**: Player action counts and frame-by-frame timelines
- **Visualization**: Multi-panel graphs (action totals, per-player breakdown, temporal analysis)
- **Debug Mode**: Real-time visualization with adjustable playback speed

## Ground Truth & Evaluation

- Annotations stored in `ground_truth/` as JSON (see `ground_truth/README.md` for format)
- `scripts/evaluate.py` computes: ball detection rate, player ID consistency, action precision/recall
- Roboflow recommended for ball detection annotations (export YOLOv8 format for fine-tuning)

## Claude Code Workflow Guidance

### Implementation Strategies
- When asked to implement a new feature, draft a short plan in the conversation and confirm the approach with the user before writing production code.
- Prefer extending existing modules under `src/` over creating new top-level files.
