"""Unit tests for scripts/import_roboflow_coco.py pure logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from import_roboflow_coco import strip_roboflow_suffix, to_yolo_lines


class TestStripRoboflowSuffix:
    def test_strips_hash_suffix(self):
        assert strip_roboflow_suffix(
            "match_f001412_jpg.rf.bWqT9GgSLPNpNdo1vEEM.jpg") == "match_f001412.jpg"

    def test_plain_name_unchanged(self):
        assert strip_roboflow_suffix("frame_0001.png") == "frame_0001.png"
        assert strip_roboflow_suffix("frame_0001.jpg") == "frame_0001.jpg"

    def test_png_suffix_variant(self):
        assert strip_roboflow_suffix("x_jpg.rf.AbC123.png") == "x.png"


class TestToYoloLines:
    def test_center_normalization(self):
        # box centered at (960, 540), 25x25 px on 1920x1080
        lines = to_yolo_lines([(960.0, 540.0, 25.0, 25.0, 1920, 1080)])
        assert lines == ["0 0.500000 0.500000 0.013021 0.023148"]

    def test_empty(self):
        assert to_yolo_lines([]) == []
