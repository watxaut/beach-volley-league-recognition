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
over-set crossings (f294) when the ball's width abstains. (The GT serve frame
was re-annotated f56 → f29 on 2026-08-17, owner-verified against the dumped
frames — entreno_3 label F1 is now **1.0** at 14/14 matched pairs.)

Below that, the player-identity stack stands as of `63ec741`: seed-dedup +
serve-zone admission (server tracked from f0, entreno_3 detection 0.96 /
id_consistency 0.97), bystander guard, upward-only ghost damping. 94 of the
113 tests predate this session.

**Config-drift guard (2026-08-17, later session):** `tests/test_config_drift.py`
(54 tests) locks the four seams where production and the GT scripts can
silently fork — DEFAULT_CONFIG ↔ component ctor defaults ↔ GT-script literal
kwargs + argparse defaults ↔ inline `.get(key, fallback)` fallbacks — so the
f539 block/spike class of bug can't recur unnoticed; 9 stale inline fallbacks
defused the same day. Suite 167 green.

**entreno_4/5 GT (2026-08-18):** owner-annotated (players every 10 frames, 6
action events each — no serves, no occlusion flags, side-noiseier footage as
warned). Checked end-to-end: boxes + box-teams fully consistent; 6/12 action
`player_id`s are mis-IDs (teams right) → Open points 1-2; baselines recorded
in the Log.

**Near-net flag (2026-08-17, later session):** old open points 4+9 closed by
diagnosis — 4's px→metres switch is GT-refuted (label F1 0.929 → 0.857/0.714):
the px `near_net` is load-bearing for the resolver's touch-3-at-net spike
rule. Point 9's block turned out to be REAL on the production/live-debug path
(a config divergence, fixed same day — see Log); the script path (all GT
numbers) always said spike. Details + revisit trigger in Open point 5 and the
Log.

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

1. **[owner action — quick] Re-verify the 6 mis-IDed action events in the
   entreno_4/5 GT.** In 6 of 12 events the `player_id` contradicts the event's
   own `player_team` (foot-side geometry of that player's box; 4 at the exact
   same frame). Arbitrated corrections (pred contact center lands inside the
   corrected player's box): e4 f133 p2→**p3**, f276 p3→**p2**; e5 f60 p2→**p4**,
   f250 p3→**p1**. Unarbitrated (pipeline had no event there): e5 f110 p2→?,
   f300 p1→? (p4 is adjacent at f300). Team labels are usable as-is. Also: no
   `visible` flags (run `scripts/flag_occluded_gt.py`), and confirm whether ALL
   touches are annotated — with a partial event list, measured precision is
   meaningless (e4's only "FP" f182 may be a real un-annotated touch).
2. **[diagnosis] entreno_5 tracking: roster may have locked to the wrong
   quartet.** detection 0.722 / ghosts 0.278 (vs e4 0.949/0.026); GT2 matched
   in only 1/36 frames while pred3 covers GT1 — with the extra people on the
   side the owner warned about. Dump + scrub the annotated video to see who
   pred3 actually locked onto; serve-zone admission in a crowded drill is open
   point 8's exact scenario.
3. **[BLOCKED — no footage] Validate side-change survival on a real match.** The
   gallery's marquee use case (players swap ends every 7 points) is untested —
   the entreno drills have no side changes. Blocked as of 2026-08-14: no video
   of a full set is available yet. Unblock by recording/obtaining one
   set-to-21 clip, calibrated, then:
   `python scripts/dump_player_tracks.py <match>.mp4 --max-players 4` →
   `python scripts/analyze_tracking.py <json> --max-players 4`, and scrub the
   annotated video through a side change watching each ID.
4. **[residual from the attribution fix] Over-set crossings without width
   evidence.** When a set/dig crosses the net but the tracked ball's widths sit
   in the 26–35px abstain band (entreno_3 f294: widths 29–40 through the gap),
   possession carries and the next contact is attributed to the wrong team.
   No counter-signal found that doesn't break a correct contact (above-net
   contact, gap length, touch index all fail on f539). Levers if it matters:
   per-video width calibration (e.g. from the serve flight), a proper camera
   calibration so pinhole size→3D works, or ball-detection recall on near-half
   approaches (currently often zero — occlusion).
5. **[diagnosed 2026-08-17 — deliberate no-change] The gesture path's image-px
   `near_net` is load-bearing; a px→metres switch is GT-refuted.**
   `_build_contact`'s `is_near_net` (px, `NEAR_NET_PX=120`) feeds BOTH
   `_detect_gesture` and the resolver's touch-3-at-net spike rule
   (`action_context.py:146`). Switching to ground metres regresses entreno_3
   label F1 0.929 → 0.857 (≤2m) / 0.714 (≤1.5m): GT spikes f174/f431/f539
   were hit from 1.79/3.77/1.96 m and only the px far-half swallow (every far
   player "near net") makes the resolver's rule fire for them; keeping all
   labels needs M≥4 m — re-encoding today's behaviour under a false name. The
   gesture layer itself is rule-INSENSITIVE on all GT footage (identical
   gestures under px/m1.5/m2.0 on entreno_1+3; every gesture-deciding contact,
   incl. entreno_1's only block at 0.23 m, sits within 2 m). The px boundary
   is nonsense in the abstract (server at 8.4 m reads far, a digger at 8.0 m
   reads near) but no footage we own can distinguish the rules. (2026-08-17
   addendum: production/live-debug briefly DID take the BLOCK branch at f539 —
   a config-default divergence, fixed same day, not a near-net regression; all
   measurements above are from the script path and remain valid.) Revisit when
   match footage exists (real overhead digs vs blocks at depth): re-run
   `output/diag_gesture_net.py <match>.mp4 --modes px m1.5 m2.0` and switch
   only if gestures differ.
6. **[same-team adjacent-player choice.]** The team filter constrains the TEAM,
   not which teammate — entreno_3 f69's dig goes to the wrong B player (both
   runs, team correct). Needs pose/reach signals, not team logic.
7. **[conditional] Phase 2: offline global stitch.** (unchanged) Post-processing
   pass that re-clusters all track fragments into exactly 4 identities. Only
   build if match validation shows residual swaps/fragmentation that phase 1
   doesn't catch.
8. **[watch] Serve-zone admission in crowded drills.** (unchanged) In drills
   with extras in the serve band, an extra can take the free slot before the
   real server; if a future dump shows a ghost behind a baseline, gate
   admission on `n_court_det < 4`.
9. **[minor] entreno_1 far-side recall.** (unchanged) `player_confidence`
   0.5→0.35 or `player_imgsz` ↑ if needed.

## Log (newest first)

### 2026-08-18 — entreno_4/5 GT checked: structurally valid; 6/12 action player_ids are mis-IDs (teams right)
- Owner added GT for entreno_4 (40 player frames @stride 10, 6 action events)
  and entreno_5 (36 frames, 6 events). Schema identical to e3; bboxes all sane
  and in-frame; court corners + net posts identical to e3 (calibrations 3=4=5
  byte-identical, same tripod spot) — and the player-box `team` labels are
  **100% consistent with foot-side geometry** (301/301 via
  `get_team_for_bbox`). No `visible` occlusion flags (pass not run), no serve
  events (drills start mid-rally), ball GT empty (as e3).
- **Finding:** in 6 of 12 action events the `player_id` contradicts the
  event's own `player_team` (the named player's feet are on the other half; 4
  contradictions at the exact annotated frame). Arbitration says the TEAM
  label is right and the PLAYER_ID wrong — annotator picked an adjacent
  same-area player. Evidence: where the pipeline detected the contact, its
  attributed player's center lands inside the corrected player's box (e4
  f133 p2→p3, f276 p3→p2; e5 f60 p2→p4, f250 p3→p1); e5 f110/f300 have no
  pred to arbitrate. → Open point 1 (owner re-verify; 4 suggested edits).
- **Baseline eval** (scripts on defaults; output/gt_check_e4|e5, git-ignored):
  - e4 actions P/R/F1 0.29/0.33/0.31 (7 preds vs 6 GT — the extra f182 spike
    may be a real un-annotated touch → precision unreliable until the event
    list is confirmed complete), team 1.0 (6/6), player-spatial 1.0 (5);
    tracking detection 0.949 / ghosts 0.026 / id 0.988 / team 0.987.
  - e5 actions P/R/F1 0.33/0.17/0.22 (only 3 contacts detected; both GT sets
    and both spikes missed — contact-recall problem under the side-noise),
    team 1.0 (3/3); tracking 0.722 / 0.278 / 0.993 / 0.981, GT2 matched 1/36
    frames → new open point 2 (roster may have locked onto a bystander
    quartet).
- No code changes; STATUS only. Run artifacts under output/gt_check_e4|e5/.

### 2026-08-17 — config-drift guard test built (candidate follow-up from the divergence fix)
- New `tests/test_config_drift.py` (54 tests) pins the four seams where
  production (`src.main`/live-debug) and the validated script paths can
  silently fork: (1) `DEFAULT_CONFIG` vs component **ctor defaults** (the
  scripts construct PlayerTracker/BallTracker bare, so ctor defaults ARE the
  script-side config — the original 30/90 + 100/150 drift lived here);
  (2) literal construction kwargs in test_action_recognition.py +
  test_ball_tracking.py, read by AST so editing a script literal without the
  config fails the suite; (3) the script's argparse defaults
  (`--pose-complexity`); (4) inline `<config>.get(key, fallback)` fallbacks in
  frame_processor / video_processor / main / dump_player_tracks. Deliberate
  divergences (ball_confidence 0.15 vs ctor 0.05, pose_complexity 0 vs ctor 1,
  action_confidence 0.3 vs ctor 0.4) are documented in the module docstring
  and pinned by the script tests instead. Two meta-guards keep the AST scans
  from passing vacuously if they stop matching.
- **Validation:** re-introducing the original drifts (config
  `player_max_disappeared`→30, main.py `ball_confidence` fallback→0.7) fails
  exactly the two expected tests; restored, all green.
- Same sweep defused **9 stale inline fallbacks** — dead today (every key
  exists in DEFAULT_CONFIG) but landmines the day a key is removed:
  frame_processor (ball_confidence 0.05, device "cpu" ×2,
  player_max_disappeared 30, pose_complexity 1, action_confidence 0.4),
  main.py (ball_confidence 0.7 — the old drifted value), dump_player_tracks
  (ball_confidence 0.5, device "cpu"). All set to the DEFAULT_CONFIG values;
  zero behavior change.
- Suite: 113 → **167 green**.
- Files: tests/test_config_drift.py, src/analysis/frame_processor.py,
  src/main.py, scripts/dump_player_tracks.py, STATUS.md.

### 2026-08-17 — live-debug showed block where the script said spike: config-default divergence FIXED
- Owner's live-debug screenshot (f562, red BLOCK label) disproved the morning's
  "never existed" verdict: a headless repro (`src.main --save-video`) shows the
  **production/live-debug path emits f539 → block (0.70)** while the script
  (and every GT number) says **spike (0.50)** — same contact, same player, same
  code, different CONFIG.
- Root cause: `Config.DEFAULT_CONFIG` had drifted from the constructor defaults
  the validated scripts run — `ball_confidence` **0.7 vs 0.15** (the starved
  ball history flips the f539 contact into the BLOCK gesture branch),
  `player_max_disappeared` **30 vs 90**, `tracking_max_distance` **100 vs
  150**. The tracking-section comment even claimed it "matches
  scripts/test_action_recognition.py". Verified no YAML/JSON override exists
  anywhere, so `src.main`/live-debug ran the drifted defaults silently.
- **Fix**: align `DEFAULT_CONFIG` to the validated values (0.15 / 90 / 150,
  with comments explaining they must not drift again); one stale assertion in
  `tests/test_components.py` updated; CLAUDE.md's "ball_confidence (0.7)"
  corrected.
- **Acceptance**: production headless re-run on entreno_3 emits the validated
  event stream EXACTLY (14/14 events, frames+labels+confidences identical to
  output/attrib_e3_new2; zero blocks). Pixel-level check of the user's exact
  screenshot frame f562: pre-fix 2400 block-blue px / post-fix 0 blue + 2711
  spike-red px, and the label region is the only changed area of the frame.
  113 tests green.
- **Correction of the morning entry below**: its "f539 block never existed in
  any run / born stale" conclusion was wrong — the archaeology ran the
  production path only at OLD commits (where the pre-attribution classifier
  didn't take the BLOCK branch at 0.7 either) and never ran CURRENT production
  code. The owner's original instinct (block appeared around the attribution
  change) was right: the attribution-era classifier + the 0.7-confidence ball
  stream produce the block; the script's 0.15 stream never does.
- Lesson recorded: GT-validate the PRODUCTION path too, or assert
  config-defaults == script-constructions in a test so drift like this can't
  silently fork the paths. (Candidate follow-up; not built today.)
- Files: src/utils/config.py, tests/test_components.py, CLAUDE.md, STATUS.md.
  Artifacts (git-ignored): output/livedebug_repro (pre-fix),
  output/livedebug_fixed (post-fix).

### 2026-08-17 — f539 "block" provenance settled: never existed in any run (owner challenge) — SUPERSEDED, see entry above
- Owner challenged the point-9 story: they remembered live debug showing f539
  as `spike` a couple of days ago and suspected the block→spike flip came from
  the team-attribution change. Git archaeology says: **their memory was right
  and the flip hypothesis wrong — f539 was spike before attribution too.**
- Evidence: detached-worktree runs of the PRODUCTION path (src.main =
  FrameProcessor = what live debug shows) at `128e53a` (Aug 15 morning, i.e.
  before BOTH the ghost exclusion d219aae and the attribution f276ca8):
  f539 → `spike (0.50)`, zero blocks in the whole timeline; the action script
  (buggy feeding and all) at the same commit: `Frame 539 → spike`; the
  attribution session's own diagnostic (output/diag_attribution2_run1.txt):
  spike; every attrib_e3_* log and the current state: spike.
- The "categorized as block" text first appears in STATUS at `6bd07c1` (Aug 17
  perf session), claimed to be folded from "the stale duplicate Open-points
  section" — but no committed STATUS version contains it (checked 970430e,
  d219aae, 63ec741, f276ca8, 663e455; the duplicate section's 5 items have no
  f539). Point 9 was **born stale** — a mis-sourced note at fold-in time, not
  a real regression that later got fixed.
- Incidental pre-fix-era observations recorded while there: the Aug 15
  production run misses the serve (no serve-zone admission yet) and instead
  emits a 14th contact ~f620 `overpass` that the current pipeline doesn't
  (contact-set drift between eras, worth remembering when comparing old logs).
- STATUS.md only (worktrees removed after use).

### 2026-08-17 — entreno_3 GT serve frame fixed (old open point 3)
- Owner scrubbed the dumped frames and confirmed the serve contact at **f29**
  (pipeline's own detection); GT event re-annotated f56 → f29 (single-line
  JSON edit, `git show 357cc14`). Eval on the existing prediction log
  (output/attrib_e3_new2): matched_pairs 13 → **14**, serve P/R 0 → 1, label
  **F1 0.929 → 1.0**; team unchanged 0.929 (13/14, the f294 over-set residual,
  open point 2). Footnote: player_accuracy_spatial now reads 0.857 (12/14)
  vs 0.923 (12/13) before — the serve pair entered spatial scoring and is one
  of the misses (it was previously unscored, not correct; no regression).
- Files: ground_truth/video_entreno_3_annotations.json, STATUS.md.

### 2026-08-17 — live-debug frame counter
- Small HUD added: `overlay.draw_frame_counter` (top-right, white text on a
  black underlay so it reads on sand too, format `f<idx>/<total>`), drawn in
  `LiveDebugProcessor._render_frame` — so both the `--debug-live` window and
  `--save-video` output now carry the frame number, matching how every event
  is referenced (GT annotations, STATUS, eval reports). Render-only change;
  pipeline untouched (mirrors-the-pipeline rule). Standalone
  `test_action_recognition.py` videos unchanged (noted in the class
  docstring). 113 tests green.
- Files: src/output_gen/overlay.py, src/analysis/live_debug_processor.py.

### 2026-08-17 — near-net gesture flag: point 9 stale, point 4's switch GT-refuted (no code change)
- **Point 9 did not reproduce**: the shipped state labels entreno_3 f539
  `spike` (GT f541 spike ✓, one of 4/4 correct spikes); it was folded in from
  a pre-attribution-shipment stale section. No block mislabels exist on any
  GT footage — the pipeline's only emitted block (entreno_1 f255) is genuinely
  at 0.23 m from the net.
- **Diagnosis first** (`output/diag_gesture_net.py` + saved per-variant JSONs,
  git-ignored; runs the exact test_action_recognition feeding under a
  monkey-patched `is_near_net`): the naive point-4 switch to ground metres
  REGRESSES entreno_3 label F1 0.929 → 0.857 (≤2m) / 0.714 (≤1.5m), because
  `near_net` also gates the resolver's touch-3-at-net spike rule
  (`action_context.py:146`): GT spikes f174/f431/f539 were hit from
  1.79/3.77/1.96 m and rely on the px far-half swallow to read "near net".
  Keeping all labels needs M≥4 m = re-encoding today's behaviour under a
  false name. The GESTURE layer itself is rule-insensitive on all GT footage
  (identical gestures under px/m1.5/m2.0 on entreno_1+3); the px boundary is
  absurd in the abstract (server at 8.4 m reads far, digger at 8.0 m reads
  near) but nothing we own can tell the rules apart.
- **Owner decision**: record, no production change. Revisit with match
  footage via the diag script; switch only if gestures differ there.
- Diag-tooling gotcha recorded: `classify_actions` builds contact k but
  EMITS contact k−1 (one-contact look-ahead) — per-contact foot diagnostics
  must zip build-order calls with event order, not attach per invocation
  (the first table was shifted by one contact).
- Files: STATUS.md only (diag script + JSONs git-ignored under output/).

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
