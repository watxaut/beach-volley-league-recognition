---
description: A/B validation of action-logic changes on the entreno drills
argument-hint: "[what changed]"
---
Validate ${@:-the current change} on the entreno practice videos (resources/video_entreno_*.mp4 — single-point drills, GT in ground_truth/).

Non-negotiable protocol (from AGENTS.md):
1. One mechanism per session — no stacked changes.
2. Diagnose first: probe raw detector output before calling anything a detection-recall gap.
3. A/B baseline vs change, and prove byte-identical neutrality on videos the change must not affect.
4. Compare detection / ID consistency / action metrics against GT; report per-video deltas vs the numbers recorded in STATUS.md.
5. cv2.setRNGSeed(0) per PlayerTracker instance in multi-tracker A/B harnesses (cv2.kmeans consumes the process RNG).
6. --debug-live must run the exact batch code path — no divergent fast paths.
