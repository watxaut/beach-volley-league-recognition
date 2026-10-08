"""scripts/score_spike_type.py (V1): the pure scoring, on a synthetic match."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from score_spike_type import (  # noqa: E402
    ACCURACY_BAR,
    COVERAGE_BAR,
    READ_POSTRUN,
    clip_gt_spikes,
    gt_spikes,
    score,
)


def _recon(frames, action="spike"):
    return {"points": [{"touches": [{"frame": f, "action": action} for f in frames]}]}


def _gt(items):
    return [{"point": 1, "frame": f, "type": t, "outcome": None} for f, t in items]


def test_all_right_and_all_covered_passes():
    r = score(_recon([100, 200]), [{"frame": 101, "spike_type": "hard"}, {"frame": 199, "spike_type": "touch"}],
              _gt([(100, "hard"), (200, "touch")]))
    assert (r["coverage"], r["accuracy"], r["pass"]) == (1.0, 1.0, True)


def test_a_spike_without_a_causal_record_is_uncovered_not_wrong():
    r = score(_recon([100, 200]), [{"frame": 100, "spike_type": "hard"}],
              _gt([(100, "hard"), (200, "touch")]))
    assert (r["covered"], r["correct"], r["coverage"]) == (1, 1, 0.5)
    assert r["confusion"]["touch"]["none"] == 1
    assert r["pass"] is False


def test_wrong_type_lowers_accuracy_and_fails():
    r = score(_recon([100]), [{"frame": 100, "spike_type": "touch"}], _gt([(100, "hard")]))
    assert (r["coverage"], r["accuracy"]) == (1.0, 0.0) and r["pass"] is False
    assert r["confusion"]["hard"]["touch"] == 1


def test_unlabelled_gt_spikes_are_not_scored_and_far_records_do_not_join():
    r = score(_recon([100, 500]), [{"frame": 140, "spike_type": "hard"}],   # 40 f away: no join
              _gt([(100, "hard"), (500, None)]))
    assert r["n_labelled"] == 1 and r["covered"] == 0


def test_gt_spikes_reads_the_contacts_file_shape():
    contacts = {"points": [{"point": 3, "contacts": [
        {"action": "serve", "match_frame": 1}, {"action": "spike", "match_frame": 40, "spike_type": "touch",
                                                "outcome": "kill"}]}]}
    assert gt_spikes(contacts) == [{"point": 3, "frame": 40, "type": "touch", "outcome": "kill"}]


def test_the_bars_are_the_pre_registered_ones():
    assert (ACCURACY_BAR, COVERAGE_BAR) == (0.85, 0.80)


def test_the_post_run_read_scores_the_type_the_touch_carries():
    recon = {"points": [{"touches": [
        {"frame": 100, "action": "spike", "spike_type": "hard"},
        {"frame": 200, "action": "overpass", "spike_type": "touch"},
        {"frame": 300, "action": "spike", "spike_type": None}]}]}
    causal = [{"frame": 100, "spike_type": "touch"}]            # ignored by this read
    r = score(recon, causal, _gt([(100, "hard"), (200, "touch"), (300, "touch")]), read=READ_POSTRUN)
    assert (r["covered"], r["correct"], r["n_labelled"]) == (2, 2, 3)
    assert r["confusion"]["touch"]["none"] == 1 and r["attacks"] == {"n": 3, "with_record": 2}


def test_practice_gt_reads_a_type_from_the_event_or_its_overrides():
    types = {g["frame"]: g["type"] for g in clip_gt_spikes(3)}
    assert types[178] == "touch" and types[541] == "hard"
    assert {g["frame"]: g["type"] for g in clip_gt_spikes(5)}[300] == "touch"   # overrides
