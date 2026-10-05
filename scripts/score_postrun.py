#!/usr/bin/env python3
"""Score a post-run reconstruction against the owner's match GT.

    venv/bin/python scripts/score_postrun.py \
        output/postrun/20260920_match/match_reconstruction.json

Reports, for ``src.postrun``'s output AND for the raw perception stream of
the same run (the baseline it has to beat):

* points   -- reconstructed vs GT points (1:1 by overlap), false and missed;
* serves   -- serving half, serving squad, contact frame within the GT's
              +-15 f tolerance;
* winners  -- per point, plus the final score;
* touches  -- precision / recall at +-15 f, then action, half and squad
              accuracy over the matched ones;
* rules    -- how many touches break the owner's rules (same player twice in
              a row, a touch on the half the ball is not in, a 4th touch).

GT frames are coarse (owner estimates, +-10-15 f): a miss by a few frames
over the tolerance is not necessarily a wrong contact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

TOLERANCE = 15
GT_CONTACTS = "ground_truth/20260920_match_contacts.json"
GT_POINTS = "ground_truth/20260920_match_points.json"


def load_gt(contacts_path: str, points_path: str) -> List[Dict[str, Any]]:
    with open(contacts_path) as f:
        contacts = json.load(f)
    with open(points_path) as f:
        winners = {p["point"]: p for p in json.load(f)["points"]}
    out = []
    for p in contacts["points"]:
        cs = p["contacts"]
        out.append({
            "point": p["point"],
            "start": cs[0]["match_frame"],
            "end": cs[-1]["match_frame"],
            "serve_side": cs[0]["side"],
            "serve_team": cs[0]["team"],
            "winner": winners[p["point"]]["winner"],
            "score_after": winners[p["point"]]["score_after"],
            "touches": [{"frame": c["match_frame"], "action": c["action"],
                         "side": c["side"], "team": c["team"]} for c in cs[1:]],
        })
    return out


def match_points(recon: List[Dict[str, Any]], gt: List[Dict[str, Any]],
                 slack: int = 45) -> Dict[int, int]:
    """recon index -> gt index, 1:1, by span overlap (largest first)."""
    pairs = []
    for i, r in enumerate(recon):
        for j, g in enumerate(gt):
            lo = max(r["start_frame"], g["start"] - slack)
            hi = min(r["end_frame"] + slack, g["end"] + slack)
            if hi >= lo:
                pairs.append((hi - lo, i, j))
    pairs.sort(reverse=True)
    out: Dict[int, int] = {}
    used = set()
    for _, i, j in pairs:
        if i in out or j in used:
            continue
        out[i] = j
        used.add(j)
    return out


def match_touches(pred: List[Dict[str, Any]], gt: List[Dict[str, Any]],
                  tolerance: int = TOLERANCE) -> List[Tuple[int, int]]:
    """Greedy 1:1 by frame distance."""
    pairs = sorted((abs(p["frame"] - g["frame"]), i, j)
                   for i, p in enumerate(pred) for j, g in enumerate(gt)
                   if abs(p["frame"] - g["frame"]) <= tolerance)
    used_p, used_g, out = set(), set(), []
    for _, i, j in pairs:
        if i in used_p or j in used_g:
            continue
        used_p.add(i)
        used_g.add(j)
        out.append((i, j))
    return out


def touch_scores(pred: List[Dict[str, Any]], gt: List[Dict[str, Any]]
                 ) -> Dict[str, Any]:
    matched = match_touches(pred, gt)
    labelled = [(i, j) for i, j in matched if gt[j]["action"] is not None]
    return {
        "pred": len(pred), "gt": len(gt), "matched": len(matched),
        "action_ok": sum(pred[i]["action"] == gt[j]["action"] for i, j in labelled),
        "action_n": len(labelled),
        "side_ok": sum(pred[i].get("side") == gt[j]["side"] for i, j in matched),
        "team_ok": sum(pred[i].get("team") == gt[j]["team"] for i, j in matched),
        "team_n": sum(pred[i].get("team") is not None for i, j in matched),
    }


def rule_violations(touches: List[Dict[str, Any]]) -> Dict[str, int]:
    """Owner rules over one point's touch list (serve first)."""
    same_player = wrong_half = fourth = 0
    run_side, run_len = None, 0
    for prev, cur in zip(touches, touches[1:]):
        if (prev.get("player") and prev.get("player") == cur.get("player")
                and prev.get("side") == cur.get("side")):
            same_player += 1
    for t in touches[1:]:
        if t.get("side") == run_side:
            run_len += 1
        else:
            run_side, run_len = t.get("side"), 1
        if run_len > 3:
            fourth += 1
    if len(touches) > 1 and touches[1].get("side") == touches[0].get("side"):
        wrong_half += 1          # the serve's first touch belongs to the receivers
    return {"same_player_twice": same_player, "fourth_touch": fourth,
            "reception_on_serving_half": wrong_half}


def _add(total: Dict[str, int], part: Dict[str, int]) -> None:
    for k, v in part.items():
        total[k] = total.get(k, 0) + v


def score_reconstruction(recon: Dict[str, Any], gt: List[Dict[str, Any]],
                         credited_only: bool = False) -> Dict[str, Any]:
    points = recon["points"]
    pairing = match_points(points, gt)
    totals: Dict[str, int] = {}
    rules: Dict[str, int] = {}
    serve = {"n": 0, "side_ok": 0, "team_ok": 0, "frame_ok": 0, "frame_err": []}
    winners = {"n": 0, "ok": 0, "undecided": 0, "wrong": []}
    rows = []
    for i, r in enumerate(points):
        touches = [t for t in r["touches"] if t["touch_number"] > 0 and t["observed"]]
        if credited_only:
            touches = [t for t in touches if t.get("player")]
        _add(rules, rule_violations(r["touches"]))
        j = pairing.get(i)
        if j is None:
            _add(totals, {"pred": len(touches), "false_point_touches": len(touches)})
            rows.append({"recon": r["point"], "gt": None})
            continue
        g = gt[j]
        ts = touch_scores(touches, g["touches"])
        _add(totals, ts)
        serve["n"] += 1
        serve["side_ok"] += r["serve"]["side"] == g["serve_side"]
        serve["team_ok"] += r["serve"]["team"] == g["serve_team"]
        err = r["serve"]["frame"] - g["start"]
        serve["frame_ok"] += abs(err) <= TOLERANCE
        serve["frame_err"].append((g["point"], err))
        winners["n"] += 1
        if r["winner"] is None:
            winners["undecided"] += 1
        elif r["winner"] == g["winner"]:
            winners["ok"] += 1
        else:
            winners["wrong"].append(g["point"])
        rows.append({"recon": r["point"], "gt": g["point"], **ts,
                     "winner": r["winner"], "gt_winner": g["winner"]})
    missed = [g["point"] for j, g in enumerate(gt) if j not in pairing.values()]
    for j, g in enumerate(gt):
        if j not in pairing.values():
            _add(totals, {"gt": len(g["touches"])})
    return {
        "points": {"recon": len(points), "gt": len(gt), "matched": len(pairing),
                   "false": len(points) - len(pairing), "missed": missed},
        "serve": serve, "winners": winners, "touches": totals, "rules": rules,
        "final_score": recon["checks"]["final_score"], "rows": rows,
    }


def perception_as_points(pipeline: Dict[str, Any], gt: List[Dict[str, Any]],
                         slack: int = TOLERANCE) -> Dict[str, Any]:
    """The causal stream folded onto the GT point windows (its own point
    layer has no serve/winner), so touches can be compared like for like.
    Actions outside every GT window are its dead-time false positives."""
    side = {"A": "near", "B": "far"}
    actions = sorted(pipeline.get("actions", []), key=lambda a: a["frame_number"])
    totals: Dict[str, int] = {}
    rules: Dict[str, int] = {}
    inside = 0
    for g in gt:
        window = [a for a in actions
                  if g["start"] - slack <= a["frame_number"] <= g["end"] + slack]
        inside += len(window)
        pred = [{"frame": a["frame_number"], "action": a["action"],
                 "side": side.get(a.get("team")), "team": None,
                 "player": a.get("player_label") or a.get("track_id")}
                for a in window]
        serve_like = [p for p in pred if abs(p["frame"] - g["start"]) <= slack
                      and p["action"] == "serve"]
        body = [p for p in pred if p not in serve_like[:1]]
        _add(totals, touch_scores(body, g["touches"]))
        _add(rules, rule_violations(
            [{"side": g["serve_side"], "player": None}] + body))
    _add(totals, {"pred": len(actions) - inside,
                  "dead_time_actions": len(actions) - inside})
    return {"touches": totals, "rules": rules, "actions": len(actions)}


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} = {a / b:.3f}" if b else f"{a}/0"


def format_report(name: str, s: Dict[str, Any]) -> str:
    t = s["touches"]
    lines = [f"== {name}"]
    if "points" in s:
        p, sv, w = s["points"], s["serve"], s["winners"]
        lines += [
            f"points   recon {p['recon']}  gt {p['gt']}  matched {p['matched']}  "
            f"false {p['false']}  missed {p['missed']}",
            f"serves   half {_pct(sv['side_ok'], sv['n'])}   squad "
            f"{_pct(sv['team_ok'], sv['n'])}   frame+-{TOLERANCE} "
            f"{_pct(sv['frame_ok'], sv['n'])}",
            f"winners  {_pct(w['ok'], w['n'])}   undecided {w['undecided']}   "
            f"wrong {w['wrong']}   final {s['final_score']}",
        ]
    matched, pred, gt = t.get("matched", 0), t.get("pred", 0), t.get("gt", 0)
    lines += [
        f"touches  precision {_pct(matched, pred)}   recall {_pct(matched, gt)}",
        f"         action {_pct(t.get('action_ok', 0), t.get('action_n', 0))}   "
        f"half {_pct(t.get('side_ok', 0), matched)}   squad "
        f"{_pct(t.get('team_ok', 0), t.get('team_n', 0))}",
        f"rules    {s['rules']}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("reconstruction")
    parser.add_argument("--pipeline-output", help="default: next to the reconstruction")
    parser.add_argument("--gt-contacts", default=GT_CONTACTS)
    parser.add_argument("--gt-points", default=GT_POINTS)
    parser.add_argument("--rows", action="store_true", help="print the per-point table")
    parser.add_argument("--json", help="write the full score here")
    args = parser.parse_args()

    gt = load_gt(args.gt_contacts, args.gt_points)
    with open(args.reconstruction) as f:
        recon = json.load(f)
    score = score_reconstruction(recon, gt)
    credited = score_reconstruction(recon, gt, credited_only=True)
    print(format_report("post-run reconstruction (every observed touch)", score))
    ct = credited["touches"]
    print(f"credited to a player: precision "
          f"{_pct(ct.get('matched', 0), ct.get('pred', 0))}   recall "
          f"{_pct(ct.get('matched', 0), ct.get('gt', 0))}")
    out = {"postrun": score, "postrun_credited": credited}
    pipeline_path = Path(args.pipeline_output) if args.pipeline_output else (
        Path(args.reconstruction).parent / "pipeline_output.json")
    if pipeline_path.exists():
        with open(pipeline_path) as f:
            baseline = perception_as_points(json.load(f), gt)
        print(format_report(f"perception stream ({baseline['actions']} actions)", baseline))
        out["perception"] = baseline
    if args.rows:
        for row in score["rows"]:
            print(row)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
