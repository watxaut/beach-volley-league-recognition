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
   strong database password and keep it in your password manager.
2. **Copy three values** from Project Settings → API Keys:
   - Project URL: `https://<ref>.supabase.co`
   - **Publishable** key (`sb_publishable_…`, or the legacy `anon` key). Goes
     to the website.
   - **Secret** key (`sb_secret_…`, or the legacy `service_role` key). Goes
     to the laptop only.
3. **Create the schema.** In this repo:
   ```bash
   supabase login
   supabase link --project-ref <ref>      # asks for the DB password
   supabase db push                       # applies the 2 migrations
   ```
   **Check:** Table Editor shows `matches`, `points`, `actions`,
   `fantasy_rules` (8 G1 rows), …; Storage shows two **private** buckets,
   `match-bundles` and `match-media`.
4. **Turn off public sign-up.** Authentication → Sign In / Providers →
   *Allow new users to sign up* = **OFF**. Keep the Email provider enabled.
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
     `{{ .Token }}`, which is the 6-digit code the login page asks for.
   - **Invite user:** body = `supabase/templates/invite.html`.
7. **URLs.** Authentication → URL Configuration. Leave it until step 4 gives
   you the site URL, then set *Site URL* = `https://<your-site>.pages.dev`
   and add these *Redirect URLs*: `https://<your-site>.pages.dev/**` and
   `http://127.0.0.1:5173/**`.
8. **(Optional) Behaviour check against the real project.** Dashboard →
   Connect → *Session pooler* URI, then:
   ```bash
   psql "<session-pooler-uri>" -v ON_ERROR_STOP=1 -f supabase/checks/rls_smoke.sql
   ```
   Expect `RLS SMOKE: ALL CHECKS PASSED`. The script runs in one transaction
   and **rolls back**, so it leaves nothing behind. If your project refuses
   the test inserts into `auth.users`, run the same check on the local
   stack instead (Docker Desktop, then `supabase start` and
   `make schema-check`).

---

## 3. The processing laptop (30 min)

1. **A clean "prod" checkout.** Published numbers must come from committed
   code (AGENTS.md §8). The publisher refuses a dirty tree.
   ```bash
   cd ~/path/to/beach-volley-league-recognition          # your dev checkout
   git fetch origin && git worktree add ~/volley-prod origin/main
   cd ~/volley-prod
   ln -s ~/path/to/beach-volley-league-recognition/models models
   ln -s ~/path/to/beach-volley-league-recognition/output output
   ln -s ~/path/to/beach-volley-league-recognition/data data
   # resources/ is tracked in git (one script), so link the videos in, not the folder:
   find ~/path/to/beach-volley-league-recognition/resources -maxdepth 1 \
        \( -iname '*.mp4' -o -iname '*.mov' \) -exec ln -sf {} resources/ \;
   # Clone the EXACT packages of your working venv/: it has ultralytics 8.3.169,
   # the only release the detector fast path is verified on (AGENTS §12) and
   # the one every GT number was measured with. A fresh `pip install -e .`
   # would resolve a newer one (uv.lock says 8.4.x).
   ~/path/to/beach-volley-league-recognition/venv/bin/pip freeze --exclude-editable > /tmp/volley-req.txt
   "$(~/path/to/beach-volley-league-recognition/venv/bin/python -c 'import sys; print(sys.executable)')" -m venv venv
   source venv/bin/activate
   pip install -r /tmp/volley-req.txt && pip install --no-deps -e .
   python -c "import ultralytics; print(ultralytics.__version__)"   # must print 8.3.169
   ```
   Every command below assumes `cd ~/volley-prod && source venv/bin/activate`.
   To update it later: `git -C ~/volley-prod pull --ff-only` (or
   `git checkout origin/main` in a detached worktree).
2. **Credentials.**
   ```bash
   cp .env.publish.example .env.publish && chmod 600 .env.publish
   ```
   Fill in `SUPABASE_URL` and `SUPABASE_SECRET_KEY`.
3. **Publish the match you already have.** Its name lacks the time, so pass
   the full key once. Get the recording time from the video:
   ```bash
   ffprobe -v quiet -show_entries format_tags=creation_time -of default=nw=1 resources/20260920_match_ari_joan_lost.mp4
   make postrun OUTPUT_DIR=output/20260920_match_ari_joan_lost      # refresh (adds the handling-error column)
   make publish OUTPUT_DIR=output/20260920_match_ari_joan_lost \
        MATCH_KEY=20260920_<HHMM>_<venue>_ari_joan DRY=1
   ```
   (Use your match's folder under `output/` if it is named differently.)
   **Check the dry run:** score A 21 – B 12, 33 points. The per-slot fantasy
   preview must equal the footer of `match_reconstruction.txt`. Then run the
   same command without `DRY=1`. Expect `published: applied (revision 1)`.
   Run it again and expect `unchanged (revision 2)`: that is the idempotency
   working. Always pass the same `MATCH_KEY` for this legacy match. New
   videos get conforming names automatically (step 6).

---

## 4. The website on Cloudflare Pages (15 min)

1. dash.cloudflare.com → Workers & Pages → Create → **Pages** → Connect to
   Git → choose this repository, production branch `main`.
2. Build settings:
   - Framework preset: **None**
   - Root directory: **`webapp`**
   - Build command: **`npm run build`**
   - Build output directory: **`dist`**
3. Environment variables (Production and Preview):
   - `VITE_SUPABASE_URL` = the project URL
   - `VITE_SUPABASE_PUBLISHABLE_KEY` = the **publishable** key (never the
     secret one)
   - `NODE_VERSION` = `22`
4. Deploy. The site gets `https://<name>.pages.dev`. Put that URL into
   Supabase *Site URL* and *Redirect URLs* (step 2.7). `webapp/public/_redirects`
   already makes deep links like `/matches/…` work.

**Check:** the site shows the login page. "Site not configured" means the
two `VITE_` variables are missing from the build: add them and redeploy.

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
4. Invite the other players from Supabase → Users → Invite. Once someone
   has accepted, go to Admin → Players & accounts and link their account to
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
   cd ~/volley-prod && ops/launchd/install.sh ~/volley-prod/venv/bin/python
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

## Day to day

| You do | The system does |
|---|---|
| Record; upload to VolleyInbox | – |
| Leave the Mac on, plugged in | `make inbox` downloads the video, names it `YYYYMMDD_HHMM_…` and notifies "needs calibration" |
| `make calibrate VIDEO=resources/<key>.mp4` (8 clicks) | Next pass: `make run-match` (~0.8× the video length), publish as a **draft**, archive the file on Drive, notify "Draft ready" |
| Website → Admin → assign the 4 slots, check, **Publish** | Players see results, box score, fantasy and the league table |

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

| Symptom | Cause / fix |
|---|---|
| Login says "not been invited yet" | Invite the email from Supabase → Users |
| The login email never arrives | SMTP not set (2.5) or rate limit; check Authentication → Logs |
| The email link opens `127.0.0.1` | *Site URL* still local (2.7). The 6-digit code works anyway |
| The site says "Site not configured" | Missing `VITE_SUPABASE_*` variables in Cloudflare (4.3); redeploy |
| `make publish`: "uncommitted changes" | Publish from `~/volley-prod`, or pass `PUBLISH_FLAGS=--allow-dirty` knowingly |
| `make publish`: "already holds a different video" | Two different files with one name. Rename one, or `PUBLISH_FLAGS=--replace-video` if it is intentional |
| `make publish`: "not a match key" | Pass `MATCH_KEY=YYYYMMDD_HHMM_<venue>_<text>` |
| A player sees no play-by-play | By design: only that match's players see it (Admin → match → "Everyone can see the play-by-play" opens it) |
| A slot thumbnail is missing | The decoded video or `diag.jsonl` was not on disk at publish time. Assign from the video link instead |
| The project is paused | Supabase dashboard → Restore. Then check the keep-alive workflow runs |
