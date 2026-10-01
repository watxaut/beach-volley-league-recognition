# Why the far serves are not emitted — and which signal does not switch

Companion to `docs/g4_serve_events.md` (open point G2/G4). Diagnose-only, no
`src/` change: two probes replay the GT-serve windows through the real
`FrameProcessor.process_frame` with the T4 diag dump on
(`scripts/probe_far_serve_tracking.py`) and then re-drive the **production**
`ActionClassifier` with each recorded ball track
(`scripts/probe_far_serve_geometry.py`).

## 0. A bug in the first scoring run, found and fixed

The first G4 numbers were produced with `Config.default()` alone, which leaves
`ball_model_path = None` → the **COCO `yolov8n.pt`**, not the fine-tuned
`models/volleyball_ball_best.pt` that `src/main.py` auto-loads ("the COCO
fallback rarely finds a volleyball on real footage" — main.py's own comment).
Consequence: the *far-flight* and *conjunction* figures were a lower bound
measured on the wrong detector, and the "far ball is detected ~1 frame in 4"
line was a COCO artefact (with the real model the median gap around a far serve
contact is **1 frame**). The runway leg was unaffected (the player detector is
`yolov8n` in both paths). Both probes now go through
`score_serve_events.production_config()`, which performs the same ball-model
wiring as `src/main.py`.

## 1. Where the 17 GT far serves die (window `[c-90, c+60]`, measured at `c ± 15 f`)

| first failing stage | far (17) | near (16, control) |
|---|---|---|
| 1 raw ball detection | 2 | 3 |
| 2 track admission | 5 | 1 |
| 3 contact candidate | **6** | 7 |
| 4 candidate gate | 0 | 1 |
| 6 label (a contact, wrong label) | 4 | 4 |

Probe reasons inside `c ± 15 f`: `no_ball_sighting` 334 (far) / 256 (near),
`no_contact_geometry` **150** / 195, `min_contact_gap` 38 / 39. Tracker reasons:
`unlocked_no_motion` 261 (far) / 199 (near), `locked_admitted` 174 / 212.

**The stage distribution barely differs between the sides.** So the far/near gap
is NOT a stage that is skipped — it is a *threshold* that never reaches.

## 2. The signal that does not switch: contact GEOMETRY

`_normal_contact_at` offers exactly four ways to call a contact. Replaying each
recorded ball track through the production classifier and measuring, at every
usable vertex, how close each test came to its own threshold:

| test | threshold | far serves (P1, P23, P28, P32) | near serves (10 usable windows) |
|---|---|---|---|
| bounce: vertex is the lowest point of ±7 f | — | 0, 0, 2, 0 | 0–4 (most ≥1) |
| bounce: rise on both sides | **≥ 26 px** | **never reachable** | 12, 60, 3, 6, 76, 100, 76 → ≥26 in 5–6/10 |
| redirect: horizontal sign flip, both sides | **≥ 20 px** | **0 flips, best 0 px** | 4–8 flips, best 38–65 px (fires in 3/10) |
| drive: downward-speed cut | **≤ −8 px/f** | −1, +4, −35, −8 | ≤ −8 in 6/10 (down to −43) |
| drive: lateral impulse | **≥ 12 px/f** | 2, 2, 17, 2 | ≥12 in 3/10 (up to 29) |
| **serve branch: fed ascent `|vin3| ≥ |vin6| + 10`** | **≥ 10 px** | **+0, +4, +3, +4 → NEVER** | **+13, +20, +13 → fires in 3/10** |

Example (P23 f16659, ball tracked on 31/31 frames, still no contact):
`bounce: lowest=False`; `vx −14.2 → −14.2` (no flip); `dvy +4…+6` (the ball is
*accelerating downward* in image space — free flight toward the camera);
`pops_up` flips, but `fed_ascent = −1.5 … −2.7 px`, i.e. the toss **decays**
exactly like gravity, which is the branch's designed reject ("e4's pure gravity
arc decelerates 25→1 px/f — refuses everywhere").

**Why**: at the far end the ball's image motion is dominated by **depth** — it
grows and descends as it approaches the lens — while all four thresholds are
near-half-scale constants (AGENTS.md §5: far balls 14–28 px, near 30–55 px,
near-half contacts 25+ px/f). A far serve therefore *looks like free flight* in
the image: no lowest vertex, no lateral reversal, downward acceleration, and a
gravity-decaying toss. This is the same venue/scale-coupling family as the far/near
width band, one stage deeper: **the contact detector is calibrated on near-half
ball scale, and at the far end the contact signal sits below that scale.**

Note the near side is weak too (only ~5/10 windows fire a contact; G1 measures
near serve recall 0.280 vs 0.000) — the far side is not "a different pipeline",
it is the same detector pushed past its scale.

## 3. Two secondary losses, independent of the geometry

1. **The ball is not always there** — 2/17 far serves have zero raw detections
   at `ball_confidence=0.15` inside `c ± 15 f`, and 5/17 never get a locked
   track (`unlocked_no_motion`, `out_of_view_reentry_wait`). Pre-contact tracked
   speed is *not* the blocker where the ball is seen (15–35 px/f, well over the
   tracker's 8 px/f lock floor), so this is a detection/admission-rate problem
   at the far end, not the lock threshold (this refutes the "toss is slower than
   8 px/f" reading of T5 for these 17 contacts).
2. **The actor is the wrong player** — where a candidate IS accepted on the far
   side (P28 f21344–46, P25/P26/P4) the emitted label is `dig`/`overpass`. The
   resolver's `serve` needs behind-baseline + rally-start, and attribution picks
   the nearest **tracked** player — the server is not one, exactly as the owner
   observed. So even a geometrically perfect far contact could not be labelled
   `serve` without the runway occupant becoming an actor (the G4 event, which is
   evidence, not an actor).

## 4. What this implies for the lever

The only far-side cue that *did* show headroom in the measurement is the one the
G4 emitter already computes: **apparent-width growth** (a ball approaching the
camera). It is monocular, needs no toss, and is exactly what free flight cannot
fake — but it is a *depth* cue, and none of the four contact tests looks at
depth. Two honest options, both requiring the owner's ratification before any
`src/` change:

* **scale-aware geometry** — express the thresholds in ball widths (or in the
  local court scale) instead of absolute px, so the far ball's 26 px rise
  becomes ~0.8 bw instead of unreachable. Needs its own A/B on the near side
  (which must not regress) plus the non-serve control windows.
* **consume the G4 events** — `serve_candidate` places the far contact from
  evidence (runway occupant + ball + far flight) without asking the shape tests
  to fire. This is the AGENTS.md §6 post-hoc path; it must be consumed as
  evidence, never as a label source (pass-2 proved the label route: 0/5 far
  serves, 3 correct dig labels broken).

## Reproduce

```bash
venv/bin/python scripts/probe_far_serve_tracking.py --side far   # stage waterfall per far serve
venv/bin/python scripts/probe_far_serve_tracking.py --side near  # the control
venv/bin/python scripts/probe_far_serve_geometry.py --dir output/g4/far_serve_dumps
```
