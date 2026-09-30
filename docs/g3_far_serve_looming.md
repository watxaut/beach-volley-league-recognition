# G3 S1 - far-side serve looming probe (diagnose only)

**Status: REFUTED** - kill 2: no separable L gap.

No `src/` change; the mechanism, if it had survived, would have required the owner-gated S2 band (STATUS #42).

## Frozen spec

* far-band onset width <= 26 px; looming window 0.5 s; merge gap 10 f (`ball_max_missing`); new-rally gap 90 f.
* dev far serves [210, 880, 2154, 3038, 4770] (GT tolerance +-15 f).

## Kill 1 - far flight detected?

Far-band tracked sightings in [c, c+0.5 s]; need >= 5 at >= 4/5 serves. **met at 4/5; not fired.**

| GT far serve | tracked | far-band | ok |
|---|---|---|---|
| f210 | 7 | 7 | yes |
| f880 | 3 | 3 | NO |
| f2154 | 10 | 10 | yes |
| f3038 | 9 | 9 | yes |
| f4770 | 9 | 9 | yes |

## Kill 2 - does L separate far serves from new-rally non-serves?

* lowest far-serve L = **0.338**; highest new-rally non-serve L = **0.945**.
* gap = -0.607, ratio = 0.357 (need >= 1.5x); L* = None; **FIRED.**

3 new-rally non-serve segment(s) loom at or above the weakest far serve, so no threshold can admit all five without false fires:

| onset | width px | L | behind baseline |
|---|---|---|---|
| f1673 | 26.0 | 0.945 | None |
| f4581 | 17.0 | 0.495 | None |
| f3390 | 23.0 | 0.364 | False |

Dev candidates (new-rally, far-band):

| onset | width px | L | GT far serve | behind baseline |
|---|---|---|---|---|
| f216 | 16.0 | 0.800 | f210 | True |
| f490 | 24.0 | 0.221 | - | False |
| f890 | 17.0 | 0.619 | f880 | True |
| f1673 | 26.0 | 0.945 | - | None |
| f1699 | 23.0 | -0.102 | - | False |
| f1733 | 21.0 | -0.191 | - | True |
| f2159 | 18.0 | 0.338 | f2154 | True |
| f3042 | 23.0 | 0.523 | f3038 | False |
| f3390 | 23.0 | 0.364 | - | False |
| f4581 | 17.0 | 0.495 | - | None |
| f4776 | 16.0 | 0.798 | f4770 | None |

## Kill 3 - entreno neutrality

Not evaluable: L* is undefined (kill 2 fired), so no threshold could fire.  Census of far-band new-rally segments per entreno clip:

| clip | tracked | far-band new-rally segments |
|---|---|---|
| e1 | 342 | 1 |
| e2 | 306 | 1 |
| e3 | 510 | 0 |
| e4 | 299 | 1 |
| e5 | 251 | 0 |
| e6 | 218 | 1 |
| e7 | 276 | 1 |

## Kill 4 - held-out match (PENDING S0)

Owner S0 contact GT (P9-P33) does not exist yet; this kill cannot be scored.  The match replay (production parity) and the new-rally far-band census are reported for when it lands:

* replay fidelity: 0 locked / 0 centre mismatches over 26068 frames.
* far-band new-rally segments: 55; would fire at L*: 0.

## Reading the result

A negative result here is the same class as T5 and R1: the far-serve CONTACT stays open, and the owner decides the next lever (targeted detector mining per #42 vs another mechanism). The secondary `behind_baseline` feature is reported above but was never used to move L*, so no threshold was fit to it.
