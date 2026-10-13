"""Owner review of a reconstructed match, rally by rally.

Run with ``make review`` -> http://127.0.0.1:8001/review

A new match is checked by the owner before it is published (AGENTS.md §11):
who is who has no ground truth. This page replaces the contact sheets: each
rally plays from the run's rally copy (``rallies.mp4``, no video needed) with
the post-run labels drawn on the bodies and the play-by-play beside it.
``Enter`` says "all right"; anything else is a correction (labels swapped,
another winner, a touch that is another action / another player / no touch, a
touch or a point the run missed, a note).

What the owner says is written to ``ground_truth/<match_key>_review.json``
(``match-review-v1``, format in ``ground_truth/README.md``). Every verdict
carries the point's frames and what the run read when it was given, so it
re-attaches after a rules change and says when the run moved under it; its
``truth`` is the point as the owner left it, independent of any later run.

Nothing here feeds the pipeline or the post-run layer. The publisher applies
the file (src/publish/reviewed.py): what is published is the match as the
owner reviewed it.
"""

from __future__ import annotations

import argparse
import functools
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from ..publish.clips import RALLY_PAD_S, RallyCopy, load_rally_copy
from ..publish.gaps import GAPS_NAME, GapCopy, load_gap_copy

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
REPO_ROOT = BASE_DIR.parent.parent
REVIEW_FORMAT = "match-review-v1"
RECON_NAME = "match_reconstruction.json"
DIAG_NAME = "diag.jsonl"

#: What a touch can be corrected to. A block is not a post-run label yet
#: (STATUS open point 32d): the owner can still say so.
ACTIONS = ("serve", "dig", "set", "spike", "overpass", "block")
PLAYERS = ("P1A", "P2A", "P1B", "P2B")
TEAMS = ("A", "B")
STATUS_OK, STATUS_CORRECTED = "ok", "corrected"
LABEL_FIXES = ("near_swapped", "far_swapped", "sides_swapped", "other")
#: A saved verdict belongs to the point that covers at least this share of it.
ATTACH_MIN_OVERLAP = 0.5
NOTE_MAX = 2000
#: A stretch of dead time is worth a look ("flagged") when the ball was played
#: in it this many times, or when it lasted this many times the usual pause
#: between two points. A hint for the owner's eyes, never a decision.
GAP_FLAG_CONTACTS = 3
GAP_FLAG_PAUSE_RATIO = 1.6

THUMB_NAME = re.compile(r"^P[12][AB]\.jpg$")
#: A body the identity read gave no name: the post-run layer calls it by its
#: track id (``T4``). The owner can say who it is, per rally.
UNNAMED = re.compile(r"^T\d+$")


# --------------------------------------------------------------------------- #
# runs on disk
# --------------------------------------------------------------------------- #

def find_runs(output_root: Path) -> List[Dict[str, Any]]:
    """Every run directory with a reconstruction, newest name first, and
    whether it has what a review needs (rally copy + diag dump)."""
    runs = []
    root = Path(output_root)
    if not root.is_dir():
        return runs
    for path in sorted(root.iterdir(), reverse=True):
        if not (path / RECON_NAME).is_file():
            continue
        copy = (path / "rallies.mp4").is_file() and (path / "rallies.json").is_file()
        diag = (path / DIAG_NAME).is_file()
        runs.append({"key": path.name, "path": path, "has_copy": copy, "has_diag": diag,
                     "reviewable": copy and diag})
    return runs


def review_path(gt_root: Path, key: str) -> Path:
    return Path(gt_root) / f"{key}_review.json"


def empty_review(key: str) -> Dict[str, Any]:
    return {"format": REVIEW_FORMAT, "match_key": key, "owner_final_score": None,
            "points": [], "missing_points": [], "gaps": []}


def load_review(path: Path, key: str) -> Dict[str, Any]:
    if not Path(path).is_file():
        return empty_review(key)
    review = json.loads(Path(path).read_text())
    if review.get("format") != REVIEW_FORMAT:
        raise ValueError(f"{path}: not a {REVIEW_FORMAT} file")
    for name, default in empty_review(key).items():
        review.setdefault(name, default)
    return review


def save_review(path: Path, review: Dict[str, Any]) -> None:
    """Write through a temporary file: a crash never leaves half a review."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    review["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(review, f, indent=1)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# --------------------------------------------------------------------------- #
# the match as the page shows it (pure)
# --------------------------------------------------------------------------- #

def _touch_view(t: Dict[str, Any]) -> Dict[str, Any]:
    return {"frame": int(t["frame"]), "action": t.get("action"), "player": t.get("player"),
            "team": t.get("team"), "side": t.get("side"), "outcome": t.get("outcome"),
            "observed": bool(t.get("observed")), "spike_type": t.get("spike_type")}


def copy_segment(copy: RallyCopy, start_frame: int, end_frame: int
                 ) -> Optional[Tuple[int, int, int]]:
    """The stretch of the copy that shows a point: its first SOURCE frame,
    last source frame and the first one's position in the copy. Rallies that
    run into each other share one stretch of the copy, so each keeps only its
    own padding."""
    before, after = (int(round(s * copy.fps)) for s in RALLY_PAD_S)
    for first, last in copy.spans:
        if first <= start_frame <= last:
            lo, hi = max(first, start_frame - before), min(last, end_frame + after)
            pos = copy.position(lo)
            return None if pos is None else (lo, hi, pos)
    return None


def match_view(recon: Dict[str, Any], copy: Optional[RallyCopy]) -> Dict[str, Any]:
    """What the page needs of a reconstruction: one row per point."""
    points = []
    before = {"A": 0, "B": 0}
    for p in recon.get("points", []):
        seg = copy_segment(copy, int(p["start_frame"]), int(p["end_frame"])) if copy else None
        serve = p.get("serve") or {}
        after = p.get("score_after") or before
        points.append({
            "point": int(p["point"]),
            "start_frame": int(p["start_frame"]), "end_frame": int(p["end_frame"]),
            "start_time_s": p.get("start_time_s"),
            "near_team": p.get("near_team"),
            "serve_team": serve.get("team"), "serve_player": serve.get("player"),
            "winner": p.get("winner"), "winner_source": p.get("winner_source"),
            "end_kind": (p.get("end") or {}).get("kind"),
            "score_before": dict(before), "score_after": dict(after),
            "flags": list(p.get("flags") or []),
            "touches": [_touch_view(t) for t in p.get("touches") or []],
            "segment": None if seg is None else
            {"first": seg[0], "last": seg[1], "copy_first": seg[2]},
        })
        before = after
    checks = recon.get("checks") or {}
    return {
        "fps": copy.fps if copy else recon.get("fps"),
        "crop": list(copy.crop) if copy else None,
        "size": list(copy.size) if copy else None,
        "points": points,
        "run": {"final_score": checks.get("final_score"),
                "switch_after": checks.get("side_switch_after_point"),
                "blocks": checks.get("points_between_switches"),
                "undecided": checks.get("undecided_points")},
        "actions": list(ACTIONS), "players": list(PLAYERS),
    }


def gaps_view(points: Sequence[Dict[str, Any]], n_frames: Optional[int], fps: float,
              copy: Optional[GapCopy] = None,
              contacts: Optional[Sequence[int]] = None) -> List[Dict[str, Any]]:
    """The dead time around the points: before the first, between each two,
    after the last. A point the run missed is in one of them.

    ``contacts``: frames where the causal stream saw the ball played. A gap
    is ``flagged`` when the ball was played in it ``GAP_FLAG_CONTACTS`` times
    or it lasted ``GAP_FLAG_PAUSE_RATIO`` times the usual pause between two
    points -- where a missed rally is likeliest, not a claim that there is
    one. ``segment`` is its part of the dead-time copy (None: no picture).
    """
    def edge(p, key, frame_key):
        return (p.get("segment") or {}).get(key, p[frame_key])

    gaps = []
    bounds = [None, *points, None]
    for before, after in zip(bounds, bounds[1:]):
        first = 0 if before is None else edge(before, "last", "end_frame") + 1
        if after is None:
            if n_frames is None:
                continue
            last = int(n_frames) - 1
        else:
            last = edge(after, "first", "start_frame") - 1
        if last < first:
            continue
        seg = copy.segment(first, last) if copy else None
        played = None if contacts is None else sum(first <= f <= last for f in contacts)
        gaps.append({
            "after_point": 0 if before is None else before["point"],
            "before_point": None if after is None else after["point"],
            "first": first, "last": last,
            "seconds": round((last - first + 1) / fps, 1) if fps else None,
            "contacts": played, "flagged": False, "why": [],
            "segment": None if seg is None else
            {"first": seg[0], "copy_first": seg[1], "n": seg[2], "step": copy.step},
        })
    between = sorted(g["seconds"] for g in gaps
                     if g["after_point"] and g["before_point"] and g["seconds"])
    usual = between[len(between) // 2] if between else None
    for g in gaps:
        if g["contacts"] is not None and g["contacts"] >= GAP_FLAG_CONTACTS:
            g["why"].append(f"the ball was played {g['contacts']} times")
        if (usual and g["after_point"] and g["before_point"]
                and g["seconds"] >= GAP_FLAG_PAUSE_RATIO * usual):
            g["why"].append(f"{g['seconds']:.0f} s, the usual pause is {usual:.0f} s")
        g["flagged"] = bool(g["why"])
    return gaps


def gap_states(review: Dict[str, Any], gaps: Sequence[Dict[str, Any]]) -> Dict[int, str]:
    """``after_point`` -> ``checked`` for every gap the owner watched (what he
    found there, if anything, is in ``missing_points``): a stored stretch
    covers at least ``ATTACH_MIN_OVERLAP`` of it (the stretches move a little
    when a rules change moves a rally)."""
    out = {}
    for g in gaps:
        length = g["last"] - g["first"] + 1
        for seen in review.get("gaps") or []:
            share = (min(seen["last"], g["last"]) - max(seen["first"], g["first"]) + 1) / length
            if seen.get("status") == "checked" and share >= ATTACH_MIN_OVERLAP:
                out[g["after_point"]] = "checked"
    return out


def put_gap(review: Dict[str, Any], gap: Dict[str, Any], checked: bool) -> None:
    """Store (or forget) that the owner watched a gap."""
    length = gap["last"] - gap["first"] + 1
    kept = [seen for seen in review.get("gaps") or []
            if (min(seen["last"], gap["last"]) - max(seen["first"], gap["first"]) + 1) / length
            < ATTACH_MIN_OVERLAP]
    if checked:
        kept.append({"first": gap["first"], "last": gap["last"], "status": "checked"})
    review["gaps"] = sorted(kept, key=lambda g: g["first"])


# --------------------------------------------------------------------------- #
# verdicts (pure)
# --------------------------------------------------------------------------- #

def run_snapshot(point: Dict[str, Any]) -> Dict[str, Any]:
    """What the run read for a point when the owner looked at it."""
    return {"point": point["point"], "winner": point["winner"],
            "serve_team": point["serve_team"], "near_team": point["near_team"],
            "touches": [[t["frame"], t["action"], t["player"]] for t in point["touches"]]}


def label_map(near_team: Optional[str], labels: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Run label -> the player the owner says it is.

    ``sides_swapped``: the run has the squads on the wrong halves (every label
    names the other squad). ``near_swapped`` / ``far_swapped``: the two
    teammates on that half carry each other's label -- the half as it REALLY
    is, after the squads are put right. ``other`` is a flag only (the note
    says what): it maps nothing.
    """
    labels = labels or {}
    true_near = near_team
    if labels.get("sides_swapped") and near_team in TEAMS:
        true_near = "B" if near_team == "A" else "A"
    out = {}
    for label in PLAYERS:
        number, squad = label[1], label[2]
        if labels.get("sides_swapped"):
            squad = "B" if squad == "A" else "A"
        on_near = true_near is not None and squad == true_near
        on_far = true_near is not None and squad != true_near
        if (on_near and labels.get("near_swapped")) or (on_far and labels.get("far_swapped")):
            number = "2" if number == "1" else "1"
        out[label] = f"P{number}{squad}"
    return out


def clean_verdict(raw: Dict[str, Any], point: Dict[str, Any]) -> Dict[str, Any]:
    """A verdict as the page sent it, checked against the point it is about.
    Raises ValueError on anything that is not a verdict."""
    status = raw.get("status")
    if status not in (STATUS_OK, STATUS_CORRECTED):
        raise ValueError("status must be ok or corrected")
    labels = {k: True for k in LABEL_FIXES if (raw.get("labels") or {}).get(k)}
    names = {}
    for unnamed, player in sorted((raw.get("names") or {}).items()):
        if not UNNAMED.match(unnamed) or player not in PLAYERS:
            raise ValueError(f"cannot name {unnamed!r} {player!r}")
        names[unnamed] = player
    winner = raw.get("winner")
    if winner not in (None, "A", "B", "none"):
        raise ValueError("winner must be A, B, none or absent")
    known = {t["frame"] for t in point["touches"]}
    lo, hi = _frame_range(point)
    touches: Dict[str, Dict[str, Any]] = {}
    for frame, fix in sorted((raw.get("touches") or {}).items(), key=lambda kv: int(kv[0])):
        if int(frame) not in known:
            raise ValueError(f"no touch at frame {frame} in point {point['point']}")
        fix = _clean_touch(fix)
        if fix:
            touches[str(int(frame))] = fix
    added = []
    for t in raw.get("added") or []:
        frame = int(t["frame"])
        if not lo <= frame <= hi:
            raise ValueError(f"added touch at frame {frame} is outside point {point['point']}")
        fix = _clean_touch(t, removable=False)
        if "action" not in fix:
            raise ValueError("an added touch needs an action")
        added.append({"frame": frame, "action": fix["action"], "player": fix.get("player")})
    verdict: Dict[str, Any] = {
        "start_frame": point["start_frame"], "end_frame": point["end_frame"],
        "status": status, "labels": labels, "names": names, "winner": winner,
        "not_a_point": bool(raw.get("not_a_point")),
        "touches": touches, "added": sorted(added, key=lambda t: t["frame"]),
        "note": str(raw.get("note") or "").strip()[:NOTE_MAX],
    }
    if status == STATUS_OK and has_corrections(verdict):
        verdict["status"] = STATUS_CORRECTED
    verdict["run"] = run_snapshot(point)
    verdict["truth"] = truth_of(point, verdict)
    return verdict


def _frame_range(point: Dict[str, Any]) -> Tuple[int, int]:
    seg = point.get("segment")
    return (seg["first"], seg["last"]) if seg else (point["start_frame"], point["end_frame"])


def _clean_touch(fix: Dict[str, Any], removable: bool = True) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if removable and fix.get("remove"):
        return {"remove": True}
    if fix.get("action") is not None:
        if fix["action"] not in ACTIONS:
            raise ValueError(f"unknown action {fix['action']!r}")
        out["action"] = fix["action"]
    if "player" in fix:
        if fix["player"] not in PLAYERS + (None,):
            raise ValueError(f"unknown player {fix['player']!r}")
        out["player"] = fix["player"]
    return out


def has_corrections(verdict: Dict[str, Any]) -> bool:
    return bool(verdict.get("labels") or verdict.get("names") or verdict.get("winner")
                or verdict.get("not_a_point")
                or verdict.get("touches") or verdict.get("added") or verdict.get("note"))


def truth_of(point: Dict[str, Any], verdict: Dict[str, Any]) -> Dict[str, Any]:
    """The point as the owner left it: the run's read with every correction
    applied. A touch's player follows the label correction (and the name the
    owner gave an unnamed body) unless the owner named the player on that
    touch."""
    if verdict.get("not_a_point"):
        return {"is_point": False}
    labels = verdict.get("labels") or {}
    names = {**label_map(point["near_team"], labels), **(verdict.get("names") or {})}
    touches = []
    for t in point["touches"]:
        fix = (verdict.get("touches") or {}).get(str(t["frame"])) or {}
        if fix.get("remove"):
            continue
        player = fix["player"] if "player" in fix else names.get(t["player"], t["player"])
        touches.append({"frame": t["frame"], "action": fix.get("action", t["action"]),
                        "player": player})
    touches += [dict(t) for t in verdict.get("added") or []]
    touches.sort(key=lambda t: t["frame"])
    near = point["near_team"]
    if labels.get("sides_swapped") and near in TEAMS:
        near = "B" if near == "A" else "A"
    winner = verdict.get("winner")
    winner = point["winner"] if winner is None else (None if winner == "none" else winner)
    serve = next((t for t in touches if t["action"] == "serve"), None)
    serve_team = serve["player"][2] if serve and serve.get("player") else point["serve_team"]
    return {"is_point": True, "winner": winner, "near_team": near, "serve_team": serve_team,
            "labels_unclear": bool(labels.get("other")), "touches": touches}


def put_verdict(review: Dict[str, Any], verdict: Optional[Dict[str, Any]],
                start_frame: int) -> None:
    """Store a point's verdict (None: the point is unreviewed again)."""
    kept = [v for v in review["points"] if v["start_frame"] != start_frame]
    if verdict is not None:
        kept.append(verdict)
    review["points"] = sorted(kept, key=lambda v: v["start_frame"])


def attach(review: Dict[str, Any], points: Sequence[Dict[str, Any]]
           ) -> Tuple[Dict[int, Dict[str, Any]], List[Dict[str, Any]]]:
    """Saved verdicts by the point number they belong to NOW, and the ones
    that fit no point any more (a rules change moved the rallies).

    A verdict fits the point that covers the largest part of its frames, at
    least ``ATTACH_MIN_OVERLAP`` of them; a point takes one verdict. Each
    attached verdict says whether the run still reads what the owner saw
    (``run_changed``).
    """
    scored = []
    for vi, v in enumerate(review.get("points") or []):
        length = max(1, v["end_frame"] - v["start_frame"] + 1)
        for p in points:
            share = (min(v["end_frame"], p["end_frame"])
                     - max(v["start_frame"], p["start_frame"]) + 1) / length
            if share >= ATTACH_MIN_OVERLAP:
                scored.append((-share, vi, p["point"]))
    by_point: Dict[int, Dict[str, Any]] = {}
    used = set()
    numbers = {p["point"]: p for p in points}
    for _, vi, number in sorted(scored):
        if vi in used or number in by_point:
            continue
        used.add(vi)
        v = dict(review["points"][vi])
        now, then = run_snapshot(numbers[number]), dict(v.get("run") or {})
        now.pop("point"), then.pop("point", None)
        v["run_changed"] = now != then
        by_point[number] = v
    orphans = [v for vi, v in enumerate(review.get("points") or []) if vi not in used]
    return by_point, orphans


def reviewed_score(points: Sequence[Dict[str, Any]], by_point: Dict[int, Dict[str, Any]],
                   missing: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The score with the owner's corrections: other winners, rallies that
    were no point, points the run missed. A point without a winner counts as
    undecided, on neither side."""
    score = {"A": 0, "B": 0}
    undecided = 0
    for p in points:
        truth = (by_point.get(p["point"]) or {}).get("truth")
        if truth is not None and not truth.get("is_point"):
            continue
        winner = truth["winner"] if truth is not None else p["winner"]
        if winner in score:
            score[winner] += 1
        else:
            undecided += 1
    for m in missing:
        if m.get("winner") in score:
            score[m["winner"]] += 1
        else:
            undecided += 1
    return {"A": score["A"], "B": score["B"], "undecided": undecided}


def clean_match_fields(raw: Dict[str, Any], points: Sequence[Dict[str, Any]]
                       ) -> Dict[str, Any]:
    """The match-level part of a review: the owner's final score and the
    points the run missed (each after a point of the run, 0 = before the
    first; ``at_frame`` when the owner marked it while watching the dead
    time)."""
    final = raw.get("owner_final_score")
    if final is not None:
        final = {t: int(final[t]) for t in TEAMS}
        if min(final.values()) < 0 or max(final.values()) > 99:
            raise ValueError("final score out of range")
    starts = {p["point"]: p["start_frame"] for p in points}
    missing = []
    for m in raw.get("missing_points") or []:
        after = int(m.get("after_point") or 0)
        if after and after not in starts:
            raise ValueError(f"no point {after}")
        if m.get("winner") not in (None, "A", "B"):
            raise ValueError("a missing point's winner is A, B or unknown")
        row = {"after_point": after, "after_frame": starts.get(after, 0),
               "winner": m.get("winner"),
               "note": str(m.get("note") or "").strip()[:NOTE_MAX]}
        if m.get("at_frame") is not None:      # where in the dead time the owner saw it
            row["at_frame"] = int(m["at_frame"])
        missing.append(row)
    return {"owner_final_score": final,
            "missing_points": sorted(missing, key=lambda m: m["after_frame"])}


# --------------------------------------------------------------------------- #
# who is where on every frame (the post-run labels, read again from the dump)
# --------------------------------------------------------------------------- #

def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() or p.exists() else REPO_ROOT / p


@functools.lru_cache(maxsize=2)
def _labelled_stream(diag: str, diag_mtime: float, recon_path: str, recon_mtime: float):
    """The run's stream with the labels the reconstruction credited its
    touches with: the same identity read over the same rallies (one read per
    run, kept while the files do not change)."""
    from ..postrun.geometry import CourtGeometry
    from ..postrun.identity import relabel
    from ..postrun.stream import load_stream

    recon = json.loads(Path(recon_path).read_text())
    stream = load_stream(diag, fps=recon.get("fps"))
    identity = recon.get("identity") or {}
    calibration = (recon.get("inputs") or {}).get("calibration")
    if identity.get("applied") and calibration and _resolve(calibration).exists():
        spans = [(int(r["start_frame"]), int(r["end_frame"])) for r in identity["rallies"]]
        relabel(stream, CourtGeometry.from_file(str(_resolve(calibration))), spans)
    return stream


def labelled_stream(run_dir: Path):
    diag, recon = Path(run_dir) / DIAG_NAME, Path(run_dir) / RECON_NAME
    return _labelled_stream(str(diag), diag.stat().st_mtime, str(recon), recon.stat().st_mtime)


def ball_contacts(run_dir: Path) -> Optional[List[int]]:
    """Frames where the causal stream saw the ball played (None: the dump
    cannot be read -- the gaps are then flagged by their length alone)."""
    try:
        return sorted(c.frame for c in labelled_stream(run_dir).candidates if c.accepted)
    except Exception as exc:                    # a hint only: never fail the page
        logger.warning("no ball contacts for %s: %s", Path(run_dir).name, exc)
        return None


def tracks(stream, first: int, last: int) -> Dict[str, Any]:
    """Bodies (label, box, track id) and the ball on every frame of a stretch,
    in the frame's own pixels. A body without a label is one the identity
    read withheld: the page calls it ``T<track id>``, as the touches do."""
    first, last = max(0, first), min(stream.n_frames - 1, last)
    bodies, ball = [], []
    for f in range(first, last + 1):
        bodies.append([[p.label, *(int(round(v)) for v in p.bbox), int(p.track_id)]
                       for p in stream.players[f]])
        x, y = stream.ball_xy[f]
        ball.append(None if x != x or y != y else [int(round(x)), int(round(y))])
    return {"first": first, "bodies": bodies, "ball": ball}


# --------------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------------- #

def create_router(output_root: Path = Path("output"),
                  gt_root: Path = Path("ground_truth")) -> APIRouter:
    router = APIRouter(prefix="/review")
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    static = BASE_DIR / "static"
    templates.env.globals["style_ver"] = str(int((static / "style.css").stat().st_mtime))
    templates.env.globals["review_ver"] = str(int(max(
        (static / n).stat().st_mtime for n in ("review.js", "review.css"))))

    def run_of(key: str, reviewable: bool = True) -> Dict[str, Any]:
        run = next((r for r in find_runs(output_root) if r["key"] == key), None)
        if run is None or (reviewable and not run["reviewable"]):
            raise HTTPException(status_code=404, detail="no such run")
        return run

    def view_of(run: Dict[str, Any], gaps: bool = False) -> Dict[str, Any]:
        recon = json.loads((run["path"] / RECON_NAME).read_text())
        view = match_view(recon, load_rally_copy(run["path"]))
        if gaps:
            view["gaps"] = gaps_view(view["points"], recon.get("n_frames"), view["fps"],
                                     load_gap_copy(run["path"]), ball_contacts(run["path"]))
        return view

    def state_of(run: Dict[str, Any], view: Dict[str, Any]) -> Dict[str, Any]:
        review = load_review(review_path(gt_root, run["key"]), run["key"])
        by_point, orphans = attach(review, view["points"])
        return {"verdicts": by_point, "orphans": orphans,
                "gaps": gap_states(review, view.get("gaps") or []),
                "missing_points": review["missing_points"],
                "owner_final_score": review["owner_final_score"],
                "reviewed_score": reviewed_score(view["points"], by_point,
                                                 review["missing_points"])}

    @router.get("", response_class=HTMLResponse)
    def index(request: Request):
        rows = []
        for run in find_runs(output_root):
            row = {"key": run["key"], "reviewable": run["reviewable"],
                   "has_copy": run["has_copy"], "has_diag": run["has_diag"]}
            try:
                view = view_of(run)
                state = state_of(run, view)
                row.update(points=len(view["points"]), reviewed=len(state["verdicts"]),
                           corrected=sum(v["status"] == STATUS_CORRECTED
                                         for v in state["verdicts"].values()),
                           run_score=view["run"]["final_score"],
                           owner_score=state["owner_final_score"])
            except (OSError, ValueError, KeyError) as exc:
                row["error"] = str(exc)
            rows.append(row)
        return templates.TemplateResponse(request, "review_index.html", {"runs": rows})

    @router.get("/{key}", response_class=HTMLResponse)
    def page(request: Request, key: str):
        run = run_of(key)
        thumbs = [p for p in PLAYERS if (run["path"] / "thumbs" / f"{p}.jpg").is_file()]
        return templates.TemplateResponse(request, "review.html",
                                          {"key": run["key"], "thumbs": thumbs})

    @router.get("/{key}/data")
    def data(key: str):
        run = run_of(key)
        view = view_of(run, gaps=True)
        return {"key": run["key"], "match": view, "review": state_of(run, view)}

    @router.get("/{key}/tracks")
    def tracks_of(key: str, first: int, last: int):
        run = run_of(key)
        if last < first or last - first > 5000:
            raise HTTPException(status_code=400, detail="bad frame range")
        return tracks(labelled_stream(run["path"]), first, last)

    @router.get("/{key}/video")
    def video(key: str):
        return FileResponse(run_of(key)["path"] / "rallies.mp4", media_type="video/mp4")

    @router.get("/{key}/gaps-video")
    def gaps_video(key: str):
        path = run_of(key)["path"] / GAPS_NAME
        if not path.is_file():
            raise HTTPException(status_code=404, detail="no dead-time copy")
        return FileResponse(path, media_type="video/mp4")

    @router.get("/{key}/thumb/{name}")
    def thumb(key: str, name: str):
        path = run_of(key)["path"] / "thumbs" / name
        if not THUMB_NAME.match(name) or not path.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(path)

    @router.post("/{key}/point/{number}")
    def save_point(key: str, number: int, raw: Dict[str, Any] = Body(...)):
        """Store the verdict of one point (``status: null`` forgets it)."""
        run = run_of(key)
        view = view_of(run, gaps=True)
        point = next((p for p in view["points"] if p["point"] == number), None)
        if point is None:
            raise HTTPException(status_code=404, detail="no such point")
        path = review_path(gt_root, run["key"])
        review = load_review(path, run["key"])
        try:
            verdict = None if raw.get("status") is None else clean_verdict(raw, point)
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        # The verdict the page edited may sit under the frames of an earlier run.
        old = attach(review, view["points"])[0].get(number)
        if old is not None:
            put_verdict(review, None, old["start_frame"])
        put_verdict(review, verdict, point["start_frame"])
        save_review(path, review)
        return state_of(run, view)

    @router.post("/{key}/match")
    def save_match(key: str, raw: Dict[str, Any] = Body(...)):
        """Store the owner's final score and the points the run missed."""
        run = run_of(key)
        view = view_of(run, gaps=True)
        path = review_path(gt_root, run["key"])
        review = load_review(path, run["key"])
        try:
            review.update(clean_match_fields(raw, view["points"]))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        save_review(path, review)
        return state_of(run, view)

    @router.post("/{key}/gap/{after_point}")
    def save_gap(key: str, after_point: int, raw: Dict[str, Any] = Body(...)):
        """Store that the owner watched the dead time after a point
        (``checked``: true), or forget it."""
        run = run_of(key)
        view = view_of(run, gaps=True)
        gap = next((g for g in view["gaps"] if g["after_point"] == after_point), None)
        if gap is None:
            raise HTTPException(status_code=404, detail="no such gap")
        path = review_path(gt_root, run["key"])
        review = load_review(path, run["key"])
        put_gap(review, gap, bool(raw.get("checked")))
        save_review(path, review)
        return state_of(run, view)

    return router


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output-root", default="output", help="where the run directories are")
    parser.add_argument("--ground-truth", default="ground_truth",
                        help="where <match_key>_review.json is written")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import RedirectResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(title="Match review", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    app.include_router(create_router(Path(args.output_root), Path(args.ground_truth)))
    app.add_api_route("/", lambda: RedirectResponse("/review"), include_in_schema=False)
    print(f"Match review: http://{args.host}:{args.port}/review", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
