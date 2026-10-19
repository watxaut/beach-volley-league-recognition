-- Behavioural check of the migrations: publish idempotency, ownership rules,
-- the video guard, fantasy rules and every access tier. Everything happens
-- in ONE transaction that is ROLLED BACK, so it leaves no trace.
--
--   local Supabase : psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres" \
--                      -v ON_ERROR_STOP=1 -f supabase/checks/rls_smoke.sql
--   plain Postgres : tests/test_supabase_schema.py (applies a stub first)
--
-- A failed ASSERT aborts with the message; the last line prints
-- 'RLS SMOKE: ALL CHECKS PASSED'.
begin;

-- ── fixtures: three accounts (admin, a player, a stranger) and 4 players ──
insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'admin@check.test'),
  ('00000000-0000-0000-0000-0000000000a1', 'ari@check.test'),
  ('00000000-0000-0000-0000-0000000000b0', 'bob@check.test');
update public.profiles set role = 'admin'
  where user_id = '00000000-0000-0000-0000-00000000000a';
insert into public.players (display_name, user_id) values
  ('Check Ari',  '00000000-0000-0000-0000-0000000000a1'),
  ('Check Joan', null), ('Check Opp1', null), ('Check Opp2', null);

-- A bundle as src/publish builds it (keys = column names).
create function pg_temp.bundle(p_hash text, p_video text, p_second_rally boolean)
returns jsonb language sql as $$
  select jsonb_build_object(
    'bundle_version', 1, 'content_sha256', p_hash, 'note', 'rls smoke',
    'match', jsonb_build_object(
      'match_key', '20260920_1830_check_court', 'match_date', '2026-09-20',
      'start_time', '18:30', 'points_to_win', 21, 'score_a', 2, 'score_b', 0,
      'winner_team', 'A', 'n_points', 2, 'set_complete', false, 'duration_s', 60.0,
      'checks', jsonb_build_object('flagged_points', '[]'::jsonb),
      'video', jsonb_build_object('filename', '20260920_1830_check_court.mp4',
                                  'url', 'https://drive.google.com/file/d/x/view',
                                  'sha256', p_video, 'fps', 25.67,
                                  'width', 1280, 'height', 720)),
    'slots', (select jsonb_agg(jsonb_build_object('slot', s, 'thumb_path', 'thumbs/k/' || s || '.jpg'))
              from unnest(array['P1A', 'P2A', 'P1B', 'P2B']) s),
    'points', jsonb_build_array(
      jsonb_build_object('point_no', 1, 'start_frame', 180, 'end_frame', 420,
                         'serving_team', 'B', 'server_slot', 'P1B', 'winner_team', 'A',
                         'winner_source', 'next_serve', 'end_kind', 'ground',
                         'score_a_after', 1, 'score_b_after', 0),
      jsonb_build_object('point_no', 2, 'start_frame', 800, 'end_frame', 900,
                         'serving_team', 'A', 'server_slot', 'P1A', 'winner_team', 'A',
                         'winner_source', 'next_serve', 'end_kind', 'lost',
                         'score_a_after', 2, 'score_b_after', 0, 'flags', jsonb_build_array('x'))),
    'actions', jsonb_build_array(
      jsonb_build_object('point_no', 1, 'seq', 0, 'frame', 211, 'slot', 'P1B', 'team', 'B',
                         'action', 'serve', 'touch_number', 0, 'observed', true),
      jsonb_build_object('point_no', 1, 'seq', 1, 'frame', 247, 'slot', 'P1A', 'team', 'A',
                         'action', 'dig', 'touch_number', 1, 'observed', true, 'own_x_m', 2.0, 'own_y_m', 3.5),
      jsonb_build_object('point_no', 1, 'seq', 2, 'frame', 304, 'slot', 'P2A', 'team', 'A',
                         'action', 'set', 'touch_number', 2, 'observed', true, 'is_assist', true,
                         'own_x_m', 4.5, 'own_y_m', 6.0,
                         'extra', jsonb_build_object('court_err_m', jsonb_build_array(0.4, 0.7))),
      jsonb_build_object('point_no', 1, 'seq', 3, 'frame', 345, 'slot', 'P1A', 'team', 'A',
                         'action', 'spike', 'touch_number', 3, 'outcome', 'kill', 'observed', true,
                         'attack_zone', 2, 'landing_x_m', 3.1, 'landing_y_m', 12.0,
                         'landing_in', true, 'landing_source', 'ball_death',
                         'landing_err_x_m', 0.3, 'landing_err_y_m', 0.9,
                         'landing_result', 'kill', 'own_x_m', 6.3, 'own_y_m', 5.4,
                         'spike_type', 'hard',
                         'extra', jsonb_build_object(
                           'court_err_m', jsonb_build_array(0.4, 0.7),
                           'launch', jsonb_build_object('speed_ms', 11.2, 'elevation_deg', 4.0),
                           'clip', 'clips/20260920_1830_check_court/345-0123456789ab.mp4')),
      jsonb_build_object('point_no', 1, 'seq', 4, 'frame', 360, 'slot', null, 'team', 'B',
                         'action', 'dig', 'touch_number', 1, 'observed', false),
      jsonb_build_object('point_no', 2, 'seq', 0, 'frame', 811, 'slot', 'P1A', 'team', 'A',
                         'action', 'serve', 'touch_number', 0, 'observed', true))
    || case when p_second_rally then jsonb_build_array(
      jsonb_build_object('point_no', 2, 'seq', 1, 'frame', 840, 'slot', 'P1B', 'team', 'B',
                         'action', 'dig', 'touch_number', 1, 'observed', true),
      jsonb_build_object('point_no', 2, 'seq', 2, 'frame', 870, 'slot', 'P2B', 'team', 'B',
                         'action', 'set', 'touch_number', 2, 'outcome', 'error', 'observed', true))
       else '[]'::jsonb end,
    'provenance', jsonb_build_object('pipeline_version', 'check', 'git_dirty', false));
$$;

-- ── publish: applied → unchanged → applied (assignments survive) ──────────
do $$
declare r jsonb;
begin
  assert has_function_privilege('service_role', 'public.ingest_match_bundle(jsonb,text,text)', 'execute'),
    'service_role must be able to publish';
  assert not has_function_privilege('authenticated', 'public.ingest_match_bundle(jsonb,text,text)', 'execute'),
    'authenticated must NOT be able to publish';
  assert not has_function_privilege('anon', 'public.leaderboard(text,date,date,int,text)', 'execute'),
    'anon must not read the leaderboard';
  assert has_function_privilege('authenticated', 'public.leaderboard(text,date,date,int,text)', 'execute'),
    'members read the leaderboard (recreated in match_details)';
  assert not has_function_privilege('anon', 'public.player_profile(bigint,text,date,date,int)', 'execute'),
    'anon must not read profiles';
  assert not has_function_privilege('anon', 'public.match_report(bigint)', 'execute'),
    'anon must not read reports';
  assert has_function_privilege('authenticated', 'public.match_report(bigint)', 'execute'),
    'members read reports';
  assert not has_function_privilege('authenticated',
    'public.window_matches(text,date,date,int,bigint,boolean,text)', 'execute'),
    'the window helper is internal';
  assert has_function_privilege('anon', 'public.ping()', 'execute'), 'anon must reach ping()';
  assert not has_function_privilege('anon', 'public.can_see_match_clip(text)', 'execute')
     and has_function_privilege('authenticated', 'public.can_see_match_clip(text)', 'execute'),
    'the clip rule is for members (the storage policy calls it)';

  -- table privileges are explicit (20261007120000): the grant is the first
  -- gate, RLS the second
  -- (CASE: the planner may test the privilege before the relkind filter)
  assert not exists (
    select 1 from pg_class c
    where c.relnamespace = 'public'::regnamespace
      and case c.relkind
            when 'S' then has_sequence_privilege('anon', c.oid, 'usage, select, update')
            when 'r' then has_table_privilege('anon', c.oid, 'select, insert, update, delete, truncate')
                          or has_any_column_privilege('anon', c.oid, 'select, insert, update')
            when 'v' then has_table_privilege('anon', c.oid, 'select, insert, update, delete, truncate')
                          or has_any_column_privilege('anon', c.oid, 'select, insert, update')
            else false end),
    'anon must hold no privilege on any table, view or sequence';
  assert not has_table_privilege('authenticated', 'public.points', 'insert, update, delete')
     and not has_table_privilege('authenticated', 'public.actions', 'insert, update, delete')
     and not has_table_privilege('authenticated', 'public.match_sources', 'insert, update, delete')
     and not has_table_privilege('authenticated', 'public.match_publications', 'insert, update, delete')
     and not has_table_privilege('authenticated', 'public.matches', 'insert, delete')
     and not has_table_privilege('authenticated', 'public.profiles', 'insert, delete'),
    'pipeline-owned tables are not writable through the API';
  assert has_column_privilege('authenticated', 'public.matches', 'status', 'update')
     and not has_column_privilege('authenticated', 'public.matches', 'score_a', 'update')
     and not has_column_privilege('authenticated', 'public.match_participants', 'thumb_path', 'update')
     and not has_column_privilege('authenticated', 'public.profiles', 'email', 'update'),
    'only the admin-owned columns are writable through the API';
  assert has_column_privilege('authenticated', 'public.matches', 'venue', 'update')
     and has_column_privilege('authenticated', 'public.matches', 'match_type', 'update')
     and has_column_privilege('authenticated', 'public.matches', 'is_tournament', 'update')
     and has_column_privilege('authenticated', 'public.matches', 'tournament_level', 'update'),
    'the match details are admin-owned (20261014120000)';
  assert has_table_privilege('authenticated', 'public.venues', 'select, insert')
     and not has_table_privilege('authenticated', 'public.venues', 'update')
     and not has_table_privilege('authenticated', 'public.venues', 'delete')
     and has_table_privilege('service_role', 'public.venues', 'select'),
    'venues: read by members, added to by admins, exported by the backup';
  assert has_table_privilege('service_role', 'public.players', 'select')
     and not has_table_privilege('service_role', 'public.players', 'insert, update, delete')
     and not has_table_privilege('service_role', 'public.actions', 'insert, update, delete'),
    'the secret key reads the backup tables and writes only through the publish RPC';

  r := public.ingest_match_bundle(pg_temp.bundle('h1', 'vid1', false), 'b/h1.json', 'check');
  assert r ->> 'result' = 'applied', 'first publish must apply: ' || r::text;
  r := public.ingest_match_bundle(pg_temp.bundle('h1', 'vid1', false), 'b/h1.json', 'check');
  assert r ->> 'result' = 'unchanged', 'same hash must be unchanged: ' || r::text;
  assert (select count(*) from public.actions a join public.matches m on m.id = a.match_id
          where m.match_key = '20260920_1830_check_court') = 6, 'unchanged publish must not touch rows';
  assert (select set_no from public.points p join public.matches m on m.id = p.match_id
          where m.match_key = '20260920_1830_check_court' and point_no = 1) = 1,
    'missing set_no must take the default 1';
  assert (select start_time from public.matches where match_key = '20260920_1830_check_court') = '18:30',
    'start_time from the key';
end $$;

-- the match id, for the role-switched blocks below (viewers can't look it up)
select set_config('check.match_id',
                  (select id::text from public.matches where match_key = '20260920_1830_check_court'),
                  true);

-- admin assigns the slots (admin-owned) ...
update public.match_participants mp set player_id = p.id
from public.players p, public.matches m
where m.id = mp.match_id and m.match_key = '20260920_1830_check_court'
  and p.display_name = case mp.slot when 'P1A' then 'Check Ari' when 'P2A' then 'Check Joan'
                                    when 'P1B' then 'Check Opp1' else 'Check Opp2' end;

-- ... and a changed bundle must keep them
do $$
declare r jsonb;
begin
  r := public.ingest_match_bundle(pg_temp.bundle('h2', 'vid1', true), 'b/h2.json', 'check');
  assert r ->> 'result' = 'applied' and (r ->> 'revision')::int = 3, 'changed bundle applies as rev 3: ' || r::text;
  assert (select count(*) from public.match_participants mp join public.matches m on m.id = mp.match_id
          where m.match_key = '20260920_1830_check_court' and mp.player_id is not null) = 4,
    'slot assignments must survive a re-publish';
  assert (select count(*) from public.match_publications p join public.matches m on m.id = p.match_id
          where m.match_key = '20260920_1830_check_court') = 3, 'every publish call is logged';
  begin
    perform public.ingest_match_bundle(pg_temp.bundle('h3', 'OTHER-VIDEO', true), 'b/h3.json', 'check');
    assert false, 'a different video under the same name must be refused';
  exception when raise_exception then
    null;  -- refused, as designed
  end;
end $$;

-- ── fantasy rules (G1) as the admin sees them ─────────────────────────────
do $$
begin
  -- P1A: dig +1, kill +1 (serve without outcome: 0) = 2.0
  -- P2A: assist +0.5 = 0.5 ; P1B: dig +1 = 1.0 ; P2B: set error (ball handling) -1 = -1.0
  assert (select fantasy from public.player_match_fantasy f join public.matches m on m.id = f.match_id
          where m.match_key = '20260920_1830_check_court' and slot = 'P1A') = 2.0, 'P1A fantasy';
  assert (select fantasy from public.player_match_fantasy f join public.matches m on m.id = f.match_id
          where m.match_key = '20260920_1830_check_court' and slot = 'P2A') = 0.5, 'P2A fantasy';
  assert (select fantasy from public.player_match_fantasy f join public.matches m on m.id = f.match_id
          where m.match_key = '20260920_1830_check_court' and slot = 'P1B') = 1.0, 'P1B fantasy';
  assert (select fantasy from public.player_match_fantasy f join public.matches m on m.id = f.match_id
          where m.match_key = '20260920_1830_check_court' and slot = 'P2B') = -1.0,
    'P2B fantasy: a set error is a ball-handling error (-1)';
end $$;

-- a block scores only when it wins the point (20261014100000_block_kill_only)
do $$
begin
  assert (select outcome from public.fantasy_rules r join public.fantasy_rulesets s on s.id = r.ruleset_id
          where s.name = 'G1' and r.rule_key = 'block') = 'kill', 'the block rule needs a kill';
end $$;

-- editing one rule rescores history; a second active rule set is refused
update public.fantasy_rules set points = 2.0
where rule_key = 'dig' and ruleset_id = (select id from public.fantasy_rulesets where is_active);
do $$
begin
  assert (select fantasy from public.player_match_fantasy f join public.matches m on m.id = f.match_id
          where m.match_key = '20260920_1830_check_court' and slot = 'P1A') = 3.0, 'dig rule edit rescored';
  begin
    insert into public.fantasy_rulesets (name, is_active) values ('second', true);
    assert false, 'two active rule sets must be refused';
  exception when unique_violation then
    null;
  end;
end $$;
update public.fantasy_rules set points = 1.0
where rule_key = 'dig' and ruleset_id = (select id from public.fantasy_rulesets where is_active);

-- the admin pages write through the API role: the admin-owned columns only
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', true);
do $$
declare
  v_id   bigint := current_setting('check.match_id')::bigint;
  v_opp2 bigint := (select id from public.players where display_name = 'Check Opp2');
begin
  insert into public.players (display_name) values ('Check New');   -- identity, no sequence grant
  delete from public.players where display_name = 'Check New';
  update public.matches set title = 'Check title' where id = v_id;
  assert (select title from public.matches where id = v_id) = 'Check title', 'admin edits the match details';
  -- the dropdowns (20261014120000): a venue from the list, type, tournament, level
  insert into public.venues (name) values ('Check Beach');
  update public.matches set venue = 'Check Beach', match_type = 'mixed', is_tournament = true,
                            tournament_level = 'regional' where id = v_id;
  assert (select venue = 'Check Beach' and match_type = 'mixed' and tournament_level = 'regional'
          from public.matches where id = v_id), 'admin tags the match';
  begin
    update public.matches set venue = 'Nowhere' where id = v_id;
    assert false, 'a venue must come from the list';
  exception when foreign_key_violation then
    null;
  end;
  begin
    insert into public.venues (name) values ('check beach');
    assert false, 'one spelling per venue';
  exception when unique_violation then
    null;
  end;
  begin
    update public.matches set is_tournament = false where id = v_id;
    assert false, 'a level needs a tournament';
  exception when check_violation then
    null;
  end;
  begin
    update public.matches set match_type = 'men' where id = v_id;
    assert false, 'match type is male / female / mixed';
  exception when check_violation then
    null;
  end;
  update public.match_participants set player_id = null where match_id = v_id and slot = 'P2B';
  update public.match_participants set player_id = v_opp2 where match_id = v_id and slot = 'P2B';
  assert (select assigned_by from public.match_participants where match_id = v_id and slot = 'P2B')
         = '00000000-0000-0000-0000-00000000000a', 'the assignment is stamped with the admin';
  update public.profiles set display_name = 'Bob' where user_id = '00000000-0000-0000-0000-0000000000b0';
  begin
    update public.matches set score_a = 99 where id = v_id;
    assert false, 'a score must not be writable through the API, even by an admin';
  exception when insufficient_privilege then
    null;
  end;
  begin
    update public.match_participants set thumb_path = 'x' where match_id = v_id;
    assert false, 'a thumbnail path must not be writable through the API';
  exception when insufficient_privilege then
    null;
  end;
  begin
    update public.profiles set email = 'x@check.test' where user_id = '00000000-0000-0000-0000-0000000000b0';
    assert false, 'an account email must not be writable through the API';
  exception when insufficient_privilege then
    null;
  end;
end $$;
reset role;

-- the publishable key without a login: the keep-alive, and nothing else
set local role anon;
do $$
begin
  assert public.ping() like 'ok:%', 'the keep-alive answers anon';
  begin
    perform count(*) from public.matches;
    assert false, 'anon must not even reach a table';
  exception when insufficient_privilege then
    null;
  end;
end $$;
reset role;

-- an admin copies G1, changes a value and activates the copy; a viewer can't
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', true);
do $$
declare v_new bigint;
begin
  v_new := public.clone_ruleset((select id from public.fantasy_rulesets where name = 'G1'), 'G1 kills x2');
  update public.fantasy_rules set points = 2.0 where ruleset_id = v_new and rule_key = 'kill';
  perform public.activate_ruleset(v_new);
  assert (select name from public.fantasy_rulesets where is_active) = 'G1 kills x2', 'copy active';
  assert (select fantasy from public.match_box_score(current_setting('check.match_id')::bigint)
          where slot = 'P1A') = 3.0, 'kill worth 2 under the copy';
  perform public.activate_ruleset((select id from public.fantasy_rulesets where name = 'G1'));
end $$;
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
begin
  begin
    perform public.activate_ruleset((select id from public.fantasy_rulesets where name = 'G1 kills x2'));
    assert false, 'a viewer must not switch the scoring';
  exception when raise_exception then
    null;
  end;
end $$;
reset role;

-- ── access tiers ──────────────────────────────────────────────────────────
-- What the publisher put in the media bucket (attack clips, 20261010100000):
-- the clip of Ari's spike, a clip under a key no match has, a slot thumbnail.
insert into storage.objects (bucket_id, name) values
  ('match-media', 'clips/20260920_1830_check_court/345-0123456789ab.mp4'),
  ('match-media', 'clips/20990101_0000_no_such_match/1-0123456789ab.mp4'),
  ('match-media', 'thumbs/20260920_1830_check_court/P1A.jpg');

-- the match is a DRAFT: not even its own players watch its clips
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000a1', true);
do $$
begin
  assert (select count(*) from storage.objects where bucket_id = 'match-media') = 0,
    'no clip of a draft';
end $$;
reset role;

-- a stranger (bob) while the match is a DRAFT: sees nothing
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
begin
  assert (select count(*) from public.matches where match_key = '20260920_1830_check_court') = 0,
    'viewer must not see drafts';
  assert (select count(*) from public.match_box_score(current_setting('check.match_id')::bigint)) = 0,
    'no box score of a draft';
  assert public.player_profile((select id from public.players where display_name = 'Check Ari'))
           -> 'history' = '[]'::jsonb, 'a draft is in nobody''s history';
end $$;
reset role;

update public.matches set status = 'published', season = 'S1'
where match_key = '20260920_1830_check_court';
-- a second, newer published match (no touches) so windows have something to cut
with m2 as (
  insert into public.matches (match_key, match_date, start_time, season, status, n_points)
  values ('20260927_1900_check_second', '2026-09-27', '19:00', 'S2', 'published', 20)
  returning id)
insert into public.match_participants (match_id, slot, player_id)
select m2.id, 'P1A', (select id from public.players where display_name = 'Check Ari') from m2;

-- bob after publishing: league tier only
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
declare v_id bigint;
begin
  select id into v_id from public.matches where match_key = '20260920_1830_check_court';
  assert v_id is not null, 'viewer sees a published match';
  assert (select count(*) from public.actions where match_id = v_id) = 0,
    'non-participant must not read touches';
  assert (select count(*) from public.points where match_id = v_id) = 0,
    'non-participant must not read points';
  assert (select count(*) from public.match_sources) = 0, 'video links are admin-only';
  assert (select count(*) from public.match_publications) = 0, 'publication log is admin-only';
  assert (select count(*) from public.match_box_score(v_id)) = 4, 'box score is league tier';
  assert (select fantasy from public.match_box_score(v_id) where slot = 'P1A') = 2.0,
    'box score fantasy (definer function sees the touches)';
  assert (select fantasy from public.leaderboard() where display_name = 'Check Ari') = 2.0,
    'leaderboard is league tier';
  assert (public.player_profile((select id from public.players where display_name = 'Check Ari'))
          ->> 'can_see_analytics')::boolean = false, 'analytics private by default';
  assert (public.player_profile((select id from public.players where display_name = 'Check Ari'))
          -> 'totals' ->> 'fantasy')::numeric = 2.0, 'profile totals are league tier';
  -- time windows (I1): season, date range, last N matches
  assert (select count(*) from public.leaderboard()) = 4, 'unfiltered: 4 players';
  assert (select count(*) from public.leaderboard(p_season => 'S1')) = 4, 'season S1';
  assert (select count(*) from public.leaderboard(p_season => 'nope')) = 0, 'unknown season';
  assert (select count(*) from public.leaderboard(p_from => '2026-09-21')) = 1, 'from: only the newer match';
  assert (select count(*) from public.leaderboard(p_to => '2026-09-20')) = 4, 'to: only the older match';
  assert (select matches from public.leaderboard(p_last_n => 1)) = 1
     and (select fantasy from public.leaderboard(p_last_n => 1)) = 0, 'last 1 match = the newer one';
  assert (select points_played from public.leaderboard() where display_name = 'Check Ari') = 22,
    'points played = the points of every match in the window';
  assert (select attacks from public.leaderboard() where display_name = 'Check Ari') = 1, 'attack denominator';
  -- the league comparison (player_page_v2): serve errors, and the TEAM's
  -- side-out / break-point over the player's matches -- league tier, so a
  -- member who did not play reads them
  assert (select serve_errors = 0 and recv_points = 1 and recv_won = 1 and serve_points = 1 and serve_won = 1
          from public.leaderboard() where display_name = 'Check Ari'),
    'team A received 1 point and won it, served 1 and won it';
  assert (select recv_points = 1 and recv_won = 0 and serve_points = 1 and serve_won = 0
          from public.leaderboard() where display_name = 'Check Opp1'),
    'team B received 1 and served 1, lost both';
  assert (select recv_points + serve_points from public.leaderboard(p_last_n => 1)) = 0,
    'a match without points adds none';
  assert (public.player_profile((select id from public.players where display_name = 'Check Ari'),
                                p_last_n => 1) -> 'totals' ->> 'matches')::int = 1, 'profile last 1';
  assert (public.player_profile((select id from public.players where display_name = 'Check Ari'),
                                p_season => 'S1') -> 'totals' ->> 'fantasy')::numeric = 2.0, 'profile season';
  assert (public.player_profile((select id from public.players where display_name = 'Check Ari'),
                                p_season => 'S1') -> 'totals' ->> 'fantasy_per_21')::numeric = 21.0,
    'fantasy per 21 points: 2.0 over 2 points';
  assert (public.player_profile((select id from public.players where display_name = 'Check Ari'))
          -> 'form' ->> 'n')::int = 2, 'form counts all matches, window or not';
  -- the same-match-type reference (20261014120000): the first match is mixed,
  -- the newer one has no type; last N counts within the type
  assert (select count(*) from public.leaderboard(p_match_type => 'mixed')) = 4, 'mixed: 4 players';
  assert (select count(*) from public.leaderboard(p_match_type => 'female')) = 0, 'no female match';
  assert (select fantasy from public.leaderboard(p_last_n => 1, p_match_type => 'mixed')
          where display_name = 'Check Ari') = 2.0, 'the last mixed match is the older one';
  -- venues: every member reads the list, only an admin adds to it
  assert (select count(*) from public.venues where name = 'Check Beach') = 1, 'members read the venues';
  begin
    insert into public.venues (name) values ('Bob Beach');
    assert false, 'a viewer must not add a venue';
  exception when insufficient_privilege then
    null;
  end;

  -- match report for a non-participant: the league tier only (box-score
  -- lines, team side-out / break); nobody shares analytics yet
  declare r jsonb;
  begin
    r := public.match_report(v_id);
    assert (r -> 'teams' -> 'A' ->> 'recv_n')::int = 1 and (r -> 'teams' -> 'A' ->> 'recv_won')::int = 1,
      'team A side-out 1/1';
    assert (r -> 'teams' -> 'B' ->> 'serve_n')::int = 1 and (r -> 'teams' -> 'B' ->> 'serve_won')::int = 0,
      'team B break 0/1';
    assert jsonb_array_length(r -> 'players') = 4, 'a line per slot';
    assert (select (x ->> 'fantasy')::numeric = 2.0 and (x ->> 'kills')::int = 1
            from jsonb_array_elements(r -> 'players') x where x ->> 'slot' = 'P1A'),
      'the box-score line is league tier';
    assert (select bool_and(x -> 'hit' = 'null'::jsonb and x -> 'own_serve' = 'null'::jsonb
                            and x -> 'avg' = 'null'::jsonb)
            from jsonb_array_elements(r -> 'players') x),
      'attack split, own-serve record and averages are analytics tier';
    assert r -> 'serve_targets' = '{}'::jsonb, 'serve targets are analytics tier';
    -- point 1: serve, dig, set, spike, dig = 5 touches; over the net with the
    -- serve and with the spike (the last touch is the losers': it did not go
    -- back). Point 2 has 3 touches and one crossing.
    assert r -> 'longest_rally' = '{"point_no": 1, "touches": 5, "net_crossings": 2}'::jsonb,
      'the longest rally is league tier: two counts and a point number, no touch';
    assert (select count(*) from public.actions) = 0,
      'and the reader who gets it still reads no touch of that match';
    assert r ->> 'timeline' is null, 'the per-point timeline needs match detail';
  end;
  assert not public.set_my_privacy(true), 'bob has no player to change';
  assert (select count(*) from storage.objects where bucket_id = 'match-media') = 0,
    'a clip follows the touches of its match: none for a member who did not play it';
  update public.players set display_name = 'hacked';
  assert not exists (select 1 from public.players where display_name = 'hacked'),
    'viewers cannot edit players';
  update public.match_participants set player_id = null;
  assert (select count(*) from public.match_participants
          where match_id = v_id and player_id is null) = 0, 'viewers cannot re-assign slots';
end $$;
reset role;

-- ari (plays in the match): sees its detail and her own analytics
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000a1', true);
do $$
declare v_id bigint; v_prof jsonb;
begin
  select id into v_id from public.matches where match_key = '20260920_1830_check_court';
  assert (select count(*) from public.actions where match_id = v_id) = 8, 'participant reads touches';
  v_prof := public.player_profile((select id from public.players where display_name = 'Check Ari'));
  assert (v_prof ->> 'can_see_analytics')::boolean, 'a player sees her own analytics';
  assert (v_prof -> 'analytics' ->> 'kill_rate')::numeric = 1.0, 'kill rate 1/1';
  assert (v_prof -> 'analytics' -> 'landings' -> 0 ->> 'result') = 'kill'
     and (v_prof -> 'analytics' -> 'landings' -> 0 ->> 'ey')::numeric = 0.9,
         'landings carry their result and position error';
  -- the attack map (player_page_v2): where the ball was hit, how far off
  -- that may be, spike or free ball, the possession, the match day
  assert (v_prof -> 'analytics' -> 'landings' -> 0) @>
         '{"sx": 6.3, "sy": 5.4, "sex": 0.4, "sey": 0.7, "a": "spike", "p": 1, "d": "2026-09-20"}'::jsonb,
         'landings carry the start of the attack';
  -- the analytics a window of one match gives: counts with denominators ...
  assert (v_prof -> 'analytics' ->> 'n_attacks')::int = 1
     and (v_prof -> 'analytics' ->> 'n_kills')::int = 1
     and (v_prof -> 'analytics' ->> 'n_serves')::int = 1, 'denominators';
  -- N4: her one attack came off the reception
  assert (v_prof -> 'analytics' -> 'hit' -> 'reception' ->> 'n')::int = 1
     and (v_prof -> 'analytics' -> 'hit' -> 'reception' ->> 'kills')::int = 1
     and (v_prof -> 'analytics' -> 'hit' -> 'transition' ->> 'n')::int = 0, 'attack split';
  -- hard / touch (attack_shots): her one attack is a spike the post-run
  -- read typed hard; the four rows add up to n_attacks
  assert (v_prof -> 'analytics' -> 'shots') =
    '{"hard": {"n": 1, "kills": 1, "errors": 0}, "touch": {"n": 0, "kills": 0, "errors": 0},
      "free": {"n": 0, "kills": 0, "errors": 0}, "unread": {"n": 0, "kills": 0, "errors": 0}}'::jsonb,
    'attacks by shot';
  assert (v_prof -> 'analytics' -> 'landings' -> 0 ->> 'type') = 'hard', 'the map knows the shot';
  -- attack clips: the attack names its clip, and she may fetch that file --
  -- that one only (no thumbnail, no clip under another key)
  assert (v_prof -> 'analytics' -> 'landings' -> 0 ->> 'clip') = 'clips/20260920_1830_check_court/345-0123456789ab.mp4', 'the attack names its clip';
  assert (select array_agg(name) from storage.objects where bucket_id = 'match-media')
         = array['clips/20260920_1830_check_court/345-0123456789ab.mp4'], 'a player of the match reads its clips, nothing else in the bucket';
  -- N1: she served point 2 (won); her team received point 1 (won) and served point 2 (won)
  assert (v_prof -> 'analytics' -> 'rally' -> 'own_serve') = '{"n": 1, "won": 1}'::jsonb, 'break % as server';
  assert (v_prof -> 'analytics' -> 'rally' -> 'team_receiving') = '{"n": 1, "won": 1}'::jsonb, 'side-out %';
  assert (v_prof -> 'analytics' -> 'rally' -> 'team_serving') = '{"n": 1, "won": 1}'::jsonb, 'team break %';
  -- N2: Opp1 took her serve; she took the one serve that came to her team
  assert (v_prof -> 'analytics' -> 'serve_in') = '{"opp_serves": 1, "team_credited": 1, "mine": 1}'::jsonb,
    'serves received';
  assert (v_prof -> 'analytics' -> 'serve_out' -> 'to' -> 0 ->> 'display_name') = 'Check Opp1'
     and (v_prof -> 'analytics' -> 'serve_out' ->> 'unseen')::int = 0, 'serve targets';
  -- N3: her reception became a spike, and a first-ball kill
  assert (v_prof -> 'analytics' -> 'reception') =
    '{"n": 1, "none": 0, "error": 0, "spike": 1, "overpass": 0, "first_ball_kills": 1}'::jsonb,
    'reception outcome';
  -- pass_map: her one dig followed the serve (a reception); the set after it
  -- was seen at (4.5, 6.0) on her own half, so that is where the ball went
  assert (v_prof -> 'analytics' -> 'passes') =
    '[{"k": "reception", "sx": 2.0, "sy": 3.5, "sex": null, "sey": null,
       "x": 4.5, "y": 6.0, "ex": 0.4, "ey": 0.7, "to": "set", "d": "2026-09-20"}]'::jsonb,
    'her reception, and where it went';
  -- serve_map: her one serve stayed in play and Opp1 took it, but that dig
  -- has no position, so the serve has no spot
  assert (v_prof -> 'analytics' -> 'serves') =
    '[{"r": "in", "x": null, "y": null, "ex": null, "ey": null, "src": null, "in": null,
       "to": "Check Opp1", "d": "2026-09-20"}]'::jsonb,
    'her serve, who took it, and no spot without a seen reception';
  assert (v_prof -> 'analytics' -> 'attack_series' -> 0 ->> 'r') = 'kill'
     and (v_prof -> 'analytics' -> 'serve_series' -> 0 ->> 'r') = 'other', 'progress series';
  -- the four players read the whole report of their match (they can count
  -- its touches anyway)
  declare r jsonb := public.match_report(v_id);
  begin
    assert (select bool_and(x -> 'hit' <> 'null'::jsonb and x -> 'own_serve' <> 'null'::jsonb)
            from jsonb_array_elements(r -> 'players') x), 'a participant reads every line in full';
    assert (select x -> 'hit' -> 'reception' = '{"n": 1, "kills": 1, "errors": 0}'::jsonb
               and x -> 'own_serve' = '{"n": 1, "won": 1}'::jsonb
               and (x -> 'avg' ->> 'matches')::int = 1
            from jsonb_array_elements(r -> 'players') x where x ->> 'slot' = 'P1A'),
      'Ari: reception attack 1/1, own serve 1/1, one OTHER published match to compare with';
    assert (r -> 'serve_targets' -> 'A' -> 'to' ->> 'P1B')::int = 1
       and (r -> 'serve_targets' -> 'B' -> 'to' ->> 'P1A')::int = 1, 'serve targets';
  end;
  -- F3: per-point fantasy timeline for a participant
  assert (select jsonb_array_length(public.match_report(v_id) -> 'timeline')) = 4,
    'a participant reads the per-point fantasy';
  assert (select (x ->> 'pts')::numeric from jsonb_array_elements(public.match_report(v_id) -> 'timeline') x
          where x ->> 'point_no' = '1' and x ->> 'slot' = 'P1A') = 2.0, 'point 1: dig + kill = 2.0';
  assert public.set_my_privacy(true), 'ari flips her privacy';
end $$;
reset role;

-- A match published before the post-run flight read holds the causal guess in
-- spike_type and no extra.launch: it reads "not read", never a type.
update public.actions set extra = extra - 'launch' where action = 'spike';
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000a1', true);
do $$
declare v_prof jsonb;
begin
  v_prof := public.player_profile((select id from public.players where display_name = 'Check Ari'));
  assert (v_prof -> 'analytics' -> 'shots' -> 'unread') = '{"n": 1, "kills": 1, "errors": 0}'::jsonb
     and (v_prof -> 'analytics' -> 'shots' -> 'hard' ->> 'n')::int = 0,
    'a causal type is never counted as hard / touch';
  assert (v_prof -> 'analytics' -> 'landings' -> 0 -> 'type') = 'null'::jsonb,
    'a causal type is never drawn on the map';
end $$;
reset role;
update public.actions
   set extra = extra || '{"launch": {"speed_ms": 11.2, "elevation_deg": 4.0}}'::jsonb
 where action = 'spike';

-- reception vs defense (pass_map): Opp1's dig after Ari's spike is a DEFENSE,
-- the one after Ari's serve in point 2 a RECEPTION. A set is added after the
-- defense so it has somewhere to go; the reception's set has no position.
update public.actions set slot = 'P1B', observed = true, own_x_m = 3.0, own_y_m = 3.0
 where point_no = 1 and seq = 4;
insert into public.actions (match_id, point_no, seq, frame, slot, team, side, action, touch_number,
                            observed, own_x_m, own_y_m)
  select match_id, 1, 5, 375, 'P2B', 'B', side, 'set', 2, true, 5.0, 6.2
  from public.actions where point_no = 1 and seq = 4;
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', true);
do $$
declare v_prof jsonb;
begin
  v_prof := public.player_profile((select id from public.players where display_name = 'Check Opp1'));
  assert jsonb_array_length(v_prof -> 'analytics' -> 'passes') = 2, 'Opp1 has a defense and a reception';
  -- the set just added is a sixth touch of point 1, on the half the ball was
  -- already in: one more touch, no more crossings
  assert public.match_report(current_setting('check.match_id')::bigint) -> 'longest_rally'
         = '{"point_no": 1, "touches": 6, "net_crossings": 2}'::jsonb,
    'the longest rally is recounted from the rows';
  assert (v_prof -> 'analytics' -> 'passes' -> 0) @>
    '{"k": "defense", "sx": 3.0, "sy": 3.0, "x": 5.0, "y": 6.2, "to": "set", "d": "2026-09-20"}'::jsonb,
    'the dig after an attack is a defense, and it went to the set';
  assert (v_prof -> 'analytics' -> 'passes' -> 1) =
    '{"k": "reception", "sx": null, "sy": null, "sex": null, "sey": null, "x": null, "y": null,
      "ex": null, "ey": null, "to": null, "d": "2026-09-20"}'::jsonb,
    'a reception whose next touch has no position keeps its place with no destination';
  -- serve_map: Opp1's serve was received by Ari at (2.0, 3.5) in HER frame,
  -- which is (6.0, 12.5) seen from the server: across the net, mirrored
  assert (v_prof -> 'analytics' -> 'serves') =
    '[{"r": "in", "x": 6.0, "y": 12.5, "ex": null, "ey": null, "src": "reception", "in": null,
       "to": "Check Ari", "d": "2026-09-20"}]'::jsonb,
    'a serve is marked where the receiver played it, in the server''s frame';
end $$;
reset role;
delete from public.actions where point_no = 1 and seq = 5;
update public.actions set slot = null, observed = false, own_x_m = null, own_y_m = null
 where point_no = 1 and seq = 4;

-- serve_map: a serve nobody touched is marked where the ball came down,
-- through the half the server stood on. Point 2 becomes Ari's service error,
-- the ball 1 m wide of the camera-frame court, 3 m from the far baseline.
savepoint serve_ground;
delete from public.actions where point_no = 2 and seq > 0;
update public.actions set side = 'near', outcome = 'error' where point_no = 2 and seq = 0;
update public.points set end_kind = 'ground', end_x_m = 9.0, end_y_m = 3.0, end_in_court = false
 where point_no = 2;
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000a1', true);
do $$
declare v_prof jsonb;
begin
  v_prof := public.player_profile((select id from public.players where display_name = 'Check Ari'));
  assert (v_prof -> 'analytics' -> 'serves') =
    '[{"r": "error", "x": 9.0, "y": 13.0, "ex": null, "ey": null, "src": "ground", "in": false,
       "to": null, "d": "2026-09-20"}]'::jsonb,
    'served from the near half: the ball-death spot, 13 m from her baseline, called out';
  assert jsonb_array_length(v_prof -> 'analytics' -> 'serves') = (v_prof -> 'analytics' ->> 'n_serves')::int,
    'the map lists the serves the tiles count';
end $$;
reset role;
update public.actions set side = 'far' where point_no = 2 and seq = 0;
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000a1', true);
do $$
declare v_prof jsonb;
begin
  v_prof := public.player_profile((select id from public.players where display_name = 'Check Ari'));
  assert (v_prof -> 'analytics' -> 'serves' -> 0) @> '{"x": -1.0, "y": 3.0, "src": "ground"}'::jsonb,
    'served from the far half: the same spot is on her own side of the net, never over';
end $$;
reset role;
update public.actions set side = null where point_no = 2 and seq = 0;
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000a1', true);
do $$
declare v_prof jsonb;
begin
  v_prof := public.player_profile((select id from public.players where display_name = 'Check Ari'));
  assert (v_prof -> 'analytics' -> 'serves' -> 0) @> '{"r": "error", "x": null, "y": null, "src": null, "in": null}'::jsonb,
    'without the half the server stood on there is no spot (never a guess)';
end $$;
reset role;
rollback to savepoint serve_ground;

-- bob again: ari's analytics are now public; the touches are still not
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
begin
  assert (public.player_profile((select id from public.players where display_name = 'Check Ari'))
          ->> 'can_see_analytics')::boolean, 'opted-in analytics are visible to members';
  assert (select count(*) from public.actions) = 0, 'touches stay participant-only';
  -- a clip shows all four players: it follows the match, never one profile
  assert (public.player_profile((select id from public.players where display_name = 'Check Ari'))
          -> 'analytics' -> 'landings' -> 0 -> 'clip') = 'null'::jsonb
     and (select count(*) from storage.objects where bucket_id = 'match-media') = 0,
    'sharing analytics shows the attack map without its clips';
  -- the report follows: Ari's own numbers open, her partner's stay closed, and
  -- so does everything that would give the partner away by subtraction
  declare r jsonb := public.match_report(current_setting('check.match_id')::bigint);
  begin
    assert (select x -> 'hit' <> 'null'::jsonb and (x -> 'avg' ->> 'matches')::int = 1
            from jsonb_array_elements(r -> 'players') x where x ->> 'slot' = 'P1A'),
      'a player who shares shows her attack split and average';
    assert (select x -> 'hit' = 'null'::jsonb and x -> 'avg' = 'null'::jsonb
            from jsonb_array_elements(r -> 'players') x where x ->> 'slot' = 'P2A'),
      'her partner did not share';
    assert (select bool_and(x -> 'own_serve' = 'null'::jsonb)
            from jsonb_array_elements(r -> 'players') x),
      'own-serve splits the team''s break-points: hidden while one teammate is private';
    assert r -> 'serve_targets' = '{}'::jsonb,
      'serve targets split the receiving pair: hidden while one of them is private';
  end;
end $$;
reset role;

-- both players of team A share: the team-split numbers of THAT team open
update public.players set profile_public = true where display_name = 'Check Joan';
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
declare r jsonb := public.match_report(current_setting('check.match_id')::bigint);
begin
  assert (select x -> 'own_serve' = '{"n": 1, "won": 1}'::jsonb
          from jsonb_array_elements(r -> 'players') x where x ->> 'slot' = 'P1A')
     and (select x -> 'own_serve' = 'null'::jsonb
          from jsonb_array_elements(r -> 'players') x where x ->> 'slot' = 'P1B'),
    'own serve: team A open, team B closed';
  assert (r -> 'serve_targets' -> 'B' -> 'to' ->> 'P1A')::int = 1 and not r -> 'serve_targets' ? 'A',
    'serve targets: who of team A received is open, who of team B received is not';
  assert r ->> 'timeline' is null, 'sharing analytics never opens the play-by-play';
end $$;
reset role;
update public.players set profile_public = false where display_name = 'Check Joan';

-- admin: detail_public opens the play-by-play to everyone
update public.matches set detail_public = true where match_key = '20260920_1830_check_court';
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
declare r jsonb := public.match_report(current_setting('check.match_id')::bigint);
begin
  assert (select count(*) from public.actions) = 8, 'detail_public opens the touches';
  assert (select bool_and(x -> 'hit' <> 'null'::jsonb and x -> 'own_serve' <> 'null'::jsonb)
          from jsonb_array_elements(r -> 'players') x)
     and r -> 'serve_targets' ? 'A' and r -> 'serve_targets' ? 'B'
     and jsonb_array_length(r -> 'timeline') = 4,
    'an opened play-by-play opens the whole report with it';
  assert (public.player_profile((select id from public.players where display_name = 'Check Ari'))
          -> 'analytics' -> 'landings' -> 0 ->> 'clip') = 'clips/20260920_1830_check_court/345-0123456789ab.mp4'
     and (select array_agg(name) from storage.objects where bucket_id = 'match-media')
         = array['clips/20260920_1830_check_court/345-0123456789ab.mp4'], 'and its clips';
end $$;
reset role;

-- an admin reads the whole media bucket (thumbnails, every clip)
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', true);
do $$
begin
  assert (select count(*) from storage.objects where bucket_id = 'match-media') = 3,
    'admins read every file of the match buckets';
end $$;
reset role;

-- ── login codes: the gate behind the login function (20261007140000) ──────
-- The function answers every address the same way; the gate decides whether a
-- mail goes out, and only the service key reaches it.
update auth.users set email_confirmed_at = now() where email = 'ari@check.test';   -- an accepted invite
do $$
begin
  assert has_function_privilege('service_role', 'public.login_code_gate(text,text)', 'execute')
     and not has_function_privilege('anon', 'public.login_code_gate(text,text)', 'execute')
     and not has_function_privilege('authenticated', 'public.login_code_gate(text,text)', 'execute'),
    'only the login function (service key) reaches the gate';
  assert not has_table_privilege('authenticated', 'public.login_code_requests', 'select, insert, update, delete')
     and not has_table_privilege('service_role', 'public.login_code_requests', 'select, insert, update, delete')
     and (select relrowsecurity from pg_class where oid = 'public.login_code_requests'::regclass),
    'the request log belongs to the gate alone';
end $$;
set local role service_role;
do $$
begin
  assert public.login_code_gate('  Ari@Check.Test ', '203.0.113.7'),
    'an accepted invite is forwarded (case and spaces ignored)';
  assert not public.login_code_gate('ari@check.test', '203.0.113.8'), 'one request a minute per address';
  assert not public.login_code_gate('bob@check.test', '203.0.113.7'),
    'an invite that was never accepted is not forwarded';
  assert not public.login_code_gate('nobody@check.test', '203.0.113.7'), 'an unknown address is not forwarded';
  assert not public.login_code_gate('not-an-email', '203.0.113.7'), 'a malformed address is not forwarded';
end $$;
reset role;
do $$
begin
  assert (select count(*) from public.login_code_requests where ip in ('203.0.113.7', '203.0.113.8')) = 3,
    'a request that passed the limits is logged once (the repeat and the malformed one are not)';
  assert not exists (select 1 from public.login_code_requests where email_sha256 !~ '^[0-9a-f]{64}$'),
    'the log holds hashes, never addresses';

  -- five an hour per address
  update public.login_code_requests set requested_at = now() - interval '2 minutes' where ip = '203.0.113.7';
  insert into public.login_code_requests (email_sha256, ip, requested_at)
  select encode(sha256(convert_to('ari@check.test', 'UTF8')), 'hex'), '203.0.113.7', now() - interval '10 minutes'
  from generate_series(1, 4);
  assert not public.login_code_gate('ari@check.test', '203.0.113.7'), 'five requests an hour per address';

  -- thirty an hour per IP, whoever they are for
  update auth.users set email_confirmed_at = now() where email = 'admin@check.test';
  insert into public.login_code_requests (email_sha256, ip, requested_at)
  select encode(sha256(convert_to('flood' || g || '@check.test', 'UTF8')), 'hex'), '198.51.100.9', now() - interval '5 minutes'
  from generate_series(1, 30) g;
  assert not public.login_code_gate('admin@check.test', '198.51.100.9'), 'thirty requests an hour per IP';
  assert public.login_code_gate('admin@check.test', '198.51.100.10'), 'another IP is not affected';

  -- the log keeps a day
  insert into public.login_code_requests (email_sha256, ip, requested_at)
  values (repeat('0', 64), '192.0.2.1', now() - interval '2 days');
  perform public.login_code_gate('nobody2@check.test', '192.0.2.2');
  assert not exists (select 1 from public.login_code_requests where ip = '192.0.2.1'), 'requests older than a day are dropped';
end $$;

-- ── unknown players (20261008100000) ──────────────────────────────────────
-- A slot the admin marks unknown keeps its stats INSIDE the match and never
-- reaches a cross-match view; re-tagging it hands the match to the player.
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', true);
do $$
declare v_id bigint := current_setting('check.match_id')::bigint;
begin
  assert has_column_privilege('authenticated', 'public.match_participants', 'is_unknown', 'update'),
    'the admin pages write the flag through the API role';
  begin
    update public.match_participants set is_unknown = true where match_id = v_id and slot = 'P2B';
    assert false, 'a slot cannot be unknown and keep its player';
  exception when check_violation then
    null;
  end;
  update public.match_participants set player_id = null, is_unknown = true
  where match_id = v_id and slot = 'P2B';
  assert (select is_unknown and player_id is null and assigned_by = '00000000-0000-0000-0000-00000000000a'
          from public.match_participants where match_id = v_id and slot = 'P2B'),
    'marking a slot unknown is stamped with the admin';
end $$;
reset role;

-- a republish with changed content must keep the flag (admin-owned)
do $$
declare r jsonb;
begin
  r := public.ingest_match_bundle(pg_temp.bundle('h-unknown', 'vid1', true), 'b/hu.json', 'check');
  assert r ->> 'result' = 'applied', 'changed bundle applies: ' || r::text;
  assert (select is_unknown from public.match_participants
          where match_id = current_setting('check.match_id')::bigint and slot = 'P2B'),
    'a re-publish keeps the unknown flag';
end $$;

-- the league: the slot keeps its line in the match, no row anywhere else
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
declare v_id bigint := current_setting('check.match_id')::bigint;
begin
  assert (select count(*) from public.match_box_score(v_id)) = 4, 'the box score keeps all four slots';
  assert (select player_id is null and display_name is null and fantasy = -1.0
          from public.match_box_score(v_id) where slot = 'P2B'),
    'the unknown slot keeps its stats in the match';
  assert (select count(*) from public.leaderboard()) = 3
     and not exists (select 1 from public.leaderboard() where display_name = 'Check Opp2'),
    'an unknown is not in the ranking';
  assert (select fantasy from public.leaderboard() where display_name = 'Check Ari') = 2.0,
    'the other players are untouched';
  assert (public.player_profile((select id from public.players where display_name = 'Check Opp2'))
          -> 'totals' ->> 'matches')::int = 0, 'the match left the old player''s history';
  update public.match_participants set is_unknown = true where match_id = v_id and slot = 'P1B';
  assert (select count(*) from public.match_participants where match_id = v_id and is_unknown) = 1,
    'a viewer cannot mark a slot unknown';
end $$;
reset role;

-- the admin's report of the match: four lines, the unknown one has no average
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', true);
do $$
declare r jsonb := public.match_report(current_setting('check.match_id')::bigint);
begin
  assert jsonb_array_length(r -> 'players') = 4, 'the report keeps all four slots';
  assert (select (x ->> 'fantasy')::numeric = -1.0 and x -> 'avg' = 'null'::jsonb and x -> 'player_id' = 'null'::jsonb
          from jsonb_array_elements(r -> 'players') x where x ->> 'slot' = 'P2B'),
    'the unknown slot has its line and nobody''s average';
end $$;

-- re-tag: the slot goes to a real player and the match flows into their totals
do $$
declare
  v_id   bigint := current_setting('check.match_id')::bigint;
  v_opp2 bigint := (select id from public.players where display_name = 'Check Opp2');
begin
  update public.match_participants set player_id = v_opp2, is_unknown = false
  where match_id = v_id and slot = 'P2B';
  assert (select player_id = v_opp2 and not is_unknown from public.match_participants
          where match_id = v_id and slot = 'P2B'), 're-tagged';
end $$;
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
begin
  assert (select count(*) from public.leaderboard()) = 4
     and (select fantasy from public.leaderboard() where display_name = 'Check Opp2') = -1.0
     and (select matches from public.leaderboard() where display_name = 'Check Opp2') = 1,
    'after the re-tag the player carries the match';
end $$;
reset role;

-- ── feedback: a member sends, reads their own; admins triage ─────────────
do $$
begin
  assert not has_table_privilege('anon', 'public.feedback', 'select'), 'anon must not read feedback';
  assert not has_function_privilege('anon', 'public.send_feedback(text,text,text,jsonb,text[])', 'execute'),
    'anon must not send feedback';
  assert not has_table_privilege('authenticated', 'public.feedback', 'insert')
     and not has_table_privilege('authenticated', 'public.feedback', 'delete'),
    'feedback rows come from send_feedback() only and are never deleted';
  assert has_table_privilege('service_role', 'public.feedback', 'select')
     and has_column_privilege('service_role', 'public.feedback', 'status', 'update'),
    'the laptop reads and closes reports';
  assert not has_column_privilege('authenticated', 'public.feedback', 'message', 'update'),
    'nobody rewrites a report';
end $$;

set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000a1', true);
do $$
declare v_id bigint;
begin
  insert into storage.objects (bucket_id, name)
  values ('feedback-media', '00000000-0000-0000-0000-0000000000a1/shot.jpg');
  begin
    insert into storage.objects (bucket_id, name)
    values ('feedback-media', '00000000-0000-0000-0000-0000000000b0/shot.jpg');
    assert false, 'an upload into another member''s folder must fail';
  exception when insufficient_privilege then null;
  end;
  begin
    insert into storage.objects (bucket_id, name)
    values ('match-media', '00000000-0000-0000-0000-0000000000a1/shot.jpg');
    assert false, 'a member must not upload into the match buckets';
  exception when insufficient_privilege then null;
  end;

  v_id := public.send_feedback('bug', '  the map is cut off  ', '/players/1', '{"viewport":"390x844"}',
                               array['00000000-0000-0000-0000-0000000000a1/shot.jpg']);
  assert (select message = 'the map is cut off' and status = 'open'
                 and user_id = '00000000-0000-0000-0000-0000000000a1'
          from public.feedback where id = v_id), 'the report is stored for its author, open';
  begin
    perform public.send_feedback('bug', 'x', null, '{}', array['00000000-0000-0000-0000-0000000000b0/shot.jpg']);
    assert false, 'a screenshot of another folder must be refused';
  exception when raise_exception then null;
  end;
  begin
    perform public.send_feedback('bug', 'x', null, '{}', array['00000000-0000-0000-0000-0000000000a1/missing.jpg']);
    assert false, 'a screenshot that was never uploaded must be refused';
  exception when raise_exception then null;
  end;
  begin
    perform public.send_feedback('spam', 'x');
    assert false, 'an unknown kind must be refused';
  exception when check_violation then null;
  end;
  begin
    perform public.send_feedback('bug', '   ');
    assert false, 'an empty report must be refused';
  exception when check_violation then null;
  end;
  begin
    insert into public.feedback (user_id, kind, message)
    values ('00000000-0000-0000-0000-0000000000a1', 'bug', 'direct');
    assert false, 'a direct insert must fail';
  exception when insufficient_privilege then null;
  end;
  update public.feedback set status = 'done' where id = v_id;
  assert (select status from public.feedback where id = v_id) = 'open', 'an author cannot close a report';

  -- 20 a day: 1 sent, 19 more pass, the next is refused
  for i in 1..19 loop
    perform public.send_feedback('suggestion', 'idea ' || i);
  end loop;
  begin
    perform public.send_feedback('suggestion', 'one too many');
    assert false, 'the daily limit must hold';
  exception when raise_exception then null;
  end;
  assert (select count(*) from public.feedback) = 20, 'a member reads their own reports';
end $$;
reset role;

set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
begin
  assert (select count(*) from public.feedback) = 0, 'a member does not read another member''s reports';
  assert (select count(*) from storage.objects where bucket_id = 'feedback-media') = 0,
    'nor their screenshots';
  update public.feedback set status = 'dismissed';
  assert public.send_feedback('suggestion', 'the limit is per member') is not null;
end $$;
reset role;

set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', true);
do $$
begin
  assert (select count(*) from public.feedback) = 21, 'an admin reads every report';
  assert (select count(*) from public.feedback where status <> 'open') = 0, 'a member closed nothing';
  assert (select count(*) from storage.objects where bucket_id = 'feedback-media') = 1,
    'an admin reads the screenshots';
  update public.feedback set status = 'done', admin_note = 'fixed' where kind = 'bug';
  assert (select count(*) from public.feedback where status = 'done' and admin_note = 'fixed') = 1,
    'an admin closes a report with a note';
  begin
    update public.feedback set message = 'rewritten' where kind = 'bug';
    assert false, 'not even an admin rewrites a report';
  exception when insufficient_privilege then null;
  end;
end $$;
reset role;

-- ── fantasy game (20261019100000): days, lineups, captain, tables ─────────
-- The published check match is the day's only fixture. Its fantasy now:
-- Ari 2.0, Joan 0.5, Opp1 1.0, Opp2 -1.0. Per 21 over each player's
-- published matches (Ari also has 0 in the 20-point second match): Ari 1.9,
-- Joan 5.25, Opp1 10.5, Opp2 -10.5 -> percentile prices 6.5, 8.5, 10.0, 5.0.
do $$
begin
  assert not has_function_privilege('anon', 'public.fantasy_match_day(bigint)', 'execute')
     and has_function_privilege('authenticated', 'public.fantasy_match_day(bigint)', 'execute')
     and has_function_privilege('authenticated', 'public.save_lineup(bigint,bigint[],bigint)', 'execute')
     and has_function_privilege('authenticated', 'public.fantasy_standings(text)', 'execute'),
    'members (never anon) read the game and save lineups';
  assert not has_function_privilege('authenticated', 'public.fantasy_player_points(bigint)', 'execute')
     and not has_function_privilege('authenticated', 'public.fantasy_lineup_scores(bigint)', 'execute')
     and not has_function_privilege('authenticated', 'public.fantasy_suggested_prices()', 'execute'),
    'the scoring helpers are internal';
  assert not has_table_privilege('authenticated', 'public.fantasy_lineups', 'insert, update, delete')
     and not has_table_privilege('authenticated', 'public.fantasy_prices', 'insert, update, delete'),
    'lineups and prices are written only through the RPCs';
  assert not has_column_privilege('authenticated', 'public.fantasy_match_days', 'status', 'update')
     and not has_column_privilege('authenticated', 'public.fantasy_fixtures', 'match_id', 'update')
     and not has_column_privilege('authenticated', 'public.fantasy_fixtures', 'fantasy_published', 'update')
     and has_column_privilege('authenticated', 'public.fantasy_fixtures', 'cancelled', 'update'),
    'opening, linking and publishing to fantasy go through the admin RPCs';
  assert has_table_privilege('service_role', 'public.fantasy_lineups', 'select'),
    'make backup exports the lineups';
end $$;

insert into public.players (display_name) values ('Check Five');

-- the admin builds a draft day: one fixture tomorrow, 2 + 2 players
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', true);
do $$
declare
  v_day bigint;
  v_fx  bigint;
begin
  insert into public.fantasy_match_days (season, name, budget) values ('S1', 'MD1', 25)
  returning id into v_day;
  insert into public.fantasy_fixtures (match_day_id, scheduled_at)
  values (v_day, now() + interval '1 day') returning id into v_fx;
  insert into public.fantasy_fixture_players (fixture_id, player_id, team)
  select v_fx, p.id, case when p.display_name in ('Check Ari', 'Check Joan') then 'A' else 'B' end
  from public.players p where p.display_name in ('Check Ari', 'Check Joan', 'Check Opp1', 'Check Opp2');
  begin
    insert into public.fantasy_fixture_players (fixture_id, player_id, team)
    values (v_fx, (select id from public.players where display_name = 'Check Five'), 'A');
    assert false, 'a side has two players';
  exception when raise_exception then null;
  end;
  begin
    update public.fantasy_fixtures set fantasy_published = true where id = v_fx;
    assert false, 'publishing to fantasy goes through the RPC';
  exception when insufficient_privilege then null;
  end;
  perform public.set_fantasy_price(v_day, (select id from public.players where display_name = 'Check Opp2'), 9.2);
  perform set_config('check.fantasy_day', v_day::text, true);
  perform set_config('check.fantasy_fixture', v_fx::text, true);
end $$;
reset role;

-- a member sees no draft
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
begin
  assert (select count(*) from public.fantasy_match_days) = 0
     and (select count(*) from public.fantasy_fixtures) = 0, 'a draft day is the admins''';
  assert public.fantasy_match_day(current_setting('check.fantasy_day')::bigint) is null,
    'the page of a draft day is empty for a member';
  begin
    insert into public.fantasy_match_days (season, name) values ('S1', 'mine');
    assert false, 'a member cannot create a match day';
  exception when insufficient_privilege then null;
  end;
end $$;
reset role;

-- the admin opens it: prices are snapshot, the override kept
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', true);
do $$
declare v_day bigint := current_setting('check.fantasy_day')::bigint;
begin
  perform public.open_fantasy_match_day(v_day);
  assert (select jsonb_object_agg(p.display_name, pr.price) from public.fantasy_prices pr
          join public.players p on p.id = pr.player_id where pr.match_day_id = v_day)
         = '{"Check Ari": 6.5, "Check Joan": 8.5, "Check Opp1": 10.0, "Check Opp2": 9.0}'::jsonb,
    'percentile prices, the override rounded to 0.5: '
      || (select jsonb_object_agg(p.display_name, pr.price)::text from public.fantasy_prices pr
          join public.players p on p.id = pr.player_id where pr.match_day_id = v_day);
  begin
    perform public.set_fantasy_price(v_day, (select id from public.players where display_name = 'Check Ari'), 5);
    assert false, 'prices never move while people pick';
  exception when raise_exception then null;
  end;
  begin
    update public.fantasy_match_days set budget = 99 where id = v_day;
    assert false, 'the rules of an open day are fixed';
  exception when raise_exception then null;
  end;
  begin
    delete from public.fantasy_fixtures where match_day_id = v_day;
    assert false, 'an open day''s fixture is cancelled, never deleted';
  exception when raise_exception then null;
  end;
end $$;
reset role;

-- Ari (a player account, no manager name yet) picks
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000a1', true);
do $$
declare
  v_day  bigint := current_setting('check.fantasy_day')::bigint;
  v_ari  bigint := (select id from public.players where display_name = 'Check Ari');
  v_joan bigint := (select id from public.players where display_name = 'Check Joan');
  v_opp1 bigint := (select id from public.players where display_name = 'Check Opp1');
  v_opp2 bigint := (select id from public.players where display_name = 'Check Opp2');
  v_five bigint := (select id from public.players where display_name = 'Check Five');
begin
  begin
    perform public.save_lineup(v_day, array[v_joan, v_opp1, v_opp2], v_opp1);
    assert false, 'a manager name comes first';
  exception when raise_exception then null;
  end;
  begin
    perform public.set_my_display_name('bob');
    assert false, 'manager names are unique, case-insensitively';
  exception when raise_exception then null;
  end;
  assert public.set_my_display_name('  Ari  ') = 'Ari', 'the name is trimmed';
  begin
    perform public.save_lineup(v_day, array[v_ari, v_opp1, v_opp2], v_ari);
    assert false, 'over budget (25.5 of 25)';
  exception when raise_exception then null;
  end;
  begin
    perform public.save_lineup(v_day, array[v_joan, v_opp1], v_joan);
    assert false, 'exactly squad_size players';
  exception when raise_exception then null;
  end;
  begin
    perform public.save_lineup(v_day, array[v_joan, v_joan, v_opp1], v_joan);
    assert false, 'a player only once';
  exception when raise_exception then null;
  end;
  begin
    perform public.save_lineup(v_day, array[v_joan, v_opp1, v_five], v_joan);
    assert false, 'only players of the day';
  exception when raise_exception then null;
  end;
  begin
    perform public.save_lineup(v_day, array[v_joan, v_opp1, v_opp2], v_ari);
    assert false, 'the captain is one of the picks';
  exception when raise_exception then null;
  end;
  begin
    insert into public.fantasy_lineups (match_day_id, user_id, player_ids, captain_player_id)
    values (v_day, auth.uid(), array[v_ari], v_ari);
    assert false, 'no lineup bypasses save_lineup';
  exception when insufficient_privilege then null;
  end;
  -- Ari 2.0 + Joan 0.5 x2 + Opp2 -1.0 = 2.0 once published to fantasy
  assert (public.save_lineup(v_day, array[v_ari, v_joan, v_opp2], v_joan) ->> 'cost')::numeric = 24.0,
    'a lineup at 24.0 of 25';
end $$;
reset role;

-- Bob picks; before the lock nobody sees another lineup
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
declare
  v_day bigint := current_setting('check.fantasy_day')::bigint;
  v_ari bigint := (select id from public.players where display_name = 'Check Ari');
  d     jsonb;
begin
  -- Ari 2.0 x2 + Joan 0.5 + Opp1 1.0 = 5.5 once published to fantasy (25.0 of 25)
  perform public.save_lineup(v_day,
    array[v_ari, (select id from public.players where display_name = 'Check Joan'),
          (select id from public.players where display_name = 'Check Opp1')], v_ari);
  assert (select count(*) from public.fantasy_lineups) = 1, 'a member reads only their own lineup';
  d := public.fantasy_match_day(v_day);
  assert d -> 'lineups' = 'null'::jsonb and (d ->> 'n_lineups')::int = 2
     and (d -> 'my_lineup' ->> 'captain')::bigint = v_ari
     and not (d -> 'day' ->> 'locked')::boolean,
    'before the lock: my lineup and a count, nobody else''s: ' || d::text;
  assert jsonb_array_length(d -> 'players') = 4 and jsonb_array_length(d -> 'fixtures') = 1,
    'the day page lists its fixture and its four players';
  assert (select count(*) from public.fantasy_standings('S1')) = 0, 'an unlocked day is in no table';
end $$;
reset role;

-- the first match starts (the clock is fixed inside the transaction: move it)
update public.fantasy_fixtures set scheduled_at = now() - interval '1 hour'
where id = current_setting('check.fantasy_fixture')::bigint;

set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
declare
  v_day bigint := current_setting('check.fantasy_day')::bigint;
  d     jsonb;
begin
  begin
    perform public.save_lineup(v_day, array[1, 2, 3]::bigint[], 1);
    assert false, 'a locked day takes no lineup';
  exception when raise_exception then null;
  end;
  d := public.fantasy_match_day(v_day);
  assert (d -> 'day' ->> 'locked')::boolean and not (d -> 'day' ->> 'final')::boolean
     and jsonb_array_length(d -> 'lineups') = 2,
    'after the lock every lineup is visible: ' || d::text;
  assert (select sum(total) from public.fantasy_standings('S1')) = 0,
    'nothing counts before a fixture is published to fantasy';
end $$;
reset role;

-- the admin links the fixture to the published match and publishes it to fantasy
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', true);
do $$
declare
  v_fx bigint := current_setting('check.fantasy_fixture')::bigint;
  r    jsonb;
begin
  begin
    insert into public.fantasy_fixtures (match_day_id, scheduled_at)
    values (current_setting('check.fantasy_day')::bigint, now() + interval '2 hours');
    assert false, 'a locked day takes no new fixture';
  exception when raise_exception then null;
  end;
  begin
    perform public.publish_fixture_to_fantasy(v_fx, true);
    assert false, 'a fixture without its match cannot be published to fantasy';
  exception when raise_exception then null;
  end;
  r := public.link_fixture_match(v_fx, current_setting('check.match_id')::bigint);
  assert r = '{"missing": [], "extra": []}'::jsonb, 'the match has the fixture''s four players: ' || r::text;
  perform public.publish_fixture_to_fantasy(v_fx, true);
end $$;
reset role;

set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
declare
  v_day bigint := current_setting('check.fantasy_day')::bigint;
  d     jsonb;
  s     record;
begin
  d := public.fantasy_match_day(v_day);
  assert (d -> 'day' ->> 'final')::boolean, 'every fixture published: the day is final';
  assert (d -> 'lineups' -> 0 ->> 'manager') = 'Bob' and (d -> 'lineups' -> 0 ->> 'points')::numeric = 5.5
     and (d -> 'lineups' -> 0 ->> 'is_me')::boolean
     and (d -> 'lineups' -> 1 ->> 'points')::numeric = 2.0 and (d -> 'lineups' -> 1 ->> 'rank')::int = 2,
    'the captain counts x2: ' || (d -> 'lineups')::text;
  select * into s from public.fantasy_standings('S1') where manager = 'Bob';
  assert s.total = 5.5 and s.day_wins = 1 and s.days_played = 1 and s.rank = 1 and s.is_me,
    'Bob leads the season';
  assert (select day_wins from public.fantasy_standings('S1') where manager = 'Ari') = 0, 'Ari won no day';
  assert (select leader = 'Bob' and leader_points = 5.5 and my_points = 5.5
          from public.fantasy_days('S1') where id = v_day), 'the day list names the leader';
  assert (select count(*) from public.fantasy_standings('other season')) = 0, 'a season filters';
end $$;
reset role;

-- points follow live: a rule edit rescores the game (dig 1 -> 2: Ari 3, Opp1 2)
update public.fantasy_rules set points = 2.0
where rule_key = 'dig' and ruleset_id = (select id from public.fantasy_rulesets where is_active);
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
begin
  assert (select total from public.fantasy_standings('S1') where manager = 'Bob') = 8.5,
    'a rule edit rescores past days (3 x2 + 0.5 + 2)';
end $$;
reset role;
update public.fantasy_rules set points = 1.0
where rule_key = 'dig' and ruleset_id = (select id from public.fantasy_rulesets where is_active);

-- a hidden match scores nothing in the game
do $$
begin
  update public.matches set status = 'hidden' where id = current_setting('check.match_id')::bigint;
  assert (select sum(points) from public.fantasy_player_points(current_setting('check.fantasy_day')::bigint))
         is null, 'a hidden match counts for nobody';
  update public.matches set status = 'published' where id = current_setting('check.match_id')::bigint;
end $$;

-- a match with history cannot be hard-deleted (hide it instead)
do $$
begin
  begin
    delete from public.matches where match_key = '20260920_1830_check_court';
    assert false, 'hard delete of a match with history must fail';
  exception when foreign_key_violation then
    null;
  end;
end $$;

select 'RLS SMOKE: ALL CHECKS PASSED' as result;
rollback;
