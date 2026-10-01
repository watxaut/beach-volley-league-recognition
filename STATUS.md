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

**Last updated:** 2026-10-02 (fifty-fifth session, **planning only: the
serve-reliability plan and a course correction**, `docs/serve_reliability_plan.md`,
open point **30**). Measured honestly, serves are unreliable on BOTH sides. At
contact level (±15 f, match P1-P33) the production stream gets near **8/16**, far
**0/17**, with 12 false serve emissions (recall 0.24, precision 0.40). The far-only
evidence layer's "14/17 at zero FP" is **in-sample**: the operating point was swept
on all 17 far serves, and its held-out binding is **4/12**. The far-serve track had
been optimising a proxy (a frame-exact far contact in the action stream) on one
match. The plan replaces it with a per-point **serve record** covering both sides
(time, side/squad, server, outcome), built post-hoc from the existing evidence plus
two signals never used before: the **audio track** (real AAC in every video, never
read) and the **beach serving rules** (decoded jointly across the match). It also
asks the owner for cheap serve-only GT on two new sessions. Nothing in `src/`,
`scripts/` or GT changed. STATUS was lean-trimmed: the #48-#54 header chain, the #54
"Where we are" block and Log #50-#52 were moved VERBATIM to `docs/history/`.

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

**Serves are the active track and they are NOT reliable (#55,
`docs/serve_reliability_plan.md`, open point 30).**

Honest per-side serve baseline (contact level, ±15 f, the real match):

| stream | near | far | other |
|---|---|---|---|
| production | **8/16** | **0/17** | 12 FP emissions; held-out P9-P33 near 7/13, far 0/12 |
| entreno e2-e7 (all near) | 4/5 | — | e2 missed |
| far-only evidence layer | not observed | 14/17 anchored (**in-sample**), bound **9/17** (held-out **4/12**) | 1 owner FP |

`docs/g3_heldout_p9_p33.md`'s near 11/13 counts production OR pass-2 serves. The
production stream alone is 7/13.

**Plan: SR0-SR7.**
- **SR0:** one serve scorer, per side, dev vs held-out.
- **SR1:** near-serve miss taxonomy.
- **SR2:** audio onset probe (diagnose-only).
- **SR3:** OWNER serve-only GT on `20290928_entreno_vall_dhebron.mp4` + the 55-min
  `Entreno Vall Hebron i Partits - 05 05 2025.mp4` (that one needs calibration).
- **SR4:** per-point serve record, both sides, post-hoc.
- **SR5:** beach-rules serve-sequence decoding.
- **SR6:** ace / service fault.
- **SR7:** learned detector, deferred until ≥3 sessions of serve GT.

**STOP list:** no more px-space or contact-geometry far-serve thresholds, selector
constants, or tracker admission tuned on the 17 match far serves. No relabeling of
the reception as the serve.

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
  - `consume_serve_evidence.py`: far-only, 9/17 bound.
- **`--serve-events` observers:** default OFF. Inertness is measured
  (byte-identical).
- **Entreno gate record** (`evaluate --ignore-player` F1): e1 0.706, e2 0.571,
  e3 1.0, e4 0.933, e5 0.923, e6 0.933, e7 0.75. Suite **1036**.

**Refuted and parked** (do not reopen without new data): T5 tracker admission, R1
departure gate, S1 looming, scale-aware geometry, M1 far-end crop, possession
signal, overpass width crossing, R2 confidence calibration.

**Known defects:** `scripts/annotate_player_gt.py` and `src/db/ingest.py` seek on
VFR. Both are allow-listed in `tests/test_vfr_seek_guard.py`. Fix the annotator
before any frame-shown annotation pass.

**Active next (ranked):**
1. SR0.
2. SR1 and SR2, one per session.
3. Now and in parallel (owner): SR3, plus decisions D2/D3.
4. SR4, then SR5, then SR6.

The non-serve backlog is unchanged: the label bucket (open point 9), the reach-gate
bucket, e4/e5/e6 re-adjudication, and the first run of the vall_dhebron video
(folded into SR3).

**Deferred triggers:** unchanged (detector v4, T7/T10, T6, T8, T12, R2), with one
exception. T9's PTS timebase is pulled forward, because SR2/SR3 map audio and
dictated timestamps to frames by PTS.

The full #54 block (production facts, G0-G4/S0-S4 histories) is archived verbatim in
`docs/history/status_where_we_are_archive.md`.

## Open points

Ranked backlog. One compact entry per point: current status, the problem,
the next step. Numbers are stable across reorganizations — reference them
("point 22") in sessions and commits. Full per-point histories: grep the
point number in `docs/history/`.

### Active

30. **Serve reliability, BOTH sides (new, #55; supersedes point 22's
    far-only framing).**
    - **Status:** PLANNED (`docs/serve_reliability_plan.md`).
    - **Problem:** production serve recall is 8/33 (near 8/16, far 0/17) and
      precision 0.40. The far evidence layer is 14/17 in-sample, 4/12 held-out
      binding. The near side has no plan. Audio and the beach serving rules are
      unused.
    - **Acceptance** (on a session NOT used for design, ±15 f): recall ≥0.90 on
      each side, side/squad ≥0.95, ≤0.1 false records per point, server identity
      ≥0.90 after SR5. If SR4 is below 0.75 on either side held-out, stop hand
      rules and go to SR7 when its trigger fires.
    - **Tasks:**
      - [ ] **SR0** `scripts/score_serves.py`: every stream (production, pass-2,
        serve_evidence, GAME_ON starts) scored per side, dev / held-out / new
        session. Gate: reproduces near 8/16, far 0/17, 12 FP.
      - [ ] **SR1** near-serve miss taxonomy (8 match + e2), diagnose-only.
      - [ ] **SR2** `scripts/probe_audio_onsets.py`, diagnose-only, PTS-mapped.
        Kills: K1 onset at <70% of serves on either side; K2 dead-time-onset
        proposer precision <0.8 on dev; K3 far onset rate more than 15 pts below
        near.
      - [ ] **SR3 (OWNER)** serve-only GT (`mm:ss.s near|far server outcome`) on
        vall_dhebron + 05-05-2025 (calibrate first). Target ≥60 serves, both
        sides. Worker: run both videos with `--serve-events`.
      - [ ] **SR4** per-point serve record (`output/serve_records.json`): opener
        gate, then a side vote (runway / behind-baseline / width trend / first
        receiver side / structural arm), then the time (audio if SR2 survives).
        Optional toss/pose check for the pre-serve-handling FPs. Promotion =
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
      - **D1:** audio as a pipeline input (after SR2; it is a new perception input
        outside §6's rule).
      - **D2:** serve-only GT + calibration.
      - **D3:** the post-hoc serve record becomes THE serve product, and the
        causal far-serve contact chase stops.

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

## Session index (one line each)
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
