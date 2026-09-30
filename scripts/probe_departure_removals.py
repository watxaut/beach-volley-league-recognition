"""G3 R1 evidence probe: list the actions the parked departure gate removed.

Arm-diff of the two committed g3r1 match runs (same code + device, yaml-only
difference): the removed-action list is bw0 (gate OFF) emitted minus bw03
(gate ON, ``contact_min_departure_bw: 0.3``) emitted, keyed on frame, with
each removal's departure bw/f read from the bw03 diag dump (the
``low_departure`` rejection record at that contact frame). Also reports any
ADDED action (2nd-order effects: a rejection frees ``_last_contact_frame``
and can admit a later candidate).

The gate itself is NOT shipped (owner decision 2026-09-30, option (a)):
``src/`` is at 185c6f0; this probe reads only the committed
``output/g3r1/`` artifacts (the refutation evidence). Defaults reproduce the
run recorded in ``docs/g3_r1_departure_gate.md`` / ``logs/r1_finish_report.md``.

Usage:
    python scripts/probe_departure_removals.py            # committed defaults
    python scripts/probe_departure_removals.py <bw0_pipeline.json> <bw03_pipeline.json> <bw03_diag.jsonl>
"""

import argparse
import json
from collections import defaultdict

DEFAULT_BW0 = "output/g3r1/match_bw0/pipeline_output.json"
DEFAULT_BW03 = "output/g3r1/match_bw03/pipeline_output.json"
DEFAULT_DIAG = "output/g3r1/match_bw03_diag.jsonl"


def low_departure_index(diag_path):
    by_frame = defaultdict(list)
    with open(diag_path) as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            for c in rec.get("candidates", []) or []:
                if isinstance(c, dict) and c.get("reason") == "low_departure":
                    by_frame[c.get("frame")].append(c)
    return by_frame


def main(bw0_json, bw03_json, diag_path):
    a = json.load(open(bw0_json))["actions"]
    b = json.load(open(bw03_json))["actions"]
    ka = {(x.get("frame_number", x.get("frame"))): x for x in a}
    kb = {(x.get("frame_number", x.get("frame"))): x for x in b}
    rej = low_departure_index(diag_path)
    print(f"bw0 {len(a)} actions -> bw03 {len(b)} actions")
    print("removed (frame, action, team, bw/f, kind):")
    for f in sorted(set(ka) - set(kb)):
        x = ka[f]
        cands = rej.get(f) or []
        bw = cands[0].get("departure_bw_f") if cands else None
        kind = cands[0].get("kind") if cands else None
        thr = cands[0].get("threshold") if cands else None
        print(f"  f{f:<6} {x.get('action'):<8} team {x.get('team')}  "
              f"bw/f {bw}  kind {kind}  thr {thr}")
    added = sorted(set(kb) - set(ka))
    print("added:", [(f, kb[f].get("action"), kb[f].get("team")) for f in added]
          or "none")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bw0", nargs="?", default=DEFAULT_BW0,
                    help="gate-OFF arm pipeline_output.json")
    ap.add_argument("bw03", nargs="?", default=DEFAULT_BW03,
                    help="gate-ON arm pipeline_output.json")
    ap.add_argument("diag", nargs="?", default=DEFAULT_DIAG,
                    help="gate-ON arm diag dump (--diag-dump jsonl)")
    args = ap.parse_args()
    main(args.bw0, args.bw03, args.diag)
