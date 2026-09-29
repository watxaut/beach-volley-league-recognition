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

**Last updated:** 2026-09-29 (thirty-eighth session — action-reliability T5
step 2 DONE: the approved mechanism is **REFUTED as a recovery**, and the
real blocker is elsewhere. A (weak 3 px/f tier) and B (backfill on a
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
detection to backfill). **So: B ships DEFAULT OFF** (`ball_backfill_lookback
= 0`, keys in DEFAULT_CONFIG + ctor defaults + drift guard), A is kept
off-by-default only so the A/B stays reproducible. Entreno e1–e7
byte-identical in both arms; dev evaluate_timed unchanged (F1 0.597).
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
|vin6|+10; the far toss is a decelerating float), not ball-track admission —
a recognition mechanism that needs owner approval. B therefore ships **default
OFF** behind `ball_backfill_lookback` (evidence in
`docs/t5_serve_admission_diagnosis.md` step-2 section,
`docs/t5_mechanism_ab.md`, `docs/t4_loss_waterfall_dev_clip.md` "After T5").
Next = **owner decision on the far-side serve follow-up**: (a) contact-probe
serve signature that does not require a fed ascent + (b) detection evidence on
the far toss (P4/P6/P8 have none), or (c) park the far-side serve at the
pass-2 layer (point 22 mechanism 3 already relabels 8/8).

**Active next (ranked, goal-driven - see North-star).** (1) **Owner call on
the far-side serve follow-up** (T5 handed it back): the ball-track half is
built and available off (`ball_backfill_lookback`), the binding defect is the
contact probe's serve signature + the missing far-toss detections — a
recognition/detection mechanism, so it needs approval before code. (2) **21.3
point winner/outcome layer** - G1's biggest missing signal; the anchored map +
serve resolutions now give TRUE windows with openers to validate against the 33
dictiated winners. (3) Round-3 owner queue (no code): P32's serve verdict,
6928A's verdict, P18-P20 anchors, ep45's nature, P23 17159A + P31 22873A
team-fix confirmation - each flips one flag in `serve_relabel.json` when
ratified. (4) Fantasy scoring module + web points table (14e); assist ships
with it (no perception needed) - the pass-2 `actions_pass2` stream is the
intended input. (5) T6-T10 of the action-reliability plan (feature sidecar,
perturbation suite, width-band `unreliable` state, PTS time windows, camera
profile) - the evidence layer the next perception mechanism should be built
on. (6) e4/e5/e6 re-adjudication sheets; the e2 production-vs-script F1 gap
(0.400 vs the 0.571 script record, pre-existing, f167 gesture flip).

## Open points

Ranked backlog. One compact entry per point: current status, the problem,
the next step. Numbers are stable across reorganizations — reference them
("point 22") in sessions and commits. Full per-point histories: grep the
point number in `docs/history/`.

### Active

22. **Far-side serves** — **Status: MECHANISMS 1+2+3 DONE (mech 3 shipped
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

## Session index (one line each)

Details: `docs/history/status_where_we_are_archive.md` (per-session state
summaries) + `docs/history/status_log_archive.md` (detailed entries,
2026-08-14 → 2026-09-26). The last ~3 sessions keep full Log entries below.

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
- 2026-09-29 **#38** — T5 step 2: A (weak tier) vs B (backfill on a fresh lock) implemented default-OFF and replayed through the REAL `BallTracker` + `ActionClassifier` (`scripts/probe_serve_mechanisms.py`; base arm reproduces the dumped production track 4968/4968 frames). **BOTH recover 0/5 far serves**; A costs 19 new bootstrap locks, B none. B does close the step-1 evidence gap (`no_ball_sighting` 23/27/20/21/21 → 16/20/19/20/18 of 31 window frames; dev waterfall detail strings only, pipeline output byte-identical) and the loss moves to `no_contact_geometry`. Root cause of the residue: the contact probe's serve branch demands a FED ascent (|vin3| ≥ |vin6|+10, e7 f25) while the far toss is a DECELERATING float; and P4/P6/P8 have no toss detection at all to restore. Shipped DEFAULT OFF, +28 tests, suite 736 (Log below).
- A `--diag-dump` JSONL replays the PRODUCTION ball tracker exactly: feeding its `ball_dets` back into a real `BallTracker` (with the calibration's court bounds) reproduces `ball_track.locked` and every emitted centre on 4968/4968 dev-clip frames. Tracker/probe counterfactuals therefore need no re-implementation (`scripts/probe_serve_mechanisms.py`, session 38).
- Restoring the missing ball history is only half of a lost contact: the contact probe's own geometry can refuse it anyway. The far-side serve dies at `no_ball_sighting` (track) AND at `no_contact_geometry` (probe): a far toss is a DECELERATING float into the contact, while the probe's serve branch only accepts a FED ascent (|vin3| ≥ |vin6| + 10, the e7 f25 pattern). Session 38.
- `CONTACT_DELAY` bounds any lock-time backfill: the probe tests contact frame `c` exactly at `c + 7`, so a lock later than contact + 7 can never feed that contact (dev P2 locks at +10 f). Session 38.
- Concatenating the high-tier and low-tier bootstrap sighting windows mis-ages motion pairs (empty low-tier frames land between real high-tier ones and halve the measured speed); union them index-wise instead (`BallTracker._merge_history`). Session 38.
- The action-script record and the production path differ on e2 today: `scripts/test_action_recognition.py` measures F1 0.571 (spike at f167), `src.main` measures 0.400 (dig at f167 + 2 extra predictions). Pre-existing, not caused by session 38's change (its OFF run is byte-identical to the T4 HEAD baseline). Session 38.
- 2026-09-29 **#37** — T5 mechanism APPROVED by the owner (serve-time ball-track (re-)admission) + step 1 diagnosis ONLY (`scripts/probe_serve_admission.py` + `docs/t5_serve_admission_diagnosis.md`, no `src/` change): all 5 lost serves are far-side, the failing condition is `speed_below_lock_min_speed`, a 3 px/f weak tier recovers 5/5 at latency 0 for ~12 extra locks and no geometry gate removes them; owner RATIFIED the P6 f3131 overpass reading via a generic `OWNER_RATIFICATIONS` table in `scripts/build_dev_clip_gt.py`; +23 tests, suite 708 (Log below).
- 2026-09-29 **#36** — T4 loss waterfall SHIPPED: off-by-default `--diag-dump` capture in the shared frame path (`src/utils/diagnostics.py`) + `scripts/waterfall.py` + `scripts/compare_runs.py`; dev clip F1 0.597, 5 of 6 candidate deaths are serves lost to `unlocked_no_motion`; byte-identical on dev/e3/e1 with hooks off and on; +37 tests, suite 685 (Log below).
- 2026-09-29 **#35** — T3 time-matched evaluator SHIPPED: `scripts/evaluate_timed.py` (+23 tests, suite 648); optimal one-to-one assignment in seconds, PTS-aware time base, separate contact/class/team/actor scores + duplicates + FP-per-dead-minute + point IoU, `--autonomous` GT-input guard; entreno gate reproduces `evaluate.py`'s F1s at the same tolerance window.
- 2026-09-29 **#34** — T2 contact-GT code review fixed (3 defects: rally-global → per-possession `touch_number`, draft/suggested duplicates moved to `superseded_draft_events` (15 of them, `events` == the 28 owner contacts), cross-net set → `overpass` + `owner_interpretation_flag`); +9 tests, suite 625.
- 2026-09-29 **#33** — T2 contact-level GT wired: `scripts/build_dev_clip_gt.py` parses the owner's `20260920_match_ari_joan_contacts_p1_p8.txt` (28 contacts, P1–P8, coarse ±10–15f, side-switch after P7) and emits `video_ari_joan_8_first_points_annotations.json` with status OWNER_DICTATED, per-contact `frame_tolerance: 15`, owner track id/side/note kept raw; +6 parser tests, suite 612.
- 2026-09-29 **#32** — T2 dev-clip GT BUILT (REVIEW, not ratified): offset map (identity, residual 0.0 at start/mid/end), `scripts/build_dev_clip_gt.py` (+25 tests), DRAFT GT for P1–P8 (8 owner serve anchors + 15 flagged suggestions + missing/fault report), ratification sheets in `output/t2_contact_sheet/`; the side switch is after P7, not P3–P4.
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

**Shipped.** Mechanism B in `BallTracker` (`backfill_lookback` and friends) +
`ActionClassifier.add_ball_sightings` + the `FrameProcessor` wiring
(`update(..., frame_number=)`, `pop_backfill()`), all **DEFAULT OFF**
(`ball_backfill_lookback = 0`), causal (past frames only) and on the shared
frame path, so live-debug parity is untouched. Mechanism A
(`weak_min_speed`/`weak_max_width`) ships off-by-default, documented as
refuted, so the A/B stays reproducible. Config-drift guard extended.

**Owner hand-off:** the far-side serve needs (a) a contact-probe serve
signature that does not require a fed ascent and (b) detection evidence on the
far toss. Both are recognition/detection mechanisms, outside the approved T5
scope — decision needed before code.

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
