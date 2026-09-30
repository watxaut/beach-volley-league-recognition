# G3 S0b — pass-2 serve re-label stream, scored at CONTACT level

**Status: DONE (measurement).** No `src/` change, no video decode. Script:
`scripts/score_pass2_contacts.py` (+28 tests, `tests/test_pass2_contact_score.py`).
Artifacts: `output/pass2_contacts/{pred_perception.json,pred_pass2.json,s0b.json}`.

**Headline: the point-level serve story does not survive contact-level scoring.**
Far serves **0/5**; GT serves with *any* action near them **6/8** (and only 1 of
those is a *correct* serve). Pass-2 is a wash on contact F1 (**+0.007**) and
**costs 0.14 of class accuracy**, because it re-labels three *correct* dig
contacts as serves.

## Why this script exists

`output/serve_relabel.json` (session 28) reports `far prefix census 8/8` and
`31 serve-typed actions`. Session 42 hand-checked P1–P8 and found the census is
point-level bookkeeping: at contact level the five relabeled far "serves" sit
31–50 f after the GT serves, i.e. **0/5**. This script turns that hand check
into a reproducible number over the *whole* stream, using the time-matched
matcher of `scripts/evaluate_timed.py` (imported, never re-implemented, so the
numbers are comparable with the T4 waterfall and with the 8/8 T4 record).

Two arms over the identical scoped action list:

| arm | stream |
|---|---|
| `perception` | production events verbatim (`action`, `team`) |
| `pass2` | `actions_pass2`: owner-FALSE demotions dropped, `pass2_action` / `pass2_team` applied |

## Scope (and a scope trap)

Score region = the first 8 GT point windows **padded by 90 f** (`rally_reset_gap`)
each side: `f126–f4910`, 29 of the 207 stream actions, all 28 owner contacts
inside.

The raw point windows are **not rally-inclusive** — 7 of the 28 owner contacts
fall outside them, including the P1 serve at f210 (a serve happens *before* the
point window opens) and the P6 tail (f3131/3172/3228, after it closes). Scoring
"inside the window" would have manufactured 7 false negatives and ~6 false
positives. The padded region is validated, not assumed: the `perception` arm
reproduces the recorded T4 dev-clip baseline **exactly** (P 0.586 / R 0.607 /
F1 0.597, 1 duplicate, 2.703 FP per dead minute, class 0.706, team 0.706) —
the parity gate is asserted in the script and in the tests.

Matching: `evaluate_timed`, base tolerance 0.2 s, raised per event to
`frame_tolerance/fps` = 15/28.84 = **0.52 s** (the owner dictation is coarse).
`--ignore-player` (GT `player_id` is a track id at the contact frame, not an
L-R index). `--autonomous` is **deliberately not used** — the pass-2 stream
carries owner anchors/verdicts; instead the GT-derived-input audit of the
relabel artifact is recorded in the report (69 findings) so the GT assistance
is visible rather than hidden.

## Result

| arm | P | R | F1 | class | team | FP | FN | dup | FP/dead-min |
|---|---|---|---|---|---|---|---|---|---|
| perception | 0.586 | 0.607 | **0.597** | 0.706 | 0.706 | 12 | 11 | 1 | 2.703 |
| pass2 | 0.640 | 0.571 | **0.604** | 0.562 | 0.625 | 9 | 12 | 1 | 1.351 |
| Δ | +0.054 | −0.036 | **+0.007** | **−0.143** | −0.081 | −3 | +1 | 0 | −1.352 |

Confusion (GT → pred), pass-2 arm:

```
dig      -> serve 3, dig 2, spike 1
set      -> set 3
spike    -> spike 3
serve    -> serve 1
overpass -> spike 1, set 1, dig 1
```

### Far serves: 0/5, and the deltas are not a tolerance problem

| GT far serve | nearest pass-2 "serve" | Δ frames | Δ s |
|---|---|---|---|
| f210 | f247 | +37 | 1.28 |
| f880 | f930 | +50 | 1.73 |
| f2154 | f2195 | +41 | 1.42 |
| f3038 | f3070 | +32 | 1.11 |
| f4770 | f4801 | +31 | 1.08 |

Effective tolerance is ±5.8 f (±0.52 s). The smallest gap is 5.4× the
tolerance, so no tolerance choice consistent with the owner dictation
recovers these; they are **different contacts** (three of them are the GT
receptions f245 / f3071 / f4800).

### All 8 GT serves, not just the far ones

* only **1/8** GT serves is matched by a correct serve action (f1395, near, emitted);
* f2575 (P5) and f3747 (P7) have **no action at all** within ±80 f — they are the
  two `anchor_only` points, where the far-prefix census counted the *anchor*,
  not an action;
* 6/8 have some action within ±80 f, but 3 of those are the relabeled
  receptions above and 2 (f930, f2195) are in-point-spurious digs that pass-2
  turned into serve-labelled false positives.

So the "8/8 far prefix census" and the "31 serve-typed actions" describe
*decisions recorded in a JSON file*, not contacts in the stream.

### What pass-2 changed, contact by contact

| GT contact | GT action | perception | pass2 | change |
|---|---|---|---|---|
| f245 | dig | f247 dig | f247 serve | **label BROKEN** |
| f3071 | dig | f3070 dig | f3070 serve | **label BROKEN** |
| f3852 | set | f3856 serve | — | **LOST** (owner-FALSE demotion of the f3856 serve) |
| f4800 | dig | f4801 dig | f4801 serve | **label BROKEN** |

Everything else is unchanged. Net effect: the demotions do their job (FP per
dead minute 2.703 → 1.351, precision +0.054), but the three relabels trade
three *correct* dig labels for zero correct serves, and the f3856 demotion
removes a contact-true / label-wrong match, costing one true positive.

Missed by both arms (11): all five far serves, two near serves (f2575, f3747),
f3228 set, f3782/f3950 digs, f4002 set.

## Conclusions (what this changes)

1. **Point 22 is confirmed at contact level, with a number:** the far-serve
   CONTACT does not exist in the stream (0/5, gaps 5.4–8.6× the tolerance).
   The pass-2 layer cannot be its substitute — that closes the "park at pass-2"
   option for good.
2. **The pass-2 relabel layer is net-negative on labels.** It should not be
   consumed as a label source by the S4 fantasy/ace chain as it stands; the
   relabel decisions need the real serve contact first (or the re-label must be
   gated on "no GT-consistent dig nearby", which is a pass-2 design question for
   the owner, not a perception fix).
3. **Scope discipline:** the point windows are not rally-inclusive. Every future
   contact-level score of a pass-2 layer must use a padded region (or per-point
   Voronoi cells) and must re-assert the T4 parity gate; otherwise the numbers
   are not comparable with anything already recorded.
4. **Unchanged:** S0 (owner contact GT for P9–P33) is still the gating input for
   any far-serve mechanism, and it is now the *only* way to check a candidate
   lever honestly — every lever so far (T5, R1, R2, S1) died on a proxy.

## Reproduce

```bash
venv/bin/python scripts/score_pass2_contacts.py --json output/pass2_contacts/s0b.json
venv/bin/python -m pytest tests/test_pass2_contact_score.py -o addopts=""
```

Inputs: `output/serve_relabel.json` (session 28) and
`ground_truth/video_ari_joan_8_first_points_annotations.json` (owner
dictation, session 33). No `src/` file is read for decisions and none is
written — the pass-2 layers stay post-hoc (AGENTS.md section 6).
