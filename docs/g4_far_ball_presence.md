# Is the far ball actually missing? No -- and that moves the blocker

M1 of the far-serve plan: the match is natively 1280x720, upscaled once, and
the ball detector runs at imgsz 1280 on the 1920-wide frame, so a far ball
measuring 14-28 px in the working frame is 9-19 px inside YOLO -- at the
stride-8 detection floor. If that were the reason the far serve dies, running
the **same weights** on a small **square** crop of the far band (4x
magnification: `scripts/probe_far_roi_ball.py`, tile 320, 3 tiles) would recover
the missing detections. (Square matters: ultralytics letterboxes by the max
dimension, so a full-width band crop gains no resolution at all.)

**Result: the premise is false, and that is the useful finding.** The detector
sees the far ball at the serve moment in nearly every window.

## 1. Ball presence in the contact window (c ± 15 f, 31 frames)

Full-frame production arm vs the 4x-magnified far-band arm, both with the
production weights at imgsz 1280, conf 0.15, seek-free sequential decode:

| point | serve frame | full-frame frames with a detection | tiled-only frames |
|---|---|---|---|
| P1 | 210 | 23/31 | 4 |
| P2 | 880 | 17 | 7 |
| P4 | 2154 | 17 | 14 |
| P6 | 3038 | 21 | 7 |
| P8 | 4770 | 23 | 4 |
| P13 | 8506 | 16 | 13 |
| P14 | 9103 | 26 | 2 |
| P15 | 10044 | 25 | 6 |
| P21 | 15145 | 28 | 2 |
| P22 | 15925 | 29 | 2 |
| P23 | 16659 | 27 | 4 |
| P25 | 18840 | 25 | 6 |
| P26 | 19832 | 14 | 14 |
| P27 | 20922 | 23 | 8 |
| P28 | 21356 | 20 | 7 |
| **P31** | **24543** | **2/31** | **25** |
| P32 | 25375 | 26 | 1 |

Detection sizes are 15-21 px -- squarely the venue's far-ball band
(AGENTS.md §5). **0 of 17 windows are empty for the full-frame arm** (kill 1
asked for 5 of 8 recovered), and the single real detector miss in the whole
set is P31 f24543, the slow-float family, where the magnified band pass does
find the ball in 26/31 frames.

## 2. What the magnified pass actually adds: mostly noise

`width_tiled_median = 3.2 px` against `width_full_median = 18 px`. The tiled
arm's median detection is a 12.8 px object *in crop space* -- i.e. sand
texture, court lines, distant heads, the 2.2 det/frame of venue noise STATUS
already records. A magnified far band is mostly *ground*, so 4x magnification
inflates the noise as efficiently as the ball. It also costs
**+104.8 ms/frame** for 3 tiles (34.9 ms each) on top of the 44.3 ms full-frame
arm -- a 2.4x detector cost.

**Verdict: M1 is refuted as a general lever** (1/17 window, at 2.4x detector
cost). It survives only as a *targeted* P31-class fallback: when the far band
is occupied and the ball track has been lost for >N frames, one extra
magnified tile around the occupant is ~35 ms and recovers that case. Parked;
not built.

## 3. The correction this forces on the diagnosis

Every prior far-serve document says the far ball is *absent*:

> "the far ball is seen on 0-1 frames in 8/17 windows" (STATUS, G1 Learnings)
> "2/17 far serves have zero raw detections at conf 0.15 and 5/17 never lock a
> track" (`docs/g4_far_serve_failure_mode.md` §3)

Both are **tracker** statements, not detector statements. The detector fires in
14-31 of 31 frames at 15-21 px. The real chain is:

```
detector: OK  ->  tracker lock: fails on 5-8/17 (never a usable vertex)
                     ->  contact geometry: refuses the rest (four px thresholds
                         unreachable at the far end, twice refuted)
                     ->  actor: the server is not one of the 4 tracks
```

So the ball-presence wall in the M1 plan does not exist, and any further work
on the far serve must attack the *lock* and the *label*, not the resolution.
This is what makes the structural route (M3') the remaining candidate: it uses
the raw detections directly, so it is immune to both the tracker and the
geometry.

## 4. Cost note for whoever implements the fallback

`ms_full 44.3 / ms_tiled 104.8 / 3 tiles` at imgsz 1280 on MPS, tile 320.
Artifact `output/g4/far_roi_ball.json`, driver
`scripts/probe_far_roi_ball.py` (seek-free single pass; tile geometry is
derived from the 8 calibration clicks so it travels across venues, AGENTS.md
§7).
