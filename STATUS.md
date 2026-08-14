# Project Status

> **Convention:** this file is the cross-session memory of the project. Read it
> first when coming back. Update it (and commit it with the work) at the end of
> every working session: refresh *Where we are*, move finished items into the
> *Log*, and re-rank *Open points*.

**Last updated:** 2026-08-15

## Where we are

The **player-identity plan (phase 1) is implemented and committed** (`e13ea8d`),
and **entreno_1 now has real player-ID ground truth** (44 frames, canonical IDs
1–4, occlusion-flagged) with the metric awake: `id_consistency` 0.97, team
accuracy 0.98. **First GT-based finding: near-side tracking is essentially
perfect, but the far side suffers bystander takeover** — see Open point 2.

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
2. **[next, real bug] Far-side bystander takeover** (found via the new GT on
   entreno_1). Far-side tracks (small boxes) get assigned YOLO detections of
   people standing *outside* the court and never recover: pred tracks in-court
   rate 41% / 20% for the two far players; 35/39 unmatched far-side boxes are
   real detections with the foot outside the court polygon. Cause: court
   membership is enforced only at track creation (`_create_track` bystander
   guard, `player_tracker.py:590`); the assignment path accepts any detection,
   and the detector's `_is_player_in_court` is bbox-overlap vs court+margin,
   which near-court bystanders pass. Fix direction: reject (or heavily
   downweight) out-of-court detections in the assignment step so the track
   coasts/dormants instead — aligned with the plan's "no match beats wrong
   match". Careful not to break off-court servers (they're within the margin;
   bystanders are beyond it). Re-check with the eval command below.
3. **[optional, repeatable] GT for a second video** (e.g. entreno_3) using
   `scripts/annotate_player_gt.py` (~30 min) to confirm the takeover is
   systematic, not a one-off.
4. **[conditional] Phase 2: offline global stitch.** Post-processing pass that
   re-clusters all track fragments into exactly 4 identities (ensemble
   signature + time/space gaps + k=4). Only build if match validation shows
   residual swaps/fragmentation that phase 1 doesn't catch.
5. **[optional, separate axis] Detection recall.** Residual drops on entreno_3
   (~15% of frames) are genuine YOLO misses, not tracking failures. Levers:
   `player_confidence` (0.5 → 0.35 lifts recall ~3pp, adds false dets) or
   `player_imgsz`. Not part of the identity plan.
6. **[minor cleanup] `CourtCalibration.filter_detections_by_play_area` is
   currently unused** (the detector's bbox-overlap `detect_play_area` filter
   replaced it). Keep or remove.

## Log (newest first)

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
