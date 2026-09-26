"""Unit tests for scripts/mine_ball_frames.py pure logic (no video/model)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from mine_ball_frames import (
    CLASSES,
    DEFAULT_CAPS,
    classify_frame,
    exclusion_zone,
    game_on_ranges,
    pick_frames,
)


def _cand(conf, bg="sky", ss=False):
    return {"conf": conf, "bg": bg, "ss": ss, "c": [0, 0], "w": 20, "h": 20}


class TestClassifyFrame:
    def test_blind(self):
        cls, best = classify_frame([])
        assert cls == "blind" and best is None

    def test_suspects_only_is_noise(self):
        cls, best = classify_frame([_cand(0.3, "sand", ss=True)])
        assert cls == "sand_noise" and best is None

    def test_low_sand(self):
        cls, best = classify_frame([_cand(0.2, "sand")])
        assert cls == "low_sand" and best is _cand(0.2, "sand") or best["conf"] == 0.2

    def test_best_non_suspect_wins_over_suspect(self):
        # a high-conf suspect must NOT make the frame a control: the best
        # non-suspect candidate classifies it
        cls, best = classify_frame([_cand(0.9, "sky", ss=True), _cand(0.2, "other")])
        assert cls == "low_other" and best["conf"] == 0.2

    def test_sky_control(self):
        cls, best = classify_frame([_cand(0.85, "sky")])
        assert cls == "sky_control" and best["conf"] == 0.85

    def test_high_conf_non_sky_is_not_mined(self):
        cls, _ = classify_frame([_cand(0.85, "sand")])
        assert cls == "high_other"  # recorded, outside CLASSES

    def test_boundary_conf_040_is_high(self):
        assert classify_frame([_cand(0.4, "sky")])[0] == "sky_control"
        assert classify_frame([_cand(0.399, "sand")])[0] == "low_sand"


class TestPickFrames:
    def test_respects_cap(self):
        rng = __import__("random").Random(0)
        picked = pick_frames(range(100), cap=5, spacing=1, rng=rng)
        assert len(picked) == 5 and picked == sorted(picked)

    def test_respects_spacing(self):
        rng = __import__("random").Random(0)
        picked = pick_frames(range(0, 100, 2), cap=10, spacing=5, rng=rng)
        assert len(picked) == 10
        assert all(b - a >= 5 for a, b in zip(picked, picked[1:]))

    def test_pool_smaller_than_cap(self):
        rng = __import__("random").Random(0)
        assert pick_frames([3, 9], cap=10, spacing=5, rng=rng) == [3, 9]

    def test_deterministic_given_seed(self):
        import random
        pool = list(range(200))
        a = pick_frames(pool, 20, 5, random.Random(7))
        b = pick_frames(pool, 20, 5, random.Random(7))
        assert a == b


class TestGameOnRanges:
    def _write(self, tmp_path, rows):
        p = tmp_path / "gs.csv"
        p.write_text("Frame_Index,Game_State\n" +
                     "".join(f"{f},{s}\n" for f, s in rows))
        return p

    def test_basic_runs(self, tmp_path):
        p = self._write(tmp_path, [
            (0, "game_off"), (1, "game_off"), (2, "game_on"), (3, "game_on"),
            (4, "game_off"), (5, "game_on"), (6, "game_off"),
        ])
        assert game_on_ranges(p) == [(2, 3), (5, 5)]

    def test_trailing_game_on(self, tmp_path):
        p = self._write(tmp_path, [(0, "game_off"), (1, "game_on"), (2, "game_on")])
        assert game_on_ranges(p) == [(1, 2)]

    def test_all_game_on(self, tmp_path):
        p = self._write(tmp_path, [(0, "game_on"), (1, "game_on")])
        assert game_on_ranges(p) == [(0, 1)]


class TestExclusionZone:
    def test_margin_zero_is_exact(self):
        assert exclusion_zone([5, 10], 0) == {5, 10}

    def test_covers_margin_on_both_sides(self):
        assert exclusion_zone([10], 2) == {8, 9, 10, 11, 12}

    def test_empty_frames(self):
        assert exclusion_zone([], 5) == set()

    def test_overlapping_zones_union(self):
        assert exclusion_zone([10, 12], 2) == set(range(8, 15))


class TestRound2CapsContract:
    def test_cap_zero_picks_nothing(self):
        rng = __import__("random").Random(0)
        assert pick_frames(range(100), cap=0, spacing=5, rng=rng) == []

    def test_round2_caps_budget(self):
        # round-2 rebalanced mining: only noise negatives + sky controls
        caps = dict(zip(CLASSES, (0, 0, 0, 200, 150)))
        assert sum(caps.values()) == 350
        assert caps["blind"] == 0 and caps["low_sand"] == 0


class TestDefaultsContract:
    def test_budget_is_500(self):
        assert sum(DEFAULT_CAPS.values()) == 500

    def test_classes_match_caps(self):
        assert set(DEFAULT_CAPS) == {
            "blind", "low_sand", "low_other", "sand_noise", "sky_control"}
