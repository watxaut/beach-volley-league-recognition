"""Tests for the DB layer: schema, ingest upsert semantics, labels, metrics.

Fixture payloads are hand-computed canonical JSON (schema_version 1) so the
expected metric numbers below are arithmetic, not re-derivations of pipeline
output.
"""

import json

import pytest

from src.db import labels as L
from src.db import metrics as M
from src.db.ingest import ingest_payload, resolve_json_paths
from src.db.schema import connect, init_db


@pytest.fixture
def conn(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    yield conn
    conn.close()


def _spike(frame, track_id, team, stype, azone, outcome, **over):
    base = {
        "frame": frame,
        "track_id": track_id,
        "player_id": track_id,
        "team": team,
        "spike_type": stype,
        "attack_zone": azone,
        "outcome": outcome,
        "landing_zone": None,
        "dug_zone": None,
        "exit_speed_px": 25.0,
        "flight_frames": 30,
        "resolution_frame": frame + 30,
    }
    base.update(over)
    return base


def _action(frame, track_id, action, team, rally=1, **over):
    base = {
        "track_id": track_id,
        "player_id": track_id,
        "action": action,
        "gesture": "bump",
        "confidence": 0.6,
        "frame_number": frame,
        "contact_point": [10.0, 20.0],
        "team": team,
        "team_in_possession": team,
        "touch_number": 1,
        "rally_id": rally,
        "contact_kind": "normal",
    }
    base.update(over)
    return base


def _payload(video_key="v1", actions=(), spikes=(), **video_over):
    video = {
        "key": video_key,
        "path": f"resources/{video_key}.mp4",
        "fps": 30.0,
        "width": 1920,
        "height": 1080,
        "total_frames": 900,
    }
    video.update(video_over)
    return {
        "schema_version": 1,
        "video": video,
        "processed_at": "2026-09-05T00:00:00+00:00",
        "pipeline_version": "deadbee",
        "actions": list(actions),
        "spikes": list(spikes),
    }


class TestIngest:
    def test_ingest_then_reingest_is_idempotent(self, conn):
        payload = _payload(actions=[_action(10, 1, "serve", "A")])
        first = ingest_payload(conn, payload)
        second = ingest_payload(conn, payload)
        assert first == second == {"video_key_len": 1, "actions": 1, "spikes": 0}
        assert conn.execute("SELECT COUNT(*) c FROM actions").fetchone()["c"] == 1

    def test_reingest_replaces_video_rows(self, conn):
        ingest_payload(conn, _payload(actions=[_action(10, 1, "serve", "A")]))
        ingest_payload(conn, _payload(actions=[
            _action(10, 1, "serve", "A"), _action(50, 2, "dig", "B"),
        ]))
        assert conn.execute("SELECT COUNT(*) c FROM actions").fetchone()["c"] == 2

    def test_reingest_preserves_labels_and_players(self, conn):
        ingest_payload(conn, _payload(actions=[_action(10, 1, "serve", "A")]))
        L.set_label(conn, "v1", 1, "Ana", "A")
        n_players = conn.execute("SELECT COUNT(*) c FROM players").fetchone()["c"]
        assert n_players == 1

        ingest_payload(conn, _payload(actions=[_action(10, 1, "serve", "A")]))
        assert L.labels_for_video(conn, "v1") == {
            1: {"player_id": 1, "name": "Ana", "team": "A"}
        }
        # players table untouched by ingest
        assert conn.execute("SELECT COUNT(*) c FROM players").fetchone()["c"] == 1

    def test_reingest_one_video_leaves_others_alone(self, conn):
        ingest_payload(conn, _payload("v1", actions=[_action(10, 1, "serve", "A")]))
        ingest_payload(conn, _payload("v2", actions=[
            _action(10, 1, "serve", "A"), _action(20, 2, "dig", "B"),
        ]))
        ingest_payload(conn, _payload("v1", actions=[_action(10, 1, "serve", "A")]))
        assert conn.execute(
            "SELECT COUNT(*) c FROM actions WHERE video_key='v2'"
        ).fetchone()["c"] == 2

    def test_rejects_bad_schema_version(self, conn):
        payload = _payload()
        payload["schema_version"] = 99
        with pytest.raises(Exception):
            ingest_payload(conn, payload)

    def test_rejects_missing_video_key(self, conn):
        payload = _payload()
        payload["video"]["key"] = None
        with pytest.raises(Exception):
            ingest_payload(conn, payload)

    def test_resolve_json_paths(self, tmp_path, monkeypatch):
        (tmp_path / "output" / "v1").mkdir(parents=True)
        (tmp_path / "output" / "v2").mkdir(parents=True)
        (tmp_path / "output" / "v1" / "pipeline_output.json").write_text("{}")
        (tmp_path / "output" / "v2" / "pipeline_output.json").write_text("{}")

        # Direct file
        p = tmp_path / "output" / "v1" / "pipeline_output.json"
        assert resolve_json_paths(p) == [p]
        # Output dir containing it
        assert resolve_json_paths(tmp_path / "output" / "v1") == [p]
        # Parent dir sweeps subdirs, sorted
        assert resolve_json_paths(tmp_path / "output") == [
            tmp_path / "output" / "v1" / "pipeline_output.json",
            tmp_path / "output" / "v2" / "pipeline_output.json",
        ]

        # Bare stem resolves against ./output (cwd-relative like production)
        monkeypatch.chdir(tmp_path)
        found = resolve_json_paths("v2")
        assert [f.resolve() for f in found] == [
            (tmp_path / "output" / "v2" / "pipeline_output.json").resolve()
        ]


class TestMetrics:
    @pytest.fixture
    def seeded(self, conn):
        """Two videos, two labeled players, hand-computed numbers."""
        ingest_payload(conn, _payload("v1",
            actions=[
                _action(10, 1, "serve", "A", rally=1),
                _action(60, 1, "set", "A", rally=1),
                _action(105, 1, "dig", "A", rally=1),      # spike@100 by B -> Ana digs
                _action(155, 1, "dig", "A", rally=2),      # spike@150 by B
                _action(500, 1, "block", "A", rally=1),    # last of rally 1 -> kill block
                _action(700, 1, "block", "A", rally=2),    # followed by dig@750 -> soft
                _action(750, 2, "dig", "B", rally=2),
            ],
            spikes=[
                _spike(100, 1, "A", "hard", "A1", "kill", landing_zone="B7"),
                _spike(200, 1, "A", "hard", "A2", "kill", landing_zone="B8"),
                _spike(300, 1, "A", "hard", "A1", "out", landing_zone="B3"),
                _spike(400, 1, "A", "touch", "A4", "dug", dug_zone="B5"),
                _spike(150, 2, "B", "hard", "B3", "kill", landing_zone="A6"),
                _spike(160, 2, "B", "hard", "B2", "out", landing_zone="A1"),
                _spike(170, 2, "B", "hard", "B3", "dug", dug_zone="A5"),
            ],
        ))
        L.set_label(conn, "v1", 1, "Ana", "A")
        L.set_label(conn, "v1", 2, "Bea", "B")
        return conn

    def test_player_metrics_ana(self, seeded):
        m = M.player_metrics(seeded, 1)  # Ana = track 1
        assert m["player"]["name"] == "Ana"
        assert m["attacks"] == 4
        assert m["kills"] == 2 and m["kill_pct"] == 50.0
        assert m["outs"] == 1 and m["error_pct"] == 25.0
        assert m["dug_opponent_kept"] == 1 and m["dug_pct"] == 25.0
        assert m["spike_hard"] == 3 and m["hard_pct"] == 75.0
        assert m["spike_touch"] == 1 and m["touch_pct"] == 25.0
        assert m["attack_zones"] == {"A1": 2, "A2": 1, "A4": 1}
        assert m["placement"] == [
            {"attack_zone": "A1", "landing_zone": "B3", "count": 1},
            {"attack_zone": "A1", "landing_zone": "B7", "count": 1},
            {"attack_zone": "A2", "landing_zone": "B8", "count": 1},
        ]
        assert m["digs"] == 2
        # Ana's dominant team A -> opponent attacks = 3 B-team spikes
        assert m["dig_opportunities"] == 3
        assert m["dig_pct"] == 66.7
        assert m["blocks"] == 2 and m["kill_blocks"] == 1 and m["soft_blocks"] == 1
        assert m["serves"] == 1 and m["sets"] == 1

    def test_player_metrics_bea(self, seeded):
        m = M.player_metrics(seeded, 2)  # Bea = track 2
        assert m["attacks"] == 3
        assert m["kills"] == 1 and m["kill_pct"] == 33.3
        assert m["digs"] == 1
        # Bea's dominant team B -> opponent attacks = 4 A-team spikes
        assert m["dig_opportunities"] == 4
        assert m["dig_pct"] == 25.0
        assert m["blocks"] == 0

    def test_per_video_splits(self, seeded):
        m = M.player_metrics(seeded, 1)
        (row,) = m["per_video"]
        assert row["video_key"] == "v1"
        assert row["team"] == "A"
        assert row["attacks"] == 4 and row["kills"] == 2 and row["digs"] == 2

    def test_unlabeled_tracks(self, conn):
        ingest_payload(conn, _payload("v1", actions=[
            _action(10, 1, "serve", "A"), _action(20, 3, "dig", "B"),
        ]))
        unlabeled = M.unlabeled_tracks(conn)
        assert [(u["video_key"], u["track_id"]) for u in unlabeled] == [("v1", 1), ("v1", 3)]
        L.set_label(conn, "v1", 1, "Ana", "A")
        unlabeled = M.unlabeled_tracks(conn)
        assert [(u["video_key"], u["track_id"]) for u in unlabeled] == [("v1", 3)]

    def test_zero_denominators_render_none(self, conn):
        ingest_payload(conn, _payload("v1", actions=[_action(10, 1, "serve", "A")]))
        L.set_label(conn, "v1", 1, "Ana", "A")
        m = M.player_metrics(conn, 1)
        assert m["attacks"] == 0
        assert m["kill_pct"] is None and m["dig_pct"] is None

    def test_classify_blocks_kills_and_soft(self, conn):
        ingest_payload(conn, _payload("v1", actions=[
            _action(100, 1, "block", "A", rally=1),  # nothing after -> kill
            _action(200, 1, "block", "A", rally=2),  # dig follows -> soft
            _action(260, 2, "dig", "B", rally=2),
            _action(300, 1, "block", "A", rally=3),  # spike by B follows -> soft
            _action(360, 2, "spike", "B", rally=3),
        ]))
        blocks = M.video_actions(conn, "v1")
        classified = M.classify_blocks(conn, "v1")
        ids = [b for b in conn.execute(
            "SELECT id FROM actions WHERE action='block' ORDER BY frame"
        ).fetchall()]
        assert [classified[r["id"]] for r in ids] == ["kill_block", "soft_block", "soft_block"]

    def test_list_videos_counts(self, seeded):
        rows = M.list_videos(seeded)
        (v1,) = rows
        assert v1["video_key"] == "v1"
        assert v1["n_actions"] == 7
        assert v1["n_spikes"] == 7
        assert v1["n_tracks"] == 2
        assert v1["n_labels"] == 2

    def test_video_actions_resolve_names(self, seeded):
        actions = M.video_actions(seeded, "v1")
        serve = next(a for a in actions if a["action"] == "serve")
        assert serve["player_name"] == "Ana"
        dig = next(a for a in actions if a["action"] == "dig" and a["team"] == "B")
        assert dig["player_name"] == "Bea"


class TestLabels:
    def test_set_update_clear(self, conn):
        ingest_payload(conn, _payload("v1", actions=[_action(10, 1, "serve", "A")]))
        L.set_label(conn, "v1", 1, "Ana", "A")
        L.set_label(conn, "v1", 1, "Ana G.", "A")  # update same slot, new player
        labels = L.labels_for_video(conn, "v1")
        assert labels[1]["name"] == "Ana G."
        L.clear_label(conn, "v1", 1)
        assert L.labels_for_video(conn, "v1") == {}

    def test_player_name_uniqueness(self, conn):
        ingest_payload(conn, _payload("v1", actions=[_action(10, 1, "serve", "A")]))
        ingest_payload(conn, _payload("v2", actions=[_action(10, 3, "serve", "B")]))
        L.set_label(conn, "v1", 1, "Ana", "A")
        L.set_label(conn, "v2", 3, "Ana", "B")  # same human, other video
        assert conn.execute("SELECT COUNT(*) c FROM players").fetchone()["c"] == 1
        players = L.all_players(conn)
        assert players[0]["n_videos"] == 2

    def test_empty_name_rejected(self, conn):
        with pytest.raises(ValueError):
            L.get_or_create_player(conn, "  ")
