"""Scoring half of scripts/probe_identity_switches.py (no video decoded).

The probe's decode half needs the owner's footage + weights; its scores must
be right before the owner reads them, so they are pinned here on a hand-made
record: orientation at GT contacts (with doubt as abstain), one flip per GT
switch window (late / missed / stray), and action attribution team vs legacy
with greedy one-to-one matching inside each contact's tolerance.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import probe_identity_switches as probe  # noqa: E402


def _gt():
    # P1 near team A serves at f10, P2 (after which sides switch) ends f100,
    # P3 is played with team B near.
    return {
        "side_switch_after_point": [2],
        "points": [
            {"point": 1, "contacts": [
                {"match_frame": 10, "side": "near", "team": "A", "action": "serve"},
                {"match_frame": 40, "side": "far", "team": "B", "action": "dig"}]},
            {"point": 2, "contacts": [
                {"match_frame": 80, "side": "far", "team": "B", "action": "serve"},
                {"match_frame": 100, "side": "near", "team": "A", "action": "dig"}]},
            {"point": 3, "contacts": [
                {"match_frame": 300, "side": "near", "team": "B", "action": "serve"},
                {"match_frame": 330, "side": "far", "team": "A", "action": "dig",
                 "frame_tolerance": 5}]},
        ],
    }


def _record(flip_at=200, doubt_at=()):
    frames = []
    for f in range(0, 400):
        near = 1 if f < flip_at else 2
        frames.append({"frame": f, "near_squad": near, "doubt": f in doubt_at, "bodies": []})
    return {"frames": frames, "flips": [{"frame": flip_at, "onset": flip_at - 10, "near_squad": 2}],
            "actions": []}


def test_expected_near_team_and_label_team():
    assert probe.expected_near_team("near", "A") == "A"
    assert probe.expected_near_team("far", "A") == "B"
    assert probe.expected_near_team("far", "B") == "A"
    assert probe.expected_near_team("left", "A") is None
    assert probe.label_team("P2B") == "B" and probe.label_team(None) is None
    assert probe.label_team("P3") is None


def test_switch_windows_span_last_contact_to_next_first():
    assert probe.switch_windows(_gt()) == [(2, 100, 300)]
    gt = _gt()
    del gt["side_switch_after_point"]
    gt["points"][1]["side_switch_after"] = True
    assert probe.switch_windows(gt) == [(2, 100, 300)]


def test_orientation_scores_every_contact_and_abstains_in_doubt():
    res = probe.score_orientation(_record(), _gt())
    assert (res["n"], res["ok"], res["wrong"], res["doubt"]) == (6, 6, 0, 0)
    late = probe.score_orientation(_record(flip_at=320), _gt())
    assert late["wrong"] == 1 and late["wrong_points"] == [3]
    doubt = probe.score_orientation(_record(flip_at=320, doubt_at={300}), _gt())
    assert doubt["wrong"] == 0 and doubt["doubt"] == 1


def test_flip_windows_ok_late_missed_and_stray():
    ok = probe.score_flips(_record(), _gt())
    assert ok["ok"] == 1 and ok["windows"][0]["verdict"] == "ok" and ok["stray_flips"] == []
    late = probe.score_flips(_record(flip_at=320), _gt(), late_frames=50)
    assert late["windows"][0]["verdict"] == "late"
    stray = probe.score_flips(_record(flip_at=50), _gt())
    assert stray["windows"][0]["verdict"] == "missed" and stray["stray_flips"] == [50]


def test_action_attribution_matches_one_to_one_within_tolerance():
    rec = _record()
    rec["actions"] = [
        {"frame": 12, "label": "P1A", "legacy_label": "P1A"},   # ok / ok
        {"frame": 14, "label": "P2A", "legacy_label": None},    # duplicate: unmatched
        {"frame": 300, "label": "P2B", "legacy_label": "P1A"},  # ok / wrong
        {"frame": 337, "label": "P1A", "legacy_label": "P1B"},  # outside the 5 f tolerance
        {"frame": 101, "label": None, "legacy_label": "P2A"},   # unlabeled / ok
    ]
    res = probe.score_actions(rec, _gt())
    assert res["n_gt"] == 6 and res["n_matched"] == 3
    assert res["label"] == {"ok": 2, "wrong": 0, "unlabeled": 1}
    assert res["legacy_label"] == {"ok": 2, "wrong": 1, "unlabeled": 0}


def test_label_stats_counts_coverage_and_teleports():
    rec = {"frames": [
        {"frame": 0, "bodies": [[1, "P1A", None, "A", 100, 100, 140, 300]]},
        {"frame": 1, "bodies": [[1, "P1A", None, "A", 102, 100, 142, 300]]},
        {"frame": 2, "bodies": [[3, "P1A", None, "B", 700, 50, 720, 120]]},
        {"frame": 3, "bodies": []},
    ]}
    stats = probe.label_stats(rec)
    assert stats["coverage"]["P1A"] == 0.75 and stats["coverage"]["P2B"] == 0.0
    assert stats["teleports"]["P1A"] == 1


# --------------------------------------------------------------------------- #
# Decode half, smoke-tested with a stub processor (no detector weights here):
# a real PlayerTracker + team resolver over a tiny synthetic video.
# --------------------------------------------------------------------------- #

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from src.tracking.identity_resolver import compute_descriptor  # noqa: E402
from src.tracking.player_tracker import PlayerTracker  # noqa: E402

_W, _H, _MID = 320, 240, 120
_CAST = [  # (label, squad, slot, cx, foot_y, colour)
    ("P1A", 1, "A", 90, 200, (255, 0, 0)), ("P2A", 1, "B", 230, 200, (0, 255, 0)),
    ("P1B", 2, "A", 100, 90, (0, 0, 255)), ("P2B", 2, "B", 220, 90, (0, 255, 255)),
]


class _Court:
    is_calibrated = True

    @staticmethod
    def foot_point(bbox):
        return (int((bbox[0] + bbox[2]) / 2), int(bbox[3]))

    def is_point_in_court(self, point):
        return True

    def get_team_for_bbox(self, bbox):
        return "A" if bbox[3] >= _MID else "B"

    def world_body_size(self, bbox):
        return None


def _bbox(cx, fy, h):
    return [cx - h * 0.2, fy - h, cx + h * 0.2, fy]


def _frame():
    img = np.full((_H, _W, 3), (150, 190, 215), np.uint8)
    for _l, _q, _s, cx, fy, colour in _CAST:
        x1, y1, x2, y2 = (int(v) for v in _bbox(cx, fy, 80 if fy > _MID else 40))
        img[y1:y2, x1:x2] = colour
    return img


class _StubProcessor:
    def __init__(self, config):
        self.court_calibration = _Court()
        self.player_tracker = PlayerTracker(court_calibration=self.court_calibration, max_players=4)

    def setup_video_fps(self, fps):
        pass

    def setup_video_dimensions(self, w, h):
        pass

    def enroll_from_video(self, video):
        frame = _frame()
        refs = []
        for label, squad, slot, cx, fy, _c in _CAST:
            box = _bbox(cx, fy, 80 if fy > _MID else 40)
            refs.append({"label": label, "squad": squad, "slot": slot,
                         "identity_samples": [compute_descriptor(frame, box)] * 10,
                         **self.player_tracker.compute_enrollment_signature(frame, box)})
        self.player_tracker.set_enrollment(refs)
        self.player_tracker._initialized = True
        self.player_tracker._current_frame = frame
        for _l, _q, _s, cx, fy, _c in _CAST:
            box = _bbox(cx, fy, 80 if fy > _MID else 40)
            self.player_tracker._create_track(
                {"bbox": box, "center": [cx, fy - 20], "confidence": 0.9},
                require_court_admission=False)
        return refs

    def process_frame(self, image, idx):
        dets = [{"bbox": _bbox(cx, fy, 80 if fy > _MID else 40), "center": [cx, fy - 20],
                 "confidence": 0.9} for _l, _q, _s, cx, fy, _c in _CAST]
        tracked = self.player_tracker.update(dets, image, frame_index=idx)
        actions = []
        if idx == 20:
            tid = next(p["track_id"] for p in tracked if p["player_label"] == "P2B")
            actions = [{"frame_number": 18, "track_id": tid, "action": "dig",
                        "player_label": self.player_tracker.label_for(tid, frame=18)}]
        return {"tracked_players": tracked, "actions": actions}


def test_sequential_pass_records_labels_actions_and_sheets(tmp_path, monkeypatch):
    import src.analysis.frame_processor as fp

    video = str(tmp_path / "synth.mp4")
    writer = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*"mp4v"), 10, (_W, _H))
    assert writer.isOpened()
    for _ in range(30):
        writer.write(_frame())
    writer.release()
    monkeypatch.setattr(fp, "FrameProcessor", _StubProcessor)

    record, sheets = probe.sequential_pass(video, {}, max_frames=25, sheet_every_s=1.0)
    assert len(record["frames"]) == 25
    assert record["enrolled"] == ["P1A", "P2A", "P1B", "P2B"]
    last = record["frames"][-1]
    assert last["near_squad"] == 1 and not last["doubt"]
    assert sorted(b[1] for b in last["bodies"]) == ["P1A", "P1B", "P2A", "P2B"]
    assert record["actions"] == [{
        "frame": 18, "seen_at": 20, "track_id": record["actions"][0]["track_id"],
        "action": "dig", "label": "P2B", "legacy_label": record["actions"][0]["legacy_label"],
    }]
    # Frame 0 precedes the fresh-tracklet claim delay: no crop there yet.
    assert len(sheets["_stamps"]) == 3 and len(sheets["P1A"]) == 2
    paths = probe.write_sheets(sheets, record["fps"], tmp_path)
    assert len(paths) == 1 and paths[0].exists()
    assert probe.print_report(record, None)["labels"]["coverage"]["P1A"] > 0.5
