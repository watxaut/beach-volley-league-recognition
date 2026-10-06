"""The Supabase migrations, exercised on a real PostgreSQL.

Runs only when ``VOLLEY_TEST_PG_DSN`` points at a PostgreSQL server where the
DSN's user may create databases (a throwaway local cluster, or the local
Supabase stack: ``postgresql://postgres:postgres@127.0.0.1:54322/postgres``),
and ``psql`` is on PATH. Each run creates a fresh database, applies
``supabase/checks/plain_postgres_stub.sql`` when the server is NOT Supabase
(no ``auth`` schema yet), then every migration in order, then
``supabase/checks/rls_smoke.sql`` (publish idempotency, ownership, video
guard, fantasy rules, every access tier), and drops the database.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUPABASE = ROOT / "supabase"
DSN = os.environ.get("VOLLEY_TEST_PG_DSN")

pytestmark = pytest.mark.skipif(
    not DSN or shutil.which("psql") is None,
    reason="set VOLLEY_TEST_PG_DSN (and have psql) to run the schema checks",
)


def _with_db(dsn: str, dbname: str) -> str:
    parts = urlsplit(dsn)
    return urlunsplit((parts.scheme, parts.netloc, "/" + dbname, parts.query, parts.fragment))


def _psql(dsn: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-X", "-q", *args],
                          capture_output=True, text=True)


@pytest.fixture()
def fresh_db():
    name = f"volley_schema_{uuid.uuid4().hex[:8]}"
    res = _psql(DSN, "-c", f"create database {name}")
    assert res.returncode == 0, res.stderr
    try:
        yield _with_db(DSN, name)
    finally:
        _psql(DSN, "-c", f"drop database if exists {name} with (force)")


def _apply(dsn: str, path: Path) -> None:
    res = _psql(dsn, "-f", str(path))
    assert res.returncode == 0, f"{path.name} failed:\n{res.stderr}"


def test_migrations_apply_and_rls_smoke_passes(fresh_db):
    has_auth = _psql(fresh_db, "-tAc", "select count(*) from pg_namespace where nspname = 'auth'")
    if has_auth.stdout.strip() == "0":
        _apply(fresh_db, SUPABASE / "checks" / "plain_postgres_stub.sql")
    for migration in sorted((SUPABASE / "migrations").glob("*.sql")):
        _apply(fresh_db, migration)
    res = _psql(fresh_db, "-tA", "-f", str(SUPABASE / "checks" / "rls_smoke.sql"))
    assert res.returncode == 0, res.stderr
    assert "RLS SMOKE: ALL CHECKS PASSED" in res.stdout


def test_reapplying_a_migration_fails_loudly(fresh_db):
    """A migration applied twice must FAIL (no silent `if not exists` drift):
    `supabase db push` tracks what ran; re-running by hand is an operator error."""
    has_auth = _psql(fresh_db, "-tAc", "select count(*) from pg_namespace where nspname = 'auth'")
    if has_auth.stdout.strip() == "0":
        _apply(fresh_db, SUPABASE / "checks" / "plain_postgres_stub.sql")
    first = sorted((SUPABASE / "migrations").glob("*.sql"))[0]
    _apply(fresh_db, first)
    again = _psql(fresh_db, "-f", str(first))
    assert again.returncode != 0


def test_sql_fantasy_equals_the_publisher_preview(fresh_db, tmp_path):
    """A bundle built from a real post-run reconstruction, ingested through the
    RPC: SQL's player_match_fantasy (active G1 rules) == fantasy.score_actions
    == postrun.player_stats (pinned in test_publish.py)."""
    import json
    import sys

    sys.path.insert(0, str(ROOT / "tests"))
    from test_publish import _run_dir, _sim_match  # noqa: E402

    from src.publish.bundle import build_bundle
    from src.publish.fantasy import score_actions

    has_auth = _psql(fresh_db, "-tAc", "select count(*) from pg_namespace where nspname = 'auth'")
    if has_auth.stdout.strip() == "0":
        _apply(fresh_db, SUPABASE / "checks" / "plain_postgres_stub.sql")
    for migration in sorted((SUPABASE / "migrations").glob("*.sql")):
        _apply(fresh_db, migration)

    bundle = build_bundle(_run_dir(tmp_path, _sim_match()))
    # psql interpolates :'bundle' only in statements read from stdin/files, not -c
    res = subprocess.run(
        ["psql", fresh_db, "-v", "ON_ERROR_STOP=1", "-X", "-q", "-tA",
         "-v", f"bundle={json.dumps(bundle)}"],
        input="select public.ingest_match_bundle(:'bundle'::jsonb, 'x', 'pytest') ->> 'result';",
        capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "applied"
    rows = _psql(fresh_db, "-tA", "-F", "|", "-c",
                 "select slot, fantasy from public.player_match_fantasy order by slot")
    sql = {slot: float(points) for slot, points in
           (line.split("|") for line in rows.stdout.split())}
    local = score_actions(bundle["actions"])
    assert sql == {s: local.get(s, {"fantasy": 0.0})["fantasy"] for s in sql}
