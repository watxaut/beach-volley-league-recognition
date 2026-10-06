"""Re-publish every published match with the CURRENT post-run rules (I2).

    python -m src.publish.republish --dry-run        # what would be redone
    python -m src.publish.republish                  # postrun + publish each match
    python -m src.publish.republish --only 20260920_1800_local_ari_joan

A stat is only comparable across matches when every match went through the
same rules. When ``src/postrun`` changes, an old match must be recomputed or
a trend shows a pipeline change instead of a player change. For each match
that was ever published from this machine (a run directory holding the
``match_bundle.json`` the publisher writes -- its ``match.match_key`` is the
identity, so legacy run names published with ``--match-key`` are found too):

1. ``python -m src.postrun <run_dir>`` re-runs the reconstruction over the
   kept ``diag.jsonl`` (about 3 s, no decode);
2. ``python -m src.publish <run_dir> --match-key <key>`` publishes it.
   Identical content is logged ``unchanged`` and writes nothing.

A match whose diag dump (or calibration) was deleted cannot be recomputed:
it is listed as skipped, never silently left behind. KEEP THE DIAG DUMP of
every published match (about 50 MB each). Exit code 1 when any match failed
or was skipped. Run from the prod worktree (AGENTS.md §8).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

Runner = Callable[..., subprocess.CompletedProcess]

BUNDLE_NAME = "match_bundle.json"
#: How deep under the root a run directory may sit (``output/<key>`` or
#: ``output/postrun/<name>``).
MAX_DEPTH = 2


@dataclass
class Candidate:
    key: str
    run_dir: Path
    #: Why it cannot be recomputed; None = ready.
    skip: Optional[str] = None


@dataclass
class Outcome:
    key: str
    run_dir: Path
    status: str          # applied | unchanged | skipped | failed | planned
    detail: str = ""


def _calibration_of(run_dir: Path) -> Optional[Path]:
    try:
        pipeline = json.loads((run_dir / "pipeline_output.json").read_text())
    except (OSError, ValueError):
        return None
    path = ((pipeline.get("video") or {}).get("calibration_readiness") or {}).get("calibration_path")
    return Path(path) if path else None


def discover(root: Path, cwd: Optional[Path] = None) -> List[Candidate]:
    """Every run directory under ``root`` that was published, newest bundle
    first per match key (a key re-run in two directories keeps the newer)."""
    cwd = cwd or Path.cwd()
    found: Dict[str, Path] = {}
    bundles = sorted(
        (p for depth in range(1, MAX_DEPTH + 1)
         for p in root.glob("/".join(["*"] * depth + [BUNDLE_NAME]))),
        key=lambda p: p.stat().st_mtime)
    for bundle in bundles:
        try:
            key = json.loads(bundle.read_text())["match"]["match_key"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        found[key] = bundle.parent               # sorted by mtime: the newest wins
    out = []
    for key, run_dir in sorted(found.items()):
        skip = None
        if not (run_dir / "diag.jsonl").exists():
            skip = "no diag.jsonl kept: the reconstruction cannot be recomputed"
        elif not (run_dir / "pipeline_output.json").exists():
            skip = "no pipeline_output.json"
        else:
            cal = _calibration_of(run_dir)
            if cal is None or not (cal if cal.is_absolute() else cwd / cal).exists():
                skip = f"calibration not found ({cal})"
        out.append(Candidate(key=key, run_dir=run_dir, skip=skip))
    return out


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def republish(candidates: Sequence[Candidate], *, dry_run: bool = False,
              allow_dirty: bool = False, run: Runner = subprocess.run,
              python: str = sys.executable,
              say: Callable[[str], None] = print) -> List[Outcome]:
    """Postrun + publish each candidate; one failure never stops the others."""
    outcomes: List[Outcome] = []
    for c in candidates:
        if c.skip:
            outcomes.append(Outcome(c.key, c.run_dir, "skipped", c.skip))
            say(f"[republish] {c.key}: SKIPPED ({c.skip})")
            continue
        if dry_run:
            outcomes.append(Outcome(c.key, c.run_dir, "planned"))
            say(f"[republish] {c.key}: would re-run postrun + publish ({c.run_dir})")
            continue
        say(f"[republish] {c.key}: postrun ...")
        res = run([python, "-m", "src.postrun", str(c.run_dir)], capture_output=True, text=True)
        if res.returncode != 0:
            detail = _last_line(res.stderr) or _last_line(res.stdout) or f"exit {res.returncode}"
            outcomes.append(Outcome(c.key, c.run_dir, "failed", f"postrun: {detail}"))
            say(f"[republish] {c.key}: FAILED postrun ({detail})")
            continue
        cmd = [python, "-m", "src.publish", str(c.run_dir), "--match-key", c.key,
               "--note", "republished with the current post-run rules"]
        if allow_dirty:
            cmd.append("--allow-dirty")
        res = run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            detail = _last_line(res.stderr) or _last_line(res.stdout) or f"exit {res.returncode}"
            outcomes.append(Outcome(c.key, c.run_dir, "failed", f"publish: {detail}"))
            say(f"[republish] {c.key}: FAILED publish ({detail})")
            continue
        tail = _last_line(res.stdout)             # "published: applied (revision 3, ...)"
        status = "unchanged" if "unchanged" in tail else "applied"
        outcomes.append(Outcome(c.key, c.run_dir, status, tail))
        say(f"[republish] {c.key}: {tail}")
    return outcomes


def summary(outcomes: Sequence[Outcome]) -> str:
    counts: Dict[str, int] = {}
    for o in outcomes:
        counts[o.status] = counts.get(o.status, 0) + 1
    return ", ".join(f"{n} {s}" for s, n in sorted(counts.items())) or "nothing to do"


def main(argv: Optional[List[str]] = None, run: Runner = subprocess.run) -> int:
    p = argparse.ArgumentParser(prog="python -m src.publish.republish",
                                description="Re-run post-run and re-publish every published match.")
    p.add_argument("--root", type=Path, default=Path("output"),
                   help="where run directories live (default: output)")
    p.add_argument("--only", nargs="+", metavar="KEY", help="just these match keys")
    p.add_argument("--dry-run", action="store_true", help="list what would be redone, write nothing")
    p.add_argument("--allow-dirty", action="store_true",
                   help="publish from a working tree with uncommitted changes")
    args = p.parse_args(argv)

    candidates = discover(args.root)
    if args.only:
        unknown = sorted(set(args.only) - {c.key for c in candidates})
        if unknown:
            print(f"error: no published run found for {', '.join(unknown)}", file=sys.stderr)
            return 2
        candidates = [c for c in candidates if c.key in args.only]
    if not candidates:
        print(f"[republish] no published runs under {args.root}/ (a run is published once "
              f"{BUNDLE_NAME} exists in its directory)")
        return 0
    outcomes = republish(candidates, dry_run=args.dry_run, allow_dirty=args.allow_dirty, run=run)
    print(f"[republish] {summary(outcomes)}")
    return 1 if any(o.status in ("failed", "skipped") for o in outcomes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
