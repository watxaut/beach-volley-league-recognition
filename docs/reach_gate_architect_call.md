# Architect memo (tier-2) — the CONTACT_REACH gate: relax, reshape, or leave it

**Provenance.** Session #71 (2026-10-02). Delegated via `scripts/run_task_openrouter.sh`
on a **531-byte pointer** `/tmp/reach_arun.md` (the child reads `/tmp/reach_brief.md`,
the brief) — route #4 for tier-2 mechanism design. Run log:
`logs/architect_reach_run.log`; raw memo: `/tmp/reach_design_memo.md`.
Model: `stealth/space-bunny-alpha` THINK=max (deepseek first attempt died with no
output; the anthropic/opus route is credit-blocked for large `max_tokens`).

**Brief.** `/tmp/reach_brief.md` — 8 questions on whether `CONTACT_REACH = 140.0`
(`src/recognition/action_classifier.py:53`) should be relaxed, reshaped (pose /
scale / kind), or left alone; which corpus selects the parameter; how the
team-attribution side effect constrains it. Evidence base: `docs/g3_reach_gate_bucket.md`.

**Coordinator's verification of the memo's code claims (own greps, this session):**

* `CONTACT_REACH = 140.0` at line 53 and `SERVE_REACH_PX = 160.0` at line 158 exist
  and are read as **class attributes** (`reach = self.CONTACT_REACH`, line 416;
  `reach = self.SERVE_REACH_PX`, line 419) — so a `src/`-free A/B harness CAN
  monkeypatch `ActionClassifier.CONTACT_REACH` at runtime. **This is the memo's
  most actionable claim and it is CORRECT.** It means the scalar arm can be
  measured today without a `src/` change (T5 `departure_gate_harness.py` precedent),
  and only the SHIPPING would need owner ratification.
* `_closest_player_at` (line 1018) computes `d = self._point_to_bbox_distance(point,
  s.get("bbox"), s["center"])` per candidate (line 1093) and returns
  `(best, best_dist, lr_index)`; the gate compares that distance at line 420. So the
  reach test's *input* is a bbox distance, not a pose distance — the memo's proposed
  hand-anchored variant is a genuine reshape, not a threshold tweak.
* Each `_player_pose_history` snapshot DOES carry the full pose dict
  (`{"frame", "pose", "center", "bbox", "team"}`, line 378-383), and
  `pose_estimator._process_landmarks` returns `keypoints_dict` keyed by MediaPipe
  index with `x/y/visibility` — **wrist/hand indices are 15 and 16** (`arms:
  [13, 14, 15, 16]`, `src/recognition/pose_estimator.py:55`). So the pose-anchored
  variant is implementable with data already in the snapshot. **Verified.**
* The pose gate that would supply those snapshots is `pose_gate_stale_frames` (30)
  and `pose_near_ball_radius_px` (300.0) — both real config keys
  (`src/utils/config.py:139`). **Verified.** The memo's abstain-on-absence rule is
  therefore implementable.

PLAIN SUMMARY:
The rule that throws a contact away when the ball is too far from the nearest
player is a real, measured cause of missed touches: a discarded row is about
ten times more likely than chance to sit next to a touch we missed. But simply
widening the distance number buys at most about eight points of action
correctness, nowhere near the accuracy goal, and it would likely invent
phantom contacts on the practice videos and keep assigning the wrong team.
I recommend against widening the number. I recommend changing what the number
is measured against: when the player's hands can be located, judge the ball
against the hands, and only fall back to the body box otherwise. A touched
ball is always beside the hand no matter how small or far the player looks, so
this is the same test at every venue and it directly targets the recorded
failure where the toucher was mid-jump. Cost is one practice-video run to gate
it plus one match run, roughly an hour of compute. The unknown is the team
assignment, which this does not fix and which the run must measure.

DECISION:
Replace the fixed 140-pixel ball-to-nearest-body-box reach test with a
pose-anchored reach — accept a contact when the ball is within the existing
140-pixel box distance OR within a body-relative hand distance of a confident
hand/wrist keypoint of the chosen player, falling back to the box-only test
whenever pose is absent or stale — and ship it only if a real practice-video
A/B clears the pre-registered bar.

WHY:
- The gate is 9.78x enriched for the 20 recoverable misses (g3_reach_gate_bucket
  §2); it is the first link of recall -> touch count -> label, and a perfect
  touch count is worth +0.244 on the 127 non-serve contacts
  (g3_touch_count_lever §3).
- The lever's ceiling is only +0.08 total-correct and ~0.00 class accuracy
  (g3_reach_gate_bucket §4, §8), so it must be spent without new false contacts;
  the raw scalar at 2.0x admits 6 false of 21 on the drills (§7) and is
  venue-coupled (court projects 206 vs 464-479 px deep, AGENTS.md §7).
- 14 of the 20 recoverable misses are `bounce` and the recorded exemplar
  (e2 f167) is an airborne toucher whose body box is displaced upward — a hand
  keypoint is the scale-free correct anchor (STATUS open point 7).

MECHANISM:
- Layer: recognition contact gate inside `ActionClassifier`
  (`src/recognition/action_classifier.py`), the reach test at lines 410-424 and
  the distance call inside `_closest_player_at`.
- Signal: keep `_point_to_bbox_distance` as the baseline. Additionally, when the
  chosen player's snapshot has pose in `self._player_pose_history` with a
  wrist/hand keypoint at confidence >= the pose estimator's threshold, use
  `min(bbox_distance, distance(point, nearest_confident_hand_keypoint))`.
- Threshold: the box fallback is UNCHANGED — `CONTACT_REACH = 140.0` px
  (line 53) and `SERVE_REACH_PX = 160.0` px (line 158) stay as they are. The
  hand reach is body-relative: `0.5 x bbox_width_px` (inferred: a hand cannot
  be more than a half-body from a ball it touched). No absolute px scalar is
  introduced or tuned.
- Default-OFF, A/B-toggleable: guard the new branch behind a class constant
  (e.g. `CONTACT_HAND_REACH = False`). When pose is absent, stale
  (`pose_gate_stale_frames`), or the player is outside `pose_near_ball_radius_px`
  (300, src/utils/config.py:139) so no snapshot exists, the code ABSTAINS and
  reverts to the 140-px box test — never guesses.
- Where: the distance computation in `_closest_player_at` reads pose; the gate
  at line 420 compares against the returned distance. No new `Config` key, so
  the `--config` path and the config-drift guard are untouched.

REFUTATION TEST:
- Arms: A = control (`CONTACT_HAND_REACH=False`, current behaviour), B =
  pose-anchored. Same code path, one class constant apart.
- Step 1 (gate; ~10 min MPS): all 7 `resources/video_entreno_*.mp4` plus
  `resources/video_ari_joan_8_first_points.mp4`, with a NON-serve control
  window. Base arm A must first reproduce the recorded
  `evaluate --ignore-player` F1 within +-0.02 (e1 0.706, e2 0.571, e3 1.0,
  e4 0.933, e5 0.923, e6 0.933, e7 0.75; STATUS entreno gate record). If it
  does not, STOP — that is a harness mismatch, not a result.
- Step 2 (~50 min MPS): the 20260920 match, held out. Metrics: held-out contact
  P/R/F1 (base 0.785/0.760/0.772), class accuracy (0.589), team raw / squad
  (0.518 / 0.755); plus team precision of the newly admitted rows.
- PASS: at least +5 recovered correct held-out contacts (>= +0.03 contact F1),
  with no drill F1 drop greater than 0.02 vs arm A and no increase in
  control-window false actions, AND admitted-row team precision above 0.43
  (the 1.2x level, §10).
- FAIL ("does not work"): held-out contact-F1 gain below +0.02, OR any drill F1
  drop above 0.05, OR admitted-row team precision at or below 0.43. A refutation
  is a valid result: revert and leave the scalar at 140 px.

NEUTRALITY:
- e3 and e6 have ZERO reach rejections (§5), so arm B must be byte-identical to
  arm A there — the pose branch must not change any admitted contact's emitted
  fields. Prove it by diffing the emitted action lists (frame + label + team +
  player) in both arms' `pipeline_output.json` for e3 and e6; any video with no
  pose-anchored admission is trivially identical. A multi-video, multi-tracker
  A/B harness MUST call `cv2.setRNGSeed(0)` per `PlayerTracker` instance
  (AGENTS.md §3) or the k-means bootstrap diverges. Byte-identity on ALL drills
  is NOT achievable by a scalar relaxation (a 1.3x gate admits 3 on e2 and 1 on
  e4, §5) — that is a further reason to prefer the pose form, whose change is
  confined to frames where a hand genuinely sits near the ball.

ROLLBACK:
- Revert the pose branch in `_closest_player_at` and delete the
  `CONTACT_HAND_REACH` constant in `src/recognition/action_classifier.py`; no
  other file is touched. Ensure no `contact_reach`, `hand_reach_px` or
  `contact_hand_reach` key survives anywhere in the config surface (none exists
  today; `--config` cannot reach the gate, so a clean `src/` is sufficient). Do
  not extend the config-drift guard, because no `Config` key is added.

PROTOCOL IMPACT:
- STATUS.md: on completion, update open point 7 (action-recall residuals) from
  "needs jump-aware reach/ghost handling" to "pose-anchored reach tested,
  verdict ..." and append the A/B numbers to the reach-gate entry.
- AGENTS.md: none required — no new config key and no architecture change. If
  the class constant ships, add one line beside the `CONTACT_REACH` note in the
  ActionClassifier invariant.
- config-drift guard: none (no Config key added). GT README: none.

RISKS + WHAT I AM UNCERTAIN ABOUT:
- Team side effect: pose anchoring does not change `_attribution_target`; the
  wrong-team default (across all 71 rejections `target_team` is B 64 / A 6, §10)
  may still dominate, so the net goal effect is ambiguous and MUST be measured,
  not assumed. Pose may not improve team precision at all.
- The 0.5x bbox-width hand radius is inferred, not measured; the drill A/B may
  show it admits bystander hands, adding noise.
- The pose snapshot may be absent exactly when it is needed (ball untracked
  beyond the staleness gate, or a player outside the 300-px near-ball radius),
  in which case the fallback silently hides the fix. The A/B must count how many
  of the 20 recoverable misses actually had a confident hand keypoint.
- The match's OWN dev split admits zero-GT contacts at every threshold (§7), so
  selection must rest on the standalone dev clip + 7 drills (27 rejections,
  91 GT) and generalisation rests on a single out-of-sample result (32/36,
  §7) — one A/B may not be decisive.
- The entire lever is only +0.08 total-correct (§4, §8). If the owner's
  priority is the class-accuracy half of G3 (128 of 183 = 0.70), this change is
  not the path and should be deferred behind the label-correctness work.
