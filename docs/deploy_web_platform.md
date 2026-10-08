# Deploying the web platform: owner checklist

Everything that can be built without your accounts is in the repo:
`supabase/` (schema, access rules, email templates), `src/publish/`
(publisher, Drive inbox runner, backup), `webapp/` (the site),
`ops/launchd/` (laptop automation) and `.github/workflows/` (keep-alive and
web CI). What is left needs your logins and clicks. Do the steps in order.
Each one ends with a **check** so you know it worked before moving on.

Time: about 2 hours the first time. Cost: €0 on free tiers. Google One
100 GB (~€2/month) becomes worth it after ~10 matches in Drive.

Design and rationale: `docs/web_platform_design.md`.

---

## 0. Install the tools on the M3 (10 min)

```bash
brew install supabase/tap/supabase rclone node libpq
brew link --force libpq          # gives you `psql` (optional checks)
```

Accounts you need: Supabase (sign in with GitHub), Cloudflare (free), the
Google account that will own the Drive folders, and GitHub (this repo).

---

## 1. Merge the code (5 min)

Open a pull request from `claude/dreamy-fermi-a6xn2n` into `main` and merge
it, or ask me to open the PR. Cloudflare and the prod worktree below both
deploy `main`.

**Check:** `main` contains `supabase/migrations/20261006120000_init.sql`.

---

## 2. Supabase project (25 min)

1. **Create the project.** supabase.com → New project. Name
   `beach-volley-league`, region **EU (Frankfurt or Paris)**. Generate a
   strong database password and keep it in your password manager. If the
   form offers *Automatically expose new tables* (Data API), leave it **off**: `20261007120000_explicit_grants.sql`
   grants exactly what the
   site and the laptop need, and nothing to visitors who are not logged in.
2. **Copy three values** from Project Settings → API Keys:
    - Project URL: `https://<ref>.supabase.co`
    - **Publishable** key (`sb_publishable_…`, or the legacy `anon` key). Goes
      to the website.
    - **Secret** key (`sb_secret_…`, or the legacy `service_role` key). Goes
      to the laptop only. Create one just for it (*New secret key*, name it
      `laptop-publisher`) instead of using the default: if the laptop is ever
      lost you revoke that one key and nothing else changes.
3. **Create the schema.** In this repo:
   ```bash
   supabase login
   supabase link --project-ref <ref>      # asks for the DB password
   supabase db push                       # applies every file in supabase/migrations/
   ```
   **Check:** Table Editor shows `matches`, `points`, `actions`,
   `fantasy_rules` (8 G1 rows), …; Storage shows two **private** buckets,
   `match-bundles` and `match-media`.
4. **Lock the login down.** Authentication → Sign In / Providers:
    - *Allow new users to sign up* = **OFF**. Keep the Email provider
      enabled; every other provider and *Anonymous sign-ins* stay off. The
      database treats every logged-in account as a league member, so this
      switch IS the membership list.
    - Email provider → *Email OTP Length* = **8**. The emailed code is the
      only login factor; 8 digits are 100× harder to guess than 6 (the login
      page takes either).
    - Leave *Email OTP Expiration* at **3600** seconds. Do not shorten it: the
      invite link expires with it, and with sign-ups off an invited player who
      missed the link cannot ask for a code. You send the invite again.

   **Check** (`supabase/config.toml` only configures the LOCAL stack, so this
   is the proof for the real project):
   ```bash
   curl -s "https://<ref>.supabase.co/auth/v1/settings" -H "apikey: <publishable key>"
   ```
   It must show `"disable_signup":true`, `"anonymous_users":false` and, under
   `external`, only `"email":true`.
5. **Set up custom SMTP.** Supabase's built-in mailer is for testing and
   will not deliver invites to your players. Authentication → Emails →
   SMTP Settings → enable. Choose one:
    - **Gmail** (no domain needed, ~500 mails/day): first enable 2-Step
      Verification on the Google account, then create an *App password*
      (myaccount.google.com → Security → App passwords). Host
      `smtp.gmail.com`, port `587`, user = the Gmail address, password =
      the app password, sender = the same address, sender name `Beach League`.
    - **Resend / Brevo**, if you own a domain.

   Then Authentication → Rate Limits: raise *emails per hour* to ~30.
6. **Email templates.** Authentication → Emails → Templates.
    - **Magic Link:** subject `Your beach volley login code`, body = the
      contents of `supabase/templates/magic_link.html`. It must contain
      `{{ .Token }}`, which is the code the login page asks for.
    - **Invite user:** body = `supabase/templates/invite.html`.
7. **URLs.** Authentication → URL Configuration. Leave it until step 4 gives
   you the site URL, then set *Site URL* = `https://<name>.<account>.workers.dev`
   and add these *Redirect URLs*: `https://<name>.<account>.workers.dev/**` and
   `http://127.0.0.1:5173/**`.
8. **(Optional) Behaviour check against the real project.** Dashboard →
   Connect → *Session pooler* URI, then:
   ```bash
   psql "<session-pooler-uri>" -v ON_ERROR_STOP=1 -f supabase/checks/rls_smoke.sql
   ```
   Expect `RLS SMOKE: ALL CHECKS PASSED`. The script runs in one transaction
   and **rolls back**, so it leaves nothing behind. Run it before the first
   `make publish`: it counts its own fixtures, so a match that is already
   published makes it fail. If your project refuses
   the test inserts into `auth.users`, run the same check on the local
   stack instead (Docker Desktop, then `supabase start` and
   `make schema-check`).

9. **One answer for every email (login function + lock).** Supabase Auth's
   own "send me a code" endpoint tells an invited address from an unknown
   one, and lets anyone who knows a member's address keep the mailer busy.
   Two parts close that. Do both, the function first:
    - **Deploy the login function.** It gives every address the same answer
      and asks the database whether a mail really goes out (one request a
      minute and five an hour per address, thirty an hour per IP):
      ```bash
      supabase functions deploy request-login-code
      ```
    - **Lock Auth's public endpoints.** Cloudflare dashboard → Turnstile → *Add widget* (name `auth-lock`, hostname:
      your site's, mode *Managed*).
      Copy its **secret key** into Supabase → Authentication → Attack
      Protection → *Enable Captcha protection* (provider: Turnstile). Never
      put the widget's *site key* on any page: with no widget anywhere nobody
      can produce a valid token, so Auth refuses every public request that
      could send a mail. The login function's requests carry the service key
      and skip the check; so do the dashboard's (invites).

   **Check** (repeat after step 5, once your own account exists):
   ```bash
   URL=https://<ref>.supabase.co; KEY=<publishable key>
   for e in <your email> nobody@example.com; do
     curl -s -X POST "$URL/functions/v1/request-login-code" -H "apikey: $KEY" \
          -H 'Content-Type: application/json' -d "{\"email\":\"$e\"}"; echo
   done      # {"ok":true} both times; a code arrives for yours only
   curl -s -X POST "$URL/auth/v1/otp" -H "apikey: $KEY" -H 'Content-Type: application/json' \
        -d '{"email":"<your email>","create_user":false}'      # ..."captcha_failed"...
   ```
   Until both parts are done the site still works: it falls back to Auth's
   own endpoint, with the old difference between known and unknown emails.

---

## 3. The processing laptop (30 min)

1. **A clean "prod" checkout.** Published numbers must come from committed
   code (AGENTS.md §8). The publisher refuses a dirty tree.
   ```bash
   cd <path to repo>          # your dev checkout
   git fetch origin && git worktree add <path to prod repo> origin/main
   cd <path to prod repo>
   ln -s <path to repo>/models models
   ln -s <path to repo>/output output
   ln -s <path to repo>/data data
   # resources/ is tracked in git (one script), so link the videos in, not the folder:
   find <path to repo>/resources -maxdepth 1 \
        \( -iname '*.mp4' -o -iname '*.mov' \) -exec ln -sf {} resources/ \;
   # Clone the EXACT packages of your working venv/: it has ultralytics 8.3.169,
   # the only release the detector fast path is verified on (AGENTS §12) and
   # the one every GT number was measured with. A fresh `pip install -e .`
   # would resolve a newer one (uv.lock says 8.4.x).
   <path to repo>/venv/bin/pip freeze --exclude-editable > /tmp/volley-req.txt
   "$(<path to repo>/venv/bin/python -c 'import sys; print(sys.executable)')" -m venv venv
   source venv/bin/activate
   pip install -r /tmp/volley-req.txt && pip install --no-deps -e .
   python -c "import ultralytics; print(ultralytics.__version__)"   # must print 8.3.169
   ```
   Every command below assumes `cd <path to prod repo> && source venv/bin/activate`.
   To update it later: `git -C <path to prod repo> pull --ff-only` (or
   `git checkout origin/main` in a detached worktree).
2. **Credentials.**
   ```bash
   cp .env.publish.example .env.publish && chmod 600 .env.publish
   ```
   Fill in `SUPABASE_URL` and `SUPABASE_SECRET_KEY`. The `chmod` is not
   optional: `make publish` and `make backup` refuse a `.env.publish` that
   other users of the Mac can read.
3. **Publish the match you already have.** Its name lacks the time, so pass
   the full key once. Get the recording time from the video:
   ```bash
   ffprobe -v quiet -show_entries format_tags=creation_time -of default=nw=1 resources/full_videos/20260920_match_ari_joan_lost.mp4
   make postrun OUTPUT_DIR=output/postrun/20260920_match      # refresh (adds the handling-error column)
   make publish OUTPUT_DIR=output/postrun/20260920_match \
        MATCH_KEY=20260920_1000_castelldefels_ari_joan DRY=1
   ```
   (Use your match's folder under `output/` if it is named differently.)
   **Check the dry run:** score A 21 – B 12, 33 points. The per-slot fantasy
   preview must equal the footer of `match_reconstruction.txt`. Then run the
   same command without `DRY=1`. Expect `published: applied (revision 1)`.
   Run it again and expect `unchanged (revision 2)`: that is the idempotency
   working. Always pass the same `MATCH_KEY` for this legacy match. New
   videos get conforming names automatically (step 6).

---

## 4. The website on Cloudflare Workers (15 min)

1. dash.cloudflare.com → Workers & Pages → Create → **Workers** → Import a
   repository → choose this repository, production branch `main`. (This is a
   Worker serving static assets, not a Pages project: `webapp/wrangler.jsonc`
   holds its name and asset folder.)
2. Build settings:
    - Root directory: **`webapp`**
    - Build command: **`npm run build`**
    - Deploy command: **`npx wrangler deploy`** (the default)
3. Build variables (Settings → Variables and secrets → *Build*):
    - `VITE_SUPABASE_URL` = the project URL
    - `VITE_SUPABASE_PUBLISHABLE_KEY` = the **publishable** key (never the
      secret one)
    - `NODE_VERSION` = `22`
4. Deploy. The site gets `https://<name>.<account>.workers.dev`. Put that URL into
   Supabase *Site URL* and *Redirect URLs* (step 2.7). `webapp/wrangler.jsonc`
   (`not_found_handling: single-page-application`) makes deep links like
   `/matches/…` work. Don't add a `/* /index.html 200` rule to `_redirects`:
   Workers rejects it as an infinite loop. The empty `"previews": {}` block is
   what lets the pull-request build (`wrangler preview`) run; without it that
   build fails with "missing a `previews` block".

**Check:** the site shows the login page. "Site not configured" means the
two `VITE_` variables are missing from the build: add them and redeploy.
Then check the security headers (`webapp/public/_headers`: a content
security policy, no framing by other sites):

```bash
curl -sI https://<name>.<account>.workers.dev | grep -iE 'content-security-policy|x-frame-options'
```

Both lines must print.

To preview locally first: `cd webapp && npm install && npm run dev` runs
on demo data. Add a `.env.local` (see `.env.example`) to use the real
project.

---

## 5. First admin, then the players (15 min)

1. Supabase → Authentication → Users → **Invite user** → your own email.
   Open the invite mail and click the link; you land on the site, logged in.
2. Make yourself admin. Supabase → SQL Editor:
   ```sql
   update public.profiles set role = 'admin' where email = '<your email>';
   ```
   Reload the site. The **Admin** tab appears.
3. Admin → Review queue → open the 20260920 match:
    - **1 · Who is who:** for each slot thumbnail, pick or create the player.
    - **2 · Check:** score, set complete, flagged points, the video link.
    - **3 · Publish:** add venue and season, then **Publish**.
4. Invite the other players from Supabase → Users → Invite. The link in
   the invite works for **one hour**; someone who opens it later is refused
   at login until you invite the same email again. Once someone has
   accepted, go to Admin → Players & accounts and link their account to
   their player. Promote a second admin there if you want one.

**Check:** log in as a player in a private window. They see the league and
their own match, and someone else's play-by-play stays hidden unless they
played in it.

---

## 6. Drive inbox and automation (20 min)

1. In Google Drive, create `VolleyInbox`, `VolleyArchive` and
   `VolleyBackups`. Share **VolleyInbox** (Editor) with whoever records.
2. Connect rclone:
   ```bash
   rclone config
   ```
   Answer: `n` (new remote), name `gdrive`, storage `drive`, leave client
   id and secret empty, scope `1` (full drive), root folder empty, service
   account empty, edit advanced config `n`, auto config `y` (a browser
   opens; log in with the Drive owner account), shared drive `n`.

   **Check:** `rclone lsjson gdrive:VolleyInbox` prints `[]`.
3. **Dry pass:** `python -m src.publish.inbox --dry-run` should print
   `inbox empty`.
4. **Schedule it:**
   ```bash
   cd <path to prod repo> && ops/launchd/install.sh <path to prod repo>/venv/bin/python
   ```
   This installs `com.volley.inbox` (a pass every 30 min while the Mac is
   awake) and `com.volley.backup` (Mondays 09:07: admin tables → JSON →
   `gdrive:VolleyBackups`). Logs go to `data/inbox.log` and
   `data/backup.log`. Remove with `ops/launchd/install.sh uninstall`.
5. Allow the notifications: System Settings → Notifications → *Script
   Editor* → allow (macOS shows `osascript` notifications under that name).
6. **Tell the recorders:**
   > Upload the video with the Google Drive app into *VolleyInbox*. The
   > app keeps the original quality. Name it `<venue>_<players>`, e.g.
   > `bogatell_ari_joan.mp4`, or leave the camera's name. Date and time are
   > added automatically.

**Check:** drop a video in the inbox and run `make inbox`.
The file appears as `resources/YYYYMMDD_HHMM_<slug>.mp4` and a notification
asks for its calibration.

---

## 7. Keep-alive (5 min)

Free Supabase projects pause after 7 days without traffic. In GitHub, go to
the repo → Settings → Secrets and variables → Actions → *New repository
secret*, and add `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`. Then Actions
→ **supabase-keepalive** → *Run workflow*. **Check:** it prints `"ok:1"`.

(GitHub disables scheduled workflows in a *public* repo after 60 days without
commits. If the repo is public and goes quiet, re-enable it from the Actions
tab.)

---

## 8. Lock the accounts (10 min)

The site is only as safe as the three accounts that can change it.

1. **Two-step login** on GitHub, Cloudflare and Supabase (each: account
   settings → security). `main` is what Cloudflare deploys and what the prod
   worktree pulls, so whoever controls the GitHub account controls the
   site's code and what runs next to the secret key.
2. **`main` is protected** (set 2026-10-06): no force-push, no deletion, and
   a pull request is required from everyone but the repository admin. Agents,
   apps and collaborators cannot push to `main`; your own direct push still
   works and prints "Bypassed rule violations". See or change it under repo →
   Settings → Branches, or with
   `gh api repos/<owner>/<repo>/branches/main/protection`.
3. **Dependabot** alerts and security updates are on (repo → Settings →
   Advanced Security): a vulnerable npm package gets a pull request. Secret
   scanning with push protection is on too, so a pushed key is refused.
4. **If a key leaks.** The publishable key is public by design: nothing to
   do. The secret key: Supabase → API Keys → revoke `laptop-publisher`,
   create a new one and put it in `.env.publish`.

---

## Day to day

| You do                                                   | The system does                                                                                                               |
|----------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| Record; upload to VolleyInbox                            | –                                                                                                                             |
| Leave the Mac on, plugged in                             | `make inbox` downloads the video, names it `YYYYMMDD_HHMM_…` and notifies "needs calibration"                                 |
| `make calibrate VIDEO=resources/<key>.mp4` (8 clicks)    | Next pass: `make run-match` (~0.8× the video length), publish as a **draft**, archive the file on Drive, notify "Draft ready" |
| Website → Admin → assign the 4 slots, check, **Publish** | Players see results, box score, fantasy and the league table                                                                  |

**Corrections:**

- **Pipeline or logic fix:** `make postrun` (or a re-run), then `make publish`.
  This creates a new revision, and the publication log keeps every earlier
  one.
- **Roll back:** `python -m src.publish --from-bundle output/<key>/match_bundle.json`
  (an older bundle can be downloaded from the admin log).
- **Wrong person in a slot:** re-assign in Admin. Every stat follows
  immediately.
- **Fantasy values:** Admin → Fantasy scoring. Edit a value to rescore
  everything, or *Duplicate rule set*, edit the copy and *Activate* it to try
  values without losing the old ones.
- **Remove a match:** Admin → **Hide**. Its publish history blocks hard
  deletes on purpose.
- **A failed inbox file:** `python -m src.publish.inbox --retry <key>`.

## Troubleshooting

| Symptom                                                                                               | Cause / fix                                                                                                                                                                                                                                                                                    |
|-------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Login says "cannot log in yet"                                                                        | Never invited, or the invite link was not opened within the hour. Invite the email (again) from Supabase → Users. (Only shown while step 2.9 is not done)                                                                                                                                      |
| "A code is on its way" but none arrives                                                               | The site says that for EVERY address (2.9). Was the invite accepted? More than one request a minute or five an hour for that address? Then Supabase → Edge Functions → `request-login-code` → Logs: a line `auth /otp -> HTTP …` is Auth refusing (429 = its rate limit, 5xx = SMTP, step 2.5) |
| Login says "the login function did not answer"                                                        | The lock is on (2.9) but the function is not deployed or fails: `supabase functions deploy request-login-code`, then its Logs. `login_code_gate -> HTTP 401` or "service key missing" there: give it a key with `supabase secrets set LOGIN_BROKER_SERVICE_KEY=<a secret key>`                 |
| The login email never arrives                                                                         | SMTP not set (2.5) or rate limit; check Authentication → Logs                                                                                                                                                                                                                                  |
| The email link opens `127.0.0.1`                                                                      | *Site URL* still local (2.7). The code in the email works anyway                                                                                                                                                                                                                               |
| The site says "Site not configured"                                                                   | Missing `VITE_SUPABASE_*` variables in Cloudflare (4.3); redeploy                                                                                                                                                                                                                              |
| `make publish`: "uncommitted changes"                                                                 | Publish from `<path to prod repo>`, or pass `PUBLISH_FLAGS=--allow-dirty` knowingly                                                                                                                                                                                                            |
| `make publish`: "already holds a different video"                                                     | Two different files with one name. Rename one, or `PUBLISH_FLAGS=--replace-video` if it is intentional                                                                                                                                                                                         |
| `make publish`: "not a match key"                                                                     | Pass `MATCH_KEY=YYYYMMDD_HHMM_<venue>_<text>`                                                                                                                                                                                                                                                  |
| A player sees no play-by-play                                                                         | By design: only that match's players see it (Admin → match → "Everyone can see the play-by-play" opens it)                                                                                                                                                                                     |
| A slot thumbnail is missing                                                                           | The decoded video or `diag.jsonl` was not on disk at publish time. Assign from the video link instead                                                                                                                                                                                          |
| The project is paused                                                                                 | Supabase dashboard → Restore. Then check the keep-alive workflow runs                                                                                                                                                                                                                          |
| The site or `make backup` says "permission denied for table" (42501)                                  | A table or view without a `GRANT`. New ones get none by default: grant it in its migration (see `20261007120000_explicit_grants.sql`)                                                                                                                                                          |
| `make publish`: "`.env.publish` is readable by other users"                                           | `chmod 600 .env.publish`                                                                                                                                                                                                                                                                       |
| A new script, font or image host does not load (console: "Refused to load … Content Security Policy") | Add the host to `webapp/public/_headers` and redeploy                                                                                                                                                                                                                                          |
