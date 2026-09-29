# T5 step 2 - mechanism A vs B (replay)

Both mechanisms were REFUTED as a recovery (0/5 far serves) and live
OUTSIDE `src/`, in `scripts/serve_mechanism_harness.py` as
default-off subclasses; `src/` is unchanged.

Replay of `output/t4/dev_diag.jsonl` (4968 frames) through the real
`BallTracker` + `ActionClassifier` contact probe, against
`ground_truth/video_ari_joan_8_first_points_annotations.json`.

| arm | far serves with a candidate | contacts | exact-frame | extra candidates | new locks | fidelity |
|---|---|---|---|---|---|---|
| base | 0/5 | 36 | 5/28 | 13 | 0 | 0 locked / 0 centre |
| A_weak3_w30 | 0/5 | 37 | 5/28 | 14 | 19 | 432 locked / 0 centre |
| A_weak3_nowidth | 0/5 | 37 | 5/28 | 14 | 26 | 507 locked / 0 centre |
| B_backfill | 0/5 | 37 | 5/28 | 14 | 0 | 0 locked / 0 centre |
| B_backfill_narrow | 0/5 | 37 | 5/28 | 14 | 0 | 0 locked / 0 centre |
| B_backfill_tight | 0/5 | 37 | 5/28 | 14 | 0 | 0 locked / 0 centre |
| B_backfill_skip_suspect | 0/5 | 37 | 5/28 | 14 | 0 | 0 locked / 0 centre |
| B_backfill_lookback12 | 0/5 | 37 | 5/28 | 14 | 0 | 0 locked / 0 centre |

## Per-serve candidates (frame:offset from the GT frame)

* **base**: P1 f210 MISS, P2 f880 MISS, P3 f1395@+1, P4 f2154 MISS, P5 f2575@-3, P6 f3038 MISS, P7 f3747@+0, P8 f4770 MISS
* **A_weak3_w30**: P1 f210 MISS, P2 f880 MISS, P3 f1395@+1, P4 f2154 MISS, P5 f2575@-3, P6 f3038 MISS, P7 f3747@+0, P8 f4770 MISS
* **A_weak3_nowidth**: P1 f210 MISS, P2 f880 MISS, P3 f1395@+1, P4 f2154 MISS, P5 f2575@-3, P6 f3038 MISS, P7 f3747@+0, P8 f4770 MISS
* **B_backfill**: P1 f210 MISS, P2 f880 MISS, P3 f1395@+1, P4 f2154 MISS, P5 f2575@-3, P6 f3038 MISS, P7 f3747@+0, P8 f4770 MISS
* **B_backfill_narrow**: P1 f210 MISS, P2 f880 MISS, P3 f1395@+1, P4 f2154 MISS, P5 f2575@-3, P6 f3038 MISS, P7 f3747@+0, P8 f4770 MISS
* **B_backfill_tight**: P1 f210 MISS, P2 f880 MISS, P3 f1395@+1, P4 f2154 MISS, P5 f2575@-3, P6 f3038 MISS, P7 f3747@+0, P8 f4770 MISS
* **B_backfill_skip_suspect**: P1 f210 MISS, P2 f880 MISS, P3 f1395@+1, P4 f2154 MISS, P5 f2575@-3, P6 f3038 MISS, P7 f3747@+0, P8 f4770 MISS
* **B_backfill_lookback12**: P1 f210 MISS, P2 f880 MISS, P3 f1395@+1, P4 f2154 MISS, P5 f2575@-3, P6 f3038 MISS, P7 f3747@+0, P8 f4770 MISS

## Contact-probe outcome inside each serve window (+-tolerance frames)

* **base**:
  * P1 f210 (far): {'no_ball_sighting': 23, 'no_contact_geometry': 8}
  * P2 f880 (far): {'no_ball_sighting': 27, 'no_contact_geometry': 4}
  * P3 f1395 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P4 f2154 (far): {'no_ball_sighting': 20, 'no_contact_geometry': 11}
  * P5 f2575 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P6 f3038 (far): {'no_ball_sighting': 21, 'no_contact_geometry': 10}
  * P7 f3747 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P8 f4770 (far): {'no_ball_sighting': 21, 'no_contact_geometry': 10}
* **A_weak3_w30**:
  * P1 f210 (far): {'no_contact_geometry': 21, 'no_ball_sighting': 10}
  * P2 f880 (far): {'no_contact_geometry': 16, 'no_ball_sighting': 15}
  * P3 f1395 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P4 f2154 (far): {'no_ball_sighting': 17, 'no_contact_geometry': 14}
  * P5 f2575 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P6 f3038 (far): {'no_ball_sighting': 19, 'no_contact_geometry': 12}
  * P7 f3747 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P8 f4770 (far): {'no_contact_geometry': 21, 'no_ball_sighting': 10}
* **A_weak3_nowidth**:
  * P1 f210 (far): {'no_contact_geometry': 21, 'no_ball_sighting': 10}
  * P2 f880 (far): {'no_contact_geometry': 16, 'no_ball_sighting': 15}
  * P3 f1395 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P4 f2154 (far): {'no_ball_sighting': 17, 'no_contact_geometry': 14}
  * P5 f2575 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P6 f3038 (far): {'no_ball_sighting': 20, 'no_contact_geometry': 11}
  * P7 f3747 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P8 f4770 (far): {'no_contact_geometry': 21, 'no_ball_sighting': 10}
* **B_backfill**:
  * P1 f210 (far): {'no_ball_sighting': 16, 'no_contact_geometry': 15}
  * P2 f880 (far): {'no_ball_sighting': 20, 'no_contact_geometry': 11}
  * P3 f1395 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P4 f2154 (far): {'no_ball_sighting': 19, 'no_contact_geometry': 12}
  * P5 f2575 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P6 f3038 (far): {'no_ball_sighting': 20, 'no_contact_geometry': 11}
  * P7 f3747 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P8 f4770 (far): {'no_ball_sighting': 18, 'no_contact_geometry': 13}
* **B_backfill_narrow**:
  * P1 f210 (far): {'no_ball_sighting': 16, 'no_contact_geometry': 15}
  * P2 f880 (far): {'no_ball_sighting': 20, 'no_contact_geometry': 11}
  * P3 f1395 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P4 f2154 (far): {'no_ball_sighting': 19, 'no_contact_geometry': 12}
  * P5 f2575 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P6 f3038 (far): {'no_ball_sighting': 20, 'no_contact_geometry': 11}
  * P7 f3747 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P8 f4770 (far): {'no_ball_sighting': 18, 'no_contact_geometry': 13}
* **B_backfill_tight**:
  * P1 f210 (far): {'no_ball_sighting': 16, 'no_contact_geometry': 15}
  * P2 f880 (far): {'no_ball_sighting': 20, 'no_contact_geometry': 11}
  * P3 f1395 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P4 f2154 (far): {'no_ball_sighting': 19, 'no_contact_geometry': 12}
  * P5 f2575 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P6 f3038 (far): {'no_ball_sighting': 20, 'no_contact_geometry': 11}
  * P7 f3747 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P8 f4770 (far): {'no_ball_sighting': 18, 'no_contact_geometry': 13}
* **B_backfill_skip_suspect**:
  * P1 f210 (far): {'no_ball_sighting': 17, 'no_contact_geometry': 14}
  * P2 f880 (far): {'no_ball_sighting': 21, 'no_contact_geometry': 10}
  * P3 f1395 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P4 f2154 (far): {'no_ball_sighting': 19, 'no_contact_geometry': 12}
  * P5 f2575 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P6 f3038 (far): {'no_ball_sighting': 20, 'no_contact_geometry': 11}
  * P7 f3747 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P8 f4770 (far): {'no_ball_sighting': 18, 'no_contact_geometry': 13}
* **B_backfill_lookback12**:
  * P1 f210 (far): {'no_ball_sighting': 16, 'no_contact_geometry': 15}
  * P2 f880 (far): {'no_ball_sighting': 20, 'no_contact_geometry': 11}
  * P3 f1395 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P4 f2154 (far): {'no_ball_sighting': 19, 'no_contact_geometry': 12}
  * P5 f2575 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P6 f3038 (far): {'no_ball_sighting': 20, 'no_contact_geometry': 11}
  * P7 f3747 (near): {'no_contact_geometry': 22, 'min_contact_gap': 8}
  * P8 f4770 (far): {'no_ball_sighting': 18, 'no_contact_geometry': 13}

## Extra candidates (outside every GT contact window)

* **base** (13): [398, 930, 1039, 1587, 2195, 2414, 2445, 2494, 2617, 3265, 3595, 3639, 4067]
* **A_weak3_w30** (14): [398, 488, 930, 1039, 1587, 2195, 2414, 2445, 2494, 2617, 3265, 3595, 3639, 4067]
* **A_weak3_nowidth** (14): [398, 488, 930, 1039, 1587, 2195, 2414, 2445, 2494, 2617, 3265, 3595, 3639, 4067]
* **B_backfill** (14): [398, 930, 1019, 1039, 1587, 2195, 2414, 2445, 2494, 2617, 3265, 3595, 3639, 4067]
* **B_backfill_narrow** (14): [398, 930, 1019, 1039, 1587, 2195, 2414, 2445, 2494, 2617, 3265, 3595, 3639, 4067]
* **B_backfill_tight** (14): [398, 930, 1019, 1039, 1587, 2195, 2414, 2445, 2494, 2617, 3265, 3595, 3639, 4067]
* **B_backfill_skip_suspect** (14): [398, 930, 1019, 1039, 1587, 2195, 2414, 2445, 2494, 2617, 3265, 3595, 3639, 4067]
* **B_backfill_lookback12** (14): [398, 930, 1019, 1039, 1587, 2195, 2414, 2445, 2494, 2617, 3265, 3595, 3639, 4067]

## New locks vs baseline

* **A_weak3_w30**: [202, 376, 481, 615, 786, 878, 1213, 1672, 2150, 2277, 2731, 3036, 3357, 3444, 4094, 4551, 4571, 4638, 4758]
* **A_weak3_nowidth**: [202, 376, 481, 609, 786, 878, 998, 1085, 1173, 1213, 1672, 2150, 2277, 2365, 2731, 3026, 3357, 3444, 4094, 4139, 4217, 4551, 4571, 4608, 4638, 4758]
* **B_backfill**: []
* **B_backfill_narrow**: []
* **B_backfill_tight**: []
* **B_backfill_skip_suspect**: []
* **B_backfill_lookback12**: []
