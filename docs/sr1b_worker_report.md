> **Provenance:** verbatim worker report from session #58 (cheap-tier delegate, read-only). Its artifacts and helper scripts live in the git-ignored `output/review_sr1b/` (`analyze_serves.py`, `cf_pass.py`, `compare_arms.py`, diag dumps). The reviewed summary is `docs/sr1b_near_serve_causes.md`.

# SR1b - is the 90 f off-court hold horizon what loses the near serve?

Read-only diagnostic. Nothing under `src/`, `scripts/`, `tests/`, `ground_truth/`, `docs/` or `STATUS.md` was touched; every artifact of this session lives in `output/review_sr1b/` (git-ignored). Both decodes are SEQUENTIAL from frame 0 through `FrameProcessor.process_frame` (no seek anywhere, AGENTS.md section 9) with the production config built by `scripts/score_serve_events.py::production_config` (fine-tuned ball model, `ball_confidence` 0.15, device mps).

Thresholds used here are the ones the code itself uses: `CourtCalibration.is_behind_baseline(foot, team)` with `margin_px=30`, i.e. near (team A) `foot_y > 791-30 = 761`, far (team B) `foot_y < 585+30 = 615` on this calibration; foot = bbox bottom centre, the same definition `ActionClassifier._build_contact` uses. Entreno: near `foot_y > 950-30 = 920`, far `foot_y < 486+30 = 516`.

## 1. Baseline parity

- `scripts/probe_near_serve_misses.py --emit-diag output/review_sr1b/match_0_15000_diag.jsonl --end-frame 15000 --device mps` ran 1093.6 s (25.67 fps VFR content, [1920, 1080]).
- **parity_vs_reference: identical = True, 111 actions in the prefix vs 111 in the shipped `output/20260920_match_ari_joan_lost/pipeline_output.json`, only_in_run [], only_in_reference [].** The baseline arm below is therefore a faithful reproduction of the shipped prefix, not a divergent run.
- Diag dump covers frames [-7, 15000], 111 emitted actions in it (post-filter, keyed by contact frame), which is what every hit/miss below is read from.

## 2. Per-serve server-track status (baseline, production hold horizon = 90 f)

Column notes: `server_status` is FED / COASTING / ABSENT in the window [gt-20, gt+2] for the serving side's track(s) whose foot is beyond that side's baseline; `n_tracks` counts distinct track ids in the window (both sides); `dwell` = frames continuously beyond the baseline up to the GT frame; `last_in_court` = last frame the track was non-predicted AND not beyond the baseline; `gap` = predicted_from - last_in_court (the label proxy); `gap_mask` = the same walk with the TRACKER's own in-court test (foot inside the court mask polygon, which is what `last_in_court_frame` tracks) - this is the number comparable to the 90 f horizon; `toucher_foot_y` is the attributed player's foot at the CONTACT frame (the frame whose snapshot `ActionClassifier` reads via `_closest_player_at`); `toucher_foot_y@seen` is the same track 7 frames later, at the frame the action is decided. `-` = not applicable.

### 2.1 Match 20260920 (12 near / 8 far GT serves in P1..P20; 6/20 hit)

| point | gt_frame | side | hit | server_status | n_tracks | dwell | predicted_from | last_in_court | gap | emitted_action | toucher_track | toucher_foot_y | toucher_foot_y@seen | toucher_pred | toucher_is_server | behind_baseline | near_net | server_track | gap_mask | coast_age_f | frozen | foot_drift_px | foot_margin_px | gap_prev_f |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | 210 | far | miss | FED | 4 | 21 | - | - | - | - | - | - | - | - | - | - | - | 2 | - | - | False | 3 | 20 | - |
| P2 | 880 | far | miss | FED | 4 | 309 | - | - | - | - | - | - | - | - | - | - | - | 2 | - | - | False | 2 | 19 | - |
| P3 | 1395 | near | HIT | FED | 4 | 20 | - | - | - | serve@+1 | 3 | 813 | 802 | False | True | True | False | 3 | - | - | False | 37 | 45 | 357 |
| P4 | 2154 | far | miss | FED | 4 | 324 | - | - | - | - | - | - | - | - | - | - | - | 2 | - | - | False | 7 | 17 | - |
| P5 | 2575 | near | miss | COASTING | 4 | 174 | 2514 | 2401 | 113 | - | - | - | - | - | - | - | - | 1 | 91 | 61 | True | 0 | 117 | - |
| P6 | 3038 | far | miss | ABSENT | 3 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| P7 | 3747 | near | miss | COASTING | 3 | 120 | 3718 | 3627 | 91 | - | - | - | - | - | - | - | - | 4 | 91 | 29 | True | 0 | 84 | - |
| P8 | 4770 | far | miss | FED | 3 | 83 | - | - | - | - | - | - | - | - | - | - | - | 1 | - | - | False | 23 | 27 | - |
| P9 | 5496 | near | miss | FED | 4 | 0 | - | - | - | spike@+0 | 4 | 737 | 769 | False | False | False | True | 1 | - | - | False | 17 | 35 | 366 |
| P10 | 6035 | near | miss | FED | 4 | 0 | - | - | - | spike@-1 | 2 | 748 | 773 | False | True | False | True | 2 | - | - | False | 11 | 54 | 478 |
| P11 | 7147 | near | miss | FED | 3 | 10 | - | - | - | dig@-15 | 2 | 737 | 767 | False | True | False | True | 2 | - | - | False | 37 | 6 | 204 |
| P12 | 7777 | near | miss | FED | 4 | 49 | - | - | - | spike@+3 | 4 | 760 | 769 | False | True | False | True | 4 | - | - | False | 64 | 4 | 435 |
| P13 | 8506 | far | miss | FED | 4 | 100 | - | - | - | - | - | - | - | - | - | - | - | 3 | - | - | False | 1 | 1 | - |
| P14 | 9103 | far | miss | FED | 4 | 181 | - | - | - | - | - | - | - | - | - | - | - | 1 | - | - | False | 2 | 2 | - |
| P15 | 10044 | far | miss | FED | 4 | 33 | - | - | - | - | - | - | - | - | - | - | - | 2 | - | - | False | 5 | 21 | - |
| P16 | 10541 | near | HIT | FED | 3 | 22 | - | - | - | serve@+0 | 4 | 814 | 811 | False | True | True | False | 4 | - | - | False | 36 | 46 | 232 |
| P17 | 11412 | near | HIT | FED | 4 | 2 | - | - | - | serve@-2 | 3 | - | 826 | - | True | True | False | 3 | - | - | False | 4 | 60 | 588 |
| P18 | 11995 | near | HIT | FED | 4 | 0 | - | - | - | serve@+1 | 3 | 835 | 829 | False | False | True | False | 2 | - | - | False | 8 | 86 | 304 |
| P19 | 13074 | near | HIT | FED | 2 | 0 | - | - | - | serve@+0 | 4 | - | 810 | - | True | True | False | 4 | - | - | False | 2 | 46 | 326 |
| P20 | 14518 | near | HIT | FED | 3 | 0 | - | - | - | serve@-2 | 2 | 823 | 708 | False | True | True | False | 2 | - | - | False | 46 | 48 | 129 |

Per-miss evidence (near):
- **P5 f2575** - only near track beyond the baseline is track 1, predicted from f2514 (+61 f before the serve), box FROZEN (0.0 px drift over the 23-frame window); predicted_from - last_in_court = 91 f (hold horizon 90, grace 45); no emitted contact within +-80 f; candidate rejections in the window {'no_contact_geometry': 22, 'reach': 1}
- **P7 f3747** - only near track beyond the baseline is track 4, predicted from f3718 (+29 f before the serve), box FROZEN (0.3 px drift over the 23-frame window); predicted_from - last_in_court = 91 f (hold horizon 90, grace 45); no emitted contact within +-80 f; candidate rejections in the window {'no_ball_sighting': 2, 'no_contact_geometry': 19, 'reach': 2}
- **P9 f5496** - server track 1 is FED (non-predicted) at the serve; emitted spike at f5496 (+0 f) on track 4 foot_y 736.8 (threshold 761 -> behind_baseline=False, near_net=True), toucher_is_server=False, gap_to_prev_contact=366 f (rally_start=True)
- **P10 f6035** - server track 2 is FED (non-predicted) at the serve; emitted spike at f6034 (-1 f) on track 2 foot_y 747.7 (threshold 761 -> behind_baseline=False, near_net=True), toucher_is_server=True, gap_to_prev_contact=478 f (rally_start=True)
- **P11 f7147** - server track 2 is FED (non-predicted) at the serve; emitted dig at f7132 (-15 f) on track 2 foot_y 736.5 (threshold 761 -> behind_baseline=False, near_net=True), toucher_is_server=True, gap_to_prev_contact=204 f (rally_start=True)
- **P12 f7777** - server track 4 is FED (non-predicted) at the serve; emitted spike at f7780 (+3 f) on track 4 foot_y 760.2 (threshold 761 -> behind_baseline=False, near_net=True), toucher_is_server=True, gap_to_prev_contact=435 f (rally_start=True)

Far-side context (the same measurement, other side of the net):
- P1 f210: FED (server track 2, dwell 21 f) | ball track at the GT frame: state=none reason=unlocked_no_motion | rejections {'no_ball_sighting': 23} | nearest same-side contact within 80 f: None
- P2 f880: FED (server track 2, dwell 309 f) | ball track at the GT frame: state=none reason=unlocked_no_motion | rejections {'no_ball_sighting': 23} | nearest same-side contact within 80 f: None
- P4 f2154: FED (server track 2, dwell 324 f) | ball track at the GT frame: state=none reason=unlocked_no_motion | rejections {'no_ball_sighting': 23} | nearest same-side contact within 80 f: {'frame': 2195, 'delta_f': 41, 'action': 'dig'}
- P6 f3038: ABSENT (server track None, dwell None f) | ball track at the GT frame: state=none reason=unlocked_no_motion | rejections {'no_ball_sighting': 23} | nearest same-side contact within 80 f: None
- P8 f4770: FED (server track 1, dwell 83 f) | ball track at the GT frame: state=none reason=unlocked_no_motion | rejections {'no_ball_sighting': 23} | nearest same-side contact within 80 f: None
- P13 f8506: FED (server track 3, dwell 100 f) | ball track at the GT frame: state=none reason=unlocked_no_motion | rejections {'no_ball_sighting': 23} | nearest same-side contact within 80 f: {'frame': 8534, 'delta_f': 28, 'action': 'serve'}
- P14 f9103: FED (server track 1, dwell 181 f) | ball track at the GT frame: state=none reason=unlocked_no_motion | rejections {'no_ball_sighting': 23} | nearest same-side contact within 80 f: None
- P15 f10044: FED (server track 2, dwell 33 f) | ball track at the GT frame: state=tracked reason=low_floor_admitted | rejections {'no_ball_sighting': 11, 'no_contact_geometry': 12} | nearest same-side contact within 80 f: {'frame': 10070, 'delta_f': 26, 'action': 'serve'}

`toucher_is_server` compares the attributed track with the track my window rule picked as "the near track behind the baseline". It reads False at P9 and P18 because in those windows two near tracks were behind the baseline and the pick landed on the other one - at P18 the attributed track 3 (foot 835.4) is behind the baseline and the label is `serve`, so the pick, not the geometry, is what differs.

What the geometry columns say about the four label misses:

- P9: the attributed tracker's foot is **24.2 px short** of the 761 threshold at the contact frame (736.8) and **8.2 px past it** 7 frames later (769.2); behind_baseline is read on the earlier snapshot.
- P10: the attributed tracker's foot is **13.3 px short** of the 761 threshold at the contact frame (747.7) and **11.8 px past it** 7 frames later (772.8); behind_baseline is read on the earlier snapshot.
- P11: the attributed tracker's foot is **24.5 px short** of the 761 threshold at the contact frame (736.5) and **6.1 px past it** 7 frames later (767.1); behind_baseline is read on the earlier snapshot.
- P12: the attributed tracker's foot is **0.8 px short** of the 761 threshold at the contact frame (760.2) and **7.9 px past it** 7 frames later (768.9); behind_baseline is read on the earlier snapshot.

For comparison, the six near hits (all FED, all `behind_baseline` true):

- P3 (HIT): foot 813.2, behind_baseline=True, near_net=False, toucher_is_server=True
- P16 (HIT): foot 814.2, behind_baseline=True, near_net=False, toucher_is_server=True
- P17 (HIT): foot no snapshot on the contact frame, 826.1 at the decision frame, behind_baseline=True, near_net=False, toucher_is_server=True
- P18 (HIT): foot 835.4, behind_baseline=True, near_net=False, toucher_is_server=False
- P19 (HIT): foot no snapshot on the contact frame, 809.5 at the decision frame, behind_baseline=True, near_net=False, toucher_is_server=True
- P20 (HIT): foot 823.4, behind_baseline=True, near_net=False, toucher_is_server=True

## 2.2 Practice captures (near serves, existing dumps, no decode)

GT frames read from `ground_truth/video_entreno_N_annotations.json`. Note e6: the owner-ratified GT serve is **f34** (ratified 2026-09-06), not f35 as quoted in the task; +-15 f covers both.

| session | gt_frame | side | hit | server_status | n_tracks | dwell | predicted_from | last_in_court | gap | emitted_action | toucher_track | toucher_foot_y | toucher_pred | toucher_is_server | behind_baseline | near_net | server_track | foot_drift_px | first failing stage |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| entreno_2 | 32 | near | miss | ABSENT | 4 | - | - | - | - | dig@+0 | 3 | 646 | False | False | False | True | - | - | contact emitted, LABEL (behind_baseline false on the toucher) |
| entreno_3 | 29 | near | HIT | FED | 4 | 16 | - | - | - | serve@+0 | 4 | 965 | False | True | True | False | 4 | 34 | contact emitted, serve |
| entreno_5 | 20 | near | miss | FED | 4 | 13 | - | - | - | - | - | - | - | - | - | - | 4 | 9 | no contact: {'pre_history': 8, 'no_contact_geometry': 7, 'no_ball_sighting': 8} |
| entreno_6 | 34 | near | HIT | FED | 4 | 35 | - | - | - | serve@+1 | 4 | 984 | False | True | True | False | 4 | 32 | contact emitted, serve |
| entreno_7 | 25 | near | HIT | FED | 4 | 17 | - | - | - | serve@+0 | 3 | 966 | False | True | True | False | 3 | 38 | contact emitted, serve |

- **entreno_2 f32 (miss)**: ABSENT - no near track is beyond the baseline anywhere in the window; the 4 tracked players sit at foot y 529/522 (far) and 715/646 (near). The contact IS emitted (dig, track 3, foot 646, near_net true, behind_baseline false) - a pure label miss, and the attributed player is a net player, not the server.
- **entreno_5 f20 (miss)**: FED, server track 4 is fed and alive (dwell 13 f, drift 8.9 px), but the window's candidate rejections are {'pre_history': 8, 'no_contact_geometry': 7, 'no_ball_sighting': 8} - the BALL was not tracked at the serve (`no_ball_sighting`). Not a server-track problem.
- **entreno_3 / 6 / 7 (hits)**: FED in all three, toucher = server track, behind_baseline true (feet 34-58 px past the 920 threshold). The hold horizon never appears: no practice serve window contains a coasting server track.

## 3. Counterfactual: `player_off_court_hold_frames` 90 -> 100000, [0, 8000]

- `output/review_sr1b/cf_pass.py` copies the probe's sequential loop and rides the override on the config dict; the effective value on the live object was asserted and printed before decoding: `player_tracker.off_court_hold_frames = 100000` (off_court_grace_frames left at 45), 549.5 s, 55 emitted actions.
- Action counts in [0,8000] (diag-to-diag, so both arms exclude their own final flushed contact): **baseline 53, counterfactual 55**; only_baseline 1, only_cf 3.

| point | gt_frame | side | hit_base | hit_cf | status_base | status_cf | server_track_base | server_track_cf | pred_from_base | pred_from_cf | gap_mask_base | gap_mask_cf | emitted_base | emitted_cf | toucher_is_server_base | toucher_is_server_cf |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | 210 | far | miss | miss | FED | FED | 2 | 2 | - | - | - | - | - | - | - | - |
| P2 | 880 | far | miss | miss | FED | FED | 2 | 2 | - | - | - | - | - | - | - | - |
| P3 | 1395 | near | HIT | HIT | FED | FED | 3 | 3 | - | - | - | - | serve@+1 | serve@+1 | True | True |
| P4 | 2154 | far | miss | miss | FED | FED | 2 | 1 | - | - | - | - | - | - | - | - |
| P5 | 2575 | near | miss | miss | COASTING | FED | 1 | 4 | 2514 | - | 91 | - | - | dig@-3 | - | True |
| P6 | 3038 | far | miss | miss | ABSENT | ABSENT | - | - | - | - | - | - | - | - | - | - |
| P7 | 3747 | near | miss | HIT | COASTING | FED | 4 | 3 | 3718 | - | 91 | - | - | serve@+0 | - | True |
| P8 | 4770 | far | miss | miss | FED | FED | 1 | 1 | - | - | - | - | - | - | - | - |
| P9 | 5496 | near | miss | miss | FED | FED | 1 | 2 | - | - | - | - | spike@+0 | spike@+0 | False | True |
| P10 | 6035 | near | miss | miss | FED | FED | 2 | 3 | - | - | - | - | spike@-1 | spike@-1 | True | True |
| P11 | 7147 | near | miss | miss | FED | FED | 2 | 1 | - | - | - | - | dig@-15 | dig@-15 | True | True |
| P12 | 7777 | near | miss | miss | FED | FED | 4 | 1 | - | - | - | - | spike@+3 | spike@+3 | True | True |

### 3.1 Full action diff (key = frame_number, action, team)

| arm | frame | action | team | side | nearest GT contact | delta |
|---|---|---|---|---|---|---|
| only_baseline | 2494 | overpass | A | near | P5 f2575 serve near | -81 f |
| only_cf | 2494 | set | A | near | P5 f2575 serve near | -81 f |
| only_cf | 2572 | dig | A | near | P5 f2575 serve near | -3 f |
| only_cf | 3747 | serve | A | near | P7 f3747 serve near | +0 f |

Reading of each diff row:

- **f2494 overpass (only_baseline)**: the SAME contact exists in both arms and is labelled `overpass` in the baseline and `set` in the counterfactual. No GT event within 81 f (nearest is the P5 serve at f2575, -81 f), so GT cannot call it a fix or a regression; it is a context-layer label difference caused by the different touch sequence, on a non-serve frame.
- **f2572 dig (only_cf)**: a contact that does not exist in the baseline. The reach gate stops passing in the baseline (448.3 px vs a 140.0 px reach at f2572, nearest player track 4), so this is the hold horizon's doing. It is emitted as `dig`, not `serve`: behind_baseline is now TRUE (toucher foot 810.9, the server track, fed) but the gap to the previous emitted contact (f2494) is 78 f, under the 90 f rally-reset gap, so rally_start is false. P5 stays a miss, in a different bucket.
- **f3747 serve (only_cf)**: the P7 serve itself. Behind the counterfactual the server track is FED (drift 34 px over the window instead of a frozen 0.3 px), the reach gate passes, and the label reads serve: behind_baseline true (foot 818.8) and rally_start true (gap to the previous contact 108 f > 90). **P7 becomes a hit.**

## 4. Verdict

**Mixed - and it splits cleanly by miss class: SUPPORTED for the two
no-contact near misses (P5, P7), REFUTED for the four label misses
(P9-P12).**

1. **P5 f2575 and P7 f3747 (no emitted contact at all) - SUPPORTED.** The only
   near track beyond the baseline is a coasting ghost: box FROZEN (0.0 px and
   0.3 px drift over the 23-frame window), last fed 61 f and 29 f before the
   serve, and its predicted run began exactly **91 f** after its last in-court
   sighting at both points - the 90 f `off_court_hold_frames` horizon, never
   the 45 f grace. The contact then dies at the reach gate (448.3 px vs a
   140.0 px reach at f2572; 204.0 vs 140.0 at f3747), with the ball itself
   tracked (conf 0.88 / 0.78).
2. **Lifting the horizon confirms it causally**: P7 becomes a HIT (serve
   emitted at f3747, +0 f, behind_baseline true at foot 818.8, rally_start
   true with a 108 f gap), and P5 stops being a `no_contact` miss and becomes a
   label miss instead - a `dig` at f2572 (-3 f) on the now-FED server track
   (foot 810.9, behind_baseline TRUE) whose `rally_start` is false because the
   previous emitted contact is only 78 f back (< 90).
3. **P9 f5496 / P10 f6035 / P11 f7147 / P12 f7777 - REFUTED.** No coasting
   anywhere: the server track is FED and moving in every window (dwell 0-49 f,
   drift 11-64 px, zero predicted frames). The contact is emitted at 0 / -1 /
   -15 / +3 f and the only failing serve condition is `behind_baseline` on the
   attributed tracker's CONTACT-frame foot - 736.8 / 747.7 / 736.5 / 760.2
   against the 761 threshold, i.e. 24.2 / 13.3 / 24.5 / **0.8** px short -
   while the very same tracks sit 8-12 px PAST the baseline 7 frames later at
   the decision frame. The counterfactual reproduces these four rows to the
   decimal (same contact frames, same actions, same foot y, same
   `behind_baseline=False`); only the track ids shuffle. The hold horizon is
   not in their causal path.
4. **The far side is a third, separate loss** and is not the player side at
   all: 7 of the 8 far serves in P1..P20 log 23/23 `no_ball_sighting`
   rejections with `ball_track.state = none` (`unlocked_no_motion`) - the ball
   never locks in the far serve window (P15 is the exception: the ball is
   tracked at conf 0.159 and a serve is emitted at +26 f, off tolerance).
5. **Cost of the override as measured**: 1 label flip on a non-serve frame
   (f2494 `overpass` -> `set`, no GT event within 81 f), 2 new contacts
   (f2572 `dig`, f3747 `serve`), 53 -> 55 actions in [0,8000]. Everything else
   is unchanged.
6. **Bottom line**: the 90 f hold horizon is real, reachable and *sufficient*
   for the P7 miss, and it is what puts the P5 server in the reach gate's blind
   spot (it fixes the reach, not the label). It explains none of the P9-P12
   misses, which are a contact-frame-vs-decision-frame foot-position question.

---

## Appendix - what each column is, and the caveats

- `load_diag` is `src/utils.diagnostics.load_diag`; a diag *frame record* is keyed by the frame it describes for `players`/`ball_track`/`actions`, and additionally by the CONTACT frame for `candidates` (so a record can hold both).
- Sanity check on the reading: recomputing `is_behind_baseline` / `is_near_net` from the contact-frame snapshot of the `candidate_passed_gates` records reproduces 104 of the 106 gate records in the match dump exactly (the 2 exceptions are non-serve contacts, plus 4 contacts whose track has no snapshot on the contact frame itself and is read from the +-1 frame history snapshot). So the `toucher_foot_y` column and the `behind_baseline` / `near_net` columns are consistent measurements of the same quantity.
- `predicted` is the tracker's own coast flag. A coasting track's box is extrapolated for `coast_extrapolation_cap` = 15 frames and then frozen, so a frozen box (`frozen`/`foot_drift_px` columns) is a dead track holding a stale position, not a player standing still.
- `last_in_court` (label proxy: foot not beyond the baseline) is looser than the tracker's `last_in_court_frame` (foot inside the court-mask polygon, whose near edge runs y 774..791 across the court); the `gap` column therefore reads larger than `gap_mask`, and `gap_mask` is the one to compare against the 90 f horizon.
- Hit/miss uses the emitted `serve` action within +-15 f whose `team` is the serving side's letter (near=A, far=B), taken from the frame records' `actions` lists, which are the post-filter emissions of `process_frame` (keyed by contact frame). The end-of-decode flush contact is not in a dump, but it costs nothing here: the baseline dump's last action is f14550 and the counterfactual's is f7815, both already finalised inside their windows (the counterfactual's flush added no new key -- 55 actions in `cf_actions.json`, 55 in its dump, identical sets).
- The counterfactual diff is diag-to-diag over [0,8000], so both arms are read the same way; `cf_actions.json` (55 actions, the emit list including the end-of-decode flush) has exactly the same 55 (frame, action, team) keys as the counterfactual dump, i.e. the flush added nothing inside the range.
- Both arms are MPS; the baseline's byte-identical parity against the shipped artifact is the bound on device jitter for the numbers quoted here.
