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
DB     ?= data/volley.db

# Derive the output folder from the video basename (strip dir + extension).
VIDEO_NAME := $(basename $(notdir $(VIDEO)))
OUTPUT_DIR := output/$(VIDEO_NAME)

# Skip visualization unless VIZ is set.
VIZ_FLAG := $(if $(VIZ),,--skip-visualization)

.PHONY: run run-video run-live run-match postrun ingest ingest-all db-reset ui help \
        calibrate process publish republish-all inbox backup schema-check

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

# Full match: the normal run plus the per-frame stream sidecar the post-run
# layer needs (--diag-dump, same frame path, off by default), then the
# post-run reconstruction (points, touches, players, winners, score).
run-match:
ifeq ($(strip $(VIDEO)),)
	$(error VIDEO is not set. Usage: make run-match VIDEO=path/to/video.mp4)
endif
	$(PYTHON) -m src.main "$(VIDEO)" --output-dir "$(OUTPUT_DIR)" $(VIZ_FLAG) --diag-dump "$(OUTPUT_DIR)/diag.jsonl"
	$(PYTHON) -m src.postrun "$(OUTPUT_DIR)"
	@echo ""
	@echo "Match reconstruction: $(OUTPUT_DIR)/match_reconstruction.json (+ .txt play-by-play)"

# Re-run only the post-run reconstruction over an existing run directory
# (seconds, no video decode): make postrun VIDEO=... or OUTPUT_DIR=output/<dir>.
postrun:
	$(PYTHON) -m src.postrun "$(OUTPUT_DIR)"

# Upsert one video's extraction output into the analysis DB (separate process
# from `run` by design: extraction writes output/<stem>/pipeline_output.json,
# ingest reads it). Re-ingesting overwrites that video's rows; player labels
# survive.
ingest:
ifeq ($(strip $(VIDEO)),)
	$(error VIDEO is not set. Usage: make ingest VIDEO=path/to/video.mp4)
endif
	$(PYTHON) -m src.db.ingest "$(VIDEO_NAME)" --db "$(DB)"

# Ingest every output/<stem>/pipeline_output.json found.
ingest-all:
	$(PYTHON) -m src.db.ingest output --db "$(DB)"

# Delete the analysis database entirely (labels too!).
db-reset:
	rm -f "$(DB)" "$(DB)-wal" "$(DB)-shm"
	@echo "Deleted $(DB)"

# Local web UI over the analysis DB (http://127.0.0.1:8000).
ui:
	$(PYTHON) -m src.web.app --db "$(DB)"

# --------------------------------------------------------------------------
# Web platform (docs/web_platform_design.md; deployment: docs/deploy_web_platform.md)
# Match key = video name: YYYYMMDD_HHMM_<venue>_<text> (make inbox names files for you).
# --------------------------------------------------------------------------

# One-time interactive court calibration (8 clicks) -> calibrations/<key>.json.
calibrate:
ifeq ($(strip $(VIDEO)),)
	$(error VIDEO is not set. Usage: make calibrate VIDEO=resources/<key>.mp4)
endif
	$(PYTHON) scripts/test_court_calibration.py "$(VIDEO)"

# Full match -> draft on the web: run + post-run reconstruction + publish.
process: run-match publish

# Publish output/<key>/ to Supabase (a new match lands as a DRAFT; re-running is
# safe: identical content is logged as 'unchanged').
#   DRY=1            build + diff against what is live, write nothing
#   MATCH_KEY=...    key override for runs whose video lacks the HHMM part
#   NOTE="..."       note stored in the publication log
#   PUBLISH_FLAGS=   extra flags (--replace-video, --allow-dirty, --no-thumbs)
publish:
	$(PYTHON) -m src.publish "$(OUTPUT_DIR)" $(if $(DRY),--dry-run) \
		$(if $(MATCH_KEY),--match-key "$(MATCH_KEY)") $(if $(NOTE),--note "$(NOTE)") $(PUBLISH_FLAGS)

# Re-run post-run + publish for EVERY match published from this machine, so old
# matches follow the current rules (needs each match's diag.jsonl; DRY=1 lists only).
republish-all:
	$(PYTHON) -m src.publish.republish $(if $(DRY),--dry-run) $(REPUBLISH_FLAGS)

# One pass over the Drive inbox: download + name, wait for calibration, run,
# publish as draft, archive on Drive (launchd runs this every 30 min).
inbox:
	$(PYTHON) -m src.publish.inbox

# Export the admin-owned tables (players, accounts, assignments, rules).
backup:
	$(PYTHON) -m src.publish.backup $(if $(OUT),--out "$(OUT)") $(BACKUP_FLAGS)

# Migrations + RLS smoke check against a Postgres you can create databases on
# (local Supabase: PG_DSN=postgresql://postgres:postgres@127.0.0.1:54322/postgres).
PG_DSN ?= postgresql://postgres:postgres@127.0.0.1:54322/postgres
schema-check:
	VOLLEY_TEST_PG_DSN="$(PG_DSN)" $(PYTHON) -m pytest tests/test_supabase_schema.py -o addopts="" -q

help:
	@echo "make run VIDEO=path/to/video.mp4        Analyze a video -> $(OUTPUT_DIR)/results.csv + pipeline_output.json"
	@echo "make run-video VIDEO=path/to/video.mp4  Also save an annotated .mp4 (two-pass, contact-anchored labels)"
	@echo "make run-live VIDEO=path/to/video.mp4   Play the annotated video live (buffered ~3s so labels land on contact)"
	@echo "make run-match VIDEO=path/to/video.mp4  Run + post-run reconstruction -> match_reconstruction.json/.txt"
	@echo "make postrun VIDEO=path/to/video.mp4    Redo only the reconstruction over an existing run (no decode)"
	@echo "  VIZ=1                                 Also generate summary_graphs.png (run / run-video)"
	@echo "  PYTHON=...                            Override the python interpreter"
	@echo "make ingest VIDEO=path/to/video.mp4   Upsert that video's output into the DB"
	@echo "make ingest-all                       Upsert every output/<stem>/pipeline_output.json"
	@echo "make db-reset                         Delete the DB (DB=$(DB))"
	@echo "make ui                               Local web UI at http://127.0.0.1:8000"
	@echo "make calibrate VIDEO=resources/<key>.mp4  Court calibration (8 clicks, once per video)"
	@echo "make process VIDEO=resources/<key>.mp4    run-match + publish as a draft"
	@echo "make publish OUTPUT_DIR=output/<key>      Publish a finished run (DRY=1 to diff only)"
	@echo "make republish-all                        Redo post-run + publish for every published match (DRY=1: list)"
	@echo "make inbox                                One pass over the Drive inbox"
	@echo "make backup                               Export admin-owned tables to backups/"
	@echo "make schema-check                         Migrations + RLS check on a local Postgres"
