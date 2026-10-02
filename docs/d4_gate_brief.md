# D4 gate — decision brief for the architect

**What is being asked:** a decision on the near-side serve mechanism **M-b**, and
a sequencing decision that follows from it. Written by session 61 (an executor)
at the owner's request. **No decision is pre-made here**; §6 states the options
with their measured prices so the architect can choose.

**Read this brief, decide, and return** (§7). Do not start building on the
strength of reading it.

## 1. The problem, in one paragraph

Production serve recall on the 20260920 match is **near 8/16 (0.50), far 0/17
(0.00)**, precision 0.40 (12 false serves), measured by `scripts/score_serves.py`
(open point 30, SR0 #56). The acceptance bar set at #55 is **≥0.90 recall per
side**, side/squad ≥0.95, ≤0.1 false records per point. The near side has two
candidate mechanisms left, M-a and M-b; **both have now been measured and both
came back negative**. The far side has none that work at all.

## 2. The two mechanisms and what is already measured

| | mechanism | card | status | measured result |
|---|---|---|---|---|
| **M-a** | judge `behind_baseline` on the **pre-contact (takeoff) foot**, not the foot on the contact frame | SR1c (#60) | **CLOSED — no mechanism** | reproduction gate FAILED (194/207 match, 6/7 e2, 13/14 e3 vs ≥98%/session). At the pre-registered K=10 the rule gains P11/P12 and **loses P17/P19**: a **+2/−2 trade**. P9/P10 read false at K=5/10/15. Owner decision at #60: **leave as is**. |
| **M-b** | exempt **servers behind their own baseline** from the 90 f off-court hold (`player_off_court_hold_frames`) | SR1d (#61, this session's work) | **DONE — blunt version REFUTED, geometric version undesigned** | see §3 |

## 3. M-b evidence in full (SR1d, `docs/sr1d_hold_horizon_cost.md`)

Two arms: normal horizon (90) and the same code with that **one** config key
raised to 100000. `Config.load` merges — verified, 118 keys in / 118 out, 1
changed, 0 missing. 14 runs (7 clips × 2 arms) + the full 26 061-frame match, all
exit 0, `--device mps`, one decode at a time. **No `src/` change.**

**Entreno (7 clips)** — `scripts/evaluate.py --component actions --ignore-player`:

| | base F1 | hold-off F1 | Δ |
|---|---|---|---|
| e1 | 0.706 | 0.706 | 0.000 |
| e2 | 0.400 | 0.400 | 0.000 |
| e3 | 1.000 | 1.000 | 0.000 |
| e4 | 0.933 | 0.933 | 0.000 |
| e5 | 0.923 | 0.923 | 0.000 |
| e6 | 0.933 | 0.933 | 0.000 |
| e7 | 0.750 | 0.750 | 0.000 |

The action streams are **byte-identical event for event** on all 7 clips, not
merely equal in score.

**Full match** (`--serve-events`, scored by `score_serves.py`'s own GT rows and
matching, never re-implemented):

| | base (90) | hold-off (100000) |
|---|---|---|
| near serves hit | **8 / 16** | **8 / 16** |
| far serves hit | 0 / 17 | 0 / 17 |
| total actions | 207 | 212 (+5) |
| serve emissions | 20 | 22 (+2) |
| false serves | 12 | **14** (+2) |
| hit timing | all within ±2 f | all within ±2 f |

**The aggregate is flat; the composition is not.** Near hits by point:

- base: P3, P16, P17, **P18**, P19, P20, P29, P30
- hold-off: P3, **P7**, P16, P17, P19, P20, P29, P30

- **+P7** — the lift emits `serve` at f3747, P7's GT frame exactly (delta +0).
  This reproduces SR1b's prediction (#58) exactly.
- **−P18** — P18's contact is still emitted, at the **same** f11996, but
  relabels `serve` → `dig`. It is a **`rally_start`** failure, the family #58
  recorded (a handling contact <90 f earlier kills the rally opening; P5 78 f,
  P33 16 f). P5 stays missed in both arms for the same reason.
- The two new false serves are f17749 and f17943, both near.

**e2 bystander check (the regression the 90 f horizon was built for):** the
right-side sideline straddler (track 2, foot x≈1550, y≈715, identified f13) is
fed on **400 / 423 frames at the 90 f horizon** and **423 / 423** with the lift.
The pre-registered rule requires "not fed longer than in baseline" → **FAIL**.

**Two findings the architect should not skip:**

1. **The 90 f horizon no longer kills the e2 bystander.** It is fed on 400 of
   423 frames *today*. The comment at `src/utils/config.py:101` ("kills e2's
   sideline-straddling bystander that held a slot for 415f") no longer describes
   measured behaviour; the horizon now buys ~23 coasting frames. Any exemption
   designed around that comment is designed around a stale premise.
2. **The `rally_start` coupling is part of M-b's price, not a separate bug.**
   A longer hold keeps earlier contacts alive, which is what demoted P18. M-b
   without a rally-opening rule recovers **+1** serve, not +2.

**Ceiling:** the geometric version's realistic outcome is **+1 serve (P7)**,
**+2 (P7, P5)** only if the rally-opening problem is fixed in the same change.
That is 8 → 9 or 10 of 16 (0.50 → 0.56 / 0.63), against a 0.90 bar.

## 4. Evidence inventory — do not re-decode

Everything below exists on disk; §3 needs no new run to re-derive.

| what | where |
|---|---|
| full SR1d report | `docs/sr1d_hold_horizon_cost.md` |
| the 14 runs + diag dumps + logs + json scores | `output/sr1d/{hold_off,base}/`, `output/sr1d/{e2_bystander.json,match_arm_scores.json,eval_fixed.log}` (git-ignored) |
| the one-off probes written for SR1d | `output/sr1d/{make_eval_predictions.py,e2_bystander.py,score_match_arms.py}` |
| near-serve cause analysis (M-a, M-b origins) | `docs/sr1b_near_serve_causes.md` + `docs/sr1b_worker_report.md` |
| M-a measurement + why it closed | `docs/sr1c_takeoff_stance.md` |
| M-b precursors (P5/P7, hold=90, P33 cascade) | `docs/sr1_near_serve_misses.md`, `output/review_sr1b/` |
| far-side evidence state (SR0/#54) | `docs/sr0_serve_scorer.md` |
| open point 30, plan SR0–SR7 | `STATUS.md` §30, `docs/serve_reliability_plan.md` |

**Provenance caveats on the numbers above** (so they are not over-trusted):

- SR1d step 3's frozen `evaluate.py --predictions <run dir>` invocation graded
  **nothing** (0 predictions on all runs and on the SR1-era artifacts): the tool
  looks for an entry named `actions` in a directory, and reads `frame` where
  `src.main` writes `frame_number`. The owner authorised a one-key adapter
  (`output/sr1d/make_eval_predictions.py`, renames the frame key, filters
  nothing); it was validated by the baseline arm reproducing the recorded per-clip
  F1s on 6 of 7 clips. e2 measures 0.400 vs the recorded 0.571 — the documented
  pre-existing action-script path gap, not a new finding.
- The match baseline artifact predates commit `d402f65` (#59 live-debug panel);
  the drift was shown inert on all 7 clips (baseline streams byte-identical to
  the SR1-era ones), so no match baseline re-run was done.
- All runs are MPS. CPU is the deterministic reference if any of this is
  re-derived.

## 5. Constraints any decision must respect

- **Held-out lock:** `resources/full_videos/20290928_entreno_vall_dhebron.mp4` and
  `ground_truth/20290928_entreno_vall_dhebron_serve_anchors.json` have **never
  been run**. Do not run, score or open outputs until rules are frozen and a card
  says "score held-out once".
- **STOP list (STATUS):** no more px-space / contact-geometry far-serve
  thresholds, no selector constants, no tracker admission tuned on the 17 match
  far serves; no relabeling the reception as the serve.
- **One session per working tree** (AGENTS.md §8); **never seek a video** (§9,
  VFR); **pass-2 work is post-hoc** over `pipeline_output.json` (§6).
- `src/` changes need an explicit owner decision and a byte-identical A/B on
  unaffected videos.

## 6. The decision

**Q1 (the gate itself).** Build the geometric M-b exemption in `src/`, or park it?

- **(a) Build.** Accepts a measured ceiling of +1 serve (+2 with a rally-opening
  fix) for roughly two sessions (design + A/B). Also unblocks SR4's near side,
  which consumes the production near label and currently has nothing better to
  consume.
- **(b) Park.** Near side stays 8/16 for now. SR4's near side must be re-specified
  or deferred. The held-out lock stays in place. Effort goes to the far side
  (17 serves, 0 found, cause unmeasured) or to SR5/SR6.
- **(c) Something narrower.** e.g. design only, no `src/` A/B; or a
  rally-opening fix alone (which also targets P33's cascade), without touching the
  hold at all.

**Q2.** If (a): what is the exact geometric predicate — "foot behind own
baseline", sustained how long, by which team side — and does it ship with a
rally-opening rule in the same change, or is that a second card?

**Q3.** Is M-a genuinely closed, or does the +2/−2 trade get revisited with
different feet evidence?

**Q4.** Sequencing against SR4 / SR5 / SR6, and against the far side. Is one
session reserved for the far side's cause measurement?

## 7. What to return

A decision on Q1–Q4, and if the answer is "build": a design, a pre-registered
PASS/FAIL rule with frozen thresholds, and task cards written with the
`task-card` skill — plus a **new owner gate** for the `src/` A/B itself. If the
answer is "park": what SR4's near side does instead, and what the far side gets
next. Do not edit the SR1c/SR1d/D4 cards' results; only add new ones.