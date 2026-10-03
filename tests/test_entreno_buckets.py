"""The entreno failure-bucket classifier, pinned on fixture rows.

``scripts/probe_entreno_buckets.py`` is the diagnose-only probe behind
``logs/entreno_buckets_report.md``: it buckets every GT action event of a drill
as found-correct / found-mislabeled / not-found against the REFERENCE action
stream and tags each failing row with a mechanism (the four known match-side
mechanisms of STATUS #74a/#74b, a new one, or a ceiling).

These tests pin the CLASSIFIER and the MECHANISM TAGGING on hand-built fixture
rows -- deliberately NOT the pipeline F1s, which would need a video run (the
real numbers live in the report's §0/§1 and are re-measured per session).
They also pin that the +-15 f matcher is IMPORTED from the existing machinery
in ``scripts/probe_touch_rules.py`` and never re-implemented here.
"""

import importlib
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

peb = importlib.import_module("probe_entreno_buckets")
pt = importlib.import_module("probe_touch_rules")


def gt_event(frame, action, touch=None, team=None, player_id=1,
             preceded_by_attack=False, note=None):
    """A GT action event shaped like ``ground_truth/video_entreno_N_annotations.json``."""
    return {
        "frame": frame, "player_id": player_id, "final_action": action,
        "player_team": team, "team_in_possession": team,
        "touch_number": touch, "preceded_by_attack": preceded_by_attack,
        "rally_id": 1,
        "overrides": ({"note": note} if note else {}),
    }


def pred_action(frame, action, touch=None, team=None, gesture="bump_set",
                player_id=1):
    """A reference-stream action shaped like ``<stem>_action_log.json``."""
    return {
        "frame": frame, "player_id": player_id, "action": action,
        "gesture": gesture, "confidence": 0.55, "team": team,
        "player_center": [900.0, 500.0], "touch_number": touch, "rally_id": 1,
        "contact_kind": "bounce",
    }


def census(**kw):
    """An all-empty window census, overridable per field."""
    base = {
        "window": [0, 0], "reasons": {}, "candidate_found_n": 0,
        "passed_gates_n": 0, "passed_gates_rows": [], "accepted_n": 0,
        "reach_rejects_n": 0, "reach_rows": [], "ball_track_states": {},
        "ball_sighted_frames": 0, "ball_track_window_frames": 0,
        "ball_sighted_ratio": None,
    }
    base.update(kw)
    return base


class TestMatcherIsImported(unittest.TestCase):
    """The +-15 f matcher comes from probe_touch_rules, not a local copy."""

    def test_tolerance_and_matcher_are_the_existing_ones(self):
        self.assertEqual(peb.pt.TOLERANCE_F, 15)
        self.assertIs(peb.pt, pt)
        self.assertIs(peb.pt.match_contacts, pt.match_contacts)

    def test_default_tolerance_is_the_existing_tolerance(self):
        """The probe must not silently use its own window."""
        import inspect
        sig = inspect.signature(peb.classify_drills)
        self.assertEqual(sig.parameters["tolerance_f"].default, pt.TOLERANCE_F)

    def test_probe_declares_no_seek(self):
        """The VFR seek discipline (AGENTS.md §9) applies to probes too."""
        src = (ROOT / "scripts" / "probe_entreno_buckets.py").read_text()
        for banned in ("CAP_PROP_POS_FRAMES", "cv2.VideoCapture"):
            self.assertNotIn(banned, src)


class TestBucketClassifier(unittest.TestCase):
    """found_correct / found_mislabeled / not_found on fixture rows."""

    def setUp(self):
        self.events = [
            gt_event(100, "dig", 1, "A"),
            gt_event(200, "set", 2, "B"),
            gt_event(400, "freeball", 3, "A"),
        ]
        self.stream = [
            pred_action(100, "dig", 1, "A"),
            pred_action(201, "dig", 2, "B"),      # wrong class, right count
            pred_action(600, "dig", 3, "A"),      # FP: no GT within tolerance
        ]

    def test_buckets(self):
        res = peb.classify_drills(1, self.events, self.stream, [], [], {})
        self.assertEqual(res["counts"],
                         {"found_correct": 1, "found_mislabeled": 1,
                          "not_found": 1})
        rows = {r["gt_frame"]: r for r in res["rows"]}
        self.assertEqual(rows[100]["bucket"], "found_correct")
        self.assertEqual(rows[200]["bucket"], "found_mislabeled")
        self.assertEqual(rows[200]["pred_action"], "dig")
        self.assertEqual(rows[200]["pred_offset_f"], 1)
        self.assertEqual(rows[400]["bucket"], "not_found")

    def test_not_found_reports_nearest_offset(self):
        """A not_found row emits NOTHING: pred_* stays None and the nearest
        emission lives in its own fields (never overloaded onto pred_*)."""
        self.stream = [pred_action(100, "dig", 1, "A")]
        res = peb.classify_drills(1, self.events, self.stream, [], [], {})
        self.assertEqual(res["counts"]["not_found"], 2)
        rows = {r["gt_frame"]: r for r in res["rows"]}
        row = rows[200]
        self.assertIsNone(row["pred_action"])
        self.assertIsNone(row["pred_frame"])
        self.assertEqual(row["nearest_offset_f"], 100)
        self.assertEqual(row["nearest_action"], "dig")
        self.assertEqual(row["nearest_frame"], 100)

    def test_tolerance_boundary(self):
        """+-15 f matches, +-16 f does not."""
        for offset, expected in ((15, "found_correct"), (16, "not_found")):
            with self.subTest(offset=offset):
                res = peb.classify_drills(
                    1, [gt_event(100, "dig", 1, "A")],
                    [pred_action(100 + offset, "dig", 1, "A")], [], [], {})
                self.assertEqual(res["rows"][0]["bucket"], expected)

    def test_fp_side_counts_non_class_consuming_actions(self):
        """An action earns an FP when no GT within tolerance takes its class.

        BOTH wrong-class actions count: the scorer is per-CLASS one-to-one
        (``evaluate.py`` ``_match_action_events``), so a ``dig`` that matched a
        ``set`` GT is still an unconsumed ``dig`` prediction. Non-exclusive
        pairing (#68) can leave ONE emission satisfying several GT events -- a
        genuine ``evaluate.py`` behaviour, pinned here, not smoothed over.
        """
        res = peb.classify_drills(1, self.events, self.stream, [], [], {})
        self.assertEqual(res["fp_actions"], 2)
        fps = {r["pred_frame"]: r for r in res["fp_rows"]}
        self.assertEqual(sorted(fps), [201, 600])
        self.assertEqual(fps[600]["nearest_gt_frame"], 400)
        self.assertFalse(fps[600]["class_matches_nearest"])
        self.assertEqual(fps[201]["nearest_gt_frame"], 200)

    def test_reconcile_invariant_matches_evaluate_accounting(self):
        """Per class: predicted == correct + FP (evaluate.py's tp+fp==n_pred)."""
        res = peb.classify_drills(1, self.events, self.stream, [], [], {})
        for cls, c in res["reconcile"].items():
            self.assertEqual(c["correct"] + c["fp"], c["predicted"], cls)

    def test_totals_match_evaluate_tp_fp_fn(self):
        res = peb.classify_drills(1, self.events, self.stream, [], [], {})
        tp = res["counts"]["found_correct"]
        fn = res["counts"]["found_mislabeled"] + res["counts"]["not_found"]
        fp = res["fp_actions"]
        per_action = pt.clip_action_f1(self.stream, self.events)["per_action"]
        etp = sum(v["true_positives"] for v in per_action.values())
        efn = sum(v["false_negatives"] for v in per_action.values())
        efp = sum(v["false_positives"] for v in per_action.values())
        self.assertEqual((etp, efn, efp), (tp, fn, fp))

    def test_frame_number_adapter(self):
        """pipeline_output.json writes frame_number; the adapter renames it."""
        adapted = peb.adapt_stream([{"frame_number": 42, "action": "dig"}])
        self.assertEqual(adapted[0]["frame"], 42)
        self.assertEqual(peb.adapt_stream([{"frame": 7, "action": "set"}])[0]["frame"], 7)


class TestMechanismTagging(unittest.TestCase):
    """Tagging of each failing bucket, known / new / ceiling."""

    def _row(self, **kw):
        row = {
            "gt_frame": 100, "gt_action": "set", "gt_touch": 2, "gt_team": "A",
            "gt_player_id": 1, "bucket": peb.CLASS_MISLABELED,
            "pred_frame": 100, "pred_action": "dig", "pred_touch": 1,
            "pred_team": "A", "gesture": "bump_set", "gate": census(),
            "gt_note": None, "gt_non_emittable": False, "nearest_offset_f": 0,
        }
        row.update(kw)
        return row

    def test_count_error_is_a_known_mechanism(self):
        """Emitted count != GT count -> the count-keyed _decide branch."""
        tag, why = peb.tag_mechanism(self._row())
        self.assertEqual(tag, "count_error")
        self.assertIn("count", why)

    def test_gesture_miss_is_new_when_count_and_team_are_right(self):
        row = self._row(pred_touch=2)
        tag, _ = peb.tag_mechanism(row)
        self.assertEqual(tag, "new:gesture_miss")
        self.assertNotIn(tag, peb.KNOWN_MECHANISMS)

    def test_attribution_swap_when_only_the_team_is_wrong(self):
        row = self._row(pred_touch=2, pred_team="B")
        tag, why = peb.tag_mechanism(row)
        self.assertEqual(tag, "attribution_swap")
        self.assertIn("wrong team", why)

    def test_emitted_vocabulary_ceiling_for_freeball(self):
        """freeball is not a VolleyballAction member: un-emittable by vocabulary."""
        row = self._row(gt_action="freeball", gt_touch=3, pred_touch=3)
        tag, why = peb.tag_mechanism(row)
        self.assertEqual(tag, "new:emitted_vocabulary")
        self.assertIn("VolleyballAction", why)

    def test_serve_mislabel_is_the_landing_artefact_gate(self):
        """The SERVE branch needs behind_baseline AND rally_start."""
        row = self._row(gt_action="serve", gt_touch=1, pred_touch=1,
                        gate=census(passed_gates_n=1,
                                    passed_gates_rows=[{"behind_baseline": False}]))
        tag, why = peb.tag_mechanism(row)
        self.assertEqual(tag, "landing_artefact")
        self.assertIn("behind_baseline", why)
        self.assertIn("rally_start", why)

    def test_not_found_reach_gate_is_the_contact_layer(self):
        row = self._row(bucket=peb.CLASS_NOT_FOUND, gt_action="dig", gt_touch=1,
                        gate=census(reach_rejects_n=1,
                                    reach_rows=[{"frame": 163, "distance": 182.3,
                                                 "reach": 140.0}],
                                    candidate_found_n=1,
                                    ball_track_states={"tracked": 31}))
        tag, why = peb.tag_mechanism(row)
        self.assertEqual(tag, "new:contact_gate")
        self.assertIn("reach gate", why)
        self.assertIn("182.3", why)

    def test_not_found_ball_loss_reports_the_measured_sight_ratio(self):
        """A 'predicted' coast is not a sighting (BallTracker never hallucinates)."""
        row = self._row(bucket=peb.CLASS_NOT_FOUND, gt_action="dig", gt_touch=1,
                        gate=census(reasons={"no_ball_sighting": 25},
                                    ball_track_states={"tracked": 6, "none": 16,
                                                       "predicted": 9},
                                    ball_sighted_frames=6,
                                    ball_track_window_frames=31))
        tag, why = peb.tag_mechanism(row)
        self.assertEqual(tag, "new:contact_gate")
        self.assertIn("ball sight 6/31 frames", why)

    def test_not_found_reports_sight_ratio_even_when_the_ball_was_seen(self):
        """The sight ratio must NOT be phrased as a loss when the ball was
        actually sighted most of the window (e7 f370) -- only the numbers."""
        row = self._row(bucket=peb.CLASS_NOT_FOUND, gt_action="set", gt_touch=2,
                        gate=census(reasons={"no_contact_geometry": 18},
                                    ball_track_states={"tracked": 18, "none": 5,
                                                       "predicted": 8},
                                    ball_sighted_frames=18,
                                    ball_track_window_frames=31))
        _, why = peb.tag_mechanism(row)
        self.assertIn("ball sight 18/31 frames", why)
        self.assertNotIn("NOT SIGHTED", why)

    def test_gt_non_emittable_block_is_a_ceiling(self):
        row = self._row(bucket=peb.CLASS_NOT_FOUND, gt_action="block",
                        gt_touch=1, gt_non_emittable=True,
                        note="No-touch block (owner 2026-09-08)", gt_note=(
                            "No-touch block (owner 2026-09-08)"))
        tag, why = peb.tag_mechanism(row)
        self.assertEqual(tag, peb.CEILING_TAG)
        self.assertIn("un-emittable", why)

    def test_gt_no_touch_block_signature(self):
        """player_id null + preceded_by_attack + block = owner convention."""
        self.assertTrue(peb.gt_no_touch_block(
            gt_event(300, "block", 1, "B", player_id=None,
                     preceded_by_attack=True)))
        self.assertFalse(peb.gt_no_touch_block(
            gt_event(300, "block", 1, "B", player_id=3,
                     preceded_by_attack=True)))

    def test_path_divergence_when_the_dump_accepts_the_contact(self):
        row = self._row(bucket=peb.CLASS_NOT_FOUND, gt_action="spike",
                        gate=census(accepted_n=1))
        tag, why = peb.tag_mechanism(row)
        self.assertEqual(tag, peb.DIVERGENCE_TAG)
        self.assertIn("divergence", why)

    def test_found_correct_rows_are_never_tagged(self):
        """Only failing rows are bucketed into mechanisms."""
        res = peb.classify_drills(
            1, [gt_event(100, "dig", 1, "A")],
            [pred_action(100, "dig", 1, "A")], [], [], {})
        split = peb.mechanism_split(res)
        self.assertEqual(split["n_failing_events"], 0)
        self.assertIsNone(split["known_pct"])

    def test_split_partitions_known_new_and_ceiling(self):
        res = peb.classify_drills(
            1, [gt_event(100, "set", 2, "A"),
                gt_event(300, "block", 1, "B", player_id=None,
                         preceded_by_attack=True),
                gt_event(500, "dig", 1, "B")],
            [pred_action(100, "dig", 1, "A")], [], [], {})
        split = peb.mechanism_split(res)
        self.assertEqual(split["known_n"] + split["new_n"] + split["ceiling_n"],
                         split["n_failing_events"])
        self.assertEqual(split["by_mechanism"],
                         {"ceiling:gt_non_emittable": 1, "count_error": 1,
                          "new:contact_gate": 1})
        self.assertEqual((split["known_n"], split["new_n"], split["ceiling_n"]),
                         (1, 1, 1))
        self.assertEqual(split["known_pct"], 50.0)
        self.assertEqual(split["known_pct_of_all"], 33.3)


class TestGateCensus(unittest.TestCase):
    """The window census that grounds the not-found tags."""

    def test_counts_per_stage_and_reasons(self):
        cands = [
            {"stage": "rejected", "reason": "no_contact_geometry", "frame": 10},
            {"stage": "rejected", "reason": "no_contact_geometry", "frame": 11},
            {"stage": "rejected", "reason": "reach", "frame": 12,
             "distance": 179.4, "reach": 140.0, "target_team": "B"},
            {"stage": "candidate_found", "frame": 13},
            {"stage": "candidate_passed_gates", "frame": 14,
             "behind_baseline": True},
        ]
        track = {f: ("tracked" if f % 2 else "none") for f in range(5, 26)}
        c = peb.window_census(cands, track, 10, w=5)
        self.assertEqual(c["reasons"], {"no_contact_geometry": 2, "reach": 1})
        self.assertEqual(c["reach_rejects_n"], 1)
        self.assertEqual(c["candidate_found_n"], 1)
        self.assertEqual(c["passed_gates_n"], 1)
        self.assertTrue(c["passed_gates_rows"][0]["behind_baseline"])
        self.assertEqual(c["ball_track_window_frames"], 11)
        self.assertEqual(c["ball_sighted_frames"], 6)

    def test_only_tracked_state_counts_as_sighted(self):
        """A 'predicted' coast must not be counted as a sighting."""
        track = {10: "tracked", 11: "predicted", 12: "none", 13: "none"}
        c = peb.window_census([], track, 11, w=1)
        self.assertEqual(c["ball_sighted_frames"], 1)
        self.assertEqual(c["ball_track_window_frames"], 3)
        self.assertEqual(c["ball_sighted_ratio"], 0.33)


class TestEvidenceShape(unittest.TestCase):
    """Evidence columns for mislabels: no silent inference of missing fields."""

    def test_behind_baseline_absent_on_accepted_rows_is_none(self):
        ev = peb._evidence([{"frame": 114, "action": "dig", "touch_number": 3,
                             "team": "A", "kind": "bounce"}], 114, 15)
        self.assertIsNone(ev["behind_baseline"])
        self.assertEqual(ev["touch_number"], 3)
        self.assertEqual(ev["kind_staleness"], "bounce")
        self.assertTrue(ev["within_tolerance"])

    def test_evidence_absent_when_no_dump_row(self):
        self.assertEqual(peb._evidence([], 100, 15), {"source": None})


if __name__ == "__main__":
    unittest.main()