# Post-run reconstruction (`src/postrun`, session #87)

Makes the match make sense after the causal pass: points with a start (serve)
and an end (ball death), touches that obey the rules, a score that follows the
serve. Hindsight over the stream only (AGENTS.md §6) — the video is never
decoded again; a full match reconstructs in ~3 s.

```bash
make run-match VIDEO=resources/full_videos/<match>.mp4   # run + diag sidecar + reconstruction
make postrun OUTPUT_DIR=output/<dir>                     # reconstruction only (no decode)
make point-images VIDEO=resources/full_videos/<match>.mp4  # one contact-sheet image per point -> output/<dir>/point_images/
venv/bin/python scripts/score_postrun.py output/<dir>/match_reconstruction.json
venv/bin/python scripts/score_postrun_entreno.py output/postrun   # practice clips
venv/bin/python scripts/sweep_postrun.py output/postrun/20260920_match
```

Input: the `--diag-dump` JSONL of a normal run (schema 4: ball bbox/velocity
and the per-frame identity labels were added to the dump; nothing else in
`src/` changed) + the court calibration. Output: `match_reconstruction.json`
and a play-by-play `match_reconstruction.txt`.

## Units

Every constant is metres, seconds or a likelihood cost — none is a pixel.
The calibration gives the ruler: a ball on a baseline measures
`D * baseline_px / 8` px and `1/width` is linear in depth, so the ball's width
is its position along the court (`court_y`: 0 far baseline, 8 net, 16 near
baseline) and the ground row at that depth gives its height. Independent
check: the two net-top clicks, never used to build the model, land at
**2.43 m** on the beach and **2.42 m** at the practice venue.

## Stages

1. **Ball timeline** (`ball_flights.py`). Events = the trajectory vertices
   perception found (accepted contacts AND the ones its reach gate refused)
   plus track births/deaths. A tracking gap is the same flight (the ball
   reappears where gravity puts it), a hidden touch (short gap, different
   trajectory → a *gap vertex*), or a break. Each flight between two events
   gets one robust line through `1/width` (ballistic ⇒ constant axial speed),
   which reads the depth at both ends far better than single frames.
2. **Points** (`rallies.py`). A serve is a launch beside a baseline that
   clears net height and reaches the other half (or dies at the net). The far
   serve has no vertex of its own — its launch is the BIRTH of the track. A
   point ends at the first of: ball on the sand, ball dropping at the net, no
   touch for longer than a ball stays in the air. Dead-time vertices (bounce
   routines, pick-ups, balls rolled back) never start or extend a point.
   A rally whose serve was never seen is still found (≥4 touches, ≥2 net
   crossings) with an inferred serve.
3. **Who is who** (`identity.py`, #105; detail and numbers below). Before
   anything is credited: which squad is near is read once per rally, then
   which tracked body is which of the four players inside the rally. The
   players of each rally window get their `label` / `squad` / `slot` and their
   half rewritten from that read. A dump without the identity observations
   (`id_sims`, schema 5) keeps the labels the causal pass stamped.
4. **Touches** (`touches.py`). One shortest path per rally over states
   (half, touch number 1–3, which of that half's two players). Hard rules:
   the reception belongs to the receivers, at most three touches per
   possession, players alternate. Evidence: ball depth vs the half, ball
   depth vs where THAT player stands (the read that still works at the net),
   ball-to-body distance in body heights, time between touches. Vertices that
   fit nowhere are skipped; touches the stream never saw are allowed as
   hidden touches so the seen ones keep the right number.
5. **Labels**. Same half follows → dig (touch 1) / set. Ends the possession →
   overpass on touch 1; on touch 2–3 a spike when hit at attack height
   (net − 0.28 m), else an overpass.
6. **Match** (`match.py`). Winner = whoever serves the next point (rally
   scoring); the ball's death (net / own half / landed in / out) is the
   cross-check and the only read for the last point, where the score closing
   the set decides. Squads come from the identity read, so a side switch is
   the rally where the near half changes squad. Service order (teammates
   alternate on each side-out) names the server of every point. A serve the
   receivers touch once, with no second touch, and lose is an ace -- from
   either end (owner rule 2026-10-10; a far serve is read from the track's
   birth and counts all the same).

7. **Attack type** (`attack_shape.py`, #97). Every observed spike / overpass
   gets `spike_type` (`hard` / `touch`) from the flight that follows it, in
   metres: the hit is the largest image-velocity step near the vertex (the
   classifier dates a vertex 1–3 frames early); the flight up to the next
   touch or the sand is ballistic, so its heights give the VERTICAL launch
   speed; the HORIZONTAL speed is read twice — the width trend over the
   flight, and attack position → next-touch position. `touch` = launch
   elevation ≥ 25° (a lob) or leaving under 5 m/s (a drop); `hard` = the
   rest; no type when the two speed reads fall on different sides. The
   numbers behind it are kept in `launch` (speed, rise, both elevations).

## Precision first (owner rule)

A missing action is fine, an invented one is not:

* a touch is credited to a player only when that player is within 0.6 body
  heights of the ball -- or when the rules pin it down: two players per half
  who never touch twice in a row, so one reach-credited touch of a possession
  names every other SEEN touch of it (dig P2A, then two touches out of
  anyone's reach on the same half = set P1A, attack P2A). Needs an anchor, a
  half with exactly two known players and credits that already agree with
  alternation; marked `player_source: "alternation"` (`(by alternation)` in
  the report). Otherwise it stays in the point, uncredited;
* hidden touches (`evidence: "structure"`) are never credited and never
  decide a kill/ace/error;
* an ambiguous possession-ending touch is an overpass, never a spike;
* a kill needs the ball seen coming down;
* an attack is typed hard / touch only when both horizontal-speed reads
  agree; a flight under 5 tracked frames reads nothing;
* a touch after which the next serve contradicts the ball's death is dropped.

## Measured (2026-10-05)

20260920 match, owner GT (33 points, 211 contacts, ±15 f):

| | post-run | causal stream |
|---|---|---|
| points | 33/33, 0 false, 0 missed | 31 (count only) |
| serve: half / squad / frame | 33/33 / 33/33 / 32/33 | near 8/16, far 0/17 |
| winner, final score | 33/33, A 21 – B 12 (exact) | 18/33 (pass-2 layer) |
| side switches | after 7, 14, 21, 28 | — |
| touch precision / recall | 0.976 / 0.933 | 0.711 / 0.815 |
| action / half / squad | 0.982 / 1.000 / 1.000 | 0.559 / 0.759 / — |
| rule breaks | 0 | 23 same-player, 45 fourth-touch, 10 reception |

The 4 unmatched post-run touches are real contacts whose GT frame is 16–23 f
away (owner frames are coarse). The serve-frame miss is P31, whose GT serve
(f24543) sits 128 f before its own reception — a typo for ~f24630.

Second, independent run of the same match (Oct 2 dump, no identity labels):
33/33 points, serve half 33/33, action 0.982, half 1.000.

Practice clips e1–e7 (other venue, tripod 2.3× higher; no constant fitted on
them — but five mechanism bugs they exposed were fixed, so they are no longer
blind): serves 5/5, touch precision 52/53, recall 52/58, action 52/52. e1/e4
have no serve in the clip and are found through the serve-less path.

Sensitivity (`sweep_postrun.py`, 78 one-at-a-time moves of every constant by
roughly ×0.6…×1.6): every row keeps 33/33 points, 0 false, winners 33/33;
worst precision 0.965, recall 0.893, action 0.958, half 0.994.

## Attack type, measured (2026-10-08, #97)

`scripts/score_spike_type.py --clips output/postrun --rows`, owner-typed
spikes, GT spike → post-run attack within ±15 f:

| | post-run `attack_shape` | causal `SpikeAnalyzer` (px ascent) |
|---|---|---|
| match: typed / right (32 spikes) | 29 / 26 (0.906 / 0.897) | 16 / 10 (0.50 / 0.625) |
| practice: typed / right (8 spikes) | 6 / 6 | 6 / 6 |
| all 63 match attacks typed | 58 | 25 |

The V1 bars (accuracy 0.85, coverage 0.80, fixed in #92) are met, but the
two constants were chosen ON these labels, so the match score is in-sample.
Sensitivity: any split in 24–26° scores the same; 18–32° gives 0.82–0.90;
the speed floor 3–6 m/s changes nothing; without the hit-frame search 23/29.
All 22 typed match overpasses read `touch`. Wrong: P10 f6320 (touch read
hard, 22.8°), P30 f23341 and P33 f25928 (hard read touch, 27.5° / 30.6°);
untyped: P19 f13397, P22 f16037 (reads disagree), P18 f12295 (no post-run
attack), e6 f310 (joust, 2 flight frames), e7 f300 (no post-run attack).
Everything else is unchanged by #97 (the reconstruction differs only by the
new keys). The sweep is now 88 moves; no row loses a point or a winner.

Why the pixel rule fails here: on a long-axis camera a ball above the lens
climbs in the picture just by flying toward it, and 57 px was fitted at the
practice venue (2.3× the beach scale). What limits the new read: depth speed
(ball width) is the weak axis — the width trend over-reads a ball flying
away by up to 30 % (seen through the net its box shrinks) — and the two
classes overlap for real between ~19° and ~31° (a width-free fit that uses
gravity as the ruler keeps the same attacks there). Amateur "hard" spikes
are flat and fast (6–15 m/s, −4…+24°), not downward; telling a swing from a
poke inside the overlap needs the arm (pose), not the ball.

## Court positions, measured (2026-10-09, #101)

`src/postrun/positions.py` — OUTPUT ONLY. `court_x_m` / `court_y_m` /
`court_err_m` of a touch and `court_xy_m` of a ground end (recon schema 4)
are no longer the decision read. The decision layers keep `BallEvent.court_y`
and `DEPTH_SPLIT_BIAS_M`; nothing below feeds a point, a touch, a label or a
winner.

Why (#100): the web drew the owner's kill at 2:49 (f4886) 2.7 m off the net;
the frames show the takeoff 0.8–1.3 m from it. Same players on both halves,
39 spikes: 2.70 m off the net from the near half, −0.30 m from the far half
(11 of 17 starting across the net).

What a published position does differently:

1. **The net is where it was clicked.** The corner midline is 0.05 m (left
   sideline) to 1.3 m (right) off the calibration's net-ground clicks, which
   agree with the post bases in the frame; a ball at that line is 23.7 px
   wide, the corner model says 22.8. Depth is read against three anchors (far
   baseline, net, near baseline) and the ground through two homographies that
   share the net line. Without clicks, or with a click that is not near
   mid-court, the frame is the corner model exactly.
2. **The ball's box is wider than the ball, by a number of pixels the video
   has to show.** The same players play both halves, so a kind of touch sits
   at one distance from the net whichever half it is played from. One width
   offset must close that gap for every kind at once:

   | kind | touches near / far | gap before (m) | after |
   |---|---|---|---|
   | dig | 28 / 31 | 2.05 | −0.16 |
   | set | 24 / 25 | 2.21 | +0.14 |
   | spike | 22 / 17 | 2.06 | 0.00 |
   | overpass | 12 / 11 | 2.15 | +0.09 |

   20260920: 1.74 px. Refused (positions then use the clicks only, and say
   so in `positions.width_bias_reason`) without a side switch, with fewer than
   two kinds of ≥5 touches per half, outside 12 % of the ball's width at the
   net, or when a kind stays more than 0.6 m apart.

Why pixels and not a shift in metres: 16 near serves put the ball −0.24 m from
their server's feet (the toss is just in front), so the read is unbiased at
the near baseline; a flat +1 m would show +0.7 m there. A pixel offset is
0.25 m at the near baseline, ~1 m at the net, more beyond it.

Result, spikes (distance from the net, near | far half):

| | before | after |
|---|---|---|
| all | 2.70 \| −0.30 | 1.40 \| 1.40 |
| P1A (6 \| 1) | 2.85 \| 0.60 | 1.55 \| 2.30 |
| P2A (4 \| 9) | 2.65 \| −0.40 | 1.35 \| 1.20 |
| P1B (5 \| 2) | 2.70 \| 0.00 | 1.40 \| 1.70 |
| P2B (7 \| 5) | 2.60 \| −0.30 | 1.30 \| 1.40 |

The 2:49 kill reads 1.4 m; 1 of 39 spikes reads across the net and is held at
it (a touch is played on its own half). All 170 positions move 0.5–2.4 m away
from the lens. Ground ends move with the net line only (up to 1.2 m beside
the right sideline).

Neutrality: everything but the position keys is identical on the match and on
e1–e7 (JSON diff, play-by-play `cmp`); `score_postrun.py` prints the same
output; practice 5/5 serves, P 52/53; sweep 88 rows, none loses a point or a
winner; hard / touch 26/29.

Tried and dropped: reading the depth in a short window at the hit (aligned on
the trajectory kink; arriving flight, leaving flight, or only the flight that
stays on the touch's half). None is tighter than the whole-flight fits (spike
IQR ~0.9 m either way), so those stay.

What it rests on, and what stays open:

* **The two halves are played alike.** The players' feet (ground plane,
  independent of the ball's width) show the same near/far gap at digs and
  sets (2.6–2.7 m), which is either the person box reading toward the lens
  too, or play that really differs by end (wind). The symmetry read cannot
  tell; a real part would be removed as if it were bias. Direct checks at the
  net disagree: a ball sliding down the near face of the net measures 25 px
  (the offset is there), two serves into the net measure 23–24 px (it is not).
* **In-sample:** one match. A second match with switches is the test.
* **No switch, no offset:** the practice clips keep the clicked net only; a far
  touch there still reads toward the lens and is held at the net if it crosses.
* **One position is ±0.6–0.8 m along the court** from the 1.25 m beach tripod
  (1 px of ball width ≈ 0.6 m at the net; 9 px of sand per metre). A takeoff
  read from the feet needs a higher camera: the practice venue's ~3 m gives
  20–24 px per metre.

## Who is who, measured (2026-10-10, #105)

**Why it exists.** The causal resolver (`TeamIdentityResolver`) decides which
squad is near frame by frame. On the 20261010 match (vall d'Hebron) it read
none of the first two side switches and then flipped ten times, so the run
came out A 11 – B 20 for a set squad A won. Two causes, both measured on the
probe's feature dump:

* **the players walk around the net one at a time** (first switch: f7450–7800,
  about 12 s). The resolver follows the level of its evidence with a ~4 s time
  constant, in dead time too: by the time all four had crossed, its "squad 1
  is near" level had slid from +0.39 / +0.52 to about 0 and the spread had
  grown fourfold. Nothing was left to detect;
* **the unseen orientation is assumed to mirror the enrolled one** (−0.39 /
  −0.52). It does not: the anchors were enrolled in one view each, so across
  the net the evidence keeps a view bias as large as the signal. Per rally the
  two orientations read +0.31…+0.38 and −0.13…+0.08 on that match (one woman
  of squad B, seen from behind, looks more like squad A's woman than like her
  own far-view anchor).

**What is read instead** (hindsight, no assumption about the unseen level):

1. *Evidence per rally.* Every clean, real body whose feet are more than 1 m
   from the net line gives `x` = best squad-1 minus best squad-2 anchor
   similarity (sign flipped on the far half); a rally's evidence is the mean
   of its two halves' means. Bodies inside that metre are left out: a far
   blocker stands on the net line in the picture (20261010 P20 / P30 / P31:
   the tracker reads him near for the whole rally).
2. *Two levels from the match.* The best two-level split of the rallies'
   evidence is accepted as two orientations only if the levels are ≥ 4 spreads
   apart and the lower one is at most half the upper one; otherwise nobody
   switched. The first read rally is the enrolled orientation by construction
   (if it sits at the lower level the read is refused and the causal labels
   stay). A two-state shortest path over the rallies then decides each one: a
   switch costs 4 nats and one rally weighs at most 6, so one odd rally in the
   middle of a block is not two switches, and a last block of one point is
   still read.
3. *Players inside the rally.* One shortest path over the frames: a state is
   which player each of the (up to four) track ids is, an id changes player
   only when the evidence pays for it (0.15 similarity for 1 s). Per body and
   frame the evidence is its similarity to that player's anchors minus the
   value half way between the two teammates of that half in this orientation
   (read from the match: a view shifts both teammates alike, so a body seen
   without its teammate is still read unbiased), less 0.5 when its feet are
   clear of the net on the other squad's half.
4. *Write-back.* Label, squad, slot and half of every tracked body in the
   rally window. The half is the SQUAD's half, so the roster of the touch
   solver holds the two teammates whatever their feet say. A half whose two
   players are told apart by less than 0.02 similarity gets no labels in that
   rally (its squad is still known; its touches are credited to nobody).

| | 20261010 (vall d'Hebron) | 20260920 (beach) |
|---|---|---|
| evidence levels (squad 1 near / squad 2 near / spread) | +0.347 / −0.038 / 0.044 | +0.146 / −0.083 / 0.023 |
| rallies oriented right | 31/31 (agent's frame read) | 33/33 (owner GT) |
| side switches | after 7, 16, 22, 29 (see below) | after 7, 14, 21, 28 |
| score as reconstructed | A 21 – B 10, set complete (causal labels: A 11 – B 20) | A 21 – B 12 (unchanged) |
| slot margin, weakest half | 0.040 (grey shirt vs black top, same view) | 0.31 |
| labels on the right person | 93/93 sampled frames, 3 per rally (agent's eyes) | players = owner CSV on 207/208 touches |
| id changes inside rallies | 8, 7 with the box jumping to another body | 36, 28 with the box jumping (the rest on coasting boxes) |

20260920 is otherwise unchanged against the record above (points, serves,
winners, score, touch precision / recall, action, half, squad, 0 rule breaks).
The one touch that moved (P19 f13624, P1A → P2A; the owner's P1A is right):
both near players are in one box, the man in front, the woman who bumps the
ball hidden behind him. The read names the box P2A, which is who it shows; the
causal label was a stale P1A that happened to be the toucher.

Feet against the assigned half: 42 of 28 633 body-frames on 20261010 and 180
of 30 475 on 20260920 read the other half by more than a metre (jumps project
the feet deep, dives and merged boxes read near), in runs of up to 18 frames.
That is why the feet are a cost and the squad decides.

Sensitivity: the eleven constants moved ×0.5…×2 one at a time keep 31/31
orientations on 20261010 and every score of 20260920. Labels change in three
rows on 20261010: side penalty 0.25 (2.4 % of body-frames; the look-alike
above wins — it holds from 0.35) and swap cost ×2 (0.4 %: one id swap followed
late).

**Not solved by this:** the 20261010 blocks are 7 / 9 / 6 / 7 points, not
7 / 7 / 7 / 7 — the orientation is right, the POINTS are not (open point 32h:
a ball lobbed back in dead time counted as a point, a near serve that left the
top of the frame lost). `switch_blocks_ok: false` says so. The live overlay
(`make run-live`) still shows the causal labels.

## Known limits

* **Players** are scored against the owner-ratified attribution of the
  20260920 match (#88 CSV: 207/208 with the hindsight read, 208/208 with that
  run's causal labels) and nothing else: one venue pair, two kits each. Four
  players dressed alike, or teammates in the same kit, give a small slot
  margin and no labels (precision first), never a guess -- untested on
  footage. Owner contact sheets stay the gate for a new match.
* **Line calls are weak** (blurred box through a 4-click homography): the
  ball-death read exists on 17 of 33 points; the 7 that need no line call
  (into the net, died on the hitter's half) are all right, but 3 of the 10
  in/out reads contradict the next serve and are overridden. The last point
  has only this read plus the score closing the set.
* Constants were set while looking at the whole match (not P1–P8 only); the
  out-of-sample evidence is the practice clips and the sweep. The
  `vall_dhebron` lock is untouched.
* 12 GT touches go unmatched: 4 are the coarse-frame pairs above, 5 are
  placed as hidden touches (uncredited), 3 are absent. 1 observed touch is
  credited to nobody (10 more are credited by alternation). Blocks are not a label. Soft "rainbow" attacks
  below ~2.15 m read as overpasses (2 on the match).
* Needs the `--diag-dump` sidecar (49 MB per match, held in memory until the
  run ends).
