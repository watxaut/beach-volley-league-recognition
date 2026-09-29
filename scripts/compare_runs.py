#!/usr/bin/env python3
"""Byte-identity check for the T4 diagnostic hooks (gate a/b).

Compares two pipeline output directories field by field. Only the fields listed
in ``VOLATILE`` (run metadata / wall-clock stamps) may differ; everything else
-- actions, spikes, game state, CSVs -- must be identical.

Usage::

    python scripts/compare_runs.py A_dir B_dir [--label "base vs hooks-off"]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: Fields allowed to differ between two runs of the SAME code+video.
VOLATILE_JSON = ("processed_at", "pipeline_version")
CSVS = ("results.csv", "results_detailed.csv", "results_game_state.csv",
        "results_spikes.csv", "results_statistics.csv")
#: Wall-clock metrics inside results_statistics.csv (per-run by construction).
VOLATILE_CSV_ROWS = ("Total_Processing_Time", "Average_Frame_Processing_Time",
                     "Processing_FPS_Achieved")


def _csv_rows(path: Path):
    return [line.split(",")[0] for line in path.read_text().splitlines()[1:] if line]


def _csv_diff(name, a, b):
    """Rows that differ, ignoring the wall-clock metrics (VOLATILE_CSV_ROWS)."""
    la, lb = a.read_text().splitlines(), b.read_text().splitlines()
    if len(la) != len(lb):
        return [f"{name}: line count {len(la)} vs {len(lb)}"]
    diffs = []
    for ra, rb in zip(la[1:], lb[1:]):
        if ra == rb:
            continue
        metric = ra.split(",")[0]
        if metric in VOLATILE_CSV_ROWS:
            continue
        diffs.append(f"{name}: {ra} != {rb}")
    return diffs


def _strip(blob):
    return {k: v for k, v in blob.items() if k not in VOLATILE_JSON}


def compare(a_dir: str, b_dir: str) -> dict:
    a, b = Path(a_dir), Path(b_dir)
    out = {"a": str(a), "b": str(b), "json_identical": None, "volatile_diff": [],
           "csv_diff": [], "missing": []}
    fa, fb = a / "pipeline_output.json", b / "pipeline_output.json"
    if not fa.exists() or not fb.exists():
        out["missing"] = [str(p) for p in (fa, fb) if not p.exists()]
        return out
    ja = json.loads(fa.read_text())
    jb = json.loads(fb.read_text())
    for k in VOLATILE_JSON:
        if ja.get(k) != jb.get(k):
            out["volatile_diff"].append(k)
    out["json_identical"] = _strip(ja) == _strip(jb)
    if not out["json_identical"]:
        sa, sb = _strip(ja), _strip(jb)
        out["differing_top_keys"] = sorted(k for k in set(sa) | set(sb)
                                           if sa.get(k) != sb.get(k))
        if "actions" in out["differing_top_keys"]:
            out["action_diff_count"] = sum(
                1 for x, y in zip(sa.get("actions", []), sb.get("actions", [])) if x != y)
    for name in CSVS:
        pa, pb = a / name, b / name
        if not pa.exists() or not pb.exists():
            out["missing"].append(name)
        else:
            out["csv_diff"].extend(_csv_diff(name, pa, pb))
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--label", default="")
    args = p.parse_args()
    res = compare(args.a, args.b)
    if args.label:
        print(f"== {args.label}")
    print(json.dumps(res, indent=2))
    ok = res["json_identical"] and not res["csv_diff"] and not res["missing"]
    print("RESULT:", "IDENTICAL" if ok else "DIFFERENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
