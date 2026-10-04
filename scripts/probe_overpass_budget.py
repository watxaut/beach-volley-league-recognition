"""G3 -- the OVERPASS lever, rule replay on MATCHED contacts with honest arithmetic.

Session #76, third step.  Three measurements now bound the overpass question:

1. ``scripts/probe_label_ceilings.py`` -- the PRIZE: relabelling the 13 matched
   GT-overpass contacts lifts the bar arm 0.6131 -> 0.7080, so ONE rule on ONE
   class crosses the 0.70 goal bar on its own.
2. ``scripts/probe_overpass_separator.py`` -- 16 per-contact kinematic
   features (width regime, arrival/departure velocity and direction,
   straightness, depth) plus all 120 two-feature AND-rules: NO LARGE separator
   (best single |delta| 0.413, best pair 0.333), and not one of the 7
   significant pairs is remotely precise enough.
3. The arithmetic here, which is the real story: to clear 0.70 the rule may fire
   on at most ``2k - 12`` matched contacts to recover ``k`` of the 13 (see
   ``precision_budget``). At the best separator that is precision >= 200%,
   i.e. IMPOSSIBLE. **The motion/WIDTH-WITNESS envelope cannot express an
   overpass; the discriminating evidence must be something the dump does not
   currently carry.**

So this probe does NOT hunt for another kinematic threshold (that family is
closed by #76 second step). It does the thing that IS still open and is
actionable: it replays the IMPORTED ``ActionContextResolver`` over the dump's
``candidate_passed_gates`` rows -- which carry exactly what ``_decide`` reads
-- with candidate rules built from the taxonomy the OWNER'S OWN GT wording
defines, and scores each rule on MATCHED contacts with the precision budget
applied.

**The taxonomy is read off the GT, not invented.** The 21 GT overpass events'
``owner_raw`` lines say, in order of frequency: "bump pass" / "bump passes"
(12), the literal word "overpass" (10, overlapping the bumps), "passes the
ball" (3). Their OWNER NOTES make it unambiguous -- "over hand dig -> overpass",
"FT dig and overpasses -> overpass", "bump pass from the back with the two
hands up", "bump passes the ball f24948 into the net and loses point". And the
negative control is clean: across all 189 non-overpass GT events, the words
"overpass" and "bump pass" NEVER appear; the only "over"-lines are 5
"overhand dig" dig events and one bystander note. **In this owner's vocabulary
`overpass` IS `bump pass` -- a bump-set SENT OVER, including the ones that die
in the net** (f24948 is a bump pass that loses the point and is still
``overpass``).

That is not a kinematic cue; it is a CLASSIFICATION problem: the class is
defined by the ball's subsequent trajectory, and the trajectory is exactly what
the perception stream currently throws away after the contact. So the
candidate rules below are all *possession-reframing* rules -- they try to use
next-contact / ball-side / follow evidence to RECLASSIFY a bump_set -- and the
probe's job is to report exactly which of them, if any, is precise enough to
clear the budget.

DIAGNOSE ONLY: no ``src/`` change, no decode, no seek, no GT edit.  Held-out
P9-P33 for scoring; the held-out region is not otherwise touched.

Usage:
    venv/bin/python scripts/probe_overpass_budget.py
    venv/bin/python scripts/probe_overpass_budget.py --json output/g3_overpass/budget.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import evaluate_timed as et  # noqa: E402
import probe_overpass_crossing as oc  # noqa: E402
from src.recognition.action_context import ActionContextResolver  # noqa: E402
from src.recognition.volleyball_actions import VisualGesture, VolleyballAction  # noqa: E402

DEFAULT_GT = "ground_truth/20260920_match_contacts.json"
DEFAULT_DIAG = "output/g3r1/match_bw03_diag.jsonl"
DEFAULT_JSON = "output/g3_overpass/budget.json"

#: The goal bar, and the arm it is defined on (`probe_label_ceilings.py`:
#: 137 matched / 84 correct = 0.6131).  The number of IN-SCOPE GT overpasses
#: that the REPLAY domain actually contains is 16 (``probe_overpass_budget``),
#: not 13: the 13 are those that survive time-matching to an emitted contact,
#: and a rule can only convert a contact that exists.  Using the honest 16
#: makes the budget strictly tighter, so it is the default.
BAR = 0.70
N_MATCHED_BAR_ARM = 137
BASE_CORRECT_BAR_ARM = 84
N_GT_TARGET_REPLAY = 16


# ----------------------------------------------------------------------
# the precision budget -- the arithmetic the whole lever turns on
# ----------------------------------------------------------------------

def precision_budget(n_matched: int, base_correct: int, bar: float = BAR,
                     n_gt_target: int = 13) -> Dict[str, Any]:
    """Max MATCHED contacts the rule may fire on, per k of 13 recovered.

    Derivation (no peeking): the metric counts a relabelled matched contact as
    correct IFF the new label equals the GT label. Overpasses the GT labels
    ``overpass`` are the only net gain; everything else the rule fires on is a
    net loss. With ``k`` recovered and ``m`` fired::

        base + k - (m - k) >= labels_needed  ->  m <= 2k - labels_needed

    so ``m >= k`` always, and any ``k`` below half the requirement is
    infeasible at ANY precision.
    """
    need_labels = math.ceil(bar * n_matched) - base_correct
    out = {
        "n_matched": n_matched, "base_correct": base_correct,
        "labels_needed_for_bar": need_labels,
        "bar": bar, "n_gt_target": n_gt_target,
        "rule": "m <= 2k - labels_needed   (m = fires on matched contacts)",
        "by_k": [],
    }
    for k in range(0, n_gt_target + 1):
        m = 2 * k - need_labels
        out["by_k"].append({
            "k_recovered": k,
            "max_fires": m,
            "precision_floor": round(k / m, 4) if m > 0 else None,
            "feasible": bool(m >= k),
        })
    return out


def levenshtein(a: Sequence[str], b: Sequence[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def emit_distance(name: str, emitted: Sequence[Dict[str, Any]],
                  gt: Sequence[Dict[str, Any]], gt_labels: Sequence[str]
                  ) -> int:
    """Label-sequence edit distance over the MATCHED contacts, in order."""
    g = [str(x) for x in gt_labels]
    return levenshtein([e["action"] for e in emitted], g)


# ----------------------------------------------------------------------
# candidate rules -- all taxonomy-motivated, all replayed on the RESOLVER
# ----------------------------------------------------------------------

def _next(c, nxt, resolver):
    """The next contact, if it is inside the same rally."""
    if nxt is None:
        return None
    if nxt["frame"] - c["frame"] > resolver.rally_reset_gap:
        return None
    return nxt


def rule_bumpset_always(c, nxt, resolved, resolver):
    """R1 (owner-vocabulary upper bound): EVERY bump_set is an overpass.

    Not a shippable rule -- it destroys the dig/set classes -- but it is the
    ceiling of the "bump_set == sent over" reading of the owner's GT, and
    locating it in the budget table bounds what any bump_set-based rule can do.
    """
    if c["gesture"] == VisualGesture.BUMP_SET:
        return VolleyballAction.OVERPASS
    return None


def rule_next_team_any_touch(c, nxt, resolved, resolver):
    """R2: the NEXT contact is the other team, at ANY touch count.

    The GT's overpasses sit at touches 1/2/3 with no count information, so the
    signal has to be the reception -- which is what the owner means by a bump
    "sent over": the other side has to play it.
    """
    n = _next(c, nxt, resolver)
    if n is not None and n.get("team") != c.get("team"):
        return VolleyballAction.OVERPASS
    return None


def rule_next_team_bumpset(c, nxt, resolved, resolver):
    """R3: the next contact is the other team's bump_set.

    Stricter than R2: the reception must itself be a bump, so dig/set receptions
    that continue the rally do not fire.
    """
    n = _next(c, nxt, resolver)
    if (n is not None and n.get("team") != c.get("team")
            and n["gesture"] == VisualGesture.BUMP_SET):
        return VolleyballAction.OVERPASS
    return None


def rule_next_team_no_attack(c, nxt, resolved, resolver):
    """R4: the next contact is the other team and is NOT an attack.

    The GT notes tie overpass to *bump* traffic ("bump pass ... into the net and
    loses point"), so the reception must be a bump-set or block.
    """
    n = _next(c, nxt, resolver)
    if (n is not None and n.get("team") != c.get("team")
            and n["gesture"] != VisualGesture.ATTACK):
        return VolleyballAction.OVERPASS
    return None


def rule_bumpset_no_same_side_follow(c, nxt, resolved, resolver):
    """R5: a bump_set whose ball-side evidence puts the ball back over the net.

    The width regime is the only side signal the stream has (#75 measured it
    side-blind only in the METRE sense; the px width regime itself is the
    production side signal, ~14-28px far / ~30-55px near). The contact is a
    bump_set whose own ball_side is the OTHER team -- i.e. the resolver's
    cross-flip event -- which is the possession-reframing the class needs.
    """
    if (c["gesture"] == VisualGesture.BUMP_SET
            and c.get("ball_side") is not None
            and c.get("ball_side") != c.get("team")):
        return VolleyballAction.OVERPASS
    return None


def rule_bumpset_no_follow(c, nxt, resolved, resolver):
    """R6: a bump_set with no follow at all (the touch-2 production rule,
    extended to every touch count)."""
    if c["gesture"] == VisualGesture.BUMP_SET and _next(c, nxt, resolver) is None:
        return VolleyballAction.OVERPASS
    return None


def rule_bumpset_next_team_bumpset_no_baseline(c, nxt, resolved, resolver):
    """R7: R3 minus serve-zone contacts (a serve's follow is never a cross)."""
    if c.get("behind_baseline") and resolved.get("new_possession"):
        return None
    return rule_next_team_bumpset(c, nxt, resolved, resolver)


RULES = {
    "R1_bumpset_always(ceiling)": rule_bumpset_always,
    "R2_next_team_any_touch": rule_next_team_any_touch,
    "R3_next_team_bumpset": rule_next_team_bumpset,
    "R4_next_team_no_attack": rule_next_team_no_attack,
    "R5_bumpset_ball_side_other": rule_bumpset_no_same_side_follow,
    "R6_bumpset_no_follow": rule_bumpset_no_follow,
    "R7_R3_minus_serve_zone": rule_bumpset_next_team_bumpset_no_baseline,
}

#: ``replay_resolver`` in ``probe_overpass_crossing`` already applies a rule
#: only when the resolver did NOT itself emit ``overpass``; that is the right
#: semantics (an existing overpass emission is not the rule's business).
_replay = oc.replay_resolver


# ----------------------------------------------------------------------
# scoring on matched contacts
# ----------------------------------------------------------------------

def gt_scope(gt_path: str, from_point: int, to_point: int) -> List[Dict[str, Any]]:
    blob = json.loads(Path(gt_path).read_text(encoding="utf-8"))
    ev = (blob.get("annotated_frames") or {}).get("actions", {}).get("events") or []
    return [e for e in ev if e.get("frame") is not None
            and from_point <= int(e.get("point") or 0) <= to_point]


def gt_events(gt: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """GT in the shape ``evaluate_timed`` wants (``raw`` carries the tolerance)."""
    out = []
    for e in gt:
        out.append({
            "frame": int(e["frame"]),
            "action": e.get("final_action") or e.get("action"),
            "team": e.get("player_team"),
            "player_id": e.get("player_id"),
            "raw": dict(e, frame_tolerance=e.get("frame_tolerance", 15)),
        })
    return out


def score_arm(emitted: Sequence[Dict[str, Any]], gt: Sequence[Dict[str, Any]],
              fps: float, tolerance_s: float = 0.2) -> Dict[str, Any]:
    """Score one arm through the IMPORTED matcher and report the lever's
    own arithmetic: how many of the rule's fires landed on a GT overpass."""
    tb = et.TimeBase(fps=fps)
    matches = et.match_events(gt_events(gt),
                              [et.normalize_event(e) for e in emitted],
                              tb, base_tolerance_s=tolerance_s)
    labels = et.score_labels(matches)
    contacts = et.score_contacts(matches)
    gt_by_frame = {int(e["frame"]): (e.get("final_action") or e.get("action"))
                   for e in gt}
    fires = 0
    fire_hits = 0
    for _g, p, _d in matches["pairs"]:
        if p["action"] == VolleyballAction.OVERPASS.value:
            fires += 1
            if gt_by_frame.get(int(p["frame"])) == "overpass":
                fire_hits += 1
    correct = sum(1 for g, p, _d in matches["pairs"]
                  if g["action"] is not None and p["action"] == g["action"])
    correct = sum(1 for g, p, _d in matches["pairs"]
                  if g["action"] is not None and p["action"] == g["action"])
    return {
        "n_pred": len(emitted),
        "n_matched": labels["class_scored"],
        "correct": correct,
        "class_accuracy": labels["class_accuracy"],
        "contact_f1": contacts["f1"],
        "overpass_fires_on_matched": fires,
        "fires_on_gt_overpass": fire_hits,
        "emit_distance": None,
        "confusion": labels["confusion_matrix"],
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gt", default=DEFAULT_GT)
    ap.add_argument("--diag", default=DEFAULT_DIAG)
    ap.add_argument("--from-point", type=int, default=9)
    ap.add_argument("--to-point", type=int, default=33)
    ap.add_argument("--json", default=DEFAULT_JSON)
    args = ap.parse_args(argv)

    gt = gt_scope(args.gt, args.from_point, args.to_point)
    fps = float(json.loads(Path(args.gt).read_text(encoding="utf-8")).get("fps") or 30.0)
    raw = oc.load_raw_contacts(args.diag)
    if not raw:
        raise SystemExit(f"Error: no candidate_passed_gates rows in {args.diag}")

    budget = precision_budget(N_MATCHED_BAR_ARM, BASE_CORRECT_BAR_ARM,
                              n_gt_target=N_GT_TARGET_REPLAY)
    gt_seq = [(e["frame"], e.get("final_action") or e.get("action")) for e in gt]

    arms = {"baseline": _replay(raw)}
    for name, rule in RULES.items():
        arms[name] = _replay(raw, rule)

    results: Dict[str, Any] = {}
    for name, emitted in arms.items():
        s = score_arm(emitted, gt, fps)
        s["emit_distance"] = emit_distance(name, emitted, gt,
                                            [lbl for _f, lbl in gt_seq])
        results[name] = s

    out = {
        "generated_from": {"gt": args.gt, "diag": args.diag},
        "scope": {"from_point": args.from_point, "to_point": args.to_point,
                  "n_gt": len(gt)},
        "n_raw_contacts": len(raw),
        "precision_budget": budget,
        "arms": results,
    }
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")

    print("=" * 78)
    print("  OVERPASS PRECISION BUDGET + RULE REPLAY  (held-out P9-P33)")
    print("=" * 78)
    b = results["baseline"]
    print(f"  baseline replay: matched {b['n_matched']}  correct {b['correct']}  "
          f"class_acc {b['class_accuracy']:.4f}  F1 {b['contact_f1']:.4f}")
    print()
    print("  PRECISION BUDGET  (bar arm: 137 matched, 84 correct, bar 0.70)")
    print(f"    needs +{budget['labels_needed_for_bar']} correct labels; "
          f"{budget['rule']}")
    for r in budget["by_k"]:
        if r["k_recovered"] < 10:
            continue
        pf = r["precision_floor"]
        print(f"      recover {r['k_recovered']:>2}/{N_GT_TARGET_REPLAY} -> rule may "
              f"fire on at most {r['max_fires']:>3} matched  (precision floor "
              f"{'n/a' if pf is None else format(pf * 100, '.0f') + '%'})"
              f"{'' if r['feasible'] else '   <- INFEASIBLE at any precision'}")
    print()
    print("  RULE REPLAY (rule fires only where the resolver did not emit overpass)")
    print(f"    {'rule':<34}{'matched':>8}{'correct':>9}{'cls_acc':>9}"
          f"{'fires':>7}{'hits':>6}{'dist':>6}")
    for name, s in results.items():
        print(f"    {name:<34}{s['n_matched']:>8}{s['correct']:>9}"
              f"{s['class_accuracy']:>9.4f}"
              f"{s['overpass_fires_on_matched']:>7}"
              f"{s['fires_on_gt_overpass']:>6}{s['emit_distance']:>6}")
    print("=" * 78)
    print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
