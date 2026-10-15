"""What the owner corrects on the review page (`make review`), by root cause.

Reads every ``ground_truth/<match_key>_review.json`` (match-review-v1) and
counts the owner's edits, grouped by the post-run read that made them
necessary, so a change can be judged by the review time it saves (edits per
match) and not only by the GT scores. Joins the run's CURRENT reconstruction
by frame for touch metadata; a verdict given on an older run still counts as
it was given.

    venv/bin/python scripts/review_corrections.py [--match <substring>] [--points]
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
NET_Y_M = 8.0          # the net line in court_y_m (the 16 m court's middle)


def _team(player: Optional[str]) -> Optional[str]:
    return player[-1] if player and player.startswith("P") else None


def classify(point: Dict[str, Any], recon_touches: Dict[int, Dict[str, Any]]) -> List[str]:
    """One cause label per owner edit of a reviewed point."""
    out: List[str] = []
    run = point["run"]["touches"]
    frames = [t[0] for t in run]
    by_frame = {t[0]: (t[1], t[2]) for t in run}
    last = frames[-1] if frames else -1
    for name, on in (point.get("labels") or {}).items():
        if on:
            out.append(f"identity: {name}")
    out += ["identity: named an unnamed body"] * len(point.get("names") or {})
    if point.get("winner"):
        out.append("winner wrong")
    if point.get("not_a_point"):
        out.append("not a point")
    for key, fix in (point.get("touches") or {}).items():
        frame = int(key)
        action, player = by_frame.get(frame, (None, None))
        meta = recon_touches.get(frame, {})
        if fix.get("remove"):
            if action == "dig" and player is None and frame == last:
                out.append("remove: phantom last dig (nobody at the ball)")
            elif action == "overpass" and meta.get("court_y_m") == NET_Y_M:
                out.append("remove: overpass read at the net (ball into the net / block)")
            elif action == "serve":
                out.append("remove: serve on the wrong frame")
            else:
                out.append(f"remove: {action}")
            continue
        if "action" in fix and fix["action"] != action:
            if action == "overpass":
                out.append(f"action: overpass -> {fix['action']}")
            elif fix["action"] == "overpass":
                out.append(f"action: {action} -> overpass")
            else:
                out.append(f"action: {action} -> {fix['action']}")
        if "player" in fix and fix["player"] != player:
            if action == "serve" or fix.get("action") == "serve":
                src = meta.get("player_source")
                out.append(f"server: {'service order' if src == 'service_order' else 'read'} wrong")
            elif player and player.startswith("T"):
                out.append("identity: unnamed body (T#) named per touch")
            elif player is None:
                out.append("credit: uncredited touch named")
            elif fix["player"] is None:
                out.append("credit: credited touch un-named")
            elif _team(player) != _team(fix["player"]):
                out.append("player: other team (touch on the wrong half)")
            else:
                out.append("player: teammate")
    for added in point.get("added") or []:
        where = ("after the run's last touch" if added["frame"] > last
                 else "before the serve" if frames and added["frame"] < frames[0] else "inside")
        out.append(f"add: {added.get('action')} {where}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--match", default="", help="only review files whose key contains this")
    ap.add_argument("--points", action="store_true", help="list every corrected point")
    args = ap.parse_args()

    per: Dict[str, collections.Counter] = {}
    for path in sorted(glob.glob(str(ROOT / "ground_truth" / "*_review.json"))):
        review = json.loads(Path(path).read_text())
        key = review["match_key"]
        if args.match not in key:
            continue
        recon_path = ROOT / "output" / key / "match_reconstruction.json"
        recon = json.loads(recon_path.read_text()) if recon_path.is_file() else {"points": []}
        touches = {t["frame"]: t for p in recon["points"] for t in p["touches"]}
        c = collections.Counter()
        c["#points reviewed"] = len(review["points"])
        for point in review["points"]:
            causes = classify(point, touches)
            c["#points corrected"] += bool(causes) or point.get("status") == "corrected"
            c.update(causes)
            if args.points and causes:
                print(f"{key[:13]} P{point['run']['point']}: " + "; ".join(causes))
        c["missing point"] += len(review.get("missing_points") or [])
        c["rally cut short (gap tail)"] += sum(
            1 for g in review.get("gaps") or [] if g.get("status") == "tail")
        per[key] = c

    if not per:
        raise SystemExit("no review file matched")
    total = sum(per.values(), collections.Counter())
    edits = {k: sum(v for n, v in c.items() if not n.startswith("#")) for k, c in per.items()}
    cols = list(per)
    print(f"{'':58s}" + "".join(f"{k[:13]:>14s}" for k in cols) + f"{'TOTAL':>8s}")
    for name in sorted(total, key=lambda n: (not n.startswith("#"), -total[n], n)):
        print(f"{name[:58]:58s}" + "".join(f"{per[k][name]:14d}" for k in cols) + f"{total[name]:8d}")
    print(f"{'edits':58s}" + "".join(f"{edits[k]:14d}" for k in cols) + f"{sum(edits.values()):8d}")


if __name__ == "__main__":
    main()
