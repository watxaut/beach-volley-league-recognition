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

**Last updated:** 2026-09-27 (twenty-fourth session — product NORTH-STAR
GOALS set (G1 Fantasy scoring, G2 individual stats) with a stat-by-stat
coverage audit and critical paths; no pipeline code touched. Pose gates
from #23 remain the last shipped mechanism.)

## North-star goals (set session 24)

Why this project exists — a service for the owner's beach-volley club:
record a session, process it, deliver two things. New mechanisms should
trace to a goal; when prioritizing, the critical paths below decide.

**G1 — Fantasy scoring.** Per point, per player:
Kill +1 (unreturnable attack) · Block +1 (defensive stop at the net) ·
Ace +1 (unreturned serve) · Dig +1 (retrieving an attacked ball) ·
Assist +0.5–1 (setting a teammate for a kill) · Error −1 (attack out,
service fault, ball-handling error).

**G2 — Individual statistics.** Per-player understanding of your game
(kill%, dig%, zones, placement, tendencies), aggregated across sessions
via player labels.

**Stat coverage audit (2026-09-27):**
- Kill — DONE: spike outcome `kill` (semantics ratified 08-31).
- Dig — DONE: `dig` action.
- Block — DONE: block action + kill_block/soft_block classification.
- Error (attack) — DONE: spike outcome `out`.
- Assist — DERIVABLE NOW, metric unbuilt: set → same-team spike with
  outcome `kill` in the same point (actions×spikes join). The +0.5 vs +1
  split (e.g. direct set vs overpass/second-ball) is a product decision.
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

**Production state (as of 2026-09-27).**

- **Weights:** `models/volleyball_ball_best.pt` = **v3** (fine-tuned FROM
  best.pt on 1091 + 350 rebalanced frames; ADOPTED 2026-09-26 after the
  four-leg gate; old weights stashed as `*_v1_entreno.pt` / `*_v2_match.pt`).
  Sub-1080p ingest upscales once to `_up1080.mp4`. Pose gating is live in
  the shared `classify_actions` path.
- **Match (20260920 — the only real match):** **31/33 GT points confirmed
  (0.939)**, first-confirmed at GT point 1, 57 episodes (26 starved);
  actions 207 (dig 84 / spike 45 / set 42 / serve 20 / overpass 9 /
  block 7); perf **68.0 ms/frame** (14.7 fps, 30.5 min) after the pose
  gates (was 84.8). All data CSVs byte-identical through the last two
  shipped mechanisms.
- **Entreno gate record** (`evaluate --ignore-player` F1): e1 0.706, e2
  0.571, e3 1.0, e4 0.933, e5 0.923, e6 0.933, e7 0.75; teams 1.0 except
  e6 0.857. Suite **477 green**.
- **Known residuals:** e4/e5/e6 GT re-adjudication vs the v3 streams
  (queued — owner-ratified contact sheets; GT was dictated against
  base-model behavior); e3 f539 outcome enrichment reads dug vs GT kill
  (tracker-side fast-fall conf dip — open point 22 family); match serves
  emitted 20 vs v2's 28 (open point 22); live-debug display decoupling
  parked (open point 23).

**Active next (ranked, goal-driven — see North-star).** (1) Open point
22: build the episode→GT-point ORDER map (57 episodes ↔ 33 points), then
the far/near serve census on TRUE windows — serves both goals (serve
emission feeds aces/errors; the episode map is the backbone of per-point
fantasy lines). (2) e4/e5/e6 re-adjudication sheets. (3) 21.3 point
winner/outcome layer — G1's biggest missing signal (unlocks aces, serve
errors, per-point grouping). (4) Fantasy scoring module + web points
table (14e); assist ships with it (no perception needed).

## Open points

Ranked backlog. One compact entry per point: current status, the problem,
the next step. Numbers are stable across reorganizations — reference them
("point 22") in sessions and commits. Full per-point histories: grep the
point number in `docs/history/`.

### Active

22. **Far-side serves** (owner feedback at v3 adoption: match far-side
    serves seem untracked; entreno serves track fine). **Status: SCOPED
    (09-27); one measurement RETRACTED, one SOLID specimen.** Serve
    team/side derivable mechanically → 16 far / 16 near
    (`scripts/derive_match_serve_windows.py`, +17 tests). Retraction: a
    first "measurement" paired the ENTRENO game-state anchor file with the
    match — fictional windows (README warns; tests use synthetic anchors).
    Corrected specimen (production-parity probe, continuous f0..6948 dump):
    P2's far-side serve IS tracked END-TO-END by the ball tracker (toss
    f889 → lock f890 → ~65/72 frames REAL through apex/descent/bounce/
    roll, conf 0.24–0.90) — the owner-visible loss is game_on firing 36f
    late (f925), the episode STARVED (point unconfirmed) and NO serve
    action emitted → the loss is the game-state episode/confirmation +
    rally-opening serve-ACTION gate (15a machinery), NOT ball tracking.
    Same family, diagnosed unfixed: v3's conf dip on a FAST-FALLING ball
    (e3 f613-618) lets the coast leave the court-bounds box, the re-entry
    window rejects the falling dets, the track dies (this is why e3 f539's
    outcome reads dug vs GT kill). **Next (one mechanism):** the
    episode→GT-point order map (57 episodes ↔ 33 points + non-point
    bursts, keyed by derived serve team/side + descriptions), then the
    far/near census + probe verdicts on TRUE windows; owner-ratified
    anchors welcome but not blocking. Tracker-side levers if needed:
    round-3 fast-fall/toss mining, re-entry-window retune (match-wide
    risk, own gate). Watch: v3 serves 20 vs v2 28. **Infra rule: VFR file
    — never CAP_PROP_POS_FRAMES seeks; decode sequentially.**

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

23. **Live-debug producer/consumer display decoupling** (parked 09-27;
    owner's call). `--debug-live` serializes pipeline + render + 33 ms
    pacing (~5-7 fps pre-gates). Design: a producer thread runs the EXACT
    `FrameProcessor.process_frame` loop in frame order (the pipeline path
    is untouched — the parity rule is about the pipeline), a consumer
    thread renders cached overlays and owns pacing; expected ≈ 1000/68 ≈
    15-20 fps live. Buys live fps only — batch is at the detector floor
    (two YOLO imgsz-1280 calls ≈ 48 ms/f) unless a future session takes
    on model fusion / imgsz changes (behavior changes → full gate).

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

Protocol rules live in **AGENTS.md** (entreno validation, live-debug
parity, diagnose-first, byte-identical A/B, `cv2.setRNGSeed(0)` per
tracker in multi-tracker harnesses). The distilled technical facts below
survive across sessions; provenance in the archives.

**Measurement & eval conventions**
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

## Session index (one line each)

Details: `docs/history/status_where_we_are_archive.md` (per-session state
summaries) + `docs/history/status_log_archive.md` (detailed entries,
2026-08-14 → 2026-09-26). The last ~3 sessions keep full Log entries below.

- 2026-09-27 **#24** — product north-star goals set (G1 Fantasy scoring / G2 individual stats); stat-coverage audit + critical paths (Log below).
- 2026-09-27 **#23** — pose gating shipped in the shared classifier (staleness + near-ball trail), byte-identical everywhere, match ×1.24 (Log below).
- 2026-09-27 **#22** — far-side serves scoped: retracted mispaired-anchor measurement; P2 specimen (ball tracked; loss = episode starvation + serve-action gate); `derive_match_serve_windows.py`.
- 2026-09-27 **#21** — pi repo default model → zai/glm-5.3-flash (Log below).
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

### 2026-09-27 (twenty-fourth session) — product north-star goals set (G1 Fantasy, G2 stats); critical paths mapped, no pipeline code

- Owner restated the product intent for the club service: (1) Fantasy-
  style scoring per point per player (Kill/Block/Ace/Dig +1, Assist
  +0.5–1, Error −1) over recorded sessions; (2) individual per-player
  statistics. Both now live as the North-star section at the top of
  STATUS; future prioritization traces to them.
- Mechanism-level coverage audit (recorded in the North-star section):
  Kill/Dig/Block/attack-Error already derivable from the DB; Assist is
  one join away (set → same-team kill, same point) — pure metric work;
  the real G1 blockers are the point winner/outcome layer (21.3),
  far-side serve emission (22), the per-point×player scoring module +
  web points table (14e), and attribution robustness (2/21.4/21.5).
  Ball-handling errors ruled a manual-review path, not perception.
- Ranking unchanged at #1 (22 serves both goals); 21.3 promoted above
  the rest of 21's frontier. Session #20's Log entry archived verbatim
  (live Log trimmed back to 3).

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

### 2026-09-27 (twenty-first session) — pi project default model set to zai/glm-5.3-flash (.pi/settings.json)
- **Harness config only** — no pipeline code, no GT. New
  `.pi/settings.json` sets `defaultProvider: zai` + `defaultModel:
  glm-5.3-flash`, overriding the user-level `~/.pi/agent/settings.json`
  (`zai/glm-5.3`) inside this repo only. Cross-checked before writing:
  `zai/glm-5.3-flash` was already in the user settings' `enabledModels`,
  and `~/.pi/agent/auth.json` authenticates `zai`, so no provider setup
  was needed. Rest of `.pi/` (prompts/) untouched. Running pi sessions
  need `/reload` or a restart to pick it up.

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
