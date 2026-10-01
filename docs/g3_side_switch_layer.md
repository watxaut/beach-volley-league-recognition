# Side-switch / squad layer (S3, open point 21.4) — pass-2 interpreter

> ## OUTCOME: SHIPPED as a pass-2 script (2026-10-01)
>
> `scripts/resolve_side_switches.py` + `tests/test_side_switches.py` (25
> tests). Pure observer over the existing artifacts
> (`output/episode_point_map.json`, `output/serve_relabel.json`, optionally a
> player diag dump): no video decode, no `src/` change, entreno-neutral by
> construction.
>
> **The finding that makes this a needle-mover:** the perception stack speaks
> COURT-SIDE letters (A = near, B = far — `CourtCalibration.get_team`), while
> the owner/GT convention is SQUAD letters (A = the squad that started near).
> The raw G1 `team 0.518` is therefore a **side-vs-squad confound**, not a
> side-attribution failure. Applying the derived switch mapping lifts it to
> **0.755** (105/139) and exposes the TRUE side error at **34/139 = 0.245**
> (10 of them pure team errors, the rest co-occurring with label errors).
> The T4 waterfall's "5 stage-5 team errors, all P8" are exactly this
> confound: P8 is the first point after the first switch.
>
> Generated raw run/report lives in `logs/side_switch_report.md` (git-ignored);
> this file is the durable record.

## Where it lives

- `scripts/resolve_side_switches.py` — pass-2 layer (AGENTS.md §6 hindsight
  layer over `pipeline_output.json`/the DB, never a second full-video pass).
  Outputs `output/side_switches.json` (git-ignored) and, with the flags
  below, `logs/side_switch_report.md`.
- `tests/test_side_switches.py` — 25 synthetic tests pinning the cadence, the
  side→squad parity (incl. the owner P9 anchor), point placement, action
  annotation, validation, the G1 metric correction and the crossing evidence,
  plus two artifact tests that pin the real numbers.
- Reproduce:
  ```bash
  venv/bin/python scripts/resolve_side_switches.py \
      --validate ground_truth/20260920_match_points.json \
      --evidence output/g3r1/match_bw03_diag.jsonl
  ```

## Design (mechanism + why)

1. **Primary mechanism = the beach cadence.** Sides change ends after every
   `--interval` (default 7) points played. For the 33-point match that is
   `[7, 14, 21, 28]`, derived from the POINT ORDER alone. This is sport rules,
   not ground truth; `--validate` opens the owner
   `side_switch_after_point` field and confirms **exact match**.
2. **Side→squad mapping.** `squad_of_side(side, point, switches)` by switch
   parity: the squad that starts near is squad A, and the mapping flips at
   each switch. Point P9 f5496 (owner: near side, squad B) is the anchor test.
3. **Output speaks squad.** `actions_pass2` is augmented with `pass2_squad`
   (and `pass2_point`), so downstream fantasy/stat layers can group by squad;
   the side letter stays as provenance. 207/207 actions annotated.
4. **Cross-check is EVIDENCE ONLY — measured, not trusted.** With
   `--evidence <diag.jsonl>` the dense player boxes are reduced to a per-point
   median signed midcourt offset per track, and each boundary's
   player-crossing support is reported. On the 20260920 match the R1 dump
   (player tracking is independent of the ball departure gate) gives **3/4
   cadence switches with support, but 16 of the 28 non-switch boundaries also
   show support** — the signal cannot place switches, because tracker ids hop
   (open point 2). It is recorded and explicitly NOT used to place switches;
   a position-based detector needs stable identity GT first.
5. **GT-leakage guard.** Inference reads point numbers + windows and the
   pass-2 stream's side letters only. The owner `side_switch_after_point`
   schedule is opened exclusively by `--validate` (and the `--g1` correction
   is a read-only re-scoring of an existing artifact).

## G1 team-metric correction (the measured needle)

On the 139 found contacts of G1's perception arm:

| metric | correct | accuracy | what it measures |
|---|---|---|---|
| raw (recorded G1) | 72/139 | **0.518** | pred SIDE letter vs GT SQUAD |
| squad-mapped (this layer) | 105/139 | **0.755** | pred side → squad vs GT squad |
| pred side vs owner side | 105/139 | **0.755** | what the perception stack actually emits |

The 34 residual errors are genuine side-attribution failures, clustering at
P10, P15, P18, P19, P22, P24–P26, P29–P30 — the near/far width-band
attribution class (open point 22 / AGENTS.md §5), not a switch gap. The
correction is reported, not rewritten: G1's recorded 0.518 stands as the
"side vs squad" number, and this layer supplies the squad-mapped number every
future consume-squad mechanism (S4 fantasy/stats) must use.

## Interaction with the other pass-2 layers

- `resolve_point_winners.py` deliberately emits a SIDE letter and gates its
  side→squad mapping behind `--validate`. This layer is the missing
  autonomous schedule that lets the winner layer, the serve relabel and the
  future fantasy module all speak squad without GT.
- `score_pass2_contacts.py` / `score_heldout_contacts.py` remain unchanged
  (no regression surface); the correction is computed separately from the G1
  per-contact artifact.
- Independent of S1/S2: the far-serve CONTACT gap is untouched here.

## Residual risks / next steps

- **Position-based cross-check** stays deferred until stable player identity
  GT exists (open point 2 / `annotate_player_gt.py`); the cadence is exact on
  this match but a rule-only layer cannot detect an off-cadence switch.
- **Consume `pass2_squad`** downstream (S4: ace/fault/assist + fantasy) and
  re-score at squad level; the G1 scorer itself can adopt the mapping when a
  squad-level baseline is wanted.
- If a future match's switch cadence differs (different set structure), the
  `--interval` knob and the `--evidence` report are the review surface.

## Reproduce

```bash
venv/bin/python scripts/resolve_side_switches.py \
    --validate ground_truth/20260920_match_points.json \
    --evidence output/g3r1/match_bw03_diag.jsonl
venv/bin/python -m pytest tests/test_side_switches.py -o addopts=""
```
