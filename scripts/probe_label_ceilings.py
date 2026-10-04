"""G3 label-lever CEILING probe -- how much is each OPEN label lever worth, held out.

Session #76.  STATUS item 0a ranks the open levers by an ESTIMATED ceiling
(label-only 90/139 = 0.6475, INSERT 96/150 = 0.6400) but that arithmetic is
inconsistent with the confusion matrix: on the SAME 139 matched held-out
contacts this probe's own census finds **61 label mismatches**, so a
label-only oracle reads 139/139, not 90/139.  The estimates were derived from
partial relabel sets; this probe measures the ceilings DIRECTLY by
rewriting ONLY the `action` field of already-emitted events and re-scoring
through the IMPORTED `evaluate_timed` matcher (never re-implemented).

Levers measured, each applied INDEPENDENTLY to the `pass2` arm (the better
arm: class 0.561 -> the shipped production stream):

  base       unchanged
  oracle     every matched contact relabelled to its GT class (label-only
             ceiling; contact recall is untouched, so F1 changes only via
             the class term)
  overpass   relabel GT `overpass` contacts only  (open point 9 / item 0a)
  serve      relabel GT `serve` contacts only
  all_nonzero=relabel every GT class the pipeline NEVER emits

Nothing in `src/` is touched and no video is decoded: this is pass-2 post-hoc
scoring (AGENTS.md section 6).  The per-contact relabel is a GT-derived
ORACLE and is a CEILING, never a shippable rule -- the point is to size the
lever, not to pretend the oracle is achievable.

Usage:
    venv/bin/python scripts/probe_label_ceilings.py
    venv/bin/python scripts/probe_label_ceilings.py --json output/g3_label_ceilings/probe.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import score_heldout_contacts as sh  # noqa: E402  (path set above)

#: Actions `VolleyballAction` can emit (src/recognition/volleyball_actions.py).
#: `ace` is in the enum but is not a GT class anywhere; `freeball` is a GT
#: class that the enum CANNOT emit (#74d `emitted_vocabulary`).
EMITTABLE = {"dig", "set", "spike", "block", "ace", "serve", "overpass"}

DEFAULT_JSON = "output/g3_label_ceilings/probe.json"

#: The R1 diag dump: 185 `stage == "accepted"` rows.  Its own `action` field
#: IS the G3 label bar (85/139 = 0.612, STATUS #70), so every ceiling must be
#: measured HERE too -- the `pass2` arm scores 0.561 and is not the bar.
MATCH_DIAG = "output/g3r1/match_bw03_diag.jsonl"

#: The PRODUCTION match dump the pass-2 stream derives from
#: (`serve_relabel.generated_from.pipeline`).  Its `action` field is the third
#: recorded G3 baseline (83/141 = 0.589), and unlike the R1 diag it carries the
#: PRODUCTION gate decisions (the diag was run at contact_min_departure_bw=0.3).
MATCH_PRODUCTION = "output/match20260920_posegate/pipeline_output.json"


def dump_actions(dump_path: str = MATCH_PRODUCTION) -> List[Dict[str, Any]]:
    """The `actions` list of a `pipeline_output.json`, as prediction events."""
    blob = json.loads(Path(dump_path).read_text(encoding="utf-8"))
    out = []
    for a in blob.get("actions") or []:
        f = a.get("frame_number")
        if f is None:
            continue
        out.append({"frame": int(f), "action": a.get("action"),
                    "team": a.get("team"), "player_id": a.get("player_id"),
                    "touch_number": a.get("touch_number")})
    out.sort(key=lambda e: e["frame"])
    return out


def diag_accepted(diag_path: str = MATCH_DIAG) -> List[Dict[str, Any]]:
    """The `accepted` contact rows of an R1 diag dump, as prediction events."""
    out: List[Dict[str, Any]] = []
    with open(diag_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            for c in row.get("candidates") or []:
                if c.get("stage") == "accepted":
                    out.append({"frame": int(c["frame"]), "action": c.get("action"),
                                "team": c.get("team"),
                                "player_id": c.get("player_id"),
                                "touch_number": c.get("touch_number")})
    out.sort(key=lambda e: e["frame"])
    return out


def _matched_pairs(gt_ev: List[Dict[str, Any]], pred_ev: List[Dict[str, Any]],
                   fps: float, tolerance_s: float
                   ) -> List[tuple]:
    """[(gt_frame, gt_action, pred_frame, pred_action)] from the REAL matcher.

    Uses `evaluate_timed.match_events` so the pairing can never disagree with
    the headline score.
    """
    import evaluate_timed as et

    timebase = et.TimeBase(fps=fps or 30.0)
    # Normalize through the scorer's own loader so `raw` / `frame_tolerance`
    # survive and the per-event tolerance is identical to the headline run.
    gt = [et.normalize_event(e) for e in gt_ev]
    pr = [et.normalize_event(e) for e in pred_ev]
    match = et.match_events(gt, pr, timebase, base_tolerance_s=tolerance_s)
    return [(g["frame"], g["action"], p["frame"], p["action"])
            for g, p, _d in match["pairs"]]


def apply_relabel(events: List[Dict[str, Any]], relabel: Dict[int, str]
                  ) -> List[Dict[str, Any]]:
    """Copy `events` with `action` overwritten where the frame is in `relabel`.

    A relabel whose prediction frame carries no event is dropped (counted by
    the caller) -- an oracle that invents events would flatter the recall.
    """
    out = []
    for e in events:
        q = dict(e)
        new = relabel.get(int(e["frame"]))
        if new is not None:
            q["action"] = new
        out.append(q)
    return out


def score(events: List[Dict[str, Any]], gt_path: Path, fps: float,
          tolerance_s: float, work: Path, tag: str) -> Dict[str, Any]:
    import evaluate_timed as et

    pred_path = work / f"pred_{tag}.json"
    pred_path.write_text(
        json.dumps(sh.prediction_blob(events, "20260920_match_ari_joan_lost", fps),
                   indent=1) + "\n", encoding="utf-8")
    res = et.evaluate_timed(str(pred_path), str(gt_path),
                            tolerance_s=tolerance_s, ignore_player=True,
                            autonomous=False)
    c = res["contact"]
    return {"precision": c["precision"], "recall": c["recall"], "f1": c["f1"],
            "tp": c["tp"], "fp": c["fp"], "fn": c["fn"],
            "class_accuracy": res["labels"]["class_accuracy"],
            "class_scored": res["labels"]["class_scored"],
            "team_accuracy": res["attribution"]["team_accuracy"]}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--relabel", default=sh.DEFAULT_RELABEL)
    ap.add_argument("--match-gt", default=sh.DEFAULT_MATCH_GT)
    ap.add_argument("--point-from", type=int, default=sh.DEFAULT_FROM)
    ap.add_argument("--point-to", type=int, default=sh.DEFAULT_TO)
    ap.add_argument("--pad", type=int, default=sh.DEFAULT_PAD)
    ap.add_argument("--tolerance-s", type=float, default=0.2)
    ap.add_argument("--workdir", default="output/g3_label_ceilings")
    ap.add_argument("--match-diag", default=MATCH_DIAG)
    ap.add_argument("--match-production", default=MATCH_PRODUCTION)
    ap.add_argument("--json", default=DEFAULT_JSON)
    args = ap.parse_args(argv)

    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)

    # Reuse the held-out scope verbatim (P9-P33, pad 90) so the ceilings are
    # measured on the SAME held-out region every prior number uses.
    blob = sh.run(relabel_path=args.relabel, match_gt=args.match_gt,
                  workdir=str(work), point_from=args.point_from,
                  point_to=args.point_to, pad=args.pad,
                  tolerance_s=args.tolerance_s)
    scope = blob["scope"]
    rel = json.loads(Path(args.relabel).read_text(encoding="utf-8"))
    gt = json.loads(Path(args.match_gt).read_text(encoding="utf-8"))
    scoped_path = work / f"gt_p{args.point_from}_p{args.point_to}.json"
    scoped_gt = json.loads(scoped_path.read_text(encoding="utf-8"))
    fps = float(gt.get("fps") or 0.0)
    lo, hi = scope["region"]
    gt_ev = sh.gt_contacts(scoped_gt)

    actions = sh.scoped_actions(rel.get("actions_pass2") or [], lo, hi)
    pred_arms = {
        "diag": [e for e in diag_accepted(args.match_diag)
                 if lo <= e["frame"] <= hi],
        "production": [e for e in dump_actions(args.match_production)
                       if lo <= e["frame"] <= hi],
        "pass2": sh.arm_events(actions, "pass2"),
    }

    results: Dict[str, Any] = {}
    for arm_name, pred_ev in pred_arms.items():
        pairs = _matched_pairs(gt_ev, pred_ev, fps, args.tolerance_s)
        preds_by_frame = {int(e["frame"]) for e in pred_ev}

        def build(want: str, pairs=pairs) -> Dict[int, str]:
            out: Dict[int, str] = {}
            for gf, ga, pf, _pa in pairs:
                if want == "oracle" or (want == "never_emitted" and ga not in EMITTABLE) \
                   or (ga == want):
                    out[int(pf)] = ga
            return out

        arms: Dict[str, Any] = {}
        for tag in ("base", "oracle", "overpass", "serve", "never_emitted"):
            rl = {} if tag == "base" else build(tag)
            ev = apply_relabel(pred_ev, rl)
            arms[tag] = score(ev, scoped_path, fps, args.tolerance_s,
                              work, f"{arm_name}_{tag}")
            arms[tag]["n_relabeled"] = len(rl)
            arms[tag]["n_relabel_unsatisfiable"] = sum(
                1 for f in rl if f not in preds_by_frame)

        base_rows = [{"gt_frame": gf, "gt_action": ga, "pred_frame": pf,
                      "pred_action": pa, "label_ok": ga == pa}
                     for gf, ga, pf, pa in pairs]
        never = sorted({r["gt_action"] for r in base_rows
                        if r["gt_action"] not in EMITTABLE})
        results[arm_name] = {
            "n_predictions": len(pred_ev),
            "matched_pairs": len(pairs),
            "label_mismatches": sum(1 for r in base_rows if not r["label_ok"]),
            "gt_classes_never_emitted": never,
            "arms": arms,
            "base_rows": base_rows,
        }

    out = {
        "generated_from": {"relabel": args.relabel, "match_gt": args.match_gt,
                           "match_diag": args.match_diag,
                           "match_production": args.match_production},
        "scope": scope,
        "time": blob["time"],
        "arms": results,
        "note": ("every arm is an ORACLE relabel of already-emitted events: a "
                 "CEILING for the lever, never a shippable rule. Only the "
                 "`action` field changes and the matcher is class-agnostic "
                 "(scripts/evaluate_timed.py:296), so tp/fp/fn -- hence the "
                 "contact F1 -- are IDENTICAL across arms by construction; the "
                 "G3 bar moves only through `class_accuracy`."),
    }
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")

    print("=" * 78)
    print("  G3 LABEL-LEVER CEILINGS -- held-out match P9-P33, class accuracy")
    print("=" * 78)
    print(f"  region f{lo}-{hi}   fps {fps:.3f}   tolerance "
          f"{out['time']['effective_tolerance_f']}f")
    for arm_name, res in results.items():
        b = res["arms"]["base"]
        print()
        print(f"  [{arm_name}]  {res['n_predictions']} predictions   "
              f"{res['matched_pairs']} matched   "
              f"{res['label_mismatches']} label mismatches   "
              f"never-emitted classes: {res['gt_classes_never_emitted'] or 'none'}")
        print(f"  {'arm':<16}{'cls':>8}{'n/139':>8}{'F1':>8}{'P':>8}{'R':>8}"
              f"{'TP':>5}{'FP':>5}{'relabel':>9}")
        for tag, a in res["arms"].items():
            n_ok = round((a["class_accuracy"] or 0) * a["class_scored"])
            print(f"  {tag:<16}{a['class_accuracy']:>8.4f}{n_ok:>4d}/{a['class_scored']:<3d}"
                  f"{a['f1']:>8.3f}{a['precision']:>8.3f}{a['recall']:>8.3f}"
                  f"{a['tp']:>5d}{a['fp']:>5d}{a['n_relabeled']:>9d}")
        print(f"  {'-> overpass':<16}{res['arms']['overpass']['class_accuracy'] - b['class_accuracy']:>+8.4f}"
              f"   {'-> oracle':<12}{res['arms']['oracle']['class_accuracy'] - b['class_accuracy']:>+8.4f}")
    print("=" * 78)
    print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
