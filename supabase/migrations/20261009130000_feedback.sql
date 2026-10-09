-- Bug reports and suggestions from the members (the "Feedback" button).
--
-- A member sends a report through send_feedback() -- the only way a row gets
-- in -- with up to three screenshots uploaded first to the private
-- `feedback-media` bucket under their own folder (<user id>/<file>). They read
-- their own reports (status + the admin's note); admins read all of them and
-- set status / note; the laptop (`make feedback`, secret key) pulls the open
-- ones for a working session. `anon` gets nothing.

create table public.feedback (
  id          bigint generated always as identity primary key,
  user_id     uuid not null references public.profiles (user_id) on delete cascade,
  kind        text not null check (kind in ('bug', 'suggestion')),
  message     text not null check (length(btrim(message)) between 1 and 4000),
  -- where the report was sent from: the route, and screen / browser / build
  page        text check (length(page) <= 300),
  context     jsonb not null default '{}'::jsonb check (length(context::text) <= 2000),
  screenshots text[] not null default '{}' check (cardinality(screenshots) <= 3),
  status      text not null default 'open' check (status in ('open', 'done', 'dismissed')),
  admin_note  text check (length(admin_note) <= 2000),
  created_at  timestamptz not null default now()
);
create index feedback_status_idx on public.feedback (status, created_at desc);
create index feedback_user_idx   on public.feedback (user_id, created_at desc);

alter table public.feedback enable row level security;
create policy own_or_admin_read on public.feedback for select to authenticated
  using (user_id = auth.uid() or public.is_admin());
create policy admin_update on public.feedback for update to authenticated
  using (public.is_admin()) with check (public.is_admin());

-- No INSERT / DELETE through the API: rows come from send_feedback(), and a
-- report is closed (done / dismissed), never removed.
grant select on public.feedback to authenticated, service_role;
grant update (status, admin_note) on public.feedback to authenticated, service_role;

-- ════════════════════════════════════════════════════════════════════════
-- screenshots
-- ════════════════════════════════════════════════════════════════════════
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('feedback-media', 'feedback-media', false, 1048576,
        array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do nothing;

-- At most 30 uploads a day per member (the web app sends <= 3 per report,
-- downscaled to a few hundred kB): a logged-in account cannot fill the bucket.
create function public.feedback_upload_allowed() returns boolean
language sql stable security definer set search_path = public as $$
  select count(*) < 30 from storage.objects
  where bucket_id = 'feedback-media'
    and split_part(name, '/', 1) = auth.uid()::text
    and created_at > now() - interval '1 day';
$$;

create policy "members add feedback screenshots" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'feedback-media'
              and split_part(name, '/', 1) = auth.uid()::text
              and public.feedback_upload_allowed());
create policy "feedback screenshots: author and admins" on storage.objects
  for select to authenticated
  using (bucket_id = 'feedback-media'
         and (split_part(name, '/', 1) = auth.uid()::text or public.is_admin()));

-- ════════════════════════════════════════════════════════════════════════
-- send_feedback(): the one way in. The author is the caller, a screenshot
-- must be an uploaded file of the caller's own folder, 20 reports a day.
-- ════════════════════════════════════════════════════════════════════════
create function public.send_feedback(
  p_kind text, p_message text, p_page text default null,
  p_context jsonb default '{}'::jsonb, p_screenshots text[] default '{}')
returns bigint
language plpgsql security definer set search_path = public as $$
declare
  v_uid   uuid := auth.uid();
  v_shots text[] := coalesce(p_screenshots, '{}');
  v_id    bigint;
begin
  if v_uid is null then
    raise exception 'not logged in' using errcode = '42501';
  end if;
  if (select count(*) from public.feedback
      where user_id = v_uid and created_at > now() - interval '1 day') >= 20 then
    raise exception 'feedback limit reached: try again tomorrow';
  end if;
  if exists (select 1 from unnest(v_shots) s
             where split_part(s, '/', 1) <> v_uid::text
                or not exists (select 1 from storage.objects o
                               where o.bucket_id = 'feedback-media' and o.name = s)) then
    raise exception 'screenshot not found';
  end if;
  insert into public.feedback (user_id, kind, message, page, context, screenshots)
  values (v_uid, p_kind, btrim(p_message), p_page, coalesce(p_context, '{}'::jsonb), v_shots)
  returning id into v_id;
  return v_id;
end $$;

revoke all on function public.feedback_upload_allowed() from public, anon, authenticated, service_role;
revoke all on function public.send_feedback(text, text, text, jsonb, text[])
  from public, anon, authenticated, service_role;
grant execute on function public.feedback_upload_allowed() to authenticated;
grant execute on function public.send_feedback(text, text, text, jsonb, text[]) to authenticated;
