# Point winner/outcome layer (open point 21.3) — pass-2 interpreter

> ## OUTCOME: SHIPPED as a pass-2 script (2026-09-30, session 43)
>
> `scripts/resolve_point_winners.py` + `tests/test_point_winners.py` (27
> tests). Pure observer over the EXISTING artifacts
> (`output/episode_point_map.json`, `output/match20260920_posegate/pipeline_output.json`,
> `output/match20260920_posegate/results_game_state.csv`,
> `output/serve_relabel.json`): no video decode, no `src/` change,
> entreno-neutral by construction. **Validation against the 33 dictated
> winners: 33/33 decided, 18/33 correct after the (validate-only)
> side→squad mapping — 54.5%.** This is an honest baseline, NOT a
> fantasy-grade outcome signal: the two dominant miss sources are
> terminal-touch side attribution and ball-death in/out, neither of which
> any current artifact carries. The layer is the G1 critical-path plumbing
> (21.3 → 13 ace/serve-fault/assist → fantasy), to be consumed only once
> the serve CONTACT and side-switch layers make the terminal touch real.
>
> Generated raw run/report lives in `logs/point_winner_report.md`
> (git-ignored); this file is the durable record.

## Where it lives

- `scripts/resolve_point_winners.py` — pass-2 layer (AGENTS.md §6
  hindsight layer over `pipeline_output.json`/the DB, never a second
  full-video pass). Outputs `output/point_winners.json` (git-ignored) and,
  under `--validate`, `logs/point_winner_report.md`.
- `tests/test_point_winners.py` — 27 synthetic tests pinning the fault
  prior, owner-verdict demotions, GT-leakage projections, side→squad
  validation mapping, miss taxonomy, game-state run parsing and
  end-to-end determinism.
- Reproduce:
  `venv/bin/python scripts/resolve_point_winners.py --validate ground_truth/20260920_match_points.json`

## Design (mechanism + why)

1. **Fault prior over the terminal touch.** The side of the last LIVE
   action in the TRUE window loses the point; winner = the other COURT
   SIDE (A = near half, B = far half — the perception stack's frame of
   reference, `CourtCalibration.get_team`).
2. **Live =** pipeline actions in-window minus the serve layer's
   owner-verdict demotions. The pass-2 serve re-label fixes the opener's
   ACTION label only, never its team.
3. **Abstain only structurally** (no live touch / unknown terminal team);
   doubt that keeps coverage is expressed as `confidence: low` + flags
   (`contested_attribution`, pass-2 override flag on the terminal, serve
   never adopted in-stream, pinned serve outside window). On the match:
   33/33 decided, 6 low-confidence.
4. **Ball-death side / in-out** — the kill-vs-fault disambiguator — is NOT
   in any artifact (`pipeline_output.json` has actions/spikes/game state
   only; no dense ball track). Kill/ace endings therefore stay fault-prior
   misses instead of guesses. `raw_widths.csv` was probed as a death-side
   source and REJECTED: post-rally ball handling and static-suspect
   survivors contaminate the tail (near-uniform "far:OUT" reads that
   contradict dictated endings).
5. **Spike-record outcomes are reported as evidence only.** Measured as a
   winner rule they score 4/10 on terminal spikes — their team letter
   inherits the same net-boundary attribution errors — so no rule consumes
   them.
6. **Winner is a SIDE letter, not a squad letter.** Squads swap halves at
   side switches and the switch schedule is GT; the side→squad mapping
   runs in `--validate` only. (Until the 21.4 side-switch layer lands the
   artifact speaks side letters.)

## Validation vs the 33 dictated winners

- decided: **33/33** windows (abstain 0)
- correct (squad-mapped): **18/33 = 54.5%** of decided
- side switches applied (GT, `--validate` only): after points [7, 14, 21, 28]

| P | winner side | → squad | GT | ok | conf | ending | terminal touch | miss class |
|---|---|---|---|---|---|---|---|---|
| 1 | B | B | B | OK | medium | attack_terminal | spike@f345 side A |  |
| 2 | B | B | A | MISS | low | serve_terminal | dig@f930 side A | serve_team_misattribution |
| 3 | A | A | B | MISS | medium | attack_terminal | set@f1488 side B | kill/ace-class ending |
| 4 | A | A | A | OK | medium | serve_terminal | dig@f2195 side B |  |
| 5 | B | B | B | OK | low | attack_terminal | overpass@f2494 side A |  |
| 6 | B | B | A | MISS | low | serve_terminal | dig@f3070 side A | serve_team_misattribution |
| 7 | B | B | A | MISS | low | reception_terminal | dig@f3639 side A | kill/ace-class ending |
| 8 | B | A | B | MISS | low | serve_terminal | dig@f4801 side A | serve_team_misattribution |
| 9 | B | A | B | MISS | low | attack_terminal | spike@f5556 side A | terminal-touch attribution |
| 10 | A | B | B | OK | medium | reception_terminal | dig@f6067 side B |  |
| 11 | A | B | B | OK | medium | attack_terminal | set@f7242 side B |  |
| 12 | A | B | A | MISS | medium | attack_terminal | spike@f7815 side B | terminal-touch attribution |
| 13 | B | A | A | OK | medium | reception_terminal | dig@f8583 side A |  |
| 14 | A | B | B | OK | low | attack_terminal | spike@f9217 side B |  |
| 15 | A | A | A | OK | medium | attack_terminal | block@f10157 side B |  |
| 16 | A | A | A | OK | medium | attack_terminal | spike@f10658 side B |  |
| 17 | B | B | A | MISS | medium | reception_terminal | dig@f11443 side A | kill/ace-class ending |
| 18 | A | A | A | OK | medium | attack_terminal | spike@f12576 side B |  |
| 19 | A | A | A | OK | medium | attack_terminal | spike@f13758 side B |  |
| 20 | A | A | B | MISS | low | attack_terminal | overpass@f15280 side B | pinned serve outside window |
| 21 | A | A | A | OK | medium | reception_terminal | dig@f16137 side B |  |
| 22 | A | B | A | MISS | medium | reception_terminal | dig@f16877 side B | terminal-touch attribution |
| 23 | B | A | B | MISS | medium | attack_terminal | overpass@f17257 side A | terminal-touch attribution |
| 24 | A | B | A | MISS | medium | reception_terminal | dig@f18408 side B | terminal-touch attribution |
| 25 | A | B | A | MISS | medium | reception_terminal | dig@f19445 side B | terminal-touch attribution |
| 26 | B | A | A | OK | medium | reception_terminal | dig@f20244 side A |  |
| 27 | A | B | A | MISS | low | attack_terminal | overpass@f20690 side B | terminal-touch attribution |
| 28 | B | A | A | OK | medium | attack_terminal | spike@f21016 side A |  |
| 29 | A | A | A | OK | medium | reception_terminal | dig@f21490 side B |  |
| 30 | B | B | B | OK | medium | attack_terminal | spike@f22389 side A |  |
| 31 | A | A | B | MISS | medium | reception_terminal | dig@f23462 side B | terminal-touch attribution |
| 32 | A | A | A | OK | medium | reception_terminal | dig@f25033 side B |  |
| 33 | A | A | A | OK | medium | attack_terminal | spike@f25925 side B |  |

### Miss taxonomy (15 misses, all explained)

| class | count | points | what it means / which dependency |
|---|---|---|---|
| terminal-touch attribution | 8 | 9, 12, 22, 23, 24, 25, 27, 31 | emitted terminal touch's side letter contradicts the dictated ending (misattributed net/far contact, or the true terminal touch was never emitted) — AGENTS.md §5 side signal / point 22 serve CONTACT |
| kill/ace-class ending | 3 | 3, 7, 17 | the dictated last toucher's side SCORED; the fault prior flips it because ball-death in/out is not in the artifacts |
| serve_team_misattribution | 3 | 2, 6, 8 | far-side serve emitted with the wrong side letter; pass-2 holds a winner-serves-derived override this layer refuses to inherit (GT leakage) |
| owner-pinned serve outside window | 1 | 20 | `ep45` phantom-rally family; needs P18–P20 anchors |

(The 8 terminal-touch misses are the dominant source and are the same
contact-level far-serve/side-attribution gap quantified in the 42nd-session
review — point 22.)

## GT-leakage accounting

- `output/serve_relabel.json` carries **13** winner-serves-derived
  serve-team overrides (`team_resolved`). The layer never projects them
  into inference; only `team_emitted` and the override FLAG are read.
- Inheriting them would have flipped **P2, P6, P8** to correct
  (18 → 21/33) — that accuracy is GT-bought and is NOT shipped.
- Inference reads inputs through field projections: the map contributes
  `point`/`window_frames` only; the serve layer contributes owner-verdict
  demotions + override flags only. GT winner / score / `side_switch` are
  opened exclusively by `--validate`.

## Residual risks / next steps

- **Dominant miss = terminal-touch side attribution** (net/far contacts,
  AGENTS.md §5). A width-band-aware attribution fix (T8) or the S1 far-serve
  CONTACT probe would move more points than any winner-layer logic.
- **Ball-death side + in/out** is the missing disambiguator for kill/ace
  endings; it needs a per-frame ball-track sidecar in `pipeline_output.json`
  (T6) or the §6 targeted re-decode escalation.
- **Squad winners need the 21.4 side-switch layer (S3)**; until then the
  artifact speaks side letters and the mapping lives in `--validate`.
- Consume this layer downstream (ace / serve-fault / assist, then fantasy)
  only after S1–S3 so the terminal touch and the serving side are real.

## Housekeeping (session 43)

The script + tests were left untracked by the session that produced the
first draft (timestamp 2026-09-30 11:32) and not reviewed by the 42nd
session. Session 43 reviewed them, found three test-side defects (a `None`
window fixture, an outcome-signal resolution-frame fixture outside its
window, and a game-state death-frame off-by-one that contradicted the
file's own `test_ball_death_from_game_on_run`), fixed them, confirmed the
script reproduces `output/point_winners.json` and the report
byte-identically, and ran the full suite green (**782**).
