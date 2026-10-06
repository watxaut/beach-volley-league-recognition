-- Local development seed (`supabase db reset` loads it after the migrations;
-- it is never pushed to the hosted project). Players only: real match data
-- arrives through `make publish` against the local stack.
insert into public.players (display_name) values
  ('Ari'), ('Joan'), ('Opponent 1'), ('Opponent 2');
