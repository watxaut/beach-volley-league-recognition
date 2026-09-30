"""G3 R1 evidence probe: do all 17 owner serve-verdicts reproduce on an arm?

Reads a pass-2 ``serve_relabel.json`` and checks every anchored verdict P1-P17
in ``ground_truth/20260920_match_serve_anchors.txt`` against the layer's
mechanical resolution, the way STATUS #28 records it:

- NOT_TRACKED far (P1,P2,P4,P6,P14)  -> decision relabeled
- NOT_TRACKED near (P5,P7)           -> anchor_only (opener rejected)
- TRACKED (P3,P16,P17)               -> emitted, serve near the anchor
- MISCLASSIFIED (P9,P10,P11,P12)     -> the owner-identified CONTACT frame
  resolves as the serve (re-labeled in actions_pass2)
- P13 far tracked                    -> emitted 28f late (8534B)
- P15 far owner-confirmed            -> emitted (10070B)
plus the owner FALSE/OFFGAME demotions and the P20 pin / P32 report_only.

G3 R1 refutation context (NOT shipped; src/ at 185c6f0): on the gate-ON arm
the P11 verdict regresses (the gate removed the owner-confirmed serve
f7132 at 0.285 bw/f, so pass-2 resolves f7160) and P4 degrades to
anchor_only — that is the committed STOP evidence, see
``docs/g3_r1_departure_gate.md``. Defaults point at the gate-ON arm
(match_bw03); pass ``output/g3r1/match_bw0_serve_relabel.json`` for the
17/17 production reproduction.

Usage:
    python scripts/probe_owner_verdicts.py [serve_relabel.json]
"""

import argparse
import json
import sys

DEFAULT_RELABEL = "output/g3r1/match_bw03_serve_relabel.json"

# point -> (verdict, expected decision, expected serve frame (or None))
EXPECTED = {
    1: ("NOT_TRACKED far", "relabeled", 247),
    2: ("NOT_TRACKED far", "relabeled", 930),
    3: ("TRACKED near", "emitted", 1396),
    4: ("NOT_TRACKED far", "relabeled", None),
    5: ("NOT_TRACKED near", "anchor_only", None),
    6: ("NOT_TRACKED far", "relabeled", 3070),
    7: ("NOT_TRACKED near", "anchor_only", None),
    8: ("NOT_TRACKED far", "relabeled", 4801),
    9: ("MISCLASSIFIED", "relabeled", 5496),
    10: ("MISCLASSIFIED", "relabeled", 6034),
    11: ("MISCLASSIFIED", "relabeled", 7132),
    12: ("MISCLASSIFIED", "relabeled", 7780),
    13: ("far tracked", "emitted", 8534),
    14: ("NOT_TRACKED far", "relabeled", 9137),
    15: ("far owner-confirmed", "emitted", 10070),
    16: ("TRACKED near", "emitted", 10541),
    17: ("TRACKED near", "emitted", 11410),
}
# Owner FALSE marks that MUST be demoted (3650 covers 3595A and 3856B;
# 11050 and the OFFGAME pass 14387 are structural; see anchors file).
# NOTE: on the gate-ON g3r1 arm, f2414 and f5130 no longer EXIST in the
# stream (the parked gate removed them upstream) -- they then appear as
# "not demoted" mechanically; that arm is read as the REGRESSION case.
MUST_DEMOTE = [1039, 2414, 3595, 3856, 5130, 14387]
P20_PIN = {"point": 20, "decision": "owner_pinned", "frame": 14516}
P32 = {"point": 32, "decision": "report_only"}


def main(path: str) -> int:
    d = json.load(open(path))
    pts = {p["point"]: p for p in d["points"]}
    demoted = {x["frame"] for x in d.get("demotions", [])}
    ok = True
    print(f"== 17 owner verdicts on {path} ==")
    for k in sorted(EXPECTED):
        verdict, dec, frame = EXPECTED[k]
        p = pts.get(k, {})
        got = p.get("decision")
        s = p.get("serve") or {}
        gf = s.get("frame")
        good = got == dec and (frame is None or gf == frame)
        ok &= good
        print(f"  P{k:<2} {verdict:<22} -> {got:<12} serve f{gf} "
              f"(expect {dec}" + (f", f{frame}" if frame else "") + f") "
              f"{'OK' if good else 'MISMATCH'}")
    for f in MUST_DEMOTE:
        good = f in demoted
        ok &= good
        print(f"  FALSE/OFFGAME f{f}: demoted={good}")
    p20 = pts.get(20, {})
    good = (p20.get("decision") == P20_PIN["decision"]
            and (p20.get("serve") or {}).get("frame") == P20_PIN["frame"])
    ok &= good
    print(f"  P20 pinned 14516A: {good}")
    good = pts.get(32, {}).get("decision") == P32["decision"]
    ok &= good
    print(f"  P32 report_only: {good}")
    print("VERDICTS:", "17/17 reproduced" if ok else "REGRESSION")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("relabel", nargs="?", default=DEFAULT_RELABEL,
                    help="pass-2 serve_relabel.json to check")
    args = ap.parse_args()
    sys.exit(main(args.relabel))
