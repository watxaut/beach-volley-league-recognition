# STATUS.md archive — Log entries 2026-08-14 → 2026-09-27 (twenty-first session onward)

> Provenance: the detailed session log entries that used to live in
> STATUS.md's "Log" section, moved here VERBATIM on 2026-09-27 when the live
> Log was reduced to the most recent sessions. Entries are newest-first.
> The compressed per-session summaries live in
> `status_where_we_are_archive.md` (same directory); the one-line-per-session
> index is in STATUS.md. Nothing was edited or deleted.

### 2026-09-27 (twenty-first session) — pi project default model set to zai/glm-5.3-flash (.pi/settings.json)
- **Harness config only** — no pipeline code, no GT. New
  `.pi/settings.json` sets `defaultProvider: zai` + `defaultModel:
  glm-5.3-flash`, overriding the user-level `~/.pi/agent/settings.json`
  (`zai/glm-5.3`) inside this repo only. Cross-checked before writing:
  `zai/glm-5.3-flash` was already in the user settings' `enabledModels`,
  and `~/.pi/agent/auth.json` authenticates `zai`, so no provider setup
  was needed. Rest of `.pi/` (prompts/) untouched. Running pi sessions
  need `/reload` or a restart to pick it up.
### 2026-09-27 (twentieth session) — e3 v3 drift FIXED without GT edits: the short-gap bridge now checks the normal path can actually host the touch

Owner brief: after the v3 swap e3 drifted (F1 1.0→0.667), the GT stays,
some contact "changes midpoint and then it starts going sideways" — fix
without regressions. Diagnose-first, one shipped mechanism.

- **Instrumentation:** production-parity ball-track dumps for e3 under
  both models (`output/diag_e3_v3_balltrack.py` →
  `output/diag_e3_balltrack_{base,v3}.json`, detector conf 0.15 + tracker
  parity + court bounds) and a SpikeAnalyzer transition tracer
  (`output/diag_e3_spike_trace.py`). The action diff against the gate
  artifacts localized the break to the missing f378/379 set, everything
  after being resolver cascade.
- **Three mechanisms found (A causes the F1 loss; B moot; C enrichments):**
  (A) v3's tracker accepts the true arc bottom f379 that base starved
  (moving bystander out-confd the ball 0.76 vs 0.70 → trusted coast; the
  in-gate ball was never tried); with the bottom real and v3 blind at
  f385-386, no frame can host the set — bounce@378 not-lowest, bounce@379
  right-sparse, drive@384 left3-empty — yet the bridge refused as "dense
  both sides". (B) ±px jitter tips |inc[0]| 18→21 over XREV_MIN=20 at
  f539, so the redirect test steals the kill → block gesture; harmless at
  touch 3 (the resolver's poke rule returns SPIKE — the `touch < 3` block
  guard is load-bearing). (C) v3 conf dip f613-618 → coast leaves the
  court-bounds box → re-entry window rejects the falling dets → track
  dies f623 → the dug→kill flush conversion loses the post-dig flight
  (f539 outcome reads dug vs GT kill; base read kill).
- **The fix (`src/recognition/action_classifier.py`, one mechanism):** the
  short-band dense-side refusal now requires `_normal_vertex_in_range(a0,
  c)` — a fireable normal vertex in the gap range — checked by reusing the
  normal tests factored out pure (`_normal_contact_at`); no duplicated
  thresholds, e6 f265 still defers. +2 tests
  (`test_short_gap_bridge_takes_seen_bottom_with_sparse_right`,
  `test_short_gap_bridge_still_defers_when_normal_vertex_fireable`),
  suite **448 green**.
- **Validation:** e3 v3 F1 **1.0** (14/14 matched; team 1.0, spike_type
  4/4, attack_zone 1.0, dug_zone 1.0; outcome 0.75 = Mechanism C's f539
  dug/kill; landing_zone 0.0 pre-exists in base — GT B8 vs emitted B7);
  e1/e2/e4/e5/e6/e7 action streams BYTE-IDENTICAL to the gate record
  (F1s 0.706/0.571/0.933/0.923/0.933/0.75; e6 team stays 0.857); base-
  weights rerun all 7 BYTE-IDENTICAL (neutrality proof). Artifacts:
  `output/e3_fix/`.
- **Match re-run (`output/match20260920_e3fix/`):** confirmed 31/33
  (0.939), 57 episodes, first-confirmed = GT pt 1 — identical to the gate
  record; actions 207 vs 206 (the +1 is a bridge-recovered dig in GT pt 5;
  all other labels unchanged: dig 84 / spike 45 / set 42 / serve 20 /
  overpass 9 / block 7). `match_points_eval.json` written.

### 2026-09-26 (nineteenth session, adoption leg) — v3 ADOPTED as production; owner feedback: far-side serves untracked (new open point 22); session closed

- **Adoption:** `models/volleyball_ball_best.pt` overwritten with v3
  (md5-verified byte-identical to `volleyball_ball_best_v3_r2.pt`); old
  production preserved as `models/volleyball_ball_best_v1_entreno.pt`; v2
  kept; owner's root drop removed (round-1 convention). Default loaders
  smoke-tested. models/ is git-ignored — the swap is STATUS-only in git.
- **Owner feedback recorded verbatim in open point 22:** far-side serves
  in the match appear untracked; entreno serves fine. Hypotheses + probe
  plan recorded there (v3 "other"-background weakness at the backdrop,
  serve count dip 28→20, entreno-tuned serve-zone admission, 25.7fps
  launch speed). No mechanism built — diagnose first.
- **Session state:** ball retrain thread (open point 20) CLOSED after two
  rounds; entreno re-adjudication (e3/e4/e5/e6) and point 22's probe are
  the queued follow-ups; open point 21 re-ranked (point-layer re-tune
  likely moot at 31/33).

### 2026-09-26 (nineteenth session, gate leg) — round-2 validation gate: v3 passes GT-frames / match / probe decisively, entreno drift-lock fails; adoption recommended with re-adjudication caveat

Owner trained r2 in Colab (fine-tune FROM production best.pt, 1441-image
zip); weights stashed as `models/volleyball_ball_best_v3_r2.pt` (production
UNTOUCHED). All four legs, three-way where it matters:

- **Leg 1 GT-frames (diag_gt_frames.py 3-way, 486 frames):** recall 94.2%
  (58.3 old / 57.8 v2), @0.4 precision 95.5% (39.9 / 25.3), dets 422
  (1750 / 3026 — noise gone), FP@0.4 18 (330 / 682; sky 11 / 31 / 236),
  blind recall 94.6% (57.1 / 58.0), TRUE-det conf sky 0.85 med 100% ≥0.4 /
  sand 0.81 med 93.5% ≥0.4. Valid-split tag updated to the current
  1441-pair split (216 valid — matches the Colab run's valid count);
  valid numbers comparable within-run only: 88.1% / 92.9%.
- **Leg 2 entreno A/B (output/retrain_eval_v3/, 14 runs, --ignore-player):**
  base leg reproduced the recorded F1s EXACTLY (0.706/0.571/1.0/1.0/1.0/
  0.933/0.75 — drift-lock reference good). v3: e1/e2/e6/e7 F1-exact;
  e3 1.0→0.667 (block FP, spike 2 FN, set churn), e4 1.0→0.933 (overpass
  FP — v2's identical failure), e5 1.0→0.923 (opening serve lost — v2's
  identical failure); e6 team 1.0→0.857 (NEW; one misattributed contact).
- **Leg 3 match (output/match20260920_v3/, ~40min run):** confirmed 31/33
  GT (0.939) vs 15/0.455 (v2) / 13/0.394 (base); episodes 57; 0 episodes
  before first confirmed (first-confirmed = GT pt 1); actions 206 (dig 83 /
  spike 45 / set 42 / serve 20 / overpass 9 / block 7) vs 104 / 90; serves
  20 vs v2's 28 / base 21 — the only match metric that regressed.
- **Leg 4 probe (diag_ball_probe_v2.py 3-way over the same 5 episodes):**
  tracked old→v3: ep02 6→28%, ep06 24→42%, ep12 4→2%, ep08 11→23%, ep35
  49→78% (flight 42→60%). ep35 sky cand conf med/≥0.4: 0.90/92 → 0.47/51
  (v2) → 0.85/99 (v3). Blind% UP everywhere (25→51 / 10→52 / 31→94 /
  16→58 / 20→20): the round-1 audit's "raw candidates were mostly sand
  noise" made visible — class (b) collapsed to 1-8%.
- **Verdict: 3/4 legs pass, decisively; entreno 4/7-exact vs the 7/7 bar.**
  e4/e5 failure modes are IDENTICAL across v2 and v3 (systematic to
  venue-matched retrains); e3's regression is v3-specific; e6's team flip
  is new and touches the safety-critical emitted-team signal. Production
  weights UNCHANGED. Recommendation recorded in open point 20: adopt v3
  (31/33 was unreachable tracker-side) AFTER the owner re-adjudicates
  e3/e4/e5/e6 against v3 streams — GT was dictated against base-model
  behavior, and base was half-blind.

### 2026-09-26 (nineteenth session) — round-2 rebalanced mining staged: 200 noise negatives + 150 sky controls, notebook switched to fine-tune-from-best.pt

Executing the round-2 spec from open point 20 after v2_match was rejected
(class (a) fixed, precision/sky/entreno regressions). No pipeline src
changes; one script extension + tests.

- **`--exclude-manifest` on `scripts/mine_ball_frames.py`:** a previous
  round's manifest excludes its same-class picks ±spacing from this
  round's pools (classes are deterministic, so cross-class collisions are
  impossible at the exact frame). `exclusion_zone()` pure helper + cap-0
  and round-2-caps contract tests (+6, suite **446 green**).
- **Determinism check came free:** the re-scan reproduced round 1's
  scanned-class counts EXACTLY (blind 1843 / low_sand 1407 / low_other
  1541 / sand_noise 1100 / sky_control 1233 / high_other 870 over 7994
  game_on frames).
- **Picks (caps hit exactly, span f240..f26004, 222MB, no exact
  collisions):** sand_noise 200/200 (pool 1100 → 449 available after
  excluding round-1's 60 ±5f) + sky_control 150/150 (1233 → 809 after
  round-1's 40). Blind/low classes NOT re-mined (round-1 GT fixed them;
  v2 kept the wins).
- **No pre-labels (`--no-prelabel`), README.md in the dir:** round-1
  audit — our ≥0.4 sky pre-labels sat on the owner's ball 3/77; the owner
  annotated without labels anyway. Noise frames are negatives by
  construction (owner boxes a ball if they see one); sky frames get the
  TRUE ball or null — the nulls are exactly the sky-FP negatives v2
  lacked (236 confident sky FPs at the 0.4 gate).
- **Recorded footnote:** 118/350 round-2 picks sit ≤5f from a round-1
  pick of a DIFFERENT class (noise and blind interleave inside rallies);
  accepted (different content), but remember if the valid split looks
  optimistic. The real gate remains the four-leg validation.
- **`notebooks/finetune_yolo_ball.ipynb` round-2-ized:** BASE_MODEL var
  defaults to the uploaded production `volleyball_ball_best.pt`
  (preserve the sky prior; round 1 from base yolov8n lost it),
  `"yolov8n.pt"` reproduces round 1; run/download renamed
  `volleyball_ball_r2` / `volleyball_ball_best_r2.pt` so production
  weights stay untouched for the A/B; recipe unchanged.
- **Handoff:** owner annotates the 350 → COCO export (dataset page —
  rapid download broken last time) → `import_roboflow_coco.py` →
  `prepare_dataset_for_training.py` → zip → Colab r2 (upload best.pt
  alongside the zip) → weights back → SAME four-leg gate.

### 2026-09-26 (eighteenth session, validation-gate leg) — candidate retrain measured on all four legs: class (a) fixed, precision/sky regress; REJECTED, round-2 spec recorded

- Weights: owner's Colab run stashed as
  `models/volleyball_ball_best_v2_match.pt`; production
  `volleyball_ball_best.pt` untouched. All artifacts git-ignored:
  output/retrain_eval/ (GT-frame eval + probe v2),
  output/match20260920_retrain/ (full run + match_points_eval.json).
- **GT-frame eval (new diag):** recall flat 58%, dets 1750→3026,
  precision 13.9→8.0%, @0.4 recall 52.5→55.4% / precision 39.9→25.3%;
  sand TRUE conf med 0.63→0.80. Valid-split (leakage-free, n=65):
  recall 50.8→47.7%.
- **Entreno A/B:** e1/e2/e3/e6 EXACT (0.706/0.571/1.0/0.933), e4
  1.0→0.933 (+FP overpass f386), e5 1.0→0.923 (opening serve f17 lost),
  e7 0.75→0.625 (f242 set lost, f440 dig gained). Team 1.0 ×7.
- **EVAL GOTCHA (permanent record):** the recorded action F1s require
  `evaluate.py --ignore-player`; with the default player matching,
  byte-identical streams score 0.933 vs 0.133 (GT player_id is a
  per-frame left-to-right index). Mirror the baseline invocation in
  every A/B.
- **Match:** confirmed 13→15 (0.394→0.455), actions 90→104, serves
  21→28; episodes 48→63, first-confirmed ordinal 4→7.
- **Probe v2:** blind% 25→2 / 10→3 / 31→19 / 16→15 / 20→9; ep35 sky
  med conf 0.90→0.47 (≥0.4: 92→51%); tracked 2→10 / 25→31 / 0→7 /
  4→11 / 47→46%.
- **Verdict: reject as drop-in.** Round 2 (owner + this gate):
  rebalanced mining (~200 pure negatives, ~150 sky positives; blind/low
  classes kept), optional fine-tune-from-best.pt, same four-leg gate.

### 2026-09-25 (eighteenth session) — retrain-mining shipped: 500 stratified match frames staged for the owner's Roboflow annotation

Open point 20's second half (detector retraining — class (a) is
unreachable by tracker-side gates). No pipeline src changes; one keeper
script + tests.

- **`scripts/mine_ball_frames.py`:** scans the GAME_ON ranges of a
  results_game_state.csv (default: the floors-ON rerun
  output/match20260920_lowconf/) with the production-parity detector
  (volleyball_ball_best.pt, conf 0.15, the _up1080 file, 30f
  static-suspect warm-up per range, det.reset() between ranges) and
  stratifies every frame with the probe's bg_class (kept byte-identical
  to diag_ball_probe_bgsky.py): blind / low_sand / low_other (cands but
  none ≥0.4, best non-suspect's bg) / sand_noise (suspects-only = hard
  negatives) / sky_control (≥0.4 sky-backed = regression guard);
  ≥0.4-non-sky frames are high_other — manifest-recorded, not mined.
  Sampling: seeded shuffle + greedy min-spacing (5f) per class; two
  decode passes (classify everything, then write only the picks).
- **Full-match scan (7994 game_on frames, 48 ranges): blind 1843 (23%),
  low_sand 1407, low_other 1541, sand_noise 1100, sky_control 1233,
  high_other 870.** Blind at 23% of ALL game_on frames confirms the
  retrain is load-bearing, not optional polish.
- **Annotation set (resources/frames/match20260920/, git-ignored like
  datasets/):** 500 JPG q95 (318MB), names
  20260920_match_ari_joan_lost_f<idx> (resolve_source_stem — no
  collision with the dataset's flat frame_XXXX namespace), spanning
  f297..f25991. Caps: 250 blind / 100 low_sand / 50 low_other / 60
  sand_noise / 40 sky_control (owner-ratified budget 500). Pre-labels =
  all non-suspect cands ≥0.15 in YOLO format (empty txt for blind/noise
  = negative unless the owner finds a ball); manifest.json carries the
  audit trail + the note that pre-labels are review-required.
- **Sanity before the full run:** smoke set (f3000-3400) end-to-end + a
  ±2-frame motion-support proxy on the smoke picks: 8/12 low-class
  picks supported (consistent with the sim's ~60%); blind picks show
  nothing at ±2 either — genuinely hard, human-only, as intended.
- **Tests:** tests/test_mine_ball_frames.py +16 (classify_frame
  admission order incl. suspect-vs-mover, 0.400 boundary, spacing/cap/
  determinism of pick_frames, game_on_ranges run extraction, 500-budget
  contract). Suite **435 green**. resources/frames/ added to .gitignore.
- **Handoff:** owner uploads images/ + labels/ together to Roboflow →
  reviews/corrects → exports YOLOv8 → merges into
  datasets/ball_detection/ → prepare_dataset_for_training → Colab
  fine-tune (notebooks/finetune_yolo_ball.ipynb) → validation-gate
  session on the new weights (entreno A/B drift-lock, match re-run +
  evaluate_match_points, probe re-run for class (a)/(b) shrinkage).

### 2026-09-26 (eighteenth session, annotation leg) — owner GT landed; retrain dataset merged + zipped; pre-label audit forces a diagnostic correction

- **Owner report:** the shipped pre-labels were mostly wrong → they
  uploaded images WITHOUT labels and annotated one by one in Roboflow.
  Version-page "rapid" download was broken; COCO export from the
  dataset page worked. 486/500 frames (14 lost: 6 blind/3 low_sand/
  2 low_other/2 noise/1 sky). Export images pixel-identical to our
  frames (diff 0.00, n=346) — same pixels, human labels.
- **Audit BEFORE the owner's explanation (kept for the record):** owner
  boxes vs pre-labels — low_sand 0/155 same-place, low_other 0/71,
  sky_control 3/77; then all "deleted pre-labels" made sense: labels
  never attached. **Correction that survives: raw detector precision on
  this venue is LOW (even ≥0.4 sky-backed picks mostly not the ball per
  human GT); the tracker's motion/geometric gates carry production;
  many probe class-(b) candidates were sand noise, not missed balls.**
  The floors mechanism keeps its validation (entreno-neutral, match
  actions +22%) because its picks are motion-gated — but re-read probe
  counts as noise-heavy. The retrain attacks precision AND recall.
- **Owner GT contents:** 423 boxes on 486 frames (208/244 exported
  blind frames now have a ball), 73 empty-label negatives, 6 degenerate
  <2px boxes dropped with report (click droppings). Box widths med
  ~25px, tail to 95px. One leftover empty Roboflow category mapped
  harmlessly (0 annotations).
- **`scripts/import_roboflow_coco.py`** (+5 tests, suite **440**):
  `_jpg.rf.<hash>` suffix strip → canonical names, COCO→YOLO, non-ball
  category aborts, collision refusal, empty labels = negatives,
  degenerate-box drop policy at 2px.
- **Merge + zip:** datasets/ball_detection/ = 1091 images (605 + 486);
  ball_dataset.zip 1.7G, 928 train / 163 valid (418/68 match).
  Gotcha: disk filled mid-prepare (Errno 28) — rm the partial
  yolo_dataset/ staging dir, rerun clean.
- **Next:** owner runs the Colab notebook on the new zip (T4, run all);
  weights return → validation-gate session (drift-lock, match re-run,
  probe re-run).

### 2026-09-24 (seventeenth session) — match GT transcribed + point evaluator; ball-recall probe indicts the 0.4 conf floor (blue-sky report confirmed)

Owner feedback on the first full-match run executed as a plan (GT infra →
ball probe → tracker mechanism → actions → points/winner/side-switch →
identity → landing confidence). This session: parts 1-2; no pipeline src
changes.

- **GT (committed):** scripts/parse_match_gt_text.py →
  ground_truth/20260920_match_points.json (33 points, final 21-12, winners
  BABABAABBBBAABAAAAABAABAAAAAABBAA, switches after 7/14/21/28; winners
  mechanical from the score table, descriptions verbatim; Team A/B = fixed
  squads). scripts/evaluate_match_points.py (count/confirmation/episode
  table/first-confirmed ordinal; winner+switch scoring declared NOT SCORED
  until those pipeline layers exist). tests/test_match_points_gt.py +18
  (suite 405 green). ground_truth/README.md documents match-points-v1.
- **Baseline:** 33 GT vs 39 episodes vs 14 confirmed (0.424); 7 episodes
  before the first confirmed → first confirmed ≈ GT point 8 (the owner's
  "P1 started around P10"). output/match20260920/match_points_eval.json.
- **Probe (diag_ball_probe_bgsky.py + ball_probe_bgsky.json):** per-candidate
  conf/size/stationary_suspect/background over ep02/ep06/ep12 (starved) +
  ep08/ep35 (controls): detector-blind 10-31%; conf-rejectable (cands
  present, none ≥0.4, lost) 33-68% — largest class; ≥0.4-yet-lost 5-24%.
  Sky-backed med 0.90 (92% ≥0.4) vs sand 0.20 (9%) vs other 0.22 (21%) —
  the "blue sky" report quantified. The 25.7fps tax NOT implicated.
- **Counterfactual (diag_lowgate_sim.py):** P2 (0.15 locked in-gate + 0.15
  motion-pair floor, non-suspect only) recovers tracked coverage to
  22/36/16/19/51% on the five episodes with flight ~flat; ~60% pick
  support, ~35% stranded-risk. Class (a) needs detector retraining — mine
  sand/building positives from this match next.
- **STATUS:** open point 20 indicted with next-mechanism spec; new open
  point 21 = the feedback backlog (emit candidates w/ confidence, action
  + point confidence, winner/score layer, side-switch layer + squad
  mapping + overlay label swap, persistent player numbers, landing
  confidence).
- **Mechanism SHIPPED (commit 2): BallTracker low-confidence floors**
  (ball_locked_low_conf_floor / ball_boot_low_conf_floor, 0.15 default,
  0=off; drift-locked ctor parity; +14 tests/test_ball_low_conf.py, suite
  419 green). Narrow zero-high-frames scope so the trusted coast stays
  byte-exact P0 (the sim's broader P2 recovered ~2-5pt more but reopens
  the e1-f77 distractor class — refused). Boot pairs may use low-tier
  sightings with identical geometric gates; re-entry waits never traded.
  **A/B:** fresh HEAD baselines first (lowconf_base; 6/7 byte-identical
  to the e15e set, e7 == ratified post-e15e stream); post: entreno evals
  FULLY NEUTRAL (0.706/0.571/1.0/1.0/1.0/0.933/0.75, team 1.0 x7); raw
  shifts confined to 1-frame/contact-kind/index inside gates (e7 dig
  f59→60, toward GT f61). **Match re-run:** actions 74→90, serves 13→21,
  first-confirmed ≈ GT pt 4 (was 8), ep f9150 confirmed; point count 13
  (flat — point layer now binding: 30fps windows on 25.7fps footage).
  **Game-state guard:** 10/13 vs a FRESH floors-off baseline of 11/13
  (the recorded 80.6% was stale — predates the session-7 ball rework);
  pt00 recovered, pt01-03 lost at boundaries; config-off escape hatch
  verified. Session D (point 21 item 1) re-tunes the point layer on both
  videos jointly.

### 2026-09-24 (sixteenth session) — cached `_up1080` inputs resolve the source-stem calibration

**Trigger:** live-debug on
`resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4` said the
court was not calibrated; the 720 original live-debugged fine.

- **Diagnosis:** `src.main` keyed calibration auto-detect on the RAW input
  stem — `..._up1080` → looked for
  `calibrations/20260920_match_ari_joan_lost_up1080.json` (missing), while
  `scripts/test_court_calibration.py` already stripped the suffix when it
  WROTE the calibration. One convention, two implementations, the reader
  was the broken one.
- **Fix:** `resolve_source_stem()` in `src/utils/video_upscale.py`
  (`re.fullmatch(r"(.+)_up(\d+)")` strip; plain stems unchanged, so
  `video2`/`warm_up` never match); used by `src.main`, the calibration
  script (dedupe), `dump_player_tracks` (auto-detect + output naming), and
  `test_{ball_tracking,player_tracking,action_recognition,pose_estimation}.py`.
- **Verified:** the `_up1080` file now resolves
  `calibrations/20260920_match_ari_joan_lost.json` AND `ensure_1080`
  passthrough keeps processing the same cached file; the 720 original
  resolves identically (no regression). Suite 387 green (+8).

### 2026-09-23 (fifteenth session) — first full-match run: points starve 14/≈39, roster holds, identities hop; ball recall indicted (point 20)

Diagnosis-only session on the 20260920 match (26,061f, ~25.7fps), owner GT
statement "final ~21-15, near team of the first point wins → ≈36 rallies".
All artifacts in git-ignored `output/match20260920/`: the batch run
(results CSVs, `pipeline_output.json`, 14 points, 74 actions, 13 serves),
the production-config tracks dump + `analyze_tracking.py`, a
production-parity ball-only pass, `diag_match_analysis.py`, and the
ratification sheets (`sheet_id3_cross_f1250-1350.png` — the confirmed
identity hop; `footy_timeline.png`, `footy_w*.png` — band
memberships).

- Episode layer RIGHT: 39 GAME_ON episodes ≈ 36 rallies. Point layer
  starved: 14 confirmed (needs `point_min_actions=2`; 17 episodes emit 0-1
  actions), 15 episodes truncate <120f — ball track dies mid-rally. Ball
  tracked 20.6% of all frames; 40-60% inside healthy episodes. 8 confirmed
  points contain no serve → fragments. Full numbers in the fifteenth-session
  Where-we-are block; mechanisms to probe ranked in open point 20.
- Players: ids 1-4 only, 0 recycled id NUMBERS, swap-rate 0.00, team
  accuracy 97.9%, 3.28/4 in-play coverage, 3.05/4 dead-time persistence;
  46 resurrections + visually confirmed mid-rally hop (id2 woman→man, both
  in-court); 12 per-episode side-mapping changes vs ~5 expected switches.
- No src/config changes; nothing to A/B. Next session: point 20's separation
  probe (raw candidates vs tracker decisions on truncated episodes), then
  point 2's GT pass around an official side switch.

### 2026-09-23 (fourteenth session, round 2) — ball-width band VALIDATED on the upscaled 20260920 video

- Probe (`output/diag_ball_widths_20260920.py` + `_followup.py`, results in
  `output/diag_ball_widths_20260920/`): production-path ball detector
  (fine-tuned model, conf 0.15, auto-imgsz) sampled every 10th frame of the
  `_up1080` cache, widths labeled by geometry (NEAR: below midcourt-ground
  line +25px, contamination-free; FAR*: above it −180px, conservative —
  near-airborne balls leak in with LARGE widths).
- **First read was a false alarm:** NEAR-labeled widths median 19px looked
  catastrophic. Conf-stratification + a 24-crop contact sheet resolved it:
  the sub-0.4-conf detections are NOT balls — this venue's sand fires the
  model on boundary lines, footprints and shadows. Real balls (conf≥0.5):
  NEAR med 36, p25–p95 36–55 (validated band 30–55 ✓); FAR med ~22–25 with a
  physics ceiling at the net-line depth (~24px ball + blur slack ≤ ~30) —
  far→near misreads impossible, near-net near balls abstain exactly as
  designed. 41% "FAR* in abstain band" is the near-airborne contamination
  upper bound, not a real rate.
- Calibration overlay checked: clicks sit on the playing lines (entreno
  convention). px/m vs entreno: near 224 vs 238 (−6%), net 114 vs 124 (−8%),
  far 70 vs 86 (−19%) — implied ball sizes 47/24/15px vs entreno 50/26/18:
  same regime, marginally more abstain-side at the net. The upscale did its
  job; no threshold changes made (26/35 stay untouched).
- Residual (open point 19(d)): sand-noise rate ~2.2 det/frame at conf 0.15 —
  tracker's motion gates own it as at entreno; full pipeline run still owed
  before trusting end-to-end attribution.

### 2026-09-23 (fourteenth session) — 20260920 match intake: one-time sub-1080p ingest upscale

- New footage: `resources/full_videos/20260920_match_ari_joan_lost.mp4`
  (1280x720, ~25.7fps effective, 26,061 frames, points only, SIDE SWITCHES —
  first real match; open point 2 unblocked). No GT yet.
- Diagnosis (see Where we are): 720p breaks ~20 hardcoded 1080p-px constants
  downstream of detection (YOLO imgsz is fixed, so detection is unaffected);
  worst is the ball-width side signal (thresholds 26/35 land inside the
  ×2/3 near-ball range).
- Shipped: `src/utils/video_upscale.py` (`ensure_1080`: pass-through at/above
  target; one-time ffmpeg Lanczos x264 CRF 18 `-vsync 0` transcode to
  `<stem>_up1080.mp4` next to the source; atomic rename + frame-count parity
  gate; cache-hit reuse), config `upscale_to_height: 1080`, hooked in
  `src/main.py` before batch AND live-debug (parity rule), calibration/output
  naming keyed on the source stem. Suite 379 green (+4).
- Verified on the real file: 1920x1080, 26,061 frames (decode-count parity
  vs source), fps preserved 25.67, 6.5min one-time, cache hit 0.01s.
- Deferred → new open point 19 (fps 25.7 vs 30; first full run unvalidated;
  test scripts bypass the hook).

### 2026-09-19 (thirteenth session, round 2) — f316 GT slip ruled and folded

- Owner ruling on output/e15e/reratify_e7_f315_team.png: contact on the FAR
  side; P2B (yellow) far from it; P4 really NEAR team (stamps flap B
  mid-jump — airborne feet); the net blocker is the FAR-side player; the
  P1/P3 boxes overlap (occlusion) with P1 also very close to the ball →
  toucher = P1 (track 1), team B = the pipeline's emission, unchanged.
- GT fold: f315 dig team A→B, team_in_possession→B, provenance note
  recorded. e7 eval: F1 0.75, P 1.0, team 1.0 (6/6).
- Flagged for the next ratification pass: GT f370 "set P4B" id now
  incoherent under near={3,4}/far={1,2} (B's f370 setter should be P1 or
  P2); track-4 airborne foot-team flap recorded as an artifact class, no
  code change (f300 unemitted today).

### 2026-09-19 (thirteenth session) — open point 15(e): width-confirmed cross + own-side drive-block refutation

- **Protocol:** fresh HEAD baselines for all 7 videos FIRST
  (output/e15e/base_actions; determinism re-verified against the p16
  baselines before any edit), probe/capture scripts under output/probe_e15e
  (git-ignored), edit only after ALL_DONE.
- **Probe (output/diag_e15e_probe.py):** the f242 contact is drive-band,
  near-net, hands-overhead, width committed A (36px, votes 1) on an A
  toucher; expected-team A picked track 3 (GT P3A) — attribution was never
  the problem, the label was. f316: width commits B (23-24px ×3 votes,
  true far regime), track 1 chosen (GT's named toucher) with contact-foot
  B.
- **Offline simulation BEFORE implementation (output/diag_e15e_sim.py +
  streams/snaps captured for all 7):** naive variants were measured and
  rejected — the plain team-flip breaks e2 f118 (set→dig: its possession
  opener e2 f90 is invisible) and e5 f298; the broad stance-window team
  read breaks e5 f298 (its spiker's approach snapshots read A while GT
  says B). The shipped gates (would-be≥3 + positive width) were chosen
  from these measurements; the final rule simulated IDENTICAL on e1-e6
  and exactly the two designed e7 field changes.
- **Shipped:** src/recognition/action_context.py (resolver only —
  cross_flip in resolve(), own_side_drive_block into _decide; docstrings
  updated; zero new constants/config). No classifier/tracker changes —
  ball_side was already threaded into every contact by team-aware
  attribution.
- **A/B:** e1-e6 BYTE-IDENTICAL (frames/labels/teams/ids/touch/conf);
  e7: f195 t3→t1, f242 block t1 → set t2. Eval (--ignore-player, actions
  component): e7 F1 0.625→0.75, P 0.833→1.0, R 0.5→0.6; e1-e6 unchanged
  at baselines. Production src.main e7: player_3 Set_Count 1 (was
  Block_Count), serve/set/dig counts match the script path.
- **Tests:** suite 375 green (+5 in tests/test_action_context.py: the e7
  chain end-to-end, width-evidence requirement, would-be-2 refusal, 
  same-team refusal, redirect-band/abstaining block preservation).
- **f316 GT suspect:** sheet output/e15e/reratify_e7_f315_team.png (f300-320,
  P<tid><foot-team> stamps, net line, f316 contact marked). The GT's f112
  "P1B" vs f315 "P1A" for the SAME track in the SAME rally is the
  primary contradiction; if the owner ratifies B, e7 team reads 1.0 with
  zero code change (the pipeline already emits team B, toucher track 1).
- Files: src/recognition/action_context.py, tests/test_action_context.py,
  STATUS.md. Artifacts (git-ignored): output/e15e/ (baselines, post-run,
  evals, sheet), output/probe_e15e/ (probe, sim, per-video streams+snaps),
  output/diag_e15e_*.py.

### 2026-09-09 (twelfth session) — open point 19: the inverted poke rule retuned (ascent-only typing)

- **Probe (output/diag_poke_retune_features{,2}.py, git-ignored):** v1 had a
  measurement bug worth recording — SpikeAnalyzer's spike RECORD carries no
  `contact_point` (only the EVENT does), so rise measured from the first
  post-contact sighting is the wrong reference. v2 captures the raw events
  and reproduces the analyzer's exact decision-time view. Measured over the
  eight pipeline spikes: rainbow touches cross 80 px rise at +4..+9f; the
  hards never rise (e3 f431 −25, f539 −34 at its dig-close, e6 f309 −30);
  e5's poke arcs 64.5 px saturating ~+15f with exit vx only 18-22; e6's
  hard exits level at |vx| 47. The shipped |vx|≥25/|vy|≤12 rule was
  measured-inverted; ascent alone separates.
- **Shipped (src/analysis/spike_analyzer.py):** TOUCH_RISE_PX 80 → 57 (the
  midpoint of the two measured boundary rises — e5's poke 64.50 above, e1
  f371 50.50 below), the |vx|/|vy| poke test + `_exit_velocity` deleted.
  The classifier's `_is_poke_drive` (team path) byte-untouched; comments
  reworded to the ratified reading (airborne-net-contact team gate, not the
  poke type).
- **A/B catch:** at threshold 50, e1 f371 (GT spike_type null, incumbent
  hard) flipped to touch — its ball rises exactly 50.5 px and floats. Not
  noise; the threshold moved to 57 rather than accepting an unratified
  change. Final A/B (output/poke19/post57 vs the p16-HEAD baselines in
  output/poke/post_actions): e1/e2/e3/e4/e7 BYTE-IDENTICAL; e5/e6 differ in
  exactly one field each (spike_type hard→touch / touch→hard).
- **Eval scorer fix (scripts/evaluate.py):** GT `overrides` are now merged
  into events before scoring — ratified corrections (e5 f300 touch, e6 f310
  hard) are gradable. Result: spike_type e3 4/4, e5 1/1, e6 1/1; teams
  1.0 everywhere; labels F1 e3 1.0 / e5 1.0 / e6 0.933 (unchanged FN = the
  unemittable no-touch block).
- **Tests:** suite 370 green. TestPokeType rewritten (moderate-slow-arc →
  touch with exit vx below the old bar; e6 level exit → hard; narrow drive
  → hard); the two POKE_EXIT constant-mirror tests replaced by a guard
  that the analyzer has NO poke-exit constants and the classifier keeps
  its own (the type/team concern split, drift-locked).
- **Production:** src.main e5 `298,1,4,B,touch,A3,out` and e6
  `309,3,1,A,hard,A1,out` — both flips confirmed end-to-end, e6 team A
  preserved.
- Files: src/analysis/spike_analyzer.py, src/recognition/action_classifier.py
  (comments only), scripts/evaluate.py, tests/test_spike_analyzer.py,
  tests/test_team_attribution.py, STATUS.md. Artifacts (git-ignored):
  output/diag_poke_retune_features*.py/.txt, output/diag_e1_f371_probe.py,
  output/poke19/.

### 2026-09-06 (ninth session) — open point 16: in-court preference in the association cost

Owner report (e6_ballmatch_joust_f296-320.png): track 2B on a far-court
passer-by, the real far-left digger never tracked, 1A flips to the right-edge
bystander across f310-312. Probe (output/diag_e6_walker.py, raw detections +
assignments + track state, all checked against the frames):

- f142: the digger's (track 3) detection blips 1 frame; a walkway bystander
  105 px away grabs the track via the CONTINUOUS branch of _may_feed_track
  (no observation gap). Track follows the walkway right (f142-188), coasts
  frozen f190-243, and the digger — detected in court every frame from f146
  — is never re-acquired (215 px from the drifted ghost): untracked to the
  end of the video. Track 2 squatted the same way at f214/f244/f256. The
  squats cascade into Hungarian CHAIN-SWAPS (a full matching with long jumps
  beats one unmatched track at the 1e6 sentinel): f305 track2↔track3 rotate,
  f311 P1 → right-edge bystander at 149.5 px (gate 150), team vote B by f314.
- Gate-style fixes measured and REJECTED (overlapping distributions): legit
  out-of-court feedings on e1-e5 reach 146.6 px jump / sim 0.17; e6 hijacks
  start at 105 px / sim 0.26; world-metre displacement explodes (17-25 m) on
  LEGIT feedings via the airborne-foot projection artifact.
- Shipped: off_court_cost_penalty_px (300) added to the Hungarian cost for
  out-of-court detections — a PREFERENCE, not a gate. Allowance rules
  (_may_feed_track grace/hold/serve-zone) untouched; below the 1e6 sentinel;
  uncalibrated courts unaffected. Config + ctor + FrameProcessor +
  dump_player_tracks wired, drift-guard row added.
- A/B (baselines completed before any edit): e1/e3/e5/e7 tracks byte-
  identical; e2 3 frames, e4 15 frames (same mechanism, benign — e4 now
  follows GT id4 back into court at f390, all analyze_tracking metrics
  identical); e6 198 frames healed (digger f146→end under id 3, no f311
  swap, P1 stays A). Actions: e1-e5/e7 identical; e6 event-identical with
  f309 player_id 4→3; e6 eval F1 0.933 / team 0.857 unchanged; production
  src.main e6 emits the identical post-fix stream.
- Residual: f309 team still B vs GT 1A — isolated to the reentry band's
  stance-window snapshot rule (nearest snapshot = f307, the first frame
  whose grounded foot crosses the net line; f297-306 read A). Moved to open
  point 15b for the classifier retune session.
- Suite 347 → 355 green (+7 TestInCourtPreference, +1 drift row).

### 2026-09-06 (eighth session) — squatter review: sideline straddlers lose their roster slot (e7 class)
- **Owner plan v2 ratified in-session** (goal + mechanism + parameters +
  acceptance criteria, all measured beforehand on the e7 diagnostic dump
  output/diag_e7_bystander.json): stop an off-court bystander who straddles
  the sideline from holding a roster slot and poisoning identity downstream.
- **Shipped**: squatter review by lifetime in-court fed fraction — see the
  Where-we-are entry above for the full mechanism. One mechanism; no
  classifier/tracker-history retuning; admission erosion untouched (open
  point 18's front-end lever is separate); GT edits none.
- **Validated** (clean-room A/B, separate processes): e1/e3/e4/e5/e6
  byte-identical; e2 changed from f127 exactly as the plan predicted (slot
  to a real player 61f earlier than the 08-29 hold-horizon reuse at ~f188);
  e7 changed f166-283 (slot at f166 vs the f262 colonization; no ghost tail;
  no re-admission; re-converge f284); action streams event-identical on
  e2/e7; eval unchanged both; suite 347 green. Rollback:
  `player_squatter_enabled: False` restores HEAD behavior exactly.
- **New open point 18** records the known limits (match-footage dead-time
  churn + the GAME OFF re-tune trigger, the irreducible f47-145 front end /
  admission-erosion lever, the 0.5 m cooldown vs a line defender, the
  not-built rolling-window variant).
- Files: src/tracking/player_tracker.py, src/utils/config.py,
  src/analysis/frame_processor.py, scripts/dump_player_tracks.py,
  tests/test_squatter_review.py (new), tests/test_config_drift.py,
  CLAUDE.md, STATUS.md. Artifacts (git-ignored): output/squatter_base2/,
  output/squatter_post/, output/squatter_actions_{base,post}_{e2,e7}/,
  output/squatter_ab_logs/ (incl. eval JSONs + the run scripts).

### 2026-09-06 (seventh session) — ball-matching rework: identity by trajectory + motion, never confidence
- **Owner report**: most missed actions trace to tracking the wrong ball —
  e6's serve matched a bottom-right spare; e7's rally events lost to
  rack/drill balls; practices and tournaments both contain many balls.
- **Diagnosis (output/diag_ball_match*.py dumps)**: four confidence-driven
  failure mechanisms — spare bootstrap (e6 f0), top-1 cull hiding the real
  ball (e7 f241-244 rack ball 0.90 over real 0.79-0.92), blind reset
  re-lock (e6 f17, e7 f245), and — once all candidates are visible — the
  growing coast gate admitting slow distractors (e1 f77, 21px from the
  prediction, not rejectable by any local rule).
- **Shipped**: detector returns all candidates + two-stage stationarity
  (remove at persist 0.55, flag `stationary_suspect` at 0.30); tracker
  motion-gated bootstrap/re-lock (8 px/f over a <=2-frame pair); locked
  admission = old rule + stationary-suspect override; out-of-view re-entry
  window (2x max_missing at the exit point) replacing reset when the coast
  prediction leaves court bounds. New config keys `ball_lock_min_speed`,
  `ball_lock_motion_window`, `ball_lock_max_jump`, `ball_lock_max_pair_gap`,
  `ball_selection_conf_window`, `ball_static_suspect_frac` (drift-guarded).
  Intermediate designs measured and REJECTED on A/B: all-candidates +
  min-dist selection lost e1's f87 set (distractor admission); strict
  short coast window lost e5's f60 dig cascade; pred-anchored coast gates
  broke e3's fast-contact dropouts. The shipped shape keeps the old
  GT-validated admission semantics except where the old path STARVED.
- **Validated**: suite 325 green; e1/e3/e4 action streams byte-identical;
  e2 0.571→0.533, e5 1.0→0.857 (one label/frame each), e7 4/9 with set f110
  newly detected (serve traded — open point 15a). e6: owner ratified the
  serve (f34 p4 A, "from 4A") and re-confirmed the joust GT; folded same
  session -> e6 F1 0.857 → **0.933** (only FN = the unemittable no-touch
  block). NEW owner finding parked as open point 16: track 2B squats on a
  bystander behind the far court, the real center-left digger is
  untracked, and 1A→2B/1B swaps across f310-312 — player-identity stack
  work, likely also heals 15b. Production src.main on e6 confirms the
  serve end-to-end. e7 GT folded from the owner's dictation (open point
  15f: ratify).
- Files: src/tracking/ball_tracker.py, src/detection/ball_detector.py,
  src/analysis/frame_processor.py, src/utils/config.py,
  tests/test_components.py, tests/test_config_drift.py,
  ground_truth/video_entreno_7_annotations.json, CLAUDE.md, STATUS.md.
  Diagnostics (git-ignored): output/diag_ball_match*.py + json dumps,
  output/ballmatch_{before,after*,prod}_e{1..7}, output/ballmatch_eval_*.

### 2026-09-05 (sixth session, round 3) — live GAME-ON badge latency + badge styling
- **Owner report**: live-debug shows GAME ON at ~f140 for a serve at f30;
  also asked: is it livedebug-only?; black background behind the game-state
  badge; do not overprint the "Court: CALIBRATED" sign (screenshot showed
  GAME OFF on top of it).
- **Diagnosis**: (1) NOT livedebug-only — the badge state is snapshotted
  per frame in both render paths, so the machine itself was late (proved
  via the annotated-save render flipping at the machine's frame). (2) NOT
  tracking recall (14c's old story refuted): the serve flight is tracked
  from f27; the toss's single flight frame splits the pre-serve quiet
  (6 < arm_quiet_frames 10), the burst gate can never arm on the serve,
  and the candidate-only badge waited for the next contact's burst (f107)
  → f136.
- **Shipped**: rolling sustained-flight provisional (20 flight frames in
  the last ``fast_confirm_window_frames``=90 — new drift-locked config)
  lights the provisional GAME_ON without a candidate; badge/CSV only,
  episode/point layers untouched. Badge: solid black plate, own line below
  CALIBRATED (tests/test_overlay_game_state.py).
- **Validated**: e3 badge ON f136 → f53; e3 batch A/B actions/spikes/points
  byte-identical; game-state video points/actions byte-identical, eval
  11/13, 0 false, 80.6% unchanged; GT-OFF provisional cost 61 s → 72 s
  (display-only); suite **305 green**.

### 2026-09-05 (sixth session, round 2) — serve-init semantics: provisional fast ON, serve-action arming, trailing-group fix
- **Owner feedback**: e3 live-debug shows GAME ON at f174 for a point
  starting f30 (too late); a far-side pass during game-off should not turn
  the game on; detect serves and make them the game's init; the coach-fed
  points (0:21 / 1:02) are forgettable; all serves from the near field in
  this practice; real matches easier.
- **Diagnosis**: three serve-discriminator candidates measured on the
  production-path dump, all refuted (width at burst start / static hold /
  near→tape→far crossing — see open point 14a). Serve detection from ball
  signals alone is not available on this footage; practice serves are
  serves.
- **Shipped**: provisional fast ON (fast_confirm_flights=20: live GAME ON
  at serve+0.9-2.4s, dimmed "GAME ON ~" badge + provisional flag in the
  frame dict/CSV; POINT segmentation untouched and byte-identical);
  serve_action_arms=True (classifier serve actions arm instantly, contacts
  ≤45f old only); finish() no longer extends a closed trailing group
  (pt12 stop +6.2s → −1.9s). Config + drift locks + 4 new tests.
- **Validated**: e2e 11/13, 0 false, 80.6% frame accuracy; offline replay
  points byte-identical to the validated list; e3 A/B byte-identical
  AGAIN; e3 live ON f174 → f136 (rest is serve-flight tracking recall);
  suite **300 green**.

- **Owner request**: game on/off machine using resources/video_entreno_game_state.mp4
  + ground_truth/gt_point_start_end.txt (13 points, whole-second MM:SS start/
  stop, ±1 s), to count points and avoid counting actions between points.
  Owner context: same footage/court as video_entreno_* (e1 calibration reused);
  PRACTICE — some points start from a coach-fed ball, not a serve; real
  matches expected easier.
- **Diagnosis (output/diag_gs_dump.py + diag_gs_analyze*.py + diag_gs_sim/grid,
  git-ignored)**: full-pipeline signal dump (8167f, ~100ms/f) → legacy
  GameStateManager locks GAME_ON forever (53.3%); EVERY ball-motion signal
  family overlaps between GT points and between-point practice; quiet-gap
  and flight-density episode rules both cap at 10/13; the separating signals
  are burst-after-quiet onset, sustained flight, and CONTACT recurrence
  (≤215f in-rally vs ≥262f across the pt06/pt07 boundary).
- **Shipped**: game_state_manager.py/game_state.py rewrite (episode → group →
  contact-chain-split + ≥2-actions point rule; params in
  DEFAULT_CONFIG["game_state_detection"]); deleted the 4 legacy analyzer
  modules + score_tracker; FrameProcessor single-step wiring + flush feeding
  (450f finalize delay — measured emission lags up to 399f); csv_exporter
  game-state timeline rewrite; json_exporter game_state block + action
  point_index (77/83 actions gated into points on this video); DB points
  table + actions.point_index (idempotent migration, ingest verified);
  live-debug GAME ON/OFF badge; scripts/evaluate_game_state.py;
  calibrations/video_entreno_game_state.json (copy of e1's — same camera,
  frame-diff verified); ground_truth/README.md documents the MM:SS format.
- **Validated end-to-end**: 11/13 one-to-one matched, 0 false, 0 merged,
  79.0% frame accuracy; 7/11 starts within ±1 s; offline replay through the
  production class = the pipeline output exactly. Misses action-recall-
  limited (open point 14). A/B: e3 byte-identical (actions + spikes).
  Suite **296 green** (+18 tests/test_game_state.py).
### 2026-09-05 (later session) — court heatmap landscape rotation; stale-cache diagnosis; CSS-cache busting
- **Report**: court "way too big", "does not show where attacks land and
  where they start from", "add a number as well as a heatmap".
- **Diagnosis before design**: blobs/counts were present and correct on HEAD
  (DB query + `_court_blobs` probe + headless-Chrome screenshot of the served
  page). The owner's screenshot showed the pre-session rendering (huge court,
  no CSS-styled elements) = stale `make ui` process + cached style.css.
- **Shipped** (src/web/app.py `_court_blobs`, player_detail.html, style.css,
  base.html): landscape 160x80 court (net vertical; attacks LEFT half →
  land RIGHT half), max-width 560px; numbers/labels inline-styled in the SVG
  (stale-CSS-proof); stylesheet link cache-busted by mtime via a new
  `style_ver` template global.
- **Verified**: suite 269 → **278 green** (+9 tests/test_web_court.py);
  served-page screenshots with the theme and with the stylesheet stripped
  (court + numbers still render); all pages 200 with the new link.

### 2026-09-05 (fifth session) — player-page court FIELD heatmap (SVG): two rounds
- **Owner request**: on the player tab, replace the counts (attack-zone
  bars + from\lands matrix) with "a heatmap of the field, a visual
  representation of the field" — bottom side where the player attacks
  from, top side where the attack lands.
- **Round 1 (rejected)**: a CSS-grid court of 18 numbered boxes with
  counts. Owner: not a field. Lesson: draw the court, not a table.
- **Round 2 (shipped)**: `player_detail.html` renders an inline SVG —
  80x160 viewBox (1 unit = 10cm), sand-tinted rect + boundary, faint
  dashed 3x3 zone grid per half, net band with posts at y=80, rotated
  half labels ("lands" / "attacks from") in a left gutter, and heat
  hotspots: blurred radial-gradient circles (r=15) at zone centers —
  orange gradient = attack origins (bottom), blue = landings (top),
  opacity = 0.35 + 0.65·count/half-max. Small white count labels on
  hotspots only; `<title>` tooltips give the landing kill/out/dug split.
  `src/web/app.py` `_court_blobs()` maps zone digits to court coordinates
  (attack half columns mirrored: net row 3-2-1; landing half 1-2-3 —
  world_point_to_zone's camera-view convention, unit-checked).
- **Data layer unchanged from round 1**: `metrics.player_metrics` returns
  `court_attack` / `court_landing` / `court_landing_outcomes` keyed by
  zone digit (team letter stripped, 180°-symmetric grid). The joint
  placement matrix survives in metrics + tests, unrendered.
- **Verified**: suite **269 green**; served page's SVG parses as XML;
  blob geometry asserts (zone 1 bottom-right-at-net, zone 9 top-left-deep);
  headless-Chrome screenshot output/ui_player_court_preview.png
  (git-ignored).

### 2026-09-04 (fourth session) — analysis DB, player labeling, local web UI; extraction/DB split by file contract
- **Shipped**: `src/output_gen/json_exporter.py` — `src.main` now writes
  `output/<stem>/pipeline_output.json` beside the CSVs (lossless action
  fields + spike records minus flights + video metadata + git-hash
  pipeline_version; presentation-only, action stream untouched).
- **Shipped**: `src/db/` — schema.py (SQLite `data/volley.db`, WAL,
  videos/players/video_players/actions/spikes), ingest.py
  (`python -m src.db.ingest <stem|dir|json>`; transactional overwrite of
  ONE video's rows via videos-UPSERT + actions/spikes DELETE — labels
  survive; caught in review that a videos-row DELETE would cascade-wipe
  video_players), labels.py (per-(video, track_id) labeling; track ids
  are per-video bootstrap artifacts), metrics.py (glossary in the module
  docstring: kill%/error%/dug%/hard%/touch%, zone distribution,
  attack_zone×landing_zone heatmap, dig%/digs, kill-block vs soft-block
  from rally continuation — ball-touching blocks only, aces parked).
- **Shipped**: `src/web/` — FastAPI+Jinja local UI (`make ui`): videos,
  video detail (rally-grouped timeline, spike table, label form with
  known-player datalist), players overview, player detail (metric cards,
  CSS bar/heatmap charts — zero JS deps). Makefile: ingest / ingest-all /
  db-reset / ui. pyproject: `[web]` extras. README §"Analysis Database &
  Local UI". .gitignore: data/.
- **Validated**: re-ran all seven entreno videos through `make run`
  (pipeline_output.json emitted everywhere), `ingest-all` — DB counts
  match CSVs + recorded baselines (e3 14/4, e6 6/2, e5 7/2, e1 8/1,
  e2 7/1, e4 7/2, e7 5/0); cross-video aggregation checked on a throwaway
  DB copy (real DB left unlabeled for the owner). Web smoke: all pages
  200, label POST 303→updated, 404s correct.
- **Later the same session: UI restyled to a modern dark theme** (owner
  request): dark palette with orange accent (style.css rewrite — sticky
  blurred header, gradient cards/metric tiles/bars, glow on heat cells,
  dark form controls with focus rings; CSS-only, still zero JS deps;
  breadcrumb links on detail pages).
- **Later still: player photos for labeling.** `pipeline_output.json` gains
  `snapshots` — per track up to 3 (frame, bbox) picks from the per-frame
  tracked_players the pipeline already emits (action-anchored moments
  first, then a neutral mid-video stance; exporter-only change, zero
  pipeline divergence). `ingest` materializes them into
  `data/thumbs/<video>/<track_N>.png` strips (crop with padding +
  min-aspect 0.45 widening so far-side players stay recognizable; stale
  strips wiped per video; skips gracefully if the source video moved).
  The label form shows the strips (click to enlarge) and the action
  timeline shows small per-track avatars. NOTE: thumbnails need the video
  file reachable at its recorded path; re-running `make run` regenerates
  snapshots. Suite 269 green (+7).
- **Gotchas**: sqlite3 needs `check_same_thread=False` for FastAPI sync
  handlers (threadpool); this venv has no pytest-cov → run
  `venv/bin/python -m pytest tests/ -q -o addopts=""`. Suite **262 green**
  (240 + 22: tests/test_json_exporter.py, tests/test_db.py).

### 2026-09-04 (third session) — e1 GT re-verified + folded: three mixed id conventions unified; ratification queue empty
- **Diagnosis before design** (output/diag_e1_gt_reverify.py, git-ignored):
  a consistency audit of the GT itself (team-per-id across the 44 box
  frames) + a per-event spatial table (which GT box the pipeline's
  attributed toucher lands in) + contact sheets (full-frame row + zoom-on-
  contact row, GT boxes/GT label/pred crosshair) + a per-id montage.
  Findings: (a) f0 numbers ids 2↔3 opposite to the other 43 frames —
  positionally continuous persons, only numbers swapped (this also explains
  the montage's "flipped" first cell the owner spotted — a person swap, not
  a rendering bug); (b) f260 id1 B is a one-off typo in the joust's nearest
  box frame; (c) the 9 events use THREE conventions — canonical (f114/f257/
  f258/f371), L-R (f89/f329), and f0-flipped (f36/f206/f277, where the
  dominant reading names a player on the wrong TEAM).
- **Owner ratification** (sheets output/gt_verify/e1_reverify_*): all
  proposals accepted; f371's spiker confirmed id2/LR3 A; f258's block ruled
  NO-TOUCH (e6 precedent). Fold (output/fold_e1_gt.py): events → canonical
  (f36→p2, f89→p1, f206→p4, f277→p2, f329→p1, f371→p2), f0 renumber, f260
  id1→A. id4 stays unannotated at f0 (never ratified).
- **Measured** (same predictions, no pipeline change): player_accuracy_
  spatial 0.125 → **0.875**, spatial_lr 0.5 → 0.125 (the mirror flip proves
  single-conversion), labels-only F1 0.706 / team 7/8 unchanged — every e1
  residual now known-class (f114 freeball pt 9, f206 overhand set pt 5,
  f257 joust one-emission: the pred's single emission is the block-A side
  while the ball touch is the spike-B side).
- Files: ground_truth/video_entreno_1_annotations.json, STATUS.md.
  Diagnostics (git-ignored): output/diag_e1_gt_reverify.py,
  output/fold_e1_gt.py, output/e1_reverify/ (fresh HEAD action log),
  sheets output/gt_verify/e1_reverify_*.

### 2026-09-04 (later session) — joust-split adjudicated (block present, no ball touch); live-debug spike logs gain origin/landing
- **Owner ruling on open point 10(a)**: at the e6 f308 joust there WAS a
  spike and the block WAS there, but the block never touched the ball.
  Therefore one manufactured contact is the complete detectable truth — no
  joust-split mechanism; a no-touch block has no ball-flight impulse and is
  outside contact detection by design. The GT f308 BLOCK (2B t1) stays as a
  physical event the pipeline legitimately cannot emit (same class as e2's
  held-ball release). No GT/code change from the ruling itself.
- **Shipped (presentation-only, zero pipeline divergence)**: live-debug
  spike logging — `_ingest_actions` appends the takeoff zone to spike
  emission lines (`-> spike (0.65) from A1`, via the new
  `SpikeAnalyzer.spike_zone_for(contact_frame)` query, which mirrors
  `spike_type_for` over pending+records); a new
  `LiveDebugProcessor._log_resolved_spikes()` (called per frame in BOTH
  render paths, after flush, and reset on 'r') logs `Spike resolved:
  contact frame 308 player 1 from A1 -> lands B7 (out)` the moment a record
  closes, re-logging on outcome flips (dug→kill pending-dug, kill/out→dug
  retro-conversion — the (frame, outcome) signature gates it). Formatting
  lives in the module-level pure `describe_spike_record()`
  (tests/test_live_debug_logs.py, no processor construction needed).
- **Verified on the real e6 two-pass run** (output/spike_log_e6, git-ignored):
  f173 `spike (0.50) from B3` → resolved `lands out of bounds (out)` →
  re-logged `dug at A8 (dug)` after the f216 dig; f308 `spike (0.65) from
  A1` → `lands B7 (out)`. Render/labels byte-identical to before (log-only
  change + a read-only analyzer query).
- Tests: +8 (spike_zone_for pending/after-close/miss; 7 formatter cases).
  Suite 232 → **240 green**.
- Files: src/analysis/spike_analyzer.py, src/analysis/live_debug_processor.py,
  tests/test_spike_analyzer.py, tests/test_live_debug_logs.py (new),
  STATUS.md.

### 2026-09-04 — reentry contact shipped: e6's out-of-frame joust spike manufactured; point 10's e2 "instance #2" refuted
- **Diagnosis first** (output/diag_reentry.py raw-sighting dump + annotated
  sheets output/gt_verify/reentry_e6_f262-320.png / reentry_e2_f160-174.png,
  git-ignored): (a) e6 — across the f308 joust the BALL tracker reset at f289
  (10 missing frames after the toss exited the top at f277) and ADOPTED the
  bottom-left spare, so the game ball's real re-entry descent (f301–310,
  seen by the raw detector at (1305,34)→(1332,268), ~24px/f, above the tape
  the whole way) NEVER reached _ball_history; the tracker re-locked the game
  ball only at f314, post-joust. The classifier's history: spare junk f302
  (34,118) → 12f gap → run start f314 (1152,278) then -48px/f flat above
  the tape — the joust impulse (vx +3 → -50) hidden in the gap. Free-flight
  fit: the toss arc cannot produce the observed re-entry; the impulse is
  the contact. (b) e2 — **the "instance #2" reentry story is REFUTED**: the
  tracker bridges the set-toss apex (f141→f149, gap 8, identity kept via
  the growing-gap tolerance), the GT-corrected spike at f167 is a plainly
  VISIBLE bounce (dense sightings, rises 148/136px) — the normal detector
  fires, and the event dies at the reach gate by 4px (nearest snapshot box
  top 144px from the ball vs CONTACT_REACH 140); the true toucher (GT p3 B)
  is airborne and coasted ~200px away mid-jump (t1B real f150 → f192).
  Re-classified under point 7 (reach/ghost-drift), not point 10.
- **Shipped** (REENTRY_* band in ActionClassifier._detect_contact, beside
  the bridge bands; gates: gap ∈ [8,30]; ≥2 real points in (c,c+7] moving
  ≥40px/f horizontally dominated, starting at/above the net tape; IDENTITY
  BREAK — the pre-gap point ≥200px from the run's backward extrapolation
  (e6: 1695px; e2 f149: 34px, refused); touch placed at the gap MIDPOINT
  (e6 → f308 == GT), point back-extrapolated, above the tape; attribution
  at the manufactured frame (1A's clean pre-swap f308 snapshot within reach
  via the near-net exemption); gesture ATTACK for kind="reentry" (bypasses
  the hands-overhead→BLOCK misread on a jumping toucher); emitted team from
  the takeoff stance [c-12, c-2] — the SpikeAnalyzer takeoff-window fix
  scoped to this kind, because contact-time airborne feet project deep
  (would have emitted B, GT is A). _detect_contact now returns a 5-tuple
  (…, frame) so the reentry can date the event off-c.
- **Measured (e6)**: +f308 spike t3 r1 (track 1 = the GT spiker, team A,
  conf 0.65) and f265 overpass→set (follow exists now): labels-only F1
  0.667 → **0.923** (P 1.0; the only FN is the GT f308 BLOCK — one
  manufactured contact per ball event; a spike+block joust-split is an
  owner decision), team 6/6. **A/B (output/diag_reentry_ab.py, identical
  feeding): e1/e2/e3/e4/e5 BYTE-IDENTICAL event streams**; evals unchanged
  (e1 0.706, e2 0.571, e3/e4/e5 1.0). Production src.main on e6: same
  6-event stream (CSV emission-anchored; spike conf 0.65 on player_1).
- Tests: +8 reentry (fires on identity break incl. midpoint frame +
  manufactured inc; rejects connectible gap / vertical run / slow run /
  below-tape run / gap-band edges; end-to-end spike with takeoff-team; no
  reach → no event); 3 call sites updated for the 5-tuple. Suite 224 →
  **232 green**.
- Files: src/recognition/action_classifier.py, tests/test_team_attribution.py,
  STATUS.md. Diagnostics (git-ignored): output/diag_reentry.py,
  output/diag_reentry_sheets.py, output/diag_reentry_ab.py, sheets
  output/gt_verify/reentry_*.png, runs output/reentry_{base,post}_e{1..6},
  output/reentry_prod_e6.

### 2026-09-01 — trail render fix: masked blend (owner-reported black boxes behind trail segments)
- **Owner report**: the red trail carried black rectangles behind its
  segments. Root cause: `draw_ball_trail` blended each segment's whole ROI
  via `addWeighted` — every background pixel in the rectangle was scaled by
  (1-alpha) toward black, not just the line's pixels.
- **Fix**: masked blend — the line is drawn anti-aliased on a scratch, and
  only the touched pixels get `roi*(1-a) + line*a`; the ROI's other pixels
  are untouched. Regression test pins it (uniform-200 background: off-line
  pixels inside the ROI stay exactly 200). Suite **224 green**; re-rendered
  production video verified visually (output/spike_prod4, git-ignored).

### 2026-08-31 — outcome semantics completed: kill = direct fall OR dug-and-dies-without-a-set (owner rule)
- **Owner adjudication**: the four e3 "kills" are three digs + one kill; the
  video is ONE point. Kill rule (now in GT README + analyzer docstring): the
  ball falls directly, OR is dug and dies without a set (on the defenders'
  court or out of bounds). A dig kept up (set follows) is just `dug`.
- **Shipped**: pending-dug watch in SpikeAnalyzer — a dug record stays
  provisional; any later touch event finalises `dug`, a CONFIRMED ball death
  flips it to `kill` at the fall point (`_detect_dug_death`: candidate
  landing must survive DUG_DEATH_CONFIRM_FRAMES=16 with no subsequent loft ≥
  DIG_LOFT_PX). The confirmation is load-bearing — diagnosed on dev5: without
  it all three kept-up digs read as kills because the descent into the
  setter's hands terminates like a landing while the set EVENT is still
  ~40-50f away (lookahead emission). The real f539 death bounces 12 px; set
  tosses loft 150+ px.
- **GT**: f178/f297/f433 → `dug` + `dug_zone` (the annotated zones
  reinterpreted as dig locations); f541 stays `kill` (landing B8 annotated,
  measured B7 — fall at world x≈1.9 m, one column left). evaluate.py gains
  dug_zone_accuracy.
- **Measured (e3)**: outcome 4/4, dug_zone 3/3, spike_type 4/4,
  attack_zone 4/4, team 14/14; landing_zone 0/1 (B7-vs-B8 residual).
  A/B stream still byte-identical (pure observer). Suite **223 green** (+2:
  dug-ball-dies → kill; dug-then-set stays dug).
- Files: src/analysis/spike_analyzer.py, scripts/evaluate.py,
  ground_truth/video_entreno_3_annotations.json, ground_truth/README.md,
  tests/test_spike_analyzer.py, STATUS.md. Runs output/spike_dev{5,6},
  output/spike_prod3 (git-ignored).

### 2026-08-30 — spike analytics: trail, touch/hard, 9-zone grid, kill/dug outcomes; f297 GT corrected
- **Diagnose first** (output/diag_spike_exit.py, git-ignored): dumped the real
  sighting stream around the four GT contacts. Three findings drove the
  design: (a) exit speed cannot separate touch from hard (touches launch
  19-29 px/f vertically; f431's hard ball left near-rest and fell under
  gravity) — post-contact ascent can (146-240 px vs ≤33 px, threshold 80);
  (b) every attack flight ends in a 220-340 px loft at the GT dig events —
  sand cannot rebound that high, so all four "kills" read as digs
  (retro-conversion gate DIG_LOFT_PX=90 built from this; f431 visually
  confirmed on the sheet); (c) airborne feet at contact project deep through
  the homography (f431 B5 from airborne feet vs B2 takeoff) — origin zone now
  uses the pre-contact snapshot closest to the net in [c-12, c-2].
- **Zone convention pinned by the GT anchors, not the sketch**: each half
  numbered 1-9 facing its OWN baseline (180°-symmetric; A1 image-right at the
  net, B1 image-left). The request's ASCII sketch is the 180° flip; the
  anchors (both A attacks from image-right = A1, f178 from image-right = B3)
  decide. Documented in world_point_to_zone + ground_truth/README.md.
- **Shipped** (pure observer; A/B byte-identical stream, 0 base-field diffs):
  SpikeAnalyzer (observe/flush/reset; records + trail/kill/type render
  queries) wired in FrameProcessor (+flush_actions feeds it the flushed
  contacts, reset_trackers resets it); overlay.draw_ball_trail (ROI-blended
  per-segment alpha, gap-aware) + draw_kill_marker + typed spike label colors;
  live-debug `_render_frame`/`_ingest_actions` render trail/KILL/spike-type
  in BOTH modes; test_action_recognition observes + enriches its log +
  renders pass-2; video_processor exposes results["spike_analysis"];
  csv_exporter writes `<stem>_spikes.csv`; statistics adds spike tallies;
  evaluate.py scores spike_type/attack_zone/landing_zone/outcome.
- **Measured (e3, vs corrected GT)**: spike_type 4/4, attack_zone 4/4, team
  14/14 (old f294 residual gone), labels: the f294/f297 pair now fails the
  player-spatial gate (pred center above the net resolves to the adjacent net
  player's box at the 10f-strided GT frame; pred team/player are right) —
  spike P/R 0.75 from that single gated pair. outcome/landing 0/4 pending
  point 12 (dug-vs-kill).
- Tests: +22 (zone grid incl. 180° symmetry + boundaries, ascent type,
  kill/out/dug/blocked/unknown, retro-conversion both ways, takeoff window,
  trail fade/gap, kill marker); suite **220 green**.
- Files: src/detection/court_calibration.py, src/analysis/spike_analyzer.py
  (new), src/analysis/{frame_processor,live_debug_processor,video_processor,
  statistics}.py, src/output_gen/{overlay,csv_exporter}.py,
  scripts/{test_action_recognition,evaluate,verify_action_labels}.py,
  ground_truth/video_entreno_3_annotations.json, ground_truth/README.md,
  tests/test_spike_analyzer.py, CLAUDE.md, STATUS.md. Diagnostics
  (git-ignored): output/diag_spike_exit.py, output/diag_spike_sheets.py,
  sheets output/gt_verify/spike_f*.png, runs output/spike_*.

### 2026-08-29 — off-court hold horizon: e2's out-of-court bystander loses its roster slot
- **Diagnosis** (output/diag_e2_tracking.py audit + sheets; streak probe
  output/diag_ooc_streaks.py over all six videos): the owner's "we get a
  hold of the player outside the court" = a right-side bystander (conf
  0.82–0.89, feet beyond the right sideline, x≈1660–1890) who straddled
  the line at bootstrap, seeded a track, then stepped out — and
  `_may_feed_track`'s continuous-match exception (no horizon, outranks
  grace AND zone rules) fed them for 415 frames. The server p1 (x≈73 at
  f0–8) was out-of-court AND beyond the 1m zone margin → never admissible;
  in court from f28 with no free slot. Earlier "0% out-of-court
  assignments" reads were a diag bug (`np.bool_ is False` never matches).
- **Measured safety margin**: max real-player continuous out-of-court
  streak across e1–e6 = 46f (e6 t3); e3's server 44, e5 42, e4 36, e1 1.
  Horizon default 90 = 2× margin, matching serve_zone_trial_frames.
- **Shipped**: `player_off_court_hold_frames` (config + ctor +
  frame_processor + dump_player_tracks + drift-guard row); the continuous
  exception expires past the horizon measured from the track's last
  IN-COURT sighting; zone-seed (never-in-court) tracks keep the existing
  regime (trial expiry governs them). Retirement is the NORMAL path (coast
  → max_disappeared → dormant) — no new eviction machinery; the freed id
  came back via new-track/gallery-restore on an in-court player.
- **A/B (output/diag_ooc_ab.py, identical feeding)**: e1/e3/e4/e5/e6 **0
  differing track frames, identical action streams**; e2 differs from f104
  only (bystander coast), action stream unchanged except f256's attributed
  track (1→2; label/team/touch identical). Production e2 re-run: F1 0.571
  unchanged.
- **Gotcha for future diag harnesses**: two PlayerTracker instances in one
  process permute bootstrap ids — `cv2.kmeans` consumes the process RNG
  (verified: identical params, sequential instances → [2,3,1,4] vs
  [4,1,3,2]; `cv2.setRNGSeed(0)` per instance fixes it). Production
  single-run is deterministic. First A/B attempt was confounded by exactly
  this (e1/e2/e6 showed id-swap diffs from f7).
- Tests: +5 (within-hold allowed, beyond-hold blocked, zone-seed regime
  unchanged, end-to-end slot-freed incl. the bystander-never-tracked and
  newcomer-takes-slot assertions); suite **198 green**.
- Files: src/tracking/player_tracker.py, src/utils/config.py,
  src/analysis/frame_processor.py, scripts/dump_player_tracks.py,
  tests/test_bystander_guard.py, tests/test_config_drift.py, STATUS.md.
  Diagnostics (git-ignored): output/diag_e2_tracking.py,
  output/diag_ooc_streaks.py, output/diag_ooc_ab.py, output/ooc_e2/,
  sheets output/gt_verify/video_entreno_2_tracking_f*.png.

### 2026-08-27 — short-gap bridge shipped (e2/e6 missed digs); e2/e6 GT honesty work; joust diagnosed as "reentry" class
- **Diagnosis first** (output/diag_e6_missed.py gate trace + sheets, e2 the
  same via its ball dump): e6's 4 missed GT contacts are TWO classes, not
  one. (a) f212 dig: 6f occlusion at the digger's arms — sightings f208/210
  descending to y482, f216 already at y338 rising; gap 6 sits below the
  bridge floor (8f) while the normal path has 1 left / 0 right points
  within NEIGH (can't fire); even gap-allowed, the right side is SPARSE
  (only f224 in the next 12f). e2 f206 identical class (7f gap, dense
  right). (b) f311 joust: structurally invisible — see new open point 10.
- **Design lesson recorded:** the obvious sparse-right fix (extend the
  right window to c+12) CANNOT work — contacts are confirmed at
  c+CONTACT_DELAY and the right window ends at c+6, so those points are not
  in history at decision time (first A/B run "passed the gates" and then
  silently refused for exactly this reason). Deferred evaluation was
  considered (pending state + ordering guards) and rejected; the
  CROSS-GAP RISE gate needs no future points and is physically tight: a
  sand rebound cannot rise 60px in ≤6f and a free-flight apex cannot
  produce it from a ≥20px descent.
- **Shipped** (`_bridge_contact` + `BRIDGE_SHORT_MIN_GAP/BRIDGE_X_CONT_*`):
  short band gap 5–7, gates = normal-path-proof (sparse NEIGH on ≥1 side —
  e6 f265 fires NORMALLY at gap 6, the bridge must not relocate it) +
  x-continuity max(24, 3·gap) + the classic left-descent shape + cross-gap
  rise when the right window is empty. Classic band 8–14f untouched.
- **A/B (subclass harness, identical feeding, all six videos):** e1/e3/e4/e5
  streams byte-identical (every short-band candidate refused: dense-NEIGH
  or x-discontinuity 68–118px — e5's spare windows f320/f325); e2 +f209 dig
  t1/r2 (the 91f gap lands as rally reset, matching GT's possession
  numbering) and the cascade heals: f256 dig→SET t2, f306 spike t2→t3; e6
  +f216 dig t1/r1, f265 dig→overpass t2 (GT set — the follow it needs is
  the joust; open points 9+10). Production script path re-run: e2/e6
  identical to the A/B streams, e5's 7-event stream identical to the
  validated one (f17 serve … f299 spike 0.65).
- **Eval (GT as-is, labels-only):** e2 F1 0.222 → **0.600** (P 0.5 / R 0.75;
  3/4 matched, labels 3/3), e6 0.545 → **0.667** (P 0.8 / R 0.571; 4/7
  matched, labels 4/5). With point 11's GT additions ratified, e2's
  denominator grows to 7 and its unmatched preds become matches.
- **GT honesty (owner review pending — NOT folded):** e2's 3 unmatched
  preds are real touches (f32/f118/f327, sheets in output/gt_verify/);
  e2 f79 is a caught/held feed ball (static f78–82) — pipeline-invisible BY
  DESIGN, correctly refused by the new gates (ascent 0 at the catch, drop 0
  at the toss); e6 f311 block team B→A proposed.
- Tests: +6 (dense-right fires, cross-rise fires, dense-NEIGH stays
  normal-turf [asserts the normal path DOES fire there], identity jump,
  no-descent, classic band keeps ≥2 right); suite **193 green**.
- Files: src/recognition/action_classifier.py,
  tests/test_team_attribution.py, STATUS.md. Diagnostics (git-ignored):
  output/diag_e6_missed.py, output/diag_shortgap_ab.py,
  output/diag_e2_unmatched.py, output/diag_e6_f216_reach.py,
  output/shortgap_e{2,5,6}/, sheets output/gt_verify/.
- **Owner ratification round (2026-08-28, same working session):** e2
  +f118 set 4B t2 and +f327 dig 4B t1 folded (GT 4→6 events, labels-only
  F1 0.222→0.667); e6's joust re-corrected to f308 spike **1A** t3 + block
  **2B** t1 (the old f311 p4-B/p3-B pair was wrong on BOTH roles; A's
  3rd-touch spike is the volleyball-consistent reading — A dug f212, set
  f262); e1's joust arbitration ratified as-is. New observations recorded:
  e2's f32 is a SERVE by an UNTRACKED server (event pending the owner's
  player_id/team; serve-zone admission unmeasured on e2); the e6 tracker
  swaps players at f311 (f308 labels correct — no tracking GT to measure);
  owner proposes a freeball label for touch-3 soft crosses (open point 9/11e).
- **Second ratification round (later, same session):** e2 f32 folded as
  **serve p1 A t1** (owner marked the untracked near-left server in white
  on the f24-44 sheet) → e2 GT complete at 7 events, labels-only F1 0.615
  (the two label misses now visible and known-class: untracked-server
  serve, 91-frame-gap overpass). **freeball adopted** into the GT vocab
  (overpass = touch-1/2 crossing, freeball = touch-3+ soft cross); e1 f114
  relabeled; emission parked on the crossing signal (point 9). Ratification
  queue down to: e2 f79 semantics + e1 id wobbles.
- **Third round (owner re-scrubbed e2 end to end):** f79 DROPPED (no dig
  there); rally corrected to serve f32 p1 A → dig **f90 p3 B** (reception)
  → set f120 p4 (frame fix) → spike **f167 p3 B t3** (new — explains the
  f185–202 descent) → f206 dig p3 A (preceded_by_attack→true) → f257 →
  f305 → f327. e2 GT = 8 coherent events, labels-only F1 0.571; residuals
  all known-class (2 recall: held-ball release + reentry-f167; 2 label:
  untracked-server serve, 91f-gap overpass). Owner tracking observations
  folded into point 7 (out-of-court squatter on e2; server tracked early
  then lost; p3 untracked at f90) and e2-f167 added as reentry instance #2
  in point 10 (descending sub-shape vs e6's horizontal one).

### 2026-08-26 (later session) — e2/e6 generality check clean; e1's "contact recall" was double-annotated GT
- **Generality check (e2/e6, first runs on the current stack):** zero
  bridge candidates on either video — the strict gates hold on unseen
  footage; teams 1.0 on every scored pair. e6: 3/7 GT contacts, all three
  labels right (dig/set/spike); the f262 set→dig is the missed f212 dig's
  touch-count cascade (e5's pattern), f311 spike+block missed. e2: 2/4
  matched (f305 spike ✓; f257 set→dig cascade from the missed f206 dig);
  3 unmatched preds (f32/f118/f327) — e2's 4-event GT is likely incomplete
  (the e4-f182 lesson: unmatched preds on sparse GT need contact sheets
  before trusting precision). **e2/e6 are now the real contact-recall
  evidence** (detection-limited), not e1.
- **e1's GT was double-annotated**: two annotation passes interleaved, 17
  events for ~9 touches (f277 duplicated verbatim; twins at ±1-2f
  throughout; the passes disagree on frames, touch numbers, and teams). The
  recorded "e1's misses are contact-detection recall" was an artifact.
  Dedup applied (17→9): twins merged (f36, f89, f277, f329, f371); f114/115
  arbitrated to **overpass** (ball rebounds off the net line into the far
  half with no further A touch — trajectory-proven); the f252-258
  four-fragment cluster arbitrated to ONE spike+block joust at the single
  f257-258 trajectory contact (f257 spike p3 B attacking B's f206 toss,
  f258 block p1 A fully airborne). Sheets: output/gt_verify/
  video_entreno_1_f{114,255}.png — **owner ratification wanted** (p3 as
  the spiker is inferred from jump geometry; no pass ever names p3).
- **e1 after cleanup: 8/9 contacts detected, labels 5/8, teams 7/8, F1
  0.471** — and the three residuals are known-class, none recall: (a) f113
  dig vs overpass — the resolver only detects overpass at touch-2, this was
  touch-3; (b) f208 dig vs set — B's overhand reception of the overpass at
  touch-1 (pose-level label, open point 5 class); (c) a joust emits one
  contact for two GT events.
- e1's GT still has id/team wobbles beyond the deduped events (e.g. f277
  names p3 whose box is far from the ball's position at the dig) — needs a
  dedicated re-verification session, not spot fixes.
- Files: ground_truth/video_entreno_1_annotations.json, STATUS.md.
  Diagnostics (git-ignored): output/diag_video_entreno_{2,6}_ball.json,
  output/gen_e{2,6}/, sheets above.

### 2026-08-26 — e5 action layer fully resolved: gap-bridged bounce + 2.5m net exemption (old open points 1+2); GT folded; eval convention fix
- **GT folded (owner dictation 2026-08-18 + contact-sheet arbitration).**
  e5: serve f20 p2 added (right-side server = GT2; pred f17 center inside
  its box), frames 60/110/159/197 → 63/111/160/200, ids f63 p4, f111 p3,
  f200 p2 ("overhand dig" kept in raw_visual_actions, final_action `dig` —
  canonical vocab has no overhand dig), f250 p1, f300 p2. e4: f133 p3,
  f276 p2, f224 pre_atk→true. Two corrections were OURS and are now
  owner-ratified (2026-08-26, from the sheets): e5 f160 p3→p4 and f300
  p4→p2 — both proven on dumped sheets (the named players stand flat-footed
  while another is airborne under the ball) + trajectory contact points.
  e4 f182 spike p4 ADDED and likewise ratified (un-annotated real touch:
  GT4 airborne at net, ball crosses to A; fixes e4's phantom-precision).
  flag_occluded_gt run on both (e4 4, e5 9 flags).
- **evaluate.py: GT action player_id conventions differ across files** —
  e1/e3 are L-R indices (probe: e3 canonical 2/14 vs L-R 12/14; e1 1/8 vs
  5/8), e4/e5 are canonical (6/7 vs 4/7; 4/5 vs 1/5). Per-action TP gating
  is now spatial + convention-agnostic (pred center → containing GT box,
  match under either convention; raw-id fallback without gt_players) and
  both `player_accuracy_spatial` (canonical) and `..._lr` are reported.
  Consequence: e3's gated F1 was 1.0 only by numeric coincidence (the f69
  known misattribution scored pid 2 == gt 2); honest value 0.929.
- **Diagnosis (instrumented replay, output/diag_e5_*.py):** e5's 3 label
  errors + 2 missed contacts were ONE root cause. The f111 set was
  undetectable (ball sightings stop descending f102, resume rising f114 —
  occluded at the setter's hands, spare ball stole top-1 meanwhile), so the
  f60→f157 gap (97f) exceeded rally_reset_gap=90 → new rally → f157
  touch-1 dig (GT spike); f196 became touch-2 set (GT dig); f247's foot
  142px > NEAR_NET_PX → dig (GT set). The f300 spike WAS detected (bounce
  at f301, prominence 171/101) but died at the reach gate: the spiker's
  per-contact foot team read B at 2.14m from the net while the width
  regime (36–40px) said near/A, and the 1.5m exemption missed by 0.64m —
  the only surviving candidate was 316px away (> CONTACT_REACH 140).
- **Shipped:** (1) `_bridge_contact` in the classifier — a bounce whose
  bottom sits inside an 8–14-frame sighting gap fires at the gap's first
  sighting (that frame's normal tests provably cannot fire: no left points
  within NEIGH), touch point interpolated; gates: ≥2 real points each side
  within 6f, net descent ≥20px, net ascent ≥60px (sand rebounds rise ~25px
  and must not read as touches — e5 f332-340). History scans: e1/e3/e4 have
  ZERO qualifying gaps → streams unchanged (A/B: e1/e4 byte-identical; e3
  differs only in f539's self-reported L-R index, same attributed player).
  (2) `attribution_near_net_exempt_m` 1.5→2.5 across config/ctor/fallback
  (drift-guarded). e5 then emits 7/7 with all labels right; f299 even reads
  gesture ATTACK → spike 0.65.
- **Measured (vs corrected GT):** e5 actions 7/7 matched, labels 7/7,
  teams 7/7, players 6/6 scored (gated F1 0.857 — the f114 bridge pair's
  GT box is occlusion-flagged so its player gate can't score; same
  conservative no-box rule as e4 f347's ±17px temporal skew). Anchors:
  e1 0.4 / e3 0.929 / e4 0.857 gated F1, all identical pre/post change.
  Production `src.main` on e5 emits the same 7-event stream (players,
  labels, confidences; CSV frame column is emission-anchored, +50 const).
- Tests: +7 (bridge fires / short-gap / too-long / sand-bounce / no-descent
  / MIN_CONTACT_GAP / spatial-either gating) + 1 updated (B_VERY_DEEP for
  the 2.5m exemption); suite **187 green**.
- Files: src/recognition/action_classifier.py, src/utils/config.py,
  src/analysis/frame_processor.py, scripts/evaluate.py,
  ground_truth/video_entreno_{4,5}_annotations.json,
  tests/test_team_attribution.py, STATUS.md. Diagnostics (git-ignored):
  output/diag_e5_ball.py, output/diag_e5_contact.py, output/diag_gt_pairs.py,
  output/diag_*_ball.json; sheets output/gt_verify/*f160/f182/f300*.png.

### 2026-08-18 — entreno_5 serve-zone squatter fixed: server vote + trial expiry + contested swap (old open points 2+8)
- **Diagnosis** (owner live-debug report + audit trail): bootstrap locked 3
  tracks at f8 (server stands behind the near baseline, never in the strict
  pool); the create loop then admitted a STATIONARY bottom-left bystander
  through the serve-zone exemption — detection order was by confidence and
  the bystander out-scored the real server — and held the 4th slot for all
  354 frames (continuously detected → off-court grace never burns; seed has
  `last_in_court_frame=None`). The server (GT2) was covered in 1/36 GT frames
  → every action after the first dig misattributed.
- **First attempt (single-frame ball anchor) failed and taught the real
  geometry**: the top-1 ball on the admission frame was a SPARE ball lying
  near the bystander (633,794) — inside the bystander's column ABOVE the
  waist, because a close-camera bystander's chest height projects where sand
  3-5m behind them does. Distance/nearest-ball anchoring admits the bystander
  by construction; the discriminator is temporal (the spare is static-
  suppressed after `static_min_frames`, the toss ball then sits over the
  server f8-20).
- **Shipped design** (player_tracker.py): (1) **server vote** — a serve-zone
  candidate is only admissible with ≥`player_serve_zone_ball_votes` (2)
  recent ball sightings inside its x-span column above the waist; live ball
  history + no qualifying candidate ⇒ zone admission defers that frame; no
  ball history at all ⇒ legacy confidence order. (2) **contested swap** — an
  admitted seed whose column the ball has LEFT (last-3 sightings) while
  another candidate has the votes is hard-removed (cooldown bbox, not
  gallery) and the true holder takes the slot — e5 swaps bystander→server at
  ~f10. (3) **trial expiry** — a seed never in court within
  `player_serve_zone_trial_frames` (90) is hard-removed with cooldown (the
  "does not let it go" backstop). `update()` gained `ball_position` (top-1
  ball det) wired through FrameProcessor / dump_player_tracks /
  test_action_recognition; config keys + drift-guard rows added.
- **Measured (e5)**: tracking detection 0.722→**0.958**, ghosts
  0.278→**0.042**, id 0.986, team 0.978; GT2 (server) 1/35→**34/35**; actions:
  serve detected for the first time (**f17** vs owner's f20), dig f60 ✓,
  f196/f247 land on the right players (formerly untracked); label residuals
  are the resolver's dig/set/overhand-dig confusion + 2 missed contacts
  (open point 2).
- **Regression gate (byte-level A/B via git stash)**: e1 — **0 differing
  frames** (the apparent 0.978→0.771 id drop reproduces identically on HEAD;
  pre-existing drift, now open point 3); e3 — 7 frames differ (server
  admitted ~6f later, metrics 0.973/0.063/0.952→0.969/0.064/0.952), **action
  stream byte-identical** to the validated 14/14 attrib_e3_new2 log; e4 —
  identical numbers.
- Tests: +11 (server vote incl. the sand-ball non-vote + swap + trial +
  cooldown); suite 180 green. Old open point 8 (crowded-drill serve-zone
  watch) closed — implemented, plus a stronger mechanism than the n_court_det
  gate it suggested.
- Files: src/tracking/player_tracker.py, src/utils/config.py,
  src/analysis/frame_processor.py, scripts/dump_player_tracks.py,
  scripts/test_action_recognition.py, tests/test_serve_zone.py,
  tests/test_config_drift.py, STATUS.md. Artifacts (git-ignored):
  output/e5_fix/, output/gt_verify/ (6 owner-verification contact sheets),
  output/diag_e5_admission.py, output/diag_e1_states.py.

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

### 2026-09-27 (twenty-third session) — perf: both parked pose levers shipped in the shared path; byte-identical everywhere; live-debug decoupling parked
- **Context:** the owner asked to make BOTH offline and debug-live
  processing faster. The 2026-08-17 perf session had measured and parked
  exactly this ("pose only for near-ball players, 52→~26ms, needs an
  occlusion-window fallback first" + producer/consumer display decoupling)
  — the ask was the trigger to cash them in. Parity rule respected: both
  levers live in the SHARED `ActionClassifier.classify_actions` (batch and
  debug-lite inherit); `LiveDebugProcessor` untouched.
- **Diagnose first (`output/diag_pose_gate_probe.py`, git-ignored like all
  diag scripts):** mirrors the GT-validated script wiring; per frame it
  records ball staleness, every observed player's point-to-bbox distance to
  the live ball, and (patched `_closest_player_at`) every contact's chosen
  snapshot frame / offset / reach / distance to the ball AT THE SNAPSHOT
  FRAME and to the last-9f ball TRAIL. Findings that shaped the design:
  (a) pose 29.7 ms/f × 3.54 calls/f is the largest non-YOLO stage; (b) the
  ONLY pose consumer is `_gesture` via the chosen snapshot of an ACCEPTED
  non-reentry contact — reentry gestures return ATTACK unread (probe gotcha:
  `_closest_player_at` fires pre-reach-gate, so raw records include
  reach-rejected contacts up to 1261px — filter `reach ≤ 160`; and reentry
  f311 e6 reads trailmin 1163px but consumes NO pose); (c) every
  pose-consuming snapshot ≤ **155 px** from some ball point in the last
  NEIGH+2=9 frames (snapshot offsets measured −2..+4); (d) staleness split
  entreno 71/27/1.6% vs match slice 28/20/52% live/occlusion(≤30f)/dead.
- **Shipped (`src/recognition/action_classifier.py`, `src/utils/config.py`,
  `src/analysis/frame_processor.py`):** `pose_gate_stale_frames` (30) +
  `pose_near_ball_radius_px` (300.0), either ≤0 disables. Dead ball
  (>30f untracked): skip MediaPipe entirely. Ball live: pose only players
  within 300px of a last-9f ball point. Occlusion window (1..30f): pose
  everyone. ALWAYS append a history entry per observed player (pose=None
  when skipped) so `_closest_player_at` snapshot selection, the L-R index
  and the takeoff-stance reads are untouched. `pose_gate_stats` counters
  (posed/skipped_stale/skipped_radius) for tests + perf reports. Config
  drift test extended with both keys (suite 465→477).
- **Neutrality protocol executed in full:** fresh HEAD baselines
  (output/posegate_base_e*) → edit → A/B (output/posegate_gated_e*):
  7/7 entreno action logs **BYTE-IDENTICAL**; `evaluate --ignore-player`
  reproduces the recorded gate F1s exactly. FULL match production re-run
  (output/match20260920_posegate/): every data CSV BYTE-IDENTICAL to
  output/match20260920_e3fix (results / detailed / game_state / spikes);
  31/33 points, 57 episodes, 0-before-first unchanged; only the
  self-referential timing statistics row differs. Match probe slice: 16/16
  contacts identical incl. snapshots.
- **Measured gains:** match wall 38 → 30.5 min (84.8 → 68.0 ms/frame,
  11.79 → 14.71 fps — ×1.24); match probe slice 76.1 → 64.2 ms/f (×1.19);
  entreno script wall ~96 → 85 ms/f (×1.13, little dead time there).
- **Parked:** open point 23 (live-debug producer/consumer display
  decoupling — fps only, pipeline untouched).
- Files: src/recognition/action_classifier.py, src/utils/config.py,
  src/analysis/frame_processor.py, tests/test_pose_gate.py (+12),
  tests/test_team_attribution.py (stub gained `estimate_pose` — the gated
  loop calls per-player, not the batch wrapper), tests/test_config_drift.py,
  STATUS.md.


### 2026-09-27 (twenty-fourth session) — product north-star goals set (G1 Fantasy, G2 stats); critical paths mapped, no pipeline code

- Owner restated the product intent for the club service: (1) Fantasy-
  style scoring per point per player (Kill/Block/Ace/Dig +1, Assist
  +0.5, Error −1) over recorded sessions; (2) individual per-player
  statistics. Both now live as the North-star section at the top of
  STATUS; future prioritization traces to them.
- Mechanism-level coverage audit (recorded in the North-star section):
  Kill/Dig/Block/attack-Error already derivable from the DB; Assist is
  one join away (set → same-team kill, same point) — pure metric work;
  the real G1 blockers are the point winner/outcome layer (21.3),
  far-side serve emission (22), the per-point×player scoring module +
  web points table (14e), and attribution robustness (2/21.4/21.5).
  Ball-handling errors ruled a manual-review path, not perception.
- Product decisions ratified at session close: Assist scores **+0.5
  flat** (set → same-team kill, no direct/indirect split); **soft
  blocks score 0** (only kill blocks take the +1).
- Ranking unchanged at #1 (22 serves both goals); 21.3 promoted above
  the rest of 21's frontier. Session #20's Log entry archived verbatim
  (live Log trimmed back to 3).
