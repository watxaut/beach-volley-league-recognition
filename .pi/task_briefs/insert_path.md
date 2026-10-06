# Task: INSERT-path feasibility — can post-hoc serve records carry the far-side goal math?

You are a diagnose-only worker on the volleyball_recognition repo
(the repository root).
Pure measurement over EXISTING artifacts. No decode, no src change, no GT edit.
STOP on any ambiguity, failed gate, or missing name instead of inferring.

## Background (measured, do not re-litigate)

- Match shipped label accuracy: 85/139 = 0.612 (dump `action`) vs the 0.70 goal bar.
- #74b (`logs/serve_bucket_report.md`): all 12 held-out far serves + P24 are
  NOT-FOUND — no resolver candidate within ±15 f. Label-only ceiling 90/139 = 0.647;
  with the 13 far-side contacts emitted as correct serves: 103/139 = 0.741 (over bar).
- The causal far-serve contact chase is owner-STOPPED (D3, open point 30).
  The sanctioned product is the POST-HOC per-point serve record
  (SR4; promotion = INSERT a serve into actions_pass2/DB after acceptance, never relabel).
- The evidence layer EXISTS: `output/serve_evidence.json` (87 records; #54:
  19/33 points bound, precision 0.90, 1 owner FP; consumer binding dev 5/5,
  held-out 4/12; binding misses P14/P22/P23 no record near serve, P28/P31 ambiguous 2nd record).
- PG2 (#67, `docs/point_map_seam.md`, `scripts/score_point_map_alignment.py`):
  far serves align with WINDOW STARTS (11/17 at a start, 0 in interior, 6 in gaps;
  narrow `far_flight` width_start<=28: 11/17 far, 0/16 near misclaimed — IN-SAMPLE).
  PM1 (#64): the point map is uniformly LATE (+6..+3153 f), 0/17 far serves inside
  their own window; pipeline has 31 points vs 33 GT.

## QUESTION (one line)

With placements keyed the PG2 way (window starts + net-crossing evidence) over the
EXISTING artifacts, how many of the 17 far serves (5 dev P1-P8 + 12 held-out P9-P33)
get a serve record within ±15 f of the GT contact, at what false-serve cost —
and does the resulting INSERT-arm reach the 103/139 = 0.741 goal math?

## G1 gates — reproduce EXACTLY before any task work; any mismatch is a STOP (report it)

- G1a: `output/serve_evidence.json` loads as a dict of 87 records.
- G1b: `output/20260920_match_ari_joan_lost/pipeline_output.json`
  `game_state.points` has 31 entries.
- G1c: `ground_truth/20260920_match_contacts.json` has 33 points; the far serves are
  the 17 GT serve events with far-side team (5 in P1-P8, 12 in P9-P33). If your
  extraction gives a different far/near split than 17/16, STOP.
- G1d: baseline arm — with NO inserted serves, the known baseline is
  85/139 = 0.612 label-correct over the 139 found contacts
  (`scripts/probe_serve_bucket.py` G1 numbers: 185 accepted / 139 found).
  Reproduce the 139-found/85-correct frame sets from
  `output/g3r1/match_bw03_diag.jsonl` before simulating the INSERT arm.

## Tasks

1. **Placement rule (post-hoc, artifacts only).** For each of the 17 far serves:
   candidate placements = serve_evidence records + window starts
   (from `game_state.points` starts, scored the PG2 way); use the net-crossing /
   `far_flight` evidence fields already IN the artifact for disambiguation
   (P28/P31-class double records). Pick ONE placement per serve; record
   frame, offset to GT, which signal chose it. IMPORT machinery from
   `scripts/score_point_map_alignment.py` / `scripts/score_serves.py` /
   `scripts/consume_serve_evidence.py` — never re-implement scoring.
2. **Contact-level score, dev and held-out separately.** Hit = placement within
   ±15 f of the GT far-serve contact frame. Per-serve table: GT frame, placed
   frame, offset, dev/holdout, signals used, hit/miss.
3. **False-serve control (mandatory, AGENTS.md §6).** Count placements that land
   within ±15 f of a NON-serve GT contact (any of the 211 contacts in
   `ground_truth/20260920_match_contacts.json`), and how many pipeline windows
   with NO GT serve receive a placement. Report precision the same way #54 did.
4. **Goal translation.** Simulate the INSERT arm: 139 found + inserted far serves
   labeled `serve` where placed within ±15 f. Report actions-correct/total for
   (a) dev serves only, (b) held-out serves only, (c) all 17 (mark (c) IN-SAMPLE).
5. **Verdict line, exactly one:**
   - `INSERT PATH CARRIES THE BAR` — held-out arm alone reaches ≥103/139-equivalent
     label count with acceptable FP (state the numbers).
   - `INSERT PATH DOES NOT CARRY THE BAR` — max achievable = N/142 (or /139+k),
     state which serves stay unreachable and why (no record / ambiguous / wrong place).
   - `NOT ANSWERABLE` — say exactly what is missing.
   NO rule design, NO src change, NO promotion. This is a feasibility measurement.

## Constraints

- No `src/` change. No video decode, no `cv2.CAP_PROP_POS_FRAMES` anywhere
  (tests/test_vfr_seek_guard.py stays green). No GT edit. The held-out entreno
  session 20290928_entreno_vall_dhebron stays untouched and unscored.
- Numbers IN-SAMPLE vs HELD-OUT must be labeled as such everywhere (AGENTS.md §5).
- No new Config key. VisualGesture enum if you touch class names (plain string
  silently skips ATTACK/BLOCK).
- Final: `venv/bin/python -m pytest tests/ -o addopts=""` green; report count.

## Report

`logs/insert_path_report.md`: §0 G1 gate results; §1 placement table;
§2 dev/held-out scores; §3 control/FP side; §4 goal translation;
§5 verdict line. Finish with the 6-line self-checklist
(scope / evidence / AB-discipline / parity / breaches / hygiene).
