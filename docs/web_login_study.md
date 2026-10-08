# Web login: staying logged in with fewer code mails (study, session #94)

**Asked (owner, 2026-10-08):** the 8-digit email code works, but on 2026-10-07
it took three logins (three mails), and code mails pile up in the inbox. Could a
login last 2–7 days or longer (cookies?), as far as security allows? Study the
simple options and their caveats. **No code was changed.** Everything below
comes from reading this repo, the Supabase Auth source (`supabase/auth` master,
read 2026-10-08) and the sources at the end. Nothing was run against the hosted
project.

## 1. Logins already persist (owner check: no code asked ~20 h later)

* `webapp/src/lib/api.ts` creates the client with `persistSession: true,
  autoRefreshToken: true`. supabase-js keeps the session in the browser's
  `localStorage`. The access token lasts 1 h (`jwt_expiry = 3600`) and is
  renewed in the background with a single-use refresh token, which **never
  expires** by default. A login therefore lasts until one of these happens:
  a sign-out, a refresh token reused outside the reuse window, or the browser
  deleting the site's storage.
* The owner confirmed it on 2026-10-08: the site opened without a code about
  20 h after the last login.
* So "make it last 2–7 days" already holds, and the login actually lasts
  longer: today it has **no limit at all**. The three logins on 10-07 came from
  something that ended or bypassed the session, not from a short expiry.

## 2. Why 2026-10-07 took three codes (likely causes, can't tell from here)

1. **Different web addresses.** Storage is per address, so `127.0.0.1:5173`,
   `<name>.<account>.workers.dev` and any Cloudflare preview/version URL each
   need their own login. 10-07 was deploy-fix day (`324dba6`, 09:25).
2. **The email link opened in another browser.** Examples: Gmail's built-in
   browser, or a *Site URL* still set to `127.0.0.1` (deploy guide, troubleshooting
   table). The session then lives in that browser, not in the one you use.
3. **"Log out" anywhere logs you out everywhere.** `Settings.tsx` calls
   `sb.auth.signOut()`, and its default scope in supabase-js is **`global`**.
   That revokes every session of the account on every device.
4. A new device, a private window, or a second account (admin and player
   tests). Each one costs one code, whatever login method is used.

From 10-09 on, cause 1 and cause 3 stop once there is one URL and a local
logout. Causes 2 and 4 are what a second login method removes.

## 3. What security says about the length

* NIST SP 800-63B-4: an email code is a single factor, which puts this app at
  **AAL1**. For AAL1 an overall reauthentication timeout **SHALL** be set and
  **SHOULD be ≤ 30 days**. An inactivity timeout MAY be added.
* The league's data is low-risk: match stats, emails and privacy tiers. There
  are no payments and no sensitive personal data. The bigger risk is a lost or
  shared phone, or a stolen token (XSS). The CSP in `webapp/public/_headers`
  is the main defence against token theft. Admin accounts are worth more.
* **Recommendation: 30 days absolute.** This means one re-login a month per
  device. A 2–7 day limit is stricter than this data needs and brings back the
  mail-every-few-days problem. Today's setting is unlimited, which falls below
  the NIST SHOULD.
* **How to enforce it.** Supabase's *Time-box user sessions* and *Inactivity
  timeout* settings are paid-plan features according to third-party sources.
  Supabase's own page could not be opened from this container. On the free
  plan the equivalent is a `pg_cron` job that runs
  `delete from auth.sessions where created_at < now() - interval '30 days'`.
  The next refresh then fails and the client logs out within ≤ 1 h.
  **Untested:** prove it on the local stack first.
* A limit kept in the browser (a timestamp in `localStorage`) is a
  convenience, not a control: a stolen refresh token ignores it.
* **Safari caveat (iPhone):** WebKit deletes a site's `localStorage` (and our
  session with it) after **7 days of Safari use without an interaction** on
  the site. An iPhone player who opens the site only after the weekly match
  can be logged out between visits. Sites added to the Home Screen keep their
  own counter.

## 4. The CAPTCHA lock decides what is "simple" (verified in the Auth source)

Deploy step 2.9 turns Auth's CAPTCHA on with a secret no page has a widget for.
In `internal/api/api.go` + `middleware.go` (`verifyCaptcha`,
`isIgnoreCaptchaRoute`) that check guards these endpoints:
`/signup`, `/recover`, `/resend`, `/magiclink`, `/otp`, `/sso`, **`/token`**
(except the grants `refresh_token`, `pkce` and `id_token`), and
**`/passkeys/authentication/options`**. Any request that carries the service
key skips it. Consequences:

| Method | Passes the lock? |
|---|---|
| Session refresh (staying logged in) | yes (`refresh_token` exempt) |
| Google / OAuth sign-in (`/authorize` → callback → `pkce`/implicit) | yes |
| Password sign-in (`/token?grant_type=password`) | **no**: needs a broker function, like the code request |
| Passkey sign-in (`/passkeys/authentication/options`) | **no**: the options step needs a broker; `/verify` is open |

OAuth with sign-ups OFF (`external.go`): an identity whose verified email
matches an invited account is **linked** to it, and a new email is refused
("Signups not allowed"). The invite list stays the membership list.

## 5. Options

| | What | Mails | Effort | Verdict |
|---|---|---|---|---|
| **A** | Keep the code. Fix what logs people out and set a 30-day limit | 1 per new browser/device (+ iPhone 7-day wipe) | ~1 h | **do now** |
| **B** | Add *Sign in with Google* | 0 for Google-account players | low, no server code | good, simplest add-on |
| **C** | Add **passkeys** (Face ID / fingerprint, enrolled after one code login) | 0 after the first login | medium | **best second method** |
| D | Add email + password | 0 | medium + risk | no |
| E | Own HttpOnly cookie session (a Worker in front of Supabase) | as A | high | not now |

**A. Keep the code, stop the accidental logouts.**
* Change Log out to `signOut({ scope: 'local' })` and add a separate
  "Log out on all devices" button (`global`) for a lost phone.
* Use one public URL: decide now whether you will have a custom domain (this
  matters for C).
* Say "You stay logged in on this device" on the login page.
* Set the 30-day limit (§3).
* Inbox clutter: all code mails share the subject *Your beach volley login
  code*, so one Gmail filter (that subject → skip inbox, or delete after
  reading) cleans it up.
* What A does not fix: one mail per new browser or device, and the iPhone
  7-day wipe.

**B. Google sign-in.**
* Setup: a Google Cloud OAuth client (basic scopes, no review), Supabase
  provider Google, and one `signInWithOAuth({ provider: 'google' })` button.
  The lock lets it through and sign-ups stay off (§4). The design doc (§Auth)
  already listed it as an option.
* Caveats:
  - It works only when the invited address is the player's Google account.
  - Google's consent screen names `<ref>.supabase.co` unless you pay for
    Supabase's custom auth domain add-on.
  - Google sees every login.
  - On iPhone Safari many people aren't signed in to Google on the web, so a
    login there can mean typing a Google password and 2FA, which is worse
    than a code.
  - It breaks the "only email" check in deploy step 2.4 and the AGENTS §13
    text, so it needs an owner decision.

**C. Passkeys.**
* Flow: the first login uses the code (or the invite link). Then Settings →
  *Add a passkey*. After that, *Log in with passkey* means Face ID or a
  fingerprint and no mail. The passkey syncs through iCloud Keychain or
  Google Password Manager, so a player's other devices skip the code too.
  This also covers the Safari 7-day wipe and every later 30-day re-login with
  one tap, and it is phishing-resistant.
* Supabase support: in **beta since 2026-05-28**. supabase-js needs
  `auth: { experimental: { passkey: true } }`, and the API may change.
  Sign-in uses discoverable credentials (no email typed). Registration needs
  a logged-in, confirmed user. The local CLI `config.toml` already has the
  `[auth.passkey]` / `[auth.webauthn]` blocks.
* Caveats:
  1. The lock blocks the options step, so it needs a small broker (an edge
     function with the service key, IP-limited in the database like
     `login_code_gate`). The helper in supabase-js can't be used as-is for
     that step.
  2. A passkey is bound to its domain (`rp_id`). Moving from `workers.dev` to
     a custom domain later orphans every passkey, so pick the final domain
     **before** players enrol.
  3. A published finding (ANT-2026-0JJXMV3G, static analysis) says passkey
     registration has no step-up: a stolen access token could enrol an
     attacker's passkey that outlives a logout. Keep the CSP strict, check the
     fix status before enabling, and give admins a way to list or delete
     passkeys (Auth has admin endpoints for it).
  4. Mixed ecosystems (an iPhone plus a Windows PC) fall back to the QR flow
     or the code. The code stays as the recovery path.

**D. Passwords: not recommended.**
* The lock blocks the password grant, so a broker would handle every
  password, and the brute-force limits would be ours to write.
* Leaked-password checks are a paid feature.
* Reused and forgotten passwords end in a code mail anyway.

**E. "On cookies": not now.**
* Moving the token into a cookie the page's scripts can still read gains
  nothing over `localStorage`.
* The real version is an HttpOnly cookie set by our own server (a Cloudflare
  Worker proxying Auth). It would make the token unreadable to scripts and
  survive Safari's wipe.
* But it means a server of ours (the design says none), CSRF handling, and
  proxying every auth call. That is not "rather simple".

## 6. Recommendation and owner decisions

1. **Now: A.** Decide the session limit (**30 days**, recommended), use one
   canonical URL, and make logout local plus "all devices".
2. **Next: C (passkeys)**, once the domain is final. It removes the mail for
   returning players on every device in their ecosystem and on iPhone. Pick
   **B** instead if you want zero server code and the players are on Gmail.
   B and C can coexist.
3. Owner decisions, in order:
   * **(a)** Session limit: none, **30 days**, or 7 days. Free plan →
     `pg_cron`; paid plan → time-box setting.
   * **(b)** Final domain: `workers.dev` or a custom domain. It must be
     settled before C.
   * **(c)** Second method: **passkeys**, Google, or none.

## Sources

* Supabase Auth source, `internal/api/api.go`, `middleware.go`, `external.go`,
  `internal/models/linking.go` (github.com/supabase/auth, master, 2026-10-08).
* Supabase docs: sessions (`/docs/guides/auth/sessions`), sign-out scopes
  (`/docs/guides/auth/signout`), passkeys (`/docs/guides/auth/passkeys`),
  passkeys beta changelog (`/changelog/46458-passkeys-for-supabase-auth-beta`),
  auth hooks (`/docs/guides/auth/auth-hooks`).
* NIST SP 800-63B-4 §AAL (pages.nist.gov/800-63-4/sp800-63b/aal).
* WebKit storage policy and the 7-day cap on script-writable storage
  (webkit.org, "Updates to Storage Policy"; WebKit bug 237350).
* ANT-2026-0JJXMV3G (red.anthropic.com/2026/cvd/findings/ANT-2026-0JJXMV3G).
