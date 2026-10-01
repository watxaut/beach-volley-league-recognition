"""The structural far-serve rule (M3') -- gate, reach and net-crossing mechanics.

Diagnosed in session 53 (``docs/g4_structural_serve.md``): a far serve is
recoverable WITHOUT the tracker and WITHOUT the contact-geometry shape tests,
because the detector already sees the far ball (15-21 px, 14-31 of 31 frames at
the serve) and a serve is a *structural* event -- it opens a rally, it happens
next to a person at the far line, and the ball is on the far side at that moment.

The rule lives in ``scripts/sweep_structural_serve.py`` while it is being
validated (the refuted-mechanism rule keeps mechanisms out of ``src/`` until
they earn their place). These tests pin the three pieces that carry the
precision, so the mechanism cannot be re-tuned into a false-positive machine
without a test failing:

* the OPENER GAP -- a rally opens after >=143 f of emitted-contact silence
  (measured on the match: openers >= 153 f, largest mid-rally gap 134 f), and
  every mid-rally far-side ball must be rejected;
* the REACH -- the ball must be within N bbox heights of an occupant in the far
  band, which is what separates a serve from a ball being carried in hands
  elsewhere on the far side;
* the NET CROSSING -- a served ball crosses the net line toward the camera, and
  the serve is the LAST candidate before it.
"""

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "sweep_structural_serve", ROOT / "scripts" / "sweep_structural_serve.py")
_sweep = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_sweep)

Replay, fire = _sweep.Replay, _sweep.fire
BALL_W_MIN, BALL_W_MAX = _sweep.BALL_W_MIN, _sweep.BALL_W_MAX

# Image-space anchors on the beach calibration (far line y~591, net line
# y~641-645, far-side court x 714..1277 at the baseline).
RUNWAY_FOOT = (995.0, 575.0)        # behind the far line  -> region "runway"
COURT_FOOT = (995.0, 600.0)         # just inside the line -> region "court"
BALL_FAR = (995.0, 470.0)           # airborne, far side of the net line
BALL_FAR_HIGH = (995.0, 300.0)      # high lob, still the far side


def recording(frames, actions=()):
    """``frames``: {frame: (balls, people)}; balls = [(cx, cy, w, conf)]."""
    per_frame = {}
    for frame, (balls, people) in frames.items():
        per_frame[frame] = {
            "ball": [[*b] for b in balls],
            "ball_track": None,
            "people": [list(p) for p in people],
            "game": "game_off",
        }
    return {"per_frame": per_frame,
            "actions": [{"frame": f, "seen_at": f} for f in actions],
            "events": []}


def runway_occupant(cx=995.0, foot=RUNWAY_FOOT, h=110.0, w=60.0, conf=0.6):
    return [cx, foot[1], w, h, conf, "runway" if foot[1] < 591 else "court"]


RULE = {
    "gap": 143, "occupant_regions": ("runway", "court"), "occupant_lookback": 15,
    "ball_lookback": 30, "ball_w_min": BALL_W_MIN, "ball_w_max": BALL_W_MAX,
    "reach": 1.0, "motion": "none", "motion_span": 15, "motion_px": 0.0,
    "bias": 0, "max_late": 30, "net_gate": False, "net_span": 120,
}


class OpenerGapTest(unittest.TestCase):
    def test_fires_after_a_long_dead_time(self):
        rec = recording({1000: ([(*BALL_FAR, 16, 0.6)], [runway_occupant()])},
                        actions=[800])
        self.assertIsNotNone(fire(Replay(rec), 1000, RULE))
        # 1000 - 800 = 200 > 143.
        self.assertEqual(1000, fire(Replay(rec), 1000, RULE))

    def test_rejects_a_mid_rally_ball(self):
        rec = recording({1000: ([(*BALL_FAR, 16, 0.6)], [runway_occupant()])},
                        actions=[950])
        self.assertIsNone(fire(Replay(rec), 1000, RULE))  # gap 50 <= 143

    def test_gap_boundary_is_inclusive_of_the_measured_chasm(self):
        """134 f is the largest real mid-rally gap, 153 f the smallest opener."""
        for last, expected in ((1000 - 134, False), (1000 - 153, True)):
            rec = recording({1000: ([(*BALL_FAR, 16, 0.6)], [runway_occupant()])},
                            actions=[last])
            self.assertEqual(expected, fire(Replay(rec), 1000, RULE) is not None,
                             f"gap {1000 - last}")

    def test_no_prior_action_counts_as_an_opener(self):
        rec = recording({1000: ([(*BALL_FAR, 16, 0.6)], [runway_occupant()])})
        self.assertIsNotNone(fire(Replay(rec), 1000, RULE))


class ReachTest(unittest.TestCase):
    def test_ball_far_from_any_occupant_is_rejected(self):
        # A ball high over the middle of the far court, nobody near it: this is
        # the shape of a far-side RECEIVER's ball, not a serve.
        rec = recording({1000: ([(*BALL_FAR_HIGH, 18, 0.7)], [runway_occupant()])})
        self.assertIsNone(fire(Replay(rec), 1000, RULE))

    def test_wider_reach_accepts_it(self):
        rec = recording({1000: ([(*BALL_FAR_HIGH, 18, 0.7)], [runway_occupant()])})
        loose = dict(RULE, reach=4.0)
        self.assertIsNotNone(fire(Replay(rec), 1000, loose))

    def test_ball_size_gate_rejects_the_venue_noise(self):
        """Sand/lines fire the detector at ~2 det/frame; 3 px is not a ball."""
        rec = recording({1000: ([(995.0, 500.0, 3, 0.4)], [runway_occupant()])})
        self.assertIsNone(fire(Replay(rec), 1000, RULE))

    def test_occupant_region_choice_matters(self):
        rec = recording({1000: ([(*BALL_FAR, 16, 0.6)], [runway_occupant()])})
        strict = dict(RULE, occupant_regions=("runway",))
        court_only = dict(RULE, occupant_regions=("court",))
        self.assertIsNotNone(fire(Replay(rec), 1000, strict))
        # A server standing exactly ON the far line classifies as "court": the
        # measured reason the band has to straddle the line (17/17 vs 7/17).
        rec_court = recording({1000: ([(*BALL_FAR, 16, 0.6)],
                                      [runway_occupant(foot=COURT_FOOT)])})
        self.assertIsNone(fire(Replay(rec_court), 1000, strict))
        self.assertIsNotNone(fire(Replay(rec_court), 1000, court_only))


class NetCrossingTest(unittest.TestCase):
    def _flight(self, cross_at=1004):
        """A ball descending toward the camera, crossing the net line at ``cross_at``."""
        slope = (650.0 - 470.0) / (cross_at - 995)
        frames = {}
        for f in range(990, 1020):
            cy = 470.0 + (f - 995) * slope
            frames[f] = ([(995.0, cy, 16, 0.7)], [runway_occupant()])
        return recording(frames)

    def test_finds_the_crossing(self):
        crossing = Replay(self._flight()).net_crossing(1000, 40)
        self.assertIsNotNone(crossing)
        self.assertGreaterEqual(crossing, 1004)

    def test_no_crossing_when_the_ball_stays_far(self):
        frames = {f: ([(995.0, 470 + f * 0.5, 16, 0.7)], [runway_occupant()])
                  for f in range(980, 1030)}
        self.assertIsNone(Replay(recording(frames)).net_crossing(1000, 40))

    def test_net_gate_keeps_only_candidates_before_the_crossing(self):
        rec = self._flight(cross_at=1004)
        rule = dict(RULE, net_gate=True, net_span=40, max_late=60)
        got = fire(Replay(rec), 1000, rule)
        self.assertIsNotNone(got)
        self.assertLessEqual(got, 1004)


class OwnerNegativesInTheRecordingTest(unittest.TestCase):
    """The real judge: the rule on the owner's FALSE / OFFGAME moments."""

    def test_parses_the_owner_negative_set(self):
        negatives = _sweep.load_owner_negatives()
        self.assertEqual(9, len(negatives))
        self.assertTrue(any("range" in n for n in negatives), "OFFGAME ranges")
        self.assertTrue(all(0 <= n["frame"] <= 26061 for n in negatives))

    def test_positive_set_is_the_17_gt_far_serves(self):
        positives = _sweep.load_positives()
        self.assertEqual(17, len(positives))
        self.assertEqual(5, sum(1 for p in positives if not p["held_out"]))
        self.assertEqual(12, sum(1 for p in positives if p["held_out"]))


if __name__ == "__main__":
    unittest.main()
