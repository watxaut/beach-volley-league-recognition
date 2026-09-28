# Reliable actions on new recordings — assessment and plan

**Date:** 2026-09-28

**Scope:** Read-only assessment of the implementation at `78aee5b`, following `AGENTS.md`. No code, model, configuration, or GT changes; no video processing or fresh benchmark runs. Numbers below are recorded results, not new measurements. Deeper code inspection delegated to `pi -p` using the subscription harness.

**Decision requested:** Approve the staged plan, starting with an unseen-recording benchmark and an evidence/feature contract—not another video-specific action fix.

## 1. Recommendation

**Your concern is justified. Keep the working detectors; change how their evidence becomes actions.** The current system is a useful, carefully regression-tested prototype, but successful detection is not equivalent to generalizable action recognition.

The recommended destination is a **hybrid temporal recognizer**:

1. Keep YOLO, tracking, court calibration, and the shared single-pass `FrameProcessor`.
2. Preserve time-aligned ball/player/pose evidence, including missingness and uncertainty.
3. Generate high-recall contact candidates from multiple signals, rather than making ball-trajectory rules the only entrance.
4. Learn contact/gesture probabilities from short temporal sequences; retain volleyball rules as interpretable sequence constraints, not camera-specific vetoes.
5. Interpret points, serves, outcomes, and scoring from the saved stream, with explicit uncertainty and human corrections.
6. Measure **unseen-session, correct-player scoring**, not only action labels on familiar clips.

Do not start by training a large end-to-end video model, replacing YOLO, or rewriting everything. First expose where events are lost and establish a held-out benchmark. Then compare a small learned baseline against the existing rules. More annotations across recordings are likely more valuable than further threshold polishing, but that is a hypothesis to test—not a measured result yet.

## 2. What the repository establishes

### Strengths worth preserving

- One shared perception path, existing action regression clips, owner-adjudicated GT, and provenance-aware post-hoc corrections.
- Ball v3 improved the existing match substantially. The recorded serve probe saw the ball at every anchored serve with confidence around 0.86–0.92; the dominant serve losses were downstream of detection.
- Recognition already separates visual gesture from contextual action. This is the right conceptual split; the evidence and decisions inside those layers need improvement.
- Post-hoc interpretation does not require a second full video decode. Keep the owner-ratified architecture in `AGENTS.md` §6.

### Concrete sources of brittleness

| Mechanism | Repository evidence | Why another recording can fail |
|---|---|---|
| Ball-motion-led candidate generation | `src/recognition/action_classifier.py:1–43`, contact methods | Normal contacts require trajectory signatures; bridges/reentry recover particular missing-data shapes. A clear body action cannot independently rescue an event that never reaches classification. |
| Fixed pixel geometry | Same file `:47–53`, `:149–163`: prominence 26 px, reach 140 px, near-net 120 px, serve reach 160 px | Zoom, depth, resolution, and camera elevation change what these distances mean. |
| Fixed motion and timing | Same file `:47–50`, `:111–115`, `:142–163`: delay/window 7 frames, reentry speed 40 px/frame, drive speed 8 px/frame, rally reset 90 frames | Physical speed is not px/frame. Different FPS/VFR changes both velocity and the wall-time covered by a window. |
| Narrow occlusion recovery | Same file `:56–84`: bridge gap bands 5/8–14 frames, drop 20 px, rise 60 px | An occluded real touch outside these signatures disappears; lowering everything also admits sand bounces and spare balls. |
| Camera-specific side evidence | `AGENTS.md` §5 and `STATUS.md` Learnings: ball-width bands roughly 14–28 px far, 30–55 px near, abstain 26–35 px | Detector-box size is a useful signal in the validated setup, not a portable team classifier. Attribution errors contaminate touch order and scoring. |
| Ball-conditioned pose availability | `action_classifier.py:166` onward: stale-ball and near-ball pose gates, defaults 30 frames / 300 px | Proven neutral for today's classifier, but a new pose-led contact detector cannot recover slow/missing-ball events if its pose evidence was never computed. |
| Context error propagation | `action_context.py` and the classifier's own bridge rationale | A missed contact or incorrect team changes possession/touch count, causing several subsequent labels to change. Correcting one gesture threshold does not fix this sequence failure. |
| Match-specific serve interpretation | `scripts/relabel_serves.py:81–102`: default match artifacts, `GAP_SERVE_MIN=143`, P20 pinned to frame 14516/team A | These are useful adjudication tools for this match, not demonstrated autonomous behavior on a new match. |

These are not all “bad rules.” Reach, continuity, dead time, and possession are valid evidence. **The problem is treating setup-dependent measurements or incomplete observations as conclusive decisions.** Moving the constants into YAML would make tuning easier, not solve generalization.

The tracking layer also matters: a good raw ball detection can be rejected by admission/static-motion logic, and a good person box can have the wrong identity. For example, `src/tracking/ball_tracker.py:80–88` defaults include a 10-frame missing window, 8 px/frame lock speed, and 90 px lock jump. “YOLO works” does not establish the quality of the evidence delivered to recognition.

### The current success numbers need careful interpretation

1. **31/33 is a point-count comparison, not matched point recall.** `scripts/evaluate_match_points.py` explicitly evaluates counts without GT frame anchors; its ratio is predicted count divided by GT count. False points and missing points can cancel. Temporal matching is necessary before claiming point precision/recall.
2. **The episode map is GT-assisted.** `scripts/map_episodes_to_points.py:1–28` uses the dictated point sequence, winner-derived serving side, known side changes, and description-implied rally size; the anchored version additionally uses owner serve markers. “Anchor-free” does not mean “GT-free.”
3. **The serve relabel improvement is assisted reconstruction.** The recorded 8/8 far-prefix result and 31 serve-typed actions include owner verdicts and structural information from that map. They demonstrate that interpretation can fix the existing stream, not that unseen serves are solved.
4. **Do not create circular outcome evaluation.** A winner predictor must not consume serving teams or windows selected using those same GT winners. Keep an assisted/reviewed mode, but benchmark autonomous inference with winners, descriptions, anchors, and frame pins unavailable.
5. Existing entreno action F1 uses `--ignore-player` for valid legacy-ID reasons. It is not evidence of reliable per-player fantasy attribution. Identity needs its own stable-ID GT and end-to-end metric.

There is also an input-contract inconsistency: `AGENTS.md` describes the validated long-axis, near/far camera, while `docs/video_recording_guide.md` recommends a sideline/net-vertical view. Reconcile that guide before collecting the benchmark. Its FPS/motion explanation should also be corrected; px/frame does not stay invariant when FPS changes.

## 3. Define “reliable” before changing the recognizer

### Initial supported scope

Start with **fixed, calibrated cameras**, all four players and serve space visible, across several heights/distances and modest oblique views. Explicitly mark unsupported views. Expand to a substantially different sideline view only when it has its own held-out evidence. Handheld/panning footage and multiple simultaneous courts are later scope, not an implicit promise.

Per-recording calibration is legitimate setup information. Per-recording action thresholds and frame-specific exceptions are not the intended product.

### Build the benchmark first

- Start with approximately **6–10 independent recordings** spanning at least three capture setups, both serving sides, different lighting and player appearances. Include complete points plus substantial dead time—not only clean rallies.
- Aim initially for **1,000–3,000 reviewed contacts**, plus negative windows and rare-event enrichment. This is an annotation-budget starting point, not a guaranteed sample requirement. Use learning curves; collect more where a class/view remains unsupported.
- Split by **whole recording/session**, and reserve a genuinely unseen camera setup. Never randomly split neighboring frames or clips from one match. Keep test recordings untouched by threshold selection and active-learning queries.
- Label contact time or uncertainty interval, stable player identity, squad versus current court side, action/gesture, visibility, point boundaries/winner, and relevant outcomes. Include held/carried balls, teammate handoffs, false starts, slow serves, occlusions, close net exchanges, and no-touch block attempts.
- Separate a **physical contact** from a **block attempt with no touch**. Both may be useful, but the latter cannot be recovered by a ball-contact-only detector or scored as a kill block automatically.
- Preserve existing owner-ratified GT. For new data use neutral annotation and independent spot checks; model disagreements are review candidates, not automatic GT corrections.

Maintain three distinct result tracks: **legacy regression**, **autonomous held-out**, and **human-reviewed final output**.

## 4. Target design: evidence → contacts → actions → points → scores

### A. Save sufficient evidence once

**Verified persistence gap:** `src/output_gen/json_exporter.py:90–120` exports video metadata, emitted actions, trimmed spike records, a few player-thumbnail snapshots, and point segments. It does **not** export the dense per-frame ball/player/pose evidence held during processing; snapshots are capped at three per track. Do not confuse `FrameProcessor`'s in-memory results with the saved JSON. Other diagnostic outputs may be reusable, but the canonical JSON alone cannot support the proposed temporal learner.

Final action events are not enough to train an alternative detector: rejected events are absent. Preserve a compact, versioned feature stream from the same online pass:

- Source frame index **and presentation timestamp**, source resolution/transforms, calibration and model/config versions.
- Ball position/box/confidence, observed versus predicted/missing status, track continuity, and relevant admission/rejection reasons.
- Player boxes/track IDs, association confidence or ambiguity, pre-jump stance/foot position, pose keypoints and their confidence when available.
- Candidate evidence, alternatives, and gate/rejection reasons; retain enough features on **non-event windows** to measure misses.

Use bounded storage or compressed sidecars rather than expanding the main JSON indefinitely. Reuse saved features for model experiments; extract missing features once through the shared path. Do not assume the existing artifacts already contain all historical poses or discarded detections.

### B. Normalize what is actually observable

- Use elapsed seconds and timestamp-based velocities/windows; preserve sequential-decode frame correspondence for this repository's VFR files. Dividing by nominal container FPS is insufficient for irregular timing.
- Use player-relative image distances (e.g. torso/body scale with confidence checks), normalized keypoints, and calibration/view descriptors. Body-relative speed helps with scale, but does **not** eliminate perspective or occlusion.
- Use court coordinates for grounded stance/feet and supported ground-contact locations.
- **Do not project an airborne ball through the court homography and call it a 3D court position.** Ball height and depth are ambiguous in one view. Likewise airborne feet are not ground stance.
- Treat ball width and projected motion as uncertain features, not universal team or attack rules. Learn/test across real views; image resizing alone cannot simulate a new 3D camera angle.

The earlier near-net px→metres replacement failed GT. Therefore normalization must be introduced in shadow mode and assessed per signal, not by globally replacing units and assuming correctness.

### C. Remove the candidate-recall ceiling

Retain current trajectory candidates, then union them with:

- Ball-to-hand/body proximity over time, relative to player scale.
- Pose/motion evidence of contact, including windows with weak/slow ball motion.
- A lightweight temporal contact scorer evaluated on rolling player windows, including explicit missing-ball masks.

The candidate stage should favor recall; a second stage rejects false events. Deduplicate nearby proposals using time **and actor/evidence**, without merging two real rapid net contacts. Log uncertainty instead of silently discarding every ambiguous window.

Do not merely train a classifier on today's emitted contacts: that could improve labels while preserving every current missed-action failure. Revisit pose gating only where measured recovery benefit justifies the cost; do not blindly run expensive pose on everyone forever.

### D. Learn local evidence; constrain sequences

Run a controlled ladder:

1. **Baseline:** current rules, frozen.
2. **Small model:** logistic/gradient-boosted contact and gesture classifiers over normalized temporal summaries. Cheap to train, inspect, and deploy; tests whether learnable evidence already beats thresholds.
3. **Only if justified:** a small temporal convolutional network over roughly 0.5–1.5-second sequences of pose, ball/player relationships, confidence and missingness. Tune window/latency on development sessions. A pretrained crop-video encoder is a later option if low-resolution pose/track features demonstrably lack information.

Predict contact probability, actor alternatives, gesture/action probabilities, and none/unknown—not only a forced label. Train with hard negatives and class imbalance explicitly handled.

Use possession, serve-at-opening, contact order, and prior/following actions to resolve ambiguity. These should not force an uncertain sequence to contain invented touches. Support a missing-contact/unknown transition and legitimate first-touch attacks, overpasses, and block exceptions.

A bounded confirmation delay is compatible with online processing: emit a backdated contact after enough observations arrive. Batch and live-debug must use identical buffering and decisions. Longer hindsight stays in the post-hoc stream layer, never a separate live-only recognizer.

### E. Complete the actual product

- Build autonomous point segmentation/serve interpretation from evidence, without needing the GT point count, winner list, descriptions, known switch times, or frame pins. Preserve owner corrections as **external, video-scoped review data**, never generic inference constants.
- Estimate point outcome/winner from last touch, observed ball death/landing, continuation, and attack/block evidence; abstain where out/occlusion is unresolvable. A track disappearing is not proof of a kill or fault.
- Validate stable player identity through side switches. A team-correct action assigned to the wrong teammate still corrupts both G1 and G2. Separate physical side from persistent squad identity.
- Implement assists and scoring as deterministic derivations over the resolved point/event ledger. Preserve ratified kill semantics, +0.5 assist, and kill-block versus soft-block scoring.
- Audit the meaning of `dig` before awarding +1: `src/recognition/action_context.py:10–17` explicitly calls the first reception `dig`. That alone does not establish retrieval of an attacked ball. Separate serve reception from fantasy-eligible defensive digs using preceding-action context.
- Keep ball-handling errors and genuinely ambiguous calls reviewable. Neither a temporal model nor volleyball rules can recover visual evidence that does not exist.
- Record original evidence, model interpretation, confidence, and manual correction separately. Downstream aggregates should identify provisional/reviewed data and recompute after corrections without rerunning perception.

## 5. Execution order and exit gates

These are proposed engineering gates, **not achieved numbers or accuracy promises**. Ratify them against club needs and sample sizes before implementation.

| Stage | Deliverable | Exit gate / decision |
|---|---|---|
| **0 — Scope and honest baseline** | Capture contract; session-level splits; error taxonomy; autonomous versus assisted audit | Time-match points and contacts on an unseen recording; quantify losses separately at detection, tracking, candidate, gesture, actor, and point/outcome stages. No new production heuristic. |
| **1 — Evidence and unit handling** | Versioned timestamped feature sidecar; shadow normalized features; rejection traces | Saving features leaves legacy perception outputs unchanged. Deterministic feature replay reproduces the baseline. Temporal/scale perturbation tests expose rather than hide sensitivity. |
| **2 — Candidate recovery** | Union proposals plus negative-window benchmark | Target ≥97% contact candidate recall overall and ≥90% in each adequately sampled class/view slice, with false candidates and downstream cost reported. Otherwise improve observability/proposals before gesture ML. |
| **3 — Learned local model** | Small baseline first; temporal model only if needed | Beat frozen rules on unseen sessions, not just pooled familiar clips; target macro event F1 ≥0.90 with per-class/view precision/recall and uncertainty intervals. Promotion cannot trade away rare serves/blocks behind a better average. |
| **4 — Point, identity and outcome integration** | GT-free interpretation, side-switch validation, deterministic scoring | Target ≥95% one-to-one point precision/recall; separately measure winner accuracy and joint action+stable-player accuracy. Target ≥98% precision for auto-accepted scoring events, with coverage reported so abstention cannot game the result. |
| **5 — Club pilot** | Review queue, player corrections, per-point ledger, aggregate stats | Compare reviewed fantasy lines to independently audited matches. Measure review minutes/hour, reviewed-event fraction, scoring discrepancies, latency and processing cost. Suggested review target: ≤10 min per recorded hour; do not call rollout ready without measuring it. |

Evaluation details:

- Match events one-to-one in **time**, not a fixed number of frames; start with ±0.2 s and adjust only to documented annotation uncertainty. Separately score contact detection, class, and actor. Report duplicate events and false positives per minute of dead time.
- Match point intervals against independent boundary annotations (predefined tolerance/overlap criterion), not against a desired point count.
- Report side/view, class, visibility and slow/fast-motion slices; bootstrap by session rather than pretending correlated frames are independent samples. Rare classes without enough held-out examples remain unvalidated.
- At each confidence threshold show **precision versus automatic coverage** and manual-review burden. A model returning unknown everywhere is not reliable automation.
- Keep legacy A/B baselines from untouched HEAD and the existing regression suite. Logging/performance-only changes must be byte-identical. Recognition improvements necessarily change intended outputs: adjudicate those differences while requiring neutrality on unaffected cases. Do not freeze known mistakes just to preserve byte parity.
- Profile the same shared path on target hardware. The recorded match baseline is 68 ms/frame; agree an acceptable incremental budget before expanding pose or adding a model.

**Parallel work:** Identity GT around switches can start immediately. An assisted points ledger/review UI and deterministic assist/scoring derivations can also deliver club value before autonomous recognition is finished. Label them assisted; do not count corrected predictions as automatic model accuracy.

## 6. First concrete work package

After approval:

1. Select one new recording that fails today and one additional recording to reserve untouched.
2. Annotate a bounded diagnostic sample: approximately 50–100 contacts across both sides, full point boundaries, and several minutes of dead time. Add a short side-switch identity sample if available.
3. Produce a waterfall for every missed/wrong event: **raw detection → track admission → candidate → actor → gesture/context → point/scoring**.
4. Specify the minimal feature-sidecar fields missing from existing artifacts and estimate extraction/storage/runtime cost.
5. Use that evidence to choose exactly one first mechanism: timestamp normalization, candidate recovery, or learned gesture disambiguation. Do not change all three together.

**Bottom line:** Stop optimizing only for the known video suite. Preserve the perception investment, make missing/uncertain evidence visible, learn the view-dependent decisions from diverse sequences, and retain volleyball rules for interpretation. The finish line is correct, attributable, reviewable statistics on recordings that were never used to tune the system—not another perfect reconstruction of the current match.
