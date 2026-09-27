"""Tests for scripts/map_episodes_to_points.py (open point 22, mechanism 1).

The alignment is diagnostic infrastructure: these tests pin the pure
functions (description expectations, side-letter conversion, burst/starve
scores, the monotone DP) on synthetic cases whose right answer is known by
construction, so the production map on the 20260920 match is interpretable.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from map_episodes_to_points import (
    align,
    burst_score,
    census,
    description_expectation,
    episode_features,
    episodes_from_game_state_csv,
    expected_serve_letter,
    build_point_view,
    is_serve_fault_description,
    link_score,
    starve_score,
)


# ----------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------

def make_gt_points(winners, serve_fault_idx=(), big_idx=(), ace_idx=()):
    """Minimal match-points-v1-shaped points with side switches as asked."""
    points = []
    score = {"A": 0, "B": 0}
    switch_after = set(serve_fault_idx)  # unused placeholder
    for i, w in enumerate(winners, start=1):
        score[w] += 1
        if i in serve_fault_idx:
            desc = "Team X fails serve goes outside bounds"
        elif i in ace_idx:
            desc = "Team A ace"
        elif i in big_idx:
            desc = "big rally, many touches and scores"
        else:
            desc = "Team X spikes and scores"
        points.append({
            "point": i,
            "winner": w,
            "score_after": dict(score),
            "side_switch_after": i in switch_after,
            "description": desc,
        })
    return points


def make_ep(start, end, n_actions=0, mix=None, confirmed=False, serves=()):
    return {
        "start": start,
        "end": end,
        "dur": end - start + 1,
        "n_actions": n_actions,
        "mix": mix or {},
        "confirmed": confirmed,
        "serves": list(serves),
    }


def default_sides(n):
    """No side switches: A near everywhere (matches make_gt_points)."""
    return {k: {"A": "near", "B": "far"} for k in range(1, n + 1)}


# ----------------------------------------------------------------------
# description expectations
# ----------------------------------------------------------------------

class TestDescriptionExpectation:
    def test_ace(self):
        assert description_expectation("Team A ace") == (1, 2, "ace")

    def test_serve_fault_variants(self):
        for d in ("Team B fails serve goes outside bounds",
                  "serve out of bounds",
                  "Team B fails serve against the net.",
                  "Team A serves outside of the court"):
            assert is_serve_fault_description(d), d
            assert description_expectation(d)[2] == "serve_fault", d

    def test_spike_out_is_not_serve_fault(self):
        # the owner's P33 wording must NOT read as a serve fault
        assert not is_serve_fault_description("Team B spikes outside of the court.")

    def test_big_rally(self):
        assert description_expectation("big rally, Team B player soft touches") == (4, 12, "big")
        assert description_expectation("rally, Team B spikes into the net") == (4, 12, "big")

    def test_normal_default(self):
        assert description_expectation("player fails hand set") == (2, 6, "normal")


# ----------------------------------------------------------------------
# side-letter conversion
# ----------------------------------------------------------------------

class TestExpectedServeLetter:
    SIDES = {1: {"A": "near", "B": "far"}, 2: {"A": "far", "B": "near"}}

    def test_near_squad_reads_A(self):
        assert expected_serve_letter("A", self.SIDES, 1) == "A"

    def test_far_squad_reads_B(self):
        assert expected_serve_letter("B", self.SIDES, 1) == "B"

    def test_switched_sides_flip_letter(self):
        # after the switch, squad A is on the FAR half -> emitted B
        assert expected_serve_letter("A", self.SIDES, 2) == "B"
        assert expected_serve_letter("B", self.SIDES, 2) == "A"

    def test_unknown_squad_is_none(self):
        assert expected_serve_letter(None, self.SIDES, 1) is None


# ----------------------------------------------------------------------
# burst / starve / link scores
# ----------------------------------------------------------------------

class TestScores:
    def test_tiny_no_action_episode_is_cheap_burst(self):
        assert burst_score(make_ep(100, 101)) > 0

    def test_action_rich_episode_is_expensive_burst(self):
        assert burst_score(make_ep(100, 400, n_actions=3)) < 0

    def test_no_action_long_episode_is_mild(self):
        assert -1.0 < burst_score(make_ep(100, 250)) <= 1.0

    def test_serve_in_window_blocks_burst(self):
        plain = make_ep(100, 250)
        with_serve = make_ep(100, 250, serves=[{"frame": 95, "team": "A"}])
        assert burst_score(with_serve) < burst_score(plain)
        assert burst_score(with_serve) < 0

    def test_starve_cheaper_for_serve_fault(self):
        assert starve_score("serve out of bounds") > starve_score("big rally and scores")

    def test_link_serve_side_match_beats_mismatch(self):
        ep = make_ep(100, 300, n_actions=3, confirmed=False,
                     serves=[{"frame": 95, "team": "A"}])
        good, _ = link_score(ep, "Team X spikes and scores", "A")
        bad, _ = link_score(ep, "Team X spikes and scores", "B")
        assert good > bad

    def test_link_confirmed_overlap_bonus(self):
        plain = make_ep(100, 300, n_actions=3)
        conf = make_ep(100, 300, n_actions=3, confirmed=True)
        s_plain, _ = link_score(plain, "player fails hand set", None)
        s_conf, _ = link_score(conf, "player fails hand set", None)
        assert s_conf == s_plain + 2.0

    def test_link_size_out_of_range_penalised(self):
        short = make_ep(100, 130, n_actions=0)
        right = make_ep(100, 300, n_actions=3)
        long_ep = make_ep(100, 900, n_actions=9)
        base = "Team X spikes and scores"
        s_short, _ = link_score(short, base, None)
        s_right, _ = link_score(right, base, None)
        s_long, _ = link_score(long_ep, base, None)
        assert s_right > s_short and s_right > s_long


# ----------------------------------------------------------------------
# alignment on synthetic cases
# ----------------------------------------------------------------------

class TestAlign:
    def test_perfect_one_to_one(self):
        points = make_gt_points(["A", "B", "A"])
        serve_teams = {1: None, 2: "B", 3: "A"}
        eps = [
            make_ep(100, 200, n_actions=3, confirmed=True),
            make_ep(300, 380, n_actions=1, confirmed=True,
                    serves=[{"frame": 295, "team": "B"}]),
            make_ep(500, 600, n_actions=2, confirmed=True,
                    serves=[{"frame": 495, "team": "A"}]),
        ]
        recs = align(eps, points, serve_teams, default_sides(3))
        assert [r["point"] for r in recs] == [1, 2, 3]
        assert all(r["role"] == "point" for r in recs)

    def test_bursts_interleaved(self):
        points = make_gt_points(["A", "B"])
        serve_teams = {1: None, 2: "A"}
        eps = [
            make_ep(100, 200, n_actions=3, confirmed=True),          # P1
            make_ep(240, 241),                                        # flicker burst
            make_ep(300, 380, n_actions=1, confirmed=True,
                    serves=[{"frame": 295, "team": "A"}]),           # P2
        ]
        recs = align(eps, points, serve_teams, default_sides(2))
        assert [r["point"] for r in recs] == [1, None, 2]
        assert recs[1]["role"] == "burst"

    def test_starved_point_between_real_points(self):
        points = make_gt_points(["A", "B", "A"])
        serve_teams = {1: None, 2: "B", 3: "A"}
        eps = [
            make_ep(100, 200, n_actions=3, confirmed=True),   # P1
            # P2 starved: no episode at all
            make_ep(500, 600, n_actions=2, confirmed=True,
                    serves=[{"frame": 495, "team": "A"}]),    # P3
        ]
        recs = align(eps, points, serve_teams, default_sides(3))
        assert [r["point"] for r in recs] == [1, 3]
        assert all(r["role"] == "point" for r in recs)

    def test_starve_then_burst_still_ordered(self):
        points = make_gt_points(["A", "B", "A", "B"])
        serve_teams = {1: None, 2: "B", 3: "A", 4: "B"}
        eps = [
            make_ep(100, 200, n_actions=3, confirmed=True),    # P1
            make_ep(260, 261),                                  # burst
            make_ep(500, 600, n_actions=2, confirmed=True,
                    serves=[{"frame": 495, "team": "A"}]),     # P3 (P2 starved)
            make_ep(700, 800, n_actions=1, confirmed=True),    # P4
        ]
        recs = align(eps, points, serve_teams, default_sides(4))
        assert [r["point"] for r in recs] == [1, None, 3, 4]

    def test_side_mismatch_flagged_but_point_taken(self):
        # order forces P2 onto the only remaining episode even though the
        # serve letter disagrees -- the mismatch must be visible in evidence
        points = make_gt_points(["A", "B"])
        serve_teams = {1: None, 2: "B"}
        eps = [
            make_ep(100, 200, n_actions=3, confirmed=True),
            make_ep(300, 380, n_actions=1, confirmed=True,
                    serves=[{"frame": 295, "team": "A"}]),  # expects B (squad B far)
        ]
        recs = align(eps, points, serve_teams, default_sides(2))
        assert recs[1]["point"] == 2
        assert recs[1]["evidence"]["serve_side"] == "MISMATCH"

    def test_split_point_attaches_second_episode(self):
        # P2 splits into two episodes (game_on flicker mid-rally)
        points = make_gt_points(["A", "B"])
        serve_teams = {1: None, 2: "B"}
        eps = [
            make_ep(100, 200, n_actions=3, confirmed=True),   # P1
            make_ep(300, 380, n_actions=1, confirmed=True,
                    serves=[{"frame": 295, "team": "B"}]),    # P2a
            make_ep(390, 470, n_actions=1, confirmed=True),    # P2b (attach)
        ]
        recs = align(eps, points, serve_teams, default_sides(2))
        assert [r["point"] for r in recs] == [1, 2, 2]
        assert recs[2]["role"] == "attach"
        assert recs[2]["evidence"]["attach_gap_frames"] == 9

    def test_attach_refused_across_large_gap(self):
        # a point cannot span inter-point dead time: the third episode sits
        # 319f after the second -- far beyond a mid-rally flicker -- so it
        # must burst rather than glue itself onto P2 (unconfirmed, so burst
        # is legal for it)
        points = make_gt_points(["A", "B"])
        serve_teams = {1: None, 2: "B"}
        eps = [
            make_ep(100, 200, n_actions=3, confirmed=True),   # P1
            make_ep(300, 380, n_actions=1, confirmed=True,
                    serves=[{"frame": 295, "team": "B"}]),    # P2
            make_ep(700, 790, n_actions=1, confirmed=False),   # gap 319f
        ]
        recs = align(eps, points, serve_teams, default_sides(2))
        assert [r["point"] for r in recs] == [1, 2, None]
        assert recs[2]["role"] == "burst"

    def test_attach_gap_measured_from_last_point_episode_not_burst(self):
        # a flicker burst between two episodes of one point must not shrink
        # the attach gap: last POINT episode ends 380, attach candidate
        # starts 540 -> gap 159f > 150 measured from the point episode;
        # measured (wrongly) from the flicker's end (400) it would be 139f
        # and attach.  The candidate is action-less: a legal cheap burst
        # (0.5) vs a clearly bad attach (-3.0), so the two gap readings
        # give different alignments.
        points = make_gt_points(["A", "B"])
        serve_teams = {1: None, 2: "B"}
        eps = [
            make_ep(100, 200, n_actions=3, confirmed=True),   # P1
            make_ep(300, 380, n_actions=1, confirmed=True,
                    serves=[{"frame": 295, "team": "B"}]),    # P2
            make_ep(390, 400),                                 # flicker burst
            make_ep(540, 630, n_actions=0, confirmed=False),   # gap 159f
        ]
        recs = align(eps, points, serve_teams, default_sides(2))
        assert [r["point"] for r in recs] == [1, 2, None, None]
        assert recs[2]["role"] == "burst"
        assert recs[3]["role"] == "burst"

    def test_every_point_consumed_in_order(self):
        # invariant: assigned points are strictly increasing 1..N with gaps
        points = make_gt_points(["A"] * 5)
        serve_teams = {1: None, 2: "A", 3: "A", 4: "A", 5: "A"}
        eps = [
            make_ep(100, 200, n_actions=3, confirmed=True),
            make_ep(240, 245),                                          # burst
            make_ep(300, 400, n_actions=2, confirmed=True),
            make_ep(500, 560, n_actions=2, confirmed=True),            # P4 (P3 starved)
            make_ep(600, 700, n_actions=2, confirmed=True,
                    serves=[{"frame": 595, "team": "A"}]),
        ]
        recs = align(eps, points, serve_teams, default_sides(5))
        assigned = [r["point"] for r in recs if r["point"] is not None]
        assert assigned == sorted(assigned)
        assert len(set(assigned)) == len(assigned)


# ----------------------------------------------------------------------
# point view + census
# ----------------------------------------------------------------------

class TestPointViewAndCensus:
    def _view(self):
        points = make_gt_points(["A", "B", "A"], serve_fault_idx={2})
        serve_teams = {1: None, 2: "A", 3: "A"}
        sides = default_sides(3)
        eps = [
            make_ep(100, 200, n_actions=3, confirmed=True),   # P1
            make_ep(300, 340, n_actions=0, confirmed=False),  # P2 (serve fault)
            make_ep(500, 600, n_actions=2, confirmed=True),   # P3
        ]
        recs = align(eps, points, serve_teams, sides)
        serves_all = [
            {"action": "serve", "frame_number": 95, "team": "A"},   # P1 window
            # P2: serve never emitted (the far-side/late-game_on loss)
            {"action": "serve", "frame_number": 495, "team": "A"},  # P3 window
        ]
        return build_point_view(eps, recs, points, serve_teams, sides, serves_all)

    def test_windows_and_starvation(self):
        view = self._view()
        assert [v["starved"] for v in view] == [False, False, False]
        assert view[0]["window_frames"] == [100 - 60, 200 + 30]
        assert view[1]["window_frames"] == [300 - 60, 340 + 30]

    def test_serve_emission_census(self):
        view = self._view()
        assert len(view[0]["serves_emitted"]) == 1
        assert len(view[1]["serves_emitted"]) == 0   # missing
        assert len(view[2]["serves_emitted"]) == 1

    def test_serve_attributed_to_nearest_point_only(self):
        # a serve sitting in the overlap of two adjacent windows (7f after
        # P1's episode ends, 1f before P2's flicker) must count for exactly
        # one point -- the nearest one -- never both
        points = make_gt_points(["A", "B"])
        serve_teams = {1: None, 2: "B"}
        sides = default_sides(2)
        eps = [
            make_ep(100, 200, n_actions=3, confirmed=True),   # P1
            make_ep(300, 340, n_actions=0, confirmed=False),  # P2
        ]
        recs = align(eps, points, serve_teams, sides)
        serves_all = [{"action": "serve", "frame_number": 301, "team": "B"}]
        view = build_point_view(eps, recs, points, serve_teams, sides, serves_all)
        # ep boundaries: P1 ends 200 (101f away), P2 starts 300 (1f away)
        assert view[0]["serves_emitted"] == []
        assert len(view[1]["serves_emitted"]) == 1

    def test_census_near_side_counts(self):
        c = census(self._view())
        # P2/P3 have squad-A servers on the near half; P1's server is
        # unknown and lands in the unknown_server bucket instead
        assert c["near"]["n_points"] == 2
        assert c["near"]["n_serve_emitted"] == 1
        assert c["near"]["n_serve_missing"] == 1
        assert c["far"] == {"n_points": 0, "n_window": 0, "n_serve_emitted": 0,
                            "n_serve_missing": 0, "n_side_match": 0,
                            "n_side_mismatch": 0, "n_starved_no_window": 0,
                            "points": []}
        assert c["unknown_server"] == [1]

    def test_far_side_letter_flips_after_switch(self):
        points = make_gt_points(["A", "B"])
        points[1]["side_switch_after"] = False
        serve_teams = {1: None, 2: "A"}
        sides = {1: {"A": "near", "B": "far"}, 2: {"A": "far", "B": "near"}}
        eps = [make_ep(100, 200, n_actions=3, confirmed=True),
               make_ep(300, 400, n_actions=2, confirmed=True)]
        recs = align(eps, points, serve_teams, sides)
        serves_all = [{"action": "serve", "frame_number": 95, "team": "A"},
                      {"action": "serve", "frame_number": 295, "team": "B"}]
        view = build_point_view(eps, recs, points, serve_teams, sides, serves_all)
        # point 2: squad A now on the far half -> expected emitted letter B
        assert view[1]["expected_serve_letter"] == "B"
        assert view[1]["serve_side_near_far"] == "far"
        assert view[1]["serve_side_match"] is True
        c = census(view)
        assert c["far"]["n_serve_emitted"] == 1


# ----------------------------------------------------------------------
# loaders (shared with evaluate_match_points)
# ----------------------------------------------------------------------

class TestEpisodesFromCsv:
    def test_reconstructs_spans(self, tmp_path):
        rows = ["Frame_Index,Game_State"]
        rows += [f"{i},game_off" for i in range(10)]
        rows += [f"{i},game_on" for i in range(10, 20)]
        rows += [f"{i},game_off" for i in range(20, 30)]
        rows += [f"{i},game_on" for i in range(30, 35)]
        p = tmp_path / "gs.csv"
        p.write_text("\n".join(rows) + "\n")
        assert episodes_from_game_state_csv(str(p)) == [(10, 19), (30, 34)]


class TestEpisodeFeatures:
    def test_serve_window_capture(self):
        actions = [
            {"action": "serve", "frame_number": 95, "team": "A"},
            {"action": "dig", "frame_number": 150, "team": "B"},
            {"action": "serve", "frame_number": 1000, "team": "B"},
        ]
        feats = episode_features([(100, 200)], actions, [])
        assert len(feats[0]["serves"]) == 1  # serve@95 is near (window), not in-span
        assert feats[0]["serves"][0] == {"frame": 95, "team": "A"}
        assert feats[0]["n_actions"] == 1  # only the in-span dig

    def test_confirmed_overlap(self):
        feats = episode_features([(100, 200)], [], [{"start_frame": 190, "end_frame": 400}])
        assert feats[0]["confirmed"] is True
