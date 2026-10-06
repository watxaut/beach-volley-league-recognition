-- Private storage buckets:
--   match-bundles : one JSON bundle per publish (content-addressed path), the
--                   reproducible copy of every pipeline-owned row
--   match-media   : slot thumbnails for the admin assignment screen
-- The publisher writes with the secret key (bypasses RLS); admins read via
-- short-lived signed URLs, which need the select policy below.
insert into storage.buckets (id, name, public, file_size_limit)
values ('match-bundles', 'match-bundles', false, 20971520),
       ('match-media',   'match-media',   false, 5242880)
on conflict (id) do nothing;

create policy "admins read match buckets" on storage.objects
  for select to authenticated
  using (bucket_id in ('match-bundles', 'match-media') and public.is_admin());
