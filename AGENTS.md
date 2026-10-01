# AGENTS.md

Instruction file for the harness. The project memory below was carried over
verbatim and must survive future edits. `CLAUDE.md` (architecture, commands,
config/GT conventions) was ABSORBED into this file on 2026-09-27 and
removed; the verbatim original stays recoverable via
`git show 09ceec2:CLAUDE.md`.

## Read-first rule (every session)

1. **`STATUS.md`** — the cross-session memory: current state, ranked Open
   points (treat as the backlog), standing Learnings, session index, and the
   last ~3 session Log entries. Read it before planning any work; update it
   at the end of every session that changes anything and commit it with the
   work.
   **Lean-STATUS convention (reorganized 2026-09-27):** *Where we are* is
   rewritten each session (never appended to); *Open points* get one compact
   entry each (status / problem / next step — collapse resolved
   `[UPDATE …]` stacks); the Log keeps only the last ~3 sessions verbatim;
   older entries move VERBATIM (never deleted) to
   `docs/history/status_log_archive.md` and
   `docs/history/status_where_we_are_archive.md`, and the session gets a
   one-line entry in the *Session index*. New durable protocol rules go
   here in AGENTS.md; new cross-session technical facts go one-line-each
   into STATUS.md's *Learnings*.
2. **`ground_truth/README.md`** — GT format (incl. spike enrichment fields
   and the entreno-anchor warning). Everything CLAUDE.md used to carry
   lives in the conventions sections below.

## Commands

```bash
make run VIDEO=resources/video_entreno_3.mp4        # full pipeline (device auto -> MPS on Apple Silicon); VIZ=1 adds graphs
make run-live VIDEO=...                              # --debug-live at 2x speed
make ui                                              # local web UI over data/volley.db
make ingest-all                                      # (re)ingest output/*/pipeline_output.json into SQLite
make db-reset                                        # DELETES the DB incl. owner player labels — ask first
venv/bin/python -m pytest tests/ -o addopts=""       # cov addopts break w/o pytest-cov
```

Per-component probes (`scripts/`): `test_court_calibration.py` (interactive,
one-time), `test_ball_detection.py`, `test_ball_tracking.py`,
`test_player_tracking.py`, `test_pose_estimation.py`,
`test_action_recognition.py` (the GT-validated action path — the
reference for any action A/B), `dump_player_tracks.py` +
`analyze_tracking.py` (tracking quality, no GT needed),
`evaluate.py --predictions <dir> --ground-truth ground_truth/` (ALWAYS with
`--ignore-player`; see STATUS Learnings), `evaluate_game_state.py`,
`evaluate_match_points.py`, `annotate_player_gt.py` / `annotate_video.py`
(owner GT passes).

## Architecture snapshot

Fixed camera on the court's LONG AXIS, net facing the camera; near half =
Team A, far = Team B (team = side of the midcourt line the feet are on).
Five layers under `src/`: `detection/` (YOLO ball + player, court
calibration) → `tracking/` (BallTracker, PlayerTracker) → `recognition/`
(pose + ActionClassifier) → `analysis/` (FrameProcessor orchestrates
per-frame; game_state_manager, spike_analyzer are pure observers) →
`output_gen/` (CSV/visualization; plus `db/` + `web/` fed by
`pipeline_output.json`). `FrameProcessor.process_frame` is the ONE shared
path — batch, scripts, and live-debug must all go through it.

Component invariants that bite if ignored:
- **BallDetector**: custom model (`ball_model_path`) needs no class filter;
  the COCO `yolov8n.pt` fallback filters to class 32 (+29). No top-1 cull
  (a high-conf spare must not hide the ball in play). Static handling is
  two-stage: persist ≥0.55 removed outright, ≥0.30 only flagged
  `stationary_suspect` for the tracker to distrust.
- **BallTracker**: returns None when lost — never hallucinates. Identity
  by trajectory + motion, never confidence alone: bootstrap/re-lock needs
  ≥8 px/f over a near-consecutive pair; locked admission = top-conf
  candidate inside the growing trajectory gate, with a stationary-suspect
  override so a rack ball can't starve the track; out-of-view exits hold a
  re-entry window (2× max_missing) instead of resetting.
- **PlayerTracker**: locks EXACTLY 4 (k-means bootstrap, Hungarian
  assignment); never a 5th track. Dormant gallery + squatter review +
  bystander guard live here — admission/gating changes are
  GT-validated territory (see entreno protocol below).
- **CourtCalibration**: interactive one-time 8-point JSON in
  `calibrations/` (4 corners + 2 net-ground + 2 net-top); provides
  `is_near_net` / `is_behind_baseline` / `get_team` / `is_above_net` /
  `world_point_to_zone` (9-zone grid per half, 180°-symmetric).
  Court detection uses NO model — `court_model_path`-style config keys
  are STALE, never wire them up.
- **ActionClassifier**: event-driven at ball-trajectory inflections only;
  Layer 1 gesture (motion + court + pose) → Layer 2 `ActionContextResolver`
  (dig/set/spike/serve/overpass from touch count). Pose gated on ball
  staleness/near-ball radius (shipped 09-27, byte-identical).
- **SpikeAnalyzer**: pure observer; `spike_type` by POST-CONTACT ASCENT
  (exit speed cannot separate touch/hard); `attack_zone` from the
  pre-contact takeoff stance (airborne contact feet project deep);
  outcome with loft-gated kill→dug retro-conversion (sand cannot rebound
  a dig's 2-3 m rise).

## Config, weights & artifacts

- Defaults: `Config.DEFAULT_CONFIG` in `src/utils/config.py`; override via
  `--config <yaml|json>`. Config-drift guard test pins DEFAULT_CONFIG ↔
  ctor defaults ↔ GT-script kwargs — extend it for new keys.
- **`ball_confidence` = 0.15 MUST match `scripts/test_action_recognition.py`**
  — every GT-validated action number was measured at 0.15; a diverging
  default silently flips gestures (the f539 bug class).
- Device: `auto` = CUDA > MPS > CPU. `make run` uses MPS on Apple Silicon;
  pass `--device cpu` for deterministic parity with CPU-measured baselines
  (MPS jitter can flip a gesture label — the script path is the reference).
- Required runtime weights (git-ignored, keep on disk):
  `models/volleyball_ball_best.pt` (fine-tuned ball detector, auto-loaded
  by main + the test scripts; currently v3) and `yolov8n.pt` (player
  detector + ball fallback). Training provenance (keep for retrain):
  `notebooks/finetune_yolo_ball.ipynb` (Colab, fine-tune FROM best.pt),
  `scripts/prepare_dataset_for_training.py`, `datasets/ball_detection/`.
- `archive/` holds unused weights and dead code — do not depend on it.

## Implementation conventions

- Draft a short plan and confirm the approach with the owner before
  writing production code for a new feature.
- Prefer extending existing modules under `src/` over new top-level files.
- GT annotation format lives in `ground_truth/README.md`; Roboflow (COCO
  export) is the annotation tool for detector retrains
  (`scripts/import_roboflow_coco.py`).

### 7. Recording domain (owner-stated 2026-09-30)

Durable facts about how the footage is captured. They are HARDWARE/setup
realities, not tuning opportunities:

- **One camera for every video except `video_david`** (a different camera,
  portrait 1564x2978, ~59.8 fps — out of spec, never validate on it).
- **Always long axis: the camera sits in front of the net, outside the court,
  net facing the lens.** It never moves mid-session. The tripod is re-set
  between videos, so **HEIGHT MAY CHANGE from video to video** (it is much
  higher at the practice venue than on the beach) — calibration is per video,
  and so is the meaning of every px threshold: the court projects 206 px deep
  on the beach vs 464–479 px at the practice venue, a 2.3x difference, which
  is why px-space constants are venue-coupled.
- **The camera DROPS frame rate on its own under low light or high
  temperature.** The 20260920 match is 25.67 avg fps inside a 30.12 VFR
  container; the 2026-09-28 practice video is ~30.1. Variable fps is therefore
  EXPECTED: never ask the owner to "fix" it at capture time, handle it in the
  timebase (PTS) and treat frame-based windows as approximate wall time.
- The 20260920 match is natively **1280x720**; `src/main` upscales it once to
  `_up1080`. All other footage is native 1920x1080.
- `docs/video_recording_guide.md` still prescribes a PERPENDICULAR-TO-NET
  camera — **STALE, it contradicts the validated geometry.** Rewrite it to the
  long-axis spec (open point 29) rather than moving the camera.

## Project memory

### 1. entreno validation protocol

If not told otherwise, always double-check any changes to the action logic
with `resources/video_entreno_*.mp4`. These are practice videos consisting of
only 1 point out of the 21. All except `entreno_1` have a serve; all others
start with a serve and end the point. Ground truths exist in `ground_truth/`.

The video_entreno_* clips are drills, not matches — but the early "they can't
validate re-ID" call was wrong twice:

- 1c appearance re-acquisition broke the detection ceiling on entreno_1
  (dropped-player frames 29.7%→0.8%, coverage 78%→93.7%).
- Then GT annotation exposed that some of that coverage was fake — far-side
  tracks were being fed out-of-court bystander detections. Fixed via
  court-membership enforcement in `_may_feed_track` (detection 0.65→0.92 on
  entreno_1).
- A "detection gap" for the server was actually tracker admission/gating —
  fixed with bootstrap seed dedup + serve-zone admission (entreno_3 detection
  →0.96, consistency →0.97).
- Lesson: before calling anything a detection-recall gap, probe raw detector
  output. Side changes remain unvalidated until real match footage.

### 2. Live debug must mirror the pipeline

The owner explicitly declined live-debug-only perf work: `--debug-live` must
run the exact same code path as batch — no divergent fast paths, because it
is used to debug the real pipeline (there was already one
eval-vs-pipeline skew bug). Speed up shared components instead. The pose
  near-ball + staleness gates were SHIPPED 2026-09-27 in
  `ActionClassifier`/`FrameProcessor` (byte-identical A/B, see STATUS); the
  still-parked lever is the live-debug producer/consumer display decoupling
  (open point 23) — it must not alter the processing path either.

### 3. Diagnose-first working style

The owner's working style that STATUS demonstrates in every entry but states
nowhere:

- Diagnose first before designing.
- Byte-identical A/B neutrality proof on unaffected videos.
- GT edits only via owner-ratified contact sheets.
- One mechanism per session.
- Gotcha: `cv2.setRNGSeed(0)` is required per PlayerTracker instance in
  multi-tracker A/B harnesses (`cv2.kmeans` consumes the process RNG).

### 4. Player-identity plan

The cross-session plan for consistent 4-player IDs:

- Core design: motion continuity is the primary identity signal;
  colour/uniforms can't be trusted; appearance is a tie-breaker; "exactly 4
  players" rejects bystanders. Side changes need no special handling if IDs
  survive.
- Implemented: 1a (two-zone filter, strict admission, 4-cap), 1b (dormant
  gallery, eviction-on-demand), 1c (ground-plane body size + ensemble
  signature), plus the later GT-validated mechanisms — bystander guard +
  serve-zone admission + seed-dedup (08-16), server vote + trial expiry +
  contested swap (08-18), off-court hold horizon =90f (08-29).
- Status: side-change validation still BLOCKED — no set-to-21 footage;
  Phase 2 (global stitch) sketched, unbuilt; `annotate_player_gt.py` ready
  for when footage arrives.

### 5. Attribution signals — long-axis camera

Safety-critical distinctions for contact attribution in this camera geometry
(fixed camera on the court's long axis, net facing the camera):

- Image-plane ball side: unusable (airborne near-half balls project "far").
- Ball pixel width + possession alternation: the working side signal
  (~14–28px far / ~30–55px near, abstain 26–35px).
- Near-net: attribution exemption in ground metres (2.5m) — but the gesture
  path's px `near_net` is load-bearing; px→m is GT-refuted (F1 0.929→0.857),
  revisit only with match footage.
- Emitted team = toucher's per-contact foot team.

### 6. Pass-2 interpretation layer (owner-ratified 2026-09-28)

Hindsight work — episode→point mapping, serve re-labeling, point
winner/outcome, fantasy scoring — lives in the POST-HOC layer over
`pipeline_output.json` / the DB, never as a second full-video pass.
Perception stays causal and single-pass through
`FrameProcessor.process_frame` (the trackers are online filters; a
re-decode reproduces the same tracks). A full-video two-pass
architecture is REJECTED: pass 1 cannot detect serves directly (every
ball-track serve feature was measured and refuted — open point 14a),
it breaks live-debug parity (a two-pass cannot exist live; that is the
eval-vs-pipeline skew bug class), and it doubles wall time for
perception output we already have. Escalation path for windows the
stream provably mis-serves (e.g. P15-class slow-float suppression):
targeted re-decode of FLAGGED windows with modified detector settings
(raw, no static suppression) — bounded, logged, never global.

New evidence may be added as **default-OFF pure observers inside
`process_frame`** (`src/analysis/serve_events.py`: `far_flight`,
`runway_occupant`, `serve_candidate`), provided three rules hold: they read
only values the pipeline already computed (detectors expose inert read-only
side channels — `PlayerDetector.off_area_detections`,
`BallDetector.raw_detections` — rather than re-running inference), they add NO
key to `pipeline_output.json` unless enabled, and their events are scored
against GT **including a NON-serve control window** for the false-positive side
before anything is allowed to act on them.

### 8. One session per working tree (owner-stated 2026-10-01)

Never run two agent sessions against this repo concurrently. Uncommitted work
is shared: a `git stash` for an A/B baseline sweeps up the other session's
uncommitted files, and long background pipeline runs import whatever tree
state exists at start — once a "new" A/B arm silently ran without the tested
changes. Serialize sessions, or give each session its own `git worktree`
(with `models/` and `resources/` symlinked in), and re-check `git status`
before any stash/checkout.
