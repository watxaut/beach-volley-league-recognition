# Serve reliability plan (session 55, 2026-10-02)

> Planning doc only. Nothing in `src/`, `scripts/` or `ground_truth/` was changed
> to write it. The numbers below come from STATUS.md plus a read-only fact probe
> (no decode) run this session; the probe's sources are cited per row.
> Task IDs are **SR0-SR7**. STATUS open point **30** tracks them.

## 1. Why the serve matters

The serve is the one event every point has. It opens the point (point
segmentation), names who served (the serving team is the winner of the previous
point, so it also feeds the winner layer), and it is what aces and service faults
hang on. Ace and serve-fault are the two fantasy items still BLOCKED (G1). On
this camera, the serve is also the most constrained event: it happens after dead
time, the server stands behind a baseline, it happens once per rally, and the
beach rules fix who serves next.

## 2. Where serves really stand (honest baseline)

| stream | near serves | far serves | false positives | source |
|---|---|---|---|---|
| production action stream, `serve` at ±15 f, match P1-P33 | **8/16** | **0/17** | **12** emitted serves with no GT serve | recomputed from `output/serve_relabel.json` `actions_pass2[].action` |
| same, held-out P9-P33 only | 7/13 | 0/12 | 6 in scored region | `output/heldout_contacts/g1.json` |
| entreno e2/e3/e5/e6/e7 (all near) | 4/5 (e2 missed) | — | — | `output/video_entreno_*` |
| serve EVIDENCE layer (#53/#54), far only | **not observed** | 14/17 anchored, **9/17 bound** (dev 5/5, held-out **4/12**) | 1 owner FP | `docs/g4_serve_evidence.md` |

So the production serve recall over the real match is **8/33 = 0.24**, and its
precision is **8/20 = 0.40**. Fifty-four sessions in, the serve is not reliable
on *either* side.

Two corrections to the record:

- `docs/g3_heldout_p9_p33.md` reports near serves as 11/13. That number counts a
  serve if the production label **or** the pass-2 re-label says serve
  (`scripts/score_heldout_contacts.py:326`). The production stream alone is 7/13.
- The far-serve "14/17 with zero false positives" comes from a 648-combination
  sweep fit on **all 17** far serves, held-out ones included. So it is an
  in-sample number. The only out-of-sample signal is the consumer's held-out
  binding, **4/12**. That drop from dev 5/5 to held-out 4/12 is what overfitting
  looks like.

## 3. Are we going in the wrong direction? Yes, in five specific ways

1. **We have been solving a proxy.** Since #38 the work has chased a frame-exact
   (±15 f) *far* serve *contact* in the ball-trajectory action stream. The goals
   need something else: a **per-point serve record** saying when it happened,
   which side and squad served, who served, and whether it was received, an ace,
   or a fault. A contact frame within ±0.5 s is one field of that record, not
   the product.
2. **We have been fitting one match.** Every far-serve rule (T5, R1, S1,
   scale-aware geometry, G4, M1-M3, the selector) was designed and tuned on the
   same 17 serves of one recording session. More rule tuning on those 17 serves
   now *lowers* our real confidence. No serve rule should be tuned again until
   serve GT exists from at least two more sessions.
3. **The near side has no plan.** The near serve, which should be the easy one,
   is a coin flip in production (8/16). The evidence layer does not look at it
   by design. "Reliable serves" has to mean both sides.
4. **Two strong, geometry-independent signals have never been tried.**
   - **Audio.** Every video, including the match, has a real AAC 48 kHz stereo
     track (match mean −35 dB, max −4.6 dB). The pipeline never reads it; the
     only mention is a docstring in `src/utils/video_upscale.py`. Hand-to-ball
     contact makes a sharp transient that does not get smaller in pixels at the
     far end. That is exactly the scale wall the px-space levers kept hitting.
   - **The beach rules.** The winner of point k serves point k+1. A team that
     wins the serve back hands it to the partner who did not serve last time.
     Sides switch every 7 points (S3 recovered this exactly). Together these
     rules pin the server's identity and strongly constrain the serving side
     across a match. Nothing decodes the serve sequence jointly. Each point is
     guessed on its own.
5. **The headlines over-claim.** "SOLVED AS EVIDENCE" stands for an in-sample,
   far-only, 9/17-bound result, and that wording has steered the backlog. It is
   corrected in STATUS this session.

**What is still right:** perception stays causal and single-pass, and hindsight
stays post-hoc (AGENTS.md §6). The opener gate is a real structural fact
(openers ≥153 f of dead time, mid-rally gaps ≤134 f). The structural far-side
arm and the runway occupant are good *proposal* evidence. And the rule "evidence,
not labels, until validated" holds. None of that is thrown away. It gets
re-used as inputs to a per-point record.

**Stop list (do not start these until the triggers below fire):**
- more px-space or contact-geometry far-serve thresholds;
- more selector or sweep constants on the 17 match far serves;
- tracker-admission work aimed at far serves;
- relabeling the reception as the serve (S0b: it broke 3 correct digs).

## 4. Target: the per-point serve record

One record per point (dead-time episode that opens a rally):

```
{point, t_contact (PTS s + frame), side (near|far), squad, server_track_id|null,
 outcome (received|ace|fault_net|fault_out|unknown), confidence, evidence[]}
```

**"Reliable"** (pre-registered acceptance, measured on a session NOT used to
design the rule, ±15 f ≈ ±0.5 s):
- serve recall **≥ 0.90 on each side**;
- serving-side/squad accuracy **≥ 0.95**;
- **≤ 0.1 false serve records per point**;
- server-identity accuracy **≥ 0.90** once SR5 lands.

Stop rule: if SR4 is below 0.75 recall on either side on the held-out session,
stop adding hand rules and go to SR7 (learned) as soon as its data trigger
allows.

## 5. Tasks

### SR0: one serve scorer and the honest baseline (worker, no decode, ~½ session)
- `scripts/score_serves.py`: scores any stream against every serve GT (match
  P1-P33, entreno e2-e7, plus new sessions as they arrive). Streams: production,
  pass-2, `serve_evidence.json`, GAME_ON episode starts (backdated burst start),
  and later the SR4 records.
- Reports near and far **separately**, dev (P1-P8 + entreno) vs held-out
  (P9-P33) vs each new session, side accuracy, false positives per point, and
  the time offset distribution.
- Gate: it must reproduce production near 8/16, far 0/17, 12 FP. It must label
  the #53 structural numbers *in-sample*.
- Cheap side question this answers: how close does the **GAME_ON episode start**
  already land to the GT serve? If the rally onset is already within ±0.5 s on
  most points, SR4 mainly needs timing refinement plus side, not proposal.

### SR1: near-serve miss taxonomy (worker, diagnose-only, existing outputs)
- For the 8 missed near match serves and e2 f32, find the first failing stage:
  no candidate, gate, label (dig/set instead of serve), team/side, or late.
- Near balls are 40-57 px and the tracker locks them, so the cause is most
  likely in the label or `rally_start` logic, which makes it cheap.
- Output a bucket table. Design nothing until it exists (diagnose-first).

### SR2: audio onset probe (worker, diagnose-only, audio decode is seconds)
- `scripts/probe_audio_onsets.py`: ffmpeg to mono, onset strength (spectral
  flux, high-passed to about ≥1 kHz to drop wind), peaks mapped to video frames
  **by PTS, never by frame index** (VFR, AGENTS.md §7/§9).
- Measure:
  - (a) the A/V offset, from near-side GT contacts;
  - (b) the share of GT contacts with an onset within ±2 f, split near/far and
    serve/non-serve, over 211 match + entreno contacts;
  - (c) the serve proposer "first onset above θ after ≥ D s with no onset or
    contact", scored on the 33 match serves + 5 entreno, the 24 mid-rally
    controls, and the 9 owner FALSE/OFFGAME moments.
- θ and D are chosen on dev (P1-P8 + entreno), then frozen and scored once on
  P9-P33.
- Pre-registered kills:
  - **K1:** onset present at < 70% of GT serves on either side, which refutes
    audio for serve timing;
  - **K2:** proposer precision < 0.8 on dev, which means audio is timing
    refinement only, not a proposer;
  - **K3:** far-side onset rate more than 15 points below near, which means mic
    distance dominates and audio is near-only.
- Known risks to look for: beach wind, neighbouring courts, voices and claps,
  and the ball landing in sand (a thud).
- **Owner decision D1** comes *after* the probe: production use means an audio
  side channel read inside the shared `process_frame` path (live parity, §2).
  That is a new perception input, outside §6's "already-computed values" rule,
  so it needs explicit ratification.

### SR3: serve-only GT on two new sessions (OWNER, async; highest-value input)
- One dictated line per serve: `mm:ss.s  near|far  server(optional)
  outcome(received|ace|fault)`. That is about 1 line per point, far cheaper than
  full contact GT. Convert timestamps to frames by PTS (no seek, §9).
- Sessions:
  - `resources/full_videos/20290928_entreno_vall_dhebron.mp4` (695 s,
    calibrated, never run);
  - `resources/full_videos/Entreno Vall Hebron i Partits - 05 05 2025.mp4`
    (55 min, includes matches; needs the one-time 8-click calibration).
- Target: ≥60 more serves with both sides represented. This turns one-session
  tuning into leave-one-session-out validation. It also satisfies the T12
  "≥3 recording sessions" trigger for serves specifically.
- Worker half: run `make run` with `--serve-events` on both videos.

### SR4: rally-onset serve record, both sides (worker, post-hoc first)
- Pass-2 fusion over existing artifacts, one record per opener episode.
- **Proposal:** opener gate (no emitted contact for 60-240 f), then the first
  ball activity.
- **Side:** a vote over
  - runway occupant (far band) or `is_behind_baseline` (near);
  - ball width trend (far serve grows toward the lens, near serve shrinks away);
  - side of the first post-serve contact (the receiver is on the other side);
  - the structural far arm.
- **Time:** the audio onset if SR2 survives. Otherwise the structural far arm,
  or the near contact/gesture time.
- **Toss check (optional sub-probe):** wrist-above-head on the server's pose in
  ±10 f. Far server bboxes are 90-160 px and pose already runs there. Its job is
  to separate the 2 known pre-serve-handling FPs (f5130, f2414), the one gap no
  dead-time test closes.
- Output `output/serve_records.json`. Dev, then held-out P9-P33, then SR3
  sessions. Acceptance is §4.
- **Promotion** (only after acceptance on ≥2 sessions): *insert* a serve action
  into `actions_pass2` and the DB. Never relabel the reception. Demote production
  `serve` labels the record contradicts (they carry the 12 FPs).

### SR5: rules-constrained serve-sequence decoding (worker, post-hoc)
- A DP/HMM over the points of a match:
  - **state:** serving squad, server within squad, side layout;
  - **transitions:** winner serves next, the server alternates when a squad wins
    the serve back, side switches at 7-point multiples (S3);
  - **emissions:** SR4 side evidence, the 21.3 winner evidence, and the player
    standing at the serve position.
- Output: serving squad + server per point, consistent with the previous
  point's winner.
- Measure serve-squad accuracy and winner accuracy, which is 18/33 today
  (`scripts/resolve_point_winners.py`). Expected payoff: the winner layer and
  the serve record correct each other.
- Ground-truth inputs (dictated winners) stay validate-only (S4 leakage rule).

### SR6: serve outcome = ace / service fault (worker; unblocks G1 open point 13)
- **Ace:** a serve record, no receiving-side contact before point end, and the
  serving squad wins (from SR5).
- **Service fault:** no net crossing, or the next serve comes from the other
  squad with no receiving contact.
- Validate against the owner contact GT: an ace point = GT contacts are the
  serve only and the server's squad won. Then wire into the fantasy module.

### SR7: learned serve detector (DEFERRED; trigger = serve GT from ≥3 sessions and ≥100 serves)
- A small temporal classifier on windows around SR4 candidates. Features: the
  server-crop pose sequence, raw ball detections within reach, and the audio
  onset envelope.
- Validated leave-one-SESSION-out. It replaces the SR4 hand rules only if it
  beats them on the held-out session.

## 6. Order and decision points

```
SR0 ──> SR1 ─┐
     └> SR2 ─┼─> SR4 ──> SR5 ──> SR6
SR3 (owner, async, start now) ─┘            SR7 when its trigger fires
```

- **D1: APPROVED.** Run SR2. Production adoption still depends on its kills.
- **D2: APPROVED, scoped down.** Label vall_dhebron only. The 05-05-2025 video
  is dropped because its conditions are too poor.
- **D3 (owner, now):** ratify the per-point serve record (post-hoc) as THE serve
  product. Pursuing a far serve in the causal `ActionClassifier` stops. The
  production `serve` label becomes a secondary signal.

One mechanism per session. Byte-identical A/B on entreno for anything touching
`src/`. Each SR's kill criteria are fixed above, before any data is seen.
