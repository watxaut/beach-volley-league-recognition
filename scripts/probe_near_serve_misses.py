#!/usr/bin/env python3
"""SR1 -- the near-serve MISS taxonomy: where a serve the owner marked is not
emitted as a ``serve`` (open point 30, task SR1).

Diagnose-only.  No mechanism is designed here and nothing under ``src/`` is
touched: the task is to name the first failing stage for every missed near
serve, so the next mechanism is chosen against evidence instead of taste.

Three buckets, from the artifacts alone (no decode, default mode), and one
optional deepening stage from a production ``--diag-dump`` (``--diag``):

``label``           a contact WAS emitted at the serve frame, with another
                    action (``spike`` / ``dig`` / ...).  Perception worked; the
                    GESTURE is what failed.
``off_tolerance``   a contact was emitted near the serve, outside +-15 f.
                    Timing/placement, not label.
``no_contact``      nothing was emitted within ``--search-f``.  The contact
                    itself died, and only the diag dump can say at which stage
                    (detection -> admission -> candidate -> gate).

The scorer (``scripts/score_serves.py``) is imported, never re-implemented: the
tolerance, the side vocabulary, the dev/held-out split and the session registry
all come from there, so the two can never disagree about what a miss is.  SR0
already measured that every near serve production DOES emit lands within +-2 f,
which is why the first bucket turns out to be the big one.

Usage::

    venv/bin/python scripts/probe_near_serve_misses.py                 # match
    venv/bin/python scripts/probe_near_serve_misses.py --session match_20260920
    venv/bin/python scripts/probe_near_serve_misses.py --session entreno_2 \\
        --diag output/sr1/entreno_2_diag.jsonl
    venv/bin/python scripts/probe_near_serve_misses.py --json output/serves/sr1.json

``--emit-diag`` is the one mode that decodes: a SEQUENTIAL production pass with
``--diag-dump`` on, used to name the stage for the ``no_contact`` cases.  It
never seeks (AGENTS.md §9) and it re-checks prefix parity against the committed
``pipeline_output.json`` before its dump is trusted -- a prefix run is only
evidence if the actions it reproduced are the ones the shipped artifact has.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import score_serves as ss  # noqa: E402  (path set above)
import waterfall as wf  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

#: How far to look for a contact that is merely misplaced.
DEFAULT_SEARCH_F = 80
#: The contact tolerance (the owner frames carry their own; this is the fallback
#: and the fallback the serve score uses too).
TOLERANCE = ss.DEFAULT_TOLERANCE
#: ``ActionContextResolver.rally_reset_gap`` -- the dead-time gap that makes a
#: contact a RALLY START.  The serve label needs BOTH ``rally_start`` and
#: ``behind_baseline`` (action_context._decide), so the two are what SR1 has to
#: tell apart in every label miss.
RALLY_RESET_GAP = 90


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------

def _read(path: str) -> Optional[Dict[str, Any]]:
    p = REPO / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def load_actions(pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Emitted contacts, with the side letter resolved once."""
    out = []
    for action in pipeline.get("actions") or []:
        frame = action.get("frame_number", action.get("frame"))
        if frame is None:
            continue
        out.append({**action, "frame_number": int(frame),
                    "side": ss.rs.side_letter_to_court(action.get("team"))})
    out.sort(key=lambda a: a["frame_number"])
    return out


def load_pass2(relabel: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """pass-2 decisions keyed by contact frame (the S3 relabel artifact)."""
    return {int(a["frame_number"]): a
            for a in (relabel.get("actions_pass2") or [])
            if a.get("frame_number") is not None}


def session_artifacts(session: Dict[str, Any]) -> Dict[str, Any]:
    """The pipeline / relabel / score artifacts of one scorer session."""
    if session["key"] == "match_20260920":
        return {"pipeline": _read(ss.MATCH_PIPELINE),
                "relabel": _read(ss.MATCH_RELABEL),
                "score": _read("output/serves/sr0.json")}
    match = re.search(r"entreno_(\d)", session["key"])
    n = match.group(1) if match else "?"
    return {"pipeline": _read(f"output/sr1/entreno_{n}/pipeline_output.json")
            or _read(f"output/video_entreno_{n}/pipeline_output.json"),
            "relabel": None,
            "score": None}


# ---------------------------------------------------------------------------
# the one decoding mode: a sequential production diag pass
# ---------------------------------------------------------------------------

def sequential_diag_pass(video: str, calibration: Optional[str],
                         end_frame: int, diag_path: str,
                         device: str = "mps") -> Dict[str, Any]:
    """Decode ``[0, end_frame]`` SEQUENTIALLY with ``--diag-dump`` on.

    One ``FrameProcessor``, production config (fine-tuned ball model included),
    no seek anywhere (AGENTS.md §9).  A prefix run is causal -- it sees exactly
    what the full run saw -- so the dump is trustworthy ONLY if it reproduces the
    committed actions, which is asserted here and reported as ``parity``.
    """
    import cv2

    from src.analysis.frame_processor import FrameProcessor
    from score_serve_events import production_config

    config = production_config(device)
    if calibration:
        config["court_calibration_path"] = str(REPO / calibration)
    config["diag_dump"] = str(REPO / diag_path)

    cap = cv2.VideoCapture(str(REPO / video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {video}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    processor = FrameProcessor(config)
    processor.setup_video_fps(fps)
    processor.setup_video_dimensions(width, height)

    actions: List[Dict[str, Any]] = []
    frame = 0
    t0 = time.time()
    while frame <= end_frame:
        ok, image = cap.read()
        if not ok:
            break
        result = processor.process_frame(image, frame)
        actions.extend(result.get("actions") or [])
        frame += 1
        if frame % 1000 == 0:
            rate = frame / max(1e-9, time.time() - t0)
            print(f"  f{frame}  {time.time() - t0:.0f}s  {rate:.1f} fps", flush=True)
    cap.release()
    for action in processor.flush_actions() or []:
        actions.append(action)
    closer = getattr(processor, "close_diagnostics", None)
    if closer:
        closer()

    return {"video": video, "end_frame": end_frame, "fps": fps,
            "resolution": [width, height], "device": device,
            "diag_dump": diag_path, "actions": actions,
            "seconds": round(time.time() - t0, 1)}


def prefix_parity(actions: Sequence[Dict[str, Any]], reference: Sequence[Dict[str, Any]],
                  end_frame: int) -> Dict[str, Any]:
    """Did the prefix run reproduce the shipped artifact's actions?

    Compared on (contact frame, action, team) because that is what every serve
    and contact score reads.  A mismatch does not void the run by itself (MPS
    jitter can flip a gesture label, AGENTS.md device caveat) but it is REPORTED
    and never hidden.
    """
    def key(a: Dict[str, Any]) -> Optional[Tuple[int, str, str]]:
        frame = a.get("frame_number", a.get("frame"))
        if frame is None:
            return None
        return (int(frame), str(a.get("action")), str(a.get("team")))

    got = [k for k in (key(a) for a in actions) if k and k[0] <= end_frame]
    want = [k for k in (key(a) for a in reference) if k and k[0] <= end_frame]
    same = sorted(got) == sorted(want)
    return {"actions_in_prefix": len(got), "reference_actions_in_prefix": len(want),
            "identical": same,
            "only_in_run": sorted(set(got) - set(want))[:10],
            "only_in_reference": sorted(set(want) - set(got))[:10]}


def emit_diag(video: str, calibration: Optional[str], end_frame: int,
              diag_path: str, reference: Optional[str], device: str) -> Dict[str, Any]:
    run = sequential_diag_pass(video, calibration, end_frame, diag_path, device)
    parity = None
    if reference:
        ref_blob = _read(reference)
        if ref_blob:
            parity = prefix_parity(run["actions"], ref_blob.get("actions") or [],
                                   end_frame)
    run.pop("actions", None)
    run["parity_vs_reference"] = parity
    return run


# ---------------------------------------------------------------------------
# the taxonomy
# ---------------------------------------------------------------------------

def serve_gate_evidence(frame: int, actions: Sequence[Dict[str, Any]],
                        diag_frames: Optional[Dict[int, Any]] = None,
                        gap: int = RALLY_RESET_GAP) -> Dict[str, Any]:
    """Which of the serve label's TWO conditions failed (``behind_baseline`` vs
    ``rally_start``).

    ``ActionContextResolver._decide`` emits SERVE only when
    ``behind_baseline and rally_start``; every other bump-serve contact falls to
    DIG and every other attack contact to SPIKE.  So a label miss is always one
    (or both) of those two, and the two have completely different fixes.

    ``rally_start`` is INFERRED from the gap to the previous emitted contact
    (the same rule the resolver applies), and ``behind_baseline`` is MEASURED
    from the diag dump's ``candidate_passed_gates`` record when one is supplied.
    Inference is labelled as such and never dressed up as a measurement.
    """
    previous = [a["frame_number"] for a in actions
                if a["frame_number"] < frame]
    gap_f = frame - max(previous) if previous else None
    rally_start = True if gap_f is None else gap_f > gap
    behind_baseline = None
    if diag_frames is not None:
        record = diag_frames.get(frame) or {}
        for candidate in record.get("candidates") or []:
            if candidate.get("stage") == "candidate_passed_gates":
                behind_baseline = candidate.get("behind_baseline")
                break
    if rally_start and behind_baseline:
        verdict = "both_conditions_met_but_no_serve_LABEL_BUG"
    elif behind_baseline is None:
        verdict = "behind_baseline_false" if rally_start else "rally_start_false"
    else:
        verdict = ("behind_baseline_false" if not behind_baseline
                   else "rally_start_false")
    return {"gap_to_prev_contact_f": gap_f, "rally_start_inferred": rally_start,
            "behind_baseline_measured": behind_baseline, "verdict": verdict}


def load_diag_frames(diag_path: Optional[str]) -> Optional[Dict[int, Any]]:
    if not diag_path or not (REPO / diag_path).exists():
        return None
    from src.utils.diagnostics import load_diag

    return load_diag(diag_path)["frames"]


def diag_coverage(diag_frames: Optional[Dict[int, Any]]) -> Optional[Tuple[int, int]]:
    """``(first, last)`` frame a dump actually covers, or None.

    A prefix dump covers a SPAN.  Without this check a GT serve past its end
    looks exactly like a serve whose window has no diagnostic records, i.e. a
    detection failure -- the first version of this probe reported 6 phantom
    `1_raw_detection` stages that way.
    """
    if not diag_frames:
        return None
    frames = [f for f in diag_frames if f >= 0]
    return (min(frames), max(frames)) if frames else None


def classify_miss(gt: Dict[str, Any], actions: Sequence[Dict[str, Any]],
                  pass2: Dict[int, Dict[str, Any]], search_f: int = DEFAULT_SEARCH_F,
                  context_f: int = 200,
                  diag_frames: Optional[Dict[int, Any]] = None) -> Dict[str, Any]:
    """Why this GT serve did not come out as an emitted ``serve``.

    The order matters and is the point of the script: a contact INSIDE the
    tolerance is a label failure even if a misplaced one also exists, and a
    contact outside it is a timing failure even if something was emitted in the
    same dead-time episode.
    """
    frame = gt["frame"]
    tolerance = gt.get("tolerance") or TOLERANCE
    inside = [a for a in actions
              if abs(a["frame_number"] - frame) <= tolerance
              and a["side"] == gt["side"]]
    same_side = sorted((a for a in actions
                        if abs(a["frame_number"] - frame) <= search_f
                        and a["side"] == gt["side"]),
                       key=lambda a: abs(a["frame_number"] - frame))
    other_side = sorted((a for a in actions
                         if abs(a["frame_number"] - frame) <= search_f
                         and a["side"] not in (None, gt["side"])),
                        key=lambda a: abs(a["frame_number"] - frame))
    context = sorted((a for a in actions if abs(a["frame_number"] - frame) <= context_f),
                     key=lambda a: abs(a["frame_number"] - frame))

    if any(a["action"] == "serve" for a in inside):
        return {"bucket": "hit", "detail": "a serve action is inside the tolerance"}

    if inside:
        first = min(inside, key=lambda a: abs(a["frame_number"] - frame))
        bucket = "label"
        detail = (f"emitted {first['action']} (gesture {first.get('gesture')}, "
                  f"kind {first.get('contact_kind')}, touch "
                  f"{first.get('touch_number')}) at f{first['frame_number']} "
                  f"({first['frame_number'] - frame:+d} f)")
        gate = serve_gate_evidence(first["frame_number"], actions, diag_frames)
    elif same_side:
        first = same_side[0]
        bucket = "off_tolerance"
        detail = (f"nearest same-side emitted contact {first['action']} at "
                  f"f{first['frame_number']} ({first['frame_number'] - frame:+d} f), "
                  f"outside the +-{tolerance} f tolerance")
    elif other_side:
        bucket = "other_side_contact"
        detail = (f"no same-side contact within +-{search_f} f; the nearest contact "
                  f"is on the OTHER side ({other_side[0]['action']} at "
                  f"f{other_side[0]['frame_number']}, "
                  f"{other_side[0]['frame_number'] - frame:+d} f)")
    else:
        bucket = "no_contact"
        detail = f"no emitted contact within +-{search_f} f"

    # What pass-2 made of it (relabel / owner demotion): context, never the
    # answer -- S0b broke 3 correct dig labels when pass-2 was treated as truth.
    p2 = [a for a in context if pass2.get(a["frame_number"], {}).get("pass2_action")
          or pass2.get(a["frame_number"], {}).get("pass2_demoted")]
    false_serves = [{"frame": a["frame_number"],
                     "delta_f": a["frame_number"] - frame,
                     "source": pass2.get(a["frame_number"], {}).get("pass2_source")}
                    for a in context
                    if a["action"] == "serve"
                    and pass2.get(a["frame_number"], {}).get("pass2_demoted")]
    out = {
        "bucket": bucket,
        "detail": detail,
        "first_contact": None if not same_side else {
            "frame": same_side[0]["frame_number"],
            "action": same_side[0]["action"],
            "gesture": same_side[0].get("gesture"),
            "delta_f": same_side[0]["frame_number"] - frame},
        "nearest_other_side_contact": None if not other_side else {
            "frame": other_side[0]["frame_number"],
            "action": other_side[0]["action"],
            "gesture": other_side[0].get("gesture"),
            "side": other_side[0].get("side"),
            "delta_f": other_side[0]["frame_number"] - frame},
        "contacts_in_tolerance": [
            {"frame": a["frame_number"], "action": a["action"],
             "gesture": a.get("gesture"), "team": a.get("team"),
             "touch_number": a.get("touch_number"),
             "rally_id": a.get("rally_id"),
             "delta_f": a["frame_number"] - frame}
            for a in inside],
        "pass2_changed_nearby": [
            {"frame": a["frame_number"],
             "action": a["action"],
             "pass2_action": pass2[a["frame_number"]].get("pass2_action"),
             "pass2_source": pass2[a["frame_number"]].get("pass2_source"),
             "pass2_demoted": bool(pass2[a["frame_number"]].get("pass2_demoted")),
             "delta_f": a["frame_number"] - frame}
            for a in p2],
        "owner_false_serve_nearby": false_serves,
    }
    if bucket == "label":
        out["serve_gate"] = gate
    return out


def diag_stage(gt: Dict[str, Any], diag_path: str,
               tolerance: int = TOLERANCE) -> Optional[Dict[str, Any]]:
    """First failing stage from a production diag dump (``scripts/waterfall.py``).

    Imported rather than re-implemented: the stage vocabulary and the reason
    strings must be the same ones the T4 waterfall reports, or the two
    taxonomies cannot be compared.

    Returns ``None`` when the dump does not cover this contact's window: a
    partial dump must never be read as "nothing happened there".
    """
    from src.utils.diagnostics import load_diag

    if not (REPO / diag_path).exists():
        return None
    frames = load_diag(diag_path)["frames"]
    coverage = diag_coverage(frames)
    if coverage and not (coverage[0] <= gt["frame"] - tolerance
                         and gt["frame"] + tolerance <= coverage[1]):
        return None
    row = wf.classify_contact(gt["frame"], "serve", gt.get("squad"), tolerance, frames)
    return {k: row.get(k) for k in
            ("stage", "detail", "candidate_frame", "kind", "gesture", "matched")}


def score_session(session: Dict[str, Any], side: str = "near",
                  search_f: int = DEFAULT_SEARCH_F,
                  diag: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Bucket every missed serve of one side for one session."""
    artifacts = session_artifacts(session)
    pipeline = artifacts["pipeline"]
    if pipeline is None:
        return {"key": session["key"], "error": "no pipeline_output.json for the session"}
    gt_blob = _read(session["gt"])
    gt_rows = [r for r in ss.serve_rows_from_contact_gt(
        gt_blob, split_of=session["split_of"],
        squad_to_side=session["squad_to_side"]) if r.get("side") == side]
    actions = load_actions(pipeline)
    pass2 = load_pass2(artifacts["relabel"] or {})
    serve_actions = [{"frame": a["frame_number"], "side": a["side"],
                      "action": a["action"]}
                     for a in actions if a["action"] == "serve"]
    matched = ss.match_candidates(gt_rows, serve_actions, require_side=True)
    hit_points = {entry["gt"] for entry in matched["matched"]}

    diag_frames = None
    dump = (diag or {}).get(session["key"]) or (diag or {}).get("*")
    if dump:
        diag_frames = load_diag_frames(dump)
    rows = []
    for index, gt in enumerate(gt_rows):
        if index in hit_points:
            continue
        row = {"point": gt.get("point"), "frame": gt["frame"], "side": gt["side"],
               "squad": gt.get("squad"), "split": gt.get("split"),
               "tolerance": gt.get("tolerance", TOLERANCE)}
        row.update(classify_miss(gt, actions, pass2, search_f,
                                 diag_frames=diag_frames))
        if diag:
            dump = diag.get(session["key"]) or diag.get("*")
            row["diag"] = diag_stage(gt, dump) if dump else None
        rows.append(row)

    buckets: Dict[str, int] = {}
    for row in rows:
        buckets[row["bucket"]] = buckets.get(row["bucket"], 0) + 1
    gates: Dict[str, int] = {}
    for row in rows:
        gate = (row.get("serve_gate") or {}).get("verdict")
        if gate:
            gates[gate] = gates.get(gate, 0) + 1
    labels: Dict[str, int] = {}
    for row in rows:
        for contact in row.get("contacts_in_tolerance") or []:
            labels[contact["action"]] = labels.get(contact["action"], 0) + 1
    stages: Dict[str, int] = {}
    for row in rows:
        stage = (row.get("diag") or {}).get("stage")
        if stage:
            stages[stage] = stages.get(stage, 0) + 1
    return {
        "key": session["key"],
        "label": session.get("label"),
        "side": side,
        "gt_serves": len(gt_rows),
        "hits": len(hit_points),
        "missed": len(rows),
        "buckets": buckets,
        "labels_inside_tolerance": labels,
        "serve_gate_verdicts": gates,
        "diag_stages": stages,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def format_report(out: Dict[str, Any]) -> str:
    lines = ["=" * 100,
             "  SR1 -- NEAR-SERVE MISS TAXONOMY (diagnose-only, open point 30)",
             "=" * 100,
             f"  buckets: label = a same-side contact at the serve frame with another "
             f"action | off_tolerance = a same-side contact outside +-{TOLERANCE}f | "
             f"other_side_contact = the only nearby contact is on the other half | "
             f"no_contact = nothing within the search window"]
    for key, session in out["sessions"].items():
        lines.append("")
        lines.append(f"  SESSION {key} -- {session.get('label') or ''}")
        if session.get("error"):
            lines.append(f"    ERROR {session['error']}")
            continue
        lines.append(f"    {session['side']} serves: {session['gt_serves']} GT, "
                     f"{session['hits']} hit, {session['missed']} missed")
        lines.append(f"    buckets {session['buckets']}"
                     + (f"   labels seen inside tolerance {session['labels_inside_tolerance']}"
                        if session["labels_inside_tolerance"] else ""))
        if session["diag_stages"]:
            lines.append(f"    diag first-failing stage {session['diag_stages']}")
        if session.get("serve_gate_verdicts"):
            lines.append(f"    serve-label gate (behind_baseline AND rally_start): "
                         f"{session['serve_gate_verdicts']}")
        for row in session["rows"]:
            lines.append("")
            lines.append(f"    P{row['point']} f{row['frame']} [{row['split']}] "
                         f"{row['side']}/{row['squad']}  -> {row['bucket'].upper()}")
            lines.append(f"      {row['detail']}")
            for contact in row.get("contacts_in_tolerance") or []:
                lines.append(f"        in-tolerance f{contact['frame']} "
                             f"{contact['action']} (gesture {contact['gesture']}, "
                             f"team {contact['team']}, touch {contact['touch_number']}, "
                             f"rally {contact['rally_id']}) {contact['delta_f']:+d} f")
            for change in row.get("pass2_changed_nearby") or []:
                lines.append(f"        pass2 f{change['frame']} {change['action']} -> "
                             f"{change['pass2_action']} ({change['pass2_source']}, "
                             f"demoted={change['pass2_demoted']}) {change['delta_f']:+d} f")
            for false_serve in row.get("owner_false_serve_nearby") or []:
                lines.append(f"        OWNER-FALSE serve emission f{false_serve['frame']} "
                             f"({false_serve['delta_f']:+d} f)")
            other = row.get("nearest_other_side_contact")
            if other:
                lines.append(f"        other-side contact f{other['frame']} "
                             f"{other['action']} (gesture {other['gesture']}, "
                             f"{other['side']}) {other['delta_f']:+d} f")
            if row.get("diag"):
                lines.append(f"        diag stage {row['diag']['stage']}: {row['diag']['detail']}")
            gate = row.get("serve_gate")
            if gate:
                lines.append(
                    f"        serve gate: {gate['verdict']}  "
                    f"(gap to prev contact {gate['gap_to_prev_contact_f']} f -> "
                    f"rally_start={gate['rally_start_inferred']}, "
                    f"behind_baseline={gate['behind_baseline_measured']})")
    lines.append("=" * 100)
    return "\n".join(lines)


def run(only_session: Optional[str] = None, side: str = "near",
        search_f: int = DEFAULT_SEARCH_F,
        diag: Optional[Dict[str, str]] = None,
        sessions: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"side": side, "search_f": search_f, "sessions": {}}
    for session in (sessions if sessions is not None else ss.build_sessions()):
        if only_session and session["key"] != only_session:
            continue
        if session["key"] == "match_20260920" or session["key"].startswith("entreno"):
            out["sessions"][session["key"]] = score_session(
                session, side=side, search_f=search_f, diag=diag)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--session", default=None)
    ap.add_argument("--side", default="near", choices=("near", "far"))
    ap.add_argument("--search-f", type=int, default=DEFAULT_SEARCH_F)
    ap.add_argument("--diag", nargs="*", default=None,
                    help="session=path pairs (or a bare path for every session) "
                         "of production --diag-dump JSONL files")
    ap.add_argument("--emit-diag", default=None,
                    help="SEQUENTIAL production pass writing this --diag-dump JSONL")
    ap.add_argument("--video", default="resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4")
    ap.add_argument("--calibration", default="calibrations/20260920_match_ari_joan_lost.json")
    ap.add_argument("--end-frame", type=int, default=4000)
    ap.add_argument("--reference", default="output/20260920_match_ari_joan_lost/pipeline_output.json",
                    help="shipped pipeline_output.json for the prefix-parity check")
    ap.add_argument("--device", default="mps")
    ap.add_argument("--json", default="output/serves/sr1.json")
    args = ap.parse_args(argv)

    if args.emit_diag:
        out = emit_diag(args.video, args.calibration, args.end_frame,
                        args.emit_diag, args.reference, args.device)
        print(json.dumps(out, indent=1))
        return 0

    diag: Dict[str, str] = {}
    if args.diag:
        for item in args.diag:
            if "=" in item:
                key, path = item.split("=", 1)
                diag[key.strip()] = path.strip()
            else:
                diag["*"] = item.strip()

    out = run(only_session=args.session, side=args.side,
              search_f=args.search_f, diag=diag or None)
    print(format_report(out))
    if args.json:
        p = REPO / args.json
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())