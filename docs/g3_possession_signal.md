# Possession-signal probe — offline A/B (no `src/` change)

Mechanisms parked default-OFF in `scripts/possession_signal_harness.py`;
replayed through the REAL `ActionClassifier` attribution methods against
`output/g3r1/match_bw03_diag.jsonl` (185 raw contacts).

| arm | correct | n | accuracy |
|---|---:|---:|---:|
| base | 121 | 157 | 0.7707 |
| trend | 122 | 157 | 0.7771 |
| motion | 121 | 157 | 0.7707 |
| both | 122 | 157 | 0.7771 |

**Verdict:** base 0.7707 → both 0.7771 (delta +1); trend fires 11x, 11 on the correct side. REFUTED as a needle-mover.

## Reading the result

The ball-field trend is PRECISE but mostly REDUNDANT: it fires only on
strict-abstain contacts and names the right arriving side, yet the base
attribution already resolves most of them by other means. The carry
errors it was meant to fix mostly have NO ball signal at all (ball lost
mid-flight), which no ball-field rule can recover. The motion tie-break
changes only same-team actor picks — zero team attribution. Hence the
mechanisms are parked in the harness (T5/R1 precedent): no config key,
ctor signature or drift-guard surface in `src/`.
