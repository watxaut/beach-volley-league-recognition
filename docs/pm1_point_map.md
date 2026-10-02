# PM1 — the point-map probe: is the far-serve record a one-rule job, or is it blocked on open point 22?

Card PM1 (STATUS.md *## Next task cards*), open point 30. Probe:
`scripts/probe_point_map.py`. Pins: `tests/test_point_map.py`. Long report:
`logs/pm1_report.md`. Raw tables: `logs/pm1_probe_stdout.txt`,
`output/pm1/probe.json`.

**VERDICT: `FAIL=blocked`.** SR4-FAR is **BLOCKED on open point 22**
(the episode→point map). The three numbers that decide it:

| pre-registered condition | required | measured |
|---|---|---|
| UNBOUND (frame, side) far hits | ≥ 15 of 17 | **16 of 17** ✔ |
| UNBOUND new false serves | ≤ 0 | **294** ✘ |
| best binding rule far hits / false positives | ≥ 12 of 17 and ≤ 3 | **11 of 17 with 35** (rule iii); rule (ii) 16 of 17 with **288** ✘ |

Neither the bypass nor any of the three binding rules clears its bar, so per the
card the point-map question is answered **blocked**. The lever the evidence points
at is the **point map**, not the binding rule — see §4.

Every claim below is marked **[measured]** (read off the committed artifacts by
`scripts/probe_point_map.py`) or **[inferred]** (a reading of
`src/analysis/game_state_manager.py`). Counts only, never rates.

Sources, unchanged and unstale: `output/20260920_match_ari_joan_lost/pipeline_output.json`
(207 actions, 31 `game_state.points`, 578 `far_flight` events of which 432 are
narrow at the 28 px cut, commit `133d87c`, 2026-10-01) and
`ground_truth/20260920_match_contacts.json` (33 serve contacts, far 17 / near 16,
tolerance 15 f). **No decode, no seek, no `src/` change, held-out session never
read** (AGENTS.md §6, §9).

## Gates

* **G1 (baseline reproduction) — PASS.** [measured] `score_serves.py --detail`
  still reads near **8/16**, far **0/17**, **12** false serves, and the scorer's
  own pre-registered gate passes.
* **G2 (width plateau, re-derived) — PASS.** [measured] `far_flight.width_start`
  at the far serves: **16–27 px** (16 of 17 far serves have an event at all; P31
  f24543 has none). At the near serves only 3 have an event and they sit far
  above: P12 **39 px**, P18 **50 px**, P24 **48 px**. Every cut in 26/28/30/32
  claims **16 far, 0 near**. The plateau is real and the side signal is
  camera-scale-coupled exactly as #63 warned; the cut used below is the card's
  FIXED 28 px.

## 1. Where each GT serve sits relative to the pipeline point map

[measured] **16 of 33** serves fall inside *some* pipeline window — but they are
overwhelmingly the near ones: **far 2 of 17** (only P23 and P25), **near 14 of
16**. Every single serve falls inside its own GT point's implied window (serve …
next GT serve): **33 of 33**.

Ordinal pairing (GT point *P* ↔ pipeline point *P−1*, the only pairing available
because the two vocabularies are different things) **[measured]**:

* **0 of 17 far serves fall inside their own point window** — the #63 root cause,
  reproduced exactly (P32/P33 have no pipeline point at all: the 31-vs-33
  shortfall). Nothing does: **0 of 31** aligned windows contain their own serve.
* The offset `pipeline start_frame − own serve_frame` is **one-signed on all 31
  aligned pairs: +6 f to +3153 f**. The architect's "−1 to −1466 f" is the
  *nearest-window* offset in the other direction (the card's step-1b signed
  offset, whose extreme is −731 f at P32); the ordinal-pairing offset, which is
  the one that decides whether a window holds its own serve, runs **+6 … +3153 f**.
* By the alternative reading (first point whose `start_frame` is after the
  serve — binding rule (ii)) the offset is **+1 … +995 f** on the 17 far serves:
  one-signed, always forward. [measured]

Per-serve table (full version in `logs/pm1_probe_stdout.txt`):

| P | serve f | side | nearest window | start−serve | in any window | own GT window | inside own GT window |
|---|---|---|---|---|---|---|---|
| 1 | 210 | far | [216, 495] | +6 | no | [210, 879] | yes |
| 2 | 880 | far | [216, 495] | −664 | no | [880, 1394] | yes |
| 3 | 1395 | near | [1376, 1674] | −19 | yes | [1395, 2153] | yes |
| 4 | 2154 | far | [2404, 2684] | +250 | no | [2154, 2574] | yes |
| 5 | 2575 | near | [2404, 2684] | −171 | yes | [2575, 3037] | yes |
| 6 | 3038 | far | [3042, 3264] | +4 | no | [3038, 3746] | yes |
| 7 | 3747 | near | [3729, 4073] | −18 | yes | [3747, 4769] | yes |
| 8 | 4770 | far | [4790, 5119] | +20 | no | [4770, 5495] | yes |
| 9 | 5496 | near | [5480, 5581] | −16 | yes | [5496, 6034] | yes |
| 10 | 6035 | near | [6017, 6556] | −18 | yes | [6035, 7146] | yes |
| 11 | 7147 | near | [7115, 7354] | −32 | yes | [7147, 7776] | yes |
| 12 | 7777 | near | [7115, 7354] | −662 | no | [7777, 8505] | yes |
| 13 | 8506 | far | [8573, 8667] | +67 | no | [8506, 9102] | yes |
| 14 | 9103 | far | [9108, 9293] | +5 | no | [9103, 10043] | yes |
| 15 | 10044 | far | [10045, 10394] | +1 | no | [10044, 10540] | yes |
| 16 | 10541 | near | [10524, 10879] | −17 | yes | [10541, 11411] | yes |
| 17 | 11412 | near | [11393, 11514] | −19 | yes | [11412, 11994] | yes |
| 18 | 11995 | near | [11981, 12583] | −14 | yes | [11995, 13073] | yes |
| 19 | 13074 | near | [13059, 13781] | −15 | yes | [13074, 14517] | yes |
| 20 | 14518 | near | [15148, 15336] | +630 | no | [14518, 15144] | yes |
| 21 | 15145 | far | [15148, 15336] | +3 | no | [15145, 15924] | yes |
| 22 | 15925 | far | [15926, 16209] | +1 | no | [15925, 16658] | yes |
| 23 | 16659 | far | [16653, 16930] | −6 | **yes** | [16659, 18134] | yes |
| 24 | 18135 | near | [18125, 18409] | −10 | yes | [18135, 18839] | yes |
| 25 | 18840 | far | [18839, 19473] | −1 | **yes** | [18840, 19831] | yes |
| 26 | 19832 | far | [19835, 20278] | +3 | no | [19832, 20921] | yes |
| 27 | 20922 | far | [20923, 21108] | +1 | no | [20922, 21355] | yes |
| 28 | 21356 | far | [21359, 21511] | +3 | no | [21356, 22149] | yes |
| 29 | 22150 | near | [22133, 22408] | −17 | yes | [22150, 22873] | yes |
| 30 | 22874 | near | [22857, 23620] | −17 | yes | [22874, 24542] | yes |
| 31 | 24543 | far | [24644, 25037] | +101 | no | [24543, 25374] | yes |
| 32 | 25375 | far | [24644, 25037] | −731 | no | [25375, 25806] | yes |
| 33 | 25807 | near | [25776, 25959] | −31 | yes | [25807, 26060] | yes |

[measured] Side by side, pipeline point *i* against GT point *i+1* (all 31 rows in
the stdout; summary): the pipeline window **starts after the whole of the GT
point** in the 12 rows where the bound window contains the GT point's own contact
set, and lands somewhere in the *following* point otherwise; no aligned window
starts before its own serve.

[measured] Inter-point gaps: 29 of 30 gaps reach `GAP_SERVE_MIN` (143, imported),
one does not (idx 12, gap 130). **14 of 30 gaps hold at least one GT serve, and
16 of 33 serves sit in a gap** — the serves are *between* the pipeline's points,
not inside them.

## 2. The bypass test

Unbound records are `(frame, side)` only, built through the scorer's own
`serve_record_candidates`, one per `far_flight` with `width_start <= 28`
(the card's fixed cut). Scored with the scorer's own `match_candidates` and
`classify_false_positives`; **false serves** = `rally_contact_mislabeled` +
`serve_outside_tolerance` (a record in dead time is not a false *serve*; both
are reported).

| form | records | far hits | near hits | unmatched | false serves | points covered |
|---|---|---|---|---|---|---|
| UNBOUND (frame, side) | 432 | **16/17** | 0/16 | 416 | **294** | — |
| (i) bind: window CONTAINS | 281 | 10/17 | 0/16 | 271 | 253 | 29 |
| (ii) bind: first `start_frame` after | 426 | **16/17** | 0/16 | 410 | **288** | 30 |
| (iii) bind: gap `[prev_end, start]` of (ii) | 149 | 11/17 | 0/16 | 138 | 35 | 25 |

Sensitivity (decides nothing, reported per the card): unbound far hits are
**16/17 at every cut** 26 / 28 / 30 / 32, with records 391 / 432 / 456 / 473 and
false serves 259 / 294 / 312 / 321. The bypass loses nothing by being unbound —
it loses only by having no way to drop the 416 records it does not need.

## 3. Reading: does `_finalize_group`'s backdating explain both the count and the offsets?

`src/analysis/game_state_manager.py` (read only, never changed): a rally group is
the merged span of consecutive flight episodes; `_finalize_group` splits it at
contact silences longer than `contact_chain_frames` and keeps a piece only when
it holds ≥ `point_min_actions` classifier actions. The **episode onset is
backdated to the flight burst start** after ≥ `arm_quiet_frames` of quiet, which
is a serve-like retrieval-and-toss pattern — so the onset that opens a point is,
by construction, an *earlier* flight burst than the rally the point contains.

[measured] The consequence is visible in the tables: on the ordinal pairing every
window starts **after** its own serve (0 of 31) and, for the 12 rows where the
window does contain the whole GT contact set, the window is *offset by roughly a
full point*: e.g. idx 17 `[15148, 15336]` opens 630 f after P20's serve f14518 and
3153 f after P18's f11995. [inferred] The point map therefore answers "when did
the *ball* next fly in a burst long enough to confirm", not "when did this point
start". A serve is a 0–30 f contact at the head of a point, and the map's opener
is the burst **before** it. That single mechanism accounts for both observations:
the offsets (+6 … +3153 f, one-signed) and the fact that the window body still
covers the point's own contacts 12 times out of 33 — [measured] the map is not
randomly placed, it is *late but real*, which is why rule (ii) keeps all 16 far
hits and why "first start after" is the most generous binding available.

[measured] The 31-vs-33 shortfall: GT P32 (f25375) and P33 (f25807) have no
pipeline point of their own; both fall inside the window of pipeline point 30
`[25776, 25959]`'s predecessor span or its gap. [inferred] Two mechanisms are
plausible and PM1 does not separate them: (a) the last two rallies were short
enough in emitted actions to fall below `point_min_actions`, or (b) they were
merged into the preceding group and then split at a contact silence whose first
piece kept the merged start. Both are `game_state_manager` behaviours, both live
in open point 22, and neither is decided here. [measured] What is *not* the cause:
the far-side blindness — the point layer never sees serves, it sees flight
bursts and classifier actions, and 87 of the 33 points' worth of serves sit in
plain sight of the layer without being claimed.

## 4. Which lever the evidence points at

[measured] Rule (ii) "first `start_frame` after the event" keeps the full **16/17**
far hits — proof that the point map, read as an ordering rather than as windows,
is sufficient to *carry* every far serve record — but it cannot reject anything:
288 false serves. Rule (iii), the gap `[prev_end, start]`, is the only rule that
rejects meaningfully (**149** records, 35 false serves) and it costs far hits
(16 → 11), because 5 of the 17 far serves are *inside* a point window rather
than in a gap. [inferred] So: **the binding rule is not the lever** — the best of
the three trades hits for false positives at roughly 1:4 and none reaches the
bar — **the point map is.** A map whose window opens *at the serve* would make
rule (i) the natural rule and would put the serve in a window instead of a gap,
which is the only configuration in which a per-point record can be both
complete and precise. The unbound form proves the *signal* is complete (16/17);
nothing about the signal needs fixing, only where the point is said to begin.

## 5. Consequence for the plan

* **SR4-FAR is BLOCKED on open point 22.** No card is written for it; per the
  card's own rule, a fourth binding rule, a width-threshold change or a
  tolerance change is out of scope and was not tried.
* **The width plateau survives as a Learning** (already recorded from #63): far
  onsets 16–27 px, near onsets 39–50 px, any cut in 26–32 gives 16 far claimed /
  0 near misclaimed — but it is a *detection* result; turning it into a record
  needs the map.
* **Open point 22 gains a measured constraint:** the fix must move the point
  opener to the serve (or to the rally it belongs to), because the current opener
  is *uniformly late* (+6 … +3153 f, one-signed on 31 of 31 aligned pairs) and
  the serves sit in inter-point gaps (16 of 33) or, for the near side, in
  windows (14 of 16) — the two populations need different handling, and the far
  side is the one the gaps describe.

Test status: `venv/bin/python -m pytest tests/ -o addopts="" -q` → **1214 passed**
(1191 before this card + 23 new in `tests/test_point_map.py`).