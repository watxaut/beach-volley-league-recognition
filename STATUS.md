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

**Last updated:** 2026-10-02 (fifty-third session — **the far serve is solved as
EVIDENCE: 14/17 GT far serves at ZERO false positives, up from 0/17 in
production.** The three checks ran in the order they were proposed. **M2 (opener
gate) = strict win**: a serve opens a rally, so gating the G4 conjunction on
60-240 f of emitted-contact silence takes precision 0.579 -> **1.000** with recall
unchanged at 11/17, and the plateau is 60-240 f wide because the match separates
openers (>=153 f) from mid-rally gaps (<=134 f) — so it is neither a fit nor a
device-jitter artefact. **M1 (magnified far-end crop) = REFUTED, and it corrects
the record**: the detector already sees the far ball in 14-31 of 31 frames at
every serve except P31 f24543, so the long-standing "the far ball is seen on 0-1
frames in 8/17 windows" was a **tracker** statement, not a detector one; the 4x
crop recovers only P31 (2/31 -> 26/31) at +105 ms/frame and its median detection
is 3.2 px of sand noise. **M3' (structural proposer) = measured frontier**: raw
detections + a far-band occupant + a reach in bbox heights + the opener gate, with
no tracker and no shape geometry, gives 11/17 at precision 1.00 (runway-only),
15/17 at 0.94 (runway+court, reach 1.0, median |offset| **1 f**) and 17/17 at
0.90; the two zero-FP rules fail on *different* windows, so their **union is
14/17 with no false positive at all** across 24 mid-rally contacts and the 9 owner
FALSE/OFFGAME moments. The two residual FPs are pre-serve ball handlings: no
dead-time test can separate those, only the toss does, and the toss is exactly
what the far-end geometry refuses. **A measurement defect was found and fixed on
the way**: every windowed G4 probe seeks, and a seek on this VFR file lands
**-28..+30 f** off, so the G4 score was really 11/17 (not 6/17) with offsets
systematically -9 f; two new seek-free probes, a 648-combination offline sweep,
`tests/test_vfr_seek_guard.py` (which also found that the owner-GT annotator can
display an off-frame image) and `tests/test_structural_serve_rule.py` (13 tests).
Suite **1008**, `src/` untouched. **Next = the owner picks the operating point
(recommend 14/17 evidence) and S4 consumes it post-hoc; the label bucket
(`overpass` 0/18) is still the largest held-out loss.**)

**Previous (fifty-second session — **the possession signal
(open point 9 enabler) was built, tested, and REFUTED as a needle-mover, then
parked default-OFF in a harness.** Two mechanisms: a ball-field width TREND
fallback in attribution (`_width_side_trend`: when the strict 26-35 px regime
abstains, the direction the apparent width moves names the arriving side) and a
motion-history tie-break (`_motion_convergence`, owner spec open point 5:
candidates within 60 px of the closest re-ranked by trajectory convergence).
Both were wired with config keys + drift guard + 18 unit tests, then measured:
entreno/dev effectively neutral (the e1 "team flip" was run-to-run
nondeterminism; dev shifted only one L-R `player_id`), and the decisive offline
replay of the REAL attribution methods on the match dump gives base **121/157
(0.771)** → both **122/157 (0.777)**. The trend fires 11× and is **11/11 on the
correct side** but mostly redundant; motion changes **0** team attributions.
The carry errors it targeted mostly have NO ball signal at all (ball lost),
which no ball-field rule can recover. Verdict: parked in
`scripts/possession_signal_harness.py` (default OFF, T5/R1 precedent), evidence
`scripts/probe_possession_signal.py` + `docs/g3_possession_signal.md`; `src/`
untouched. Suite **985** (+20). **ALSO: a second pi session (G4/#51) worked this
repo concurrently and its commit collided with my stash mid-validation — never
run two sessions on this repo at once.** **Next = the owner decides on the S4
consume-the-serve-events step, or another possession attempt with a NON-ball
signal (motion history alone was inert for team attribution).**)
**Previous (fifty-first session — **G4: the two serve-EVIDENCE
event emitters the owner asked for are built, scored and committed.** New
`src/analysis/serve_events.py`: **E1 `far_flight`** (a ball whose apparent bbox
width GROWS is flying at the fixed long-axis camera = far-side flight) and **E2
`runway_occupant`** (any raw person detection whose foot is behind the far line
and inside the two sidelines CONTINUED TO INFINITY, never behind the near line),
plus the owner's conjunction `serve_candidate` ("a player in that area, with the
ball, and a contact"). Wired into `FrameProcessor.process_frame` as pure
observers, **default OFF** (`--serve-events`), with two inert detector side
channels (person boxes the play-area filter dropped; pre-static-suppression ball
candidates). Geometry is image-space from the 8 calibration clicks because the
far-end ground homography is off by ~10x, and the band STRADDLES the far line as
a fraction of the court's projected depth. `scripts/score_serve_events.py`
(+`--control`) + 45 tests + `docs/g4_serve_events.md`; suite **965**.
Measured on the 17 GT far serves (windowed replay through the real
`process_frame`): runway **15/17** (only 7/17 genuinely off-court), far flight
in window / conjunction at +-15 f — **CORRECTED in the addendum below** (this
block's ball-side numbers came from a config that silently ran the COCO
`yolov8n` ball detector; with the production model they are far flight 16/17
in window and 8/17 at +-15 f, conjunction 14/17 in window and **6/17** at +-15 f
— 3/5 dev, 3/12 held-out — with 4/24 control false positives, precision 0.60,
recall 0.35, against production's **0/17**). Verdict: the runway leg is strong, the conjunction is a
real but thin signal — an evidence stream for the G2 decision, NOT a fix.
**Next = the owner reads `docs/g4_serve_events.md` and decides whether to consume
the events in the post-hoc layer (S4) or keep pushing the ball side (a far ball
is detected ~1 frame in 4 and half the far-serve windows show no growing run at
all); the label bucket (`overpass` 0/18) is still the largest held-out loss.**)

**Previous (fiftieth session — **G3 overpass
net-crossing diagnosis: the ball-width crossing signal is REFUTED.** Open
point 9's "thread the crossing signal into the resolver" lever was probed
diagnose-only (`scripts/probe_overpass_crossing.py` + 19 tests +
`docs/g3_overpass_crossing.md`; no `src/` change, no decode). On the 18
held-out GT overpasses (P9–P33) a width-regime crossing across the contact is
present at only **3/18**, indistinguishable from the non-attack controls (set
4/46, dig 10/55) — K1 (signal present) and K2 (separation) both FIRE. The ball
is tracked on both sides at **18/18**, so it is not a detection gap (K3
clean): the crossing is at the net/tape where the width regime abstains, and a
high lob reads ambiguously on both sides. The perceived next-contact team is
also unusable as a substitute (overpass flip 8/18 = 0.444 vs controls 0.582;
K4 fires) because the stream's possession/team read is noisy (G1 side-level
0.755). The overpass loss is therefore a LABEL/RULE problem, not a geometry
one: the resolver emits `overpass` only at touch-2-no-follow while GT
overpasses span touch 1/2/3, and the emitted reads were dig 6 / spike 5 / set
2 / missed 5. The three implementable rules were then REPLAYED offline through
the imported resolver on the dump's raw contacts: **all net-negative** (baseline
85 correct; next-team 71, no-follow 80 with 3/18 recovered, next-team+side 82
with 0/18) — so no overpass `src/` change ships (T5/R1 precedent). Suite **920**
(+23). **Next = the ENABLING work (a reliable possession/next-toucher signal —
the 34 genuine side errors) or the G2 far-serve decision / S4; the label bucket
is still the largest held-out loss (57/183).**)

**Previous (forty-ninth session — **S3 DONE: the pass-2
side-switch/squad layer.** `scripts/resolve_side_switches.py` (+25 tests) +
`docs/g3_side_switch_layer.md`; no `src/` change, no decode. Derives the beach
switch cadence from the POINT ORDER alone (`[7,14,21,28]`, EXACT vs the owner
`side_switch_after_point`), maps court-side→squad by parity, and augments
`actions_pass2` with `pass2_squad`. The needle is a measurement confound found
en route: the perception stack emits COURT-SIDE letters while the GT is SQUAD,
so G1's raw `team 0.518` is side-vs-squad; the same 139 found contacts score
**105/139 = 0.755** squad-mapped (leaving 34 genuine side errors). The
player-crossing cross-check is honest but useless (3/4 switches supported, but
16/28 non-switch boundaries also supported — ids hop, open point 2) and is
evidence only. Suite **897** (+25). **Next = S4 (consume `pass2_squad`) or the
G2 owner far-serve decision; the label bucket (`overpass` 0/18) is still the
largest held-out perception loss.**)

**Previous (forty-eighth session — **G1 DONE: the first
HELD-OUT contact score on P9–P33.** `scripts/score_heldout_contacts.py`
(+20 tests, `tests/test_heldout_contacts.py`) + `docs/g3_heldout_p9_p33.md`;
no `src/` change, no video decode. On the 183 owner contacts of the 25 held-out
points the production stream scores **P 0.785 / R 0.760 / F1 0.772**, class
**0.590**, team **0.518**; pass-2 is flat on F1 (0.774) and again costs class
(0.561). The re-rank: held-out contact *detection* is BETTER than dev
(F1 0.772 vs 0.597), so the dev loss budget over-weighted proposal (39% vs
24%) and under-weighted the gesture label (14% vs **31%** — 57 wrong-label /
44 missed / 36 wrong-team of 183). `overpass` is never emitted correctly
held-out (recall 0.000 across 18 contacts). The 12 held-out FAR serves are
**0/12**: 8/12 have a nearby emitted "serve" (6 are the pass-2 re-labelled GT
reception, 2 are production serves 26–28 f late with the opposite team), 4
have nothing within ±80 f — the S0b dev finding reproduced on 12 independent
contacts. The 44 missed are mostly not empty-stream (41/44 have an action
within ±80 f, 7–69 f away). The stage waterfall is NOT reproduced (the only
full-match diag dump is the R1 bw=0.3 run); recorded as unavailable, never
faked. Suite **872** (+20). **Next = G2: the owner decision on the far-serve
lever, now decidable on data with baseline F1 0.772 / far-serve 0/12.**)

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
- Ace — BLOCKED: needs point-outcome layer (21.3) + far-side serve
  emission (22 — 16/32 match serves); parked as point 13.
- Error (serve fault) — BLOCKED: same dependencies as ace.
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

**The far serve is SOLVED as evidence (#53): 14/17 GT far serves at zero false
positives, against 0/17 in the action stream.** The three levers the owner asked
for were run in order and each returned a verdict: the **opener gate** is a
strict win (precision 0.579 -> 1.000, recall unchanged, plateau 60-240 f wide);
the **magnified far-end crop** is refuted and, more importantly, shows the far
ball was never missing from the detector's point of view (14-31 of 31 frames at
every serve but P31) — the old "0-1 tracked frames" line was the *tracker*; and
the **structural proposer** measured as a clean frontier (11/17 @ 1.00, 15/17 @
0.94, 17/17 @ 0.90, union of the two zero-FP rules 14/17), built on raw
detections so it needs neither the tracker nor the px-space contact geometry.
A measurement defect surfaced on the way: windowed G4 probes seek, and a seek on
this VFR file lands -28..+30 f off, so the G4 score was really 11/17 with -9 f
offsets, not 6/17 (`docs/g4_far_serve_alignment.md`, now guarded by a test).

Everything here is **evidence**, not labels: `src/` is untouched, nothing is
written to `events`/CSV, and per AGENTS.md §6 + the S0b lesson it is consumed
post-hoc. Next owner action: pick the operating point (recommend the 14/17
union) and let S4 consume it for who-served / aces / serve faults. Still open:
S4's remaining work, the label bucket (`overpass` 0/18), the reach-gate and
dig-vs-ball-death buckets, and the two seek defects the guard test surfaced
(owner-GT annotator, thumbnail crops).

- **Held-out score** — `scripts/score_heldout_contacts.py` scores P9–P33
  against `ground_truth/20260920_match_contacts.json` with the S0b scope
  discipline (region f5240–f26147 = the padded span of the emission windows;
  a SCOPED GT copy so P1–P8 can't be charged as FN; `evaluate_timed` matcher,
  `--ignore-player`, effective ±15 f). Production **P 0.785 / R 0.760 / F1
  0.772**, class 0.590, team 0.518; pass-2 F1 0.774 / class 0.561 / team 0.561.
  Doc `docs/g3_heldout_p9_p33.md`; artifacts `output/heldout_contacts/`.
- **S3 side-switch/squad layer** (`scripts/resolve_side_switches.py`, +25
  tests, `docs/g3_side_switch_layer.md`) — beach cadence from the point order
  alone → `[7,14,21,28]` EXACT vs the owner schedule; side→squad by parity;
  `actions_pass2.pass2_squad` on 207/207 actions. The recorded G1 **team 0.518
  is a side-vs-squad confound** (the stack emits side letters): the same 139
  found contacts score **0.755** squad-mapped, leaving **34 genuine side
  errors**. The player-crossing cross-check is evidence-only (ids hop, open
  point 2).
- **Possession signal REFUTED + parked (#52, open point 9 enabler)** —
  `scripts/possession_signal_harness.py` (default OFF) +
  `scripts/probe_possession_signal.py` + `docs/g3_possession_signal.md`; no
  `src/` change, no decode. Offline replay of the REAL attribution methods on
  the match dump: base **121/157 (0.771)** → both **122/157 (0.777)**; the
  ball-field width trend fires 11×, **11/11 correct side** but redundant;
  the motion tie-break changes **0** team attributions. The carry errors it
  targeted mostly have no ball signal at all (ball lost mid-flight). Parked
  per the T5/R1 rule.
- **Miss taxonomy (perception, 183 contacts)** — 46 correct / **57
  wrong_label** / 36 wrong_team / 44 missed. The largest bucket is the label,
  not proposal. The 36 wrong_team is inflated by the side-vs-squad confound
  (S3); the true side error is ~34 of 139 found contacts. `overpass` 0/18
  correct (13 found, all mislabelled); serve recall 0.280 (far serves all
  missed). Only 3/44 missed have no action within ±80 f.
- **Overpass crossing diagnosis REFUTED (#50, open point 9)** —
  `scripts/probe_overpass_crossing.py` (+19 tests) +
  `docs/g3_overpass_crossing.md`; no `src/` change, no decode. On the 18
  held-out GT overpasses the width-regime crossing across the contact is
  **3/18** vs non-attack controls (set 4/46, dig 10/55): K1+K2 fire. The ball
  is tracked both sides at **18/18** so it is NOT detection (K3 clean); the
  crossing sits at the net/tape where width abstains and a high lob reads
  ambiguously. The perceived next-team is no substitute (overpass flip 8/18 =
  0.444 vs controls 0.582; K4 fires). Emitted reads: dig 6 / spike 5 / set 2 /
  missed 5; the resolver emits `overpass` only at touch-2-no-follow while GT
  overpasses span touch 1/2/3. Artifacts `output/g3_overpass/`. The three
  implementable rules replayed offline through the imported resolver are ALL
  net-negative (baseline 85 → 71/80/82), so no `src/` change ships; the blocker
  is a reliable possession/next-toucher signal (34 genuine side errors).
- **G4 serve-evidence events (#51, re-scored #53)** — `src/analysis/serve_events.py` emits
  `runway_occupant` / `far_flight` / `serve_candidate` from the shared frame path
  as pure observers, **default OFF** (`--serve-events`); `serve_events` appears
  in `pipeline_output.json` only when they run. Geometry is image-space from the
  8 calibration clicks (the far-end homography is ~10x wrong), laterally the two
  sidelines continued to infinity, longitudinally a band straddling the far line
  (`-0.15..+0.30` x court depth). Scored on the 17 GT far serves vs 24 mid-rally
  non-serve control windows: runway **15/17** (only 7/17 genuinely off-court),
  conjunction **6/17** at +-15 f (**3/12 held-out**) vs production **0/17**, FP
  **4/24** -> precision 0.60, recall 0.35. Docs `docs/g4_serve_events.md`,
  `docs/g4_far_serve_failure_mode.md`; scorers `scripts/score_serve_events.py`,
  `scripts/probe_far_serve_{tracking,geometry}.py`. These are EVIDENCE — no
  consumer is wired, and the label bucket (`overpass` 0/18) is still the largest
  held-out loss. **[#53 those numbers are superseded — the windowed probes SEEK
  and a seek on this VFR file lands -28..+30 f off
  (`docs/g4_far_serve_alignment.md`). Seek-free the same conjunction scores
  **11/17 with 8/24 control FPs (precision 0.579)**, and with the **opener gate**
  **11/17 at 0/24 FPs — precision 1.000.** Keep the old figures only as
  provenance.]**
- **THE FAR SERVE IS SOLVED AS EVIDENCE (#53, `docs/g4_structural_serve.md`)** —
  a structural proposer over the RAW detections (no tracker, no px-space shape
  test): *no emitted contact for 60-240 f* + *a person in the far band* + *a
  far-side ball-sized (8-60 px) raw detection within 30 f* + *the ball within R
  bbox heights of that person*. Measured frontier on one seek-free pass (17 GT far
  serves, 24 mid-rally controls, the 9 owner FALSE/OFFGAME moments):
  runway-only @ reach 1.5-4.0 = **11/17, 0 FP of any kind**; runway+court @
  reach 1.0 = **15/17, 1 owner FP** (f5130, ball handling after the point ended);
  @ reach 2.5 = **17/17, 2 owner FPs** (adds f2414, walking to the serve line with
  the ball in hands). Median |offset| **1 f** (the G4 conjunction's is -9 f). The
  two zero-FP rules fail on *different* windows, so their **union is 14/17 with no
  false positive at all** — the recommended operating point. Driver
  `scripts/sweep_structural_serve.py` (648-combination offline sweep over the
  recording, no decode), tests `tests/test_structural_serve_rule.py`. The
  residual FPs are pre-serve handlings: no dead-time test separates them, only the
  toss does, and the toss is what the far-end geometry refuses — which is why
  this is evidence (post-hoc, AGENTS.md §6) and not a label source (S0b broke 3
  correct dig labels).
- **M1 magnified far-end pass REFUTED (#53, `docs/g4_far_ball_presence.md`)** —
  the same production weights on a 4x-magnified square crop of the far band
  (`scripts/probe_far_roi_ball.py`, tile 320, 3 tiles, tile geometry from the 8
  calibration clicks): **0 of 17 windows were empty for the full-frame arm**, so
  the "the far ball is too small to detect" premise is FALSE — the detector sees
  15-21 px balls in 14-31 of 31 frames at every serve except P31 f24543 (2/31,
  which the tiles recover to 26/31 at +105 ms/frame). The tiled arm's median
  detection is 3.2 px of unscaled sand/line noise. Parked as a possible
  P31-class fallback; not built. **This also corrects a long-standing claim: the
  "0-1 tracked frames in 8/17 windows" figures in the STATUS/G4 docs are TRACKER
  counts, not detector counts.**
- **Scale-aware geometry REFUTED (#52, the owner's "lets try scale aware
  geometry")** — `scripts/scale_aware_harness.py` (subclass of the production
  `ActionClassifier`, OUTSIDE `src/` per the refuted-mechanism rule) +
  `scripts/probe_scale_aware_geometry.py` + `docs/g4_scale_aware_geometry.md`;
  7 fidelity/inertness tests pin the `px` arm to `super()`. Arms over the SAME
  recorded ball tracks (57 windows: 17 far serves, 16 near, 24 non-serve
  controls; +-15 f): thresholds as `k x ball width` buy **+1 far contact
  (held-out only, 0 on dev) for +4 control false positives** -> precision 0.40
  -> 0.33; k=0.5 buys nothing and still costs a FP. A **mirror** arm (a
  far-side serve is hit at the camera, so the ball PEAKS and descends — the
  mirror of the `bounce` shape) adds nothing on top. The multiplier each test
  would need says why (`--required-k`): bounce **8.2** ball widths, redirect
  **2.4** (near-equivalents 4.5 / 1.3); the tests reachable at k~0 (drive decel,
  serve fed ascent, mirrored peak) are reachable because they no longer
  discriminate (any downward change / gravity arc / lob apex passes). Three
  walls, none a threshold size: 8/17 far serves have **no usable vertex at all**
  (0-1 tracked frames), the rest are **wrong shape/sign** (depth-dominated
  motion), and the contacts that do fire are **wrong label** (attribution picks
  the nearest tracked player). The G4 evidence path still dominates every arm
  (6 hits / 4 FP = 0.60 precision, 0.35 recall). Nothing shipped.
- **WHY the far serve dies (#51, the "which signal does not switch" answer)** —
  `docs/g4_far_serve_failure_mode.md`. The stage waterfall is nearly IDENTICAL
  far vs near (first failing stage: candidate 6/17 vs 7/16; probe reasons
  `no_ball_sighting` 334 vs 256, `no_contact_geometry` 150 vs 195), so it is not
  a skipped stage: **the contact GEOMETRY cannot reach its thresholds at the far
  end**. Replaying every recorded far-serve ball track through the production
  `ActionClassifier`: no vertex is ever the lowest point (bounce needs a 26 px
  rise), horizontal flip **0 px** (redirect needs 20 px), `dvy` +4/-1 (drive
  needs <= -8), `dvx` 2 px (needs 12), and the **serve branch's fed-ascent
  margin is +0..+4 px against its required +10** — the far toss DECAYS like free
  flight, which is that branch's designed reject. Near-side control reaches
  rise 60-100 px, flips 38-65 px, `dvy` -42, fed ascent +13..+20 and fires 5/10.
  Root cause: all four thresholds are near-half-scale px constants (AGENTS.md
  §5) and at the far end the ball's image motion is DEPTH-dominated (growing +
  descending toward the lens), so a far serve looks like uninterrupted free
  flight. Secondary, independent: 2/17 far serves have zero raw detections at
  conf 0.15 and 5/17 never lock a track; and where a candidate IS accepted
  (P28 f21344-46, P25/P26/P4) the label is dig/overpass because attribution
  picks the nearest TRACKED player — the server is not one.
- **Far serves 0/12 held-out** — 6/8 with a nearby "serve" are the pass-2
  re-labelled GT reception (+26…+34 f), 2 are production serves 26–28 f late
  with the opposite team, 4 have no serve within ±80 f. The S0b dev finding
  holds on 12 independent contacts; the far-serve CONTACT is measured, not
  data-starved.
- **Scope caveat** — the episode-map emission windows are PREDICTIONS and
  only 12/25 cover their own owner contact range (P32 window f24614–f25085 vs
  contact f25375); the contact P/R/F1 is window-independent, the dead-time /
  points metrics inherit the drift.
- **Stage waterfall gap** — `scripts/waterfall.py` needs a production match
  diag dump; the only one is the R1 bw=0.3 run, whose gate decisions differ.
  A fresh production dump is a follow-up decode.
- **G0 facts stand** — match contact GT `20260920_match_contacts.json`: 33
  points / **211 owner contacts** (28 P1–P8 + 183 P9–P33), match-frame axis,
  all `source=owner_gt`; P1–P8 rebuild field-identical (only `raw_line_no`
  +3); side→squad is switch PARITY; P30 f23545 `action=null` +
  `owner_action_unspecified`. Builder `scripts/build_match_contact_gt.py`.
- **New practice video** `20290928_entreno_vall_dhebron.mp4` still not run
  (cheap parallel G3-footage item; it has no labels).

**Production state (as of 2026-09-28; unchanged by #30's documentation-only
assessment — #28 shipped the pass-2 serve re-label layer over existing
artifacts, zero src/ changes).** The proposed generalization roadmap in
`docs/202609-28-astra-fix-pipeline.md` awaits owner approval; the active
implementation backlog below remains unchanged.

- **Weights:** `models/volleyball_ball_best.pt` = **v3** (fine-tuned FROM
  best.pt on 1091 + 350 rebalanced frames; ADOPTED 2026-09-26). Sub-1080p
  ingest upscales once to `_up1080.mp4`. Pose gating live in the shared
  `classify_actions` path.
- **Pass-2 serve layer SHIPPED (28th session):**
  `scripts/relabel_serves.py` (+29 tests) over the anchored map +
  pipeline JSON → `output/serve_relabel.json` (per-point resolution +
  demotions + `actions_pass2` annotated stream + gates). Far prefix
  census 2/8 → **8/8**; serve-typed 20 → **31** (−6 owner-FALSE/OFFGAME
  demotions, +17 bump-serve re-labels, 6928A reported-only); 32/33
  points carry a serve resolution (P32 report_only, round 3); P20
  owner-pinned to 14516A (q5). All 17 owner verdicts reproduce
  mechanically. 13 team overrides flagged (far-side width-band class).
  **CAVEAT (#42): the 8/8 census and the 31 serve-typed are POINT-level;
  at CONTACT level P1–P8's far serves are 0/5 (relabeled contact 31–50 f
  late, 3 of 5 are GT receptions) — the "width-band class" attribution of
  the overrides is unverified (P1 f247 / P6 f3070 are correct-team near
  receptions: the override masks a missing serve contact).**
- **Pass-2 winner layer SHIPPED (43rd session, open point 21.3):**
  `scripts/resolve_point_winners.py` (+27 tests, `docs/point_winner_layer.md`)
  — fault prior over the terminal live touch, side-letter winner, explicit
  GT-leakage projection guard (13 winner-serves overrides flagged, never
  inherited). 33/33 decided, **18/33 (54.5%)** vs the 33 dictated winners
  after the validate-only side→squad mapping; 8 misses are the point-22
  terminal-touch/far-serve attribution gap, 3 kill/ace (ball-death side not
  in any artifact), 3 serve-team, 1 pinned-outside-window. Honest baseline;
  consume after S1–S3. No `src/` change, no decode.
- **Match (20260920 — the only real match):** **31/33 GT points confirmed
  (0.939)**; actions 207 (dig 84 / spike 45 / set 42 / serve 20 /
  overpass 9 / block 7) at the perception layer — the pass-2 layer
  re-interprets serves post-hoc (31 serve-resolved incl. 17 re-labels);
  perf **68.0 ms/frame** (14.7 fps, 30.5 min).
- **Entreno gate record** (`evaluate --ignore-player` F1): e1 0.706, e2
  0.571, e3 1.0, e4 0.933, e5 0.923, e6 0.933, e7 0.75; teams 1.0 except
  e6 0.857. Suite **554 green**. Live-debug decoupling (#25): `--debug-live`
  ≈ 12 fps vs 8.0, rendered frames + logs byte-identical.
- **Known residuals:** e4/e5/e6 GT re-adjudication vs the v3 streams
  (queued — owner-ratified contact sheets); e3 f539 outcome enrichment
  reads dug vs GT kill (tracker-side fast-fall conf dip — 22 family);
  P32's serve + 6928A's verdict + P20's window/re-serve question sit in
  the round-3 owner queue.

**Action-reliability track (session 38):** executable plan lives in
`docs/action_reliability_plan.md` (T1-T15, status per task). Dev clip =
`video_ari_joan_8_first_points.mp4`; T1 readiness DONE, T2 dev-clip GT DONE
(P6 f3131 owner-RATIFIED as an overpass, 09-29), T3 time-matched evaluator
DONE, T4 loss waterfall DONE, **T5 DONE (step 1 diagnosis + step 2 A/B =
mechanism refuted)**. Dev-clip baseline: contact P 0.586 / R 0.607 / **F1
0.597**, class 0.706, team 0.706, 1 duplicate, 2.703 FP per dead-time minute,
points 6 matched / 2 missed / 0 spurious (mean IoU 0.707); waterfall 0
detection / 0 admission / **6 candidate** / 5 gate / 5 actor-team / 4 label /
8 survives. **T5 result (38th session):** both candidate mechanisms recover
**0/5** far serves. A = weak 3 px/f tier far-band gated: 5/5 locks in the
offline sweep (as measured in step 1) but 19 new bootstrap locks per 4968
frames in the real-class replay and still no contact candidate. B = backfill
on a fresh lock: 0 new lock opportunities, +1 dead-time candidate, and it
converts the far-serve probe rejections from `no_ball_sighting` (23/27/20/21/21
of 31 window frames) to `no_contact_geometry` — the missing pre-contact history
of the step-1 diagnosis is supplied and the loss moves one gate along. The
blocker is the CONTACT PROBE's serve signature (a fed ascent, |vin3| ≥
|vin6|+10; the far toss is a decelerating float) + the absent far-toss
detections on P4/P6/P8 — recognition/detection mechanisms, not ball-track
admission. **NEITHER mechanism is shipped** (session 39): `src/` is back at
`185c6f0` (`git diff 185c6f0 -- src/` empty) and A + B live only in
`scripts/serve_mechanism_harness.py` as default-off subclasses, so the A/B
replay is reproducible with the same numbers (evidence in
`docs/t5_serve_admission_diagnosis.md` step-2 section,
`docs/t5_mechanism_ab.md`, `docs/t4_loss_waterfall_dev_clip.md` "After T5").
**R1 attempted and REFUTED (41st session):** the confirmation-time
departure gate passed its fitting domain cleanly (dev contact P
0.586→0.739 / F1 0.597→0.667 with exactly the 6 offline-flagged FPs
removed; e4 0.933→1.000; entreno otherwise byte-identical) but the
held-out full match refuted it at 0.3: 22 removals incl. P11's
owner-confirmed serve f7132 (0.285 bw/f) and 6928A → owner-verdict
regression, points 31/33→28/33, far census 8/8→7/8. Width-normalised
departure conflates dead balls with far float serves (T5 physics again).
NOT shipped (owner option (a)): `src/` back at exactly `185c6f0`,
mechanism parked reproducible (`scripts/departure_gate_harness.py` +
`action_evidence.py` + `probe_departure_removals.py`/`probe_owner_verdicts.py`;
banner + tables in `docs/g3_r1_departure_gate.md`); suite 755. Revisit
only as a width-band-aware mechanism after T8.
Next = the far-side serve follow-up. The 42nd-session architect review chose a
diagnose-only S1 looming probe first; **#44 ran it and it was REFUTED at kill 2**
(no separable `L` gap; see Log + open point 22). T5 (tracker admission) and R1
(departure gate) were already refuted; the pass-2 relabel option stays rejected.
The next far-serve lever is an OWNER call (targeted far-flight detector mining
vs another contact-proposal mechanism); S2 is NOT triggered. Owner-side S0
(P9–P33 contact GT + capture spec) remains the highest-value async input.

**Active next (ranked, goal-driven - see North-star; G3 first) — RE-RANKED by
the 42nd-session architect review (Log #42) and again in #46/#47 now that the
S0 GT exists and G0 landed.** The "detector v4 → normalise → learned gestures" order was NOT
adopted. Order = make the labels machine-readable → measure held-out → fix the
contact proposal where the loss is → pass-2 layers on real contacts → learn
last. One mechanism per session; each step's kill criteria are pre-registered.

- **G0 (worker) — [#47 DONE 2026-10-01] the P9–P33 contacts are
  machine-readable:** dialect-B `parse_contact_gt` + `scripts/build_match_contact_gt.py`
  → `ground_truth/20260920_match_contacts.json` (211 contacts P1–P33 on the
  match frame axis, 33 contact sheets). Gates met: P1–P8 field-identical
  rebuild, every contact line in `events`, switches after P7/14/21/28,
  parentheticals verbatim (`raw_line_no` is the only dev-GT difference, +3 from
  the owner's later header lines). Open point 24(a) closed.
- **G1 (worker) — [#48 DONE 2026-10-01] the first HELD-OUT contact score.**
  `scripts/score_heldout_contacts.py` + `docs/g3_heldout_p9_p33.md`:
  production F1 0.772 / class 0.590 / team 0.518; miss taxonomy 46 correct /
  57 wrong-label / 36 wrong-team / 44 missed; far serves **0/12**. The dev
  loss budget is re-ranked: the LABEL bucket dominates held-out (31%), not
  proposal (24%). Stage waterfall deferred (needs a production match diag
  dump). This is the baseline every future mechanism must beat.
- **G2 (owner decision, ANSWERED #53 — pick the operating point).** T5
  (tracker admission), R1 (departure gate), S1 (looming) and pass-2 are all
  refuted; the 12 held-out far-serve contacts are now measured at **0/12**
  (baseline F1 0.772), so the choice could be made on data.
  **[#53 the far-serve lever is ANSWERED: it is neither "detector mining" nor
  another px-space contact-proposal mechanism — the ball IS detected, so the
  lever is a STRUCTURAL proposer over the raw detections with the opener gate,
  scoring 14/17 at precision 1.00, 15/17 at 0.94, 17/17 at 0.90
  (`docs/g4_structural_serve.md`). The G1 data's other lead (the gesture-label
  bucket, `overpass` 0/18) was diagnosed at #50 and remains an owner/architect
  call.]** **[#50: the gesture-label lead was
diagnosed for its worst class — the ball-width net-crossing signal for
`overpass` is REFUTED (3/18, no separation; not detection; next-team signal
unusable). So the overpass lever is now an owner/architect call on a
gesture/touch-rule + possession-signal change, not a ball-geometry threshold;
the rest of the label bucket (spike→block 7, set→dig 10, …) is still
diagnosed only at the confusion-matrix level.]** **[#51: the owner asked for the EVIDENCE to be emitted
instead of choosing: G4 delivers `far_flight` + `runway_occupant` +
`serve_candidate` (default OFF, `docs/g4_serve_events.md`). Scored on the 17 GT
far serves: runway 15/17, conjunction 3/17 at +-15 f (3/12 held-out) vs
production 0/12, with 1 FP in 24 non-serve control windows. The remaining choice
is 'consume the events post-hoc (S4)' vs 'keep pushing the ball side'.]**
- **G4 (RESOLVED #53, was: consume the serve events or push the ball side).**
  `src/analysis/serve_events.py` + `docs/g4_serve_events.md` emit
  `runway_occupant` / `far_flight` / `serve_candidate` (default OFF,
  `--serve-events`, inert otherwise). The owner's "check all in the order you
  stated" resolved both branches at once: pushing the ball side is **refuted**
  (M1: the far ball is detected in 14-31 of 31 frames at every serve — the
  "1 frame in 4" premise was a COCO-detector artefact and the "0-1 tracked
  frames" figures are TRACKER counts), while consuming the evidence is **now
  strong enough to build on**: with the opener gate the existing conjunction
  reaches 11/17 at precision 1.000, and a structural proposer over the raw
  detections reaches **14/17 with zero false positives** (union of the two
  zero-FP rules), or 15/17 at 0.94 / 17/17 at 0.90
  (`docs/g4_structural_serve.md`). Any consumer ships post-hoc as a serve
  EVIDENCE record, never as a label (pass-2 proved the label-source route at
  0/5 with 3 correct dig labels broken), with F1 0.772 / far-serve 0/12 as its
  baseline and P9–P33 as the held-out check. Re-score with the SEEK-FREE
  `scripts/probe_serve_events_seq.py` (the old `score_serve_events.py` seeks
  and is +-30 f unreliable) and sweep the rule frontier with
  `scripts/sweep_structural_serve.py`.
  **[#51 the WHY is measured too — `docs/g4_far_serve_failure_mode.md`: the
  contact GEOMETRY is the signal that does not switch. Far-side contact tests
  reach 0 of 4 (no lowest vertex, 0 px horizontal flip, dvy +4 vs <= -8, dvx 2
  vs >= 12, fed ascent +0..+4 vs >= 10) while near-side control reaches them and
  fires 5/10. **Option (a) SCALE-AWARE geometry was tried and is REFUTED**
  (#52): +1 far contact (held-out only, 0 on dev) for +4 control false
  positives, precision 0.40 -> 0.33; a mirror arm adds nothing. Required-k
  arithmetic in `docs/g4_scale_aware_geometry.md`: bounce would need 8.2 ball
  widths, redirect 2.4 (near: 4.5 / 1.3), and the k~0-reachable tests are
  reachable only because they stop discriminating. So option (b) is what
  remains: consume `serve_candidate` post-hoc as evidence (never as a label),
  plus the ball-PRESENCE question (8/17 far serves have no usable vertex).]**
- **G3-footage (worker, parallel, cheap) — first run of the new practice video**
  `20290928_entreno_vall_dhebron.mp4` (`make run VIDEO=…`, ~21k frames, the
  fastest full video here): sanity-check the pipeline on a second recording
  session at a known venue, then use it as the **second fold** for anything
  leave-one-session (T12's precondition) and as the side-change subject IF the
  owner dictates which points had side switches (open point 2). Do not spend
  effort here before G0/G1 — it has no labels.
- **S0 (OWNER, async, no code) — [#46 LANDED]** held-out contact GT for match
  P9–P33: **DONE** — the owner appended ~200 contact lines to
  `ground_truth/20260920_match_ari_joan_contacts_p1_p8.txt` (2026-09-30) in a
  second dialect, covering the 12 far-serve points. Not machine-readable yet
  (0 of the new lines parse; the worker half is G0 above).
- **S0b (worker, script only) — [#45 DONE 2026-09-30]** score `actions_pass2`
  at CONTACT level against the dev GT P1–P8 with `scripts/evaluate_timed.py`
  (NOT `--autonomous`: pass-2 carries owner inputs; the GT-input audit is
  recorded instead): `scripts/score_pass2_contacts.py` +
  `tests/test_pass2_contact_score.py` + `docs/g3_s0b_pass2_contact_score.md`.
  Result: far serves **0/5**; GT serves matched **1/8**; pass-2 contact F1
  0.597 → 0.604 with class accuracy 0.706 → **0.562** (3 correct dig labels
  broken, 1 TP lost). Scope must be the point windows padded ±90 f, and the
  perception arm must reproduce the T4 baseline (asserted in-script).
- **S1 (diagnose only, no `src/`) — [#44 DONE 2026-09-30, REFUTED at kill 2
  (no separable `L` gap; see Log + Open point 22); S2 NOT triggered] far-side
  serve looming probe:**
  `scripts/probe_far_serve_looming.py` + `docs/g3_far_serve_looming.md`. In the
  new-rally state (no emitted contact within `RALLY_RESET_GAP`), a ball segment
  whose onset width is ≤26 px (below the 26–35 abstain band) and whose
  L = OLS slope of ln(bbox width) vs time in SECONDS over [onset, onset+0.5 s]
  is high = candidate far serve, contact placed at onset (T5 measured first
  sighting 2–4 f after contact). Secondary feature declared NOW: nearest
  far-team player `is_behind_baseline` at onset. L* = midpoint of the empty gap
  between the lowest dev far-serve L and the highest dev new-rally non-serve L.
  Inputs = existing dumps: `output/t4/dev_diag.jsonl`,
  `output/g3r1/match_bw03_diag.jsonl` (replay its `ball_dets` through
  `BallTracker` first; require `locked` + centre identity on 26068/26068
  frames or stop), `output/g3/e1..e7_diag.jsonl`. Base arm must reproduce T4
  (P 0.586 / R 0.607 / F1 0.597; the 5 far serves die at `3_candidate`).
  **KILLS:** (1) <4/5 dev far serves (f210/880/2154/3038/4770) have ≥5 far-band
  sightings in [c, c+0.5 s] → the far flight is undetected and the lever flips
  to detection (targeted far-flight mining for v4, not a general v4); (2) no
  empty gap on dev, or gap ratio <1.5×; (3) any fire on e1–e7 (all entreno
  serves are near-side); (4) match P9–P33 with L* frozen: must fire in ≥9/12
  far-serve windows before the pass-2 reception, and precision ≥0.75 over all
  new-rally fires (fires on the 7 owner-FALSE serve frames / 4 OFFGAME ranges
  are FPs). No `PlayerTracker` is created ⇒ no `cv2.setRNGSeed` needed.
- **S2 (OWNER-GATED, only if S1 survives) —** new contact band in
  `src/recognition/action_classifier.py` next to `_reentry_contact`, config key
  + drift-guard rows. Gates: dev recall ≥0.714 (+3/28) with precision ≥0.586;
  e1–e7 byte-identical (`scripts/compare_runs.py`, baselines from untouched
  HEAD, `--device cpu`); match action-set diff = additions at fire frames only;
  pass-2 chain holds (17/17 owner verdicts, 31/33 points); ≥9/12 held-out far
  serves within tolerance vs the S0 GT. Refuted ⇒ `git checkout 185c6f0 --
  src/ tests/test_config_drift.py` and the band moves to a default-off
  `scripts/*_harness.py` subclass (T5/R1 precedent).
- **S3 (worker) — [#49 DONE 2026-10-01] pass-2 squad/side-switch layer (open point 21.4):** squad = side ×
  switch parity (beach rule: switch every 7 points), cross-checked by all four
  players crossing the net in dead time; target exactly the 4 GT switches
  (after P7/14/21/28). SHIPPED: derived `[7,14,21,28]` exact; `pass2_squad`
  on 207/207 actions; **G1 team 0.518 → 0.755 squad-mapped** (the raw number
  was a side-vs-squad confound), 34 genuine side errors; player-crossing
  evidence-only. Deterministic pass-2, independent of S1. Consume in S4.
- **S4 — 21.3 winner/outcome layer → 13 (ace / serve fault / assist) → fantasy
  module + points table (14e)**, consuming `actions_pass2` after S1–S3 so aces,
  faults and receptions hang on real serve contacts. **21.3 DONE (#43)** as a
  pass-2 script: `scripts/resolve_point_winners.py` + `tests/test_point_winners.py`
  + `docs/point_winner_layer.md` — 33/33 decided, **18/33 (54.5%)** vs the 33
  dictated winners; miss sources = terminal-touch attribution (8, point 22),
  ball-death in/out (3), serve-team overrides (3); GT-bought 21/33 explicitly
  not inherited. The remaining S4 work (13 ace/fault/assist + fantasy module)
  still waits on S1–S3 for real serve contacts and squad letters.
- **Round-3 owner queue (no code, unchanged):** P32's serve, 6928A's verdict,
  P18–P20 anchors, ep45's nature, P23 17159A + P31 22873A team-fix
  confirmation — each flips one flag in `serve_relabel.json` when ratified.
- **Queued behind S1:** the reach-gate bucket (5/28: P5 f2575, P7
  f3747/3782/3950/4002 — near-side, so tracking diagnosis BEFORE any
  normalisation); the label bucket (4/28, 3 of them overpass — cf. open point
  9); e4/e5/e6 re-adjudication sheets; the e2 production-vs-script F1 gap
  (0.400 vs the 0.571 script record, pre-existing, f167 gesture flip).
- **DEFERRED, each with an explicit trigger (do not start earlier):**
  detector v4 → second-venue footage exists OR S1 kill 1 fires; T9 PTS time
  windows → mandatory before any footage outside 25–31 fps; T7 perturbation
  suite / T10 camera profile → before a second camera; T6 feature sidecar →
  when T12 fires (`--diag-dump` covers every probe until then); T8 width-band
  `unreliable` state → prerequisite for any departure-gate (R1) revisit, its
  "team overrides" motivation RE-SCOPED (see Learnings); T12 learned
  contact/gesture head → only when contact GT spans ≥3 recording sessions,
  validated leave-one-SESSION-out (e1–e7 = one fold); R2 calibrated confidence
  (REFUTED at diagnosis, 41st session) → parked behind its owner-gated
  preconditions (`docs/g3_r2_confidence_calibration.md` §6; S0 supplies
  precondition 1). `track_frac_15f` remains the one within-clip-stable ordinal
  (review-UI flag candidate, not a calibrated replacement).

## Open points

Ranked backlog. One compact entry per point: current status, the problem,
the next step. Numbers are stable across reorganizations — reference them
("point 22") in sessions and commits. Full per-point histories: grep the
point number in `docs/history/`.

### Active

22. **Far-side serves** — **[#53 SOLVED AS EVIDENCE: 14/17 at ZERO false
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

## Session index (one line each)
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