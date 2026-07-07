# Making `make run` Faster

Proposals for speeding up `make run VIDEO=resources/video_entreno_4.mp4` (and any other
video) through the batch pipeline (`src.main` → `VideoProcessor` → `FrameProcessor`).

All numbers below were **measured on this machine** (Apple M3 Pro, 11 cores, macOS 14.8,
torch 2.7.1, MPS available). Re-measure on other hardware before trusting the projections.

---

## TL;DR

- **Baseline: ~100 s** to process `video_entreno_4.mp4` (408 frames, 1920×1080 @ 30 fps → ~4 fps, ~7.5× slower than real-time).
- The pipeline is **CPU-bound on two YOLO passes per frame** (player + ball, both at `imgsz=1280`) plus **MediaPipe pose run on every frame for every player**.
- **Two changes get us to ~48 s (~2.1× faster) with no accuracy loss:**
  1. **Run YOLO on MPS (Apple GPU)** — currently hardcoded to CPU.
  2. **Stop computing pose on every frame** — it's only *read* at the few dozen ball-contact events.
- Further speedups (lower `imgsz`, CoreML/ANE, frame striding) trade accuracy or need more work — see tiers below.

---

## Where the time goes

Per-frame cost of the hot paths, measured on real frames from `video_entreno_4.mp4`:

| Stage | Config today | CPU @1280 | MPS @1280 | CPU @640 |
|---|---|--:|--:|--:|
| Player YOLO (`yolov8n.pt`, person) | CPU, `imgsz=1280` | **91 ms** | 37 ms | 26 ms |
| Ball YOLO (`volleyball_ball_best.pt`) | CPU, auto `imgsz=1280` | **88 ms** | 54 ms | 24 ms |
| MediaPipe pose | CPU runtime, ~5 players/frame | **~41 ms** | n/a (CPU-only) | n/a |
| **Total detection + pose** | | **~220 ms** | ~132 ms | ~51 ms |

- 408 frames × ~220 ms ≈ **90 s** — i.e. detection+pose is ~90% of the 100 s wall time. The rest (~10 s) is model load, tracking, game-state, CSV, and video decode.
- Both detectors process the **full 1920×1080 frame**. `imgsz` dominates cost (it scales ~quadratically): 1280→640 is ~3.5× faster per pass.
- **MediaPipe pose does not use the GPU** — it has its own runtime. The only way to cut it is to call it less often (see Proposal 2).

### Two structural facts worth knowing

- **`frame_skip` is dead config.** `Config.DEFAULT_CONFIG["frame_skip"]` exists but is never read — the `VideoProcessor` loop processes every frame. (See [config.py:61](src/utils/config.py:61); no consumer in `src/`.)
- **Pose is computed eagerly, consumed lazily.** [`ActionClassifier.classify_actions`](src/recognition/action_classifier.py:132) calls `estimate_poses_batch(...)` for **all tracked players on every frame** to fill a history buffer, but pose is only ever *read* at confirmed ball contacts (a few dozen per video), and only for the **player closest to the ball**. ~95%+ of pose compute is discarded.

---

## Proposals

Ranked by value ÷ effort. Impact = projected wall time for `video_entreno_4.mp4`
(holding the ~10 s of non-detection overhead fixed).

| # | Proposal | Effort | Accuracy risk | Projected wall | Speedup |
|---|---|---|---|--:|--:|
| 1 | Run YOLO on **MPS** (Apple GPU) | Low | None | ~64 s | 1.6× |
| 2 | **Defer pose** to contacts (or closest-player-only) | Med | None → Low | combines → ~48 s | +0.5× |
| 3 | Lower **player `imgsz`** 1280→960 | Low (tunable) | Medium — validate | ~46 s | small |
| 4 | **FP16** (`half=True`) on MPS | Low | Low | marginal | ~1.1× |
| 5 | **CoreML export → Apple Neural Engine** | Med–High | Needs parity check | potentially ~30–35 s | up to ~3× |
| 6 | Implement **frame striding** (`frame_skip`) | Med | High — retune contacts | ~50 s @ stride 2 | ~2× |
| 7 | **Batched** YOLO inference | High | None | modest on MPS | ~1.1–1.3× |
| 8 | Fix redundant **BGR→RGB** in player detector | Trivial | Improves accuracy | negligible | — |

> Proposals 1 + 2 stack to **~48 s (~2.1×)** with no accuracy change and are the recommended first step.

---

### Tier 1 — Do first (low risk, high value)

#### 1. Run the detectors on MPS (Apple GPU)

> **✅ Implemented.** `make run` now defaults to `--device auto` (→ MPS on Apple Silicon).
> Measured on `video_entreno_4.mp4`: **100 s → 57 s (1.75×)**. MPS is deterministic
> run-to-run, but its detections differ slightly from CPU at action-classification
> boundaries (same *total* action count on v4, different dig/set/spike attribution).
> Pass **`--device cpu`** to reproduce exact CPU numbers for eval baselines.

The machine has Metal/MPS available and built, but the pipeline never uses it: the default
device is `"cpu"` ([config.py:20](src/utils/config.py:20)) and `Config.validate()` **rejects**
anything other than `cpu`/`cuda` ([config.py:365](src/utils/config.py:365)). Both detectors
only check for CUDA and otherwise fall back to CPU
([ball_detector.py:105](src/detection/ball_detector.py:105),
[player_detector.py:63](src/detection/player_detector.py:63)).

**Measured:** player 91→37 ms, ball 88→54 ms per frame. Combined detection ~179→~91 ms (~2×).

**Changes:**
- Allow `"mps"` in `Config.validate()`'s device check.
- In both detectors' `load_model()`, add an MPS branch:
  `elif self.device == "mps" and torch.backends.mps.is_available(): self._model.to("mps")`.
- In `main.py`, auto-select the best device when the config is left at the `"cpu"` default:
  prefer `cuda` → `mps` → `cpu`. (Keep an explicit `--device`/config override so CPU stays reachable for parity checks.)

**Caveats:** MediaPipe pose is unaffected (own runtime). Verify detection parity vs. a CPU run —
ultralytics occasionally falls back to CPU for a few ops on MPS, and results can differ by a
hair. Run `scripts/evaluate.py` before/after (see *Validation*).

#### 2. Stop running pose on every frame

Pose is computed for every player every frame but only consumed at contacts, for the closest
player. Two options, smallest-change first:

- **(a) Closest-player-only + skip when no ball (cheap, very safe).** Compute pose only for the
  player nearest the tracked ball, and skip pose entirely on frames where the ball tracker
  returns `None`. Cuts ~5 pose calls/frame down to ~1 (or 0). Saves ~30–40 ms/frame.
- **(b) Defer to contacts (bigger win).** Keep a rolling buffer of recent frames (or player
  crops) keyed by frame index instead of eager pose. When a contact is confirmed
  (`CONTACT_DELAY=7` frames later), compute pose on demand for the closest player over the small
  window `[F−NEIGH, F+NEIGH]`. Cuts pose calls from *players × frames* (~2000) to *~contacts ×
  small window* (~a few hundred). Saves ~40 ms/frame; amortizes to ~0.

**Accuracy:** Option (a) is behavior-preserving for the gesture logic (it only ever reads the
closest player's pose). Option (b) needs care: MediaPipe's temporal smoothing
(`static_image_mode=False`, [pose_estimator.py:43](src/recognition/pose_estimator.py:43)) relies
on consecutive calls; computing pose over a short consecutive window around each contact preserves
local smoothing. Memory cost of buffering ~14×1080p BGR frames ≈ 90 MB (or store downscaled
crops).

Combined with Proposal 1: (37 + 54 + ~2) ≈ **93 ms/frame → ~48 s wall (~2.1×)**.

---

### Tier 2 — Tunable, validate against ground truth

#### 3. Lower the player detector `imgsz` (1280 → 960)

`player_imgsz=1280` exists specifically to recover small, backlit far-side players
([player_detector.py:48](src/detection/player_detector.py:48); the entreno-3 tracking notes call
recall/`imgsz` the bottleneck). 640 is ~3.5× faster but drops far-player recall. **960 is a
middle ground** (~1.5× faster than 1280) — worth an A/B against `scripts/evaluate.py`.

- **Keep the ball detector at ~1280.** The ball model was fine-tuned at `imgsz=1280` and the ball
  is tiny; dropping it will hurt ball recall badly. Leave `ball_detector` auto-`imgsz` alone.

#### 4. FP16 half precision on MPS

Pass `half=True` to the YOLO call (or export half weights) when running on MPS. Small,
low-risk speedup on top of Proposal 1. Verify no detection regression.

---

### Tier 3 — Bigger swings / more engineering

#### 5. Export to CoreML and target the Apple Neural Engine (ANE)

`yolov8n` is small and a great fit for the ANE. Export once with
`YOLO('...').export(format='coreml')`, then load the `.mlpackage` through the same `YOLO(...)`
wrapper. The ANE can beat both CPU and MPS for these models and offloads the CPU/GPU entirely.
**Potentially the largest single lever** (detectors could drop to ~15–25 ms each → ~30–35 s wall),
but requires an export step, a load path, and a **parity check** (CoreML quantization can shift
detections). Treat as an experiment with a before/after eval.

#### 6. Implement frame striding (`frame_skip`)

Wire the existing-but-dead `frame_skip` into the `VideoProcessor` loop. Stride 2 ≈ halves cost.
**High accuracy risk:** contact detection reads the ball arc at 30 fps and its thresholds are in
frame units (`MIN_CONTACT_GAP=9`, `CONTACT_DELAY=7`, `NEIGH=7` in
[action_classifier.py:48](src/recognition/action_classifier.py:48)). Striding changes the
effective frame rate and would need those retuned, plus re-evaluation. Consider only after Tier 1,
and only if wall time still matters.

#### 7. Batched YOLO inference

Ultralytics can process a list of frames in one call. Requires buffering K frames and threading
results back through the streaming loop. On MPS/CPU the batch win is modest (unlike CUDA), so this
is low priority given the complexity.

---

### Quick hygiene fix

#### 8. Redundant BGR→RGB in the player detector

[`player_detector.detect`](src/detection/player_detector.py:88) calls `preprocess_frame()`, which
does a full-frame `cvtColor(BGR→RGB)` before handing the frame to YOLO — but ultralytics assumes
**BGR** for numpy input (the ball detector correctly passes the frame straight through). This is a
wasted full-frame op **and likely a channel-swap bug** feeding R/B-swapped pixels to the person
model. Passing the frame directly removes the op and probably *improves* player detection. Confirm
with an eval; near-zero perf impact but a free correctness win.

---

## Recommended sequence

1. **Proposal 8** (trivial, correctness bonus) + **Proposal 1** (MPS). → ~64 s, likely *better*
   detections. Run `scripts/evaluate.py` to confirm parity.
2. **Proposal 2a** (closest-player pose), then **2b** (defer to contacts) if you want the full win.
   → ~48 s, no accuracy change.
3. If still too slow: A/B **Proposal 3** (player `imgsz=960`) and **Proposal 4** (FP16) against
   ground truth.
4. Only if wall time is still a blocker: prototype **Proposal 5** (CoreML/ANE) with a strict
   parity check; treat **Proposal 6** (striding) as a last resort due to accuracy retuning.

**Realistic target: ~45–50 s (≈2× faster) with zero accuracy loss** from steps 1–2 alone.

---

## Validation — don't trade accuracy blindly

Every change above (except 8) can move detection/action numbers. Guard each with a before/after:

```bash
# 1. Baseline once (CPU, current settings)
make run VIDEO=resources/video_entreno_4.mp4
python scripts/evaluate.py --predictions output/video_entreno_4/ --ground-truth ground_truth/

# 2. Apply a change, re-run, re-evaluate, compare ball-detection rate,
#    player-ID consistency, and action precision/recall.
```

Ground truth exists for videos 3–6 (`ground_truth/`), and the eval notes already track per-video
action F1 (v4 ≈ 0.92 is the strong case) — use v4 as the accuracy anchor and time it as the speed
anchor.

---

## One-time vs. per-run costs

- **Model loading** (~2–3 s) and MediaPipe warmup happen once per `make run`. They matter for
  short clips but not for the per-frame budget. If you batch many videos in one process, load the
  models once and reuse the `FrameProcessor`.
- The proposals above target the **per-frame** budget, which is where ~90% of the time lives.
