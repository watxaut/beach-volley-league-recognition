"""Tests for scripts/build_dev_clip_gt.py (T2 dev-clip GT builder).

Pure-function level: the offset map, the frame translation, the error-event
classification and the GT assembly are exercised without decoding video. The
end-to-end run is the script's own job (`--points 1-8`).
"""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "build_dev_clip_gt", ROOT / "scripts" / "build_dev_clip_gt.py")
mod = importlib.util.module_from_spec(SPEC)
sys.modules["build_dev_clip_gt"] = mod
SPEC.loader.exec_module(mod)


def _fake_thumbs(n, seed=0, motion=3.0):
    """Synthetic 'video': per-frame unique noise + a drifting bright blob, so
    a matching frame is unique (no ambiguity in the offset search)."""
    rng = np.random.default_rng(seed)
    out = np.empty((n, 18 * 32), np.float32)
    for i in range(n):
        f = rng.uniform(90, 110, size=(18, 32)).astype(np.float32)
        col = int((i * motion) % 32)
        f[9 - (i % 4), col] = 235
        out[i] = f.ravel()
    return out


# --- offset map ------------------------------------------------------------

def test_offset_map_identity_no_drift():
    clip = _fake_thumbs(400, seed=1)
    match = _fake_thumbs(400, seed=1)
    om = mod.build_offset_map(clip, match, coarse_stride=50, radius=48)
    assert not om["drift"]
    assert [s["match_offset"] for s in om["segments"]] == [0]
    assert all(c["ok"] for c in om["checks"])
    assert all(c["residual_at_mapped"] == 0.0 for c in om["checks"])


def test_offset_map_constant_nonzero_offset():
    clip = _fake_thumbs(400, seed=2)
    match = np.concatenate([_fake_thumbs(137, seed=9), clip, _fake_thumbs(50, seed=9)])
    om = mod.build_offset_map(clip, match, coarse_stride=50, radius=48)
    assert not om["drift"]
    assert [s["match_offset"] for s in om["segments"]] == [137]
    assert mod.clip_to_match(om, 0) == 137
    assert mod.match_to_clip(om, 137) == 0
    assert mod.match_to_clip(om, 400) == 263


def test_offset_map_detects_drift_as_piecewise():
    """Clip = A ++ B; the match copy of B has 5 duplicated frames spliced in."""
    a = _fake_thumbs(200, seed=3)
    b = _fake_thumbs(200, seed=4)
    clip = np.concatenate([a, b])
    match = np.concatenate([a, b[:100], b[95:100], b[100:]])
    om = mod.build_offset_map(clip, match, coarse_stride=50, radius=48)
    assert om["drift"] is True, om["segments"]
    assert sorted({s["match_offset"] for s in om["segments"]}) == [0, 5], om["segments"]
    # the two halves still translate correctly
    assert mod.clip_to_match(om, 50) == 50
    assert mod.clip_to_match(om, 300) == 305


def test_segment_for_picks_right_segment():
    segs = [{"clip_start": 0, "clip_end": 99, "match_offset": 0},
            {"clip_start": 100, "clip_end": 199, "match_offset": 5}]
    assert mod.segment_for(segs, 0)["match_offset"] == 0
    assert mod.segment_for(segs, 150)["match_offset"] == 5
    assert mod.segment_for(segs, 500)["match_offset"] == 5
    assert mod.segment_for([], 0) is None
    assert mod.clip_to_match({"segments": segs}, 150) == 155


# --- error-event classification -------------------------------------------

@pytest.mark.parametrize("desc,expected", [
    ("Team A fails spike into the net", mod.ERROR_SPIKE_NET),
    ("Team B fails serve goes outside bounds", mod.ERROR_SERVE_OUT),
    ("serve out of bounds", mod.ERROR_SERVE_OUT),
    ("P1 fails serve", mod.ERROR_SERVE_FAULT),
    ("player fails hand set", mod.ERROR_SET_SLIP),
    ("Team B bumb passes ball on third contact, touches line court and scores", None),
    ("poke spike from A team wins the point", None),
    ("spike from B team wins the point", None),
])
def test_classify_error(desc, expected):
    assert mod.classify_error(desc) == expected


def test_error_team_squads():
    # serve fault -> the serving squad
    assert mod._error_team(mod.ERROR_SERVE_OUT, "serve out of bounds", "B", "A") == "A"
    # spike into the net -> the LOSING squad
    assert mod._error_team(mod.ERROR_SPIKE_NET, "Team A fails spike into the net",
                           "B", "B") == "A"
    # set slip: winner is the failing side -> squad inferred from the score
    assert mod._error_team(mod.ERROR_SET_SLIP, "player fails hand set", "A", "B") == "B"
    assert "INFERRED" in mod._error_note(mod.ERROR_SET_SLIP, "player fails hand set",
                                         "A", "B")
    # a serve fault with no dictated location says so
    assert "WHERE" in mod._error_note(mod.ERROR_SERVE_FAULT, "P1 fails serve", "A", "B")


# --- GT assembly -----------------------------------------------------------

def _fixtures(tmp_path):
    anchors = tmp_path / "anchors.txt"
    anchors.write_text(
        "# test\n"
        "P1 230 far NOT_TRACKED note\n"
        "P2 900 far NOT_TRACKED goes outside\n"
        "FALSE 1039 hands\n"
        "OFFGAME 2444-2534 pre-serve\n",
        encoding="utf-8")
    doc = mod.parse_serve_anchors(str(anchors))
    match_points = {
        "points": [
            {"point": 1, "winner": "B", "description": "Team A fails spike into the net",
             "side_switch_after": False},
            {"point": 2, "winner": "A", "description": "Team B fails serve goes outside bounds",
             "side_switch_after": False},
        ]
    }
    ep_map = {"points": [
        {"point": 1, "serve_squad": "B", "window_frames": [50, 350]},
        {"point": 2, "serve_squad": "B", "window_frames": [720, 1020]},
    ]}
    relabel = {"points": [{"point": 1, "decision": "relabeled"}],
               "actions_pass2": [{"frame_number": 345, "pass2_action": "spike",
                                  "pass2_team": "A", "pass2_source": "emitted"}]}
    pipeline = {
        "actions": [
            {"frame_number": 247, "action": "dig", "player_id": 4, "team": "A",
             "team_in_possession": "A", "touch_number": 1, "gesture": "bump_set",
             "confidence": 0.55, "contact_point": [1289.5, 473.0]},
            {"frame_number": 345, "action": "spike", "player_id": 2, "team": "A",
             "team_in_possession": "A", "touch_number": 3, "confidence": 0.6,
             "contact_point": [10, 10]},
            {"frame_number": 1039, "action": "serve", "player_id": 1, "team": "A",
             "team_in_possession": "A", "touch_number": 1, "confidence": 0.5,
             "contact_point": [1, 1]},
            {"frame_number": 2450, "action": "dig", "player_id": 1, "team": "A",
             "team_in_possession": "A", "touch_number": 1, "confidence": 0.5,
             "contact_point": [1, 1]},
            {"frame_number": 2500, "action": "overpass", "player_id": 1, "team": "A",
             "team_in_possession": "A", "touch_number": 2, "confidence": 0.5,
             "contact_point": [1, 1]},
        ],
        "game_state": {"points": [{"start_frame": 216, "end_frame": 495, "n_actions": 5}]},
    }
    return doc, match_points, ep_map, relabel, pipeline


def test_build_points_sources_and_flags(tmp_path):
    doc, mp, ep, rl, pl = _fixtures(tmp_path)
    om = {"segments": [{"clip_start": 0, "clip_end": 5000, "match_offset": 0}]}
    points, events = mod.build_points(5000, om, mp, doc, ep, rl, pl, [1, 2])
    assert [p["point"] for p in points] == [1, 2]

    p1, p2 = points
    # P1: owner serve at 230 with the SPIKE-INTO-NET fault implied but unlocated
    assert p1["n_owner_gt_events"] == 1
    serve = p1["events"][0]
    assert serve["source"] == mod.SOURCE_OWNER
    assert serve["frame"] == 230 and serve["match_frame"] == 230
    assert serve["final_action"] == "serve"
    assert serve["player_id"] is None
    assert serve["owner_verdict"] == "NOT_TRACKED"
    assert serve["error"] is None
    assert p1["implied_events"][0]["type"] == mod.ERROR_SPIKE_NET
    assert p1["implied_events"][0]["frame"] is None
    assert p1["implied_events"][0]["team"] == "A"
    assert any(m["type"] == mod.ERROR_SPIKE_NET for m in p1["missing_events"])
    # suggested: only 247 and 345 (in the confirmed segment); the owner FALSE
    # serve candidate 1039 and the OFFGAME dig/overpass are excluded
    sug = [e for e in p1["events"] if e["source"] == mod.SOURCE_SUGGESTED]
    assert sorted(e["frame"] for e in sug) == [247, 345]
    assert all(e["final_action"] != "serve" for e in sug)
    assert p1["window_source"] == "game_state_confirmed_segment"
    assert p1["clip_start_frame"] == 216 and p1["clip_end_frame"] == 495
    assert p1["window_is_prediction"] is True
    assert p1["side_switch_after"] is False

    # P2: serve fault is ON the anchored serve; no confirmed segment -> emission window
    p2_serve = p2["events"][0]
    assert p2_serve["error"] == {"type": mod.ERROR_SERVE_OUT, "team": "B",
                                 "text": p2["description"]}
    assert p2["window_source"] == "episode_map_emission_window"
    assert p2["n_suggested_events"] == 0  # no actions in [720, 1020]
    assert not p2["missing_events"]
    assert p2["serving_side"] == "far" and p2["winner"] == "A"


def test_build_points_side_switch_flags(tmp_path):
    doc, mp, ep, rl, pl = _fixtures(tmp_path)
    mp["points"][0]["side_switch_after"] = True   # switch between P1 and P2
    om = {"segments": [{"clip_start": 0, "clip_end": 5000, "match_offset": 0}]}
    points, _ = mod.build_points(5000, om, mp, doc, ep, rl, pl, [1, 2])
    assert points[0]["side_switch_before"] is False
    assert points[0]["side_switch_after"] is True
    assert points[1]["side_switch_before"] is True


def test_events_translate_through_a_shifted_offset_map(tmp_path):
    doc, mp, ep, rl, pl = _fixtures(tmp_path)
    # positive offset = the clip starts `offset` frames INTO the match
    om = {"segments": [{"clip_start": 0, "clip_end": 5000, "match_offset": 120}]}
    points, _ = mod.build_points(5000, om, mp, doc, ep, rl, pl, [1])
    p1 = points[0]
    # match f230 is clip f110, and the clip is 120 frames shorter at the head
    assert p1["events"][0]["frame"] == 110
    assert p1["events"][0]["match_frame"] == 230
    assert p1["clip_start_frame"] == 96
    assert p1["clip_end_frame"] == 375
    assert p1["owner_serve_anchor_clip_frame"] == 110


# --- contact-level GT parser (owner-dictated, coarse frames) --------------

_CONTACTS_TXT = ROOT / "ground_truth" / "20260920_match_ari_joan_contacts_p1_p8.txt"


def _contacts(tmp_path, body):
    p = tmp_path / "contacts.txt"
    p.write_text("# header comment\n#\n# <side> team P<k> <action> at f<frame>\n"
                 + body, encoding="utf-8")
    return mod.parse_contact_gt(str(p))


def test_parse_contact_gt_edge_cases(tmp_path):
    doc = _contacts(tmp_path, """
Some players change number when occlusions happen
GT 8 points match
Point 1
Far team P2 serve at f210
Near team P3 set at f300 (missatributed to P2)
Near team P4 spike accelerated into the net f345, far team scores
Point 2
Far team P2 serve at f880 -> goes wide outside court at f930, near team scores
Point 3
Far team serve at f2154, goes into the net, near team scores
Far team bump overpass at f1543 -> touches the line on the exterior at f1595
Near team P4 set f3131 overpasses
Far team P3 set f3228 slips hands and loses point, near team scores
Point 7
Near side P2 digs f3950
Side switch (near team now is far team)
Point 8
Far team serves f4770
Near team dig at f4800
Far team hand digs the ball f4910 and goes wide, ball falls to the ground f4950
""")
    pts = {p["point"]: p for p in doc["points"]}
    assert sorted(pts) == [1, 2, 3, 7, 8]
    assert doc["frame_tolerance"] == mod.CONTACT_FRAME_TOLERANCE

    # (a) header/preamble lines are reported, never silently dropped
    assert len(doc["unparsed"]) == 2
    assert all("before the first" in u["reason"] for u in doc["unparsed"])
    assert doc["unparsed"][1]["line"].strip() == "GT 8 points match"

    p1 = {c["match_frame"]: c for c in pts[1]["contacts"]}
    assert len(p1) == 3
    # (b) team from the side word (near=A at match start), coarse tolerance kept
    assert p1[210]["team"] == "B" and p1[210]["player_id"] == 2
    assert p1[300]["team"] == "A"
    assert p1[300]["player_id"] == 3
    assert p1[300]["note"] == "(missatributed to P2)"
    assert p1[300]["frame_tolerance"] == 15
    # (c) error / spike wording BEFORE the frame token is still classified
    assert p1[345]["action"] == "spike"
    assert p1[345]["spike_type"] == "hard"
    assert p1[345]["error"] == {"type": mod.ERROR_SPIKE_NET}
    assert p1[345]["outcome"] == "out"       # into the net beats "far team scores"
    assert p1[345]["note"] == "far team scores"
    assert p1[345]["raw"].startswith("Near team P4 spike")

    # (d) a second f<n> on the line is NOT a contact: it rides the note
    p2 = pts[2]["contacts"][0]
    assert p2["match_frame"] == 880 and p2["extra_match_frames"] == [930]
    assert p2["error"] == {"type": mod.ERROR_SERVE_OUT}
    assert "f930" in p2["note"]

    p3 = pts[3]["contacts"]
    # (e) no player id on "Far team serve at f2154"
    assert p3[0]["player_id"] is None and p3[0]["action"] == "serve"
    assert p3[0]["error"] == {"type": mod.ERROR_SERVE_NET}
    # (f) bump == overpass (the owner's "overpass/bump" is ONE action)
    assert p3[1]["action"] == "overpass" and p3[1]["player_id"] is None
    # (g) first-occurring action wins, but "overpass" wording applies the
    #     pipeline taxonomy: a set that crossed the net is an OVERPASS
    assert p3[2]["action"] == "overpass" and p3[2]["gesture"] == "set"
    assert p3[2]["owner_interpretation_flag"]["rule"] == \
        "overpass_wording_with_gesture_keyword"
    assert p3[2]["note"] == "overpasses"
    assert p3[3]["error"] == {"type": mod.ERROR_SET_SLIP}

    # (h) "Near side" == "Near team"; the switch marker closes P7 and flips
    # every LATER point only
    assert pts[7]["side_switch_after"] is True
    assert pts[7]["contacts"][0]["team"] == "A"     # near is still A in P7
    assert pts[8]["contacts"][0]["side"] == "far" and pts[8]["contacts"][0]["team"] == "A"
    assert pts[8]["contacts"][1]["team"] == "B"      # near is now B


def test_parse_contact_gt_unmappable_and_unknown_action(tmp_path):
    doc = _contacts(tmp_path, "Point 1\nNear team P1 does something at f10\n"
                              "Far team P2 serve no frame here\n")
    assert len(doc["unparsed"]) == 2
    reasons = " | ".join(u["reason"] for u in doc["unparsed"])
    assert "no known action" in reasons and "without any f<frame>" in reasons
    assert doc["points"][0]["contacts"] == []


def test_contact_events_translate_and_keep_owner_fields(tmp_path):
    doc = _contacts(tmp_path, "Point 1\nFar team P2 serve at f210\n"
                              "Near team P4 dig at f245\n")
    om = {"segments": [{"clip_start": 0, "clip_end": 4000, "match_offset": 120}]}
    events, unmappable = mod.contact_events(4000, om, doc, [1])
    assert unmappable == []
    assert [e["match_frame"] for e in events] == [210, 245]
    assert [e["frame"] for e in events] == [90, 125]     # clip = match - 120
    serve = events[0]
    assert serve["final_action"] == "serve" and serve["action"] == "serve"
    assert serve["player_id"] == 2 and serve["player_team"] == "B"
    assert serve["team_in_possession"] == "B"
    assert serve["touch_number"] == 1 and events[1]["touch_number"] == 1  # new side
    assert serve["source"] == mod.SOURCE_OWNER
    assert serve["status"] == mod.STATUS_OWNER_DICTATED
    assert serve["frame_tolerance"] == mod.CONTACT_FRAME_TOLERANCE
    assert "COARSE" in serve["frame_tolerance_note"]
    # raw owner fields survive verbatim
    assert serve["owner_side"] == "far" and serve["owner_track_id"] == 2
    assert serve["owner_raw"] == "Far team P2 serve at f210"
    # a contact past the end of the clip is reported, not dropped
    events2, unm2 = mod.contact_events(100, om, doc, [1])
    assert [e["match_frame"] for e in events2] == [210]
    assert [u["match_frame"] for u in unm2] == [245]
    assert unm2[0]["raw"] == "Near team P4 dig at f245"


def test_build_points_contact_gt_supersedes_serve_anchor(tmp_path):
    doc, mp, ep, rl, pl = _fixtures(tmp_path)
    contacts = {"path": "contacts.txt", "frame_tolerance": 15, "unparsed": [],
                "points": [{"point": 1, "side_switch_after": False, "contacts": [
                    {"point": 1, "side": "near", "side_word": "near team", "team": "A",
                     "player_id": 2, "action": "serve", "action_token": "serve",
                     "match_frame": 230, "extra_match_frames": [], "note": None,
                     "frame_tolerance": 15, "spike_type": None, "outcome": None,
                     "error": None, "raw": "Near team P2 serve at f230",
                     "raw_line_no": 1}]}]}
    om = {"segments": [{"clip_start": 0, "clip_end": 5000, "match_offset": 0}]}
    points, events = mod.build_points(5000, om, mp, doc, ep, rl, pl, [1, 2], contacts)
    p1, p2 = points
    # P1 has a dictated contact serve -> NO anchor duplicate, but the anchor
    # frame is still carried for cross-reference
    assert p1["n_owner_gt_events"] == 1
    assert p1["n_owner_contact_events"] == 1
    assert p1["events"][0]["player_id"] == 2
    assert p1["events"][0]["player_team"] == "A"
    assert p1["owner_serve_anchor_frame"] == 230
    assert p1["owner_contacts"][0]["match_frame"] == 230
    # P2 has no contact-level serve -> the anchor event survives
    assert p2["n_owner_contact_events"] == 0 and p2["events"][0]["player_id"] is None
    gt = mod.build_gt(30.0, 5000, {"segments": om["segments"], "drift": False,
                                   "checks": []},
                      points, events, [1, 2], {}, False, contacts)
    assert gt["status"] == mod.STATUS_OWNER_DICTATED
    assert "COARSE" in gt["status_note"]
    graded = gt["annotated_frames"]["actions"]["events"]
    assert len(graded) == 2   # the contact serve + the P2 anchor serve


def test_build_gt_status_draft_without_contacts(tmp_path):
    doc, mp, ep, rl, pl = _fixtures(tmp_path)
    om = {"segments": [{"clip_start": 0, "clip_end": 5000, "match_offset": 0}]}
    points, events = mod.build_points(5000, om, mp, doc, ep, rl, pl, [1, 2])
    gt = mod.build_gt(30.0, 5000, {"segments": om["segments"], "drift": False,
                                   "checks": []}, points, events, [1, 2], {}, False)
    assert gt["status"] == mod.STATUS_DRAFT


def test_owner_contacts_file_parses_end_to_end():
    """The real owner file, P1-P8 (dialect A): 8 points, 28 contacts, 3 preamble lines.

    The file now also carries the owner's P9-P33 dictation in dialect B
    (session 46); only its headers parse, and the coverage of that half is
    pinned by test_owner_contacts_p9_p33_dialect_is_not_parsed_yet. P1-P8
    stays the regression anchor: it must rebuild identically no matter how
    much the owner appends below it.
    """
    doc = mod.parse_contact_gt(str(_CONTACTS_TXT))
    pts = [p for p in doc["points"] if p["point"] <= 8]
    assert [p["point"] for p in pts] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert [len(p["contacts"]) for p in pts] == [4, 1, 4, 1, 1, 5, 7, 5]
    assert pts[6]["side_switch_after"] is True
    assert all(len(p["contacts"]) == len({c["match_frame"] for c in p["contacts"]})
               for p in pts)
    assert len([u for u in doc["unparsed"]
                if u["reason"].startswith("before the first")]) == 3
    om = {"segments": [{"clip_start": 0, "clip_end": 4960, "match_offset": 0}]}
    events, unm = mod.contact_events(4961, om, doc, [1, 2, 3, 4, 5, 6, 7, 8])
    assert unm == [] and len(events) == 28
    assert [e["frame"] for e in events] == sorted(e["frame"] for e in events)
    assert {e["final_action"] for e in events} == {"serve", "dig", "set",
                                                  "overpass", "spike"}
    assert sum(1 for e in events if e["player_id"] is None) == 8


def test_owner_contacts_p9_p33_dialect_is_not_parsed_yet():
    """Session 46 state: the headers parse, the dialect-B contact lines do not.

    G0 (the next worker task) extends `parse_contact_gt` for dialect B; when it
    lands, THIS test is the thing that must change, and it should change to
    "every P9-P33 point has contacts" -- not to a smaller number.
    """
    doc = mod.parse_contact_gt(str(_CONTACTS_TXT))
    late = [p for p in doc["points"] if p["point"] >= 9]
    assert late, "P9-P33 headers must be found"
    assert {p["point"] for p in late} == set(range(9, 34))
    # all four side switches (after P7/14/21/28) are read
    assert [p["point"] for p in doc["points"] if p["side_switch_after"]] == [7, 14,
                                                                             21, 28]
    # ...but no contact of P9+ is machine-readable yet
    assert sum(len(p["contacts"]) for p in late) == 0
    # the duplicated "Point 21" header the owner's dictation contains
    assert [p["point"] for p in doc["points"]].count(21) == 2


# --- touch_number: per-POSSESSION, not rally-global -----------------------

def test_possession_touch_numbers_restart_on_every_side_change():
    contacts = [{"team": t} for t in
                ["B", "A", "A", "A",            # serve, dig 1, set 2, spike 3
                 "B", "B", "B",                # new possession: 1, 2, 3
                 "A", "A"]]                   # and again: 1, 2
    assert mod.possession_touch_numbers(contacts) == [1, 1, 2, 3, 1, 2, 3, 1, 2]
    assert mod.possession_touch_numbers([]) == []


def test_possession_touch_numbers_serve_is_always_one():
    # P6 of the owner dictation: the whole point restarts per side change
    doc = mod.parse_contact_gt(str(_CONTACTS_TXT))
    p6 = next(p for p in doc["points"] if p["point"] == 6)
    touches = mod.possession_touch_numbers(p6["contacts"])
    assert [c["action"] for c in p6["contacts"]] == [
        "serve", "dig", "overpass", "dig", "set"]
    assert touches == [1, 1, 2, 1, 2], touches   # NOT [1, 2, 3, 4, 5]


def test_contact_events_touch_number_is_per_possession(tmp_path):
    doc = _contacts(tmp_path, "Point 1\nFar team P2 serve at f210\n"
                              "Near team P4 dig at f245\n"
                              "Near team P3 set at f300\n"
                              "Far team P1 dig at f355\n"
                              "Far team P2 spike at f400\n")
    om = {"segments": [{"clip_start": 0, "clip_end": 4000, "match_offset": 0}]}
    events, _ = mod.contact_events(4000, om, doc, [1])
    assert [e["final_action"] for e in events] == ["serve", "dig", "set", "dig", "spike"]
    assert [e["touch_number"] for e in events] == [1, 1, 2, 1, 2]
    assert [e["player_team"] for e in events] == ["B", "A", "A", "B", "B"]


# --- overpass wording: pipeline taxonomy wins, gesture kept ---------------

def test_set_that_crosses_the_net_is_an_overpass(tmp_path):
    """P6: 'Near team P4 set f3131 overpasses' -> overpass + gesture set."""
    doc = _contacts(tmp_path, "Point 6\nFar team P3 serve at f3038\n"
                              "Near team P2 dig at f3071\n"
                              "Near team P4 set f3131 overpasses\n")
    set_c = doc["points"][0]["contacts"][2]
    assert set_c["action"] == "overpass"          # pipeline taxonomy
    assert set_c["gesture"] == "set"              # the touch the owner described
    flag = set_c["owner_interpretation_flag"]
    assert flag["rule"] == "overpass_wording_with_gesture_keyword"
    assert flag["raw_action_label"] == "set" and flag["gesture"] == "set"
    assert "ratification" in flag["why"].lower()
    assert "overpass" in flag["why"] and "set f3131 overpasses" in flag["why"]
    om = {"segments": [{"clip_start": 0, "clip_end": 4000, "match_offset": 0}]}
    events, _ = mod.contact_events(4000, om, doc, [6])
    ev = events[2]
    assert ev["final_action"] == "overpass" and ev["action"] == "overpass"
    assert ev["gesture"] == "set"
    assert ev["owner_interpretation_flag"] == flag


def test_unratified_flag_keeps_asking_for_ratification(tmp_path):
    """A flagged contact the owner has NOT ruled on stays open."""
    doc = _contacts(tmp_path, "Point 1\nNear team P4 set f999 overpasses\n")
    flag = doc["points"][0]["contacts"][0]["owner_interpretation_flag"]
    assert flag["rule"] == "overpass_wording_with_gesture_keyword"
    assert "needs ratification" in flag["why"]
    assert "owner_ratified" not in flag


def test_owner_ratified_overpass_flag(tmp_path):
    """P6 f3131: the owner RATIFIED the reading ("it's an overpass", 2026-09-29)."""
    doc = _contacts(tmp_path, "Point 6\nNear team P4 set f3131 overpasses\n")
    flag = doc["points"][0]["contacts"][0]["owner_interpretation_flag"]
    assert flag["owner_ratified"] is True
    assert flag["owner_ratification_date"] == "2026-09-29"
    assert flag["owner_ratification_statement"] == "it's an overpass"
    assert "RATIFIED 2026-09-29" in flag["why"]
    assert "needs ratification" not in flag["why"]
    # ... and the event carries the same flag through to the GT blob
    om = {"segments": [{"clip_start": 0, "clip_end": 4000, "match_offset": 0}]}
    events, _ = mod.contact_events(4000, om, doc, [6])
    assert events[0]["owner_interpretation_flag"] == flag


def test_ratification_table_is_generic_and_point_scoped():
    """The table is keyed by (point, frame, gesture): no flag is ratified by
    accident because another point's row matches."""
    assert mod.OWNER_RATIFICATIONS[(6, 3131, "set")]["owner_ratified"] is True
    assert mod._ratification(7, 3131, "set") is None
    assert mod._ratification(6, 3131, "dig") is None
    assert mod._ratification(6, 1543, None) is None
    assert mod._ratification(None, 3131, "set") is None


def test_committed_dev_gt_carries_the_ratification():
    gt = json.loads((ROOT / "ground_truth"
                     / "video_ari_joan_8_first_points_annotations.json")
                    .read_text(encoding="utf-8"))
    p6 = next(p for p in gt["points"] if p["point"] == 6)
    ev = next(e for e in p6["events"] if e["match_frame"] == 3131)
    assert ev["final_action"] == "overpass" and ev["gesture"] == "set"
    flag = ev["owner_interpretation_flag"]
    assert flag["owner_ratified"] is True
    assert flag["owner_ratification_date"] == "2026-09-29"
    # every other flagged contact would still read "needs ratification"
    for p in gt["points"]:
        for e in p["events"]:
            f = e.get("owner_interpretation_flag")
            if f and not f.get("owner_ratified"):
                assert "needs ratification" in f["why"]


@pytest.mark.parametrize("line,action,gesture,flagged", [
    ("Near team P4 set f3131 overpasses", "overpass", "set", True),
    ("Near team P4 dig f3131 overpasses it", "overpass", "dig", True),
    ("Near team P4 dig f3131 and overpasses", "overpass", "dig", True),
    ("Far team P2 serves at f880, overpass long", "serve", None, False),
    ("Near team P3 set at f300", "set", None, False),      # stays a set
    ("Far team bump overpass at f1543", "overpass", None, False),
])
def test_overpass_interpretation_generalises(tmp_path, line, action, gesture, flagged):
    doc = _contacts(tmp_path, f"Point 1\n{line}\n")
    c = doc["points"][0]["contacts"][0]
    assert c["action"] == action
    assert c["gesture"] == gesture
    assert bool(c["owner_interpretation_flag"]) is flagged


# --- owner contacts supersede draft/suggested events ----------------------

def test_owner_contacts_supersede_draft_events(tmp_path):
    """P6 shape: a suggested dig 1f before the owner dig is NOT a 2nd contact."""
    doc, mp, ep, rl, pl = _fixtures(tmp_path)
    pl["actions"].append(
        {"frame_number": 3070, "action": "dig", "player_id": 1, "team": "A",
         "team_in_possession": "A", "touch_number": 1, "gesture": "bump_set",
         "confidence": 0.55, "contact_point": [485, 492]})
    rl["points"] = [{"point": 1, "decision": "kept"}]
    ep["points"] = [{"point": 1, "serve_squad": "B", "window_frames": [3000, 3300]}]
    pl["game_state"]["points"] = [{"start_frame": 3000, "end_frame": 3300}]
    contacts = {"path": "contacts.txt", "frame_tolerance": 15, "unparsed": [],
                "points": [{"point": 1, "side_switch_after": False, "contacts": [
                    {"point": 1, "side": "far", "side_word": "far team", "team": "B",
                     "player_id": 3, "action": "serve", "action_token": "serve",
                     "gesture": None, "owner_interpretation_flag": None,
                     "match_frame": 3038, "extra_match_frames": [], "note": None,
                     "frame_tolerance": 15, "spike_type": None, "outcome": None,
                     "error": None, "raw": "Far team P3 serve at f3038",
                     "raw_line_no": 1},
                    {"point": 1, "side": "near", "side_word": "near team", "team": "A",
                     "player_id": 2, "action": "dig", "action_token": "digs",
                     "gesture": None, "owner_interpretation_flag": None,
                     "match_frame": 3071, "extra_match_frames": [], "note": None,
                     "frame_tolerance": 15, "spike_type": None, "outcome": None,
                     "error": None, "raw": "Near team P2 dig at f3071",
                     "raw_line_no": 2}]}]}
    om = {"segments": [{"clip_start": 0, "clip_end": 5000, "match_offset": 0}]}
    points, events = mod.build_points(5000, om, mp, doc, ep, rl, pl, [1], contacts)
    p1 = points[0]
    # events == the owner contacts, one per contact: the draft dig is GONE
    assert [e["frame"] for e in p1["events"]] == [3038, 3071]
    assert [e["final_action"] for e in p1["events"]] == ["serve", "dig"]
    assert all(e["source"] == mod.SOURCE_OWNER for e in p1["events"])
    assert [e["touch_number"] for e in p1["events"]] == [1, 1]
    # ... but nothing is lost: the draft near the owner dig is kept with the
    # owner contact it duplicates, and the unmatched drafts are kept too
    sup = p1["superseded_draft_events"]
    assert len(sup) == 1
    dup = sup
    assert dup[0]["frame"] == 3070
    assert dup[0]["gesture"] == "bump_set"           # draft fields survive
    assert dup[0]["superseded_by_owner_contact"]["frame"] == 3071
    assert dup[0]["superseded_by_owner_contact"]["final_action"] == "dig"
    assert "duplicate" in dup[0]["superseded_reason"]
    assert dup[0]["source"] == mod.SOURCE_SUGGESTED
    assert p1["n_superseded_draft_events"] == 1 and p1["n_suggested_events"] == 0
    # a draft event with no owner contact nearby is kept, unmatched
    m = mod.supersede_matching({"frame": 9999, "final_action": "dig", "player_team": "A"},
                               p1["events"])
    assert m["superseded_by_owner_contact"] is None
    assert "no owner contact" in m["superseded_reason"]


def test_supersede_matching_requires_same_squad_and_window():
    owner = [{"frame": 3071, "final_action": "dig", "player_team": "A",
              "player_id": 2, "match_frame": 3071, "touch_number": 1,
              "owner_raw": "Near team P2 dig at f3071"}]
    # same frame, other squad -> not a duplicate of that contact
    assert mod.supersede_matching(
        {"frame": 3071, "final_action": "dig", "player_team": "B"},
        owner)["superseded_by_owner_contact"] is None
    # 16f away on the same squad -> outside the coarse frame window
    assert mod.supersede_matching(
        {"frame": 3071 + mod.DRAFT_MATCH_WINDOW + 1, "final_action": "dig",
         "player_team": "A"}, owner)["superseded_by_owner_contact"] is None
    # inside the window, different label -> matched AND the disagreement flagged
    m = mod.supersede_matching(
        {"frame": 3073, "final_action": "set", "player_team": "A"}, owner)
    assert m["superseded_by_owner_contact"]["frame"] == 3071
    assert m["superseded_by_owner_contact"]["final_action"] == "dig"
    assert "differs" in m["superseded_reason"]


def test_real_gt_file_events_are_exactly_the_28_owner_contacts():
    """The regenerated GT: 8 points, 28 owner contacts, 0 duplicate drafts."""
    gt = json.loads((ROOT / "ground_truth" /
                     "video_ari_joan_8_first_points_annotations.json").read_text())
    points = gt["points"]
    assert [len(p["events"]) for p in points] == [4, 1, 4, 1, 1, 5, 7, 5]
    assert sum(len(p["events"]) for p in points) == 28
    for p in points:
        assert [e["match_frame"] for e in p["events"]] == \
            [c["match_frame"] for c in p["owner_contacts"]]
        assert all(e["source"] == mod.SOURCE_OWNER for e in p["events"])
        # per-possession touch numbering, restarting on every side change
        assert [e["touch_number"] for e in p["events"]] == \
            mod.possession_touch_numbers(p["owner_contacts"])
    graded = gt["annotated_frames"]["actions"]["events"]
    assert len(graded) == 28
    assert all(e["source"] == mod.SOURCE_OWNER for e in graded)
    assert gt["provenance"]["superseded_draft_events"] == \
        sum(p["n_superseded_draft_events"] for p in points)
    # P6: the cross-net set is an overpass with a ratification flag
    p6 = points[5]
    ev = next(e for e in p6["events"] if e["match_frame"] == 3131)
    assert ev["final_action"] == "overpass" and ev["gesture"] == "set"
    assert ev["owner_interpretation_flag"]["rule"] == \
        "overpass_wording_with_gesture_keyword"
    # the P6 draft dig at 3070 that used to sit next to the owner dig at 3071
    dup = next(e for e in p6["superseded_draft_events"] if e["frame"] == 3070)
    assert dup["superseded_by_owner_contact"]["frame"] == 3071


# --- description claims ----------------------------------------------------

@pytest.mark.parametrize("desc,expected", [
    ("Team A fails spike into the net", [("A", "spike")]),
    ("poke spike from A team wins the point", [("A", "poke")]),
    ("spike from B team wins the point", [("B", "spike")]),
    ("Team B bumb passes ball on third contact, touches line court and scores",
     [("B", "bump")]),
    ("serve out of bounds", []),
])
def test_description_claims(desc, expected):
    assert mod.description_claims(desc) == expected


def test_missing_events_reports_unsupported_claims():
    desc = "spike from B team wins the point"
    suggested = [{"final_action": "dig", "player_team": "A"}]
    out = mod._missing_events(desc, None, [], suggested)
    assert {"type": "spike_by_team_B",
            "reason": "dictated 'spike' by squad B has no matching contact "
                      "(team/label to adjudicate)",
            "frame": None} in out
    # a matching suggested contact clears the claim
    ok = mod._missing_events(desc, None, [],
                             [{"final_action": "spike", "player_team": "B"}])
    assert not any(m["type"].endswith("_by_team_B") for m in ok)


def test_owner_excluded_actions_are_not_suggested_events(tmp_path):
    doc, mp, ep, rl, pl = _fixtures(tmp_path)
    # the owner's FALSE@3650 verdict covers the emitted 3856 serve (no exact frame)
    rl["points"] = [{"point": 1, "decision": "relabeled", "excluded": [
        {"frame": 345, "action": "spike", "team": "A", "because": "owner FALSE mark"}]}]
    om = {"segments": [{"clip_start": 0, "clip_end": 5000, "match_offset": 0}]}
    points, _ = mod.build_points(5000, om, mp, doc, ep, rl, pl, [1])
    p1 = points[0]
    assert [e["frame"] for e in p1["events"] if e["source"] == mod.SOURCE_SUGGESTED] == [247]
    assert p1["excluded_by_owner_verdict"] == [
        {"match_frame": 345, "clip_frame": 345, "action": "spike", "team": "A",
         "because": "owner FALSE mark"}]


def test_build_gt_graded_events_exclude_suggestions_by_default(tmp_path):
    doc, mp, ep, rl, pl = _fixtures(tmp_path)
    om = {"segments": [{"clip_start": 0, "clip_end": 5000, "match_offset": 0}]}
    points, events = mod.build_points(5000, om, mp, doc, ep, rl, pl, [1, 2])
    om_map = {"segments": om["segments"], "drift": False, "checks": []}
    gt = mod.build_gt(30.0, 5000, om_map, points, events, [1, 2], {}, False)
    assert gt["status"] == "DRAFT_PENDING_OWNER_RATIFICATION"
    graded = gt["annotated_frames"]["actions"]["events"]
    assert [e["source"] for e in graded] == [mod.SOURCE_OWNER, mod.SOURCE_OWNER]
    assert [e["frame"] for e in graded] == [230, 900]      # frame-sorted
    assert gt["annotated_frames"]["ball"]["frames"] == {}
    assert gt["annotated_frames"]["players"]["frames"] == {}
    assert gt["offset_map"]["drift"] is False
    assert any("gt_point_start_end" in s for s in gt["provenance"]["not_used"])

    gt2 = mod.build_gt(30.0, 5000, om_map, points, events, [1, 2], {}, True)
    assert len(gt2["annotated_frames"]["actions"]["events"]) == len(events)


def test_gt_file_is_json_serialisable_and_evaluator_loadable(tmp_path):
    """The written GT must load through scripts/evaluate.py's own loader."""
    doc, mp, ep, rl, pl = _fixtures(tmp_path)
    om = {"segments": [{"clip_start": 0, "clip_end": 5000, "match_offset": 0}]}
    points, events = mod.build_points(5000, om, mp, doc, ep, rl, pl, [1, 2])
    gt = mod.build_gt(30.0, 5000, {"segments": om["segments"], "drift": False, "checks": []},
                      points, events, [1, 2], {}, False)
    path = tmp_path / "gt.json"
    path.write_text(json.dumps(gt, indent=2), encoding="utf-8")

    spec = importlib.util.spec_from_file_location("evaluate", ROOT / "scripts" / "evaluate.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    loaded = ev.load_json(str(path))
    gt_annotated = loaded.get("annotated_frames", loaded)
    gt_actions = gt_annotated["actions"]["events"]
    merged = [{**e, **(e.get("overrides") or {})} for e in gt_actions]
    metrics = ev.evaluate_actions(
        [{"frame": 230, "action": "serve"}, {"frame": 900, "action": "serve"}],
        merged, match_player=True)
    assert metrics["per_action"]["serve"]["true_positives"] == 2
    assert metrics["per_action"]["serve"]["recall"] == 1.0
    # a prediction far away does not match
    assert ev.evaluate_actions([{"frame": 5000, "action": "serve"}], merged,
                               match_player=True)["per_action"]["serve"]["true_positives"] == 0
