# SR1c — the takeoff-stance `behind_baseline` read, and why it was closed (#60, 2026-10-02)

Task card SR1c (STATUS `## Next task cards`), diagnose-only, **no `src/` change**.
It asked one question: if the "behind the baseline" judgment were made on where
the toucher stood **just before** the contact instead of at the contact, would
the four missed near serves P9-P12 come back without inventing false serves?

The answer never became decidable, because the card's own **reproduction gate
failed**: the probe could not reproduce the shipped reading on enough contacts to
be trusted as the same measurement. A failed gate is a STOP; nothing was tuned,
re-run or relaxed. The owner then chose to leave the near side exactly as it is.

## What was run

* **One sequential full-match diag pass**, `--end-frame 999999`, MPS, 26061
  frames decoded in 1887.8 s, no seek anywhere (§9). Output
  `output/sr1c/match_full_diag.jsonl`, log `output/sr1c/match_full_run.log`.
* Seven entreno dumps from #57 (`output/sr1/entreno_1..7_diag.jsonl`) — reused,
  not re-decoded.
* `scripts/probe_takeoff_stance.py` (new) + `tests/test_takeoff_stance.py` (22
  tests). It imports the real `CourtCalibration.is_behind_baseline` and never
  re-implements the test.

## Gate G1 (parity) — PASS

`parity_vs_reference.identical: true`: 207 emitted actions in the prefix, 207 in
the shipped artifact, `only_in_run: []`, `only_in_reference: []`.

## Gate G2 (reproduction) — FAIL

`K = 0` must equal the `behind_baseline` the classifier itself emitted. It does
not, on three sessions:

| session | records | agree | rate |
|---|---|---|---|
| match_20260920 | 207 | **194** | **0.9372** |
| entreno_2 | 7 | **6** | **0.8571** |
| entreno_3 | 14 | **13** | **0.9286** |
| entreno_1/4/5/6/7 | 8/8/6/7/6 | all | 1.0 |

Required: ≥0.98 per session. **The gate fails on the match and on two practice
clips**, so the sweep below is reported as evidence about the gate, never as a
mechanism result.

### Why it fails — all 15 disagreements are the same thing

Every mismatching record is `(shipped True, recomputed False)` and every one has
**no usable player position at the contact frame**: the toucher's track is either
carried forward with no fresh detection (11 records) or missing from that frame's
tracked-player list entirely (4 records, `frames_used = 0`). The card's rule
says to use non-carried-forward positions only, so at the contact frame it has
nothing to read and falls back to false.

The shipped value comes from a different source: a contact is confirmed 7 frames
after it happens, and the classifier picks the player's **last genuinely
detected** position (a code comment states this; the measurement below agrees).
On these records that position can be *after* the contact frame. Measured: the
last real position at or before contact+7 reproduces the shipped value on
**12 of the 15**; the remaining 3 (f355, f4067, f20076) sit 1-17 px on the wrong
side of the 615 px far-side threshold.

Rendered proof (6 panels per record, ±3 frames, crop on the toucher):
`output/sr1c/frames/*.png`, script `output/sr1c/render_mismatch_frames.py`.
In every case the player is visible and moving while the box over them is frozen
or absent — e.g. `match_20260920_f4067_tr1.png` (box pixel-identical f4064-f4068
on a player mid-lunge) and `match_20260920_f11410_tr3.png` (track absent f11407-
f11410, re-acquired f11411).

Scale of the phenomenon: 37 of 263 candidate records have no usable position at
the contact frame; 15 of those disagree with the shipped value (the other 22
agree, both being false).

## Owner check on the 15 (ratified in session #60)

The owner looked at the frames and said only **two** of the 15 are serves —
P17 (f11410) and P19 (f13074). The committed contact GT agrees exactly: those
two are `serve`; the other thirteen are `spike`/`dig`/`set`/`overpass`. No GT
file was touched.

That is the decisive fact about the harm: all 13 non-serves carry the wrong
"behind the line" reading **and none of them became a serve**, because the serve
label also requires the contact to open a rally, and that was false on all 13.
The two real serves are the only records where both conditions coincided.

| contact | state at contact frame | opens a rally | emitted | owner |
|---|---|---|---|---|
| 13 records | carried forward / absent | **False** | dig / set / overpass / spike | not serves |
| f11410 (P17) | absent | **True** | serve | **serve** |
| f13074 (P19) | absent | **True** | serve | **serve** |

## Sensitivity table (decides nothing)

Counts per window, match only — `rec` = missed serve recovered, `fbg` = flip
landing on a real non-serve contact, `fdt` = flip on dead time, `ns` = flip on a
serve of the other side or one already emitted:

| K | rec | fbg | fdt | ns |
|---|---|---|---|---|
| 0 (shipped) | 0 | 0 | 0 | 0 |
| 5 (sensitivity) | 1 | 1 | 0 | 0 |
| **10 (pre-registered)** | **2** | **1** | **0** | **0** |
| 15 (sensitivity) | 2 | 1 | 0 | 0 |

All seven practice clips: 0 flips at every K.

Pre-registered rule (freeze, never re-read): PASS = ≥3 of P9-P12 recovered AND
match `fbg` = 0 AND match `fdt` ≤ 1 AND practice false flips = 0, at K = 10.
**Result: 2 of 4 recovered and 1 `fbg` → FAIL either way.**

### The three flips at K = 10

| contact | action before | window position | bucket | ground truth |
|---|---|---|---|---|
| f7132 | dig | y=804 (past 761) | recovered, P11 | serve f7147 (+15) |
| f7780 | spike | y=801 (past 761) | recovered, P12 | serve f7777 (-3) |
| f18164 | dig | — | false break, P24 | dig f18165 (+1) |

P9 (y=750) and P10 (y=747) read false at K = 5, 10 **and** 15 — they are never
within 10 frames of the line on a real position, so this kind of rule cannot
reach them at any window in the card's range.

## The implication that made the owner stop

A stance read that only looks backwards **cannot** keep the two serves that
currently work: at P17 and P19 the toucher has no real position at or before the
contact (the detection returns 1-7 frames later, y=826 and y=809, both past the
line). So replacing the contact-frame read with a backward window trades
**+P11, +P12 for −P17, −P19**: the same near-side total with a different hit
set, not a gain. (First-order only; the cascade from relabelling a serve is
unmeasured.)

The reading of the 13 wrong ones also has an untested second consumer: the same
field feeds whether a touch is treated as sending the ball over the net
(`_last_touch_went_over`). Only the emitted action label was measured here.

## Outcome

**Closed, nothing shipped.** No mechanism was designed, no `src/` file was
touched, no threshold or window was adjusted. Owner decision: leave the near
side as is. If this line is ever picked up again, the two things to measure
first are (a) how many *other* contacts in the match a more permissive read
would change, and (b) the knock-on effect of adding or removing a serve on the
following contacts' rally-opening test.

Evidence: `output/sr1c/takeoff_stance.json` (git-ignored, like all of `output/`).
