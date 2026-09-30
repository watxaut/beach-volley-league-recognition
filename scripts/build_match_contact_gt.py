#!/usr/bin/env python3
"""G0 — match-level contact GT (owner-dictated P1-P33, 20260920 match).

Transcribes the owner's TWO-dialect contact dictation
(`ground_truth/20260920_match_ari_joan_contacts_p1_p8.txt`, which carries the
WHOLE match P1-P33 since 2026-09-30) into a machine-readable GT JSON on the
MATCH frame axis — the same axis as the serve anchors and every pipeline
`frame_number`, so NO clip offset map is involved. The per-contact translation
is `scripts/build_dev_clip_gt.py::contact_events` with an IDENTITY
clip<->match map, so the match GT and the dev-clip GT share one event shape
(`source="owner_gt"`, coarse `frame_tolerance`, per-possession touch numbers).

The point windows carried alongside are the episode map's PREDICTIONS, flagged
`window_is_prediction=True` (the dev-clip GT does the same); they are never
ground truth and the GT JSON is fully usable without them (`--episode-map ""`).

Also renders one contact-sheet PNG per point from the match video (sequential,
VFR-safe decode) plus a `README.md` index, so the owner can spot-check the
transcription.

Outputs (defaults):
    ground_truth/20260920_match_contacts.json
    output/match_contact_sheet/P<n>.png + README.md

Usage:
    venv/bin/python scripts/build_match_contact_gt.py              # JSON+sheets
    venv/bin/python scripts/build_match_contact_gt.py --no-sheets  # JSON only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_dev_clip_gt import (  # noqa: E402
    CONTACT_FRAME_TOLERANCE,
    CONTACTS,
    SOURCE_OWNER,
    STATUS_OWNER_DICTATED,
    contact_events,
    parse_contact_gt,
)

MATCH = "resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4"
MATCH_CONTACTS = "ground_truth/20260920_match_contacts.json"
EPISODE_MAP = "output/episode_point_map.json"
PIPELINE = "output/match20260920_posegate/pipeline_output.json"
SHEET_DIR = "output/match_contact_sheet"
DEFAULT_FPS = 25.6702272643995   # pipeline_output.json -> video.fps (VFR average)


def _pipeline_fps(path: str, default: float = DEFAULT_FPS) -> float:
    """The pipeline's measured average fps, when the artifact exists."""
    p = Path(path)
    if not p.exists():
        return default
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
        fps = (blob.get("video") or {}).get("fps")
        return float(fps) if fps else default
    except Exception:
        return default


def _episode_windows(path: str) -> Dict[int, Dict[str, Any]]:
    """{point: window/serve info} from the episode map (a PREDICTION, not GT)."""
    if not path or not str(path).strip():
        return {}
    p = Path(path)
    if not p.exists() or p.is_dir():
        return {}
    em = json.loads(p.read_text(encoding="utf-8"))
    out: Dict[int, Dict[str, Any]] = {}
    for v in em.get("points", []):
        win = v.get("window_frames")
        if not win:
            continue
        out[int(v["point"])] = {"start": int(win[0]), "end": int(win[1]),
                                "serve_squad": v.get("serve_squad")}
    return out


# ----------------------------------------------------------------------
# pure builder
# ----------------------------------------------------------------------

def build_match_gt(contacts_path: str = CONTACTS, video: str = MATCH,
                   fps: float = DEFAULT_FPS, episode_map: str = EPISODE_MAP,
                   point_range: Optional[Sequence[int]] = None
                   ) -> Dict[str, Any]:
    """The match-level GT blob. No video is decoded, no `src/` import."""
    doc = parse_contact_gt(contacts_path)
    points_doc = doc["points"]
    by_point = {int(p["point"]): p for p in points_doc}
    wanted = [int(k) for k in point_range] if point_range else sorted(by_point)

    max_frame = max((int(c["match_frame"]) for p in points_doc
                     for c in p.get("contacts", [])), default=0)
    n_frames = max_frame + 1
    identity = {"segments": [{"clip_start": 0, "clip_end": n_frames - 1,
                              "match_offset": 0}],
                "drift": False, "checks": []}
    events, unmappable = contact_events(n_frames, identity, doc, wanted)
    ev_by_point: Dict[int, List[Dict[str, Any]]] = {}
    for e in events:
        ev_by_point.setdefault(int(e["point"]), []).append(e)
    windows = _episode_windows(episode_map)

    points: List[Dict[str, Any]] = []
    for k in wanted:
        pd = by_point.get(k, {})
        cs = pd.get("contacts", [])
        frames = [int(c["match_frame"]) for c in cs]
        win = windows.get(k, {})
        points.append({
            "point": k,
            "side_switch_after": bool(pd.get("side_switch_after", False)),
            "n_contacts": len(cs),
            "match_frame_range": [min(frames), max(frames)] if frames else None,
            # window from the episode map: a PREDICTION, never ground truth
            "match_start_frame": win.get("start"),
            "match_end_frame": win.get("end"),
            "window_source": ("episode_map_emission_window" if win else None),
            "window_is_prediction": True,
            "predicted_serve_squad": win.get("serve_squad"),
            "contacts": cs,
            "events": ev_by_point.get(k, []),
        })

    graded = sorted(events, key=lambda e: e["frame"])
    return {
        "status": STATUS_OWNER_DICTATED,
        "status_note": (
            "OWNER_DICTATED: the whole 20260920 match (P1-P33) contact GT. "
            "The owner dictated it in two plain-text dialects "
            f"({contacts_path}; P1-P8 2026-09-28, P9-P33 2026-09-30). FRAMES "
            f"ARE COARSE (owner estimates, +-{CONTACT_FRAME_TOLERANCE}f — the "
            "txt header): nothing here is frame-exact, and a prediction "
            "outside the tolerance is NOT a GT error by construction. "
            "`player_id` is the pipeline track id valid AT the contact frame "
            "(ids are NOT stable across occlusions — see the txt header)."
        ),
        "video": video,
        "fps": fps,
        "fps_note": "VFR container; this is the pipeline's measured average "
                    "(25.67 fps), not the 30.12 nominal rate",
        "resolution": [1920, 1080],
        "frame_indexing": "MATCH frames — the same axis as the serve anchors "
                          "and every pipeline `frame_number`; no clip-local "
                          "frames here (the dev-clip GT carries those).",
        "generated_by": "scripts/build_match_contact_gt.py",
        "points": points,
        "annotated_frames": {
            "ball": {"description": "No ball annotations (contact GT only)",
                     "frames": {}},
            "players": {"description": "No player boxes (player_id only)",
                        "frames": {}},
            "actions": {
                "description": "Owner-dictated rally contacts, MATCH frames. "
                               "Every event is source='owner_gt'; frames are "
                               "coarse (see status_note).",
                "events": graded,
            },
        },
        "provenance": {
            "owner_gt_inputs": [contacts_path],
            "dialects": {
                "A": "P1-P8: `<side> team P<k> <action> at f<frame>`",
                "B": "P9-P33 (2026-09-30): NT/FT abbreviations, frame-first "
                     "form, bare frames without `f`, `-> overpass` relabels, "
                     "prose blocks",
            },
            "team_mapping": "near/far are court HALVES; the squads are FIXED "
                            "and every `Side switch` marker flips the mapping "
                            "(parity): the 4 switches after P7/14/21/28 leave "
                            "`near` = Team A again from P29.",
            "contacts_unparsed_lines": doc["unparsed"],
            "contacts_notes": doc["notes"],
            "contacts_unmappable": unmappable,
            "n_owner_contact_events": len(graded),
            "contact_counts_by_point": {
                k: len(by_point.get(k, {}).get("contacts", [])) for k in wanted},
            "graded_events_source": SOURCE_OWNER,
            "window_source": ("output/episode_point_map.json (PREDICTION — "
                              "never ground truth)"),
        },
    }


# ----------------------------------------------------------------------
# contact sheets (match video, sequential decode)
# ----------------------------------------------------------------------

TILE_W, TILE_H = 480, 270
COLS = 4
MARGIN = 26
LABEL_H = 58
HEAD = 70


def _label(img: np.ndarray, lines: Sequence[str], color=(0, 255, 255),
           top: bool = True) -> None:
    y = 20 if top else img.shape[0] - 14 - 18 * (len(lines) - 1)
    for ln in lines:
        cv2.putText(img, ln, (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
        cv2.putText(img, ln, (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        y += 18


def render_sheets(video_path: str, points: Sequence[Dict[str, Any]],
                  out_dir: str) -> List[str]:
    """One PNG grid per point, read back from the MATCH video in one pass."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    wanted: List[Tuple[Dict[str, Any], Dict[str, Any]]] = [
        (p, e) for p in points for e in p["events"]]
    wanted.sort(key=lambda pe: (pe[0]["point"], pe[1]["frame"]))
    need = sorted({int(e["frame"]) for _p, e in wanted})
    frames: Dict[int, np.ndarray] = {}
    if need:
        want = set(need)
        last = need[-1]
        cap = cv2.VideoCapture(video_path)
        try:
            i = 0
            while i <= last:
                ok, fr = cap.read()
                if not ok:
                    break
                if i in want:
                    frames[i] = fr
                i += 1
        finally:
            cap.release()

    written: List[str] = []
    for p in points:
        evs = [e for pp, e in wanted if pp["point"] == p["point"]]
        if not evs:
            continue
        rows = (len(evs) + COLS - 1) // COLS
        sheet = np.full((HEAD + rows * (TILE_H + LABEL_H + MARGIN) + 24,
                         COLS * TILE_W, 3), 24, np.uint8)
        title = (f"GT P{p['point']}  contacts={p['n_contacts']}  "
                 f"window(PRED)={p['match_start_frame']}-{p['match_end_frame']}"
                 + ("  SIDE SWITCH after this point"
                    if p["side_switch_after"] else ""))
        cv2.putText(sheet, title, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (255, 255, 255), 1)
        cv2.putText(sheet, f"owner dictation, MATCH frames (coarse +/-"
                           f"{CONTACT_FRAME_TOLERANCE}f) - source=owner_gt",
                    (8, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
        for idx, e in enumerate(evs):
            r, c = divmod(idx, COLS)
            x0 = c * TILE_W
            y0 = HEAD + r * (TILE_H + LABEL_H + MARGIN)
            img = frames.get(int(e["frame"]))
            colour = (0, 255, 0)
            if img is None:
                img = np.zeros((TILE_H, TILE_W, 3), np.uint8)
                _label(img, ["FRAME UNAVAILABLE"], (0, 0, 255))
            else:
                img = cv2.resize(img, (TILE_W, TILE_H), interpolation=cv2.INTER_AREA)
                _label(img, [
                    f"f{e['frame']} {(e.get('final_action') or 'TOUCH (no label)')}"
                    f"  side={e.get('owner_side_word')} team={e.get('player_team')}",
                    f"player={e.get('player_id')} touch={e.get('touch_number')}"
                    + (f" spike={e['spike_type']}" if e.get("spike_type") else "")
                    + (f" {e['outcome']}" if e.get("outcome") else ""),
                    f"note: {(e.get('owner_note') or '-')[:64]}",
                ], colour, top=False)
            sheet[y0:y0 + TILE_H, x0:x0 + TILE_W] = img
            lab = (f"f{e['frame']} | {e.get('final_action')} | "
                   f"team={e.get('player_team')} | player={e.get('player_id')}")
            cv2.putText(sheet, lab[:70], (x0 + 6, y0 + TILE_H + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            cv2.putText(sheet, f"note: {(e.get('owner_note') or '-')[:60]}",
                        (x0 + 6, y0 + TILE_H + 36),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
        path = str(Path(out_dir) / f"P{p['point']}.png")
        cv2.imwrite(path, sheet)
        written.append(path)
    return written


def render_index(points: Sequence[Dict[str, Any]], gt_path: str,
                 out_dir: str) -> str:
    """Markdown index of the match contact GT (per point, per contact)."""
    lines: List[str] = [
        "# Match contact GT — owner-dictated P1-P33",
        "",
        f"GT JSON: `{gt_path}` (match frames; every event `source=owner_gt`).",
        "",
    ]
    for p in points:
        if not p["events"]:
            continue
        lines.append(f"## P{p['point']}"
                     + (" — **SIDE SWITCH after this point**"
                        if p["side_switch_after"] else ""))
        lines += ["", "| frame | action | gesture | side | team | player | "
                  "touch | note |", "|---|---|---|---|---|---|---|---|"]
        for e in p["events"]:
            lines.append(
                f"| {e['frame']} | {e.get('final_action') or '—'} | "
                f"{e.get('gesture') or '—'} | {e.get('owner_side_word')} | "
                f"{e.get('player_team')} | {e.get('player_id')} | "
                f"{e.get('touch_number')} | {e.get('owner_note') or ''} |")
        lines.append("")
    path = Path(out_dir) / "README.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--contacts", default=CONTACTS,
                    help="owner-dictated contact GT txt (both dialects)")
    ap.add_argument("--video", default=MATCH,
                    help="match video (sheets only; stored verbatim in the GT)")
    ap.add_argument("--out", default=MATCH_CONTACTS)
    ap.add_argument("--episode-map", default=EPISODE_MAP,
                    help="prediction windows to ATTACH (flagged; '' to skip)")
    ap.add_argument("--pipeline", default=PIPELINE, help="for the measured fps")
    ap.add_argument("--sheet-dir", default=SHEET_DIR)
    ap.add_argument("--fps", type=float, default=None)
    ap.add_argument("--points", default=None, help="e.g. 1-33 or 9,10")
    ap.add_argument("--no-sheets", action="store_true")
    args = ap.parse_args(argv)

    def _p(s: str) -> str:
        if not s:
            return s
        p = Path(s)
        return str(p if p.is_absolute() or p.exists() else ROOT / s)

    point_range: Optional[List[int]] = None
    if args.points:
        if "-" in args.points:
            lo, hi = args.points.split("-")
            point_range = list(range(int(lo), int(hi) + 1))
        else:
            point_range = [int(x) for x in args.points.split(",")]

    fps = args.fps if args.fps is not None else _pipeline_fps(_p(args.pipeline))
    gt = build_match_gt(_p(args.contacts), args.video, fps,
                        _p(args.episode_map), point_range)

    out = _p(args.out)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(gt, indent=2) + "\n", encoding="utf-8")
    print(f"[gt] wrote {out}: {len(gt['points'])} points, "
          f"{gt['provenance']['n_owner_contact_events']} owner_gt contacts, "
          f"{len(gt['provenance']['contacts_unparsed_lines'])} unparsed line(s), "
          f"{len(gt['provenance']['contacts_notes'])} owner note line(s)")

    if not args.no_sheets:
        written = render_sheets(_p(args.video), gt["points"], _p(args.sheet_dir))
        index = render_index(gt["points"], args.out, _p(args.sheet_dir))
        print(f"[sheets] {len(written)} PNG grids + {index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())