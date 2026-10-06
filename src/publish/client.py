"""Minimal Supabase REST client for the laptop (stdlib only).

Credentials come from the environment or ``.env.publish`` (git-ignored):

    SUPABASE_URL=https://<project-ref>.supabase.co
    SUPABASE_SECRET_KEY=sb_secret_...      # or a legacy service_role JWT

The secret key bypasses RLS: it lives ONLY on the processing laptop, never
in ``webapp/`` and never in git.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_ENV_FILE = Path(".env.publish")
TIMEOUT_S = 60


class SupabaseError(RuntimeError):
    pass


def load_env_file(path: Path = DEFAULT_ENV_FILE) -> Dict[str, str]:
    """KEY=VALUE lines (``#`` comments, optional quotes). Real environment
    variables win over the file."""
    values: Dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip('"').strip("'")
    values.update({k: v for k, v in os.environ.items() if k in values or k.startswith(
        ("SUPABASE_", "VOLLEY_"))})
    return values


class SupabaseClient:
    def __init__(self, url: str, key: str) -> None:
        if not url or not key:
            raise SupabaseError("SUPABASE_URL and SUPABASE_SECRET_KEY are required "
                                "(environment or .env.publish)")
        self.url = url.rstrip("/")
        self.key = key

    @classmethod
    def from_env(cls, env_file: Path = DEFAULT_ENV_FILE) -> "SupabaseClient":
        env = load_env_file(env_file)
        return cls(env.get("SUPABASE_URL", ""),
                   env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY", ""))

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {"apikey": self.key}
        # Legacy service_role keys are JWTs and go in Authorization too; the new
        # sb_secret_ keys are not JWTs -- the gateway resolves them from apikey.
        if self.key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {self.key}"
        headers.update(extra or {})
        return headers

    def _request(self, method: str, path: str, body: Optional[bytes] = None,
                 headers: Optional[Dict[str, str]] = None) -> Any:
        req = urllib.request.Request(self.url + path, data=body, method=method,
                                     headers=self._headers(headers))
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise SupabaseError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SupabaseError(f"{method} {path} -> {exc.reason}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw.decode(errors="replace")

    # -- API ------------------------------------------------------------------

    def rpc(self, name: str, params: Dict[str, Any]) -> Any:
        return self._request("POST", f"/rest/v1/rpc/{name}",
                             json.dumps(params).encode(),
                             {"Content-Type": "application/json"})

    def upload(self, bucket: str, path: str, data: bytes, content_type: str,
               upsert: bool = True) -> Any:
        quoted = urllib.parse.quote(path)
        return self._request("POST", f"/storage/v1/object/{bucket}/{quoted}", data,
                             {"Content-Type": content_type,
                              "x-upsert": "true" if upsert else "false"})

    def download(self, bucket: str, path: str) -> Any:
        quoted = urllib.parse.quote(path)
        return self._request("GET", f"/storage/v1/object/{bucket}/{quoted}")

    def select_all(self, table: str, columns: str = "*", page: int = 1000) -> List[Dict]:
        rows: List[Dict] = []
        offset = 0
        while True:
            q = urllib.parse.urlencode({"select": columns, "limit": page, "offset": offset})
            batch = self._request("GET", f"/rest/v1/{table}?{q}") or []
            rows.extend(batch)
            if len(batch) < page:
                return rows
            offset += page
