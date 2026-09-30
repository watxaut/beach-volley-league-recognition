#!/usr/bin/env python3
"""Pass-2 point winner/outcome layer (open point 21, mechanism 3).

One mechanism, hindsight-only (AGENTS.md section 6): a pure observer over
the EXISTING JSON artifacts -- the episode->point map's TRUE windows, the
pipeline action stream, and the pass-2 serve resolutions.  No video is
decoded, nothing under src/ is touched, entreno neutrality holds by
construction.

Mechanism (diagnosed first, see logs/point_winner_report.md): the winner
is resolved with a FAULT PRIOR over the terminal touch -- the side of the
last live touch in the window loses the point.  Rationale: the match's
endings are dominated by unreturned attacks landing out/at the net and
failed receptions, and the pipeline's per-action side letter is the only
terminal-touch signal the artifacts carry.  The prior is wrong exactly
when the last toucher's side SCORED (kill/ace class); disambiguating that
needs the ball-death IN/OUT position, which no current artifact holds
(pipeline_output.json has actions/spikes/game state only), so those are
reported as honest misses, never guessed around.

Semantics: ``winner`` is a COURT-SIDE letter at the moment of the point
(A = near half, B = far half -- the frame of reference of the whole
perception stack, CourtCalibration.get_team).  Squad letters (GT
convention: A = the squad that started near) differ from side letters
whenever a side switch has happened; the side->squad mapping uses the GT
side-switch schedule and is therefore computed ONLY by ``--validate``.

GT-leakage guard (structural, not a promise): the inference path reads
its inputs through field projections -- the map contributes window
geometry + episode spans ONLY (its ``winner``/``description``/
``expected_serve_letter``/``serve_squad``/... fields are dropped on
load), and the serve layer contributes owner-verdict flags ONLY.  In
particular ``serve.team_resolved`` (the 13 winner-serves-derived team
overrides of the serve layer) is NEVER projected into inference; the
override EXISTENCE is kept as a confidence flag.  ``--validate`` may read
the GT winner/side_switch fields and does the leakage accounting.

Usage:
    python scripts/resolve_point_winners.py            # defaults below
    python scripts/resolve_point_winners.py --validate \\
        ground_truth/20260920_match_points.json        # + report file
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_MAP = "output/episode_point_map.json"
DEFAULT_PIPELINE = "output/match20260920_posegate/pipeline_output.json"
DEFAULT_GAME_STATE_CSV = (
    "output/match20260920_posegate/results_game_state.csv")
DEFAULT_SERVE_RELABEL = "output/serve_relabel.json"
DEFAULT_OUT = "output/point_winners.json"
DEFAULT_GT = "ground_truth/20260920_match_points.json"
DEFAULT_REPORT = "logs/point_winner_report.md"

OPPONENT = {"A": "B", "B": "A"}

# Attack-ish terminal touches (second/third contact over the net or a net
# duel); a dig/set/serve ending is a control/reception ending.
_ATTACK_ACTIONS = {"spike", "block", "overpass"}

# Terminal-touch classes that carry a pass-2 team override in the serve
# layer (owner/winner-serves provenance, never inherited here).
_STREAM_SERVE_SOURCES = {"emitted", "relabeled", "owner_pinned"}
_UNADOPTED_SERVE_SOURCES = {"anchor_only", "report_only", "missing"}

# --- GT-leakage projections (the ONLY fields inference may see) ----------
_MAP_POINT_FIELDS = ("point", "window_frames")
_SERVE_FIELDS = ("frame", "source", "action_original", "team_emitted",
                 "team_overridden")

# Dictated-ending vocabulary used ONLY by --validate to classify misses.
_KILL_RE = ("scores", "wins the point", " ace", "touches line",
            "touch the line", "touches the line")


# ----------------------------------------------------------------------
# input projection (leakage guard)
# ----------------------------------------------------------------------

def project_map(amap: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map points reduced to window geometry (GT-derived fields dropped)."""
    # NOTE: points[].episodes are episode IDs, not indices into
    # amap["episodes"] (which records only a burst/offgame/point subset) --
    # the reliable rally-death span source is the game-state CSV run that
    # contains the terminal touch (see game_on_runs).
    return [{k: pv.get(k) for k in _MAP_POINT_FIELDS}
            for pv in amap.get("points", [])]


def project_serve_layer(rel: Dict[str, Any]) -> Dict[str, Any]:
    """Serve layer reduced to owner-verdict flags (no resolved teams).

    ``team_resolved`` is winner-serves-derived on overridden rows (13 in
    the 20260920 match) and would leak GT winners into this layer; only
    ``team_emitted`` (the stream's own letter) and the override FLAG are
    projected.
    """
    serves = {}
    for r in rel.get("points", []):
        s = r.get("serve")
        if s:
            serves[r["point"]] = {k: s.get(k) for k in _SERVE_FIELDS}
        else:
            serves[r["point"]] = None
    overrides = {a["frame_number"] for a in rel.get("actions_pass2", [])
                 if a.get("pass2_team_overridden")}
    demotions = [{"frame": d["frame"], "because": d["because"]}
                 for d in rel.get("demotions", [])]
    return {"serves": serves, "override_frames": overrides,
            "demotions": demotions}


# ----------------------------------------------------------------------
# pure resolution
# ----------------------------------------------------------------------

def live_actions(actions: List[Dict[str, Any]], window: List[int],
                 demoted_frames: set) -> List[Dict[str, Any]]:
    w0, w1 = window
    return sorted((a for a in actions
                   if w0 <= a["frame_number"] <= w1
                   and a["frame_number"] not in demoted_frames),
                  key=lambda a: a["frame_number"])


def ending_class(terminal: Dict[str, Any],
                 serve: Optional[Dict[str, Any]]) -> str:
    """Structural descriptor of HOW the stream says the rally ended."""
    if serve is not None and serve.get("source") in _STREAM_SERVE_SOURCES \
            and serve.get("frame") == terminal["frame_number"]:
        return "serve_terminal"
    if terminal.get("action") in _ATTACK_ACTIONS \
            or (terminal.get("touch_number") or 0) >= 2:
        return "attack_terminal"
    return "reception_terminal"


def game_on_runs(csv_path: str) -> List[List[int]]:
    """[start, end] frame spans of every game_on run (perception output)."""
    import csv
    runs: List[List[int]] = []
    cur: Optional[List[int]] = None
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fr = int(row["Frame_Index"])
            if row["Game_State"] == "game_on":
                if cur is not None and cur[1] == fr - 1:
                    cur[1] = fr
                else:
                    if cur is not None:
                        runs.append(cur)
                    cur = [fr, fr]
            elif cur is not None:
                runs.append(cur)
                cur = None
    if cur is not None:
        runs.append(cur)
    return runs


def ball_death(runs: List[List[int]], terminal_frame: Optional[int],
               window: List[int]) -> Dict[str, Any]:
    """Rally-death evidence from the game-state runs (pure observer).

    The run containing the terminal touch ends when the rally state
    machine dies; frames_after_terminal measures how long the rally lived
    past the last emitted touch (large = trailing touches likely
    unemitted).  The DEATH SIDE is not in any artifact (no per-frame ball
    track), so side stays None -- honestly, not guessed.
    """
    run = next((r for r in runs if terminal_frame is not None
                and r[0] <= terminal_frame <= r[1]), None)
    return {
        "frame": run[1] if run else None,
        "frames_after_terminal": (run[1] - terminal_frame
                                  if run and terminal_frame is not None
                                  else None),
        "side": None,
        "note": ("game_on never fired for this rally (serve-fault / "
                 "never-gathered class)" if run is None else
                 "end of the game_on run containing the terminal touch"),
        "side_note": "no per-frame ball track in the pipeline artifacts; "
                     "ball-death side/in-out needs a tracker sidecar",
    }


def outcome_signal(spikes: List[Dict[str, Any]],
                   window: List[int]) -> Optional[Dict[str, Any]]:
    """Latest spike record that resolved INSIDE the window (evidence only).

    Measured on the 20260920 match the spike outcome is NOT a usable
    winner rule (4/10 on last-touch spikes -- the SpikeAnalyzer team
    letter inherits the same net-boundary attribution errors), so this is
    reported, never consumed.
    """
    w1 = window[1]
    inside = [s for s in spikes if window[0] <= s["frame"] <= w1
              and s.get("resolution_frame") is not None
              and s["resolution_frame"] <= w1]
    if not inside:
        return None
    s = max(inside, key=lambda s: s["frame"])
    return {"frame": s["frame"], "team": s["team"], "outcome": s["outcome"],
            "resolution_frame": s["resolution_frame"]}


def resolve_point(pv: Dict[str, Any], actions: List[Dict[str, Any]],
                  spikes: List[Dict[str, Any]],
                  serve: Optional[Dict[str, Any]],
                  override_frames: set,
                  demoted_frames: set,
                  runs: List[List[int]]) -> Dict[str, Any]:
    """Resolve one TRUE window to a winning COURT-SIDE (or abstain)."""
    k = pv["point"]
    window = pv.get("window_frames")
    rec: Dict[str, Any] = {
        "point": k,
        "window_frames": window,
        "winner": None,
        "abstain": None,
        "method": "last_touch_fault_prior",
        "ending_class": None,
        "confidence": None,
        "evidence": {},
        "flags": [],
    }
    if not window:
        rec["abstain"] = "no_true_window"
        rec["confidence"] = "low"
        return rec

    live = live_actions(actions, window, demoted_frames)
    excluded = sorted(a["frame_number"] for a in actions
                      if window[0] <= a["frame_number"] <= window[1]
                      and a["frame_number"] in demoted_frames)
    terminal = live[-1] if live else None
    if terminal is None:
        rec["abstain"] = "no_live_touch"
        rec["confidence"] = "low"
        rec["evidence"] = {"n_live_actions": 0, "excluded_demoted": excluded}
        return rec

    team = terminal.get("team")
    if team not in OPPONENT:
        rec["abstain"] = "terminal_team_unknown"
        rec["confidence"] = "low"
        rec["evidence"] = {"terminal_touch": _touch_evidence(terminal)}
        return rec

    ec = ending_class(terminal, serve)
    flags: List[str] = []
    pos = terminal.get("team_in_possession")
    if pos is not None and pos != team:
        flags.append("contested_attribution")
    if terminal["frame_number"] in override_frames:
        flags.append("terminal_team_override_flagged_by_pass2")
    if serve is not None and serve.get("source") in _UNADOPTED_SERVE_SOURCES:
        flags.append("serve_not_adopted_in_stream")
    if (serve is not None and serve.get("source") == "owner_pinned"
            and not window[0] <= serve["frame"] <= window[1]):
        flags.append("pinned_serve_outside_window")

    rec.update({
        "winner": OPPONENT[team],
        "ending_class": ec,
        "confidence": "low" if flags else "medium",
        "flags": flags,
        "evidence": {
            "terminal_touch": _touch_evidence(terminal),
            "serve": ({k2: serve.get(k2) for k2 in _SERVE_FIELDS}
                      if serve else None),
            "ball_death": ball_death(runs, terminal["frame_number"], window),
            "outcome_signal": outcome_signal(spikes, window),
            "n_live_actions": len(live),
            "excluded_demoted": excluded,
        },
    })
    return rec


def _touch_evidence(a: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "frame": a["frame_number"],
        "action": a["action"],
        "team_emitted": a.get("team"),
        "team_in_possession": a.get("team_in_possession"),
        "touch_number": a.get("touch_number"),
        "contact_kind": a.get("contact_kind"),
    }


def census(resolutions: List[Dict[str, Any]]) -> Dict[str, Any]:
    decided = [r for r in resolutions if r["winner"]]
    abst = [r for r in resolutions if r["abstain"]]
    return {
        "n_points": len(resolutions),
        "n_winners": len(decided),
        "n_abstain": len(abst),
        "by_ending_class": {
            ec: [r["point"] for r in resolutions
                 if r["ending_class"] == ec]
            for ec in ("serve_terminal", "attack_terminal",
                       "reception_terminal", None)
        },
        "by_confidence": {
            c: [r["point"] for r in resolutions if r["confidence"] == c]
            for c in ("low", "medium")
        },
        "flagged": {
            f: [r["point"] for r in resolutions if f in r["flags"]]
            for f in sorted({f for r in resolutions for f in r["flags"]})
        },
    }


# ----------------------------------------------------------------------
# driver
# ----------------------------------------------------------------------

def run(map_path: str, pipeline_path: str, serve_path: str,
        out_path: str, game_state_csv: str = DEFAULT_GAME_STATE_CSV
        ) -> Dict[str, Any]:
    amap = json.loads(Path(map_path).read_text(encoding="utf-8"))
    pipe = json.loads(Path(pipeline_path).read_text(encoding="utf-8"))
    rel = json.loads(Path(serve_path).read_text(encoding="utf-8"))

    points = project_map(amap)
    serve_layer = project_serve_layer(rel)
    actions = sorted(pipe["actions"], key=lambda a: a["frame_number"])
    spikes = sorted(pipe.get("spikes", []),
                    key=lambda s: (s["frame"], s.get("resolution_frame") or 0))
    demoted = {d["frame"] for d in serve_layer["demotions"]}
    runs = game_on_runs(game_state_csv) if game_state_csv else []

    resolutions = [resolve_point(pv, actions, spikes,
                                 serve_layer["serves"].get(pv["point"]),
                                 serve_layer["override_frames"], demoted,
                                 runs)
                   for pv in points]

    out = {
        "video": amap.get("video"),
        "generated_from": {
            "map": map_path,
            "pipeline": pipeline_path,
            "game_state_csv": game_state_csv,
            "serve_relabel": serve_path,
            "note": "pass-2 interpretation layer (AGENTS.md section 6); "
                    "perception untouched, no video decoded",
        },
        "conventions": {
            "winner": "COURT-SIDE letter at the point (A=near half, "
                      "B=far half; the perception stack's frame of "
                      "reference). NOT a squad letter: squads swap halves "
                      "at side switches, and the side-switch schedule is "
                      "GT -- mapping side->squad happens only in "
                      "--validate.",
            "method": "fault prior: the terminal (last live) touch's side "
                      "loses the point; kill/ace endings need ball-death "
                      "in/out which no current artifact carries",
        },
        "points": resolutions,
        "census": census(resolutions),
    }
    Path(out_path).write_text(json.dumps(out, indent=1) + "\n",
                              encoding="utf-8")
    return out


# ----------------------------------------------------------------------
# validation (the ONLY reader of GT winner / side_switch fields)
# ----------------------------------------------------------------------

def squad_of_side(side: str, point: int, switches: List[int]) -> str:
    """Side letter -> squad letter given switches AFTER points (GT)."""
    n_sw = sum(1 for s in switches if point > s)
    return side if n_sw % 2 == 0 else OPPONENT[side]


def classify_miss(rec: Dict[str, Any], gt_desc: str) -> str:
    """Why the fault prior was wrong (validate-only, GT description read)."""
    serve = (rec.get("evidence") or {}).get("serve") or {}
    if "pinned_serve_outside_window" in rec["flags"]:
        return ("owner-pinned serve sits OUTSIDE the map window; the "
                "in-window action chain is the ep45 phantom-rally family")
    if serve.get("team_overridden") and \
            rec["evidence"]["terminal_touch"]["frame"] == serve.get("frame"):
        return ("serve_team_misattribution: the rally opener (a far-side "
                "serve) was emitted with the wrong side letter; pass-2 "
                "holds a winner-serves-derived team override this layer "
                "refuses to inherit (GT leakage)")
    d = gt_desc.lower()
    if any(k in d for k in _KILL_RE):
        return ("kill/ace-class ending: the dictated last toucher's side "
                "SCORED; the fault prior flips it because ball-death "
                "in/out is not in the artifacts")
    return ("terminal-touch attribution: the emitted terminal touch's "
            "side letter contradicts the dictated ending (misattributed "
            "net/far contact, or the true terminal touch was never "
            "emitted)")


def validate(out: Dict[str, Any], gt: Dict[str, Any],
             rel: Dict[str, Any]) -> Dict[str, Any]:
    gt_points = {p["point"]: p for p in gt["points"]}
    switches = gt.get("side_switch_after_point", [])
    rows = []
    n_ok = n_decided = 0
    for rec in out["points"]:
        k = rec["point"]
        g = gt_points.get(k)
        pred_side = rec["winner"]
        if g is None or pred_side is None:
            rows.append({"point": k, "pred_side": pred_side,
                         "pred_squad": None,
                         "gt": (g or {}).get("winner"),
                         "ok": False, "desc": (g or {}).get("description", ""),
                         "miss_class": "no decision" if pred_side is None
                         else "no GT"})
            continue
        pred_squad = squad_of_side(pred_side, k, switches)
        ok = pred_squad == g["winner"]
        n_decided += 1
        n_ok += ok
        rows.append({"point": k, "pred_side": pred_side,
                     "pred_squad": pred_squad, "gt": g["winner"], "ok": ok,
                     "desc": g["description"], "confidence": rec["confidence"],
                     "ending_class": rec["ending_class"],
                     "flags": rec["flags"],
                     "terminal": rec["evidence"]["terminal_touch"],
                     "miss_class": None if ok else classify_miss(rec, g["description"])})

    # leakage accounting: what the winner-serves-derived serve-team
    # overrides would have added had they been inherited (they are not)
    by_point = {r["point"]: r for r in rel.get("points", [])}
    leak_gains = []
    for row in rows:
        if row["ok"]:
            continue
        rec = next(p for p in out["points"] if p["point"] == row["point"])
        serve = (rec.get("evidence") or {}).get("serve") or {}
        r = by_point.get(row["point"], {}).get("serve") or {}
        if serve and r.get("team_resolved") and r.get("team_overridden") \
                and serve.get("frame") == rec["evidence"]["terminal_touch"]["frame"]:
            t = r["team_resolved"]
            if t in OPPONENT:
                alt = squad_of_side(OPPONENT[t], row["point"], switches)
                if alt == row["gt"]:
                    leak_gains.append(row["point"])

    acc = n_ok / len(rows) if rows else 0.0
    return {
        "rows": rows,
        "n": len(rows),
        "n_decided": n_decided,
        "n_correct": n_ok,
        "accuracy": round(acc, 4),
        "switches": switches,
        "leakage": {
            "serve_team_overrides_in_layer":
                sum(1 for r in rel.get("points", [])
                    if (r.get("serve") or {}).get("team_overridden")),
            "points_flipped_correct_if_inherited": leak_gains,
            "note": "team_resolved is winner-serves-derived (GT); it is "
                    "never projected into inference",
        },
    }


def write_report(out: Dict[str, Any], val: Dict[str, Any],
                 report_path: str) -> None:
    lines: List[str] = []
    a = lines.append
    a("# Point winner/outcome layer (open point 21.3) -- validation report")
    a("")
    a("Pass-2 hindsight layer over existing JSON artifacts "
      "(`episode_point_map.json` + `match20260920_posegate/pipeline_output.json`"
      " + `serve_relabel.json`); no video decoded, no `src/` change, "
      "entreno-neutral by construction.")
    a("")
    a("## Design (mechanism + why)")
    a("")
    a("1. Fault prior over the terminal touch: the side of the last LIVE "
      "action in the TRUE window loses the point; winner = the other "
      "COURT SIDE (A=near, B=far -- the perception stack's letters).")
    a("2. Live = pipeline actions in-window minus the serve layer's "
      "owner-verdict demotions; the pass-2 serve re-label fixes the "
      "opener's ACTION label only, never its team.")
    a("3. Abstain only structurally (no live touch / unknown terminal "
      "team); doubt that keeps coverage is expressed as confidence=low + "
      "flags (contested attribution, pass-2 override flag on the "
      "terminal, serve never adopted in-stream, pinned serve outside "
      "window).")
    a("4. Ball-death side/in/out -- the owner's sketched "
      "kill-vs-fault disambiguator -- is NOT in any artifact "
      "(pipeline JSON has actions/spikes/game state only); kill/ace "
      "endings therefore stay fault-prior misses instead of guesses.")
    a("5. Spike-record outcomes are reported as evidence only: measured "
      "as a winner rule they score 4/10 on terminal spikes (their team "
      "letter inherits the same net-boundary attribution errors), so no "
      "rule consumes them.")
    a("6. Winner is a SIDE letter, not a squad letter: squads swap "
      "halves at side switches and the switch schedule is GT; the "
      "side->squad mapping below runs in --validate only.")
    a("")
    a("## Validation vs the 33 dictated winners")
    a("")
    a(f"- decided: **{val['n_decided']}/{val['n']}** windows "
      f"(abstain: {val['n'] - val['n_decided']})")
    a(f"- correct (squad-mapped): **{val['n_correct']}/{val['n_decided']}**"
      f" = **{val['accuracy'] * 100:.1f}%** of decided")
    a(f"- side switches applied (GT, validate-only): after points "
      f"{val['switches']}")
    a("")
    a("| P | winner side | -> squad | GT | ok | conf | ending | terminal "
      "touch | miss class |")
    a("|---|---|---|---|---|---|---|---|---|")
    for r in val["rows"]:
        t = r.get("terminal") or {}
        term = (f"{t.get('action')}@f{t.get('frame')} side "
                f"{t.get('team_emitted')}" if t else "-")
        mc = (r.get("miss_class") or "").split(":")[0]
        a(f"| {r['point']} | {r['pred_side'] or '-'} | "
          f"{r['pred_squad'] or '-'} | {r['gt'] or '-'} | "
          f"{'OK' if r['ok'] else 'MISS'} | "
          f"{r.get('confidence', '-')} | "
          f"{r.get('ending_class') or '-'} | {term} | {mc} |")
    a("")
    a("## Miss analysis (every miss explained)")
    a("")
    misses = [r for r in val["rows"] if not r["ok"]]
    for r in misses:
        t = r.get("terminal") or {}
        a(f"- **P{r['point']}** (GT winner {r['gt']}: "
          f"\"{r['desc']}\")")
        a(f"  - signal: terminal touch {t.get('action')}@f{t.get('frame')} "
          f"side {t.get('team_emitted')} -> fault prior gave side "
          f"{r['pred_side']} (squad {r['pred_squad']}); confidence "
          f"{r.get('confidence')}, flags {r.get('flags') or '[]'}.")
        a(f"  - why wrong: {r['miss_class']}.")
    a("")
    a("## GT-leakage accounting")
    a("")
    lk = val["leakage"]
    a(f"- `serve_relabel.json` carries **{lk['serve_team_overrides_in_layer']}"
      f"** winner-serves-derived serve-team overrides "
      f"(`team_resolved`); {lk['note']}.")
    if lk["points_flipped_correct_if_inherited"]:
        a(f"- inheriting them would have flipped "
          f"{lk['points_flipped_correct_if_inherited']} to correct "
          f"({val['n_correct']} -> "
          f"{val['n_correct'] + len(lk['points_flipped_correct_if_inherited'])}"
          f"/{val['n_decided']}) -- that accuracy is GT-bought and is "
          f"NOT shipped.")
    a("- Inference reads inputs through field projections: the map "
      "contributes `point`/`window_frames`/episode spans only; the serve "
      "layer contributes owner-verdict demotions + override FLAGS only; "
      "GT winner/score/side_switch are opened exclusively by "
      "`--validate`.")
    a("")
    a("## Residual risks / next steps")
    a("")
    a("- Ball-death side + in/out is the missing disambiguator for "
      "kill/ace endings; it needs a per-frame ball-track sidecar in "
      "`pipeline_output.json` (or the §6 targeted re-decode escalation), "
      "then the prior becomes a two-sided rule.")
    a("- Terminal-touch side attribution (net/far contacts, AGENTS.md "
      "section 5) is the DOMINANT miss source; a width-band-aware "
      "attribution fix would move more points than any winner-layer "
      "logic.")
    a("- Squad winners need the 21.4 side-switch layer; until then the "
      "artifact speaks side letters and the mapping lives in --validate.")
    a("- `raw_widths.csv` (10-frame-sampled raw detections) was probed "
      "as a death-side source and REJECTED: post-rally ball handling and "
      "static-suspect survivors contaminate the tail (near-uniform "
      "'far:OUT' reads that contradict dictated endings).")
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(out: Dict[str, Any], val: Optional[Dict[str, Any]]) -> None:
    c = out["census"]
    print("=== pass-2 point winners ===")
    print(f"windows: {c['n_points']}  decided: {c['n_winners']}  "
          f"abstain: {c['n_abstain']}")
    for ec, pts in c["by_ending_class"].items():
        if pts:
            print(f"  {ec}: {pts}")
    if c["flagged"]:
        for f, pts in sorted(c["flagged"].items()):
            print(f"  flag {f}: {pts}")
    if val is not None:
        print(f"validation: {val['n_correct']}/{val['n_decided']} correct "
              f"({val['accuracy'] * 100:.1f}%) after side->squad mapping")
        lk = val["leakage"]
        print(f"leakage: {lk['serve_team_overrides_in_layer']} serve-team "
              f"overrides NOT inherited; "
              f"{len(lk['points_flipped_correct_if_inherited'])} points "
              f"would have been GT-bought")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--map", default=DEFAULT_MAP)
    ap.add_argument("--pipeline", default=DEFAULT_PIPELINE)
    ap.add_argument("--game-state-csv", default=DEFAULT_GAME_STATE_CSV)
    ap.add_argument("--serve-relabel", default=DEFAULT_SERVE_RELABEL)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--validate", default=None, metavar="GT",
                    help="match-points GT json; reads winner/"
                         "side_switch_after_point (validation ONLY) and "
                         "writes the report")
    ap.add_argument("--report", default=DEFAULT_REPORT)
    args = ap.parse_args(argv)

    out = run(args.map, args.pipeline, args.serve_relabel, args.out,
              args.game_state_csv)
    val = None
    if args.validate:
        gt = json.loads(Path(args.validate).read_text(encoding="utf-8"))
        rel = json.loads(
            Path(args.serve_relabel).read_text(encoding="utf-8"))
        val = validate(out, gt, rel)
        write_report(out, val, args.report)
    print_summary(out, val)
    print(f"\nwritten: {args.out}")
    if val is not None:
        print(f"written: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
