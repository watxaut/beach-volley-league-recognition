"""PARKED G3 R1 mechanism: the confirmation-time departure gate (NOT shipped).

Owner decision 2026-09-30 (option (a)): R1 does NOT ship. The mechanism was
REFUTED on the held-out full match (20260920): at threshold 0.3 ball-widths
per frame it removed the P11 owner-confirmed serve (f7132 dig A, 0.285 bw/f)
and the structural FP 6928A, points confirmed fell 31/33 -> 28/33 and the
far prefix census 8/8 -> 7/8. Full gate tables and the STOP report:
``docs/g3_r1_departure_gate.md`` + ``logs/r1_finish_report.md``.
``src/`` is reverted to 185c6f0 (T5 precedent, commit 8140711): no gate, no
``contact_min_departure_bw`` config key.

This module keeps the pure measurement ``departure_bw_per_frame`` VERBATIM
(as it lived in ``src/recognition/action_classifier.py`` when the g3r1 runs
were produced) so the committed evidence stays reproducible:
``scripts/action_evidence.py`` imports it (never a copy) to re-derive
``output/g3/evidence_r1.json``'s ``departure_gate_check``, and the g3r1
diag dumps remain renderable. Default-OFF harness in the T5 style
(``scripts/serve_mechanism_harness.py``): nothing here is wired into the
production pipeline.
"""

from typing import Iterable, List, Optional, Tuple

import numpy as np


def departure_bw_per_frame(
    points: Iterable[Tuple[int, float, float, float, float]],
    contact_frame: int,
    window: int,
) -> Optional[float]:
    """Post-contact departure speed in BALL WIDTHS PER FRAME (G3 R1).

    Pure measurement shared by the production gate and the offline evidence
    tooling (``scripts/action_evidence.py`` imports it -- never a copy).
    ``points`` are REAL ball sightings in the classifier's own
    ``_ball_history`` format ``(frame, x, y, w, h)`` (coasted tracker
    predictions are absent by construction), ``window`` is the number of
    frames after ``contact_frame`` the caller may look at (the classifier
    passes ``CONTACT_DELAY``: the contact is confirmed at
    ``contact_frame + CONTACT_DELAY``, so every frame of the window has
    already been seen -- no lookahead).

    Value: the MEAN per-frame displacement over the chain of sightings from
    the contact frame through the end of the window --
    ``[contact_frame, contact_frame + window]``, consecutive points paired,
    each step divided by its own frame gap. This is the classifier-data
    equivalent of the offline evidence measurement (whose consecutive-frame
    step chain started at the contact-frame centre; on rows where the
    classifier held the game ball the two agree to 3 decimals). A net
    first-to-last displacement would instead read ~0 when the apex falls
    inside the window (a high dig that rose AND fell within 7 frames
    departed; the net says it did not), and dropping the contact-frame point
    would measure motion between two post-contact sightings only -- not
    departure FROM the touch. The speed is divided by the ball WIDTH at the
    sighting nearest the contact within the same window (the apparent size
    at the touch -- normalising by it makes the measure scale-invariant: a
    far-side ball moves fewer pixels for the same real speed).

    Returns None when departure is NOT MEASURABLE -- callers must ABSTAIN,
    never reject: fewer than 2 sightings inside the window (contact frame
    included) or no pair on distinct frames, or no sighting with a positive
    width at/near the contact.
    """
    width: Optional[float] = None
    best_d: Optional[int] = None
    chain: List[Tuple[int, float, float, float, float]] = []
    for p in points:
        f = p[0]
        if contact_frame <= f <= contact_frame + window:
            chain.append(p)
            w = float(p[3])
            d = abs(f - contact_frame)
            if w > 0.0 and (best_d is None or d < best_d):
                best_d, width = d, w
    if width is None or len(chain) < 2:
        return None
    chain.sort(key=lambda p: p[0])
    steps = [
        float(np.hypot(b[1] - a[1], b[2] - a[2])) / (b[0] - a[0])
        for a, b in zip(chain, chain[1:])
        if b[0] > a[0]
    ]
    if not steps:
        return None
    return (sum(steps) / len(steps)) / width
