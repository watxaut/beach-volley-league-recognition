# T5 step 1 - serve-time ball-track (re-)admission: DIAGNOSIS

Diagnostic only: no `src/` behaviour changed. Numbers come from `output/t4/dev_diag.jsonl` (T4 off-by-default `--diag-dump`), the GT serves in `ground_truth/video_ari_joan_8_first_points_annotations.json`, and the offline bootstrap replay in `scripts/probe_serve_admission.py`.

## Tracker gates in force

`lock_min_speed` = **8.0 px/f**, `lock_motion_window` = 5f, `lock_max_jump` = 90.0 px, `lock_max_pair_gap` = 2f, high tier >= 0.4, `boot_low_conf_floor` = 0.15. A bootstrap lock needs ONE pair of surviving (non-suspect, non-removed) sightings with `age <= lock_max_pair_gap`, `distance <= lock_max_jump` and `distance/age >= lock_min_speed`.

## Per-serve summary

| point | serve f | side | locked AT f? | first lock after serve (latency) | pre-contact toss: median px/f, det width px, first sighting | dets at contact f | dominant failing condition |
|---|---|---|---|---|---|---|---|---|
| 1 | 210 | far | **NO** | f216 (+6f) | 4.0 px/f, w16, f201 | 1 | no_detections x32, speed_below_lock_min_speed x11 |
| 2 | 880 | far | **NO** | f890 (+10f) | 6.7 px/f, w14, f877 | 1 | no_detections x37, speed_below_lock_min_speed x10 |
| 3 | 1395 | near | yes | f1395 (+0f) | 11.5 px/f, w50, f1355 | 2 | no_plausible_survivor x14, no_detections x6 |
| 4 | 2154 | far | **NO** | f2159 (+5f) | 2.0 px/f, w15, f2145 | 0 | no_detections x39, no_previous_sighting_in_window x4 |
| 5 | 2575 | near | yes | f2575 (+0f) | 16.8 px/f, w51, f2541 | 1 | no_detections x7, no_previous_sighting_in_window x1 |
| 6 | 3038 | far | **NO** | f3042 (+4f) | 1.6 px/f, w15, f3025 | 0 | no_detections x33, no_previous_sighting_in_window x9 |
| 7 | 3747 | near | yes | f3747 (+0f) | 7.3 px/f, w50, f3710 | 1 | no_detections x12, no_previous_sighting_in_window x10 |
| 8 | 4770 | far | **NO** | f4776 (+6f) | 3.5 px/f, w15, f4757 | 0 | no_detections x33, no_previous_sighting_in_window x8 |

## Per-frame detail (each serve window)

### P1 serve f210 (far team B), window f170-f250

| f | dets (x,y w conf persist flags) | tracker | replay | obs gap-1 speed | best pair speed | dist | fail |
|---|---|---|---|---|---|---|---|
| 170 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 171 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 172 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 173 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 174 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 175 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 176 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 177 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 178 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 179 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 180 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 181 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 182 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 183 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 184 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 185 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 186 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 187 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 188 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 189 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 190 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 191 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 192 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 193 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 194 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 195 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 196 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 197 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 198 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 199 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 200 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 201 | (861,470 w18 c0.22 p0.00) | none/unlocked_no_motion | - | - | - | - | no_previous_sighting_in_window |
| 202 | (860,463 w16 c0.49 p0.03) | none/unlocked_no_motion | - | 7.1 | - | - | no_previous_sighting_in_window |
| 203 | (860,458 w15 c0.55 p0.05) | none/unlocked_no_motion | - | 4.5 | 4.5 | 5 | speed_below_lock_min_speed |
| 204 | (860,454 w16 c0.56 p0.07) | none/unlocked_no_motion | - | 4.0 | 4.2 | 8 | speed_below_lock_min_speed |
| 205 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 206 | (862,446 w15 c0.54 p0.10) | none/unlocked_no_motion | - | 8.6 | 4.3 | 9 | speed_below_lock_min_speed |
| 207 | (861,445 w16 c0.66 p0.12) | none/unlocked_no_motion | - | 1.1 | 1.1 | 1 | speed_below_lock_min_speed |
| 208 | (860,444 w17 c0.64 p0.12) | none/unlocked_no_motion | - | 1.1 | 1.1 | 1 | speed_below_lock_min_speed |
| 209 | (860,444 w17 c0.61 p0.15) | none/unlocked_no_motion | - | 0.5 | 0.8 | 2 | speed_below_lock_min_speed |
| 210 | (861,444 w16 c0.56 p0.17) | none/unlocked_no_motion | - | 0.7 | 0.7 | 1 | speed_below_lock_min_speed |
| 211 | (860,444 w17 c0.72 p0.20) | none/unlocked_no_motion | - | 1.5 | 1.5 | 2 | speed_below_lock_min_speed |
| 212 | (861,445 w16 c0.70 p0.25) | none/unlocked_no_motion | - | 1.8 | 1.8 | 2 | speed_below_lock_min_speed |
| 213 | (862,446 w15 c0.58 p0.28) | none/unlocked_no_motion | - | 1.1 | 1.4 | 3 | speed_below_lock_min_speed |
| 214 | (862,446 w16 c0.63 p0.30S) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 215 | (869,437 w16 c0.54 p0.28) | none/unlocked_no_motion | - | 11.7 | 5.9 | 12 | speed_below_lock_min_speed |
| 216 | (876,423 w16 c0.52 p0.03) | tracked/bootstrap_locked | lock | 15.7 | - | - | - |
| 217 | (882,412 w15 c0.55 p0.03) | tracked/locked_admitted | lock | 12.3 | - | - | - |
| 218 | (888,399 w17 c0.22 p0.03) | tracked/low_floor_admitted | lock | 14.3 | - | - | - |
| 219 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 220 | (902,376 w16 c0.31 p0.00) | none/out_of_view_reentry_wait | lock | 26.8 | - | - | - |
| 221 | (910,366 w19 c0.77 p0.03) | tracked/locked_admitted | lock | 12.5 | - | - | - |
| 222 | (918,358 w19 c0.74 p0.05) | tracked/locked_admitted | lock | 12.0 | - | - | - |
| 223 | (926,348 w21 c0.69 p0.05) | tracked/locked_admitted | lock | 12.8 | - | - | - |
| 224 | (935,340 w20 c0.74 p0.03) | tracked/locked_admitted | lock | 12.4 | - | - | - |
| 225 | (944,332 w21 c0.76 p0.05) | tracked/locked_admitted | lock | 12.4 | - | - | - |
| 226 | (953,324 w22 c0.82 p0.05) | tracked/locked_admitted | lock | 11.7 | - | - | - |
| 227 | (964,316 w21 c0.83 p0.05) | tracked/locked_admitted | lock | 12.6 | - | - | - |
| 228 | (974,312 w22 c0.86 p0.05) | tracked/locked_admitted | lock | 11.6 | - | - | - |
| 229 | (984,306 w22 c0.84 p0.05) | tracked/locked_admitted | lock | 11.4 | - | - | - |
| 230 | (994,302 w23 c0.87 p0.05) | tracked/locked_admitted | lock | 11.1 | - | - | - |
| 231 | (1006,300 w23 c0.88 p0.05) | tracked/locked_admitted | lock | 12.4 | - | - | - |
| 232 | (1018,299 w24 c0.86 p0.05) | tracked/locked_admitted | lock | 11.5 | - | - | - |
| 233 | (1031,299 w24 c0.89 p0.05) | tracked/locked_admitted | lock | 13.0 | - | - | - |
| 234 | (1044,300 w24 c0.88 p0.03) | tracked/locked_admitted | lock | 13.0 | - | - | - |
| 235 | (1058,301 w26 c0.90 p0.03) | tracked/locked_admitted | lock | 14.1 | - | - | - |
| 236 | (1072,304 w26 c0.85 p0.03) | tracked/locked_admitted | lock | 14.3 | - | - | - |
| 237 | (1087,309 w26 c0.83 p0.03) | tracked/locked_admitted | lock | 15.8 | - | - | - |
| 238 | (1104,315 w28 c0.88 p0.03) | tracked/locked_admitted | lock | 18.0 | - | - | - |
| 239 | (1120,322 w28 c0.82 p0.03) | tracked/locked_admitted | lock | 17.7 | - | - | - |
| 240 | (1138,332 w28 c0.81 p0.03) | tracked/locked_admitted | lock | 20.6 | - | - | - |
| 241 | (1158,344 w31 c0.78 p0.03) | tracked/locked_admitted | lock | 22.9 | - | - | - |
| 242 | (1179,358 w28 c0.78 p0.00) | tracked/locked_admitted | lock | 25.1 | - | - | - |
| 243 | (1198,376 w31 c0.85 p0.00) | tracked/locked_admitted | lock | 27.2 | - | - | - |
| 244 | (1220,396 w28 c0.85 p0.00) | tracked/locked_admitted | lock | 29.4 | - | - | - |
| 245 | (1242,418 w30 c0.80 p0.00) | tracked/locked_admitted | lock | 31.1 | - | - | - |
| 246 | (1266,446 w31 c0.82 p0.00) | tracked/locked_admitted | lock | 35.8 | - | - | - |
| 247 | (1290,473 w33 c0.25 p0.00) | tracked/low_floor_admitted | lock | 36.5 | - | - | - |
| 248 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 249 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 250 | - | predicted/coast_predicted | lock | - | - | - | - |

### P2 serve f880 (far team B), window f840-f920

| f | dets (x,y w conf persist flags) | tracker | replay | obs gap-1 speed | best pair speed | dist | fail |
|---|---|---|---|---|---|---|---|
| 840 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 841 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 842 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 843 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 844 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 845 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 846 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 847 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 848 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 849 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 850 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 851 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 852 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 853 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 854 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 855 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 856 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 857 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 858 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 859 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 860 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 861 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 862 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 863 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 864 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 865 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 866 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 867 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 868 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 869 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 870 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 871 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 872 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 873 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 874 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 875 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 876 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 877 | (866,462 w14 c0.40 p0.00) | none/unlocked_no_motion | - | - | - | - | no_previous_sighting_in_window |
| 878 | (866,456 w11 c0.24 p0.03) | none/unlocked_no_motion | - | 5.5 | - | - | no_previous_sighting_in_window |
| 879 | (868,450 w14 c0.58 p0.05) (867,453 w14 c0.24 p0.05) | none/unlocked_no_motion | - | 6.7 | 6.1 | 12 | speed_below_lock_min_speed |
| 880 | (867,446 w14 c0.42 p0.07) | none/unlocked_no_motion | - | 4.1 | 4.1 | 4 | speed_below_lock_min_speed |
| 881 | (868,444 w16 c0.71 p0.10) | none/unlocked_no_motion | - | 1.8 | 2.8 | 6 | speed_below_lock_min_speed |
| 882 | (868,443 w17 c0.74 p0.12) | none/unlocked_no_motion | - | 1.1 | 1.5 | 3 | speed_below_lock_min_speed |
| 883 | (868,443 w16 c0.71 p0.15) | none/unlocked_no_motion | - | 0.5 | 0.5 | 0 | speed_below_lock_min_speed |
| 884 | (868,443 w16 c0.70 p0.17) | none/unlocked_no_motion | - | 0.0 | 0.2 | 0 | speed_below_lock_min_speed |
| 885 | (868,443 w16 c0.69 p0.20) | none/unlocked_no_motion | - | 0.0 | 0.0 | 0 | speed_below_lock_min_speed |
| 886 | (868,444 w17 c0.71 p0.23) | none/unlocked_no_motion | - | 0.7 | 0.7 | 1 | speed_below_lock_min_speed |
| 887 | (868,444 w16 c0.66 p0.25) | none/unlocked_no_motion | - | 1.1 | 1.1 | 1 | speed_below_lock_min_speed |
| 888 | (868,446 w15 c0.42 p0.28) | none/unlocked_no_motion | - | 2.1 | 2.1 | 2 | speed_below_lock_min_speed |
| 889 | (868,442 w15 c0.61 p0.30S) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 890 | (872,430 w17 c0.52 p0.28) | tracked/bootstrap_locked | lock | 17.5 | - | - | - |
| 891 | (872,418 w18 c0.70 p0.05) | tracked/locked_admitted | lock | 11.5 | - | - | - |
| 892 | - | none/coast_short_trajectory | lock | - | - | - | - |
| 893 | (876,396 w17 c0.69 p0.03) | tracked/locked_admitted | lock | 22.8 | - | - | - |
| 894 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 895 | (879,374 w20 c0.68 p0.03) | tracked/locked_admitted | lock | 22.3 | - | - | - |
| 896 | (881,364 w22 c0.70 p0.03) | tracked/locked_admitted | lock | 10.2 | - | - | - |
| 897 | (883,354 w20 c0.76 p0.05) | tracked/locked_admitted | lock | 9.2 | - | - | - |
| 898 | (886,346 w20 c0.76 p0.05) | tracked/locked_admitted | lock | 9.5 | - | - | - |
| 899 | (889,335 w20 c0.83 p0.05) | tracked/locked_admitted | lock | 10.9 | - | - | - |
| 900 | (890,327 w21 c0.83 p0.05) | tracked/locked_admitted | lock | 8.1 | - | - | - |
| 901 | (893,319 w22 c0.82 p0.05) | tracked/locked_admitted | lock | 8.4 | - | - | - |
| 902 | (895,312 w24 c0.81 p0.07) | tracked/locked_admitted | lock | 7.8 | - | - | - |
| 903 | (897,304 w22 c0.85 p0.07) | tracked/locked_admitted | lock | 7.8 | - | - | - |
| 904 | (898,298 w23 c0.88 p0.07) | tracked/locked_admitted | lock | 6.7 | - | - | - |
| 905 | (901,292 w24 c0.89 p0.07) | tracked/locked_admitted | lock | 6.5 | - | - | - |
| 906 | (904,286 w25 c0.88 p0.07) | tracked/locked_admitted | lock | 6.0 | - | - | - |
| 907 | (905,282 w24 c0.85 p0.10) | tracked/locked_admitted | lock | 4.7 | - | - | - |
| 908 | (906,278 w26 c0.84 p0.10) | tracked/locked_admitted | lock | 3.2 | - | - | - |
| 909 | (908,277 w26 c0.87 p0.12) | tracked/locked_admitted | lock | 2.5 | - | - | - |
| 910 | (910,276 w26 c0.89 p0.15) | tracked/locked_admitted | lock | 2.2 | - | - | - |
| 911 | (912,276 w27 c0.90 p0.17) | tracked/locked_admitted | lock | 1.6 | - | - | - |
| 912 | (913,280 w28 c0.89 p0.20) | tracked/locked_admitted | lock | 3.8 | - | - | - |
| 913 | (914,284 w29 c0.86 p0.23) | tracked/locked_admitted | lock | 3.8 | - | - | - |
| 914 | (916,290 w30 c0.87 p0.28) | tracked/locked_admitted | lock | 7.2 | - | - | - |
| 915 | (918,298 w31 c0.85 p0.30S) | tracked/locked_admitted | lock | - | - | - | - |
| 916 | (918,308 w31 c0.85 p0.17) | tracked/locked_admitted | lock | 17.7 | - | - | - |
| 917 | (920,321 w33 c0.82 p0.05) | tracked/locked_admitted | lock | 13.2 | - | - | - |
| 918 | (923,336 w34 c0.82 p0.03) | tracked/locked_admitted | lock | 15.2 | - | - | - |
| 919 | (924,355 w34 c0.85 p0.03) | tracked/locked_admitted | lock | 19.0 | - | - | - |
| 920 | (926,375 w33 c0.83 p0.03) | tracked/locked_admitted | lock | 20.2 | - | - | - |

### P3 serve f1395 (near team A), window f1355-f1435

| f | dets (x,y w conf persist flags) | tracker | replay | obs gap-1 speed | best pair speed | dist | fail |
|---|---|---|---|---|---|---|---|
| 1355 | (708,776 w28 c0.50 p1.00SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1356 | (708,777 w28 c0.50 p1.00SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1357 | (708,778 w28 c0.50 p1.00SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1358 | (708,777 w29 c0.52 p1.00SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1359 | (708,778 w28 c0.58 p1.00SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1360 | (708,777 w28 c0.61 p1.00SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1361 | (708,777 w29 c0.60 p1.00SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1362 | (708,778 w29 c0.62 p1.00SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1363 | (709,778 w30 c0.59 p1.00SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1364 | (710,778 w31 c0.70 p1.00SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1365 | (710,778 w31 c0.69 p1.00SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1366 | (712,780 w34 c0.59 p1.00SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1367 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 1368 | (716,780 w42 c0.67 p0.97SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1369 | (718,780 w47 c0.70 p0.97SR) | none/unlocked_no_motion | - | - | - | - | no_plausible_survivor |
| 1370 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 1371 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 1372 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 1373 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 1374 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 1375 | (854,455 w49 c0.72 p0.00) | none/unlocked_no_motion | - | - | - | - | no_previous_sighting_in_window |
| 1376 | (855,423 w46 c0.83 p0.00) | tracked/bootstrap_locked | lock | 32.0 | - | - | - |
| 1377 | (852,394 w50 c0.80 p0.00) | tracked/locked_admitted | lock | 28.7 | - | - | - |
| 1378 | (851,368 w50 c0.82 p0.00) | tracked/locked_admitted | lock | 26.0 | - | - | - |
| 1379 | (852,344 w50 c0.82 p0.03) | tracked/locked_admitted | lock | 24.5 | - | - | - |
| 1380 | (852,322 w50 c0.84 p0.03) (908,454 w27 c0.24 p0.00) (702,772 w28 c0.21 p0.72SR) | tracked/locked_admitted | lock | 21.5 | - | - | - |
| 1381 | (851,304 w50 c0.84 p0.03) (703,772 w32 c0.21 p0.72SR) | tracked/locked_admitted | lock | 19.0 | - | - | - |
| 1382 | (852,286 w51 c0.87 p0.03) (910,442 w26 c0.19 p0.03) | tracked/locked_admitted | lock | 17.0 | - | - | - |
| 1383 | (851,272 w50 c0.87 p0.03) | tracked/locked_admitted | lock | 14.5 | - | - | - |
| 1384 | (850,261 w51 c0.87 p0.03) | tracked/locked_admitted | lock | 11.0 | - | - | - |
| 1385 | (850,254 w51 c0.87 p0.05) | tracked/locked_admitted | lock | 7.5 | - | - | - |
| 1386 | (850,248 w51 c0.86 p0.07) | tracked/locked_admitted | lock | 6.1 | - | - | - |
| 1387 | (848,244 w51 c0.87 p0.07) | tracked/locked_admitted | lock | 4.1 | - | - | - |
| 1388 | (848,242 w51 c0.87 p0.10) | tracked/locked_admitted | lock | 1.0 | - | - | - |
| 1389 | (850,244 w51 c0.87 p0.12) | tracked/locked_admitted | lock | 1.8 | - | - | - |
| 1390 | (848,248 w49 c0.89 p0.17) (766,458 w27 c0.73 p0.00) (826,401 w17 c0.16 p0.00) | tracked/locked_admitted | lock | 4.0 | - | - | - |
| 1391 | (848,254 w49 c0.88 p0.20) | tracked/locked_admitted | lock | 7.0 | - | - | - |
| 1392 | (847,264 w48 c0.87 p0.25) (764,468 w25 c0.43 p0.03) | tracked/locked_admitted | lock | 10.0 | - | - | - |
| 1393 | (847,276 w48 c0.87 p0.15) | tracked/locked_admitted | lock | 11.5 | - | - | - |
| 1394 | (846,292 w49 c0.87 p0.10) | tracked/locked_admitted | lock | 15.5 | - | - | - |
| 1395 | (846,306 w49 c0.87 p0.10) (816,407 w21 c0.20 p0.03) | tracked/locked_admitted | lock | 15.0 | - | - | - |
| 1396 | (846,326 w51 c0.76 p0.10) | tracked/locked_admitted | lock | 19.0 | - | - | - |
| 1397 | (860,322 w47 c0.85 p0.12) | tracked/locked_admitted | lock | 14.6 | - | - | - |
| 1398 | (884,304 w46 c0.89 p0.00) | tracked/locked_admitted | lock | 29.3 | - | - | - |
| 1399 | (907,288 w44 c0.88 p0.00) | tracked/locked_admitted | lock | 28.3 | - | - | - |
| 1400 | (927,275 w44 c0.87 p0.03) | tracked/locked_admitted | lock | 23.6 | - | - | - |
| 1401 | (945,264 w42 c0.87 p0.03) | tracked/locked_admitted | lock | 20.8 | - | - | - |
| 1402 | (962,258 w38 c0.89 p0.03) | tracked/locked_admitted | lock | 18.4 | - | - | - |
| 1403 | (978,253 w37 c0.87 p0.03) | tracked/locked_admitted | lock | 16.1 | - | - | - |
| 1404 | (992,252 w36 c0.88 p0.03) | tracked/locked_admitted | lock | 14.5 | - | - | - |
| 1405 | (1004,252 w35 c0.88 p0.03) | tracked/locked_admitted | lock | 11.5 | - | - | - |
| 1406 | (1015,254 w34 c0.88 p0.05) | tracked/locked_admitted | lock | 11.7 | - | - | - |
| 1407 | (1024,256 w32 c0.90 p0.05) | tracked/locked_admitted | lock | 9.3 | - | - | - |
| 1408 | (1034,261 w31 c0.88 p0.05) | tracked/locked_admitted | lock | 10.7 | - | - | - |
| 1409 | (1042,266 w30 c0.88 p0.05) | tracked/locked_admitted | lock | 9.9 | - | - | - |
| 1410 | (1049,272 w30 c0.86 p0.05) | tracked/locked_admitted | lock | 9.6 | - | - | - |
| 1411 | (1056,280 w29 c0.89 p0.05) | tracked/locked_admitted | lock | 10.3 | - | - | - |
| 1412 | (1063,288 w28 c0.85 p0.05) | tracked/locked_admitted | lock | 10.7 | - | - | - |
| 1413 | (1070,296 w27 c0.87 p0.05) | tracked/locked_admitted | lock | 10.7 | - | - | - |
| 1414 | (1075,306 w26 c0.84 p0.05) | tracked/locked_admitted | lock | 11.4 | - | - | - |
| 1415 | (1081,316 w26 c0.88 p0.05) | tracked/locked_admitted | lock | 11.2 | - | - | - |
| 1416 | (1087,326 w26 c0.83 p0.05) | tracked/locked_admitted | lock | 12.1 | - | - | - |
| 1417 | (1092,337 w25 c0.90 p0.05) | tracked/locked_admitted | lock | 11.9 | - | - | - |
| 1418 | (1098,348 w25 c0.86 p0.05) | tracked/locked_admitted | lock | 11.6 | - | - | - |
| 1419 | (1103,358 w24 c0.86 p0.05) | tracked/locked_admitted | lock | 12.3 | - | - | - |
| 1420 | (1108,368 w22 c0.73 p0.05) | tracked/locked_admitted | lock | 10.7 | - | - | - |
| 1421 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 1422 | (1116,395 w21 c0.68 p0.00) | tracked/locked_admitted | lock | 28.0 | - | - | - |
| 1423 | (1121,406 w22 c0.74 p0.03) | tracked/locked_admitted | lock | 12.7 | - | - | - |
| 1424 | (1124,419 w19 c0.73 p0.03) | tracked/locked_admitted | lock | 13.0 | - | - | - |
| 1425 | (1126,432 w17 c0.69 p0.03) | tracked/locked_admitted | lock | 13.6 | - | - | - |
| 1426 | (1132,445 w19 c0.73 p0.03) | tracked/locked_admitted | lock | 13.5 | - | - | - |
| 1427 | (1132,459 w21 c0.76 p0.03) | tracked/locked_admitted | lock | 14.0 | - | - | - |
| 1428 | (1134,472 w19 c0.75 p0.03) | tracked/locked_admitted | lock | 13.6 | - | - | - |
| 1429 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 1430 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 1431 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 1432 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 1433 | (1139,462 w18 c0.74 p0.07) | tracked/locked_admitted | lock | 11.9 | - | - | - |
| 1434 | (1136,438 w17 c0.71 p0.12) | tracked/locked_admitted | lock | 23.1 | - | - | - |
| 1435 | (1135,415 w18 c0.70 p0.10) | tracked/locked_admitted | lock | 23.5 | - | - | - |

### P4 serve f2154 (far team B), window f2114-f2194

| f | dets (x,y w conf persist flags) | tracker | replay | obs gap-1 speed | best pair speed | dist | fail |
|---|---|---|---|---|---|---|---|
| 2114 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2115 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2116 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2117 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2118 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2119 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2120 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2121 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2122 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2123 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2124 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2125 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2126 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2127 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2128 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2129 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2130 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2131 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2132 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2133 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2134 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2135 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2136 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2137 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2138 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2139 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2140 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2141 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2142 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2143 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2144 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2145 | (952,412 w15 c0.43 p0.00) (950,412 w15 c0.26 p0.00) | none/unlocked_no_motion | - | - | - | - | no_previous_sighting_in_window |
| 2146 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2147 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2148 | (952,413 w15 c0.33 p0.03) | none/unlocked_no_motion | - | 1.1 | - | - | no_previous_sighting_in_window |
| 2149 | (952,413 w15 c0.39 p0.05) | none/unlocked_no_motion | - | 0.0 | 0.0 | 0 | no_previous_sighting_in_window |
| 2150 | (952,415 w15 c0.49 p0.07) (950,416 w15 c0.25 p0.07) | none/unlocked_no_motion | - | 2.0 | 4.6 | 5 | no_pair_within_lock_max_pair_gap |
| 2151 | (950,420 w17 c0.68 p0.10) | none/unlocked_no_motion | - | 4.9 | 4.9 | 5 | speed_below_lock_min_speed |
| 2152 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2153 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2154 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2155 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2156 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2157 | (939,396 w20 c0.71 p0.10) | none/unlocked_no_motion | - | 26.6 | - | - | no_previous_sighting_in_window |
| 2158 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2159 | (932,373 w18 c0.59 p0.03) | tracked/bootstrap_locked | lock | 23.6 | - | - | - |
| 2160 | (926,366 w21 c0.77 p0.03) | tracked/locked_admitted | lock | 8.5 | - | - | - |
| 2161 | (920,360 w19 c0.79 p0.05) | tracked/locked_admitted | lock | 9.2 | - | - | - |
| 2162 | (918,352 w21 c0.72 p0.05) | tracked/locked_admitted | lock | 8.5 | - | - | - |
| 2163 | (910,348 w21 c0.73 p0.07) | tracked/locked_admitted | lock | 7.6 | - | - | - |
| 2164 | (904,344 w20 c0.69 p0.07) | tracked/locked_admitted | lock | 7.6 | - | - | - |
| 2165 | (898,340 w20 c0.77 p0.07) | tracked/locked_admitted | lock | 7.2 | - | - | - |
| 2166 | (894,338 w21 c0.79 p0.07) | tracked/locked_admitted | lock | 5.1 | - | - | - |
| 2167 | (888,336 w20 c0.79 p0.07) | tracked/locked_admitted | lock | 5.9 | - | - | - |
| 2168 | (882,336 w21 c0.78 p0.10) | tracked/locked_admitted | lock | 6.5 | - | - | - |
| 2169 | (876,336 w21 c0.80 p0.10) | tracked/locked_admitted | lock | 5.0 | - | - | - |
| 2170 | (869,338 w22 c0.82 p0.10) | tracked/locked_admitted | lock | 7.8 | - | - | - |
| 2171 | (863,340 w22 c0.85 p0.07) | tracked/locked_admitted | lock | 6.5 | - | - | - |
| 2172 | (858,344 w23 c0.79 p0.07) | tracked/locked_admitted | lock | 6.3 | - | - | - |
| 2173 | (850,348 w23 c0.86 p0.07) | tracked/locked_admitted | lock | 8.3 | - | - | - |
| 2174 | (843,356 w24 c0.83 p0.05) | tracked/locked_admitted | lock | 11.0 | - | - | - |
| 2175 | (836,361 w22 c0.80 p0.05) | tracked/locked_admitted | lock | 8.6 | - | - | - |
| 2176 | (829,370 w22 c0.82 p0.05) | tracked/locked_admitted | lock | 11.4 | - | - | - |
| 2177 | (822,378 w21 c0.62 p0.05) | tracked/locked_admitted | lock | 11.3 | - | - | - |
| 2178 | (814,395 w21 c0.76 p0.03) | tracked/locked_admitted | lock | 17.9 | - | - | - |
| 2179 | (811,405 w22 c0.75 p0.03) | tracked/locked_admitted | lock | 10.6 | - | - | - |
| 2180 | (808,415 w23 c0.79 p0.05) | tracked/locked_admitted | lock | 10.6 | - | - | - |
| 2181 | (804,428 w25 c0.80 p0.05) | tracked/locked_admitted | lock | 14.1 | - | - | - |
| 2182 | (801,443 w22 c0.71 p0.03) | tracked/locked_admitted | lock | 14.7 | - | - | - |
| 2183 | (798,458 w21 c0.58 p0.03) | tracked/locked_admitted | lock | 15.9 | - | - | - |
| 2184 | (796,466 w23 c0.75 p0.05) | tracked/locked_admitted | lock | 8.1 | - | - | - |
| 2185 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 2186 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 2187 | (630,704 w67 c0.17 p0.00) | none/out_of_view_reentry_wait | lock | 289.8 | - | - | - |
| 2188 | (788,503 w23 c0.72 p0.00) (634,704 w76 c0.30 p0.03) | tracked/locked_admitted | lock | 255.7 | - | - | - |
| 2189 | (786,512 w25 c0.63 p0.03) (630,706 w67 c0.19 p0.05) | tracked/locked_admitted | lock | 9.7 | - | - | - |
| 2190 | (785,526 w24 c0.79 p0.05) | tracked/locked_admitted | lock | 13.1 | - | - | - |
| 2191 | (784,538 w26 c0.83 p0.03) | tracked/locked_admitted | lock | 12.5 | - | - | - |
| 2192 | (782,552 w25 c0.84 p0.03) (620,704 w51 c0.20 p0.07) | tracked/locked_admitted | lock | 13.7 | - | - | - |
| 2193 | (780,568 w23 c0.86 p0.03) (622,702 w54 c0.18 p0.10) | tracked/locked_admitted | lock | 16.1 | - | - | - |
| 2194 | (778,584 w24 c0.87 p0.03) | tracked/locked_admitted | lock | 17.1 | - | - | - |

### P5 serve f2575 (near team A), window f2535-f2615

| f | dets (x,y w conf persist flags) | tracker | replay | obs gap-1 speed | best pair speed | dist | fail |
|---|---|---|---|---|---|---|---|
| 2535 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2536 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2537 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2538 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2539 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2540 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2541 | (588,566 w20 c0.53 p0.00) | none/unlocked_no_motion | - | - | - | - | no_previous_sighting_in_window |
| 2542 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2543 | (604,562 w28 c0.68 p0.03) | tracked/bootstrap_locked | lock | 16.8 | - | - | - |
| 2544 | (614,554 w31 c0.70 p0.03) | tracked/locked_admitted | lock | 12.4 | - | - | - |
| 2545 | (624,539 w35 c0.66 p0.03) | tracked/locked_admitted | lock | 17.6 | - | - | - |
| 2546 | (632,520 w39 c0.69 p0.03) | tracked/locked_admitted | lock | 20.6 | - | - | - |
| 2547 | (638,500 w44 c0.70 p0.03) | tracked/locked_admitted | lock | 21.7 | - | - | - |
| 2548 | (643,469 w48 c0.78 p0.00) | tracked/locked_admitted | lock | 30.9 | - | - | - |
| 2549 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 2550 | (650,402 w51 c0.78 p0.00) | tracked/locked_admitted | lock | 67.3 | - | - | - |
| 2551 | (647,372 w48 c0.80 p0.00) | tracked/locked_admitted | lock | 29.6 | - | - | - |
| 2552 | (645,342 w48 c0.84 p0.00) | tracked/locked_admitted | lock | 31.1 | - | - | - |
| 2553 | (644,314 w50 c0.83 p0.00) | tracked/locked_admitted | lock | 27.5 | - | - | - |
| 2554 | (642,288 w50 c0.84 p0.00) | tracked/locked_admitted | lock | 25.6 | - | - | - |
| 2555 | (639,265 w52 c0.85 p0.03) | tracked/locked_admitted | lock | 23.7 | - | - | - |
| 2556 | (638,244 w51 c0.87 p0.03) | tracked/locked_admitted | lock | 20.6 | - | - | - |
| 2557 | (636,228 w53 c0.88 p0.03) | tracked/locked_admitted | lock | 17.1 | - | - | - |
| 2558 | (634,212 w51 c0.88 p0.03) | tracked/locked_admitted | lock | 15.1 | - | - | - |
| 2559 | (633,200 w52 c0.88 p0.03) | tracked/locked_admitted | lock | 13.0 | - | - | - |
| 2560 | (632,189 w51 c0.87 p0.05) | tracked/locked_admitted | lock | 10.6 | - | - | - |
| 2561 | (630,181 w51 c0.84 p0.05) | tracked/locked_admitted | lock | 8.1 | - | - | - |
| 2562 | (629,176 w52 c0.87 p0.07) | tracked/locked_admitted | lock | 5.2 | - | - | - |
| 2563 | (628,174 w53 c0.86 p0.07) | tracked/locked_admitted | lock | 2.1 | - | - | - |
| 2564 | (626,174 w53 c0.88 p0.10) | tracked/locked_admitted | lock | 1.0 | - | - | - |
| 2565 | (626,176 w53 c0.88 p0.15) | tracked/locked_admitted | lock | 1.8 | - | - | - |
| 2566 | (624,182 w53 c0.89 p0.17) | tracked/locked_admitted | lock | 6.3 | - | - | - |
| 2567 | (623,189 w52 c0.89 p0.20) | tracked/locked_admitted | lock | 7.0 | - | - | - |
| 2568 | (622,200 w52 c0.87 p0.20) | tracked/locked_admitted | lock | 11.0 | - | - | - |
| 2569 | (620,212 w52 c0.85 p0.12) | tracked/locked_admitted | lock | 12.2 | - | - | - |
| 2570 | (618,228 w51 c0.86 p0.07) | tracked/locked_admitted | lock | 16.1 | - | - | - |
| 2571 | (616,246 w51 c0.88 p0.05) | tracked/locked_admitted | lock | 18.1 | - | - | - |
| 2572 | (614,265 w51 c0.84 p0.05) | tracked/locked_admitted | lock | 19.1 | - | - | - |
| 2573 | (614,255 w52 c0.81 p0.05) | tracked/locked_admitted | lock | 10.0 | - | - | - |
| 2574 | (608,225 w49 c0.86 p0.07) | tracked/locked_admitted | lock | 30.5 | - | - | - |
| 2575 | (604,202 w46 c0.88 p0.10) | tracked/locked_admitted | lock | 23.9 | - | - | - |
| 2576 | (601,182 w44 c0.86 p0.07) | tracked/locked_admitted | lock | 19.7 | - | - | - |
| 2577 | (598,166 w44 c0.86 p0.03) | tracked/locked_admitted | lock | 16.8 | - | - | - |
| 2578 | (596,152 w41 c0.91 p0.03) | tracked/locked_admitted | lock | 13.2 | - | - | - |
| 2579 | (594,142 w41 c0.91 p0.05) | tracked/locked_admitted | lock | 11.0 | - | - | - |
| 2580 | (593,135 w38 c0.88 p0.05) | tracked/locked_admitted | lock | 6.7 | - | - | - |
| 2581 | (590,130 w37 c0.90 p0.07) | tracked/locked_admitted | lock | 6.0 | - | - | - |
| 2582 | (590,127 w37 c0.90 p0.07) | tracked/locked_admitted | lock | 2.7 | - | - | - |
| 2583 | (588,126 w37 c0.87 p0.10) | tracked/locked_admitted | lock | 1.1 | - | - | - |
| 2584 | (588,127 w35 c0.88 p0.12) | tracked/locked_admitted | lock | 1.1 | - | - | - |
| 2585 | (584,130 w32 c0.87 p0.15) | tracked/locked_admitted | lock | 4.3 | - | - | - |
| 2586 | (583,132 w32 c0.86 p0.20) | tracked/locked_admitted | lock | 3.2 | - | - | - |
| 2587 | (582,138 w31 c0.88 p0.23) | tracked/locked_admitted | lock | 5.7 | - | - | - |
| 2588 | (580,144 w32 c0.86 p0.25) | tracked/locked_admitted | lock | 6.7 | - | - | - |
| 2589 | (579,152 w30 c0.88 p0.20) | tracked/locked_admitted | lock | 7.6 | - | - | - |
| 2590 | (577,160 w30 c0.88 p0.12) | tracked/locked_admitted | lock | 8.7 | - | - | - |
| 2591 | (576,170 w29 c0.89 p0.07) | tracked/locked_admitted | lock | 9.1 | - | - | - |
| 2592 | (573,180 w28 c0.87 p0.05) | tracked/locked_admitted | lock | 10.8 | - | - | - |
| 2593 | (572,191 w28 c0.86 p0.05) | tracked/locked_admitted | lock | 11.0 | - | - | - |
| 2594 | (571,202 w28 c0.84 p0.05) | tracked/locked_admitted | lock | 11.5 | - | - | - |
| 2595 | (570,215 w27 c0.84 p0.05) | tracked/locked_admitted | lock | 12.6 | - | - | - |
| 2596 | (568,228 w25 c0.87 p0.03) | tracked/locked_admitted | lock | 12.5 | - | - | - |
| 2597 | (568,242 w26 c0.88 p0.03) | tracked/locked_admitted | lock | 14.5 | - | - | - |
| 2598 | (568,256 w26 c0.86 p0.03) | tracked/locked_admitted | lock | 14.0 | - | - | - |
| 2599 | (568,270 w25 c0.85 p0.03) | tracked/locked_admitted | lock | 14.5 | - | - | - |
| 2600 | (568,286 w25 c0.83 p0.03) | tracked/locked_admitted | lock | 15.0 | - | - | - |
| 2601 | (568,300 w24 c0.87 p0.03) | tracked/locked_admitted | lock | 15.0 | - | - | - |
| 2602 | (568,318 w22 c0.80 p0.03) | tracked/locked_admitted | lock | 17.5 | - | - | - |
| 2603 | (568,334 w21 c0.79 p0.03) | tracked/locked_admitted | lock | 16.0 | - | - | - |
| 2604 | (569,352 w20 c0.78 p0.03) | tracked/locked_admitted | lock | 17.5 | - | - | - |
| 2605 | (569,368 w22 c0.76 p0.03) | tracked/locked_admitted | lock | 17.0 | - | - | - |
| 2606 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 2607 | (566,404 w23 c0.75 p0.00) | tracked/locked_admitted | lock | 35.1 | - | - | - |
| 2608 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 2609 | (565,441 w22 c0.20 p0.00) | none/out_of_view_reentry_wait | lock | 37.5 | - | - | - |
| 2610 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 2611 | - | predicted/coast_predicted | lock | - | - | - | - |
| 2612 | (564,500 w24 c0.68 p0.00) | tracked/locked_admitted | lock | 59.0 | - | - | - |
| 2613 | (561,518 w18 c0.56 p0.03) | tracked/locked_admitted | lock | 18.7 | - | - | - |
| 2614 | (558,538 w21 c0.75 p0.03) | tracked/locked_admitted | lock | 20.2 | - | - | - |
| 2615 | (559,560 w20 c0.81 p0.03) | tracked/locked_admitted | lock | 21.5 | - | - | - |

### P6 serve f3038 (far team B), window f2998-f3078

| f | dets (x,y w conf persist flags) | tracker | replay | obs gap-1 speed | best pair speed | dist | fail |
|---|---|---|---|---|---|---|---|
| 2998 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 2999 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3000 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3001 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3002 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3003 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3004 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3005 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3006 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3007 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3008 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3009 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3010 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3011 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3012 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3013 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3014 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3015 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3016 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3017 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3018 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3019 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3020 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3021 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3022 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3023 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3024 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3025 | (1210,550 w35 c0.22 p0.00) | none/unlocked_no_motion | - | - | - | - | no_previous_sighting_in_window |
| 3026 | (1210,553 w37 c0.21 p0.03) | none/unlocked_no_motion | - | 3.6 | 3.6 | 4 | no_previous_sighting_in_window |
| 3027 | (864,456 w15 c0.18 p0.00) | none/unlocked_no_motion | - | 359.5 | - | - | no_previous_sighting_in_window |
| 3028 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3029 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3030 | (864,445 w14 c0.28 p0.03) | none/unlocked_no_motion | - | 10.5 | - | - | no_previous_sighting_in_window |
| 3031 | (864,444 w15 c0.48 p0.05) | none/unlocked_no_motion | - | 1.6 | - | - | no_previous_sighting_in_window |
| 3032 | (864,443 w15 c0.51 p0.07) | none/unlocked_no_motion | - | 0.5 | 0.5 | 0 | speed_below_lock_min_speed |
| 3033 | (864,443 w15 c0.50 p0.10) | none/unlocked_no_motion | - | 0.0 | 0.2 | 0 | speed_below_lock_min_speed |
| 3034 | (864,443 w14 c0.35 p0.12) | none/unlocked_no_motion | - | 0.5 | - | - | no_previous_sighting_in_window |
| 3035 | (864,444 w13 c0.31 p0.15) | none/unlocked_no_motion | - | 1.1 | 1.1 | 1 | no_previous_sighting_in_window |
| 3036 | (864,447 w13 c0.19 p0.17) | none/unlocked_no_motion | - | 3.0 | 3.0 | 3 | no_previous_sighting_in_window |
| 3037 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3038 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3039 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3040 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3041 | (836,410 w23 c0.42 p0.00) | none/unlocked_no_motion | - | 46.0 | - | - | no_previous_sighting_in_window |
| 3042 | (832,400 w23 c0.66 p0.03) | tracked/bootstrap_locked | lock | 10.4 | - | - | - |
| 3043 | - | none/coast_short_trajectory | lock | - | - | - | - |
| 3044 | - | none/coast_short_trajectory | lock | - | - | - | - |
| 3045 | (810,370 w18 c0.52 p0.00) | tracked/locked_admitted | lock | 37.9 | - | - | - |
| 3046 | (801,364 w18 c0.77 p0.03) | tracked/locked_admitted | lock | 11.1 | - | - | - |
| 3047 | (795,356 w20 c0.73 p0.05) | tracked/locked_admitted | lock | 10.0 | - | - | - |
| 3048 | (783,350 w18 c0.67 p0.05) | tracked/locked_admitted | lock | 13.0 | - | - | - |
| 3049 | (773,344 w20 c0.73 p0.03) | tracked/locked_admitted | lock | 12.2 | - | - | - |
| 3050 | (764,338 w21 c0.75 p0.05) | tracked/locked_admitted | lock | 10.7 | - | - | - |
| 3051 | (753,334 w20 c0.78 p0.05) | tracked/locked_admitted | lock | 11.4 | - | - | - |
| 3052 | (742,330 w21 c0.78 p0.05) | tracked/locked_admitted | lock | 11.2 | - | - | - |
| 3053 | (732,326 w24 c0.80 p0.05) | tracked/locked_admitted | lock | 11.4 | - | - | - |
| 3054 | (720,324 w23 c0.81 p0.05) | tracked/locked_admitted | lock | 12.7 | - | - | - |
| 3055 | (710,324 w25 c0.90 p0.05) | tracked/locked_admitted | lock | 10.0 | - | - | - |
| 3056 | (696,322 w25 c0.81 p0.05) | tracked/locked_admitted | lock | 13.0 | - | - | - |
| 3057 | (684,325 w27 c0.87 p0.03) | tracked/locked_admitted | lock | 13.2 | - | - | - |
| 3058 | (672,328 w26 c0.81 p0.03) | tracked/locked_admitted | lock | 11.9 | - | - | - |
| 3059 | (660,334 w26 c0.82 p0.03) | tracked/locked_admitted | lock | 13.4 | - | - | - |
| 3060 | (646,338 w25 c0.82 p0.03) | tracked/locked_admitted | lock | 15.2 | - | - | - |
| 3061 | (634,347 w25 c0.81 p0.03) | tracked/locked_admitted | lock | 14.7 | - | - | - |
| 3062 | (618,357 w26 c0.81 p0.03) | tracked/locked_admitted | lock | 18.4 | - | - | - |
| 3063 | (604,368 w28 c0.82 p0.03) | tracked/locked_admitted | lock | 17.5 | - | - | - |
| 3064 | (588,382 w29 c0.83 p0.03) | tracked/locked_admitted | lock | 22.0 | - | - | - |
| 3065 | (573,398 w30 c0.74 p0.03) | tracked/locked_admitted | lock | 21.2 | - | - | - |
| 3066 | (556,416 w29 c0.83 p0.00) | tracked/locked_admitted | lock | 25.1 | - | - | - |
| 3067 | (540,438 w32 c0.81 p0.00) | tracked/locked_admitted | lock | 27.3 | - | - | - |
| 3068 | (520,460 w33 c0.79 p0.00) | tracked/locked_admitted | lock | 29.8 | - | - | - |
| 3069 | (501,489 w32 c0.77 p0.00) | tracked/locked_admitted | lock | 34.5 | - | - | - |
| 3070 | (486,492 w27 c0.54 p0.03) | tracked/locked_admitted | lock | 15.9 | - | - | - |
| 3071 | (498,444 w33 c0.82 p0.00) | tracked/locked_admitted | lock | 49.5 | - | - | - |
| 3072 | (508,395 w35 c0.79 p0.00) | tracked/locked_admitted | lock | 50.5 | - | - | - |
| 3073 | (519,350 w34 c0.86 p0.00) (446,494 w37 c0.56 p0.00) | tracked/locked_admitted | lock | 46.4 | - | - | - |
| 3074 | (528,306 w34 c0.91 p0.00) | tracked/locked_admitted | lock | 44.9 | - | - | - |
| 3075 | (538,264 w33 c0.88 p0.00) | tracked/locked_admitted | lock | 42.6 | - | - | - |
| 3076 | (546,224 w34 c0.88 p0.00) | tracked/locked_admitted | lock | 41.4 | - | - | - |
| 3077 | (556,186 w34 c0.89 p0.00) | tracked/locked_admitted | lock | 38.8 | - | - | - |
| 3078 | (565,150 w34 c0.88 p0.00) | tracked/locked_admitted | lock | 37.6 | - | - | - |

### P7 serve f3747 (near team A), window f3707-f3787

| f | dets (x,y w conf persist flags) | tracker | replay | obs gap-1 speed | best pair speed | dist | fail |
|---|---|---|---|---|---|---|---|
| 3707 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3708 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3709 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3710 | (831,410 w18 c0.16 p0.07) | none/unlocked_no_motion | - | - | - | - | no_previous_sighting_in_window |
| 3711 | (832,409 w17 c0.21 p0.10) | none/unlocked_no_motion | - | 0.7 | 0.7 | 1 | no_previous_sighting_in_window |
| 3712 | (832,410 w17 c0.18 p0.12) | none/unlocked_no_motion | - | 0.5 | 0.5 | 0 | no_previous_sighting_in_window |
| 3713 | (832,410 w18 c0.17 p0.15) | none/unlocked_no_motion | - | 0.7 | 0.7 | 1 | no_previous_sighting_in_window |
| 3714 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3715 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3716 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3717 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3718 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3719 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3720 | (832,410 w19 c0.32 p0.17) | none/unlocked_no_motion | - | 0.7 | - | - | no_previous_sighting_in_window |
| 3721 | (832,410 w19 c0.33 p0.17) | none/unlocked_no_motion | - | 0.0 | 0.0 | 0 | no_previous_sighting_in_window |
| 3722 | (832,410 w19 c0.38 p0.17) | none/unlocked_no_motion | - | 0.0 | 0.0 | 0 | no_previous_sighting_in_window |
| 3723 | (832,410 w19 c0.37 p0.17) | none/unlocked_no_motion | - | 0.5 | 0.5 | 0 | no_previous_sighting_in_window |
| 3724 | (832,410 w19 c0.28 p0.20) | none/unlocked_no_motion | - | 0.0 | 0.2 | 0 | no_previous_sighting_in_window |
| 3725 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3726 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3727 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 3728 | (902,416 w50 c0.79 p0.00) | none/unlocked_no_motion | - | 70.8 | - | - | no_previous_sighting_in_window |
| 3729 | (900,392 w50 c0.83 p0.03) | tracked/bootstrap_locked | lock | 24.1 | - | - | - |
| 3730 | (899,367 w50 c0.84 p0.00) | tracked/locked_admitted | lock | 25.5 | - | - | - |
| 3731 | (898,342 w49 c0.85 p0.03) | tracked/locked_admitted | lock | 24.5 | - | - | - |
| 3732 | (897,321 w50 c0.87 p0.03) | tracked/locked_admitted | lock | 21.5 | - | - | - |
| 3733 | (896,304 w51 c0.87 p0.03) | tracked/locked_admitted | lock | 16.6 | - | - | - |
| 3734 | (894,290 w50 c0.86 p0.03) | tracked/locked_admitted | lock | 14.6 | - | - | - |
| 3735 | (894,278 w51 c0.84 p0.03) | tracked/locked_admitted | lock | 12.5 | - | - | - |
| 3736 | (892,268 w51 c0.86 p0.05) | tracked/locked_admitted | lock | 10.0 | - | - | - |
| 3737 | (890,260 w53 c0.86 p0.05) | tracked/locked_admitted | lock | 7.3 | - | - | - |
| 3738 | (890,256 w51 c0.88 p0.07) | tracked/locked_admitted | lock | 5.1 | - | - | - |
| 3739 | (888,254 w51 c0.88 p0.10) | tracked/locked_admitted | lock | 1.8 | - | - | - |
| 3740 | (888,254 w52 c0.88 p0.12) | tracked/locked_admitted | lock | 0.5 | - | - | - |
| 3741 | (886,258 w51 c0.85 p0.15) | tracked/locked_admitted | lock | 3.8 | - | - | - |
| 3742 | (885,264 w50 c0.85 p0.17) | tracked/locked_admitted | lock | 6.2 | - | - | - |
| 3743 | (883,272 w50 c0.85 p0.23) (832,414 w26 c0.61 p0.23) | tracked/locked_admitted | lock | 8.7 | - | - | - |
| 3744 | (882,283 w50 c0.84 p0.15) | tracked/locked_admitted | lock | 11.0 | - | - | - |
| 3745 | (880,296 w51 c0.85 p0.12) | tracked/locked_admitted | lock | 13.1 | - | - | - |
| 3746 | (880,312 w51 c0.83 p0.07) | tracked/locked_admitted | lock | 16.0 | - | - | - |
| 3747 | (880,325 w49 c0.78 p0.05) | tracked/locked_admitted | lock | 13.0 | - | - | - |
| 3748 | (888,295 w48 c0.86 p0.17) | tracked/locked_admitted | lock | 31.2 | - | - | - |
| 3749 | (896,272 w46 c0.90 p0.30S) | tracked/locked_admitted | lock | - | - | - | - |
| 3750 | (902,249 w43 c0.87 p0.20) | tracked/locked_admitted | lock | 48.2 | - | - | - |
| 3751 | (908,232 w43 c0.89 p0.03) | tracked/locked_admitted | lock | 17.6 | - | - | - |
| 3752 | (916,218 w39 c0.87 p0.03) | tracked/locked_admitted | lock | 16.1 | - | - | - |
| 3753 | (922,208 w38 c0.88 p0.03) (931,573 w24 c0.24 p0.00) | tracked/locked_admitted | lock | 12.3 | - | - | - |
| 3754 | (928,200 w37 c0.92 p0.05) | tracked/locked_admitted | lock | 9.3 | - | - | - |
| 3755 | (933,195 w36 c0.86 p0.05) (832,410 w21 c0.17 p0.15) | tracked/locked_admitted | lock | 7.4 | - | - | - |
| 3756 | (938,194 w35 c0.85 p0.07) (832,410 w21 c0.26 p0.17) | tracked/locked_admitted | lock | 5.7 | - | - | - |
| 3757 | (942,193 w33 c0.85 p0.07) | tracked/locked_admitted | lock | 4.0 | - | - | - |
| 3758 | (946,194 w32 c0.86 p0.10) | tracked/locked_admitted | lock | 3.6 | - | - | - |
| 3759 | (950,197 w31 c0.89 p0.12) | tracked/locked_admitted | lock | 4.6 | - | - | - |
| 3760 | (951,202 w30 c0.84 p0.15) | tracked/locked_admitted | lock | 4.7 | - | - | - |
| 3761 | (952,207 w30 c0.86 p0.15) | tracked/locked_admitted | lock | 5.6 | - | - | - |
| 3762 | (954,213 w29 c0.84 p0.15) | tracked/locked_admitted | lock | 6.2 | - | - | - |
| 3763 | (955,220 w28 c0.85 p0.10) | tracked/locked_admitted | lock | 7.6 | - | - | - |
| 3764 | (956,228 w27 c0.85 p0.07) | tracked/locked_admitted | lock | 8.0 | - | - | - |
| 3765 | (956,238 w26 c0.85 p0.05) | tracked/locked_admitted | lock | 9.5 | - | - | - |
| 3766 | (956,248 w25 c0.84 p0.05) | tracked/locked_admitted | lock | 9.5 | - | - | - |
| 3767 | (956,258 w25 c0.84 p0.05) | tracked/locked_admitted | lock | 10.5 | - | - | - |
| 3768 | (956,270 w25 c0.84 p0.05) | tracked/locked_admitted | lock | 11.5 | - | - | - |
| 3769 | (956,282 w24 c0.84 p0.05) | tracked/locked_admitted | lock | 12.0 | - | - | - |
| 3770 | (956,294 w24 c0.85 p0.05) | tracked/locked_admitted | lock | 12.5 | - | - | - |
| 3771 | (955,306 w22 c0.83 p0.03) | tracked/locked_admitted | lock | 12.5 | - | - | - |
| 3772 | (954,320 w23 c0.80 p0.03) | tracked/locked_admitted | lock | 13.0 | - | - | - |
| 3773 | (954,334 w23 c0.81 p0.03) | tracked/locked_admitted | lock | 14.5 | - | - | - |
| 3774 | (956,348 w21 c0.75 p0.03) | tracked/locked_admitted | lock | 13.6 | - | - | - |
| 3775 | (953,362 w22 c0.76 p0.03) | tracked/locked_admitted | lock | 14.2 | - | - | - |
| 3776 | (952,374 w16 c0.26 p0.03) | tracked/low_floor_admitted | lock | 12.0 | - | - | - |
| 3777 | (946,394 w25 c0.68 p0.03) | tracked/locked_admitted | lock | 21.2 | - | - | - |
| 3778 | (952,411 w15 c0.21 p0.03) | tracked/low_floor_admitted | lock | 17.7 | - | - | - |
| 3779 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 3780 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 3781 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 3782 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 3783 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 3784 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 3785 | - | none/out_of_view_reentry_wait | lock | - | - | - | - |
| 3786 | (948,395 w22 c0.70 p0.07) | tracked/locked_admitted | lock | 16.4 | - | - | - |
| 3787 | (952,370 w17 c0.74 p0.07) | tracked/locked_admitted | lock | 25.9 | - | - | - |

### P8 serve f4770 (far team A), window f4730-f4810

| f | dets (x,y w conf persist flags) | tracker | replay | obs gap-1 speed | best pair speed | dist | fail |
|---|---|---|---|---|---|---|---|
| 4730 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4731 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4732 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4733 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4734 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4735 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4736 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4737 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4738 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4739 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4740 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4741 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4742 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4743 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4744 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4745 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4746 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4747 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4748 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4749 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4750 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4751 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4752 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4753 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4754 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4755 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4756 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4757 | (998,444 w14 c0.44 p0.00) | none/unlocked_no_motion | - | - | - | - | no_previous_sighting_in_window |
| 4758 | (998,439 w14 c0.37 p0.03) | none/unlocked_no_motion | - | 5.5 | - | - | no_previous_sighting_in_window |
| 4759 | (997,434 w14 c0.31 p0.05) | none/unlocked_no_motion | - | 5.6 | 5.6 | 6 | no_previous_sighting_in_window |
| 4760 | (998,430 w15 c0.45 p0.07) | none/unlocked_no_motion | - | 3.5 | - | - | no_pair_within_lock_max_pair_gap |
| 4761 | (996,428 w16 c0.62 p0.10) | none/unlocked_no_motion | - | 2.9 | 2.9 | 3 | speed_below_lock_min_speed |
| 4762 | (996,426 w16 c0.50 p0.12) | none/unlocked_no_motion | - | 2.0 | 2.4 | 5 | speed_below_lock_min_speed |
| 4763 | (996,426 w16 c0.36 p0.15) | none/unlocked_no_motion | - | 0.0 | - | - | no_previous_sighting_in_window |
| 4764 | (996,426 w15 c0.34 p0.17) | none/unlocked_no_motion | - | 0.7 | 0.7 | 1 | no_previous_sighting_in_window |
| 4765 | (997,430 w16 c0.41 p0.20) | none/unlocked_no_motion | - | 3.5 | - | - | no_pair_within_lock_max_pair_gap |
| 4766 | (997,430 w14 c0.21 p0.23) | none/unlocked_no_motion | - | 1.0 | 2.3 | 5 | no_previous_sighting_in_window |
| 4767 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4768 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4769 | (996,446 w14 c0.24 p0.25) | none/unlocked_no_motion | - | 15.0 | - | - | no_previous_sighting_in_window |
| 4770 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4771 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4772 | (993,406 w18 c0.52 p0.17) | none/unlocked_no_motion | - | 39.1 | - | - | no_previous_sighting_in_window |
| 4773 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4774 | - | none/unlocked_no_motion | - | - | - | - | no_detections |
| 4775 | (988,369 w18 c0.68 p0.00) | none/unlocked_no_motion | - | 37.8 | - | - | no_pair_within_lock_max_pair_gap |
| 4776 | (987,355 w16 c0.68 p0.03) | tracked/bootstrap_locked | lock | 14.0 | - | - | - |
| 4777 | (984,346 w19 c0.71 p0.05) | tracked/locked_admitted | lock | 9.3 | - | - | - |
| 4778 | (982,334 w21 c0.78 p0.05) | tracked/locked_admitted | lock | 11.9 | - | - | - |
| 4779 | (979,326 w20 c0.81 p0.05) | tracked/locked_admitted | lock | 9.3 | - | - | - |
| 4780 | (978,318 w20 c0.82 p0.05) | tracked/locked_admitted | lock | 7.6 | - | - | - |
| 4781 | (976,312 w21 c0.84 p0.07) | tracked/locked_admitted | lock | 6.7 | - | - | - |
| 4782 | (975,306 w22 c0.81 p0.07) | tracked/locked_admitted | lock | 5.2 | - | - | - |
| 4783 | (972,302 w22 c0.87 p0.10) | tracked/locked_admitted | lock | 5.4 | - | - | - |
| 4784 | (970,298 w22 c0.86 p0.10) | tracked/locked_admitted | lock | 4.5 | - | - | - |
| 4785 | (967,296 w24 c0.81 p0.12) | tracked/locked_admitted | lock | 3.4 | - | - | - |
| 4786 | (964,296 w25 c0.86 p0.12) | tracked/locked_admitted | lock | 2.5 | - | - | - |
| 4787 | (960,298 w25 c0.87 p0.15) | tracked/locked_admitted | lock | 4.5 | - | - | - |
| 4788 | (956,302 w25 c0.88 p0.17) | tracked/locked_admitted | lock | 5.0 | - | - | - |
| 4789 | (952,306 w25 c0.83 p0.20) | tracked/locked_admitted | lock | 6.4 | - | - | - |
| 4790 | (947,315 w26 c0.90 p0.07) | tracked/locked_admitted | lock | 10.1 | - | - | - |
| 4791 | (942,326 w28 c0.88 p0.05) | tracked/locked_admitted | lock | 12.5 | - | - | - |
| 4792 | (936,339 w29 c0.78 p0.03) | tracked/locked_admitted | lock | 13.7 | - | - | - |
| 4793 | (932,356 w27 c0.78 p0.03) | tracked/locked_admitted | lock | 17.5 | - | - | - |
| 4794 | (926,376 w29 c0.79 p0.03) | tracked/locked_admitted | lock | 20.4 | - | - | - |
| 4795 | (923,398 w26 c0.72 p0.03) | tracked/locked_admitted | lock | 22.8 | - | - | - |
| 4796 | (914,424 w30 c0.79 p0.00) | tracked/locked_admitted | lock | 28.0 | - | - | - |
| 4797 | (910,454 w30 c0.80 p0.00) | tracked/locked_admitted | lock | 30.3 | - | - | - |
| 4798 | (901,490 w32 c0.86 p0.00) | tracked/locked_admitted | lock | 37.1 | - | - | - |
| 4799 | (894,528 w35 c0.85 p0.00) | tracked/locked_admitted | lock | 38.7 | - | - | - |
| 4800 | - | predicted/coast_predicted | lock | - | - | - | - |
| 4801 | (880,540 w30 c0.78 p0.03) | tracked/locked_admitted | lock | 17.4 | - | - | - |
| 4802 | (884,486 w37 c0.83 p0.03) | tracked/locked_admitted | lock | 53.6 | - | - | - |
| 4803 | (884,433 w35 c0.79 p0.00) | tracked/locked_admitted | lock | 53.0 | - | - | - |
| 4804 | (882,384 w36 c0.83 p0.00) (848,530 w30 c0.22 p0.00) | tracked/locked_admitted | lock | 49.6 | - | - | - |
| 4805 | (882,336 w37 c0.80 p0.00) | tracked/locked_admitted | lock | 47.0 | - | - | - |
| 4806 | (880,292 w37 c0.90 p0.00) | tracked/locked_admitted | lock | 44.0 | - | - | - |
| 4807 | (878,250 w37 c0.88 p0.00) (856,500 w28 c0.47 p0.00) | tracked/locked_admitted | lock | 42.0 | - | - | - |
| 4808 | (878,212 w38 c0.89 p0.00) (870,499 w21 c0.19 p0.05) | tracked/locked_admitted | lock | 38.5 | - | - | - |
| 4809 | (877,176 w38 c0.88 p0.00) (871,492 w26 c0.42 p0.07) (868,492 w25 c0.21 p0.07) | tracked/locked_admitted | lock | 36.0 | - | - | - |
| 4810 | (876,141 w36 c0.86 p0.00) | tracked/locked_admitted | lock | 35.0 | - | - | - |

## Counterfactual sweep (offline replay of the bootstrap)

| rule | serves recovered (P# f) | new locks elsewhere | new-lock frames |
|---|---|---|---|
| baseline | - | 0 | - |
| min_speed=6 | - | 8 | 376, 481, 879, 2304, 2373, 3362, 3461, 4101 |
| min_speed=5 | P8 f4770 | 12 | 215, 376, 481, 879, 1173, 2304, 2365, 3360, 3458, 4101, 4571, 4608 |
| min_speed=4 | P1 f210, P2 f880, P4 f2154, P8 f4770 | 14 | 203, 376, 481, 609, 1173, 1240, 2150, 2304, 2365, 3360, 3458, 4101, 4571, 4608 |
| min_speed=3 | P1 f210, P2 f880, P4 f2154, P6 f3038, P8 f4770 | 15 | 203, 376, 481, 609, 1173, 1213, 2150, 2277, 2365, 3026, 3360, 3444, 4095, 4551, 4608 |
| min_speed=2 | P1 f210, P2 f880, P4 f2154, P6 f3038, P8 f4770 | 16 | 92, 376, 481, 609, 1173, 1210, 2150, 2275, 2365, 2732, 3113, 3360, 3443, 4095, 4551, 4608 |
| min_speed=1 | P1 f210, P2 f880, P4 f2154, P6 f3038, P8 f4770 | 18 | 31, 376, 472, 609, 1173, 1210, 1655, 1797, 2274, 2360, 2732, 3113, 3360, 3443, 3682, 4095, 4551, 4608 |
| pair_gap=3 | - | 3 | 1018, 3373, 4775 |
| pair_gap=4 | - | 3 | 1001, 3373, 4775 |
| min_speed=4 + pair_gap=3 | P1 f210, P2 f880, P4 f2154, P8 f4770 | 15 | 203, 376, 481, 609, 1018, 1173, 1240, 2150, 2304, 2365, 3314, 3458, 4101, 4571, 4608 |
| min_speed=4 + pair_gap=4 | P1 f210, P2 f880, P4 f2154, P8 f4770 | 16 | 203, 376, 481, 608, 997, 1173, 1240, 2150, 2243, 2304, 2365, 3314, 3458, 4101, 4571, 4608 |
| min3 + ascending | P1 f210, P2 f880, P4 f2154, P6 f3038, P8 f4770 | 15 | 203, 376, 481, 609, 1173, 1213, 2150, 2277, 2365, 3026, 3360, 3444, 4095, 4551, 4608 |
| min4 + ascending | P1 f210, P2 f880, P4 f2154, P8 f4770 | 14 | 203, 376, 481, 609, 1173, 1240, 2150, 2304, 2365, 3360, 3458, 4101, 4571, 4608 |
| min3 + ascending + near player 200px | P1 f210, P2 f880, P4 f2154, P6 f3038, P8 f4770 | 15 | 203, 376, 481, 609, 1173, 1213, 2150, 2277, 2365, 3026, 3360, 3444, 4095, 4551, 4608 |
| min3 + ascending + near player 120px | P1 f210, P2 f880, P4 f2154, P6 f3038, P8 f4770 | 15 | 203, 376, 481, 609, 1173, 1213, 2150, 2277, 2365, 3026, 3360, 3444, 4095, 4551, 4608 |
| WEAK lock >=3px/f (plain) | P1 f210, P2 f880, P4 f2154, P6 f3038, P8 f4770 | 15 | 203, 376, 481, 609, 1173, 1213, 2150, 2277, 2365, 3026, 3360, 3444, 4095, 4551, 4608 |
| WEAK lock >=3px/f + 3-of-3 sightings @20px | P1 f210, P2 f880, P4 f2154, P6 f3038, P8 f4770 | 15 | 203, 376, 481, 609, 1173, 1213, 2150, 2277, 2365, 3026, 3360, 3444, 4095, 4551, 4608 |
| WEAK lock >=3px/f + 3-of-3 + persist<0.25 | P1 f210, P2 f880, P4 f2154, P6 f3038, P8 f4770 | 15 | 203, 376, 481, 609, 1173, 1213, 2150, 2277, 2365, 3026, 3360, 3444, 4095, 4551, 4608 |
| WEAK lock >=3px/f + 3-of-3 + persist<0.25 + player<250px | P1 f210, P2 f880, P4 f2154, P6 f3038, P8 f4770 | 15 | 203, 376, 481, 609, 1173, 1213, 2150, 2277, 2365, 3026, 3360, 3444, 4095, 4551, 4608 |
| WEAK lock >=4px/f + 3-of-3 + persist<0.25 | P1 f210, P2 f880, P4 f2154, P8 f4770 | 14 | 203, 376, 481, 609, 1173, 1240, 2150, 2304, 2365, 3360, 3458, 4101, 4571, 4608 |
| size-normalised gate ref=60 | P1 f210, P4 f2154, P8 f4770 | 15 | 203, 376, 481, 879, 1173, 1213, 2150, 2277, 2365, 3036, 3360, 3444, 4095, 4551, 4759 |
| size-normalised gate ref=50 | P1 f210, P4 f2154, P8 f4770 | 14 | 203, 376, 481, 879, 1222, 2150, 2304, 2365, 3036, 3360, 3444, 4095, 4571, 4759 |
| size-normalised gate ref=40 | P1 f210, P4 f2154, P8 f4770 | 12 | 203, 376, 481, 879, 2150, 2304, 3036, 3360, 3461, 4095, 4571, 4759 |
| size-normalised ref=50 + 3-of-3 + persist<0.25 | P1 f210, P4 f2154, P8 f4770 | 14 | 203, 376, 481, 879, 1222, 2150, 2304, 2365, 3036, 3360, 3444, 4095, 4571, 4759 |

| rule | P1 f210 lock/latency, locked frames in +-15f | P2 f880 lock/latency, locked frames in +-15f | P3 f1395 lock/latency, locked frames in +-15f | P4 f2154 lock/latency, locked frames in +-15f | P5 f2575 lock/latency, locked frames in +-15f | P6 f3038 lock/latency, locked frames in +-15f | P7 f3747 lock/latency, locked frames in +-15f | P8 f4770 lock/latency, locked frames in +-15f |
|---|---|---|---|---|---|---|---|---|
| baseline | 216/+6f · 10/31 | 890/+10f · 6/31 | 1395/+0f · 31/31 | 2159/+5f · 11/31 | 2575/+0f · 31/31 | 3042/+4f · 12/31 | 3747/+0f · 31/31 | 4776/+6f · 10/31 |
| min_speed=6 | 216/+6f · 10/31 | 880/+0f · 17/31 | 1395/+0f · 31/31 | 2159/+5f · 11/31 | 2575/+0f · 31/31 | 3042/+4f · 12/31 | 3747/+0f · 31/31 | 4776/+6f · 10/31 |
| min_speed=5 | 215/+5f · 11/31 | 880/+0f · 17/31 | 1395/+0f · 31/31 | 2159/+5f · 11/31 | 2575/+0f · 31/31 | 3042/+4f · 12/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| min_speed=4 | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3042/+4f · 12/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| min_speed=3 | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 28/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| min_speed=2 | 210/+0f · 31/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 31/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| min_speed=1 | 210/+0f · 31/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 31/31 | 2575/+0f · 31/31 | 3038/+0f · 31/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| pair_gap=3 | 216/+6f · 10/31 | 890/+10f · 6/31 | 1395/+0f · 31/31 | 2159/+5f · 11/31 | 2575/+0f · 31/31 | 3042/+4f · 12/31 | 3747/+0f · 31/31 | 4775/+5f · 11/31 |
| pair_gap=4 | 216/+6f · 10/31 | 890/+10f · 6/31 | 1395/+0f · 31/31 | 2159/+5f · 11/31 | 2575/+0f · 31/31 | 3042/+4f · 12/31 | 3747/+0f · 31/31 | 4775/+5f · 11/31 |
| min_speed=4 + pair_gap=3 | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3042/+4f · 12/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| min_speed=4 + pair_gap=4 | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3042/+4f · 12/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| min3 + ascending | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 28/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| min4 + ascending | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3042/+4f · 12/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| min3 + ascending + near player 200px | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 28/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| min3 + ascending + near player 120px | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 28/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| WEAK lock >=3px/f (plain) | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 28/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| WEAK lock >=3px/f + 3-of-3 sightings @20px | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 28/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| WEAK lock >=3px/f + 3-of-3 + persist<0.25 | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 28/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| WEAK lock >=3px/f + 3-of-3 + persist<0.25 + player<250px | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 28/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| WEAK lock >=4px/f + 3-of-3 + persist<0.25 | 210/+0f · 23/31 | 880/+0f · 31/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3042/+4f · 12/31 | 3747/+0f · 31/31 | 4770/+0f · 31/31 |
| size-normalised gate ref=60 | 210/+0f · 23/31 | 880/+0f · 17/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 18/31 | 3747/+0f · 31/31 | 4770/+0f · 27/31 |
| size-normalised gate ref=50 | 210/+0f · 23/31 | 880/+0f · 17/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 18/31 | 3747/+0f · 31/31 | 4770/+0f · 27/31 |
| size-normalised gate ref=40 | 210/+0f · 23/31 | 880/+0f · 17/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 18/31 | 3747/+0f · 31/31 | 4770/+0f · 27/31 |
| size-normalised ref=50 + 3-of-3 + persist<0.25 | 210/+0f · 23/31 | 880/+0f · 17/31 | 1395/+0f · 31/31 | 2154/+0f · 20/31 | 2575/+0f · 31/31 | 3038/+0f · 18/31 | 3747/+0f · 31/31 | 4770/+0f · 27/31 |
## Hand analysis (authored, kept on regeneration)

**Replay fidelity gate.** Replaying the bootstrap offline at the production
thresholds reproduces the dumped `ball_track.locked` flag on **4966 / 4968
frames** (2 disagreements, f288 and f1698, where the real tracker locked and
lost the ball inside the same frame). Every counterfactual below is measured
on that replay; nothing in `src/` was touched.

### 1. The headline: the failure is a SIDE effect, not a serve effect

**5 of the 8 GT serves are unlocked at their own contact frame, and all 5 are
far-side serves** (P1/P2/P4/P6/P8). All 3 near-side serves (P3 f1395, P5 f2575,
P7 f3747) are locked at contact and already produce their action. The
pre-contact toss tells the whole story:

| | near-side serves (P3, P5, P7) | far-side serves (P1, P2, P4, P6, P8) |
|---|---|---|
| tossed-ball detection width | 46-53 px | 13-17 px |
| median pre-contact rise | 7.3-16.8 px/f | **1.6-6.7 px/f** |
| lock latency vs the owner frame | 0f (P3, P5), -18f (P7) | +4f .. +10f |
| detections AT the contact frame | 1-2 | **0** (P4, P6, P8) |

The same physical toss is ~3-4x slower in pixels on the far half (and reads
conf 0.18-0.6 instead of 0.85-0.9), so `lock_min_speed = 8 px/f` - a
constant measured on near-side balls - is above what a far-side toss can ever
produce. P7 survives only because its toss was caught at 25-70 px/f from f3728,
18 frames before contact.

### 2. Ranked failing bootstrap conditions (frames inside the +-15f window where the tracker is UNLOCKED)

| rank | condition | evidence | verdict |
|---|---|---|---|
| 1 | **`speed_below_lock_min_speed`** (pair exists, `dist <= 90`, `age <= 2`, but `dist/age` in 0.2-6.7 px/f) | 11 / 10 / 1 / 2 / 2 frames in P1 / P2 / P4 / P6 / P8 | THE cause. Removing it is necessary and (at >= 3 px/f) sufficient for all 5. |
| 2 | **`no_previous_sighting_in_window` / `no_detections`** (no pair at all) | 5-11 and 32-39 frames per failing window; the far ball is seen only every 2-4 frames and is invisible AT the contact frame (0 dets in P4/P6/P8) | caps any rule: no threshold can lock at a frame with no evidence. The earliest possible lock is the first post-contact sighting (latency +2..+4f, obs 23-46 px/f). |
| 3 | `no_plausible_survivor` (every candidate `stationary_suspect`/static-removed) | 1 frame in P1 (f214, persist 0.30) and P2; 14 in the healthy P3 (a parked spare) | incidental; costs one toss sighting each. |
| - | `lock_max_jump` (pair farther than 90 px) | never fires in the 5 failing windows (nearest previous sighting stays < 30 px) | NOT a cause. |
| - | `lock_max_pair_gap` (age > 2) | only P8's post-contact pair (f4772 vs f4769, age 3, 39 px, 13 px/f) | minor: `pair_gap=3..4` alone recovers nothing (`new locks` 3, no serve). |
| - | multiple candidates / rack-ball interference | one plausible candidate in 4/5 windows; P6 f3025-3026 has a second candidate at (1210,553) conf 0.21 - a bystander ball, and precisely what a plain 3 px/f rule locks on first | risk, not cause. |
| - | `stationary_suspect` on the real ball | 1 frame (P1 f214) | minor. |

### 3. Contrast with the serves that survive

| clip / serve | side | ball width | pre-contact rise | first lock |
|---|---|---|---|---|
| dev P3 f1395 | near | w50 | 11.5 px/f | f1376 (-19f) |
| dev P5 f2575 | near | w51 | 16.8 px/f | f2541 (-34f) |
| dev P7 f3747 | near | w50 | 7.3 px/f (toss caught at 25-70 px/f) | f3729 (-18f) |
| entreno 3 f29 | near | w51-55 | 32 px/f | f14 (-15f) |
| entreno 7 f22 | near | w51-57 | 17 px/f | f21 (-1f) |
| entreno 6 f73 | far | - | - | not an admission failure: the tracker is locked from f1, its serve loss is the rack-ball class |

Every surviving serve in the corpus is near-side with a 40-57 px ball. The
entreno suite therefore has almost no power to validate this mechanism - the
gate has to be the dev clip plus a re-check that the entreno logs do not move.

### 4. Proposed mechanism (NOT implemented - step 2)

Add a **second, weaker motion tier used only while UNLOCKED**, in
`BallTracker._try_lock` / `_scan_motion_pair`: accept a pair whose
`dist/age >= ball_lock_weak_min_speed` (default **3.0 px/f**) when the current
detection is a survivor, is not `stationary_suspect`, and its apparent width is
in the far band (`< 30 px`), so near-side behaviour is byte-identical. The
`lock_min_speed = 8 px/f` fast path is untouched.

Numbers it would need (all measured):

* `weak_min_speed = 3.0` px/f recovers **5/5** failing serves at lock latency
  **0f**, with 20-31 of the 31 window frames owned (2.0-2.3 px/f recovers 5/5
  too, 4.0 only 4/5, 5.0 only 1/5, 6.0 none).
* Gating the weak tier on apparent width (a far-band `w < 30 px`) is required
  for byte-identity on the near-side entreno gate; the size-normalised variant
  (`8 px/f * w/ref`, ref 40-60) recovers only 3/5 - it misses P2 and P6 because
  their toss detections are also low-confidence/low-tier, not just small.
* Extra discriminators I measured and that DO NOT pay off: 3-of-3 sustained
  sightings within 20 px, `persist < 0.25`, proximity to a player (< 120 /
  250 px), all remove **zero** spurious locks. **Ascending-only LOSES serves**
  (P4, P6): the far toss is frequently detected on its way down
  (f2148-2151, f3030-3036). So the candidate geometry alone cannot separate
  the toss from a spare - a real discriminator has to be serve CONTEXT
  (dead-ball gap + far service zone), which is a larger mechanism than the
  approved one.

### 5. What it could break (risk list, with the measured instances)

1. **Rack / parked balls** - the reason `lock_min_speed` exists (entreno_6 lost
   a whole serve to a bottom-right spare, entreno_7 f244 to a static rack ball).
   Static suppression still removes a ball that never moves (persist >= 0.55)
   or flags it suspect (>= 0.30), but a spare the detector jitters by 3-5 px
   frame-to-frame would now be admitted. **f3360 is exactly this case**: the
   weak lock fires on (1105,593) 17 px from a parked ball already at
   `persist 0.75`.
2. **Held balls** - a ball in a server's hand between rallies reads as
   sustained ~0-3 px/f sightings (f4095: w16 conf 0.71, 34 px from a player;
   f2365: w34 conf 0.43, 45 px). Each admitted hold can emit a contact
   candidate in dead time, feeding the false-positive `serve` class T4 already counted on
   the dev clip (f1039, f2414, f3595).
3. **Bystander / other-court balls** - f1173 (conf 0.24, 377 px from any
   player) and f4551 (conf 0.19, 583 px) are almost certainly not game balls;
   a lock on one holds the tracker until the next reset (max_missing 10f).
4. **Cost on the dev clip**: the 3 px/f tier adds **15 bootstrap locks over
   4968 frames**, of which 3 are the intended serve tosses (f203, f2150,
   f3026/f3030) - i.e. **~12 new lock opportunities**, some of which may be
   real balls the current track also loses (f2365, f4095). Only a real run can
   tell; offline the replay cannot see past the lock.
5. **Evidence asymmetry**: this is 1080p far-side evidence from ONE clip.

### 6. Expected dev-clip recovery

**5 of the 5** stage-3 (`candidate`) serve deaths in
`docs/t4_loss_waterfall_dev_clip.md` - P1 f210, P2 f880, P4 f2154, P6 f3038,
P8 f4770 - each at lock latency 0 with >= 20/31 window frames owned. Serve
contact recovery would go from 3/8 (P3, P5, P7) to a projected 8/8 tracked;
P5 and P7 still die later at the stage-4 reach gate, so the *action* count
only moves if the classifier then emits them (needs the A/B run). The overall
contact F1 (0.597) cannot be projected from this offline replay - it must be
re-measured with `scripts/evaluate_timed.py --ignore-player`.

### 7. Gates for the implementation step

* byte-identical (or strictly better) action logs on `video_entreno_1..7`,
  `--device cpu`, including the serve count;
* dev clip: 5 fewer stage-3 deaths in `scripts/waterfall.py` AND no growth in
  false-positive `serve` actions (today 3: f1039, f2414, f3595);
* unit tests for the new tier (weak pair admitted, static spare still not,
  near-side path unchanged) + the existing config-drift guard extended with
  the new key.

### Reproduce

```bash
venv/bin/python scripts/probe_serve_admission.py \
    --diag output/t4/dev_diag.jsonl \
    --ground-truth ground_truth/video_ari_joan_8_first_points_annotations.json \
    --json output/t5/dev_serve_admission.json \
    --markdown docs/t5_serve_admission_diagnosis.md
# contrast (entreno GT carries no action labels -> explicit serve frames)
venv/bin/python -m src.main resources/video_entreno_3.mp4 --output-dir output/t5/e3 \
    --skip-visualization --device cpu --diag-dump output/t5/e3_diag.jsonl
venv/bin/python -m src.main resources/video_entreno_7.mp4 --output-dir output/t5/e7 \
    --skip-visualization --device cpu --diag-dump output/t5/e7_diag.jsonl
venv/bin/python -m src.main resources/video_entreno_6.mp4 --output-dir output/t5/e6 \
    --skip-visualization --device cpu --diag-dump output/t5/e6_diag.jsonl
venv/bin/python scripts/probe_serve_admission.py --diag output/t5/e3_diag.jsonl \
    --ground-truth - --serve-frames 29 --serve-labels e3-near \
    --json output/t5/e3_serve_admission.json --no-sweep
venv/bin/python scripts/probe_serve_admission.py --diag output/t5/e7_diag.jsonl \
    --ground-truth - --serve-frames 22 --serve-labels e7-near \
    --json output/t5/e7_serve_admission.json --no-sweep
```

---

# T5 step 2 — A vs B replayed against the PRODUCTION classes, and the decision

Both candidate mechanisms were implemented in `src/tracking/ball_tracker.py`
behind config keys that default OFF, so the comparison runs the real code, not
a re-implementation: `scripts/probe_serve_mechanisms.py` feeds the T4
`--diag-dump` raw detections back into a real `BallTracker` and then drives the
real `ActionClassifier` contact probe over the ball history the pipeline would
have received (`FrameProcessor` semantics: append the real sighting, then test
`c = frame - CONTACT_DELAY`).

**Fidelity gate:** the `base` arm reproduces the dumped production
`ball_track` state on **4968/4968 frames** and every emitted centre to 1e-6 —
the replayed arms are the pipeline's own decisions.

## A vs B (dev clip, 4968 frames, GT = the 28 owner contacts)

| arm | far serves with a contact candidate | contact candidates | candidates outside every GT window | new bootstrap locks | probe fidelity |
|---|---|---|---|---|---|
| base (production) | 0/5 | 36 | 13 | 0 | 0 / 0 |
| **A** weak tier (3 px/f, w<30) | **0/5** | 37 (+1) | 14 (+1: f488) | **19** | — (arm diverges by design) |
| **B** backfill (lookback 20, w<30) | **0/5** | 37 (+1) | 14 (+1: f1019) | **0** | — (identical tracking) |

Per-serve candidates: unchanged in every arm — the 3 near-side serves keep
their candidates (P3 f1395 @+1, P5 f2575 @−3, P7 f3747 @0), the 5 far-side
serves stay empty. A's 19 new locks (f202, 376, 481, 615, 786, 878, 1213, 1672,
2150, 2277, 2731, 3036, 3357, 3444, 4094, 4551, 4571, 4638, 4758) confirm the
step-1 estimate (~12–15 spurious) and buy **zero** candidates; B creates no
lock opportunity at all and adds exactly one dead-time candidate (f1019, a
2-point chain on a re-lock). B is insensitive to its parameters: dropping the
width gate, tightening the radius (20 px + 6 px/frame), skipping
`stationary_suspect` points, or shortening the look-back to 12 all give the
identical 0/5 · 37 · 14.

## B does exactly what it was built to do — and the loss moves one gate along

Probe outcome inside each far-serve window (±15 f), base → B:

| serve | base | B |
|---|---|---|
| P1 f210 | `no_ball_sighting` ×23, `no_contact_geometry` ×8 | `no_ball_sighting` ×16, `no_contact_geometry` ×15 |
| P2 f880 | ×27 / ×4 | ×20 / ×11 |
| P4 f2154 | ×20 / ×11 | ×19 / ×12 |
| P6 f3038 | ×21 / ×10 | ×20 / ×11 |
| P8 f4770 | ×21 / ×10 | ×18 / ×13 |

B restores the pre-contact evidence the step-1 diagnosis identified: the
`no_ball_sighting` rejections at the contact frame fall everywhere, and the
18 backfill events (P1 f216 → 14 points f201–f215, P2 f890 → 13 points,
P8 f4776 → 13 points f4757–f4775) put the contact frame itself into the probe's
history. The contact then dies on the NEXT gate instead, and never for P4/P6/P8
where the chain has 1 point: the detector produced **no toss sighting at all**
for 10–15 frames before those contacts, so there is nothing to retro-extend.

## Why the restored history still cannot host the contact (the second defect)

With the full toss in the history, the far serve's contact (P1) measures, at
the best candidate frame c=214: `vin = (0.8, 0.7)`, `vout = (6.5, −11.3)`,
speed 13.1 px/f, `vin6 = (0.2, 0.3)`, `stays_down = False`, `pops_up = True`.
Against the four branches of `_normal_contact_at`:

* **bounce** — the toss apex is *before* the contact, so the ball never falls
  into it; no 26 px prominence.
* **redirect** — the far toss is vertical (`vin.x ≈ 0`); there is no sign flip.
* **drive** — needs `stays_down` (a spike keeps the ball down/flat); a serve
  keeps rising, so it refuses by construction.
* **serve branch** — needs the ascent to be FED, `|vin3| ≥ |vin6| + 10`
  (the e7 f25 signature: −42 vs −13). The far toss is a *decelerating float*
  (2 → 0 px/f into the contact), so the margin is ≈ −9.6.

A hypothetical "float toss → fast rise" signature (incoming ≤ 4 px/f, outgoing
≥ 10 px/f rising) fires on **3 frames of the whole clip with B on and 0 with B
off** (P1 f214/f215, P2 f889) — i.e. even a follow-up probe mechanism would
recover at most **2 of the 5** far serves on this clip, because for P4/P6/P8 the
detector never saw the toss. Recovering the far serves therefore needs
(a) a contact-probe serve signature that does not require a fed ascent and
(b) detection evidence on the far toss — a recognition+detection mechanism, not
the ball-track admission T5 was approved for.

**Structural limit of B itself:** the contact probe tests `c` exactly at
`frame + CONTACT_DELAY` (7). A lock that arrives later than contact + 7 can
never feed that contact — P2 locks at +10 f, so P2 is unreachable by
construction even with a perfect chain. B's ceiling on this clip is 4/5.

## Decision

**B is the winner of the two** (no new lock opportunities, near-side byte
identity by construction, one extra dead-time candidate; A costs 19 spurious
locks for the same zero recovery), and it is the only half of the far-serve fix
that is actually needed: it converts the step-1 finding ("the pre-contact
history is missing") into a fixed evidence gap. **But it does not pass the
recovery bar** (0/5 far serves, not ≥ 4/5), so it ships **DEFAULT OFF**
(`ball_backfill_lookback = 0`) and is not adopted as the T5 mechanism. The
finding it produced is the session's deliverable: the far-side serve loss is
TWO defects — ball-track admission (closed by B, available on request) and the
contact probe's serve signature (open, needs owner approval as a new mechanism).

Reproduce:

```bash
venv/bin/python scripts/probe_serve_mechanisms.py \
    --diag output/t4/dev_diag.jsonl \
    --ground-truth ground_truth/video_ari_joan_8_first_points_annotations.json \
    --calibration calibrations/video_ari_joan_8_first_points.json \
    --json output/t5/dev_mechanisms.json --markdown docs/t5_mechanism_ab.md
```
