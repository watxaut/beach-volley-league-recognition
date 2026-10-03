# #72 — the reach-gate CASCADE is REFUTED offline: admitting the reach-blocked contacts does not fix the labels, it damages them

**Session #72 (2026-10-02).** Diagnose-only, committed artifacts only. No `src/`
change, no decode, no seek, no GT edit, held-out session untouched.

## 1. Why this measurement had to exist

#71 (`docs/g3_reach_gate_bucket.md`) measured that the reach gate blocks **20 of
the 44** held-out GT contacts that have no accepted contact within ±15 f (9.78×
enriched), and that all 20 sit in points where the pipeline emitted fewer
contacts than GT. That closed a chain — recall → touch count → label — and the
tier-2 architect call (`docs/reach_gate_architect_call.md`) then designed a
pose-anchored reach to recover them.

But the architect's own memo carries a caveat that decides the whole track: its
lever buys at most **+0.08 total-correct and ~0.00 class accuracy**, i.e. it does
**not** move the class-accuracy half of the goal. The cascade premise — that
recovering the missing contacts would repair the starved touch count and so the
labels — was never measured. This document measures it.

## 2. The method (an upper bound by construction)

Offline replay of the UNMODIFIED `ActionContextResolver` (imported, never
copied) over `output/g3r1/match_bw03_diag.jsonl`:

* base arm = the **185** `stage == "accepted"` rows;
* arm *K* = the base rows **plus every `reason == "reach"` rejection whose
  overage `distance / reach <= K`** (the gate's own recorded numbers re-score
  offline), replayed in frame order;
* scored against the **182** in-region (f5240–f26147) GT events at ±15 f,
  nearest-emission matching, exactly as #68/#71.

`behind_baseline` is fixed `False` in every arm including the base (the accepted
rows do not carry it — the #70 replay artifact), so the base is a REPLAY
control, not the production baseline; every arm is compared to **that** control.
Gestures are passed as the `VisualGesture` enum (a plain string silently skips
the ATTACK/BLOCK branches — my own #71 harness bug).

## 3. The result

```
[measured] accepted=185 reach_rejected=71 GT_events=182
[measured] BASE replay: found 139  label 78/139 = 0.561  touch 90/139 = 0.647
[measured] K=1.1: + 4 candidates, found 141, label 79/141 = 0.560 (+1), touch 92/141 (+2)
[measured] K=1.2: +14 candidates, found 145, label 74/145 = 0.510 (-4), touch 90/145 (+0)
[measured] K=1.3: +21 candidates, found 148, label 73/148 = 0.493 (-5), touch 89/148 (-1)
[measured] K=1.5: +28 candidates, found 149, label 77/149 = 0.517 (-1), touch 94/149 (+4)
[measured] K=2.0: +48 candidates, found 154, label 79/154 = 0.513 (+1), touch 94/154 (+4)
```

**Every scalar arm is flat-to-worse on labels while the FOUND denominator grows
by up to 15.** At K=1.2 — the gate whose frame precision is 14/14 = 1.00 — all
14 admitted rows DO sit within ±15 f of some GT contact, yet the label count
falls by 4. At K=2.0, 31 of 48 do, and the label rate is still 0.513 vs 0.561.

The base reproduces the recorded replay control (78/139 ≈ TC1's 79/139 = 0.568;
the 1-contact difference is the non-exclusive-vs-nearest matcher policy already
documented in the #69 Learnings, and it does not move any arm).

## 4. Why it fails — the count is not the binding constraint on these contacts

```
[measured] GT events with a wrong touch number at K=0 (found):        49
[measured] ... still wrong after admitting ALL 71 reach rows:         40
```

Admitting every reach candidate — far more than any shippable arm — repairs
**9 of 49** wrong touch numbers. The extra candidates mostly arrive AT or NEAR
the contact but do not land on the correct possession position: the resolver's
count is driven by its own resets (`cross_flip`, `team_change`, `attack_before`,
`rally_start`), and a stray extra contact inside a possession can as easily push
a later touch number UP as correct the starved one. So the "recall → count →
label" chain is real as a statement about the ERROR POPULATION, but **earning the
recall does not earn the count**, and earning the count is what the labels need.

## 5. The verdict

**`REACH_CASCADE_REFUTED`.** The scalar reach relaxation does not fix held-out
class accuracy — it is neutral at best (K=1.1: +1 label, +2 touch for +4 found)
and negative at the precision-clean gate (K=1.2: −4 labels for +14 found). The
architect's own +0.00-class-accuracy caveat is therefore CONFIRMED and slightly
pessimistic: the honest expectation is **negative**.

Consequences:

1. **No `src/` change for the scalar reach. Nothing ships.** The STOP list and
   AGENTS.md §5 discipline apply — the arm is in-sample on the same match.
2. **The pose-anchored arm is NOT justified by this result either.** It targets
   the same 20 contacts through the same resolver, so it inherits the same
   failure mode unless it *also* fixes the count. Its only distinct argument was
   scale-freedom and the airborne toucher; that is not a label argument.
3. **Card RG1 is NOT written** — the offline cascade gate it would have run has
   been run here, and it fails.
4. **The 44 missed contacts stay the RECALL story, not the goal story.** They
   are worth contact P/R (the architect's +0.03 contact F1 branch) and they feed
   fantasy/per-point completeness, but they are not the path to 0.70 class
   accuracy, and the coordinator should not spend a 2-hour GPU A/B on them while
   the goal is the class metric.

## 6. Where the label bucket actually stands (the decomposition that motivated this)

Wrong-label contacts by (touch correct?, Layer-1 gesture, GT, emitted), over the
182 in-region GT events, replay base arm:

```
 9  touch_bad  bump_set  set      -> dig
 6  touch_bad  block     spike    -> block
 4  touch_bad  bump_set  dig      -> spike
 4  touch_bad  bump_set  spike    -> set
 4  touch_ok   bump_set  overpass -> spike
 4  touch_bad  bump_set  dig      -> set
 4  touch_bad  bump_set  overpass -> dig
 3  touch_ok   attack    serve    -> spike
 3  touch_bad  bump_set  set      -> spike
 2  touch_ok   bump_set  serve    -> dig
 ... (19 rows, 55 wrong total)
```

| touch status | wrong labels |
|---|---|
| wrong touch number | **39** |
| correct touch number | **16** |

So **39 of 55 wrong labels carry a wrong possession count**, and a perfect count
is worth +0.244 (#68). But the count cannot be EARNED by more recall (#72), and
TC1 measured it cannot be RE-DERIVED from the emitted contacts either
(+0.050 held-out). The remaining 16 are Layer-1/Layer-2 rule errors with a
CORRECT count (`overpass -> spike` 4, `serve -> spike` 3, `serve -> dig` 2, plus
singletons) — the shape open point 9 already names.

**The honest state of the label bucket:** both routes to the count are now
measured and closed (re-derive: TC1; earn-by-recall: #72), and the residual
rule errors are 16 contacts. No un-measured lever of the required size is
currently known, so the next move on G3 is a RANKING decision for the owner, not
another card.
