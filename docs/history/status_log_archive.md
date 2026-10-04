# STATUS.md archive — Log entries 2026-08-14 → 2026-09-27 (twenty-first session onward)

> Provenance: the detailed session log entries that used to live in
> STATUS.md's "Log" section, moved here VERBATIM on 2026-09-27 when the live
> Log was reduced to the most recent sessions (and again on 2026-10-02 for
> entry #53). Entries are appended chronologically within the archived block,
> i.e. OLDEST-FIRST; read from the bottom for the newest.
> The compressed per-session summaries live in
> `status_where_we_are_archive.md` (same directory); the one-line-per-session
> index is in STATUS.md. Nothing was edited or deleted.

### 2026-10-02 (seventy-second session) — #72: the REACH-GATE CASCADE is REFUTED offline — admitting the reach-blocked contacts DAMAGES the labels; the recall→count→label chain holds about the error POPULATION but earning the recall does not earn the count

**Asked:** continue the coordinator loop toward G3 (standing "Continue"). Session
died mid-STATUS-ritual (no commit, no index/log entries — completed by #73); its
measurements and doc were verified and committed as found.

**The measurement (`docs/g3_reach_cascade.md`).** Offline replay of the UNMODIFIED
`ActionContextResolver` (imported, never copied) over `output/g3r1/match_bw03_diag.jsonl`:
base arm = the 185 `accepted` rows; arm K = base plus every `reason="reach"`
rejection whose overage `distance / reach <= K` (the gate's own recorded numbers
re-scored offline), replayed in frame order; scored against the 182 in-region GT
events (f5240–f26147) at ±15 f, nearest-emission matching, exactly as #68/#71.
`behind_baseline` fixed False everywhere (the #70 replay artifact), so the base is
a REPLAY control and every arm is a delta over THAT.

**The result: BASE 78/139 = 0.561 label, 90/139 touch. K=1.1 +4 found → +1 label;
K=1.2 +14 found (all 14 within ±15 f of a GT contact — the precision-clean gate
#71 recommended) → −4 LABELS; K=1.3 +21 → −5; K=1.5 +28 → −1; K=2.0 +48 → +1 at
rate 0.513 vs 0.561.** Admitting ALL 71 reach rows repairs only **9 of 49** wrong
touch numbers (40 still wrong): the count is driven by the resolver's own resets,
not by recall. The architect's "~0.00 class accuracy" caveat is CONFIRMED and
slightly optimistic — the honest expectation is NEGATIVE.

**Verdict.** The recall → count → label chain is real about WHERE the errors live
(the 44 missed contacts) but relaxing the gate does not convert them into correct
labels — the newly admitted rows mostly renumber touches wrongly. **CARD RG1 is
NOT written; the pose-anchored reach inherits the same failure** (same 20 contacts
through the same resolver; its only distinct argument was scale-freedom, not a
label argument). **The 44 missed contacts are a RECALL story (contact P/R,
per-point completeness — open points 2/5), NOT the path to 0.70 class accuracy;
do not spend a GPU A/B on them while the goal is the class metric.** The label
bucket's two count routes are both measured and closed (re-derive: TC1 +0.050;
earn-by-recall: #72 negative), leaving 39 of 55 wrong labels with a wrong count
and 16 with a CORRECT count (the Layer-1/2 rule errors open point 9 names).

**Discipline:** no `src/` change, no decode, no seek, no GT edit, held-out session
untouched. Trap recorded in the doc: gestures must be passed as the `VisualGesture`
enum — a plain string silently skips the ATTACK/BLOCK branches (#71 harness bug).

### 2026-10-01 (fifty-second session) — possession signal built, REFUTED, parked default-OFF (`src/` untouched)

**Asked:** create a possession signal (open point 9's enabler for overpass and
for the 34 genuine side errors). Diagnose the team errors first, then build.

**Diagnosis.** Joining the G1 rows to the diag's attribution provenance:
`width` target 76 correct / 13 wrong (0.85 precision), `carry`/`flip` 14 / 21
(0.40), `none` 15 / 0. The weak link is the same-team carry fallback used
whenever the strict width regime abstains; a gated width TREND decoded the
arriving side at precision 1.00 on the strict-abstain contacts it covers.

**Built (both requested mechanisms).** (1) A ball-field width-trend fallback
(`_width_side_trend`: median split of `ln(width)` over 15 frames, commit at
`|dln| >= 0.20`) after the strict width step in `_attribution_target`. (2) A
motion-history convergence tie-break (`_motion_convergence`: candidates within
60 px of the closest re-ranked by the cosine between their recent trajectory
and the direction to the contact) in `_closest_player_at`. Config keys +
drift-guard rows + 18 unit tests.

**Measured, then refuted.** Entreno/dev: effectively neutral (the e1 "team
flip" was run-to-run NONDETERMINISM — two reruns without the mechanism gave
different results; dev shifted only one L-R `player_id`). The decisive offline
replay of the REAL attribution methods on the match dump (157 GT-side
contacts): base **121/157 (0.771)** → both **122/157 (0.777)**; the trend fires
11x and is **11/11 on the correct side** but mostly redundant (base already
resolved those contacts); motion changes **0** team attributions. The carry
errors it targeted mostly have NO ball signal at all (ball lost mid-flight),
which no ball-field rule can recover.

**Parked per T5/R1.** `src/`/config/frame_processor/tests reverted to HEAD;
the mechanisms live default-OFF in `scripts/possession_signal_harness.py`,
with the evidence in `scripts/probe_possession_signal.py` +
`docs/g3_possession_signal.md` (+20 tests). `git diff HEAD -- src/ tests/` is
empty.

**Environment incident.** A concurrent pi session (G4/#51) was committing in
this repo during validation: my `git stash` swept its uncommitted files and the
first match A/B "new" arm never had my changes. Recovered cleanly (its files
intact, 985 tests green). Rule: never run two sessions on this repo at once.

**Suite:** **985** (+20). **Next:** S4 (consume the serve events) or a
NON-ball possession signal.

### 2026-10-01 (fifty-first session) — G4: serve-EVIDENCE event emitters (far flight + serve runway), scored against the 17 GT far serves

**Asked:** (1) "add the far-flight detector as a new event that we can use to
decide"; (2) the server "is sometimes not tracked because he is outside the
court" -> "create an event emitter that includes any person that is inside the
two side lines if they were to continue at infinitum, and outside of the court,
that is behind the far line and in front of the near line"; "the serve must
come from a player in this area with the ball and with a contact. With these 2
together we might be able to detect more."

**Diagnosed first (no `src/` touched).** Over the 17 GT far serves of the beach
match with raw person detections: a STRICTLY-behind-the-far-line region sees a
person at only **7/17**, because far-side servers often stand ON the line (and
their 85-160 px boxes are what the detector returns, not the ~7 px the 4-corner
homography predicts -> far-end metre gates are meaningless here). A band
straddling the line sees one at **17/17**, so the band straddles and is
expressed as a FRACTION of the court's projected depth (venue coupling,
AGENTS.md §7). Raw ball detections show a growing-width far flight in the
window at 10/17, and a far ball is detected on only ~1 frame in 4.

**Delivered.** `src/analysis/serve_events.py` (`ServeRunway` image-space wedge
+ band, `FarFlightDetector`, `ServeRunwayWatcher`, `ServeEventEmitter`), wired
into `FrameProcessor.process_frame` as pure observers behind
`serve_events_enabled` (default OFF, `--serve-events`); inert read-only side
channels `PlayerDetector.off_area_detections` (person boxes the play-area filter
dropped) and `BallDetector.raw_detections` (pre-static-suppression ball
candidates, the AGENTS.md §6 escalation path); `serve_events` key in
`pipeline_output.json` only when they ran; `scripts/score_serve_events.py`
(+`--control`), 45 tests, `docs/g4_serve_events.md`. Suite 965.

**Two corrections the first scoring run forced.** The far-flight onset gate was
the foot band, which rejects the contact itself (the ball is at hand height) and
then rejects the whole flight (it rises to y~306, above the wedge apex at 504)
-- it is now gated on the NET line. And runs were consecutive-only, which throws
away a 1-frame-in-4 ball -- they now tolerate `far_flight_max_gap` (3).

**Measured** (windowed replay through the real `process_frame`, GT far serves vs
24 mid-rally non-serve control windows):

| event | far serves (17) | held-out (12) | control (24) |
|---|---|---|---|
| `runway_occupant` near the serve | 15 | 10 | 18 |
| ... genuinely off-court | 7 | 5 | 5 |
| `far_flight` in window / at +-15 f | 11 / 4 | 9 / 3 | 14 / 8 |
| `serve_candidate` in window / at +-15 f | 6 / **3** | 5 / **3** | 4 / **1** |

Contact-level: **3 hits vs 1 false positive** (P25 d=13, P26 d=6, P32 d=6)
where production scores **0/12** held-out. Honest read: E2 (runway) is the
strong leg and it confirms the owner's premise (the server is usually DETECTED
but not trackable); E1 alone is a weak discriminator (4/17 vs 8/24 control, S1's
kill 2 reproduced held-out) and only pays off after E2; the conjunction is a
real but thin signal, an evidence stream for the G2 decision, not a fix.

**Workspace note:** an external `git reset --hard` in this repo reverted the
tracked-file edits twice mid-session; the work is committed (5b678b2) and the
patch is also kept at `/tmp/apply_serve_events.py` for re-application.

**Next:** the owner decides between consuming `serve_candidate` as post-hoc
serve EVIDENCE (never as a label) and pushing the ball side, where the measured
bottleneck is detector/temporal (a far ball is seen 1 frame in 4; half the
far-serve windows show no growing run at all).

### 2026-10-01 (fiftieth session) — G3 overpass net-crossing diagnosis: the ball-width crossing signal is REFUTED (`src/` untouched)

**Asked:** continue the next point that moves the needle for G3 after the
whole-match GT landed. G2 (far-serve lever) is an owner decision, S2
owner-gated and S1 refuted; the largest held-out loss is the gesture LABEL
bucket (57/183) and its worst class is `overpass` (0/18). Open point 9's
declared fix — thread the ball-crossing signal into the resolver — was the
unblocked worker candidate, so run it diagnose-first.

**Delivered.** `scripts/probe_overpass_crossing.py` (+19 tests,
`tests/test_overpass_crossing.py`) + `docs/g3_overpass_crossing.md`, artifacts
`output/g3_overpass/overpass_crossing.json`; no `src/` change, no decode.
Inputs only: the match contact GT, the production perception stream
(`serve_relabel.json` `actions_pass2`), and the match diag dump
(`output/g3r1/match_bw03_diag.jsonl` — ball tracking is gate-independent, so
the labels are read from production, never the dump's own actions).

**Headline (pre-registered kills).** On the 18 held-out GT overpasses the
ball-width regime (near > 35 px / far < 26 px) flips across the contact at
only **3/18**, indistinguishable from the non-attack controls (set 4/46, dig
10/55) — **K1 (signal present) and K2 (separation) both FIRE**. The ball is
tracked on BOTH sides at **18/18**, so it is NOT a detection gap (**K3
clean**): the crossing sits at the net/tape where the width regime abstains,
and a high lob reads ambiguously on both sides. The perceived next-contact
team is no substitute either (overpass next-team flip 8/18 = 0.444 vs controls
0.582; **K4 fires**). Verdict: **the ball-crossing resolver lever is
REFUTED**, same class as S1/T5/R1.

**Why (mechanism breakdown).** The overpass loss is a LABEL/RULE problem, not
geometry: `ActionContextResolver` emits `overpass` in exactly one place — a
bump-set at touch 2 with no follow within `rally_reset_gap` — while the owner's
GT overpasses span touch 1/2/3. The emitted reads nearest the 18 GT overpasses
were dig 6 / spike 5 / set 2 / **missed 5**. The resolver's touch/gesture read
(t1→dig, t3 near-net→spike, t2-with-follow→set) sends the rest to the wrong
label, and the stream's own possession/team signal (G1 side-level 0.755) is
too noisy to supply the crossing structurally.

**Then the code change was scoped (all refuted).** The diag dump's
`candidate_passed_gates` records carry the resolver's own inputs, so
`ActionContextResolver` was replayed offline (imported, not reimplemented) with
three candidate overpass rules on top of the baseline. **All net-negative on
P9–P33**: baseline 85 correct / 0 overpasses; next-team crossing 71 (3/18
recovered); no-follow net bump-set 80 (3/18); next-team + ball-side 82 (0/18).
Since no rule passes, no `src/` change ships (T5/R1 precedent). The blocker is
upstream — a reliable next-toucher/possession signal (the 34 genuine side
errors).

**Suite:** **920** (897 + 23). No `src/` change (`git diff 185c6f0 -- src/`
empty).

**Next:** the enabling work (a reliable possession/next-toucher signal) before
any overpass rule; or the G2 far-serve decision / S4 (`pass2_squad`). The label
bucket remains the largest held-out loss. Owner-side capture-spec rewrite
(point 29) still open.

### 2026-09-30 (forty-third session) — open point 21.3 point winner/outcome layer SHIPPED as a pass-2 script (no `src/` change)

**Asked:** continue open point 21.3 (the owner's match-feedback backlog item 3
/ G1 critical path): a post-hoc point winner/outcome layer over
`episode_point_map.json` + `serve_relabel.json` + `pipeline_output.json`, no
video decode, no `src/` change, validated against the 33 dictated winners. A
draft (`scripts/resolve_point_winners.py` + `tests/test_point_winners.py`)
had been left in the tree untracked and unreviewed; the 42nd STATUS said the
next session touching 21.3 must decide its status.

**Reviewed + landed.** Mechanism: a fault prior over the terminal LIVE touch —
the side of the last in-window pipeline action (minus the serve layer's
owner-verdict demotions) loses the point; winner = the other COURT SIDE (A
near / B far, the perception stack's letters). Structural-only abstains;
doubt = `confidence: low` + flags. GT-leakage is prevented structurally by
field projections: the map contributes `point`/`window_frames` only, the serve
layer `team_emitted` + override FLAGS only; the 13 winner-serves-derived
`team_resolved` overrides are never inherited (inheriting them would buy 3
points -> 21/33, not shipped). Ball-death side/in-out is absent from every
artifact, so kill/ace endings stay misses, not guesses; spike outcomes are
reported as evidence only (4/10 as a rule).

**Result vs the 33 dictated winners:** 33/33 decided, **18/33 correct =
54.5%** after the `--validate`-only side->squad mapping (GT switch schedule
[7,14,21,28]). Misses: 8 terminal-touch attribution (the same far-serve/side
gap as point 22), 3 kill/ace (ball-death absent), 3 serve_team_misattribution
(far serves emitted with the wrong side; pass-2 override refused), 1
owner-pinned serve outside the window (P20 ep45 family). Full table +
taxonomy: `docs/point_winner_layer.md` (raw run in
`logs/point_winner_report.md`, git-ignored).

**Verification.** Found and fixed 3 test-side defects in the inherited draft
(a `None`-window fixture that could not construct; an outcome-signal fixture
whose resolution frame sat outside its own window; a game-state death-frame
off-by-one contradicting the file's own `test_ball_death_from_game_on_run`).
`venv/bin/python scripts/resolve_point_winners.py --validate
ground_truth/20260920_match_points.json` reproduces `output/point_winners.json`
and `logs/point_winner_report.md` byte-identically; full suite **782** (755 +
27). No `src/` edit, no decode, entreno-neutral by construction.

**Verdict / next:** P2/P4/P6/P8 are exactly the 0/5 far-serve points from
#42 — the winner layer makes the consequence explicit (its terminal touch is
the receiver's dig). The layer is the G1 plumbing for 13 (ace / serve-fault /
assist); it ships as an honest baseline and should be consumed only after
S1–S3 make the terminal touch and the serving side real. The dominant miss
class is terminal-touch attribution, not winner logic — no winner-layer
heuristic can fix it.

### 2026-09-30 (forty-second session) — architect strategy review: G3 generalization plan re-ranked; far-serve CONTACT is the shared gap (docs-only, `src/` at `185c6f0`)

**Asked:** an external LLM proposed that generalization pain is structural
(pixel-constant Layer 1) and prescribed detector v4 → scale-free
normalisation → learned gestures, keeping contact triggering and the
resolver as-is, with G1/G2 then unblocked by pass-2. The owner asked the
tier-2 architect to challenge it against STATUS/tried-and-failed and give a
strategy that achieves G3 and enables G1/G2. Output = decision memo; this
entry records it.

**Verified against the repo (each hinges a rejection).**
- *Detection first:* T4 waterfall stage-1 = 0/28; detector conf 0.74–0.87 at
  all 5 lost dev serves, ≥0.86 at every anchored match serve; no second-venue
  footage exists and v2 was already rejected. Only the pre-contact toss is
  absent on P4/P6/P8; even a perfect history restore (T5-B) only moved the
  loss to `no_contact_geometry`.
- *Normalise, then retune:* R1 already used ball-widths/frame and was refuted
  on the held-out match (P11 f7132 at 0.285 bw/f). The far serve moves along
  the camera axis (image-plane speed small in any unit); "retune jointly" =
  fit 7 clips of one session. Normalisation stays worth doing as a
  perturbation-tested invariance property (T7/T9/T10), not as a retune.
- *Learned gestures:* labelled contacts = 91 (63 entreno + 28 dev); the 207
  match actions are predictions. R2 (LOCO, 2 features) already failed: pooled
  AUC 0.172 vs 0.551. The label bucket is the smallest dev loss (4/28).
- *Keep contact triggering as-is:* wrong — contact proposal is the largest
  loss (11/28).
- *"G1/G2 are pass-2 and need no visual generalization":* wrong at contact
  level — see below.

**New finding (hand-checked, `output/serve_relabel.json` vs
`ground_truth/video_ari_joan_8_first_points_annotations.json`, identity offset
0):**

| point | GT serve | pass-2 "serve" (was) | Δ frames | what the relabeled contact really is |
|---|---:|---:|---:|---|
| P1 | 210 | 247 (dig) | +37 | GT reception f245 (dig, team A) |
| P2 | 880 | 930 (dig) | +50 | dev in-point-spurious dig |
| P4 | 2154 | 2195 (dig) | +41 | dev in-point-spurious dig |
| P6 | 3038 | 3070 (dig) | +32 | GT reception f3071 (dig, team A) |
| P8 | 4770 | 4801 (dig) | +31 | GT reception f4800 (dig; team flag = post-switch loss) |

0/5 within tolerance. So the point-level far census 8/8 (and 31 serve-typed)
is bookkeeping: G1's ace / serve-fault / who-served and the receiver's dig
are wrong for these points. (Match-wide 12 of 16 far serves carry a team
override; whether P13/P15/P27, emitted as `serve`, are real serve contacts is
unknown until S0.)

**Decision (memo):** do NOT adopt the proposed order. Strategy = measure
in-domain (S0 owner contact GT P9–P33, S0b contact-level score) → fix the
contact proposal where the loss is (S1 diagnose-only far-serve looming probe
with pre-registered kills; S2 owner-gated mechanism only if it survives) →
pass-2 layers on real contacts (S3 side-switch squad layer, S4 winner →
ace/assist → fantasy) → learn last (T12 only at ≥3 recording sessions of
contact GT, leave-one-SESSION-out). Full S1 spec and kill criteria: *Active
next*. Deferrals with triggers (detector v4, T6, T7, T8, T9, T10, T12, R2):
*Active next*. Owner-side lever: pin the capture spec in
`docs/video_recording_guide.md`.

**PROPOSED `AGENTS.md` wording — NOT applied, owner ratification pending:**
- §1 add: "Entreno e1–e7 are the regression/neutrality suite, not a
  match-domain validation set (all seven are one session; R2 held-out correct
  rate dev 0.276 vs entreno 0.56–1.00). A threshold or model fit on dev
  P1–P8 ships only after it holds on data it was not fit on — contact-level
  match GT P9–P33 once dictated."
- §6 append: "Pass-2 layers are scored at CONTACT level (`evaluate_timed.py`
  on `actions_pass2`), not only by point census: far census 8/8 is 0/5 at
  contact level on P1–P8, three being GT receptions relabeled as serves."
- new §7: "Learned heads (plan T12) wait for contact GT spanning ≥3 recording
  sessions; validation is leave-one-SESSION-out (e1–e7 = one fold)."
- Also pending: `docs/action_reliability_plan.md` (T11's first instance =
  S1; T6/T7/T9/T10/T12 triggers) and a `ground_truth/README.md` line for the
  P9–P33 contact file when it lands.

**Uncertainties recorded by the architect:** 5 dev positives make the S1 gap
fragile (how R1 died); width noise at 13–17 px is ~±7%/px and the expected
growth over 0.5 s depends on an unmeasured camera distance; dead-time
throw-backs may loom like a serve (point 14a refuted a crossing-based serve
detector on practice footage) — hence the secondary feature is declared
before any held-out look; emission latency ≈ 0.5 s + `CONTACT_DELAY` (causal,
needs a live-debug check); if S1 kill 1 fires the detector-mining lever wins,
narrowly and targeted. P8's letter/side convention in `serve_relabel.json`
(expected B far vs GT serve team A after the switch) was NOT resolved here —
check when S3 lands.

**Housekeeping:** the 39th-session Log entry moved VERBATIM to
`docs/history/status_log_archive.md`. No code, GT, or `AGENTS.md` edits.
Suite unchanged (755).

**Next:** owner: S0 (P9–P33 contact dictation) + capture-spec doc + ratify
the AGENTS.md wording; worker: S0b, then S1 (one session each).

### 2026-09-30 (forty-first session) — G3 R1 departure gate: full validation cycle; REFUTED on the held-out match; parked T5-style (`src/` back at `185c6f0`)

**Asked:** continue session 40's uncommitted R1 work (the owner-approved
departure gate; implementation was in the tree, validation had never
run). Delegated to the worker subagent; the coordinator verified every
gate against raw artifacts.

**Validated (all `--device cpu`).** Offline re-measure on the
classifier's OWN history held: 7/85 flagged (5 `fp_in_point` + 2
`fp_dead_time`), 0 correct, max flagged 0.287 / min unflagged-correct
0.383 bw/f. Entreno: 6/7 byte-identical; e4 0.933→1.000 via FP f388
(0.287) — record F1s equal everywhere (e2's src.main 0.400 vs script
0.571 = the pre-existing gap, open point 6). Dev (`evaluate_timed
--ignore-player`): contact P 0.586→**0.739**, R 0.607 unchanged, F1
0.597→**0.667**, FP/dead-min 2.703→1.351, exactly the 6 flagged FPs
(f2195/f2414/f2445/f2494/f3265/f3639), 0 additions; points matched 6→5
(the game-state observer losing a window a dead-time FP had kept alive —
reported, not tuned); waterfall shows `low_departure` at
4_candidate_gate. Match (held-out; arms = same code, yaml-only
`contact_min_departure_bw` 0 vs 0.3): **bw0 ≡ production** (207 actions,
action-set identical to the posegate run; pass-2 chain reproduces 8/8
far census, 31 serve-typed, 17/17 owner verdicts, 31/33 points). **bw03
REFUTES**: 22 net removals including **P11's owner-confirmed serve f7132
(0.285 bw/f)**, 6928A, and P11's rally cluster (7160–7345) → owner
verdicts broken (P11 resolves at f7160), points **31/33→28/33** (P29–31
lost), far census **8/8→7/8** → STOP reported per spec; threshold NOT
tuned to the match. P1–P8 removals all ≥37f from GT contacts.

**Root cause.** Width-normalised departure conflates the dead/lost-ball
FP class with far-side float serves (a far toss is a slow float in bw/f —
the same physics that refuted T5). The dev-fitted empty gap does not
transfer to the match domain.

**Owner decision (option (a), T5 precedent 8140711): NOT shipped.**
`src/` (+ `contact_min_departure_bw` key, drift rows, 15 gate tests,
script kwarg) restored to exactly `185c6f0`; `scripts/waterfall.py`
keeps the inert `low_departure` mapping so the committed g3r1 diag dumps
render. Parked reproducible: `scripts/departure_gate_harness.py` (helper
VERBATIM; `action_evidence.py` re-derives `evidence_r1.json`'s
`departure_gate_check` byte-identically), `scripts/probe_departure_removals.py`
(22 removals / 0 additions) + `scripts/probe_owner_verdicts.py` (bw0
17/17, bw03 regression) with the g3r1 artifact paths as defaults.
Evidence doc bannered NOT SHIPPED, tables intact:
`docs/g3_r1_departure_gate.md`; runs under `output/g3r1/` (git-ignored).
Suite **755** (772 − 15 gate tests − 2 restored drift rows).

**R2 diagnosis (same session, worker + coordinator-verified).** The
plan's R2 candidate — replace the hand-set gesture confidence with a
LOCO-calibrated continuity × gesture-tier score — is **REFUTED at
diagnosis**: pooled AUC **0.172** vs **0.551** for the emitted constant
(within-clip 0.265; no variant — per-cell, gesture-only, continuity-only
— wins). Causes measured: the gesture tier REVERSES across clips (dev
low-tier 0/11 vs entreno 4/4 — clip-type-driven, NOT near/far) and fold
base rates anti-correlate with held-out rates (dev 0.276↔fit 0.821).
Side-finding: **`action_confidence=0.3` is INERT** — min emitted constant
0.45, so the filter keeps 85/85; on a calibrated scale, matched precision
⇒ keep-all and precision decays monotonically to 0 at θ=0.9. Motivation
stands (ECE 0.154/0.164, monotonicity violated); `track_frac_15f` is the
only within-clip-stable ordinal (decomposition AUC 0.636). New:
`scripts/confidence_calibration.py` +
`docs/g3_r2_confidence_calibration.md` (revival preconditions + the R1
battery for any future threshold change, §6). No `src/` change; suite
755.

**Next:** Active-next re-ranked — the far-side serve owner call is on
top; the departure gate is revisitable ONLY as a width-band-aware
mechanism after T8 (its dev-side precision pool is real: 7 FPs at zero
collateral); R2 is parked behind its owner-gated preconditions (match-side
per-prediction labels + clip-type-aware base rates) — the cheapest G3
work that is NOT owner-gated is now T6 (feature sidecar).

### 2026-09-29 (fortieth session) — G3 per-action evidence diagnosis (diagnose only)

**Asked:** owner added G3 (action accuracy/confidence) as the top goal;
coordinator picked the next needle-mover and delegated to GLM (pi -p),
then reviewed. **Done:** 8 `--device cpu --diag-dump` runs (e1–e7 fresh
under `output/g3/eN`; dev re-run byte-identical to T4). New
`scripts/action_evidence.py` imports `evaluate_timed.match_events` and
waterfall's FP classes; per prediction outcome + ~28 features →
`output/g3/evidence.json`, `docs/g3_action_evidence.md` (precision tables,
single-split separability, calibration of the hand-set confidence,
per-clip consistency). **Result:** 85 predictions, 54 correct; confidence
constants uncalibrated; `speed_out` < ~0.3 bw/f flags 6/14 FPs at zero
collateral (gap 0.198→0.423 bw/f), `frames_since_prev > 90` holds all 4
serve FPs but costs 2 correct, `track_frac_15f` monotone and
clip-consistent. **Review fix:** delegate's first R1 used raw px/f (×1.26
margin, dev dup/FP inside the gap, far-biased) → reworked to
width-normalised; `SPEED_F` pinned to `ActionClassifier.CONTACT_DELAY`
(causal at confirmation). Caveats: n=85, all 6 R1 hits on dev; entreno
GTs have no point windows (their FPs are all `fp_in_point`). Suite 754
(732 + 22). **Next:** owner approval of R1 before any `src/` change.

### 2026-09-29 (thirty-ninth session) — T5 revert: neither mechanism ships; `src/` back to `185c6f0`, A + B live in the probe harness only

**What was asked:** the reviewer ruled that both T5 mechanisms recover 0/5 far
serves and therefore belong nowhere near production. Restore `src/` (and the
src-facing config) exactly to `185c6f0`, keep the A/B reproducible outside
`src/`, rerun it, fix the docs.

**What was done.** (1) `git checkout 185c6f0 -- src/ tests/test_config_drift.py`
— `git diff 185c6f0 -- src/` is now EMPTY, including the `ball_weak_*` /
`ball_backfill_*` DEFAULT_CONFIG keys and the config-drift rows (ctor-parity +
default-off) that pinned them. (2) The mechanisms moved to
`scripts/serve_mechanism_harness.py` as default-off subclasses:
`ServeMechanismBallTracker(weak_*=, backfill_*=)` overrides `_try_lock`
(weak tier, tried only AFTER production's own scan so a production lock always
wins), `_scan_motion_pair_with_bar` (the production loop with the speed bar
parameterised), `_update`/`_bootstrap_detection`/`_chain_backfill` (mechanism B)
and `ProbeClassifier.add_ball_sightings`. `scripts/probe_serve_mechanisms.py`
now imports the harness instead of the src hooks. (3) Replay rerun with the
documented command: **every number in `docs/t5_mechanism_ab.md` is unchanged**
— base 36/13/0, A_weak3_w30 37/14/19, A_weak3_nowidth 37/14/26, all four
B arms 37/14/0, **0/5 far serves recovered**, base fidelity 4968/4968 frames.
(4) `tests/test_serve_backfill.py` retargeted at the harness (24 tests) plus a
guard that greps `src/` for the mechanism tokens so a refuted mechanism cannot
re-enter; config-drift back to its T4 form. (5) Docs corrected
(`t5_mechanism_ab.md`, `t5_serve_admission_diagnosis.md`, plan T5 row,
STATUS).

**Conclusion (unchanged, now shippable as a verdict): T5 far-serve admission is
REFUTED at the tracker level.** The root blocker is the contact probe's
serve-branch geometry (fed-ascent demand vs a far decelerating float) plus the
complete absence of toss detections on P4/P6/P8 — recognition/detection work
that needs an owner decision. Suite green (736).

### 2026-09-29 (thirty-seventh session) - T5 DECIDED (owner: serve-time ball-track (re-)admission) + step 1 diagnosis, diagnose only

- **Owner decisions recorded:** (a) T5 mechanism = serve-time ball-track
  (re-)admission - extend the UNLOCKED bootstrap so the far-side toss can lock
  below `lock_min_speed = 8 px/f` (NOT time-based windows, NOT the width-split
  `unreliable` state); (b) P6 f3131 set->overpass RATIFIED ("it's an
  overpass").
- **Scope:** measurement only. Zero `src/` change (the only code is a new
  diagnostic script + tests + a GT ratification table).
- **Harness:** `scripts/probe_serve_admission.py` reads the T4
  `--diag-dump` JSONL + the GT serves, reports per frame the raw detections
  (pos, px width, conf, `persist`/suspect/removed), the tracker state+reason,
  the observed gap-1 speed and the exact bootstrap pair the tracker computes,
  plus WHICH gate failed. It also REPLAYS the unlock decision over the whole
  clip (the dumped `locked` flag resyncs it - fidelity 4966/4968 frames) so
  counterfactual rules can be scored: serves recovered AND every extra lock
  they create. Artifacts: `output/t5/*.jsonl|json`, e3/e6/e7 diag dumps from
  fresh `--device cpu` runs.
- **Result (dev clip, 8 GT serves):** 5 of 8 are unlocked at their own contact
  frame, and they are EXACTLY the 5 far-side serves (P1 f210, P2 f880, P4 f2154,
  P6 f3038, P8 f4770); the 3 near-side serves (P3/P5/P7) lock at contact.
  Far-side toss: 13-17 px ball, median pre-contact rise 1.6-6.7 px/f, 0
  detections at the contact frame. Near-side: 46-53 px, 7-17 px/f.
- **Ranked failing conditions:** 1) `speed_below_lock_min_speed` (the cause,
  all 5); 2) `no_previous_sighting_in_window` / `no_detections` (the far ball
  is seen every 2-4 frames and is invisible at contact - caps any rule);
  3) `no_plausible_survivor` (1 frame each in P1/P2, 14 in the healthy P3).
  NOT failing: `lock_max_jump`, `lock_max_pair_gap` (`pair_gap=3..4` alone
  recovers nothing), candidate crowding.
- **Counterfactuals:** `lock_min_speed` 3.0 px/f recovers **5/5** at lock
  latency 0 with 20-31/31 window frames owned (4.0 -> 4/5, 5.0 -> 1/5, 6.0 ->
  0); cost 15 new bootstrap locks per 4968 frames, ~3 of them the intended
  tosses. Size-normalised gate (`8 px/f * w/ref`) recovers only 3/5.
  Discriminators measured and rejected: 3-of-3 sustained sightings within
  20 px, `persist < 0.25`, player proximity < 120/250 px remove ZERO spurious
  locks; ascending-only LOSES P4 and P6.
- **Contrast:** every surviving serve in the corpus is near-side - dev P3 f1395
  (w50, 11.5 px/f, lock -19f), P5 f2575 (w51, 16.8, -34f), P7 f3747 (w50, lock
  -18f), entreno 3 f29 (w51-55, lock f14), entreno 7 f22 (w51-57, lock f21);
  entreno 6's serve is not an admission failure at all (locked from f1). So
  the entreno gate has little power over this mechanism - the A/B must be
  "entreno not worse" + the dev clip.
- **Proposal for step 2 (NOT implemented):** a second, weaker motion tier used
  only while UNLOCKED (`ball_lock_weak_min_speed = 3.0` px/f) gated on the far
  apparent-width band (`w < 30 px`) so near-side behaviour is byte-identical,
  with the 8 px/f fast path untouched; risks enumerated with measured
  instances (rack ball f3360, held balls f4095/f2365, other-court f1173/f4551)
  in the doc.
- **GT ratification:** `scripts/build_dev_clip_gt.py` gained a generic
  `OWNER_RATIFICATIONS[(point, match_frame, gesture)]` table; a ratified flag
  carries `owner_ratified/owner_ratification_date/owner_ratification_statement`
  and ratified wording, an unratified one keeps "needs ratification". P6 f3131
  ratified 2026-09-29; GT regenerated (only those fields changed).
- **Tests:** +19 (`tests/test_probe_serve_admission.py`) +4 GT-ratification
  tests; suite green.


### 2026-09-29 (thirty-sixth session) — T4 loss waterfall on the dev clip: diagnose only, one root cause found (serve-time ball-track admission)

- **Scope:** locate, per GT contact, the FIRST stage where it dies. NO
  decision/threshold change; the only production change is inert capture.
- **Step 1 — the first dev-clip run that ever existed**
  (`--device cpu`, calibration auto-detected, T1 readiness green) into
  `output/t4/base_dev`, then `scripts/evaluate_timed.py --ignore-player`:
  contact P 0.586 / R 0.607 / **F1 0.597** (tp 17, fp 12 of which 1 duplicate,
  fn 11), class 0.706, team 0.706, 2.703 FP per dead-time minute (4 FP over
  1.48 dead min of 172.0 s), points 6 matched / 2 missed / 0 spurious, mean
  temporal IoU 0.707. Baseline A/B dumps for the byte gates (dev + e3 + e1)
  were taken from clean HEAD BEFORE any edit, per the standing rule.
- **Step 2 — diagnostic capture (off by default).** `src/utils/diagnostics.py`
  (`DiagRecorder` + `load_diag`, JSONL: a `meta` header line then one record
  per frame) wired into the ONE shared `FrameProcessor.process_frame`: raw ball
  candidates with their `persist`/`suspect`/`removed` flags (BallDetector),
  tracker state + the branch/reason it took (BallTracker, via a thin `update`
  wrapper around the untouched body), player boxes/ids/team, contact probes
  incl. refusals with the gate that refused them, and the accepted contact with
  actor/team/attribution source + resolved action/touch/rally (ActionClassifier).
  All hooks are `if self.diag_enabled:` guards around values that already
  exist; `diag_dump` is a real config key (None by default) wired to
  `--diag-dump`, with a config-drift guard section pinning key-exists /
  off-by-default / CLI-wired / no-mirror-while-off.
- **Step 3 — `scripts/waterfall.py`.** Per GT contact, walks the 7-stage chain
  inside the T3 tolerance window and blames the first failure; the GT/prediction
  pairing is IMPORTED from `evaluate_timed.match_events` (never reimplemented),
  and actions/candidates are keyed by CONTACT frame. FPs are classified by
  source: duplicate / dead-time / in-point spurious, each annotated with the
  candidate that produced it. `scripts/compare_runs.py` is the byte-identity
  gate helper (ignores only `processed_at` and the three wall-clock rows of
  `results_statistics.csv`).
- **Result (`docs/t4_loss_waterfall_dev_clip.md`):** 0 raw detection, 0 track
  admission, **6 candidate, 5 gate (all `reach`), 5 actor/team, 4 label, 8
  survive**; FPs 8 in-point spurious / 3 dead-time / 1 duplicate.
- **The finding:** 5 of the 6 candidate deaths are the 5 lost serves, and there
  the detector DOES see the ball — 18–23 raw candidates per window at conf
  0.74–0.87, `removed=false`, `suspect` almost never — while the tracker is
  `unlocked` reporting `unlocked_no_motion` on 19–25 of the 31 window frames
  (one `bootstrap_locked` frame, then `coast_short_trajectory`). The toss apex
  never produces the >=8 px/f near-consecutive motion pair the bootstrap needs.
  So the serve class is a BALL-TRACK ADMISSION loss, one layer earlier than both
  the "serve-action gate" of STATUS point 22 (match footage) and the plan's
  "candidate recovery" option — and it also explains the 4 false-positive
  `serve` actions (same toss class, mistimed).
- **Secondary, orthogonal:** 4 of the 5 actor/team deaths are P8 — exactly the
  post-P7 side switch the owner dictated (near = B from P8). That is open point
  2 / task T14, deliberately NOT the T5 mechanism. The 5 gate deaths are all the
  `reach` gate; the 4 label deaths are 3 overpasses read as spike/set/dig plus
  P7 f3852's set read as a serve.
- **Gates (a)-(d) all green:** hooks off == pre-change HEAD byte-identical on
  dev + e3 + e1 (only `processed_at` and the wall-clock statistic rows differ);
  hooks on == hooks off byte-identical on the dev clip (and the evaluate_timed
  numbers are unchanged); +37 unit tests (22 waterfall stage/precedence/FP, 11
  diagnostics + compare_runs, 4 config-drift); suite **685**.
- Files: `src/utils/diagnostics.py` (new), `src/utils/config.py`,
  `src/detection/ball_detector.py`, `src/tracking/ball_tracker.py`,
  `src/recognition/action_classifier.py`, `src/analysis/frame_processor.py`,
  `src/main.py`, `scripts/waterfall.py` (new), `scripts/compare_runs.py` (new),
  `tests/test_waterfall.py` (new), `tests/test_diagnostics.py` (new),
  `tests/test_config_drift.py`, `docs/t4_loss_waterfall_dev_clip.md` (new),
  `docs/action_reliability_plan.md`, STATUS.md.


### 2026-09-28 (twenty-seventh session) — architecture decision: pass-2 interpretation layer ratified; full-video two-pass rejected; mechanism 3 reframed (no code)

- **Trigger:** the owner proposed processing matches in two full video
  passes — pass 1 dissects the video into points (a serve STARTS a
  point, so no guessing whether the ball is airborne; ball hitting the
  ground or a 1-2s held ball ENDS it), pass 2 runs action recognition
  inside the windows — accepting ~2× offline cost and a live-debug
  divergence TBD; stated goal: MINIMIZE false positives.
- **Challenge — what survives:** hindsight IS the winning ingredient.
  A serve is hard to identify causally (the #22 diagnosis: contact
  25-35f before game_on arms) but easy with hindsight ("the flight
  that opened a rally with N contacts"), and the episode→point map
  (#26) already IS that second pass — over the recorded stream, not a
  video re-decode. A structural serve prior kills both main #22 loss
  classes at once.
- **Challenge — what breaks:** (1) the premise "we know a point is
  taking place if the serve started" assumes pass 1 can detect serves
  — it can't (14a: burst width, static hold, near→tape→far all
  measured and REFUTED; the probe proved the detector sees every serve
  — the loss is the DECISION, not the data). (2) Two video passes
  double the wrong half: perception (68 ms/f) is causal anyway — the
  trackers are online filters, a re-decode reproduces the same tracks;
  the layer that profits from hindsight (which episodes are points,
  which contact is the serve, who won) runs over pipeline_output.json
  in seconds. (3) It breaks the two hardest invariants: the ONE shared
  FrameProcessor path, and live-debug parity (owner-ratified after a
  real skew bug — a two-pass cannot exist live by definition). (4) FP
  taxonomy vs the proposal: off-game handling → already fixed by the
  map's constraints + anchors (post-hoc, zero re-decode); gesture
  misclassification → fixed by the structural serve prior
  (interpretation); suppressed slow-float serves (P15) → the ONE class
  genuinely needing re-perception, solvable by targeted re-decode of
  flagged windows only (~15×500f ≈ 8-15% cost). (5) The proposed
  point-END rule is already the shipped design (static_off_frames held
  ball, density starvation ball-death, contact_chain/group_gap
  boundaries). Honest caveat recorded: a cheap ball-only pass 1 +
  full-stack pass 2 on windows could be cost-neutral at ~50% dead
  time — but ball-only segmentation is exactly the FP-prone burst
  gate; it saves money by weakening the FP-critical layer, opposite of
  the stated goal.
- **RATIFIED (owner): two passes over the STREAM, one pass over the
  video.** Pass 1 unchanged causal FrameProcessor →
  pipeline_output.json → DB; live-debug stays byte-identical to
  production. Pass 2 offline (seconds): episode→point map (done) →
  TRUE point windows → rally-opening-contact serve re-label → winner
  layer (21.3, vs the 33 dictated winners) → fantasy lines (13/14e,
  DB-side). Escalation only where flagged: window re-decode with raw
  detector settings (P15 class), bounded + logged. Marginal math
  noted: point segmentation is already 31/33 — re-architecting pass 1
  chases 2 points; serve emission (16/32 missing) lives in the
  interpretation layer.
- **Mechanism 3 (point 22) reframed to:** pass-2 serve re-labeling
  from map windows. Validation gates: anchored census far 2/8 → ≥6/8
  clean, serve actions 20 → ~28 (v2 emitted 28); entreno 7/7 action
  logs byte-identical; suite green; config-drift guard extended if new
  keys appear; A/B baselines dumped from HEAD before editing.
- Codified as AGENTS.md §6 (pass-2 interpretation layer). Session #24's
  Log entry archived verbatim (live Log trimmed back to 3). No files
  under src/, no GT edits, suite untouched (525).


### 2026-09-27 (twenty-first session) — pi project default model set to zai/glm-5.3-flash (.pi/settings.json)
- **Harness config only** — no pipeline code, no GT. New
  `.pi/settings.json` sets `defaultProvider: zai` + `defaultModel:
  glm-5.3-flash`, overriding the user-level `~/.pi/agent/settings.json`
  (`zai/glm-5.3`) inside this repo only. Cross-checked before writing:
  `zai/glm-5.3-flash` was already in the user settings' `enabledModels`,
  and `~/.pi/agent/auth.json` authenticates `zai`, so no provider setup
  was needed. Rest of `.pi/` (prompts/) untouched. Running pi sessions
  need `/reload` or a restart to pick it up.
### 2026-09-27 (twentieth session) — e3 v3 drift FIXED without GT edits: the short-gap bridge now checks the normal path can actually host the touch

Owner brief: after the v3 swap e3 drifted (F1 1.0→0.667), the GT stays,
some contact "changes midpoint and then it starts going sideways" — fix
without regressions. Diagnose-first, one shipped mechanism.

- **Instrumentation:** production-parity ball-track dumps for e3 under
  both models (`output/diag_e3_v3_balltrack.py` →
  `output/diag_e3_balltrack_{base,v3}.json`, detector conf 0.15 + tracker
  parity + court bounds) and a SpikeAnalyzer transition tracer
  (`output/diag_e3_spike_trace.py`). The action diff against the gate
  artifacts localized the break to the missing f378/379 set, everything
  after being resolver cascade.
- **Three mechanisms found (A causes the F1 loss; B moot; C enrichments):**
  (A) v3's tracker accepts the true arc bottom f379 that base starved
  (moving bystander out-confd the ball 0.76 vs 0.70 → trusted coast; the
  in-gate ball was never tried); with the bottom real and v3 blind at
  f385-386, no frame can host the set — bounce@378 not-lowest, bounce@379
  right-sparse, drive@384 left3-empty — yet the bridge refused as "dense
  both sides". (B) ±px jitter tips |inc[0]| 18→21 over XREV_MIN=20 at
  f539, so the redirect test steals the kill → block gesture; harmless at
  touch 3 (the resolver's poke rule returns SPIKE — the `touch < 3` block
  guard is load-bearing). (C) v3 conf dip f613-618 → coast leaves the
  court-bounds box → re-entry window rejects the falling dets → track
  dies f623 → the dug→kill flush conversion loses the post-dig flight
  (f539 outcome reads dug vs GT kill; base read kill).
- **The fix (`src/recognition/action_classifier.py`, one mechanism):** the
  short-band dense-side refusal now requires `_normal_vertex_in_range(a0,
  c)` — a fireable normal vertex in the gap range — checked by reusing the
  normal tests factored out pure (`_normal_contact_at`); no duplicated
  thresholds, e6 f265 still defers. +2 tests
  (`test_short_gap_bridge_takes_seen_bottom_with_sparse_right`,
  `test_short_gap_bridge_still_defers_when_normal_vertex_fireable`),
  suite **448 green**.
- **Validation:** e3 v3 F1 **1.0** (14/14 matched; team 1.0, spike_type
  4/4, attack_zone 1.0, dug_zone 1.0; outcome 0.75 = Mechanism C's f539
  dug/kill; landing_zone 0.0 pre-exists in base — GT B8 vs emitted B7);
  e1/e2/e4/e5/e6/e7 action streams BYTE-IDENTICAL to the gate record
  (F1s 0.706/0.571/0.933/0.923/0.933/0.75; e6 team stays 0.857); base-
  weights rerun all 7 BYTE-IDENTICAL (neutrality proof). Artifacts:
  `output/e3_fix/`.
- **Match re-run (`output/match20260920_e3fix/`):** confirmed 31/33
  (0.939), 57 episodes, first-confirmed = GT pt 1 — identical to the gate
  record; actions 207 vs 206 (the +1 is a bridge-recovered dig in GT pt 5;
  all other labels unchanged: dig 84 / spike 45 / set 42 / serve 20 /
  overpass 9 / block 7). `match_points_eval.json` written.

### 2026-09-26 (nineteenth session, adoption leg) — v3 ADOPTED as production; owner feedback: far-side serves untracked (new open point 22); session closed

- **Adoption:** `models/volleyball_ball_best.pt` overwritten with v3
  (md5-verified byte-identical to `volleyball_ball_best_v3_r2.pt`); old
  production preserved as `models/volleyball_ball_best_v1_entreno.pt`; v2
  kept; owner's root drop removed (round-1 convention). Default loaders
  smoke-tested. models/ is git-ignored — the swap is STATUS-only in git.
- **Owner feedback recorded verbatim in open point 22:** far-side serves
  in the match appear untracked; entreno serves fine. Hypotheses + probe
  plan recorded there (v3 "other"-background weakness at the backdrop,
  serve count dip 28→20, entreno-tuned serve-zone admission, 25.7fps
  launch speed). No mechanism built — diagnose first.
- **Session state:** ball retrain thread (open point 20) CLOSED after two
  rounds; entreno re-adjudication (e3/e4/e5/e6) and point 22's probe are
  the queued follow-ups; open point 21 re-ranked (point-layer re-tune
  likely moot at 31/33).

### 2026-09-26 (nineteenth session, gate leg) — round-2 validation gate: v3 passes GT-frames / match / probe decisively, entreno drift-lock fails; adoption recommended with re-adjudication caveat

Owner trained r2 in Colab (fine-tune FROM production best.pt, 1441-image
zip); weights stashed as `models/volleyball_ball_best_v3_r2.pt` (production
UNTOUCHED). All four legs, three-way where it matters:

- **Leg 1 GT-frames (diag_gt_frames.py 3-way, 486 frames):** recall 94.2%
  (58.3 old / 57.8 v2), @0.4 precision 95.5% (39.9 / 25.3), dets 422
  (1750 / 3026 — noise gone), FP@0.4 18 (330 / 682; sky 11 / 31 / 236),
  blind recall 94.6% (57.1 / 58.0), TRUE-det conf sky 0.85 med 100% ≥0.4 /
  sand 0.81 med 93.5% ≥0.4. Valid-split tag updated to the current
  1441-pair split (216 valid — matches the Colab run's valid count);
  valid numbers comparable within-run only: 88.1% / 92.9%.
- **Leg 2 entreno A/B (output/retrain_eval_v3/, 14 runs, --ignore-player):**
  base leg reproduced the recorded F1s EXACTLY (0.706/0.571/1.0/1.0/1.0/
  0.933/0.75 — drift-lock reference good). v3: e1/e2/e6/e7 F1-exact;
  e3 1.0→0.667 (block FP, spike 2 FN, set churn), e4 1.0→0.933 (overpass
  FP — v2's identical failure), e5 1.0→0.923 (opening serve lost — v2's
  identical failure); e6 team 1.0→0.857 (NEW; one misattributed contact).
- **Leg 3 match (output/match20260920_v3/, ~40min run):** confirmed 31/33
  GT (0.939) vs 15/0.455 (v2) / 13/0.394 (base); episodes 57; 0 episodes
  before first confirmed (first-confirmed = GT pt 1); actions 206 (dig 83 /
  spike 45 / set 42 / serve 20 / overpass 9 / block 7) vs 104 / 90; serves
  20 vs v2's 28 / base 21 — the only match metric that regressed.
- **Leg 4 probe (diag_ball_probe_v2.py 3-way over the same 5 episodes):**
  tracked old→v3: ep02 6→28%, ep06 24→42%, ep12 4→2%, ep08 11→23%, ep35
  49→78% (flight 42→60%). ep35 sky cand conf med/≥0.4: 0.90/92 → 0.47/51
  (v2) → 0.85/99 (v3). Blind% UP everywhere (25→51 / 10→52 / 31→94 /
  16→58 / 20→20): the round-1 audit's "raw candidates were mostly sand
  noise" made visible — class (b) collapsed to 1-8%.
- **Verdict: 3/4 legs pass, decisively; entreno 4/7-exact vs the 7/7 bar.**
  e4/e5 failure modes are IDENTICAL across v2 and v3 (systematic to
  venue-matched retrains); e3's regression is v3-specific; e6's team flip
  is new and touches the safety-critical emitted-team signal. Production
  weights UNCHANGED. Recommendation recorded in open point 20: adopt v3
  (31/33 was unreachable tracker-side) AFTER the owner re-adjudicates
  e3/e4/e5/e6 against v3 streams — GT was dictated against base-model
  behavior, and base was half-blind.

### 2026-09-26 (nineteenth session) — round-2 rebalanced mining staged: 200 noise negatives + 150 sky controls, notebook switched to fine-tune-from-best.pt

Executing the round-2 spec from open point 20 after v2_match was rejected
(class (a) fixed, precision/sky/entreno regressions). No pipeline src
changes; one script extension + tests.

- **`--exclude-manifest` on `scripts/mine_ball_frames.py`:** a previous
  round's manifest excludes its same-class picks ±spacing from this
  round's pools (classes are deterministic, so cross-class collisions are
  impossible at the exact frame). `exclusion_zone()` pure helper + cap-0
  and round-2-caps contract tests (+6, suite **446 green**).
- **Determinism check came free:** the re-scan reproduced round 1's
  scanned-class counts EXACTLY (blind 1843 / low_sand 1407 / low_other
  1541 / sand_noise 1100 / sky_control 1233 / high_other 870 over 7994
  game_on frames).
- **Picks (caps hit exactly, span f240..f26004, 222MB, no exact
  collisions):** sand_noise 200/200 (pool 1100 → 449 available after
  excluding round-1's 60 ±5f) + sky_control 150/150 (1233 → 809 after
  round-1's 40). Blind/low classes NOT re-mined (round-1 GT fixed them;
  v2 kept the wins).
- **No pre-labels (`--no-prelabel`), README.md in the dir:** round-1
  audit — our ≥0.4 sky pre-labels sat on the owner's ball 3/77; the owner
  annotated without labels anyway. Noise frames are negatives by
  construction (owner boxes a ball if they see one); sky frames get the
  TRUE ball or null — the nulls are exactly the sky-FP negatives v2
  lacked (236 confident sky FPs at the 0.4 gate).
- **Recorded footnote:** 118/350 round-2 picks sit ≤5f from a round-1
  pick of a DIFFERENT class (noise and blind interleave inside rallies);
  accepted (different content), but remember if the valid split looks
  optimistic. The real gate remains the four-leg validation.
- **`notebooks/finetune_yolo_ball.ipynb` round-2-ized:** BASE_MODEL var
  defaults to the uploaded production `volleyball_ball_best.pt`
  (preserve the sky prior; round 1 from base yolov8n lost it),
  `"yolov8n.pt"` reproduces round 1; run/download renamed
  `volleyball_ball_r2` / `volleyball_ball_best_r2.pt` so production
  weights stay untouched for the A/B; recipe unchanged.
- **Handoff:** owner annotates the 350 → COCO export (dataset page —
  rapid download broken last time) → `import_roboflow_coco.py` →
  `prepare_dataset_for_training.py` → zip → Colab r2 (upload best.pt
  alongside the zip) → weights back → SAME four-leg gate.

### 2026-09-26 (eighteenth session, validation-gate leg) — candidate retrain measured on all four legs: class (a) fixed, precision/sky regress; REJECTED, round-2 spec recorded

- Weights: owner's Colab run stashed as
  `models/volleyball_ball_best_v2_match.pt`; production
  `volleyball_ball_best.pt` untouched. All artifacts git-ignored:
  output/retrain_eval/ (GT-frame eval + probe v2),
  output/match20260920_retrain/ (full run + match_points_eval.json).
- **GT-frame eval (new diag):** recall flat 58%, dets 1750→3026,
  precision 13.9→8.0%, @0.4 recall 52.5→55.4% / precision 39.9→25.3%;
  sand TRUE conf med 0.63→0.80. Valid-split (leakage-free, n=65):
  recall 50.8→47.7%.
- **Entreno A/B:** e1/e2/e3/e6 EXACT (0.706/0.571/1.0/0.933), e4
  1.0→0.933 (+FP overpass f386), e5 1.0→0.923 (opening serve f17 lost),
  e7 0.75→0.625 (f242 set lost, f440 dig gained). Team 1.0 ×7.
- **EVAL GOTCHA (permanent record):** the recorded action F1s require
  `evaluate.py --ignore-player`; with the default player matching,
  byte-identical streams score 0.933 vs 0.133 (GT player_id is a
  per-frame left-to-right index). Mirror the baseline invocation in
  every A/B.
- **Match:** confirmed 13→15 (0.394→0.455), actions 90→104, serves
  21→28; episodes 48→63, first-confirmed ordinal 4→7.
- **Probe v2:** blind% 25→2 / 10→3 / 31→19 / 16→15 / 20→9; ep35 sky
  med conf 0.90→0.47 (≥0.4: 92→51%); tracked 2→10 / 25→31 / 0→7 /
  4→11 / 47→46%.
- **Verdict: reject as drop-in.** Round 2 (owner + this gate):
  rebalanced mining (~200 pure negatives, ~150 sky positives; blind/low
  classes kept), optional fine-tune-from-best.pt, same four-leg gate.

### 2026-09-25 (eighteenth session) — retrain-mining shipped: 500 stratified match frames staged for the owner's Roboflow annotation

Open point 20's second half (detector retraining — class (a) is
unreachable by tracker-side gates). No pipeline src changes; one keeper
script + tests.

- **`scripts/mine_ball_frames.py`:** scans the GAME_ON ranges of a
  results_game_state.csv (default: the floors-ON rerun
  output/match20260920_lowconf/) with the production-parity detector
  (volleyball_ball_best.pt, conf 0.15, the _up1080 file, 30f
  static-suspect warm-up per range, det.reset() between ranges) and
  stratifies every frame with the probe's bg_class (kept byte-identical
  to diag_ball_probe_bgsky.py): blind / low_sand / low_other (cands but
  none ≥0.4, best non-suspect's bg) / sand_noise (suspects-only = hard
  negatives) / sky_control (≥0.4 sky-backed = regression guard);
  ≥0.4-non-sky frames are high_other — manifest-recorded, not mined.
  Sampling: seeded shuffle + greedy min-spacing (5f) per class; two
  decode passes (classify everything, then write only the picks).
- **Full-match scan (7994 game_on frames, 48 ranges): blind 1843 (23%),
  low_sand 1407, low_other 1541, sand_noise 1100, sky_control 1233,
  high_other 870.** Blind at 23% of ALL game_on frames confirms the
  retrain is load-bearing, not optional polish.
- **Annotation set (resources/frames/match20260920/, git-ignored like
  datasets/):** 500 JPG q95 (318MB), names
  20260920_match_ari_joan_lost_f<idx> (resolve_source_stem — no
  collision with the dataset's flat frame_XXXX namespace), spanning
  f297..f25991. Caps: 250 blind / 100 low_sand / 50 low_other / 60
  sand_noise / 40 sky_control (owner-ratified budget 500). Pre-labels =
  all non-suspect cands ≥0.15 in YOLO format (empty txt for blind/noise
  = negative unless the owner finds a ball); manifest.json carries the
  audit trail + the note that pre-labels are review-required.
- **Sanity before the full run:** smoke set (f3000-3400) end-to-end + a
  ±2-frame motion-support proxy on the smoke picks: 8/12 low-class
  picks supported (consistent with the sim's ~60%); blind picks show
  nothing at ±2 either — genuinely hard, human-only, as intended.
- **Tests:** tests/test_mine_ball_frames.py +16 (classify_frame
  admission order incl. suspect-vs-mover, 0.400 boundary, spacing/cap/
  determinism of pick_frames, game_on_ranges run extraction, 500-budget
  contract). Suite **435 green**. resources/frames/ added to .gitignore.
- **Handoff:** owner uploads images/ + labels/ together to Roboflow →
  reviews/corrects → exports YOLOv8 → merges into
  datasets/ball_detection/ → prepare_dataset_for_training → Colab
  fine-tune (notebooks/finetune_yolo_ball.ipynb) → validation-gate
  session on the new weights (entreno A/B drift-lock, match re-run +
  evaluate_match_points, probe re-run for class (a)/(b) shrinkage).

### 2026-09-26 (eighteenth session, annotation leg) — owner GT landed; retrain dataset merged + zipped; pre-label audit forces a diagnostic correction

- **Owner report:** the shipped pre-labels were mostly wrong → they
  uploaded images WITHOUT labels and annotated one by one in Roboflow.
  Version-page "rapid" download was broken; COCO export from the
  dataset page worked. 486/500 frames (14 lost: 6 blind/3 low_sand/
  2 low_other/2 noise/1 sky). Export images pixel-identical to our
  frames (diff 0.00, n=346) — same pixels, human labels.
- **Audit BEFORE the owner's explanation (kept for the record):** owner
  boxes vs pre-labels — low_sand 0/155 same-place, low_other 0/71,
  sky_control 3/77; then all "deleted pre-labels" made sense: labels
  never attached. **Correction that survives: raw detector precision on
  this venue is LOW (even ≥0.4 sky-backed picks mostly not the ball per
  human GT); the tracker's motion/geometric gates carry production;
  many probe class-(b) candidates were sand noise, not missed balls.**
  The floors mechanism keeps its validation (entreno-neutral, match
  actions +22%) because its picks are motion-gated — but re-read probe
  counts as noise-heavy. The retrain attacks precision AND recall.
- **Owner GT contents:** 423 boxes on 486 frames (208/244 exported
  blind frames now have a ball), 73 empty-label negatives, 6 degenerate
  <2px boxes dropped with report (click droppings). Box widths med
  ~25px, tail to 95px. One leftover empty Roboflow category mapped
  harmlessly (0 annotations).
- **`scripts/import_roboflow_coco.py`** (+5 tests, suite **440**):
  `_jpg.rf.<hash>` suffix strip → canonical names, COCO→YOLO, non-ball
  category aborts, collision refusal, empty labels = negatives,
  degenerate-box drop policy at 2px.
- **Merge + zip:** datasets/ball_detection/ = 1091 images (605 + 486);
  ball_dataset.zip 1.7G, 928 train / 163 valid (418/68 match).
  Gotcha: disk filled mid-prepare (Errno 28) — rm the partial
  yolo_dataset/ staging dir, rerun clean.
- **Next:** owner runs the Colab notebook on the new zip (T4, run all);
  weights return → validation-gate session (drift-lock, match re-run,
  probe re-run).

### 2026-09-24 (seventeenth session) — match GT transcribed + point evaluator; ball-recall probe indicts the 0.4 conf floor (blue-sky report confirmed)

Owner feedback on the first full-match run executed as a plan (GT infra →
ball probe → tracker mechanism → actions → points/winner/side-switch →
identity → landing confidence). This session: parts 1-2; no pipeline src
changes.

- **GT (committed):** scripts/parse_match_gt_text.py →
  ground_truth/20260920_match_points.json (33 points, final 21-12, winners
  BABABAABBBBAABAAAAABAABAAAAAABBAA, switches after 7/14/21/28; winners
  mechanical from the score table, descriptions verbatim; Team A/B = fixed
  squads). scripts/evaluate_match_points.py (count/confirmation/episode
  table/first-confirmed ordinal; winner+switch scoring declared NOT SCORED
  until those pipeline layers exist). tests/test_match_points_gt.py +18
  (suite 405 green). ground_truth/README.md documents match-points-v1.
- **Baseline:** 33 GT vs 39 episodes vs 14 confirmed (0.424); 7 episodes
  before the first confirmed → first confirmed ≈ GT point 8 (the owner's
  "P1 started around P10"). output/match20260920/match_points_eval.json.
- **Probe (diag_ball_probe_bgsky.py + ball_probe_bgsky.json):** per-candidate
  conf/size/stationary_suspect/background over ep02/ep06/ep12 (starved) +
  ep08/ep35 (controls): detector-blind 10-31%; conf-rejectable (cands
  present, none ≥0.4, lost) 33-68% — largest class; ≥0.4-yet-lost 5-24%.
  Sky-backed med 0.90 (92% ≥0.4) vs sand 0.20 (9%) vs other 0.22 (21%) —
  the "blue sky" report quantified. The 25.7fps tax NOT implicated.
- **Counterfactual (diag_lowgate_sim.py):** P2 (0.15 locked in-gate + 0.15
  motion-pair floor, non-suspect only) recovers tracked coverage to
  22/36/16/19/51% on the five episodes with flight ~flat; ~60% pick
  support, ~35% stranded-risk. Class (a) needs detector retraining — mine
  sand/building positives from this match next.
- **STATUS:** open point 20 indicted with next-mechanism spec; new open
  point 21 = the feedback backlog (emit candidates w/ confidence, action
  + point confidence, winner/score layer, side-switch layer + squad
  mapping + overlay label swap, persistent player numbers, landing
  confidence).
- **Mechanism SHIPPED (commit 2): BallTracker low-confidence floors**
  (ball_locked_low_conf_floor / ball_boot_low_conf_floor, 0.15 default,
  0=off; drift-locked ctor parity; +14 tests/test_ball_low_conf.py, suite
  419 green). Narrow zero-high-frames scope so the trusted coast stays
  byte-exact P0 (the sim's broader P2 recovered ~2-5pt more but reopens
  the e1-f77 distractor class — refused). Boot pairs may use low-tier
  sightings with identical geometric gates; re-entry waits never traded.
  **A/B:** fresh HEAD baselines first (lowconf_base; 6/7 byte-identical
  to the e15e set, e7 == ratified post-e15e stream); post: entreno evals
  FULLY NEUTRAL (0.706/0.571/1.0/1.0/1.0/0.933/0.75, team 1.0 x7); raw
  shifts confined to 1-frame/contact-kind/index inside gates (e7 dig
  f59→60, toward GT f61). **Match re-run:** actions 74→90, serves 13→21,
  first-confirmed ≈ GT pt 4 (was 8), ep f9150 confirmed; point count 13
  (flat — point layer now binding: 30fps windows on 25.7fps footage).
  **Game-state guard:** 10/13 vs a FRESH floors-off baseline of 11/13
  (the recorded 80.6% was stale — predates the session-7 ball rework);
  pt00 recovered, pt01-03 lost at boundaries; config-off escape hatch
  verified. Session D (point 21 item 1) re-tunes the point layer on both
  videos jointly.

### 2026-09-24 (sixteenth session) — cached `_up1080` inputs resolve the source-stem calibration

**Trigger:** live-debug on
`resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4` said the
court was not calibrated; the 720 original live-debugged fine.

- **Diagnosis:** `src.main` keyed calibration auto-detect on the RAW input
  stem — `..._up1080` → looked for
  `calibrations/20260920_match_ari_joan_lost_up1080.json` (missing), while
  `scripts/test_court_calibration.py` already stripped the suffix when it
  WROTE the calibration. One convention, two implementations, the reader
  was the broken one.
- **Fix:** `resolve_source_stem()` in `src/utils/video_upscale.py`
  (`re.fullmatch(r"(.+)_up(\d+)")` strip; plain stems unchanged, so
  `video2`/`warm_up` never match); used by `src.main`, the calibration
  script (dedupe), `dump_player_tracks` (auto-detect + output naming), and
  `test_{ball_tracking,player_tracking,action_recognition,pose_estimation}.py`.
- **Verified:** the `_up1080` file now resolves
  `calibrations/20260920_match_ari_joan_lost.json` AND `ensure_1080`
  passthrough keeps processing the same cached file; the 720 original
  resolves identically (no regression). Suite 387 green (+8).

### 2026-09-23 (fifteenth session) — first full-match run: points starve 14/≈39, roster holds, identities hop; ball recall indicted (point 20)

Diagnosis-only session on the 20260920 match (26,061f, ~25.7fps), owner GT
statement "final ~21-15, near team of the first point wins → ≈36 rallies".
All artifacts in git-ignored `output/match20260920/`: the batch run
(results CSVs, `pipeline_output.json`, 14 points, 74 actions, 13 serves),
the production-config tracks dump + `analyze_tracking.py`, a
production-parity ball-only pass, `diag_match_analysis.py`, and the
ratification sheets (`sheet_id3_cross_f1250-1350.png` — the confirmed
identity hop; `footy_timeline.png`, `footy_w*.png` — band
memberships).

- Episode layer RIGHT: 39 GAME_ON episodes ≈ 36 rallies. Point layer
  starved: 14 confirmed (needs `point_min_actions=2`; 17 episodes emit 0-1
  actions), 15 episodes truncate <120f — ball track dies mid-rally. Ball
  tracked 20.6% of all frames; 40-60% inside healthy episodes. 8 confirmed
  points contain no serve → fragments. Full numbers in the fifteenth-session
  Where-we-are block; mechanisms to probe ranked in open point 20.
- Players: ids 1-4 only, 0 recycled id NUMBERS, swap-rate 0.00, team
  accuracy 97.9%, 3.28/4 in-play coverage, 3.05/4 dead-time persistence;
  46 resurrections + visually confirmed mid-rally hop (id2 woman→man, both
  in-court); 12 per-episode side-mapping changes vs ~5 expected switches.
- No src/config changes; nothing to A/B. Next session: point 20's separation
  probe (raw candidates vs tracker decisions on truncated episodes), then
  point 2's GT pass around an official side switch.

### 2026-09-23 (fourteenth session, round 2) — ball-width band VALIDATED on the upscaled 20260920 video

- Probe (`output/diag_ball_widths_20260920.py` + `_followup.py`, results in
  `output/diag_ball_widths_20260920/`): production-path ball detector
  (fine-tuned model, conf 0.15, auto-imgsz) sampled every 10th frame of the
  `_up1080` cache, widths labeled by geometry (NEAR: below midcourt-ground
  line +25px, contamination-free; FAR*: above it −180px, conservative —
  near-airborne balls leak in with LARGE widths).
- **First read was a false alarm:** NEAR-labeled widths median 19px looked
  catastrophic. Conf-stratification + a 24-crop contact sheet resolved it:
  the sub-0.4-conf detections are NOT balls — this venue's sand fires the
  model on boundary lines, footprints and shadows. Real balls (conf≥0.5):
  NEAR med 36, p25–p95 36–55 (validated band 30–55 ✓); FAR med ~22–25 with a
  physics ceiling at the net-line depth (~24px ball + blur slack ≤ ~30) —
  far→near misreads impossible, near-net near balls abstain exactly as
  designed. 41% "FAR* in abstain band" is the near-airborne contamination
  upper bound, not a real rate.
- Calibration overlay checked: clicks sit on the playing lines (entreno
  convention). px/m vs entreno: near 224 vs 238 (−6%), net 114 vs 124 (−8%),
  far 70 vs 86 (−19%) — implied ball sizes 47/24/15px vs entreno 50/26/18:
  same regime, marginally more abstain-side at the net. The upscale did its
  job; no threshold changes made (26/35 stay untouched).
- Residual (open point 19(d)): sand-noise rate ~2.2 det/frame at conf 0.15 —
  tracker's motion gates own it as at entreno; full pipeline run still owed
  before trusting end-to-end attribution.

### 2026-09-23 (fourteenth session) — 20260920 match intake: one-time sub-1080p ingest upscale

- New footage: `resources/full_videos/20260920_match_ari_joan_lost.mp4`
  (1280x720, ~25.7fps effective, 26,061 frames, points only, SIDE SWITCHES —
  first real match; open point 2 unblocked). No GT yet.
- Diagnosis (see Where we are): 720p breaks ~20 hardcoded 1080p-px constants
  downstream of detection (YOLO imgsz is fixed, so detection is unaffected);
  worst is the ball-width side signal (thresholds 26/35 land inside the
  ×2/3 near-ball range).
- Shipped: `src/utils/video_upscale.py` (`ensure_1080`: pass-through at/above
  target; one-time ffmpeg Lanczos x264 CRF 18 `-vsync 0` transcode to
  `<stem>_up1080.mp4` next to the source; atomic rename + frame-count parity
  gate; cache-hit reuse), config `upscale_to_height: 1080`, hooked in
  `src/main.py` before batch AND live-debug (parity rule), calibration/output
  naming keyed on the source stem. Suite 379 green (+4).
- Verified on the real file: 1920x1080, 26,061 frames (decode-count parity
  vs source), fps preserved 25.67, 6.5min one-time, cache hit 0.01s.
- Deferred → new open point 19 (fps 25.7 vs 30; first full run unvalidated;
  test scripts bypass the hook).

### 2026-09-19 (thirteenth session, round 2) — f316 GT slip ruled and folded

- Owner ruling on output/e15e/reratify_e7_f315_team.png: contact on the FAR
  side; P2B (yellow) far from it; P4 really NEAR team (stamps flap B
  mid-jump — airborne feet); the net blocker is the FAR-side player; the
  P1/P3 boxes overlap (occlusion) with P1 also very close to the ball →
  toucher = P1 (track 1), team B = the pipeline's emission, unchanged.
- GT fold: f315 dig team A→B, team_in_possession→B, provenance note
  recorded. e7 eval: F1 0.75, P 1.0, team 1.0 (6/6).
- Flagged for the next ratification pass: GT f370 "set P4B" id now
  incoherent under near={3,4}/far={1,2} (B's f370 setter should be P1 or
  P2); track-4 airborne foot-team flap recorded as an artifact class, no
  code change (f300 unemitted today).

### 2026-09-19 (thirteenth session) — open point 15(e): width-confirmed cross + own-side drive-block refutation

- **Protocol:** fresh HEAD baselines for all 7 videos FIRST
  (output/e15e/base_actions; determinism re-verified against the p16
  baselines before any edit), probe/capture scripts under output/probe_e15e
  (git-ignored), edit only after ALL_DONE.
- **Probe (output/diag_e15e_probe.py):** the f242 contact is drive-band,
  near-net, hands-overhead, width committed A (36px, votes 1) on an A
  toucher; expected-team A picked track 3 (GT P3A) — attribution was never
  the problem, the label was. f316: width commits B (23-24px ×3 votes,
  true far regime), track 1 chosen (GT's named toucher) with contact-foot
  B.
- **Offline simulation BEFORE implementation (output/diag_e15e_sim.py +
  streams/snaps captured for all 7):** naive variants were measured and
  rejected — the plain team-flip breaks e2 f118 (set→dig: its possession
  opener e2 f90 is invisible) and e5 f298; the broad stance-window team
  read breaks e5 f298 (its spiker's approach snapshots read A while GT
  says B). The shipped gates (would-be≥3 + positive width) were chosen
  from these measurements; the final rule simulated IDENTICAL on e1-e6
  and exactly the two designed e7 field changes.
- **Shipped:** src/recognition/action_context.py (resolver only —
  cross_flip in resolve(), own_side_drive_block into _decide; docstrings
  updated; zero new constants/config). No classifier/tracker changes —
  ball_side was already threaded into every contact by team-aware
  attribution.
- **A/B:** e1-e6 BYTE-IDENTICAL (frames/labels/teams/ids/touch/conf);
  e7: f195 t3→t1, f242 block t1 → set t2. Eval (--ignore-player, actions
  component): e7 F1 0.625→0.75, P 0.833→1.0, R 0.5→0.6; e1-e6 unchanged
  at baselines. Production src.main e7: player_3 Set_Count 1 (was
  Block_Count), serve/set/dig counts match the script path.
- **Tests:** suite 375 green (+5 in tests/test_action_context.py: the e7
  chain end-to-end, width-evidence requirement, would-be-2 refusal, 
  same-team refusal, redirect-band/abstaining block preservation).
- **f316 GT suspect:** sheet output/e15e/reratify_e7_f315_team.png (f300-320,
  P<tid><foot-team> stamps, net line, f316 contact marked). The GT's f112
  "P1B" vs f315 "P1A" for the SAME track in the SAME rally is the
  primary contradiction; if the owner ratifies B, e7 team reads 1.0 with
  zero code change (the pipeline already emits team B, toucher track 1).
- Files: src/recognition/action_context.py, tests/test_action_context.py,
  STATUS.md. Artifacts (git-ignored): output/e15e/ (baselines, post-run,
  evals, sheet), output/probe_e15e/ (probe, sim, per-video streams+snaps),
  output/diag_e15e_*.py.

### 2026-09-09 (twelfth session) — open point 19: the inverted poke rule retuned (ascent-only typing)

- **Probe (output/diag_poke_retune_features{,2}.py, git-ignored):** v1 had a
  measurement bug worth recording — SpikeAnalyzer's spike RECORD carries no
  `contact_point` (only the EVENT does), so rise measured from the first
  post-contact sighting is the wrong reference. v2 captures the raw events
  and reproduces the analyzer's exact decision-time view. Measured over the
  eight pipeline spikes: rainbow touches cross 80 px rise at +4..+9f; the
  hards never rise (e3 f431 −25, f539 −34 at its dig-close, e6 f309 −30);
  e5's poke arcs 64.5 px saturating ~+15f with exit vx only 18-22; e6's
  hard exits level at |vx| 47. The shipped |vx|≥25/|vy|≤12 rule was
  measured-inverted; ascent alone separates.
- **Shipped (src/analysis/spike_analyzer.py):** TOUCH_RISE_PX 80 → 57 (the
  midpoint of the two measured boundary rises — e5's poke 64.50 above, e1
  f371 50.50 below), the |vx|/|vy| poke test + `_exit_velocity` deleted.
  The classifier's `_is_poke_drive` (team path) byte-untouched; comments
  reworded to the ratified reading (airborne-net-contact team gate, not the
  poke type).
- **A/B catch:** at threshold 50, e1 f371 (GT spike_type null, incumbent
  hard) flipped to touch — its ball rises exactly 50.5 px and floats. Not
  noise; the threshold moved to 57 rather than accepting an unratified
  change. Final A/B (output/poke19/post57 vs the p16-HEAD baselines in
  output/poke/post_actions): e1/e2/e3/e4/e7 BYTE-IDENTICAL; e5/e6 differ in
  exactly one field each (spike_type hard→touch / touch→hard).
- **Eval scorer fix (scripts/evaluate.py):** GT `overrides` are now merged
  into events before scoring — ratified corrections (e5 f300 touch, e6 f310
  hard) are gradable. Result: spike_type e3 4/4, e5 1/1, e6 1/1; teams
  1.0 everywhere; labels F1 e3 1.0 / e5 1.0 / e6 0.933 (unchanged FN = the
  unemittable no-touch block).
- **Tests:** suite 370 green. TestPokeType rewritten (moderate-slow-arc →
  touch with exit vx below the old bar; e6 level exit → hard; narrow drive
  → hard); the two POKE_EXIT constant-mirror tests replaced by a guard
  that the analyzer has NO poke-exit constants and the classifier keeps
  its own (the type/team concern split, drift-locked).
- **Production:** src.main e5 `298,1,4,B,touch,A3,out` and e6
  `309,3,1,A,hard,A1,out` — both flips confirmed end-to-end, e6 team A
  preserved.
- Files: src/analysis/spike_analyzer.py, src/recognition/action_classifier.py
  (comments only), scripts/evaluate.py, tests/test_spike_analyzer.py,
  tests/test_team_attribution.py, STATUS.md. Artifacts (git-ignored):
  output/diag_poke_retune_features*.py/.txt, output/diag_e1_f371_probe.py,
  output/poke19/.

### 2026-09-06 (ninth session) — open point 16: in-court preference in the association cost

Owner report (e6_ballmatch_joust_f296-320.png): track 2B on a far-court
passer-by, the real far-left digger never tracked, 1A flips to the right-edge
bystander across f310-312. Probe (output/diag_e6_walker.py, raw detections +
assignments + track state, all checked against the frames):

- f142: the digger's (track 3) detection blips 1 frame; a walkway bystander
  105 px away grabs the track via the CONTINUOUS branch of _may_feed_track
  (no observation gap). Track follows the walkway right (f142-188), coasts
  frozen f190-243, and the digger — detected in court every frame from f146
  — is never re-acquired (215 px from the drifted ghost): untracked to the
  end of the video. Track 2 squatted the same way at f214/f244/f256. The
  squats cascade into Hungarian CHAIN-SWAPS (a full matching with long jumps
  beats one unmatched track at the 1e6 sentinel): f305 track2↔track3 rotate,
  f311 P1 → right-edge bystander at 149.5 px (gate 150), team vote B by f314.
- Gate-style fixes measured and REJECTED (overlapping distributions): legit
  out-of-court feedings on e1-e5 reach 146.6 px jump / sim 0.17; e6 hijacks
  start at 105 px / sim 0.26; world-metre displacement explodes (17-25 m) on
  LEGIT feedings via the airborne-foot projection artifact.
- Shipped: off_court_cost_penalty_px (300) added to the Hungarian cost for
  out-of-court detections — a PREFERENCE, not a gate. Allowance rules
  (_may_feed_track grace/hold/serve-zone) untouched; below the 1e6 sentinel;
  uncalibrated courts unaffected. Config + ctor + FrameProcessor +
  dump_player_tracks wired, drift-guard row added.
- A/B (baselines completed before any edit): e1/e3/e5/e7 tracks byte-
  identical; e2 3 frames, e4 15 frames (same mechanism, benign — e4 now
  follows GT id4 back into court at f390, all analyze_tracking metrics
  identical); e6 198 frames healed (digger f146→end under id 3, no f311
  swap, P1 stays A). Actions: e1-e5/e7 identical; e6 event-identical with
  f309 player_id 4→3; e6 eval F1 0.933 / team 0.857 unchanged; production
  src.main e6 emits the identical post-fix stream.
- Residual: f309 team still B vs GT 1A — isolated to the reentry band's
  stance-window snapshot rule (nearest snapshot = f307, the first frame
  whose grounded foot crosses the net line; f297-306 read A). Moved to open
  point 15b for the classifier retune session.
- Suite 347 → 355 green (+7 TestInCourtPreference, +1 drift row).

### 2026-09-06 (eighth session) — squatter review: sideline straddlers lose their roster slot (e7 class)
- **Owner plan v2 ratified in-session** (goal + mechanism + parameters +
  acceptance criteria, all measured beforehand on the e7 diagnostic dump
  output/diag_e7_bystander.json): stop an off-court bystander who straddles
  the sideline from holding a roster slot and poisoning identity downstream.
- **Shipped**: squatter review by lifetime in-court fed fraction — see the
  Where-we-are entry above for the full mechanism. One mechanism; no
  classifier/tracker-history retuning; admission erosion untouched (open
  point 18's front-end lever is separate); GT edits none.
- **Validated** (clean-room A/B, separate processes): e1/e3/e4/e5/e6
  byte-identical; e2 changed from f127 exactly as the plan predicted (slot
  to a real player 61f earlier than the 08-29 hold-horizon reuse at ~f188);
  e7 changed f166-283 (slot at f166 vs the f262 colonization; no ghost tail;
  no re-admission; re-converge f284); action streams event-identical on
  e2/e7; eval unchanged both; suite 347 green. Rollback:
  `player_squatter_enabled: False` restores HEAD behavior exactly.
- **New open point 18** records the known limits (match-footage dead-time
  churn + the GAME OFF re-tune trigger, the irreducible f47-145 front end /
  admission-erosion lever, the 0.5 m cooldown vs a line defender, the
  not-built rolling-window variant).
- Files: src/tracking/player_tracker.py, src/utils/config.py,
  src/analysis/frame_processor.py, scripts/dump_player_tracks.py,
  tests/test_squatter_review.py (new), tests/test_config_drift.py,
  CLAUDE.md, STATUS.md. Artifacts (git-ignored): output/squatter_base2/,
  output/squatter_post/, output/squatter_actions_{base,post}_{e2,e7}/,
  output/squatter_ab_logs/ (incl. eval JSONs + the run scripts).

### 2026-09-06 (seventh session) — ball-matching rework: identity by trajectory + motion, never confidence
- **Owner report**: most missed actions trace to tracking the wrong ball —
  e6's serve matched a bottom-right spare; e7's rally events lost to
  rack/drill balls; practices and tournaments both contain many balls.
- **Diagnosis (output/diag_ball_match*.py dumps)**: four confidence-driven
  failure mechanisms — spare bootstrap (e6 f0), top-1 cull hiding the real
  ball (e7 f241-244 rack ball 0.90 over real 0.79-0.92), blind reset
  re-lock (e6 f17, e7 f245), and — once all candidates are visible — the
  growing coast gate admitting slow distractors (e1 f77, 21px from the
  prediction, not rejectable by any local rule).
- **Shipped**: detector returns all candidates + two-stage stationarity
  (remove at persist 0.55, flag `stationary_suspect` at 0.30); tracker
  motion-gated bootstrap/re-lock (8 px/f over a <=2-frame pair); locked
  admission = old rule + stationary-suspect override; out-of-view re-entry
  window (2x max_missing at the exit point) replacing reset when the coast
  prediction leaves court bounds. New config keys `ball_lock_min_speed`,
  `ball_lock_motion_window`, `ball_lock_max_jump`, `ball_lock_max_pair_gap`,
  `ball_selection_conf_window`, `ball_static_suspect_frac` (drift-guarded).
  Intermediate designs measured and REJECTED on A/B: all-candidates +
  min-dist selection lost e1's f87 set (distractor admission); strict
  short coast window lost e5's f60 dig cascade; pred-anchored coast gates
  broke e3's fast-contact dropouts. The shipped shape keeps the old
  GT-validated admission semantics except where the old path STARVED.
- **Validated**: suite 325 green; e1/e3/e4 action streams byte-identical;
  e2 0.571→0.533, e5 1.0→0.857 (one label/frame each), e7 4/9 with set f110
  newly detected (serve traded — open point 15a). e6: owner ratified the
  serve (f34 p4 A, "from 4A") and re-confirmed the joust GT; folded same
  session -> e6 F1 0.857 → **0.933** (only FN = the unemittable no-touch
  block). NEW owner finding parked as open point 16: track 2B squats on a
  bystander behind the far court, the real center-left digger is
  untracked, and 1A→2B/1B swaps across f310-312 — player-identity stack
  work, likely also heals 15b. Production src.main on e6 confirms the
  serve end-to-end. e7 GT folded from the owner's dictation (open point
  15f: ratify).
- Files: src/tracking/ball_tracker.py, src/detection/ball_detector.py,
  src/analysis/frame_processor.py, src/utils/config.py,
  tests/test_components.py, tests/test_config_drift.py,
  ground_truth/video_entreno_7_annotations.json, CLAUDE.md, STATUS.md.
  Diagnostics (git-ignored): output/diag_ball_match*.py + json dumps,
  output/ballmatch_{before,after*,prod}_e{1..7}, output/ballmatch_eval_*.

### 2026-09-05 (sixth session, round 3) — live GAME-ON badge latency + badge styling
- **Owner report**: live-debug shows GAME ON at ~f140 for a serve at f30;
  also asked: is it livedebug-only?; black background behind the game-state
  badge; do not overprint the "Court: CALIBRATED" sign (screenshot showed
  GAME OFF on top of it).
- **Diagnosis**: (1) NOT livedebug-only — the badge state is snapshotted
  per frame in both render paths, so the machine itself was late (proved
  via the annotated-save render flipping at the machine's frame). (2) NOT
  tracking recall (14c's old story refuted): the serve flight is tracked
  from f27; the toss's single flight frame splits the pre-serve quiet
  (6 < arm_quiet_frames 10), the burst gate can never arm on the serve,
  and the candidate-only badge waited for the next contact's burst (f107)
  → f136.
- **Shipped**: rolling sustained-flight provisional (20 flight frames in
  the last ``fast_confirm_window_frames``=90 — new drift-locked config)
  lights the provisional GAME_ON without a candidate; badge/CSV only,
  episode/point layers untouched. Badge: solid black plate, own line below
  CALIBRATED (tests/test_overlay_game_state.py).
- **Validated**: e3 badge ON f136 → f53; e3 batch A/B actions/spikes/points
  byte-identical; game-state video points/actions byte-identical, eval
  11/13, 0 false, 80.6% unchanged; GT-OFF provisional cost 61 s → 72 s
  (display-only); suite **305 green**.

### 2026-09-05 (sixth session, round 2) — serve-init semantics: provisional fast ON, serve-action arming, trailing-group fix
- **Owner feedback**: e3 live-debug shows GAME ON at f174 for a point
  starting f30 (too late); a far-side pass during game-off should not turn
  the game on; detect serves and make them the game's init; the coach-fed
  points (0:21 / 1:02) are forgettable; all serves from the near field in
  this practice; real matches easier.
- **Diagnosis**: three serve-discriminator candidates measured on the
  production-path dump, all refuted (width at burst start / static hold /
  near→tape→far crossing — see open point 14a). Serve detection from ball
  signals alone is not available on this footage; practice serves are
  serves.
- **Shipped**: provisional fast ON (fast_confirm_flights=20: live GAME ON
  at serve+0.9-2.4s, dimmed "GAME ON ~" badge + provisional flag in the
  frame dict/CSV; POINT segmentation untouched and byte-identical);
  serve_action_arms=True (classifier serve actions arm instantly, contacts
  ≤45f old only); finish() no longer extends a closed trailing group
  (pt12 stop +6.2s → −1.9s). Config + drift locks + 4 new tests.
- **Validated**: e2e 11/13, 0 false, 80.6% frame accuracy; offline replay
  points byte-identical to the validated list; e3 A/B byte-identical
  AGAIN; e3 live ON f174 → f136 (rest is serve-flight tracking recall);
  suite **300 green**.

- **Owner request**: game on/off machine using resources/video_entreno_game_state.mp4
  + ground_truth/gt_point_start_end.txt (13 points, whole-second MM:SS start/
  stop, ±1 s), to count points and avoid counting actions between points.
  Owner context: same footage/court as video_entreno_* (e1 calibration reused);
  PRACTICE — some points start from a coach-fed ball, not a serve; real
  matches expected easier.
- **Diagnosis (output/diag_gs_dump.py + diag_gs_analyze*.py + diag_gs_sim/grid,
  git-ignored)**: full-pipeline signal dump (8167f, ~100ms/f) → legacy
  GameStateManager locks GAME_ON forever (53.3%); EVERY ball-motion signal
  family overlaps between GT points and between-point practice; quiet-gap
  and flight-density episode rules both cap at 10/13; the separating signals
  are burst-after-quiet onset, sustained flight, and CONTACT recurrence
  (≤215f in-rally vs ≥262f across the pt06/pt07 boundary).
- **Shipped**: game_state_manager.py/game_state.py rewrite (episode → group →
  contact-chain-split + ≥2-actions point rule; params in
  DEFAULT_CONFIG["game_state_detection"]); deleted the 4 legacy analyzer
  modules + score_tracker; FrameProcessor single-step wiring + flush feeding
  (450f finalize delay — measured emission lags up to 399f); csv_exporter
  game-state timeline rewrite; json_exporter game_state block + action
  point_index (77/83 actions gated into points on this video); DB points
  table + actions.point_index (idempotent migration, ingest verified);
  live-debug GAME ON/OFF badge; scripts/evaluate_game_state.py;
  calibrations/video_entreno_game_state.json (copy of e1's — same camera,
  frame-diff verified); ground_truth/README.md documents the MM:SS format.
- **Validated end-to-end**: 11/13 one-to-one matched, 0 false, 0 merged,
  79.0% frame accuracy; 7/11 starts within ±1 s; offline replay through the
  production class = the pipeline output exactly. Misses action-recall-
  limited (open point 14). A/B: e3 byte-identical (actions + spikes).
  Suite **296 green** (+18 tests/test_game_state.py).
### 2026-09-05 (later session) — court heatmap landscape rotation; stale-cache diagnosis; CSS-cache busting
- **Report**: court "way too big", "does not show where attacks land and
  where they start from", "add a number as well as a heatmap".
- **Diagnosis before design**: blobs/counts were present and correct on HEAD
  (DB query + `_court_blobs` probe + headless-Chrome screenshot of the served
  page). The owner's screenshot showed the pre-session rendering (huge court,
  no CSS-styled elements) = stale `make ui` process + cached style.css.
- **Shipped** (src/web/app.py `_court_blobs`, player_detail.html, style.css,
  base.html): landscape 160x80 court (net vertical; attacks LEFT half →
  land RIGHT half), max-width 560px; numbers/labels inline-styled in the SVG
  (stale-CSS-proof); stylesheet link cache-busted by mtime via a new
  `style_ver` template global.
- **Verified**: suite 269 → **278 green** (+9 tests/test_web_court.py);
  served-page screenshots with the theme and with the stylesheet stripped
  (court + numbers still render); all pages 200 with the new link.

### 2026-09-05 (fifth session) — player-page court FIELD heatmap (SVG): two rounds
- **Owner request**: on the player tab, replace the counts (attack-zone
  bars + from\lands matrix) with "a heatmap of the field, a visual
  representation of the field" — bottom side where the player attacks
  from, top side where the attack lands.
- **Round 1 (rejected)**: a CSS-grid court of 18 numbered boxes with
  counts. Owner: not a field. Lesson: draw the court, not a table.
- **Round 2 (shipped)**: `player_detail.html` renders an inline SVG —
  80x160 viewBox (1 unit = 10cm), sand-tinted rect + boundary, faint
  dashed 3x3 zone grid per half, net band with posts at y=80, rotated
  half labels ("lands" / "attacks from") in a left gutter, and heat
  hotspots: blurred radial-gradient circles (r=15) at zone centers —
  orange gradient = attack origins (bottom), blue = landings (top),
  opacity = 0.35 + 0.65·count/half-max. Small white count labels on
  hotspots only; `<title>` tooltips give the landing kill/out/dug split.
  `src/web/app.py` `_court_blobs()` maps zone digits to court coordinates
  (attack half columns mirrored: net row 3-2-1; landing half 1-2-3 —
  world_point_to_zone's camera-view convention, unit-checked).
- **Data layer unchanged from round 1**: `metrics.player_metrics` returns
  `court_attack` / `court_landing` / `court_landing_outcomes` keyed by
  zone digit (team letter stripped, 180°-symmetric grid). The joint
  placement matrix survives in metrics + tests, unrendered.
- **Verified**: suite **269 green**; served page's SVG parses as XML;
  blob geometry asserts (zone 1 bottom-right-at-net, zone 9 top-left-deep);
  headless-Chrome screenshot output/ui_player_court_preview.png
  (git-ignored).

### 2026-09-04 (fourth session) — analysis DB, player labeling, local web UI; extraction/DB split by file contract
- **Shipped**: `src/output_gen/json_exporter.py` — `src.main` now writes
  `output/<stem>/pipeline_output.json` beside the CSVs (lossless action
  fields + spike records minus flights + video metadata + git-hash
  pipeline_version; presentation-only, action stream untouched).
- **Shipped**: `src/db/` — schema.py (SQLite `data/volley.db`, WAL,
  videos/players/video_players/actions/spikes), ingest.py
  (`python -m src.db.ingest <stem|dir|json>`; transactional overwrite of
  ONE video's rows via videos-UPSERT + actions/spikes DELETE — labels
  survive; caught in review that a videos-row DELETE would cascade-wipe
  video_players), labels.py (per-(video, track_id) labeling; track ids
  are per-video bootstrap artifacts), metrics.py (glossary in the module
  docstring: kill%/error%/dug%/hard%/touch%, zone distribution,
  attack_zone×landing_zone heatmap, dig%/digs, kill-block vs soft-block
  from rally continuation — ball-touching blocks only, aces parked).
- **Shipped**: `src/web/` — FastAPI+Jinja local UI (`make ui`): videos,
  video detail (rally-grouped timeline, spike table, label form with
  known-player datalist), players overview, player detail (metric cards,
  CSS bar/heatmap charts — zero JS deps). Makefile: ingest / ingest-all /
  db-reset / ui. pyproject: `[web]` extras. README §"Analysis Database &
  Local UI". .gitignore: data/.
- **Validated**: re-ran all seven entreno videos through `make run`
  (pipeline_output.json emitted everywhere), `ingest-all` — DB counts
  match CSVs + recorded baselines (e3 14/4, e6 6/2, e5 7/2, e1 8/1,
  e2 7/1, e4 7/2, e7 5/0); cross-video aggregation checked on a throwaway
  DB copy (real DB left unlabeled for the owner). Web smoke: all pages
  200, label POST 303→updated, 404s correct.
- **Later the same session: UI restyled to a modern dark theme** (owner
  request): dark palette with orange accent (style.css rewrite — sticky
  blurred header, gradient cards/metric tiles/bars, glow on heat cells,
  dark form controls with focus rings; CSS-only, still zero JS deps;
  breadcrumb links on detail pages).
- **Later still: player photos for labeling.** `pipeline_output.json` gains
  `snapshots` — per track up to 3 (frame, bbox) picks from the per-frame
  tracked_players the pipeline already emits (action-anchored moments
  first, then a neutral mid-video stance; exporter-only change, zero
  pipeline divergence). `ingest` materializes them into
  `data/thumbs/<video>/<track_N>.png` strips (crop with padding +
  min-aspect 0.45 widening so far-side players stay recognizable; stale
  strips wiped per video; skips gracefully if the source video moved).
  The label form shows the strips (click to enlarge) and the action
  timeline shows small per-track avatars. NOTE: thumbnails need the video
  file reachable at its recorded path; re-running `make run` regenerates
  snapshots. Suite 269 green (+7).
- **Gotchas**: sqlite3 needs `check_same_thread=False` for FastAPI sync
  handlers (threadpool); this venv has no pytest-cov → run
  `venv/bin/python -m pytest tests/ -q -o addopts=""`. Suite **262 green**
  (240 + 22: tests/test_json_exporter.py, tests/test_db.py).

### 2026-09-04 (third session) — e1 GT re-verified + folded: three mixed id conventions unified; ratification queue empty
- **Diagnosis before design** (output/diag_e1_gt_reverify.py, git-ignored):
  a consistency audit of the GT itself (team-per-id across the 44 box
  frames) + a per-event spatial table (which GT box the pipeline's
  attributed toucher lands in) + contact sheets (full-frame row + zoom-on-
  contact row, GT boxes/GT label/pred crosshair) + a per-id montage.
  Findings: (a) f0 numbers ids 2↔3 opposite to the other 43 frames —
  positionally continuous persons, only numbers swapped (this also explains
  the montage's "flipped" first cell the owner spotted — a person swap, not
  a rendering bug); (b) f260 id1 B is a one-off typo in the joust's nearest
  box frame; (c) the 9 events use THREE conventions — canonical (f114/f257/
  f258/f371), L-R (f89/f329), and f0-flipped (f36/f206/f277, where the
  dominant reading names a player on the wrong TEAM).
- **Owner ratification** (sheets output/gt_verify/e1_reverify_*): all
  proposals accepted; f371's spiker confirmed id2/LR3 A; f258's block ruled
  NO-TOUCH (e6 precedent). Fold (output/fold_e1_gt.py): events → canonical
  (f36→p2, f89→p1, f206→p4, f277→p2, f329→p1, f371→p2), f0 renumber, f260
  id1→A. id4 stays unannotated at f0 (never ratified).
- **Measured** (same predictions, no pipeline change): player_accuracy_
  spatial 0.125 → **0.875**, spatial_lr 0.5 → 0.125 (the mirror flip proves
  single-conversion), labels-only F1 0.706 / team 7/8 unchanged — every e1
  residual now known-class (f114 freeball pt 9, f206 overhand set pt 5,
  f257 joust one-emission: the pred's single emission is the block-A side
  while the ball touch is the spike-B side).
- Files: ground_truth/video_entreno_1_annotations.json, STATUS.md.
  Diagnostics (git-ignored): output/diag_e1_gt_reverify.py,
  output/fold_e1_gt.py, output/e1_reverify/ (fresh HEAD action log),
  sheets output/gt_verify/e1_reverify_*.

### 2026-09-04 (later session) — joust-split adjudicated (block present, no ball touch); live-debug spike logs gain origin/landing
- **Owner ruling on open point 10(a)**: at the e6 f308 joust there WAS a
  spike and the block WAS there, but the block never touched the ball.
  Therefore one manufactured contact is the complete detectable truth — no
  joust-split mechanism; a no-touch block has no ball-flight impulse and is
  outside contact detection by design. The GT f308 BLOCK (2B t1) stays as a
  physical event the pipeline legitimately cannot emit (same class as e2's
  held-ball release). No GT/code change from the ruling itself.
- **Shipped (presentation-only, zero pipeline divergence)**: live-debug
  spike logging — `_ingest_actions` appends the takeoff zone to spike
  emission lines (`-> spike (0.65) from A1`, via the new
  `SpikeAnalyzer.spike_zone_for(contact_frame)` query, which mirrors
  `spike_type_for` over pending+records); a new
  `LiveDebugProcessor._log_resolved_spikes()` (called per frame in BOTH
  render paths, after flush, and reset on 'r') logs `Spike resolved:
  contact frame 308 player 1 from A1 -> lands B7 (out)` the moment a record
  closes, re-logging on outcome flips (dug→kill pending-dug, kill/out→dug
  retro-conversion — the (frame, outcome) signature gates it). Formatting
  lives in the module-level pure `describe_spike_record()`
  (tests/test_live_debug_logs.py, no processor construction needed).
- **Verified on the real e6 two-pass run** (output/spike_log_e6, git-ignored):
  f173 `spike (0.50) from B3` → resolved `lands out of bounds (out)` →
  re-logged `dug at A8 (dug)` after the f216 dig; f308 `spike (0.65) from
  A1` → `lands B7 (out)`. Render/labels byte-identical to before (log-only
  change + a read-only analyzer query).
- Tests: +8 (spike_zone_for pending/after-close/miss; 7 formatter cases).
  Suite 232 → **240 green**.
- Files: src/analysis/spike_analyzer.py, src/analysis/live_debug_processor.py,
  tests/test_spike_analyzer.py, tests/test_live_debug_logs.py (new),
  STATUS.md.

### 2026-09-04 — reentry contact shipped: e6's out-of-frame joust spike manufactured; point 10's e2 "instance #2" refuted
- **Diagnosis first** (output/diag_reentry.py raw-sighting dump + annotated
  sheets output/gt_verify/reentry_e6_f262-320.png / reentry_e2_f160-174.png,
  git-ignored): (a) e6 — across the f308 joust the BALL tracker reset at f289
  (10 missing frames after the toss exited the top at f277) and ADOPTED the
  bottom-left spare, so the game ball's real re-entry descent (f301–310,
  seen by the raw detector at (1305,34)→(1332,268), ~24px/f, above the tape
  the whole way) NEVER reached _ball_history; the tracker re-locked the game
  ball only at f314, post-joust. The classifier's history: spare junk f302
  (34,118) → 12f gap → run start f314 (1152,278) then -48px/f flat above
  the tape — the joust impulse (vx +3 → -50) hidden in the gap. Free-flight
  fit: the toss arc cannot produce the observed re-entry; the impulse is
  the contact. (b) e2 — **the "instance #2" reentry story is REFUTED**: the
  tracker bridges the set-toss apex (f141→f149, gap 8, identity kept via
  the growing-gap tolerance), the GT-corrected spike at f167 is a plainly
  VISIBLE bounce (dense sightings, rises 148/136px) — the normal detector
  fires, and the event dies at the reach gate by 4px (nearest snapshot box
  top 144px from the ball vs CONTACT_REACH 140); the true toucher (GT p3 B)
  is airborne and coasted ~200px away mid-jump (t1B real f150 → f192).
  Re-classified under point 7 (reach/ghost-drift), not point 10.
- **Shipped** (REENTRY_* band in ActionClassifier._detect_contact, beside
  the bridge bands; gates: gap ∈ [8,30]; ≥2 real points in (c,c+7] moving
  ≥40px/f horizontally dominated, starting at/above the net tape; IDENTITY
  BREAK — the pre-gap point ≥200px from the run's backward extrapolation
  (e6: 1695px; e2 f149: 34px, refused); touch placed at the gap MIDPOINT
  (e6 → f308 == GT), point back-extrapolated, above the tape; attribution
  at the manufactured frame (1A's clean pre-swap f308 snapshot within reach
  via the near-net exemption); gesture ATTACK for kind="reentry" (bypasses
  the hands-overhead→BLOCK misread on a jumping toucher); emitted team from
  the takeoff stance [c-12, c-2] — the SpikeAnalyzer takeoff-window fix
  scoped to this kind, because contact-time airborne feet project deep
  (would have emitted B, GT is A). _detect_contact now returns a 5-tuple
  (…, frame) so the reentry can date the event off-c.
- **Measured (e6)**: +f308 spike t3 r1 (track 1 = the GT spiker, team A,
  conf 0.65) and f265 overpass→set (follow exists now): labels-only F1
  0.667 → **0.923** (P 1.0; the only FN is the GT f308 BLOCK — one
  manufactured contact per ball event; a spike+block joust-split is an
  owner decision), team 6/6. **A/B (output/diag_reentry_ab.py, identical
  feeding): e1/e2/e3/e4/e5 BYTE-IDENTICAL event streams**; evals unchanged
  (e1 0.706, e2 0.571, e3/e4/e5 1.0). Production src.main on e6: same
  6-event stream (CSV emission-anchored; spike conf 0.65 on player_1).
- Tests: +8 reentry (fires on identity break incl. midpoint frame +
  manufactured inc; rejects connectible gap / vertical run / slow run /
  below-tape run / gap-band edges; end-to-end spike with takeoff-team; no
  reach → no event); 3 call sites updated for the 5-tuple. Suite 224 →
  **232 green**.
- Files: src/recognition/action_classifier.py, tests/test_team_attribution.py,
  STATUS.md. Diagnostics (git-ignored): output/diag_reentry.py,
  output/diag_reentry_sheets.py, output/diag_reentry_ab.py, sheets
  output/gt_verify/reentry_*.png, runs output/reentry_{base,post}_e{1..6},
  output/reentry_prod_e6.

### 2026-09-01 — trail render fix: masked blend (owner-reported black boxes behind trail segments)
- **Owner report**: the red trail carried black rectangles behind its
  segments. Root cause: `draw_ball_trail` blended each segment's whole ROI
  via `addWeighted` — every background pixel in the rectangle was scaled by
  (1-alpha) toward black, not just the line's pixels.
- **Fix**: masked blend — the line is drawn anti-aliased on a scratch, and
  only the touched pixels get `roi*(1-a) + line*a`; the ROI's other pixels
  are untouched. Regression test pins it (uniform-200 background: off-line
  pixels inside the ROI stay exactly 200). Suite **224 green**; re-rendered
  production video verified visually (output/spike_prod4, git-ignored).

### 2026-08-31 — outcome semantics completed: kill = direct fall OR dug-and-dies-without-a-set (owner rule)
- **Owner adjudication**: the four e3 "kills" are three digs + one kill; the
  video is ONE point. Kill rule (now in GT README + analyzer docstring): the
  ball falls directly, OR is dug and dies without a set (on the defenders'
  court or out of bounds). A dig kept up (set follows) is just `dug`.
- **Shipped**: pending-dug watch in SpikeAnalyzer — a dug record stays
  provisional; any later touch event finalises `dug`, a CONFIRMED ball death
  flips it to `kill` at the fall point (`_detect_dug_death`: candidate
  landing must survive DUG_DEATH_CONFIRM_FRAMES=16 with no subsequent loft ≥
  DIG_LOFT_PX). The confirmation is load-bearing — diagnosed on dev5: without
  it all three kept-up digs read as kills because the descent into the
  setter's hands terminates like a landing while the set EVENT is still
  ~40-50f away (lookahead emission). The real f539 death bounces 12 px; set
  tosses loft 150+ px.
- **GT**: f178/f297/f433 → `dug` + `dug_zone` (the annotated zones
  reinterpreted as dig locations); f541 stays `kill` (landing B8 annotated,
  measured B7 — fall at world x≈1.9 m, one column left). evaluate.py gains
  dug_zone_accuracy.
- **Measured (e3)**: outcome 4/4, dug_zone 3/3, spike_type 4/4,
  attack_zone 4/4, team 14/14; landing_zone 0/1 (B7-vs-B8 residual).
  A/B stream still byte-identical (pure observer). Suite **223 green** (+2:
  dug-ball-dies → kill; dug-then-set stays dug).
- Files: src/analysis/spike_analyzer.py, scripts/evaluate.py,
  ground_truth/video_entreno_3_annotations.json, ground_truth/README.md,
  tests/test_spike_analyzer.py, STATUS.md. Runs output/spike_dev{5,6},
  output/spike_prod3 (git-ignored).

### 2026-08-30 — spike analytics: trail, touch/hard, 9-zone grid, kill/dug outcomes; f297 GT corrected
- **Diagnose first** (output/diag_spike_exit.py, git-ignored): dumped the real
  sighting stream around the four GT contacts. Three findings drove the
  design: (a) exit speed cannot separate touch from hard (touches launch
  19-29 px/f vertically; f431's hard ball left near-rest and fell under
  gravity) — post-contact ascent can (146-240 px vs ≤33 px, threshold 80);
  (b) every attack flight ends in a 220-340 px loft at the GT dig events —
  sand cannot rebound that high, so all four "kills" read as digs
  (retro-conversion gate DIG_LOFT_PX=90 built from this; f431 visually
  confirmed on the sheet); (c) airborne feet at contact project deep through
  the homography (f431 B5 from airborne feet vs B2 takeoff) — origin zone now
  uses the pre-contact snapshot closest to the net in [c-12, c-2].
- **Zone convention pinned by the GT anchors, not the sketch**: each half
  numbered 1-9 facing its OWN baseline (180°-symmetric; A1 image-right at the
  net, B1 image-left). The request's ASCII sketch is the 180° flip; the
  anchors (both A attacks from image-right = A1, f178 from image-right = B3)
  decide. Documented in world_point_to_zone + ground_truth/README.md.
- **Shipped** (pure observer; A/B byte-identical stream, 0 base-field diffs):
  SpikeAnalyzer (observe/flush/reset; records + trail/kill/type render
  queries) wired in FrameProcessor (+flush_actions feeds it the flushed
  contacts, reset_trackers resets it); overlay.draw_ball_trail (ROI-blended
  per-segment alpha, gap-aware) + draw_kill_marker + typed spike label colors;
  live-debug `_render_frame`/`_ingest_actions` render trail/KILL/spike-type
  in BOTH modes; test_action_recognition observes + enriches its log +
  renders pass-2; video_processor exposes results["spike_analysis"];
  csv_exporter writes `<stem>_spikes.csv`; statistics adds spike tallies;
  evaluate.py scores spike_type/attack_zone/landing_zone/outcome.
- **Measured (e3, vs corrected GT)**: spike_type 4/4, attack_zone 4/4, team
  14/14 (old f294 residual gone), labels: the f294/f297 pair now fails the
  player-spatial gate (pred center above the net resolves to the adjacent net
  player's box at the 10f-strided GT frame; pred team/player are right) —
  spike P/R 0.75 from that single gated pair. outcome/landing 0/4 pending
  point 12 (dug-vs-kill).
- Tests: +22 (zone grid incl. 180° symmetry + boundaries, ascent type,
  kill/out/dug/blocked/unknown, retro-conversion both ways, takeoff window,
  trail fade/gap, kill marker); suite **220 green**.
- Files: src/detection/court_calibration.py, src/analysis/spike_analyzer.py
  (new), src/analysis/{frame_processor,live_debug_processor,video_processor,
  statistics}.py, src/output_gen/{overlay,csv_exporter}.py,
  scripts/{test_action_recognition,evaluate,verify_action_labels}.py,
  ground_truth/video_entreno_3_annotations.json, ground_truth/README.md,
  tests/test_spike_analyzer.py, CLAUDE.md, STATUS.md. Diagnostics
  (git-ignored): output/diag_spike_exit.py, output/diag_spike_sheets.py,
  sheets output/gt_verify/spike_f*.png, runs output/spike_*.

### 2026-08-29 — off-court hold horizon: e2's out-of-court bystander loses its roster slot
- **Diagnosis** (output/diag_e2_tracking.py audit + sheets; streak probe
  output/diag_ooc_streaks.py over all six videos): the owner's "we get a
  hold of the player outside the court" = a right-side bystander (conf
  0.82–0.89, feet beyond the right sideline, x≈1660–1890) who straddled
  the line at bootstrap, seeded a track, then stepped out — and
  `_may_feed_track`'s continuous-match exception (no horizon, outranks
  grace AND zone rules) fed them for 415 frames. The server p1 (x≈73 at
  f0–8) was out-of-court AND beyond the 1m zone margin → never admissible;
  in court from f28 with no free slot. Earlier "0% out-of-court
  assignments" reads were a diag bug (`np.bool_ is False` never matches).
- **Measured safety margin**: max real-player continuous out-of-court
  streak across e1–e6 = 46f (e6 t3); e3's server 44, e5 42, e4 36, e1 1.
  Horizon default 90 = 2× margin, matching serve_zone_trial_frames.
- **Shipped**: `player_off_court_hold_frames` (config + ctor +
  frame_processor + dump_player_tracks + drift-guard row); the continuous
  exception expires past the horizon measured from the track's last
  IN-COURT sighting; zone-seed (never-in-court) tracks keep the existing
  regime (trial expiry governs them). Retirement is the NORMAL path (coast
  → max_disappeared → dormant) — no new eviction machinery; the freed id
  came back via new-track/gallery-restore on an in-court player.
- **A/B (output/diag_ooc_ab.py, identical feeding)**: e1/e3/e4/e5/e6 **0
  differing track frames, identical action streams**; e2 differs from f104
  only (bystander coast), action stream unchanged except f256's attributed
  track (1→2; label/team/touch identical). Production e2 re-run: F1 0.571
  unchanged.
- **Gotcha for future diag harnesses**: two PlayerTracker instances in one
  process permute bootstrap ids — `cv2.kmeans` consumes the process RNG
  (verified: identical params, sequential instances → [2,3,1,4] vs
  [4,1,3,2]; `cv2.setRNGSeed(0)` per instance fixes it). Production
  single-run is deterministic. First A/B attempt was confounded by exactly
  this (e1/e2/e6 showed id-swap diffs from f7).
- Tests: +5 (within-hold allowed, beyond-hold blocked, zone-seed regime
  unchanged, end-to-end slot-freed incl. the bystander-never-tracked and
  newcomer-takes-slot assertions); suite **198 green**.
- Files: src/tracking/player_tracker.py, src/utils/config.py,
  src/analysis/frame_processor.py, scripts/dump_player_tracks.py,
  tests/test_bystander_guard.py, tests/test_config_drift.py, STATUS.md.
  Diagnostics (git-ignored): output/diag_e2_tracking.py,
  output/diag_ooc_streaks.py, output/diag_ooc_ab.py, output/ooc_e2/,
  sheets output/gt_verify/video_entreno_2_tracking_f*.png.

### 2026-08-27 — short-gap bridge shipped (e2/e6 missed digs); e2/e6 GT honesty work; joust diagnosed as "reentry" class
- **Diagnosis first** (output/diag_e6_missed.py gate trace + sheets, e2 the
  same via its ball dump): e6's 4 missed GT contacts are TWO classes, not
  one. (a) f212 dig: 6f occlusion at the digger's arms — sightings f208/210
  descending to y482, f216 already at y338 rising; gap 6 sits below the
  bridge floor (8f) while the normal path has 1 left / 0 right points
  within NEIGH (can't fire); even gap-allowed, the right side is SPARSE
  (only f224 in the next 12f). e2 f206 identical class (7f gap, dense
  right). (b) f311 joust: structurally invisible — see new open point 10.
- **Design lesson recorded:** the obvious sparse-right fix (extend the
  right window to c+12) CANNOT work — contacts are confirmed at
  c+CONTACT_DELAY and the right window ends at c+6, so those points are not
  in history at decision time (first A/B run "passed the gates" and then
  silently refused for exactly this reason). Deferred evaluation was
  considered (pending state + ordering guards) and rejected; the
  CROSS-GAP RISE gate needs no future points and is physically tight: a
  sand rebound cannot rise 60px in ≤6f and a free-flight apex cannot
  produce it from a ≥20px descent.
- **Shipped** (`_bridge_contact` + `BRIDGE_SHORT_MIN_GAP/BRIDGE_X_CONT_*`):
  short band gap 5–7, gates = normal-path-proof (sparse NEIGH on ≥1 side —
  e6 f265 fires NORMALLY at gap 6, the bridge must not relocate it) +
  x-continuity max(24, 3·gap) + the classic left-descent shape + cross-gap
  rise when the right window is empty. Classic band 8–14f untouched.
- **A/B (subclass harness, identical feeding, all six videos):** e1/e3/e4/e5
  streams byte-identical (every short-band candidate refused: dense-NEIGH
  or x-discontinuity 68–118px — e5's spare windows f320/f325); e2 +f209 dig
  t1/r2 (the 91f gap lands as rally reset, matching GT's possession
  numbering) and the cascade heals: f256 dig→SET t2, f306 spike t2→t3; e6
  +f216 dig t1/r1, f265 dig→overpass t2 (GT set — the follow it needs is
  the joust; open points 9+10). Production script path re-run: e2/e6
  identical to the A/B streams, e5's 7-event stream identical to the
  validated one (f17 serve … f299 spike 0.65).
- **Eval (GT as-is, labels-only):** e2 F1 0.222 → **0.600** (P 0.5 / R 0.75;
  3/4 matched, labels 3/3), e6 0.545 → **0.667** (P 0.8 / R 0.571; 4/7
  matched, labels 4/5). With point 11's GT additions ratified, e2's
  denominator grows to 7 and its unmatched preds become matches.
- **GT honesty (owner review pending — NOT folded):** e2's 3 unmatched
  preds are real touches (f32/f118/f327, sheets in output/gt_verify/);
  e2 f79 is a caught/held feed ball (static f78–82) — pipeline-invisible BY
  DESIGN, correctly refused by the new gates (ascent 0 at the catch, drop 0
  at the toss); e6 f311 block team B→A proposed.
- Tests: +6 (dense-right fires, cross-rise fires, dense-NEIGH stays
  normal-turf [asserts the normal path DOES fire there], identity jump,
  no-descent, classic band keeps ≥2 right); suite **193 green**.
- Files: src/recognition/action_classifier.py,
  tests/test_team_attribution.py, STATUS.md. Diagnostics (git-ignored):
  output/diag_e6_missed.py, output/diag_shortgap_ab.py,
  output/diag_e2_unmatched.py, output/diag_e6_f216_reach.py,
  output/shortgap_e{2,5,6}/, sheets output/gt_verify/.
- **Owner ratification round (2026-08-28, same working session):** e2
  +f118 set 4B t2 and +f327 dig 4B t1 folded (GT 4→6 events, labels-only
  F1 0.222→0.667); e6's joust re-corrected to f308 spike **1A** t3 + block
  **2B** t1 (the old f311 p4-B/p3-B pair was wrong on BOTH roles; A's
  3rd-touch spike is the volleyball-consistent reading — A dug f212, set
  f262); e1's joust arbitration ratified as-is. New observations recorded:
  e2's f32 is a SERVE by an UNTRACKED server (event pending the owner's
  player_id/team; serve-zone admission unmeasured on e2); the e6 tracker
  swaps players at f311 (f308 labels correct — no tracking GT to measure);
  owner proposes a freeball label for touch-3 soft crosses (open point 9/11e).
- **Second ratification round (later, same session):** e2 f32 folded as
  **serve p1 A t1** (owner marked the untracked near-left server in white
  on the f24-44 sheet) → e2 GT complete at 7 events, labels-only F1 0.615
  (the two label misses now visible and known-class: untracked-server
  serve, 91-frame-gap overpass). **freeball adopted** into the GT vocab
  (overpass = touch-1/2 crossing, freeball = touch-3+ soft cross); e1 f114
  relabeled; emission parked on the crossing signal (point 9). Ratification
  queue down to: e2 f79 semantics + e1 id wobbles.
- **Third round (owner re-scrubbed e2 end to end):** f79 DROPPED (no dig
  there); rally corrected to serve f32 p1 A → dig **f90 p3 B** (reception)
  → set f120 p4 (frame fix) → spike **f167 p3 B t3** (new — explains the
  f185–202 descent) → f206 dig p3 A (preceded_by_attack→true) → f257 →
  f305 → f327. e2 GT = 8 coherent events, labels-only F1 0.571; residuals
  all known-class (2 recall: held-ball release + reentry-f167; 2 label:
  untracked-server serve, 91f-gap overpass). Owner tracking observations
  folded into point 7 (out-of-court squatter on e2; server tracked early
  then lost; p3 untracked at f90) and e2-f167 added as reentry instance #2
  in point 10 (descending sub-shape vs e6's horizontal one).

### 2026-08-26 (later session) — e2/e6 generality check clean; e1's "contact recall" was double-annotated GT
- **Generality check (e2/e6, first runs on the current stack):** zero
  bridge candidates on either video — the strict gates hold on unseen
  footage; teams 1.0 on every scored pair. e6: 3/7 GT contacts, all three
  labels right (dig/set/spike); the f262 set→dig is the missed f212 dig's
  touch-count cascade (e5's pattern), f311 spike+block missed. e2: 2/4
  matched (f305 spike ✓; f257 set→dig cascade from the missed f206 dig);
  3 unmatched preds (f32/f118/f327) — e2's 4-event GT is likely incomplete
  (the e4-f182 lesson: unmatched preds on sparse GT need contact sheets
  before trusting precision). **e2/e6 are now the real contact-recall
  evidence** (detection-limited), not e1.
- **e1's GT was double-annotated**: two annotation passes interleaved, 17
  events for ~9 touches (f277 duplicated verbatim; twins at ±1-2f
  throughout; the passes disagree on frames, touch numbers, and teams). The
  recorded "e1's misses are contact-detection recall" was an artifact.
  Dedup applied (17→9): twins merged (f36, f89, f277, f329, f371); f114/115
  arbitrated to **overpass** (ball rebounds off the net line into the far
  half with no further A touch — trajectory-proven); the f252-258
  four-fragment cluster arbitrated to ONE spike+block joust at the single
  f257-258 trajectory contact (f257 spike p3 B attacking B's f206 toss,
  f258 block p1 A fully airborne). Sheets: output/gt_verify/
  video_entreno_1_f{114,255}.png — **owner ratification wanted** (p3 as
  the spiker is inferred from jump geometry; no pass ever names p3).
- **e1 after cleanup: 8/9 contacts detected, labels 5/8, teams 7/8, F1
  0.471** — and the three residuals are known-class, none recall: (a) f113
  dig vs overpass — the resolver only detects overpass at touch-2, this was
  touch-3; (b) f208 dig vs set — B's overhand reception of the overpass at
  touch-1 (pose-level label, open point 5 class); (c) a joust emits one
  contact for two GT events.
- e1's GT still has id/team wobbles beyond the deduped events (e.g. f277
  names p3 whose box is far from the ball's position at the dig) — needs a
  dedicated re-verification session, not spot fixes.
- Files: ground_truth/video_entreno_1_annotations.json, STATUS.md.
  Diagnostics (git-ignored): output/diag_video_entreno_{2,6}_ball.json,
  output/gen_e{2,6}/, sheets above.

### 2026-08-26 — e5 action layer fully resolved: gap-bridged bounce + 2.5m net exemption (old open points 1+2); GT folded; eval convention fix
- **GT folded (owner dictation 2026-08-18 + contact-sheet arbitration).**
  e5: serve f20 p2 added (right-side server = GT2; pred f17 center inside
  its box), frames 60/110/159/197 → 63/111/160/200, ids f63 p4, f111 p3,
  f200 p2 ("overhand dig" kept in raw_visual_actions, final_action `dig` —
  canonical vocab has no overhand dig), f250 p1, f300 p2. e4: f133 p3,
  f276 p2, f224 pre_atk→true. Two corrections were OURS and are now
  owner-ratified (2026-08-26, from the sheets): e5 f160 p3→p4 and f300
  p4→p2 — both proven on dumped sheets (the named players stand flat-footed
  while another is airborne under the ball) + trajectory contact points.
  e4 f182 spike p4 ADDED and likewise ratified (un-annotated real touch:
  GT4 airborne at net, ball crosses to A; fixes e4's phantom-precision).
  flag_occluded_gt run on both (e4 4, e5 9 flags).
- **evaluate.py: GT action player_id conventions differ across files** —
  e1/e3 are L-R indices (probe: e3 canonical 2/14 vs L-R 12/14; e1 1/8 vs
  5/8), e4/e5 are canonical (6/7 vs 4/7; 4/5 vs 1/5). Per-action TP gating
  is now spatial + convention-agnostic (pred center → containing GT box,
  match under either convention; raw-id fallback without gt_players) and
  both `player_accuracy_spatial` (canonical) and `..._lr` are reported.
  Consequence: e3's gated F1 was 1.0 only by numeric coincidence (the f69
  known misattribution scored pid 2 == gt 2); honest value 0.929.
- **Diagnosis (instrumented replay, output/diag_e5_*.py):** e5's 3 label
  errors + 2 missed contacts were ONE root cause. The f111 set was
  undetectable (ball sightings stop descending f102, resume rising f114 —
  occluded at the setter's hands, spare ball stole top-1 meanwhile), so the
  f60→f157 gap (97f) exceeded rally_reset_gap=90 → new rally → f157
  touch-1 dig (GT spike); f196 became touch-2 set (GT dig); f247's foot
  142px > NEAR_NET_PX → dig (GT set). The f300 spike WAS detected (bounce
  at f301, prominence 171/101) but died at the reach gate: the spiker's
  per-contact foot team read B at 2.14m from the net while the width
  regime (36–40px) said near/A, and the 1.5m exemption missed by 0.64m —
  the only surviving candidate was 316px away (> CONTACT_REACH 140).
- **Shipped:** (1) `_bridge_contact` in the classifier — a bounce whose
  bottom sits inside an 8–14-frame sighting gap fires at the gap's first
  sighting (that frame's normal tests provably cannot fire: no left points
  within NEIGH), touch point interpolated; gates: ≥2 real points each side
  within 6f, net descent ≥20px, net ascent ≥60px (sand rebounds rise ~25px
  and must not read as touches — e5 f332-340). History scans: e1/e3/e4 have
  ZERO qualifying gaps → streams unchanged (A/B: e1/e4 byte-identical; e3
  differs only in f539's self-reported L-R index, same attributed player).
  (2) `attribution_near_net_exempt_m` 1.5→2.5 across config/ctor/fallback
  (drift-guarded). e5 then emits 7/7 with all labels right; f299 even reads
  gesture ATTACK → spike 0.65.
- **Measured (vs corrected GT):** e5 actions 7/7 matched, labels 7/7,
  teams 7/7, players 6/6 scored (gated F1 0.857 — the f114 bridge pair's
  GT box is occlusion-flagged so its player gate can't score; same
  conservative no-box rule as e4 f347's ±17px temporal skew). Anchors:
  e1 0.4 / e3 0.929 / e4 0.857 gated F1, all identical pre/post change.
  Production `src.main` on e5 emits the same 7-event stream (players,
  labels, confidences; CSV frame column is emission-anchored, +50 const).
- Tests: +7 (bridge fires / short-gap / too-long / sand-bounce / no-descent
  / MIN_CONTACT_GAP / spatial-either gating) + 1 updated (B_VERY_DEEP for
  the 2.5m exemption); suite **187 green**.
- Files: src/recognition/action_classifier.py, src/utils/config.py,
  src/analysis/frame_processor.py, scripts/evaluate.py,
  ground_truth/video_entreno_{4,5}_annotations.json,
  tests/test_team_attribution.py, STATUS.md. Diagnostics (git-ignored):
  output/diag_e5_ball.py, output/diag_e5_contact.py, output/diag_gt_pairs.py,
  output/diag_*_ball.json; sheets output/gt_verify/*f160/f182/f300*.png.

### 2026-08-18 — entreno_5 serve-zone squatter fixed: server vote + trial expiry + contested swap (old open points 2+8)
- **Diagnosis** (owner live-debug report + audit trail): bootstrap locked 3
  tracks at f8 (server stands behind the near baseline, never in the strict
  pool); the create loop then admitted a STATIONARY bottom-left bystander
  through the serve-zone exemption — detection order was by confidence and
  the bystander out-scored the real server — and held the 4th slot for all
  354 frames (continuously detected → off-court grace never burns; seed has
  `last_in_court_frame=None`). The server (GT2) was covered in 1/36 GT frames
  → every action after the first dig misattributed.
- **First attempt (single-frame ball anchor) failed and taught the real
  geometry**: the top-1 ball on the admission frame was a SPARE ball lying
  near the bystander (633,794) — inside the bystander's column ABOVE the
  waist, because a close-camera bystander's chest height projects where sand
  3-5m behind them does. Distance/nearest-ball anchoring admits the bystander
  by construction; the discriminator is temporal (the spare is static-
  suppressed after `static_min_frames`, the toss ball then sits over the
  server f8-20).
- **Shipped design** (player_tracker.py): (1) **server vote** — a serve-zone
  candidate is only admissible with ≥`player_serve_zone_ball_votes` (2)
  recent ball sightings inside its x-span column above the waist; live ball
  history + no qualifying candidate ⇒ zone admission defers that frame; no
  ball history at all ⇒ legacy confidence order. (2) **contested swap** — an
  admitted seed whose column the ball has LEFT (last-3 sightings) while
  another candidate has the votes is hard-removed (cooldown bbox, not
  gallery) and the true holder takes the slot — e5 swaps bystander→server at
  ~f10. (3) **trial expiry** — a seed never in court within
  `player_serve_zone_trial_frames` (90) is hard-removed with cooldown (the
  "does not let it go" backstop). `update()` gained `ball_position` (top-1
  ball det) wired through FrameProcessor / dump_player_tracks /
  test_action_recognition; config keys + drift-guard rows added.
- **Measured (e5)**: tracking detection 0.722→**0.958**, ghosts
  0.278→**0.042**, id 0.986, team 0.978; GT2 (server) 1/35→**34/35**; actions:
  serve detected for the first time (**f17** vs owner's f20), dig f60 ✓,
  f196/f247 land on the right players (formerly untracked); label residuals
  are the resolver's dig/set/overhand-dig confusion + 2 missed contacts
  (open point 2).
- **Regression gate (byte-level A/B via git stash)**: e1 — **0 differing
  frames** (the apparent 0.978→0.771 id drop reproduces identically on HEAD;
  pre-existing drift, now open point 3); e3 — 7 frames differ (server
  admitted ~6f later, metrics 0.973/0.063/0.952→0.969/0.064/0.952), **action
  stream byte-identical** to the validated 14/14 attrib_e3_new2 log; e4 —
  identical numbers.
- Tests: +11 (server vote incl. the sand-ball non-vote + swap + trial +
  cooldown); suite 180 green. Old open point 8 (crowded-drill serve-zone
  watch) closed — implemented, plus a stronger mechanism than the n_court_det
  gate it suggested.
- Files: src/tracking/player_tracker.py, src/utils/config.py,
  src/analysis/frame_processor.py, scripts/dump_player_tracks.py,
  scripts/test_action_recognition.py, tests/test_serve_zone.py,
  tests/test_config_drift.py, STATUS.md. Artifacts (git-ignored):
  output/e5_fix/, output/gt_verify/ (6 owner-verification contact sheets),
  output/diag_e5_admission.py, output/diag_e1_states.py.

### 2026-08-18 — entreno_4/5 GT checked: structurally valid; 6/12 action player_ids are mis-IDs (teams right)
- Owner added GT for entreno_4 (40 player frames @stride 10, 6 action events)
  and entreno_5 (36 frames, 6 events). Schema identical to e3; bboxes all sane
  and in-frame; court corners + net posts identical to e3 (calibrations 3=4=5
  byte-identical, same tripod spot) — and the player-box `team` labels are
  **100% consistent with foot-side geometry** (301/301 via
  `get_team_for_bbox`). No `visible` occlusion flags (pass not run), no serve
  events (drills start mid-rally), ball GT empty (as e3).
- **Finding:** in 6 of 12 action events the `player_id` contradicts the
  event's own `player_team` (the named player's feet are on the other half; 4
  contradictions at the exact annotated frame). Arbitration says the TEAM
  label is right and the PLAYER_ID wrong — annotator picked an adjacent
  same-area player. Evidence: where the pipeline detected the contact, its
  attributed player's center lands inside the corrected player's box (e4
  f133 p2→p3, f276 p3→p2; e5 f60 p2→p4, f250 p3→p1); e5 f110/f300 have no
  pred to arbitrate. → Open point 1 (owner re-verify; 4 suggested edits).
- **Baseline eval** (scripts on defaults; output/gt_check_e4|e5, git-ignored):
  - e4 actions P/R/F1 0.29/0.33/0.31 (7 preds vs 6 GT — the extra f182 spike
    may be a real un-annotated touch → precision unreliable until the event
    list is confirmed complete), team 1.0 (6/6), player-spatial 1.0 (5);
    tracking detection 0.949 / ghosts 0.026 / id 0.988 / team 0.987.
  - e5 actions P/R/F1 0.33/0.17/0.22 (only 3 contacts detected; both GT sets
    and both spikes missed — contact-recall problem under the side-noise),
    team 1.0 (3/3); tracking 0.722 / 0.278 / 0.993 / 0.981, GT2 matched 1/36
    frames → new open point 2 (roster may have locked onto a bystander
    quartet).
- No code changes; STATUS only. Run artifacts under output/gt_check_e4|e5/.

### 2026-08-17 — config-drift guard test built (candidate follow-up from the divergence fix)
- New `tests/test_config_drift.py` (54 tests) pins the four seams where
  production (`src.main`/live-debug) and the validated script paths can
  silently fork: (1) `DEFAULT_CONFIG` vs component **ctor defaults** (the
  scripts construct PlayerTracker/BallTracker bare, so ctor defaults ARE the
  script-side config — the original 30/90 + 100/150 drift lived here);
  (2) literal construction kwargs in test_action_recognition.py +
  test_ball_tracking.py, read by AST so editing a script literal without the
  config fails the suite; (3) the script's argparse defaults
  (`--pose-complexity`); (4) inline `<config>.get(key, fallback)` fallbacks in
  frame_processor / video_processor / main / dump_player_tracks. Deliberate
  divergences (ball_confidence 0.15 vs ctor 0.05, pose_complexity 0 vs ctor 1,
  action_confidence 0.3 vs ctor 0.4) are documented in the module docstring
  and pinned by the script tests instead. Two meta-guards keep the AST scans
  from passing vacuously if they stop matching.
- **Validation:** re-introducing the original drifts (config
  `player_max_disappeared`→30, main.py `ball_confidence` fallback→0.7) fails
  exactly the two expected tests; restored, all green.
- Same sweep defused **9 stale inline fallbacks** — dead today (every key
  exists in DEFAULT_CONFIG) but landmines the day a key is removed:
  frame_processor (ball_confidence 0.05, device "cpu" ×2,
  player_max_disappeared 30, pose_complexity 1, action_confidence 0.4),
  main.py (ball_confidence 0.7 — the old drifted value), dump_player_tracks
  (ball_confidence 0.5, device "cpu"). All set to the DEFAULT_CONFIG values;
  zero behavior change.
- Suite: 113 → **167 green**.
- Files: tests/test_config_drift.py, src/analysis/frame_processor.py,
  src/main.py, scripts/dump_player_tracks.py, STATUS.md.

### 2026-08-17 — live-debug showed block where the script said spike: config-default divergence FIXED
- Owner's live-debug screenshot (f562, red BLOCK label) disproved the morning's
  "never existed" verdict: a headless repro (`src.main --save-video`) shows the
  **production/live-debug path emits f539 → block (0.70)** while the script
  (and every GT number) says **spike (0.50)** — same contact, same player, same
  code, different CONFIG.
- Root cause: `Config.DEFAULT_CONFIG` had drifted from the constructor defaults
  the validated scripts run — `ball_confidence` **0.7 vs 0.15** (the starved
  ball history flips the f539 contact into the BLOCK gesture branch),
  `player_max_disappeared` **30 vs 90**, `tracking_max_distance` **100 vs
  150**. The tracking-section comment even claimed it "matches
  scripts/test_action_recognition.py". Verified no YAML/JSON override exists
  anywhere, so `src.main`/live-debug ran the drifted defaults silently.
- **Fix**: align `DEFAULT_CONFIG` to the validated values (0.15 / 90 / 150,
  with comments explaining they must not drift again); one stale assertion in
  `tests/test_components.py` updated; CLAUDE.md's "ball_confidence (0.7)"
  corrected.
- **Acceptance**: production headless re-run on entreno_3 emits the validated
  event stream EXACTLY (14/14 events, frames+labels+confidences identical to
  output/attrib_e3_new2; zero blocks). Pixel-level check of the user's exact
  screenshot frame f562: pre-fix 2400 block-blue px / post-fix 0 blue + 2711
  spike-red px, and the label region is the only changed area of the frame.
  113 tests green.
- **Correction of the morning entry below**: its "f539 block never existed in
  any run / born stale" conclusion was wrong — the archaeology ran the
  production path only at OLD commits (where the pre-attribution classifier
  didn't take the BLOCK branch at 0.7 either) and never ran CURRENT production
  code. The owner's original instinct (block appeared around the attribution
  change) was right: the attribution-era classifier + the 0.7-confidence ball
  stream produce the block; the script's 0.15 stream never does.
- Lesson recorded: GT-validate the PRODUCTION path too, or assert
  config-defaults == script-constructions in a test so drift like this can't
  silently fork the paths. (Candidate follow-up; not built today.)
- Files: src/utils/config.py, tests/test_components.py, CLAUDE.md, STATUS.md.
  Artifacts (git-ignored): output/livedebug_repro (pre-fix),
  output/livedebug_fixed (post-fix).

### 2026-08-17 — f539 "block" provenance settled: never existed in any run (owner challenge) — SUPERSEDED, see entry above
- Owner challenged the point-9 story: they remembered live debug showing f539
  as `spike` a couple of days ago and suspected the block→spike flip came from
  the team-attribution change. Git archaeology says: **their memory was right
  and the flip hypothesis wrong — f539 was spike before attribution too.**
- Evidence: detached-worktree runs of the PRODUCTION path (src.main =
  FrameProcessor = what live debug shows) at `128e53a` (Aug 15 morning, i.e.
  before BOTH the ghost exclusion d219aae and the attribution f276ca8):
  f539 → `spike (0.50)`, zero blocks in the whole timeline; the action script
  (buggy feeding and all) at the same commit: `Frame 539 → spike`; the
  attribution session's own diagnostic (output/diag_attribution2_run1.txt):
  spike; every attrib_e3_* log and the current state: spike.
- The "categorized as block" text first appears in STATUS at `6bd07c1` (Aug 17
  perf session), claimed to be folded from "the stale duplicate Open-points
  section" — but no committed STATUS version contains it (checked 970430e,
  d219aae, 63ec741, f276ca8, 663e455; the duplicate section's 5 items have no
  f539). Point 9 was **born stale** — a mis-sourced note at fold-in time, not
  a real regression that later got fixed.
- Incidental pre-fix-era observations recorded while there: the Aug 15
  production run misses the serve (no serve-zone admission yet) and instead
  emits a 14th contact ~f620 `overpass` that the current pipeline doesn't
  (contact-set drift between eras, worth remembering when comparing old logs).
- STATUS.md only (worktrees removed after use).

### 2026-08-17 — entreno_3 GT serve frame fixed (old open point 3)
- Owner scrubbed the dumped frames and confirmed the serve contact at **f29**
  (pipeline's own detection); GT event re-annotated f56 → f29 (single-line
  JSON edit, `git show 357cc14`). Eval on the existing prediction log
  (output/attrib_e3_new2): matched_pairs 13 → **14**, serve P/R 0 → 1, label
  **F1 0.929 → 1.0**; team unchanged 0.929 (13/14, the f294 over-set residual,
  open point 2). Footnote: player_accuracy_spatial now reads 0.857 (12/14)
  vs 0.923 (12/13) before — the serve pair entered spatial scoring and is one
  of the misses (it was previously unscored, not correct; no regression).
- Files: ground_truth/video_entreno_3_annotations.json, STATUS.md.

### 2026-08-17 — live-debug frame counter
- Small HUD added: `overlay.draw_frame_counter` (top-right, white text on a
  black underlay so it reads on sand too, format `f<idx>/<total>`), drawn in
  `LiveDebugProcessor._render_frame` — so both the `--debug-live` window and
  `--save-video` output now carry the frame number, matching how every event
  is referenced (GT annotations, STATUS, eval reports). Render-only change;
  pipeline untouched (mirrors-the-pipeline rule). Standalone
  `test_action_recognition.py` videos unchanged (noted in the class
  docstring). 113 tests green.
- Files: src/output_gen/overlay.py, src/analysis/live_debug_processor.py.

### 2026-08-17 — near-net gesture flag: point 9 stale, point 4's switch GT-refuted (no code change)
- **Point 9 did not reproduce**: the shipped state labels entreno_3 f539
  `spike` (GT f541 spike ✓, one of 4/4 correct spikes); it was folded in from
  a pre-attribution-shipment stale section. No block mislabels exist on any
  GT footage — the pipeline's only emitted block (entreno_1 f255) is genuinely
  at 0.23 m from the net.
- **Diagnosis first** (`output/diag_gesture_net.py` + saved per-variant JSONs,
  git-ignored; runs the exact test_action_recognition feeding under a
  monkey-patched `is_near_net`): the naive point-4 switch to ground metres
  REGRESSES entreno_3 label F1 0.929 → 0.857 (≤2m) / 0.714 (≤1.5m), because
  `near_net` also gates the resolver's touch-3-at-net spike rule
  (`action_context.py:146`): GT spikes f174/f431/f539 were hit from
  1.79/3.77/1.96 m and rely on the px far-half swallow to read "near net".
  Keeping all labels needs M≥4 m = re-encoding today's behaviour under a
  false name. The GESTURE layer itself is rule-insensitive on all GT footage
  (identical gestures under px/m1.5/m2.0 on entreno_1+3); the px boundary is
  absurd in the abstract (server at 8.4 m reads far, digger at 8.0 m reads
  near) but nothing we own can tell the rules apart.
- **Owner decision**: record, no production change. Revisit with match
  footage via the diag script; switch only if gestures differ there.
- Diag-tooling gotcha recorded: `classify_actions` builds contact k but
  EMITS contact k−1 (one-contact look-ahead) — per-contact foot diagnostics
  must zip build-order calls with event order, not attach per invocation
  (the first table was shifted by one contact).
- Files: STATUS.md only (diag script + JSONs git-ignored under output/).

### 2026-08-17 — perf: detector device defaults, annotator I/O, pose-lite default
- **Measured first** (output/diag_perf_*.py, git-ignored): per-frame pipeline
  on entreno_3 = ~102ms core (pose 52ms CPU + ball 23 + player 25 MPS;
  trackers/game-state ≤1ms); the live-debug loop adds serialized
  waitKey(33ms)+render on top → ~5-7fps. The ANNOTATOR was ~150ms per
  interaction because BOTH its detectors ran on CPU:
  `BallDetector`/`PlayerDetector` shadow `BaseDetector`'s `device="auto"`
  with their own `device="cpu"` defaults, so every bare construction
  (annotate_video, test_action_recognition, dump_player_tracks, auto_label,
  test_* scripts) silently inherited CPU. Also: `cap.set` forward seek = 65ms
  vs 6ms for 5 sequential reads.
- **Fixes**: detector device defaults → "auto" (docstrings updated);
  annotator `_seek_frame` uses sequential reads for forward steps ≤64 when
  the capture cursor is contiguous, plus `_use_frame` cursor bookkeeping;
  detections memoised per (frame, mode-class — PLAYER/ACTION share one slot)
  so revisits/mode switches/undo are free; `pose_complexity` default 1→0
  (lite, ~1.6x faster pose) adopted only after the A/B; `--pose-complexity`
  arg on test_action_recognition.py (default 0 = production, so eval runs
  can't silently diverge from the pipeline again).
- **GT regression check** (entreno_1 + entreno_3, players + actions): all
  four eval JSONs BYTE-IDENTICAL across baseline (CPU detectors, pose 1) →
  post (MPS detectors, pose 0). entreno_3 tracking 0.961/0.064/0.972/1.0,
  actions team 0.923 / player-spatial 0.923 (13 pairs); entreno_1 team 1.0 /
  0.625 (8 pairs) — unchanged from the 2026-08-16 session. 113 unit tests
  green (run via `venv/`, not `.venv/` — only the former has pytest).
- **Measured gains**: annotator click-advance ~150ms → ~30-40ms (revisits
  ~0ms); pipeline per-frame ~102 → ~81ms (pose 52→33ms end-to-end).
- **Deliberately NOT done**: live-debug pose near-ball gating (52→~26ms
  measured) + producer/consumer display decoupling — owner wants live debug
  byte-identical to the shared pipeline while debugging for real. Levers
  recorded here for whenever they're wanted.
- STATUS.md cleanup: removed the stale duplicate "Open points" section (it
  predated the attribution shipment); its one fresh item (f539 block bug) was
  folded into the live list as point 9.
- Files: src/detection/{ball_detector,player_detector}.py,
  scripts/annotate_video.py, scripts/test_action_recognition.py,
  src/utils/config.py, STATUS.md.

### 2026-08-16 — team-aware contact attribution shipped (old open point 2)
- **Diagnosis first, and it changed the design.** The sanctioned retry
  ingredient (incoming-trajectory IMAGE side) was refuted by the diagnostic
  (output/diag_attribution2.py + probes, git-ignored): an airborne ball over
  the NEAR half projects ABOVE the midcourt line (line y≈600, net top y≈300,
  far baseline y≈490), so GT-A contacts f211/f244/f453/f488 all read "B";
  worse, the ball is often undetected during near-half approaches (occlusion
  by the large near players) — every A-contact window had 0 samples. Ball-size
  → ground-depth inversion also fails (an airborne ball is always closer to
  the camera than the ground under it → everything reads near-side), and a
  pinhole decomposition of the 4-click homography doesn't close (0.033
  orthogonality residual, reconstructed feet ~30m off).
- **f76 mystery solved (two findings).** The f76 contact is the GT f69 DIG by
  a far-side player (ball descending into GT4's box) — the earlier "serve
  misattribution" reading conflated it with the serve. The REAL serve contact
  is ~f30 (toss apex f23) and had been REJECTED (d=177.8) because
  scripts/test_action_recognition.py fed the tracker the strict in-court set
  without `strict_detections` — serve-zone admission never fired in the action
  pipeline (production FrameProcessor was already correct). Also found
  max_players=6 hardcoded there vs the production 4.
- **Shipped design** (src/recognition/action_classifier.py): expected touch
  team = ball pixel WIDTH regime (w<26 → far/B, w>35 → near/A, else abstain;
  any disagreeing sample blocks) when it commits, else possession
  alternation (flip after ATTACK/BLOCK/serve gestures, carry after dig/set;
  unconstrained on rally reset). `_closest_player_at` filters candidates by
  per-contact foot team (`get_team_for_bbox`), exempts wrong-team candidates
  only for block geometry (feet ≤1.5 ground metres from the net via new
  `CourtCalibration.world_dist_from_net` AND contact above the net-top line —
  image-px bands swallow the whole far half, and without the above-net gate a
  net-standing setter steals sets, f488), relaxes when the filter empties the
  set, and breaks 0.0-dist ties by centre distance. Emitted `team` is now the
  toucher's foot team (`team_in_possession` kept for observability) — the
  resolver's latch used to mask thefts behind an inherited label. Ball history
  now carries (frame, x, y, w, h). Resolver label/touch logic deliberately
  UNCHANGED (crossing-based touch counts match GT 14/14 on numbers but relabel
  f379 set→spike via the touch-3-at-net rule).
- **Measured** (13 frame-matched pairs, A/B = same feeding fix +
  `--no-team-aware`): team 0.692 → **0.923**, player-spatial 0.769 → **0.923**,
  label F1 0.897 → **0.929**; serve detected + labeled (f29, containment).
  Fixed: f211, f563, f488 (+ serve). Remaining miss: f294 over-set (width
  abstained 29–40px through the gap) — open point 2. entreno_1 regression:
  team 1.0 / player 0.625 identical across A/B, precision 0.778→0.875, recall
  unchanged (its misses are contact-detection recall, not attribution).
- **Eval tooling**: evaluate.py actions now report team_accuracy (pred team vs
  GT player_team) and player_accuracy_spatial (pred player_center → GT box →
  L-R index; the GT action player_id convention is the L-R index at the
  annotation frame — probe scored 12/14 vs 7/14 for canonical ids).
- Files: action_classifier.py, court_calibration.py (+
  midcourt_y_at_x/signed_midcourt_offset/world_dist_from_net),
  frame_processor.py, config.py (attribution_* keys),
  scripts/test_action_recognition.py (feeding fix, player_center,
  --no-team-aware), scripts/evaluate.py; tests/test_team_attribution.py (+19);
  suite 113 green.

### 2026-08-16 — server tracking fixed (open point 3) + ghost drift damped (4) + dead filter removed (6)
- **Diagnosis first** (output/diag_serve_probe.py + diag_serve_audit.py,
  git-ignored): the entreno_3 server was detected at conf 0.84–0.91 in EVERY
  frame 0–200 — the f10–175 untracked window was 100% tracker admission, NOT
  detection recall (the previous "honest detection gaps" read was wrong for
  the server). Three stacked causes: (a) bootstrap k-means forces k=4 from 3
  on-court people → a split cluster seeded a phantom 4th track (t3/t4 10px
  apart) that retired dormant at f38 and held the slot; (b) strict
  foot-in-court admission can never admit a server behind the baseline;
  (c) the dormant slot wasn't reclaimable for 60 frames (min-hold) and at f90
  a far-side walker position-restored it — wrong person.
- **Fixes**: (1) `_lock_roster_from_buffer` dedups seeds (IoU>0.35 with an
  already-locked seed) — a split cluster no longer inflates the roster;
  (2) serve-zone admission: `CourtCalibration.is_in_serve_zone` (ground-plane
  metres via the court homography; ≤3m behind a baseline, ≤1m beyond
  sidelines) is the only off-court foot that may open a NEW track (free slot
  required); serve-zone seeds start `last_in_court_frame=None` and
  `_may_feed_track` lets them re-feed out-of-court only from the zone itself
  (no gap-hijack); (3) create-loop now checks admission BEFORE eviction so an
  inadmissible detection can't burn a dormant slot; (4) `--serve-zone*` args
  in dump_player_tracks are real now. Config: `player_serve_zone_enabled/
  depth_m/side_margin_m`.
- **Measured** (dump + GT eval, output/servezone/): entreno_3 detection
  0.876→0.961, ghosts 0.114→0.064, id_consistency 0.929→0.972, team 1.00;
  GT2 (server) 50/67→65/67 @0.97, tracked from f0 with a 1:1 GT↔pred map the
  whole video. entreno_1: 0.923/0.133/0.978/0.986 — identical to fix2 (no
  regression).
- **Ghost drift (4)**: `_coast_step` damps UPWARD coast velocity
  (`coast_vertical_damping` 0.5). First attempt damped all vertical velocity
  and fragmented entreno_1 far-side ids (consistency 0.978→0.794) —
  court-axis running is image-VERTICAL. Upward-only: no regression on either
  video, jumps no longer ride up.
- **Cleanup (6)**: removed dead `CourtCalibration.filter_detections_by_play_area`
  + `is_point_in_play_area` (the detector-side bbox-overlap `detect_play_area`
  mask filter is the live path).
- **Action pipeline re-run** (entreno_3): 14 contacts, same set as before —
  the serve is still not labeled serve: its contact event fires at f76 but is
  attributed to the wrong player and labeled dig (see open point 2's new
  evidence). Server-side tracking is no longer the blocker.
- Tests: `tests/test_serve_zone.py` (+19); suite 94 green.

### 2026-08-15 — team-aware attribution attempted and reverted (findings recorded)
- Implemented ball-vertex-side candidate constraint in `_closest_player_at`
  (+5 unit tests); end-to-end run on entreno_3 showed regressions (vertex ≠
  touch position; smoothed team labels wrong near midcourt band) → reverted
  to the ghost-fix state; working tree back to `d219aae`. Everything learned
  is in open point 2, including the two signals a retry must not use.

### 2026-08-15 — action attribution: ghosts excluded from classifier (live-debug bugs triaged)
- Live-debug review of entreno_3 surfaced 3 bugs. Fixed now: `predicted`
  (ghost) players are excluded from `classify_actions` — no pose estimation on
  extrapolated boxes, no drifted bboxes in `_closest_player_at` (a ghost riding
  a jump's upward velocity had been stealing contacts).
- GT-verified effect on the reported events: dig f211 → now canonical 1 ✓
  (was the spiker), dig f563 → canonical 4 ✓. Sets f378/f488 still
  misattributed — adjacent same-line players, the true team-in-possession
  rules out the chosen player in both → parked as open point 2 (team-aware
  attribution) with this evidence. Serve f56 missed entirely (server
  untracked, open point 3). Ghost drift visuals parked (open point 4).

### 2026-08-15 — entreno_3 GT validates the bystander-hijack fix
- 67 frames × 4 players annotated (serve + entry gap and a heavy dig-and-fall
  occlusion included); occlusion flagger caught the fall window (GT3 invisible
  from ~590; GT3 then has ZERO visible-but-unmatched frames).
- Baseline (1c) vs fixed (fix2) on the same GT: detection 0.686→0.876, ghosts
  0.324→0.114, id_consistency 0.818→0.929, team 0.994→0.996. GT2: 2/67 →
  50/67 matched, 0.96 consistency — the 1c run had been tracking a frame-edge
  bystander; the fixed run's ID2 restore at f180 is the REAL player.
  Remaining GT2 misses (frames 10–170) = serve outside court + undetected
  entry: honest detection gaps, open point 3.
- Annotator usability: added [R] reset-frame, and actually wired up [B] back
  (was advertised but unimplemented).

### 2026-08-15 — bystander-hijack fix: assignment-level court membership in PlayerTracker
- **Mechanism (via GT + a new opt-in tracker audit trail**, `debug_assignments`
  param, paths: hungarian / iou_reattach / gallery_position / gallery_appearance
  / new_track**)**: far-side player undetected → track coasts/retires → an
  out-of-court bystander inherits the id (entreno_1: gallery_appearance at
  f97, hungarian at f181; 586/1635 assignments were out-of-court) → hungarian
  then feeds the bystander forever. Same bug invalidated part of the 1c
  entreno_3 numbers (ID2 ghosted, then tracked a frame-edge bystander 70+ frames).
- **Fix** (`_may_feed_track` + `last_in_court_frame`/`last_matched_frame`
  bookkeeping): an out-of-court detection may only continue a track while
  identity is OBSERVED — within `player_off_court_grace_frames` (45) of the
  last in-court sighting, or continuously matched frame-to-frame (a player who
  walked out and keeps being detected). Gallery restores (both passes) require
  a strictly in-court detection, like new-track admission.
- **Measured**: entreno_1 GT eval detection 0.651→0.923, ghost 0.352→0.133,
  id_consistency 0.974→0.978, team 0.981→0.986; GT4 matched frames 9→32.
  Audit under fix: 0/1399 out-of-court assignments. entreno_3: 0 swaps,
  ID2 dormant during the bystander window then restored IN COURT (f180) —
  the analyze_tracking "dropped frames" increase (6.3%→17.2%) there is the
  honest cost of refusing fake bystander coverage, not a regression.
- New tests `tests/test_bystander_guard.py` (8); suite 75 green.
- Throwaway diagnostics kept in git-ignored `output/diag_hijack.py` +
  `output/diag_hijack_log.json` (pre-fix audit), `output/fix1`/`fix2/` dumps.

### 2026-08-15 — first player-ID ground truth + occlusion-aware eval; found far-side bystander takeover
- Annotated 44 frames of entreno_1 (canonical IDs 1–4; GT 1/2 near side, 3/4
  far; 61 boxes redrawn/added by hand, so GT is independent of predictions).
- New tooling: `scripts/annotate_player_gt.py` (interactive, resumable,
  pre-draws tracker boxes; 1–4 assign, D drop, A add, per-frame redo via
  `--start F --end F+1 --redo`), `scripts/flag_occluded_gt.py` (geometric
  occlusion flags: smaller box ≥50% contained in another → `visible: false`;
  20 flagged), `evaluate.py` now skips invisible GT + reads `foot_team`.
  67 unit tests green (was 48).
- Eval on 1c tracks: detection 0.69 (occlusion excluded), id_consistency 0.97,
  team 0.98. Near side (GT1/2) perfect — every box matched, stable ID map
  (pred3=GT1, pred1=GT2). Far side broken by bystander takeover → Open point 2.
- Learned: phase-1 "coverage 94%" on entreno_1 was partly fake — the tracker
  was covering far-side slots with out-of-court bystanders. The
  "detection-limited" story for entrenos is really "far-side detection weak
  AND tracker papers over it with wrong people".

### 2026-08-14 — player identity phase 1 (1a+1b+1c) shipped
- **1a** two-zone filter + bootstrap-at-first-rally + hardened 4-cap; **1b**
  dormant gallery with original-ID re-acquisition and eviction-on-demand;
  **1c** ground-plane body-size + ensemble signature + appearance-based
  re-acquisition (side-change path).
- Files: `player_tracker.py`, `court_calibration.py`, `player_detector.py`,
  `frame_processor.py`, `dump_player_tracks.py`, `config.py`;
  new tests `test_player_tracker_gallery.py`, `test_court_ground_plane.py`.
- Measured: baseline vs 1a/1b/1c dumps in `output/{baseline,1a,1b,1c}/`
  (git-ignored); per-stage summaries alongside.
- Learned: the entreno drops looked "detection-limited" under position-only
  re-acquisition (1a/1b) but were appearance-bridgeable — 1c broke through the
  detection-recall ceiling. entreno drills remain useful for continuity
  validation; they just can't test side changes.

### 2026-09-27 (twenty-third session) — perf: both parked pose levers shipped in the shared path; byte-identical everywhere; live-debug decoupling parked
- **Context:** the owner asked to make BOTH offline and debug-live
  processing faster. The 2026-08-17 perf session had measured and parked
  exactly this ("pose only for near-ball players, 52→~26ms, needs an
  occlusion-window fallback first" + producer/consumer display decoupling)
  — the ask was the trigger to cash them in. Parity rule respected: both
  levers live in the SHARED `ActionClassifier.classify_actions` (batch and
  debug-lite inherit); `LiveDebugProcessor` untouched.
- **Diagnose first (`output/diag_pose_gate_probe.py`, git-ignored like all
  diag scripts):** mirrors the GT-validated script wiring; per frame it
  records ball staleness, every observed player's point-to-bbox distance to
  the live ball, and (patched `_closest_player_at`) every contact's chosen
  snapshot frame / offset / reach / distance to the ball AT THE SNAPSHOT
  FRAME and to the last-9f ball TRAIL. Findings that shaped the design:
  (a) pose 29.7 ms/f × 3.54 calls/f is the largest non-YOLO stage; (b) the
  ONLY pose consumer is `_gesture` via the chosen snapshot of an ACCEPTED
  non-reentry contact — reentry gestures return ATTACK unread (probe gotcha:
  `_closest_player_at` fires pre-reach-gate, so raw records include
  reach-rejected contacts up to 1261px — filter `reach ≤ 160`; and reentry
  f311 e6 reads trailmin 1163px but consumes NO pose); (c) every
  pose-consuming snapshot ≤ **155 px** from some ball point in the last
  NEIGH+2=9 frames (snapshot offsets measured −2..+4); (d) staleness split
  entreno 71/27/1.6% vs match slice 28/20/52% live/occlusion(≤30f)/dead.
- **Shipped (`src/recognition/action_classifier.py`, `src/utils/config.py`,
  `src/analysis/frame_processor.py`):** `pose_gate_stale_frames` (30) +
  `pose_near_ball_radius_px` (300.0), either ≤0 disables. Dead ball
  (>30f untracked): skip MediaPipe entirely. Ball live: pose only players
  within 300px of a last-9f ball point. Occlusion window (1..30f): pose
  everyone. ALWAYS append a history entry per observed player (pose=None
  when skipped) so `_closest_player_at` snapshot selection, the L-R index
  and the takeoff-stance reads are untouched. `pose_gate_stats` counters
  (posed/skipped_stale/skipped_radius) for tests + perf reports. Config
  drift test extended with both keys (suite 465→477).
- **Neutrality protocol executed in full:** fresh HEAD baselines
  (output/posegate_base_e*) → edit → A/B (output/posegate_gated_e*):
  7/7 entreno action logs **BYTE-IDENTICAL**; `evaluate --ignore-player`
  reproduces the recorded gate F1s exactly. FULL match production re-run
  (output/match20260920_posegate/): every data CSV BYTE-IDENTICAL to
  output/match20260920_e3fix (results / detailed / game_state / spikes);
  31/33 points, 57 episodes, 0-before-first unchanged; only the
  self-referential timing statistics row differs. Match probe slice: 16/16
  contacts identical incl. snapshots.
- **Measured gains:** match wall 38 → 30.5 min (84.8 → 68.0 ms/frame,
  11.79 → 14.71 fps — ×1.24); match probe slice 76.1 → 64.2 ms/f (×1.19);
  entreno script wall ~96 → 85 ms/f (×1.13, little dead time there).
- **Parked:** open point 23 (live-debug producer/consumer display
  decoupling — fps only, pipeline untouched).
- Files: src/recognition/action_classifier.py, src/utils/config.py,
  src/analysis/frame_processor.py, tests/test_pose_gate.py (+12),
  tests/test_team_attribution.py (stub gained `estimate_pose` — the gated
  loop calls per-player, not the batch wrapper), tests/test_config_drift.py,
  STATUS.md.


### 2026-09-27 (twenty-fourth session) — product north-star goals set (G1 Fantasy, G2 stats); critical paths mapped, no pipeline code

- Owner restated the product intent for the club service: (1) Fantasy-
  style scoring per point per player (Kill/Block/Ace/Dig +1, Assist
  +0.5, Error −1) over recorded sessions; (2) individual per-player
  statistics. Both now live as the North-star section at the top of
  STATUS; future prioritization traces to them.
- Mechanism-level coverage audit (recorded in the North-star section):
  Kill/Dig/Block/attack-Error already derivable from the DB; Assist is
  one join away (set → same-team kill, same point) — pure metric work;
  the real G1 blockers are the point winner/outcome layer (21.3),
  far-side serve emission (22), the per-point×player scoring module +
  web points table (14e), and attribution robustness (2/21.4/21.5).
  Ball-handling errors ruled a manual-review path, not perception.
- Product decisions ratified at session close: Assist scores **+0.5
  flat** (set → same-team kill, no direct/indirect split); **soft
  blocks score 0** (only kill blocks take the +1).
- Ranking unchanged at #1 (22 serves both goals); 21.3 promoted above
  the rest of 21's frontier. Session #20's Log entry archived verbatim
  (live Log trimmed back to 3).
### 2026-09-27 (twenty-fifth session) — PERF: open point 23 shipped (live-debug producer/consumer decoupling); byte-identical output; 8.0 → ~12 fps

- **Context:** the last parked 2026-08-17 perf lever. `--debug-live`
  serialized per displayed frame: process (68 ms at HEAD) + render +
  `waitKey(33 ms)` → ~8 fps. The parked design (producer thread runs the
  EXACT `FrameProcessor.process_frame` loop in frame order; consumer renders
  cached overlays and owns pacing) is blessed by the parity rule — the rule
  protects the pipeline path, which is untouched (`git diff`: only
  `src/analysis/live_debug_processor.py`).
- **Diagnose first (probe `output/diag_live_debug_probe.py`, git-ignored):**
  runs the real `_process_buffered_live` GUI-less (cv2 imshow/waitKey
  patched, waitKey sleeping the real 33 ms pacing; fake VideoWriter
  MD5-hashes every rendered frame) and captures the full INFO log stream.
  HEAD baselines FIRST, ×2 each on entreno_1 + entreno_3: run-to-run
  byte-identical (logs + all 441/665 frame MD5s) — the A/B ground truth is
  deterministic. HEAD live throughput: 8.06 fps on both.
- **Shipped (`src/analysis/live_debug_processor.py` only):** (1) producer
  thread `_produce_frames` — the exact shared sequence (cap.read →
  `process_frame(enable_court_redetection=True)` → ingest actions → spike
  log → overlay-data cache), flush + typed spikes on natural end only, stop
  discards the tail like the old loop, sentinel + done-event on every exit
  path; (2) the court overlay is drawn ON THE PRODUCER, right after each
  frame's processing — the consumer never reads calibration state
  mid-redetection and the compositing order (court → ball → trail → kill →
  players → counter → state) is pixel-identical (proved by the MD5s);
  `_render_frame` split into court + `_draw_overlay` (two-pass save still
  uses the full `_render_frame` — unchanged); (3) consumer (main thread —
  macOS GUI requirement) gated on queue depth > delay (same 90-frame
  label-latency guarantee as the old `len(buffer) > delay` arithmetic),
  drains after the done-event, keeps polling keys at `waitKey(1)` while
  filling/paused; (4) `_ThreadSafeLabelPlan` — lock around add/active
  (presentation-only subclass; the shared pipeline never touches it);
  (5) 'q'/'r' stop the producer via `_stop_producer` (drain-unblocks a
  producer parked on a full queue, join, then reset/rewind on 'r').
- **Two bugs caught by the probe/tests before they could ship:** (a) the
  sentinel parks at the queue's BACK, so a depth-gated consumer deadlocks
  (exit=124 on the first new-code run) — fixed with the done-event set
  strictly AFTER the sentinel is queued (event seen ⇒ everything enqueued,
  drain without the gate); regression test
  `test_sentinel_deadlock_regression_long_video`. (b) `waitKey` returns −1
  (→ 255 after `& 0xFF`), so a `key == -1` poll check never fires — replaced
  with a showed-this-pass flag.
- **Neutrality proof:** NEW code, same probe: e1 + e3 logs BYTE-IDENTICAL
  to the HEAD baselines (all action/tracker lines) AND every rendered frame
  MD5-identical (441/665). Suite 477 → **491** (+14
  tests/test_live_debug_decoupling.py: producer order/flush/sentinel,
  stop-without-flush, pause park/resume, stop-unblocks-full-queue, typed
  spikes on flush, run-to-completion order, sentinel-deadlock regression,
  quit key, restart re-runs + rewinds + resets, short-video drain, render
  split order, thread-safe plan semantics + concurrency).
- **Measured:** e1 8.06 → 11.84 fps, e3 8.06 → 12.04 fps (×1.47-1.49) with
  real 33 ms pacing; remainder of the gap to 1000/68 ≈ 14.7 fps is thread
  GIL contention (consumer render work steals producer time) — accepted,
  not worth further engineering for a debug tool.
- **Owner GUI validation still owed (cannot automate a real window):**
  SPACE pause + 'r' restart + 'q' quit on a real run; also note 'r' on the
  VFR match file inherits the pre-existing CAP_PROP_POS_FRAMES seek
  unreliability (open point 22 lesson) — unchanged old behavior, just
  remember it when restart looks misaligned there.
- Files: src/analysis/live_debug_processor.py,
  tests/test_live_debug_decoupling.py (+14; suite 491), STATUS.md. Probe
  (git-ignored): output/diag_live_debug_probe.py.


### 2026-09-27 (twenty-sixth session) — open point 22, mechanism 1: anchor-free episode→GT-point order map + far/near serve census on TRUE windows

- **Goal trace:** the map is the backbone of per-point fantasy lines
  (G1) and the pre-condition for the serve census the owner asked for at
  v3 adoption. Inputs: the posegate production run
  (`output/match20260920_posegate/`), the dictated GT
  (`ground_truth/20260920_match_points.json`, NO frame anchors), the
  mechanical serve derivations (#22). No pipeline code touched; no video
  decoded (CSV/JSON only — VFR-seek safe); no GT edits.
- **Diagnose first:** episode features extracted from
  `results_game_state.csv` + `pipeline_output.json`: 57 episodes, 18-ish
  overlapping confirmed points, 20 serve actions (all `touch_number=1`,
  15 of them emitted OUTSIDE episode spans — 5-30f before `game_on`
  fires: the late-game_on family). Expected serve letters derived
  mechanically (winner-serves × side switches): 16 near / 16 far, only 5
  far-side serves observed → the owner's complaint was already visible in
  the raw data.
- **Shipped (`scripts/map_episodes_to_points.py`, +34
  tests/test_episode_point_map.py):** monotone DP alignment over states
  (episodes consumed, points closed, LAST episode touching the open
  point) with actions open/attach/close/starve/burst. Link evidence:
  emitted-serve side match ±(60/30)f window (strong), confirmed-point
  overlap ±30f, description-implied rally size (ace/serve-fault → 1-2
  contacts, "big rally" → 4-12, else 2-6). Physics constraints, each
  installed after the production run exposed its violation: (1) attach
  only across ≤150f game_off gaps (real mid-rally splits measure 11-115f;
  before this, P24 hoarded 5 rallies across 126s and the DP burst a
  671f/13-action confirmed rally to protect tail serve alignments);
  (2) confirmed/action-rich episodes can NEVER burst (a rally is a
  point); (3) point numbers carried in the backpointer walk, never
  re-counted (a starved point shifts naive counters); (4) serve actions
  attribute to EXACTLY ONE point (nearest episode span — adjacent windows
  overlap by the ± serve margins).
- **Map result (output/episode_point_map.json, provenance recorded):** 45
  episodes → all 33 points (33 openers + 12 attaches), 12 bursts (all
  unconfirmed flickers/dead-ball handling), 0 starved points. Spot checks:
  P1=ep0 (first-confirmed ✓), P19=ep34+35 (25f flicker split), P20=ep36+37
  (serve + re-serve reading of the two A-serves), P8/P13/P15 serve letters
  match. **Census on TRUE windows: near 11/16 serve actions emitted (69%,
  11/11 side-consistent); far 4/16 clean (25%) + 2 emitted-but-mismatched
  (P4 f1396A, P23 f17159A) — far-side serve-ACTION loss ~2-3× near, both
  mismatches in far windows (consistent with the width-band side signal
  degrading far, AGENTS.md §5). P2 verdict: serve MISSING — the #22
  specimen (ball tracked, emission lost) confirmed on the full map.**
  Unattributed: f6928 (P12's serve, emitted with NO episode within ±120f
  — that rally never gathered at all).
- **Owner adjudication flags (NOT auto-fixed):** P4 "P1 fails serve"
  (description player vs winner-serves rule → B); P7/P20 double-serve
  points (re-serve vs misattribution); P23 = ep41+42 with ep42's serve
  mismatched (count-forced cascade from P26); P26 = 4 episodes/39s
  (gap+count-forced; likely a GT boundary question at P26/P27 — the
  episodes are 37/48/81f apart, contiguous play).
- **Mid-session: the owner RATIFIED serve anchors** (P1-P15 + FALSE@3650,
  verbatim in `ground_truth/20260920_match_serve_anchors.txt`): every
  serve moment with side + verdict, the winner-serves rule confirmed, and
  P1's unknown server filled (f230 far side = squad B). The map ingests
  them (`--serve-anchors`): anchored prefix (opener = first episode in
  [s-180, s+300]; attach chain ≤150f gaps, never across a serve marker;
  emission window [s-180, s+120]; boundary conflicts and false-positive
  serve candidates REPORTED) + DP tail for P16-33. The anchors exposed and
  fixed real map errors: f1396A is P3's serve (not P4's), P10's big rally
  = eps 17+18+19 (gaps 9f/20f), P11 = ep20, P12 = ep21 (the DP had burst
  it), P26/P27 split correctly once the serve-crossing rule landed. The
  owner's four misclassification verdicts REPRODUCE MECHANICALLY (P9
  spike@5496, P10 spike@6034, P11 dig@7132, P12 spike-touch@7780).
- **Probe (`scripts/probe_serve_tracking.py`):** production + raw (no
  static suppression) detectors strictly inside the 15 anchored windows,
  sequential CPU decode of the _up1080 file. VERDICT: dets present at
  EVERY serve (prod conf 0.86-0.92; the "NOT_TRACKED" P1/P2/P4/P6/P8/P14
  all covered) and the ≥8px/f bootstrap pair exists within ~±25f of every
  anchor (P2 boot@890 vs owner f900). DETECTION IS NOT THE LOSS. Real
  mechanisms: (a) serve-ACTION gate (contact before game_on arms); (b)
  bump-serve gesture misclassification (dig/spike labels AT the anchors —
  incl. the owner's four + likely P1/P2/P4/P14); (c) static suppression
  only on P15's slow float serve (raw 91 vs prod 58 frames, median motion
  2.1 px/f; P4 partial 17 frames). False-positive serves are a real class
  (owner FALSE@3650; candidates 1039A, 5130B, 10070B, 10541A).
- **Mid-session round 2: the owner adjudicated 11 contact sheets**
  (`scripts/contact_sheet.py`, raw-detector overlays + anchor/action
  marks) covering every disputed moment. Verdicts: 7 emitted serves are
  FALSE (carried ball / walking to the line / teammate ball-passing);
  P5/P7/P11/P15/P16/P17/P20 real serve moments pinned (several confirming
  that the "missing" serves sit at dig/spike-labeled actions); 4 episodes
  are OFF-GAME ball handling. The P13-P17 chain is forced by the f11050
  verdict (next server near-side → P17's ace 11410A). Anchored map
  re-run: prefix P1-P17 ratified, OFFGAME ranges force-burst episodes
  (8, 26, 28, 36), FALSE-marked serves removed globally. Final anchored
  census: near 7/16 clean + 4 misclassified (P9-P12), far 5/17 clean
  (P13, P15 + tail P27, P33) + 4 misclassified candidates (P1, P2, P4,
  P14) + 2 tail side-mismatches (P23, P31, DP-inferred). Tail caveats:
  ep45 (confirmed 1-dig at f19857, unattachable) forces P20's
  owner-confirmed serve (14516A) to burst — needs P18-P20 anchors or an
  ep45 verdict (round 3). A brute-force check of the tail DP (43.0 =
  43.0) proved the alignment optimal under the current constraints.
- **Suite:** 491 → **525** (+34; all green incl. the full suite).
  Byte-parity trivially unaffected (no `src/` changes). FLAKE OBSERVED
  (pre-existing, reproves on clean HEAD): #25's
  `test_stop_without_flush_discards_tail` failed once in a full-suite run
  (flush_calls 1 != 0 — `stop.set()` races the producer's flush) and
  passed 8/8 in isolation + on re-runs; not touched this session, needs a
  deterministic gate if it recurs.
- Files: scripts/map_episodes_to_points.py,
  scripts/probe_serve_tracking.py, ground_truth/
  20260920_match_serve_anchors.txt, tests/test_episode_point_map.py,
  output/episode_point_map.json + output/probe_serve_tracking.json
  (git-ignored), STATUS.md.

## Useful commands

```bash
# tracking quality (no GT needed) — the main iteration loop
python scripts/dump_player_tracks.py resources/video_entreno_1.mp4 --max-players 4
python scripts/analyze_tracking.py output/video_entreno_1_tracks.json --max-players 4

# full test suite (cov addopts are broken w/o pytest-cov; override them)
venv/bin/python -m pytest tests/ -o addopts=""

# full pipeline on a video
python -m src.main <video.mp4> --court calibrations/<name>.json
```

### 2026-09-28 (twenty-eighth session) — open point 22 mechanism 3 SHIPPED: pass-2 serve re-labeling; far prefix 2/8 → 8/8; all owner verdicts reproduce mechanically

- **Scope:** the layer ratified in #27 (AGENTS §6): two passes over the
  STREAM, one over the video. Pure post-hoc — inputs are the anchored
  episode→point map, the posegate pipeline JSON, and the ratified serve
  anchors; zero `src/` changes, so entreno neutrality holds by
  construction (verified: `git status` shows only the new script +
  tests).
- **Diagnose first:** evidence tables over all 33 TRUE windows before
  any code. The dead-ball gap (frames since the previous action of ANY
  kind) splits cleanly: serve-position window openers 153-1206f
  (anchored prefix 219-853f or video start); the largest NON-opening t1
  gap anywhere is 134f (P19 f13758 mid-rally possession change). GAP_
  SERVE_MIN = 143 = chasm midpoint; below-threshold openers degrade to
  report_only/anchor_only, never to a wrong serve. The contact-half
  projection is evidence-only (the known airborne bias swamps it — 16
  of 17 prefix windows read far).
- **Shipped (`scripts/relabel_serves.py`, +29
  tests/test_serve_relabel.py):** per TRUE window: live actions (owner
  FALSE/OFFGAME excluded) → opener = first live action; t1 + gap +
  adoptable action type → emitted / relabeled (bump-serve class,
  `actions_pass2` carries pass2_action/pass2_team/pass2_source beside
  the untouched original); rejected opener + anchor → anchor_only (P5,
  P7 — the owner SAW the serve, nothing was emitted); no anchor →
  report_only. Precedence learned in-build: (1) FALSE@3650 covers
  3595A+3856B via the map's adjudicated false-candidate notes, not
  exact frames; (2) owner TRACKED/MISCLASSIFIED verdicts outrank the
  gap veto (a real emitted serve can follow a false one closely) AND
  the fault-description guard (P12: desc says fault, owner says the
  serve was emitted — desc yields); (3) P32-class guard: fault desc +
  post-serve rally + no owner verdict → report_only, never forced;
  (4) P20 owner-pinned to 14516A (round-2 q5 verbatim, structured in
  OWNER_PINNED_SERVES — the DP window must not swallow the opener);
  (5) 6928A stays report-only (structural map note, no owner verdict).
- **Gates (all measured on the real data):** far prefix census
  **2/8 → 8/8** (target ≥6/8 ✓; before = P13, P15 only). Serve-typed
  actions **20 → 31** = 20 − 6 demotions (1039, 2414, 3595, 3856,
  5130 owner-FALSE; 14387 OFFGAME) + 17 re-labels (prefix: P1 dig@247,
  P2 dig@930, P4 dig@2195, P6 dig@3070, P8 dig@4801, P9 spike@5496,
  P10 spike@6034, P11 dig@7132, P12 spike@7780, P14 dig@9137; tail:
  P21, P22, P24, P25, P26, P28, P29). The ~28 sanity anchor (v2
  emitted 28) is overshot DELIBERATELY: 30/33 points now hold an
  in-stream serve action (P5, P7 anchor-only; P32 pending) — each maps
  to a distinct point, and 6928A remains in-stream un-demoted pending
  its owner verdict. **All 17 owner round-1+2 verdicts reproduce
  mechanically** (MISCLASSIFIED points land on the exact contact
  frames: 5496, 6034, 7132, 7780). **13 team overrides flagged**
  (emitted toucher team vs anchor/winner-serves): twelve A→B
  (far-side width-band degradation, incl. emitted-fixes P23 17159A and
  P31 22873A) + P24's mirror B→A — the structural squad is what the
  fantasy layer will consume; `team_emitted` kept as provenance.
- **Suite:** 525 → **554** (+29; all green incl. full suite). Tests pin
  the gap chasm, anchor precedence, FALSE/OFFGAME demotions, the
  P32/P12 fault-rule pair, the P20 pin, census scoping + gate math,
  pass2 stream annotations, determinism.
- Files: scripts/relabel_serves.py, tests/test_serve_relabel.py (+29),
  output/serve_relabel.json (git-ignored), STATUS.md.

### 2026-09-29 (thirty-eighth session) — T5 step 2: A vs B replayed through the production classes; both refuted as a recovery; B shipped default OFF; the far-side serve's real blocker is the contact probe

**What was asked:** compare mechanism A (weak-speed lock tier, as proposed in
the step-1 doc) against mechanism B (backfill on a fresh lock) in the replay
harness, implement the winner behind a config key, and gate it on
entreno e1–e7, the dev clip, the waterfall and the suite.

**How it was measured.** Both mechanisms were implemented in
`src/tracking/ball_tracker.py` behind config keys that default OFF, so the
comparison runs production code: `scripts/probe_serve_mechanisms.py` (new)
feeds the T4 `--diag-dump` raw detections back into a real `BallTracker` and
then drives the real `ActionClassifier` contact probe over the ball history the
pipeline would have received (FrameProcessor semantics: append the real
sighting, then test `c = frame − CONTACT_DELAY`). **Fidelity gate: the `base`
arm reproduces the dumped production `ball_track` state on 4968/4968 frames and
every emitted centre to 1e-6** — the arms are the pipeline's own decisions.

**A vs B (dev clip, 28 owner contacts).**

| arm | far serves with a contact candidate | candidates | outside every GT window | new bootstrap locks |
|---|---|---|---|---|
| base | 0/5 | 36 | 13 | 0 |
| A weak 3 px/f, w<30 | 0/5 | 37 (+1) | 14 (+1: f488) | **19** |
| B backfill (20 f, w<30) | 0/5 | 37 (+1) | 14 (+1: f1019) | **0** |

A confirms the step-1 estimate of ~12–19 spurious locks and buys nothing. B
creates no lock opportunity at all and is insensitive to its parameters (no
width gate / tighter radius / skip suspect / look-back 12: all identical).

**Why nothing is recovered.** B does exactly what it was built to do: the
probe's `no_ball_sighting` rejections at the far serves fall 23/27/20/21/21 →
16/20/19/20/18 of 31 window frames (18 backfill events, e.g. P1 f216 → 14
points f201–f215), and the loss moves to `no_contact_geometry`. With the full
toss in the history the far serve's contact measures (P1, c=214) `vin =
(0.8, 0.7)`, `vout = (6.5, −11.3)`, `vin6 = (0.2, 0.3)`: no bounce (the apex is
before the contact), no redirect (the toss is vertical), the drive branch
refuses because a serve keeps rising (`stays_down = False`), and the serve
branch needs a FED ascent `|vin3| ≥ |vin6| + 10` while the far toss
decelerates (margin ≈ −9.6). A hypothetical "float toss → fast rise" signature
fires on 3 frames of the whole clip with B on and 0 with B off (P1 f214/f215,
P2 f889) → at most 2/5, because for P4/P6/P8 the detector produced **no toss
sighting at all** to retro-extend. Structural limit of B itself: the probe
tests `c` at exactly `c + CONTACT_DELAY`, so P2 (lock at +10 f) is unreachable
even with a perfect chain — B's ceiling is 4/5.

**Gates (all `--device cpu`).** (1) Entreno e1–e7: action logs **byte-identical
in both arms** (8/7/14/8/6/7/6 actions); `evaluate.py --ignore-player` F1/team
unchanged (e1 .706, e2 .400, e3 1.0, e4 .933, e5 .923, e6 .933, e7 .75; teams
1.0 except e6 .857). The OFF arm is byte-identical to the T4 HEAD baseline
(`compare_runs.py` IDENTICAL on e1). The record's e2 .571 is the *action
script* path; the production path has measured .400 before and after (pre-existing
f167 gesture flip, noted in Learnings). (2) Dev clip with B on: pipeline output
**byte-identical** to OFF, `evaluate_timed --ignore-player` unchanged (F1 .597,
class .706, team .706, 1 dup, 2.703 FP/dead-min, 6/2/0 points) → serve recovery
0/5, serve FPs unchanged (the one extra replay candidate, f1019, never becomes
an action). (3) Waterfall rerun on the B-on diag dump: identical stage counts
(0/0/**6**/5/5/4/8) and identical per-contact rows except the five
`no_ball_sighting` counts; `docs/t4_loss_waterfall_dev_clip.md` gained an
"After T5 step 2" section. (4) `pytest tests/` → **736 passed** (+17 mechanism
tests, +2 drift-guard tests).

**Shipped.** ~~Mechanism B in `BallTracker` …~~ **SUPERSEDED the same day by
session 39: nothing of this reached `src/` — `src/` is back at `185c6f0` and
both mechanisms live only in `scripts/serve_mechanism_harness.py` as
default-off subclasses, so the A/B replay is still reproducible with the same
numbers.** (As implemented on this day, mechanism B was in `BallTracker`
(`backfill_lookback` and friends) + `ActionClassifier.add_ball_sightings` +
the `FrameProcessor` wiring (`update(..., frame_number=)`,
`pop_backfill()`), all **DEFAULT OFF** (`ball_backfill_lookback = 0`), causal
(past frames only) and on the shared frame path, so live-debug parity is
untouched. Mechanism A (`weak_min_speed`/`weak_max_width`) shipped
off-by-default, documented as refuted, so the A/B stayed reproducible.
Config-drift guard extended.)

**Owner hand-off:** the far-side serve needs (a) a contact-probe serve
signature that does not require a fed ascent and (b) detection evidence on the
far toss. Both are recognition/detection mechanisms, outside the approved T5
scope — decision needed before code.


---

### 2026-09-30 (forty-fourth session) — G3 plan S1 far-side serve looming probe: diagnose only; REFUTED at kill 2 (`src/` untouched)

**Asked:** execute the owner-approved G3 plan S1 (STATUS #42, Active next):
a diagnose-only far-side serve LOOMING probe, with pre-registered kill
criteria, no `src/` change. Chosen over S0b because S0 is owner-only and S0b's
expected result (far serves 0/5 at contact level) was already hand-measured;
S1 is the first concrete far-serve perception mechanism and unblocks the
S3/S4 pass-2 layers that wait on real serve contacts.

**Mechanism measured (spec frozen by #42, not tuned).** After the contact the
far serve flies toward the fixed long-axis camera, so its apparent bbox width
grows; the pre-contact toss is absent at ~3/5 dev far serves (T5). In the
new-rally state (no emitted contact within `RALLY_RESET_GAP=90`), a ball
SEGMENT is a run of production-tracked sightings merged across gaps ≤
`ball_max_missing` (10 f, the identity horizon); its ONSET is the first
tracked frame and must be far-band (width ≤26 px, below the 26–35 abstain
band); `L` = OLS slope of `ln(width)` vs time in SECONDS over
`[onset, onset+0.5 s]`. Dev/e1–e7 use the dumped production `ball_track`;
the match dump is replayed through the production `BallTracker` (imported from
`scripts/probe_serve_mechanisms.py`, never re-implemented) with a hard parity
stop. Secondary feature `nearest far-team player is_behind_baseline at onset`
declared before any held-out look, reported only, never fit.

**Result.** Kill 1 (far flight detected?): **passes at the boundary** — 4/5
far serves have ≥5 far-band tracked sightings in `[c, c+0.5 s]` (f210 7,
f2154 10, f3038 9, f4770 9; f880 only 3). Kill 2 (does `L` separate?):
**FIRES** — lowest far-serve `L` **0.338** (P4 f2159) vs highest new-rally
non-serve `L` **0.945** (dead-time throw-back f1673, width 26; also f4581
0.495, f3390 0.364), so `L*` is undefined and no threshold admits all five
without false fires. Robust to the segment-merge choice: maxgap 0/2/5/10 all
overlap (non-serve max 1.29/1.18/1.18/0.945). Kill 3 (entreno neutrality)
vacuous (`L*` undefined); census only (e1/e2/e4/e6/e7 have 1 far-band
new-rally segment each). Kill 4 (match P9–P33) **pending owner S0** — the
match replay is exact (0 locked / 0 centre mismatches over 26068 frames; 55
far-band new-rally segments). **Verdict: the far-serve looming lever is
REFUTED at diagnosis** — same class as T5 and R1; no threshold was tuned on
the 5 dev points.

**Deliberately NOT done.** No kill-1 detector-mining branch (kill 1 passed);
no `src/` mechanism band (S2 is owner-gated and not triggered); the
`behind_baseline` secondary was not used to move `L*`. The far-serve CONTACT
(open point 22) stays open; the next lever (targeted far-flight detector
mining vs another contact-proposal mechanism) is an owner call.

**Artifacts.** `scripts/probe_far_serve_looming.py` (+29 pure-mechanism
tests), `docs/g3_far_serve_looming.md`, `output/s1/far_serve_looming.json`
(git-ignored). T4 base anchors re-confirmed: `output/t4/dev_timed.json`
contact P 0.586 / R 0.607 / F1 0.597 and `dev_waterfall.json` stage
`3_candidate` = 6 (the committed T4 baseline; no src change to re-measure).
Suite **811** (782 + 29).


---

### 2026-10-01 (forty-seventh session) — G0 DONE: the whole-match contact GT (P1–P33, 211 contacts) is machine-readable (`src/` untouched)

**Asked:** execute G0 from *Active next*: extend `parse_contact_gt`
(`scripts/build_dev_clip_gt.py`) with the owner's dialect B (P9–P33) and emit
a match-level GT JSON for P1–P33 on the match frame axis plus a per-point
contact sheet, with the P1–P8 rebuild as the regression anchor.

**Delivered.**
- `scripts/build_dev_clip_gt.py`: dialect-B grammar (NT/FT, frame-first form,
  player id after the frame, `-> overpass` / `overpasses` relabels, bare
  frames, wrapped parentheticals, the duplicated empty `Point 21`,
  prose-vs-contact discrimination), `_join_continuations`, parenthetical-
  protected note extraction, the owner's blanket overpass rule
  (`OVERPASS_CONVENTION`), `poke` / `rainbow` -> soft spike, `hard` -> hard
  spike, spike-out wording, and `_side_to_team` now uses switch PARITY.
- `scripts/build_match_contact_gt.py` (new): `build_match_gt` (pure; identity
  clip<->match map + the shared `contact_events` translation), a sequential
  contact-sheet renderer + markdown index, `--no-sheets` mode.
- `ground_truth/20260920_match_contacts.json`: 33 points, **211 owner
  contacts** (28 P1–P8 + 183 P9–P33), every event `source=owner_gt` with
  `frame == match_frame` and coarse `frame_tolerance=15`.
  `output/match_contact_sheet/` has 33 PNG grids + README.
- `ground_truth/README.md`: dialect B documented as parsed (shapes +
  mechanical transcription rules + the match GT section).

**Gates (all met).**
- P1–P8 rebuild: parsed contacts equal the committed dev GT
  `owner_contacts` FIELD-for-FIELD; the only difference is physical
  `raw_line_no` (+3 — the owner appended header lines after that GT was
  built). Pinned by `test_dialect_b_regression_p1_p8_unchanged`.
- Every contact line lands in `events` (211 = 211 contacts);
  `test_owner_file_lines_are_all_accounted_for` balances every logical line of
  the txt against headers + switches + contacts + notes + unparsed (3 preamble
  lines only).
- 4 `Side switch` flags stay after P7/14/21/28; owner parentheticals survive
  verbatim as `owner_note`.
- No `src/` change; suite **852** (+12 tests: 7 in
  `tests/test_build_dev_clip_gt.py`, 5 in `tests/test_match_contact_gt.py`).

**Findings worth remembering (now Learnings / README).**
- The team mapping needed switch PARITY: the old `switch_after` "last marker"
  formula labels `near` as Team B for P15–P21 and P29–P33; with 4
  switches `near` is Team A again from P29. Dialect A's P1–P8 output is
  unchanged.
- `poke` = soft attack -> `spike` + `spike_type="touch"`; `bump set` = set;
  `bump pass(es) (the) ball` = overpass; `returns` (serve reception) = dig.
- `"... missatributed to P2, but its P4"` gives the TRUE player P4 (not the
  wrong id named before it); the correction stays verbatim in the note.
- P15 f10180 (`FT is close to a dig ...`) is PROSE, never a contact (open
  point 25); P20 f14518's note wraps across two physical lines; P30 f23545 is
  a touch with no owner action label -> `action=null` +
  `owner_action_unspecified=true` (contact scoring is class-agnostic, so it
  still counts; class accuracy must skip it).

**Next:** G1 — the first held-out contact score on P9–P33 (perception +
`actions_pass2` arms) with `score_pass2_contacts.py`'s scope discipline, point
windows from the episode map (the match GT's `match_start_frame/end_frame` are
episode-map PREDICTIONS, flagged), then the G2 far-serve lever decision on real
labels. Owner-side: capture-spec doc rewrite (point 29).


**Previous (forty-seventh session — **G0 DONE: the whole
20260920 match contact GT (P1–P33, 211 contacts) is machine-readable.** The
owner's second line dialect is parsed by `parse_contact_gt`, and
`scripts/build_match_contact_gt.py` emits
`ground_truth/20260920_match_contacts.json` (211 events, all
`source=owner_gt`, MATCH frame axis) plus 33 per-point contact sheets. Gates
met: the 8 P1–P8 points rebuild FIELD-identical to the committed dev GT (only
physical `raw_line_no` shifts +3 — the owner added header lines later); every
one of the 211 contact lines lands in `events`; the 4 `Side switch` flags
stay after P7/14/21/28; parentheticals survive verbatim as `owner_note`.
Found and fixed en route: team mapping must be switch PARITY — after the 4
switches P29–P33 `near` is Team A again (the old last-switch formula
mislabelled P15–P21 and P29–P33). No `src/` change; suite **852** (+12 tests).
**Next = G1: the first held-out contact score on P9–P33** → G2 far-serve
lever on real labels.)


**Previous (forty-seventh session — **G0 DONE: the whole
20260920 match contact GT (P1–P33, 211 contacts) is machine-readable.** The
owner's second line dialect is parsed by `parse_contact_gt`, and
`scripts/build_match_contact_gt.py` emits
`ground_truth/20260920_match_contacts.json` (211 events, all
`source=owner_gt`, MATCH frame axis) plus 33 per-point contact sheets. Gates
met: the 8 P1–P8 points rebuild FIELD-identical to the committed dev GT (only
physical `raw_line_no` shifts +3 — the owner added header lines later); every
one of the 211 contact lines lands in `events`; the 4 `Side switch` flags
stay after P7/14/21/28; parentheticals survive verbatim as `owner_note`.
Found and fixed en route: team mapping must be switch PARITY — after the 4
switches P29–P33 `near` is Team A again (the old last-switch formula
mislabelled P15–P21 and P29–P33). No `src/` change; suite **852** (+12 tests).
**Next = G1: the first held-out contact score on P9–P33** → G2 far-serve
lever on real labels.)


---

### 2026-10-01 (forty-eighth session) — G1 DONE: first HELD-OUT contact score on P9–P33; far serves 0/12; labels (not proposal) dominate the loss (`src/` untouched)

**Asked:** execute G1 from *Active next*: score the perception stream (and
`actions_pass2`) at contact level on the held-out match points P9–P33 with
`score_pass2_contacts.py`'s scope discipline, and re-rank the dev loss budget
against held-out reality.

**Delivered.** `scripts/score_heldout_contacts.py` (+20 tests,
`tests/test_heldout_contacts.py`) + `docs/g3_heldout_p9_p33.md`; artifacts
`output/heldout_contacts/{gt_p9_p33.json,pred_perception.json,pred_pass2.json,g1.json}`.
No `src/` change, no video decode. The script reuses the tested S0b helpers
(arm construction, `evaluate_timed` matcher, serve-nearest table) and adds a
SCOPED-GT writer so P1–P8 events can never be charged as false negatives, a
contact-level miss taxonomy, and a per-side/per-class recall split.

**Headline.** Region f5240–f26147 (padded span of the P9–P33 emission
windows; covers all 183 owner contacts, no P1–P8 contact), effective tolerance
±15 f at 25.67 fps. Production **P 0.785 / R 0.760 / F1 0.772**, class
**0.590**, team **0.518** (38 FP / 44 FN / 2 dup). Pass-2 F1 0.774, class
0.561, team 0.561 — again flat on contact and negative on class.

**The re-rank (the point of G1).** Held-out contact DETECTION is BETTER than
the dev clip (F1 0.772 vs 0.597), while class/team are similar or worse. The
miss taxonomy over 183 contacts: **46 correct / 57 wrong-label / 36 wrong-team
/ 44 missed**. Normalized vs the T4 dev waterfall (39% proposal / 18% team /
14% label), the held-out loss is 24% missed / 20% team / **31% label** — the
dev budget over-weighted proposal and under-weighted the gesture label. The
single largest held-out error class is the LABEL, and `overpass` is never
emitted correctly (recall 0.000 over 18 contacts; 13 found, all dig/spike/set).
Only 3/44 missed contacts have no action within ±80 f; 41 have one 7–69 f away.

**Far serves 0/12, reproduced on independent contacts.** 8/12 have a nearby
emitted "serve": 6 are the GT reception the pass-2 layer re-labelled
(+26…+34 f), 2 are production serves 26–28 f late with the opposite team; 4
have nothing within ±80 f. Near serves 11/13; all serves 11/25 (serve recall
0.280 — the far serve is the whole serve-recall hole). This is S0b's dev
finding confirmed on 12 held-out contacts, and it closes the last excuse for
leaving the far-serve contact open.

**Honesty notes.** The episode-map emission windows are predictions and only
12/25 cover their own owner contact range, so the contact P/R/F1 is
window-independent but the dead-time/points metrics inherit the drift (flagged
in the doc). The stage waterfall is NOT reproduced: the only full-match diag
dump is the R1 `bw=0.3` run, whose gate decisions differ from production, so
the script records `waterfall.available = false` rather than faking stage
counts; a production diag dump is a follow-up decode. `--autonomous` is not
used (the pass-2 stream carries owner anchors); the GT-derived-input audit is
recorded.

**Suite:** **872** (852 + 20). No `src/` change (`git diff 185c6f0 -- src/`
empty).

**Next:** G2 — the owner decision on the far-serve lever, now decidable on
data with baseline F1 0.772 / far-serve 0/12; the G1 data also makes the
gesture-label bucket (`overpass` 0/18) a first-class candidate for the next
mechanism. The deferred production diag dump would give the stage waterfall.

### 2026-10-01 (forty-ninth session) — S3 DONE: pass-2 side-switch/squad layer; G1's raw team 0.518 corrected to 0.755 (`src/` untouched)

**Asked:** continue with the next point that moves the needle for G3. G2
(far-serve lever) is an owner decision, S2 is owner-gated and S1 refuted, so
the next unblocked worker item was **S3 — the pass-2 side-switch/squad layer
(open point 21.4)**.

**Delivered.** `scripts/resolve_side_switches.py` + 25 tests
(`tests/test_side_switches.py`) + `docs/g3_side_switch_layer.md`; no `src/`
change, no video decode. The layer derives the beach switch cadence (change
ends after every 7 points) from the POINT ORDER alone, maps each court-side
letter to a squad letter by switch parity, and augments every `actions_pass2`
entry with `pass2_squad` (+ `pass2_point`) for downstream fantasy/stat
consumption. Output `output/side_switches.json`; report
`logs/side_switch_report.md`.

**The needle (a measurement confound found en route).** The perception stack
speaks COURT-SIDE letters (A=near, B=far, `CourtCalibration.get_team`) while
the owner/GT convention is SQUAD letters — so G1's recorded raw `team 0.518`
is side-vs-squad, NOT a side-attribution failure. On the same 139 found
contacts, mapping side→squad lifts team to **105/139 = 0.755** (identical to
`pred side vs owner side`, what the stack actually emits), leaving **34
genuine side errors** (clustered P10/P15/P18/P19/P22/P24–P26/P29–P30 — the
near/far width-band attribution class). The T4 dev "5 stage-5 team errors, all
P8" are the same confound at the first switch point.

**Gates.** Derived switches `[7,14,21,28]` are an EXACT match to the owner
`side_switch_after_point` (validate-only read); P9 f5496 (owner near/squad B)
is the parity anchor test; 207/207 actions annotated.

**Cross-check honest result.** The player-crossing cross-check (from the R1
match diag dump, whose player tracking is independent of the ball departure
gate) gives only **3/4 cadence switches with support AND 16/28 non-switch
boundaries also supported** — it cannot place switches because tracker ids hop
(open point 2). It is therefore EVIDENCE ONLY and explicitly NOT used; a
position-based detector waits on stable identity GT.

**Suite:** **897** (872 + 25). No `src/` change (`git diff 185c6f0 -- src/`
empty).

**Next:** S4 (consume `pass2_squad`; the winner layer's side→squad mapping can
now use this schedule instead of GT) and/or the G2 owner decision on the
far-serve lever (baseline F1 0.772 / far-serve 0/12); the label bucket
(`overpass` 0/18) remains the largest held-out perception loss.

### 2026-10-02 (fifty-third session) — the far serve SOLVED as evidence: 14/17 at ZERO false positives; the VFR seek defect found

**Asked:** "so far what we tried to get the far serves did not work. What can we
do to reliably get serves" — then, to the three proposed checks (M2 opener gate
~15 min, M1 magnified far-ROI probe, M3 structural proposer): "check all in the
order you stated". No `src/` change; the action stream is untouched.

**Three verdicts.**

**M2 — the opener gate: a strict win.** A serve opens a rally, so a
`serve_candidate` should only count when no contact was emitted in the preceding
N frames. Measured seek-free on the 17 GT far serves vs 24 mid-rally controls:
no gate = 11/17 hits and 8/24 FPs (precision 0.579, recall 0.647); gate 30 = 4
FPs; **gate 60 → 240 = 0 FPs at unchanged 11/17 (precision 1.000)**. Every
control FP sits at a 2-58 f gap and every hit at 231-816 f, so the plateau is
60-240 f wide — consistent with the session-28 measurement that openers follow
>=153 f of dead time while the largest mid-rally gap is 134 f, and therefore
neither a fitted threshold nor an MPS/CPU-jitter artefact. `GAME_OFF` gives
identical numbers.

**M1 — the magnified far-end pass: refuted, and it corrects the record.** The
match is natively 720p, upscaled, and the ball detector runs at imgsz 1280, so
a 14-28 px far ball is 9-19 px inside YOLO; running the same production weights
on a 4x-magnified square crop of the far band (3 x 320 px, tile geometry from
the 8 calibration clicks) should have recovered the "missing" detections.
`scripts/probe_far_roi_ball.py`, one sequential pass over all 41 windows:
**0 of 17 windows were empty for the full-frame arm** — the detector sees a
15-21 px ball in 14-31 of 31 frames at every serve, P31 f24543 excepted (2/31,
which the tiles lift to 26/31 at +105 ms/frame for 3 tiles). The tiled arm's
median detection is 3.2 px of unscaled sand/line noise, because a magnified far
band is mostly ground. **So the "the far ball is seen on 0-1 frames in 8/17
windows" line repeated across STATUS and the G4 docs is a TRACKER count, not a
detector count** — the detector was never the far-serve problem, which moves the
blocker to the lock + the label, exactly where #51's geometry diagnosis said it
was. Parked as a possible P31-class fallback; not built.

**M3' — the structural proposer: the frontier, and the answer.** Rule over the
RAW detections (no tracker, no shape test): *no emitted contact for 60-240 f* +
*a person in the far band* + *a far-side ball-sized 8-60 px detection within
30 f* + *the ball within R bbox heights of that person*. Swept 648 ways offline
from one recording (`scripts/sweep_structural_serve.py`): runway-only at reach
1.5-4.0 = **11/17 with 0 FP**; runway+court at reach 1.0 = **15/17 with 1 owner
FP**; at reach 2.5 = **17/17 with 2**. Median |offset| **1 f** (the G4
conjunction's is -9 f). The two zero-FP rules miss *different* windows, so their
**union is 14/17 with no false positive at all** against 24 mid-rally contacts
and the 9 owner FALSE/OFFGAME moments. The two residual FPs (f5130 "ball
handling after the point ended", f2414 "walking to the serve line with the ball
in hands") are pre-serve handlings: no dead-time test separates them from a
serve, only the toss does, and the toss is the one signature the far-end
geometry refuses — which is also why this is EVIDENCE (post-hoc, AGENTS.md §6)
and never a label source (S0b broke 3 correct dig labels).

**The measurement defect.** To score any of this I had to decode the match
without seeks, and that exposed a defect in the existing numbers: on this VFR
file (25.67 fps in a 30.12 container) `CAP_PROP_POS_FRAMES` lands **-28..+30
frames** from the requested index (13 probe points, mean +8.5, measured against
a full sequential decode). Every windowed G4 probe seeks, so the recorded
"6/17 far serves, 4/24 FPs, precision 0.60" was computed on shifted windows:
seek-free it is **11/17 with 8/24 FPs**, and the candidate offsets are
systematically **-9 f** (the same sign as the mean seek error). Two seek-free
probes replace them, `tests/test_vfr_seek_guard.py` (3 tests, AST-based so a
docstring mention is not an offence, exceptions allow-listed with reasons and
failing when stale) greps `scripts/`, `src/` and `tests/` — and its audit turned
up two real defects outside the serve work: `scripts/annotate_player_gt.py` can
show the OWNER a frame up to ~30 f from the requested one (a GT contact could be
judged off its own moment; it wants a sequential-cursor fix before the next
annotation pass) and `src/db/ingest.py` crops review-UI player thumbnails with
the same seek (cosmetic). Both recorded as allow-list KNOWN ISSUES, not fixed
here.

**Also corrected:** the G4 doc's "a far ball is detected on ~1 frame in 4" was
already known to be a COCO-detector artefact; the honest figure is a median gap
of 1 frame, i.e. nearly every frame.

**Not done, deliberately:** no `src/` change, no label emitted, no player
identity (the server is a raw detection, not one of the 4 tracks), near side
untouched by construction. The recommendation to the owner is the 14/17 union
consumed post-hoc; the 17/17 point is available at 0.90 but its errors are
systematic (pre-serve handlings), not random.

Artifacts: `output/g4/serve_events_seq_recording.json` (the recording the sweep
replays, so future rules cost no decode), `output/g4/{serve_events_seq,
far_roi_ball,structural_serve_sweep,seek_offsets}.json`; docs
`docs/g4_structural_serve.md`, `docs/g4_far_ball_presence.md`,
`docs/g4_far_serve_alignment.md`; tests `tests/test_structural_serve_rule.py`
(13), `tests/test_vfr_seek_guard.py` (3). Suite **1008**.

**Next:** the owner picks the operating point (recommend 14/17) and S4 consumes
the evidence post-hoc for who-served / aces / serve faults; the label bucket
(`overpass` 0/18) is still the largest held-out perception loss; the
owner-GT-annotator seek wants a fix before the next annotation pass.

### 2026-10-02 (fifty-fourth session) — S4 DONE: the serve evidence is a real artifact, and it needs two numbers

**Asked:** "do recommendation" — build the approved operating point (the 14/17
union of the gated conjunction and the structural arm, consumed post-hoc).

**Shipped.** `ServeContactProposer` in `src/analysis/serve_events.py` (inside the
`--serve-events` envelope, 5 `serve_structural_*` config keys, drift-guard clean,
12 unit tests): a runway occupant + a ball-SIZED (8-60 px) far-side detection
within 1.5 bbox heights, WITHOUT the `far_flight` requirement, one candidate per
run, the contact at the run's last frame. `scripts/consume_serve_evidence.py`
(pass 2) reads `pipeline_output.json` + the point map and writes
`output/serve_evidence.json` — 87 records, 21 with both arms agreeing, 19/33
points bound, plus a `validation` block and a `disclaimer`. It touches nothing
else: no `events`, no CSV, no DB (AGENTS.md §6, the S0b lesson).

**The production artifact is a real run**, not a probe: `src.main` over the
match with `--serve-events`, 26 061 frames, 33 min on MPS, serve events
runway 395 / far flight 578 / conjunction 443 / structural 60.

**Inertness is measured, not asserted.** `scripts/probe_serve_events_inertness.py`
decodes one span sequentially into two processors (emitters off, then on) on CPU:
actions OFF 1 / ON 1, **byte-identical**, no `serve_events` key with them off,
20 events with them on. The observers add a key and nothing else.

**The honest result is two numbers, and the doc leads with the difference.**

| measure | value |
|---|---|
| evidence coverage (anchored on the GT contact) | **14/17** GT far serves |
| the consumer's own binding (no GT, as shipped) | **9/17** (dev **5/5**, held-out **4/12**) |
| owner FALSE/OFFGAME false positives | **1** (f5121 "ball handling after the point ended") -> precision **0.90** |
| points with a serve record | 19/33 (7 of them in points the map calls near-served, which this layer cannot observe — reported, never consumed) |

This is the G1 shape again: the signal is there, the interpretation is the loss.
Reporting only 14/17 would be the mistake the whole G1 exercise exists to
prevent, so both numbers are in `docs/g4_serve_evidence.md` and in the artifact's
`validation` block.

**Two implementation findings worth keeping.** (1) Binding by **dead-time
episode** rather than by the pass-2 point window removed a whole failure class:
the first version scored 8/17 and four of its misses were serves that fall
outside their own predicted window (the episode map's windows are PREDICTIONS,
12/25 cover their own contact range). The emitted contacts are not predictions
and already partition the video, so binding through them is both cheaper and
more faithful. (2) The selector is ONE constant — the record closest to the
reception that is at least `min_next_gap = 20` frames from it, which drops the
post-contact echo (the ball still inside the server's bbox a few frames after
the hit) and the walk to the serve line. The sweep ships in the artifact and is
flat over 15-20 f (9/17 at both), so the constant is not balanced on a knife
edge.

**The five binding misses, diagnosed.** P14 / P22 / P23 have **no record at all**
near the serve (closest 117 f, 187 f, nothing) — an evidence gap, not a binding
gap. P28 and P31 have a second record 8-19 f from the contact (P31: 24535 and
24648 for a 24543 serve) and nothing in the emitted stream says which side of the
contact the ball is on. **The missing ingredient is already measured and unused:
the net crossing** — a served ball crosses the calibrated net line toward the
camera, and the 578 `far_flight` events carry the width growth that precedes it.
That is a post-hoc computation over the existing artifact (no re-decode) and it
is the next session's lever.

Artifacts: `output/serve_evidence.json`,
`output/20260920_match_ari_joan_lost/pipeline_output.json`; docs
`docs/g4_serve_evidence.md`; tests `tests/test_serve_evidence_consumer.py` (25).
Suite **1036**.

**Next:** the net-crossing selector, then S4's ace / serve-fault derivation off
the 19/33 points that already carry a record. The label bucket (`overpass` 0/18)
is still the largest held-out perception loss, and the owner-GT-annotator seek
that `tests/test_vfr_seek_guard.py` flagged still wants a sequential-cursor fix.

### 2026-10-02 (fifty-fifth session): serve-reliability plan; the far-serve track is a proxy (planning only)

**Asked:** "So far what we have tried to see if we can get serves reliably has
failed… come up with a plan to make serve be detected reliably… if you think we
are going in the wrong direction also state it explicitly." Low-credit session.
Only AGENTS.md and STATUS.md were read directly. One read-only fact probe ran in a
sub-agent (no decode, no repo change).

**Facts the probe established:**
- Every video has real audio, and nothing uses it.
- Production serves at contact level: near 8/16, far 0/17, 12 FP.
- `docs/g3_heldout_p9_p33.md`'s near 11/13 is production OR pass-2. Production
  alone is 7/13.
- Entreno near serves: 4/5.
- The serve-evidence consumer is far-only by design.
- Far server bboxes are 90-160 px, and pose already runs on them. No serve branch
  uses pose.
- Unlabeled footage: vall_dhebron (695 s, calibrated, never run) and a 55-min
  05-05-2025 session that includes matches (uncalibrated).

**Verdict, stated explicitly: yes, the direction was wrong in five ways.**
1. We chased a proxy: a ±15 f far contact in the causal action stream, instead of
   a per-point serve record.
2. We fit everything on the 17 far serves of one match. The 14/17 is in-sample;
   held-out binding is 4/12.
3. The near side, the easy one, is a coin flip and has no plan.
4. Audio and the beach serving rules were never used.
5. The headlines over-claimed ("SOLVED AS EVIDENCE").

What stays right: the §6 causal/post-hoc split, the opener gate, the structural
and runway evidence as proposals, and evidence-not-labels until validated.

**Plan:** `docs/serve_reliability_plan.md`, tasks SR0-SR7 with pre-registered
kills and acceptance criteria. They are tracked as open point **30**, which
supersedes 22's framing.

**Housekeeping:** STATUS was 1885 lines against the lean convention. The #48-#54
header chain and the #54 "Where we are" block moved verbatim to
`docs/history/status_where_we_are_archive.md`. Log #50-#52 moved verbatim to
`docs/history/status_log_archive.md`. Nothing was deleted.

**Next:** SR0 (worker). In parallel, the owner does SR3 (serve-only GT on two new
sessions) and answers D3.

### 2026-10-02 (fifty-sixth session) — SR0 DONE: one serve scorer, and the record corrected

**Asked:** "read agents, start with the next task" — the next task being SR0, the
first task of the serve-reliability plan: one scorer, per side, dev vs held-out.
Scorer only: no decode, no `src/` change, no label emitted (AGENTS.md §6).

**Shipped.** `scripts/score_serves.py` (+33 tests, `tests/test_serve_scorer.py`),
`docs/sr0_serve_scorer.md`, artifact `output/serves/sr0.json`. Sessions are
declared, not discovered, so a stream can never be silently swapped; each stream
declares what it SPEAKS (court side / squad / time only), whether it CLAIMS a
serve per candidate, and whether it is point-bound. Five measurement rules, each
of which prevented a wrong number from being printed:

- one matching rule for everything (greedy one-to-one, nearest first, inside each
  owner contact's own `frame_tolerance`), side-correct by default;
- **side accuracy is scored on the POSITIONAL match** — under side-aware matching
  it is tautologically 1.00;
- **a proposal is not a claim**: the raw evidence records and the rally onset
  report no precision at all ("74 false serves" and "precision 1.000" were both
  one line away);
- **coverage ≠ binding**: `point_bound` reproduces what a consumer claims, and it
  is the whole 13-vs-9 gap;
- **side ≠ squad**: pass-2's side read is the emitted letter, never its
  winner-serves-derived squad (which is flagged GT-derived), and a squad is
  compared through the switch parity imported from `resolve_side_switches`.

**Gate PASSES** exactly as pre-registered: production near **8/16**, far **0/17**,
12 false emissions. The script exits non-zero if those move.

**The record, corrected twice.** The shipped far-serve evidence covers **13/17**
far serves, not 14 — 14 records land within ±15 f of a serve of any side and the
fourteenth is on a **near** serve (P12 f7777, record f7762); 14/17 was a sweep
figure on the recording, not a property of the shipped artifact. And scored as the
claim it is, the consumer's precision is **0.47** (19 bound records, 9 on their
own serve), while its zero-FP property (1 FP on 24 mid-rally controls + 9 owner
FALSE/OFFGAME moments) remains exactly as true as before. Both are printed.

**Three findings that steer SR4.**
1. **Far-side serve TIME is nearly free.** The `game_on` backdated burst start —
   already computed, zero extra work — lands within ±15 f of **11/17** far
   serves at median |offset| **3 f** (range −6…+6), against **3/16** near at 14 f
   (all late). At ±120 f it covers 27/33. A far serve IS the rally onset; a near
   serve is not, because the onset there belongs to the reception. So SR4's
   proposal step must be **per side**: a side vote on a known time far side, a
   real proposer near side.
2. **The near misses are not timing.** Every near serve production emits is
   within **±2 f** of the owner frame (8/8, median 1 f), so the 8 missing near
   match serves are missing *emissions*. SR1 is unblocked and cheap.
3. **The 12 false emissions are mostly dead time**: 8 handlings with no owner
   contact within 80 f, 3 rally contacts with the wrong label (f3856 a `set`,
   f8534 and f10070 `dig`s) and 1 serve 25 f late. The toss sub-probe in SR4 is
   worth spending on the 8, not the 3.

**A stale-artifact defect found while scoring the other sessions.** The seven
`output/video_entreno_*/pipeline_output.json` files date from 2026-09-04/06
(commits `239490c` / `8150694`) — before the v3 ball detector (09-26) and the pose
gates (09-27) — so their 3/5 is not the current production number and the plan's
4/5 came from a run whose artifacts are gone. The scorer prints each stream's
`processed_at` + commit so this cannot be read as current; re-running the seven
short clips is queued with the SR3 worker half.

**Housekeeping:** STATUS's *Where we are* rewritten on the SR0 numbers; open point
30's SR0 marked done with its findings folded into SR1/SR4; seven Learnings added
(one per durable fact); session index extended; Log entry #53 moved VERBATIM to
`docs/history/status_log_archive.md`. Suite **1069** (1036 + 33).

**Next:** SR1 (near-serve miss taxonomy) or SR2 (audio onsets), one mechanism per
session. Owner: SR3 on vall_dhebron.

### 2026-10-02 (fifty-seventh session) — SR1 DONE: the near serve is lost at the LABEL, and 5 of 6 misses are one condition

**Asked:** "Start with SR1" — the near-serve miss taxonomy. Diagnose-only by the
plan's own wording, and that held: **no mechanism designed, no `src/` file
touched**. `scripts/probe_near_serve_misses.py` (+21 tests),
`docs/sr1_near_serve_misses.md`, artifacts `output/serves/sr1.json`.

**Two decodes, both necessary and both cheap.** (1) All seven
`video_entreno_*` clips re-run under **production config with `--diag-dump`**,
which closed SR0's outstanding action: those `output/video_entreno_*` artifacts
are from 2026-09-04/06, before the v3 detector and the pose gates. (2) One
**sequential** pass over the match prefix [0, 4000] (MPS, 14.0 fps, 285 s) for the
two `no_contact` cases, which are early in the file. It **passed the
prefix-parity gate — 23/23 `(frame, action, team)` triples identical to the
shipped artifact** — so its dump is a production pass, not a probe. No seek
anywhere (AGENTS.md §9).

**The taxonomy (10 missed near serves: match 8, practice 2).**

| bucket | n | what it is |
|---|---|---|
| `label` | **6** | a same-side contact AT the serve frame, emitted as `dig`/`spike` |
| `no_contact` | **3** | no same-side contact; the contact died earlier in the chain |
| `other_side_contact` | 1 | the only nearby contact is on the OTHER half (P24) |

**The label bucket is one mechanism.** `ActionContextResolver._decide` emits
SERVE only when `behind_baseline AND rally_start`; anything else is DIG (bump
gesture) or SPIKE (attack gesture). So the probe splits the two conditions:
**5 of 6 fail on `behind_baseline`** with `rally_start` certainly true (gaps of
204–478 f to the previous contact) — the contact is detected, attributed to a
player and opens the rally; it is simply not judged behind the baseline, and e2
f32's dump measures that field directly (`"behind_baseline": false`,
`"near_net": true` at a serve contact). The 6th is a **cascade of our own
emission**: at P33 the pipeline emits a serve **25 f early** (f25782), which
counts as a contact and suppresses `rally_start` 16 f later, so the real serve
at f25798 reads as a `dig`. One bad emission costs a correct label.

**The `no_contact` bucket splits into two different stages.** P5 f2575 and
P7 f3747 both die at **stage 4, the reach gate**: the ball is tracked, the
geometry fires (a `bounce` at f2572, `drive`s at f3749-51) and the candidate is
refused at 448.3 px and 204.0 px against a 140 px reach, with all four tracked
boxes elsewhere on court. That is the reach-gate family the non-serve backlog
already carries (open point 7), now measured for the serve. e5 f20 dies one
stage earlier: `no_ball_sighting` × 15 of 31 window frames.

**What this corrects.**
- SR0's inference needed one step: the 8 match near misses are missing **serve**
  emissions, but **6 of the 10 have the contact right there in the stream**. The
  near side is a LABEL problem, not a perception one — the ball was tracked in
  all 10 and a contact candidate existed in 9.
- **Practice serves are 3/5, not the plan's 4/5.** Fresh runs hit e3 f29 (+0),
  e6 f35 (+1), e7 f25 (+0) and miss e2 f32, e5 f20. The stale artifacts also
  gave 3/5 but a *different* set (e6 missed, e5 hit) — the coincidence is not
  evidence the recorded number was right.
- **"No diagnostic records in the window" is not "no detection in the window."**
  The first version of the probe reported six phantom `1_raw_detection` stages
  for match rows past the prefix dump; `diag_stage` now checks the dump's
  coverage and returns nothing outside it.

**Near-side serve recall is 11/21 = 0.52** on current production artifacts.

**Housekeeping:** `score_serves.py` now prefers a fresh practice run over the
stale one; STATUS's *Where we are*, open point 30 (SR1 done, its findings folded
into SR4's task) and the Learnings updated with five new facts; session index
extended; Log #54 moved VERBATIM to `docs/history/status_log_archive.md`. Suite
**1090**.

**Next:** SR2 (audio onsets), or the SR4 design decision SR1 makes answerable —
a side + rally-opening test for the serve record that does not read the emitted
label. One open sub-question, cheap to close: was the server detected but
untracked at P5/P7 (one more prefix pass with `--serve-events`)?

### 2026-10-02 (fifty-eighth session) — SR1b: SR0/SR1 reviewed; the near serve has three measured causes; task cards for cheap executors

**Asked:** review the serve plan plus SR0/SR1 ("are we going in the right
direction?"), explore through the cheap-model runner; then write it up, correct
STATUS, commit the vall_dhebron GT, and create a prompt + skill so that smaller
LLMs pick up the next STATUS task without inferring work.

**Verdict on direction:** the strategy holds (D3 per-point record, one scorer,
held-out discipline, far stop list). SR1's cause analysis did not: 4 of its 5
`behind_baseline` verdicts were inferred (`behind_baseline_measured: null`), and
"not a tracking problem" checked the ball only.

**Measured (worker, read-only; `docs/sr1b_worker_report.md`):** one sequential
production pass over the match [0, 15000] with `--diag-dump` (MPS, parity
**111/111**), the SR1 entreno dumps, and a config-only counterfactual [0, 8000]
with `player_off_court_hold_frames = 100000`:
- P9-P12: server track FED, contact emitted, `rally_start` true;
  `behind_baseline` false because the toucher's CONTACT-frame foot is 0.8-24.5 px
  inside 761 px (6-12 px past it 7 f later). Hits P3/P16-P20 at 809-835.
- P5/P7: the server track goes `predicted` exactly 91 f after its last in-court
  sighting (hold = 90) and coasts frozen through the serve → reach gate.
  Counterfactual: P7 hit; P5 → `dig` (rally_start killed by a handling 78 f
  earlier); P9-P12 identical to the decimal; 53 → 55 actions, one non-GT flip.
- e2: server never tracked (sideline bystander in the 4th slot). e5: ball.
- Far P1-P20: far server track FED at 7/8, ball track `none` at 7/8.

**Written:** `docs/sr1b_near_serve_causes.md` (review), `docs/sr1b_worker_report.md`
(verbatim worker report), correction banner on `docs/sr1_near_serve_misses.md`;
STATUS: header, *Where we are* (cause table, held-out lock, SR2 demoted), new
**Next task cards** section (SR1c, SR1d READY; D4 owner gate), open point 30
(SR1b/SR1c/SR1d, SR3, D4), Learnings (+6, 2 SR1 lines flagged), session index;
Log #55 moved verbatim to `docs/history/status_log_archive.md` and header #55 to
`docs/history/status_where_we_are_archive.md`. Committed
`ground_truth/20290928_entreno_vall_dhebron_serve_anchors.json` (owner SR3, 19
serves). Harness: `.pi/prompts/next-task.md` (executor contract) and
`.pi/skills/task-card/SKILL.md` (how planners write cards); AGENTS.md §10.

**Nothing in `src/` changed.** Suite unchanged (1091).

**Next:** card SR1c, then SR1d (one decode at a time), then owner gate D4.

### 2026-10-02 (fifty-ninth session) — live debug: readable frame counter + a signal/event side panel

**Asked** (two changes, both HUD-only): the frame counter is hard to read, and
live debug needs a side panel showing which events fire on which frame and what
the signals were (ball px width first), so "something is very wrong" is visible
at plain sight.

**1. Frame counter.** `overlay.draw_frame_counter` now paints a SOLID black
plate (8 px padding, drawn first) instead of relying on a thin black text
underlay, and the scale is 0.55 → **0.60** (+1 px cap height). Pinned by
`tests/test_overlay_frame_counter.py` (plate black in all four corners/padding,
frame outside untouched, and the scale delta so it cannot silently revert).
Same helper the standalone action script draws with, so both entry points stay
aligned.

**2. Side panel** (`src/analysis/debug_panel.py`, display-only, `p` toggles it):
a 600 px strip composited to the RIGHT of the annotated frame by the live
consumer, built from a per-frame snapshot the PRODUCER takes right after
`process_frame` (`LiveDebugProcessor._signals`), so the render thread never
touches tracker/classifier state. Body text scale **0.55** (owner follow-up:
+3 px over 0.40), row height 20 px, rows clipped to the strip by MEASURED width
so a dense signal row degrades to `~` instead of running off the edge. It
prints, per frame:
- **BALL** — pos, bbox size in px, the classifier's OWN width-side read
  (`_width_side`: `A (near)` / `B (far)` / `-` abstain, with vote count), speed
  px/f, detection confidence, real vs `PREDICTED`, frames since the last real
  sighting. **A dropped track HOLDS the last sighting** (owner follow-up: the
  block used to vanish and the row became unreadable mid-rally): pos / size /
  width-side / speed / conf stay on screen, with the flag riding ON the section
  header (`-- BALL -- NOT TRACKED (last f147, 8f ago)`, no extra row — the held
  block has exactly as many rows as the tracked one) and `track HELD stale Nf`
  on the track row, so the last known signal is visible while the tracker is
  blind. Predicted coasting points still update it (flagged `PREDICTED`), player
  distances keep measuring against the held point (dimmed + `[ball not tracked]`
  on the section header), and the hold is cleared on restart;
- **PLAYERS** — `P<id> team net/ghost` + point-to-BBOX distance to the ball,
  coloured by whether it is inside `CONTACT_REACH` (the exact value the reach
  gate used);
- **GAME** — the on/off badge value + point count;
- **CONTACT PROBE / LOOK-AHEAD** — what `_detect_contact` did at `t-7` this
  frame (`found drive d=41px/140px`) or WHICH GATE refused it (`refused: reach`),
  plus the contact the classifier is currently holding back for the one-contact
  look-ahead;
- **EVENTS** — every emitted action and every resolved spike outcome, keyed on
  the action's **TRUE contact frame** (`EventPlan`, thread-safe, producer writes
  / consumer reads) and marked `>>` on that frame. The second row carries the
  signals that produced the label: `gesture/kind net= behind= bbl= src= w=<ball
  px width at the contact>`.

**Invariants kept.** No processing-path change: the producer runs the same
call sequence (a test pins it), the panel only reads values the frame already
produced (no duplicated thresholds — `CONTACT_REACH`/`NEAR_NET_PX` are read off
the classifier class, the width verdict is its own method), and every read is
guarded so a stubbed processor renders "-" instead of raising. The probe mirror
reuses `ActionClassifier._diag` (the `diag_dump` writer's own inert record) and
is **skipped when a `DiagRecorder` owns those records**, so live debug can never
steal entries from a dump. Display only: `writer.write()` still gets the
unpanelled frame, `--save-video` and the two-pass path are untouched, and the
window asks for `WINDOW_NORMAL` (an autosized window wider than the screen
clips its RIGHT edge, which is exactly where the panel lives).

**Verified:** two real live runs of `video_entreno_3.mp4` with the actual
pipeline (GUI patched, CPU). Run 1 (420 frames): 420/420 shown at 2350 px
composed, events landing on their contact frames (f29 serve, f74 dig, f130 set,
f177 spike with its `out → dug` resolution steps, f212 dig). Run 2 (240 frames,
after the follow-up): **30 held frames / 14 never-seen** — e.g. at f155 the
ball was last seen at f147 (pos 1164,11, 27x23 px, conf 0.21, i.e. gone off the
top of the frame) and the panel kept all of it, flagged. Suite **1155** (+40
total: `tests/test_debug_panel.py` 34, `tests/test_overlay_frame_counter.py` 5,
3 panel/wiring cases in `tests/test_live_debug_decoupling.py`).

**Note for the next session:** an event whose emission lag exceeds the 3 s
display delay cannot appear on its contact frame (same limitation the player
labels have); the measured lags stay inside it, but that is what to check if an
event ever seems to be missing from the panel. The panel is drawn at 1:1 in the
composed frame and OpenCV then scales that into the window (requested
`min(composed, 1900)`), so the on-screen glyphs are ~0.75 of the composed size
— the window is `WINDOW_NORMAL`, so dragging it bigger is a free legibility
knob.


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


### 2026-10-02 (sixty-fourth session) — PM1 DONE (`FAIL=blocked`): the far-serve signal is COMPLETE (16/17) and no binding rule makes it precise (294 false serves unbound) — the point map is the lever, and open point 22 inherits the constraint

**Asked:** continue the coordinator loop toward G3 (owner, verbatim: "Continue"
after telling me not to use gemini/sonnet/opus and to pass briefs as files).

**Step 0 (read).** STATUS *Active next* ranked PM1 (the point-map probe, carded by me
at the end of #63) first. Ran it the way the owner prescribed: a **197-byte pointer**
prompt telling the child to read its card out of STATUS.md, on
`stealth/space-bunny-alpha` (route #2; the GLM subagent tier is quota-blocked until
2026-10-03 per the coordinator prompt).

**Step 4 (verify, own commands).** Suite **1214** = 1191 + 23 new, green.
`git diff` shows the four STATUS edits the card listed and nothing else; no `src/`,
no `ground_truth/`, no decode, no seek, held-out session never read. `grep` confirms
the probe imports no `cv2` and opens no capture (the §9 seek guard). I corrected one
defect the worker left: it rewrote the STATUS prose to the verdict but never flipped
the card's own `status:` line off READY (the same defect as #62+).

**Result (both gates green, pre-registered FAIL fires).**
- **G1** reproduced: near 8/16, far 0/17, 12 false serves.
- **G2** reproduced: `far_flight.width_start` **16-27 px** at every far serve vs
  **39-50 px** at the 3 near serves that have an event; every cut in 26/28/30/32
  claims **16/17 far, 0/16 near**.
- The bypass test: **unbound (frame, side) = 16/17 far hits with 294 false serves**
  (bar: >= 15/17 AND 0 new false serves). Binding rules: in-window 10/17 (253 FP),
  first-start-after 16/17 (288 FP), inter-point gap 11/17 (35 FP) — bar was >= 12/17
  with <= 3 FP. **FAIL** on both halves; SR4-FAR is **BLOCKED on open point 22**.
- #63's root cause re-derived and sharpened: 31 pipeline points vs 33 GT points
  (P32/P33 have none); under the only workable pairing the opener offset is
  **one-signed +6 … +3153 f on all 31 pairs** (uniformly late, not noisy); **far 2/17**
  serves sit inside any window vs **near 14/16**; 29/30 inter-point gaps clear
  `GAP_SERVE_MIN` 143, so the chasm rule selects nothing. [inferred] `_finalize_group`
  opens a point on a pre-serve flight burst, backdated after a quiet interval — the
  point layer never sees a serve.

**Decisions.** SR4-FAR is not the next card; the point map is. I wrote the constraint
into open point 22 (move the opener to the serve or the rally it heads) and demoted
SR4-FAR in *Active next* item 3 (it contradicted item 1 before the fix). SR4-NEAR
stays parked on perception. Nothing shipped; a refutation that pins the blocker is a
success of the session.

**Hygiene:** the sixtieth-session Log entry was archived VERBATIM to
`docs/history/status_log_archive.md` (Log back to 3 entries), per the Lean-STATUS
convention. New pins: 23 tests in `tests/test_point_map.py` (mechanical + the literal
#63/#64 counts + the verdict truth table).

**Not done (deliberate):** no card for the point-map fix yet — it is a `src/`
mechanism design, which is tier-2 (architect) work by the coordinator prompt's Step
3.5, and it needs an owner decision on whether the point map may change at all.

**Asked:** continue the coordinator loop toward G3 — reliably track actions across
videos, target >70% of actions correct against the match ground truth without the
practice drills dropping below 90%.

**Step 0 (read).** STATUS *Active next* ranked SR4 (the per-point serve record) as
the needle-mover; nothing was carded for it. SR4a had just landed (see the #62+
entry) and its G2 verdicts said the near side was repairable after the fact and the
tracking exemption should reopen as an architect call only.

**Step 1 (rank).** Serve reliability is the active defect (near 8/16, far 0/17,
12 false emissions; held-out contacts F1 0.772). NOT worth doing now, per STATUS:
the audio-onset probe (timing is not the bottleneck — the far TIME is already
nearly free at 11/17 within +-15 f), the beach-rules serve-sequence decoding
(needs SR4's records first), and the stale off-court-hold comment (comment-only,
deferred into a session that touches `src/` anyway).

**Step 3.5 (escalate).** SR4 has no card and its design hinges on an unverified
premise — that a serve can be located post-hoc — so it went to the architect
(route 4) with the SR4a evidence attached. **The first three attempts died on a
harness bug, not on the model:** `cat .pi/prompts/architect.md /tmp/brief.md >
full.md` (the documented route-4 recipe) makes a ~15 KB prompt, and a delegated
prompt over ~1 KB kills the child `pi` with `Killed: 9` / `EXIT 137` and zero
output, on every model, at every THINK level, independent of agent directory. Found
by bisection (800 B survives, 1000 B dies, neutral filler text dies at the same
size, 3+ repeats each). The owner's recollection was right: the brief must be a
file the child reads. Re-run as a 451-byte pointer, and the architect ran 24 min
and returned a **refutation**. Log: `logs/architect_sr4_ds_run.log`. (A later
attempt with opus returned an OpenRouter billing error instead — 128k max_tokens
against the remaining credit — so the architect tier also needs credit or a
`max_tokens` cap. Recorded as a Learning.)

**Step 4 (verify, own commands).** Re-ran the architect's own two probe scripts and
the ceiling claim from committed artifacts, all reproduce:
- Near coverage ceiling **13/16**: only 13 of the 16 ground-truth near serves have
  ANY action on the serving side within +-15 f; P5 f2575 nearest -81 f (`overpass`
  A), P7 f3747 nearest -108 f (`dig` A), P24 f18135 nearest +29 f (`dig` B). The
  planned 15/16 bar is above the ceiling, so SR4-NEAR is not buildable as planned.
- Far side signal (new, not in the brief): ball width at flight onset **14-23 px at
  all 17 far serves** vs **39-52 px** at the 3 near serves that have a flight event
  (13 of 16 have none within +-15 f); a cut anywhere in the **26-32 px plateau**
  claims **far 16/17, near 0/16 misclaimed**.
- Binding kills it: **0 of 17 far serves fall inside their own point window**.
  `game_state.points` has **31** entries vs 33 GT points and each point's
  `start_frame` sits **1-1466 f AFTER its own serve** (the session-56 backdated
  onset). In-window binding: far 9-11/17 with 2-8 false records; leading-gap
  binding: 5-7/33 side-correct with 22-25 false; unscoped: 432 narrow candidates for
  33 serves; suppression by next-action distance N=15/30/60/120 gives far hits
  16/8/2/0 with 329/256/183/141 false. Every lever trades true serves for false
  ones ~1-for-1. **Root cause = the point map, not the signal.**

**Verdict:** architect refutation ACCEPTED, and extended with the root cause. No
`src/` change, no decode, held-out session untouched, full suite green (1191).
Written up in `docs/sr4_architect_call.md` (new file).

**Decisions:** SR4-NEAR parked on perception (its ceiling is 13/16 and M-b fixes
P5/P7 at best, not P24); SR4-FAR demoted to a detection-only result until the point
map is fixed or bypassed; the +-15 f tolerance stays (admitting P33's -25 f would
also admit the far false serve f8534 at +16 f); wrong-label repairs do not violate
the STOP list because a serve record never mutates `actions_pass2`. **Next is the
point-map probe** — post-hoc, no `src/`, decides bypass vs open point 22 — and it
needs a card written before an executor can run it.

**Not done this session (deliberate):** no task card for the point-map probe yet
(the card-writing is a planning act; the owner asked for results), and the owner
gate on the near bar (lower it to 13/16, or make it explicitly contingent on M-b) is
left for the owner because it changes an acceptance criterion in open point 30.
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

**SR4a (delegated step).** The card ran later the same day, in a worker session, with
no `src/` change and no decode: `scripts/probe_near_openings.py` (imports
`score_serves` and `relabel_serves`, contains no `cv2`), `docs/sr4a_near_openings.md`,
`logs/sr4a_report.md`, `tests/test_near_openings.py` (+35; suite **1191**). **G1 was
run before a single bucket was read and passed on both arms** (near 8/16, far 0/17,
12 false serves, drills e2-e7 3/5). The 8 match near misses bucket into
**2 `emitted_mislabeled_opener` + 3 `emitted_not_opener` + 3 `not_emitted`**;
**G2 verdict 1: SR4's near side proceeds after the fact, 5 repairable of 8** (rule
>= 4); **G2 verdict 2: M-b is REOPENED as a fresh architect call only, not a build —
3 never produced, 2 of them coasting** (P5 f2575, P7 f3747; rules >= 3 AND >= 2),
with the caveat that `output/sr1c/match_full_diag.jsonl` has **no recorded arm**, so
the reopen must re-run with the arm named. Trap guard **0** of 17. Two things the
next card must inherit: only **4 of the 8 hits** have a `serve` as their window
opener, and **6 of the 12 false serves** sit inside a near-miss window, so an
opener-keyed SR4 record is not yet safe. One card deviation is disclosed in the doc:
the card's window rule leaves the clip-opening serve undefined (4 of 5 drills, P1),
and the probe follows `relabel_serves.resolve_point` (video start is an anchor)
because the literal reading scores the drills 0/5 and fails G1.


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

### 2026-10-02 (sixty-ninth session) — THE TOUCH-COUNT LEVER (#68): the label bucket is Layer 2's possession count, not Layer 1's gesture — and the far serve is the SMALLEST lever on the goal metric

**Asked:** continue the coordinator loop toward G3 (the user's standing "Continue", m00266,
with gemini/sonnet banned, opus only for `/architect`, briefs passed as files).

**Step 0 (read).** Re-read STATUS *Active next* + *Open points* + the re-ranked cards,
AGENTS.md, `.pi/prompts/coordinator-prompt.md`. All 7 existing cards were DONE — no READY
card remained — so the first job was to decide what the next card should be, not to run one.

**Step 1 (the hypothesis I wanted to test, and refuted).** After PG2 passed and #48's
"41 of 44 missed contacts have a nearby action 7-69 f away" plus 8 far serves 26-34 f late,
the natural story was that emissions are systematically LATE. Measured the signed delta to
the nearest emission by GT class on committed artifacts: dig median **-2 f**, set **-2 f**,
spike **-2 f**, overpass **-2 f**, serve **+23 f**. **A global timing fix pays nothing.**
The recorded class accuracy reproduces exactly (83/141 = 0.589).

**Step 2 (the find).** Dumped the match `--diag-dump` (`output/g3r1/match_bw03_diag.jsonl`,
185 `accepted` candidates) and found **Layer 1 is degenerate**: the whole match emits only
three `VisualGesture` values, with `bump_set` at **157 of 185 (85 %)**. `bump_set` becomes
dig 73 / set 40 / spike 24 / serve 16 / overpass 4. So the entire `dig`/`set`/`overpass`/
`serve` decision is **Layer 2's `ActionContextResolver._decide`**, keyed on `_poss_touch`.
That reclassifies the "label bucket" from a perception problem to a Layer 2 rule problem.

**Step 3 (the lever, verified by replay).** Replayed the **unmodified** `_decide` over the
accepted contacts, substituting one input at a time. Feeding the **real GT `touch_number`**
lifts label accuracy **79/139 = 0.568 -> 110/139 = 0.791 (+0.223)**, while `touch_number`
itself is only **96/139 = 0.691**. That is bigger than every other lever measured on this GT
(12 far serves +0.032 class / +0.066 total-correct; 13 overpass labels +0.071; the 14
`set<->dig` swaps +0.077). Residual confusions after a perfect count: `overpass->spike` 10,
`serve->dig` 9, `serve->spike` 3, `overpass->dig` 3, `spike->block` 2, `spike->set` 1,
`set->overpass` 1 — the count is necessary, not sufficient.

**Mechanism, first cut.** Touch errors concentrate where the pipeline emitted FEWER contacts
than the owner listed: 11 GT points with `accepted >= GT` -> 11/37 touch errors; 14 points
with `accepted < GT` -> **32/102**. Worst: P19 18/13 (7), P25 18/12 (6), P26 11/8 (6),
P30 18/15 (5), P23 7/6 (4), P29 6/7 (4), P33 4/5 (3). P18 (16 GT / 15 accepted) and
P24 (7/6) are CLEAN, so it is the placement of the missing contact, not the count itself.

**Trap.** The GT `touch_number` lives in `points[].events[].touch_number`, **not** in
`points[].contacts[]`. Reading `contacts` (which has `action`, `gesture`, `team`, ... but no
touch key) silently returns 0/139 while the code runs fine — it produced a wrong answer
mid-session before it was caught. Anyone re-running this must read `events`.

**What did NOT happen.** No `src/` change, no decode, no seek, no GT edit, no pipeline run,
held-out session `20260928_entreno_vall_dhebron` never read. No rule proposed and nothing
shipped (STOP list / AGENTS.md §5 discipline: this is in-sample on the same 139 contacts).

**Step 5.** Wrote `docs/g3_touch_count_lever.md` (the full argument, plus the two limits:
the GT touch number encodes the OWNER's segmentation, and the +0.223 is an upper bound on a
rule fix, not a result), `logs/touch_lever_stdout.txt` (the reproducible transcript), **CARD
TC1** (READY, first card) and the re-ranked *Active next*.

**Owner decision needed (recorded, not acted on):** the far-serve track (open point 30 /
22) is now measurably the SMALLEST lever on the goal metric, so the label work goes first.
That does not cancel the owner's serve priority — it re-orders it — so it is written up here
rather than assumed.

### 2026-10-02 (seventy-first session) — CARD TC1 DONE: `TOUCH_COUNT_LEVER_REFUTED/0.6187` — the count is not re-derivable, the fix is UPSTREAM (emit the missing contacts); the reach-gate bucket is the measured upstream cause, and the tier-2 architect call proposes a POSE-ANCHORED reach

**Asked:** continue the coordinator loop toward G3 (standing "Continue", m00266).

**Step 0.** CARD TC1 re-issued in #70 with a baseline-independent gate (a gain over the
R0 replay control, so which stream is quoted cannot move the verdict), delegated on
`stealth/space-bunny-alpha THINK=high` via a **202-byte pointer** `/tmp/tc1_run.md`
(`EXIT 0`, ~17 min, log buffered until exit).

**Step 4 (verify, own commands).** `probe_touch_rules.py` imports the UNMODIFIED
`ActionContextResolver` and the existing matchers, opens no capture, imports no `cv2`
(`grep` clean); `git status` shows no `src/` change. Suite **1327** = 1286 + 41, green.
G1 reproduction matched #68 exactly (I re-ran each figure myself: 185 accepted; 157
`bump_set` / 16 `attack` / 12 `block`; 139 found; touch 96/139; R0 79/139; GT-touch
110/139; serve median +23 f; 85/139 and 83/141 shipped). Worker again left the card's
`status:` line at READY; I set it to DONE (#71).

**Result — the pre-registered FAIL fires, and step 2 is the real deliverable.** Chosen
rule R4 (dev+entreno summed F1 5.745 vs R0 5.577) scored **86/139 = 0.6187 = +0.050**
over R0 (bars +0.132 PASS / +0.082 PARTIAL) at touch accuracy 103/139 = 0.741;
non-serve 86/127 = 0.677 vs R0 0.622 and the GT-touch arm 0.866 — so a perfect count is
worth +0.244 and the best re-derived count +0.055. **The 43 wrong-touch found contacts
are STARVED, not mis-reset**: `under_counted` 20 + `previous_contact_missing` 13 = **33
of 43 (77 %)**, `team_change_not_reset` 5, `over_counted` 4, `attack_not_reset` 1.
The fix is therefore **upstream — emit the missing contacts** (open points 2/5), not
better counting. Three card defects reported and NOT reinterpreted into the verdict:
(ii) is unsatisfiable by any offline replay (the R0 replay is off-record on 4 of 7 drills);
**R2 is a no-op by construction** (the card keeps the resolver's own `attack_before` reset
in every arm, which IS R2, so R2 ≡ R1 — pinned by a test); G1's timing/0.589 references
only reproduce on the production stream over ALL region events.

**Step 5 (the coordinator's own follow-up, because step 2 named the fix but not its
cause).** Diagnosed the upstream recall loss on the same committed artifacts
(`docs/g3_reach_gate_bucket.md`): **44 of 183 held-out GT contacts have no accepted
contact within ±15 f** (median nearest 33 f), and every one has a rejected row within
15 f. Base-rate-normalised against frame coverage, two reasons are enriched and
`reach` is the actionable one: **`reach` 71 rejections / 4.65 % coverage → 20 observed
misses vs 2.05 expected = 9.78×**; `no_contact_geometry` blocks 43 of 44 but is the
residual bucket (1.76×); `no_ball_sighting` is exactly at chance (0.99×) and
`min_contact_gap` is DEPLETED (0.42×). Every rejected row carries its own
`distance`/`reach`, so the gate re-scores offline: **1.2× admits 14/14 (prec 1.00),
1.3× 21/19 (0.90), 2.0× 48/32 (0.67)**; of the 20 reach-carrying misses, **2 are
within 1.05×, 6 within 1.2×, 9 within 1.3×, 16 within 2.0×, and 24 of the 44 have no
candidate geometry at all.** **But two hard caveats stop it shipping:** (a) the
match's OWN dev split (P≤8, cut f4910) admits **12-15 candidates carrying ZERO GT
contacts at every threshold**, so the match cannot select the gate — in-sample only;
(b) at the best frame-precision gate (1.2×) only **6 of 14** carry the correct
`target_team`, and across all 71 rejections `target_team` is **B 64 / A 6** — so this
recall comes with wrong-team contacts. It is a **recall lever worth ~+0.08
total-correct and ~0.00 class-accuracy**, not the label fix.

**Deliverables / state.** `docs/tc1_touch_rules.md`, `scripts/probe_touch_rules.py`,
`tests/test_touch_rules.py` (+41), `docs/g3_reach_gate_bucket.md` (new, coordinator),
`docs/g3_touch_count_lever.md` §3 corrected. No `src/` change, no decode, no seek, no
GT edit, held-out session untouched. Suite **1327**.

**Next.** The reach relaxation is a px constant on GT-validated action logic and is
venue-coupled (206 px vs 464-479 px court depth, AGENTS.md §7) **and is not
selectable out of sample** — so it needs a real A/B run (a `src/` change ⇒ architect
tier) or it does not ship. The cheapest decisive step is a **real A/B run of the
reach arm**, scored on the match AND all 7 drills, because only a run can tell what an
admitted candidate resolves to (the dump has no `contact_point` on rejected rows).

**Tier-2 architect call DONE (same session).** Delegated on a 531-byte pointer to
`/tmp/reach_brief.md`; memo saved verbatim as `docs/reach_gate_architect_call.md`.
Verdict: **do NOT widen the 140 px scalar** (venue-coupled; +0.08 total-correct
ceiling; admits 6 false contacts on the drills at 2.0×). Instead **replace the
ball-to-box reach with a POSE-ANCHORED reach**: accept when the ball is within the
140 px box OR within `0.5 × bbox_width_px` of a confident wrist keypoint
(MediaPipe 15/16), fall back to the box-only test when pose is absent/stale, guard
with a new class constant `CONTACT_HAND_REACH = False` (no new `Config` key, so
the config-drift guard is untouched). Rationale: a touched ball is always beside
the hand regardless of apparent size, so the test is scale-free and it directly
targets the recorded airborne-toucher failure (open point 7, e2 f167).
**Coordinator verified the memo's load-bearing claim by grep:** `CONTACT_REACH =
140.0` (`src/recognition/action_classifier.py:53`) and `SERVE_REACH_PX = 160.0`
(line 158) are CLASS attributes read as `self.` (lines 416, 419), and the
`_player_pose_history` snapshot carries the full pose dict (lines 378-383) with
wrist indices 15/16 (`src/recognition/pose_estimator.py:55`). **Scope of that
finding — corrected after checking the construction site: only the SCALAR arm is
measurable with no `src/` change** (monkeypatch `ActionClassifier.CONTACT_REACH`,
T5 precedent `scripts/departure_gate_harness.py`). **The architect's POSE-ANCHORED
branch is new logic inside `_closest_player_at`, so that arm needs either (a) a
`src/` change, or (b) a `ProbeClassifier(ActionClassifier)` subclass in `scripts/`
overriding `_closest_player_at`, injected by patching the symbol
`FrameProcessor` reads at `src/analysis/frame_processor.py:210`** — T5 kept its
subclass out of `src/` the same way, though T5 drove the classifier directly
rather than through `FrameProcessor`, so (b) is a new harness shape. Either way
the SHIP needs owner ratification of the mechanism. Pre-registered A/B gates in the memo: **PASS** = ≥ +5 recovered
correct held-out contacts (≥ +0.03 contact F1), no drill F1 drop > 0.02 vs control,
no new control-window false actions, AND admitted-row team precision > 0.43;
**FAIL** = F1 gain < +0.02, OR any drill F1 drop > 0.05, OR team precision ≤ 0.43.
Neutrality provable on e3/e6 (ZERO reach rejections → arm B byte-identical);
harness MUST `cv2.setRNGSeed(0)` per `PlayerTracker` (AGENTS.md §3).

**Owner gate (left for the owner, not resolved unilaterally):** the pose-anchored
reach is a change to GT-validated action logic, so the coordinator surfaced the
mechanism for ratification rather than shipping it. Two honest caveats recorded in
the memo: the whole lever is ~+0.08 total-correct and ~0.00 class accuracy (so if
the priority is the 0.70 class-accuracy half of G3, this is NOT the path), and the
0.5× bbox-width hand radius is inferred, not measured.

### 2026-10-02 (seventieth session) — #68's headline baseline was WRONG and a cheap executor caught it: the shipped stream is 0.612, not 0.568 (replay artifact); CARD TC1 re-issued with a baseline-independent gate

**Asked:** continue the coordinator loop toward G3 (standing "Continue", m00266).

**Step 0.** #68 was committed (`1c03447`) with CARD TC1 (READY, first card) and its
executor delegated on `stealth/space-bunny-alpha` via a **217-byte pointer** to
`/tmp/tc1_run.md` (`EXIT 0`, 5 min). Per the card's own step 1 it had to reproduce #68
before touching anything, and it **stopped and reported instead of proceeding** — exactly
the behaviour the card is designed to force.

**What it reported, and it was right.** Its step-1 reproduction gave **85/139 = 0.611**
for the label control where the card said **79/139 = 0.568**, and it noticed the replay
cannot reproduce the shipped stream: the `accepted` rows of
`output/g3r1/match_bw03_diag.jsonl` carry **no `behind_baseline` field** (0 of 185), while
`src/recognition/action_context.py:167` reads it for the serve branch. It also flagged that
my residual-confusion table was quoted from the *post-substitution* arm while it read the
*as-emitted* arm — two different measurements. It created nothing, made no STATUS edits and
issued no `touch_rule_gate` token.

**Verify (my own commands, all four arms).** `ARM A` the dump's own `action` field vs GT =
**85/139**; `ARM B` replay `_decide(behind_baseline=False, own_side_drive_block=False)`
as-emitted touch = **79/139**; `ARM C` same replay with the real GT `touch_number` =
**110/139**; `ARM D` the 207-action `pipeline_output.json` = **83/141 = 0.589** (the
recorded 0.590). Replay fidelity to the dumped `action` = **168/185**. Split by serve:
**non-serve 127 -> emitted 78 (0.614) / replay 79 (0.622) / replay+GT-touch 110 (0.866)**;
**serve 12 -> emitted 7 (0.583) / replay 0 (0.000) / replay+GT-touch 0 (0.000)**.

**Verdict.** My #68 "as emitted (the real pipeline) 79 = 0.568" row is **wrong** — 0.568 is
a replay artifact of the missing `behind_baseline`, and the serves are unreachable in any
offline replay. The **touch-count lever is untouched** (96/139 touch as-emitted and 110/139
under substitution both reproduce exactly); only the label figure it was quoted against was
mislabeled, and on the subset a replay can faithfully model the lever is **larger**, not
smaller (**+0.244** on the 127 non-serve). I also re-measured the lever comparison table,
which had two more of my own quoted numbers wrong: all 25 region serves +0.177 (near serves
are where the serve lever lives), the 13 overpass labels **+0.092** (I wrote 0.071), the 15
`set↔dig` swaps **+0.106** (I wrote 0.077), and the 12 far serves **+0.032** class /
+0.066 total-correct.

**Repairs.** `docs/g3_touch_count_lever.md` §3 rewritten (corrected table, an explicit
CORRECTION note, a second note that `own_side_drive_block` is also unrecoverable, and the
corrected lever table); CARD TC1's G1 now expects the replay control explicitly and carries
a REQUIRED CAVEAT telling the executor not to re-investigate the missing flag; TC1's
pre-registered gate is restated as a **gain over the R0 replay control** (PASS >= 0.700 =
+0.132, PARTIAL >= 0.650, FAIL below) so the verdict cannot turn on which baseline is
quoted, plus a report-only arm on the faithful 127; open point 9 and the #68 index line
carry the correction. Nothing in `src/` changed, no decode, no seek, no GT edit, held-out
session untouched. Suite **1286 passed**.

**Lesson (durable).** A replay arm is not a baseline until its fidelity to the shipped
stream is measured, and a diag dump that omits one `_decide` input makes that fidelity
unachievable for a whole class of contacts. Quote the shipped stream's own score, and state
every gate as a delta over the arm the tooling can actually produce.

### 2026-10-03 (seventy-third session) — live-debug ball-candidate overlay LANDED (`b` toggle); the prior session's FALSE commit claim caught and repaired; #72's ritual completed

**Asked (owner):** continue what the previous sessions left unfinished, then continue
the coordinator loop toward G3.

**Found in the tree (verified, not trusted).** Two threads, neither committed:
(a) #72's STATUS ritual was half-done — Last updated + open point 0z rewritten,
sixty-ninth Log entry archived verbatim, but NO session-index line, NO Log entry,
and NO commit; `docs/g3_reach_cascade.md` sat untracked.
(b) A complete display-only live-debug feature (73rd-session work, session
`2026-10-03T06-59-26`): every ball the detector saw this frame as a hollow box with
its confidence and the detector's own verdict — `sus` = stationary suspect (kept,
distrusted), `rm` = dropped by static suppression (tracker never saw it) — toggle
`b`, default ON, cached on the producer thread like every other panel signal. Its
final message claimed "committed as `8040f04`" — **FALSE**: `git cat-file` fails,
reflog shows no commit after `ad1dc03`.

**Verification (coordinator-run, all checked in the diff):** suite **1336 passed**
(1327 + 9 new); scope is ONE display mechanism (`src/analysis/live_debug_processor.py`
+81, `src/output_gen/overlay.py` +61, `tests/test_debug_panel.py` +61,
`tests/test_live_debug_decoupling.py` +108); reads ONLY
`BallDetector.raw_detections` (the AGENTS.md §6 side channel) plus the tracker's
survivor list, flag looked up never re-derived; no new Config key (class attribute);
no `FrameProcessor`/tracker/classifier change; saved video stays unpanelled (writer
gets the pre-panel frame — but with the toggle ON it now carries candidate boxes;
display behaviour, not pipeline). Cross-check: #72's K-curve in its session
transcript (K=1.3 −5, K=1.5 −1, K=2.0 +1; 49→40 wrong touches after all 71) matches
its STATUS/doc writeup exactly.

**Committed:** (1) the overlay feature (src + tests); (2) this ritual +
`docs/g3_reach_cascade.md` + the archive. `.pi/goals/` goal-runner state left
untracked on purpose. **Next (coordinator's ranking, item 0a):** diagnose the
15 `set↔dig` swap bucket (+0.106, the largest surviving measured label lever) —
no `src/` change; overpass (+0.092) stays parked on a rule idea (open point 9).


### 2026-10-03 (seventy-fourth session) — coordinator: ritual completed and committed; the SET↔DIG swap lever AND the SERVE bucket are CLOSED (NO SEPARATOR — swaps are count errors in costume; the serve line is mostly MISSING far-side contacts); lever table corrected twice

**Asked:** standing "Continue" on G3; owner prompt (m00005): finish what the prior
sessions left, then continue toward the goal, as TIER-1 COORDINATOR (decide →
brief → verify; never write deliverables; never rubber-stamp).

**Finished (verified, then committed):** (1) the #73 live-debug ball-candidate
overlay — display-only, `b` toggle, reads only `BallDetector.raw_detections`; its
session's own "committed as `8040f04`" claim was FALSE (`git cat-file` fails,
reflog clean after `ad1dc03`) → committed as `da0c962` after checklist
verification (suite 1336, no processing-path change). (2) #72's half-finished
STATUS ritual + `docs/g3_reach_cascade.md` (reach-gate cascade REFUTED as a
label lever: K=1.2 precision-clean +14 found → −4 LABELS) → committed as
`c336753` with index/log/archive entries.

**Delegated + verified (the goal step):** the set↔dig swap diagnosis, run by a
worker on the #68-machinery G1 gate. **Verdict: NO SEPARATOR — the lever is
closed.** G1 reproduced exactly (185 accepted / 139 found / touch 96/139 =
0.691 / R0 79/139 = 0.568) before any swap was read; 13 swaps on the dump
population (9 GT-set→dig, 4 GT-dig→set), reconciled EXACTLY with #68's 15 (the
2 extras are production-only, P11 f7162/f7207, where the dump labels are
correct). All 12 dump-carried signals overlap between GT-set and GT-dig swaps
(best `ball_above_net_px` δ=−0.722, ~19 px overlap at n=9/4; the soft trends
point the way the possession mechanism already predicts). **Mechanism
(coordinator-checked in source):** `_decide` keys set/dig on the touch count
(`src/recognition/action_context.py:198-210`: touch 1 → DIG, touch 2+follow →
SET), so a swap REQUIRES a ±1 count error — 0/13 swaps carry a correct count;
all 13 are a subset of #70's 43 wrong-touch contacts; 8/13 also mis-attribute
team. **Consequence: #68's +0.106 swap line is NOT a separate lever — it
re-absorbs into the touch-count lever, whose two repair routes are already
measured closed (TC1 +0.050; #72 recall negative). The +0.244 GT-touch
substitution number already includes these swaps.** Remaining measured label
levers: 25 region serves +0.177, 13 overpass +0.092 (needs a rule idea, open
point 9), 12 far serves +0.032.

**Discipline:** worker had no `src/` change, no decode/seek, no GT edit,
held-out session untouched; coordinator independently reproduced the suite
(1345 passed = 1336 + 9 new pins incl. no-cv2/no-seek + determinism), checked
the resolver mapping in source, and accepted on the gates — not on the
worker's word. Artifacts: `scripts/probe_set_dig_swaps.py`,
`tests/test_set_dig_swaps.py`, `logs/swaps_report.md`, `output/swaps/report.json`
(logs/ + output/ git-ignored per convention).

**Open for the owner:** the entreno 0.90 metric definition (per-drill F1 vs
per-action accuracy); the overpass rule idea (open point 9) needs owner/tier-2.

**Then (same session, owner reroute): the SERVE bucket (+0.177, the last big
label lever) is CLOSED as a label lever.** Owner instructed mid-run to switch
delegation to the free OpenRouter route (`MODEL=stealth/space-bunny-alpha
scripts/run_task_openrouter.sh`); the in-flight GLM subagent was stopped at
~3 min (read-only, tree verified untouched) and the same brief relaunched
headless (`.pi/task_briefs/serve_bucket.md`). **Verdict: NO SEPARATOR.** G1
exact before any serve read (185 accepted / 139 found / dump base 85/139 =
0.612 / dump serves 7/12 / touch 96/139 / R0 control 79/139). Bucket split
**7 found-correct / 5 found-mislabeled / 13 NOT-FOUND (all 12 far serves +
P24)** — reconciled with #68's +0.177 (25/141 ✓) and near/far 13/12 ✓, while
the far **+0.032 line does NOT reproduce** (12/141 = 0.085; reported, not
reinterpreted; lever doc corrected: read far as "≈4.5 of 12 convert today").
The 5 mislabels = spike×3 (P9/P10/P12) + dig×2 (P11/P33), exactly #68's
serve→spike 3 / serve→dig 2 found-set residual. **Two named mechanisms, no
rule designed:** 4/5 read `behind_baseline=False` because the contact frame
catches the LANDING (feet 14.6–15.4 m at the frame; +5…+7 f later they read
inside at 16.6–17.0 m — a cousin of #60's closed M-a, which was about the
takeoff stance); P33 fails `rally_start` (a contact accepted 16 f earlier).
**Premise refuted: the dump DOES carry `behind_baseline` — in its
`candidate_passed_gates` stage, 185/185 rows (`src/recognition/
action_classifier.py:443-457`; the `accepted` writer drops it); a reduced
`_decide` replay reproduces the shipped serve labels 12/12**, so #70's
"replay scores 0/12 on serves" is a stage-selection issue, not a hard dump
limit. **Goal math: label-only fix = 90/139 = 0.647 (UNDER the bar); full fix
= 103/139 = 0.741 (OVER) but needs the 13 far-side contacts to be emitted at
all — the recall story (open points 2/5) is now load-bearing: without
far-side recall, 0.70 is unreachable on this match by labelling alone.** The
docs' +23 f serve latency is CONFIRMED a completeness artefact (nearest-ANY
over all 25; the found set's median is +1 f). Coordinator verification:
suite **1365** (1345 + 20) run independently; the source claim checked at
the cited lines; the JSON artifact checked (G1, split, branch 12/12, 24
signals, zero separators); vfr guard green; no `src/` change, no decode,
no GT edit, held-out untouched. Artifacts: `scripts/probe_serve_bucket.py`,
`tests/test_serve_bucket.py`, `logs/serve_bucket_report.md`,
`output/g3r1/serve_bucket.json`. Committed with STATUS + the lever-doc
correction.

**Open for the owner (updated):** (1) the entreno 0.90 metric definition;
(2) the overpass rule idea (open point 9) — now the ONLY surviving label
lever (+0.092); (3) whether to open the far-side RECALL story (the detector
sees the far ball at GT far serves per AGENTS.md §9, but no candidate
survives admission within ±15 f — the death is in candidate gating, upstream
of the resolver); (4) ratification gate for the two serve mislabel
mechanisms (default-OFF observer + non-serve controls per §6 before anything
acts on them).

**Then (#74c, same route): the INSERT path — the sanctioned way to give far
serves a record (SR4's promotion shape: INSERT, never relabel) — is MEASURED
and DOES NOT CARRY THE BAR.** The first worker degenerated after writing
`scripts/probe_insert_path.py` (stream error, EXIT 0, never ran it); the
coordinator ran the probe once (G1 green; far_hits 11/17 = PG2's exact point
list and seam split), then relaunched the remainder as a continuation brief
(`.pi/task_briefs/insert_path_continuation.md`). Placement rule keyed on
window starts over the EXISTING artifacts (no decode, no `src/` change):
**11/17 far hits — every at_seam serve, none of the 6 in_gap ones — at
precision 0.6111** (3 rally-contact misclaims + 1 dead-time + 3 late
near-side serve claims; 0 near misclaims; 0 owner-negative FP, a lower bound
since 4 of 9 owner negatives are mid-window). The 6 misses are structural:
in-gap far serves have no window start within 20–778 f to hang a claim on —
the ceiling is the POINT MAP's (PM1's uniform lateness), not the evidence
layer's. **Goal translation under the consistent convention (a)
(insert-into-denominator, verified against the dump: no accepted emission
within ±15 f of any hit serve, nearest 23–84 f late): all-17 IN-SAMPLE
96/150 = 0.6400, held-out arm 94/148 = 0.6351, label-only ceiling 90/139 =
0.6475 — all UNDER the 0.70 bar; under #74b's numerator-only convention the
same arm reads 96/139 = 0.6906, still under. #74b's "103/139 = 0.741" is
CORRECTED: it added the 13 not-found serves to the numerator without the
denominator (consistent: 103/152 ≈ 0.678; lever doc corrected).** The worker
also fixed two inherited probe bugs (the 0.0 precision print =
`classify_false_positives` applied to matched rows; a pool silently wider
than PG2's 28 px cut), both regression-pinned. Coordinator verification:
suite **1393** (1365 + 28) run independently; PG2 anchors reproduced
exactly. Artifacts: `scripts/probe_insert_path.py`,
`tests/test_insert_path.py`, `logs/insert_path_report.md`,
`output/insert_path/probe.json`. **Open for the owner (adds item 5): the
0.70 bar on this match is now a COMPOUND-LEVER question — the measured
compound (INSERT + overpass) reads ≈109/150 = 0.727 only in-sample-best,
with the overpass rule unsolved and 7 imprecise placements to clean; decide
whether to widen scope (point-map/seam repair for the 6 in-gap serves is the
prerequisite serve-recall lever) or re-examine the bar/metric definition.**

