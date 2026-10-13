"""A match as the owner reviewed it: the reconstruction with his verdicts applied.

    venv/bin/python -m src.publish.reviewed output/<run_dir>     # what a publish would send

The owner reviews a match rally by rally (``make review``, src/web/review.py)
and his verdicts are in ``ground_truth/<match_key>_review.json``. Owner
decision (2026-10-13): what is PUBLISHED is the match as he left it. This
module is that step, pure: reconstruction + review in, a reconstruction of the
same shape out, so the bundle, the credits and the clips are built from it by
the code that builds them from any reconstruction.

Rules:

* **Only what the owner changed changes.** A point he did not review, or said
  "all right" to, is published as the run reads it. In a corrected point a
  touch he left alone keeps everything the run measured.
* **A reviewed point is his.** It takes the touches (action, player), the
  winner and the near squad of the verdict's ``truth``, also when a later rules
  change makes the run read that rally differently: the run's measurements
  (position, height, attack type) follow a touch only where the run still has
  one at that frame.
* **A touch he added or named is seen:** it is credited like any observed
  touch. It has no position (nothing measured it), so no map draws it.
* **ace / kill / error are derived again** on a point whose end he changed (the
  winner, or one of the last three touches), with the post-run layer's own
  semantics (src/postrun/match.py ``_outcomes``) and without its perception
  guards: he watched the rally. A block that wins the point is a kill; any
  other block has no outcome (owner rule: only a kill block scores).
* **A rally the run cut short** (the owner saw it go on in the dead time:
  ``gaps[].status == "tail"``) has no ace / kill / error at all: its last
  touch on record is not its last touch, and nothing may be charged to it.
* **A point the run missed** is a point without touches: it counts in the
  score, the winner of the point before it serves it.
* ``match_reconstruction.json`` is never written: the pipeline's scores stay
  about the pipeline.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

SLOTS = ("P1A", "P2A", "P1B", "P2B")
ATTACKS = ("spike", "overpass")
#: Actions that can win a point by themselves (a block that ends it is a kill).
WINNERS = ATTACKS + ("block",)
HANDLING = ("set", "dig")
#: A touch of the truth is the run's touch when the run has one this close
#: (the verdict's frames are the run's own unless the rules changed since).
SAME_TOUCH_S = 0.25
#: The outcomes of a point sit on its last three touches (the hit, the dig,
#: the touch that failed): a change there, or to the winner, derives them again.
TAIL = 3
FLAG_ADDED = "owner_added"
GT_ROOT = Path("ground_truth")


def _other(team: Optional[str]) -> Optional[str]:
    return {"A": "B", "B": "A"}.get(team)


# --------------------------------------------------------------------------- #
# one point
# --------------------------------------------------------------------------- #

def _pair(truth: Sequence[Dict[str, Any]], run: Sequence[Dict[str, Any]],
          tolerance: int) -> Dict[int, int]:
    """truth index -> run index: the same frame first, then the nearest run
    touch within ``tolerance`` frames, each run touch used once."""
    out: Dict[int, int] = {}
    used = set()
    for i, t in enumerate(truth):
        for j, r in enumerate(run):
            if j not in used and r["frame"] == t["frame"]:
                out[i] = j
                used.add(j)
                break
    near = sorted((abs(r["frame"] - t["frame"]), i, j)
                  for i, t in enumerate(truth) if i not in out
                  for j, r in enumerate(run) if j not in used
                  and abs(r["frame"] - t["frame"]) <= tolerance)
    for _, i, j in near:
        if i not in out and j not in used:
            out[i] = j
            used.add(j)
    return out


def _new_touch(frame: int) -> Dict[str, Any]:
    return {"frame": int(frame), "action": None, "side": None, "team": None, "player": None,
            "player_source": None, "touch_number": 0, "observed": True, "evidence": "owner",
            "ends_possession": False, "outcome": None, "height_m": None,
            "contact_height_m": None, "contact_ratio": None, "court_x_m": None,
            "court_y_m": None, "court_err_m": None, "reach_body_heights": None,
            "perception_action": None, "spike_type": None, "launch": None}


def _number(touches: List[Dict[str, Any]]) -> None:
    """Touch numbers and who ends a possession, from the teams in order: the
    serve is 0, then 1, 2, 3 while the same team keeps the ball."""
    count, team = 0, None
    for i, t in enumerate(touches):
        if i == 0 and t["action"] == "serve":
            t["touch_number"], team, count = 0, t["team"], 0
        else:
            count = count + 1 if (t["team"] == team and i > 0
                                  and touches[i - 1]["touch_number"] > 0) else 1
            t["touch_number"], team = count, t["team"]
    for i, t in enumerate(touches):
        nxt = touches[i + 1] if i + 1 < len(touches) else None
        t["ends_possession"] = nxt is None or nxt["team"] != t["team"]


def derive_outcomes(touches: List[Dict[str, Any]], winner: Optional[str]) -> None:
    """ace / kill / error on the hit that decided the point (owner semantics,
    as ``postrun.match._outcomes``): the last ball of the winners is a kill; a
    failed FIRST touch credits the hit before it (a serve: an ace); a team's
    own second or third touch that loses the point is its error."""
    for t in touches:
        t["outcome"] = None
    if winner is None or not touches:
        return
    last = touches[-1]
    if last["touch_number"] == 0:
        last["outcome"] = "ace" if last["team"] == winner else "error"
        return
    if last["team"] == winner:
        if last["action"] in WINNERS:
            last["outcome"] = "kill"
        return
    if last["touch_number"] > 1:
        if last["action"] in ATTACKS + HANDLING:
            last["outcome"] = "error"
        return
    if len(touches) < 2:
        return
    before = touches[-2]
    if before["team"] == last["team"]:
        return
    if before["touch_number"] == 0:
        before["outcome"] = "ace"
    elif before["action"] in WINNERS:
        before["outcome"] = "kill"


def _key(t: Dict[str, Any]) -> Tuple[int, Optional[str], Optional[str]]:
    """What decides an outcome about a touch: when, what, which team."""
    return (t["frame"], t["action"], t["team"])


def reviewed_point(point: Dict[str, Any], truth: Dict[str, Any], fps: float
                   ) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """One point with the owner's truth applied, and what changed in it."""
    out = copy.deepcopy(point)
    run = point["touches"]
    changes = {"touches_changed": 0, "touches_added": 0, "touches_removed": 0,
               "winner_changed": 0, "sides_changed": 0}
    near = truth.get("near_team") or point.get("near_team")
    if near != point.get("near_team"):
        changes["sides_changed"] = 1
    flipped = bool(changes["sides_changed"])
    pairs = _pair(truth["touches"], run, max(1, int(round(SAME_TOUCH_S * fps))))
    changes["touches_removed"] = len(run) - len(pairs)

    touches: List[Dict[str, Any]] = []
    for i, want in enumerate(truth["touches"]):
        j = pairs.get(i)
        if j is None:
            t = _new_touch(want["frame"])
            changes["touches_added"] += 1
        else:
            t = copy.deepcopy(run[j])
        if j is not None and (want["action"], want["player"]) != (t["action"], t["player"]):
            changes["touches_changed"] += 1
            t["observed"] = True                       # he saw it and said what it is
        if want["action"] != t["action"]:
            t["spike_type"], t["launch"] = None, None  # measured for another action
        if j is None or want["player"] != t["player"]:
            t["player_source"] = "owner"
        t["action"], t["player"] = want["action"], want["player"]
        if t["player"] in SLOTS:
            t["team"] = t["player"][2]
        elif j is not None and flipped:
            t["team"] = _other(t["team"])
        touches.append(t)
    # A touch nobody is named for takes its team from the rally: the ball stays
    # with a team while it digs and sets, and crosses after an attack or serve.
    for i, t in enumerate(touches):
        if t["team"] is None and i > 0:
            prev = touches[i - 1]
            t["team"] = prev["team"] if prev["action"] in HANDLING else _other(prev["team"])
    for t in touches:
        if t["team"] is not None and near is not None:
            t["side"] = "near" if t["team"] == near else "far"

    winner = truth.get("winner")
    if winner != point.get("winner"):
        changes["winner_changed"] = 1
        out["winner_source"] = "owner"
    if not any(changes.values()):
        return copy.deepcopy(point), changes       # "all right": the run's point, untouched
    if (changes["touches_added"] or changes["touches_removed"]
            or changes["touches_changed"] or flipped):
        _number(touches)
    if (changes["winner_changed"]
            or [_key(t) for t in touches[-TAIL:]] != [_key(t) for t in run[-TAIL:]]):
        derive_outcomes(touches, winner)

    out["touches"] = touches
    out["winner"] = winner
    out["near_team"] = near
    serve = dict(out.get("serve") or {})
    if touches and touches[0]["action"] == "serve":
        first = touches[0]
        serve.update(team=first["team"] or truth.get("serve_team") or serve.get("team"),
                     player=first["player"], player_source=first["player_source"],
                     outcome=first["outcome"], side=first["side"] or serve.get("side"))
    else:
        serve.update(team=truth.get("serve_team") or serve.get("team"))
    out["serve"] = serve
    out["rally"] = {**(out.get("rally") or {}), **_shape(touches, winner)}
    return out, changes


def _shape(touches: List[Dict[str, Any]], winner: Optional[str]) -> Dict[str, int]:
    from ..postrun.reconstruct import rally_shape
    return rally_shape(touches, winner)


def _no_outcomes(point: Dict[str, Any]) -> bool:
    """Take every ace / kill / error off a point (True when there was one)."""
    had = any(t.get("outcome") for t in point["touches"]) or bool(
        (point.get("serve") or {}).get("outcome"))
    for t in point["touches"]:
        t["outcome"] = None
    if point.get("serve"):
        point["serve"]["outcome"] = None
    return had


def missing_point(m: Dict[str, Any], before: Optional[Dict[str, Any]],
                  after: Optional[Dict[str, Any]], fps: float = 30.0) -> Dict[str, Any]:
    """A point the run did not find, as the owner gave it: a winner, no
    touches. It sits at the frame he marked, else right after the point
    before it; the winner of that point serves it."""
    frame = m.get("at_frame")
    if frame is None:
        frame = (before["end_frame"] + 1) if before else 0
    neighbour = before or after or {}
    # The marked frame on the video's clock is not known here: the end of the
    # point before it is close enough for the play-by-play.
    at_s = (before or {}).get("end_time_s")
    at_s = round(frame / fps, 1) if at_s is None else at_s
    return {
        "point": 0, "start_frame": int(frame), "end_frame": int(frame),
        "start_time_s": at_s, "end_time_s": at_s,
        "rally": {"touches": 0, "net_crossings": 0, "duration_s": 0.0},
        "near_team": neighbour.get("near_team"),
        "serve": {"frame": int(frame), "side": None,
                  "team": before.get("winner") if before else None,
                  "player": None, "player_source": None, "outcome": None, "observed": False,
                  "inferred": True, "into_net": False, "confirmed_by": "owner"},
        "end": None, "winner": m.get("winner"), "winner_source": "owner",
        "ball_death_read": {"winner": None, "reason": None},
        "score_after": {"A": 0, "B": 0}, "flags": [FLAG_ADDED], "touches": [],
    }


# --------------------------------------------------------------------------- #
# the match
# --------------------------------------------------------------------------- #

def _player_stats(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The post-run stats over the reviewed points, plus what only a review
    can say: blocks, and the ones that won the point (+1 each, owner rule)."""
    from ..postrun.reconstruct import FANTASY, player_stats
    stats = player_stats(points)
    for pt in points:
        for t in pt["touches"]:
            if t["action"] != "block" or not t["observed"] or t["player"] not in SLOTS:
                continue
            row = stats.setdefault(t["player"], {k: 0 for k in (
                "serves", "aces", "serve_errors", "digs", "sets", "assists", "spikes",
                "overpasses", "kills", "attack_errors", "handling_errors", "fantasy")})
            row["blocks"] = row.get("blocks", 0) + 1
            if t["outcome"] == "kill":
                row["block_kills"] = row.get("block_kills", 0) + 1
                row["fantasy"] = round(row["fantasy"] + FANTASY["kill"], 1)
    extra = stats.pop("_uncredited_observed_touches")
    stats = dict(sorted(stats.items()))
    stats["_uncredited_observed_touches"] = extra
    return stats


def _checks(checks: Dict[str, Any], points: List[Dict[str, Any]],
            renumbered: Dict[int, int], points_to_win: int = 21,
            switch_every: int = 7) -> Dict[str, Any]:
    from ..postrun.reconstruct import longest_rally
    out = dict(checks)
    score = points[-1]["score_after"] if points else {"A": 0, "B": 0}
    switches = [i for i in range(1, len(points))
                if None not in (points[i]["near_team"], points[i - 1]["near_team"])
                and points[i]["near_team"] != points[i - 1]["near_team"]]
    blocks, prev = [], 0
    for i in switches:
        blocks.append(i - prev)
        prev = i
    top, low = max(score.values()), min(score.values())
    out.update({
        "points": len(points), "final_score": dict(score),
        "set_complete": top >= points_to_win and top - low >= 2,
        "undecided_points": [p["point"] for p in points if p["winner"] is None],
        "side_switch_after_point": switches, "points_between_switches": blocks,
        "switch_blocks_ok": all(b == switch_every for b in blocks),
        "flagged_points": {p["point"]: p["flags"] for p in points if p["flags"]},
        "longest_rally": longest_rally(points),
    })
    order = out.get("service_order")
    if isinstance(order, dict):                     # its point numbers moved too
        out["service_order"] = {
            team: ({**row, "order_breaks_before_point": [
                renumbered[n] for n in row.get("order_breaks_before_point") or []
                if n in renumbered]} if isinstance(row, dict) else row)
            for team, row in order.items()}
    return out


def apply_review(recon: Dict[str, Any], review: Optional[Dict[str, Any]]
                 ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """The reconstruction as the owner reviewed it, and a report of what the
    review changed. Without a review the reconstruction is returned as it is."""
    report: Dict[str, Any] = {"applied": False, "points": len(recon.get("points") or [])}
    if not review or not (review.get("points") or review.get("missing_points")):
        return recon, report
    from ..web.review import attach, match_view

    fps = float(recon.get("fps") or 0.0) or 30.0
    view = match_view(recon, None)["points"]
    by_point, orphans = attach(review, view)
    starts = sorted((p["start_frame"], p["point"]) for p in view)

    def after_of(m: Dict[str, Any]) -> int:
        """The current point a missing point follows (0: before the first)."""
        frame = m.get("at_frame", m.get("after_frame") or 0)
        if m.get("at_frame") is None and not m.get("after_frame"):
            return 0
        earlier = [n for s, n in starts if s <= frame]
        return earlier[-1] if earlier else 0

    missing: Dict[int, List[Dict[str, Any]]] = {}
    for m in review.get("missing_points") or []:
        missing.setdefault(after_of(m), []).append(m)
    # Points whose rally goes on after the run ended it: the last one that
    # starts before the stretch of dead time the owner marked.
    cut = set()
    for g in review.get("gaps") or []:
        earlier = [n for s, n in starts if s <= g["first"]]
        if g.get("status") == "tail" and earlier:
            cut.add(earlier[-1])

    points: List[Dict[str, Any]] = []
    renumbered: Dict[int, int] = {}
    totals = {"reviewed": 0, "corrected": 0, "dropped": 0, "added": 0, "run_moved": 0,
              "cut_short": 0,
              "touches_changed": 0, "touches_added": 0, "touches_removed": 0,
              "winner_changed": 0, "sides_changed": 0}

    def add_missing(after: int, nxt: Optional[Dict[str, Any]]) -> None:
        for m in sorted(missing.get(after, []), key=lambda m: m.get("at_frame") or 0):
            points.append(missing_point(m, points[-1] if points else None, nxt, fps))
            totals["added"] += 1

    source = recon.get("points") or []
    add_missing(0, source[0] if source else None)
    for k, pt in enumerate(source):
        verdict = by_point.get(pt["point"])
        if verdict is None:
            points.append(copy.deepcopy(pt))
        else:
            totals["reviewed"] += 1
            totals["run_moved"] += bool(verdict.get("run_changed"))
            truth = verdict["truth"]
            if not truth.get("is_point"):
                totals["dropped"] += 1
                add_missing(pt["point"], source[k + 1] if k + 1 < len(source) else None)
                continue
            new, changes = reviewed_point(pt, truth, fps)
            if any(changes.values()):
                totals["corrected"] += 1
            for name, n in changes.items():
                totals[name] += n
            points.append(new)
        if pt["point"] in cut:
            totals["cut_short"] += 1
            if _no_outcomes(points[-1]):
                totals["corrected"] += verdict is None or not any(changes.values())
        renumbered[pt["point"]] = len(points)
        add_missing(pt["point"], source[k + 1] if k + 1 < len(source) else None)

    report.update(applied=True, orphans=len(orphans),
                  unreviewed=len(source) - totals["reviewed"],
                  score_run=(recon.get("checks") or {}).get("final_score"), **totals)
    if not (totals["corrected"] or totals["dropped"] or totals["added"]):
        # Every reviewed point was right: the match is the run's, byte for byte.
        report["score"] = dict(report["score_run"] or {"A": 0, "B": 0})
        return recon, report

    score = {"A": 0, "B": 0}
    for n, pt in enumerate(points, start=1):
        pt["point"] = n
        if pt["winner"] in score:
            score[pt["winner"]] += 1
        pt["score_after"] = dict(score)

    out = dict(recon)
    out["points"] = points
    out["checks"] = _checks(recon.get("checks") or {}, points, renumbered)
    out["player_stats"] = _player_stats(points)
    report.update(points=len(points), score=dict(score))
    out["review"] = report
    return out, report


# --------------------------------------------------------------------------- #
# on disk
# --------------------------------------------------------------------------- #

def load_review_for(key: str, gt_root: Path = GT_ROOT) -> Optional[Dict[str, Any]]:
    """The owner's review of a match, when there is one."""
    from ..web.review import load_review, review_path
    path = review_path(gt_root, key)
    return load_review(path, key) if path.is_file() else None


def describe(report: Dict[str, Any]) -> str:
    if not report.get("applied"):
        return "owner review: none, published as the run reads it"
    run, now = report.get("score_run") or {}, report["score"]
    parts = [f"owner review applied: {report['reviewed']} points reviewed "
             f"({report['corrected']} corrected, {report['unreviewed']} not reviewed)"]
    for name, text in (("added", "missing points added"), ("dropped", "rallies that were no point"),
                       ("winner_changed", "winners changed"), ("sides_changed", "sides put right"),
                       ("cut_short", "rallies the run cut short (no ace / kill / error on them)"),
                       ("touches_changed", "touches renamed"), ("touches_added", "touches added"),
                       ("touches_removed", "touches removed")):
        if report.get(name):
            parts.append(f"{report[name]} {text}")
    parts.append(f"score A {run.get('A')} – B {run.get('B')} -> A {now['A']} – B {now['B']}")
    if report.get("run_moved"):
        parts.append(f"{report['run_moved']} reviewed points the run now reads differently "
                     f"(the review wins; look again in `make review`)")
    if report.get("orphans"):
        parts.append(f"{report['orphans']} verdicts fit no rally any more (not applied)")
    return "; ".join(parts)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run_dir", help="run directory (output/<match_key>)")
    parser.add_argument("--ground-truth", default=str(GT_ROOT))
    parser.add_argument("--write", action="store_true",
                        help="write match_reviewed.json + .txt next to the reconstruction")
    args = parser.parse_args(argv)
    from ..postrun.reconstruct import format_report

    run_dir = Path(args.run_dir)
    recon = json.loads((run_dir / "match_reconstruction.json").read_text())
    reviewed, report = apply_review(recon, load_review_for(run_dir.name, Path(args.ground_truth)))
    print(describe(report))
    if report.get("applied"):
        before, after = recon.get("player_stats") or {}, reviewed["player_stats"]
        for player in SLOTS:
            a, b = before.get(player) or {}, after.get(player) or {}
            diff = {k: (a.get(k, 0), b.get(k, 0)) for k in sorted(set(a) | set(b))
                    if a.get(k, 0) != b.get(k, 0)}
            print(f"  {player}: " + (", ".join(f"{k} {x} -> {y}" for k, (x, y) in diff.items())
                                     or "unchanged"))
    if args.write and report.get("applied"):
        (run_dir / "match_reviewed.json").write_text(json.dumps(reviewed, indent=1))
        (run_dir / "match_reviewed.txt").write_text(format_report(reviewed))
        print(f"written: {run_dir / 'match_reviewed.json'} (+ .txt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
