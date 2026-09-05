"""Player / video metrics computed from the analysis database.

All percentages guard division by zero (None renders as "—" in the UI).

Metric glossary (ratified 2026-09-05):
- attacks ............ spike records attributed to the player's tracks
- kill% .............. kills / attacks            (spike outcome == kill)
- error% (attack) .... outs / attacks             (spike outcome == out)
- dug% ............... dugs / attacks             (opponent kept it up)
- hard% / touch% ..... spike_type split over attacks
- attack zones ....... counts of spikes per attack_zone ("B3"-style keys)
- placement .......... attack_zone x landing_zone counts (kill/out landings)
- court attack ....... takeoff-zone counts keyed by zone DIGIT 1-9 (team
                       letter stripped) -- the drawing is per-perspective, so
                       the side letter carries no extra information
- court landing ...... where attacks end, keyed by digit 1-9: kill/out ->
                       landing_zone, dug -> dug_zone (the ball came down on
                       the defender at that spot); plus a per-zone outcome
                       breakdown for the UI cell tooltips
- digs ............... action == dig
- dig% ............... digs / opponent attacks. Per video, the player's
                       opponent side is derived from the player's dominant
                       team (mode of their action teams in that video);
                       denominator = spikes in that video by the OTHER team.
- blocks ............. action == block -- ball-touching by construction
                       (the pipeline cannot emit no-touch blocks; owner rule
                       2026-09-05: kill/soft blocks only, others disregarded)
  - kill block ....... the block is the LAST action of its rally (ball died
                       on the attacker's side, rally over)
  - soft block ....... a subsequent action in the same rally followed it
                       (deflection kept in play)
- serves / sets ...... action counts (assist proxy parked with aces)
- aces ............... PARKED (open point: needs point-outcome detection or
                       ratification of a derived heuristic)
"""

import sqlite3
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Sequence


def _pct(numerator: int, denominator: int) -> Optional[float]:
    """Percentage in 0-100, or None when the denominator is zero."""
    return round(100.0 * numerator / denominator, 1) if denominator else None


# --- scope helpers -----------------------------------------------------------


def list_videos(conn: sqlite3.Connection) -> List[Dict]:
    """All ingested videos with row counts and labeling status."""
    return [
        dict(r)
        for r in conn.execute(
            """SELECT v.video_key, v.path, v.fps, v.total_frames,
                      v.processed_at, v.pipeline_version,
                      (SELECT COUNT(*) FROM actions a  WHERE a.video_key  = v.video_key) AS n_actions,
                      (SELECT COUNT(*) FROM spikes s  WHERE s.video_key  = v.video_key) AS n_spikes,
                      (SELECT COUNT(DISTINCT track_id) FROM actions
                        WHERE video_key = v.video_key AND track_id IS NOT NULL) AS n_tracks,
                      (SELECT COUNT(*) FROM video_players vp WHERE vp.video_key = v.video_key) AS n_labels
               FROM videos v
               ORDER BY v.video_key"""
        ).fetchall()
    ]


def video_actions(conn: sqlite3.Connection, video_key: str) -> List[Dict]:
    """Action timeline with resolved player names, frame-ordered."""
    return [
        dict(r)
        for r in conn.execute(
            """SELECT a.id, a.frame, a.ts, a.track_id, a.action, a.gesture,
                      a.confidence, a.team, a.team_in_possession,
                      a.touch_number, a.rally_id, a.contact_kind,
                      p.id AS player_id, p.name AS player_name
               FROM actions a
               LEFT JOIN video_players vp
                      ON vp.video_key = a.video_key AND vp.track_id = a.track_id
               LEFT JOIN players p ON p.id = vp.player_id
               WHERE a.video_key = ?
               ORDER BY a.frame, a.id""",
            (video_key,),
        ).fetchall()
    ]


def video_spikes(conn: sqlite3.Connection, video_key: str) -> List[Dict]:
    """Spike records with resolved player names, frame-ordered."""
    return [
        dict(r)
        for r in conn.execute(
            """SELECT s.frame, s.track_id, s.team, s.spike_type, s.attack_zone,
                      s.outcome, s.landing_zone, s.dug_zone, s.exit_speed_px,
                      s.flight_frames, s.resolution_frame,
                      p.id AS player_id, p.name AS player_name
               FROM spikes s
               LEFT JOIN video_players vp
                      ON vp.video_key = s.video_key AND vp.track_id = s.track_id
               LEFT JOIN players p ON p.id = vp.player_id
               WHERE s.video_key = ?
               ORDER BY s.frame, s.id""",
            (video_key,),
        ).fetchall()
    ]


# --- block classification -----------------------------------------------------


def classify_blocks(conn: sqlite3.Connection, video_key: str) -> Dict[int, str]:
    """block action id -> "kill_block" | "soft_block".

    Kill block: no subsequent action in the same rally (the rally died with
    the block -- ball on the attacker's sand). Soft block: any later action
    in the rally followed (deflection kept in play).
    """
    blocks = conn.execute(
        """SELECT id, rally_id, frame FROM actions
           WHERE video_key = ? AND action = 'block'""",
        (video_key,),
    ).fetchall()
    out: Dict[int, str] = {}
    for b in blocks:
        row = conn.execute(
            """SELECT COUNT(*) AS n FROM actions
               WHERE video_key = ? AND rally_id IS ? AND frame > ?""",
            (video_key, b["rally_id"], b["frame"]),
        ).fetchone()
        out[b["id"]] = "kill_block" if row["n"] == 0 else "soft_block"
    return out


# --- per-player metrics --------------------------------------------------------


def _player_video_keys(conn: sqlite3.Connection, player_id: int) -> List[str]:
    return [
        r["video_key"]
        for r in conn.execute(
            """SELECT DISTINCT vp.video_key FROM video_players vp
               WHERE vp.player_id = ? ORDER BY vp.video_key""",
            (player_id,),
        ).fetchall()
    ]


def _dominant_team(conn: sqlite3.Connection, video_key: str, track_id: int) -> Optional[str]:
    """Mode of this track's action teams in this video (sides can swap)."""
    rows = conn.execute(
        """SELECT team, COUNT(*) AS n FROM actions
           WHERE video_key = ? AND track_id = ? AND team IS NOT NULL
           GROUP BY team ORDER BY n DESC""",
        (video_key, track_id),
    ).fetchall()
    return rows[0]["team"] if rows else None


def player_metrics(conn: sqlite3.Connection, player_id: int) -> Optional[Dict]:
    """Full metric bundle for one labeled player across all their videos."""
    from .labels import all_players

    name = next((p["name"] for p in all_players(conn) if p["id"] == player_id), None)
    if name is None:
        return None

    video_keys = _player_video_keys(conn, player_id)
    tracks = conn.execute(
        """SELECT video_key, track_id FROM video_players WHERE player_id = ?""",
        (player_id,),
    ).fetchall()

    # --- attacks (spike records) ---
    spikes: List[Dict] = []
    for t in tracks:
        spikes.extend(
            dict(r)
            for r in conn.execute(
                "SELECT * FROM spikes WHERE video_key = ? AND track_id = ?",
                (t["video_key"], t["track_id"]),
            ).fetchall()
        )

    outcomes = Counter(s["outcome"] or "unknown" for s in spikes)
    types = Counter(s["spike_type"] or "unknown" for s in spikes)
    attack_zones = Counter(s["attack_zone"] for s in spikes if s["attack_zone"])
    placement: Counter = Counter(
        (s["attack_zone"], s["landing_zone"])
        for s in spikes
        if s["attack_zone"] and s["landing_zone"]
    )

    attacks = len(spikes)
    kills = outcomes.get("kill", 0)
    outs = outcomes.get("out", 0)
    dugs = outcomes.get("dug", 0)

    # Court-heatmap marginals: zone digit only (letter stripped). The 9-zone
    # grid is 180-degree symmetric, so "digit on the player's own half" is
    # side-independent and both halves of the drawing use one key space.
    court_attack: Counter = Counter(
        {int(zone[-1]): n for zone, n in attack_zones.items()}
    )
    court_landing: Counter = Counter()
    court_landing_outcomes: Dict[int, Counter] = defaultdict(Counter)
    for s in spikes:
        zone = s["dug_zone"] if s["outcome"] == "dug" else s["landing_zone"]
        if zone:
            court_landing[int(zone[-1])] += 1
            court_landing_outcomes[int(zone[-1])][s["outcome"] or "unknown"] += 1

    # --- touch actions ---
    action_counts: Counter = Counter()
    per_video_actions: Dict[str, Counter] = defaultdict(Counter)
    for t in tracks:
        for r in conn.execute(
            "SELECT action FROM actions WHERE video_key = ? AND track_id = ?",
            (t["video_key"], t["track_id"]),
        ).fetchall():
            action_counts[r["action"]] += 1
            per_video_actions[t["video_key"]][r["action"]] += 1

    # --- digs and opponent-attack denominator ---
    dig_count = action_counts.get("dig", 0)
    dig_opportunities = 0
    for t in tracks:
        team = _dominant_team(conn, t["video_key"], t["track_id"])
        if team is None:
            continue
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM spikes WHERE video_key = ? AND team IS NOT ?",
            (t["video_key"], team),
        ).fetchone()
        dig_opportunities += row["n"]

    # --- blocks (kill/soft derived from rally continuation) ---
    blocks: Counter = Counter()
    for t in tracks:
        classified = classify_blocks(conn, t["video_key"])
        track_block_ids = {
            r["id"]
            for r in conn.execute(
                "SELECT id FROM actions WHERE video_key = ? AND track_id = ? AND action = 'block'",
                (t["video_key"], t["track_id"]),
            ).fetchall()
        }
        for bid in track_block_ids:
            blocks[classified.get(bid, "soft_block")] += 1

    per_video = [
        {
            "video_key": t["video_key"],
            "team": _dominant_team(conn, t["video_key"], t["track_id"]),
            "attacks": 0,
            "kills": 0,
            "digs": per_video_actions[t["video_key"]].get("dig", 0),
            "blocks": per_video_actions[t["video_key"]].get("block", 0),
            "serves": per_video_actions[t["video_key"]].get("serve", 0),
            "sets": per_video_actions[t["video_key"]].get("set", 0),
        }
        for t in tracks
    ]
    video_attacks = Counter()
    video_kills = Counter()
    for s in spikes:
        video_attacks[s["video_key"]] += 1
        if s["outcome"] == "kill":
            video_kills[s["video_key"]] += 1
    for row in per_video:
        row["attacks"] = video_attacks.get(row["video_key"], 0)
        row["kills"] = video_kills.get(row["video_key"], 0)

    return {
        "player": {"id": player_id, "name": name},
        "n_videos": len(video_keys),
        "video_keys": video_keys,
        "attacks": attacks,
        "kills": kills,
        "outs": outs,
        "dug_opponent_kept": dugs,
        "kill_pct": _pct(kills, attacks),
        "error_pct": _pct(outs, attacks),
        "dug_pct": _pct(dugs, attacks),
        "spike_hard": types.get("hard", 0),
        "spike_touch": types.get("touch", 0),
        "hard_pct": _pct(types.get("hard", 0), attacks),
        "touch_pct": _pct(types.get("touch", 0), attacks),
        "attack_zones": dict(sorted(attack_zones.items())),
        "court_attack": dict(sorted(court_attack.items())),
        "court_landing": dict(sorted(court_landing.items())),
        "court_landing_outcomes": {
            z: dict(sorted(c.items())) for z, c in sorted(court_landing_outcomes.items())
        },
        "placement": [
            {"attack_zone": az, "landing_zone": lz, "count": n}
            for (az, lz), n in sorted(placement.items())
        ],
        "digs": dig_count,
        "dig_opportunities": dig_opportunities,
        "dig_pct": _pct(dig_count, dig_opportunities),
        "blocks": sum(blocks.values()),
        "kill_blocks": blocks.get("kill_block", 0),
        "soft_blocks": blocks.get("soft_block", 0),
        "serves": action_counts.get("serve", 0),
        "sets": action_counts.get("set", 0),
        "per_video": per_video,
    }


def players_overview(conn: sqlite3.Connection) -> List[Dict]:
    """Summary row per labeled player (players_overview page)."""
    from .labels import all_players

    rows = []
    for p in all_players(conn):
        m = player_metrics(conn, p["id"])
        rows.append({
            "id": p["id"],
            "name": p["name"],
            "n_videos": p["n_videos"],
            "attacks": m["attacks"],
            "kills": m["kills"],
            "kill_pct": m["kill_pct"],
            "digs": m["digs"],
            "dig_pct": m["dig_pct"],
            "blocks": m["blocks"],
            "serves": m["serves"],
            "sets": m["sets"],
        })
    return rows


def unlabeled_tracks(conn: sqlite3.Connection) -> List[Dict]:
    """Tracks that appear in actions/spikes but carry no player label."""
    rows = conn.execute(
        """SELECT a.video_key, a.track_id, COUNT(*) AS n_actions
           FROM actions a
           LEFT JOIN video_players vp
                  ON vp.video_key = a.video_key AND vp.track_id = a.track_id
           WHERE a.track_id IS NOT NULL AND vp.player_id IS NULL
           GROUP BY a.video_key, a.track_id
           ORDER BY a.video_key, a.track_id"""
    ).fetchall()
    return [dict(r) for r in rows]
