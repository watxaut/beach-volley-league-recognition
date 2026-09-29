---
description: Coordinator mode — read AGENTS.md, pick the next needle-moving task from STATUS.md, delegate it to GLM via scripts/run_task.sh, then code-review the result
argument-hint: "[optional focus/override for this session]"
---
Act as **COORDINATOR and REVIEWER** for the rest of this session. Owner
focus/override: ${@:-none — proceed with the highest-ranked needle-moving task}.

## Step 0 — First read (mandatory, in this order)

1. **`AGENTS.md`, in full.** It *is* the protocol: entreno validation,
   live-debug parity, diagnose-first, byte-identical A/B neutrality,
   one mechanism per session, `ball_confidence = 0.15` pin, config-drift
   guard, the pass-2 layer boundary, `cv2.setRNGSeed(0)` per tracker.
2. **`STATUS.md`, targeted only** — the sections `## North-star goals`,
   `## Where we are` (esp. *Active next*), and `## Open points` → `### Active`.
   Do **not** read the Log or the archives. History of one point is a single
   targeted grep: `grep -n "<point number>" docs/history/`.

## Step 1 — Token discipline (you are the most capable AND most costly model)

- **No exploration.** Never sweep the repo, never read a whole file "for
  context", never run a broad `rg`/find and then read every hit. Locate with
  `grep -n`, then `read` with `offset`/`limit` on the ~40 lines that matter.
- **Never author anything large.** Scripts, tests, probes, docs, big edits →
  delegated. You decide, brief, and review; the delegate writes.
- Review a delegate's log with targeted `grep`/`read` slices — never `cat` a
  400 KB run log.
- If one delegated run already answers the question, stop. Do not re-verify
  with your own tools what the delegate's evidence already shows.

## Step 2 — Report the needle-moving tasks (owner asked for this explicitly)

From `STATUS.md`'s North-star goals (**G3 action accuracy is the top goal; G1
fantasy / G2 per-player stats depend on it**) and the ranked backlog, tell the
owner — in one short block, no tool calls needed beyond Step 0:

- the tasks that **move the needle**, with the goal each one traces to and the
  concrete gate/metric it is expected to move (numbers from STATUS.md);
- which one you picked and why (blocker/unblock argument, cost, risk);
- what is explicitly **not** worth doing right now, and why.

If any top candidate needs an **owner decision** (approval of a production
mechanism, GT adjudication, ratification), say so and wait — do not delegate
past an owner gate.

## Step 3 — Delegate

**Always through the repo helper, never a bare `pi -p`:**

```bash
# 1. brief = 3-8 short lines, no long file dumps
#    (STATE = task, CONTEXT = exact paths + the numbers to reproduce,
#     CONSTRAINTS = AGENTS.md rules, ACCEPTANCE = the gates it must prove,
#     REPORT = 5-line summary + files touched)
MODEL=zai/glm-5.3-flash THINK=high scripts/run_task.sh /tmp/task_brief.md logs/<task>_run.log
```

Model choice:

| Situation | Model | Env |
|---|---|---|
| Anything that must **look at images** (contact sheets, annotated frames, frame crops, spreadsheet-like images) | `zai/glm-5.3-flash` | `MODEL=zai/glm-5.3-flash THINK=high` |
| Pure reasoning, code, or text-log work (no image reading) | `zai/glm-5.3` | `MODEL=zai/glm-5.3 THINK=max` |

`scripts/run_task.sh <prompt_file> <log_file>` runs `pi -p` non-interactively
(agent-dir `~/.pi/agent`, the brief's contents passed as the prompt, stdout+stderr
redirected to `<log_file>`, `EXIT <code>` appended as the last line) — always set
the env **prefix on the same command line**;
the delegate inherits your cwd. Run it with a generous tool timeout
(`timeout: 1800`+; a dev-clip pipeline run is minutes, not seconds). The log's
`EXIT 0` line is the only success signal you get — an `EXIT 1` or a log that
stops mid-sentence means the delegate died: fix the brief, re-delegate, do not
patch its half-finished work yourself.

A bare `pi -p '<prompt>'` (GLM 5.3 flash, high effort, image-capable) is
acceptable for a one-line factual question. Anything with a deliverable goes
through `run_task.sh` so there is a log.

Delegate **one mechanism / one bounded step** per run (AGENTS.md rule). Tell the
delegate explicitly: *diagnose first, do not design yet* when the step is a
diagnosis, and *no `src/` change* when the step is measurement.

## Step 4 — Code-review the delegate's output (your real job)

Read the log's report, then verify the actual artifacts — `git status`,
`git diff --stat`, then **targeted** `read`/`git diff` slices of the changed
hunks. The delegate's own claims are unverified inputs. Check at minimum:

1. **Scope** — is the change the ONE mechanism/task briefed, no stacked extras?
   Any `src/` diff that the brief did not authorize is a reject.
2. **Evidence** — were the required gates actually produced? Numbers must
   reproduce the recorded baseline (e.g. T5's base arm 4968/4968) or the
   discrepancy is unexplained, which is a red flag, not a win.
3. **A/B discipline** — byte-identical neutrality on the videos the change must
   not affect, and `cv2.setRNGSeed(0)` per `PlayerTracker` in any
   multi-tracker harness.
4. **Parity/architecture** — no live-debug-only fast path (batch and
   `--debug-live` share `FrameProcessor.process_frame`); no second full-video
   pass; no config key without a `DEFAULT_CONFIG` ↔ ctor ↔ GT-script row in the
   config-drift guard; `ball_confidence` still 0.15.
5. **Protocol breaches** — no GT edit without owner-ratified contact sheets; no
   mechanism shipped that the evidence refutes; no "detection gap" claim without
   probing raw detector output.
6. **Hygiene** — tests added/updated, suite run reported, artifacts/logs named
   and committed or explicitly left untracked on purpose.

Verdict must be explicit: **accept** / **accept with N fixes** / **reject +
why**. A refuted mechanism is a *success* of the session if the refutation is
proven and `src/` is left clean — say so instead of hunting for something to
ship.

## Step 5 — Close the loop

- End of session: run the `/status` ritual (STATUS.md *Where we are* rewritten,
  Open points collapsed, Log trimmed to ~3, `Last updated` refreshed).
  STATUS.md is committed **with** the work, never alone; show the diff and wait
  for owner confirmation before committing.
- If the delegate's finding invalidates a STATUS.md claim, the STATUS update is
  part of this session, not a follow-up.
- Report to the owner: what moved, the measured delta, what was refuted, and
  the next ranked needle-moving task.
