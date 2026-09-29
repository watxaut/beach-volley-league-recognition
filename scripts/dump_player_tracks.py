#!/usr/bin/env python3
"""
Dump per-frame player tracks for a video, using the SAME tracker config the
production pipeline (src.main / FrameProcessor) uses -- so the measurement
reflects reality, not the looser defaults of scripts/test_player_tracking.py
(which silently uses max_distance=150 instead of the configured 100).

Output JSON schema:
    {"video": <stem>, "fps": float, "width": int, "height": int,
     "max_players": int,
     "frames": [
        {"frame": int, "players": [
            {"track_id": int, "bbox": [x1,y1,x2,y2], "center": [cx,cy],
             "team": "A"|"B"|null, "confidence": float, "predicted": bool}
        , ...]}
     ]}

`predicted` is True for coasting (ghost) boxes the tracker emits without a
real detection -- lets analyze_tracking.py separate real tracks from ghosts.

Usage:
    python scripts/dump_player_tracks.py resources/video_entreno_1.mp4 \\
        --out-json output/baseline/video_entreno_1_tracks.json
"""

import argparse
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.player_detector import PlayerDetector
from src.detection.ball_detector import BallDetector
from src.detection.court_calibration import CourtCalibration
from src.detection.calibration_readiness import resolve_script_calibration
from src.tracking.player_tracker import PlayerTracker
from src.utils.config import Config
from src.utils.video_upscale import resolve_source_stem

# Production tracker config -- read straight from Config.DEFAULT_CONFIG so the
# measurement provably matches what FrameProcessor runs (previously these were
# hardcoded and had silently drifted: max_players=4 vs the configured 6).
_CFG = Config.DEFAULT_CONFIG
PROD_MAX_PLAYERS = _CFG["max_players"]
PROD_MAX_DISAPPEARED = _CFG["player_max_disappeared"]
PROD_MAX_DISTANCE = _CFG["tracking_max_distance"]
PROD_PLAYER_CONFIDENCE = _CFG["player_confidence"]

TEAM_COLORS = {
    "A": (255, 0, 0),    # Blue for Team A (near half)
    "B": (0, 165, 255),  # Orange for Team B (far half)
    None: (0, 255, 0),
}
PLAYER_COLORS = {
    1: (255, 0, 0),
    2: (255, 100, 100),
    3: (0, 165, 255),
    4: (100, 200, 255),
}


def main():
    parser = argparse.ArgumentParser(description="Dump per-frame player tracks (production config)")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--court", help="Court calibration JSON (auto-detected from calibrations/ if omitted)")
    parser.add_argument("--output", default="output/tracks", help="Output directory for video")
    parser.add_argument("--max-frames", type=int, default=0, help="Max frames (0 = whole video)")
    parser.add_argument("--max-players", type=int, default=PROD_MAX_PLAYERS, help="Tracker roster size")
    parser.add_argument("--out-json", help="Path to write per-frame tracks JSON")
    # Serve-zone admission (server tracking at video/rally start)
    parser.add_argument("--serve-zone-depth", type=float, default=None,
                        help="Serve-zone depth behind each baseline in metres (default: config)")
    parser.add_argument("--no-serve-zone", action="store_true", help="Disable serve-zone admission")
    parser.add_argument("--save-video", action="store_true", help="Save annotated mp4")
    parser.add_argument("--allow-uncalibrated", action="store_true",
                        help="Run without a usable court calibration (court admission, "
                             "serve-zone admission and the bystander guard are DEGRADED "
                             "-- track dumps are NOT comparable with calibrated runs).")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: cannot open {args.video}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    n_frames = total if args.max_frames <= 0 else min(args.max_frames, total)

    # Auto-load calibration + readiness gate: track dumps drive GT annotation,
    # so an uncalibrated dump must not look like a calibrated one.
    court_path = resolve_script_calibration(
        args.video, args.court, args.allow_uncalibrated,
        calibrations_dir=Path(__file__).resolve().parent.parent / "calibrations",
        script_name=Path(__file__).name,
    )
    court = CourtCalibration(court_path) if court_path else CourtCalibration()

    detector = PlayerDetector(confidence_threshold=PROD_PLAYER_CONFIDENCE)

    # Ball detector -- only used to drive the bootstrap's ball_active gate
    # (skip warmup). Optional: if it can't be built, the bootstrap falls back to
    # locking at bootstrap_max_wait, so measurement still works.
    ball_detector = None
    try:
        auto_ball = Path(__file__).resolve().parent.parent / "models" / "volleyball_ball_best.pt"
        ball_model = str(auto_ball) if auto_ball.exists() else None
        ball_detector = BallDetector(
            model_path=ball_model,
            confidence_threshold=_CFG.get("ball_confidence", 0.15),
            device=_CFG.get("device", "auto"),
        )
    except Exception as exc:  # pragma: no cover - best-effort measurement aid
        print(f"(warn) ball detector unavailable, bootstrap will use the time fallback: {exc}")

    if court.is_calibrated:
        court.set_play_area_margin(_CFG.get("player_play_area_margin_px", 100))

    tracker = PlayerTracker(
        max_players=args.max_players,
        max_disappeared=PROD_MAX_DISAPPEARED,
        max_distance=PROD_MAX_DISTANCE,
        court_calibration=court,
        appearance_weight=_CFG.get("player_appearance_weight", 0.4),
        init_frames=_CFG.get("player_init_frames", 60),
        team_vote_window=_CFG.get("player_team_vote_window", 15),
        coast_extrapolation_cap=_CFG.get("coast_extrapolation_cap", 15),
        coast_velocity_decay=_CFG.get("coast_velocity_decay", 0.85),
        gallery_enabled=_CFG.get("player_gallery_enabled", True),
        gallery_reacquire_distance_px=_CFG.get("player_gallery_reacquire_distance_px", 120.0),
        gallery_reacquire_min_appearance=_CFG.get("player_gallery_reacquire_min_appearance", 0.15),
        gallery_reacquire_appearance_min=_CFG.get("player_gallery_reacquire_appearance_min", 0.5),
        gallery_evict_min_hold_frames=_CFG.get("player_gallery_evict_min_hold_frames", 60),
        bootstrap_min_window=_CFG.get("player_bootstrap_min_window", 8),
        bootstrap_ball_required=_CFG.get("player_bootstrap_ball_required", True),
        signature_color_weight=_CFG.get("player_signature_color_weight", 0.4),
        signature_head_weight=_CFG.get("player_signature_head_weight", 0.15),
        signature_height_weight=_CFG.get("player_signature_height_weight", 0.3),
        signature_proportions_weight=_CFG.get("player_signature_proportions_weight", 0.15),
        signature_height_smoothing=_CFG.get("player_signature_height_smoothing", 30),
        off_court_grace_frames=_CFG.get("player_off_court_grace_frames", 45),
        off_court_hold_frames=_CFG.get("player_off_court_hold_frames", 90),
        off_court_cost_penalty_px=_CFG.get("player_off_court_cost_penalty_px", 300.0),
        squatter_enabled=_CFG.get("player_squatter_enabled", True),
        squatter_review_frames=_CFG.get("player_squatter_review_frames", 120),
        squatter_min_fed_frames=_CFG.get("player_squatter_min_fed_frames", 20),
        squatter_min_in_court_frac=_CFG.get("player_squatter_min_in_court_frac", 0.35),
        squatter_cooldown_radius_m=_CFG.get("player_squatter_cooldown_radius_m", 0.5),
        serve_zone_enabled=(not args.no_serve_zone),
        serve_zone_depth_m=(args.serve_zone_depth if args.serve_zone_depth is not None
                            else _CFG.get("player_serve_zone_depth_m", 3.0)),
        serve_zone_side_margin_m=_CFG.get("player_serve_zone_side_margin_m", 1.0),
        serve_zone_trial_frames=_CFG.get("player_serve_zone_trial_frames", 90),
        serve_zone_ball_votes=_CFG.get("player_serve_zone_ball_votes", 2),
        coast_vertical_damping=_CFG.get("coast_vertical_damping", 0.5),
    )

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Output naming keys on the SOURCE stem (cached _up<target> files strip
    # their suffix), matching the pipeline's calibration/output convention.
    video_name = resolve_source_stem(args.video)
    writer = None
    if args.save_video:
        out_path = str(output_dir / f"{video_name}_player_tracking.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    out_json = args.out_json or str(output_dir / f"{video_name}_tracks.json")

    frames_dump = []
    id_seen = set()
    max_simultaneous = 0

    for frame_idx in range(n_frames):
        ret, frame = cap.read()
        if not ret:
            break

        raw = detector.detect(frame)
        if court.is_calibrated:
            strict = court.filter_detections_by_court(raw)
        else:
            strict = raw
        # Association set = the detector output (already play-area bbox-overlap
        # filtered), wider than the strict set so an established track can follow
        # a player who steps off-court. NEW tracks are still gated by the strict
        # foot-in-court admission test inside PlayerTracker.
        play_area = raw
        # Raw in-court detection count -- the live/dead-ball signal
        # analyze_tracking uses (live play = 4 in court; dead ball = extras walk
        # in, > 4). Kept on the STRICT set even though the tracker is fed the
        # wider play-area set, so the live/dead logic stays correct.
        n_court_det = len(strict)
        ball_active = False
        ball_position = None
        if ball_detector is not None:
            try:
                ball_dets = ball_detector.detect(frame)
                ball_active = len(ball_dets) > 0
                if ball_dets:
                    top = max(ball_dets, key=lambda d: d.get("confidence", 0))
                    c = top.get("center")
                    if c and c[0] is not None:
                        ball_position = (float(c[0]), float(c[1]))
            except Exception:
                ball_active = False
        tracked = tracker.update(
            play_area, frame,
            strict_detections=strict,
            ball_active=ball_active,
            n_court_det=n_court_det,
            ball_position=ball_position,
        )
        max_simultaneous = max(max_simultaneous, len(tracked))

        # --- JSON dump (real boxes only by default; ghosts flagged via `predicted`) ---
        players_dump = []
        for p in tracked:
            tid = int(p.get("track_id", -1))
            id_seen.add(tid)
            # foot_team = the spec ground-truth team (side of the midcourt line
            # the feet fall on). Compared against the tracker's `team` in
            # analyze_tracking.py to score team accuracy with no manual GT.
            foot_team = None
            if court.is_calibrated:
                foot_team = court.get_team_for_bbox([int(v) for v in p["bbox"]])
            players_dump.append({
                "track_id": tid,
                "bbox": [float(v) for v in p["bbox"]],
                "center": [float(v) for v in p["center"]],
                "team": p.get("team"),
                "foot_team": foot_team,
                "confidence": float(p.get("confidence", 0.0)),
                "predicted": bool(p.get("predicted", False)),
            })
        frames_dump.append({"frame": frame_idx, "n_court_det": n_court_det, "players": players_dump})

        # --- Annotated video ---
        if writer:
            if court.is_calibrated:
                frame = court.draw_court_overlay(frame)
            for p in tracked:
                tid = p.get("track_id", -1)
                team = p.get("team")
                x1, y1, x2, y2 = [int(v) for v in p["bbox"]]
                color = PLAYER_COLORS.get(tid, TEAM_COLORS.get(team, (0, 255, 0)))
                thickness = 1 if p.get("predicted") else 2  # ghosts drawn thin
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
                label = f"P{tid}"
                if team:
                    label += f" T{team}"
                if p.get("predicted"):
                    label += " (ghost)"
                cv2.putText(frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            status = f"Frame {frame_idx} | Players: {len(tracked)} | IDs: {sorted(id_seen)}"
            cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            writer.write(frame)

        if frame_idx % 100 == 0:
            print(f"  frame {frame_idx}/{n_frames}  ids={sorted(id_seen)}")

    cap.release()
    if writer:
        writer.release()
        print(f"Annotated video: {output_dir / f'{video_name}_player_tracking.mp4'}")

    dump = {
        "video": video_name,
        "fps": float(fps),
        "width": w,
        "height": h,
        "max_players": args.max_players,
        "frames": frames_dump,
    }
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w") as f:
        json.dump(dump, f)
    print(f"Tracks JSON: {out_json}")

    print(f"\n{'='*50}\n  Player Tracking Dump Summary\n{'='*50}")
    print(f"  Frames processed:     {len(frames_dump)}")
    print(f"  Distinct IDs seen:    {sorted(id_seen)}")
    print(f"  Total distinct IDs:   {len(id_seen)}")
    print(f"  Max simultaneous:     {max_simultaneous}")
    print(f"  Expected (beach VB):  {args.max_players}")
    print(f"  Ghost/recycled IDs:   {max(0, len(id_seen) - args.max_players)}")


if __name__ == "__main__":
    main()
