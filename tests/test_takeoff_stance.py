"""SR1c: the takeoff-stance read for ``behind_baseline`` (open point 30, M-a).

Diagnose-only, so what is pinned here is the PROBE, not a mechanism: the four
places a wrong implementation would silently produce a flattering number.

* the ``K``-window is ``[c-K, c]`` INCLUSIVE and skips coasted (predicted)
  frames -- a frozen box held by the off-court hold horizon is exactly the
  situation M-a is supposed to read past, so a probe that trusts it is circular;
* the stance foot is the max y for team A (near, behind the bottom line) and the
  min y for team B (far, behind the top line) -- the two sides are mirror images
  and swapping them makes every far read behind the near line;
* ``K = 0`` must reduce to the shipped read (the reproduction gate), and an
  empty window must fall back to the shipped default, false;
* the flip rule needs ALL FOUR legs, and the buckets must not collapse: a GT
  non-serve contact inside the tolerance is a different failure from no GT
  contact at all.

The real numbers over the artifacts are a script run (``output/`` is
git-ignored):
``venv/bin/python scripts/probe_takeoff_stance.py``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "probe_takeoff_stance", ROOT / "scripts" / "probe_takeoff_stance.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


S = _load()


class StubCourt:
    """``is_behind_baseline`` with the real signature and a fixed threshold."""

    def __init__(self, threshold_y: int = 761):
        self.threshold_y = threshold_y
        self.calls = []

    def is_behind_baseline(self, point, team, margin_px: int = 0):
        self.calls.append((tuple(point), team))
        if team == "A":
            return point[1] > self.threshold_y - margin_px
        return point[1] < -self.threshold_y + margin_px


def _player(track_id, x0, x1, y1, predicted=False):
    return {"track_id": track_id, "bbox": [x0, 0.0, x1, float(y1)],
            "predicted": predicted}


def _frames(mapping):
    """``{frame: [player, ...]}`` -> dump-shaped ``{frame: {"players": [...]}}``."""
    return {t: {"players": players} for t, players in mapping.items()}


# -- foot + window ----------------------------------------------------------

def test_foot_is_bbox_bottom_centre_int_truncated():
    # Same arithmetic as ActionClassifier._build_contact: int((x0+x1)/2), int(y1).
    assert S.foot_of(_player(3, 100.4, 200.6, 740.9)) == (150, 740)
    assert S.foot_of({"bbox": None}) is None
    assert S.foot_of({"bbox": [1, 2]}) is None


def test_window_is_inclusive_and_spans_c_minus_k_to_c():
    frames = _frames({t: [_player(7, 10, 20, 700)] for t in range(95, 106)})
    feet = S.window_feet(frames, 7, 105, 10)
    assert [t for t, _ in feet] == [95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105]
    # K = 0 is the contact frame alone -- the shipped read.
    assert [t for t, _ in S.window_feet(frames, 7, 105, 0)] == [105]


def test_window_skips_predicted_and_other_tracks():
    frames = _frames({
        100: [_player(7, 10, 20, 700), _player(9, 10, 20, 999)],
        101: [_player(7, 10, 20, 700, predicted=True)],
        102: [_player(7, 10, 20, 705)],
    })
    feet = S.window_feet(frames, 7, 102, 10)
    assert [(t, f[1]) for t, f in feet] == [(100, 700), (102, 705)]


# -- stance pick ------------------------------------------------------------

def test_stance_foot_is_max_y_for_A_and_min_y_for_B():
    feet = [(100, (50, 700)), (101, (50, 760)), (102, (50, 730))]
    assert S.stance_foot(feet, "A") == (50, 760)
    assert S.stance_foot(feet, "B") == (50, 700)
    assert S.stance_foot([], "A") is None
    assert S.stance_foot(feet, None) is None
    assert S.stance_foot(feet, "C") is None


def test_bb_k_uses_the_real_test_on_the_stance_foot():
    court = StubCourt(threshold_y=761)
    # The contact frame is airborne (736.8, inside the line); 10 f earlier the
    # same track stood at 780, behind it -- the P9-P12 shape.
    contact = 100
    frames = _frames({t: [_player(2, 100, 140, 780)]
                      for t in range(contact - 10, contact)})
    frames[contact] = {"players": [_player(2, 100, 140, 736.8)]}
    read = S.behind_baseline_at_k(court, frames, 2, contact, "A", 0)
    assert read["behind_baseline"] is False and read["foot"] == [120, 736]
    read = S.behind_baseline_at_k(court, frames, 2, contact, "A", 10)
    assert read["behind_baseline"] is True and read["foot"] == [120, 780]
    assert court.calls[-1] == ((120, 780), "A")


def test_bb_k_empty_window_falls_back_to_the_shipped_default():
    court = StubCourt()
    frames = _frames({100: [_player(2, 100, 140, 780, predicted=True)]})
    read = S.behind_baseline_at_k(court, frames, 2, 100, "A", 10)
    assert read == {"behind_baseline": False, "foot": None, "frames_used": 0}


def test_bb_k_unknown_team_is_never_behind_baseline():
    court = StubCourt()
    frames = _frames({100: [_player(2, 100, 140, 900)]})
    assert S.behind_baseline_at_k(court, frames, 2, 100, None, 10)["behind_baseline"] is False


# -- the flip rule ----------------------------------------------------------

@pytest.mark.parametrize("action,flips", [
    ("spike", True), ("dig", True), ("set", False), ("overpass", False),
    ("block", False), ("serve", False), (None, False),
])
def test_flip_rule_only_spike_and_dig(action, flips):
    action_row = {"action": action, "frame_number": 100}
    assert S.flips_to_serve(action_row, True, False, True) is flips


def test_flip_rule_needs_all_four_legs():
    action = {"action": "spike", "frame_number": 100}
    assert S.flips_to_serve(action, True, False, True) is True
    assert S.flips_to_serve(action, False, False, True) is False   # not rally_start
    assert S.flips_to_serve(action, True, True, True) is False    # already behind
    assert S.flips_to_serve(action, True, False, False) is False  # still inside


def test_rally_start_is_the_resolver_rule():
    actions = [{"frame_number": 10}, {"frame_number": 99}, {"frame_number": 190}]
    flags = S.rally_start_flags(actions, gap=90)
    assert flags == {10: True, 99: False, 190: True}


# -- the buckets ------------------------------------------------------------

ROWS = [{"frame": 5496, "point": 9, "side": "near", "tolerance": 15}]
CONTACTS = [{"frame": 5496, "action": "serve", "point": 9, "side": "near"},
            {"frame": 5700, "action": "dig", "point": 9, "side": "near"},
            {"frame": 6035, "action": "serve", "point": 10, "side": "near"}]


def test_bucket_recovered_needs_an_unhit_gt_serve_of_the_same_side():
    assert S.classify_flip(5496, "near", ROWS, CONTACTS, [])["bucket"] == "recovered"
    other = S.classify_flip(5496, "far", ROWS, CONTACTS, [])
    assert other["bucket"] == "gt_serve_not_recovered"


def test_bucket_recovered_excludes_a_serve_already_emitted():
    already = [{"frame": 5494, "side": "near"}]
    assert S.classify_flip(5496, "near", ROWS, CONTACTS, already)["bucket"] \
        == "gt_serve_not_recovered"


def test_bucket_false_breaks_gt_is_a_gt_non_serve_contact_inside_the_tolerance():
    hit = S.classify_flip(5700, "near", ROWS, CONTACTS, [])
    assert hit["bucket"] == "false_breaks_gt" and hit["gt_action"] == "dig"


def test_bucket_false_dead_time_is_no_gt_contact_at_all():
    assert S.classify_flip(7000, "near", ROWS, CONTACTS, [])["bucket"] == "false_dead_time"


def test_tolerance_boundary_is_inclusive_on_both_sides():
    assert S.TOLERANCE == 15
    assert S.classify_flip(5481, "near", ROWS, CONTACTS, [])["bucket"] == "recovered"
    assert S.classify_flip(5480, "near", ROWS, CONTACTS, [])["bucket"] == "false_dead_time"


# -- session bookkeeping ----------------------------------------------------

def test_candidate_records_and_emitted_actions_are_deduplicated():
    frames = {
        30: {"candidates": [{"stage": "candidate_passed_gates", "frame": 29,
                             "track_id": 4, "team": "A", "gesture": "bump_set",
                             "behind_baseline": True}],
             "actions": [{"action": "serve", "frame_number": 29}]},
        31: {"actions": [{"action": "dig", "frame_number": 74}]},
        32: {"actions": [{"action": "serve", "frame_number": 29}]},
    }
    records = S.candidate_records(frames)
    assert [(r["frame"], r["track_id"], r["shipped_behind_baseline"]) for r in records] \
        == [(29, 4, True)]
    assert [a["frame_number"] for a in S.emitted_actions(frames)] == [29, 74]