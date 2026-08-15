# Project Status

> **Convention:** this file is the cross-session memory of the project. Read it
> first when coming back. Update it (and commit it with the work) at the end of
> every working session: refresh *Where we are*, move finished items into the
> *Log*, and re-rank *Open points*.

**Last updated:** 2026-08-15

## Where we are

The **player-identity plan (phase 1) is implemented and committed** (`e13ea8d`),
**entreno_1 and entreno_3 have real player-ID ground truth** (44 + 67 frames,
canonical IDs, occlusion-flagged), and the **far-side bystander-hijack bug
found via that GT is fixed and validated on both videos**: assignment-level
court membership in `PlayerTracker` (`_may_feed_track`). entreno_1: detection
0.65 → **0.92**, ghosts 0.35 → **0.13**. entreno_3: detection 0.69 → **0.88**,
ghosts 0.32 → **0.11**, id_consistency 0.82 → **0.93** — and GT2 (the server)
went from 2/67 matched frames in the 1c baseline (it was tracking a frame-edge
bystander) to 50/67 with 0.96 consistency. 75 unit tests green.

**Plan reference:** the full design lives in the session plan file
(`~/.claude-zai/plans/i-want-to-start-golden-naur.md`) and the summary in
Claude memory (`player-identity-plan`). Short version of the architecture:
uniforms vary/are uncontrolled → colour can't be a trusted identity signal →
**motion continuity is the primary identity signal**, appearance/body-size are
conditional tie-breakers, and "exactly 4 players / 2 per side" is a hard
constraint. Side changes need no special handling as long as IDs survive.

## Open points

1. **[BLOCKED — no footage] Validate side-change survival on a real match.** The
   gallery's marquee use case (players swap ends every 7 points) is untested —
   the entreno drills have no side changes. Blocked as of 2026-08-14: no video
   of a full set is available yet. Unblock by recording/obtaining one
   set-to-21 clip, calibrated, then:
   `python scripts/dump_player_tracks.py <match>.mp4 --max-players 4` →
   `python scripts/analyze_tracking.py <json> --max-players 4`, and scrub the
   annotated video through a side change watching each ID.
2. **[conditional] Phase 2: offline global stitch.** Post-processing pass that
   re-clusters all track fragments into exactly 4 identities (ensemble
   signature + time/space gaps + k=4). Only build if match validation shows
   residual swaps/fragmentation that phase 1 doesn't catch.
3. **[optional, separate axis] Detection recall.** The remaining honest gaps
   are genuine YOLO misses: entreno_3 GT2 was invisible to the tracker for
   frames 10–170 (serve outside court + entry, confirmed by GT); entreno_1
   far-side misses similar. Levers: `player_confidence` (0.5 → 0.35 lifts
   recall ~3pp, adds false dets) or `player_imgsz`. Not part of the identity
   plan.
4. **[minor cleanup] `CourtCalibration.filter_detections_by_play_area` is
   currently unused** (the detector's bbox-overlap `detect_play_area` filter
   replaced it). Keep or remove.

## Log (newest first)

### 2026-08-15 — entreno_3 GT validates the bystander-hijack fix
- 67 frames × 4 players annotated (serve + entry gap and a heavy dig-and-fall
  occlusion included); occlusion flagger caught the fall window (GT3 invisible
  from ~590; GT3 then has ZERO visible-but-unmatched frames).
- Baseline (1c) vs fixed (fix2) on the same GT: detection 0.686→0.876, ghosts
  0.324→0.114, id_consistency 0.818→0.929, team 0.994→0.996. GT2: 2/67 →
  50/67 matched, 0.96 consistency — the 1c run had been tracking a frame-edge
  bystander; the fixed run's ID2 restore at f180 is the REAL player.
  Remaining GT2 misses (frames 10–170) = serve outside court + undetected
  entry: honest detection gaps, open point 3.
- Annotator usability: added [R] reset-frame, and actually wired up [B] back
  (was advertised but unimplemented).

### 2026-08-15 — bystander-hijack fix: assignment-level court membership in PlayerTracker
- **Mechanism (via GT + a new opt-in tracker audit trail**, `debug_assignments`
  param, paths: hungarian / iou_reattach / gallery_position / gallery_appearance
  / new_track**)**: far-side player undetected → track coasts/retires → an
  out-of-court bystander inherits the id (entreno_1: gallery_appearance at
  f97, hungarian at f181; 586/1635 assignments were out-of-court) → hungarian
  then feeds the bystander forever. Same bug invalidated part of the 1c
  entreno_3 numbers (ID2 ghosted, then tracked a frame-edge bystander 70+ frames).
- **Fix** (`_may_feed_track` + `last_in_court_frame`/`last_matched_frame`
  bookkeeping): an out-of-court detection may only continue a track while
  identity is OBSERVED — within `player_off_court_grace_frames` (45) of the
  last in-court sighting, or continuously matched frame-to-frame (a player who
  walked out and keeps being detected). Gallery restores (both passes) require
  a strictly in-court detection, like new-track admission.
- **Measured**: entreno_1 GT eval detection 0.651→0.923, ghost 0.352→0.133,
  id_consistency 0.974→0.978, team 0.981→0.986; GT4 matched frames 9→32.
  Audit under fix: 0/1399 out-of-court assignments. entreno_3: 0 swaps,
  ID2 dormant during the bystander window then restored IN COURT (f180) —
  the analyze_tracking "dropped frames" increase (6.3%→17.2%) there is the
  honest cost of refusing fake bystander coverage, not a regression.
- New tests `tests/test_bystander_guard.py` (8); suite 75 green.
- Throwaway diagnostics kept in git-ignored `output/diag_hijack.py` +
  `output/diag_hijack_log.json` (pre-fix audit), `output/fix1`/`fix2/` dumps.

### 2026-08-15 — first player-ID ground truth + occlusion-aware eval; found far-side bystander takeover
- Annotated 44 frames of entreno_1 (canonical IDs 1–4; GT 1/2 near side, 3/4
  far; 61 boxes redrawn/added by hand, so GT is independent of predictions).
- New tooling: `scripts/annotate_player_gt.py` (interactive, resumable,
  pre-draws tracker boxes; 1–4 assign, D drop, A add, per-frame redo via
  `--start F --end F+1 --redo`), `scripts/flag_occluded_gt.py` (geometric
  occlusion flags: smaller box ≥50% contained in another → `visible: false`;
  20 flagged), `evaluate.py` now skips invisible GT + reads `foot_team`.
  67 unit tests green (was 48).
- Eval on 1c tracks: detection 0.69 (occlusion excluded), id_consistency 0.97,
  team 0.98. Near side (GT1/2) perfect — every box matched, stable ID map
  (pred3=GT1, pred1=GT2). Far side broken by bystander takeover → Open point 2.
- Learned: phase-1 "coverage 94%" on entreno_1 was partly fake — the tracker
  was covering far-side slots with out-of-court bystanders. The
  "detection-limited" story for entrenos is really "far-side detection weak
  AND tracker papers over it with wrong people".

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
