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
   crossings) with an inferred serve. Two reads added on the second match
   (#106, numbers below): a serve-shaped launch at receivers who are NOT
   standing side by side and do not play the ball is the ball going back
   between two points (`checks.launches_refused`, "Not a serve" in the
   report); a landing is read where the ball stops falling, not at the first
   frame its width fits the sand. And since #109 (third match, numbers
   below) a serve the ball alone leaves open -- its flight out of the
   picture, its toss read inside the court or taken for a pass, a ball the
   tape stops -- is taken when the court was STILL before it: the owner's
   cue that at a serve everybody but the server stands (`court_sway`,
   `serve.confirmed_by: "still_court"`).
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
   overpass on touch 1; on touch 2–3 a spike when the ball was hit with the
   arm up, else an overpass. "Arm up" = contact height ≥ 1.23 × the toucher's
   own standing height (#106): the contact is read where the ball leaves the
   arc it arrived on (`BallTimeline.arc_exit`), the standing height is the
   75th percentile of the player's box heights, one number per identified
   player for the whole video. Net − 0.28 m is only the fallback when no
   player can be measured.
6. **Match** (`match.py`). Winner = whoever serves the next point (rally
   scoring); the ball's death (net / own half / landed in / out) is the
   cross-check and the only read for the last point, where the score closing
   the set decides. Squads come from the identity read, so a side switch is
   the rally where the near half changes squad. Service order (teammates
   alternate on each side-out) names the server of every point. A serve the
   receivers touch once, with no second touch, and lose is an ace -- from
   either end (owner rule 2026-10-10; a far serve is read from the track's
   birth and counts all the same). A spike that is dug and never set is a
   kill (owner rule 2026-10-11): a second touch after which the ball never
   climbs back to net height set nothing up, and is nobody's error.

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
* a serve the ball leaves open needs the court still before it; players
  moving never refuse a serve the ball shows;
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
worst precision 0.965, recall 0.893, action 0.958, half 0.994. (#106: 130
moves, same points / winners on every row, action 0.988 shipped and 0.970 at
worst.)

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

**Not solved by this:** the 20261010 blocks were 7 / 9 / 6 / 7 points, not
7 / 7 / 7 / 7 — the orientation is right, the POINTS were not (a ball lobbed
back in dead time counted as a point, a near serve that left the top of the
frame lost; both fixed since, #105b / #106: the blocks read 7 / 8 / 7 / 7,
which is what was played — the players switched one point late). The live
overlay (`make run-live`) still shows the causal labels.

## Second match, measured (2026-10-10, #106)

Three reads the 20261010 match (vall d'Hebron, tripod ~3 m, a pair of short
players) showed wrong; each is a mechanism, none a constant fitted to it.

**1. A landing is where the ball stops falling.** A ground end was read at
the first frame the width test (`grounded`) fired. A falling ball lines up
with sand metres behind where it will land, and for a frame or two its width
fits that sand too: the last point's cut shot read 2 m BEHIND the far baseline
(out, point B) when it lands a metre inside the side line (f29205; the owner:
in, point A). `_landing_frame` walks from that first frame while the ball
still comes down faster than 1.5 m/s in the picture. 20261010: 6 landings
move 4–7 m, in / out reads 5 of 5 agree with the next serve (was 3 of 4), the
last point is A's, and P11's last attack is no longer dropped as "died on its
own half" (spike P2A, kill — the owner's read). 20260920: one landing moves
(P6), winners and line calls as before (7 of 10: those three are not this).

**2. A serve needs receivers.** The ball sent back to the next server at
06:52 was thrown from BEHIND the far baseline (fetched there), peaked at
4.8 m and flew 13 m at 7.6 m/s: no ball read separates it from a serve. The
bodies do: a team waiting for a serve stands side by side, a team about to
serve has one player walking to the line. Depth between the two receivers at
every serve with both read (ground read of the feet within 0.5 m; the far
half of the low beach camera is not, and nothing is refused there): ≤ 0.84 m
at 51 of 52 serves (two matches + clips), 1.37 m in one drill that was played
on; 2.2 m at the throw. Refused = stagger > 1.5 m AND fewer than two touches
follow (a rally is a point wherever the receivers stood). It is listed in
`checks.launches_refused` and in the report. 20261010: 31 points, A 22 – B 9,
blocks 7 / 8 / 7 / 7, P13 goes to B — the owner's sequence. Limit: a ball
sent back to a pair that happens to stand level still passes.

**3. An attack is a ball hit above the player's own head.** The tape rule
(contact ≥ net − 0.28 m) failed twice over. The contact height was read at
the classifier's vertex, which is dated up to three frames early while a set
drops 0.2 m a frame: +0.3…+0.5 m on some touches and not on others. And two
players attack at 1.85–2.05 m, under any tape: their attacks read "spike"
only when the vertex happened to be early (6 of 11). Now the contact is the
sample where the ball leaves its incoming arc, and the ruler is the toucher's
standing height. The 91 possession-ending second / third touches with a label
(20260920 owner GT, 20261010 owner feedback):

| contact / standing height | passes | attacks |
|---|---|---|
| ≤ 1.19 | 20 | 0 |
| 1.27 – 1.29 | 2 (arms above the head: 20260920 f3913, f10789) | 4 |
| ≥ 1.31 | 0 | 65 |

20261010: the five attacks read as overpass are spikes (four named by the
owner, f23222 by the frames). 20260920: action 162/165 → 163/165 (two soft
attacks and one bump read at 2.33 m fixed, the two passes above lost).
Practice clips 52/52 as before. Standing heights read ~10 % under the real
ones (crouch, sand) for everybody, which is why the split is a ratio measured
on the same boxes and not anatomy.

## Third match, measured (2026-10-11, #109)

The owner wrote the running score of `20261010_1100` with the time of every
point: 35 points, A 13 – B 22, switches after 8 / 15 / 22 / 29
(`ground_truth/20261010_1100_vall_dhebron_points.json`, scored by
`scripts/score_postrun_points.py`). The run of #108 had 31 points and A 14 –
B 17. Four points were lost and one serve was read from the wrong half; each
was a serve the ball alone could not settle.

| owner time | frame | what it is | why it was dropped |
|---|---|---|---|
| 00.41 | f1060 | near serve | toss and hit seen, then the ball leaves the top of the picture and is seen again 5 frames before the reception: no flight long enough to carry a speed |
| 11.01 | f16535 | far jump serve | the toss is tracked in two pieces; the join reads as a touch 5 m away (16 px of ball width), so the serve is "fed by a pass" |
| 16.03 | f24669 | near serve into the net | the ball lies at the net for 18 tracked frames: one line through flight AND rest reads the launch 2.3 m inside the court at 3.9 m/s |
| 19.58 | f31784 | far serve, net cord, drops on the receivers' sand | 4.8 m/s (under the 5.5 m/s a serve that clears the net needs) and it ends at a vertex 2.5 m up, not on the sand |
| 19.31 | f30939 | far serve (found, wrong half) | toss tracked, read 1 m INSIDE the court (the rule wanted it behind the baseline), track dead at the hit; the serve-less path then took the server's bounce for a reception and invented a near serve |

**The owner's cue: a still court.** "At most serves the people on the court
are completely still, aside from the one serving." Read as `court_sway`: over
the 2 s before a launch, how far the feet of each tracked body strayed from
their own median spot (p90, in that body's own heights); the court's value is
the THIRD-stillest body's, so a server running up to a jump serve does not
count. On 20260920 and the three 20261010 videos:

| | n read | ≤ 0.10 | ≤ 0.15 | median |
|---|---|---|---|---|
| serves | 138 | 114 (83 %) | 123 (89 %) | 0.03 |
| attacks (spike / overpass) | 211 | 1 | 3 | 0.41 |

(The one attack under 0.10 is a serve sent straight back by its receiver,
1.3 s after the serve.) So a still court is strong evidence FOR a serve and
its absence is weak evidence against one: one serve in six is read with
somebody walking or a box flickering. It is used one way only -- to let
through a launch the ball leaves open -- and never to refuse a serve:

* **serve past the frame** (`_serve_past_the_frame`): the hit may be a seen
  vertex before the track dies; a far toss may read up to `FAR_SERVE_MAX_Y`
  (as a far launch does); a ball seen again too briefly to carry a speed
  counts when it is seen INSIDE the court, as it is received, after a toss
  placed without doubt. Each of these needs the still court. (Tried first
  without the "received" condition: a far ball glimpsed for half a second,
  then the near server's toss, read as a far serve on 20261010_1000 and
  swallowed the real one.)
* **own toss** (`_own_toss`): a launch "fed by a pass" is a serve when the
  feeding flight stayed on the server's half and the court was still. A
  rally's first attack is fed on its own half too, but never with three
  bodies standing for two seconds.
* **net cord** (`_dropped_by_the_tape`): a flight toward the net that ends at
  a vertex at or under the tape, the ball then falling to the sand, is a
  serve into the net on a still court. The rally ends at the tape (`net`).
* **airborne part** (`_airborne`, no court needed): a launch flight with the
  ball lying at its end is fitted up to the landing only.

Six serves are confirmed that way: four on 20261010_1100 and two on _1200
(f18029, a near serve out of the picture; f43822, a near serve the run had
replaced by an invented far one -- both checked on frames).

**What else the review changed.**

* *A ball thrown back is not the rally's landing.* A serve-shaped launch
  within 5 s of a rally whose track was lost used to be merged as its tail.
  On 1100 P1 that was team B sending the ball to A's server 4.2 s later: its
  landing became "the spike died on its own half" and the spike was dropped
  when the next serve said otherwise. Now a launch that comes after the
  rally's ball had to be down (> 3.2 s) and that nobody plays (< 2 touches)
  is skipped. Two such launches on four matches, both dead time; the one
  merge that stays is 1.7 s after the last sighting with three touches.
* *A dig at sand level.* A flight's "resting on the sand" samples counted
  the frames a ball spends low as it LEAVES a dig taken off the sand, so the
  rally ended at its reception (1100 owner P30: serve, dig, set, spike, dig
  read as an ace). `Flight.landed_frames` counts them only from the moment
  the ball has climbed above 1.3 m (what sand cannot do); the landing frame
  is searched from there too. And a flight that stays under 1.3 m is not a
  bounce when the ball is followed all the way to the next vertex and played
  on from there (`_seen_to_next`; 1200 P21, a dig popped knee-high to the
  partner).
* *The half of a last touch under the tape.* The ball crosses the net above
  the tape. When it is tracked from the rally's last vertex down to the sand
  without getting within 0.5 m of the tape, that touch was made on the half
  it came down on (`UNDER_TAPE_COST`; 1100 owner P2: a second touch 0.9 m up
  at the net read as the other team's overpass and kill). Only the end of a
  rally: the same rule between two touches changed nothing on four matches
  and was not kept.
* *Dug but never set is a kill* (owner rule, `_dug_never_set`). The 171 sets
  that are followed by a third touch (four matches) send the ball to 3.7 m
  or more at the 5th percentile; the second touches that end a rally with
  the ball not going up peak at 1.3–1.4 m. The split is the net: under it
  nothing was set up. Then the spike before the dig is a kill (a serve: an
  ace) and the touch is nobody's error. After an OVERPASS it stays the
  setter's handling error -- 20260920 P6, "fails hand set", the owner's own
  label.
* *The clock.* 1100 runs at 25 fps for 14 min and at 30 after; frame /
  average fps printed times up to 50 s off the video player. With
  `frame_times.json` (`scripts/write_frame_times.py`, written by `make
  run-match`: the packets' timestamps, no decode, refused unless there is
  exactly one per frame) the report and the point images print the player's
  clock; the run's 35 serve times are within 1 s of the owner's. Decisions
  still run on the average rate: speeds on this video are 6 % high before
  minute 14 and 11 % low after (the net-cord serve is 5.4 m/s, not 4.8).
* *Longest rally* (owner-asked): every point carries `rally` (touches, net
  crossings, seconds), `checks.longest_rally` names the longest; one line in
  the report. 1100: owner P14, 23 touches, 9 crossings, 32 s.

**Result.** 20261010_1100 against the owner's table: 35 / 35 points, 0 false,
serving team 35 / 35, winners 34 / 35, switches 8 / 15 / 22 / 29 exact. The
wrong winner is the LAST point (read A from the ball's death, the table says
B): an over-set and a joust at the net, where the touch 2.1 m up is read as
B's third instead of A's first. 20260920 and the seven practice clips
reconstruct exactly as before (33 / 33, winners 33 / 33, A 21 – B 12, P 0.976
/ R 0.933, action 0.988, who 208 / 208; clips 5 / 5, 52 / 53, 52 / 52).
20261010_1000 keeps its 31 points and score; one rally end moves 53 frames
(P3). 20261010_1200 changes: 41 points (40), blocks 8 / 7 / 7 / 7 / 7 (the
third was 6), A 21 – B 20 (was A 21 – B 19 and "complete"; the last point is
A's by the owner's word, see below) -- no owner table for that video.

Sweep, one constant at a time: 20260920 (156 moves) loses no point and no
winner on any row. 20261010_1100 (points and winners only, 122 moves) is
IN-SAMPLE and shows where the recovered points sit: 115 moves change
nothing; 00.41 is lost with the still-court bar at 0.05 (it reads 0.07) or
with gaps up to 1.2 s taken for hidden touches, 11.01 with a 3 s window
(0.19), 19.58 with 0.1 m of tape slack; a 1.9 m serve peak or a 3 s dead time
each add a false point.

**A ball that comes down at the net** (same day, the owner on the last
point of 20261010_1200: "the last spike spikes into the net and falls to the
ground", A's point; the run had left it undecided at A 20 – B 20). A landing
within 1.5 m of the net has no half, and a hit INTO the net has no vertex at
the net (the net stops the ball at the hit, there is no flight to it), so
neither the landing read nor the net-fault read fires. The ball was followed
from the spike to the sand, though, and its centre never got above the tape:
it did not cross (`fell_at_net`, `_never_over_the_tape`). Where the next
serve can check that read, on four matches: right on 6 of 7 (20260920 P6 and
P30, 20261010_1000 P14 and P27, _1100 P19, _1200 P35; wrong on _1200 P11, an
overpass read 0.24 m under the tape that went over). A margin does not
separate that one (the six read 0.05–1.1 m under), so it is a WEAK read like
a line call: the next serve overrules it and nothing is dropped for it; it
decides only a point no serve follows. 1200: 41 points, A 21 – B 20.

Not fixed, from the same review: blocks (owner P5 / P6: a block read as the
attacker's spike or error, a joust), an attack into the net replayed by the
same player (P31, read as the other team's overpass), a "dig" after two
kills that is the ball on the sand (P20 / P21, never credited), the unseen
attack behind a block (P29: the owner says it is the setter's partner's; the
layer still credits no touch it did not see -- 2 such attacks on four
matches, both real).

## Fourth video, measured (2026-10-12, #111: 20261010_1230)

The owner's only number was the final: A 21 – B 19 = 40 points. The first run
read 38 (A 21 – B 17, switches after 7 / 14 / 21 / 28 / **34**). A scan of every
ball contact outside the points plus contact sheets (sequential decode) found
four clusters: two of dead-time handling (a ball fed over the net to a diving
player) and two rallies, both told by the owner afterwards:

* **17:32 (f31700), a net-cord ace.** B serves, the ball touches the tape and
  drops, A reaches it and the dig is hidden by the digger. No flight before the
  tape: the track is BORN at y 8.0 m (the far-serve gate stops at 7.5 m), 2.1 m
  up, 2.5 m/s, on a court that had stood still (sway 0.056). New last-resort
  read `_serve_at_the_tape`: a birth within `NET_ZONE_M` of the net, ≥
  `LIVE_MIN_PEAK_M` up, moving away from the net onto the other half and
  ending on the sand, STILL COURT only; it runs after the flight test, so a
  serve the flight already finds keeps its frame (the first version ran before
  and moved two serve frames by 10 f).
* **23:10 (f41879), a far serve read as a pass.** The tracker found the ball
  five frames before the hit; that "feeder" vertex has a one-sample arriving
  flight, and the toss moves 3 m along the axis the far end cannot measure, so
  `_fed_by_pass` called it a pass; the court sway was 0.133 (> 0.10), too much
  for `_own_toss`. A feeder the ball reached in fewer than `MIN_DEPTH_SAMPLES`
  is the ball's first sight, not a touch (the 49 other serve-shaped launches
  `_fed_by_pass` refused on the 12 runs have a feeder with ≥ 7 arriving samples,
  the real attacks among them ≥ 15; the bar is 3).

With the serve back, P37 (the previous point) is A's: its ball-death read
(`fell_at_net`, B's overpass hit the net) was right and the next-serve read was
wrong only because the serve after it was missing. Result: 40 points, switches
7 / 14 / 21 / 28 / 35, A 21 – B 18 and the **last point undecided** (A's spike
dies 0.9 m from the net, inside `LANDING_NET_MARGIN_M`, and with A already on 21
both teams "close" the set; the owner: B's, so 21 – 19). The other eleven runs
(20260920, 1000, 1100, 1200, e1–e7): reconstruction JSON and report
byte-identical; bars as before (33/33, winners 33/33, P 0.976 / R 0.933, action
0.988; 1100 35/35, serving team 35/35, winners 34/35; practice 5/5, 52/53,
52/52); sweep 157 moves, none loses a point or a winner. In-sample for these two
rallies: the test is the next new match.

## Fifth video, measured (2026-10-12, #112: 20261012_1130_masnou)

A beach video the automatic calibration refused (calibration read by hand,
`source: agent-read`); the owner's only number was the final, A 21 – B 15 = 36
points. The first run read 31 (A 19 – B 11), switch blocks 4 / 7 / 6 / 7 / 6:
the shortfalls (3 + 1 + 1) added up to the 5 missing. Causal actions outside
every point + contact sheets (sequential decode) found two rallies, both a far
serve the ball alone leaves open, received by a team that stood waiting:

* **f2175, first seen at the tape and dug.** A birth 1 m past the net, 2.5 m up,
  moving onto the near half, on a still court (sway 0.05), received by a dig.
  `_serve_at_the_tape` (#111) asked the flight to END ON THE SAND; a dug ball
  ends in a touch. It now takes either (`_received`); still court as before.
* **f3425, a lob serve.** A far flight of 41 samples, 4.4 m peak, 8.3 m of
  travel at 4.6 m/s (< `SERVE_MIN_SPEED_MS`, 5.5: "a lob back to the server"),
  court sway 0.13 (not still). Receivers side by side (stagger 0.15 m, the
  formation rule of #108) and play followed. `_lob_to_a_formation`: a slow flight
  that gets over the tape (not at it: the tape stays the still court's), with a
  tight formation read and play after it, is a serve (`confirmed_by:
  formation`). The ball sent back between points lands on a team that is NOT in
  formation (1.9 m on this video, f26020: a far player lobs it to the near team,
  who pick it up — still refused).

First version of the lob rule did not ask for the ball to clear the net and
took the toss of a jump serve (20261010_1100 P19, f16504, a toss that travels
5 m forward on its own half): the net condition is the fix, and 1100 is
byte-identical again. Result: 33 points, A 19 – B 13, switches 6 / 13 / 19 / 26 /
32, the last point undecided. The other twelve runs (20260920, 1000, 1100, 1200,
1230, e1–e7): `match_reconstruction.json` byte-identical; 20260920 bars as before
(33/33, winners 33/33, P 0.976 / R 0.933, action 0.988). In-sample for these two
rallies. **Left (3 of 36):** f14445, a NEAR lob serve (toss at y 15.6, flight
12.4 → 3.4 m at 3.1 m/s, sway 0.017 = a perfectly still court) dropped because
the flight's own depth read starts at 12.4 m, short of `NEAR_SERVE_MIN_Y` (14 m)
— the toss that fed it reads 15.6; and two more not located (the 56 s gap before
P27 and one in the first six points).

## The ball on the sand, from the owner's reviews (2026-10-15, #117)

The review files of the four vall_dhebron videos and masnou show 7 points whose
last touch is an observed first touch nobody was at, after a hit already read
as an ace or a kill; the owner removed 6. The flight after it separates them:
after the two real digs (1100 P3, kept; 20260920 P17, owner GT "completely
occluded, goes wide and ball falls to sand") the ball climbs to 4.0 / 4.5 m;
after the 6 removed it stays at 1.0–1.9 m. `MatchAssembler._drop_ball_on_the_sand`
drops such a touch when the ball never climbs back to the tape (the
`_dug_never_set` test) and flags the point `ball_on_the_sand:<frame>`; the
outcome was decided before and stands. A/B over all 13 runs: exactly the 6
touches go (1100 P20 / P21, 1200 P9 / P26, 1230 P3 / P19), everything else
byte-identical (20260920, 1000, masnou, e1–e7 whole files; elsewhere only the
`positions.kinds` diagnostic, the offset unchanged); 1100 vs the owner's table
unchanged (35/35, winners 34/35, switches 8 / 15 / 22 / 29).

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
  has only this read plus the score closing the set. (#106: a landing is
  now read where the fall stops; the three wrong calls of 20260920 are not
  that bug and stay.)
* Constants were set while looking at the whole match (not P1–P8 only); the
  out-of-sample evidence is the practice clips and the sweep. The
  `vall_dhebron` lock is untouched.
* 12 GT touches go unmatched: 4 are the coarse-frame pairs above, 5 are
  placed as hidden touches (uncredited), 3 are absent. 1 observed touch is
  credited to nobody (10 more are credited by alternation). Blocks are not a label. A pass played with
  the arms above the head reads as an attack (2 on the match, #106); a soft attack on the FIRST touch
  is always an overpass.
* Needs the `--diag-dump` sidecar (49 MB per match, held in memory until the
  run ends).
