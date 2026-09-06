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
- **BallDetector** (`ball_detector.py`): YOLO-based. Loads either COCO `yolov8n.pt` (filters to sports ball class 32 + frisbee class 29) or a custom fine-tuned model via `model_path` (e.g., `models/volleyball_ball_best.pt`, no class filter needed). Auto-scales input resolution for high-res video. Size filtering rejects too-large detections. Returns EVERY surviving detection (no top-1 cull since 2026-09-06: the cull let a high-confidence courtside/rack ball hide the ball in play); the `keep_all` flag is accepted but ignored. Static-ball handling is two-stage: detections persisting across the rolling window at `static_persist_frac` (0.55) are removed outright (sand/rack balls), and weaker persistence at `static_suspect_frac` (0.30) is only flagged `stationary_suspect` for the tracker to distrust.
- **PlayerDetector** (`player_detector.py`): YOLO person detection with court-boundary filtering (foot position inside court polygon). Aspect-ratio floor lowered to 0.6 so diving/crouching and close-to-camera players are not rejected.
- **CourtCalibration** (`court_calibration.py`): One-time interactive calibration -- user clicks 4 court corners + 2 midcourt ground-line points (where the net tape meets the sand at each sideline) + 2 net-top points (where the net tape meets each post/antenna). Saves to JSON for reuse. Provides court polygon, midcourt/net lines, team zones, and spatial queries (`is_near_net`, `is_behind_baseline`, `get_team`, `is_above_net`).

#### Tracking System
- **BallTracker** (`ball_tracker.py`): Conservative single-ball tracker; owns ball IDENTITY (2026-09-06 rework). When the ball is lost, returns None instead of hallucinating. Identity rules: only a MOVING candidate can bootstrap or re-lock the track (`lock_min_speed` 8 px/f over a near-consecutive sighting pair -- static spares can never own the track, and a serve toss locks within ~1-2 frames); while locked, the highest-confidence candidate is accepted inside a trajectory gate around the last position (growing with missing frames), and a candidate flagged `stationary_suspect` that fails the gate is overridden by the best in-gate plausible candidate instead of starving the track (entreno_7 f244 rack ball); when the coast prediction leaves the court bounds (ball provably out of view), a re-entry window holds the track near the exit point for 2x max_missing frames instead of resetting into whatever moves next (entreno_6 f225 lob). Settings: max_missing_frames=10, low_confidence_threshold=0.4, max_trajectory_gap=60px.
- **PlayerTracker** (`player_tracker.py`): Locks to exactly 4 players after initialization. K-means clustering from first N frames, Hungarian algorithm assignment, color histogram appearance features. IDs 1-4, never creates 5th track. Team assignment via court calibration. Squatter review (2026-09-06): a track whose lifetime in-court FEEDING fraction stays below `player_squatter_min_in_court_frac` (0.35) once `player_squatter_review_frames` (120) old is expired to the gallery with a `squatter` flag — every restore path skips it, it is immediately evictable for a real candidate, and its sampled world foot positions block new-track admission within `player_squatter_cooldown_radius_m` (0.5 m).

#### Action Recognition
- **PoseEstimator** (`pose_estimator.py`): MediaPipe in video mode (temporal smoothing). Outputs body-relative normalized features (wrist_height_ratio, elbow_height_ratio, etc.) instead of raw pixel coordinates.
- **ActionClassifier** (`action_classifier.py`): Event-driven -- only classifies at ball trajectory inflection points. Team-aware attribution: candidates are filtered by the expected touch team (ball pixel-width near/far regime overriding possession alternation; flip after attack/serve/block, carry after dig/set), then closest by point-to-bbox distance with per-contact foot teams. Two layers: Layer 1 gesture (bump_set/attack/block from ball motion + court + pose), Layer 2 `ActionContextResolver` resolves dig/set/spike/serve/overpass from touch count. Image-plane ball side is NOT a side signal in this camera geometry (airborne near-half balls project above the midcourt line).
- **SpikeAnalyzer** (`src/analysis/spike_analyzer.py`): Pure observer wired inside `FrameProcessor` (never mutates the action stream) that enriches spikes with `spike_type` (touch/hard, decided by post-contact ASCENT -- exit speed cannot separate them), `attack_zone` (9-zone grid per half via `CourtCalibration.world_point_to_zone`, from the spiker's pre-contact takeoff stance -- airborne contact feet project deep), and `outcome` (kill/out from the landed point's world coords; dug/blocked from follow contacts, with a loft-gated retro-conversion since sand cannot rebound a dig's 2-3m rise). Renderers read `trail_points`/`kill_annotation`/`spike_type_for` for the red fading trail, `KILL <zone>` marker, and `spike hard`/`spike touch` labels (shared `overlay.py` helpers).

#### Pipeline
- **FrameProcessor** (`frame_processor.py`): Orchestrates detection -> tracking -> recognition per frame.
- **VideoProcessor** (`video_processor.py`): Processes full videos using FrameProcessor.
- **LiveDebugProcessor** (`live_debug_processor.py`): Real-time visualization for development.

### Video Processing Flow
1. Court calibration (one-time, saved to JSON)
2. Ball + player detection using YOLO
3. 4-player locked tracking with appearance features
4. Conservative ball tracking (returns None when lost; identity by trajectory + motion, never by confidence alone)
5. Pose estimation with body-relative features
6. Event-driven action classification at ball contact points
7. Statistical aggregation and result export

### Configuration
- Defaults live in `src/utils/config.py` (`Config.DEFAULT_CONFIG`). Override by passing `--config <file>` (YAML or JSON) on the CLI.
- Key settings: `ball_confidence` (0.15 -- MUST match `scripts/test_action_recognition.py`; every GT-validated action number was measured at 0.15, and a diverging default silently flips gestures in production/live-debug), `player_confidence` (0.5), `max_players` (4), `ball_model_path` (optional -- points to a fine-tuned ball model)
- Device selection via `device` config or `--device` CLI: `auto` (default -- picks CUDA > MPS (Apple GPU) > CPU), `cpu`, `cuda`, or `mps`. `make run` uses MPS automatically on Apple Silicon (~1.75x faster than CPU); pass `--device cpu` for deterministic parity with CPU eval baselines.

### Output
- **CSV Export**: Player action counts and frame-by-frame timelines
- **Visualization**: Multi-panel graphs (action totals, per-player breakdown, temporal analysis)
- **Debug Mode**: Real-time visualization with adjustable playback speed

### Model Weights & Training Data
- **Required runtime weights** (git-ignored, keep on disk): `models/volleyball_ball_best.pt` — the fine-tuned ball detector, auto-loaded by `main.py` and the `scripts/test_*` scripts; and `yolov8n.pt` — COCO YOLOv8n used as the player detector (and ball fallback), auto-downloaded by ultralytics.
- **Court detection uses no model.** It is the interactive `CourtCalibration` JSON in `calibrations/`. The `court_model_path` / `weights/court/...` config entries are stale and never loaded — do not wire them up.
- **Training provenance for the ball model** (keep to retrain): `notebooks/finetune_yolo_ball.ipynb` (Colab; base `yolov8n.pt`, `freeze=10`, `imgsz=1280`), `scripts/prepare_dataset_for_training.py`, `scripts/auto_label_balls.py`, and the labeled set `datasets/ball_detection/`. Full workflow in README §"Model Weights & Training".
- **`archive/`** holds unused weights/artifacts (legacy Wilson CNN, leftover base models, the unused court model) and dead code (`motion_ball_tracker.py`, `config_front_video.py`, stray root debug/test scripts) staged for deletion — do not depend on them.

## Ground Truth & Evaluation

- Annotations stored in `ground_truth/` as JSON (see `ground_truth/README.md` for format). Spike events may carry `spike_type` (touch|hard), `attack_zone`/`landing_zone` `{side, zone 1-9}` (each half numbered 1-9 facing its own baseline) and `outcome` (kill|out|dug|blocked).
- `scripts/evaluate.py` computes: ball detection rate, player ID consistency, action precision/recall
- Roboflow recommended for ball detection annotations (export YOLOv8 format for fine-tuning)

## Claude Code Workflow Guidance

### Progress Tracking (STATUS.md)
- `STATUS.md` at the repo root is the cross-session memory: current state, open points (ranked), and a per-session log. The owner returns to this project every 1–3 weeks and relies on it to remember context.
- **Read `STATUS.md` at the start of every session** (before planning work) and treat its Open points as the backlog.
- **Update `STATUS.md` at the end of every session** that changes anything: refresh "Where we are", move finished items into the "Log" (newest first, with dates and commit hashes), re-rank Open points. Commit it together with the work.

### Implementation Strategies
- When asked to implement a new feature, draft a short plan in the conversation and confirm the approach with the user before writing production code.
- Prefer extending existing modules under `src/` over creating new top-level files.
