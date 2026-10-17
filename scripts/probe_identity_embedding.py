"""Can a CNN embedding tell the two players of one squad apart (#121 (f))?

1230's B players read alike against every HSV anchor, so ``id_sims`` cannot name
them. Before adding anything to the diag dump (a full re-run), test the signal
offline: take the bodies the owner's review names at the touches of one squad
(``truth.touches``), embed their crops from the video (ONE sequential decode,
§9), and score how well each descriptor recovers the owner's name when the
whole rally is held out.

PRE-REGISTERED RULE (fixed before the first run): the embedding is worth a dump
field only if its leave-one-rally-out accuracy on the squad is >= 0.90 AND at
least 0.15 above the HSV descriptor the pipeline already uses, on the
squad's NEAR half and FAR half separately. Otherwise REFUTED.

    nice -n 10 venv/bin/python scripts/probe_identity_embedding.py \
        --run output/<key> --video resources/full_videos/<key>.mp4 --squad B
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OFFSETS = (-6, -3, 0, 3, 6)   # same track id around the touch: more samples


def load_samples(run: Path, review: dict, squad: str) -> List[dict]:
    """(frame, name, rally, half, bbox-of-the-body-at-the-ball) per touch sample."""
    wanted: Dict[int, dict] = {}
    for pi, pt in enumerate(review["points"]):
        truth = pt.get("truth") or {}
        if not truth.get("is_point") or truth.get("labels_unclear"):
            continue
        near_team = truth.get("near_team")
        for t in truth.get("touches", []):
            name = t.get("player")
            if name and name.endswith(squad) and name.startswith("P"):
                half = "near" if near_team == squad else "far"
                for o in OFFSETS:
                    wanted.setdefault(t["frame"] + o, []).append(
                        {"touch": t["frame"], "name": name, "rally": pi,
                         "half": half, "off": o})
    frames = {}
    last = max(wanted)
    with open(run / "diag.jsonl") as fh:
        next(fh)
        for line in fh:
            r = json.loads(line)
            f = r.get("frame")
            if f is None or f < 0 or f > last:
                continue
            if "players" in r:
                frames[f] = r
    out = []
    for f, entries in wanted.items():
        for e in entries:
            rec = frames.get(e["touch"])
            if rec is None:
                continue
            bodies = [p for p in rec["players"] if not p.get("predicted")]
            if len(bodies) < 4:
                continue
            bodies.sort(key=lambda p: p["bbox"][3], reverse=True)   # deepest feet = near
            half = bodies[:2] if e["half"] == "near" else bodies[2:4]
            bt = (rec.get("ball_track") or {}).get("center")
            if not bt:
                dets = rec.get("ball_dets") or []
                bt = max(dets, key=lambda d: d["conf"])["center"] if dets else None
            if not bt:
                continue

            def dist(p):
                b = p["bbox"]
                return np.hypot((b[0] + b[2]) / 2 - bt[0], (b[1] + b[3]) / 2 - bt[1])
            at_ball = min(half, key=dist)
            if dist(at_ball) > 1.2 * (at_ball["bbox"][3] - at_ball["bbox"][1]):
                continue
            tid = at_ball["track_id"]
            cur = frames.get(f)
            if cur is None:
                continue
            same = [p for p in cur["players"] if p["track_id"] == tid]
            if not same:
                continue
            out.append({"frame": f, "name": e["name"], "rally": e["rally"],
                        "half": e["half"], "bbox": same[0]["bbox"]})
    return out


def decode(video: Path, samples: List[dict]) -> None:
    need = {}
    for s in samples:
        need.setdefault(s["frame"], []).append(s)
    cap = cv2.VideoCapture(str(video))
    i, last = 0, max(need)
    while i <= last:
        if not cap.grab():
            break
        if i in need:
            ok, img = cap.retrieve()
            if ok:
                for s in need[i]:
                    s["img"] = img
        i += 1
    cap.release()


def crop(img: np.ndarray, bbox) -> Optional[np.ndarray]:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = [int(round(v)) for v in bbox]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    if x2 - x1 < 8 or y2 - y1 < 16:
        return None
    return img[y1:y2, x1:x2]


def loo_rally_accuracy(X: np.ndarray, y: np.ndarray, rally: np.ndarray) -> float:
    names = sorted(set(y))
    right = n = 0
    for r in sorted(set(rally)):
        tr, te = rally != r, rally == r
        if len(set(y[tr])) < 2:
            continue
        cents = {k: X[tr & (y == k)].mean(0) for k in names}
        for xi, yi in zip(X[te], y[te]):
            pred = max(names, key=lambda k: float(
                xi @ cents[k] / (np.linalg.norm(xi) * np.linalg.norm(cents[k]) + 1e-9)))
            right += pred == yi
            n += 1
    return right / n if n else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--squad", default="B")
    ap.add_argument("--threads", type=int, default=3)
    a = ap.parse_args()
    import torch
    import torchvision
    torch.set_num_threads(a.threads)
    cv2.setNumThreads(a.threads)

    run = Path(a.run)
    review = json.load(open(next((ROOT / "ground_truth").glob(f"{run.name}_review.json"))))
    samples = load_samples(run, review, a.squad)
    print(f"{len(samples)} samples, {len({s['rally'] for s in samples})} rallies")
    decode(Path(a.video), samples)
    samples = [s for s in samples if "img" in s]

    from src.tracking.identity_resolver import compute_descriptor
    net = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.DEFAULT)
    net.fc = torch.nn.Identity()
    net.eval()
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)

    feats = {"hsv": [], "cnn": []}
    keep = []
    for s in samples:
        c = crop(s["img"], s["bbox"])
        d = compute_descriptor(s["img"], s["bbox"])
        if c is None or d is None:
            continue
        rgb = cv2.cvtColor(cv2.resize(c, (64, 128), interpolation=cv2.INTER_AREA),
                           cv2.COLOR_BGR2RGB)
        t = (torch.from_numpy(rgb).permute(2, 0, 1).float().unsqueeze(0) / 255 - mean) / std
        with torch.no_grad():
            feats["cnn"].append(net(t)[0].numpy())
        feats["hsv"].append(np.asarray(d.parts, dtype=np.float64).ravel())
        keep.append(s)
        s.pop("img")
    y = np.array([s["name"] for s in keep])
    rally = np.array([s["rally"] for s in keep])
    half = np.array([s["half"] for s in keep])
    for h in ("near", "far", "all"):
        m = np.ones(len(keep), bool) if h == "all" else half == h
        if m.sum() < 6 or len(set(y[m])) < 2:
            print(h, "too few samples", int(m.sum()))
            continue
        row = {k: loo_rally_accuracy(np.array(v)[m], y[m], rally[m]) for k, v in feats.items()}
        print(f"{h:4s} n={int(m.sum()):3d} " + "  ".join(f"{k}={v:.3f}" for k, v in row.items()))


if __name__ == "__main__":
    main()
