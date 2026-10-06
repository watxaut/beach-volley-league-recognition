"""src/publish/republish: finds every published run, redoes post-run + publish
with a fake runner, and never lets one bad match hide the others."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.publish import republish as rp  # noqa: E402


def _run_dir(root: Path, name: str, key: str, *, diag=True, calibration=True,
             mtime=None, nested=False) -> Path:
    d = root / ("postrun" if nested else "") / name
    d.mkdir(parents=True)
    (d / "match_bundle.json").write_text(json.dumps({"match": {"match_key": key}}))
    cal = root.parent / "calibrations" / f"{name}.json"
    (d / "pipeline_output.json").write_text(json.dumps(
        {"video": {"calibration_readiness": {"calibration_path": str(cal)}}}))
    if diag:
        (d / "diag.jsonl").write_text("{}\n")
    if calibration:
        cal.parent.mkdir(exist_ok=True)
        cal.write_text("{}")
    if mtime:
        os.utime(d / "match_bundle.json", (mtime, mtime))
    return d


class FakeRunner:
    def __init__(self, fail_on=None, publish_says="published: applied (revision 2, match id 1)"):
        self.calls = []
        self.fail_on = fail_on or {}
        self.publish_says = publish_says

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        module = cmd[2]
        target = cmd[3]
        if (module, target) in self.fail_on:
            return subprocess.CompletedProcess(cmd, 1, "", self.fail_on[(module, target)])
        out = self.publish_says if module == "src.publish" else "written"
        return subprocess.CompletedProcess(cmd, 0, out, "")


def test_discover_finds_published_runs_flat_and_nested(tmp_path):
    root = tmp_path / "output"
    _run_dir(root, "a", "20260920_1800_local_ari_joan", nested=True)   # output/postrun/a
    _run_dir(root, "b", "20260927_1900_bogatell_laia_nil")             # output/b
    (root / "never_published").mkdir()
    (root / "never_published" / "diag.jsonl").write_text("{}")
    found = rp.discover(root, cwd=tmp_path)
    assert [c.key for c in found] == ["20260920_1800_local_ari_joan", "20260927_1900_bogatell_laia_nil"]
    assert all(c.skip is None for c in found)


def test_discover_reports_what_cannot_be_recomputed(tmp_path):
    root = tmp_path / "output"
    _run_dir(root, "nodiag", "20260101_1000_x_a", diag=False)
    _run_dir(root, "nocal", "20260102_1000_x_b", calibration=False)
    by_key = {c.key: c for c in rp.discover(root, cwd=tmp_path)}
    assert "diag.jsonl" in by_key["20260101_1000_x_a"].skip
    assert "calibration" in by_key["20260102_1000_x_b"].skip


def test_the_newest_run_of_a_key_wins(tmp_path):
    root = tmp_path / "output"
    _run_dir(root, "old", "20260920_1800_local_ari_joan", mtime=1_000_000)
    _run_dir(root, "new", "20260920_1800_local_ari_joan", mtime=2_000_000)
    (found,) = rp.discover(root, cwd=tmp_path)
    assert found.run_dir.name == "new"


def test_republish_runs_postrun_then_publish_with_the_key(tmp_path):
    root = tmp_path / "output"
    _run_dir(root, "a", "20260920_1800_local_ari_joan")
    run = FakeRunner()
    out = rp.republish(rp.discover(root, cwd=tmp_path), run=run, python="py", say=lambda _m: None)
    assert [o.status for o in out] == ["applied"]
    assert run.calls[0][:3] == ["py", "-m", "src.postrun"]
    assert run.calls[1][:3] == ["py", "-m", "src.publish"]
    assert run.calls[1][run.calls[1].index("--match-key") + 1] == "20260920_1800_local_ari_joan"
    assert "--allow-dirty" not in run.calls[1]


def test_unchanged_is_reported_and_dry_run_runs_nothing(tmp_path):
    root = tmp_path / "output"
    _run_dir(root, "a", "20260920_1800_local_ari_joan")
    run = FakeRunner(publish_says="published: unchanged (revision 3, match id 1)")
    out = rp.republish(rp.discover(root, cwd=tmp_path), run=run, say=lambda _m: None)
    assert out[0].status == "unchanged"
    run2 = FakeRunner()
    planned = rp.republish(rp.discover(root, cwd=tmp_path), dry_run=True, run=run2, say=lambda _m: None)
    assert planned[0].status == "planned" and run2.calls == []


def test_one_failure_does_not_stop_the_rest_and_sets_the_exit_code(tmp_path, monkeypatch, capsys):
    root = tmp_path / "output"
    a = _run_dir(root, "a", "20260101_1000_x_a")
    _run_dir(root, "b", "20260102_1000_x_b")
    monkeypatch.chdir(tmp_path)
    run = FakeRunner(fail_on={("src.postrun", str(a.relative_to(tmp_path))): "boom"})
    code = rp.main(["--root", "output"], run=run)
    out = capsys.readouterr().out
    assert code == 1
    assert "1 applied" in out and "1 failed" in out
    assert any(c[2] == "src.publish" for c in run.calls)       # b still published


def test_a_skipped_match_fails_the_run_so_it_is_never_silently_left_behind(tmp_path, monkeypatch):
    root = tmp_path / "output"
    _run_dir(root, "a", "20260101_1000_x_a", diag=False)
    monkeypatch.chdir(tmp_path)
    assert rp.main(["--root", "output", "--dry-run"], run=FakeRunner()) == 1


def test_only_filters_and_unknown_keys_are_an_error(tmp_path, monkeypatch):
    root = tmp_path / "output"
    _run_dir(root, "a", "20260101_1000_x_a")
    _run_dir(root, "b", "20260102_1000_x_b")
    monkeypatch.chdir(tmp_path)
    run = FakeRunner()
    assert rp.main(["--root", "output", "--only", "20260102_1000_x_b"], run=run) == 0
    assert all("b" in c[3] for c in run.calls if c[2] == "src.postrun")
    assert rp.main(["--root", "output", "--only", "nope"], run=run) == 2
