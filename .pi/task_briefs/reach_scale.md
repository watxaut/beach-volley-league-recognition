# Task: far-side reach-gate asymmetry — is the 140 px threshold side-blind?

Diagnose-only worker on the volleyball_recognition repo
(the repository root).
Pure measurement over EXISTING artifacts. No decode, no src change, no GT edit.
STOP on any ambiguity, failed gate, or missing name instead of inferring.

## Background (measured, do not re-litigate)

- #74d (`logs/entreno_buckets_report.md`): the entreno losing drills (e1/e2/e7)
  fail mostly on NEW mechanisms; one of them, `contact_gate` (4 events), splits
  into reach-gate rejections, ball-out-of-frame, and dead geometry. **ALL 7
  reach-gate rejections across the three clips target team B (far side), never
  A**: e1 f161/f399, e2 f79/f390/f402/f403, e7 f163. Measured examples:
  e2 f90 needs 179.4 px vs reach 140.0 (target B); e7 f160 needs 182.3 vs 140.0
  (target B). Zero near-side rejections.
- The same side asymmetry dominates the 20260920 match (open points 2/5, §5:
  far ball width 14–23 px vs near 39–52; the far-side story now spans BOTH
  goal halves).
- HARD CONSTRAINT from project memory: a ground-metre REACH mechanism is
  OWNER-GATED (the px→m move was GT-refuted for `near_net`, F1 0.929→0.857;
  AGENTS.md long-axis memory). This task MEASURES whether the asymmetry is
  explained by pixel scale — it designs NOTHING.

## QUESTION (one line)

Once each side's pixel scale is accounted for (court calibration), are the
7 far-side reach rejections the SAME physical reach as near-side accepted
contacts (scale-explained), or do they demand genuinely more physical reach?

## G1 gates — verify before any task work; mismatch is a STOP (report it)

- G1a: `output/entreno_buckets/buckets.json` exists and carries the 7 rejection
  rows for the frames listed above, with ball-to-target px distances
  (179.4 / 182.3 for the two named ones). If the artifact lacks a needed
  field, STOP — do NOT re-run any pipeline.
- G1b: `calibrations/video_entreno_{1,2,7}.json` all exist (they do — verify
  loadable with the existing CourtCalibration loader, IMPORTED, never
  re-implemented).

## Tasks

1. **Ground-metre conversion.** For each of the 7 rejected (far) contacts AND
   for the accepted contacts of the same three drills (near and far
   separately): convert the ball-to-contact-player px distance to ground
   metres via the per-video CourtCalibration (project both points through the
   calibration; state the method and which calibration entry you use — feet
   ground point, same convention as the tracker's `get_team` ground plane).
2. **Distributions + effect size.** Near-accepted vs far-rejected px
   distances; the same in metres. Cliff's delta both ways. The decisive
   comparison: is the far-rejected set's METRE distance inside the
   near-accepted metre range (i.e. physically ordinary reaches killed by px
   scale) or outside it (physically extraordinary)?
3. **Sensitivity, not tuning.** Report what reach threshold in px would make
   the 7 far rejections pass, and what that threshold would do to the
   near-side FP exposure (how many near-side non-contacts sit within that px
   band in the same dumps) — one table, no rule proposed.
4. **Verdict line, exactly one:**
   - `SCALE-EXPLAINED` — far rejections are metre-equivalent to near
     acceptances; the 140 px constant is side-blind and the asymmetry is the
     known pixel-scale coupling (state the numbers).
   - `NOT SCALE-EXPLAINED` — far rejections are physically farther too
     (state the numbers).
   - `NOT ANSWERABLE` — say exactly what is missing.
   NO mechanism design. The ground-metre reach is owner-gated; this result
   only quantifies the asymmetry for that decision.

## Constraints

- Existing artifacts only (`output/entreno_buckets/`, the script action logs,
  `calibrations/`). NO pipeline re-run, NO video decode, NO
  `cv2.CAP_PROP_POS_FRAMES` (`tests/test_vfr_seek_guard.py` stays green).
- No `src/` change, no GT edit, no new Config key. The held-out session
  `20290928_entreno_vall_dhebron` stays untouched.
- IN-SAMPLE labeling: these are 3 drills, not a threshold study; say so.
- Tests (`tests/test_reach_scale.py`): pin the px→metre conversion helper on
  a fixture pair (imported calibration loader, synthetic points), and the
  verdict table structure. Do NOT pin pipeline outputs.
- Final: `venv/bin/python -m pytest tests/ -o addopts=""` green; report count.

## Report

`logs/reach_scale_report.md`: §0 G1 gates; §1 conversion table (all 7
rejections + accepted same-drill contacts, px and metres); §2 distributions +
Cliff's delta; §3 sensitivity table; §4 verdict line; 6-line self-checklist.
