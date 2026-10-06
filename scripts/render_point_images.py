"""Render one contact-sheet image per point from match_reconstruction.json.

Each tile is the video frame of one touch, labelled with action/player/team/outcome;
a final tile shows the point end frame. Header carries the point outcome.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

TW, TH, COLS = 640, 360, 3


def put(img, text, org, scale=0.6, color=(255, 255, 255), bg=(0, 0, 0)):
    (w, h), b = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
    x, y = org
    cv2.rectangle(img, (x - 3, y - h - 3), (x + w + 3, y + b), bg, -1)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)


def load_frames(path, wanted):
    """One sequential decode pass (VFR-safe: CAP_PROP_POS_FRAMES seeks land on the wrong frame)."""
    cap = cv2.VideoCapture(path)
    frames, last = {}, max(wanted)
    for i in range(last + 1):
        if not cap.grab():
            break
        if i in wanted:
            ok, img = cap.retrieve()
            if ok:
                frames[i] = cv2.resize(img, (TW, TH))
    cap.release()
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="output/postrun/20260920_match")
    ap.add_argument("--video", default="resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4")
    ap.add_argument("--points", default="", help="comma list, default all")
    a = ap.parse_args()
    run = Path(a.run_dir)
    d = json.load(open(run / "match_reconstruction.json"))
    fps = d["fps"]
    out = run / "point_images"
    out.mkdir(exist_ok=True)
    want = {int(x) for x in a.points.split(",") if x}
    pts = [p for p in d["points"] if not want or p["point"] in want]
    needed = {t["frame"] for p in pts for t in p["touches"]} | {p["end"]["frame"] for p in pts}
    frames = load_frames(a.video, needed)
    blank = np.zeros((TH, TW, 3), np.uint8)

    def grab(_, f):
        return frames.get(f, blank).copy()

    cap = None
    for p in pts:
        tiles = []
        for t in p["touches"]:
            img = grab(cap, t["frame"])
            lab = f'f{t["frame"]} {t["action"].upper()} {t["player"] or "?"}'
            put(img, lab, (8, 24))
            if t["outcome"]:
                put(img, t["outcome"].upper(), (8, 52), color=(255, 255, 255),
                    bg=(0, 140, 0) if t["outcome"] in ("kill", "ace") else (0, 0, 180))
            if not t["observed"]:
                put(img, "inferred", (8, TH - 10), 0.5, (0, 255, 255))
            tiles.append(img)
        e = p["end"]
        img = grab(cap, e["frame"])
        put(img, f'f{e["frame"]} END: {e["kind"]} {e["side"] or ""} '
                 f'{"in" if e["in_court"] else "out" if e["in_court"] is False else ""}', (8, 24),
            bg=(120, 60, 0))
        tiles.append(img)
        while len(tiles) % COLS:
            tiles.append(np.zeros((TH, TW, 3), np.uint8))
        rows = [np.hstack(tiles[i:i + COLS]) for i in range(0, len(tiles), COLS)]
        sheet = np.vstack(rows)
        s, sa = p["serve"], p["score_after"]
        hdr = np.full((90, sheet.shape[1], 3), 30, np.uint8)
        m, sec = divmod(int(p["start_frame"] / fps), 60)
        put(hdr, f'P{p["point"]} {m:02d}:{sec:02d}  {s["team"]} serves ({s["side"]})  ->  '
                 f'{p["winner"]} WINS ({p["winner_source"]})   A {sa["A"]} - B {sa["B"]}', (10, 34), 0.9)
        fl = ", ".join(p["flags"]) or "no flags"
        put(hdr, f'ball death: {p["ball_death_read"]}   flags: {fl}', (10, 72), 0.55, (200, 200, 200))
        cv2.imwrite(str(out / f'point_{p["point"]:02d}.jpg'), np.vstack([hdr, sheet]),
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
    print("wrote", out)


if __name__ == "__main__":
    main()
