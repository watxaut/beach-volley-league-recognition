# Automatic court calibration (#110)

The 8-click calibration was the one manual step between a Drive upload and a
draft on the web. `src/detection/court_autocalibration.py` finds the same 8
points from the picture: 4 court corners, the 2 points under the net, the 2 on
the net tape. Rules it must keep: `AGENTS.md` §14. Scorer:
`scripts/score_autocalibration.py`. Tolerance probe:
`scripts/probe_calibration_sensitivity.py`.

Status: **built, in `propose` mode.** The inbox looks for the court and leaves
a proposal; the owner takes it with one key (`make calibrate`, **A**) or clicks.
Nothing runs on a calibration nobody looked at until the owner switches the
inbox to `accept` (`VOLLEY_AUTO_CALIBRATION=accept`).

## How it reads the picture

No model: the court is line tape on sand (AGENTS §7: fixed camera on the long
axis, net facing the lens).

| step | what | why it holds |
|---|---|---|
| plate | median of 45 frames of the first 3 min, decoded in order | players and ball vanish, tape and net stay |
| tape | thin things on the sand whose COLOUR is not the sand's | a shadow only changes brightness; the tape's colour is read off the picture, never assumed |
| lines | what adds up along a whole line, twice (any colour, then the tape's own) | half-buried tape is barely above the sand's noise |
| court | near baseline + the two sidelines that leave its ends and converge: the triple with the most tape | the neighbouring court has less tape in the picture |
| as it lies | each tape is followed from mid-court outwards; a corner is where two tapes cross | tapes bow (12–40 px off a straight line), and a corner may be outside the frame |
| net tape | the line along which the colour hardly varies while it varies a lot just above and below; then its two edges | one object spans the court in front of trees, fences, buildings; works brighter or darker than the background |
| across | near baseline ∩ net tape | both are parallel in the world: they fix the direction of every line across the court |
| far baseline | where a sideline's tape ends; far tape where it shows; the camera's known focal length | see below |

**The far baseline is the hard part.** At vall d'Hebron by day it is buried:
there is no far line in the picture. The owner's far clicks sit where each
sideline's tape ends. Reads, each as a depth along the left sideline:

- `left_end` / `right_end`: where that sideline's tape stops for good (a
  buried stretch up to 0.5 m is bridged; 1.2 m of quiet sand ends it). A tape
  ends short of its corner when its last stretch is buried, never beyond: of
  two ends that agree, the farther is taken.
- `far_tape`: an across-line covered by unbroken stretches of tape
  (≥ 20 % of it, ≥ 0.25 m each).
- `camera`: where the far baseline must be for the corners to imply the focal
  length this camera is known to have (the median of ≥ 3 other calibrations
  within 4 %; a video never reads its own file). It confirms a read of the
  picture (within 0.6 m), it never replaces one.

One read is a proposal. Two that agree (1 m) are a calibration.

## What it accepts

`accepted: true` needs all of:

- a court (near baseline covered ≥ 35 %, sidelines ≥ 25 % on their near half);
- tape seen on ≥ 50 % of each sideline up to its far corner;
- the far baseline seen by two reads that agree;
- no sideline's tape running on beyond that far baseline;
- a net tape, reading 2.10–2.60 m through the finished calibration;
- corners that imply a plausible camera (0.8–4.5 m up, 3–18 m behind the near
  baseline, focal 0.45–1.8 × the frame width).

Anything else is `accepted: false` with the reasons, and still a proposal
with its 8 points (unless no court was found at all).

## The bar (C0): how wrong may a calibration be?

`probe_calibration_sensitivity.py` moves one quantity at a time and
reconstructs the finished run in memory (post-run layer only).

| run | decisions hold up to (far width / near width / far row / near row) |
|---|---|
| 20260920 beach | ±6 % / ±6 % / ±16 px / ±16 px (everything tried) |
| 20261010_1100 | ±4 % / ±4 % / ±16 px / ±16 px |
| 20261010_1000 | 1.0 % / **< 0.5 %** / 2 px / 2 px |
| 20261010_1200 | **< 0.5 %** / 1.0 % / 4 px / ±16 px |
| e1–e7 | ±3–6 % / ±6 % / ±16 px / ±16 px |

The net clicks (±16 px) change no decision on any run.

Two of three high-tripod matches have one or two knife-edge points that flip
at 0.5 % of a baseline width (3 px). No recalibration can promise identical
decisions there, the owner clicking again included. So the bar is what the
match becomes against the owner's GT, with every differing point listed.
That fragility belongs to the post-run layer and is open (STATUS open point 36).

## Measured record

Views: 6 distinct in-spec calibrations exist (e1–e7 share one). Developed on
e3, 20261010_1000 and 20260920. 1100, 1200 and 1230 were scored with the
detector frozen (commit `498898b`); 1230 was run before reading the owner's
file. Auto minus clicks, px:

| view | accepted | far L | far R | near R | near L | far / near width | net reads |
|---|---|---|---|---|---|---|---|
| 20260920 beach (dev) | no | +34, −1 | +40, +3 | −4, −3 | −3, −1 | +1.1 % / −0.1 % | 2.40 m |
| 20261010_1000 (dev) | yes | +2, −5 | −3, −5 | +2, +4 | −1, 0 | −0.8 % / +0.2 % | 2.37 m |
| 20261010_1100 (held out) | yes | −6, +7 | −3, +4 | −10, −1 | +8, −2 | +0.5 % / −1.0 % | 2.41 m |
| 20261010_1200 (held out) | yes | −4, +2 | +2, −8 | −10, −3 | +3, +3 | +1.0 % / −0.7 % | 2.35 m |
| 20261010_1230 (held out, blind) | yes | +7, −6 | +7, −7 | −2, −2 | +5, +7 | 0.0 % / −0.4 % | 2.32 m |
| e3 = e1–e7 (dev) | yes | −8, +5 | +15, +4 | +8, −5 | **−92, +21** | +3.4 % / +5.2 % | 2.38 m |

- **e1–e7:** the near-left corner is ~90 px outside the frame. The click sits
  at (7, 910), inside it, so the manual file's near baseline is 5 % short.
  The automatic corner is the extrapolated one.
- **Beach:** refused. The right sideline shows tape on 30 % of it and the far
  corners are 34–40 px off sideways (0.5 m); the far row is right (far tape).
- **Honest note on acceptance:** frozen, the detector accepted 1100 and e3 only
  (1000, 1200, 1230 had one read each). The `camera` read was added after
  seeing that; it changed no point, only `accepted` on those three. The
  follower fix found on drawn courts moved far corners by ≤ 2 px on them.

Focal length implied by the corners, the four same-morning videos: automatic
1870–1943 px (±1.9 %), clicks 1838–1972 px (±3.5 %).

### What the match becomes (post-run replay, the existing dumps)

| run | with the clicks | with the automatic file |
|---|---|---|
| 20260920 | 33/33 points, winners 33/33, P 0.976 / R 0.933, action 0.988 | identical, 0 touches differ |
| 20261010_1000 | 31 points, A 22 – B 9 | identical, 0 touches differ |
| 20261010_1100 (owner table) | 35/35, serving team 35/35, winners 34/35 | same; +12 touches, 1 label |
| 20261010_1200 | 41 points, A 21 – B 20 | same points and winners; −2 touches, 1 label |
| e1–e7 | serves 5/5, P 52/53, action 52/52 | identical |

No point lost or invented, no serving team or winner changed, on any run.

### Full run with the automatic file (C2, causal pass re-run, same session)

| | clicks | automatic |
|---|---|---|
| e1–e7 causal actions | 61 | 60; identical on 5 clips; e1 f114 dig → spike (GT: freeball); **e7 f163 spike lost** (a reach-gate contact, STATUS open point 7) |
| e1–e7 post-run | serves 5/5, P 52/53, R 52/58, action 52/52 | 5/5, P 53/54, R 53/58, action 53/53 |
| 20261010_1100 (held out), owner table | 35/35 points, serving team 35/35, winners 34/35, A 14 – B 21, switches 8 / 15 / 22 / 29; 251 causal actions, 201 touches | the same points, serving teams, winners, score and switches; 256 causal actions, 213 touches |

The 12 extra touches on 1100 are one point: P13 (serve f9889) is a 15-touch
rally of 20.9 s instead of one cut after 3 touches at f9987. Frames decoded in
order show all four players playing on to f10412 and the ball picked up at
f10450 (the agent's read, not the owner's). The same +12 appears when the
manual run's own dump is replayed with the automatic file, so it is the
post-run geometry, not the causal pass: that rally end is one of the
knife-edge reads.

## Known limits

1. **Two venues, two tape colours, 6 views.** White lines, rope, no lines, a
   third venue: untested. It refuses what it cannot read; it has never been
   shown a court it reads wrongly with confidence, which is not proof.
2. **Both sidelines buried alike near the far corners** agree with each other
   on a far baseline that is not there. Only the camera read speaks against
   it, and only where ≥ 3 earlier calibrations share the lens setting. Pinned
   as a test (`test_both_far_ends_buried_alike_…`).
3. **The camera read assumes one lens setting.** A zoomed video matches no
   known focal length: no confirmation, a proposal. A wrong focal length cannot
   side with a tape that ends short while the other tape runs on (test).
4. **The points under the net are the middle of the court** (the 16 × 8 m
   homography), not the posts. The clicks read 7.3–7.8 m there at vall
   d'Hebron: 3–20 px lower. No decision reads them; the published court
   positions (`positions.py`, #101) anchor on them and move by up to ~0.7 m
   along the court on a newly calibrated match.
5. **Results move with any recalibration** (the knife-edge points above). An
   existing match keeps its manual file: never recalibrate a published match.
6. **Not built:** the start / middle / end check for a camera bumped
   mid-video; the cross-check from play after the run (ball width at serves,
   feet inside the court); a far corner read off the far tape's own end.
7. **Lens:** a pinhole with its centre in the middle of the frame is assumed
   for the camera read only; the 8 points themselves come from tape.

## Using it

```bash
make autocalibrate VIDEO=resources/<key>.mp4            # proposal -> output/<key>/calibration_auto/
make autocalibrate VIDEO=resources/<key>.mp4 WRITE=1    # + calibrations/<key>.json when accepted and none exists
make calibrate VIDEO=resources/<key>.mp4                # shows a proposal first: A accept, C click
venv/bin/python scripts/score_autocalibration.py        # every view against its clicks + replays
venv/bin/python scripts/probe_calibration_sensitivity.py output/<run>   # how much that run tolerates
```

Look at `auto_points.jpg`: the 8 points zoomed, green ring = automatic, red
cross = manual when one exists. An accepted file carries `source: "auto"` and
`auto: {version, accepted, accepted_by: checks | owner, reasons, checks}`;
every reader uses the four standing keys. A run on it says so in
`calibration_readiness` (`calibration_method: "auto"`); a run on a clicked
file reports exactly what it always did.

Inbox (`.env.publish`): `VOLLEY_AUTO_CALIBRATION=propose` (default) / `accept`
/ `off`. A manual calibration is never overwritten.
