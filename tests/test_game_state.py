"""Tests for the game on/off state machine.

Run with: pytest tests/test_game_state.py -v

The machine is a pure observer (ball velocity + emitted actions), so all
tests drive it with synthetic frame_result dicts -- no CV stack needed.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analysis.game_state import GameState
from src.analysis.game_state_manager import GameStateManager
from src.utils.config import Config


def make_manager(**overrides) -> GameStateManager:
    cfg = {"game_state_detection": dict(Config.DEFAULT_CONFIG["game_state_detection"], **overrides)}
    return GameStateManager(cfg)


def ball(spd=None):
    """tracked_ball dict; spd None = untracked."""
    if spd is None:
        return None
    return {"center": (960.0, 300.0), "velocity": (spd, 0.0)}


def drive(mgr, frames, actions_at=None):
    """frames: list of speeds (None = untracked). actions_at: {frame: [..]}.

    Returns the GameStateInfo of each frame.
    """
    infos = []
    for i, spd in enumerate(frames):
        fr = {"tracked_ball": ball(spd), "actions": (actions_at or {}).get(i, [])}
        infos.append(mgr.analyze_frame(fr, i))
    return infos


# --- episode layer -------------------------------------------------


def test_quiet_then_sustained_flight_turns_on_backdated():
    mgr = make_manager()
    # 30 quiet frames, then a rally; provisional ON once the rolling window
    # holds fast_confirm_flights (= burst+19), full confirmation at +90
    frames = [None] * 30 + [10.0] * 90 + [None] * 30
    infos = drive(mgr, frames)
    assert mgr.get_current_state() == GameState.GAME_ON
    # the episode start is backdated to the burst start
    assert mgr._episode_start == 30
    on_frames = [i for i, inf in enumerate(infos) if inf.current_state == GameState.GAME_ON]
    assert on_frames and on_frames[0] == 30 + 19  # 20 flights in the 90f window
    confirmed = [i for i, inf in enumerate(infos)
                 if inf.current_state == GameState.GAME_ON and not inf.provisional]
    assert confirmed and confirmed[0] == 30 + 90


def test_isolated_practice_burst_stays_off():
    mgr = make_manager()
    # quiet, one 20-frame burst, then quiet forever -> the episode never
    # confirms and no point is produced; the live badge MAY flicker
    # provisional (sustained-flight window) -- that is its documented cost.
    frames = [None] * 30 + [10.0] * 20 + [None] * 100
    infos = drive(mgr, frames)
    assert mgr.get_current_state() == GameState.GAME_OFF
    assert mgr.get_points() == []
    assert all(inf.current_state == GameState.GAME_OFF or inf.provisional for inf in infos)


def test_burst_without_prior_quiet_does_not_arm():
    mgr = make_manager()
    # flight from frame 0: burst_quiet == 0 < arm_quiet_frames -> the
    # EPISODE never arms/confirms (the provisional badge is window-driven
    # and lights, by design -- a video starting mid-rally reads GAME ON ~).
    frames = [10.0] * 150
    infos = drive(mgr, frames)
    assert mgr.get_current_state() == GameState.GAME_OFF
    assert mgr.get_points() == []
    assert all(inf.provisional for inf in infos[19:])  # window full from f19


def test_tracked_toss_serve_badge_not_delayed_to_next_contact():
    """entreno_3 regression (owner: serve f30, badge ON ~f140). The tracked
    toss's slow apex frames split the pre-serve quiet (6 < arm_quiet_frames),
    so the burst gate can NEVER arm on the serve flight -- the old badge
    waited for the NEXT contact's burst (+3.5 s). The rolling-flight window
    must light the provisional badge during the serve flight itself."""
    mgr = make_manager()
    # hold (quiet), one toss flight frame, apex hang (6 quiet), serve flight
    frames = [None] * 19 + [11.0] + [3.0] * 6 + [10.0] * 80 + [None] * 40
    infos = drive(mgr, frames)
    on_frames = [i for i, inf in enumerate(infos) if inf.current_state == GameState.GAME_ON]
    assert on_frames and on_frames[0] == 44  # 20 flights by f44 (f19 toss + f26..f43)
    assert infos[on_frames[0]].provisional is True
    # the burst gate never armed (quiet 6 < 10): the episode layer stays OFF
    assert mgr._candidate is None
    assert mgr.get_points() == []


def test_provisional_retracts_when_flight_window_drains():
    mgr = make_manager()
    # toss-split burst (never arms a candidate) that flies f26..f55 then
    # dies: the badge shows provisional from f44 (20 flights in the window)
    # and retracts once the window drains below 20 -- with no candidate the
    # episode layer must never confirm.
    frames = [None] * 19 + [11.0] + [3.0] * 6 + [10.0] * 30 + [None] * 160
    infos = drive(mgr, frames)
    prov = [i for i, inf in enumerate(infos) if inf.provisional]
    assert prov and prov[0] == 44 and prov[-1] == 125  # last frame with 20 flights in window
    assert mgr.get_current_state() == GameState.GAME_OFF
    assert mgr.get_points() == []


def test_density_starvation_ends_episode():
    mgr = make_manager()
    # 30 quiet + 90 flight confirms ON; then long quiet drains the window
    frames = [None] * 30 + [10.0] * 90 + [None] * 120
    mgr2 = mgr
    infos = drive(mgr2, frames)
    assert mgr2.get_current_state() == GameState.GAME_OFF
    # ON was reached at some point
    assert any(inf.current_state == GameState.GAME_ON for inf in infos)


def test_short_occlusion_inside_rally_keeps_on():
    mgr = make_manager()
    # rally with a 60-frame untracked gap (real occlusion), then flight again
    frames = [None] * 30 + [10.0] * 90 + [None] * 60 + [10.0] * 90
    infos = drive(mgr, frames)
    assert mgr.get_current_state() == GameState.GAME_ON


def test_static_hold_ends_episode():
    mgr = make_manager()
    # rally, then the server holds the ball (tracked but ~static) for long
    frames = [None] * 30 + [10.0] * 90 + [1.0] * 60
    infos = drive(mgr, frames)
    assert mgr.get_current_state() == GameState.GAME_OFF


# --- point layer ----------------------------------------------------


def action(frame, kind="dig"):
    # production action dicts carry the CONTACT frame under "frame_number"
    return {"action": kind, "frame_number": frame, "confidence": 0.5}


def test_rally_group_with_two_actions_is_a_point():
    mgr = make_manager()
    frames = [None] * 30 + [10.0] * 90 + [None] * 200  # rally then long quiet
    drive(mgr, frames, actions_at={40: [action(40)], 70: [action(70)]})
    mgr.finish()
    pts = mgr.get_points()
    assert len(pts) == 1
    assert pts[0].start_frame == 30
    assert pts[0].n_actions == 2


def test_rally_group_without_actions_is_not_a_point():
    mgr = make_manager()
    frames = [None] * 30 + [10.0] * 90 + [None] * 200
    drive(mgr, frames)
    mgr.finish()
    assert mgr.get_points() == []


def test_split_rally_episodes_merge_into_one_point():
    # Episode 1 confirms at f120, then a static hold (server holds ball)
    # ends it at f139 with episode end = last flight + 1 = 100. Episode 2
    # starts at f160 -- 60 frames after the episode end == group gap, so
    # both episodes are ONE rally group.
    mgr = make_manager()
    frames = (
        [None] * 30
        + [10.0] * 70      # f30-99: rally 1 flights
        + [1.0] * 40       # f100-139: static hold -> episode ends (end=100)
        + [None] * 20      # f140-159
        + [10.0] * 40      # f160-199: rally 2
        + [None] * 200
    )
    drive(mgr, frames, actions_at={40: [action(40)], 170: [action(170)]})
    mgr.finish()
    pts = mgr.get_points()
    assert len(pts) == 1
    assert pts[0].start_frame == 30
    assert pts[0].end_frame == 200
    assert pts[0].n_actions == 2


def test_far_apart_rallies_are_separate_points():
    mgr = make_manager()
    frames = (
        [None] * 30
        + [10.0] * 90
        + [None] * 300   # far beyond group gap -> group 1 finalized
        + [10.0] * 60
        + [None] * 200
    )
    drive(mgr, frames, actions_at={40: [action(40)], 70: [action(70)],
                                   430: [action(430)], 450: [action(450)]})
    mgr.finish()
    pts = mgr.get_points()
    assert len(pts) == 2
    assert pts[1].start_frame > 300


def test_flushed_actions_count_into_open_group():
    mgr = make_manager()
    frames = [None] * 30 + [10.0] * 90 + [None] * 10  # video ends mid-rally
    drive(mgr, frames, actions_at={50: [action(50)]})
    mgr.observe_flushed_actions([action(80)])
    mgr.finish()
    pts = mgr.get_points()
    assert len(pts) == 1 and pts[0].n_actions == 2
    # the trailing group extends to the last flight + 1
    assert pts[0].end_frame == 120


def test_actions_outside_group_do_not_count():
    mgr = make_manager()
    frames = [None] * 30 + [10.0] * 90 + [None] * 200
    # both actions before the group opens
    drive(mgr, frames, actions_at={10: [action(10)], 20: [action(20)]})
    mgr.finish()
    assert mgr.get_points() == []


def test_two_rallies_in_one_group_split_at_contact_silence():
    # practice volleying keeps one long episode alive across two real rallies
    # (here: a 60f quiet bridge, within group gap); the contact silence
    # (> contact_chain_frames) splits the group into 2 points
    mgr = make_manager()
    frames = (
        [None] * 30
        + [10.0] * 121    # f30-150: rally 1 flights
        + [None] * 60     # f151-210: quiet bridge (density window holds)
        + [10.0] * 121    # f211-331: rally 2 flights, same episode/group
        + [None] * 269
    )
    # contacts: rally 1 at 40/70, silence 70->320 (250f > 240), rally 2 at 320/330
    drive(mgr, frames, actions_at={40: [action(40)], 70: [action(70)],
                                   320: [action(320)], 330: [action(330)]})
    mgr.finish()
    pts = mgr.get_points()
    assert len(pts) == 2
    assert pts[0].start_frame == 30
    assert pts[0].end_frame == 70        # interior cut at the last contact
    assert pts[1].start_frame == 320
    assert pts[1].end_frame == 332       # group end = last flight + 1
    assert pts[0].n_actions == 2 and pts[1].n_actions == 2


def test_close_contacts_do_not_split():
    mgr = make_manager()
    frames = [None] * 30 + [10.0] * 90 + [None] * 200
    drive(mgr, frames, actions_at={40: [action(40)], 70: [action(70)]})
    mgr.finish()
    pts = mgr.get_points()
    assert len(pts) == 1
    assert pts[0].n_actions == 2


# --- plumbing --------------------------------------------------------


def test_reset_clears_everything():
    mgr = make_manager()
    drive(mgr, [None] * 30 + [10.0] * 90 + [None] * 200,
         actions_at={40: [action(40)], 70: [action(70)]})
    mgr.finish()
    assert mgr.get_points()
    mgr.reset()
    assert mgr.get_points() == []
    assert mgr.get_current_state() == GameState.GAME_OFF


def test_disabled_manager_stays_off():
    mgr = make_manager(enabled=False)
    infos = drive(mgr, [10.0] * 200)
    assert all(inf.current_state == GameState.GAME_OFF for inf in infos)


def test_info_dict_shape():
    mgr = make_manager()
    infos = drive(mgr, [None] * 30 + [10.0] * 95, actions_at={40: [action(40)], 70: [action(70)]})
    d = infos[-1].to_dict()
    assert d["current_state"] == "game_on"
    assert d["episode_start_frame"] == 30
    assert isinstance(d["points"], list)
    assert d["frame_number"] == 124


def test_ctor_defaults_match_default_config():
    """Config-drift lock: the ctor reads DEFAULT_CONFIG keys, no inline
    fallbacks that can silently diverge."""
    d = Config.DEFAULT_CONFIG["game_state_detection"]
    mgr = GameStateManager({})
    assert mgr.flight_speed_px == d["flight_speed_px"]
    assert mgr.arm_quiet_frames == d["arm_quiet_frames"]
    assert mgr.serve_burst_frames == d["serve_burst_frames"]
    assert mgr.burst_gap_frames == d["burst_gap_frames"]
    assert mgr.confirm_frames == d["confirm_frames"]
    assert mgr.confirm_flight_frames == d["confirm_flight_frames"]
    assert mgr.density_window_frames == d["density_window_frames"]
    assert mgr.density_min_flights == d["density_min_flights"]
    assert mgr.static_off_frames == d["static_off_frames"]
    assert mgr.group_gap_frames == d["group_gap_frames"]
    assert mgr.point_min_actions == d["point_min_actions"]
    assert mgr.contact_chain_frames == d["contact_chain_frames"]
    assert mgr.fast_confirm_flights == d["fast_confirm_flights"]
    assert mgr.fast_confirm_window_frames == d["fast_confirm_window_frames"]
    assert mgr.serve_action_arms == d["serve_action_arms"]
    assert mgr.enabled == d["enabled"]


# --- serve-init semantics (live ON at the serve) --------------------


def test_provisional_on_before_full_confirmation():
    """The live state turns GAME_ON ~20 flight frames into the serve burst,
    long before the 90f confirmation window closes (owner complaint: ON
    landed ~5s late on entreno_3)."""
    mgr = make_manager()
    frames = [None] * 30 + [10.0] * 40 + [None] * 60
    infos = drive(mgr, frames)
    on_frames = [i for i, inf in enumerate(infos) if inf.current_state == GameState.GAME_ON]
    assert on_frames[0] == 30 + 19  # 20 flight frames in the rolling window
    # it is flagged provisional until the window confirms
    assert infos[on_frames[0]].provisional is True
    # after the confirmation boundary it is a real episode
    late = [i for i, inf in enumerate(infos)
            if inf.current_state == GameState.GAME_ON and not inf.provisional][(-1)]
    assert infos[late].episode_start_frame == 30


def test_provisional_on_retracts_if_burst_dies():
    mgr = make_manager()
    # 35 flight frames then silence: provisional ON shows briefly, then OFF
    frames = [None] * 30 + [10.0] * 35 + [None] * 150
    infos = drive(mgr, frames)
    assert any(inf.provisional for inf in infos)
    assert mgr.get_current_state() == GameState.GAME_OFF
    assert mgr.get_points() == []


def test_serve_action_arms_candidate_without_quiet():
    """A classifier serve action arms instantly -- no quiet/burst gate."""
    mgr = make_manager()
    # continuous flight from frame 0 (burst_quiet == 0 -> no normal arm);
    # a serve action at frame 10 arms the candidate at its contact frame
    frames = [10.0] * 130
    infos = drive(mgr, frames, actions_at={10: [{"action": "serve", "frame_number": 10, "confidence": 0.5}]})
    assert any(inf.current_state == GameState.GAME_ON for inf in infos)
    assert mgr.get_current_state() == GameState.GAME_ON
    assert mgr._episode_start == 10


def test_stale_serve_action_does_not_arm():
    """Serve actions whose contact frame is far in the past (emission lag)
    must not arm a stale candidate."""
    mgr = make_manager()
    frames = [10.0] * 130
    infos = drive(mgr, frames, actions_at={100: [{"action": "serve", "frame_number": 5, "confidence": 0.5}]})
    assert mgr.get_current_state() == GameState.GAME_OFF
