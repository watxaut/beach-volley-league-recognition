"""
Wilson Ball CNN Tracker - Plan 3 Implementation

This module implements a custom CNN + multi-method tracking fusion approach
specifically designed for Wilson volleyball tracking using the reference images.
"""

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import deque
import albumentations as A
from albumentations.pytorch import ToTensorV2

class WilsonBallDataset(Dataset):
    """Dataset for training Wilson ball detection CNN."""

    def __init__(self, positive_images_dir: str, negative_samples_count: int = 1000,
                 image_size: int = 64, augment: bool = True):
        """
        Initialize Wilson ball dataset.

        Args:
            positive_images_dir: Path to wilson_ball/ directory
            negative_samples_count: Number of negative samples to generate
            image_size: Size to resize images to
            augment: Whether to apply data augmentation
        """
        self.positive_dir = Path(positive_images_dir)
        self.image_size = image_size
        self.samples = []
        self.labels = []

        # Setup augmentation pipeline
        if augment:
            self.transform = A.Compose([
                A.Resize(image_size, image_size),
                A.HorizontalFlip(p=0.5),
                A.VerticalFlip(p=0.3),
                A.Rotate(limit=30, p=0.7),
                A.RandomBrightnessContrast(p=0.5),
                A.GaussianBlur(blur_limit=3, p=0.3),
                A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ToTensorV2()
            ])
        else:
            self.transform = A.Compose([
                A.Resize(image_size, image_size),
                A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ToTensorV2()
            ])

        self._load_samples()

    def _load_samples(self):
        """Load positive and negative samples."""
        # Load positive samples (Wilson balls)
        positive_files = list(self.positive_dir.glob("*.png")) + list(self.positive_dir.glob("*.jpg"))

        for img_path in positive_files:
            img = cv2.imread(str(img_path))
            if img is not None:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                self.samples.append(img)
                self.labels.append(1)  # Positive label

        # Generate negative samples (random patches from backgrounds)
        self._generate_negative_samples()

        print(f"Dataset loaded: {len([l for l in self.labels if l == 1])} positive, "
              f"{len([l for l in self.labels if l == 0])} negative samples")

    def _generate_negative_samples(self):
        """Generate negative samples from random patches."""
        # For now, create random noise as negative samples
        # In a real implementation, you'd extract patches from volleyball court backgrounds
        for _ in range(len(self.samples)):  # Balance the dataset
            # Generate random noise image
            noise_img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
            self.samples.append(noise_img)
            self.labels.append(0)  # Negative label

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        image = self.samples[idx]
        label = self.labels[idx]

        # Apply transforms
        transformed = self.transform(image=image)
        image = transformed['image']

        return image, torch.tensor(label, dtype=torch.float32)


class WilsonBallCNN(nn.Module):
    """Lightweight CNN for Wilson ball detection."""

    def __init__(self, input_size: int = 64):
        """
        Initialize Wilson ball CNN.

        Args:
            input_size: Input image size (assumed square)
        """
        super(WilsonBallCNN, self).__init__()

        self.features = nn.Sequential(
            # First conv block
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Second conv block
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Third conv block
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Fourth conv block
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((4, 4))
        )

        self.classifier = nn.Sequential(
            nn.Dropout(0.5),
            nn.Linear(256 * 4 * 4, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(512, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


class WilsonBallTracker:
    """
    Complete Wilson Ball Tracking System using CNN + Multi-Method Fusion.

    Combines:
    1. Custom CNN for Wilson-specific detection
    2. Template matching for confirmation
    3. Feature matching for tracking continuity
    4. Kalman filter for smooth trajectories
    """

    def __init__(self, wilson_ball_dir: str = "resources/wilson_ball",
                 device: str = "cpu"):
        """
        Initialize Wilson ball tracker.

        Args:
            wilson_ball_dir: Path to Wilson ball reference images
            device: Device for CNN inference ("cpu" or "cuda")
        """
        self.wilson_ball_dir = Path(wilson_ball_dir)
        self.device = device
        self.logger = logging.getLogger(__name__)

        # CNN components
        self.cnn_model = None
        self.cnn_transform = None
        self.detection_window_size = 64
        self.detection_stride = 16
        self.cnn_threshold = 0.7

        # Template matching components
        self.templates = []
        self.template_scales = [0.5, 0.75, 1.0, 1.25, 1.5]
        self.template_threshold = 0.6

        # Feature matching components
        self.reference_features = []
        self.feature_detector = cv2.SIFT_create()
        self.matcher = cv2.FlannBasedMatcher()
        self.min_match_count = 8

        # Tracking components
        self.kalman_filter = self._initialize_kalman_filter()
        self.trajectory = deque(maxlen=100)
        self.missing_frames = 0
        self.max_missing_frames = 15

        # Detection fusion
        self.detection_history = deque(maxlen=5)

        # Initialize all components
        self._initialize_components()

    def _initialize_components(self):
        """Initialize all tracking components."""
        self.logger.info("Initializing Wilson ball tracker components...")

        # Load and prepare templates
        self._load_templates()

        # Extract reference features
        self._extract_reference_features()

        # Initialize CNN (will train if no model exists)
        self._initialize_cnn()

        self.logger.info("Wilson ball tracker initialized successfully")

    def _load_templates(self):
        """Load Wilson ball images as templates for template matching."""
        template_files = list(self.wilson_ball_dir.glob("*.png")) + \
                        list(self.wilson_ball_dir.glob("*.jpg"))

        for template_path in template_files:
            template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
            if template is not None:
                # Resize template to standard size
                template = cv2.resize(template, (32, 32))
                self.templates.append(template)

        self.logger.info(f"Loaded {len(self.templates)} Wilson ball templates")

    def _extract_reference_features(self):
        """Extract SIFT features from Wilson ball reference images."""
        template_files = list(self.wilson_ball_dir.glob("*.png")) + \
                        list(self.wilson_ball_dir.glob("*.jpg"))

        for template_path in template_files:
            img = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                keypoints, descriptors = self.feature_detector.detectAndCompute(img, None)
                if descriptors is not None:
                    self.reference_features.append(descriptors)

        self.logger.info(f"Extracted features from {len(self.reference_features)} reference images")

    def _initialize_cnn(self):
        """Initialize or train the CNN model."""
        model_path = Path("wilson_ball_cnn.pth")

        if model_path.exists():
            # Load existing model
            self.cnn_model = WilsonBallCNN()
            self.cnn_model.load_state_dict(torch.load(model_path, map_location=self.device))
            self.cnn_model.eval()
            self.logger.info("Loaded existing Wilson ball CNN model")
        else:
            # Train new model
            self.logger.info("Training new Wilson ball CNN model...")
            self._train_cnn()

        # Setup preprocessing
        self.cnn_transform = A.Compose([
            A.Resize(64, 64),
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ToTensorV2()
        ])

    def _train_cnn(self):
        """Train the Wilson ball CNN."""
        # Create dataset
        dataset = WilsonBallDataset(
            positive_images_dir=str(self.wilson_ball_dir),
            image_size=64,
            augment=True
        )

        # Split into train/val
        train_size = int(0.8 * len(dataset))
        val_size = len(dataset) - train_size
        train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])

        # Create data loaders
        train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)

        # Initialize model
        self.cnn_model = WilsonBallCNN()
        criterion = nn.BCELoss()
        optimizer = optim.Adam(self.cnn_model.parameters(), lr=0.001)

        # Training loop
        num_epochs = 20
        best_val_acc = 0.0

        for epoch in range(num_epochs):
            # Training phase
            self.cnn_model.train()
            train_loss = 0.0
            train_correct = 0
            train_total = 0

            for images, labels in train_loader:
                optimizer.zero_grad()
                outputs = self.cnn_model(images)
                loss = criterion(outputs.squeeze(), labels)
                loss.backward()
                optimizer.step()

                train_loss += loss.item()
                predicted = (outputs.squeeze() > 0.5).float()
                train_total += labels.size(0)
                train_correct += (predicted == labels).sum().item()

            # Validation phase
            self.cnn_model.eval()
            val_loss = 0.0
            val_correct = 0
            val_total = 0

            with torch.no_grad():
                for images, labels in val_loader:
                    outputs = self.cnn_model(images)
                    loss = criterion(outputs.squeeze(), labels)

                    val_loss += loss.item()
                    predicted = (outputs.squeeze() > 0.5).float()
                    val_total += labels.size(0)
                    val_correct += (predicted == labels).sum().item()

            train_acc = 100 * train_correct / train_total
            val_acc = 100 * val_correct / val_total

            print(f"Epoch {epoch+1}/{num_epochs}")
            print(f"Train Loss: {train_loss/len(train_loader):.4f}, Train Acc: {train_acc:.2f}%")
            print(f"Val Loss: {val_loss/len(val_loader):.4f}, Val Acc: {val_acc:.2f}%")

            # Save best model
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                torch.save(self.cnn_model.state_dict(), "wilson_ball_cnn.pth")

        self.logger.info(f"CNN training completed. Best validation accuracy: {best_val_acc:.2f}%")

    def _initialize_kalman_filter(self):
        """Initialize Kalman filter for ball tracking."""
        kalman = cv2.KalmanFilter(4, 2)
        kalman.measurementMatrix = np.array([[1, 0, 0, 0],
                                           [0, 1, 0, 0]], np.float32)
        kalman.transitionMatrix = np.array([[1, 0, 1, 0],
                                          [0, 1, 0, 1],
                                          [0, 0, 1, 0],
                                          [0, 0, 0, 1]], np.float32)
        kalman.processNoiseCov = 0.03 * np.eye(4, dtype=np.float32)
        return kalman

    def detect_wilson_ball(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Detect Wilson ball using multi-method fusion.

        Args:
            frame: Input video frame

        Returns:
            Detection result with center, confidence, and method used
        """
        # Method 1: CNN sliding window detection
        cnn_detections = self._detect_with_cnn(frame)

        # Method 2: Template matching
        template_detections = self._detect_with_templates(frame)

        # Method 3: Feature matching (if we have previous detection)
        feature_detections = self._detect_with_features(frame)

        # Method 4: Kalman filter prediction
        kalman_prediction = self._predict_with_kalman()

        # Fusion: Combine all detection methods
        best_detection = self._fuse_detections(
            cnn_detections, template_detections,
            feature_detections, kalman_prediction
        )

        # Update tracking state
        if best_detection:
            self._update_tracking_state(best_detection)
        else:
            self.missing_frames += 1
            if self.missing_frames > self.max_missing_frames:
                self._reset_tracker()

        return best_detection

    def _detect_with_cnn(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect Wilson ball using CNN sliding window."""
        if self.cnn_model is None:
            return []

        detections = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = gray.shape[:2]

        # Sliding window detection
        for y in range(0, h - self.detection_window_size, self.detection_stride):
            for x in range(0, w - self.detection_window_size, self.detection_stride):
                # Extract window
                window = gray[y:y+self.detection_window_size, x:x+self.detection_window_size]

                # Preprocess for CNN
                transformed = self.cnn_transform(image=window)
                input_tensor = transformed['image'].unsqueeze(0)

                # CNN inference
                with torch.no_grad():
                    confidence = self.cnn_model(input_tensor).item()

                if confidence > self.cnn_threshold:
                    center_x = x + self.detection_window_size // 2
                    center_y = y + self.detection_window_size // 2

                    detections.append({
                        'center': [center_x, center_y],
                        'confidence': confidence,
                        'method': 'cnn',
                        'bbox': [x, y, x + self.detection_window_size, y + self.detection_window_size]
                    })

        # Non-maximum suppression to remove overlapping detections
        return self._non_max_suppression(detections)

    def _detect_with_templates(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect Wilson ball using template matching."""
        detections = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        for template in self.templates:
            for scale in self.template_scales:
                # Scale template
                h, w = template.shape
                scaled_template = cv2.resize(template, (int(w * scale), int(h * scale)))

                # Template matching
                result = cv2.matchTemplate(gray, scaled_template, cv2.TM_CCOEFF_NORMED)
                locations = np.where(result >= self.template_threshold)

                for pt in zip(*locations[::-1]):
                    confidence = result[pt[1], pt[0]]
                    center_x = pt[0] + scaled_template.shape[1] // 2
                    center_y = pt[1] + scaled_template.shape[0] // 2

                    detections.append({
                        'center': [center_x, center_y],
                        'confidence': float(confidence),
                        'method': 'template',
                        'bbox': [pt[0], pt[1], pt[0] + scaled_template.shape[1], pt[1] + scaled_template.shape[0]]
                    })

        return self._non_max_suppression(detections)

    def _detect_with_features(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect Wilson ball using feature matching."""
        if not self.reference_features or len(self.trajectory) == 0:
            return []

        detections = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Get search region around last known position
        last_pos = self.trajectory[-1]
        search_radius = 100

        x1 = max(0, int(last_pos[0] - search_radius))
        y1 = max(0, int(last_pos[1] - search_radius))
        x2 = min(gray.shape[1], int(last_pos[0] + search_radius))
        y2 = min(gray.shape[0], int(last_pos[1] + search_radius))

        search_region = gray[y1:y2, x1:x2]

        # Extract features from search region
        kp, desc = self.feature_detector.detectAndCompute(search_region, None)

        if desc is not None:
            for ref_desc in self.reference_features:
                if len(ref_desc) < 2:
                    continue

                # Match features
                matches = self.matcher.knnMatch(ref_desc, desc, k=2)

                # Apply Lowe's ratio test
                good_matches = []
                for match_pair in matches:
                    if len(match_pair) == 2:
                        m, n = match_pair
                        if m.distance < 0.7 * n.distance:
                            good_matches.append(m)

                if len(good_matches) >= self.min_match_count:
                    # Estimate ball center from matched keypoints
                    matched_kp = [kp[m.trainIdx] for m in good_matches]
                    if matched_kp:
                        x_coords = [kp.pt[0] for kp in matched_kp]
                        y_coords = [kp.pt[1] for kp in matched_kp]

                        center_x = int(np.mean(x_coords)) + x1
                        center_y = int(np.mean(y_coords)) + y1
                        confidence = min(1.0, len(good_matches) / 20.0)

                        detections.append({
                            'center': [center_x, center_y],
                            'confidence': confidence,
                            'method': 'features',
                            'bbox': [center_x - 20, center_y - 20, center_x + 20, center_y + 20]
                        })

        return detections

    def _predict_with_kalman(self) -> Optional[Dict[str, Any]]:
        """Predict ball position using Kalman filter."""
        if len(self.trajectory) == 0:
            return None

        try:
            prediction = self.kalman_filter.predict()
            predicted_x = int(prediction[0])
            predicted_y = int(prediction[1])

            return {
                'center': [predicted_x, predicted_y],
                'confidence': 0.5,  # Medium confidence for predictions
                'method': 'kalman',
                'bbox': [predicted_x - 15, predicted_y - 15, predicted_x + 15, predicted_y + 15]
            }
        except:
            return None

    def _fuse_detections(self, cnn_detections, template_detections,
                        feature_detections, kalman_prediction) -> Optional[Dict[str, Any]]:
        """Fuse detections from multiple methods."""
        all_detections = []

        # Add all detections with method-specific confidence weights
        for det in cnn_detections:
            det['weighted_confidence'] = det['confidence'] * 1.0  # CNN gets full weight
            all_detections.append(det)

        for det in template_detections:
            det['weighted_confidence'] = det['confidence'] * 0.8  # Template gets 80% weight
            all_detections.append(det)

        for det in feature_detections:
            det['weighted_confidence'] = det['confidence'] * 0.9  # Features get 90% weight
            all_detections.append(det)

        if kalman_prediction:
            kalman_prediction['weighted_confidence'] = kalman_prediction['confidence'] * 0.6  # Kalman gets 60% weight
            all_detections.append(kalman_prediction)

        if not all_detections:
            return None

        # If we have trajectory history, prefer detections close to predicted path
        if len(self.trajectory) >= 2:
            # Calculate expected position based on trajectory
            last_pos = self.trajectory[-1]
            prev_pos = self.trajectory[-2]
            expected_x = last_pos[0] + (last_pos[0] - prev_pos[0])
            expected_y = last_pos[1] + (last_pos[1] - prev_pos[1])

            # Boost confidence for detections near expected position
            for det in all_detections:
                distance = np.sqrt((det['center'][0] - expected_x)**2 + (det['center'][1] - expected_y)**2)
                proximity_boost = max(0, 1.0 - distance / 100.0)  # Boost decreases with distance
                det['weighted_confidence'] += proximity_boost * 0.3

        # Return detection with highest weighted confidence
        best_detection = max(all_detections, key=lambda x: x['weighted_confidence'])

        # Only return if confidence is above threshold
        if best_detection['weighted_confidence'] > 0.4:
            return best_detection

        return None

    def _update_tracking_state(self, detection: Dict[str, Any]):
        """Update tracking state with new detection."""
        center = detection['center']

        # Add to trajectory
        self.trajectory.append(center)
        self.missing_frames = 0

        # Update Kalman filter
        if len(self.trajectory) == 1:
            # Initialize Kalman filter
            self.kalman_filter.statePre = np.array([center[0], center[1], 0, 0], dtype=np.float32)
            self.kalman_filter.statePost = np.array([center[0], center[1], 0, 0], dtype=np.float32)
        else:
            # Correct Kalman filter with measurement
            measurement = np.array([[center[0]], [center[1]]], dtype=np.float32)
            self.kalman_filter.correct(measurement)

        # Add to detection history for analysis
        self.detection_history.append(detection)

    def _reset_tracker(self):
        """Reset tracker state."""
        self.trajectory.clear()
        self.detection_history.clear()
        self.missing_frames = 0
        self.kalman_filter = self._initialize_kalman_filter()

    def _non_max_suppression(self, detections: List[Dict[str, Any]],
                           iou_threshold: float = 0.3) -> List[Dict[str, Any]]:
        """Apply non-maximum suppression to remove overlapping detections."""
        if not detections:
            return []

        # Sort by confidence
        detections = sorted(detections, key=lambda x: x['confidence'], reverse=True)

        keep = []
        while detections:
            # Keep the highest confidence detection
            current = detections.pop(0)
            keep.append(current)

            # Remove overlapping detections
            remaining = []
            for det in detections:
                if self._calculate_iou(current['bbox'], det['bbox']) < iou_threshold:
                    remaining.append(det)
            detections = remaining

        return keep

    def _calculate_iou(self, box1: List[int], box2: List[int]) -> float:
        """Calculate Intersection over Union (IoU) of two bounding boxes."""
        x1_inter = max(box1[0], box2[0])
        y1_inter = max(box1[1], box2[1])
        x2_inter = min(box1[2], box2[2])
        y2_inter = min(box1[3], box2[3])

        if x2_inter <= x1_inter or y2_inter <= y1_inter:
            return 0.0

        inter_area = (x2_inter - x1_inter) * (y2_inter - y1_inter)
        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])

        union_area = box1_area + box2_area - inter_area
        return inter_area / union_area if union_area > 0 else 0.0
