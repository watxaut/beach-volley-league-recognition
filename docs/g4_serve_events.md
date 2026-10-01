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

**Re-measured with the PRODUCTION ball model.** The first run used
`Config.default()` alone, which leaves `ball_model_path = None` -> the COCO
`yolov8n.pt` instead of the fine-tuned `models/volleyball_ball_best.pt` that
`src/main.py` auto-loads ("the COCO fallback rarely finds a volleyball on real
footage"). Both probes now go through `production_config()`, which performs the
same wiring as `src/main.py`. The runway leg was unaffected (the player detector
is `yolov8n` in both paths); the ball legs were a lower bound.

Windows `[c-90, c+60]` replayed through the real `process_frame`, emitters ON.
Far serves: the 17 GT far serves (5 dev P1–P8, 12 held-out P9–P33). Control: 24
mid-rally **non-serve** GT contacts, where any candidate is a false positive.

| event | far serves (17) | dev (5) | held-out (12) | control (24) |
|---|---|---|---|---|
| `runway_occupant` near the serve | 15 | 5 | 10 | 18 (fires often: weak alone) |
| ... of which genuinely off-court | 7 | 4 | 3 | 5 |
| `far_flight` in window | 16 | 5 | 11 | 21 |
| `far_flight` within +-15 f | 8 | 3 | 5 | 15 |
| `serve_candidate` in window | 14 | 5 | 9 | 15 |
| **`serve_candidate` within +-15 f** | **6** | **3** | **3** | **4** |

Contact level: **6 hits (offsets 2, 2, 2, 7, 9, 15 f) vs 4 false positives** in
24 non-serve control windows -> precision **0.60**, recall **0.35**, against
production's **0/17** far serves (**0/12** held-out). The accidental COCO run
measured 3 hits with 1 false positive: the correct detector buys recall
(3 -> 6) and costs precision (1 -> 4 FPs), which is why the control windows
exist.

Read it honestly:

* **E2 (runway) is the strong leg**: a person is in the far band at 15/17 far
  serves (10/12 held-out), and only at 7/17 is he genuinely off-court. That is
  the direct confirmation of the owner's premise -- the server is usually
  detected but not *trackable*, because he is off the court or standing on the
  line. It is also why the band had to straddle the far line.
* **E1 (far flight) is weak alone** (8/17 vs 15/24 control), reproducing S1's
  kill 2 on held-out data; its value is conditional, after the runway leg.
* **The conjunction is the usable signal and it is still thin**: 6 contacts
  where we had none, precision 0.60.
* **Why the action stream cannot get there on its own** is measured in
  `docs/g4_far_serve_failure_mode.md`: the contact detector's four px-space
  tests cannot reach their thresholds at the far end (no lowest vertex, no
  horizontal flip, gravity-decaying toss), so the far serve is geometrically
  invisible to `ActionClassifier` even when the ball is tracked on 31/31 frames.

## Reproduce

```bash
venv/bin/python scripts/score_serve_events.py                    # all 17 far serves
venv/bin/python scripts/score_serve_events.py --dev-only         # the 5 dev ones
venv/bin/python scripts/score_serve_events.py --control          # the false-positive side
# why the action stream cannot reach them:
venv/bin/python scripts/probe_far_serve_tracking.py --side far
venv/bin/python scripts/probe_far_serve_tracking.py --side near
venv/bin/python scripts/probe_far_serve_geometry.py --dir output/g4/far_serve_dumps
make run VIDEO=resources/full_videos/20260920_match_ari_joan_lost.mp4 EXTRA="--serve-events"
```
