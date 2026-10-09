"""`make feedback`: the local mirror of the members' reports (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.publish import feedback  # noqa: E402
from src.publish.client import SupabaseError  # noqa: E402

UID = "00000000-0000-0000-0000-0000000000a1"
JPEG = b"\xff\xd8\xff\xe0 not text \x00\xff"


class FakeClient:
    def __init__(self):
        self.rows = [
            {"id": 1, "user_id": UID, "kind": "bug", "message": "Map cut off\non my phone",
             "page": "/players/1", "context": {"viewport": "390x844", "build": "abc1234"},
             "screenshots": [f"{UID}/a.jpg", f"{UID}/gone.jpg"], "status": "open",
             "admin_note": None, "created_at": "2026-10-09T10:00:00+00:00"},
            {"id": 2, "user_id": "someone-else", "kind": "suggestion", "message": "Dark mode toggle",
             "page": None, "context": {}, "screenshots": [], "status": "done",
             "admin_note": "shipped", "created_at": "2026-10-08T10:00:00+00:00"},
        ]
        self.updates = []

    def select_all(self, table, columns="*", page=1000, filters=None):
        if table == "profiles":
            return [{"user_id": UID, "email": "ari@check.test"}]
        assert table == "feedback"
        only_open = (filters or {}).get("status") == "eq.open"
        return [dict(r) for r in self.rows if not only_open or r["status"] == "open"]

    def download_bytes(self, bucket, path):
        assert bucket == "feedback-media"
        if path.endswith("gone.jpg"):
            raise SupabaseError("HTTP 404")
        return JPEG

    def update(self, table, filters, values):
        self.updates.append((table, filters, values))
        ids = {int(i) for i in filters["id"][4:-1].split(",")}
        hit = [r for r in self.rows if r["id"] in ids]
        for r in hit:
            r.update(values)
        return hit


def test_open_reports_are_mirrored_with_their_screenshots(tmp_path):
    client = FakeClient()
    stale = tmp_path / "9_bug"
    stale.mkdir()
    keep = tmp_path / "notes"
    keep.mkdir()

    missing = feedback.write_mirror(client, feedback.fetch(client), tmp_path)

    assert not stale.exists() and keep.exists(), "only folders of an earlier pull are replaced"
    assert (tmp_path / "1_bug" / "screenshot_1.jpg").read_bytes() == JPEG, "images stay binary"
    report = (tmp_path / "1_bug" / "report.md").read_text()
    assert "from: ari@check.test" in report and "page: /players/1" in report
    assert "viewport: 390x844" in report and "Map cut off\non my phone" in report
    assert "![screenshot 1](screenshot_1.jpg)" in report and "screenshot_2" not in report
    assert len(missing) == 1 and "gone.jpg" in missing[0], "a lost screenshot is reported, not hidden"
    index = (tmp_path / "index.md").read_text()
    assert "1 report)" in index and "1_bug/report.md" in index and "Map cut off" in index
    assert not (tmp_path / "2_suggestion").exists(), "a closed report is not pulled by default"


def test_all_includes_closed_reports_and_unknown_authors(tmp_path):
    client = FakeClient()
    feedback.write_mirror(client, feedback.fetch(client, include_closed=True), tmp_path)
    report = (tmp_path / "2_suggestion" / "report.md").read_text()
    assert "from: someone-else" in report and "note: shipped" in report and "page: unknown" in report


def test_closing_reports_names_the_ones_that_do_not_exist(tmp_path, monkeypatch, capsys):
    client = FakeClient()
    monkeypatch.setattr(feedback.SupabaseClient, "from_env", classmethod(lambda cls, env: client))
    assert feedback.main(["--out", str(tmp_path), "--done", "1", "--note", "fixed"]) == 0
    assert client.updates == [("feedback", {"id": "in.(1)"}, {"status": "done", "admin_note": "fixed"})]
    assert "0 reports" in capsys.readouterr().out, "the closed report left the open mirror"

    assert feedback.main(["--out", str(tmp_path), "--dismiss", "1", "77"]) == 1
    assert client.updates[-1][2] == {"status": "dismissed"}, "no --note leaves the note alone"
    assert "no such report: #77" in capsys.readouterr().out
