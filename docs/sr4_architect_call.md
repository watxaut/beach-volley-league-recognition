# SR4 architect call — the per-point serve record is refuted as specified

Coordinator record, session #62+1 (2026-10-02). Escalated to tier-2
(`anthropic/claude-opus-5.5`, memo run in `logs/architect_sr4_ds_run.log`,
memo body at `/tmp/sr4_design_memo.md`). Every number below was re-measured by
the coordinator from committed artifacts; the architect's own two probe scripts
(`/tmp/sr4_width.py`, `/tmp/sr4_ff2.py`) were re-run and reproduce.

## 1. The call

The architect **refuted the single-mechanism SR4** that was handed to it. The
brief asked for one per-point serve record reaching near ≥ 15 of 16 and far
≥ 16 of 17 at zero new false serves. The memo's finding, confirmed here:

- **NEAR has a hard coverage ceiling of 13 of 16.** Three near serves (P5 f2575,
  P7 f3747, P24 f18135) have **no action on the serving side within ±15 f of
  the ground-truth contact at all**. Nearest own-side actions are −81 f and
  −108 f for P5/P7; P24 has none. No hindsight rule can recover a record for a
  contact the pipeline never emitted. The near bar of 15/16 is therefore above
  the ceiling — it is not reachable by design work, only by fixing perception
  (which is M-b's job, and M-b alone does not fix P24 either).
- **FAR's side signal is real and was not in the brief.** The ball as seen
  leaving the far half is **14–23 px** wide at all 17 far serves and
  **39–52 px** at all near serves that have a flight event at all. At a cut
  anywhere in **26–32 px** (a plateau, not a knife edge) the rule claims
  **16 of 17 far serves and 0 of 16 near serves**. 13 of the 16 near serves
  have no flight event within ±15 f at all; the 3 that do (P12 w=39, P18 w=50,
  P24 w=48) sit far above the plateau.
- **But binding those records to points destroys it.** Scoped to a point window
  the far count falls to 9–11 of 17 with 2–8 false records; unscoped there are
  **432** narrow events for 33 serves. Every suppression rule tried loses the
  signal with the false positives (see §3). This is a genuine refutation, not a
  tuning failure.

## 2. Why the point binding fails — the root cause (new, measured here)

**The pipeline's point windows do not contain their own serves: 0 of 17 far
serves fall inside their own point window.** `game_state.points` has **31**
entries against the ground truth's **33** points, and point *i*'s
`start_frame` sits **after** its own serve by −1 to −1466 f (the rally-onset
backdating that session 56 measured). A record keyed on
`points[i].start_frame … end_frame` therefore looks in the wrong place for every
serve. This also explains the session-#54 "13/17 covered but 9/17 bound" split:
coverage was measured over the whole stream, binding over the windows.

Consequence: **SR4 cannot be a per-point record until the point map is fixed or
bypassed.** Two routes, both cheap, neither `src/`:

1. **Bypass the point map** — emit records as (frame, side) and let the existing
   `scripts/score_serves.py` match them positionally. This is what the width
   signal does at 16/17; it is a *detection* result, not yet a *record* result,
   because 432 candidates → 16 hits with 416 false records.
2. **Fix the episode→point map first** (open point 22, the G1 critical-path
   head). A correct point map turns the 16/17 detection into a record per point
   with no new suppression rules at all.

## 3. What was tried for the false positives (all measured, all fail)

| rule | records | far hits | false records |
|---|---|---|---|
| narrow-event onset inside `[point_start−0, point_start+12]` | 11–17 | 9–11 / 17 | 2–8 |
| leading-gap window `[prev_end − L, point_start]`, L = 120…400 | 29–31 | 5–7 / 33 side-correct | 22–25 |
| narrow onset in `[point_start−15, point_start)` | 8 of 31 points | — | — |
| global: drop a narrow event when the next action is within N f | N=15 → 345 recs | 16/17 | **329** |
| global: same | N=30 → 264 recs | 8/17 | 256 |
| global: same | N=60 → 185 recs | 2/17 | 183 |
| global: same | N=120 → 141 recs | 0/17 | 141 |

The N-sweep is the informative one: **any rule aggressive enough to cut the
false records also cuts the true serves**, because the true far serves are
followed by a near-side reception within 15 f just as often as the false ones.
There is no separating gap in that direction. The only lever left is the point
map, which is why route 2 above is the honest recommendation.

## 4. Corrected decisions

1. **SR4-NEAR: do not build.** Its bar (15/16) is above the measured coverage
   ceiling (13/16). It waits on perception (M-b / P24), and the near record that
   *is* buildable covers 13/16, not 15/16.
2. **SR4-FAR: the detection exists, the record does not.** Keep the width band as
   a Learning (it is the strongest measured far-side side-signal in the project)
   and gate SR4-FAR on the point map, not on a new suppression rule.
3. **P12 is not the record's job** — confirmed again: it is a rally-boundary
   segmentation defect (9 actions of R19 between the window opener f7132 and the
   contact f7780), the same root cause as §2.
4. **Wrong-label repairs do not violate the STOP list.** Writing a serve record
   into `output/serve_records.json` never mutates `actions_pass2` and never
   relabels the reception; the STOP rule forbids the latter. P9/P10/P11 remain
   repairable on the near side.
5. **Tolerances stay at ±15 f.** P33's −25 f is not admitted: widening to 25 f
   also admits the far false serve f8534 at +16 f. (Memo's ruling, re-checked
   against `docs/sr4a_near_openings.md` §5.)

## 5. Provenance and caveats

- Sources: `output/20260920_match_ari_joan_lost/pipeline_output.json` (207
  actions, 31 `game_state.points`, 578 `far_flight` events of which 432 are
  narrow), `ground_truth/20260920_match_contacts.json` (33 serve contacts, far
  17 / near 16, tolerance 15), `output/serve_evidence.json` (87 records,
  arms `conjunction` + `structural`). All committed; nothing here is new decode.
- **The width cut is camera-scale biased** (AGENTS.md §5; the practice venue
  projects the court 2.3× shallower than the beach). The band is *separated*
  (14–23 vs 39–52), so a normalised cut has room, but "26–32 px" must be
  re-derived per session and must not be frozen as a constant.
- **Every number is from one match**, and the width band was fitted on it. The
  held-out drill `20260928_entreno_vall_dhebron` was never read.
- The architect's own near-coverage numbers are from the same single artifact as
  everything else; the ±81/−108 f distances for P5/P7 are the only new readings
  and are reproducible from `pipeline_output.json`.

## 6. What this changes in the plan

- **New, ranked first:** a **point-map probe** — measure, over the 33 ground-truth
  serves, where a serve sits relative to its own pipeline point window (§2), and
  whether the 31-vs-33 mismatch and the backdated onsets have one cause. It is a
  pure post-hoc measurement, no `src/`, no decode, and it decides whether SR4-FAR
  is a 1-rule job (bypass) or blocked on open point 22.
- SR4-FAR becomes SR4b, gated on that probe; SR4-NEAR stays parked on perception.
- The held-out session is still untouched; the rules are not frozen yet, so
  SR3's worker half still waits.