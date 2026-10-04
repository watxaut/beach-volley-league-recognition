# Task: INSERT-path CONTINUATION — finish the interrupted diagnosis

Continuation of `.pi/task_briefs/insert_path.md` (read it first: background, G1
gates, constraints, report format, verdict decision rule all still apply).
The previous worker degenerated AFTER writing `scripts/probe_insert_path.py`
but BEFORE running it / writing tests / writing the report. The coordinator
ran the probe once: `GATE G1 GREEN`, all gates OK, and the run wrote
`output/insert_path/probe.json`.

## Your scope (exactly this, nothing else)

1. **Run the probe yourself** and confirm G1 green:
   `venv/bin/python scripts/probe_insert_path.py --json output/insert_path/probe.json`
2. **FIX the control-section bug.** The CONTROL / FALSE-SERVE SIDE section
   prints `within +-15 f of a GT serve 0` and `precision 0.0` while the
   SENSITIVITY table on the same run reports `far_hits 11, nearFP 3` — the
   precision/serve-hit computation is broken (wrong key or empty dict). Fix it
   in `scripts/probe_insert_path.py`, state the convention used in the report
   (suggest #54's: correct serve claims / all placed claims), rerun, and show
   the corrected numbers.
3. **REQUIRED analysis addition — goal translation under BOTH denominator
   conventions**, in the report and in the probe output:
   (a) insert-into-denominator: inserted far serves ADD to the denominator
       (139 + k) because they were NOT-FOUND, not mislabeled — this is the
       consistent convention and the one the verdict must use;
   (b) #74b's literal 139-denominator variant, with a one-line note that it
       is numerator-only (adds correct serves without counting them as found)
       and therefore overstates the arm.
   The coordinator measured run (a) as: all-17 IN-SAMPLE 96/150 = 0.64;
   held-out-only 94/148 = 0.635; label-only ceiling 90/139 = 0.6475 — confirm
   or correct these from your own run.
4. **Consistency anchors — check and record in the report:** far_hits 11/17 at
   anchor_tol 15 must equal PG2's in-sample 11/17
   (`docs/point_map_seam.md`); seam split far {11 at_seam, 0 inside_window,
   6 in_gap} must equal PG2's. Any deviation = STOP and report.
5. **Tests** (`tests/test_insert_path.py`, mirror `tests/test_serve_bucket.py`
   style): G1 gate numbers; claim-building determinism; the two PG2 anchors;
   the both-conventions goal-translation structure. No cv2, no decode, no seek.
6. **Report** `logs/insert_path_report.md` per the ORIGINAL brief's §0–§5
   layout + the 6-line self-checklist, and the ONE verdict line per the
   original decision rule, computed with the corrected precision and the
   convention-(a) numbers. Name the unreachable serves and their common
   property (in-gap) and the FP side (rally-contact misclaims + dead-time).

## Constraints (unchanged from the original brief)

No `src/` change, no decode, no seek (`tests/test_vfr_seek_guard.py` stays
green), no GT edit, held-out entreno session untouched, no new Config key,
IN-SAMPLE vs HELD-OUT labeled everywhere, import machinery never re-implement.
Final: `venv/bin/python -m pytest tests/ -o addopts=""` green; report the count.
