# Beach Volleyball Tracker: Improvement Plan

## Context

Beach volleyball tracking app to count player stats (sets, spikes, kills, digs, blocks, serves) from video. The system
has ~43 Python files and ~16,000 lines of code. The camera is **fixed on a tripod, perpendicular to the net** -- this
simplifies many problems.

---

## Problem Assessment (by severity)

### CRITICAL -- System cannot produce correct output

| # | Problem                                     | Root Cause                                                         |
|---|---------------------------------------------|--------------------------------------------------------------------|
| 1 | Ball detection tuned for indoor, not beach  | HSV ranges match sand; feature/hybrid methods are dead code        |
| 2 | Ball tracker hallucinates during occlusions | 15% confidence accepted, +0.3 boost, 30-frame extrapolation        |
| 3 | Action recognition fundamentally broken     | Raw pixel Y-coords as thresholds; 4 validation modules kill signal |

### HIGH -- System works poorly

| # | Problem                                    | Root Cause                                                      |
|---|--------------------------------------------|-----------------------------------------------------------------|
| 4 | Player tracking creates ghost IDs          | No max player count; centroid-only; aspect ratio rejects divers |
| 5 | Court detection assumes wrong camera angle | Geometric fallback assumes end-of-court camera                  |
| 6 | MediaPipe static mode causes jitter        | Each frame independent; keypoints jump                          |

---

## Fixed Camera Advantage

| Hard Problem        | Becomes Easy Because                                  |
|---------------------|-------------------------------------------------------|
| Court detection     | Court doesn't move -- define once, use forever        |
| Team assignment     | Net divides frame -- left = Team A, right = Team B    |
| Player count        | Exactly 4 players. Any 5th detection is wrong         |
| Perspective changes | None -- player size at a given Y-coord is constant    |
| Block detection     | Net position is known and fixed -- spatial check only |
| Serve detection     | Baseline position is known and fixed                  |

---

## Implementation Phases

### Phase 0: Ground Truth & Evaluation

**Goal**: Enable measurement so we know if changes help.

- Define JSON annotation format for: ball positions, player boxes + IDs, action events
- Build `scripts/evaluate.py` reporting: ball detection rate, player ID consistency, action precision/recall
- Store annotations in `ground_truth/` directory
- Manually annotate 3 clips (30-60s each) later

**Files created**:

- `ground_truth/README.md` -- annotation format specification
- `scripts/evaluate.py` -- evaluation script

### Phase 1: Court Calibration + Player Locking

#### 1a. Replace court detection with one-time calibration

- Show first frame, user clicks 4 court corners + 2 net post positions
- Save calibration to JSON (reusable across sessions)
- Optional: auto-detect yellow posts via color thresholding
- Bypass `court_detector.py` and `yolo_court_detector.py`
- Output: court polygon, net line, left/right halves

**Files created/modified**:

- `src/detection/court_calibration.py` -- new calibration module
- `src/analysis/frame_processor.py` -- use calibration instead of court_detector

#### 1b. Lock players to exactly 4 with stable IDs

- First N frames: detect people, cluster spatially, keep 4 most persistent
- Assign 2 per side of net (Team A/B)
- Stable IDs 1-4. NEVER create 5th track
- Add color histogram of torso crop for appearance matching
- Remove aspect ratio minimum (1.2 rejects diving players)
- Raise `max_velocity` to 150+ px/frame

**Files modified**:

- `src/tracking/player_tracker.py` -- rebuild with constraints

### Phase 2: Ball Detection & Tracking Simplification

#### 2a. YOLO as primary ball detector

- YOLO sports ball (class 32) as primary method
- Drop template/feature/hybrid methods entirely
- Simplify `ball_detector.py` interface

**Files modified**:

- `src/detection/ball_detector.py` -- simplify to YOLO-only

#### 2b. One conservative ball tracker

- Keep `ball_tracker.py`, delete `enhanced_ball_tracker.py` and `wilson_ball_tracker.py`
- Settings changes:
    - `low_confidence_threshold`: 0.15 -> 0.4
    - `max_trajectory_gap`: 150 -> 60 pixels
    - `max_missing_frames`: 30 -> 10
- When ball is lost, return `None` (stop hallucinating)
- Reject predictions outside court bounds

**Files modified/deleted**:

- `src/tracking/ball_tracker.py` -- conservative settings
- `src/tracking/enhanced_ball_tracker.py` -- DELETE
- `src/tracking/wilson_ball_tracker.py` -- DELETE

### Phase 3: Action Recognition Rebuild

#### 3a. Fix pose features

- Switch MediaPipe to video mode (`static_image_mode=False`)
- Replace raw pixel coords with body-relative ratios:
  ```
  wrist_height_ratio = (wrist_y - hip_y) / (shoulder_y - hip_y)
  ```
- All spatial features normalized by player bounding box

**Files modified**:

- `src/recognition/pose_estimator.py` -- video mode + normalized features

#### 3b. Event-driven classification

Instead of classifying every player every frame, detect **ball trajectory inflection points**, then:

1. Find the inflection frame
2. Find closest player at that moment
3. Classify based on: player pose, court position, ball direction

**Action detection tiers**:

| Tier          | Action       | How to detect                                       | Expected accuracy       |
|---------------|--------------|-----------------------------------------------------|-------------------------|
| 1 (spatial)   | **Serve**    | Behind baseline + rally start                       | 80%+                    |
| 1 (spatial)   | **Block**    | Within 1m of net + arms above shoulders             | 70%+                    |
| 2 (pose+ball) | **Dig**      | Arms below shoulders + ball goes up from low        | 50-60%                  |
| 2 (pose+ball) | **Set**      | Both arms symmetric overhead + moderate upward ball | 40-50%                  |
| 2 (pose+ball) | **Spike**    | Near net + arm asymmetric high + fast downward ball | 40-50%                  |
| 3 (outcome)   | **Ace/Kill** | Serve/spike with no successful return               | Requires rally tracking |

**Files modified/deleted**:

- `src/recognition/action_classifier.py` -- replace with ~300 line event-driven classifier
- `src/recognition/enhanced_ball_contact.py` -- DELETE
- `src/recognition/temporal_contact_validator.py` -- DELETE
- `src/recognition/ball_trajectory_analyzer.py` -- DELETE
- `src/recognition/court_position_validator.py` -- DELETE

### Pipeline Integration

Update `frame_processor.py` to wire all new components together:

- Court calibration instead of court_detector
- 4-player locked tracker
- Simplified ball detection/tracking
- Event-driven action classification

---

## Per-Component Test Scripts

Each component gets a standalone test script in `scripts/`:

| Script                       | Input                                 | Output                                  |
|------------------------------|---------------------------------------|-----------------------------------------|
| `test_court_calibration.py`  | Video path                            | Annotated frame + calibration JSON      |
| `test_ball_detection.py`     | Video + optional ground truth         | Annotated video + detection metrics     |
| `test_ball_tracking.py`      | Video + optional ground truth         | Trajectory video + tracking metrics     |
| `test_player_tracking.py`    | Video + court calibration             | Annotated video with stable IDs         |
| `test_pose_estimation.py`    | Video + court calibration             | Skeleton overlay video + feature dump   |
| `test_action_recognition.py` | Video + court + optional ground truth | Action-labeled video + precision/recall |
| `evaluate.py`                | Predictions + ground truth            | Per-component metrics report            |

---

## Expected Results

| Component                    | Current                | After Improvements |
|------------------------------|------------------------|--------------------|
| Player detection             | Works OK               | 95%+               |
| Player tracking (stable IDs) | Broken (swaps, ghosts) | 85-90%             |
| Court/team assignment        | Broken                 | 95%+ (calibration) |
| Ball detection               | ~20%                   | 50-65%             |
| Serve detection              | Near zero              | 80%+               |
| Block detection              | Near zero              | 70%+               |
| Dig detection                | Near zero              | 50-60%             |
| Set vs Spike                 | Near zero              | 30-50%             |

---

## Priority Order

| # | Task                                       | Impact                    | Effort   |
|---|--------------------------------------------|---------------------------|----------|
| 0 | Ground truth + evaluation script           | Enables measurement       | 1-2 days |
| 1 | Court calibration                          | Unlocks everything        | 2 days   |
| 2 | Lock player count to 4 + ReID              | Fixes player tracking     | 3 days   |
| 3 | MediaPipe video mode + normalized features | Stabilizes pose data      | 1.5 days |
| 4 | YOLO primary ball detection                | Better ball detection     | 2 days   |
| 5 | Single conservative ball tracker           | Stops hallucination       | 2 days   |
| 6 | Event-driven action classification         | Proper action recognition | 5 days   |
| 7 | Delete dead code + simplify                | Maintainability           | 2 days   |

---

## Key Files to Modify

- `src/analysis/frame_processor.py` -- pipeline orchestrator
- `src/tracking/player_tracker.py` -- 4-player constraint + appearance
- `src/recognition/action_classifier.py` -- event-driven classifier
- `src/recognition/pose_estimator.py` -- video mode + body-relative features
- `src/tracking/ball_tracker.py` -- conservative settings
- `src/detection/ball_detector.py` -- YOLO primary only
