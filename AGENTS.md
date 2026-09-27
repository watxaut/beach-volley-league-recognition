# AGENTS.md

Instruction file for the ZCode harness. This project is migrating from the
Claude Code harness; the project memory below was carried over verbatim and
must survive future edits.

## Read-first rule (every session)

1. **`STATUS.md`** — the cross-session memory: current state, ranked Open
   points (treat as the backlog), per-session log. Read it before planning
   any work; update it at the end of every session that changes anything and
   commit it with the work.
2. **`CLAUDE.md`** — full architecture, commands, config conventions, GT/eval
   docs. It is kept as the reference even though this harness does not load
   it automatically; its guidance applies unchanged.

## Project memory

### 1. entreno validation protocol

If not told otherwise, always double-check any changes to the action logic
with `resources/video_entreno_*.mp4`. These are practice videos consisting of
only 1 point out of the 21. All except `entreno_1` have a serve; all others
start with a serve and end the point. Ground truths exist in `ground_truth/`.

The video_entreno_* clips are drills, not matches — but the early "they can't
validate re-ID" call was wrong twice:

- 1c appearance re-acquisition broke the detection ceiling on entreno_1
  (dropped-player frames 29.7%→0.8%, coverage 78%→93.7%).
- Then GT annotation exposed that some of that coverage was fake — far-side
  tracks were being fed out-of-court bystander detections. Fixed via
  court-membership enforcement in `_may_feed_track` (detection 0.65→0.92 on
  entreno_1).
- A "detection gap" for the server was actually tracker admission/gating —
  fixed with bootstrap seed dedup + serve-zone admission (entreno_3 detection
  →0.96, consistency →0.97).
- Lesson: before calling anything a detection-recall gap, probe raw detector
  output. Side changes remain unvalidated until real match footage.

### 2. Live debug must mirror the pipeline

The owner explicitly declined live-debug-only perf work: `--debug-live` must
run the exact same code path as batch — no divergent fast paths, because it
is used to debug the real pipeline (there was already one
eval-vs-pipeline skew bug). Speed up shared components instead. The pose
  near-ball + staleness gates were SHIPPED 2026-09-27 in
  `ActionClassifier`/`FrameProcessor` (byte-identical A/B, see STATUS); the
  still-parked lever is the live-debug producer/consumer display decoupling
  (open point 23) — it must not alter the processing path either.

### 3. Diagnose-first working style

The owner's working style that STATUS demonstrates in every entry but states
nowhere:

- Diagnose first before designing.
- Byte-identical A/B neutrality proof on unaffected videos.
- GT edits only via owner-ratified contact sheets.
- One mechanism per session.
- Gotcha: `cv2.setRNGSeed(0)` is required per PlayerTracker instance in
  multi-tracker A/B harnesses (`cv2.kmeans` consumes the process RNG).

### 4. Player-identity plan

The cross-session plan for consistent 4-player IDs:

- Core design: motion continuity is the primary identity signal;
  colour/uniforms can't be trusted; appearance is a tie-breaker; "exactly 4
  players" rejects bystanders. Side changes need no special handling if IDs
  survive.
- Implemented: 1a (two-zone filter, strict admission, 4-cap), 1b (dormant
  gallery, eviction-on-demand), 1c (ground-plane body size + ensemble
  signature), plus the later GT-validated mechanisms — bystander guard +
  serve-zone admission + seed-dedup (08-16), server vote + trial expiry +
  contested swap (08-18), off-court hold horizon =90f (08-29).
- Status: side-change validation still BLOCKED — no set-to-21 footage;
  Phase 2 (global stitch) sketched, unbuilt; `annotate_player_gt.py` ready
  for when footage arrives.

### 5. Attribution signals — long-axis camera

Safety-critical distinctions for contact attribution in this camera geometry
(fixed camera on the court's long axis, net facing the camera):

- Image-plane ball side: unusable (airborne near-half balls project "far").
- Ball pixel width + possession alternation: the working side signal
  (~14–28px far / ~30–55px near, abstain 26–35px).
- Near-net: attribution exemption in ground metres (2.5m) — but the gesture
  path's px `near_net` is load-bearing; px→m is GT-refuted (F1 0.929→0.857),
  revisit only with match footage.
- Emitted team = toucher's per-contact foot team.
