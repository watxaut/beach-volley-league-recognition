# G3 — the TOUCH-COUNT lever: the label loss is Layer 2's possession count, not Layer 1's gesture

Coordinator measurement (#68), written while deciding the next card after #67.
**Committed artifacts only: no `src/` change, no decode, no seek, no GT edit,
held-out session never read.** Sources, both already committed:

* `output/20260920_match_ari_joan_lost/pipeline_output.json` — 207 actions
* `output/g3r1/match_bw03_diag.jsonl` — the match `--diag-dump` (185 `accepted`
  candidates, fields `frame/gesture/touch_number/near_net/team/ball_side/kind/
  rally_id/action`)
* `ground_truth/20260920_match_contacts.json` — 183 held-out owner events
  (P9–P33, region f5240–f26147, effective ±15 f)

Reproduce: `logs/touch_lever_stdout.txt`.

## 1. Timing is NOT the bottleneck (a hypothesis, refuted)

A plausible story after #48 ("41 of 44 missed contacts have a nearby action
7–69 f away") and the 8 far serves that sit 26–34 f late was that emissions are
systematically late. Measured signed delta to the nearest emission, by GT class
(＋ = emission late):

| GT class | n | within ±15 f | median delta |
|---|---|---|---|
| dig | 55 | 46 | **−2 f** |
| set | 46 | 37 | **−2 f** |
| spike | 38 | 33 | **−2 f** |
| overpass | 18 | 13 | −2 f |
| serve | 25 | 12 | **+23 f** |

Only `serve` is late, and only by ~1 s. Correcting any global timing offset buys
nothing: the emissions are already frame-accurate where they exist. The recorded
class accuracy reproduces exactly from raw artifacts — **83/141 = 0.589** (the
`docs/g3_heldout_p9_p33.md` record is 0.590).

## 2. Layer 1 is degenerate: 85 % of contacts are ONE gesture

The 185 accepted match candidates carry only three `VisualGesture` values:

| gesture | n | final actions it becomes |
|---|---|---|
| `bump_set` | **157** (85 %) | dig 73, set 40, spike 24, serve 16, overpass 4 |
| `attack` | 16 | spike 16 |
| `block` | 12 | block 7, spike 4, dig 1 |

So the visual layer does not decide `dig`/`set`/`overpass`/`serve` at all — it
reports "bump-set" and **the whole label decision is `ActionContextResolver._decide`
in `src/recognition/action_context.py:175-219`**, keyed on the possession
`touch` count (`_poss_touch`, lines 127-135). This is exactly what the module
docstring says it is designed for, and it means the 57-contact label bucket
`docs/g3_heldout_p9_p33.md` calls the largest held-out loss is a *Layer 2 rule*
problem, not a perception problem.

## 3. The touch count is the lever (verified by replay)

**CORRECTION (2026-10-02, coordinator, after CARD TC1's executor refused G1).**
The first version of this table labeled a *replay* row "the real pipeline". That
is wrong: the `accepted` rows of `output/g3r1/match_bw03_diag.jsonl` carry **no
`behind_baseline` field** (0 of 185), and `_decide` reads it for its serve
branch, so an offline replay **cannot reproduce the shipped label stream** — it
replays fidelity only **168/185**, and it scores **0/12 on the serves** against
the dump's own 7/12. The measurements below are the corrected ones; the touched
conclusion is unchanged (it is in fact slightly larger on the subset a replay
can faithfully model).

Replaying the *unmodified* `ActionContextResolver._decide` over the 185 accepted
candidates, substituting one input at a time (the GT `touch_number` lives in
`points[].events[].touch_number`, **not** in `points[].contacts[]` — a trap that
silently produced a 0/139 wrong answer before it was caught):

| arm | all 139 found | non-serve 127 (replay-faithful) |
|---|---|---|
| **the shipped stream** (the dump's own `action`, incl. the serve branch) | **85 = 0.612** | 78 = 0.614 |
| replay of `_decide(behind_baseline=False)`, as-emitted touch | 79 = 0.568¹ | **79 = 0.622** |
| replay, **real GT `touch_number`** fed in | 110 = **0.791** | **110 = 0.866** |
| `touch_number` accuracy itself | 96/139 = 0.691 | — |

¹ 0.568 is a **replay artifact, not the production baseline** — the 12 serves
are unreachable without `behind_baseline`, and they are 7/12 in the shipped
stream. Do not quote 0.568 as "production". For reference,
`output/20260920_match_ari_joan_lost/pipeline_output.json` (the 207-action
stream) gives **83/141 = 0.589** on the same GT and tolerance (the recorded
0.590); the three figures differ only in which stream is matched and whether the
`accepted` dump is used.

**On the 127 non-serve contacts, where an offline replay IS faithful, the true
touch number lifts label accuracy 79/127 = 0.622 → 110/127 = 0.866 (+0.244)**
with the resolver untouched. Lever comparison, all measured on the same GT and
the same `pipeline_output.json` base of **83/141 = 0.589** (a perfect arm adds
`found+correct` entries where the contact is currently missed):

| lever | n | class-acc gain |
|---|---|---|
| all 25 region serves perfect | 25 | **+0.177** |
| **all 12 far serves perfect** | 12 | **+0.032** |
| the 13 held-out overpass labels | 13 | +0.092 |
| the 15 `set↔dig` swaps | 15 | +0.106 |
| **the touch count, on the replay-faithful 127** | — | **+0.244** (0.622→0.866) |

So the touch count is the largest lever and the far serve the smallest. (The
near serve is where the serve lever actually lives: 13 of the 25.)

**CORRECTION (2026-10-03, #74b, from `logs/serve_bucket_report.md` §1).** The
**+0.032 far line does not reproduce** as "all 12 far serves perfect": that
substitution measures **12/141 = 0.0851** (near: 13/141 = 0.0922; together
25/141 = 0.1773 ✓). The measured bucket split explains the gap: **all 12 far
serves are NOT-FOUND** (no emission within ±15 f at all), so "far perfect" is a
recall substitution, not a label substitution; the documented +0.032 is closest
to what the far serves the production stream can *convert today* contribute
(≈4.5/141). Until the owner rules on the convention, read the far line as
"≈4.5 far serves convert", not "12/12". The near/far split and the +0.177 total
are confirmed exact.

**CORRECTION 2 (2026-10-03, #74c, from `logs/insert_path_report.md` §4).** The
#74b goal math "full fix 103/139 = 0.741" is numerator-only: the 13 far-side
contacts were NOT-FOUND, so a consistent INSERT arm counts them in the
denominator too (103/152 ≈ 0.678). The measured INSERT path (PG2-style
window-start placement over the existing evidence artifacts) tops out at
**96/150 = 0.640** IN-SAMPLE — 11/17 far hits (every at_seam serve, none of
the 6 in_gap ones; the ceiling is the point map's, not the evidence's), at
placement precision 0.6111 with 0 near misclaims and 0 owner-negative FP.
Even the numerator-only variant reads 96/139 = 0.691, still under 0.70.

Residual confusions after the substitution (all 139): `overpass→spike` 10,
`serve→dig` 9, `serve→spike` 3, `overpass→dig` 3, `spike→block` 2, `spike→set` 1,
`set→overpass` 1. So a perfect touch count is necessary but not sufficient:
`overpass` still fails on its own rule (`touch == 2 and no follow`), and the
`serve` cases fail because the near serve is a touch-1 `bump_set` (and because
the replay cannot see `behind_baseline` at all).

**Second correction.** `_decide` also takes an `own_side_drive_block` argument
(`src/recognition/action_context.py:216` region) that the dump does not record;
the replay passes `False`. Combined with the missing `behind_baseline`, the 7 of
185 replay mismatches are **not** attributable to the touch count and the card
below is written against `behind_baseline=False` explicitly.

## 4. Where the touch error comes from (mechanism, first cut)

Touch errors cluster in the GT points where the pipeline emitted FEWER accepted
contacts than the owner listed — i.e. a missing contact starves `_poss_touch`,
and every later contact in that possession is numbered one too low:

| GT points | touch errors / matched |
|---|---|
| 11 points where `accepted >= GT` | 11 / 37 |
| 14 points where `accepted < GT` | **32 / 102** |

Per-point detail (GT events, accepted in window ±90, matched ±15, touch errors):
P10 12/9/9/2 · P13 4/4/2/2 · P15 4/4/3/2 · P19 18/13/12/**7** · P22 9/6/6/1 ·
P23 7/6/6/**4** · P25 18/12/11/**6** · P26 11/8/7/**6** · P29 6/7/6/**4** ·
P30 18/15/15/**5** · P33 4/5/4/**3**; every other point is clean.
Note P18 (16 GT, 15 accepted) and P24 (7/6) are clean, so it is not a pure count
effect — the *placement* of the missing contact inside the possession matters.

## 5. What this does NOT establish

* **In-sample.** These 139 contacts are the held-out P9–P33 GT, but the replay
  is a post-hoc substitution on an already-scored stream; the +0.223 is an
  upper bound on a rule fix, not a result, and no rule is proposed here (STOP
  list; §5 of AGENTS.md forbids far-serve threshold tuning — this is not that,
  but the same discipline applies).
* The GT `touch_number` is the OWNER's count of touches in the point, so it
  encodes the owner's segmentation, not an independent measurement.
* Nothing about `src/` has changed. The resolver, `touch` semantics and the
  emission path are byte-identical to production.

## 6. Defect found in passing (deferred, do not fix here)

`src/recognition/action_context.py:193-194` contains a **duplicated `return`**:

```python
            if touch < 3 and not own_side_drive_block:
                return VolleyballAction.BLOCK, 0.7
                return VolleyballAction.BLOCK, 0.7
```

Dead code, no behaviour change (the second line is unreachable), so it is NOT a
bug with a symptom — but it is a landmine for the next editor of that gate.
Fix comment-only/cleanup, **inside whichever session next touches `src/` for
another reason** (same rule as the stale `player_off_court_hold_frames` comment
at `src/utils/config.py:101`).
