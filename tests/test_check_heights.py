"""scripts/check_heights.py (V2): the pure verdicts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import check_heights as ch  # noqa: E402


def _stat(near, far):
    return {"near": {"n": 100, "p50": near, "p75": near}, "far": {"n": 100, "p50": far, "p75": far}}


def test_stature_passes_when_near_and_far_agree():
    stat = {s: _stat(1.80, 1.76) for s in ch.SLOTS}
    v = ch.stature_verdict(stat, None)
    assert v["pass"] and not v["with_real_heights"]


def test_stature_fails_when_one_player_reads_shorter_far_away():
    stat = {s: _stat(1.80, 1.78) for s in ch.SLOTS}
    stat["P2A"] = _stat(1.80, 1.55)
    v = ch.stature_verdict(stat, None)
    assert not v["pass"] and [r["agree"] for r in v["rows"]] == [True, False, True, True]


def test_stature_against_the_real_height():
    stat = {s: _stat(1.80, 1.80) for s in ch.SLOTS}
    assert ch.stature_verdict(stat, {"P1A": 1.82})["pass"]
    assert not ch.stature_verdict(stat, {"P1A": 2.05})["pass"]       # 12 % off


def test_stature_needs_both_halves():
    stat = {s: _stat(1.8, 1.8) for s in ch.SLOTS}
    del stat["P1B"]["far"]
    assert not ch.stature_verdict(stat, None)["pass"]


def _crossing(clear, timing=0.0, live=True):
    return {"frame": 1, "u": 0.0, "clearance_m": clear, "samples": 10, "timing_err_m": timing, "live": live}


def test_net_verdict_counts_only_live_well_conditioned_crossings():
    good = [_crossing(0.5)] * ch.MIN_NET_CROSSINGS
    dead = [_crossing(-2.3, live=False)] * 10                       # a ball rolling on the sand
    noisy = [_crossing(-1.0, timing=0.9)] * 10                      # timing alone moves it a metre
    v = ch.net_verdict(good + dead + noisy)
    assert v["pass"] and v["good"]["n"] == ch.MIN_NET_CROSSINGS and v["all"]["n"] == 40


def test_net_verdict_fails_on_a_live_ball_far_under_the_tape():
    cross = [_crossing(0.5)] * 30 + [_crossing(-0.6)]
    assert not ch.net_verdict(cross)["pass"]


def test_net_verdict_needs_enough_crossings():
    v = ch.net_verdict([_crossing(0.5)] * 3)
    assert not v["pass"] and "well-conditioned" in v["note"]
    assert not ch.net_verdict([])["pass"]


def _recon(heights):
    touches = [{"action": a, "side": side, "height_m": h, "observed": True, "player": "P1A"}
               for (a, side), hs in heights.items() for h in hs]
    return {"points": [{"touches": touches}]}


def test_contact_heights_compare_near_and_far_per_action():
    ok = ch.contact_heights(_recon({("spike", "near"): [2.5] * 8, ("spike", "far"): [2.45] * 8}))
    assert ok["pass"]
    bad = ch.contact_heights(_recon({("dig", "near"): [1.3] * 8, ("dig", "far"): [1.7] * 8}))
    assert not bad["pass"] and bad["rows"][0]["ok"] is False


def test_contact_heights_do_not_pass_on_too_little_data():
    assert not ch.contact_heights(_recon({("spike", "near"): [2.5] * 3, ("spike", "far"): [2.5] * 3}))["pass"]


def test_parse_heights():
    assert ch.parse_heights("P1A=1.8,P2B=1.7") == {"P1A": 1.8, "P2B": 1.7}
    assert ch.parse_heights(None) is None
    with pytest.raises(SystemExit):
        ch.parse_heights("X=1.8")
