# Makefile for beach volleyball recognition
#
# Runs the full pipeline (src.main) on a video and writes the per-player
# results CSV to output/<video_name>/results.csv.
#
# Court calibration (calibrations/<video_name>.json) and the fine-tuned ball
# model (models/volleyball_ball_best.pt) are auto-detected by src.main.
#
# Usage:
#   make run VIDEO=resources/video_entreno_4.mp4
#   make run VIDEO=resources/video_entreno_4.mp4 VIZ=1   # also emit summary graphs

PYTHON ?= python
VIDEO  ?=
VIZ    ?=

# Derive the output folder from the video basename (strip dir + extension).
VIDEO_NAME := $(basename $(notdir $(VIDEO)))
OUTPUT_DIR := output/$(VIDEO_NAME)

# Skip visualization unless VIZ is set.
VIZ_FLAG := $(if $(VIZ),,--skip-visualization)

.PHONY: run run-video run-live help

run:
ifeq ($(strip $(VIDEO)),)
	$(error VIDEO is not set. Usage: make run VIDEO=path/to/video.mp4)
endif
	$(PYTHON) -m src.main "$(VIDEO)" --output-dir "$(OUTPUT_DIR)" $(VIZ_FLAG)
	@echo ""
	@echo "Per-player results CSV: $(OUTPUT_DIR)/results.csv"

run-video:
ifeq ($(strip $(VIDEO)),)
	$(error VIDEO is not set. Usage: make run VIDEO=path/to/video.mp4)
endif
	$(PYTHON) -m src.main "$(VIDEO)" --output-dir "$(OUTPUT_DIR)" $(VIZ_FLAG) --save-video
	@echo ""
	@echo "Per-player results CSV: $(OUTPUT_DIR)/results.csv"

run-live:
ifeq ($(strip $(VIDEO)),)
	$(error VIDEO is not set. Usage: make run VIDEO=path/to/video.mp4)
endif
	$(PYTHON) -m src.main "$(VIDEO)" --output-dir "$(OUTPUT_DIR)" --debug-live --debug-speed 2
	@echo ""
	@echo "Per-player results CSV: $(OUTPUT_DIR)/results.csv"

help:
	@echo "make run VIDEO=path/to/video.mp4        Analyze a video -> $(OUTPUT_DIR)/results.csv"
	@echo "make run-video VIDEO=path/to/video.mp4  Also save an annotated .mp4 (two-pass, contact-anchored labels)"
	@echo "make run-live VIDEO=path/to/video.mp4   Play the annotated video live (buffered ~3s so labels land on contact)"
	@echo "  VIZ=1                                 Also generate summary_graphs.png (run / run-video)"
	@echo "  PYTHON=...                            Override the python interpreter"
