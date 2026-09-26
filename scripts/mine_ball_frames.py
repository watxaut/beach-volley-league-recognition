"""Mine hard frames from a match video for ball-detector retraining.

Open point 20, second half of the lever: the fine-tuned ball detector's
confidence is background-dependent (sky-backed med 0.90 vs sand-backed med
0.20 -- see output/match20260920/ball_probe_bgsky.json), and 10-31% of
GAME_ON frames are detector-BLIND (0 candidates @0.15), unreachable by any
tracker-side gate. This script mines the frames the owner should annotate
in Roboflow so the next fine-tune learns sand/building-backed balls:

  blind       0 candidates @0.15               -- class (a); owner decides
                                                  ball vs. true negative
  low_sand    candidates but none >=0.4,       -- class (b) hard positives
              best non-suspect is sand-backed
  low_other   same, best backed by "other"     -- class (b), buildings etc.
  sand_noise  ONLY stationary-suspect cands    -- hard negatives (the venue's
                                                  ~2.2 det/frame sand noise)
  sky_control best cand >=0.4 AND sky-backed   -- regression guard so the
                                                  retrain doesn't trade sky
                                                  for sand

Two passes over the GAME_ON ranges of --game-state-csv: (1) run the
production detector (same ctor as FrameProcessor) + the probe's bg_class
stratifier over every frame; (2) re-read and write only the sampled picks
as JPG + optional YOLO pre-labels (all non-suspect candidates @conf floor;
blind frames get an EMPTY label = negative unless the owner finds a ball).
Sampling is seeded-shuffle + greedy min-spacing so picks spread across the
whole match instead of clustering in one long rally.

Output (Roboflow-ready: drag & drop images/ + labels/ together):
    <output-dir>/images/<stem>_f<idx>.jpg
    <output-dir>/labels/<stem>_f<idx>.txt   (PRE-LABELS -- review required)
    <output-dir>/manifest.json              (audit trail: class, candidates)

Round 2 (2026-09-26, after the v2_match candidate was REJECTED at the
validation gate): rebalanced mining only -- the blind/low classes were
genuinely fixed (blind 25->2% on the probe episodes) but confident FPs
exploded (330->684) and sky TRUE conf collapsed on unseen episodes
(ep35 med 0.90->0.47). So round 2 mines ONLY hard negatives + sky
controls and EXCLUDES the previous round's picks:
    --caps 0,0,0,200,150 --no-prelabel \
    --exclude-manifest resources/frames/match20260920/manifest.json \
    --output-dir resources/frames/match20260920_round2
The exclusion is same-class +-spacing (classes are deterministic, so a
previous pick of class X can only collide with this round's pool of X).

After the owner reviews/exports and the model is retrained, the validation
gate is: entreno A/B drift-lock -> match re-run + evaluate_match_points ->
re-run diag_ball_probe_bgsky.py on the same 5 episodes to quantify the
class (a)/(b) shrinkage.
"""

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.ball_detector import BallDetector
from src.utils.video_upscale import resolve_source_stem

# Frame classes, in admission order (see module docstring).
CLASSES = ("blind", "low_sand", "low_other", "sand_noise", "sky_control")
DEFAULT_CAPS = {
    "blind": 250,
    "low_sand": 100,
    "low_other": 50,
    "sand_noise": 60,
    "sky_control": 40,
}
HIGH_CONF = 0.4  # the tracker's low_confidence_threshold; the (a)/(b) split key


def bg_class(frame, cx, cy):
    """Classify the background BEHIND a candidate from its patch colours.

    Identical to diag_ball_probe_bgsky.bg_class (keep in sync): the probe's
    sky/sand/other stratification is the validated reference.
    """
    h, w = frame.shape[:2]
    x0, y0 = int(cx) - 15, int(cy) - 15
    patch = frame[max(0, y0):min(h, y0 + 31), max(0, x0):min(w, x0 + 31)]
    if patch.size == 0:
        return "other"
    b, g, r = patch.reshape(-1, 3).mean(axis=0)
    if b > 120 and b - r > 25:
        return "sky"
    if r - b > 25 and r > 110:
        return "sand"
    return "other"


def classify_frame(cands):
    """Map one frame's candidate list to a mining class.

    cands: list of dicts with 'conf', 'bg', 'ss' (stationary_suspect).
    Returns (class, best) where best is the highest-conf non-suspect
    candidate (None for blind/noise frames). Frames with a >=0.4 non-sky
    best candidate are 'high_other' -- recorded in the manifest but NOT
    mined (they are not class (a)/(b) targets).
    """
    if not cands:
        return "blind", None
    movers = [c for c in cands if not c["ss"]]
    if not movers:
        return "sand_noise", None
    best = max(movers, key=lambda c: c["conf"])
    if best["conf"] >= HIGH_CONF:
        return ("sky_control" if best["bg"] == "sky" else "high_other"), best
    return (f"low_{best['bg']}" if best["bg"] in ("sand", "other")
            else "low_other"), best


def exclusion_zone(frames, margin):
    """All frames within +-margin of any frame in `frames`, as a set.

    Used to keep a previous mining round's picks (and their near
    duplicates) out of this round's pools.
    """
    out = set()
    for f in frames:
        for d in range(-margin, margin + 1):
            out.add(f + d)
    return out


def pick_frames(pool, cap, spacing, rng):
    """Sample <=cap frame indices from pool with min `spacing` separation.

    Seeded shuffle then greedy pick: coverage spread without order bias.
    pool: iterable of frame indices (ints); returns a sorted list.
    """
    shuffled = list(pool)
    rng.shuffle(shuffled)
    picked = []
    for f in shuffled:
        if len(picked) >= cap:
            break
        if all(abs(f - p) >= spacing for p in picked):
            picked.append(f)
    return sorted(picked)


def game_on_ranges(csv_path):
    """Contiguous GAME_ON frame ranges [(start, end_inclusive), ...] from a
    results_game_state.csv (Frame_Index, Game_State columns)."""
    rows = []
    with open(csv_path) as fh:
        for r in csv.DictReader(fh):
            rows.append((int(r["Frame_Index"]), r["Game_State"]))
    rows.sort(key=lambda x: x[0])
    ranges = []
    start = None
    prev = None
    for f, state in rows:
        if state == "game_on":
            if start is None:
                start = f
            prev = f
        elif start is not None:
            ranges.append((start, prev))
            start = None
    if start is not None:
        ranges.append((start, prev))
    return ranges


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--video", default="resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4")
    ap.add_argument("--game-state-csv", default="output/match20260920_lowconf/results_game_state.csv",
                    help="per-frame game-state CSV; GAME_ON runs define the mined ranges")
    ap.add_argument("--output-dir", default="resources/frames/match20260920")
    ap.add_argument("--model", default="models/volleyball_ball_best.pt")
    ap.add_argument("--conf", type=float, default=0.15,
                    help="detector confidence floor (production parity: 0.15)")
    ap.add_argument("--caps", default=",".join(str(DEFAULT_CAPS[c]) for c in CLASSES),
                    help="comma caps for " + ",".join(CLASSES))
    ap.add_argument("--exclude-manifest", default=None,
                    help="mining manifest of a previous round: its same-class "
                         "picks (+-spacing) are excluded from this round's pools "
                         "(round-2 rebalanced mining)")
    ap.add_argument("--spacing", type=int, default=5,
                    help="min frame distance between two picks of one class")
    ap.add_argument("--pad", type=int, default=30,
                    help="warm-up frames before each GAME_ON range (static-suspect state; not mined)")
    ap.add_argument("--jpg-quality", type=int, default=95)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--no-prelabel", action="store_true",
                    help="write images only, no YOLO txt pre-labels")
    ap.add_argument("--dry-run", action="store_true",
                    help="classify + sample only; write manifest, no images")
    args = ap.parse_args()

    caps = dict(zip(CLASSES, (int(x) for x in args.caps.split(","))))
    out_dir = Path(args.output_dir)
    stem = resolve_source_stem(args.video)

    ranges = game_on_ranges(args.game_state_csv)
    n_scan = sum(e - s + 1 for s, e in ranges)
    print(f"{len(ranges)} GAME_ON ranges, {n_scan} frames to scan "
          f"(+{args.pad}f warm-up each)")

    det = BallDetector(model_path=args.model, confidence_threshold=args.conf,
                       device=args.device)
    cap_video = cv2.VideoCapture(args.video)
    total = cap_video.get(cv2.CAP_PROP_FRAME_COUNT)

    # ---- pass 1: classify every GAME_ON frame --------------------------
    rows = {}          # frame -> {"cls": ..., "cands": [...]}
    scanned = 0
    for s, e in ranges:
        det.reset()  # fresh static-suspect memory per rally
        cap_video.set(cv2.CAP_PROP_POS_FRAMES, max(0, s - args.pad))
        f = max(0, s - args.pad)
        while f <= e:
            ok, frame = cap_video.read()
            if not ok:
                break
            if f >= s:
                cands = []
                for d in det.detect(frame):
                    x1, y1, x2, y2 = d["bbox"]
                    cands.append({
                        "c": [round(d["center"][0]), round(d["center"][1])],
                        "conf": round(float(d["confidence"]), 3),
                        "w": int(x2 - x1), "h": int(y2 - y1),
                        "ss": bool(d.get("stationary_suspect", False)),
                        "bg": bg_class(frame, d["center"][0], d["center"][1]),
                    })
                cls, _ = classify_frame(cands)
                rows[f] = {"cls": cls, "cands": cands}
                scanned += 1
                if scanned % 500 == 0:
                    print(f"  classified {scanned}/{n_scan}", flush=True)
            else:
                det.detect(frame)  # warm up static-suspect memory only
            f += 1

    counts = Counter(r["cls"] for r in rows.values())
    print("\nscanned-frame classes:", dict(counts))

    # ---- sample ---------------------------------------------------------
    excluded = {cls: set() for cls in CLASSES}
    if args.exclude_manifest:
        prev = json.loads(Path(args.exclude_manifest).read_text())
        for cls in CLASSES:
            excluded[cls] = exclusion_zone(prev["picked"].get(cls, []),
                                           args.spacing)
        print(f"excluding previous picks (+-{args.spacing}f) from "
              f"{args.exclude_manifest}: "
              + ", ".join(f"{cls} {len(excluded[cls])}" for cls in CLASSES))

    rng = random.Random(args.seed)
    picks = {}
    for cls in CLASSES:
        pool = (f for f, r in rows.items()
                if r["cls"] == cls and f not in excluded[cls])
        picks[cls] = pick_frames(pool, caps[cls], args.spacing, rng)
        print(f"  {cls:<12} scanned {counts.get(cls, 0):>5}  "
              f"excl {len(excluded[cls]):>5}  cap {caps[cls]:>3}  "
              f"picked {len(picks[cls])}")
    picked_frames = sorted(f for lst in picks.values() for f in lst)

    # ---- pass 2: write picked frames + pre-labels -----------------------
    images_dir, labels_dir = out_dir / "images", out_dir / "labels"
    if not args.dry_run:
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        encode = [int(cv2.IMWRITE_JPEG_QUALITY), args.jpg_quality]
        written = 0
        prev_cls = {}
        for cls in CLASSES:
            prev_cls.update({f: cls for f in picks[cls]})
        cap_video.set(cv2.CAP_PROP_POS_FRAMES, 0)
        f = 0
        it = iter(picked_frames)
        target = next(it, None)
        while target is not None:
            ok, frame = cap_video.read()
            if not ok:
                raise SystemExit(f"decode ended before picked frame {target}")
            if f == target:
                name = f"{stem}_f{f:06d}"
                cv2.imwrite(str(images_dir / f"{name}.jpg"), frame, encode)
                if not args.no_prelabel:
                    h, w = frame.shape[:2]
                    lines = []
                    for c in rows[f]["cands"]:
                        if c["ss"]:
                            continue  # suspects are the noise we teach against
                        lines.append(
                            f"0 {c['c'][0]/w:.6f} {c['c'][1]/h:.6f} "
                            f"{c['w']/w:.6f} {c['h']/h:.6f}")
                    (labels_dir / f"{name}.txt").write_text(
                        "\n".join(lines) + ("\n" if lines else ""))
                written += 1
                if written % 50 == 0:
                    print(f"  wrote {written}/{len(picked_frames)}", flush=True)
                target = next(it, None)
            f += 1
        print(f"wrote {written} images -> {images_dir}")

    cap_video.release()

    manifest = {
        "video": args.video,
        "game_state_csv": args.game_state_csv,
        "model": args.model,
        "conf": args.conf,
        "caps": caps, "spacing": args.spacing, "pad": args.pad, "seed": args.seed,
        "exclude_manifest": args.exclude_manifest,
        "excluded_counts": {cls: len(excluded[cls]) for cls in CLASSES},
        "total_frames": int(total),
        "scanned": scanned,
        "scanned_classes": dict(counts),
        "picked": {cls: picks[cls] for cls in CLASSES},
        "frames": {str(f): rows[f] for f in picked_frames},
        "prelabels": not args.no_prelabel,
        "note": "labels/*.txt are PRE-LABELS from the current detector "
                "(conf>=%s, non-suspect only) -- review/correct in Roboflow; "
                "empty txt = no candidate found (annotate the ball if you see "
                "one, else keep as negative)." % args.conf,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"manifest -> {out_dir / 'manifest.json'}")

    print("\nNext steps:")
    print("1. Upload images/ + labels/ to Roboflow (drag & drop together),")
    print("   review/correct, export YOLOv8, merge into datasets/ball_detection/")
    print("2. python scripts/prepare_dataset_for_training.py datasets/ball_detection")
    print("3. fine-tune in notebooks/finetune_yolo_ball.ipynb (Colab)")
    print("4. validation gate: entreno A/B -> match re-run + evaluate_match_points")
    print("   -> re-run diag_ball_probe_bgsky.py (class a/b shrinkage)")


if __name__ == "__main__":
    main()
