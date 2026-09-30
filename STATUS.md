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

**Last updated:** 2026-09-30 (forty-second session — **architect strategy
review of the "detector v4 → normalise → learned gestures" generalization
proposal; docs-only, NO `src/` change (`src/` still exactly `185c6f0`),
suite 755.** The proposed order is NOT adopted — each step conflicts with a
measurement already in the repo: detection loses 0/28 dev contacts (the
detector fires at conf 0.74–0.87 at all 5 lost serves); R1 was already
width-normalised and died on the held-out match (a far serve travels along
the camera axis, so its image-plane speed is small in any unit); labelled
contacts total 91 (63 entreno = ONE session + 28 dev) and R2's
leave-one-clip-out already showed pooled AUC 0.172 vs 0.551 (dev correct
rate 0.276 vs entreno 0.56–1.00); the largest dev loss is contact PROPOSAL
(6 candidate + 5 reach gate = 11/28), not the gesture label (4/28). NEW
FINDING (`output/serve_relabel.json` vs dev GT, P1–P8): the pass-2
far-serve census "8/8" is POINT-level bookkeeping — at CONTACT level it is
**0/5**: the relabeled serves sit at f247/930/2195/3070/4801 vs GT serves
f210/880/2154/3038/4770 (31–50 f late, outside ±15 f); three (247, 3070,
4801) are the GT receptions (245, 3071, 4800) turned into serves, the other
two (930, 2195) are dev in-point-spurious digs. The far-serve CONTACT is the
gap G3 and G1 share. New plan **S0–S4** in *Active next* (first mechanism =
S1, a diagnose-only far-serve looming probe, kill criteria pre-registered);
proposed `AGENTS.md` wording is in the Log and awaits owner ratification.)

**Previous (forty-first session — **G3 R1 departure
gate: implemented, fully validated, REFUTED on the held-out match — NOT
shipped.** The owner-approved mechanism (session 40 task2, found
uncommitted after that session died mid-run) was finished by a delegated
worker and coordinator-verified against raw artifacts. Gates (`--device
cpu`): entreno 6/7 byte-identical + **e4 0.933→1.000** (its offline-flagged
FP f388 removed; zero correct actions lost anywhere); dev contact **P
0.586→0.739, R 0.607 unchanged, F1 0.597→0.667** — exactly the 6
offline-flagged FPs removed, 0 additions; match arms (same code,
yaml-only `contact_min_departure_bw` 0 vs 0.3): **bw0 ≡ production**
(207/207 action-set identical to the posegate run; pass-2 reproduces 8/8
far census, 31 serve-typed, 17/17 owner verdicts, 31/33 points) but
**bw03 REFUTES: 22 removals incl. P11's owner-confirmed serve f7132
(0.285 bw/f), 6928A and P11's rally cluster → 17/17 verdicts broken,
points 31/33→28/33, far census 8/8→7/8** → STOP per spec, no threshold
tuning. Root: width-normalised departure conflates dead balls with far
float serves (T5 physics). Owner decision = option (a): `src/` restored
to exactly `185c6f0`, mechanism PARKED reproducible scripts-side
(`scripts/departure_gate_harness.py` verbatim helper + `action_evidence.py`
+ `probe_departure_removals.py`/`probe_owner_verdicts.py`; banner +
tables in `docs/g3_r1_departure_gate.md`). Suite **755**. Revisit only as
a width-band-aware mechanism after T8. Same-session R2 DIAGNOSIS (negative
result, no `src/` change): the planned calibrated confidence (continuity ×
gesture tier, leave-one-clip-out) is REFUTED at diagnosis — pooled AUC
0.172 vs 0.551 for the emitted hand-set constant, no variant wins; the
gesture tier reverses across clips (clip-type-driven) and fold base rates
anti-correlate with held-out rates. Motivation STANDS: hand-set constants
uncalibrated (ECE 0.154/0.164) and the `action_confidence=0.3` emission
filter is INERT (min emitted constant 0.45 — it never rejects anything).
Doc: `docs/g3_r2_confidence_calibration.md` (revival preconditions are
owner-gated: match-side per-prediction labels + clip-type-aware base
rates).)

**Previous (fortieth session — **G3 per-action evidence
diagnosis, diagnose only, NO `src/` change.** Owner added **G3 (action
accuracy) as the top goal**. `scripts/action_evidence.py` labels every
emitted action on dev + e1–e7 (85 predictions) against GT via
`evaluate_timed`'s matcher and joins already-computed features:
**54 correct / 11 wrong_label / 5 wrong_team / 1 both / 1 dup / 13 FP**
(dev alone 8/29 correct). The hand-set gesture `confidence` is
UNCALIBRATED (0.75→4/8 correct, 0.6→16/20, 0.55→23/37, 0.45→0/3).
Strongest signal: **post-contact departure in ball-widths/frame** over
the CONTACT_DELAY window — 6/14 FPs ≤0.198 bw/f, every correct action
≥0.423 bw/f (×2.1 empty gap; raw px/f only ×1.26 and far-biased). Ball
continuity (`track_frac_15f`) is the only monotone signal without a
per-clip reversal. Doc: `docs/g3_action_evidence.md`. Next = owner
approval of R1 (departure gate) — see Active next.)

**Previous (thirty-ninth session — **T5 revert/cleanup,
docs+tests only, NO production change**: the reviewer ruled that both T5
mechanisms (A weak 3 px/f tier, B backfill on a fresh lock) recover **0/5**
far serves and therefore must not live in `src/`. `src/` is restored exactly
to `185c6f0` — `git diff 185c6f0 -- src/` is EMPTY, the `ball_weak_*` /
`ball_backfill_*` DEFAULT_CONFIG keys and their config-drift rows are gone.
The mechanisms now live ONLY in the probe harness,
`scripts/serve_mechanism_harness.py`, as default-off subclasses of
`BallTracker` / `ActionClassifier`, so `scripts/probe_serve_mechanisms.py`
still reproduces `docs/t5_mechanism_ab.md` **byte-for-byte** (base 36/13/0,
A 37/14/19, B 37/14/0, 0/5 recovered, base fidelity 4968/4968). **T5
far-serve admission is REFUTED at the tracker level.** The root blocker is the
CONTACT PROBE's serve-branch geometry — it demands a FED ascent (|vin3| ≥
|vin6|+10, the e7 f25 pattern) while the far toss is a DECELERATING float —
plus **no toss detection at all** on P4/P6/P8; both are recognition/detection
work and need an **owner decision**.

**Previous (thirty-eighth session — action-reliability T5 step 2 DONE: the
approved mechanism is **REFUTED as a recovery**, and the real blocker is
elsewhere. A (weak 3 px/f tier) and B (backfill on a
fresh lock) were both implemented default-OFF and replayed through the
PRODUCTION classes (`scripts/probe_serve_mechanisms.py`; the base arm
reproduces the dumped production track on 4968/4968 frames): **both
recover 0/5 far serves**. A costs 19 new bootstrap locks for that zero;
B costs none, adds one dead-time candidate, and **does fix the
step-1 evidence gap** — the probe's `no_ball_sighting` rejections at
the 5 far serves fall 23/27/20/21/21 → 16/20/19/20/18 of 31 window
frames (confirmed end-to-end: the dev waterfall's only change is those
five detail strings; the pipeline output stays byte-identical). The loss
then moves to `no_contact_geometry`: with the full toss in the history
the far serve's contact measures vin=(0.8,0.7) vout=(6.5,-11.3) and the
probe's serve branch demands a FED ascent (|vin3| ≥ |vin6|+10, the e7
f25 pattern) while the far toss is a DECELERATING float; a hypothetical
float-serve signature would reach at most 2/5 (P4/P6/P8 have NO toss
detection to backfill). **(SUPERSEDED the same day by session 39: B is no
longer "shipped DEFAULT OFF" — neither mechanism is shipped at all; `src/`
is back at `185c6f0` and both live in the probe harness only.)**
Entreno e1–e7 byte-identical in both arms; dev evaluate_timed unchanged (F1 0.597).
+28 tests, suite 736.

**Previous (thirty-seventh session — action-reliability T5
DECIDED + step 1 DONE (diagnose only). **Owner APPROVED the T5 mechanism
(2026-09-29): serve-time ball-track (re-)admission** — extend the UNLOCKED
bootstrap so the far-side toss can lock below `lock_min_speed = 8 px/f`; NOT
time windows, NOT the width-split `unreliable` state. Step 1 measured it
offline: `scripts/probe_serve_admission.py` (new, reads the T4
`--diag-dump`, replays the bootstrap decision over the whole clip — baseline
replay reproduces the dumped `locked` flag on 4966/4968 frames) +
`docs/t5_serve_admission_diagnosis.md`. FINDINGS: **all 5 stage-3 serve deaths
are FAR-side serves** (toss ball 13-17 px wide, median pre-contact rise
1.6-6.7 px/f; the 3 surviving serves are near-side, 46-53 px, 7-17 px/f, locked
at contact); the failing condition is `speed_below_lock_min_speed`; a 3 px/f
weak tier recovers **5/5** at lock latency 0 (>= 20/31 window frames owned) for
~12 extra bootstrap locks per 4968 frames, and no candidate-geometry
discriminator removes them (ascending-only LOSES 2 serves). Entreno contrast:
every surviving serve there is near-side (e3 f29, e7 f22), so the entreno gate
has little power over this mechanism. Also **owner RATIFIED the P6 f3131
set->overpass reading** ("it's an overpass"): `scripts/build_dev_clip_gt.py`
gained a generic `OWNER_RATIFICATIONS` table and the GT flag now carries
`owner_ratified/date/statement`. +23 tests, suite 708.)

**Previous (thirty-sixth session — action-reliability T4 DONE:
loss waterfall on the dev clip. `--diag-dump` writes a per-frame JSONL of what
each stage already computed, from inside the shared `FrameProcessor.process_frame`
(`src/utils/diagnostics.py`; `if self.diag_enabled:` guards, default OFF, config
key `diag_dump` + config-drift guard extension); `scripts/waterfall.py` walks the
7-stage chain per GT contact and imports the T3 matcher so the two agree;
`scripts/compare_runs.py` is the byte-identity gate helper. BASELINE (first
dev-clip run ever, `--device cpu`): contact P 0.586 / R 0.607 / F1 0.597, class
0.706, team 0.706, 1 dup, 2.703 FP/dead-min, points 6/2/0 mean IoU 0.707.
WATERFALL: detection 0, admission 0, candidate 6, gate 5 (all reach), actor/team 5
(4 = post-P7 side switch), label 4, survives 8; FPs 8 in-point / 3 dead-time /
1 dup. FINDING: 5 of the 6 candidate deaths are serves where the detector DOES
see the ball (conf 0.74-0.87) and the tracker says `unlocked_no_motion` on
19-25 of 31 window frames — a toss apex slower than `lock_min_speed = 8 px/f`
cannot re-lock. T5 next: ONE mechanism, ball-tracker serve admission. Gates:
hooks-off == pre-change HEAD byte-identical on dev + e3 + e1, hooks-on ==
hooks-off byte-identical, +37 tests, suite 685. Table:
`docs/t4_loss_waterfall_dev_clip.md`.)

**Previous (thirty-first session — action-reliability T3 DONE:
`scripts/evaluate_timed.py`, the TIME-MATCHED evaluator (a sibling of
`evaluate.py`, which is untouched). One-to-one optimal assignment on time
distance, tolerance `max(0.2 s, GT frame_tolerance/fps)`, per-frame PTS when
the blob carries one else `frame/fps` (reported, no decode); SEPARATE scores —
class-agnostic contact P/R/F1, class accuracy + confusion matrix, team, actor,
duplicates, FP per dead-time minute, point intervals by temporal IoU.
`--autonomous` refuses a prediction file carrying GT-derived inputs (winners,
serve anchors, owner pins/verdicts, the map/re-label layers). +23 tests,
suite 648. Gate: entreno contact F1 e1 .941 e2 .857 e3 .929 e4 1.0 e5 1.0
e6 .933 e7 .750; at `evaluate.py`'s effective ±15f window the two agree
exactly and the ORDERING is preserved. No dev-clip prediction output exists,
so no dev-clip run. T4 next.)

**Last implementation update:** 2026-09-28 (twenty-eighth session — POINT 22 MECHANISM
3 SHIPPED: `scripts/relabel_serves.py` (+29 tests) — the pass-2 serve
re-labeling layer ratified in #27. The rally-opening contact of each TRUE
map window is re-labeled serve by structural prior: touch t1 + dead-ball
gap in the MEASURED chasm (openers ≥153f vs mid-rally ≤134f; threshold
143 = midpoint) + window-opening position; owner anchors outrank a
rejected opener (anchor_only), owner TRACKED/MISCLASSIFIED verdicts
outrank the gap veto and the fault-description guard, P20 is owner-pinned
to 14516A (round-2 q5), P32 stays report_only (fault desc contradicted by
a full post-serve rally, no owner verdict). Owner FALSE/OFFGAME serves
demoted (1039, 2414, 3595, 3856, 5130, 14387); 6928 reported-only (no
owner verdict). GATES: far prefix census **2/8 → 8/8** (target ≥6/8 ✓);
serve-typed actions **20 → 31** (−6 demoted +17 relabeled; ~28 sanity
anchor overshot because 30/33 points now hold an in-stream serve action —
every one mapped to a distinct point, 6928 included, pending owner
arbitration); ALL 17 owner round-1+2 verdicts reproduced mechanically
(P9-P12 at the exact contact frames); 13 team overrides flagged (the
far-side width-band class + P24's mirror). Entreno neutrality BY
CONSTRUCTION (zero src/ changes — only the new script + tests). Suite
**554** (+29).)

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
Next = the far-side serve follow-up is now decided by the 42nd-session
architect review: option (c) "park at pass-2" is REJECTED (pass-2 is 0/5 at
contact level — point 22), (a)/(b) are replaced by ONE diagnose-only probe
first (S1, looming onset — post-contact flight exists at all 5 dev serves
while the toss exists at only ~2/5). See *Active next* S0–S4.

**Active next (ranked, goal-driven - see North-star; G3 first) — RE-RANKED by
the 42nd-session architect review (Log #42).** The "detector v4 → normalise →
learned gestures" order was NOT adopted. Order = measure in-domain → fix the
contact proposal where the loss is → pass-2 layers on real contacts → learn
last. One mechanism per session; each step's kill criteria are pre-registered.

- **S0 (OWNER, async, no code) — held-out contact GT for match P9–P33** in the
  P1–P8 dictation format (`ground_truth/20260920_match_ari_joan_contacts_p1_p8.txt`;
  ~90 contacts, 12 of them far-serve points). It is the held-out set for every
  perception mechanism below AND R2's precondition 1 (match-side labels);
  until it lands, held-out checks are a point-level proxy (open point 24).
  Same lane: pin the capture spec (30 fps, 1080p, long-axis, fixed height) in
  `docs/video_recording_guide.md` — controlling the input domain is the
  cheapest generalization lever; 59.8 fps `video_david` is the first
  out-of-spec file.
- **S0b (worker, script only) —** score `actions_pass2` (`output/serve_relabel.json`)
  at CONTACT level against the dev GT P1–P8 with `scripts/evaluate_timed.py`
  (NOT `--autonomous`: pass-2 carries owner inputs) and record it. Expected
  from the hand check: far serves 0/5.
- **S1 (diagnose only, no `src/`) — far-side serve looming probe:**
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
- **S3 — pass-2 squad/side-switch layer (open point 21.4):** squad = side ×
  switch parity (beach rule: switch every 7 points), cross-checked by all four
  players crossing the net in dead time; target exactly the 4 GT switches
  (after P7/14/21/28). Should fix 4 of the 5 dev stage-5 team errors (all P8).
  Deterministic pass-2, independent of S1.
- **S4 — 21.3 winner/outcome layer → 13 (ace / serve fault / assist) → fantasy
  module + points table (14e)**, consuming `actions_pass2` after S1–S3 so aces,
  faults and receptions hang on real serve contacts. (Untracked
  `scripts/resolve_point_winners.py` + `tests/test_point_winners.py` are in the
  tree — not part of the 42nd-session review; the next session that touches
  21.3 must decide their status.)
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

22. **Far-side serves** — **[#42 RE-SCOPE] POINT-level DONE, CONTACT-level
    OPEN.** Measured 09-30 (`output/serve_relabel.json` vs dev GT P1–P8):
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
    winners; feeds aces (13). (4) *Side-switch layer:* persistent
    all-player side flip between points (majority + serve-side evidence),
    cross-checked vs score expectation; ALL team fields become squad
    identity; overlay labels must swap; target = exactly the 4 GT switches
    after points 7/14/21/28. (5) *Persistent player numbers:* GT pass
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

24. **Match-domain contact GT + contact-level scoring of pass-2 (new, #42)** —
    **Status: OPEN, owner-gated.** Problem: every perception mechanism this
    project has refuted (T5, R1, R2) died on a held-out MATCH check that only
    existed as proxies (17 owner verdicts, point counts, 33 winners); labelled
    contacts are 91 total (63 entreno = one session, 28 dev = match P1–P8),
    dev correct rate 0.276 vs entreno 0.56–1.00, so entreno cannot stand in
    for match performance, and pass-2's point-level census hid a 0/5
    contact-level result (point 22). Next: (a) OWNER dictates contacts for
    P9–P33 (S0; ~90 contacts, 12 far-serve points; folded by
    `scripts/build_dev_clip_gt.py`-style tooling into a match GT); (b) S0b
    contact-level score of `actions_pass2` on P1–P8 via `evaluate_timed.py`;
    (c) from then on every pass-2 layer is scored at contact level, and any
    threshold fit on dev P1–P8 must hold on P9–P33 before it ships. The
    dictated anchors are too coarse for contact timing (P8 anchor f4700 vs GT
    serve f4770), so they cannot substitute. Also feeds R2 precondition 1.

### Parked / conditional

5.  **Same-team adjacent-player choice.** The team filter constrains the
    TEAM, not which teammate — e3 f69's dig goes to the wrong B player.
    Needs pose/reach signals, not team logic.

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
- Recorded action F1s REQUIRE `evaluate --ignore-player`: GT player_id is
  a per-frame L-R index; with player matching on, IDENTICAL streams score
  0.933 vs 0.133. GT id conventions: e1/e3 = L-R indices, e4/e5 =
  canonical ids.
- The scorer merges GT `overrides` before matching — ratified corrections
  must be visible to eval.
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
- Entreno e1–e7 are ONE recording session: a regression / byte-identity
  suite, not a match-domain validation set (held-out correct rate dev 0.276
  vs entreno 0.56–1.00; the R2 gesture tier reverses dev↔entreno). A leave-one-
  clip-out over them is one fold. Labelled contacts: 91 = 63 entreno + 28 dev
  (the "207 match actions" are PREDICTIONS, not labels). Session 42.
- Dev loss budget (28 GT contacts, T4): proposal 11 (6 candidate + 5 reach
  gate) > team/actor 5 (4 = post-P7 side switch) > label 4 > survives 8;
  detection 0. The gesture label is the SMALLEST bucket, so a learned
  gesture head cannot move G3 by itself. Session 42.
- Device caveat: MPS jitter can flip a gesture label (e.g. e6 f309
  block vs spike); the script path (deterministic) is the reference.

**GT conventions (owner-ratified)**
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

Details: `docs/history/status_where_we_are_archive.md` (per-session state
summaries) + `docs/history/status_log_archive.md` (detailed entries,
2026-08-14 → 2026-09-26). The last ~3 sessions keep full Log entries below.

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
