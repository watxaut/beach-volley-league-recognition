# TC1 — is the possession TOUCH COUNT the label lever? (`TOUCH_COUNT_LEVER_REFUTED`)

Card TC1, executed 2026-10-02 (session 71). Probe: `scripts/probe_touch_rules.py`
(exit 2 on the pre-registered FAIL). Transcript: `logs/tc1_report.md`.
Tests: `tests/test_touch_rules.py`. Committed artifacts only — **no `src/`
change, no decode, no seek (AGENTS.md §9), no new pipeline run, no GT edit, and
the held-out session `20260928_entreno_vall_dhebron` untouched.**

## Verdict

```
touch_rule_gate = TOUCH_COUNT_LEVER_REFUTED/0.6187
```

* chosen rule on **dev + e1..e7 only**: **R4**
* held-out label accuracy: **86/139 = 0.6187** (R0 replay control 79/139 =
  0.5683, so **gain over R0 = +0.050**; the PASS bar was +0.132 and the
  PARTIAL bar +0.082)
* held-out touch accuracy: **103/139 = 0.741** (R0's emitted count was 96/139)
* 127 non-serve contacts: R0 **79/127 = 0.622** → R4 **86/127 = 0.677**

## Step 1 — G1, #68 reproduced (gate GREEN)

Every pinned figure reproduced, including both reference lines:

| quantity | #68 record | measured here |
|---|---|---|
| accepted candidates | 185 | 185 |
| gesture table | bump_set 157 / attack 16 / block 12 | 157 / 16 / 12 |
| timing medians (signed, + late) | dig/set/spike/overpass −2 f, serve +23 f | −2 / −2 / −2 / −2 / **+23 f** |
| held-out GT events in region | 183 | 183 |
| held-out **found** contacts | 139 | 139 |
| `touch_number` accuracy | 96/139 = 0.691 | 96/139 = 0.6906 |
| replay control R0 | 79/139 = 0.568 | 79/139 = 0.5683 |
| GT-touch substitution | 110/139 = 0.791 | 110/139 = 0.7914 |
| the dump's own `action` field | 85/139 = 0.612 | 85/139 = 0.6115 |
| `pipeline_output.json` stream | 83/141 = 0.589 | **0.5899** (139 matched pairs, 177 in-region actions) |
| replay fidelity vs the dump | 168/185 | 168/185 |
| serves, replay vs dump | 0/12 vs 7/12 | 0/12 vs 7/12 |

Two of these needed #68's exact measurement semantics, which the card did not
spell out and which cost the first two runs of the probe:

1. **The timing table is measured on the PRODUCTION stream** (`pipeline_output.json`
   actions), nearest-ANY-emission, over **all** region contacts — found or not.
   On the 12 *found* serves alone the median is **−0.5 f**, not +23 f: the 13
   far serves with no emission within ±15 f sit +23…+125 f late and are what
   makes the class median +23 f. #68's table (`n` = 55/46/38/18/**25**, and
   `within ±15 f` = 46/37/33/13/**12**) only reproduces that way.
2. **The 0.589 reference is `evaluate_timed.score_labels`, not
   `evaluate.py`.** `evaluate.py` on the same data grades a different
   population and gives 0.437. The arm is: GT blob scoped to P9–P33 via
   `scripts/score_heldout_contacts.scoped_gt_blob`, 177 in-region production
   actions, `evaluate_timed.match_events` (one-to-one, effective tolerance
   max(0.2 s, 15/25.67 s) = 15 f) → 139 pairs → 82 correct = 0.5899. The
   `83/141` denominator is `class_scored` after dropping the P30 unspecified
   touch.

**Matcher semantics (the 139 vs 137 matter).** #68's counts are reproduced by
**non-exclusive nearest-within-±15 f** matching (a contact may pair with more
than one GT event; 139 events find 137 *distinct* contacts). `evaluate_timed`'s
one-to-one optimal assignment on the identical data gives **137**. The probe
uses the non-exclusive pass for every G1 figure and reports the one-to-one count
for reference. This is the same class of trap as the AGENTS.md `evaluate.py`
warning: the denominator decides the number.

## Step 2 — the 43 wrong-touch found contacts (the deliverable's centre)

Bucketed in a fixed precedence order, so the partition is total and
deterministic: `previous_contact_missing` → `team_change_not_reset` →
`attack_not_reset` → `over_counted` → `under_counted`.

| bucket | n | what it means |
|---|---|---|
| **`under_counted`** | **20** | emitted `touch` < GT `touch_number` — the possession counter was **starved**, so every later touch in that possession is numbered too low |
| `previous_contact_missing` | 13 | the preceding GT contact of the same point has **no accepted contact at all** (within ±15 f) — the counter could not have seen it |
| `team_change_not_reset` | 5 | GT `touch_number == 1` but the emitted count continued across a **team change** (or, symmetrically, GT keeps possession across what the dump reads as a change) |
| `over_counted` | 4 | emitted `touch` > GT `touch_number` |
| `attack_not_reset` | 1 | GT resets to 1 after an attack the resolver did not treat as one |

The centre of gravity is **starvation (20 + 13 = 33 of 43, 77 %)**, not a wrong
reset rule. The per-row local context (GT frame/action/touch, pred
frame/action/emitted touch, gesture/team/`ball_side`/`kind`, the previous and
next accepted contact in the rally, and the previous GT event with whether it
was accepted) is printed by the probe and stored in
`logs/tc1_report.md`; each row is one of the 43. Representative rows:

```
P10  GT f6320  spike    t2 | pred f6327  spike  t3 | bump_set team B side B bounce  rally 12 | prev f6305 set t2 team B | prevGT f6266 dig  t1 accepted=True  -> over_counted
P10  GT f6330  dig      t1 | pred f6327  spike  t3 | bump_set team B side B bounce  rally 12 | prev f6305 set t2 team B | prevGT f6320 spike t2 accepted=True  -> team_change_not_reset
P23  GT f16776 spike    t3 | pred f16775 dig    t1 | bump_set team B side B bounce  rally 32 | prev f16732 set  t2 team A | prevGT f16734 set  t2 accepted=True  -> under_counted
P26  GT f20001 dig      t1 | pred f19998 set    t2 | bump_set team B side B bounce  rally 39 | prev f19967 dig   t1 team A | prevGT f19966 overpass t3 accepted=True -> attack_not_reset
P29  GT f22223 overpass t1 | pred f22217 set    t2 | bump_set team B side B bounce  rally 44 | prev f22178 dig   t1 team B | prevGT f22180 overpass t1 accepted=True -> team_change_not_reset
```

`under_counted` and `previous_contact_missing` are the same mechanism seen from
two sides: the counter is off by exactly the number of contacts the pipeline
never emitted, so it stays low for the rest of that possession. This is #68's
`32/102` vs `11/37` split, reproduced at contact level.

## Step 3 — the rule search (dev + e1..e7 ONLY)

Every rule is a pure function over the accepted-contact list replayed through
the **unmodified** `ActionContextResolver._decide`, called exactly as the card
specifies:
`_decide(gesture, touch, near_net, behind_baseline=False, rally_start=False, next_contact, frame, own_side_drive_block=False)`.
The two unrecoverable inputs are fixed `False` in **every** arm including R0,
so the arms are comparable; that is #68's known replay limit, not a finding.

`dev_verify` + `e1..e7`, `evaluate --ignore-player` action F1 of the replayed
labels (accepted count == pipeline action count on every clip, so
`f1_accepted_only == f1_replayed_all`):

| rule | reset condition | touch acc (dev) | dev F1 | summed F1 over dev+e1..e7 |
|---|---|---|---|---|
| **R0** | as emitted today | 14/17 | 0.386 | 5.577 |
| R1 | any `team` change | 14/17 | 0.421 | 5.591 |
| R2 | R1 + after any `attack`/`block` gesture | 14/17 | 0.421 | 5.591 |
| R3 | R2 + `rally_id` change | 14/17 | 0.421 | 5.591 |
| **R4** | R3 + `ball_side` cross check (abstain where `None`) | 14/17 | 0.421 | **5.745 ← chosen** |

Per-drill F1 (chosen-rule ladder / recorded STATUS gate record):

| drill | R0 | R1–R3 | R4 | recorded |
|---|---|---|---|---|
| e1 | 0.706 | 0.706 | 0.706 | 0.706 |
| e2 | 0.400 | 0.533 | 0.533 | 0.571 |
| e3 | 0.929 | 0.929 | 0.929 | 1.000 |
| e4 | 0.933 | 0.933 | 0.933 | 0.933 |
| e5 | 0.923 | 0.769 | 0.923 | 0.923 |
| e6 | 0.800 | 0.800 | 0.800 | 0.933 |
| e7 | 0.500 | 0.500 | 0.500 | 0.750 |

**Two observations that matter more than the +0.168 summed F1:**

1. **R1–R3 are indistinguishable from each other on all eight clips** and R4
   differs only on e2 and e5. The ladder's resets are almost entirely
   redundant with the resolver's own `new_rally` / `attack_before` resets —
   the choice among R1–R4 is close to noise, and the "best" rule is chosen by
   a summed-F1 margin of **0.15 over R0** concentrated on a single drill (e2).
2. **On the drills, a reset rule is flatly worse than R0 in one place**: R1–R3
   drop e5 from 0.923 to 0.769 (the ball-crossing-with-`ball_side is None`
   abstention, exactly the 64-of-185 case, turns a touch-3 spike into a
   touch-1 dig). R4's `ball_side` check is what rescues e5 — which is
   evidence that the R4 margin is the `ball_side` abstention, not the resets.

## Step 4 — G2, the held-out shot (one shot, rule chosen on dev+entreno only)

| quantity | R0 control | **R4 (chosen)** |
|---|---|---|
| touch accuracy | 96/139 = 0.691 | **103/139 = 0.741** |
| label accuracy, all 139 found | 79/139 = 0.568 | **86/139 = 0.619** |
| label accuracy, 127 non-serve | 79/127 = 0.622 | **86/127 = 0.677** |
| gain over R0 | — | **+0.050** (bar: PASS ≥ +0.132, PARTIAL ≥ +0.082) |

Residual confusion after R4 (all 139 found): `serve→dig` 8, `overpass→dig` 6,
`set→dig` 6, `spike→block` 6, `overpass→spike` 5, `dig→spike` 4,
`serve→spike` 3, `set→spike` 3, `spike→set` 3, `overpass→set` 2,
`dig→set` 2, `dig→overpass` 1, `set→overpass` 1, `spike→dig` 1,
`spike→overpass` 1, `serve→set` 1. The 8 `serve→dig` are unreachable by any
rule arm, because the replay cannot see `behind_baseline` (#68's caveat).

**Both non-gating arms required by the card**, on the 127 non-serve contacts
where a replay is faithful: R0 **79/127 = 0.622** → GT-touch arm
**110/127 = 0.866**. #68's +0.244 upper bound stands as an upper bound; the
best re-derivable rule recovers **+0.055 of it** (0.622 → 0.677).

## Step 5 — the entreno regression arm

`evaluate --ignore-player` action F1, offline replay vs the STATUS gate record:

| drill | recorded | R4 replay | Δ vs recorded | R0 replay | Δ chosen − R0 |
|---|---|---|---|---|---|
| e1 | 0.706 | 0.706 | +0.000 | 0.706 | +0.000 |
| e2 | 0.571 | 0.533 | −0.038 | 0.400 | **+0.133** |
| e3 | 1.000 | 0.929 | −0.071 | 0.929 | +0.000 |
| e4 | 0.933 | 0.933 | +0.000 | 0.933 | +0.000 |
| e5 | 0.923 | 0.923 | +0.000 | 0.923 | +0.000 |
| e6 | 0.933 | 0.800 | −0.133 | 0.800 | +0.000 |
| e7 | 0.750 | 0.500 | −0.250 | 0.500 | +0.000 |

**Criterion (ii) as literally written is NOT met, and it cannot be met with an
offline replay:** the R0 replay is *itself* off-record on **4 of 7** drills
(e2 −0.171, e3 −0.071, e6 −0.133, e7 −0.250), so "every replay within ±0.01"
fails before the rule is applied. The probe therefore also reports the
rule-relative check — **chosen rule vs the R0 replay** — which is the only part
a delta can be attributed to: **no drill is made worse by R4** (Δ = 0.000 on
six, +0.133 on e2).

This is stated as an **offline approximation**, as the card requires. No
pipeline run was made, so the goal's "≥ 90 % on the drills" is **not confirmed
by this card** — it can only be confirmed by a real run of a rule that is
already chosen, and the verdict below says no `src/` change is warranted.

## Step 6 — is the follow-up a `src/` change? (tier-2 architect call)

**No. Nothing ships.** The card's decision rule makes a PASS the precondition
for proposing a `src/` change, and the gate is a pre-registered FAIL.

The mechanism, in one line, for whoever picks this up:

> **The label bucket is not reachable by re-deriving the possession count,
> because the counter is *starved*, not mis-reset — so the fix is upstream of
> the resolver (emit the contacts that are missing), and `src/` touch-count
> surgery would buy at most the +0.050 measured here while risking the e5-class
> `ball_side is None` regression.**

Supporting reading of the buckets: 33 of the 43 wrong-touch contacts are
starvation (`under_counted` 20 + `previous_contact_missing` 13), and every
reset rule R1–R4 can only move a counter that has been fed the wrong number of
events. The +0.050 that R4 *does* buy comes from the `ball_side` cross check
fixing 5 `team_change_not_reset` and the `ball_side`-abstention preserving the
touch-3 spikes — i.e. from the **attribution** signal, not from the count
arithmetic. An owner/architect decision is therefore needed on the upstream
question (contact recall inside a possession), which is open points 2/5 and the
`previous_contact_missing` bucket — a tier-2 call, not this card's.

## Pre-registered decision, as applied

Thresholds are gains over the R0 replay control (79/139 = 0.568), i.e.
identical to the bars as first written (0.700 / 0.650 absolute), so the
baseline label cannot move the verdict.

| criterion | measured | met |
|---|---|---|
| (i) held-out label accuracy ≥ 0.700 | 0.6187 | **no** |
| (ii) every entreno replay within ±0.01 | R0 replay is off-record on 4/7 | **no** (and unattributable — see step 5) |
| (iii) rule chosen on dev+entreno only | yes | **yes** |

→ `TOUCH_COUNT_LEVER_REFUTED/0.6187`.

**What survives, and what does not.** #68's finding that the possession count is
the largest single lever is **not** overturned: it remains the largest
*diagnostic* lever (+0.244 upper bound on the faithful 127). What is refuted is
that a touch-count rule **re-derived from the emitted contacts** can recover
it — the best of five such rules recovers +0.050 of +0.244 on the held-out
contacts, and the choice among the four reset variants is within noise of R0.
The count is a lever only if the contacts feeding it are right, which makes
contact recall the real blocker (open point 9's `previous_contact_missing`
bucket, 13 of 43).

## Reproduce

```bash
venv/bin/python scripts/probe_touch_rules.py --json output/tc1/report.json
venv/bin/python -m pytest tests/test_touch_rules.py -o addopts=""
```

The probe exits **2** on the FAIL verdict (and on a G1 mismatch), 0 on
PASS/PARTIAL. It imports `ActionContextResolver`, `evaluate`,
`evaluate_timed` and `score_heldout_contacts`; it never re-implements the
matcher or the scorer, never imports `cv2`, and never seeks.