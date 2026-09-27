"""Map GAME_ON episodes to dictated GT points (open point 22, mechanism 1).

The 20260920 match run produces 57 raw GAME_ON episodes against 33 dictated
GT points.  The GT (match-points-v1) has NO frame anchors, so the mapping is
built from ORDER plus per-episode evidence:

- serve evidence (strong): an emitted serve action (touch_number=1) in or
  near the episode carries the server's court-side team letter (A=near /
  B=far).  The GT serve squad per point is mechanical (winner-of-previous
  serves, cross-checked against descriptions by
  ``derive_match_serve_windows.derive_serve_teams``); the squad's court side
  per point is mechanical too (``derive_sides``).  Expected emitted letter:
  'A' when the serving squad is on the near half at that point, else 'B'.
- confirmed-point overlap (structural): episodes overlapping a confirmed
  pipeline point are surely real rallies.
- description-implied rally size (weak): "ace" / serve-fault descriptions
  imply ~1 contact, "big rally" many, else a mid rally.
- BURST class: tiny no-action episodes (detection flickers, dead-ball
  handling) and any other episode that binds to no point.

Output: ``output/episode_point_map.json`` (with input provenance) + a
printed alignment table + the far/near serve census on the TRUE windows
(the mapped episode spans) -- the open-point-22 owner question ("far-side
serves seem untracked") answered per point, no owner anchors needed.

Diagnostic only: nothing here feeds the production pipeline, no video is
decoded (CSV/JSON inputs only -- VFR-seek safe).  Owner-ratified frame
anchors can later replace the inferred windows in downstream consumers.

Usage:
    python scripts/map_episodes_to_points.py \
        --gt ground_truth/20260920_match_points.json \
        --pipeline output/match20260920_posegate/pipeline_output.json \
        --game-state-csv output/match20260920_posegate/results_game_state.csv \
        [--out output/episode_point_map.json]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from derive_match_serve_windows import derive_serve_teams, derive_sides
from evaluate_match_points import episodes_from_game_state_csv

# A serve action counts as the point's serve when it lies within this many
# frames of an attached episode's span (serves are routinely emitted 5-30f
# BEFORE game_on fires -- the late-game_on family; and occasionally just
# after a late death).
SERVE_WINDOW_BEFORE = 60
SERVE_WINDOW_AFTER = 30

# An episode counts as overlapping a confirmed pipeline point within this
# tolerance (the point layer backdates starts; same value as
# evaluate_match_points._CONFIRM_TOLERANCE_FRAMES).
CONFIRM_TOLERANCE_FRAMES = 30

# Attach a second episode to an already-open point: costs this much before
# evidence; splits happen when game_on flickers off mid-rally.
ATTACH_PENALTY = 2.0
# ...and only while the game_off gap to the previous episode of that point
# is small (a mid-rally ball-loss flicker).  Observed real splits: 11-115f.
# Inter-point dead time (serve prep, ball retrieval) is far larger -- the
# biggest traps in the first production run attached points across 300-1100f
# gaps.  ATTACH_MAX_GAP_FRAMES = 150f ~ 6 s at 25.67 fps.
ATTACH_MAX_GAP_FRAMES = 150

# Burst scores: an episode that binds to no point.  Tiny no-action flickers
# are cheap bursts; anything that is physically a rally (confirmed overlap
# with a pipeline point, or action-rich) must not burst at all -- the first
# production run once parked a 671f 13-action confirmed rally as a BURST
# because bursting let later serve letters align.  A rally is a point.
BURST_TINY_MAX_DUR = 30
BURST_TINY_SCORE = 1.5
BURST_NO_ACTION_SCORE = 0.5
BURST_FORBIDDEN_SCORE = -50.0
BURST_RICH_MIN_ACTIONS = 2
BURST_SERVE_PENALTY = 3.5  # a serve in the window argues against BURST

# Starving a GT point (no episode at all): a real cost, cheaper for
# serve-fault points whose flight often never gathers a rally.
STARVE_SCORE = -2.5
STARVE_SERVE_FAULT_SCORE = -1.5

# Link evidence weights.
W_SERVE_MATCH = 3.0
W_SERVE_MISMATCH = -1.0
W_SERVE_NO_EXPECTATION = 1.0
W_CONFIRMED = 2.0
W_SIZE_IN_RANGE = 1.0
W_SIZE_BELOW = -0.5    # per missing contact
W_SIZE_ABOVE = -0.25   # per extra contact
W_SIZE_ABOVE_CAP = 2.0
W_DUR_LONG = -0.5
DUR_LONG_THRESHOLD = 700
W_DUR_SHORT = -0.5
DUR_SHORT_THRESHOLD = 30

_SERVE_FAULT_RE = re.compile(
    r"fails? (?:the )?serve|serves? (?:out|outside)|serve out|against the net",
    re.IGNORECASE)
_ACE_RE = re.compile(r"\bace\b", re.IGNORECASE)
_BIG_RALLY_RE = re.compile(r"\bbig rally\b|\brally\b|struggl", re.IGNORECASE)

# --- owner serve anchors (2026-09-27 dictation) ---------------------------
# The owner's frames are coarse video reads, so all tolerances below are
# generous and every deviation is REPORTED, never silently resolved.
# Emission window around an anchored serve moment: an emitted serve action
# may sit well before the owner's contact estimate (the #22 specimen: toss
# f889 vs owner f900) or the game_on layer may fire late.
ANCHOR_EMIT_BEFORE = 180
ANCHOR_EMIT_AFTER = 120
# The point's first episode (its rally) starts within this window after the
# serve moment (game_on fires on sustained flight, up to ~10s later).
ANCHOR_OPENER_BEFORE = 180
ANCHOR_OPENER_AFTER = 300
# A serve action inside a point's span but OUTSIDE its emission window is a
# false-positive candidate (the f3650 class: walking to the serve location
# with the ball in hand); it is reported, never counted.

_ANCHOR_RE = re.compile(
    r"^(P\d+|FALSE)\s+(\d+)\s+(near|far)?\s*"
    r"(TRACKED|NOT_TRACKED|MISCLASSIFIED)?\s*(.*)$")

NEG_INF = float("-inf")


# ----------------------------------------------------------------------
# evidence extraction (pure)
# ----------------------------------------------------------------------

def action_frame(a: Dict[str, Any]) -> int:
    """Frame of an action record (pipeline key: frame_number)."""
    return a["frame_number"]


def description_expectation(description: str) -> Tuple[int, int, str]:
    """Implied contact-count range [lo, hi] and class from the GT text.

    Classes: 'ace', 'serve_fault', 'big', 'normal'.  Deliberately loose:
    the sizes only break ties, they never overrule serve/order evidence.
    """
    d = description or ""
    if _ACE_RE.search(d):
        return 1, 2, "ace"
    if _SERVE_FAULT_RE.search(d):
        return 1, 2, "serve_fault"
    if _BIG_RALLY_RE.search(d):
        return 4, 12, "big"
    return 2, 6, "normal"


def is_serve_fault_description(description: str) -> bool:
    return description_expectation(description)[2] == "serve_fault"


def expected_serve_letter(
    serve_squad: Optional[str], sides: Dict[int, Dict[str, str]], point: int
) -> Optional[str]:
    """Expected EMITTED team letter for the point's serve.

    The pipeline's emitted team is the toucher's court half (A=near /
    B=far), NOT the squad -- squads only map to halves through the
    mechanically derived side table.  None when the server squad is
    unknown (GT point 1).
    """
    if serve_squad is None:
        return None
    return "A" if sides[point][serve_squad] == "near" else "B"


def collect_serves_near(
    serves: List[Dict[str, Any]], start: int, end: int,
    before: int = SERVE_WINDOW_BEFORE, after: int = SERVE_WINDOW_AFTER,
) -> List[Dict[str, Any]]:
    """Serve actions within [start-before, end+after] of an episode span."""
    out = []
    for a in serves:
        f = action_frame(a)
        if start - before <= f <= end + after:
            out.append({"frame": f, "team": a["team"]})
    return out


def episode_features(
    episodes: List[Tuple[int, int]],
    actions: List[Dict[str, Any]],
    confirmed_points: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Per-episode evidence: actions, serve markers, confirmed overlap."""
    serves = [a for a in actions if a.get("action") == "serve"]
    feats = []
    for start, end in episodes:
        in_span = [a for a in actions if start <= action_frame(a) <= end]
        mix: Dict[str, int] = {}
        for a in in_span:
            mix[a["action"]] = mix.get(a["action"], 0) + 1
        confirmed = any(
            cp["start_frame"] - CONFIRM_TOLERANCE_FRAMES <= end
            and start <= cp["end_frame"] + CONFIRM_TOLERANCE_FRAMES
            for cp in confirmed_points
        )
        opens_with_serve = bool(collect_serves_near(serves, start, start + 30,
                                                    before=60, after=0))
        feats.append({
            "start": start,
            "end": end,
            "dur": end - start + 1,
            "n_actions": len(in_span),
            "mix": mix,
            "confirmed": confirmed,
            "serves": collect_serves_near(serves, start, end),
            "opens_with_serve": opens_with_serve,
        })
    return feats


def burst_score(ep: Dict[str, Any]) -> float:
    """Score of labelling an episode BURST (binds to no GT point)."""
    if ep["confirmed"] or ep["n_actions"] >= BURST_RICH_MIN_ACTIONS:
        return BURST_FORBIDDEN_SCORE  # a rally is a point, never a burst
    if ep["n_actions"] == 0 and ep["dur"] <= BURST_TINY_MAX_DUR:
        s = BURST_TINY_SCORE
    elif ep["n_actions"] == 0:
        s = BURST_NO_ACTION_SCORE
    else:
        s = 0.0
    if ep["serves"]:
        s -= BURST_SERVE_PENALTY  # a serve in the window argues for a point
    return s


def starve_score(description: str) -> float:
    """Score of leaving a GT point with no episode at all."""
    if is_serve_fault_description(description):
        return STARVE_SERVE_FAULT_SCORE
    return STARVE_SCORE


def link_score(ep: Dict[str, Any], description: str, expected_letter: Optional[str]) -> Tuple[float, Dict[str, Any]]:
    """Score + evidence of opening GT point ``description`` with episode ``ep``."""
    s = 0.0
    ev: Dict[str, Any] = {}
    serve_ev = []
    if ep["serves"]:
        for sv in ep["serves"]:
            if expected_letter is None:
                s += 0.0  # P1: no expectation, presence alone is neutral here
                serve_ev.append({"frame": sv["frame"], "team": sv["team"], "match": "no_expectation"})
            elif sv["team"] == expected_letter:
                s += W_SERVE_MATCH
                serve_ev.append({"frame": sv["frame"], "team": sv["team"], "match": True})
            else:
                s += W_SERVE_MISMATCH
                serve_ev.append({"frame": sv["frame"], "team": sv["team"], "match": False})
        only_mismatch = all(not e["match"] for e in serve_ev) and expected_letter is not None
        if only_mismatch:
            ev["serve_side"] = "MISMATCH"
        else:
            ev["serve_side"] = "match"
    elif expected_letter is not None:
        ev["serve_side"] = "missing"
    ev["serves"] = serve_ev

    if ep["confirmed"]:
        s += W_CONFIRMED
        ev["confirmed_overlap"] = True

    lo, hi, kind = description_expectation(description)
    ev["expected_class"] = kind
    n = ep["n_actions"]
    if lo <= n <= hi:
        s += W_SIZE_IN_RANGE
    elif n < lo:
        s += W_SIZE_BELOW * (lo - n)
    else:
        s += max(-W_SIZE_ABOVE_CAP, W_SIZE_ABOVE * (n - hi))  # capped penalty
    if ep["dur"] > DUR_LONG_THRESHOLD and kind != "big":
        s += W_DUR_LONG
    if ep["dur"] < DUR_SHORT_THRESHOLD and lo >= 2:
        s += W_DUR_SHORT
    return s, ev


# ----------------------------------------------------------------------
# alignment (monotone DP)
# ----------------------------------------------------------------------

def align(
    eps: List[Dict[str, Any]],
    points: List[Dict[str, Any]],
    serve_teams: Dict[int, Optional[str]],
    sides: Dict[int, Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Monotone alignment: episodes -> (point | BURST), points -> episode(s) | starved.

    Returns one record per episode, in episode order:
      {"episode": i, "frames": [s, e], "point": k | None,
       "role": "point"|"burst"|"attach", "evidence": {...}}
    A "point" role opened the point; "attach" joined an already-open point
    (only across a small game_off gap -- ATTACH_MAX_GAP_FRAMES; a point
    cannot span inter-point dead time).
    """
    n, m = len(eps), len(points)
    expected = [
        expected_serve_letter(serve_teams.get(p["point"]), sides, p["point"])
        for p in points
    ]
    link = [link_score(eps[i], points[k]["description"], expected[k])
            for i in range(n) for k in range(m)]

    # dp[i][k][j+1]: best score with i episodes consumed, k points closed,
    # and the open point (k+1) last touched by episode j; j = -1 means no
    # point is open.  j is needed because an attach's plausibility depends
    # on the gap to the LAST episode of that point (bursts in between must
    # not shrink it).
    NEG = NEG_INF
    dp = [[[NEG] * (n + 1) for _ in range(m + 1)] for _ in range(n + 1)]
    bp = [[[None] * (n + 1) for _ in range(m + 1)] for _ in range(n + 1)]
    dp[0][0][0] = 0.0  # j = -1 encoded at index 0

    def jdx(j: int) -> int:
        return j + 1

    for i in range(n + 1):
        for k in range(m + 1):
            for j in range(-1, n):
                cur = dp[i][k][jdx(j)]
                if cur == NEG:
                    continue
                if j >= 0 and k < m:
                    # close the open point
                    if cur > dp[i][k + 1][jdx(-1)]:
                        dp[i][k + 1][jdx(-1)] = cur
                        bp[i][k + 1][jdx(-1)] = (i, k, j, "close")
                if j < 0 and k < m:
                    # starve point k+1 (nothing open for it)
                    sc = cur + starve_score(points[k]["description"])
                    if sc > dp[i][k + 1][jdx(-1)]:
                        dp[i][k + 1][jdx(-1)] = sc
                        bp[i][k + 1][jdx(-1)] = (i, k, j, "starve")
                if i < n:
                    # burst (open state unchanged)
                    sc = cur + burst_score(eps[i])
                    if sc > dp[i + 1][k][jdx(j)]:
                        dp[i + 1][k][jdx(j)] = sc
                        bp[i + 1][k][jdx(j)] = (i, k, j, "burst")
                    if j < 0 and k < m:
                        # open point k+1 with episode i
                        sc, ev = link[i * m + k]
                        sc = cur + sc
                        if sc > dp[i + 1][k][jdx(i)]:
                            dp[i + 1][k][jdx(i)] = sc
                            bp[i + 1][k][jdx(i)] = (i, k, j, ("open", ev))
                    elif j >= 0 and k < m:
                        # attach episode i to the open point k+1, only
                        # across a small game_off gap, and never across a
                        # serve marker (a serve opens a NEW point)
                        if eps[i].get("opens_with_serve"):
                            continue
                        gap = eps[i]["start"] - eps[j]["end"] - 1
                        if gap <= ATTACH_MAX_GAP_FRAMES:
                            sc, ev = link[i * m + k]
                            sc = cur + sc - ATTACH_PENALTY
                            if sc > dp[i + 1][k][jdx(i)]:
                                ev = dict(ev or {})
                                ev["attach_gap_frames"] = gap
                                dp[i + 1][k][jdx(i)] = sc
                                bp[i + 1][k][jdx(i)] = (i, k, j, ("attach", ev))

    # drain: at i == n, close the open point / starve the remaining points.
    # Walk the closure chain from every (n, k, j) down to (n, m, -1) by
    # simulating the forced close/starve moves.
    for k in range(m):
        for j in range(-1, n):
            cur = dp[n][k][jdx(j)]
            if cur == NEG:
                continue
            if j >= 0:
                if cur > dp[n][k + 1][jdx(-1)]:
                    dp[n][k + 1][jdx(-1)] = cur
                    bp[n][k + 1][jdx(-1)] = (n, k, j, "close")
            else:
                sc = cur + starve_score(points[k]["description"])
                if sc > dp[n][k + 1][jdx(-1)]:
                    dp[n][k + 1][jdx(-1)] = sc
                    bp[n][k + 1][jdx(-1)] = (n, k, j, "starve")

    best = dp[n][m][jdx(-1)]
    assert best > NEG_INF, "alignment found no feasible path"

    # reconstruct: (episode_index, action, point_number_or_None, evidence)
    seq: List[Tuple[int, str, Optional[int], Optional[Dict[str, Any]]]] = []
    i, k, j = n, m, -1
    while (i, k, j) != (0, 0, -1):
        prev = bp[i][k][jdx(j)]
        assert prev is not None, "alignment reconstruction hit an unreachable state"
        pi, pk, pj, act = prev
        if isinstance(act, tuple):
            label, ev = act
            # open/attach happened FROM (pi, pk, pj): the 1-based point
            # number is pk+1 -- carried here, NOT re-counted later (a
            # starved point would shift a naive counter)
            seq.append((i - 1, label, pk + 1, ev))
        elif act == "burst":
            seq.append((i - 1, "burst", None, None))
        # close/starve: no episode consumed, nothing to record
        i, k, j = pi, pk, pj
    seq.reverse()

    records = []
    for (idx, label, point, ev) in seq:
        ep = eps[idx]
        records.append({
            "episode": idx,
            "frames": [ep["start"], ep["end"]],
            "point": point,
            "role": {"burst": "burst", "open": "point", "attach": "attach"}[label],
            "evidence": ev or {},
        })
    return records


def build_point_view(
    eps: List[Dict[str, Any]],
    records: List[Dict[str, Any]],
    points: List[Dict[str, Any]],
    serve_teams: Dict[int, Optional[str]],
    sides: Dict[int, Dict[str, str]],
    serves_all: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Per-GT-point view: attached episodes, TRUE window, serve census."""
    by_point: Dict[int, List[Dict[str, Any]]] = {}
    for r in records:
        if r["point"] is not None:
            by_point.setdefault(r["point"], []).append(r)
    view = []
    for p in points:
        k = p["point"]
        attached = sorted(by_point.get(k, []), key=lambda r: r["frames"][0])
        starved = not attached
        if attached:
            s = min(r["frames"][0] for r in attached)
            e = max(r["frames"][1] for r in attached)
            window = [s - SERVE_WINDOW_BEFORE, e + SERVE_WINDOW_AFTER]
        else:
            window = None
        view.append({
            "point": k,
            "winner": p["winner"],
            "serve_squad": serve_teams.get(k),
            "serve_side_near_far": None if serve_teams.get(k) is None else sides[k][serve_teams.get(k)],
            "expected_serve_letter": expected_serve_letter(serve_teams.get(k), sides, k),
            "description": p["description"],
            "starved": starved,
            "episodes": [r["episode"] for r in attached],
            "window_frames": window,
            "serves_emitted": [],
            "serve_side_match": None,
        })
    # attribute each serve action to EXACTLY ONE point: the point whose
    # window contains it and whose nearest episode boundary is closest
    # (adjacent windows overlap by the +/- serve margins; naive containment
    # double-counted serves sitting in the gap between two points)
    view_by_point = {v["point"]: v for v in view}
    for a in sorted(serves_all, key=action_frame):
        f = action_frame(a)
        best = None  # (distance, point)
        for v in view:
            w = v["window_frames"]
            if w and w[0] <= f <= w[1]:
                dist = min(abs(f - eps[idx]["start"]) + abs(f - eps[idx]["end"])
                           for idx in v["episodes"]) if v["episodes"] else 0
                cand = (dist, v["point"])
                if best is None or cand < best:
                    best = cand
        if best is not None:
            view_by_point[best[1]]["serves_emitted"].append(
                {"frame": f, "team": a["team"]})
    for v in view:
        expected = v["expected_serve_letter"]
        if v["serves_emitted"] and expected is not None:
            v["serve_side_match"] = any(x["team"] == expected for x in v["serves_emitted"])
    return view


# ----------------------------------------------------------------------
# owner serve anchors
# ----------------------------------------------------------------------

def parse_serve_anchors(path: str) -> Dict[str, Any]:
    """Parse the ratified serve-anchor file (see ground_truth/*.txt header).

    Returns {"points": {k: {frame, side, verdict, note}}, "false":
    [{frame, note}], "order": [k ...]}.
    """
    points: Dict[int, Dict[str, Any]] = {}
    false_pos: List[Dict[str, Any]] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        m = _ANCHOR_RE.match(line)
        if not m:
            raise ValueError(f"{path}: unparsable anchor line: {raw!r}")
        kind, frame, side, verdict, note = m.groups()
        if kind == "FALSE":
            false_pos.append({"frame": int(frame), "note": note.strip()})
            continue
        k = int(kind[1:])
        points[k] = {
            "frame": int(frame),
            "side": side,
            "verdict": verdict,
            "note": note.strip(),
        }
    order = sorted(points)
    if order != list(range(1, len(order) + 1)):
        raise ValueError(f"{path}: anchored points must be 1..K, got {order}")
    return {"points": points, "false": false_pos, "order": order}


def anchored_prefix(
    eps: List[Dict[str, Any]],
    actions: List[Dict[str, Any]],
    points: List[Dict[str, Any]],
    serve_teams: Dict[int, Optional[str]],
    sides: Dict[int, Dict[str, str]],
    anchors: Dict[str, Any],
) -> Dict[str, Any]:
    """Assign episodes/serve emissions for the ANCHORED point prefix.

    Owner frames are coarse, so the assignment is bracket-based and every
    deviation becomes an explicit finding:
    - opener of anchored point k = first episode starting in
      [s_k - 180, s_k + 300]; none -> the point is window-only (starved);
    - later episodes join by the normal attach gap while they start before
      the next anchor; one that cannot join is a BOUNDARY CONFLICT
      (reported, never silently a burst) -- a confirmed rally is somewhere
      in the GT, the owner sheet must say where;
    - serve emissions = serve actions in [s_k - 180, s_k + 120]; a serve
      action inside the point's span but outside the window is a
      FALSE-POSITIVE candidate (the f3650 walking-with-ball class);
    - non-serve actions right at the serve moment are reported as
      MISCLASSIFIED-SERVE candidates (the owner confirmed four).
    """
    aret = anchors["points"]
    order = anchors["order"]
    serves_all = [a for a in actions if a.get("action") == "serve"]

    # P1's server is not derivable mechanically; the owner's side fills it.
    if order and serve_teams.get(order[0]) is None and aret[order[0]]["side"]:
        side = aret[order[0]]["side"]
        serve_teams = dict(serve_teams)
        serve_teams[order[0]] = next(
            s for s in ("A", "B") if sides[order[0]][s] == side)

    # ---- FALSE anchors: emitted serves near a FALSE frame are suspects
    false_marks = [] if anchors is None else anchors["false"]

    point_view: List[Dict[str, Any]] = []
    claimed: set = set()
    conflict_eps: List[int] = []
    false_candidates: List[Dict[str, Any]] = []
    for idx, k in enumerate(order):
        a = aret[k]
        s = a["frame"]
        nxt = aret[order[idx + 1]]["frame"] if idx + 1 < len(order) else None
        span_end = (nxt - 180) if nxt is not None else None
        opener = next((i for i, e in enumerate(eps)
                       if s - ANCHOR_OPENER_BEFORE <= e["start"] <= s + ANCHOR_OPENER_AFTER),
                      None)
        attached: List[int] = []
        if opener is not None:
            claimed.add(opener)
            last = opener
            for i in range(opener + 1, len(eps)):
                if eps[i]["start"] >= (span_end if span_end is not None
                                       else eps[len(eps) - 1]["end"] + 1):
                    break
                if eps[i].get("opens_with_serve"):
                    break  # a serve marker starts a NEW point, never an attach
                gap = eps[i]["start"] - eps[last]["end"] - 1
                if gap <= ATTACH_MAX_GAP_FRAMES:
                    attached.append(i)
                    claimed.add(i)
                    last = i
                else:
                    conflict_eps.append(i)  # boundary conflict, reported
        episodes = ([opener] if opener is not None else []) + attached
        window = [s - ANCHOR_EMIT_BEFORE, s + ANCHOR_EMIT_AFTER]
        emitted, misclassified = [], []
        span_lo = s - ANCHOR_OPENER_BEFORE
        for x in serves_all:
            f = action_frame(x)
            if window[0] <= f <= window[1]:
                emitted.append({"frame": f, "team": x["team"]})
            elif (span_end is not None and span_lo <= f < span_end
                  and f not in [e["frame"] for e in emitted]):
                false_candidates.append({
                    "frame": f, "team": x["team"], "point": k,
                    "note": "serve action inside the point span but outside "
                            "the anchored emission window"})
        for x in actions:
            f = action_frame(x)
            if (x["action"] != "serve" and not emitted
                    and s - 30 <= f <= s + 45):
                misclassified.append({"frame": f, "action": x["action"],
                                      "team": x["team"]})
                if len(misclassified) >= 2:
                    break
        squad = serve_teams.get(k)
        expected = expected_serve_letter(squad, sides, k)
        emission_conflict = False
        for fm in false_marks:
            near = [e for e in emitted if abs(e["frame"] - fm["frame"]) <= 250]
            for e in near:
                false_candidates.append({
                    "frame": e["frame"], "team": e["team"], "point": k,
                    "note": f"near owner FALSE mark f{fm['frame']}: {fm['note']}"})
                emitted.remove(e)
                emission_conflict = True
        side_match = None
        if emitted and expected is not None:
            side_match = any(x["team"] == expected for x in emitted)
        point_view.append({
            "point": k,
            "winner": points[k - 1]["winner"],
            "serve_squad": squad,
            "serve_side_near_far": None if squad is None else sides[k][squad],
            "expected_serve_letter": expected,
            "description": points[k - 1]["description"],
            "starved": opener is None,
            "episodes": episodes,
            "window_frames": window,
            "serves_emitted": emitted,
            "serve_side_match": side_match,
            "attribution": "anchored",
            "anchor_frame": s,
            "anchor_side": a["side"],
            "anchor_verdict": a["verdict"],
            "emission_conflict": emission_conflict,
            "misclassified_candidates": misclassified,
        })
    tail_start = (min(i for i in range(len(eps)) if i not in claimed
                      and eps[i]["start"] >= aret[order[-1]]["frame"] - 180)
                  if any(eps[i]["start"] >= aret[order[-1]]["frame"] - 180
                         for i in range(len(eps)) if i not in claimed)
                  else len(eps))
    return {
        "point_view": point_view,
        "claimed": claimed,
        "conflict_eps": sorted(set(conflict_eps)),
        "false_candidates": false_candidates,
        "tail_start": tail_start,
        "serve_teams": serve_teams,
    }


def census(point_view: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Far/near serve census over TRUE windows (the open-point-22 answer)."""
    out: Dict[str, Any] = {}
    for side_key, letter in (("near", "A"), ("far", "B")):
        pts = [v for v in point_view if v["expected_serve_letter"] == letter]
        keyed = [v for v in pts if v["window_frames"] is not None]
        emitted = [v for v in keyed if v["serves_emitted"]]
        misclassified = [v for v in keyed if not v["serves_emitted"]
                         and v.get("misclassified_candidates")]
        matched = [v for v in keyed if v["serve_side_match"]]
        late = []
        for v in emitted:
            for sv in v["serves_emitted"]:
                late.append(v["window_frames"][0] + SERVE_WINDOW_BEFORE - sv["frame"] - 1)
        out[side_key] = {
            "n_points": len(pts),
            "n_window": len(keyed),
            "n_serve_emitted": len(emitted),
            "n_serve_misclassified": len(misclassified),
            "n_serve_missing": len(keyed) - len(emitted) - len(misclassified),
            "misclassified_points": [v["point"] for v in misclassified],
            "n_side_match": len(matched),
            "n_side_mismatch": len(emitted) - len(matched),
            "n_starved_no_window": len(pts) - len(keyed),
            "points": [v["point"] for v in pts],
        }
    out["unknown_server"] = [v["point"] for v in point_view
                             if v["expected_serve_letter"] is None]
    return out


# ----------------------------------------------------------------------
# reporting
# ----------------------------------------------------------------------

def print_report(records: List[Dict[str, Any]], eps: List[Dict[str, Any]],
                 point_view: List[Dict[str, Any]],
                 census_view: Dict[str, Any],
                 false_candidates: Optional[List[Dict[str, Any]]] = None) -> None:
    print("episode -> point map")
    print(f"{'ep':>4} {'frames':>15} {'dur':>5} {'act':>4} {'conf':>4}  {'point':>5}  role      evidence")
    for r in records:
        ep = eps[r["episode"]]
        ev = r["evidence"]
        flags = []
        if ev.get("serve_side") == "MISMATCH":
            flags.append("SERVE_SIDE_MISMATCH")
        if ev.get("confirmed_overlap"):
            flags.append("confirmed")
        if ev.get("serves"):
            flags.append("serve@" + ",".join(str(s["frame"]) for s in ev["serves"]))
        print(f"{r['episode']:>4} {r['frames'][0]:>7}-{r['frames'][1]:<7} "
              f"{r['frames'][1] - r['frames'][0] + 1:>5} "
              f"{ep.get('n_actions', ''):>4} {str(ep.get('confirmed', '')):>4}  "
              f"{str(r['point']):>5}  {r['role']:<8} {' '.join(flags)}")

    print("\nper-point view (TRUE windows)")
    print(f"{'P':>3} {'win':>3} {'srv sq':>6} {'nf':>4} {'exp':>3} {'eps':>10} "
          f"{'window':>15} {'serves':>18} verdict")
    for v in point_view:
        w = v["window_frames"]
        serves = ",".join(f"{s['frame']}{s['team']}" for s in v["serves_emitted"]) or "-"
        if v.get("attribution") == "anchored":
            if v["starved"]:
                verdict = "serve MISSING (anchored)"
            elif not v["serves_emitted"]:
                verdict = "serve MISSING"
            elif v["serve_side_match"] is False:
                verdict = "serve SIDE MISMATCH"
            else:
                verdict = "serve OK"
            if v.get("emission_conflict"):
                verdict += " + EMISSION CONFLICT (owner FALSE mark)"
            if v.get("misclassified_candidates"):
                verdict += " + MISCLASSIFIED[" + ",".join(
                    f"{m['frame']}{m['action']}" for m in v["misclassified_candidates"]) + "]"
            verdict = "ANCHORED " + verdict
        elif v["starved"]:
            verdict = "STARVED (no episode)"
        elif not v["serves_emitted"]:
            verdict = "serve MISSING"
        elif v["serve_side_match"] is False:
            verdict = "serve SIDE MISMATCH"
        else:
            verdict = "serve OK"
        print(f"{v['point']:>3} {v['winner']:>3} {str(v['serve_squad']):>6} "
              f"{str(v['serve_side_near_far']):>4} {str(v['expected_serve_letter']):>3} "
              f"{','.join(str(e) for e in v['episodes']):>10} "
              f"{(f'{w[0]}-{w[1]}' if w else '-'):>15} {serves:>18} {verdict}")

    print("\nfar/near serve census (TRUE windows)")
    for key in ("near", "far"):
        c = census_view[key]
        print(f"  {key}: {c['n_serve_emitted']}/{c['n_window']} emitted "
              f"({c['n_serve_missing']} missing, {c['n_serve_misclassified']} "
              f"emitted-as-other-gesture at {c['misclassified_points']}), "
              f"side match {c['n_side_match']}, "
              f"mismatch {c['n_side_mismatch']}, starved-no-window {c['n_starved_no_window']}; "
              f"points {c['points']}")
    print(f"  unknown-server points: {census_view['unknown_server']}")
    if false_candidates:
        print("\nFALSE-POSITIVE serve candidates (inside a point span, outside "
              "its anchored emission window -- owner sheet to confirm):")
        for x in false_candidates:
            print(f"  f{x['frame']} team={x['team']} in P{x['point']}'s span")
    conflicts = [r for r in records if r["role"] == "conflict"]
    if conflicts:
        print("\nBOUNDARY-CONFLICT episodes (confirmed rallies the anchored "
              "brackets cannot place -- owner sheet to adjudicate):")
        for r in conflicts:
            i = r["episode"]
            print(f"  ep{i:02d} f{eps[i]['start']}-{eps[i]['end']} "
                  f"actions={eps[i]['n_actions']} confirmed={eps[i]['confirmed']}")


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gt", required=True)
    ap.add_argument("--pipeline", required=True)
    ap.add_argument("--game-state-csv", required=True)
    ap.add_argument("--serve-anchors", help="owner-ratified serve anchor file "
                    "(ground_truth/20260920_match_serve_anchors.txt)")
    ap.add_argument("--out", default="output/episode_point_map.json")
    args = ap.parse_args(argv)

    gt = json.loads(Path(args.gt).read_text(encoding="utf-8"))
    points = gt["points"]
    pipeline = json.loads(Path(args.pipeline).read_text(encoding="utf-8"))
    actions = pipeline["actions"]
    confirmed_points = (pipeline.get("game_state") or {}).get("points") or []

    episodes = episodes_from_game_state_csv(args.game_state_csv)
    eps = episode_features(episodes, actions, confirmed_points)

    serve_teams = derive_serve_teams(points)
    sides = derive_sides(points)

    anchors = None
    anchored = None
    false_candidates: List[Dict[str, Any]] = []
    if args.serve_anchors:
        anchors = parse_serve_anchors(args.serve_anchors)
        anchored = anchored_prefix(eps, actions, points, serve_teams, sides, anchors)
        serve_teams = anchored["serve_teams"]
        false_candidates = anchored["false_candidates"]
        tail_eps = eps[anchored["tail_start"]:]
        tail_points = [p for p in points if p["point"] > max(anchors["order"])]
        tail_records = align(tail_eps, tail_points, serve_teams, sides)
        for r in tail_records:
            r["episode"] += anchored["tail_start"]
            r["frames"] = list(r["frames"])
            r["point"] = (r["point"] + max(anchors["order"])) if r["point"] else None
        tail_view = build_point_view(
            eps, tail_records, tail_points, serve_teams, sides,
            [a for a in actions if a.get("action") == "serve"
             and action_frame(a) >= eps[anchored["tail_start"]]["start"] - SERVE_WINDOW_BEFORE])
        records = (
            [{"episode": i, "frames": [eps[i]["start"], eps[i]["end"]],
              "point": None, "role": "conflict", "evidence": {}}
             for i in anchored["conflict_eps"]]
            + tail_records)
        point_view = anchored["point_view"] + tail_view
    else:
        records = align(eps, points, serve_teams, sides)
        point_view = None
    serves_all = [a for a in actions if a.get("action") == "serve"]
    if point_view is None:
        point_view = build_point_view(
            eps, records, points, serve_teams, sides, serves_all)
    census_view = census(point_view)

    print_report(records, eps, point_view, census_view, false_candidates)

    n_mapped = sum(1 for r in records if r["role"] not in ("burst", "conflict"))
    n_bursts = sum(1 for r in records if r["role"] == "burst")
    n_conflicts = sum(1 for r in records if r["role"] == "conflict")
    n_starved = sum(1 for v in point_view if v["starved"])
    result = {
        "video": gt.get("video"),
        "generated_from": {
            "gt": args.gt,
            "pipeline": args.pipeline,
            "game_state_csv": args.game_state_csv,
            "serve_anchors": args.serve_anchors,
            "note": "owner-anchored prefix + DP tail; windows are anchored "
                    "or inferred, only the anchored prefix is owner-ratified",
        },
        "summary": {
            "n_episodes": len(eps),
            "n_points": len(points),
            "n_episodes_mapped": n_mapped,
            "n_bursts": n_bursts,
            "n_conflict_episodes": n_conflicts,
            "n_points_starved": n_starved,
            "n_false_serve_candidates": len(false_candidates),
        },
        "false_serve_candidates": false_candidates,
        "episodes": records,
        "points": point_view,
        "census": census_view,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
