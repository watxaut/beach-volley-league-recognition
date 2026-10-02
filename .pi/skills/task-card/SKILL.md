---
name: task-card
description: Write or audit an executable task card in STATUS.md's "Next task cards" section so that a cheaper LLM can run it via /next-task without inferring work. Use at the end of a planning/review session, whenever the next step is handed to another (smaller) model, or when asked to "queue", "brief" or "card" the next task.
---

# Task cards — briefs a cheap executor can run without guessing

A **task card** is the whole brief for one session of work. It lives in
`STATUS.md` under `## Next task cards` (between *Where we are* and *Open
points*). The executor prompt `.pi/prompts/next-task.md` (`/next-task`) takes
the first `READY` card and does exactly what it says. Anything the card leaves
open, the executor must STOP on, so a vague card produces a stalled session,
not a creative one. That is intentional.

Who writes cards: a planning or review session (frontier model or owner). An
executor never writes or reorders cards. It only flips its own card's status.

## Card template (copy exactly, fill every field)

```markdown
### CARD <ID> — <imperative title>, <"no `src/` change" if true>
- **status:** READY | BLOCKED (<what unblocks it>) | DONE (#<session>): <verdict — numbers>
- **type:** measurement (diagnose-only) | implementation (A/B) | owner-gate | housekeeping
- **goal:** <one sentence: what decision or metric this moves, open point N>
- **why:** <1-2 lines + the doc/section with the evidence>
- **read first (nothing else):** AGENTS.md; this card; <exact files + function names>
- **may create:** <exact paths/globs>
- **may modify:** <exact paths; STATUS.md "only the edits listed below">
- **must not touch:** <src/, ground_truth/, held-out inputs, ... explicit>
- **steps:**
  1. <one concrete action with the exact command line>
  2. **Gate G1 (<name>):** <objective check>. If it fails: STOP, report.
  3. ...
- **pre-registered decision (<the fixed parameter>, not re-tunable):**
  - **PASS** = <numeric thresholds>
  - **FAIL** = anything else. Report it as REFUTED; do not try another variant.
- **deliverables:** <files, each with what it must contain>
- **STATUS edits when done:** <exact list; always "do NOT write a new card">
- **stop and ask if:** <the situations where guessing would be tempting>
- **est. cost:** <decode minutes + coding hours>
```

## Rules for the writer

1. **One mechanism, one card.** If you need "and then", it is two cards.
   Mark the dependency in `status` (`BLOCKED (needs SR1c DONE)`).
2. **Every command is literal.** Full `venv/bin/python …` lines with real flags.
   Check each flag exists (`grep add_argument`) before writing it. Long decodes
   get `nohup … &` plus a poll line.
3. **Every name is real.** Functions, fields, config keys and paths must be
   grepped in the current tree. Cite the function the executor must IMPORT
   rather than re-implement (scorers, court tests, loaders).
4. **Pre-register.** The decision rule, its one parameter value and the
   PASS/FAIL thresholds are fixed in the card before any data is seen.
   Sensitivity values may be reported but "decide nothing".
5. **Gates before results.** Put a reproduction or parity gate first (the run
   reproduces the shipped artifact; a recomputation reproduces the dumped
   field). A failed gate means STOP, never "adjust".
6. **Scope fences are explicit.** `may create` / `may modify` / `must not touch`.
   `src/` is untouched unless the card is an approved implementation card that
   names the owner decision that approved it.
7. **Owner gates are cards too** (`type: owner-gate`, `BLOCKED`). An executor
   that reaches one stops.
8. **Protocol constraints come from AGENTS.md, not from memory:** no seek on
   VFR (§9), one session per tree / one decode at a time (§8), entreno A/B +
   byte-identical neutrality for `src/` changes (§1, §3), `ball_confidence`
   0.15, the held-out lock in STATUS *Where we are*.
9. **Cheap-model sizing.** ≤ 8 steps, ≤ ~2 h of work. If bigger, split.
10. **Close the loop.** The card says exactly which STATUS lines the executor
    edits when done, and always ends with "do NOT write a new card".

## Audit checklist (run before committing a card)

- [ ] every path / function / flag / config key grepped in the current tree
- [ ] at least one objective gate with a STOP action
- [ ] PASS/FAIL thresholds numeric and fixed; parameter value fixed
- [ ] scope fences list `src/`, `ground_truth/`, held-out inputs explicitly
- [ ] no step says "investigate", "improve", "tune", "as needed", "etc."
- [ ] STATUS edits on completion are listed; "do NOT write a new card" present
- [ ] dependencies and owner gates are expressed in `status`
