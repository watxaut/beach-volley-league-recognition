# Action reliability — execution plan

Source: `docs/202609-28-astra-fix-pipeline.md` (assessment, §5 stages, §6 first work package).
Linked from `STATUS.md` → *Where we are / Active next*. One task = one mechanism = one session (AGENTS.md §3).
Status legend: `TODO` / `WIP` / `REVIEW` / `DONE` / `BLOCKED(owner)`.

**Dev clip (fails today):** `resources/video_ari_joan_8_first_points.mp4` (1920x1080, VFR, 4963 frames, first 8
match points; missed serves, serve-out, set slip, spike-into-net, side switch at 3–4).
**Regression suite:** `resources/video_entreno_1..7.mp4` + `ground_truth/` (byte-identical gate for no-decision changes).
**Held-out candidate (untouched until Stage 3):** `resources/full_videos/Entreno Vall Hebron i Partits - 05 05 2025.mp4`
(1080p, 29.97 fps CFR — different setup/rate). Owner to confirm.

## Stage 0 — honest baseline (no production decision changes)

| #  | Task | Deliverable | Gate | Status |
|----|------|-------------|------|--------|
| T1 | **Calibration/view readiness** | `src/main.py`: readiness report (calibration found, source-stem match, `frame_dimensions` vs actual video size, degraded outputs listed); missing/unmatched calibration = hard error unless `--allow-uncalibrated`; readiness block in `pipeline_output.json` metadata. Calibration for the dev clip (derived from the match calibration if same camera, scaled via `frame_dimensions`), owner verifies on a frame overlay. | Entreno action outputs byte-identical (only the new metadata key differs); tests for each readiness state; suite green. | DONE (568 tests, e1–e7 byte-identical; owner to eyeball `output/t1_calib_overlay.png` far corners) |
| T2 | **Dev-clip GT** | Locate clip offset inside `20260920_match_ari_joan_lost_up1080.mp4`; translate match GT (actions + point start/end + serve anchors) for P1–P8 into `ground_truth/video_ari_joan_8_first_points_annotations.json`; contact sheet for owner ratification; tag error events (serve out, set slip, net spike) and side switch. | Owner-ratified sheet. | TODO |
| T3 | **Time-matched evaluator** | `scripts/evaluate.py` (or sibling): one-to-one matching in seconds (±0.2 s, from PTS), separate contact / class / team / actor scores, FP per dead-time minute, duplicates; point intervals by overlap (not count ratio). Autonomous mode forbids GT-derived inputs (winners, anchors, pins). | Reproduces existing entreno F1 ordering on frame-exact data; unit tests. | TODO |
| T4 | **Loss waterfall** | Diagnostic-only hooks (off by default) + `scripts/waterfall.py`: for each GT event on the dev clip, the first stage where it dies — raw detection → track admission → candidate → actor/team → gesture/context → point/scoring. | Outputs byte-identical with hooks off; table committed under `docs/`. | TODO |
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
