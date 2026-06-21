# Beach Volleyball Video Analysis System

A comprehensive computer vision system for analyzing beach volleyball videos, detecting players and ball, tracking movements, and recognizing actions (digs, sets, blocks, aces, spikes).

## Features

- **Player Detection & Tracking**: Uses YOLO for detecting players and maintains consistent identities across frames
- **Ball Detection & Tracking**: Detects volleyball and tracks trajectory with occlusion handling
- **Action Recognition**: Recognizes volleyball-specific actions using pose estimation and temporal analysis
- **Statistical Analysis**: Generates comprehensive statistics and performance metrics
- **Multiple Output Formats**: Exports results to CSV and creates visualization graphs

## System Requirements

- Python 3.11 or higher
- CPU or CUDA-compatible GPU
- 8GB+ RAM recommended for video processing

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd volley_recognition
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies using uv:
```bash
pip install uv
uv pip install -e .
```

## Quick Start

### Basic Usage

Analyze a volleyball video:
```bash
python -m src.main path/to/your/video.mp4
```

### Advanced Usage

With custom output directory and configuration:
```bash
python -m src.main path/to/your/video.mp4 \
    --output-dir ./results \
    --config config.yaml \
    --log-level DEBUG
```

## Configuration

The system can be configured using a YAML or JSON file. Default configuration:

```yaml
# Device settings
device: "cpu"  # or "cuda" for GPU

# Detection thresholds
ball_confidence: 0.7
player_confidence: 0.5
max_players: 4

# Tracking parameters
ball_max_missing: 30
player_max_disappeared: 30
tracking_max_distance: 100.0

# Recognition settings
pose_confidence: 0.5
action_confidence: 0.7
temporal_window: 10

# Output settings
save_debug_frames: false
```

## Project Structure

```
volley_recognition/
├── src/
│   ├── main.py                    # Entry point
│   ├── detection/                 # Object detection modules
│   │   ├── ball_detector.py       # Ball detection using YOLO
│   │   ├── player_detector.py     # Player detection using YOLO
│   │   ├── court_calibration.py   # One-time interactive court + net calibration
│   │   └── base_detector.py       # Abstract base class
│   ├── tracking/                  # Object tracking modules
│   │   ├── ball_tracker.py        # Ball trajectory tracking
│   │   └── player_tracker.py      # Multi-player tracking
│   ├── recognition/               # Action recognition modules
│   │   ├── pose_estimator.py      # MediaPipe pose estimation
│   │   └── action_classifier.py   # Volleyball action classification
│   ├── analysis/                  # Video processing and statistics
│   │   ├── video_processor.py     # Main processing pipeline
│   │   └─��� statistics.py          # Statistical analysis
│   ├── output_gen/                # Export and visualization
│   │   ├── csv_exporter.py        # CSV export functionality
│   │   └── visualization.py       # Graph generation
│   └── utils/                     # Utility modules
│       ├── config.py              # Configuration management
│       └── logger.py              # Logging utilities
├── tests/                         # Unit tests
├── resources/                     # Sample videos
├── pyproject.toml                 # Project configuration
└── README.md                      # This file
```

## Output Files

The system generates three main output files:

1. **results.csv**: Player action summary with counts per player
2. **results_detailed.csv**: Frame-by-frame action timeline
3. **summary_graphs.png**: Visualization graphs including:
   - Total action counts bar chart
   - Per-player action breakdown
   - Game activity over time
   - Action distribution pie chart

## Supported Actions

- **Digs**: Defensive plays where players dive or crouch to retrieve the ball
- **Sets**: Overhead ball placement for attacking plays
- **Spikes**: Attacking hits with high arm extension
- **Blocks**: Defensive actions at the net with raised arms
- **Aces**: Direct scoring serves
- **Serves**: Ball service actions

## Technical Details

### Computer Vision Pipeline

1. **Frame Processing**: Each video frame is processed through the pipeline
2. **Object Detection**: YOLO models detect players and ball
3. **Object Tracking**: Maintains consistent identities across frames
4. **Pose Estimation**: MediaPipe extracts human pose keypoints
5. **Action Classification**: Rule-based classifier recognizes volleyball actions
6. **Statistical Analysis**: Aggregates results and generates insights

### Performance Considerations

- **GPU Acceleration**: Use CUDA for faster processing on compatible hardware
- **Frame Skipping**: Configure `frame_skip` to process every nth frame for speed
- **Batch Processing**: Optimized for processing multiple videos
- **Memory Management**: Efficient memory usage for long videos

## Testing

Run the test suite:
```bash
python -m pytest tests/ -v
```

Run specific test categories:
```bash
# Test detection components
python -m pytest tests/test_components.py::TestBallDetector -v

# Test configuration
python -m pytest tests/test_components.py::TestConfig -v
```

## Development

### Adding New Actions

To add a new volleyball action:

1. Add the action to `VolleyballAction` enum in `action_classifier.py`
2. Implement scoring logic in `ActionClassifier._calculate_action_scores()`
3. Update visualization colors in `VisualizationGenerator`
4. Add tests for the new action

### Custom Models

Replace default YOLO models:
```yaml
ball_model_path: "path/to/custom/ball_model.pt"
player_model_path: "path/to/custom/player_model.pt"
```

### Debug Mode

Enable debug frame saving:
```yaml
save_debug_frames: true
debug_output_dir: "./debug_frames"
```

## Troubleshooting

### Common Issues

1. **CUDA out of memory**: Reduce batch size or use CPU
2. **Low detection accuracy**: Adjust confidence thresholds
3. **Missing ball detections**: Lower `ball_confidence` threshold
4. **Player tracking issues**: Increase `tracking_max_distance`

### Performance Optimization

- Use GPU acceleration: `device: "cuda"`
- Process every nth frame: `frame_skip: 2`
- Reduce model complexity: `pose_complexity: 0`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## License

[MIT License](LICENSE)

## Citation

If you use this system in research, please cite:
```bibtex
@software{volleyball_analysis,
  title={Beach Volleyball Video Analysis System},
  author={Joan Heredia},
  year={2025},
  url={https://github.com/your-repo/volley_recognition}
}
```
