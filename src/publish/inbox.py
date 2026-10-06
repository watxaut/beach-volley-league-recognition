"""Drive inbox -> local run -> draft on the web (`make inbox`).

    python -m src.publish.inbox            # one pass (launchd runs it every 30 min)
    python -m src.publish.inbox --dry-run  # list what it would do
    python -m src.publish.inbox --retry <match_key>   # clear a failed entry

For every video in the shared Drive folder (rclone remote ``gdrive:VolleyInbox``):

1. download it and name it ``YYYYMMDD_HHMM_<slug>`` (date + LOCAL start time
   from the file's ``creation_time``; a name that already conforms is kept,
   a ``YYYYMMDD_<slug>`` name only gains the time) -> ``resources/<key>.<ext>``
   and ``output/<key>/source.json`` (Drive link for the publication log);
2. wait for ``calibrations/<key>.json`` -- the one manual step (the tripod
   moves between videos): a notification says which command to run, once;
3. ``make run-match`` (only on AC power, under ``caffeinate``);
4. ``python -m src.publish output/<key>`` (lands as a DRAFT);
5. move the Drive file to ``VolleyArchive/<key>.<ext>`` (a server-side move
   keeps the file id, so the stored link stays valid).

Every step checks its own output, so an interrupted pass simply resumes.
State (Drive id -> key/status) lives in ``data/inbox_state.json``. Run it
from the dedicated prod worktree (AGENTS.md §8; the publisher refuses a
dirty tree).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from .client import DEFAULT_ENV_FILE, load_env_file
from .naming import MatchKeyError, match_key_for, parse_match_key

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi"}
Runner = Callable[..., subprocess.CompletedProcess]

ST_NEEDS_CALIBRATION = "needs_calibration"
ST_FAILED = "failed"
ST_ARCHIVED = "archived"


@dataclass
class InboxConfig:
    remote: str = "gdrive"
    inbox: str = "VolleyInbox"
    archive: str = "VolleyArchive"
    tz: str = "Europe/Madrid"
    require_ac: bool = True
    root: Path = Path(".")
    python: str = sys.executable
    make: str = "make"

    @property
    def resources(self) -> Path:
        return self.root / "resources"

    @property
    def calibrations(self) -> Path:
        return self.root / "calibrations"

    @property
    def output(self) -> Path:
        return self.root / "output"

    @property
    def state_path(self) -> Path:
        return self.root / "data" / "inbox_state.json"

    @property
    def lock_path(self) -> Path:
        return self.root / "data" / "inbox.lock"

    @classmethod
    def from_env(cls, env: Dict[str, str], root: Optional[Path] = None) -> "InboxConfig":
        return cls(remote=env.get("VOLLEY_RCLONE_REMOTE", "gdrive"),
                   inbox=env.get("VOLLEY_DRIVE_INBOX", "VolleyInbox"),
                   archive=env.get("VOLLEY_DRIVE_ARCHIVE", "VolleyArchive"),
                   tz=env.get("VOLLEY_TZ", "Europe/Madrid"),
                   require_ac=env.get("VOLLEY_REQUIRE_AC", "1") != "0",
                   root=(root or Path.cwd()).resolve())


@dataclass
class Inbox:
    cfg: InboxConfig
    run: Runner = subprocess.run
    notify_cmd: Optional[str] = field(default_factory=lambda: shutil.which("osascript"))
    log: List[str] = field(default_factory=list)

    # -- plumbing -------------------------------------------------------------

    def say(self, msg: str) -> None:
        line = f"[inbox] {msg}"
        self.log.append(line)
        print(line, flush=True)

    def notify(self, msg: str) -> None:
        self.say(f"NOTIFY {msg}")
        if self.notify_cmd:
            text = msg.replace('"', "'")
            self.run([self.notify_cmd, "-e",
                      f'display notification "{text}" with title "Volley inbox"'],
                     capture_output=True, text=True)

    def load_state(self) -> Dict[str, Any]:
        if self.cfg.state_path.exists():
            return json.loads(self.cfg.state_path.read_text())
        return {"files": {}}

    def save_state(self, state: Dict[str, Any]) -> None:
        self.cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cfg.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1, sort_keys=True))
        tmp.replace(self.cfg.state_path)

    def _remote(self, folder: str, name: str = "") -> str:
        return f"{self.cfg.remote}:{folder}" + (f"/{name}" if name else "")

    # -- external reads ---------------------------------------------------------

    def list_inbox(self) -> List[Dict[str, Any]]:
        res = self.run(["rclone", "lsjson", "--files-only", self._remote(self.cfg.inbox)],
                       capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"rclone lsjson failed: {res.stderr.strip()}")
        return [e for e in json.loads(res.stdout or "[]")
                if Path(e["Name"]).suffix.lower() in VIDEO_EXTS]

    def on_ac_power(self) -> bool:
        if not self.cfg.require_ac or shutil.which("pmset") is None:
            return True
        res = self.run(["pmset", "-g", "batt"], capture_output=True, text=True)
        return "AC Power" in res.stdout

    def recording_start(self, video: Path, drive_modtime: Optional[str]):
        """LOCAL start time of the recording: the container's creation_time,
        else the Drive modification time (flagged in source.json)."""
        tz = ZoneInfo(self.cfg.tz)
        res = self.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format",
                        "-show_streams", str(video)], capture_output=True, text=True)
        stamps: List[str] = []
        if res.returncode == 0 and res.stdout:
            info = json.loads(res.stdout)
            stamps.append((info.get("format", {}).get("tags") or {}).get("creation_time") or "")
            for s in info.get("streams") or []:
                stamps.append((s.get("tags") or {}).get("creation_time") or "")
        for raw in [s for s in stamps if s]:
            try:
                return _parse_utc(raw).astimezone(tz), "creation_time"
            except ValueError:
                continue
        if drive_modtime:
            return _parse_utc(drive_modtime).astimezone(tz), "drive_modtime"
        return None, None

    # -- one pass -----------------------------------------------------------------

    def run_once(self, dry_run: bool = False) -> int:
        self.cfg.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cfg.lock_path, "w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.say("another inbox pass is running; nothing to do")
                return 0
            state = self.load_state()
            entries = self.list_inbox()
            if not entries:
                self.say("inbox empty")
            for entry in entries:
                rec = state["files"].setdefault(entry["ID"], {"name": entry["Name"]})
                if rec.get("status") in (ST_FAILED, ST_ARCHIVED):
                    continue
                if dry_run:
                    self.say(f"would process {entry['Name']} (status {rec.get('status', 'new')})")
                    continue
                try:
                    self._process(entry, rec)
                except Exception as exc:  # one bad file never blocks the others
                    rec["status"] = ST_FAILED
                    rec["error"] = str(exc)[:500]
                    self.notify(f"FAILED {rec.get('match_key') or entry['Name']}: {exc}")
                rec["updated_at"] = _now()
                self.save_state(state)
        return 0

    def _process(self, entry: Dict[str, Any], rec: Dict[str, Any]) -> None:
        cfg = self.cfg
        ext = Path(entry["Name"]).suffix.lower()
        url = f"https://drive.google.com/file/d/{entry['ID']}/view"

        # 1. download + name
        if not rec.get("match_key"):
            tmp_dir = cfg.resources / ".inbox"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp = tmp_dir / f"{entry['ID']}{ext}"
            self.say(f"downloading {entry['Name']}")
            self._check(self.run(["rclone", "copyto", self._remote(cfg.inbox, entry["Path"]),
                                  str(tmp)], capture_output=True, text=True), "download")
            started, source = self.recording_start(tmp, entry.get("ModTime"))
            key = match_key_for(Path(entry["Name"]).stem, started)
            parse_match_key(key)
            target = cfg.resources / f"{key}{ext}"
            if target.exists():
                raise MatchKeyError(f"{target} already exists (another video has this name)")
            tmp.replace(target)
            run_dir = cfg.output / key
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "source.json").write_text(json.dumps({
                "video_url": url, "drive_id": entry["ID"], "original_name": entry["Name"],
                "started_at": started.isoformat() if started else None,
                "time_source": source}, indent=1))
            rec.update(match_key=key, video=str(target), video_url=url, time_source=source)
            self.say(f"{entry['Name']} -> {target.name} (time from {source})")

        key = rec["match_key"]
        video = Path(rec["video"])
        run_dir = cfg.output / key

        # 2. calibration (manual, once per video)
        if not (cfg.calibrations / f"{key}.json").exists():
            if rec.get("status") != ST_NEEDS_CALIBRATION:
                rec["status"] = ST_NEEDS_CALIBRATION
                self.notify(f"{key} needs its court calibration: "
                            f"make calibrate VIDEO={video.relative_to(cfg.root)}")
            return

        # 3. the run
        if not (run_dir / "match_reconstruction.json").exists():
            if not self.on_ac_power():
                self.say(f"{key}: on battery, the run waits for AC power")
                rec["status"] = "waiting_for_power"
                return
            rec["status"] = "running"
            self.say(f"{key}: make run-match (≈0.8× the video length)")
            cmd = [cfg.make, "run-match", f"VIDEO={video.relative_to(cfg.root)}",
                   f"PYTHON={cfg.python}"]
            if shutil.which("caffeinate"):
                cmd = ["caffeinate", "-is", *cmd]
            with open(run_dir / "inbox_run.log", "a") as logf:
                res = self.run(cmd, cwd=cfg.root, stdout=logf, stderr=subprocess.STDOUT)
            self._check(res, f"make run-match (log: {run_dir / 'inbox_run.log'})")

        # 4. publish as a draft
        if rec.get("status") not in ("published",):
            res = self.run([cfg.python, "-m", "src.publish", str(run_dir.relative_to(cfg.root))],
                           cwd=cfg.root, capture_output=True, text=True)
            self._check(res, "publish")
            rec["status"] = "published"
            summary = next((ln for ln in res.stdout.splitlines() if ln.startswith("score")), "")
            rec["summary"] = summary

        # 5. archive on Drive under the match key
        self._check(self.run(["rclone", "moveto", self._remote(cfg.inbox, entry["Path"]),
                              self._remote(cfg.archive, f"{key}{ext}")],
                             capture_output=True, text=True), "archive")
        rec["status"] = ST_ARCHIVED
        self.notify(f"Draft ready to review: {key}  {rec.get('summary', '')}".strip())

    @staticmethod
    def _check(res: subprocess.CompletedProcess, what: str) -> None:
        if res.returncode != 0:
            err = (getattr(res, "stderr", "") or "").strip()[-300:]
            raise RuntimeError(f"{what} failed (exit {res.returncode}) {err}")


def _parse_utc(raw: str) -> datetime:
    """ISO-8601 from ffprobe / rclone; rclone writes nanoseconds, which
    datetime cannot hold -- fractions are cut to microseconds."""
    raw = re.sub(r"(\.\d{6})\d+", r"\1", raw.strip()).replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.publish.inbox", description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--retry", metavar="MATCH_KEY_OR_DRIVE_ID",
                   help="forget the failed state of one entry so the next pass retries it")
    p.add_argument("--env", type=Path, default=DEFAULT_ENV_FILE)
    args = p.parse_args(argv)
    inbox = Inbox(InboxConfig.from_env(load_env_file(args.env)))
    if args.retry:
        state = inbox.load_state()
        for drive_id, rec in state["files"].items():
            if args.retry in (drive_id, rec.get("match_key")):
                rec.pop("status", None)
                rec.pop("error", None)
                inbox.save_state(state)
                print(f"cleared {args.retry}; the next pass retries it")
                return 0
        print(f"no inbox entry {args.retry!r}")
        return 1
    if shutil.which("rclone") is None:
        print("rclone is not installed (brew install rclone; see docs/deploy_web_platform.md)")
        return 1
    return inbox.run_once(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
