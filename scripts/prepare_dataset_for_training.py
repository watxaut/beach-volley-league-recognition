"""Prepare a YOLO-format dataset zip for Colab training.

Takes the flat images/ + labels/ from auto_label_balls.py, splits into
train/valid, generates data.yaml, and creates a zip file ready to upload.

Usage:
    python scripts/prepare_dataset_for_training.py datasets/ball_detection/

Output:
    datasets/ball_detection/ball_dataset.zip
"""

import argparse
import random
import shutil
import yaml
from pathlib import Path


def prepare_dataset(dataset_dir: Path, val_ratio: float = 0.15, seed: int = 42):
    images_dir = dataset_dir / "images"
    labels_dir = dataset_dir / "labels"

    if not images_dir.exists() or not labels_dir.exists():
        print(f"Expected {images_dir} and {labels_dir} to exist")
        return

    # Collect matched image+label pairs
    pairs = []
    for img_path in sorted(images_dir.glob("*.png")) + sorted(images_dir.glob("*.jpg")):
        label_path = labels_dir / f"{img_path.stem}.txt"
        if label_path.exists():
            pairs.append((img_path, label_path))

    print(f"Found {len(pairs)} image+label pairs")

    # Split
    random.seed(seed)
    random.shuffle(pairs)
    n_val = max(1, int(len(pairs) * val_ratio))
    val_pairs = pairs[:n_val]
    train_pairs = pairs[n_val:]

    print(f"Train: {len(train_pairs)}, Valid: {n_val}")

    # Build output structure
    out_dir = dataset_dir / "yolo_dataset"
    if out_dir.exists():
        shutil.rmtree(out_dir)

    for split, split_pairs in [("train", train_pairs), ("valid", val_pairs)]:
        (out_dir / split / "images").mkdir(parents=True)
        (out_dir / split / "labels").mkdir(parents=True)
        for img_path, label_path in split_pairs:
            shutil.copy2(img_path, out_dir / split / "images" / img_path.name)
            shutil.copy2(label_path, out_dir / split / "labels" / label_path.name)

    # Write data.yaml
    data_yaml = {
        "train": "../train/images",
        "val": "../valid/images",
        "nc": 1,
        "names": ["ball"],
    }
    yaml_path = out_dir / "data.yaml"
    yaml_path.write_text(yaml.dump(data_yaml, default_flow_style=False))

    # Zip it
    zip_path = dataset_dir / "ball_dataset"
    shutil.make_archive(str(zip_path), "zip", root_dir=str(out_dir))

    # Cleanup temp dir
    shutil.rmtree(out_dir)

    print(f"\nCreated: {zip_path}.zip")
    print("Upload this zip to Google Colab and use the notebook to train.")


def main():
    parser = argparse.ArgumentParser(description="Prepare YOLO dataset zip for Colab training")
    parser.add_argument("dataset_dir", type=str, help="Dataset directory with images/ and labels/")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Validation split ratio (default: 0.15)")
    args = parser.parse_args()

    prepare_dataset(Path(args.dataset_dir), val_ratio=args.val_ratio)


if __name__ == "__main__":
    main()
