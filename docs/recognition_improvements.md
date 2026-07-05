# Improving Recognition — Evidence-Based Roadmap

This doc is the *sequel* to `improvement_plan.md`. That plan has largely landed (calibration, 4-player locking, YOLO ball, event-driven actions). This one records **what the measurement tooling now shows is actually limiting recognition** and how to push each lever further. Every claim here is backed by numbers from `scripts/dump_player_tracks.py` + `scripts/analyze_tracking.py` on `video_entreno_3`.

## How to measure (do this before/after any change)

The project can now score player recognition **without manual ground truth**, because team is *defined* by geometry (side of the midcourt line the feet are on):

```bash
# 1. Dump per-frame tracks using the REAL production config (Config.DEFAULT_CONFIG)
.venv/bin/python scripts/dump_player_tracks.py resources/video_entreno_3.mp4 \
    --save-video --out-json output/run/video_entreno_3_tracks.json --output output/run

# 2. Analyze: live-play segmentation + team accuracy + recall/coverage/drop
.venv/bin/python scripts/analyze_tracking.py output/run/video_entreno_3_tracks.json \
    --actions-gt ground_truth/video_entreno_3_annotations.json
```

Key metrics (all scored on **live-play** frames = ≤4 people in court; dead-ball frames with extras are excluded):

| Metric | Meaning | Lever it isolates |
|---|---|---|
| `detection_recall` | mean in-court detections / 4 | **YOLO detector** |
| `tracked_coverage` | mean real tracks / 4 | tracker association |
| `drop_rate` | % live frames with <4 real tracks | end-to-end recall |
| `team_accuracy` | stored team == foot-position team | team logic |

Rule of thumb learned here: **`tracked_coverage ≈ detection_recall`** — the tracker converts nearly every detection, so *recall is the ceiling*. Spend effort on the detector, not the tracker, until that stops being true.

## Current measured state (video 3, live play)

| Metric | Before this work | Now |
|---|---|---|
| Team accuracy | 67% | **99.7%** |
| Detection recall | 74% | **87%** |
| Tracked coverage | 73% | **87%** |
| Drop rate (<4) | 75% | **38%** |

Wins already banked: per-frame team from foot position + vote smoothing; coast extrapolation; `player_imgsz=1280`. The remaining gap is **detector recall on hard frames**.

---

## Ranked improvement avenues

### 1. Player detection recall — the dominant lever (biggest impact)

`drop_rate` is still 38%: on many live frames the detector finds only 3 of 4. The misses cluster on three hard cases, all visible around frame 620:

- **Far-side players** — small, backlit, often occluded by the net tape.
- **Diving/sprawling players** — non-upright, motion-blurred.
- **Players fused with the net line** at the top of the near half.

Options, cheapest first:

| Approach | Expected | Effort | Notes |
|---|---|---|---|
| **Confidence 0.5 → 0.35** | +3pp recall | trivial | Already tested; reverted (adds false detections). Re-enable per-video if precision holds. `config.player_confidence`. |
| **Far-half ROI / tiling** | +5–10pp | medium | Run a second YOLO pass on an upscaled crop of the far half (small region, big pixel gain) and merge boxes. The far players are the worst-detected and the cheapest to isolate because the court geometry is known. |
| **Fine-tune the person detector** | +10pp, durable | high | Auto-label with the current pipeline + hand-correct hard frames (dives, far-side), fine-tune `yolov8n`/`yolov8s` at `imgsz=1280`. Mirrors the existing ball-model workflow (`notebooks/finetune_yolo_ball.ipynb`). Bigger backbone (`yolov8s/m`) alone may also help if runtime allows. |
| **Track-before-detect on the far half** | +recall on occlusion | medium | When a locked far-side track is briefly undetected, run a local detector/template around its predicted box (coast already predicts the box — reuse `_coast_step` output as the ROI). |

**Verify:** `detection_recall` and `drop_rate` on video 3; watch `dead_frames` and `max_simultaneous` for false-positive inflation.

### 2. Tracker init & roster handling (correctness edge cases)

- **`max_players=6` locks junk IDs during a dead-ball opening.** The tracker initializes on the first 60 frames regardless of game state; if the video opens on a dead ball (extras milling), IDs get bound to non-players. **Fix:** initialize (or re-initialize) the roster only on a confirmed live-play window (≤4 stable in-court detections), or make init game-state-aware via `GameStateManager`.
- **Serve inside the init window is unlabeled.** `init_frames=60`; the serve in video 3 is at frame 56, so teams are `None` there and the serve can't be attributed. **Fix:** shorten init, or back-fill team/ID once init completes for the frames it spanned.

**Verify:** action-anchor check in the analyzer (GT `player_team` present at the 12 `actions.events` frames); currently 11/12, the miss is exactly this init-window serve.

### 3. Ball detection & tracking — the ceiling for *action* recognition

Player tracking is now the healthy part; **action recognition is bottlenecked by ball recall**, because the classifier only fires at ball-trajectory inflection points (`action_classifier.py`). If the ball is lost, contacts are missed.

- Measure ball detection rate first (`scripts/test_ball_detection.py`), the same way we measured players — establish the honest number before tuning.
- The fine-tuned `models/volleyball_ball_best.pt` exists; quantify its per-frame recall on the entreno clips and, if low, extend its training set with entreno frames (night, sand, multiple stray balls — note video 2's extra balls are a known contaminant).
- Stray/dead balls on the court (visible in video 3) can create phantom contacts — gate ball association to the live-play ball via game state.

### 4. Game-state gating for stats (precision of the final counts)

Extras walk into the court during dead balls; stray balls sit on the sand. **Only count actions during live play.** `GameStateManager` exists but isn't used to gate stats. Wire live/dead-ball state into the stat aggregation so dead-ball motion never becomes a "dig" or a phantom rally. The `n_court_det > 4` heuristic in the analyzer is a cheap, dependency-free live/dead signal if the full state machine proves unreliable.

### 5. Pose & action classifier refinements (lower priority until 1–4 land)

- Pose is already video-mode + body-relative (`pose_estimator.py`); the limiting factor upstream is detection/ball, not pose features.
- Once ball recall is solid, revisit the Tier-2 set/spike/dig thresholds against the `actions.events` GT (12 labeled events in video 3) and expand labeled events before tuning — the sample is currently too small to trust precision/recall.

---

## Suggested priority

| # | Task | Impact | Effort |
|---|---|---|---|
| 1 | Far-half ROI/tiling + re-test conf 0.35 | High (recall) | Low–Med |
| 2 | Game-state-aware init (kill junk IDs) + init-window serve fix | Med (correctness) | Med |
| 3 | Fine-tune person detector on hard frames | High, durable | High |
| 4 | Measure + improve ball recall | High (unlocks actions) | Med |
| 5 | Game-state gating of stats | Med (precision) | Med |
| 6 | Expand action GT, retune Tier-2 | Med | Med |

## Scope notes

- All numbers above are **video 3**. Video 2 has wandering players + stray balls (contaminated); video 1 has no serve. Re-baseline per video before generalizing — the tooling makes this a two-command operation.
- Changes to `player_confidence`, `player_imgsz`, and the tracker knobs are shared production defaults in `src/utils/config.py`; validate on more than one clip before shipping a change to them.
