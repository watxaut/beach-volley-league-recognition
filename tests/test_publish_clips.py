"""src/publish/clips: the crop, the rally copy and its index, clips cut by
frame number (sequential decode, never a seek), and what the publisher
uploads and removes. The video tests need the ``ffmpeg`` binary."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

import postrun_sim as sim  # noqa: E402
from src.postrun.reconstruct import reconstruct  # noqa: E402
from src.publish import cli, clips  # noqa: E402
from src.publish.bundle import ATTACKS, attack_frames, build_bundle  # noqa: E402
from src.publish.client import SupabaseClient, SupabaseError  # noqa: E402

KEY = "20260920_1830_bogatell_ari_joan"
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs the ffmpeg binary")

#: The net as clicked on the two venues (1080p frames).
VALL_DHEBRON = {"net_top_points": [[455, 266], [1386, 276]],
                "midcourt_points": [[453, 541], [1375, 544]], "frame_dimensions": [1080, 1920]}
BEACH = {"net_top_points": [[558, 384], [1467, 369]],
         "midcourt_points": [[538, 645], [1426, 641]], "frame_dimensions": [1080, 1920]}


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #

def test_crop_is_three_net_heights_centred_on_the_net():
    x, y, w, h = clips.crop_box(VALL_DHEBRON, 1920, 1080)
    net = 542.5 - 271.0
    assert y == 0, "one net height above the tape leaves the frame: clamped"
    assert abs((y + h) - (542.5 + net)) <= 2, "one net height below the net's ground line"
    assert abs((x + w / 2) - 917.25) <= 2, "centred on the net"
    assert x < 453 and x + w > 1386, "both posts are in the picture"
    assert w % 2 == 0 and h % 2 == 0
    assert clips.fit_size(w, h) == (640, 480)

    x, y, w, h = clips.crop_box(BEACH, 1920, 1080)
    assert y > 0 and y + h < 1080 and abs(w / h - 4 / 3) < 0.01, "fits the frame: 4:3"


def test_crop_follows_the_frame_the_run_decoded():
    """A calibration clicked at 720p, a run that decoded the 1080p upscale."""
    small = {"net_top_points": [[303, 177], [924, 184]], "midcourt_points": [[302, 361], [917, 363]],
             "frame_dimensions": [720, 1280]}
    big = clips.crop_box(small, 1920, 1080)
    native = clips.crop_box(small, 1280, 720)
    assert all(abs(b - n * 1.5) <= 3 for b, n in zip(big, native))


@pytest.mark.parametrize("calibration", [None, {}, {"net_top_points": [[1, 2]]},
                                         {"net_top_points": [[0, 500], [9, 500]],
                                          "midcourt_points": [[0, 100], [9, 100]]}])
def test_no_usable_net_means_the_whole_frame(calibration):
    assert clips.crop_box(calibration, 1921, 1080) == (0, 0, 1920, 1080)


def test_fit_size_never_enlarges_and_stays_even():
    assert clips.fit_size(1920, 1080) == (640, 360)
    assert clips.fit_size(1086, 814) == (640, 480)
    assert clips.fit_size(301, 201) == (300, 200)


def test_rally_spans_pad_merge_and_clamp():
    points = [{"start_frame": 5, "end_frame": 60}, {"start_frame": 75, "end_frame": 90},
              {"start_frame": 300, "end_frame": 395}]
    # 10 fps: one second before the serve, two after the end
    assert clips.rally_spans(points, 10.0, n_frames=400) == [(0, 110), (290, 399)]
    assert clips.rally_spans([], 30.0) == []


def test_a_clip_window_is_a_position_in_the_copy():
    copy = clips.RallyCopy(Path("x.mp4"), 30.0, (640, 480), (0, 0, 640, 480),
                           [(100, 199), (300, 399)])
    assert copy.window(150) == (20, 95)          # 1 s before, 1.5 s after
    assert copy.window(310) == (100, 155)        # the second stretch starts at 100; cut at its edge
    assert copy.window(390) == (160, 199)
    assert copy.window(250) is None and copy.window(99) is None


# --------------------------------------------------------------------------- #
# the copy and the clips, on a video whose frames say their own number
# --------------------------------------------------------------------------- #

W, H, BAR = 640, 480, 4          # frame i shows a white bar BAR * i px wide


def _numbered_video(path: Path, n: int = 150) -> Path:
    import cv2

    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (W, H))
    for i in range(n):
        frame = np.zeros((H, W, 3), np.uint8)
        frame[:, :BAR * i] = 255
        out.write(frame)
    out.release()
    return path


def _numbers(path: Path):
    """The source frame number each frame of a video shows."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    seen = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        row = frame[H // 2, :, 1].astype(int)
        seen.append(int(round(int((row > 127).sum()) / BAR)))
    cap.release()
    return seen


POINTS = [{"start_frame": 40, "end_frame": 60}, {"start_frame": 100, "end_frame": 110}]


@needs_ffmpeg
def test_clips_are_cut_by_frame_number(tmp_path):
    video = _numbered_video(tmp_path / "v.avi")
    said = []
    made = clips.make_attack_clips(tmp_path, [50, 105, 5], points=POINTS, fps=10.0,
                                   video=video, say=said.append)
    assert sorted(made) == [50, 105], "frame 5 is in no rally: no clip"
    copy = clips.load_rally_copy(tmp_path)
    assert copy.spans == [(30, 80), (90, 130)] and copy.size == (W, H)
    assert _numbers(copy.path) == list(range(30, 81)) + list(range(90, 131))
    assert _numbers(made[50]) == list(range(40, 66)), "1 s before the contact to 1.5 s after"
    assert _numbers(made[105]) == list(range(95, 121))
    assert "2 of 3 attacks (2 cut now; 1 outside the rally copy" in said[-1]


@needs_ffmpeg
def test_a_republish_without_the_video_cuts_from_the_copy(tmp_path):
    video = _numbered_video(tmp_path / "v.avi")
    first = clips.make_attack_clips(tmp_path, [50, 105], points=POINTS, fps=10.0, video=video,
                                    say=lambda _: None)
    before = {f: (p.stat().st_mtime_ns, p.read_bytes()) for f, p in first.items()}
    copy_written = (tmp_path / clips.RALLIES_NAME).stat().st_mtime_ns
    video.unlink()

    # the rules changed: 105 is no attack any more, 70 and 85 are
    said = []
    again = clips.make_attack_clips(tmp_path, [50, 70, 85], points=POINTS, fps=10.0,
                                    video=None, say=said.append)
    assert sorted(again) == [50, 70], "85 was never copied and the video is gone"
    assert (again[50].stat().st_mtime_ns, again[50].read_bytes()) == before[50], "not cut again"
    assert _numbers(again[70]) == list(range(60, 81)), "cut at the edge of its rally"
    assert not (tmp_path / clips.CLIPS_DIR / "105.mp4").exists(), "no attack points at it"
    assert (tmp_path / clips.RALLIES_NAME).stat().st_mtime_ns == copy_written
    assert "2 of 3 attacks (1 cut now; 1 outside the rally copy" in said[-1]


@needs_ffmpeg
def test_the_copy_is_rebuilt_when_the_video_can_give_a_missing_attack(tmp_path):
    video = _numbered_video(tmp_path / "v.avi")
    clips.make_attack_clips(tmp_path, [50], points=POINTS[:1], fps=10.0, video=video,
                            say=lambda _: None)
    assert clips.load_rally_copy(tmp_path).spans == [(30, 80)]
    made = clips.make_attack_clips(tmp_path, [50, 105], points=POINTS, fps=10.0, video=video,
                                   say=lambda _: None)
    assert clips.load_rally_copy(tmp_path).spans == [(30, 80), (90, 130)]
    assert _numbers(made[50]) == list(range(40, 66)) and _numbers(made[105]) == list(range(95, 121))


@needs_ffmpeg
def test_a_video_that_ends_early_gives_a_copy_of_what_it_had(tmp_path):
    video = _numbered_video(tmp_path / "v.avi", n=100)
    made = clips.make_attack_clips(tmp_path, [50, 105], points=POINTS, fps=10.0, video=video,
                                   say=lambda _: None)
    assert clips.load_rally_copy(tmp_path).spans == [(30, 80), (90, 99)]
    assert sorted(made) == [50]


def test_without_a_copy_or_a_video_the_clips_of_an_earlier_publish_stay(tmp_path, monkeypatch):
    (tmp_path / clips.CLIPS_DIR).mkdir()
    (tmp_path / clips.CLIPS_DIR / "50.mp4").write_bytes(b"clip")
    said = []
    assert sorted(clips.make_attack_clips(tmp_path, [50, 70], points=POINTS, fps=10.0,
                                          say=said.append)) == [50]
    monkeypatch.setattr(clips.shutil, "which", lambda _: None)
    assert sorted(clips.make_attack_clips(tmp_path, [50, 70], points=POINTS, fps=10.0,
                                          say=said.append)) == [50]
    assert "ffmpeg is not installed" in said[-1]


def test_a_storage_path_names_its_content(tmp_path):
    (tmp_path / clips.CLIPS_DIR).mkdir()
    local = tmp_path / clips.CLIPS_DIR / "345.mp4"
    local.write_bytes(b"one")
    path = clips.storage_path(KEY, 345, local)
    assert path.startswith(f"clips/{KEY}/345-") and path.endswith(".mp4")
    assert clips.local_clip(tmp_path, path) == local
    local.write_bytes(b"two")
    assert clips.storage_path(KEY, 345, local) != path
    assert clips.local_clip(tmp_path, path) is None, "the file is no longer what the path names"
    assert clips.local_clip(tmp_path, f"clips/{KEY}/999-abc.mp4") is None


# --------------------------------------------------------------------------- #
# bundle
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def recon():
    b = sim.StreamBuilder(12.0 * 4 + 5.0)
    for i, side in enumerate(["near", "far", "far", "near"]):
        b.rally(sim.standard_rally(2.0 + 12.0 * i, side, sim.NEAR_A, exchanges=2))
    return json.loads(json.dumps(reconstruct(b.build(), b.g, points_to_win=3)))


def _run_dir(tmp_path, recon):
    run = tmp_path / "run"
    run.mkdir()
    (run / "match_reconstruction.json").write_text(json.dumps(recon))
    (run / "pipeline_output.json").write_text(json.dumps({
        "pipeline_version": "abc1234",
        "video": {"key": KEY, "path": f"resources/{KEY}.mp4", "fps": 30.0, "width": 1920,
                  "height": 1080, "total_frames": recon["n_frames"]}, "spikes": []}))
    return run


def test_only_a_credited_attack_carries_a_clip(tmp_path, recon):
    run = _run_dir(tmp_path, recon)
    frames = attack_frames(recon["points"])
    assert frames, "the synthetic match has attacks"
    every_touch = {t["frame"]: f"clips/{KEY}/{t['frame']}-x.mp4"
                   for p in recon["points"] for t in p["touches"]}
    bundle = build_bundle(run, clip_paths=every_touch)
    with_clip = [a for a in bundle["actions"] if "clip" in a["extra"]]
    assert sorted(a["frame"] for a in with_clip) == sorted(frames)
    assert all(a["slot"] and a["action"] in ATTACKS for a in with_clip)
    assert cli.clip_paths_of(bundle) == sorted(every_touch[f] for f in frames)


def test_a_run_without_clips_builds_the_bundle_it_always_did(tmp_path, recon):
    run = _run_dir(tmp_path, recon)
    plain = build_bundle(run)
    assert all("clip" not in a["extra"] for a in plain["actions"])
    assert build_bundle(run, clip_paths={})["content_sha256"] == plain["content_sha256"]
    frame = attack_frames(recon["points"])[0]
    assert build_bundle(run, clip_paths={frame: "clips/k/1-a.mp4"})["content_sha256"] \
        != plain["content_sha256"]


# --------------------------------------------------------------------------- #
# storage: what is sent, what is removed
# --------------------------------------------------------------------------- #

class FakeStorage:
    def __init__(self, held=(), list_fails=False):
        self.held, self.list_fails, self.calls = list(held), list_fails, []

    def list_objects(self, bucket, folder):
        self.calls.append(("list", bucket, folder))
        if self.list_fails:
            raise SupabaseError("HTTP 500")
        return list(self.held)

    def upload(self, bucket, path, data, content_type, upsert=True):
        self.calls.append(("upload", bucket, path, content_type))

    def remove_objects(self, bucket, paths):
        self.calls.append(("remove", bucket, list(paths)))
        return len(paths)

    def rpc(self, name, params):
        self.calls.append(("rpc", name))
        return {"result": "applied", "revision": 2, "match_id": 1}


def _bundle_with_local_clips(tmp_path, frames=(345, 811)):
    (tmp_path / clips.CLIPS_DIR).mkdir(exist_ok=True)
    actions = []
    for f in frames:
        local = tmp_path / clips.CLIPS_DIR / f"{f}.mp4"
        local.write_bytes(f"clip {f}".encode())
        actions.append({"frame": f, "extra": {"clip": clips.storage_path(KEY, f, local)}})
    actions.append({"frame": 1, "extra": {}})
    return {"match": {"match_key": KEY}, "actions": actions}


def test_only_a_clip_storage_lacks_is_sent_and_only_unnamed_ones_removed(tmp_path):
    bundle = _bundle_with_local_clips(tmp_path)
    here, new = cli.clip_paths_of(bundle)
    old = f"clips/{KEY}/300-0123456789ab.mp4"
    store = FakeStorage(held=[here, old])
    present = cli.upload_clips(store, bundle, tmp_path)
    assert store.calls == [("list", "match-media", f"clips/{KEY}"),
                           ("upload", "match-media", new, "video/mp4")]
    assert cli.prune_clips(store, bundle, present) == 1
    assert store.calls[-1] == ("remove", "match-media", [old])
    assert cli.prune_clips(store, bundle, [here, new]) == 0, "nothing to remove: no call"
    assert store.calls[-1] == ("remove", "match-media", [old])


def test_when_storage_cannot_be_listed_everything_is_sent_and_nothing_removed(tmp_path):
    bundle = _bundle_with_local_clips(tmp_path)
    store = FakeStorage(list_fails=True)
    present = cli.upload_clips(store, bundle, tmp_path)
    assert present is None
    assert [c[0] for c in store.calls] == ["list", "upload", "upload"]
    assert cli.prune_clips(store, bundle, present) == 0
    assert "remove" not in [c[0] for c in store.calls]


def test_a_clip_missing_on_this_disk_is_skipped_not_fatal(tmp_path, capsys):
    bundle = _bundle_with_local_clips(tmp_path)
    (tmp_path / clips.CLIPS_DIR / "345.mp4").unlink()
    store = FakeStorage()
    cli.upload_clips(store, bundle, tmp_path)
    assert [c[0] for c in store.calls] == ["list", "upload"]
    assert "1 not in this run directory" in capsys.readouterr().out


def test_publish_sends_clips_before_the_rows_and_removes_old_ones_after(tmp_path, recon,
                                                                         monkeypatch, capsys):
    run = _run_dir(tmp_path, recon)
    frame = attack_frames(recon["points"])[0]
    (run / clips.CLIPS_DIR).mkdir()
    local = run / clips.CLIPS_DIR / f"{frame}.mp4"
    local.write_bytes(b"clip")
    bundle = build_bundle(run, clip_paths={frame: clips.storage_path(KEY, frame, local)})
    saved = run / "match_bundle.json"
    saved.write_text(json.dumps(bundle))
    old = f"clips/{KEY}/1-0123456789ab.mp4"
    store = FakeStorage(held=[old])
    monkeypatch.setattr(SupabaseClient, "from_env", classmethod(lambda cls, env=None: store))
    rc = cli.main(["--from-bundle", str(saved), "--log", str(tmp_path / "log.jsonl")])
    assert rc == 0, capsys.readouterr().err
    kinds = [(c[0], c[1]) for c in store.calls]
    assert kinds == [("list", "match-media"), ("upload", "match-media"),
                     ("upload", "match-bundles"), ("rpc", "ingest_match_bundle"),
                     ("remove", "match-media")]
    assert store.calls[-1][2] == [old]


# --------------------------------------------------------------------------- #
# client
# --------------------------------------------------------------------------- #

def test_list_objects_pages_and_returns_full_paths(monkeypatch):
    client = SupabaseClient("https://x.supabase.co", "sb_secret_x")
    sent = []

    def fake(method, path, body=None, headers=None, raw_bytes=False):
        req = json.loads(body)
        sent.append((method, path, req))
        rows = [{"name": "1-a.mp4", "id": "u1"}, {"name": "clips/k/2-b.mp4", "id": "u2"},
                {"name": "sub", "id": None}]
        return rows[req["offset"]:req["offset"] + req["limit"]]

    monkeypatch.setattr(client, "_request", fake)
    assert client.list_objects("match-media", "clips/k/", page=2) == ["clips/k/1-a.mp4",
                                                                      "clips/k/2-b.mp4"]
    assert [s[2]["offset"] for s in sent] == [0, 2]
    assert sent[0][:2] == ("POST", "/storage/v1/object/list/match-media")
    assert sent[0][2]["prefix"] == "clips/k"


def test_remove_objects_sends_the_paths(monkeypatch):
    client = SupabaseClient("https://x.supabase.co", "sb_secret_x")
    sent = []
    monkeypatch.setattr(client, "_request",
                        lambda method, path, body=None, headers=None, raw_bytes=False:
                        sent.append((method, path, json.loads(body))))
    assert client.remove_objects("match-media", ["a", "b", "c"], chunk=2) == 3
    assert sent == [("DELETE", "/storage/v1/object/match-media", {"prefixes": ["a", "b"]}),
                    ("DELETE", "/storage/v1/object/match-media", {"prefixes": ["c"]})]
