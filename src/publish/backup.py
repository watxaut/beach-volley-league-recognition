"""Export the ADMIN-OWNED tables (the only data the laptop cannot rebuild).

    python -m src.publish.backup            # -> backups/admin_backup_<UTC>.json + Drive copy
    python -m src.publish.backup --no-drive # local file only

Pipeline-owned rows (points, touches, scores) are reproducible from the
bundles in Storage and the local output/ folders; players, accounts, slot
assignments, match titles/status and the fantasy rules are not -- the free
Supabase plan keeps no downloadable backups, so this runs weekly (launchd)
and copies the file off the laptop to ``gdrive:VolleyBackups`` when rclone
is configured.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .client import DEFAULT_ENV_FILE, SupabaseClient, SupabaseError, load_env_file

ADMIN_TABLES = {
    "profiles": "user_id,email,role,display_name,created_at",
    "players": "*",
    "matches": "id,match_key,title,venue,season,status,detail_public",
    "match_participants": "match_id,slot,player_id,is_unknown,assigned_by,assigned_at",
    "fantasy_rulesets": "*",
    "fantasy_rules": "*",
}


def export(client: SupabaseClient) -> Dict[str, List[Dict]]:
    return {table: client.select_all(table, cols) for table, cols in ADMIN_TABLES.items()}


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.publish.backup", description=__doc__)
    p.add_argument("--out", type=Path, default=Path("backups"))
    p.add_argument("--env", type=Path, default=DEFAULT_ENV_FILE)
    p.add_argument("--no-drive", action="store_true", help="do not copy the file to Drive")
    args = p.parse_args(argv)
    try:
        data = export(SupabaseClient.from_env(args.env))
    except SupabaseError as exc:
        print(f"error: {exc}")
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = args.out / f"admin_backup_{stamp}.json"
    path.write_text(json.dumps({"exported_at": stamp, "tables": data}, indent=1, default=str))
    print(f"{path}: " + ", ".join(f"{t} {len(rows)}" for t, rows in data.items()))
    if not args.no_drive and shutil.which("rclone"):
        env = load_env_file(args.env)
        dest = (f"{env.get('VOLLEY_RCLONE_REMOTE', 'gdrive')}:"
                f"{env.get('VOLLEY_DRIVE_BACKUPS', 'VolleyBackups')}")
        res = subprocess.run(["rclone", "copy", str(path), dest], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"error: copy to {dest} failed: {res.stderr.strip()}")
            return 1
        print(f"copied to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
