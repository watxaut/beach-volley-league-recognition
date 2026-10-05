# STATUS.md archive — "Where we are" session blocks (2026-08-15 → 2026-09-27)

> Provenance: these are the per-session state summaries that used to accrete
> in STATUS.md's "Where we are" section, moved here VERBATIM on 2026-09-27
> when that section was reduced to the current state only. The detailed log
> entries live in `status_log_archive.md` (same directory). Nothing was
> edited; only the newest block (23rd session) is also distilled into
> STATUS.md's live "Where we are".

## Where we are

**(2026-09-27, twenty-third session — PERF SESSION: both parked pose levers
shipped, byte-identical everywhere; lever 3 parked as open point 23.)**

- **Shipped (one mechanism, `src/recognition/action_classifier.py` + config
  plumbing):** the 2026-08-17 parked perf levers, now that the owner asked.
  Pose is gated in the SHARED `classify_actions` path (batch + debug-live
  inherit it — the parity rule is respected; nothing in
  `LiveDebugProcessor` was touched): (1) **staleness gate** — no contact can
  consume pose past the reentry horizon, so once the ball is untracked
  > `pose_gate_stale_frames` (30 = `REENTRY_MAX_GAP`) MediaPipe is skipped;
  (2) **near-ball trail radius** — when the ball IS tracked, only players
  within `pose_near_ball_radius_px` (300) of a ball point in the last
  `NEIGH+2` frames are posed; a ball lost 1..30f ago (in-rally occlusion
  gap) still poses EVERYONE (the recorded occlusion-window fallback — bridge
  contacts fire at the first re-sighting and can consume an in-gap
  snapshot). A history entry is appended for EVERY observed player
  regardless: snapshot selection / L-R index / takeoff-stance read only use
  center+bbox+team, and they stay byte-identical; only the MediaPipe call is
  gated.
- **Measured first (probe `output/diag_pose_gate_probe.py`, all 7 entrenos +
  a 2500f match slice):** pose = 29.7 ms/frame at 3.54 calls/frame (the
  largest stage after the two YOLOs); the ONLY pose consumer is `_gesture`
  reading the snapshot `_closest_player_at` chooses for an ACCEPTED
  non-reentry contact (reentry returns ATTACK without pose — the e6 f311
  outlier with trailmin 1163px is exactly that, no pose consumed); every
  pose-consuming snapshot sits within **155 px** of SOME ball point in the
  last 9f → R=300 gives 2× margin and poses ~1.8 of 3.5 observed players on
  live frames. Staleness split: entreno 71% live / 27% occlusion / 1.6%
  dead; match slice 28/20/52 (dead = free skip).
- **Neutrality proof:** fresh HEAD baselines FIRST (output/posegate_base_*),
  then the edit, then A/B — **7/7 entreno action logs BYTE-IDENTICAL**; eval
  F1s exactly the recorded gate values (0.706 / 0.571 / 1.0 / 0.933 /
  0.923 / 0.933 / 0.75, teams 1.0 except e6 0.857). **FULL match production
  re-run** (output/match20260920_posegate/): results.csv,
  results_detailed.csv, results_game_state.csv, results_spikes.csv ALL
  BYTE-IDENTICAL to the e3fix gate record; points 31/33, episodes 57,
  0-before-first unchanged; the only diff is the self-referential timing
  row. Suite **477 green** (+12 tests/test_pose_gate.py; config-drift pins
  the two new keys across DEFAULT_CONFIG/ctor/FrameProcessor).
- **Measured gains:** match 38 → 30.5 min wall (84.8 → 68.0 ms/frame,
  11.79 → 14.71 fps, ×1.24); match probe slice ×1.19 (76.1→64.2) with the
  contact stream identical; entreno ×1.13 (~96→85 ms/f) — dead time is
  where the staleness gate pays, entrenos are mostly live ball.
- **PARKED as open point 23:** the live-debug producer/consumer display
  decoupling (the other 2026-08-17 lever) — owner's call when wanted; it
  buys live fps only, not batch time.

**(2026-09-27, twenty-second session — open point 22: scoping leg done,
one finding RETRACTED, one SOLID corrected specimen.)**

- **RETRACTED:** the “far-side 0/5 vs near-side 2/7 serve-emission”
  measurement and the “P2 TOTAL miss / P6 starved” specimens from earlier
  in this session. Root cause: `ground_truth/gt_point_start_end.txt` was
  treated as MATCH serve anchors — it is the game-state GT for
  **video_entreno_game_state.mp4** (30fps, 4.5 min, 13 points; every
  diag_gs_* script pairs them; the GT README documents it). Mapping its
  timestamps onto the 17-minute match produced fictional windows
  (“P2 = 539..821” is dead time; P2's real rally is f889–~1032).
  README now carries a hard warning; tests use synthetic anchors.
- **SURVIVES the retraction:** serve TEAM is derivable mechanically
  (winner-of-previous; cross-checked 6/6 against dictated server mentions;
  P1 unknown) and side from GT conventions (A near at start, switches
  after 7/14/21/28) → **16 far / 16 near serves**. The keeper
  `scripts/derive_match_serve_windows.py` (+17 tests, suite 465) encodes
  this; WITHOUT --anchors it emits server+side only (UNANCHORED) — correct
  default until ratified match anchors exist. Also survives: the
  pipeline's confirmed spans do NOT map 1:1 to GT points (c8 straddles
  P12/P13), so episode-order alignment needs its own careful pass.
- **THE CORRECTED SPECIMEN (production-parity probe,
  `output/diag_farside_serve_probe.py`, continuous f0..6948 dump):** P2's
  far-side serve (“Team B fails serve out”, B far) is tracked END-TO-END
  by the production ball tracker: pre-serve hold (992,507) f626–640
  (stationary-flagged, correctly not locked), toss from f889, LOCK at
  f890, then REAL on ~65 of 72 frames through apex (913,276), descent,
  sand bounce ~f928 and roll past f960; conf 0.24–0.90; only f928–929
  read predicted during the fastest descent and re-acquired immediately.
  **The owner-visible P2 loss is NOT ball tracking**: game_on fired only
  at f925 (36f after lock — ep 925..1032, later STARVED → point never
  confirmed) and NO serve action was emitted for the rally. For 1-touch
  serve-out points the loss lives in the game-state episode/confirmation
  + rally-opening serve-ACTION gate (open point 15a machinery), not in
  the ball half.
- **Probe-infra lesson (bit me, must not again):** cv2
  `CAP_PROP_POS_FRAMES` seeks are frame-UNRELIABLE on this VFR file
  (25.67fps content in a 30.12fps container) — seek-based sheets were
  index-shifted; the pass-1 sequential dump is the ground truth. All
  frame-accurate work must decode sequentially.
- **NEXT (re-scoped, one mechanism):** build the episode→GT-point ORDER
  map (57 episodes ↔ 33 points + non-point bursts, keyed by derived serve
  team/side + descriptions + emitted actions; flag unratified), THEN the
  far/near serve census and probe verdicts on TRUE windows; owner pass
  with `annotate_video.py`/contact sheets can ratify anchors afterwards.
  The 20-vs-28 serve-emission regression (v3 vs v2) stays the headline
  symptom; P2 says check the serve gate + episode starvation first.

**(2026-09-27, twentieth session): e3 DRIFT FIXED WITHOUT GT EDITS.**
The owner ruled the GT stays; the pipeline had to heal. See the Log entry
for the full three-mechanism diagnosis and the one shipped fix.

- **Mechanism A (FIXED — the whole F1 regression):** v3's tracker ACCEPTED
  the true arc bottom at f379 (1041,406) — base's tracker starved that
  frame because a moving bystander out-confd the ball (0.76 vs 0.70; the
  top-conf primary fails the gate → trusted coast, in-gate ball never
  tried). With f379 real, the bounce vertex moved f378→f379, but v3 was
  blind at f385-386, so f379's right side had 1 point within NEIGH (no
  vertex) and f384's left3 was empty (no drive) — the short-gap bridge at
  c=384 refused as "dense both sides: normal turf" although the normal
  path provably could not host the touch. The SET (GT f379) vanished and
  the touch chain reset: f431 spike→dig(t1), f453 dig→set, f488 set→dig,
  f539 spike→block(t2) — the resolver's touch-3 poke rule is what turns
  the block gesture back into SPIKE once the chain is restored.
- **The fix (one mechanism, `action_classifier.py`):** the short-band
  dense-side refusal now additionally requires `_normal_vertex_in_range(a0,
  c)` — some real sighting in the gap range can actually host a normal
  contact (checked by REUSING the normal tests, factored out pure as
  `_normal_contact_at`, so no duplicated thresholds). e6 f265's protected
  case still defers (its vertex is fireable); +2 unit tests pin both
  sides. e3 F1 1.0 (14/14, team 1.0, spike_type 4/4, attack_zone 1.0,
  dug_zone 1.0); e1/e2/e4/e5/e6/e7 BYTE-IDENTICAL to the gate record;
  base-weights rerun 7/7 BYTE-IDENTICAL (neutrality proof); suite 448.
- **Mechanism B (moot, recorded):** at f539 v3's ±px jitter tipped
  |inc[0]| 18→21 across XREV_MIN=20, so the redirect test (which runs
  before the drive test) stole the kill contact → gesture block. Harmless
  once Mechanism A is fixed: at touch 3 the resolver deliberately falls
  through block to the poke rule → SPIKE 0.5 (exactly base's path). The
  `touch < 3` guard on the block label is load-bearing — do not reorder
  the redirect/drive tests.
- **Mechanism C (diagnosed, UNFIXED — tracker-side, queued):** e3 f539's
  outcome enrichment reads dug vs GT kill (base read kill; landing_zone
  0.0 in BOTH — GT B8 vs emitted B7 pre-exists). Root cause: v3's conf dip
  on the fast-falling ball at f613-618 (no dets ≥0.15; base caught f614 at
  0.45) lets the coast leave the court-bounds box → re-entry window arms
  and rejects the falling dets at f619-622 → track expires at f623 → the
  analyzer's post-dig flight ends mid-air (no landing → no dug→kill
  conversion at flush). Fix levers, owner's call: round-3 mining of
  fast-fall positives (same pipeline as round 2 — and the SAME v3 conf-dip
  family as open point 22's far-side serves) or a re-entry-window retune
  (match-wide risk, needs its own gate).
- **Match re-run (`output/match20260920_e3fix/`, production parity):**
  confirmed **31/33 (0.939)**, episodes 57, 0 before first confirmed
  (first-confirmed = GT pt 1) — ALL identical to the v3 gate record;
  actions 207 vs 206: exactly one bridge-recovered dig (in GT pt 5), every
  other label identical (dig 84 / spike 45 / set 42 / serve 20 /
  overpass 9 / block 7). The point layer is untouched.

**(2026-09-26, nineteenth session — gate leg): ROUND-2 GATE RUN →
ADOPTED. v3 (fine-tuned FROM best.pt on 1091 + 350 rebalanced frames)
passed GT-frames, match and probe legs decisively; entreno drift-lock
failed 4/7-exact; the owner ADOPTED it. Production
`models/volleyball_ball_best.pt` = v3 (md5-verified); old production
stashed as `volleyball_ball_best_v1_entreno.pt`; v2 kept for reference.
All future defaults (main.py, test scripts) now run v3 behavior — the
gate artifacts ARE the production-behavior record.**

- **Leg 1 GT-frames (486 frames, 3-way, output/retrain_eval/gt_frames_v3.log):**
  recall 58.3 (old) / 57.8 (v2) / **94.2 (v3)**; @0.4 precision 39.9 / 25.3 /
  **95.5**; dets 1750 / 3026 / **422** (the venue noise is gone); FP@0.4
  330 / 682 / **18** (sky 31 / 236 / 11); blind-class recall 57→**94.6**;
  TRUE-det conf: sky 0.85 med 100% ≥0.4, sand 0.81 med 93.5% ≥0.4 (the
  background-confidence skew is DEAD); leakage-free valid split (59 frames
  under the current 1441-pair split): 88.1 / 92.9.
- **Leg 2 entreno A/B (output/retrain_eval_v3/, --ignore-player; base
  reproduced the recorded 7 F1s EXACTLY):** e1 0.706 / e2 0.571 / e6 0.933 /
  e7 0.75 all EXACT; **e3 1.0→0.667** (new: block FP, spike 2 FN), e4
  1.0→0.933 (overpass FP f386 — same mode as v2), e5 1.0→0.923 (opening
  serve lost — same mode as v2); **e6 team 1.0→0.857** (one misattributed
  contact; v2 kept team 1.0×7). Drift-lock FAIL.
- **Leg 3 match (output/match20260920_v3/):** confirmed **31/33 GT (0.939)**
  vs 15 (v2) / 13 (base); episodes 57 (26 starved); first-confirmed at GT
  point **1**; actions **206** (dig 83 / spike 45 / set 42 / serve 20 /
  overpass 9 / block 7) vs 104 / 90. Serves 20 vs v2's 28 — the one match
  metric that went DOWN; watch after adoption.
- **Leg 4 probe (output/retrain_eval/ball_probe_v3_3way.log):** tracked
  coverage old→v2→v3: ep02 6→10→**28%**, ep06 24→31→**42%**, ep12 4→7→2%
  (both ~dead — hardest episode), ep08 11→11→**23%**, ep35 49→46→**78%**;
  flight ep35 42→**60%**. ep35 sky cand conf med / ≥0.4: 0.90/92 (old) →
  0.47/51 (v2) → **0.85/99 (v3)** — the v2 killer is fixed. Blind% ROSE
  (25→51, 10→52, 31→94, 16→58, 20→20): that is the noise leaving, not
  recall dying — class (b) conf-rejectable collapsed to 1-8%, and the
  GT-frames leg proves 94% recall where a human sees a ball.
- **Adoption + follow-ups:** owner adopted v3 (see header). Queued:
  (i) re-adjudicate e3/e4/e5/e6 against the v3 streams (owner-ratified
  contact sheets) — the GT was dictated against base-model behavior, and
  e4's "overpass" may be a real event base couldn't see; (ii) mechanism
  read on e6's one-contact team flip before it is called a detector bug;
  (iii) **new owner feedback = open point 22 (far-side serve tracking)**;
  (iv) re-rank open point 21 — point-layer re-tune (item 1) likely moot
  at 31/33 with first-confirmed at pt 1 (verify the residual 2 aren't
  far-side-serve losses); winner/side-switch/confidence layers are the
  frontier.

**(2026-09-26, nineteenth session — mining leg): ROUND-2 BALL RETRAIN STAGED — 350
rebalanced frames await the owner's Roboflow annotation; pipeline src
untouched, suite 446 green.**

- **`scripts/mine_ball_frames.py` + `--exclude-manifest` (keeper, +6 tests →
  suite 446):** same production-parity scan (best.pt, conf 0.15, _up1080,
  30f warm-up, det.reset per range); scanned classes BYTE-IDENTICAL to the
  round-1 scan (blind 1843 / low_sand 1407 / low_other 1541 / sand_noise
  1100 / sky_control 1233 / high_other 870) — the determinism check came
  free. Exclusion is same-class ±spacing (classes are deterministic, so a
  round-1 pick can only collide with this round's pool of the same class).
- **The round-2 set (`resources/frames/match20260920_round2/`, git-ignored,
  222MB, README.md inside):** 200 sand_noise picks (pool 1100 → 449 after
  excluding round-1's 60 picks ±5f) + 150 sky_control picks (1233 → 809
  after round-1's 40) — caps hit exactly, span f240..f26004, no exact
  collisions. **NO pre-labels** (`--no-prelabel`): round-1 audit showed
  ≥0.4 sky pre-labels were on the owner's ball 3/77 — wrong labels are
  worse than none. Noise frames = negatives by construction (owner adds a
  box if they see a ball); sky frames = true ball or null (the nulls are
  the sky-FP negatives v2 lacked). Footnote: 118/350 picks sit ≤5f from a
  round-1 pick of a DIFFERENT class (noise/blind interleave inside
  rallies) — accepted, different content; remember if the valid split
  looks optimistic.
- **Notebook round-2-ized (`notebooks/finetune_yolo_ball.ipynb`):**
  `BASE_MODEL = "/content/volleyball_ball_best.pt"` — fine-tune FROM the
  production weights to preserve the sky prior round 1 lost (ep35 med
  0.90→0.47); `"yolov8n.pt"` reproduces round 1. Recipe unchanged
  (freeze=10, imgsz=1280, epochs=100); run + download renamed *_r2 so the
  production best.pt stays untouched for the A/B.
- **Owner court:** annotate the 350 (COCO export from the dataset page —
  the rapid download was broken) → `import_roboflow_coco.py` →
  `prepare_dataset_for_training.py` → zip → Colab r2 → weights back.
- **Then the SAME four-leg gate as round 1:** GT-frames eval → entreno A/B
  drift-lock (all 7 F1s, `--ignore-player`) → full match +
  `evaluate_match_points` → `diag_ball_probe_bgsky.py` on the 5 episodes.
  Gate criteria: keep class-(a) wins (blind ≤ round-1 v2 numbers),
  precision @0.4 back ≥ ~40%, sky TRUE conf med back near 0.9, entreno
  7/7 exact.
- **Still queued after that:** session D (point-layer re-tune — the
  binding constraint for point COUNT), then the rest of open point 21.

**(2026-09-25, eighteenth session): RETRAIN-MINING SESSION — the
detector half of open point 20's second lever is PREPARED: 500
stratified frames from the 20260920 match await the owner's Roboflow
annotation. Pipeline src untouched.**

- **`scripts/mine_ball_frames.py` (keeper, tests +16 → suite 435
green):** scans the GAME_ON ranges of a results_game_state.csv (default:
the floors-ON rerun) with the production-parity detector
(`models/volleyball_ball_best.pt`, conf 0.15, `_up1080` file, 30f
static-suspect warm-up per rally, `det.reset()` between ranges) and
stratifies every frame with the probe's `bg_class` (kept identical):
`blind` (0 cands) / `low_sand` / `low_other` (cands but none ≥0.4,
best non-suspect's bg) / `sand_noise` (suspects only — hard NEGATIVES)
/ `sky_control` (≥0.4 sky-backed — regression guard). ≥0.4 non-sky
frames are `high_other`: recorded in the manifest, NOT mined. Sampling
= seeded shuffle + greedy min-spacing (5f) per class; two decode passes
(classify all, then write only picks).
- **Full-match scan (7994 game_on frames, 48 ranges): blind 1843 (23%),
low_sand 1407, low_other 1541, sand_noise 1100, sky_control 1233,
high_other 870.** Class (a) at 23% of ALL game_on frames — the
tracker-side floors could never have fixed this alone; the retrain is
load-bearing.
- **The annotation set (`resources/frames/match20260920/`, git-ignored
like datasets/):** 500 JPG q95 (318MB) named
`20260920_match_ari_joan_lost_f<idx>` (source-stem via
`resolve_source_stem`; no collision with the dataset's flat
`frame_XXXX` namespace) + YOLO pre-labels (all non-suspect cands ≥0.15;
empty txt for blind/noise = negative unless the owner finds a ball) +
`manifest.json` audit trail. Pre-label sanity via a ±2-frame
motion-support proxy: 8/12 on smoke-set low picks — consistent with the
probe's ~60%; blind picks show nothing at ±2 either (genuinely hard,
human-only). Picks span f297..f25991.
- **Owner handoff — COMPLETED 2026-09-25/26 (see the annotation leg
below):** the owner hand-annotated in Roboflow; the dataset is merged
and the training zip is BUILT.
- **Validation gate when weights return (one session):** entreno A/B
drift-lock (all 7 F1s must hold) → full match re-run +
`evaluate_match_points` → re-run `diag_ball_probe_bgsky.py` on the same
5 episodes to quantify class (a)/(b) shrinkage vs the recorded
baselines.
- **Still queued after that:** session D (point-layer re-tune — the
binding constraint for point COUNT), then the rest of open point 21.

**(2026-09-26, the annotation leg of the eighteenth session — OWNER
GT LANDED, DATASET MERGED, ZIP BUILT; one big diagnostic correction.)**

- **The owner's report:** the shipped pre-labels were MOSTLY WRONG, so
they uploaded the images WITHOUT labels and annotated one by one
themselves. Export came as COCO from the dataset page (the version
page's "rapid" download was broken); 486/500 frames made it (14 lost:
6 blind / 3 low_sand / 2 low_other / 2 noise / 1 sky — accepted).
Export images verified PIXEL-IDENTICAL to our mined frames (mean abs
diff 0.00, n=346).
- **DIAGNOSTIC CORRECTION (load-bearing for future probe reads):**
pre-label-vs-owner-GT audit — our raw candidates were almost never on
the owner's ball: low_sand 0/155 same-place, low_other 0/71,
sky_control 3/77. Even ≥0.4-conf SKY-BACKED picks were mostly not the
ball per human GT. Raw detector precision on this venue is far lower
than the probe assumed; the tracker's motion/geometric gates (not
confidence) carry production. Many probe "class (b)" candidates were
sand noise, not missed balls. The floors mechanism keeps its
entreno-neutrality + match action gains, but the retrain now attacks
precision too, not just recall.
- **Owner GT:** 423 boxes on 486 frames; 208/244 exported blind frames
got a ball (the class-(a) gold); 73 frames empty = negatives; 6
degenerate <2px boxes (click droppings) dropped with per-frame report.
Box widths: med ~25px, tail to 95px.
- **`scripts/import_roboflow_coco.py` (+5 tests, suite 440 green):**
strips Roboflow's `_jpg.rf.<hash>` suffix back to canonical mining
names, COCO→YOLO conversion, non-ball categories ABORT (never silently
become class 0), refuses canonical-name collisions, empty labels =
valid negatives.
- **Merged + zipped:** `datasets/ball_detection/` now 1091 images
(605 entreno + 486 match); `ball_dataset.zip` rebuilt 1.7G — 928
train / 163 valid (418/68 match frames mixed in). Gotcha hit: disk
filled mid-prepare (Errno 28) — removed the partial `yolo_dataset/`
staging dir and reran fine.
- **NEXT (owner):** Colab `notebooks/finetune_yolo_ball.ipynb` —
upload `datasets/ball_detection/ball_dataset.zip`, T4 GPU, run all
(same recipe: yolov8n base, freeze=10, imgsz=1280, epochs=100). Then
hand the weights back for the validation-gate session.

**(2026-09-26, third leg — the VALIDATION GATE ran; candidate
REJECTED; production untouched.)** The owner trained in Colab (same
recipe) and dropped the weights in the repo root; stashed as
`models/volleyball_ball_best_v2_match.pt` (old weights untouched for
A/B). Gate legs:

- **GT-frame eval (output/retrain_eval/diag_gt_frames.py, 486
owner-GT frames, stateless raw predicts @0.15, imgsz 1280, IoU 0.3):**
recall FLAT (old 58.3% / new 57.8%; valid-split 50.8→47.7%); detections
1750→3026 with precision 13.9→8.0%; at the 0.4 gate: recall 52.5→55.4%
but precision 39.9→25.3% (confident FPs 330→684, sky-backed 31→236).
TRUE-det conf by bg: sand med 0.63→0.80 (62→82% ≥0.4), other 88→100%,
sky 98.8% both — the intended confidence fix is real ON TRAINED FRAMES.
- **Entreno drift-lock: FAILED 3/7** (test_action_recognition +
evaluate --ignore-player on both runs): e1 0.706, e2 0.571, e3 1.0,
e6 0.933 EXACT; e4 1.0→0.933 (+1 FP overpass f386), e5 1.0→0.923 (LOST
the opening serve f17), e7 0.75→0.625 (lost the fragile f242 set,
gained f440 dig). Team 1.0 everywhere. **EVAL GOTCHA (record): the
recorded F1s require `--ignore-player`** — GT player_id is a per-frame
L-R index; with player matching on, IDENTICAL streams score 0.933 vs
0.133. First read of this leg falsely looked like a crash; always
mirror the baseline invocation.
- **Match re-run (output/match20260920_retrain/):** actions 90→104
(serves 21→28, spikes 10→16, sets 4→9, digs 42 flat, block 2,
overpass 7); episodes 48→63 (MORE fragmentation); **confirmed points
13→15 (ratio 0.394→0.455)**; first-confirmed ordinal 4→7.
- **Probe re-run (diag_ball_probe_v2.py + ball_probe_v2.json; floors ON
in both tracker chains now — tracked% has floor parity, candidate stats
are model-only):** class (a) blind frames SHRANK everywhere — ep02
25→2%, ep06 10→3%, ep12 31→19%, ep08 16→15%, ep35 20→9% (the retrain's
genuine win). But ep35 (control) sky-backed candidates med conf
0.90→0.47, ≥0.4 share 92→51% — the OLD model's crown jewel REGRESSED on
unseen sky; sand/other pool confs ~flat (the FP flood dilutes).
Tracked: ep02 2→10%, ep06 25→31%, ep12 0→7%, ep08 4→11%, ep35 47→46%.
- **VERDICT: REJECTED as a drop-in.** It buys class-(a) recall and +2
confirmed points but pays with raw precision (2× confident FPs), sky
regression on the control episode, and 3 entreno F1s moved — the
neutrality bar and the robustness story (sky-confident tracking is the
working regime) both break.
- **Round-2 spec (open point 20):** rebalance the mining set — many more
PURE NEGATIVES (sand-noise pool scanned 1100, only 60 exported; plus
empty frames beyond the 73) and many more SKY POSITIVES from the match
(scanned 1233 sky_control, only 40 exported) to protect the crown
jewel; consider fine-tuning FROM volleyball_ball_best.pt instead of
base yolov8n; retrain → same gate. One lever at a time.

**(2026-09-24, seventeenth session — TWO commits; full detail in the
log entry): (1) match GT transcribed** (`parse_match_gt_text.py` →
`ground_truth/20260920_match_points.json`, 33 points, winners mechanical,
switches after 7/14/21/28) **+ `evaluate_match_points.py`** (baseline 14/33
confirmed, first-confirmed ≈ GT pt 8) **+ the background-stratified ball
probe** (sky med 0.90 / sand 0.20 — the "blue sky" report quantified;
class (a) blind 10-31%, class (b) conf-rejectable 33-68%). **(2) The
conf-floor mechanism shipped** (`ball_locked_low_conf_floor` /
`ball_boot_low_conf_floor` 0.15, zero-high-frames scope, drift-locked,
suite 419): entreno FULLY NEUTRAL (all 7 F1s, team 1.0); match actions
74→90, serves 13→21, first-confirmed ≈ GT pt 4, ep f9150 confirmed;
point count flat 13 — the point layer became the binding constraint
(session D); game-state guard 10/13 vs a FRESH floors-off 11/13 (the old
80.6% recording was stale). Artifacts: output/match20260920_lowconf/,
output/lowconf_gs_off.yaml.

**(2026-09-24, sixteenth session): CALIBRATION AUTO-DETECT FIXED FOR CACHED
_up1080 FILES.** Owner report: live-debug on
`resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4` reported
"court not calibrated" although the court was clicked — because the run
was pointed at the CACHED upscale file while the calibration lives under
the SOURCE stem (`calibrations/20260920_match_ari_joan_lost.json`); the
720 original worked because its raw stem matched. Fixed with one shared
helper `resolve_source_stem()` in `src/utils/video_upscale.py` (the module
that owns the `<stem>_up<target>.mp4` naming): strips a trailing
`_up<digits>` suffix; wired into `src.main` (calibration auto-detect +
annotated-video naming), `scripts/test_court_calibration.py` (its private
regex deduped onto the helper — the WRITE side and the READ side now share
one implementation), `scripts/dump_player_tracks.py` (the explicit
`--court` workaround from the fifteenth session is no longer needed) and
the four diagnostic `scripts/test_*.py` auto-detects. No pipeline/behavior
change: `ensure_1080` passthrough is untouched, entreno stems never match
the pattern. Suite **387 green** (+8 tests/test_source_stem.py, pure
function + a calibration-script contract test; cov addopts still need
`-o addopts=""` without pytest-cov).

**(2026-09-23, fifteenth session): FIRST FULL-MATCH RUN — the point layer
STARVES (14 confirmed vs ≈39 rallies), the player roster HOLDS but identities
HOP; root cause is BALL-TRACK RECALL on this footage, not the point machine.
No src changes — diagnosis only, all artifacts in git-ignored
`output/match20260920/` (pipeline run, tracks dump, ball-only pass, sheets,
`diag_match_analysis.py`).** Owner score statement: final ~21-15, near team
of the first point wins → ≈36 rallies.

- **What ran:** (1) full production batch, `python -m src.main`
  `resources/full_videos/20260920_match_ari_joan_lost.mp4 --output-dir
  output/match20260920` (38 min MPS, ~11 it/s; calibration auto-detected,
  verified aligned on 3 spread frames). (2) production-config
  `scripts/dump_player_tracks.py` on the `_up1080` file (passing
  `--court calibrations/20260920_match_ari_joan_lost.json` explicitly — its
  stem auto-detect misses cached files). (3) a production-parity BALL-ONLY
  pass (`diag_ball_pass.py`, FrameProcessor ctor args mirrored). (4)
  `scripts/analyze_tracking.py` + `diag_match_analysis.py`.
- **POINTS — episode layer right, point layer starved.** 39 GAME_ON
  episodes (per-frame `results_game_state.csv`) ≈ the ≈36 rallies. Only 14
  confirmed as points (`point_min_actions=2`): 17 episodes emitted 0-1
  actions; 15 episodes truncated <120f (a real rally here is 10-25s; the
  longest, ep34, is 769f/30s and got 7 actions). Episodes end when flight
  density starves — the ball track dies mid-rally. 74 actions total (dig
  37 / serve 13 / overpass 11 / spike 9 / set 4), 13 serves vs ≈39 rallies;
  6 of those serves fall OUTSIDE any confirmed point (their rallies
  unconfirmed). 8 confirmed points have NO serve inside — the confirmed
  segment is a mid-rally fragment, not the rally.
- **BALL RECALL IS THE BOTTLENECK: tracked 20.6% of all frames (4049
  flight frames at ≥8 px/f).** Within episodes 40-60% tracked for healthy
  rallies vs 5-35% for the truncated ones. Candidate mechanisms NOT yet
  separated (open point 20): venue detector recall (session-14 round-2
  already measured sand noise 2.2 det/frame), the 25.7fps tax on the 8 px/f
  flight/lock gates (open point 19), conservative identity gates. Note the
  action layer CANNOT be diagnosed before this is fixed — contacts without a
  tracked ball never reach the classifier.
- **PLAYERS — the roster held; identities hop.** `analyze_tracking.py` on
  the 26k-frame dump: distinct ids [1,2,3,4] only, 0 ghost/recycled id
  NUMBERS, max simultaneous 4, swap-rate 0.00, team accuracy 97.9%. In-play
  coverage 3.28/4 real players (detection recall 72.2%); dead-time
  persistence is GOOD (3.05/4 — tracks survive between rallies; ids present
  70-83% of dead frames). BUT 46 resurrections (13/5/13/15 per id) and a
  VISUALLY CONFIRMED mid-rally identity hop: `sheet_id3_cross_f1250-1350`
  (id2's box walks off the receiving woman onto the adjacent man during the
  serve scramble — both in-court, so the in-court preference cannot separate
  them; the woman ends untracked; id3 near→far in the same scramble).
  Per-episode all-4 side-mapping changes 12x — more than the ~5 official
  switches a 36-rally set should have — consistent with hops corrupting the
  mapping. The ~50 team flips per id are mostly dead-time wandering across
  the midcourt line + net-area jitter, NOT switches. The 21-15 score is NOT
  reconstructable at this recall (would need per-rally point winners).
- **Next (in order):** (a) ball-recall separation probe (open point 20):
  raw detector vs tracker gates on a few truncated episodes, px/frame
  histograms at 25.7fps; (b) GT pass with `annotate_player_gt.py` on a few
  points around an OFFICIAL side switch (5 expected) to measure hop rate and
  judge side-change survival; (c) only then re-tune whatever the probe
  indicts — one mechanism at a time.
**(2026-09-23, fourteenth session): NEW MATCH FOOTAGE INTAKE + SUB-1080P
INGEST UPSCALE.** `resources/full_videos/20260920_match_ari_joan_lost.mp4`
(1280x720, ~25.7fps effective, 26,061 frames, ~17min, points only, side
switches present, no GT yet) is the first real match — which unblocks open
point 2 (side-change survival) for the first time.

- **Diagnosis first:** 720p is NOT a detection problem — both YOLO detectors
  run a fixed imgsz=1280, so the network sees the ball at the same input
  scale as from 1080p (a 1080p frame is downscaled to 1280 anyway). What
  breaks is everything downstream in ORIGINAL-frame pixels: ~20 hardcoded px
  constants measured at 1080p shrink by 2/3. The killer list:
  `attribution_width_far_px`/`near_px` 26/35 (validated ball-width ranges
  14-28 far / 30-55 near become 9-19 / 20-37 — thresholds land INSIDE the
  near range, so the side signal, team attribution and the width-confirmed
  cross all break), `TOUCH_RISE_PX` 57 (measured boundary 50.5/64.5 → 34-43;
  everything reads hard), `NEAR_NET_PX` 120 (load-bearing, becomes ~180),
  and every px/px-per-frame gate (`DRIVE_MIN_PX`, `lock_min_speed`,
  `flight_speed_px`, tracker distances).
- **Shipped (`src/utils/video_upscale.py`, hooked in `src/main.py` before
  both batch and live-debug — parity rule respected; config
  `upscale_to_height: 1080`, 0 disables):** `ensure_1080` passes 1080p+
  sources through untouched (entreno baselines can't move); sub-1080p
  sources are transcoded ONCE (ffmpeg Lanczos, x264 CRF 18, `-vsync 0` so
  VFR input keeps every frame exactly once) to `<stem>_up1080.mp4` next to
  the original, written via atomic rename + decoded-frame-count parity gate
  (a cache file always implies complete+verified), and reused on every later
  run (0.01s resolve). Court-calibration auto-detect and output naming key
  on the SOURCE stem (`calibrations/20260920_match_ari_joan_lost.json`).
  Suite 379 green (+4 upscale tests).
- **Measured on the real file:** 1920x1080, 26,061 frames (count verified
  against the source decode), fps preserved 25.67, 6.5min one-time cost,
  1.4GB cache (mp4 is git-ignored).
- **Deferred (open point 19):** the source is ~25.7fps effective vs the
  30fps entreno tuning — frames-based windows span ~17% more wall-time and
  px/frame speeds shrink another ~14%. Not fixed on purpose (one mechanism
  per session); revisit only if contact-window misses show up. Also still
  owed for this video: court calibration (6 clicks), first full pipeline
  run, then the GT pass (`annotate_player_gt.py`) to unlock point 2's
  side-change scrub.
**(2026-09-19, thirteenth session): open point 15(e)'s label item is RESOLVED
— the resolver now owns a WIDTH-CONFIRMED CROSS and an own-side drive-block
refutation, both keyed on the ball's width side (the project's validated
side signal) instead of new constants. e7's f242 reads set A t2 (GT ✓, the
attribution tid 3 = GT P3A untouched) and e7 eval F1 0.625 → 0.75 / P 0.833
→ 1.0; e1-e6 action streams BYTE-IDENTICAL; suite 375 green.**

- **Diagnosis first (output/probe_e15e/, git-ignored):** the f242 mislabel
  decomposed into ONE starvation: B's f160 spike is unemittable (toucher
  untracked — attribution by design, GT agrees), so the wrap rule reset the
  possession one contact LATE — A's f195 reception read t3, f242 wrapped to
  t1, and the touch-1 block gate kept the drive-band hands-overhead read as
  a block. Measured shapes split the contested contacts cleanly: e1 f256 /
  e5 f298 (validated blocks/spike) are REDIRECT-band; e7 f242 / e6 f309 are
  drive-band; width-side evidence (ball_side, already threaded into every
  contact by team-aware attribution) commits A on e7 f242's own-side toucher
  and abstains at both jousts.
- **Shipped (src/recognition/action_context.py only):** (1) WIDTH-CONFIRMED
  CROSS — a non-attack touch that would be the 3rd+ of the latched
  possession, by the OTHER team, with ball_side == toucher team, flips the
  possession AT the crossing contact (the wrap rule with evidence, no longer
  one contact late). Gates measured against every regression candidate:
  would-be touch >= 3 (e2 f118's GT set keeps its t2 — its possession opener
  e2 f90 is structurally invisible; a would-be-2 team change is a missed
  reception or attribution wobble, not proof of a cross), positive width
  only (e5 f298's flip is refused — its over-set ball still reads the
  setter's regime — its GT t1 stays cosmetic), and never past attack/rally
  resets. (2) OWN-SIDE DRIVE-BLOCK REFUTATION — you cannot block your own
  side's ball: a drive-band BLOCK gesture with ball_side == team falls
  through to the touch-position rules (redirect-band blocks keep the block
  unconditionally — e1's joust emission; abstaining drive reads keep it
  too — e6 f309). Zero new constants, zero config.
- **GT semantics discovery:** the GT's touch_number counts per-TEAM
  possession (any cross restarts the receiver at t1) — proven by the GT's
  own e4 f329 spike t1 and e5 f300 spike t1 (each preceded by the OTHER
  team's set, not an attack). The width-confirmed cross implements exactly
  this; the old attack-based counting matched only because attacks are the
  usual cross.
- **Measured:** fresh HEAD baselines FIRST (output/e15e/base_actions, all 7,
determinism re-verified vs the p16 baselines), then the edit, then A/B:
  e1-e6 BYTE-IDENTICAL (incl. confidences); e7 differs in exactly two
  fields — f195 t3→t1 (GT ✓) and f242 block→set t1→t2 (GT ✓). Eval: e7
  F1 0.625→0.75, P 0.833→1.0, R 0.5→0.6, team 0.833 unchanged; e1-e6 all
  at their recorded baselines (0.706 / 0.571 / 1.0 / 1.0 / 1.0 / 0.933,
  teams 1.0). Production src.main e7: player_3 Set_Count 1 (was Block).
  Suite 375 green (+5: cross flip + width-gate + would-be-2 refusal +
  same-team refusal + redirect/abstain block preservation).
- **f316 team RESOLVED — the GT letter was the slip (owner ruling
  2026-09-19, folded):** off the sheet
  output/e15e/reratify_e7_f315_team.png the owner ruled the contact is on
  the FAR side, the P2B (yellow) player is far from it, P4 is really a
  NEAR-team player (its B-flapping stamps are the airborne spiker's feet),
  the blocker at the net is the far-side player, and the P1/P3 boxes
  overlap (occlusion — track 1's box bottom y=532 sits inside track 3's
  y-range) with P1 also very close to the ball. Toucher = track 1 = P1,
  team B — exactly the pipeline's emission (f316 dig tid 1 team B, never
  changed). GT f315 folded to P1B (+team_in_possession B) with the ruling
  as provenance; e7 eval after the fold: F1 0.75, P 1.0, team 1.0 (6/6).
- **Two follow-ups from the same ruling (flagged, not folded):** (a) GT
  f370 "set P4B" is now incoherent — the owner's mapping is near = {3,4},
  far = {1,2}, so B's f370 setter must be P1 or P2 (the far setter is P1,
  who set at f112); confirm the id at the next ratification pass (the
  event is unemitted/parked regardless). (b) Track 4's per-contact foot
  team flaps B while airborne at the net (y≈560-571 mid-jump vs ≈605+
  grounded) — same airborne-feet artifact class the takeoff-stance reads
  exist for; only matters if f300's spike ball ever gets tracked (point 1
  ball-recall), no code change today.
- **e2's f256 residual now explained:** its dig-vs-set miss needs a
  would-be-2 flip (possession opener f90 invisible) — deliberately refused
  (the same gate that protects e2 f118). Not worth chasing without the
  held-ball-release contact.
**(2026-09-09, twelfth session): the inverted poke rule is RETUNED — spike
type is now ASCENT-ONLY (TOUCH_RISE_PX 80 → 57) and the level-exit |vx|/|vy|
type rule is DELETED. Both ratified pairs score: e5 f298 touch / e6 f309
hard; e3 4/4; teams and every other emitted field byte-identical on all
seven videos.**

- **Diagnosis first (output/diag_poke_retune_features2.py, byte-copy of the
  GT-validated script loop):** the probe's decision-time view (per-frame
  rise above the EVENT contact_point, exit windows, close frames) showed the
  shipped rule inverted on its own evidence — e6's hard exits at |vx| 47
  (fired "poke") while e5's true poke exits at |vx| 18-22 (below the 25
  bar), and e5's arc tops out at 64.5 px above the contact point — under
  the old 80 px rainbow bar. Every ratified hard stays at/below the contact
  point through its whole decision window (e3 f431 −25, f539 −34 at its
  dig-close, e6 f310 −30). Ascent alone separates all three classes; vx
  added nothing but the false positive.
- **Boundary discovery (A/B caught it):** a first cut at 50 px flipped e1
  f371 (GT-untyped, incumbent hard) whose ball rises EXACTLY 50.5 px and
  floats level — a real boundary spike, not noise. The shipped threshold is
  the MIDPOINT of the two measured boundary rises: e5's poke 64.50 above,
  e1 f371 50.50 below → TOUCH_RISE_PX = 57 (6.5 px margin both sides).
- **Coupling owned (19b):** the classifier's `_is_poke_drive` team gate is
  UNTOUCHED byte-for-byte — it keys the AIRBORNE toucher for the
  takeoff-stance team read (e6 f309 team A preserved, production CSV
  `309,3,1,A,hard,A1,out`); only its comments now say what it is (the
  ratified e6 f310 is a hard whose toucher is airborne by construction).
  The type/team concern split is drift-guarded: the old constant-mirror
  tests are replaced by a guard asserting SpikeAnalyzer has NO POKE_EXIT_*
  and the classifier keeps its own 25/12.
- **Eval gap fixed (scripts/evaluate.py):** the scorer ignored the GT
  `overrides` block, so ratified corrections (e5/e6 spike_type) were
  invisible to eval — spike_type was simply unscored on e5/e6. GT events
  are now merged with their overrides before scoring; e3 4/4, e5 1/1,
  e6 1/1, teams 14/14 + 7/7 + 7/7; labels F1 e3 1.0 / e5 1.0 / e6 0.933
  (the e6 FN is the unemittable no-touch block) — all equal to the
  recorded baselines.
- **Measured:** suite 370 green (TestPokeType rewritten for the ratified
  physics: moderate slow arc = touch, e6 level exit = hard, narrow drive =
  hard; both mirror tests replaced). e1/e2/e3/e4/e7 action logs
  BYTE-IDENTICAL; e5/e6 differ in exactly one field each (the spike_type).
  Production src.main e5+e6 spikes CSVs confirm the script path.

**(2026-09-09, eleventh session): the poke GT RATIFIED — and the 09-08
dictation was misattributed: THE poke is e5's f300 spike (pid 2 B, now
spike_type touch); e6's joust contact is a HARD spike at f310 (1A) and the
no-touch 2B block sits at f314. Both GTs folded. The shipped poke machinery
measures INVERTED and is the owned retune (new open point 19). Labels and
teams are unaffected: e5 F1 1.0 / team 7/7, e6 F1 0.933 / team 7/7 (the only
FN is the unemittable no-touch block) — the fold costs exactly the two
spike_type pairs (e5 f298 emitted hard vs GT touch; e6 f309 emitted touch vs
GT hard).**

- **Ratification sheet (output/diag_e6_poke_ratify_sheet.py → .png,
  git-ignored):** dense f294-318 step-1 strip + 2x joust zoom, OpenCV
  stamps, detector candidates AND the tracked-ball trail drawn from a
  FrameProcessor-identical BallTracker reconstruction (its f310→f312 bridge
  matches the pipeline's exactly). The owner ruled off the sheet: poke =
  e5 f300; e6 = hard f310; no-touch block = f314.
- **GT folds:** e6 spike f308→f310 (raw drops 'poke', overrides
  spike_type 'hard', correction note), e6 block f308→f314 (note updated);
  e5 f300 spike gains raw 'poke' + spike_type 'touch' (frame/pid/team were
  already ratified); both description strings record the correction
  provenance.
- **Retune diagnosis (output/diag_poke_true_probe.py):** e5's true poke:
  descent vy ≈ +29 into f300, vertical reversal f300→f301 (+28 → −2), then
  ASCENDS 124 px by f315 with exit vx +20..+27, vy −20..−8 — a soft tip
  arcs to the back of the field. e6 f310 (pipeline-consistent history =
  the sheet run): exit vx −49, vy ≈ +1, dead LEVEL, no ascent. The
  analyzer's poke rule (no ascent + |vx| ≥ 25 + |vy| ≤ 12) fires on exactly
  the wrong one. CAVEAT: a late-bootstrap e6 tracker run (window from
  f280) locks the far-left corner and loses the ball — the f265-window
  reconstruction is the pipeline-consistent one; cite that for e6.
- **Survivors:** the resolver's block-at-touch-3 fall-through is
  gesture-vs-possession logic, poke-independent — e5's spike label stays
  correct. The stance-majority team rule is scoped to the level-exit
  signature e6 f309 still matches — team A stays correct today, but
  re-typing e6 hard without moving that scope regresses e6 team (point 19
  records the coupling).
- **Eval gotcha re-confirmed:** player-box agreement GATES label matching —
  e5 reads F1 0.857 without --ignore-player (6/7 player-spatial,
  pre-existing, GT boxes untouched by the fold); the recorded "labels F1"
  convention = --ignore-player.

**(2026-09-08, tenth session): [CORRECTED 2026-09-09 — the poke dictation
below belonged to e5 f300; e6's joust contact is a HARD spike at f310 and
the no-touch block sits at f314; see the eleventh-session entry and open
point 19. The e5 block→spike label heal and the e6 team-A outcome SURVIVE;
the poke-type rule and the "poke" reading of e6's level exit do not.]**
The e6 joust contact was read as a POKE — owner dictated "spike touch, not a
block" — and the whole read chain then agreed: the production path emits
spike (not the jittery block), team A (was B), spike_type touch (was hard).
e5's f298 block misread healed to spike as a
corollary (F1 0.857 → 1.0, point 15c closed); e1/e2/e3/e4/e7 byte-identical;
e6 team accuracy 0.857 → 1.0 (point 15b closed); suite 364 green (+9).**

- **Diagnosis first (probe over the REAL path, output/diag_poke_probe.py =
  byte-copy of the GT script + a _classify_type capture wrapper):** the raw
  ball flight is unambiguous — A's f262 set exits the frame top f278,
  re-enters descending f299 at x≈1300 over the jumping 1A, KINKS at the net
  plane at f311 (sighting gap), then floats flat-left ~45 px/f and dies deep
  near the far-left corner f342 (sheet output/diag_e6_poke_sheet.png). One
  contact after the set; the owner's "poke to the back of the field" = this
  kink. Measured over ALL GT spikes: the poke arrives descending (+29 px/f)
  and leaves LEVEL and strongly HORIZONTAL (vy_out +1.5, vx −47) with zero
  ascent — overlapping the two e3 hard spikes (f431/f539) on every vertical
  feature; the ONLY separator is the horizontal exit (poke |vx| 47 vs hard
  max 14). Critically, in the script path the contact fires via the DRIVE
  band (kind=drive: the post-rework tracker bridges the f311 gap to 2
  frames, so the reentry band never engages) — the ninth session's
  reentry-only team fix was aiming at a dead branch, and the team still read
  B off the airborne contact-time box.
- **Shipped (three mechanisms, each measured):** (1) *resolver poke rule*
  (src/recognition/action_context.py): a BLOCK gesture at touch 3 of a
  continuing possession is self-contradictory (a block is definitionally
  touch 1 after an attack) → falls through to the existing touch-3-at-net
  spike rule. This makes the owner's production MPS-jitter path (pose reads
  hands-overhead → BLOCK) structurally unable to emit block on the poke;
  touch 1 keeps block, touch 2 keeps block (e1's joust emission sits there;
  no cascade — spike and block both reset possession).
  (2) *analyzer poke type* (src/analysis/spike_analyzer.py POKE_EXIT_VX_PX
  25 / POKE_EXIT_VY_PX 12): no ascent + |mean exit vx| ≥ 25 + |exit vy| ≤ 12
  → "touch". Thresholds in the wide measured gap (poke 47 vs hard max 14);
  e3's types stay 4/4 (f431 vx 5, f539 vx 14 → hard), e6 f173 touch
  unchanged. (3) *poke-class stance team* (action_classifier.py
  _is_poke_drive + _takeoff_stance majority): for drive contacts with the
  SAME level-horizontal signature, the toucher is airborne by construction,
  so the emitted team reads the takeoff-stance window [c-12, c-2] by
  MAJORITY court team (nearest-to-contact had landed on f307, the first
  frame whose grounded foot drifted across the net line; f297-306 read A →
  majority A). Ties/uncalibrated → old nearest behavior. Classifier/analyzer
  constants equality is drift-pinned by test.
- **Measured (clean A/B, output/poke/post_actions vs the p16 HEAD
  baselines):** e1/e2/e3/e4/e7 BYTE-IDENTICAL (e1's touch-2 block and e7's
  touch-1 block preserved; e3 spike types 4/4 unchanged). e5 f298 block →
  spike (team B unchanged, touch 3): labels F1 0.857 → **1.0** — point 15(c)
  closed. e6 f309: team B → **A**, spike_type hard → **touch**, label spike
  unchanged; eval F1 0.933 (the FN is still the GT's no-touch 2B block,
  unemittable), team **0.857 → 1.0** — point 15(b) closed. Production
  src.main rerun on e6: spikes CSV row `309,3,1,A,touch,A1,out` and the
  emitted action reads spike/team A even when that run's gesture read block
  — the owner's exact complaint path is closed.
- **GT fold (owner-dictated, sheet output/diag_e6_poke_sheet.png):** the f308
  spike event carries spike_type "touch" + raw "poke" + an overrides note;
  OPEN QUESTION for the next ratification pass: the owner counted the poke
  at f298, the sheet-measured contact (trajectory kink at the net plane) is
  f311 OpenCV-indexed, the pipeline emits f309, GT sits at f308 — all four
  within eval tolerance of each other, but the offset should be confirmed
  once. The GT's no-touch 2B block event was NOT touched (owner-ratified
  twice as physical); confirm whether "not a block" also revokes it.
- **Suite 364 green** (+9: resolver block-at-touch-3 fall-through + touch
  1/2 preservation; analyzer poke-touch + narrow-exit-stays-hard + constants
  parity; classifier poke gate + NEIGH normalization, stance majority beats
  landing drift, tie fallback, and the full e6-shape drive→spike/team-A e2e).
- **Same session, later: e7 GT RATIFIED (point 15f closed).** Owner
  corrected against the OpenCV-stamped sheets: f55→f61 (digger untracked —
  their screenshot), f110→f112 P1B, f160 confirmed (rainbow touch, toucher
  untracked until f166), f200→f197 P2A, f244→f243 P3A, f300 confirmed P4A
  hard + no-touch B block ADDED (10 events), f330→f315 team B→A (P1A),
  f360→f370 P4B; player ids = per-video track ids where named. The current
  stream vs the ratified GT: f59/f112/f195/f239/f316 emitted — frame F1
  0.533 (P 0.8, R 0.4); f239 is the f243 set misread as block, f316 has the
  wrong team (B vs P1A), f25/f160/f243/f300/f370 die at classifier gates.
  That is the concrete target list for the 15(a)/(e) retune.
- **Same session, end: the ratified-e7 retune SHIPPED (points 15a + 15d
  closed, 15e partly).** Gate-probe diagnosis (output/diag_e7_gates.py) on
  the real path reframed the misses: f160 IS detected (bounce@162) and dies
  at the reach gate because the rainbow toucher is UNTRACKED (attribution
  by design — GT says so); f300's ball was NEVER tracked there (only stray
  far-left junk points — a ball-recall gap, tracker-side, not classifier);
  f370's set sits in a 6f sighting gap and re-appears already descending
  toward the teammate (no ascent-out — the bridge signature is absent;
  parked); f25's serve toss flows THROUGH the hit (ascent into ascent — no
  band applies) and f243's set was stolen by a FALSE redirect vertex at
  f239 whose flip evidence lived 6f ahead. Shipped: (1) *rally-opening
  serve gate* — inside the drive test, a pop-up whose incoming ±3f slope
  beats the preceding ±6f slope by SERVE_ACCEL_MARGIN_PX=10 (gravity can
  only decay an ascent) fires before ANY contact; measured openings: e7
  f25 vin3 −42 vs vin6 −13 fires, e4's pure gravity arc (25→1 px/f
  decelerating) refuses everywhere, e2's slow arc and e1's fed descent
  never qualify; plus a serve-scoped reach (SERVE_REACH_PX=160 — the
  toss-apex arm extension measured 147.5 vs the 140 dig/spike reach;
  scoped to the rally-opening drive so e2 f167's deliberate 4px refusal
  is untouched); the resolver's behind-baseline + rally-start rule labels
  it. (2) *redirect locality* — the horizontal-flip test must pass in the
  vertex's own ±3f window; a flip measured only over the full NEIGH window
  is a neighbor contact's impulse leaking in; locality-unprovable (<2
  points in ±3f) falls through. Measured A/B (stash-regenerated HEAD
  baselines): e6 byte-identical; e7 +f25 serve A (EXACT vs GT — F1 0.533
  → 0.625, team 0.8 → 0.833) and the false f239 vertex is gone (the real
  set contact now fires at f242 via the drive band — 1f from GT f243 —
  still labeled block pending the upstream cascade fix); e2's f81 FP is
  KILLED and f118 now reads set (GT ✓) — F1 0.533 → 0.571 (15d closed;
  the cascade shift moves f256's set to read dig — CSV-context, labels
  net-positive); e1's joust block re-attributed to B (GT's spike side —
  team 0.875 → 1.0) with a 1f vertex shift; e3/e4/e5 1-frame vertex
  shifts toward GT (e5 f248 now exact), F1 1.0 unchanged; production
  src.main e7 confirms the identical f25-serve stream. Suite 370 green
  (+6: fed-ascent fires / gravity-arc refuses / rally-start required /
  redirect locality refuses+fals-through / local redirect fires /
  serve-reach e2e).
- **Same session, later: e7 GT RATIFIED (point 15f closed).** Owner
  corrected against the OpenCV-stamped sheets: f55→f61 (digger untracked —
  their screenshot), f110→f112 P1B, f160 confirmed (rainbow touch, toucher
  untracked until f166), f200→f197 P2A, f244→f243 P3A, f300 confirmed P4A
  hard + no-touch B block ADDED (10 events), f330→f315 team B→A (P1A),
  f360→f370 P4B; player ids = per-video track ids where named. The current
  stream vs the ratified GT: f59/f112/f195/f239/f316 emitted — frame F1
  0.533 (P 0.8, R 0.4); f239 is the f243 set misread as block, f316 has the
  wrong team (B vs P1A), f25/f160/f243/f300/f370 die at classifier gates.
  That is the concrete target list for the 15(a)/(e) retune.

**(2026-09-06, ninth session): OPEN POINT 16 FIXED — identity is anchored in
court: an out-of-court detection may still CONTINUE a track (grace/hold rules
untouched) but now loses the assignment to any in-court detection within the
gate (off_court_cost_penalty_px = 300). e6's far-left digger is tracked from
f146 to the end under his original id 3, and the f311 chain-swap (P1 onto the
right-edge bystander, team flip A→B) is gone. e1/e3/e5/e7 tracks byte-
identical; e2/e4 diffs are the same mechanism firing benignly (e4 now follows
GT id4 back INTO court at f390); all action streams identical except e6's
f309 player index (4→3).**

- **Diagnosis (owner style — probe first, then eyes):** dumped every raw
  detection + assignment decision + per-track state for e6 (output/
  diag_e6_walker.py) and LOOKED at the frames. The owner's report decomposed
  into ONE mechanism with four symptoms: a detection BLIP of the tracked
  player (1 frame) lets a walkway bystander behind the far baseline take the
  track through the CONTINUOUS-observation branch of _may_feed_track — a
  105-149 px single-frame jump reads as "no observation gap". Smoking gun
  f142: track 3 (the digger) fed at [816,462] in-court at f141; f142 the
  digger's detection blips, a walker at [866,370] grabs the track; the track
  follows the walkway right (f142-188), coasts frozen at [1010,373] f190-243
  — and the digger, detected IN COURT every frame from f146, is never
  re-acquired (215 px from the drifted ghost): untracked f142→end. Same
  class on track 2 (f214/f244/f256 squats, each seeded by a blip); the
  squats then CASCADE into Hungarian CHAIN-SWAPS (a full matching with long
  jumps costs less than leaving a track unmatched at the 1e6 sentinel):
  f305 track2↔track3 rotate onto each other's persons, f311 P1 jumps to the
  right-edge bystander [1433,374] at 149.5 px (just inside max_distance=150)
  and P2/P3 take the abandoned players — the team vote fills B by f314.
- **Measured rejection of gate-style fixes:** per-frame jump px (legit
  out-of-court feedings on e1-e5 reach 146.6 px; e6 hijacks start at 105),
  world-metre displacement (17-25 m "jumps" on LEGIT feedings — the known
  airborne-foot projection artifact), and signature similarity (legit 0.17-
  0.53 vs hijack 0.26-0.69) ALL overlap. No per-frame signal separates
  "same person moving fast" from "different person nearby" → the fix is a
  PREFERENCE, not a gate: in the Hungarian cost, out-of-court detections
  carry +300 px-equivalent (below the 1e6 invalid sentinel, so an off-court
  chain still beats leaving a track unmatched; uncalibrated courts
  unaffected; 0 disables). Allowance rules (_may_feed_track grace/hold/
  serve-zone) are UNTOUCHED — e2's hold-horizon bystander and e7's straddler
  cases keep their mechanisms.
- **Shipped (src/tracking/player_tracker.py + config player_off_court_cost_
  penalty_px, drift-guarded, wired through FrameProcessor + dump_player_
  tracks):** the penalty lives in _compute_assignment_cost — it reorders
  candidate preference within a track's row; e6 f146 recovery is exactly the
  intended shape (walker at 3 px + penalty vs digger in-court at 113 px →
  digger wins back the track after a 4-frame squat).
- **Measured (clean-room A/B, dump_player_tracks all 7, baselines completed
  BEFORE any edit):** e1/e3/e5/e7 BYTE-IDENTICAL. e2: 3 frames (f377-383, a
  track fed off-court at y≈364 now fed in-court; all metrics identical,
  actions identical). e4: 15 frames (f379-397) — same class and a fix: GT
  id4 stands behind the baseline at f380 ([948,396], BASE matches), walks
  back in by f390 (GT [933,456] — POST follows at [936,459]; BASE was
  stolen at f384 and parked 107 px off GT); every analyze_tracking metric
  identical (87.2% recall, 93.1% coverage, team 98.9%). e6: 198 frames
  (f118-342) — digger tracked from f146 (BASE: f142→end), P3 stays the
  digger, P2 the blue/red player, P1 grey/pink team A through the joust;
  end state f340 = P1A/P2B/P3B-digger/P4A (BASE: P1B on the bystander).
- **Actions (test_action_recognition, all 7):** e1/e2/e3/e4/e5/e7 streams
  IDENTICAL. e6: 7/7 events identical (frames/labels/teams/touch numbers),
  f309 player_id 4→3 (the candidate set at the manufactured contact is now
  the real players). e6 eval unchanged: F1 0.933, team 0.857 (6/7).
  Production src.main e6 emits the identical 7-event post-fix stream.
- **15b re-check (the point-16 entanglement, resolved as far as the tracker
  goes):** the f309 team still reads B vs GT 1A — but the cause is now
  isolated to the CLASSIFIER's stance-window snapshot rule, not tracker
  contamination: the reentry band's takeoff stance takes the snapshot
  nearest the contact inside [c-12, c-2]; under the clean tracks that is
  f307, the FIRST frame whose grounded foot crosses the net ground line
  (foot y 618→607 between f306/f307) and reads B — f297-306 all read A.
  Next session's classifier retune (point 15 protocol, sheets first): prefer
  the window-majority or last-clearly-grounded-A read over the single
  nearest snapshot.
- **Suite 355 green** (+7 tests/test_bystander_guard.py TestInCourtPreference:
  cost-unit preference, update-level pick, f146 recovery shape, continuity-
  without-alternative preserved, penalty=0 restore, uncalibrated no-op,
  chain-swap still prefers full matching; +1 config-drift row). Owner
  evidence sheets: output/p16_sheet_{grab_f115-152,mid_f240-260,joust_
  f295-320,end_f326-342}.png (BASE | POST side-by-side).

**(2026-09-06, eighth session): squatter review SHIPPED — a track whose
lifetime in-court FEEDING fraction stays below 0.35 once it is 120 frames old
is expired as a sideline straddler: flagged in the gallery (id preserved as a
fail-safe, every restore path blocked, immediately evictable), its sampled
foot positions blocking re-admission nearby. e2's freed slot is taken by a
real player at f127 (was ~f188), e7's at f166 (was f262); e1/e3/e4/e5/e6
byte-identical; action streams event-identical on e2/e7.**

- **Diagnosis recap (session plan v2, owner-ratified):** the e7-class
  bystander seeds a track while STRADDLING the sideline and reads "in court"
  for a dense early run (f47-79 at 7.87-7.99 m), so strict admission cannot
  refuse the seed. Narrative correction folded: the off-court hold horizon
  DOES fire (~f172 on e7, last in-court f82 + 90) — the 2026-08-29 story
  understated it — but the track then coasts as a ghost for max_disappeared
  (90f) and the gallery re-acquires the id onto whoever stands near the old
  position: measured on the clean-HEAD dump, the real 4th player colonizes
  id4 at f262-263 (position restore on the coasted box). So the slot is only
  truly usable from f262 — the reset/re-acquire loophole stretched the squat.
- **Shipped (src/tracking/player_tracker.py):** per-track counters
  `fed_frames` / `in_court_fed_frames` incremented ONLY in `_update_track`
  (ghost/coast frames never dilute the fraction; bootstrap seeds start at 0);
  `_expire_squatters()` beside `_expire_serve_zone_trials()` — fire when age
  ≥ 120 AND fed ≥ 20 AND in_court_fed/fed < 0.35 (lifetime fraction, not
  rolling; occluded real players keep theirs frozen at 100%); expiry is to
  the GALLERY with `squatter: True` — NOT hard-remove (hard-remove stays
  reserved for never-in-court seeds, e5 precedent). Flag interlocks: both
  gallery restore passes skip flagged entries; flagged entries bypass
  gallery_evict_min_hold_frames and are preferred by `_evict_stalest_dormant`
  (the real 4th player gets the slot the same frame); `_restore_track`
  reloads counters + created_frame (no fresh review amnesty after a legit
  restore). Cooldown: world foot sampled every 10th fed frame (maxlen 12 ≈
  the review window); at expiry the samples go on `_squatter_cooldown` and
  `_track_admission_ok` refuses new tracks within 0.5 m of any sample —
  including in-court candidates (re-admission attempts read 7.84-7.99 m);
  existing tracks are never affected. Uncalibrated court → no-op.
  Config: `player_squatter_enabled/review_frames/min_fed_frames/
  min_in_court_frac/cooldown_radius_m` (drift-guarded); wired through
  FrameProcessor + dump_player_tracks (bare ctor sites inherit parity).
- **Measured (clean-room A/B, dump_player_tracks all 7 videos):** e1/e3/e4/
  e5/e6 byte-identical (e6 watched for the 46f-streak track — no diff). e2:
  127 frames differ, f127-253 — id2 passes from the coasting bystander ghost
  to a real in-court player at f127; analyze_tracking: ID2 missing 60 → 0
  frames, its resurrection gone, tracked coverage 71.4% → 80.0%, drop rate
  85.5% → 69.0%. e7: 106 frames differ, f166-283 — id4 is the real 4th
  player from f166, zero real emissions in the bystander region (x>1500)
  after it, runs re-converge at f284; coverage 83.7% → 89.5%, drop rate
  56.3% → 38.2%. Action streams (test_action_recognition): e2 and e7
  EVENT-IDENTICAL (same frames/labels/teams/track_ids/touch numbers); eval
  vs GT unchanged (e2 F1 0.533 = its current baseline — the plan's 0.571 bar
  predates the 7th-session ball-matching shift, see that entry; e7 4/9 →
  4/9, direction check only, no tuning); teams 1.0 everywhere.
- **Process gotcha (recorded the hard way):** NEVER generate A/B baselines
  while editing the code — each dump process imports at start, so my first
  e5/e6/e7 "baselines" ran partially-edited code and the A/B falsely read
  e7-neutral; a second race compared e7 while the post file was still being
  written. Protocol: edit NOTHING until the baseline run prints ALL_DONE,
  then edit, then post-run, then compare (git stash → run → pop for HEAD
  baselines).
- **Suite 347 green** (+17 tests/test_squatter_review.py: tick/floor/real-
  player/server-path/ghost-no-dilute/uncalibrated/disable-flag, both restore-
  pass skips, immediate eviction + preference over protected entries, counter
  reload on legit restore, cooldown blocks-in-court/admits-far/never-touches-
  existing, bootstrap seed counters + created_frame at lock; +5 config-drift
  rows).

**(2026-09-06, seventh session): ball-matching rework shipped — the tracker now
owns ball identity via trajectory + motion, never confidence alone. The e6
serve is tracked for the first time (f34, production path confirmed), e7's
f110 set is newly detected, and static spares can no longer bootstrap, steal,
or starve the track. e1/e3/e4 action streams are byte-identical to HEAD.**
Owner report: most missed actions trace to tracking the WRONG ball — e6's
serve lost to a bottom-right spare ball, e7's rally events lost to rack/
drill balls ("in volley practices it is bound there will be a lot of balls,
but also in tournaments").

- **Diagnosis first (output/diag_ball_match*.py, git-ignored, raw-detection
  dumps + tracker-decision traces over e6/e7 full videos):** four failure
  mechanisms, all confidence-driven: (1) bootstrap locks the highest-conf
  first detection — in practice videos that is a foreground spare (e6 f0
  locks the bottom-right ball; the serve toss is then rejected by the
  trajectory gate for 70 frames); (2) the detector's top-1 confidence cull
  HIDES the real ball whenever a spare out-scores it (e7 f241-244: a static
  rack ball at 0.90 starves the f244 set whose real ball reads 0.79-0.88);
  (3) after a reset the tracker re-locks the next top-1 blindly (e6 f17
  re-locks the same spare; e7 f245 re-locks the rack ball); (4) the growing
  coast gate admits slow-moving distractor balls when fed all candidates
  (e1 f77: a far-side drill ball 21px from the prediction — not rejectable
  by any local rule; only the old cull protected against it).
- **Shipped (src/tracking/ball_tracker.py selection rework +
  src/detection/ball_detector.py cull removal + suspect flag):** (a) the
  detector returns all surviving candidates, each tagged
  `stationary_suspect` at persist >= 0.30 of the rolling window (full
  removal still happens at 0.55 — player-side `ball_position` = max-conf
  over the same list, so the validated player-side behavior is untouched);
  (b) UNLOCKED bootstrap/re-lock requires demonstrated motion (>= 8 px/f
  over a pair <= 2 frames apart — detection-sparse spares show apparent
  speed across gaps and must not qualify): the e6/e7 serve toss locks
  within 1-2 frames of appearing; (c) LOCKED admission keeps the old
  GT-validated rule (top-confidence candidate inside the growing gate
  around the last position) with ONE divergence: a `stationary_suspect`
  top candidate that fails the gate cannot starve the track — the best
  in-gate plausible candidate is taken instead (recovers e7's f244 set); a
  MOVING top candidate that merely left the gate is trusted and the track
  coasts exactly as before (protects e1 f82's grown-gate recovery);
  (d) when the coast prediction leaves court bounds (ball provably out of
  view, e.g. a lob over the camera), a re-entry window holds the track near
  the exit point for 2x max_missing instead of resetting (recovers e6's
  f262 set across the f225-236 out-of-frame lob).
- **Measured (scripts/test_action_recognition.py = the GT-validated path,
  7 videos, before/after):** e1/e3/e4 action streams BYTE-IDENTICAL; e3
  1.0/1.0, e4 1.0/1.0 unchanged; e2 0.571 -> 0.533 (+f81 set FP near the
  held-ball release; f118 overpass->spike label; f209->f204 is CLOSER to GT
  f206); e5 1.0 -> 0.857 (f299 spike -> f298 block: frame closer to GT f300,
  label flipped); e6 — see below; e7 (new dictated GT, see below) 4/9
  matched both before and after but the COMPOSITION improved: set f110 now
  detected (dist 2), serve f25 now missed (the toss rise is 2.6 px/f —
  deliberately below the motion-lock floor), f160/f244/f300 remain
  undetected. Production `src.main` on e6 emits the same 7 events incl. the
  serve (f309 label reads block vs the script's spike under MPS jitter —
  the known device caveat, script path is the reference).
- **e6 ratifications (owner, sheets e6_ballmatch_*.png) + eval after the
  fold:** (a) the new serve is REAL — "e6 serve is from 4A" (the teal
  near-left player); folded into GT as f34 p4 A t1 -> e6 F1 0.857 -> 0.933
  (P 1.0, R 0.875; the only FN is the no-touch block, unemittable by
  design) vs before-rework 0.857 — e6 is a net win; (b) joust GT
  re-confirmed: spike 1A + no-touch block 2B at f308 (the sheet shows 1A
  airborne at the net on A's f262 set arc; 2B never plays the ball).
- **NEW owner finding — e6 player-tracking bug (open point 16):** track 2B
  latches onto a bystander passing behind the far court, the REAL far-left
  digger (blue/yellow/black, dig stance) is never tracked, and track 1A
  flips to the right-edge bystander across f310-312 (team flips A->B with
  it). Probe dump (f285-322): the 2B box sits parked at ~(1179,367) — the
  walker — from f286, oscillates with the real net player f306-310, and
  track 1 jumps [1322,474] -> [1434,374] at f312 (right-edge bystander),
  re-teaming to 1B by f314. Pre-existing (owner first saw the f311 swap on
  2026-08-28), now prioritized — see open point 16.
- **e7 GT folded (owner-dictated this session, pending ratification):**
  ground_truth/video_entreno_7_annotations.json — 9 events (serve A f25,
  dig B f55, set B f110, spike touch B f160 "rainbow on line", dig A f200,
  set A f244, spike hard A f300 with block, dig B f330, set B f360 slipped
  point ends). No player ids/boxes yet; evaluate with --ignore-player.
- **Suite 325 green** (+13: ball-matching behaviors distilled from the e6/e7
  failures — static-spare bootstrap refusal, toss lock, suspect override,
  moving-top-1 trust, re-lock-needs-motion, contact reversal in gate,
  out-of-view re-entry + expiry; +1 detector suspect-frac drift row).
  Known follow-up class (new open point 15): the classifier's contact gates
  are calibrated to the OLD tracker's histories; the shifted histories move
  individual labels/frames (e2 f81/f118, e5 f298, e6 f309 team, e7 serve
  left-window thin at 2 points) — retune with contact sheets next session,
  NOT by weakening the tracker rules.

**(2026-09-05, round 3): live GAME-ON badge latency FIXED — e3 serve at f30,
badge ON f136 → f53 — and the badge got a black plate on its own line below
the CALIBRATED sign.** Owner report: in live-debug the serve happens at f30
and GAME ON appears at ~f140; asked to fix it, check whether it is
livedebug-only, put a black background on the badge, and stop it
overprinting the "Court: CALIBRATED" text (screenshot showed GAME OFF on
top of CALIBRATED).

- **Not a livedebug bug (verified, not assumed):** the badge state is
  snapshotted per frame (``frame_result["game_state"]``) in BOTH render
  paths — buffered live and two-pass save — so the badge travels with its
  frame; the 3 s display delay shifts when a frame is shown, never what
  state is drawn on it. The machine itself was late. Proven by rendering
  the annotated e3 video (same ``_render_frame``): badge flips exactly at
  the machine's provisional frame.
- **Not ball-tracking recall either (open point 14c's old explanation was
  WRONG):** the production-path dump (output/diag_gs_live_latency.py,
  git-ignored) shows the serve flight tracked from f27 through the hit at
  f31 (55.9 px/f) to the f76 reception. Root cause: the toss produces ONE
  flight frame at f20 (11 px/f) which resets ``_no_flight_run``, so the
  burst starting f27 captures ``_burst_quiet = 6 < arm_quiet_frames(10)``
  and can NEVER arm — the entire 65-flight-frame serve+reception flight
  armed nothing; the badge waited for the NEXT contact's burst (the set,
  f107) + 20 flights → f136.
- **Shipped: rolling sustained-flight provisional** (new config
  ``fast_confirm_window_frames`` = 90, drift-locked): the live state shows
  GAME_ON ~ once ≥ ``fast_confirm_flights`` (20) flight frames fall in the
  rolling 90f window — no candidate required. Badge/CSV state only; the
  candidate confirm (episode/point layers) is untouched, so segmentation
  is unaffected by construction. e3: badge ON f53 (0.7 s after the serve
  hit, during the serve flight itself).
- **Measured cost (display-only, game-state video):** GT-OFF windows now
  show the provisional badge 2173 frames (72 s) vs 1832 (61 s) under the
  old candidate-only rule — any sustained practice exchange lights it by
  design; on match footage game-off means a dead ball, so no sustained
  flight. Points/actions byte-identical either way.
- **Badge rendering:** solid black plate (cv2.rectangle fill) with the
  colored text on top, moved to its own line (baseline y=62) below
  CALIBRATED (baseline y=30); locked by tests/test_overlay_game_state.py
  (plate pure black, plate top below CALIBRATED's ink, state tints).
- **Validated:** suite **305 green** (+2 toss-regression/retraction tests
  + overlay tests, timings updated for the earlier window ON); e3 batch
  A/B actions/spikes/points **byte-identical**; game-state video e2e
  points + actions **byte-identical**, eval **11/13, 0 false, 80.6%**
  unchanged.

**(2026-09-05, sixth session): game on/off state machine SHIPPED and GT-validated
end-to-end on `video_entreno_game_state.mp4`: 11/13 points one-to-one matched,
0 false, 0 merged, 79.0% frame accuracy (scripts/evaluate_game_state.py).**
Owner context (ratified this session): the video is the SAME footage/court as
video_entreno_* (e1's calibration reused, frame-diff verified), GT boundaries
are ±1 s, it is PRACTICE — **some points start from a coach-fed ball, not a
serve** (why the machine deliberately arms on any flight burst after quiet,
not on a serve signature), and a real match is expected to be EASIER (cleaner
serve→rally→death, no between-point practice volleying).

Diagnosis first (output/diag_gs_*.py, git-ignored, over a full 8167-frame
signal dump through the REAL FrameProcessor):

- **The legacy GameStateManager + 4 analyzer modules + ScoreTracker were
  broken/dead** (open point 13's "score machinery"): confidence-voting code
  that locks GAME_ON once and never turns off (53.3% frame agreement =
  chance). DELETED (action_sequence/trajectory_state/temporal_activity
  analyzers + score_tracker; archive/code/debug_action_sequence.py is the only
  reference and is staged for deletion anyway).
- **Ball motion alone CANNOT separate points from practice on this footage**:
  the OFF windows contain real volleyball exchanges (2-2 formations, serve-like
  bursts, 10s-scale flight budgets, 5-14 net crossings in off09/off10 — NOTE
  the net ground line is roughly HORIZONTAL at y≈600 in this long-axis camera)
  that overlap GT rallies on every per-frame signal family tried: speed
  distributions, flight budgets at every window size, net crossings (x- and
  y-based), onset context, team composition, formation spread, player motion
  energy, quiet-gap horizons AND flight-density windows. What separates:
  GT start = point start (serve OR coach feed — a flight burst at the GT frame,
  preceded by quiet), GT stop = ball death, and after a REAL point activity
  SUSTAINS with CONTACTS recurring (≤215f in-rally gaps), while between-point
  practice produces long contact silences.
- **Shipped machine** (src/analysis/game_state_manager.py rewrite + game_state.py
  dataclasses): three layers, pure observers of ball-tracker velocity + the
  emitted action stream. *Episode layer (causal):* flight = tracked & ≥8px/f;
  a burst of ≥8 flight frames after ≥10f quiet arms a candidate; confirmed
  GAME_ON (backdated) iff ≥20 flight frames land within 90f — isolated
  practice bursts reject; ON persists while the rolling 90f window holds ≥20
  flights and ends on density starvation or 40f tracked-static (held ball).
  *Group layer:* episodes within 60f merge into rally groups. *Point layer:*
  each group SPLITS at contact silences >240f (two rallies swallowed by one
  ball episode separate there — practice volleying keeps the ball flying but
  produces no contacts); a piece is a POINT iff ≥2 actions occurred in it.
  Params live in DEFAULT_CONFIG["game_state_detection"]; grid optimum flat.
- **Wiring:** FrameProcessor steps the machine ONCE per frame after actions
  (old code double-stepped); flush_actions() feeds flushed contacts + finish()
  (trailing group closes at last flight +1). Group finalization waits 450f —
  measured classifier emission lags reach 399f (median 60; the lookahead
  chains), so counting is by CONTACT frame at finalize, not arrival.
  frame_result["game_state"] carries the per-frame dict; results["game_state"]
  ["points"] the final segments; pipeline_output.json gains game_state.points
  + per-action point_index (-1 = outside any point — the owner's action
  gating key; on this video 77/83 actions land inside points);
  <stem>_game_state.csv rewritten (per-frame state + Point_Index); live-debug
  draws a GAME ON/OFF + point-count badge (overlay.draw_game_state); DB gains
  a points table + actions.point_index (idempotent ALTER-TABLE migration;
  ingest verified on the real DB).
- **Measured (end-to-end + offline replay agree exactly):** 11/13 matched,
  0 false, 0 merged; 7/11 starts within ±1 s (the −5 s ones absorb practice
  lead-ins that chain into the point's contacts); stops mostly ±1-4 s
  (trailing practice). Misses are action-recall-limited, not machine logic:
  pt00 = coach-fed point with ONE detected contact (370) — unrecoverable
  under ≥2-actions; pt03 = pt02's last spike fires 43f AFTER the GT stop and
  chains pt03's contacts into pt02's group (41% coverage, just under the 50%
  match bar). Suite **296 green** (+18 tests/test_game_state.py).
- **Serve-init semantics added (owner round 2, same session):** the owner
  tested live-debug on entreno_3 (point starts f30, GAME ON only at f174)
  and asked for serve detection as the game's init, noting (a) a far-side
  pass during game-off should NOT turn the game on, (b) the coach-fed
  points (0:21 / 1:02) are forgettable, (c) all serves in this practice
  are from the NEAR field, (d) real matches should be easier. Diagnosis
  (output/diag_gs_serve.py + probes): NO per-event serve discriminator
  exists in this ball-track data — burst-start WIDTH fails (the tracker
  picks up the serve at the TOSS, mid-air, far-regime 23-30px, same as
  far passes); static-held-ball precedes only 6/13 serves (and 31/90
  practice bursts — practice servers hold balls too); near→tape→far
  crossings fire on 17 OFF bursts. Shipped instead: **provisional fast
  ON** (live GAME ON once a candidate holds ≥20 flight frames —
  0.9-2.4s after the serve, dimmed "GAME ON ~" badge; points still wait
  for the validated 90f confirm, segmentation byte-identical), **serve
  actions arm instantly** (classifier serve = strongest point-start
  signal; only contacts ≤45f old, emission lags reach ~400f), and a
  trailing-group finish fix (stray tail flights no longer extend a closed
  episode — pt12 stop +6.2s → −1.9s). e2e re-validated: 11/13, 0 false,
  80.6% frame accuracy; e3 A/B byte-identical AGAIN (14/14); e3 live ON
  f174→f136 (the rest of the gap to f30 is serve-flight tracking recall,
  not machine latency). Known cost: a sustained far-side pass during
  game-off shows a brief provisional GAME ON (the point layer still
  rejects it) — no signal separates it on this footage; revisit with
  match footage where serves are the only net entries.
- **A/B neutrality PROVEN (twice):** e3 re-runs on the new code = action
  stream and spikes **byte-identical** to the 2026-09-04 baseline (14/14
  actions); the machine is a pure observer and the entreno GT numbers are
  unaffected.
- **Gotcha (new instance of the eval-vs-pipeline skew class): the first
  diagnostic dump silently ran with the COCO yolov8n ball-model fallback**
  (`DEFAULT_CONFIG["ball_model_path"] = None`) while `src.main` auto-loads
  `models/volleyball_ball_best.pt` — different detector → different ball
  track → different action stream (67 vs 83 actions; pt00 had ZERO actions
  under COCO, 1 under the fine-tuned model). diag_gs_dump.py now mirrors
  src.main's auto-detection + records `ball_model` provenance
  (gs_signals_coco_fallback.json kept for reference). Params tuned on the
  production path; the stack re-verified deterministic run-to-run.

**(2026-09-05, later session): player court heatmap rotated to landscape +
the "no hotspots" report diagnosed as stale server/browser cache** (owner
report: court "way too big", "does not show where attacks land and where do
they start from", wants numbers too). Diagnosis first: the data was present
(Jesus: `court_attack {1:1, 2:1}`, `court_landing {5:2}`), `_court_blobs`
emitted correct blobs, and a headless-Chrome screenshot of HEAD's served page
showed blobs + counts at the 340px cap — the owner's view was a STALE `make
ui` process plus a cached pre-session style.css (their screenshot lacks even
the CSS-styled white count text, and the court overflows the max-width).
Shipped so that class of failure cannot recur: (a) the court is now
LANDSCAPE — 160x80 viewBox (1 unit = 10 cm), net VERTICAL at x=80, player's
own half LEFT ("ATTACKS FROM"), opponent half RIGHT ("LANDS"), i.e. the old
portrait drawing rotated 90° clockwise so world_point_to_zone's digit
semantics are unchanged (zone 1 attack = net-adjacent bottom column; halves
mirror across net x=80 and mid y=40); sized down to max-width 560px;
(b) hotspot count numbers + half labels carry INLINE fill/stroke attributes
in the SVG, so they render even with no/any stale stylesheet (verified with
the stylesheet stripped from the served HTML); (c) the stylesheet link is
now cache-busted by file mtime (`/static/style.css?v=…` global set in
app.py). Tests: +9 (tests/test_web_court.py — zone 1/9 anchors both halves,
180°-symmetry mirror, intensity normalization, outcome-detail title,
well-formed landscape SVG render with inline-filled numbers, no-attacks
branch). Suite **278 green**. NOTE for the owner: restart `make ui` and
hard-refresh once — the running server predates the fix.

**(2026-09-05, fifth session): player page court FIELD heatmap shipped**
(owner request, two rounds): round 1 replaced the count bars/matrix with a
cell-grid court — the owner rejected it ("I want a visual representation of
the field"), round 2 rebuilt it as a drawn SVG overhead court: 8m x 16m
field with sand tint, boundary, net band + posts, faint 3x3 zone grid per
half, and SMOOTH radial-gradient heat hotspots (blurred circles at zone
centers) — orange = takeoff zones on the BOTTOM half (where the player
attacks from), blue = landings on the TOP half (kill/out → landing_zone,
dug → dug_zone); intensity/opacity scales to each half's max, small count
labels sit on hotspots with native title tooltips (kill/out/dug split for
landings). Data side (round 1, unchanged): `player_metrics` gains
`court_attack` / `court_landing` / `court_landing_outcomes` keyed by zone
DIGIT 1-9 (team letter stripped — the 9-zone grid is 180°-symmetric so the
digit is side-independent); geometry (`_court_blobs` in app.py) follows the
camera-view layout (landing half net row 1-2-3 left-to-right, attack half
3-2-1). CSS-only, still zero JS. The joint placement matrix stays in the
metrics bundle (tests pin it) but is no longer rendered. Verified: suite
269 green, served page XML-valid, geometry unit-checked, headless-Chrome
screenshot output/ui_player_court_preview.png (git-ignored).

**Analysis database + player labeling + local UI shipped (2026-09-04,
fourth session): extraction and DB are separate processes joined by a
lossless file contract.** Extraction (`make run`) now also writes
`output/<stem>/pipeline_output.json` — the canonical machine-readable
export (every emitted action keeps team/touch_number/rally_id/contact_kind/
contact_point, which the human CSVs drop; spikes minus flight arrays;
pipeline_version = git hash). A new `src/db/` package upserts that JSON
into SQLite (`data/volley.db`, WAL): `videos` (key = video stem),
`players` (names), `video_players` ((video, track_id) → player — track
ids are per-video bootstrap artifacts, NOT cross-video identities),
`actions`, `spikes`. **Overwrite semantics ratified:** re-ingest replaces
only that video's actions/spikes rows in one transaction; labels and
players survive (the ingester UPSERTs the videos row — never DELETE, which
would cascade-wipe video_players). No per-frame data stored (owner
decision). `src/db/metrics.py` computes the metric glossary at query time:
kill%/error%/dug% (denominator = attacks), hard/touch%, attack-zone
distribution, attack_zone×landing_zone placement heatmap, dig%
(denominator = opponent attacks via the player's dominant team per
video), blocks = ball-touching only with kill-block (rally ends with the
block) vs soft-block (play continues) derived from rally continuation —
no-touch blocks are never counted (owner rule; the pipeline cannot emit
them anyway). Aces PARKED (open point 13). Local web UI (`src/web/`,
`make ui`, FastAPI+Jinja, CSS-only charts — fully offline): video list,
per-video rally-grouped timeline + spike table, **labeling form**
(track→player dropdown/free-text), players overview, player detail with
metric cards/zone bars/placement heatmap/per-video splits. Gotchas
recorded: sqlite connections need `check_same_thread=False` under
FastAPI (sync handlers run in a threadpool); suite runs 262 green
(240 + 22 new: json exporter parity, ingest idempotency/label-survival/
cascade isolation, hand-computed metric fixtures, path resolution);
venv lacks pytest-cov so run `pytest -o addopts=""`. Seeded all seven
entreno videos — DB counts match the CSVs and recorded baselines (e3
14 actions/4 spikes, e6 6/2, e5 7/2). The DB is left UNLABELED for the
owner's real player names.

**e1 GT re-verification folded (2026-09-04, third session): the ratification
queue is now EMPTY.** Diagnosis (output/diag_e1_gt_reverify.py, sheets
output/gt_verify/e1_reverify_*) found the "id/team wobbles" were THREE mixed
player_id conventions in one file: 4 events in dominant-canonical ids, 2 in
L-R indices, and 3 (f36/f206/f277) in the F0-FLIPPED numbering — the f0 box
frame numbers ids 2↔3 opposite to the other 43 frames (positionally
continuous persons, only the numbers swap), and those three events follow
it. Owner ratified all corrections from the sheets: the 9 events re-expressed
under dominant canonical (f36→p2, f89→p1, f206→p4, f277→p2, f329→p1,
f371→p2 — the spiker is id2/LR3 A; f114/f257/f258 unchanged), f0 boxes
renumbered, f260's id1 B→A one-off typo fixed (it sat in the joust's nearest
box frame). **f258's block ruled NO-TOUCH** (e6 precedent extends: the GT
keeps the physical event; the pipeline legitimately emits one ball contact
per joust). Measured after the fold (same predictions):
player_accuracy_spatial **0.125 → 0.875** (L-R mirror-drops to 0.125 —
single-convention proof), labels-only F1 0.706 and team 7/8 unchanged (the
miss is the joust pair: pred's one emission is the block-A side while the
ball touch is the spike-B side). Every e1 residual is now known-class:
f114 freeball (pt 9 crossing signal), f206 set (pt 5 overhand-reception
pose), f257 joust one-emission. Suite 240 green (no code changed).

**Joust-split adjudicated + spike log detail shipped (2026-09-04, later
session): the e6 block was there but did NOT touch the ball** — the owner's
ruling closes open point 10(a): one manufactured contact IS the complete
detectable truth of the joust; a no-touch block has no ball-flight impulse,
so it is outside contact detection by design (the GT f308 BLOCK stays as a
physical event the pipeline legitimately cannot emit — no eval penalty
mechanism, no code change). Shipped alongside: the live-debug action log
now tells spikes' origin and destination — `Action: ... -> spike (0.65)
from A1` at emission (new `SpikeAnalyzer.spike_zone_for` query, takeoff
zone is known immediately) and a `Spike resolved: contact frame 308
player 1 from A1 -> lands B7 (out)` line the moment the outcome closes
(including re-logging retro-conversions: f173 logged `lands out of bounds
(out)` then re-logged `dug at A8 (dug)` when the f216 dig landed on the
"landing"). Verified on the real e6 two-pass run. Suite 232 → **240 green**
(+1 spike_zone_for, +7 formatter tests).

**Reentry contact shipped (2026-09-04): e6's out-of-frame joust spike
recovered, f265 overpass→set healed — and point 10's "instance #2" (e2 f167)
REFUTED by the sighting dump.** New REENTRY band in the classifier's
_detect_contact (next to the two bridge bands). Diagnosis: across e6's joust
the ball tracker reset at f289 (10 missing frames) and adopted a bottom-left
SPARE, so the real re-entry descent (f301–310) never reached _ball_history;
the tracker re-locked the game ball only at f314, post-joust. What the
classifier sees is a 12f sighting gap whose endpoints free flight cannot
connect (spare (34,118) → run start (1152,278): 1695px; the bridged-apex
shape it must not fire on is velocity-consistent: 34px) followed by a fast
horizontal run (≥40px/f, horizontally dominated) starting at/above the net
tape. The touch is manufactured at the gap MIDPOINT (e6 → f308 == GT
exactly), the point back-extrapolated along the run; attribution runs
normally at the manufactured frame (1A's clean pre-swap snapshot f308 is
within reach via the near-net exemption — heeding the owner's "place at/
before f308" caveat about the f311 tracker swap); gesture ATTACK (bypasses
the hands-overhead→BLOCK misread on a jumping toucher); the emitted team is
read from the takeoff stance [c-12, c-2] (SpikeAnalyzer's takeoff-window
fix, scoped to this contact kind — the contact-time snapshot is mid-jump by
construction and its airborne feet project deep).
**Measured (e6)**: +f308 spike t3 rally 1 (track 1 = the GT spiker, team A
via stance, conf 0.65) and f265 overpass→set: labels-only F1 0.667 →
**0.923** (P 1.0, R 0.857 — the only FN left is the GT f308 BLOCK, which one
manufactured contact per ball event cannot also emit), team 6/6. **A/B:
e1/e2/e3/e4/e5 byte-identical** (the identity-break gate is what keeps e2's
bridged apex at f149 out); production src.main path emits the same 6-event
stream. **e2's f167 is NOT a reentry case**: the tracker bridges the toss
apex (f141→f149) and the spike is a plainly visible bounce at f167 (rises
148/136px — the normal detector FIRES); the event dies at the reach gate by
4px (nearest snapshot box top 144px below the ball vs CONTACT_REACH 140),
and the true toucher (GT p3 B) is airborne and coasted ~200px away mid-jump
— a reach/ghost-drift residual (folded into point 7), not point 10. Suite
**232 green** (+8 reentry tests).

**Spike analytics shipped (2026-08-30): trail, touch/hard type, 9-zone attack
grid, kill/out/dug outcomes — plus an f297 GT correction that needs one more
owner pass.** New pure-observer `SpikeAnalyzer` (src/analysis/
spike_analyzer.py) wired into `FrameProcessor` (constructed/observed/flushed
there; live debug and the script only READ it — mirrors-pipeline rule holds).
A/B on entreno_3: the action stream is **byte-identical to HEAD** (0 base-field
diffs; only additive spike keys on the log's spike entries). Suite 198 → **220
green** (+22, tests/test_spike_analyzer.py). What was measured/built:

1. **Zone grid** (`CourtCalibration.world_point_to_zone` / `get_court_zone`):
   9 zones per half, numbered 1-9 left-to-right as seen standing at the net
   facing that side's OWN baseline — 180°-rotationally symmetric, so in camera
   view A's zone 1 is image-RIGHT at the net, B's is image-LEFT. NOTE: this is
   the mirror-swap of the ASCII sketch first drawn in the request; the GT
   anchors decide (both A attacks come from image-right at the net = "A1",
   f178's B attack from image-right = "B3"). GT attack zones: **4/4 exact**
   (B3/A1/B2/A1) after adding a takeoff-window fix — a jumping spiker's feet
   at contact are airborne and the homography projects them deep (f431 read
   B5 from airborne feet; the pre-contact stance closest to the net in
   [c-12, c-2] reads B2 ✓).
2. **Spike type by POST-CONTACT ASCENT, not exit speed** (TOUCH_RISE_PX=80):
   diag on the real sightings showed exit speed CANNOT separate the classes —
   the touches launch at 19-29 px/f (vertically!) while f431's hard ball left
   near-rest and fell. Ascent separates cleanly: touches rise 146-240 px above
   contact, hard balls ≤33 px. GT types: **4/4** (touch/touch/hard/hard).
3. **Outcome machinery**: landing = image-y descent terminating (bounce flip
   or quiet-loss); kill/out from the landed point's world coords; dug/blocked
   from a follow contact; **retro-conversion**: a just-committed kill/out
   whose ball then LOFTS ≥90 px (DIG_LOFT_PX — sand cannot rebound 2-3 m)
   within ±12f of a follow contact flips to dug. Trails render red fading
   (`overlay.draw_ball_trail`, TRAIL_MAX_AGE=45) + `KILL <zone>` marker +
   `spike hard`/`spike touch` labels in live-debug and the script; NO zone
   grid drawn (owner spec). CSV: `<stem>_spikes.csv` + per-player zone/kills
   tallies in statistics; evaluate.py scores spike_type/attack_zone/
   landing_zone/outcome on matched pairs.
4. **e3 GT**: f297 corrected to **spike A p3 t3** (owner decision — it was
   p4 B t1; A's f248 set is t2, so A's t3 is the rainbow; cascade recomputed:
   f332 dig B t1 pre_atk, f379 t2, f433 t3). Team accuracy 14/14 now (the old
   f294 over-set residual is GONE — open point 3 closed). New GT fields on
   the 4 spikes (spike_type/attack_zone/outcome/landing_zone), README +
   verify_action_labels updated.

**Outcome semantics completed (2026-08-31, owner ratification): kill = direct
fall OR dug-and-dies-without-a-set.** The owner adjudicated the four e3
"kills": the whole video is ONE point — f178/f297/f433 were dug AND set
(outcomes now `dug` with `dug_zone`, the annotated zones reinterpreted as
where the dig happened), and f541 is the rally-winning KILL (dug at f563, the
ball falls with no set; the owner's "8 B" annotation stands, measured fall
B7). Shipped as a pending-dug watch in SpikeAnalyzer: a dug record stays
provisional until a later touch event (kept up -> `dug`) or a CONFIRMED ball
death (`kill` at the fall point, in court or out). The confirmation window
(DUG_DEATH_CONFIRM_FRAMES=16 + loft rejection) is load-bearing: the descent
into the setter's hands looks exactly like a landing, and the set EVENT
arrives too late (lookahead emission ~f255 for a f248 set) to veto it — only
the physical loft test separates them (the real f539 death bounces 12 px; the
three set contacts loft 150+ px). **Final e3 numbers: outcome 4/4, dug_zone
3/3, spike_type 4/4, attack_zone 4/4, team 14/14; the single residual is the
kill's landing zone (measured B7 vs annotated B8 — the fall at world x≈1.9 m
is one column left of middle).** Suite **223 green** (+2 dug-kill tests).
Known-class miss unchanged: the f294/f297 pair fails the player-spatial gate
(pred center above the net resolves to the adjacent net player's box at the
10f-strided GT frame; the pred's team/player are right per the corrected GT).




**Off-court hold horizon shipped (2026-08-29): e2's wasted roster slot
recovered.** The owner's e2 tracking report decomposed into: (a) a
right-side OUT-OF-COURT bystander (x≈1660–1890, detected at conf 0.82–0.89,
feet beyond the right sideline) who straddled the line during bootstrap,
seeded a track, and was then fed CONTINUOUSLY for 415 frames by
`_may_feed_track`'s "continuously matched frame-to-frame" exception — which
had NO horizon and outranked both the grace window and the zone rules; (b)
the server (p1 A), out-of-court AND beyond the 1m zone margin at f0–8 →
never admissible, in court from f28 with no free slot; (c) t1 ghosting
(slot starvation). Fix: the continuous exception now expires
`player_off_court_hold_frames` (90) after the track's last IN-COURT
sighting → the track coasts, retires through the normal path, and strict
admission/gallery-restore re-takes the slot (measured on e2: bystander
coasting from f104, id reused by an in-court player from ~f188). Safety:
max real-player out-of-court streak measured on ALL GT videos = 46f (e6),
90 = 2× margin; zone-seed rules untouched (trial expiry governs them).
**A/B (6 videos, identical feeding): e1/e3/e4/e5/e6 byte-identical (0
differing frames); e2 changes only from f104** (the bystander's coast) with
one attribution change in the action stream (f256 set → track 2; labels/
teams identical). e2 actions F1 unchanged 0.571 — its residuals are the
known recall/label classes, not tracking. Accepted limitation: the f32
serve stays mis-attributed (server unadmissible before the slot frees;
widening the zone margin to reach x≈73 would re-open the e5-squatter door).
Suite 198 green (+5 tests). **Diag gotcha recorded:** two PlayerTracker
instances in ONE process permute bootstrap ids — `cv2.kmeans` consumes the
process RNG; A/B harnesses must `cv2.setRNGSeed(0)` per instance (production
single-run is deterministic; fresh process = fresh RNG).

**Short-gap bridge shipped (2026-08-27): e2/e6's missed digs recovered.**
The e2/e6 contact-recall residual (old open point 7) split into two classes
on diagnosis. (a) A **5–7-frame occlusion at the toucher's arms** — e6 f212
and e2 f206, both sheet-proven — sat in a hole between the normal detector
(needs ≥2 points within NEIGH per side) and the bridge (floor was 8f). The
bridge now takes gap 5–7 under three extra gates: the normal path PROVABLY
cannot fire (sparse NEIGH on ≥1 side), ball-identity continuity
(|Δx| ≤ max(24, 3·gap)), and for sparse re-acquisition a CROSS-GAP RISE
(first post-gap sighting ≥60px above the last pre-gap one — needs no future
points; decision time is c+7 and the right window ends at c+6). A/B on all
six videos: e1/e3/e4/e5 **byte-identical**; e2 +f209 dig with the cascade
healed (f256 dig→set t2, f306 t3); e6 +f216 dig t1, f265 dig→overpass t2
(GT set — blocked on the joust, open point 10). Labels-only F1: e2 0.222 →
**0.600**, e6 0.545 → **0.667**. Suite 193 green. (b) The **e6 f311 joust
is structurally invisible** to any descent/ascent bridge — the set toss
exits the frame top at f277 and the ball re-enters at net height f314
already deflected; the f289–302 "ball" is a bottom-left spare handled by 1B.
A "reentry contact" mechanism is diagnosed and parked (open point 10).
**GT ratification queue is loaded for the owner** (open point 11): e2's
three unmatched preds are REAL touches (f32, f118 set, f327 dig — sheets),
e2 f79 is a caught/held feed ball (static f78–82, then a toss —
pipeline-invisible by design), e6's f311 block team B is almost surely A.

**entreno_5's action layer is fully resolved (old open points 1+2 closed,
2026-08-26).** The GT now carries the owner's dictated truth (serve f20 p2
added, frames 63/111/160/200, six id corrections) plus two contact-sheet
corrections of our own (f160 spiker is GT4 not p3; f300 spiker is GT2 not
p4 — sheets in output/gt_verify/, **owner-ratified 2026-08-26**). Against
it the pipeline reads **7/7 contacts, 7/7 labels, 7/7 teams, 6/6 scored
players** (gated F1 0.857; the 7th pair's GT box is occlusion-flagged).
The fix was diagnosis-first and turned out to be ONE root cause, not a
disambiguation problem: the missed f111 set made the f60→f157 gap (97f)
exceed rally_reset_gap=90, corrupting every downstream touch number
(spike→dig→set→dig cascade). Two shipped mechanisms:

1. **Gap-bridged bounce** (`_bridge_contact`, classifier): the ball is
   often UNDETECTED across a touch (occluded at the toucher's hands —
   sightings fall to f102, resume rising at f114). A bounce whose bottom
   sits inside an 8–14-frame sighting gap now fires at the gap's first
   sighting with the touch point interpolated. Gates are deliberately
   strict (net descent ≥20px in, ascent ≥60px out — a sand rebound rises
   ~25px and must not read as a touch; gaps <8f are the normal detector's
   turf) so entreno_1/3/4 histories yield ZERO candidates — their streams
   are unchanged (e1/e4 byte-identical; e3 differs only in f539's
   self-reported L-R index 2→3, same attributed player by center).
2. **near-net exemption 1.5 → 2.5 ground metres** (config
   `attribution_near_net_exempt_m`): e5's f300 spiker took off 2.14m from
   the net and the width regime (36–40px) mis-called his side; at 1.5m the
   exemption missed him by 0.64m and the reach gate killed a DETECTED
   contact. The above-net-tape condition stays, so e3's f488-style
   below-tape set thief is still excluded. With the contact recovered it
   even reads gesture ATTACK → spike 0.65.

Production (`src.main`) verified to emit the identical 7-event stream on
e5. Suite 187 green. evaluate.py now scores BOTH GT player-id conventions
(e1/e3 actions are L-R indices, e4/e5 canonical — see previous commit);
with honest gating e3's gated F1 is 0.929, not the 1.0 previously recorded
(the f69 known misattribution used to count as TP by numeric coincidence).

**Generality + e1 (2026-08-26, later session):** e2/e6 (first runs on the
current stack) show zero bridge false positives and teams 1.0 on scored
pairs; their residual is genuine contact recall (e6 3/7, e2 2/4). e1's GT
turned out to be double-annotated (17 events ≈ 9 touches) — after dedup +
arbitration e1 detects 8/9 contacts with 3 known-class label residuals, so
the old "e1 = contact-recall-limited" story is retired. Current action
scores (labels-only F1): e3 0.929, e4 0.857, e5 0.857 (7/7 labels), e1
0.471, e6 0.667, e2 0.600 (both e2/e6 moved by the 2026-08-27 short-gap
bridge). (2026-08-28 ratification rounds: e2 **0.571** vs its complete
8-event GT, e6 0.667 vs the owner-corrected GT — the e2 dips along the way
were denominator honesty: each ratification round exposed events the GT
had been under-counting, and every remaining miss is now a diagnosed
class.)

**Team-aware contact attribution is shipped and GT-validated** on
entreno_3 (2026-08-16): team accuracy 0.69 → 0.92, label F1 0.90 → 0.93,
serve detected. Design: candidates filtered by expected touch team (ball
pixel-width regime + possession alternation), per-contact foot teams,
ground-metre near-net exemption, emitted team = toucher's foot team.
Residuals unchanged: e3 f294 over-set (width abstains), f69 same-team
adjacent choice.

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

**entreno_4/5 (2026-08-18):** owner-annotated GT (players every 10 frames, 6
action events each — no serves, no occlusion flags, noisier footage as
warned). e5's serve-zone-squatter tracking bug (bystander held the 4th slot
all video, server untracked) FIXED via server-vote admission + contested
swap + trial expiry: e5 tracking 0.722/0.278 → 0.958/0.042, the serve is
detected (f17), byte-neutral on e1/e4, action-stream-identical on e3. The GT
mis-ID corrections and the action-layer residuals were this session's work
(see the 2026-08-26 entry).

**Near-net flag (2026-08-17, later session):** old open points 4+9 closed by
diagnosis — 4's px→metres switch is GT-refuted (label F1 0.929 → 0.857/0.714):
the px `near_net` is load-bearing for the resolver's touch-3-at-net spike
rule. Point 9's block turned out to be REAL on the production/live-debug path
(a config divergence, fixed same day — see Log); the script path (all GT
numbers) always said spike. Details + revisit trigger in Open point 4 and the
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
the shared pipeline for real debugging. **[SHIPPED 2026-09-27 (twenty-third
session): both parked pose levers are now live in the shared classifier —
staleness gate + near-ball trail radius with the occlusion-window fallback;
7/7 entreno byte-identical, full match CSVs byte-identical, match 84.8→68.0
ms/frame. The remaining parked lever is open point 23 (live-debug display
decoupling).]**

**Plan reference:** the full design lives in the session plan file
(`~/.claude-zai/plans/i-want-to-start-golden-naur.md`, identity) and
(`~/.claude-zai/plans/read-status-lets-try-imperative-anchor.md`,
attribution — including the recorded design pivot away from image-plane
trajectory side). Short version of the identity architecture: uniforms vary/
are uncontrolled → colour can't be a trusted identity signal → **motion
continuity is the primary identity signal**, appearance/body-size are
conditional tie-breakers, and "exactly 4 players / 2 per side" is a hard
constraint. Side changes need no special handling as long as IDs survive.


**Production state (as of 2026-09-27).**

- **Weights:** `models/volleyball_ball_best.pt` = **v3** (fine-tuned FROM
  best.pt on 1091 + 350 rebalanced frames; ADOPTED 2026-09-26 after the
  four-leg gate; old weights stashed as `*_v1_entreno.pt` / `*_v2_match.pt`).
  Sub-1080p ingest upscales once to `_up1080.mp4`. Pose gating is live in
  the shared `classify_actions` path.
- **Match (20260920 — the only real match):** **31/33 GT points confirmed
  (0.939)**, first-confirmed at GT point 1, 57 episodes (26 starved);
  actions 207 (dig 84 / spike 45 / set 42 / serve 20 / overpass 9 /
  block 7); perf **68.0 ms/frame** (14.7 fps, 30.5 min) after the pose
  gates (was 84.8). All data CSVs byte-identical through the last two
  shipped mechanisms.
- **Entreno gate record** (`evaluate --ignore-player` F1): e1 0.706, e2
  0.571, e3 1.0, e4 0.933, e5 0.923, e6 0.933, e7 0.75; teams 1.0 except
  e6 0.857. Suite **491 green**.
- **Known residuals:** e4/e5/e6 GT re-adjudication vs the v3 streams
  (queued — owner-ratified contact sheets; GT was dictated against
  base-model behavior); e3 f539 outcome enrichment reads dug vs GT kill
  (tracker-side fast-fall conf dip — open point 22 family); match serves
  emitted 20 vs v2's 28 (open point 22). Live-debug display decoupling
  SHIPPED (25th session): `--debug-live` ≈ 12 fps vs 8.0 serialized,
  rendered frames + logs byte-identical (probe `output/
  diag_live_debug_probe.py`); batch untouched (68.0 ms/f stands).

**Active next (ranked, goal-driven — see North-star).** (1) Open point
22: build the episode→GT-point ORDER map (57 episodes ↔ 33 points), then
the far/near serve census on TRUE windows — serves both goals (serve
emission feeds aces/errors; the episode map is the backbone of per-point
fantasy lines). (2) e4/e5/e6 re-adjudication sheets. (3) 21.3 point
winner/outcome layer — G1's biggest missing signal (unlocks aces, serve
errors, per-point grouping). (4) Fantasy scoring module + web points
table (14e); assist ships with it (no perception needed).


---

## Header chain archived 2026-10-01 (sessions 31-46 + last implementation update #28)

**Previous (forty-sixth session — **RECORD-ONLY session:
S0 GT LANDED for the whole 20260920 match (owner dictated P9–P33 contacts
into the existing file), a NEW practice video + calibration arrived, and the
camera domain was pinned down. No `src/` change; no new mechanism.** The
owner added ~200 contact lines for P9–P33 to
`ground_truth/20260920_match_ari_joan_contacts_p1_p8.txt` in a SECOND dialect;
measured with the existing parser: the `Point` headers and all 4 `Side switch`
markers (after P7/14/21/28) parse, but **0 of the ~196 new contact lines do** —
all 34 point records appear yet only the 28 P1–P8 contacts come out, and the
file has a duplicated `Point 21` header. So S0's *owner* half is DONE and its
*worker* half (dialect-B parser → match-level GT JSON) is now the top next
step, not a worksheet. The dialect shapes + the owner's three new conventions
(overpass-labelled-as-overpass; **"missatr" markers are NOT exhaustive**; a
no-touch block is attributed to the spiking player) are recorded in
`ground_truth/README.md`. New footage: **`resources/full_videos/20290928_entreno_vall_dhebron.mp4`**
(1920x1080 native, 695 s, 20939 frames, ~30.1 fps VFR-ish, practice venue,
same camera, fewer points, teams keep changing) + `calibrations/20290928_entreno_vall_dhebron.json`
— **not ingested, no GT, no prediction run.** Camera facts pinned in
AGENTS.md §7: one camera for everything except `video_david`; always long
axis in front of the net outside the court, never moving mid-session but
**height changes per video** (court projects 206 px deep on the beach vs
464–479 px at the practice venue = 2.3x, so px constants are venue-coupled);
**the camera drops fps by itself in low light / high heat** (that is the
25.67 fps match, not a capture mistake — nothing to fix at capture time); the
match is natively 720p and is upscaled once to `_up1080`. The owner raised
FOUR new GT-semantics/attribution questions (open points 25, 26 and the
extension of point 5). Suite **840** (+1 parser-coverage test), mechanisms
unchanged. Next steps re-ranked below: GT-build for P9–P33 → first HELD-OUT
contact score → then the far-serve lever decision with real labels.

**Previous (forty-fifth session — **G3 plan S0b DONE:
the pass-2 serve stream scored at CONTACT level against the owner P1–P8
contact GT. `scripts/score_pass2_contacts.py` + `tests/test_pass2_contact_score.py`
(28 tests) + `docs/g3_s0b_pass2_contact_score.md`; no `src/` change, no
decode, output `output/pass2_contacts/`. The perception arm reproduces the T4
dev-clip baseline EXACTLY (P 0.586 / R 0.607 / F1 0.597, 1 dup, 2.703
FP/dead-min) under the padded region scope, which validates the scope; the
pass-2 arm is P 0.640 / R 0.571 / **F1 0.604 (+0.007)** with class accuracy
**0.706 → 0.562 (−0.143)**. FAR SERVES **0/5** at contact level (relabeled
contacts +31..+50 f = 5.4-8.6x the ±0.52 s effective tolerance; 3 of the 5 are
the GT receptions f245/3071/4800), and only **1/8** GT serves is matched at
all — f2575/f3747 (`anchor_only`) have NO action within ±80 f, so the "far
prefix census 8/8" counts ANCHORS, not contacts. Pass-2 changes exactly 4
contacts: 3 correct dig labels BROKEN (f245/3071/4800) and 1 TP LOST (the
f3856 owner-FALSE demotion). Verdict: the point-level serve story does not
survive contact scoring; the "park at pass-2" option for point 22 is closed
and pass-2 must not be consumed as a label source by S4 as it stands. Suite
**839**. Next = owner: S0 (P9–P33 contact GT) + the far-serve lever decision;
worker-side next = S3 (pass-2 squad/side-switch layer), which is independent of
the far-serve gap.

**Previous (forty-fourth session — **G3 plan S1, the
far-side serve LOOMING probe: diagnose-only, REFUTED at kill 2 (no separable
`L` gap).** `scripts/probe_far_serve_looming.py` +
`tests/test_far_serve_looming.py` (29 tests) + `docs/g3_far_serve_looming.md`;
no `src/` change, no config key. Mechanism measured: after the contact the far
serve flies toward the long-axis camera, so its tracked bbox width grows; in
the new-rally state (no emitted contact within `RALLY_RESET_GAP=90`) a far-band
(onset width ≤26 px) production-tracked segment gets `L` = OLS slope of
`ln(width)` vs seconds over `[onset, onset+0.5 s]`. RESULT: **kill 1 passes at
the boundary** — 4/5 dev far serves (f210/2154/3038/4770) have ≥5 far-band
tracked sightings in `[c, c+0.5 s]`; f880 has 3 — the far flight IS detected.
**Kill 2 FIRES:** lowest far-serve `L` **0.338** (P4 f2159) vs highest
new-rally non-serve `L` **0.945** (dead-time f1673; 0.495 at f4581) → overlap,
no empty gap, ratio 0.36× (need ≥1.5×); three new-rally non-serve segments
loom at/above the weakest far serve. Kill 3 vacuous (`L*` undefined); kill 4
pending owner S0. Match replay parity exact (0 locked / 0 centre mismatches
over 26068 frames; 55 far-band new-rally segments). Verdict: **the far-serve
looming lever is REFUTED at diagnosis** — same class as T5/R1; no threshold
tuned on 5 dev points. Suite **811**. Next = owner: S0 (P9–P33 contact GT) +
S0b contact-level scoring + decide the next far-serve lever (targeted detector
mining vs another mechanism).

**Previous (forty-third session — **open point 21.3:
the point winner/outcome layer SHIPPED as a pass-2 script.**
`scripts/resolve_point_winners.py` + `tests/test_point_winners.py` (27
tests) + `docs/point_winner_layer.md`; pure observer over the existing
artifacts (`episode_point_map.json` + `pipeline_output.json` +
`results_game_state.csv` + `serve_relabel.json`) — no video decode, no
`src/` change, entreno-neutral by construction. Mechanism = fault prior over
the terminal LIVE touch (its side loses), owner-verdict demotions excluded,
structural-only abstains, and a projection-level GT-leakage guard (the 13
winner-serves-derived `team_resolved` overrides are FLAGGED, never
inherited). Validation vs the 33 dictated winners: 33/33 decided, **18/33 =
54.5%** after the validate-only side→squad mapping. Miss taxonomy: 8
terminal-touch attribution (the point-22 far-serve/side gap) + 3 kill/ace
(ball-death in/out absent from every artifact) + 3 serve-team misattribution
+ 1 owner-pinned-outside-window; inheriting the GT overrides would buy 21/33
and is explicitly not shipped. Fixed 3 test-side defects in the inherited
untracked draft (session-42 left it unreviewed); the script reproduces
`output/point_winners.json` + the report byte-identically. Suite **782**.
This is an honest baseline, NOT fantasy-grade — consume it after S1–S3 so
the terminal touch and serving side are real.)

**Previous (forty-second session — **architect strategy
review of the "detector v4 → normalise → learned gestures" generalization
proposal; docs-only, NO `src/` change (`src/` still exactly `185c6f0`),
suite 755.** The proposed order is NOT adopted — each step conflicts with a
measurement already in the repo: detection loses 0/28 dev contacts (the
detector fires at conf 0.74–0.87 at all 5 lost serves); R1 was already
width-normalised and died on the held-out match (a far serve travels along
the camera axis, so its image-plane speed is small in any unit); labelled
contacts total 91 (63 entreno = ONE session + 28 dev) and R2's
leave-one-clip-out already showed pooled AUC 0.172 vs 0.551 (dev correct
rate 0.276 vs entreno 0.56–1.00); the largest dev loss is contact PROPOSAL
(6 candidate + 5 reach gate = 11/28), not the gesture label (4/28). NEW
FINDING (`output/serve_relabel.json` vs dev GT, P1–P8): the pass-2
far-serve census "8/8" is POINT-level bookkeeping — at CONTACT level it is
**0/5**: the relabeled serves sit at f247/930/2195/3070/4801 vs GT serves
f210/880/2154/3038/4770 (31–50 f late, outside ±15 f); three (247, 3070,
4801) are the GT receptions (245, 3071, 4800) turned into serves, the other
two (930, 2195) are dev in-point-spurious digs. The far-serve CONTACT is the
gap G3 and G1 share. New plan **S0–S4** in *Active next* (first mechanism =
S1, a diagnose-only far-serve looming probe, kill criteria pre-registered);
proposed `AGENTS.md` wording is in the Log and awaits owner ratification.)

**Previous (forty-first session — **G3 R1 departure
gate: implemented, fully validated, REFUTED on the held-out match — NOT
shipped.** The owner-approved mechanism (session 40 task2, found
uncommitted after that session died mid-run) was finished by a delegated
worker and coordinator-verified against raw artifacts. Gates (`--device
cpu`): entreno 6/7 byte-identical + **e4 0.933→1.000** (its offline-flagged
FP f388 removed; zero correct actions lost anywhere); dev contact **P
0.586→0.739, R 0.607 unchanged, F1 0.597→0.667** — exactly the 6
offline-flagged FPs removed, 0 additions; match arms (same code,
yaml-only `contact_min_departure_bw` 0 vs 0.3): **bw0 ≡ production**
(207/207 action-set identical to the posegate run; pass-2 reproduces 8/8
far census, 31 serve-typed, 17/17 owner verdicts, 31/33 points) but
**bw03 REFUTES: 22 removals incl. P11's owner-confirmed serve f7132
(0.285 bw/f), 6928A and P11's rally cluster → 17/17 verdicts broken,
points 31/33→28/33, far census 8/8→7/8** → STOP per spec, no threshold
tuning. Root: width-normalised departure conflates dead balls with far
float serves (T5 physics). Owner decision = option (a): `src/` restored
to exactly `185c6f0`, mechanism PARKED reproducible scripts-side
(`scripts/departure_gate_harness.py` verbatim helper + `action_evidence.py`
+ `probe_departure_removals.py`/`probe_owner_verdicts.py`; banner +
tables in `docs/g3_r1_departure_gate.md`). Suite **755**. Revisit only as
a width-band-aware mechanism after T8. Same-session R2 DIAGNOSIS (negative
result, no `src/` change): the planned calibrated confidence (continuity ×
gesture tier, leave-one-clip-out) is REFUTED at diagnosis — pooled AUC
0.172 vs 0.551 for the emitted hand-set constant, no variant wins; the
gesture tier reverses across clips (clip-type-driven) and fold base rates
anti-correlate with held-out rates. Motivation STANDS: hand-set constants
uncalibrated (ECE 0.154/0.164) and the `action_confidence=0.3` emission
filter is INERT (min emitted constant 0.45 — it never rejects anything).
Doc: `docs/g3_r2_confidence_calibration.md` (revival preconditions are
owner-gated: match-side per-prediction labels + clip-type-aware base
rates).)

**Previous (fortieth session — **G3 per-action evidence
diagnosis, diagnose only, NO `src/` change.** Owner added **G3 (action
accuracy) as the top goal**. `scripts/action_evidence.py` labels every
emitted action on dev + e1–e7 (85 predictions) against GT via
`evaluate_timed`'s matcher and joins already-computed features:
**54 correct / 11 wrong_label / 5 wrong_team / 1 both / 1 dup / 13 FP**
(dev alone 8/29 correct). The hand-set gesture `confidence` is
UNCALIBRATED (0.75→4/8 correct, 0.6→16/20, 0.55→23/37, 0.45→0/3).
Strongest signal: **post-contact departure in ball-widths/frame** over
the CONTACT_DELAY window — 6/14 FPs ≤0.198 bw/f, every correct action
≥0.423 bw/f (×2.1 empty gap; raw px/f only ×1.26 and far-biased). Ball
continuity (`track_frac_15f`) is the only monotone signal without a
per-clip reversal. Doc: `docs/g3_action_evidence.md`. Next = owner
approval of R1 (departure gate) — see Active next.)

**Previous (thirty-ninth session — **T5 revert/cleanup,
docs+tests only, NO production change**: the reviewer ruled that both T5
mechanisms (A weak 3 px/f tier, B backfill on a fresh lock) recover **0/5**
far serves and therefore must not live in `src/`. `src/` is restored exactly
to `185c6f0` — `git diff 185c6f0 -- src/` is EMPTY, the `ball_weak_*` /
`ball_backfill_*` DEFAULT_CONFIG keys and their config-drift rows are gone.
The mechanisms now live ONLY in the probe harness,
`scripts/serve_mechanism_harness.py`, as default-off subclasses of
`BallTracker` / `ActionClassifier`, so `scripts/probe_serve_mechanisms.py`
still reproduces `docs/t5_mechanism_ab.md` **byte-for-byte** (base 36/13/0,
A 37/14/19, B 37/14/0, 0/5 recovered, base fidelity 4968/4968). **T5
far-serve admission is REFUTED at the tracker level.** The root blocker is the
CONTACT PROBE's serve-branch geometry — it demands a FED ascent (|vin3| ≥
|vin6|+10, the e7 f25 pattern) while the far toss is a DECELERATING float —
plus **no toss detection at all** on P4/P6/P8; both are recognition/detection
work and need an **owner decision**.

**Previous (thirty-eighth session — action-reliability T5 step 2 DONE: the
approved mechanism is **REFUTED as a recovery**, and the real blocker is
elsewhere. A (weak 3 px/f tier) and B (backfill on a
fresh lock) were both implemented default-OFF and replayed through the
PRODUCTION classes (`scripts/probe_serve_mechanisms.py`; the base arm
reproduces the dumped production track on 4968/4968 frames): **both
recover 0/5 far serves**. A costs 19 new bootstrap locks for that zero;
B costs none, adds one dead-time candidate, and **does fix the
step-1 evidence gap** — the probe's `no_ball_sighting` rejections at
the 5 far serves fall 23/27/20/21/21 → 16/20/19/20/18 of 31 window
frames (confirmed end-to-end: the dev waterfall's only change is those
five detail strings; the pipeline output stays byte-identical). The loss
then moves to `no_contact_geometry`: with the full toss in the history
the far serve's contact measures vin=(0.8,0.7) vout=(6.5,-11.3) and the
probe's serve branch demands a FED ascent (|vin3| ≥ |vin6|+10, the e7
f25 pattern) while the far toss is a DECELERATING float; a hypothetical
float-serve signature would reach at most 2/5 (P4/P6/P8 have NO toss
detection to backfill). **(SUPERSEDED the same day by session 39: B is no
longer "shipped DEFAULT OFF" — neither mechanism is shipped at all; `src/`
is back at `185c6f0` and both live in the probe harness only.)**
Entreno e1–e7 byte-identical in both arms; dev evaluate_timed unchanged (F1 0.597).
+28 tests, suite 736.

**Previous (thirty-seventh session — action-reliability T5
DECIDED + step 1 DONE (diagnose only). **Owner APPROVED the T5 mechanism
(2026-09-29): serve-time ball-track (re-)admission** — extend the UNLOCKED
bootstrap so the far-side toss can lock below `lock_min_speed = 8 px/f`; NOT
time windows, NOT the width-split `unreliable` state. Step 1 measured it
offline: `scripts/probe_serve_admission.py` (new, reads the T4
`--diag-dump`, replays the bootstrap decision over the whole clip — baseline
replay reproduces the dumped `locked` flag on 4966/4968 frames) +
`docs/t5_serve_admission_diagnosis.md`. FINDINGS: **all 5 stage-3 serve deaths
are FAR-side serves** (toss ball 13-17 px wide, median pre-contact rise
1.6-6.7 px/f; the 3 surviving serves are near-side, 46-53 px, 7-17 px/f, locked
at contact); the failing condition is `speed_below_lock_min_speed`; a 3 px/f
weak tier recovers **5/5** at lock latency 0 (>= 20/31 window frames owned) for
~12 extra bootstrap locks per 4968 frames, and no candidate-geometry
discriminator removes them (ascending-only LOSES 2 serves). Entreno contrast:
every surviving serve there is near-side (e3 f29, e7 f22), so the entreno gate
has little power over this mechanism. Also **owner RATIFIED the P6 f3131
set->overpass reading** ("it's an overpass"): `scripts/build_dev_clip_gt.py`
gained a generic `OWNER_RATIFICATIONS` table and the GT flag now carries
`owner_ratified/date/statement`. +23 tests, suite 708.)

**Previous (thirty-sixth session — action-reliability T4 DONE:
loss waterfall on the dev clip. `--diag-dump` writes a per-frame JSONL of what
each stage already computed, from inside the shared `FrameProcessor.process_frame`
(`src/utils/diagnostics.py`; `if self.diag_enabled:` guards, default OFF, config
key `diag_dump` + config-drift guard extension); `scripts/waterfall.py` walks the
7-stage chain per GT contact and imports the T3 matcher so the two agree;
`scripts/compare_runs.py` is the byte-identity gate helper. BASELINE (first
dev-clip run ever, `--device cpu`): contact P 0.586 / R 0.607 / F1 0.597, class
0.706, team 0.706, 1 dup, 2.703 FP/dead-min, points 6/2/0 mean IoU 0.707.
WATERFALL: detection 0, admission 0, candidate 6, gate 5 (all reach), actor/team 5
(4 = post-P7 side switch), label 4, survives 8; FPs 8 in-point / 3 dead-time /
1 dup. FINDING: 5 of the 6 candidate deaths are serves where the detector DOES
see the ball (conf 0.74-0.87) and the tracker says `unlocked_no_motion` on
19-25 of 31 window frames — a toss apex slower than `lock_min_speed = 8 px/f`
cannot re-lock. T5 next: ONE mechanism, ball-tracker serve admission. Gates:
hooks-off == pre-change HEAD byte-identical on dev + e3 + e1, hooks-on ==
hooks-off byte-identical, +37 tests, suite 685. Table:
`docs/t4_loss_waterfall_dev_clip.md`.)

**Previous (thirty-first session — action-reliability T3 DONE:
`scripts/evaluate_timed.py`, the TIME-MATCHED evaluator (a sibling of
`evaluate.py`, which is untouched). One-to-one optimal assignment on time
distance, tolerance `max(0.2 s, GT frame_tolerance/fps)`, per-frame PTS when
the blob carries one else `frame/fps` (reported, no decode); SEPARATE scores —
class-agnostic contact P/R/F1, class accuracy + confusion matrix, team, actor,
duplicates, FP per dead-time minute, point intervals by temporal IoU.
`--autonomous` refuses a prediction file carrying GT-derived inputs (winners,
serve anchors, owner pins/verdicts, the map/re-label layers). +23 tests,
suite 648. Gate: entreno contact F1 e1 .941 e2 .857 e3 .929 e4 1.0 e5 1.0
e6 .933 e7 .750; at `evaluate.py`'s effective ±15f window the two agree
exactly and the ORDERING is preserved. No dev-clip prediction output exists,
so no dev-clip run. T4 next.)

**Last implementation update:** 2026-09-28 (twenty-eighth session — POINT 22 MECHANISM
3 SHIPPED: `scripts/relabel_serves.py` (+29 tests) — the pass-2 serve
re-labeling layer ratified in #27. The rally-opening contact of each TRUE
map window is re-labeled serve by structural prior: touch t1 + dead-ball
gap in the MEASURED chasm (openers ≥153f vs mid-rally ≤134f; threshold
143 = midpoint) + window-opening position; owner anchors outrank a
rejected opener (anchor_only), owner TRACKED/MISCLASSIFIED verdicts
outrank the gap veto and the fault-description guard, P20 is owner-pinned
to 14516A (round-2 q5), P32 stays report_only (fault desc contradicted by
a full post-serve rally, no owner verdict). Owner FALSE/OFFGAME serves
demoted (1039, 2414, 3595, 3856, 5130, 14387); 6928 reported-only (no
owner verdict). GATES: far prefix census **2/8 → 8/8** (target ≥6/8 ✓);
serve-typed actions **20 → 31** (−6 demoted +17 relabeled; ~28 sanity
anchor overshot because 30/33 points now hold an in-stream serve action —
every one mapped to a distinct point, 6928 included, pending owner
arbitration); ALL 17 owner round-1+2 verdicts reproduced mechanically
(P9-P12 at the exact contact frames); 13 team overrides flagged (the
far-side width-band class + P24's mirror). Entreno neutrality BY
CONSTRUCTION (zero src/ changes — only the new script + tests). Suite
**554** (+29).)

---

## Archived 2026-10-02 (#55): header chain #48-#54 + the "Where we are" block as of #54

**Last updated:** 2026-10-02 (fifty-fourth session — **S4 DONE: the serve evidence
is now a real artifact, and the honest number is two numbers.** The owner
approved the recommended operating point, so the structural arm shipped
(`ServeContactProposer` in `src/analysis/serve_events.py`, inside the
`--serve-events` envelope, 5 `serve_structural_*` config keys) and the pass-2
consumer landed (`scripts/consume_serve_evidence.py` -> `output/serve_evidence.json`,
which touches nothing else). The production artifact came from a real run
(26 061 frames, serve events: runway 395 / far flight 578 / conjunction 443 /
structural 60), and **inertness is measured**: the action streams with the
emitters ON and OFF are byte-identical over a 400-frame span and no
`serve_events` key appears when they are off. **Evidence coverage (anchored) is
14/17 GT far serves with 1 owner false positive (precision 0.90); the CONSUMER
binds 9/17 (dev 5/5, held-out 4/12)** — the signal is there, the interpretation
is the loss, exactly the G1 shape, so both numbers are reported and the doc
leads with the difference. The selector is one constant (min_next_gap=20 f, flat
over 15-20) and its sweep ships in the artifact. Two implementation findings
worth keeping: binding by **dead-time episode** rather than by the pass-2 point
window removed a whole failure class (4 of 8 misses were windows that do not
contain their own serve), and the five remaining misses are diagnosed —
P14/P22/P23 have no record at all, P28/P31 have a second record 8-19 f from the
contact, which the **net crossing** (already measured, unused) would resolve
post-hoc with no re-decode. Suite **1036**. **Next = the net-crossing selector,
then S4's ace/serve-fault derivation; the label bucket (`overpass` 0/18) is still
the largest held-out loss.**)

**Previous (fifty-third session — **the far serve is solved as
EVIDENCE: 14/17 GT far serves at ZERO false positives, up from 0/17 in
production.** The three checks ran in the order they were proposed. **M2 (opener
gate) = strict win**: a serve opens a rally, so gating the G4 conjunction on
60-240 f of emitted-contact silence takes precision 0.579 -> **1.000** with recall
unchanged at 11/17, and the plateau is 60-240 f wide because the match separates
openers (>=153 f) from mid-rally gaps (<=134 f) — so it is neither a fit nor a
device-jitter artefact. **M1 (magnified far-end crop) = REFUTED, and it corrects
the record**: the detector already sees the far ball in 14-31 of 31 frames at
every serve except P31 f24543, so the long-standing "the far ball is seen on 0-1
frames in 8/17 windows" was a **tracker** statement, not a detector one; the 4x
crop recovers only P31 (2/31 -> 26/31) at +105 ms/frame and its median detection
is 3.2 px of sand noise. **M3' (structural proposer) = measured frontier**: raw
detections + a far-band occupant + a reach in bbox heights + the opener gate, with
no tracker and no shape geometry, gives 11/17 at precision 1.00 (runway-only),
15/17 at 0.94 (runway+court, reach 1.0, median |offset| **1 f**) and 17/17 at
0.90; the two zero-FP rules fail on *different* windows, so their **union is
14/17 with no false positive at all** across 24 mid-rally contacts and the 9 owner
FALSE/OFFGAME moments. The two residual FPs are pre-serve ball handlings: no
dead-time test can separate those, only the toss does, and the toss is exactly
what the far-end geometry refuses. **A measurement defect was found and fixed on
the way**: every windowed G4 probe seeks, and a seek on this VFR file lands
**-28..+30 f** off, so the G4 score was really 11/17 (not 6/17) with offsets
systematically -9 f; two new seek-free probes, a 648-combination offline sweep,
`tests/test_vfr_seek_guard.py` (which also found that the owner-GT annotator can
display an off-frame image) and `tests/test_structural_serve_rule.py` (13 tests).
Suite **1008**, `src/` untouched. **Next = the owner picks the operating point
(recommend 14/17 evidence) and S4 consumes it post-hoc; the label bucket
(`overpass` 0/18) is still the largest held-out loss.**)
**Previous (fifty-second session — **the possession signal
(open point 9 enabler) was built, tested, and REFUTED as a needle-mover, then
parked default-OFF in a harness.** Two mechanisms: a ball-field width TREND
fallback in attribution (`_width_side_trend`: when the strict 26-35 px regime
abstains, the direction the apparent width moves names the arriving side) and a
motion-history tie-break (`_motion_convergence`, owner spec open point 5:
candidates within 60 px of the closest re-ranked by trajectory convergence).
Both were wired with config keys + drift guard + 18 unit tests, then measured:
entreno/dev effectively neutral (the e1 "team flip" was run-to-run
nondeterminism; dev shifted only one L-R `player_id`), and the decisive offline
replay of the REAL attribution methods on the match dump gives base **121/157
(0.771)** → both **122/157 (0.777)**. The trend fires 11× and is **11/11 on the
correct side** but mostly redundant; motion changes **0** team attributions.
The carry errors it targeted mostly have NO ball signal at all (ball lost),
which no ball-field rule can recover. Verdict: parked in
`scripts/possession_signal_harness.py` (default OFF, T5/R1 precedent), evidence
`scripts/probe_possession_signal.py` + `docs/g3_possession_signal.md`; `src/`
untouched. Suite **985** (+20). **ALSO: a second pi session (G4/#51) worked this
repo concurrently and its commit collided with my stash mid-validation — never
run two sessions on this repo at once.** **Next = the owner decides on the S4
consume-the-serve-events step, or another possession attempt with a NON-ball
signal (motion history alone was inert for team attribution).**)
**Previous (fifty-first session — **G4: the two serve-EVIDENCE
event emitters the owner asked for are built, scored and committed.** New
`src/analysis/serve_events.py`: **E1 `far_flight`** (a ball whose apparent bbox
width GROWS is flying at the fixed long-axis camera = far-side flight) and **E2
`runway_occupant`** (any raw person detection whose foot is behind the far line
and inside the two sidelines CONTINUED TO INFINITY, never behind the near line),
plus the owner's conjunction `serve_candidate` ("a player in that area, with the
ball, and a contact"). Wired into `FrameProcessor.process_frame` as pure
observers, **default OFF** (`--serve-events`), with two inert detector side
channels (person boxes the play-area filter dropped; pre-static-suppression ball
candidates). Geometry is image-space from the 8 calibration clicks because the
far-end ground homography is off by ~10x, and the band STRADDLES the far line as
a fraction of the court's projected depth. `scripts/score_serve_events.py`
(+`--control`) + 45 tests + `docs/g4_serve_events.md`; suite **965**.
Measured on the 17 GT far serves (windowed replay through the real
`process_frame`): runway **15/17** (only 7/17 genuinely off-court), far flight
in window / conjunction at +-15 f — **CORRECTED in the addendum below** (this
block's ball-side numbers came from a config that silently ran the COCO
`yolov8n` ball detector; with the production model they are far flight 16/17
in window and 8/17 at +-15 f, conjunction 14/17 in window and **6/17** at +-15 f
— 3/5 dev, 3/12 held-out — with 4/24 control false positives, precision 0.60,
recall 0.35, against production's **0/17**). Verdict: the runway leg is strong, the conjunction is a
real but thin signal — an evidence stream for the G2 decision, NOT a fix.
**Next = the owner reads `docs/g4_serve_events.md` and decides whether to consume
the events in the post-hoc layer (S4) or keep pushing the ball side (a far ball
is detected ~1 frame in 4 and half the far-serve windows show no growing run at
all); the label bucket (`overpass` 0/18) is still the largest held-out loss.**)

**Previous (fiftieth session — **G3 overpass
net-crossing diagnosis: the ball-width crossing signal is REFUTED.** Open
point 9's "thread the crossing signal into the resolver" lever was probed
diagnose-only (`scripts/probe_overpass_crossing.py` + 19 tests +
`docs/g3_overpass_crossing.md`; no `src/` change, no decode). On the 18
held-out GT overpasses (P9–P33) a width-regime crossing across the contact is
present at only **3/18**, indistinguishable from the non-attack controls (set
4/46, dig 10/55) — K1 (signal present) and K2 (separation) both FIRE. The ball
is tracked on both sides at **18/18**, so it is not a detection gap (K3
clean): the crossing is at the net/tape where the width regime abstains, and a
high lob reads ambiguously on both sides. The perceived next-contact team is
also unusable as a substitute (overpass flip 8/18 = 0.444 vs controls 0.582;
K4 fires) because the stream's possession/team read is noisy (G1 side-level
0.755). The overpass loss is therefore a LABEL/RULE problem, not a geometry
one: the resolver emits `overpass` only at touch-2-no-follow while GT
overpasses span touch 1/2/3, and the emitted reads were dig 6 / spike 5 / set
2 / missed 5. The three implementable rules were then REPLAYED offline through
the imported resolver on the dump's raw contacts: **all net-negative** (baseline
85 correct; next-team 71, no-follow 80 with 3/18 recovered, next-team+side 82
with 0/18) — so no overpass `src/` change ships (T5/R1 precedent). Suite **920**
(+23). **Next = the ENABLING work (a reliable possession/next-toucher signal —
the 34 genuine side errors) or the G2 far-serve decision / S4; the label bucket
is still the largest held-out loss (57/183).**)

**Previous (forty-ninth session — **S3 DONE: the pass-2
side-switch/squad layer.** `scripts/resolve_side_switches.py` (+25 tests) +
`docs/g3_side_switch_layer.md`; no `src/` change, no decode. Derives the beach
switch cadence from the POINT ORDER alone (`[7,14,21,28]`, EXACT vs the owner
`side_switch_after_point`), maps court-side→squad by parity, and augments
`actions_pass2` with `pass2_squad`. The needle is a measurement confound found
en route: the perception stack emits COURT-SIDE letters while the GT is SQUAD,
so G1's raw `team 0.518` is side-vs-squad; the same 139 found contacts score
**105/139 = 0.755** squad-mapped (leaving 34 genuine side errors). The
player-crossing cross-check is honest but useless (3/4 switches supported, but
16/28 non-switch boundaries also supported — ids hop, open point 2) and is
evidence only. Suite **897** (+25). **Next = S4 (consume `pass2_squad`) or the
G2 owner far-serve decision; the label bucket (`overpass` 0/18) is still the
largest held-out perception loss.**)

**Previous (forty-eighth session — **G1 DONE: the first
HELD-OUT contact score on P9–P33.** `scripts/score_heldout_contacts.py`
(+20 tests, `tests/test_heldout_contacts.py`) + `docs/g3_heldout_p9_p33.md`;
no `src/` change, no video decode. On the 183 owner contacts of the 25 held-out
points the production stream scores **P 0.785 / R 0.760 / F1 0.772**, class
**0.590**, team **0.518**; pass-2 is flat on F1 (0.774) and again costs class
(0.561). The re-rank: held-out contact *detection* is BETTER than dev
(F1 0.772 vs 0.597), so the dev loss budget over-weighted proposal (39% vs
24%) and under-weighted the gesture label (14% vs **31%** — 57 wrong-label /
44 missed / 36 wrong-team of 183). `overpass` is never emitted correctly
held-out (recall 0.000 across 18 contacts). The 12 held-out FAR serves are
**0/12**: 8/12 have a nearby emitted "serve" (6 are the pass-2 re-labelled GT
reception, 2 are production serves 26–28 f late with the opposite team), 4
have nothing within ±80 f — the S0b dev finding reproduced on 12 independent
contacts. The 44 missed are mostly not empty-stream (41/44 have an action
within ±80 f, 7–69 f away). The stage waterfall is NOT reproduced (the only
full-match diag dump is the R1 bw=0.3 run); recorded as unavailable, never
faked. Suite **872** (+20). **Next = G2: the owner decision on the far-serve
lever, now decidable on data with baseline F1 0.772 / far-serve 0/12.**)

## Where we are

**The far serve is SOLVED as evidence (#53): 14/17 GT far serves at zero false
positives, against 0/17 in the action stream.** The three levers the owner asked
for were run in order and each returned a verdict: the **opener gate** is a
strict win (precision 0.579 -> 1.000, recall unchanged, plateau 60-240 f wide);
the **magnified far-end crop** is refuted and, more importantly, shows the far
ball was never missing from the detector's point of view (14-31 of 31 frames at
every serve but P31) — the old "0-1 tracked frames" line was the *tracker*; and
the **structural proposer** measured as a clean frontier (11/17 @ 1.00, 15/17 @
0.94, 17/17 @ 0.90, union of the two zero-FP rules 14/17), built on raw
detections so it needs neither the tracker nor the px-space contact geometry.
A measurement defect surfaced on the way: windowed G4 probes seek, and a seek on
this VFR file lands -28..+30 f off, so the G4 score was really 11/17 with -9 f
offsets, not 6/17 (`docs/g4_far_serve_alignment.md`, now guarded by a test).

Everything here is **evidence**, not labels: `src/` is untouched, nothing is
written to `events`/CSV, and per AGENTS.md §6 + the S0b lesson it is consumed
post-hoc. Next owner action: pick the operating point (recommend the 14/17
union) and let S4 consume it for who-served / aces / serve faults. Still open:
S4's remaining work, the label bucket (`overpass` 0/18), the reach-gate and
dig-vs-ball-death buckets, and the two seek defects the guard test surfaced
(owner-GT annotator, thumbnail crops).

- **Held-out score** — `scripts/score_heldout_contacts.py` scores P9–P33
  against `ground_truth/20260920_match_contacts.json` with the S0b scope
  discipline (region f5240–f26147 = the padded span of the emission windows;
  a SCOPED GT copy so P1–P8 can't be charged as FN; `evaluate_timed` matcher,
  `--ignore-player`, effective ±15 f). Production **P 0.785 / R 0.760 / F1
  0.772**, class 0.590, team 0.518; pass-2 F1 0.774 / class 0.561 / team 0.561.
  Doc `docs/g3_heldout_p9_p33.md`; artifacts `output/heldout_contacts/`.
- **S3 side-switch/squad layer** (`scripts/resolve_side_switches.py`, +25
  tests, `docs/g3_side_switch_layer.md`) — beach cadence from the point order
  alone → `[7,14,21,28]` EXACT vs the owner schedule; side→squad by parity;
  `actions_pass2.pass2_squad` on 207/207 actions. The recorded G1 **team 0.518
  is a side-vs-squad confound** (the stack emits side letters): the same 139
  found contacts score **0.755** squad-mapped, leaving **34 genuine side
  errors**. The player-crossing cross-check is evidence-only (ids hop, open
  point 2).
- **Possession signal REFUTED + parked (#52, open point 9 enabler)** —
  `scripts/possession_signal_harness.py` (default OFF) +
  `scripts/probe_possession_signal.py` + `docs/g3_possession_signal.md`; no
  `src/` change, no decode. Offline replay of the REAL attribution methods on
  the match dump: base **121/157 (0.771)** → both **122/157 (0.777)**; the
  ball-field width trend fires 11×, **11/11 correct side** but redundant;
  the motion tie-break changes **0** team attributions. The carry errors it
  targeted mostly have no ball signal at all (ball lost mid-flight). Parked
  per the T5/R1 rule.
- **Miss taxonomy (perception, 183 contacts)** — 46 correct / **57
  wrong_label** / 36 wrong_team / 44 missed. The largest bucket is the label,
  not proposal. The 36 wrong_team is inflated by the side-vs-squad confound
  (S3); the true side error is ~34 of 139 found contacts. `overpass` 0/18
  correct (13 found, all mislabelled); serve recall 0.280 (far serves all
  missed). Only 3/44 missed have no action within ±80 f.
- **Overpass crossing diagnosis REFUTED (#50, open point 9)** —
  `scripts/probe_overpass_crossing.py` (+19 tests) +
  `docs/g3_overpass_crossing.md`; no `src/` change, no decode. On the 18
  held-out GT overpasses the width-regime crossing across the contact is
  **3/18** vs non-attack controls (set 4/46, dig 10/55): K1+K2 fire. The ball
  is tracked both sides at **18/18** so it is NOT detection (K3 clean); the
  crossing sits at the net/tape where width abstains and a high lob reads
  ambiguously. The perceived next-team is no substitute (overpass flip 8/18 =
  0.444 vs controls 0.582; K4 fires). Emitted reads: dig 6 / spike 5 / set 2 /
  missed 5; the resolver emits `overpass` only at touch-2-no-follow while GT
  overpasses span touch 1/2/3. Artifacts `output/g3_overpass/`. The three
  implementable rules replayed offline through the imported resolver are ALL
  net-negative (baseline 85 → 71/80/82), so no `src/` change ships; the blocker
  is a reliable possession/next-toucher signal (34 genuine side errors).
- **G4 serve-evidence events (#51, re-scored #53)** — `src/analysis/serve_events.py` emits
  `runway_occupant` / `far_flight` / `serve_candidate` from the shared frame path
  as pure observers, **default OFF** (`--serve-events`); `serve_events` appears
  in `pipeline_output.json` only when they run. Geometry is image-space from the
  8 calibration clicks (the far-end homography is ~10x wrong), laterally the two
  sidelines continued to infinity, longitudinally a band straddling the far line
  (`-0.15..+0.30` x court depth). Scored on the 17 GT far serves vs 24 mid-rally
  non-serve control windows: runway **15/17** (only 7/17 genuinely off-court),
  conjunction **6/17** at +-15 f (**3/12 held-out**) vs production **0/17**, FP
  **4/24** -> precision 0.60, recall 0.35. Docs `docs/g4_serve_events.md`,
  `docs/g4_far_serve_failure_mode.md`; scorers `scripts/score_serve_events.py`,
  `scripts/probe_far_serve_{tracking,geometry}.py`. These are EVIDENCE — no
  consumer is wired, and the label bucket (`overpass` 0/18) is still the largest
  held-out loss. **[#53 those numbers are superseded — the windowed probes SEEK
  and a seek on this VFR file lands -28..+30 f off
  (`docs/g4_far_serve_alignment.md`). Seek-free the same conjunction scores
  **11/17 with 8/24 control FPs (precision 0.579)**, and with the **opener gate**
  **11/17 at 0/24 FPs — precision 1.000.** Keep the old figures only as
  provenance.]**
- **S4 CONSUMED (#54, `docs/g4_serve_evidence.md`)** — the recommended
  operating point is a real artifact. `ServeContactProposer`
  (`src/analysis/serve_events.py`, inside the `--serve-events` envelope, 5
  `serve_structural_*` config keys, 12 tests) emits the structural arm;
  `scripts/consume_serve_evidence.py` (pass 2) writes
  `output/serve_evidence.json` — 87 records, 21 with both arms agreeing, 19/33
  points bound, a `validation` block and a `disclaimer` — and touches nothing
  else. Production artifact from a real 26 061-frame run (`--serve-events`);
  **inertness measured**: action streams byte-identical ON vs OFF
  (`scripts/probe_serve_events_inertness.py`). **Two numbers, both reported:**
  anchored evidence coverage **14/17** GT far serves with **1** owner
  FALSE/OFFGAME false positive (precision 0.90), and the consumer's own binding
  **9/17 (dev 5/5, held-out 4/12)** — the signal is there, the interpretation is
  the loss (the G1 shape). Selector = one constant (`min_next_gap = 20 f`, flat
  over 15-20, sweep shipped in the artifact). Two design facts: **bind by
  dead-time EPISODE, not by the pass-2 point window** (the windows are
  predictions and 4 of the first version's 8 misses were serves outside their own
  window), and **the GT is validate-only** — nothing GT-derived enters a record.
  Suite **1036**.
- **THE FAR SERVE IS SOLVED AS EVIDENCE (#53, `docs/g4_structural_serve.md`)** —
  a structural proposer over the RAW detections (no tracker, no px-space shape
  test): *no emitted contact for 60-240 f* + *a person in the far band* + *a
  far-side ball-sized (8-60 px) raw detection within 30 f* + *the ball within R
  bbox heights of that person*. Measured frontier on one seek-free pass (17 GT far
  serves, 24 mid-rally controls, the 9 owner FALSE/OFFGAME moments):
  runway-only @ reach 1.5-4.0 = **11/17, 0 FP of any kind**; runway+court @
  reach 1.0 = **15/17, 1 owner FP** (f5130, ball handling after the point ended);
  @ reach 2.5 = **17/17, 2 owner FPs** (adds f2414, walking to the serve line with
  the ball in hands). Median |offset| **1 f** (the G4 conjunction's is -9 f). The
  two zero-FP rules fail on *different* windows, so their **union is 14/17 with no
  false positive at all** — the recommended operating point. Driver
  `scripts/sweep_structural_serve.py` (648-combination offline sweep over the
  recording, no decode), tests `tests/test_structural_serve_rule.py`. The
  residual FPs are pre-serve handlings: no dead-time test separates them, only the
  toss does, and the toss is what the far-end geometry refuses — which is why
  this is evidence (post-hoc, AGENTS.md §6) and not a label source (S0b broke 3
  correct dig labels).
- **M1 magnified far-end pass REFUTED (#53, `docs/g4_far_ball_presence.md`)** —
  the same production weights on a 4x-magnified square crop of the far band
  (`scripts/probe_far_roi_ball.py`, tile 320, 3 tiles, tile geometry from the 8
  calibration clicks): **0 of 17 windows were empty for the full-frame arm**, so
  the "the far ball is too small to detect" premise is FALSE — the detector sees
  15-21 px balls in 14-31 of 31 frames at every serve except P31 f24543 (2/31,
  which the tiles recover to 26/31 at +105 ms/frame). The tiled arm's median
  detection is 3.2 px of unscaled sand/line noise. Parked as a possible
  P31-class fallback; not built. **This also corrects a long-standing claim: the
  "0-1 tracked frames in 8/17 windows" figures in the STATUS/G4 docs are TRACKER
  counts, not detector counts.**
- **Scale-aware geometry REFUTED (#52, the owner's "lets try scale aware
  geometry")** — `scripts/scale_aware_harness.py` (subclass of the production
  `ActionClassifier`, OUTSIDE `src/` per the refuted-mechanism rule) +
  `scripts/probe_scale_aware_geometry.py` + `docs/g4_scale_aware_geometry.md`;
  7 fidelity/inertness tests pin the `px` arm to `super()`. Arms over the SAME
  recorded ball tracks (57 windows: 17 far serves, 16 near, 24 non-serve
  controls; +-15 f): thresholds as `k x ball width` buy **+1 far contact
  (held-out only, 0 on dev) for +4 control false positives** -> precision 0.40
  -> 0.33; k=0.5 buys nothing and still costs a FP. A **mirror** arm (a
  far-side serve is hit at the camera, so the ball PEAKS and descends — the
  mirror of the `bounce` shape) adds nothing on top. The multiplier each test
  would need says why (`--required-k`): bounce **8.2** ball widths, redirect
  **2.4** (near-equivalents 4.5 / 1.3); the tests reachable at k~0 (drive decel,
  serve fed ascent, mirrored peak) are reachable because they no longer
  discriminate (any downward change / gravity arc / lob apex passes). Three
  walls, none a threshold size: 8/17 far serves have **no usable vertex at all**
  (0-1 tracked frames), the rest are **wrong shape/sign** (depth-dominated
  motion), and the contacts that do fire are **wrong label** (attribution picks
  the nearest tracked player). The G4 evidence path still dominates every arm
  (6 hits / 4 FP = 0.60 precision, 0.35 recall). Nothing shipped.
- **WHY the far serve dies (#51, the "which signal does not switch" answer)** —
  `docs/g4_far_serve_failure_mode.md`. The stage waterfall is nearly IDENTICAL
  far vs near (first failing stage: candidate 6/17 vs 7/16; probe reasons
  `no_ball_sighting` 334 vs 256, `no_contact_geometry` 150 vs 195), so it is not
  a skipped stage: **the contact GEOMETRY cannot reach its thresholds at the far
  end**. Replaying every recorded far-serve ball track through the production
  `ActionClassifier`: no vertex is ever the lowest point (bounce needs a 26 px
  rise), horizontal flip **0 px** (redirect needs 20 px), `dvy` +4/-1 (drive
  needs <= -8), `dvx` 2 px (needs 12), and the **serve branch's fed-ascent
  margin is +0..+4 px against its required +10** — the far toss DECAYS like free
  flight, which is that branch's designed reject. Near-side control reaches
  rise 60-100 px, flips 38-65 px, `dvy` -42, fed ascent +13..+20 and fires 5/10.
  Root cause: all four thresholds are near-half-scale px constants (AGENTS.md
  §5) and at the far end the ball's image motion is DEPTH-dominated (growing +
  descending toward the lens), so a far serve looks like uninterrupted free
  flight. Secondary, independent: 2/17 far serves have zero raw detections at
  conf 0.15 and 5/17 never lock a track; and where a candidate IS accepted
  (P28 f21344-46, P25/P26/P4) the label is dig/overpass because attribution
  picks the nearest TRACKED player — the server is not one.
- **Far serves 0/12 held-out** — 6/8 with a nearby "serve" are the pass-2
  re-labelled GT reception (+26…+34 f), 2 are production serves 26–28 f late
  with the opposite team, 4 have no serve within ±80 f. The S0b dev finding
  holds on 12 independent contacts; the far-serve CONTACT is measured, not
  data-starved.
- **Scope caveat** — the episode-map emission windows are PREDICTIONS and
  only 12/25 cover their own owner contact range (P32 window f24614–f25085 vs
  contact f25375); the contact P/R/F1 is window-independent, the dead-time /
  points metrics inherit the drift.
- **Stage waterfall gap** — `scripts/waterfall.py` needs a production match
  diag dump; the only one is the R1 bw=0.3 run, whose gate decisions differ.
  A fresh production dump is a follow-up decode.
- **G0 facts stand** — match contact GT `20260920_match_contacts.json`: 33
  points / **211 owner contacts** (28 P1–P8 + 183 P9–P33), match-frame axis,
  all `source=owner_gt`; P1–P8 rebuild field-identical (only `raw_line_no`
  +3); side→squad is switch PARITY; P30 f23545 `action=null` +
  `owner_action_unspecified`. Builder `scripts/build_match_contact_gt.py`.
- **New practice video** `20290928_entreno_vall_dhebron.mp4` still not run
  (cheap parallel G3-footage item; it has no labels).

**Production state (as of 2026-09-28; unchanged by #30's documentation-only
assessment — #28 shipped the pass-2 serve re-label layer over existing
artifacts, zero src/ changes).** The proposed generalization roadmap in
`docs/202609-28-astra-fix-pipeline.md` awaits owner approval; the active
implementation backlog below remains unchanged.

- **Weights:** `models/volleyball_ball_best.pt` = **v3** (fine-tuned FROM
  best.pt on 1091 + 350 rebalanced frames; ADOPTED 2026-09-26). Sub-1080p
  ingest upscales once to `_up1080.mp4`. Pose gating live in the shared
  `classify_actions` path.
- **Pass-2 serve layer SHIPPED (28th session):**
  `scripts/relabel_serves.py` (+29 tests) over the anchored map +
  pipeline JSON → `output/serve_relabel.json` (per-point resolution +
  demotions + `actions_pass2` annotated stream + gates). Far prefix
  census 2/8 → **8/8**; serve-typed 20 → **31** (−6 owner-FALSE/OFFGAME
  demotions, +17 bump-serve re-labels, 6928A reported-only); 32/33
  points carry a serve resolution (P32 report_only, round 3); P20
  owner-pinned to 14516A (q5). All 17 owner verdicts reproduce
  mechanically. 13 team overrides flagged (far-side width-band class).
  **CAVEAT (#42): the 8/8 census and the 31 serve-typed are POINT-level;
  at CONTACT level P1–P8's far serves are 0/5 (relabeled contact 31–50 f
  late, 3 of 5 are GT receptions) — the "width-band class" attribution of
  the overrides is unverified (P1 f247 / P6 f3070 are correct-team near
  receptions: the override masks a missing serve contact).**
- **Pass-2 winner layer SHIPPED (43rd session, open point 21.3):**
  `scripts/resolve_point_winners.py` (+27 tests, `docs/point_winner_layer.md`)
  — fault prior over the terminal live touch, side-letter winner, explicit
  GT-leakage projection guard (13 winner-serves overrides flagged, never
  inherited). 33/33 decided, **18/33 (54.5%)** vs the 33 dictated winners
  after the validate-only side→squad mapping; 8 misses are the point-22
  terminal-touch/far-serve attribution gap, 3 kill/ace (ball-death side not
  in any artifact), 3 serve-team, 1 pinned-outside-window. Honest baseline;
  consume after S1–S3. No `src/` change, no decode.
- **Match (20260920 — the only real match):** **31/33 GT points confirmed
  (0.939)**; actions 207 (dig 84 / spike 45 / set 42 / serve 20 /
  overpass 9 / block 7) at the perception layer — the pass-2 layer
  re-interprets serves post-hoc (31 serve-resolved incl. 17 re-labels);
  perf **68.0 ms/frame** (14.7 fps, 30.5 min).
- **Entreno gate record** (`evaluate --ignore-player` F1): e1 0.706, e2
  0.571, e3 1.0, e4 0.933, e5 0.923, e6 0.933, e7 0.75; teams 1.0 except
  e6 0.857. Suite **554 green**. Live-debug decoupling (#25): `--debug-live`
  ≈ 12 fps vs 8.0, rendered frames + logs byte-identical.
- **Known residuals:** e4/e5/e6 GT re-adjudication vs the v3 streams
  (queued — owner-ratified contact sheets); e3 f539 outcome enrichment
  reads dug vs GT kill (tracker-side fast-fall conf dip — 22 family);
  P32's serve + 6928A's verdict + P20's window/re-serve question sit in
  the round-3 owner queue.

**Action-reliability track (session 38):** executable plan lives in
`docs/action_reliability_plan.md` (T1-T15, status per task). Dev clip =
`video_ari_joan_8_first_points.mp4`; T1 readiness DONE, T2 dev-clip GT DONE
(P6 f3131 owner-RATIFIED as an overpass, 09-29), T3 time-matched evaluator
DONE, T4 loss waterfall DONE, **T5 DONE (step 1 diagnosis + step 2 A/B =
mechanism refuted)**. Dev-clip baseline: contact P 0.586 / R 0.607 / **F1
0.597**, class 0.706, team 0.706, 1 duplicate, 2.703 FP per dead-time minute,
points 6 matched / 2 missed / 0 spurious (mean IoU 0.707); waterfall 0
detection / 0 admission / **6 candidate** / 5 gate / 5 actor-team / 4 label /
8 survives. **T5 result (38th session):** both candidate mechanisms recover
**0/5** far serves. A = weak 3 px/f tier far-band gated: 5/5 locks in the
offline sweep (as measured in step 1) but 19 new bootstrap locks per 4968
frames in the real-class replay and still no contact candidate. B = backfill
on a fresh lock: 0 new lock opportunities, +1 dead-time candidate, and it
converts the far-serve probe rejections from `no_ball_sighting` (23/27/20/21/21
of 31 window frames) to `no_contact_geometry` — the missing pre-contact history
of the step-1 diagnosis is supplied and the loss moves one gate along. The
blocker is the CONTACT PROBE's serve signature (a fed ascent, |vin3| ≥
|vin6|+10; the far toss is a decelerating float) + the absent far-toss
detections on P4/P6/P8 — recognition/detection mechanisms, not ball-track
admission. **NEITHER mechanism is shipped** (session 39): `src/` is back at
`185c6f0` (`git diff 185c6f0 -- src/` empty) and A + B live only in
`scripts/serve_mechanism_harness.py` as default-off subclasses, so the A/B
replay is reproducible with the same numbers (evidence in
`docs/t5_serve_admission_diagnosis.md` step-2 section,
`docs/t5_mechanism_ab.md`, `docs/t4_loss_waterfall_dev_clip.md` "After T5").
**R1 attempted and REFUTED (41st session):** the confirmation-time
departure gate passed its fitting domain cleanly (dev contact P
0.586→0.739 / F1 0.597→0.667 with exactly the 6 offline-flagged FPs
removed; e4 0.933→1.000; entreno otherwise byte-identical) but the
held-out full match refuted it at 0.3: 22 removals incl. P11's
owner-confirmed serve f7132 (0.285 bw/f) and 6928A → owner-verdict
regression, points 31/33→28/33, far census 8/8→7/8. Width-normalised
departure conflates dead balls with far float serves (T5 physics again).
NOT shipped (owner option (a)): `src/` back at exactly `185c6f0`,
mechanism parked reproducible (`scripts/departure_gate_harness.py` +
`action_evidence.py` + `probe_departure_removals.py`/`probe_owner_verdicts.py`;
banner + tables in `docs/g3_r1_departure_gate.md`); suite 755. Revisit
only as a width-band-aware mechanism after T8.
Next = the far-side serve follow-up. The 42nd-session architect review chose a
diagnose-only S1 looming probe first; **#44 ran it and it was REFUTED at kill 2**
(no separable `L` gap; see Log + open point 22). T5 (tracker admission) and R1
(departure gate) were already refuted; the pass-2 relabel option stays rejected.
The next far-serve lever is an OWNER call (targeted far-flight detector mining
vs another contact-proposal mechanism); S2 is NOT triggered. Owner-side S0
(P9–P33 contact GT + capture spec) remains the highest-value async input.

**Active next (ranked, goal-driven - see North-star; G3 first) — RE-RANKED by
the 42nd-session architect review (Log #42) and again in #46/#47 now that the
S0 GT exists and G0 landed.** The "detector v4 → normalise → learned gestures" order was NOT
adopted. Order = make the labels machine-readable → measure held-out → fix the
contact proposal where the loss is → pass-2 layers on real contacts → learn
last. One mechanism per session; each step's kill criteria are pre-registered.

- **G0 (worker) — [#47 DONE 2026-10-01] the P9–P33 contacts are
  machine-readable:** dialect-B `parse_contact_gt` + `scripts/build_match_contact_gt.py`
  → `ground_truth/20260920_match_contacts.json` (211 contacts P1–P33 on the
  match frame axis, 33 contact sheets). Gates met: P1–P8 field-identical
  rebuild, every contact line in `events`, switches after P7/14/21/28,
  parentheticals verbatim (`raw_line_no` is the only dev-GT difference, +3 from
  the owner's later header lines). Open point 24(a) closed.
- **G1 (worker) — [#48 DONE 2026-10-01] the first HELD-OUT contact score.**
  `scripts/score_heldout_contacts.py` + `docs/g3_heldout_p9_p33.md`:
  production F1 0.772 / class 0.590 / team 0.518; miss taxonomy 46 correct /
  57 wrong-label / 36 wrong-team / 44 missed; far serves **0/12**. The dev
  loss budget is re-ranked: the LABEL bucket dominates held-out (31%), not
  proposal (24%). Stage waterfall deferred (needs a production match diag
  dump). This is the baseline every future mechanism must beat.
- **G2 (owner decision, ANSWERED #53 — pick the operating point).** T5
  (tracker admission), R1 (departure gate), S1 (looming) and pass-2 are all
  refuted; the 12 held-out far-serve contacts are now measured at **0/12**
  (baseline F1 0.772), so the choice could be made on data.
  **[#53 the far-serve lever is ANSWERED: it is neither "detector mining" nor
  another px-space contact-proposal mechanism — the ball IS detected, so the
  lever is a STRUCTURAL proposer over the raw detections with the opener gate,
  scoring 14/17 at precision 1.00, 15/17 at 0.94, 17/17 at 0.90
  (`docs/g4_structural_serve.md`). The G1 data's other lead (the gesture-label
  bucket, `overpass` 0/18) was diagnosed at #50 and remains an owner/architect
  call.]** **[#50: the gesture-label lead was
diagnosed for its worst class — the ball-width net-crossing signal for
`overpass` is REFUTED (3/18, no separation; not detection; next-team signal
unusable). So the overpass lever is now an owner/architect call on a
gesture/touch-rule + possession-signal change, not a ball-geometry threshold;
the rest of the label bucket (spike→block 7, set→dig 10, …) is still
diagnosed only at the confusion-matrix level.]** **[#51: the owner asked for the EVIDENCE to be emitted
instead of choosing: G4 delivers `far_flight` + `runway_occupant` +
`serve_candidate` (default OFF, `docs/g4_serve_events.md`). Scored on the 17 GT
far serves: runway 15/17, conjunction 3/17 at +-15 f (3/12 held-out) vs
production 0/12, with 1 FP in 24 non-serve control windows. The remaining choice
is 'consume the events post-hoc (S4)' vs 'keep pushing the ball side'.]**
- **G4 (RESOLVED #53, was: consume the serve events or push the ball side).**
  `src/analysis/serve_events.py` + `docs/g4_serve_events.md` emit
  `runway_occupant` / `far_flight` / `serve_candidate` (default OFF,
  `--serve-events`, inert otherwise). The owner's "check all in the order you
  stated" resolved both branches at once: pushing the ball side is **refuted**
  (M1: the far ball is detected in 14-31 of 31 frames at every serve — the
  "1 frame in 4" premise was a COCO-detector artefact and the "0-1 tracked
  frames" figures are TRACKER counts), while consuming the evidence is **now
  strong enough to build on**: with the opener gate the existing conjunction
  reaches 11/17 at precision 1.000, and a structural proposer over the raw
  detections reaches **14/17 with zero false positives** (union of the two
  zero-FP rules), or 15/17 at 0.94 / 17/17 at 0.90
  (`docs/g4_structural_serve.md`). Any consumer ships post-hoc as a serve
  EVIDENCE record, never as a label (pass-2 proved the label-source route at
  0/5 with 3 correct dig labels broken), with F1 0.772 / far-serve 0/12 as its
  baseline and P9–P33 as the held-out check. Re-score with the SEEK-FREE
  `scripts/probe_serve_events_seq.py` (the old `score_serve_events.py` seeks
  and is +-30 f unreliable) and sweep the rule frontier with
  `scripts/sweep_structural_serve.py`.
  **[#51 the WHY is measured too — `docs/g4_far_serve_failure_mode.md`: the
  contact GEOMETRY is the signal that does not switch. Far-side contact tests
  reach 0 of 4 (no lowest vertex, 0 px horizontal flip, dvy +4 vs <= -8, dvx 2
  vs >= 12, fed ascent +0..+4 vs >= 10) while near-side control reaches them and
  fires 5/10. **Option (a) SCALE-AWARE geometry was tried and is REFUTED**
  (#52): +1 far contact (held-out only, 0 on dev) for +4 control false
  positives, precision 0.40 -> 0.33; a mirror arm adds nothing. Required-k
  arithmetic in `docs/g4_scale_aware_geometry.md`: bounce would need 8.2 ball
  widths, redirect 2.4 (near: 4.5 / 1.3), and the k~0-reachable tests are
  reachable only because they stop discriminating. So option (b) is what
  remains: consume `serve_candidate` post-hoc as evidence (never as a label),
  plus the ball-PRESENCE question (8/17 far serves have no usable vertex).]**
- **G3-footage (worker, parallel, cheap) — first run of the new practice video**
  `20290928_entreno_vall_dhebron.mp4` (`make run VIDEO=…`, ~21k frames, the
  fastest full video here): sanity-check the pipeline on a second recording
  session at a known venue, then use it as the **second fold** for anything
  leave-one-session (T12's precondition) and as the side-change subject IF the
  owner dictates which points had side switches (open point 2). Do not spend
  effort here before G0/G1 — it has no labels.
- **S0 (OWNER, async, no code) — [#46 LANDED]** held-out contact GT for match
  P9–P33: **DONE** — the owner appended ~200 contact lines to
  `ground_truth/20260920_match_ari_joan_contacts_p1_p8.txt` (2026-09-30) in a
  second dialect, covering the 12 far-serve points. Not machine-readable yet
  (0 of the new lines parse; the worker half is G0 above).
- **S0b (worker, script only) — [#45 DONE 2026-09-30]** score `actions_pass2`
  at CONTACT level against the dev GT P1–P8 with `scripts/evaluate_timed.py`
  (NOT `--autonomous`: pass-2 carries owner inputs; the GT-input audit is
  recorded instead): `scripts/score_pass2_contacts.py` +
  `tests/test_pass2_contact_score.py` + `docs/g3_s0b_pass2_contact_score.md`.
  Result: far serves **0/5**; GT serves matched **1/8**; pass-2 contact F1
  0.597 → 0.604 with class accuracy 0.706 → **0.562** (3 correct dig labels
  broken, 1 TP lost). Scope must be the point windows padded ±90 f, and the
  perception arm must reproduce the T4 baseline (asserted in-script).
- **S1 (diagnose only, no `src/`) — [#44 DONE 2026-09-30, REFUTED at kill 2
  (no separable `L` gap; see Log + Open point 22); S2 NOT triggered] far-side
  serve looming probe:**
  `scripts/probe_far_serve_looming.py` + `docs/g3_far_serve_looming.md`. In the
  new-rally state (no emitted contact within `RALLY_RESET_GAP`), a ball segment
  whose onset width is ≤26 px (below the 26–35 abstain band) and whose
  L = OLS slope of ln(bbox width) vs time in SECONDS over [onset, onset+0.5 s]
  is high = candidate far serve, contact placed at onset (T5 measured first
  sighting 2–4 f after contact). Secondary feature declared NOW: nearest
  far-team player `is_behind_baseline` at onset. L* = midpoint of the empty gap
  between the lowest dev far-serve L and the highest dev new-rally non-serve L.
  Inputs = existing dumps: `output/t4/dev_diag.jsonl`,
  `output/g3r1/match_bw03_diag.jsonl` (replay its `ball_dets` through
  `BallTracker` first; require `locked` + centre identity on 26068/26068
  frames or stop), `output/g3/e1..e7_diag.jsonl`. Base arm must reproduce T4
  (P 0.586 / R 0.607 / F1 0.597; the 5 far serves die at `3_candidate`).
  **KILLS:** (1) <4/5 dev far serves (f210/880/2154/3038/4770) have ≥5 far-band
  sightings in [c, c+0.5 s] → the far flight is undetected and the lever flips
  to detection (targeted far-flight mining for v4, not a general v4); (2) no
  empty gap on dev, or gap ratio <1.5×; (3) any fire on e1–e7 (all entreno
  serves are near-side); (4) match P9–P33 with L* frozen: must fire in ≥9/12
  far-serve windows before the pass-2 reception, and precision ≥0.75 over all
  new-rally fires (fires on the 7 owner-FALSE serve frames / 4 OFFGAME ranges
  are FPs). No `PlayerTracker` is created ⇒ no `cv2.setRNGSeed` needed.
- **S2 (OWNER-GATED, only if S1 survives) —** new contact band in
  `src/recognition/action_classifier.py` next to `_reentry_contact`, config key
  + drift-guard rows. Gates: dev recall ≥0.714 (+3/28) with precision ≥0.586;
  e1–e7 byte-identical (`scripts/compare_runs.py`, baselines from untouched
  HEAD, `--device cpu`); match action-set diff = additions at fire frames only;
  pass-2 chain holds (17/17 owner verdicts, 31/33 points); ≥9/12 held-out far
  serves within tolerance vs the S0 GT. Refuted ⇒ `git checkout 185c6f0 --
  src/ tests/test_config_drift.py` and the band moves to a default-off
  `scripts/*_harness.py` subclass (T5/R1 precedent).
- **S3 (worker) — [#49 DONE 2026-10-01] pass-2 squad/side-switch layer (open point 21.4):** squad = side ×
  switch parity (beach rule: switch every 7 points), cross-checked by all four
  players crossing the net in dead time; target exactly the 4 GT switches
  (after P7/14/21/28). SHIPPED: derived `[7,14,21,28]` exact; `pass2_squad`
  on 207/207 actions; **G1 team 0.518 → 0.755 squad-mapped** (the raw number
  was a side-vs-squad confound), 34 genuine side errors; player-crossing
  evidence-only. Deterministic pass-2, independent of S1. Consume in S4.
- **S4 — [#54 the serve-EVIDENCE half is DONE] 21.3 winner/outcome layer → 13 (ace / serve fault / assist) → fantasy
  module + points table (14e)**, consuming `actions_pass2` after S1–S3 so aces,
  faults and receptions hang on real serve contacts. **21.3 DONE (#43)** as a
  pass-2 script: `scripts/resolve_point_winners.py` + `tests/test_point_winners.py`
  + `docs/point_winner_layer.md` — 33/33 decided, **18/33 (54.5%)** vs the 33
  dictated winners; miss sources = terminal-touch attribution (8, point 22),
  ball-death in/out (3), serve-team overrides (3); GT-bought 21/33 explicitly
  not inherited. The remaining S4 work (13 ace/fault/assist + fantasy module)
  still waits on S1–S3 for real serve contacts and squad letters.
- **Round-3 owner queue (no code, unchanged):** P32's serve, 6928A's verdict,
  P18–P20 anchors, ep45's nature, P23 17159A + P31 22873A team-fix
  confirmation — each flips one flag in `serve_relabel.json` when ratified.
- **Queued behind S1:** the reach-gate bucket (5/28: P5 f2575, P7
  f3747/3782/3950/4002 — near-side, so tracking diagnosis BEFORE any
  normalisation); the label bucket (4/28, 3 of them overpass — cf. open point
  9); e4/e5/e6 re-adjudication sheets; the e2 production-vs-script F1 gap
  (0.400 vs the 0.571 script record, pre-existing, f167 gesture flip).
- **DEFERRED, each with an explicit trigger (do not start earlier):**
  detector v4 → second-venue footage exists OR S1 kill 1 fires; T9 PTS time
  windows → mandatory before any footage outside 25–31 fps; T7 perturbation
  suite / T10 camera profile → before a second camera; T6 feature sidecar →
  when T12 fires (`--diag-dump` covers every probe until then); T8 width-band
  `unreliable` state → prerequisite for any departure-gate (R1) revisit, its
  "team overrides" motivation RE-SCOPED (see Learnings); T12 learned
  contact/gesture head → only when contact GT spans ≥3 recording sessions,
  validated leave-one-SESSION-out (e1–e7 = one fold); R2 calibrated confidence
  (REFUTED at diagnosis, 41st session) → parked behind its owner-gated
  preconditions (`docs/g3_r2_confidence_calibration.md` §6; S0 supplies
  precondition 1). `track_frac_15f` remains the one within-clip-stable ordinal
  (review-UI flag candidate, not a calibrated replacement).

## Archived 2026-10-02 (#58): header paragraph #55, verbatim

**#55:** 2026-10-02 (fifty-fifth session, **planning only: the
serve-reliability plan and a course correction**, `docs/serve_reliability_plan.md`,
open point **30**). Measured honestly, serves are unreliable on BOTH sides. At
contact level (±15 f, match P1-P33) the production stream gets near **8/16**, far
**0/17**, with 12 false serve emissions (recall 0.24, precision 0.40). The far-only
evidence layer's "14/17 at zero FP" is **in-sample**: the operating point was swept
on all 17 far serves, and its held-out binding is **4/12**. The far-serve track had
been optimising a proxy (a frame-exact far contact in the action stream) on one
match. The plan replaces it with a per-point **serve record** covering both sides
(time, side/squad, server, outcome), built post-hoc from the existing evidence plus
two signals never used before: the **audio track** (real AAC in every video, never
read) and the **beach serving rules** (decoded jointly across the match). It also
asks the owner for cheap serve-only GT on one new session.


### Archived 2026-10-04 (superseded by #80 rewrite)

**The post-hoc interpretation layer is RATIFIED and its first
instrumentation step is SHIPPED (#77, owner 2026-10-04; open point 9).** The
owner ratified overpass as a POST-HOC read of WHERE an action lands (a dig
and an overpass are the same contact kinematically; spike-on-2 vs overpass is
the hard case to separate) and possession-first attribution for ambiguous
touches (who touched first decides the side; both proposals stand on ONE
substrate — a per-rally ball-fate timeline). Shipped this session,
display-only: per-frame ball-side possession (near/far/last-known) +
net-crossing flag as a live-debug label (`possession: NEAR|FAR` + `CROSSING`)
via a new always-on pure observer in `process_frame`
(`src/analysis/ball_side_possession.py`, bands per video from the
calibration via the owner's pinhole `d_net` formula; recorded in the diag
dump as `ball_possession`, schema v2). Next in the ratified sequencing:
**C1** fitted ball-fate measurement (pre-registered PASS/FAIL at the
m ≤ 2k−12 budget) → **C2** possession timeline reliability → **C3** overpass
relabel scored once on the held-out → **C4** ambiguous-touch reattribution.
RECALIBRATED #78+#79 on owner feedback: measured width regimes (probe
`scripts/probe_possession_feedback.py`) are near flight 1.49-1.6×d_net,
net-plane rest/tape AND blurred far flight BOTH 1.0-1.35×d_net
(indistinguishable), far ground 0.5-0.8×d_net — shipped evidence is
ASYMMETRIC: NEAR commits on the rolling max(12 measured frames) ≥1.45×d_net
(occlusion is momentary smallness), FAR on max ≤0.85×d_net OR ≥4 of the
last 12 measured frames ≤0.85×d_net (far rallies FLICKER 0.66-1.14×d_net;
persistent smallness is the far signature). Verified on the owner's windows

## Archived 2026-10-05 (#83): header paragraph #81 + the #81 identity block of "Where we are", verbatim

**Last updated:** 2026-10-05 (eighty-first session — **#81: player ENROLLMENT
pre-pass (E1) + squad colours (E3) SHIPPED — stable P1A/P1B/P2A/P2B labels and
team-blue/team-red boxes, display-only, tracking byte-identical.** New
`src/tracking/player_enrollment.py`: sequential decode of the first 600 frames
(detector every 5th, foot-strictly-in-court only — §9, no seeks), greedy ONE-TO-ONE
chains (120 px gate + torso-HSV correl tie-break), fragment merge (gap ≤60 f, correl
≥0.45), 4 most persistent chains (≥8 obs) → majority-side squads (near = squad 1),
left→right slots A/B, averaged-signature references. `PlayerTracker.set_enrollment`
attaches labels in-stream (greedy best-unclaimed ensemble similarity > 0.35, sticky
per tid, survives gallery retire+restore, cleared on track death); every tracked player
dict + every ACTION now carries `player_label`/`squad`/`slot`. Overlay: 4 squad colours
(blue clear/dark, red clear/dark) follow the SQUAD not the side — stable through side
switches; fallback = legacy green `P<tid>`. Wired into batch + BOTH live paths via
`FrameProcessor.enroll_from_video` before the loops; 7 new `player_enrollment_*` Config
keys, drift-guard extended. **Gate PASS:** fresh A/B on all 7 entrenos — action F1
Δ = 0.000 on 7/7, tracker snapshot streams byte-identical, 56/56 actions labelled
(e1: 4 refs from 294 samples/8 chains, labels by frame ~8 at sim 0.51–0.93). Suite
**1549** (+24). e2's recorded 0.571 reads 0.400 on BOTH fresh arms — pre-existing
fresh-run variance in the base, rule 'compare A/B, never vs recorded' extended to e2.
Next: E2 identity-drift + side-switch observers (display/diag only, OWNER GATE);
owner visual pass on live debug pending.)

**#81 SHIPPED: player-enrollment pre-pass (E1) + squad colours (E3) — the first
half of the owner's player-identity request (m00001, plan m00055/m00056).** Stable
labels **P1A/P1B (near/squad 1) and P2A/P2B (far/squad 2)**, slots left→right at the
earliest simultaneously-observed frame; **colours follow the SQUAD, not the current
side** (blue clear/dark + red clear/dark), so a side switch cannot recolour a player.
Mechanism (display-only by design — the GT-validated bootstrap/admission machinery is
untouched, enrollment only supplies reference signatures + a tid→label map): sequential
decode of the first 600 frames, player DETECTOR only every 5th frame, foot-strictly-
in-court detections, greedy ONE-TO-ONE nearest-neighbour chaining (120 px gate +
torso-HSV correl tie-break; each chain takes ≤1 obs per sampled frame so two players
projecting close cannot feed one chain), occlusion-fragment merge (gap ≤60 f, endpoint
≤120 px, cross-corr ≥0.45), the 4 most persistent chains (≥8 obs) become averaged-
signature references; <4 chains or no 2+2 near/far split → no enrollment, legacy green
`P<tid>` fallback. In-stream: labels attach greedily (best unclaimed ref, ensemble
similarity > `player_label_min_similarity` = 0.35), sticky per tid, survive
retire-to-gallery + restore (same tid → same label → same colour, the owner's core
ask). Every tracked-player dict and every ACTION carries `player_label`/`squad`/
`slot`; `pipeline_output.json` actions gained `player_label` (additive; snapshots
unchanged). **Validation:** fresh A/B both arms, all 7 entrenos — action F1 Δ=0.000
on 7/7, tracker snapshot streams (tid→frame/bbox) byte-identical, 56/56 actions
labelled; suite **1549** (+17 enrollment, +7 squad-colour tests). **E2 is next
session, owner-approved:** identity-drift observer (sustained signature mismatch vs
the enrolled reference) + side-switch observer (sustained foot-side ≠ squad side),
display/diag only, owner gate before anything acts. Owner visual pass on live debug
(squad colours + labels) pending. The serves track below remains the standing record.

Open point 2 as it stood before the #83 rewrite, verbatim:

2.  **Side-change survival (player identity) — [UPDATE #81: E1 enrollment + E3
    squad colours SHIPPED (labels P1A/P1B/P2A/P2B, squad-stable colours, actions
    carry player_label; tracking byte-identical, gate ΔF1 0.000 on 7/7 entrenos).
    E2 NEXT SESSION, owner-approved scope: identity-drift observer (sustained
    signature mismatch vs enrolled reference) + side-switch observer (sustained
    foot-side ≠ squad side) — display/diag only, OWNER GATE before acting. The
    GT-pass blocker below still stands for VALIDATING drift/side switches on real
    match footage.]** The roster machinery SURVIVED the full match: ids 1-4 only, 0 ghost/
    recycled ids, swap-rate 0.00, team acc 97.9%, coverage 3.28/4,
    dead-time persistence 3.05/4. BUT 46 resurrections and a visually
    confirmed mid-rally identity hop (id2 woman→man, both in-court —
    `output/match20260920/sheet_id3_cross_f1250-1350.png`; the in-court
    preference cannot separate them) and 12 per-episode all-4 side-mapping
    changes vs ~5 official switches. **Next:** GT pass on a few points
    around an official switch to measure hop rate → then judge the
    dead-time gallery horizon (18a lever) vs a stronger appearance
    tie-breaker. Not blocked by 22 (tracks dump is ball-independent).

## Archived 2026-10-05 (#84): header paragraph #83 + the #83 identity block of "Where we are" + open point 2 as of #83, verbatim

**Last updated:** 2026-10-05 (eighty-third session — **#83: side-switch-aware
TEAM IDENTITY RESOLVER shipped (output labels only; tracking byte-identical by
construction).** New `src/tracking/identity_resolver.py` (`TeamIdentityResolver`)
re-derives P1A/P2A/P1B/P2B every frame from the structural fact that teammates
share a side: (1) ORIENTATION (which squad is near) by a one-sided CUSUM over
per-body evidence with a 900 f minimum dwell, labels withheld while in doubt;
(2) within-side slots by per-tracklet evidence EMA + hysteresis + elimination.
Evidence = impostor-normalised DISCRIMINATION + same-view FIT, both calibrated on
the video's own enrollment samples (no venue/kit constant); background-weighted,
resolution-normalised part histograms (H x S + achromatic V) + lateral-scale
height; each player LEARNS the view it was not enrolled in after a confident flip
(anchors never replaced). The #82 resolver keeps running only to feed the
tracker's enrollment guards. Synthetic validation (drawn near/back vs far/front
players, scrambled ids): switches flip in ~10 frames with ZERO wrong labels, 3
consecutive switches, no flip through occlusion, silent teammate swap fixed in
≤4 f. NOT yet run on real footage (no video in the cloud session) — owner runs
`scripts/probe_identity_switches.py` on the 20260920 match next. Suite **1475**
(+30). Config `player_identity_mode` ("team"/"legacy") + 3 CUSUM keys.)

**#83 SHIPPED: TEAM IDENTITY RESOLVER — the owner's side-switch request (labels
must find the same person again after a switch; a few wrong/blank frames are
acceptable, actions are ~10% of frames).** Identity stack today, all output-only
(no tracking decision reads it): E1 enrollment pre-pass (#81) → 4 references,
now also carrying per-sample identity descriptors + heights → `TeamIdentityResolver`
(#83, `player_identity_mode: "team"`, default) stamps `player_label`/`squad`/`slot`
on tracked players and actions; actions take the label at their CONTACT frame
(`label_for(tid, frame)`, 900 f history), falling back to the emission-time label.
The #82 per-frame resolver still runs and still writes `_track_labels`, which ONLY
the tracker's enrollment guards read — so tracking is identical in "team" and
"legacy" modes (unit-pinned). Mechanism: orientation CUSUM (threshold 40, drift
0.5, min dwell 900 f; doubt at 25% of the threshold or one frame with mean swap
advantage ≥3 over ≥2 bodies → labels blank, never wrong); within-side slots by
EMA evidence (+1 hold bonus, −1 hold floor, quick-EMA hold break for overlap
swaps, 5-frame claim delay, elimination only with a decided partner); evidence
`e = z + f` (z = vs all other players' samples in both views, f = vs the player's
own same-view samples, capped +1); learning only when settled, isolated
(IoU < 0.05), in court, pair margin ≥2. Eligible bodies = in court (+16 px
slack) or in a serve zone (the server). **Validation status:** synthetic only —
the real-footage gate is the owner's run of `scripts/probe_identity_switches.py`
(one sequential production pass, team vs legacy labels side by side, contact
sheets rows = P1A..P2B, and with `--contacts-gt
ground_truth/20260920_match_contacts.json`: orientation at all 184 GT contacts,
one flip per GT switch window after P7/P14/P21/P28, action-label squad accuracy
team vs legacy). Entreno A/B for action F1 is unchanged by construction (labels
never reach the classifier) but a fresh run is still owed per §1. Open risks,
unmeasured: cross-view similarity on real far players (weak sims 0.3-0.6 in #82),
lighting drift over a long match, same-gender teams with similar kit.

2.  **Side-change survival (player identity) — status: BUILT, awaiting the
    real-footage gate (#83).** Problem: labels mixed after side switches (#82's
    resolver had no team constraint, position continuity locked swaps in, and
    enrollment only ever saw squad 1 near / squad 2 far). #83 ships
    `TeamIdentityResolver` (orientation CUSUM + within-side slots + per-video
    calibrated evidence + learned second view), output labels only. Prior
    roster facts stand (full match: ids 1-4 only, swap-rate 0.00, 46
    resurrections, a mid-rally id hop f1250-1350 — the resolver is designed to
    absorb hops, not prevent them). **Next:** owner runs
    `scripts/probe_identity_switches.py <20260920 match> --contacts-gt
    ground_truth/20260920_match_contacts.json`; pre-registered reading: PASS =
    4/4 switch windows ok, 0 stray flips, orientation wrong at 0 GT contacts
    outside the first ~5 s after a switch, team-resolver action squad errors <
    legacy's, contact-sheet rows one person each. Then entreno A/B (§1) and
    vall_dhebron only after its held-out lock is lifted. History:
    `docs/history/status_where_we_are_archive.md` (#83 section).

## Archived 2026-10-05 (#85): header paragraph #84 + the #84 identity block of "Where we are" + open point 2 as of #84, verbatim

**Last updated:** 2026-10-05 (eighty-fourth session — **#84: the team identity
resolver's FIRST REAL RUN (owner, 20260920 match) measured, diagnosed and the
orientation layer REDESIGNED.** Measured (`scripts/probe_identity_switches.py`,
26 061 f): **18 flips for 4 real switches** (3/4 windows right, P7 masked by a
stray flip just before it, 15 stray flips, dwell-limited every ~900-1500 f);
orientation at GT contacts 127/211 ok, 21 wrong, 63 withheld; action squad
team 71 ok / 28 wrong / 60 unlabeled vs legacy 83 / 71 / 5 (159 matched).
Owner's contact sheets: within-side labels right whenever the orientation was
right — every error sits in a wrong-orientation stretch, swapped whole-team.
Causes: the FIT term was 0 for views without native stats but negative for
the current hypothesis (a standing bias toward flipping), learned prototypes
fed back into the orientation (corrupted by wrong-orientation learning), and
the dwell clamp fired the moment the dwell expired. Redesign: orientation =
per-side, baseline-relative, directional CUSUM on FIXED anchors, both sides
required; within-side = always label (hysteresis + quick swap override scaled
by the video's teammate-margin spread, occluded/merged crops ignored);
learning feeds the within-side models only. New: feature dump
(`identity_features.npz`) + `scripts/replay_identity.py` so the decision layer
is re-tuned OFFLINE from one owner run. Synthetic: 3 switches, 0 wrong labels
outside teammate crossings. Suite **1477**. Next: owner re-runs the probe and
shares the dump.)

**#84: TEAM IDENTITY RESOLVER, round 2 — first real run measured, orientation
redesigned (the owner's side-switch request: labels must find the same person
after a switch; a few wrong/blank frames are fine, actions are ~10% of frames).**
Identity stack, all output-only (no tracking decision reads it): E1 enrollment
(#81, refs carry per-sample identity descriptors + heights) →
`TeamIdentityResolver` (`player_identity_mode: "team"`, default) stamps
`player_label`/`squad`/`slot` on tracked players and actions (actions at their
CONTACT frame via `label_for(tid, frame)`, emission-time fallback). The #82
resolver still writes `_track_labels`, read ONLY by the tracker's enrollment
guards → tracking identical in "team"/"legacy" (unit-pinned).

**First real run (#83 design, 20260920 match, owner):** 18 flips for 4 switches
(P14/P21/P28 windows right; P7 masked by a stray flip at f3743; 15 stray flips
in both orientations, spaced by the 900 f dwell); orientation at GT contacts
127/211 ok, 21 wrong, 63 withheld; action squad 71/28/60 (ok/wrong/unlabeled)
vs legacy 83/71/5. Contact sheets: every error is a whole-team swap inside a
wrong-orientation stretch; within-side labels right otherwise. Diagnosed:
(1) FIT term 0 for views without native stats vs negative for the current
hypothesis → standing bias to flip; (2) prototypes learned under a wrong
orientation fed back into the orientation statistic; (3) the dwell clamp held
the CUSUM at threshold and fired on dwell expiry.

**#84 design:** orientation statistic per side `x = best squad-1 − best squad-2
similarity` on FIXED anchors only; per-orientation per-side levels learned
online (warm-up 100 obs, EMA α 0.002 while in the noise band); directional
standardised CUSUM per side (drift 0.5, threshold 25, both sides required,
min dwell 1500 f); a new orientation's baseline is reused if seen before, else
seeded from the post-change run (u ≥ 1); doubt (labels withheld) at half the
threshold on both sides or one frame at the clip on both. Within side: slow +
quick EMAs of similarity to each player (anchors + view-learned prototypes +
height), better permutation with hysteresis 0.5 and quick override 1.0 per
clean body, both in units of the video's RMS teammate margin; occluded/merged
crops ignored, merged same-side pairs withheld; stranger = best similarity 4
spreads below usual. Learning only while settled; never read by orientation.
**Validation status:** synthetic only for #84; the real-footage gate is the
owner re-running `scripts/probe_identity_switches.py ... --contacts-gt
ground_truth/20260920_match_contacts.json` (now also writes
`identity_features.npz`), after which `scripts/replay_identity.py` re-scores /
re-tunes OFFLINE. Entreno A/B owed per §1 (action F1 unchanged by
construction).

2.  **Side-change survival (player identity) — status: round 2 BUILT (#84),
    awaiting the owner's re-run.** #83's first real run: 18 flips for 4
    switches, orientation wrong/withheld at 84 of 211 GT contacts, action
    squad 71 ok / 28 wrong / 60 unlabeled (legacy 83 / 71 / 5); within-side
    labels right whenever the orientation was. #84 redesigns the orientation
    (baseline-relative per-side CUSUM on fixed anchors, both sides) and the
    within-side step (always label). **Next:** owner re-runs the probe (same
    command; it now writes `identity_features.npz`) and shares the dump +
    `identity_probe.json`; tuning then happens offline with
    `scripts/replay_identity.py`. PASS reading unchanged: 4/4 switch windows, 0
    stray flips, orientation wrong at 0 GT contacts outside ~5 s after a
    switch, team-resolver squad errors < legacy's, contact-sheet rows one
    person each. History: `docs/history/status_where_we_are_archive.md` (#83,
    #84 sections).
