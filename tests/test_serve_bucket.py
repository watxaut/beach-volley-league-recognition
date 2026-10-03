"""Contract tests for ``scripts/probe_serve_bucket.py`` (G3 serve bucket).

Three things are pinned here:

1. **The no-decode / no-seek contract.** The probe answers its questions from
   committed artifacts (the ``--diag-dump`` jsonl, ``pipeline_output.json``,
   ``ground_truth/``), so it must not import ``cv2`` and must not touch
   ``CAP_PROP_POS_FRAMES`` (AGENTS.md §9). The existing
   ``tests/test_vfr_seek_guard.py`` already greps the tree for the seek; this
   adds the ``cv2`` half and checks it by AST, so a ``import cv2`` inside a
   function body is caught too.
2. **The G1 gate numbers**, exactly as ``logs/serve_bucket_report.md`` quotes
   them: 185 accepted / 139 found / dump-base label 85/139 = 0.612 / dump
   serves 7/12 / R0 replay control 79. They are the reproduction of #68 and
   #74, and if the dump or the GT moves, this test is the thing that says so
   before a serve is read.
3. **Determinism + the pre-registered verdict rule.** ``derive()`` is pure over
   the artifacts (two calls must be byte-equal), and the verdict can only say
   ``SEPARATOR FOUND`` when some signal really has zero overlap between the two
   groups -- it cannot be flipped by hand.

The artifact-backed tests skip (never fail) when the dump / GT are absent, so
the suite stays green on a fresh clone.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import probe_serve_bucket as psb  # noqa: E402

PROBE = ROOT / "scripts" / "probe_serve_bucket.py"


# --- 1. the no-decode / no-seek contract -----------------------------------

def _imported_modules(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    return mods


def test_probe_imports_no_cv2():
    assert "cv2" not in _imported_modules(PROBE), (
        "the serve bucket is answerable from the dump alone -- a decode would "
        "make the numbers irreproducible and would violate the no-cv2 contract")


def test_probe_does_not_touch_seek_or_decode():
    src = PROBE.read_text(encoding="utf-8")
    for needle in ("CAP_PROP_POS_FRAMES", "VideoCapture", "CAP_PROP_FRAME_COUNT"):
        assert needle not in src, f"{needle} found in a diagnose-only probe"


def test_probe_does_not_reference_the_held_out_session():
    """The held-out session must not be READ by a match-diagnosis probe.

    Checked over CODE strings only (docstrings excluded -- the module
    docstring names the session precisely to declare it off-limits), so a probe
    cannot be quietly pointed at held-out footage.
    """
    tree = ast.parse(PROBE.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)
    code_strings = [n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and n.value not in docstrings]
    assert code_strings, "no code strings found -- the AST walk is broken"
    for s in code_strings:
        assert "vall_dhebron" not in s, (
            "the 20260928 held-out session must not be read by a "
            "match-diagnosis probe")


def test_probe_does_not_mutate_ground_truth_or_src():
    src = PROBE.read_text(encoding="utf-8")
    assert "ground_truth/" not in src.replace(
        "ground_truth/20260920_match_contacts.json", ""), (
        "the probe may READ the GT and nothing else")


# --- 2/3. the artifact-backed pins -----------------------------------------

def _have_artifacts() -> bool:
    return (Path(psb.REPO) / psb.pt.MATCH_DIAG).exists()


needs_artifacts = pytest.mark.skipif(
    not _have_artifacts(), reason="match --diag-dump artifact not present")


@pytest.fixture(scope="module")
def result():
    if not _have_artifacts():
        pytest.skip("match --diag-dump artifact not present")
    return psb.derive()


@needs_artifacts
def test_g1_gate_reproduces_68_exactly(result):
    assert result["gate"] == "G1_GREEN", result.get("mismatch")
    assert result["g1"] == psb.G1_EXPECT


@needs_artifacts
def test_g1_gate_fails_loudly_on_a_moved_number(monkeypatch):
    """The gate must be able to FAIL: a doctored expectation has to abort the
    probe before any serve row is built, not be silently tolerated."""
    monkeypatch.setitem(psb.G1_EXPECT, "found", 138)
    data, mismatch = psb.g1()
    assert mismatch == {"found": (139, 138)}
    assert psb.derive.__doc__  # probe stays importable


@needs_artifacts
def test_diag_stages_carry_the_same_frames(result):
    diag = Path(psb.REPO) / psb.pt.MATCH_DIAG
    ins = psb.load_diag_stage(str(diag), psb.INPUT_STAGE)
    outs = psb.load_diag_stage(str(diag), psb.OUTPUT_STAGE)
    assert len(ins) == len(outs) == 185
    assert {c["frame"] for c in ins} == {c["frame"] for c in outs}
    # The `accepted` writer drops these two fields; the INPUT stage keeps them.
    # This is the finding that makes every serve-branch input derivable.
    assert all("behind_baseline" in c for c in ins)
    assert all("behind_baseline" not in c for c in outs)


@needs_artifacts
def test_bucket_split(result):
    c = result["bucket"]["counts"]
    assert c["total"] == 25
    assert c["found_and_correct"]["n"] == 7
    assert c["found_and_mislabeled"]["n"] == 5
    assert c["not_found"]["n"] == 13
    assert c["found_and_correct"]["near"] == 7 and c["found_and_correct"]["far"] == 0
    assert c["not_found"]["far"] == 12 and c["not_found"]["near"] == 1
    assert c["mislabeled_confusion"] == {"spike": 3, "dig": 2}


@needs_artifacts
def test_every_found_serve_row_is_fully_derived(result):
    """A found row with a None in a signal the card asks for would be a hole
    in the table; the only permitted Nones are kinematic edge columns."""
    rows = result["bucket"]["rows"]
    found = [r for r in rows if r["group"] != "NOT_FOUND"]
    assert len(found) == 12
    required = ("delta_f", "emitted_touch", "touch_correct", "gt_team",
                "emitted_team", "team_match", "gesture", "near_net",
                "ball_side", "kind", "contact_point_px",
                "taker_feet_world_m", "ball_xy_px", "ball_above_net_px",
                "serve_branch")
    for r in found:
        for key in required:
            assert r[key] is not None, (r["point"], key)
    # ``taker_zone`` is the one permitted None: P18's feet project INTO the
    # off-court margin at the contact frame (x=4.12 m, y=17.15 m -- deepest of
    # the seven correct serves), so ``world_point_to_zone`` returns None. The
    # zone grid is not answerable for that row; the DEPTH that the serve branch
    # actually reads is, and it is present.
    assert [r["point"] for r in found if r["taker_zone"] is None] == [18]


@needs_artifacts
def test_serve_branch_inputs_are_derived_and_reproduce_the_shipped_label(result):
    b = result["bucket"]["branch_agreement"]
    assert b["n_found"] == 12
    assert b["agree"] == 12, (
        "the reduced _decide replay must reproduce 12/12 shipped serve labels, "
        "otherwise the replay is not faithful and the derived inputs are wrong")


@needs_artifacts
def test_touch_number_comes_from_events_not_contacts(result):
    """Regression pin for the silent-zero trap: ``points[].contacts[]`` has no
    ``touch_number``. Every GT serve here is touch 1 and every found one was
    emitted as touch 1, which is only visible via ``points[].events[]``."""
    rows = result["bucket"]["rows"]
    assert all(r["gt_touch"] == 1 for r in rows)
    assert all(r["emitted_touch"] == 1 for r in rows
               if r["group"] != "NOT_FOUND")


@needs_artifacts
def test_not_found_rows_split_into_late_and_never_emitted(result):
    """The completeness half of the bucket is not one phenomenon: 11 of the 13
    never produced a serve emission at all, and 2 emitted one 26-28 f late
    (just outside the +-15 f matching window)."""
    nfk = result["bucket"]["counts"]["not_found_kind"]
    assert nfk["n"] == 13
    assert nfk["serve_emitted_late_outside_tolerance"] == 2
    assert nfk["late_points"] == [(13, 28), (15, 26)]
    assert sorted(nfk["never_emitted_as_serve"]) == \
        [14, 21, 22, 23, 24, 25, 26, 27, 28, 31, 32]
    for r in result["bucket"]["rows"]:
        if r["group"] != "NOT_FOUND":
            continue
        ns = r["nearest_serve_accepted"]
        if ns is None:
            continue
        assert ns["delta_f"] > psb.pt.TOLERANCE_F, r["point"]


@needs_artifacts
def test_lever_reconciliation_reports_the_far_line_discrepancy(result):
    rec = result["reconciliation"]
    assert rec["region_gt_events"] == rec["n68_region_gt"] == 183
    assert rec["base_68_accuracy"] == round(83 / 141, 4)
    assert rec["perfect_25_gain_over_base"] == round(25 / 141, 4)  # +0.177
    # The doc's far line is +0.032, which is neither 12/141 nor 13/141. The
    # probe must SURFACE that, not silently adopt one of the three numbers.
    assert rec["gains"]["far_serves"] == f"12/141 = {round(12 / 141, 4)}"
    assert "0.032" in rec["far_gain_note"]


@needs_artifacts
def test_group_comparison_reports_every_signal_with_an_effect_size(result):
    cmp_ = result["comparison"]
    assert cmp_["n_found_correct"] == 7
    assert cmp_["n_found_mislabeled"] == 5
    for key in psb.NUMERIC_SIGNALS:
        entry = cmp_["numeric"][key]
        if entry["found_correct"] and entry["found_mislabeled"]:
            assert entry["cliffs_delta"] is not None, key
    for key in psb.CATEGORICAL_SIGNALS:
        assert key in cmp_["categorical"], key


@needs_artifacts
def test_verdict_rule_is_the_pre_registered_one(result):
    """``NO SEPARATOR`` here, and it must be derived from the zero-overlap test
    rather than asserted: flip a signal into zero overlap and the rule has to
    change its mind."""
    v = result["verdict"]
    assert v["verdict"] == "NO SEPARATOR"
    assert v["signals"] == []
    assert v["numeric_separators"] == []
    assert v["categorical_separators"] == []
    assert set(v["tried"]) == set(psb.NUMERIC_SIGNALS) | set(psb.CATEGORICAL_SIGNALS)

    cmp_ = dict(result["comparison"])
    cmp_["numeric"] = dict(cmp_["numeric"])
    cmp_["numeric"]["synthetic"] = {
        "found_correct": {"n": 2, "median": 10, "min": 10, "max": 10,
                          "mean": 10.0},
        "found_mislabeled": {"n": 2, "median": 1, "min": 1, "max": 1,
                             "mean": 1.0},
        "cliffs_delta": 1.0, "overlap_span": -8.0, "zero_overlap": True}
    forced = psb.verdict(cmp_, result["bucket"]["counts"],
                         result["bucket"]["branch_agreement"])
    assert forced["verdict"] == "SEPARATOR FOUND"
    assert forced["signals"] == ["synthetic"]


@needs_artifacts
def test_cliffs_delta_definition():
    assert psb.cliffs_delta([2.0], [1.0]) == 1.0
    assert psb.cliffs_delta([1.0], [3.0]) == -1.0
    assert psb.cliffs_delta([2.0], [2.0]) == 0.0
    assert psb.cliffs_delta([], [1.0]) is None
    # Brute force against the definition, sign included.
    for xs, ys, want in (((2.0, 4.0), (1.0, 3.0), 0.5),
                         ((1.0, 3.0), (2.0, 4.0), -0.5),
                         ((5.0, 5.0, 5.0), (1.0, 9.0, 5.0), 0.0)):
        gt = sum(1 for x in xs for y in ys if x > y)
        lt = sum(1 for x in xs for y in ys if x < y)
        assert psb.cliffs_delta(xs, ys) == \
            pytest.approx((gt - lt) / (len(xs) * len(ys))), (xs, ys)
        assert want == pytest.approx((gt - lt) / (len(xs) * len(ys)))


@needs_artifacts
def test_derive_is_deterministic(result):
    again = psb.derive()
    assert json.dumps(again, sort_keys=True, default=str) == \
        json.dumps(result, sort_keys=True, default=str)


@needs_artifacts
def test_rally_start_series_matches_the_resolver_semantics():
    """``gap is None or gap > rally_reset_gap``: the FIRST accepted contact is
    a rally start, and a contact within ``rally_reset_gap`` frames of its
    predecessor is not."""
    series = psb.rally_start_series(
        [{"frame": 100}, {"frame": 400}, {"frame": 480}], gap=90)
    assert series[100] == (True, None)
    assert series[400] == (True, 300)
    assert series[480] == (False, 80)


@needs_artifacts
def test_serve_branch_action_priority_order():
    """Both gestures plus a live ``behind_baseline`` -> ``serve``; otherwise
    the attack/block/dig priority decides, which is the production order."""
    g_bb = dict(gesture="bump_set", touch=1, near_net=False,
                behind_baseline=True, rally_start=True)
    assert psb.serve_branch_action(**g_bb) == "serve"
    assert psb.serve_branch_action(**{**g_bb, "rally_start": False}) == "dig"
    assert psb.serve_branch_action(**{**g_bb, "behind_baseline": False}) == "dig"
    assert psb.serve_branch_action(**{**g_bb, "rally_start": False,
                                      "gesture": "attack"}) == "spike"
    assert psb.serve_branch_action(**{**g_bb, "rally_start": False,
                                      "gesture": "block"}) == "block"
    assert psb.serve_branch_action(**{**g_bb, "behind_baseline": False,
                                      "touch": 2}) == "set"


@needs_artifacts
def test_json_artifact_is_written_and_agrees_with_the_run(tmp_path, result):
    """The artifact is the report's data source, so a round-trip must agree
    with the in-memory run (JSON turns tuples into lists, so compare through
    the same normaliser)."""
    out = tmp_path / "serve_bucket.json"
    assert psb.main(["--json", str(out)]) == 0
    norm = lambda o: json.loads(json.dumps(o, sort_keys=True, default=str))  # noqa: E731
    disk = norm(json.loads(out.read_text(encoding="utf-8")))
    assert disk["g1"] == result["g1"]
    assert disk["bucket"]["counts"] == norm(result["bucket"]["counts"])
    assert disk["comparison"] == norm(result["comparison"])
    assert disk["verdict"]["verdict"] == result["verdict"]["verdict"]
    assert disk["reconciliation"] == norm(result["reconciliation"])