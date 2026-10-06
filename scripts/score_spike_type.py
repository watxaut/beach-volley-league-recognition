#!/usr/bin/env python3
"""V1: score hard / touch spikes on the 20260920 match against the owner GT.

    venv/bin/python scripts/score_spike_type.py \
        [output/postrun/20260920_match] [--gt ground_truth/20260920_match_contacts.json]

Why: the web wants to draw hard and touch attacks differently
(docs/stats_feature_brainstorm.md O2). The causal ``SpikeAnalyzer``
(post-contact ascent) is right on 6 of 6 practice spikes, but on the match it
was never scored: 32 spikes carry an owner label (13 hard, 19 touch).

PASS RULE, fixed before the first run (brainstorm V1): accuracy >= 0.85 AND
coverage >= 0.80 over the owner-labelled spikes, scored the way the web sees
them -- GT spike -> the post-run attack within +-15 f -> the causal spike
record the publisher joins to that attack (``bundle._nearest_spike``). Below
either bar the hard / touch encoding is dropped from the web.

Also printed (diagnostics, not the verdict): the record nearest to the GT frame
directly, and how many of all post-run attacks get a record at all.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_postrun import GT_CONTACTS, TOLERANCE, match_touches  # noqa: E402
from src.publish.bundle import ATTACKS, _nearest_spike  # noqa: E402

TYPES = ("hard", "touch")
ACCURACY_BAR = 0.85
COVERAGE_BAR = 0.80


def gt_spikes(contacts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every owner-dictated spike with its frame, point and (maybe) type."""
    out = []
    for p in contacts["points"]:
        for c in p["contacts"]:
            if c.get("action") == "spike":
                out.append({"point": p["point"], "frame": c["match_frame"],
                            "type": c.get("spike_type"), "outcome": c.get("outcome")})
    return out


def score(recon: Dict[str, Any], spikes: List[Dict[str, Any]],
          gt: List[Dict[str, Any]], tolerance: int = TOLERANCE) -> Dict[str, Any]:
    """Pure scoring: ``recon`` is match_reconstruction.json, ``spikes`` the
    causal records of pipeline_output.json, ``gt`` from :func:`gt_spikes`."""
    attacks = [{"frame": t["frame"], "action": t["action"]}
               for p in recon["points"] for t in p["touches"] if t["action"] in ATTACKS]
    labelled = [g for g in gt if g["type"] in TYPES]

    # GT spike -> the post-run attack touch (1:1 by frame distance)
    pairing = dict(match_touches(attacks, [{"frame": g["frame"]} for g in labelled], tolerance))
    to_gt = {j: i for i, j in pairing.items()}

    confusion = {g: {"hard": 0, "touch": 0, "none": 0} for g in TYPES}
    covered = correct = 0
    direct_covered = direct_correct = 0
    rows = []
    for j, g in enumerate(labelled):
        attack = attacks[to_gt[j]] if j in to_gt else None
        rec = _nearest_spike(attack["frame"], spikes) if attack else None
        pred = rec.get("spike_type") if rec else None
        confusion[g["type"]][pred if pred in TYPES else "none"] += 1
        if pred in TYPES:
            covered += 1
            correct += pred == g["type"]
        raw = _nearest_spike(g["frame"], spikes)
        raw_pred = raw.get("spike_type") if raw else None
        if raw_pred in TYPES:
            direct_covered += 1
            direct_correct += raw_pred == g["type"]
        rows.append({"point": g["point"], "frame": g["frame"], "gt": g["type"],
                     "attack_found": attack is not None, "published": pred, "direct": raw_pred})
    n = len(labelled)
    accuracy = correct / covered if covered else 0.0
    coverage = covered / n if n else 0.0
    with_record = sum(1 for a in attacks if _nearest_spike(a["frame"], spikes))
    return {
        "n_gt_spikes": len(gt), "n_labelled": n,
        "attack_matched": len(pairing), "covered": covered, "correct": correct,
        "accuracy": accuracy, "coverage": coverage, "confusion": confusion,
        "direct": {"covered": direct_covered, "correct": direct_correct},
        "attacks": {"n": len(attacks), "with_record": with_record},
        "pass": accuracy >= ACCURACY_BAR and coverage >= COVERAGE_BAR,
        "rows": rows,
    }


def wilson(k: int, n: int, z: float = 1.96) -> Optional[tuple]:
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def report(r: Dict[str, Any]) -> str:
    lo, hi = wilson(r["correct"], r["covered"]) or (0, 0)
    lines = [
        f"GT spikes {r['n_gt_spikes']}, owner-labelled hard/touch {r['n_labelled']}; "
        f"matched to a post-run attack within +-{TOLERANCE} f: {r['attack_matched']}",
        f"coverage (a type is published for the spike): {r['covered']}/{r['n_labelled']} = {r['coverage']:.3f}   "
        f"(bar {COVERAGE_BAR})",
        f"accuracy (published type == owner type):      {r['correct']}/{r['covered']} = {r['accuracy']:.3f}   "
        f"(bar {ACCURACY_BAR}; 95% range {lo:.2f}-{hi:.2f})",
        "confusion (rows = owner, columns = published):",
        f"            {'hard':>6}{'touch':>7}{'none':>6}",
    ]
    for g in TYPES:
        c = r["confusion"][g]
        lines.append(f"  {g:<9} {c['hard']:>6}{c['touch']:>7}{c['none']:>6}")
    d = r["direct"]
    lines += [
        f"diagnostic, record nearest the GT frame: {d['correct']}/{d['covered']} right, "
        f"{d['covered']}/{r['n_labelled']} covered",
        f"diagnostic, all post-run attacks: {r['attacks']['with_record']}/{r['attacks']['n']} have a causal record",
        f"VERDICT: {'PASS' if r['pass'] else 'FAIL'} -> "
        + ("the hard / touch encoding may ship" if r["pass"] else "drop the hard / touch encoding from the web"),
    ]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("run_dir", nargs="?", default="output/postrun/20260920_match",
                   help="directory with match_reconstruction.json + pipeline_output.json")
    p.add_argument("--gt", default=GT_CONTACTS)
    p.add_argument("--rows", action="store_true", help="print every labelled spike")
    args = p.parse_args(argv)
    run = Path(args.run_dir)
    recon = json.loads((run / "match_reconstruction.json").read_text())
    spikes = json.loads((run / "pipeline_output.json").read_text()).get("spikes") or []
    gt = gt_spikes(json.loads(Path(args.gt).read_text()))
    result = score(recon, spikes, gt)
    print(report(result))
    if args.rows:
        for row in result["rows"]:
            print(f"  P{row['point']:<3} f{row['frame']:<6} gt={row['gt']:<6} attack={row['attack_found']!s:<5} "
                  f"published={row['published']} direct={row['direct']}")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
