#!/usr/bin/env python3
"""
Evaluation script for volleyball tracking pipeline.

Compares predictions against ground truth annotations and reports:
- Ball detection rate and accuracy
- Player ID consistency
- Action precision/recall per type

Usage:
    python scripts/evaluate.py --predictions output/results/ --ground-truth ground_truth/video_annotations.json
    python scripts/evaluate.py --predictions output/results.json --ground-truth ground_truth/video_annotations.json --component ball
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple

import numpy as np


def load_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def load_tracks_as_predictions(path: str) -> dict:
    """Convert a dump_player_tracks.py JSON into the predictions layout that
    evaluate_player_tracking expects:

        {"players": {"frames": { "<frame_int_as_str>": [{"id","bbox","team"}] }}}

    Includes coasting/ghost boxes (the tracker's claim that the player is there);
    a ghost that does not overlap GT simply won't IoU-match and won't count.
    """
    data = load_json(path)
    frames = {}
    for fr in data.get("frames", []):
        frames[str(fr["frame"])] = [
            {"id": p["track_id"], "bbox": p["bbox"], "team": p.get("team") or p.get("foot_team")}
            for p in fr.get("players", [])
        ]
    return {"players": {"frames": frames}}


# --- Ball Detection Evaluation ---

def evaluate_ball_detection(
    predictions: Dict[str, Any],
    ground_truth: Dict[str, Any],
    distance_threshold: float = 30.0,
) -> Dict[str, Any]:
    """Evaluate ball detection accuracy.

    Args:
        predictions: Dict mapping frame number (str) to {"x": ..., "y": ...} or None
        ground_truth: Ground truth ball annotations (frames dict)
        distance_threshold: Max pixel distance to count as correct detection

    Returns:
        Metrics dict with detection_rate, false_positive_rate, avg_distance
    """
    gt_frames = ground_truth.get("frames", {})
    if not gt_frames:
        return {"error": "No ground truth ball frames"}

    true_positives = 0
    false_positives = 0
    false_negatives = 0
    distances = []

    for frame_str, gt_ball in gt_frames.items():
        if gt_ball is None or not gt_ball.get("visible", True):
            # Ball not visible in ground truth
            pred = predictions.get(frame_str)
            if pred is not None:
                false_positives += 1
            continue

        gt_pos = np.array([gt_ball["x"], gt_ball["y"]])
        pred = predictions.get(frame_str)

        if pred is None:
            false_negatives += 1
            continue

        pred_pos = np.array([pred["x"], pred["y"]])
        dist = np.linalg.norm(gt_pos - pred_pos)
        distances.append(dist)

        if dist <= distance_threshold:
            true_positives += 1
        else:
            false_positives += 1
            false_negatives += 1  # missed the real position

    total_visible = true_positives + false_negatives
    detection_rate = true_positives / total_visible if total_visible > 0 else 0
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0

    return {
        "detection_rate": round(detection_rate, 3),
        "precision": round(precision, 3),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "total_gt_visible": total_visible,
        "avg_distance_px": round(float(np.mean(distances)), 1) if distances else None,
        "median_distance_px": round(float(np.median(distances)), 1) if distances else None,
    }


# --- Player Tracking Evaluation ---

def evaluate_player_tracking(
    predictions: Dict[str, Any],
    ground_truth: Dict[str, Any],
    iou_threshold: float = 0.3,
) -> Dict[str, Any]:
    """Evaluate player tracking: detection, ID consistency, team assignment.

    Args:
        predictions: Dict mapping frame number (str) to list of player dicts
        ground_truth: Ground truth player annotations (frames dict)
        iou_threshold: Min IoU to match prediction to ground truth

    Returns:
        Metrics dict
    """
    gt_frames = ground_truth.get("frames", {})
    if not gt_frames:
        return {"error": "No ground truth player frames"}

    total_gt_players = 0
    total_gt_occluded = 0
    total_detected = 0
    total_matched = 0
    id_mappings = []  # list of (gt_id, pred_id) per frame
    team_correct = 0
    team_total = 0

    for frame_str, gt_players in gt_frames.items():
        if gt_players is None:
            continue

        # Occluded GT players (visible: false, set by scripts/flag_occluded_gt.py)
        # are excluded everywhere -- no detector can be expected to find them.
        visible_gt = [p for p in gt_players if p.get("visible", True)]
        total_gt_occluded += len(gt_players) - len(visible_gt)
        gt_players = visible_gt

        pred_players = predictions.get(frame_str, [])
        total_gt_players += len(gt_players)
        total_detected += len(pred_players)

        # Match by IoU
        matches = _match_players_by_iou(gt_players, pred_players, iou_threshold)
        total_matched += len(matches)

        for gt_idx, pred_idx in matches:
            gt_p = gt_players[gt_idx]
            pred_p = pred_players[pred_idx]
            id_mappings.append((gt_p["id"], pred_p.get("id", -1)))

            # Team assignment check
            if "team" in gt_p and "team" in pred_p:
                team_total += 1
                if gt_p["team"] == pred_p["team"]:
                    team_correct += 1

    # ID consistency: for each GT ID, check how many different pred IDs it maps to
    id_consistency = _compute_id_consistency(id_mappings)

    detection_rate = total_matched / total_gt_players if total_gt_players > 0 else 0
    ghost_rate = max(0, total_detected - total_matched) / max(total_detected, 1)

    return {
        "detection_rate": round(detection_rate, 3),
        "ghost_player_rate": round(ghost_rate, 3),
        "total_gt_players": total_gt_players,
        "total_gt_occluded": total_gt_occluded,
        "total_detected": total_detected,
        "total_matched": total_matched,
        "id_consistency": id_consistency,
        "team_accuracy": round(team_correct / team_total, 3) if team_total > 0 else None,
    }


def _match_players_by_iou(
    gt_players: List[Dict], pred_players: List[Dict], iou_threshold: float
) -> List[Tuple[int, int]]:
    """Match ground truth players to predictions using IoU."""
    if not gt_players or not pred_players:
        return []

    iou_matrix = np.zeros((len(gt_players), len(pred_players)))

    for i, gt in enumerate(gt_players):
        for j, pred in enumerate(pred_players):
            gt_bbox = gt["bbox"]
            pred_bbox = pred.get("bbox", pred.get("box", [0, 0, 0, 0]))
            iou_matrix[i, j] = _compute_iou(gt_bbox, pred_bbox)

    matches = []
    used_gt = set()
    used_pred = set()

    # Greedy matching by highest IoU
    while True:
        if iou_matrix.size == 0:
            break
        max_idx = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
        max_iou = iou_matrix[max_idx]

        if max_iou < iou_threshold:
            break

        i, j = max_idx
        if i not in used_gt and j not in used_pred:
            matches.append((i, j))
            used_gt.add(i)
            used_pred.add(j)

        iou_matrix[i, :] = -1
        iou_matrix[:, j] = -1

    return matches


def _compute_iou(box_a: List[float], box_b: List[float]) -> float:
    """Compute IoU between two [x1, y1, x2, y2] boxes."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - intersection

    return intersection / union if union > 0 else 0


def _compute_id_consistency(id_mappings: List[Tuple[int, int]]) -> Dict[str, Any]:
    """Compute how consistently each GT ID maps to the same predicted ID."""
    gt_to_pred_ids = defaultdict(list)
    for gt_id, pred_id in id_mappings:
        gt_to_pred_ids[gt_id].append(pred_id)

    consistency_scores = {}
    for gt_id, pred_ids in gt_to_pred_ids.items():
        if not pred_ids:
            continue
        # Most common pred_id
        from collections import Counter
        counter = Counter(pred_ids)
        most_common_count = counter.most_common(1)[0][1]
        consistency = most_common_count / len(pred_ids)
        consistency_scores[str(gt_id)] = {
            "consistency": round(consistency, 3),
            "unique_pred_ids": len(counter),
            "total_frames": len(pred_ids),
            "most_common_pred_id": counter.most_common(1)[0][0],
        }

    avg_consistency = (
        np.mean([v["consistency"] for v in consistency_scores.values()])
        if consistency_scores
        else 0
    )

    return {
        "per_player": consistency_scores,
        "average_consistency": round(float(avg_consistency), 3),
    }


# --- Action Recognition Evaluation ---

def evaluate_actions(
    predictions: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]],
    frame_tolerance: int = 15,
    match_player: bool = True,
    gt_players: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Evaluate action recognition precision and recall.

    Args:
        predictions: List of {"frame": int, "player_id": int, "action": str}
        ground_truth: List of {"frame": int, "player_id": int, "action": str}
        frame_tolerance: Max frame difference to match prediction to ground truth

    Returns:
        Per-action and overall precision/recall
    """
    if not ground_truth:
        return {"error": "No ground truth actions"}

    # Ground truth uses the "final_action" schema key; predictions use "action".
    # Normalise both so either side can supply either key.
    def _act(evt):
        return evt.get("action", evt.get("final_action"))

    action_types = set()
    for evt in ground_truth + predictions:
        action_types.add(_act(evt))

    per_action = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for action in sorted(action_types):
        gt_events = [e for e in ground_truth if _act(e) == action]
        pred_events = [e for e in predictions if _act(e) == action]

        tp, fp, fn = _match_action_events(
            gt_events, pred_events, frame_tolerance, match_player, gt_players)
        total_tp += tp
        total_fp += fp
        total_fn += fn

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        per_action[action] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "total_gt": len(gt_events),
            "total_pred": len(pred_events),
        }

    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    overall_f1 = (
        2 * overall_precision * overall_recall / (overall_precision + overall_recall)
        if (overall_precision + overall_recall) > 0
        else 0
    )

    return {
        "overall": {
            "precision": round(overall_precision, 3),
            "recall": round(overall_recall, 3),
            "f1": round(overall_f1, 3),
        },
        "per_action": per_action,
        **_action_attribution_metrics(
            predictions, ground_truth, frame_tolerance, gt_players),
    }


def _action_attribution_metrics(
    predictions: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]],
    frame_tolerance: int,
    gt_players: Optional[Dict[str, List[Dict[str, Any]]]],
) -> Dict[str, Any]:
    """Team + player accuracy of ATTRIBUTION on nearest-frame matched pairs.

    Matching here ignores player_id and action type (nearest prediction within
    tolerance per GT event, greedy) so team/player are scored independently of
    label correctness. GT events are frame-sorted first (the entreno_3 file
    stores f332 last).

    - team: predicted ``team`` vs the GT toucher's ``player_team``.
    - player (spatial, only when ``gt_players`` given and the prediction has a
      ``player_center``): the GT box containing the predicted player centre at
      the nearest annotated frame, scored under BOTH id conventions --
      ``player_accuracy_spatial`` compares the box's canonical id (the
      entreno_4/5 convention), ``player_accuracy_spatial_lr`` its left-to-right
      index (the entreno_1/3 convention). Use whichever matches the file.
    """
    out: Dict[str, Any] = {}
    pairs = []
    used = set()
    for gt in sorted(ground_truth, key=lambda e: e["frame"]):
        best, bd = None, frame_tolerance + 1
        for i, pred in enumerate(predictions):
            if i in used:
                continue
            d = abs(pred.get("frame", -10**9) - gt["frame"])
            if d < bd:
                best, bd = i, d
        if best is not None:
            used.add(best)
            pairs.append((gt, predictions[best]))

    if pairs:
        n_team = sum(1 for gt, p in pairs if p.get("team") is not None)
        ok_team = sum(1 for gt, p in pairs
                      if p.get("team") is not None and p["team"] == gt.get("player_team"))
        out["team_accuracy"] = round(ok_team / n_team, 3) if n_team else None
        out["team_scored"] = n_team

    if gt_players and pairs:
        n_pl = ok_can = ok_lr = 0
        for gt, p in pairs:
            can, lr = _gt_box_ids_at(gt_players, gt["frame"], p.get("player_center"))
            if can is None:
                continue
            n_pl += 1
            ok_can += int(can == gt.get("player_id"))
            ok_lr += int(lr == gt.get("player_id"))
        out["player_accuracy_spatial"] = round(ok_can / n_pl, 3) if n_pl else None
        out["player_accuracy_spatial_lr"] = round(ok_lr / n_pl, 3) if n_pl else None
        out["player_scored_spatial"] = n_pl

    # Spike enrichment fields (spike_type / attack_zone / landing_zone /
    # dug_zone / outcome), scored on the same matched pairs wherever the GT
    # carries them. attack_zone/landing_zone/dug_zone are {"side", "zone"}
    # dicts on both sides.
    for out_key, gt_key in (
        ("spike_type_accuracy", "spike_type"),
        ("attack_zone_accuracy", "attack_zone"),
        ("landing_zone_accuracy", "landing_zone"),
        ("dug_zone_accuracy", "dug_zone"),
        ("outcome_accuracy", "outcome"),
    ):
        scored = ok = 0
        for gt, p in pairs:
            if gt.get(gt_key) is None:
                continue
            scored += 1
            ok += int(p.get(gt_key) == gt.get(gt_key))
        if scored:
            out[out_key] = round(ok / scored, 3)
            out[out_key.replace("_accuracy", "_scored")] = scored

    out["matched_pairs"] = len(pairs)
    return out


def _gt_box_ids_at(
    gt_players: Optional[Dict[str, List[Dict[str, Any]]]], frame: int, center
) -> Tuple[Optional[int], Optional[int]]:
    """(canonical_id, lr_index) of the visible GT box containing `center`.

    The two return values encode the two GT action player_id conventions in
    the wild: entreno_1/3 action ids follow the L-R index at the annotation
    frame, entreno_4/5 follow the canonical (annotator) id. Callers accept
    either so both conventions score fairly.
    """
    if not gt_players or not center:
        return None, None
    k = min(gt_players.keys(), key=lambda kk: abs(int(kk) - frame))
    visible = [p for p in gt_players[k] if p.get("visible", True)]
    hit = None
    for p in visible:
        x1, y1, x2, y2 = p["bbox"]
        if x1 <= center[0] <= x2 and y1 <= center[1] <= y2:
            hit = p
            break
    if hit is None:
        return None, None
    lr = sorted(visible, key=lambda p: p["bbox"][0]).index(hit) + 1
    return hit["id"], lr


def _match_action_events(
    gt_events: List[Dict], pred_events: List[Dict], frame_tolerance: int,
    match_player: bool = True,
    gt_players: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Tuple[int, int, int]:
    """Match predicted action events to ground truth within frame tolerance."""
    matched_gt = set()
    matched_pred = set()

    # Sort by frame
    gt_sorted = sorted(enumerate(gt_events), key=lambda x: x[1]["frame"])
    pred_sorted = sorted(enumerate(pred_events), key=lambda x: x[1]["frame"])

    for pi, pred in pred_sorted:
        best_dist = float("inf")
        best_gi = None

        for gi, gt in gt_sorted:
            if gi in matched_gt:
                continue
            frame_dist = abs(pred["frame"] - gt["frame"])
            # Optionally check player match (skipped when match_player=False).
            # With gt_players available this is spatial + convention-agnostic:
            # the pred's player_center must land in the GT box the event
            # names, under either id convention (canonical or L-R -- see
            # _gt_box_ids_at). Without gt_players, or for centerless preds,
            # fall back to raw player_id equality.
            if match_player and gt_players and pred.get("player_center"):
                can, lr = _gt_box_ids_at(gt_players, gt["frame"], pred["player_center"])
                player_match = can == gt.get("player_id") or lr == gt.get("player_id")
            else:
                player_match = (
                    not match_player
                    or pred.get("player_id") == gt.get("player_id")
                    or pred.get("player_id") is None
                )
            if frame_dist <= frame_tolerance and player_match and frame_dist < best_dist:
                best_dist = frame_dist
                best_gi = gi

        if best_gi is not None:
            matched_gt.add(best_gi)
            matched_pred.add(pi)

    tp = len(matched_pred)
    fp = len(pred_events) - tp
    fn = len(gt_events) - len(matched_gt)
    return tp, fp, fn


# --- Main ---

def run_evaluation(predictions_path: str, ground_truth_path: str, component: Optional[str] = None,
                   match_player: bool = True, tracks_json: Optional[str] = None):
    """Run evaluation and print results."""
    gt = load_json(ground_truth_path)
    gt_annotated = gt.get("annotated_frames", gt)

    if tracks_json:
        # dump_player_tracks.py output -> predictions layout for the players component
        predictions = load_tracks_as_predictions(tracks_json)
    else:
        # Try to load predictions
        pred_path = Path(predictions_path)
        if pred_path.is_file():
            predictions = load_json(str(pred_path))
        elif pred_path.is_dir():
            # Look for component-specific files
            predictions = {}
            for f in pred_path.glob("*.json"):
                predictions[f.stem] = load_json(str(f))
        else:
            print(f"Error: predictions path not found: {predictions_path}")
            sys.exit(1)

    components = [component] if component else ["ball", "players", "actions"]
    results = {}

    for comp in components:
        if comp == "ball" and "ball" in gt_annotated:
            pred_ball = predictions.get("ball", predictions.get("ball_detections", {}))
            if isinstance(pred_ball, dict) and "frames" in pred_ball:
                pred_ball = pred_ball["frames"]
            results["ball"] = evaluate_ball_detection(pred_ball, gt_annotated["ball"])
            _print_section("Ball Detection", results["ball"])

        elif comp == "players" and "players" in gt_annotated:
            pred_players = predictions.get("players", predictions.get("tracked_players", {}))
            if isinstance(pred_players, dict) and "frames" in pred_players:
                pred_players = pred_players["frames"]
            results["players"] = evaluate_player_tracking(pred_players, gt_annotated["players"])
            _print_section("Player Tracking", results["players"])

        elif comp == "actions" and "actions" in gt_annotated:
            # Predictions may be a bare list (action log) or a dict wrapper.
            if isinstance(predictions, list):
                pred_actions = predictions
            else:
                pred_actions = predictions.get("actions", predictions.get("action_events", []))
            if isinstance(pred_actions, dict) and "events" in pred_actions:
                pred_actions = pred_actions["events"]
            gt_actions = gt_annotated["actions"].get("events", gt_annotated["actions"])
            results["actions"] = evaluate_actions(
                pred_actions, gt_actions, match_player=match_player,
                gt_players=gt_annotated.get("players", {}).get("frames"))
            _print_section("Action Recognition", results["actions"])

    return results


def _print_section(title: str, metrics: Dict):
    """Pretty-print a metrics section."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    _print_dict(metrics, indent=2)


def _print_dict(d: Dict, indent: int = 0):
    """Recursively print a dict."""
    prefix = " " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            print(f"{prefix}{k}:")
            _print_dict(v, indent + 2)
        else:
            print(f"{prefix}{k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate volleyball tracking pipeline")
    parser.add_argument("--predictions", help="Path to predictions JSON or directory")
    parser.add_argument("--tracks-json", help="dump_player_tracks.py output (converted for player eval)")
    parser.add_argument("--ground-truth", required=True, help="Path to ground truth annotations JSON")
    parser.add_argument(
        "--component",
        choices=["ball", "players", "actions"],
        help="Evaluate only one component",
    )
    parser.add_argument("--output", help="Save results to JSON file")
    parser.add_argument(
        "--ignore-player", action="store_true",
        help="Match actions on type + frame only, ignoring player_id (GT player_id "
             "is a per-frame left-to-right index that may not match the predictor's).",
    )
    args = parser.parse_args()

    if not args.predictions and not args.tracks_json:
        print("Error: provide either --predictions or --tracks-json")
        sys.exit(1)

    results = run_evaluation(
        args.predictions, args.ground_truth, args.component,
        match_player=not args.ignore_player,
        tracks_json=args.tracks_json,
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
