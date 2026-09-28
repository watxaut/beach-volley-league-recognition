#!/usr/bin/env python3
"""Pass-2 serve re-labeling (open point 22, mechanism 3; ratified 2026-09-28).

Two passes over the STREAM, one pass over the video (AGENTS.md section 6):
perception stays the causal single pass through FrameProcessor; this script
is the post-hoc interpretation layer.  It reads the episode->point map
(scripts/map_episodes_to_points.py output, owner-anchored prefix first) and
the pipeline JSON, and re-labels the RALLY-OPENING contact of each TRUE
point window as the serve, by structural prior:

  touch t1  +  dead-ball gap before it  +  window-opening position
  (+ owner anchor / winner-serves side prior for the team)

The gap threshold sits in the MEASURED chasm of the 20260920 match:
serve-position window openers follow 153-1206f of dead time (anchored
prefix: 219-853f or video start), while the largest mid-rally gap anywhere
is 134f.  GAP_SERVE_MIN = 143 is the midpoint; a below-threshold opener
degrades to report_only / anchor_only, never to a wrong serve.

The diagnosis (26th session probe) proved the detector sees every serve and
the losses are the serve-ACTION gate and bump-serve gesture
misclassification -- so the fix is a RE-LABEL of existing actions, never a
re-decode.  Nothing under src/ is touched; entreno neutrality holds by
construction.

Per-point decisions (all carried with evidence in the output JSON):
  emitted      the window opener is already serve-typed (optionally with a
               structural team fix when the emitted toucher team contradicts
               the anchor / winner-serves expectation).
  relabeled    the window opener is a t1 dig/spike/set/overpass after a
               dead-ball gap >= GAP_SERVE_MIN -> re-labeled serve (the
               bump-serve class).  team_resolved = structural expectation,
               team_emitted kept as provenance.
  anchor_only  an owner anchor exists but no adoptable action was emitted
               (the serve-fault / never-gathered class: P5, P7).  The FALSE
               serve-typed actions owner-marked in that window are demoted.
  owner_pinned the owner's round-2 verdicts place a point's serve OUTSIDE
               its DP-inferred window (P20: q5 "serve starts f14500,
               contact just before f14520" -> 14516A, which exists in the
               stream unassigned).  The pinned action is adopted; the
               window opener is NOT re-labeled.  Data, not logic -- see
               OWNER_PINNED_SERVES below.
  report_only  the prior is not clean (P32: a serve-FAULT description
               contradicted by a full post-serve rally in its window;
               sub-threshold gaps).  Never forced.

Demotions (action stays in the stream, flagged not-a-serve):
  - serve-typed actions owner-marked FALSE in the anchors file;
  - serve-typed actions inside owner OFFGAME ranges;
  - serve-typed actions outside every point window are REPORTED (never
    demoted without an owner verdict: 6928A structural, 14516A = the
    owner's q5 verdict for P20 still lacking a structured record).

Measured basis for GAP_SERVE_MIN (20260920 match, all 33 TRUE windows):
serve-position window openers sit 153-1206f after the previous action
(anchored prefix: 219-853f or video start); the largest NON-opening t1 gap
anywhere is 134f (P19 f13758, a mid-rally possession change).  130 sits in
the chasm; a below-threshold opener degrades to report_only, never to a
wrong serve.

Usage:
    python scripts/relabel_serves.py            # defaults below
    python scripts/relabel_serves.py --map ... --pipeline ... --out ...
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from map_episodes_to_points import (
    ANCHOR_EMIT_BEFORE,
    is_serve_fault_description,
    parse_serve_anchors,
)

DEFAULT_MAP = "output/episode_point_map.json"
DEFAULT_PIPELINE = "output/match20260920_posegate/pipeline_output.json"
DEFAULT_ANCHORS = "ground_truth/20260920_match_serve_anchors.txt"
DEFAULT_OUT = "output/serve_relabel.json"

# Measured dead-ball-gap chasm on the 20260920 match (see module docstring):
# serve-position window openers >= 153f, non-opening t1 gaps <= 134f.
GAP_SERVE_MIN = 143

_RELABELABLE = {"dig", "spike", "set", "overpass", "block"}

# Owner round-2 verdicts that pin a serve OUTSIDE its map window.  These
# are DATA (owner dictation, verbatim in the anchors file comments), not
# inferred: P20's q5 verdict ("the serve action starts at f14500 and
# contact happens just before f14520") pins 14516A -- an action that sits
# in no DP-inferred window because ep45's forced burst skewed P20's tail
# alignment (round-3 queue).  A pinned point adopts the pinned action and
# its window opener is never re-labeled on top of it.
OWNER_PINNED_SERVES = {
    20: {"frame": 14516, "team": "A",
         "provenance": "owner round-2 q5 (verbatim in serve anchors file "
                       "comments); ep45/P20 round-3 queue"},
}

_DECISIONS = ("emitted", "relabeled", "owner_pinned", "anchor_only",
              "report_only", "missing")


# ----------------------------------------------------------------------
# pure helpers
# ----------------------------------------------------------------------

def action_frame(a: Dict[str, Any]) -> int:
    return a["frame_number"]


def gap_before(a: Dict[str, Any], prev: Optional[Dict[str, Any]]) -> Optional[int]:
    """Frames since the previous action of ANY kind (None = video start)."""
    if prev is None:
        return None
    return action_frame(a) - action_frame(prev)


def in_ranges(f: int, ranges: List[Dict[str, int]]) -> bool:
    return any(r["start"] <= f <= r["end"] for r in ranges)


def contact_half(contact_point: Optional[List[float]],
                 midcourt: Optional[List[List[float]]]) -> Optional[str]:
    """Which half the contact point projects onto (EVIDENCE ONLY).

    The long-axis camera's airborne bias (AGENTS.md section 5) makes a
    far-half read ambiguous (far ground OR airborne near), so this is never
    scored -- reported alongside each decision.
    """
    if contact_point is None or not midcourt:
        return None
    (x1, y1), (x2, y2) = midcourt[0], midcourt[1]
    x, _ = contact_point[0], contact_point[1]
    t = (x - x1) / (x2 - x1)
    line_y = y1 + t * (y2 - y1)
    return "near" if contact_point[1] > line_y else "far"


def window_actions(actions: List[Dict[str, Any]],
                   window: List[int]) -> List[Dict[str, Any]]:
    w0, w1 = window
    return sorted((a for a in actions if w0 <= action_frame(a) <= w1),
                  key=action_frame)


def owner_marked_frames(anchors: Dict[str, Any],
                        false_candidates: List[Dict[str, Any]]) -> set:
    """Frames the owner (or the ratified map, owner-backed) marked FALSE.

    Two sources: exact FALSE records in the anchors file (1039, 2414,
    5130) and the map's false_serve_candidates whose note references an
    owner FALSE mark (2414, and f3650 covering 3595A + 3856B).  Purely
    structural map candidates (6928: inside the span, outside the anchored
    emission window, no owner verdict) are NOT included -- they stay
    report-only.
    """
    frames = {f["frame"] for f in anchors["false"]}
    for c in false_candidates:
        if c.get("note", "").startswith("near owner FALSE mark"):
            frames.add(c["frame"])
    return frames


def resolve_point(pv: Dict[str, Any],
                  actions: List[Dict[str, Any]],
                  gaps: Dict[int, Optional[int]],
                  anchors: Dict[str, Any],
                  midcourt: Optional[List[List[float]]],
                  owner_marked: set,
                 ) -> Dict[str, Any]:
    """Decide one point's serve from its TRUE window (pure).

    Returns a resolution record; `decision` is one of _DECISIONS.
    """
    k = pv["point"]
    anchor = anchors["points"].get(k)
    window = pv.get("window_frames")
    expected = pv.get("expected_serve_letter")
    rec: Dict[str, Any] = {
        "point": k,
        "expected_serve_letter": expected,
        "serve_side_near_far": pv.get("serve_side_near_far"),
        "window_frames": window,
        "attribution": pv.get("attribution"),
        "anchor_frame": anchor["frame"] if anchor else None,
        "decision": None,
        "serve": None,
        "report": [],
    }
    if window is None:
        rec["decision"] = "missing"
        rec["report"].append("starved point: no TRUE window")
        return rec

    # Owner-pinned points adopt the pinned stream action; the window is
    # never re-labeled on top of an owner verdict.
    pin = OWNER_PINNED_SERVES.get(k)
    if pin is not None:
        pinned = next((a for a in actions
                       if action_frame(a) == pin["frame"]), None)
        if pinned is not None and pinned["action"] == "serve":
            rec["decision"] = "owner_pinned"
            rec["serve"] = {
                "frame": pin["frame"], "source": "owner_pinned",
                "action_original": "serve",
                "team_emitted": pinned["team"],
                "team_resolved": expected or pinned["team"],
                "team_overridden": (expected is not None
                                    and pinned["team"] != expected),
                "provenance": pin["provenance"],
            }
        else:
            rec["decision"] = "report_only"
            rec["report"].append(
                f"owner pin f{pin['frame']} not a serve-typed action")
        rec["report"].append(
            "window opener not adopted: owner pins this point's serve "
            f"at f{pin['frame']} (outside the DP-inferred window)")
        return rec

    acts = window_actions(actions, window)
    excluded = []
    for a in acts:
        why = []
        if action_frame(a) in owner_marked:
            why.append("owner FALSE mark")
        if in_ranges(action_frame(a), anchors["offgame"]):
            why.append("owner OFFGAME range")
        if why:
            excluded.append({"frame": action_frame(a), "action": a["action"],
                             "team": a["team"], "because": "; ".join(why)})
    live = [a for a in acts if not any(
        e["frame"] == action_frame(a) for e in excluded)]

    opener = live[0] if live else None
    ev: Dict[str, Any] = {}
    if opener is not None:
        ev = {
            "frame": action_frame(opener),
            "action": opener["action"],
            "team_emitted": opener["team"],
            "touch_number": opener.get("touch_number"),
            "gap_before": gaps.get(action_frame(opener)),
            "d_anchor": (action_frame(opener) - anchor["frame"]) if anchor else None,
            "contact_half": contact_half(opener.get("contact_point"), midcourt),
            "is_t1": opener.get("touch_number") == 1,
        }
        rec["opener_evidence"] = ev

    def _serve_record(source: str, a: Dict[str, Any]) -> Dict[str, Any]:
        team_resolved = expected or a["team"]
        return {
            "frame": action_frame(a),
            "source": source,
            "action_original": a["action"],
            "gesture": a.get("gesture"),
            "team_emitted": a["team"],
            "team_resolved": team_resolved,
            "team_overridden": expected is not None and a["team"] != expected,
            "gap_before": gaps.get(action_frame(a)),
            "contact_half": contact_half(a.get("contact_point"), midcourt),
        }

    if opener is None:
        if anchor:
            rec["decision"] = "anchor_only"
            rec["serve"] = {
                "frame": anchor["frame"], "source": "anchor_only",
                "note": "owner anchor with no emitted action; the serve was "
                        "never emitted (fault / never gathered)",
            }
        else:
            rec["decision"] = "missing"
        rec["excluded"] = excluded
        return rec

    gap = ev["gap_before"]
    verdict = (anchor or {}).get("verdict")
    owner_saw_emission = verdict in ("TRACKED", "MISCLASSIFIED")
    reject = None
    if not ev["is_t1"]:
        reject = f"window opener f{ev['frame']} is t{ev['touch_number']}, not t1"
    elif (gap is not None and gap < GAP_SERVE_MIN
          and not (owner_saw_emission and anchor is not None
                   and abs(ev["d_anchor"]) <= ANCHOR_EMIT_BEFORE)):
        # An owner TRACKED/MISCLASSIFIED verdict at the anchor outranks the
        # gap chasm: the owner SAW the emission (e.g. a serve right after a
        # false one).  Without that verdict the gap veto stands.
        reject = (f"window opener f{ev['frame']} gap {gap} < {GAP_SERVE_MIN} "
                  f"(no dead-ball gap)")
    elif (opener["action"] not in _RELABELABLE
          and opener["action"] != "serve"):
        reject = (f"window opener f{ev['frame']} unexpected action "
                  f"{opener['action']!r}")
    if reject is not None:
        # An owner anchor outranks a rejected opener: the owner SAW the
        # serve moment and no action was emitted there (P7's walk-to-line
        # dig before the real contact).
        rec["decision"] = "anchor_only" if anchor else "report_only"
        rec["report"].append(reject)
        if anchor and rec["decision"] == "anchor_only":
            rec["serve"] = {
                "frame": anchor["frame"], "source": "anchor_only",
                "note": "owner anchor; the opener failed the structural "
                        "prior and no action exists at the anchor",
            }
        rec["excluded"] = excluded
        return rec

    if opener["action"] == "serve":
        rec["decision"] = "emitted"
        rec["serve"] = _serve_record("emitted", opener)
    elif (is_serve_fault_description(pv.get("description", ""))
          and len(live) > 1 and not owner_saw_emission):
        # A serve-fault point must have no post-serve rally; a full action
        # chain after the opener contradicts the GT description (P32 class)
        # -- never force the re-label.
        rec["decision"] = "report_only"
        rec["report"].append(
            f"serve-fault description but {len(live) - 1} post-opener "
            f"actions in window and no owner emission verdict "
            f"(P32-class contradiction; round 3)")
        rec["excluded"] = excluded
        return rec
    else:
        rec["decision"] = "relabeled"
        rec["serve"] = _serve_record("relabeled", opener)
        rec["report"].append(
            f"bump-serve class: {opener['action']}@{ev['frame']} re-labeled "
            f"serve (t1, gap {gap})")
    rec["excluded"] = excluded
    return rec


def find_demotions(actions: List[Dict[str, Any]],
                   anchors: Dict[str, Any],
                   owner_marked: set) -> List[Dict[str, Any]]:
    """Serve-typed actions that are NOT serves (flagged, stream untouched)."""
    owner_false = {f["frame"]: f["note"] for f in anchors["false"]}
    map_notes = {}
    out = []
    for a in actions:
        if a["action"] != "serve":
            continue
        f = action_frame(a)
        if f in owner_false:
            out.append({"frame": f, "team": a["team"],
                        "because": "owner FALSE record", "note": owner_false[f]})
        elif f in owner_marked:
            out.append({"frame": f, "team": a["team"],
                        "because": "owner FALSE mark (map-adjudicated)",
                        "note": "covered by an owner FALSE record "
                                "(see false_serve_candidates)"})
        elif in_ranges(f, anchors["offgame"]):
            note = next((r.get("note", "") for r in anchors["offgame"]
                         if r["start"] <= f <= r["end"]), "")
            out.append({"frame": f, "team": a["team"],
                        "because": "owner OFFGAME range", "note": note})
    return sorted(out, key=lambda d: d["frame"])


def outside_window_serves(actions: List[Dict[str, Any]],
                          windows: List[List[int]]) -> List[Dict[str, Any]]:
    """Serve-typed actions in no point window: FP candidates or unassigned
    owner verdicts (6928A / 14516A class) -- reported, never auto-demoted."""
    out = []
    for a in actions:
        if a["action"] != "serve":
            continue
        f = action_frame(a)
        if not any(w[0] <= f <= w[1] for w in windows):
            out.append({"frame": f, "team": a["team"]})
    return out


def census(resolutions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Prefix + whole-match serve resolution census (the point-22 gates)."""
    anchored = [r for r in resolutions if r["attribution"] == "anchored"]
    out: Dict[str, Any] = {}
    for side_key in ("near", "far"):
        pts = [r for r in anchored if r["serve_side_near_far"] == side_key]
        resolved = [r for r in pts if r["serve"]
                    and r["serve"].get("team_resolved") == r["expected_serve_letter"]]
        out[side_key] = {
            "n_points": len(pts),
            "points": [r["point"] for r in pts],
            "n_resolved_side_match": len(resolved),
            "resolved_points": [r["point"] for r in resolved],
            "by_decision": {
                d: [r["point"] for r in pts if r["decision"] == d]
                for d in _DECISIONS
            },
        }
    out["all_points"] = {
        "n": len(resolutions),
        "n_with_serve": sum(1 for r in resolutions if r["serve"]),
        "decisions": {
            d: [r["point"] for r in resolutions if r["decision"] == d]
            for d in _DECISIONS
        },
    }
    return out


def prefix_census_before(map_points: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The pre-pass-2 census, scoped to the ANCHORED PREFIX (the gate's
    '2/8' baseline: far prefix points whose window held an emitted,
    side-matching serve action -- P13, P15)."""
    out: Dict[str, Any] = {}
    anchored = [p for p in map_points if p.get("attribution") == "anchored"]
    for side_key in ("near", "far"):
        pts = [p for p in anchored if p.get("serve_side_near_far") == side_key]
        out[side_key] = {
            "n_window": len(pts),
            "n_side_match": sum(1 for p in pts if p.get("serve_side_match")),
        }
    return out


def gates(census_before: Dict[str, Any], census_after: Dict[str, Any],
          n_serve_typed_before: int, n_demoted: int,
          n_relabeled: int, n_anchor_only: int) -> Dict[str, Any]:
    far_after = census_after["far"]["n_resolved_side_match"]
    far_before = census_before["far"]["n_side_match"]
    far_n = census_after["far"]["n_points"]
    after = n_serve_typed_before - n_demoted + n_relabeled
    return {
        "far_prefix_census": {
            "before": f"{far_before}/{census_before['far']['n_window']}",
            "after": f"{far_after}/{far_n}",
            "target": ">= 6/8",
            "pass": far_n > 0 and far_after * 8 >= 6 * far_n,
        },
        "serve_action_count": {
            "before": n_serve_typed_before,
            "demoted": n_demoted,
            "relabeled": n_relabeled,
            "anchor_only_no_action": n_anchor_only,
            "after": after,
            "sanity_anchor": "~28 (v2 emitted 28; includes known-FP 6928A "
                             "still in stream + P32 pending round 3)",
        },
        "entreno_neutrality": "by construction: no src/ file touched "
                              "(post-hoc over pipeline_output.json)",
    }


# ----------------------------------------------------------------------
# driver
# ----------------------------------------------------------------------

def run(map_path: str, pipeline_path: str, anchors_path: str,
        out_path: str) -> Dict[str, Any]:
    amap = json.loads(Path(map_path).read_text(encoding="utf-8"))
    pipe = json.loads(Path(pipeline_path).read_text(encoding="utf-8"))
    anchors = parse_serve_anchors(anchors_path)
    actions = sorted(pipe["actions"], key=action_frame)

    prev: Optional[Dict[str, Any]] = None
    gaps: Dict[int, Optional[int]] = {}
    for a in actions:
        gaps[action_frame(a)] = gap_before(a, prev)
        prev = a

    n_serve_before = sum(1 for a in actions if a["action"] == "serve")
    census_before = prefix_census_before(amap["points"])

    owner_marked = owner_marked_frames(anchors,
                                       amap.get("false_serve_candidates", []))
    resolutions = [resolve_point(pv, actions, gaps, anchors, None,
                                 owner_marked)
                   for pv in amap["points"]]
    demotions = find_demotions(actions, anchors, owner_marked)
    demoted_frames = {d["frame"] for d in demotions}
    windows = [pv["window_frames"] for pv in amap["points"]
               if pv.get("window_frames")]
    outside = [o for o in outside_window_serves(actions, windows)
               if o["frame"] not in demoted_frames]
    cen = census(resolutions)
    relabeled = [r for r in resolutions if r["decision"] == "relabeled"]
    anchor_only = [r for r in resolutions if r["decision"] == "anchor_only"]

    # pass-2 action stream: original stream + pass-2 annotations (the
    # production stream is never rewritten; downstream layers join on frame)
    by_frame = {r["serve"]["frame"]: r for r in resolutions
                if r["serve"] and r["decision"] in ("emitted", "relabeled",
                                                    "owner_pinned")}
    actions_pass2 = []
    for a in actions:
        f = action_frame(a)
        b = dict(a)
        if f in demoted_frames:
            b["pass2_demoted"] = True
        r = by_frame.get(f)
        if r is not None and a["action"] == r["serve"]["action_original"]:
            b["pass2_action"] = "serve"
            b["pass2_team"] = r["serve"]["team_resolved"]
            b["pass2_source"] = r["decision"]
            if r["serve"]["team_overridden"]:
                b["pass2_team_overridden"] = True
        actions_pass2.append(b)

    gts = gates(census_before, cen, n_serve_before, len(demotions),
                len(relabeled), len(anchor_only))

    out = {
        "video": amap["video"],
        "generated_from": {
            "map": map_path,
            "pipeline": pipeline_path,
            "serve_anchors": anchors_path,
            "note": "pass-2 interpretation layer (AGENTS.md section 6); "
                    "perception untouched",
        },
        "gap_rule": {
            "GAP_SERVE_MIN": GAP_SERVE_MIN,
            "measured": "serve-position openers 153-1206f (prefix 219-853/"
                        "None); largest non-opening t1 gap 134f",
        },
        "points": resolutions,
        "demotions": demotions,
        "owner_marked_false_frames": sorted(owner_marked),
        "outside_window_serves": outside,
        "census": cen,
        "gates": gts,
        "actions_pass2": actions_pass2,
    }
    Path(out_path).write_text(json.dumps(out, indent=1) + "\n",
                              encoding="utf-8")
    return out


def print_report(out: Dict[str, Any]) -> None:
    g = out["gates"]
    print("=== pass-2 serve re-labeling report ===")
    print(f"far prefix census: {g['far_prefix_census']['before']} -> "
          f"{g['far_prefix_census']['after']} (target "
          f"{g['far_prefix_census']['target']}, "
          f"pass={g['far_prefix_census']['pass']})")
    print(f"serve-typed actions: {g['serve_action_count']['before']} -> "
          f"{g['serve_action_count']['after']} "
          f"(-{g['serve_action_count']['demoted']} demoted, "
          f"+{g['serve_action_count']['relabeled']} relabeled)")
    ac = out["census"]["all_points"]
    print(f"points with a resolved serve: {ac['n_with_serve']}/{ac['n']}")
    for d in _DECISIONS:
        pts = ac["decisions"].get(d, [])
        if pts:
            print(f"  {d:12s}: {pts}")
    ov = [r for r in out["points"] if r.get("serve", {}) 
          and (r["serve"] or {}).get("team_overridden")]
    if ov:
        print("team overridden to the structural expectation "
              "(emitted toucher team contradicts anchor/winner-serves):")
        for r in ov:
            print(f"  P{r['point']}: {r['serve']['team_emitted']} -> "
                  f"{r['serve']['team_resolved']} "
                  f"(f{r['serve']['frame']}, {r['decision']})")
    if out["demotions"]:
        print("demoted (owner FALSE / OFFGAME):")
        for d in out["demotions"]:
            print(f"  f{d['frame']} {d['team']} -- {d['because']}: "
                  f"{d['note'][:70]}")
    if out["outside_window_serves"]:
        print("serve-typed OUTSIDE every window (reported, not demoted):")
        for o in out["outside_window_serves"]:
            print(f"  f{o['frame']} {o['team']}")
    ro = [r for r in out["points"] if r["decision"] == "report_only"]
    if ro:
        print("report_only (never forced):")
        for r in ro:
            for line in r["report"]:
                print(f"  P{r['point']}: {line}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--map", default=DEFAULT_MAP)
    ap.add_argument("--pipeline", default=DEFAULT_PIPELINE)
    ap.add_argument("--anchors", default=DEFAULT_ANCHORS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    out = run(args.map, args.pipeline, args.anchors, args.out)
    print_report(out)
    print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
