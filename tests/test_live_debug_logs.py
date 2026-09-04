"""Tests for the live-debug spike log helpers.

``describe_spike_record`` formats a resolved SpikeAnalyzer record for the
live-debug log lines ("from B2 -> lands A7 (kill)"). It is a module-level
pure function so it can be tested without constructing a processor.
"""

from src.analysis.live_debug_processor import describe_spike_record


def _rec(**kw):
    base = {
        "frame": 297,
        "track_id": 1,
        "attack_zone": {"side": "B", "zone": 2},
        "outcome": "kill",
        "landing_zone": {"side": "A", "zone": 7},
        "dug_zone": None,
    }
    base.update(kw)
    return base


class TestDescribeSpikeRecord:
    def test_kill_with_landing_zone(self):
        assert describe_spike_record(_rec()) == "from B2 -> lands A7 (kill)"

    def test_kill_out_of_bounds_has_no_zone(self):
        r = _rec(outcome="kill", landing_zone=None)
        assert describe_spike_record(r) == "from B2 -> lands out of bounds (kill)"

    def test_out(self):
        r = _rec(outcome="out", landing_zone=None)
        assert describe_spike_record(r) == "from B2 -> lands out of bounds (out)"

    def test_dug_with_zone(self):
        r = _rec(outcome="dug", landing_zone=None,
                 dug_zone={"side": "B", "zone": 8})
        assert describe_spike_record(r) == "from B2 -> dug at B8 (dug)"

    def test_dug_without_zone(self):
        r = _rec(outcome="dug", landing_zone=None, dug_zone=None)
        assert describe_spike_record(r) == "from B2 -> dug (zone unknown) (dug)"

    def test_blocked_kept_unknown(self):
        assert describe_spike_record(_rec(outcome="blocked", landing_zone=None)) == \
            "from B2 -> blocked (blocked)"
        assert describe_spike_record(_rec(outcome="kept", landing_zone=None)) == \
            "from B2 -> kept up by the attack team (kept)"
        assert describe_spike_record(_rec(outcome="unknown", landing_zone=None)) == \
            "from B2 -> no landing within horizon (unknown)"

    def test_missing_origin_renders_placeholder(self):
        r = _rec(attack_zone=None)
        assert describe_spike_record(r) == "from ? -> lands A7 (kill)"
