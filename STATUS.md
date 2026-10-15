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

Last updated: **2026-10-14 (116th session) — #116 web: no home page (`/` = the member's own player page, "My stats"), a Settings button instead of the name, match details on the admin page (venue from a list, match type, tournament + level; migration `20261014120000_match_details`, NOT pushed) and a "Same type" reference in the player comparison.**
#115 (blocks as a hidden post-run label), #113 (web player page v3; merged, pushed and deployed by the owner), #112 (masnou: a new beach video, calibrated by hand), #111 (1230: two lost rallies), #110 (automatic court calibration), #109 (1100 vs the owner's table), #108 (two more videos run), #107 (attack clips), #106 (20261010 = the owner's sequence), #105 (who is who post-run), #104 (second match, diagnosis), #102 (Feedback button), #101 (net-anchored court positions), #99 (reception vs defense), #98 / #97 (hard / touch), #96 (player page v2), #95 (unknown-player slots) and #90 (platform) lie underneath.

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
  touch; block = hidden, uncredited label (#115); ball-handling error not perceptible →
  manual override in the review UI.
- Critical path: owner player gate (32a) → ingest `match_reconstruction.json`
  into the DB → points-table UI (14e) + fantasy. Rollout gate = fast human
  review of the play-by-play.


## Where we are

**Post-run reconstruction (#87, `src/postrun`, `docs/postrun_reconstruction.md`).**
Offline layer over the `--diag-dump` sidecar (schema 4), ~3 s per match, no
decode: ball timeline (vertices incl. reach-refused ones, births/deaths, gap
vertices, one robust depth line per flight) → points (serve = launch beside a
baseline that clears the net and reaches the other half, at receivers standing
side by side (#106); far serve = track BIRTH; end = sand / net / air-time, a
landing read where the fall stops) → touches (one shortest path per rally
over half × touch number × player: reception to the receivers, ≤3 touches,
players alternate; hidden touches keep the count, never credited; a seen touch out of reach is credited by alternation) → labels
(attack = contact ≥ 1.23 × the toucher's standing height, #106) → match (winner = next server; ball death is the cross-check; score closes the
last point; service order names every server). All constants are metres /
seconds / costs through the calibration (net height reads 2.43 m beach,
2.42 m practice). `make run-match` / `make postrun`; output
`match_reconstruction.json` + play-by-play `.txt` + per-player stats/fantasy.

**Record (20260920, `scripts/score_postrun.py`, ±15 f):** points 33/33, 0
false; serve half 33/33, squad 33/33, frame 32/33 (P31 = GT typo); winners
33/33, score A 21 – B 12 exact, switches after 7/14/21/28; touches P 0.976 /
R 0.933, action 0.988 (#106; 0.982 before), half 1.000, squad 1.000; 0 rule breaks (causal stream:
P 0.711 / R 0.815 / action 0.559 / half 0.759; 23 same-player-twice, 45
fourth touches). Practice e1–e7: serves 5/5, P 52/53, action 52/52. Sweep (130
moves): no row loses a point or a winner; worst P 0.965, action 0.970.
**Per-player WHO: RATIFIED (#88).** Owner reviewed the 208-row attribution
CSV — every player right, 0 corrections (incl. the 10 by-alternation and
rotation-named servers); the CSV is the per-player GT. Line calls: 3 of 10
in/out reads wrong (overridden by the next serve).

**Attack type (#97, `attack_shape.py`): hard / touch is a POST-RUN read.** The flight after the attack in metres:
vertical launch speed (ballistic fit) + horizontal speed read twice (ball-width trend; attack → next touch). Touch =
launch elevation ≥ 25° or leaving under 5 m/s, hard = the rest, NO type when the two reads disagree. Match, 32
owner-typed spikes: 26/29 right, 29 typed (causal `SpikeAnalyzer`: 10/16 on 16) — V1 bars met, IN-SAMPLE; practice
6/6 on 6 of 8. Recon schema 3 (`spike_type`, `launch`); the bundle publishes it. **Web (#98):** `player_profile` → `analytics.shots` (hard / touch / free / unread × n, kills, errors; adds up to `n_attacks`) + guarded `landings[].type` (migration `20261009110000_attack_shots`, NOT pushed): only a row with `extra.launch` has a type, so a pre-#97 publish reads "not read". Attack map: line = shot, `Shot` filter; "By shot" card; grade B. **Compare (#113, replaces the #99 gap chart):** a table, You / League / gap: the arrow = which way the number goes, blue / orange = better / worse, the row's wash pale while chance could explain the gap and strong + `clear` once the two 95 % ranges no longer overlap (`gapOf` / `gapTint`, fantasy untinted and last); the same line sits under the tiles of the Attack / Serve / Receive tabs (`compareByKey`).
**Court positions (#101, `positions.py`, OUTPUT ONLY, recon schema 4):** published `court_x_m` / `court_y_m` / `court_xy_m` = net-anchored frame (net-ground clicks) + per-video ball-box offset from the end switches (20260920: 1.74 px; spikes 1.40 m off the net from both halves, was 2.70 / −0.30). Points / touches / labels / winners / txt byte-identical (match + e1–e7); needs `make republish-all`; ±0.6–0.8 m per position (open point 35).

**Automatic court calibration (#110, BUILT, inbox in `propose` — AGENTS §14, `docs/auto_calibration.md`).** `src/detection/court_autocalibration.py` finds the 8 points from a median plate, no model: tape by colour on the sand, each tape followed as it lies, net tape by colour uniformity + its two edges, far baseline where a sideline's tape ends / far tape shows / the camera's known focal length agrees — one read is a proposal, two a calibration. 6 views (dev e3, 1000, 20260920; 1100, 1200, 1230 scored frozen): 5 accepted, beach refused; held-out corners ≤ 10 px from the clicks, widths ≤ 1.3 %; e1–e7's near-left corner is ~90 px outside the frame. Every existing dump replays with the same points, serving teams and winners; full re-run of 1100 = the manual run against the owner's table. `make autocalibrate`, `make calibrate` (A = accept), `VOLLEY_AUTO_CALIBRATION`. **7th view, 20261012_1130 (beach, black tape, yellow net): REFUSED ("no court"); `calibrations/…json` read by hand (`source: agent-read`).** Owner (2026-10-15): the automatic calibration works well, masnou now runs on it; the #110 owner check is closed.

**Product platform (#90, DEPLOYED — AGENTS §13; owner 2026-10-15: every migration through `20261014120000` pushed, the web redeployed, the reviewed matches published and `make republish-all` run from prod — the "NOT pushed" notes below are history).** Drive inbox →
`make inbox` (name, calibration wait, run-match, publish DRAFT) → one
transactional Supabase RPC (applied/unchanged, admin rows untouched) → RLS +
React SPA. Verified offline (scratch PG16, parity, CLI e2e, SPA screenshots);
hosted Supabase/Cloudflare/Drive/launchd untested — owner deploys (#90 Log). #102: Feedback button (bug / suggestion + ≤3 screenshots; `send_feedback()` is the only way in, 20 reports + 30 uploads a day per member; Settings → My reports, Admin → Feedback, `make feedback` → `output/feedback/`; migration `20261009130000_feedback`, NOT pushed). #91: attack landings carry both axes, a per-axis error and a result (recon schema 2, migration `20261006180000_landing_confidence`); needs `make postrun` + re-publish per match. #92: stats windows + side-out/break + serve targets + reception outcome + hitting % + report card + `/measure` (migration `20261007100000`, no re-publish needed); `make republish-all` redoes post-run + publish for every published match (needs its diag dump). #93 security review (AGENTS §13): table privileges are explicit (`20261007120000`; `anon` holds none), `match_report` gates its per-player extras by tier (`20261007130000`), `webapp/public/_headers` (CSP), the publisher refuses a `.env.publish` others can read, login codes go through `supabase/functions/request-login-code` + `login_code_gate()` (`20261007140000`); verified on the local stack only. #95: `match_participants.is_unknown` (`20261008100000`) = a slot outside the league (AGENTS §13); migration pushed by the owner (2026-10-08). #94 login study (`docs/web_login_study.md`): sessions persist (refresh token, no limit); fixes + passkeys/Google options await owner decisions (open point 34). #96 player page v2: tabs (Overview / Attack / Serve & receive / Matches), "you vs the league / vs your earlier matches" strips counted from league-tier data, attack map start → end from `own_x_m/own_y_m` (already published, no re-publish), grades in the "i" hint (AGENTS §13); migration `20261009100000_player_page_v2` NOT pushed yet. #99 reception vs defense: `analytics.passes` (migration `20261009120000_pass_map`, NOT pushed; no post-run change, no re-publish) + `PassMap` card; the real match has 24 credited receptions / 34 defenses, 54 with a seen destination. #113 player page v3: five tabs (Overview / Attack / Serve / Receive & defense / Matches); the attack map opens on KILLS (the other outcomes one tap away, a message on the court when empty); serve map = where each serve was received or came down (`analytics.serves`: ace / in play / error, who took it; migration `20261013100000_serve_map` NOT pushed, no re-publish). #116: no home page (`/` → own player page, unlinked → League; admin drafts = a count on the Admin link), a gear Settings button; admin "3 · Match details" (venue from `venues`, match type male / female / mixed, tournament + level, saved as picked; AGENTS §13 "Match details": a DIVISION, never a player's gender); Overview comparison gets "Same type" (`leaderboard(p_match_type)`, migration `20261014120000_match_details` NOT pushed — push BEFORE deploying the web, `MATCH_COLUMNS` reads the new columns).

**Attack clips (#107, deployed 2026-10-10 — `src/publish/clips.py`, AGENTS §13).** Every credited attack gets a clip: 1 s before the contact, 1.5 s after, cropped around the net (three net heights tall, centred on the net), 640×480 H.264, no sound. Two steps because the video is not kept: `rallies.mp4` + `rallies.json` in the run directory (every rally in that crop, ONE sequential decode, 39–44 MB) → `clips/<frame>.mp4` cut from that copy, so a re-publish after a rules change needs no video. Storage: `match-media/clips/<key>/<frame>-<hash>.mp4`, path in `actions.extra.clip`; sent once, the ones nothing names removed after a publish. Who sees one = who reads that match's touches (owner decision; migration `20261010100000_attack_clips`, pushed). Web: the attack map's hover / tap panel plays it (fetched after 250 ms of rest, links reused, CSP `media-src`). 20261010: 41 / 41 attacks, 9.9 MB; 20260920: 62 / 62, 11 MB; ~90 matches per GB. First publish +2–3 min, re-publish 2 s with the same bundle hash. `make republish-all` ends each match's line with `clips N of M` and the publisher's reason when not all (#107b).

**Identity (#105: who is who is a POST-RUN read — `src/postrun/identity.py`, AGENTS §4 / §11, numbers in `docs/postrun_reconstruction.md`).** Per RALLY: how much better the bodies of each half (feet > 1 m off the net line) match the squad enrolled there; the two orientations sit at two levels read from the match itself (20261010 +0.347 / −0.038, 20260920 +0.146 / −0.083), a two-state path over the rallies decides (a switch costs 4 nats, one rally weighs ≤ 6).
Per FRAME inside a rally: one shortest path over which player each track id is (similarity centred between the two teammates of that half, a cost for feet on the other squad's half, an id changes player only when paid for). Label / squad / slot / HALF of every body are rewritten before the touches are solved. Input: `id_sims` per clean body in the diag dump (schema 5); a dump without them keeps its causal labels and reconstructs byte-identical.
20261010: 31/31 rallies oriented (agent's frame read), 93/93 sampled labels on the right person (score and blocks: next paragraph). 20260920: record unchanged, players = the owner CSV on 207/208 (P19 f13624: the toucher is hidden behind her teammate). Clips e1–e7 unchanged. The causal `TeamIdentityResolver` (live overlay) is untouched and still misses switches.

**Second match (20261010 vall d'Hebron; `output/20261010_1000_vall_dhebron_jesus_sara_joan_loida/`, owner feedback in `ground_truth/20261010_1000_vall_dhebron_owner_feedback.txt`) — the owner's sequence since #106: 31 points, A 22 – B 9, switches after 7 / 15 / 22 / 29** (the players switched one point late and counted one short, so the set ran to 22). #106, numbers in `docs/postrun_reconstruction.md`: (1) landing = where the ball stops falling (the last point's cut shot read 2 m behind the baseline, it lands 1 m inside the side line → A; P11's attack is P2A's kill again); (2) the 06:52 return is refused as a serve — receivers 2.2 m apart in depth and nobody plays it (51 of 52 real serves ≤ 0.84 m), listed as "Not a serve" in the report; (3) attack = contact ≥ 1.23 × the toucher's standing height, contact read where the ball leaves its arc: the five attacks read as overpass are spikes.
Still not publishable without the owner's contact sheet per rally (AGENTS §11); left on this match: blocks (2), an invented overpass (P10), a set + kill unseen (P21), a set from off court (P2) — open point 32i. **#109 (videos 1100 + 1200 of the same morning; owner score table for 1100 in `ground_truth/20261010_1100_vall_dhebron_points.json`, scored by `scripts/score_postrun_points.py`):** 1100 = 35/35 points, 0 false, serving team 35/35, winners 34/35 (the LAST point: over-set + joust at the net, read A, is B's → A 14 – B 21 printed, 13 – 22 true), switches 8 / 15 / 22 / 29 exact; 1200 = 41 points, blocks 8 / 7 / 7 / 7 / 7, A 21 – B 20 (the owner: the last rally counted, A won it, the spike went into the net; no score table). What found them (`rallies.py`, detail in `docs/postrun_reconstruction.md` "Third match"): a STILL COURT (`court_sway`: third-stillest body ≤ 0.10 body heights for 2 s; 114 of 138 serves, 1 of 211 attacks) confirms a serve past the frame / a far toss read inside the court / a toss taken for a pass / a net cord; a launch flight is fitted up to its landing; an unplayed late launch is not a rally's tail; low samples before the ball climbs 1.3 m are no landing; a last touch under the tape is on the half the ball fell on; a ball followed down to the net that never got over the tape fell on the hitter's side (`fell_at_net`, a WEAK death read: 6 of 7 against the next serve); dug-never-set = kill (owner rule). Recon schema 7: `start_time_s` / `end_time_s` (video clock when `frame_times.json` exists), `rally`, `checks.longest_rally`, `serve.confirmed_by`. Nothing published. **#111 (1230, owner's final A 21 – B 19 = 40 points; the run read 38):** two dropped rallies found (`_serve_at_the_tape`, `_fed_by_pass`; `rallies.py` only, no new constant), P37 → A, switches 7 / 14 / 21 / 28 / 35; the last point (A's spike dies 0.9 m from the net, A already on 21) stays undecided; nothing published. **Web:** the match page shows the longest rally under the score (`match_report` → `longest_rally`, league tier, counted in SQL from the stored touches: no re-publish; migration `20261011100000_longest_rally`, NOT pushed; on 20260920 touches per point = owner GT on 31 of 33 points, crossings 33 of 33).
**Owner review (#114, `make review`, AGENTS §11).** `src/web/review.py`: each rally plays from `rallies.mp4` with the post-run labels on the bodies and the play-by-play beside it; Enter = all right, keys for labels swapped / winner / not a point / a touch added, retyped or removed / a missing point / a note. Output `ground_truth/<match_key>_review.json` (`match-review-v1`: per point what the run read and the point as the owner left it; re-attaches by frames after a rules change). **Dead time (owner: "I cannot tell when there is a point missing"):** `make review-gaps` writes `gaps.mp4` + `gaps.json` per run (`src/publish/gaps.py`: everything the rally copy leaves out, whole frame, one frame in 3, ~10 MB, needs the video); the page puts a dot between the points, orange where a look is worth it (ball played ≥ 3 times, or a pause ≥ 1.6 × the usual), plays it 3× faster, M marks a missing point with its frame. **Applied at publish (`src/publish/reviewed.py`, AGENTS §13):** the publisher builds the bundle from the reconstruction with the review applied in memory — a reviewed point takes the owner's touches / winner / near squad, ace / kill / error derived again where he changed the end, a missed point = a point without touches; an all-right review gives the same bundle hash; `--no-review` = the run. A block scores only as a kill block (migration `20261014100000_block_kill_only`, NOT pushed). What the owner corrects, by cause: `scripts/review_corrections.py` (#117: 175 edits on 71 of 180 points). 1000 reviewed: 25 of 31 right, 6 corrected, who and winners all right; 1100 reviewed: 24 of 35 right, A 13 – B 22 = the owner's table. 1200: 26 of 41 right, 0 winners changed, A 21 – B 20 (his answer file); 1230: 20 of 40 right, 1 rally no point, 1 missing point (an ace into the net), 3 winners changed, A 21 – B 19, ends every 7; masnou: A 21 – B 14 over 35 (owner: the remembered 21 – 15 was a miscount, nothing missing in the 6-point first block), committed.

**Production state (causal pass, unchanged):** weights
`volleyball_ball_best.pt` v3; match 720p upscaled `_up1080`; 30–32 ms/frame
(#89; 75 before, dump on); 212 actions on the #87 run; held-out P9–P33 contact F1 0.772, class 0.590;
overpass 0/18; serves near 8/16, far 0/17, 12 FP (`score_serves.py`).
Display-only observers: possession (#77–#79), ground contact (#80), squad
colours/labels. Pass-2 scripts (`relabel_serves`, `resolve_side_switches`,
`resolve_point_winners` 18/33, `consume_serve_evidence`) are SUPERSEDED by
`src/postrun` for points/serves/winners; kept as provenance. Entreno action
gate (causal): e1 0.706, e2 0.571, e3 1.0, e4 0.933, e5 0.923, e6 0.933,
e7 0.75 (same-session A/B only). Test suite **1409** (1404 pass, 5 skipped: the schema checks, which pass with a Postgres).

**Player detector input (#94, default ON):** `player_bgr_input: true` passes BGR as-is (`false` = the old path; how to compare: Learnings). 4-track frames up on all 7 clips, stream F1 0.824→0.839, post-run identical; match stream labels 81/145→74/146; e3 contact sheet owed. Full text: `docs/history/status_where_we_are_archive.md` (#97).
**Speed (#89, results-neutral — AGENTS §12):** `prefetch_depth: 8` + `detector_fast_inference`: match 1955 → 783–836 s, clips 291 → 131 s, byte-identical to the pre-#94 goldens (= `player_bgr_input: false`). Bound: MediaPipe pose (open point 33). Full text: same archive (#94, #97).

**Held-out lock:** `ground_truth/20290928_entreno_vall_dhebron_serve_anchors.json` = 19 serves; the video has NEVER been run; use only via a card "score held-out once" with frozen rules (the post-run layer has not seen it either).

**STOP list (causal serve work):** no more px-space far-serve thresholds
tuned on the 17 match far serves; no relabeling reception as serve; no
vall_dhebron output looks. Serve START is now a post-run read — do not
reopen causal serve detection for it.

**Refuted/parked mechanisms:** list moved to `docs/history/status_where_we_are_archive.md` (#90 block); never `src/`.

**Known defects:** `annotate_player_gt.py` + `src/db/ingest.py` seek on VFR (allow-listed in `test_vfr_seek_guard.py`); stale comment at `src/utils/config.py:101`;
GT `20260920_match_ari_joan_contacts_p1_p8.txt` P31 serve f24543 is 128 f before its reception (owner to confirm ~f24630).

## Active next (ranked)

0. **Cut the owner's review time (#117; measured: 175 edits on 71 of 180 points over 5 reviewed matches, ~20 min a match; `scripts/review_corrections.py`).** One mechanism per session, each judged by the edits it saves on the 5 review files with the §11 bars held: (a) review page: naming a `T#` body on one touch names it for the whole rally, and a missing point / label fix re-derives the servers after it (≈30 edits, no pipeline change); (b) drop an observed last-touch dig with nobody at the ball (6 of 7 were removed); (c) a touch read on the net line right after an attack = ball into the net / block, never an overpass by the other team (4 removes + knock-ons); (d) the rally ended early after a set (19 touches added after the run's last): read the attack by the setter's partner, owner decides on crediting it; (e) dig vs overpass on first touches (18 overpass relabels + 7 wrong-half players); (f) identity on look-alike squads (1230 B: 26 per-touch names + 5 far swaps).
1. **Blocks (owner, 2026-10-15):** a block MAY be credited (to the defender at the net); it scores +1 only as a kill block (§13 rule unchanged). Owed: the credit rule in §11 + `player_stats` + publisher together, and a landing half read independently of the touch sides (the #115 stuff read was refuted).
2. **Web, design §8 "Next":** action_overrides UI, in-app invites, `own_x_m` heatmaps; a match-type filter on the League table / tabs ("for the future", #116).
3. **Landing line calls** (20260920: 3 of 10 wrong, not the #106 bug; 20261010:
   5 of 5): needed only for the last point and for kill-vs-out detail; a read
   from raw detections of the resting ball is the candidate (open point 31).
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

30 / 22. **Serve reliability + far-side serves.** SOLVED POST-HOC (#87); both entries archived verbatim (#110, `docs/history/status_log_archive.md`). Next: none (STOP list).
21. **Owner's match-feedback backlog.** (1) point count 33/33 DONE (#87);
    (2) per-point + per-action confidence surfaces: the reconstruction
    carries `evidence` (vertex / gap / structure), `flags` and the
    ball-death cross-check per point — UI unbuilt; (3) winner 33/33 DONE
    (next-serve rule); (4) side switches exact DONE; (5) player-number GT
    pass DONE #88 (owner CSV review, 0 corrections); (6) landing
    confidence: line calls 7/10 (open point 31). Next: (2) with the DB
    ingest (Active next 1).
2.  **Side-change survival (player identity) — status: SOLVED POST-RUN #105.**
    `src/postrun/identity.py` reads the near squad per rally and the players
    per frame from `id_sims`: 20261010 31/31 rallies (agent's read) + 93/93
    sampled labels; 20260920 switches 7/14/21/28, who 207/208 vs the #88 CSV.
    Open: (a) the causal resolver (live overlay) still misses switches
    (20261010: 0 of the first 2, then 10 flips) — display only; (b) two
    venues, visibly different kits: look-alike teammates give no labels,
    untested on footage; (c) a new match = owner contact sheet first.
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
    exists on only 16/33 points and its in/out half is weak (3 of 10 wrong;
    #106 fixed the too-deep landing, these three are not it). Harmless for winners
    (next serve decides) except on the LAST point. Next: read the resting
    ball from the dump's raw `removed` detections (it sits in-court at ratio
    0.93–0.98 of the ground prediction) and map its bottom point.
32. **Post-run layer residuals (#87).** (a) WHO RATIFIED #88 (owner review
    of the 208-touch CSV, 0 corrections; CSV = per-player GT); (b) built
    and tuned on ONE match — second match RUN #104 (20261010), see (h);
    (c) needs the `--diag-dump` sidecar (49 MB, in memory until the run
    ends) — decide whether `make run` should always write a compact one;
    (d) blocks are not a label; (e) 1 observed touch is credited to nobody
    (10 more by alternation), 5 are placed as hidden touches; (f) FIXED #90:
    set/dig `error` = ball handling −1 (`handling_errors`); (g) #97 hard / touch: split fitted on this match's 32 labels (same score for 24–26°), owner looked at the sheet (#98): P10 f6320 = a second-touch poke that left flat from mid-court and P22 f16037 = a touch to the side that barely rose — both labels stand (TOUCH; read hard / untyped), nothing re-tuned; P30, P33, P19 not commented; swing vs poke needs pose in the dump; (h) #104, 20261010 with the orientation set by hand (agent's frame read, not owner GT): 29/30 points, winners 26/29. Residuals: a caught-and-replayed serve counts as a point (P8); a dead-time lob from the far half passes every serve gate (P14: birth 2.5 m inside, peak 4.8 m, 13 m at 7.6 m/s); a near serve that leaves the top of the frame is lost (track dead at the hit, reborn past the net 4.3 m up; the serve-less path did not fire); the last point's winner by landing read was wrong. #105b: the cut rally (07:17) and the serve past the frame (10:11) are FOUND; #106: the dead-time return is refused (receivers not side by side), the last point's winner is right (landing read) → 31 points, A 22 – B 9 = the owner's sequence; (i) owner label feedback: attacks read as overpass FIXED #106 (reach ratio); left: blocks (2) read as the attacker's spike, an attack into the net with an invented overpass (P10), a set + kill unseen (P21), a set from off court unseen (P2). Next: Active next 2. (j) #108 → #109, 20261010_1100 (owner score table: 35 points, A 13 – B 22) + _1200 (no GT): FIXED #109 — the four lost points (near serve out of the picture f1060, far jump serve f16535, near serve into the net f24669, net-cord ace f31784), the serve read from the wrong half (f30939), the rally cut at a dive-dig, the dead-time return merged as a rally's landing, the report clock. LEFT: (1) the last point of 1100 (winner from the ball's death: a touch 2.1 m up at the net read as B's third, is A's first); (2) blocks (P5 / P6) and an attack into the net replayed by the same player (P31) read as other touches; (3) a phantom "dig" on the sand after a kill (P20 / P21, uncredited); (4) decisions still run on the AVERAGE fps (speeds 6 % high / 11 % low on 1100): put the video timestamp of every frame in the diag dump; (5) a vertex one frame before the track dies hides the death, so `_serve_past_the_frame` does not see that serve (sim only); (6) the thresholds were set with 1100 in view (in-sample sweep: lost with sway bar 0.05, 3 s window, 0.1 m tape slack): test = the next match with an owner score table; (7) 1200 has the owner's word on its last point only (`ground_truth/20261010_1200_vall_dhebron_owner_feedback.txt`), no table. (k) #111, 20261010_1230 (owner: A 21 – B 19, 40 points; run 38): FIXED — a net-cord ace first seen at the tape (f31700) and a serve whose toss the tracker released at the hand (f41879), each dropped; LEFT: the last point (both teams "close" a set already complete, the ball dies inside `LANDING_NET_MARGIN_M`), the far-half server read (B breaks at P4 / P34), T-labels on P39.
33. **Speed, results-neutral (#89).** Shipped: read-ahead + exact detector
    fast path. Left, in order: (a) pose on its own thread, call order kept
    (~30 → ~26 ms/f; touches `ActionClassifier`); (b) read-ahead for the
    `--debug-live` producer and the enrollment pre-pass (5 s per clip);
    (c) re-verify the fast path before any ultralytics upgrade (it turns
    itself off on an unverified release; `venv/` is the only env).
34. **Web login: fewer code mails (#94, study only, `docs/web_login_study.md`).** Sessions already last until logout (no limit). Owner decides: (a) limit — 30 d (NIST AAL1) via `pg_cron` on free plan; (b) final domain (before passkeys); (c) second method — passkeys (beta, needs an options broker: the Auth lock blocks it) or Google (passes the lock). Then build A: local logout + "all devices", one URL.
35. **Published court positions (#100 diagnosed → #101 FIXED in code, output only; republish owed).** `src/postrun/positions.py`: `court_x_m` / `court_y_m` / `court_xy_m` are read in a net-anchored frame (the calibration's net-ground clicks) with the ball-box offset removed; the offset is per video, read off the end switches (20260920: 1.74 px closes dig / set / spike / overpass from 2.05–2.21 m to within ±0.16 m; spikes 2.70 / −0.30 → 1.40 / 1.40 m, the 2:49 kill 2.7 → 1.4 m, 1 of 39 held at the net). Decisions untouched (`DEPTH_SPLIT_BIAS_M` stays). Open: (a) it rests on the two halves being played alike — the players' feet show the same near/far gap, so a real part (wind) cannot be excluded; two serves into the net read no offset, one net-slide reads it; (b) a video without a switch (practice clips) stays uncorrected and holds across-net reads at the net; (c) a single position is ±0.6–0.8 m; a takeoff-from-the-feet read needs a higher camera or its own design; (d) in-sample on one match. Next: owner looks at `output/postrun/20260920_match/attack_map_now_vs_fixed.png`, then merge + `make republish-all` from prod.
36. **Automatic calibration residuals + calibration fragility (#110; `docs/auto_calibration.md`).** Status: BUILT, inbox in `propose`. (a) knife-edge points: 20261010_1000 and _1200 each flip a point at 0.5 % of a baseline width — any recalibration, a re-click included, can move them; a post-run robustness card is owed (anchor ball depth on what play shows, e.g. serves, not only on the corner widths); (b) beach refused: right sideline 30 % seen, far corners 0.5 m off sideways (a far corner could be read off the far tape's own end); (c) the points under the net are the court's middle, the clicks follow the posts (3–20 px): published positions (#101) move up to ~0.7 m on a newly calibrated match — posts are the fix; (d) blind spot: both sideline ends buried alike (only the camera read speaks against it); (e) not built: start / middle / end plates (bumped camera), cross-check from play; (f) 6 views, 2 venues, 2 tape colours; the causal stream loses e7 f163 (reach gate) with the automatic file. (g) #112: the first NEW held-out view (20261012_1130, a beach, black tape on pale sand, a yellow net with a 1 m band, 25.56 fps) found NO court — nothing scored; the file was read by hand (corners 632,794 / 1205,797 / 1712,989 / 104,1009, net 2.29 m, camera f 1790 px, 1.55 m up). The beach is now 2 of 2 refused: a far-corner / sideline-coverage fix is the next calibration work (b). Next: Active next 0.
37. **20261012_1130_masnou (#112): 33 of 36 points, A 19 – B 13 (was 31, A 19 – B 11).** Owner's final A 21 – B 15 (A = the yellow-bib team, `ground_truth/20261012_1130_masnou_owner_feedback.txt`; no table, no times). FIXED (`rallies.py` only, `docs/postrun_reconstruction.md` "Fifth video"): a serve first seen at the tape and DUG (f2175; `_serve_at_the_tape` took only a ball that ends on the sand) and a LOB serve received by two players side by side (f3425, 4.6 m/s: `_lob_to_a_formation`, `confirmed_by: formation`); 12 other runs byte-identical. LEFT (3): f14445, a near lob serve on a perfectly still court whose flight depth reads 12.4 m (< `NEAR_SERVE_MIN_Y` 14; its toss reads 15.6) — the next card; one in the 56 s gap before P27 (f21790–23204, nothing seen yet); one in the first six points. Switch blocks now 6 / 7 / 6 / 7 / 6. P33 (the last) undecided. Next: the near lob serve, then contact sheet per rally before publishing.

### Parked / conditional

5.  **Same-team adjacent-player choice.** Needs the owner-specified engine
    (motion history + ball half, #46); scoreable only with stable-identity
    GT (2); `--ignore-player` stands until then.
6.  **Phase 2: offline global stitch.** BUILT #105 as the per-rally identity
    read (open point 2); no stitch ACROSS rallies needed (fixed anchors).
9.  **Overpass label lever.** Status: SOLVED POST-HOC (#87) — the crossing
    is known in hindsight (the next touch is on the other half): action
    0.988 on the match, overpass vs spike by contact height over the toucher's
    standing height (#106). Residual: passes with the arms above the head (2).
    C1–C4 are closed by supersession.
13. **Ace metric.** Status: DERIVED (#87) — `outcome: ace` on a serve the
    receivers never touch or touch once and lose (owner kill semantics);
    kill / error likewise. #105 (owner rule): a far serve counts too (its
    launch is read from the track birth) — 20261010 P8; 20260920 unchanged.
    Next: surface in the UI with open point 21.
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

**Court calibration (#110)**
- The clicks are not GT: the net reads 7.26–9.33 m through the 4-corner homography; e1–e7's near-left corner is ~90 px OUTSIDE the frame and was clicked inside it (that file's near baseline is 5 % short).
- vall d'Hebron by day: the far baseline tape is BURIED — the far corners are where the sideline tapes end. A tape ends short of its corner (buried), never beyond: of two ends that agree the farther; tape running on beyond a far baseline refutes it.
- Calibration tolerance (post-run only, `probe_calibration_sensitivity.py`): beach immune (±6 %, ±16 px), 1100 ±4 %; 1000 and 1200 each flip a point at 0.5 % of a baseline width; the net clicks (±16 px) change no decision. Identical decisions after ANY recalibration cannot be promised.
- Tape evidence = chroma distance from the sand (robust sd) + thin top-hat: shadows vanish. Half-buried tape sits at the sand's own p97–p99, so lines are voted along their whole length, then again on the tape's own colour; specks are dropped before voting, fits use ridge centres (a 12 px tape lets a line lie anywhere in it).
- A net tape is found by colour UNIFORMITY along its line (spread 7–18 vs 40–130 just above / below), not by brightness: against the bright court behind it a brightness band locked onto a tilted line (1000). Its two edges, weakest third deciding, give row and slope.
- Tapes bow 12–40 px off a straight fit (the beach left sideline 23 px): follow them from mid-court outwards, rate-limited — an unlimited follower turns the far corner onto the baseline (seen on a drawn court, explained the beach / e3 far-corner errors).
- Focal length from the corners is a camera constant: four same-morning videos read 1870–1943 px automatically (clicks 1838–1972); ~12 px of focal per px of far row there, so ±2 % pins the far baseline to ~0.3 m. e-clips read ~2160, beach ~1660–1725 (other settings).
- What cannot place the far baseline: the net height through the calibration (0.006 m per px of far row) and "net y from a 2.43 m tape" (7.2–10 m: ill-conditioned with the lens near tape height).

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
- Orientation levels are NOT mirror images (#104, 20261010): anchors are enrolled in ONE view, so the evidence keeps a view bias as large as the signal (squad 2 near reads ~0, not −0.39 / −0.52). `LEVEL_ALPHA` 0.002 × 4 bodies a frame follows a level in ~4 s, faster than players walk a switch; slower (0.0002 / 0) finds the switches but flaps 24 / 28 times. Decide per rally in hindsight, on rally frames only (in dead time bodies wander onto the other half).
- Post-run identity (#105): one orientation per RALLY from firm-footed bodies, two levels read from the match (the unseen level is match-specific: −0.038 on 20261010, −0.083 on 20260920; the enrolled one +0.347 / +0.146) — never a fixed threshold, never the 7-point rule (point counts can be wrong; block sizes are the cross-check).
- A body's half is NOT its feet (#105): a far blocker stands on the net line in the picture (tracker reads him near for whole rallies), a jump projects the feet metres deep, dives and merged boxes read near — 42 of 28 633 firm body-frames on 20261010 and 180 of 30 475 on 20260920 contradict the squad's half, in runs up to 18 frames. The squad decides, feet are a cost.
- Cross-view look-alike (#105, 20261010): P2B seen from behind matches squad A's anchors better than her own far-view one (0.84 vs 0.63) → an unconstrained 4-way match fails; the PAIR on a half + the half constraint decide (side penalty under 0.35 lets the look-alike win). Centre each player's similarity between the two teammates of that half, or a body seen alone is read with the view's bias.
- The live resolver lost the first 20261010 switch because the players crossed ONE AT A TIME over 12 s (f7450–7800) while its level and spread adapted (level +0.39 → ~0, spread ×4): by the time all four were across nothing was left to detect.
- A probe feature dump joins a run's diag dump exactly by (frame, track id) — 0 box mismatches on both matches (MPS is deterministic) — so an identity change can be prototyped by injecting into an existing dump before any 30-minute re-run.
- A stale causal label can be right by accident (20260920 P19 f13624: two teammates in one box, the hidden one bumps the ball; the box shows the other one) — the one touch where the hindsight read differs from the owner CSV.
- Service order is NOT one bit per squad when a point is lost or invented (#105b): everything after it is shifted, and a majority vote then overrides correctly SEEN servers (20261010: the owner read it as "team A players switching"). Let the order break where a run of seen servers says so (`_serving_order`, break = 1.5 seen servers); a break marks where to look for a lost / false point.
- A dig at the far baseline can read at sand level (height from a ±2 m depth read): a rally must not end on it when ANY later vertex within air time sends the ball up again — the next one alone can be a short low flight (20261010 07:17 rally, cut after the reception).
- High tripod: a near serve leaves the top of the frame — toss tracked beside the baseline, track dead at the hit, ball reborn mid-court above any contact height. Read the serve at the toss's death when the reborn flight is where a serve from there would be (`_serve_past_the_frame`).

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
- Serve-shaped non-points exist (#104): a serve the receiver catches and hands back (replayed), a ball lobbed back over the net between points. "Winner = next server" then gives the wrong winner to the point BEFORE a false or a missed point; `death_disagrees:serve_into_net` marked one such neighbour (P20) and one true net-cord ace (P30) — a "look here" flag, not a winner.
- The width "grounded" test fires BEFORE a ball lands (#106): a falling ball lines up with sand metres behind its landing spot and its width fits that sand for a frame or two (20261010 last point: 0.7 m up, read 2 m behind the baseline; it lands 1 m inside). A landing = where the fall stops (`_landing_frame`). The higher the tripod, the nearer that wrong sand, so the bug bites high cameras; on the beach the ray is at the horizon and the test stays silent.
- A classifier vertex is dated 0–3 frames early and a set drops 0.2 m a frame: contact height at the vertex is +0…+0.5 m, at random (#106). Read it where the ball leaves its incoming arc (`BallTimeline.arc_exit`); `attack_shape.hit_frame` (largest velocity step) lands up to 7 frames late on a pass and is not that read.
- Attack vs pass is the PLAYER's ruler, not the net's (#106): two 20261010 players attack at 1.85–2.05 m, under any tape; contact / standing height reads passes ≤ 1.19, attacks ≥ 1.27 on 91 labelled touches of two matches. Standing height = p75 of box heights in metres, pooled per identified player (one rally is ±10 %); boxes read ~10 % under real height for everyone.
- A dead-time ball can be a perfect serve for the ball reads (#106: thrown from BEHIND the far baseline where it was fetched, 4.8 m peak, 13 m at 7.6 m/s). What differs is the receiving team: about to serve, it stands one behind the other (2.2 m; 51 of 52 real serves ≤ 0.84 m). Feet depth is only good enough on the near half or under a high tripod (beach far half ±0.7–0.9 m, a garbage box read 2.9 m at a real serve).
- The players' own count can be wrong (#106, 20261010: side switch after 15 points, set played to 22): never force blocks of 7 or a 21 cap onto a match; `switch_blocks_ok: false` is information.
- Practice venue (lens ~3 m): a near serve can leave the TOP of the frame — the track dies at the hit and is reborn past the net above `SERVE_MAX_CONTACT_M`, so no serve is found. Checking a run by eye: one frame per point at its serve frame (ffmpeg `select`, one sequential decode) shows who is near; the score at each switch must be 7 / 14 / 21 / 28 points.

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
- **The video must be named `YYYYMMDD_HHMM_<venue>_<text>` BEFORE calibration (owner, 2026-10-10):** `pipeline_output.json` records the path the run read, so a rename after the run left the publisher without the video (no thumbnails, no hash). `make calibrate` / `make run-match` now refuse any other name (`scripts/check_video_name.py`); no fallback that guesses the renamed file. A run made under the old name: keep its thumbs/ + video_identity.json (cut once) and republish.
- **Reception vs defense (#99):** both are `dig` (touch 1) in the post-run layer; the touch BEFORE it decides — serve = reception, spike / overpass from the other team = defense. Where it went = the same team's next touch, if observed and positioned (`own_x_m/own_y_m`, already published). Use `team`, not `side`, in SQL (the smoke fixture has no `side`). 20260920: P1A 3/11, P2A 6/7, P1B 7/10, P2B 8/6 receptions/defenses, 54 of 58 with a destination: ~14 passes per player per match, so a per-match spread is thin.
- **A serve row has no position (#113):** `court_x_m` / `court_y_m` are null on every serve touch (20260920 0 of 33, 20261010_1100 0 of 35), so a serve can only be drawn by its END: the other team's SEEN next touch (26 / 33, 26 / 35), turned into the server's frame (8 − x, 16 − y), else the point's ground end through `actions.side` of the serve; `points` keeps no error for that end.
- **Web screenshots without a browser tool (#113):** `VITE_DEMO=1 npx vite --port 5199` in `webapp/`, then headless Chrome (`--headless=new --screenshot=… --window-size=W,H --blink-settings=preferredColorScheme=0` dark / `1` light, a fresh `--user-data-dir`); it does not exit by itself (wait for the file, kill it) and lays a page out no narrower than 500 px.
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
- Attack clips (#107): a 2.5 s clip as GIF (360p, 15 fps) is 5.2–5.9 MB, as H.264 MP4 640×480 0.13–0.33 MB. Clips re-encoded from a crf-25 rally copy (crf 23 = 64 MB, crf 25 slow = 44 MB for 323 s). Players + ball around an attack span ~616 × 681 px (the set's apex dominates): a crop holding the whole court is the whole frame. Net-sized crop (1086 × 814 on vall d'Hebron): attacker never cut, ball leaves sideways in 5 of 41 clips; the central 960 × 720 cuts the attacker in 4.
- Prod checkout trap (#107b, 2026-10-10): `~/volley-prod/resources/full_videos/` held per-file links made at setup, so a match run in the dev checkout later has NO video from prod: `make republish-all` published it without clips and, the bundle being the live one, logged `unchanged`. `republish` swallows the publisher's output — only what it re-prints is seen.
- Browser check without a test runner (#107): `VITE_DEMO=1 npx vite` + the playwright in `~/.npm/_npx/*/node_modules/playwright` with `chromium.launch({channel: 'chrome'})`; an element screenshot scrolls and drops the hover — use `page.screenshot`.
- New match, no GT (#108): the cheapest soundness tests are the switch blocks (7 / 7 / 7), `checks.service_order` agreement (1200: 37/37; 1100: 83 % + `server_from_rotation` flags) and the final score closing the set; a point missing shows as a 6-block + a long gap holding a serve-shaped flight (`BallTimeline.flights`: peak ≥ 2.2 m, ≥ 5.5 m/s toward the other half).
- Post-run reads that fail on the far half (#108): a far jump serve with a high toss splits the toss at a `gap` vertex and 16 px of ball width gives ~5 m of depth noise, so `_fed_by_pass` calls it a pass; a dive-dig at sand level is read as the landing (`line_call_overridden` flags are the symptom). Both are by design precision-first; neither changes a winner (next serve decides).
- Missing point = wrong neighbour (#111, 1230): the next-serve winner of the point BEFORE a dropped rally is wrong, and the ball's own death was right (P37 `fell_at_net` = A; the serve after it was missing). A net-cord serve first seen at the tape (born at y ≈ 8 m, 2.1 m up, 2.5 m/s) is a serve only on a still court; a "feeder" vertex that is the track's first sample is the toss release, not a pass.
- A still court is one-way evidence (#109): third-stillest body's feet within 0.10 body heights of their spot for 2 s = 83 % of serves, 1 of 211 attacks; use it to CONFIRM an open serve, never to refuse one (a 1 s window or the receivers alone separate worse: 8–23 % of attacks pass).
- Two weak reads must not stack (#109): "far toss inside the court" + "ball seen again too briefly to carry a speed" turned a far ball glimpsed for 0.5 s and the near server's toss into a far serve, on a still court (20261010_1000 f23808), and its rally swallowed the real serve. Background courts read y ≈ −7…−10: a glimpse "past the net" must be INSIDE the court and end at a vertex.
- The serve-less (orphan) path takes the first vertex after a track birth for the reception: a server's bounce or toss vertex gives a serve from the WRONG half (1100 f30854, 1200 f43750) and then a wrong winner for the point before. A missed serve is worse than a missed point.
- `ground_frames` at the START of a flight are a ball leaving a dig off the sand (at 3 m lens height everything under ~0.5 m passes the width test); a landing is low samples AFTER the ball has been above 1.3 m. A flight that never exceeds 1.3 m is a low pass if the ball is followed to the next vertex and played on.
- `has_vertex(end - 1, …)` in `_build_events` swallows the DEATH of a track that ends one frame after a vertex: no death / birth pair, so readers of that pattern see nothing (real data: the hit vertex was 2 frames before the death).
- Owner labels vs run labels (#109, 1100): the owner named team B the other way round (owner P1B = run P2B) through the whole video — check a serve frame with the dump's labels drawn before calling an identity bug. The owner's `mm.ss` is the SERVE time; `ffprobe` packet pts ≥ 0, sorted, are the decoder's frames exactly (4 videos: one per frame).

## Session index (one line each)
- #117 **What the owner corrects in `make review`: 175 edits on 71/180 points (5 matches) — identity ~36, overpass ~35, uncredited 22, rally ended early 21, serves 13, blocks 12; `scripts/review_corrections.py`**
- #116 **Web: no home page (`/` = own player page), Settings button, admin match details (venue list, match type, tournament + level; `20261014120000`), "Same type" comparison reference**
- #115 **Blocks as a post-run label: an attack above the tape at the net that comes back to the hitter's half, a defender at the net → hidden block, new possession; 3 of 6 reviewed read, 1 doubtful, 0 points changed**
- #114 **Owner review page (`make review`): each rally plays from the rally copy with the post-run labels on the bodies; Enter = right, keys for corrections; verdicts in `ground_truth/<key>_review.json`; replaces the contact sheets**
- #113 **Web player page v3: comparison = table with the gap in colour (arrow, blue / orange, pale = could be chance), league line under every tab's tiles, attack map opens on kills, Serve | Receive tabs, serve map (`20261013100000`)**
- #112 **20261012_1130_masnou (new beach video): auto-calibration refused, 8 points read by hand; 31 → 33 of 36 points (owner's final A 21 – B 15): serve first seen at the tape and dug, lob serve in formation; 12 runs identical**
- #111 **20261010_1230 run + checked: 38 → 40 points (a net-cord ace first seen at the tape, a serve whose toss was read as a pass), P37 → A, switches 7…35; post-run only, 11 other runs byte-identical; last point undecided**
- #110 **Automatic court calibration: 8 points from the picture, no model; 5 of 6 views accepted, held-out corners ≤10 px from the clicks, replays keep every point and winner; inbox `propose`; C0: two matches flip a point at 0.5 % width**
- #109 **20261010_1100 vs the owner's score table: 31 → 35/35 points, 0 false, winners 34/35; still-court cue confirms open serves; dug-never-set = kill; video clock; 1200 → 41 points, A 21–B 20; longest rally on the match page**
- #108 **Two more 20261010 videos run and checked by frames: 1200 sound (40 points, A 21–B 19); 1100 not (31 points, A 14–B 17: a missed far jump serve, a rally cut at a dive-dig, clock up to 50 s off); no `src/` change**
- #107 **Attack clips on the player page: hover / tap an attack, watch 1 s before + 1.5 s after (640×480 MP4 from a kept rally copy, cut by frame number); seen by whoever reads that match's touches; 41/41 + 62/62 attacks; not deployed**
- #106 **20261010 = the owner's sequence (31 points, A 22–B 9): landing read where the fall stops, dead-time return refused (receivers not side by side), attack = contact ≥ 1.23 × standing height; 20260920 action 0.982→0.988**
- #105 **Side switches read POST-RUN (`src/postrun/identity.py`): near squad per rally + per-frame player path; 20261010 A 11–B 20 → A 21–B 10, 31/31 rallies; 20260920 unchanged, who 207/208; ace rule from either end**
- #104 **Second match run (20261010 vall d'Hebron): A 11–B 20 as run vs 21–9 true; resolver missed 2 of 4 side switches then flapped; by hand 29/30 points, 2 false, winners 26/29; diagnosis only, post-run orientation proposed**
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
## Log (newest first)

### 2026-10-15 (hundred-and-seventeenth session) — #117: what the owner corrects in `make review`, by cause

**Asked (owner):** close the owed topics (deploy #116, publish the reviewed matches, `republish-all`: done; auto-calibration works well, masnou runs on it; a block may be credited but scores +1 only as a kill block); then study the corrections on the four vall_dhebron videos and masnou and say how to cut the ~20 min a match the review still takes.

**Measured (`scripts/review_corrections.py`, new; reads the 5 review files, joins the current reconstruction by frame).** 180 points reviewed, 71 corrected, 175 edits (1000: 15, 1100: 22, 1200: 46, 1230: 55, masnou: 37). By cause: identity ~36 (26 = a `T#` body named touch by touch, 22 of them on 1230's look-alike B squad, the per-rally "name" control never used; 5 far swaps; servers that follow); possession / overpass ~35 (overpass → dig 7, → set 6, → spike 5, set → overpass 4, 7 players on the wrong half, 6 overpasses removed, 4 of them read on the net line after an attack = ball into the net or a block); uncredited touches named 22 (half `observed: False` structure touches; a naive alternation guess is right 9, wrong 6: NOT a rule); touches added after the run's last 19 (+2 rally tails): the rally ends early, typically on a set whose attack is unseen (5 of 14 rallies ending on a set got a spike added); blocks 12; serves 13 (service-order credits wrong 7 of 17, the masnou ones right after the missing point the owner marked); a last dig nobody was at 6 of 7 removed; winners 8, missing points 3. Triage is not a lever: 10 of 45 points with no flag were still corrected; every point with an unnamed or uncredited touch was (32/32).

**Plan (Active next 0, owner to pick the order):** (a) review page: a `T#` name and a missing point propagate (≈30 edits, no pipeline change); (b) drop the unattended last dig; (c) net-line touch after an attack ≠ overpass; (d) the attack after an unfinished set; (e) dig vs overpass on first touches; (f) look-alike squads. Nothing in `src/` changed.

### 2026-10-14 (hundred-and-sixteenth session) — #116: web simpler (no home page, a Settings button), match details on the admin page, "Same type" comparison

**Asked (owner):** (1) drop the home page, the player view is the default; (2) Settings through a real settings button, not the player's name; (3) more data on each match to segregate later, admin only, dropdowns: match type (male / female / mixt), tournament or not, its level, pro or amateur, venue (a dropdown that can be extended); (4) compare a player with others similar to them (match type) besides the league; maybe a spider chart.

**Owner decisions (asked):** levels Local – amateur / Local – pro / Regional / National, and pro / amateur is carried by the level (no field of its own); "similar" = same match type only; NO spider chart (my advice: one rank scale over ~10 players jumps on small samples, cannot show "could be chance", its shape depends on the axis order; the table already says better / worse and how sure). GDPR worry about storing gender: nothing per player is stored — the match type is the match's division (AGENTS §13 "Match details" forbids a gender on `players`); the larger exposure is the footage, the clips and the appearance-based identification, which a members' privacy notice + consent would cover.

**Built.** Migration `20261014120000_match_details`: `venues` (name PK, one spelling per lower-case name, seeded from the venues typed so far, capitalised spelling kept; members read, admins add; FK from `matches.venue`), `matches.match_type` / `is_tournament` / `tournament_level` (+ check: a level needs a tournament; admin-owned column grants), `window_matches` + `leaderboard` take `p_match_type` (last N counts within the type). Web: `/` redirects (own player page, else League with the "not linked" notice), nav "My stats", Admin (N drafts), gear Settings button (icon only on phones); admin match page "3 · Match details" (selects saved on change, "+ Add venue…" inline), "4 · Publish", Type column in the review queue; Overview's segmented control League · Same type · Earlier matches, a type picker when the player has several (`typesPlayed`, from the history rows + `matches`), the reference = everyone else's row of `leaderboard(window, type)`; the tab tiles stay on the league (their analytics are not type-filtered). Demo mode mirrors it; `make backup` exports the new columns + `venues`.

**Checked.** `make schema-check` 5 passed on a throwaway Postgres (rls_smoke: grants, FK, case-insensitive duplicate, level-needs-tournament, type check, a viewer cannot add a venue, `leaderboard(p_match_type)` counts and last-N within the type); the seeding run on messy venues (`masnou` / ` Masnou ` / '' → `Masnou`, blank → none); vitest 86, `tsc`, oxlint; demo driven in headless Chrome at 1200 and 400 px (lands on My stats, Same type + picker, Settings, add venue, type / tournament / level, level hidden after "No").

**Not done / owed.** Owner: merge, `supabase db push` BEFORE the web deploy, tag the published matches. The real league has no typed match yet, so "Same type" is disabled until an admin tags them. Not built: a match-type filter on the League table or the tabs (asked "for the future").

### 2026-10-14 (hundred-and-fifteenth session) — #115: blocks in the post-run touch solver

**Asked (owner):** start with blocks; "if there is a block and the ball ends up in the spiker's field then it was a block".

**Diagnosis.** The owner reviews carry 8 block labels (1000 ×2, 1100 ×2 = a joust, 1200 ×4). The block is 2–6 frames after the attack (one tracker vertex; twice the attack itself is not even labelled) and the ball's depth read at the net is ±1.5 m, so no reversal is readable off the ball. 6 of 8 are "the attacker's team plays the ball again"; none is a clean kill block. The solver already allowed "over and back" but priced it as two whole crossings (~2.3 s); a block returns in 0.4–1.1 s.

**Built (`src/postrun/touches.py`).** A block step in `TouchSolver._transition`: from a vertex read within 1.5 m of the net and above the attack height, when a player of the OTHER half stands within 1.5 m of the net (`_blockable`), the hitter's half may start a new possession after `BLOCK_RETURN_S` (0.75 ± 0.35 s), cost `BLOCK_COST` 1.0; the block is a hidden touch (action `block`, never credited, not published: the bundle sends observed touches only). The defender guard removed the one clear false block (masnou P24: nearest defender 4.5 m; reviewed blockers 0.7–1.3 m). Two sim tests.

**Measured (all runs, `python -m src.postrun` both arms).** 1200: blocks at P6 / P21 / P24 = the owner's three; touches matching his truth 6/8 → 7/10, 8/9 → 10/12, 12/15 → 14/16. 1230 P18: a block read where the owner noted "net violation by A" (A at the net 1.1 m) plus an overpass after it he does not list — the one invented touch. Unread: 1000 P4 / P25, 1100 P4 (the touch after the block reads at the net on the blocker's half), 1200 P6's last block (it lost the point). Points, winners, scores unchanged everywhere; 20260920, 1000, 1100, masnou, e1–e7 byte-identical, so the §11 bars hold as recorded; `sweep_postrun.py` not re-run (20260920 identical). 1406 tests pass.

**Owner answers (same day).** 1230 P18 WAS a block (the net violation is the blocker's) → 4 of 6 reviewed situations read, 0 false. Credit only kill blocks we are sure of. Tried: a stuff read at the rally's end (last hit above the tape at the net, ball down ≥ 1 m back on its own half within 1.5 s, one defender at the net → credited kill block) — REFUTED and reverted: its 3 reads (1200 P37, masnou P24 / P30) are all attacks that landed on the OTHER half per the reviews (the end side follows a wrong touch side); two would have credited an invented kill. No block is credited until the landing half is read independently of the touch sides. Not published (no re-publish needed: blocks are not sent yet).

