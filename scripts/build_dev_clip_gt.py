#!/usr/bin/env python3
"""T2 — dev-clip ground truth for resources/video_ari_joan_8_first_points.mp4.

The dev clip (1920x1080, VFR) is a re-encode of the first points of
resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4. This script

  1. locates the clip INSIDE the full match by SEQUENTIAL decode (the match is
     VFR — CAP_PROP_POS_FRAMES seeks are frame-unreliable, see STATUS) and
     matching downscaled grayscale thumbnails. The result is a (possibly
     piecewise) clip<->match frame map, verified at the start, the middle and
     the end of the clip, with the per-check residual reported;
  2. translates the owner-ratified match GT for points 1..8 into CLIP frames:
       * ground_truth/20260920_match_ari_joan_contacts_p1_p8.txt (OWNER GT,
         CONTACT-level: every rally contact of P1..P8 with the player track id
         the owner saw AT THE CONTACT, its side, the action and the point
         outcome — coarse frames (+-10-15f), parsed by parse_contact_gt)
       * ground_truth/20260920_match_serve_anchors.txt  (OWNER GT, serve frames)
       * ground_truth/20260920_match_points.json        (OWNER GT, dictated text
         + mechanically derived winner / side switch, parsed verbatim from
         ground_truth/20260920_match_ari_joan_lost.txt)
  3. attaches SUGGESTIONS from pipeline predictions (episode map / relabel /
     pipeline_output.json). Predictions are NEVER ground truth: every event
     carries source="suggested_from_prediction" plus the artifact it came from,
     and by default only source="owner_gt" events go into
     annotated_frames.actions.events (what scripts/evaluate.py grades).
  4. flags the error events the owner's dictation implies (serve out, set slip
     off the hands, spike into the net) and the side switch;
  5. renders one contact-sheet PNG per point for owner ratification plus a
     point-level summary README.

Output: ground_truth/video_ari_joan_8_first_points_annotations.json
        output/t2_contact_sheet/P<n>.png + README.md

The file is written with "status": "DRAFT_PENDING_OWNER_RATIFICATION" and is
NOT ground truth until the owner ratifies the contact sheets (AGENTS.md:
"GT edits only via owner-ratified contact sheets").

Usage:
    venv/bin/python scripts/build_dev_clip_gt.py                 # full build
    venv/bin/python scripts/build_dev_clip_gt.py --skip-offset   # reuse cache
    venv/bin/python scripts/build_dev_clip_gt.py --no-sheets
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from map_episodes_to_points import parse_serve_anchors  # noqa: E402

CLIP = "resources/video_ari_joan_8_first_points.mp4"
MATCH = "resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4"
MATCH_POINTS = "ground_truth/20260920_match_points.json"
ANCHORS = "ground_truth/20260920_match_serve_anchors.txt"
CONTACTS = "ground_truth/20260920_match_ari_joan_contacts_p1_p8.txt"
EPISODE_MAP = "output/episode_point_map.json"
SERVE_RELABEL = "output/serve_relabel.json"
PIPELINE = "output/match20260920_posegate/pipeline_output.json"
GT_OUT = "ground_truth/video_ari_joan_8_first_points_annotations.json"
SHEET_DIR = "output/t2_contact_sheet"

SOURCE_OWNER = "owner_gt"
SOURCE_SUGGESTED = "suggested_from_prediction"
# a draft (suggested/earlier-pass) event that the owner contacts supersede: it
# is NOT in `events`, it lives in `points[].superseded_draft_events`
SOURCE_SUPERSEDED = "superseded_by_owner_contact"

# --- error-event taxonomy (what the owner's dictation can imply) -----------

ERROR_SERVE_OUT = "serve_out"
ERROR_SERVE_FAULT = "serve_fault"   # serve failed, location not dictated
ERROR_SERVE_NET = "serve_into_net"
ERROR_SET_SLIP = "set_slip_off_hands"
ERROR_SPIKE_NET = "spike_into_net"

# contact-level GT (owner-dictated 2026-09-28)
STATUS_OWNER_DICTATED = "OWNER_DICTATED"
STATUS_DRAFT = "DRAFT_PENDING_OWNER_RATIFICATION"
# Owner frame estimates for these contacts are COARSE (+-10-15f, verbatim in the
# contacts txt header). 15 is the evaluator's own default tolerance and the
# conservative end of the owner's stated range, so it is stored per contact.
CONTACT_FRAME_TOLERANCE = 15

_SERVE_OUT_RE = re.compile(r"serve[^.]*\b(out(side)?|out of)\b", re.I)
_SERVE_FAIL_RE = re.compile(r"\b(fail\w*|fault|error)\b[^.]*\bserve\b", re.I)
_SET_SLIP_RE = re.compile(r"\b(fail\w*|slip\w*|drop\w*)\b[^.]*\bset\b|\bset\b[^.]*\b(slip\w*|off the hands?|fingers?)\b", re.I)
_SPIKE_NET_RE = re.compile(r"\bspike\w*\b[^.]*\b(into|in) the net\b", re.I)


def classify_error(description: str) -> Optional[str]:
    """Error class the owner's dictated description implies (or None).

    `serve_fault` is used when the dictation says the serve failed but not
    WHERE (P4 "P1 fails serve") — it is NOT the same claim as `serve_out`.
    """
    d = description or ""
    if _SERVE_OUT_RE.search(d):
        return ERROR_SERVE_OUT
    if _SERVE_FAIL_RE.search(d):
        return ERROR_SERVE_FAULT
    if _SET_SLIP_RE.search(d):
        return ERROR_SET_SLIP
    if _SPIKE_NET_RE.search(d):
        return ERROR_SPIKE_NET
    return None


# --- offset map (clip frames <-> match frames) -----------------------------


def compute_thumbs(path: str, size: Tuple[int, int] = (32, 18),
                   max_frames: Optional[int] = None) -> np.ndarray:
    """Sequentially decode `path` and return an (n, size_h*size_w) float32 array
    of downscaled grayscale frames. NEVER seek (VFR files are seek-unreliable).
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(f"cannot open video: {path}")
    out: List[np.ndarray] = []
    try:
        while max_frames is None or len(out) < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            gray = cv2.cvtColor(cv2.resize(frame, size, interpolation=cv2.INTER_AREA),
                                cv2.COLOR_BGR2GRAY)
            out.append(gray.astype(np.float32).ravel())
    finally:
        cap.release()
    if not out:
        raise IOError(f"no frames decoded from {path}")
    return np.stack(out)


def _best_offset(clip_row: np.ndarray, match_t: np.ndarray,
                 lo: int, hi: int) -> Tuple[int, float]:
    """Best matching match-frame index for one clip frame inside [lo, hi)."""
    lo = max(0, lo)
    hi = min(len(match_t), hi)
    if hi <= lo:
        return -1, float("inf")
    d = np.abs(match_t[lo:hi] - clip_row).mean(axis=1)
    k = int(d.argmin())
    return lo + k, float(d[k])


def build_offset_map(clip_t: np.ndarray, match_t: np.ndarray,
                     coarse_stride: int = 100, radius: int = 96,
                     drift_tol: int = 2) -> Dict[str, Any]:
    """Locate the clip inside the match from thumbnails.

    Three stages:
      * a coarse GLOBAL scan (every `coarse_stride` clip frames against the
        whole match set) — catches an offset far from 0;
      * a per-block local refinement inside a +/-`radius` search band, giving
        a piecewise map (re-encode drop/dup shows up as the local best offset
        stepping);
      * verification at the start, the middle and the end of the clip: the
        residual at the mapped frame vs. the best residual achievable inside
        the search band.

    Returns a JSON-serialisable dict:
      {"segments": [{"clip_start", "clip_end", "match_offset", "residual"}],
       "drift": bool, "checks": [...], "n_clip_frames", "n_match_frames"}
    """
    n_clip = len(clip_t)
    coarse: List[Tuple[int, int, float]] = []
    for i in range(0, n_clip, coarse_stride):
        j, res = _best_offset(clip_t[i], match_t, 0, len(match_t))
        if j >= 0:
            coarse.append((i, j - i, res))

    if not coarse:
        raise RuntimeError("coarse offset scan found no candidate")
    base = int(np.median([o for _, o, _ in coarse]))
    base_res = float(np.median([r for _, _, r in coarse]))

    # Piecewise refinement: walk the clip in blocks, tracking a running offset.
    block = max(1, coarse_stride // 2)
    segments: List[Dict[str, Any]] = []
    cur_off: Optional[int] = None
    seg_start = 0
    seg_res: List[float] = []
    local_offsets: List[Tuple[int, int]] = []
    for lo in range(0, n_clip, block):
        hi = min(n_clip, lo + block)
        votes: List[int] = []
        for i in range(lo, hi, max(1, (hi - lo) // 3)):
            centre = base if cur_off is None else cur_off
            j, res = _best_offset(clip_t[i], match_t, i + centre - radius, i + centre + radius)
            if j < 0:
                continue
            off = j - i
            votes.append(off)
            seg_res.append(res)
        if not votes:
            continue
        off = int(round(float(np.median(votes))))
        local_offsets.append(((lo + hi) // 2, off))
        if cur_off is None:
            cur_off, seg_start = off, lo
        elif abs(off - cur_off) > drift_tol:
            segments.append({"clip_start": seg_start, "clip_end": lo - 1,
                             "match_offset": cur_off,
                             "residual": round(float(np.mean(seg_res)), 4)})
            cur_off, seg_start, seg_res = off, lo, []
    if cur_off is not None:
        segments.append({"clip_start": seg_start, "clip_end": n_clip - 1,
                         "match_offset": cur_off,
                         "residual": round(float(np.mean(seg_res)) if seg_res else base_res, 4)})

    offsets = [s["match_offset"] for s in segments]
    drift = len(set(offsets)) > 1

    # Verification at start / middle / end (each a +/-radius band).
    checks: List[Dict[str, Any]] = []
    for name, ci in (("start", 0), ("middle", n_clip // 2), ("end", n_clip - 1)):
        seg = segment_for(segments, ci)
        mapped = ci + seg["match_offset"] if seg else None
        best_j, best_res = _best_offset(clip_t[ci], match_t,
                                        ci - radius, ci + radius)
        res_at_map = (float(np.abs(match_t[mapped] - clip_t[ci]).mean())
                      if mapped is not None and 0 <= mapped < len(match_t) else None)
        checks.append({
            "check": name, "clip_frame": ci,
            "mapped_match_frame": mapped,
            "residual_at_mapped": None if res_at_map is None else round(res_at_map, 4),
            "best_residual_in_band": round(best_res, 4),
            "best_offset_in_band": None if best_j < 0 else best_j - ci,
            "ok": bool(res_at_map is not None
                       and res_at_map <= max(0.5, 2.0 * best_res)
                       and (best_j - ci) == (seg["match_offset"] if seg else None)),
        })
    return {
        "method": "sequential decode + downscaled grayscale abs-difference",
        "vfr_safe": True,
        "n_clip_frames": n_clip,
        "n_match_frames": len(match_t),
        "coarse_stride": coarse_stride,
        "search_radius": radius,
        "base_offset": base,
        "base_residual": round(base_res, 4),
        "local_offsets": [[int(i), int(o)] for i, o in local_offsets],
        "drift": drift,
        "segments": segments,
        "checks": checks,
    }


def segment_for(segments: Sequence[Dict[str, Any]], clip_frame: int) -> Optional[Dict[str, Any]]:
    for s in segments:
        if s["clip_start"] <= clip_frame <= s["clip_end"]:
            return s
    return segments[-1] if segments else None


def clip_to_match(offset_map: Dict[str, Any], clip_frame: int) -> Optional[int]:
    seg = segment_for(offset_map["segments"], clip_frame)
    return None if seg is None else clip_frame + seg["match_offset"]


def match_to_clip(offset_map: Dict[str, Any], match_frame: int) -> Optional[int]:
    """Inverse map. Ambiguous when segments overlap after the inverse; the
    closest segment (lowest |clip_start|) wins and the caller is told via
    `offset_map["drift"]`."""
    best: Optional[int] = None
    best_cost: Optional[int] = None
    for s in offset_map["segments"]:
        clip_frame = match_frame - s["match_offset"]
        if not (s["clip_start"] <= clip_frame <= s["clip_end"]):
            continue
        cost = abs(clip_frame)
        if best_cost is None or cost < best_cost:
            best, best_cost = clip_frame, cost
    return best


# --- contact-level GT parser (owner-dictated, coarse frames) --------------
#
# File format (ground_truth/20260920_match_ari_joan_contacts_p1_p8.txt), now
# carrying the WHOLE match P1..P33 in TWO owner dialects:
#
#   dialect A (P1..P8, owner 2026-09-28):
#       <side> team|side P<k> <action> at f<frame>[  <- verbatim owner note]
#   dialect B (P9..P33, owner 2026-09-30, documented in ground_truth/README):
#       NT|FT <action> [<frame> [P<k>]][ <- owner note]   (NT = near, FT = far)
#       f|bare <frame> NT|FT ...                          (frame-first form)
#       "FT is close to a dig in f10180 ..." is PROSE, not a contact (open
#       point 25: the owner says that ball must NOT count as a dig).
#
# with `side` in {near, far} = the court half the player stood on at the
# moment of the contact, "near = Team A at match start, far = Team B at match
# start" and `Side switch (near team now is far team)` marker lines inverting
# that mapping for the LATER points (parity matters — see _side_to_team). The
# player number is the PIPELINE TRACK id valid at the contact frame (the owner
# changes it when the track is lost), and it is OPTIONAL — several dictated
# contacts name no player at all.

_CONTACT_POINT_RE = re.compile(r"^\s*Point\s+(\d+)\s*$", re.I)
_CONTACT_SWITCH_RE = re.compile(r"^\s*side\s+switch\b\s*(\(.*\))?\s*$", re.I)
_CONTACT_SIDE_RE = re.compile(r"^\s*(near|far)\s+(team|side)\b(.*)$", re.I)
_CONTACT_FRAME_RE = re.compile(r"\bf\s*(\d+)\b", re.I)
_CONTACT_PLAYER_RE = re.compile(r"\bP\s*(\d+)\b")

# --- dialect B: the owner's P9+ notation (appended 2026-09-30) -------------
# Separate grammar so the P1..P8 dialect-A output stays byte-identical.
_CONTACT_SIDE_B_RE = re.compile(r"^\s*(NT|FT)\b(.*)$", re.I)
_CONTACT_FRAME_FIRST_B_RE = re.compile(r"^\s*f?\s*(\d{2,6})\s+(NT|FT)\b(.*)$", re.I)
_CONTACT_BARE_FRAME_RE = re.compile(r"(?<!\w)(\d{2,6})(?!\w)")
_BUMP_SET_RE = re.compile(r"\bbump\w*\s+sets?\b", re.I)
_BUMP_PASS_RE = re.compile(r"\bbump\w*\s+pass(?:es|ing|ed)?\s*(?:the\s+)?(?:ball\b)?",
                           re.I)
#: words that may legitimately sit between the side abbreviation and the verb
#: ("upper hand dig", "over hand dig", "hard spike") — anything ELSE in that
#: slot means the side word started a prose sentence, not a contact.
_DIALECT_B_MODIFIERS = {"upper", "over", "hand", "overhand", "hard",
                        "accelerated", "rainbow", "low", "high"}
_CONTACT_BUT_ITS_RE = re.compile(r"\bbut\s+its?\s+P\s*(\d+)\b", re.I)
_CONTACT_ATTRIB_PREFIX_RE = re.compile(r"(?:missatr\w*|attribut\w*)\s+(?:to\s+)?$",
                                       re.I)
#: a side+frame line with NO action keyword is only accepted as a contact when
#: the owner's wording says it was a touch (P30 f23545); anything else is a
#: malformed line, not an excuse to emit an unlabelled contact.
_CONTACT_UNSPECIFIED_TOUCH_RE = re.compile(r"\btouch\w*\b", re.I)

# First occurrence in the line wins (the owner writes the dominant gesture
# first: "set f3131 overpasses" -> set, "bump overpass at f1543" -> overpass).
# Dialect B adds the owner's attack variants: `poke` is the soft attack the
# pipeline scores as a spike, and `returns` a serve reception -> dig.
_CONTACT_ACTIONS: Tuple[Tuple[str, re.Pattern], ...] = (
    ("serve", re.compile(r"\bserves?\b|\bserving\b", re.I)),
    ("dig", re.compile(r"\bdigs?\b|\bdigging\b|\bdigged\b|\breturns?\b", re.I)),
    ("set", re.compile(r"\bsets?\b|\bsetting\b", re.I)),
    ("overpass", re.compile(r"\boverpass\w*\b|\bbump\w*\b", re.I)),
    ("spike", re.compile(r"\bspikes?\b|\bspiking\b|\bspiked\b|\bpokes?\b|\bpoked\b",
                          re.I)),
)
# "overpass/bump" is ONE action in the owner's vocabulary; the pipeline label
# for a bump pass is `overpass`.
_CONTACT_ALIASES = {"bump": "overpass", "passes the ball": "overpass"}

_CONTACT_SERVE_WIDE_RE = re.compile(r"\bwide\b|\bout of bounds?\b|\boutside\b", re.I)
_CONTACT_SERVE_NET_RE = re.compile(r"\b(into|in) the net\b", re.I)
_CONTACT_SET_SLIP_RE = re.compile(r"\bslip\w*\b|\bfalls? (off )?the hands?\b|\bloses point\b",
                                  re.I)
_CONTACT_ACCEL_RE = re.compile(r"\baccelerated\b|\bacceleration\b|\bdriven\b|\bhard\b",
                               re.I)
#: owner wording for a SOFT attack (pipeline spike_type `touch`). Deliberately
#: requires `poke` or the bigram "spike touch": a bare "touch" is also the
#: owner's possession counter ("poke on second touch") and a verb ("touches
#: ball"), so it must not be read as intensity on its own.
_CONTACT_SOFT_RE = re.compile(r"\bpoke\w*\b|\bspikes?\s+touch\b|\brainbow\b", re.I)
#: owner wording that states a spike went OUT (never inferred from the score).
_CONTACT_SPIKE_OUT_RE = re.compile(
    r"\bwide\b|\bout of (the )?court\b|\bout of bounds?\b|\boutside\b|"
    r"\bloses? (the )?point\b|\bloses? match\b", re.I)
_CONTACT_SCORES_RE = re.compile(r"\bscores\b|\bwins? (the )?point\b", re.I)
# "set f3131 overpasses" / "dig bump overpass at f1543": the line names a
# set/dig GESTURE and states the ball was sent OVER. In the pipeline taxonomy
# (src/recognition ActionContextResolver) a ball sent over without an attack is
# an OVERPASS, whatever the gesture was -- so the gesture keyword is kept
# separately and the action becomes `overpass` (flagged for owner ratification).
_CONTACT_OVERPASS_RE = re.compile(r"\boverpass\w*\b", re.I)
_CONTACT_GESTURE_RE: Tuple[Tuple[str, re.Pattern], ...] = (
    ("set", re.compile(r"\bsets?\b|\bsetting\b", re.I)),
    ("dig", re.compile(r"\bdigs?\b|\bdigging\b|\bdigged\b", re.I)),
)

OVERPASS_FLAG_TEMPLATE = (
    "OWNER INTERPRETATION (needs ratification): the owner line states the ball "
    "went over ('overpass'), so the pipeline taxonomy "
    "(ActionContextResolver: overpass = ball sent over WITHOUT an attack) makes "
    "this a final_action='overpass' with gesture='{gesture}' -- the gesture is "
    "kept as {gesture!r} because that is the touch the owner described. Raw "
    "wording: {raw}"
)

# Owner RATIFICATIONS of the flags above (owner decisions, 2026-09-29). Keyed
# by (point, match_frame, gesture) so the rule stays generic: adding a row here
# is all it takes to ratify a future flagged contact, and an UNRATIFIED flag
# keeps its "needs ratification" wording. Nothing here invents GT - it records
# what the owner said about a flag the generator already raised.
OWNER_RATIFICATIONS = {
    (6, 3131, "set"): {
        "owner_ratified": True,
        "date": "2026-09-29",
        "statement": "it's an overpass",
        "channel": "owner decision recorded in the T5 session",
    },
}

# The owner's own blanket rule, stated verbatim in the footer of the contact
# dictation (2026-09-30): "All actions that overpass label as overpass".
# It ratifies every dialect-B overpass flag without inventing anything; a
# point/frame-specific OWNER_RATIFICATIONS row (like P6 f3131) still wins.
OVERPASS_CONVENTION = {
    "owner_ratified": True,
    "date": "2026-09-30",
    "statement": "All actions that overpass label as overpass",
    "source": "owner footer, "
              "ground_truth/20260920_match_ari_joan_contacts_p1_p8.txt",
}


def _ratification(point: Optional[int], frame: Optional[int],
                  gesture: Optional[str]) -> Optional[Dict[str, Any]]:
    """The owner ratification for one flagged contact, or None."""
    if point is None or frame is None:
        return None
    return OWNER_RATIFICATIONS.get((int(point), int(frame), gesture))



def _contact_interpretation(action: str, token: str, remainder: str,
                            raw: str, point: Optional[int] = None,
                            frame: Optional[int] = None,
                            dialect: str = "A"
                            ) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
    """(final_action, gesture, owner_interpretation_flag) for one contact line.

    A set/dig keyword co-occurring with "overpass" wording is a cross-net send
    without an attack => `overpass`, with the keyword kept as the gesture.
    Everything else is returned unchanged. Dialect-B flags are ratified by the
    owner's blanket footer rule (OVERPASS_CONVENTION) unless a specific
    OWNER_RATIFICATIONS row applies.
    """
    if not _CONTACT_OVERPASS_RE.search(remainder or ""):
        return action, None, None
    gesture = None
    for name, rx in _CONTACT_GESTURE_RE:
        if rx.search(remainder or ""):
            gesture = name
            break
    if gesture is None:
        # no set/dig keyword: the owner's own vocabulary already says it
        # ("bump overpass"), so the action stands unchanged
        return action, None, None
    flag = {"rule": "overpass_wording_with_gesture_keyword",
            "raw_action_label": action,
            "gesture": gesture,
            "why": OVERPASS_FLAG_TEMPLATE.format(gesture=gesture, raw=raw)}
    rat = _ratification(point, frame, gesture)
    if rat is None and dialect == "B":
        rat = OVERPASS_CONVENTION
    if rat is not None:
        flag["owner_ratified"] = True
        flag["owner_ratification_date"] = rat["date"]
        flag["owner_ratification_statement"] = rat["statement"]
        flag["why"] = (
            "OWNER INTERPRETATION (RATIFIED {date}, owner: \"{stmt}\"): the owner "
            "line states the ball went over ('overpass'), and the pipeline "
            "taxonomy (ActionContextResolver: overpass = ball sent over WITHOUT "
            "an attack) agrees, so final_action='overpass' with "
            "gesture='{gesture}'. See OWNER_RATIFICATIONS for the owner "
            "ratification of this flag. Raw wording: {raw}"
        ).format(date=rat["date"], stmt=rat["statement"], gesture=gesture, raw=raw)
    return "overpass", gesture, flag


def _contact_action(remainder: str) -> Tuple[Optional[str], Optional[str]]:
    """(canonical action, matched verbatim token) from a contact line body."""
    best: Optional[Tuple[int, str, str]] = None
    for action, rx in _CONTACT_ACTIONS:
        m = rx.search(remainder)
        if m and (best is None or m.start() < best[0]):
            token = m.group(0).lower().strip()
            best = (m.start(), action, token)
    if best is None:
        return None, None
    _, action, token = best
    return _CONTACT_ALIASES.get(token, action), token


def _contact_error(action: str, note: str) -> Optional[Dict[str, Any]]:
    """Error the dictated CONTACT text implies (owner wording, no invention)."""
    n = note or ""
    if action == "serve":
        if _CONTACT_SERVE_NET_RE.search(n):
            return {"type": ERROR_SERVE_NET}
        if _CONTACT_SERVE_WIDE_RE.search(n):
            return {"type": ERROR_SERVE_OUT}
    if action == "set" and _CONTACT_SET_SLIP_RE.search(n):
        return {"type": ERROR_SET_SLIP}
    if action == "spike" and _CONTACT_SERVE_NET_RE.search(n):
        return {"type": ERROR_SPIKE_NET}
    return None


def _contact_outcome(action: str, note: str) -> Optional[str]:
    """Spike outcome only when the dictation states it.

    "into the net" and the owner's out-of-court wording ("goes wide", "out of
    court", "loses point") are STATED outcomes, never inferred from the score;
    anything the dictation does not state stays None.
    """
    if action != "spike":
        return None
    n = note or ""
    if _CONTACT_SERVE_NET_RE.search(n):
        return "out"
    if _CONTACT_SCORES_RE.search(n):
        return "kill"
    if _CONTACT_SPIKE_OUT_RE.search(n):
        return "out"
    return None


# --- dialect-B line grammar -------------------------------------------------

def _join_continuations(raw_lines: Sequence[str]) -> List[Tuple[int, str]]:
    """Physical lines -> logical lines, joining the owner's line wraps.

    The owner's P20 dictation wraps inside a parenthetical across two physical
    lines (an unbalanced '(' at the end of one); joining while parens are
    unbalanced is the only wrap shape in the file, checked by
    tests/test_build_dev_clip_gt.py.
    """
    out: List[Tuple[int, str]] = []
    for i, raw in enumerate(raw_lines, start=1):
        if out and out[-1][1].count("(") > out[-1][1].count(")"):
            out[-1] = (out[-1][0], out[-1][1].rstrip() + " " + raw.strip())
        else:
            out.append((i, raw))
    return out


def _paren_intervals(text: str) -> List[Tuple[int, int]]:
    """Character intervals INSIDE parentheses — kept verbatim, never stripped."""
    spans: List[Tuple[int, int]] = []
    depth = start = 0
    for i, ch in enumerate(text):
        if ch == "(":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
            if depth == 0:
                spans.append((start, i))
    if depth:                       # unbalanced: protect the rest
        spans.append((start, len(text)))
    return spans


def _span_inside(spans: Sequence[Tuple[int, int]], span: Tuple[int, int]) -> bool:
    a, b = span
    return any(s < b and a < e for s, e in spans)


def _blank_spans(text: str, spans: Sequence[Tuple[int, int]]) -> str:
    chars = list(text)
    for a, b in spans:
        for i in range(max(0, a), min(b, len(chars))):
            chars[i] = " "
    return "".join(chars)


def _span_adjacent(a: Tuple[int, int], b: Tuple[int, int], text: str) -> bool:
    lo, hi = (a[1], b[0]) if a[1] <= b[0] else (b[1], a[0])
    return text[lo:hi].strip() == ""


def _dialect_b_action(body: str) -> Optional[Tuple[str, str, Tuple[int, int]]]:
    """(canonical action, verbatim token, span) for one dialect-B line body.

    "bump set" is a SET (the bump names the technique); "bump pass(es)" is an
    OVERPASS; otherwise the earliest action keyword wins, exactly as in
    dialect A.
    """
    m = _BUMP_SET_RE.search(body)
    if m:
        return "set", m.group(0).lower(), m.span()
    m = _BUMP_PASS_RE.search(body)
    if m:
        return "overpass", m.group(0).lower(), m.span()
    best: Optional[Tuple[int, str, str, Tuple[int, int]]] = None
    for action, rx in _CONTACT_ACTIONS:
        mm = rx.search(body)
        if mm and (best is None or mm.start() < best[0]):
            token = mm.group(0).lower().strip()
            best = (mm.start(), action, token, mm.span())
    if best is None:
        return None
    _, action, token, span = best
    return _CONTACT_ALIASES.get(token, action), token, span


def _dialect_b_player(body: str) -> Tuple[Optional[int], Optional[Tuple[int, int]]]:
    """(track id, span-to-strip) for one dialect-B body.

    The owner corrects a mis-attribution inside the note ("missatributed to P2,
    but its P4"): the TRUE track id is the one after "but its", and the whole
    correction stays verbatim in the note (span None). A P<k> inside an
    attribution clause ("to P2") is the pipeline's WRONG id, never the GT.
    """
    m = _CONTACT_BUT_ITS_RE.search(body)
    if m:
        return int(m.group(1)), None
    for pm in _CONTACT_PLAYER_RE.finditer(body):
        if _CONTACT_ATTRIB_PREFIX_RE.search(body[:pm.start()][-40:]):
            continue
        return int(pm.group(1)), pm.span()
    return None, None


def _dialect_b_note(body: str, spans: Sequence[Tuple[int, int]]) -> Optional[str]:
    """Owner note = the body with the structural tokens blanked.

    Parenthetical text is protected by the caller (it is never in `spans`), so
    every owner parenthetical survives verbatim; only whitespace and leading /
    trailing connective punctuation are normalised.
    """
    text = _blank_spans(body, spans)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:it|and|that|at)\s+", "", text, flags=re.I)
    return text.strip(" ,;:->") or None


def _dialect_b_contact(side_word: str, body: str, raw: str, line_no: int,
                       point: int, switches_before: int,
                       explicit_frame: Optional[int] = None
                       ) -> Tuple[Optional[Dict[str, Any]], Optional[str], str]:
    """One dialect-B line -> (contact, reason, kind), kind in {note, unparsed}.

    contact=None means the line was refused: `kind` says whether it is owner
    prose (a note, deliberately not a contact — e.g. P15 f10180, open point 25)
    or a malformed contact line.
    """
    side = "near" if side_word.upper() == "NT" else "far"
    action = _dialect_b_action(body)
    if action is not None:
        # the action must sit in the structural slot; only the known technique
        # modifiers may precede it. "FT is close to a dig in f10180 ..." fails
        # here on "is" and is kept as a note (never a dig contact).
        pre = re.sub(r"^\s*P\s*\d+\b", " ", body[:action[2][0]])
        words = re.findall(r"[A-Za-z]+", pre)
        if any(w.lower() not in _DIALECT_B_MODIFIERS for w in words):
            return None, ("side word followed by a sentence, not a contact "
                          "(owner prose)"), "note"
    frames = [int(x) for x in _CONTACT_FRAME_RE.findall(body)]
    if explicit_frame is not None:
        frames = [explicit_frame] + [f for f in frames if f != explicit_frame]
    bare_span: Optional[Tuple[int, int]] = None
    if not frames:
        bm = _CONTACT_BARE_FRAME_RE.search(body)
        if bm:
            frames, bare_span = [int(bm.group(1))], bm.span()
    if action is None and not frames:
        return None, "owner prose (no action and no frame)", "note"
    if not frames:
        return None, "contact line without any f<frame>", "unparsed"
    if action is None and not _CONTACT_UNSPECIFIED_TOUCH_RE.search(body):
        return None, "contact line with no known action", "unparsed"

    final_action: Optional[str] = None
    gesture: Optional[str] = None
    flag: Optional[Dict[str, Any]] = None
    action_span: Optional[Tuple[int, int]] = None
    action_token: Optional[str] = None
    if action is not None:
        final_action, action_token, action_span = action
        final_action, gesture, flag = _contact_interpretation(
            final_action, action_token or "", body, raw.strip(),
            point=point, frame=frames[0], dialect="B")
    player_id, player_span = _dialect_b_player(body)

    protected = _paren_intervals(body)
    remove: List[Tuple[int, int]] = []

    def _rm(span: Optional[Tuple[int, int]]) -> None:
        if span and not _span_inside(protected, span) and span not in remove:
            remove.append(span)

    _rm(action_span)
    for fm in _CONTACT_FRAME_RE.finditer(body):
        _rm(fm.span())
        if player_span and _span_adjacent(player_span, fm.span(), body):
            _rm(player_span)
    _rm(bare_span)
    if action_span is not None and player_span and \
            _span_adjacent(player_span, action_span, body):
        _rm(player_span)
    note = _dialect_b_note(body, remove)

    contact: Dict[str, Any] = {
        "point": point,
        "side": side,
        "side_word": side_word.lower(),
        "team": _side_to_team(side, switches_before),
        "player_id": player_id,
        "action": final_action,
        "action_token": action_token,
        "gesture": gesture,
        "owner_interpretation_flag": flag,
        "match_frame": frames[0],
        "extra_match_frames": frames[1:],
        "note": note,
        "frame_tolerance": CONTACT_FRAME_TOLERANCE,
        "spike_type": ("hard" if final_action == "spike"
                       and _CONTACT_ACCEL_RE.search(body)
                       else "touch" if final_action == "spike"
                       and _CONTACT_SOFT_RE.search(body) else None),
        "outcome": _contact_outcome(final_action, body),
        "error": _contact_error(final_action, body),
        "raw": raw.strip(),
        "raw_line_no": line_no,
    }
    if final_action is None:
        # the owner described a touch without naming an action (P30 f23545);
        # the contact is still GT, the label is honestly left unspecified
        contact["owner_action_unspecified"] = True
    return contact, None, "contact"


def parse_contact_gt(path: str) -> Dict[str, Any]:
    """Parse the owner-dictated contact-level GT txt (dialects A and B).

    Returns
        {"path", "frame_tolerance", "points": [{"point", "side_switch_after",
         "contacts": [...]}], "unparsed": [{"line", "line_no", "reason"}],
         "notes": [{"line", "line_no", "reason"}]}

    Contacts carry the OWNER fields verbatim (side word, optional track id,
    free-text note, every frame the line mentions) alongside the derived
    team/action. Frames are MATCH frames (same numbering as the serve anchors).
    `unparsed` is for malformed/contact-like lines; `notes` collects the
    owner's prose (legend, note blocks, sentences that merely start with a side
    word) so nothing is silently dropped.
    """
    raw_lines = Path(path).read_text(encoding="utf-8").splitlines()
    logical = _join_continuations(raw_lines)
    points: List[Dict[str, Any]] = []
    unparsed: List[Dict[str, Any]] = []
    notes: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    switches = 0

    def _record(raw: str, line_no: int, reason: str, kind: str) -> None:
        entry = {"line": raw, "line_no": line_no, "reason": reason}
        (notes if kind == "note" else unparsed).append(entry)

    for line_no, raw in logical:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _CONTACT_POINT_RE.match(line)
        if m:
            k = int(m.group(1))
            if cur is not None and cur["point"] == k and not cur["contacts"]:
                # the dictation carries a duplicated empty "Point 21" header:
                # re-open the same point instead of emitting it twice
                continue
            cur = {"point": k, "side_switch_after": False, "contacts": []}
            points.append(cur)
            continue
        m = _CONTACT_SWITCH_RE.match(line)
        if m:
            # the marker closes the point it follows: every LATER point is
            # played on switched halves (parity — see _side_to_team)
            if cur is not None:
                cur["side_switch_after"] = True
            switches += 1
            continue
        if cur is None:
            _record(raw, line_no,
                    "before the first 'Point <k>' header (verbatim preamble)",
                    "unparsed")
            continue
        m = _CONTACT_SIDE_RE.match(line)
        if m:
            side = m.group(1).lower()
            remainder = m.group(3).strip()
            frames = [int(x) for x in _CONTACT_FRAME_RE.findall(remainder)]
            if not frames:
                unparsed.append({"line": raw, "line_no": line_no,
                                 "reason": "contact line without any f<frame>"})
                continue
            action, token = _contact_action(remainder)
            if action is None:
                unparsed.append({"line": raw, "line_no": line_no,
                                 "reason": "contact line with no known action"})
                continue
            final_action, gesture, flag = _contact_interpretation(
                action, token or "", remainder, raw.strip(),
                point=cur["point"], frame=frames[0])
            pm = _CONTACT_PLAYER_RE.search(remainder)
            # note = the free text AFTER the first dictated frame
            tail = remainder[_CONTACT_FRAME_RE.search(remainder).end():]
            note = tail.strip(" ,->:;")
            contact = {
                "point": cur["point"],
                "side": side,
                "side_word": f"{m.group(1).lower()} {m.group(2).lower()}",
                "team": _side_to_team(side, switches),
                "player_id": int(pm.group(1)) if pm else None,
                "action": final_action,
                "action_token": token,
                "gesture": gesture,
                "owner_interpretation_flag": flag,
                "match_frame": frames[0],
                "extra_match_frames": frames[1:],
                "note": note or None,
                "frame_tolerance": CONTACT_FRAME_TOLERANCE,
                # the ERROR / outcome wording can sit BEFORE the frame token
                # ("spike accelerated into the net f345"), so the whole line
                # body is classified, not just the trailing note.
                "spike_type": ("hard" if final_action == "spike"
                               and _CONTACT_ACCEL_RE.search(remainder)
                               else "touch" if final_action == "spike"
                               and _CONTACT_SOFT_RE.search(remainder) else None),
                "outcome": _contact_outcome(final_action, remainder),
                "error": _contact_error(final_action, remainder),
                "raw": raw.strip(),
                "raw_line_no": line_no,
            }
            cur["contacts"].append(contact)
            continue
        m = _CONTACT_SIDE_B_RE.match(line)
        if m:
            contact, reason, kind = _dialect_b_contact(
                m.group(1), m.group(2).strip(), raw, line_no, cur["point"], switches)
            if contact is not None:
                cur["contacts"].append(contact)
            else:
                _record(raw, line_no, reason or "unclassified line", kind)
            continue
        m = _CONTACT_FRAME_FIRST_B_RE.match(line)
        if m:
            contact, reason, kind = _dialect_b_contact(
                m.group(2), m.group(3).strip(), raw, line_no, cur["point"], switches,
                explicit_frame=int(m.group(1)))
            if contact is not None:
                cur["contacts"].append(contact)
            else:
                _record(raw, line_no, reason or "unclassified line", kind)
            continue
        _record(raw, line_no, "owner prose / note (not a contact line)", "note")

    return {"path": str(path), "frame_tolerance": CONTACT_FRAME_TOLERANCE,
            "points": points, "unparsed": unparsed, "notes": notes}


def possession_touch_numbers(contacts: Sequence[Dict[str, Any]]) -> List[int]:
    """Per-POSSESSION touch numbers for one point's contacts (GT convention,
    ground_truth/README.md / video_entreno_3_annotations.json): the serve is
    touch 1, and every time the ball crosses to the other team the count
    restarts at 1 -- so the receiving team's rally reads dig 1, set 2,
    spike/overpass 3. NOT a rally-global counter.

    A team error that ends the rally (spike into the net, serve out) still ends
    the possession there; nothing is invented for contacts that follow it.
    """
    out: List[int] = []
    prev_team: Optional[str] = None
    n = 0
    for c in contacts:
        team = c.get("team")
        n = 1 if team != prev_team else n + 1
        out.append(n)
        prev_team = team
    return out


def _side_to_team(side: str, switches_before: int) -> str:
    """Owner header convention: near = Team A at match start, far = Team B at
    match start; every `Side switch` marker inverts the mapping for the LATER
    points (squads are fixed, only their half changes). Parity matters: after an
    EVEN number of switches — the 4 of the 20260920 match — `near` is Team A
    again, so a single "last switch frame" comparison is not enough."""
    near_is_a = (int(switches_before) % 2 == 0)
    if side == "near":
        return "A" if near_is_a else "B"
    return "B" if near_is_a else "A"


def contact_events(clip_frames: int, offset_map: Dict[str, Any],
                   contacts_doc: Dict[str, Any],
                   point_range: Sequence[int]) -> Tuple[List[Dict[str, Any]],
                                                         List[Dict[str, Any]]]:
    """Translate owner contacts into CLIP-frame events in the per-contact format
    scripts/evaluate.py grades (frame / final_action / player_id / player_team /
    team_in_possession / touch_number), keeping the raw owner fields."""
    events: List[Dict[str, Any]] = []
    unmappable: List[Dict[str, Any]] = []
    wanted = set(point_range)
    for pdoc in contacts_doc.get("points", []):
        k = int(pdoc["point"])
        if wanted and k not in wanted:
            continue
        for i, (c, touch) in enumerate(
                zip(pdoc["contacts"], possession_touch_numbers(pdoc["contacts"])), start=1):
            clip_frame = match_to_clip(offset_map, int(c["match_frame"]))
            if clip_frame is None or not (0 <= clip_frame < clip_frames):
                unmappable.append({"point": k, "match_frame": c["match_frame"],
                                   "raw": c["raw"]})
                continue
            ev = {
                "frame": clip_frame,
                "match_frame": int(c["match_frame"]),
                "final_action": c["action"],
                "action": c["action"],
                "player_id": c["player_id"],
                "player_team": c["team"],
                "team_in_possession": c["team"],
                "touch_number": touch,
                "point": k,
                "source": SOURCE_OWNER,
                "status": STATUS_OWNER_DICTATED,
                "source_detail": contacts_doc.get("path", CONTACTS),
                "frame_tolerance": c["frame_tolerance"],
                "frame_tolerance_note": "owner frame estimates are COARSE "
                                        "(+-10-15f, contacts txt header); the "
                                        "frame is NOT frame-exact",
                # verbatim owner fields
                "owner_side": c["side"],
                "owner_side_word": c["side_word"],
                "owner_track_id": c["player_id"],
                "owner_note": c["note"],
                "owner_raw": c["raw"],
                "owner_extra_match_frames": c["extra_match_frames"] or None,
                "error": ({"type": c["error"]["type"], "team": c["team"],
                           "text": c["note"]} if c["error"] else None),
            }
            if c.get("gesture"):
                ev["gesture"] = c["gesture"]
            if c.get("owner_interpretation_flag"):
                ev["owner_interpretation_flag"] = c["owner_interpretation_flag"]
            if c.get("owner_action_unspecified"):
                ev["owner_action_unspecified"] = True
            if c["spike_type"]:
                ev["spike_type"] = c["spike_type"]
            if c["outcome"]:
                ev["outcome"] = c["outcome"]
            events.append(ev)
    events.sort(key=lambda e: e["frame"])
    return events, unmappable


# --- GT assembly -----------------------------------------------------------


def load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _point_view(points: List[Dict[str, Any]], k: int) -> Optional[Dict[str, Any]]:
    for p in points:
        if int(p.get("point", -1)) == k:
            return p
    return None


def _suggested_window(view: Dict[str, Any], anchors: Dict[str, Any],
                      confirmed: List[Dict[str, Any]]) -> Tuple[Optional[Tuple[int, int]], str]:
    """Clip-local point window suggested by PREDICTIONS (never GT)."""
    anchor = anchors.get("frame")
    if anchor is not None:
        for seg in confirmed:
            if seg["start_frame"] <= anchor <= seg["end_frame"]:
                return (seg["start_frame"], seg["end_frame"]), "game_state_confirmed_segment"
    # No confirmed segment contains the anchor (P2/P4 class: the rally never
    # gathered) — fall back to the map's serve-emission window.
    win = view.get("window_frames")
    if win:
        return (int(win[0]), int(win[1])), "episode_map_emission_window"
    return None, "none"


def build_points(clip_frames: int, offset_map: Dict[str, Any],
                 match_points: Dict[str, Any], anchors_doc: Dict[str, Any],
                 ep_map: Optional[Dict[str, Any]], relabel: Optional[Dict[str, Any]],
                 pipeline: Optional[Dict[str, Any]],
                 point_range: Sequence[int],
                 contacts_doc: Optional[Dict[str, Any]] = None,
                 ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (points, events). Frames are CLIP-local; the match frame of every
    event is carried alongside as `match_frame`."""
    anchor_pts: Dict[int, Dict[str, Any]] = anchors_doc["points"]
    false_frames = {int(f["frame"]) for f in anchors_doc.get("false", [])}
    offgame = anchors_doc.get("offgame", [])

    gt_points = {int(p["point"]): p for p in match_points["points"]}
    view_by_point = {int(v["point"]): v for v in (ep_map or {}).get("points", [])}
    relabel_by_point = {int(v["point"]): v for v in (relabel or {}).get("points", [])}
    confirmed = (pipeline or {}).get("game_state", {}).get("points", [])
    actions = (pipeline or {}).get("actions", [])
    pass2_by_frame = {int(a["frame_number"]): a for a in (relabel or {}).get("actions_pass2", [])}

    def is_offgame(frame: int) -> bool:
        return any(r["start"] <= frame <= r["end"] for r in offgame)

    points: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    contacts_by_point: Dict[int, List[Dict[str, Any]]] = {}
    if contacts_doc is not None:
        contacts_by_point = {int(p["point"]): p["contacts"]
                             for p in contacts_doc.get("points", [])}
    unmappable: List[Dict[str, Any]] = []

    for k in point_range:
        gtp = gt_points.get(k)
        view = view_by_point.get(k, {})
        rel = relabel_by_point.get(k, {})
        anchor = anchor_pts.get(k)
        description = (gtp or {}).get("description", "")
        winner = (gtp or {}).get("winner")
        serve_squad = view.get("serve_squad")
        serve_side = (anchor or {}).get("side")
        err_class = classify_error(description)
        losing = {"A", "B"} - {winner} if winner else set()

        # --- owner GT, CONTACT level (the dictated contacts supersede the serve
        # anchor for the same moment: they carry the track id, side and action)
        cevs, unm = contact_events(
            clip_frames, offset_map,
            {"path": (contacts_doc or {}).get("path", CONTACTS),
             "points": [{"point": k, "contacts": contacts_by_point.get(k, [])}]},
            [k])
        unmappable.extend(unm)
        owner_events: List[Dict[str, Any]] = list(cevs)

        # --- owner GT: the serve moment (frame anchor, coarse owner estimate).
        # Skipped when the contact-level dictation already anchors that serve.
        if anchor is not None and not any(e["final_action"] == "serve"
                                          for e in owner_events):
            clip_frame = match_to_clip(offset_map, int(anchor["frame"]))
            if clip_frame is not None and 0 <= clip_frame < clip_frames:
                ev: Dict[str, Any] = {
                    "frame": clip_frame,
                    "match_frame": int(anchor["frame"]),
                    "final_action": "serve",
                    "action": "serve",
                    "player_id": None,
                    "player_team": serve_squad,
                    "team_in_possession": serve_squad,
                    "touch_number": 1,
                    "point": k,
                    "serve_side": serve_side,
                    "source": SOURCE_OWNER,
                    "source_detail": "ground_truth/20260920_match_serve_anchors.txt",
                    "owner_verdict": anchor.get("verdict"),
                    "owner_note": anchor.get("note") or None,
                    "error": None,
                    "nearest_pipeline_action": _nearest_action(int(anchor["frame"]), actions),
                }
                if err_class == ERROR_SERVE_OUT:
                    ev["error"] = {"type": ERROR_SERVE_OUT, "team": serve_squad,
                                   "text": description}
                owner_events.append(ev)
            else:
                owner_events.append({"unmappable_serve_anchor": int(anchor["frame"])})

        # --- suggested (PREDICTION) events
        win, win_src = _suggested_window(view, anchor or {}, confirmed)
        # Owner-adjudicated exclusions. relabel's `excluded` list carries the
        # owner verdicts that do NOT name an exact frame (e.g. "FALSE 3650 ...
        # covers 3595A and 3856B"), so it is the honest source for them.
        excluded_frames = {int(x["frame"]): str(x.get("because", "owner verdict"))
                           for x in rel.get("excluded", [])}
        suggested: List[Dict[str, Any]] = []
        dropped: List[Dict[str, Any]] = []
        if win is not None:
            lo, hi = win
            for a in actions:
                fr = int(a["frame_number"])
                if not (lo <= fr <= hi):
                    continue
                cf = match_to_clip(offset_map, fr)
                if cf is None or not (0 <= cf < clip_frames):
                    continue
                # Owner FALSE serves and owner OFFGAME ranges are NOT contacts
                # (carried ball / ball passing) — reported, never suggested.
                because = None
                if fr in false_frames:
                    because = "owner FALSE mark"
                elif fr in excluded_frames:
                    because = excluded_frames[fr]
                elif is_offgame(fr):
                    because = "owner OFFGAME range"
                if because:
                    dropped.append({"match_frame": fr, "clip_frame": cf,
                                    "action": a["action"], "team": a.get("team"),
                                    "because": because})
                    continue
                p2 = pass2_by_frame.get(fr, {})
                ev = {
                    "frame": cf,
                    "match_frame": fr,
                    "final_action": a["action"],
                    "action": a["action"],
                    "player_id": a.get("player_id"),
                    "player_team": a.get("team"),
                    "team_in_possession": a.get("team_in_possession"),
                    "touch_number": a.get("touch_number"),
                    "point": k,
                    "source": SOURCE_SUGGESTED,
                    "source_detail": PIPELINE,
                    "suggestion_window": [lo, hi],
                    "gesture": a.get("gesture"),
                    "confidence": a.get("confidence"),
                    "contact_point": a.get("contact_point"),
                    "pass2_action": p2.get("pass2_action"),
                    "pass2_team": p2.get("pass2_team"),
                    "pass2_source": p2.get("pass2_source"),
                    "error": None,
                }
                suggested.append(ev)

        # The serve of this point, when the pass-2 layer produced one, is
        # already covered by the owner anchor -> don't suggest it twice.
        owner_serve_frames = {e["frame"] for e in owner_events if "frame" in e}
        suggested = [e for e in suggested
                     if not (e["point"] == k and e["final_action"] == "serve"
                             and any(abs(e["frame"] - s) <= 20 for s in owner_serve_frames))]

        # --- owner CONTACTS are the authoritative contact list. Any DRAFT
        # event (pipeline suggestion / older draft pass) that coexists with
        # owner contacts is NOT a second contact: it is moved verbatim into
        # `superseded_draft_events`, annotated with the owner contact it
        # duplicates (so nothing is lost and the owner can still adjudicate).
        superseded: List[Dict[str, Any]] = []
        if cevs:   # owner CONTACTS exist for this point (a serve ANCHOR alone is not)
            for e in suggested:
                superseded.append({**e, **supersede_matching(e, owner_events)})
            suggested = []

        # --- error events implied by the dictation
        implied: List[Dict[str, Any]] = []
        if err_class is not None:
            implied.append({
                "type": err_class,
                "team": _error_team(err_class, description, winner, serve_squad),
                "text": description,
                "frame": None,
                "note": _error_note(err_class, description, winner, serve_squad),
            })

        # --- events the dictation implies but that NO frame covers
        missing = _missing_events(description, err_class, owner_events,
                                 suggested + superseded)
        for mi in missing:
            mi["nearby_suggestions"] = [
                {"clip_frame": e["frame"], "action": e["final_action"],
                 "team": e.get("player_team"), "touch_number": e.get("touch_number")}
                for e in suggested]

        switch_after = bool((gtp or {}).get("side_switch_after"))
        contacts_switch = bool(next(
            (p.get("side_switch_after") for p in (contacts_doc or {}).get("points", [])
             if int(p["point"]) == k), False))
        switch_after = switch_after or contacts_switch
        # the window comes from PREDICTIONS in MATCH frames -> translate to clip
        clip_win: Optional[Tuple[int, int]] = None
        if win is not None:
            lo_c, hi_c = match_to_clip(offset_map, win[0]), match_to_clip(offset_map, win[1])
            if lo_c is not None and hi_c is not None and 0 <= lo_c <= hi_c:
                clip_win = (lo_c, min(hi_c, clip_frames - 1))
        point_doc = {
            "point": k,
            "winner": winner,
            "serving_team": serve_squad,
            "serving_side": serve_side,
            "description": description,
            "side_switch_after": switch_after,
            "side_switch_before": k > 1 and bool(gt_points.get(k - 1, {}).get("side_switch_after")),
            "clip_start_frame": clip_win[0] if clip_win else None,
            "clip_end_frame": clip_win[1] if clip_win else None,
            "match_start_frame": win[0] if win else None,
            "match_end_frame": win[1] if win else None,
            "window_source": win_src,
            "window_is_prediction": True,
            "owner_serve_anchor_frame": (int(anchor["frame"]) if anchor else None),
            "owner_serve_anchor_clip_frame": (
                match_to_clip(offset_map, int(anchor["frame"])) if anchor else None),
            "map_attribution": view.get("attribution"),
            "serve_relabel_decision": rel.get("decision"),
            "events": owner_events + suggested,
            "excluded_by_owner_verdict": dropped,
            "n_owner_gt_events": len([e for e in owner_events if "frame" in e]),
            "n_owner_contact_events": len(cevs),
            "owner_contacts": contacts_by_point.get(k, []),
            "contacts_side_switch_after": contacts_switch,
            "unmappable_owner_contacts": [u for u in unm if u["point"] == k],
            "n_suggested_events": len(suggested),
            "superseded_draft_events": superseded,
            "n_superseded_draft_events": len(superseded),
            "implied_events": implied,
            "missing_events": missing,
            "error_events": [e for e in implied if e["frame"] is not None],
        }
        points.append(point_doc)
        events.extend([e for e in owner_events if "frame" in e])
        events.extend(suggested)

    return points, events


def all_unmappable_contacts(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [u for p in points for u in p.get("unmappable_owner_contacts", [])]


# a draft event can be called a duplicate of an owner contact only when it is
# within the owner's own coarse-frame window (CONTACT_FRAME_TOLERANCE) AND on
# the same squad; action labels are allowed to differ (that disagreement is
# exactly what the owner has to adjudicate) but are reported.
DRAFT_MATCH_WINDOW = CONTACT_FRAME_TOLERANCE


def supersede_matching(draft: Dict[str, Any],
                       owner_events: Sequence[Dict[str, Any]]
                       ) -> Dict[str, Any]:
    """Provenance of a draft event that the OWNER CONTACTS supersede."""
    best: Optional[Dict[str, Any]] = None
    for o in owner_events:
        if "frame" not in o:
            continue
        d = abs(int(draft["frame"]) - int(o["frame"]))
        if d > DRAFT_MATCH_WINDOW or o.get("player_team") != draft.get("player_team"):
            continue
        if best is None or d < best["frame_delta"]:
            best = {"frame_delta": d, "o": o}
    if best is None:
        return {
            "superseded_by_owner_contact": None,
            "superseded_reason": "no owner contact on this squad within "
                                 f"+-{DRAFT_MATCH_WINDOW}f — kept here (not in "
                                 "events) so the prediction is not lost; owner to "
                                 "adjudicate whether a contact is missing",
        }
    o = best["o"]
    return {
        "superseded_by_owner_contact": {
            "frame": o["frame"],
            "match_frame": o.get("match_frame"),
            "final_action": o.get("final_action"),
            "player_id": o.get("player_id"),
            "player_team": o.get("player_team"),
            "touch_number": o.get("touch_number"),
            "owner_raw": o.get("owner_raw"),
        },
        "superseded_reason": (
            f"duplicate of the owner-dictated contact at clip f{o['frame']} "
            f"({o.get('final_action')}), {best['frame_delta']}f away on the same "
            "squad; the owner contact is authoritative (coarse frame tolerance "
            f"+-{CONTACT_FRAME_TOLERANCE}f)"
            + ("" if draft.get("final_action") == o.get("final_action") else
               f"; NOTE the draft label '{draft.get('final_action')}' differs from "
               f"the owner action '{o.get('final_action')}' — owner to adjudicate")
        ),
    }


def _nearest_action(frame: int, actions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Closest perception action to an owner anchor, with its delta.

    Owner anchors are COARSE estimates, so the delta is the honest measure of
    anchor precision (and of how far the perception stream is from the contact)
    -- it is reported, never used to move the anchor.
    """
    best = None
    for a in actions:
        d = abs(int(a["frame_number"]) - frame)
        if best is None or d < best["delta_frames"]:
            best = {"match_frame": int(a["frame_number"]), "delta_frames": d,
                    "action": a["action"], "team": a.get("team")}
    return best


def _error_team(err_class: str, description: str, winner: Optional[str],
                serve_squad: Optional[str]) -> Optional[str]:
    """Squad the error belongs to, when the description pins it down."""
    d = (description or "").lower()
    for squad in ("A", "B"):
        if re.search(rf"team {squad.lower()}\b", d):
            return squad
    if err_class in (ERROR_SERVE_OUT, ERROR_SERVE_FAULT):
        return serve_squad
    if err_class == ERROR_SPIKE_NET and winner:
        return ({"A", "B"} - {winner}).pop()
    if err_class == ERROR_SET_SLIP and winner:
        # "player fails hand set": the score says who WON, so the failing set
        # must be the loser's — unless the point survived. Ambiguous when the
        # winner is the failing side; left to the owner.
        return ({"A", "B"} - {winner}).pop() if winner else None
    return None


def _error_note(err_class: str, description: str, winner: Optional[str],
                serve_squad: Optional[str]) -> Optional[str]:
    if err_class == ERROR_SERVE_FAULT:
        return ("the dictation does not say WHERE the serve failed (net / out / "
                "into the net) — owner must confirm")
    if err_class == ERROR_SET_SLIP and winner:
        team = _error_team(err_class, description, winner, serve_squad)
        if team is None:
            return None
        return (f"INFERRED: the score table says {winner} WON, so the faulty set "
                f"reads as squad {team}'s; if the slip did not decide the point "
                f"the squad is the other one — owner to confirm (no frame anchored)")
    return None


_IMPLIED_CONTACT_RE = [
    ("ace", re.compile(r"\bace\b", re.I)),
    ("overpass", re.compile(r"overpass", re.I)),
    ("block", re.compile(r"\bblock", re.I)),
    ("poke_spike", re.compile(r"\bpoke\b", re.I)),
    ("third_contact_pass", re.compile(r"third contact", re.I)),
]

# family -> pipeline action labels that could satisfy it
_FAMILY_ACTIONS = {
    "ace": {"ace"},
    "overpass": {"overpass", "set", "spike"},
    "block": {"block"},
    "poke": {"spike"},
    "poke_spike": {"spike"},
    "third_contact_pass": {"dig", "overpass", "set", "spike"},
    "spike": {"spike"},
    "bump": {"dig", "overpass"},
    "bumb": {"dig", "overpass"},
    "soft touch": {"spike", "overpass", "dig"},
    "set": {"set", "overpass"},
    "dig": {"dig"},
}

# "team A ... spikes", "poke spike from A team", "spike from B team"
_CLAIM_RE = re.compile(
    r"team\s+([ab])\b([^.]*?)\b(spike|poke|overpass|ace|dig|bump|bumb|soft touch|set)s?\b",
    re.I)
_CLAIM_REV_RE = re.compile(
    r"\b(poke spike|spike|overpass|ace|dig|set)s?\b[^.]*"
    r"\b(?:from|by)\s+(?:team\s+)?([ab])\b", re.I)


def _normalise_family(family: str) -> str:
    f = family.lower().strip()
    if "poke" in f:
        return "poke"
    if f in ("bumb", "bump"):
        return "bump"
    return f


def description_claims(description: str) -> List[Tuple[str, str]]:
    """(squad, action family) pairs the dictated text attributes to a squad."""
    claims: List[Tuple[str, str]] = []
    for m in _CLAIM_RE.finditer(description or ""):
        claims.append((m.group(1).upper(), _normalise_family(m.group(3))))
    for m in _CLAIM_REV_RE.finditer(description or ""):
        claims.append((m.group(2).upper(), _normalise_family(m.group(1))))
    out: List[Tuple[str, str]] = []
    for c in claims:
        if c not in out:
            out.append(c)
    return out


def _missing_events(description: str, err_class: Optional[str],
                    owner_events: List[Dict[str, Any]],
                    suggested: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Contacts the dictation implies that no frame covers (owner GT or
    suggestion). Reported, never invented."""
    d = description or ""
    out: List[Dict[str, Any]] = []
    if err_class is not None and not any(e.get("error") for e in owner_events):
        out.append({"type": err_class, "reason": "dictated fault has no owner frame anchor",
                    "frame": None})
    for name, rx in _IMPLIED_CONTACT_RE:
        if rx.search(d) and not any(
                name.split("_")[0] in (e.get("final_action") or "") for e in suggested):
            out.append({"type": name, "reason": "dictated but no action emitted for it",
                        "frame": None})
    for squad, family in description_claims(d):
        acts = _FAMILY_ACTIONS.get(family, {family})
        if not any(e.get("player_team") == squad and e.get("final_action") in acts
                   for e in suggested):
            out.append({"type": f"{family}_by_team_{squad}",
                        "reason": f"dictated '{family}' by squad {squad} has no "
                                  f"matching contact (team/label to adjudicate)",
                        "frame": None})
    return out


def build_gt(clip_fps: float, clip_frames: int, offset_map: Dict[str, Any],
             points: List[Dict[str, Any]], events: List[Dict[str, Any]],
             point_range: Sequence[int], args_sources: Dict[str, str],
             include_suggested_in_actions: bool,
             contacts_doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    graded = [e for e in events
              if include_suggested_in_actions or e.get("source") == SOURCE_OWNER]
    graded.sort(key=lambda e: e["frame"])
    has_contacts = contacts_doc is not None and any(
        p.get("contacts") for p in contacts_doc.get("points", []))
    status = STATUS_OWNER_DICTATED if has_contacts else STATUS_DRAFT
    status_note = (
        "OWNER_DICTATED: every contact of P1-P8 was dictated by the owner "
        "(ground_truth/20260920_match_ari_joan_contacts_p1_p8.txt, 2026-09-28) "
        "with the player track id seen AT the contact. FRAMES ARE COARSE "
        "(owner estimates, +-10-15f) — each event carries frame_tolerance=15, so "
        "nothing here is frame-exact and a prediction outside that tolerance is "
        "NOT a GT error by construction."
        if has_contacts else
        "DRAFT: serve-anchor level only; nothing here is ground truth until the "
        "owner ratifies the contact sheets (AGENTS.md).")
    return {
        "status": status,
        "status_note": status_note,
        "video": CLIP,
        "fps": clip_fps,
        "fps_note": "VFR container (r_frame_rate 30.12, avg ~28.84); the clip is a "
                    "frame-exact re-encode of the match prefix, so frame indices "
                    "match the match 1:1 and NO time conversion is applied",
        "resolution": [1920, 1080],
        "frame_indexing": "clip-local; `match_frame` carries the same event in "
                          "resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4",
        "generated_by": "scripts/build_dev_clip_gt.py",
        "offset_map": offset_map,
        "points": points,
        "provenance": {
            "owner_gt_inputs": [
                CONTACTS + " (contact-level dictation: every rally contact of "
                "P1-P8 with track id / side / action; coarse +-10-15f frames)",
                ANCHORS + " (serve frame anchors, rounds 1+2; superseded by the "
                "contact-level serve wherever both exist)",
                MATCH_POINTS + " (parsed verbatim from "
                "ground_truth/20260920_match_ari_joan_lost.txt: descriptions, "
                "mechanical winner, side switches)",
            ],
            "prediction_inputs_suggestions_only": [
                EPISODE_MAP, SERVE_RELABEL, PIPELINE],
            "not_used": [
                "ground_truth/gt_point_start_end.txt — anchors the game-state video "
                "ONLY, meaningless for the match (ground_truth/README.md warning)"],
            "point_range": list(point_range),
            "contacts_unparsed_lines": (contacts_doc or {}).get("unparsed", []),
            "contacts_unmappable": all_unmappable_contacts(points),
            "event_sources": args_sources,
            "events_in_annotated_frames": sorted({e.get("source") for e in graded}),
            "n_owner_contact_events": len(graded),
            "superseded_draft_events": sum(
                len(p.get("superseded_draft_events", [])) for p in points),
            "superseded_draft_events_note":
                "Draft/suggested events that coexisted with owner-dictated "
                "CONTACTS. The owner contacts are the authoritative contact "
                "list, so these live in points[].superseded_draft_events (with "
                "the owner contact each duplicates) and are NOT graded.",
        },
        "annotated_frames": {
            "ball": {
                "description": "No ball annotations in T2 (frame-level GT covers "
                               "contact events only).",
                "frames": {},
            },
            "players": {
                "description": "No player boxes in T2 — player_id is null on every "
                               "serve-anchor event; owner-dictated CONTACT events "
                               "carry the pipeline track id valid at the contact "
                               "frame (ids are NOT stable across occlusions — see "
                               "the contacts txt header).",
                "frames": {},
            },
            "actions": {
                "description": "Contact events, clip-local frames. Only "
                               "source='owner_gt' events are ground truth; "
                               "source='suggested_from_prediction' events are "
                               "pipeline suggestions flagged for owner adjudication "
                               "and are excluded from this list by default. Where "
                               "the owner dictated contacts, the owner contacts "
                               "are the whole list and every draft/suggested event "
                               "was moved to points[].superseded_draft_events.",
                "events": graded,
            },
        },
    }


# --- contact sheets --------------------------------------------------------

TILE_W, TILE_H = 480, 270
COLS = 4
_MARGIN = 26
_LABEL_H = 58


def _label(img: np.ndarray, lines: Sequence[str], color=(0, 255, 255),
           top: bool = True) -> None:
    y = 20 if top else img.shape[0] - 14 - 18 * (len(lines) - 1)
    for ln in lines:
        cv2.putText(img, ln, (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
        cv2.putText(img, ln, (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        y += 18


def render_sheets(clip_path: str, points: List[Dict[str, Any]],
                  out_dir: str) -> List[str]:
    """One PNG grid per point: a cell per event (owner GT + suggestions), read
    back from the CLIP by sequential decode (VFR-safe)."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    wanted: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for p in points:
        for e in p["events"]:
            if "frame" in e:
                wanted.append((p, e))
        for e in p.get("superseded_draft_events", []):
            if "frame" in e:
                # still shown (dashed, magenta) so the owner can adjudicate the
                # draft prediction against the owner contact that supersedes it
                wanted.append((p, {**e, "status_label": SOURCE_SUPERSEDED}))
        for imp in p.get("implied_events", []):
            if imp.get("frame") is not None:
                wanted.append((p, {"frame": imp["frame"],
                                   "final_action": imp.get("type", "?"),
                                   "player_team": imp.get("team"),
                                   "player_id": None,
                                   "source": SOURCE_SUGGESTED,
                                   "error": {"type": imp.get("type")}}))
    wanted.sort(key=lambda pe: (pe[0]["point"], pe[1]["frame"]))

    need = [e["frame"] for _, e in wanted]
    frames: Dict[int, np.ndarray] = {}
    if need:
        last = max(need)
        cap = cv2.VideoCapture(clip_path)
        try:
            i = 0
            while i <= last:
                ok, fr = cap.read()
                if not ok:
                    break
                if i in set(need):
                    frames[i] = fr
                i += 1
        finally:
            cap.release()

    written: List[str] = []
    for p in points:
        evs = [e for pp, e in wanted if pp["point"] == p["point"]]
        if not evs:
            continue
        rows = (len(evs) + COLS - 1) // COLS
        head = 76
        sheet = np.full((head + rows * (TILE_H + _LABEL_H + _MARGIN) + 30, COLS * TILE_W, 3),
                        24, np.uint8)
        head_lines = [
            f"GT P{p['point']}  winner={p['winner']}  serving={p['serving_team']}"
            f" ({p['serving_side']})  win_frames=[{p['clip_start_frame']},"
            f"{p['clip_end_frame']}] ({p['window_source']}, PREDICTION)",
            f"description: {p['description']}",
            f"owner GT: serve anchor match_f{p['owner_serve_anchor_frame']} = "
            f"clip_f{p['owner_serve_anchor_clip_frame']}"
            + (f" | SIDE SWITCH after P{p['point']}" if p["side_switch_after"] else ""),
        ]
        for k, ln in enumerate(head_lines):
            cv2.putText(sheet, ln[:150], (8, 20 + 20 * k), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 255, 255), 1)
        for idx, e in enumerate(evs):
            r, c = divmod(idx, COLS)
            x0 = c * TILE_W
            y0 = head + r * (TILE_H + _LABEL_H + _MARGIN)
            img = frames.get(e["frame"])
            if img is None:
                img = np.zeros((TILE_H, TILE_W, 3), np.uint8)
                _label(img, ["FRAME UNAVAILABLE"], (0, 0, 255))
            else:
                img = cv2.resize(img, (TILE_W, TILE_H), interpolation=cv2.INTER_AREA)
                colour = (0, 255, 0) if e.get("source") == SOURCE_OWNER else (0, 165, 255)
                if e.get("status_label") == SOURCE_SUPERSEDED:
                    colour = (255, 0, 255)
                cp = e.get("contact_point")
                if cp and 0 <= int(cp[0]) < 1920 and 0 <= int(cp[1]) < 1080:
                    # mark the predicted contact + 2x zoom inset so the owner can
                    # actually see the ball at the player on the sheet
                    cx, cy = int(cp[0]) * TILE_W // 1920, int(cp[1]) * TILE_H // 1080
                    zx = max(0, min(1920 - 480, int(cp[0]) - 240))
                    zy = max(0, min(1080 - 270, int(cp[1]) - 135))
                    full = frames.get(e["frame"])
                    if full is not None:
                        zoom = cv2.resize(full[zy:zy + 270, zx:zx + 480],
                                          (TILE_W // 2, TILE_H // 2),
                                          interpolation=cv2.INTER_LINEAR)
                        img[0:TILE_H // 2, TILE_W // 2:TILE_W] = zoom
                        cv2.rectangle(img, (TILE_W // 2, 0), (TILE_W, TILE_H // 2),
                                      colour, 2)
                        cv2.putText(img, "2x zoom (contact)", (TILE_W // 2 + 6, 14),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, colour, 1)
                    # drawn last so the 2x inset never covers the marker
                    cv2.circle(img, (cx, cy), 16, colour, 2)
                _label(img, [
                    f"clip_f{e['frame']} (match_f{e['match_frame']})",
                    f"{e.get('final_action')} team={e.get('player_team')}"
                    f" player={e.get('player_id')}",
                    f"source={e.get('status_label', e.get('source'))}"
                    + (f" err={e['error']['type']}" if e.get("error") else ""),
                ], colour, top=False)
            sheet[y0:y0 + TILE_H, x0:x0 + TILE_W] = img
            lab = (f"clip_f{e['frame']} | {e.get('final_action')} | "
                   f"team={e.get('player_team')} | player={e.get('player_id')} | "
                   f"{e.get('status_label', e.get('source'))}")
            cv2.putText(sheet, lab[:70], (x0 + 6, y0 + TILE_H + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            cv2.putText(sheet, f"match_f{e['match_frame']}", (x0 + 6, y0 + TILE_H + 36),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
        path = str(Path(out_dir) / f"P{p['point']}.png")
        cv2.imwrite(path, sheet)
        written.append(path)
    return written


def render_readme(points: List[Dict[str, Any]], offset_map: Dict[str, Any],
                  gt_path: str, out_dir: str) -> str:
    lines: List[str] = [
        "# T2 dev-clip GT — owner ratification sheet",
        "",
        f"Clip: `{CLIP}` — first 8 points of `{MATCH}`.",
        f"GT file (DRAFT): `{gt_path}`.",
        "",
        "**Nothing here is ground truth until you ratify it.** Every cell is "
        "labelled with its source: `owner_gt` (from the ratified match serve "
        "anchors / dictated text) or `suggested_from_prediction` (pipeline "
        "output, a suggestion only).",
        "",
        "## Offset map (clip frame -> match frame)",
        "",
        f"- method: {offset_map['method']}; drift detected: **{offset_map['drift']}**",
        "",
        "| segment | clip frames | match offset | residual |",
        "|---|---|---|---|",
    ]
    for s in offset_map["segments"]:
        lines.append(f"| {s['clip_start']}-{s['clip_end']} | +{s['match_offset']} | "
                     f"{s['residual']} |")
    lines += ["", "Verification (thumbnail abs-difference, lower is better):", "",
              "| check | clip frame | mapped match frame | residual at mapped | "
              "best in ±radius | offset in band | ok |", "|---|---|---|---|---|---|---|"]
    for c in offset_map["checks"]:
        lines.append(f"| {c['check']} | {c['clip_frame']} | {c['mapped_match_frame']} | "
                     f"{c['residual_at_mapped']} | {c['best_residual_in_band']} | "
                     f"{c['best_offset_in_band']} | {'yes' if c['ok'] else 'NO'} |")
    lines += ["", "## Points", ""]
    for p in points:
        lines += [
            f"### P{p['point']} — {p['description']}",
            "",
            f"- winner: **{p['winner']}** (mechanical, owner score table) | serving "
            f"squad: **{p['serving_team']}** from the **{p['serving_side']}** side",
            f"- side switch after this point: **{p['side_switch_after']}**",
            f"- owner GT: serve anchor match f{p['owner_serve_anchor_frame']} -> clip "
            f"f{p['owner_serve_anchor_clip_frame']}"
            + (f" (verdict {p['events'][0].get('owner_verdict')})"
               if p["events"] and p["events"][0].get("owner_verdict") else ""),
            f"- point window [clip {p['clip_start_frame']}, {p['clip_end_frame']}] from "
            f"`{p['window_source']}` — **PREDICTION, not GT**",
            f"- events: {p['n_owner_gt_events']} owner_gt"
            + (f" ({p.get('n_owner_contact_events', 0)} owner-dictated CONTACTS, "
               f"coarse +-{CONTACT_FRAME_TOLERANCE}f)" if p.get("n_owner_contact_events") else ""),
        ]
        if p.get("superseded_draft_events"):
            lines[-1] += (f" — {p['n_superseded_draft_events']} draft/suggested "
                          f"event(s) moved to `superseded_draft_events`")
        ns = p["events"][0].get("nearest_pipeline_action") if p["events"] else None
        if ns:
            lines.append(
                f"- anchor precision: nearest perception action is "
                f"f{ns['match_frame']} ({ns['action']}, team {ns['team']}) — "
                f"**{ns['delta_frames']} frames** from the owner anchor. The anchor "
                f"is a COARSE owner estimate; the evaluator's default ±15f tolerance "
                f"cannot match it.")
        if p["events"]:
            lines += ["", "| clip frame | match frame | action | gesture | team | "
                      "player | touch | source | note |",
                      "|---|---|---|---|---|---|---|---|---|"]
            for e in p["events"]:
                note = ""
                if e.get("error"):
                    note = f"ERROR: {e['error']['type']}"
                elif e.get("pass2_action") and e["pass2_action"] != e["final_action"]:
                    note = f"pass2 re-labels this as {e['pass2_action']}"
                if e.get("owner_interpretation_flag"):
                    fl = e["owner_interpretation_flag"]
                    note = (note + " | " if note else "") + (
                        "FLAG: overpass wording (OWNER-RATIFIED "
                        f"{fl['owner_ratification_date']})"
                        if fl.get("owner_ratified")
                        else "FLAG: overpass wording")
                lines.append(
                    f"| {e['frame']} | {e['match_frame']} | {e['final_action']} | "
                    f"{e.get('gesture') or '-'} | "
                    f"{e.get('player_team')} | {e.get('player_id')} | "
                    f"{e.get('touch_number')} | {e['source']} | {note} |")
        else:
            lines += ["", "_no event frames available in this point_"]
        for imp in p.get("implied_events", []):
            lines.append("")
            lines.append(f"- **IMPLIED (no frame):** {imp['type']} by squad "
                         f"{imp['team']} — {imp['text']}")
            if imp.get("note"):
                lines.append(f"  - {imp['note']}")
        if p.get("excluded_by_owner_verdict"):
            lines.append("")
            lines.append("- **Excluded by owner verdict (NOT contacts):**")
            for x in p["excluded_by_owner_verdict"]:
                lines.append(f"  - clip f{x['clip_frame']} {x['action']} "
                             f"({x['team']}): {x['because']}")
        for sup in p.get("superseded_draft_events", []):
            lines += ["", "- **SUPERSEDED draft/suggested events** (not contacts; "
                          "the owner contact is authoritative):"]
            lines.append(f"  - clip f{sup['frame']} {sup['final_action']} "
                         f"({sup.get('player_team')}, t{sup.get('touch_number')}): "
                         f"{sup.get('superseded_reason', '')}")
            m = sup.get("superseded_by_owner_contact")
            if m:
                lines.append(f"    - owner contact: clip f{m['frame']} "
                             f"{m['final_action']} team={m['player_team']} "
                             f"player={m['player_id']} touch={m['touch_number']}")
        if p.get("missing_events"):
            lines.append("")
            lines.append("- **MISSING (dictated, no frame anywhere):**")
            for mi in p["missing_events"]:
                lines.append(f"  - {mi['type']}: {mi['reason']}")
                if mi.get("nearby_suggestions"):
                    lines.append("    - candidate frames to adjudicate: "
                                 + ", ".join(
                                     f"clip f{c['clip_frame']} {c['action']}"
                                     f"({c['team']},t{c['touch_number']})"
                                     for c in mi["nearby_suggestions"]))
        lines += ["", f"Suggested frames to adjudicate: "
                  + (", ".join(f"clip f{e['frame']} ({e['final_action']})"
                               for e in p["events"] if e["source"] == SOURCE_SUGGESTED)
                     or "none"),
                  "", "---", ""]
    lines += [
        "## What the owner has to decide",
        "",
        "1. Ratify/correct each P<n>.png cell: is the ball at a player at that "
        "frame, and is the action label right?",
        "2. Supply frames for the MISSING events (dictated but unlocated) — most "
        "importantly the fault contacts (spike into the net, set slip).",
        "3. Confirm the serving squad/side per point and the side-switch point.",
        "4. Once ratified, flip `status` to `RATIFIED` (owner action, not this script).",
        "",
    ]
    path = str(Path(out_dir) / "README.md")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return path


# --- main ------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--clip", default=CLIP)
    ap.add_argument("--match", default=MATCH)
    ap.add_argument("--match-points", default=MATCH_POINTS)
    ap.add_argument("--anchors", default=ANCHORS)
    ap.add_argument("--contacts", default=CONTACTS,
                    help="owner-dictated contact-level GT txt (owner track ids)")
    ap.add_argument("--episode-map", default=EPISODE_MAP)
    ap.add_argument("--serve-relabel", default=SERVE_RELABEL)
    ap.add_argument("--pipeline", default=PIPELINE)
    ap.add_argument("--out", default=GT_OUT)
    ap.add_argument("--sheet-dir", default=SHEET_DIR)
    ap.add_argument("--points", default="1-8", help="point range, e.g. 1-8 or 1,2,5")
    ap.add_argument("--cache", default="output/t2_offset_thumbs.npz",
                    help="thumbnail cache (sequential decode is the slow part)")
    ap.add_argument("--skip-offset", action="store_true",
                    help="reuse the cached offset map instead of re-matching")
    ap.add_argument("--no-sheets", action="store_true")
    ap.add_argument("--include-suggested-in-actions", action="store_true",
                    help="also put suggested_from_prediction events into "
                         "annotated_frames.actions.events (NOT ground truth)")
    ap.add_argument("--thumb", default="32x18")
    args = ap.parse_args(argv)

    def _p(s: str) -> str:
        return str(ROOT / s) if not Path(s).is_absolute() and not Path(s).exists() else s

    if "-" in args.points:
        lo, hi = args.points.split("-")
        point_range = list(range(int(lo), int(hi) + 1))
    else:
        point_range = [int(x) for x in args.points.split(",")]

    tw, th = (int(x) for x in args.thumb.split("x"))
    cache = Path(_p(args.cache)) if args.cache else None
    clip_t = compute_thumbs(_p(args.clip), (tw, th))
    print(f"[offset] clip thumbnails: {clip_t.shape}")

    offset_map: Optional[Dict[str, Any]] = None
    if args.skip_offset and cache and cache.exists():
        data = np.load(str(cache), allow_pickle=True)
        offset_map = json.loads(str(data["offset_map"]))
        print("[offset] reused cached offset map")
    if offset_map is None:
        match_t = None
        if cache and cache.exists():
            data = np.load(str(cache), allow_pickle=True)
            if "match_thumbs" in data and tuple(data["thumb_size"]) == (tw, th):
                match_t = data["match_thumbs"]
        if match_t is None:
            print("[offset] decoding the match sequentially (VFR-safe)...")
            match_t = compute_thumbs(_p(args.match), (tw, th))
        print(f"[offset] match thumbnails: {match_t.shape}")
        offset_map = build_offset_map(clip_t, match_t)
        for c in offset_map["checks"]:
            print(f"[offset] {c['check']:>6}: clip f{c['clip_frame']} -> match "
                  f"f{c['mapped_match_frame']} residual={c['residual_at_mapped']} "
                  f"(best in band {c['best_residual_in_band']} @ off "
                  f"{c['best_offset_in_band']}) ok={c['ok']}")
        print(f"[offset] drift={offset_map['drift']} segments={offset_map['segments']}")
        if cache:
            Path(cache).parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(str(cache), clip_thumbs=clip_t, match_thumbs=match_t,
                                thumb_size=np.array([tw, th]),
                                offset_map=np.array(json.dumps(offset_map)))
            print(f"[offset] cache written: {cache}")

    clip_frames = len(clip_t)
    cap = cv2.VideoCapture(_p(args.clip))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_meta = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()

    anchors_doc = parse_serve_anchors(_p(args.anchors))
    contacts_doc = (parse_contact_gt(_p(args.contacts))
                    if Path(_p(args.contacts)).exists() else None)
    if contacts_doc:
        print(f"[contacts] {sum(len(p['contacts']) for p in contacts_doc['points'])} "
              f"owner contacts over points "
              f"{[p['point'] for p in contacts_doc['points']]}; "
              f"{len(contacts_doc['unparsed'])} unparsed line(s)")
    match_points = load_json(_p(args.match_points))
    ep_map = load_json(_p(args.episode_map)) if Path(_p(args.episode_map)).exists() else None
    relabel = load_json(_p(args.serve_relabel)) if Path(_p(args.serve_relabel)).exists() else None
    pipeline = load_json(_p(args.pipeline)) if Path(_p(args.pipeline)).exists() else None

    points, events = build_points(clip_frames, offset_map, match_points, anchors_doc,
                                  ep_map, relabel, pipeline, point_range, contacts_doc)
    gt = build_gt(fps, clip_frames, offset_map, points, events, point_range,
                  {"owner_gt": CONTACTS + " + " + ANCHORS, "suggested": EPISODE_MAP + " + " + SERVE_RELABEL
                   + " + " + PIPELINE},
                  args.include_suggested_in_actions, contacts_doc)
    gt["clip_container_frames"] = n_meta
    gt["clip_decoded_frames"] = clip_frames
    out_path = _p(args.out)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(gt, indent=2) + "\n", encoding="utf-8")
    n_owner = sum(1 for e in events if e["source"] == SOURCE_OWNER)
    n_sup = sum(len(p.get("superseded_draft_events", [])) for p in points)
    print(f"[gt] wrote {out_path}: {len(points)} points, {n_owner} owner_gt events, "
          f"{len(events) - n_owner} suggested events, {n_sup} superseded draft events, "
          f"{len(gt['annotated_frames']['actions']['events'])} events graded by the evaluator")

    if not args.no_sheets:
        written = render_sheets(_p(args.clip), points, _p(args.sheet_dir))
        readme = render_readme(points, offset_map, args.out, _p(args.sheet_dir))
        print(f"[sheets] {len(written)} PNG grids + {readme}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
