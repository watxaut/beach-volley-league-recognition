"""SR0: one serve scorer, per side, dev vs held-out (open point 30).

The scorer exists because every serve number in this project was measured by a
different script with a different scope, so what is pinned here is the
MEASUREMENT, not a mechanism:

* one matching rule (greedy one-to-one, nearest first, inside the owner
  contact's own tolerance) and one FP rule -- a stream that does not CLAIM a
  serve per candidate (raw evidence records, the rally onset) reports no
  precision at all, because "precision 1.000 on 14 rally onsets" and "74 false
  serves" are both fiction;
* **coverage and binding are different numbers.**  A record that sits on the
  serve but was bound to the WRONG point is a binding miss: the evidence layer
  is 13/17 by coverage and 9/17 by binding, and only the second number is what
  a consumer got;
* side accuracy is measured against the POSITIONAL match.  Under side-aware
  matching it is trivially 1.00, which would hide every wrong-side emission;
* the SR3 serve-only GT format parses through an INJECTED timebase, because on
  the VFR match a wall-clock timestamp must go through PTS and never a seek
  (AGENTS.md §9).

The numbers themselves are reproduced against the real artifacts by running
``venv/bin/python scripts/score_serves.py`` (``output/`` is git-ignored, so the
gate is a script run and not a test).
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "score_serves", ROOT / "scripts" / "score_serves.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


S = _load()


def gt_blob(points, events=(), fps=25.67, video="resources/full_videos/match.mp4"):
    """A contact-GT blob in the MATCH dialect (owner_side + match_frame)."""
    return {
        "video": video,
        "fps": fps,
        "points": [{"point": p, "match_start_frame": f, "match_end_frame": f + 200}
                   for p, f in points],
        "annotated_frames": {"actions": {"events": [
            {"point": p, "match_frame": f, "action": act, "owner_side": side,
             "player_team": squad, "frame_tolerance": 15}
            for p, f, act, side, squad in events]}},
    }


def events_of(blob):
    return blob["annotated_frames"]["actions"]["events"]


def rows(frames, side="near", squad="A", split="all", tolerance=15,
         point_of=None):
    return [{"frame": f, "point": (point_of or (lambda i: i))(f), "side": side,
             "squad": squad, "side_source": "owner_side", "tolerance": tolerance,
             "split": split} for f in frames]


class TestGtRows:
    def test_match_dialect_carries_side_squad_split_and_tolerance(self):
        blob = gt_blob([(1, 210), (9, 5496)], events=[
            (1, 210, "serve", "far", "B"),
            (9, 5496, "serve", "near", "B"),
            (9, 5530, "dig", "near", "B"),
        ])
        out = S.serve_rows_from_contact_gt(blob, split_of=S.match_split)
        assert [r["frame"] for r in out] == [210, 5496], "only serves"
        assert out[0]["side"] == "far" and out[0]["squad"] == "B"
        assert out[0]["split"] == "dev" and out[1]["split"] == "held_out"
        assert out[0]["tolerance"] == 15
        assert out[0]["side_source"] == "owner_side"

    def test_squad_only_gt_uses_the_session_side_mapping(self):
        """The entreno dialect carries no owner_side; A played near there."""
        blob = {"video": "v", "fps": 30.0,
                "annotated_frames": {"actions": {"events": [
                    {"frame": 29, "final_action": "serve", "player_team": "A"},
                    {"frame": 60, "final_action": "dig", "player_team": "A"}]}}}
        out = S.serve_rows_from_contact_gt(
            blob, squad_to_side=S.entreno_squad_to_side)
        assert len(out) == 1
        assert out[0]["side"] == "near"
        assert out[0]["side_source"] == "squad (side mapping)"

    def test_sr3_serve_only_format(self):
        text = ("# mm:ss.s near|far [server] [outcome]\n"
                "12:34.5 near P2 ace\n"
                "bad line without a side\n"
                "13:02.0 far\n"
                "\n")
        out = S.parse_serve_gt_text(text, timebase=lambda s: int(s * 2),
                                    point_of=lambda f: f // 1000)
        assert [(r["frame"], r["side"], r["split"]) for r in out] == [
            (1509, "near", "new"), (1564, "far", "new")]
        assert out[0]["note"] == "P2 ace"

    def test_sr3_timebase_is_injected_not_guessed(self):
        """VFR: the seconds->frame conversion is the caller's, never a seek."""
        seen = []

        def timebase(seconds):
            seen.append(seconds)
            return 42

        S.parse_serve_gt_text("01:00.0 far\n", timebase=timebase)
        assert seen == [60.0]


class TestMatching:
    def test_one_to_one_nearest_first(self):
        """Two emissions near one serve: the closest wins, the echo is an FP."""
        gt = rows([100])
        cands = [{"frame": 108, "side": "near", "squad": None, "point": 1},
                 {"frame": 97, "side": "near", "squad": None, "point": 1}]
        m = S.match_candidates(gt, cands)
        assert len(m["matched"]) == 1
        assert m["matched"][0]["delta_f"] == -3, "97 is nearer than 108"
        assert m["unmatched_candidates"] == [0], "the +8 echo stays unmatched"

    def test_tolerance_is_per_row(self):
        gt = rows([100], tolerance=5) + rows([200], tolerance=15)
        cands = [{"frame": 108, "side": "near", "squad": None, "point": 1},
                 {"frame": 210, "side": "near", "squad": None, "point": 2}]
        m = S.match_candidates(gt, cands)
        assert [e["delta_f"] for e in m["matched"]] == [10]

    def test_side_aware_matching_refuses_a_wrong_side_emission(self):
        gt = rows([100], side="far", squad="B")
        cands = [{"frame": 100, "side": "near", "squad": "A", "point": 1}]
        assert S.match_candidates(gt, cands)["matched"] == []
        positional = S.match_candidates(gt, cands, require_side=False)
        assert len(positional["matched"]) == 1
        assert positional["matched"][0]["side_ok"] is False

    def test_point_bound_matching_is_binding_not_coverage(self):
        """A record ON the serve but bound to another point is a binding miss."""
        gt = rows([100], side="far", squad="B")
        cands = [{"frame": 100, "side": "far", "squad": None, "point": 9}]
        assert S.match_candidates(gt, cands, point_bound=True)["matched"] == []
        assert len(S.match_candidates(gt, cands, point_bound=False)["matched"]) == 1


class TestFalsePositiveKinds:
    def test_three_kinds(self):
        gt_contacts = [{"frame": 245, "action": "dig", "owner_side": "near"},
                       {"frame": 880, "action": "serve", "owner_side": "far"}]
        cands = [{"frame": 1000, "side": "near", "squad": None, "point": None},
                 {"frame": 245, "side": "near", "squad": None, "point": None},
                 {"frame": 890, "side": "far", "squad": None, "point": None}]
        out = S.classify_false_positives(cands, [0, 1, 2], gt_contacts)
        assert [r["kind"] for r in out] == ["dead_time_handling",
                                            "rally_contact_mislabeled",
                                            "serve_outside_tolerance"]
        assert out[1]["nearest_contact"]["action"] == "dig"


class TestStreams:
    def test_production_reads_emitted_serve_actions_with_a_side_letter(self):
        pipeline = {"actions": [
            {"action": "serve", "frame_number": 100, "team": "A"},
            {"action": "dig", "frame_number": 120, "team": "A"},
            {"action": "serve", "frame_number": 300, "team": "B"}]}
        out = S.production_candidates(pipeline)
        assert [(c["frame"], c["side"]) for c in out] == [(100, "near"), (300, "far")]

    def test_pass2_side_comes_from_the_emitted_letter_not_the_gt_derived_squad(self):
        """pass2_team is winner-serves-derived; using it as the side would be circular."""
        relabel = {"actions_pass2": [
            {"frame_number": 100, "action": "dig", "pass2_action": "serve",
             "team": "A", "pass2_team": "B"},
            {"frame_number": 200, "action": "serve", "pass2_action": "serve",
             "team": "B", "pass2_team": "A", "pass2_demoted": True}]}
        out = S.pass2_candidates(relabel)
        assert len(out) == 1, "demoted serves are dropped"
        assert out[0]["side"] == "near" and out[0]["squad"] == "B"

    def test_game_on_reads_the_backdated_burst_start(self):
        pipeline = {"game_state": {"point_count": 2, "points": [
            {"start_frame": 216, "end_frame": 495, "n_actions": 5},
            {"start_frame": 1376, "end_frame": 1600, "n_actions": 4}]}}
        assert [c["frame"] for c in S.game_on_candidates(pipeline)] == [216, 1376]

    def test_evidence_coverage_and_binding_are_separate_streams(self):
        evidence = {"records": [{"frame": 81, "sources": ["conjunction"]}],
                    "points": [{"point": 1, "serve_evidence": {"frame": 223,
                                                             "sources": ["structural"]}}]}
        coverage = S.evidence_record_candidates(evidence)
        assert [(c["frame"], c["side"], c["point"]) for c in coverage] == [(81, "far", None)]
        bound = S.evidence_bound_candidates(evidence)
        assert [(c["frame"], c["point"]) for c in bound] == [(223, 1)]

    def test_serve_records_stream_reads_the_sr4_artifact(self):
        blob = {"records": [{"t_contact_frame": 500, "side": "near",
                             "squad": "A", "point": 3, "outcome": "received"}]}
        assert S.serve_record_candidates(blob)[0]["frame"] == 500


def score(gt, stream, switches=(), contacts=None):
    near_served = {r["point"]: r["squad"] for r in gt}
    return S.score_stream(stream, gt, contacts or [], list(switches), near_served)


class TestScoring:
    def test_per_side_recall_precision_and_fp_per_point(self):
        gt = (rows([100], side="near", squad="A", point_of=lambda f: 1)
              + rows([200], side="far", squad="B", point_of=lambda f: 2))
        stream = {"name": "production", "proposes_serve": True, "side_aware": True,
                  "candidates": [{"frame": 100, "side": "near", "squad": None, "point": 1},
                                 {"frame": 700, "side": "near", "squad": None, "point": 1}]}
        out = score(gt, stream)
        assert out["by_side"]["near"]["hits"] == 1
        assert out["by_side"]["near"]["recall"] == 1.0
        assert out["by_side"]["near"]["false_positives"] == 1
        assert out["by_side"]["near"]["fp_per_point"] == 0.5, "1 FP over 2 points"
        assert out["by_side"]["far"]["hits"] == 0
        assert out["by_side"]["far"]["precision"] is None, "nothing emitted"

    def test_a_proposal_stream_reports_no_precision(self):
        gt = rows([100], point_of=lambda f: 1)
        stream = {"name": "serve_evidence", "proposes_serve": False,
                  "side_aware": True,
                  "candidates": [{"frame": 100, "side": "near", "squad": None,
                                  "point": None},
                                 {"frame": 500, "side": "near", "squad": None,
                                  "point": None}]}
        out = score(gt, stream)
        assert out["overall"]["precision"] is None
        assert out["overall"]["false_positives"] is None
        assert out["unmatched_total"] == 1, "the unmatched count is still visible"

    def test_side_accuracy_is_measured_positionally_not_tautologically(self):
        """A stream that emits on the wrong side must not score side 1.00."""
        gt = (rows([100], side="far", squad="B", point_of=lambda f: 1)
              + rows([200], side="near", squad="A", point_of=lambda f: 2))
        stream = {"name": "production", "proposes_serve": True, "side_aware": True,
                  "candidates": [{"frame": 100, "side": "near", "squad": None, "point": 1}]}
        out = score(gt, stream)
        assert out["by_side"]["far"]["hits"] == 0, "wrong side is not a far hit"
        assert out["by_side"]["far"]["side_accuracy"] == 0.0
        assert out["positional_hits"] == 1
        assert out["positional_hits_wrong_side"] == 1

    def test_squad_accuracy_maps_a_side_letter_through_the_switch_parity(self):
        """P9 is after the P7 switch, so squad A is FAR there."""
        switches = [7]
        gt = rows([100], side="far", squad="A", point_of=lambda f: 9)
        stream = {"name": "production", "proposes_serve": True, "side_aware": True,
                  "candidates": [{"frame": 100, "side": "far", "squad": None, "point": 9}]}
        near_served = {9: "B"}          # parity: A started near, so B is near at P9
        out = S.score_stream(stream, gt, [], switches, near_served)
        assert out["by_side"]["far"]["squad_accuracy"] == 1.0

    def test_held_out_column_exists_for_an_in_sample_stream(self):
        """The in-sample flag must travel with the number, not replace it."""
        gt = (rows([100], side="far", split="dev", point_of=lambda f: 1)
              + rows([200], side="far", split="held_out", point_of=lambda f: 9))
        stream = {"name": "serve_evidence", "in_sample": True,
                  "proposes_serve": False, "side_aware": True,
                  "candidates": [{"frame": 100, "side": "far", "squad": None,
                                  "point": None}]}
        out = score(gt, stream)
        assert out["in_sample"] is True
        assert out["by_split"]["dev"]["hits"] == 1
        assert out["by_split"]["held_out"]["hits"] == 0

    def test_per_serve_rows_carry_the_nearest_candidate_on_a_miss(self):
        gt = rows([100], point_of=lambda f: 1)
        stream = {"name": "production", "proposes_serve": True,
                  "candidates": [{"frame": 140, "side": "near", "squad": None,
                                  "point": 1}]}
        out = score(gt, stream)
        row = out["per_serve"][0]
        assert row["hit"] is False
        assert row["nearest_candidate_delta_f"] == 40


class TestGate:
    def test_the_gate_is_pre_registered_on_the_match_production_stream(self):
        assert S.GATE == {"session": "match_20260920", "stream": "production",
                          "near": (8, 16), "far": (0, 17), "false_positives": 12}

    def test_gate_passes_on_a_report_that_reproduces_the_baseline(self):
        report = {"sessions": {"match_20260920": {"streams": {"production": {
            "by_side": {"near": {"hits": 8, "gt_serves": 16},
                        "far": {"hits": 0, "gt_serves": 17}},
            "overall": {"false_positives": 12}}}}}}
        gate = S.gate_check(report)
        assert gate["pass"] is True
        assert gate["checks"] == {"near": True, "far": True, "false_positives": True}

    def test_gate_fails_loudly_when_a_number_moves(self):
        report = {"sessions": {"match_20260920": {"streams": {"production": {
            "by_side": {"near": {"hits": 9, "gt_serves": 16},
                        "far": {"hits": 0, "gt_serves": 17}},
            "overall": {"false_positives": 11}}}}}}
        gate = S.gate_check(report)
        assert gate["pass"] is False
        assert gate["checks"] == {"near": False, "far": True,
                                   "false_positives": False}


class TestSessionBuilders:
    def test_match_session_declares_every_stream_with_its_vocabulary(self):
        session = S.build_match_session()
        names = {s["name"] for s in session["streams"]}
        assert {"production", "pass2", "game_on", "serve_evidence",
                "serve_evidence_bound"} <= names
        bound = next(s for s in session["streams"]
                     if s["name"] == "serve_evidence_bound")
        assert bound["point_bound"] is True, "binding is a point claim"
        assert next(s for s in session["streams"]
                    if s["name"] == "serve_evidence")["proposes_serve"] is False
        assert next(s for s in session["streams"]
                    if s["name"] == "game_on")["proposes_serve"] is False

    def test_switches_come_from_the_cadence_not_gt(self):
        assert S.rs.derive_switches(list(range(1, 34))) == [7, 14, 21, 28]

    def test_entreno_session_maps_the_squad_letter_to_a_side(self):
        session = S.build_entreno_session(3)
        assert session["squad_to_side"]("A") == "near"
        assert session["split_of"](1) == "dev", "entreno is dev by definition"

    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6, 7])
    def test_every_entreno_session_has_a_gt_path_that_exists(self, n):
        assert (ROOT / S.build_entreno_session(n)["gt"]).exists()

    def test_a_fresh_practice_run_beats_the_stale_artifact(self, tmp_path, monkeypatch):
        """SR0 measured that `output/video_entreno_*` predates the v3 detector
        (09-26) and the pose gates (09-27), so a run under `output/sr1/` wins."""
        monkeypatch.setattr(S, "REPO", tmp_path)
        (tmp_path / "output" / "video_entreno_2").mkdir(parents=True)
        (tmp_path / "output" / "video_entreno_2" / "pipeline_output.json").write_text("{}")
        assert S.session_pipeline_path(2).startswith("output/video_entreno_2")
        (tmp_path / "output" / "sr1" / "entreno_2").mkdir(parents=True)
        (tmp_path / "output" / "sr1" / "entreno_2" / "pipeline_output.json").write_text("{}")
        assert S.session_pipeline_path(2) == "output/sr1/entreno_2/pipeline_output.json"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))