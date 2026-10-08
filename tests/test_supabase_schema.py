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


def _recount(bundle):
    """The N1-N4 stats, counted in plain Python straight from a bundle: the
    reference the SQL (`player_profile`) has to equal."""
    from collections import defaultdict

    by_point = defaultdict(list)
    for a in bundle["actions"]:
        by_point[a["point_no"]].append(a)
    team_of = {"P1A": "A", "P2A": "A", "P1B": "B", "P2B": "B"}
    out = {s: {"hit": {k: {"n": 0, "kills": 0, "errors": 0} for k in ("reception", "transition")},
               "reception": {"n": 0, "spike": 0, "overpass": 0, "error": 0, "none": 0,
                             "first_ball_kills": 0},
               "own_serve": {"n": 0, "won": 0}, "team_serving": {"n": 0, "won": 0},
               "team_receiving": {"n": 0, "won": 0},
               "serve_in": {"opp_serves": 0, "team_credited": 0, "mine": 0},
               "serve_to": defaultdict(int), "serve_unseen": 0} for s in team_of}
    for pt in bundle["points"]:
        acts = sorted(by_point[pt["point_no"]], key=lambda a: a["seq"])
        possession, poss_of = 0, {}
        for a in acts:
            possession += a["touch_number"] == 1
            poss_of[a["seq"]] = possession
        receiver = next((a for a in acts if a["seq"] == 1 and a["touch_number"] == 1
                         and a["slot"] and a["team"] != pt["serving_team"]), None)
        for slot, team in team_of.items():
            r = out[slot]
            if pt["winner_team"] is None:
                continue
            won = pt["winner_team"] == team
            if pt["server_slot"] == slot:
                r["own_serve"]["n"] += 1
                r["own_serve"]["won"] += won
                if receiver is None:
                    r["serve_unseen"] += 1
                else:
                    r["serve_to"][receiver["slot"]] += 1
            key = "team_serving" if pt["serving_team"] == team else "team_receiving"
            r[key]["n"] += 1
            r[key]["won"] += won
            if pt["serving_team"] != team:
                r["serve_in"]["opp_serves"] += 1
                r["serve_in"]["team_credited"] += bool(receiver and receiver["slot"] in
                                                       [s for s, t in team_of.items() if t == team])
                r["serve_in"]["mine"] += bool(receiver and receiver["slot"] == slot)
        for a in acts:
            if a["slot"] and a["action"] in ("spike", "overpass"):
                h = out[a["slot"]]["hit"]["reception" if poss_of[a["seq"]] == 1 else "transition"]
                h["n"] += 1
                h["kills"] += a["outcome"] == "kill"
                h["errors"] += a["outcome"] == "error"
        if receiver is not None:
            first = [a for a in acts if poss_of[a["seq"]] == 1]
            spike = any(a["action"] == "spike" for a in first)
            over = any(a["action"] == "overpass" for a in first)
            err = any(a["outcome"] == "error" for a in first)
            rc = out[receiver["slot"]]["reception"]
            rc["n"] += 1
            rc["spike"] += spike
            rc["overpass"] += (not spike) and over
            rc["error"] += (not spike) and (not over) and err
            rc["none"] += (not spike) and (not over) and (not err)
            rc["first_ball_kills"] += any(a["outcome"] == "kill" for a in first)
    return out


def _real_match_bundle():
    path = ROOT / "output" / "postrun" / "20260920_match" / "match_bundle.json"
    if not path.exists():
        pytest.skip("the 20260920 match bundle is not on disk")
    import json
    return json.loads(path.read_text())


@pytest.mark.parametrize("which", ["sim", "match"])
def test_sql_analytics_equal_a_python_recount(fresh_db, tmp_path, which):
    """N1-N4 in SQL (`player_profile`) == a plain-Python recount of the same
    bundle: the simulated match, and the real 20260920 match when on disk."""
    import json
    import sys

    sys.path.insert(0, str(ROOT / "tests"))
    from test_publish import _run_dir, _sim_match  # noqa: E402

    from src.publish.bundle import build_bundle

    bundle = (build_bundle(_run_dir(tmp_path, _sim_match())) if which == "sim"
              else _real_match_bundle())
    has_auth = _psql(fresh_db, "-tAc", "select count(*) from pg_namespace where nspname = 'auth'")
    if has_auth.stdout.strip() == "0":
        _apply(fresh_db, SUPABASE / "checks" / "plain_postgres_stub.sql")
    for migration in sorted((SUPABASE / "migrations").glob("*.sql")):
        _apply(fresh_db, migration)

    admin = "00000000-0000-0000-0000-00000000000a"
    script = f"""
insert into auth.users (id, email) values ('{admin}', 'admin@check.test');
update public.profiles set role = 'admin' where user_id = '{admin}';
insert into public.players (display_name) values ('Ari'), ('Joan'), ('Marc'), ('Pau');
select public.ingest_match_bundle($j${json.dumps(bundle)}$j$::jsonb, 'x', 'pytest') ->> 'result';
update public.match_participants set player_id = case slot
  when 'P1A' then 1 when 'P2A' then 2 when 'P1B' then 3 else 4 end;
update public.matches set status = 'published';
begin;
set local role authenticated;
select set_config('request.jwt.claim.sub', '{admin}', true);
select 'P1A|' || (public.player_profile(1) -> 'analytics')::text
union all select 'P2A|' || (public.player_profile(2) -> 'analytics')::text
union all select 'P1B|' || (public.player_profile(3) -> 'analytics')::text
union all select 'P2B|' || (public.player_profile(4) -> 'analytics')::text;
select 'LB|' || display_name || '|' || serve_errors || '|' || recv_points || '|' || recv_won
       || '|' || serve_points || '|' || serve_won from public.leaderboard();
rollback;
"""
    res = subprocess.run(["psql", fresh_db, "-v", "ON_ERROR_STOP=1", "-X", "-q", "-tA"],
                         input=script, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    sql, board = {}, {}
    for line in res.stdout.splitlines():
        if line[:4] in ("P1A|", "P2A|", "P1B|", "P2B|"):
            sql[line[:3]] = json.loads(line[4:])
        elif line.startswith("LB|"):
            name, *nums = line[3:].split("|")
            board[name] = [int(n) for n in nums]
    assert set(sql) == {"P1A", "P2A", "P1B", "P2B"}, res.stdout[-500:]

    names = {"P1A": "Ari", "P2A": "Joan", "P1B": "Marc", "P2B": "Pau"}
    for slot, ref in _recount(bundle).items():
        got = sql[slot]
        assert got["hit"] == ref["hit"], slot
        assert got["reception"] == ref["reception"], slot
        assert got["rally"] == {k: ref[k] for k in ("own_serve", "team_serving", "team_receiving")}, slot
        assert got["serve_in"] == ref["serve_in"], slot
        assert {t["display_name"]: t["n"] for t in got["serve_out"]["to"]} == \
            {names[s]: n for s, n in ref["serve_to"].items()}, slot
        assert got["serve_out"]["unseen"] == ref["serve_unseen"], slot
        # player_page_v2: the leaderboard's league-tier comparison columns ...
        serve_errors = sum(a["slot"] == slot and a["action"] == "serve" and a["outcome"] == "error"
                           for a in bundle["actions"])
        assert board[names[slot]] == [serve_errors, ref["team_receiving"]["n"], ref["team_receiving"]["won"],
                                      ref["team_serving"]["n"], ref["team_serving"]["won"]], slot
        # ... and the attack map: every credited attack that has a position
        # says where the ball was hit, as the publisher stored it
        attacks = [a for a in bundle["actions"] if a["slot"] == slot and a["action"] in ("spike", "overpass")
                   and (a.get("landing_y_m") is not None or a.get("landing_result") is not None
                        or a.get("own_y_m") is not None)]
        assert len(got["landings"]) == len(attacks), slot

        def spot(x, y):
            return (None if x is None else round(x, 2), None if y is None else round(y, 2))

        assert sorted((spot(l["sx"], l["sy"]) for l in got["landings"]), key=str) == \
            sorted((spot(a.get("own_x_m"), a.get("own_y_m")) for a in attacks), key=str), slot
        assert {l["a"] for l in got["landings"]} <= {"spike", "overpass"}, slot
