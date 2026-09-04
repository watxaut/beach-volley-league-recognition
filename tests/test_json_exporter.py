"""Tests for the canonical JSON exporter (the DB ingest contract).

Field parity matters more than formatting: every emitted action keeps its
full field set (the CSVs drop team/touch_number/rally_id/contact_kind) and
spike records are flattened to DB-ready zone keys without the flight array.
"""

from src.output_gen.json_exporter import JSONExporter


def _action(frame_number, track_id=1, action="dig", **over):
    base = {
        "track_id": track_id,
        "player_id": 2,
        "action": action,
        "gesture": "bump",
        "confidence": 0.55,
        "frame_number": frame_number,
        "contact_point": [100.0, 200.0],
        "player_center": (50, 60),
        "team": "A",
        "team_in_possession": "A",
        "touch_number": 1,
        "rally_id": 3,
        "contact_kind": "normal",
    }
    base.update(over)
    return base


def _results(actions_by_frame, spikes=None, path="resources/foo.mp4", tracked=None):
    frame_results = [
        {"frame_index": f, "actions": acts} for f, acts in actions_by_frame.items()
    ]
    if tracked is not None:
        for fr in frame_results:
            fr["tracked_players"] = tracked.get(fr["frame_index"], [])
    return {
        "video_info": {
            "path": path,
            "total_frames": 300,
            "fps": 30.0,
            "width": 1920,
            "height": 1080,
        },
        "frame_results": frame_results,
        "spike_analysis": spikes or [],
    }


def test_payload_keeps_full_action_fields():
    exporter = JSONExporter()
    results = _results({10: [_action(8)]})
    payload = exporter.build_payload(results, pipeline_version="abc1234")

    assert payload["schema_version"] == 1
    assert payload["video"]["key"] == "foo"
    assert payload["video"]["fps"] == 30.0
    assert payload["pipeline_version"] == "abc1234"
    assert payload["processed_at"]

    (action,) = payload["actions"]
    # The fields the DB needs -- all the ones the detailed CSV drops.
    assert action["team"] == "A"
    assert action["team_in_possession"] == "A"
    assert action["touch_number"] == 1
    assert action["rally_id"] == 3
    assert action["contact_kind"] == "normal"
    assert action["contact_point"] == [100.0, 200.0]
    assert action["frame_number"] == 8  # true contact frame, not emission frame


def test_actions_sorted_by_contact_frame_even_when_flushed_on_last_frame():
    exporter = JSONExporter()
    # The classifier's end-of-video flush attaches the final contact to the
    # LAST frame_result; its frame_number is the true (earlier) contact frame.
    results = _results({
        5: [_action(3)],
        299: [_action(120, action="set", track_id=4)],
    })
    payload = exporter.build_payload(results)
    frames = [a["frame_number"] for a in payload["actions"]]
    assert frames == [3, 120]


def test_spike_zones_flattened_and_flight_dropped():
    exporter = JSONExporter()
    spikes = [
        {
            "frame": 173,
            "track_id": 2,
            "player_id": 2,
            "team": "B",
            "spike_type": "touch",
            "attack_zone": {"side": "B", "zone": 3},
            "outcome": "dug",
            "landing_zone": None,
            "dug_zone": {"side": "A", "zone": 8},
            "exit_speed_px": 19.06,
            "flight_frames": 43,
            "resolution_frame": 223,
            "landing_frame": None,
            "flight": [(173, 1, 2), (174, 3, 4)],  # render-only: must be dropped
        }
    ]
    payload = exporter.build_payload(_results({}, spikes=spikes))
    (spike,) = payload["spikes"]
    assert spike["attack_zone"] == "B3"
    assert spike["dug_zone"] == "A8"
    assert spike["landing_zone"] is None
    assert "flight" not in spike
    assert spike["outcome"] == "dug"


def test_export_writes_readable_file(tmp_path):
    exporter = JSONExporter()
    out = tmp_path / "sub" / "pipeline_output.json"
    exporter.export(_results({10: [_action(8)]}), out, pipeline_version="v")
    import json

    payload = json.loads(out.read_text())
    assert payload["video"]["key"] == "foo"
    assert len(payload["actions"]) == 1


def test_snapshots_prefer_action_frames_plus_neutral_midpoint():
    exporter = JSONExporter()
    # Track 1 appears every 10 frames (0..100); acts at frames 30 and 90.
    action_buckets = {30: [_action(30, track_id=1)], 90: [_action(90, track_id=1)]}
    frame_results = [
        {
            "frame_index": f,
            "actions": action_buckets.get(f, []),
            "tracked_players": [
                {"track_id": 1, "bbox": [10, 20, 30, 40], "team": "A", "center": [20, 30]}
            ],
        }
        for f in range(0, 101, 10)
    ]
    results = {"video_info": {"path": "resources/foo.mp4"}, "frame_results": frame_results}
    actions = exporter.collect_actions(results)
    snaps = exporter.collect_snapshots(results, actions)["1"]
    frames = [s["frame"] for s in snaps]
    # Two action moments (exact appearances) + neutral midpoint (frame 50).
    assert frames == [30, 50, 90]
    assert all(s["bbox"] == [10, 20, 30, 40] for s in snaps)


def test_snapshots_capped_deduped_sorted_and_empty_without_tracks():
    exporter = JSONExporter()
    tracked = {
        f: [{"track_id": 2, "bbox": [1, 2, 3, 4]}] for f in (0, 10, 20, 30, 40)
    }
    # Actions at 10 and 20; midpoint of appearances (0..40) is 20 -> dup,
    # so chosen = [10, 20]; cap 3 respected.
    results = _results(
        {10: [_action(10, track_id=2)], 20: [_action(20, track_id=2)]},
        tracked=tracked,
    )
    snaps = exporter.build_payload(results)["snapshots"]["2"]
    assert [s["frame"] for s in snaps] == [10, 20]

    # No tracked_players at all -> empty dict, no crash
    payload = exporter.build_payload(_results({}))
    assert payload["snapshots"] == {}
