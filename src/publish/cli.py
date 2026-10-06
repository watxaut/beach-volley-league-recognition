"""Publish one finished run to the web (docs/web_platform_design.md §3).

    python -m src.publish output/<key>/                       # publish (lands as a draft)
    python -m src.publish output/<key>/ --dry-run             # build + diff vs what is live
    python -m src.publish output/<old_name>/ --match-key 20260920_1830_bogatell_ari_joan
    python -m src.publish --from-bundle output/<key>/match_bundle.json   # re-apply / roll back

Steps: build the bundle (pure), make the 4 slot thumbnails (sequential
decode), upload thumbnails + the content-addressed bundle to Storage, then
ONE call to ``ingest_match_bundle`` -- the database applies it in a single
transaction (or records it as ``unchanged``). Re-running is always safe.
Every call is appended to ``data/publish_log.jsonl`` (the database keeps the
authoritative log in ``match_publications``).
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .bundle import (BundleError, build_bundle, content_sha256, default_match_key,
                     validate_bundle)
from .client import DEFAULT_ENV_FILE, SupabaseClient, SupabaseError
from .fantasy import score_actions

REPO = Path(__file__).resolve().parents[2]
DEFAULT_LOG = Path("data/publish_log.jsonl")
BUNDLE_BUCKET = "match-bundles"
MEDIA_BUCKET = "match-media"


def git_state() -> Dict[str, Any]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                                  text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return ""
    return {"publisher_version": run("rev-parse", "--short", "HEAD") or None,
            "git_dirty": bool(run("status", "--porcelain", "--untracked-files=no"))}


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _diag_schema(diag: Path) -> Optional[int]:
    try:
        with open(diag) as f:
            first = json.loads(f.readline())
        return int(first.get("meta", {}).get("schema_version"))
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def build_from_run(args: argparse.Namespace) -> Dict[str, Any]:
    run_dir = Path(args.run_dir)
    pipeline_path = run_dir / "pipeline_output.json"
    pipeline = json.loads(pipeline_path.read_text()) if pipeline_path.exists() else {}
    recon_path = run_dir / "match_reconstruction.json"
    if not recon_path.exists():
        raise BundleError(f"{recon_path} not found (run `make run-match` / `make postrun`)")
    recon = json.loads(recon_path.read_text())
    key = args.match_key or default_match_key(run_dir, pipeline)
    decoded = (pipeline.get("video") or {}).get("path")

    from .thumbs import find_source_video, make_slot_thumbnails

    video_sha = None
    source_video = find_source_video(decoded)
    if source_video and not args.no_video_hash:
        print(f"hashing {source_video.name} ...", flush=True)
        video_sha = sha256_file(source_video)

    thumb_paths: Dict[str, str] = {}
    diag = run_dir / "diag.jsonl"
    if not args.no_thumbs:
        if decoded and Path(decoded).exists() and diag.exists():
            print("slot thumbnails (sequential decode of the first touches) ...", flush=True)
            made = make_slot_thumbnails(Path(decoded), diag, recon, run_dir / "thumbs")
            thumb_paths = {slot: f"thumbs/{key}/{slot}.jpg" for slot in made}
        else:
            print("no thumbnails: the decoded video or diag.jsonl is missing", flush=True)

    if not diag.exists():
        print("warning: no diag.jsonl in this run directory. Keep the diag dump of every "
              "published match: without it the match cannot be recomputed when the post-run "
              "rules change (make republish-all).", flush=True)

    provenance = {**git_state(), "diag_schema": _diag_schema(diag) if diag.exists() else None,
                  "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "host": socket.gethostname()}
    return build_bundle(run_dir, match_key=key, video_url=args.video_url,
                        video_sha256=video_sha,
                        video_filename=source_video.name if source_video else None,
                        thumb_paths=thumb_paths, provenance=provenance, note=args.note,
                        replace_video=args.replace_video)


def summarize(bundle: Dict[str, Any]) -> str:
    m = bundle["match"]
    actions = bundle["actions"]
    credited = sum(1 for a in actions if a["slot"])
    lines = [
        f"match     {m['match_key']}  ({m['match_date']} {m['start_time']})",
        f"score     A {m['score_a']} - B {m['score_b']}   points {m['n_points']}   "
        f"set complete: {m['set_complete']}",
        f"touches   {len(actions)} ({credited} credited to a slot)",
        f"video     {m['video'].get('filename')}  url: {m['video'].get('url') or '-'}  "
        f"sha256: {(m['video'].get('sha256') or '-')[:12]}",
        f"thumbs    {', '.join(s['slot'] for s in bundle['slots'] if s['thumb_path']) or '-'}",
        f"hash      {bundle['content_sha256'][:16]}",
        "fantasy (G1 preview; live scoring uses the database rules):",
    ]
    for slot, row in score_actions(actions).items():
        parts = ", ".join(f"{k} {v}" for k, v in sorted(row["breakdown"].items()))
        lines.append(f"  {slot}  {row['fantasy']:>5}   {parts}")
    flagged = (m.get("checks") or {}).get("flagged_points") or {}
    if flagged:
        lines.append(f"flagged points: {', '.join(str(k) for k in flagged)}")
    return "\n".join(lines)


def diff_against_live(bundle: Dict[str, Any], live: Dict[str, Any]) -> str:
    if not live or not live.get("exists"):
        return "live: no such match yet -> publishing creates it as a DRAFT"
    m = bundle["match"]
    lines = [f"live: status {live.get('status')}, revision {live.get('revision')}, "
             f"score A {live.get('score_a')} - B {live.get('score_b')}, "
             f"points {live.get('n_points')}, touches {live.get('n_actions')}"]
    if live.get("content_sha256") == bundle["content_sha256"]:
        lines.append("content identical -> publishing records 'unchanged' only")
        return "\n".join(lines)
    lines.append(f"new : score A {m['score_a']} - B {m['score_b']}, points {m['n_points']}, "
                 f"touches {len(bundle['actions'])}")
    if live.get("video_sha256") and m["video"].get("sha256") and \
            live["video_sha256"] != m["video"]["sha256"]:
        lines.append("WARNING: a DIFFERENT video is live under this name "
                     "(publishing needs --replace-video)")
    local = score_actions(bundle["actions"])
    for s in live.get("slots") or []:
        new = local.get(s["slot"], {}).get("fantasy", 0.0)
        if float(s.get("fantasy") or 0) != new:
            lines.append(f"  {s['slot']} fantasy {s.get('fantasy')} -> {new}")
    return "\n".join(lines)


def append_log(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m src.publish",
                                description="Publish a finished run to the web (Supabase).")
    p.add_argument("run_dir", nargs="?", help="output/<key>/ holding match_reconstruction.json")
    p.add_argument("--from-bundle", help="re-apply a saved bundle JSON (rollback / retry)")
    p.add_argument("--match-key", help="override the key (YYYYMMDD_HHMM_<venue>_<text>)")
    p.add_argument("--video-url", help="link to the original video (default: source.json)")
    p.add_argument("--note", help="free text stored in the publication log")
    p.add_argument("--dry-run", action="store_true", help="build and diff only, write nothing")
    p.add_argument("--replace-video", action="store_true",
                   help="allow a different video under an existing match key")
    p.add_argument("--allow-dirty", action="store_true",
                   help="publish from a working tree with uncommitted changes")
    p.add_argument("--no-thumbs", action="store_true", help="skip the slot thumbnails")
    p.add_argument("--no-video-hash", action="store_true", help="skip hashing the source video")
    p.add_argument("--env", type=Path, default=DEFAULT_ENV_FILE, help="credentials file")
    p.add_argument("--log", type=Path, default=DEFAULT_LOG, help="local publish log (JSONL)")
    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.run_dir and not args.from_bundle:
        print("error: give a run directory or --from-bundle", file=sys.stderr)
        return 2
    try:
        if args.from_bundle:
            bundle = json.loads(Path(args.from_bundle).read_text())
            if args.note:
                bundle["note"] = args.note
            if args.replace_video:
                bundle["replace_video"] = True
            validate_bundle(bundle)
            if bundle.get("content_sha256") != content_sha256(bundle):
                raise BundleError("bundle content does not match its content_sha256")
            run_dir = Path(args.from_bundle).parent
        else:
            bundle = build_from_run(args)
            run_dir = Path(args.run_dir)
            (run_dir / "match_bundle.json").write_text(json.dumps(bundle, indent=1))
    except (BundleError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(summarize(bundle))
    key = bundle["match"]["match_key"]

    if args.dry_run:
        try:
            client = SupabaseClient.from_env(args.env)
            print(diff_against_live(bundle, client.rpc("publish_preview",
                                                       {"p_match_key": key})))
        except SupabaseError as exc:
            print(f"(no live comparison: {exc})")
        print("dry run: nothing written")
        return 0

    if bundle.get("provenance", {}).get("git_dirty") and not args.allow_dirty:
        print("error: the working tree has uncommitted changes; publish from a clean "
              "checkout (the prod worktree) or pass --allow-dirty", file=sys.stderr)
        return 2

    try:
        client = SupabaseClient.from_env(args.env)
        for slot in bundle["slots"]:
            if slot["thumb_path"]:
                local = run_dir / "thumbs" / f"{slot['slot']}.jpg"
                if local.exists():
                    client.upload(MEDIA_BUCKET, slot["thumb_path"], local.read_bytes(),
                                  "image/jpeg")
        bundle_path = f"{key}/{bundle['content_sha256']}.json"
        client.upload(BUNDLE_BUCKET, bundle_path, json.dumps(bundle).encode(),
                      "application/json")
        who = f"{getpass.getuser()}@{socket.gethostname()}"
        result = client.rpc("ingest_match_bundle", {
            "p_bundle": bundle, "p_bundle_path": f"{BUNDLE_BUCKET}/{bundle_path}",
            "p_published_by": who})
    except SupabaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        append_log(args.log, {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                              "match_key": key, "result": "failed", "error": str(exc)[:500]})
        return 1

    append_log(args.log, {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "match_key": key, "result": result.get("result"), "revision": result.get("revision"),
        "content_sha256": bundle["content_sha256"], "bundle_path": bundle_path,
        "video_url": bundle["match"]["video"].get("url"),
        "pipeline_version": bundle.get("provenance", {}).get("pipeline_version"),
        "publisher_version": bundle.get("provenance", {}).get("publisher_version"),
        "git_dirty": bundle.get("provenance", {}).get("git_dirty"),
        "note": bundle.get("note")})
    print(f"published: {result.get('result')} (revision {result.get('revision')}, "
          f"match id {result.get('match_id')})")
    return 0
