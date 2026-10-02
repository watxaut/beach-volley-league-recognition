# SR1d — the cost of lifting the 90 f off-court hold horizon (session 61, 2026-10-02)

Measure-only, **no `src/` change**: what does `player_off_court_hold_frames`
= 100000 cost, on the seven entreno drills and on the full match? Open point
**30**, mechanism **M-b** (a serve-zone exemption from the hold), which is the
candidate fix for the P5/P7 near serves.

**Verdict: `global lift REFUTED`** — the expected outcome. Near-serve recall
does not move (8/16 both arms), the e2 sideline bystander is fed *longer*, and
the cost is concrete: +2 false serves, +5 actions, and a net zero that is two
opposite trades cancelling.

Artifacts (all git-ignored, `output/sr1d/`): `hold_off.yaml`, the 14 runs under
`hold_off/` and `base/` with their diag dumps, `eval_fixed.log`,
`e2_bystander.json`, `match_arm_scores.json`, and the three one-off scripts
(`make_eval_predictions.py`, `e2_bystander.py`, `score_match_arms.py`).

## 1. Method, and one fix the owner authorised

`src/utils/config.py:362` `Config.load` → `Config.__init__` does
`DEFAULT_CONFIG.copy()` then `.update(...)`, so an override **merges**. Verified
empirically: 118 default keys in, 118 out, exactly one changed
(`player_off_court_hold_frames` 90 → 100000), 0 missing, 0 added.

14 runs, all exit 0, `--device mps`, sequential, one decode at a time: the 7
entreno clips with the override, and (step 2's drift condition — `git diff
--stat 006e343 HEAD -- src/` is NOT empty, it is commit `d402f65`, the #59 live
debug panel) the same 7 without it, into `output/sr1d/base/`.

**The step-3 scoring command was broken and the owner authorised fixing it.**
`scripts/evaluate.py` takes its action events with a `frame` key while
`src.main` writes `frame_number`; and given a DIRECTORY it looks for an entry
named `actions` instead of opening `pipeline_output.json`. The frozen command
therefore graded an empty list and printed F1 0.000 for all 14 runs **and** for
the pre-existing SR1 baseline artifacts. `output/sr1d/make_eval_predictions.py`
writes each run's actions with the frame key renamed, nothing filtered or
reordered, and the command then runs on that file.

**Adapter validated against the record:** the baseline arm reproduces the
STATUS entreno gate record on 6 of 7 clips (e1 0.706, e3 1.0, e4 0.933, e5
0.923, e6 0.933, e7 0.75). e2 measures **0.400** vs the record's 0.571 — the
known pre-existing path discrepancy documented in
`docs/history/status_log_archive.md` ("the record's e2 .571 is the *action
script* path; the production path has measured .400 before and after",
pre-existing f167 gesture flip). Reported, not resolved; the arms are compared
with each other.

Baseline integrity: the fresh baseline arm is identical to the SR1-era artifacts
on labels + frames for all 7 clips (8/7/14/8/6/7/6 actions), so the `d402f65`
drift is inert for a `--skip-visualization` batch run.

## 2. Entreno, all 7 clips (`scripts/evaluate.py --component actions --ignore-player`)

| clip | base P / R / **F1** | hold-off P / R / **F1** | ΔF1 |
|---|---|---|---|
| e1 | 0.750 / 0.667 / **0.706** | 0.750 / 0.667 / **0.706** | 0.000 |
| e2 | 0.429 / 0.375 / **0.400** | 0.429 / 0.375 / **0.400** | 0.000 |
| e3 | 1.000 / 1.000 / **1.000** | 1.000 / 1.000 / **1.000** | 0.000 |
| e4 | 0.875 / 1.000 / **0.933** | 0.875 / 1.000 / **0.933** | 0.000 |
| e5 | 1.000 / 0.857 / **0.923** | 1.000 / 0.857 / **0.923** | 0.000 |
| e6 | 1.000 / 0.875 / **0.933** | 1.000 / 0.875 / **0.933** | 0.000 |
| e7 | 1.000 / 0.600 / **0.750** | 1.000 / 0.600 / **0.750** | 0.000 |

Not "similar": the two arms' **action streams are identical, event for event**,
on all 7 clips (frame, label and side; zero differences). The drills have
nothing to gain from the lift, which is expected — SR1b's premise is a match
server waiting 120–324 f behind the baseline between points, and the config
comment's "real players max out at 46f (e6)" is a drill figure.

## 3. The e2 sideline bystander (the regression the 90 f horizon was built for)

The track the card describes — right side, foot at x ≈ 1550–1700, y ≈ 700–720 in
frames 0–40 — is track **2**, identified at frame 13, foot (1550.0, 714.9). "Fed"
= present on a frame with `predicted: false`, over the clip's 423 recorded
frames.

| arm | fed frames | present frames | last fed frame | longest fed run |
|---|---|---|---|---|
| base (90) | **400** | 423 | 422 | 296 |
| hold_off (100000) | **423** | 423 | 422 | **423** |

**The bystander is fed 23 frames LONGER, and for the whole clip straight
through.** Note also that in the *baseline* the bystander is still fed on 400 of
423 frames and is present on all 423 — the 90 f horizon is not killing it today
(08-29's "held a slot for 415 f" no longer describes it). What the horizon buys
on e2 is 23 coasting frames, not the track's life.

## 4. The full match (26 061 frames, 31 min, `--serve-events`)

Scored with the project's own scorer, not re-implemented: GT rows from
`serve_rows_from_contact_gt`, matching from `match_candidates` (greedy
one-to-one, nearest first, inside the owner tolerance, side-correct).

| | base (90) | hold_off (100000) |
|---|---|---|
| total actions | 207 | **212** (+5) |
| serve emissions | 20 | 22 (+2) |
| near serves hit | **8 / 16** | **8 / 16** |
| far serves hit | 0 / 17 | 0 / 17 |
| false serves | 12 | **14** (+2) |
| hit timing | all within ±2 f | all within ±2 f |

The aggregate is flat; the composition is not. Near hits by point:

- base: P3, P16, P17, **P18**, P19, P20, P29, P30
- hold-off: P3, **P7**, P16, P17, P19, P20, P29, P30

**+P7, −P18.** SR1b's prediction reproduces: the lift emits `serve` at f3747,
P7's ground-truth frame exactly (delta +0). But P18 regresses at the *same*
frame it was already hit at: baseline emits `serve` at f11996, the lift emits
`dig` at f11996 (P18's GT frame is f11995, tol 15). The contact is not lost —
it is emitted, one frame later than the serve, and no longer reads as a rally
opening, which is the `rally_start` family SR1b already recorded for P5 (still
missed: no emission within ±15 f of f2575 in either arm). The two extra false
serves are f17749 and f17943, both near.

Net: **+1 recovered, −1 lost, +2 false serves, +5 actions, recall unchanged.**

## 5. Pre-registered reading

- `every entreno F1 within ±0.01 of baseline` → **PASS** (Δ = 0.000 × 7, streams
  byte-identical).
- `the e2 bystander is not fed longer than in baseline` → **FAIL** (423 vs 400).

→ **`global lift REFUTED`.** Per the card: the serve-zone exemption needs design
(architect / owner). That is the designed outcome, and this run is its price
list: the exemption cannot be "raise the horizon for everyone", and the P7
recovery it was built for is real but is cancelled by P18 plus two false serves.

**What this does not say.** Nothing here is evidence against a *geometric*
exemption. SR1b's argument still stands that a server behind the own baseline
and a person straddling the sideline are separable — this run only shows the
crude global version cannot tell them apart, and shows the other half of the
cost the card asked for: the `rally_start` coupling at P5/P18 that a longer
hold exposes.

## 6. Card hygiene

- The card's stop-and-ask "the baseline artifacts are older than the current
  `src/`" is TRUE here, yet step 2 gives an explicit instruction for exactly
  that case (re-run the baseline). Both were followed; the wording should be
  reconciled.
- Step 3's frozen command is wrong as written (§1). Worth fixing in the card
  text so the next executor does not re-lose the session to it.
- Two FileNotFoundError flakes on a file that exists were seen while the long
  run was finishing (transient; both paths read fine before and after).