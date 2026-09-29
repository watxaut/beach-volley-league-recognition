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

**Last updated:** 2026-09-28 (thirtieth session — documentation-only action
reliability assessment: `docs/202609-28-astra-fix-pipeline.md`, revised to
incorporate the companion proposal in
`docs/20260928-space-bunny-fix-pipeline.md` (cheap portability mechanisms:
calibration/readiness loudness, perturbation gate, per-video camera profile in
the existing calibration artifact, adaptive width split, scale/fps/time
normalization, dimensionless motion features, conditional learned head — with
fact-check corrections: width bands misattribute rather than abstain,
frame-count constants are fps-dependent, ground-homography metres are relative
proxies, median-scale ≠ guaranteed parity, synthetic warps ≠ new viewpoints).
Proposed held-out benchmark → evidence sidecar → multi-signal contact proposals
→ small temporal learner → GT-free interpretation/review. Pending owner
approval; no code, config, model, GT, or runtime changes; no tests/video runs.)

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

**Action-reliability track (session 31):** executable plan derived from the
astra assessment lives in `docs/action_reliability_plan.md` (tasks T1–T15,
status per task). Dev clip = `video_ari_joan_8_first_points.mp4` (had NO
calibration → court signals silently dropped); T1 readiness report DONE
(uncommitted, reviewed); next = T2 dev-clip GT.

**Active next (ranked, goal-driven — see North-star).** (1) **21.3 point
winner/outcome layer** — G1's biggest missing signal; the anchored map +
serve resolutions now give TRUE windows with openers to validate against
the 33 dictated winners. (2) Round-3 owner queue (no code): P32's serve
verdict, 6928A's verdict, P18-P20 anchors, ep45's nature, P23 17159A +
P31 22873A team-fix confirmation — each flips one flag in
`serve_relabel.json` when ratified. (3) Fantasy scoring module + web
points table (14e); assist ships with it (no perception needed) — the
pass-2 `actions_pass2` stream is the intended input. (4) P15-class
targeted window re-decode escalation (raw detector settings, bounded +
logged) — only if a missing serve (P5/P7 class) needs the perception
back. (5) e4/e5/e6 re-adjudication sheets.

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

- Calibration `frame_dimensions` is (h,w) and is NOT a scale hint: points are used verbatim, only the court mask is sized from it — a smaller calibration on a bigger video silently drops near-half players. `src/main.py` now hard-errors on missing/mismatched calibration (`--allow-uncalibrated` to waive; T1, session 31). Probe scripts (`scripts/test_action_recognition.py`) bypass this check.

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
