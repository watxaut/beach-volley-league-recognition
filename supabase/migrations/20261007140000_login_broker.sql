-- Login codes without an oracle (security review, 2026-10-06).
--
-- The public auth endpoint answers differently for an invited email (200) and
-- an unknown one (422), so anyone could test who is in the league, and anyone
-- who knew a member's address could keep the mailer busy. Supabase Auth cannot
-- be told to answer both the same, so the web app no longer calls it for the
-- code request:
--
--   web app -> edge function `request-login-code` (always the same answer)
--           -> login_code_gate()   this file: rate limits + "is it an account?"
--           -> Supabase Auth /otp  with the service key, only for a real account
--
-- and the hosted project turns CAPTCHA protection on with a secret nobody
-- holds a widget for (docs/deploy_web_platform.md step 2.9): Auth then refuses
-- every public request that could send a mail, known address or not, while
-- requests carrying the service key skip the check. The code itself is still
-- verified by Auth directly (it answers a wrong code and an unknown address
-- alike).
--
-- The gate is only reachable with the service key (the edge function's), so it
-- may return the truth: forward or not.

-- One row per request that was let through the limits. It holds a hash of the
-- address, never the address: the log must not become a list of who tried.
-- Rows older than a day are dropped by the gate itself.
create table public.login_code_requests (
  id           bigint generated always as identity primary key,
  email_sha256 text        not null,
  ip           text        not null,
  requested_at timestamptz not null default now()
);
create index login_code_requests_email_idx on public.login_code_requests (email_sha256, requested_at);
create index login_code_requests_ip_idx    on public.login_code_requests (ip, requested_at);
create index login_code_requests_at_idx    on public.login_code_requests (requested_at);
-- RLS on, no policy, no grant: only the gate (definer) touches it.
alter table public.login_code_requests enable row level security;

-- True when this request should become an email. The limits count every
-- address the same way, member or not:
--   per address  one request a minute, five an hour (a code lasts an hour)
--   per IP       thirty an hour (a whole group logging in from one wifi)
-- Only an account that accepted its invite is forwarded: Auth refuses the
-- others anyway, and their requests must not use up its own request limit,
-- which all forwarded requests share (they come from one address).
create function public.login_code_gate(p_email text, p_ip text) returns boolean
language plpgsql security definer set search_path = public as $$
declare
  v_email text := lower(btrim(coalesce(p_email, '')));
  v_ip    text := coalesce(nullif(btrim(p_ip), ''), 'unknown');
  v_hash  text;
begin
  if length(v_email) > 254 or v_email !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' then
    return false;
  end if;
  v_hash := encode(sha256(convert_to(v_email, 'UTF8')), 'hex');
  -- check + insert as one step per address
  perform pg_advisory_xact_lock(hashtext('login_code:' || v_hash));

  delete from public.login_code_requests where requested_at < now() - interval '1 day';

  if exists (select 1 from public.login_code_requests r
             where r.email_sha256 = v_hash and r.requested_at > now() - interval '60 seconds')
     or (select count(*) from public.login_code_requests r
         where r.email_sha256 = v_hash and r.requested_at > now() - interval '1 hour') >= 5
     or (select count(*) from public.login_code_requests r
         where r.ip = v_ip and r.requested_at > now() - interval '1 hour') >= 30 then
    return false;
  end if;
  insert into public.login_code_requests (email_sha256, ip) values (v_hash, v_ip);

  return exists (select 1 from auth.users u
                 where u.email = v_email and u.email_confirmed_at is not null);
end $$;

revoke execute on function public.login_code_gate(text, text) from public, anon, authenticated;
grant  execute on function public.login_code_gate(text, text) to service_role;
