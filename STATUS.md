# STATUS.md — cross-session memory

**Convention (hard budgets, enforced by `tests/test_status_leanness.py` — added
2026-10-06):** Read this + `ground_truth/README.md` before planning any work;
update at the end of every session that changes anything and commit with the work.

- **Budgets:** ≤600 total lines; `## Where we are` ≤80; `## Active next` ≤25;
  each open point ONE compact entry (status/problem/next, ≤8 lines, collapsed
  `[UPDATE]` stacks); `## Learnings` ≤140; `## Session index` exactly one line
  per session (≤240 chars; longer stories go to the Log or `docs/`);
  `## Log` keeps the last 2-3 sessions; `## Next task cards` holds ONLY cards
  not yet DONE/REFUTED (a finished card is archived under its session date in
  `docs/history/status_log_archive.md`, then deleted from here).
- *Where we are* is REWRITTEN each session, never appended. When a budget is
  exceeded: move the verbatim text to `docs/history/status_log_archive.md`
  (old Where-we-are blocks → `status_where_we_are_archive.md`), then shrink —
  history is moved, never deleted.
- New durable protocol rules go in `AGENTS.md`; new cross-session technical
  facts go one-line-each into *Learnings* below.

Last updated: **2026-10-06 (86th session) — repo lean pass, merged with
the parallel identity sessions (#83–#85, PR #1).** Lean pass (no `src/`
change): STATUS compacted 2465 → ~530 lines per the budgets above (every
removed line verbatim in `docs/history/`); 21 closed-investigation test
files deleted (530 tests — suites whose subject is a DONE/REFUTED one-off
probe); leanness guard added; suite **1083** all green. Identity state =
#85 (side switches solved offline on the owner's match dump). Numbering:
#83–#85 = identity resolver sessions; this lean pass = #86.

## North-star goals (set session 24)

- **G1 — fantasy scoring per point/player** (ratified 09-27): Kill +1,
  Block +1 (kill_block +1 / soft_block 0), Ace +1, Dig +1, Assist +0.5 flat,
  Error −1 (attack out / service fault / ball handling).
- **G2 — individual stats** (kill%, dig%, zones, tendencies, multi-session
  via player labels): mostly built (player pages, heatmaps, splits); left =
  serve/assist/error stats, per-point views, confidence surfaces, multi-session UX.
- **G3 — ACTION ACCURACY = most important** (G1/G2 depend on it). Bar =
  `class_accuracy`; contact F1 is label-blind; label-only oracle is trivially 1.000.
- Stat coverage: kill/dig/block/attack-error DONE; assist derivable (set →
  same-team spike kill in the same point; metric unbuilt); ace + serve-error
  blocked on 21.3 + 22 (parked as 13); ball-handling error not perceptible →
  manual override in the review UI; point winner (21.3) groups the lines.
- Critical path: 22 → 21.3 → 13 → fantasy module from DB + points-table UI
  (14e). Rollout gate = 21.4/21.5 + fast human review.

## Where we are

Display/interpretation layers (all display-only or post-hoc; perception
byte-identical). **Identity (#85, side switches SOLVED offline on the
owner's match dump):** E1 enrollment (#81) → `TeamIdentityResolver`
(`player_identity_mode:"team"`, default) stamps `player_label`/`squad`/
`slot` on players and actions at their CONTACT frame; output-only, tracking
identical in team/legacy (unit-pinned). Orientation = two-state
log-likelihood test on fixed-anchor per-body evidence (e = ±(best squad-1 −
best squad-2 sim)); levels measured in the opening, unseen state mirrored,
slow drift only while quiet; per-body LLR clipped ±2, tempered ×0.2 into a
CUSUM, flip at 8, min interval 300 f, instant doubt on one clearly-swapped
frame. Within side: EMA-similarity permutation, hysteresis 0.5, quick swap
override 2.0. Record (20260920 replay, `scripts/replay_identity.py`, 17 s):
4/4 switches in-window, 0 stray, orientation 211/211 GT contacts, action
squad 128/27/4 vs legacy 83/71/5 (23 of 27 = classifier side-attribution,
not identity); d' 3.9 near / 2.3 far; far within-squad flips 760→51;
robust across a 4× range of every knob. Owed: owner contact-sheet re-run
(per-PLAYER check), entreno 0-flip run. Also display-only: ball
ground-contact/out observer (#80, always-on §6-pure); possession labels
recalibrated twice on owner feedback (#78/#79: NEAR rolling-max ≥1.45×d_net,
FAR max ≤0.85× OR ≥4 of last 12 ≤0.85×); pass-2 relabel/winner/side-switch/
serve-evidence layers (below).

**Production state:** weights `volleyball_ball_best.pt` v3; match 720p
upscaled `_up1080`; 68 ms/frame (pose gating shipped, byte-identical);
match 31/33 points (count, not recall), 207 actions; held-out P9–P33
contact P 0.785 / R 0.760 / F1 0.772, class 0.590, team 0.518 raw →
**0.755 squad-mapped** (34 genuine side errors); taxonomy 46 correct /
57 wrong label / 36 wrong team / 44 missed; overpass 0/18. Pass-2:
`relabel_serves` (near 12/16, far 0/17 — NEVER consume far as label),
`resolve_side_switches` [7,14,21,28] exact, `resolve_point_winners` 18/33,
`consume_serve_evidence` 13/17 covered 9/17 bound. `--serve-events`
observers default OFF (inertness measured). Entreno action gate: e1 0.706,
e2 0.571, e3 1.0, e4 0.933, e5 0.923, e6 0.933, e7 0.75 (e2 caveat: 0.400
on both fresh arms — same-session A/B only). Test suite **1083** (post
lean-pass + identity #83–#85).

**Serves (score_serves.py, ±15f, match P1–P33):** production near **8/16**
(dev 1/3, held-out 7/13), far **0/17** (0/5, 0/12), 12 FP, precision 0.40;
pass-2 relabel near 12/16 far 0/17 + 14 near FP; rally-onset (game_on time
only) near 3/16, **far 11/17** (median |offset| 3f); far evidence layer far
13/17 coverage IN-SAMPLE, 9/17 bound, held-out 4/12, precision 0.47 as
claim, 1 owner FP; entreno fresh 3/5 (e3+0, e6+1, e7+0; e2 f32 + e5 f20
missed; near recall 11/21).

**Near-loss record (#58, 16 near serves):** P9–P12 behind_baseline reads the
contact-frame foot (0.8–24.5 px inside the 761 px threshold) → M-a closed
#60; P5/P7 `player_off_court_hold_frames=90` starves the server track 91 f
(coasts frozen through the serve) → M-b parked (D4: ceiling +1/16, blunt
lever net 0, +P7/−P18); e2 server never tracked (bystander slot); e5 no ball
sighting; P24/P33 unmeasured (P33 = rally_start cascade from own early serve).

**Held-out lock:** `ground_truth/20290928_entreno_vall_dhebron_serve_anchors.json`
= 19 serves (8 near / 11 far, 1 ace, 1 net); the video has NEVER been run;
≥0.90 passes only at 8/8 near (Wilson CI [0.68,1.0]); use only via a card
"score held-out once" with frozen rules.

**SR plan status:** SR0/SR1/SR1b DONE; SR1c closed; SR1d refuted; D4 decided;
SR4a DONE (near bar 15/16 > ceiling 13/16 → SR4-NEAR waits on perception);
SR4-FAR mis-keyed not blocked — its rule keyed on window starts, still
IN-SAMPLE (PG2); SR2 demoted; SR3 worker half behind the held-out lock;
SR5/SR6 after SR4; SR7 deferred.

**STOP list:** no more px-space/contact-geometry far-serve thresholds or
selector constants tuned on the 17 match far serves; no relabeling reception
as serve; no vall_dhebron output looks (band diagnosis #78 was the one
sanctioned exception).

**Refuted/parked mechanisms** (harnesses in `scripts/`, never `src/`): T5
tracker admission, R1 departure gate, S1 looming, scale-aware geometry, M1
far-end crop, possession signal, overpass width-crossing, R2 confidence
calibration, reach-gate cascade (#72), touch-count rules (TC1).

**Known defects:** `annotate_player_gt.py` + `src/db/ingest.py` seek on VFR
(allow-listed in `test_vfr_seek_guard.py`); stale comment at
`src/utils/config.py:101` (`player_off_court_hold_frames`; comment-only fix
deferred).

## Active next (ranked)

1. **E2 observers** (owner-approved scope, next session): identity-drift
   (sustained signature mismatch vs enrolled reference) + side-switch
   (sustained foot-side ≠ squad side) — display/diag only, OWNER GATE
   before acting.
2. **SR4-FAR rule keyed on window starts**, re-tested OUT-OF-SAMPLE with a
   non-serve control window (AGENTS §6) — before SR4-NEAR.
3. **Overpass label lever** = Layer-2 rule design on new instrumentation:
   C1 fitted ball-fate read → C3 relabel via `probe_label_ceilings.py`
   (open point 9; owner-ratified post-hoc direction #77).
4. Owner visual pass on live debug (squad colours/labels, ground observer,
   possession labels).
5. Deferred comment-only fix: `src/utils/config.py:101` (next src-touching
   session).

## Next task cards

*(Empty — cards appear here only while READY/pending; DONE/REFUTED cards are
archived under their session date in `docs/history/status_log_archive.md`.)*

## Open points

### Active

30. **Serve reliability.** Status: near 8/16, far 0/17, 12 FP (see
    Where-we-are table); SR0–SR1b done, near/far loss causes measured
    (near = opener/label/emission; far = mis-keyed rule, see 22). Next:
    SR4-FAR window-start rule out-of-sample, then SR3 worker half.
22. **Far-side serves.** PG2 (#67): window starts ARE serve-anchored (14/31
    within ±15f of a GT serve vs 1.21 chance = 11.56×; far 11/17 AT a start,
    near 11/16 inside), so SR4-FAR is MIS-KEYED, not blocked; far evidence
    exists (width plateau / far_flight; 13/17 coverage in-sample, held-out
    4/12). Next: key the rule on window starts + dead-time episodes,
    out-of-sample re-test + non-serve control; STOP list applies.
21. **Owner's match-feedback backlog** (agreed order): (1) point count 31/33
    — residual 2 = far-serve losses (→22); (2) per-point + per-action
    confidence surfaces UNBUILT; (3) winner layer shipped 18/33 (8 misses =
    terminal-touch attribution →22; 3 kill/ace endings lack ball-death
    side); (4) side-switch shipped exact [7,14,21,28]; (5) player-number GT
    pass pending owner; (6) landing/outcome confidence. Next: (2), then
    winner accuracy via perception.
2.  **Side-change survival (player identity) — status: orientation SOLVED
    on the real match (#85 replay: 4/4 switches, 0 stray, 211/211 GT
    contacts); per-player check pending.** Remaining identity work:
    (a) owner re-runs `scripts/probe_identity_switches.py` for contact
    sheets — each row must be one person (the within-side slot is the
    unmeasured part, far side weakest); (b) entreno run to confirm 0 flips
    on switch-free footage. The 23 wrong-side action attributions in the
    replay are the classifier's (reach/side attribution, parked point 5),
    not identity. History: `docs/history/status_where_we_are_archive.md`
    (#83–#85 sections).
1.  **Stale baselines.** e1/e3 recorded tracking numbers don't reproduce
    (0.771/0.193 vs 0.978/0.133); e2 F1 0.571 recorded vs 0.400 fresh.
    Rule: same-session A/B only; diagnose when touching tracking.
7.  **Action-recall residuals (reach gate).** 20/44 held-out misses
    reach-blocked (9.78× enriched; far-side B 64 / A 6); NOT scale-explained
    (#75: 140 px constant is side-blind; 5/7 rejections pure-lateral; e2
    f403 needs 2.40× the largest real near reach); metre-scale reach
    OWNER-GATED. Next: owner GT contact sheets for e1 f161/f399, e2
    f390/402/403, e7 f163 (ratified) — only then is a mechanism arguable.
15. **Classifier-gate residuals.** (a)–(d),(f) resolved. Open: (e)
    tracking-side gaps (e7 f300 ball never tracked there, f370 set in a 6 f
    sighting gap); (g) multi-court simultaneous play (bootstrap takes first
    mover — needs tournament footage).
14. **game-state limits.** (a) No per-event serve detector in ball-track
    data — every candidate feature refuted; (b) pt00 (coach-fed, one
    contact) + pt03 structurally unrecoverable; (d) contact_chain margin
    thin (in-rally max 215 f vs boundary 262 f); (e) points table not in
    web UI yet.
19. **Deliberate deferrals.** 25.7 fps vs 30 tuning (~17% wall-time skew);
    upscale hooked in `src.main` only (probes read raw files); venue sand
    fires detector ~2.2 det/frame (absorbed by motion gates — check TRACKED
    sample provenance before thresholds).
18. **Squatter-review limits.** (a) real players off-court between points
    look squatter-like (ready lever: pause review on GAME OFF); (b) e7-class
    straddler front end irreducible; (c) cooldown may block admission near
    an expelled squatter (never existing tracks); (d) rolling window NOT
    built (deliberate).
24. **Match contact GT + pass-2 contact scoring.** GT BUILT (33 points /
    211 owner contacts, `ground_truth/20260920_match_contacts.json`);
    G0+G1 done (held-out F1 0.772, far serves 0/12,
    `scripts/score_heldout_contacts.py`). Standing rule: thresholds fit on
    P1–P8 must hold on P9–P33 before shipping. Caveats: P30 f23545
    `action=null` (class acc skips it); `match_start/end_frame` there are
    episode-map PREDICTIONS, never GT.
25. **Dig at ball death (owner-flagged, P15 f10180).** A contact whose ball
    dies within the same contact window is NOT a dig — encode as an
    EXCLUSION in the contact-GT build (not a pipeline change), then count
    how many FPs it removes.
26. **One contact attributed to two players (owner-flagged: P16 f10703, P19
    f13074, P20 live flap).** `evaluate_timed` already reports
    `duplicates`; next: score them vs GT, then look at the emit path (one
    inflect, two actors) — same proximity ambiguity as 5, measure together.
29. **Stale recording guide.** `docs/video_recording_guide.md` contradicts
    the validated long-axis geometry. Next (docs-only): rewrite to the
    long-axis spec + `scripts/probe_capture_spec.py` pre-flight (ffprobe:
    CFR/VFR, effective fps, resolution).
31. **Point-end REST invisible to the ground-contact observer (OWNER GATE
    before any `src/` change).** Static suppression removes resting balls
    BY DESIGN → the tracker drops the final descent (e3 f616: 56 f rolling
    ball visible in diag, track=none) and the label honestly holds AIR
    (BETWEEN read 60.7% AIR). Next: v1.5 = on lost-track frames, if last
    read was AIR + downward vy + near-stationary post-suppression detection
    near the last position, emit a grounded row tagged `from_candidate`
    (§6-pure, display/diag only); parked rack balls (e3 (290,444)/(436,465))
    are the FP control.

### Parked / conditional

5.  **Same-team adjacent-player choice.** Needs the owner-specified engine
    (motion history + ball half, #46); scoreable only with stable-identity
    GT (2); `--ignore-player` stands until then.
6.  **Phase 2: offline global stitch.** Build only if match validation
    shows residual swaps/fragmentation phase 1 doesn't catch.
9.  **Overpass label lever (owner-ratified post-hoc direction #77).** The
    crossing signal is NOT in the stream (4 families killed; dig and
    overpass kinematically identical); TC1 touch-count rules refuted
    0.6187 (+0.050; counter STARVED not mis-reset, 33/43 — upstream is
    contact recall, points 2/5); GT-touch oracle upper bound 0.791.
    Shipped substrate: `src/analysis/ball_side_possession.py` display-only
    (bands 0.85/1.45 × d_net, rolling max 12, far persistent-smallness).
    Sequencing: **C1** fitted ball-fate read (PASS m ≤ 2k−12, one held-out
    shot; e4 f347 must NOT fire, f24948 must fire via the terminal branch)
    → **C2** possession timeline (squad-mapped) → **C3** overpass relabel
    via `probe_label_ceilings.py` → **C4** ambiguous-touch reattribution
    (26 = named test). If C1 fails, C2–C4 still build as attribution tooling.
13. **Ace metric.** Needs point-outcome detection: (a) derived heuristic
    (serve + no opposing touch ≈ likely ace, flagged derived) or (b) real
    outcome detection (game_state score machinery unvalidated). Assist
    proxy parked with it.

## Learnings (standing)

Recording domain + GT conventions live in `AGENTS.md` §7 and
`ground_truth/README.md`; below only what those don't cover.

**Pipeline / output contract**
- `json_exporter.collect_actions` has an EXPLICIT key list — a new action field must be added there or it never reaches `pipeline_output.json`.
- `pipeline_output.json` lacks a dense per-frame sequence; temporal experiments need a `--diag-dump` sidecar.
- A `--diag-dump` JSONL replays the PRODUCTION ball tracker exactly (4968/4968 frames) — tracker counterfactuals need no re-implementation (`scripts/probe_serve_mechanisms.py`).
- Detectors expose inert read-only side channels (`PlayerDetector.off_area_detections`, `BallDetector.raw_detections`) — observers read them, never re-run inference.
- `action_confidence` is INERT (0.3 < min emitted 0.45); gesture constants carry no correctness info — do not surface as trust.
- MPS jitter can flip a gesture label — the script path is the reference; `--device cpu` for baseline parity.
- `evaluate.py` on raw `src.main` output reads 0.000 — it wants an `actions` entry + `frame` key (`src.main` writes `frame_number`); use the frame-key adapter.
- `evaluate --ignore-player` REQUIRED (0.933 vs 0.133); pred `player_id` = L-R index over the FILTERED candidate set (convention, not bug).
- Perception emits COURT-SIDE letters; GT uses SQUAD letters — squad-map before comparing (0.518 → 0.755).
- `evaluate_match_points` 31/33 is a COUNT comparison, not matched recall.
- A refuted mechanism must NOT live in `src/` even default-OFF (config surface + drift guard carry it forever); keep it in the probe harness as a default-off subclass (`test_serve_backfill.py` greps `src/` to enforce).
- Fix-worth-nothing rule: a change that fixes no measured failure ships nothing.
- Measured ≠ inferred: a dumped replay is not the production stream (dump `accepted` rows lack `behind_baseline` — 0/12 serves; shipped 85/139 vs replay 79/139).
- Probe scripts must mirror `src.main` auto-detection — `Config.default()` runs the COCO fallback, use `score_serve_events.production_config()`.
- Diag scripts must read what the pipeline actually consumed; a "baseline" from an offline re-run is not a baseline.

**Ball / side / calibration**
- Ball px width is the side signal: ~14–28 far / ~30–55 near, ABSTAIN 26–35; possession alternation confirms.
- `d_net = D·w_near·w_far/(4·(w_near+w_far))` (owner pinhole; match ≈22.8 px); possession bands FAR ≤0.85×, NEAR ≥1.45× on the ROLLING MAX of the last 12 measured frames; far also fires on persistent smallness (≥4 of 12 ≤0.85×).
- `NEAR_NET_PX=120` is load-bearing; px→m for `near_net` is GT-REFUTED (0.929 → 0.857) — px `near_net` stays.
- Px thresholds are VENUE-COUPLED (court depth 206 px beach vs 464–479 px practice); camera height changes per video, calibration is per video.
- 4-corner homography is wrong at the far end (far zones in IMAGE space); `CourtCalibration.world_scale_at` is UNUSABLE (mean of two ~6× components, poles) — use the ACROSS component (0.58–0.74 m) only; `frame_dimensions` is (h, w).
- Wire every calibration consumer in `__init__` — the #80 batch-calibration bug was a consumer reading a stale calibration.
- Ball speeds used as gates must be normalised by apparent ball width (px/f is scale-biased against far contacts); width-normalised departure conflates dead balls.
- Far serve is geometrically invisible to `ActionClassifier` (depth-dominated motion; needs a size-growth cue); far ball detected ~1-in-4 frames; "0–1 tracked" figures are TRACKER counts — the detector sees 14–31 of 31.
- Serve is structurally recoverable post-hoc: no-contact 60–240 f + far-band person + raw det = 11/17 @ 1.00 precision (union 14/17 @ 0 FP); bind by dead-time EPISODE, not point window; report coverage and binding as two numbers; the far-serve ECHO straddles contact (net crossing separates).
- Serve-window opener is a weak key (only 4/8 near hits have the serve as first action).

**Tracker / identity**
- `BallTracker` returns None when lost — never hallucinates; before calling a detection-recall gap, probe raw detector output (it's often tracker admission/gating).
- T4 waterfall: lost dev serves = detector FIRES (conf 0.74–0.87) but tracker `unlocked_no_motion` — the toss apex is slower than `lock_min_speed` 8 px/f; T5: all 5 lost dev serves are far-side (13–17 px, 1.6–6.7 px/f; a 3 px/f weak tier recovers 5/5 but has no discriminator).
- `CONTACT_DELAY` bounds lock-time backfill (probe tests contact at c+7); union high/low-tier sighting windows index-wise or motion pairs mis-age.
- Enrollment chaining is ONE-TO-ONE per sampled frame (greedy chains + fragment merge); `cv2.setRNGSeed(0)` per PlayerTracker instance in multi-tracker harnesses.
- Identity changes are MATCH-WIDE events (one swap poisons the whole episode); display labels follow the BODY via the per-frame resolver, never the carried-forward box (a carried box freezes identity).
- Identity contract (owner): labels must CONVERGE on the same person most of the time; do not harden association against every swap.
- A side switch is invisible to positions — identity there is appearance-only, and the first post-switch comparison is CROSS-VIEW (enrollment saw each squad from one view): decompose into orientation (change-point over all four bodies) + one slot bit per side (#83).
- Teammate-only impostor normalisation is fooled by mixed teams (a same-build stranger outscores the teammate): normalise against ALL players + a same-view genuine FIT term (#83).
- Never decide orientation by absolute hypothesis comparison (informative-for-one/neutral-for-the-other terms are a standing flip bias), nor by generic "shift from own baseline" (a 1σ pose/light drift freezes it, #84): two-state LLR between explicit levels, learned prototypes OUT (#85).
- `np.load(npz)[key]` decompresses the whole array on EVERY access — read each array once before looping (replay >10 min → 17 s, #85).
- Squatter/bystander: in-court preference + court-membership enforcement in `_may_feed_track`; detection-gap diagnoses in the entreno protocol (AGENTS §1).

**GT / scoring semantics**
- Contacts dictation has two dialects; `gt_point_start_end.txt` is game-state VIDEO, not the match; match serve team = winner-of-previous; `touch_number` is per-TEAM possession; kill = direct fall OR dug-and-dies; GT edits only via owner-ratified contact sheets; re-adjudicate GT when the model shifts streams.
- Two "point start" sources in `ground_truth/` are PREDICTIONS, not anchors (owner anchor = serve contact frame; all 33 points have the serve as earliest contact).
- GT class wording IS the label: "bump pass" ⇒ overpass even into-the-net (f24948); `missatr` marks are NOT exhaustive; GT-file `landing` ≠ readable (parser extraction issue).
- e2 recorded F1 0.571 does not reproduce (0.400 on both fresh arms) — same-session A/B is the only valid comparison.
- PRECISION BUDGET: `m ≤ 2k − labels_needed` (fires allowed for a label lever); include a sanity-check row in every scoring table.
- Label-lever harness: `probe_label_ceilings.py` (vocabulary ceilings), the label-only oracle is trivially 1.000 — bar is class_accuracy.
- Layer 1 is degenerate on the match (157/185 contacts = `bump_set`); every dig/set/overpass/serve label is `ActionContextResolver._decide` keyed on `_poss_touch` — touch-count errors are downstream of MISSING contacts (starved 33/43, not mis-reset).

**Perf / infra**
- Pose gating shipped: 84.8 → 68.0 ms/f byte-identical; detector floor ~48 ms/f.
- VFR: `CAP_PROP_POS_FRAMES` lands −28..+30 f off — decode spans sequentially (`test_vfr_seek_guard.py`); two KNOWN-ISSUE allow-lists: `annotate_player_gt.py`, `src/db/ingest.py`.
- Delegation: >1 KB prompt kills the child pi (EXIT 137) — few hundred bytes + the child reads a brief file.
- Retraining: four-leg gate; fine-tune FROM `best.pt`; mine frames with NO pre-labels.

## Session index (one line each)
- #86 **Repo lean pass**: STATUS 2465→~530 lines with hard budgets + guard test (tests/test_status_leanness.py); 21 closed-probe test files deleted (530 tests, suite 1569→1039→1083 post-merge); no src/ change
- #85 **Side switches SOLVED on the real match (replay of the owner's dump): two-state LLR orientation → 4/4 switches, 0 stray, 211/211; squad 128/27/4 vs 83/71/5 (23/27 classifier); churn 760→51; suite 1477**
- #84 **Identity round 2: first real run measured (18 flips / 4 switches) → orientation redesigned (per-side CUSUM on fixed anchors); feature dump + scripts/replay_identity.py for offline tuning; suite 1477**
- #83 **TEAM IDENTITY RESOLVER (output labels only, tracking identical): identity_resolver.py (orientation + within-side slots), probe_identity_switches.py owner gate, contact-frame action labels; +30 tests, suite 1475**
- #82 **Identity labels follow the body (per-frame resolver), team-letter labels P1A/P2A/P1B/P2B, readable colours; f151 teammate id-swap fixed**
- #81 **Player enrollment (E1) + squad colours (E3) shipped display-only — sticky P1A/P1B/P2A/P2B labels; tracking byte-identical (ΔF1 0.000 ×7)**
- #80 **Ball GROUND-CONTACT/OUT observer shipped (display+diag); batch-calibration wiring bug fixed; point-end REST invisible to the tracked-ball contract (open point 31)**
- #79 **Possession labels RE-BALANCED on owner feedback (mirror bias: far rallies held NEAR)** — the #78 rolling-max statistic is wrong for the far side: a far dig/set rally flickers 0.66-1.14×d_net ( — …(log archive 2026-10-06)
- #78 **Possession labels recalibrated on owner feedback (occlusion-dip far bias)** — probe `scripts/probe_possession_feedback.py` measured the width regimes on match+vall (near flight ≥1.55×d_net — …(log archive 2026-10-06)
- #77 **Post-hoc layer RATIFIED + first instrumentation SHIPPED: per-frame ball-side POSSESSION + net-CROSSING live-debug labels (display-only pure observer)** — …(log archive 2026-10-06)
- #76b **The OVERPASS lever is `UNREACHABLE FROM THE CURRENT STREAM` — the +0.0949 prize and the modest 88-100% precision budget are both real, but no emitted signal separates the class — …(log archive 2026-10-06)
- #76 **G3 label-lever ceilings RE-MEASURED: item 0a's arithmetic is CORRECTED — the `overpass` lever alone crosses the 0.70 bar (0.6131 → 0.7080), because `90/139 = 0.6475` is TOUCH accuracy quoted i — …(log archive 2026-10-06)
- #75 **Reach-gate scale diagnosis DONE: `NOT SCALE-EXPLAINED` — the 140 px `CONTACT_REACH` is side-blind (far 1.359 m vs near 1.014 m, 1.341x), but the 7 far-side rejections are 1.382-4.540 m, 2.40x — …(log archive 2026-10-06)
- #74 **Coordinator session: finished #72/#73's ritual (commits `da0c962` overlay, `c336753` ritual; FALSE commit claim `8040f04` caught via reflog), then delegated + verified the SET↔DIG SWAP diagnos — …(log archive 2026-10-06)
- #73 **Live-debug ball-candidate overlay LANDED (display-only, `b` toggle, default ON): every detector ball with confidence + suppression verdict via the `raw_detections` side channel — …(log archive 2026-10-06)
- #72 **REACH-GATE CASCADE REFUTED offline (`docs/g3_reach_cascade.md`): admitting the reach-blocked contacts does NOT fix the labels — K=1.2 (precision-clean, +14 found) → −4 LABELS; K=1.3 −5 — …(log archive 2026-10-06)
- #71 **CARD TC1 DONE: `touch_rule_gate = TOUCH_COUNT_LEVER_REFUTED/0.6187` — the possession count is NOT re-derivable from the emitted contacts; nothing ships, no architect card is justified — …(log archive 2026-10-06)
- #70 **#68's LABEL BASELINE CORRECTED — the shipped stream is 85/139 = 0.612 (dump `action`) / 83/141 = 0.589 (`pipeline_output.json`), NOT 79/139 = 0.568; that figure is a REPLAY artifact** — …(log archive 2026-10-06)
- #68 **THE TOUCH-COUNT LEVER: the largest held-out label loss is Layer 2's possession count, not Layer 1's gesture** — …(log archive 2026-10-06)
- #66b **PG2 DONE, `point_map_alignment = PG1_VERDICT_IS_A_PAIRING_ARTIFACT`: PG1's `REFUTED/1` is a PAIRING artifact — window starts ARE serve-anchored; SR4-FAR is mis-keyed, not blocked** — …(log archive 2026-10-06)
- #65 **PG1 DONE, `point_map_gate = REFUTED/1` — the point map is uniformly LATE, not aligned; SR4-FAR stays blocked on open point 22** — …(log archive 2026-10-06)
- #64 **PM1 `FAIL=blocked`: the far-serve record cannot bypass the point map; SR4-FAR is blocked on open point 22** — …(log archive 2026-10-06)
- #63 **SR4 REFUTED AS SPECIFIED (architect call + coordinator re-measurement; nothing built, `src/` untouched)** — `docs/sr4_architect_call.md`, memo run in `logs/architect_sr4_ds_run.log`. — …(log archive 2026-10-06)
- #62+ **SR4a DONE (delegated worker card; diagnose-only, `src/` untouched)** — `scripts/probe_near_openings.py`, `docs/sr4a_near_openings.md`, `logs/sr4a_report.md`, `tests/test_near_openings.py` (+3 — …(log archive 2026-10-06)
- #62 D4 DECIDED (architect, on `docs/d4_gate_brief.md`; nothing built, `src/` untouched): M-a stays CLOSED and **M-b is PARKED** — …(log archive 2026-10-06)
- #61 SR1d DONE — `global lift REFUTED` (`docs/sr1d_hold_horizon_cost.md`, no `src/` change): the 90 f off-court hold lifted to 100000 changes the 7 practice clips not at all (action streams byte-iden — …(log archive 2026-10-06)
- #60 SR1c CLOSED (stopped at its own reproduction gate — 194/207 match, 6/7 and 13/14 practice, vs ≥98% — nothing shipped — …(log archive 2026-10-06)
- #59 live-debug HUD: the frame counter gets a solid black plate and +1 px, and a new display-only side panel (`src/analysis/debug_panel.py`, `p` toggles) shows the per-frame signals (ball px size + t — …(log archive 2026-10-06)
- #58 SR1b review: SR0/SR1 checked by a worker pass over match [0,15000] (parity 111/111) + a hold-off counterfactual — …(log archive 2026-10-06)
- #57 SR1 DONE: the near-serve miss taxonomy (`scripts/probe_near_serve_misses.py` + `docs/sr1_near_serve_misses.md`, +21 tests — …(log archive 2026-10-06)
- #56 SR0 DONE: one serve scorer for every stream and side (`scripts/score_serves.py` + `docs/sr0_serve_scorer.md`, +33 tests, gate PASS): baseline reproduced (near 8/16, far 0/17, 12 FP), the record — …(log archive 2026-10-06)
- #55 planning only: serve-reliability plan SR0-SR7 (`docs/serve_reliability_plan.md`, open point 30). Honest baseline near 8/16 / far 0/17 / 12 FP. — …(log archive 2026-10-06)
- #54 S4 DONE: the serve evidence is a real artifact (`output/serve_evidence.json`, 87 records, precision 0.90, inertness measured) — anchored coverage 14/17 vs consumer binding 9/17, both reported — …(log archive 2026-10-06)
- #53 the far serve SOLVED as evidence: 14/17 GT far serves at ZERO false positives (production 0/17) via the opener gate + a structural proposer over raw detections — …(log archive 2026-10-06)
- #51 G4 serve-evidence events (far flight + runway + conjunction): default-off observers in `process_frame`, scored 3/17 GT far serves at +-15 f vs production 0/12 — …(log archive 2026-10-06)
- 2026-10-01 **#52** — possession signal built + REFUTED + parked (no `src/` change, no decode): `scripts/possession_signal_harness.py` (default OFF) + `scripts/probe_possession_signal.py` + `docs/g3_ — …(log archive 2026-10-06)
- 2026-10-01 **#50** — G3 overpass crossed diagnosis REFUTED (diagnose only, no `src/` change, no decode): `scripts/probe_overpass_crossing.py` (+23 tests) + `docs/g3_overpass_crossing.md`, artifacts — …(log archive 2026-10-06)
- 2026-10-01 **#49** — S3 DONE: pass-2 side-switch/squad layer — `scripts/resolve_side_switches.py` (+25 tests) + `docs/g3_side_switch_layer.md`, no `src/` change, no decode — …(log archive 2026-10-06)
- 2026-10-01 **#48** — G1 DONE: the first HELD-OUT contact score — `scripts/score_heldout_contacts.py` (+20 tests) + `docs/g3_heldout_p9_p33.md`, no `src/` change — …(log archive 2026-10-06)
- 2026-10-01 **#47** — G0 DONE: the whole-match contact GT (P1–P33) is machine-readable — dialect-B `parse_contact_gt` + `scripts/build_match_contact_gt.py` → `ground_truth/20260920_match_contacts.jso — …(log archive 2026-10-06)
- 2026-09-30 **#46** — RECORD-ONLY session: owner dictated the **whole 20260920 match contact GT (P1–P33)** in a second dialect (0 of ~196 new lines parse yet — …(log archive 2026-10-06)
- 2026-09-30 **#45** — G3 plan S0b: pass-2 stream scored at CONTACT level on the owner P1–P8 GT (`scripts/score_pass2_contacts.py` + 28 tests + `docs/g3_s0b_pass2_contact_score.md` — …(log archive 2026-10-06)
- 2026-09-30 **#44** — G3 plan S1 far-side serve looming probe (diagnose only, no `src/` change, suite 811): `scripts/probe_far_serve_looming.py` + 29 tests + `docs/g3_far_serve_looming.md` — …(log archive 2026-10-06)
- 2026-09-30 **#43** — open point 21.3 point winner/outcome layer SHIPPED as a pass-2 script (`scripts/resolve_point_winners.py` + 27 tests + `docs/point_winner_layer.md` — …(log archive 2026-10-06)
- 2026-09-30 **#42** — architect strategy review of the "detector v4 → normalise → learned gestures" proposal (docs-only, no `src/` change, suite 755): order NOT adopted — …(log archive 2026-10-06)
- 2026-09-29 **#40** — G3 per-action evidence diagnosis (`scripts/action_evidence.py` + `docs/g3_action_evidence.md`, +22 tests, suite 754; no `src/` change): 85 predictions, 54 correct — …(log archive 2026-10-06)
- 2026-09-29 **#39** — T5 revert/cleanup (docs + tests only, no production change): reviewer ruled both mechanisms refuted (0/5 far serves) ⇒ `src/` restored exactly to `185c6f0` (`git diff 185c6f0 -- — …(log archive 2026-10-06)
- 2026-09-29 **#38** — T5 step 2: A (weak tier) vs B (backfill on a fresh lock) implemented default-OFF and replayed through the REAL `BallTracker` + `ActionClassifier` (`scripts/probe_serve_mechanism — …(log archive 2026-10-06)
- 2026-09-29 **#37** — T5 mechanism APPROVED by the owner (serve-time ball-track (re-)admission) + step 1 diagnosis ONLY (`scripts/probe_serve_admission.py` + `docs/t5_serve_admission_diagnosis.md`, n — …(log archive 2026-10-06)
- 2026-09-29 **#36** — T4 loss waterfall SHIPPED: off-by-default `--diag-dump` capture in the shared frame path (`src/utils/diagnostics.py`) + `scripts/waterfall.py` + `scripts/compare_runs.py` — …(log archive 2026-10-06)
- 2026-09-29 **#35** — T3 time-matched evaluator SHIPPED: `scripts/evaluate_timed.py` (+23 tests, suite 648) — …(log archive 2026-10-06)
- 2026-09-29 **#34** — T2 contact-GT code review fixed (3 defects: rally-global → per-possession `touch_number`, draft/suggested duplicates moved to `superseded_draft_events` (15 of them, `events` == — …(log archive 2026-10-06)
- 2026-09-29 **#33** — T2 contact-level GT wired: `scripts/build_dev_clip_gt.py` parses the owner's `20260920_match_ari_joan_contacts_p1_p8.txt` (28 contacts, P1–P8, coarse ±10–15f, side-switch after — …(log archive 2026-10-06)
- 2026-09-30 **#33** — G3 R1 departure gate validated end-to-end and REFUTED on the held-out match (P11 owner serve f7132 @ 0.285 bw/f removed; verdicts broken, 31/33→28/33, census 8/8→7/8) — …(log archive 2026-10-06)
- 2026-09-29 **#32** — T2 dev-clip GT BUILT (REVIEW, not ratified): offset map (identity, residual 0.0 at start/mid/end), `scripts/build_dev_clip_gt.py` (+25 tests), DRAFT GT for P1–P8 (8 owner serve — …(log archive 2026-10-06)
- 2026-09-29 (38th session, archived) — T5 step 2: A/B replay of the serve-admission mechanisms through the production classes — both refuted as a recovery (0/5) — …(log archive 2026-10-06)
- 2026-09-28 **#30** — documentation-only generalization assessment and staged G1/G2 roadmap: `docs/202609-28-astra-fix-pipeline.md` — …(log archive 2026-10-06)
- 2026-09-28 **#28** — point 22 mechanism 3 SHIPPED: pass-2 serve re-labeling (`scripts/relabel_serves.py`, +29 tests) — …(log archive 2026-10-06)
- 2026-09-28 **#27** — architecture ratified: pass-2 interpretation layer over the stream (map → serve re-label → winner → fantasy); full-video two-pass REJECTED (live parity + no perception gain) — …(log archive 2026-10-06)
- 2026-09-27 **#26** — open point 22 mechanism 1 SHIPPED: anchor-free episode→GT-point order map (DP + BURST class, physics constraints) + far/near serve census on TRUE windows — …(log archive 2026-10-06)
- 2026-09-27 **#25** — open point 23 SHIPPED: live-debug producer/consumer decoupling; logs + rendered frames byte-identical; 8.0 → ~12 fps; +14 tests (Log below).
- 2026-09-27 **#24** — product north-star goals set (G1 Fantasy scoring / G2 individual stats); stat-coverage audit + critical paths (archived).
- 2026-09-27 **#23** — pose gating shipped in the shared classifier (staleness + near-ball trail), byte-identical everywhere, match ×1.24 (Log below).
- 2026-09-27 **#22** — far-side serves scoped: retracted mispaired-anchor measurement; P2 specimen (ball tracked; loss = episode starvation + serve-action gate); `derive_match_serve_windows.py`.
- 2026-09-28 **#29** — pi config split per harness: model defaults moved out of `.pi/settings.json` (project settings override agent-dir; no per-provider scope) into each harness's agent dir — …(log archive 2026-10-06)
- 2026-09-27 **#21** — pi repo default model → zai/glm-5.3-flash (SUPERSEDED by #29: default now lives in `~/.pi/agent/settings.json` as zai/glm-5.3).
- 2026-09-27 **#20** — e3 v3 drift FIXED without GT edits: bridge defers only when a fireable normal vertex exists; 7/7 neutrality; match 31/33 unchanged (Log below).
- 2026-09-26 **#19** — round-2 rebalanced mining (350 frames); v3 four-leg gate → **ADOPTED as production**; far-side serve feedback → point 22.
- 2026-09-25/26 **#18** — retrain-mining staged (500 stratified frames); owner GT landed (486 frames, pre-labels mostly wrong — diagnostic correction); dataset merged + zipped (1091) — …(log archive 2026-10-06)
- 2026-09-24 **#17** — match GT transcribed (33 points) + `evaluate_match_points` (baseline 14/33); bg-stratified ball probe indicts the 0.4 conf floor; conf-floor mechanism SHIPPED (actions 74→90 — …(log archive 2026-10-06)
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
- 2026-08-17 — config-drift guard; config-default divergence FIXED (f539 block provenance); e3 GT serve frame fixed; live-debug frame counter; near-net flag closed by diagnosis — …(log archive 2026-10-06)
- 2026-08-16 — team-aware contact attribution (team 0.69→0.92); server tracking fixed + ghost damping.
- 2026-08-15 — bystander-hijack fix (assignment-level court membership); first player-ID GT + occlusion-aware eval; ghosts excluded from the classifier.
- 2026-08-14 — player identity phase 1 (1a+1b+1c) shipped.
## Log (newest first)

### 2026-10-06 (eighty-sixth session) — #86: repo lean pass — STATUS compacted with hard budgets + guard; closed-probe tests deleted

**Asked (owner):** STATUS and tests/ are both getting too long; summarize STATUS, make it structurally unable to regrow, audit tests and delete the unneeded ones — goal: LLMs put fewer tokens into reading at the same repo performance.

**Done:** STATUS.md 2465 → ~530 lines (every removed line VERBATIM in `docs/history/status_log_archive.md` + `status_where_we_are_archive.md`; nothing deleted); hard budgets enforced by `tests/test_status_leanness.py` (≤600 lines total, per-section caps, one-line session index ≤240 chars, ≤3 Log sessions, no DONE task cards, canonical header order — a failed guard means archive-then-shrink); AGENTS.md lean-STATUS convention now names the guard. Deleted 21 test files (6,600 lines / 530 tests) whose ONLY subject is a DONE/REFUTED one-off diagnostic probe (TC1 touch rules, PG1/PG2 point maps, PM1, SR1*/SR4a probes, overpass levers, possession signal, reach/scale/looming diagnoses, near-serve misses, takeoff stance, entreno/serve buckets, dev-clip GT builder, insert path, label ceilings, set-dig swaps) — probe scripts stay as provenance, docstrings annotated; everything guarding `src/`, standing evaluators/scorers, pass-2 layers, GT tooling, config drift and the VFR seek guard KEPT. No `src/` change. Merged with the parallel identity sessions #83–#85 (PR #1); this lean pass renumbered #83 → #86; suite 1083 all green.

### 2026-10-05 (eighty-fifth session) — #85: side-switch orientation solved on the real match — two-state likelihood test, measured offline on the owner's feature dump

**Asked (owner):** re-ran the probe with #84 and pushed `identity_features.npz` + `identity_probe.json` to `temp-branch`. #84 live: 16 flips (P7/P14 windows right, P21/P28 missed, 14 stray, dwell-spaced every ~1500 f), 151 of 211 GT contacts withheld, action squad 37/13/109; sheets mostly blank (doubt).

**Diagnosed on the dump (no video needed):** per-body fixed-anchor evidence vs GT orientation: near +0.148±0.085 (A near) vs −0.119±0.093 (B near), far −0.172±0.108 vs +0.048±0.087 — d' ~3 / ~2.2, sign right for 81-97 % of bodies. The signal was fine; #84's detector was not: a directional 'any shift' CUSUM with drift 0.5σ freezes its baseline once a 1σ pose/light drift starts, then accumulates forever.

**Changed:** orientation = two-state log-likelihood test (see Where we are) — offline simulation first (`numpy` over the dump), then in `TeamIdentityResolver`; knobs `player_identity_switch_threshold` 8, new `player_identity_switch_temper` 0.2 (replaces `_switch_drift`), `player_identity_min_switch_interval_frames` 300; instant doubt (mean per-body LLR ≥ 1 on one frame, ≥ 2 bodies; 11 false frames of 23 176); `separability()` (d' per side) in state + probe/replay reports. Within-side: SWAP_K 1.0 → 2.0 (far within-squad flips 760 → 51; HYST_K stays 0.5 — a reversed margin converges only to its own size, so ≥ 1 could never fire). Combined per-player similarity stacks; `load_features` reads each npz array once (replay >10 min → 17 s). Tests: synthetic warm-up overridden to 100 frames in the helpers, swap bound 15 frames; suite 1477.

**Measured (replay of the owner's run):** flips 4510/9563/15487/21718 all in-window, 0 stray, orientation 211/211, 0 withheld; action squad 128/27/4 vs legacy 83/71/5; 23 of 27 errors = toucher on the other side (classifier), 3 identity, 1 not visible. Robustness sweep (simulation): flips and 0-error result unchanged for κ 0.05-0.2, H 8-15, clip 1-2, warm-up 150-600, dwell 0-1500, α 0.0005-0.002 (α 0.01 breaks: adaptation chases noise), far-side bias +0.05/+0.1, separation ×0.6/×0.4.

**Not done / owed:** owner contact-sheet re-run (per-player); entreno run (0 flips expected); the owner may delete `temp-branch` (match-derived data).
### 2026-10-05 (eighty-fourth session) — #84: identity resolver round 2 — the first real run diagnosed (18 flips for 4 switches) and the orientation layer redesigned

**Asked (owner):** ran `scripts/probe_identity_switches.py` on the 20260920 match and shared the log, the report and 3 contact sheets: sheet 02 all right; sheet 00 right except 0:59B/1:19B (P1A also missing some); sheet 01 swaps around 11:19/12:19/13:19.

**Measured (owner run, #83 design):** flips at f1163, 2292, 3743, 5855, 7052, 9488, 11000, 12001, 12901, 13801, 15544, 17054, 18214, 19938, 20840, 21740, 22820, 23720 (GT switch windows: after P7 [4040,4770] missed -- the state was already flipped by the stray f3743; P14 9488, P21 15544, P28 21740 on time); orientation at GT contacts 127 ok / 21 wrong / 63 withheld of 211; label coverage 0.40-0.48; action squad (159 matched) team 71/28/60 vs legacy 83/71/5. Every sheet error is a whole-team swap inside a wrong-orientation stretch.

**Diagnosed (code + numbers; no footage in the container):** (1) the orientation evidence `e = z + f` had f = 0 for (player, view) pairs without native stats -- every cross-view comparison -- while the current hypothesis's f was often strongly negative on real poses (enrollment genuine spread is tight), so the swapped hypothesis was favoured at rest; (2) learning ran after wrong flips and fed the corrupted prototypes back into the orientation statistic (12 learned far prototypes for P1A by the end); (3) the dwell clamp held the CUSUM at threshold, so a flip fired as soon as the 900 f dwell expired (flips spaced 900-1100 f: 12001/12901/13801, 22820/23720).

**Changed:** `src/tracking/identity_resolver.py` decision layer rewritten (see Where we are): `measure()` / `update_observed()` split (`BodyObs`); orientation = per-side baseline-relative directional CUSUM on FIXED anchors, both sides, baseline seeding from the post-change run, defaults threshold 25 / drift 0.5 / dwell 1500 (Config + tracker + drift guard); within-side = always label with margin-scaled hysteresis, per-clean-body quick swap override, occluded/merged crops ignored, lenient stranger test; learning only for within-side models. Probe: records x/CUSUM per side and writes `identity_features.npz`; new `scripts/replay_identity.py` (re-run + re-score offline, `--set NAME=VALUE` overrides). Tests: resolver suite adapted (warm-up-realistic timings, steady-state CUSUM bound instead of exactly 0), +2 dump/replay round-trip tests; suite 1477 passed (same pre-existing missing-`output/` failures).

**Not done / owed:** the real-footage check of #84 (owner re-run + dump); entreno A/B (§1).
