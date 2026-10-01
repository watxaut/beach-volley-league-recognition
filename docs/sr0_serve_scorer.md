# SR0 — one serve scorer, per side, dev vs held-out (session 56, 2026-10-03)

`scripts/score_serves.py` (+33 tests, `tests/test_serve_scorer.py`). No decode,
no `src/` change: post-hoc scoring over existing artifacts (AGENTS.md §6).
Artifact: `output/serves/sr0.json`. Task **SR0** of
`docs/serve_reliability_plan.md`, tracked as open point **30**.

**Gate: PASS.** The scorer reproduces the plan's pre-registered baseline exactly
— production **near 8/16, far 0/17, 12 false emissions** on the 33 match points
(±15 f, greedy one-to-one, side-correct). The script exits non-zero if those
three numbers ever move, so a later stream cannot silently redefine them.

## 1. Why one scorer

Every serve number in this project came from a different script with a different
scope: `score_serve_events.py` (windowed, seek-possessed), `score_heldout_contacts.py`
(counts production **OR** pass-2), `score_pass2_contacts.py` (dev only),
`consume_serve_evidence.py` (its own validation block, far only). That is how
near 11/13 and "14/17 at zero FP" both became headline numbers. One scorer, one
matching rule, one place where the dev/held-out split is applied:

- **matching** — greedy one-to-one, nearest pair first, inside each owner
  contact's own `frame_tolerance` (15 f on every owner contact);
- **side-correct by default** — a far emission is not a near serve; the
  positional match runs alongside so side accuracy is measured, not assumed
  (under side-aware matching it is tautologically 1.00);
- **coverage ≠ binding** — a stream can declare `point_bound`, and then a
  record that sits on the serve but was bound to the wrong point is a miss.
  This is the entire 13-vs-9 gap below;
- **proposals are not claims** — a stream that does not claim a serve per
  candidate (the raw evidence records, the rally onset) reports **no precision
  at all**. "Precision 1.000 over 14 rally onsets" and "74 false serves" are
  both fiction, and each was one line away from being printed;
- **side ≠ squad** — the action stream speaks court side (`team` A=near), pass-2
  speaks squad (`pass2_team`, *winner-serves-derived*, i.e. GT-derived). The
  pass-2 side read is therefore the emitted letter, its squad is flagged, and a
  squad call is scored through the switch parity (imported from
  `resolve_side_switches`, never re-implemented).

## 2. The honest baseline, all streams, both sides

Match `20260920_match_ari_joan_lost`, GT `ground_truth/20260920_match_contacts.json`
(33 owner serves: near 16 / far 17; dev = P1-P8, held-out = P9-P33), production
artifact = the #54 run `133d87c` with `--serve-events`.

| stream | side | dev | held-out | all | precision | FP/point | median \|offset\| |
|---|---|---|---|---|---|---|---|
| `production` | near | 1/3 | 7/13 | **8/16** (R 0.50) | 0.53 | 0.21 | **1 f** |
| `production` | far | 0/5 | 0/12 | **0/17** | 0.00 | 0.15 | — |
| `production` | all | 1/8 | 7/25 | 8/33 (R 0.24) | 0.40 | 0.36 | 1 f |
| `pass2` (GT-derived squad) | near | 1/3 | 11/13 | 12/16 (R 0.75) | 0.46 | 0.42 | 1 f |
| `pass2` | far | 0/5 | 0/12 | 0/17 | 0.00 | 0.15 | — |
| `game_on` (rally onset, no side) | near | 0/3 | 3/13 | 3/16 (R 0.19) | n/a | n/a | 14 f |
| `game_on` | far | 2/5 | 9/12 | **11/17** (R 0.65) | n/a | n/a | **3 f** |
| `serve_evidence` (coverage) | far | 5/5 | 8/12 | **13/17** (R 0.76) | n/a | n/a | 8 f |
| `serve_evidence_bound` (binding) | far | 5/5 | 4/12 | **9/17** (R 0.53) | 0.47 | 0.30 | 8 f |

Two corrections to the record, both from running the same rule over the shipped
artifacts:

- **The far-serve evidence covers 13/17 far serves, not 14/17.** 14 records land
  within ±15 f of a serve of *any* side, but the fourteenth is on a **near**
  serve (P12 f7777, record f7762). The 14/17 in `docs/g4_structural_serve.md` is
  a sweep figure on the recording, not a property of the artifact that ships.
- **The evidence layer's precision is 0.47, not 1.00, when it is scored as the
  claim it is.** 19 bound records, 9 land on their own point's serve. The zero-FP
  claim was measured against 24 mid-rally controls and 9 owner FALSE/OFFGAME
  moments, which is a real and useful property — it is just not the same number
  as precision against 33 GT serves, and both are now printed.

## 3. Findings that change what SR4 should do

**3.1 The far-side serve TIME is nearly free; the near-side time is not.** This
was SR0's cheap side question: *how close does the rally onset already land to
the GT serve?* The `game_on` backdated burst start (`game_state.points[].start_frame`,
already computed, no extra work) lands within ±15 f of **11/17 far** serves at
median |offset| **3 f** (range −6…+6) and only **3/16 near** at |offset| 14 f
(all three *late* by 10-15 f). At ±120 f it covers 27/33.

Read: a far serve is the first thing that happens in a rally, so the ball-flight
burst starts on it — the far side does not need a contact proposer to know
*when*, it needs one only where the point layer lost the rally (17 of 31 onsets
are unmatched, and those are the misses). The near side gets no such help
because the rally onset is governed by the *reception*, not the serve. **So SR4
keeps a proposal step, and it must be per side: cheap on the far side, real work
on the near side.** (The SR3 audio onset, if it survives its kills, would be the
one signal that is symmetric between the sides.)

**3.2 The near-side misses are not a timing problem.** Every near serve
production emits is within **±2 f** of the owner frame (8/8, median 1 f). So the
8 missing near serves are missing *emissions* — proposal, gesture label, or the
serve gate — not late ones. That is exactly what SR1 is for, and it is now
cheap to answer: 8 match near serves + e2/e6.

**3.3 The 12 false serve emissions are mostly dead time, and the three rally ones
are named.** Taxonomy from the scorer (`serve_outside_tolerance` /
`rally_contact_mislabeled` / `dead_time_handling`):

| kind | n | frames |
|---|---|---|
| dead-time handling, no owner contact within 80 f | 8 | f1039 f2414 f3595 f5130 f6928 f14387 f17159 f20397 |
| rally contact with the wrong label | 3 | f3856 (a `set` at f3852), f8534 (a `dig` at f8550), f10070 (a `dig` at f10072) |
| a serve outside tolerance | 1 | f25782, 25 f before P33's f25807 |

8 of 12 sit in dead time — the pre-serve-handling family that no dead-time test
separates from a serve (#53 §4) — so SR4's toss check is worth the sub-probe the
plan budgets for it, and only for these.

**3.4 pass-2 buys near recall at a precision nobody would ship.** It reaches
12/16 near (production 8/16) with median |offset| 1 f, and it can never produce
a far serve (0/17, and its squad call is only 0.58 accurate *even though it is
GT-derived*). 14 of its 26 near emissions are false, 13 of them a rally contact
re-labelled as a serve (the S0b family, unchanged). It stays a secondary signal,
exactly as D3 says.

## 4. What SR0 does not do

- **No decode, no `src/` change, no label emitted.** Scorer only.
- **The entreno numbers it prints are from STALE artifacts.** The seven
  `output/video_entreno_*/pipeline_output.json` files were produced 2026-09-04 /
  09-06 (commits `239490c` / `8150694`), i.e. **before the v3 ball detector
  (09-26) and the pose gating (09-27)**. They give **3/5** (e2 and e6 emit no
  serve at all; e3/e5/e7 hit with |offset| 0/3/3 f), where the plan quotes 4/5
  from a script-path run whose artifacts are not on disk. The report prints each
  stream's `processed_at` + commit so this cannot be read as current. **Action
  (cheap, worker): re-run the seven clips with `make run` and re-score.** Until
  then the match is the only trustworthy serve baseline.
- **SR3's serve-only GT format is parsed but unexercised against real data**
  (`parse_serve_gt_text`). Wall-clock timestamps go through an *injected*
  timebase on purpose: on the VFR match a timestamp must be converted by PTS,
  never by a seek (AGENTS.md §9). The SR3 worker half builds that index.

## 5. Next

SR1 (near-serve miss taxonomy) is now unblocked and cheap: §3.2 says the 8
missing near match serves are missing emissions, and §3.3 names the false ones.
SR2 (audio onsets) is unchanged and still the only symmetric timing signal.
The trainer for SR4 should read §3.1 before writing the proposal step: far side
needs a side decision on a known time, near side needs a proposal.

Suite **1069**.