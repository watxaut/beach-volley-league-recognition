#!/usr/bin/env python3
"""Identity probe: do P1A/P2A/P1B/P2B survive side switches? (owner-run)

ONE sequential production pass (``FrameProcessor.process_frame`` over a plain
``cap.read()`` loop -- no seeks, AGENTS.md §9) with the enrollment pre-pass,
exactly like ``src/main.py``. It records, per frame, the labels of both
identity layers side by side -- the side-switch-aware TEAM resolver (output
labels) and the #82 LEGACY resolver (still computed inside the tracker for its
own guards) -- so a single run is an A/B of the two.

Outputs (``--out``, default ``output/identity_probe/<stem>/``, git-ignored):

* ``identity_probe.json`` -- the raw record (re-score it with ``--reuse``);
* ``identity_sheet_NN.png`` -- CONTACT SHEETS, rows = P1A / P2A / P1B / P2B,
  one column every ``--sheet-every`` seconds. Each row must show ONE person
  from left to right, on both sides of every switch: the eyeball check for
  per-player identity (no per-player GT exists). A red header = labels
  withheld (orientation in doubt) at that moment; the header says which
  squad was near.
* stdout summary.

With ``--contacts-gt`` (the match-contacts-v1 format, e.g.
``ground_truth/20260920_match_contacts.json``: every GT contact carries its
side AND its fixed squad, across the 4 switches), three objective scores:

1. **orientation at GT contacts** -- at every GT contact frame, does the
   resolver's near squad match the GT (side, team)? (doubt = abstain);
2. **switch timing** -- one flip inside each GT switch window (last contact
   of point k .. first contact of point k+1, k in ``side_switch_after``),
   late flips and flips outside every window listed;
3. **action attribution, team vs legacy** -- emitted actions matched to GT
   contacts (greedy one-to-one, nearest first, within each contact's
   ``frame_tolerance``): is the squad of the action's player label right?
   This is the number goals G1/G2 consume.

Usage::

    venv/bin/python scripts/probe_identity_switches.py \\
        resources/full_videos/20260920_match_ari_joan_lost.mp4 \\
        --contacts-gt ground_truth/20260920_match_contacts.json --device mps
    venv/bin/python scripts/probe_identity_switches.py --reuse \\
        output/identity_probe/20260920_match_ari_joan_lost/identity_probe.json \\
        --contacts-gt ground_truth/20260920_match_contacts.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LABELS = ("P1A", "P2A", "P1B", "P2B")


# --------------------------------------------------------------------------- #
# Pure scoring (unit-tested; no video)
# --------------------------------------------------------------------------- #

def label_team(label: Optional[str]) -> Optional[str]:
    """Team letter of an enrolled label (``P1A`` -> ``A``), else None."""
    if not label or label[-1] not in ("A", "B"):
        return None
    return label[-1]


def expected_near_team(side: str, team: str) -> Optional[str]:
    """Which team is NEAR when a ``team`` player touches on ``side``."""
    if side not in ("near", "far") or team not in ("A", "B"):
        return None
    if side == "near":
        return team
    return "B" if team == "A" else "A"


def gt_contacts(gt: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for point in gt.get("points", []):
        for c in point.get("contacts", []):
            if c.get("match_frame") is None:
                continue
            out.append({
                "point": int(point["point"]),
                "frame": int(c["match_frame"]),
                "side": c.get("side"),
                "team": c.get("team"),
                "action": c.get("action"),
                "tolerance": int(c.get("frame_tolerance") or 15),
            })
    return sorted(out, key=lambda c: c["frame"])


def switch_windows(gt: Dict[str, Any]) -> List[Tuple[int, int, int]]:
    """(after_point, last contact frame of it, first contact of the next)."""
    by_point: Dict[int, List[int]] = {}
    for c in gt_contacts(gt):
        by_point.setdefault(c["point"], []).append(c["frame"])
    switches = [int(p) for p in gt.get("side_switch_after_point", [])]
    if not switches:
        switches = [int(p["point"]) for p in gt.get("points", []) if p.get("side_switch_after")]
    out = []
    for k in switches:
        if k in by_point and (k + 1) in by_point:
            out.append((k, max(by_point[k]), min(by_point[k + 1])))
    return out


def near_team_at(frames: Dict[int, Dict[str, Any]], frame: int) -> Tuple[Optional[str], bool]:
    """(near team letter, in doubt) of the record at ``frame``."""
    rec = frames.get(frame)
    if rec is None or rec.get("near_squad") is None:
        return None, False
    return ("A" if rec["near_squad"] == 1 else "B"), bool(rec.get("doubt"))


def score_orientation(record: Dict[str, Any], gt: Dict[str, Any]) -> Dict[str, Any]:
    frames = {int(f["frame"]): f for f in record["frames"]}
    last = max(frames) if frames else -1
    rows = []
    for c in gt_contacts(gt):
        if c["frame"] > last:
            continue
        want = expected_near_team(c["side"], c["team"])
        got, doubt = near_team_at(frames, c["frame"])
        if want is None or got is None:
            continue
        verdict = "doubt" if doubt else ("ok" if got == want else "wrong")
        rows.append(dict(c, expected=want, got=got, verdict=verdict))
    n = len(rows)
    count = {v: sum(r["verdict"] == v for r in rows) for v in ("ok", "wrong", "doubt")}
    return {"n": n, **count, "wrong_points": sorted({r["point"] for r in rows if r["verdict"] == "wrong"}),
            "rows": rows}


def score_flips(record: Dict[str, Any], gt: Dict[str, Any], late_frames: int = 0) -> Dict[str, Any]:
    """Each GT switch window should hold exactly one flip."""
    flips = [int(f["frame"]) for f in record.get("flips", [])]
    last = max((int(f["frame"]) for f in record["frames"]), default=-1)
    windows = [w for w in switch_windows(gt) if w[1] <= last]
    used = set()
    rows = []
    for k, start, end in windows:
        inside = [f for f in flips if start <= f <= end + late_frames]
        on_time = [f for f in inside if f <= end]
        rows.append({
            "after_point": k, "window": [start, end],
            "flips": inside,
            "verdict": "ok" if len(on_time) == 1 and len(inside) == 1
            else ("late" if len(inside) == 1 else ("missed" if not inside else "multiple")),
        })
        used.update(inside)
    stray = [f for f in flips if f not in used]
    return {"windows": rows, "stray_flips": stray,
            "ok": sum(r["verdict"] == "ok" for r in rows), "n_windows": len(rows)}


def score_actions(record: Dict[str, Any], gt: Dict[str, Any]) -> Dict[str, Any]:
    """Squad of the action's player label vs the GT contact's team, for the
    team resolver (``label``) and the legacy resolver (``legacy_label``)."""
    actions = sorted(record.get("actions", []), key=lambda a: a["frame"])
    last = max((int(f["frame"]) for f in record["frames"]), default=-1)
    contacts = [c for c in gt_contacts(gt) if c["frame"] <= last]
    pairs = []
    for ci, c in enumerate(contacts):
        for ai, a in enumerate(actions):
            d = abs(a["frame"] - c["frame"])
            if d <= c["tolerance"]:
                pairs.append((d, ci, ai))
    pairs.sort()
    used_c, used_a, matched = set(), set(), []
    for d, ci, ai in pairs:
        if ci in used_c or ai in used_a:
            continue
        used_c.add(ci)
        used_a.add(ai)
        matched.append((contacts[ci], actions[ai]))
    out: Dict[str, Any] = {"n_gt": len(contacts), "n_matched": len(matched)}
    for key in ("label", "legacy_label"):
        res = {"ok": 0, "wrong": 0, "unlabeled": 0}
        for c, a in matched:
            team = label_team(a.get(key))
            if team is None:
                res["unlabeled"] += 1
            elif team == c["team"]:
                res["ok"] += 1
            else:
                res["wrong"] += 1
        out[key] = res
    return out


def label_stats(record: Dict[str, Any]) -> Dict[str, Any]:
    """Coverage + churn: frames each label is shown, label changes per id,
    and 'teleports' (a label on a different id whose box is far away)."""
    shown = {lab: 0 for lab in LABELS}
    last_pos: Dict[str, Tuple[int, float, float]] = {}
    teleports = {lab: 0 for lab in LABELS}
    for f in record["frames"]:
        for tid, label, _legacy, _side, x1, y1, x2, y2 in f["bodies"]:
            if label not in shown:
                continue
            shown[label] += 1
            cx, fy = (x1 + x2) / 2.0, float(y2)
            prev = last_pos.get(label)
            if prev is not None and prev[0] != tid and abs(cx - prev[1]) + abs(fy - prev[2]) > 200:
                teleports[label] += 1
            last_pos[label] = (tid, cx, fy)
    n = max(1, len(record["frames"]))
    return {"coverage": {k: round(v / n, 3) for k, v in shown.items()}, "teleports": teleports}


# --------------------------------------------------------------------------- #
# The production pass
# --------------------------------------------------------------------------- #

def sequential_pass(video: str, config: Dict[str, Any], max_frames: Optional[int],
                    sheet_every_s: float) -> Tuple[Dict[str, Any], Dict[str, list]]:
    import cv2  # noqa: E402

    from src.analysis.frame_processor import FrameProcessor  # noqa: E402

    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise SystemExit(f"cannot open {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    processor = FrameProcessor(config)
    processor.setup_video_fps(fps)
    processor.setup_video_dimensions(width, height)
    refs = processor.enroll_from_video(video)
    tracker = processor.player_tracker
    court = processor.court_calibration
    if not refs or tracker.team_identity is None:
        print("WARNING: no enrollment / no team resolver -- nothing to probe "
              f"(refs={'yes' if refs else 'no'})")

    record: Dict[str, Any] = {"video": video, "fps": fps, "frames": [], "actions": [],
                              "flips": [], "enrolled": [r["label"] for r in refs or []]}
    sheets: Dict[str, list] = {lab: [] for lab in LABELS}
    sheet_every = max(1, int(round(sheet_every_s * fps)))

    cap = cv2.VideoCapture(video)
    frame_idx = 0
    t0 = time.time()
    try:
        while max_frames is None or frame_idx < max_frames:
            ok, image = cap.read()
            if not ok:
                break
            result = processor.process_frame(image, frame_idx)
            state = tracker.identity_state() or {}
            bodies = []
            for p in result.get("tracked_players") or []:
                if p.get("predicted") or not p.get("bbox"):
                    continue
                tid = p.get("track_id")
                legacy = tracker._track_labels.get(tid)
                bbox = [int(round(v)) for v in p["bbox"]]
                side = court.get_team_for_bbox(bbox) if court is not None else None
                bodies.append([tid, p.get("player_label"), legacy[0] if legacy else None,
                               side, *bbox])
            record["frames"].append({
                "frame": frame_idx,
                "near_squad": state.get("near_squad"),
                "cusum": state.get("cusum"),
                "evidence": state.get("evidence"),
                "doubt": state.get("doubt"),
                "bodies": bodies,
            })
            for a in result.get("actions") or []:
                tid = a.get("track_id")
                legacy = tracker._track_labels.get(tid)
                record["actions"].append({
                    "frame": int(a.get("frame_number", frame_idx)), "seen_at": frame_idx,
                    "track_id": tid, "action": a.get("action"),
                    "label": a.get("player_label"),
                    "legacy_label": legacy[0] if legacy else None,
                })
            if frame_idx % sheet_every == 0:
                for tid, label, _legacy, _side, x1, y1, x2, y2 in bodies:
                    if label in sheets:
                        crop = image[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
                        if crop.size:
                            sheets[label].append((frame_idx, crop.copy()))
                stamp = (frame_idx, state.get("near_squad"), bool(state.get("doubt")))
                sheets.setdefault("_stamps", []).append(stamp)
            frame_idx += 1
            if frame_idx % 1000 == 0:
                print(f"  frame {frame_idx}  ({frame_idx / max(1e-6, time.time() - t0):.1f} fps)  "
                      f"near squad {state.get('near_squad')}  flips {len(state.get('flips', []))}",
                      flush=True)
    finally:
        cap.release()
    final = tracker.identity_state() or {}
    record["flips"] = final.get("flips", [])
    record["learned"] = final.get("learned")
    return record, sheets


def write_sheets(sheets: Dict[str, list], fps: float, out_dir: Path,
                 per_sheet: int = 24, cell_h: int = 128) -> List[Path]:
    """Rows = labels, columns = sample times; one PNG per ``per_sheet`` columns."""
    import cv2  # noqa: E402
    import numpy as np  # noqa: E402

    stamps = sheets.get("_stamps", [])
    if not stamps:
        return []
    cell_w = cell_h // 2
    header_h, label_w = 22, 52
    by_label = {lab: {f: crop for f, crop in sheets.get(lab, [])} for lab in LABELS}
    paths = []
    for s0 in range(0, len(stamps), per_sheet):
        cols = stamps[s0:s0 + per_sheet]
        img = np.full((header_h + cell_h * len(LABELS), label_w + cell_w * len(cols), 3), 30, np.uint8)
        for r, lab in enumerate(LABELS):
            cv2.putText(img, lab, (4, header_h + r * cell_h + cell_h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        for c, (frame, near_squad, doubt) in enumerate(cols):
            x = label_w + c * cell_w
            secs = frame / max(fps, 1e-6)
            colour = (60, 60, 200) if doubt else (70, 70, 70)
            cv2.rectangle(img, (x, 0), (x + cell_w - 1, header_h - 1), colour, -1)
            near = {1: "A", 2: "B"}.get(near_squad, "?")
            cv2.putText(img, f"{int(secs // 60)}:{int(secs % 60):02d}{near}", (x + 2, 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.33, (255, 255, 255), 1)
            for r, lab in enumerate(LABELS):
                crop = by_label[lab].get(frame)
                if crop is None:
                    continue
                h, w = crop.shape[:2]
                scale = min(cell_h / h, cell_w / w)
                small = cv2.resize(crop, (max(1, int(w * scale)), max(1, int(h * scale))))
                y = header_h + r * cell_h
                img[y:y + small.shape[0], x:x + small.shape[1]] = small
        path = out_dir / f"identity_sheet_{s0 // per_sheet:02d}.png"
        cv2.imwrite(str(path), img)
        paths.append(path)
    return paths


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _config(args) -> Tuple[str, Dict[str, Any]]:
    from src.detection.base_detector import resolve_device  # noqa: E402
    from src.detection.calibration_readiness import resolve_script_calibration  # noqa: E402
    from src.utils.config import Config  # noqa: E402
    from src.utils.video_upscale import ensure_1080  # noqa: E402

    config = Config.load(args.config) if args.config else Config.default()
    # Same order as src/main.py: upscale a sub-1080p source ONCE, then check
    # the calibration against the frames the pipeline will actually see.
    video = str(ensure_1080(args.video, target_height=config.get("upscale_to_height", 1080)))
    court = resolve_script_calibration(
        video, args.court, False, ROOT / "calibrations", "probe_identity_switches.py")
    config["court_calibration_path"] = court
    config["device"] = resolve_device(args.device)
    ball_model = ROOT / "models" / "volleyball_ball_best.pt"
    if ball_model.exists():
        config["ball_model_path"] = str(ball_model)
    return video, config


def print_report(record: Dict[str, Any], gt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    fps = record.get("fps") or 30.0
    report: Dict[str, Any] = {"labels": label_stats(record)}
    print(f"\nframes: {len(record['frames'])}   enrolled: {record.get('enrolled')}")
    print("flips (side switches detected):")
    for f in record.get("flips", []):
        s = f["frame"] / fps
        print(f"  frame {f['frame']} ({int(s // 60)}:{s % 60:04.1f})  onset {f['onset']}  "
              f"-> team {'A' if f['near_squad'] == 1 else 'B'} near")
    print(f"label coverage (fraction of frames shown): {report['labels']['coverage']}")
    print(f"label teleports (label jumps to another id >200 px away): {report['labels']['teleports']}")
    if record.get("learned"):
        print(f"learned prototypes per view: {record['learned']}")
    if gt is None:
        return report
    orient = score_orientation(record, gt)
    flips = score_flips(record, gt, late_frames=int(5 * fps))
    acts = score_actions(record, gt)
    report.update(orientation={k: v for k, v in orient.items() if k != "rows"},
                  flips=flips, actions=acts)
    print(f"\n[1] orientation at GT contacts: {orient['ok']}/{orient['n']} ok, "
          f"{orient['wrong']} wrong, {orient['doubt']} in doubt; wrong points {orient['wrong_points']}")
    print(f"[2] switch windows: {flips['ok']}/{flips['n_windows']} ok")
    for w in flips["windows"]:
        print(f"    after P{w['after_point']} window {w['window']}: {w['verdict']} {w['flips']}")
    print(f"    stray flips: {flips['stray_flips']}")
    print(f"[3] action attribution (matched {acts['n_matched']}/{acts['n_gt']} GT contacts):")
    for key, name in (("label", "team resolver"), ("legacy_label", "legacy #82")):
        r = acts[key]
        print(f"    {name:14s} squad ok {r['ok']}  wrong {r['wrong']}  unlabeled {r['unlabeled']}")
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("video", nargs="?", help="video to decode (omit with --reuse)")
    ap.add_argument("--court", default=None, help="calibration JSON (default: auto by stem)")
    ap.add_argument("--config", default=None, help="config yaml/json overrides")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--sheet-every", type=float, default=20.0, help="seconds between sheet columns")
    ap.add_argument("--contacts-gt", default=None, help="match-contacts-v1 GT JSON")
    ap.add_argument("--out", default=None, help="output dir (default output/identity_probe/<stem>)")
    ap.add_argument("--reuse", default=None, help="re-score an identity_probe.json, no decode")
    args = ap.parse_args(argv)

    gt = json.loads(Path(args.contacts_gt).read_text()) if args.contacts_gt else None
    if args.reuse:
        record = json.loads(Path(args.reuse).read_text())
        out_dir = Path(args.reuse).parent
    else:
        if not args.video:
            ap.error("a video is required unless --reuse is given")
        from src.utils.video_upscale import resolve_source_stem  # noqa: E402

        stem = resolve_source_stem(args.video)
        out_dir = Path(args.out) if args.out else ROOT / "output" / "identity_probe" / stem
        out_dir.mkdir(parents=True, exist_ok=True)
        video, config = _config(args)
        record, sheets = sequential_pass(video, config, args.max_frames, args.sheet_every)
        (out_dir / "identity_probe.json").write_text(json.dumps(record))
        for path in write_sheets(sheets, record["fps"], out_dir):
            print(f"contact sheet: {path}")
    report = print_report(record, gt)
    (out_dir / "identity_report.json").write_text(json.dumps(report, indent=1))
    print(f"\nreport: {out_dir / 'identity_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
