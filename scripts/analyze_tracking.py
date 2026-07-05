#!/usr/bin/env python3
"""
Analyze a per-frame tracks JSON (from dump_player_tracks.py) for the failure
modes this project cares about:

  - Distinct IDs / ghost count        (roster leakage)
  - ID survival histogram             (how long each ID stays alive)
  - Resurrections                     (ID reappears after > max_disappeared -- the
                                       recycled-ID smoking gun for BUG B)
  - Swap-rate per ID                  (same ID center jumps > swap_px in 1 frame
                                       while NOT a predicted/ghost box)
  - Dropped-player frames             (len(players) < max_players, runs >= 3)
  - Missing-ID leaderboard            (which roster slots are dropped most)
  - Team flips per ID                 (A<->B within 5 frames -- Pass A mis-assign)
  - Dropped-server frames             (serve action with < max_players tracked --
                                       the BUG A signal; needs --actions-gt)

Usage:
    python scripts/analyze_tracking.py output/baseline/video_entreno_1_tracks.json
    python scripts/analyze_tracking.py tracks.json --actions-gt ground_truth/video_entreno_1_annotations.json
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np


def load_tracks(path):
    with open(path) as f:
        return json.load(f)


def load_serve_frames(gt_path):
    """Return sorted set of frames where a 'serve' action is annotated."""
    if not gt_path:
        return set()
    with open(gt_path) as f:
        gt = json.load(f)
    frames = set()
    # actions may be a list under annotated_frames.actions.events, or top-level
    ann = gt.get("annotated_frames", gt)
    actions = ann.get("actions", {})
    events = actions.get("events") if isinstance(actions, dict) else actions
    if not events:
        # Some files use a flat list of action events
        events = gt.get("actions", [])
    for ev in events or []:
        if str(ev.get("action") or ev.get("final_action") or "").lower() == "serve":
            frames.add(int(ev["frame"]))
    return frames


def runs_of_presence(frames_for_id):
    """Given sorted frame indices where an ID appears, return list of (start,end) runs
    where consecutive appearances differ by 1 frame (a single dropped frame does NOT
    split a run -- we tolerate a 1-frame flicker)."""
    if not frames_for_id:
        return []
    runs = []
    start = prev = frames_for_id[0]
    for fr in frames_for_id[1:]:
        if fr - prev <= 2:  # tolerate up to 1 missing frame between sightings
            prev = fr
        else:
            runs.append((start, prev))
            start = prev = fr
    runs.append((start, prev))
    return runs


def main():
    ap = argparse.ArgumentParser(description="Analyze per-frame tracks JSON")
    ap.add_argument("tracks_json")
    ap.add_argument("--actions-gt", help="ground_truth/<video>_annotations.json (for serve frames)")
    ap.add_argument("--max-players", type=int, default=None, help="roster CAP (else from JSON) -- for ghost/distinct-ID checks")
    ap.add_argument("--target-roster", type=int, default=4,
                    help="expected in-court players during live play (drop/coverage/recall scored against this)")
    ap.add_argument("--max-disappeared", type=int, default=30, help="gap (frames) that counts as a resurrection")
    ap.add_argument("--swap-px", type=float, default=250.0, help="center jump in 1 frame = a swap")
    ap.add_argument("--drop-min-run", type=int, default=3, help="consecutive under-roster frames = a drop run")
    ap.add_argument("--skip-init", type=int, default=60,
                    help="exclude the first N frames (tracker init phase uses unstable temp IDs)")
    ap.add_argument("--out-json", help="write summary JSON here")
    args = ap.parse_args()

    data = load_tracks(args.tracks_json)
    max_players = args.max_players or data.get("max_players", 4)
    all_frames = data.get("frames", [])
    # Core metrics exclude the init phase (temp IDs shuffle by detection order).
    frames = [fr for fr in all_frames if fr["frame"] >= args.skip_init]
    max_dis = args.max_disappeared

    # --- Per-ID presence ---
    presence = {}      # id -> sorted list of frame idx
    centers = {}       # id -> list of (frame, center, predicted)
    teams = {}         # id -> list of (frame, team)
    for fr in frames:
        fi = fr["frame"]
        for p in fr["players"]:
            tid = p["track_id"]
            presence.setdefault(tid, []).append(fi)
            centers.setdefault(tid, []).append((fi, p["center"], p.get("predicted", False)))
            teams.setdefault(tid, []).append((fi, p.get("team")))

    distinct_ids = sorted(presence)
    ghost_count = max(0, len(distinct_ids) - max_players)

    # --- Survival + resurrections ---
    survival = {}
    resurrections_total = 0
    for tid, frs in presence.items():
        frs = sorted(frs)
        runs = runs_of_presence(frs)
        res = 0
        for i in range(1, len(runs)):
            gap = runs[i][0] - runs[i - 1][1]
            if gap > max_dis:
                res += 1
        resurrections_total += res
        run_lens = [e - s + 1 for s, e in runs]
        survival[tid] = {
            "runs": len(runs),
            "resurrections": res,
            "max_run": max(run_lens) if run_lens else 0,
            "min_run": min(run_lens) if run_lens else 0,
            "first_frame": runs[0][0] if runs else None,
            "last_frame": runs[-1][1] if runs else None,
        }

    # --- Swap-rate (same ID, big center jump, NOT predicted) ---
    swaps = {tid: 0 for tid in distinct_ids}
    for tid, seq in centers.items():
        seq = sorted(seq)
        for i in range(1, len(seq)):
            f0, c0, pred0 = seq[i - 1]
            f1, c1, pred1 = seq[i]
            if f1 - f0 != 1:        # only same-ID consecutive frames
                continue
            if pred0 or pred1:      # ghost boxes can teleport; ignore
                continue
            d = float(np.linalg.norm(np.array(c1) - np.array(c0)))
            if d > args.swap_px:
                swaps[tid] += 1
    total_consec = sum(max(0, len(centers[t]) - 1) for t in distinct_ids)
    swap_rate_per100 = (sum(swaps.values()) / total_consec * 100) if total_consec else 0.0

    # --- Dropped-player frames ---
    under = [fr["frame"] for fr in frames if len(fr["players"]) < max_players]
    # runs of consecutive under-roster frames
    under_runs = []
    if under:
        s = prev = under[0]
        for fr in under[1:]:
            if fr - prev <= 2:
                prev = fr
            else:
                under_runs.append((s, prev))
                s = prev = fr
        under_runs.append((s, prev))
    long_drops = [r for r in under_runs if r[1] - r[0] + 1 >= args.drop_min_run]

    # Which roster slots are missing most often
    present_per_frame = [set(p["track_id"] for p in fr["players"]) for fr in frames]
    expected = set(range(1, max_players + 1))
    missing_counts = {tid: 0 for tid in expected}
    for pf in present_per_frame:
        for tid in expected - pf:
            missing_counts[tid] += 1

    # --- Team flips ---
    team_flips = {tid: 0 for tid in distinct_ids}
    for tid, seq in teams.items():
        seq = sorted(seq)
        for i in range(1, len(seq)):
            f0, t0 = seq[i - 1]
            f1, t1 = seq[i]
            if t0 and t1 and t0 != t1 and (f1 - f0) <= 5:
                team_flips[tid] += 1

    # --- Live-play segmentation: recall / coverage / drop / team-accuracy ---
    # Live play = <= target_roster people in court; dead ball = extras walked in
    # (n_court_det > target). Drop/coverage/team metrics are scored on live frames
    # only, against the target roster (4) -- NOT max_players (the 6-cap).
    target = args.target_roster

    def _real(fr):
        return [p for p in fr["players"] if not p.get("predicted", False)]

    live_frames, dead_frames = [], []
    for fr in frames:
        n_court = fr.get("n_court_det")
        if n_court is None:  # dump predates n_court_det -- fall back to real tracked count
            n_court = len(_real(fr))
        (dead_frames if n_court > target else live_frames).append(fr)

    live_stats = None
    if live_frames:
        n_live = len(live_frames)
        court_dets = [min(fr.get("n_court_det", len(_real(fr))), target) for fr in live_frames]
        real_counts = [len(_real(fr)) for fr in live_frames]
        drop_frames = [fr["frame"] for fr in live_frames if len(_real(fr)) < target]
        tt = tc = 0
        for fr in live_frames:
            for p in _real(fr):
                st, ft = p.get("team"), p.get("foot_team")
                if st is not None and ft is not None:
                    tt += 1
                    tc += int(st == ft)
        live_stats = {
            "target_roster": target,
            "live_frames": n_live,
            "dead_frames": len(dead_frames),
            "mean_court_detections": round(float(np.mean(court_dets)), 3),
            "detection_recall": round(float(np.mean(court_dets)) / target, 3),
            "mean_tracked_real": round(float(np.mean(real_counts)), 3),
            "tracked_coverage": round(float(np.mean(real_counts)) / target, 3),
            "drop_rate": round(len(drop_frames) / n_live, 3),
            "drop_frames": len(drop_frames),
            "team_accuracy": round(tc / tt, 3) if tt else None,
            "team_samples": tt,
        }

    # --- Dropped-server frames (BUG A signal) ---
    serve_frames = load_serve_frames(args.actions_gt) if args.actions_gt else set()
    serve_drop = None
    if serve_frames:
        by_frame = {fr["frame"]: fr for fr in frames}
        dropped = []
        for sf in sorted(serve_frames):
            fr = by_frame.get(sf)
            if fr is None:
                continue
            if len(fr["players"]) < max_players:
                dropped.append(sf)
        serve_drop = {"serve_frames": len(serve_frames), "dropped": len(dropped),
                      "drop_rate": len(dropped) / max(1, len(serve_frames)),
                      "example_dropped": dropped[:10]}

    summary = {
        "video": data.get("video"),
        "max_players": max_players,
        "frames_processed": len(frames),
        "init_frames_excluded": args.skip_init,
        "total_frames": len(all_frames),
        "distinct_ids": distinct_ids,
        "total_distinct_ids": len(distinct_ids),
        "max_simultaneous": max((len(fr["players"]) for fr in frames), default=0),
        "ghost_or_recycled_ids": ghost_count,
        "resurrections_total": resurrections_total,
        "swap_rate_per100_frames": round(swap_rate_per100, 3),
        "swaps_per_id": swaps,
        "survival": survival,
        "team_flips_per_id": team_flips,
        "dropped_player_frames": len(under),
        "dropped_player_fraction": round(len(under) / max(1, len(frames)), 3),
        "long_drop_runs": long_drops,
        "missing_id_frame_counts": missing_counts,
        "live_play": live_stats,
        "serve_drop": serve_drop,
    }

    if args.out_json:
        Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out_json, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"Summary JSON: {args.out_json}")

    print(f"\n{'='*60}\n  Tracking Analysis: {data.get('video')}\n{'='*60}")
    print(f"  Frames processed:      {len(frames)}  (first {args.skip_init} init frames excluded; {len(all_frames)} total)")
    print(f"  Distinct IDs:          {distinct_ids}  (expected 1..{max_players})")
    print(f"  Ghost/recycled IDs:    {ghost_count}")
    print(f"  Max simultaneous:      {summary['max_simultaneous']}")
    print(f"  Resurrections (BUG B): {resurrections_total}")
    print(f"  Swap-rate/100 frames:  {swap_rate_per100:.2f}   (swaps/ID: {swaps})")
    print(f"  Team flips/ID:         {team_flips}")
    print(f"  Dropped-player frames: {len(under)}/{len(frames)} ({summary['dropped_player_fraction']*100:.1f}%)")
    print(f"  Long drop runs (>= {args.drop_min_run}): {len(long_drops)} -> {long_drops[:6]}")
    print(f"  Missing-ID frame counts: {missing_counts}")
    if live_stats:
        ls = live_stats
        ta = f"{ls['team_accuracy']*100:.1f}% (n={ls['team_samples']})" if ls["team_accuracy"] is not None else "n/a"
        print(f"  --- Live play (<= {target} in court) ---")
        print(f"    Live/dead frames:    {ls['live_frames']} / {ls['dead_frames']}")
        print(f"    Detection recall:    {ls['detection_recall']*100:.1f}%  (mean {ls['mean_court_detections']:.2f}/{target} in court)")
        print(f"    Tracked coverage:    {ls['tracked_coverage']*100:.1f}%  (mean {ls['mean_tracked_real']:.2f}/{target} real tracks)")
        print(f"    Drop rate (<{target}):     {ls['drop_rate']*100:.1f}%  ({ls['drop_frames']} frames)")
        print(f"    Team accuracy:       {ta}")
    if serve_drop:
        print(f"  Serve frames: {serve_drop['serve_frames']}, dropped (BUG A): "
              f"{serve_drop['dropped']} ({serve_drop['drop_rate']*100:.1f}%)"
              f"  examples {serve_drop['example_dropped']}")
    print(f"  Survival:")
    for tid in sorted(survival):
        s = survival[tid]
        print(f"    ID {tid}: runs={s['runs']} resurrections={s['resurrections']} "
              f"max_run={s['max_run']} frames  [{s['first_frame']}..{s['last_frame']}]")


if __name__ == "__main__":
    main()
