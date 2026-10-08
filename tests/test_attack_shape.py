"""Post-run attack shape (src/postrun/attack_shape): hard vs touch from the
flight in metres and seconds.

Synthetic attacks are scripted in court metres (tests/postrun_sim.py), so the
launch the layer reads back has a known answer. The real match and the
practice clips pin the owner-GT score when the runs are on disk.
"""

import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "scripts"))

import postrun_sim as sim  # noqa: E402
import score_spike_type as scorer  # noqa: E402
from src.postrun import attack_shape  # noqa: E402
from src.postrun.attack_shape import (  # noqa: E402
    LOFT_ANGLE_DEG,
    PLACED_SPEED_MS,
    TYPE_HARD,
    TYPE_TOUCH,
    AttackLaunch,
)
from src.postrun.reconstruct import format_report, reconstruct  # noqa: E402

SPIKER = sim.NEAR_A["P1B"]            # the far player who attacks in standard_rally


def _attack(landing, landing_dt, exchanges=1):
    """Reconstruct one rally; return its first attack touch (payload)."""
    b = sim.StreamBuilder(16.0)
    script = sim.standard_rally(2.0, "near", sim.NEAR_A, exchanges=exchanges, landing=landing)
    script.landing_dt = landing_dt
    b.rally(script)
    result = reconstruct(b.build(), b.g)
    attacks = [t for t in result["points"][0]["touches"] if t["action"] == "spike"]
    return attacks[0], result


def _truth(landing, landing_dt, z1=0.11):
    """Launch the simulator scripted: (rise m/s, horizontal m/s)."""
    rise = (z1 - sim.SPIKE_Z + 0.5 * 9.81 * landing_dt ** 2) / landing_dt
    return rise, math.hypot(landing[0] - SPIKER[0], landing[1] - SPIKER[1]) / landing_dt


def test_a_flat_fast_ball_is_hard_and_its_launch_is_read_in_metres():
    attack, _ = _attack((4.0, 12.5), 0.7)
    rise, speed = _truth((4.0, 12.5), 0.7)
    launch = attack["launch"]
    assert attack["spike_type"] == TYPE_HARD
    assert launch["rise_ms"] == pytest.approx(rise, abs=0.4)
    assert launch["speed_ms"] == pytest.approx(math.hypot(rise, speed), rel=0.12)
    assert launch["elevation_deg"] < LOFT_ANGLE_DEG - 8


def test_a_lofted_ball_is_a_touch_even_when_it_travels_as_far():
    attack, _ = _attack((4.0, 12.5), 1.5)
    rise, speed = _truth((4.0, 12.5), 1.5)
    assert attack["spike_type"] == TYPE_TOUCH
    assert attack["launch"]["elevation_deg"] == pytest.approx(
        math.degrees(math.atan2(rise, speed)), abs=5.0)
    assert attack["launch"]["elevation_deg"] > LOFT_ANGLE_DEG + 8


def test_a_slow_flat_drop_over_the_tape_is_a_touch():
    attack, _ = _attack((2.5, 8.7), 0.85)
    launch = attack["launch"]
    assert launch["elevation_deg"] < LOFT_ANGLE_DEG       # flat ...
    assert launch["speed_ms"] < PLACED_SPEED_MS           # ... but placed
    assert attack["spike_type"] == TYPE_TOUCH


def test_a_dug_attack_is_read_twice_and_the_reads_agree():
    attack, result = _attack(None, 0.9, exchanges=2)      # dug 0.9 s later, 6 m away
    launch = attack["launch"]
    assert launch["elevation_ends_deg"] is not None
    assert launch["elevation_ends_deg"] == pytest.approx(launch["elevation_deg"], abs=6.0)
    assert attack["spike_type"] == TYPE_HARD
    assert "(hard)" in format_report(result)


def test_two_speed_reads_on_different_sides_of_the_split_give_no_type():
    def launch(speed, ends):
        return AttackLaunch(frame=0, samples=12, rise_ms=3.3, horizontal_ms=speed,
                            horizontal_ends_ms=ends)

    assert launch(9.4, 6.2).elevation_deg < LOFT_ANGLE_DEG < launch(9.4, 6.2).elevation_ends_deg
    assert launch(9.4, 6.2).spike_type() is None          # precision first: no guess
    assert launch(9.4, 9.0).spike_type() == TYPE_HARD
    assert launch(5.0, 5.5).spike_type() == TYPE_TOUCH
    assert launch(9.4, None).spike_type() == TYPE_HARD    # nothing to cross-check with


def test_only_observed_attacks_get_a_type_and_other_touches_never_do():
    _, result = _attack((4.0, 12.5), 0.7, exchanges=2)
    for t in result["points"][0]["touches"]:
        if t["action"] not in ("spike", "overpass"):
            assert t["spike_type"] is None and t["launch"] is None


def test_a_flight_too_short_to_fit_reads_nothing():
    b = sim.StreamBuilder(16.0)
    script = sim.standard_rally(2.0, "near", sim.NEAR_A)
    frames = b.rally(script)
    b.hide(frames[-1] + 4, b.n - 1)                       # the tracker loses the ball at the hit
    attack = [t for t in reconstruct(b.build(), b.g)["points"][0]["touches"]
              if t["action"] in ("spike", "overpass") and t["observed"]]
    assert attack and all(t["spike_type"] is None and t["launch"] is None for t in attack)


def test_the_constants_are_metres_seconds_and_degrees_not_pixels():
    # AGENTS.md §11: never a pixel threshold in the post-run layer.
    assert 15.0 < attack_shape.LOFT_ANGLE_DEG < 40.0
    assert 2.0 < attack_shape.PLACED_SPEED_MS < 7.0
    assert all(0.0 < s < 0.5 for s in attack_shape.CONTACT_SEARCH_S)


# --------------------------------------------------------------------------- #
# the real runs (skip when not on disk)
# --------------------------------------------------------------------------- #

RUNS = REPO / "output" / "postrun"


@pytest.fixture(scope="module")
def match_types():
    run = RUNS / "20260920_match"
    if not (run / "diag.jsonl").exists():
        pytest.skip("20260920 match run (output/postrun/20260920_match) not on disk")
    data = scorer.load_run(run, str(REPO / "calibrations/20260920_match_ari_joan_lost.json"))
    gt = scorer.gt_spikes(json.loads((REPO / scorer.GT_CONTACTS).read_text()))
    return data, {read: scorer.score(data["recon"], data["spikes"], gt, read=read)
                  for read in (scorer.READ_CAUSAL, scorer.READ_POSTRUN)}


def test_match_types_clear_the_v1_bars_and_beat_the_causal_read(match_types):
    _, scores = match_types
    post, causal = scores[scorer.READ_POSTRUN], scores[scorer.READ_CAUSAL]
    assert post["accuracy"] >= scorer.ACCURACY_BAR and post["coverage"] >= scorer.COVERAGE_BAR
    assert post["correct"] > causal["correct"] and post["covered"] > causal["covered"]


def test_match_overpasses_are_never_typed_hard(match_types):
    data, _ = match_types
    types = [t["spike_type"] for p in data["recon"]["points"] for t in p["touches"]
             if t["action"] == "overpass"]
    assert types and TYPE_HARD not in types


def test_practice_clips_type_every_covered_spike_right():
    if not (RUNS / "entreno_3" / "diag.jsonl").exists():
        pytest.skip("practice runs (output/postrun/entreno_<n>) not on disk")
    right = covered = 0
    for index in range(1, 8):
        clip = RUNS / f"entreno_{index}"
        data = scorer.load_run(clip, str(REPO / f"calibrations/video_entreno_{index}.json"))
        r = scorer.score(data["recon"], [], scorer.clip_gt_spikes(index),
                         read=scorer.READ_POSTRUN)
        right, covered = right + r["correct"], covered + r["covered"]
    assert covered >= 6 and right == covered
