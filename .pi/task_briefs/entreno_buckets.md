# Task: entreno failure structure — which mechanisms lose the 0.90 bar?

Diagnose-only worker on the volleyball_recognition repo
(/Users/joan.heredia/Documents/personal/projects/volley_recognition).
STOP on any ambiguity, failed gate, or missing name instead of inferring.

## Background (measured, do not re-litigate)

- The GOAL bar: ≥ 0.90 on video_entreno (and ≥ 0.70 on the match — already
  lever-exhausted, see STATUS item 0a). The recorded per-drill entreno gate
  (STATUS *Learnings*, `evaluate --ignore-player` F1, action-script record):
  **e1 0.706, e2 0.571, e3 1.000, e4 0.933, e5 0.923, e6 0.933, e7 0.750.**
  So 4 of 7 drills are already ≥ 0.90 on the record; the losing drills are
  **e1, e2, e7**.
- The record convention is `scripts/test_action_recognition.py` (the
  GT-validated reference path) + `evaluate.py --ignore-player`. KNOWN AND
  EXPECTED: on e2 the `src.main` production path reads 0.400 vs the script's
  0.571 (STATUS Learning, the f167 gesture flip) — do NOT chase that, do NOT
  use src.main for the record; the script path IS the record.
- The match-side failure mechanisms are fully mapped (see STATUS #74a/#74b):
  possession-count errors (under/over-counted, starved by missing previous
  contacts), `behind_baseline` landing artefact, `rally_start` cascade,
  far-side contacts never emitted. The entreno drills are 1-point clips —
  far-side absence should NOT apply; whether the other mechanisms repeat is
  exactly the question.
- `ground_truth/video_entreno_N_annotations.json` is the GT (e1–e7). Read
  `ground_truth/README.md` FIRST (format + the entreno-anchor warning).
  If any GT key/format detail differs from what a script expects, STOP.

## G1 gates — reproduce EXACTLY before any task work; a mismatch is a STOP (report it)

- G1a: run the reference path on **e2** with the script's own defaults
  (`--device cpu` if the script exposes a device flag; state the device):
  `scripts/test_action_recognition.py` → `evaluate.py --predictions ... \
  --ground-truth ground_truth/ --ignore-player`. Expected: **F1 0.571**.
  Two known traps: (i) `evaluate.py --predictions <dir>` reads an `actions`
  entry with a `frame` key — if the script's output uses `frame_number`,
  convert with the frame-key adapter (never edit the GT); (ii) confirm
  `ball_confidence` = 0.15 in BOTH `Config.DEFAULT_CONFIG` and the script
  kwargs before running (the f539 bug class). If e2 ≠ 0.571: STOP, report
  the drift number — a drifted reference is a coordinator decision, not
  something to bucket on top of.
- G1b: same path on **e3**, expected **F1 1.000** (second anchor).
- G1c: e1 and e7 on the same path — expected **0.706 / 0.750**. If only some
  match, report exactly which drifted and by how much, then STOP.

## Tasks

1. **Current-record table, all 7 drills** (G1a–G1c numbers + e4–e6): per drill,
   F1 / precision / recall on the script record vs the recorded baseline.
   Any drift vs the record is a finding in §1, not a STOP (the STOPs were the
   four gate drills).
2. **Failure buckets for e1, e2, e7** (the drills under 0.90): every GT action
   event classified found-correct / found-mislabeled (GT class vs predicted
   class) / not-found, matched at ±15 f with the existing matching machinery
   (IMPORT from `scripts/probe_touch_rules.py` / `scripts/probe_serve_bucket.py`
   — never re-implement). Per mislabel: predicted class, touch count, team,
   ball staleness if in the dump. Per not-found: nearest emission offset.
   Also the FP side: emitted actions matching no GT event (count + classes),
   since the goal says "minimizing false positives".
3. **Mechanism comparison vs the match:** for each bucket, say whether it
   matches a KNOWN match-side mechanism (count error / landing artefact /
   rally_start / attribution swap) with the evidence, or is NEW (name it,
   describe it, no rule design). Percentages: how much of the e1+e2+e7 loss
   is known-mechanism vs new.
4. **Verdict line, exactly one:**
   - `ENTRENO LOSSES = MATCH MECHANISMS (NNN%)` — the known mechanisms cover
     NNN% of the failing events; name the residual.
   - `NEW MECHANISMS DOMINATE` — name them, with counts.
   - `NOT ANSWERABLE` — say exactly what is missing.
   NO rule design, NO src change. This is a diagnosis.

## Crash-safe progress (REQUIRED — the route has dropped a turn before)

After EACH drill completes, append its rows to `logs/entreno_buckets_report.md`
immediately (§ per drill), so a crash loses at most one drill.

## Constraints

- No `src/` change, no GT edit, no new Config key. The held-out session
  `20290928_entreno_vall_dhebron` stays untouched and unscored.
- The reference record path is `scripts/test_action_recognition.py` only;
  never score `src.main` output as the record (the e2 0.400 divergence is a
  known Learning, report-if-seen, do not chase).
- Sequential decode inside the script path only (it is the existing
  production-faithful path; `tests/test_vfr_seek_guard.py` stays green).
- Final: `venv/bin/python -m pytest tests/ -o addopts=""` green; report count.
- Tests (`tests/test_entreno_buckets.py`): pin the bucket classifier on
  fixture rows (found-correct / mislabeled / not-found / FP), the ±15 f
  matcher import, and the mechanism-tagging logic. Do NOT pin pipeline F1s
  that require a video run.

## Report

`logs/entreno_buckets_report.md`: §0 G1 gate results (including the exact
commands + device); §1 current-vs-recorded table all 7; §2 bucket tables for
e1/e2/e7 + FP side; §3 mechanism comparison with percentages; §4 verdict line.
Finish with the 6-line self-checklist (scope / evidence / AB-discipline /
parity / breaches / hygiene).
