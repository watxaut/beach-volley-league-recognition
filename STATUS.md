# Project Status

> **Convention:** this file is the cross-session memory of the project. Read it
> first when coming back. Update it (and commit it with the work) at the end of
> every working session: refresh *Where we are*, move finished items into the
> *Log*, and re-rank *Open points*.

**Last updated:** 2026-08-17

## Where we are

**Team-aware contact attribution (old open point 2) is shipped and
GT-validated** on entreno_3: attribution team accuracy 0.69 → **0.92**, player
(spatial) 0.77 → **0.92**, label F1 0.90 → **0.93**, and the serve contact is
detected and labeled `serve` for the first time (f29, containment). The
winning design after a diagnosis-first sweep: candidates are filtered by the
expected touch team — from the **ball's pixel width** (near/far regime,
override) and **possession alternation** (flip after attack/serve/block,
carry after dig/set) — with per-contact **foot teams** via
`get_team_for_bbox`, a **ground-metre near-net exemption** gated on block
geometry (contact above the net-top line), and the emitted `team` now the
toucher's foot team (the resolver's latched possession used to mask
wrong-team thefts). The action script's tracker feeding was also fixed
(strict-set + no `strict_detections` had silently disabled serve-zone
admission in the action pipeline only). 113 unit tests green. Known residual:
over-set crossings (f294) when the ball's width abstains, and the GT serve
frame is ~26 frames after the physical hit (annotated f56, hit ~f30) so it
eval-mismatches at tol 15.

Below that, the player-identity stack stands as of `63ec741`: seed-dedup +
serve-zone admission (server tracked from f0, entreno_3 detection 0.96 /
id_consistency 0.97), bystander guard, upward-only ghost damping. 94 of the
113 tests predate this session.

**Perf (2026-08-17):** the detector device defaults were silently CPU —
`BallDetector`/`PlayerDetector` shadowed `BaseDetector`'s `"auto"` with their
own `device="cpu"`, so every bare construction (the annotator included) ran
YOLO on CPU (~150ms per annotation interaction). Defaults are now auto (MPS);
the annotator also gained sequential forward seeks (~6ms vs ~65ms keyframe
seek) and a (frame, mode) detection cache → ~30-40ms per interaction,
revisits free; pose runs the lite model (`pose_complexity` 0, new default)
after a byte-identical GT A/B on entreno_1/3. Pipeline per-frame ~102 →
~81ms. Live debug deliberately untouched — the owner wants it identical to
the shared pipeline for real debugging. Next lever if ever wanted: pose only
for near-ball players (measured 52→~26ms; needs an occlusion-window fallback
first).

**Plan reference:** the full design lives in the session plan file
(`~/.claude-zai/plans/i-want-to-start-golden-naur.md`, identity) and
(`~/.claude-zai/plans/read-status-lets-try-imperative-anchor.md`,
attribution — including the recorded design pivot away from image-plane
trajectory side). Short version of the identity architecture: uniforms vary/
are uncontrolled → colour can't be a trusted identity signal → **motion
continuity is the primary identity signal**, appearance/body-size are
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
2. **[residual from the attribution fix] Over-set crossings without width
   evidence.** When a set/dig crosses the net but the tracked ball's widths sit
   in the 26–35px abstain band (entreno_3 f294: widths 29–40 through the gap),
   possession carries and the next contact is attributed to the wrong team.
   No counter-signal found that doesn't break a correct contact (above-net
   contact, gap length, touch index all fail on f539). Levers if it matters:
   per-video width calibration (e.g. from the serve flight), a proper camera
   calibration so pinhole size→3D works, or ball-detection recall on near-half
   approaches (currently often zero — occlusion).
3. **[data] entreno_3 GT serve frame is late.** Annotated at f56; the physical
   hit is ~f30 (toss apex f23, flight apex f47 over the far court). The
   pipeline now detects+labels the serve correctly but eval-mismatches at
   tolerance 15. Fix by re-annotating that one event (or accept).
4. **[minor, pre-existing] `_detect_gesture`'s image-px `is_near_net` swallows
   the whole far half** (the far court is only ~110px deep; every far player
   is "near net" at 120px). The attribution path now uses ground metres
   (`world_dist_from_net`); the gesture path (block/attack labels) still uses
   px. Switch it if block labels misfire on far-side play.
5. **[same-team adjacent-player choice.]** The team filter constrains the TEAM,
   not which teammate — entreno_3 f69's dig goes to the wrong B player (both
   runs, team correct). Needs pose/reach signals, not team logic.
6. **[conditional] Phase 2: offline global stitch.** (unchanged) Post-processing
   pass that re-clusters all track fragments into exactly 4 identities. Only
   build if match validation shows residual swaps/fragmentation that phase 1
   doesn't catch.
7. **[watch] Serve-zone admission in crowded drills.** (unchanged) In drills
   with extras in the serve band, an extra can take the free slot before the
   real server; if a future dump shows a ghost behind a baseline, gate
   admission on `n_court_det < 4`.
8. **[minor] entreno_1 far-side recall.** (unchanged) `player_confidence`
   0.5→0.35 or `player_imgsz` ↑ if needed.
9. **[bug] entreno_3 last spike categorized as block** at frame 539 (suspect:
   open point 4's image-px `is_near_net` swallowing the far half).

## Log (newest first)

### 2026-08-17 — perf: detector device defaults, annotator I/O, pose-lite default
- **Measured first** (output/diag_perf_*.py, git-ignored): per-frame pipeline
  on entreno_3 = ~102ms core (pose 52ms CPU + ball 23 + player 25 MPS;
  trackers/game-state ≤1ms); the live-debug loop adds serialized
  waitKey(33ms)+render on top → ~5-7fps. The ANNOTATOR was ~150ms per
  interaction because BOTH its detectors ran on CPU:
  `BallDetector`/`PlayerDetector` shadow `BaseDetector`'s `device="auto"`
  with their own `device="cpu"` defaults, so every bare construction
  (annotate_video, test_action_recognition, dump_player_tracks, auto_label,
  test_* scripts) silently inherited CPU. Also: `cap.set` forward seek = 65ms
  vs 6ms for 5 sequential reads.
- **Fixes**: detector device defaults → "auto" (docstrings updated);
  annotator `_seek_frame` uses sequential reads for forward steps ≤64 when
  the capture cursor is contiguous, plus `_use_frame` cursor bookkeeping;
  detections memoised per (frame, mode-class — PLAYER/ACTION share one slot)
  so revisits/mode switches/undo are free; `pose_complexity` default 1→0
  (lite, ~1.6x faster pose) adopted only after the A/B; `--pose-complexity`
  arg on test_action_recognition.py (default 0 = production, so eval runs
  can't silently diverge from the pipeline again).
- **GT regression check** (entreno_1 + entreno_3, players + actions): all
  four eval JSONs BYTE-IDENTICAL across baseline (CPU detectors, pose 1) →
  post (MPS detectors, pose 0). entreno_3 tracking 0.961/0.064/0.972/1.0,
  actions team 0.923 / player-spatial 0.923 (13 pairs); entreno_1 team 1.0 /
  0.625 (8 pairs) — unchanged from the 2026-08-16 session. 113 unit tests
  green (run via `venv/`, not `.venv/` — only the former has pytest).
- **Measured gains**: annotator click-advance ~150ms → ~30-40ms (revisits
  ~0ms); pipeline per-frame ~102 → ~81ms (pose 52→33ms end-to-end).
- **Deliberately NOT done**: live-debug pose near-ball gating (52→~26ms
  measured) + producer/consumer display decoupling — owner wants live debug
  byte-identical to the shared pipeline while debugging for real. Levers
  recorded here for whenever they're wanted.
- STATUS.md cleanup: removed the stale duplicate "Open points" section (it
  predated the attribution shipment); its one fresh item (f539 block bug) was
  folded into the live list as point 9.
- Files: src/detection/{ball_detector,player_detector}.py,
  scripts/annotate_video.py, scripts/test_action_recognition.py,
  src/utils/config.py, STATUS.md.

### 2026-08-16 — team-aware contact attribution shipped (old open point 2)
- **Diagnosis first, and it changed the design.** The sanctioned retry
  ingredient (incoming-trajectory IMAGE side) was refuted by the diagnostic
  (output/diag_attribution2.py + probes, git-ignored): an airborne ball over
  the NEAR half projects ABOVE the midcourt line (line y≈600, net top y≈300,
  far baseline y≈490), so GT-A contacts f211/f244/f453/f488 all read "B";
  worse, the ball is often undetected during near-half approaches (occlusion
  by the large near players) — every A-contact window had 0 samples. Ball-size
  → ground-depth inversion also fails (an airborne ball is always closer to
  the camera than the ground under it → everything reads near-side), and a
  pinhole decomposition of the 4-click homography doesn't close (0.033
  orthogonality residual, reconstructed feet ~30m off).
- **f76 mystery solved (two findings).** The f76 contact is the GT f69 DIG by
  a far-side player (ball descending into GT4's box) — the earlier "serve
  misattribution" reading conflated it with the serve. The REAL serve contact
  is ~f30 (toss apex f23) and had been REJECTED (d=177.8) because
  scripts/test_action_recognition.py fed the tracker the strict in-court set
  without `strict_detections` — serve-zone admission never fired in the action
  pipeline (production FrameProcessor was already correct). Also found
  max_players=6 hardcoded there vs the production 4.
- **Shipped design** (src/recognition/action_classifier.py): expected touch
  team = ball pixel WIDTH regime (w<26 → far/B, w>35 → near/A, else abstain;
  any disagreeing sample blocks) when it commits, else possession
  alternation (flip after ATTACK/BLOCK/serve gestures, carry after dig/set;
  unconstrained on rally reset). `_closest_player_at` filters candidates by
  per-contact foot team (`get_team_for_bbox`), exempts wrong-team candidates
  only for block geometry (feet ≤1.5 ground metres from the net via new
  `CourtCalibration.world_dist_from_net` AND contact above the net-top line —
  image-px bands swallow the whole far half, and without the above-net gate a
  net-standing setter steals sets, f488), relaxes when the filter empties the
  set, and breaks 0.0-dist ties by centre distance. Emitted `team` is now the
  toucher's foot team (`team_in_possession` kept for observability) — the
  resolver's latch used to mask thefts behind an inherited label. Ball history
  now carries (frame, x, y, w, h). Resolver label/touch logic deliberately
  UNCHANGED (crossing-based touch counts match GT 14/14 on numbers but relabel
  f379 set→spike via the touch-3-at-net rule).
- **Measured** (13 frame-matched pairs, A/B = same feeding fix +
  `--no-team-aware`): team 0.692 → **0.923**, player-spatial 0.769 → **0.923**,
  label F1 0.897 → **0.929**; serve detected + labeled (f29, containment).
  Fixed: f211, f563, f488 (+ serve). Remaining miss: f294 over-set (width
  abstained 29–40px through the gap) — open point 2. entreno_1 regression:
  team 1.0 / player 0.625 identical across A/B, precision 0.778→0.875, recall
  unchanged (its misses are contact-detection recall, not attribution).
- **Eval tooling**: evaluate.py actions now report team_accuracy (pred team vs
  GT player_team) and player_accuracy_spatial (pred player_center → GT box →
  L-R index; the GT action player_id convention is the L-R index at the
  annotation frame — probe scored 12/14 vs 7/14 for canonical ids).
- Files: action_classifier.py, court_calibration.py (+
  midcourt_y_at_x/signed_midcourt_offset/world_dist_from_net),
  frame_processor.py, config.py (attribution_* keys),
  scripts/test_action_recognition.py (feeding fix, player_center,
  --no-team-aware), scripts/evaluate.py; tests/test_team_attribution.py (+19);
  suite 113 green.

### 2026-08-16 — server tracking fixed (open point 3) + ghost drift damped (4) + dead filter removed (6)
- **Diagnosis first** (output/diag_serve_probe.py + diag_serve_audit.py,
  git-ignored): the entreno_3 server was detected at conf 0.84–0.91 in EVERY
  frame 0–200 — the f10–175 untracked window was 100% tracker admission, NOT
  detection recall (the previous "honest detection gaps" read was wrong for
  the server). Three stacked causes: (a) bootstrap k-means forces k=4 from 3
  on-court people → a split cluster seeded a phantom 4th track (t3/t4 10px
  apart) that retired dormant at f38 and held the slot; (b) strict
  foot-in-court admission can never admit a server behind the baseline;
  (c) the dormant slot wasn't reclaimable for 60 frames (min-hold) and at f90
  a far-side walker position-restored it — wrong person.
- **Fixes**: (1) `_lock_roster_from_buffer` dedups seeds (IoU>0.35 with an
  already-locked seed) — a split cluster no longer inflates the roster;
  (2) serve-zone admission: `CourtCalibration.is_in_serve_zone` (ground-plane
  metres via the court homography; ≤3m behind a baseline, ≤1m beyond
  sidelines) is the only off-court foot that may open a NEW track (free slot
  required); serve-zone seeds start `last_in_court_frame=None` and
  `_may_feed_track` lets them re-feed out-of-court only from the zone itself
  (no gap-hijack); (3) create-loop now checks admission BEFORE eviction so an
  inadmissible detection can't burn a dormant slot; (4) `--serve-zone*` args
  in dump_player_tracks are real now. Config: `player_serve_zone_enabled/
  depth_m/side_margin_m`.
- **Measured** (dump + GT eval, output/servezone/): entreno_3 detection
  0.876→0.961, ghosts 0.114→0.064, id_consistency 0.929→0.972, team 1.00;
  GT2 (server) 50/67→65/67 @0.97, tracked from f0 with a 1:1 GT↔pred map the
  whole video. entreno_1: 0.923/0.133/0.978/0.986 — identical to fix2 (no
  regression).
- **Ghost drift (4)**: `_coast_step` damps UPWARD coast velocity
  (`coast_vertical_damping` 0.5). First attempt damped all vertical velocity
  and fragmented entreno_1 far-side ids (consistency 0.978→0.794) —
  court-axis running is image-VERTICAL. Upward-only: no regression on either
  video, jumps no longer ride up.
- **Cleanup (6)**: removed dead `CourtCalibration.filter_detections_by_play_area`
  + `is_point_in_play_area` (the detector-side bbox-overlap `detect_play_area`
  mask filter is the live path).
- **Action pipeline re-run** (entreno_3): 14 contacts, same set as before —
  the serve is still not labeled serve: its contact event fires at f76 but is
  attributed to the wrong player and labeled dig (see open point 2's new
  evidence). Server-side tracking is no longer the blocker.
- Tests: `tests/test_serve_zone.py` (+19); suite 94 green.

### 2026-08-15 — team-aware attribution attempted and reverted (findings recorded)
- Implemented ball-vertex-side candidate constraint in `_closest_player_at`
  (+5 unit tests); end-to-end run on entreno_3 showed regressions (vertex ≠
  touch position; smoothed team labels wrong near midcourt band) → reverted
  to the ghost-fix state; working tree back to `d219aae`. Everything learned
  is in open point 2, including the two signals a retry must not use.

### 2026-08-15 — action attribution: ghosts excluded from classifier (live-debug bugs triaged)
- Live-debug review of entreno_3 surfaced 3 bugs. Fixed now: `predicted`
  (ghost) players are excluded from `classify_actions` — no pose estimation on
  extrapolated boxes, no drifted bboxes in `_closest_player_at` (a ghost riding
  a jump's upward velocity had been stealing contacts).
- GT-verified effect on the reported events: dig f211 → now canonical 1 ✓
  (was the spiker), dig f563 → canonical 4 ✓. Sets f378/f488 still
  misattributed — adjacent same-line players, the true team-in-possession
  rules out the chosen player in both → parked as open point 2 (team-aware
  attribution) with this evidence. Serve f56 missed entirely (server
  untracked, open point 3). Ghost drift visuals parked (open point 4).

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
