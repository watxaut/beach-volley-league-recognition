# Video → web platform design (session #90: designed, ratified, built)

Owner ask (2026-10-06): design the flow from a recorded match video to a
login-only stats + fantasy web page. Constraints: MVP, no GCP/AWS
infrastructure to maintain, processing on the owner's laptop (M3), Supabase for
the web, idempotent upsert keyed by the video name, a log of every upload with
a link to the video, admins who map players to people, viewers who see their
own stats and other players' public ones.

Status: **ratified by the owner (2026-10-06, decisions in §9) and BUILT in
the same session.** The code is `supabase/`, `src/publish/`, `webapp/`,
`ops/launchd/` and `.github/workflows/`. What is left is the owner's
deployment, done step by step in `docs/deploy_web_platform.md`. Two owner
changes to the proposal:

* **D3:** the file name carries the start time, `YYYYMMDD_HHMM_<venue>_<text>`.
* **D8:** fantasy points live in their own tables (`fantasy_rulesets` +
  `fantasy_rules`), not in a one-row settings table.

D1 also changed: no Telegram, not even for notifications. The laptop uses
macOS notifications.

The canonical SQL is the migration itself. Appendix A now only points to it.

---

## 0. TL;DR

| Question | Recommendation |
|---|---|
| 1. Getting videos in | **Google Drive shared folder** (`VolleyInbox`), pulled by `rclone` on the laptop. Not Telegram: by default it re-encodes videos, a bot can download only 20 MB without self-hosting a Bot API server, and it keeps undelivered bot updates for only 24 h. (Owner: no Telegram at all for now; the laptop notifies through macOS.) |
| 2. Processing | **The M3 laptop.** About 0.8× the video length (30–32 ms/frame since the #89 speed work; 68 before). The 2014 Mac mini can't run the locked stack: the last PyTorch for Intel macOS is 2.2.x and the repo locks 2.10. It would also be CPU-only and much slower. Don't use it. |
| 3. Feeding the web | **`make publish`** builds one JSON *match bundle* from `output/<stem>/`, uploads it to Supabase Storage and calls one Postgres function, `ingest_match_bundle`, which applies it in **one transaction**. Keyed by `match_key` = the video's source stem. Re-publishing the same content changes nothing (`unchanged`). Changed content replaces only the pipeline-owned rows. Every call adds a row to `match_publications` (the log), which links the bundle and the video. |
| 4. Web | **Supabase** (Postgres + Auth + row-level security + Storage) plus a **static React SPA on Cloudflare Workers (static assets)**. No server of ours. Invite-only, with magic-link or one-time-code login. All access rules are enforced in the database by row-level security. Two roles: admin and viewer. New matches land as **drafts** that an admin reviews, assigns players to and publishes. |
| 5. Data model | Dimensions `players`, `profiles`. Facts at three grains: `matches` (one per video), `points` (one per rally), `actions` (one per touch, the lowest grain). Bridge table `match_participants` (slot P1A/P2A/P1B/P2B → player): **actions store the slot, never the person**, so assignments survive re-processing. Spike landing and dig detail go in the **same `actions` table** as nullable columns. Stats and fantasy points are **views** over actions, not stored totals. |
| Cost | €0 on free tiers (Drive 15 GB ≈ 10 matches; Google One 100 GB ≈ €2/month). Supabase Pro ($25/month) only when you want uploads through the web, no pausing and managed backups. |

```
 recorder's phone                owner's laptop (M3)                        free-tier cloud
 ┌──────────────┐  upload   ┌───────────────────────────┐            ┌───────────────────────────┐
 │ Google Drive │──────────▶│ Drive: VolleyInbox/        │            │ Supabase                  │
 │ app          │ original  └─────────────┬─────────────┘            │  Postgres + RLS           │
 └──────────────┘ bytes                   │ rclone (make inbox)      │  Auth (invite-only)       │
                                          ▼                          │  Storage: bundles, thumbs │
                            calibrate (8 clicks, the one manual step) └─────────────▲─────────────┘
                                          ▼                                        │ rpc ingest_match_bundle
                            make run-match  (~0.8× video length)                   │ (secret key, 1 transaction)
                                          ▼                                        │
                            make publish ── bundle.json + 4 slot thumbs ───────────┘
                                          │
                                          └─▶ notify: "draft ready: 21–17, 38 pts, 2 flags"
                                                                          ┌───────────────────────────┐
                                    admin: review → assign slots → publish │ Web SPA (CF Workers)      │
                                    viewer: my stats, league, matches      │ supabase-js, RLS-guarded  │
                                                                          └───────────────────────────┘
```

---

## 1. Video intake (Q1)

### Telegram: does work, but has three problems

* **Compression.** A video sent the normal way is re-encoded by Telegram.
  Only "attach → File/Document" sends the original bytes, and a sender will
  forget that sooner or later. For this pipeline the damage is real: the
  far-side ball is ~14–28 px wide, its pixel width is the side signal (AGENTS
  §5), and every px constant was measured at 1080p (§7). A re-encoded video
  silently becomes a different input.
* **Size.** User uploads can be up to 2 GB (4 GB with Premium), but a bot on
  the public Bot API can download at most **20 MB**. Getting 1.2–1.5 GB files
  means running Telegram's own `telegram-bot-api` server (up to 2000 MB) on
  the laptop. That is infrastructure, and a longer match would exceed it.
* **Availability.** Telegram keeps undelivered bot updates for **24 h**, and a
  bot cannot read chat history. If the laptop is off for a weekend, the upload
  is lost and has to be re-sent.

Telegram would still be fine for **notifications** (`sendMessage` on the
standard Bot API, no local server). The owner chose none for now (D1), so the
laptop uses macOS notifications.

### Recommended: Google Drive inbox folder

* The recorder uploads with the Drive mobile or desktop app into a shared
  `VolleyInbox/` folder. Drive stores the **original bytes**, uploads resume
  after interruptions, nobody installs anything new, and files **wait there
  while the laptop is off**.
* The laptop pulls with `rclone` (scriptable; `rclone lsjson` returns the Drive
  file id, which gives the debug link
  `https://drive.google.com/file/d/<id>/view`). After a successful publish the
  file is *moved* to `VolleyArchive/` with `rclone moveto`. A move keeps the
  file id, so the link stored in the log stays valid.
* Sharing: the inbox is writable by recorders. The archive links are opened
  only by admins, and the web app shows them only to admins (§6.3).
* Quota: 15 GB free ≈ 10 matches of 1.5 GB. Google One 100 GB ≈ €2/month, or
  prune the archive (the laptop keeps its own copy in `resources/`).

| Option | Original quality | Laptop must be on | Build/maintain | Cost | Verdict |
|---|---|---|---|---|---|
| Google Drive + rclone | yes | no | none | €0–2/mo | **MVP** |
| Telegram bot | only if sent "as file" | yes (24 h window) | local Bot API server | €0 | not used (D1) |
| Supabase Storage (resumable uploads) | yes | no | an upload page in the web app | free plan max **50 MB/file**, so it needs Pro ($25/mo, files up to 500 GB, 100 GB included) | Phase 4 ("upload match" button) |
| Cloudflare R2 + presigned upload | yes | no | an upload page | 10 GB free, no egress fees | only if leaving Drive |
| AirDrop / USB | yes | yes | none | €0 | fine when the owner recorded it |

### Naming = match identity

`match_key` = the **source** video stem, lowercased, after
`resolve_source_stem` (it strips the `_up1080` cache suffix — note that
`pipeline_output.json` `video.key` carries `_up1080` for the 720p match, so
the publisher must NOT use it raw). Convention:
`YYYYMMDD_HHMM_<venue>_<free_text>` (D3, ratified with the time added), e.g.
`20260920_1830_bogatell_ari_joan`, validated by
`^[0-9]{8}_[0-9]{4}_[a-z0-9]+(_[a-z0-9]+)*$` (`src/publish/naming.py`, and
the DB check). The prefix gives `match_date` and `start_time`. A date in the
future is rejected (`20290928_entreno_vall_dhebron` in `ground_truth/` is
exactly that typo).

Inbox files are renamed **before** calibration, because `calibrations/` and
`output/` key on the stem:
* `IMG_1234.MOV` becomes `<local creation time YYYYMMDD_HHMM>_img_1234`
  (`ffprobe` `creation_time`, else the Drive time, flagged).
* A `YYYYMMDD_<slug>` name only gains the time.

Venue and title are edited later in the web, because they are admin-owned
columns that publishing never overwrites. Runs made before the convention
publish with `--match-key`.

One video = one match (MVP). Two safety rules:

* The bundle carries the video's sha256 (~3 s for 1.5 GB). The ingest
  function **refuses** a bundle whose `match_key` already holds a different
  video, unless `--replace-video` is passed. This protects the
  "name is the id" convention against two different files called `IMG_0001`.
* `points.set_no` exists from day one (default 1) so a best-of-3 video does
  not need a migration. A match split across two files gets a `_p2` suffix
  convention later. Not designed now.

---

## 2. Processing (Q2)

**The M3 MacBook is the processing machine.** Production speed is 30–32
ms/frame since #89 (read-ahead + exact detector fast path; 68–75 before). At
the match's 25.7 fps that is ≈0.8× real time: the 20260920 match takes ~13
min, a 40-min video ~32 min. Post-run is ~3 s.

**The 2014 Mac mini.** Not recommended for inference:

* It is Intel x86_64, so macOS tops out at 12. **PyTorch stopped publishing
  Intel-macOS wheels after 2.2.x**, and `uv.lock` pins torch 2.10.0. Running
  there means either a second, older dependency set (an unvalidated pipeline:
  the GT numbers were all measured on this stack) or installing Linux on it.
* It is CPU-only on a 2014 CPU. CPU is the *parity* reference (AGENTS: `--device cpu`), so
  results would be valid, but expect it to be several times slower than the
  M3 (unmeasured).
* The only thing it could usefully do is be an always-on watcher, and the
  Drive inbox makes that unnecessary: files wait in Drive.

**The one manual step is calibration.** The tripod moves between videos (§7),
so every video needs the interactive 8-point calibration (~1 min). The flow
stops there and notifies; everything else is automatic.

### Local runner (no state database; every step checks its own output)

```
make inbox                         # Phase 2: the only command (or launchd every 15 min)
  ├─ rclone lsjson gdrive:VolleyInbox → new files → rclone copy → resources/<key>.mp4
  ├─ calibrations/<key>.json missing?  → notify "needs calibration: make calibrate VIDEO=…" → skip
  ├─ output/<key>/match_reconstruction.json missing or older than video/calibration/code?
  │      → caffeinate -is make run-match VIDEO=resources/<key>.mp4
  ├─ make publish OUTPUT_DIR=output/<key>      (lands as DRAFT; idempotent)
  ├─ rclone moveto gdrive:VolleyInbox/<f> gdrive:VolleyArchive/<f>
  └─ notify (macOS notification): score, points, flags, review link
```

Rules that come from AGENTS.md:

* **§8 (one session per working tree):** the runner never runs in the dev
  checkout. It runs from a dedicated `git worktree` (e.g. `~/volley-prod` on
  `main`, with `models/` and `resources/` symlinked), so `pipeline_version` is
  a real commit and a half-edited tree can never produce published numbers.
  `make publish` refuses a dirty tree unless `--allow-dirty` is passed, and
  then records `git_dirty=true`.
* A lock file stops two runs at once. Long runs start only on AC power and
  run under `caffeinate` (launchd does not run while the Mac sleeps; the
  inbox simply waits).
* The diag dump is required (post-run input, open point 32c). `run-match`
  already writes it.

---

## 3. Publishing / sync (Q3)

### Sources of truth

* **Pipeline-owned data** (points, touches, scores, checks, thumbnails): the
  laptop's `output/<key>/` is the truth. Supabase holds a **reproducible
  copy**, and every published bundle is kept in Storage, so the whole
  pipeline-owned part of the DB can be rebuilt with `publish --all`.
* **Admin-owned data** (players, users and roles, slot→player assignments,
  match title/venue/status, manual overrides): Supabase is the truth.
  Publishing **never writes it** (the same rule as the local SQLite ingest:
  "labels survive re-ingest"). A weekly JSON export covers it (§6.5).

### The bundle (`bundle_version: 1`)

`src/publish/bundle.py` is pure and testable: it reads `match_reconstruction.json` +
`pipeline_output.json` + the diag dump + the calibration and writes:

```json
{
  "bundle_version": 1,
  "content_sha256": "sha256 of canonical JSON(match, slots, points, actions)",
  "match":  {"match_key": "20260920_match_ari_joan", "match_date": "2026-09-20",
             "points_to_win": 21, "score_a": 21, "score_b": 12, "winner_team": "A",
             "n_points": 33, "set_complete": true, "duration_s": 1530.2, "checks": {"…": "…"},
             "video": {"filename": "…mp4", "url": "https://drive.google.com/file/d/…/view",
                       "sha256": "…", "fps": 25.67, "width": 1280, "height": 720}},
  "slots":  [{"slot": "P1A", "thumb_path": "thumbs/20260920_match_ari_joan/P1A.jpg"}, "…"],
  "points": [{"point_no": 1, "set_no": 1, "start_frame": 180, "end_frame": 420,
              "serving_team": "B", "server_slot": "P1B", "winner_team": "A", "…": "…"}],
  "actions":[{"point_no": 1, "seq": 0, "frame": 211, "slot": "P1B", "team": "B",
              "action": "serve", "outcome": null, "observed": true, "…": "…"}],
  "provenance": {"pipeline_version": "78844e5", "git_dirty": false, "postrun_schema": 1,
                 "diag_schema": 4, "calibration_sha256": "…", "built_at": "…", "host": "…"}
}
```

* Point and action keys are named exactly like the table columns. The SQL
  function inserts with `jsonb_populate_recordset`, so a new column is
  added in two places only: the migration and the bundle builder.
* **The hash covers content only, not provenance or timestamps.** Rebuilding
  an unchanged run gives the same hash, so the publish is a recorded no-op even
  when the pipeline version moved.
* `is_assist` is computed per set in Python with the **same rule as
  `postrun.player_stats`** (one source for the rule). Spike detail (attack
  zone, spike type) is joined from `pipeline_output.json` `spikes` to the
  post-run attack touch (nearest frame within ±15 f, the contact-scoring
  tolerance). Its landing comes from the next touch (dug) or the point end.
* **Slot thumbnails** (needed so the admin can tell P1A from P2A): a few
  credited-contact frames per slot, cropped with the dump's bbox. They are
  decoded **sequentially with `grab()`**, never with a `CAP_PROP_POS_FRAMES`
  seek (§9; `test_vfr_seek_guard.py` would fail it anyway). This takes about
  1–2 min per match. Each is uploaded as `match-media/thumbs/<key>/<slot>.jpg`.

### The publish call

```
make publish OUTPUT_DIR=output/<key> [DRY=1] [NOTE="re-run after fix 32f"]
  1. build bundle; validate (schema versions, match_key regex, set_no, slots ⊂ {P1A,P2A,P1B,P2B})
  2. DRY=1 → fetch the live current revision and print the diff
            (score, n_points, per-slot fantasy deltas, actions added/removed); stop
  3. upload bundle → storage  match-bundles/<key>/<content_sha256>.json  (content-addressed: re-upload is harmless)
  4. upload thumbs (only if missing or changed)
  5. POST /rest/v1/rpc/ingest_match_bundle  {bundle, bundle_path, published_by}
  6. append the result to data/publish_log.jsonl (local mirror of the log); notify
```

**Why one RPC and not table upserts from Python?** Each PostgREST request is
its own transaction. Upserting `matches`, then `points`, then `actions` from
the client can leave a half-updated match visible to users if the Wi-Fi drops
midway. The SQL function (Appendix A) does everything under one advisory lock
in one transaction:

1. Upsert `matches` on `match_key`, writing **pipeline-owned columns only**.
2. If `content_sha256` equals the current publication's hash, insert a log
   row with `result='unchanged'` and stop.
3. Otherwise delete the match's `points` (its `actions` cascade) and insert the
   new ones. Create missing `match_participants` slots **without touching
   `player_id`**. Upsert `match_sources`.
4. Insert a log row in `match_publications` (`revision = n+1`,
   `result='applied'`, hash, pipeline version, bundle path, video url, counts,
   note) and point `matches.current_publication_id` at it.

If the network fails at any step, re-run the same command. Before step 5
nothing is visible, and step 5 is atomic. **That is the idempotency
guarantee.**

### Correcting data

| What's wrong | How it's fixed |
|---|---|
| Pipeline / post-run logic (e.g. open point 32f) | fix code → `make postrun` (3 s) → `make publish` → new revision; old ones stay in the log |
| Bad revision published | `make publish FROM_BUNDLE=<storage path or local file>` re-applies an older bundle (it is just another revision) |
| Wrong person on a slot | admin re-assigns in the web; every stat is a view, so it updates immediately |
| One touch wrong or missing (e.g. a ball-handling error the camera can't see) | Phase 3: `action_overrides` (admin-owned, keyed by match + point + frame, so it survives re-publishes). The ingest re-attaches each override to the nearest touch in the same point within ±0.5 s, and lists the ones that no longer match as **orphaned** for the admin. |
| Match should not exist | admin sets `status='hidden'`; the log keeps its history (the log's FK forbids hard deletes by default) |

Re-publishing an already published match keeps it published (status is
admin-owned). The admin page shows a "changed since review: rev 3 → 4" badge.

---

## 4. Web application (Q4)

### Stack (nothing to run or patch)

* **Supabase:** Postgres, Auth, row-level security, Storage. **EU region** (the players
  are EU residents and this is personal data about them — get their consent
  before inviting them; the login-only design helps).
* **Frontend:** Vite + React + TypeScript + `supabase-js`, React Router,
  TanStack Query, Tailwind + shadcn/ui (fast to make look intuitive),
  mobile-first because players will open it on their phones. DB types are
  generated with `supabase gen types typescript`. It is a static build, so
  there are no server secrets. The only key in the browser is the publishable
  (anon) key, which is safe **because every table has RLS**.
* **Hosting:** Cloudflare Workers with static assets (free, deploys on git push,
  no non-commercial clause; Cloudflare's recommended successor to Pages).
  Vercel Hobby works too but is for non-commercial use.
* **Server-side code:** none in the MVP. Phase 3 adds one Supabase Edge
  Function (`invite-user`, which needs the secret key). It is managed, not
  infrastructure.
* The existing FastAPI + SQLite UI (`make ui`) **stays the local lab tool**
  (labeling, causal-stream debugging). The product does not extend it.

### Auth and roles

* **Invite-only.** Turn off "Allow new users to sign up". In the MVP the
  admin invites from the Supabase dashboard; Phase 3 adds an in-app invite
  button.
* **Login:** email magic link or 8-digit code (nothing to remember, works on
  phones), with Google sign-in as an option.
* **Set up custom SMTP before inviting anyone** (e.g. Resend's free tier).
  Supabase's built-in mailer is a testing service with a very low rate limit.
* A trigger creates `profiles(user_id, role='viewer')` on sign-up. The first
  admin is promoted with one SQL line.
* `role ∈ {admin, viewer}`. `is_admin()` is a `security definer` helper used
  by the policies.
* **User ≠ player.** `players.user_id` (unique, nullable) links an account to
  a player. Opponents and guests are players without accounts. The admin
  links them when the person joins.

### Privacy: what is public (decision D2, recommended default)

Row-level security works on rows, and **any rows a user can read, the user can
aggregate**. So "private analytics" is only real if the raw touches are
protected too. Recommended tiers:

| Tier | Who sees it | Content | Served by |
|---|---|---|---|
| League | every logged-in member | published matches, final scores, who played, **box score and fantasy points per player per match**, leaderboard | `security definer` SQL functions returning aggregates only |
| Match detail | admins + **the 4 players of that match** (+ everyone if an admin sets `matches.detail_public`) | play-by-play, every touch | RLS on `points` / `actions` |
| Player analytics | the player, admins, + everyone if the player turns on `players.profile_public` | heatmaps, zones, percentages, trends across matches | `player_analytics()` function that checks the flag |
| Admin only | admins | drafts, video links, publication log, hashes, flags | RLS + a separate `match_sources` table (RLS can't hide one column) |

The match report (`match_report`) mixes tiers, so it applies them per value
(`20261007130000_match_report_privacy.sql`): the box-score line of each slot
and the teams' side-out / break-point are League; a player's attack split,
own-serve record, average over other matches and the serve targets are Player
analytics, also open to whoever holds Match detail for that match (they could
count the touches). A count that splits a team total the league already sees
needs BOTH teammates visible, or the visible one gives the other away by
subtraction.

### Pages

**Viewer**
1. **Home — "My season":** fantasy total and league rank, stat tiles (kills,
   aces, digs, assists, errors), last 5 matches as cards (score, W/L, my
   points, MVP badge).
2. **League:** fantasy leaderboard with season and date filters and sortable
   counts.
3. **Matches:** list with scores, then a match page with score header,
   team names and photos, score progression chart, box score, and
   play-by-play (tier rules above).
4. **Player (v2, #96):** a header (record, league rank, form, fantasy) and four tabs, `?tab=` in the
   URL. *Overview* (league tier): five count tiles and "you vs the league / vs your earlier matches",
   one strip per stat with better to the right, counted from `leaderboard` rows and the profile's match
   history. *Attack* and *Serve & receive* (analytics tier, "private" notice otherwise): rate tiles, the
   attack map (a line per attack from where the ball was hit to where it came down; colour = outcome,
   dashed = free ball), reception vs transition, serve targeting, reception outcome, trends. *Matches*:
   the history table. Every stat explains itself in an "i" hint (`lib/glossary.ts`).
5. **Settings:** display name, "share my detailed stats with the league".

**Admin** (extra menu)
6. **Review queue (drafts):** checks (`set_complete`, score, flags, uncredited
   touches), the play-by-play like `match_reconstruction.txt`, the 4 slot
   thumbnails with a player dropdown each (a player can't take two slots, enforced by the DB),
   the Drive video link, then **Publish**. This is the STATUS "rollout gate =
   fast human review".
7. **Players:** create, edit, link to an account, invite. **Unknown players:** a slot
   can be marked *Unknown player* instead of assigned (an opponent or guest the league
   does not know): the slot keeps its stats inside that match but is in no ranking or
   profile; this page lists every unknown slot with a "re-tag as" dropdown, so a person
   who joins later takes their matches over (`20261008100000_unknown_players.sql`).
8. **Publication log:** revisions per match with result, hash, pipeline
   version, bundle download and video link.

### Keeping the free tier healthy

* **Pausing:** free projects pause after **7 days of inactivity**. A
  `.github/workflows/keepalive.yml` cron (every 3 days, one cheap REST call
  with the publishable key) prevents it with no laptop involved.
* **Limits:** 500 MB DB and 1 GB Storage. A match is about 33 points + ~210
  actions (well under 1 MB with indexes), a ~0.3 MB bundle and 4 × ~30 KB
  thumbnails, so on the order of 1000 matches fit. Video never goes to
  Supabase in the MVP.
* **Backups:** the free plan has no managed backups. Pipeline data is
  reproducible (`publish --all` from bundles). Admin-owned tables get a weekly
  `python -m src.publish.backup` → JSON into Drive (or `supabase db dump`).

---

## 5. Data model (Q5)

Your three tables are the right core. Four refinements:

1. **Add a `points` fact (rally grain)** between match and action. Point
   start/end, server, winner, score after, end kind, line-call position and
   flags belong to the rally, not to any touch. The play-by-play UI and
   per-point fantasy (G1) read it directly.
2. **Add a bridge, `match_participants` (match × slot → player).** The video
   only knows P1A/P2A/P1B/P2B, which are stable within a match because the
   team identity resolver keeps them across side switches. Actions store the
   **slot**; the person is joined at query time. Re-processing a match never
   loses assignments, and fixing a wrong assignment fixes every stat at once.
   This is the existing `video_players` principle.
3. **Spike landing and dig detail: same `actions` table** (your instinct is
   right). They are 1:1 with one touch and only a handful of columns, and
   at this scale nullable columns cost nothing. Every stat query stays a
   single-table scan. Split into a child table only when a detail becomes 1:N
   (e.g. a ball flight polyline: put that in Storage JSON, not the DB) or
   grows many columns. A `extra jsonb` column takes experimental fields until
   they earn a typed column.
4. **Don't store match/player totals; compute them in views.** At ~210 rows per
   match, a view is instant for years. Fantasy values live in **their own
   tables** (D8, as built): `fantasy_rulesets` (exactly one active) and
   `fantasy_rules`, one row per rule:
   * `rule_key`, `label`
   * `actions[]`: the action labels it applies to
   * `outcome`: the required outcome, NULL = any
   * `assist_only`
   * `points`

   The view `action_fantasy` joins every credited touch to the matching
   active rules. Editing a value rescores history at once. To try new
   values, duplicate a rule set (`clone_ruleset`) and switch to it
   (`activate_ruleset`); the admin page does both. There are no aggregates to
   keep in sync after a re-publish or re-assignment. Materialize only if a
   page is ever slow.

### Tables

| Table | Grain | Owned by | Key columns |
|---|---|---|---|
| `profiles` | auth user | admin | `user_id` PK, `role`, `display_name` |
| `players` | real person | admin (+ own `profile_public`) | `id`, `display_name`, `user_id` unique null, `handedness`, `preferred_side`, `photo_path`, `profile_public`, `active` |
| `matches` | one video = one match | admin cols + pipeline cols | `id`, **`match_key` unique**, admin: `title`, `venue`, `season`, `status` (draft/published/hidden), `detail_public`; pipeline: `match_date`, `score_a/b`, `winner_team`, `n_points`, `set_complete`, `duration_s`, `checks`, `current_publication_id` |
| `match_sources` | 1:1 match, **admin-only** | pipeline | `video_filename`, `video_url`, `video_sha256`, `fps`, `width`, `height` |
| `match_participants` | match × slot | slot rows: pipeline; `player_id`, `is_unknown`: admin | PK (`match_id`, `slot`), `team` generated from slot, `player_id`, `is_unknown` (no player, stats kept in the match, never in a ranking; check: unknown ⇒ `player_id` null), `thumb_path`, unique (`match_id`, `player_id`) |
| `points` | rally | pipeline | PK (`match_id`, `point_no`), `set_no`, `start/end_frame`, `serving_team`, `server_slot`, `near_team`, `winner_team`, `winner_source`, `end_kind`, `end_x_m/end_y_m/end_in_court`, `score_a/b_after`, `flags[]` |
| `actions` | **touch (lowest grain)** | pipeline | PK (`match_id`, `point_no`, `seq`), `frame`, `slot` (null = not credited), `team`, `side`, `action`, `touch_number`, `outcome`, `is_assist`, `observed`, `evidence`, `player_source`, `height_m`, `own_x_m/own_y_m`, attack detail: `attack_zone`, `spike_type`, `landing_x_m/landing_y_m/landing_in/landing_source`, `landing_err_x_m/landing_err_y_m` (± metres across/along, ~1σ best effort), `landing_result` (kill/dug/out/net/error), dig detail: `dug_zone`, `extra` |
| `match_publications` | publish call (**the log**) | pipeline (append-only) | `match_id`, `revision`, `result` (applied/unchanged), `content_sha256`, `pipeline_version`, `bundle_path`, `video_url`, counts, `score`, `published_by/at`, `notes` |
| `fantasy_rulesets` | rule set | admin | `name`, `description`, `is_active` (unique when true) |
| `fantasy_rules` | rule × set | admin | PK (`ruleset_id`, `rule_key`), `label`, `actions[]`, `outcome` (NULL = any), `assist_only`, `points`, `sort_order`; G1 seeded |
| `action_overrides` (Phase 3) | manual correction | admin | `match_id`, `point_no`, `frame`, `field`, `value`, `orphaned`, `author`, `reason` |

### Modeling notes that matter

* **Unseen and uncredited touches are kept, not credited.** The post-run
  reconstruction keeps hidden "structure" touches for the touch count. They
  go in `actions` with `observed=false` and/or `slot=null`, so the
  play-by-play is complete, and every stat view filters `observed AND slot IS
  NOT NULL`. This is the owner's precision-first rule (AGENTS §11), applied
  in SQL.
* **Coordinates in the team's frame of reference.** `court_y` in the
  reconstruction runs 0 (far baseline) to 16 (near), in camera terms. Teams
  switch sides every 7 points, so heatmaps must use the toucher's own frame:
  `own_y_m` = metres from the toucher's own baseline, and `own_x_m` mirrored
  for the far half (the 9-zone grid is already 180°-symmetric). Store the
  normalised values; the raw camera-frame value can go in `extra`.
* **Landing is currently low-confidence.** The ball-death read exists on
  17/33 points and 3 of 10 line calls are wrong (open point 31). Landing
  columns are nullable and carry `landing_source` (`next_touch`,
  `ball_death`, `none`). The UI shows landing heatmaps only once 31 is
  better. Dug landing (where the next touch was) is reliable now.
* **Time.** `frame` is the canonical key. `frame / fps` is **not** video time
  on this VFR camera (25.67 fps of content in a 30.12 fps container; open point
  19's ~17 % skew). Showing an approximate mm:ss is fine. Deep links ("watch
  this point") need the real PTS. That is a §11-legal addition: record the
  decoder's PTS as one more observation in the diag dump. Phase 4.
* **Vocabulary:** `action ∈ {serve, dig, set, spike, overpass}` today, with
  `block` and `ball_handling` reserved (block is not a label yet; ball
  handling comes from overrides). `outcome ∈ {ace, kill, error}`.
  Fantasy: errors = serve + attack + **set/dig ball-handling** errors. That
  is G1, and it fixes the open 32f gap in the SQL. Fix
  `postrun.player_stats` too (small), so the parity test agrees.
* A parity test (`tests/test_publish_bundle.py`, real match when on disk)
  pins: SQL-equivalent box score from the bundle == `player_stats` on
  20260920 (A 21–B 12, 208 credited rows = the ratified per-player GT CSV).
  The same bundle built twice gives the same hash.

---

## 6. Security checklist

1. RLS **enabled on every table**, and every policy is `to authenticated`.
   Table privileges are explicit (`20261007120000_explicit_grants.sql`):
   `anon` holds none, `authenticated` writes only the admin-owned tables
   and columns, and a new table or view gets nothing until its migration
   grants it. The grant is the first gate, RLS the second.
2. The secret (service-role) key exists only on the laptop
   (`.env.publish`, git-ignored, mode 600 or the publisher refuses it; or
   macOS Keychain). It is never in `webapp/` and never committed.
3. `ingest_match_bundle` is executable by `service_role` only (revoke
   `public`). Aggregate functions check `auth.uid() is not null`.
4. Storage buckets `match-bundles` and `match-media` are private.
   Thumbnails are served with short signed URLs.
5. Admin-only data lives in admin-only tables (`match_sources`,
   `match_publications`), because RLS cannot hide a column.
6. Players change their own privacy through an RPC (`set_my_privacy(bool)`),
   not a table UPDATE, so they can't edit other columns of `players`.
7. RLS tests: `supabase test db` (pgTAP) checks that a viewer can't read
   drafts, other matches' touches or `match_sources`, and that an admin can.
8. The site sends a content security policy and refuses framing
   (`webapp/public/_headers`): only its own bundle runs, and it talks only
   to Supabase. A new third-party host has to be listed there.
9. Membership is the Supabase *Allow new users to sign up* switch (off):
   every logged-in account reads the league tier. It is a dashboard setting,
   not code, so the deploy checklist (step 2.4) verifies it on the real
   project.
10. Asking for a login code gives one answer for every email. The form calls
    the edge function `request-login-code`, never Auth: the function always
    answers `{"ok": true}`, the database gate (`login_code_gate`, service key
    only) applies the rate limits and says whether the address is an accepted
    account, and only then the function asks Auth for the mail. Auth's own
    public endpoints are locked on the hosted project with a CAPTCHA secret
    that no page has a widget for (deploy step 2.9); requests with the
    service key skip that check. Wrong code and unknown address already get
    the same answer from Auth's verify endpoint.

---

## 7. Repository layout (as built)

```
supabase/config.toml                    # local stack; sign-ups off; email templates
supabase/migrations/20261006120000_init.sql     # schema, RLS, views, RPCs, G1 seed
supabase/migrations/20261006120100_storage.sql  # private buckets + admin read policy
supabase/checks/rls_smoke.sql           # behaviour check (rolls back); plain_postgres_stub.sql
supabase/templates/                     # magic-link (with the login code) + invite emails
src/publish/                            # naming, bundle (pure), fantasy, thumbs, client, cli,
                                        #   inbox (Drive runner), backup
ops/launchd/                            # inbox every 30 min + weekly backup; install.sh
webapp/                                 # Vite + React + TS SPA (Cloudflare Workers root)
.github/workflows/                      # supabase-keepalive (every 3 days), webapp CI
Makefile                                # calibrate, process, publish, inbox, backup, schema-check
tests/test_publish.py, test_inbox.py, test_supabase_schema.py
```

---

## 8. What was verified in the build session

* **Migration on a scratch PostgreSQL 16** (stub `auth`/`storage` schemas
  and Supabase's three roles). `supabase/checks/rls_smoke.sql` passes:
  - publish applied → unchanged → applied; assignments survive
  - a different video is refused
  - G1 fantasy, including the ball-handling error (open 32f)
  - a rule edit rescores; a cloned rule set activates; two active sets are
    refused; a viewer can't switch scoring
  - every access tier holds (drafts hidden, touches participant-only,
    `detail_public`, opt-in analytics, viewers can't edit, no hard delete)

  A deliberately broken expectation fails the check.
* **Publisher parity:** a bundle built from a real `src.postrun`
  reconstruction of the simulated match has credits, assists and fantasy
  equal to `postrun.player_stats`, and the SQL `player_match_fantasy` equals
  them too after ingesting through the RPC.
* **Publish CLI end-to-end** (real HTTP client → stand-in gateway → scratch
  DB): dry-run diff, applied, unchanged, the video guard with its dry-run
  warning, `--replace-video`, a bad key logged as `failed`.
* **Web app:** typecheck, lint and unit tests pass, and it builds. The demo
  build was rendered in Chromium at 1280 px and 390 px on all 11 routes:
  no console errors, no horizontal overflow.
* **Not verified here:** the hosted Supabase project, its Auth emails,
  Cloudflare, Drive/rclone and launchd. These need the owner's accounts;
  each step in `docs/deploy_web_platform.md` ends with a check.

Caveat to keep in view: the post-run layer is validated on **one** 21-point
match (open point 32b). The first matches through this flow are also its
generalization test. That is why everything lands as a draft and re-publishing
is cheap.

Next (not built): `action_overrides` + UI for manual corrections, in-app
invites (Edge Function), lateral `own_x_m` from the dump for 2-D heatmaps,
PTS in the diag dump for per-point video links, uploads through the web
(Supabase Pro), multi-set matches.

---

## 9. Owner decisions (ratified 2026-10-06)

| # | Decision | Ratified |
|---|---|---|
| D1 | Video intake | Google Drive inbox + rclone; **no Telegram** (macOS notifications) |
| D2 | Privacy tiers (§4) | as proposed: league = results + box scores + fantasy; match detail = that match's players; analytics = self unless opted in |
| D3 | File naming / `match_key` | **`YYYYMMDD_HHMM_<venue>_<text>`** (time added by the owner); the inbox auto-renames |
| D4 | Frontend + hosting | React SPA on Cloudflare Workers |
| D5 | Login | magic link / 8-digit code |
| D6 | Review gate | every new match lands as a draft; an admin publishes |
| D7 | Repo layout | new top-level `supabase/` and `webapp/` |
| D8 | Scoring | **its own tables** (`fantasy_rulesets` + `fantasy_rules`), editable from the admin page |

---

## Appendix A — the migration

The draft SQL that stood here was finalized into
`supabase/migrations/20261006120000_init.sql` (plus the storage migration).
Read the schema there; this document no longer copies it.

Notes on the ingest function:

* `insert … select * from jsonb_populate_recordset(<base>, …)` relies on the
  bundle's keys matching the column names. That is the point (one place to
  add a field), and the phase-1b test checks it.
* `points` and `actions` must keep **no generated columns** for `select *` to
  work.
* A key missing from the bundle takes the **base record's** value, never the
  column DEFAULT. That is why the base carries `match_id`, `set_no`, `flags`
  and `is_assist`. The bundle builder still emits every key explicitly.

**Smoke-tested 2026-10-06 on a scratch PostgreSQL 16** (stub `auth` schema
and Supabase's three roles; not Supabase itself). Results: the migration
applies; publish → `applied`, same content → `unchanged`, changed content →
`applied` with admin slot assignments kept; a different video under the same
name is refused; a viewer sees no drafts, can't call the ingest, sees touches
only of matches they played (or `detail_public`), and gets the
leaderboard. The `null::points` base of the first draft broke on the missing
`set_no`, which is what the base-record note above fixes.

---

Sources for the platform limits quoted above (checked 2026-10-06): Telegram Bot
API (`getFile` 20 MB; updates kept 24 h; local Bot API server up to 2000 MB),
Telegram client limits (2 GB / 4 GB Premium; "send as file" skips compression),
Supabase Storage file limits (free 50 MB; Pro up to 500 GB), Supabase free
tier (pause after 7 days inactive; 500 MB DB; 1 GB storage), PyTorch macOS
x86_64 deprecation (last wheels 2.2.x).
