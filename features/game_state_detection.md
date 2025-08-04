# Game ON/OFF State Detection Implementation Plan

## Problem Statement

The volleyball recognition system currently processes all detected actions equally, without understanding whether the
game is actively in play or in a pause state. This leads to several issues:

1. **Action Context Loss**: Cannot distinguish between a serve (game starting) and a spike (game in progress)
2. **Invalid Action Counting**: Actions during timeouts, breaks, or setup are counted as game actions
3. **Point Tracking Limitation**: No ability to track team scores or understand point-scoring events
4. **Rally Analysis Issues**: Cannot properly segment video into discrete rallies and points

**Goal**: Implement a GAME ON/OFF state detection system that can:

- Distinguish when the ball is actively in play vs. out of play
- Track point scoring for each team
- Provide context for action classification (serve vs spike differentiation)
- Enable proper rally segmentation and statistics
- Modify live video output to reflect game state changes

---

## Strategy Analysis

### Strategy 1: Action Sequence Pattern Analysis

**Approach**: Analyze patterns in detected action sequences to infer game state transitions.

**Core Logic**:

```
GAME OFF → SERVE detected → GAME ON
GAME ON → Extended inactivity (>3 seconds) → GAME OFF
GAME ON → Scoring event pattern → GAME OFF
```

**Implementation**:

- State machine based on action sequence patterns
- Pattern matching for rally start/end sequences
- Temporal analysis of action gaps

**Pros**:

- Simple to implement using existing action classification
- Intuitive volleyball flow logic
- Lightweight computational overhead
- Direct integration with current action classifier

**Cons**:

- Heavily dependent on action classification accuracy
- Vulnerable to false positives/negatives in action detection
- Cannot handle cases where actions are missed
- Difficulty detecting subtle game state changes

**Evaluation Score**: 6/10

---

### Strategy 2: Ball Trajectory and Physics Analysis

**Approach**: Use ball trajectory physics and movement patterns to detect game state transitions.

**Core Logic**:

```
Ball trajectory analysis → Serve detection (specific arc pattern)
Ball velocity → Ball hits ground/out → Point scored
Ball position → Court boundaries → In/out determination
Physics modeling → Realistic vs unrealistic ball behavior
```

**Implementation**:

- Physics-based trajectory analysis module
- Court boundary detection and ball position tracking
- Velocity and acceleration pattern recognition
- Serve vs attack trajectory classification

**Pros**:

- Objective, physics-based detection
- Independent of action classification errors
- Can detect serve vs spike based on trajectory alone
- Robust to player detection failures

**Cons**:

- Requires excellent ball tracking quality
- Complex physics modeling implementation
- Sensitive to camera angle and perspective
- May miss subtle game events not reflected in ball motion

**Evaluation Score**: 7/10

---

### Strategy 3: Multi-Modal Temporal Analysis ⭐ **SELECTED**

**Approach**: Combine action patterns, ball trajectory, player positioning, and temporal gaps for robust game state
detection.

**Core Logic**:

```
Multi-modal state machine combining:
1. Action sequence patterns (serves, rallies)
2. Ball trajectory analysis (physics validation)
3. Player positioning and movement patterns
4. Temporal activity analysis (gaps, pauses)
5. Court position context
```

**Implementation**:

- Central GameStateManager coordinating multiple analysis modules
- Weighted confidence scoring from each modality
- Temporal smoothing and state persistence
- Configurable thresholds and validation rules

**Pros**:

- Highest accuracy through multi-modal redundancy
- Robust to single-point failures in any one detection method
- Extensible architecture for future enhancements
- Builds on existing system components
- Can handle complex edge cases

**Cons**:

- More complex implementation and tuning
- Higher computational overhead
- Requires coordination between multiple systems
- More parameters to configure and optimize

**Evaluation Score**: 9/10

---

## Implementation Plan: Multi-Modal Temporal Analysis

### Phase 1: Core Architecture

#### 1.1 GameStateManager Class

**Location**: `src/analysis/game_state_manager.py`

```python
class GameStateManager:
    """Central coordinator for game state detection using multiple modalities."""

    def __init__(self, config: Dict[str, Any]):
        self.current_state = GameState.GAME_OFF
        self.state_confidence = 0.0
        self.state_history = deque(maxlen=100)

        # Initialize analysis modules
        self.action_analyzer = ActionSequenceAnalyzer(config)
        self.trajectory_analyzer = TrajectoryStateAnalyzer(config)
        self.temporal_analyzer = TemporalActivityAnalyzer(config)
        self.scoring_tracker = ScoreTracker(config)
```

#### 1.2 Game State Enumeration

```python
class GameState(Enum):
    GAME_OFF = "game_off"  # Between points, timeouts
    GAME_ON = "game_on"  # Active rally in progress
    SERVE_PREPARATION = "serve_prep"  # Server preparing
    POINT_SCORED = "point_scored"  # Point just scored
    TIMEOUT = "timeout"  # Official timeout
```

#### 1.3 Integration Point

**Location**: `src/analysis/video_processor.py` (modify `_process_frame` method)

```python
# Add to VideoProcessor._process_frame()
game_state_info = self.game_state_manager.analyze_frame(
    frame_result, frame_number=self.frame_count
)
frame_result["game_state"] = game_state_info
```

### Phase 2: Analysis Modules

#### 2.1 Action Sequence Analyzer

**Location**: `src/analysis/action_sequence_analyzer.py`

**Responsibilities**:

- Detect serve patterns (game starting)
- Identify rally continuation patterns
- Detect typical point-ending sequences
- Validate action temporal coherence

**Key Methods**:

```python
def analyze_action_sequence(self, actions: List[Dict]) -> Dict[str, Any]:
    """Analyze action patterns for game state indicators."""


def detect_serve_sequence(self, recent_actions: List[Dict]) -> float:
    """Confidence that a serve sequence is starting."""


def detect_rally_end_pattern(self, actions: List[Dict]) -> float:
    """Confidence that rally is ending based on action patterns."""
```

#### 2.2 Trajectory State Analyzer

**Location**: `src/analysis/trajectory_state_analyzer.py`

**Responsibilities**:

- Analyze ball trajectory for serve vs attack patterns
- Detect ball hitting ground or going out of bounds
- Validate physics consistency of ball movement
- Track ball possession and contact sequences

**Key Methods**:

```python
def analyze_trajectory_state(self, ball_trajectory: List) -> Dict[str, Any]:
    """Analyze ball trajectory for game state indicators."""


def classify_trajectory_type(self, trajectory_segment: List) -> str:
    """Classify trajectory as serve, attack, defense, etc."""


def detect_point_ending_trajectory(self, trajectory: List) -> float:
    """Confidence that trajectory indicates point ended."""
```

#### 2.3 Temporal Activity Analyzer

**Location**: `src/analysis/temporal_activity_analyzer.py`

**Responsibilities**:

- Track activity levels and gaps between actions
- Detect natural pauses in game flow
- Identify timeout periods and extended breaks
- Monitor player movement patterns

**Key Methods**:

```python
def analyze_activity_patterns(self, frame_results: List) -> Dict[str, Any]:
    """Analyze temporal patterns for game state indicators."""


def detect_activity_gaps(self, timeline: List) -> List[Dict]:
    """Identify significant gaps in game activity."""


def classify_pause_type(self, gap_info: Dict) -> str:
    """Classify type of pause (timeout, between points, etc.)."""
```

#### 2.4 Score Tracker

**Location**: `src/analysis/score_tracker.py`

**Responsibilities**:

- Track points for each team
- Detect point-scoring events
- Maintain game score state
- Handle service rotation logic

### Phase 3: State Machine Logic

#### 3.1 State Transition Rules

```python
# Core state transition logic in GameStateManager
def update_game_state(self, analysis_results: Dict) -> GameState:
    """Update game state based on multi-modal analysis."""

    # Extract confidence scores from each analyzer
    action_confidence = analysis_results.get("action_sequence", {})
    trajectory_confidence = analysis_results.get("trajectory", {})
    temporal_confidence = analysis_results.get("temporal", {})

    # Weighted scoring for state transitions
    if self.current_state == GameState.GAME_OFF:
        serve_probability = (
                action_confidence.get("serve_detected", 0.0) * 0.4 +
                trajectory_confidence.get("serve_trajectory", 0.0) * 0.4 +
                temporal_confidence.get("activity_resuming", 0.0) * 0.2
        )

        if serve_probability > self.config["serve_threshold"]:
            return GameState.GAME_ON

    elif self.current_state == GameState.GAME_ON:
        point_end_probability = (
                action_confidence.get("rally_end_pattern", 0.0) * 0.3 +
                trajectory_confidence.get("point_ending", 0.0) * 0.5 +
                temporal_confidence.get("extended_pause", 0.0) * 0.2
        )

        if point_end_probability > self.config["point_end_threshold"]:
            return GameState.POINT_SCORED
```

#### 3.2 Temporal Smoothing

```python
def apply_temporal_smoothing(self, new_state: GameState) -> GameState:
    """Apply temporal smoothing to prevent rapid state changes."""

    # Require minimum confidence duration for state changes
    min_duration = self.config["min_state_duration_frames"]

    # Check state persistence
    if self.state_persistence_counter < min_duration:
        return self.current_state

    return new_state
```

### Phase 4: Configuration Integration

#### 4.1 Configuration Settings

**Location**: `src/utils/config.py` (add to DEFAULT_CONFIG)

```python
"game_state_detection": {
    "enabled": True,
    "serve_threshold": 0.7,
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
            "out_of_bounds_margin": 30,  # pixels beyond court
            "velocity_drop_threshold": 0.3  # relative velocity drop
        }
    },

    # Temporal analysis
    "temporal_analysis": {
        "activity_smoothing_window": 15,  # frames
        "pause_classification_thresholds": {
            "short_pause": 1.0,  # seconds - between-point pause
            "medium_pause": 5.0,  # seconds - timeout/break
            "long_pause": 15.0  # seconds - extended break
        }
    },

    # Score tracking
    "score_tracking": {
        "max_score_per_set": 25,
        "service_rotation_enabled": True,
        "point_detection_methods": ["trajectory", "action_sequence"]
    }
}
```

### Phase 5: Output Integration

#### 5.1 Enhanced Frame Results

```python
# Enhanced frame_result structure
frame_result = {
    # ... existing fields ...
    "game_state": {
        "current_state": "game_on",
        "state_confidence": 0.85,
        "state_duration_frames": 45,
        "transitions": [
            {
                "from_state": "game_off",
                "to_state": "game_on",
                "frame": 123,
                "confidence": 0.82,
                "trigger": "serve_detected"
            }
        ],
        "analysis_breakdown": {
            "action_sequence": {"serve_detected": 0.9, "rally_active": 0.8},
            "trajectory": {"serve_trajectory": 0.7, "ball_in_play": 0.9},
            "temporal": {"activity_level": 0.85, "gap_analysis": 0.0}
        }
    },
    "score_info": {
        "team_a_score": 12,
        "team_b_score": 8,
        "serving_team": "team_a",
        "point_in_progress": True
    }
}
```

#### 5.2 Enhanced CSV Export

**Location**: `src/output_gen/csv_exporter.py` (add new export method)

```python
def _export_game_state_timeline(self, analysis_results: Dict, output_path: Path):
    """Export game state timeline with score progression."""

    csv_data = []
    for frame_result in analysis_results.get("frame_results", []):
        game_state = frame_result.get("game_state", {})
        score_info = frame_result.get("score_info", {})

        row = {
            "Frame_Index": frame_result["frame_index"],
            "Timestamp_Seconds": frame_result["frame_index"] / fps,
            "Game_State": game_state.get("current_state", "unknown"),
            "State_Confidence": game_state.get("state_confidence", 0.0),
            "Team_A_Score": score_info.get("team_a_score", 0),
            "Team_B_Score": score_info.get("team_b_score", 0),
            "Serving_Team": score_info.get("serving_team", "unknown"),
            "Point_In_Progress": score_info.get("point_in_progress", False)
        }
        csv_data.append(row)
```

### Phase 6: Enhanced Action Classification

#### 6.1 Context-Aware Action Classification

**Location**: `src/recognition/action_classifier.py` (modify `classify_actions` method)

```python
def classify_actions(self, frame, player_detections, ball_info=None,
                     game_state_info=None, **kwargs):
    """Enhanced action classification with game state context."""

    # Get base action classifications
    base_actions = self._classify_base_actions(frame, player_detections, ball_info)

    # Apply game state context
    if game_state_info:
        enhanced_actions = self._apply_game_state_context(
            base_actions, game_state_info
        )
        return enhanced_actions

    return base_actions


def _apply_game_state_context(self, actions: List[Dict],
                              game_state_info: Dict) -> List[Dict]:
    """Apply game state context to refine action classifications."""

    current_state = game_state_info.get("current_state")
    score_info = game_state_info.get("score_info", {})

    for action in actions:
        # Context-aware serve vs spike distinction
        if action["action"] in ["serve", "spike"]:
            if current_state == "game_off" or current_state == "serve_preparation":
                # Bias towards serve when game is starting
                action["action"] = "serve"
                action["context_reason"] = "game_state_starting"
            elif current_state == "game_on":
                # Bias towards spike during active play
                action["action"] = "spike"
                action["context_reason"] = "game_state_active"

        # Add team context if available
        if score_info.get("serving_team"):
            action["team_context"] = {
                "serving_team": score_info["serving_team"],
                "score_context": f"{score_info.get('team_a_score', 0)}-{score_info.get('team_b_score', 0)}"
            }

    return actions
```

---

## Testing Strategy

### Unit Tests

- Individual analyzer module testing
- State transition logic validation
- Configuration parameter validation
- Edge case handling verification

### Integration Tests

- End-to-end game state detection on sample videos
- Multi-modal coordination testing
- Performance benchmarking
- Output format validation

### Validation Videos

- Create test videos with known game states
- Manual annotation of ground truth game states
- Accuracy measurement against ground truth
- Performance testing on various video qualities

---

## Expected Outcomes

### Immediate Benefits

1. **Accurate Serve Detection**: Distinguish serves from spikes with >90% accuracy
2. **Rally Segmentation**: Proper segmentation of rallies with clear start/end points
3. **Point Tracking**: Basic team score tracking functionality
4. **Context-Aware Actions**: Actions classified with proper game context

### Long-term Benefits

1. **Advanced Analytics**: Rally-level statistics and team performance metrics
2. **Game Flow Analysis**: Understanding of game rhythm and patterns
3. **Coaching Insights**: Point-by-point breakdown for tactical analysis
4. **Video Navigation**: Jump to specific game events (serves, points, rallies)

### Performance Targets

- **Accuracy**: >85% game state detection accuracy
- **Latency**: <10ms additional processing time per frame
- **Reliability**: Robust operation across different video qualities and angles
- **Extensibility**: Easy addition of new game state types and rules

---

## Implementation Timeline

### Week 1-2: Core Architecture

- Implement GameStateManager class
- Create game state enumeration and basic state machine
- Integrate with existing VideoProcessor

### Week 3-4: Analysis Modules

- Implement ActionSequenceAnalyzer
- Implement TrajectoryStateAnalyzer
- Implement TemporalActivityAnalyzer

### Week 5: Score Tracking & Integration

- Implement ScoreTracker
- Enhance action classification with context
- Update configuration system

### Week 6: Output & Testing

- Enhance CSV export with game state data
- Implement comprehensive test suite
- Performance optimization and validation

### Week 7: Documentation & Refinement

- Complete documentation
- Fine-tune parameters based on testing
- Prepare for deployment

---

## Configuration Parameters Summary

```yaml
game_state_detection:
  enabled: true
  serve_threshold: 0.7
  point_end_threshold: 0.6
  min_state_duration_frames: 10
  activity_gap_threshold_seconds: 3.0

  action_sequence:
    serve_pattern_window: 30
    rally_end_inactivity_threshold: 90
    action_confidence_threshold: 0.6

  trajectory_analysis:
    serve_trajectory_features:
      min_arc_height: 50
      horizontal_distance_threshold: 200
      velocity_pattern_weight: 0.7
    point_end_detection:
      ground_contact_threshold: 20
      out_of_bounds_margin: 30
      velocity_drop_threshold: 0.3

  temporal_analysis:
    activity_smoothing_window: 15
    pause_classification_thresholds:
      short_pause: 1.0
      medium_pause: 5.0
      long_pause: 15.0

  score_tracking:
    max_score_per_set: 25
    service_rotation_enabled: true
    point_detection_methods: [ "trajectory", "action_sequence" ]
```

This implementation plan provides a comprehensive, robust solution for game state detection that builds upon the
existing volleyball recognition system while adding powerful new capabilities for understanding game context and flow.