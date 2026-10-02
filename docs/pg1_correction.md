# PG1 CORRECTION — the "uniformly late" verdict is an artifact of the ordinal pairing

Coordinator verification note (#66), written while reading the PG1 diff and
artifacts (step 4). **No `src/` change, no decode, no seek, no GT edit, held-out
session never read.** Sources are the same two committed artifacts PG1 used:
`output/20260920_match_ari_joan_lost/pipeline_output.json` (31
`game_state.points`) and `ground_truth/20260920_match_contacts.json` (33 owner
serve anchors, far 17 / near 16).

## What PG1 reported, and what is actually there

PG1 paired GT point *P* with pipeline point *P−1* (ordinal) and measured
`start_hits_within_15f` = **1 of 33**, offsets **+6 … +3153 f** on all 31 pairs,
median **+1700 f**, and concluded the map is **uniformly late**.

That pairing is the problem. The pipeline emits **31** windows for **33** GT
points, and the windows are *not* the same vocabulary as the points: once the
pipeline skips one GT point, the ordinal index accumulates a permanent phase
shift, so every later pair compares a window to the *wrong* serve. The +1700 f
median is that accumulated shift, not lateness.

## The three readings, measured

| pairing | pairs | within ±15 f | median offset |
|---|---|---|---|
| ordinal (PG1: window *k* ↔ serve *k*) | 31 | **1** | +1700 f |
| nearest window start per serve | 33 | **14** | −6 f |
| monotone order-preserving DP (skip cost 60/120/240 f, stable) | 28 | **14** | −6 f |

**Chance baseline.** Serve anchors occupy 3.92 % of the match's frames (a ±15 f
ball around each of 33 serves over 26 069 frames). Monte-Carlo of 31 uniform
random starts (20 000 draws) gives **1.22 of 31** within ±15 f. Measured:
**14 of 31**. So the window starts carry real serve information — roughly 11×
chance — and the ordinal reading is a pairing artifact.

## The side split (this is the load-bearing part)

| side | n | nearest window start within ±15 f | inside *some* window |
|---|---|---|---|
| far | 17 | **11** | 2 |
| near | 16 | **3** | 14 |

Far serves sit **at** a window start (offsets −6 … +20 f for the hits) but are
**not inside** the window, because the opener lands a few frames *after* the
serve. Near serves are the opposite: they sit **inside** a window, a little
after its start (−10 … −19 f).

So #64's "far serves live in the inter-point gaps" is half right — they live at
the *seam*: after the previous window closed and within a few frames of the next
one opening. That is a different, much smaller problem than "no binding exists".

## Consequence for SR4-FAR

A far-serve record keyed on **window starts** (not window membership) is
plausible: using a narrow `far_flight` event within ±15 f of a window start as
the claim gives, on the committed artifacts:

| rule | claims | far serves hit | near serves misclaimed | unanchored claims (FP) |
|---|---|---|---|---|
| narrow ff within ±10 f of a window start | 16 | **11 of 17** | **0 of 16** | 5 |
| … ±15 f | 16 | 11 of 17 | 0 of 16 | 5 |
| … ±20 f | 17 | 11 of 17 | 0 of 16 | 6 |

That is **11/17 far at ≤ 5 false** at zero near misclaim — well short of the
16/17 the unbound signal offers, but far better than PM1's "best binding 11/17
with **35** false serves". The residual 6 far serves have no window start near
them at all (the 31-vs-33 shortfall on the far side).

## What this is and is not

* **Is:** a measurement showing PG1's PASS/FAIL gate was decided by an arbitrary
  pairing choice, and that the map's starts are serve-anchored ~11× chance.
* **Is not:** a claim that the map is fixed, or that a far-serve rule ships. The
  11/17-with-5-FP table is **in-sample** on the 17 match far serves, i.e. exactly
  the population the STOP list (AGENTS.md §5 / open point 30) forbids tuning on.
  It is a reason to re-test with a pre-registered rule, not a result.
* The ±15 f tolerance and the 28 px width cut are unchanged and unfrozen.

## Provenance

Commands were run by the coordinator against the committed artifacts; the full
transcripts are `logs/pg1_correction_stdout.txt`. The alternative pairings are
re-derived from scratch in `scripts/score_point_map.py`'s neighbourhood but were
NOT added to it — PG1's artifacts stay as PG1 committed them, and the re-test is
CARD PG2.
