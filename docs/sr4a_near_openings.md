# SR4a — the near-opening table: what the pipeline emitted around every serve

**Card:** `STATUS.md` § *Next task cards* → `### CARD SR4a` (D4 / open point 30,
`#62`). **Type:** measurement, diagnose-only. **No `src/` change, no decode, no
seek, no re-run.** Every number below is a COUNT. Every claim is marked
**[measured]** (computed by `scripts/probe_near_openings.py` from the named
artifacts, or read directly out of them) or **[inferred]** (an interpretation of
those numbers, not itself a measurement).

Reproduce with:

```bash
venv/bin/python scripts/probe_near_openings.py            # table + G1 + G2, writes output/sr4a/near_openings.json
venv/bin/python scripts/probe_near_openings.py --g1-only  # the gate alone
```

---

## 0. Verdict in one block

| | count | source |
|---|---|---|
| G1 scorer near / far / false serves | **8/16, 0/17, 12** | measured |
| G1 probe recount near / far / drills | **8/16, 0/17, 3/5** | measured |
| near misses (`MISS_NEAR`) | **8** | measured |
| `emitted_mislabeled_opener` (near misses) | **2** | measured |
| `emitted_not_opener` (near misses) | **3** | measured |
| `not_emitted` (near misses) | **3** | measured |
| **SR4 near side proceeds after the fact** | **YES — 5 repairable of 8** (rule `>= 4`) | measured |
| **M-b REOPENED** | **YES — 3 never produced, 2 of them coasting** (rule `>= 3` AND `>= 2`) | measured |
| `far_unseen_near_reception_first` | **0** | measured |

Both G2 verdicts are true. Per the card, **SR4 goes first** — it needs no
`src/` change — and M-b reopens only as *a fresh architect call with a lift-arm
diag dump*, not as a build. The trap guard is **0**, so no onset-side guard is
demanded by this card's rule; §6 records why that is a weak reassurance anyway.

---

## 1. G1 — the gate, run before any bucket was read **[measured]**

```
scorer (scripts/score_serves.py --detail) : near 8/16   far 0/17   false_positives 12   -> GATE PASS
probe   (own recount)                     : near 8/16   far 0/17   drills e2-e7 3/5   -> PASS
```

Drill detail: e2 0/1, e3 1/1, e4 (no serve contact in GT), e5 0/1, e6 1/1,
e7 1/1 -> **3 of 5**.

The two drill action files were compared on `(frame_number, action, team)` for
N = 2..7 as the card requires: **identical** for all six **[measured]**, so
`#61`'s claim holds and scoring the `output/sr1d/base/` arm is legitimate. The
probe asserts this itself and prints it in the G2 footer.

**One deviation from the card's literal wording, disclosed.** The card's window
rule ("starts at the last action before the GT frame whose gap to its own
predecessor is >= `GAP_SERVE_MIN`") leaves one case undefined: a GT serve with
**no action at all before it**. That is not exotic — it is the *clip-opening*
serve, and it occurs in 4 of the 5 drills with a serve (e2 f32, e3 f29, e6 f34,
e7 f25) and once in the match (P1 f210, far). Read literally, those windows do
not exist, every clip-opening serve reads `not_emitted`, and the probe's drill
recount comes out **0/5**, i.e. G1 fails. Rather than adjust the window, the
tolerance or the buckets (which the card forbids) the probe follows
`scripts/relabel_serves.py`, whose own gate is
`if gap is not None and gap < GAP_SERVE_MIN` (line ~288, in `resolve_point`) —
**known-and-below** is the only rejection, so an unknown gap (video start)
qualifies — and its documented basis (lines 54-58) measures openers from "the
previous action (anchored prefix: 219-853f **or video start**)". The probe
therefore opens the window at the **first action of the stream** when nothing
precedes the GT frame. With that one reading, G1 passes on both arms. The
`GAP_SERVE_MIN` value itself is **imported, never re-tuned and never redefined**;
a test (`test_probe_does_not_redefine_gap_serve_min`) parses the probe's `ast` and
fails if the name is ever assigned at module level.

This is flagged rather than buried because it is the one judgement in this card
that the card did not literally pre-register. It is [measured] that the literal
reading fails G1 and that this reading passes it.

---

## 2. The near-opening table — 16 match near GT serves **[measured]**

Window = the opening exchange, from the chasm-gap opener to the first
other-team action after the GT frame. `onset` = `game_state.points[*].start_frame`
nearest the GT frame (a pure time proposer; `side: null`, so it proposes *no*
side). `n` = actions in the window.

| pt | GT frame | bucket | onset off | window | n | what the window holds |
|---|---|---|---|---|---|---|
| 3 | f1395 | **hit** | -19 | f930..f1428 | 4 | opener f930 `dig` A (gap 532); f1396 `serve` A (+1 f) |
| 5 | f2575 | **not_emitted** | -171 | f2414..f3172 | 6 | f2414 `serve` A (-161) is a FALSE serve; f2445 `dig` A; f2494 `overpass` A |
| 7 | f3747 | **not_emitted** | -18 | f3595..f3856 | 3 | f3595 `serve` A (-152) is a FALSE serve; f3639 `dig` A |
| 9 | f5496 | **emitted_not_opener** | -16 | f5130..f5520 | 3 | f5130 `serve` B is a FALSE serve; f5496 `spike` A (+0 f), R14 |
| 10 | f6035 | **emitted_mislabeled_opener** | -18 | f6034..f6067 | 2 | f6034 `spike` A (-1 f) is the window's FIRST action; f6067 `dig` B |
| 11 | f7147 | **emitted_mislabeled_opener** | -32 | f7132..f7160 | 2 | f7132 `dig` A (-15 f) opens (gap 204); f7147 nothing within 15 f |
| 12 | f7777 | **emitted_not_opener** | -662 | f7132..f7815 | 9 | a whole R19 exchange, then f7780 `spike` A (+3 f) = P12's contact |
| 16 | f10541 | **hit** | -17 | f10070..f10571 | 9 | f10541 `serve` A (+0 f) |
| 17 | f11412 | **hit** | -19 | f11410..f12026 | 6 | f11410 `serve` A (-2 f) |
| 18 | f11995 | **hit** | -14 | f11677..f12026 | 4 | f11996 `serve` A (+1 f) |
| 19 | f13074 | **hit** | -15 | f12748..f13110 | 3 | f13074 `serve` A (+0 f) |
| 20 | f14518 | **hit** | +630 | f14387..f14550 | 3 | f14516 `serve` A (-2 f); nearest onset is the NEXT point's (+630) |
| 24 | f18135 | **not_emitted** | -10 | f17159..f18164 | 4 | f17159 `serve` A is a FALSE serve; then silence until f18164 `dig` B |
| 29 | f22150 | **hit** | -17 | f22149..f22178 | 2 | f22149 `serve` A (-1 f) |
| 30 | f22874 | **hit** | -17 | f22873..f22909 | 2 | f22873 `serve` A (-1 f) |
| 33 | f25807 | **emitted_not_opener** | -31 | f25782..f25837 | 3 | f25782 `serve` A (-25 f, **outside** ±15) then f25798 `dig` A (-9 f) |

Bucket totals over all 16 near serves: **8 hit, 2 `emitted_mislabeled_opener`,
3 `emitted_not_opener`, 3 `not_emitted`** — i.e. the 8 misses are exactly
5 repairable + 3 never produced. **[measured]**

Notes that matter for SR4's design, all **[measured]** unless marked:

- **The 8 hits are NOT all "the window's opener is a serve".** Only **4** of the
  8 have a `serve` as their window's first action (P17, P20, P29, P30, at -2,
  -131, -1, -1 f from the GT frame); the other **4** (P3, P16, P18, P19) have
  the window open 326–471 f earlier on a `dig` / far `serve` / `spike`, with the
  true `serve` sitting later inside the window. [measured] Every hit does have a
  same-side `serve` inside ±15 f of its GT frame (offsets 0, +1, +1, 0, -2, -2,
  -1, -1 f) — [measured] — but an SR4 record keyed on **the window opener**
  would recover **4 of the 8 hits**, not 8. [inferred] This is a design
  constraint for the SR4 card and a correction to the intuition the bucket names
  invite.
- **The 3 `emitted_not_opener` misses are three different defects**, and SR4
  cannot fix all three with one rule [measured from the table, inferred as a
  classification]:
  - **P9 (f5496)**: the emitted contact at the GT frame is a `spike`, not a
    serve, and it *is* the first action of R14 — a genuinely wrong label on a
    correctly-opened rally.
  - **P33 (f25807)**: a `serve` **was** emitted at f25782, **25 f** before the
    GT frame — 10 f outside the ±15 f tolerance. The scorer's own classifier
    already names this `serve_outside_tolerance` (§5). Within tolerance this row
    would be a `hit`, so this is a **tolerance-boundary** miss, not a missing
    perception; a same-side contact exists 9 f away too (f25798 `dig`).
  - **P12 (f7777)**: the nearest own-side action is f7780, a `spike` **+3 f**,
    but it is the first action of R20 while the window opener is f7132 — the
    whole R19 exchange (9 actions) sits between them. The window as defined by
    the chasm gap therefore does **not** contain P12's serve; the rally
    boundary, not the perception, is what makes this a miss.
- **The 2 `emitted_mislabeled_opener` misses are both ±1/±15 f neighbours of a
  wrong-label action**: P10's window starts at f6034 `spike` A, 1 f before the GT
  frame; P11's window starts at f7132 `dig` A, 15 f before it with **no own-side
  action at the GT frame at all** (so P11 is *also* structurally `not_emitted`
  and only reaches the mislabeled bucket through its window opener). [measured]
- **Onsets sit BEFORE the serve, not at it.** 12 of 15 near rows have an onset
  10–19 f before the GT frame, and the two outliers are P12 (-662, the previous
  point's start) and P20 (+630, the next point's). [measured] The onset is
  therefore **not** a usable point-of-serve marker at ±15 f; SR4's record needs
  the contact evidence, not the onset. [inferred]
- **Split composition of the misses** (from `match_split`, point <= 8 = dev):
  **6 held_out, 2 dev**; of the 8 hits, 7 held_out / 1 dev. [measured] The
  misses are not concentrated in the dev half.

---

## 3. The same table for the drills (`output/sr1d/base/`, `#61` BASE arm) **[measured]**

| clip | GT serve | bucket | window | note |
|---|---|---|---|---|
| e2 | f32 | **emitted_mislabeled_opener** | f32..f119 (2) | f32 `dig` A (+0 f) at the GT frame, first action, gap `None` |
| e3 | f29 | **hit** | f29..f74 (2) | f29 `serve` A (+0 f) |
| e4 | — | — | — | no serve contact in GT |
| e5 | f20 | **not_emitted** | f68..f68 (1) | window opens at f68 `dig` **B** (far) — nothing on the near side anywhere |
| e6 | f34 | **hit** | f35..f73 (2) | f35 `serve` A (+1 f); first action is **1 f after** the GT frame |
| e7 | f25 | **hit** | f25..f60 (2) | f25 `serve` A (+0 f) |

Drill buckets: **3 hit, 1 mislabeled_opener, 1 not_emitted** = the recorded
3/5 near hit count plus one repairable and one never-produced.

- **e2 is the mirror image of P10/P11**: the serve is there at the GT frame but
  labelled `dig`. [measured] The **mislabeled-opener class is real in both the
  drills and the match, independently** — which is what makes it a mechanism and
  not a one-off. [inferred]
- **e5 is the cleanest `not_emitted` in the whole card**: the GT serve is at f20,
  the first emitted action is f68 `dig` **far**, and there is no near-side action
  at any frame in the clip. Nothing was emitted on the serving side at all.
  [measured]
- **e6 is why the clip-opening clause is not cosmetic**: its `serve` lands at
  f35, one frame *after* the GT frame, so an implementation that required a
  preceding action to open the window would score it `not_emitted` while the
  scorer scores it a hit — the two arms would disagree on G1. [measured/inferred]

---

## 4. Coasting read — lowest-foot same-team track at each of the 8 near misses **[measured]**

From `output/sr1c/match_full_diag.jsonl`, read **sequentially by line**, keyed on
the `frame` field (no seek anywhere). 26069 lines, 26068 frames recorded,
25.67 fps. All 8 GT frames are present in the dump — `diag_absent` **0 of 8**.

| pt | GT frame | bucket | track | team | foot y | conf | **`predicted`** | same-team tracks |
|---|---|---|---|---|---|---|---|---|
| 5 | f2575 | not_emitted | 1 | A | 878.3 | 0.866 | **true** | 2 |
| 7 | f3747 | not_emitted | 4 | A | 845.8 | 0.828 | **true** | 2 |
| 9 | f5496 | emitted_not_opener | 4 | A | 736.8 | 0.849 | false | 3 |
| 10 | f6035 | emitted_mislabeled_opener | 3 | A | 744.9 | 0.876 | false | 2 |
| 11 | f7147 | emitted_mislabeled_opener | 2 | A | 767.6 | 0.919 | false | 2 |
| 12 | f7777 | emitted_not_opener | 4 | A | 789.7 | 0.832 | false | 2 |
| 24 | f18135 | not_emitted | 3 | A | 809.9 | 0.868 | false | 2 |
| 33 | f25807 | emitted_not_opener | 3 | A | 805.6 | 0.907 | false | 2 |

Full `predicted` list at each frame is printed beside every row in
`logs/sr4a_report.md` so the reading can be re-cut without a re-run.

**The arm of this dump is NOT ESTABLISHED.** `output/sr1c/match_full_run.log`
records device `mps`, the video, the fps and `diag_dump:
output/sr1c/match_full_diag.jsonl`, plus `parity_vs_reference
{actions_in_prefix: 207, reference_actions_in_prefix: 207, identical: true,
only_in_run: [], only_in_reference: []}` — but it names **no src arm and no
commit**. Per the card, no claim is made about which arm produced it. **[measured
absence of provenance]**

Reading the numbers: **`predicted: true` = 2 of 8, and both of them are
`not_emitted` misses (P5, P7)** — exactly the pre-registered combination the M-b
rule reads. The other 6 misses have a real (`predicted: false`) lowest-foot
same-team track at the GT frame, i.e. a *detected* player, which is why their
defect has to be a labelling/opening one rather than a reach gate. [measured;
the "has to be" is inferred]

---

## 5. The 12 false serves, with their window neighbours **[measured]**

Classified by `score_serves.classify_false_positives` (imported, not
re-implemented; `DEAD_TIME_SEARCH_F = 80`).

| frame | side | pt | kind | window opener? | nearest GT contact |
|---|---|---|---|---|---|
| f1039 | near | 2 | `dead_time_handling` | **no** (gap 109 < 143) | none within 80 f |
| f2414 | near | 5 | `dead_time_handling` | yes (gap 219) | none within 80 f |
| f3595 | near | 7 | `dead_time_handling` | yes (gap 330) | none within 80 f |
| f6928 | near | 11 | `dead_time_handling` | yes (gap 406) | none within 80 f |
| f14387 | near | 19 | `dead_time_handling` | yes (gap 629) | none within 80 f |
| f17159 | near | 23 | `dead_time_handling` | yes (gap 282) | none within 80 f |
| f3856 | far | 7 | `rally_contact_mislabeled` | yes | f3852 `set` far, -4 f |
| f8534 | far | 13 | `rally_contact_mislabeled` | yes | f8550 `dig` near, +16 f |
| f10070 | far | 15 | `rally_contact_mislabeled` | yes | f10072 `dig` near, +2 f |
| f5130 | far | 9 | `dead_time_handling` | yes (gap 224) | none within 80 f |
| f20397 | far | 27 | `dead_time_handling` | yes (gap 153) | none within 80 f |
| f25782 | near | 33 | `serve_outside_tolerance` | yes (gap 249) | f25807 `serve` near, +25 f |

Counts: `dead_time_handling` **8** (6 near, 2 far), `rally_contact_mislabeled`
**3** (all far), `serve_outside_tolerance` **1** (near).

Three things SR4 must not get wrong here:

1. **6 of the 12 false serves sit INSIDE a near miss's own window** — f2414
   (P5's window opener), f3595 (P7's opener), f3856 (P7, a far
   `rally_contact_mislabeled`), f5130 (P9's opener), f17159 (P24's opener) and
   f25782 (P33's opener, the +25 f one). [measured] Of those 6, **5 are that
   window's first action** (11 of the 12 false serves overall are). The G2
   counts in §0 are therefore **not** safe to apply as a promotion rule without
   first dropping the `dead_time_handling` / `serve_outside_tolerance`
   populations. [inferred, and it is the single most important consequence of
   this card]
2. **f25782 is P33's real serve, 25 f early.** The pipeline emitted it; the
   scorer rejects it because the GT is 25 f later. A record keyed on
   `(side, window, ±tolerance)` recovers P33 only if the tolerance is widened
   past 25 f, which would also admit `rally_contact_mislabeled` rows like
   f8534 (+16 f). [measured offsets; the tension is inferred]
3. **f1039 is the one false serve the chasm rule already rejects** (gap 109 <
   143) — the single false emission whose opener the `GAP_SERVE_MIN` import
   would exclude, i.e. **1 of 12**; the other 11 have an opener gap >= 143 and
   would pass it. [measured] So the chasm rule alone does not separate the 12
   false serves from the 8 true ones. [inferred]

---

## 6. The trap guard **[measured]**

`far_unseen_near_reception_first` = **0** of 17 far serves: there is no far serve
with a near-side action inside ±15 f and no rally onset inside ±15 f. Per the
card, no onset-side guard is demanded.

Caveat, stated rather than hidden: the guard's window is built the same way as
the bucket windows, and 12 of 15 near onsets sit 10–19 f **before** their serve,
so an onset at "±15 f of the serve" is a narrow target by construction. The
count of 0 is a real measurement; it is **not** evidence that a far serve can
never be preceded by a near-side emission. [measured offsets; the inference is
explicit]

---

## 7. What this card decides, and what it does not

**Decided [measured]:**

- SR4's near side **can be built after the fact**: 5 of the 8 near misses are
  repairable from the emitted actions alone (P9, P10, P11 wrong label; P33
  tolerance-boundary; P12 rally boundary), which clears the pre-registered
  `>= 4`. **But** only 4 of the 8 hits have a `serve` as their window's opener,
  and 6 false serves sit inside near-miss windows, so SR4 must key on the
  same-side contact within tolerance, not on the window opener alone. [measured
  counts; the constraint is inferred]
- M-b **reopens** as an architect call with a lift-arm diag dump (3 never
  produced, 2 of them with a `predicted: true` lowest-foot same-team track),
  which clears the pre-registered `>= 3` AND `>= 2`. It is **not** a build, and
  SR4 still goes first because it needs no `src/` change.
- Nothing here ships: no rule, threshold or config key was written.

**Not decided / out of scope:**

- Whether an SR4 record can be made *correct* on all 5 repairable rows — §5.1
  shows 6 windows contain false serves, and §2 shows the opener key recovers
  only 4 of the 8 hits. Both are rule-design questions for the SR4 card, not
  measurements.
- The far side: 17 of 17 far serves are misses and this card says nothing about
  them beyond the trap count.
- The provenance of `output/sr1c/match_full_diag.jsonl`, and therefore whether
  the 2 `predicted: true` readings would reproduce on a named arm. The M-b call
  it feeds is precisely the one that must re-run with the arm named.

## 8. Provenance of the inputs **[measured]**

| input | what it is |
|---|---|
| `output/20260920_match_ari_joan_lost/pipeline_output.json` | 207 actions, 31 `game_state.points`, `processed_at` 2026-10-01T19:46:34+00:00, `pipeline_version` `133d87c` |
| `ground_truth/20260920_match_contacts.json` | 33 serve contacts, `owner_side` far 17 / near 16, `frame_tolerance` 15 |
| `output/sr1d/base/entreno_{2..7}/` | `#61` BASE arm, `processed_at` 2026-10-02, `pipeline_version` `60770fb` |
| `ground_truth/video_entreno_{2..7}_annotations.json` | drill GT; e2 f32, e3 f29, e5 f20, e6 f34, e7 f25 |
| `output/sr1c/match_full_diag.jsonl` | 26069 lines, arm **not established** |

`GAP_SERVE_MIN = 143` and every scorer function were **imported**
(`from relabel_serves import GAP_SERVE_MIN`, `import score_serves as S`). The
probe contains **no `cv2` import** — pinned by an `ast` test.