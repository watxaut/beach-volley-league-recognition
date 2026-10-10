"""Publish one finished run to the web (docs/web_platform_design.md §3).

    python -m src.publish output/<key>/                       # publish (lands as a draft)
    python -m src.publish output/<key>/ --dry-run             # build + diff vs what is live
    python -m src.publish output/<old_name>/ --match-key 20260920_1830_bogatell_ari_joan
    python -m src.publish --from-bundle output/<key>/match_bundle.json   # re-apply / roll back

Steps: make the 4 slot thumbnails and the attack clips (sequential decode;
the clips come from the run's rally copy once the video is gone), build the
bundle (pure), upload thumbnails + clips + the content-addressed bundle to
Storage, then ONE call to ``ingest_match_bundle`` -- the database applies it
in a single transaction (or records it as ``unchanged``). Re-running is
always safe. Clips of this match that no action points at any more are
removed from Storage after a successful publish.
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
from typing import Any, Dict, List, Optional

from .bundle import (ATTACKS, SLOTS, BundleError, attack_frames, build_bundle, checked_match_key,
                     content_sha256, default_match_key, validate_bundle)
from .client import DEFAULT_ENV_FILE, SupabaseClient, SupabaseError
from .fantasy import score_actions

REPO = Path(__file__).resolve().parents[2]
#: The identity of the run's video, kept in the run directory so that a match
#: can be re-published after the video itself was deleted from the laptop.
IDENTITY_NAME = "video_identity.json"
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


def video_identity(run_dir: Path, key: str, decoded: Optional[str], source_video: Optional[Path],
                   env_file: Path, hash_video: bool = True) -> Dict[str, Optional[str]]:
    """``{filename, sha256}`` of the ORIGINAL video of a run.

    The video is only needed once. While it is on disk it is hashed and the
    result is written to ``<run_dir>/video_identity.json``; after it was
    deleted (disk space) that record is the identity. A run published before
    the record existed falls back on the hash the database already holds for
    this match key -- with no file there is nothing to compare, so the stored
    identity is kept instead of being replaced by "unknown".
    """
    record = run_dir / IDENTITY_NAME
    if source_video is not None:
        ident: Dict[str, Optional[str]] = {"filename": source_video.name, "sha256": None}
        if hash_video:
            print(f"hashing {source_video.name} ...", flush=True)
            ident["sha256"] = sha256_file(source_video)
            record.write_text(json.dumps(ident, indent=1))
        return ident
    try:
        saved = json.loads(record.read_text())
        if saved.get("sha256"):
            print(f"video not on disk: identity from {record.name}", flush=True)
            return {"filename": saved.get("filename"), "sha256": saved["sha256"]}
    except (OSError, ValueError, AttributeError):
        pass
    filename = None
    if decoded:
        from src.utils.video_upscale import resolve_source_stem

        filename = resolve_source_stem(Path(decoded)) + Path(decoded).suffix
    sha = None
    try:
        live = SupabaseClient.from_env(env_file).rpc("publish_preview", {"p_match_key": key}) or {}
        sha = live.get("video_sha256")
    except SupabaseError:
        pass
    if sha:
        print("video not on disk: keeping the hash already published for this match", flush=True)
        record.write_text(json.dumps({"filename": filename, "sha256": sha}, indent=1))
    else:
        print("video not on disk and no hash on record: published without a video hash", flush=True)
    return {"filename": filename, "sha256": sha}


def _calibration(recon: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The calibration the reconstruction read (the clip crop is sized by its net)."""
    path = (recon.get("inputs") or {}).get("calibration")
    try:
        return json.loads(Path(path).read_text()) if path else None
    except (OSError, ValueError):
        return None


def clip_paths_of(bundle: Dict[str, Any]) -> List[str]:
    """Storage paths of the attack clips a bundle names."""
    return sorted({a["extra"]["clip"] for a in bundle["actions"]
                   if (a.get("extra") or {}).get("clip")})


def upload_clips(client: SupabaseClient, bundle: Dict[str, Any],
                 run_dir: Path) -> Optional[List[str]]:
    """Upload the clips Storage does not hold yet (a path names its content,
    so a file there is never sent twice). Returns the clips of this match
    Storage held before the call; None when that could not be listed."""
    wanted = clip_paths_of(bundle)
    try:
        present: Optional[List[str]] = client.list_objects(
            MEDIA_BUCKET, f"clips/{bundle['match']['match_key']}")
    except SupabaseError as exc:
        print(f"warning: the clips in storage could not be listed ({exc}); "
              f"sending all, removing none", flush=True)
        present = None
    from .clips import local_clip

    held = set(present or [])
    sent = lost = 0
    for path in wanted:
        if path in held:
            continue
        local = local_clip(run_dir, path)
        if local is None:
            lost += 1
            continue
        client.upload(MEDIA_BUCKET, path, local.read_bytes(), "video/mp4")
        sent += 1
    if wanted:
        print(f"clips     {sent} uploaded, {len(wanted) - sent - lost} already in storage"
              + (f", {lost} not in this run directory" if lost else ""), flush=True)
    return present


def prune_clips(client: SupabaseClient, bundle: Dict[str, Any],
                present: Optional[List[str]]) -> int:
    """Remove the clips of this match that the bundle now live does not name
    (an attack whose contact frame moved, or that is no attack any more).
    Storage is small: an unreachable clip is only cost."""
    stale = sorted(set(present or []) - set(clip_paths_of(bundle)))
    if not stale:
        return 0
    try:
        client.remove_objects(MEDIA_BUCKET, stale)
    except SupabaseError as exc:
        print(f"warning: {len(stale)} old clips could not be removed from storage ({exc})",
              flush=True)
        return 0
    print(f"clips     {len(stale)} old ones removed from storage", flush=True)
    return len(stale)


def build_from_run(args: argparse.Namespace) -> Dict[str, Any]:
    run_dir = Path(args.run_dir)
    pipeline_path = run_dir / "pipeline_output.json"
    pipeline = json.loads(pipeline_path.read_text()) if pipeline_path.exists() else {}
    recon_path = run_dir / "match_reconstruction.json"
    if not recon_path.exists():
        raise BundleError(f"{recon_path} not found (run `make run-match` / `make postrun`)")
    recon = json.loads(recon_path.read_text())
    key = args.match_key or default_match_key(run_dir, pipeline)
    checked_match_key(key)  # refuse a non-conforming name before hashing / decoding
    decoded = (pipeline.get("video") or {}).get("path")

    from .thumbs import find_source_video, make_slot_thumbnails

    source_video = find_source_video(decoded)
    ident = video_identity(run_dir, key, decoded, source_video, args.env,
                           hash_video=not args.no_video_hash)

    thumb_paths: Dict[str, str] = {}
    diag = run_dir / "diag.jsonl"
    if not args.no_thumbs:
        if decoded and Path(decoded).exists() and diag.exists():
            print("slot thumbnails (sequential decode of the first touches) ...", flush=True)
            made = make_slot_thumbnails(Path(decoded), diag, recon, run_dir / "thumbs")
            thumb_paths = {slot: f"thumbs/{key}/{slot}.jpg" for slot in made}
        else:
            # the video is gone: the thumbnails cut on an earlier publish still are the players
            kept = [s for s in SLOTS if (run_dir / "thumbs" / f"{s}.jpg").exists()]
            thumb_paths = {slot: f"thumbs/{key}/{slot}.jpg" for slot in kept}
            print(f"video not on disk: {'keeping the ' + str(len(kept)) + ' thumbnails of an earlier publish' if kept else 'no thumbnails'}",
                  flush=True)

    clip_paths: Dict[int, str] = {}
    if not args.no_clips:
        from .clips import make_attack_clips, storage_path

        fps = float(recon.get("fps") or (pipeline.get("video") or {}).get("fps") or 0.0)
        made = make_attack_clips(
            run_dir, attack_frames(recon.get("points") or []),
            points=recon.get("points") or [], fps=fps,
            video=Path(decoded) if decoded and Path(decoded).exists() else None,
            calibration=_calibration(recon),
            n_frames=recon.get("n_frames")) if fps else {}
        clip_paths = {frame: storage_path(key, frame, path) for frame, path in made.items()}

    if not diag.exists():
        print("warning: no diag.jsonl in this run directory. Keep the diag dump of every "
              "published match: without it the match cannot be recomputed when the post-run "
              "rules change (make republish-all).", flush=True)

    provenance = {**git_state(), "diag_schema": _diag_schema(diag) if diag.exists() else None,
                  "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "host": socket.gethostname()}
    return build_bundle(run_dir, match_key=key, video_url=args.video_url,
                        video_sha256=ident["sha256"], video_filename=ident["filename"],
                        thumb_paths=thumb_paths, clip_paths=clip_paths,
                        provenance=provenance, note=args.note,
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
        f"clips     {len(clip_paths_of(bundle))} of "
        f"{sum(1 for a in actions if a['slot'] and a['action'] in ATTACKS)} credited attacks",
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
    p.add_argument("--no-clips", action="store_true",
                   help="publish without attack clips (the ones in storage are removed)")
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
        clips_before = upload_clips(client, bundle, run_dir)
        bundle_path = f"{key}/{bundle['content_sha256']}.json"
        client.upload(BUNDLE_BUCKET, bundle_path, json.dumps(bundle).encode(),
                      "application/json")
        who = f"{getpass.getuser()}@{socket.gethostname()}"
        result = client.rpc("ingest_match_bundle", {
            "p_bundle": bundle, "p_bundle_path": f"{BUNDLE_BUCKET}/{bundle_path}",
            "p_published_by": who})
        prune_clips(client, bundle, clips_before)
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
