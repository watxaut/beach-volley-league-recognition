# SR1 — the near-serve miss taxonomy (session 57, 2026-10-02)

> **[#58 CORRECTION]** The bucket counts below stand, but two conclusions do not:
> "not a tracking problem" is false for P5/P7 (the server's PLAYER track coasts
> under the 90 f off-court hold horizon) and e2 (server never tracked), and the
> `behind_baseline` story for P9-P12 was inferred, not measured — the measured
> cause is the toucher's CONTACT-frame foot 0.8-24.5 px inside the threshold.
> See `docs/sr1b_near_serve_causes.md`.

`scripts/probe_near_serve_misses.py` (+21 tests,
`tests/test_near_serve_misses.py`). Task **SR1** of
`docs/serve_reliability_plan.md`, tracked as open point **30**. Diagnose-only:
**no mechanism designed, nothing under `src/` touched.** Artifacts:
`output/serves/sr1.json`, the fresh practice runs `output/sr1/entreno_*/` and the
production diag dumps `output/sr1/*_diag.jsonl`.

## 1. Scope and method

Every near-side serve the owner marked that production did not emit as a
`serve`, in two places:

- the **match** (P1–P33, 16 GT near serves, 8 missed) — from the shipped
  `pipeline_output.json` + `serve_relabel.json`, no decode;
- the **practice** clips — from a **fresh production run of all seven
  `video_entreno_*` clips with `--diag-dump`** (HEAD `006e343`, MPS). This was
  SR0's outstanding action: the old `output/video_entreno_*` artifacts are from
  2026-09-04/06, *before* the v3 ball detector and the pose gates.

`scripts/score_serves.py` is imported, never re-implemented, so the tolerance,
the side vocabulary, the dev/held-out split and "what counts as a hit" are the
same in both scripts.

One sequential production pass over the match **prefix [0, 4000]** (MPS, 14.0
fps, 285 s) supplies the per-frame stage evidence for the two `no_contact`
cases, which are early in the file. It **never seeks** (AGENTS.md §9) and it
passed the **prefix-parity gate: 23/23 actions identical to the shipped
artifact**, so the dump is a faithful production pass, not a probe.

## 2. The taxonomy

| bucket | meaning | match | practice | total |
|---|---|---|---|---|
| `label` | a same-side contact **at** the serve frame, emitted with another action | 5 | 1 | **6** |
| `no_contact` | no same-side contact at all; the contact died earlier in the chain | 2 | 1 | **3** |
| `other_side_contact` | the only nearby contact is on the **other half** | 1 | — | **1** |
| `off_tolerance` | a same-side contact exists but outside ±15 f | 0 | — | 0 |

10 misses out of 21 GT near serves (match 8/16, practice 2/5) → **near serve
recall 11/21 = 0.52** on current production artifacts.

### 2.1 `label` (6) — one mechanism, plus one cascade

The serve label needs **two** conditions and both must hold:
`ActionContextResolver._decide` emits `SERVE` only when
`behind_baseline and rally_start`; otherwise a bump gesture falls to `DIG` and
an attack gesture to `SPIKE`. So every label miss is one of those two, and the
probe separates them:

| GT | emitted | gesture | kind | Δf | gap to previous contact | failed condition |
|---|---|---|---|---|---|---|
| P9 f5496 | `spike` | attack | bounce | 0 | 366 f | `behind_baseline` |
| P10 f6035 | `spike` | attack | bounce | −1 | 478 f | `behind_baseline` |
| P11 f7147 | `dig` | bump_set | bounce | −15 | 204 f | `behind_baseline` |
| P12 f7777 | `spike` | attack | bounce | +3 | 435 f | `behind_baseline` |
| P33 f25807 | `dig` | bump_set | redirect | −9 | **16 f** | `rally_start` (cascade) |
| e2 f32 | `dig` | bump_set | bounce | 0 | — (first contact) | `behind_baseline` (**measured**) |

Two different stories hide in this bucket:

- **5 cases, one mechanism: `behind_baseline` is false.** The contact is found,
  attributed to a player, opens the rally (gaps of 204–478 f, so `rally_start`
  is certainly true), and is still not a serve because the contact point is not
  judged behind the baseline. The geometry explains why: a bump serve *is* a
  reception (ball up after contact, `kind: bounce`) and an overhand toss at the
  far side of the near half can look like an attack (`kind: bounce`, gesture
  `attack`). This is measured directly on e2, whose dump carries the field:
  `"frame": 32, "behind_baseline": false, "near_net": true` — and note
  `near_net: true` at a serve contact, i.e. the px near-net rule is also wrong
  there.
- **1 case, a cascade of our own emission.** P33: production emits a `serve`
  **25 f early** (f25782) and then a `dig` at f25798, 9 f *before* the owner's
  serve frame. The serve counts as a contact 16 f earlier, so `rally_start` is
  false at f25798 and the touch-1 bump gesture falls to `DIG`. The early serve
  is the cause of the dig, not the reverse. (This is also SR0's single
  `serve_outside_tolerance` false emission.)

Pass-2 already relabels 4 of the 6 (`relabeled` → `serve`); it is right about
the label and wrong about everything else (SR0: 14 near false emissions, squad
0.58, far still 0/17). It is not evidence that the mechanism works, only that
the label is recoverable.

### 2.2 `no_contact` (3) — two different stages, both measured

| GT | first failing stage | detail |
|---|---|---|
| P5 f2575 | **4 candidate gate** | `reach`: ball-to-box **448.3 px** vs reach 140 |
| P7 f3747 | **4 candidate gate** | `reach`: **204.0 px** vs 140 (plus `drive` candidates at 259–303 vs 160 on f3749–f3751) |
| e5 f20 | **3 candidate** | `no_ball_sighting` × 15 of the 31 window frames |

- The two match cases are the **reach gate**: the ball is tracked, the contact
  geometry fires (a `bounce` at P5 f2572, a `drive` at P7 f3749), and the
  candidate is refused because no tracked player's box is anywhere near the
  contact point. At f2572 the four tracked boxes sit at x 378–527, 847–911,
  1025–1136, 1133–1191 while the ball is at x 614 and y 265 — 320 px above the
  court's far edge, i.e. the ball is high on a toss and the server is not among
  the four tracks at that moment. This is the same reach-gate family the
  non-serve backlog already carries (open point 7, "jump-aware reach/ghost
  handling"), now measured for the serve.
- e5 is a **tracking** failure one stage earlier: the ball is tracked but the
  contact probe had no sighting in 15 of 31 frames, so no candidate existed.

**Open sub-question (not answered here, and not assumed):** was the server
*detected but untracked* at P5/P7, or absent from the detections entirely? The
diag dump carries only tracked players, so answering it needs one more prefix
pass with `--serve-events` (the `off_area_detections` channel, ~5 min). It
matters because tracker admission is a refuted lever for the far side (T5) and
must not be re-tried here on assumption.

### 2.3 `other_side_contact` (1)

P24 f18135 (near serve): the nearest contact is a **`dig` on the FAR side** at
f18164 (+29 f). No near-side contact exists within ±80 f. Attribution, not
timing and not labelling — bucketing it as `off_tolerance` would have sent the
fix to the wrong machinery, which is why the probe treats it as its own bucket.

## 3. What this changes for the backlog

- **SR0's inference needs one correction.** SR0 concluded from "every near
  serve production emits is within ±2 f" that the 8 near misses are *missing
  emissions*. They are missing **serve** emissions, but 6 of the 10 misses have
  the contact right there in the stream. The loss is **the label**, and one
  third of it is one condition: `behind_baseline` at a rally-opening contact.
- **The near side is not a detection or tracking problem.** In every one of the
  10 misses the ball was tracked, and in 9 of them a contact candidate existed
  (e5 f20 is the only one where the probe had no sighting to work with).
- **The false-serve story is unchanged and separate** (SR0): 8 dead-time
  handlings, 3 mislabeled rally contacts, 1 off-tolerance emission (P33, which
  this session shows also *costs* a real serve through the `rally_start`
  cascade).
- **For SR4**, the input is now concrete: a per-point serve record does not need
  a new proposer on the near side to know *that* a serve happened — 6 of 10
  misses have a contact at the serve frame, and the rally onset times the far
  side at |offset| 3 f (SR0). What it needs is a **side + rally-opening test**
  that does not depend on the emitted label. **That is a design decision for the
  next session, not a finding of this one.**

## 4. Corrections to the record

- **Practice serves are 3/5, not 4/5.** The fresh production runs hit e3 f29
  (+0), e6 f35 (+1) and e7 f25 (+0) and miss e2 f32 and e5 f20. The old
  artifacts (pre-v3) gave 3/5 with a *different* set of hits (e6 was a miss,
  e5 was a hit at f17), so the number was both stale and coincidentally equal.
  `score_serves.py` now prefers `output/sr1/entreno_*` over
  `output/video_entreno_*` and prints each run's `processed_at` + commit.
- **A partial diag dump must never be read as evidence.** The first version of
  this probe reported six phantom `1_raw_detection` stages for match rows past
  f4000, because "no records in the window" and "no detection in the window"
  look identical to the waterfall. `diag_stage` now checks the dump's coverage
  and returns nothing outside it.

Suite **1091**.