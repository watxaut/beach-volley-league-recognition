"""Derive per-point serve team, court side and serve-frame windows for a match.

Open point 22 (far-side serves untracked): scoping the diagnostic probe needs
per-point SERVE frames. The match GT (match-points-v1) has NO frame anchors,
but two fields are derivable MECHANICALLY:

- serve TEAM -- the winner of the previous point serves next (beach
  volleyball rule). Cross-checked here against every dictated description
  that names a server ("Team B serves ...", "P1 fails serve", "ace"): a
  mismatch is a hard error, not a warning. Point 1 has no previous winner;
  unless its description names the server the team stays None.
- court SIDE -- Team A played the near half at match start and halves swap
  after every flagged side switch; squads are fixed (GT convention).

Serve-moment FRAMES come from the partial game-state anchor file
(``gt_point_start_end.txt`` format: "MM:SS point starts" marks the SERVE
moment, "point stops" the ball death; whole-second granularity, +/-15f).
That file currently anchors only points 1..13 of the 20260920 match -- later
points are emitted UNANCHORED (server + side only) rather than guessed from
the pipeline's own spans, which demonstrably do not map 1:1 onto GT points.

Cross-checks against pipeline_output.json (optional inputs):
- emitted serve ACTIONS inside an anchored window (label 'serve');
- game_on EPISODE overlap (was the point seen at all?).

Outputs JSON + a printed table. Diagnostic only: nothing here feeds the
production pipeline.

Usage:
    python scripts/derive_match_serve_windows.py \
        --gt ground_truth/20260920_match_points.json \
        --anchors ground_truth/gt_point_start_end.txt \
        --fps 25.6702272643995 \
        [--pipeline output/match20260920_e3fix/pipeline_output.json] \
        [--game-state-csv output/match20260920_e3fix/results_game_state.csv] \
        [--out output/far_side_serve_windows.json]
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_MOMENT_RE = re.compile(r"^(\d+):(\d+)\s+point (starts|stops)$")

# Serve-action matching tolerance around an anchored window, frames: the
# serve label is emitted within a few frames of the GT serve moment, and the
# GT moment itself carries +/-15f annotation granularity.
_SERVE_MATCH_TOL = 40

# Flags emitted per point (diagnostic triage, open point 22).
F_UNANCHORED = "UNANCHORED"            # no GT serve-moment anchor (>= point 14)
F_NO_SERVER = "NO_SERVER"              # point 1, server not derivable
F_NO_EPISODE = "NO_EPISODE"            # no game_on episode overlaps the window
F_NO_SERVE = "NO_SERVE"                # no serve action emitted in the window
F_SERVE_TEAM_MISMATCH = "SERVE_TEAM_MISMATCH"  # emitted serve team != derived


# ----------------------------------------------------------------------
# mechanical derivations (pure, unit-tested)
# ----------------------------------------------------------------------

def derive_serve_teams(points: List[Dict[str, Any]]) -> Dict[int, Optional[str]]:
    """Winner of point k-1 serves point k; point 1 stays None.

    Cross-checks against descriptions that name a server. Patterns covered:
    "Team X serves ...", "Team X fails serve ...", "Team X ace", and the
    player form "P<k> fails serve" (the PLAYER's team is taken from the
    side the winner rule demands, so the player form only VALIDATES, it
    never overrides).
    """
    teams: Dict[int, Optional[str]] = {points[0]["point"]: None}
    for prev, cur in zip(points, points[1:]):
        teams[cur["point"]] = prev["winner"]

    server_re = re.compile(
        r"team ([ab]) (?:serves|fails serve)|team ([ab]) ace", re.IGNORECASE)
    for p in points:
        m = server_re.search(p.get("description", ""))
        if not m:
            continue
        named = (m.group(1) or m.group(2)).upper()
        derived = teams[p["point"]]
        if derived is None:
            teams[p["point"]] = named
        elif derived != named:
            raise ValueError(
                f"point {p['point']}: description names server {named} but "
                f"winner-serves rule says {derived}: {p['description']!r}")
    return teams


def derive_sides(points: List[Dict[str, Any]]) -> Dict[int, Dict[str, str]]:
    """Per point, each team's court half ('near'/'far').

    Team A plays the near half at match start; halves swap after every
    point flagged ``side_switch_after``; squads are fixed.
    """
    sides: Dict[int, Dict[str, str]] = {}
    a_far = False
    for p in points:
        k = p["point"]
        sides[k] = {"A": "far" if a_far else "near",
                    "B": "near" if a_far else "far"}
        if p.get("side_switch_after"):
            a_far = not a_far
    return sides


def parse_point_moments(text: str) -> List[Tuple[int, int]]:
    """Parse 'MM:SS point starts' / 'MM:SS point stops' pairs into seconds."""
    moments: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        m = _MOMENT_RE.match(raw.strip())
        if not m:
            continue
        secs = int(m.group(1)) * 60 + int(m.group(2))
        if m.group(3) == "starts":
            if start is not None:
                raise ValueError(f"line {lineno}: 'point starts' before 'stops'")
            start = secs
        else:
            if start is None:
                raise ValueError(f"line {lineno}: 'point stops' before 'starts'")
            moments.append((start, secs))
            start = None
    if start is not None:
        raise ValueError("unterminated 'point starts' at end of file")
    return moments


def build_serve_windows(
    gt: Dict[str, Any],
    anchors_text: str,
    fps: float,
) -> List[Dict[str, Any]]:
    """One record per GT point: derived server, side, anchored window or None."""
    teams = derive_serve_teams(gt["points"])
    sides = derive_sides(gt["points"])
    moments = parse_point_moments(anchors_text)
    if len(moments) > len(gt["points"]):
        raise ValueError(
            f"{len(moments)} anchored windows > {len(gt['points'])} GT points")

    records: List[Dict[str, Any]] = []
    for p in gt["points"]:
        k = p["point"]
        server = teams[k]
        rec: Dict[str, Any] = {
            "point": k,
            "winner": p["winner"],
            "serve_team": server,
            "serve_side": sides[k][server] if server else None,
            "description": p["description"],
            "anchored": k <= len(moments),
            "window_frames": None,
            "serve_frame": None,
            "flags": [],
        }
        if not rec["anchored"]:
            rec["flags"].append(F_UNANCHORED)
        if server is None:
            rec["flags"].append(F_NO_SERVER)
        if k <= len(moments):
            a, b = moments[k - 1]
            rec["serve_frame"] = round(a * fps)
            rec["window_frames"] = [round(a * fps), round(b * fps)]
        records.append(rec)
    return records


# ----------------------------------------------------------------------
# pipeline cross-checks (pure, unit-tested)
# ----------------------------------------------------------------------

def attach_serve_actions(
    records: List[Dict[str, Any]],
    actions: List[Dict[str, Any]],
) -> None:
    """Attach emitted serve actions inside each anchored window.

    A serve emission matches the window if its frame lies within
    [start - tol, end + tol]. Non-anchored records get no matches.
    Sets F_NO_SERVE / F_SERVE_TEAM_MISMATCH accordingly (never on
    unanchored / serverless records).
    """
    serves = [a for a in actions if a.get("action") == "serve"]
    for rec in records:
        if not rec["anchored"]:
            continue
        lo, hi = rec["window_frames"]
        hits = sorted(
            (a for a in serves
             if lo - _SERVE_MATCH_TOL <= a["frame_number"] <= hi + _SERVE_MATCH_TOL),
            key=lambda a: a["frame_number"])
        rec["emitted_serves"] = [
            {"frame": a["frame_number"], "team": a.get("team"),
             "confidence": a.get("confidence")}
            for a in hits]
        if rec["serve_team"] is None:
            continue  # nothing to mismatch against
        if not hits:
            rec["flags"].append(F_NO_SERVE)
        elif all(a.get("team") != rec["serve_team"] for a in hits):
            rec["flags"].append(F_SERVE_TEAM_MISMATCH)


def attach_episode_overlap(
    records: List[Dict[str, Any]],
    game_state_csv: str,
) -> None:
    """Flag anchored windows with NO game_on episode overlapping them."""
    episodes = _episodes_from_csv(game_state_csv)
    for rec in records:
        if not rec["anchored"]:
            continue
        lo, hi = rec["window_frames"]
        if not any(a <= hi and b >= lo for a, b in episodes):
            rec["flags"].append(F_NO_EPISODE)


def _episodes_from_csv(path: str) -> List[Tuple[int, int]]:
    """GAME_ON episode spans (start, end) from the per-frame game-state CSV."""
    episodes: List[Tuple[int, int]] = []
    start: Optional[int] = None
    last_frame = -1
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            frame = int(row["Frame_Index"])
            state = (row.get("Game_State") or "").strip()
            last_frame = frame
            if state == "game_on":
                if start is None:
                    start = frame
            elif start is not None:
                episodes.append((start, frame - 1))
                start = None
    if start is not None:
        episodes.append((start, last_frame))
    return episodes


# ----------------------------------------------------------------------
# report
# ----------------------------------------------------------------------

def summarize(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Side-split coverage over ANCHORED points with a derived server."""
    anchored = [r for r in records if r["anchored"] and r["serve_team"]]
    out: Dict[str, Any] = {}
    for side in ("far", "near"):
        pts = [r for r in anchored if r["serve_side"] == side]
        with_serve = [r for r in pts
                      if any(e.get("team") == r["serve_team"]
                             for e in r.get("emitted_serves", []))]
        out[f"{side}_side"] = {
            "n_points": len(pts),
            "points": [r["point"] for r in pts],
            "n_serve_emitted": len(with_serve),
            "n_serve_missing": len(pts) - len(with_serve),
        }
    out["n_anchored"] = sum(1 for r in records if r["anchored"])
    out["n_unanchored"] = sum(1 for r in records if not r["anchored"])
    return out


def format_table(records: List[Dict[str, Any]]) -> str:
    header = (f"{'pt':>3} {'srv':>3} {'side':>4} {'window':>13} "
              f"{'emitted serves':>22}  flags")
    lines = [header, "-" * len(header)]
    for r in records:
        w = (f"{r['window_frames'][0]}..{r['window_frames'][1]}"
             if r["window_frames"] else "-")
        em = ",".join(f"{e['team']}@{e['frame']}"
                      for e in r.get("emitted_serves", [])) or "-"
        flags = ",".join(r["flags"]) or "-"
        lines.append(f"{r['point']:>3} {str(r['serve_team']):>3} "
                     f"{str(r['serve_side']):>4} {w:>13} {em:>22}  {flags}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gt", required=True, help="match-points-v1 JSON")
    ap.add_argument("--anchors", required=True,
                    help="gt_point_start_end.txt-format anchor file")
    ap.add_argument("--fps", type=float, required=True,
                    help="video fps (pipeline_output.json video.fps)")
    ap.add_argument("--pipeline", help="pipeline_output.json for serve actions")
    ap.add_argument("--game-state-csv", help="results_game_state.csv for episodes")
    ap.add_argument("--out", help="write JSON report here")
    args = ap.parse_args(argv)

    gt = json.loads(Path(args.gt).read_text(encoding="utf-8"))
    if gt.get("format") != "match-points-v1":
        raise SystemExit(f"{args.gt}: unexpected format {gt.get('format')!r}")
    anchors_text = Path(args.anchors).read_text(encoding="utf-8")

    records = build_serve_windows(gt, anchors_text, args.fps)

    if args.pipeline:
        d = json.loads(Path(args.pipeline).read_text(encoding="utf-8"))
        attach_serve_actions(records, d.get("actions") or [])
    if args.game_state_csv:
        attach_episode_overlap(records, args.game_state_csv)

    summary = summarize(records)
    report = {"video": gt.get("video"), "fps": args.fps,
              "summary": summary, "points": records}
    table = format_table(records)
    print(table)
    print()
    print(json.dumps(summary, indent=1))

    if args.out:
        Path(args.out).write_text(
            json.dumps(report, indent=1) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
