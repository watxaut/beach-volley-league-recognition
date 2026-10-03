"""G3 -- the set<->dig swap probe: contract tests (no decode, no seek).

Covers `scripts/probe_set_dig_swaps.py`:

* the no-cv2 / no-seek / no-decode contract (AGENTS.md section 9);
* G1: the #68 numbers reproduce exactly before any swap is read;
* the swap set: 13 dump-derived swaps (9 GT-set->dig, 4 GT-dig->set), all
  bump_set, all with a WRONG emitted touch count, identical under the dump's
  own action field and the R0 replay;
* the reconciliation against #68's production-stream 15 (extras 7162/7207);
* determinism: two derives produce byte-identical JSON.

The artifact-backed tests skip (never fail) when the committed dumps are
missing, so a fresh clone without `output/` still runs the suite.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PROBE = REPO / "scripts" / "probe_set_dig_swaps.py"
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

ARTIFACTS = (REPO / "output/g3r1/match_bw03_diag.jsonl",
             REPO / "ground_truth/20260920_match_contacts.json",
             REPO / "output/20260920_match_ari_joan_lost/pipeline_output.json")


def _load_probe():
    import probe_set_dig_swaps as p  # noqa: E402
    return p


probe = _load_probe()


# ----------------------------------------------------------------------
# 1. the contract: no cv2 import, no seek, no decode
# ----------------------------------------------------------------------

def test_probe_has_no_cv2_import():
    tree = ast.parse(PROBE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert not a.name.startswith("cv2"), f"imports {a.name}"
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("cv2")


def test_probe_does_not_use_video_capture():
    src = PROBE.read_text(encoding="utf-8")
    for bad in ("VideoCapture", "cv2.imread", "CAP_PROP_POS_FRAMES",
                "CAP_PROP_POS_MSEC", "set(CAP_PROP"):
        assert bad not in src


def test_probe_imports_the_matcher_never_reimplements():
    """The matching/replay machinery is imported from probe_touch_rules."""
    src = PROBE.read_text(encoding="utf-8")
    assert "import probe_touch_rules as pt" in src
    assert "pt.match_contacts" in src and "pt.replay_decide" in src
    assert "def match_contacts" not in src       # not re-implemented here
    assert "def replay_decide" not in src


# ----------------------------------------------------------------------
# 2. artifact-backed pins
# ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def derived():
    if not all(p.exists() for p in ARTIFACTS):
        pytest.skip("match artifacts not present")
    return probe.derive()


def test_g1_reproduces_68_exactly(derived):
    assert derived["gate"] == "G1_GREEN"
    assert derived["g1"] == {"accepted": 185, "found": 139,
                             "touch_correct": 96, "r0_correct": 79}


def test_swap_count_and_groups(derived):
    rows = derived["swaps"]
    assert len(rows) == 13
    assert sum(1 for r in rows if r["gt_action"] == "set") == 9
    assert sum(1 for r in rows if r["gt_action"] == "dig") == 4
    for r in rows:
        assert (r["gt_action"], r["pred_action"]) in (("set", "dig"),
                                                      ("dig", "set"))


def test_every_swap_is_a_touch_miscount_with_bump_set(derived):
    """set<->dig in `_decide` is purely touch-keyed: no swap may carry a
    correct touch count, and all are Layer-1 `bump_set`."""
    for r in derived["swaps"]:
        assert r["gesture"] == "bump_set"
        assert r["touch_correct"] is False
        assert abs(r["gt_touch"] - r["emitted_touch"]) == 1
        if r["gt_action"] == "set":
            assert (r["gt_touch"], r["emitted_touch"]) == (2, 1)
        else:
            assert (r["gt_touch"], r["emitted_touch"]) == (1, 2)


def test_reconciliation_against_68_production_count(derived):
    rec = derived["reconciliation"]
    assert rec["production_count"] == 15     # #68's table
    assert rec["dump_count"] == 13
    assert rec["extras_in_production_only"] == [7162, 7207]
    assert rec["in_dump_only"] == []


def test_verdict_is_no_separator_with_all_signals(derived):
    v = derived["verdict"]
    assert v["verdict"] == "NO SEPARATOR"
    for sig in ("ball_above_net_px", "vy_in", "vy_out", "speed_in",
                "speed_out", "gesture", "near_net", "kind", "team_match",
                "touch_correct", "taker_zone"):
        assert sig in v["tried"]
    for entry in derived["comparison"]["numeric"].values():
        assert entry["zero_overlap"] is False


def test_derive_is_deterministic(derived):
    again = probe.derive()
    assert json.dumps(again, sort_keys=True, default=str) == \
        json.dumps(derived, sort_keys=True, default=str)
