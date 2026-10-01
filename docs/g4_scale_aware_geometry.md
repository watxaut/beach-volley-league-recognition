# Scale-aware (and mirror-aware) contact geometry — REFUTED as the far-serve lever

The owner's call after `docs/g4_far_serve_failure_mode.md`: "lets try scale
aware geometry". Tried, measured, and it does not work — this records why with
numbers, so the next far-serve attempt starts from the real blocker.

**Nothing shipped.** The mechanism lives in `scripts/scale_aware_harness.py` (a
subclass of the production `ActionClassifier`, deliberately outside `src/` per
the refuted-mechanism rule, same pattern as `scripts/serve_mechanism_harness.py`).
Driver: `scripts/probe_scale_aware_geometry.py`. Fidelity is pinned by
`tests/test_scale_aware_geometry.py` (7 tests): the `px` arm **is** production
(it calls `super()`), and the re-implemented scale arm reproduces production
exactly when `k * width` equals each production px constant.

## Arms

* `px` — untouched production geometry (baseline).
* `scale` — every contact threshold as `k × the ball's apparent width` at the
  vertex (`MIN_PROMINENCE` 26 px, `XREV_MIN` 20 px, `DRIVE_DECEL` 8 px/f,
  `DRIVE_XIMPULSE` 12 px/f, `DRIVE_RISE_TOL` 3 px/f, `SERVE_ACCEL_MARGIN_PX` 10 px).
* `mirror` — production + mirrored vertex tests: a far-side serve is hit
  *toward* the camera, so at the contact the ball sits at an image-space
  **peak** (y minimal) and descends on both sides — the mirror of the `bounce`
  shape production looks for. No threshold change can help a test whose
  structural precondition never holds, so this is a separate mechanism.
* `scale+mirror` — both.

Every arm replays the **same recorded ball tracks** the production run produced
(diag dumps from `scripts/probe_far_serve_tracking.py --keep-dumps`), so the
only thing that varies is the geometry.

## Result (17 GT far serves, 16 near-side serves, 24 non-serve control windows, ±15 f)

A hit = a contact fires within ±15 f of the owner frame. In the 24 control
windows (mid-rally **non-serve** GT contacts) any hit is a **false positive**.

| arm | far dev | far held-out | near dev | near held-out | **control FP** | fires invented |
|---|---|---|---|---|---|---|
| `px` (production) | 1/5 | 3/12 | 0/3 | 5/13 | **6/24** | 84 |
| `scale` k=0.3 | 1/5 | **4/12** | 1/3 | 5/13 | **10/24** | 98 |
| `scale+mirror` k=0.3 | 1/5 | 4/12 | 1/3 | 5/13 | **10/24** | 99 |
| `scale` k=0.5 | 1/5 | 3/12 | 0/3 | 5/13 | 7/24 | 83 |
| `scale+mirror` k=0.5 | 1/5 | 3/12 | 0/3 | 5/13 | 7/24 | 83 |
| `scale` k=0.7 / 1.0 | 0/5 | 3/12 | 0/3 | 5/13 | — | 48 (33-window pass) |

Contact-level precision vs the control windows: production **4 hits / 6 FP =
0.40**; `scale` k=0.3 **5 / 10 = 0.33**. So the best arm buys **+1 far contact
(all of it held-out, none on dev) for +4 false positives** — strictly worse
precision. At k = 0.5 it buys nothing at all and still costs a false positive.
The mirror adds nothing measurable on top (its own `far_serve` shape fires in
exactly one window, P23) and, notably, does **not** improve precision either.

For comparison, the G4 evidence path on the same windows: **6 hits / 4 FP =
0.60 precision, 0.35 recall** — better than any geometry arm on *both* axes.

## Why — the multiplier each test would actually need

`probe_far_serve_geometry.py --required-k` prints, per window, the k (in ball
widths) at which each test could fire; `inf` = **no structurally valid vertex
exists**, so no threshold can reach it. Windows with a usable vertex: 9 far, 10
near. (At the near scale production's constants are ≈ k 0.2–0.65 ball widths.)

| test | far: finite k | median k | near: finite k | median k |
|---|---|---|---|---|
| bounce | 3/9 | **8.2** | 7/10 | 4.5 |
| redirect | 4/9 | **2.4** | 4/10 | 1.3 |
| drive decel | 6/9 | ~0.0 (fires on any downward change → free flight) | 7/10 | 0.2 |
| serve fed ascent | 5/9 | ~0.0–0.2 (= 3–6 px: gravity arcs pass) | 4/10 | 0.1 |
| mirrored peak | 3/9 | 0.1 (any lob apex passes) | 7/10 | 0.1 |

Three separate walls, none of them a threshold size:

1. **No ball.** 8 of the 17 far serves have no usable vertex at all (P2, P6,
   P13, P14, P15, P21, P22, P31: 0–1 tracked frames around the contact). No
   geometry can reach them.
2. **Wrong shape / sign.** Where the ball *is* tracked, `bounce` would need a
   threshold of **8.2 ball widths** and `redirect` **2.4** (near-equivalents
   4.5 / 1.3) — i.e. 2–12× looser than production's near-side margin, which is
   not a margin, it is a different measurement. The tests that *can* be reached
   at k ≈ 0 (drive decel, serve fed ascent, mirrored peak) are reached precisely
   because they no longer discriminate: any downward velocity change, any
   gravity arc, any lob apex qualifies. That is the +18% invented contacts.
3. **Wrong actor / wrong label.** Even the contacts that do fire are mostly
   labelled `dig`/`overpass` (measured: P4/P25/P26/P28), because attribution
   picks the nearest *tracked* player and the far server is not one.

## Verdict

Scale-aware geometry is **REFUTED as the far-serve lever** (T5/R1/S1
precedent: refuted mechanisms stay out of `src/`). It is worth +1 held-out
contact and costs +4 false positives; precision 0.40 → 0.33.

The far-serve blocker, in one sentence: **the ball is often absent, and when it
is present its image motion is depth-dominated, so no image-plane shape test —
at any threshold — separates the contact from free flight.** The two remaining
honest routes are therefore not geometry:

* **Depth evidence** — apparent-size growth, i.e. exactly the G4 `far_flight`
  event, consumed post-hoc as evidence (never as a label): measured 6/17 far
  serves at ±15 f (3/12 held-out) with 4/24 control false positives, no `src/`
  change and no near-side regression by construction.
* **Ball presence** — the far ball is seen on 0–1 frames in 8/17 windows. That
  is a detector/temporal question (imgsz, conf floor, per-frame recall at
  15–22 px), not a tracking question.

## Reproduce

```bash
# dumps (the arms only read these; no decode after the first run)
venv/bin/python scripts/probe_far_serve_tracking.py --side far  --keep-dumps output/g4/serve_dumps
venv/bin/python scripts/probe_far_serve_tracking.py --side near --keep-dumps output/g4/serve_dumps
venv/bin/python scripts/probe_far_serve_tracking.py --control  --keep-dumps output/g4/serve_dumps
# the sweep
venv/bin/python scripts/probe_scale_aware_geometry.py --dir output/g4/serve_dumps \
    --arms scale --sweep 0.3,0.5,0.7,1.0 --sweep-arms scale,scale+mirror
# why: the multiplier each test would need
venv/bin/python scripts/probe_far_serve_geometry.py --dir output/g4/serve_dumps --required-k
```
