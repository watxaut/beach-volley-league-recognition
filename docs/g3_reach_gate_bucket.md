# The reach-gate bucket — the contact-recall lever (#69, coordinator-verified)

Written 2026-10-02, session 71, by the coordinator, from **committed artifacts
only** (`output/g3r1/match_bw03_diag.jsonl` and
`ground_truth/20260920_match_contacts.json`). No decode, no seek, no `src/`
change, no GT edit, no new pipeline run. Held-out session untouched.

## 1. Why this exists

CARD TC1 returned `touch_rule_gate = TOUCH_COUNT_LEVER_REFUTED/0.6187` and its
step 2 named the mechanism: **33 of the 43 wrong-touch found contacts (77 %) are
STARVED, not mis-reset** (`under_counted` 20 + `previous_contact_missing` 13).
The fix is therefore **upstream — emit the missing contacts** (open points 2/5),
not a better counter. TC1's own next-task line: "the next probe is a
contact-recall/attribution diagnosis on the same 14 `accepted < GT` points."

This document is that diagnosis's first measurement, and it localises the loss to
a single named gate.

## 2. The measurement

183 held-out GT events (f5240–f26147) vs the 185 `accepted` contacts of the
match dump, ±15 f. **44 GT contacts have no accepted contact within 15 f**
(median nearest-accepted distance 33 f; 145/183 within 20 f, 159 within 30 f,
173 within 45 f, 178 within 60 f).

**Where those 44 go — a rejected-candidate row sits within 15 f of all 44.**
The reject-reason density is the signal, and it must be read against its own
base rate because **99.3 % of the video carries at least one rejected row** (so
"there is a rejection nearby" is uninformative by itself). Expected hits are
`coverage × 44`, where coverage is the fraction of all region frames lying
within ±15 f of at least one rejection of that reason:

| reason | rejections in region | frame coverage | expected hits / 44 | **observed at the 44 misses** | enrichment | observed at the 139 found |
|---|---|---|---|---|---|---|
| `reach` | 71 | 4.65 % | 2.05 | **20** | **9.78×** | 6 |
| `low_departure` | 60 | 3.16 % | 1.39 | 4 | 2.88× | 1 |
| `no_contact_geometry` | 7 720 | 55.62 % | 24.47 | **43** | 1.76× | 139 |
| `no_ball_sighting` | 16 530 | 85.29 % | 37.53 | 37 | 0.99× (chance) | 77 |
| `min_contact_gap` | 1 480 | 27.22 % | 11.98 | 5 | 0.42× (depleted) | 139 |
| `pre_history` | 15 | 0.00 % | 0.00 | 0 | — | 0 |

**Two reasons are enriched, and they are different levers.** `reach` (9.78×)
is a *narrow, actionable* gate: 20 of the 44 misses carry one, and each row
carries its own `distance`/`reach`, so a relaxation is directly re-scorable.
`no_contact_geometry` (1.76×) blocks **43 of the 44** but it is the *residual*
reason — every rejection that is not one of the named early-outs lands there,
so its enrichment is mild and it is not itself an actionable threshold.
`no_ball_sighting` sits exactly at chance (0.99×) and `min_contact_gap` is
**depleted** (0.42×, i.e. anti-correlated with a miss).

Note the reach row is the one that moved: an earlier count in this same
investigation read 13 of 44 because it attributed each miss to a single
"nearest rejection", which discards the frame-coverage base rate. The
coverage-normalised 20 / 9.78× above is the version to quote.

## 3. The overage curve (in-sample, on the match)

`reach` is `CONTACT_REACH = 140.0` px (`src/recognition/action_classifier.py:53`;
`SERVE_REACH_PX = 160.0` at line 158 for a rally-opening `drive` kind,
selected at lines 416-419). Every rejected row carries its own
`distance`/`reach`, so the gate can be re-scored offline without re-running:

| gate | admits | of which GT-correct | precision |
|---|---|---|---|
| 1.0× (shipped) | 0 | 0 | — |
| 1.1× | 4 | 4 | 1.00 |
| **1.2×** | **14** | **14** | **1.00** |
| 1.3× | 21 | 19 | 0.90 |
| 1.5× | 28 | 23 | 0.82 |
| 2.0× | 48 | 32 | 0.67 |
| 3.0× | 68 | 49 | 0.72 |

The 71 reach rejections in the region contain **49 GT contacts**; the 44 misses
contain **20 that ANY reach relaxation could recover** (the other 24 have either
no candidate geometry at all or a non-`reach` blocker).

The 20 misses that carry a reach rejection, each with the **nearest** reach
rejection and its overage (sorted, the actionable form):

| overage | GT frame | GT action | rejection frame | kind | distance/reach |
|---|---|---|---|---|---|
| **1.00** | f19162 | spike | f19157 | bounce | 141/140 |
| **1.03** | f12160 | overpass | f12155 | bounce | 144/140 |
| **1.10** | f20094 | overpass | f20093 | bounce | 154/140 |
| **1.14** | f19183 | dig | f19181 | bounce | 159/140 |
| **1.16** | f23501 | set | f23497 | bounce | 162/140 |
| **1.19** | f15925 | **serve** | f15926 | bounce | 166/140 |
| **1.20** | f20133 | dig | f20134 | bounce | 169/140 |
| **1.23** | f6104 | set | f6103 | bounce | 172/140 |
| **1.29** | f13709 | set | f13719 | bounce | 181/140 |
| **1.32** | f19360 | spike | f19357 | drive | 185/140 |
| 1.50 | f13158 | set | f13155 | redirect | 210/140 |
| 1.59 | f13666 | dig | f13667 | bounce | 222/140 |
| 1.68 | f23545 | (none) | f23536 | drive | 235/140 |
| 1.95 | f6145 | spike | f6141 | drive | 273/140 |
| 1.96 | f23122 | spike | f23121 | bounce | 274/140 |
| 1.99 | f13236 | overpass | f13238 | redirect | 278/140 |
| 2.42 | f19075 | spike | f19083 | bounce | 339/140 |
| 2.43 | f23261 | dig | f23258 | bounce | 340/140 |
| 2.44 | f24870 | dig | f24862 | bounce | 342/140 |
| 2.90 | f6369 | set | f6369 | bounce | 407/140 |

Kinds: `bounce` 14, `drive` 3, `redirect` 3. Median overage **1.28×**.
Recoverable misses by gate: **1.05× → 2, 1.1× → 2, 1.2× → 6, 1.3× → 9,
1.5× → 10, 2.0× → 16 of the 20.** (§3's 0.90-precision 1.3× row counts
*admitted candidates*, not recovered *misses*; the two are different
populations and both are reported.)
The other **24 of 44** have no candidate geometry at all and are out of this
gate's reach.

**A 1.3× gate (182 px) admits 19 of 21 in-sample at precision 0.90.**

## 4. What this lever buys — and what it does NOT

Estimating the goal metric if the in-sample 1.2×-1.3× admission held exactly:
found 139 → ~153-158, of which ~14-19 correct → class accuracy stays
**≈0.60-0.62 (no gain)**, while total-correct goes **85/183 = 0.464 →
~99-104/183 = 0.54-0.57 (+0.08)**. The reach lever is a **RECALL lever, not a
precision lever**: it buys the total-correct half of the goal metric and does
nothing for the class-accuracy half.

This is why it must not be sold as the label fix. To reach 70 % of 183 = 128
correct, the reach bucket supplies at most ~+20; the rest must still come from
the label bucket (open point 9).

## 5. Constraints, hazards, and what is NOT claimed

* **IN-SAMPLE.** All of §2-§4 is measured on the same 44 misses it would fix.
  Per AGENTS.md §5/§6 and the TC1/PM1/SR4 precedents, an in-sample admission
  curve is a **re-test target, not a shippable rule** — it needs a control
  window and out-of-sample validation before anything acts on it.
* **VENUE-COUPLED, and that is the deep hazard.** `CONTACT_REACH = 140 px` is a
  px-space constant; the court projects **206 px deep on the beach vs 464-479 px
  at the practice venue (2.3×)** (AGENTS.md §7). The same 1.3× therefore means a
  *different physical reach* at each venue. A global relaxation is the exact
  class of change AGENTS.md warns about, and it must be tested as one.
* **IT IS NOT BYTE-IDENTICAL ON THE DRILLS.** Reach rejections exist on every
  drill (dev 18, e1 2, e2 4, e4 1, e5 1, e7 1; e3 and e6 clean), and a 1.3× gate
  would admit 3 on e2 and 1 on e4. So the entreno 90 % gate is **live** and can
  only be settled by a real run, never by an offline replay.
* **An offline probe cannot reproduce the delivered F1.** The rejected rows
  carry `kind`/`distance`/`reach`/`track_id`/`player_id`/`target_team` but **not
  `contact_point`**, so an admitted candidate cannot be pushed through
  `_build_contact` → the resolver → the confidence threshold offline. Any
  offline number is an upper bound on contacts, not on correct actions.
* **`behind_baseline` IS recoverable — a correction to #68/#69.** The
  `candidate_passed_gates` rows of the same dump DO carry `behind_baseline`
  (44 True / 141 False across the same 185 frames) and `contact_point`, joined
  to `accepted` by frame with **0 gesture mismatches**. The `accepted` rows do
  not, which is why the TC1 replay is 168/185 and scores 0/12 on serves. A
  future replay that joins the two stages gets the flag for free — but **it
  still cannot recover the 0/12 serves**, because `_decide`'s serve branch also
  needs `rally_start`, which no row carries.
* **Coordinator hygiene note.** My own first replay measured 150/185, not the
  recorded 168/185. The cause was **my harness bug** (passing the gesture as a
  `str` instead of `VisualGesture(...)`, which silently skips the
  `ATTACK`/`BLOCK` branches), not a data problem. Re-run with the enum: 168/185.
  Lesson: when a re-measurement disagrees with a verified artifact, suspect your
  own harness before the artifact.

## 6. The one-line state

**The reach gate is a measured 9.78×-enriched blocker of missed contacts, and a
modest relaxation recovers up to 20 of the 44 (16 at 2.0×) with precision
0.90-1.00 IN SAMPLE — a recall lever worth ~+0.08 total-correct and ~0.00
class-accuracy.** It is not yet a rule: it is unvalidated out of sample,
venue-coupled, and measurably not byte-identical on the drills.

## 7. Can the threshold be SELECTED out of sample? (two different answers)

The coordinator split the same dump at the match's own P≤8 boundary (**cut
f4910**) and at the standalone clips:

| arm | reach rejections | 1.3× adm/GT | 2.0× adm/GT | all adm/GT |
|---|---|---|---|---|
| **match dev P≤8** (f≤4910) | 15 | 0/0 | **12 / 0** | 15 / 0 |
| **match held-out P9-33** | 56 | 21/19 | 36 / 32 | 56 / 49 |

**The match's OWN dev split cannot select the gate: at every threshold it admits
12-15 candidates carrying ZERO GT contacts.** So a "choose on P≤8, score on
P9-33" protocol returns *no* relaxation, and the 1.2×-1.3× curve in §3 is
reachable only by having already seen P9-33 — i.e. it is in-sample, exactly as
flagged.

The **standalone dev clip + 7 drills** (which IS the project's legitimate
selection corpus, per the TC1 / D4 / SR1 precedent) gives a different answer:

| clip | reach rej. | GT | 1.3× | 1.5× | 2.0× | all |
|---|---|---|---|---|---|---|
| dev (`video_ari_joan_8_first_points`) | 18 | 28 | 0/0 | 2/2 | 15 / **12** | 18/15 |
| e1 | 2 | 9 | 0/0 | 0/0 | 1/0 | 2/0 |
| e2 | 4 | 8 | 3/1 | 3/1 | 3/1 | 4/1 |
| e3 | 0 | 14 | — | — | — | — |
| e4 | 1 | 7 | 1/1 | 1/1 | 1/1 | 1/1 |
| e5 | 1 | 7 | 0/0 | 0/0 | 0/0 | 1/0 |
| e6 | 0 | 8 | — | — | — | — |
| e7 | 1 | 10 | 0/0 | 1/1 | 1/1 | 1/1 |
| **total** | 27 | 91 | 4/2 | 7/5 | **21 / 15** | 27/18 |

A dev-selected **2.0× gate** (precision 12/15 = 0.80 on dev) generalises to the
held-out match at **32/36 = 0.89** — a legitimate out-of-sample result, and the
first one this bucket has. But note the two costs it also selects:

* it admits **6 false contacts on the drills** (21 admitted, 15 GT) — those
  become false actions and are exactly what can push a drill below its 90 % gate;
* the dev clip supplies 12 of the 15 drill-side GT hits, so the *drill* evidence
  for the gate is mostly the dev clip, not the 7 entreno files.

## 8. Where this leaves the goal metric

The goal needs **128 correct of 183** (0.70). Best case for this lever, taking
the held-out in-sample ceiling (the 20 recoverable misses, all correct, at
precision ~1.0): total-correct **85 → 105 of 183 = 0.574**, class accuracy
**0.589 → ~0.61**. The reach gate is therefore a **recall lever that closes
roughly a third of the gap to the goal and none of the class-accuracy gap**.

Its real value is **upstream**: TC1 measured that 77 % of the touch-count error
is a STARVED count (`under_counted` + `previous_contact_missing`), and this
bucket is a measured 9.78× cause of missing contacts. Fixing recall feeds the
count, and the count is the largest label lever (+0.244 on the 127 non-serve
contacts). The chain is **recall → count → label**, and this document is the
first link's measurement — not a replacement for the label bucket (open point 9),
which remains necessary for the 0.70 class bar.

## 9. The hazard that decides a real run

Relaxing reach admits contacts where the ball is FAR from every tracked player —
which is precisely where **bystanders and untracked players** live. The drills'
2.0× arm (6 false of 21) is the visible tip. So a real A/B must watch the
drill gate and the false-action count, not just the match recall. That is a
`src/` change to a px constant on GT-validated action logic, hence
**architect-tier**: it needs a mechanism memo and an owner-ratified delivery
before it ships, and the constant is **venue-coupled** (206 px vs 464-479 px
court depth, AGENTS.md §7) so a single scalar may not even be the right shape.

## 10. The attribution caveat — frame-precision is NOT contact-precision

Re-scored with each admitted row's own `target_team` against the GT event's
`player_team` at the same frame:

| gate | admitted | on a GT frame | GT frame **and** GT team | prec(frame) | prec(team) |
|---|---|---|---|---|---|
| 1.1× | 4 | 4 | **0** | 1.00 | 0.00 |
| 1.2× | 14 | 14 | **6** | 1.00 | **0.43** |
| 1.3× | 21 | 19 | 7 | 0.90 | 0.33 |
| 1.5× | 28 | 23 | 10 | 0.82 | 0.36 |
| 2.0× | 48 | 32 | 15 | 0.67 | 0.31 |
| 3.0× | 68 | 49 | 17 | 0.72 | 0.25 |
| all | 71 | 49 | 17 | 0.69 | 0.24 |

**At the best frame-precision gate (1.2×, 14/14) only 6 of 14 carry the correct
team.** Across all 71 reach rejections, `target_team` is **B at 64 of 71 and A at
only 6** — the gate is reached almost exclusively when the ball is far from the
far-side formation, which is also when attribution defaults to the far team.
Of the 71: 6 are already accepted nearby, 21 are not a GT contact at all, 14 sit
on a GT contact with a **matching** team, and **30 sit on a GT contact with the
WRONG team**.

So the recall this gate recovers is **frame-recall with a ~1-in-4 correct-team
rate overall (17 of 71 = 0.24)**, and the goal's team metric is at 0.518 raw /
0.755 squad-mapped (open points 2/5). Admitting these contacts would raise
recall AND inject wrong-team contacts — the net effect on the goal metric is
genuinely ambiguous and **cannot be settled offline**, because an admitted
candidate still has to pass `_build_contact` → the resolver → the confidence
threshold, none of which the dump lets us replay.

**This strengthens, rather than weakens, the conclusion: the reach gate is the
right bucket to probe, and a `src/` relaxation is NOT justified by these
numbers.** The correct next step is a measurement of what an admitted candidate
would actually resolve to — which needs a real run, not another offline cut.
