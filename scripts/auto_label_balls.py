"""Auto-label ball detections using Roboflow's find-balls workflow.

Sends frames to the Roboflow API, converts predictions to YOLOv8 annotation
format (txt files), and copies images + labels into a dataset folder ready
for upload to Roboflow for review, correction, and training.

Usage:
    python scripts/auto_label_balls.py resources/frames/entreno_20260216/ \
        --output datasets/ball_detection \
        --confidence 0.5

Output structure (YOLOv8 format):
    datasets/ball_detection/
        images/
            frame_0001.png
            frame_0002.png
            ...
        labels/
            frame_0001.txt
            frame_0002.txt
            ...

Each .txt file contains one line per detection:
    <class_id> <cx_norm> <cy_norm> <w_norm> <h_norm>
"""

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

from inference_sdk import InferenceHTTPClient

WORKSPACE = "volley-sbinv"
WORKFLOW_ID = "find-balls"


def process_frames(
    frames_dir: Path,
    output_dir: Path,
    confidence_threshold: float = 0.5,
    skip_existing: bool = True,
):
    """Process all frames and generate YOLO-format annotations."""
    images_dir = output_dir / "images"
    labels_dir = output_dir / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        raise SystemExit(
            "ROBOFLOW_API_KEY env var not set. "
            "Get a key from Roboflow settings and `export ROBOFLOW_API_KEY=...`."
        )

    client = InferenceHTTPClient(
        api_url="https://serverless.roboflow.com",
        api_key=api_key,
    )

    frame_paths = sorted(frames_dir.glob("*.png")) + sorted(frames_dir.glob("*.jpg"))
    if not frame_paths:
        print(f"No images found in {frames_dir}")
        sys.exit(1)

    print(f"Found {len(frame_paths)} frames in {frames_dir}")
    print(f"Output: {output_dir}")
    print(f"Confidence threshold: {confidence_threshold}")
    print()

    stats = {"total": len(frame_paths), "processed": 0, "skipped": 0, "detections": 0, "errors": 0}

    for i, frame_path in enumerate(frame_paths):
        label_path = labels_dir / f"{frame_path.stem}.txt"
        image_dest = images_dir / frame_path.name

        if skip_existing and label_path.exists() and image_dest.exists():
            stats["skipped"] += 1
            continue

        try:
            result = client.run_workflow(
                workspace_name=WORKSPACE,
                workflow_id=WORKFLOW_ID,
                images={"image": str(frame_path)},
                use_cache=True,
            )

            predictions = result[0].get("predictions", {})
            img_w = predictions["image"]["width"]
            img_h = predictions["image"]["height"]
            detections = predictions.get("predictions", [])

            # Filter by confidence and convert to YOLO format
            lines = []
            for det in detections:
                if det["confidence"] < confidence_threshold:
                    continue
                # Roboflow gives center x, y, width, height in pixels
                cx = det["x"] / img_w
                cy = det["y"] / img_h
                w = det["width"] / img_w
                h = det["height"] / img_h
                # class_id = 0 (ball)
                lines.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

            # Write label file (empty file if no detections — still valid YOLO)
            label_path.write_text("\n".join(lines) + ("\n" if lines else ""))

            # Copy image
            if not image_dest.exists():
                shutil.copy2(frame_path, image_dest)

            stats["processed"] += 1
            stats["detections"] += len(lines)

            n_total = stats["processed"] + stats["skipped"]
            print(
                f"[{n_total}/{stats['total']}] {frame_path.name}: "
                f"{len(lines)} balls (of {len(detections)} raw detections)"
            )

        except Exception as e:
            stats["errors"] += 1
            print(f"[ERROR] {frame_path.name}: {e}")
            # Brief pause on error (rate limiting)
            time.sleep(1)

    # Write summary
    print()
    print("=" * 50)
    print(f"Done! Processed: {stats['processed']}, Skipped: {stats['skipped']}, Errors: {stats['errors']}")
    print(f"Total detections: {stats['detections']}")
    print(f"Images: {images_dir}")
    print(f"Labels: {labels_dir}")
    print()
    print("Next steps:")
    print("1. Upload the dataset folder to Roboflow (drag & drop images + labels)")
    print("2. Review and correct annotations in the Roboflow UI")
    print("3. Train a YOLOv8 model in Roboflow")
    print("4. Export/download the weights")

    # Save stats
    stats_path = output_dir / "labeling_stats.json"
    stats_path.write_text(json.dumps(stats, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Auto-label volleyball ball detections using Roboflow")
    parser.add_argument("frames_dir", type=str, help="Directory containing frame images")
    parser.add_argument("--output", type=str, default="datasets/ball_detection", help="Output dataset directory")
    parser.add_argument("--confidence", type=float, default=0.5, help="Minimum confidence threshold (default: 0.5)")
    parser.add_argument("--no-skip", action="store_true", help="Re-process frames that already have labels")
    args = parser.parse_args()

    process_frames(
        frames_dir=Path(args.frames_dir),
        output_dir=Path(args.output),
        confidence_threshold=args.confidence,
        skip_existing=not args.no_skip,
    )


if __name__ == "__main__":
    main()
