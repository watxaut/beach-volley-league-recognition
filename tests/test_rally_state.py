"""Tests for rally-state tracking.

Run with: pytest tests/test_rally_state.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.recognition.rally_state import compute_rally_state


def make_event(frame: int, action: str, team: str) -> dict:
    """Minimal event dict; compute_rally_state fills the rest."""
    return {
        "frame": frame,
        "final_action": action,
        "player_team": team,
        "raw_visual_actions": [action],
    }


# --- Single-event cases ---


def test_first_event_starts_rally_one():
    events = [make_event(10, "serve", "A")]
    compute_rally_state(events)
    assert events[0]["rally_id"] == 1
    assert events[0]["team_in_possession"] == "A"
    assert events[0]["touch_number"] == 1
    assert events[0]["preceded_by_attack"] is False


def test_empty_events_is_noop():
    events = []
    compute_rally_state(events)
    assert events == []


# --- Same-team possession: touch_number increments ---


def test_same_team_increments_touch():
    events = [
        make_event(10, "dig", "A"),
        make_event(20, "set", "A"),
        make_event(30, "spike", "A"),
    ]
    compute_rally_state(events)
    assert [e["touch_number"] for e in events] == [1, 2, 3]
    assert all(e["team_in_possession"] == "A" for e in events)
    assert all(e["rally_id"] == 1 for e in events)


# --- Team change: new possession, touch resets ---


def test_team_change_starts_new_possession():
    events = [
        make_event(10, "dig", "A"),
        make_event(20, "set", "A"),
        make_event(30, "dig", "B"),
    ]
    compute_rally_state(events)
    assert [e["touch_number"] for e in events] == [1, 2, 1]
    assert events[2]["team_in_possession"] == "B"


def test_rally_id_increments_only_on_first_event():
    # rally_id increments only when transitioning out of IDLE (first event),
    # not on every possession change between teams. Two possessions from
    # one rally (dig/set/spike by A, then dig by B) share rally_id=1.
    events = [
        make_event(10, "serve", "A"),
        make_event(20, "dig", "B"),  # team change, same rally
        make_event(30, "set", "B"),
    ]
    compute_rally_state(events)
    assert all(e["rally_id"] == 1 for e in events)


# --- preceded_by_attack ---


def test_dig_after_spike_is_preceded_by_attack():
    events = [
        make_event(10, "spike", "A"),
        make_event(20, "dig", "B"),
    ]
    compute_rally_state(events)
    assert events[1]["preceded_by_attack"] is True


def test_dig_after_serve_is_preceded_by_attack():
    events = [
        make_event(10, "serve", "A"),
        make_event(20, "dig", "B"),
    ]
    compute_rally_state(events)
    assert events[1]["preceded_by_attack"] is True


def test_set_after_dig_same_team_not_preceded_by_attack():
    events = [
        make_event(10, "dig", "A"),
        make_event(20, "set", "A"),
    ]
    compute_rally_state(events)
    assert events[1]["preceded_by_attack"] is False


def test_spike_by_same_team_after_spike_not_preceded_by_attack():
    # Two touches by same team -- second isn't "after an attack" in the
    # defensive sense.
    events = [
        make_event(10, "spike", "A"),
        make_event(20, "spike", "A"),
    ]
    compute_rally_state(events)
    assert events[1]["preceded_by_attack"] is False


# --- Out-of-order events: recompute is robust ---


def test_out_of_order_events_processed_chronologically():
    events = [
        make_event(30, "spike", "A"),
        make_event(10, "dig", "A"),
        make_event(20, "set", "A"),
    ]
    compute_rally_state(events)
    by_frame = sorted(events, key=lambda e: e["frame"])
    assert [e["touch_number"] for e in by_frame] == [1, 2, 3]


# --- Overrides cascade ---


def test_override_touch_number_cascades_to_next_event():
    events = [
        make_event(10, "dig", "A"),
        make_event(20, "set", "A"),
        make_event(30, "spike", "A"),
    ]
    events[1]["overrides"] = {"touch_number": 5}
    compute_rally_state(events)
    assert events[0]["touch_number"] == 1
    assert events[1]["touch_number"] == 5
    assert events[2]["touch_number"] == 6


def test_override_team_in_possession_cascades():
    events = [
        make_event(10, "dig", "A"),
        make_event(20, "set", "A"),
    ]
    events[0]["overrides"] = {"team_in_possession": "B"}
    compute_rally_state(events)
    # Event 0 overridden to B. Event 1's player_team is A -- differs from
    # cascaded B, so it starts a new possession.
    assert events[0]["team_in_possession"] == "B"
    assert events[1]["team_in_possession"] == "A"
    assert events[1]["touch_number"] == 1


def test_override_survives_recompute():
    events = [make_event(10, "dig", "A"), make_event(20, "set", "A")]
    events[0]["overrides"] = {"touch_number": 7}
    compute_rally_state(events)
    # Recompute again -- override should still apply.
    compute_rally_state(events)
    assert events[0]["touch_number"] == 7
    assert events[1]["touch_number"] == 8


# --- Unknown team (no calibration) ---


def test_unknown_team_treated_as_regular_team_value():
    # Without calibration, player_team is "?". The state machine still runs
    # but the resulting rally context is meaningless. This just verifies we
    # don't crash and produce consistent output.
    events = [
        make_event(10, "dig", "?"),
        make_event(20, "set", "?"),
    ]
    compute_rally_state(events)
    assert all(e["team_in_possession"] == "?" for e in events)
    assert [e["touch_number"] for e in events] == [1, 2]
