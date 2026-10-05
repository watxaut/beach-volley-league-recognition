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

**Last updated:** 2026-10-05 (eighty-third session — **#83: side-switch-aware
TEAM IDENTITY RESOLVER shipped (output labels only; tracking byte-identical by
construction).** New `src/tracking/identity_resolver.py` (`TeamIdentityResolver`)
re-derives P1A/P2A/P1B/P2B every frame from the structural fact that teammates
share a side: (1) ORIENTATION (which squad is near) by a one-sided CUSUM over
per-body evidence with a 900 f minimum dwell, labels withheld while in doubt;
(2) within-side slots by per-tracklet evidence EMA + hysteresis + elimination.
Evidence = impostor-normalised DISCRIMINATION + same-view FIT, both calibrated on
the video's own enrollment samples (no venue/kit constant); background-weighted,
resolution-normalised part histograms (H x S + achromatic V) + lateral-scale
height; each player LEARNS the view it was not enrolled in after a confident flip
(anchors never replaced). The #82 resolver keeps running only to feed the
tracker's enrollment guards. Synthetic validation (drawn near/back vs far/front
players, scrambled ids): switches flip in ~10 frames with ZERO wrong labels, 3
consecutive switches, no flip through occlusion, silent teammate swap fixed in
≤4 f. NOT yet run on real footage (no video in the cloud session) — owner runs
`scripts/probe_identity_switches.py` on the 20260920 match next. Suite **1475**
(+30). Config `player_identity_mode` ("team"/"legacy") + 3 CUSUM keys.)
Prior sessions this file: #73's overlay paragraph below; #72's reach-cascade refutation below that (also in `docs/g3_reach_cascade.md`).
An offline replay of the unmodified `ActionContextResolver` over the 185 accepted rows PLUS every `reason="reach"` rejection within a scalar factor K (the gate re-scores offline) scores, against the 182 in-region GT events at ±15 f: BASE 78/139 = 0.561 label, 90/139 touch; **K=1.1 +4 found → +1 label; K=1.2 +14 found (all 14 within ±15 f of a GT contact, the precision-clean gate) → −4 LABELS; K=1.3 +21 → −5; K=1.5 +28 → −1; K=2.0 +48 → +1 at rate 0.513 vs 0.561.** Admitting ALL 71 reach rows repairs only **9 of 49** wrong touch numbers (40 still wrong), because the count is driven by the resolver's own resets, not by recall — so the recall → count → label chain is real about the ERROR POPULATION but **earning the recall does not earn the count**. The architect's own "~0.00 class accuracy" caveat is CONFIRMED and slightly optimistic: the honest expectation is negative. **The 44 missed contacts stay a RECALL story (contact P/R, per-point completeness), NOT the path to 0.70 class accuracy — do not spend a GPU A/B on them while the goal is the class metric.** The label bucket's two count routes are now BOTH measured and closed (re-derive: TC1 +0.050; earn-by-recall: #72 negative), leaving **39 of 55 wrong labels with a wrong count and 16 with a CORRECT count** (the residual Layer-1/2 rule errors open point 9 already names).
**Seventy-third session (2026-10-03): a display-only live-debug overlay LANDED** — every ball the DETECTOR saw this frame drawn as a hollow box with its confidence and the detector's own verdict (`sus` stationary-suspect / `rm` dropped by static suppression), toggle `b`, default ON; reads only the sanctioned `BallDetector.raw_detections` side channel, no new Config key, processing path untouched; tests +9, suite **1336**. Its session's own commit claim (`8040f04`) was FALSE — the commit never existed (reflog clean after `ad1dc03`); committed after coordinator verification. With the toggle ON the saved `--debug-live` video now carries the candidate boxes too (still unpanelled).
TC1 (`touch_rule_gate = TOUCH_COUNT_LEVER_REFUTED/0.6187`) and the #71 reach diagnosis + tier-2 architect call (`docs/g3_reach_gate_bucket.md`, `docs/reach_gate_architect_call.md`) stand as measured; `docs/tc1_touch_rules.md`, `logs/tc1_report.md`, `logs/tc1_stdout.txt`, `scripts/probe_touch_rules.py`, open points 9 / 7).
Committed artifacts only: no `src/` change, no decode, no seek, no GT edit,
held-out session untouched. G1 reproduced #68 exactly (185 accepted, 157
bump_set, 139 found, touch 96/139 = 0.691, R0 replay control 79/139 = 0.568,
GT-touch substitution 110/139 = 0.791, serve median +23 f, shipped stream
85/139 = 0.612 / 0.589). Rule search offline on dev+entreno only chose R4 (R0
5.577 / R1-R3 5.591 / R4 5.745 summed F1) and its ONE held-out shot scored
label accuracy **86/139 = 0.6187** (**+0.050** over R0, bars were +0.132 PASS /
+0.082 PARTIAL) at touch accuracy **103/139 = 0.741**; non-serve
**86/127 = 0.677** vs the GT-touch arm's 110/127 = 0.866. **The 43 wrong-touch
found contacts are STARVED, not mis-reset**: `under_counted` 20 +
`previous_contact_missing` 13 = **33 of 43 (77 %)**, `team_change_not_reset` 5,
`over_counted` 4, `attack_not_reset` 1 — so the fix is upstream (emit the
missing contacts, open points 2/5) and touch-count surgery buys at most +0.050.
Three card defects reported, not reinterpreted: criterion (ii) is unsatisfiable
by an offline replay (the R0 replay is off-record on 4 of 7 drills); R2 is a
no-op by construction (the card also mandates keeping the resolver's own
`attack_before` reset in every arm); G1's two reference figures need
production-stream semantics the card did not state. Suite **1327 passed**
(+41). No task card written or reordered.

**#68 (previous session):** the TOUCH-COUNT LEVER diagnosis — Layer 1 is
degenerate (157 of 185 accepted contacts carry `bump_set`), so every
`dig`/`set`/`overpass`/`serve` decision is `ActionContextResolver._decide`
(`src/recognition/action_context.py:175-219`) keyed on `_poss_touch`;
substituting the real GT `touch_number` into the UNMODIFIED `_decide` lifts
label accuracy 79/139 = 0.568 → 110/139 = 0.791 (non-serve 0.622 → 0.866) while
`touch_number` itself is only 96/139 = 0.691. Timing is NOT the bottleneck
(median **−2 f** for dig/set/spike/overpass; only `serve` is late at **+23 f**),
so the far serve is the SMALLEST lever on the goal metric. **Baseline hygiene,
corrected in that session after CARD TC1's executor refused its own G1 and was
right: the shipped stream is 85/139 = 0.612 (dump `action`) / 83/141 = 0.589
(`pipeline_output.json`), NOT 0.568** — the `accepted` rows carry no
`behind_baseline`, so a replay is 168/185 faithful and scores 0/12 on serves.
Full detail: `docs/g3_touch_count_lever.md`, `logs/touch_lever_stdout.txt`,
open point 9, Session index #68/#70.

**#64 (earlier session):** 2026-10-02 (sixty-fourth session, **PM1 verdict: `FAIL=blocked` —
the far-serve record cannot bypass the point map; SR4-FAR is BLOCKED on open point
22**, `docs/pm1_point_map.md`, `logs/pm1_report.md`, `scripts/probe_point_map.py`,
open point **30**). Post-hoc, committed artifacts only: no `src/` change, no decode,
no seek, held-out session untouched. **The three numbers:** the UNBOUND (frame,
side) form emits **16 of 17 far serves with 0/16 near misclaimed** (>= 15 required,
PASS) but carries **294 false serves** (<= 0 required, FAIL); the best binding
rule by precision is the gap rule at **11 of 17 far hits with 35 false serves**
(need >= 12/17 and <= 3); the most generous rule, first `start_frame` after,
keeps **16 of 17** but carries **288 false serves**. So the signal is complete and
the *map* is what cannot be worked around. Reproduced and extended #63: **31
pipeline points vs 33 GT points**, **0 of 17 far serves inside their own window**,
and the ordinal-pairing offset is **one-signed +6 … +3153 f on all 31 pairs** (the
map is uniformly *late*, not noisy) — while only **2 of 17 far serves** sit inside
any window and **16 of 33 serves sit in inter-point gaps** (near is the opposite:
14 of 16 inside). [inferred] cause: `_finalize_group` opens a point on a flight
burst *before* the rally's first action, so the opener precedes the serve it
belongs to. **Next: open point 22** (move the point opener to the serve / its
rally) before SR4-FAR; the width plateau (far 16-27 px, near 39-50 px, any cut in
26-32 -> 16/17 far, 0/16 near) survives as a Learning and is a detection result
only. Suite 1214 passed (1191 + 23 new pins).

**#63 (previous session):** 2026-10-02 (sixty-third session, **the serve record is REFUTED as
specified, and the reason is the point map, not the signal: 0 of 17 far serves fall
inside their own point window** — `docs/sr4_architect_call.md`, open point **30**).
Tier-2 architect call (route 4) + coordinator re-measurement. No `src/` change, no
decode, held-out session untouched. Three measured results, all reproducible from
committed artifacts: (1) **NEAR has a hard coverage ceiling of 13/16** — three near
serves have no action on the serving side within +/-15 f (P5 -81 f, P7 -108 f,
P24 +29 f), so the planned bar of 15/16 is above the ceiling and SR4-NEAR must not
be built; (2) **the far-side side signal is the strongest in the project and was not
in the brief** — the ball leaving the far half is 14-23 px wide at all 17 far serves
vs 39-52 px at the 3 near serves that have a flight event, a plateau at any cut in
26-32 px giving **far 16/17 with 0/16 near misclaimed**; (3) **binding it to points
collapses it** — 9-11/17 with 2-8 false records in-window, 432 candidates unscoped,
and every suppression rule tried trades true serves for false ones 1-for-1. Root
cause: `game_state.points` has 31 entries against 33 GT points and every point starts
1-1466 f AFTER its own serve (the session-56 backdated onset). Next (ranked):
**(a) the point-map probe** (pure post-hoc, decides whether SR4-FAR is a 1-rule job
or blocked on open point 22), then SR4-FAR, then SR4-NEAR on perception, then the
held-out session once, then SR5 -> SR6. Also measured: a delegation harness bug —
prompts over ~1 KB kill the child `pi` with `EXIT 137` on every model; briefs must be
files the child reads (see *Learnings*).

**#63 (previous session):** 2026-10-02 (sixty-second session + delegated worker,
**SR4a DONE: 5 of the 8 near-serve misses are repairable after the fact, so the
per-point serve record can be built without touching the main pipeline; the tracking
exemption reopens as an architect call only**, `docs/sr4a_near_openings.md`,
`scripts/probe_near_openings.py`, open point **30**, commit `0bd2a28`). No `src/`
change, no decode. Buckets over the 8 misses: 2 wrong label, 3 present-but-misplaced,
3 never produced. **Design constraint measured, not assumed: a record keyed on the
window's first action would recover only 4 of the 8 true serves, and 6 of the 12
false serves sit inside a near-miss window — the record must key on the same-side
contact within tolerance.** Next: write card **SR4** (no card exists for it yet),
then the held-out session once, then SR5 -> SR6.

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

**#83 SHIPPED: TEAM IDENTITY RESOLVER — the owner's side-switch request (labels
must find the same person again after a switch; a few wrong/blank frames are
acceptable, actions are ~10% of frames).** Identity stack today, all output-only
(no tracking decision reads it): E1 enrollment pre-pass (#81) → 4 references,
now also carrying per-sample identity descriptors + heights → `TeamIdentityResolver`
(#83, `player_identity_mode: "team"`, default) stamps `player_label`/`squad`/`slot`
on tracked players and actions; actions take the label at their CONTACT frame
(`label_for(tid, frame)`, 900 f history), falling back to the emission-time label.
The #82 per-frame resolver still runs and still writes `_track_labels`, which ONLY
the tracker's enrollment guards read — so tracking is identical in "team" and
"legacy" modes (unit-pinned). Mechanism: orientation CUSUM (threshold 40, drift
0.5, min dwell 900 f; doubt at 25% of the threshold or one frame with mean swap
advantage ≥3 over ≥2 bodies → labels blank, never wrong); within-side slots by
EMA evidence (+1 hold bonus, −1 hold floor, quick-EMA hold break for overlap
swaps, 5-frame claim delay, elimination only with a decided partner); evidence
`e = z + f` (z = vs all other players' samples in both views, f = vs the player's
own same-view samples, capped +1); learning only when settled, isolated
(IoU < 0.05), in court, pair margin ≥2. Eligible bodies = in court (+16 px
slack) or in a serve zone (the server). **Validation status:** synthetic only —
the real-footage gate is the owner's run of `scripts/probe_identity_switches.py`
(one sequential production pass, team vs legacy labels side by side, contact
sheets rows = P1A..P2B, and with `--contacts-gt
ground_truth/20260920_match_contacts.json`: orientation at all 184 GT contacts,
one flip per GT switch window after P7/P14/P21/P28, action-label squad accuracy
team vs legacy). Entreno A/B for action F1 is unchanged by construction (labels
never reach the classifier) but a fresh run is still owed per §1. Open risks,
unmeasured: cross-view similarity on real far players (weak sims 0.3-0.6 in #82),
lighting drift over a long match, same-gender teams with similar kit.

**#80 SHIPPED: ball GROUND-CONTACT / OUT-of-court observer, display+diag, beside
possession (#77-#79).** New always-on pure observer
`src/analysis/ball_ground_contact.py` in `process_frame` (step 3d): maps the TRACKED
ball's bbox bottom-center through the ground homography
(`compute_ground_homography`, SIGN-normalized — `cv2.findHomography` normalization is
arbitrary and the owner's convention yields w<0 on-court) and reads groundedness =
bbox width / projected ground diameter (D = 0.67/π) at the mapped point; hysteresis
AIR (ratio ≥1.45 or degenerate) → GROUND (≤1.25 AND inside court rect +0.25 m) / OUT
(grounded outside; the band re-locates in/out for a rolling ball); BOUNCE = gated
image-vy sign flip (≥+2 → ≤−2 px/f, gap 1, armed by the fall). Noise inflates the
ratio only → cannot fake GROUND. Live-debug GROUND/OUT/AIR label at the ball +
per-candidate GND/AIR tags in the `b` overlay + panel `ground:` line; diag
`ball_ground`, SCHEMA_VERSION 3; NO Config key, NO `pipeline_output.json` key.
Validated on the game_state video (13 GT point windows, 8196 f): IN-window 95.5% AIR
vs BETWEEN-points 39.3% GROUND/OUT; live GROUND/OUT within ≤2 s of 11/13 GT point
stops (the 2 misses = ball carried at once — honest AIR); 10 bounces (5 in-rally, 5
dead-ball). **Known half-gap (open point 31, OWNER GATE before any `src/` change): a
point-ending ball comes to REST and the static-ball suppression removes it from the
track BY DESIGN — the tracker drops the final descent (e3 f616) and the label
honestly HOLDS AIR; v1.5 would read a near-stationary post-suppression detection on
lost-track frames (§6-pure, tagged `from_candidate`)**. The probe also FIXED a latent
wiring bug: `FrameProcessor.__init__` loads the calibration itself and the batch path
never called `set_court_calibration`, so POSSESSION ran on FALLBACK px bands in every
batch run since #77 — both observers now wired at init, tests pin it. Possession
stands as recalibrated #79 (asymmetric evidence — NEAR on rolling max ≥1.45×d_net,
FAR on max ≤0.85× OR ≥4 of last 12 measured ≤0.85×; measured regimes: near flight
1.49-1.6×, net-plane rest AND blurred far flight 1.0-1.35× indistinguishable, far
ground 0.5-0.8×d_net). Ratified post-hoc sequencing stands: **C1** fitted ball-fate
measurement (pre-registered at the m ≤ 2k−12 budget) → **C2** possession timeline →
**C3** overpass relabel on the held-out → **C4** ambiguous-touch reattribution.
The serves track
below remains the standing record.
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
  e3 1.0, e4 0.933, e5 0.923, e6 0.933, e7 0.75 — CAVEAT #81: e2's 0.571 reads
  0.400 on BOTH fresh MPS arms (pre-existing fresh-run variance in the base; same-
  session A/B is the valid comparison). Suite **1549**.

**Refuted and parked** (do not reopen without new data): T5 tracker admission, R1
departure gate, S1 looming, scale-aware geometry, M1 far-end crop, possession
signal, overpass width crossing, R2 confidence calibration.

**Known defects:** `scripts/annotate_player_gt.py` and `src/db/ingest.py` seek on
VFR. Both are allow-listed in `tests/test_vfr_seek_guard.py`. Fix the annotator
before any frame-shown annotation pass.

**Active next (ranked) — execute via the task cards below (`/next-task`):**
0. **TC1 DONE (#69): `touch_rule_gate = TOUCH_COUNT_LEVER_REFUTED/0.6187` — the possession count is NOT re-derivable from the emitted contacts; nothing ships, no architect card is justified.** `docs/tc1_touch_rules.md`, `logs/tc1_report.md`, transcript `logs/tc1_stdout.txt`, `scripts/probe_touch_rules.py` (imports `ActionContextResolver` + the existing matchers, no `cv2`, no decode, no seek, exit 2 on FAIL), `tests/test_touch_rules.py` (+41; suite **1327**). G1 reproduced #68 EXACTLY (185 accepted; bump_set 157 / attack 16 / block 12; 139 found; touch accuracy **96/139 = 0.691**; R0 replay control **79/139 = 0.568**; GT-touch substitution **110/139 = 0.791**; timing medians dig/set/spike/overpass **−2 f**, serve **+23 f**; shipped stream 85/139 = 0.612 / 0.589). **Step 2 is the centre: the 43 wrong-touch found contacts are STARVED, not mis-reset** — `under_counted` **20** + `previous_contact_missing` **13** = **33 of 43 (77 %)**, `team_change_not_reset` **5**, `over_counted` **4**, `attack_not_reset` **1** — which independently re-confirms #68's "errors cluster where fewer contacts were emitted" mechanism and says the fix is UPSTREAM (emit the missing contacts; open points 2/5), not in the counter. **Step 3 (dev + e1–e7 only; R0 = emitted count, R1 = +reset on any team change, R2 = +reset after an attack gesture, R3 = +reset on `rally_id` change, R4 = +ball-width cross confirmation, abstaining where `ball_side is None` — 64 of 185; every rule replayed through the UNMODIFIED `_decide`)**: summed F1 R0 5.577 / R1–R3 5.591 / R4 **5.745 → R4 chosen**; per-drill R0 is never beaten on more than one drill (e5 0.923 → 0.769 under R1–R3). **Step 4, ONE held-out shot: label accuracy 86/139 = 0.6187 = +0.050 over the R0 control** (PASS bar +0.132, PARTIAL +0.082 → **neither met**) at touch accuracy **103/139 = 0.741**; the non-serve arm is **86/127 = 0.677** vs R0 79/127 = 0.622 and the GT-touch arm 110/127 = 0.866 — a perfect count is worth +0.244, the best re-derived count +0.055. **Step 5 (offline approximation, NOT the real gate): R4 vs the recorded F1 — e1 0.706→0.706, e2 0.571→0.533, e3 1.000→0.929, e4 0.933→0.933, e5 0.923→0.923, e6 0.933→0.800, e7 0.750→0.500 — 4 of 7 outside ±0.01, but the R0 REPLAY is itself off-record on 4 of 7 (e2 −0.171, e3 −0.071, e6 −0.133, e7 −0.250), so criterion (ii) as literally written is unsatisfiable by any replay; reported, NOT reinterpreted (the verdict already fails on (i)). Rule-relative, R4 made no drill worse than R0 (+0.133 on e2, 0.000 elsewhere). **Step 6: NO `src/` change** — #68's +0.223 survives as a DIAGNOSTIC lever only; what is refuted is recovering it by re-deriving the count. Three card defects reported to the coordinator: (a) (ii) as above; (b) **R2 is a no-op by construction** — the card also mandates keeping the resolver's own `attack_before` reset in EVERY arm, which IS R2, so R2 ≡ R1 always (pinned by `test_r2_is_subsumed_by_the_base_attack_reset`); (c) G1's timing / 0.589 references only reproduce on the PRODUCTION stream over ALL region events, not on the found subset. **Next task (coordinator's): DONE as #72** — the reach-gate bucket WAS that diagnosis, and the cascade verdict is NEGATIVE for labels (item 0z): the recall work stays parked for contact completeness (open points 2/5), NOT class accuracy. No card written or reordered by this card.
0a. **POST-INSERT-CLOSURE RANKING (coordinator, 2026-10-03) — [CORRECTED #76, 2026-10-04: the "no SINGLE lever reaches the bar / COMPOUND levers / owner scope decision" conclusion is WITHDRAWN as a category error; keep the INSERT measurements, discard the ceiling arithmetic.]** The `90/139 = 0.6475` "label-only ceiling" quoted here is TOUCH accuracy, not label accuracy: `docs/g3_reach_cascade.md:43` records `label 78/139 = 0.561  touch 90/139 = 0.647` on the same 139 found contacts, and the label-only oracle on those contacts is **139/139 = 1.000** (`scripts/probe_label_ceilings.py`, `logs/label_ceilings_report.md`, suite 1448). **MEASURED: the `overpass` lever alone crosses 0.70 on the bar arm — `diag` 0.6131 → 0.7080 (+0.0949, 13/137); `production` 0.5899 → 0.6835; `pass2` 0.5612 → 0.6547.** The bar needs +12 labels (84 → 96 of 137); `overpass` supplies 13. Contact F1 is invariant across every arm because `evaluate_timed.match_events` is class-agnostic by design — **the bar is `class_accuracy`, so a lever's value is exactly its label count.** Second coherent bucket, newly named: **`spike → block` x7** (the match GT has ZERO `block` events). The remaining original findings stand as measurements: INSERT-of-far-serves **96/150 = 0.6400 IN-SAMPLE** (#74c, precision 0.6111, 0 near misclaims, 0 owner-negative FP; a RECALL lever on a different denominator, never part of the 0.70 arithmetic); #74b's "103/139 = 0.741" was a numerator-only artefact (consistent 103/152 ≈ 0.678); all 11 INSERT hits at_seam, all 6 misses (P2/P4/P8 dev, P13/P31/P32 held-out) in_gap — the point map's uniform lateness (PM1), not the evidence layer's. **Remaining single label lever: overpass +0.094 — now THE blocking question for the match half of G3, and a LAYER-2 RULE-DESIGN problem, not a discovery problem (the resolver emits `overpass` only at `touch == 2 and not has_follow`; the 13 matched overpasses sit at the same counts as dig/set/spike).** Goal bars today: match shipped **0.612** (diag `action`) / 0.589 (`pipeline_output.json`) vs the 0.70 bar. **Entreno (#74d): the recorded baselines reproduce exactly (7/7 drills, Δ=0.000, script path, MPS) and 4 of 7 already pass 0.90 (e3 1.000, e4/e6 0.933, e5 0.923); the losing drills are e1 0.706 / e2 0.571 / e7 0.750 and their verdict is `NEW MECHANISMS DOMINATE` — known mechanisms cover only 2/9 reachable losses (count error e2 f257; behind_baseline at INVERTED polarity e2 f32), the 7 new ones are `gesture_miss` ×2, `contact_gate` ×4 (reach gate fires ONLY far-side — 7/7 rejections team B — plus ball-out-of-frame and dead geometry) and `emitted_vocabulary` ×1 (`freeball` ∉ `VolleyballAction`); 2 ceiling events. Fixing the KNOWN mechanisms alone: e1 0.706 / e2 0.857 / e7 0.750 — all still under. Per-drill 0.90 ceilings: e1 0.941 nominal but a MEASURED 0.824 without the vocabulary change (the f256 spike relabel steals the f258 block match; `MIN_CONTACT_GAP=9` makes the 1-f-apart pair un-emittable), e2 0.933, e7 0.947 (needs all 3 of its far-side events). The metric-definition question stays open, but the diagnosis is convention-agnostic.** The far-side/upstream-emission story (open points 2/5) now spans BOTH halves of the goal.
0z. **REACH-GATE BUCKET — DIAGNOSED (#71) then REFUTED as a label lever (#72): the scalar reach relaxation does NOT fix the labels, and the pose-anchored arm inherits the same failure mode. NOTHING SHIPS, CARD RG1 is NOT written. The 44 missed contacts are a RECALL story, not the 0.70 class-accuracy path.** #72 (`docs/g3_reach_cascade.md`) replayed the unmodified `ActionContextResolver` over the 185 accepted rows plus every scalar-reachable `reach` rejection: BASE 78/139 = 0.561 label / 90/139 touch; K=1.1 +4 found → +1 label; **K=1.2 +14 found (14/14 within ±15 f of a GT contact — the precision-clean gate) → −4 LABELS**; K=1.3 +21 → −5; K=2.0 +48 → +1 at 0.513. Admitting ALL 71 repairs only **9 of 49** wrong touch numbers. Reason: the count is driven by the resolver's own resets, not by recall. The #71 diagnosis below stands as the measured record. [UPDATED #74b: the far-side slice of the recall story IS now the 0.70 path — the serve bucket's 13 not-found contacts carry 0.647→0.741; the reach-gate refutation stands for the reach mechanism specifically.] [UPDATED #74c: the 0.647→0.741 step is itself corrected — 0.741 was numerator-only; the measured INSERT ceiling is 96/150 = 0.640 IN-SAMPLE and the in-gap 6 are point-map-blocked. See item 0a.]

    #71 diagnosis (kept): the reach gate blocks **20 of the 44 held-out GT contacts that have no accepted contact within ±15 f** (median nearest 33 f); every one has a rejected row within 15 f. Base-rate-normalised against frame coverage, **`reach` is 9.78× enriched** (71 rejections, 4.65 % coverage → 20 observed vs 2.05 expected); `no_contact_geometry` is the residual bucket (1.76×, blocks 43 of 44, not itself actionable), `no_ball_sighting` is at chance (0.99×), `min_contact_gap` is DEPLETED (0.42×). All 20 reach-carrying misses sit in points where accepted < GT (P10 3, P18 1, P19 4, P22 1, P25 4, P26 2, P30 4, P31 1). Raw-scalar admission curve: 1.1× 4/4 (1.00), **1.2× 14/14 (1.00)**, 1.3× 21/19 (0.90), 2.0× 48/32 (0.67); of the 20 misses 2 within 1.05×, 6 within 1.2×, 9 within 1.3×, 16 within 2.0×; the other 24 of 44 have no candidate geometry at all. **Three measured reasons the scalar could not ship from the diagnosis alone:** (i) the match's OWN dev split (P≤8, cut f4910) admits 12-15 candidates carrying **ZERO** GT contacts at every threshold, so the threshold is NOT selectable out of sample from the match — only the standalone dev clip + 7 drills can select it (a dev-selected 2.0× gate, dev precision 0.80, generalises to 32/36 = 0.89 but admits 6 false drill contacts); (ii) at 1.2× only **6 of 14** carry the correct `target_team`, and across all 71 rejections `target_team` is **B 64 / A 6**; (iii) `CONTACT_REACH = 140 px` (`src/recognition/action_classifier.py:53`) is a px constant on GT-validated action logic, venue-coupled (206 px vs 464-479 px court depth, AGENTS.md §7). The tier-2 architect call (`docs/reach_gate_architect_call.md`) proposed a pose-anchored reach (`0.5 × bbox_width_px` hand radius, class constant default OFF, no new `Config` key) with its own A/B gates — **but it targets the same 20 contacts through the same resolver and so inherits #72's negative result; its only distinct argument was scale-freedom, which is not a label argument.**
0b. **PG2 DONE (#67): `point_map_alignment = PG1_VERDICT_IS_A_PAIRING_ARTIFACT` — PASS. PG1's `point_map_gate = REFUTED/1` ("uniformly late") is an ARTIFACT of its ordinal pairing (GT *P* ↔ pipeline *P−1*); the window starts ARE serve-anchored, so SR4-FAR is MIS-KEYED, not blocked.** `docs/point_map_seam.md`, `logs/pg2_report.md`, `scripts/score_point_map_alignment.py` (imports `score_point_map` → `probe_point_map`, no `cv2`, exit 2 on FAIL), `tests/test_point_map_alignment.py` (+49; suite **1286** = 1237 + 49). Pairing-independent, all three pre-registered criteria PASS: **14 of 31** window starts within ±15 f of ANY GT serve (23/31 at ±30 f, 25/31 at ±60 f) vs a seeded Monte-Carlo chance baseline of **1.21 of 31** (20 000 draws, seed 20261002, serve balls cover 3.93 % of frames) = **11.56×** (bar ≥ 5×); monotone order-preserving DP keeps **14 pairs within ±15 f at every skip cost** 60/120/240 f (27–28 pairs, median −6/−8 f). PG1's ordinal numbers reproduce exactly (1 of 33, 31 of 31 non-negative, +6/+3153/+1700 f) and now decide nothing. Seam: far serves **AT a window start** (11/17 at_seam, 0 interior, 6 in a gap), near serves **INSIDE** one (11/16, geometrically 14/16) — #65's "far 14/17 in the gaps" is a seam. Step 5 narrow `far_flight` (`width_start <= 28`, fixed) keyed on window starts: **11/17 far, 0/16 near misclaimed, 5 unanchored** at ±10 and ±15 f — **IN-SAMPLE re-test target, NOT shippable** (STOP list, AGENTS.md §5). Card defect logged: 1(e) asks for a "sign-free" median of −6 f (impossible); −6 f is the nearest-**boundary** signed median (nearest-start signed −1 f, sign-free +17 f) — all three readings serve-anchored, so the verdict does not turn on it. **Next task (coordinator's):** the far-serve rule keyed on WINDOW STARTS, re-tested OUT of sample against a non-serve control (AGENTS.md §6 rules) — the corrected-opener architect card is NOT justified by either run, and SR4-FAR stays OFF until that rule has an out-of-sample score. No card written or reordered by this card.
1. **PM1 DONE (#64): `FAIL=blocked`** — `docs/pm1_point_map.md`,
   `logs/pm1_report.md`. The probe ran both gates green (G1 baseline reproduced
   near 8/16 / far 0/17 / 12 FP; G2 plateau re-derived far 16-27 px vs near
   39-50 px, 16/17 far and 0/16 near at every cut 26-32) and returned the
   pre-registered FAIL: unbound (frame, side) = **16/17 far hits with 294 false
   serves**; best binding rule = **11/17 with 35 false serves**; first-after =
   **16/17 with 288**. **The next task is open point 22** (the episode->point map):
   PM1 shows the far-serve signal is complete (16/17) and that no binding rule can
   make it precise, because the map's window opener is one-signed **+6 … +3153 f
   late** and the far serves sit in inter-point gaps (16 of 33) while the near ones
   sit in windows (14 of 16) — the fix must move the opener to the serve or to the
   rally it heads. SR4-FAR stays blocked behind that; it is not the next card.
2. **SR4a** (DONE #62+, `docs/sr4a_near_openings.md`): the near-opening table —
   G1 reproduced on both arms (near 8/16, far 0/17, 12 FP, drills 3/5); the 8 near
   misses bucket into **2 mislabeled_opener + 3 not_opener + 3 not_emitted**.
   **G2 verdicts: SR4's near side proceeds after the fact (5 repairable of 8, rule
   >= 4) and M-b is REOPENED as a fresh architect call only (3 never produced, 2 of
   them coasting, rules >= 3 AND >= 2) — nothing ships.** Trap guard 0. Superseded
   on the near side by #63: the near record's bar (15/16) is above its measured
   coverage ceiling (13/16), so **SR4-NEAR does not get built as planned** — it
   waits on perception.
3. **SR4-FAR is BLOCKED behind open point 22** (was "next after the probe"; #64
   measured why): the detection exists (ball width 16-27 px far vs 39-50 px near,
   plateau 26-32 px, far 16/17, near 0/16) but **no binding rule makes it precise**
   — unbound 16/17 with 294 false serves, best binding 11/17 with 35. It becomes a
   one-rule job only AFTER the point map opens at the serve. Keep the cut
   per-session (camera-scale biased, AGENTS.md §5), never frozen. **#68 demoted
   it further: the far serve is the SMALLEST lever on the goal metric** — making
   all 12 far serves perfect moves class accuracy only 0.589→0.621
   (+0.032; total-correct 0.456→0.522, +0.066 = exactly 12/182), while the label
   bucket is 58 losses and the touch count alone is worth +0.223. Do the label
   work first.
4. **SR3 worker half, ONCE, after the rules are frozen**: teach `score_serves.py`
   the `serve-anchors-v1` format, run the held-out session, score it once. Still
   not run — the serve rules are not frozen, so the freeze gate is not met.
5. **SR5 -> SR6.**
6. **Deferred edit, not a card:** the `player_off_court_hold_frames` comment at
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

### CARD TC1 — the TOUCH-COUNT rule: can a re-derived possession count reach the label bar offline, with no `src/` change?
- **status:** READY
- **type:** measurement + offline rule search (diagnose-first; no production change)
- **goal:** decide whether the label bucket — the largest held-out loss — is fixable by the possession COUNT alone, on dev+entreno only, and then score the chosen rule once on held-out. Moves open point 9 and feeds the G3 target.
- **why:** #68 (`docs/g3_touch_count_lever.md`, transcript `logs/touch_lever_stdout.txt`) established three things on committed artifacts: (1) emissions are already frame-accurate — signed delta to the nearest emission is median **−2 f** for dig/set/spike/overpass, only `serve` runs **+23 f** — so timing is not the bottleneck; (2) Layer 1 is degenerate — **157 of 185 (85 %)** accepted match contacts carry the single gesture `bump_set`, so the whole `dig`/`set`/`overpass`/`serve` decision is `ActionContextResolver._decide`, keyed on `_poss_touch`; (3) substituting the **real GT `touch_number`** into the unmodified `_decide` lifts label accuracy from **79/139 = 0.568** to **110/139 = 0.791** (+0.223) while `touch_number` itself is only **96/139 = 0.691** accurate — a bigger lever than any other measured on this GT (12 far serves +0.066, 13 overpass labels +0.071, 14 `set↔dig` swaps +0.077). Touch errors concentrate where the pipeline emitted FEWER contacts than the owner listed (11 points with `accepted >= GT`: 11/37 touch errors; 14 points with `accepted < GT`: **32/102**).
- **read first (nothing else):** AGENTS.md; this card; `docs/g3_touch_count_lever.md`; `src/recognition/action_context.py` (`_decide` at lines 175-219, `_poss_touch` at lines 127-135, the `cross_flip` block at lines 84-135, `ATTACK_ACTIONS` at line 30); `docs/g3_heldout_p9_p33.md` (the 0.590 baseline); `scripts/score_heldout_contacts.py` (IMPORT its matcher, never re-implement).
- **may create:** `scripts/probe_touch_rules.py`, `tests/test_touch_rules.py`, `docs/tc1_touch_rules.md`, `logs/tc1_report.md`
- **may modify:** `STATUS.md` (only the edits listed below)
- **must not touch:** `src/`, `ground_truth/`, `calibrations/`, `models/`, `output/`, and the held-out session `20290928_entreno_vall_dhebron` (held-out lock). No decode, no seek (§9), no new pipeline run, no GT edit. Do NOT add a task card, do NOT reorder cards, do NOT archive the Log. Do **NOT** edit `output/g3r1/match_bw03_diag.jsonl` or any `pipeline_output.json`.
- **inputs (all committed, already on disk):**
  - `output/g3r1/match_bw03_diag.jsonl` — the match dump; filter `stage == "accepted"` (185 rows). Fields to use: `frame`, `gesture`, `touch_number`, `near_net`, `team`, `ball_side`, `kind`, `rally_id`, `action`.
  - `ground_truth/20260920_match_contacts.json` — **the GT touch number lives in `points[].events[].touch_number`, NOT in `points[].contacts[]`** (the contacts block has no such key; reading the wrong one silently returns 0/139 — this trap bit the coordinator). Also `events[].final_action`, `events[].owner_side`, `events[].match_frame`. Held-out scope f5240–f26147, tolerance ±15 f.
  - dev + entreno: `output/g3/dev_verify_diag.jsonl` + `output/g3/dev_verify/pipeline_output.json` + `ground_truth/video_ari_joan_8_first_points_annotations.json`, and `output/g3/e{1..7}_diag.jsonl` with their GT via the same loaders `scripts/action_evidence.py` already uses.
- **steps:**
  1. **Gate G1 (reproduce #68 before touching anything).** Print, labeled `[measured]`: the accepted-candidate count (expect **185**); the Layer-1 gesture table (expect `bump_set` **157**, `attack` 16, `block` 12); the timing medians (expect dig/set/spike/overpass **−2 f**, serve **+23 f**); the held-out found-contact count (**139**); the **control** — a replay of the UNMODIFIED `_decide` with `behind_baseline=False`, `own_side_drive_block=False`, as-emitted touch — expecting **79/139 = 0.568**; the touch accuracy (**96/139 = 0.691**); and the GT-touch substitution (**110/139 = 0.791**). **Also print the shipped stream for reference: the dump's own `action` field scores 85/139 = 0.612 on the same GT, and the 207-action `pipeline_output.json` scores 83/141 = 0.589.** If the 185/157/139/96/110 numbers differ, **STOP and report**. **REQUIRED CAVEAT, already established (do not re-investigate, do not try to fix):** the `accepted` rows carry **no `behind_baseline`** field (0 of 185), so an offline replay CANNOT reproduce the shipped stream — fidelity is **168/185**, and it scores **0/12 on the serves** against the dump's own 7/12. The replay control is therefore 0.568 *by construction*, and 0.568 is **NOT the production baseline** (production is 0.612). This is why the gate below is stated as a **gain over the replay control**: so the baseline label cannot change the verdict.
  2. **Characterize the touch errors before designing anything.** For the 43 wrong-touch found contacts, print the full local context from the dump (its own `gesture`/`team`/`ball_side`/`kind`/`near_net`, and the previous and next accepted contact of the same `rally_id` with their `team`s) plus the GT touch number. Bucket them: `previous_contact_missing` (no accepted contact between the GT point's previous event and this one), `team_change_not_reset` (the GT touch is 1 but the emitted count continued), `attack_not_reset` (GT 1 after a GT 2/3 that went over), `over_counted` (emitted > GT), `under_counted` (emitted < GT). Report the bucket sizes — **this table is the deliverable's centre**, so do not skip it to get to the rules.
  3. **The offline rule search — dev + entreno ONLY.** Implement candidate touch-count rules as pure functions over the accepted-contact list, replayed through the **unmodified** `ActionContextResolver._decide` (import it; never copy it). Call it as `_decide(gesture, touch, near_net, behind_baseline=False, rally_start=False, next_contact, frame, own_side_drive_block=False)` — **`behind_baseline` and `own_side_drive_block` are NOT recoverable from the dump, so they are fixed `False` in every arm including R0**; state that in the report as the replay's known limit and do not treat the resulting serve loss as a finding. At minimum:
     - **R0** the current behaviour (the control: the emitted `touch_number`);
     - **R1** reset on ANY `team` change (not only the would-be-3rd+ `cross_flip` gate);
     - **R2** R1 + reset after any attack gesture (`attack`/`block`);
     - **R3** R2 + reset when `rally_id` changes;
     - **R4** R3 + a `ball_side` cross check when `ball_side` is present (abstain where it is `None`, which is 64 of 185).
     Report per rule, on dev and on each of e1–e7: touch accuracy, label accuracy, and the per-class confusion. **Choose the rule on dev+entreno ONLY**; never on the 139 held-out rows, and never re-choose after seeing held-out.
  4. **Gate G2 (held-out, ONE shot, after step 3 is written down).** Score the chosen rule once on the held-out 139 and print: touch accuracy, label accuracy, and the class-accuracy delta vs the 0.568 control. Report the number whatever it is.
  5. **The entreno regression arm (the goal's own constraint).** For each of e1–e7, report the `evaluate --ignore-player` F1 the chosen rule would give, using the recorded baseline from STATUS *Learnings* (**e1 0.706, e2 0.571, e3 1.0, e4 0.933, e5 0.923, e6 0.933, e7 0.75**). This is an OFFLINE replay, so state plainly that it is an approximation and that the goal's "≥ 90 % on the drills" can only be *confirmed* by a real run — which this card does not do.
  6. **State whether the required follow-up is a `src/` change**, and if so say so explicitly as the next step (a tier-2 architect call, not a worker), including the one-line mechanism the data supports.
  7. Write `docs/tc1_touch_rules.md` and `logs/tc1_report.md`; `venv/bin/python -m pytest tests/ -o addopts="" -q` green (baseline **1286**); report the actual count.
- **pre-registered decision (fixed; no rule may be added, dropped or re-parameterised after the held-out score is seen):**
  - All thresholds are **gains over the replay control R0 = 79/139 = 0.568**, so they are identical to the bars as first written (0.700 / 0.650 absolute) and cannot be moved by which baseline is quoted.
  - **PASS = `TOUCH_COUNT_LEVER_CONFIRMED`** if the chosen rule (i) reaches held-out label accuracy **≥ 0.700** (i.e. ≥ **+0.132** over R0, which is 59 % of the +0.223 ideal substitution lift), AND (ii) keeps every entreno replay within **±0.01** of its recorded F1, AND (iii) is chosen on dev+entreno only. Then the next card is the **architect call for the `src/` touch-count change** — the coordinator writes it.
  - **PARTIAL = `TOUCH_COUNT_LEVER_PARTIAL/<accuracy>`** if (i) reaches ≥ **0.650** (≥ +0.082) but < 0.700 with (ii) and (iii) intact. Then the next card is a second diagnose pass on the residual `overpass`/`serve` confusions, not a `src/` change.
  - **FAIL = `TOUCH_COUNT_LEVER_REFUTED/<accuracy>`** if (i) < 0.650, or (ii) breaks any entreno replay, or (iii) cannot be satisfied. Then the count is not the lever after all and the label bucket needs a different diagnosis.
  - **Additionally report, without gating on it** (it is where the replay IS faithful): the same three arms on the **127 non-serve** contacts, where R0 = 79/127 = 0.622 and the GT-touch arm = 110/127 = **0.866**. This is the cleaner statement of the lever and is what the architect call will be sized against.
  - Report the token as `touch_rule_gate = <token>` in all cases, whatever it is.
- **deliverables:**
  - `scripts/probe_touch_rules.py` — imports `ActionContextResolver` and the existing matcher; imports NO `cv2`; no decode; prints every number the steps require; exit 2 on FAIL.
  - `tests/test_touch_rules.py` — pin the no-`cv2`/no-seek rule, the step-1 G1 numbers, the error buckets being deterministic, each rule's reset semantics on synthetic sequences, and the verdict truth table. Expect roughly +20 tests.
  - `docs/tc1_touch_rules.md`, `logs/tc1_report.md`.
- **STATUS edits when done:** open point 9 — append a `#69:` line with the gate token, the touch accuracy, the label accuracy and the bucket sizes; *Where we are* *Active next* item 0 — replace with `TC1 DONE (#69): <token> — <the numbers>` and name the next task (the architect call for the touch-count change, or a second diagnosis); *Last updated* — one-line refresh; the Session index — one line; add one *Learnings* line if a durable fact emerged (e.g. the `events` vs `contacts` GT touch-number trap). Do **NOT** write a new task card and do NOT reorder the cards; do NOT archive the Log.
- **stop and ask if:** step 1 does not reproduce #68's numbers; the GT `touch_number` cannot be read from `points[].events[]`; the dev/entreno dumps are missing or lack `stage == "accepted"` rows; or any step would require touching `src/`, re-running the pipeline, or decoding video.
- **est. cost:** ~45 min, no decode, 0 pipeline minutes.

### CARD PG2 — RE-TEST the point map with a pairing-independent metric: is its opener serve-anchored, or was PG1's "uniformly late" a pairing artifact? no `src/` change
- **status:** DONE (#67): `point_map_alignment = PG1_VERDICT_IS_A_PAIRING_ARTIFACT` — PASS. See *Active next* item 0.
- **type:** measurement (diagnose-only)
- **goal:** replace PG1's pairing-dependent verdict with a pairing-independent one, and decide whether SR4-FAR is blocked or merely mis-keyed. Moves open point 22 and 21.3.
- **why:** the coordinator's step-4 review of #65 found that the headline `point_map_gate = REFUTED/1` is decided by PG1's **ordinal pairing** (GT point *P* ↔ pipeline point *P−1*). With 31 windows for 33 points, any skipped GT point shifts every later pair by one, accumulating the +6…+3153 f spread PG1 read as "uniformly late". Re-measured on the same committed artifacts (`docs/pg1_correction.md`, `logs/pg1_correction_stdout.txt`): pairwise-independent **14 of 31** window starts fall within ±15 f of a GT serve vs a Monte-Carlo chance of **1.21 of 31** (33 serve anchors cover 3.92 % of frames), median offset **−6 f**; far serves sit **at** a window start (**11 of 17**) while near serves sit **inside** a window (**14 of 16**). PG1's gate is not wrong arithmetic — it answers a question about ordinal correspondence, not about frame alignment.
- **read first (nothing else):** AGENTS.md; this card; `docs/pg1_correction.md`; `docs/point_map_alignment.md` §5; `scripts/score_point_map.py` (IMPORT it, never re-implement); `scripts/probe_point_map.py`; `output/pm1/probe.json` (the parity target, unchanged).
- **may create:** `scripts/score_point_map_alignment.py`, `tests/test_point_map_alignment.py`, `docs/point_map_seam.md`, `logs/pg2_report.md`
- **may modify:** `STATUS.md` (only the edits listed below); `docs/point_map_alignment.md` (ONLY an appended `## 7. Correction (#66/#67)` section that points at `docs/point_map_seam.md` — do NOT rewrite §1-§6, they are the #65 record)
- **must not touch:** `src/`, `ground_truth/`, `calibrations/`, `models/`, `output/`, and the held-out session `20290928_entreno_vall_dhebron` (held-out lock). No decode, no seek (§9), no new pipeline run, no GT edit. Do NOT add a task card. Do NOT change `scripts/score_point_map.py` — PG1's committed numbers must stay reproducible.
- **steps:**
  1. **Gate G1 (reproduce the correction):** `venv/bin/python scripts/score_point_map_alignment.py` prints, labeled `[measured]`: (a) the **pairwise-independent** count of pipeline window starts within ±15 f of ANY GT serve (expect **14 of 31**); (b) the same count at ±30 and ±60 f; (c) the Monte-Carlo chance baseline for the same count (seed a fixed RNG, ≥ 10 000 draws of 31 uniform starts over `[0, video.total_frames]`, tolerance ±15) — expect **≈ 1.2 of 31**; (d) the **frame-coverage** fraction of the ±15 f serve balls (expect **3.92 %**); (e) the **nearest** offset per GT serve (sign-free) and its median (expect **−6 f**). If (a) is not 14 of 31 or (e) is not −6 f, **STOP** and report the discrepancy — do not adjust anything.
  2. **Gate G2 (G2 parity with #65/#64, decide nothing):** the new script must reproduce PG1's ordinal numbers exactly when asked for the ordinal view — `start_hits_within_15f` **1 of 33**, `offsets_nonnegative` **31 of 31**, offset min/max/median **+6 / +3153 / +1700 f** — by importing `score_point_map`'s functions, not by recomputing them. A mismatch means the two tools disagree: report, do not re-tune.
  3. **The monotone alignment (the pairing-independent pair view):** order-preserving dynamic-programming alignment of the 31 window starts to the 33 serve frames, with a skip cost swept over **60 / 120 / 240 f**. Report, per skip cost: the pair count, the count of pairs within ±15 f, the offset min/max/median, and the unmatched windows/serves. **Expect stability at 14 of 27-28 pairs and median −6 f.** A pairing whose result changes materially with the skip cost is not a result — report that as the finding.
  4. **The seam measurement (#64's gap claim, re-scored):** per GT serve, report the signed offset to the nearest window **start** and to the nearest window **end**, split by side; and classify each serve as `at_seam` (nearest start within ±15), `inside_window`, or `in_gap`. State plainly whether far serves live *at the seam* (PG1's §5 said "in the gaps") — this wording is the deliverable's point.
  5. **The far-record consequence, scored but NOT tuned:** with a narrow `far_flight` event (`width_start <= 28`, the card's fixed cut — do NOT sweep it) whose `onset_frame` lies within ±10/±15/±20 f of a window **start**, report: claims, far serves hit (of 17), near serves misclaimed (of 16), unanchored claims. Expect **11/17 far, 0/16 near, 5 unanchored** at ±10 and ±15. Label the whole table **IN-SAMPLE** and state that it is a re-test target, not a shippable rule (STOP list, AGENTS.md §5).
  6. Write `docs/point_map_seam.md` (steps 1-5 + one paragraph: **is the opener serve-anchored, or late?** — decided by the chance baseline, not by the ordinal sign) and `logs/pg2_report.md`.
  7. `venv/bin/python -m pytest tests/ -o addopts="" -q` green; report the actual count (baseline **1237**).
- **pre-registered decision (fixed; no second pairing, no re-derived offset, no tolerance or width-cut change):**
  - **PASS = `PG1_VERDICT_IS_A_PAIRING_ARTIFACT`** if (i) window starts within ±15 f of a GT serve ≥ **10 of 31**, AND (ii) that count exceeds the Monte-Carlo chance baseline by ≥ **5×**, AND (iii) the monotone alignment stays at ≥ **10** pairs within ±15 f across all three skip costs. Then SR4-FAR is **mis-keyed, not blocked**: the coordinator cards the far-serve rule built on window starts (pre-registered on the dev half, scored once on the held-out half).
  - **FAIL = `PG1_VERDICT_STANDS`** if any of (i)-(iii) misses, reported as `point_map_alignment = REFUTED/<number>`. Then the starts are not serve-anchored after all, PG1's reading is upheld, and SR4-FAR stays blocked on open point 22.
- **deliverables:**
  - `scripts/score_point_map_alignment.py` — imports `score_point_map` (and through it `probe_point_map`); imports NO `cv2`; prints every number the steps require; exit 2 on FAIL.
  - `tests/test_point_map_alignment.py` — pins: no `cv2`/seek; the step-1 numbers on the real artifacts; the chance baseline is deterministic under its seed; the monotone alignment is order-preserving; the verdict truth table. Expect roughly +20 tests.
  - `docs/point_map_seam.md`, `logs/pg2_report.md`, plus the appended `docs/point_map_alignment.md` §7 pointer.
- **STATUS edits when done:** open point 22 — append a `#67:` line with the pass/fail token, the pairwise-independent count, the chance baseline and the far/near seam split; open point 21 — append the same one line; *Where we are* *Active next* item 0 — replace with `PG2 DONE (#67): <token> — <headline numbers>` and name the next task (the far-serve window-start rule card, or SR4-FAR stays blocked); *Last updated* — one-line refresh; the Session index — one line. **Do NOT write a new task card** and do NOT reorder the cards; do NOT archive the Log.
- **stop and ask if:** step 1's (a) or (e) does not reproduce; the two tools disagree on the ordinal view (G2); `serve_events` far_flight events are absent from `pipeline_output.json`; or any step would require touching `src/` or running the pipeline.
- **est. cost:** ~40 min, no decode, 0 pipeline minutes.


### CARD PG1 — POINT-MAP SCORING: the segment-start metric on the ground truth you already gave, no `src/` change
- **status:** DONE (#65): `point_map_gate = REFUTED/1` — SUPERSEDED by #66/#67 (PG2): the verdict is a pairing artifact. Not re-runnable.
- **status (after #67):** DONE — `point_map_alignment = PG1_VERDICT_IS_A_PAIRING_ARTIFACT` (PASS on all three criteria). Unrun: nothing.
- **type:** measurement (diagnose-only)
- **goal:** put the point map behind a pass/fail gate using the owner's existing ground truth. Moves open point 22 and 21.3; it is the gate SR4-FAR waits on.
- **why:** #64 measured that `game_state.points` opens each point **+6 … +3153 f AFTER its own serve on all 31 pairs** (one-signed, uniform), 31 points vs 33 GT, and that this — not the serve signal — blocks the far-side serve record (16/17 detected, 294 false serves unbound; best binding 11/17 with 35 FP). `docs/pm1_point_map.md`. The owner approved changing the map in principle (#64b) but it has never been validated. **The GT start frames EXIST** — see the correction in step 1.
- **read first (nothing else):** AGENTS.md; this card; `docs/pm1_point_map.md` §3 and §7; `scripts/probe_point_map.py` (import its loaders and `alignment` logic, never re-implement); `scripts/evaluate_match_points.py` (`load_match_gt` / `load_pipeline_points`); `ground_truth/20260920_match_contacts.json` — `points[].contacts[*].match_frame` is owner-dictated.
- **may create:** `scripts/score_point_map.py`, `tests/test_point_map_score.py`, `docs/point_map_alignment.md`, `logs/point_map_report.md`
- **may modify:** `STATUS.md` (only the edits listed below)
- **must not touch:** `src/`, `ground_truth/`, `calibrations/`, `models/`, `output/`, and the held-out session `20290928_entreno_vall_dhebron` (held-out lock). No decode, no seek (§9), no new pipeline run, no GT edit. Do NOT add a task card.
- **steps:**
  1. **CORRECTION — this card's earlier version wrongly said the GT start frames were missing; they are not, and the owner pointed it out (2026-10-02).** In `ground_truth/20260920_match_contacts.json`, **all 33 points carry exactly one `serve` contact, and in every point the serve IS the earliest contact** (verified by the coordinator: 0 of 33 exceptions; `n_contacts` min 1). So the owner's GT already carries a per-point start frame — the serve frame, +-15 f by construction. **Use that as the anchor.** **Explicitly NOT the anchor:** `points[].match_start_frame`, which all 33 carry as `window_source: "episode_map_emission_window"` + `window_is_prediction: true` (a pipeline prediction; measured spread vs the first owner contact -1723 … +746 f), and **not** `ground_truth/gt_point_start_end.txt` (the GAME-STATE VIDEO's GT — `video_entreno_game_state.mp4`, 13 mm:ss pairs, a different video). If step 1 does not reproduce (any point without exactly one serve, or a serve that is not the earliest contact), **STOP** and report.
  2. **Gate G1 (metric definition, then the run):** `venv/bin/python scripts/score_point_map.py` prints, for each GT point *P* (1..33): the serve frame, the pipeline point paired with it (same ordinal), its `start_frame`, and the signed offset `pipeline start_frame - serve_frame`; then the aggregate **offset min / max / median**, the count of points whose offset is **>= 0** (must be 31 of 31 per #64 — if not, #64 is wrong, and that IS the finding), and the **within-tolerance start-hit count** = points whose pipeline `start_frame` is within **+-15 f** of the serve frame. This is the headline number; the pipeline emits starts ~+6 … +3153 f late, so a low count is the EXPECTED reading and is **not** a reason to stop.
  3. **Gate G2 (parity, decide nothing):** the paired count is **31**, `gt_points_without_pipeline_point == [32, 33]`, and the per-point offsets match `output/pm1/probe.json`'s `alignment` list exactly (that file is #64's committed output; a mismatch means the two tools disagree — report it, do not re-tune).
  4. **Gap-side measure (the #64 claim, scored):** for each of the 33 GT points report whether its serve frame falls inside ANY pipeline window and inside the inter-point gap preceding the point that holds its own contacts, so #64's "far 2/17 in-window vs near 14/16" split becomes a pinned number rather than prose. Every number labeled `[measured]`.
  5. Write `docs/point_map_alignment.md` (the tables + one paragraph: is the map **one point behind**, **uniformly late**, or **noise**? — the same three readings #64 listed, decided by the offset distribution's sign) and `logs/point_map_report.md`.
  6. `venv/bin/python -m pytest tests/ -o addopts="" -q` green; report the actual count (baseline **1214**).
- **pre-registered decision (the gate, fixed):**
  - **PASS** = `start_hits_within_15f >= 20` of 33 AND `offsets_nonnegative == 31` of 31 paired. Then the map's alignment is measured and an architect card for a corrected opener is justified; the coordinator cards it next.
  - **FAIL** = anything else, reported as `point_map_gate = REFUTED/<number>`; the map's STRUCTURE (not its offset) is then the suspect, and SR4-FAR stays blocked with the blocker restated. **Do not try a second pairing (ordinal, nearest, ordinal+1), a re-derived offset, or a tolerance change.**
- **deliverables:**
  - `scripts/score_point_map.py` — imports `probe_point_map`'s loaders; imports NO `cv2`; prints every number the steps require.
  - `tests/test_point_map_score.py` — pins: no `cv2`/seek; the step-1 anchor rule (one serve per point, serve is earliest) on the real GT; the pairing is ordinal; the aggregates exist; the verdict truth table.
  - `docs/point_map_alignment.md`, `logs/point_map_report.md`.
- **STATUS edits when done:** open point 22 — append a `#65:` line with `start_hits_within_15f`, `offsets_nonnegative`, the offset triple and the in-window/gap split; open point 21 — append the same one line; *Where we are* *Active next* item 0 — replace with `PG1 DONE (#65): <PASS|FAIL> — <headline numbers>` and name the next task (architect card for the opener, or SR4-FAR stays blocked); *Last updated* — one-line refresh; the Session index — one line. **Do NOT write a new task card** and do NOT reorder the cards; do NOT archive the Log.
- **stop and ask if:** step 1's anchor rule does not reproduce; `game_state.points` or the GT contacts are absent; the two tools disagree on a paired offset (G2); or any step would require touching `src/` or running the pipeline.
- **est. cost:** ~30 min, no decode, 0 pipeline minutes.

### CARD PM1 — the point-map probe: why 0 of 17 far serves fall inside their own point window, no `src/` change
- **status:** DONE (#64): `FAIL=blocked` — UNBOUND (frame, side) **16/17 far hits
  with 294 false serves** (bar >= 15/0); binding rule (iii) gap **11/17 with 35 FP**,
  (ii) first-after **16/17 with 288 FP**, (i) contain **10/17 with 253 FP**. Neither
  bar met, so **SR4-FAR is BLOCKED on open point 22**; the signal is complete (16/17)
  and the point map is the lever. **Do NOT re-run**; the probe's verdict is pinned in
  `tests/test_point_map.py`.
- **type:** measurement (diagnose-only)
- **goal:** decide whether SR4-FAR (the far-side serve record) is a one-rule job that bypasses the point map, or is blocked on open point 22 (episode→point map). Moves open point 30.
- **why:** the architect call (`docs/sr4_architect_call.md`, #63) refuted SR4 as specified and named the root cause: `game_state.points` has **31** entries against 33 ground-truth points, and **0 of 17 far serves fall inside their own point window** — each point's `start_frame` sits **1–1466 f AFTER its own serve** (the session-56 backdated rally onset). Meanwhile the far-side *detection* is already solved: ball width at flight onset is **14–23 px at all 17 far serves** vs **39–52 px** at the 3 near serves that have a flight event, a plateau at any cut in **26–32 px** giving **far 16/17, near 0/16 misclaimed**. If the point map can be bypassed, SR4-FAR is one rule; if not, it waits on open point 22 and the next ranked task changes.
- **read first (nothing else):** AGENTS.md; this card; `docs/sr4_architect_call.md` §2 and §3; `scripts/score_serves.py` (only `match_split`, `serve_record_candidates`, `classify_false_positives` — IMPORT them, never re-implement); `src/analysis/game_state_manager.py` lines 1–30 and `_finalize_group` (to name the mechanism you are measuring, not to change it).
- **may create:** `scripts/probe_point_map.py`, `tests/test_point_map.py`, `docs/pm1_point_map.md`, and `logs/pm1_report.md`
- **may modify:** `STATUS.md` (only the edits listed below)
- **must not touch:** `src/`, `ground_truth/`, `calibrations/`, `models/`, `output/`, and anything from the held-out session `20260928_entreno_vall_dhebron` (held-out lock). No `cv2` import, no decode, no seek, no new pipeline run. Do not add a `subagent` task card.
- **steps:**
  1. `venv/bin/python scripts/probe_point_map.py` — the probe MUST, on the committed artifacts only: (a) load `output/20260920_match_ari_joan_lost/pipeline_output.json` and `ground_truth/20260920_match_contacts.json`; (b) for each of the 33 GT serve contacts print the frame, side, the nearest pipeline point window `[start_frame, end_frame]`, the signed offset `start_frame − serve_frame`, and whether the serve is inside any window; (c) print the pipeline point count (31) and the GT point count (33) and the two frame lists side by side; (d) count how many of the 33 serves fall inside their own GT point's implied window (serve to next GT serve) vs inside a pipeline window; (e) for each pipeline point, report `start_frame − previous_point.end_frame` (the inter-point gap) and whether a GT serve lies inside that gap.
  2. **Gate G1 (baseline reproduction):** the probe MUST first reproduce `venv/bin/python scripts/score_serves.py --detail` → `near_hits 8, near_n 16, far_hits 0, far_n 17, false_positives 12` (the #56/#62 recorded baseline) and its own recount → near 8/16, far 0/17. If either differs, **STOP** and report the difference; do not proceed.
  3. **Gate G2 (the width plateau, re-derived, decide nothing):** recompute the `far_flight.width_start` band from the same artifact: the max width at any of the 17 GT far serves and the min width at any of the 16 GT near serves within ±15 f, at width cuts 26, 28, 30, 32. Report far-claimed and near-misclaimed counts at each. It must reproduce 16/17 far and 0/16 near at every cut in [26, 32]. If not, **STOP**.
  4. **The bypass test (the actual decision).** Emit candidate far-serve records as **(frame, side) only — never a point number** — for every `far_flight` event with `width_start <= 28`, and score them with `scripts/score_serves.py`'s own matcher (`match_candidates`, imported). Report: far hits, near hits, false positives, and the record count. Then repeat with ONE point-binding rule at a time and report each: (i) bind to the pipeline point whose window CONTAINS the event; (ii) bind to the pipeline point whose `start_frame` is the FIRST one after the event; (iii) bind to the gap `[prev_end, start]` of rule (ii). For each, report far hits / false positives / points covered. **Decide nothing here** — the pre-registered rule in the next field does that.
  5. Write the numbers and the mechanism reading (does `game_state_manager._finalize_group`'s backdating explain both the 31-vs-33 count and the offsets?) into `docs/pm1_point_map.md`, marking every claim **[measured]** or **[inferred]**. Report counts, never rates.
  6. `venv/bin/python -m pytest tests/ -o addopts="" -q` must be green at 1191 + your new tests; report the actual number.
- **pre-registered decision (the point-map question, not re-tunable; `far_flight.width_start <= 28` is FIXED and imported, never re-tuned):**
  - **PASS (bypass)** = at least **15 of 17** far hits with **0 new false serves** in the UNBOUND (frame, side) form, AND at least one of the three binding rules (i)/(ii)/(iii) reaching **>= 12 of 17** far hits with **<= 3 false positives**. Then SR4-FAR proceeds as a one-rule post-hoc record and the coordinator cards SR4-FAR immediately.
  - **FAIL (blocked)** = anything else, including: unbound far hits < 15, any binding rule under 12 of 17, or any binding rule with > 3 false positives. Report SR4-FAR as BLOCKED on open point 22 and say which lever the evidence points at (point map vs binding rule). **Do not try a fourth binding rule, a width threshold, or a tolerance change.**
  - Sensitivity values (other cuts in 26–32, other offsets) MAY be reported, but they decide nothing.
- **deliverables:**
  - `scripts/probe_point_map.py` — no `cv2` import (pin with an `ast` test); imports `GAP_SERVE_MIN`, `score_serves` functions; prints every number the fields above require.
  - `tests/test_point_map.py` — pins: no `cv2`/VideoCapture/seek; `GAP_SERVE_MIN` not redefined; the 31-vs-33 count and the 0-of-17 inside-window count as literals; the width plateau edges.
  - `docs/pm1_point_map.md` — the per-serve offset table, the gap table, the bypass-vs-binding comparison, and the PASS/FAIL verdict with the numbers.
  - `logs/pm1_report.md` — the long report.
- **STATUS edits when done:** open point 30's #63 block — add one line `#64: PM1 <PASS=bypass|FAIL=blocked> — <the three numbers>`; *Where we are* *Active next* item 1 — replace with `PM1 DONE (#64): <verdict>` and name the next task (SR4-FAR card, or open point 22); *Last updated* — rewrite the first paragraph to the PM1 verdict; the Session index — one line. **Do NOT write a new task card** and do NOT reorder the cards; do NOT archive the Log.
- **stop and ask if:** a GT serve frame is absent from `pipeline_output.json`; `score_serves.py --detail` no longer prints the G1 baseline; `far_flight` events are missing `width_start`; `game_state.points` is absent; the held-out session is the only place a number can be found; or any step would require touching `src/`.
- **est. cost:** ~30 min, no decode, 0 pipeline minutes.

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
- **status:** **DONE (#62+, delegated worker; `docs/sr4a_near_openings.md`, open
  point 30)** — G1 reproduced on both arms; 8 near misses = 2 mislabeled_opener +
  3 not_opener + 3 not_emitted. **G2: SR4's near side PROCEEDS (5 of 8 repairable,
  rule ≥4); M-b REOPENED as a fresh architect call only (3 never produced, 2
  coasting, rules ≥3 AND ≥2); trap 0.** Retained below for provenance — do NOT
  re-run.
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
      **[#62 +1: SR4a DONE (`docs/sr4a_near_openings.md`, `scripts/probe_near_openings.py`,
      `logs/sr4a_report.md`). G1 reproduced on both arms: near 8/16, far 0/17, 12 false
      serves, drills e2-e7 3/5. The 8 near misses bucket into 2 `emitted_mislabeled_opener`
      + 3 `emitted_not_opener` + 3 `not_emitted`.]**
      - **SR4a G2 verdict 1 — SR4 near side PROCEEDS after the fact: 5 repairable of 8**
        (rule >= 4). The 5 are three different defects: wrong label on a correctly
        opened rally (P9 `spike`, P10, P11), a same-side `serve` emitted **25 f**
        before the GT frame (P33, the scorer's own `serve_outside_tolerance`), and a
        rally-boundary case where the window opener sits 9 actions earlier (P12).
      - **SR4a G2 verdict 2 — M-b is REOPENED as a fresh architect call (NOT a build):
        3 never produced and 2 of them coasting** (rules >= 3 AND >= 2). The two
        coasting reads are P5 f2575 and P7 f3747, lowest-foot same-team track
        `predicted: true`; the other 6 misses have a `predicted: false` same-team
        track at the GT frame. **`output/sr1c/match_full_diag.jsonl` has NO recorded
        arm**, so the reopen call must re-run with the arm named. SR4 still goes first
        (no `src/` change).
      - **SR4a trap guard `far_unseen_near_reception_first` = 0** of 17 far serves, so no
        onset-side guard is demanded — but 12 of 15 near onsets sit 10-19 f BEFORE the
        serve, so the guard's +-15 f onset window is narrow by construction.
      - **SR4a design constraint (inferred, not a rule):** only **4 of the 8 hits** have
        a `serve` as their window's opener, and **6 of the 12 false serves sit inside a
        near-miss window** (5 of them as its first action). SR4 must key on the
        same-side contact within tolerance, not on the window opener alone. The chasm
        rule (`GAP_SERVE_MIN`, imported, never re-tuned) rejects only **1 of 12** false
        serves.
      **[#63: SR4 REFUTED AS SPECIFIED (architect call + coordinator re-measurement,
      `docs/sr4_architect_call.md`). This supersedes the "Next = card SR4a; SR4 still
      goes first" line above.]**
      - **NEAR has a hard coverage ceiling of 13/16** [measured]: three near serves have
        NO action on the serving side within +-15 f of GT (P5 f2575 nearest -81 f
        `overpass` A, P7 f3747 nearest -108 f `dig` A, P24 f18135 nearest +29 f `dig` B).
        The planned bar of 15/16 is above the ceiling -> **SR4-NEAR is not built as a
        15/16 target**; it waits on perception (M-b fixes P5/P7 at best; P24 has a real
        detected player and no own-side action, so M-b alone does not reach even 13/16).
        **[OWNER-RATIFIED 2026-10-02: the near-side bar is 13/16 — the measured ceiling —
        not 15/16.]** SR4-NEAR's remaining requirement is therefore perception-only: the
        3 uncovers (P5, P7, P24) must produce an own-side action within +-15 f; no
        post-hoc rule can do it.
      - **The far-side side signal is the strongest measured in the project and was NOT
        in the plan** [measured]: ball width at flight onset is **14-23 px at all 17 far
        serves** and **39-52 px** at the 3 near serves that have a flight event (13 of 16
        have none within +-15 f). A cut anywhere in the **26-32 px plateau** claims
        **far 16/17 with 0/16 near misclaimed**. Keep the cut PER SESSION (camera-scale
        biased, AGENTS.md §5), never frozen as a constant.
      - **ROOT CAUSE of the record's failure is the POINT MAP, not the signal** [measured]:
        **0 of 17 far serves fall inside their own point window.** `game_state.points` has
        **31** entries vs 33 GT points, and each point's `start_frame` sits **1-1466 f
        AFTER its own serve** (the session-56 backdated rally onset). Binding in-window
        gives far 9-11/17 with 2-8 false records; unscoped there are **432** narrow
        candidates for 33 serves; and every suppression rule tried (drop on next-action
        within 15/30/60/120 f) trades true serves for false ones ~1-for-1 (far hits fall
        16 -> 8 -> 2 -> 0 while false records fall 416 -> 256 -> 183 -> 141).
      - **Decisions:** SR4-NEAR parked on perception; SR4-FAR becomes a detection-only
        result until the point map is fixed or bypassed; P12 stays a rally-boundary defect
        (same root cause); the +-15 f tolerance stays (P33's -25 f must NOT be admitted —
        it would also admit the far false serve f8534 at +16 f); wrong-label repairs
        (P9/P10/P11) do NOT violate the STOP list because a serve RECORD never mutates
        `actions_pass2` and never relabels the reception.
      - **Next = the POINT-MAP PROBE** (post-hoc, no `src/`, no decode): per-serve offset
        to its own window, and whether the 31-vs-33 mismatch and the backdated onsets
        have one cause. Then SR4-FAR as a record; SR4-NEAR only with perception.
      - **#64: PM1 `FAIL=blocked`** (`docs/pm1_point_map.md`, `logs/pm1_report.md`,
        `scripts/probe_point_map.py`; artifacts unchanged). UNBOUND (frame, side) far hits
        **16/17** with **294** false serves; best binding rule (gap) **11/17** with
        **35** false serves; first-after rule **16/17** with **288** false serves.
        **The point map is the lever, not the binding rule, and not the width cut.**
        Reproduced: 31 pipeline points vs 33 GT points; **0 of 17 far serves inside
        their own window**; ordinal-pairing offset one-signed **+6 … +3153 f** on all
        31 pairs (map uniformly LATE, not noisy — the #63 "1-1466 f" figure is the
        *nearest-window* offset, extreme -731 f at P32); **2 of 17 far serves** inside
        any window vs **14 of 16 near**; **16 of 33 serves** in inter-point gaps;
        29 of 30 gaps clear `GAP_SERVE_MIN` (143), so the chasm rule selects nothing
        here. [inferred] `_finalize_group` backdates the episode onset to a flight
        burst before the rally's first action, so the point opener precedes its own
        serve; the 31-vs-33 shortfall is P32/P33 and is unresolved between two
        `game_state_manager` causes (below `point_min_actions` vs merge-then-split) —
        deliberately NOT separated by this card. **Constraint handed to open point
        22: the opener must move to the serve / its rally**; a map that opens there
        makes rule (i) natural and is the only shape where a per-point record is both
        complete and precise. Width plateau survives as a Learning (detection only).
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

22. **Far-side serves** — **[#67, PG2 DONE — `point_map_alignment = PG1_VERDICT_IS_A_PAIRING_ARTIFACT`: SR4-FAR is MIS-KEYED, not blocked. Pairwise-independent on the same artifacts: 14 of 31 window starts within ±15 f of ANY GT serve vs 1.21 of 31 Monte-Carlo chance (20 000 draws, seed 20261002, serve balls cover 3.93 % of frames) = 11.56× (bar ≥ 5×); monotone order-preserving DP keeps 14 pairs within ±15 f at every skip cost 60/120/240 f (27-28 pairs, median −6/−8 f); PG1's ordinal numbers reproduce exactly (1 of 33, 31 of 31 non-negative, +6/+3153/+1700 f) and now decide nothing. Seam split: far 11/17 sit AT a window start, 0 in a window interior, 6 in a genuine gap; near 3/16 at a start, 11/16 inside a window — #65's "far 14/17 in the gaps" is a SEAM, not a gap. Step 5 narrow `far_flight` (`width_start <= 28`, fixed) keyed on window starts: 11/17 far, 0/16 near misclaimed, 5 unanchored at ±10 and ±15 f — IN-SAMPLE re-test target, NOT a shippable rule (STOP list, AGENTS.md §5). Card defect: 1(e) asks for a "sign-free" median of −6 f (impossible); −6 f is the nearest-boundary signed median (nearest-start signed −1 f, sign-free +17 f) and all three readings are serve-anchored (`docs/point_map_seam.md` §6, `logs/pg2_report.md`, `scripts/score_point_map_alignment.py` +49 pins, suite **1286**). The remaining work is the coordinator's far-serve rule keyed on window starts, not an opener re-tune.]** **[#55: SUPERSEDED by point 30. The far-serve contact chase is STOPPED, and its runway/structural evidence is reused as SR4 inputs. The '14/17 at zero FP' figure is IN-SAMPLE (swept on all 17); the held-out binding is 4/12.]** **[#53 SOLVED AS EVIDENCE: 14/17 at ZERO false
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
    **[#64: the episode->point map is now MEASURED as the blocker for the far
    serve, and open point 30's SR4-FAR waits on it.]** Measured over the 33 GT
    serves against `game_state.points`: **31 pipeline points vs 33 GT points**
    (P32/P33 have none), and under the only pairing the two vocabularies support
    (GT point *P* <-> pipeline point *P-1*) the offset `start_frame - own
    serve_frame` is **one-signed +6 f ... +3153 f on all 31 pairs** — the opener is
    uniformly LATE, not noisy, so **0 of 17 far serves (and 0 of 31 windows) sit
    inside their own window**. Only **16 of 33** serves fall inside *any* window,
    and the split is stark: **far 2 of 17** vs **near 14 of 16** — the far serves
    live in inter-point gaps (16 of 33), the near ones inside windows. Consequence
    for the serve record: the far-side *detection* is complete (ball width at
    flight onset **16-27 px** at every far serve vs **39-50 px** at the 3 near
    serves that have an event, plateau 26-32 px -> **16/17 far, 0/16 near
    misclaimed** at every cut), but **no binding rule makes it precise**: unbound
    16/17 with 294 false serves, in-window 10/17 with 253, first-start-after
    16/17 with 288, gap 11/17 with 35. **So the fix is HERE, not in the serve
    logic: move the point opener to the serve or to the rally it heads**
    ([inferred] from `_finalize_group`: the opener is a pre-serve flight burst,
    backdated after a quiet interval, and the point layer never sees a serve).
    Next = card for that; SR4-FAR is not buildable until it lands.
    **[#64b, OWNER 2026-10-02 — the point map MAY be changed, but only behind a ratified
    validation gate; the gate is the missing piece, not permission.]** What the owner
    was asked to decide had three parts, answered as follows: (1) *is the late opener a
    bug worth fixing* — YES in principle, since G1's critical path runs through this map
    (21.3 point winner -> 13 ace/assist/serve-error -> fantasy), but **the alignment has
    never been validated**, so "fix" is currently an unfalsifiable move;
    (2) *who fixes it* — tier-2 architect design + owner ratification, per AGENTS.md
    `src/` rules; (3) *what must stay true* — the action stream itself is untouchable,
    `actions_pass2` output is byte-identical, the practice drills must not move, and
    `game_state.points` count must not drift without an explicit owner call.
    **MEASURED THIS SESSION (the gate's shape):** `scripts/evaluate_match_points.py`
    against `ground_truth/20260920_match_points.json` (33 points, winners
    `BABABAABBBBAABAAAAABAABAAAAAABBAA`, side switches after [7,14,21,28]) prints
    **"Not scored ... segmentation_starts: requires owner-ratified frame anchors per GT
    point"** — i.e. the ONLY thing blocking a pass/fail gate on the point map is the
    absence of **owner-ratified per-point start frames**. It also reports
    **"Pipeline episodes: 0 (GAME_ON spans)"** (the CSV layer is not in this artifact,
    so the episodes~=rallies check is unavailable, not failed) and **confirmation ratio
    0.939** = 31/33 points, with the confirmed windows spanning f216-f25776 (last
    window 7.2 s / 5 actions, so P32/P33 are absent entirely, not truncated).
    **So the next task is a SCORER, not an owner pass and not new GT — CORRECTED BY THE
    OWNER 2026-10-02 ("the 33 points start with the start frame, which I already provided
    the GT").** The anchor exists: every one of the 33 GT points carries exactly one
    `serve` contact and in every point the serve IS the earliest contact, so the
    owner-dictated serve frame is the point's start frame (+-15 f by construction). What
    is missing is only the metric that compares it to `game_state.points`, which is why
    the evaluator keeps printing `Not scored`. CARD PG1 builds that scorer (post-hoc, no
    `src/` change); with it, #64's alignment becomes a pass/fail quantity and a
    point-map change becomes testable instead of unfalsifiable. Until PG1 lands SR4-FAR
    stays blocked and open point 30 stays where it is.
    **[#65, PG1 DONE — `point_map_gate = REFUTED/1` (`docs/point_map_alignment.md`,
    `logs/point_map_report.md`, `scripts/score_point_map.py`, `tests/test_point_map_score.py`;
    suite **1237** = 1214 + 23).** The anchor reproduced: all 33 GT points carry exactly one
    `serve` contact and the serve is the earliest contact, so the owner-dictated serve frame
    IS the per-point start frame (predicted `match_start_frame` never read). Ordinal pairing
    (GT P ↔ pipeline P-1): `start_hits_within_15f` = **1 of 33** (PASS bar >= 20; only P1, +6 f),
    `offsets_nonnegative` = **31 of 31 paired** (#64's sign confirmed), offset min/max/median
    = **+6 / +3153 / +1700 f** → reading **uniformly late**, 0 of 31 windows contain their own
    serve. G2 parity with `output/pm1/probe.json` PASS (0 offset mismatches). Gap side scored:
    serve inside any window **16 of 33** (far 2/17, near 14/16); inside any inter-point gap
    **16 of 33** (far 14/17, near 2/16); inside the gap immediately before its own holder
    only **1 of 33**. FAIL ⇒ the map's STRUCTURE is the suspect, not a constant offset;
    **SR4-FAR stays BLOCKED on open point 22** and the corrected-opener architect card is
    NOT justified by this run (that was the PASS branch).]
    **[#67, PG2 DONE — `point_map_alignment = PG1_VERDICT_IS_A_PAIRING_ARTIFACT`,
    PASS on all three pre-registered criteria (`docs/point_map_seam.md`,
    `logs/pg2_report.md`, `scripts/score_point_map_alignment.py`,
    `tests/test_point_map_alignment.py`; suite **1286** = 1237 + 49).** PG1's ordinal
    `REFUTED/1` is an artifact of its GT *P* ↔ pipeline *P−1* pairing, not of the video:
    pairwise-independent, **14 of 31** window starts fall within ±15 f of ANY GT serve
    (23/31 at ±30 f, 25/31 at ±60 f) vs a seeded Monte-Carlo chance baseline of
    **1.21 of 31** (20 000 draws, serve balls cover 3.93 % of frames) = **11.56×**;
    monotone order-preserving DP keeps **14 pairs within ±15 f at every skip cost
    60/120/240 f** (27-28 pairs, median −6 to −8 f). PG1's own numbers reproduce exactly
    (1 of 33, 31 of 31 non-negative, +6/+3153/+1700 f) and now decide nothing. Seam:
    far serves sit **AT a window start** (11 of 17 at_seam, 0 in a window interior,
    6 in a genuine gap), near serves **INSIDE** one (11 of 16) — so #65's "far 14/17 in
    the gaps" is a seam, not a gap. Step 5's narrow `far_flight` (`width_start <= 28`) keyed
    on window starts scores **11/17 far, 0/16 near misclaimed, 5 unanchored** at ±10 and
    ±15 f — **IN-SAMPLE, a re-test target, NOT shippable** (STOP list, AGENTS.md §5).
    **SR4-FAR is MIS-KEYED, not blocked**; the corrected-opener architect card is NOT
    justified either. Card defect logged: step 1(e) asks for a "sign-free" median of −6 f,
    which cannot be negative — −6 f is the nearest-**boundary** signed median (nearest-start
    signed −1 f, sign-free +17 f); all three readings are serve-anchored, so the verdict
    does not turn on it (`docs/point_map_seam.md` §6).**

21. **Owner's match-feedback backlog** (agreed order; GT exists for all).
    **[#42 order: (4) side-switch = S3, then (3) winner = S4 — both after S1's
    far-serve contact work so serve/reception contacts are real.]**
    (1) *Point count:* ball half SHIPPED (conf floors + v3); point-layer
    windows now binding at 31/33 — re-tune group_gap/contact_chain/confirm
    jointly on the game-state video + the 25.7fps match; emit every rally
    candidate with a confidence (no silent skips). Likely partly moot —
    verify the residual 2 misses aren't far-side-serve losses (→ 22).
    **[#65: the point-start half of (1)/(3) is now SCORED and REFUTED —
    `point_map_gate = REFUTED/1`: `start_hits_within_15f` = 1 of 33 (bar >= 20),
    `offsets_nonnegative` = 31 of 31, offset min/max/median = +6 / +3153 / +1700 f
    (uniformly late), 0 of 31 windows contain their own serve, GT P32/P33 have no
    pipeline point (`docs/point_map_alignment.md`). The window COUNT binds
    31/33, but the window STARTS do not, so re-tuning cannot reach the GT starts
    without moving the opener; SR4-FAR stays blocked on 22.]**
    **[#67: that "starts do not bind" reading is CORRECTED — it was PG1's pairing,
    not the map. Pairwise-independent: 14 of 31 window starts within ±15 f of ANY GT
    serve vs 1.21 of 31 chance (11.56×), median −6 f, stable 14/14/14 pairs across the
    skip-cost sweep; far 11/17 sit AT a start, near 11/16 INSIDE a window
    (`docs/point_map_seam.md`). So the starts ARE serve-anchored and re-tuning the
    opener is NOT the lever; SR4-FAR moves from blocked to MIS-KEYED (its rule still
    to be keyed on window starts, still off/IN-SAMPLE).]**
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

2.  **Side-change survival (player identity) — status: BUILT, awaiting the
    real-footage gate (#83).** Problem: labels mixed after side switches (#82's
    resolver had no team constraint, position continuity locked swaps in, and
    enrollment only ever saw squad 1 near / squad 2 far). #83 ships
    `TeamIdentityResolver` (orientation CUSUM + within-side slots + per-video
    calibrated evidence + learned second view), output labels only. Prior
    roster facts stand (full match: ids 1-4 only, swap-rate 0.00, 46
    resurrections, a mid-rally id hop f1250-1350 — the resolver is designed to
    absorb hops, not prevent them). **Next:** owner runs
    `scripts/probe_identity_switches.py <20260920 match> --contacts-gt
    ground_truth/20260920_match_contacts.json`; pre-registered reading: PASS =
    4/4 switch windows ok, 0 stray flips, orientation wrong at 0 GT contacts
    outside the first ~5 s after a switch, team-resolver action squad errors <
    legacy's, contact-sheet rows one person each. Then entreno A/B (§1) and
    vall_dhebron only after its held-out lock is lifted. History:
    `docs/history/status_where_we_are_archive.md` (#83 section).

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
    **[#75, `logs/reach_scale_report.md`: the reach-gate part is now MEASURED
    and the asymmetry is `NOT SCALE-EXPLAINED` — the 140 px constant IS
    side-blind (far 1.359 m vs near 1.014 m, 1.341x) but that is only ~0.34 m,
    while the 7 rejections are 1.382-4.540 m against a near-side GT-contact
    max of 0.576 m (Cliff's delta +1.000). The smallest, e2 f403 at 140.8 px,
    is 2.40x the largest reach a real near contact needs and misses by 49 px
    even after the full scale correction. 5 of 7 are PURE LATERAL (dy = 0),
    which is what "needs jump-aware reach" does NOT predict. Status: the
    metric explanation is dead, no mechanism is designed (a ground-metre reach
    is OWNER-GATED, and the px->m move was GT-refuted for `near_net`), and
    the OPEN question is now upstream: which of the 7 are real far-side
    contacts at all? 3.08 m (e2 f390) and 4.54 m (e1 f399) are the frame where
    the ball is 472 px from a baseline player, not a reach. **Next step:
    GT contact sheets for e1 f161/f399, e2 f390/f402/f403, e7 f163 — owner
    ratified; only then is any reach mechanism arguable.**]

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

31. **Point-end REST is invisible to the ground-contact observer's tracked-ball
    contract (new, #80 — OWNER GATE before any `src/` change).**
    - **Status:** v1 shipped display/diag-only; the rally-over use case is HALF-covered.
    - **Problem:** a point-ending ball lands, bounces and rolls to rest — and the
      static-ball suppression (persist ≥0.55 removed outright, ≥0.30
      `stationary_suspect`) removes resting balls from the track BY DESIGN, so the
      tracker drops the final descent (e3 f616: vy +17.5 falling, then `track=none`
      while diag `ball_dets` shows the rolling ball drifting (686,478)→(558,492) for
      56 f) and the label honestly HOLDS AIR. game_state BETWEEN-points read 39.3%
      GROUND/OUT but 60.7% AIR (mostly carried ball — honest — plus these mid-fall
      losses); live GROUND/OUT fires ≤2 s after 11/13 GT stops, and hard-driven
      terminations stay AIR.
    - **Next step (owner gate):** v1.5 — on lost-track frames, if the LAST tracked read
      was AIR with downward vy and a near-stationary post-suppression detection near
      the last tracked position maps GROUND/OUT (`measure_box` on the
      `ball_detections`/side-channel box), emit that grounded row tagged
      `from_candidate` (§6-pure: reads only values the pipeline already computed,
      display/diag only, no new keys). Parked rack balls (e3 (290,444)/(436,465),
      present all video) are the FP control for the proximity + falling-vy gate.
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
    **[OWNER-RATIFIED #77 (2026-10-04): the post-hoc direction is GO, and the
    first instrumentation piece is shipped.** The owner reframed overpass as
    “not an action but WHERE the action lands” (dig/hand-set/bump that
    crosses; spike-on-2 vs overpass is the hard case; bump-pass-attacks may
    be labeled overpass for now) and added the twin proposal:
    possession-first attribution post-hoc to settle ambiguous touches (if
    PA1's 3rd touch follows an unknown mid-court touch, it was PA2's set;
    if PB2 touched it, PA1's dig was an overpass). Both stand on one
    substrate: a per-rally ball-fate timeline. SHIPPED this session
    (display-only, no `pipeline_output.json` key): per-frame ball-side
    possession + crossing labels — `src/analysis/ball_side_possession.py`,
    an always-on pure observer in `process_frame`; bands per-video from the
    calibration via the owner's pinhole
    `d_net = D·w_near·w_far/(4(w_near+w_far))`; RECALIBRATED #78+#79 on
    owner feedback: factors **0.85/1.45** (match 19.4/33.1 px; fallback
    19/33), NEAR on the ROLLING MAX width of the last 12 measured frames,
    FAR additionally on PERSISTENT smallness (≥4 of the last 12 measured
    frames ≤ far_px; window fixed to exactly 12 entries) — the #77 factors
    (1.15/1.55, fit on flying balls) put far_px
    INSIDE the net-plane rest regime, so occlusion dips committed far
    (match f302, vall f1059) and stuck for 100-220 frames; live-debug label +
    diag `ball_possession` (schema v2). Sequencing for the label lever:
    **C1** fitted ball-fate read (fitted crossing + landing depth +
    next-contact side incl. rejected candidates + rally-terminal flag;
    pre-registered PASS/FAIL at m ≤ 2k−12, ONE held-out shot; e4 f347 must
    NOT fire, f24948 into-net MUST fire via the terminal branch) → **C2**
    possession timeline (squad mapping + ratified side-switch schedule,
    never raw foot-side; alternation/3-cap/2v2 rules) → **C3** overpass
    relabel via the `scripts/probe_label_ceilings.py` harness → **C4**
    ambiguous-touch reattribution (open point 26 = named test). If C1 fails,
    C2-C4 still build as attribution/team tooling, not a label lever.)
    [#78 UPDATE: the display possession labels were RECALIBRATED on owner
    feedback — occluded near-side balls committed far under the #77 factors;
    fixed with rolling-max evidence + FAR_FACTOR 0.85, probe-verified on
    match/vall/e3 (Log #78). C1-C4 unchanged. vall_dhebron was unlocked for
    THIS display-band diagnosis only.]
    [#79 UPDATE: the MIRROR bias — far dig/set rallies held NEAR because
    the rolling max rescued their 0.66-1.14×d_net flicker into the band;
    fixed with the persistent-smallness far rule + NEAR_FACTOR 1.45
    (e3 GT cross-check: 12/14 touches correct, both misses flight latency,
    every flip precedes the next GT touch). C1-C4 unchanged.]

    **[UPDATED #76: the crossing signal is not merely "missing" — it is NOT
    PRESENT in this stream, and four independent families are now measured
    and killed (`logs/overpass_unreachable_report.md`, suite 1470).** The
    prize is +0.0949 and the PRECISION BUDGET is only 88-100% of fires
    (`m <= 2k - 12` on the 137/84 bar arm: k=13 -> at most 14 fires), so the
    task was always tractable — the blocker is that no emitted signal
    separates the class: (i) 16 kinematic features + all 120 two-feature
    AND-rules give NO LARGE separator (best |delta| 0.413 single / 0.333
    pair; 7/120 significant at p<=0.05 is exactly the chance rate);
    (ii) 7 possession-reframing rules replayed through the IMPORTED
    resolver are ALL net-negative (R5 best, 5 fires / 0 hits, -0.0073) and
    recover 2 of 16 in-scope GT overpasses across 205 fires;
    (iii) the vocabulary ceiling R1 "every bump_set is an overpass" — which
    is literally what the owner's GT wording says ("bump pass" x12, and NO
    non-overpass event ever uses that wording) — fires 117 and recovers
    ONE: **a dig and an overpass are kinematically the same contact here**;
    (iv) post-contact NET-PLANE crossing in y on the production calibration
    is the physically correct instrument and still gives precision 0.124
    (shallow, 0.25 band) / 0.129 (deep, 0.50 band) — at the deep threshold
    SPIKE crosses more than overpass (0.552 vs 0.267), which is physically
    right, and only 27% of GT overpasses clear the band at all because a
    bump sent over crosses close to the tape. **So this is an INSTRUMENTATION
    requirement, not a rule-design task: the pipeline emits a contact and
    discards the ball's fate.** Missing evidence, both already-available
    §6-shaped pure observers: (a) per-contact net-plane crossing of THIS ball
    after THIS contact, crossing FITTED on the trajectory (the per-frame
    thresholded version above is too noisy at the threshold that matters);
    (b) a rally-terminal flag — GT f24948 is a bump pass INTO THE NET that
    loses the point and is still `overpass`, so "sent over" must not exclude
    "did not clear". NOT built: per diagnose-first and the owner-scope flag on
    item 0a, adding per-contact outcome evidence to the emission is a
    production change and needs owner ratification first. The touch-count
    avenue stays dead for the reason recorded above (overpasses sit at touch
    1/2/3, which are the majority dig/set/spike counts in BOTH the match and
    the drills).
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
    **[#68 (2026-10-02) — the lever was re-founded on the possession
    COUNT, and the numbers above were re-derived: `docs/g3_touch_count_lever.md`,
    `logs/touch_lever_stdout.txt`. Layer 1 is degenerate — **157 of 185 (85 %)
    accepted match contacts carry the single gesture `bump_set`** — so every
    `dig`/`set`/`overpass`/`serve` decision is `ActionContextResolver._decide`
    keyed on `_poss_touch`. Substituting the real GT `touch_number` into the
    UNMODIFIED resolver lifts label accuracy from the replay control
    **79/139 = 0.568 to 110/139 = 0.791**, and on the 127 non-serve contacts
    where an offline replay is faithful, **79/127 = 0.622 to 110/127 = 0.866
    (+0.244)**; the count itself is only **96/139 = 0.691** accurate. Touch
    errors cluster where the pipeline emitted FEWER contacts than the owner
    listed (11 points `accepted >= GT`: 11/37; 14 points `accepted < GT`:
    **32/102**). **Baseline hygiene, corrected in-session:** the shipped stream
    is **85/139 = 0.612** (the dump's `action` field) / **83/141 = 0.589**
    (`pipeline_output.json`), NOT 0.568 — that figure is a replay artifact,
    because the dump's `accepted` rows carry no `behind_baseline` (0 of 185),
    making the replay 168/185 faithful and **0/12 on serves**. Nothing ships
    from #68; **CARD TC1** (READY, first card) tests a re-derived count offline
    on dev+entreno with one held-out shot (PASS >= 0.700 = +0.132 over R0 /
    PARTIAL >= 0.650 / FAIL).]**
    **[#69 (2026-10-02) — CARD TC1 ran the whole decision: `touch_rule_gate =
    TOUCH_COUNT_LEVER_REFUTED/0.6187`. Nothing ships and no architect card is
    justified. `docs/tc1_touch_rules.md`, `logs/tc1_report.md`,
    `logs/tc1_stdout.txt`, `scripts/probe_touch_rules.py`,
    `tests/test_touch_rules.py` (+41; suite **1327**). G1 reproduced every
    #68 number exactly (185 / 157 / 139 / 96 / 79 / 110, medians -2 f and
    serve +23 f, shipped stream 85/139 = 0.612 / 0.589). R0-R4 were replayed
    through the UNMODIFIED `_decide` on dev + e1-e7 only; summed F1 R0 5.577 /
    R1-R3 5.591 / R4 **5.745**, so **R4 was chosen there** and scored ONCE on
    held-out: label accuracy **86/139 = 0.6187 (+0.050 over the R0 control)**,
    touch accuracy **103/139 = 0.741**, non-serve **86/127 = 0.677** vs the
    GT-touch arm's 110/127 = 0.866. **The 43 wrong-touch found contacts are
    STARVED, not mis-reset**: `under_counted` 20 + `previous_contact_missing`
    13 = **33 of 43 (77 %)**, `team_change_not_reset` 5, `over_counted` 4,
    `attack_not_reset` 1 — so the counter is downstream of a MISSING-CONTACT
    problem (open points 2/5) and a re-derived count buys at most +0.055 of
    #68's +0.223/#68's non-serve +0.244. **#68's lever stands as an in-sample
    UPPER BOUND / diagnostic, not as a shippable rule set.** Step 5 (offline
    approximation of the STATUS gate) is 4 of 7 drills outside +-0.01, but the
    R0 replay is itself off-record on 4 of 7, so that criterion cannot be met
    by any replay. Three card defects reported, not reinterpreted: criterion
    (ii) is unsatisfiable as written; **R2 is a no-op** (the card also mandates
    keeping the resolver's own `attack_before` reset in every arm, which IS
    R2, so R2 == R1); and G1's timing / 0.589 references only reproduce on the
    PRODUCTION stream over ALL region events. Next = the upstream contact-recall
    diagnosis, not another touch-rule search.]**

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

- **`json_exporter.collect_actions` projects actions through an EXPLICIT key list — a new action field must be added there or it silently vanishes from `pipeline_output.json` (measured #81: `player_label` was stamped in `FrameProcessor` yet exported None; the flushed last contact also bypasses `process_frame`, so stamp at `flush_actions`'s return).**
- **Enrollment chaining must be ONE-TO-ONE per sampled frame (#81):** without the exclusion, two same-frame detections within the gate both feed ONE chain (4 players → 2 chains, squad split fails) — greedy best-(correl, −dist)-first with per-frame used-sets is the fix.
- **e2's recorded entreno F1 0.571 does not reproduce on fresh runs (base reads 0.400 on both arms, #81)** — fresh-run device variance exists in the BASE itself; the same-session A/B is the only valid comparison (extends the open-point-1 rule from tracking to the action gate).

- **THE NET-PLANE BALL SCALE IS COMPUTABLE FROM THE CALIBRATION ALONE (owner-derived #77): `d_net = D·w_near·w_far/(4(w_near+w_far))`** with D = 0.67/π m and w_near/w_far the projected baseline widths (near pair = the 2 largest-y corners; sanity: near projects wider than far). Match 20260920: d_net = 22.8 px. **MEASURED width regimes (#78/#79, three videos + e3 GT): near flight 1.49-1.6×d_net; net-plane rest/tape/mesh AND motion-blurred far flight BOTH 1.0-1.35×d_net — width cannot split those two; far ground bounce 0.5-0.8×d_net; a far rally FLICKERS 0.66-1.14×d_net (max-only reads it as band).** Shipped bands (recalibrated #79): FAR 0.85× / NEAR 1.45× d_net; NEAR commits on the rolling max of the last 12 measured frames (owner: "do the greatest of the sides"), FAR on max ≤ far_px OR ≥4 of the last 12 measured frames ≤ far_px (persistent smallness — occlusion dips never produce 4 sub-far frames, flickering far rallies do) — occlusion dips hold the last side, the overlap regime reads CROSSING. Per-video bands replace venue-coupled px constants (match 19.4/33.1; entreno_3: d_net 26.9 → 22.8/39.0). Carried caveats: ±0.5 m of depth shifts the ball diameter by <0.5 px and jitter/motion-blur are ±1-2 px, so width alone is weak PER-FRAME — asymmetric rolling evidence + hysteresis + last-known hold is the design answer.

- **A GT CLASS WHOSE WORDING NEVER APPEARS IN ANY OTHER GT EVENT IS A LABEL, NOT A MOTION PATTERN — read the `owner_raw` lines before designing the rule (measured #76b).** The 21 match-GT overpass events read "bump pass"/"bump passes" (12), "overpass" (10) and "passes the ball" (3), and across all 189 non-overpass events those words NEVER appear (the only "over"-lines are five `overhand dig` dig events and one bystander). So the owner's `overpass` means *a bump sent over* — including f24948, "bump passes ball f24948 into the net and loses point", still `overpass`. **That immediately tells you the feature is the ball's FATE after the contact, not the contact's kinematics — and it is why the "every bump_set is an overpass" ceiling rule recovers 1 of 16: a dig and an overpass are the same motion here.** Corollary: when a class cannot be recovered from a contact's own features, check whether the GT's own wording makes it a post-hoc/outcome class before hunting another threshold; that reclassifies an open point from a rule-design task into an instrumentation requirement.
- **THE PRECISION BUDGET IS THE FIRST THING TO COMPUTE FOR ANY RELABEL LEVER, AND IT IS CHEAP (measured #76b).** `base + k - (m - k) >= labels_needed` because the matcher is class-agnostic and a relabelled matched contact scores iff the label equals the GT's — so `m <= 2k - labels_needed`, and `m >= k` always. On G3's bar arm (137 matched, 84 correct, bar 0.70) that is 12 labels needed, k=13 -> at most 14 fires (93% precision), k=16 -> at most 20 (80%), and **any k below 6 is infeasible at ANY precision**. Write it down FIRST: it turns a lever hunt into a target ("does any family hit 93% precision?") and it catches a family instantly. It also caught a first-draft algebra error (`bar*n_matched` = 95.9 instead of the 12 labels needed) that would have "proved" every rule impossible for the wrong reason — pinned by `tests/test_overpass_levers.py::test_budget_would_have_been_satisfied_by_the_mistaken_formula`.
- **A SANITY-CHECK ROW PROVES AN INSTRUMENT IS MEASURING WHAT IT CLAIMS — report the control that should score HIGHEST (measured #76b).** The net-plane crossing test reported `spike` crossing MORE than `overpass` at the deep threshold (0.552 vs 0.267), which is physically correct and is what makes the near-zero overpass rate believable rather than suspicious. A probe whose classes are all similarly bad is indistinguishable from a broken instrument; one class that must fire always, firing, is the control that licenses reading the others.

- **THE G3 BAR IS `class_accuracy` AND CONTACT F1 IS BLIND TO LABELS — so a lever's value is EXACTLY its label count, and a "label-only ceiling" measured with a recall-shaped denominator is meaningless (measured #76).** `scripts/evaluate_timed.py:296 match_events` matches on TIME only, deliberately ("*Class-agnostic on purpose: the CONTACT was found or it was not; whether the label is right is scored separately*"), so `tp`/`fp`/`fn` and the contact F1 are INVARIANT under any relabel — measured: five arms spanning class accuracy 0.5612 → 1.000 all scored the identical F1 (0.774/0.772/0.794 per arm). Pinned by `tests/test_label_ceilings.py::test_relabeling_cannot_change_the_pairing`. Corollary that cost a session's worth of ranking: a **label-only oracle is trivially 1.000** (relabel each matched prediction to its GT class), so "label-only ceiling" can only ever mean a REAL rule's achievable count — quoting a *touch*-accuracy figure (90/139 = 0.647) in the label slot is what produced STATUS item 0a's wrong "no single lever reaches 0.70". **WHEN RANKING LEVERS, always measure the ceiling by relabelling `action` alone and reading `class_accuracy`, on a named arm; never carry a ceiling number across metrics or arms.**
- **`CourtCalibration.world_scale_at` is UNUSABLE as a metric scale (measured #75) — and the reason is that a ground homography has TWO scale components that differ ~6x here.** It is the MEAN of the ACROSS and ALONG (depth) components and inherits the broken one: multiplied into median player bbox widths it reads 4.8 m for a near-side body and 5.9-6.2 m far, it has poles at y = 192-193 and y = 302-303 (577 m/px at y = 250, 112 rows above 1.0), and its far/near metres-per-pixel ratio is 4.169. **Use the ACROSS component only** — `|image_to_world((x+3,y)).x - image_to_world((x,y)).x| / 3`, which reads **0.58-0.74 m** against the same widths at EVERY depth in all 3 entreno drills. The ALONG component reads 1.88-4.76 m and is separately inconsistent with the court (calibration puts the depth vanishing row at y=246; its own 8-point fit needs y=271 for the 492/602/930 px rows at world depth 0/8/16 m). **Do NOT convert a vertical px span with either**: the 6-point DLT over 4 corners + 2 net-tops is degenerate (every net height 1.8-3.4 m fits to 0.64 px), so the focal length is unrecoverable. Corner order is CORRECT as shipped (`CORNER_WORLD` reproduces `compute_ground_homography` to 0.0 elementwise) — do not "fix" it. And ball bbox width is NOT a usable scale reference (non-monotonic in y: 28 px at y<360, 22 at y=420, 44 at y=600). Two measurement traps this cost: a published `far/near 0.49x` metres-per-pixel ratio is **physically impossible** (a far object must have FEWER px per metre), and the apparent "far players look BIGGER" is the same artefact — check the SIGN of any far/near scale ratio before reporting it.

- **TWO "point start" sources in `ground_truth/` are PREDICTIONS, not anchors — and the OWNER'S OWN anchor is the serve frame (measured #64b, corrected by the owner).** (a) `ground_truth/20260920_match_contacts.json`'s `points[].match_start_frame`: all **33** carry `window_source: "episode_map_emission_window"` + `window_is_prediction: true` (built by `scripts/build_match_contact_gt.py:131`); spread vs the first owner-dictated contact is **-1723 … +746 f**. (b) `ground_truth/gt_point_start_end.txt`: **the GAME-STATE VIDEO's** GT (`video_entreno_game_state.mp4`, 13 mm:ss pairs, dev era — commit 48f8222), a different video. **The owner-ratified per-point start frame is the `serve` contact's `match_frame`** — verified #64b: all **33** GT points carry exactly one `serve`, and in **every** point the serve IS the earliest contact (0 of 33 exceptions), so `points[].contacts` already defines the point start within its stated +-15 f. Do NOT ask the owner to re-annotate point starts; do NOT read the two prediction sources above as anchors. The only consequence is that `scripts/evaluate_match_points.py` has no segment-start metric wired (it reports `segmentation_starts: requires owner-ratified frame anchors per GT point`) — that is a SCORER gap, not missing GT, and CARD PG1 closes it.

- **DELEGATION HARNESS: a prompt over ~1 KB kills the child `pi` instantly (`Killed: 9` / `EXIT 137`, zero output) on every model.** Measured #62+ by bisection on all three worker models (`stealth/space-bunny-alpha`, `anthropic/claude-opus-5.5`, `deepseek/deepseek-v4.1-flash`): 800 B survives, 1000 B dies, reproducible across 3+ repeats, independent of model, THINK level, `PI_CODING_AGENT_DIR`, and `-ne/-ns/-np/-nc`. Neutral filler text dies at the same size, so it is the prompt bytes, not the content. **Rule: keep the delegating prompt to a few hundred bytes and make the child READ a brief file** (`/tmp/<brief>.md`) instead of inlining it — exactly as `scripts/run_task_openrouter.sh` already builds `$(cat "$1")`, so the fix is to pass a short pointer, not the brief. This is why `cat .pi/prompts/architect.md /tmp/architect_brief.md > /tmp/architect_full.md` (the documented route-4 recipe) **cannot work today**; the architect prompt alone is 7.3 KB. Note `EXIT 1` with an OpenRouter billing body (not 137) is a different failure: the 128k max_tokens request exceeds the remaining credit, so architect-sized runs need the balance topped up or `max_tokens` lowered.

- **The serve-window opener is a weak key: measured #62+ on the 20260920 match, only 4 of the 8 production near hits have a `serve` as their window's first action (the other 4 windows open 326-471 f earlier on a dig/far serve/spike), and 6 of the 12 false serves sit INSIDE a near-miss window, 5 of them as its first action.** A post-hoc per-point serve record (SR4) must key on the same-side contact within tolerance, not on the window opener. Related: the chasm rule (`GAP_SERVE_MIN = 143`, imported from `relabel_serves.py`) rejects only **1 of 12** false serves, and rally onsets sit 10-19 f BEFORE the serve on 12 of 15 near rows (P12 -662 f, P20 +630 f), so an onset is not a serve marker at ±15 f. Source: `docs/sr4a_near_openings.md`.

- Calibration `frame_dimensions` is (h,w) and is NOT a scale hint: points are used verbatim, only the court mask is sized from it — a smaller calibration on a bigger video silently drops near-half players. `src/main.py` now hard-errors on missing/mismatched calibration (`--allow-uncalibrated` to waive; T1, session 31). Probe scripts share it via `src/detection/calibration_readiness.py` (T1b); they decode at native res, so point them at `_up1080` for sub-1080p sources.

Protocol rules live in **AGENTS.md** (entreno validation, live-debug
parity, diagnose-first, byte-identical A/B, `cv2.setRNGSeed(0)` per
tracker in multi-tracker harnesses). The distilled technical facts below
survive across sessions; provenance in the archives.

**Measurement & eval conventions**
- **An offline replay is not a baseline, and a "median offset to the nearest emission" needs its POPULATION stated — three separate measurement traps, all hit while running CARD TC1 (measured #69, reusing #68/#70's numbers).** (1) **Replay fidelity**: `ActionContextResolver._decide` reads `behind_baseline`, which the `accepted` rows of `output/g3r1/match_bw03_diag.jsonl` do not carry (0 of 185), so any replay over that dump scores **0/12 on serves** and reads 79/139 = 0.568 while the shipped streams are 85/139 = 0.612 (the dump's own `action` field) and 83/141 = 0.589 (`pipeline_output.json`) — gate on a GAIN over the replay control, never on its absolute. (2) **Population**: #68's serve median of **+23 f** only reproduces on the PRODUCTION `pipeline_output.json` actions over ALL 183 region events, found or not (nearest-ANY action); on the 12 FOUND serves alone the median is **-0.5 f**, because the 13 far serves at +23…+125 f carry the class. (3) **Matcher policy**: #68's 139 found contacts (137 DISTINCT contacts — two contacts serve two GT events under a non-exclusive matcher) require non-exclusive nearest-within-±15 f; `evaluate_timed.match_events`'s one-to-one assignment on the same data gives 137, and `evaluate.py` on the same data grades 0.437 rather than 0.589 (different population). Corollary on rule ladders: when a probe must keep the shipped resolver's own resets in every arm, **an arm that re-adds one of them is a no-op** — CARD TC1's R2 ("reset after an attack gesture") was exactly the resolver's existing `attack_before` reset, so R2 ≡ R1 by construction and the ladder's apparent depth was fake; pin such an arm with a test instead of reading it as a distinct rule.
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

- **A calibration consumer wired ONLY in `set_court_calibration` never receives the batch calibration — `FrameProcessor.__init__` loads `self.court_calibration` itself and the batch path never calls the setter (measured #80).** Both the #77 possession and the #80 ground-contact observers silently ran on their FALLBACK px bands in every batch run (e3: fallback 19/33 px vs real 22.8/39.0, diag `net_width_px: null`) until the #80 probe showed 672/672 `state: None`. Fix = wire every calibration consumer in `__init__` right after construction and PIN it with a wiring grep test (possession + ground both). Live-debug was unaffected (it calls the setter); only batch was degraded — suspect this bug class whenever a batch diag shows fallback constants while live looks right.

- **Identity labels must converge, not be perfect (owner contract, #82).** P1A/P2A/P1B/P2B only have to land on the same person again within a few frames; a lost box, a momentary id swap or a stolen box is fine. The tracker swapped the two far teammates at f151 of the 20260920 match because `_may_feed_track`'s 90 f off-court hold expired for the on-sideline player (detection sim 0.956 to her own track) and Hungarian paired her id with the teammate's box; fixed for enrolled tracks, and a per-frame display-only resolver (`_resolve_identities`: smoothed appearance + last-seen-position continuity + sticky bonus, history wiped on a box jump) now makes labels follow the body. Far-player appearance is weak (sims ~0.3-0.6, near ~0.9) and an occluded far player gets ~0.5 on every reference, so expect brief None/flicker, not swaps.

- **A side switch is invisible to positions — identity there is an appearance question, and the FIRST one is cross-view (#83).** 2 near + 2 far before and after, so only appearance can tell; enrollment sees squad 1 only from behind/large and squad 2 only from the front/small, so raw similarities are biased toward "nothing changed". Decompose identity into orientation (piecewise constant → change-point test over all four bodies) + one slot bit per side, and standardise every similarity on the video's OWN enrollment samples.
- **Teammate-only impostor normalisation is fooled by mixed teams (#83, found while designing on the owner's stills).** If a man's only impostor is his female teammate, any other man scores a high z — including the other team's man after a switch. Normalise against ALL other players (both views) and add a same-view genuine FIT term (how typical for that player in that view), which collapses for the whole replaced pair at a switch with no view bias.

## Session index (one line each)
- #83 **Side-switch-aware TEAM IDENTITY RESOLVER (output labels only; tracking identical)** — `src/tracking/identity_resolver.py` (orientation CUSUM + within-side slots + per-video calibrated z/fit evidence + learned second view); enrollment refs carry identity samples; `label_for(tid, frame)` labels actions at their contact frame; `player_identity_mode` + 3 CUSUM Config keys; `scripts/probe_identity_switches.py` (owner-run real-footage gate, scored against the match contact GT); tests +30 (synthetic switches), suite 1475; NOT yet run on real footage.
- #82 **Identity labels follow the body (per-frame resolver), team-letter labels P1A/P2A/P1B/P2B, readable colours**
- #81 **Player ENROLLMENT pre-pass (E1) + squad colours (E3) SHIPPED (display-only)**
  — `src/tracking/player_enrollment.py` builds 4 averaged-signature references from a
  sequential decode of the first 600 frames (detector every 5th, foot-in-court, greedy
  one-to-one chains + fragment merge); `PlayerTracker.set_enrollment` attaches sticky
  per-tid labels (P1A/P1B/P2A/P2B, squad = majority side, slots left→right, ensemble
  similarity > 0.35); tracked players + actions carry `player_label`/`squad`/`slot`;
  overlay `PLAYER_SQUAD_COLORS` (blue clear/dark, red clear/dark, squad-stable) used by
  batch + live debug; 7 new `player_enrollment_*` Config keys + drift-guard rows;
  tests `tests/test_player_enrollment.py` (10) + `tests/test_overlay_squad_colors.py`
  (7); gate PASS — fresh A/B 7 entrenos, action F1 Δ=0.000, snapshots byte-identical,
  56/56 actions labelled; suite 1549. E2 (drift + side-switch observers, display/diag,
  owner gate) is next session.
- #80 **Ball GROUND-CONTACT/OUT observer SHIPPED (display+diag, always-on pure
  observer) + latent batch-calibration wiring bug FIXED** — `src/analysis/ball_ground_contact.py`
  maps the tracked ball's bbox bottom-center through the SIGN-normalized ground homography;
  groundedness ratio = bbox width / projected ground diameter; hysteresis AIR≥1.45 →
  GROUND≤1.25 (in-court rect +0.25 m) / OUT (band re-locates for a rolling ball); BOUNCE on
  gated image-vy flip; live-debug GROUND/OUT/AIR ball label + per-candidate GND/AIR tags +
  panel `ground:` line; diag `ball_ground`, SCHEMA_VERSION 3; tests `tests/test_ball_ground_contact.py`
  on a synthetic pinhole camera (grounded ratio ≈1 ±0.15 m world recovery; 1 m-up ball maps
  16.5-60 m deep → AIR not OUT; owner-convention negative-w → sign-normalize), suite **1525**.
  Probe FIXED `FrameProcessor.__init__` never calling `set_court_calibration` in batch —
  possession had run on FALLBACK px bands since #77 (both observers wired at init, greps pin
  it). game_state GT (13 windows): IN-window 95.5% AIR vs BETWEEN 39.3% GROUND/OUT; live
  GROUND/OUT ≤2 s after 11/13 point stops; 10 bounces (5 in-rally/5 dead-ball); e3 dig touch
  f453-455 + bounce f454; point-end rest invisible to the tracked-only contract → open
  point 31 (v1.5 raw-candidate extension, owner gate).
- #79 **Possession labels RE-BALANCED on owner feedback (mirror bias: far rallies held NEAR)** — the #78 rolling-max statistic is wrong for the far side: a far dig/set rally flickers 0.66-1.14×d_net (match f1415-1500) and the max rescued it into the band; fix = ASYMMETRIC evidence in `src/analysis/ball_side_possession.py`: NEAR stays max-only, FAR also fires on ≥FAR_COMMIT_MIN_COUNT=4 of the last 12 measured frames ≤0.85×d_net; NEAR_FACTOR 1.55→1.45 (e3's GT near touches sustain only 1.49×; e3 GT cross-check 12/14 correct, both misses flight latency, all 6 transitions precede the next GT touch); latent #78 off-by-one fixed (window was 13 entries). Probe A/B: match f1428/f1488 far (count fires at the dig), tape 0 far, f254 intact; vall f1185 near✕, 5/5 bounces far; suite **1496**.
- #78 **Possession labels recalibrated on owner feedback (occlusion-dip far bias)** — probe `scripts/probe_possession_feedback.py` measured the width regimes on match+vall (near flight ≥1.55×d_net; net-plane rest AND blurred far flight OVERLAP at 1.0-1.35×d_net; far ground 0.5-0.8×d_net); fix in `src/analysis/ball_side_possession.py` = ALL band decisions on the ROLLING MAX width of the last 12 measured frames (owner: "do the greatest of the sides") + FAR_FACTOR 1.15→0.85 (overlap regime reads CROSSING, holds last side; fallback 26→19); probe A/B: match f250-345 far 100→4, f378+ 0, vall f1059-1280 0 (f1185 near+crossing), e3 one far commit at the point-ending landing. vall unlocked for THIS display-band diagnosis only. Suite **1493**.
- #77 **Post-hoc layer RATIFIED + first instrumentation SHIPPED: per-frame ball-side POSSESSION + net-CROSSING live-debug labels (display-only pure observer)** — owner ratified overpass-as-where-it-lands + possession-first attribution (open point 9 [OWNER-RATIFIED #77]); new `src/analysis/ball_side_possession.py` (always-on, inside `process_frame` step 3c): reads tracked-ball bbox width ONLY on non-predicted frames, hysteresis bands per-video from the owner's pinhole `d_net` formula (1.15×/1.55× of d_net; match 26.3/35.4 px ≈ measured 26/35; fallback 26/35 uncalibrated), last-known side on lost/predicted frames, crossings counted on completed far↔near transitions; live-debug `possession: NEAR|FAR` + `CROSSING` label via `_overlay_data` 4-tuple → queue 7-tuple → `overlay.draw_possession`; diag `ball_possession` (SCHEMA_VERSION 2); NO `pipeline_output.json` key, actions byte-identical. Sequencing C1→C4 recorded (C1 = fitted ball-fate read, pre-registered at the m ≤ 2k−12 budget). Suite **1489**; e3 script-path F1 **1.000** reproduced post-ship (14/14, team 1.0).
- #76b **The OVERPASS lever is `UNREACHABLE FROM THE CURRENT STREAM` — the +0.0949 prize and the modest 88-100% precision budget are both real, but no emitted signal separates the class; 4 independent families measured and killed, nothing ships** — `logs/overpass_unreachable_report.md`, `scripts/probe_overpass_separator.py` (16 kinematic features + all 120 two-feature AND-rules, Cliff's delta + Fisher, no scipy), `scripts/probe_overpass_budget.py` (the budget + 7 possession-refaming rules replayed through the IMPORTED `ActionContextResolver` over `candidate_passed_gates`), `scripts/probe_overpass_netcross.py` (post-contact net-plane crossing in y on the PRODUCTION calibration), `tests/test_overpass_levers.py` (+22; suite **1470**). Budget `m <= 2k - 12`: 12 labels needed on the 137/84 bar arm, k=13 -> <=14 fires (93%), k=16 -> <=20 (80%), k<6 infeasible at any precision; the 13-contact oracle satisfies it exactly. Family (i) NO LARGE separator (best single -0.413, best pair +0.333 at 8/16 vs 14/92; 7/120 significant = the chance rate). Family (ii) all 7 rules net-negative, best R5 5 fires/0 hits/-0.0073, 2 hits total across 205 fires, edit distance grows in every arm. Family (iii) the vocabulary ceiling R1 "every bump_set is an overpass" fires 117 and recovers **1** — a dig and an overpass are kinematically the same contact here. Family (iv) net-plane crossing precision 0.124 / 0.129; the ball IS tracked 91/91 frames in the window so the evidence exists and was never read; the `spike`-crosses-more row is the instrument's sanity check. **⇒ OPEN POINT 9 RECLASSIFIED as an INSTRUMENTATION requirement: the pipeline emits a contact and discards the ball's fate. Two §6-shaped default-OFF observers are specified (per-contact FITTED net crossing; rally-terminal flag, because "sent over" must not exclude "did not clear" — f24948) and NOT built: adding per-contact outcome evidence to the emission is a production change and needs OWNER RATIFICATION FIRST.**
- #76 **G3 label-lever ceilings RE-MEASURED: item 0a's arithmetic is CORRECTED — the `overpass` lever alone crosses the 0.70 bar (0.6131 → 0.7080), because `90/139 = 0.6475` is TOUCH accuracy quoted in the LABEL slot** — `logs/label_ceilings_report.md`, `scripts/probe_label_ceilings.py` (relabels ONLY the `action` field of emitted events, re-scored through the IMPORTED `evaluate_timed` matcher; no decode, no seek, no `src/` change, no GT edit, held-out untouched), `tests/test_label_ceilings.py` (+11; suite **1448**). All three recorded baselines reproduce: `diag` 0.6131 (84/137), `production` 0.5899 (82/139), `pass2` 0.5612. **Contact F1 is invariant across every arm (0.794/0.772/0.774) because `evaluate_timed.match_events` is CLASS-AGNOSTIC by design — so the bar is `class_accuracy` and a lever's value is exactly its label count.** Label-only oracle = **1.000** (139/139), not 0.6475; `docs/g3_reach_cascade.md:43` records the same 139 contacts as `label 78/139 = 0.561  touch 90/139 = 0.647`. `overpass` = the same 13 contacts on all three arms: **+0.0949 / +0.0936 / +0.0935**, reproducing #70's "+0.092"; bar needs +12, lever supplies 13. New bucket **`spike → block` x7** (match GT has ZERO `block` events). `serve` ≤ +0.029 (7/11 already correct). "Compound levers / owner scope decision" WITHDRAWN; INSERT (0.640, recall, different denominator) and #69/#72/#74/#74c/#75 all stand untouched. Mechanism for `overpass` still unsolved — promoted to THE blocking question for the match half, a Layer-2 rule-design problem.
- #75 **Reach-gate scale diagnosis DONE: `NOT SCALE-EXPLAINED` — the 140 px `CONTACT_REACH` is side-blind (far 1.359 m vs near 1.014 m, 1.341x), but the 7 far-side rejections are 1.382-4.540 m, 2.40x above the largest reach any true near-side contact demands, so scale is NOT their story** — `logs/reach_scale_report.md`, `scripts/probe_reach_scale.py` (imports `CourtCalibration` + `ActionClassifier`; no decode, no seek, no `src/` change, no GT edit, held-out untouched; IN-SAMPLE 3 drills), `tests/test_reach_scale.py` (+17; suite **1437**). Conversions come from the IMPORTED homography's **ACROSS** component, validated against detector player widths (0.58-0.74 m at every depth, all 3 drills); the ALONG component and `world_scale_at` (the mean of the two) are REFUTED and reported with numbers — `world_scale_at` reads a 4.8 m near body, has poles at y=192/302 (577 m/px) and a 4.169 far/near ratio. Far-rejected metres 1.382/1.521/1.549/1.661/2.283/3.080/4.540 vs near-accepted 0-0.736 m and GT-contact near max 0.576 m; Cliff's delta +1.000 both ways, in px and metres. Scale-corrected near-equivalents 188.8-633.8 px, all still over 140. G1a PARTIAL FAIL reported: 2 of 7 rows in `buckets.json` (the ±15 f window census in `scripts/probe_entreno_buckets.py:120-162`); the other 5 read from `output/sr1/*_diag.jsonl`; e1 f161 recomputes 11.3 px higher (258.7 vs 247.4, `seen_at` lag — conservative). Sensitivity (counts only): 187.7 px -> 4/7 admitted, 254/589 near-side rows already dropped downstream inside the band; 472.7 px -> 7/7 and 580/589. Extra findings: rejected and accepted sets differ in KIND (5/7 pure lateral vs 8/21 image-vertical), and vertical px->m is impossible from these 6 calibration points. **NOTHING SHIPS; the metre-scale reach stays OWNER-GATED. The open decision is whether any of the 7 is a real far-side contact — GT contact sheets would settle it.**)
- #74 **Coordinator session: finished #72/#73's ritual (commits `da0c962` overlay, `c336753` ritual; FALSE commit claim `8040f04` caught via reflog), then delegated + verified the SET↔DIG SWAP diagnosis → **NO SEPARATOR, LEVER CLOSED** (`logs/swaps_report.md`, probe `scripts/probe_set_dig_swaps.py` +9 tests, suite **1345**): the 15 swaps are ±1 possession-count errors in costume — subset of the 43 wrong-touch contacts, all 12 signals overlapping, +0.106 re-absorbed into the (closed) touch-count lever. No `src/` change, no GT edit, held-out untouched.** **Same session, second half (owner rerouted delegation to the free OpenRouter route, `stealth/space-bunny-alpha`): the SERVE bucket also CLOSED as a label lever (`logs/serve_bucket_report.md`, `scripts/probe_serve_bucket.py` +20 tests, suite **1365**): NO SEPARATOR over 24 signals; 7/5/13 split — ALL 12 far serves NOT-FOUND; label-only ceiling 0.647 < 0.70, full fix 0.741 needs far-side recall; `behind_baseline` found in the dump's `candidate_passed_gates` stage (185/185), serve branch replays 12/12; +23 f latency = completeness artefact; far +0.032 line corrected in the lever doc.** **Third half (#74c): the INSERT path MEASURED — DOES NOT CARRY THE BAR (`logs/insert_path_report.md`, `scripts/probe_insert_path.py` +28 tests, suite **1393**): window-start placement over existing artifacts, 11/17 far hits (all at_seam, none of the 6 in_gap — the ceiling is the point map's), precision 0.6111, 96/150 = 0.640 IN-SAMPLE ceiling; #74b's 0.741 corrected as numerator-only (103/152 ≈ 0.678); 0.70 now needs COMPOUND levers — owner scope decision.** **Fourth half (#74d): the ENTRENO half diagnosed (`logs/entreno_buckets_report.md`, `scripts/probe_entreno_buckets.py` +27 tests, suite **1420**): all 7 recorded baselines reproduce EXACTLY (Δ=0.000, script path, MPS; G1 gates e2 0.571 / e3 1.000 / e1 0.706 / e7 0.750 all pass — the reference is healthy), 4 of 7 drills already pass 0.90, and the three losing drills (e1/e2/e7) verdict `NEW MECHANISMS DOMINATE`: known match mechanisms cover 2/9 reachable losses (count error e2 f257; behind_baseline INVERTED polarity e2 f32), the 7 new ones are gesture_miss ×2 (Layer-1 gesture wrong at correct count/team), contact_gate ×4 (reach gate fires ONLY far-side, 7/7 rejections team B; ball out of frame; dead geometry), emitted_vocabulary ×1 (`freeball` ∉ `VolleyballAction`); 2 ceiling events. Known-fixes-only leaves e1 0.706 / e2 0.857 / e7 0.750 — all under; 0.90 reachable only via the new mechanisms (ceilings 0.941/0.933/0.947; e1's nominal 0.941 is a measured 0.824 without the vocabulary change). The far-side/upstream-emission story (open points 2/5) now spans BOTH halves of the goal.**
- #73 **Live-debug ball-candidate overlay LANDED (display-only, `b` toggle, default ON): every detector ball with confidence + suppression verdict via the `raw_detections` side channel; +9 tests, suite **1336**; processing path untouched. The session's own commit claim (`8040f04`) was FALSE (reflog clean); committed after coordinator verification, together with #72's unfinished ritual.** No `src/` processing change; no GT edit; held-out untouched.
- #72 **REACH-GATE CASCADE REFUTED offline (`docs/g3_reach_cascade.md`): admitting the reach-blocked contacts does NOT fix the labels — K=1.2 (precision-clean, +14 found) → −4 LABELS; K=1.3 −5; K=1.5 −1; K=2.0 +1 at 0.513 vs 0.561; ALL 71 reach rows repair only 9/49 wrong touch numbers — the count is driven by the resolver's resets, not recall; earning the recall does not earn the count. NO `src/` change, CARD RG1 NOT written; the pose-anchored arm inherits the failure. The 44 missed contacts are a RECALL story, not the 0.70 path.** Session died mid-ritual; entries committed by #73.
- #71 **CARD TC1 DONE: `touch_rule_gate = TOUCH_COUNT_LEVER_REFUTED/0.6187` — the possession count is NOT re-derivable from the emitted contacts; nothing ships, no architect card is justified — and the TIER-2 ARCHITECT CALL for the upstream cause is DONE (`docs/reach_gate_architect_call.md`): do NOT widen the 140 px scalar, use a POSE-ANCHORED reach (0.5× bbox-width hand radius, class constant default OFF, no new Config key), A/B-able with NO `src/` change because `CONTACT_REACH` is a class attribute** — `docs/tc1_touch_rules.md`, `logs/tc1_report.md`, transcript `logs/tc1_stdout.txt`, `scripts/probe_touch_rules.py` (imports `ActionContextResolver` + the existing matchers; no `cv2`, no decode, no seek; exit 2 on FAIL), `tests/test_touch_rules.py` (+41 tests; suite **1327** = 1286 + 41). Committed artifacts only: no `src/` change, no decode, no seek, no GT edit, held-out session untouched. **G1 reproduced #68 EXACTLY**: 185 accepted (bump_set 157 / attack 16 / block 12), 139 found, touch accuracy **96/139 = 0.691**, R0 replay control **79/139 = 0.568**, GT-touch substitution **110/139 = 0.791**, timing medians dig/set/spike/overpass **-2 f** and serve **+23 f**, shipped stream 85/139 = 0.612 (dump `action`) / 0.589 (`pipeline_output.json`). **Step 2, the deliverable's centre: the 43 wrong-touch found contacts are STARVED, not mis-reset** — `under_counted` **20** + `previous_contact_missing` **13** = **33 of 43 (77 %)**, `team_change_not_reset` **5**, `over_counted` **4**, `attack_not_reset` **1**; this independently re-confirms #68's mechanism (errors cluster on the 14 points where the pipeline emitted FEWER contacts) and localises the fix UPSTREAM. **Step 3, dev + e1-e7 only, every rule replayed through the UNMODIFIED `_decide`** (R0 emitted count; R1 +reset on any team change; R2 +reset after an attack gesture; R3 +reset on `rally_id` change; R4 +ball-width cross confirmation, abstaining where `ball_side is None` = 64 of 185): summed F1 R0 5.577 / R1-R3 5.591 / R4 **5.745 → R4 chosen on dev+entreno**; per-drill R0 is beaten on at most one drill (e5 0.923 → 0.769). **Step 4, ONE held-out shot with R4: label accuracy 86/139 = 0.6187, i.e. +0.050 over the R0 control** — PASS bar +0.132 and PARTIAL bar +0.082 are BOTH unmet — at touch accuracy **103/139 = 0.741**; the card's non-gating non-serve arms read **86/127 = 0.677** vs R0 79/127 = 0.622 and the GT-touch arm 110/127 = 0.866, so a perfect count is worth +0.244 and the best re-derived count +0.055. **Step 5 (offline approximation of the STATUS gate, explicitly not the real gate): e1 0.706→0.706, e2 0.571→0.533, e3 1.000→0.929, e4 0.933→0.933, e5 0.923→0.923, e6 0.933→0.800, e7 0.750→0.500** — 4 of 7 outside ±0.01, but the R0 REPLAY is already off-record on 4 of 7 (e2 -0.171, e3 -0.071, e6 -0.133, e7 -0.250), so criterion (ii) as literally written is unsatisfiable by any replay; reported, not reinterpreted, and the verdict already fails on (i). Rule-relative R4 made no drill worse than R0 (+0.133 on e2, 0.000 elsewhere). **Step 6: NO `src/` change** — #68's +0.223 (non-serve +0.244) survives as an in-sample upper bound / diagnostic lever; what is refuted is recovering it by re-deriving the count from emitted contacts. **Three card defects reported to the coordinator (none reinterpreted into the verdict):** (a) criterion (ii) unsatisfiable as written; (b) **R2 is a no-op by construction** — the card mandates keeping the resolver's own `attack_before` reset in EVERY arm, which is exactly R2, so R2 ≡ R1 always (pinned by `test_r2_is_subsumed_by_the_base_attack_reset`); (c) G1's timing table and 0.589 reference only reproduce on the PRODUCTION stream over ALL region events — on the 12 FOUND serves alone the median is -0.5 f, not +23 f, and `evaluate.py` on the same data grades 0.437, not 0.589. **Next task (coordinator's):** the upstream contact-recall diagnosis on the same 14 `accepted < GT` points (open points 2/5), NOT a second touch-rule search. No new task card, no cards reordered, Log not archived.
- #70 **#68's LABEL BASELINE CORRECTED — the shipped stream is 85/139 = 0.612 (dump `action`) / 83/141 = 0.589 (`pipeline_output.json`), NOT 79/139 = 0.568; that figure is a REPLAY artifact** — caught by CARD TC1's executor, which refused its own G1 and reported instead of proceeding (the card working as designed). Cause: the `accepted` rows of `output/g3r1/match_bw03_diag.jsonl` carry **no `behind_baseline`** (0 of 185) while `src/recognition/action_context.py:167` reads it for the serve branch, so an offline replay is only **168/185** faithful and scores **0/12 on serves** against the dump's own 7/12. Four arms verified by the coordinator: dump `action` **85/139**, replay `behind_baseline=False` **79/139**, replay + real GT `touch_number` **110/139**, `pipeline_output.json` **83/141 = 0.589**. Split: non-serve 127 -> 78 / **79** / **110 (0.866)**; serve 12 -> 7 / 0 / 0. **The touch-count lever is untouched** (96/139 and 110/139 both reproduce exactly) and is in fact LARGER on the replay-faithful subset (**+0.244**). Corrected my own lever table too: all 25 region serves +0.177, 13 overpass labels **+0.092**, 15 `set↔dig` swaps **+0.106**, 12 far serves **+0.032**. Repairs: `docs/g3_touch_count_lever.md` §3 rewritten with a CORRECTION note and the `own_side_drive_block` caveat; CARD TC1's G1 expects the replay control and carries a REQUIRED CAVEAT, and its gate is restated as a **gain over the R0 control** (PASS >= 0.700 = +0.132 / PARTIAL >= 0.650 / FAIL) so it cannot turn on the baseline; open point 9 + the #68 index line amended. No `src/` change, no decode, no seek, no GT edit, held-out untouched; suite **1286**. Durable lesson: a replay arm is not a baseline until its fidelity to the shipped stream is measured.
- #68 **THE TOUCH-COUNT LEVER: the largest held-out label loss is Layer 2's possession count, not Layer 1's gesture** — `docs/g3_touch_count_lever.md`, transcript `logs/touch_lever_stdout.txt` (committed artifacts only; no `src/`, no decode, no seek, no GT edit, held-out session untouched). Three measured facts on `output/20260920_match_ari_joan_lost/pipeline_output.json` + `output/g3r1/match_bw03_diag.jsonl` (185 `accepted` rows) vs the 182 held-out GT events in f5240–f26147 at ±15 f: (1) **timing is NOT the bottleneck** — the signed delta to the nearest emission is median **−2 f** for dig (n=55) / set (46) / spike (38) / overpass (18), and only `serve` runs late (**+23 f**, n=25), so the #48 "41 of 44 missed contacts 7–69 f away" story is serve-specific and a global re-timing pays nothing; the recorded class accuracy reproduces exactly (**83/141 = 0.589**, record 0.590); (2) **Layer 1 is degenerate: the 185 accepted match contacts carry only 3 gestures — `bump_set` 157 (85 %), `attack` 16, `block` 12** — and the one gesture becomes dig 73 / set 40 / spike 24 / serve 16 / overpass 4, so the whole `dig`/`set`/`overpass`/`serve` decision is `ActionContextResolver._decide` (`src/recognition/action_context.py:175-219`) keyed on `_poss_touch` (lines 127-135); (3) **the lever is verified by replay** — substituting the real GT `touch_number` into the *unmodified* `_decide` over the 139 found held-out contacts lifts label accuracy **79/139 = 0.568 → 110/139 = 0.791 (+0.223)**, and on the **127 non-serve** contacts where an offline replay is faithful **79/127 = 0.622 → 110/127 = 0.866 (+0.244)**, while `touch_number` itself is only **96/139 = 0.691** — the largest single lever measured on this GT (all 25 region serves +0.177, 13 overpass labels +0.092, 15 `set↔dig` swaps +0.106, and the **12 far serves only +0.032**). **BASELINE CORRECTED in-session (seventieth session) after CARD TC1's executor refused G1 and was right: the shipped streams are 85/139 = 0.612 (the dump's `action` field) and 83/141 = 0.589 (`pipeline_output.json`) — 0.568 is a REPLAY artifact, NOT production.** The `accepted` rows carry **no `behind_baseline`** (0 of 185) and `_decide` reads it for its serve branch, so an offline replay is only **168/185** faithful and scores **0/12 on the serves** against the dump's own 7/12. TC1's gate is therefore restated as a gain over the R0 replay control. Residual after a perfect count: `overpass→spike` 10, `serve→dig` 9, `serve→spike` 3, `overpass→dig` 3, `spike→block` 2, `spike→set` 1, `set→overpass` 1 — so the count is necessary but not sufficient (`overpass` still fails its own `touch == 2 and no follow` rule). **Mechanism, first cut:** touch errors cluster where the pipeline emitted FEWER contacts than the owner listed — 11 points with `accepted >= GT`: touch errors 11/37; 14 points with `accepted < GT`: **32/102** (P19 18/13/**7**, P25 18/12/**6**, P26 11/8/**6**, P30 18/15/**5**, P23 7/6/**4**, P29 6/7/**4**, P33 4/5/**3**, P10 2, P13 2, P15 2, P22 1) — i.e. a missing contact starves `_poss_touch` and every later touch in that possession is numbered low; P18 (16/15) and P24 (7/6) are clean, so it is the *placement* of the missing contact, not the raw count. **In-sample upper bound, no rule proposed, nothing shipped** — wrote **CARD TC1** (READY, first card) to test a re-derived count offline on dev+entreno with one held-out shot, pre-registered PASS ≥0.700 / PARTIAL ≥0.650 / FAIL, and re-ranked *Active next* to put the label lever ahead of the far serve. **Trap found:** the GT touch number lives in `points[].events[].touch_number`, **not** in `points[].contacts[]` (only `events` carries it; reading `contacts` silently returns 0/139 — it bit me mid-session). **Defect found in passing (deferred, do not fix alone):** `src/recognition/action_context.py:193-194` is a duplicated unreachable `return VolleyballAction.BLOCK, 0.7` — dead code, no symptom, a landmine for the next editor of that gate.
- #66b **PG2 DONE, `point_map_alignment = PG1_VERDICT_IS_A_PAIRING_ARTIFACT`: PG1's `REFUTED/1` is a PAIRING artifact — window starts ARE serve-anchored; SR4-FAR is mis-keyed, not blocked** — `docs/point_map_seam.md`, `logs/pg2_report.md`, `logs/pg2_run.log`, `scripts/score_point_map_alignment.py`, `tests/test_point_map_alignment.py` (+49 tests; suite **1286** = 1237 + 49), plus a `## 7. Correction` pointer appended to `docs/point_map_alignment.md` (§1–§6 left byte-identical). Committed artifacts only: no `src/` change, no decode, no seek, no GT edit, held-out session `20260928_entreno_vall_dhebron` untouched, `scripts/score_point_map.py` unmodified. All three pre-registered criteria PASS: (i) **14 of 31** window starts within ±15 f of ANY GT serve (23/31 at ±30 f, 25/31 at ±60 f); (ii) **11.56×** chance — seeded Monte-Carlo `random.Random(20261002)`, 20 000 draws × 31 uniform starts over `[0, 26061)`, tol ±15 → **1.21 of 31** (observed range 0–7), while the ±15 f serve balls cover only **3.93 %** of frames (1023/26061); (iii) monotone order-preserving DP keeps **14 pairs within ±15 f at every skip cost** 60/120/240 f (27/28/28 pairs, unmatched 4/3/3, median −6/−8/−8 f, min −32/−171/−171). **G2 parity exact**: PG1's own scorer gives `start_hits_within_15f` = 1, `offsets_nonnegative` = 31, min/max/median **+6 / +3153 / +1700 f**, reading `uniformly late` — reproduced, and it decides nothing. **Seam**: far 11/17 `at_seam` (nearest start within ±15 f), **0** in a window interior, 6 in a genuine gap; near 3/16 `at_seam`, 11/16 inside — so #65's "far 14/17 in the gaps" is a **seam**, and PG1's geometric `inside_any_window` (far 2/17, near 14/16) is the same 16 serves bucketed differently (both geometric far rows P23/P25 are also `at_seam`; the scorer prints both). **Step 5** narrow `far_flight` (`width_start <= 28`, no sweep) keyed on window starts, one claim per start: ±10 and ±15 f → 16 claims, **far 11/17, near misclaimed 0/16, 5 unanchored**; ±20 f → 17/12/0/5. **IN-SAMPLE on the same 17 far serves — a re-test target, NOT a shippable rule** (STOP list, AGENTS.md §5), so SR4-FAR stays OFF. Two implementation notes recorded so nobody re-tunes them blind: the DP needs the tolerance-hinge reward (`100 − distance` inside ±15 f, `−distance` outside) — a plain `−|offset|` reward yields only 13 within-15 pairs; and card step 1(e) asks for a "sign-free" median of **−6 f**, which cannot be negative — the −6 f is the nearest-**boundary** signed median (nearest-start signed **−1 f**, sign-free **+17 f**, DP median at skip 60 −6 f), all three readings serve-anchored, so the verdict does not turn on it (reported to the owner, nothing re-tuned). Next task is the coordinator's far-serve rule keyed on window starts, re-tested out of sample with a non-serve control; the corrected-opener architect card is NOT justified by either run. No new task card, no cards reordered, Log not archived.
- #65 **PG1 DONE, `point_map_gate = REFUTED/1` — the point map is uniformly LATE, not aligned; SR4-FAR stays blocked on open point 22** — `docs/point_map_alignment.md`, `logs/point_map_report.md`, `logs/point_map_score_stdout.txt`, `scripts/score_point_map.py`, `tests/test_point_map_score.py` (+23 tests; suite **1237** = 1214 + 23). Committed artifacts only: no `src/` change, no decode, no seek, no GT edit, held-out session untouched. **Step-1 anchor REPRODUCED**: all 33 GT points carry exactly one `serve` contact and the serve IS the earliest contact, so the owner-dictated serve frame is the per-point start frame (the predicted `match_start_frame`, `window_is_prediction: true`, and `ground_truth/gt_point_start_end.txt` are explicitly NOT read). Ordinal pairing (GT P ↔ pipeline P-1): **`start_hits_within_15f` = 1 of 33** (bar ≥ 20; only P1 at +6 f), **`offsets_nonnegative` = 31 of 31** (the sign half of the gate PASSES), offset min/max/median **+6 / +3153 / +1700 f** → **uniformly late**; **0 of 31** windows contain their own serve; GT P32 (f25375) and P33 (f25807) have no pipeline point. **G2 parity PASS**, all 31 offsets identical to `output/pm1/probe.json` (0 mismatches). Gap side #64's claim scored: inside any window **16/33** (far **2/17**, near **14/16**), inside any inter-point gap **16/33** (far 14/17, near 2/16), inside the gap immediately before its own holder only **1/33**. Pre-registered **FAIL** ⇒ the map's STRUCTURE is the suspect (a constant re-timing cannot close a +1700 f median and still leaves far's 14/17-gap population unclaimed), so the corrected-opener architect card (the PASS branch) is NOT justified by this run and **SR4-FAR stays BLOCKED on 22**. No new task card, no cards reordered, Log not archived.
- #64 **PM1 `FAIL=blocked`: the far-serve record cannot bypass the point map; SR4-FAR is blocked on open point 22** — `docs/pm1_point_map.md`, `logs/pm1_report.md`, `logs/pm1_probe_stdout.txt`, `output/pm1/probe.json`, `scripts/probe_point_map.py`, `tests/test_point_map.py` (+23 tests; suite **1214** = 1191 + 23). Committed artifacts only: no `src/` change, no decode, no seek, held-out session untouched. Both gates green (G1 near 8/16, far 0/17, 12 FP; G2 plateau re-derived: far 16-27 px vs near 39-50 px, **16/17 far and 0/16 near at every cut 26/28/30/32**). Pre-registered FAIL: **UNBOUND (frame, side) 16/17 far hits with 294 false serves** (bar: >= 15/0 — first half PASS, second FAIL); **binding rule (iii) gap 11/17 with 35 FP**; **(ii) first-after 16/17 with 288 FP**; (i) contain 10/17 with 253 FP. So the *signal* is complete and no *binding* can make it precise — **the point map is the lever.** Reproduced #63: 31 pipeline points vs 33 GT points (P32/P33 have none), **0 of 17 far serves inside their own window**, and the ordinal-pairing offset is **one-signed +6 … +3153 f on all 31 pairs** (uniformly late, not noisy; #63's "1-1466 f" is the nearest-window offset, extreme -731 f at P32). **Far 2/17 inside any window vs near 14/16**; **16/33 serves sit in inter-point gaps**; 29/30 gaps clear `GAP_SERVE_MIN` 143 so the chasm rule selects nothing. [inferred] `_finalize_group` opens a point on a flight burst before the rally's first action. **Constraint handed to open point 22: move the opener to the serve / its rally.** No new task card written (per card), no cards reordered, Log not archived.
- #63 **SR4 REFUTED AS SPECIFIED (architect call + coordinator re-measurement; nothing built, `src/` untouched)** — `docs/sr4_architect_call.md`, memo run in `logs/architect_sr4_ds_run.log`. The serve record cannot be a single post-hoc rule. **Near coverage ceiling is 13/16** (P5 -81 f, P7 -108 f, P24 +29 f: no own-side action within +-15 f), so the planned 15/16 bar is unreachable by hindsight work and **SR4-NEAR is parked on perception**. **The far-side side signal is new and strong**: ball width at flight onset 14-23 px at all 17 far serves vs 39-52 px at the 3 near serves that have one, plateau 26-32 px -> **far 16/17, near 0/16 misclaimed**. **But 0 of 17 far serves fall inside their own point window** (31 pipeline points vs 33 GT points; each point starts 1-1466 f AFTER its own serve), so binding costs 5-7 true serves for 2-8 false records and every suppression rule trades them 1-for-1. **Next = the point-map probe** (post-hoc, decides bypass vs open point 22), then SR4-FAR. Also fixed a delegation harness bug (prompts >~1 KB kill the child `pi` with EXIT 137 on every model — briefs must be files the child reads).
- #62+ **SR4a DONE (delegated worker card; diagnose-only, `src/` untouched)** — `scripts/probe_near_openings.py`, `docs/sr4a_near_openings.md`, `logs/sr4a_report.md`, `tests/test_near_openings.py` (+35 tests; suite **1191** = 1156 + 35). G1 reproduced on both arms before any bucket was read: near 8/16, far 0/17, 12 false serves, drills e2-e7 3/5. The 8 match near misses bucket into **2 `emitted_mislabeled_opener` + 3 `emitted_not_opener` + 3 `not_emitted`**; drills into 3 hit / 1 mislabeled / 1 not_emitted. **G2 verdict 1: SR4's near side PROCEEDS after the fact — 5 repairable of 8** (rule >= 4). **G2 verdict 2: M-b is REOPENED as a fresh architect call only (NOT a build) — 3 never produced, 2 of them coasting** (P5 f2575 and P7 f3747, lowest-foot same-team track `predicted: true`; rules >= 3 AND >= 2); the diag dump has NO recorded arm, so the call must re-run with the arm named. SR4 still goes first (no `src/` change). Trap guard `far_unseen_near_reception_first` = **0** of 17. Design constraint for SR4 (inferred): only 4 of the 8 hits have a `serve` as their window opener, and 6 of the 12 false serves sit inside a near-miss window. One card deviation disclosed (the clip-opening serve has no preceding action; the probe follows `relabel_serves.resolve_point` and opens at video start, else G1 fails at 0/5).
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

### 2026-10-05 (eighty-third session) — #83: TEAM IDENTITY RESOLVER — labels survive side switches by structure (orientation change-point + within-side slots), not by appearance alone

**Asked (owner):** player tracking works until a side switch, then players mix and swap boxes; build a system that reliably re-attaches the same player id to the same player across switches (not every frame -- actions are ~10% of frames, a few wrong/blank frames are fine); generalise, do not overfit the one video; 5 stills shared (not committed). Plan approved (AskUserQuestion): the online team resolver first; a post-hoc pass only if online is not enough.

**Diagnosed (code-reading; no footage in the cloud container):** the #82 resolver has (1) no team constraint (P1A near + P1B far possible), (2) self-reinforcing position continuity (`_label_pos` follows whichever body holds the label, +0.4 bonus vs weak far sims -> a swap never corrects), (3) enrollment only sees each squad from one view, so post-switch comparisons are cross-view and biased toward "no change", (4) `_adapt_reference` drifts references toward whoever holds the label (corruption after a wrong lock-in). Labels also feed the tracker's enrollment guards (`_enrollment_holds`), so changing them changes tracking.

**Built:** `TeamIdentityResolver` (see Where we are) as a pure observer with its own label map; the #82 resolver keeps writing `_track_labels` for the guards -> tracking identical in both modes (pinned). Enrollment refs gained `identity_samples`/`identity_heights`. `PlayerTracker.update(..., frame_index=)`, `label_for(tid, frame=)` (contact-frame history, emission fallback), `identity_state()`. FrameProcessor passes frame_index and labels actions at `frame_number` (also fixes the end-of-video flush labelling actions with the FINAL tid->label map). Config: `player_identity_mode` "team", `_switch_threshold` 40, `_switch_drift` 0.5, `_min_switch_interval_frames` 900 (+ drift-guard rows). Design corrections found during the build: teammate-only impostors are fooled by mixed teams -> all-player impostors + same-view fit (Learnings); a held label survived a silent cross-net swap for 2-5 frames -> 30 f gap reset, quick-EMA hold break, 5 f claim delay, elimination only with a decided partner, instant doubt.

**Measured (synthetic only):** stable rally 0 wrong; 3 consecutive switches with scrambled ids: flip 10-11 f after reappearance, 0 wrong labels (blank instead), all views learned; occlusion 0 flips; silent teammate swap 2 wrong frames then corrected; ~3 ms/frame at 640x360 with 4 bodies. Suite 1475 passed (+19 resolver, +7 probe, +4 drift rows); the 4 failed + 42 errors are the pre-existing missing-`output/` artifacts (identical set before/after).

**Not done / owed:** real-footage run (owner: `scripts/probe_identity_switches.py`, pre-registered reading in open point 2); fresh entreno A/B (§1; action F1 unchanged by construction). E2 drift observers are subsumed by the resolver's doubt/flip diagnostics.

### 2026-10-05 (eighty-second session) — #82: labels renamed to team letters, readable colours, per-frame identity resolver, f151 teammate id-swap fixed

**Asked (owner):** (1) first/second player of a team = P1A/P2A (team B = P1B/P2B); (2) the dark navy is unreadable on black; (3) players must stop swapping ids -- a pre-video pass over colours/features so a label sticks from start to end (only in-court bodies; full matches, not entreno; side switches every 7 points). Follow-up contract: a momentary loss/swap/steal is fine as long as the same id returns to the same person after some frames.

**Found:** labels were never reassigned (`_track_labels` only changes on removal); the f189 flip was a TRACKER id swap at f151 -- `_may_feed_track` stopped feeding P2A's track (off-court hold 90 f expired, her detection sits just off the sideline) and Hungarian paired it with her teammate's box.

**Changed (display + one guard):** enrolled tracks keep feeding off-court while the detection matches their reference (`tid` param on `_may_feed_track`/`_compute_assignment_cost`); label text = number + team letter (`_build_reference`); `PLAYER_SQUAD_COLORS` vivid blue/red (contrast >= 4.5 on black, tested); `PlayerTracker._resolve_identities` per-frame resolver (config `player_identity_resolver`, `player_identity_court_slack_px`); slow reference drift for lighting/side switches (not validated on a real switch).

**Measured (20260920 match, f1-2500):** f74/f189 correct; label teleports 10 -> 6 (all one id hopping between two people at f1305-1363, tracker-side), label changes 4 -> 25 (more None flicker, fewer wrong-person labels). Suite 1569 passed. Full 26k-frame run NOT done; no identity GT exists.

### 2026-10-05 (eighty-first session) — #81: player enrollment (E1) + squad colours (E3) shipped: sticky P1A/P1B/P2A/P2B labels, squad-stable colours on boxes and actions, tracking byte-identical (gate ΔF1 0.000 ×7)

**Asked (owner, m00001):** make player tracking bulletproof — a pre-pipeline step
sampling the opening frames to extract features so the same player always gets the
same number; live debug colours one team 2 blues (clear/dark) and the other 2 reds
(clear/dark); a re-appearing player must regain number AND colour; open to proposals;
worried about tracking a wrong person and voiding the video; side switches should
unblock automatically. **Plan approved m00055/m00056:** names P1A/P1B/P2A/P2B
(left→right), colours follow the TEAM not the side, enrollment window = first ~600
frames stride 5, E1+E3 this session / E2 (identity-drift + side-switch observers,
display/diag only, owner gate) next session, batch overlay gets the same colours,
`20290928_entreno_vall_dhebron` stays held-out (players substituted — never run).

**Design pivot (deliberate, safer):** enrollment does NOT seed tracker positions and
does NOT skip the in-stream k-means bootstrap — all GT-validated bootstrap/admission
machinery untouched; enrollment only supplies reference signatures + a tid→label map
attached greedily in-stream. Avoids the position-mismatch-at-frame-0 problem and
keeps one shared path (§2 live-debug parity).

**Shipped:**
- `src/tracking/player_enrollment.py` — `_Chain` dataclass (running hist means),
  `PlayerEnrollment.enroll(video_path)` → Optional[List[ref dicts]] guarded on
  `enabled`/`is_calibrated`; sequential decode ≤600 frames (§9), detector every 5th
  frame, strict foot-in-court filter, per-obs ensemble signature via
  `tracker.compute_enrollment_signature`; `_build_chains` greedy ONE-TO-ONE per
  sampled frame (best (correl, −dist) pair first; ≤1 obs per chain per frame —
  without this two players within the 120 px gate both fed ONE chain, 4 players → 2
  chains, caught by the no-2+2 test); `_merge_chains` (gap ∈ (0,60] f, endpoint
  ≤120 px, cross-corr ≥0.45); ≥8 obs chains, squads by majority side (near = 1),
  slots left→right at the earliest shared frame; refs = averaged histograms + world
  size samples (compatible with `_signature_similarity`).
- `src/tracking/player_tracker.py` — `label_min_similarity` ctor param,
  `_enrollment_refs`/`_track_labels` state, `set_enrollment()` (clears labels),
  `enrollment_active`, `label_for(tid)`, `compute_enrollment_signature(frame, bbox)`,
  `_maybe_assign_label` on create/update (greedy best-unclaimed, sticky),
  `_stamp_identities` on all three `update()` returns; labels cleared on
  expiry/eviction, KEPT through retire-to-gallery (restore = same tid = same label).
- `src/output_gen/overlay.py` — `PLAYER_SQUAD_COLORS` (1,A) clear blue / (1,B) dark
  blue / (2,A) clear red / (2,B) dark red; `player_box_style(player)`;
  `draw_player(..., color=, label=)` explicit-colour precedence over action tint.
- Wiring: `FrameProcessor.enroll_from_video(video_path)` (config-gated); called in
  `VideoProcessor.process_video` + live `_process_two_pass` AND
  `_process_buffered_live` before the loops; live `PlayerOverlay` 4-tuples + panel
  rows carry label/squad; `json_exporter.collect_actions` projects `player_label`
  onto exported actions (explicit key list — a new action field must be added there
  or it silently vanishes; cost one debug loop this session).
- Config: `player_enrollment_enabled` True / `_frames` 600 / `_stride` 5 / `_min_obs`
  8 / `_chain_gate_px` 120.0 (venue-coupled) / `_chain_gap_samples` 6 /
  `_merge_gap_frames` 60 / `player_label_min_similarity` 0.35 — drift-guard rows
  added (85 pass).

**Validation (pre-registered gate):** unit parity — byte-identical tracker outputs
enrollment on/off (scripted gather/drift/swap/occlude, `cv2.setRNGSeed(0)` per arm);
end-to-end — fresh A/B both arms (git worktree @ HEAD d2414f1 vs working tree), all
7 entrenos: action F1 e1-e7 Δ = **0.000** on 7/7, tracker snapshot streams
(tid→frame/bbox) byte-identical on 7/7, **56/56 actions carry a player_label**; e1
engagement: 4 refs from 294 samples / 8 chains, labels assigned by frame ~8 at
similarities 0.51-0.93. Suite **1549** (+10 enrollment incl. occlusion-merge 10+10
→20 obs, label stickiness across position swap, gallery retire+restore,
<4-chains/no-2+2 fallbacks; +7 squad-colour overlay tests). Enrollment adds no
measurable wall time (441-frame clip: 46 s base vs 36 s enrolled — run noise).

**e2 caveat recorded:** the recorded e2 baseline 0.571 reads **0.400 on BOTH fresh
arms** — pre-existing fresh-run/MPS variance in the BASE itself, both arms equal;
open point 1's rule ('compare A/B, never vs recorded') now covers e2 explicitly.

**Discipline:** one mechanism (E1+E3 as one approved unit, no E2); no GT edit; no
seek (§9 — sequential decode); held-out untouched; GT-validated tracker machinery
untouched by design; STATUS updated per the lean convention (#77 log entry moved
verbatim to `docs/history/status_log_archive.md`).
