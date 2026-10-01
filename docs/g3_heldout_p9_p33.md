# G1 — first HELD-OUT contact score (match P9–P33)

**Status: DONE (measurement).** No `src/` change, no video decode. Script:
`scripts/score_heldout_contacts.py` (+20 tests, `tests/test_heldout_contacts.py`).
Artifacts: `output/heldout_contacts/{gt_p9_p33.json,pred_perception.json,pred_pass2.json,g1.json}`.

**Headline.** On the 183 owner contacts of P9–P33 — the first points *never*
used to fit any mechanism — the production stream scores **P 0.785 / R 0.760 /
F1 0.772**, class **0.590**, team **0.518**. The held-out contact *detection*
is **better** than the dev clip (F1 0.772 vs 0.597), but **label and team
accuracy are the dominant losses**: 46 correct / **57 wrong-label** /
**36 wrong-team** / 44 missed. And the far serve is still **0/12**: every
held-out far serve is either absent or replaced, 26–34 f late, by the GT
reception the pass-2 layer re-labelled as a serve.

## Why this measurement

S0b (#45) scored the *dev* windows P1–P8 — the same 28 contacts every
mechanism was fitted on (T4 baseline, T5, R1, S1). G0 (#47) made the rest of
the match machine-readable (`ground_truth/20260920_match_contacts.json`, 211
contacts P1–P33), so this is the first score on points that never participated
in any tuning. It is the number every future mechanism must beat, and the
first real measurement of the 12 far-serve contacts.

## Method (same scope discipline as S0b)

* **Scope** = points P9–P33, region = the padded span of their emission
  windows: `f5240–f26147` (pad 90 = `rally_reset_gap`). The span covers all
  183 owner contacts (first contact f5496 > f5240; last f25928 < f26147) and
  no P1–P8 contact (last P8 contact f4910). 177 of the 207 stream actions fall
  in the region.
* **GT is scoped to P9–P33** (a temp copy `output/heldout_contacts/gt_p9_p33.json`),
  so P1–P8 events can never be charged as false negatives. `clip_start/end`
  are added from the match-axis windows because `evaluate_timed.point_intervals`
  only reads the `clip_*` names.
* **Two arms over the identical action list** (`output/serve_relabel.json`):
  `perception` = production events verbatim; `pass2` = `actions_pass2`
  (demotions dropped, overrides applied).
* **Matcher** = `scripts/evaluate_timed.py` (imported, never re-implemented),
  `--ignore-player`, base tolerance 0.2 s raised per event by the owner
  `frame_tolerance=15` → effective **±15 f** at 25.67 fps.
* `--autonomous` deliberately not used (the pass-2 stream carries owner
  anchors/verdicts); the GT-derived-input audit is recorded (69 findings).

**Scope caveat (flagged, measured).** The episode-map emission windows are
*PREDICTIONS* (`window_is_prediction: true`) and drift badly on later points:
only **12/25** windows cover their own owner contact range (e.g. P32 window
f24614–f25085 vs contact f25375; P20 window f15113–f15371 vs contact f14518).
The contact P/R/F1 is window-independent (the region is the whole padded
span), but the point-interval / dead-time metrics inherit the drift, so
`FP/dead-min` here is a soft number.

## Headline score

| arm | P | R | F1 | class | team | FP | FN | dup | FP/dead-min |
|---|---|---|---|---|---|---|---|---|---|
| perception | 0.785 | 0.760 | **0.772** | **0.590** | **0.518** | 38 | 44 | 2 | 1.678 |
| pass2 | 0.790 | 0.760 | **0.774** | 0.561 | 0.561 | 37 | 44 | 2 | 1.580 |
| Δ | +0.004 | 0.000 | **+0.002** | **−0.029** | +0.043 | −1 | 0 | 0 | −0.098 |

Pass-2 remains a wash on contact F1 and again **costs class accuracy**
(0.590 → 0.561): it breaks correct labels faster than it fixes anything. It
does move team accuracy up (+0.043) by overriding far-band attribution.

### Held-out vs dev (the re-ranking)

| | dev P1–P8 | held-out P9–P33 |
|---|---|---|
| contacts | 28 | 183 |
| contact F1 | 0.597 | **0.772** |
| class acc | 0.706 | **0.590** |
| team acc | 0.706 | **0.518** |
| loss budget (waterfall) | 11 proposal / 5 team / 4 label / 8 survives | 44 missed / 36 team / **57 label** / 46 survives |
| normalized | proposal 39 % / team 18 % / label 14 % | missed 24 % / team 20 % / **label 31 %** |

The dev loss budget **over-weighted contact proposal** (39 % of dev losses vs
24 % held-out) and **under-weighted the gesture label** (14 % vs 31 %). A
mechanism fitted to the dev proposal gap is fitting the dev clip's easiest-to-
fix bucket; the held-out data says the largest single error class is the
**label**.

## Contact-level miss taxonomy (perception arm)

```
correct    46   (25.1 %)
wrong_label 57  (31.1 %)
wrong_team  36  (19.7 %)
missed      44  (24.0 %)
```

Only **3 of the 44 missed** contacts have no emitted action within ±80 f. The
other 41 have a nearby action (delta 7–69 f), 25 of them a `dig`. That is the
same "emission sits on the neighbouring contact / wrong side of tolerance"
signature the far serves show; it is **not** an empty-stream failure except for
3 contacts. (Caveat: in dense rallies the optimal matcher may have consumed
that nearby action on an adjacent GT contact, so "nearby" is not proof of a
mis-timed emission — it is a lower bound on stream presence.)

### Recall by action class

| GT action | n | correct | wrong_label | wrong_team | missed | recall* | found |
|---|---|---|---|---|---|---|---|
| dig | 55 | 16 | 11 | 19 | 9 | 0.636 | 0.836 |
| set | 46 | 13 | 14 | 10 | 9 | 0.500 | 0.804 |
| spike | 38 | 10 | 15 | 7 | 6 | 0.447 | 0.842 |
| serve | 25 | 7 | 4 | 0 | 14 | 0.280 | 0.440 |
| overpass | 18 | **0** | 13 | 0 | 5 | **0.000** | 0.722 |
| *(unspecified P30)* | 1 | 0 | 0 | 0 | 1 | — | 0.0 |

\* recall = (correct + wrong_team) / n, i.e. contact found with the right class.
**`overpass` is never emitted correctly on the held-out match** (0/18): all 13
found overpasses come out as `dig`/`spike`/`set`. This is open point 9 and is
worth as much as the far serve (18 contacts, ~10 % of the held-out GT).

### Recall by side

| side | n | correct | wrong_label | wrong_team | missed | found |
|---|---|---|---|---|---|---|
| far | 88 | 25 | 28 | 13 | 22 | 0.750 |
| near | 95 | 21 | 29 | 23 | 22 | 0.768 |

Contact *finding* is side-symmetric (0.750 / 0.768); the side asymmetry is in
**team correctness** — far contacts carry far fewer `wrong_team` (13) than near
(23), which is the mirror of the near/far width-band attribution class
(open point 22).

### Label confusion (GT → pred)

```
set      -> dig x10, spike x3, overpass x1
spike    -> block x7, set x5, dig x2, overpass x1
overpass -> dig x6, spike x5, set x2
dig      -> set x5, spike x4, overpass x1, serve x1
serve    -> spike x3, dig x1
```

## Serves, including the 12 held-out far serves

Effective tolerance ±15 f:

| | n | hits | hit rate |
|---|---|---|---|
| all serves | 25 | 11 | 0.44 |
| near serves | 13 | 11 | 0.85 |
| **far serves** | **12** | **0** | **0.00** |

| GT far serve | nearest emitted "serve" | Δ f | what that emission is |
|---|---|---|---|
| f8506 | f8534 | +28 | production serve (team B), next GT is the near dig f8550 |
| f9103 | f9137 | +34 | pass-2 relabelled the near dig f9138 (prod dig, A→B) |
| f10044 | f10070 | +26 | production serve (team B), next GT is the near dig f10072 |
| f15145 | — | — | nothing within ±80 f |
| f15925 | f15955 | +30 | pass-2 relabelled the near dig f15955 |
| f16659 | f16685 | +26 | pass-2 relabelled the near dig f16687 |
| f18840 | — | — | nothing within ±80 f |
| f19832 | f19860 | +28 | pass-2 relabelled the near dig f19862 |
| f20922 | f20951 | +29 | pass-2 relabelled the near dig f20951 |
| f21356 | f21383 | +27 | pass-2 relabelled the near dig f21385 |
| f24543 | — | — | nothing within ±80 f |
| f25375 | — | — | nothing within ±80 f |

This reproduces the S0b dev finding on **12 independent held-out contacts**:
8/12 far serves have a nearby emitted "serve", but **6 of those are the GT
reception the pass-2 layer re-labelled** and 2 are production serves 26–28 f
late with the opposite team attributed; on 4 far serves there is no serve
within ±80 f at all. The contact-level far-serve gap is now measured, not
data-starved.

The 14 missed GT serves (all 12 far + 2 near) are the single biggest action-
class recall hole (serve recall 0.280).

## What this changes (re-ranked next steps)

1. **G2 far-serve lever decision is now decidable on data.** 12 held-out
   far-serve contacts, 0/12, no pass-2 substitute. T5 (tracker admission), R1
   (departure gate), S1 (looming) all remain refuted; the lever choice
   (targeted far-flight detector mining vs another contact-proposal mechanism)
   should be made with **0.772 F1 / 0.00 far-serve** as the baseline.
2. **The label bucket jumps in priority.** Dev said "proposal first"; the
   held-out data says the largest error class is the gesture label (57/183),
   driven by `overpass` (0/18 recall) and `set`/`spike` confusions
   (`set→dig`, `spike→block`). Any label work should be measured against the
   G1 baseline.
3. **The 44 missed are mostly not empty-stream.** 41/44 have an action within
   ±80 f (7–69 f away), so the loss is timing/placement and dense-rally
   consumption as much as pure proposal.
4. **Pass-2 must still not be consumed as a label source** by S4: it breaks
   class accuracy on the held-out set too (0.590 → 0.561).

## Not reproduced here (explicit gap)

The stage waterfall (`scripts/waterfall.py`: raw detection → admission →
candidate → reach gate → actor/team → label) is **not** reproduced, because
the only full-match diag dump is the R1 `bw=0.3` run
(`output/g3r1/match_bw03_diag.jsonl`); its `low_departure` gate decisions
differ from production, so a production stage waterfall needs a fresh
production diag dump (a full decode, ~30 min). The contact-level taxonomy
above is derived from the score artifacts alone. The script records this as
`waterfall.available = false` rather than faking stage counts.

## Reproduce

```bash
venv/bin/python scripts/score_heldout_contacts.py \
    --json output/heldout_contacts/g1.json
venv/bin/python -m pytest tests/test_heldout_contacts.py -o addopts=""
```
