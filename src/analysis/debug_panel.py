"""Live-debug side panel: per-frame signals + the event log on the HUD.

Render-only. Nothing here feeds the pipeline: the live-debug producer snapshots
values ``FrameProcessor.process_frame`` already produced this frame (ball
position/size/speed, the classifier's own width-side verdict, per-player court
team + ball distance, the game-state badge, the contact probe) and caches them
next to the frame; the consumer thread draws them onto a strip composited to
the RIGHT of the annotated frame. Because the consumer is ~3 s behind the
producer, the event log can be keyed on each action's TRUE contact frame -- the
same trick ``overlay.LabelPlan`` uses for the player labels -- so an event shows
up on the frame the contact happened, not on the frame the look-ahead emitted
it.

Two independent pieces:

- :class:`EventPlan` -- a thread-safe, contact-frame-keyed event log
  (producer writes, consumer reads) for the emitted actions and the resolved
  spike outcomes.
- :func:`build_rows` / :func:`compose` -- the panel's formatting and painting,
  kept as pure functions over plain data so they are testable without the
  pipeline (and so no threshold is duplicated here: every number arrives
  already computed by the components that own it).

ASCII only -- OpenCV's Hershey fonts cannot render non-ASCII text.
"""

import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

# --- panel geometry / palette -------------------------------------------
# Text scale is chosen so the composed panel is legible when OpenCV scales the
# widened frame into the window (the window is sized to fit the screen, so the
# on-screen size is a fraction of this). 0.55 is +3 px of cap height over the
# previous 0.40; the panel is widened to match, or every signal row would clip.
PANEL_WIDTH = 600          # px added to the right of the annotated frame
PAD = 10                   # left/right margin inside the panel
LINE = 20                  # row height (px)
FONT = cv2.FONT_HERSHEY_SIMPLEX
SCALE = 0.55               # body text scale (~11 px/char, ~54 chars fit)
TITLE_SCALE = 0.62         # the SIGNALS header

BG = (24, 24, 24)
FG = (225, 225, 225)
DIM = (135, 135, 135)
HEADER = (255, 190, 60)    # section titles (BGR amber)
TITLE = (255, 255, 255)
OK = (90, 220, 120)
WARN = (70, 200, 250)
BAD = (70, 70, 240)        # BGR red
SEP = (85, 85, 85)

# How long an event stays on screen, in frames (~7 s at 30 fps). Long enough to
# read the row and its signals while the contact frame is still in view.
EVENT_PERSIST = 210
# Rows drawn per section / total: keeps the panel inside short frames.
MAX_PLAYER_ROWS = 6
MAX_EVENT_ROWS = 8

Row = Tuple[str, Tuple[int, int, int], int]   # (text, colour, indent px)


def _fmt(v: Optional[float], nd: int = 1, suffix: str = "") -> str:
    """Number -> string, or a dash for None (signals are frequently absent)."""
    if v is None:
        return "-"
    if isinstance(v, bool):
        return str(v)
    try:
        return f"{float(v):.{nd}f}{suffix}"
    except (TypeError, ValueError):
        return str(v)


class EventPlan:
    """Contact-frame-keyed event log, safe for producer writes / consumer reads.

    Keyed by contact frame rather than track_id: the panel wants EVERY event,
    including repeats by the same player and events with no player, and the
    producer ingests an action only when the look-ahead releases it. :meth:`at`
    returns the entries whose window covers the rendered frame, newest first, so
    the panel shows the event on its contact frame and keeps the recent history
    in view.
    """

    def __init__(self, persist: int = EVENT_PERSIST):
        self.persist = persist
        self._by_frame: Dict[int, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def add(self, contact_frame: Optional[int], title: str, detail: str = "",
            color: Tuple[int, int, int] = FG) -> None:
        """Record one event at its true contact frame (ignored if frame is None)."""
        if contact_frame is None:
            return
        with self._lock:
            self._by_frame.setdefault(int(contact_frame), []).append(
                {"title": title, "detail": detail, "color": color})

    def at(self, frame_idx: Optional[int], limit: int = MAX_EVENT_ROWS
           ) -> List[Tuple[int, Dict[str, Any]]]:
        """``(contact_frame, entry)`` for events covering ``frame_idx``, newest first."""
        if frame_idx is None:
            return []
        with self._lock:
            found = [
                (cf, e)
                for cf, entries in self._by_frame.items()
                for e in entries
                if cf <= frame_idx < cf + self.persist
            ]
        found.sort(key=lambda ce: -ce[0])
        return found[:limit]

    def reset(self) -> None:
        with self._lock:
            self._by_frame.clear()


def build_rows(snapshot: Dict[str, Any],
               events: Sequence[Tuple[int, Dict[str, Any]]] = ()
               ) -> List[Row]:
    """Format one frame's snapshot + its events into drawable rows.

    Every value is a pre-computed pipeline output (see ``LiveDebugProcessor``'s
    ``_signals``): nothing here re-derives a threshold, re-runs inference or
    re-reads calibration state. Missing values render as "-" so a silently
    absent signal is visible instead of guessed.
    """
    rows: List[Row] = []
    add = rows.append

    # ---- header -------------------------------------------------------
    frame = snapshot.get("frame")
    total = snapshot.get("total")
    frame_str = f"frame {frame}" if not total else f"frame {frame}/{total}"
    add(("SIGNALS", TITLE, 0))
    add((frame_str, HEADER, 0))

    # ---- ball ---------------------------------------------------------
    # A dropped track must NOT blank the readout: the last known pos / size /
    # width-side read stay on screen, flagged as held with the age in frames,
    # because they are what the classifier's own decisions were made on. The
    # flag rides ON the section header line -- no extra row.
    ball = snapshot.get("ball")
    held = bool(ball) and ball.get("present") is False
    if held:
        add(("-- BALL -- NOT TRACKED (last f{}, {}f ago)".format(
            ball.get("held_from"), ball.get("stale")), BAD, 0))
    else:
        add(("-- BALL --", HEADER, 0))
    if not ball:
        add(("no track yet", DIM, 1))
    else:
        tone = WARN if held else FG
        add((f"pos {ball.get('x')},{ball.get('y')}   "
             f"size {ball.get('w')}x{ball.get('h')}px", tone, 1))
        side = ball.get("side")
        votes = ball.get("side_votes")
        side_txt = "-" if side is None else f"{side} ({ball.get('side_name')})"
        if votes:
            side_txt += f" {votes}v"
        add((f"width-side read: {side_txt}", tone, 1))
        add((f"speed {_fmt(ball.get('speed'))} px/f   "
             f"conf {_fmt(ball.get('conf'), 2)}", tone, 1))
        # Ball ground contact (#80): GROUND / OUT / AIR + groundedness ratio
        # + mapped court position (metres). Held rows keep the last state.
        g = ball.get("ground") or {}
        g_state = g.get("state")
        if g_state:
            g_ratio = g.get("ratio")
            g_txt = g_state.upper()
            if g_ratio is not None:
                g_txt += f" r{float(g_ratio):.2f}"
            wpt = g.get("world")
            if wpt:
                g_txt += f" @({float(wpt[0]):.1f},{float(wpt[1]):.1f})m"
            if g.get("bounce"):
                g_txt += " BOUNCE"
            add((f"ground: {g_txt}", tone, 1))
        pred = bool(ball.get("predicted"))
        stale = ball.get("stale")
        if held:
            add((f"track HELD   stale {stale}f", WARN, 1))
        else:
            stale_col = BAD if pred else (WARN if (stale or 0) > 2 else FG)
            add((f"track {'PREDICTED' if pred else 'real'}   "
                 f"stale {stale}f", stale_col, 1))

    # ---- players ------------------------------------------------------
    # Distances stay live w.r.t. the players even while the ball is held (they
    # are measured against the LAST known ball point); the block is dimmed so
    # nobody reads them as current.
    players = snapshot.get("players") or []
    add((f"-- PLAYERS ({len(players)}) --"
         + ("  [ball not tracked]" if held else ""),
         WARN if held else HEADER, 0))
    for p in players[:MAX_PLAYER_ROWS]:
        flags = []
        if p.get("near_net"):
            flags.append("net")
        if p.get("predicted"):
            flags.append("ghost")
        dist = p.get("dist")
        reach = p.get("reach")
        dist_txt = "-" if dist is None else f"{int(round(dist))}px"
        if reach is True:
            dist_col = OK
        elif reach is False:
            dist_col = BAD
        else:
            dist_col = FG
        if held:
            dist_col = DIM
        team = p.get("team") or "?"
        name = p.get("label") or f"P{p.get('tid')}"
        add((f"{name} {team} {(' '.join(flags)):<8} {dist_txt:>6}",
             dist_col, 1))
    if len(players) > MAX_PLAYER_ROWS:
        add((f"... +{len(players) - MAX_PLAYER_ROWS} more", DIM, 1))

    # ---- game state ---------------------------------------------------
    game = snapshot.get("game") or {}
    add(("-- GAME --", HEADER, 0))
    state = game.get("state") or "-"
    state_col = OK if state == "game_on" else DIM
    prov = " ~" if game.get("provisional") else ""
    add((f"{state}{prov}   points {game.get('points', 0)}", state_col, 1))

    # ---- contact probe ------------------------------------------------
    probe = snapshot.get("probe") or []
    pend = snapshot.get("pending")
    add(("-- CONTACT PROBE / LOOK-AHEAD --", HEADER, 0))
    for rec in probe[:3]:
        add((_probe_row(rec), _probe_color(rec), 1))
    if not probe:
        add(("no contact probed", DIM, 1))
    if pend:
        gest = pend.get("gesture") or "?"
        add((f"held back: f{pend.get('frame')} P{pend.get('player_id')} "
             f"{gest} {pend.get('team') or '?'}", HEADER, 1))
    else:
        add(("held back: -", DIM, 1))

    # ---- events (anchored on their TRUE contact frame) ----------------
    add(("-- EVENTS --", HEADER, 0))
    cur = snapshot.get("frame")
    if not events:
        add(("none yet", DIM, 1))
    for cf, entry in events:
        on = (cf == cur)
        mark = ">>" if on else "  "
        add((f"{mark} {entry.get('title')}", entry.get("color", FG), 1))
        detail = entry.get("detail")
        if detail:
            add((f"     {detail}", FG if on else DIM, 1))
    return rows


def _probe_row(rec: Dict[str, Any]) -> str:
    """One contact-probe record: what fired, or which gate refused it."""
    frame = rec.get("frame")
    stage = rec.get("stage")
    reason = rec.get("reason")
    if stage in ("candidate_found", "candidate_passed_gates", "accepted"):
        kind = rec.get("kind") or rec.get("gesture") or "?"
        extra = ""
        dist, reach = rec.get("distance"), rec.get("reach")
        if dist is not None:
            extra = f" d={int(round(float(dist)))}px/{int(round(float(reach)))}px"
        act = rec.get("action")
        if act:
            extra += f" -> {act}"
        return f"f{frame} {stage.split('_')[0]} {kind}{extra}"
    return f"f{frame} refused: {reason}"


def _probe_color(rec: Dict[str, Any]) -> Tuple[int, int, int]:
    stage = rec.get("stage")
    if stage in ("candidate_found", "candidate_passed_gates", "accepted"):
        return OK
    reason = rec.get("reason")
    # "no contact here" is the normal case; a gate refusal on a real vertex is
    # the interesting one (a contact the pipeline saw and threw away).
    return WARN if reason in ("reach", "no_player_snapshot",
                              "context_confidence") else DIM


def _clip(text: str, max_px: int) -> str:
    """Trim ``text`` so it fits ``max_px`` px at the panel's font scale.

    Signal rows are dense (a detail row can carry gesture/kind/net/side/width),
    so overflow is clipped with a trailing '~' rather than running off the
    strip. Measured, not character-counted, so wide glyphs are safe.
    """
    if max_px <= 8:
        return ""
    (tw, _), _ = cv2.getTextSize(text, FONT, SCALE, 1)
    if tw <= max_px:
        return text
    lo, hi = 0, len(text)
    while lo < hi:                      # longest prefix that fits
        mid = (lo + hi + 1) // 2
        (w_mid, _), _ = cv2.getTextSize(text[:mid], FONT, SCALE, 1)
        if w_mid <= max_px - 10:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + "~"


def compose(frame: np.ndarray, snapshot: Dict[str, Any],
            events: Sequence[Tuple[int, Dict[str, Any]]] = (),
            panel_width: int = PANEL_WIDTH) -> np.ndarray:
    """Return ``frame`` with the signal/event panel composited on its right."""
    h, w = frame.shape[:2]
    out = np.empty((h, w + panel_width, 3), dtype=np.uint8)
    out[:, :w] = frame
    out[:, w:] = BG
    cv2.line(out, (w, 0), (w, h - 1), SEP, 1)

    rows = build_rows(snapshot, events)
    x = w + PAD
    y = PAD + LINE
    for i, (text, color, indent) in enumerate(rows):
        if y > h - 4:
            add_more = f"... +{len(rows) - i} rows"
            cv2.putText(out, add_more, (x, y), FONT, SCALE, DIM, 1, cv2.LINE_AA)
            break
        text = _clip(text, panel_width - 2 * PAD - indent)
        cv2.putText(out, text, (x + indent, y),
                    FONT, TITLE_SCALE if i == 0 else SCALE, color, 1, cv2.LINE_AA)
        y += LINE
    return out