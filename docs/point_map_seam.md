# PG2 — THE POINT-MAP SEAM: are the pipeline's window starts serve-anchored, or late?

Card PG2 (#67), open points 22 and 21.3.  Committed artifacts only: no `cv2`,
no decode, no seek, no `src/` change, no new pipeline run, no GT edit, the
held-out session never read.  Sources are the two files PG1 and #66 used:

* `output/20260920_match_ari_joan_lost/pipeline_output.json` — 31
  `game_state.points` windows, 578 `far_flight` `serve_events`, 26 061 frames
* `ground_truth/20260920_match_contacts.json` — 33 owner serve anchors
  (far 17 / near 16)

Everything is computed by `scripts/score_point_map_alignment.py`, which IMPORTS
`scripts/score_point_map.py` (and through it `scripts/probe_point_map.py` /
`scripts/score_serves.py`).  No loader, pairing rule or serve-row builder is
re-implemented; the only new code is the chance baseline, the monotone DP and
the seam table.  Transcript: `logs/pg2_report.md`.

## 1. Step 1 (G1) — the pairing-independent count

A window **start** counts if ANY GT serve anchor lies within ±tolerance of it.
No window/point pairing is used at all.

| quantity | [measured] |
|---|---|
| starts within **±15 f** of any GT serve | **14 of 31** |
| starts within ±30 f | 23 of 31 |
| starts within ±60 f | 25 of 31 |
| chance baseline (31 uniform starts over `[0, 26061)`, tol ±15, seed 20261002, 20 000 draws) | **1.21 of 31** (range 0–7) |
| multiple over chance | **11.6×** |
| frame coverage of the ±15 f serve balls | 33 anchors → 1 023 of 26 061 frames = **3.93 %** |

Every quantity the card listed for step 1 reproduced except the sign
convention of 1(e) — see §6.

Per-serve signed offset to the nearest window **start** (`start − serve`,
negative = the window opened before the serve), 33 values:

```
+6 +496 -19 +250 -171 +4 -18 +20 -16 -18 -32 -662 +67 +5 +1
-17 -19 -14 -15 +630 +3 +1 -6 -10 -1 +3 +1 +3 -17 -17 +101 +401 -31
```

## 2. Step 2 (G2) — PG1's ordinal numbers, reproduced

Read through `score_point_map` (PG1's own `ordinal_pairs` / `aggregate`), not
recomputed:

| quantity | [measured] | PG1 |
|---|---|---|
| `start_hits_within_15f` | **1** (of 33) | 1 |
| `offsets_nonnegative` | **31** (of 31 paired) | 31 |
| offset min / max / median | **+6 / +3153 / +1700 f** | +6 / +3153 / +1700 f |
| PG1's reading of the sign | `uniformly late` | same |

The two tools agree exactly.  Nothing was re-tuned; PG1's committed numbers
stay reproducible.

## 3. Step 3 — the monotone order-preserving DP

Order-preserving alignment of the 31 starts to the 33 serve frames, maximising
a tolerance-hinged match reward (`TIGHT_BONUS − |offset|` inside ±15 f,
`−|offset|` outside) minus `skip_cost` per unpaired start or serve.  Pairing is
by frame proximity under a monotone constraint, never by point number.

| skip cost (f) | pairs | pairs within ±15 f | offset min / max / median | offsets ≥ 0 | unpaired starts | unpaired serves |
|---|---|---|---|---|---|---|
| 60 | 27 | **14** | −32 / +101 / **−6 f** | 12 | 4 | 6 |
| 120 | 28 | **14** | −171 / +101 / **−8 f** | 12 | 3 | 5 |
| 240 | 28 | **14** | −171 / +101 / **−8 f** | 12 | 3 | 5 |

[measured] **Stable**: 14 pairs within ±15 f at every skip cost, pair count
27–28, median −6…−8 f.  The card expected "14 of 27-28 pairs, median −6 f" —
the hit count and pair count reproduce; the median is −6 f at skip 60 and
−8 f at 120/240, a 2-frame difference from one additional long pair, which is
not a material change.  A pairing that moved materially with the skip cost
would have been the finding; this one does not.

## 4. Step 4 — the seam

Per GT serve: the signed offset to the nearest window **start** and to the
nearest window **end**, classified `at_seam` (nearest start within ±15 f),
`inside_window` (the serve falls in some `[start, end]`) or `in_gap`.

| side | n | `at_seam` | `inside_window` | `in_gap` |
|---|---|---|---|---|
| **far** | 17 | **11** | **0** | 6 |
| **near** | 16 | 3 | **11** | 2 |
| all | 33 | 14 | 11 | 8 |

**Far serves live AT THE SEAM, not in the gaps.**  PG1's §5 wording ("the far
side's 14/17-gap population") overstates it: 11 of 17 far serves sit within
±15 f of a window **start** — the window opens a few frames after the serve, so
the serve is *just outside* it — and only **6 of 17** sit in a genuine gap with
no start near them.  A far serve is inside a window **zero** times.  The near
side is the mirror image: 11 of 16 near serves sit inside a window, a few frames
after its start (−10 … −19 f), and only 3 sit at a start.  (PG1's `docs/
point_map_alignment.md` §5 and `docs/pg1_correction.md` quoted "near inside a
window 14 of 16"; this table reports 11, because it applies the `at_seam`
class first: a near serve within ±15 f of a start is classified `at_seam`, not
`inside_window`.  The two readings differ by exactly that precedence and are
otherwise identical.)

The load-bearing asymmetry: **the far side is anchored to window boundaries and
the near side is anchored to window interiors.**  That is why a far-side serve
record keyed on *window starts* can work at all, while the near side needs
window membership.

## 5. Step 5 — the far-record consequence (IN-SAMPLE)

One claim per window **start**: the narrow `far_flight` event (`width_start ≤
28` px — the card's fixed cut, not swept) whose `onset_frame` is nearest that
start, when within ±tolerance of it.  A claim is a hit when it also lands
within ±tolerance of a far GT serve.

| anchoring tolerance | claims | far serves hit (of 17) | near serves misclaimed (of 16) | unanchored claims |
|---|---|---|---|---|
| ±10 f | 16 | **11** | **0** | 5 |
| ±15 f | 16 | **11** | **0** | 5 |
| ±20 f | 17 | 12 | 0 | 5 |

[measured] Reproduces the card's expectation at ±10 and ±15 (11/17 far, 0/16
near, 5 unanchored) and #66's transcript row for ±20 (claims 17, 11/17, 6 FP
— the difference is that this table counts one claim per start, so the extra
±20 f claim lands on a start already claimed at ±15 and is not double-counted).

**This table is IN-SAMPLE.**  It is scored on the 17 match far serves — exactly
the population the STOP list (AGENTS.md §5, open point 30) forbids tuning a rule
on.  It is a **re-test target**: a far-serve rule on window starts should be
**pre-registered on the dev half and scored once on the held-out half**, never
adopted from these numbers.  No mechanism is changed by this document.

## 6. Is the opener serve-anchored, or late? — decided by the chance baseline

**The opener is serve-anchored, not late.**  PG1's "uniformly late" reading was
produced by an ordinal pairing (GT point *P* ↔ pipeline point *P−1*) over 31
windows for 33 points, so a single skipped GT point shifts every later pair by
one and the comparison drifts from +6 f to +3153 f by construction — the sign of
an accumulated index shift, not of a late opener.

The pairing-free measurement settles it: **14 of 31** window starts fall within
±15 f of a GT serve anchor against a chance baseline of **1.21 of 31**
(11.6×, 20 000 fixed-seed draws).  If the openers were late or unanchored, the
count would sit at chance; it does not.  The monotone DP agrees at **14 pairs
within ±15 f** and is stable across all three skip costs.  The three sign
conventions of the offset distribution (PG1's "late / one point behind / noise")
are therefore the wrong question: they describe an index drift, not the frames.

**Note on the card's step 1(e).**  The card expected a **−6 f** median for "the
nearest offset per GT serve (sign-free)".  The −6 f figure reproduces exactly
under the **signed** offset to the nearest window **boundary** (start or end,
whichever is nearer: median −6 f) and is the median the DP reports at skip 60.
A **sign-free** per-serve offset to the nearest **start** cannot be negative by
construction; its median is +17 f (and the signed start-only median is −1 f).
So the card's own 1(e) combines two conventions: the word "sign-free" cannot
yield −6 f.  The card's two step-1 STOP conditions — 1(a) = 14 of 31 and the
"−6 f" offset — are both satisfied under the reading that makes −6 f a signed
frame offset (nearest boundary, or the DP).  This is flagged rather than
silently resolved: the anchor is serve-anchored on every reading, and the
decision does not turn on it.

## 7. Verdict

| criterion | required | [measured] | |
|---|---|---|---|
| (i) starts within ±15 f of a GT serve | ≥ 10 of 31 | **14** | ✅ |
| (ii) multiple over the chance baseline | ≥ 5× | **11.6×** | ✅ |
| (iii) DP pairs within ±15 f, all three skip costs | ≥ 10 | **14, 14, 14** | ✅ |

**`PG1_VERDICT_IS_A_PAIRING_ARTIFACT`** (PASS, exit 0).

Consequence, per the card: **SR4-FAR is mis-keyed, not blocked.**  The point map
is *not* the blocker it was called — the far side's 6-of-17 genuine-gap
population is a smaller and better-defined problem than "no point start matches a
serve (1/33)".  The coordinator's next task is to **card the far-serve rule
built on window starts**, pre-registered on the dev half and scored once on the
held-out half.  **No task card is written by this session** (the card forbids
it), and no `src/` mechanism is changed.

Test status: `venv/bin/python -m pytest tests/ -o addopts="" -q` → **1286
passed** (baseline 1237 + 49 new in `tests/test_point_map_alignment.py`).
Transcript: `logs/pg2_run.log`; full report: `logs/pg2_report.md`.
