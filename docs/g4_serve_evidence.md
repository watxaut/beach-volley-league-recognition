# S4 -- the serve evidence consumed: what the layer delivers, and what it does not

Session 54. The owner approved the recommended operating point (the 14/17 union
of the gated conjunction and the structural arm, consumed post-hoc). This
records what was built, what it measures on the real production artifact, and
the one thing it does **not** yet do.

## What shipped

| piece | where | state |
|---|---|---|
| structural arm | `ServeContactProposer` in `src/analysis/serve_events.py` | inside the `--serve-events` envelope, `serve_structural_*` config keys, 12 unit tests |
| S4 consumer | `scripts/consume_serve_evidence.py` | pass 2, writes `output/serve_evidence.json` and nothing else |
| inertness proof | `scripts/probe_serve_events_inertness.py` | action streams byte-identical with the emitters ON vs OFF |
| tests | `tests/test_serve_evidence_consumer.py` (25), `tests/test_vfr_seek_guard.py` | suite **1036** |

The production artifact the consumer reads came from a real run, not a probe:

```bash
venv/bin/python -m src.main resources/full_videos/20260920_match_ari_joan_lost.mp4 \
    --output-dir output/20260920_match_ari_joan_lost --skip-visualization --serve-events
# 26 061 frames, 33 min on MPS
# serve events: runway_occupant 395, far_flight 578, serve_candidate 443, serve_contact 60
venv/bin/python scripts/consume_serve_evidence.py
```

**Inertness, measured** (`--from 1900 --to 2300`, CPU, one sequential decode
into two processors): actions OFF 1 / ON 1, **byte-identical**, no
`serve_events` key with the emitters off, 20 serve events with them on. The
observers add a key and nothing else.

## The two numbers, kept apart on purpose

| measure | value | what it means |
|---|---|---|
| **evidence coverage** (anchored) | **14/17** GT far serves have a record within ±15 f | the mechanism fires where the serve is |
| **binding** (what a consumer gets) | **9/17** (dev **5/5**, held-out **4/12**) | the record the pipeline picks *without* knowing the answer |
| owner FALSE/OFFGAME false positives | **1** (f5121, "ball handling after the point ended") -> precision **0.90** | 87 records over the whole match, one of them in an owner-declared non-serve moment |
| points with a serve record | 19/33 | and 7 of them are in points the structural map calls NEAR-served, which this layer cannot observe (reported, never consumed) |

This is the same shape as the G1 miss taxonomy: *the signal is there, the
interpretation is the loss.* The action stream has 0/17 far serves; the evidence
has 14/17; the honest consumer binds 9/17. Reporting only the 14/17 would be
the mistake G1 was written to prevent.

## Why binding loses five, diagnosed

A dead-time episode holds three kinds of record and the emitted stream only says
"a rally contact follows":

1. **the walk to the serve line** (the owner's FALSE list: "walking to the serve
   line with the ball in her hands", "the throw from one near player to the
   server") -- hundreds of frames before the reception;
2. **the serve** -- the last contact before the rally, so the next emitted
   action follows within a flight;
3. **the echo** -- the ball still inside the server's bbox a few frames AFTER
   the hit (P8 f4796, 5 f before the reception, against the serve's own record at
   f4762).

`select_serve` takes the record closest to the reception that is at least
`min_next_gap = 20` frames from it, which removes the echo and the walk. The
sensitivity sweep ships in the artifact:

| min_next_gap | 0 | 5 | 10 | 15 | **20** | 30 | 40 | 60 |
|---|---|---|---|---|---|---|---|---|
| far serves bound | 5/17 | 7 | 8 | 9 | **9** | 6 | 4 | 1 |

Flat over 15-20 f, so the one constant is not balanced on a knife edge. The
five misses:

* **P14, P22, P23 -- no record near the serve at all** (the closest is 117, 187
  and nothing). The evidence gap, not the binding.
* **P28, P31 -- a second record 8-19 f from the contact** (P28: 21274 vs 21375
  for a 21356 serve; P31: 24535 vs 24648 for 24543). Both readings are within a
  frame or two of defensible and nothing in the emitted stream says which side of
  the contact the ball is on.

**The missing ingredient is already measured and unused: the net crossing.** A
served ball crosses the calibrated net line toward the camera, so "the record
that is immediately followed by a crossing" resolves cases 4 and 5 exactly. The
578 `far_flight` events carry the width growth that precedes it. That is the next
session's lever, and it is a post-hoc computation over the existing artifact --
no re-decode.

## Two design decisions worth keeping

* **Binding by dead-time episode, not by the pass-2 point window.** The first
  version bound records to the point windows from `output/serve_relabel.json` and
  scored 8/17 with four of the misses being windows that do not contain their own
  serve -- the episode map's windows are PREDICTIONS (12/25 cover their own
  contact range, STATUS Learnings). The emitted contacts are not predictions, and
  they already partition the video into dead-time episodes; binding through them
  removed the window failure class entirely and is what the 9/17 is measured on.
* **The GT is validate-only.** `output/serve_evidence.json` carries a
  `validation` block (coverage, the owner false positives, the selector sweep)
  and nothing derived from GT enters a record. The disclaimer field states the
  contract a consumer must honour: `frame` is an estimate, `sources` is the
  confidence signal (21 of the 87 records have both arms agreeing), and NEAR
  serves are not observed by this layer at all.

## Reproduce

```bash
venv/bin/python scripts/probe_serve_events_inertness.py --from 1900 --to 2300
venv/bin/python scripts/consume_serve_evidence.py --validate-only
venv/bin/python -m pytest tests/test_serve_evidence_consumer.py -o addopts="" -q
```
