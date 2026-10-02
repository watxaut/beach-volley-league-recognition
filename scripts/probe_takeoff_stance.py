#!/usr/bin/env python3
"""SR1c -- would judging ``behind_baseline`` on the TAKEOFF STANCE recover the
near serves P9-P12 (open point 30, mechanism M-a)?

Diagnose-only.  Nothing under ``src/`` is touched: the real test
(``CourtCalibration.is_behind_baseline``) is imported and called, and the
pipeline is never re-run here.  The question is only what the SAME decisions
would have read if the foot were taken from the K frames BEFORE the contact
instead of the contact frame itself -- SR1b measured that at P9-P12 the
airborne/landing foot projects 0.8-24.5 px inside the threshold.

What it does, per diag-dump session (the dump is the only input; no decode):

1. **Reproduction gate.** For every ``candidate_passed_gates`` record the
   contact-frame read (``K = 0``) is recomputed and compared with the
   ``behind_baseline`` the classifier actually emitted.  If that does not
   reproduce, nothing downstream means anything.
2. **Sweep.** The same read over a ``[c-K, c]`` window, taking the foot with
   the max y for team A (near, behind the bottom line) / min y for team B
   (far, behind the top line).  Predicted (coasted) track frames are skipped:
   a held-out-of-court track is frozen and would pin the read.
3. **First-order flip simulation.** An EMITTED action becomes ``serve`` iff it
   is a ``spike``/``dig``, ``rally_start`` holds (gap to the previous emitted
   contact > 90 f, or it is the first), the shipped read was false and the
   ``K``-window read is true.  No cascade: the flip is scored on its own.
4. **Scoring.** Every flip is bucketed against the owner GT within +-15 f,
   side-correct, with the scorer (``scripts/score_serves.py``) imported, never
   re-implemented: ``recovered`` (a GT serve of that side not already hit by a
   production serve), ``false_breaks_gt`` (a GT non-serve contact inside the
   tolerance), ``false_dead_time`` (no GT contact at all inside it).

K = 10 is the pre-registered rule; K = 5 and 15 are reported as sensitivity
and decide nothing.  Usage::

    venv/bin/python scripts/probe_takeoff_stance.py
    venv/bin/python scripts/probe_takeoff_stance.py --k 10 --json output/sr1c/x.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import score_serves as ss  # noqa: E402  (path set above)

REPO = Path(__file__).resolve().parent.parent

#: The pre-registered window.  Not re-tunable: SR1b measured the feet 6-12 px
#: past the line "seven frames later", so the window has to span the airborne
#: phase, and the serve's contact geometry is ~10 f from takeoff at this fps.
K_PREREGISTERED = 10
#: Reported, never used to decide.
K_SENSITIVITY: Tuple[int, ...] = (5, 15)
ALL_K: Tuple[int, ...] = (0,) + K_SENSITIVITY + (K_PREREGISTERED,)

#: The rally reset the resolver itself uses (`ActionContextResolver`).
RALLY_RESET_GAP = 90
#: Actions that can flip to ``serve`` (``_decide``: ATTACK -> SPIKE, bump -> DIG).
FLIPPABLE = ("spike", "dig")
TOLERANCE = ss.DEFAULT_TOLERANCE

MATCH_DIAG = "output/sr1c/match_full_diag.jsonl"
MATCH_CALIB = "calibrations/20260920_match_ari_joan_lost.json"
ENTRENO_CALIB = "calibrations/video_entreno_{n}.json"


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------

def sessions(diag_root: str = "output/sr1") -> List[Dict[str, Any]]:
    """The eight dump sessions: the match plus the seven entreno clips."""
    out = [{
        "key": "match_20260920",
        "label": "20260920 match (720p->up1080, 25.67 fps VFR)",
        "diag": MATCH_DIAG,
        "calibration": MATCH_CALIB,
    }]
    for n in range(1, 8):
        out.append({
            "key": f"entreno_{n}",
            "label": f"video_entreno_{n}",
            "diag": f"{diag_root}/entreno_{n}_diag.jsonl",
            "calibration": ENTRENO_CALIB.format(n=n),
        })
    return out


# ---------------------------------------------------------------------------
# the read itself
# ---------------------------------------------------------------------------

def foot_of(player: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    """The foot point, built exactly as ``ActionClassifier._build_contact`` does.

    ``int()`` truncation included: the shipped value is the one being
    reproduced, so a "cleaner" float foot would make the reproduction gate
    measure the probe instead of the pipeline.
    """
    bbox = player.get("bbox")
    if not bbox or len(bbox) < 4:
        return None
    return (int((bbox[0] + bbox[2]) / 2), int(bbox[3]))


def window_feet(frames: Dict[int, Dict[str, Any]], track_id: Any,
                contact_frame: int, k: int) -> List[Tuple[int, Tuple[int, int]]]:
    """``(frame, foot)`` for ``track_id`` over ``[c-k, c]``, predicted skipped.

    A coasted (predicted) frame carries the frozen last box, so it would pin
    the stance to a place the player is not; those frames are dropped, not
    clamped.
    """
    out: List[Tuple[int, Tuple[int, int]]] = []
    for t in range(contact_frame - k, contact_frame + 1):
        for player in (frames.get(t) or {}).get("players") or []:
            if player.get("track_id") != track_id:
                continue
            if bool(player.get("predicted", False)):
                continue
            foot = foot_of(player)
            if foot is not None:
                out.append((t, foot))
    return out


def stance_foot(feet: Sequence[Tuple[int, Tuple[int, int]]],
                team: Optional[str]) -> Optional[Tuple[int, int]]:
    """The stance foot over a window: max y for team A, min y for team B.

    A = near = behind the BOTTOM line, so the deepest foot of the window is
    the one that can read behind it; B is the mirror.  ``None`` when the team
    is unknown or the window held no usable frame.
    """
    if not feet or team not in ("A", "B"):
        return None
    pick = max if team == "A" else min
    return pick(foot for _, foot in feet)


def behind_baseline_at_k(court: Any, frames: Dict[int, Dict[str, Any]],
                         track_id: Any, contact_frame: int, team: Optional[str],
                         k: int) -> Dict[str, Any]:
    """``is_behind_baseline`` on the ``k``-frame stance foot, via the real class."""
    feet = window_feet(frames, track_id, contact_frame, k)
    foot = stance_foot(feet, team)
    if foot is None:
        return {"behind_baseline": False, "foot": None, "frames_used": len(feet)}
    return {"behind_baseline": bool(court.is_behind_baseline(foot, team)),
            "foot": [int(foot[0]), int(foot[1])], "frames_used": len(feet)}


# ---------------------------------------------------------------------------
# the dump
# ---------------------------------------------------------------------------

def load_court(calibration: str) -> Any:
    from src.detection.court_calibration import CourtCalibration

    path = REPO / calibration
    if not path.exists():
        raise FileNotFoundError(f"missing calibration {calibration}")
    court = CourtCalibration(calibration_path=str(path))
    if not court.is_calibrated:
        raise RuntimeError(f"calibration did not load: {calibration}")
    return court


def candidate_records(frames: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every ``candidate_passed_gates`` record, keyed by its own contact frame."""
    out = []
    for frame in sorted(frames):
        for cand in (frames[frame] or {}).get("candidates") or []:
            if cand.get("stage") != "candidate_passed_gates":
                continue
            c = cand.get("frame")
            if c is None:
                continue
            out.append({
                "frame": int(c),
                "track_id": cand.get("track_id"),
                "team": cand.get("team"),
                "gesture": cand.get("gesture"),
                "kind": cand.get("kind"),
                "shipped_behind_baseline": bool(cand.get("behind_baseline")),
                "contact_point": cand.get("contact_point"),
            })
    out.sort(key=lambda r: (r["frame"], str(r["track_id"])))
    return out


def emitted_actions(frames: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Emitted actions, de-duplicated and chronological (``frame_number``)."""
    seen, out = set(), []
    for frame in sorted(frames):
        for action in (frames[frame] or {}).get("actions") or []:
            key = action.get("frame_number")
            if key is None or key in seen:
                continue
            seen.add(key)
            out.append(dict(action))
    out.sort(key=lambda a: a["frame_number"])
    return out


def rally_start_flags(actions: Sequence[Dict[str, Any]],
                      gap: int = RALLY_RESET_GAP) -> Dict[int, bool]:
    """``rally_start`` per emitted contact, the resolver's own rule."""
    flags, prev = {}, None
    for action in actions:
        frame = int(action["frame_number"])
        flags[frame] = True if prev is None else (frame - prev) > gap
        prev = frame
    return flags


# ---------------------------------------------------------------------------
# the flip rule (pure)
# ---------------------------------------------------------------------------

def flips_to_serve(action: Dict[str, Any], rally_start: bool,
                   shipped_behind_baseline: bool, bb_k: bool) -> bool:
    """The pre-registered first-order flip rule (no cascade)."""
    return (str(action.get("action")) in FLIPPABLE
            and bool(rally_start)
            and not bool(shipped_behind_baseline)
            and bool(bb_k))


def simulate_flips(records: Sequence[Dict[str, Any]],
                   actions: Sequence[Dict[str, Any]],
                   by_contact: Dict[Tuple[int, Any], Dict[str, Any]],
                   flags: Dict[int, bool], k: int) -> Tuple[List[Dict[str, Any]],
                                                             List[Dict[str, Any]]]:
    """``(flips, unmatched)`` for window ``k``."""
    flips, unmatched = [], []
    for action in actions:
        frame = int(action["frame_number"])
        record = by_contact.get((frame, action.get("track_id")))
        if record is None:
            unmatched.append({"frame": frame, "action": action.get("action"),
                              "track_id": action.get("track_id")})
            continue
        bb = record["bb"].get(str(k))
        if bb is None:
            continue
        if flips_to_serve(action, flags.get(frame, False),
                          record["shipped_behind_baseline"], bb):
            flips.append({
                "frame": frame,
                "action": action.get("action"),
                "track_id": record["track_id"],
                "team": record["team"],
                "gesture": record["gesture"],
                "stance_foot": record["bb_detail"].get(str(k), {}).get("foot"),
                "stance_frames_used": record["bb_detail"].get(str(k), {}).get("frames_used"),
                "contact_foot": record["bb_detail"].get("0", {}).get("foot"),
                "shipped_behind_baseline": record["shipped_behind_baseline"],
            })
    flips.sort(key=lambda f: f["frame"])
    return flips, unmatched


# ---------------------------------------------------------------------------
# GT scoring (pure)
# ---------------------------------------------------------------------------

def classify_flip(frame: int, side: Optional[str], gt_rows: Sequence[Dict[str, Any]],
                  gt_contacts: Sequence[Dict[str, Any]],
                  emitted_serves: Sequence[Dict[str, Any]],
                  tolerance: int = TOLERANCE) -> Dict[str, Any]:
    """Bucket one flip against the owner GT.

    ``recovered``  a GT serve of the SAME side inside the tolerance that no
                   production serve already covers (a second emission on a
                   serve already hit is not a recovery).
    ``false_breaks_gt``  a GT NON-serve contact inside the tolerance.
    ``false_dead_time``  no GT contact at all inside it.
    Anything else (a GT serve of the OTHER side, or one already hit) is
    reported as ``gt_serve_not_recovered`` rather than folded into one of the
    three -- it is a flip that is not a recovery either way.
    """
    rows = []
    for row in gt_rows:
        delta = int(row["frame"]) - frame
        if abs(delta) <= int(row.get("tolerance") or tolerance):
            rows.append((abs(delta), row, delta))
    serves = [r for r in rows if r[1].get("side") == side]
    already = [s for s in emitted_serves
               if s.get("side") == side and abs(int(s["frame"]) - frame) <= tolerance]

    contacts = []
    for contact in gt_contacts:
        delta = int(contact["frame"]) - frame
        if abs(delta) <= tolerance:
            contacts.append((abs(delta), contact, delta))
    contacts.sort(key=lambda c: c[0])

    if serves and not already:
        best = min(serves, key=lambda s: s[0])
        return {"bucket": "recovered", "gt_frame": int(best[1]["frame"]),
                "gt_point": best[1].get("point"), "gt_squad": best[1].get("squad"),
                "delta_f": best[2]}
    non_serve = [c for c in contacts if ss._action_of(c[1]) != "serve"]
    if non_serve:
        best = non_serve[0]
        return {"bucket": "false_breaks_gt", "gt_frame": int(best[1]["frame"]),
                "gt_point": best[1].get("point"),
                "gt_action": ss._action_of(best[1]), "delta_f": best[2]}
    if not contacts:
        return {"bucket": "false_dead_time", "gt_frame": None, "gt_point": None}
    best = contacts[0]
    return {"bucket": "gt_serve_not_recovered",
            "gt_frame": int(best[1]["frame"]), "gt_point": best[1].get("point"),
            "gt_action": ss._action_of(best[1]), "delta_f": best[2],
            "already_hit_by_production_serve": bool(already)}


# ---------------------------------------------------------------------------
# per-session run
# ---------------------------------------------------------------------------

def gt_side_letter(team: Optional[str]) -> Optional[str]:
    """Court-side letter -> owner side word (A = near), via the scorer."""
    return ss.rs.side_letter_to_court(team)


def gt_for_session(key: str) -> Dict[str, Any]:
    """GT rows + GT contacts for a session key, through the scorer loaders."""
    if key == "match_20260920":
        session = ss.build_match_session()
    else:
        session = ss.build_entreno_session(int(key.rsplit("_", 1)[1]))
    blob = ss._read(session["gt"])
    if blob is None:
        raise FileNotFoundError(f"missing GT for {key}: {session['gt']}")
    contacts = []
    for event in ss.contact_gt_events(blob):
        contacts.append({
            "frame": ss._frame_of(event),
            "action": ss._action_of(event),
            "point": event.get("point"),
            "side": event.get("owner_side"),
            "squad": event.get("player_team"),
        })
    rows = ss.serve_rows_from_contact_gt(
        blob, split_of=session.get("split_of"),
        squad_to_side=session.get("squad_to_side"))
    return {"rows": rows, "contacts": contacts}


def run_session(session: Dict[str, Any], ks: Sequence[int] = ALL_K,
                dump_frames: Optional[Dict[int, Dict[str, Any]]] = None,
                frames: Optional[Dict[int, Dict[str, Any]]] = None,
                gt: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Sweep every window for one session."""
    from src.utils.diagnostics import load_diag

    if frames is None:
        frames = load_diag(str(REPO / session["diag"]))["frames"]
    if gt is None:
        gt = gt_for_session(session["key"])
    court = load_court(session["calibration"])

    records = candidate_records(frames)
    swept = []
    for record in records:
        bb, bb_detail = {}, {}
        for k in ks:
            read = behind_baseline_at_k(court, frames, record["track_id"],
                                        record["frame"], record["team"], k)
            bb[str(k)] = read["behind_baseline"]
            bb_detail[str(k)] = read
        swept.append(dict(record, bb=bb, bb_detail=bb_detail))

    agree = sum(1 for r in swept if r["bb"]["0"] == r["shipped_behind_baseline"])
    by_contact: Dict[Tuple[int, Any], Dict[str, Any]] = {}
    for r in swept:
        by_contact.setdefault((r["frame"], r["track_id"]), r)

    actions = emitted_actions(frames)
    flags = rally_start_flags(actions)
    emitted_serves = [{"frame": int(a["frame_number"]),
                       "side": gt_side_letter(a.get("team"))}
                      for a in actions if a.get("action") == "serve"]

    per_k = {}
    for k in ks:
        flips, unmatched = simulate_flips(swept, actions, by_contact, flags, k)
        scored = []
        for flip in flips:
            side = gt_side_letter(flip["team"])
            bucket = classify_flip(flip["frame"], side, gt["rows"], gt["contacts"],
                                   emitted_serves)
            scored.append(dict(flip, side=side, **bucket))
        per_k[str(k)] = {
            "flips": scored,
            "unmatched_actions": unmatched,
            "counts": {b: sum(1 for f in scored if f["bucket"] == b)
                       for b in ("recovered", "false_breaks_gt", "false_dead_time",
                                 "gt_serve_not_recovered")},
            "recovered_points": sorted({f["gt_point"] for f in scored
                                        if f["bucket"] == "recovered"
                                        and f["gt_point"] is not None}),
        }

    return {
        "key": session["key"],
        "label": session["label"],
        "diag": session["diag"],
        "calibration": session["calibration"],
        "records": len(swept),
        "reproduction": {"agree": agree, "total": len(swept),
                         "rate": round(agree / len(swept), 4) if swept else None,
                         "passes_98pct": bool(swept) and agree / len(swept) >= 0.98,
                         "mismatches": [
                             {"frame": r["frame"], "track_id": r["track_id"],
                              "team": r["team"], "shipped": r["shipped_behind_baseline"],
                              "bb_0": r["bb"]["0"],
                              "foot": r["bb_detail"]["0"]["foot"],
                              "frames_used": r["bb_detail"]["0"]["frames_used"]}
                             for r in swept
                             if r["bb"]["0"] != r["shipped_behind_baseline"]]},
        "emitted_actions": len(actions),
        "emitted_serves": len(emitted_serves),
        "per_k": per_k,
        "sweep": swept,
    }


def fmt_per_k(report: Dict[str, Any], k: int) -> str:
    cell = report["per_k"][str(k)]
    c = cell["counts"]
    points = ", ".join(str(p) for p in cell["recovered_points"]) or "-"
    return (f"recovered {c['recovered']} (P{points}) | false_breaks_gt "
            f"{c['false_breaks_gt']} | false_dead_time {c['false_dead_time']} | "
            f"gt_serve_not_recovered {c['gt_serve_not_recovered']}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--k", type=int, default=K_PREREGISTERED)
    ap.add_argument("--diag-root", default="output/sr1")
    ap.add_argument("--only", default=None, help="one session key")
    ap.add_argument("--json", default="output/sr1c/takeoff_stance.json")
    ap.add_argument("--table", action="store_true", help="print every record")
    args = ap.parse_args(argv)

    report = {
        "preregistered_k": args.k,
        "sensitivity_k": list(K_SENSITIVITY),
        "rally_reset_gap": RALLY_RESET_GAP,
        "tolerance": TOLERANCE,
        "sessions": [],
    }
    for session in sessions(args.diag_root):
        if args.only and session["key"] != args.only:
            continue
        path = REPO / session["diag"]
        if not path.exists():
            print(f"-- skip {session['key']}: no dump at {session['diag']}")
            continue
        print(f"== {session['key']} ({session['diag']})", flush=True)
        result = run_session(session)
        report["sessions"].append(result)
        rep = result["reproduction"]
        print(f"   records {result['records']}  emitted {result['emitted_actions']} "
              f"(serves {result['emitted_serves']})")
        print(f"   G2 reproduction bb_0 == shipped: {rep['agree']}/{rep['total']} "
              f"= {rep['rate']}  -> {'PASS' if rep['passes_98pct'] else 'FAIL'}")
        for k in sorted({args.k, *K_SENSITIVITY, 0}):
            tag = "PREREG" if k == args.k else "sens"
            print(f"   K={k:<3} [{tag}] {fmt_per_k(result, k)}")

        if args.table:
            for row in result["sweep"]:
                print("   ", row["frame"], row["track_id"], row["team"],
                      row["gesture"], "shipped", row["shipped_behind_baseline"],
                      {k: v["foot"] for k, v in row["bb_detail"].items()})

    match = next((s for s in report["sessions"] if s["key"] == "match_20260920"), None)
    entrenos = [s for s in report["sessions"] if s["key"] != "match_20260920"]
    if match is not None:
        cell = match["per_k"][str(args.k)]
        c = cell["counts"]
        target = {9, 10, 11, 12}
        hit = target & set(cell["recovered_points"])
        entreno_false = sum(
            f["per_k"][str(args.k)]["counts"]["false_breaks_gt"]
            + f["per_k"][str(args.k)]["counts"]["false_dead_time"]
            + f["per_k"][str(args.k)]["counts"]["gt_serve_not_recovered"]
            for f in entrenos)
        verdict = {
            "recovered_of_P9_P12": sorted(hit),
            "n_recovered_of_P9_P12": len(hit),
            "match_false_breaks_gt": c["false_breaks_gt"],
            "match_false_dead_time": c["false_dead_time"],
            "entreno_false_flips": entreno_false,
            "rule": (f"PASS = >=3 of P9-P12 recovered AND match false_breaks_gt == 0 "
                     f"AND match false_dead_time <= 1 AND entreno false flips == 0 "
                     f"(K = {args.k})"),
        }
        verdict["PASS"] = bool(
            len(hit) >= 3 and c["false_breaks_gt"] == 0
            and c["false_dead_time"] <= 1 and entreno_false == 0)
        verdict["gates"] = {
            s["key"]: s["reproduction"]["passes_98pct"] for s in report["sessions"]}
        report["verdict"] = verdict
        print("\nVERDICT", "PASS" if verdict["PASS"] else "FAIL")
        print(f"  recovered of P9-P12: {verdict['recovered_of_P9_P12']} "
              f"(n={verdict['n_recovered_of_P9_P12']}/4)")
        print(f"  match false_breaks_gt {verdict['match_false_breaks_gt']}, "
              f"false_dead_time {verdict['match_false_dead_time']}, "
              f"entreno false flips {verdict['entreno_false_flips']}")

    out = REPO / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())