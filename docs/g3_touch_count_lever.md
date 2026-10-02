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

Replaying the *unmodified* `ActionContextResolver._decide` over the 185 accepted
candidates, substituting one input at a time (the GT `touch_number` lives in
`points[].events[].touch_number`, **not** in `points[].contacts[]` — a trap that
silently produced a 0/139 wrong answer before it was caught):

| arm | correct labels (of 139 found) | accuracy |
|---|---|---|
| as emitted (the real pipeline) | 79 | **0.568** |
| with the **real GT touch_number** fed in | 110 | **0.791** |
| `touch_number` accuracy itself | 96/139 | **0.691** |

Feeding only the true touch number lifts label accuracy by **+0.223** with the
prerendered resolver untouched. That is a larger single lever than any other
measured on this GT: the 12 far serves are +0.066 total, the 13 overpass labels
+0.071, the 14 `set↔dig` swaps +0.077.

Residual confusions after the substitution: `overpass→spike` 10, `serve→dig` 9,
`serve→spike` 3, `overpass→dig` 3, `spike→block` 2, `spike→set` 1,
`set→overpass` 1. So a perfect touch count is necessary but not sufficient:
`overpass` still fails on its own rule (`touch == 2 and no follow`), and the
`serve` cases fail because the near serve is a touch-1 `bump_set`.

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
