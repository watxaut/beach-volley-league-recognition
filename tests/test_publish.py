"""src/publish: naming, bundle, credit/fantasy parity with postrun.player_stats,
thumbnails (sequential decode), CLI guards. The bundle is built from a REAL
post-run reconstruction of the synthetic match in ``postrun_sim``."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

import postrun_sim as sim  # noqa: E402
from src.postrun.reconstruct import player_stats, reconstruct  # noqa: E402
from src.publish import cli  # noqa: E402
from src.publish.bundle import (BundleError, build_bundle, content_sha256,  # noqa: E402
                                to_own_frame)
from src.publish.client import SupabaseClient, load_env_file  # noqa: E402
from src.publish.fantasy import G1_RULES, score_actions  # noqa: E402
from src.publish.naming import MatchKeyError, match_key_for, parse_match_key, slugify  # noqa: E402

KEY = "20260920_1830_bogatell_ari_joan"


# --------------------------------------------------------------------------- #
# naming
# --------------------------------------------------------------------------- #

def test_parse_match_key():
    k = parse_match_key(KEY, today=date(2026, 10, 6))
    assert (k.match_date, k.start_time.strftime("%H:%M"), k.slug) == \
        (date(2026, 9, 20), "18:30", "bogatell_ari_joan")


@pytest.mark.parametrize("bad", [
    "20260920_match_ari_joan",          # legacy: no time
    "20260920_1830",                    # no venue
    "20260920_1830_Bogatell",           # uppercase
    "20260920_2460_x",                  # not a time
    "20261340_1830_x",                  # not a date
    "20290928_1830_entreno",            # future (the ground_truth typo)
])
def test_parse_match_key_refuses(bad):
    with pytest.raises(MatchKeyError):
        parse_match_key(bad, today=date(2026, 10, 6))


def test_match_key_for_adds_the_timestamp():
    at = datetime(2026, 10, 4, 18, 5)
    assert match_key_for(KEY, None) == KEY
    assert match_key_for("20260920_match_ari_joan", at) == "20260920_1805_match_ari_joan"
    assert match_key_for("IMG_1234", at) == "20261004_1805_img_1234"
    assert match_key_for("Bogatell – Ari & Joan", at) == "20261004_1805_bogatell_ari_joan"
    with pytest.raises(MatchKeyError):
        match_key_for("IMG_1234", None)
    assert slugify("Vall d'Hebron") == "vall_d_hebron"


# --------------------------------------------------------------------------- #
# fantasy rules mirror the migration seed
# --------------------------------------------------------------------------- #

def test_g1_rules_mirror_the_migration_seed():
    sql = (REPO / "supabase/migrations/20261006120000_init.sql").read_text()
    rows = re.findall(
        r"\('(\w+)',\s*'([^']+)',\s*array\[([^\]]+)\],\s*(null|'\w+'),\s*(true|false),\s*(-?[\d.]+),",
        sql)
    seeded = {r[0]: {"label": r[1], "actions": re.findall(r"'(\w+)'", r[2]),
                     "outcome": None if r[3] == "null" else r[3].strip("'"),
                     "assist_only": r[4] == "true", "points": float(r[5])} for r in rows}
    assert seeded == {r["rule_key"]: {k: r[k] for k in
                                      ("label", "actions", "outcome", "assist_only", "points")}
                      for r in G1_RULES}


def test_player_stats_charges_ball_handling_errors_32f():
    """Open point 32f: a set marked `error` (P6 f3229) costs -1 like G1 says."""
    pt = {"serve": {"player": "P1A", "outcome": None},
          "touches": [
              {"touch_number": 0, "action": "serve", "player": "P1A", "observed": True,
               "side": "near", "outcome": None},
              {"touch_number": 1, "action": "dig", "player": "P1B", "observed": True,
               "side": "far", "outcome": None},
              {"touch_number": 2, "action": "set", "player": "P2B", "observed": True,
               "side": "far", "outcome": "error"}]}
    stats = player_stats([pt])
    assert stats["P2B"]["handling_errors"] == 1 and stats["P2B"]["fantasy"] == -1.0
    assert stats["P1B"]["fantasy"] == 1.0


# --------------------------------------------------------------------------- #
# bundle from a real reconstruction of the synthetic match
# --------------------------------------------------------------------------- #

def _sim_match():
    b = sim.StreamBuilder(12.0 * 4 + 5.0)
    for i, side in enumerate(["near", "far", "far", "near"]):
        b.rally(sim.standard_rally(2.0 + 12.0 * i, side, sim.NEAR_A, exchanges=2))
    result = reconstruct(b.build(), b.g, points_to_win=3)
    return json.loads(json.dumps(result))      # exactly what the CLI writes to disk


@pytest.fixture(scope="module")
def recon():
    return _sim_match()


def _run_dir(tmp_path, recon, video_key=f"{KEY}_up1080", spikes=None):
    run = tmp_path / "run"
    run.mkdir()
    (run / "match_reconstruction.json").write_text(json.dumps(recon))
    (run / "pipeline_output.json").write_text(json.dumps({
        "pipeline_version": "abc1234",
        "video": {"key": video_key, "path": f"resources/{video_key}.mp4",
                  "fps": 30.0, "width": 1920, "height": 1080, "total_frames": recon["n_frames"]},
        "spikes": spikes or []}))
    return run


def test_bundle_shape_and_hash(tmp_path, recon):
    bundle = build_bundle(_run_dir(tmp_path, recon))
    m = bundle["match"]
    assert m["match_key"] == KEY                 # _up1080 cache suffix stripped
    assert (m["match_date"], m["start_time"]) == ("2026-09-20", "18:30")
    assert (m["score_a"], m["score_b"]) == (recon["checks"]["final_score"]["A"],
                                            recon["checks"]["final_score"]["B"])
    assert len(bundle["points"]) == len(recon["points"])
    assert len(bundle["actions"]) == sum(len(p["touches"]) for p in recon["points"])
    assert [s["slot"] for s in bundle["slots"]] == ["P1A", "P2A", "P1B", "P2B"]
    assert bundle["content_sha256"] == content_sha256(bundle)
    seqs = [(a["point_no"], a["seq"]) for a in bundle["actions"]]
    assert len(set(seqs)) == len(seqs)


def test_hash_ignores_provenance_and_note_but_not_content(tmp_path, recon):
    run = _run_dir(tmp_path, recon)
    a = build_bundle(run, provenance={"host": "x"}, note="first")
    b = build_bundle(run, provenance={"host": "y"}, note="second")
    assert a["content_sha256"] == b["content_sha256"]
    c = build_bundle(run, video_url="https://drive.google.com/file/d/new/view")
    assert c["content_sha256"] != a["content_sha256"]


def test_credits_and_fantasy_equal_player_stats(tmp_path, recon):
    """The web's numbers ARE the owner-ratified post-run numbers."""
    bundle = build_bundle(_run_dir(tmp_path, recon))
    ps = player_stats(recon["points"])
    credited = [a for a in bundle["actions"] if a["slot"]]
    assert credited, "the synthetic match credits touches"
    for slot, row in ps.items():
        if slot.startswith("_"):
            continue
        mine = [a for a in credited if a["slot"] == slot]
        count = lambda f: sum(1 for a in mine if f(a))  # noqa: E731
        assert count(lambda a: a["action"] == "serve") == row["serves"]
        assert count(lambda a: a["action"] == "dig") == row["digs"]
        assert count(lambda a: a["action"] == "set") == row["sets"]
        assert count(lambda a: a["action"] == "spike") == row["spikes"]
        assert count(lambda a: a["is_assist"]) == row["assists"]
        assert count(lambda a: a["action"] in ("spike", "overpass")
                     and a["outcome"] == "kill") == row["kills"]
    fantasy = score_actions(bundle["actions"])
    for slot, row in ps.items():
        if not slot.startswith("_"):
            assert fantasy.get(slot, {"fantasy": 0.0})["fantasy"] == row["fantasy"], slot


def test_legacy_name_needs_a_match_key(tmp_path, recon):
    run = _run_dir(tmp_path, recon, video_key="20260920_match_ari_joan_up1080")
    with pytest.raises(BundleError, match="--match-key"):
        build_bundle(run)
    assert build_bundle(run, match_key=KEY)["match"]["match_key"] == KEY


def test_spike_join_and_attacker_frame_landing(tmp_path, recon):
    attacks = [t for p in recon["points"] for t in p["touches"]
               if t["action"] in ("spike", "overpass")]
    first = attacks[0]
    spikes = [{"frame": first["frame"] + 3, "attack_zone": {"side": "A", "zone": 2},
               "spike_type": "hard", "outcome": "dug", "landing_zone": None, "dug_zone": None}]
    bundle = build_bundle(_run_dir(tmp_path, recon, spikes=spikes))
    row = next(a for a in bundle["actions"] if a["frame"] == first["frame"])
    assert row["attack_zone"] == 2 and row["spike_type"] == "hard"
    # any landing is on the OTHER half in the attacker's own frame (> 8 m from own baseline)
    for a in bundle["actions"]:
        if a["landing_y_m"] is not None:
            assert a["landing_y_m"] > 8.0, a


def test_to_own_frame():
    assert to_own_frame(1.0, 12.0, "near") == (1.0, 4.0)      # 4 m from the near baseline
    assert to_own_frame(1.0, 3.0, "far") == (7.0, 3.0)        # far team: x mirrored
    assert to_own_frame(None, None, None) == (None, None)


# --------------------------------------------------------------------------- #
# thumbnails: sequential decode, crop at the labelled box
# --------------------------------------------------------------------------- #

def test_slot_thumbnails(tmp_path):
    import cv2
    from src.publish.thumbs import make_slot_thumbnails

    video = tmp_path / "v.avi"
    w = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 30, (320, 240))
    for i in range(30):
        frame = np.zeros((240, 320, 3), np.uint8)
        frame[40:200, 100:140] = (0, 0, 255) if i == 12 else (40, 40, 40)
        w.write(frame)
    w.release()
    diag = tmp_path / "diag.jsonl"
    with open(diag, "w") as f:
        f.write(json.dumps({"meta": {"schema_version": 4, "fps": 30}}) + "\n")
        for i in range(30):
            f.write(json.dumps({"frame": i, "players": [
                {"track_id": 1, "bbox": [100, 40, 140, 200], "player_label": "P1A",
                 "team": "A"}]}) + "\n")
    recon = {"points": [{"touches": [{"frame": 12, "player": "P1A", "observed": True}]}]}
    out = make_slot_thumbnails(video, diag, recon, tmp_path / "thumbs")
    assert set(out) == {"P1A"}
    img = cv2.imread(str(out["P1A"]))
    assert img.shape[0] == 240
    b, g, r = img[img.shape[0] // 2, img.shape[1] // 2]
    assert r > 150 and b < 100, "the crop is frame 12 (red), found by sequential decode"


# --------------------------------------------------------------------------- #
# CLI guards (no network)
# --------------------------------------------------------------------------- #

def test_cli_dry_run_without_credentials(tmp_path, recon, monkeypatch, capsys):
    for k in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(k, raising=False)
    run = _run_dir(tmp_path, recon)
    rc = cli.main([str(run), "--dry-run", "--no-thumbs", "--env", str(tmp_path / "none")])
    out = capsys.readouterr().out
    assert rc == 0 and "dry run: nothing written" in out and KEY in out
    saved = json.loads((run / "match_bundle.json").read_text())
    assert saved["content_sha256"] == content_sha256(saved)


def test_cli_refuses_a_dirty_tree(tmp_path, recon, monkeypatch, capsys):
    monkeypatch.setattr(cli, "git_state", lambda: {"publisher_version": "x", "git_dirty": True})
    rc = cli.main([str(_run_dir(tmp_path, recon)), "--no-thumbs",
                   "--env", str(tmp_path / "none")])
    assert rc == 2 and "uncommitted" in capsys.readouterr().err


def test_cli_from_bundle_rejects_tampering(tmp_path, recon, capsys):
    bundle = build_bundle(_run_dir(tmp_path, recon))
    bundle["match"]["score_a"] = 99
    path = tmp_path / "b.json"
    path.write_text(json.dumps(bundle))
    assert cli.main(["--from-bundle", str(path), "--dry-run"]) == 2
    assert "content_sha256" in capsys.readouterr().err


def test_env_file_and_key_headers(tmp_path, monkeypatch):
    for k in ("SUPABASE_URL", "SUPABASE_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    env = tmp_path / ".env.publish"
    env.write_text("# creds\nSUPABASE_URL=https://x.supabase.co\nSUPABASE_SECRET_KEY='sb_secret_abc'\n")
    values = load_env_file(env)
    assert values["SUPABASE_SECRET_KEY"] == "sb_secret_abc"
    c = SupabaseClient.from_env(env)
    assert "Authorization" not in c._headers() and c._headers()["apikey"] == "sb_secret_abc"
    assert SupabaseClient("https://x", "eyJabc")._headers()["Authorization"] == "Bearer eyJabc"
