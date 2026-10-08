#!/usr/bin/env python3
"""One-at-a-time sensitivity sweep of the post-run layer's constants.

    venv/bin/python scripts/sweep_postrun.py output/postrun/20260920_match

Every constant of ``src.postrun`` is a physical quantity (metres, seconds) or
a likelihood cost. This moves each one well away from its shipped value and
re-scores the reconstruction against the owner GT, so a result that only
holds on a knife edge shows up as a row that falls apart. The last column is
the hard / touch read of ``attack_shape`` (right / typed of the 32 owner-typed
spikes, ``scripts/score_spike_type.py``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_postrun import GT_CONTACTS, GT_POINTS, load_gt, score_reconstruction  # noqa: E402
from score_spike_type import READ_POSTRUN, gt_spikes  # noqa: E402
from score_spike_type import score as score_types  # noqa: E402
from src.postrun import attack_shape, ball_flights, match, rallies, touches  # noqa: E402
from src.postrun.geometry import CourtGeometry  # noqa: E402
from src.postrun.reconstruct import reconstruct  # noqa: E402
from src.postrun.stream import load_stream  # noqa: E402

#: (module, constant, values to try). Tuples are scaled element-wise.
SWEEP = [
    (rallies, "SERVE_MIN_PEAK_M", (1.9, 2.4)),
    (rallies, "SERVE_MIN_SPEED_MS", (4.0, 6.5)),
    (rallies, "SERVE_MIN_TRAVEL_M", (3.5, 6.5)),
    (rallies, "NEAR_SERVE_MIN_Y", (13.3, 14.6)),
    (rallies, "MAX_AIR_S", (2.8, 4.0)),
    (rallies, "MIN_DEAD_TIME_S", (3.0, 8.0)),
    (rallies, "GROUND_EVENT_HEIGHT_M", (0.45, 0.8)),
    (rallies, "GROUND_CERTAIN_HEIGHT_M", (0.25, 0.45)),
    (rallies, "SAND_REBOUND_MAX_M", (1.0, 1.7)),
    (rallies, "LIVE_MIN_PEAK_M", (1.1, 2.0)),
    (rallies, "NET_FAULT_MAX_S", (0.5, 1.2)),
    (ball_flights, "MERGE_EVENTS_S", (0.15, 0.35)),
    (ball_flights, "GAP_TOUCH_MAX_S", (0.5, 1.2)),
    (ball_flights, "GAP_STEP_MS", (2.5, 6.0)),
    (ball_flights, "GAP_MISS_M", (0.6, 1.6)),
    (ball_flights, "GAP_BLINK_S", (0.15, 0.4)),
    (ball_flights, "GAP_MIN_FLIGHT_MS", (0.8, 3.0)),
    (rallies, "PASS_MIN_TRAVEL_M", (1.0, 2.5)),
    (rallies, "SERVE_MIN_FLIGHT_S", (0.3, 0.6)),
    (ball_flights, "REENTRY_GAP_S", (2.0, 4.5)),
    (ball_flights, "RUN_HOLE_S", (0.08, 0.3)),
    (ball_flights, "GROUND_RATIO_MAX", (1.1, 1.3)),
    (touches, "DEPTH_SPLIT_BIAS_M", (0.7, 1.9)),
    (touches, "DEPTH_SIGMA_M", (0.4, 1.0)),
    (touches, "STANCE_SIGMA_M", (0.9, 1.9)),
    (touches, "REACH_SIGMA", (0.25, 0.5)),
    (touches, "PLAYER_COST_CAP", (1.5, 4.0)),
    (touches, "SKIP_COST", (2.5, 6.0)),
    (touches, "SKIP_COST_GAP_VERTEX", (1.0, 4.0)),
    (touches, "HIDDEN_COST_GAP", (0.6, 2.4)),
    (touches, "HIDDEN_COST_TRACKED", (2.5, 6.0)),
    (touches, "DOUBLE_CROSS_COST", (1.0, 4.0)),
    (touches, "POSSESSION_END_COST", ({1: 0.9, 2: 1.1, 3: 0.15},
                                      {1: 2.7, 2: 3.3, 3: 0.45})),
    (touches, "SAME_SIDE_INTERVAL_S", ((1.4, 0.55), (1.9, 0.55), (1.65, 0.8))),
    (touches, "CROSS_INTERVAL_S", ((0.95, 0.5), (1.35, 0.5), (1.15, 0.75))),
    (touches, "ATTACK_BELOW_TAPE_M", (0.15, 0.45)),
    (touches, "REACH_CREDIT_MAX", (0.4, 0.9)),
    (match, "ARC_SLACK_S", (0.2, 0.6)),
    (attack_shape, "LOFT_ANGLE_DEG", (20.0, 30.0)),
    (attack_shape, "PLACED_SPEED_MS", (3.0, 6.5)),
    (attack_shape, "CONTACT_SEARCH_S", ((0.04, 0.12), (0.2, 0.4))),
    (attack_shape, "MIN_FLIGHT_SAMPLES", (3, 8)),
    (attack_shape, "MIN_FLIGHT_S", (0.1, 0.3)),
]


def summarise(score):
    p, sv, w, t = score["points"], score["serve"], score["winners"], score["touches"]
    matched = t.get("matched", 0)
    return (f"points {p['recon']:>2}/{p['matched']:>2}m/{p['false']}f  "
            f"serve-half {sv['side_ok']:>2}/{sv['n']}  win {w['ok']:>2}/{w['n']}  "
            f"P {matched / max(t.get('pred', 0), 1):.3f}  R {matched / max(t.get('gt', 0), 1):.3f}  "
            f"action {t.get('action_ok', 0) / max(t.get('action_n', 0), 1):.3f}  "
            f"half {t.get('side_ok', 0) / max(matched, 1):.3f}  final {score['final_score']}"
            f"  type {score['types']['correct']}/{score['types']['covered']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run_dir")
    parser.add_argument("--calibration",
                        default="calibrations/20260920_match_ari_joan_lost.json")
    args = parser.parse_args()
    stream = load_stream(str(Path(args.run_dir) / "diag.jsonl"))
    geometry = CourtGeometry.from_file(args.calibration)
    gt = load_gt(GT_CONTACTS, GT_POINTS)
    typed = gt_spikes(json.loads(Path(GT_CONTACTS).read_text()))

    def run():
        recon = json.loads(json.dumps(reconstruct(stream, geometry)))
        score = score_reconstruction(recon, gt)
        score["types"] = score_types(recon, [], typed, read=READ_POSTRUN)
        return score

    print(f"{'shipped':<34} {summarise(run())}")
    for module, name, values in SWEEP:
        shipped = getattr(module, name)
        for value in values:
            setattr(module, name, value)
            try:
                line = summarise(run())
            finally:
                setattr(module, name, shipped)
            print(f"{name + '=' + str(value):<34.34} {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
