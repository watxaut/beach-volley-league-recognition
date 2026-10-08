# Stats & fantasy feature brainstorm (session #91, 2026-10-06; "Now" built in #92)

Owner ask: brainstorm new stats and fantasy features (position heat maps by
possession, an attack start → end map, a net-view chart of attack heights, a
betting-style fantasy, time filters / seasons / progress), add new ideas, and
be honest about what the camera can really measure. **The owner picks Now /
Next / Never per ID**; picked items then go to STATUS (Active next, open points
or task cards).

**Status (2026-10-08, session #98): hard / touch is shown.** The post-run read (#97) met the V1 bars, so
the Attack map draws the shot as the line (heavy = hard, dotted = touch, dashed = free ball, thin = spike not
read; colour stays the outcome) with a Shot filter, and a "By shot" card splits every attack into hard / touch /
free ball / not read with attempts, share, kills, errors and hitting %. Grade B: in-sample on one match, and a
flat poke reads hard. `player_profile` counts a type only on a row with `extra.launch`, so a match published
before #97 reads "not read" until it is re-published.

**Status (2026-10-08, session #96): player page v2.** O2 is built as the *Attack map*: a line per
attack from the contact point (`own_x_m` / `own_y_m`, on every touch since #91, so I3 was already
half done) to where the ball came down or was dug, colour = outcome, dashed = free ball; hard / touch
stays off (V1 below). New, not in the lists: **"you vs the league" and "you vs your earlier matches"**
(strips per stat from league-tier counts, a verdict only when the 95 % ranges do not overlap), and
grades moved from a letter per tile into each stat's hint. Still open from O2: kill / error ends (I6).

**Status (2026-10-07, session #92): the "Now" picks are built** (see the table below);
V1 and V2 were run and both **fail** their pre-registered bars, which changes the
"Next" list (O3 shows relative heights only; hard/touch is not shown).

| Pick | Built as | Where |
|---|---|---|
| O4 + I1 | `?w=` filter (all / last 3·5·10 matches / last 7·30·60 days / season); SQL `window_matches`, `leaderboard(…)`, `player_profile(…)` take season, from, to, last N (league's N on the league, the player's own N on a profile) | migration `20261007100000`, `WindowPicker` |
| H1 | `k/n` on every rate, percentage from 10 attempts (`MIN_N`), 95 % Wilson range, rolling-window trends with a band, leaderboard ranks a rate only from the minimum | `lib/stats.ts`, `Rate.tsx`, `Charts.tsx` |
| H2 | blocks read "not measured"; the Block rule is flagged on the scoring page | `PlayerPage`, `AdminScoring` |
| H3 | `/measure` page: what the camera reads, how well, A/B/C badges on every stat, the V1/V2 results | `Measure.tsx` |
| N1 | side-out %, break-point % (own serve, team serving, team receiving; per team in a match) | `player_profile`, `match_report` |
| N2 | serve targeting (who took each serve; share of the serves aimed at your team that you took) | same |
| N3 | reception outcome: the possession after your reception became a spike / free ball / error / nothing; first-ball kills | same |
| N4 | hitting % `(K − E) / attacks`, split reception vs transition attacks | same, leaderboard column |
| N8 + F3 | match report card: MVP, each player vs their own average, fantasy per 21 points, side-out / break, serve targets, per-point fantasy race with best point (play-by-play viewers only); form (newest 5 matches) | `MatchReport.tsx` |
| I2 | `make republish-all` (`DRY=1` lists): post-run + publish for every run with a `match_bundle.json`; a run whose diag dump is gone is skipped and fails the command | `src/publish/republish.py` |
| V1 | `scripts/score_spike_type.py` | **FAIL**: a type is published for 16 of the 32 owner-labelled spikes (coverage 0.50, bar 0.80), right on 10 of those 16 (0.625, bar 0.85). 25 of 63 post-run attacks have any causal record. The hard / touch encoding is dropped. **#97 (2026-10-08):** a post-run read (`src/postrun/attack_shape.py`, launch elevation + speed in metres) types 29 of the 32, 26 right (0.906 / 0.897) → both bars met, but in-sample (its two constants were chosen on these labels); practice clips 6/6 on 6 of 8. The publisher now sends that type; the web shows it since #98 (map line style + "By shot", grade B). |
| V2 | `scripts/check_heights.py` | **FAIL** overall, so O3 may not say "±0.2 m". Net: PASS — 33 live, well-conditioned crossings, all at or above −0.15 m of the tape, median +0.61 m. Stature: far half reads 5–6 % shorter, P2A 12 % (FAIL; real heights not given yet). Contacts: spike 2.52 / 2.51 m near / far, set and overpass agree, **digs 1.37 vs 1.66 m (0.29, FAIL)**. |

How V2 was run: bars fixed first (see the script's docstring). The first run
scored every net crossing and failed on dead-time balls rolling on the sand
(−2.3 m under the tape) and on crossings whose height is wrong by timing alone;
both filters were added after seeing that, bars unchanged, and the unfiltered
numbers are still printed. Owner input still wanted: the four real heights
(`--heights P1A=1.80,…`) for the absolute stature check.

Not touched by this session: everything marked Next / Later / Park below.

Below this status block the original brainstorm is unchanged
(only the title carries the "built in #92" note). The numbers come from the 20260920 match (the only full
match so far), its owner-ratified per-player CSV
(`ground_truth/20260920_match_reconstruction_player_review.csv`), the owner
contact GT (`ground_truth/20260920_match_contacts.json`) and two calibrations
(beach match, practice `video_entreno_3`). The geometry figures were computed
this session with `src/postrun/geometry.py`.

---

## 1. What the camera can and cannot measure

| Quantity | How it is read | Precision | Grade |
|---|---|---|---|
| Points, server, winner, score, side switches | post-run rules (`src/postrun`) | 33/33 on the match | **A** |
| Who touched (slot P1A…) | reach + alternation | 208/208 owner-ratified, 0 corrections | **A** |
| Action label (serve/dig/set/spike/overpass) | touch structure + contact height | 0.982 | **A** |
| Outcome (ace / kill / error) | who serves next | winners 33/33 | **A** |
| Touch coverage | — | recall 0.933: about 1 touch in 15 is missing or uncredited, so **counts are lower bounds** | A, with that caveat |
| Left–right position (along the net) | pixel column | 3 px of jitter = 3–4 cm at every depth (beach) | **A/B** (real limit: box and blur, a few cm to a dm) |
| Ball / contact height | ball row vs the ground row at its depth | net tape reads 2.43 m (beach) / 2.42 m (practice). A 1.3 m depth error moves a 2.8 m contact by ±0.15 m on the beach and ±0.01 m at practice. **No direct ground truth yet** | **B** |
| Player feet, depth (toward / away from the camera) | homography of the box bottom | per 3 px of box jitter: near baseline 0.09 m, net 0.34 m, **far baseline 0.76 m** (beach); far baseline 0.29 m at practice (higher tripod) | **B** near half, **C** far half |
| Ball depth | ball pixel width | 1 px of width = 0.64 m at the net, 1.23 m at the far baseline; fitting whole flights helps; balls in play read ~1.3 m nearer the lens | **C** for a single point |
| Landing spot, in / out | the ball's ground read | exists on 17/33 points; line calls 7/10 right (open point 31) | **C** |
| Hard vs touch spike | causal `SpikeAnalyzer` (post-contact ascent) | 6/6 on practice spikes. The match GT has **32 owner-labelled spikes (13 hard, 19 touch), not scored yet** | **unknown** |
| Durations, speeds | frame / fps | VFR camera: up to ~17 % off wall time until the decoder's timestamps (PTS) are recorded | **C** |
| **Not measured at all** | — | blocks, ball-handling faults (double / lift), pass quality, ball speed (no ground truth) | — |

Two consequences shape everything below:

1. **Left–right is the precise axis; depth is the weak one, worst on the far
   half.** Charts that live on the left–right axis (line vs cross, the net
   view of attack heights, serving lanes) are honest. Charts that need an exact
   depth (how deep a ball landed, exact far-side positions) are not, unless
   they are coarse. A higher tripod on the beach would sharpen every
   depth-based stat: at the practice venue the camera sits much higher (the
   court projects 2.3× deeper in pixels) and its far-baseline depth is 2.6×
   sharper. That is an option for the owner, not a requirement (AGENTS §7).
2. **Sample size limits us more than geometry does.** Per player per match:
   5–14 serves, 7–13 spikes, 13–17 digs, 10–15 sets. A kill rate of 4/10 is
   anywhere between 17 % and 69 % (95 % Wilson interval); 20/50 is 28–54 %;
   40/100 is 31–50 %. Per-match rates are mostly noise, so trends need rolling
   windows over many attempts.

---

## 2. Owner ideas, assessed

### O1 — Position heat map, with and without possession

* **What:** density of each player's feet (box bottom → court metres, in the
  player's *own* frame so side switches don't mix halves), split by phase:
  we serve / we receive / our possession (ball on our half) / their possession
  (ball on their half). Dead time is excluded.
* **Data:** the diag dump already has every player's box and P1A… label per
  frame, and the reconstruction gives the phases (touch frames and sides).
  Nothing new to perceive.
* **Honest limits:** left–right is sharp; depth is fine on the near half and
  about ±0.8 m at the far baseline on the beach. A jumping player reads deeper
  (the feet leave the sand), so drop the frames around their own contacts or
  use the pre-contact stance as post-run already does. Exclude carried-forward
  (predicted) boxes. Brief identity swaps are allowed by the identity
  contract, so expect a little contamination.
* **Recommendation:** 1 m cells or a smoothed density, not a fine map; a
  "near half only (sharpest)" toggle. Self-check before shipping (V3): the
  same player's map from near-half points and from far-half points should
  agree. If they don't, the far-side depth is lying.
* **Storage:** aggregate at publish time (match × slot × phase on a 1 m grid,
  ~80 cells), never raw frames to Supabase.
* A sharper version of the same question is **N12** (where were you at the
  moment the opponent attacked?).
* Grade **B**. Cost: medium (bundle + new table + court component).

### O2 — Attack map: start → end, hard/touch, kill/dug/error

* **Start:** the contact point. Left–right from the ball (precise); depth from
  the flight fit or the attacker's stance (±0.3–1 m). Good enough for an arrow.
* **End**, three cases:
  * **Dug:** where the defender played it (the next touch). Available on every
    attack the opponent touched, but it is "where it was played", not where it
    would have landed.
  * **Kill / error with a ground read:** the landing spot, only where the
    ball's death was seen (17/33 points on the match).
  * **Kill / error without one:** no arrow end. List them under the court
    ("3 attacks without a landing") rather than inventing one.
* **Outcome** (kill / dug / error) is reliable (A). **Hard / touch** is
  unmeasured on the match: run V1 first.
* **In/out:** never draw an error as "out" from the line call (3/10 wrong).
  The outcome comes from the score; the dot position is approximate.
* **Encoding:** colour = outcome (the reliable field), line style = hard
  (solid) / touch (dashed). Or the owner's red/yellow for hard/touch if V1
  passes. Add a "line vs cross" bar (N10), which needs only left–right.
* **Needs:** I3 (the bundle publishes `own_x_m = null` today); I6 (open point
  31) improves kill/error ends.
* Grade **B** for dug arrows, **C** for kill/error landings until open 31.

### O3 — Net view: attack height, left to right

* **Chart:** the net seen from your side; x = where along the net (0–8 m, from
  your left antenna to your right), y = contact height; the net drawn at the
  height the calibration measures (2.43 m); dot colour = outcome; a line at the
  player's median.
* **Feasibility:** the best-measured of the three ideas. x is cm-precise;
  height is ±0.15 m from the geometry on the beach, and height already drives
  spike vs overpass (net − 0.28 m → action accuracy 0.982).
* **Honest risks:**
  * no direct ground truth of any ball height;
  * contact-frame timing: a hard spike falls up to ~0.4 m per frame right
    after the hit at 25 fps, so a vertex one frame late reads low. Take the
    highest ball in the frames around the contact;
  * a systematic bias: balls in play read ~1.3 m nearer, i.e. ~0.12 m low on
    the beach. It is the same for every player, so comparisons survive it,
    and it can be corrected.
* **Before shipping, V2.** Show heights rounded to 0.1 m and per-player
  medians, labelled "approximate (±0.2 m)" if V2 supports that.
* **Bonus after V2:** jump ≈ contact height − standing reach (entered by the
  player in their profile).
* Grade **B**. Cost: small–medium (I3 + an SVG chart).

### O4 — Time filters, seasons, progress

* **Filters:** last match / 7 / 30 / 60 days / all / season, plus **last N
  matches**, which works better than days when matches are irregular (a
  7-day window is often empty).
* **Today:** `leaderboard(p_season)` takes a season; `player_profile` has no
  filter. Add window parameters (from–to, season, last N) to
  `player_profile`, `leaderboard` and the analytics. `matches.season`
  (admin-owned) already exists.
* **Progress charts, honestly:** plot rates over rolling windows of attempts
  (e.g. the last 30 attacks) with the interval band, not one dot per match.
  Show counts with denominators. Hide a rate below a minimum n.
* **Comparability (what makes "a stat is a fact" true):** when the post-run
  rules change, old matches must be recomputed with the same rules, or a trend
  shows a pipeline change instead of a player change. `make postrun` (3 s) +
  `make publish` does it per match **if the diag dump (49 MB) or the video is
  kept**. So: keep the diag dumps of every published match, keep the pipeline
  version per publication (already stored), add a "re-publish all with
  current rules" command (I2).
* Grade **A**. Cost: small (SQL parameters + filter UI) + I2.

### O5 — Advertised matches + betting fantasy

* **Honest view:** with ~4–10 people the market is thin. Real-money betting is
  regulated gambling (in Spain it needs a licence), so only ever points.
* **F1 — upcoming matches + pick'em:** an admin creates a scheduled match
  (date, the 4 players); members predict the winner and margin before it
  starts (locked at the start time); points for correct picks; a predictors'
  leaderboard. When the video is published it binds to the scheduled match by
  date, time and players. Small–medium (one table, two RPCs, one page).
* **F2 — full draft fantasy** (budget, player prices from rolling fantasy
  averages, lineups per round): only worth it with a bigger pool. Park.
* **F3 — cheap fantasy additions:** form (rolling last 5 matches), a per-point
  fantasy timeline (G1 "per point"), match MVP, fantasy per 21 points played
  (normalises long and short matches).

---

## 3. New ideas

### Stats from facts (grade A, no new perception: SQL + UI only)

* **N1 — Side-out % and break-point %:** rallies won when receiving vs when
  serving, per team, per pair, and per player as server (break % on their
  own serve). The most-used beach stat; needs only the points table.
* **N2 — Serve targeting:** who received each serve (the credited first touch
  after it). "Opponents served you 68 % of the time"; "your serves went to X
  70 %". Beach teams serve the weaker passer, so this is very telling.
* **N3 — Reception outcome (pass-quality proxy):** of the possessions after
  your reception, % that ended in a spike (in system) vs an overpass / free
  ball vs an error; first-ball side-out (point won by the first attack after
  reception). No pass grading needed. Caveat: soft "rainbow" attacks below
  ~2.15 m are labelled overpass (2 on the match).
* **N4 — Attack efficiency:** (kills − errors) / attempts, the standard
  hitting %, split into reception attacks vs transition attacks (after a dig
  of their attack).
* **N5 — Rally structure:** touches per rally, win % by rally length,
  longest rally of the match.
* **N6 — Runs and pressure:** longest scoring run, serve runs, record in
  close endings (from 18–18). Small samples: fun, labelled as such.
* **N7 — Partners and opponents:** record with each partner and against each
  pair, head-to-head pages, optionally an Elo-style rating from results.
  Results are pure facts.
* **N8 — Match report card:** after each match, your stats vs your own
  average, your best rally, match MVP (fantasy), the per-point fantasy
  timeline (F3).
* **N9 — Records and milestones:** career highs (most kills in a match),
  streaks, badges (first ace, 5-kill match, 10 matches played). Cheap
  engagement for a small group, and every badge is a fact.

### Geometry stats (grade B, after the validation cards)

* **N10 — Line vs cross:** the left–right direction of each attack and serve,
  as % line / middle / cross per player and per start zone. Robust even where
  depth is coarse.
* **N11 — Serving lanes:** where along the baseline you serve from and which
  lane it reaches (the receiver's left–right), e.g. "from the right corner,
  60 % down the line".
* **N12 — Defensive role at the opponent's attack:** at the opponent's attack
  contact, each player's stance (0.3–0.6 s before; post-run already reads
  it) → who is at the net (blocking or pulling off) and where the defender
  stands. Gives role % per player and a defender-position map. Depth near the
  net is the decent part of the court (±0.3 m per 3 px on the beach). Blocks
  themselves are still not detected, so "at the net" never means "blocked".
* **N13 — Set height and setter position:** apex of the set's flight (slow
  balls are the best-measured balls) and the setter's distance from the net.
  Exclude flights that leave the top of the frame.
* **N14 — Net clearance:** how high above the tape serves and attacks
  crossed. Doubles as a self-check (V2): no live ball may cross below the tape.

### Validation cards (offline on the owner's laptop, no decode; before any B stat ships)

* **V1 — Hard/touch on the match:** score `spike_type` against the 32
  owner-labelled spikes in `ground_truth/20260920_match_contacts.json`, plus
  coverage (how many post-run attacks get a causal spike record within ±15 f).
  Fix the PASS rule beforehand (e.g. ≥ 85 % right and ≥ 80 % coverage);
  otherwise drop the hard/touch encoding.
* **V2 — Height:** (1) stature: each player's standing height from the video
  vs their real height (the owner knows all 4), which checks the vertical scale
  at player depth; (2) net-crossing heights: no live ball under the tape;
  (3) contact heights by action and per player stay consistent across
  matches. Decides whether O3 may say "±0.2 m".
* **V3 — Positions:** the same player's near-half vs far-half heat map agree
  (O1); foot jitter on standing frames.

### Risky / park (grade C)

* **N15 — Ball speed (km/h):** no ground truth, blur biases the width read,
  and it needs PTS. The most honest version is the average serve speed from
  contact to reception (distance / flight time, ±10–15 %), only once PTS is
  in the dump (I5). Tempting and easy to get wrong.
* **N16 — Distance run / sprints:** box jitter inflates path length (0.8 m
  per 3 px at the far baseline). It would lie. Park.
* **N17 — Video clips ("watch my kills", highlight reel):** very motivating;
  needs real timestamps (I5), clip cutting at publish time and storage
  (Supabase free is 1 GB; Drive or R2 instead). Medium–large.
* **N18 — Animated 2-D rally replay:** it would put the far-side noise on
  display. Park.
* **N19 — Serve type (jump / float / standing)** from contact height and
  toss: no GT; possible later with a small owner-labelled set.
* **N20 — Opponent scouting card** for an advertised match (F1): their serve
  targets, line/cross, side-out %. Cheap once N2/N10 exist.

### UI honesty rules (cheap, apply everywhere)

* **H1:** counts with denominators ("4/10"), a minimum n before a rate is
  shown or ranked, interval bands on trends.
* **H2:** unmeasured stats read "not measured", never 0 (blocks,
  ball-handling faults). The fantasy Block rule (+1) can never fire today; say
  so on the rules page.
* **H3:** a "how we measure" page with the validated numbers (33/33 points,
  208/208 players, actions 0.982, line calls 7/10), the fact that counts are
  lower bounds (~1 touch in 15 is never credited), and a grade badge per stat.
* **H4:** fairness check: credits per player by camera side. Sides switch
  every 7 points so it should even out, but far-side detection is weaker:
  measure it once.

---

## 4. Enablers (shared work several ideas need)

| ID | Enabler | Unblocks |
|---|---|---|
| I1 | time-window parameters in the RPCs | O4 |
| I2 | keep diag dumps + "re-publish all with current rules" | O4 comparability |
| I3 | contact left–right x and the toucher's stance (x, y) per touch in the bundle | O2, O3, N10–N12 |
| I4 | per-match position grids aggregated at publish | O1, N12 |
| I5 | PTS per frame in the diag dump (§11-legal: an observation of an existing value) | N15, N17, honest durations |
| I6 | open point 31: landing read from the resting ball | O2 kill/error ends |

---

## 5. Pick list (suggested slicing; the owner decides)

| ID | Idea | Grade | Cost | Depends on | Suggested |
|---|---|---|---|---|---|
| O4 + I1 | time filters, seasons, last N | A | S | — | **Now** |
| H1–H3 | honesty rules + "how we measure" | A | S | — | **Now** |
| N1 | side-out / break-point % | A | S | — | **Now** |
| N2 | serve targeting | A | S | — | **Now** |
| N3, N4 | reception outcome, attack efficiency | A | S | — | **Now** |
| N8 + F3 | match report card, per-point fantasy, form | A | S–M | — | **Now** |
| V1, V2 | hard/touch score, height checks | — | S (laptop) | — | **Now** |
| I2 | re-publish all with current rules | — | S | — | **Now** |
| I3 → O3 | net view of attack heights | B | S–M | V2 | Next |
| N10, O2 (dug arrows) | line vs cross, attack map | B | M | I3, V1 | Next |
| O1 + I4 | position heat maps (coarse) | B | M | V3 | Next |
| N7, N9 | partners/opponents, records & badges | A | M | — | Next |
| F1 | upcoming matches + pick'em | — | M | — | Next |
| N11–N14 | lanes, defensive role, set height, net clearance | B | M | I3, V2 | Later |
| O2 kill/error ends | landing spots | C | M | I6 | Later |
| F2, N15–N19 | draft fantasy, speed, distance, clips, replay, serve type | C | M–L | I5 and more | Park |
