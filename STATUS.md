# Project Status

> **Convention:** this file is the cross-session memory of the project. Read it
> first when coming back. Update it (and commit it with the work) at the end of
> every working session: refresh *Where we are*, move finished items into the
> *Log*, and re-rank *Open points*.

**Last updated:** 2026-09-04 (fourth session)

## Where we are

**Analysis database + player labeling + local UI shipped (2026-09-04,
fourth session): extraction and DB are separate processes joined by a
lossless file contract.** Extraction (`make run`) now also writes
`output/<stem>/pipeline_output.json` — the canonical machine-readable
export (every emitted action keeps team/touch_number/rally_id/contact_kind/
contact_point, which the human CSVs drop; spikes minus flight arrays;
pipeline_version = git hash). A new `src/db/` package upserts that JSON
into SQLite (`data/volley.db`, WAL): `videos` (key = video stem),
`players` (names), `video_players` ((video, track_id) → player — track
ids are per-video bootstrap artifacts, NOT cross-video identities),
`actions`, `spikes`. **Overwrite semantics ratified:** re-ingest replaces
only that video's actions/spikes rows in one transaction; labels and
players survive (the ingester UPSERTs the videos row — never DELETE, which
would cascade-wipe video_players). No per-frame data stored (owner
decision). `src/db/metrics.py` computes the metric glossary at query time:
kill%/error%/dug% (denominator = attacks), hard/touch%, attack-zone
distribution, attack_zone×landing_zone placement heatmap, dig%
(denominator = opponent attacks via the player's dominant team per
video), blocks = ball-touching only with kill-block (rally ends with the
block) vs soft-block (play continues) derived from rally continuation —
no-touch blocks are never counted (owner rule; the pipeline cannot emit
them anyway). Aces PARKED (open point 13). Local web UI (`src/web/`,
`make ui`, FastAPI+Jinja, CSS-only charts — fully offline): video list,
per-video rally-grouped timeline + spike table, **labeling form**
(track→player dropdown/free-text), players overview, player detail with
metric cards/zone bars/placement heatmap/per-video splits. Gotchas
recorded: sqlite connections need `check_same_thread=False` under
FastAPI (sync handlers run in a threadpool); suite runs 262 green
(240 + 22 new: json exporter parity, ingest idempotency/label-survival/
cascade isolation, hand-computed metric fixtures, path resolution);
venv lacks pytest-cov so run `pytest -o addopts=""`. Seeded all seven
entreno videos — DB counts match the CSVs and recorded baselines (e3
14 actions/4 spikes, e6 6/2, e5 7/2). The DB is left UNLABELED for the
owner's real player names.

**e1 GT re-verification folded (2026-09-04, third session): the ratification
queue is now EMPTY.** Diagnosis (output/diag_e1_gt_reverify.py, sheets
output/gt_verify/e1_reverify_*) found the "id/team wobbles" were THREE mixed
player_id conventions in one file: 4 events in dominant-canonical ids, 2 in
L-R indices, and 3 (f36/f206/f277) in the F0-FLIPPED numbering — the f0 box
frame numbers ids 2↔3 opposite to the other 43 frames (positionally
continuous persons, only the numbers swap), and those three events follow
it. Owner ratified all corrections from the sheets: the 9 events re-expressed
under dominant canonical (f36→p2, f89→p1, f206→p4, f277→p2, f329→p1,
f371→p2 — the spiker is id2/LR3 A; f114/f257/f258 unchanged), f0 boxes
renumbered, f260's id1 B→A one-off typo fixed (it sat in the joust's nearest
box frame). **f258's block ruled NO-TOUCH** (e6 precedent extends: the GT
keeps the physical event; the pipeline legitimately emits one ball contact
per joust). Measured after the fold (same predictions):
player_accuracy_spatial **0.125 → 0.875** (L-R mirror-drops to 0.125 —
single-convention proof), labels-only F1 0.706 and team 7/8 unchanged (the
miss is the joust pair: pred's one emission is the block-A side while the
ball touch is the spike-B side). Every e1 residual is now known-class:
f114 freeball (pt 9 crossing signal), f206 set (pt 5 overhand-reception
pose), f257 joust one-emission. Suite 240 green (no code changed).

**Joust-split adjudicated + spike log detail shipped (2026-09-04, later
session): the e6 block was there but did NOT touch the ball** — the owner's
ruling closes open point 10(a): one manufactured contact IS the complete
detectable truth of the joust; a no-touch block has no ball-flight impulse,
so it is outside contact detection by design (the GT f308 BLOCK stays as a
physical event the pipeline legitimately cannot emit — no eval penalty
mechanism, no code change). Shipped alongside: the live-debug action log
now tells spikes' origin and destination — `Action: ... -> spike (0.65)
from A1` at emission (new `SpikeAnalyzer.spike_zone_for` query, takeoff
zone is known immediately) and a `Spike resolved: contact frame 308
player 1 from A1 -> lands B7 (out)` line the moment the outcome closes
(including re-logging retro-conversions: f173 logged `lands out of bounds
(out)` then re-logged `dug at A8 (dug)` when the f216 dig landed on the
"landing"). Verified on the real e6 two-pass run. Suite 232 → **240 green**
(+1 spike_zone_for, +7 formatter tests).

**Reentry contact shipped (2026-09-04): e6's out-of-frame joust spike
recovered, f265 overpass→set healed — and point 10's "instance #2" (e2 f167)
REFUTED by the sighting dump.** New REENTRY band in the classifier's
_detect_contact (next to the two bridge bands). Diagnosis: across e6's joust
the ball tracker reset at f289 (10 missing frames) and adopted a bottom-left
SPARE, so the real re-entry descent (f301–310) never reached _ball_history;
the tracker re-locked the game ball only at f314, post-joust. What the
classifier sees is a 12f sighting gap whose endpoints free flight cannot
connect (spare (34,118) → run start (1152,278): 1695px; the bridged-apex
shape it must not fire on is velocity-consistent: 34px) followed by a fast
horizontal run (≥40px/f, horizontally dominated) starting at/above the net
tape. The touch is manufactured at the gap MIDPOINT (e6 → f308 == GT
exactly), the point back-extrapolated along the run; attribution runs
normally at the manufactured frame (1A's clean pre-swap snapshot f308 is
within reach via the near-net exemption — heeding the owner's "place at/
before f308" caveat about the f311 tracker swap); gesture ATTACK (bypasses
the hands-overhead→BLOCK misread on a jumping toucher); the emitted team is
read from the takeoff stance [c-12, c-2] (SpikeAnalyzer's takeoff-window
fix, scoped to this contact kind — the contact-time snapshot is mid-jump by
construction and its airborne feet project deep).
**Measured (e6)**: +f308 spike t3 rally 1 (track 1 = the GT spiker, team A
via stance, conf 0.65) and f265 overpass→set: labels-only F1 0.667 →
**0.923** (P 1.0, R 0.857 — the only FN left is the GT f308 BLOCK, which one
manufactured contact per ball event cannot also emit), team 6/6. **A/B:
e1/e2/e3/e4/e5 byte-identical** (the identity-break gate is what keeps e2's
bridged apex at f149 out); production src.main path emits the same 6-event
stream. **e2's f167 is NOT a reentry case**: the tracker bridges the toss
apex (f141→f149) and the spike is a plainly visible bounce at f167 (rises
148/136px — the normal detector FIRES); the event dies at the reach gate by
4px (nearest snapshot box top 144px below the ball vs CONTACT_REACH 140),
and the true toucher (GT p3 B) is airborne and coasted ~200px away mid-jump
— a reach/ghost-drift residual (folded into point 7), not point 10. Suite
**232 green** (+8 reentry tests).

**Spike analytics shipped (2026-08-30): trail, touch/hard type, 9-zone attack
grid, kill/out/dug outcomes — plus an f297 GT correction that needs one more
owner pass.** New pure-observer `SpikeAnalyzer` (src/analysis/
spike_analyzer.py) wired into `FrameProcessor` (constructed/observed/flushed
there; live debug and the script only READ it — mirrors-pipeline rule holds).
A/B on entreno_3: the action stream is **byte-identical to HEAD** (0 base-field
diffs; only additive spike keys on the log's spike entries). Suite 198 → **220
green** (+22, tests/test_spike_analyzer.py). What was measured/built:

1. **Zone grid** (`CourtCalibration.world_point_to_zone` / `get_court_zone`):
   9 zones per half, numbered 1-9 left-to-right as seen standing at the net
   facing that side's OWN baseline — 180°-rotationally symmetric, so in camera
   view A's zone 1 is image-RIGHT at the net, B's is image-LEFT. NOTE: this is
   the mirror-swap of the ASCII sketch first drawn in the request; the GT
   anchors decide (both A attacks come from image-right at the net = "A1",
   f178's B attack from image-right = "B3"). GT attack zones: **4/4 exact**
   (B3/A1/B2/A1) after adding a takeoff-window fix — a jumping spiker's feet
   at contact are airborne and the homography projects them deep (f431 read
   B5 from airborne feet; the pre-contact stance closest to the net in
   [c-12, c-2] reads B2 ✓).
2. **Spike type by POST-CONTACT ASCENT, not exit speed** (TOUCH_RISE_PX=80):
   diag on the real sightings showed exit speed CANNOT separate the classes —
   the touches launch at 19-29 px/f (vertically!) while f431's hard ball left
   near-rest and fell. Ascent separates cleanly: touches rise 146-240 px above
   contact, hard balls ≤33 px. GT types: **4/4** (touch/touch/hard/hard).
3. **Outcome machinery**: landing = image-y descent terminating (bounce flip
   or quiet-loss); kill/out from the landed point's world coords; dug/blocked
   from a follow contact; **retro-conversion**: a just-committed kill/out
   whose ball then LOFTS ≥90 px (DIG_LOFT_PX — sand cannot rebound 2-3 m)
   within ±12f of a follow contact flips to dug. Trails render red fading
   (`overlay.draw_ball_trail`, TRAIL_MAX_AGE=45) + `KILL <zone>` marker +
   `spike hard`/`spike touch` labels in live-debug and the script; NO zone
   grid drawn (owner spec). CSV: `<stem>_spikes.csv` + per-player zone/kills
   tallies in statistics; evaluate.py scores spike_type/attack_zone/
   landing_zone/outcome on matched pairs.
4. **e3 GT**: f297 corrected to **spike A p3 t3** (owner decision — it was
   p4 B t1; A's f248 set is t2, so A's t3 is the rainbow; cascade recomputed:
   f332 dig B t1 pre_atk, f379 t2, f433 t3). Team accuracy 14/14 now (the old
   f294 over-set residual is GONE — open point 3 closed). New GT fields on
   the 4 spikes (spike_type/attack_zone/outcome/landing_zone), README +
   verify_action_labels updated.

**Outcome semantics completed (2026-08-31, owner ratification): kill = direct
fall OR dug-and-dies-without-a-set.** The owner adjudicated the four e3
"kills": the whole video is ONE point — f178/f297/f433 were dug AND set
(outcomes now `dug` with `dug_zone`, the annotated zones reinterpreted as
where the dig happened), and f541 is the rally-winning KILL (dug at f563, the
ball falls with no set; the owner's "8 B" annotation stands, measured fall
B7). Shipped as a pending-dug watch in SpikeAnalyzer: a dug record stays
provisional until a later touch event (kept up -> `dug`) or a CONFIRMED ball
death (`kill` at the fall point, in court or out). The confirmation window
(DUG_DEATH_CONFIRM_FRAMES=16 + loft rejection) is load-bearing: the descent
into the setter's hands looks exactly like a landing, and the set EVENT
arrives too late (lookahead emission ~f255 for a f248 set) to veto it — only
the physical loft test separates them (the real f539 death bounces 12 px; the
three set contacts loft 150+ px). **Final e3 numbers: outcome 4/4, dug_zone
3/3, spike_type 4/4, attack_zone 4/4, team 14/14; the single residual is the
kill's landing zone (measured B7 vs annotated B8 — the fall at world x≈1.9 m
is one column left of middle).** Suite **223 green** (+2 dug-kill tests).
Known-class miss unchanged: the f294/f297 pair fails the player-spatial gate
(pred center above the net resolves to the adjacent net player's box at the
10f-strided GT frame; the pred's team/player are right per the corrected GT).




**Off-court hold horizon shipped (2026-08-29): e2's wasted roster slot
recovered.** The owner's e2 tracking report decomposed into: (a) a
right-side OUT-OF-COURT bystander (x≈1660–1890, detected at conf 0.82–0.89,
feet beyond the right sideline) who straddled the line during bootstrap,
seeded a track, and was then fed CONTINUOUSLY for 415 frames by
`_may_feed_track`'s "continuously matched frame-to-frame" exception — which
had NO horizon and outranked both the grace window and the zone rules; (b)
the server (p1 A), out-of-court AND beyond the 1m zone margin at f0–8 →
never admissible, in court from f28 with no free slot; (c) t1 ghosting
(slot starvation). Fix: the continuous exception now expires
`player_off_court_hold_frames` (90) after the track's last IN-COURT
sighting → the track coasts, retires through the normal path, and strict
admission/gallery-restore re-takes the slot (measured on e2: bystander
coasting from f104, id reused by an in-court player from ~f188). Safety:
max real-player out-of-court streak measured on ALL GT videos = 46f (e6),
90 = 2× margin; zone-seed rules untouched (trial expiry governs them).
**A/B (6 videos, identical feeding): e1/e3/e4/e5/e6 byte-identical (0
differing frames); e2 changes only from f104** (the bystander's coast) with
one attribution change in the action stream (f256 set → track 2; labels/
teams identical). e2 actions F1 unchanged 0.571 — its residuals are the
known recall/label classes, not tracking. Accepted limitation: the f32
serve stays mis-attributed (server unadmissible before the slot frees;
widening the zone margin to reach x≈73 would re-open the e5-squatter door).
Suite 198 green (+5 tests). **Diag gotcha recorded:** two PlayerTracker
instances in ONE process permute bootstrap ids — `cv2.kmeans` consumes the
process RNG; A/B harnesses must `cv2.setRNGSeed(0)` per instance (production
single-run is deterministic; fresh process = fresh RNG).

**Short-gap bridge shipped (2026-08-27): e2/e6's missed digs recovered.**
The e2/e6 contact-recall residual (old open point 7) split into two classes
on diagnosis. (a) A **5–7-frame occlusion at the toucher's arms** — e6 f212
and e2 f206, both sheet-proven — sat in a hole between the normal detector
(needs ≥2 points within NEIGH per side) and the bridge (floor was 8f). The
bridge now takes gap 5–7 under three extra gates: the normal path PROVABLY
cannot fire (sparse NEIGH on ≥1 side), ball-identity continuity
(|Δx| ≤ max(24, 3·gap)), and for sparse re-acquisition a CROSS-GAP RISE
(first post-gap sighting ≥60px above the last pre-gap one — needs no future
points; decision time is c+7 and the right window ends at c+6). A/B on all
six videos: e1/e3/e4/e5 **byte-identical**; e2 +f209 dig with the cascade
healed (f256 dig→set t2, f306 t3); e6 +f216 dig t1, f265 dig→overpass t2
(GT set — blocked on the joust, open point 10). Labels-only F1: e2 0.222 →
**0.600**, e6 0.545 → **0.667**. Suite 193 green. (b) The **e6 f311 joust
is structurally invisible** to any descent/ascent bridge — the set toss
exits the frame top at f277 and the ball re-enters at net height f314
already deflected; the f289–302 "ball" is a bottom-left spare handled by 1B.
A "reentry contact" mechanism is diagnosed and parked (open point 10).
**GT ratification queue is loaded for the owner** (open point 11): e2's
three unmatched preds are REAL touches (f32, f118 set, f327 dig — sheets),
e2 f79 is a caught/held feed ball (static f78–82, then a toss —
pipeline-invisible by design), e6's f311 block team B is almost surely A.

**entreno_5's action layer is fully resolved (old open points 1+2 closed,
2026-08-26).** The GT now carries the owner's dictated truth (serve f20 p2
added, frames 63/111/160/200, six id corrections) plus two contact-sheet
corrections of our own (f160 spiker is GT4 not p3; f300 spiker is GT2 not
p4 — sheets in output/gt_verify/, **owner-ratified 2026-08-26**). Against
it the pipeline reads **7/7 contacts, 7/7 labels, 7/7 teams, 6/6 scored
players** (gated F1 0.857; the 7th pair's GT box is occlusion-flagged).
The fix was diagnosis-first and turned out to be ONE root cause, not a
disambiguation problem: the missed f111 set made the f60→f157 gap (97f)
exceed rally_reset_gap=90, corrupting every downstream touch number
(spike→dig→set→dig cascade). Two shipped mechanisms:

1. **Gap-bridged bounce** (`_bridge_contact`, classifier): the ball is
   often UNDETECTED across a touch (occluded at the toucher's hands —
   sightings fall to f102, resume rising at f114). A bounce whose bottom
   sits inside an 8–14-frame sighting gap now fires at the gap's first
   sighting with the touch point interpolated. Gates are deliberately
   strict (net descent ≥20px in, ascent ≥60px out — a sand rebound rises
   ~25px and must not read as a touch; gaps <8f are the normal detector's
   turf) so entreno_1/3/4 histories yield ZERO candidates — their streams
   are unchanged (e1/e4 byte-identical; e3 differs only in f539's
   self-reported L-R index 2→3, same attributed player by center).
2. **near-net exemption 1.5 → 2.5 ground metres** (config
   `attribution_near_net_exempt_m`): e5's f300 spiker took off 2.14m from
   the net and the width regime (36–40px) mis-called his side; at 1.5m the
   exemption missed him by 0.64m and the reach gate killed a DETECTED
   contact. The above-net-tape condition stays, so e3's f488-style
   below-tape set thief is still excluded. With the contact recovered it
   even reads gesture ATTACK → spike 0.65.

Production (`src.main`) verified to emit the identical 7-event stream on
e5. Suite 187 green. evaluate.py now scores BOTH GT player-id conventions
(e1/e3 actions are L-R indices, e4/e5 canonical — see previous commit);
with honest gating e3's gated F1 is 0.929, not the 1.0 previously recorded
(the f69 known misattribution used to count as TP by numeric coincidence).

**Generality + e1 (2026-08-26, later session):** e2/e6 (first runs on the
current stack) show zero bridge false positives and teams 1.0 on scored
pairs; their residual is genuine contact recall (e6 3/7, e2 2/4). e1's GT
turned out to be double-annotated (17 events ≈ 9 touches) — after dedup +
arbitration e1 detects 8/9 contacts with 3 known-class label residuals, so
the old "e1 = contact-recall-limited" story is retired. Current action
scores (labels-only F1): e3 0.929, e4 0.857, e5 0.857 (7/7 labels), e1
0.471, e6 0.667, e2 0.600 (both e2/e6 moved by the 2026-08-27 short-gap
bridge). (2026-08-28 ratification rounds: e2 **0.571** vs its complete
8-event GT, e6 0.667 vs the owner-corrected GT — the e2 dips along the way
were denominator honesty: each ratification round exposed events the GT
had been under-counting, and every remaining miss is now a diagnosed
class.)

**Team-aware contact attribution is shipped and GT-validated** on
entreno_3 (2026-08-16): team accuracy 0.69 → 0.92, label F1 0.90 → 0.93,
serve detected. Design: candidates filtered by expected touch team (ball
pixel-width regime + possession alternation), per-contact foot teams,
ground-metre near-net exemption, emitted team = toucher's foot team.
Residuals unchanged: e3 f294 over-set (width abstains), f69 same-team
adjacent choice.

Below that, the player-identity stack stands as of `63ec741`: seed-dedup +
serve-zone admission (server tracked from f0, entreno_3 detection 0.96 /
id_consistency 0.97), bystander guard, upward-only ghost damping. 94 of the
113 tests predate this session.

**Config-drift guard (2026-08-17, later session):** `tests/test_config_drift.py`
(54 tests) locks the four seams where production and the GT scripts can
silently fork — DEFAULT_CONFIG ↔ component ctor defaults ↔ GT-script literal
kwargs + argparse defaults ↔ inline `.get(key, fallback)` fallbacks — so the
f539 block/spike class of bug can't recur unnoticed; 9 stale inline fallbacks
defused the same day. Suite 167 green.

**entreno_4/5 (2026-08-18):** owner-annotated GT (players every 10 frames, 6
action events each — no serves, no occlusion flags, noisier footage as
warned). e5's serve-zone-squatter tracking bug (bystander held the 4th slot
all video, server untracked) FIXED via server-vote admission + contested
swap + trial expiry: e5 tracking 0.722/0.278 → 0.958/0.042, the serve is
detected (f17), byte-neutral on e1/e4, action-stream-identical on e3. The GT
mis-ID corrections and the action-layer residuals were this session's work
(see the 2026-08-26 entry).

**Near-net flag (2026-08-17, later session):** old open points 4+9 closed by
diagnosis — 4's px→metres switch is GT-refuted (label F1 0.929 → 0.857/0.714):
the px `near_net` is load-bearing for the resolver's touch-3-at-net spike
rule. Point 9's block turned out to be REAL on the production/live-debug path
(a config divergence, fixed same day — see Log); the script path (all GT
numbers) always said spike. Details + revisit trigger in Open point 4 and the
Log.

**Perf (2026-08-17):** the detector device defaults were silently CPU —
`BallDetector`/`PlayerDetector` shadowed `BaseDetector`'s `"auto"` with their
own `device="cpu"`, so every bare construction (the annotator included) ran
YOLO on CPU (~150ms per annotation interaction). Defaults are now auto (MPS);
the annotator also gained sequential forward seeks (~6ms vs ~65ms keyframe
seek) and a (frame, mode) detection cache → ~30-40ms per interaction,
revisits free; pose runs the lite model (`pose_complexity` 0, new default)
after a byte-identical GT A/B on entreno_1/3. Pipeline per-frame ~102 →
~81ms. Live debug deliberately untouched — the owner wants it identical to
the shared pipeline for real debugging. Next lever if ever wanted: pose only
for near-ball players (measured 52→~26ms; needs an occlusion-window fallback
first).

**Plan reference:** the full design lives in the session plan file
(`~/.claude-zai/plans/i-want-to-start-golden-naur.md`, identity) and
(`~/.claude-zai/plans/read-status-lets-try-imperative-anchor.md`,
attribution — including the recorded design pivot away from image-plane
trajectory side). Short version of the identity architecture: uniforms vary/
are uncontrolled → colour can't be a trusted identity signal → **motion
continuity is the primary identity signal**, appearance/body-size are
conditional tie-breakers, and "exactly 4 players / 2 per side" is a hard
constraint. Side changes need no special handling as long as IDs survive.

## Open points

1. **[diagnosed 2026-08-18 — pre-existing, NOT the serve-zone fix] e1/e3
   tracking baselines are stale.** Old-code (HEAD pre-fix) e1 dump scores id
   0.771 / ghosts 0.193 vs the recorded 0.978/0.133; e3 id 0.952 vs 0.972.
   Byte-identical A/B (git stash) proves the serve-zone/vote/swap diff is
   e1-NEUTRAL (0 differing frames) and e3-neutral beyond 7 lock-window frames
   (server admitted ~6f later; action stream byte-identical). The drift crept
   in between the 2026-08-16 servezone baselines and HEAD — prime suspect: the
   08-17 ball_confidence 0.7→0.15 fix (the dump's ball detector feeds
   ball_active → bootstrap timing) or device CPU→auto. Diagnose when touching
   tracking next; until then, compare A/B, not vs recorded numbers. (Tracking
   numbers vs the flag-occluded e4/e5 GT denominators also moved for that
   reason: e4 0.949→0.974 detection, e5 ghosts 0.042→0.083 — occluded GT
   boxes leave the denominator and their covering preds now count as ghosts.)
2. **[BLOCKED — no footage] Validate side-change survival on a real match.** The
   gallery's marquee use case (players swap ends every 7 points) is untested —
   the entreno drills have no side changes. Blocked as of 2026-08-14: no video
   of a full set is available yet. Unblock by recording/obtaining one
   set-to-21 clip, calibrated, then:
   `python scripts/dump_player_tracks.py <match>.mp4 --max-players 4` →
   `python scripts/analyze_tracking.py <json> --max-players 4`, and scrub the
   annotated video through a side change watching each ID.
3. **[RESOLVED 2026-08-30 by the f297 GT correction] Over-set crossings without
   width evidence.** The e3 f294 residual was the GT, not the pipeline: the
   owner corrected f297 to a team-A touch-3 spike, and HEAD's own emission
   (f294 spike, team A) is now fully correct — e3 team accuracy 14/14. The
   mechanism note stays for future footage: when a set/dig crosses the net but
   the tracked ball's widths sit in the 26–35px abstain band, possession
   carries and the next contact can be attributed to the wrong team.
4. **[diagnosed 2026-08-17 — deliberate no-change] The gesture path's image-px
   `near_net` is load-bearing; a px→metres switch is GT-refuted.**
   `_build_contact`'s `is_near_net` (px, `NEAR_NET_PX=120`) feeds BOTH
   `_detect_gesture` and the resolver's touch-3-at-net spike rule
   (`action_context.py:146`). Switching to ground metres regresses entreno_3
   label F1 0.929 → 0.857 (≤2m) / 0.714 (≤1.5m): GT spikes f174/f431/f539
   were hit from 1.79/3.77/1.96 m and only the px far-half swallow (every far
   player "near net") makes the resolver's rule fire for them; keeping all
   labels needs M≥4 m — re-encoding today's behaviour under a false name. The
   gesture layer itself is rule-INSENSITIVE on all GT footage (identical
   gestures under px/m1.5/m2.0 on entreno_1+3; every gesture-deciding contact,
   incl. entreno_1's only block at 0.23 m, sits within 2 m). The px boundary
   is nonsense in the abstract (server at 8.4 m reads far, a digger at 8.0 m
   reads near) but no footage we own can distinguish the rules. (2026-08-17
   addendum: production/live-debug briefly DID take the BLOCK branch at f539 —
   a config-default divergence, fixed same day, not a near-net regression; all
   measurements above are from the script path and remain valid.) Revisit when
   match footage exists (real overhead digs vs blocks at depth): re-run
   `output/diag_gesture_net.py <match>.mp4 --modes px m1.5 m2.0` and switch
   only if gestures differ.
5. **[same-team adjacent-player choice.]** The team filter constrains the TEAM,
   not which teammate — entreno_3 f69's dig goes to the wrong B player (both
   runs, team correct; now also visible as e3's only gated-F1 miss under the
   honest scorer). Needs pose/reach signals, not team logic.
6. **[conditional] Phase 2: offline global stitch.** (unchanged) Post-processing
   pass that re-clusters all track fragments into exactly 4 identities. Only
   build if match validation shows residual swaps/fragmentation that phase 1
   doesn't catch.
7. **[narrowed 2026-08-27; e2 f167 RE-DIAGNOSED 2026-09-04].** recall
   residuals after the short-gap bridge. The two missed digs (e6 f212, e2
   f206) are fixed. e2's remaining misses: f90 held-ball release
   (structurally invisible), f32 serve mislabel (tracking — see below),
   f118 overpass-vs-set (its follow is the undetected f167), and f167
   itself — **NOT a reentry case** (the old point-10 story is refuted): the
   tracker bridges the set-toss apex (f141→f149, identity kept) and the
   spike is a plainly visible bounce at f167 (dense sightings, rises
   148/136px); the event dies at the reach gate by 4px (nearest snapshot's
   box top 144px from the ball vs CONTACT_REACH 140) — and that nearest
   snapshot is the WRONG human anyway: the true toucher (GT p3 B) is
   airborne at f167 and coasted away mid-jump (t1B real sightings stop at
   f150, resume f192, ~200px off the ball). Fixing it needs jump-aware
   reach/ghost handling (airborne reach extension, or anti-drift coasting
   through jumps), not a new contact detector. e6's f265/f308 residuals
   are RESOLVED (2026-09-04, reentry contact). e1's far-side player recall lever
   (`player_confidence` 0.5→0.35, `player_imgsz` ↑) is unchanged/untried.
   **e2 tracking observation (owner 2026-08-28) — squatter RESOLVED
   2026-08-29** by the off-court hold horizon (see Where we are): the
   out-of-court bystander no longer holds a slot (coasts from f104, id
   reused by an in-court player from ~f188). Still open on e2: the server
   is inadmissible before f28 (out-of-zone at video start) so the f32 serve
   stays mis-attributed; and "p3 untracked at f90" did NOT reproduce as a
   tracking gap (t3 is real on the far receiver f80–94 in the audit —
   possibly the owner meant the near-side player; ask before chasing).
   e2/e6 GTs still lack player boxes
   (no team/player spatial scoring; raw-id gating makes their gated F1s
   look brutal — pred player_id is the L-R index, point 8).
8. **[minor, eval] pred `player_id` is the L-R index among FILTERED
   candidates.** `_closest_player_at` computes the emitted L-R index over the
   team-eligible snapshot set, not all tracked players — the index shifts when
   the filter set changes (seen: e3 f539 pid 2→3 after the exemption widened,
   same attributed player). Harmless today (spatial scoring is
   convention-free) but worth knowing when reading logs.
9. **[small, resolver] Overpass is only detectable at touch-2 — and
   "freeball" wants the same missing signal.**
   `ActionContextResolver` labels a no-follow second touch overpass; a
   LATER touch that crosses without attack gesture reads dig (e1 f113:
   GT overpass at touch-3, pred dig). Extending the rule needs the
   ball-crossing signal threaded into the resolver — a naive "last touch
   with no follow → overpass" breaks e4's f347 dig (last event, no follow).
   One GT event; do it with the crossing signal or not at all.
   (2026-08-27 addendum: e6's f265 now lands here too — with the f212 dig
   recovered it reads touch-2 no-follow overpass while GT says set; the
   follow it needs is the f311 joust, i.e. point 10. Same fix shape.)
   **(2026-09-04: e6's f265 RESOLVED — the reentry contact supplies the
   follow and f265 reads set. e1's f113 remains, parked on the crossing
   signal.)**
   (2026-08-28: owner adopted the vocabulary split — **overpass** for a
   touch-1/2 crossing, **freeball** for a touch-3+ soft cross; e1 f114
   relabeled overpass→freeball in GT. Pipeline emission of freeball stays
   parked here until the crossing signal lands: a touch-3+ no-follow is
   ambiguous between "crossed" (→ freeball) and "detection missed the
   follow" (→ dig, e4 f347) without it.)
10. **[RESOLVED 2026-09-04 for e6 — the reentry contact shipped; "instance
    #2" refuted; joust-split adjudicated (later session).]** The e6 joust spike (f308 1A t3) is manufactured by the
    REENTRY band in _detect_contact (full story in Where we are): f265
    overpass→set healed, labels-only F1 0.923, six-video A/B byte-neutral
    on e1–e5. (a) **RESOLVED by owner ruling (2026-09-04, later session):
    the block was present at the joust but did NOT touch the ball** — no
    joust-split mechanism is wanted or needed; one manufactured contact is
    the whole detectable truth, and the GT f308 BLOCK (2B t1) records a
    no-touch block that contact detection cannot and should not emit.
    (b) ROOT CAUSE untouched — remains open: the
    BALL tracker's post-reset reseed adopted the left spare (e6 f289), which
    is why the real re-entry descent (f301–310) is unrecoverable to the
    classifier — a smarter reseed (prefer in-flight balls over static/spare
    ones) is a possible future lever, six-video A/B required. **e2 f167 was NOT a reentry case** (see point 7).
    Evidence history: the toss exited the frame TOP at f277 [1166,17] still
    ascending; the contact happens above/entering the frame; the ball
    re-enters at f314 [1152,278] — above the net tape (verified via
    `is_above_net`) — flying left at ~48px/f with dense sightings f314–319;
    the tracker's f289–302 "ball" is a bottom-left spare (sheet-proven).
    Sub-shapes differ across footage: e6 = horizontal re-entry AT net height
    (deflection exit); e2 = steep descending re-entry (attack landing
    flight) — the mechanism's horizontal-dominance + identity-break gates
    cover the first and correctly refuse the second (it is ordinary flight;
    see point 7). Owner caveat heeded: the tracker swaps players at f311,
    so the event is placed at/before f308 (gap midpoint) and attributes off
    the clean snapshots. Original trace: output/diag_e6_missed.py, sheets
    video_entreno_6_f296-322; new evidence: output/diag_reentry*.py.
11. **[RESOLVED 2026-09-04 (third session) — ratification queue EMPTY].**
    History: the 2026-08-28 round folded e2's complete 8-event rally, e6's
    joust re-correction, e1's joust arbitration, and the freeball vocabulary;
    the 08-28 later rounds dropped e2 f79 and completed e2's rally. The last
    item — e1's residual id/team wobbles — was resolved by the 2026-09-04
    re-verification session: the wobbles were three mixed player_id
    conventions (see Where we are); all 9 events now use dominant canonical
    ids, the f0/f260 box wobbles are fixed, and the owner ruled f258's block
    no-touch (kept in GT as a physical event). e1's player spatial accuracy
    is 0.875 (was 0.125); remaining e1 residuals are known-class label
    issues, not identity.
    FOLDED: (a) e2 +3 events — f32 **serve p1 A t1** (the untracked near-left
    server, owner-marked in white on the sheet; the pred had attributed the
    contact to nearby tracked 2A → dig), f118 set p4 B t2, f327 dig p4 B t1.
    e2 GT is now the complete 7-event rally (serve → catch → set → dig →
    set → spike → dig); labels-only F1 vs it: **0.615** (6/7 matched; the
    two label misses are known-class: f32 dig-vs-serve = the untracked
    server, f118 overpass-vs-set = its follow is 91f, one frame past
    rally_reset_gap=90). (b) e6's joust RE-CORRECTED beyond our proposal:
    contact at **f308** (not f311), the SPIKER is **1A** (A's 3rd touch —
    consistent with A's dig f212 + set f262), the BLOCKER **2B**; old
    f311 spike-p4-B/block-p3-B replaced. Owner observed the TRACKER swaps
    players at f311 and tracks something out-of-court there while f308
    labels are correct — an e6 tracking bug with no GT to measure it (e6
    has no player boxes). (c) e1's joust arbitration RATIFIED as-is (f257
    spike p3 B, f258 block p1 A — JSON already correct). (d) **freeball**
    added to the GT vocabulary (owner decision): overpass = touch-1/2
    crossing, freeball = touch-3+ soft cross; e1 f114 relabeled
    overpass→freeball (pipeline emission parked on the crossing signal,
    point 9). REMAINING: (e) RESOLVED 2026-08-28 (later round): f79 dropped —
    the owner's full re-read of e2: NO dig at f79; the rally is serve f32
    p1 A → **dig f90 p3 B t1** (reception) → set f120 p4 B (frame corrected
    from our f118) → **spike f167 p3 B t3** (un-annotated before; explains
    the steep f185–202 descent into A's dig) → f206 dig p3 A (now
    preceded_by_attack TRUE) → f257 → f305 → f327. e2 GT = 8 coherent
    events; labels-only F1 **0.571** with every residual known-class:
    f32 dig-vs-serve (untracked server), f90 undetected (held-ball
    release — static hold f78–82 then play, no descent signature,
    structurally invisible), f118 overpass-vs-set (91f follow), f167
    undetected (reentry, point 10's SECOND instance). (f) e1's residual
    id/team wobbles — RESOLVED 2026-09-04 (third session): three mixed
    player_id conventions diagnosed, all events re-expressed canonical,
    f0/f260 box wobbles fixed, f258 block ruled no-touch (see Where we are
    and the resolution note above).

12. **[RESOLVED 2026-08-31 — owner ratified the semantics] e3's four GT
    "kills" were three digs + one real kill.** The owner's rule: kill = the
    ball falls directly, OR is dug and dies without a set (in court or out
    of bounds); the whole e3 video is one point. GT now: f178/f297/f433
    `dug` (dug_zone A7/B8/A5 — the originally annotated zones, reinterpreted
    as the dig locations), f541 `kill` (landing B8 annotated; measured B7 —
    the one residual). The analyzer implements exactly this
    (DUG_DEATH_CONFIRM_FRAMES + loft rejection); eval: outcome 4/4,
    dug_zone 3/3. Small follow-up if the owner wants: a `target_zone` field
    (attack placement) is NOT yet modelled — the GT zones double as dig
    locations today.

13. **[PARKED 2026-09-04 — no point-outcome detection] Ace metric.** The
    DB/metrics layer (fourth session) deliberately ships without aces:
    an ace needs "point won directly off the serve", which needs rally
    outcome/score detection the pipeline does not have. Two unblock paths
    when wanted: (a) ratify a derived heuristic in the metrics layer — a
    serve whose `rally_id` contains no opposing-team touch after it ≈
    likely ace (flagged as derived; zero pipeline change); or (b) real
    point-outcome detection (score machinery exists in
    `src/analysis/game_state_manager.py` but is unvalidated). Assist proxy
    (set → same-team kill) is parked with it — same dependency.

## Log (newest first)

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
