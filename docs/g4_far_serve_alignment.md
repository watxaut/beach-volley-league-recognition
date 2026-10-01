# Frame alignment on the VFR match: the windowed probes were measuring shifted frames

**Status: measurement defect found and fixed (2026-10-02).** It does not change
any production behaviour; it changes what the G4 far-serve numbers *mean*, and
it produced the seek-free probes that the far-serve work now runs on.

## The defect

`scripts/score_serve_events.py`, `scripts/probe_far_serve_tracking.py` and
`scripts/probe_scale_aware_geometry.py` all position a window with
`cv2.CAP_PROP_POS_FRAMES` and then score events against owner GT frames on the
match frame axis. The 20260920 match is **VFR** (25.67 fps content in a 30.12 fps
container, AGENTS.md §7), and a seek lands on a nearby *keyframe*, not the
requested frame.

Measured by decoding the whole file sequentially once (64x36 grayscale
thumbnails, `output/g4/_seq_thumbs.npy`) and asking, for each seek, which
sequential frame the seeked image actually matches
(`output/g4/seek_offsets.json`):

| requested | actual | offset |
|---|---|---|
| 0 / 120 / 210 | 0 / 120 / 210 | 0 (exact — the method is sound) |
| 880 | 852 | **−28** |
| 1395 | 1401 | +6 |
| 3070 | 3089 | +19 |
| 4801 | 4831 | **+30** |
| 5240 | 5235 | −5 |
| 7132 | 7162 | **+30** |
| 16659 | 16651 | −8 |
| 21344 | 21371 | +27 |
| 25375 / 25435 | 25395 / 25455 | +20 |

**Range −28…+30 frames, mean +8.5** — at ~26 fps that is up to **1.1 s**, and
the contact tolerance every score in this project uses is **±15 f**. The error is
larger than the thing being measured.

## What it invalidates, and what it does not

A window is decoded as a contiguous run after the seek, so *relative* frame
deltas inside a window stay correct; only the mapping to the GT frame axis
shifts by that window's offset. So:

* **Invalid**: any ±15 f hit/miss verdict from a seek-positioned window, and
  therefore the G4 conjunction's "6/17 far serves, 4/24 control false positives,
  precision 0.60" and the candidate offsets "(+2, +2, +2, +7, +9, +15 f)". A
  window with a +20 f seek error reports a candidate that is really ~20 f
  EARLIER than the owner frame — i.e. some of those "hits" are misses and some
  misses are unexplained.
* **Still valid**: the *counts per event type over a 151-frame window*
  (runway 15/17, far flight 16/17 in window) — a ±30 f shift barely moves which
  151 frames are in the window, and the far-side geometry findings
  (`docs/g4_far_serve_failure_mode.md`) are about shapes measured on recorded
  tracks, not about absolute frames.
* **Untouched**: production. `src/` never seeks; `src/main.py` and the live
  debug path decode sequentially, so pipeline outputs and the recorded
  31/33-point match result are unaffected.

## The fix

Two seek-free probes, both decoding the file **once, sequentially**, and scoring
against the true decode index:

| probe | what it replaces |
|---|---|
| `scripts/probe_serve_events_seq.py` | the windowed `score_serve_events.py` runner: one continuous `FrameProcessor` over the whole span (also strictly more production-faithful — the old runner reset the trackers per window) |
| `scripts/probe_far_roi_ball.py` | the M1 magnified-crop probe, which needs a ±15 f window to mean anything |

`tests/test_vfr_seek_guard.py` (3 tests) greps `scripts/`, `src/` and `tests/`
with `ast` — a mention in a docstring is fine, an attribute access is not — and
fails on any new seek site. The exceptions are allow-listed *with a reason* and
the test fails on a stale entry. The audit it produced turned up two real
(non-serve) risks now recorded as allow-list KNOWN ISSUES:

* `scripts/annotate_player_gt.py` — the **owner-GT annotator** can display a
  frame up to ~30 f from the requested one, so a GT contact could be judged off
  its own moment. It wants a sequential-cursor fix before the next annotation
  pass (the owner should know this).
* `src/db/ingest.py` — the player-thumbnail crops for the review UI can be
  taken ~30 f away and miss the player. Cosmetic.

## Reproduce

```bash
venv/bin/python -m pytest tests/test_vfr_seek_guard.py -o addopts="" -q
# the offsets: sequential thumbnail decode, then best-match each seek
venv/bin/python -c "import cv2,numpy as np,json; ..."   # see the table above
```
