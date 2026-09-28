# De-hardcoding the perception layer — camera-agnostic action recognition

> **Status:** PROPOSAL (2026-09-28) — nothing implemented. Zero `src/` changes
> to date. Written after a read of `AGENTS.md`, `STATUS.md`,
> `src/recognition/action_classifier.py`, `src/recognition/action_context.py`,
> `src/analysis/spike_analyzer.py`, `src/detection/court_calibration.py`,
> `src/utils/config.py`, `src/analysis/video_processor.py`,
> `src/analysis/frame_processor.py`, `src/main.py`.
>
> **Problem statement (owner):** ball YOLO and body YOLO work well, but the
> *actions* are hardcoded and depend on the camera angle; some actions depend
> on how much the ball is moving. Consequence: record a new video and the
> actions stop being tracked.
>
> **Reading order:** §1 diagnosis (where the video-dependence actually is) →
> §2 measurement-first step → §3 the proposed mechanisms → §4 sequencing
> and gates → §5 what I would not do.

---

## 1. Diagnosis: the fragile surface is small and concentrated

The intuition is correct but the damage is not spread evenly. ~17 constants in
two files carry the fragility, and they fail in **three structurally different
ways**, which need three structurally different fixes.

### (A) Apparent-size constants — the side/attribution signal (worst offender)

`ActionClassifier` ctor `width_far_px=26.0 / width_near_px=35.0`
(`src/recognition/action_classifier.py:186-187`; config keys
`attribution_width_far_px` / `attribution_width_near_px`,
`src/utils/config.py:155-156`). Used by `_width_side()`
(`action_classifier.py:856-886`).

These are raw **pixels of ball diameter**, measured on one camera at one
distance. Move the camera 20 m back and the far-half ball is ~14 px and the
near-half ~20 px → **both fall under 26 → the width side abstains on every
frame** → attribution silently falls back to possession alternation, and
`_closest_player_at`'s team filter starts deleting real contacts (the
e2 f167 class — "dies at the reach gate by 4 px" — is a width/reach
failure, not a detection failure).

This is the single most likely explanation for "actions stop being tracked"
on a new camera: the side signal dies *silently* (abstain is a legal outcome,
so nothing logs an error).

### (B) Displacement constants — the gesture ladder

All in `src/recognition/action_classifier.py` unless noted:

| Constant | Value | Role |
|---|---|---|
| `MIN_PROMINENCE` | 26.0 | ball must rise this much on both sides of a bounce |
| `XREV_MIN` | 20.0 | net horizontal displacement for a redirect |
| `BRIDGE_MIN_DROP` / `BRIDGE_MIN_RISE` | 20.0 / 60.0 | short-gap bridge shape check |
| `BRIDGE_X_CONT_PX` | 24.0 | cross-gap ball-identity continuity |
| `REENTRY_JUMP_PX` | 200.0 | min identity break pre-gap → run |
| `POKE_EXIT_VX_PX` / `POKE_EXIT_VY_PX` | 25.0 / 12.0 | airborne-net-contact shape |
| `RISE_MIN_PX` | 30.0 | outgoing vertical speed = "ball rising" |
| `NEAR_NET_PX` | 120 | `\|y - midcourt\|` band = "near the net" |
| `TOUCH_RISE_PX` (`spike_analyzer.py:86`) | 57.0 | rise that separates touch classes |
| `DIG_LOFT_PX` (`spike_analyzer.py:106`) | 90.0 | a dig's loft (kill vs touched) |

All are "how many pixels did the ball move in the image", which scales with
**court depth in pixels**. A camera 30 % higher sees the same 2 m of court
rise as ~30 % fewer pixels → the dig-loft and bounce-prominence gates stop
firing → no contacts → no actions at all.

### (C) Speed constants — dependent on px *and* fps

`DRIVE_MIN_SPEED 8.0`, `DRIVE_DECEL 8.0`, `DRIVE_XIMPULSE 12.0`,
`DRIVE_RISE_TOL 3.0`, `DRIVE_MIN_PX 55.0`, `REENTRY_MIN_SPEED 40.0`
(`action_classifier.py:142-160`); plus `ball_lock_min_speed 8.0` and
`fast_ball_velocity_threshold 50.0` (`src/utils/config.py:51,124`).

These are **px/frame**. Two independent dependencies: pixels *and* frame
rate. The match is already VFR 25.67-in-30.12 (STATUS Learnings; open point
19(a) parks exactly this). A 60 fps phone video divides every one of these by
~2 → the drive/impulse tests go blind.

**Free win:** `FrameProcessor.setup_video_fps()`
(`src/analysis/frame_processor.py:197-200`) already receives fps from
`VideoProcessor` (`video_processor.py:65-72`) and hands it to
`game_state_manager` — but **never to the classifier**. The number is right
there and unused.

### (D) Camera-invariant — leave alone

`MIN_CONTACT_GAP 9`, `CONTACT_DELAY 7`, `RALLY_RESET_GAP 90`, the whole
`ActionContextResolver` touch-counting / 3-touch rule
(`src/recognition/action_context.py`), `world_point_to_zone` attack zones,
`is_in_serve_zone` (already in ground metres, already camera-agnostic,
`court_calibration.py:659`).

This is why `scripts/relabel_serves.py` (pass 2, point 22) and
`game_state_manager` transfer to unseen footage untouched, and it confirms the
owner's read: **the perception/gesture layer is the problem, not the
interpretation layer.**

### (E) The silent-degradation path (a presentation bug, not a threshold bug)

The 8-point `CourtCalibration` is already **per-video and mandatory**:
`src/main.py:166-178` auto-detects `calibrations/<video_stem>.json` and, when
absent, logs one line and **continues in a degraded mode**. Every
court-derived signal (team, near_net, behind_baseline, zones, the near-net
attribution exemption) then goes away, and the classifier emits ~zero
actions with **no loud failure**.

"Actions don't get tracked" is currently indistinguishable from "the
calibration filename didn't match the video stem". Two cheap, non-mechanism
fixes belong at the front of the queue:

1. make a missing/unmatched calibration a **loud precondition failure** (or at
   minimum a loud, unmissable banner in the outputs);
2. record the camera profile in `pipeline_output.json` so every downstream
   number carries the camera it was measured under.

---

## 2. Step 0 — make "hardcoded" a number, not a feeling

Per the diagnose-first working style, no design work until the priority order
is measured. We have GT for 7 entrenos + the match, so build a
**camera-perturbation suite** as the generalization metric:
`scripts/camera_perturbation_suite.py` — synthetically re-shoot the validated
videos, then run `evaluate.py --ignore-player`.

| Perturbation | What it simulates | Construction |
|---|---|---|
| **zoom** | camera distance | crop 15 / 25 / 40 %, rescale back to 1080p |
| **elevation** | camera height / angle (the owner's named failure) | vertical perspective warp of the court region |
| **fps resample** | 60 fps phone, 15 fps webcam | drop or duplicate frames; GT frame numbers rescaled |
| **off-axis** | camera not centred on the long axis | horizontal shear + mild rotation |
| **re-encode** | different phone / bitrate | 720p→1080p path, mild blur + noise |

**Deliverable:** an F1 table (per perturbation × per video) plus a
**label-flip attribution**: for every flipped contact, *which constant*
rejected it (`XREV_MIN`? `DIG_LOFT_PX`? width-band abstain? reach gate?).

**Caveat to respect:** warping a video changes ball appearance and therefore
detector behaviour. So (i) verify the ball track survives the perturbation
before blaming the classifier — "probe raw detector output first", the
entreno lesson; and (ii) read the flip attribution per-constant, not just the
aggregate F1.

This suite is also the **permanent regression gate** for everything in §3.
Note the required eval convention: recorded action F1s only mean anything with
`--ignore-player` (GT `player_id` is a per-frame L-R index).

---

## 3. Proposed mechanisms

### Step 1 — a per-video *camera profile* with identity-preserving rescale

Extend the **existing** calibration artifact; do not add a second config
surface. The 8-point JSON already keys on `<video_stem>.json` and is already
required — it becomes a camera profile carrying, in addition to the points:

- `court_depth_px` (near-baseline y − far-baseline y), `court_width_px_near/far`, `net_height_px`
- `px_per_m` at the net and at each baseline (from `court.world_scale_at()`, `court_calibration.py:619`)
- `fps` (already known, `video_processor.py:65`)
- `ball_width_far_mode` / `ball_width_near_mode` (measured — see Step 2)

Then:

- every **(B)** constant becomes `reference × (court_depth_px_video / court_depth_px_reference)`
- every **(C)** constant becomes `reference × (scale_ratio) / (fps_video / fps_reference)`

**The critical property:** set `court_depth_px_reference` = the **median over
the 7 entrenos + the match**. For any video already in that set the factor is
≈1.0, so the A/B is **byte-identical or near** — the same no-regression-by-
construction move as the 09-27 pose gate. New cameras get a proportional
rescale instead of a wrong constant.

**Explicitly better than the `px→metres` swap that point 4 GT-refuted:**
that changed the *semantics* of near-net (e3 label F1 0.929 → 0.857). This
keeps the px semantics — point 4's finding that "the px `near_net` is
load-bearing" stays true — and only corrects the **scale**. Revisit point 4's
metre variant only if the perturbation suite says scale-fixing is insufficient
on top-down cameras specifically.

### Step 2 — replace the width bands with a measured per-video split

`26 / 35 px` becomes a **2-cluster split of the observed ball-width time
series** (k-means on widths, or Otsu on the histogram), with the abstain band
derived from the cluster separation. The predicate itself, the abstain
semantics, and the commit rule (`_width_side`, `action_classifier.py:856-886`)
are untouched — only the two numbers come from the video instead of from this
camera.

If the split is unimodal, or the separation is below a floor, the profile
records `width_side_unreliable: true` and attribution degrades **loudly and on
the record** rather than silently — which is exactly the failure mode in §1(A).

### Step 3 — make the "how much is the ball moving" features dimensionless

This is the class the owner named explicitly. The code already contains the
right null model in its own comments ("a ball under gravity keeps a
near-constant horizontal speed and accelerates downward"). Push that all the
way: express the drive/impulse/rise thresholds as **ratios to the ball's own
recent flight baseline**.

Examples:

- `DRIVE_XIMPULSE 12.0 px/f` → "horizontal velocity change ≥ k × the ball's
  mean speed over the last N sightings"
- `RISE_MIN_PX 30.0` → "post-contact rise ≥ k × the gravity-predicted drop
  over the NEIGH window"

Ratios are invariant to resolution, fps *and* camera distance simultaneously,
and each constant collapses from "a number measured on my video" into "a
dimensionless gain with a physical meaning". The only per-video scalar left is
the median ball px-per-metre from Step 1.

**Exception — do reach differently:** `CONTACT_REACH 140.0` and
`SERVE_REACH_PX 160.0` are body measurements, not ball-flight measurements.
Convert them to **metres** via `world_scale_at()` at the player's foot point
(~1.2 m / ~1.5 m allowance). Reach is a body measurement and a homography is
exactly the right tool for it — the tracker already uses `world_body_size()`
for precisely this reason (open point 1c).

### Step 4 (conditional) — a fitted decision layer, not more thresholds

Only if Steps 1-3 leave real error:

`scripts/train_action_head.py` — dump the *existing* gesture features at every
contact (made dimensionless by Steps 1-3), label them from GT, fit a small
model (logistic regression or a shallow GBM), and ship it as an **optional
head** that can shadow the hand-written `_detect_gesture` ladder.

Hard requirements:

- **Leave-one-video-out** validation, never a random frame split. A random
  split over frames from the same video scores beautifully and proves nothing —
  and would be precisely the overfitting this document exists to remove.
- Only worth it once features are dimensionless. Otherwise the model just
  memorizes this camera, and the problem becomes *less* visible rather than
  *smaller*.
- It must not fork the production path: `FrameProcessor.process_frame` stays
  the one shared path (AGENTS §2), so the head has to be a swappable component
  inside it, not a second pipeline.

---

## 4. Sequencing and gates (one mechanism per session, in project idiom)

| # | Mechanism | Gate |
|---|---|---|
| 0 | `scripts/camera_perturbation_suite.py` (measurement only) | F1 table + per-constant flip attribution; **zero `src/` changes** |
| 1 | Camera profile in the calibration JSON + court-depth rescale of the (B) constants | byte-identical on 7/7 entrenos (factor ≈ 1.0) or a ratified delta |
| 2 | fps normalization fed to the classifier (fps already known) | byte-identical at native fps; measured gain at 2× / 0.5× |
| 3 | Measured width split replacing 26/35 | 14/14 e3 attribution + all 7 entreno team accuracies |
| 4 | Reach → metres via `world_scale_at` | e2 f167-class gate resolved; 7/7 entreno F1 |
| 5 | Dimensionless motion ratios | perturbation-suite F1 delta |
| 6 | Fitted head (conditional) | leave-one-video-out |

Cross-cutting, do these first because they change how failure *presents*
(§1(E)):

- make a missing/unmatched calibration a loud precondition failure;
- write the camera profile into `pipeline_output.json`.

**Standing constraints (unchanged by this proposal):**

- `ball_confidence` must stay `0.15` — every GT-validated action number was
  measured there (the f539 bug class);
- keep the config-drift guard test extended for every new profile key;
- every mechanism gets a **byte-identical A/B on the validated videos first**,
  then a perturbation-suite number as the generalization claim;
- perception stays causal and single-pass; nothing here re-opens the
  two-pass question (AGENTS §6, pass-2 interpretation layer stays post-hoc).

---

## 5. What I would not do

- **Keep tuning the ladder per video.** That is the mechanism that is failing.
  Every new video currently costs a hand-tune; the goal is a new video costing
  a calibration click.
- **Touch the pass-2 layer** (`relabel_serves.py`, the episode→point map). It
  is already camera-free and validated against all 17 owner verdicts.
- **Add a second calibration/config file.** Two sources of truth is how the
  0.15 `ball_confidence` skew happened; extend the artifact that is already
  per-video and already mandatory.
- **Swap `near_net` px → metres globally** (point 4 already refuted that on
  e3). Rescale the px semantics instead (§3 Step 1).
- **Learn a head before the features are dimensionless.** That hides the
  overfitting rather than removing it.
- **Relax the "exactly 4 players" / court-membership invariants** chasing a
  new video's numbers. That territory is GT-validated (entreno protocol) and
  is not what is failing.

---

## 6. First action, if approved

Start with **Step 0** (the perturbation suite). It changes no production code,
needs no new GT, and converts the whole argument above from an ordering of
guesses into a measured priority — while becoming the permanent generalization
gate for the mechanisms that follow.
