# Action reliability — execution plan

Source: `docs/202609-28-astra-fix-pipeline.md` (assessment, §5 stages, §6 first work package).
Linked from `STATUS.md` → *Where we are / Active next*. One task = one mechanism = one session (AGENTS.md §3).
Status legend: `TODO` / `WIP` / `REVIEW` / `DONE` / `BLOCKED(owner)`.

**Dev clip (fails today):** `resources/video_ari_joan_8_first_points.mp4` (1920x1080, VFR, 4963 frames, first 8
match points; missed serves, serve-out, set slip, spike-into-net, side switch at 3–4).
**Regression suite:** `resources/video_entreno_1..7.mp4` + `ground_truth/` (byte-identical gate for no-decision changes).
**Held-out:** OPEN — need a second recording with a pinhole (non-fisheye) fixed camera in the supported long-axis
scope, kept untouched until Stage 3. `Entreno Vall Hebron i Partits - 05 05 2025.mp4` is REJECTED as the held-out
gate (fisheye breaks the 8-point homography; rain/lens drops) — at most a later 1–2-point *stress/unsupported* probe.

## Stage 0 — honest baseline (no production decision changes)

| #  | Task | Deliverable | Gate | Status |
|----|------|-------------|------|--------|
| T1 | **Calibration/view readiness** | `src/main.py`: readiness report (calibration found, source-stem match, `frame_dimensions` vs actual video size, degraded outputs listed); missing/unmatched calibration = hard error unless `--allow-uncalibrated`; readiness block in `pipeline_output.json` metadata. Calibration for the dev clip (derived from the match calibration if same camera, scaled via `frame_dimensions`), owner verifies on a frame overlay. | Entreno action outputs byte-identical (only the new metadata key differs); tests for each readiness state; suite green. | DONE (568 tests, e1–e7 byte-identical; overlay owner-verified; probe scripts gated too — T1b, 581 tests) |
| T2 | **Dev-clip GT** | Locate clip offset inside `20260920_match_ari_joan_lost_up1080.mp4`; translate match GT (actions + point start/end + serve anchors) for P1–P8 into `ground_truth/video_ari_joan_8_first_points_annotations.json`; contact sheet for owner ratification; tag error events (serve out, set slip, net spike) and side switch. | Owner-ratified sheet. | DONE — owner-dictated contact GT (`20260920_match_ari_joan_contacts_p1_p8.txt`) folded by `scripts/build_dev_clip_gt.py`: 28 contacts, per-possession touch numbers, 15 superseded draft events kept; frames coarse ±15f; P6 f3131 set→overpass flagged for owner ratification; side switch after P7. |
| T3 | **Time-matched evaluator** | `scripts/evaluate.py` (or sibling): one-to-one matching in seconds (±0.2 s, from PTS), separate contact / class / team / actor scores, FP per dead-time minute, duplicates; point intervals by overlap (not count ratio). Autonomous mode forbids GT-derived inputs (winners, anchors, pins). | Reproduces existing entreno F1 ordering on frame-exact data; unit tests. | DONE — `scripts/evaluate_timed.py` (+23 tests, suite 648), sibling of `evaluate.py` (untouched, its `load_json` is imported). Matching = optimal one-to-one assignment on TIME distance (scipy `linear_sum_assignment`, greedy fallback), tolerance `max(--tolerance-s 0.2, GT frame_tolerance/fps)`. Time source: per-frame PTS vector if the blob carries one, else `frame/fps` (reported; no video decode). Separate scores: class-agnostic contact P/R/F1, class accuracy + confusion matrix, team, actor (n/a on null GT `player_id` / `--ignore-player`), duplicates, FP per dead-time minute, point intervals by temporal IoU (matched/missed/spurious, mean IoU). `--autonomous` refuses a prediction file carrying `winner`/`score`, `serve_anchor`/`anchor`, `owner_pin`/`owner_verdict`/`owner_contact`, `map_attribution`, `serve_relabel*`, `gt_*`/`ground_truth*` keys (documented in `find_gt_derived_inputs`); verified clean on the real e15e/posegate/`output/video_entreno_*` files, and it correctly refuses the dev-clip GT used as predictions. Gate result: contact F1 0.2 s e1 .941 / e2 .857 / e3 .929 / e4 1.0 / e5 1.0 / e6 .933 / e7 .750; at the 0.5 s window `evaluate.py` effectively uses (±15f) every one equals its `evaluate.py` F1; ordering preserved (Spearman 0.82 @0.5 s, 0.64 @0.2 s, the only inversions e1/e6/e3 where `evaluate.py`'s class-aware matching hides a hit). No `output/` prediction exists for the dev clip, so the point-IoU/dead-time paths were exercised on the posegate match output against the dev-clip GT as a smoke test (numbers meaningless — different clips) + unit tests. |
| T4 | **Loss waterfall** | Diagnostic-only hooks (off by default) + `scripts/waterfall.py`: for each GT event on the dev clip, the first stage where it dies — raw detection → track admission → candidate → actor/team → gesture/context → point/scoring. | Outputs byte-identical with hooks off; table committed under `docs/`. | DONE — `--diag-dump` JSONL capture through the shared `FrameProcessor.process_frame` (`src/utils/diagnostics.py`; sinks are `if self.diag_enabled:` guards, default off) + `scripts/waterfall.py` and `scripts/compare_runs.py`; +37 tests, suite 685. Gates: hooks-off == pre-change HEAD byte-identical on the dev clip + e3 + e1 (`--device cpu`, only `processed_at` / wall-clock statistic rows differ), hooks-on == hooks-off byte-identical, unit tests per stage, suite green. Dev headline (`evaluate_timed --ignore-player`): contact P 0.586 / R 0.607 / F1 0.597, class 0.706, team 0.706, 1 dup, 2.703 FP/dead-min, points 6 matched / 2 missed / 0 spurious (mean IoU 0.707). Waterfall: detection 0, admission 0, candidate 6, gate 5 (all reach), actor/team 5 (4 of them the post-P7 side switch), label 4, survives 8. FPs: in-point spurious 8, dead time 3, duplicate 1. **Root finding:** 5 of the 6 stage-3 deaths are serves, and there the detector sees the ball (conf 0.74–0.87, none suppressed) while the tracker reports `unlocked_no_motion` on 19–25 of 31 window frames — the toss apex never meets `lock_min_speed = 8 px/f`. Table: `docs/t4_loss_waterfall_dev_clip.md`. |
| T5 | **Pick first mechanism** | From T4 counts, choose ONE of: time-based windows (VFR), candidate recovery, width-split `unreliable` state. Written decision in STATUS. | Owner approval. | TODO |

## Stage 1 — evidence and units (shadow first)

| #  | Task | Gate | Status |
|----|------|------|--------|
| T6 | Versioned feature sidecar (PTS, ball obs/pred/missing + rejection reason, player boxes/IDs, pose+conf, candidates incl. rejected + gate reason, non-event windows) — compressed sidecar, not the main JSON | Legacy outputs byte-identical; replay reproduces baseline decisions; runtime/storage cost reported vs 68 ms/frame | TODO |
| T7 | Perturbation suite, level 1 (feature replay: rescale, frame drop/dup, width scaling) with per-constant flip attribution | Report only; no thresholds changed | TODO |
| T8 | Width-band fix: sub-far-band widths currently vote *far by default* (`action_classifier.py:871–884`) → adaptive per-video split + explicit `unreliable` state, shadow mode | A/B on entreno + dev clip; team accuracy per side | TODO |
| T9 | PTS-based time windows for duration constants (`MIN_CONTACT_GAP`, `CONTACT_DELAY`, `RALLY_RESET_GAP`) and px/s velocities, shadow | Per-signal A/B; revert any signal that doesn't help | TODO |
| T10 | Camera profile in calibration artifact (px/m at net & baselines, measured fps, width stats) + config-drift guard extension | Guard test extended | TODO |

## Stage 2+ (after Stage 0/1 evidence)

- T11 Multi-signal contact proposals (ball-hand proximity rel. player scale, pose motion, missing-ball masks) unioned with trajectory candidates — gate ≥97% candidate recall on dev clip.
- T12 Small learned contact/gesture head (logistic/GBM) vs frozen rules, evaluated on held-out session only.
- T13 GT-free point segmentation + serve interpretation (no winners/anchors/pins).
- T14 Identity through side switch (dev clip P3→P4 sample) + stable-player metric.
- T15 Point winner/outcome (= STATUS open point 21.3), then deterministic scoring (assist +0.5, kill_block/soft_block); audit `dig` = reception vs defensive dig before +1.

## Parallel / owner-side (no code)

- Approve plan + held-out choice; ratify T2 contact sheet.
- Reconcile `docs/video_recording_guide.md` (long-axis vs sideline; fix px/frame-vs-FPS claim).
- Collect 6–10 recordings across ≥3 setups for the benchmark.

## Standing constraints

`ball_confidence` 0.15; A/B baselines from untouched HEAD before editing; `--device cpu` for parity; perception causal
and single-pass through `FrameProcessor.process_frame`; hindsight work in pass-2 only; no GT edits without
owner-ratified sheets.
