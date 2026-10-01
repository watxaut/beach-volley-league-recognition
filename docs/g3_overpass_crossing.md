# G3 overpass net-crossing probe — diagnosis (no `src/` change)

Scope P9–P33: **18 GT overpasses** (183 contacts in scope).

Crossing signal = ball apparent WIDTH regime (near > 35 px / far < 26 px) across the contact, pre `[f-15, f-1]` vs post `[f+1, f+45]`.

## Aggregate

| GT action | n | crossing | covered | tracked both sides | next-team flip |
|---|---:|---:|---:|---:|---:|
| dig | 55 | 10 | 44 | 52 | 32/55 |
| set | 46 | 4 | 31 | 42 | 21/46 |
| spike | 38 | 5 | 26 | 37 | 20/37 |
| serve | 25 | 16 | 18 | 17 | 11/25 |
| overpass | 18 | 3 | 12 | 18 | 8/18 |
| <none> | 1 | 0 | 1 | 1 | 0/1 |

**GT overpass**: crossing **3/18** (0.1667), tracked both sides 18/18.

## Pre-registered kills

- **K1_signal_present** — FIRED: overpass crossing 3/18 (< 12 -> fired)
- **K2_separation** — FIRED: overpass rate 0.167 vs control dig 0.182 (need >= 1.5x)
- **K3_detection** — clean: overpass tracked-both-sides 18/18 (< 15 -> fired)
- **K4_next_team** — FIRED: overpass next-team flip 8/18 (0.444) vs control 0.582

**Verdict: REFUTED: ball-width net-crossing is not available at the overpass contacts**

## Resolver read at the overpass contacts

Emitted labels near the 18 GT overpasses (production stream): {'<missed>': 5, 'spike': 5, 'set': 2, 'dig': 6}.

## Reading the result

A negative result, the same class as S1/T5/R1: the ball-width net-crossing signal is NOT available at the owner's overpass contacts (3/18), while the ball is tracked on BOTH sides at 18/18 — so this is not a detection gap either. The crossing is measured at the net/tape, where the width regime abstains, and a high lob reads ambiguously on both sides of the contact.

The loss is therefore a LABEL/RULE problem, not a geometry one: the resolver emits `overpass` in exactly one place (a bump-set at touch 2 with no follow), but GT overpasses occur at touch 1 and touch 3 as well, and the emitted touch/gesture read sends them to dig/spike/set. The perceived next-contact team does NOT provide the missing signal either (overpass next-team flip 8/18 = 0.444, controls 0.582) because the stream's own possession/team read is noisy (G1 side-level team 0.755). Any overpass lever must therefore be a gesture/touch-rule change plus a reliable possession signal — an owner/architect decision, not a ball-width threshold.

Caveat: the ball sightings come from the only full-match diag dump (`match_bw03_diag.jsonl`). Its departure gate differs, but the `BallTracker` that produced `ball_track` / `ball_dets` is the shared production one, and the action labels are read from the production stream (`serve_relabel.json`), never the dump.

## Per-contact rows

| pt | f | GT team/touch | tracked pre/post | pre→post sides | crossing | emitted (action/gesture/team/touch) |
|---|---:|---|---:|---|---|---|
| P11 | 7320 | B/t2 | 15/34 | B→B | . | MISSED ±tol |
| P16 | 10656 | B/t3 | 15/34 | B→A,B | X | spike/bump_set/B/t3 |
| P16 | 10793 | A/t3 | 8/42 | →B | . | spike/attack/A/t3 |
| P18 | 12118 | B/t3 | 13/44 | B→B | . | spike/bump_set/B/t3 |
| P18 | 12160 | A/t1 | 15/43 | B→B | . | MISSED ±tol |
| P19 | 13202 | B/t3 | 14/43 | B→B | . | set/bump_set/B/t2 |
| P19 | 13236 | A/t1 | 14/40 | →B | . | MISSED ±tol |
| P19 | 13267 | B/t1 | 13/42 | B→B | . | dig/bump_set/B/t1 |
| P19 | 13626 | A/t3 | 11/41 | →B | . | dig/bump_set/A/t1 |
| P23 | 16877 | A/t3 | 15/44 | B→A,B | X | dig/bump_set/B/t1 |
| P25 | 19100 | B/t1 | 15/37 | →B | . | MISSED ±tol |
| P26 | 19966 | B/t3 | 9/40 | →B | . | dig/bump_set/A/t1 |
| P26 | 20094 | B/t1 | 15/40 | B→B | . | MISSED ±tol |
| P27 | 21021 | B/t3 | 14/17 | A→B | X | spike/bump_set/A/t3 |
| P29 | 22180 | B/t1 | 13/44 | B→B | . | dig/bump_set/B/t1 |
| P29 | 22223 | A/t1 | 15/20 | B→B | . | set/bump_set/B/t2 |
| P30 | 23011 | B/t3 | 14/39 | B→B | . | spike/bump_set/B/t3 |
| P31 | 24948 | A/t3 | 10/41 | →B | . | dig/bump_set/A/t1 |
