# M3' -- the structural far-serve contact: measured frontier and operating points

Session 53. The owner's question was "what can we do to **reliably** get
serves", after T5 (tracker admission), R1 (departure gate), S1 (looming) and
scale-aware geometry were all refuted. This records the three checks run in the
order they were proposed, and the operating-point table the decision needs.

Everything is measured on ONE seek-free sequential pass of the 20260920 match
(`scripts/probe_serve_events_seq.py`, 25 316 frames, 200 emitted contacts,
artifact `output/g4/serve_events_seq_recording.json`), which also produced two
corrections to the record:

* **the G4 event score was mis-measured** -- windowed probes seek, and a seek on
  this VFR file lands −28…+30 f from the requested frame
  (`docs/g4_far_serve_alignment.md`). Seek-free, the G4 conjunction scores
  **11/17 far serves, not 6/17**, and the control false positives are 8/24, not
  4/24. The candidate offsets are systematically **negative** (−1…−14 f).
* **the far ball is not missing** -- the detector sees it in 14-31 of 31 frames
  at every serve except P31 f24543 (`docs/g4_far_ball_presence.md`). The
  "0-1 tracked frames in 8/17 windows" line is a *tracker* statement.

## 1. M2 -- the opener gate: a strict win

A serve opens a rally, so a candidate only counts when no contact was emitted in
the preceding N frames. The match already guarantees the separation: openers
follow ≥153 f of dead time, the largest mid-rally gap is 134 f
(`GAP_SERVE_MIN=143`, session 28).

| gate (f) | far serves hit ±15 f | control FPs | precision | recall |
|---|---|---|---|---|
| none | 11/17 | 8/24 | 0.579 | 0.647 |
| 30 | 11 | 4 | 0.733 | 0.647 |
| **60 – 240** | **11** | **0** | **1.000** | 0.647 |
| 400 | 11 | 0 | 1.000 | 0.647 |

Every control false positive sits at a gap of 2–58 f and every true hit at
231–816 f, so the plateau is 60–240 f wide: **not a knife-edge fit**, and MPS/CPU
label jitter cannot flip it. The same gate with `game_state == GAME_OFF` gives
identical numbers (11/17, 0/24).

Cost: one comparison against the classifier's last-contact frame, inside the
emitter that already exists.

## 2. M1 -- the magnified far-end pass: refuted, and it corrects the diagnosis

Run the same production weights on a 4x-magnified square crop of the far band
(3 tiles of 320 px, tile geometry from the 8 calibration clicks).
**0 of 17 windows were empty for the full-frame arm**, so the premise ("the far
ball is too small to detect") is false; the tiles recover only P31 (2/31 → 26/31)
at +104.8 ms/frame for 3 tiles, and their median detection is 3.2 px of
unscaled sand/line noise. Parked as a possible P31-class fallback; not built.

## 3. M3' -- structural proposer: the frontier

Rule: *no emitted contact in 143 f* + *a person in the far band* + *a far-side
ball-sized (8-60 px) raw detection within 30 f* + *the ball within R bbox heights
of that person* → contact placed at that sighting (bias 0). No tracker, no shape
geometry, so it is immune to both walls the earlier levers hit.

Negative sets: 24 mid-rally non-serve contacts (a fire is an FP by
construction) and the **9 owner FALSE / OFFGAME moments** -- a player with a
ball in dead time, i.e. the same physical situation minus the toss and the hit.

| occupant region | reach (bbox heights) | hits ±15 f | dev / held-out | mid-rally FP | owner FP | precision |
|---|---|---|---|---|---|---|
| runway only | 0.5 | 9/17 | | 0 | 0 | 1.00 |
| runway only | 1.0 | 10/17 | | 0 | 0 | 1.00 |
| **runway only** | **1.5 – 4.0** | **11/17** | 3 / 8 | 0 | **0** | **1.00** |
| runway + court | 0.5 | 14/17 | | 0 | 1 | 0.93 |
| **runway + court** | **1.0** | **15/17** | 4 / 11 | 0 | **1** | **0.94** |
| runway + court | 1.5 | 16/17 | | 0 | 2 | 0.89 |
| runway + court | 2.5 | 17/17 | | 0 | 2 | 0.90 |

* pre-registered **K1 (≥12/17)**: met at reach 1.0 with runway+court (15/17);
* **K2 (≤3/24 mid-rally, ≤2/10 owner FP)**: met everywhere in the table;
* **K3 (systematic timing)**: offsets −8…+0, median |offset| **1 f** -- an order
  of magnitude tighter than the G4 conjunction's −9 f median.

The two zero-FP rules fail on *different* windows, so they compose:

| rule | hits | notes |
|---|---|---|
| G4 conjunction + opener gate | 11/17 | 5 dev / 6 held-out, median offset −9 f |
| structural, runway, reach 1.5 | 11/17 | 3 dev / 8 held-out, median offset 1 f |
| **union of the two** | **14/17** | **0 FP of any kind** |
| structural, runway+court, reach 1.0 | 15/17 | 1 owner FP: f5130 "ball handling after the point ended" |
| structural, runway+court, reach 2.5 | 17/17 | 2 owner FPs: f5130 and f2414 "walking to the serve line with the ball in hands" |

Production today: **0/17** far serves at contact level. So every row above is a
gain of 11-17 contacts.

## 4. What the two owner false positives mean

Both are *pre-serve ball handling* in dead time, and both are inside the same
opening gap as a real serve, so no dead-time test can separate them. The only
thing that separates a serve from a handled ball is the **toss plus a hit
toward the camera**, and in the far half that signature is exactly what the
contact-geometry probe refuses (the far toss decays like gravity). The sweep
confirms the trade honestly: every discriminator tight enough to reject them
(`grow`, apparent-width growth) also throws away real serves (7/17), while the
loose ones admit them.

**Therefore: pick the operating point by what the consumer needs.**

* **Post-hoc serve EVIDENCE (recommended, AGENTS.md §6) -- 14/17 at precision
  1.00.** A record with a ±1-9 f frame, the far-side server (the occupant's
  box), and `confidence: evidence`. It unblocks the G1/G2 path (who served, aces,
  serve faults) for 14 of 17 far serves with **zero** false positives on 33
  negative windows, and the 3 misses are visible as absences rather than
  inventions.
* **Single-rule 15/17 at precision 0.94** if one rule is preferred over a union
  (4 dev / 11 held-out, median |offset| 1 f, one owner FP at f5130).
* **17/17 at 0.90** is available but I do not recommend it: both FPs are
  pre-serve handlings, and f2414-style moments are what a serve *looks* like
  before the hit, so the error mode is systematic rather than random.

## 5. What this does NOT fix

* The action stream is untouched: nothing here writes a `serve` into
  `events`/CSV. Per AGENTS.md §6 and the S0b lesson (pass-2 relabeling broke 3
  correct dig labels), this stays an **evidence record consumed post-hoc**.
* No player identity: the occupant is a raw detection, not one of the 4 tracks,
  so the server is "the far-side person at the far line", not `player_id`. Squad
  attribution comes from the winner-of-previous-point rule (6/6 cross-checked).
* The near side is untouched by construction (the band is on the far side), and
  the 33 mid-rally/owner negatives already include near-side moments.
* P31 f24543 (the slow float) needs the M1 magnified pass, or nothing: the
  detector sees the ball on 2 of 31 frames there.

## Reproduce

```bash
# the seek-free pass (MPS, ~30 min; writes the raw recording the sweep needs)
venv/bin/python scripts/probe_serve_events_seq.py --device mps
# the frontier
venv/bin/python scripts/sweep_structural_serve.py --min-precision 1.0
# the two refuted/one-pass probes
venv/bin/python scripts/probe_far_roi_ball.py --device mps
venv/bin/python -m pytest tests/test_structural_serve_rule.py tests/test_vfr_seek_guard.py \
    -o addopts="" -q
```
