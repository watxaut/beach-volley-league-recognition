#!/usr/bin/env python3
"""
Test script for full action recognition pipeline.

Runs detection + tracking + pose + action classification,
draws action labels on players when detected.

Usage:
    python scripts/test_action_recognition.py resources/avp_front_1.mp4
    python scripts/test_action_recognition.py resources/avp_front_1.mp4 --court court_calibration.json --save-video
"""

import argparse
import sys
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.ball_detector import BallDetector
from src.detection.player_detector import PlayerDetector
from src.detection.court_calibration import CourtCalibration
from src.detection.calibration_readiness import resolve_script_calibration
from src.tracking.ball_tracker import BallTracker
from src.tracking.player_tracker import PlayerTracker
from src.recognition.pose_estimator import PoseEstimator
from src.recognition.action_classifier import ActionClassifier
from src.analysis.spike_analyzer import SpikeAnalyzer
from src.output_gen import overlay


def main():
    parser = argparse.ArgumentParser(description="Test action recognition")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--court", help="Path to court calibration JSON (auto-detected from calibrations/ if omitted)")
    parser.add_argument("--ball-model", help="Path to fine-tuned ball model (auto-detected from models/volleyball_ball_best.pt if omitted)")
    parser.add_argument("--output", default="output/action_test", help="Output directory")
    parser.add_argument("--max-frames", type=int, default=1000, help="Max frames to process")
    parser.add_argument("--save-video", action="store_true", help="Save annotated video")
    parser.add_argument("--no-team-aware", action="store_true",
                        help="Disable team-aware attribution (legacy closest-player)")
    parser.add_argument("--pose-complexity", type=int, default=0, choices=[0, 1, 2],
                        help="MediaPipe pose model complexity. Default 0 matches the "
                             "Config default (lite; entreno_1/3 GT A/B showed identical "
                             "action output at 0 and 1, 0 is ~1.6x faster).")
    parser.add_argument("--allow-uncalibrated", action="store_true",
                        help="Run without a usable court calibration (missing file, stem "
                             "mismatch or frame_dimensions that do not fit the video). "
                             "Court-derived features (team attribution, near-net, "
                             "serve-zone admission, spike zones) are DEGRADED -- the "
                             "action log is NOT comparable with calibrated runs.")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: cannot open {args.video}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Court calibration + readiness gate. Every action number validated against
    # ground_truth/ came from a CALIBRATED run, so an uncalibrated log must not
    # be produced silently (it used to run degraded and be compared anyway).
    # Calibration auto-detect keys on the SOURCE stem, so pointing this script at
    # the cached <stem>_up1080.mp4 still finds calibrations/<source_stem>.json.
    court_path = resolve_script_calibration(
        args.video, args.court, args.allow_uncalibrated,
        calibrations_dir=Path(__file__).resolve().parent.parent / "calibrations",
        script_name=Path(__file__).name,
    )
    court = CourtCalibration(court_path) if court_path else CourtCalibration()

    # Fine-tuned ball model (auto-detect from models/ if not given). Needed on
    # real footage; the COCO fallback rarely finds a volleyball.
    ball_model = args.ball_model
    if not ball_model:
        auto_model = Path(__file__).resolve().parent.parent / "models" / "volleyball_ball_best.pt"
        if auto_model.exists():
            ball_model = str(auto_model)
            print(f"Auto-loaded ball model: {ball_model}")

    ball_detector = BallDetector(model_path=ball_model, confidence_threshold=0.15)
    player_detector = PlayerDetector(confidence_threshold=0.5)
    ball_tracker = BallTracker(max_missing_frames=10, low_confidence_threshold=0.4, max_trajectory_gap=60.0)
    # Production tracker config (defaults = Config: max_players 4, serve-zone
    # admission on). The old explicit max_players=6 + strict-only feeding
    # disabled serve-zone admission, so the server was untracked in this
    # pipeline while dump_player_tracks/FrameProcessor tracked them fine.
    player_tracker = PlayerTracker(court_calibration=court)
    pose_estimator = PoseEstimator(min_detection_confidence=0.5, model_complexity=args.pose_complexity)
    action_classifier = ActionClassifier(
        pose_estimator=pose_estimator,
        confidence_threshold=0.3,
        court_calibration=court,
        team_aware=(not args.no_team_aware),
    )
    # Spike outcome/zone enrichment (pure observer, mirrors FrameProcessor).
    spike_analyzer = SpikeAnalyzer(court)

    if court.is_calibrated and court.court_bounds:
        ball_tracker.set_court_bounds(court.court_bounds)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_name = Path(args.video).stem
    writer = None
    if args.save_video:
        out_path = str(output_dir / f"{video_name}_action_recognition.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    action_counts = defaultdict(int)
    action_log = []

    def record_action(action):
        act_name = action["action"]
        tid = action.get("track_id", -1)
        conf = action.get("confidence", 0)
        # frame_number is the TRUE contact frame. The classifier confirms a
        # contact a few frames late and finalises it only once the NEXT contact
        # arrives (look-ahead), so an event is *emitted* well after its contact.
        # We anchor the on-screen label to frame_number in pass 2 so the label
        # appears on the contact frame, not where it happened to be emitted.
        contact_frame = action.get("frame_number")
        action_counts[act_name] += 1
        action_log.append({
            "frame": contact_frame,
            "player_id": action.get("player_id"),
            "track_id": tid,
            "action": act_name,
            "gesture": action.get("gesture"),
            "confidence": conf,
            "team": action.get("team"),
            "player_center": action.get("player_center"),
            "touch_number": action.get("touch_number"),
            "rally_id": action.get("rally_id"),
            "contact_kind": action.get("contact_kind"),
        })
        print(f"  Frame {contact_frame}: Player {tid} (idx {action.get('player_id')}) "
              f"[{action.get('gesture')}] -> {act_name} ({conf:.2f})")

    # ---- Pass 1: detect / track / classify. Cache lightweight per-frame overlay
    # data (ball + player boxes) so pass 2 can redraw without re-running YOLO. ----
    frame_cache = []
    for frame_idx in range(min(args.max_frames, total)):
        ret, frame = cap.read()
        if not ret:
            break

        ball_dets = ball_detector.detect(frame)
        player_dets = player_detector.detect(frame)
        # Same two-zone feeding as FrameProcessor: the detector output (already
        # play-area filtered) is the association set; the STRICT foot-in-court
        # subset gates NEW-track admission (incl. serve-zone logic, which needs
        # the wide set to ever see the server).
        if court.is_calibrated:
            strict_players = court.filter_detections_by_court(player_dets)
        else:
            strict_players = player_dets
        ball_position = None
        if ball_dets:
            top_ball = max(ball_dets, key=lambda d: d.get("confidence", 0))
            bc = top_ball.get("center")
            if bc and bc[0] is not None:
                ball_position = (float(bc[0]), float(bc[1]))
        tracked_players = player_tracker.update(
            player_dets, frame,
            strict_detections=strict_players,
            ball_active=bool(ball_dets),
            n_court_det=len(strict_players),
            ball_position=ball_position,
        )
        tracked_ball = ball_tracker.update(ball_dets)

        actions = action_classifier.classify_actions(
            frame, tracked_players, tracked_ball, frame_number=frame_idx
        )
        for action in actions:
            record_action(action)
        # Same emission filter as FrameProcessor before feeding the observer.
        spike_analyzer.observe(
            frame_idx, tracked_ball, tracked_players,
            [a for a in actions if a.get("action", "unknown") != "unknown"],
        )

        ball_draw = None
        if tracked_ball and tracked_ball.get("center") and tracked_ball["center"][0] is not None:
            ball_draw = (int(tracked_ball["center"][0]), int(tracked_ball["center"][1]),
                         bool(tracked_ball.get("is_predicted")))
        frame_cache.append({
            "ball": ball_draw,
            "players": [(p.get("track_id", -1), [int(v) for v in p["bbox"]]) for p in tracked_players],
        })

    # Finalise the last contact still held for its look-ahead (context layer).
    flushed = action_classifier.flush()
    for action in flushed:
        record_action(action)
    visible_flushed = [a for a in flushed if a.get("action", "unknown") != "unknown"]
    if visible_flushed:
        spike_analyzer.observe(None, None, None, visible_flushed)
    spike_analyzer.flush()

    cap.release()

    # ---- Attach the resolved spike enrichment to the log's spike entries ----
    rec_by_frame = {r["frame"]: r for r in spike_analyzer.spike_records()}
    for e in action_log:
        if e.get("action") == "spike" and e.get("frame") in rec_by_frame:
            r = rec_by_frame[e["frame"]]
            e["spike_type"] = r.get("spike_type")
            e["attack_zone"] = r.get("attack_zone")
            e["outcome"] = r.get("outcome")
            e["landing_zone"] = r.get("landing_zone")
            e["dug_zone"] = r.get("dug_zone")
            e["exit_speed_px"] = r.get("exit_speed_px")

    # ---- Build a per-track label plan anchored on each action's contact frame ----
    plan = overlay.LabelPlan()
    for e in action_log:
        name = e["action"]
        if name == "spike" and e.get("spike_type") in ("hard", "touch"):
            name = f"spike {e['spike_type']}"
        plan.add(e["track_id"], e["frame"], name, e["confidence"])

    # ---- Pass 2: redraw from cache, labels anchored on the true contact frame ----
    if writer:
        cap = cv2.VideoCapture(args.video)
        for frame_idx, cache in enumerate(frame_cache):
            ret, frame = cap.read()
            if not ret:
                break

            if court.is_calibrated:
                frame = court.draw_court_overlay(frame)

            if cache["ball"] is not None:
                bx, by, pred = cache["ball"]
                overlay.draw_ball(frame, bx, by, predicted=pred)

            # Spike flights: red fading trail + KILL marker (same overlay
            # helpers the live-debug processor uses).
            overlay.draw_ball_trail(frame, spike_analyzer.trail_points(frame_idx))
            kill = spike_analyzer.kill_annotation(frame_idx)
            if kill is not None:
                overlay.draw_kill_marker(frame, kill[0], kill[1], kill[2])

            for tid, (x1, y1, x2, y2) in cache["players"]:
                lab = plan.active(tid, frame_idx)
                overlay.draw_player(
                    frame, tid, (x1, y1, x2, y2),
                    action=lab[0] if lab is not None else None,
                    confidence=lab[1] if lab is not None else None,
                )

            writer.write(frame)

        cap.release()
        writer.release()
        print(f"\nAnnotated video saved to {output_dir / f'{video_name}_action_recognition.mp4'}")

    # Save action log
    import json
    log_path = output_dir / f"{video_name}_action_log.json"
    with open(log_path, "w") as f:
        json.dump(action_log, f, indent=2)
    print(f"Action log saved to {log_path}")

    print(f"\n{'='*50}")
    print(f"  Action Recognition Summary")
    print(f"{'='*50}")
    print(f"  Total actions detected: {sum(action_counts.values())}")
    for action, count in sorted(action_counts.items()):
        print(f"    {action:10s}: {count}")

    spikes = [r for r in spike_analyzer.spike_records()]
    if spikes:
        print(f"\n  Spike analysis ({len(spikes)}):")
        for r in spikes:
            az = r["attack_zone"]
            az_s = f"{az['side']}{az['zone']}" if az else "?"
            if r["outcome"] == "kill" and r["landing_zone"]:
                dest = f"kill -> {r['landing_zone']['side']}{r['landing_zone']['zone']}"
            elif r["outcome"] == "dug" and r["dug_zone"]:
                dest = f"dug at {r['dug_zone']['side']}{r['dug_zone']['zone']}"
            else:
                dest = r["outcome"]
            print(f"    f{r['frame']} p{r['player_id']} [{r['team']}] {r['spike_type']:6s} "
                  f"from {az_s:3s} {dest} (exit {r['exit_speed_px']} px/f)")


if __name__ == "__main__":
    main()
