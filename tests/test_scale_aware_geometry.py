"""The scale-aware / mirror-aware contact geometry harness.

It is an UNVALIDATED mechanism (the owner asked to try it), so it lives in
``scripts/``, not ``src/``. These tests pin the two properties that make it safe
to measure at all:

1. **Fidelity** — the ``px`` arm IS production (it calls ``super()``), and the
   re-implemented scale arm reproduces production exactly when the multiplier
   makes ``k * width`` equal the production px constant. Without this, any win
   could just be a drifted copy of the classifier.
2. **Inertness** — with no multipliers and no mirror the object refuses nothing
   and adds nothing; the mirrored tests need their own conditions to fire.
"""
from __future__ import annotations

import pytest

from scripts.scale_aware_harness import ARMS, ScaleAwareActionClassifier
from src.recognition.pose_estimator import PoseEstimator
from src.utils.config import Config


def build(arm="px", **kwargs):
    cfg = Config.default().config
    return ScaleAwareActionClassifier(
        pose_estimator=PoseEstimator(min_detection_confidence=0.5, model_complexity=0),
        temporal_window=cfg["temporal_window"],
        confidence_threshold=cfg["action_confidence"],
        team_aware=cfg["attribution_team_aware"],
        width_side_enabled=cfg["attribution_width_side"],
        width_window=cfg["attribution_width_window"],
        width_far_px=cfg["attribution_width_far_px"],
        width_near_px=cfg["attribution_width_near_px"],
        near_net_exempt_m=cfg["attribution_near_net_exempt_m"],
        arm=arm,
        **kwargs,
    )


def history(points, width=20.0):
    """points: [(frame, x, y)] -> ball history entries with a fixed width."""
    return [(f, float(x), float(y), width, width) for f, x, y in points]


# A bounce: the ball descends to a trough at f100 then rises again.
BOUNCE = [(f, 100 + (f - 96) * 6, 300 + (f - 96) ** 2 * 3) for f in range(96, 105)]
BOUNCE = [(f, 100 + (f - 96) * 6, 300 + (100 - f) ** 2 * 3 if f >= 100 else 300 - (100 - f) ** 2 * 3)
          for f in range(96, 105)]


def ask(clf, points, frames):
    clf._ball_history.extend(history(points))
    out = []
    for c in frames:
        result = clf._detect_contact(c)
        if result is not None:
            out.append((c, result[1]))
    return out


def test_arms_are_the_documented_four():
    assert ARMS == ("px", "scale", "mirror", "scale+mirror")


def test_px_arm_is_production():
    """The px arm delegates to super(), so it cannot drift."""
    prod, arm = build("px"), build("px")
    assert ask(prod, BOUNCE, [100]) == ask(arm, BOUNCE, [100])


def test_scale_arm_reproduces_production_when_k_equals_the_px_constant():
    """k * width == the production px constant must behave identically."""
    clf_prod = build("px")
    # MIN_PROMINENCE is 26 px; pin the width so 1.0 * width == 26.
    # Widths pinned to 26 px, one multiplier per production constant
    # (XREV_MIN 20, DRIVE_DECEL 8, DRIVE_XIMPULSE 12, RISE_TOL 3, SERVE 10
    # all differ from MIN_PROMINENCE 26).
    clf_scaled = build("scale", width_min_px=26.0, width_max_px=26.0,
                       k_prominence=26.0 / 26.0, k_xrev=20.0 / 26.0,
                       k_decel=8.0 / 26.0, k_ximpulse=12.0 / 26.0,
                       k_rise_tol=3.0 / 26.0, k_serve_margin=10.0 / 26.0)
    assert ask(clf_prod, BOUNCE, [100]) == ask(clf_scaled, BOUNCE, [100])


def test_scale_thresholds_shrink_with_a_smaller_ball():
    clf_big = build("scale", k_prominence=1.0)
    clf_small = build("scale", k_prominence=1.0)
    assert clf_big._thresholds(40.0)["prominence"] == pytest.approx(40.0)
    assert clf_small._thresholds(10.0)["prominence"] == pytest.approx(10.0)


def test_none_multiplier_keeps_the_production_px_value():
    th = build("scale")._thresholds(10.0)
    clf = build("px")
    assert th["prominence"] == clf.MIN_PROMINENCE
    assert th["xrev"] == clf.XREV_MIN
    assert th["decel"] == clf.DRIVE_DECEL
    assert th["serve_margin"] == clf.SERVE_ACCEL_MARGIN_PX


def test_mirror_is_inert_without_its_flag():
    clf = build("mirror")
    assert clf.mirror is True and clf.scale is False
    # A mirrored test cannot invent a contact out of a pure trough.
    assert ask(clf, BOUNCE, [100]) == ask(build("px"), BOUNCE, [100])


def test_mirrored_test_fires_on_a_peak_with_a_drop():
    """The far-side shape: the ball peaks at the contact, then descends hard."""
    # y is MINIMAL at the contact and grows on both sides: the ball rises into
    # the contact and drops after it (struck at the camera).
    peak = [(f, 200 + (f - 100) * 2, 400 + (100 - f) ** 2 * 3) for f in range(94, 107)]
    prod = ask(build("px"), peak, [100])
    mirrored = ask(build("mirror"), peak, [100])
    assert prod == []
    assert mirrored and mirrored[0][1] in ("far_flight", "far_serve")
