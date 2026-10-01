# G4 -- serve-evidence events: far flight (E1) + serve runway (E2)

Status: implemented + unit-tested + scored against the owner GT far serves.
Baseline to beat: **F1 0.772, far serves 0/12** (`docs/g3_heldout_p9_p33.md`).

## Why

Open point **G2** (the owner decision on the far-serve lever) had nothing left
to choose between: T5 (tracker admission), R1 (departure gate), S1 (looming as
a *discriminator*) and pass-2 re-labelling were all refuted, and G1 then showed
the far serve is 0/12 on held-out contacts. The owner's alternative is not
another classifier -- it is to **emit the evidence a far serve physically must
leave** and decide with it afterwards:

* **E1 `far_flight`** -- after a far-side contact the ball flies *toward* the
  fixed long-axis camera, so its apparent bbox width **grows**. Monocular, no
  toss needed (the toss is absent at ~3/5 far serves, T5). S1 refuted using
  `L` to *separate* serves from other far lofts (kill 2: 0.338 vs 0.945, no
  empty gap); as an *event* paired with E2 it is still evidence.
* **E2 `runway_occupant`** -- the server stands **off the court behind the far
  baseline**, so strict foot-in-court admission can never track them
  (`PlayerTracker` locks exactly 4 in-court tracks; AGENTS.md §1). Region: the
  two sidelines **continued to infinity**, not extending behind the near line.
* **Conjunction `serve_candidate`** -- "a player in this area, with the ball,
  and a contact": an occupant whose box the ball was inside/next to within
  `serve_candidate_lookback_s`, at a `far_flight` onset.

## Code

| file | what |
|---|---|
| `src/analysis/serve_events.py` | `ServeRunway` (geometry), `ServeRunwayWatcher` (E2), `FarFlightDetector` (E1), `ServeEventEmitter` (conjunction) |
| `src/analysis/frame_processor.py` | builds the emitter only when `serve_events_enabled`; `setup_video_fps` re-times the second-based windows |
| `src/detection/player_detector.py` | inert side channel `off_area_detections` -- the person boxes the play-area filter dropped |
| `src/detection/ball_detector.py` | inert side channel `raw_detections` -- pre-static-suppression ball candidates (the AGENTS.md §6 escalation path) |
| `src/analysis/video_processor.py`, `src/output_gen/json_exporter.py` | `serve_events` key in `pipeline_output.json`, **absent unless the emitters ran** |
| `src/main.py` | `--serve-events` |
| `scripts/score_serve_events.py` | replays the GT far-serve windows through the shared path and scores the events |
| `tests/test_serve_events.py` | 42 tests |

**Inert by construction.** Default `serve_events_enabled = False`: no emitter,
no events, no new keys, byte-identical artifacts; the detector side channels
only append references to dicts that already exist. Every event is *evidence*:
nothing writes back into the tracker or the action stream.

## Geometry (and the one measurement that shaped it)

Image-space only, from the 8 calibration clicks. The 4-corner ground
homography assumes a 16x8 m beach court and is badly wrong at the far end of
the beach match -- it predicts a 1.8 m person ~7 px tall at the far baseline
where the detector returns 90-160 px boxes -- so metre gates there are
meaningless, and AGENTS.md §7 already forbids px constants that do not travel.

"Between the sidelines continued to infinity" is a **projective wedge**: the
extended sidelines cross at an apex (1055, 504) on the beach match, so the
half-plane tests close the region by themselves -- no height cap needed, and
bystanders beside the court are rejected for free.

**The band straddles the far baseline.** Measured over the 17 GT far serves of
the beach match (raw person detections, conf >= 0.20, 101-frame windows):

| band around the far line | GT far serves with a person present (>= 10 frames) |
|---|---|
| strictly behind (`front = 0`) | **7 / 17** |
| `-0.15 .. +0.30` x court depth (default) | **17 / 17** |

A far-side server very often stands *on* the far line, so the literal
"behind the far line" region misses two thirds of them. Defaults:
`serve_runway_front_frac = 0.15`, `serve_runway_back_frac = 0.30`,
`serve_runway_side_margin_frac = 0.0`. Fractions, not pixels, because the court
projects 206 px deep on the beach and 464-479 px at the practice venue (2.3x).

## Event shapes

```json
{"type": "runway_occupant", "frame": 100, "start_frame": 100, "end_frame": 149,
 "frames": 50, "peak_conf": 0.6, "bbox": [900, 480, 940, 570],
 "off_far_line_px": 24.1, "off_court_frames": 50}

{"type": "far_flight", "frame": 140, "onset_frame": 140, "end_frame": 144,
 "sightings": 5, "growth": 0.86, "width_start": 14.0, "width_end": 26.0,
 "mean_conf": 0.6, "onset_center": [920.0, 550.0]}

{"type": "serve_candidate", "frame": 140, "contact_frame": 140,
 "evidence_frame": 140, "occupant_bbox": [...], "occupant_region": "runway",
 "occupant_conf": 0.6, "ball_gap_norm": 0.0, "ball_conf": 0.6,
 "flight_growth": 0.86, "flight_sightings": 5}
```

`growth` is `L` = OLS slope of `ln(width)` vs **seconds** over a
`far_flight_span_s` window; `ball_gap_norm` is the ball-to-box distance in
occupant bbox heights.

## Honest limits

* The reach radius (1.0 bbox height) is **generous relative to the band**: the
  far band is only ~90 px tall on the beach match, so a flight ball inside it
  is usually within reach of any occupant in it. The conjunction therefore
  needs the *timing* (the ball must be with the player near the onset), not
  just the distance -- see `serve_candidate_lookback_s`.
* The emitters are track-free by design (windowed replay resets trackers), so
  they cannot say *which* player served, only that a person was there.
* Nothing here is validated as a mechanism: an event is evidence, and the
  scored numbers are coverage, not precision on the contact stream.

## Measured (2026-10-01, `scripts/score_serve_events.py`)

Windows `[c-90, c+60]` replayed through the real `process_frame` on the
20260920 match, emitters ON. Far serves: the 17 GT far serves (5 dev P1–P8,
12 held-out P9–P33). Control: 24 mid-rally **non-serve** GT contacts, where any
candidate is a false positive by construction.

| event | far serves (17) | held-out (12) | control windows (24) |
|---|---|---|---|
| `runway_occupant` near the serve | **15** | 10 | 18 (fires often: weak alone) |
| ... of which genuinely off-court | 7 | 5 | 5 |
| `far_flight` in window | 11 | 9 | 14 |
| `far_flight` within +-15 f | 4 | 3 | **8** |
| `serve_candidate` in window | 6 | 5 | 4 |
| **`serve_candidate` within +-15 f** | **3** | **3** | **1** |

Contact-level: **3 hits / 1 false positive** (P25 d=13, P26 d=6, P32 d=6 vs one
control at d=6), against production's **0/12** held-out far serves. Offsets when
the conjunction fires are 6/6/13 f -- inside the owner's own coarse +-10-15 f.

Read it honestly:

* **E2 (runway) is the strong leg**: a person is in the far band at 15/17 far
  serves (10/12 held-out), and only at 7/17 is he genuinely off-court. That is
  the direct confirmation of the owner's premise -- the server is usually
  detected but not *trackable*, because he is off the court or standing on the
  line. It is also why the band had to straddle the far line.
* **E1 (far flight) is a weak discriminator on its own** (4/17 vs 8/24
  control), exactly S1's kill 2 reproduced on held-out data. Its value is
  conditional: after the runway leg, it is what turns an occupancy into a
  candidate.
* **The conjunction is the usable signal but it is thin**: 3 contacts where we
  had none. It is an evidence stream, not a fix. Two of the three are held-out
  points, so the number is not a dev artefact, but 3/12 is not a mechanism.
* What is missing is not the geometry but the **ball**: a far ball is detected
  on roughly 1 frame in 4, so runs must tolerate gaps, and half the far-serve
  windows have no growing-width run at all.

## Reproduce

```bash
venv/bin/python scripts/score_serve_events.py                    # all 17 far serves
venv/bin/python scripts/score_serve_events.py --dev-only         # the 5 dev ones
make run VIDEO=resources/full_videos/20260920_match_ari_joan_lost.mp4 EXTRA="--serve-events"
```
