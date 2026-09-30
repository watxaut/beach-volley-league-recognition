"""Tests for scripts/build_match_contact_gt.py (G0 match-level contact GT).

Pure-builder tests: no video is decoded, so only the JSON / index paths run.
The sheet renderer is exercised by the script's own `--no-sheets`-less run.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "build_match_contact_gt", ROOT / "scripts" / "build_match_contact_gt.py")
mod = importlib.util.module_from_spec(SPEC)
sys.modules["build_match_contact_gt"] = mod
SPEC.loader.exec_module(mod)


def test_build_match_gt_real_file():
    """The real owner dictation, both dialects, on the MATCH frame axis."""
    gt = mod.build_match_gt(episode_map="")
    assert gt["status"] == "OWNER_DICTATED"
    assert len(gt["points"]) == 33
    assert [p["point"] for p in gt["points"]] == list(range(1, 34))
    events = gt["annotated_frames"]["actions"]["events"]
    assert len(events) == 211
    assert {e["source"] for e in events} == {"owner_gt"}
    assert all(e["frame"] == e["match_frame"] for e in events)
    assert [e["frame"] for e in events] == sorted(e["frame"] for e in events)
    assert [p["point"] for p in gt["points"] if p["side_switch_after"]] == [7, 14, 21,
                                                                            28]
    assert gt["provenance"]["n_owner_contact_events"] == 211
    assert gt["provenance"]["contacts_unmappable"] == []
    assert len(gt["provenance"]["contacts_unparsed_lines"]) == 3
    # dialect B is on board: P9 sale + reception, one event each
    p9 = gt["points"][8]
    assert [e["frame"] for e in p9["events"]] == [5496, 5530]
    assert [e["final_action"] for e in p9["events"]] == ["serve", "dig"]
    # per-possession touch numbers restart on every side change
    p10 = gt["points"][9]
    assert [e["touch_number"] for e in p10["events"]][:4] == [1, 1, 2, 3]
    # the owner's blanket overpass rule is ratified on dialect-B flags
    f7320 = next(e for e in events if e["frame"] == 7320)
    assert f7320["final_action"] == "overpass" and f7320["gesture"] == "set"
    assert f7320["owner_interpretation_flag"]["owner_ratified"] is True
    # P15 f10180 is prose (open point 25): never an event
    assert 10180 not in {e["frame"] for e in events}
    # P30 f23545: the owner described a touch without a label -> kept, no invention
    t = next(e for e in events if e["frame"] == 23545)
    assert t["final_action"] is None and t["owner_action_unspecified"] is True
    assert t["player_team"] == "A"
    # coarse tolerance is carried per event
    assert all(e["frame_tolerance"] == 15 for e in events)


def test_build_match_gt_is_evaluator_loadable(tmp_path):
    gt = mod.build_match_gt(episode_map="")
    path = tmp_path / "gt.json"
    path.write_text(json.dumps(gt), encoding="utf-8")
    sys.path.insert(0, str(ROOT / "scripts"))
    import evaluate_timed as et

    loaded = et.load_ground_truth(str(path))
    assert len(loaded["events"]) == 211
    mm = et.match_events(loaded["events"], [], et.TimeBase(gt["fps"]))
    assert mm["n_gt"] == 211 and mm["n_pred"] == 0


def test_build_match_gt_point_range_keeps_match_frames():
    gt = mod.build_match_gt(episode_map="", point_range=[9, 10])
    assert [p["point"] for p in gt["points"]] == [9, 10]
    frames = [e["frame"] for e in gt["annotated_frames"]["actions"]["events"]]
    assert frames == [5496, 5530, 6035, 6065, 6104, 6145, 6166, 6200, 6240,
                      6266, 6320, 6330, 6369, 6416]


def test_episode_windows_are_attached_but_flagged(tmp_path):
    em = tmp_path / "ep.json"
    em.write_text(json.dumps({"points": [
        {"point": 9, "window_frames": [5400, 5700], "serve_squad": "B"}]}),
        encoding="utf-8")
    gt = mod.build_match_gt(episode_map=str(em))
    p9 = gt["points"][8]
    assert p9["match_start_frame"] == 5400 and p9["match_end_frame"] == 5700
    assert p9["window_is_prediction"] is True
    assert p9["window_source"] == "episode_map_emission_window"
    assert p9["predicted_serve_squad"] == "B"
    # without the map the fields are empty, never fabricated
    gt2 = mod.build_match_gt(episode_map="")
    assert gt2["points"][8]["match_start_frame"] is None
    assert gt2["points"][8]["window_source"] is None


def test_render_index_lists_contacts(tmp_path):
    gt = mod.build_match_gt(episode_map="", point_range=[9, 10])
    idx = mod.render_index(gt["points"], "ground_truth/20260920_match_contacts.json",
                           str(tmp_path))
    text = Path(idx).read_text(encoding="utf-8")
    assert "## P9" in text and "5496" in text
    assert "attributed as a spike" in text
    assert "bump set" not in text          # the raw line is not dumped wholesale
    assert "player not tracked" in text