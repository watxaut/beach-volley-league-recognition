# Ball Tracking: Reducing Template Matching False Positives

## Problem Statement

The Wilson volleyball template matching system is currently detecting volleyball patterns on player t-shirts and
background objects, leading to false positives. Analysis shows:

- 3-4 detections per frame instead of expected 1 volleyball
- Consistent detections at frame edges (player positions)
- Static or human-motion patterns instead of volleyball physics
- High confidence matches on clothing patterns that resemble Wilson ball designs

## Proposed Solutions

### Solution 1: Motion-Based Filtering + Trajectory Validation ⭐ **RECOMMENDED**

**Approach**: Combine template matching with physics-based motion analysis to distinguish volleyballs from
static/human-attached patterns.

**Key Components**:

- **Optical Flow Tracking**: Track movement patterns between frames
- **Physics Validation**: Apply volleyball-specific trajectory rules (parabolic motion, gravity effects)
- **Velocity Filtering**: Use speed thresholds to eliminate slow-moving objects
- **Motion Pattern Classification**: Distinguish ball physics from human biomechanics

**Advantages**:

- Most distinctive differentiator between balls and t-shirts
- Leverages temporal information that static analysis cannot provide
- Computationally efficient (optical flow is fast)
- Robust across lighting and visual conditions
- Can recover missed balls due to motion blur

**Implementation Strategy**:

1. Run Wilson template matching to get initial candidates
2. Track optical flow for each detection across 3-5 frames
3. Apply trajectory validation:
    - Parabolic motion fitting
    - Gravity acceleration validation (9.8 m/s²)
    - Velocity range constraints (volleyball speeds: 5-30 m/s)
4. Score detections based on motion + template confidence
5. Filter out detections with human-like motion patterns

### Solution 2: Multi-Stage Template Matching with Negative Examples

**Approach**: Enhance template matching with negative templates and contextual filtering.

**Key Components**:

- **Negative Templates**: T-shirt patterns, human torso shapes, common background textures
- **Hierarchical Scoring**: `final_score = positive_template_score - negative_template_score`
- **Contextual Filtering**: Court boundary detection, net location awareness
- **Multi-scale Analysis**: Different template sizes for various perspectives

**Advantages**:

- Direct approach to the visual similarity problem
- Can be tuned with specific false positive patterns
- Maintains pure computer vision approach

**Disadvantages**:

- Requires collecting and maintaining negative template sets
- May not generalize to new clothing patterns or backgrounds
- Higher computational cost due to multiple template matching passes

### Solution 3: Geometric Consistency + Temporal Persistence Filtering

**Approach**: Combine template matching with strict shape validation and temporal analysis.

**Key Components**:

- **Hough Circle Detection**: Secondary validation for circular shape
- **Size Consistency**: Track perspective scaling rules across frames
- **Temporal Filtering**: Real balls appear in motion sequences, clothing patterns are persistent
- **Court Boundary Constraints**: Balls should mostly be within play areas

**Advantages**:

- Leverages volleyball's circular shape
- Uses spatial constraints effectively
- Can eliminate edge-of-frame false positives

**Disadvantages**:

- May miss balls that are partially occluded or motion-blurred
- Less effective when ball appears oval due to perspective/motion
- Relies heavily on court detection accuracy

## Recommended Implementation: Motion-Based Filtering

### Why This Solution is Best

1. **Fundamental Physics Difference**: Volleyballs follow projectile motion with gravity, while t-shirt patterns move
   with human biomechanics - completely different motion signatures.

2. **Temporal Context**: Template matching only sees individual frames, but motion analysis uses time-series data for
   much richer information.

3. **Efficiency**: Optical flow is computationally lightweight compared to multiple template matching passes or complex
   geometric analysis.

4. **Robustness**: Works regardless of lighting changes, court angles, or specific visual patterns on clothing.

5. **Dual Benefit**: Not only eliminates false positives but can also recover true positives that were missed due to
   motion blur or partial occlusion.

### Implementation Architecture

```
Template Detections → Motion Tracker → Physics Validator → Final Detections
       ↓                    ↓               ↓               ↓
   Wilson patterns    Optical flow    Trajectory math   Filtered balls
   (all candidates)   (3-5 frames)    (gravity check)   (high confidence)
```

### Key Parameters

- **Trajectory Window**: 5 frames (0.17 seconds at 30fps)
- **Velocity Range**: 5-30 m/s (reasonable volleyball speeds)
- **Acceleration Tolerance**: 8-12 m/s² (gravity ± air resistance)
- **Motion Score Weight**: 0.6 motion + 0.4 template confidence
- **Minimum Movement**: 10 pixels/frame to exclude static objects

### Success Metrics

- **False Positive Reduction**: Target <1 false positive per 100 frames
- **True Positive Retention**: Maintain >90% of actual volleyball detections
- **Processing Speed**: <5ms additional overhead per frame
- **Trajectory Accuracy**: Correctly predict ball position 3 frames ahead within 20 pixels

This approach transforms template matching from a static pattern detector into a dynamic physics-aware ball tracker,
addressing the fundamental cause of false positives rather than just filtering symptoms.