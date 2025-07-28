"""
Wilson Volleyball Hybrid CNN + Classical CV Detection - Approach 3

This module implements a hybrid approach combining a lightweight CNN classifier
with classical computer vision techniques for Wilson volleyball detection.
"""

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import logging
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import albumentations as A
from albumentations.pytorch import ToTensorV2


class WilsonBallDataset(Dataset):
    """Dataset for training Wilson ball CNN classifier."""

    def __init__(self, positive_dir: str, negative_samples: List[np.ndarray], 
                 image_size: int = 64, augment: bool = True):
        """
        Initialize dataset.

        Args:
            positive_dir: Directory with Wilson ball images
            negative_samples: List of negative sample images
            image_size: Size to resize images to
            augment: Whether to apply augmentation
        """
        self.positive_dir = Path(positive_dir)
        self.image_size = image_size
        self.samples = []
        self.labels = []

        # Setup augmentation
        if augment:
            self.transform = A.Compose([
                A.Resize(image_size, image_size),
                A.HorizontalFlip(p=0.5),
                A.VerticalFlip(p=0.3),
                A.Rotate(limit=30, p=0.7),
                A.RandomBrightnessContrast(brightness_limit=0.3, contrast_limit=0.3, p=0.5),
                A.GaussianBlur(blur_limit=3, p=0.3),
                A.GaussNoise(var_limit=(10.0, 50.0), p=0.3),
                A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ToTensorV2()
            ])
        else:
            self.transform = A.Compose([
                A.Resize(image_size, image_size),
                A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ToTensorV2()
            ])

        self._load_samples(negative_samples)

    def _load_samples(self, negative_samples: List[np.ndarray]):
        """Load positive and negative samples."""
        # Load positive samples
        positive_files = list(self.positive_dir.glob("*.png")) + list(self.positive_dir.glob("*.jpg"))
        
        for img_path in positive_files:
            img = cv2.imread(str(img_path))
            if img is not None:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                self.samples.append(img)
                self.labels.append(1)

        # Add negative samples
        for neg_img in negative_samples:
            if len(neg_img.shape) == 3:
                neg_img = cv2.cvtColor(neg_img, cv2.COLOR_BGR2RGB)
            self.samples.append(neg_img)
            self.labels.append(0)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        image = self.samples[idx]
        label = self.labels[idx]

        transformed = self.transform(image=image)
        image = transformed['image']

        return image, torch.tensor(label, dtype=torch.float32)


class WilsonBallCNN(nn.Module):
    """Lightweight CNN for Wilson ball classification."""

    def __init__(self, input_size: int = 64):
        """Initialize CNN."""
        super(WilsonBallCNN, self).__init__()
        
        self.features = nn.Sequential(
            # First block
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            
            # Second block
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            
            # Third block
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            
            # Fourth block
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((4, 4))
        )
        
        self.classifier = nn.Sequential(
            nn.Dropout(0.5),
            nn.Linear(256 * 4 * 4, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
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


class WilsonHybridDetector:
    """
    Hybrid Wilson volleyball detector combining CNN classification 
    with classical computer vision techniques.
    """

    def __init__(
        self,
        template_dir: str = "resources/wilson_ball",
        confidence_threshold: float = 0.7,
        device: str = "cpu"
    ):
        """
        Initialize hybrid detector.

        Args:
            template_dir: Directory with Wilson ball reference images
            confidence_threshold: Minimum confidence for detection
            device: Device for CNN inference
        """
        self.template_dir = Path(template_dir)
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.logger = logging.getLogger(__name__)
        
        # CNN components
        self.cnn_model = None
        self.cnn_transform = None
        self.patch_size = 64
        
        # Classical CV components - Wilson volleyball specific colors
        self.yellow_lower = np.array([22, 150, 180])  # More saturated bright yellow
        self.yellow_upper = np.array([28, 255, 255])
        self.orange_lower = np.array([8, 180, 180])   # Higher saturation orange/red
        self.orange_upper = np.array([18, 255, 255])
        
        # Circular detection parameters
        self.hough_params = {
            'dp': 1,
            'min_dist': 30,
            'param1': 50,
            'param2': 30,
            'min_radius': 10,
            'max_radius': 100
        }
        
        self._initialize_components()

    def _initialize_components(self):
        """Initialize CNN and other components."""
        self.logger.info("Initializing Wilson hybrid detector...")
        
        # Setup CNN preprocessing
        self.cnn_transform = A.Compose([
            A.Resize(self.patch_size, self.patch_size),
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ToTensorV2()
        ])
        
        # Initialize or train CNN
        self._initialize_cnn()
        
        self.logger.info("Wilson hybrid detector initialized")

    def _initialize_cnn(self):
        """Initialize or train CNN model."""
        model_path = Path("wilson_ball_hybrid_cnn.pth")
        
        if model_path.exists():
            # Load existing model
            self.cnn_model = WilsonBallCNN()
            self.cnn_model.load_state_dict(torch.load(model_path, map_location=self.device))
            self.cnn_model.eval()
            self.logger.info("Loaded existing Wilson CNN model")
        else:
            # Train new model
            self.logger.info("Training new Wilson CNN model...")
            self._train_cnn()

    def _train_cnn(self):
        """Train the CNN classifier."""
        # Generate negative samples from random patches
        negative_samples = self._generate_negative_samples()
        
        # Create dataset
        dataset = WilsonBallDataset(
            positive_dir=str(self.template_dir),
            negative_samples=negative_samples,
            image_size=self.patch_size,
            augment=True
        )
        
        if len(dataset) < 10:
            self.logger.warning("Insufficient training data, using simple threshold detector")
            return
        
        # Split dataset
        train_size = int(0.8 * len(dataset))
        val_size = len(dataset) - train_size
        train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])
        
        # Data loaders
        train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)
        
        # Initialize model and training components
        self.cnn_model = WilsonBallCNN()
        criterion = nn.BCELoss()
        optimizer = optim.Adam(self.cnn_model.parameters(), lr=0.001)
        
        # Training loop
        num_epochs = 15
        best_val_acc = 0.0
        
        for epoch in range(num_epochs):
            # Training
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
            
            # Validation
            self.cnn_model.eval()
            val_correct = 0
            val_total = 0
            
            with torch.no_grad():
                for images, labels in val_loader:
                    outputs = self.cnn_model(images)
                    predicted = (outputs.squeeze() > 0.5).float()
                    val_total += labels.size(0)
                    val_correct += (predicted == labels).sum().item()
            
            train_acc = 100 * train_correct / train_total
            val_acc = 100 * val_correct / val_total if val_total > 0 else 0
            
            self.logger.debug(f"Epoch {epoch+1}: Train Acc: {train_acc:.1f}%, Val Acc: {val_acc:.1f}%")
            
            # Save best model
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                torch.save(self.cnn_model.state_dict(), "wilson_ball_hybrid_cnn.pth")
        
        self.logger.info(f"CNN training completed. Best accuracy: {best_val_acc:.1f}%")

    def _generate_negative_samples(self) -> List[np.ndarray]:
        """Generate negative samples for training."""
        negative_samples = []
        
        # Generate random noise patches
        for _ in range(20):
            noise = np.random.randint(0, 255, (self.patch_size, self.patch_size, 3), dtype=np.uint8)
            negative_samples.append(noise)
        
        # Generate patches with volleyball court colors but wrong patterns
        for _ in range(15):
            # Create patches with sand/court colors
            patch = np.random.randint(150, 220, (self.patch_size, self.patch_size, 3), dtype=np.uint8)
            # Add some noise
            noise = np.random.randint(-30, 30, patch.shape, dtype=np.int16)
            patch = np.clip(patch.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            negative_samples.append(patch)
        
        return negative_samples

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect Wilson volleyball using hybrid approach.

        Args:
            frame: Input video frame

        Returns:
            List of detection dictionaries
        """
        if self.cnn_model is None:
            return []

        # Quick size check to avoid processing very large or small frames inefficiently
        h, w = frame.shape[:2]
        if w * h > 2000000:  # Very large frame - downsample for candidate detection
            scale = 0.5
            small_frame = cv2.resize(frame, None, fx=scale, fy=scale)
            candidates = self._find_candidates(small_frame)
            # Scale candidates back up
            for candidate in candidates:
                bbox = candidate['bbox']
                candidate['bbox'] = [int(x/scale) for x in bbox]
        else:
            # Step 1: Classical CV pre-filtering
            candidates = self._find_candidates(frame)
        
        if not candidates:
            return []
        
        # Limit candidates to prevent excessive processing - be more aggressive
        candidates = sorted(candidates, key=lambda x: x['confidence'], reverse=True)[:5]
        
        # Step 2: CNN classification of candidates
        detections = []
        
        for candidate in candidates:
            x, y, w, h = candidate['bbox']
            
            # Extract patch
            patch = frame[y:y+h, x:x+w]
            
            if patch.size == 0:
                continue
            
            # CNN classification
            cnn_confidence = self._classify_patch(patch)
            
            if cnn_confidence >= self.confidence_threshold:
                # Combine classical CV and CNN confidences
                combined_confidence = (candidate['confidence'] * 0.3 + cnn_confidence * 0.7)
                
                detection = {
                    'center': [x + w//2, y + h//2],
                    'bbox': [x, y, x + w, y + h],
                    'confidence': combined_confidence,
                    'method': 'hybrid_cnn_cv',
                    'cnn_confidence': cnn_confidence,
                    'cv_confidence': candidate['confidence']
                }
                
                detections.append(detection)
        
        # Sort by confidence and apply NMS
        detections.sort(key=lambda x: x['confidence'], reverse=True)
        final_detections = self._non_max_suppression(detections)
        
        # Limit final output to max 3 detections
        return final_detections[:3]

    def _find_candidates(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Find candidate regions using classical CV techniques."""
        candidates = []
        
        # Convert to HSV for color filtering
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Create more restrictive color mask for Wilson ball colors
        yellow_mask = cv2.inRange(hsv, self.yellow_lower, self.yellow_upper)
        orange_mask = cv2.inRange(hsv, self.orange_lower, self.orange_upper)
        
        # Require both colors to be present in close proximity (Wilson pattern)
        kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        yellow_dilated = cv2.dilate(yellow_mask, kernel_small, iterations=1)
        orange_dilated = cv2.dilate(orange_mask, kernel_small, iterations=1)
        
        # Wilson balls have yellow AND orange in close proximity
        combined_mask = cv2.bitwise_and(yellow_dilated, orange_dilated)
        color_mask = cv2.bitwise_or(combined_mask, yellow_mask)  # Include pure yellow regions too
        
        # More aggressive morphological operations to reduce noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_CLOSE, kernel)
        color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_OPEN, kernel)
        
        # Find contours in color mask
        contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            
            # Much more restrictive size filtering to exclude shirts
            frame_area = frame.shape[0] * frame.shape[1]
            min_ball_area = 400    # Minimum ball size
            max_ball_area = min(8000, frame_area * 0.01)  # Max 1% of frame or 8000 pixels
            
            if area < min_ball_area or area > max_ball_area:
                continue
            
            # More restrictive aspect ratio for ball-like shapes
            aspect_ratio = w / h
            if aspect_ratio < 0.8 or aspect_ratio > 1.25:  # Very square-like for balls
                continue
            
            # Size consistency check - width and height should be similar for balls
            size_diff = abs(w - h) / max(w, h)
            if size_diff > 0.3:  # Reject if too rectangular
                continue
            
            # Calculate circularity
            contour_area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            
            if perimeter > 0:
                circularity = 4 * np.pi * contour_area / (perimeter * perimeter)
                if circularity < 0.5:  # Much more circular required
                    continue
            else:
                continue
            
            # More restrictive confidence calculation
            confidence = circularity * 0.8  # Less aggressive boosting
            
            # Enhanced color analysis for volleyball vs clothing
            roi = frame[y:y+h, x:x+w]
            roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            # Check for Wilson volleyball colors
            yellow_pixels = cv2.inRange(roi_hsv, self.yellow_lower, self.yellow_upper)
            orange_pixels = cv2.inRange(roi_hsv, self.orange_lower, self.orange_upper)
            
            yellow_ratio = np.sum(yellow_pixels > 0) / (w * h)
            orange_ratio = np.sum(orange_pixels > 0) / (w * h)
            
            # Wilson balls should have both yellow AND some orange/red accents
            if yellow_ratio < 0.15 or orange_ratio < 0.02:  # Must have both colors
                continue
            
            # Check color distribution - balls have mixed colors, shirts are uniform
            total_colored = yellow_ratio + orange_ratio
            if total_colored > 0.8:  # Too much color = likely clothing
                continue
            
            # Color pattern check - Wilson balls have specific color arrangements
            color_score = yellow_ratio * 2 + orange_ratio  # Yellow is primary
            if color_score < 0.3:  # Minimum color requirement
                continue
            
            # Boost confidence for good Wilson-like color pattern
            confidence *= (1 + color_score * 0.5)
            
            candidates.append({
                'bbox': [x, y, w, h],
                'confidence': min(1.0, confidence),
                'area': area,
                'circularity': circularity,
                'yellow_ratio': yellow_ratio
            })
        
        # Also try Hough circle detection as additional candidates
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=self.hough_params['dp'],
            minDist=self.hough_params['min_dist'],
            param1=self.hough_params['param1'],
            param2=self.hough_params['param2'],
            minRadius=self.hough_params['min_radius'],
            maxRadius=self.hough_params['max_radius']
        )
        
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            # Limit to max 5 circles and filter by size
            for (x, y, r) in circles[:5]:  # Only take first 5 circles
                # Filter circles by reasonable ball radius
                if r < 10 or r > 60:  # Reasonable ball radius range
                    continue
                    
                # Create bounding box from circle
                bbox_x = max(0, x - r)
                bbox_y = max(0, y - r)
                bbox_w = min(frame.shape[1] - bbox_x, 2 * r)
                bbox_h = min(frame.shape[0] - bbox_y, 2 * r)
                
                # Check color content in circle area
                roi = frame[bbox_y:bbox_y+bbox_h, bbox_x:bbox_x+bbox_w]
                if roi.size > 0:
                    roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                    yellow_pixels = cv2.inRange(roi_hsv, self.yellow_lower, self.yellow_upper)
                    yellow_ratio = np.sum(yellow_pixels > 0) / (bbox_w * bbox_h)
                    
                    if yellow_ratio < 0.1:  # Must have significant yellow content
                        continue
                    
                    # Also check for orange content in circles
                    orange_pixels = cv2.inRange(roi_hsv, self.orange_lower, self.orange_upper)
                    orange_ratio = np.sum(orange_pixels > 0) / (bbox_w * bbox_h)
                    
                    # Require some orange content for Wilson volleyball pattern
                    if orange_ratio < 0.01:
                        continue
                
                candidates.append({
                    'bbox': [bbox_x, bbox_y, bbox_w, bbox_h],
                    'confidence': 0.5 + yellow_ratio * 0.3,  # Confidence based on color match
                    'area': bbox_w * bbox_h,
                    'circularity': 1.0,  # Perfect circle
                    'yellow_ratio': yellow_ratio
                })
        
        # Sort candidates by confidence and limit aggressively for performance
        candidates = sorted(candidates, key=lambda x: x['confidence'], reverse=True)
        return candidates[:8]  # Maximum 8 candidates total for speed

    def _classify_patch(self, patch: np.ndarray) -> float:
        """Classify patch using CNN."""
        if self.cnn_model is None:
            return 0.0
        
        try:
            # Convert BGR to RGB
            patch_rgb = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
            
            # Apply transforms
            transformed = self.cnn_transform(image=patch_rgb)
            input_tensor = transformed['image'].unsqueeze(0)
            
            # CNN inference
            self.cnn_model.eval()
            with torch.no_grad():
                output = self.cnn_model(input_tensor)
                confidence = output.item()
            
            return confidence
            
        except Exception as e:
            self.logger.debug(f"CNN classification failed: {e}")
            return 0.0

    def _non_max_suppression(self, detections: List[Dict[str, Any]], iou_threshold: float = 0.3) -> List[Dict[str, Any]]:
        """Apply non-maximum suppression."""
        if not detections:
            return []
        
        keep = []
        detections = sorted(detections, key=lambda x: x['confidence'], reverse=True)
        
        while detections:
            current = detections.pop(0)
            keep.append(current)
            
            remaining = []
            for det in detections:
                iou = self._calculate_iou(current['bbox'], det['bbox'])
                if iou < iou_threshold:
                    remaining.append(det)
            
            detections = remaining
        
        return keep

    def _calculate_iou(self, box1: List[int], box2: List[int]) -> float:
        """Calculate IoU of two bounding boxes."""
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