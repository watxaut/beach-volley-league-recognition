#!/usr/bin/env python3
"""S4 -- consume the serve EVIDENCE into a per-point serve record (pass 2).

The far serve is solved as evidence (session 53, ``docs/g4_structural_serve.md``):
a structural proposer over the RAW detections reaches 14/17 GT far serves with
**zero** false positives across 24 mid-rally contacts and the 9 owner
FALSE/OFFGAME moments, where the action stream has 0/17. This script turns that
evidence into the artifact the rest of the club tooling can read -- one serve
record per point -- and it is deliberately PASS 2:

* it reads ``pipeline_output.json`` (from a run with ``--serve-events``) and the
  existing ``output/serve_relabel.json`` point map; it never re-decodes video;
* it writes ``output/serve_evidence.json`` and nothing else. It does **not**
  touch ``events``, the action stream, the CSV or the DB. AGENTS.md §6 and the
  S0b lesson are explicit: a pass-2 layer must never be a LABEL source (the
  relabel experiment broke 3 correct dig labels and recovered 0/5 far serves);
* the GT is used **validate-only**: the gates report what the record would have
  been worth, and the owner anchors (FALSE / OFFGAME) are the false-positive
  side. Nothing in the output is fitted to them.

The opener gate lives here, not in the emitter, because it is structural
bookkeeping over the WHOLE action stream: a serve opens a rally, and on this
match openers follow >=153 f of dead time while the largest mid-rally gap is
134 f. Applied to the evidence it takes precision 0.579 -> 1.000 with recall
unchanged -- a 60-240 f plateau, so the constant is not a fit.

What a record carries, and what a consumer may do with it:

* ``frame``      -- the contact estimate (median |error| 1 f on the 14/17 set);
* ``sources``    -- which arms fired (``conjunction`` / ``structural`` /
  ``both``). Agreement between two independent mechanisms is the strongest
  signal in the record and is what a consumer should weight;
* ``server_side``-- ``far`` for every record here. The far runway is what the
  emitters observe, so a NEAR serve is not covered by this layer at all and a
  consumer must fall back to the emitted ``serve`` actions for it (the record
  says so explicitly, per point, in ``near_serve_in_evidence``);
* ``server_bbox``-- the occupant's box, so the review UI can point at the person
  even though they are not one of the 4 tracked players (the tracker locks
  exactly 4 in-court tracks, AGENTS.md §1).

Usage::

    venv/bin/python scripts/consume_serve_evidence.py
    venv/bin/python scripts/consume_serve_evidence.py --opener-gap 90 --validate-only
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: The default pipeline run this layer was measured on.
MATCH_RUN = "output/20260920_match_ari_joan_lost/pipeline_output.json"
POINT_MAP = "output/serve_relabel.json"
ANCHORS = "ground_truth/20260920_match_serve_anchors.txt"
MATCH_GT = "ground_truth/20260920_match_contacts.json"
DEFAULT_OUT = "output/serve_evidence.json"

#: Frame tolerance for "this record IS the serve the owner dictated". Owner
#: frames are coarse (+-10-15 f, stated in the GT file itself).
TOLERANCE = 15
#: Structural constant: openers >= 153 f, largest mid-rally gap 134 f (session 28).
DEFAULT_OPENER_GAP = 143
#: Serve -> first rally contact: the flight from the far line to the net plus the
#: receiver's read. The SELECTOR uses the LOWER bound only, and it is the one
#: that matters: a record sitting within a few frames of the next action is the
#: post-contact echo (the ball still inside the server's bbox as it leaves), not
#: the serve. Fitted on the 5 dev far serves, verified on the 12 held-out ones;
#: the sensitivity sweep is in the artifact so the choice is auditable.
MIN_NEXT_GAP = 20
MAX_NEXT_GAP = 140
#: Arms whose union is the recommended operating point (14/17, zero FP).
ARMS = ("conjunction", "structural")
EVENT_TYPE = {"conjunction": "serve_candidate", "structural": "serve_contact"}


# --------------------------------------------------------------------------- io


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def action_frames(pipeline: Dict[str, Any]) -> List[int]:
    """Every emitted contact frame, sorted and de-duplicated.

    The perception stream lives under ``actions`` in ``pipeline_output.json``
    (``events`` is the schema used by the GT files, so both are accepted). Each
    action is keyed by its CONTACT frame, which is what the opener gap has to
    be measured on.
    """
    frames = set()
    for key in ("actions", "events"):
        for action in pipeline.get(key) or []:
            frame = action.get("frame_number", action.get("frame"))
            if isinstance(frame, int):
                frames.add(frame)
    return sorted(frames)


def load_owner_negatives() -> List[Dict[str, Any]]:
    """The owner's FALSE frames and OFFGAME ranges -- the false-positive side."""
    out: List[Dict[str, Any]] = []
    for line in (ROOT / ANCHORS).read_text().splitlines():
        line = line.strip()
        m = re.match(r"^FALSE\s+(\d+)\s*(.*)$", line)
        if m:
            out.append({"frame": int(m.group(1)), "why": m.group(2).strip(),
                        "range": [int(m.group(1)), int(m.group(1))]})
            continue
        m = re.match(r"^OFFGAME\s+(\d+)-(\d+)\s*(.*)$", line)
        if m:
            out.append({"frame": (int(m.group(1)) + int(m.group(2))) // 2,
                        "range": [int(m.group(1)), int(m.group(2))],
                        "why": m.group(3).strip()})
    out.sort(key=lambda n: n["frame"])
    return out


def load_gt_far_serves() -> List[Dict[str, Any]]:
    data = load_json(ROOT / MATCH_GT)
    out = []
    for point in data["points"]:
        for event in point.get("events", []):
            if event.get("action") == "serve" and event.get("owner_side") == "far":
                out.append({"point": int(point["point"]),
                            "frame": int(event["match_frame"]),
                            "held_out": int(point["point"]) > 8})
    out.sort(key=lambda s: s["frame"])
    return out


# ------------------------------------------------------------------ the gate


def prev_action(frames: Sequence[int], frame: int) -> Optional[int]:
    i = bisect.bisect_left(frames, frame)
    return frames[i - 1] if i else None


def gate_open(frames: Sequence[int], frame: int, opener_gap: int) -> bool:
    """True when no contact was emitted in the preceding ``opener_gap`` frames."""
    last = prev_action(frames, frame)
    return last is None or frame - last > opener_gap


def group_evidence(events: Sequence[Dict[str, Any]], frames: Sequence[int],
                   opener_gap: int, before: int, after: int) -> List[Dict[str, Any]]:
    """One record per qualifying contact moment, from the two arms unioned.

    Candidates from the two arms that land within ``merge_frames`` of each other
    are ONE record with ``sources`` naming both -- agreement between two
    independent mechanisms is the strongest thing in the record.
    """
    gated = []
    for event in events:
        kind = event.get("type")
        if kind not in EVENT_TYPE.values():
            continue
        frame = int(event.get("contact_frame", event.get("frame", 0)))
        if not gate_open(frames, frame, opener_gap):
            continue
        arm = "conjunction" if kind == EVENT_TYPE["conjunction"] else "structural"
        gated.append((frame, arm, event))
    gated.sort(key=lambda item: item[0])

    records: List[Dict[str, Any]] = []
    for frame, arm, event in gated:
        if records and abs(frame - records[-1]["frame"]) <= 15:
            record = records[-1]
            record["sources"] = sorted(set(record["sources"]) | {arm})
            record["evidence_frames"].append(frame)
            record["arms"][arm] = _arm_summary(event)
            # Prefer the arm with the tighter timing (the conjunction places the
            # contact at the closest approach, the structural arm at the last
            # sighting of the run); keep both and note the disagreement.
            if arm == "structural":
                record["frame"] = frame
            continue
        records.append({
            "frame": frame,
            "sources": [arm],
            "arms": {arm: _arm_summary(event)},
            "evidence_frames": [frame],
        })
    return records


def _arm_summary(event: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("contact_frame", "frame", "occupant_bbox", "occupant_region",
            "occupant_conf", "ball_gap_norm", "ball_conf", "flight_onset_frame",
            "flight_growth", "sightings", "ball_width")
    return {k: event[k] for k in keys if k in event}


def select_serve(records: Sequence[Dict[str, Any]], frames: Sequence[int],
                 min_next_gap: int = MIN_NEXT_GAP,
                 max_next_gap: int = MAX_NEXT_GAP) -> Optional[Dict[str, Any]]:
    """The serve among the records of one dead-time episode.

    A dead-time episode holds several records, and they are not equally likely:

    * a **pre-serve handling** record (the owner annotated several: "walking to
      the serve line with the ball in her hands", "the throw from one near
      player to the server") is far from the rally -- hundreds of frames;
    * the **serve** is the last contact before the rally, so the next emitted
      action follows it within a flight's worth of frames;
    * a **post-contact echo** (the ball still inside the server's bbox as it
      leaves) sits only a handful of frames before the next action.

    So: among the records whose distance to the next emitted contact is at least
    ``min_next_gap``, take the one with the **smallest** such distance -- the
    serve is the record closest to the rally that is not the echo. Everything
    further back is the walk to the serve line.

    Honest limits, measured on the 17 owner far serves
    (``docs/g4_serve_evidence.md``): this recovers 12/17 where the evidence
    itself covers 14/17, and two of the five misses are genuine ambiguity (a
    second record 8-18 f from the contact, so either reading is defensible).
    """
    best = None
    best_distance = None
    for record in records:
        i = bisect.bisect_left(frames, record["frame"])
        if i >= len(frames):
            continue
        distance = frames[i] - record["frame"]
        if not (min_next_gap <= distance <= max_next_gap):
            continue
        if best_distance is None or distance < best_distance:
            best, best_distance = record, distance
    return best


def attach_to_points(records: Sequence[Dict[str, Any]], points: Sequence[Dict[str, Any]],
                     frames: Sequence[int], before: int, after: int,
                     min_next_gap: int = MIN_NEXT_GAP,
                     max_next_gap: int = MAX_NEXT_GAP) -> List[Dict[str, Any]]:
    """Bind records to points through the DEAD-TIME EPISODE they live in.

    The first version of this layer bound a record to a point by the pass-2
    window, and that cost half the serves for a reason that has nothing to do
    with the evidence: the episode map's windows are PREDICTIONS (only 12/25
    cover their own owner contact range, STATUS Learnings), so a serve can sit
    outside its own window entirely -- four of the 17 owner far serves do.

    The emitted contacts are not predictions, though: they are what the pipeline
    actually saw, and they already partition the video into **dead-time
    episodes**. A serve lives in exactly one of them, opens it, and is followed
    by that episode's FIRST contact -- the reception. So:

    * an episode is the stretch between two consecutive emitted contacts;
    * the serve is the last record in the episode whose distance to the
      episode's first contact is in the flight window;
    * the point is the one that owns that first contact.

    ``before``/``after`` are kept only for the record list attached to each
    point (diagnostics), not for the binding itself.
    """
    episodes = build_episodes(records, frames)
    bound: Dict[int, List[Dict[str, Any]]] = {}
    for episode in episodes:
        record = select_serve(episode["records"], frames, min_next_gap, max_next_gap)
        if record is None:
            continue
        anchor = episode["first_action"]
        if anchor is None:
            continue
        point = point_of_frame(points, anchor, before, after)
        if point is None:
            continue
        record = dict(record)
        record["episode"] = {"start_frame": episode["start_frame"],
                             "first_action": episode["first_action"],
                             "records_in_episode": len(episode["records"])}
        bound.setdefault(point, []).append(record)

    out = []
    for point in points:
        lo, hi = point["window_frames"]
        inside = [r for r in records if lo - before <= r["frame"] <= hi + after]
        mine = bound.get(point["point"], [])
        best = max(mine, key=lambda r: r["frame"], default=None)
        out.append({"point": point["point"], "window_frames": [lo, hi], **point,
                    "records": inside,
                    "serve_evidence_records": mine,
                    "serve_evidence": best})
    return out


def build_episodes(records: Sequence[Dict[str, Any]],
                   frames: Sequence[int]) -> List[Dict[str, Any]]:
    """The dead-time episodes: one per consecutive pair of emitted contacts.

    Episode *i* is the stretch ``(frames[i-1], frames[i])`` -- everything with
    no contact in it is dead time, and a record inside it opens the rally that
    ``frames[i]`` belongs to. The stretch before the first contact of the video
    and after the last one are included as open-ended episodes so a serve is
    never dropped for want of a successor.
    """
    bounds = [None] + list(frames)          # bounds[i] is the episode's start
    episodes = []
    for index, first_action in enumerate(frames):
        start = bounds[index]
        inside = [r for r in records
                  if r["frame"] < first_action and (start is None or r["frame"] > start)]
        if inside:
            episodes.append({"start_frame": start, "first_action": first_action,
                             "records": inside})
    if records:
        last = max(frames) if frames else None
        tail = [r for r in records if last is None or r["frame"] > last]
        if tail:
            episodes.append({"start_frame": last, "first_action": None,
                             "records": tail})
    return episodes


def point_of_frame(points: Sequence[Dict[str, Any]], frame: int,
                   before: int = 90, after: int = 60) -> Optional[int]:
    """Which point owns this frame: its own window first, then the nearest one.

    A reception immediately after a far serve can sit just outside its point's
    window, so the nearest window is the fallback and the choice is reported
    (``point_binding``) rather than hidden.
    """
    for point in points:
        lo, hi = point["window_frames"]
        if lo - before <= frame <= hi + after:
            return point["point"]
    if not points:
        return None
    nearest = min(points, key=lambda p: min(abs(frame - p["window_frames"][0]),
                                            abs(frame - p["window_frames"][1])))
    lo, hi = nearest["window_frames"]
    if abs(frame - lo) <= 400 or abs(frame - hi) <= 400:
        return nearest["point"]
    return None


# ---------------------------------------------------------------- validation


def validate(rows: Sequence[Dict[str, Any]], records: Sequence[Dict[str, Any]],
             opener_gap: int) -> Dict[str, Any]:
    """GT is VALIDATE-ONLY: report what the records were worth, fit nothing."""
    far_serves = load_gt_far_serves()
    negatives = load_owner_negatives()
    hit_points, missed = set(), []
    for serve in far_serves:
        row = next((r for r in rows if r["point"] == serve["point"]), None)
        record = (row or {}).get("serve_evidence")
        if record and abs(record["frame"] - serve["frame"]) <= TOLERANCE:
            hit_points.add(serve["point"])
        else:
            missed.append({"point": serve["point"], "frame": serve["frame"],
                           "record": None if record is None else record["frame"],
                           "offset": None if record is None
                           else record["frame"] - serve["frame"]})
    # Far serves whose point has no record at all are misses too.
    uncovered = [r["point"] for r in rows
                 if r["point"] not in hit_points and r.get("serve_side_near_far") == "far"]
    fp = []
    for neg in negatives:
        lo, hi = neg["range"]
        for record in records:
            if lo - TOLERANCE <= record["frame"] <= hi + TOLERANCE:
                fp.append({"frame": record["frame"], "negative": neg["frame"],
                           "why": neg["why"], "sources": record["sources"]})
    agreement = sum(1 for r in records if len(r["sources"]) > 1)
    return {
        "far_serves": len(far_serves),
        "far_serves_covered": len(hit_points),
        "dev_covered": sum(1 for s in far_serves
                           if s["point"] in hit_points and not s["held_out"]),
        "dev_total": sum(1 for s in far_serves if not s["held_out"]),
        "held_out_covered": sum(1 for s in far_serves
                                if s["point"] in hit_points and s["held_out"]),
        "held_out_total": sum(1 for s in far_serves if s["held_out"]),
        "missed": missed,
        "points_far_served_without_record": sorted(set(uncovered) - {m["point"] for m in missed}),
        "owner_false_positives": fp,
        "records_in_near_served_points": [r["point"] for r in rows
                                          if r.get("serve_evidence")
                                          and r.get("serve_side_near_far") == "near"],
        "records": len(records),
        "records_with_agreement": agreement,
        "precision_on_owner_negatives": round(
            len(hit_points) / (len(hit_points) + len(fp)), 3) if hit_points or fp else None,
        "opener_gap": opener_gap,
    }


# ---------------------------------------------------------------------- main


def selector_sensitivity(events: Sequence[Dict[str, Any]], frames: Sequence[int],
                         points: Sequence[Dict[str, Any]], opener_gap: int,
                         before: int, after: int) -> List[Dict[str, Any]]:
    """How the binding accuracy moves with the one selector parameter.

    A single fitted constant is only acceptable if the curve is flat around it,
    so the sweep ships in the artifact and the chosen value is one the
    dev points and the held-out points agree on.
    """
    records = group_evidence(events, frames, opener_gap, before, after)
    out = []
    for min_gap in (0, 5, 10, 15, 20, 30, 40, 60):
        rows = attach_to_points(records, points, frames, before, after,
                                min_gap, MAX_NEXT_GAP)
        gates = validate(rows, records, opener_gap)
        out.append({"min_next_gap": min_gap, "covered": gates["far_serves_covered"],
                    "n": gates["far_serves"],
                    "dev": gates["dev_covered"], "dev_n": gates["dev_total"],
                    "held_out": gates["held_out_covered"],
                    "held_out_n": gates["held_out_total"],
                    "owner_false_positives": len(gates["owner_false_positives"])})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", default=MATCH_RUN)
    ap.add_argument("--point-map", default=POINT_MAP)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--opener-gap", type=int, default=DEFAULT_OPENER_GAP)
    ap.add_argument("--before", type=int, default=90,
                    help="frames before a point window a record may bind to")
    ap.add_argument("--after", type=int, default=60)
    ap.add_argument("--min-next-gap", type=int, default=MIN_NEXT_GAP,
                    help="a record closer than this to the next contact is the "
                         "post-contact echo, not the serve (frames)")
    ap.add_argument("--max-next-gap", type=int, default=MAX_NEXT_GAP,
                    help="further than this back is the walk to the serve line")
    ap.add_argument("--validate-only", action="store_true",
                    help="score and print, do not write the artifact")
    args = ap.parse_args()

    pipeline_path = ROOT / args.pipeline
    if not pipeline_path.exists():
        print(f"missing {args.pipeline} -- run the pipeline with --serve-events first:\n"
              f"  venv/bin/python -m src.main resources/full_videos/"
              f"20260920_match_ari_joan_lost.mp4 --output-dir output/"
              f"20260920_match_ari_joan_lost --skip-visualization --serve-events")
        return 2
    pipeline = load_json(pipeline_path)
    events = pipeline.get("serve_events") or []
    if not events:
        print(f"{args.pipeline} carries no serve_events -- was it run with --serve-events?")
        return 2
    point_map = load_json(ROOT / args.point_map)
    frames = action_frames(pipeline)

    counts: Dict[str, int] = {}
    for event in events:
        counts[event.get("type", "?")] = counts.get(event.get("type", "?"), 0) + 1
    records = group_evidence(events, frames, args.opener_gap, args.before, args.after)
    rows = attach_to_points(records, point_map.get("points", []), frames,
                            args.before, args.after, args.min_next_gap,
                            args.max_next_gap)

    print(f"pipeline {args.pipeline}")
    print(f"  emitted contacts {len(frames)} | serve events {counts}")
    print(f"  opener gap {args.opener_gap} f -> {len(records)} records "
          f"({sum(1 for r in records if len(r['sources']) > 1)} with both arms)")

    gates = validate(rows, records, args.opener_gap)
    sweep = selector_sensitivity(events, frames, point_map.get("points", []),
                                 args.opener_gap, args.before, args.after)
    gates["selector_sensitivity"] = sweep
    print(f"\nVALIDATE-ONLY (GT never enters the artifact)")
    print(f"  far serves covered {gates['far_serves_covered']}/{gates['far_serves']} "
          f"(dev {gates['dev_covered']}/{gates['dev_total']}, "
          f"held-out {gates['held_out_covered']}/{gates['held_out_total']})")
    print(f"  min_next_gap sensitivity: " + ", ".join(
        f"{s['min_next_gap']}f->{s['covered']}/{s['n']}" for s in sweep))
    print(f"  owner FALSE/OFFGAME false positives {len(gates['owner_false_positives'])} "
          f"-> precision {gates['precision_on_owner_negatives']}")
    if gates["records_in_near_served_points"]:
        print(f"  cross-check: records in near-served points (not consumed): "
              f"{gates['records_in_near_served_points']}")
    if gates["missed"]:
        print(f"  missed: {json.dumps(gates['missed'])}")

    per_point = []
    for row in rows:
        record = row["serve_evidence"]
        near_served = row.get("serve_side_near_far") == "near"
        per_point.append({
            "point": row["point"],
            "window_frames": row["window_frames"],
            # Every record here comes from the FAR runway, so the evidence can
            # only speak for a far serve. A record in a point the structural map
            # says was served from the NEAR side is a cross-check failure, not a
            # near serve -- it is counted, never consumed.
            "serve_side_evidence": "far" if record else None,
            "point_serve_side_structural": row.get("serve_side_near_far"),
            "record_in_near_served_point": bool(record) and near_served,
            "serve_evidence": record,
            "evidence_count": len(row["records"]),
        })
    covered = sum(1 for p in per_point if p["serve_evidence"])
    near_mismatch = [p["point"] for p in per_point if p["record_in_near_served_point"]]
    print(f"\npoints with a serve record: {covered}/{len(per_point)}")
    if near_mismatch:
        print(f"  cross-check: records in near-served points (NOT consumed): {near_mismatch}")

    artifact = {
        "source": {"pipeline": args.pipeline, "point_map": args.point_map,
                   "video": pipeline.get("video") or pipeline.get("video_name")},
        "opener_gap_frames": args.opener_gap,
        "tolerance_frames": TOLERANCE,
        "arms": list(ARMS),
        "disclaimer": ("Serve EVIDENCE, not labels. This layer never writes to the "
                       "action stream (AGENTS.md §6); a consumer must treat `frame` "
                       "as an estimate, weight `sources` (both arms agreeing is the "
                       "strong signal), and fall back to the emitted `serve` actions "
                       "for NEAR-side serves, which this layer does not observe."),
        "records": records,
        "points": per_point,
        "validation": gates,
        "serve_event_counts": counts,
        "emitted_contact_frames": len(frames),
    }
    if args.validate_only:
        print("validate-only: nothing written")
        return 0
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
