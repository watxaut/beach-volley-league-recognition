# PG1 — the point map scored against the owner's per-point start frames: `point_map_gate = REFUTED/1`

Card PG1 (STATUS.md *## Next task cards*), open point **22** and **21.3**. Scorer:
`scripts/score_point_map.py`. Pins: `tests/test_point_map_score.py`. Raw tables:
`logs/point_map_score_stdout.txt`.

**VERDICT: `point_map_gate = REFUTED/1`** — the map's start frames are not
aligned to the GT's point starts, and they fail the gate by a wide margin. The
card's PASS bar (`start_hits_within_15f >= 20` of 33 **and**
`offsets_nonnegative == 31` of 31) needs **20 of 33**; the measured value is
**1 of 33** (P1 alone, at +6 f).

| pre-registered condition | required | measured |
|---|---|---|
| `start_hits_within_15f` | ≥ 20 of 33 | **1 of 33** ✘ |
| `offsets_nonnegative` | == 31 of 31 paired | **31 of 31** ✔ |
| G2 parity with #64 (`output/pm1/probe.json`) | 31 pairs, `[32, 33]`, identical offsets | **identical, 0 mismatches** ✔ |

Post-hoc, committed artifacts only: **no decode, no seek, no `src/` change, no
new pipeline run, no GT edit**, held-out session `20290928_entreno_vall_dhebron`
never read (AGENTS.md §6, §9). Sources: `output/20260920_match_ari_joan_lost/pipeline_output.json`
(31 `game_state.points`) and `ground_truth/20260920_match_contacts.json` (33 points).

## 1. The anchor (card step 1) — REPRODUCED

[measured] All 33 GT points carry **exactly one** `serve` contact and in **every**
point that serve is the **earliest** contact (0 exceptions; `n_contacts` ≥ 1
everywhere). So the owner already dictated a per-point start frame: the serve
frame, ±15 f by construction. The scorer reads that field and nothing else; the
excluded sources are `points[].match_start_frame` (all 33 carry
`window_source: "episode_map_emission_window"` + `window_is_prediction: true` —
a pipeline prediction, and it differs from the serve anchor on ≥ 20 points) and
`ground_truth/gt_point_start_end.txt` (the game-state VIDEO's GT, 13 mm:ss pairs,
a different video).

## 2. Gate G1 — the metric

Pairing: **ordinal**, GT point *P* ↔ pipeline point *P−1*, #64's pairing
(reproduced through `probe_point_map`'s own `alignment` construction so G2 can
compare offsets exactly). 31 of 33 points pair; **GT P32 (f25375) and P33 (f25807)
have no pipeline point at all** — the 31-vs-33 shortfall.

[measured] **offset min / max / median = +6 / +3153 / +1700 f**, one-signed:
every one of the 31 paired points has `pipeline start_frame − serve_frame > 0`,
i.e. `offsets_nonnegative = 31 of 31`, confirming #64's sign claim exactly.

[measured] **`start_hits_within_15f = 1 of 33`** — only P1 (+6 f). 0 of 17 far
serves and 0 of 16 near serves land inside their own ordinal window; the one hit
is P1 (a far serve) and misses the window by 6 f because the window opens *after*
it. The tightest offset is +6 f and the loosest is +3153 f, i.e. **~0.24 s to
~2 minutes late** at the match's 25.67 fps (AGENTS.md §7, VFR).

## 3. Gate G2 — parity with #64

[measured] PASS: 31 paired points, `gt_points_without_pipeline_point == [32, 33]`,
and all 31 signed offsets equal `output/pm1/probe.json`'s `alignment` list
element for element — **0 mismatches**. The two tools agree; nothing was
re-tuned.

## 4. The #64 gap-side claim, scored

[measured] Per GT point (the serve frame's position):

| figure | far | near | total |
|---|---|---|---|
| serve frame inside **any** pipeline window | **2 of 17** | **14 of 16** | 16 of 33 |
| serve frame inside **any** inter-point gap | 14 of 17 | 2 of 16 | 16 of 33 |
| serve frame inside the gap immediately before its **own** holder window | 1 of 17 | 0 of 16 | 1 of 33 |

The first two rows are #64's pinned numbers ("far 2/17 in-window vs near 14/16";
"16 of 33 serves in inter-point gaps") reproduced exactly. The third row is the
card's stricter wording — the gap *preceding the point that holds the point's own
contacts* — and it is almost empty (only P2): the ordinal holder window opens
**after** nearly every serve, so the serve is not in the gap that immediately
precedes its own holder, it is *inside* that holder's predecessor's gap. Both
figures are reported because they answer different questions.

## 5. Reading: is the map one point behind, uniformly late, or noise?

**Uniformly late**, decided by the sign of the offset distribution
(`reading()` returns this when every paired offset is ≥ 0, which holds on 31 of
31). It is *not* "one point behind": that reading would require all offsets to be
≤ 0. It is *not* noise: 31 of 31 pairs share one sign and the offsets span two
orders of magnitude smoothly (median +1700 f), with the *nearest-window* offsets
(#64's step-1b view, −731 f at P32 to +630 f at P20) the mixed picture that only
appears when a serve is compared to whichever window happens to be nearest — the
ordinal pairing is the one that says where a point is *said to begin*.

[measured] The map is late but **real**: 12 of 31 windows still contain their own
GT point's whole contact set (#64), and 16 of 33 serves sit inside *some* window
(14 of 16 near, 2 of 17 far). The mechanism #64 named is consistent with the
measurement: `game_state_manager` opens a point on the flight burst *before* the
rally's first action, so the opener precedes — never follows — the serve it is
nominally attached to.

## 6. Consequence

* **The map's STRUCTURE is the suspect, not its offset** (card FAIL wording): a
  pure re-timing of the opener by a constant would still need a median shift of
  ~1700 f, and would still leave the far side's 14/17-gap population unclaimed.
  The fix has to make the point open *at* the serve or *at* the rally it heads.
* **SR4-FAR stays BLOCKED on open point 22**, blocker restated: no point start
  matches the GT's (1/33 within ±15 f), so a per-point serve record has no
  reliable point to bind to.
* **A corrected-opener architect card is NOT justified by this run** — that was
  the PASS branch's consequence, and it did not fire. The next task is whatever
  the coordinator chooses for open point 22; SR4-FAR remains behind it.

Test status: `venv/bin/python -m pytest tests/ -o addopts="" -q` → **1237 passed**
(1214 baseline + 23 new in `tests/test_point_map_score.py`).
## 7. Correction (#66/#67) — this verdict is PAIRING-DEPENDENT

**Added by the coordinator during the step-4 review of #65.** §1-§6 above stand
as the #65 record, but the headline must be read with the pairing in mind.

The `FAIL` rests on PG1's **ordinal** pairing (GT point *P* ↔ pipeline point
*P−1*). The pipeline emits **31** windows for **33** GT points, so once the
pipeline skips a point the ordinal index accumulates a permanent phase shift and
every later pair compares a window to the *wrong* serve. That accumulated shift
is what the +1700 f median measures.

Re-measured on the same committed artifacts, pairing-independently
(`docs/pg1_correction.md`, transcript `logs/pg1_correction_stdout.txt`):

| pairing | pairs | within ±15 f | median offset |
|---|---|---|---|
| ordinal (§2 above) | 31 | 1 | +1700 f |
| nearest window start per serve | 33 | **14** | **−6 f** |
| monotone order-preserving DP (skip 60/120/240 f) | 27-28 | **14** | **−6 f** |

Chance baseline: 33 serve anchors cover **3.92 %** of the match's frames; 31
uniform random starts give **1.21 of 31** within ±15 f (20 000 draws). Measured
**14 of 31**, i.e. ~11× chance — the starts are serve-anchored. And by side: far
serves sit **at** a window start (**11 of 17**), near serves sit **inside** a
window (**14 of 16**), so §5's "the far side's 14/17-gap population" is better
described as a **seam** (the few frames straddling a window boundary).

**This does not ship anything.** No mechanism is changed by it, and the
far-record table it permits is **in-sample** on the 17 match far serves (STOP
list, AGENTS.md §5). CARD PG2 re-tests it with a pre-registered gate.
