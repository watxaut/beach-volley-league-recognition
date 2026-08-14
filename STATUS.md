# Project Status

> **Convention:** this file is the cross-session memory of the project. Read it
> first when coming back. Update it (and commit it with the work) at the end of
> every working session: refresh *Where we are*, move finished items into the
> *Log*, and re-rank *Open points*.

**Last updated:** 2026-08-14

## Where we are

The **player-identity plan (phase 1) is implemented and committed** (`e13ea8d`):
the tracker now keeps exactly 4 stable IDs across occlusions, off-court servers,
and re-appearances, via two-zone filtering, a dormant-ID gallery with
re-acquisition, and an appearance+biometrics signature. Validated on the
`video_entreno_*` drills (e.g. entreno_1: dropped-player frames 29.7% → 0.8%,
coverage 78% → 94%; entreno_3: 0 dropped serves, 0 resurrections, 0 swaps).
48 unit tests green.

**Plan reference:** the full design lives in the session plan file
(`~/.claude-zai/plans/i-want-to-start-golden-naur.md`) and the summary in
Claude memory (`player-identity-plan`). Short version of the architecture:
uniforms vary/are uncontrolled → colour can't be a trusted identity signal →
**motion continuity is the primary identity signal**, appearance/body-size are
conditional tie-breakers, and "exactly 4 players / 2 per side" is a hard
constraint. Side changes need no special handling as long as IDs survive.

## Open points

1. **[blocked on footage] Validate side-change survival on a real match.** The
   gallery's marquee use case (players swap ends every 7 points) is untested —
   the entreno drills have no side changes. Need one set-to-21 clip, calibrated,
   then: `python scripts/dump_player_tracks.py <match>.mp4 --max-players 4` →
   `python scripts/analyze_tracking.py <json> --max-players 4`, and scrub the
   annotated video through a side change watching each ID.
2. **[next, small] One-time identity ground truth** to wake up the dead metric:
   populate `players.frames` (currently empty in every `ground_truth/*.json`)
   for ~30–50 sampled frames of 1–2 videos with canonical IDs 1–4, spanning a
   side change if possible, then
   `python scripts/evaluate.py <tracks.json> <gt.json> --component players`
   (`_compute_id_consistency` target → 1.0).
3. **[conditional] Phase 2: offline global stitch.** Post-processing pass that
   re-clusters all track fragments into exactly 4 identities (ensemble
   signature + time/space gaps + k=4). Only build if match validation shows
   residual swaps/fragmentation that phase 1 doesn't catch.
4. **[optional, separate axis] Detection recall.** Residual drops on entreno_3
   (~15% of frames) are genuine YOLO misses, not tracking failures. Levers:
   `player_confidence` (0.5 → 0.35 lifts recall ~3pp, adds false dets) or
   `player_imgsz`. Not part of the identity plan.
5. **[minor cleanup] `CourtCalibration.filter_detections_by_play_area` is
   currently unused** (the detector's bbox-overlap `detect_play_area` filter
   replaced it). Keep or remove.

## Log (newest first)

### 2026-08-14 — player identity phase 1 (1a+1b+1c) shipped
- **1a** two-zone filter + bootstrap-at-first-rally + hardened 4-cap; **1b**
  dormant gallery with original-ID re-acquisition and eviction-on-demand;
  **1c** ground-plane body-size + ensemble signature + appearance-based
  re-acquisition (side-change path).
- Files: `player_tracker.py`, `court_calibration.py`, `player_detector.py`,
  `frame_processor.py`, `dump_player_tracks.py`, `config.py`;
  new tests `test_player_tracker_gallery.py`, `test_court_ground_plane.py`.
- Measured: baseline vs 1a/1b/1c dumps in `output/{baseline,1a,1b,1c}/`
  (git-ignored); per-stage summaries alongside.
- Learned: the entreno drops looked "detection-limited" under position-only
  re-acquisition (1a/1b) but were appearance-bridgeable — 1c broke through the
  detection-recall ceiling. entreno drills remain useful for continuity
  validation; they just can't test side changes.

## Useful commands

```bash
# tracking quality (no GT needed) — the main iteration loop
python scripts/dump_player_tracks.py resources/video_entreno_1.mp4 --max-players 4
python scripts/analyze_tracking.py output/video_entreno_1_tracks.json --max-players 4

# full test suite (cov addopts are broken w/o pytest-cov; override them)
venv/bin/python -m pytest tests/ -o addopts=""

# full pipeline on a video
python -m src.main <video.mp4> --court calibrations/<name>.json
```
