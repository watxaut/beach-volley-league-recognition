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
                         'action', 'serve', 'observed', true),
      jsonb_build_object('point_no', 1, 'seq', 1, 'frame', 247, 'slot', 'P1A', 'team', 'A',
                         'action', 'dig', 'observed', true, 'own_y_m', 3.5),
      jsonb_build_object('point_no', 1, 'seq', 2, 'frame', 304, 'slot', 'P2A', 'team', 'A',
                         'action', 'set', 'observed', true, 'is_assist', true),
      jsonb_build_object('point_no', 1, 'seq', 3, 'frame', 345, 'slot', 'P1A', 'team', 'A',
                         'action', 'spike', 'outcome', 'kill', 'observed', true,
                         'attack_zone', 2, 'landing_x_m', 3.1, 'landing_y_m', 12.0,
                         'landing_in', true, 'landing_source', 'ball_death',
                         'landing_err_x_m', 0.3, 'landing_err_y_m', 0.9,
                         'landing_result', 'kill'),
      jsonb_build_object('point_no', 1, 'seq', 4, 'frame', 360, 'slot', null, 'team', 'B',
                         'action', 'dig', 'observed', false),
      jsonb_build_object('point_no', 2, 'seq', 0, 'frame', 811, 'slot', 'P1A', 'team', 'A',
                         'action', 'serve', 'observed', true))
    || case when p_second_rally then jsonb_build_array(
      jsonb_build_object('point_no', 2, 'seq', 1, 'frame', 840, 'slot', 'P1B', 'team', 'B',
                         'action', 'dig', 'observed', true),
      jsonb_build_object('point_no', 2, 'seq', 2, 'frame', 870, 'slot', 'P2B', 'team', 'B',
                         'action', 'set', 'outcome', 'error', 'observed', true))
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
  assert not has_function_privilege('anon', 'public.leaderboard(text)', 'execute'),
    'anon must not read the leaderboard';
  assert has_function_privilege('anon', 'public.ping()', 'execute'), 'anon must reach ping()';

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

update public.matches set status = 'published' where match_key = '20260920_1830_check_court';

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
  assert not public.set_my_privacy(true), 'bob has no player to change';
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
  assert public.set_my_privacy(true), 'ari flips her privacy';
end $$;
reset role;

-- bob again: ari's analytics are now public; the touches are still not
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
begin
  assert (public.player_profile((select id from public.players where display_name = 'Check Ari'))
          ->> 'can_see_analytics')::boolean, 'opted-in analytics are visible to members';
  assert (select count(*) from public.actions) = 0, 'touches stay participant-only';
end $$;
reset role;

-- admin: detail_public opens the play-by-play to everyone
update public.matches set detail_public = true where match_key = '20260920_1830_check_court';
set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b0', true);
do $$
begin
  assert (select count(*) from public.actions) = 8, 'detail_public opens the touches';
end $$;
reset role;

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
