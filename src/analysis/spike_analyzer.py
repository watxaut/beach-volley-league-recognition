"""Spike outcome/zone analyzer: a pure observer over the per-frame stream.

The two-layer classifier emits a ``spike`` event well after the true contact
(one-contact look-ahead + ``CONTACT_DELAY``), carrying the true contact frame
in ``frame_number``. This component watches the same per-frame stream that
``FrameProcessor`` already produces (tracked ball, tracked players, emitted
actions) and enriches each spike with:

- ``spike_type``  -- ``touch`` (soft shot / rainbow) vs ``hard`` (driven or
  accelerated), from the ball's exit speed over the first real sightings
  after contact;
- ``attack_zone`` -- the spiker's 3x3 zone on their own half (numbering
  convention in ``CourtCalibration.world_point_to_zone``), from the spiker's
  FEET at the contact frame (looked up retro-actively from a ring buffer,
  because the event arrives ~14+ frames late);
- ``outcome``     -- what happened to the ball: ``kill`` (landed in court
  with no opponent touch, plus ``landing_zone``), ``out`` (landed outside),
  ``dug`` (an opponent kept it up, plus ``dug_zone``), ``blocked``,
  ``kept`` (a same-team touch followed the attack), or ``unknown`` (the
  outcome horizon expired).

It never mutates the emitted actions -- the GT-validated event stream stays
byte-identical; the enrichment rides a parallel record list consumed by the
CSV/stat exporters and by the renderers (red fading trail, KILL marker, typed
spike labels).

Landing detection is image-space on purpose: a 2D ground homography cannot
project an airborne ball onto the court plane (documented failure mode, see
STATUS.md 2026-08-16), so the landing frame is found from the ball's image-y
descent terminating -- either a bounce (y drops again after a max) or the
tracker going quiet after an established descent. Only the LANDDED point
(ball at ground level) is mapped through the homography.
"""

from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

from src.detection.court_calibration import CourtCalibration
from src.output_gen.overlay import LABEL_PERSIST

# Outcome vocabulary (CSV/eval consumers rely on these strings).
OUTCOME_KILL = "kill"
OUTCOME_OUT = "out"
OUTCOME_DUG = "dug"
OUTCOME_BLOCKED = "blocked"
OUTCOME_KEPT = "kept"
OUTCOME_UNKNOWN = "unknown"


class SpikeAnalyzer:
    """Enriches spike events with type/origin-zone/outcome. Pure observer.

    Construct with a calibrated :class:`CourtCalibration`, call
    :meth:`observe` once per frame after the actions are emitted, and read
    :meth:`spike_records` (full-video), :meth:`spike_type_for` /
    :meth:`trail_points` / :meth:`kill_annotation` (renderers).
    """

    # Real ball sightings (frame, x, y, w, h) retained -- ~20 s. The analyzer
    # reconstructs flights retro-actively (events arrive late), so this must
    # comfortably cover the emission lag + the outcome horizon.
    BALL_HISTORY_MAX = 600
    # Per-track (frame, foot) snapshots -- ~13 s, enough to look up the
    # spiker's/digger's feet at a contact frame ~40 frames in the past.
    FOOT_SNAPSHOTS_MAX = 400
    # Spike type: classified by POST-CONTACT ASCENT (image px the ball rises
    # above the contact point). Measured on entreno_3 GT (2026-08-30 diag):
    # the touches launch at 19-29 px/f but rise 146-240 px (high arcs), the
    # hard balls rise <=33 px (flat/downhill; f431 even left near-rest and
    # fell). Raw exit speed CANNOT separate them -- a rainbow's vertical
    # launch is as fast as a drive. Rise is computed over the ATTACK flight
    # only (up to outcome resolution, so a dig's own loft does not count).
    TOUCH_RISE_PX = 80.0
    TYPE_WINDOW = 5           # sightings still used for the audit exit speed
    # Outcome resolution.
    OUTCOME_HORIZON = 90      # frames after contact without resolution -> unknown
    DESCENT_MIN_PX = 4.0      # per-frame image-y gain that counts as descending
    BOUNCE_RISE_PX = 8.0      # later sighting this much higher = bounce after landing
    LANDING_QUIET_FRAMES = 8  # no sightings this long after a descent -> landed
    LANDING_TAIL = 6          # ...landing = max-y sighting among the last N
    LANDING_MARGIN_M = 0.2    # world-metre tolerance for the in/out call
    # Origin zone: the spiker's feet AT the contact frame are airborne on a
    # jump (projected deep by the homography). The takeoff stance is the
    # pre-contact foot position closest to the net in this window.
    TAKEOFF_WINDOW = (-12, -2)
    # A follow contact near a just-committed "landing" converts the record to
    # dug/blocked when the ball subsequently LOFTS far higher than sand can
    # rebound (a dig redirect); a real kill's bounce stays low and its next
    # contact is a different (retrieved/fed) ball. Measured on entreno_3: the
    # four tracked attack flights all loft 220-340 px after the "landing"
    # frame, coinciding with the GT dig events.
    RETRO_FOLLOW_FRAMES = 12
    DIG_LOFT_PX = 90.0

    def __init__(self, court_calibration: CourtCalibration):
        self.court = court_calibration
        self._ball_hist: Deque[Tuple[int, float, float, float, float]] = deque(
            maxlen=self.BALL_HISTORY_MAX
        )
        self._feet: Dict[int, Deque[Tuple[int, Tuple[int, int]]]] = {}
        self._pending: Optional[Dict[str, Any]] = None
        self._records: List[Dict[str, Any]] = []
        self._kill_marks: List[Dict[str, Any]] = []
        self._last_frame: Optional[int] = None

    # --- state management -------------------------------------------------

    def reset(self) -> None:
        """Clear all history/pendings (live-debug 'r' restarts the rally)."""
        self._ball_hist.clear()
        self._feet.clear()
        self._pending = None
        self._records.clear()
        self._kill_marks.clear()
        self._last_frame = None

    def flush(self) -> None:
        """Resolve any pending spike at end of video (best effort)."""
        if self._pending is None:
            return
        self._update_pending()
        p = self._pending
        if p is None:
            return
        # With the video over, an established descent whose sightings stopped
        # is a landing (force the quiet rule; there are no future frames).
        flight = self._flight(p["contact_frame"])
        forced_now = (flight[-1][0] if flight else p["contact_frame"]) + self.LANDING_QUIET_FRAMES
        landing = self._detect_landing(flight, forced_now)
        if landing is None or not self._close_on_landing(*landing):
            self._close(outcome=OUTCOME_UNKNOWN)

    # --- per-frame ingestion ----------------------------------------------

    def observe(
        self,
        frame_number: Optional[int],
        tracked_ball: Optional[Dict[str, Any]],
        tracked_players: Optional[List[Dict[str, Any]]],
        actions: Optional[List[Dict[str, Any]]],
    ) -> None:
        """Ingest one processed frame. Call after the actions are emitted.

        ``frame_number`` may be None for a flush-time, event-only ingestion
        (the classifier's last look-ahead contacts, fed by
        ``FrameProcessor.flush_actions``); the analyzer then reuses the last
        observed frame index.
        """
        if frame_number is None:
            if self._last_frame is None or tracked_ball or tracked_players:
                return
            frame_number = self._last_frame
        self._last_frame = frame_number

        # 1. Real ball sighting (predicted points would smear the trail and
        #    fake landings; same policy as the classifier's _ball_history).
        if tracked_ball and not tracked_ball.get("is_predicted", False):
            center = tracked_ball.get("center")
            bbox = tracked_ball.get("bbox")
            if center and bbox and len(bbox) >= 4:
                w = float(bbox[2] - bbox[0])
                h = float(bbox[3] - bbox[1])
                self._ball_hist.append(
                    (frame_number, float(center[0]), float(center[1]), w, h)
                )

        # 2. Per-track foot snapshots (observed players only -- no ghosts).
        for p in tracked_players or []:
            if p.get("predicted", False):
                continue
            tid = p.get("track_id")
            bbox = p.get("bbox")
            if tid is None or not bbox or len(bbox) < 4:
                continue
            buf = self._feet.setdefault(
                tid, deque(maxlen=self.FOOT_SNAPSHOTS_MAX)
            )
            buf.append((frame_number, CourtCalibration.foot_point(bbox)))

        # 3. Emitted events (true contact frames are in the past).
        for ev in actions or []:
            self._handle_event(ev)

        # 4. Pending-spike progress (type + landing).
        if self._pending is not None:
            self._update_pending()

    # --- event handling -----------------------------------------------------

    def _handle_event(self, ev: Dict[str, Any]) -> None:
        action = ev.get("action")
        contact = ev.get("frame_number")
        if contact is None:
            return

        if self._pending is not None and contact > self._pending["contact_frame"]:
            # Any later contact ends the attack flight.
            self._resolve_follow(ev)
            self._pending = None

        # A landed record may still be converted if this contact is right on
        # top of the "landing" (the ball was actually dug, occluded at the
        # digger's arms -- see RETRO_FOLLOW_FRAMES).
        self._retro_convert(ev)

        if action == "spike":
            self._open_pending(ev)

    def _open_pending(self, ev: Dict[str, Any]) -> None:
        contact = ev["frame_number"]
        track_id = ev.get("track_id")
        zone = self._origin_zone_for_track(track_id, contact)
        if zone is None:
            # Fall back to the event's own geometry (feet unknown).
            for key in ("player_center", "contact_point"):
                pt = ev.get(key)
                if pt:
                    zone = self.court.get_court_zone((pt[0], pt[1]))
                    if zone:
                        break
        self._pending = {
            "contact_frame": contact,
            "track_id": track_id,
            "player_id": ev.get("player_id"),
            "team": ev.get("team"),
            "contact_point": ev.get("contact_point"),
            "attack_zone": {"side": zone[1], "zone": zone[0]} if zone else None,
            "spike_type": None,
            "exit_speed_px": None,
        }

    def _resolve_follow(self, ev: Dict[str, Any]) -> None:
        """Close the pending spike via a follow contact (dig/block/other)."""
        p = self._pending
        team = ev.get("team")
        if team and p["team"] and team != p["team"]:
            outcome = OUTCOME_BLOCKED if ev.get("action") == "block" else OUTCOME_DUG
            dug_zone = self._zone_for_track(ev.get("track_id"), ev["frame_number"])
            if dug_zone is None:
                pt = ev.get("player_center") or ev.get("contact_point")
                if pt:
                    z = self.court.get_court_zone((pt[0], pt[1]))
                    dug_zone = z and {"side": z[1], "zone": z[0]}
            self._close(
                outcome=outcome,
                dug_zone={"side": dug_zone[1], "zone": dug_zone[0]} if dug_zone else None,
            )
        else:
            self._close(outcome=OUTCOME_KEPT)

    def _retro_convert(self, ev: Dict[str, Any]) -> None:
        """Turn a just-committed kill/out into dug/blocked when the contact
        sits on the "landing" frame AND the ball subsequently lofts far
        higher than sand can rebound (a dig redirect, not a bounce)."""
        if not self._records:
            return
        rec = self._records[-1]
        if rec["outcome"] not in (OUTCOME_KILL, OUTCOME_OUT) or rec.get("landing_frame") is None:
            return
        contact = ev.get("frame_number")
        if contact is None or contact <= rec["frame"]:
            return
        delta = contact - rec["landing_frame"]
        if not (-3 <= delta <= self.RETRO_FOLLOW_FRAMES):
            return
        # Loft from the LIVE history (the record's flight snapshot froze at
        # close time; the dig's own loft happens after it).
        flight = self._flight(rec["frame"])
        landing_y = next(
            (y for (f, _x, y) in flight if f == rec["landing_frame"]), None
        )
        if landing_y is None:
            return
        loft = landing_y - min(
            (y for (f, _x, y) in flight if f >= rec["landing_frame"]), default=landing_y
        )
        if loft < self.DIG_LOFT_PX:
            return  # a real sand bounce -- the contact is a different ball
        team = ev.get("team")
        if team and rec["team"] and team != rec["team"]:
            rec["outcome"] = (
                OUTCOME_BLOCKED if ev.get("action") == "block" else OUTCOME_DUG
            )
            dug = self._zone_for_track(ev.get("track_id"), contact)
            if dug is None:
                pt = ev.get("player_center") or ev.get("contact_point")
                if pt:
                    dug = self.court.get_court_zone((pt[0], pt[1]))
            rec["dug_zone"] = (
                {"side": dug[1], "zone": dug[0]} if dug else rec.get("dug_zone")
            )
            rec["landing_zone"] = None
            self._sync_kill_marks()

    def _sync_kill_marks(self) -> None:
        """Drop kill marks whose record is no longer a kill (retro-conversion)."""
        self._kill_marks = [
            m for m in self._kill_marks
            if m.get("record") is None or m["record"]["outcome"] == OUTCOME_KILL
        ]

    # --- pending progress ---------------------------------------------------

    def _flight(self, contact_frame: int) -> List[Tuple[int, float, float]]:
        """Real ball sightings strictly after the contact frame."""
        return [
            (f, x, y)
            for (f, x, y, _w, _h) in self._ball_hist
            if f > contact_frame
        ]

    def _update_pending(self) -> None:
        p = self._pending
        now = self._last_frame
        if p is None or now is None:
            return

        flight = self._flight(p["contact_frame"])

        # Type: classify once, from the first window of sightings.
        if p["spike_type"] is None:
            p["spike_type"], p["exit_speed_px"] = self._classify_type(
                p["contact_frame"], flight
            )

        # Landing: bounce (max-y sighting with a later clear rise) or loss
        # (quiet after an established descent).
        landing = self._detect_landing(flight, now)
        if landing is not None and self._close_on_landing(*landing):
            return

        if now > p["contact_frame"] + self.OUTCOME_HORIZON:
            self._close(outcome=OUTCOME_UNKNOWN)

    def _close_on_landing(
        self, landing_frame: int, landing_pt: Tuple[float, float]
    ) -> bool:
        """Close the pending spike as kill/out at a detected landing."""
        world = self.court.image_to_world(landing_pt)
        if world is None:
            return False
        m = self.LANDING_MARGIN_M
        inside = (
            -m <= world[0] <= self.court.BEACH_COURT_WIDTH_M + m
            and -m <= world[1] <= self.court.BEACH_COURT_LENGTH_M + m
        )
        zone = self.court.world_point_to_zone(world[0], world[1])
        self._close(
            outcome=OUTCOME_KILL if inside else OUTCOME_OUT,
            landing_frame=landing_frame,
            landing_zone={"side": zone[1], "zone": zone[0]} if zone else None,
        )
        return True

    def _classify_type(
        self, contact_frame: int, flight: List[Tuple[int, float, float]]
    ) -> Tuple[Optional[str], Optional[float]]:
        """Ascent-based classification plus the audit exit speed.

        Returns (spike_type, exit_speed_px). ``touch`` is decided the moment
        the ball rises TOUCH_RISE_PX above the contact point (arcs develop
        fast); ``hard`` is only final at close time, when the whole attack
        flight never rose that high. Exit speed (median px/frame over the
        first TYPE_WINDOW sightings) is recorded for audit only -- it does
        NOT separate the classes (see TOUCH_RISE_PX).
        """
        contact_point = (
            self._pending["contact_point"] if self._pending else None
        )
        base_y = float(contact_point[1]) if contact_point else None
        if base_y is not None:
            rise = base_y - min((y for (_f, _x, y) in flight), default=base_y)
            if rise >= self.TOUCH_RISE_PX:
                return "touch", self._exit_speed(contact_frame, flight)
        return None, self._exit_speed(contact_frame, flight)

    def _exit_speed(
        self, contact_frame: int, flight: List[Tuple[int, float, float]]
    ) -> Optional[float]:
        """Median px/frame over the first TYPE_WINDOW post-contact sightings."""
        window = flight[: self.TYPE_WINDOW]
        if len(window) < 2:
            return None
        speeds = []
        prev = self._pending["contact_point"] if self._pending else None
        prev_f = contact_frame
        for (f, x, y) in window:
            if prev is not None and f > prev_f:
                speeds.append(
                    ((x - prev[0]) ** 2 + (y - prev[1]) ** 2) ** 0.5 / (f - prev_f)
                )
            prev, prev_f = (x, y), f
        if not speeds:
            return None
        speeds.sort()
        return speeds[len(speeds) // 2]

    def _detect_landing(
        self, flight: List[Tuple[int, float, float]], now: int
    ) -> Optional[Tuple[int, Tuple[float, float]]]:
        """Landing frame+point from the image-y descent terminating.

        (a) Bounce: the max-y sighting with a later sighting clearly higher.
        (b) Loss: an established descent, then no sighting for
            LANDING_QUIET_FRAMES -- the landing is the max-y sighting among
            the last LANDING_TAIL (covers hard-driven balls the tracker loses
            to motion blur, and sand kills that roll).
        """
        if len(flight) < 2:
            return None
        ys = [y for (_f, _x, y) in flight]
        # Established descent?
        dy = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
        if not any(d >= self.DESCENT_MIN_PX for d in dy):
            return None

        # (a) Bounce: global max-y with a later clear rise.
        m = max(range(len(ys)), key=lambda i: ys[i])
        for j in range(m + 1, len(ys)):
            if ys[m] - ys[j] >= self.BOUNCE_RISE_PX:
                f_m, x_m, y_m = flight[m]
                return f_m, (x_m, y_m)

        # (b) Loss: quiet since the last sighting.
        last_f = flight[-1][0]
        if now - last_f >= self.LANDING_QUIET_FRAMES:
            tail = flight[-self.LANDING_TAIL :]
            t = max(range(len(tail)), key=lambda i: tail[i][2])
            f_t, x_t, y_t = tail[t]
            return f_t, (x_t, y_t)
        return None

    # --- closing ------------------------------------------------------------

    def _close(
        self,
        outcome: str,
        landing_frame: Optional[int] = None,
        landing_zone: Optional[Dict[str, Any]] = None,
        dug_zone: Optional[Dict[str, Any]] = None,
    ) -> None:
        p = self._pending
        flight = self._flight(p["contact_frame"])
        if p["spike_type"] is None:
            p["spike_type"], p["exit_speed_px"] = self._classify_type(
                p["contact_frame"], flight
            )
        # Still undecided at close = the flight never rose TOUCH_RISE_PX.
        if p["spike_type"] is None:
            p["spike_type"] = "hard" if flight else "unknown"

        trail = []
        cp = p.get("contact_point")
        if cp:
            trail.append((p["contact_frame"], float(cp[0]), float(cp[1])))
        trail.extend(flight)

        record = {
            "frame": p["contact_frame"],
            "track_id": p["track_id"],
            "player_id": p["player_id"],
            "team": p["team"],
            "spike_type": p["spike_type"],
            "attack_zone": p["attack_zone"],
            "outcome": outcome,
            "landing_zone": landing_zone,
            "dug_zone": dug_zone,
            "exit_speed_px": (
                round(p["exit_speed_px"], 2) if p["exit_speed_px"] is not None else None
            ),
            "flight_frames": (flight[-1][0] - p["contact_frame"]) if flight else 0,
            "resolution_frame": self._last_frame,
            "landing_frame": landing_frame,
            "flight": trail,
        }
        self._records.append(record)
        if outcome == OUTCOME_KILL and landing_zone:
            lp = next(
                ((x, y) for (f, x, y) in flight if f == landing_frame), None
            )
            if lp is not None:
                self._kill_marks.append(
                    {
                        "frame": landing_frame,
                        "x": lp[0],
                        "y": lp[1],
                        "text": "KILL {}{}".format(landing_zone["side"], landing_zone["zone"]),
                        "record": record,
                    }
                )
        self._pending = None

    # --- render/consumer queries ---------------------------------------------

    def spike_records(self) -> List[Dict[str, Any]]:
        """All resolved spike records (copy; safe for CSV/export consumers)."""
        return [dict(r, flight=list(r["flight"])) for r in self._records]

    def spike_type_for(self, contact_frame: Optional[int]) -> Optional[str]:
        """Type for the spike with this contact frame, if classified yet."""
        if contact_frame is None:
            return None
        if self._pending and self._pending["contact_frame"] == contact_frame:
            return self._pending["spike_type"]
        for r in self._records:
            if r["frame"] == contact_frame:
                return r["spike_type"]
        return None

    def trail_points(self, frame_idx: int) -> List[Tuple[float, float, int]]:
        """Ball trail for rendering: ``(x, y, age_frames)`` for every flight
        point at or before ``frame_idx``. The renderer fades by age and drops
        points past its max age."""
        flights: List[List[Tuple[int, float, float]]] = []
        if self._pending is not None:
            cp = self._pending.get("contact_point")
            pending_flight = self._flight(self._pending["contact_frame"])
            if cp:
                pending_flight = [
                    (self._pending["contact_frame"], float(cp[0]), float(cp[1]))
                ] + pending_flight
            flights.append(pending_flight)
        flights.extend(r.get("flight") or [] for r in self._records)
        pts = []
        for flight in flights:
            for (f, x, y) in flight:
                if f <= frame_idx:
                    pts.append((x, y, frame_idx - f))
        return pts

    def kill_annotation(self, frame_idx: int, persist: int = LABEL_PERSIST) -> Optional[Tuple[float, float, str]]:
        """Active kill marker for this rendered frame, else None."""
        for m in self._kill_marks:
            if m["frame"] is not None and m["frame"] <= frame_idx < m["frame"] + persist:
                return (m["x"], m["y"], m["text"])
        return None

    # --- helpers -------------------------------------------------------------

    def _zone_for_track(
        self, track_id: Optional[int], contact_frame: int
    ) -> Optional[Tuple[int, str]]:
        """(zone, side) of a track's feet at ~contact_frame (nearest snapshot
        within 3 frames)."""
        if track_id is None:
            return None
        buf = self._feet.get(track_id)
        if not buf:
            return None
        best = None
        for (f, foot) in buf:
            d = abs(f - contact_frame)
            if d <= 3 and (best is None or d < best[0]):
                best = (d, foot)
        if best is None:
            return None
        return self.court.get_court_zone(best[1])

    def _origin_zone_for_track(
        self, track_id: Optional[int], contact_frame: int
    ) -> Optional[Tuple[int, str]]:
        """The spiker's takeoff zone.

        At the contact frame a jumping attacker's feet are ~0.5-1 m off the
        sand, and the ground homography projects them deep into the court
        (entreno_3 f431: GT takeoff B2 read as B5). The takeoff stance is the
        pre-contact foot snapshot CLOSEST TO THE NET inside TAKEOFF_WINDOW;
        falls back to the at-contact snapshot, then the event's own geometry.
        """
        if track_id is None:
            return None
        buf = self._feet.get(track_id)
        if not buf:
            return None
        lo, hi = self.TAKEOFF_WINDOW
        best = None
        for (f, foot) in buf:
            if not (contact_frame + lo <= f <= contact_frame + hi):
                continue
            dist = self.court.world_dist_from_net(foot)
            if dist is not None and (best is None or dist < best[0]):
                best = (dist, foot)
        if best is not None:
            zone = self.court.get_court_zone(best[1])
            if zone:
                return zone
        return self._zone_for_track(track_id, contact_frame)
