# Project Status

> **Convention:** this file is the cross-session memory of the project. Read
> it first when coming back. Update it (and commit it with the work) at the
> end of every working session. To keep it lean:
>
> - **Where we are** holds the CURRENT state only (production facts, latest
>   outcome, active next steps) — rewrite it, never append to it.
> - **Open points** holds one compact entry per point: status, problem, next
>   step. Collapse resolved `[UPDATE …]` stacks into the status line; full
>   histories live in `docs/history/`.
> - **Log** keeps only the last ~3 sessions verbatim; older entries move to
>   `docs/history/status_log_archive.md` (and superseded "Where we are"
>   blocks to `docs/history/status_where_we_are_archive.md`). Never delete
>   history — move it.
> - New durable protocol rules go into **AGENTS.md**; new cross-session
>   technical facts go into **Learnings** (one line each, provenance in the
>   archives).

**Last updated:** 2026-10-02 (sixty-second session, **D4 DECIDED: the serve-zone
exemption from the off-court hold is PARKED; card SR4a (the near-opening table) is
READY and unrun because the worker models are quota-blocked until 2026-10-03 18:49**,
`docs/d4_gate_brief.md`, open point **30**). No `src/` change, no decode. M-b's
ceiling is +1 near serve of 16 (+2 with P5) against a 0.90 bar that needs 15, and
the only measured version was net 0; its cost is match-wide identity churn (#62
re-read of P18: an attribution swap, not a rally_start failure), so it is priced
only by a full-match run. Next: run card **SR4a** (`/next-task`), then SR4, then
the held-out session once, then SR5 -> SR6.

**#58 (previous session):** 2026-10-02 (fifty-eighth session, **SR1b: review of SR0/SR1 —
the near serve has three measured causes, not one**, `docs/sr1b_near_serve_causes.md`,
open point **30**). Diagnose-only, no `src/` change. One sequential production pass
over the match [0, 15000] (parity **111/111**) plus a config-only counterfactual
measured what SR1 had inferred: **P9-P12** are lost because `behind_baseline` reads
the toucher's foot on the CONTACT frame (0.8-24.5 px inside the 761 px threshold; 7 f
later the same tracks are past it) — the server is tracked and attributed; **P5/P7**
are lost because the near server's PLAYER track stops being fed exactly 91 f after
its last in-court sighting (`player_off_court_hold_frames = 90`) and coasts frozen
through the serve (lifting the horizon makes **P7 a hit**; P5 then dies on
`rally_start` behind a pre-serve handling 78 f earlier); **e2**'s server is never
tracked. SR1's "not a tracking problem" was about the ball only. SR3 GT has
**arrived** (vall_dhebron, 19 serves: 8 near / 11 far) and is committed as the
held-out session. Next = task card **SR1c** below (measurement, no `src/`).
A cheap-model executor prompt (`/next-task`) and the `task-card` skill were added.

**#57 (previous session):** 2026-10-02 (fifty-seventh session, **SR1 DONE: the near-serve miss
taxonomy**, `scripts/probe_near_serve_misses.py` + `docs/sr1_near_serve_misses.md`,
open point **30**). Diagnose-only, no `src/` change. Across 10 missed near serves
(match 8 + practice 2, all from **fresh production runs**): **6 `label`, 3
`no_contact`, 1 `other_side_contact`**. The label bucket is ONE mechanism: the
serve label needs `behind_baseline AND rally_start`
(`ActionContextResolver._decide`) and `behind_baseline` is false at 5 of the 6
-- the contact is found, attributed and opens the rally (gaps 204-478 f), it is
just not judged behind the baseline; e2's dump measures it directly. The 6th is
a **cascade**: P33's own serve emitted 25 f early suppresses `rally_start` 16 f
later and turns the real serve into a `dig`. The 3 `no_contact` cases split
P5/P7 (stage 4, **reach gate**: 448 px and 204 px vs a 140 px reach -- the
server is not among the four tracks at the contact) and e5 (stage 3,
`no_ball_sighting` x15/31f). Near-side serve recall is **11/21 = 0.52** on
current artifacts, and the practice figure is **3/5, not the plan's 4/5**.

**#56:** 2026-10-02 (fifty-sixth session, **SR0 DONE: one serve scorer**,
`scripts/score_serves.py` + `docs/sr0_serve_scorer.md`, open point **30**). The
scorer reproduces the plan's pre-registered baseline exactly (production near
**8/16**, far **0/17**, 12 FP, ±15 f) and adds the numbers the backlog was
missing. It corrects the record twice: the shipped far-serve evidence covers
**13/17** far serves, not 14 (the 14th record sits on a NEAR serve), and its
precision as a claim is **0.47**, not 1.00. Three findings steer SR4: (1) the
**rally onset already times 11/17 far serves at median |offset| 3 f** (vs 3/16
near at 14 f) -- far-side timing is nearly free, near-side timing is not, so the
proposal step must be per side; (2) the near serves production *does* emit are
all within ±2 f, so the 8 near misses are missing emissions, not late ones
(SR1's job, now cheap); (3) 8 of the 12 false emissions are dead-time handlings
and only 3 are mislabeled rally contacts (named). Nothing in `src/` changed.

Earlier sessions: see the *Session index* below.

## North-star goals (set session 24)

Why this project exists — a service for the owner's beach-volley club:
record a session, process it, deliver two things. New mechanisms should
trace to a goal; when prioritizing, the critical paths below decide.

**G1 — Fantasy scoring.** Per point, per player:
Kill +1 (unreturnable attack) · Block +1 (defensive stop at the net) ·
Ace +1 (unreturned serve) · Dig +1 (retrieving an attacked ball) ·
Assist +0.5 flat (setting a teammate for a kill) · Error −1 (attack out,
service fault, ball-handling error).

**G2 — Individual statistics.** Per-player understanding of your game
(kill%, dig%, zones, placement, tendencies), aggregated across sessions
via player labels.

**G3 - Action accuracy.** This is the most important goal, as the other 
  two are based on this one:
  We must strive to be as confident about the detected actions as possible

**Stat coverage audit (2026-09-27):**
- Kill — DONE: spike outcome `kill` (semantics ratified 08-31).
- Dig — DONE: `dig` action.
- Block — DONE: block action + kill_block/soft_block classification.
  Fantasy: kill_block +1, soft_block 0 (ratified 09-27).
- Error (attack) — DONE: spike outcome `out`.
- Assist — DERIVABLE NOW, metric unbuilt: set → same-team spike with
  outcome `kill` in the same point (actions×spikes join). Scoring
  RATIFIED 09-27: +0.5 flat, no direct/indirect split.
- Ace — BLOCKED (plan: point 30 SR4→SR6): needs point-outcome layer (21.3) + far-side serve
  emission (22 — 16/32 match serves); parked as point 13.
- Error (serve fault) — BLOCKED (plan: point 30 SR6): same dependencies as ace.
- Error (ball handling) — NOT PERCEPTIBLE from ball+pose; plan a manual
  override in the review UI instead of perception work.
- Point winner / scoreboard (needed to group lines per point) — BLOCKED
  on 21.3/21.4; validate against the 33 dictated match winners.

**G1 critical path:** 22 (episode→point map; serves emitted on BOTH
sides) → 21.3 (point winner/outcome layer) → 13 (ace/assist/serve-error
derivation) → fantasy scoring module (per point × player, computed from
the DB) + points table in the web UI (14e). Quality gate before any club
rollout: 2/21.4/21.5 — identity hops and side switches corrupt per-player
lines; plus a fast human-review pass per match (fantasy numbers must be
trustworthy).
**G2 critical path:** mostly BUILT (player pages, court heatmaps,
placement, per-video splits); remaining adds = serve/assist/error stats
(from the same 21.3/13 work), per-point views (14e), confidence surfaces
(21.2), and multi-session aggregation UX.

## Where we are

**Serves are the active track and they are NOT reliable (#56 SR0 measured them;
#58 SR1b measured WHY the near side fails; `docs/serve_reliability_plan.md`,
`docs/sr0_serve_scorer.md`, `docs/sr1b_near_serve_causes.md`, open point 30).**

Honest per-side serve baseline, all from `scripts/score_serves.py` (contact
level, ±15 f, greedy one-to-one, side-correct; match P1-P33, 33 owner serves):

| stream | near | far | other |
|---|---|---|---|
| production | **8/16** (dev 1/3, held-out 7/13) | **0/17** (0/5, 0/12) | 12 FP (precision 0.40, 0.36/point); timing of every hit within ±2 f |
| pass-2 re-label (GT-derived squad) | 12/16 | 0/17 | 14 near FP; squad acc 0.58 even though GT-derived |
| rally onset (`game_on`, time only) | 3/16 | **11/17** (median &#124;offset&#124; 3 f) | no side read; 17 of 31 onsets unmatched |
| far-only evidence layer | not observed | **13/17** coverage (**in-sample**), **9/17** bound (held-out **4/12**) | precision 0.47 as a claim; 1 owner FP |
| entreno e2-e7, fresh runs | 3/5 (e3 +0, e6 +1, e7 +0) | — | e2 f32, e5 f20 missed; near recall 11/21 = 0.52 overall |

**Why near serves are lost — MEASURED (#58, supersedes SR1's inferred story):**

| misses | mechanism | candidate fix (owner gate before `src/`) |
|---|---|---|
| P9, P10, P11, P12 | `behind_baseline` reads the toucher's foot on the CONTACT frame; airborne/landing feet sit 0.8-24.5 px inside the 761 px threshold (past it 7 f later). Server tracked and attributed. | **M-a** takeoff stance (pre-contact foot) — measured next as card SR1c |
| P5, P7 | the near server's PLAYER track stops being fed 91 f after its last in-court sighting (`player_off_court_hold_frames = 90`, tuned on drills) and coasts frozen through the serve; contact dies at the reach gate. Lifting it: P7 → hit; P5 → `dig` (rally_start killed by a pre-serve handling 78 f earlier) | **M-b** serve-zone exemption from the hold — cost measured as card SR1d |
| e2 | server never tracked (sideline bystander holds the 4th slot from bootstrap) | none planned (drill artefact) |
| e5 | ball not sighted | none planned |
| P24, P33 | not re-measured (outside the [0,15000] pass); P33 = rally_start cascade from our own early serve | — |

`docs/g3_heldout_p9_p33.md`'s near 11/13 counts production OR pass-2 serves. The
production stream alone is 7/13.

**Held-out lock (#58):** `ground_truth/20290928_entreno_vall_dhebron_serve_anchors.json`
(SR3, owner-dictated 2026-10-01: 19 serves, 8 near / 11 far, 1 `ace`, 1 `net`) is the
held-out session. The video has NEVER been run. Do not run, score or look at
pipeline output on it until a card says "score held-out once" with frozen rules.
With 8 near serves, "≥0.90" passes only at 8/8 (Wilson 95% CI on 8/8 = [0.68, 1.0]):
report counts + CI, never a bare rate.

**Plan: SR0-SR7.**
- **SR0:** DONE (#56). **SR1:** DONE (#57), corrected by **SR1b** (#58).
- **SR1c CLOSED #60 / SR1d REFUTED #61 → D4 DECIDED #62** (see *Next task
  cards* and `docs/d4_gate_brief.md`): **M-a stays closed, M-b is PARKED.** Its
  ceiling is **+1 near serve of 16** (+2 only with P5) against a 0.90 bar that
  needs 15 of 16, and the blunt version measured **net 0** (+P7 / −P18, false
  serves 12→14). **SR4a** (the near-opening table, no decode) goes first.
- **SR2:** audio onset probe — DEMOTED (#58): timing is not the bottleneck on either
  side. Run only after the near-side mechanisms, if far binding stays the gap.
- **SR3:** owner half DONE (vall_dhebron GT committed, #58). Worker half (the run) is
  held behind the held-out lock.
- **SR4:** per-point serve record, both sides, post-hoc. Near side consumes the
  production near label once M-a/M-b land; far side = rally onset time + side vote.
- **SR5:** beach-rules serve-sequence decoding (server identity needs the server's
  track at the serve — M-b). resources/full_videos/20290928_entreno_vall_dhebron.mp4 
  is not real gameplay, there are no side switches, but you can use it for serve testing.
- **SR6:** ace / service fault. **SR7:** learned detector, deferred.

**STOP list:** no more px-space or contact-geometry far-serve thresholds, selector
constants, or tracker admission tuned on the 17 match far serves. No relabeling of
the reception as the serve. No look at vall_dhebron outputs (held-out lock).

**Production state (unchanged since #54):**
- **Weights:** `models/volleyball_ball_best.pt` v3. The match is native 720p,
  upscaled once to `_up1080`. Perf 68 ms/frame. Pose gates are live in
  `classify_actions`.
- **Match:** 31/33 points. That is a count comparison, not matched recall. 207
  actions.
- **Held-out contacts P9-P33:** P 0.785 / R 0.760 / F1 0.772, class 0.590. Team
  0.518 raw, 0.755 squad-mapped (S3), so 34 genuine side errors. Taxonomy: 46
  correct / 57 wrong label / 36 wrong team / 44 missed. `overpass` 0/18.
- **Pass-2 layers** (scripts only, no `src/`):
  - `relabel_serves.py`: point-level only. Its far contact on dev is 0/5, so never
    consume it as a label.
  - `resolve_side_switches.py`: `[7,14,21,28]`, exact.
  - `resolve_point_winners.py`: 18/33.
  - `consume_serve_evidence.py`: far-only, 13/17 covered, 9/17 bound.
- **`--serve-events` observers:** default OFF. Inertness is measured
  (byte-identical).
- **Entreno gate record** (`evaluate --ignore-player` F1): e1 0.706, e2 0.571,
  e3 1.0, e4 0.933, e5 0.923, e6 0.933, e7 0.75. Suite **1091**.

**Refuted and parked** (do not reopen without new data): T5 tracker admission, R1
departure gate, S1 looming, scale-aware geometry, M1 far-end crop, possession
signal, overpass width crossing, R2 confidence calibration.

**Known defects:** `scripts/annotate_player_gt.py` and `src/db/ingest.py` seek on
VFR. Both are allow-listed in `tests/test_vfr_seek_guard.py`. Fix the annotator
before any frame-shown annotation pass.

**Active next (ranked) — execute via the task cards below (`/next-task`):**
1. **SR4a** (READY): the near-opening table — for every serve, what the pipeline
   already emitted around it, bucketed into hit / wrong label / wrong rally opening
   / never produced. No `src/` change, no decode. Decides whether the after-the-fact
   serve record is worth building, and reopens the tracking exemption only on a
   pre-registered count.
2. **SR4** (after SR4a reads): the per-point serve record — far side from rally
   onset time + side vote, near side from the after-the-fact opener rule.
3. **SR3 worker half, ONCE, after the rules are frozen**: teach `score_serves.py`
   the `serve-anchors-v1` format, run the held-out session, score it once.
4. **SR5 → SR6.**
5. **Deferred edit, not a card:** the `player_off_court_hold_frames` comment at
   `src/utils/config.py:101` is **STALE** (it credits the 90 f horizon with killing
   e2's sideline bystander; that bystander is fed on **400 of 423** frames at the
   horizon today, #61). Fix it **comment-only**, inside whichever session next
   touches `src/` for another reason — never as a change of its own.

The non-serve backlog is unchanged: the label bucket (open point 9), the reach-gate
bucket, e4/e5/e6 re-adjudication.

**Deferred triggers:** unchanged (detector v4, T7/T10, T6, T8, T12, R2), with one
exception. T9's PTS timebase is pulled forward, because SR2/SR3 map audio and
dictated timestamps to frames by PTS.

The full #54 block (production facts, G0-G4/S0-S4 histories) is archived verbatim in
`docs/history/status_where_we_are_archive.md`.

## Next task cards

> Executable briefs for the next sessions, written by a planning session with the
> `task-card` skill (`.pi/skills/task-card/SKILL.md`). A cheap executor runs ONE
> card via `/next-task` (`.pi/prompts/next-task.md`) and does exactly what it says.
> Take the first card whose status is `READY`. A card is the whole brief: if it
> is ambiguous, wrong, or reality disagrees with it, the executor STOPS and
> reports. It does not fill gaps.

### CARD SR1c — measure the takeoff-stance `behind_baseline` (M-a), no `src/` change
- **status:** DONE (#60): CLOSED at gate G2 — the probe could not reproduce the
  shipped read (match 194/207, entreno_2 6/7, entreno_3 13/14, vs ≥98% per
  session), so the decision rule was never read; no mechanism, owner chose
  "leave as is" (`docs/sr1c_takeoff_stance.md`).
- **type:** measurement (diagnose-only)
- **goal:** decide with numbers whether judging `behind_baseline` on the pre-contact
  stance recovers the near serves P9-P12 without creating false serves (open point
  30, near recall 8/16).
- **why:** `docs/sr1b_near_serve_causes.md` §2: at P9-P12 the toucher's foot on the
  contact frame is 0.8-24.5 px inside the 761 px threshold (team A, match).
- **read first (nothing else):** AGENTS.md; this card; `docs/sr1b_near_serve_causes.md`;
  `src/recognition/action_classifier.py` `_build_contact` and the
  `candidate_passed_gates` diag record; `src/recognition/action_context.py`
  `resolve` + `_decide`; `src/detection/court_calibration.py` `is_behind_baseline`;
  `scripts/probe_near_serve_misses.py` (`sequential_diag_pass`, `emit_diag`,
  `load_diag_frames`); `scripts/score_serves.py` (`build_match_session`,
  `build_entreno_session`, GT loaders).
- **may create:** `scripts/probe_takeoff_stance.py`, `tests/test_takeoff_stance.py`,
  `docs/sr1c_takeoff_stance.md`, anything under `output/sr1c/`.
- **may modify:** `STATUS.md` (only the edits listed below).
- **must not touch:** `src/`, `ground_truth/`, other scripts/tests, `AGENTS.md`,
  any vall_dhebron input or output.
- **steps:**
  1. Full-match diag dump, ONE sequential pass (~35 min on MPS):
     `mkdir -p output/sr1c && nohup venv/bin/python scripts/probe_near_serve_misses.py --emit-diag output/sr1c/match_full_diag.jsonl --end-frame 999999 --device mps > output/sr1c/match_full_run.log 2>&1 &`
     then poll (`sleep 300; tail -3 output/sr1c/match_full_run.log`). Defaults give
     the match video, calibration and reference artifact. The log ends with a JSON
     block.
  2. **Gate G1 (parity):** in that JSON block, `parity_vs_reference.identical` must
     be `true` (207 shipped actions). If false: STOP, report the diff.
  3. Write `scripts/probe_takeoff_stance.py`. Inputs: `output/sr1c/match_full_diag.jsonl`
     (calibration `calibrations/20260920_match_ari_joan_lost.json`) and
     `output/sr1/entreno_{1..7}_diag.jsonl` (calibrations `calibrations/video_entreno_N.json`).
     For every `candidate_passed_gates` record (contact frame `c`, `track_id`,
     `team`, `gesture`, `behind_baseline`):
     - foot(t) = (bbox x-centre, bbox[3]) of that `track_id` in frame record `t`'s
       `players`, NON-predicted only;
     - `bb_K` = `CourtCalibration.is_behind_baseline(foot, team)` using the foot
       with the max y (team A) / min y (team B) over frames `[c-K, c]`; import the
       real class, never re-implement the test;
     - K = 0 recomputes the shipped value; **K = 10 is the pre-registered rule**;
       K = 5 and 15 are reported as sensitivity only and decide nothing.
  4. **Gate G2 (reproduction):** `bb_0` must equal the dumped `behind_baseline` on
     ≥ 98% of records per session (SR1b measured 104/106). Else STOP.
  5. First-order flip simulation (no cascade): an EMITTED action flips to `serve`
     iff its action is `spike` or `dig`, `rally_start` is true (gap to the previous
     emitted contact > 90 f, or first contact), shipped `behind_baseline` is false,
     and `bb_10` is true. Emitted actions = the dump frame records' `actions`.
  6. Score every flip against GT (±15 f, side letter A = near): `recovered` (a GT
     serve of that side, not already hit by a production serve), `false_dead_time`
     (no GT contact within ±15 f), `false_breaks_gt` (a GT non-serve contact within
     ±15 f). Match GT = `ground_truth/20260920_match_contacts.json` via the
     score_serves loaders; entreno GT via `build_entreno_session`.
  7. Tests: `bb_K` window logic, predicted-frame skipping, the flip rule, the
     bucket rule, on synthetic records. Run the full suite:
     `venv/bin/python -m pytest tests/ -o addopts=""` (was 1091; must stay green).
- **pre-registered decision (K = 10, not re-tunable):**
  - **PASS** = ≥ 3 of {P9, P10, P11, P12} `recovered` AND match `false_breaks_gt`
    = 0 AND match `false_dead_time` ≤ 1 AND entreno false flips = 0.
  - **FAIL** = anything else. Report it as REFUTED; do not try another K or rule.
- **deliverables:** the script + tests; `docs/sr1c_takeoff_stance.md` (method,
  G1/G2 results, a per-flip table, the per-K sensitivity table, the verdict line);
  `output/sr1c/takeoff_stance.json`.
- **STATUS edits when done:** set this card's status to `DONE (#<session>): PASS|FAIL
  — <one line with the numbers>`; add the result to open point 30's SR1c line;
  add one Learnings line; add a Session index line and a Log entry (move the
  oldest Log entry verbatim to `docs/history/status_log_archive.md`). Do NOT write
  a new card and do NOT start owner gate D4. Commit ONLY the card's files + STATUS
  (+ the archive) in one commit: `#<session>: SR1c DONE - <PASS|FAIL> <one line>`.
- **stop and ask if:** a gate fails; a field named here does not exist; the full
  pass dies; the result would need a different K or rule to pass.
- **est. cost:** ~35 min decode + ~1 h code.

### CARD SR1d — measure the cost of lifting the 90 f off-court hold (M-b), no `src/` change
- **status:** DONE (#61): `global lift REFUTED` — entreno F1 unchanged on all 7 clips (action streams byte-identical, ΔF1 0.000) but the e2 sideline bystander is fed 423 f vs 400 f, and on the match near serves stay **8/16** (composition changes: **+P7** at f3747 delta +0, **−P18** — f11996 relabels `serve`→`dig`; #62 re-read: that is an ATTRIBUTION SWAP (toucher track 3→2, the server's partner), not a rally_start failure), far 0/17, FP 12→**14**, actions 207→**212**
- **type:** measurement (diagnose-only)
- **goal:** know what lifting `player_off_court_hold_frames` costs on the entreno
  gate and on the full match before anyone designs the serve-zone exemption.
- **why:** `docs/sr1b_near_serve_causes.md` §3: lifting it made P7 a hit on
  [0, 8000], but the e2 sideline-bystander regression it was built for (08-29)
  was never re-measured.
- **read first:** AGENTS.md; this card; `docs/sr1b_near_serve_causes.md`;
  `src/tracking/player_tracker.py` `_may_feed_track`; `src/utils/config.py`
  (`player_off_court_hold_frames`) and `Config.load`; `src/main.py` arguments.
- **may create:** `output/sr1d/**`, `docs/sr1d_hold_horizon_cost.md`.
- **may modify:** `STATUS.md` (only the edits listed below).
- **must not touch:** `src/`, `scripts/`, `tests/`, `ground_truth/`, any vall_dhebron
  input or output.
- **steps:**
  1. Write `output/sr1d/hold_off.yaml` containing only
     `player_off_court_hold_frames: 100000`. Confirm from `Config.load` that it
     MERGES over the defaults (other keys unchanged); if it replaces them, STOP.
  2. For N in 1..7: `venv/bin/python -m src.main resources/video_entreno_N.mp4 --output-dir output/sr1d/hold_off/entreno_N --config output/sr1d/hold_off.yaml --device mps --skip-visualization --diag-dump output/sr1d/hold_off/entreno_N_diag.jsonl`.
     Baseline arm = the existing `output/sr1/entreno_N/` (MPS, produced at
     `006e343`). If `git diff --stat 006e343 HEAD -- src/` is NOT empty, re-run
     the baseline too (same command without `--config`) into
     `output/sr1d/base/entreno_N`.
  3. For both arms, all 7 clips:
     `venv/bin/python scripts/evaluate.py --predictions <arm dir>/entreno_N --ground-truth ground_truth/video_entreno_N_annotations.json --component actions --ignore-player`.
     Record F1 / precision / recall per clip. If the baseline differs from the
     STATUS entreno gate record, report both and continue (the arms are compared
     with each other, not with the record).
  4. e2 bystander check: from both diag dumps, the frames the right-side
     sideline-straddling track (foot x ≈ 1550-1700, foot y ≈ 700-720 at f0-f40)
     stays fed. Report the count per arm.
  5. Full match, counterfactual arm only (~35 min):
     `venv/bin/python -m src.main resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4 --output-dir output/sr1d/hold_off/match --config output/sr1d/hold_off.yaml --device mps --skip-visualization --serve-events`,
     then report near/far serve hits and the total action count with a short
     one-off script under `output/sr1d/` that imports `scripts/score_serves.py`
     (`serve_rows_from_contact_gt`, `production_candidates`, `match_candidates`;
     never re-implement the matching). `score_serves.py` has no pipeline-path
     flag; do not add one. Baseline arm = `output/20260920_match_ari_joan_lost/`.
- **pre-registered reading (descriptive, nothing ships):**
  - `global lift is SAFE-LOOKING` = every entreno F1 within ±0.01 of baseline AND
    the e2 bystander is not fed longer than in baseline.
  - otherwise `global lift REFUTED` → the serve-zone exemption needs design
    (architect / owner), which is the expected outcome.
- **deliverables:** `docs/sr1d_hold_horizon_cost.md` (per-clip table both arms,
  e2 bystander counts, match serve hits near/far + total action count both arms).
- **STATUS edits when done:** card status → `DONE (#<session>): <reading> — <numbers>`;
  open point 30 SR1d line; Learnings line; Session index line; Log entry (archive
  the oldest verbatim). Do NOT write a new card. Commit ONLY the doc + STATUS (+
  the archive) in one commit: `#<session>: SR1d DONE - <reading>`. `output/` is
  git-ignored; never force-add it.
- **stop and ask if:** the config does not merge; any run crashes; the baseline
  artifacts are older than the current `src/`.
- **est. cost:** ~15 min entreno + ~35 min match.

### CARD D4 — owner gate (not executable by a worker)
- **status:** DONE (#62): DECIDED — M-a stays CLOSED, M-b is **PARKED** (ceiling
  +1 of 16, +2 with P5; the blunt lift measured net 0 and its cost is match-wide
  identity churn, not a rally-opening failure). No `src/` A/B was approved. Next
  card = SR4a.
- The planner presents SR1c/SR1d to the owner and asks: A/B M-a in `src/`? design
  M-b (serve-zone exemption)? A cheap executor that reaches this card STOPS.

### CARD SR4a — the near-opening table: what the pipeline emitted around every serve, no `src/` change
- **status:** READY
- **type:** measurement (diagnose-only)
- **goal:** split the 8 match near-serve misses into "repairable after the fact"
  (wrong label / wrong rally opening) and "never produced" (reach gate, ball not
  seen), which decides whether SR4 — the post-hoc per-point serve record — can be
  built without touching `src/`, and reopens the parked tracking exemption (M-b)
  only on a pre-registered count. Open point 30, D4 (#62).
- **why:** D4 (#62, `docs/d4_gate_brief.md`): M-b's ceiling is **+1 near serve of
  16** (+2 only with P5) against a 0.90 bar that needs 15 of 16, and the blunt
  version measured net 0. SR4 is the cheaper next step and needs no change to the
  main pipeline — but only if the missing contacts are actually present in the
  emitted actions, which is exactly what this card counts.
- **read first (nothing else):** AGENTS.md; this card;
  `scripts/score_serves.py` (IMPORT, never re-implement: `build_match_session`,
  `build_entreno_session`, `serve_rows_from_contact_gt`, `production_candidates`,
  `game_on_candidates`, `match_candidates`, `match_split`, `entreno_split`,
  `entreno_squad_to_side`, `classify_false_positives`); `scripts/relabel_serves.py:87`
  (`GAP_SERVE_MIN = 143`); the `actions` and `game_state` keys of one pipeline
  artifact; one line of `output/sr1c/match_full_diag.jsonl`.
- **may create:** `scripts/probe_near_openings.py`, `tests/test_near_openings.py`,
  `docs/sr4a_near_openings.md`, `logs/sr4a_report.md`, `output/sr4a/**`.
- **may modify:** `STATUS.md` (only the edits listed below).
- **must not touch:** `src/`, `ground_truth/`, `scripts/score_serves.py`,
  `scripts/relabel_serves.py`, `docs/d4_gate_brief.md`, ANY vall_dhebron input or
  output (held-out lock), and every `output/` artifact except reading (no decode,
  no re-run, no seek).
- **inputs (all exist, read-only, no decode):** match actions + game state
  `output/20260920_match_ari_joan_lost/pipeline_output.json`; match GT
  `ground_truth/20260920_match_contacts.json`; drill actions
  `output/sr1d/base/entreno_{2,3,4,5,6,7}/pipeline_output.json` (the #61 BASE arm);
  drill GT `ground_truth/video_entreno_{2..7}_annotations.json`; player-track
  diagnostics `output/sr1c/match_full_diag.jsonl` (covers match frames 0-26060,
  including all 16 near GT serve frames — verified 2026-10-02).
- **steps:**
  1. Write `scripts/probe_near_openings.py` (no `cv2` import at all — this card
     decodes nothing). It prints a per-GT-serve table and the totals below.
  2. MATCH: GT serve rows from
     `serve_rows_from_contact_gt(json.load(open("ground_truth/20260920_match_contacts.json")), match_split)`
     → **16 near + 17 far**. Emitted candidates = the `serve`-labelled actions via
     `production_candidates(pipeline)`; rally onsets = `game_on_candidates(pipeline)`
     (`start_frame` per point). DRILLS: read the ACTIONS from
     `output/sr1d/base/entreno_N/pipeline_output.json` EXPLICITLY (do NOT rely on
     `build_entreno_session`'s own path — it prefers `output/sr1/entreno_N`) and
     the GT rows from `build_entreno_session(N)`'s `gt` file with `entreno_split` /
     `entreno_squad_to_side`. Compare the two drill action files for N in 2..7 on
     `(frame_number, action, team)` and report in the doc whether they are
     identical (#61 measured them identical; if not, say so and score the sr1d arm).
  3. **Window per GT serve:** it starts at the last action before the GT frame whose
     gap to its own predecessor is >= `GAP_SERVE_MIN` (imported from
     `scripts/relabel_serves.py`, reused AS IS — never re-tuned, never redefined)
     and ends at the first action after the GT frame on the other team. Per action
     in the window record `frame_number`, `action`, `team`, `touch_number`,
     `rally_id`, `track_id`, and the gap to the previous action. Also record the
     rally-onset offset `min |start_frame - gt_frame|` and the `rally_id` of the
     action nearest the GT frame.
  4. **Buckets, one per GT serve, pre-registered** (tolerance ±15 f, side-correct):
     - `hit` — an emitted `serve` within ±15 f on the serve's own side.
     - `emitted_mislabeled_opener` — no `serve` within ±15 f, but an action on the
       serve's own side within ±15 f that IS the window's first action.
     - `emitted_not_opener` — an action on the serve's own side within ±15 f that
       is NOT the window's first action (inside an earlier rally: the P5/P33 class).
     - `not_emitted` — no action on the serve's own side within ±15 f.
     - Per FAR serve, additionally count `far_unseen_near_reception_first`: a
       near-side action within ±15 f AND no rally onset within ±15 f. Raw count
       only — it is the trap guard, not a bucket of the near table.
  5. **Gate G1 (reproduce the recorded baseline — run it BEFORE reading a single
     bucket):** `venv/bin/python scripts/score_serves.py --detail`, and the probe's
     own recount, must BOTH give match near **8/16**, far **0/17**, **12** false
     serves, drills e2-e7 near **3/5**. If any number differs: STOP and report the
     difference. Do not adjust the window, the tolerance or the buckets.
  6. **Coasting read (feeds the reopen rule only):** scan
     `output/sr1c/match_full_diag.jsonl` line by line (sequential, keyed on the
     `frame` field — no seek). For each of the 8 match near MISSES at its GT frame,
     take the `players` entry whose `team` is the serve's court side and whose
     `bbox[3]` (foot) is maximal — the player nearest the camera on that side, which
     is where a server waiting behind their own line stands — and record its
     `predicted` flag. Print that frame's full `predicted` list beside it so the
     reading can be re-cut without a re-run, and state in the doc whether this
     dump is the base arm; if the arm is recorded nowhere, write "arm not
     established" and do not assert it.
  7. **Gate G2 (pre-registered reading, DESCRIPTIVE — it decides order, nothing
     ships; `MISS_NEAR` = 8, the match near misses):**
     - SR4's near side proceeds after the fact iff
       `emitted_mislabeled_opener + emitted_not_opener >= 4` of `MISS_NEAR`.
     - M-b is REOPENED — as a fresh architect call with a lift-arm diag dump, NOT
       as a build — iff `not_emitted >= 3` of `MISS_NEAR` AND in `>= 2` of those
       the lowest-foot same-team track at the GT frame has `predicted: true`.
     - Both may be true; SR4 still goes first, because it needs no `src/` change.
     - Record the `far_unseen_near_reception_first` count. If it is `>= 1`, state
       that any near-opener rule MUST carry an onset-side guard.
  8. Tests `tests/test_near_openings.py`: synthetic-row unit tests for the window
     builder and every bucket (a right-label `serve` as the window's first action;
     a `dig` first action → `emitted_mislabeled_opener`; a `dig` third action inside
     an existing rally → `emitted_not_opener`; an empty window → `not_emitted`; a
     far serve with a near action and no onset → the trap), plus a test that
     `GAP_SERVE_MIN` is imported from `relabel_serves` and equals 143. 10+ tests.
     Then `venv/bin/python -m pytest tests/ -o addopts=""` must be green at
     **1156 + the new tests** (1156 is the measured count at `1f8f62a`; if the
     count differs, report the number, do not chase it).
- **deliverables:** `scripts/probe_near_openings.py`; `tests/test_near_openings.py`;
  `docs/sr4a_near_openings.md` (per-serve window table; the four bucket counts over
  the 8 match near misses; the same table for the drills; the 12 false serves with
  their window neighbours; the coasting read; the trap count; the two G2 verdicts as
  counts, never rates; every claim marked measured or inferred);
  `logs/sr4a_report.md`.
- **STATUS edits when done:** open point 30's SR4/SR4a line; *Where we are* Active
  next item 1 (`READY` → `DONE` with both G2 verdicts); a Learnings line ONLY if a
  durable new fact appears; the Session index line; and a `**SR4a (delegated step).**`
  paragraph appended to the existing #62 Log entry — do NOT open a new dated Log
  entry and do NOT archive anything (the coordinator trims). Do NOT write a new
  card. Commit ONLY `scripts/probe_near_openings.py`,
  `tests/test_near_openings.py`, `docs/sr4a_near_openings.md` and `STATUS.md` in
  one commit: `#62: SR4a DONE - <one line with the numbers>`. `output/` and `logs/`
  are git-ignored; never force-add them.
- **stop and ask if:** G1 fails; any named scorer function is missing or its
  signature differs; a GT serve frame has no line in the diag dump (report
  `diag_absent`, do not count it as coasting); the two drill action files disagree;
  anything from the held-out session turns out to be needed.
- **est. cost:** ~20 min coding + ~10 min running. No decode.

## Open points

Ranked backlog. One compact entry per point: current status, the problem,
the next step. Numbers are stable across reorganizations — reference them
("point 22") in sessions and commits. Full per-point histories: grep the
point number in `docs/history/`.

### Active

30. **Serve reliability, BOTH sides (new, #55; supersedes point 22's
    far-only framing).**
    - **Status:** IN PROGRESS (`docs/serve_reliability_plan.md`). SR0 DONE #56,
      SR1 DONE #57, **SR1b (review) DONE #58**, SR3 owner half DONE #58,
      **SR1c CLOSED #60 (no mechanism; owner "leave as is")**,
      **SR1d DONE #61 (global lift REFUTED)**,
      **D4 DECIDED #62 (architect, on `docs/d4_gate_brief.md`): M-a stays CLOSED,
      M-b is PARKED** — its ceiling is **+1 near serve of 16** (+2 only with P5)
      against a 0.90 bar that needs 15 of 16, and the only measured version was
      net 0 (**+P7 / −P18**, false serves 12→14, actions 207→212).
      **P18 is an ATTRIBUTION SWAP, not a rally_start failure** (corrected #62):
      the same ball point (867.5, 313) in both arms, touch 1 in both, a NEW rally in
      both, and the toucher track goes 3→2 — the hit is credited to the server's
      PARTNER, so it reads `dig`; the lift also renumbers tracks match-wide
      (f2494: track 1 → track 4). Any exemption changes identity wherever it
      fires, so its price is only measurable on a full-match run.
      Next = card **SR4a**; M-b reopens ONLY if SR4a measures
      `not_emitted >= 3` of the 8 match near misses with the server coasting in
      >= 2 of them — and then only as a fresh architect call with a lift-arm
      diag dump.
    - **Problem:** production serve recall is 8/33 (near 8/16, far 0/17) and
      precision 0.40. The far evidence layer is 13/17 covered (**in-sample**),
      4/12 held-out binding. The near side's losses are now MEASURED (#58): contact-frame
      foot for `behind_baseline` (P9-P12), the 90 f off-court hold (P5/P7), e2
      server never tracked, e5 no ball. Audio and the beach serving rules are unused.
    - **Acceptance** (on a session NOT used for design, ±15 f): recall ≥0.90 on
      each side, side/squad ≥0.95, ≤0.1 false records per point, server identity
      ≥0.90 after SR5. If SR4 is below 0.75 on either side held-out, stop hand
      rules and go to SR7 when its trigger fires.
    - **Tasks:**
      - [x] **SR0** `scripts/score_serves.py`: every stream (production, pass-2,
        serve_evidence coverage/binding, rally onset, SR4 records) scored per
        side, dev / held-out / new session. Gate PASSES (near 8/16, far 0/17,
        12 FP). Findings: rally onset times **11/17 far** serves at |offset| 3 f
        vs 3/16 near at 14 f (far timing is nearly free, near is not); production
        near hits are all within ±2 f; 8 of 12 FPs are dead-time handlings, 3
        named rally contacts; the evidence layer is **13/17** covered (the "14" is
        a near serve) and **0.47** precision as a claim. **Done:** all 7 entreno
        clips re-run with `--diag-dump` under #57 (their old artifacts predate
        the v3 model); practice serves are 3/5, not 4/5.
      - [x] **SR1** near-serve miss taxonomy, diagnose-only
        (`scripts/probe_near_serve_misses.py` + `docs/sr1_near_serve_misses.md`):
        10 misses = **6 `label` / 3 `no_contact` / 1 `other_side_contact`**. The
        label bucket is one mechanism (`behind_baseline` false at a rally-opening
        contact, 5/6; the 6th is a `rally_start` cascade from our own early serve
        emission at P33). `no_contact` splits P5/P7 (stage 4 **reach gate**,
        448/204 px vs 140) and e5 (stage 3, `no_ball_sighting` x15/31f).
        **[#58: superseded by SR1b]** the "one mechanism / not a tracking problem"
        reading and the "label-free SR4 test" next step are withdrawn.
      - [x] **SR1b** review, diagnose-only (`docs/sr1b_near_serve_causes.md`,
        worker report `docs/sr1b_worker_report.md`; match [0,15000] pass, parity
        111/111, + hold-off counterfactual [0,8000]): P9-P12 = contact-frame foot
        0.8-24.5 px inside the threshold (server tracked); P5/P7 = server track
        coasts from exactly 91 f after its last in-court sighting (hold = 90);
        lifting the hold makes P7 a hit, P5 a `dig` (rally_start killed by a
        handling 78 f earlier). `NEAR_NET_PX = 120` covers ~80% of the beach near half.
      - [x] **SR1c** (card) takeoff-stance `behind_baseline` measured over diag
        dumps — **CLOSED #60, nothing shipped**: the reproduction gate FAILED
        (194/207 match, 6/7, 13/14 vs ≥98%/session) because every one of the 15
        disagreements is a contact whose toucher had no fresh detection at the
        contact frame (box carried forward, or absent from the tracked list),
        while the shipped read came from the player's last real position — up to
        7 f LATER. Owner-confirmed from the frames: only P17/P19 of those 15 are
        serves, and those are exactly the two a backward-only stance read loses;
        at K = 10 the same rule would gain P11/P12 (P9/P10 read false at every K),
        a +2/−2 trade before knock-on effects (unmeasured). `docs/sr1c_takeoff_stance.md`.
      - [x] **SR1d** (card) cost of lifting the hold horizon on entreno + full match — **REFUTED (#61, nothing shipped)**: 14 runs (both arms; baseline re-run, `src/` had drifted at `d402f65`), no `src/` change. Entreno **ΔF1 0.000 on 7/7** with byte-identical action streams; the e2 sideline bystander is fed **423 f vs 400 f** (and is fed on 400/423 even at the 90 f horizon today, so that horizon no longer buys the track's life — 08-29's premise is stale). Match: near **8/16 → 8/16**, far 0/17 → 0/17, FP **12 → 14**, actions **207 → 212**; the composition is **+P7 / −P18**, and **#62 re-reads P18: it is an attribution swap, not a rally_start failure** — the same ball point (867.5, 313) in both arms, touch 1 in both, a NEW rally in both, the toucher track 3→2 (server→partner) so the contact reads `dig`; the lift renumbers tracks match-wide (f2494: track 1 → 4). So the cost of ANY hold exemption is unbounded by this run: it is an identity change wherever it fires, not a rally-opening failure. `docs/sr1d_hold_horizon_cost.md`.
      - [ ] **SR2** (DEMOTED #58: timing is not the bottleneck) `scripts/probe_audio_onsets.py`, diagnose-only, PTS-mapped.
        Kills: K1 onset at <70% of serves on either side; K2 dead-time-onset
        proposer precision <0.8 on dev; K3 far onset rate more than 15 pts below
        near.
      - [~] **SR3** owner half DONE (#58 committed
        `ground_truth/20290928_entreno_vall_dhebron_serve_anchors.json`, schema
        `serve-anchors-v1`, 19 serves: 8 near / 11 far, `ace` f10981, `net` f2095).
        **Held-out lock:** never run / scored until rules are frozen. Worker half:
        teach `score_serves.py` the `serve-anchors-v1` format, then one run with
        `--serve-events`, scored once. Owner question: is it game play under beach
        serving rules (SR5 assumes it)?
      - [ ] **SR4** per-point serve record (`output/serve_records.json`): opener
        gate, then a side vote (runway / behind-baseline / width trend / first
        receiver side / structural arm), then the time (audio if SR2 survives;
        **on the far side the rally onset already gives the time at |offset| 3 f**
        -- SR0). Near side: consume the production near label once M-a / M-b land
        (#58 SR1b; the label-free test is withdrawn). Optional toss/pose
        check for the pre-serve-handling FPs (8 of the 12 measured). Promotion =
        INSERT a serve into `actions_pass2`/DB after acceptance on ≥2 sessions,
        never relabel.
      - [ ] **SR5** DP/HMM over points (winner serves next, the server alternates
        on regaining the serve, side switch every 7). GT winners stay
        validate-only. Measure serve-squad accuracy and winner accuracy (18/33
        today).
      - [ ] **SR6** ace / service fault from SR4+SR5, which unblocks point 13 and
        the fantasy module.
      - [ ] **SR7 (DEFERRED)** learned serve detector (pose + raw ball + audio),
        leave-one-session-out. Trigger: ≥3 sessions and ≥100 serves of GT.
    - **Owner decisions:**
      - **D1: APPROVED (#55 follow-up).** The audio probe SR2 goes ahead. Adopting
        audio in production is still gated on SR2's kills.
      - **D2: APPROVED, scoped down.** The owner labels serves on
        `20290928_entreno_vall_dhebron.mp4` only. The 05-05-2025 video is DROPPED
        (bad conditions) and is being removed from the repo. The SR3 target becomes
        "every serve in vall_dhebron, both sides".
      - **D3: APPROVED.** The post-hoc per-point serve record (SR4 evidence for
        when and which side, plus SR5 beach-rules decoding for who served) is THE
        serve product. The causal far-serve contact chase stops. (#58: near-side
        perception fixes M-a/M-b are NOT the far chase and are compatible with D3.)
      - **D4: DECIDED #62 (architect, on `docs/d4_gate_brief.md`; owner relayed
        2026-10-02).** **NO `src/` A/B of M-a** — SR1c could not reproduce the
        shipped read, and the mechanism it points at trades +P11/+P12 for
        −P17/−P19. **M-b (serve-zone exemption from the 90 f hold) is PARKED, not
        built**: ceiling +1 of 16 (+2 with P5), the blunt lift measured net 0, and
        its cost is match-wide identity churn (P18) that no cheap run can bound.
        The two new false serves sit at the right edge of the image and no
        foot-behind-the-line test has been measured against them, so a geometric
        exemption would be designed blind. M-a's predecessor question (M-a's
        back-looking stance read) reopens only with a foot signal that has a FRESH
        detection at the hit — none exists. **Next: card SR4a**, then SR4, then
        the held-out run once, then SR5 → SR6.

22. **Far-side serves** — **[#55: SUPERSEDED by point 30. The far-serve contact chase is STOPPED, and its runway/structural evidence is reused as SR4 inputs. The '14/17 at zero FP' figure is IN-SAMPLE (swept on all 17); the held-out binding is 4/12.]** **[#53 SOLVED AS EVIDENCE: 14/17 at ZERO false
    positives, from 0/17.]** Status: the mechanism is MEASURED and the owner
    decision is the OPERATING POINT; the implementation step is a post-hoc
    consumer (S4), not a `src/` label. T5 (tracker), R1 (departure gate), S1
    (looming), scale-aware geometry (#52) and the magnified far-end pass (M1,
    #53) are all refuted, each for a *measured* reason. The winner uses the raw
    detections directly, so it is immune to both walls the earlier levers hit
    (the tracker will not lock a far ball; the px-space contact tests cannot
    reach their thresholds at the far end). **[#42 RE-SCOPE] POINT-level DONE,
    CONTACT-level OPEN.** Measured 09-30 (`output/serve_relabel.json` vs dev GT P1–P8):
    the 5 relabeled far "serves" (f247/930/2195/3070/4801) are 31–50 f after
    the GT serves (f210/880/2154/3038/4770) = 0/5 at contact level; three are
    the GT receptions (245/3071/4800) relabeled, two (930, 2195) are dev
    in-point-spurious digs; 12 of the 16 far serves carry a team override.
    Every "8/8", "31 serve-typed" and "13 team overrides = width-band class"
    below is a POINT-level statement. Consequence: the receiver's dig is
    consumed and the true serve contact (aces, serve faults, who served) is
    still missing — the gap G3 and G1 share. Next = S1 far-serve looming probe
    (Active next), validated on the S0 GT (open point 24); T5 (tracker) and
    R1 (departure gate) already refuted; option "park at pass-2" rejected.
    **[#44: S1 RAN and was REFUTED at kill 2 — the dev far-serve `L`
    (0.338 lowest) overlaps the new-rally non-serve `L` (0.945 highest), so no
    looming threshold admits all 5 without false fires; kill 1 passed at the
    boundary (4/5 far serves detected), i.e. the far flight IS in the track.
    `src/` untouched; S2 not triggered. Next = owner decision on the next
    far-serve lever: targeted far-flight detector mining (#42's kill-1 branch
    does NOT apply since kill 1 passed) vs another contact-proposal mechanism.
    S0 GT + capture spec remain the highest-value async inputs.]**
    **[#53: the lever is found and measured — `docs/g4_structural_serve.md`.
    Opener gate (M2) takes the G4 conjunction from 11/17 @ 0.579 to 11/17 @
    1.000 (0/24 control FPs), with a 60-240 f plateau because the match
    separates openers (>=153 f) from mid-rally gaps (<=134 f). The structural
    proposer (M3') over raw detections measures 11/17 @ 1.00 (runway-only),
    15/17 @ 0.94, 17/17 @ 0.90, and the union of the two zero-FP rules is
    **14/17 with no false positive at all** across 24 mid-rally contacts and the
    9 owner FALSE/OFFGAME moments, at median |offset| 1 f. M1 (4x far-end crop) is
    REFUTED and corrects the record: the far ball is detected in 14-31 of 31
    frames at every serve (the "0-1 tracked frames" figures are TRACKER counts).
    Also fixed: the windowed G4 probes SEEK and a seek on this VFR file lands
    -28..+30 f off, so the old 6/17 was really 11/17 with -9 f offsets
    (`docs/g4_far_serve_alignment.md`, now guarded by `tests/test_vfr_seek_guard.py`).
    **Next = the owner picks the operating point (recommend the 14/17 union),
    then S4 consumes it post-hoc as a serve EVIDENCE record (never as a label —
    S0b broke 3 correct dig labels).**]**
    **[#54: the owner picked the recommended 14/17 union and it is BUILT —
    `docs/g4_serve_evidence.md`. The structural arm shipped inside the
    `--serve-events` envelope and `scripts/consume_serve_evidence.py` writes
    `output/serve_evidence.json` (87 records, 19/33 points bound, 21 with both
    arms agreeing, 1 owner false positive -> precision 0.90). Inertness is
    MEASURED (action streams byte-identical with the emitters ON vs OFF). The
    honest split: evidence coverage 14/17, consumer binding 9/17 (dev 5/5,
    held-out 4/12). Three of the five binding misses (P14, P22, P23) have NO
    record near the serve; two (P28, P31) have a second record 8-19 f from the
    contact that nothing in the emitted stream disambiguates. **Next = the
    NET-CROSSING selector (a served ball crosses the net line toward the camera;
    the 578 `far_flight` events already carry the evidence) as a post-hoc
    computation over the existing artifact, no re-decode, then S4's ace /
    serve-fault derivation.]**
    **[#45: S0b measured the whole pass-2 stream at CONTACT level
    (`scripts/score_pass2_contacts.py`, `docs/g3_s0b_pass2_contact_score.md`):
    far serves 0/5 with deltas +31..+50 f = 5.4-8.6x the effective ±0.52 s
    tolerance, and only 1/8 GT serves matched at all — f2575/f3747 are
    `anchor_only` with NO action within ±80 f, so the "far prefix census 8/8"
    counts ANCHORS, not contacts. Pass-2 contact F1 0.597 → 0.604 (flat) but
    class accuracy 0.706 → 0.562: it breaks 3 correct dig labels (f245/3071/
    4800) and loses 1 TP to the f3856 demotion. The "park at pass-2" option
    is CLOSED, and pass-2 must not be consumed as a LABEL source by S4 until
    the real serve contact exists. Far-serve CONTACT work stays owner-gated on
    S0.]**
    **[#46: the held-out labels now EXIST (owner dictated P9–P33 contacts,
    12 of them far-serve), so this point is no longer data-starved — it is
    mechanism-starved. #47: G0 (transcribe) DONE —
    `ground_truth/20260920_match_contacts.json` (211 contacts, P1–P33). #48:
    G1 held-out score DONE — far serves **0/12** on P9–P33 (8/12 have a
    nearby emitted "serve": 6 are the pass-2 re-labelled GT reception +26…+34 f,
    2 are production serves 26–28 f late with the opposite team; 4 have nothing
    within ±80 f). Baseline F1 0.772 / class 0.590 / team 0.518
    (`docs/g3_heldout_p9_p33.md`). Next = the G2 owner decision on the lever.]**
    **Status (as of 28th session): MECHANISMS 1+2+3 DONE (mech 3 shipped
    09-28, 28th session).** Mechanism 3 = pass-2 serve re-labeling
    (`scripts/relabel_serves.py`, +29 tests): per TRUE map window, the
    rally-opening contact is re-labeled serve by structural prior (t1 +
    dead-ball gap 143f = midpoint of the measured chasm: openers ≥153f,
    mid-rally ≤134f; window-opening position). Precedence ladder, all
    owner-backed: owner FALSE/OFFGAME demote; owner TRACKED/MISCLASSIFIED
    verdicts beat the gap veto AND the fault-description guard; anchors
    turn a rejected opener into anchor_only (P5, P7); P20 owner-pinned to
    14516A (round-2 q5, structured in OWNER_PINNED_SERVES); P32
    report_only (fault desc + 8 post-opener actions, no owner verdict);
    6928A structural-FP reported, never demoted without an owner verdict.
    Gates: far prefix **2/8 → 8/8** (≥6/8 ✓); serve-typed **20 → 31**
    (−6 demoted +17 relabeled; ~28 sanity anchor overshot — 30/33 points
    hold an in-stream serve action, all distinct, 6928 included); ALL 17
    owner verdicts reproduced mechanically (P9-P12 at the exact contact
    frames); 13 team overrides flagged (emitted toucher team vs
    anchor/winner-serves: P1/P2/P6/P8/P14/P21/P22/P25/P26/P28 A→B,
    P24 B→A, P23/P31 emitted-fix A→B — the far-side width-band class);
    entreno neutral by construction (zero src/ changes); suite 554.
    Output: `output/serve_relabel.json` (resolutions + demotions +
    `actions_pass2` annotated stream + gates). Round-3 owner queue from
    this layer: P32's serve, 6928A's verdict, P20's window/re-serve
    question, P23/P31 team-fix confirmation.
    Mechanisms 1+2 (09-27, 26th session; full detail in git + archive):
    `map_episodes_to_points.py` (+34 tests; monotone DP, physics
    constraints, serves attribute to exactly one point) + the owner's
    RATIFIED serve anchors P1-P17 with 7 FALSE serves + 4 OFFGAME ranges
    (`ground_truth/20260920_match_serve_anchors.txt`) + the detector
    probe (`probe_serve_tracking.py`: dets present at EVERY serve, conf
    0.86-0.92 — detection is NOT the loss; the losses are the
    serve-ACTION gate, bump-serve gesture misclassification, and
    P15-class static suppression, which bites only on P15's slow float).
    Round-2 contact sheets adjudicated every disputed moment; the
    P13-P17 chain is FORCED by the verdicts. Tail findings (DP-inferred,
    round-3 queue): ep45 (confirmed 1-dig, unattachable) forces P20's
    owner-confirmed serve (14516A) to burst — needs P18-P20 anchors or
    an ep45 verdict.
    **Infra rule: VFR file — never CAP_PROP_POS_FRAMES seeks; decode
    sequentially.**

21. **Owner's match-feedback backlog** (agreed order; GT exists for all).
    **[#42 order: (4) side-switch = S3, then (3) winner = S4 — both after S1's
    far-serve contact work so serve/reception contacts are real.]**
    (1) *Point count:* ball half SHIPPED (conf floors + v3); point-layer
    windows now binding at 31/33 — re-tune group_gap/contact_chain/confirm
    jointly on the game-state video + the 25.7fps match; emit every rally
    candidate with a confidence (no silent skips). Likely partly moot —
    verify the residual 2 misses aren't far-side-serve losses (→ 22).
    (2) *Per-point + per-action confidence:* gesture × attribution
    certainty (width votes/abstain) × ball-track continuity; points:
    n_actions + confidences + tracked fraction + serve presence; incl.
    live badge. (3) *Point winner/score layer:* pure observer — ball-death
    side + last-touch team + kill/out; validate vs all 33 dictated
    winners; feeds aces (13). **[#43] SHIPPED as `scripts/resolve_point_winners.py`
    (fault prior over the terminal touch; 33/33 decided, 18/33 vs the dictated
    winners — 54.5%; `docs/point_winner_layer.md`). Ball-death side/in-out is
    absent from every artifact, so kill/ace endings (3 misses) stay honest
    fault-prior misses; 8 misses are terminal-touch attribution (→ 22).** (4) *Side-switch layer:* **[#49 DONE 2026-10-01]** persistent
    all-player side flip between points (majority + serve-side evidence),
    cross-checked vs score expectation; ALL team fields become squad
    identity; overlay labels must swap; target = exactly the 4 GT switches
    after points 7/14/21/28. SHIPPED as `scripts/resolve_side_switches.py`
    (+25 tests, `docs/g3_side_switch_layer.md`): beach cadence from the point
    order alone reproduces `[7,14,21,28]` exactly; side→squad by parity;
    `actions_pass2.pass2_squad` for downstream. The player-crossing
    cross-check is EVIDENCE ONLY — noisy because ids hop (open point 2), so
    the cadence places the switches. Corrected G1's raw team 0.518 (side vs
    squad) to **0.755** squad-mapped, 34 genuine side errors. (5) *Persistent player numbers:* GT pass
    around the switches first (`annotate_player_gt.py`), then GAME_OFF
    dead-time gallery mode (18a lever) + size/appearance gates on
    continuous feeds; Phase 2 stitch (6) only if fragmentation persists.
    (6) *Landing/outcome confidence:* distance-to-line/net in ground
    metres + abstain band; "hard to call" must read LOW. Parity rule
    applies to all layers.

2.  **Side-change survival (player identity) — BLOCKED on the GT pass.**
    The roster machinery SURVIVED the full match: ids 1-4 only, 0 ghost/
    recycled ids, swap-rate 0.00, team acc 97.9%, coverage 3.28/4,
    dead-time persistence 3.05/4. BUT 46 resurrections and a visually
    confirmed mid-rally identity hop (id2 woman→man, both in-court —
    `output/match20260920/sheet_id3_cross_f1250-1350.png`; the in-court
    preference cannot separate them) and 12 per-episode all-4 side-mapping
    changes vs ~5 official switches. **Next:** GT pass on a few points
    around an official switch to measure hop rate → then judge the
    dead-time gallery horizon (18a lever) vs a stronger appearance
    tie-breaker. Not blocked by 22 (tracks dump is ball-independent).

1.  **e1/e3 tracking baselines stale vs recorded numbers** (diagnosed
    08-18; pre-existing, NOT the serve-zone fix). Old-code dumps: e1 id
    0.771 / ghosts 0.193 (recorded 0.978/0.133); e3 id 0.952 (0.972).
    Byte-identical A/B proves the 08-18 fix is e1/e3-neutral. Drift crept
    in between the 08-16 baselines and HEAD (prime suspect:
    ball_confidence 0.7→0.15 or device CPU→auto). **Rule: compare A/B,
    never vs recorded numbers; diagnose when touching tracking next.**

7.  **Action-recall residuals (post short-gap bridge).** e2: f90
    held-ball release (structurally invisible — no descent signature);
    f32 serve mis-attributed (server inadmissible before f28); f118
    overpass-vs-set (its follow is 91f, one past rally_reset_gap=90);
    f167 dies at the reach gate by 4px and the true toucher is airborne
    mid-jump → needs jump-aware reach/ghost handling, NOT a new detector.
    e2/e6 GTs still lack player boxes. e1's far-side recall lever
    (`player_confidence` 0.5→0.35, `player_imgsz` ↑) unchanged/untried.

15. **Classifier-gate residuals after the ball-matching rework.** Items
    (a)-(d), (f) RESOLVED 09-08..09-19 (serve gate, stance team, touch-3
    fall-through, redirect locality, e7 GT ratified — archive). Still
    open: **(e) tracking-side** — e7 f160 toucher untracked (by design;
    GT agrees), f300 spike ball never tracked there (→ 22 family), f370's
    set sits in a 6f sighting gap, re-appears descending (no bridge
    signature; parked). **(g) Multi-court simultaneous play** — motion
    lock takes the first mover at bootstrap; needs tournament footage.

14. **[game-state] Remaining limits.** (a) No per-event serve detector
    exists in this ball-track data — every candidate feature measured and
    REFUTED (burst width, static hold, near→tape→far crossing); the
    provisional badge fires on ANY sustained flight (known cost on
    practice footage); revisit a directional/width-regime side gate on
    match footage where serves are the only net entries. (b) pt00
    (coach-fed, ONE contact) unrecoverable under ≥2-actions; pt03 loses
    to contact-chaining. (d) contact_chain_frames=240 margin thin
    (in-rally max 215f vs boundary 262f). (e) points table not rendered
    in the web UI yet.

19. **Deliberate deferrals from the match intake.** (a) ~25.7fps effective
    vs 30fps tuning — frames-based windows span ~17% more wall-time,
    px/frame speeds −14%; deferred, revisit only on contact-window misses
    (the e3 probe did NOT implicate it). (c) The upscale is hooked in
    `src.main` only; `scripts/test_*.py` probes still read raw files.
    (d) Venue sand fires the detector at ~2.2 det/frame (lines/footprints/
    shadows) — production motion gates absorb it; if width-side wobbles
    appear, check TRACKED-sample provenance, not thresholds.

18. **Squatter-review known limits.** (a) Real players off-court between
    points look squatter-like — ready lever: pause the review while
    game-state says GAME OFF. (b) e7-class straddler front end
    (f47-~f145) irreducible without admission erosion — parked until a
    real-player line-margin is measured. (c) The cooldown may block a
    real player planted within 0.5 m of an expelled squatter (new-track
    admission only, never existing tracks). (d) A rolling-window fraction
    would fire ~27f earlier — deliberately not built (lifetime is simpler
    and occlusion-safe).

24. **Match-domain contact GT + contact-level scoring of pass-2 — [#47: the
    GT IS BUILT; scoring is next]**
    **Status: owner half DONE (2026-09-30); worker half (a) G0 DONE (#47,
    2026-10-01).** `ground_truth/20260920_match_contacts.json` carries 33
    points / **211 owner contacts** (28 P1–P8 + 183 P9–P33) on the match frame
    axis; dialect B is parsed by `parse_contact_gt` (`scripts/build_dev_clip_gt.py`),
    the builder is `scripts/build_match_contact_gt.py`, and the shapes/owner
    conventions are documented in `ground_truth/README.md`. The 8 P1–P8 points
    rebuild field-identical to the committed dev GT (only physical
    `raw_line_no` shifted +3); sheets in `output/match_contact_sheet/`.
    Next: (b) G1 = the first held-out contact score on P9–P33 (perception +
    pass-2 arms) — **[#48 DONE 2026-10-01]**: production F1 0.772 / class
    0.590 / team 0.518, pass-2 0.774 / 0.561 / 0.561; far serves **0/12**;
    `scripts/score_heldout_contacts.py` + `docs/g3_heldout_p9_p33.md`; (c) from
    then on every pass-2 layer is scored at contact level, and any threshold
    fit on dev P1–P8 must hold on P9–P33 before it ships. The dictated anchors
    are too coarse for contact timing (P8 anchor f4700 vs GT serve f4770), so
    they cannot substitute. Also feeds R2 precondition 1. Known scoring
    caveats for G1: the P30 f23545 event has `action=null`
    (`owner_action_unspecified`) — class-agnostic contact scoring handles it,
    class accuracy must skip it; the match methods
    `match_start_frame/end_frame` in that JSON are episode-map PREDICTIONS
    (`window_is_prediction: true`), never GT (only 12/25 cover their own owner
    contact range, so dead-time/points metrics inherit the drift).

25. **A dig simultaneous with the ball death (new, #46 — OWNER-FLAGGED).**
    P15 f10180: "FT is close to a dig in f10180 but the ball falls to the
    ground first (if the ball falls after a dig or before it it should not be
    counted as a dig, flag as an open point)". Problem: at that frame the
    stream emits (or nearly emits) a dig while the ball is dying, and the owner
    says it is NOT a dig — so the evaluator would charge us a false positive
    for a contact the GT does not contain. Next: decide the GT rule (a contact
    whose ball dies within the same contact window is not a dig) and encode it
    as an EXCLUSION in the contact GT build, not as a pipeline change; then
    check how many of our FPs such a rule would remove (the "dig at the moment
    of ball death" family is probably a chunk of the 3 dead-time FPs).

26. **One contact attributed to TWO players (new, #46 — OWNER-FLAGGED).**
    P16 f10703: "NT digs f10703 (this dig gets attributed to two people, this
    cannot happen, flag it as an open point)"; P19 f13074 the serve "gets
    attributed to two players"; P20 notes the serve flapping between players
    in live debug ("there are two serves"). Problem: double emission for one
    contact inflates FP and can steal a match from a real contact.
    `evaluate_timed` already reports these as `duplicates` (the dev clip has
    1) and T4 saw "1 dup"; now the GT names cases, so duplicates become
    SCORABLE. Next: score duplicates against the GT in G1, and if they are a
    real family, look at the emit path (one inflect, two actors) — likely the
    same proximity ambiguity as open point 5, so measure both together.

29. **Recording-domain docs are stale (new, #46).**
    `docs/video_recording_guide.md` prescribes a camera PERPENDICULAR to the
    net and "30 fps" as a requirement; the owner uses one camera ALWAYS in
    front of the net outside the court, and the fps drops on its own under low
    light / heat (that is the 25.67 fps match). The guide also cannot promise a
    fixed height — it changes per video (court projects 206 px deep on the
    beach vs 464–479 px at the practice venue). Problem: the doc contradicts
    the validated geometry and asks the owner for something the hardware
    cannot do. Next (docs-only, no code): rewrite it to the long-axis spec
    with the measured consequences (px thresholds are venue-coupled; ball
    px-width side signal; width-normalised speeds) and add a
    `scripts/probe_capture_spec.py` pre-flight (ffprobe: CFR/VFR, effective
    fps, resolution, resolution-change mid-file) that flags out-of-spec input
    instead of asking for a different capture setup.

### Parked / conditional

5.  **Same-team adjacent-player choice.** The team filter constrains the
    TEAM, not which teammate — e3 f69's dig goes to the wrong B player.
    Needs pose/reach signals, not team logic.
    **[#46: the owner has now specified what that engine should use, and
    supplied the evidence: "we probably need an engine to decide when there
    are players together to which player attribute the action based on the
    past and based on the ball field" (P18, where two NT mis-attributed
    contacts both landed on the FT player while the ball was in the NT field,
    same player). So the two signals are MOTION HISTORY (who was converging)
    and BALL HALF. Note this is the same failure the P9–P33 GT annotates as
    `missatr` throughout, and the owner states those marks are NOT exhaustive.
    Not scored today (`--ignore-player` is the standing rule because GT
    `player_id` is a per-frame track id); it becomes scoreable only once a
    stable-identity GT exists (open point 2 / owner player labels).]**

6.  **Phase 2: offline global stitch (conditional).** Post-processing that
    re-clusters all track fragments into exactly 4 identities. Build only
    if match validation shows residual swaps/fragmentation phase 1
    doesn't catch.

9.  **Overpass is only detectable at touch-2; "freeball" wants the same
    missing crossing signal.** e1 f113: GT overpass at touch-3, pred dig.
    A naive "last touch with no follow → overpass" breaks e4 f347. Do it
    with the ball-crossing signal threaded into the resolver or not at
    all. Vocabulary ratified: overpass = touch-1/2 crossing, freeball =
    touch-3+ soft cross.
    **[#50 DIAGNOSED and the ball-crossing lever REFUTED on held-out data:
    `scripts/probe_overpass_crossing.py` + `docs/g3_overpass_crossing.md`.
    The width-regime crossing across the contact is present at **3/18**
    held-out GT overpasses, indistinguishable from the non-attack controls
    (set 4/46, dig 10/55); K1 (signal present) and K2 (separation) fire. The
    ball is tracked on BOTH sides at 18/18, so it is not a detection gap
    (K3 clean): the crossing sits at the net/tape where the width regime
    abstains and a high lob reads ambiguously. The perceived next-contact
    team is also unusable (overpass flip 8/18 = 0.444 vs controls 0.582; K4
    fires). So the loss is a LABEL/RULE problem: the resolver emits
    `overpass` only at touch-2-no-follow while GT overpasses span touch
    1/2/3, and the emitted reads were dig 6 / spike 5 / set 2 / missed 5.
    Next = an owner/architect decision on an overpass lever — a
    gesture/touch-rule change plus a RELIABLE possession signal (the
    current team read is 0.755 side-level), never a ball-width threshold.
    The three implementable rules were replayed offline through the imported
    resolver on the dump's raw contacts — next-team (85→71 correct), no-follow
    (85→80, 3/18 overpasses recovered), next-team+side (85→82, 0/18) — ALL
    net-negative, so no `src/` change ships (T5/R1 precedent). The blocker is
    upstream: a reliable next-toucher/possession signal (34 genuine side
    errors, open points 2/5), without which the structural crossing rule
    cannot be built.]**
    **[#52: the possession signal was then BUILT and measured — ball-field
    width trend + motion-convergence tie-break — and REFUTED (base 121/157 →
    122/157; trend 11/11 precise but redundant; motion 0 team changes). The
    carry errors have no ball signal at all (ball lost). Parked default-OFF
    in `scripts/possession_signal_harness.py`; a NON-ball possession signal
    is the open need.]**

13. **Ace metric (parked) — needs point-outcome detection.** Paths: (a)
    derived heuristic in the metrics layer (serve whose rally has no
    opposing-team touch ≈ likely ace, flagged derived); (b) real outcome
    detection (score machinery exists in game_state_manager, unvalidated).
    Assist proxy (set → same-team kill) parked with it.

### Resolved (details: grep the number in `docs/history/`)

20. **Ball tracking on the 20260920 match — RESOLVED 09-26: v3 ADOPTED**
    after the four-leg gate (GT-frames recall 94.2% / @0.4 precision
    95.5% / FPs 330→18; match 31/33 confirmed, first-confirmed at GT pt 1;
    ep35 sky conf restored 0.85/99%). Survivors moved: e4/e5/e6
    re-adjudication (queued), e3 drift FIXED 09-27 (short-gap bridge
    defers only when a fireable normal vertex exists), far-side serves
    → 22.
16. **Bystander squat + joust identity swap — RESOLVED** (tracker:
    in-court preference `off_court_cost_penalty_px`, 09-06; classifier:
    stance-majority team read, 09-08). e6 digger tracked f146→end, no
    f311 swap, e6 team 7/7.
10. **e6 joust spike — RESOLVED** by the reentry contact (09-04, f308
    manufactured at the gap midpoint); e2 f167 "instance #2" REFUTED;
    joust-split ruled not wanted (no-touch block is GT-physical).
11. **GT ratification queue — EMPTY since 09-04** (e1's three mixed
    player_id conventions unified; all videos ratified).
12. **Kill semantics — RESOLVED 08-31:** kill = direct fall OR
    dug-and-dies-without-a-set; e3 outcome 4/4, dug_zone 3/3.
3.  **Over-set crossings — RESOLVED** by the f297 GT correction (e3 team
    14/14). Mechanism note: with ball widths in the 26-35px abstain band,
    a crossing can misattribute the next contact.
4.  **Near-net px flag — GT-REFUTED to switch px→metres** (e3 label F1
    0.929 → 0.857/0.714); the px `near_net` is load-bearing. Revisit only
    with match footage: rerun `diag_gesture_net.py <match>.mp4 --modes px
    m1.5 m2.0` and switch only if gestures differ.
8.  **pred `player_id` = L-R index over the FILTERED candidate set** — not
    a bug; a reading convention (see Learnings).

## Learnings (standing)

- Calibration `frame_dimensions` is (h,w) and is NOT a scale hint: points are used verbatim, only the court mask is sized from it — a smaller calibration on a bigger video silently drops near-half players. `src/main.py` now hard-errors on missing/mismatched calibration (`--allow-uncalibrated` to waive; T1, session 31). Probe scripts share it via `src/detection/calibration_readiness.py` (T1b); they decode at native res, so point them at `_up1080` for sub-1080p sources.

Protocol rules live in **AGENTS.md** (entreno validation, live-debug
parity, diagnose-first, byte-identical A/B, `cv2.setRNGSeed(0)` per
tracker in multi-tracker harnesses). The distilled technical facts below
survive across sessions; provenance in the archives.

**Measurement & eval conventions**
- `evaluate_match_points.py`'s 31/33 ratio compares counts, not temporally matched recall; the episode map/serve relabel results use GT structure and owner corrections, so autonomous winner/scoring evaluation must exclude those inputs (#30 assessment).
- Canonical `pipeline_output.json` persists events, point segments and sparse thumbnail snapshots, not the dense ball/player/pose sequence; temporal-model experiments need a feature sidecar, not just existing event JSON (`json_exporter.py`, #30 assessment).
- The 4-corner ground homography is **badly wrong at the far end** of the beach
  match: it predicts a 1.8 m person ~7 px tall at the far baseline where the
  detector returns 90-160 px boxes (the assumed 16x8 m does not match the
  projected court). Far-end regions must be defined in IMAGE space from the 8
  calibration clicks, never in metres via `image_to_world` (#51).
- A runway band must STRADDLE the far baseline: strictly behind it a person is
  present at only 7/17 GT far serves, `-0.15..+0.30` x court depth at 17/17 —
  far-side servers stand ON the line. Express such bands as a FRACTION of the
  court's projected depth (venue coupling, AGENTS.md §7) (#51).
- A foot-based ground gate is wrong for the BALL: the contact happens at hand
  height and the ball is airborne afterwards (a far serve rises to y~306, above
  the wedge apex at 504). Gate ball sightings on the NET line instead (#51).
- A far ball is detected on roughly **1 frame in 4** (beach match); any
  consecutive-frame run logic throws the flight away unless it tolerates ~3-frame
  gaps (#51).
- The far serve is **geometrically invisible to `ActionClassifier`**, not
  merely untracked: with the ball tracked on 31/31 frames its four contact tests
  reach none of their thresholds (no lowest vertex; 0 px horizontal flip vs the
  20 px redirect gate; dvy +4 vs <= -8; dvx 2 vs >= 12; the serve branch's fed
  ascent +0..+4 px vs the +10 px margin — the far toss decays like gravity).
  All four thresholds are near-half-scale px constants and the far ball's image
  motion is DEPTH-dominated (growing + descending toward the lens). Any far-serve
  fix must therefore add a depth cue (apparent-size growth = the G4
  `far_flight` event) or make the geometry scale-relative (#51).
- Scale-aware contact geometry is **refuted for the far serve**, and the
  arithmetic says why: where the ball is tracked, the tests would need a
  threshold of 8.2 (bounce) / 2.4 (redirect) BALL WIDTHS vs near-side
  equivalents of 4.5 / 1.3, and the tests reachable at k~0 are reachable only
  because they stop discriminating (any downward velocity change, any gravity
  arc, any lob apex). The far deficit is shape/sign (depth-dominated motion)
  plus ball absence, never threshold size — do not re-attempt it as a k sweep
  (#52, `docs/g4_scale_aware_geometry.md`).
- **A probe that builds its config from `Config.default()` alone runs the COCO
  `yolov8n.pt` ball detector, not the fine-tuned model** `src/main.py`
  auto-loads — it under-reports the ball legs badly (far-flight at +-15 f 4/17 ->
  8/17, conjunction 3/17 -> 6/17 once fixed). Probes now go through
  `score_serve_events.production_config()` (#51).
- Detectors can expose INERT read-only side channels for observers (person boxes
  the play-area filter dropped; pre-static-suppression ball candidates) without
  touching the returned list — the serve emitters need exactly these
  (`PlayerDetector.off_area_detections`, `BallDetector.raw_detections`) (#51).
- Recorded action F1s REQUIRE `evaluate --ignore-player`: GT player_id is
  a per-frame L-R index; with player matching on, IDENTICAL streams score
  0.933 vs 0.133. GT id conventions: e1/e3 = L-R indices, e4/e5 =
  canonical ids.
- The scorer merges GT `overrides` before matching — ratified corrections
  must be visible to eval.
- The perception stack emits COURT-SIDE letters (A=near, B=far,
  `get_team`); GT/owner teams are SQUAD letters. Comparing them directly is a
  side-vs-squad confound: G1's raw team 0.518 corrects to **0.755** once
  side→squad is mapped via the beach switch cadence
  (`scripts/resolve_side_switches.py`, S3). Score team at side level, or map
  side→squad before consuming it as squad.
- pred `player_id` = L-R index over the team-filtered snapshot set; it
  shifts when the filter set changes (harmless for spatial scoring).
- A/B baselines: generate from HEAD (git stash) BEFORE editing, never
  WHILE editing (each dump process imports at start — partially-edited
  baselines once faked a neutral A/B). Neutrality bar: 7/7 entreno action
  logs byte-identical + full match data CSVs byte-identical.
- Width-normalised departure (bw/f) conflates dead balls with far float
  serves: R1's dev-fitted gap (FPs ≤0.287, correct ≥0.383) was empty on
  dev+e1-e7, but the match's real far serves (e.g. P11 f7132, 0.285)
  sit inside the dev FP band — width-derived thresholds need held-out
  validation before shipping (`docs/g3_r1_departure_gate.md`).
- `action_confidence=0.3` is INERT as an emission filter: the emitted
  resolver confidence is hand-set per gesture tier with minimum 0.45
  (measured over all 85 evidence rows) — the filter never rejects
  anything. Any real confidence work must first decide whether the
  threshold is supposed to bind (and re-cut it) or stay cosmetic
  (`docs/g3_r2_confidence_calibration.md`).
- Diag scripts must mirror `src.main`'s auto-detection (a dump once ran
  the COCO yolov8n fallback → different track, different stream;
  provenance is now recorded in diag outputs).
- The match file is VFR (25.67fps content in a 30.12fps container):
  cv2 `CAP_PROP_POS_FRAMES` seeks are frame-UNRELIABLE — decode
  sequentially for frame-accurate work.
- Match serve-action emission on TRUE windows (26th session, from the
  episode→point map): near 11/16 vs far 4/16 clean (+2 side-mismatched,
  both far) — the far-side loss is the serve-ACTION/episode layer, not
  ball tracking; emitted-team mismatches concentrate on far-side windows.
- Anchor-free episode↔point alignment is COUNT+GAP constrained: with
  every confirmed rally forced into a point and attaches limited to small
  game_off gaps, most of the 20260920 mapping is forced 1:1 — treat
  surviving side-mismatch flags as findings, not alignment errors.
- Serve-loss diagnosis (26th session probe): the ball detector sees EVERY
  owner-anchored serve (conf ≥0.86) and the tracker's ≥8px/f bootstrap
  criterion is met fast — far-side serve losses are the serve-ACTION gate
  + bump-serve gesture misclassification (dig/spike labels), NOT
  detection; static suppression only bites on slow float serves
  (P15: median 2.1 px/f).
- Serve-position openers follow ≥153f of dead time; the largest mid-rally
  t1 gap on the 20260920 match is 134f — GAP_SERVE_MIN=143 splits them
  (28th session, all 33 TRUE windows measured).
- The emitted toucher team is unreliable at window-opening contacts:
  13/31 pass-2 serves needed the structural squad (ten far-side windows
  read A, P24's near-side serve read B, P23/P31 emitted-fixes) —
  downstream layers consume `pass2_team`, keep `team_emitted` as
  provenance (28th session).
- CORRECTION (#42) to the line above: on the dev clip, P1 f247 and P6 f3070
  (emitted team A) are correct-team near-side RECEPTIONS (GT digs f245/f3071,
  team A) that pass-2 relabeled as the far serve — the override hides a
  missing serve contact rather than fixing a width-band error. P8 f4801's
  team flag comes from the post-P7 side switch (stage-5 loss), a different
  mechanism. Do not attribute the 13 overrides to the width-band class
  (T8) without contact-level GT.
- Pass-2 layers must be scored at CONTACT level (`evaluate_timed.py` on
  `actions_pass2`), not by point census alone: "far prefix census 8/8" is
  0/5 at contact level on P1–P8 (relabeled contact 31–50 f late, outside ±15 f).
  Session 42.
- A pass-2 point-WINNER layer speaks SIDE letters (A near / B far,
  `CourtCalibration.get_team`), so squad scoring needs the GT/21.4 switch
  schedule (validate-only). `serve_relabel.json`'s `team_resolved` is
  winner-serves-derived GT: a winner layer must project it out (flag only) or
  its honest 18/33 becomes a GT-bought 21/33. `pipeline_output.json` carries
  no ball-death side/in-out, so kill/ace endings cannot be disambiguated from
  artifacts alone. Session 43, `docs/point_winner_layer.md`.
- Pass-2 point census vs contact reality: `relabel_serves.py`'s "far prefix
  8/8" counts owner ANCHORS, not emitted actions — 2 of the 8 P1–P8 points are
  `anchor_only` with no action within ±80 f of the GT serve, and the pass-2
  stream matches 1/8 GT serves at contact level. Score every pass-2 layer at
  contact level with the padded-region scope (below). Session 45.
- Contact-level scope trap: the point windows in
  `video_ari_joan_8_first_points_annotations.json` are NOT rally-inclusive —
  7 of the 28 owner contacts fall outside them (a serve precedes its window,
  the rally tail follows it). Score inside a region padded by
  `rally_reset_gap` (90 f) and assert parity: the perception arm must
  reproduce the T4 dev-clip baseline (P 0.586 / R 0.607 / F1 0.597) or the
  numbers are not comparable with the recorded record
  (`scripts/score_pass2_contacts.py`, session 45).
- The pass-2 relabel decisions are net-negative on gesture labels
  (−0.143 class accuracy on P1–P8) because the far-serve opener candidates
  ARE the receiver's dig in 3/5 cases; a relabel gate would need "no nearby
  reception contact", which is pass-2 bookkeeping, not perception. Session 45.
- Entreno e1–e7 are ONE recording session: a regression / byte-identity
  suite, not a match-domain validation set (held-out correct rate dev 0.276
  vs entreno 0.56–1.00; the R2 gesture tier reverses dev↔entreno). A leave-one-
  clip-out over them is one fold. Labelled contacts: 91 = 63 entreno + 28 dev
  (the "207 match actions" are PREDICTIONS, not labels). Session 42.
- Dev loss budget (28 GT contacts, T4): proposal 11 (6 candidate + 5 reach
  gate) > team/actor 5 (4 = post-P7 side switch) > label 4 > survives 8;
  detection 0. The gesture label is the SMALLEST dev bucket — but the HELD-OUT
  budget runs the other way and supersedes it: over P9–P33 (183 contacts)
  label 57 > missed 44 > team 36 > correct 46 (label 31% vs proposal 24%),
  so the label is the single largest error class on held-out data. Read the
  dev budget as clip-specific: the dev proposal gap was the outlier. Session 48.
- Held-out match contact score (P9–P33, 183 owner contacts, effective
  tolerance ±15 f): production P 0.785 / R 0.760 / F1 0.772, class 0.590,
  team 0.518; `overpass` recall **0.000** (18 contacts, 13 found all
  mislabelled dig/spike/set); serve recall 0.280. Detection F1 is HIGHER than
  the dev clip (0.597) even though labels/team are lower. Session 48,
  `docs/g3_heldout_p9_p33.md`.
- The 12 held-out FAR serves score **0/12** at the effective ±15 f tolerance:
  6/8 nearby emitted "serve"s are the pass-2 re-labelled GT RECEPTION
  (+26…+34 f), 2 are production serves 26–28 f late with the opposite team, 4
  have no serve within ±80 f. Reproduces S0b on independent contacts — the
  far serve is both a proposal and a label loss. Session 48.
- Held-out "missed" is mostly NOT an empty stream: only 3/44 missed contacts
  have no action within ±80 f; the other 41 have a nearby action 7–69 f away
  (25 a dig). Timing/placement + dense-rally matcher consumption, not absence.
  Session 48.
- Match-scoring scope: the episode-map emission windows in
  `20260920_match_contacts.json` are PREDICTIONS and only 12/25 cover their own
  owner contact range (P32 window f24614–f25085 vs contact f25375; P20 window
  f15153 vs contact f14518). The padded span still covers every P9–P33
  contact, so contact P/R/F1 is window-independent; dead-time/points metrics
  inherit the drift. Session 48.
- The overpass LABEL cannot be recovered from a ball-width net-crossing
  signal: on 18 held-out GT overpasses the width regime flips across the
  contact at only **3/18**, vs set 4/46 and dig 10/55 — no signal and no
  separation. The ball is tracked on BOTH sides at 18/18 (not detection): the
  crossing sits at the net/tape where the width regime abstains and a high lob
  reads ambiguously on both sides. The perceived next-contact team is also
  unusable as a substitute (overpass next-team flip 8/18 = 0.444 vs controls
  0.582). The resolver emits `overpass` only at touch-2-no-follow while GT
  overpasses span touch 1/2/3 (emitted dig 6 / spike 5 / set 2 / missed 5), so
  the loss is a rule/touch-geometry problem — `scripts/probe_overpass_crossing.py`,
  session 50, `docs/g3_overpass_crossing.md`.
- No implementable overpass RULE works without a reliable possession signal:
  replaying the imported `ActionContextResolver` over the diag dump's raw
  `candidate_passed_gates` contacts, every candidate is net-negative on P9–P33
  (baseline 85 correct; next-team crossing 71; no-follow net bump-set 80 with
  only 3/18 overpasses recovered; next-team + ball-side 82 with 0/18). An
  overpass override needs a trustworthy NEXT-TOUCHER team, i.e. the possession
  layer is the real enabler. Session 50.
- A BALL-FIELD possession signal cannot fix the `carry` attribution errors:
  the width-trend fallback is 11/11 precise on the strict-abstain contacts
  where it fires, but they were mostly already correct, and the remaining
  carry errors have NO ball signal at all (ball lost mid-flight) — base
  attribution 121/157 → 122/157. A motion-convergence tie-break changes only
  same-team actor picks (0 team changes). Possession needs a NON-ball signal.
  Parked default-OFF in `scripts/possession_signal_harness.py`, session 52,
  `docs/g3_possession_signal.md`.
- **`cv2.CAP_PROP_POS_FRAMES` is frame-UNRELIABLE on the 20260920 match** (VFR,
  AGENTS.md §7): measured against a full sequential decode, seeks land
  **-28..+30 frames** from the requested index (13 points, mean +8.5) — twice
  the ±15 f tolerance every contact score uses. Every windowed probe that seeks
  is measuring shifted frames, and the G4 serve-event score was one of them
  (recorded 6/17, actually 11/17 with -9 f offsets). Decode SEQUENTIALLY and
  index what you decoded; `tests/test_vfr_seek_guard.py` enforces it and its
  allow-list records the two sites that still seek (the owner-GT annotator and
  the UI thumbnail crops), session 53, `docs/g4_far_serve_alignment.md`.
- **A far ball's "0-1 tracked frames" is a TRACKER count, not a detector
  count.** The fine-tuned detector sees a 15-21 px far ball in **14-31 of 31
  frames** at every GT far serve except P31 f24543 (2/31). So the far serve is
  not a detection problem: the tracker will not lock the ball and the px-space
  contact tests refuse it, and a 4x-magnified far-end crop buys only that one
  window (+105 ms/frame). When a far-side signal "is not there", check the
  detector's `raw_detections` before blaming resolution. Session 53,
  `docs/g4_far_ball_presence.md`.
- **A serve can be recovered structurally, without the tracker and without the
  shape tests**: no emitted contact for 60-240 f (the match separates openers
  ≥153 f from mid-rally gaps ≤134 f, so the gate plateau is structural, not
  fitted) + a person in the far band + a far-side ball-sized raw detection
  within reach in bbox heights. 11/17 at precision 1.00, 15/17 at 0.94, 17/17
  at 0.90, union of the two zero-FP rules **14/17 with no false positive**,
  median |offset| 1 f — against production's 0/17. The residual errors are
  pre-serve ball handlings, which no dead-time test can separate from a serve;
  only the toss does, and the toss is what the far-end geometry refuses. So this
  belongs in the post-hoc evidence layer, never in the label stream. Session 53,
  `docs/g4_structural_serve.md`, `scripts/sweep_structural_serve.py`.
- **Bind pass-2 evidence by DEAD-TIME EPISODE, not by the episode map's point
  window.** The windows are PREDICTIONS (only 12/25 cover their own owner
  contact range), so a serve can sit outside its own window -- 4 of the 17 owner
  far serves do, and binding by window cost the consumer 4 of its 8 misses. The
  EMITTED CONTACTS are not predictions and already partition the video into
  episodes: a serve lives in one, opens it, and is followed by that episode's
  first contact. Session 54, `docs/g4_serve_evidence.md`.
- **Report evidence coverage and consumer binding as two numbers.** The far-serve
  evidence covers 14/17 GT far serves (anchored on the contact) but the shipped
  consumer binds 9/17 (dev 5/5, held-out 4/12) — the same shape as G1's
  "41/44 missed contacts have an action within 80 f". Quoting only the anchored
  number would be the mistake the G1 exercise exists to prevent.
- **A far serve and its own post-contact ECHO straddle the contact**: the echo is
  the ball still inside the server's bbox a few frames after the hit, and it
  sits 1-19 f before the rally's first action. A one-sided dead-time rule cannot
  separate them; the NET CROSSING can, because a served ball crosses the
  calibrated net line toward the camera (578 `far_flight` events already carry
  the evidence, and it is a post-hoc computation, no re-decode). Session 54.
- Device caveat: MPS jitter can flip a gesture label (e.g. e6 f309
  block vs spike); the script path (deterministic) is the reference.

**GT conventions (owner-ratified)**
- The contacts dictation has TWO dialects (P1–P8 parsed; P9–P33 added 09-30 and
  NOT yet parsed) — shapes and owner conventions in `ground_truth/README.md`.
  Measure parser coverage before building on a GT file.
- `ground_truth/gt_point_start_end.txt` is the game-state VIDEO's GT —
  NOT match serve anchors (mispairing once produced fictional windows).
- Match serve team = winner-of-previous (mechanical, 6/6 cross-checked);
  sides: A near at start, switches after points 7/14/21/28. P1's server
  unknown.
- GT touch_number counts per-TEAM possession — any cross restarts the
  receiver at t1 (proven by e4 f329 / e5 f300 GT spike t1).
- No-touch blocks are physical GT events the pipeline cannot emit (no
  eval penalty mechanism).
- Kill = direct fall OR dug-and-dies-without-a-set.
- `ground_truth/20260920_match_ari_joan_contacts_p1_p8.txt` (owner dictation
  2026-09-29, session #33): contact-level GT for match points 1–8 with the
  PLAYER TRACK ID + side at each contact. Player id = the id the track had AT
  THE CONTACT FRAME (ids drift across occlusions/off-screen by design) — never
  treat cross-point id drift as a GT contradiction. All 8 winners agree with
  the point-level GT; P7 wording conflict (accelerated spike vs "poke spike").
  Not yet wired to any script.
- GT edits only via owner-ratified contact sheets; GT was dictated against
  base-model behavior — when a new model shifts streams, RE-ADJUDICATE
  before calling regressions (the v3 e4/e5 lesson: same failure modes on
  both retrains = systematic, not noise).

**Detector / tracker facts**
- Raw detector confidence is background-dependent (was: sky med 0.90 /
  sand 0.20) and raw precision on this venue is LOW — the tracker's
  motion/geometric gates carry production. Read probe "candidates" as
  mostly sand noise (pre-label audit: even ≥0.4 sky picks were 3/77 on
  the owner's ball). v3 fixed the conf skew; conf dips remain on
  fast-falling balls (22 family).
- Ball pixel width: ~14-28 far / ~30-55 near, abstain 26-35 — the
  validated side signal. Image-plane ball side is UNUSABLE (airborne
  near-half balls project "far").
- The gesture path's px `near_net` (NEAR_NET_PX=120) is load-bearing;
  px→metres is GT-refuted (see point 4). Near-net attribution exemption
  is 2.5 m in ground metres.
- A "detection gap" is often tracker admission/gating, not recall — probe
  raw detector output before calling recall (entreno lessons 1c/serve-zone).
- The loss waterfall (T4, dev clip) makes that concrete for serves: at all 5
  lost serves the detector fires (conf 0.74–0.87, `removed=false`) while the
  tracker reports `unlocked_no_motion` on 19–25 of the 31 window frames — a
  toss apex slower than `lock_min_speed = 8 px/f` cannot (re-)lock. Serve loss
  is a BALL-TRACK ADMISSION class, not detection and not the serve-action gate
  STATUS open point 22 measured on the match.
- T5 step 1 (#37) measured WHY: all 5 lost dev-clip serves are FAR-side serves
  and all 3 surviving ones are NEAR-side. A far-side toss is a 13-17 px ball
  creeping 1.6-6.7 px/f (near-side: 46-53 px, 7-17 px/f), so `lock_min_speed =
  8 px/f` - a constant measured on near-side balls - is above what a far-side
  toss can ever produce; the far ball also has 0 detections AT the contact
  frame, so no threshold can lock there (earliest lock = first post-contact
  sighting, latency +2..+4f). A 3 px/f weak tier recovers 5/5 at latency 0 for
  ~12 extra bootstrap locks / 4968 frames, and NO candidate-geometry
  discriminator removes those locks (sustained sightings, low `persist`, player
  proximity) while ascending-only LOSES 2 serves - serve-vs-spare separation
  needs context, not geometry.
- An UNLOCKED tracker replays exactly from a `--diag-dump`: the only decision
  is `_try_lock`, and the dumped `locked` flag resyncs it (4966/4968 frames
  identical on the dev clip). Counterfactuals ("what if `lock_min_speed` were
  3") are therefore measurable per frame WITHOUT re-running the pipeline -
  `scripts/probe_serve_admission.py` is the reference harness.

**Video domain (owner-stated 2026-09-30 — see also AGENTS.md §7)**
- The camera DROPS fps on its own under low light / high temperature: the
  20260920 match is 25.67 avg fps in a 30.12 VFR container, the 2026-09-28
  practice video ~30.1. Variable fps is hardware, not a capture error — never
  ask the owner to change it; handle it in the timebase (PTS) and remember that
  frame-based windows then stand for different wall time (the deferral in point
  19a is now explained rather than mysterious).
- The match is natively **1280x720** and is upscaled once to `_up1080`; every
  other clip is native 1080p. `video_david` is a different camera (portrait
  1564x2978, ~59.8 fps) and is out of spec — never validate on it.
- Camera height changes between videos (tripod re-set; much higher at the
  practice venue). The court's projected DEPTH differs by 2.3x (beach 206 px vs
  practice 464-479 px in a 1920x1080 frame), so **px-space constants are
  venue-coupled** — a threshold validated on the beach is not a threshold on the
  practice venue, and any venue-general number should be expressed relative to
  the per-video calibration.
- Owner GT: a `player id` in the contacts file is the track id AT that contact
  frame (optional, absent when "player not tracked"); `missatr` marks are
  **NOT exhaustive**; a no-touch block is attributed to the spiking player; any
  contact the owner calls an overpass is GT `overpass`.
- A GT file landing is not a GT file *readable*: the 20260920 contacts file
  gained ~200 owner lines in a second dialect and the existing parser still
  reads 0 of them. Always MEASURE how many lines/points a parser actually
  extracts before planning work on top of it (session 46).

**Perf**
- Pose gating SHIPPED in the shared classifier (staleness 30f + near-ball
  300px last-9f trail radius; occlusion window poses everyone): match
  84.8→68.0 ms/f (×1.24), byte-identical everywhere. Detector floor
  ≈ 48 ms/f (two YOLO imgsz-1280 calls). Remaining lever: point 23.
- `cv2.setRNGSeed(0)` per PlayerTracker instance in multi-tracker A/B
  harnesses (`cv2.kmeans` consumes the process RNG).

**Retraining (ball detector)**
- Four-leg gate, one lever at a time: GT-frames eval → entreno drift-lock
  (all 7 F1s exact, `--ignore-player`) → full match + evaluate_match_points
  → bg-stratified probe on the 5 episodes.
- Fine-tune FROM production best.pt, not base yolov8n (the BASE_MODEL
  switch preserved the sky prior — round-1's crown jewel).
- Mine with NO pre-labels: wrong labels are worse than none (sky
  pre-labels were 3/77 correct); noise frames are negatives by
  construction.

**Harness config (pi)**
- pi has TWO config scopes only: `$PI_CODING_AGENT_DIR` (per-harness user
  dir) and the project dir `<cwd>/.pi` (path is HARDCODED — no env
  override). Project settings OVERRIDE agent-dir settings, and there is
  no per-provider project scope. So model/provider defaults MUST live in
  each harness's agent-dir `settings.json`; `.pi/settings.json` stays
  provider-agnostic (shared prompts/extensions only). zai harness =
  `~/.pi/agent`, openrouter harness = `~/.pi-openroute` (note the
  spelling) — both read this repo's shared `.pi/`.
- Three-tier agent setup (2026-09-29): tier-1 COORDINATOR
  (`.pi/prompts/coordinator-prompt.md`, cheap model, routine sessions) →
  tier-1 WORKER delegated as a pi **subagent** (`subagent({agent: "worker",
  ...})` from the `pi-subagents` package in the zai agent-dir; GLM 5.3 /
  5.3 flash) → tier-2 ARCHITECT (`.pi/prompts/architect.md`, frontier,
  stateless, escalation-only, advisory decision memo). `scripts/run_task.sh`
  (`pi -p`) is now only the FALLBACK delegation path. Fresh sessions expose
  just `subagents_enable` — the coordinator prompt authorizes delegation so
  the full `subagent` schema activates on the next model request. The
  coordinator prompt's token-discipline section was REPLACED by the cheap-tier
  safeguards: the worker self-reports the 6-point checklist in its log, a
  host-run `acceptance`/`gate` verifies the objective part, and the coordinator
  verifies each remaining claim against `git diff` slices (claims are
  unverified inputs). Tier-2 triggers: mechanism design, ambiguous/refuted
  A/B, protocol changes, conflicting evidence, owner-gate mechanism
  approval — never mechanical fixes, evidence gathering, or refutation
  cleanups.
- Subagent runs default to ASYNC/background with a 30-min `timeoutMs` default;
  a dev-clip pipeline run exceeds it, so raise `timeoutMs` AND `toolTimeoutMs`
  and collect with `bg_wait`. `pi-subagents` docs: `models.md` (per-run
  `provider/id:thinking` override; the `thinking` field is ignored on
  dispatch), `tool-reference.md` (params, `acceptance`/`gate`), `agents.md`
  (builtin agents; project agents live in `.pi/agents/`).

- Every video, including the 20260920 match, carries a real AAC 48 kHz stereo audio track (match mean −35 dB / max −4.6 dB). The pipeline never reads it; `src/utils/video_upscale.py` only stream-copies it. Contact sounds are a geometry-independent signal that has never been tried (session 55, `docs/serve_reliability_plan.md`).
- The production serve baseline at contact level (±15 f, match P1-P33) is near **8/16**, far **0/17**, with 12 FP emissions. `scripts/score_heldout_contacts.py` counts `action OR pass2_action == serve`, so its near 11/13 is not the production number (production is 7/13). Session 55.
- The #53 structural serve operating point (14/17, 0 FP) was chosen by a sweep over ALL 17 match far serves, so it is in-sample. The out-of-sample signal is the consumer's held-out binding of 4/12. Never tune serve rules again on those same 17 serves (session 55).
- **One scorer for every serve number** (`scripts/score_serves.py`, session 56): greedy one-to-one, nearest first, inside each owner contact's own `frame_tolerance`, side-correct by default with the positional match reported beside it. Side-correct matching makes side accuracy TAUTOLOGICAL (always 1.00), so side accuracy must be scored on the positional match; a squad call is only comparable through the switch parity, and the court words `near`/`far` must be mapped to the stack's side letters `A`/`B` before `resolve_side_switches.side_to_squad` will accept them.
- **A stream that proposes is not a stream that claims.** Scoring the raw far-side evidence records as "74 false serves" and the rally onset as "precision 1.000" were both one line away from being reported; `proposes_serve: false` makes the scorer print no precision at all. Same for the point dimension: a record that lands on the serve but was bound to the WRONG point is a binding miss, which is the whole 13-vs-9 gap between coverage and binding (session 56).
- **The far-serve TIME is nearly free and the near-side TIME is not.** The `game_on` backdated burst start lands within ±15 f of **11/17** far serves at median |offset| **3 f**, vs **3/16** near at 14 f (all late); at ±120 f it covers 27/33. A far serve IS the rally onset, so SR4 needs a side decision on a known time far side and a real proposer near side (session 56).
- **The near serves production emits are all within ±2 f of the owner frame** (8/8, median 1 f), so the 8 missing near match serves are missing EMISSIONS (proposal / label / gate), not late ones — SR1 should look at the emit path, not at timing (session 56).
- **The shipped far-serve evidence covers 13/17 far serves, not 14.** 14 records land within ±15 f of a serve of any side, but the 14th is on a NEAR serve (P12 f7777, record f7762); 14/17 was a sweep figure on the recording, and the consumer's precision as a claim is 0.47 (19 bound records, 9 on their own serve) — the zero-FP claim was measured against mid-rally controls and owner FALSE/OFFGAME moments, which is a different and still true number (session 56).
- **A pipeline artifact in `output/` can be silently stale.** The seven `output/video_entreno_*/pipeline_output.json` files date from 2026-09-04/06 (commits `239490c`/`8150694`), i.e. before the v3 ball detector (09-26) and the pose gates (09-27); they read as 3/5 serves where the plan quotes 4/5 from a run whose artifacts are gone. `score_serves.py` prints each stream's `processed_at` + commit and now prefers a fresh run, for exactly this reason (sessions 56-57). On fresh runs the practice serves are **3/5** (e3 +0, e6 +1, e7 +0; e2 f32 and e5 f20 missed) — the same count as the stale artifacts but a DIFFERENT set of hits, so the coincidence is not evidence the old numbers were right.
- **[#58 CORRECTED — see the SR1b lines below; 4 of the 5 `behind_baseline` verdicts here were INFERRED, and the cause is the contact-frame foot, not the gesture]** **The near-side serve loss is the LABEL, and one condition of it.** `ActionContextResolver._decide` emits SERVE only when `behind_baseline AND rally_start`; otherwise a bump gesture becomes DIG and an attack gesture SPIKE. Across 10 missed near serves (match 8 + practice 2), 5 fail on `behind_baseline` with `rally_start` certainly true (gaps of 204-478 f) — the contact is detected, attributed and opens the rally, it is simply not judged behind the baseline, and e2's diag dump measures `behind_baseline: false` on that exact contact. The 6th (P33) is a **cascade**: our own serve emitted 25 f early suppresses `rally_start` 16 f later, so the real serve is read as a dig (session 57).
- **[#58 ANSWERED: the server's track is COASTING under the 90 f hold horizon, see below]** **A serve contact can die at the REACH GATE with the server nowhere near the contact point.** P5 f2575 (candidate rejected: ball-to-box 448.3 px vs reach 140) and P7 f3747 (204.0 vs 140): the ball is tracked, the geometry fires, and all four tracked boxes are elsewhere on court — the same reach-gate family as open point 7, now measured for the serve. The dump carries only TRACKED players, so "detected but untracked" needs one pass with `--serve-events` to answer; tracker admission is a refuted lever (T5) and must not be assumed (session 57).
- **"No diagnostic records in the window" is NOT "no detection in the window".** A prefix diag dump covers a span and the T4 waterfall reports both as stage 1; scoring match rows past the prefix produced six phantom `1_raw_detection` stages before `diag_stage` learned to check the dump's coverage (session 57).
- **A SEQUENTIAL prefix pass is production-faithful when it reproduces the shipped actions**: match [0,4000] on MPS reproduced 23/23 `(frame, action, team)` triples of the committed artifact, which is the gate that makes its diag dump usable (session 57).

- **`behind_baseline` is read on the CONTACT-frame foot, which is airborne/landing at a serve** (#58, `docs/sr1b_near_serve_causes.md`). Match P9-P12: toucher foot 736.5-760.2 vs the 761 px threshold (team A, `max(near corner y) - 30`), past it 7 f later; near hits sit at 809-835. Same physics as SpikeAnalyzer's takeoff-stance fix for `attack_zone`.
- **`player_off_court_hold_frames = 90` loses the near server during match dead time** (#58). P5/P7: the server's track goes `predicted` exactly 91 f after its last in-court sighting and coasts frozen (0.0/0.3 px) through the serve; dwell behind the baseline was 174/120 f. The horizon's "real players max out at 46f (e6)" comes from 1-point drill clips; match servers wait 120-324 f. Lifting it (config) turned P7 into a hit on [0,8000] with one non-GT label change.
- **Dead-time handlings cost serve RECALL, not only precision** (#58): a pre-serve handling contact emitted <90 f before the serve kills `rally_start` (P5 under the counterfactual at 78 f; P33 at 16 f).
- **`NEAR_NET_PX = 120` is venue-coupled**: the beach match near half is ~147 px deep, so `near_net` is true over ~80% of it, including the P9-P12 serve contacts (#58).
- **"The ball was tracked" is not "the player was tracked"**: SR1's "not a tracking problem" checked the ball only. Check the attributed player's track (`predicted`, foot, track id) in the diag dump before calling a miss a label problem (#58).
- **A cause in a headline must be MEASURED.** If a verdict is reached by elimination (e.g. from `_decide`'s logic), write "inferred" next to it; SR1's `behind_baseline_measured: null` rows were reported as the mechanism and a review session was needed to measure it (#58).
- **A debugging HUD is a mirror, not a second classifier** (#59). The live-debug side panel is only trustworthy because every number in it is read out of a value the frame already produced — the width-side verdict from the classifier's own `_width_side`, `CONTACT_REACH`/`NEAR_NET_PX` from its class constants, the ball width at a contact from its `_ball_history`, the probe from its own `_diag` records (the same sink `--diag-dump` uses, skipped when a `DiagRecorder` owns them). Duplicating a threshold in the panel is how a HUD starts lying. Corollary: an event anchored on its TRUE contact frame only exists because the live render is ~3 s behind the producer — a panel cannot show, on a frame, something the pipeline had not yet decided at that frame.
- **A HUD that blanks a signal when its producer drops it is useless exactly when it matters** (#59). The ball tracker returns None for ~12% of the frames in a 240-frame entreno window, and the panel's BALL block used to disappear with it. Holding the LAST sighting (pos / size / width-side read / speed / conf) answers the real question ("what was the last thing the pipeline saw, and how long ago?") instead of showing nothing — and the flag belongs ON the section header, not on an extra row, so the block keeps its layout and the eye does not have to re-find it. Same rule for any observer: hold the value, flag its age on the header, never silently substitute a blank (#59).
- **A fix that recovers exactly what it was designed to recover can still be worth nothing** (#61). Lifting the off-court hold emitted P7's serve at its exact ground-truth frame (delta +0) and moved near recall 0 frames — P18 relabelled `serve`→`dig` at the same frame and two false serves appeared, for 8/16 either way. Always report the per-point SET of recovered/lost points, never the aggregate, and price the `rally_start` coupling (#58: a handling <90 f early kills the rally opening) as part of the cost of a longer hold. Corollary on the e2 premise: the bystander is fed on 400 of 423 frames at the 90 f horizon TODAY, so "the horizon kills the bystander" is no longer a measured fact — check it before designing an exemption around it.
- **Lifting the 90 f off-court hold changes track IDENTITY across the whole match** (#62). Its cost surfaces as attribution swaps at contacts the change never touched (P18: same ball point, same touch number, new rally, toucher track 3→2 so a serve reads `dig`; the lift also renumbers tracks match-wide, f2494 track 1→4), so a hold exemption's price is only measurable on a full-match run. Corollary: before designing an exemption, ask what it does to IDs anywhere it fires, not only at the serve.
- **A player box with no detector behind it can read "behind the line" and do no harm, and a backward-looking fix for it costs as much as it gains** (#60). Fifteen match contacts had `behind_baseline` read off a carried-forward or absent track; the owner confirmed only 2 are serves and the other 13 were vetoed by the serve label's second condition (they did not open a rally). The 2 real serves DEPEND on that read — their player has no real detection at or before the hit (it returns 1-7 f LATER) — so a rule that looks backwards for a cleaner position trades +P11/+P12 for −P17/−P19; P9/P10 read false at K = 5, 10 and 15 (stance feet y = 750/747 vs the 761 px line). Corollary for any reproduction gate: a diag dump's per-frame player list is NOT the classifier's snapshot (a contact is confirmed 7 f late and the last REAL position is used), so a probe cannot reproduce the shipped read on the ~6% of contacts whose toucher is coasting.

## Session index (one line each)
- #62 D4 DECIDED (architect, on `docs/d4_gate_brief.md`; nothing built, `src/` untouched): M-a stays CLOSED and **M-b is PARKED** — the serve-zone exemption's ceiling is +1 near serve of 16 (+2 with P5) against a 0.90 bar needing 15, and the blunt version measured net 0 (+P7 / −P18, false serves 12→14). **#62 re-reads P18: an attribution swap, not a rally_start failure** (same ball point 867.5,313 in both arms, touch 1, new rally, toucher track 3→2 = server→partner; the lift renumbers tracks match-wide, f2494 track 1→4), so a hold exemption's cost is only bounded by a full-match run. Next: card **SR4a** (near-opening table, no decode), then SR4, then the held-out run once, then SR5 → SR6. Also: the stale `player_off_court_hold_frames` comment at `src/utils/config.py:101` is now on the deferred list (comment-only, inside the next session that touches `src/` anyway).
- #61 SR1d DONE — `global lift REFUTED` (`docs/sr1d_hold_horizon_cost.md`, no `src/` change): the 90 f off-court hold lifted to 100000 changes the 7 practice clips not at all (action streams byte-identical, ΔF1 0.000) but feeds e2's sideline bystander 423 f vs 400 f, and on the full match leaves near serves at 8/16 while the composition churns (+P7 at delta +0, −P18 as `serve`→`dig` at the same frame), FP 12→14, actions 207→212. So M-b must be geometric, not a bigger horizon. One card step needed an owner-sanctioned fix (the `evaluate.py` invocation graded nothing); adapter validated against the recorded per-clip F1s.
- #60 SR1c CLOSED (stopped at its own reproduction gate — 194/207 match, 6/7 and 13/14 practice, vs ≥98% — nothing shipped; owner "leave as is"): all 15 disagreements are contacts whose toucher had no fresh detection at the hit (box carried forward or absent from the tracked list), while the pipeline read their last real position up to 7 frames later. The owner checked the rendered frames: 13 of the 15 are not serves (the existing rally-opening condition already vetoed them) and the 2 real ones are exactly those a backward-looking stance read would lose. New probe + 22 tests (`scripts/probe_takeoff_stance.py`, `tests/test_takeoff_stance.py`), write-up `docs/sr1c_takeoff_stance.md`. Suite 1156 (1134 at HEAD + the 22 new; an earlier count in this session read 1113 against the pre-#59 tree — see the Log).
- #59 live-debug HUD: the frame counter gets a solid black plate and +1 px, and a new display-only side panel (`src/analysis/debug_panel.py`, `p` toggles) shows the per-frame signals (ball px size + the classifier's own width-side read, staleness, player team/near-net/ball distance vs `CONTACT_REACH`, game badge, the contact probe with the refusing gate, the held-back look-ahead contact) and an event log keyed on each action's TRUE contact frame with the signals that produced it. Follow-up in the same session: panel text +3 px (scale 0.55, strip 600 px) and a **held ball readout** — a dropped track keeps the last pos/size/width with its age instead of blanking the block. Processing path untouched (producer sequence pinned), saved video unpanelled; verified on two real live runs of `video_entreno_3.mp4`; suite 1155.
- #58 SR1b review: SR0/SR1 checked by a worker pass over match [0,15000] (parity 111/111) + a hold-off counterfactual; the near serve has three measured causes (contact-frame foot P9-P12, 90 f off-court hold P5/P7, e2 server untracked), SR2 demoted, vall_dhebron serve GT committed under a held-out lock, task cards SR1c/SR1d/D4 + `/next-task` prompt + `task-card` skill added (`docs/sr1b_near_serve_causes.md`).
- #57 SR1 DONE: the near-serve miss taxonomy (`scripts/probe_near_serve_misses.py` + `docs/sr1_near_serve_misses.md`, +21 tests; fresh production runs of all 7 entreno clips + a parity-checked match prefix dump): 10 misses = 6 `label` (5 = `behind_baseline` false at a rally-opening contact, 1 = `rally_start` cascade from our own early serve) / 3 `no_contact` (P5/P7 reach gate, e5 no ball sighting) / 1 `other_side_contact`. Near recall 11/21; practice 3/5, not 4/5.
- #56 SR0 DONE: one serve scorer for every stream and side (`scripts/score_serves.py` + `docs/sr0_serve_scorer.md`, +33 tests, gate PASS): baseline reproduced (near 8/16, far 0/17, 12 FP), the record corrected (13/17 far covered not 14; evidence precision 0.47 not 1.00), and three SR4-steering findings (rally onset times 11/17 far at |offset| 3 f; near hits all within ±2 f so the misses are missing emissions; 8 of 12 FPs are dead-time handlings). Entreno artifacts found stale.
- #55 planning only: serve-reliability plan SR0-SR7 (`docs/serve_reliability_plan.md`, open point 30). Honest baseline near 8/16 / far 0/17 / 12 FP. The far-serve track is declared a proxy fit on one match. Audio and beach-rule decoding are proposed. STATUS lean-trimmed (header chain, Where we are, Log #50-#52 archived verbatim).
- #54 S4 DONE: the serve evidence is a real artifact (`output/serve_evidence.json`, 87 records, precision 0.90, inertness measured) — anchored coverage 14/17 vs consumer binding 9/17, both reported — `docs/g4_serve_evidence.md`.
- #53 the far serve SOLVED as evidence: 14/17 GT far serves at ZERO false positives (production 0/17) via the opener gate + a structural proposer over raw detections; M1 (magnified far-end crop) REFUTED and it corrects the detector-vs-tracker record; the VFR seek defect found and guarded — `docs/g4_structural_serve.md`.
- #51 G4 serve-evidence events (far flight + runway + conjunction): default-off observers in `process_frame`, scored 3/17 GT far serves at +-15 f vs production 0/12 — `docs/g4_serve_events.md` (numbers superseded by #53's seek-free re-score: 11/17).
Details: `docs/history/status_where_we_are_archive.md` (per-session state
summaries) + `docs/history/status_log_archive.md` (detailed entries,
2026-08-14 → 2026-09-26). The last ~3 sessions keep full Log entries below.

- 2026-10-01 **#52** — possession signal built + REFUTED + parked (no `src/` change, no decode): `scripts/possession_signal_harness.py` (default OFF) + `scripts/probe_possession_signal.py` + `docs/g3_possession_signal.md`; ball-field width trend + motion-convergence tie-break both implemented and unit-tested (20 tests), then replayed through the REAL attribution methods on the match dump: base **121/157 (0.771)** → both **122/157 (0.777)**, trend fires 11× / **11/11 correct side** but redundant, motion **0** team changes; the carry errors have no ball signal (ball lost). Parked per T5/R1. ALSO: a concurrent pi session (G4/#51) collided with the validation stash — never run two sessions on this repo at once. Suite 985.
- 2026-10-01 **#50** — G3 overpass crossed diagnosis REFUTED (diagnose only, no `src/` change, no decode): `scripts/probe_overpass_crossing.py` (+23 tests) + `docs/g3_overpass_crossing.md`, artifacts `output/g3_overpass/`; the ball-width net-crossing across the contact is present at only **3/18** held-out GT overpasses vs non-attack controls (set 4/46, dig 10/55) — K1+K2 fire; tracked both sides 18/18 (K3 clean, not detection — crossing is at the net/tape where width abstains); perceived next-team unusable (overpass flip 8/18 = 0.444 vs controls 0.582, K4 fires); emitted dig 6 / spike 5 / set 2 / missed 5; loss is a LABEL/RULE problem (resolver emits overpass only at touch-2-no-follow, GT spans touch 1/2/3); the three implementable rules replayed through the imported resolver are ALL net-negative (baseline 85 → 71/80/82), so no `src/` change ships; suite 920.
- 2026-10-01 **#49** — S3 DONE: pass-2 side-switch/squad layer — `scripts/resolve_side_switches.py` (+25 tests) + `docs/g3_side_switch_layer.md`, no `src/` change, no decode; beach cadence from the point order alone → `[7,14,21,28]` EXACT vs the owner schedule; side→squad by parity → `actions_pass2.pass2_squad` (207/207); **G1 raw team 0.518 is a side-vs-squad confound — same 139 found contacts score 0.755 squad-mapped, 34 genuine side errors**; player-crossing cross-check evidence-only (3/4 switches supported but 16/28 non-switch boundaries too — ids hop); suite 897.
- 2026-10-01 **#48** — G1 DONE: the first HELD-OUT contact score — `scripts/score_heldout_contacts.py` (+20 tests) + `docs/g3_heldout_p9_p33.md`, no `src/` change; P9–P33 (183 owner contacts, region f5240–f26147, effective ±15 f) production **P 0.785 / R 0.760 / F1 0.772**, class 0.590, team 0.518; pass-2 F1 0.774 / class 0.561 / team 0.561; miss taxonomy 46 correct / **57 wrong-label** / 36 wrong-team / 44 missed ⇒ the label bucket is the largest held-out loss (not proposal); `overpass` recall 0.000; far serves **0/12** (6/8 nearby "serves" = pass-2 re-labelled reception +26…+34 f); stage waterfall not reproduced (only match diag dump is R1 bw=0.3), flagged; suite 872.
- 2026-10-01 **#47** — G0 DONE: the whole-match contact GT (P1–P33) is machine-readable — dialect-B `parse_contact_gt` + `scripts/build_match_contact_gt.py` → `ground_truth/20260920_match_contacts.json` (33 points, **211 owner contacts**: 28 P1–P8 + 183 P9–P33, match-frame axis, all `source=owner_gt`) + 33 contact sheets; P1–P8 rebuild field-identical (only physical `raw_line_no` +3); fixed side→squad mapping to switch PARITY (P29–P33 `near`=Team A again; old last-switch formula mislabelled P15–P21/P29–P33); P30 f23545 unlabelled touch kept `action=null` + `owner_action_unspecified`; no `src/` change; suite 852.
- 2026-09-30 **#46** — RECORD-ONLY session: owner dictated the **whole 20260920 match contact GT (P1–P33)** in a second dialect (0 of ~196 new lines parse yet; G0 queued) and delivered a new calibrated practice video `20290928_entreno_vall_dhebron.mp4` (1080p, 695 s, ~30.1 fps); camera domain pinned in AGENTS.md §7 (long axis always, fps drops by itself in heat/low light, height varies per video); 3 new open points (25 dig-vs-ball-death, 26 duplicate actor attribution, 29 stale recording docs) + point 5 extended with the owner's "past + ball field" attribution spec; suite 840.
- 2026-09-30 **#45** — G3 plan S0b: pass-2 stream scored at CONTACT level on the owner P1–P8 GT (`scripts/score_pass2_contacts.py` + 28 tests + `docs/g3_s0b_pass2_contact_score.md`; no `src/` change, no decode): padded-region scope validated by exact T4 parity; far serves **0/5** (deltas 5.4–8.6× tolerance), GT serves matched 1/8, pass-2 F1 0.597→0.604 but class 0.706→**0.562**; "park at pass-2" closed; suite 839.
- 2026-09-30 **#44** — G3 plan S1 far-side serve looming probe (diagnose only, no `src/` change, suite 811): `scripts/probe_far_serve_looming.py` + 29 tests + `docs/g3_far_serve_looming.md`; post-contact tracked loom `L` = OLS slope ln(width) vs s over 0.5 s from the new-rally far-band onset; **REFUTED at kill 2** (lowest far-serve L 0.338 < highest new-rally non-serve L 0.945, no empty gap), kill 1 passed at 4/5 (flight detected), kill 3 vacuous, kill 4 pending S0; match replay parity 0/26068; the far-serve CONTACT stays open, S2 not triggered.
- 2026-09-30 **#43** — open point 21.3 point winner/outcome layer SHIPPED as a pass-2 script (`scripts/resolve_point_winners.py` + 27 tests + `docs/point_winner_layer.md`; no `src/` change, no decode): fault prior over the terminal touch, 33/33 decided, **18/33 (54.5%)** vs the 33 dictated winners after the validate-only side→squad mapping; GT-serve-override inheritance (21/33) explicitly not shipped; fixed 3 test-side defects left by an unreviewed draft; suite 782.
- 2026-09-30 **#42** — architect strategy review of the "detector v4 → normalise → learned gestures" proposal (docs-only, no `src/` change, suite 755): order NOT adopted; pass-2 far serves are 0/5 at contact level (census 8/8 was point-level); plan S0–S4 (owner P9–P33 contact GT → far-serve looming probe → side-switch layer → winner/fantasy), deferrals with triggers; proposed AGENTS.md wording pending ratification; #39 Log entry archived (Log below).

- `evaluate_timed.py`'s contact F1 is CLASS-AGNOSTIC and its tolerance is a
  TIME, not a frame count: at `evaluate.py`'s effective ±15f window (0.5 s @
  30 fps) the two reproduce the same 7/7 entreno F1s; at 0.2 s only e3 changes
  (GT f69 dig / pred f76 = 0.23 s late). `evaluate.py`'s F1 is lower on e1/e2
  because it is CLASS-AWARE — a mislabelled-but-found contact scores 0 there
  and 1 in the class-agnostic contact score (read the confusion matrix for the
  label half). T3, session #35.
- No `output/` prediction exists for the dev clip
  (`video_ari_joan_8_first_points`) — T3/T4 need one run before they can
  report dev-clip numbers.
- GT `touch_number` is PER-POSSESSION, never rally-global: serve = 1, the receiving team restarts at 1 (dig 1, set 2, spike/overpass 3) and the count resets on every side change (`ground_truth/README.md`, entreno_3 JSON). T2 contact GT now emits that; `possession_touch_numbers()` in `scripts/build_dev_clip_gt.py` is the reference.
- Side→squad mapping in the owner dictation is switch PARITY, not "last switch frame": after the 4 switches of the 20260920 match `near` is Team A again from P29 (a last-switch comparison mislabels P15–P21 and P29–P33). `_side_to_team(side, switches_before)`; session 47.
- The owner's contact dictation has TWO dialects (A `Near team P3 set at f300`; B `NT dig f6166`, frame-first, bare frames, `poke` = spike touch, `bump set` = set, `bump pass` = overpass, `returns` = dig). Both parse via `parse_contact_gt`; the match GT is `ground_truth/20260920_match_contacts.json` (211 contacts P1–P33, MATCH frames, all `source=owner_gt`). Prose that merely starts with a side word (`FT is close to a dig in f10180 ...`) is NOT a contact; session 47.
- `action=null` + `owner_action_unspecified` (P30 f23545) is an intentional GT value: contact scoring is class-agnostic so it counts as a contact, class accuracy skips it — never invent the label; session 47.
- In the pipeline taxonomy a set/dig that crosses the net is `final_action=overpass` (ActionContextResolver: overpass = sent over without an attack) with the gesture kept separately — T2 GT applies this to owner wording and flags it via `owner_interpretation_flag` for owner ratification.
- Where owner-dictated CONTACTS exist they are the authoritative contact list: draft/suggested events are never appended to `events`, they move to `points[].superseded_draft_events` with the owner contact each duplicates (matched by same squad within the coarse ±15f window) so no prediction is lost.
- 2026-09-29 **#40** — G3 per-action evidence diagnosis (`scripts/action_evidence.py` + `docs/g3_action_evidence.md`, +22 tests, suite 754; no `src/` change): 85 predictions, 54 correct; hand-set confidence uncalibrated; width-normalised departure separates 6/14 FPs with a ×2.1 empty gap; R1 departure gate proposed, awaiting owner (Log below).
- The hand-set action `confidence` (0.45–0.75 gesture constants) carries NO correctness information — do not surface it as a trust score (session 40).
- Ball speeds used as gates must be normalised by apparent ball width (ball-widths/frame): px/f is camera-scale dependent and biased against far-side contacts (far ball 13–28 px). Session 40.
- Suite baseline after #39 was 732, not 736 (drift rows removed by the revert). Session 40.
- 2026-09-29 **#39** — T5 revert/cleanup (docs + tests only, no production change): reviewer ruled both mechanisms refuted (0/5 far serves) ⇒ `src/` restored exactly to `185c6f0` (`git diff 185c6f0 -- src/` empty; `ball_weak_*` / `ball_backfill_*` DEFAULT_CONFIG keys and their config-drift rows removed) and A + B moved to `scripts/serve_mechanism_harness.py` as default-off `BallTracker` / `ActionClassifier` subclasses; A/B replay reproduces `docs/t5_mechanism_ab.md` unchanged (base 36/13/0, A 37/14/19, B 37/14/0). A test now greps `src/` so a refuted mechanism cannot re-enter. Suite 736.
- 2026-09-29 **#38** — T5 step 2: A (weak tier) vs B (backfill on a fresh lock) implemented default-OFF and replayed through the REAL `BallTracker` + `ActionClassifier` (`scripts/probe_serve_mechanisms.py`; base arm reproduces the dumped production track 4968/4968 frames). **BOTH recover 0/5 far serves**; A costs 19 new bootstrap locks, B none. B does close the step-1 evidence gap (`no_ball_sighting` 23/27/20/21/21 → 16/20/19/20/18 of 31 window frames; dev waterfall detail strings only, pipeline output byte-identical) and the loss moves to `no_contact_geometry`. Root cause of the residue: the contact probe's serve branch demands a FED ascent (|vin3| ≥ |vin6|+10, e7 f25) while the far toss is a DECELERATING float; and P4/P6/P8 have no toss detection at all to restore. Shipped DEFAULT OFF, +28 tests, suite 736 — **SUPERSEDED by #39: neither mechanism is shipped; both live in the probe harness only** (Log below).
- A `--diag-dump` JSONL replays the PRODUCTION ball tracker exactly: feeding its `ball_dets` back into a real `BallTracker` (with the calibration's court bounds) reproduces `ball_track.locked` and every emitted centre on 4968/4968 dev-clip frames. Tracker/probe counterfactuals therefore need no re-implementation (`scripts/probe_serve_mechanisms.py`, session 38).
- Restoring the missing ball history is only half of a lost contact: the contact probe's own geometry can refuse it anyway. The far-side serve dies at `no_ball_sighting` (track) AND at `no_contact_geometry` (probe): a far toss is a DECELERATING float into the contact, while the probe's serve branch only accepts a FED ascent (|vin3| ≥ |vin6| + 10, the e7 f25 pattern). Session 38.
- `CONTACT_DELAY` bounds any lock-time backfill: the probe tests contact frame `c` exactly at `c + 7`, so a lock later than contact + 7 can never feed that contact (dev P2 locks at +10 f). Session 38.
- Concatenating the high-tier and low-tier bootstrap sighting windows mis-ages motion pairs (empty low-tier frames land between real high-tier ones and halve the measured speed); union them index-wise instead (`serve_mechanism_harness.merge_history`). Session 38.
- A refuted mechanism must not live in `src/`, even default-OFF behind config keys: the config surface, the ctor signature and the drift guard all carry it forever, and it invites a later "just enable it". Keep it in the probe harness as a default-off subclass; the A/B replay then reproduces byte-for-byte (`git diff <pre-mechanism> -- src/` empty). Session 39.
- The action-script record and the production path differ on e2 today: `scripts/test_action_recognition.py` measures F1 0.571 (spike at f167), `src.main` measures 0.400 (dig at f167 + 2 extra predictions). Pre-existing, not caused by session 38's change (its OFF run is byte-identical to the T4 HEAD baseline). Session 38.
- 2026-09-29 **#37** — T5 mechanism APPROVED by the owner (serve-time ball-track (re-)admission) + step 1 diagnosis ONLY (`scripts/probe_serve_admission.py` + `docs/t5_serve_admission_diagnosis.md`, no `src/` change): all 5 lost serves are far-side, the failing condition is `speed_below_lock_min_speed`, a 3 px/f weak tier recovers 5/5 at latency 0 for ~12 extra locks and no geometry gate removes them; owner RATIFIED the P6 f3131 overpass reading via a generic `OWNER_RATIFICATIONS` table in `scripts/build_dev_clip_gt.py`; +23 tests, suite 708 (Log below).
- 2026-09-29 **#36** — T4 loss waterfall SHIPPED: off-by-default `--diag-dump` capture in the shared frame path (`src/utils/diagnostics.py`) + `scripts/waterfall.py` + `scripts/compare_runs.py`; dev clip F1 0.597, 5 of 6 candidate deaths are serves lost to `unlocked_no_motion`; byte-identical on dev/e3/e1 with hooks off and on; +37 tests, suite 685 (Log below).
- 2026-09-29 **#35** — T3 time-matched evaluator SHIPPED: `scripts/evaluate_timed.py` (+23 tests, suite 648); optimal one-to-one assignment in seconds, PTS-aware time base, separate contact/class/team/actor scores + duplicates + FP-per-dead-minute + point IoU, `--autonomous` GT-input guard; entreno gate reproduces `evaluate.py`'s F1s at the same tolerance window.
- 2026-09-29 **#34** — T2 contact-GT code review fixed (3 defects: rally-global → per-possession `touch_number`, draft/suggested duplicates moved to `superseded_draft_events` (15 of them, `events` == the 28 owner contacts), cross-net set → `overpass` + `owner_interpretation_flag`); +9 tests, suite 625.
- 2026-09-29 **#33** — T2 contact-level GT wired: `scripts/build_dev_clip_gt.py` parses the owner's `20260920_match_ari_joan_contacts_p1_p8.txt` (28 contacts, P1–P8, coarse ±10–15f, side-switch after P7) and emits `video_ari_joan_8_first_points_annotations.json` with status OWNER_DICTATED, per-contact `frame_tolerance: 15`, owner track id/side/note kept raw; +6 parser tests, suite 612.
- 2026-09-30 **#33** — G3 R1 departure gate validated end-to-end and REFUTED on the held-out match (P11 owner serve f7132 @ 0.285 bw/f removed; verdicts broken, 31/33→28/33, census 8/8→7/8); dev clean (P 0.586→0.739, e4→1.000); NOT shipped per owner option (a): src/ at 185c6f0, parked in scripts/ harness; suite 755. Same session: R2 calibration diagnosed and REFUTED (LOCO AUC 0.172 vs 0.551; `action_confidence=0.3` found INERT, min emitted 0.45) (Log below).
- 2026-09-29 **#32** — T2 dev-clip GT BUILT (REVIEW, not ratified): offset map (identity, residual 0.0 at start/mid/end), `scripts/build_dev_clip_gt.py` (+25 tests), DRAFT GT for P1–P8 (8 owner serve anchors + 15 flagged suggestions + missing/fault report), ratification sheets in `output/t2_contact_sheet/`; the side switch is after P7, not P3–P4.
- 2026-09-29 (38th session, archived) — T5 step 2: A/B replay of the serve-admission mechanisms through the production classes — both refuted as a recovery (0/5); blocker = the contact probe's fed-ascent serve signature + missing far-toss detections; B briefly default-OFF (reverted next session).
- 2026-09-28 **#30** — documentation-only generalization assessment and staged G1/G2 roadmap: `docs/202609-28-astra-fix-pipeline.md`; count-vs-recall, GT-assisted interpretation, and dense-feature persistence gaps verified; implementation pending approval, no runtime changes.
- 2026-09-28 **#28** — point 22 mechanism 3 SHIPPED: pass-2 serve re-labeling (`scripts/relabel_serves.py`, +29 tests); far prefix 2/8 → 8/8, serve-typed 20 → 31, all 17 owner verdicts mechanical, 13 team overrides flagged; suite 554 (Log below).
- 2026-09-28 **#27** — architecture ratified: pass-2 interpretation layer over the stream (map → serve re-label → winner → fantasy); full-video two-pass REJECTED (live parity + no perception gain); point 22 mechanism 3 reframed (Log below).
- 2026-09-27 **#26** — open point 22 mechanism 1 SHIPPED: anchor-free episode→GT-point order map (DP + BURST class, physics constraints) + far/near serve census on TRUE windows; far-side loss quantified ~2-3× near, emission-layer not tracking (Log below).
- 2026-09-27 **#25** — open point 23 SHIPPED: live-debug producer/consumer decoupling; logs + rendered frames byte-identical; 8.0 → ~12 fps; +14 tests (Log below).
- 2026-09-27 **#24** — product north-star goals set (G1 Fantasy scoring / G2 individual stats); stat-coverage audit + critical paths (archived).
- 2026-09-27 **#23** — pose gating shipped in the shared classifier (staleness + near-ball trail), byte-identical everywhere, match ×1.24 (Log below).
- 2026-09-27 **#22** — far-side serves scoped: retracted mispaired-anchor measurement; P2 specimen (ball tracked; loss = episode starvation + serve-action gate); `derive_match_serve_windows.py`.
- 2026-09-28 **#29** — pi config split per harness: model defaults moved out of `.pi/settings.json` (project settings override agent-dir; no per-provider scope) into each harness's agent dir — `~/.pi-openroute/settings.json` gets openrouter/stealth-space-bunny-alpha.
- 2026-09-27 **#21** — pi repo default model → zai/glm-5.3-flash (SUPERSEDED by #29: default now lives in `~/.pi/agent/settings.json` as zai/glm-5.3).
- 2026-09-27 **#20** — e3 v3 drift FIXED without GT edits: bridge defers only when a fireable normal vertex exists; 7/7 neutrality; match 31/33 unchanged (Log below).
- 2026-09-26 **#19** — round-2 rebalanced mining (350 frames); v3 four-leg gate → **ADOPTED as production**; far-side serve feedback → point 22.
- 2026-09-25/26 **#18** — retrain-mining staged (500 stratified frames); owner GT landed (486 frames, pre-labels mostly wrong — diagnostic correction); dataset merged + zipped (1091); v2 candidate gate → **REJECTED** (precision/sky/entreno regress).
- 2026-09-24 **#17** — match GT transcribed (33 points) + `evaluate_match_points` (baseline 14/33); bg-stratified ball probe indicts the 0.4 conf floor; conf-floor mechanism SHIPPED (actions 74→90; points flat — point layer binding).
- 2026-09-24 **#16** — calibration auto-detect fixed for cached `_up1080` files (`resolve_source_stem`).
- 2026-09-23 **#15** — first full-match run: 14/≈39 points confirmed, roster holds but identities hop; ball recall indicted (tracked 20.6%); width band validated round 2.
- 2026-09-23 **#14** — match intake: one-time sub-1080p ingest upscale (`ensure_1080`, ffmpeg Lanczos, parity-gated cache).
- 2026-09-19 **#13** — width-confirmed cross + own-side drive-block refutation (e7 0.625→0.75); f316 ruled a GT slip and folded.
- 2026-09-09 **#12** — poke rule retuned ASCENT-ONLY (TOUCH_RISE_PX 57), level-exit vx rule deleted; eval merges GT overrides.
- 2026-09-09 **#11** — poke GT ratified; the 09-08 dictation was misattributed (e5 f300 = poke, e6 f310 = hard).
- 2026-09-08 **#10** — e6 poke read (resolver touch-3 fall-through + analyzer type + stance-majority team) + rally-opening serve gate + redirect locality; e7 GT ratified; e5/e6 team 1.0.
- 2026-09-06 **#9** — in-court preference (off-court cost penalty) fixes bystander squat + Hungarian chain-swaps (point 16).
- 2026-09-06 **#8** — squatter review: sideline straddlers expire from the roster (e2/e7 slots freed early).
- 2026-09-06 **#7** — ball-matching rework: identity by trajectory + motion, never confidence; static spares can't bootstrap/steal/starve.
- 2026-09-05 **#6** — GAME-ON badge latency fixed (rolling sustained-flight provisional); serve-init semantics (provisional fast ON, serve arming); heatmap landscape + cache busting.
- 2026-09-05 **#5** — player-page court SVG field heatmap (two rounds).
- 2026-09-04 **#4** — analysis DB + player labeling + local web UI; extraction/DB split by lossless file contract.
- 2026-09-04 **#3** — e1 GT re-verified (three mixed id conventions unified; queue empty); joust-split adjudicated; reentry contact shipped (e6 f308).
- 2026-09-01 — trail render fix (masked blend, black boxes gone).
- 2026-08-31 — outcome semantics completed: kill = direct fall OR dug-and-dies-without-a-set.
- 2026-08-30 — spike analytics: trail, touch/hard, 9-zone grid, kill/dug outcomes; f297 GT corrected.
- 2026-08-29 — off-court hold horizon (=90f) recovers e2's roster slot.
- 2026-08-27 — short-gap bridge ships e2/e6's missed digs; GT honesty rounds.
- 2026-08-26 — e5 action layer fully resolved (gap-bridged bounce + 2.5 m net exemption); e2/e6 generality clean; e1's double-annotated GT deduped.
- 2026-08-18 — e5 serve-zone squatter fixed (server vote + trial expiry + contested swap); e4/e5 GT checked.
- 2026-08-17 — config-drift guard; config-default divergence FIXED (f539 block provenance); e3 GT serve frame fixed; live-debug frame counter; near-net flag closed by diagnosis; perf (device defaults, annotator cache, pose-lite).
- 2026-08-16 — team-aware contact attribution (team 0.69→0.92); server tracking fixed + ghost damping.
- 2026-08-15 — bystander-hijack fix (assignment-level court membership); first player-ID GT + occlusion-aware eval; ghosts excluded from the classifier.
- 2026-08-14 — player identity phase 1 (1a+1b+1c) shipped.

## Log (newest first)
### 2026-10-02 (sixty-second session) — D4 DECIDED: the serve-zone exemption is PARKED; next is the near-opening table, and the worker tier is quota-blocked

**Asked:** take the architect's answer to `docs/d4_gate_brief.md`, fold the decision
into STATUS, and start the next task (the SR4a near-opening table, carded with the
`task-card` skill).

**The decision (architect, relayed by the owner 2026-10-02).** M-a stays CLOSED.
**M-b (the serve-zone exemption from the 90 f off-court hold) is PARKED, not built**:
its ceiling is **+1 near serve of 16** (+2 only with P5, which needs a second
mechanism) against a 0.90 bar that needs 15 of 16, and the blunt version measured
**net 0** (+P7, -P18, false serves 12 -> 14, actions 207 -> 212). Why the cost cannot
be bounded from #61: **P18 is an attribution swap, not a rally_start failure** — the
same ball point (867.5, 313) in both arms, touch 1 in both, a NEW rally in both, and
the toucher track goes 3 -> 2, i.e. the hit is credited to the server's PARTNER, so
the contact reads `dig`; the lift also renumbers tracks match-wide (f2494: track 1 ->
4). Any exemption changes identity wherever it fires, so its price is only
measurable on a full-match run, which is the most expensive kind of refutation. The
geometric alternative was rejected as designed-blind (the two new false serves sit at
the right edge of the image, x ~1552-1576, and no foot-behind-the-line test has been
measured against them), and the comment it would be built around is stale: that
bystander is fed on 400 of 423 frames at today's horizon.

**What was done in `src/`: nothing.** No `src/` change, no decode, no new run. STATUS
only: open point 30's status + SR1d lines, the D4 owner decision and card, the SR4a
card, a Learning (a hold exemption's price shows up as identity churn elsewhere), the
Active-next ranking, and the AGENTS.md warning that `evaluate.py --predictions <dir>`
grades ZERO predictions on `src.main` output (it wants a `frame` key, `src.main`
writes `frame_number` — measured #61, it cost a vacuous 0.000-vs-0.000 "PASS" then).
The stale `player_off_court_hold_frames` comment at `src/utils/config.py:101` is now
on the deferred list: comment-only, inside the next session that touches `src/` anyway.

**Delegation BLOCKED — card SR4a is READY and UNRUN.** The `subagent` tool was not
exposed in this session, so the `scripts/run_task.sh` fallback was used: `zai/glm-5.3`
and `zai/glm-5.3-flash` both return `429 code 1310 Weekly/Monthly Limit Exhausted`
(reset 2026-10-03 18:49), `openrouter` has no API key and `amazon-bedrock` no region.
Three delegate attempts, zero files written, working tree untouched. **The card is the
first READY card, so `/next-task` runs it as soon as a worker model is reachable.**


### 2026-10-02 (sixty-first session) — SR1d: lifting the 90 f off-court hold is REFUTED; it recovers P7 exactly and still buys nothing

**Asked:** run card SR1d — measure the cost of lifting
`player_off_court_hold_frames` from 90 to 100000 on the 7 entreno clips and the
full match, before anyone designs the serve-zone exemption (M-b). Measure only,
no `src/` change. Full report: `docs/sr1d_hold_horizon_cost.md`; artifacts in
the git-ignored `output/sr1d/`.

**Method.** `Config.load` merges (118 keys in / out, 1 changed, verified), so
`output/sr1d/hold_off.yaml` overrides exactly one key. 14 runs, all exit 0, MPS,
sequential, one decode at a time. `src/` had drifted from `006e343` (`d402f65`,
the #59 live-debug panel), so step 2's condition fired and the baseline arm was
re-run too — and it comes out identical to the SR1-era artifacts on labels +
frames for all 7 clips, which is the evidence that the drift is inert for a
`--skip-visualization` batch run.

**Gate.** Step 3's frozen `evaluate.py --predictions <run dir>` command grades
**nothing**: 0 predictions on all 14 runs AND on the SR1-era artifacts (record:
e3 1.0), because the tool looks for an entry named `actions` in a directory and
takes `frame` where `src.main` writes `frame_number`. Both F1s would have been
0.000 vs 0.000 — a vacuous "SAFE-LOOKING" PASS. Executor STOPPED and reported;
**the owner authorised fixing the grading by naming the artifact** and the run
continued. The adapter renames the frame key and nothing else; validated by the
baseline arm reproducing the recorded F1s on 6 of 7 clips (e2 0.400 vs the
record's 0.571 is the documented pre-existing action-script path gap).

**Result.**
- Entreno: **ΔF1 0.000 on 7 of 7** — and not merely equal, the two arms' action
  streams are byte-identical event for event. The drills have nothing to gain.
- e2 bystander (the regression the 90 f horizon was built for): fed **423 f**
  with the lift vs **400 f** at baseline, i.e. fed **longer**, straight through.
  Side finding: it is fed on 400 of 423 frames at the 90 f horizon *today* — 08-29's
  "held a slot for 415 f" no longer describes it, and the horizon now buys only
  23 coasting frames.
- Match (26 061 f): near **8/16 → 8/16**, far 0/17 → 0/17, FP **12 → 14**,
  actions **207 → 212**, all hit timings within ±2 f. The aggregate is flat, the
  composition is not: **+P7** (serve emitted at f3747, delta +0, SR1b's
  prediction reproduces) and **−P18** — P18's contact is still emitted at the
  same f11996 but relabels `serve` → `dig`, the `rally_start` family SR1b found
  at P5 (still missed in both arms). The two extra false serves are f17749, f17943.

**Verdict: `global lift REFUTED`** (F1 criterion passes, bystander criterion
fails) → the serve-zone exemption needs design (architect / owner), which is the
expected outcome. This is **not** evidence against a *geometric* exemption: the
server is behind the own baseline and the bystander straddles the sideline, and
this run only shows the crude global version cannot separate them. What it adds
to the price list: the `rally_start` coupling at P5/P18.

**Card hygiene for the planner.** (1) Step 3's command should name a readable
artifact; it cost the session a STOP. (2) "stop if the baseline artifacts are
older than the current `src/`" is TRUE here while step 2 explicitly says to
re-run the baseline in that case — reconcile the two. (3) Report the per-point
SET of recovered/lost serves, not the aggregate: 8/16 → 8/16 hides the whole
finding.

**Nothing in `src/` changed.** Suite not run (no `scripts/` or `tests/` touched).

### 2026-10-02 (sixtieth session) — SR1c closed: the takeoff-stance read could not be trusted, and the fix it pointed at is a trade, not a gain

**Asked:** run card SR1c — decide with numbers whether judging "behind the
baseline" on where the server stood just before the hit recovers the four missed
near serves, without inventing false serves. Diagnose-only.

**What happened.** One sequential full-match diagnostic pass (26061 frames,
1888 s, MPS, no seek). Its parity check passed: the 207 emitted actions matched
the shipped artifact exactly. Then the card's second check — can the probe
reproduce the reading the pipeline actually made? — **failed**: 194 of 207 on the
match, 6 of 7 and 13 of 14 on two practice clips, against a 98% requirement. A
failed check is a stop, so the decision rule was never read and nothing was
tuned to get past it.

**Why it failed, all 15 cases the same.** Each disagreement is a contact where
the player had no fresh detection at the moment of the hit — the box over them
was being carried forward, or they had briefly dropped off the tracked list. The
probe had been told to ignore carried-forward positions, so it had nothing to
read, while the pipeline had read the player's last genuinely detected position,
which can be a few frames *after* the hit. The frames were rendered as evidence:
in every case the player is visible and moving under a frozen box.

**What the owner established.** Looking at those frames: only two of the fifteen
are serves, and the committed ground truth agrees (the other thirteen are
spikes, digs, sets and overpasses). That is also why the bad reading was mostly
harmless — a serve needs the hit to open a rally as well as the player to be
behind the line, and on all thirteen the rally was already under way, so the
pipeline read the position wrong and then did nothing with it.

**Why the fix is a trade.** The two serves that currently work are the two where
the player's real position is available only *after* the hit, so a rule that
looks backwards for a cleaner position loses them. At the pre-registered window
the same rule gains two other near serves (of the four missed) and cannot reach
the other two at any window. Two gained, two lost — the same total with a
different set of hits, before counting knock-on effects, which were not measured.

**Outcome:** closed with nothing shipped; no source file touched; owner chose to
leave the near side as is. Written up in `docs/sr1c_takeoff_stance.md`.

**Housekeeping / a warning.** Suite **1156** green (1134 collected at HEAD plus
the 22 new tests; `scripts/probe_takeoff_stance.py`, `tests/test_takeoff_stance.py`).
Note for the next session: commit `d402f65` (#59) landed on this tree at
**15:31:21 the same day, while this session was running**, so a second session
was active on the shared working tree (AGENTS.md §8). Nothing was lost — this
session's files are its own and no stash/checkout was used — but an earlier test
count in this session read 1113 because the tree was still pre-#59 at that
moment. Serialize sessions, or give each one its own worktree.

**Next:** card SR1d (the cost of lifting the 90-frame off-court hold) is the
other open measurement; any change to the serve logic still needs both of them
plus an owner decision.

