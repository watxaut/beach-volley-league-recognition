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

Last updated: **2026-10-09 (102nd session) — a Feedback button on every page of the web app: members send a bug or a suggestion with up to
3 screenshots, follow it under Settings; admins triage under Admin → Feedback; `make feedback` pulls the open ones for a session.**
#101 (net-anchored court positions), #99 (reception vs defense), #98 / #97 (hard / touch), #96 (player page v2), #95 (unknown-player slots) and #90 (platform) lie underneath.

## North-star goals (set session 24)

- **G1 — fantasy scoring per point/player** (ratified 09-27): Kill +1,
  Block +1 (kill_block +1 / soft_block 0), Ace +1, Dig +1, Assist +0.5 flat,
  Error −1 (attack out / service fault / ball handling).
- **G2 — individual stats** (kill%, dig%, zones, tendencies, multi-session
  via player labels): mostly built (player pages, heatmaps, splits); left =
  serve/assist/error stats, per-point views, confidence surfaces, multi-session UX.
- **G3 — ACTION ACCURACY = most important** (G1/G2 depend on it). Bar =
  `class_accuracy`; contact F1 is label-blind; label-only oracle is trivially 1.000.
- Stat coverage: kill/dig/attack-error, ace + serve-error, assist and
  point winner are all derived by the post-run layer (#87) per credited
  touch; block is not a label; ball-handling error not perceptible →
  manual override in the review UI.
- Critical path: owner player gate (32a) → ingest `match_reconstruction.json`
  into the DB → points-table UI (14e) + fantasy. Rollout gate = fast human
  review of the play-by-play.


## Where we are

**Post-run reconstruction (#87, `src/postrun`, `docs/postrun_reconstruction.md`).**
Offline layer over the `--diag-dump` sidecar (schema 4), ~3 s per match, no
decode: ball timeline (vertices incl. reach-refused ones, births/deaths, gap
vertices, one robust depth line per flight) → points (serve = launch beside a
baseline that clears the net and reaches the other half; far serve = track
BIRTH; end = sand / net / air-time) → touches (one shortest path per rally
over half × touch number × player: reception to the receivers, ≤3 touches,
players alternate; hidden touches keep the count, never credited; a seen touch out of reach is credited by alternation) → labels →
match (winner = next server; ball death is the cross-check; score closes the
last point; service order names every server). All constants are metres /
seconds / costs through the calibration (net height reads 2.43 m beach,
2.42 m practice). `make run-match` / `make postrun`; output
`match_reconstruction.json` + play-by-play `.txt` + per-player stats/fantasy.

**Record (20260920, `scripts/score_postrun.py`, ±15 f):** points 33/33, 0
false; serve half 33/33, squad 33/33, frame 32/33 (P31 = GT typo); winners
33/33, score A 21 – B 12 exact, switches after 7/14/21/28; touches P 0.976 /
R 0.933, action 0.982, half 1.000, squad 1.000; 0 rule breaks (causal stream:
P 0.711 / R 0.815 / action 0.559 / half 0.759; 23 same-player-twice, 45
fourth touches). Practice e1–e7: serves 5/5, P 52/53, action 52/52. Sweep (78
moves): no row loses a point or a winner; worst P 0.965, action 0.958.
**Per-player WHO: RATIFIED (#88).** Owner reviewed the 208-row attribution
CSV — every player right, 0 corrections (incl. the 10 by-alternation and
rotation-named servers); the CSV is the per-player GT. Line calls: 3 of 10
in/out reads wrong (overridden by the next serve).

**Attack type (#97, `attack_shape.py`): hard / touch is a POST-RUN read.** The flight after the attack in metres:
vertical launch speed (ballistic fit) + horizontal speed read twice (ball-width trend; attack → next touch). Touch =
launch elevation ≥ 25° or leaving under 5 m/s, hard = the rest, NO type when the two reads disagree. Match, 32
owner-typed spikes: 26/29 right, 29 typed (causal `SpikeAnalyzer`: 10/16 on 16) — V1 bars met, IN-SAMPLE; practice
6/6 on 6 of 8. Recon schema 3 (`spike_type`, `launch`); the bundle publishes it. **Web (#98):** `player_profile` → `analytics.shots` (hard / touch / free / unread × n, kills, errors; adds up to `n_attacks`) + guarded `landings[].type` (migration `20261009110000_attack_shots`, NOT pushed): only a row with `extra.launch` has a type, so a pre-#97 publish reads "not read". Attack map: line = shot, `Shot` filter; "By shot" card; grade B. **Compare (#99):** the Overview card draws the gap to the league average (`gapScale`: more = right, one shaded "too close to call" zone, blue / orange verdict bars, fantasy last); no average yet = bars from zero.
**Court positions (#101, `positions.py`, OUTPUT ONLY, recon schema 4):** published `court_x_m` / `court_y_m` / `court_xy_m` = net-anchored frame (net-ground clicks) + per-video ball-box offset from the end switches (20260920: 1.74 px; spikes 1.40 m off the net from both halves, was 2.70 / −0.30). Points / touches / labels / winners / txt byte-identical (match + e1–e7); needs `make republish-all`; ±0.6–0.8 m per position (open point 35).

**Product platform (#90, BUILT, not deployed — AGENTS §13).** Drive inbox →
`make inbox` (name, calibration wait, run-match, publish DRAFT) → one
transactional Supabase RPC (applied/unchanged, admin rows untouched) → RLS +
React SPA. Verified offline (scratch PG16, parity, CLI e2e, SPA screenshots);
hosted Supabase/Cloudflare/Drive/launchd untested — owner deploys (#90 Log). #102: Feedback button (bug / suggestion + ≤3 screenshots; `send_feedback()` is the only way in, 20 reports + 30 uploads a day per member; Settings → My reports, Admin → Feedback, `make feedback` → `output/feedback/`; migration `20261009130000_feedback`, NOT pushed). #91: attack landings carry both axes, a per-axis error and a result (recon schema 2, migration `20261006180000_landing_confidence`); needs `make postrun` + re-publish per match. #92: stats windows + side-out/break + serve targets + reception outcome + hitting % + report card + `/measure` (migration `20261007100000`, no re-publish needed); `make republish-all` redoes post-run + publish for every published match (needs its diag dump). #93 security review (AGENTS §13): table privileges are explicit (`20261007120000`; `anon` holds none), `match_report` gates its per-player extras by tier (`20261007130000`), `webapp/public/_headers` (CSP), the publisher refuses a `.env.publish` others can read, login codes go through `supabase/functions/request-login-code` + `login_code_gate()` (`20261007140000`); verified on the local stack only. #95: `match_participants.is_unknown` (`20261008100000`) = a slot outside the league (AGENTS §13); migration pushed by the owner (2026-10-08). #94 login study (`docs/web_login_study.md`): sessions persist (refresh token, no limit); fixes + passkeys/Google options await owner decisions (open point 34). #96 player page v2: tabs (Overview / Attack / Serve & receive / Matches), "you vs the league / vs your earlier matches" strips counted from league-tier data, attack map start → end from `own_x_m/own_y_m` (already published, no re-publish), grades in the "i" hint (AGENTS §13); migration `20261009100000_player_page_v2` NOT pushed yet. #99 reception vs defense: `analytics.passes` (migration `20261009120000_pass_map`, NOT pushed; no post-run change, no re-publish) + `PassMap` card; the real match has 24 credited receptions / 34 defenses, 54 with a seen destination.

**Identity (#85):** `TeamIdentityResolver` (`player_identity_mode:"team"`,
default) stamps P1A/P2A/P1B/P2B per frame; orientation = two-state LLR on
fixed anchors (replay: 4/4 switches, 0 stray, 211/211 GT contacts). The #87
live run confirms it end to end: the post-run squads are right on 33/33
serves and 166/166 touches. Within-half slot RATIFIED by the same owner
review (#88). Owed: entreno 0-flip run. Detail:
`docs/history/status_where_we_are_archive.md`.

**Production state (causal pass, unchanged):** weights
`volleyball_ball_best.pt` v3; match 720p upscaled `_up1080`; 30–32 ms/frame
(#89; 75 before, dump on); 212 actions on the #87 run; held-out P9–P33 contact F1 0.772, class 0.590;
overpass 0/18; serves near 8/16, far 0/17, 12 FP (`score_serves.py`).
Display-only observers: possession (#77–#79), ground contact (#80), squad
colours/labels. Pass-2 scripts (`relabel_serves`, `resolve_side_switches`,
`resolve_point_winners` 18/33, `consume_serve_evidence`) are SUPERSEDED by
`src/postrun` for points/serves/winners; kept as provenance. Entreno action
gate (causal): e1 0.706, e2 0.571, e3 1.0, e4 0.933, e5 0.923, e6 0.933,
e7 0.75 (same-session A/B only). Test suite **1228** (1222 pass, 5 skipped; `test_inbox` run-match order fails at HEAD, not #94 / #97 / #98).

**Player detector input (#94, default ON):** `player_bgr_input: true` passes BGR as-is (`false` = the old path; how to compare: Learnings). 4-track frames up on all 7 clips, stream F1 0.824→0.839, post-run identical; match stream labels 81/145→74/146; e3 contact sheet owed. Full text: `docs/history/status_where_we_are_archive.md` (#97).

**Speed (#89, results-neutral — AGENTS §12):** `prefetch_depth: 8` + `detector_fast_inference`: match 1955 → 783–836 s, clips 291 → 131 s, byte-identical to the pre-#94 goldens (= `player_bgr_input: false`). Bound: MediaPipe pose (open point 33). Full text: same archive (#94, #97).

**Held-out lock:** `ground_truth/20290928_entreno_vall_dhebron_serve_anchors.json`
= 19 serves; the video has NEVER been run; use only via a card "score
held-out once" with frozen rules (the post-run layer has not seen it either).

**STOP list (causal serve work):** no more px-space far-serve thresholds
tuned on the 17 match far serves; no relabeling reception as serve; no
vall_dhebron output looks. Serve START is now a post-run read — do not
reopen causal serve detection for it.

**Refuted/parked mechanisms:** list moved to
`docs/history/status_where_we_are_archive.md` (#90 block); never `src/`.

**Known defects:** `annotate_player_gt.py` + `src/db/ingest.py` seek on VFR
(allow-listed in `test_vfr_seek_guard.py`); stale comment at
`src/utils/config.py:101`; GT `20260920_match_ari_joan_contacts_p1_p8.txt`
P31 serve f24543 is 128 f before its reception (owner to confirm ~f24630).

## Active next (ranked)

0. ✅ **Owner security follow-through DONE (2026-10-07):** `supabase db push` (4 migrations), deploy doc 2.4/2.9/4/8, stats pages reviewed.
   Heights check done with the real heights: not good (V2 ±0.2 m stays FAIL; O3 would show relative heights only).
   Next picks (§5): I3 → O3 (relative heights, V2), N10/O2, O1+I4, N7/N9, F1.
1. ✅ **Product deployed (owner, DONE 2026-10-07):** `docs/deploy_web_platform.md` steps 0–7. Still open: publish 20260920 check
   (fantasy = txt footer), then action_overrides UI, in-app invites, `own_x_m` heatmaps (design §8 "Next"). **Owed (#98), in any order — each step is safe alone:** merge `spike-type-touch-vs-hard`; `supabase db push` (`20261009100000` + `20261009110000` + `20261009120000`); move `~/volley-prod` to that commit and run `make republish-all` THERE (this checkout's `.env.publish` is the local stack; an older prod checkout would rewrite the shared `output/` with the old rules); then look at the Attack tab on the real match.
2. **Second match / other venue through `make run-match`** (also the first out-of-sample test of #97 hard / touch) — the only
   21-point match so far is the one the layer was built on; practice clips
   and the sweep are the out-of-sample evidence.
3. **Landing line calls** (3 of 10 wrong): needed only for the last point
   and for kill-vs-out detail; a ground-plane read from raw detections of
   the resting ball is the candidate (open point 31).
4. E2 observers (identity drift / side-switch, display only, owner gate).
5. Deferred fix: comment `src/utils/config.py:101` (32f set-error fixed #90).
6. **Bugs found in #89 (results-changing → measure with a same-session
   A/B on e1–e7 + the match before fixing):** (a) `PlayerDetector` hands
   ultralytics an RGB frame it treats as BGR — the person model sees R/B
   swapped; (b) one MediaPipe video-mode `Pose` is shared by all players,
   so one player's landmarks seed the next one's ROI/smoothing.
7. **Speed left (results-neutral, open point 33):** pose on its own thread
   (~30 → ~26 ms/f); read-ahead for the `--debug-live` producer and the
   enrollment pre-pass (5 s per clip).
8. **Court positions (#101, open point 35):** owner looks at the before / after map, merges, then `make republish-all` from prod (every published position moves; no migration, no web change).

## Next task cards

*(Empty — cards appear here only while READY/pending; DONE/REFUTED cards are
archived under their session date in `docs/history/status_log_archive.md`.)*

## Open points

### Active

30. **Serve reliability.** Status: SOLVED POST-HOC (#87) — the post-run
    layer finds every serve of the match (33/33, half + squad, frame 32/33)
    and 5/5 on the practice clips; the causal stream stays near 8/16, far
    0/17, 12 FP and is no longer the source of point starts. Next: nothing
    causal (STOP list); SR4-FAR / SR3 are closed by supersession.
22. **Far-side serves.** Status: SOLVED POST-HOC (#87) — a far serve has no
    vertex (the tracker locks ~0.2 s after the hit), so its launch is the
    BIRTH of the track: far 17/17 found, frame within ±15 f on 16 (P31 = GT
    typo). Toss-tracked births read up to 15 f early. Next: none.
21. **Owner's match-feedback backlog.** (1) point count 33/33 DONE (#87);
    (2) per-point + per-action confidence surfaces: the reconstruction
    carries `evidence` (vertex / gap / structure), `flags` and the
    ball-death cross-check per point — UI unbuilt; (3) winner 33/33 DONE
    (next-serve rule); (4) side switches exact DONE; (5) player-number GT
    pass DONE #88 (owner CSV review, 0 corrections); (6) landing
    confidence: line calls 7/10 (open point 31). Next: (2) with the DB
    ingest (Active next 1).
2.  **Side-change survival (player identity) — status: orientation SOLVED
    (#85 replay: 4/4 switches, 0 stray, 211/211 GT contacts) AND per-player
    slot RATIFIED #88 (owner reviewed the 208-row attribution CSV: all
    correct).** Remaining: (b) entreno run to confirm 0 flips on
    switch-free footage. The 23 wrong-side action attributions in the
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
25. **Dig at ball death (owner-flagged, P15 f10180).** Status: handled in
    the post-run layer (#87): a vertex at sand level, or after which the
    ball only rolls, ends the point and is not a touch. Next: none unless
    the owner sees one in the play-by-play.
26. **One contact attributed to two players (owner-flagged: P16 f10703, P19
    f13074, P20 live flap).** Status: impossible by construction in the
    post-run touches (one state per vertex, duplicates merged within
    0.25 s). The causal stream still does it; not worth fixing there.
29. **Stale recording guide.** `docs/video_recording_guide.md` contradicts
    the validated long-axis geometry. Next (docs-only): rewrite to the
    long-axis spec + `scripts/probe_capture_spec.py` pre-flight (ffprobe:
    CFR/VFR, effective fps, resolution).
31. **Point-end REST / landing line calls.** The tracker drops the final
    descent by design (static suppression), so the post-run ball-death read
    exists on only 17/33 points and its in/out half is weak (3 of 10 wrong;
    the 7 reads that need no line call are all right). Harmless for winners
    (next serve decides) except on the LAST point. Next: read the resting
    ball from the dump's raw `removed` detections (it sits in-court at ratio
    0.93–0.98 of the ground prediction) and map its bottom point.
32. **Post-run layer residuals (#87).** (a) WHO RATIFIED #88 (owner review
    of the 208-touch CSV, 0 corrections; CSV = per-player GT); (b) built
    and tuned on ONE match — a second 21-point match is the real test;
    (c) needs the `--diag-dump` sidecar (49 MB, in memory until the run
    ends) — decide whether `make run` should always write a compact one;
    (d) blocks are not a label; (e) 1 observed touch is credited to nobody
    (10 more by alternation), 5 are placed as hidden touches; (f) FIXED #90:
    set/dig `error` = ball handling −1 (`handling_errors`); (g) #97 hard / touch: split fitted on this match's 32 labels (same score for 24–26°), owner looked at the sheet (#98): P10 f6320 = a second-touch poke that left flat from mid-court and P22 f16037 = a touch to the side that barely rose — both labels stand (TOUCH; read hard / untyped), nothing re-tuned; P30, P33, P19 not commented; swing vs poke needs pose in the dump. Next: (b).
33. **Speed, results-neutral (#89).** Shipped: read-ahead + exact detector
    fast path. Left, in order: (a) pose on its own thread, call order kept
    (~30 → ~26 ms/f; touches `ActionClassifier`); (b) read-ahead for the
    `--debug-live` producer and the enrollment pre-pass (5 s per clip);
    (c) re-verify the fast path before any ultralytics upgrade (it turns
    itself off on an unverified release; `venv/` is the only env).
34. **Web login: fewer code mails (#94, study only, `docs/web_login_study.md`).** Sessions already last until logout (no limit). Owner decides: (a) limit — 30 d (NIST AAL1) via `pg_cron` on free plan; (b) final domain (before passkeys); (c) second method — passkeys (beta, needs an options broker: the Auth lock blocks it) or Google (passes the lock). Then build A: local logout + "all devices", one URL.
35. **Published court positions (#100 diagnosed → #101 FIXED in code, output only; republish owed).** `src/postrun/positions.py`: `court_x_m` / `court_y_m` / `court_xy_m` are read in a net-anchored frame (the calibration's net-ground clicks) with the ball-box offset removed; the offset is per video, read off the end switches (20260920: 1.74 px closes dig / set / spike / overpass from 2.05–2.21 m to within ±0.16 m; spikes 2.70 / −0.30 → 1.40 / 1.40 m, the 2:49 kill 2.7 → 1.4 m, 1 of 39 held at the net). Decisions untouched (`DEPTH_SPLIT_BIAS_M` stays). Open: (a) it rests on the two halves being played alike — the players' feet show the same near/far gap, so a real part (wind) cannot be excluded; two serves into the net read no offset, one net-slide reads it; (b) a video without a switch (practice clips) stays uncorrected and holds across-net reads at the net; (c) a single position is ±0.6–0.8 m; a takeoff-from-the-feet read needs a higher camera or its own design; (d) in-sample on one match. Next: owner looks at `output/postrun/20260920_match/attack_map_now_vs_fixed.png`, then merge + `make republish-all` from prod.

### Parked / conditional

5.  **Same-team adjacent-player choice.** Needs the owner-specified engine
    (motion history + ball half, #46); scoreable only with stable-identity
    GT (2); `--ignore-player` stands until then.
6.  **Phase 2: offline global stitch.** Build only if match validation
    shows residual swaps/fragmentation phase 1 doesn't catch.
9.  **Overpass label lever.** Status: SOLVED POST-HOC (#87) — the crossing
    is known in hindsight (the next touch is on the other half): action
    0.982 on the match, overpass vs spike by contact height below the tape.
    Residual: soft "rainbow" attacks under ~2.15 m read as overpasses (2).
    C1–C4 are closed by supersession.
13. **Ace metric.** Status: DERIVED (#87) — `outcome: ace` on a serve the
    receivers never touch or touch once and lose (owner kill semantics);
    kill / error likewise. Matches the owner's point descriptions on the
    match except P18 (final attack unseen → no credit). Next: surface in
    the UI with open point 21.
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

**Post-run layer (#87)**
- Ball width IS depth: `1/width` is linear between the baselines (15.0 / 22.8 / 47.7 px far / net / near on the match), and a flight is ballistic so ONE robust line through `1/width` reads both of its ends; single frames are ±2 m at the far end.
- A ball in play reads ~1.3 m nearer the lens than it is (blur widens the box; resting balls measure 0.93–0.98 of the ground prediction): depth alone cannot split the metre around the net.
- The read that works at the net is ball depth minus the TOUCHER's stance depth: within −2…+2.7 m for the true toucher, beyond ±3.2 m for the nearest player of the other half (stance = feet 0.3–0.6 s before contact; a jump projects the feet deep).
- A far serve has no vertex — its launch is the track BIRTH (lock ~0.2 s after the hit); serve vs dead-time handling = starts beside a baseline, peaks ≥ 2.2 m, travels ≥ 5 m at ≥ 5.5 m/s. The dead-time crossing launches on the match peak < 2 m, start > 3 m inside the court (one lob) or start above any serve contact height (one junk track).
- In-rally trajectory vertices are touches (169 of 170 on the match), INCLUDING the reach-refused ones (22/22: real touches by a player whose box was stale); the causal stream's false contacts are dead-time ones (43 on the Oct 2 run) plus the ball's own death (net, sand, pick-up).
- Winner = next server is the strong read (33/33); landing in/out through the 4-click homography is the weak one (7/10) — never let a line call overrule a serve.
- Image-plane speed cannot tell a toss apex from a serve flying straight at the lens; an image-plane velocity step is perspective once the ball has left its toss depth.
- A tracking gap is the same flight only if the ball reappears where gravity puts it; a short gap it leaves on another trajectory hides a touch (gap vertex), but only if the ball was flying on both sides — a resting ball that "moves" is a re-lock onto another ball.
- Spike vs overpass on a possession-ending touch = contact height against the tape (net − 0.28 m); pokes and bump passes overlap only around 2.05 m, and the safe label there is overpass.
- Hard vs touch (#97): image ascent in px is depth-blind on a long-axis camera (a ball above the lens climbs in the picture by flying toward it; 57 px was fitted at 2.3× the beach scale). Vertical launch speed is the robust number (three depth reads agree within 0.2 m/s); horizontal speed is not — the width trend over-reads a ball flying AWAY by up to 30 % (seen through the net its box shrinks) → read it twice (trend; attack → next touch), type only on agreement.
- Amateur "hard" is not downward (#97): 13 of 15 owner-typed drives leave at −4…+24° and 6–15 m/s and stay up 0.3–1.1 s; "touch" is a lob (≥ 26°) or a slow drop (1.8 m/s). The classes overlap for real at ~19–31° (hard up to 30.6°, touch down to 19.4°; width trend, attack → dig ends and a gravity-as-ruler fit all keep them there): swing vs poke needs pose, not ball flight — do not re-tune the split on the same labels.
- The classifier dates a vertex 1–3 frames BEFORE the picture shows the turn; a launch fit that starts at the vertex swallows the set's descent (type score 23/29 vs 26/29) → `attack_shape.hit_frame` (largest image-velocity step within −0.08…+0.25 s).
- Hard / touch is asymmetric (owner, #98): a ball that RISES after the attack is almost always a touch, but a touch need not rise (a flat second-touch poke, a touch to the side) → `hard` is the weaker read; the flight cannot see the swing.
- Practice clips exposed five mechanism bugs the match never hit (re-lock gap vertex, net-fault timing, serve-into-net read, toss-hit search, serve-less rally): run `score_postrun_entreno.py` on every change.

**GT / scoring semantics**
- Contacts dictation has two dialects; `gt_point_start_end.txt` is game-state VIDEO, not the match; match serve team = winner-of-previous; `touch_number` is per-TEAM possession; kill = direct fall OR dug-and-dies; GT edits only via owner-ratified contact sheets; re-adjudicate GT when the model shifts streams.
- Two "point start" sources in `ground_truth/` are PREDICTIONS, not anchors (owner anchor = serve contact frame; all 33 points have the serve as earliest contact).
- GT class wording IS the label: "bump pass" ⇒ overpass even into-the-net (f24948); `missatr` marks are NOT exhaustive; GT-file `landing` ≠ readable (parser extraction issue).
- e2 recorded F1 0.571 does not reproduce (0.400 on both fresh arms) — same-session A/B is the only valid comparison.
- PRECISION BUDGET: `m ≤ 2k − labels_needed` (fires allowed for a label lever); include a sanity-check row in every scoring table.
- Label-lever harness: `probe_label_ceilings.py` (vocabulary ceilings), the label-only oracle is trivially 1.000 — bar is class_accuracy.
- Layer 1 is degenerate on the match (157/185 contacts = `bump_set`); every dig/set/overpass/serve label is `ActionContextResolver._decide` keyed on `_poss_touch` — touch-count errors are downstream of MISSING contacts (starved 33/43, not mis-reset).

**Perf / infra**
- **`make republish-all` → `Connection refused` (#98):** this checkout's `.env.publish` is the LOCAL stack (`127.0.0.1:54321`); the hosted URL is only in `~/volley-prod/.env.publish`. `~/volley-prod/output` is a symlink to this checkout's `output/`, so republish from prod only once prod has the current `src/postrun`.
- **A published match no longer needs its video (#98):** the original's hash lives in `<run_dir>/video_identity.json` (written when hashed; for an older run taken once from `publish_preview`), thumbnails are reused from `<run_dir>/thumbs/`. Before: a deleted original sent `sha256: null` and the database refused it as "a different video".
- **Reception vs defense (#99):** both are `dig` (touch 1) in the post-run layer; the touch BEFORE it decides — serve = reception, spike / overpass from the other team = defense. Where it went = the same team's next touch, if observed and positioned (`own_x_m/own_y_m`, already published). Use `team`, not `side`, in SQL (the smoke fixture has no `side`). 20260920: P1A 3/11, P2A 6/7, P1B 7/10, P2B 8/6 receptions/defenses, 54 of 58 with a destination: ~14 passes per player per match, so a per-match spread is thin.
- **Schema check without the local Supabase stack (#96):** `colima start`, then `docker run -d --name volley_pg_check -e POSTGRES_PASSWORD=postgres -v "$PWD":"$PWD":ro public.ecr.aws/supabase/postgres:17.11.0.002`, a `psql` shim on PATH (`exec docker exec -i volley_pg_check psql "$@"`) and `PG_DSN=postgresql://postgres:postgres@127.0.0.1:5432/postgres make schema-check`; remove the container after.
- Pose gating shipped: 84.8 → 68.0 ms/f byte-identical. #89: the "detector floor ~48 ms/f" was half overhead — a YOLO forward is ~11 ms; ultralytics' NMS + rescale on MPS cost 10–20 ms/f in GPU syncs (3 ms on CPU).
- MPS (M3 Pro, #89): run-to-run deterministic (HEAD reproduces `output/postrun` byte for byte); batch>1 is bit-identical to batch-1 but NOT faster (compute-bound); two models driven from two threads stay bit-identical.
- CPU NMS ≠ MPS NMS in general: ~1 frame per 1000 has a box pair with IoU within 1e-5 of the 0.7 threshold, hence the certificate + device fallback in `yolo_inference.py`. Dead speed levers: batching, a detection cache (the loop is pose-bound), lazy pose (MediaPipe video-mode state → not exact).
- Byte-identical gate for results-neutral changes: `scripts/compare_runs.py` + `cmp diag.jsonl` against `output/postrun/*` (AGENTS §12); `scripts/` already had the tool — check before writing one.
- Found while profiling, NOT touched (results-changing, impact unmeasured): one MediaPipe `Pose(static_image_mode=False)` is shared by all players (A's landmarks seed B's ROI/smoothing). Its sibling, `PlayerDetector.preprocess_frame` handing ultralytics RGB it reads as BGR, was fixed in #94.
- #94 `player_bgr_input` (default `true`): `false` reproduces every pre-#94 artifact byte for byte (`output/postrun/*` are that arm; only `processed_at` differs). Compare: `venv/bin/python -m src.main <video> --output-dir <dir> --config <json with {"player_bgr_input": false}> --diag-dump <dir>/diag.jsonl`. The old A/B hack (`ab_wrap.py`) is no longer needed. `evaluate.py` on `src.main` output needs the `frame_number`→`frame` adapter and a `{"actions": [...]}` file.
- VFR: `CAP_PROP_POS_FRAMES` lands −28..+30 f off — decode spans sequentially (`test_vfr_seek_guard.py`); two KNOWN-ISSUE allow-lists: `annotate_player_gt.py`, `src/db/ingest.py`.
- Delegation: >1 KB prompt kills the child pi (EXIT 137) — few hundred bytes + the child reads a brief file.
- Retraining: four-leg gate; fine-tune FROM `best.pt`; mine frames with NO pre-labels.
- Web/infra facts (#90, checked 2026-10-06): Telegram bot `getFile` caps 20 MB (local Bot API server: 2000 MB), undelivered updates kept 24 h, "video" sends re-encode; Supabase free = 50 MB/file, 1 GB storage, 500 MB DB, pauses after 7 idle days; torch for Intel macOS ends at 2.2.x.
- Court positions (#91, 20260920, 136 credited touches, ball at the touch vs the toucher's feet — a noisy reference, NOT GT): agree ~0.4 m across / ~0.7 m along at 1σ, 83–96 % within 2×; flight fits have 54+ width samples so the floor is systematic, not noise. Ground reads at ±4 px: ±0.1 m depth at the near baseline, ±1.1 m at the far one (lens 1.5 m up). `geometry.ground_read_error_m` / `ball_read_error_m` (the ground one shrinks by itself with a higher tripod).
- **Depth resolution, low beach camera (#100, 20260920: lens ~1.25 m up, ~7.3 m behind the near baseline, 720p source):** the sand gets 9 px per metre of depth at the net (4 at the far baseline) — 5 cm of sand relief or a 5 px box edge ≈ 0.6 m; the ball gets 1.6 px of width per metre (1.1 native) — 1 px ≈ 0.6 m. Practice venues (lens ~2.9–3.0 m, 1080p): 20–24 px/m on the sand. Height buys every GROUND read (feet, landings, calibration clicks) linearly and nothing for ball-width depth; that one needs pixels (1080p = 1.5×). The corner midline is the net on no venue (net-ground clicks read 8.05 / 9.33 beach, 7.69 / 7.82 e3, 7.40 / 7.47 vall d'Hebron; a 4 px far-corner click = 1 m). Ball vs grounded feet (95 digs / sets, net-anchored ground): the ball reads 0.6–0.9 m netward on the near half, 0.8–1.2 m on the far half — neither is GT. Tracker boxes lag a jump and labels drop at the hit: a takeoff read needs its own design. The play-by-play clock is frame / fps (3:10 for the kill the video shows at 2:49, VFR).
- **Ball-width depth bias (#101, 20260920):** the near/far gap is the SAME for every kind of touch (dig 2.05, set 2.21, spike 2.06, overpass 2.15 m) — one cause, not an attack effect; near serves sit on their server (ball − feet −0.24 m, 16 serves), so the read is unbiased at the near baseline and the correction must be in PIXELS (little near the lens, ~1 m at the net, more beyond), not a flat metre shift nor a net shift. Tried and dropped: reading depth in a window at the hit (trajectory-kink aligned, in / out / same-half flights) — no tighter than the whole-flight fits; a ball seen in the net band (rows between tape and bottom band) boxes 1.15 px narrower. Recorded touch frames sit ~2 f before the kink. Ball vs feet is not a referee here: person boxes read toward the lens too.
- Postgres: `jsonb_populate_recordset` fills a MISSING key from its base record (NULL), never the column DEFAULT — pass a base row carrying the defaults (#90 smoke test).
- V1 (#92 → #97, 20260920, 32 owner-typed spikes; bars 0.85 / 0.80): causal `SpikeAnalyzer` types 16, 10 right → FAIL; post-run `attack_shape` types 29, 26 right (0.897 / 0.906) → bars met IN-SAMPLE; practice 6/6 on 6 of 8; split 18–32° gives 0.82–0.90. `scripts/score_spike_type.py --clips output/postrun --rows`.
- V2 (#92): live net crossings with a well-conditioned timing clear the tape (33/33, median +0.61 m) but the far half reads people 5–12 % shorter and digs 0.29 m higher than near → no "±0.2 m". Dead-time balls rolling past the net read 2.3 m under the tape (on the sand) — always filter to rallies. `scripts/check_heights.py`.
- SQL stats (#92): possession = running count of `touch_number = 1` per point (0 = serve, 1 = reception); a `bool_or` over a column that is NULL for most rows returns NULL, not false — `coalesce` it. New Supabase functions get EXECUTE for anon by default: revoke explicitly.
- Supabase grants (#93, checked 2026-10-06): projects created since 2026-05-30 grant NO table/sequence privilege to `anon`/`authenticated`/`service_role` (changelog 45329); the local CLI stack (2.119) still grants ALL, so local runs hid it. Every table/view needs a `GRANT` in its migration; the test stub keeps the permissive default and `rls_smoke.sql` asserts `anon` holds nothing. `supabase/config.toml` configures ONLY the local stack — hosted Auth settings are dashboard switches, proven by `GET /auth/v1/settings`.
- Supabase Auth (#93, measured on the local stack): with sign-ups off, an invited user who has not opened the invite link gets 422 `signup_disabled` on `/otp` — the link is the only way in and it dies with the email OTP expiry (1 h), so never shorten that. Code length (6–10) is the lever against guessing; the login form takes any. `/otp` answers unknown and known emails differently and cannot be told not to: the fix is the login function (same answer for all) plus CAPTCHA protection ON with a secret no page has a widget for — GoTrue v2.197 then refuses every public mail-sending route (`/otp`, `/signup`, `/recover`, `/magiclink`, `/resend`) identically, while requests with the service key skip the check (`verifyCaptcha`); `/verify` answers a wrong code and an unknown address alike.
- Supabase Auth lock (#94, read in `supabase/auth` master 2026-10-08): CAPTCHA guards `/otp` `/magiclink` `/recover` `/resend` `/signup` `/sso`, `/token` except `refresh_token`/`pkce`/`id_token` grants, and `/passkeys/authentication/options` — password + passkey sign-in need a broker, OAuth and refresh pass; with sign-ups off an OAuth identity links to the invited account with the same verified email. `supabase-js` `signOut()` defaults to scope `global` (logs out every device).
- Edge functions (#93): `EdgeRuntime.waitUntil` exists only in a USER worker (the platform's way of running a function), not when the file is the runtime's main service — guard it; a function added while the local stack runs is not served (404) until the stack restarts. `pg_net` was rejected for the broker: its tables and `net.http_post` are granted to `anon` and owned by `supabase_admin`, so a migration cannot revoke that.

## Session index (one line each)
- #103 **"Last match" (n1) added to the stats time filter menu (`MATCH_PRESETS` = 1, 3, 5, 10); web only, no migration**
- #102 **Feedback button on the web: bug / suggestion + ≤3 screenshots → `feedback` table + private `feedback-media` bucket (`20261009130000`); Settings "My reports", Admin → Feedback, `make feedback` → `output/feedback/`**
- #101 **Published court positions fixed, output only (`positions.py`): net = net-ground clicks, ball-box offset (1.74 px) from the end switches; spikes 2.70 / −0.30 → 1.40 / 1.40 m; decisions byte-identical; schema 4; republish owed**
- #100 **Attack-map depth diagnosed (no code): published ball depth keeps a ~1.3 m shift toward the lens and the net is not the corner midline; the owner's 2:49 kill reads 2.7 m off the net, frames say ~1 m; fix = open point 35**
- #99b **Compare card redrawn as GAP TO THE LEAGUE: centre = average, more = right (never flipped), shaded too-close zone = where the 95% ranges overlap, blue / orange verdict bars, fantasy last; no average yet = bars from zero**
- #99 **Reception vs defense: a dig after a serve / after an attack; "Where the pass went" card (map start → next touch + spread ring around the player's own usual spot, no fixed target); `analytics.passes` (`20261009120000`)**
- #98 **Web shows hard / touch: map line = shot (heavy hard, dotted touch, dashed free ball) + Shot filter; "By shot" card from SQL `analytics.shots` (`20261009110000`); pre-#97 publish = "not read"; publish error = local-stack env**
- #97 **Hard / touch attacks read POST-RUN (`attack_shape.py`): launch elevation ≥25° or <5 m/s = touch, two speed reads must agree; match 26/29 on 29 of 32 (causal 10/16 on 16), practice 6/6; recon schema 3**
- #96 **Player page v2: 4 tabs, 5 count tiles, "you vs league / vs earlier" strips (verdict only when 95% ranges do not overlap), attack map with lines (kill blue, dug grey, error red; dashed = free ball), "i" hints replace grade letters**
- #95 **Admin can mark a slot "Unknown player": its stats stay in the match, never in a ranking or profile; re-tag later from Players → Unknown players; also `previews` block in wrangler.jsonc (PR build)**
- #94 **Player detector got RGB frames ultralytics reads as BGR: now passes BGR (`player_bgr_input`, default ON; `false` = old path); 4-track frames up on all 7 clips, stream F1 0.824→0.839, post-run identical; match stream labels −7**
- #94b **Web login study (docs only): sessions already persist without limit; 10-07 re-logins = other URLs / global logout / link in another browser; options A–E incl. passkeys + Google vs the Auth lock; owner picks**
- #93 **Pre-launch security review + fixes: explicit grants (new Supabase projects grant none), CSP headers, login function (one answer per email) + Auth lock, 8-digit code, `.env.publish` 600, report card by tier, `main` protected**
- #92 **Stats "Now" picks BUILT: windows, side-out/break, serve targets, reception outcome, hitting %, report card, /measure, republish-all; V1 hard/touch FAILS (10/16 right on 16 of 32), V2 ±0.2 m heights FAIL (net clearance passes)**
- #91 **Web "Where they land": landings 17→57 of 63 attacks placed (touch x from the ball read), per-axis position error + `landing_result`; recon schema 2, new migration, map with uncertainty areas + out-of-court margin**
- #91 **Stats/fantasy brainstorm (docs-only): measurement budget from the calibrations (left–right cm-precise, height ±0.15 m, far depth weak), owner ideas graded, new ideas + validation cards; owner picks**
- #90 **Video→web platform designed, ratified + BUILT: supabase/ (RLS, RPCs, fantasy rule tables), src/publish (publisher, Drive inbox, backup), webapp/ SPA, launchd, CI; deploy guide; 32f fixed; owner deploys next**
- #89 **Offline run 2.3–2.5× faster, byte-identical: read-ahead decode+detectors (`frame_prefetch.py`) + exact detector fast path (`yolo_inference.py`); match 1955→783 s, 7 clips 291→131 s; suite 1139**
- #88 **Owner ratified post-run per-player attributions: 208-touch review CSV all correct, 0 corrections → per-player GT; found fantasy set-error gap (P6 f3229)**
- #87 **POST-RUN RECONSTRUCTION (`src/postrun`): 20260920 points 33/33, serves 33/33, winners 33/33, score A 21–B 12 exact; touches P 0.976 / action 0.982 / half 1.000, 0 rule breaks; practice P 52/53; diag schema 4**
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
## Log (newest first)

### 2026-10-09 (hundred-and-third session) — "last match" on the time filter

**Asked (owner):** add a "last match" option to the stats time filter (the menu started at "last 3 matches").

**Built.** `MATCH_PRESETS` in `webapp/src/lib/window.ts` is now `[1, 3, 5, 10]`; the key `n1` (label "last match", `p_last_n => 1`)
was already supported by `windowParams` / `windowLabel` and the SQL window (`rls_smoke.sql` pins last-1), so no migration and no
demo change. vitest +1 (65), typecheck clean.

### 2026-10-09 (hundred-and-second session) — #102: a Feedback button (bugs / suggestions with screenshots)

**Asked (owner):** a "suggest / report a bug" button on the web; GitHub issues need an account, so onboarded people must be able to
send bugs or ideas easily, with screenshots, "so that we can get them easily and tackle them in a session".
**Decisions (owner):** reports stay in Supabase only (no GitHub mirror, no new secret or host); members see the status of what they sent.

**Built.** Migration `20261009130000_feedback` (NOT pushed): table `feedback` (kind bug / suggestion, text, page, context, ≤3
screenshot paths, status open / done / dismissed, admin note) + private bucket `feedback-media` (1 MB, images only, a member writes
under `<user id>/` only). `send_feedback()` is the only way a row gets in (author = caller, every screenshot must exist in the caller's
folder, 20 reports a day); uploads capped at 30 a day (`feedback_upload_allowed()`); a member reads their own, admins read all and set
status + note, nobody rewrites the text, `anon` nothing. Web: `Feedback` button in the top bar → native `<dialog>` (kind, text, pick or
paste screenshots, downscaled in the browser to ≤1600 px JPEG via `createImageBitmap`, so no CSP change), sends route + viewport +
browser + build (`__BUILD__` = Cloudflare commit); Settings → "My reports" (status + reply); Admin → Feedback (open count on the tab,
Done / Not planned / Reopen, note). Laptop: `make feedback` (`src/publish/feedback.py`) replaces `output/feedback/` with `index.md` +
`<id>_<kind>/report.md` + screenshots; `DONE="3 5" NOTE=...` / `DISMISS=` close reports from a session. `make backup` exports the table.

**Verified:** schema check 5/5 on a throwaway `supabase/postgres:17` (smoke: own folder only, foreign / missing screenshot refused,
direct insert refused, daily limit, member vs member vs admin, column grants); `tests/test_feedback_pull.py` 3; vitest 64, typecheck,
oxlint, build; demo mode driven in Chrome at 1100 px and 390 px (send with a 2400 px image → 1600 px, Settings, Admin, close), 0
console errors.

**Not done / owed:** `supabase db push` (4 migrations now owed) and a first report on the hosted project — the storage policies and the
PATCH with the secret key ran only against the stub / a fake. No notification on a new report (Admin tab count or `make feedback`).

### 2026-10-09 (hundred-and-first session) — #101: published court positions — net-anchored, ball-box offset from the end switches

**Asked (owner):** "yes, let's try it out and see how the new map plots" — build the #100 fix and plot the four players.

**Diagnosed first (it changed the fix):** (1) net clicks: kept — the corner midline is 0.05 / 1.3 m off the clicked net, a ball at
the net is 23.7 px (model 22.8). (2) Depth "at the hit": DROPPED — kink-aligned windows over the arriving, leaving or same-half
flight are no tighter than the whole-flight fits (spike IQR 0.9 m either way). (3) The rest is not an attack effect: every kind
of touch shows the same near/far gap (dig 2.05, set 2.21, spike 2.06, overpass 2.15 m), near serves sit on their server (−0.24 m,
16 serves: no bias at the near baseline), so it is a box a fixed number of pixels wider than the ball, not a metre shift.

**Built (`src/postrun/positions.py`, output only):** `CourtPositions` (three depth anchors, two ground homographies sharing the
clicked net line; no clicks or a slipped click = the corner model, exactly) + `calibrate_width_bias` (one offset that closes the
gap of every kind with ≥5 touches per half; refused without a side switch, with <2 kinds, outside 12 % of the ball's width at the
net, or when a kind stays >0.6 m apart). `Touch.pos_*` / `RallyEnd.pos_xy*` feed `court_x_m` / `court_y_m` / `court_err_m` /
`court_xy_m`; a touch that reads across the net is held at it; `positions` block in the JSON; recon schema 4.

**Measured (20260920):** offset 1.74 px, gaps after −0.16 / +0.14 / 0.00 / +0.09 m. Spikes 2.70 / −0.30 → 1.40 / 1.40 m (11 far
starts across the net → 0; 1 of 39 held at the net). Per player near | far: P1A 1.55 (6) | 2.30 (1), P2A 1.35 | 1.20, P1B 1.40 |
1.70 (2), P2B 1.30 | 1.40; the 2:49 kill 2.7 → 1.4 m (frames: takeoff 0.8–1.3 m). All 170 positions move 0.5–2.4 m away from the
lens. **Neutral:** everything but the position keys identical on the match and e1–e7 (JSON + txt `cmp`); `score_postrun` output
identical (33/33, winners 33/33, P 0.976 / R 0.933, 0 rule breaks); practice 5/5 serves, P 52/53; sweep 88 rows, none loses a
point or a winner; hard / touch 26/29. Tests +8 (suite 1239: 1233 pass, 5 skipped, the known `test_inbox` failure).

**Not settled (open point 35):** the players' feet show the same gap, so part may be real play; two serves into the net read no
offset; practice clips (no switch) stay uncorrected; in-sample on one match. Plot: `output/postrun/20260920_match/attack_map_now_vs_fixed.png`.

**Not done / owed:** owner look, merge, `make republish-all` from prod (the on-disk `match_reconstruction.json` was left as is).
