# Court Detection Model Weights

This directory contains the trained YOLO11 model weights for volleyball court detection.

## Expected File
- `court_best.pt` - Trained YOLO11 model for volleyball court detection

## Model Training
The model should be trained to detect volleyball courts as either:
1. **Bounding boxes** - Rectangular regions containing the court
2. **Segmentation masks** - Precise court boundary polygons (preferred)

## Model Classes
The model should detect the following class:
- `court` or `volleyball_court` - The main volleyball court area

## Usage
Once you place the `court_best.pt` file in this directory, the system will automatically use YOLO-based court detection instead of geometric methods.

## Fallback Behavior
If the model file is not present or fails to load, the system will automatically fallback to geometric court detection methods.
