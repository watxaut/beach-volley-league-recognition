"""Pull the members' bug reports and suggestions for a working session.

    python -m src.publish.feedback                 # open reports -> output/feedback/
    python -m src.publish.feedback --all           # closed ones too
    python -m src.publish.feedback --done 3 5 --note "fixed in #102"
    python -m src.publish.feedback --dismiss 4 --note "not planned"

Members send reports with the web app's Feedback button (table ``feedback``,
screenshots in the private ``feedback-media`` bucket). Each pull REPLACES the
local mirror: ``index.md`` lists the reports, and every report has a folder
``<id>_<kind>/`` with ``report.md`` and its screenshots. ``--done`` /
``--dismiss`` close reports on the web; the note is what the author reads
under Settings.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from .client import DEFAULT_ENV_FILE, SupabaseClient, SupabaseError

BUCKET = "feedback-media"
COLUMNS = "id,user_id,kind,message,page,context,screenshots,status,admin_note,created_at"
REPORT_DIR = re.compile(r"^\d+_(bug|suggestion)$")


def fetch(client: SupabaseClient, include_closed: bool = False) -> List[Dict]:
    """Reports oldest first, each with its author's ``email``."""
    filters = {"order": "id.asc"}
    if not include_closed:
        filters["status"] = "eq.open"
    reports = client.select_all("feedback", COLUMNS, filters=filters)
    emails = {p["user_id"]: p.get("email") for p in client.select_all("profiles", "user_id,email")}
    for r in reports:
        r["email"] = emails.get(r["user_id"])
    return reports


def report_markdown(report: Dict, images: List[str]) -> str:
    context = report.get("context") or {}
    lines = [
        f"# #{report['id']} {report['kind']} ({report['status']})",
        "",
        f"- from: {report.get('email') or report['user_id']}",
        f"- sent: {report['created_at']}",
        f"- page: {report.get('page') or 'unknown'}",
    ]
    lines += [f"- {key}: {context[key]}" for key in sorted(context)]
    if report.get("admin_note"):
        lines.append(f"- note: {report['admin_note']}")
    lines += ["", report["message"], ""]
    lines += [f"![screenshot {i}]({name})" for i, name in enumerate(images, 1)]
    return "\n".join(lines).rstrip() + "\n"


def write_mirror(client: SupabaseClient, reports: List[Dict], out: Path) -> List[str]:
    """Replace ``out`` with ``reports``; returns the screenshots that could not
    be downloaded (the report is still written, with the gap named)."""
    out.mkdir(parents=True, exist_ok=True)
    for old in out.iterdir():  # only what an earlier pull wrote
        if old.is_dir() and REPORT_DIR.match(old.name):
            shutil.rmtree(old)
    missing: List[str] = []
    index = [f"# Feedback ({len(reports)} report{'s' if len(reports) != 1 else ''})", ""]
    for r in reports:
        folder = out / f"{r['id']}_{r['kind']}"
        folder.mkdir()
        images: List[str] = []
        for i, path in enumerate(r.get("screenshots") or [], 1):
            name = f"screenshot_{i}{Path(path).suffix or '.jpg'}"
            try:
                (folder / name).write_bytes(client.download_bytes(BUCKET, path))
            except SupabaseError as exc:
                missing.append(f"#{r['id']} {path}: {exc}")
                continue
            images.append(name)
        (folder / "report.md").write_text(report_markdown(r, images))
        first = r["message"].strip().splitlines()[0]
        index.append(f"- [#{r['id']} {r['kind']} ({r['status']})]({folder.name}/report.md), "
                     f"{len(images)} screenshot{'s' if len(images) != 1 else ''}, "
                     f"{r.get('page') or 'unknown page'}: {first[:120]}")
    (out / "index.md").write_text("\n".join(index) + "\n")
    return missing


def close(client: SupabaseClient, ids: List[int], status: str, note: Optional[str]) -> List[int]:
    """Set ``status`` (and the note, when given) on ``ids``; returns the ids found."""
    values = {"status": status, **({"admin_note": note} if note is not None else {})}
    rows = client.update("feedback", {"id": f"in.({','.join(str(i) for i in ids)})"}, values)
    return sorted(r["id"] for r in rows)


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.publish.feedback", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("output/feedback"))
    p.add_argument("--env", type=Path, default=DEFAULT_ENV_FILE)
    p.add_argument("--all", action="store_true", help="include done / dismissed reports")
    p.add_argument("--done", type=int, nargs="+", default=[], metavar="ID")
    p.add_argument("--dismiss", type=int, nargs="+", default=[], metavar="ID")
    p.add_argument("--note", help="note for the author, stored with --done / --dismiss")
    args = p.parse_args(argv)
    try:
        client = SupabaseClient.from_env(args.env)
        for ids, status in ((args.done, "done"), (args.dismiss, "dismissed")):
            if not ids:
                continue
            found = close(client, ids, status, args.note)
            print(f"{status}: {', '.join(f'#{i}' for i in found) or 'none'}")
            unknown = sorted(set(ids) - set(found))
            if unknown:
                print(f"error: no such report: {', '.join(f'#{i}' for i in unknown)}")
                return 1
        reports = fetch(client, include_closed=args.all)
        missing = write_mirror(client, reports, args.out)
    except SupabaseError as exc:
        print(f"error: {exc}")
        return 1
    n_shots = sum(len(r.get("screenshots") or []) for r in reports) - len(missing)
    print(f"{args.out}/index.md: {len(reports)} report{'s' if len(reports) != 1 else ''}, "
          f"{n_shots} screenshot{'s' if n_shots != 1 else ''}")
    for line in missing:
        print(f"error: screenshot not downloaded: {line}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
