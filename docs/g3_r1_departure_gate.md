# G3 R1 — the confirmation-time DEPARTURE gate (attempted 2026-09-30)

> ## OUTCOME: NOT SHIPPED — refuted on the held-out full match (owner decision 2026-09-30, option (a))
>
> At `contact_min_departure_bw = 0.3` the gate removed the **P11
> owner-confirmed serve** (f7132 dig A, 0.285 bw/f) and the structural FP
> **6928A**, points confirmed fell **31/33 → 28/33** and the far prefix
> census **8/8 → 7/8** (Gate C below). **`src/` is reverted to 185c6f0**
> (T5 precedent, commit 8140711): no gate, no `contact_min_departure_bw`
> config key. The mechanism is **parked and reproducible** via the
> scripts-side harness `scripts/departure_gate_harness.py`
> (`departure_bw_per_frame`, verbatim) + `scripts/action_evidence.py`
> (`departure_gate_check`) + the committed `output/g3r1/` artifacts,
> probed by `scripts/probe_departure_removals.py` /
> `scripts/probe_owner_verdicts.py`. All tables below are the historical
> gate evidence, unchanged.

Owner-approved G3 R1 mechanism (session 40, task 2): a contact candidate is
REJECTED when the ball's post-contact departure speed, measured in BALL
WIDTHS PER FRAME over the `ActionClassifier.CONTACT_DELAY` window after the
contact frame, is below `contact_min_departure_bw` (default **0.3**). The
measurement uses the classifier's OWN `_ball_history` (real admitted
sightings only — no coasted tracker predictions), is normalised by the ball
width at the sighting nearest the contact (scale-invariant: far-side balls
move fewer pixels for the same real speed), and reads only frames the
confirmation has already seen (causal — no lookahead, live-debug parity
preserved: the gate lives in the shared `classify_actions` path). Departure
NOT measurable (fewer than 2 sightings in the window / no pair on distinct
frames / no positive width) ⇒ **ABSTAIN**, never reject. `0` or `None`
disables the gate. Rejections are recorded as the new diag reason
`low_departure` (seen by `scripts/waterfall.py`).

## Where it lives

- `src/recognition/action_classifier.py` — pure helper `departure_bw_per_frame`
  (imported, never copied, by the offline evidence tooling) + the gate in the
  candidate path, BEFORE any player attribution (ball-trajectory evidence
  only; a rejection leaves `_last_contact_frame` untouched, same semantics as
  a reach rejection).
- `src/utils/config.py` — `contact_min_departure_bw: 0.3` in
  `DEFAULT_CONFIG`; wired via `src/analysis/frame_processor.py` and the
  `scripts/test_action_recognition.py` kwarg; pinned in
  `tests/test_config_drift.py` (DEFAULT_CONFIG ↔ ctor default ↔ script
  kwargs). `ball_confidence` stays 0.15 (untouched).
- `tests/test_departure_gate.py` — 14 unit tests: helper value, scale
  invariance, chain starts at the contact-frame vertex, mean-step-not-net,
  causal window bounds, all abstain cases, width-at-nearest-sighting,
  per-gap normalisation; gate reject / pass / abstain / disable(0,None) /
  bw-not-px / only-seen-sightings.

## Offline evidence (re-measured on the classifier's OWN history)

`scripts/action_evidence.py` reconstructs `_ball_history` from the diag dumps
and calls the SAME `departure_bw_per_frame` helper on the 85 predictions
(dev + e1–e7): **flagged 7 of 85 (5 `fp_in_point` + 2 `fp_dead_time`),
flagged CORRECT 0, max flagged non-correct 0.287 bw/f, min unflagged correct
0.383 bw/f — the empty gap holds on the classifier's data** (abstain 0).
Flagged: dev f2195 0.186, f2414 0.211, f2445 0.185, f2494 0.127, f3265
0.198, f3639 0.161, e4 f388 0.287. Evidence:
`output/g3/g3_action_evidence_r1.md` / `output/g3/evidence_r1.json`
(`departure_gate_check`). The gate therefore must remove exactly 7 FPs and
0 correct actions; every gate below tests that prediction.

## Gate A — entreno e1–e7 (`--device cpu`, byte-identity vs HEAD baselines)

Baselines `output/g3/e{1..7}/` (HEAD src, verified by `git log -- src/`),
post-change `output/g3r1/e{1..7}/` (`output/g3r1/run_runs.sh`).
`scripts/compare_runs.py` verdict and `scripts/evaluate.py --ignore-player`
(on `action_log.json`) per clip; "script" = `scripts/test_action_recognition.py`
(the GT-validated reference path; its F1 is the historical record source).

| clip | baseline F1 / team | after F1 / team | script F1 / team | compare_runs | record |
|------|-------------------|-----------------|------------------|--------------|--------|
| e1 | 0.706 / 1.0 | 0.706 / 1.0 | 0.706 / 1.0 | IDENTICAL | 0.706 ✓ |
| e2 | 0.400 / 1.0 | 0.400 / 1.0 | 0.571 / 1.0 | IDENTICAL | 0.571 ✓ (script record; src.main path reads 0.400 pre-existing — STATUS Learning, the f167 gesture flip, NOT this change) |
| e3 | 1.000 / 1.0 | 1.000 / 1.0 | 1.000 / 1.0 | IDENTICAL | 1.000 ✓ |
| e4 | 0.933 / 1.0 | **1.000 / 1.0** | **1.000 / 1.0** | DIFFERENT | 0.933 → 1.000: the single diff is FP f388 `overpass` B removed (0.287 bw/f, the offline-flagged e4 FP); predicted 8→7 vs GT 7 ⇒ all 7 correct, team 1.0 unchanged. NOT a lost correct action. |
| e5 | 0.923 / 1.0 | 0.923 / 1.0 | 0.923 / 1.0 | IDENTICAL | 0.923 ✓ |
| e6 | 0.933 / 0.857 | 0.933 / 0.857 | 0.933 / 0.857 | IDENTICAL | 0.933 ✓ (team 0.857 ✓) |
| e7 | 0.750 / 1.0 | 0.750 / 1.0 | 0.750 / 1.0 | IDENTICAL | 0.750 ✓ |

**Zero correct entreno actions lost**: 6/7 clips byte-identical; e4's only
diff is the removal of the offline-flagged FP (offline `flagged_correct`
= 0; every clip's F1/team equals the record, with e4 ABOVE it by exactly
that FP removal). Eval JSONs: `output/g3r1/eval/{g3,g3r1,script}_e{1..7}.json`.

## Gate B — dev clip (`video_ari_joan_8_first_points.mp4`, `--device cpu`)

`scripts/evaluate_timed.py --ignore-player` before (`output/g3/dev_verify`,
= T4 baseline, `output/g3r1/dev_timed_base.json`) vs after
(`output/g3r1/dev`, `output/g3r1/dev_timed.json`):

| metric | before | after |
|--------|-------:|------:|
| contact P | 0.586 | 0.739 |
| contact R | 0.607 | 0.607 |
| contact F1 | 0.597 | **0.667** |
| class accuracy | 0.706 | 0.706 |
| team accuracy | 0.706 | 0.706 |
| duplicates | 1 | 1 |
| FP / dead-minute | 2.703 (4 FP) | 1.351 (2 FP) |
| points matched/missed/spurious | 6 / 2 / 0 | 5 / 3 / 0 |
| mean point IoU | 0.707 | 0.649 |

Exactly the 6 offline-flagged dev FPs are removed (no additions):
f2195 dig B 0.186 / f2414 serve A 0.211 / f2445 dig A 0.185 / f2494 overpass
A 0.127 / f3265 spike B 0.198 / f3639 dig A 0.161 bw/f. The point-window
change (6→5 matched) is the game-state OBSERVER reacting to the removed
dead-time touches (a window kept alive by a dead-time FP no longer
confirms); reported, not tuned. `scripts/waterfall.py` on the after-dump
(`output/g3r1/dev_waterfall.md`): stage 4_candidate_gate now shows
**`low_departure`** (GT P5 serve f2575 — the FP serve at f2494's candidate)
alongside the reach rejections; FP sources after: dead_time 1, duplicate 1,
in_point_spurious 4.

## Gate C — full match 20260920 (held-out; both arms SAME code + `--device cpu`)

Arms differ ONLY by `--config` yaml: `output/g3r1/match_bw0.yaml`
(`contact_min_departure_bw: 0`) vs `output/g3r1/match_bw03.yaml` (0.3).

bw0 (gate OFF) is the production reproduction: **207 actions, dig 84 /
spike 45 / set 42 / serve 20 / overpass 9 / block 7**, action-set identical
(frame+action+team, 207/207) to the canonical `output/match20260920_posegate`
run. NOTE: the bw0 log was initially named `match_bw0_partial_deadrun.log`
by a revival mishap (see `logs/r1_finish_report.md`); it is the COMPLETE
run's log and has been renamed `match_bw0.log` (the killed 1h-ceiling
relaunch log is kept as `match_bw0_relaunch_killed1h.log`). bw0 ran WITHOUT
`--diag-dump` (a partial diag from the killed relaunch was deleted); bw03
runs WITH `--diag-dump` (default-off logging, byte-identity proven in T4 —
not an A/B variable).

### Removed actions (arm diff, bw0 − bw03; bw/f from the bw03 diag `low_departure` records)

22 removals, 0 additions (`output/g3r1/removed_actions.py`):

| frame | action | team | bw/f | kind | region note |
------:|--------|------|-----:|------|-------------|
| 2195 | dig | B | 0.186 | drive | dev-validated FP; P4's pass-2 relabeled serve (owner P4 = NOT_TRACKED far) |
| 2414 | serve | A | 0.211 | drive | owner FALSE mark ("going to the serve line") |
| 2445 | dig | A | 0.185 | drive | inside OFFGAME 2444-2534 |
| 2494 | overpass | A | 0.127 | redirect | inside OFFGAME 2444-2534 |
| 3265 | spike | B | 0.198 | redirect | dead time after P6 |
| 3639 | dig | A | 0.161 | bounce | dead time before P7 |
| 5130 | serve | B | 0.253 | drive | owner FALSE mark ("ball handling after the point ended") |
| 6928 | serve | A | 0.090 | redirect | structural FP, round-3 owner queue (report-only in pass-2) |
| **7132** | **dig** | **A** | **0.285** | bounce | **P11 = owner round-2 MISCLASSIFIED verdict: the serve contact at f7132, owner-confirmed — REMOVED = owner-verdict regression** |
| 10206 | set | B | 0.208 | drive | P15 tail |
| 10292 | spike | B | 0.241 | bounce | P15 tail |
| 15265 | dig | B | 0.232 | bounce | P20 region |
| 15280 | overpass | B | 0.114 | drive | P20 region |
| 17246 | dig | A | 0.204 | bounce | P23 region |
| 17257 | overpass | A | 0.100 | redirect | P23 region |
| 18408 | dig | B | 0.138 | drive | P24 region |
| 19359 | spike | B | 0.258 | drive | P25 region |
| 20397 | serve | B | 0.263 | drive | P27's EMITTED serve (map census "20397B serve OK", side-matched) |
| 20690 | overpass | B | 0.278 | bounce | P27 region |
| 25033 | dig | B | 0.279 | bounce | P30 window (point-confirmation starvation) |
| 25444 | dig | A | 0.239 | drive | P30/P31 window |
| 25533 | overpass | A | 0.169 | drive | P31 window (point-confirmation starvation) |

**P1–P8 GT comparison** (`ground_truth/20260920_match_ari_joan_contacts_p1_p8.txt`):
the 6 removals inside the P1–P8 frame range are all ≥37f from any
owner-dictated contact frame (2195↔2154: 41f; 3265↔3228: 37f; the rest
≥81f; owner frames are ±10-15f coarse) — **no correct P1–P8 contact is
lost**. The regression lives OUTSIDE the fitted region.

### Pass-2 chain on both arms (map → relabel → evaluate_match_points)

| gate | bw0 (gate OFF) | bw03 (gate ON) | verdict |
|------|----------------|----------------|---------|
| far prefix census | 2/8 → **8/8** (≥6/8 ✓) | 2/8 → **7/8** (≥6/8 ✓) | CHANGED (P4 → anchor_only) |
| serve-typed actions | 20 → 31 (−6 dem, +17 relab) | 16 → 29 (−4 dem, +17 relab) | CHANGED (−4 emitted serves removed upstream) |
| points with resolved serve | 32/33 | 32/33 | same |
| resolutions (emitted/relab/pin/anchor_only/report) | 12/17/1/2/1 | 11/17/1/3/1 | P4 relab→anchor_only; P27 emit→relab |
| owner FALSE demotions | 1039,2414,3595,3856,5130,14387 | 1039,3595,3856,14387 (2414+5130 no longer exist) | consistent |
| P20 pinned 14516A / P32 report_only | ✓ / ✓ | ✓ / ✓ | same |
| 17 owner verdicts (`output/g3r1/check_owner_verdicts.py`) | **17/17 OK** | **REGRESSION**: P4 relabeled→anchor_only; P11 serve f7132→**f7160** | **STOP** |
| points confirmed (`evaluate_match_points.py`) | **31/33 (0.939)** | **28/33 (0.848)** — points 29-31 lose confirmation | **STOP** |
| map (episodes/mapped/bursts/false-serve-cands) | 57/19/6/6 | 57/18/7/3 | one episode demotes to burst |

Points 29–31 (f22857-25959) lose confirmation because the pipeline's own
point layer — whose windows the tail's touches kept alive — loses the
f25033/f25444/f25533 actions (0.279/0.239/0.169 bw/f). The P11 regression
is the owner round-2 verdict "serve starts f7114, contact f7132 = the
dig-labeled action (owner-confirmed)": the gate removes that real serve
(0.285 bw/f < 0.3) and pass-2 falls back to f7160 (28f late).

### STOP condition hit (reported, not fixed)

Per the task spec ("a regression in the owner-verdict reproduction or
points confirmed = STOP and report, do not tune the threshold to the
match"), the gate **fails the held-out match generalization check**:

1. **Owner-verdict regression**: P11's owner-confirmed serve f7132
   (0.285 bw/f) is removed; the "P9–P12 at the exact contact frames"
   reproduction breaks.
2. **Points-confirmed regression**: 31/33 → 28/33.
3. Far prefix census 8/8 → 7/8 (still above target) and serve-typed
   31 → 29; P27's side-matched emitted serve f20397 (0.263) is removed.

Where the gate does what the evidence predicted: the 6 dev-region FPs
are removed exactly; the owner-FALSE serves f2414/f5130 never emit; the
structural FP f6928 (round-3 queue) never emits; entreno (Gate A) and dev
(Gate B) pass with zero correct actions lost.

Reading: the 0.3 threshold was fitted on dev P1–P8's empty gap
[0.287, 0.383]; the match's held-out region contains REAL serve-class
contacts with post-contact departure BELOW that gap (far float serves:
f7132 0.285, f20397 0.263 — the T5 "decelerating float" family), which
dev's near-side serves never exercised. The threshold is not safe at 0.3
for match generalization. **The src/ diff is left as-implemented for the
owner/reviewer to decide** (revert, retune on the match-informed gap, or
exempt serve-class candidates); no threshold tuning was done here.

## Tests

`tests/test_departure_gate.py` — 14 tests (helper: value, scale
invariance, contact-frame chain start, mean-step-not-net, causal window
bounds, abstain cases, nearest-contact width, per-gap normalisation;
gate: reject+diag reason, pass, abstain, disabled at 0/None, bw-not-px,
seen-sightings-only). Full suite:
`venv/bin/python -m pytest tests/ -o addopts=""` → **772 passed**
(754 before + 18 new cases: the 14 departure-gate tests incl.
parametrisation + the config-drift pin rows).
## Reproduce commands

```bash
# entreno + dev (gate ON, production default) + baselines
bash output/g3r1/run_runs.sh            # e1-e7 + dev -> output/g3r1/<clip>, cpu, diag
for n in 1 2 3 4 5 6 7; do
  venv/bin/python scripts/test_action_recognition.py resources/video_entreno_${n}.mp4 \
    --output output/g3r1/script_e${n} > output/g3r1/script_e${n}.log 2>&1
  venv/bin/python scripts/evaluate.py \
    --predictions output/g3r1/e${n}/action_log.json \
    --ground-truth ground_truth/video_entreno_${n}_annotations.json \
    --component actions --ignore-player --output output/g3r1/eval/g3r1_e${n}.json
  venv/bin/python scripts/evaluate.py \
    --predictions output/g3r1/script_e${n}/video_entreno_${n}_action_log.json \
    --ground-truth ground_truth/video_entreno_${n}_annotations.json \
    --component actions --ignore-player --output output/g3r1/eval/script_e${n}.json
  venv/bin/python scripts/compare_runs.py output/g3/e${n} output/g3r1/e${n}
done
# dev before/after + waterfall
venv/bin/python scripts/evaluate_timed.py --predictions output/g3/dev_verify/pipeline_output.json \
  --ground-truth ground_truth/video_ari_joan_8_first_points_annotations.json \
  --ignore-player --json output/g3r1/dev_timed_base.json
venv/bin/python scripts/evaluate_timed.py --predictions output/g3r1/dev/pipeline_output.json \
  --ground-truth ground_truth/video_ari_joan_8_first_points_annotations.json \
  --ignore-player --json output/g3r1/dev_timed.json
venv/bin/python scripts/waterfall.py --diag output/g3r1/dev_diag.jsonl \
  --predictions output/g3r1/dev/pipeline_output.json \
  --ground-truth ground_truth/video_ari_joan_8_first_points_annotations.json \
  --markdown output/g3r1/dev_waterfall.md --json output/g3r1/dev_waterfall.json
# match arms (yaml: contact_min_departure_bw 0 vs 0.3)
nohup venv/bin/python -m src.main resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4 \
  --output-dir output/g3r1/match_bw03 --skip-visualization --device cpu \
  --config output/g3r1/match_bw03.yaml --diag-dump output/g3r1/match_bw03_diag.jsonl \
  > output/g3r1/match_bw03.log 2>&1 &
# removal list / pass-2 chain / verdicts (per arm X in bw0 bw03)
venv/bin/python output/g3r1/removed_actions.py output/g3r1/match_bw0/pipeline_output.json \
  output/g3r1/match_bw03/pipeline_output.json output/g3r1/match_bw03_diag.jsonl
venv/bin/python scripts/map_episodes_to_points.py --gt ground_truth/20260920_match_points.json \
  --pipeline output/g3r1/match_X/pipeline_output.json \
  --game-state-csv output/g3r1/match_X/results_game_state.csv \
  --serve-anchors ground_truth/20260920_match_serve_anchors.txt \
  --out output/g3r1/match_X_episode_point_map.json
venv/bin/python scripts/relabel_serves.py --map output/g3r1/match_X_episode_point_map.json \
  --pipeline output/g3r1/match_X/pipeline_output.json --out output/g3r1/match_X_serve_relabel.json
venv/bin/python scripts/evaluate_match_points.py --gt ground_truth/20260920_match_points.json \
  --pipeline output/g3r1/match_X/pipeline_output.json \
  --game-state-csv output/g3r1/match_X/results_game_state.csv \
  --out output/g3r1/match_X_match_points.json
venv/bin/python output/g3r1/check_owner_verdicts.py output/g3r1/match_X_serve_relabel.json
# suite
venv/bin/python -m pytest tests/ -o addopts=""
```
