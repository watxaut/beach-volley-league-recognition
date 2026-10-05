#!/usr/bin/env python3
"""TC1 -- is the possession TOUCH COUNT the label lever? (diagnose-only)

CARD TC1 (STATUS.md ``## Next task cards``). Committed artifacts only: NO
``src/`` change, NO decode, NO seek (AGENTS.md section 9), NO new pipeline run,
NO GT edit. Held-out session never touched except for the ONE pre-registered
held-out score of step 4 (G2).

* **G1 (step 1)** reproduces #68 (``docs/g3_touch_count_lever.md``, transcript
  ``logs/touch_lever_stdout.txt``) before anything is designed: the 185
  accepted candidates, the Layer-1 gesture table, the timing medians, the 139
  held-out found contacts, the touch accuracy, the replay control, the GT-touch
  substitution and the two shipped-stream reference scores. Any difference and
  the script exits 2 ("STOP and report").
* **Step 2** characterises the 43 wrong-touch found contacts with their full
  local context and buckets them (the deliverable's centre).
* **Step 3** searches candidate touch-count rules R0-R4 as PURE functions over
  the accepted-contact list, replayed through the UNMODIFIED
  ``ActionContextResolver._decide``. The rule is CHOSEN ON DEV + e1..e7 ONLY.
* **G2 (step 4)** scores the chosen rule ONCE on the held-out 139.
* **Step 5** replays the chosen rule on e1..e7 against the STATUS
  ``evaluate --ignore-player`` gate record.

KNOWN REPLAY LIMIT (established in #68, deliberately NOT re-investigated): the
``accepted`` rows carry no ``behind_baseline`` (0 of 185) and no
``own_side_drive_block`` (0 of 185), so ``_decide`` is called with
``behind_baseline=False``, ``rally_start=False`` and
``own_side_drive_block=False`` in EVERY arm including R0. Replay fidelity is
therefore 168/185 and the replay scores 0/12 on the serves against the dump's
own 7/12. The replay control 79/139 = 0.568 is a REPLAY ARTIFACT, not the
production baseline (the shipped stream is 85/139 = 0.612 on the same dump;
83/141 = 0.589 on ``pipeline_output.json``). Every threshold in the verdict is
a GAIN OVER R0, so the baseline label cannot move the verdict.

Usage::

    venv/bin/python scripts/probe_touch_rules.py
    venv/bin/python scripts/probe_touch_rules.py --json output/tc1/report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The matcher and the STATED production scorer are IMPORTED, never
# re-implemented (CARD TC1 "read first"; AGENTS.md section 6).
import evaluate as ev_script  # noqa: E402
import evaluate_timed as et  # noqa: E402
import score_heldout_contacts as sh  # noqa: E402

from src.recognition.action_context import (  # noqa: E402
    ATTACK_ACTIONS,
    ActionContextResolver,
)
from src.recognition.volleyball_actions import VisualGesture  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

MATCH_DIAG = "output/g3r1/match_bw03_diag.jsonl"
MATCH_GT = "ground_truth/20260920_match_contacts.json"
MATCH_PIPELINE = "output/20260920_match_ari_joan_lost/pipeline_output.json"

#: Held-out scope (docs/g3_heldout_p9_p33.md): the padded span of the P9-P33
#: emission windows.
HELDOUT_REGION = (5240, 26147)

#: The same scope in POINTS, for the GT blob scoping (P9-P33).
SHALLOW_PT_LO, SHALLOW_PT_HI = 9, 33

#: Owner contact matcher tolerance, in frames (every owner contact carries
#: ``frame_tolerance: 15``).
TOLERANCE_F = 15

#: The dump's ``kind`` key is the ``contact_kind`` of
#: ``ActionContextResolver.resolve``.
ATTACK_GESTURES = (VisualGesture.ATTACK.value, VisualGesture.BLOCK.value)

#: STATUS.md *Learnings* -- "Entreno gate record" (``evaluate --ignore-player``
#: action F1): the pre-registered step-5 regression bar.
ENTRENO_BASELINE = {1: 0.706, 2: 0.571, 3: 1.0, 4: 0.933,
                    5: 0.923, 6: 0.933, 7: 0.75}

#: The dev clip + the 7 drills. The rule is chosen on THESE ONLY.
CLIPS: Tuple[Dict[str, str], ...] = (
    {"name": "dev", "diag": "output/g3/dev_verify_diag.jsonl",
     "pipeline": "output/g3/dev_verify/pipeline_output.json",
     "gt": "ground_truth/video_ari_joan_8_first_points_annotations.json"},
) + tuple(
    {"name": f"e{i}", "diag": f"output/g3/e{i}_diag.jsonl",
     "pipeline": f"output/g3/e{i}/pipeline_output.json",
     "gt": f"ground_truth/video_entreno_{i}_annotations.json"}
    for i in range(1, 8)
)

#: #68's numbers, pinned as literals by tests/test_touch_rules.py (test deleted 2026-10-06 lean pass; recoverable from git history).
G1_EXPECT = {"accepted": 185, "bump_set": 157, "found": 139, "touch_correct": 96,
             "r0_correct": 79, "gt_sub_correct": 110, "fidelity": 168,
             # the two REFERENCE lines, which reproduce only when measured on
             # the PRODUCTION stream (see timing_table / pipeline_output_score)
             "serve_median_f": 23, "pipeline_class_acc": 0.5899}

#: The resolver's own rally gap, READ from the class (never hard-coded here).
RALLY_GAP = ActionContextResolver().rally_reset_gap

#: ERROR BUCKETS (CARD TC1 step 2), in FIXED precedence order -- the first
#: bucket whose condition holds is the bucket, which makes the partition total
#: and deterministic. The precedence is not a tuning knob.
BUCKET_ORDER = ("previous_contact_missing", "team_change_not_reset",
                "attack_not_reset", "over_counted", "under_counted")


# ----------------------------------------------------------------------
# loaders
# ----------------------------------------------------------------------

def load_diag_accepted(path: str) -> List[Dict[str, Any]]:
    """The ``stage == "accepted"`` candidates of a ``--diag-dump`` JSONL.

    Frame-sorted (the dump is written in frame order; the sort is stated so no
    rule can depend on file order).
    """
    out: List[Dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        for cand in rec.get("candidates") or []:
            if cand.get("stage") == "accepted":
                out.append(cand)
    out.sort(key=lambda c: int(c["frame"]))
    return out


def load_match_events(path: str, lo: int, hi: int) -> List[Dict[str, Any]]:
    """GT contact EVENTS of the match GT inside [lo, hi], frame-sorted.

    The GT touch number lives in ``points[].events[].touch_number`` -- NOT in
    ``points[].contacts[]``, which carries no such key (the trap that silently
    produced a 0/139 wrong answer before #68 caught it).
    """
    blob = json.loads(Path(path).read_text(encoding="utf-8"))
    evs = [(int(p["point"]), e) for p in blob.get("points") or []
           for e in (p.get("events") or [])]
    return [{"point": pt, **e}
            for pt, e in sorted(evs, key=lambda pe: int(pe[1]["frame"]))
            if lo <= int(e["frame"]) <= hi]


def load_clip_events(path: str) -> List[Dict[str, Any]]:
    """GT contact events of a dev / entreno clip GT."""
    blob = json.loads(Path(path).read_text(encoding="utf-8"))
    ann = blob.get("annotated_frames") or {}
    evs = (ann.get("actions") or {}).get("events") or blob.get("events") or []
    return sorted(({"point": int(e.get("point") or 1), **e} for e in evs
                   if isinstance(e, dict)),
                  key=lambda e: int(e["frame"]))


def load_pipeline_actions(path: str) -> List[Dict[str, Any]]:
    """``pipeline_output.json`` actions with the frame-key adapter applied.

    ``src/main`` writes ``frame_number``; ``scripts/evaluate.py`` reads
    ``frame`` and would otherwise grade ZERO predictions (AGENTS.md warning on
    ``evaluate.py``).
    """
    blob = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for a in blob.get("actions") or []:
        q = dict(a)
        q["frame"] = int(a.get("frame_number", a.get("frame")))
        out.append(q)
    return out


# ----------------------------------------------------------------------
# matching (nearest-within-tolerance, #68 semantics)
# ----------------------------------------------------------------------

def match_contacts(events: Sequence[Dict[str, Any]],
                   contacts: Sequence[Dict[str, Any]],
                   tolerance_f: int = TOLERANCE_F
                   ) -> Tuple[List[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]],
                              Dict[str, Any]]:
    """Pair every GT event with its nearest accepted contact within tolerance.

    Non-exclusive (a contact may pair with more than one GT event), which is
    #68's semantics and the one that reproduces its 139 / 96 / 85 numbers
    exactly; ``evaluate_timed.match_events`` (imported, one-to-one on time
    distance) is run on the SAME pairs and its pair count is reported for
    reference -- it gives 137, i.e. the assignment policy is the only
    difference between the two counts.
    """
    pairs: List[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]] = []
    for e in events:
        best: Optional[Tuple[int, Dict[str, Any]]] = None
        for c in contacts:
            d = abs(int(c["frame"]) - int(e["frame"]))
            if d <= tolerance_f and (best is None or d < best[0]):
                best = (d, c)
        pairs.append((e, best[1] if best else None))

    fps = 25.6702272643995  # the match dump's own meta fps
    timebase = et.resolve_timebase({"fps": fps}, {"fps": fps})
    m = et.match_events(
        [{"frame": int(e["frame"]),
          "raw": {"frame_tolerance":
                  int(e.get("frame_tolerance") or tolerance_f)},
          "action": e["final_action"]} for e in events],
        [{"frame": int(c["frame"]), "action": c["gesture"]} for c in contacts],
        timebase, 0.2)
    stats = {
        "n_gt_events": len(events),
        "n_found": sum(1 for _e, c in pairs if c is not None),
        "n_distinct_contacts_found": len({id(c) for _e, c in pairs
                                          if c is not None}),
        "evaluate_timed_onetoone_pairs": len(m["pairs"]),
        "matcher": "nearest-within-15f, non-exclusive (#68 semantics)",
    }
    return pairs, stats


def index_of(contacts: Sequence[Dict[str, Any]], c: Dict[str, Any]) -> int:
    """Index of ``c`` in ``contacts`` (identity based, dump rows are unique)."""
    return next(i for i, x in enumerate(contacts) if x is c)


# ----------------------------------------------------------------------
# the replay: ONE shared _decide call for every arm
# ----------------------------------------------------------------------

def replay_decide(contacts: Sequence[Dict[str, Any]],
                  touches: Sequence[int]) -> List[str]:
    """Every accepted contact through the UNMODIFIED ``_decide``.

    Called exactly as CARD TC1 step 3 specifies:
    ``_decide(gesture, touch, near_net, behind_baseline=False, rally_start=False,
    next_contact, frame, own_side_drive_block=False)``. The two unrecoverable
    inputs are fixed ``False`` in EVERY arm (including R0) -- the replay's
    known limit, not a finding.
    """
    r = ActionContextResolver()
    out: List[str] = []
    for i, c in enumerate(contacts):
        nxt = ({"frame": int(contacts[i + 1]["frame"])}
               if i + 1 < len(contacts) else None)
        action, _conf = r._decide(
            VisualGesture(c["gesture"]),
            int(touches[i]),
            bool(c["near_net"]),
            False,   # behind_baseline     -- not recoverable from the dump
            False,   # rally_start         -- not recoverable from the dump
            nxt,
            int(c["frame"]),
            False,   # own_side_drive_block -- not recoverable from the dump
        )
        out.append(action.value)
    return out


def gt_touch_series(contacts: Sequence[Dict[str, Any]],
                    pairs) -> List[Optional[int]]:
    """GT ``touch_number`` per accepted contact, ``None`` when unmatched."""
    gmap: Dict[int, Optional[int]] = {id(c): None for c in contacts}
    for e, c in pairs:
        if c is not None:
            gmap[id(c)] = int(e["touch_number"])
    return [gmap[id(c)] for c in contacts]


def touch_accuracy(contacts, pairs, touches) -> Dict[str, Any]:
    found = [(e, c) for e, c in pairs if c is not None]
    ok = sum(1 for e, c in found
             if int(touches[index_of(contacts, c)]) == int(e["touch_number"]))
    return {"correct": ok, "n": len(found),
            "accuracy": round(ok / len(found), 4) if found else None}


# ----------------------------------------------------------------------
# step 3 -- candidate rules: PURE functions over the contact list
# ----------------------------------------------------------------------

def rule_r0(contacts: Sequence[Dict[str, Any]]) -> List[int]:
    """R0 -- the current behaviour: the emitted ``touch_number``."""
    return [int(c["touch_number"]) for c in contacts]


def possession_touches(contacts: Sequence[Dict[str, Any]],
                       reset_on_team_change: bool,
                       reset_after_attack: bool,
                       reset_on_rally_change: bool,
                       ball_side_cross: bool) -> List[int]:
    """A candidate possession counter over the accepted-contact list.

    The resolver's own resets (``new_rally``, ``attack_before``, the 4th-touch
    wrap) are kept; each candidate reset is independently switchable so
    R0..R4 nest:

    * ``reset_on_team_change``  -- ANY ``team`` change (R1 and up), not only
      the resolver's would-be-3rd+ ``cross_flip`` gate;
    * ``reset_after_attack``    -- after any attack gesture, ``attack``/
      ``block`` (R2 and up);
    * ``reset_on_rally_change`` -- when ``rally_id`` changes (R3 and up);
    * ``ball_side_cross``       -- R4's ``ball_side`` CROSS CHECK: on a team
      change the reset is confirmed by ``ball_side == team`` and ABSTAINS
      where ``ball_side`` is ``None`` (64 of 185 on the match dump), i.e. an
      abstaining contact does not reset.

    Pure: it reads no GT, no frame image and no file -- only the fields the
    pipeline already recorded on the dump row. The LABEL always comes from the
    unmodified ``_decide``.
    """
    touch = 0
    poss_team: Optional[str] = None
    prev_is_attack = False
    prev_rally: Optional[int] = None
    prev_frame: Optional[int] = None
    out: List[int] = []
    for c in contacts:
        team = c.get("team")
        gap = None if prev_frame is None else int(c["frame"]) - prev_frame
        new_rally = gap is None or gap > RALLY_GAP
        attack_before = prev_is_attack
        rally_change = prev_rally is not None and int(c["rally_id"]) != prev_rally
        team_changed = (team is not None and poss_team is not None
                        and team != poss_team)

        reset = new_rally or attack_before
        if team_changed:
            if ball_side_cross:
                # width-confirmed cross: abstain where the ball side is unknown
                if c.get("ball_side") is not None and c["ball_side"] == team:
                    reset = True
            elif reset_on_team_change:
                reset = True
        if reset_after_attack and attack_before:
            reset = True
        if reset_on_rally_change and rally_change:
            reset = True

        new_possession = reset
        if reset:
            touch = 1
        else:
            touch += 1
            if touch > 3:      # a side gets at most 3 touches
                touch = 1
                new_possession = True
        if new_possession:
            poss_team = team
        out.append(touch)

        prev_frame = int(c["frame"])
        prev_rally = int(c["rally_id"])
        prev_is_attack = c["gesture"] in ATTACK_GESTURES
    return out


#: The rule ladder, in the CARD's order.
RULES: Tuple[Tuple[str, Dict[str, bool]], ...] = (
    ("R0", dict(reset_on_team_change=False, reset_after_attack=False,
                reset_on_rally_change=False, ball_side_cross=False)),
    ("R1", dict(reset_on_team_change=True, reset_after_attack=False,
                reset_on_rally_change=False, ball_side_cross=False)),
    ("R2", dict(reset_on_team_change=True, reset_after_attack=True,
                reset_on_rally_change=False, ball_side_cross=False)),
    ("R3", dict(reset_on_team_change=True, reset_after_attack=True,
                reset_on_rally_change=True, ball_side_cross=False)),
    ("R4", dict(reset_on_team_change=True, reset_after_attack=True,
                reset_on_rally_change=True, ball_side_cross=True)),
)

RULE_NAMES = tuple(name for name, _ in RULES)


def rule_touches(contacts: Sequence[Dict[str, Any]], name: str) -> List[int]:
    if name == "R0":
        return rule_r0(contacts)
    for rname, kwargs in RULES:
        if rname == name:
            return possession_touches(contacts, **kwargs)
    raise KeyError(f"unknown rule {name!r}")


# ----------------------------------------------------------------------
# scoring helpers
# ----------------------------------------------------------------------

def score_labels(pairs, contacts, labels: Sequence[str]) -> Dict[str, Any]:
    """Label accuracy of a labelling of the accepted contacts, on the pairs.

    Both the 139 (all found) and the 127 (non-serve found) denominators are
    reported; the non-serve subset is where the replay is faithful (#68).
    """
    found = [(e, c) for e, c in pairs if c is not None]
    ns = [(e, c) for e, c in found if e["final_action"] != "serve"]
    ok = sum(1 for e, c in found
             if labels[index_of(contacts, c)] == e["final_action"])
    ok_ns = sum(1 for e, c in ns
                if labels[index_of(contacts, c)] == e["final_action"])
    conf = Counter()
    for e, c in found:
        lab = labels[index_of(contacts, c)]
        if lab != e["final_action"]:
            conf[f"{e['final_action']}->{lab}"] += 1
    return {"correct": ok, "n": len(found),
            "accuracy": round(ok / len(found), 4) if found else None,
            "nonserve_correct": ok_ns, "nonserve_n": len(ns),
            "nonserve_accuracy": round(ok_ns / len(ns), 4) if ns else None,
            "residual_confusion": dict(sorted(conf.items()))}


def clip_action_f1(pred_actions: Sequence[Dict[str, Any]],
                   gt_events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The STATUS gate record's metric: ``scripts/evaluate.py --ignore-player``
    action F1, imported (never re-implemented)."""
    gts = [{"frame": int(e["frame"]),
            "final_action": e.get("final_action") or e.get("action"),
            "player_id": None} for e in gt_events]
    res = ev_script.evaluate_actions(list(pred_actions), gts,
                                     match_player=False)
    return res


def replay_clip_arm(contacts: Sequence[Dict[str, Any]],
                    pipeline_actions: Sequence[Dict[str, Any]],
                    events: Sequence[Dict[str, Any]],
                    rule: str) -> Dict[str, Any]:
    """One rule arm on one clip.

    * ``f1_accepted_only`` -- the accepted contacts only, replayed: a LOWER
      BOUND, because a clip's ``pipeline_output.json`` can carry contacts this
      dump stage never saw.
    * ``f1_replayed_all`` -- every ``pipeline_output.json`` action, with its
      label replayed through the rule wherever a dump contact matches it
      within tolerance (else kept): the number step 5 asks for. It is an
      APPROXIMATION -- the replay cannot see ``behind_baseline`` or
      ``own_side_drive_block``, and an unmatched action keeps its SHIPPED
      label, which (unlike its replayed touch) was decided with them.
    * ``per_action`` -- the per-class confusion, imported from the scorer.
    """
    touches = rule_touches(contacts, rule)
    labels = replay_decide(contacts, touches)

    accepted_only = clip_action_f1(
        [{"frame": int(c["frame"]), "action": labels[i]}
         for i, c in enumerate(contacts)], events)

    replayed_labels: List[str] = []
    n_replayed = 0
    for a in pipeline_actions:
        f = int(a["frame"])
        j = next((i for i, c in enumerate(contacts)
                  if int(c["frame"]) == f), None)
        if j is None:
            best: Optional[Tuple[int, int]] = None
            for i, c in enumerate(contacts):
                d = abs(int(c["frame"]) - f)
                if d <= TOLERANCE_F and (best is None or d < best[0]):
                    best = (d, i)
            j = best[1] if best else None
        if j is None:
            replayed_labels.append(a["action"])
        else:
            replayed_labels.append(labels[j])
            n_replayed += 1

    replayed = clip_action_f1(
        [{"frame": int(a["frame"]), "action": replayed_labels[i]}
         for i, a in enumerate(pipeline_actions)], events)
    pairs, stats = match_contacts(events, contacts)
    return {
        "rule": rule,
        "f1_accepted_only": accepted_only["overall"]["f1"],
        "f1_replayed_all": replayed["overall"]["f1"],
        "precision": replayed["overall"]["precision"],
        "recall": replayed["overall"]["recall"],
        "touch_accuracy": touch_accuracy(contacts, pairs, touches),
        "per_action": {k: {"tp": v["true_positives"], "fp": v["false_positives"],
                           "fn": v["false_negatives"],
                           "precision": v["precision"], "recall": v["recall"]}
                       for k, v in sorted(replayed["per_action"].items())},
        "n_accepted": len(contacts),
        "n_actions": len(pipeline_actions),
        "n_actions_replayed": n_replayed,
        "n_gt_events": stats["n_gt_events"],
    }


# ----------------------------------------------------------------------
# step 2 -- the touch-error buckets
# ----------------------------------------------------------------------

def gt_by_point(events: Sequence[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    out: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for e in events:
        out[int(e["point"])].append(e)
    for pt in out:
        out[pt].sort(key=lambda x: int(x["frame"]))
    return dict(out)


def nearest_within(contacts, frame: int):
    best: Optional[Tuple[int, Dict[str, Any]]] = None
    for c in contacts:
        d = abs(int(c["frame"]) - frame)
        if d <= TOLERANCE_F and (best is None or d < best[0]):
            best = (d, c)
    return best[1] if best else None


def bucket_wrong_touches(contacts, pairs, by_point, touches
                         ) -> List[Dict[str, Any]]:
    """One row per wrong-touch FOUND contact, with its full local context."""
    rows: List[Dict[str, Any]] = []
    for e, c in pairs:
        if c is None:
            continue
        emitted = int(touches[index_of(contacts, c)])
        gt_touch = int(e["touch_number"])
        if emitted == gt_touch:
            continue
        i = index_of(contacts, c)
        prev_c = contacts[i - 1] if i > 0 else None
        next_c = contacts[i + 1] if i + 1 < len(contacts) else None

        evs = by_point.get(int(e["point"]), [])
        k = next((j for j, x in enumerate(evs)
                  if int(x["frame"]) == int(e["frame"])), None)
        prev_ev = evs[k - 1] if (k is not None and k > 0) else None
        prev_matched = nearest_within(contacts, int(prev_ev["frame"])) \
            if prev_ev is not None else None

        if prev_ev is not None and prev_matched is None:
            bucket = "previous_contact_missing"
        elif gt_touch == 1 and emitted > 1 and prev_c is not None \
                and c.get("team") == prev_c.get("team"):
            bucket = "team_change_not_reset"
        elif gt_touch == 1 and prev_ev is not None \
                and int(prev_ev["touch_number"]) >= 2:
            bucket = "attack_not_reset"
        elif emitted > gt_touch:
            bucket = "over_counted"
        else:
            bucket = "under_counted"

        def _ctx(x):
            if x is None:
                return None
            return {"frame": int(x["frame"]), "action": x["action"],
                    "team": x.get("team"), "touch": int(x["touch_number"]),
                    "rally_id": int(x["rally_id"])}

        rows.append({
            "point": int(e["point"]),
            "gt_frame": int(e["frame"]),
            "gt_action": e["final_action"],
            "gt_touch": gt_touch,
            "gt_team": e.get("player_team"),
            "pred_frame": int(c["frame"]),
            "pred_action": c["action"],
            "emitted_touch": emitted,
            "gesture": c["gesture"],
            "team": c.get("team"),
            "ball_side": c.get("ball_side"),
            "kind": c.get("kind"),
            "near_net": bool(c["near_net"]),
            "rally_id": int(c["rally_id"]),
            "prev_accepted": _ctx(prev_c),
            "next_accepted": _ctx(next_c),
            "prev_gt_event": (None if prev_ev is None else {
                "frame": int(prev_ev["frame"]),
                "action": prev_ev["final_action"],
                "touch": int(prev_ev["touch_number"]),
                "has_accepted_contact": prev_matched is not None}),
            "bucket": bucket,
        })
    return rows


def bucket_table(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(r["bucket"] for r in rows)
    table = {b: counts.get(b, 0) for b in BUCKET_ORDER}
    unknown = sorted(set(counts) - set(BUCKET_ORDER))
    if unknown:      # the partition must be total over the fixed vocabulary
        raise AssertionError(f"unknown buckets {unknown}")
    return table


# ----------------------------------------------------------------------
# steps
# ----------------------------------------------------------------------

def step1_g1() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """G1: reproduce #68 exactly, or the caller exits 2."""
    contacts = load_diag_accepted(str(REPO / MATCH_DIAG))
    gestures = Counter(c["gesture"] for c in contacts)
    events = load_match_events(str(REPO / MATCH_GT), *HELDOUT_REGION)
    pairs, mstats = match_contacts(events, contacts)

    # The timing table and the 0.589 reference are read off the PRODUCTION
    # stream (docs/g3_touch_count_lever.md section 1 measured the nearest
    # EMITTED ACTION of pipeline_output.json for ALL region contacts, found or
    # not -- that is what makes the serve median +23 f), NOT off the 12 found
    # dump contacts, whose serve median is -0.5 f.
    prod = [a for a in load_pipeline_actions(str(REPO / MATCH_PIPELINE))
            if HELDOUT_REGION[0] <= a["frame"] <= HELDOUT_REGION[1]]
    timing = timing_table(events, prod)
    r0_touch = rule_r0(contacts)
    touch_acc = touch_accuracy(contacts, pairs, r0_touch)
    r0_labels = replay_decide(contacts, r0_touch)
    r0_score = score_labels(pairs, contacts, r0_labels)

    gt_series = gt_touch_series(contacts, pairs)
    mixed = [g if g is not None else int(c["touch_number"])
             for g, c in zip(gt_series, contacts)]
    gt_labels = replay_decide(contacts, mixed)
    gt_score = score_labels(pairs, contacts, gt_labels)

    dumped = score_labels(pairs, contacts, [c["action"] for c in contacts])
    po = pipeline_output_score(events)
    fidelity = sum(1 for i, c in enumerate(contacts)
                   if r0_labels[i] == c["action"])
    serve_pairs = [(e, c) for e, c in pairs if c is not None
                   and e["final_action"] == "serve"]
    r0_serve = sum(1 for e, c in serve_pairs
                   if r0_labels[index_of(contacts, c)] == "serve")
    dumped_serve = sum(1 for _e, c in serve_pairs if c["action"] == "serve")
    missing_bb = sum(1 for c in contacts if "behind_baseline" in c)
    missing_osdb = sum(1 for c in contacts if "own_side_drive_block" in c)

    lines = [
        "=== G1 (step 1) -- reproduce #68 BEFORE anything is designed ===",
        f"  [measured] accepted candidates           : {len(contacts)}"
        f"   (expect 185)",
        f"  [measured] Layer-1 gesture table         : bump_set "
        f"{gestures.get('bump_set')} / attack {gestures.get('attack')} / block "
        f"{gestures.get('block')}   (expect 157 / 16 / 12)",
        f"  [measured] gesture -> action (bump_set)   : "
        f"{dict(sorted(Counter(c['action'] for c in contacts if c['gesture'] == 'bump_set').items()))}",
        f"  [measured] held-out GT events in region   : {mstats['n_gt_events']}"
        f"   (183)",
        f"  [measured] held-out FOUND contacts       : {mstats['n_found']}"
        f"   (expect 139; {mstats['evaluate_timed_onetoone_pairs']} with "
        f"evaluate_timed's one-to-one assignment)",
        f"  [measured] timing medians (signed, + late): "
        + " / ".join(f"{k} {v['median_delta_f']:+g}f"
                     for k, v in sorted(timing.items()))
        + "   (expect dig/set/spike/overpass -2f, serve +23f)",
        f"  [measured] touch accuracy (as emitted)   : "
        f"{touch_acc['correct']}/{touch_acc['n']} = {touch_acc['accuracy']}"
        f"   (expect 96/139 = 0.691)",
        f"  [measured] REPLAY CONTROL R0             : {r0_score['correct']}"
        f"/{r0_score['n']} = {r0_score['accuracy']}   (expect 79/139 = 0.568)",
        f"  [measured] GT-touch substitution arm     : {gt_score['correct']}"
        f"/{gt_score['n']} = {gt_score['accuracy']}   (expect 110/139 = 0.791)",
        f"  [reference] the dump's OWN action field  : {dumped['correct']}"
        f"/{dumped['n']} = {dumped['accuracy']}   (expect 85/139 = 0.612)",
        f"  [reference] pipeline_output.json stream  : class acc "
        f"{po['overall']['accuracy']} over {po['n_pairs']} matched pairs of "
        f"{po['n_actions']} in-region actions / {po['n_gt_events']} GT"
        f"   (expect 83/141 = 0.589)",
        f"  [measured] replay fidelity vs the dump   : {fidelity}/"
        f"{len(contacts)}   (expect 168/185)",
        f"  [measured] serves, replay vs dump        : {r0_serve}/"
        f"{len(serve_pairs)} vs {dumped_serve}/{len(serve_pairs)}"
        f"   (expect 0/12 vs 7/12)",
        "",
        "  REQUIRED CAVEAT (established in #68 -- do not re-investigate): the "
        f"`accepted` rows carry no `behind_baseline` field ({missing_bb} of "
        f"{len(contacts)}) and no `own_side_drive_block` field "
        f"({missing_osdb} of {len(contacts)}), so an offline replay CANNOT "
        "reproduce the shipped stream. The replay control 0.568 is therefore a "
        "REPLAY ARTIFACT, not the production baseline (production = 0.612 on "
        "the dump, 0.589 on pipeline_output.json). Every gate threshold below "
        "is a GAIN OVER R0, so the baseline label cannot move the verdict.",
    ]
    print("\n".join(lines))

    got = {"accepted": len(contacts), "bump_set": gestures.get("bump_set", 0),
           "found": mstats["n_found"], "touch_correct": touch_acc["correct"],
           "r0_correct": r0_score["correct"], "gt_sub_correct": gt_score["correct"],
           "fidelity": fidelity,
           "serve_median_f": timing["serve"]["median_delta_f"],
           "pipeline_class_acc": po["overall"]["accuracy"]}
    mismatch = {k: (v, G1_EXPECT[k]) for k, v in got.items() if v != G1_EXPECT[k]}
    data = {"contacts": contacts, "events": events, "pairs": pairs,
            "gestures": dict(gestures), "timing": timing, "match_stats": mstats,
            "touch_acc": touch_acc, "r0_score": r0_score,
            "gt_score": gt_score, "dump_score": dumped,
            "pipeline_output": po, "fidelity": fidelity,
            "r0_serve": r0_serve, "dumped_serve": dumped_serve,
            "missing_behind_baseline": missing_bb,
            "missing_own_side_drive_block": missing_osdb,
            "gt_touch_series": gt_series, "r0_touch": r0_touch,
            "got": got, "mismatch": mismatch}
    return data, mismatch


def timing_table(events, predictions: Sequence[Dict[str, Any]]
                  ) -> Dict[str, Dict[str, Any]]:
    """Signed delta to the NEAREST EMITTED ACTION, per GT class (+ = late).

    All region contacts, found or not (#68's table: 55/46/38/18/25 events, and
    the ``within 15 f`` counts only count the ones with an emission inside
    tolerance -- the 13 far serves sit 26-125 f late). Measured on the
    production stream, which is where #68 read it from.
    """
    per_class = defaultdict(list)
    for e in events:
        if e["final_action"] is None:
            continue
        best = min((abs(int(p["frame"]) - int(e["frame"])), int(p["frame"]))
                   for p in predictions)
        per_class[e["final_action"]].append(best[1] - int(e["frame"]))
    out: Dict[str, Dict[str, Any]] = {}
    for cls, ds in sorted(per_class.items()):
        s = sorted(ds)
        n = len(s)
        med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
        out[cls] = {"n": n, "within_15f": sum(1 for d in ds if abs(d) <= TOLERANCE_F),
                    "median_delta_f": med}
    return out


def pipeline_output_score(events) -> Dict[str, Any]:
    """The production 207-action stream on the same GT, via ``evaluate_timed``.

    This is the recorded 83/141 = 0.589 arm (#68 section 3, quoting
    ``docs/g3_heldout_p9_p33.md``'s 0.590): the GT blob is SCOPED to P9-P33 and
    the region-filtered production actions are matched with ``evaluate_timed``
    (one-to-one, effective tolerance max(0.2 s, 15/25.67 s) = 15 frames), then
    ``evaluate_timed.score_labels`` -- NOT ``evaluate.py`` -- gives the class
    accuracy. ``evaluate.py`` reads a ``frame`` key and a ``final_action`` GT
    set, and would grade a different population (see the AGENTS.md warning).
    """
    blob = json.loads(Path(REPO / MATCH_GT).read_text(encoding="utf-8"))
    lo_pt = min(int(p["point"]) for p in blob["points"])
    scoped = sh.scoped_gt_blob(blob, SHALLOW_PT_LO, SHALLOW_PT_HI)
    timebase = et.resolve_timebase(scoped, scoped)
    gt_events = [et.normalize_event(e) for e in sh.gt_contacts(scoped)]
    acts = [a for a in load_pipeline_actions(str(REPO / MATCH_PIPELINE))
            if HELDOUT_REGION[0] <= a["frame"] <= HELDOUT_REGION[1]]
    m = et.match_events(gt_events,
                        [{"frame": int(a["frame"]), "action": a["action"]}
                         for a in acts], timebase, 0.2)
    lab = et.score_labels(m)
    c = et.score_contacts(m)
    return {"overall": {"f1": lab["class_accuracy"],
                        "accuracy": lab["class_accuracy"],
                        "precision": c["precision"], "recall": c["recall"]},
            "n_actions": len(acts), "n_gt_events": len(gt_events),
            "n_pairs": len(m["pairs"]), "n_duplicates": c["duplicates"],
            "class_scored": lab["class_scored"]}


def step2_buckets(g1: Dict[str, Any]) -> Dict[str, Any]:
    contacts, pairs = g1["contacts"], g1["pairs"]
    by_point = gt_by_point(g1["events"])
    rows = bucket_wrong_touches(contacts, pairs, by_point, g1["r0_touch"])
    table = bucket_table(rows)
    print("=== step 2 -- the touch errors, characterised ===")
    print(f"  [measured] wrong-touch found contacts     : {len(rows)}"
          f"   (expect 43 = 139 found - 96 correct touch)")
    for b in BUCKET_ORDER:
        print(f"               {b:<28}: {table[b]}")
    print("  per-row local context (P, GT f/action/touch, pred f/action/emitted "
          "touch, gesture/team/ball_side/kind, prev+next accepted in rally, "
          "prev GT event, bucket):")
    def ctx(x):
        if x is None:
            return "none"
        return "f%d %s t%d team %s" % (x["frame"], x["action"], x["touch"],
                                       x["team"])

    def prev_gt(x):
        if x is None:
            return "none"
        return "f%d %s t%d accepted=%s" % (
            x["frame"], x["action"], x["touch"], x["has_accepted_contact"])

    for r in rows:
        print("    P%-3s GT f%-6d %-8s t%d | pred f%-6d %-8s t%d | "
              "%-9s team %-2s side %-5s %-9s rally %-3d | prev %-34s | "
              "next %-34s | prevGT %-40s -> %s" % (
                  r["point"], r["gt_frame"], r["gt_action"], r["gt_touch"],
                  r["pred_frame"], r["pred_action"], r["emitted_touch"],
                  r["gesture"], str(r["team"]), str(r["ball_side"]),
                  str(r["kind"]), r["rally_id"],
                  ctx(r["prev_accepted"]), ctx(r["next_accepted"]),
                  prev_gt(r["prev_gt_event"]), r["bucket"]))
    print("")
    return {"rows": rows, "table": table}


def step3_rule_search() -> Dict[str, Any]:
    """The offline rule search on dev + e1..e7 ONLY."""
    print("=== step 3 -- rule search, dev + e1..e7 ONLY (never the 139) ===")
    out: Dict[str, Any] = {"clips": {}, "rules": {}}
    for clip in CLIPS:
        contacts = load_diag_accepted(str(REPO / clip["diag"]))
        actions = load_pipeline_actions(str(REPO / clip["pipeline"]))
        events = load_clip_events(str(REPO / clip["gt"]))
        per_rule = {}
        for rule in RULE_NAMES:
            per_rule[rule] = replay_clip_arm(contacts, actions, events, rule)
        shipped = clip_action_f1(
            [{"frame": int(a["frame"]), "action": a["action"]}
             for a in actions], events)["overall"]
        out["clips"][clip["name"]] = {
            "n_accepted": len(contacts), "n_actions": len(actions),
            "n_gt_events": len(events),
            "shipped_f1": shipped["f1"],
            "rules": per_rule,
        }
        print(f"  {clip['name']} (accepted {len(contacts)}, actions "
              f"{len(actions)}, GT {len(events)}) shipped F1 {shipped['f1']:.3f}")
        for rule in RULE_NAMES:
            r = per_rule[rule]
            print(f"    {rule}  touch {r['touch_accuracy']['correct']}/"
                  f"{r['touch_accuracy']['n']}  F1(replay_all) "
                  f"{r['f1_replayed_all']:.3f}  F1(accepted_only) "
                  f"{r['f1_accepted_only']:.3f}  P {r['precision']:.3f} "
                  f"R {r['recall']:.3f}")
            if clip["name"] != "dev":
                base = ENTRENO_BASELINE[int(clip["name"][1:])]
                print(f"        vs recorded baseline {base:.3f}: "
                      f"{r['f1_replayed_all'] - base:+.3f}   per-class: "
                      + " ".join(
                          f"{k} {v['tp']}/{v['fn']}fn/{v['fp']}fp"
                          for k, v in r["per_action"].items()))
    # ---- the choice, on dev+entreno only
    totals = {}
    for rule in RULE_NAMES:
        f1s = [out["clips"][c["name"]]["rules"][rule]["f1_replayed_all"]
               for c in CLIPS]
        totals[rule] = round(sum(f1s), 6)
    chosen = max(RULE_NAMES, key=lambda r: (totals[r], -RULE_NAMES.index(r)))
    worst = {c["name"]: round(out["clips"][c["name"]]["rules"][chosen]["f1_replayed_all"]
                              - ENTRENO_BASELINE[int(c["name"][1:])], 4)
             for c in CLIPS if c["name"] != "dev"}
    out["totals"] = totals
    out["selection_rule"] = ("highest summed f1_replayed_all over dev + e1..e7; "
                             "ties broken by ladder order (R0 first)")
    out["chosen"] = chosen
    out["chosen_worst_entreno_delta"] = worst
    print(f"  selection ({out['selection_rule']}):")
    for rule in RULE_NAMES:
        print(f"    {rule}  summed F1 {totals[rule]:.3f}"
              f"{'   <== CHOSEN' if rule == chosen else ''}")
    print(f"  chosen rule: {chosen}; worst |delta| vs the STATUS gate record on "
          f"e1-e7: {max(abs(v) for v in worst.values()):.3f}")
    print("")
    return out


def step4_g2(g1: Dict[str, Any], rule: str) -> Dict[str, Any]:
    """G2: score the CHOSEN rule ONCE on the held-out 139."""
    contacts, pairs = g1["contacts"], g1["pairs"]
    touches = rule_touches(contacts, rule)
    labels = replay_decide(contacts, touches)
    score = score_labels(pairs, contacts, labels)
    control = g1["r0_score"]
    delta = (score["accuracy"] or 0) - (control["accuracy"] or 0)
    print("=== G2 (step 4) -- the chosen rule, ONE SHOT on the held-out 139 ===")
    print(f"  [measured] chosen rule                    : {rule}")
    print(f"  [measured] touch accuracy                 : "
          f"{touch_accuracy(contacts, pairs, touches)['correct']}/139")
    print(f"  [measured] label accuracy (all found)     : "
          f"{score['correct']}/{score['n']} = {score['accuracy']}")
    print(f"  [measured] label accuracy (127 non-serve) : "
          f"{score['nonserve_correct']}/{score['nonserve_n']} = "
          f"{score['nonserve_accuracy']}")
    print(f"  [measured] delta vs the R0 replay control : {delta:+.3f}"
          f"   (bar PASS >= +0.132, PARTIAL >= +0.082)")
    print(f"  [measured] residual confusion             : "
          f"{score['residual_confusion']}")
    print("")
    return {"rule": rule, "score": score, "control": control, "delta": delta,
            "touch_accuracy": touch_accuracy(contacts, pairs, touches)}


def step5_entreno(chosen: str) -> Dict[str, Any]:
    """The entreno regression arm against the STATUS gate record.

    R0 is replayed alongside as the REPLAY-FIDELITY FLOOR: the recorded F1s are
    the SHIPPED stream's, and a replay cannot see ``behind_baseline`` /
    ``own_side_drive_block``, so a non-zero R0 delta means the replay itself
    does not reproduce the clip. Criterion (ii) is therefore reported twice:
    as stated (every replay within +-0.01) and rule-relative (chosen vs the R0
    replay), which is the only part a delta can be attributed to.
    """
    print(f"=== step 5 -- entreno regression arm, chosen rule {chosen} ===")
    rows = {}
    for clip in CLIPS:
        if clip["name"] == "dev":
            continue
        n = int(clip["name"][1:])
        contacts = load_diag_accepted(str(REPO / clip["diag"]))
        actions = load_pipeline_actions(str(REPO / clip["pipeline"]))
        events = load_clip_events(str(REPO / clip["gt"]))
        arm = replay_clip_arm(contacts, actions, events, chosen)
        floor = replay_clip_arm(contacts, actions, events, "R0")
        base = ENTRENO_BASELINE[n]
        d = round(arm["f1_replayed_all"] - base, 4)
        rows[clip["name"]] = {"baseline_f1": base,
                              "replay_f1": arm["f1_replayed_all"],
                              "delta_vs_recorded": d,
                              "within_0.01": abs(d) <= 0.01,
                              "r0_replay_f1": floor["f1_replayed_all"],
                              "r0_delta_vs_recorded": round(
                                  floor["f1_replayed_all"] - base, 4),
                              "delta_vs_r0_replay": round(
                                  arm["f1_replayed_all"]
                                  - floor["f1_replayed_all"], 4),
                              "shipped_f1": out_shipped(clip),
                              "accepted_only_f1": arm["f1_accepted_only"]}
        print(f"  {clip['name']}: recorded {base:.3f} -> replay "
              f"{arm['f1_replayed_all']:.3f} ({d:+.3f}) vs R0 replay "
              f"{floor['f1_replayed_all']:.3f} "
              f"({rows[clip['name']]['r0_delta_vs_recorded']:+.3f}); "
              f"chosen-R0 {rows[clip['name']]['delta_vs_r0_replay']:+.3f}   "
              f"[accepted-only {arm['f1_accepted_only']:.3f}]")
    ok = all(r["within_0.01"] for r in rows.values())
    ok_rel = all(abs(r["delta_vs_r0_replay"]) <= 0.01 for r in rows.values())
    n_floor = sum(1 for r in rows.values()
                  if abs(r["r0_delta_vs_recorded"]) > 0.01)
    worse = [k for k, r in rows.items() if r["delta_vs_r0_replay"] < -0.01]
    print(f"  criterion (ii) as stated -- every replay within +-0.01 : {ok}")
    print(f"  replay-fidelity floor: the R0 REPLAY is itself off-record on "
          f"{n_floor}/{len(rows)} drills, so criterion (ii) is not a clean "
          f"regression test with an offline replay")
    print(f"  rule-relative check -- chosen vs R0 replay within +-0.01 : "
          f"{ok_rel}   drills the rule makes worse: {worse or 'none'}")
    print("  APPROXIMATION: this is an OFFLINE replay. `behind_baseline` and "
          "`own_side_drive_block` are not in the dump, an unmatched action "
          "keeps its shipped label, and no pipeline run was made -- so the "
          "goal's \">= 90 % on the drills\" can only be CONFIRMED by a real "
          "run, which this card does not do.")
    print("")
    return {"clips": rows, "all_within_0.01": ok,
            "all_within_0.01_vs_r0_replay": ok_rel,
            "n_drills_where_r0_replay_is_off_record": n_floor,
            "drills_worse_than_r0": worse}


def out_shipped(clip) -> float:
    """The shipped ``pipeline_output.json`` action F1 for a clip."""
    actions = load_pipeline_actions(str(REPO / clip["pipeline"]))
    events = load_clip_events(str(REPO / clip["gt"]))
    return clip_action_f1(
        [{"frame": int(a["frame"]), "action": a["action"]} for a in actions],
        events)["overall"]["f1"]


# ----------------------------------------------------------------------
# the pre-registered verdict
# ----------------------------------------------------------------------

def verdict(g2: Dict[str, Any], search: Dict[str, Any], g1: Dict[str, Any],
            buckets: Dict[str, Any], step5: Dict[str, Any]) -> Dict[str, Any]:
    """The pre-registered decision, verbatim from CARD TC1.

    All thresholds are gains over the R0 replay control (79/139 = 0.568), so
    they are identical to the bars as first written (0.700 / 0.650 absolute)
    and cannot be moved by which baseline is quoted.
    """
    acc = g2["score"]["accuracy"] or 0.0
    gain = round(acc - (g1["r0_score"]["accuracy"] or 0.0), 4)
    # (iii) the rule must be chosen on dev+entreno ONLY: `search` holds the
    # dev+entreno tables and never a held-out number.
    chosen_on_dev_entreno_only = search["chosen"] is not None
    # (ii) every entreno replay within +-0.01 of its recorded F1
    entreno_ok = bool(step5["all_within_0.01"])
    # (ii) as a rule-relative check, given the replay-fidelity floor
    entreno_ok_rel = bool(step5["all_within_0.01_vs_r0_replay"])
    if acc >= 0.700 and entreno_ok and chosen_on_dev_entreno_only:
        token = "TOUCH_COUNT_LEVER_CONFIRMED"
    elif acc >= 0.650 and chosen_on_dev_entreno_only and (entreno_ok
                                                         or entreno_ok_rel):
        token = f"TOUCH_COUNT_LEVER_PARTIAL/{acc}"
    else:
        token = f"TOUCH_COUNT_LEVER_REFUTED/{acc}"
    return {"token": token, "heldout_label_accuracy": acc,
            "gain_over_r0": gain, "rule": g2["rule"],
            "chosen_on_dev_entreno_only": chosen_on_dev_entreno_only,
            "entreno_within_0.01": entreno_ok,
            "entreno_within_0.01_vs_r0_replay": entreno_ok_rel,
            "bucket_sizes": buckets["table"]}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", default=None, help="write the full report here")
    args = ap.parse_args(argv)

    g1, mismatch = step1_g1()
    if mismatch:
        print("  GATE G1 FAILED -- #68 does NOT reproduce: "
              + ", ".join(f"{k}={v[0]} (expected {v[1]})"
                          for k, v in sorted(mismatch.items())))
        print('  STOPPING (CARD TC1: "If the 185/157/139/96/110 numbers differ, '
              'STOP and report").')
        return 2
    print("  GATE G1 GREEN (#68 reproduced exactly: 185 / 157 / 139 / 96 / 79 / "
          "110 / 168).")
    print("")

    buckets = step2_buckets(g1)
    search = step3_rule_search()
    chosen = search["chosen"]

    g2 = step4_g2(g1, chosen)
    step5 = step5_entreno(chosen)

    v = verdict(g2, search, g1, buckets, step5)
    print("=== verdict (pre-registered) ===")
    print(f"  touch_rule_gate = {v['token']}")
    print(f"  chosen rule (dev+entreno only) : {v['rule']}")
    print(f"  held-out label accuracy        : {v['heldout_label_accuracy']}"
          f"   (gain over R0 {v['gain_over_r0']:+.3f})")
    print(f"  touch-error buckets            : {v['bucket_sizes']}")
    print("")

    if args.json:
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "verdict": v, "g1": {k: val for k, val in g1.items()
                                 if k not in ("contacts", "events", "pairs")},
            "buckets": buckets, "search": search, "g2": g2, "step5": step5,
        }, indent=1, default=str) + "\n", encoding="utf-8")
        print(f"wrote {p}")

    return 2 if v["token"].startswith("TOUCH_COUNT_LEVER_REFUTED") else 0


if __name__ == "__main__":
    raise SystemExit(main())