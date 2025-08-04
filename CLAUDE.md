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

# With custom output directory and configuration
python -m src.main path/to/video.mp4 --output-dir ./results --config volleyball_detection_config.yaml

# Enable live debug mode with real-time visualization
python -m src.main path/to/video.mp4 --debug-live --debug-speed 0.5

# Skip visualization generation
python -m src.main path/to/video.mp4 --skip-visualization

# Wilson Ball Detection Configuration Examples
python -m src.main video.mp4 --detection-method template  # Template matching
python -m src.main video.mp4 --detection-method features  # Feature-based detection
python -m src.main video.mp4 --detection-method hybrid    # CNN + Classical CV
python -m src.main video.mp4 --detection-method fusion    # All methods combined
```

### Testing
```bash
# Run all tests with coverage
pytest tests/ -v

# Run specific test categories
pytest tests/test_components.py::TestBallDetector -v
pytest tests/test_components.py::TestConfig -v

# Generate coverage report
pytest --cov=src --cov-report=html
```

### Code Quality and Linting
```bash
# Format code with Black
black src/ tests/

# Run type checking with mypy
mypy src/

# Run linting with flake8
flake8 src/ tests/

# Install and run pre-commit hooks
pre-commit install
pre-commit run --all-files
```

### Testing with Sample Videos
Use videos in the `resources/` directory for testing:
- `resources/avp_front_1.mp4` - Front view volleyball match
- `resources/video_front.mov` - Another front view sample
- `resources/video_side.mov` - Side view volleyball

## Project Architecture

### Core Pipeline Architecture
The system follows a modular computer vision pipeline:

1. **Detection Layer** (`src/detection/`): YOLO-based object detection for balls and players
2. **Tracking Layer** (`src/tracking/`): Maintains object identities across frames using trajectory analysis
3. **Recognition Layer** (`src/recognition/`): MediaPipe pose estimation + rule-based action classification
4. **Analysis Layer** (`src/analysis/`): Orchestrates the pipeline and processes video frames
5. **Output Layer** (`src/output_gen/`): Exports results to CSV and generates visualizations

### Key Components

#### Detection System
- **BallDetector**: Multi-method Wilson volleyball detection with 5 configurable approaches:
  1. **YOLO**: Traditional sports ball detection (class ID 32)
  2. **Template Matching**: Multi-scale Wilson ball template matching with color filtering
  3. **Feature-Based**: SIFT/ORB feature matching with geometric verification
  4. **Hybrid CNN**: Lightweight CNN classifier + classical CV candidate detection
  5. **Fusion**: Combines all methods with intelligent detection merging
- **PlayerDetector**: YOLO-based human detection with confidence filtering
- **CourtDetector**: Perspective detection for court boundary analysis

#### Tracking System
- **BallTracker**: Handles high-velocity volleyball trajectories with enhanced prediction algorithms
- **PlayerTracker**: Multi-object tracking with identity management and occlusion handling
- **Enhanced tracking variants**: `wilson_ball_tracker.py` and `enhanced_ball_tracker.py` for specialized scenarios

#### Action Recognition
- **PoseEstimator**: MediaPipe-based human pose estimation
- **ActionClassifier**: Rule-based classifier for volleyball actions (digs, sets, blocks, aces, spikes)

#### Configuration Management
- Uses YAML configuration files (`volleyball_detection_config.yaml`)
- Default settings tuned for volleyball: low confidence thresholds (0.05), high velocity tracking (200.0)
- Supports CPU/CUDA device selection

### Video Processing Flow
1. Frame extraction and preprocessing
2. Parallel ball and player detection using YOLO
3. Trajectory-based tracking with occlusion handling
4. Pose estimation for detected players
5. Temporal action classification using pose sequences
6. Statistical aggregation and result export

### Model Integration
- **YOLO Models**: Uses `yolov8n.pt` (standard) and `volleyball_optimized_yolov8.pt` (custom-trained)
- **MediaPipe**: Integrated for real-time pose estimation
- **Custom Models**: Support for specialized volleyball detection models via configuration

### Output Generation
- **CSV Export**: Player action counts and frame-by-frame timelines
- **Visualization**: Multi-panel graphs (action totals, per-player breakdown, temporal analysis)
- **Debug Mode**: Real-time visualization with adjustable playback speed

### Development Considerations
- Code follows strict type hints and comprehensive docstrings
- Performance optimized for video processing workloads
- Robust error handling for various video formats and qualities
- Configurable thresholds for different volleyball scenarios (indoor/outdoor, camera angles)

## Wilson Volleyball Detection Methods

### Available Detection Approaches

#### 1. Template Matching (`wilson_template_detector.py`)
- **Method**: Multi-scale template matching using Wilson ball reference images
- **Features**: HSV color space analysis, morphological filtering, non-max suppression
- **Best for**: Consistent lighting, clear ball visibility, similar camera angles
- **Strengths**: Fast, interpretable, works well with static backgrounds

#### 2. Feature-Based Detection (`wilson_feature_detector.py`)
- **Method**: SIFT/ORB feature extraction and matching with geometric verification
- **Features**: Rotation/scale invariant, homography estimation, robust matching
- **Best for**: Variable viewpoints, partial occlusions, scale changes
- **Strengths**: Robust to transformations, handles perspective changes

#### 3. Hybrid CNN + Classical CV (`wilson_hybrid_detector.py`)
- **Method**: Lightweight CNN classifier with classical CV candidate detection
- **Features**: Color-based pre-filtering, Hough circle detection, CNN validation
- **Best for**: Complex backgrounds, varying ball conditions, general robustness
- **Strengths**: Learns discriminative features, adapts to variations

#### 4. Multi-Method Fusion (`detection_method="fusion"`)
- **Method**: Combines all three approaches with intelligent detection merging
- **Features**: Spatial clustering, confidence boosting, method agreement scoring
- **Best for**: Maximum accuracy, diverse video conditions, production use
- **Strengths**: Highest reliability, leverages all method strengths

### Configuration Examples

```python
# Configure different detection methods
from src.detection.ball_detector import BallDetector

# Template-based detection
detector = BallDetector(detection_method="template", confidence_threshold=0.6)

# Feature-based detection
detector = BallDetector(detection_method="features", confidence_threshold=0.5)

# Hybrid CNN detection
detector = BallDetector(detection_method="hybrid", confidence_threshold=0.7)

# Multi-method fusion (recommended)
detector = BallDetector(detection_method="fusion", enable_multiple_methods=True)
```

### Wilson Ball Reference Images
- Located in `resources/wilson_ball/` directory
- Contains 8 reference images (img.png through img_7.png)
- Images show Wilson volleyball from different angles and lighting
- Used by template and feature-based methods for training/matching

### File Structure Notes
- `src/main.py`: Entry point with comprehensive CLI argument parsing
- Configuration files support both YAML and JSON formats
- Live debug processor provides real-time development feedback
- Test suite covers core components with sample video validation
- Wilson detection modules are standalone and can be used independently

## Claude Code Workflow Guidance

### Implementation Strategies
- When told to "implement a new feature":
  * Write down an implementation plan
  * Consider 3 different implementation strategies
  * Select the best strategy
  * Create the feature in the @features/ folder first
  * Do not write actual code implementation initially