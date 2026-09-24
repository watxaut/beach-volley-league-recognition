"""Evaluate the match point layer against the owner's dictated match GT.

Compares ``pipeline_output.json`` (game_state.points) and the per-frame
game-state CSV (GAME_ON episodes) against
``ground_truth/<stem>_match_points.json`` (produced by
``scripts/parse_match_gt_text.py``).

The dictated GT carries NO frame anchors -- only point ordinals, winners
(from the running score) and side-switch markers. The evaluation is
therefore honest about what can be scored today:

- point COUNT: GT points vs pipeline confirmed points vs raw GAME_ON
  episodes (the episode layer is the rally detector; the point layer
  confirms a subset);
- the implied ordinal of the first confirmed point (``episodes before the
  first confirmed point + 1`` under the episodes~=rallies assumption) --
  quantifies the owner's live-debug observation "P1 started around P10";
- a per-episode table (start, duration, confirmed?) that doubles as the
  alignment artifact for owner-ratified frame anchors later;
- winner/side-switch scoring becomes possible only once the pipeline
  emits winners/side-switches (planned layers) AND frame anchors are
  ratified -- explicitly reported as NOT SCORED.

Usage:
    python scripts/evaluate_match_points.py \
        --gt ground_truth/20260920_match_points.json \
        --pipeline output/match20260920/pipeline_output.json \
        --game-state-csv output/match20260920/results_game_state.csv \
        [--out report.json]
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# An episode whose start lies within a confirmed point's span (with this
# tolerance for the episode layer's backdated starts) counts as confirmed.
_CONFIRM_TOLERANCE_FRAMES = 30


# ----------------------------------------------------------------------
# loaders
# ----------------------------------------------------------------------

def load_match_gt(path: str) -> Dict[str, Any]:
    """Load and validate the match-points-v1 JSON."""
    gt = json.loads(Path(path).read_text(encoding="utf-8"))
    if gt.get("format") != "match-points-v1":
        raise ValueError(f"{path}: unexpected format {gt.get('format')!r}")
    pts = gt.get("points") or []
    if not pts:
        raise ValueError(f"{path}: no points")
    for i, p in enumerate(pts):
        if p.get("point") != i + 1:
            raise ValueError(f"{path}: point ordinals not 1..N at index {i}")
        if p.get("winner") not in ("A", "B"):
            raise ValueError(f"{path}: bad winner at point {p.get('point')}")
    fs = gt.get("final_score") or {}
    last = pts[-1]["score_after"]
    if fs != {"A": last["A"], "B": last["B"]}:
        raise ValueError(f"{path}: final_score {fs} != last row {last}")
    return gt


def load_pipeline_points(path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Return (video metadata, confirmed points) from pipeline_output.json."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    video = d.get("video") or {}
    pts = (d.get("game_state") or {}).get("points") or []
    return video, pts


def episodes_from_game_state_csv(path: str) -> List[Tuple[int, int]]:
    """Reconstruct GAME_ON episode spans (start, end) from the CSV.

    The CSV is per-frame; an episode starts at the first frame whose
    Game_State flips to ``game_on`` and ends at the last frame before it
    flips back.
    """
    episodes: List[Tuple[int, int]] = []
    start: Optional[int] = None
    last_frame = -1
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            state = (row.get("Game_State") or "").strip()
            frame = int(row["Frame_Index"])
            last_frame = frame
            if state == "game_on":
                if start is None:
                    start = frame
            elif start is not None:
                episodes.append((start, frame - 1))
                start = None
    if start is not None:
        episodes.append((start, last_frame))  # video ended while on
    return episodes


# ----------------------------------------------------------------------
# summary
# ----------------------------------------------------------------------

def summarize(
    gt: Dict[str, Any],
    confirmed_points: List[Dict[str, Any]],
    episodes: List[Tuple[int, int]],
    fps: float,
) -> Dict[str, Any]:
    """Build the evaluation report dict (pure -- no I/O)."""
    spans = [
        (p.get("start_frame"), p.get("end_frame"), p.get("n_actions", 0))
        for p in confirmed_points
    ]

    def _confirmed(start: int) -> bool:
        return any(
            s - _CONFIRM_TOLERANCE_FRAMES <= start <= e + _CONFIRM_TOLERANCE_FRAMES
            for s, e, _ in spans
        )

    episode_rows = [
        {
            "episode": i + 1,
            "start_frame": s,
            "end_frame": e,
            "duration_s": round((e - s + 1) / fps, 1),
            "start_s": round(s / fps, 1),
            "confirmed": _confirmed(s),
        }
        for i, (s, e) in enumerate(episodes)
    ]

    first_confirmed_start = spans[0][0] if spans else None
    episodes_before_first = (
        sum(1 for s, _ in episodes if s < first_confirmed_start)
        if first_confirmed_start is not None
        else len(episodes)
    )

    return {
        "gt": {
            "video": gt.get("video"),
            "n_points": len(gt["points"]),
            "final_score": gt["final_score"],
            "side_switch_after_point": gt.get("side_switch_after_point", []),
            "winners": "".join(p["winner"] for p in gt["points"]),
        },
        "pipeline": {
            "n_confirmed_points": len(spans),
            "n_episodes": len(episodes),
            "episodes_before_first_confirmed": episodes_before_first,
            "implied_first_confirmed_ordinal": (
                episodes_before_first + 1
                if first_confirmed_start is not None and episodes
                else None
            ),
            "confirmation_ratio": (
                round(len(spans) / len(gt["points"]), 3) if gt["points"] else None
            ),
            "confirmed_points": [
                {
                    "index": i + 1,
                    "start_frame": s,
                    "end_frame": e,
                    "duration_s": round((e - s + 1) / fps, 1),
                    "start_s": round(s / fps, 1),
                    "n_actions": n,
                }
                for i, (s, e, n) in enumerate(spans)
            ],
            "episodes": episode_rows,
        },
        "not_scored": {
            "winners": "requires the pipeline point-winner layer + ratified frame anchors",
            "side_switches": "requires the pipeline side-switch layer + ratified frame anchors",
            "segmentation_starts": "requires owner-ratified frame anchors per GT point",
        },
    }


def print_report(rep: Dict[str, Any]) -> None:
    gt = rep["gt"]
    pl = rep["pipeline"]
    print("=" * 72)
    print(f"GT video              : {gt['video']}")
    print(f"GT points             : {gt['n_points']}  (final {gt['final_score']['A']}-{gt['final_score']['B']})")
    print(f"GT side switches after: {gt['side_switch_after_point']}")
    print(f"GT winners            : {gt['winners']}")
    print("-" * 72)
    print(f"Pipeline episodes     : {pl['n_episodes']}  (GAME_ON spans)")
    print(f"Pipeline confirmed    : {pl['n_confirmed_points']} points "
          f"(confirmation ratio {pl['confirmation_ratio']})")
    print(f"Episodes before first confirmed point: "
          f"{pl['episodes_before_first_confirmed']} "
          f"-> first confirmed point ~= GT point "
          f"{pl['implied_first_confirmed_ordinal']} "
          "(episodes~=rallies assumption)")
    print("-" * 72)
    print("Confirmed points (index, start, start_s, dur_s, actions):")
    for p in pl["confirmed_points"]:
        print(f"  {p['index']:>3}  f{p['start_frame']:>6}  {p['start_s']:>7.1f}s  "
              f"{p['duration_s']:>5.1f}s  {p['n_actions']}")
    print("-" * 72)
    print("Episodes (idx, start_f, dur_s, confirmed?):")
    for e in pl["episodes"]:
        print(f"  {e['episode']:>3}  f{e['start_frame']:>6}  {e['duration_s']:>5.1f}s  "
              f"{'CONFIRMED' if e['confirmed'] else 'starved'}")
    print("-" * 72)
    print("Not scored (missing pipeline layers / GT frame anchors):")
    for k, v in rep["not_scored"].items():
        print(f"  {k}: {v}")
    print("=" * 72)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gt", required=True, help="match-points JSON (parse_match_gt_text.py)")
    ap.add_argument("--pipeline", required=True, help="pipeline_output.json")
    ap.add_argument("--game-state-csv", default=None, help="results_game_state.csv")
    ap.add_argument("--out", default=None, help="write the report JSON here")
    args = ap.parse_args(argv)

    gt = load_match_gt(args.gt)
    video, confirmed = load_pipeline_points(args.pipeline)
    fps = float(video.get("fps") or 30.0)
    episodes = (
        episodes_from_game_state_csv(args.game_state_csv)
        if args.game_state_csv
        else []
    )
    rep = summarize(gt, confirmed, episodes, fps)
    rep["inputs"] = {
        "gt": args.gt,
        "pipeline": args.pipeline,
        "game_state_csv": args.game_state_csv,
        "fps": fps,
    }
    print_report(rep)
    if args.out:
        Path(args.out).write_text(
            json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"report written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
