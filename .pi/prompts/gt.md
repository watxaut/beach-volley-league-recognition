---
description: Propose a GT edit via owner-ratified contact sheets (no direct edits)
argument-hint: "<video> <frames or what to check>"
---
Prepare a ground-truth edit proposal for $@ — but make NO GT change yet:

1. Generate contact sheets (annotate_player_gt.py where applicable) for the frames in question.
2. Present the evidence — frames, current label, proposed label, and the mechanism/reasoning — and ask for explicit ratification.
3. Only after I ratify: apply the edit, recompute any cascading labels, and update the GT README plus verify_action_labels.
