"""Import a Roboflow COCO export into the flat YOLO ball dataset.

The retrain workflow's annotation leg: the owner reviews the mined frames
in Roboflow (scripts/mine_ball_frames.py output), exports COCO, and this
script converts + flattens the result into datasets/ball_detection/
(the flat images/+labels/ tree that prepare_dataset_for_training.py
consumes):

- Roboflow's `_jpg.rf.<hash>` filename suffix is stripped back to the
  canonical `<stem>_f<idx>.jpg` mining name (no collision with the
  entreno `frame_XXXX` namespace).
- COCO [x_min, y_min, w, h] px boxes -> YOLO normalized center/wh.
- Categories whose name contains 'ball' map to class 0; anything else
  aborts (a stray 'person' class must never silently become a ball).
- Degenerate boxes (w or h < 2 px -- click droppings) are dropped and
  reported, never silently.
- Images with zero surviving boxes get an EMPTY label file: a valid YOLO
  negative.

Usage:
    python scripts/import_roboflow_coco.py output/roboflow_coco \
        --output datasets/ball_detection
"""

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROBOFLOW_SUFFIX = re.compile(r"_jpg\.rf\.[A-Za-z0-9]+\.(jpg|jpeg|png)$", re.I)
DEGENERATE_PX = 2.0


def strip_roboflow_suffix(file_name):
    """`..._f001412_jpg.rf.<hash>.jpg` -> `..._f001412.jpg` (else unchanged)."""
    return ROBOFLOW_SUFFIX.sub(lambda m: "." + m.group(1), file_name)


def load_export(export_root):
    """Read all split JSONs -> (files: {canonical: Path}, boxes: {canonical:
    [(cx, cy, w, h) px]}, dropped: {canonical: n}) with category policing."""
    export_root = Path(export_root)
    files, boxes, dropped = {}, {}, {}
    for split in ("train", "valid", "test"):
        ann_path = export_root / split / "_annotations.coco.json"
        if not ann_path.exists():
            continue
        data = json.loads(ann_path.read_text())
        for cat in data["categories"]:
            if "ball" not in cat["name"].lower():
                raise SystemExit(
                    f"non-ball category {cat['name']!r} in {split} -- "
                    "resolve by hand, refusing to map it to class 0")
        id2name = {i["id"]: strip_roboflow_suffix(i["file_name"])
                   for i in data["images"]}
        id2size = {i["id"]: (i["width"], i["height"]) for i in data["images"]}
        for i in data["images"]:
            canon = strip_roboflow_suffix(i["file_name"])
            files.setdefault(canon, export_root / split / i["file_name"])
            boxes.setdefault(canon, [])
            dropped.setdefault(canon, 0)
        for a in data["annotations"]:
            canon = id2name[a["image_id"]]
            x, y, w, h = a["bbox"]
            if w < DEGENERATE_PX or h < DEGENERATE_PX:
                dropped[canon] += 1
                continue
            iw, ih = id2size[a["image_id"]]
            boxes[canon].append((x + w / 2, y + h / 2, w, h, iw, ih))
    return files, boxes, dropped


def to_yolo_lines(box_list):
    """[(cx, cy, w, h, img_w, img_h)] -> YOLO txt lines (class 0)."""
    lines = []
    for cx, cy, w, h, iw, ih in box_list:
        lines.append(f"0 {cx/iw:.6f} {cy/ih:.6f} {w/iw:.6f} {h/ih:.6f}")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("export_root", help="Roboflow COCO export dir (train/valid/test)")
    ap.add_argument("--output", default="datasets/ball_detection",
                    help="flat dataset dir (images/ + labels/)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files, boxes, dropped = load_export(args.export_root)
    images_dir = Path(args.output) / "images"
    labels_dir = Path(args.output) / "labels"

    clash = [f for f in files if (images_dir / f).exists()]
    if clash:
        raise SystemExit(f"{len(clash)} canonical names already exist in "
                         f"{images_dir} (e.g. {clash[:3]}) -- refusing to overwrite")

    n_boxes = sum(len(v) for v in boxes.values())
    n_empty = sum(1 for f in files if not boxes.get(f))
    n_dropped = sum(dropped.values())
    print(f"{len(files)} images, {n_boxes} boxes, {n_empty} empty-label "
          f"negatives, {n_dropped} degenerate boxes dropped (<{DEGENERATE_PX}px)")
    if n_dropped:
        for f, n in sorted(dropped.items()):
            if n:
                print(f"  dropped {n}: {f}")

    if args.dry_run:
        print("dry run -- nothing written")
        return

    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    for canon, src in sorted(files.items()):
        shutil.copy2(src, images_dir / canon)
        lines = to_yolo_lines(boxes.get(canon, []))
        (labels_dir / (Path(canon).stem + ".txt")).write_text(
            "\n".join(lines) + ("\n" if lines else ""))
    print(f"wrote {len(files)} images + labels -> {args.output}")

    widths = Counter()
    for v in boxes.values():
        for b in v:
            widths[int(b[2] // 10) * 10] += 1
    print("box width px histogram:", dict(sorted(widths.items())))


if __name__ == "__main__":
    main()
