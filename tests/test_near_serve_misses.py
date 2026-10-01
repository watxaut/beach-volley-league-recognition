"""SR1: the near-serve miss taxonomy (open point 30, task SR1).

Diagnose-only, so what is pinned here is the TAXONOMY, not a mechanism.  The
distinctions that matter are the ones a wrong fix would collapse:

* a contact INSIDE the tolerance with another action (``label``) is a different
  failure from a contact 29 f away (``off_tolerance``), and a different one again
  from having only an OTHER-SIDE contact nearby (``other_side_contact``) --
  attribution and labelling are not the same bug;
* the serve label needs BOTH ``behind_baseline`` and ``rally_start``
  (``ActionContextResolver._decide``), so a label miss is always one of those
  two, with completely different fixes.  ``rally_start`` is inferred from the
  gap to the previous emitted contact, ``behind_baseline`` is MEASURED from the
  diag dump when one is given -- and the two are never conflated;
* the fresh practice runs must win over the stale ones in ``output/video_entreno_*``
  (SR0 found those artifacts predate the v3 detector and the pose gates).

The real numbers are reproduced by running
``venv/bin/python scripts/probe_near_serve_misses.py`` (``output/`` is
git-ignored, so the taxonomy over real artifacts is a script run, not a test).
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "probe_near_serve_misses", ROOT / "scripts" / "probe_near_serve_misses.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


S = _load()


def gt(frame=100, side="near", point=1, tolerance=15):
    return {"frame": frame, "side": side, "point": point, "squad": "A",
            "split": "held_out", "tolerance": tolerance}


def action(frame, act="dig", side="near", **extra):
    return {"frame_number": frame, "action": act, "side": side,
            "gesture": extra.get("gesture", "bump_set"),
            "contact_kind": extra.get("contact_kind", "bounce"),
            "touch_number": extra.get("touch_number", 1),
            "rally_id": extra.get("rally_id", 1), "team": side[0].upper()}


class TestBuckets:
    def test_a_hit_is_not_a_miss(self):
        out = S.classify_miss(gt(), [action(100, "serve")], {})
        assert out["bucket"] == "hit"

    def test_label_bucket_when_a_contact_is_emitted_with_another_action(self):
        out = S.classify_miss(gt(), [action(100, "dig")], {})
        assert out["bucket"] == "label"
        assert out["contacts_in_tolerance"][0]["action"] == "dig"

    def test_off_tolerance_when_the_contact_is_outside_the_window(self):
        out = S.classify_miss(gt(), [action(129, "dig")], {})
        assert out["bucket"] == "off_tolerance"
        assert out["first_contact"]["delta_f"] == 29

    def test_other_side_contact_is_not_off_tolerance(self):
        """A near serve with only a far-side contact nearby is an attribution
        failure, and bucketing it as 'off_tolerance' would send the fix to the
        timing/placement machinery."""
        out = S.classify_miss(gt(), [action(129, "dig", side="far")], {})
        assert out["bucket"] == "other_side_contact"
        assert out["nearest_other_side_contact"]["side"] == "far"

    def test_no_contact_when_nothing_is_near(self):
        assert S.classify_miss(gt(), [action(700)], {})["bucket"] == "no_contact"

    def test_the_tolerance_is_the_owner_frames_own(self):
        wide = gt(tolerance=40)
        out = S.classify_miss(wide, [action(129, "dig")], {})
        assert out["bucket"] == "label", "a 29 f offset is inside a 40 f tolerance"


class TestServeGate:
    def test_rally_start_is_inferred_from_the_gap_to_the_previous_contact(self):
        gate = S.serve_gate_evidence(1000, [action(400), action(1000)])
        assert gate["gap_to_prev_contact_f"] == 600
        assert gate["rally_start_inferred"] is True
        assert gate["behind_baseline_measured"] is None
        assert gate["verdict"] == "behind_baseline_false", "one condition left"

    def test_a_short_gap_means_rally_start_false(self):
        gate = S.serve_gate_evidence(1000, [action(984), action(1000)])
        assert gate["gap_to_prev_contact_f"] == 16
        assert gate["rally_start_inferred"] is False
        assert gate["verdict"] == "rally_start_false"

    def test_behind_baseline_is_measured_from_the_diag_dump(self):
        dump = {1000: {"candidates": [
            {"frame": 1000, "stage": "candidate_passed_gates",
             "behind_baseline": False, "near_net": True}]}}
        gate = S.serve_gate_evidence(1000, [action(1000)], dump)
        assert gate["behind_baseline_measured"] is False
        assert gate["verdict"] == "behind_baseline_false"

    def test_both_conditions_met_and_still_no_serve_is_flagged_as_a_bug(self):
        dump = {1000: {"candidates": [
            {"frame": 1000, "stage": "candidate_passed_gates",
             "behind_baseline": True}]}}
        gate = S.serve_gate_evidence(1000, [action(1000)], dump)
        assert gate["verdict"] == "both_conditions_met_but_no_serve_LABEL_BUG"

    def test_first_contact_has_no_predecessor_so_rally_start_holds(self):
        gate = S.serve_gate_evidence(1000, [action(1000)])
        assert gate["gap_to_prev_contact_f"] is None
        assert gate["rally_start_inferred"] is True


class TestPass2Context:
    def test_owner_false_serve_emissions_are_surfaced_not_consumed(self):
        actions = [action(1000, "dig"), action(840, "serve")]
        pass2 = {840: {"pass2_action": "serve", "pass2_demoted": True,
                       "pass2_source": "owner_verdict"}}
        out = S.classify_miss(gt(frame=1000), actions, pass2)
        assert out["owner_false_serve_nearby"][0]["frame"] == 840
        assert out["bucket"] == "label", "the demotion does not change the bucket"

    def test_a_pass2_relabel_is_context_only(self):
        actions = [action(100, "dig")]
        pass2 = {100: {"pass2_action": "serve", "pass2_source": "relabeled"}}
        out = S.classify_miss(gt(), actions, pass2)
        assert out["pass2_changed_nearby"][0]["pass2_action"] == "serve"
        assert out["bucket"] == "label", "SR1 scores production, not pass-2"


class TestPrefixParity:
    def test_identical_prefix_is_reported_as_identical(self):
        actions = [{"frame_number": 10, "action": "dig", "team": "A"}]
        out = S.prefix_parity(actions, actions, 4000)
        assert out["identical"] is True
        assert out["actions_in_prefix"] == 1

    def test_a_gesture_flip_is_reported_not_hidden(self):
        run = [{"frame_number": 10, "action": "dig", "team": "A"}]
        ref = [{"frame_number": 10, "action": "serve", "team": "A"}]
        out = S.prefix_parity(run, ref, 4000)
        assert out["identical"] is False
        assert out["only_in_run"] == [(10, "dig", "A")]

    def test_actions_beyond_the_prefix_are_ignored(self):
        run = [{"frame_number": 10, "action": "dig", "team": "A"},
               {"frame_number": 9000, "action": "spike", "team": "B"}]
        ref = [{"frame_number": 10, "action": "dig", "team": "A"}]
        assert S.prefix_parity(run, ref, 4000)["identical"] is True


class TestSessionArtifacts:
    def test_the_fresh_practice_run_wins_over_the_stale_artifact(self):
        """SR0 measured the `output/video_entreno_*` artifacts at 2026-09-04/06,
        before the v3 detector and the pose gates."""
        import inspect

        source = inspect.getsource(S.session_artifacts)
        assert source.index("output/sr1/entreno_") < source.index("output/video_entreno_")

    def test_the_match_session_reads_the_shipped_run_and_its_pass2(self):
        artifacts = S.session_artifacts({"key": "match_20260920"})
        assert artifacts["pipeline"] is not None
        assert artifacts["relabel"] is not None

    def test_a_missing_diag_dump_yields_no_stage_rather_than_a_guess(self):
        assert S.diag_stage(gt(), "output/sr1/does_not_exist.jsonl") is None
        assert S.load_diag_frames("output/sr1/does_not_exist.jsonl") is None


class TestScoring:
    def _session(self):
        return {"key": "unit",
                "gt": str(Path("ground_truth/video_entreno_3_annotations.json")),
                "split_of": S.ss.entreno_split,
                "squad_to_side": S.ss.entreno_squad_to_side,
                "label": "unit"}

    def test_hits_are_excluded_and_misses_are_counted(self):
        blob = {"actions": [{"frame_number": 29, "action": "serve", "team": "A"}]}
        original = S.session_artifacts
        S.session_artifacts = lambda _session: {"pipeline": blob, "relabel": None}
        try:
            out = S.score_session(self._session())
        finally:
            S.session_artifacts = original
        assert out["gt_serves"] == 1 and out["hits"] == 1 and out["missed"] == 0

    def test_a_missed_practice_serve_lands_in_a_bucket(self):
        blob = {"actions": [{"frame_number": 29, "action": "dig", "team": "A",
                             "gesture": "bump_set", "touch_number": 1}]}
        original = S.session_artifacts
        S.session_artifacts = lambda _session: {"pipeline": blob, "relabel": None}
        try:
            out = S.score_session(self._session())
        finally:
            S.session_artifacts = original
        assert out["buckets"] == {"label": 1}
        assert out["serve_gate_verdicts"] == {"behind_baseline_false": 1}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))