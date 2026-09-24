"""Parse the owner's dictated match GT text into machine-readable JSON.

The owner annotates matches as free text: one line per point
(``P<n>: description``) followed by a running score table (``A  B`` rows)
with ``Side switch`` markers between rows. This script transcribes that
file into ``ground_truth/<stem>_match_points.json`` so evaluators can read
it without re-parsing prose.

Derived fields are MECHANICAL, from the score table only:

- ``winner`` -- which column incremented vs the previous row (first row
  diffs from 0-0). Descriptions are stored verbatim and never used to
  derive the winner.
- ``side_switch_after`` -- true for the point ordinal immediately before
  each ``Side switch`` marker (teams swap halves for the NEXT point).

Usage:
    python scripts/parse_match_gt_text.py \
        ground_truth/20260920_match_ari_joan_lost.txt \
        --out ground_truth/20260920_match_points.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

_DESC_RE = re.compile(r"^P(\d+):\s*(.+?)\s*$")
_SCORE_RE = re.compile(r"^(\d+)\s+(\d+)\s*$")
_SWITCH = "side switch"


def parse_match_gt_text(text: str) -> dict:
    """Parse the dictated text into the match-points-v1 dict structure.

    Raises ValueError with a line reference on any structural problem --
    the transcription must fail loudly, never guess.
    """
    descriptions = []  # (ordinal, description)
    scores = []        # (a, b)
    switch_after_ordinal = []  # point ordinals followed by a side switch

    lines = text.splitlines()
    in_table = False
    for ln, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        if line.lower() == "points":
            in_table = True
            continue
        if not in_table:
            m = _DESC_RE.match(line)
            if m:
                descriptions.append((int(m.group(1)), m.group(2)))
            continue
        if line.lower() == _SWITCH:
            if not scores:
                raise ValueError(f"line {ln}: 'Side switch' before any score row")
            switch_after_ordinal.append(len(scores))
            continue
        if line.upper() == "A  B":
            continue  # table header
        m = _SCORE_RE.match(line)
        if m:
            scores.append((int(m.group(1)), int(m.group(2))))
            continue
        raise ValueError(f"line {ln}: unparsed table line: {line!r}")

    if not descriptions:
        raise ValueError("no 'P<n>:' description lines found")
    if not scores:
        raise ValueError("no score rows found below the 'Points' header")
    if len(descriptions) != len(scores):
        raise ValueError(
            f"{len(descriptions)} descriptions vs {len(scores)} score rows"
        )
    ordinals = [o for o, _ in descriptions]
    if ordinals != list(range(1, len(descriptions) + 1)):
        raise ValueError(f"description ordinals not 1..N in order: {ordinals}")

    # winners mechanically from the running score
    points = []
    prev = (0, 0)
    for i, ((a, b), (ordinal, desc)) in enumerate(zip(scores, descriptions)):
        da, db = a - prev[0], b - prev[1]
        if (da, db) not in ((0, 1), (1, 0)):
            raise ValueError(
                f"score row {i + 1} ('{a} {b}') does not increment exactly "
                f"one side from '{prev[0]} {prev[1]}'"
            )
        points.append(
            {
                "point": ordinal,
                "winner": "A" if da == 1 else "B",
                "score_after": {"A": a, "B": b},
                "side_switch_after": ordinal in switch_after_ordinal,
                "description": desc,
            }
        )
        prev = (a, b)

    return {
        "format": "match-points-v1",
        # filled by the CLI from the input path
        "video": "",
        "source_text": "",
        "conventions": {
            "team_a": "fixed squad; played the NEAR side at match start",
            "team_b": "fixed squad; played the FAR side at match start",
            "side_switch_after_point": (
                "teams swap court halves AFTER the flagged point ordinal; "
                "the next point is played on switched sides"
            ),
            "winner": "mechanically derived from the running score table",
            "descriptions": (
                "verbatim owner dictation; 'P<k>' inside a description "
                "refers to a PLAYER (track id), not a point"
            ),
        },
        "final_score": {"A": scores[-1][0], "B": scores[-1][1]},
        "side_switch_after_point": switch_after_ordinal,
        "points": points,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", help="owner's dictated match GT text file")
    ap.add_argument("--out", required=True, help="output JSON path")
    args = ap.parse_args(argv)

    src = Path(args.input)
    text = src.read_text(encoding="utf-8")
    gt = parse_match_gt_text(text)
    stem = src.stem
    # strip a known "_match_..." double-prefix safely: keep the stem as-is
    gt["video"] = stem
    gt["source_text"] = str(src)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(gt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"{out}: {len(gt['points'])} points, final "
        f"{gt['final_score']['A']}-{gt['final_score']['B']}, "
        f"side switches after {gt['side_switch_after_point']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
