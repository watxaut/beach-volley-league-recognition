# Post-run reconstruction (`src/postrun`, session #87)

Makes the match make sense after the causal pass: points with a start (serve)
and an end (ball death), touches that obey the rules, a score that follows the
serve. Hindsight over the stream only (AGENTS.md §6) — the video is never
decoded again; a full match reconstructs in ~3 s.

```bash
make run-match VIDEO=resources/full_videos/<match>.mp4   # run + diag sidecar + reconstruction
make postrun OUTPUT_DIR=output/<dir>                     # reconstruction only (no decode)
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
3. **Touches** (`touches.py`). One shortest path per rally over states
   (half, touch number 1–3, which of that half's two players). Hard rules:
   the reception belongs to the receivers, at most three touches per
   possession, players alternate. Evidence: ball depth vs the half, ball
   depth vs where THAT player stands (the read that still works at the net),
   ball-to-body distance in body heights, time between touches. Vertices that
   fit nowhere are skipped; touches the stream never saw are allowed as
   hidden touches so the seen ones keep the right number.
4. **Labels**. Same half follows → dig (touch 1) / set. Ends the possession →
   overpass on touch 1; on touch 2–3 a spike when hit at attack height
   (net − 0.28 m), else an overpass.
5. **Match** (`match.py`). Winner = whoever serves the next point (rally
   scoring); the ball's death (net / own half / landed in / out) is the
   cross-check and the only read for the last point, where the score closing
   the set decides. Squads come from the identity labels, so a side switch is
   the rally where the near half changes squad. Service order (teammates
   alternate on each side-out) names the server of every point.

## Precision first (owner rule)

A missing action is fine, an invented one is not:

* a touch is credited to a player only when that player is within 0.6 body
  heights of the ball; otherwise it stays in the point, uncredited;
* hidden touches (`evidence: "structure"`) are never credited and never
  decide a kill/ace/error;
* an ambiguous possession-ending touch is an overpass, never a spike;
* a kill needs the ball seen coming down;
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

## Known limits

* **Players are unscored.** The GT has no stable player identity; within-half
  correctness rests on the identity resolver. Indirect evidence: the observed
  servers agree with the service-order rotation on 84 % (A) / 89 % (B) of
  serves. Owner contact sheets are still the gate.
* **Line calls are weak** (blurred box through a 4-click homography): the
  ball-death read exists on 17 of 33 points; the 7 that need no line call
  (into the net, died on the hitter's half) are all right, but 3 of the 10
  in/out reads contradict the next serve and are overridden. The last point
  has only this read plus the score closing the set.
* Constants were set while looking at the whole match (not P1–P8 only); the
  out-of-sample evidence is the practice clips and the sweep. The
  `vall_dhebron` lock is untouched.
* 12 GT touches go unmatched: 4 are the coarse-frame pairs above, 5 are
  placed as hidden touches (uncredited), 3 are absent. 11 observed touches
  are credited to nobody. Blocks are not a label. Soft "rainbow" attacks
  below ~2.15 m read as overpasses (2 on the match).
* Needs the `--diag-dump` sidecar (49 MB per match, held in memory until the
  run ends).
