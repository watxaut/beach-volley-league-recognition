"""Slot thumbnails for the admin's assignment screen (who is P1A?).

A few CREDITED touches per slot are cropped from the run's video with the
player's box from the ``--diag-dump`` (same frame space: the decoded,
possibly ``_up1080``, file the run read). The video is decoded SEQUENTIALLY
with ``grab()`` up to the last needed frame -- never positioned with a seek,
which lands -28..+30 frames off on this VFR camera (AGENTS.md §9). The first
touches of each slot are used, so the decode stops early in the video.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .bundle import SLOTS

TOUCHES_PER_SLOT = 3
THUMB_HEIGHT_PX = 240
PAD_FRACTION = 0.15
#: How far from the touch frame to look for the player's box in the dump.
BOX_SEARCH_FRAMES = 3


def pick_frames(recon: Dict, per_slot: int = TOUCHES_PER_SLOT) -> Dict[str, List[int]]:
    """slot -> the first ``per_slot`` frames where that slot is credited."""
    out: Dict[str, List[int]] = {s: [] for s in SLOTS}
    for pt in recon.get("points") or []:
        for t in pt.get("touches") or []:
            slot = t.get("player")
            if slot in out and t.get("observed") and len(out[slot]) < per_slot:
                out[slot].append(int(t["frame"]))
    return out


def _boxes(diag_path: Path, wanted: Dict[str, List[int]]) -> Dict[Tuple[str, int], Tuple]:
    """(slot, touch frame) -> (frame, bbox) of the labelled player nearest in time."""
    from src.postrun.stream import load_stream

    stream = load_stream(str(diag_path))
    found: Dict[Tuple[str, int], Tuple] = {}
    for slot, frames in wanted.items():
        for f in frames:
            for d in range(BOX_SEARCH_FRAMES + 1):
                hit = None
                for g in ((f,) if d == 0 else (f - d, f + d)):
                    if 0 <= g < stream.n_frames:
                        hit = next((p for p in stream.players[g]
                                    if p.label == slot and not p.predicted), None)
                        if hit:
                            found[(slot, f)] = (g, hit.bbox)
                            break
                if hit:
                    break
    return found


def _crop(frame, bbox):
    import cv2

    h, w = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    pw, ph = (x2 - x1) * PAD_FRACTION, (y2 - y1) * PAD_FRACTION
    x1, y1 = max(0, int(x1 - pw)), max(0, int(y1 - ph))
    x2, y2 = min(w, int(x2 + pw)), min(h, int(y2 + ph))
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame[y1:y2, x1:x2]
    scale = THUMB_HEIGHT_PX / crop.shape[0]
    return cv2.resize(crop, (max(1, int(crop.shape[1] * scale)), THUMB_HEIGHT_PX),
                      interpolation=cv2.INTER_AREA)


def make_slot_thumbnails(video_path: Path, diag_path: Path, recon: Dict,
                         out_dir: Path) -> Dict[str, Path]:
    """Write ``<out_dir>/<slot>.jpg`` (the tallest box among the slot's first
    credited touches). Returns the slots that got one."""
    import cv2

    wanted = pick_frames(recon)
    boxes = _boxes(diag_path, wanted)
    if not boxes:
        return {}
    by_frame: Dict[int, List[Tuple[str, Tuple]]] = {}
    for (slot, _), (frame, bbox) in boxes.items():
        by_frame.setdefault(frame, []).append((slot, bbox))
    last = max(by_frame)

    best: Dict[str, Tuple[float, object]] = {}
    cap = cv2.VideoCapture(str(video_path))
    try:
        idx = 0
        while idx <= last:
            if not cap.grab():
                break
            if idx in by_frame:
                ok, frame = cap.retrieve()
                if ok:
                    for slot, bbox in by_frame[idx]:
                        height = bbox[3] - bbox[1]
                        if height > best.get(slot, (-1.0, None))[0]:
                            img = _crop(frame, bbox)
                            if img is not None:
                                best[slot] = (height, img)
            idx += 1
    finally:
        cap.release()

    out_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}
    for slot, (_, img) in best.items():
        path = out_dir / f"{slot}.jpg"
        cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        written[slot] = path
    return written


def locate_decoded_video(decoded_path: Optional[str], *names: str) -> Optional[Path]:
    """The file the run decoded, or its renamed twin.

    ``pipeline_output.json`` records the path the run READ. ``make inbox`` names
    the video (``YYYYMMDD_HHMM_<venue>_<text>``) after calibration and the run
    can predate the rename, so the recorded path may be gone while the same
    video sits next to it under the match name. ``names`` (match key, run
    directory name) are tried as stems in the recorded directory, with the
    ``_up1080`` cache variant and the usual extensions.
    """
    if not decoded_path:
        return None
    p = Path(decoded_path)
    if p.exists():
        return p
    exts = (p.suffix, ".mp4", ".MP4", ".mov", ".MOV", ".m4v", ".mkv", ".avi")
    for name in names:
        for stem in (name, f"{name}_up1080"):
            for ext in dict.fromkeys(exts):
                cand = p.with_name(stem + ext)
                if cand.exists():
                    return cand
    return None


def find_source_video(decoded_path: Optional[str]) -> Optional[Path]:
    """The ORIGINAL file behind the path the run decoded (``<stem>_up1080.mp4``
    is a cache next to ``<stem>.<ext>``): what the video hash is taken of."""
    if not decoded_path:
        return None
    from src.utils.video_upscale import resolve_source_stem

    p = Path(decoded_path)
    stem = resolve_source_stem(p)
    if stem == p.stem:
        return p if p.exists() else None
    for ext in (".mp4", ".MP4", ".mov", ".MOV", ".m4v", ".mkv", ".avi"):
        cand = p.with_name(stem + ext)
        if cand.exists():
            return cand
    return None
