"""Contract tests for ``scripts/probe_insert_path.py`` (INSERT-path diagnosis).

The probe answers one question from committed artifacts -- if a serve record is
INSERTED per point window, keyed the PG2 way, how many of the 17 far serves
gain a record within +-15 f of the GT contact, at what false-serve cost, and
does the arm reach the goal math? -- and four things are pinned here:

1. **The no-decode / no-seek contract.** No ``cv2`` (checked by AST, so an
   import inside a function body is caught too) and no ``CAP_PROP_POS_FRAMES``
   (AGENTS.md section 9; ``tests/test_vfr_seek_guard.py`` greps the tree, this
   adds the cv2 half and the held-out-session half).
2. **The G1 gate numbers**, exactly as the card lists them: evidence 87 records /
   pipeline 31 points / GT 33 points, 17 far + 16 near serves / 185 accepted /
   139 found / dump-base 85 correct / 211 GT contacts.  They must reproduce
   before any serve is read, and the gate must be able to FAIL.
3. **The two PG2 consistency anchors.** ``far_hits`` at anchor_tol 15 must be
   PG2's in-sample 11/17 (``docs/point_map_seam.md``) and the seam split must be
   11 at_seam / 0 inside_window / 6 in_gap.  A deviation means this probe and
   PG2 stopped describing the same placements, and the card says STOP.
4. **Determinism, the both-conventions goal translation, and the two bugs this
   continuation had to fix** (the control-section precision that read 0.0 next
   to ``far_hits 11``, and the double-counted ``unanchored_claims``).

Artifact-backed tests skip (never fail) when the artifacts are absent, so the
suite stays green on a fresh clone.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import probe_insert_path as pip  # noqa: E402

PROBE = ROOT / "scripts" / "probe_insert_path.py"

#: PG2's ``docs/point_map_seam.md`` section 4 table, IN-SAMPLE.
PG2_SEAM_FAR = {"n": 17, "at_seam": 11, "inside_window": 0, "in_gap": 6}
PG2_FAR_HITS_IN_SAMPLE = 11


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
        "the insert path is answerable from the committed artifacts -- a decode "
        "would make the numbers irreproducible and would violate the no-cv2 "
        "contract")


def test_probe_does_not_touch_seek_or_decode():
    src = PROBE.read_text(encoding="utf-8")
    for needle in ("CAP_PROP_POS_FRAMES", "VideoCapture", "CAP_PROP_FRAME_COUNT"):
        assert needle not in src, f"{needle} found in a diagnose-only probe"


def test_probe_does_not_reference_the_held_out_session():
    """The held-out session must not be READ by a match-diagnosis probe.

    Checked over CODE strings only (docstrings excluded -- the module docstring
    names the session precisely to declare it off-limits), so a probe cannot be
    quietly pointed at held-out footage.
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
        "the probe may READ the match GT and nothing else")


def test_probe_never_writes_outside_output():
    """The card allows writing ``output/insert_path/probe.json`` and nothing
    else: the module's only write is the ``--json`` dump, and it must not copy,
    remove or rewrite anything."""
    src = PROBE.read_text(encoding="utf-8")
    for needle in (".write_bytes(", "shutil.copy", "os.remove", "os.rename",
                   "open(", "unlink"):
        assert needle not in src, f"{needle} found -- diagnosis must not mutate"
    writes = [ln for ln in src.splitlines() if ".write_text(" in ln]
    assert len(writes) == 1 and writes[0].lstrip().startswith("p.write_text("), \
        f"unexpected writes: {writes}"


# --- 2/3/4. the artifact-backed pins --------------------------------------

def _have_artifacts() -> bool:
    return all((Path(pip.REPO) / p).exists()
               for p in (pip.MATCH_PIPELINE, pip.MATCH_GT, pip.MATCH_EVIDENCE,
                         pip.MATCH_DIAG))


needs_artifacts = pytest.mark.skipif(
    not _have_artifacts(), reason="match artifacts (pipeline/GT/evidence/diag) absent")


@pytest.fixture(scope="module")
def result():
    if not _have_artifacts():
        pytest.skip("match artifacts absent")
    return pip.derive()


@pytest.fixture(scope="module")
def headline(result):
    return result["variants"][result["headline"]]


# --- G1 --------------------------------------------------------------------

@needs_artifacts
def test_g1_gate_reproduces_the_card_exactly(result):
    assert result["gate"] == "G1_GREEN", result.get("mismatch")
    g = result["g1"]
    assert g["ok"] is True and g["mismatch"] == {}
    for key, want in pip.G1_EXPECT.items():
        assert g[key] == want, f"{key} moved: {g[key]} != {want}"
    assert g["dev_far"] == 5
    assert g["held_far"] == 12


@needs_artifacts
def test_g1_gate_fails_loudly_on_a_moved_number(monkeypatch):
    """The gate must be able to FAIL: a doctored expectation has to abort
    before any serve row is built, not be silently tolerated."""
    monkeypatch.setitem(pip.G1_EXPECT, "found", 138)
    gates = pip.g1()
    assert gates["ok"] is False
    assert gates["mismatch"] == {"found": (139, 138)}
    assert pip.derive() == {"gate": "G1_FAILED", "g1": gates}
    assert "G1 GATE FAILED" in pip.format_report(pip.derive())
    assert pip.main([]) == 2


@needs_artifacts
def test_g1_tolerances_are_one_value_across_the_house(result):
    """The +-15 f window is a house constant: a probe that quietly widened it
    would move every hit count in this report."""
    assert pip.TOL == pip.S.DEFAULT_TOLERANCE == 15
    assert pip.A.TOLERANCE == pip.PT.TOLERANCE_F == pip.TOL
    assert pip.WIDTH_CUT == pip.P.WIDTH_CUT == 28
    assert result["inputs"]["hit_tolerance"] == 15
    assert result["inputs"]["anchor_tols"][0] == 15


# --- the placement rule ----------------------------------------------------

@needs_artifacts
def test_one_claim_per_window_start_and_one_placement_each(headline):
    """The unit of the arm is the WINDOW START: 31 pipeline points, so at most
    31 claims and one placement per claim, however many candidates the pool
    attaches to a start."""
    assert headline["claims_total"] == 31
    assert headline["claims_placed"] == 18
    assert headline["claims_ambiguous"] == 4
    assert headline["claims_with_empty_pool"] == 13
    assert headline["claims_placed"] + headline["claims_with_empty_pool"] == 31
    # one PLACEMENT per claim, and each claim has its own start
    starts = [r for r in headline["claim_score"]["matched_detail"]]
    assert len({d["anchor_start"] for d in starts}) == len(starts)
    cands = pip.placed_claims(
        pip.build_claims(pip.P.pipeline_points(pip.P._read(pip.MATCH_PIPELINE)),
                         pip.candidate_pool(pip.P._read(pip.MATCH_PIPELINE),
                                            pip.P._read(pip.MATCH_EVIDENCE)), 15))
    placed = [c["frame"] for c in cands]
    assert len(placed) == len(set(placed)) == 18, "a claim was placed twice"
    assert len({c["anchor_start"] for c in cands}) == 18


@needs_artifacts
def test_claim_building_is_deterministic_and_gt_free(result):
    """``build_claims`` takes (points, pool, anchor_tol) -- there is no argument
    through which a GT frame could reach the rule, and two calls agree."""
    import inspect

    params = set(inspect.signature(pip.build_claims).parameters)
    assert params == {"points", "pool", "anchor_tol", "refuse_on_tie"}

    pool = pip.candidate_pool(pip.P._read(pip.MATCH_PIPELINE),
                              pip.P._read(pip.MATCH_EVIDENCE))
    points = pip.P.pipeline_points(pip.P._read(pip.MATCH_PIPELINE))
    a = json.dumps(pip.build_claims(points, pool, 15), sort_keys=True, default=str)
    b = json.dumps(pip.build_claims(points, list(pool), 15), sort_keys=True,
                   default=str)
    assert a == b
    # the tie-break is deterministic too: the same tie set always yields the
    # same winner, and the tie SIZE is recorded rather than hidden
    claims = pip.build_claims(points, pool, 15)
    ties = [c for c in claims if c["tie_size"] > 1]
    assert len(ties) == result["variants"][result["headline"]]["claims_ambiguous"] == 4
    for c in ties:
        assert c["placed_frame"] == min(
            c["tied_frames"], key=lambda f: (abs(f - c["start"]), f))


@needs_artifacts
def test_refuse_on_tie_only_removes_placements(result):
    """The strict consumer emits nothing on an ambiguous start: 18 placements
    minus the 4 tied ones, and the tied ones cost 4 of the 11 hits."""
    strict = result["variants"]["refuse_on_tie_tol_15"]
    head = result["variants"][result["headline"]]
    assert strict["claims_placed"] == head["claims_placed"] - 4 == 14
    assert strict["claims_ambiguous"] == head["claims_ambiguous"] == 4
    assert strict["serve_score"]["all"]["hits"] == 7
    tied_points = {r["point"] for r in head["serve_table"] if r["ambiguous"]}
    assert tied_points == {14, 22, 23, 28}
    assert set(head["serve_score"]["all"]["points_hit"]) - \
        set(strict["serve_score"]["all"]["points_hit"]) == tied_points


@needs_artifacts
def test_pool_is_narrow_flight_plus_evidence_records(result):
    inp = result["inputs"]
    assert inp["pool_ff"] == 432        # PG1/PG2's narrow far_flight onsets
    assert inp["pool_evidence"] == 87   # every serve_evidence.json record
    assert inp["pool_size"] == 432 + 87
    # the leak the continuation found: the pool claimed the narrow cut but took
    # far_flight_events unfiltered, so the 29-77 px band rode along
    assert inp["pool_dropped_wide"] == 20
    assert inp["pool_size_width_filtered"] == inp["pool_size"] - 20


# --- anchor 3: the two PG2 consistency anchors ----------------------------

@needs_artifacts
def test_far_hits_equals_pg2_in_sample_11_of_17(result, headline):
    """The card's STOP condition, part 1: PG2 (``docs/point_map_seam.md``)
    scored 11 of the 17 IN-SAMPLE far serves off the window starts.  This probe
    places on the same starts with the same narrow pool, so it must reproduce
    11 -- and it must reproduce WHICH 11."""
    score = headline["serve_score"]
    assert score["all"]["n"] == 17
    assert score["all"]["hits"] == PG2_FAR_HITS_IN_SAMPLE
    assert headline["claim_score"]["splits"]["all"]["far_hit_points"] == \
        [1, 6, 14, 15, 21, 22, 23, 25, 26, 27, 28]


@needs_artifacts
def test_seam_split_equals_pg2(result):
    """The card's STOP condition, part 2: far 11 at_seam / 0 inside_window /
    6 in_gap, near 3 / 11 / 2."""
    far = result["seam_split"]["far"]
    for key, want in PG2_SEAM_FAR.items():
        assert far[key] == want, f"seam split moved: {key}={far[key]} != {want}"
    near = result["seam_split"]["near"]
    assert (near["n"], near["at_seam"], near["inside_window"], near["in_gap"]) \
        == (16, 3, 11, 2)


@needs_artifacts
def test_every_miss_is_an_in_gap_serve(headline):
    """The unreachable serves' common property, and the reason the decision rule
    asks for: a far serve sitting BETWEEN two windows has no start to hang a
    claim on, so no anchor tolerance can reach it."""
    misses = [r for r in headline["serve_table"] if not r["hit"]]
    assert len(misses) == 6
    assert sorted(r["point"] for r in misses) == [2, 4, 8, 13, 31, 32]
    assert {r["seam_kind"] for r in misses} == {"in_gap"}
    # all 11 at_seam serves are hits: the seam split and the hit count are the
    # same fact seen twice
    hits = [r for r in headline["serve_table"] if r["hit"]]
    assert {r["seam_kind"] for r in hits} == {"at_seam"}
    assert all(r["miss_kind"] == "wrong_place" for r in misses), (
        "an in-gap miss is a placement that exists but is anchored to the wrong"
        " window -- not a missing record and not an ambiguity")


# --- anchor 4a: the control section (the bug this continuation fixed) -----

@needs_artifacts
def test_control_section_precision_is_the_placements_ratio(headline):
    """The regression pin for the bug: the control section reported
    ``within +-15 f of a GT serve 0 / precision 0.0`` next to ``far_hits 11``.

    Root cause: ``score_serves.classify_false_positives`` was run over EVERY
    placement and its rows were then filtered to drop the serve kinds -- a
    matched claim arrives with ``kind`` None, so the filter removed the true
    positives as well, and the correct-serve count was read off the emptied
    list.  The taxonomy was never wrong; it was applied to the wrong
    population.  Match FIRST, classify the unmatched second (the order
    ``score_serves`` itself uses)."""
    c = headline["control"]
    assert c["precision_convention"] == pip.PRECISION_CONVENTION
    assert c["placements"] == headline["claims_placed"]
    assert c["placements_within_tol_of_a_gt_serve"] == \
        headline["serve_score"]["all"]["hits"] == 11
    assert c["precision_on_placements"] == pytest.approx(11 / c["placements"],
                                                        abs=5e-5)
    # the FP buckets are disjoint and add up to every non-correct placement
    fp = (c["non_serve_misclaims"] + c["dead_time_handling"]
          + c["serve_claims_late_outside_tolerance"])
    assert fp == c["placements"] - c["placements_within_tol_of_a_gt_serve"]


@needs_artifacts
def test_fp_side_is_rally_contacts_plus_dead_time(headline):
    """The card's control question: the cost is rally-contact misclaims and
    dead-time placements, NOT near serves."""
    c = headline["control"]
    assert c["non_serve_misclaims"] == 3
    assert c["dead_time_handling"] == 1
    assert headline["claim_score"]["near_misclaims_total"] == 0
    assert headline["claim_score"]["outside_tolerance_total"] == 0
    assert c["n_windows_without_gt_serve"] == 0
    assert c["dead_time_search_f"] == pip.S.DEAD_TIME_SEARCH_F == 80
    # every rally misclaim names a non-serve owner contact
    for row in c["per_claim"]:
        if row["kind"] == "rally_contact_mislabeled":
            assert pip.S._action_of(row["nearest_contact"]) != pip.SERVE


@needs_artifacts
def test_owner_negative_side_is_a_lower_bound(headline):
    """#54's 0.90 precision was computed over the owner's own FALSE/OFFGAME
    moments.  The rule can only place at window STARTS, and four of the nine
    owner negatives sit mid-window where no start is in reach, so zero FP here
    is a floor, not a clean sheet."""
    c = headline["control"]
    assert c["owner_negative_windows_total"] == 9
    assert c["owner_fp_placements"] == 0
    assert c["owner_precision"] == 1.0


@needs_artifacts
def test_unanchored_claims_counts_placements_not_taxonomy_rows(headline):
    """The second regression pin: ``sum(len(u) for u in unmatched)`` summed a
    FLAT row list, so it reported the taxonomy's row count (42) instead of the
    number of placements that matched no serve (7)."""
    cs = headline["claim_score"]
    assert cs["unanchored_claims"] == \
        cs["placements"] - cs["splits"]["all"]["claims_scored_against_a_serve"]
    assert cs["unanchored_claims"] == 7
    assert len(cs["unanchored_frames"]) == 7
    # PG2's own unanchored anchors were 4790/8573/11662/24644/25776; the
    # unfiltered headline adds the two late NEAR-side serve claims at 1375/6015
    assert set(cs["unanchored_frames"]) == {1375, 4796, 6015, 8583, 11665,
                                            24648, 25775}


@needs_artifacts
def test_width_cut_moves_only_the_fp_side(result):
    """The diagnostic is registered as one: far_hits (and WHICH points) are
    invariant to the width cut, so the cut is not a lever on the goal math."""
    sweep = result["width_sweep"]
    assert {row["far_hits"] for row in sweep} == {11}
    assert {tuple(row["far_hit_points"]) for row in sweep} == \
        {(1, 6, 14, 15, 21, 22, 23, 25, 26, 27, 28)}
    assert sweep[0]["width_cut"] == pip.WIDTH_CUT == 28
    tight, loose = sweep[0], [r for r in sweep if r["width_cut"] is None][0]
    assert (tight["unanchored_placements"], tight["dead_time_handling"]) \
        == (5, 0)
    assert (loose["unanchored_placements"], loose["dead_time_handling"]) \
        == (7, 1)
    assert tight["precision_on_placements"] > loose["precision_on_placements"]


# --- anchor 4b: the both-conventions goal translation ----------------------

@needs_artifacts
def test_goal_translation_reports_both_conventions(result):
    """(a) insert-into-denominator (139+k) is the consistent convention and the
    verdict's: the inserted serves were NOT-FOUND, so they belong in the
    denominator.  (b) #74b's literal 139 is numerator-only and overstates."""
    goal = result["goal"]
    for arm in ("all_17_IN_SAMPLE", "dev_only", "held_out_only"):
        g = goal[arm]
        a, b = g["a_insert_into_denominator"], g["b_literal_139_denominator"]
        # (a): numerator 85+k, denominator 139+k
        assert a["numerator"] == 85 + g["inserted"]
        assert a["denominator"] == 139 + g["inserted"]
        assert a["accuracy"] == pytest.approx(a["numerator"] / a["denominator"],
                                             abs=5e-5)
        # (b): same numerator, denominator held at 139 -> strictly larger
        assert b["numerator"] == a["numerator"]
        assert b["denominator"] == 139
        assert b["accuracy"] == pytest.approx(b["numerator"] / 139, abs=5e-5)
        assert b["accuracy"] >= a["accuracy"]
        assert "OVERSTATES" in b["note"]
        assert "verdict" in a["note"]


@needs_artifacts
def test_goal_translation_numbers(result):
    """The coordinator's measured figures, pinned.  Both conventions stay under
    the 0.70 bar, and the label-only ceiling is #74b's own 90/139."""
    goal = result["goal"]
    all17 = goal["all_17_IN_SAMPLE"]
    assert all17["inserted"] == 11
    assert (all17["a_insert_into_denominator"]["numerator"],
            all17["a_insert_into_denominator"]["denominator"]) == (96, 150)
    assert all17["a_insert_into_denominator"]["accuracy"] == 0.64
    assert all17["a_insert_into_denominator"]["over_bar"] is False

    ho = goal["held_out_only"]
    assert ho["inserted"] == 9
    assert (ho["a_insert_into_denominator"]["numerator"],
            ho["a_insert_into_denominator"]["denominator"]) == (94, 148)
    assert ho["a_insert_into_denominator"]["accuracy"] == 0.6351

    dev = goal["dev_only"]
    assert dev["inserted"] == 2
    assert (dev["a_insert_into_denominator"]["numerator"],
            dev["a_insert_into_denominator"]["denominator"]) == (87, 141)

    ceiling = goal["label_only_ceiling_74b"]
    assert (ceiling["correct"], ceiling["denominator"]) == (90, 139)
    assert ceiling["accuracy"] == 0.6475

    assert pip.BAR == 0.70 and pip.GOAL_CORRECT == 103 and pip.GOAL_N == 139


@needs_artifacts
def test_goal_arithmetic_cannot_be_met_by_an_insert_only_arm(result):
    """Both conventions prove it independently: under (a) reaching 103 correct
    needs 18 insertions and only 17 far serves exist; under (b) clearing 0.70
    needs 13 insertions (5 mislabeled + 12 not-found), which also exceeds 17
    only after the 5 mislabeled are counted, and the INSERT path may not
    relabel."""
    all17 = result["goal"]["all_17_IN_SAMPLE"]
    assert all17["goal_hits_needed_convention_a"] == 18 > 17
    assert all17["hits_needed_for_74b_literal_to_clear_bar"] == 13
    assert all17["unreachable_serves"] == 6
    assert result["goal"]["all_17_IN_SAMPLE"]["base_accuracy"] == \
        round(85 / 139, 4)


def test_goal_translation_is_pure_arithmetic_and_needs_no_artifacts():
    """Both conventions must be checkable without the match artifacts."""
    g = pip.goal_translation(85, 139, 0)
    assert g["a_insert_into_denominator"]["accuracy"] == round(85 / 139, 4)
    assert g["b_literal_139_denominator"]["accuracy"] == round(85 / 139, 4)
    assert g["inserted"] == 0 and g["unreachable_serves"] == 17
    g17 = pip.goal_translation(85, 139, 17)
    assert g17["a_insert_into_denominator"]["denominator"] == 156
    assert g17["b_literal_139_denominator"]["denominator"] == 139
    assert g17["a_insert_into_denominator"]["accuracy"] < \
        g17["b_literal_139_denominator"]["accuracy"]


# --- determinism and the artifact round trip ------------------------------

@needs_artifacts
def test_derive_is_deterministic(result):
    again = pip.derive()
    assert json.dumps(again, sort_keys=True, default=str) == \
        json.dumps(result, sort_keys=True, default=str)


@needs_artifacts
def test_json_artifact_is_written_and_agrees_with_the_run(tmp_path, result):
    """The artifact is the report's data source, so a round trip must agree with
    the in-memory run (JSON turns tuples into lists, so compare through the same
    normaliser)."""
    out = tmp_path / "insert_path.json"
    assert pip.main(["--json", str(out)]) == 0
    norm = lambda o: json.loads(json.dumps(o, sort_keys=True, default=str))  # noqa: E731
    disk = norm(json.loads(out.read_text(encoding="utf-8")))
    assert disk["g1"] == norm(result["g1"])
    assert disk["inputs"] == norm(result["inputs"])
    assert disk["seam_split"] == norm(result["seam_split"])
    assert disk["width_sweep"] == norm(result["width_sweep"])
    assert disk["goal"] == norm(result["goal"])
    head = disk["variants"][disk["headline"]]
    assert head["serve_score"] == norm(result["variants"][result["headline"]]["serve_score"])
    assert head["control"] == norm(result["variants"][result["headline"]]["control"])


@needs_artifacts
def test_every_inserted_serve_is_genuinely_not_found(result):
    """Convention (a) charges each insertion +1 in the denominator because the
    serve was NOT-FOUND, not mislabeled.  Measured against the dump's 185
    accepted contacts: none of the 11 hit serves has an accepted emission
    within +-15 f (the nearest is 23-84 f LATE), so no insertion here would
    double-count an existing emission -- and the 5 mislabeled far/near
    corrections inside #74b's 103 are NOT reachable by an insert-only arm."""
    head = result["variants"][result["headline"]]
    hits = head["claim_score"]["splits"]["all"]["far_hit_points"]
    assert len(hits) == PG2_FAR_HITS_IN_SAMPLE
    diag = Path(pip.REPO) / pip.MATCH_DIAG
    accepted = [int(c["frame"]) for c in
                pip.B.load_diag_stage(str(diag), pip.B.INPUT_STAGE)]
    assert len(accepted) == pip.G1_EXPECT["accepted"]
    gt = pip.P._read(pip.MATCH_GT)
    rows = {int(r["point"]): int(r["frame"])
            for r in pip.P.gt_serve_rows(gt) if r["side"] == "far"}
    for point in hits:
        nearest = min(abs(f - rows[point]) for f in accepted)
        assert nearest > pip.TOL, (
            f"P{point} already has an accepted emission {nearest} f away -- an "
            f"insertion here would be a DUPLICATE, not a new correct action")


@needs_artifacts
def test_report_states_the_precision_convention_and_the_verdict_numbers(result):
    """The printed report is what the owner reads: it must carry the
    convention, both goal conventions, and the unreachable count."""
    text = pip.format_report(result)
    assert pip.PRECISION_CONVENTION in text
    assert "0.6111" in text and "0.6875" in text
    for needle in ("96/150", "94/148", "87/141", "90", "139"):
        assert needle in text, needle
    assert "GATE G1 GREEN" in text
    assert "all_17_IN_SAMPLE" in text and "held_out_only" in text
    assert "OVERSTATES" in text
    assert "in_gap" in text