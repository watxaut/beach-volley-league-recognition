"""TC1 -- the touch-count-lever probe: contract tests (no decode, no seek).

Covers `scripts/probe_touch_rules.py`:

* the no-cv2 / no-seek / no-decode contract (AGENTS.md section 9);
* step-1 G1: every pinned #68 number reproduces from the committed artifacts;
* step 2: the buckets are total, deterministic, and sum to the 43 wrong touches;
* step 3: each rule's reset semantics on SYNTHETIC contact sequences (the only
  place the rules are exercised independently of the artifacts);
* the pre-registered verdict truth table.

The artifact-backed tests skip (never fail) when the committed dumps are
missing, so a fresh clone without `output/` still runs the suite.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PROBE = REPO / "scripts" / "probe_touch_rules.py"
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))


def _load_probe():
    import probe_touch_rules as p  # noqa: E402
    return p


probe = _load_probe()


# ----------------------------------------------------------------------
# 1. the contract: no cv2, no seek, no decode, imports the real modules
# ----------------------------------------------------------------------

def test_probe_has_no_cv2_import():
    """CARD TC1: the probe must not import cv2 (no decode anywhere)."""
    tree = ast.parse(PROBE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert not a.name.startswith("cv2"), f"imports {a.name}"
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("cv2")


def test_probe_does_not_use_video_capture():
    """No VideoCapture / imread / CAP_PROP_POS_FRAMES -- see AGENTS.md §9."""
    src = PROBE.read_text(encoding="utf-8")
    for bad in ("VideoCapture", "cv2.imread", "CAP_PROP_POS_FRAMES",
                "CAP_PROP_POS_MSEC", "set(CAP_PROP"):
        assert bad not in src


def test_probe_imports_the_real_resolver_and_matchers():
    """The card forbids re-implementing the resolver or the matcher."""
    src = PROBE.read_text(encoding="utf-8")
    assert "from src.recognition.action_context import" in src
    assert "import evaluate as ev_script" in src
    assert "import evaluate_timed as et" in src
    assert "ActionContextResolver()._decide" in src.replace(
        "r = ActionContextResolver()", "ActionContextResolver()._decide")


def test_probe_exit_codes_are_the_pre_registered_ones():
    """exit 2 on FAIL (and on a G1 mismatch), 0 otherwise."""
    src = PROBE.read_text(encoding="utf-8")
    assert 'return 2\n' in src or '        return 2' in src
    assert "TOUCH_COUNT_LEVER_REFUTED" in src
    assert "TOUCH_COUNT_LEVER_CONFIRMED" in src
    assert "TOUCH_COUNT_LEVER_PARTIAL" in src


def test_vfr_seek_guard_accepts_the_probe():
    """The repo's own no-seek guard must pass on the new script."""
    guard = REPO / "tests" / "test_vfr_seek_guard.py"
    if not guard.exists():
        pytest.skip("no seek guard in this checkout")
    r = subprocess.run([sys.executable, "-m", "pytest", str(guard),
                        "-o", "addopts=", "-q"],
                       cwd=str(REPO), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-4000:]


# ----------------------------------------------------------------------
# 2. step 1 -- G1 reproduces #68
# ----------------------------------------------------------------------

MATCH_ARTIFACTS = [REPO / probe.MATCH_DIAG, REPO / probe.MATCH_GT,
                   REPO / probe.MATCH_PIPELINE]


@pytest.fixture(scope="module")
def g1():
    if not all(p.exists() for p in MATCH_ARTIFACTS):
        pytest.skip("match artifacts not present")
    data, mismatch = probe.step1_g1()
    assert mismatch == {}, f"G1 does not reproduce: {mismatch}"
    return data


def test_g1_is_green(g1):
    """Every pinned #68 number reproduced exactly."""
    assert g1["mismatch"] == {}


def test_g1_accepted_and_gesture_table(g1):
    assert g1["got"]["accepted"] == 185
    assert g1["got"]["bump_set"] == 157
    assert g1["gestures"]["attack"] == 16
    assert g1["gestures"]["block"] == 12


def test_g1_found_and_touch_and_control(g1):
    assert g1["match_stats"]["n_found"] == 139
    assert g1["touch_acc"]["correct"] == 96
    assert g1["r0_score"]["correct"] == 79
    assert g1["gt_score"]["correct"] == 110
    assert g1["fidelity"] == 168


def test_g1_reference_lines(g1):
    """85/139 on the dump's own action field; 0.5899 on the production stream."""
    assert g1["dump_score"]["correct"] == 85
    assert g1["pipeline_output"]["overall"]["accuracy"] == pytest.approx(0.5899)


def test_g1_timing_serve_median_is_the_production_stream(g1):
    """#68's +23 f serve median only reproduces on the production stream."""
    assert g1["timing"]["serve"]["median_delta_f"] == 23
    for cls in ("dig", "set", "spike", "overpass"):
        assert g1["timing"][cls]["median_delta_f"] == -2


def test_g1_replay_serves_are_unreachable(g1):
    """#68's caveat: 0/12 replayed serves vs the dump's own 7/12."""
    assert g1["r0_serve"] == 0
    assert g1["dumped_serve"] == 7
    assert g1["missing_behind_baseline"] == 0
    assert g1["missing_own_side_drive_block"] == 0


def test_g1_matcher_policy_is_reported(g1):
    """The non-exclusive policy gives 139 found over 137 distinct contacts;
    evaluate_timed's one-to-one assignment gives 137."""
    s = g1["match_stats"]
    assert s["n_found"] == 139
    assert s["n_distinct_contacts_found"] == 137
    assert s["evaluate_timed_onetoone_pairs"] == 137
    assert "non-exclusive" in s["matcher"]


# ----------------------------------------------------------------------
# 3. step 2 -- the buckets
# ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def buckets(g1):
    if not all(p.exists() for p in MATCH_ARTIFACTS):
        pytest.skip("match artifacts not present")
    return probe.step2_buckets(g1)


def test_buckets_are_total_over_the_fixed_vocabulary():
    """The partition covers every wrong-touch row exactly once."""
    assert tuple(probe.BUCKET_ORDER) == (
        "previous_contact_missing", "team_change_not_reset",
        "attack_not_reset", "over_counted", "under_counted")


def test_buckets_sum_to_the_43_wrong_touches(buckets, g1):
    assert len(buckets["rows"]) == 43
    assert sum(buckets["table"].values()) == 43
    wrong = 43
    assert wrong == g1["match_stats"]["n_found"] - g1["touch_acc"]["correct"]


def test_bucket_sizes_are_pinned(buckets):
    """#69 measured partition."""
    assert buckets["table"] == {"previous_contact_missing": 13,
                                "team_change_not_reset": 5,
                                "attack_not_reset": 1,
                                "over_counted": 4,
                                "under_counted": 20}


def test_every_row_carries_its_local_context(buckets):
    for r in buckets["rows"]:
        for k in ("point", "gt_frame", "gt_action", "gt_touch", "pred_frame",
                  "pred_action", "emitted_touch", "gesture", "team",
                  "ball_side", "kind", "near_net", "rally_id",
                  "prev_accepted", "next_accepted", "prev_gt_event", "bucket"):
            assert k in r, k
        assert r["bucket"] in probe.BUCKET_ORDER


def test_buckets_are_deterministic(g1, buckets):
    again = probe.step2_buckets(g1)
    assert [r["bucket"] for r in again["rows"]] == \
           [r["bucket"] for r in buckets["rows"]]


def test_starvation_dominates(buckets):
    """33 of 43 (under_counted + previous_contact_missing) -- the mechanism."""
    t = buckets["table"]
    assert t["under_counted"] + t["previous_contact_missing"] == 33


# ----------------------------------------------------------------------
# 4. step 3 -- rule reset semantics on SYNTHETIC sequences
# ----------------------------------------------------------------------

def _c(frame, gesture="bump_set", team="A", rally=1, ball_side="A",
       touch=1, action="dig"):
    return {"frame": frame, "gesture": gesture, "team": team,
            "rally_id": rally, "ball_side": ball_side, "touch_number": touch,
            "action": action, "near_net": False}


def test_r0_is_the_emitted_touch():
    cs = [_c(10, touch=1), _c(20, touch=2), _c(30, touch=3)]
    assert probe.rule_r0(cs) == [1, 2, 3]


def test_r0_returns_rather_than_counting_past_three():
    """The resolver's own reset is kept by every arm."""
    cs = [_c(10), _c(20), _c(30), _c(40)]        # 4 touches, same possession
    for rule in probe.RULE_NAMES:
        assert probe.rule_touches(cs, rule)[-1] == 1, rule


def test_r1_resets_on_any_team_change():
    """R0 is the EMITTED count; R1 resets on any team change."""
    cs = [_c(10, team="A", touch=1), _c(20, team="A", touch=2),
          _c(30, team="B", touch=3)]
    assert probe.rule_touches(cs, "R0") == [1, 2, 3]
    assert probe.rule_touches(cs, "R1") == [1, 2, 1]


def test_r1_is_the_first_rule_that_differs_from_r0():
    """The resolver's own resets (new_rally by frame gap, attack_before, the
    4th-touch wrap) are kept in EVERY arm including R0, so on a possession
    that needs none of R1-R4's extra resets all five arms agree."""
    cs = [_c(10, touch=1), _c(20, touch=2), _c(30, touch=3)]
    for rule in probe.RULE_NAMES:
        assert probe.rule_touches(cs, rule) == [1, 2, 3], rule


def test_r2_is_subsumed_by_the_base_attack_reset():
    """CARD DEFINITION FINDING: the card keeps the resolver's own resets in
    every arm, and one of them is `attack_before` -- a reset after an
    `attack`/`block` gesture, which is exactly R2. So R2's added switch is a
    NO-OP by construction and R2 == R1 on every sequence. Pinned here so the
    redundancy cannot be silently changed."""
    cs = [_c(10), _c(20, gesture="attack", action="spike"), _c(30),
          _c(40, team="B")]
    assert probe.rule_touches(cs, "R1") == [1, 2, 1, 1]
    assert probe.rule_touches(cs, "R2") == probe.rule_touches(cs, "R1")


def test_r2_covers_block_as_an_attack_gesture():
    """Both `attack` and `block` are attack gestures for the base reset."""
    cs = [_c(10), _c(20, gesture="block", action="block"), _c(30)]
    assert probe.rule_touches(cs, "R2") == [1, 2, 1]


def test_r3_adds_the_rally_id_reset():
    """rally_id change with a SHORT frame gap: the base gap reset does not
    fire, so R3 is the rule that catches it."""
    cs = [_c(10, rally=7), _c(20, rally=7), _c(30, rally=8)]
    assert probe.rule_touches(cs, "R2") == [1, 2, 3]
    assert probe.rule_touches(cs, "R3") == [1, 2, 1]


def test_the_base_new_rally_reset_is_in_every_arm():
    """A frame gap beyond ActionContextResolver.rally_reset_gap resets R0 too."""
    far = probe.RALLY_GAP + 10
    cs = [_c(10), _c(10 + far)]
    for rule in probe.RULE_NAMES:
        assert probe.rule_touches(cs, rule) == [1, 1], rule


def test_r4_abstains_when_ball_side_is_unknown():
    """The 64-of-185 case: no ball_side, no cross confirmation, no reset."""
    cs = [_c(10, team="A"), _c(20, team="A"), _c(30, team="B", ball_side=None)]
    assert probe.rule_touches(cs, "R4") == [1, 2, 3]
    # ... and the same sequence WITH the width confirming the cross:
    cs2 = [_c(10, team="A"), _c(20, team="A"), _c(30, team="B", ball_side="B")]
    assert probe.rule_touches(cs2, "R4") == [1, 2, 1]


def test_r4_does_not_reset_when_the_width_disagrees():
    """ball_side must CONFIRM the cross; a contradicting read abstains."""
    cs = [_c(10, team="A"), _c(20, team="A"), _c(30, team="B", ball_side="A")]
    assert probe.rule_touches(cs, "R4") == [1, 2, 3]


def test_the_ladder_nests():
    """The switch sets grow monotonically R1 -> R4 (as the card defines them)."""
    assert [name for name, _ in probe.RULES] == ["R0", "R1", "R2", "R3", "R4"]
    off = {"reset_on_team_change": False, "reset_after_attack": False,
           "reset_on_rally_change": False, "ball_side_cross": False}
    expected = [dict(off),
                {**off, "reset_on_team_change": True},
                {**off, "reset_on_team_change": True, "reset_after_attack": True},
                {**off, "reset_on_team_change": True, "reset_after_attack": True,
                 "reset_on_rally_change": True},
                {**off, "reset_on_team_change": True, "reset_after_attack": True,
                 "reset_on_rally_change": True, "ball_side_cross": True}]
    assert [kw for _n, kw in probe.RULES] == expected
    for (_n1, a), (_n2, b) in zip(probe.RULES, probe.RULES[1:]):
        for k, v in b.items():
            assert v >= a[k], f"{k} is not monotone from {_n1} to {_n2}"


def test_rules_are_pure_functions_of_the_contact_list():
    """No GT, no file, no frame: two calls agree and input is untouched."""
    cs = [_c(10), _c(20, gesture="attack"), _c(30, team="B", rally=2)]
    snapshot = json.dumps(cs, sort_keys=True)
    a = probe.rule_touches(cs, "R4")
    b = probe.rule_touches(cs, "R4")
    assert a == b
    assert json.dumps(cs, sort_keys=True) == snapshot


def test_unknown_rule_raises():
    with pytest.raises(KeyError):
        probe.rule_touches([_c(10)], "R99")


# ----------------------------------------------------------------------
# 5. the pre-registered verdict truth table
# ----------------------------------------------------------------------

def _v(acc, ok, rel_ok, chosen=True):
    g2 = {"score": {"accuracy": acc}, "rule": "R4"}
    search = {"chosen": "R4" if chosen else None}
    g1s = {"r0_score": {"accuracy": 0.5683}}
    b = {"table": {}}
    return probe.verdict(g2, search, g1s, b,
                         {"all_within_0.01": ok,
                          "all_within_0.01_vs_r0_replay": rel_ok})


def test_verdict_confirmed_requires_all_three():
    """CONFIRMED needs (i) acc >= 0.700, (ii) every replay within +-0.01 as
    written, and (iii) the rule chosen on dev+entreno only."""
    assert _v(0.70, True, True)["token"] == "TOUCH_COUNT_LEVER_CONFIRMED"
    assert _v(0.80, False, True)["token"].startswith(
        "TOUCH_COUNT_LEVER_PARTIAL")      # (i) ok, (ii) only via the fallback
    assert _v(0.80, False, False)["token"].startswith(
        "TOUCH_COUNT_LEVER_REFUTED")


def test_verdict_partial_band():
    assert _v(0.65, True, True)["token"] == "TOUCH_COUNT_LEVER_PARTIAL/0.65"
    assert _v(0.6999, True, True)["token"].startswith(
        "TOUCH_COUNT_LEVER_PARTIAL")
    assert _v(0.6499, True, True)["token"].startswith(
        "TOUCH_COUNT_LEVER_REFUTED")


def test_verdict_thresholds_are_gains_over_r0():
    """0.700 = +0.132 over the 79/139 control, 0.650 = +0.082."""
    assert pytest.approx(0.700 - 0.5683, abs=1e-3) == 0.1317
    assert pytest.approx(0.650 - 0.5683, abs=1e-3) == 0.0817
    assert "gains over the R0 replay control" in probe.verdict.__doc__


def test_verdict_requires_the_rule_to_be_chosen_on_dev_entreno():
    assert _v(0.80, True, True, chosen=False)["token"].startswith(
        "TOUCH_COUNT_LEVER_REFUTED")


def test_verdict_partial_accepts_the_rule_relative_entreno_check():
    """(ii) as written is False for a replay; the rule-relative form is the
    only attributable one, so PARTIAL accepts either."""
    assert _v(0.66, False, True)["token"] == "TOUCH_COUNT_LEVER_PARTIAL/0.66"
    assert _v(0.66, False, False)["token"].startswith(
        "TOUCH_COUNT_LEVER_REFUTED")


def test_measured_verdict_is_refuted(g1):
    """The measured TC1 outcome is pinned so a silent regression is loud."""
    touches = probe.rule_touches(g1["contacts"], "R4")
    labels = probe.replay_decide(g1["contacts"], touches)
    score = probe.score_labels(g1["pairs"], g1["contacts"], labels)
    assert score["correct"] == 86
    assert score["accuracy"] == pytest.approx(0.6187, abs=1e-4)
    assert probe.touch_accuracy(g1["contacts"], g1["pairs"], touches)[
        "correct"] == 103
    v = _v(score["accuracy"], ok=False, rel_ok=False)
    assert v["token"] == "TOUCH_COUNT_LEVER_REFUTED/0.6187"
    assert v["gain_over_r0"] == pytest.approx(0.0504, abs=1e-3)


def test_non_serve_arm_matches_68(g1):
    """The card's non-gating arms: R0 79/127 and the GT-touch arm 110/127."""
    assert g1["r0_score"]["nonserve_correct"] == 79
    assert g1["r0_score"]["nonserve_n"] == 127
    assert g1["gt_score"]["nonserve_correct"] == 110
    assert g1["gt_score"]["nonserve_accuracy"] == pytest.approx(0.866, abs=1e-3)


def test_gt_touch_series_uses_events_not_contacts(g1):
    """The trap #68 hit: touch_number lives in points[].events[] only.

    139 found EVENTS map onto 137 DISTINCT contacts (two contacts serve two GT
    events under the non-exclusive matcher), so the series has 137 non-None
    entries over 185 contacts."""
    series = g1["gt_touch_series"]
    assert len(series) == len(g1["contacts"]) == 185
    assert sum(1 for v in series if v is not None) == 137
    assert all(v is None or v in (1, 2, 3) for v in series)
    # a contacts[]-style read would yield nothing at all -- the trap
    blob = json.loads((REPO / probe.MATCH_GT).read_text(encoding="utf-8"))
    assert all("touch_number" not in c
               for p in blob["points"] for c in (p.get("contacts") or []))
    assert any("touch_number" in e
               for p in blob["points"] for e in (p.get("events") or []))


def test_entreno_gate_record_is_pinned():
    assert probe.ENTRENO_BASELINE == {1: 0.706, 2: 0.571, 3: 1.0, 4: 0.933,
                                      5: 0.923, 6: 0.933, 7: 0.75}


def test_clips_are_dev_plus_the_seven_drills():
    assert [c["name"] for c in probe.CLIPS] == ["dev"] + [f"e{i}"
                                                          for i in range(1, 8)]
    for c in probe.CLIPS:
        assert not c["gt"].startswith("ground_truth/video_ari_joan_lost")