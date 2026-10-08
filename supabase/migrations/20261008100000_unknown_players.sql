-- Unknown players: a slot the admin marks "not someone in the league".
--
-- The opponent (or a guest) has no `players` row and should not get one: a
-- placeholder player would show up in the leaderboard and on profile pages.
-- So "unknown" is a state of the SLOT, not a person:
--
--   * `match_participants.is_unknown = true`, `player_id` stays NULL.
--   * In-match views key on the slot (box score, match report, play-by-play)
--     and keep the slot's stats.
--   * Every cross-match view (leaderboard, player_profile, window_matches,
--     the report's "vs avg") joins `players` by `player_id`, so an unknown is
--     left out BY CONSTRUCTION -- no function needs a filter, and none may
--     aggregate by slot across matches.
--   * Re-tag = give the slot a real player (player_id set, is_unknown false).
--     Stats are views over the slot, so the match flows into that player's
--     totals at once.
--
-- Ownership: admin-owned like `player_id`. The publisher's upsert only sets
-- `thumb_path`, so a republish keeps the flag. A slot is "decided" when it has
-- a player OR is unknown; only an undecided slot blocks publishing (web app).

alter table public.match_participants
  add column is_unknown boolean not null default false;

alter table public.match_participants
  add constraint match_participants_unknown_has_no_player
  check (not (is_unknown and player_id is not null));

-- Stamp who/when on EITHER change (marking unknown and re-tagging are both
-- admin decisions about the slot).
create or replace function public.stamp_assignment() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if new.player_id is distinct from old.player_id
     or new.is_unknown is distinct from old.is_unknown then
    new.assigned_by := auth.uid();
    new.assigned_at := now();
  end if;
  return new;
end $$;

-- Same column-level rule as player_id (20261007120000_explicit_grants.sql);
-- the admin_update policy decides who.
grant update (is_unknown) on public.match_participants to authenticated;
