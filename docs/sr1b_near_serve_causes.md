# SR1b — what actually loses the near serve (session 58, 2026-10-02)

Review of SR1 (`docs/sr1_near_serve_misses.md`), open point **30**.
Diagnose-only: **no `src/` change**. Evidence: one sequential production pass
over the match [0, 15000] with `--diag-dump` (MPS, **parity 111/111 identical**
to the shipped artifact), the seven fresh entreno dumps from SR1, and one
counterfactual pass [0, 8000] with `player_off_court_hold_frames` lifted to
100000 by config override. Full worker report, verbatim:
`docs/sr1b_worker_report.md`; artifacts in the git-ignored `output/review_sr1b/`.

## 1. Why SR1 needed a review

SR1 concluded that the near side "is a LABEL problem, not a perception one", and
that 5 of 6 label misses were "one condition" (`behind_baseline` false), with a
geometric story (a bump serve looks like a reception, an overhand toss like an
attack). Two parts of that were **inferred, not measured**:

- `output/serves/sr1.json` has `behind_baseline_measured: null` for all four
  match label rows; the verdict came by elimination from `_decide`. Only e2 was
  measured.
- "Not a tracking problem" was about the **ball**. SR1's own P5/P7 rows say the
  server is not among the four tracks; the **player** track was never checked.

## 2. The measured causes (three mechanisms, not one)

| GT near serve | outcome | cause, measured |
|---|---|---|
| P9 f5496, P10 f6035, P11 f7147, P12 f7777 | label (`spike`/`dig`) | **Contact-frame foot.** Server track FED, contact emitted at 0/-1/-15/+3 f, `rally_start` true. `behind_baseline` reads the toucher's foot on the CONTACT frame: 736.8 / 747.7 / 736.5 / 760.2 vs threshold 761 (**24.2 / 13.3 / 24.5 / 0.8 px short**). Seven frames later the same tracks are 6-12 px PAST it. Hits P3, P16-P20 have contact feet at 809-835 (50-75 px past). |
| P5 f2575, P7 f3747 | no contact (reach gate) | **Off-court hold horizon.** The near server's track goes `predicted` exactly **91 f** after its last in-court sighting (`player_off_court_hold_frames = 90`) and coasts FROZEN (0.0 / 0.3 px drift) through the serve. Dwell behind the baseline before the serve: 174 / 120 f. |
| e2 f32 | label (`dig`) | **Server never tracked.** No near track behind the baseline; the 4th slot is held by a sideline-straddling person since bootstrap; the contact goes to the partner at the net (foot 646, `near_net` true). Drill/bootstrap artefact, serve at frame 32. |
| e5 f20 | no contact | Ball not sighted (SR1 was right). Server track FED. |

Not covered by the [0, 15000] pass: P24 (`other_side_contact`) and P33 (the
`rally_start` cascade from our own early emission, SR1 §2.1).

## 3. Counterfactual: hold horizon lifted (config only, [0, 8000])

- **P7 becomes a HIT** (serve at +0 f, foot 818.8, gap 108 f).
- **P5 changes bucket**: the contact now exists (`dig` at -3 f, server track FED,
  `behind_baseline` TRUE) but `rally_start` is false — a pre-serve handling
  contact (f2494) is only 78 f earlier (< 90). Same family as P33 and as 8 of the
  12 false serves: dead-time handlings cost recall as well as precision.
- P9-P12 reproduce **to the decimal** under the counterfactual: the hold horizon
  is not in their causal path.
- Cost inside [0, 8000]: 53 → 55 actions; one label flip on a frame with no GT
  event within 81 f (f2494 `overpass` → `set`). **Not measured:** the entreno
  e2 bystander that the 90 f horizon was introduced to kill (08-29). The horizon
  comment says "real players max out at 46f (e6)" — a figure from 1-point drill
  clips; match servers wait 120-324 f behind the baseline between points.

## 4. Side facts

- **`NEAR_NET_PX = 120` is venue-broken on the beach.** The match's near half is
  ~147 px deep (midcourt y≈643, baseline 774-791), so 120 px from the net covers
  ~80% of it: `near_net` is TRUE at all four P9-P12 serve contacts.
- **Far side, P1-P20**: the far server track is FED at 7/8 far serves (P6 ABSENT),
  while the ball track is `none` (`unlocked_no_motion`) at 7/8 — consistent with
  the known far-ball wall, and good news for SR5 server identity.
- The near misses cluster: P9-P12 (squad B serving from the near side, one
  server standing on the line) miss in a row; P16-P20 hit in a row. A per-server
  stance, not a random gate failure.

## 5. What this changes

- SR1's "next = a label-free side + rally-opening test in SR4" treats a symptom.
  The near serve is recoverable **upstream** by two separate, rule-backed
  mechanisms, each one session, each needing an owner gate before `src/`:
  - **M-a — takeoff stance for `behind_baseline`.** By rule the server is behind
    the line at takeoff; the airborne/landing foot projects inside. Same fact
    SpikeAnalyzer already uses for `attack_zone`. Candidate for P9-P12.
  - **M-b — serve-zone exemption from the 90 f hold.** The e2 bystander was on
    the SIDELINE; a server is BEHIND THE OWN BASELINE, so the two separate
    geometrically. Candidate for P5/P7 (P5 also needs the `rally_start` fix).
- Both also give SR5 what it needs: the server's own track id at the serve.
- SR2 (audio) loses priority: timing is not the bottleneck on either side (near
  emitted serves ±2 f; far rally onset median 3 f).
- Next is a **measurement** of M-a over existing dumps (task card SR1c in
  STATUS), not a `src/` edit.
