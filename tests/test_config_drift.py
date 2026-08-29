"""Guard against silent config drift between production and the GT scripts.

Why this file exists (2026-08-17): ``Config.DEFAULT_CONFIG`` had drifted from
the component constructor defaults (ball_confidence 0.7 vs 0.15,
player_max_disappeared 30 vs 90, tracking_max_distance 100 vs 150), so
``src.main`` / live-debug silently ran a *different pipeline* than
``scripts/test_action_recognition.py`` -- same code, different config,
different gestures (entreno_3 f539: production said block, the script said
spike). Every surface looked fine on its own; only the cross-comparison
catches it. The same sweep found stale inline ``.get(key, fallback)`` values
(main.py still carried the old 0.7) -- defused the same day.

Four seams, one test each:
1. DEFAULT_CONFIG vs component ctor defaults -- the validated scripts
   construct PlayerTracker/BallTracker bare, so the ctor defaults ARE the
   script-side config.
2. DEFAULT_CONFIG vs literal kwargs in the GT scripts (the values every
   GT-validated number was measured with).
3. DEFAULT_CONFIG vs argparse defaults of the GT scripts (--pose-complexity).
4. DEFAULT_CONFIG vs inline ``<config>.get(key, fallback)`` fallbacks in the
   wiring code -- dead while the key exists, a landmine the day a key is
   removed from DEFAULT_CONFIG.

Deliberate divergences (pinned by tests 2/3, not bugs):
- ball_confidence 0.15 vs BallDetector ctor 0.05 (bare-detector floor).
- pose_complexity 0 vs PoseEstimator ctor 1 (config + script both run lite).
- action_confidence 0.3 vs ActionClassifier ctor 0.4.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from src.detection.ball_detector import BallDetector
from src.detection.player_detector import PlayerDetector
from src.recognition.action_classifier import ActionClassifier
from src.recognition.pose_estimator import PoseEstimator
from src.tracking.ball_tracker import BallTracker
from src.tracking.player_tracker import PlayerTracker
from src.utils.config import Config

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = Config.DEFAULT_CONFIG

_NON_LITERAL = object()  # kwarg/arg written as an expression (args.foo, not x.no_team_aware)
_MISSING = object()  # key absent from DEFAULT_CONFIG


def _literal(node: ast.AST):
    """Literal value of an AST node, or _NON_LITERAL for expressions."""
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return _NON_LITERAL


# ---------------------------------------------------------------------------
# 1. DEFAULT_CONFIG <-> component ctor defaults
# ---------------------------------------------------------------------------
# (config_key, class, ctor_param): every key documented in config.py as the
# "surface" of a ctor default must equal that default, because the validated
# scripts run the bare constructors. The original drift lived here
# (player_max_disappeared 30 vs 90, tracking_max_distance 100 vs 150).
CTOR_PARITY = [
    # BallTracker
    ("ball_max_missing", BallTracker, "max_missing_frames"),
    ("trajectory_smoothing", BallTracker, "trajectory_smoothing"),
    ("low_confidence_threshold", BallTracker, "low_confidence_threshold"),
    ("max_trajectory_gap", BallTracker, "max_trajectory_gap"),
    # PlayerDetector
    ("player_confidence", PlayerDetector, "confidence_threshold"),
    ("player_imgsz", PlayerDetector, "imgsz"),
    ("max_detections", PlayerDetector, "max_players"),
    # PoseEstimator (pose_complexity deliberately differs -- module docstring)
    ("pose_confidence", PoseEstimator, "min_detection_confidence"),
    # ActionClassifier (action_confidence deliberately differs)
    ("temporal_window", ActionClassifier, "temporal_window"),
    ("attribution_team_aware", ActionClassifier, "team_aware"),
    ("attribution_width_side", ActionClassifier, "width_side_enabled"),
    ("attribution_width_window", ActionClassifier, "width_window"),
    ("attribution_width_far_px", ActionClassifier, "width_far_px"),
    ("attribution_width_near_px", ActionClassifier, "width_near_px"),
    ("attribution_near_net_exempt_m", ActionClassifier, "near_net_exempt_m"),
    # PlayerTracker
    ("player_max_disappeared", PlayerTracker, "max_disappeared"),
    ("tracking_max_distance", PlayerTracker, "max_distance"),
    ("max_players", PlayerTracker, "max_players"),
    ("player_appearance_weight", PlayerTracker, "appearance_weight"),
    ("player_init_frames", PlayerTracker, "init_frames"),
    ("player_team_vote_window", PlayerTracker, "team_vote_window"),
    ("coast_extrapolation_cap", PlayerTracker, "coast_extrapolation_cap"),
    ("coast_velocity_decay", PlayerTracker, "coast_velocity_decay"),
    ("coast_vertical_damping", PlayerTracker, "coast_vertical_damping"),
    ("player_gallery_enabled", PlayerTracker, "gallery_enabled"),
    ("player_gallery_reacquire_distance_px", PlayerTracker, "gallery_reacquire_distance_px"),
    ("player_gallery_reacquire_min_appearance", PlayerTracker, "gallery_reacquire_min_appearance"),
    ("player_gallery_reacquire_appearance_min", PlayerTracker, "gallery_reacquire_appearance_min"),
    ("player_gallery_evict_min_hold_frames", PlayerTracker, "gallery_evict_min_hold_frames"),
    ("player_bootstrap_min_window", PlayerTracker, "bootstrap_min_window"),
    ("player_bootstrap_ball_required", PlayerTracker, "bootstrap_ball_required"),
    ("player_signature_color_weight", PlayerTracker, "signature_color_weight"),
    ("player_signature_head_weight", PlayerTracker, "signature_head_weight"),
    ("player_signature_height_weight", PlayerTracker, "signature_height_weight"),
    ("player_signature_proportions_weight", PlayerTracker, "signature_proportions_weight"),
    ("player_signature_height_smoothing", PlayerTracker, "signature_height_smoothing"),
    ("player_off_court_grace_frames", PlayerTracker, "off_court_grace_frames"),
    ("player_off_court_hold_frames", PlayerTracker, "off_court_hold_frames"),
    ("player_serve_zone_enabled", PlayerTracker, "serve_zone_enabled"),
    ("player_serve_zone_depth_m", PlayerTracker, "serve_zone_depth_m"),
    ("player_serve_zone_side_margin_m", PlayerTracker, "serve_zone_side_margin_m"),
    ("player_serve_zone_trial_frames", PlayerTracker, "serve_zone_trial_frames"),
    ("player_serve_zone_ball_votes", PlayerTracker, "serve_zone_ball_votes"),
]


@pytest.mark.parametrize("config_key,cls,param", CTOR_PARITY)
def test_ctor_default_matches_config(config_key, cls, param):
    value = DEFAULTS.get(config_key, _MISSING)
    assert value is not _MISSING, f"DEFAULT_CONFIG no longer has '{config_key}'"
    ctor_default = inspect.signature(cls).parameters[param].default
    assert value == ctor_default, (
        f"{cls.__name__}.{param} ctor default {ctor_default!r} != "
        f"DEFAULT_CONFIG['{config_key}'] {value!r}: the validated scripts run "
        f"the bare constructor, so production and the scripts have silently "
        f"forked (the 2026-08-17 f539 block/spike class of bug)."
    )


# ---------------------------------------------------------------------------
# 2. DEFAULT_CONFIG <-> literal kwargs in the GT scripts
# ---------------------------------------------------------------------------
GT_SCRIPTS = [
    ROOT / "scripts" / "test_action_recognition.py",
    ROOT / "scripts" / "test_ball_tracking.py",
]

_PLAYER_TRACKER_PARAMS = {
    param: key for key, cls, param in CTOR_PARITY if cls is PlayerTracker
}

# literal kwarg -> config key, per constructed class. Any literal a script
# passes must equal DEFAULT_CONFIG: the scripts are where every GT-validated
# number comes from. Keyword args written as expressions (args.*, not x) are
# skipped here; their defaults are covered by test 3 where they matter.
SCRIPT_KWARGS = {
    "BallDetector": {"confidence_threshold": "ball_confidence"},
    "PlayerDetector": {
        "confidence_threshold": "player_confidence",
        "imgsz": "player_imgsz",
        "max_players": "max_detections",
    },
    "BallTracker": {
        "max_missing_frames": "ball_max_missing",
        "trajectory_smoothing": "trajectory_smoothing",
        "low_confidence_threshold": "low_confidence_threshold",
        "max_trajectory_gap": "max_trajectory_gap",
    },
    "PoseEstimator": {
        "min_detection_confidence": "pose_confidence",
        "model_complexity": "pose_complexity",
    },
    "PlayerTracker": _PLAYER_TRACKER_PARAMS,
    "ActionClassifier": {
        "confidence_threshold": "action_confidence",
        "temporal_window": "temporal_window",
        "team_aware": "attribution_team_aware",
    },
}


def _script_literal_cases():
    """[(file, lineno, class, kwarg, config_key, value)] for every mapped
    literal construction kwarg in the GT scripts."""
    cases = []
    for path in GT_SCRIPTS:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in SCRIPT_KWARGS):
                continue
            for kw in node.keywords:
                if kw.arg is None:  # **kwargs splat
                    continue
                config_key = SCRIPT_KWARGS[node.func.id].get(kw.arg)
                if config_key is None:
                    continue
                value = _literal(kw.value)
                if value is not _NON_LITERAL:
                    cases.append((path.name, node.lineno, node.func.id, kw.arg,
                                  config_key, value))
    return cases


@pytest.mark.parametrize("file,lineno,cls_name,kwarg,config_key,value",
                         _script_literal_cases())
def test_script_literal_matches_config(file, lineno, cls_name, kwarg,
                                       config_key, value):
    expected = DEFAULTS.get(config_key, _MISSING)
    assert expected is not _MISSING, f"DEFAULT_CONFIG no longer has '{config_key}'"
    assert value == expected, (
        f"{file}:{lineno} {cls_name}({kwarg}={value!r}) != "
        f"DEFAULT_CONFIG['{config_key}']={expected!r}: the script and "
        f"production have forked."
    )


def test_script_literal_scan_is_nonempty():
    # Guard the guard: if the AST scan stops matching (rename, refactor), the
    # parametrized test above silently shrinks to zero cases and passes vacuously.
    assert len(_script_literal_cases()) >= 8


# ---------------------------------------------------------------------------
# 3. DEFAULT_CONFIG <-> argparse defaults of the GT scripts
# ---------------------------------------------------------------------------
ARGPARSE_DEFAULTS = {
    # Script default 0 (lite) must equal the config default -- the knob was
    # added so eval runs can't silently diverge from production pose.
    "--pose-complexity": "pose_complexity",
}


def test_argparse_defaults_match_config():
    path = ROOT / "scripts" / "test_action_recognition.py"
    found = {}
    for node in ast.walk(ast.parse(path.read_text())):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"
                and node.args and isinstance(node.args[0], ast.Constant)):
            flag = node.args[0].value
            for kw in node.keywords:
                if kw.arg == "default":
                    value = _literal(kw.value)
                    if value is not _NON_LITERAL:
                        found[flag] = value
    for flag, config_key in ARGPARSE_DEFAULTS.items():
        assert flag in found, f"{path.name}: {flag} no longer has a literal default"
        assert found[flag] == DEFAULTS[config_key], (
            f"{path.name}: {flag} default {found[flag]!r} != "
            f"DEFAULT_CONFIG['{config_key}']={DEFAULTS[config_key]!r}"
        )


# ---------------------------------------------------------------------------
# 4. DEFAULT_CONFIG <-> inline .get(key, fallback) fallbacks in wiring code
# ---------------------------------------------------------------------------
FALLBACK_FILES = [
    ROOT / "src" / "analysis" / "frame_processor.py",
    ROOT / "src" / "analysis" / "video_processor.py",
    ROOT / "src" / "main.py",
    ROOT / "scripts" / "dump_player_tracks.py",
]

# Keys that intentionally have NO DEFAULT_CONFIG entry: their only surface is
# the inline fallback, which must equal the component ctor default.
FALLBACK_ONLY = {
    "velocity_threshold": (BallTracker, "velocity_threshold"),
    "player_max_velocity": (PlayerTracker, "max_velocity"),
}


def test_inline_fallbacks_match_defaults():
    problems = []
    seen = 0
    for path in FALLBACK_FILES:
        for node in ast.walk(ast.parse(path.read_text())):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"):
                continue
            recv = node.func.value
            is_config = (
                isinstance(recv, ast.Name) and recv.id in ("config", "_CFG")
            ) or (isinstance(recv, ast.Attribute) and recv.attr == "config")
            if not is_config or len(node.args) < 2:
                continue
            if not isinstance(node.args[0], ast.Constant):
                continue
            fallback = _literal(node.args[1])
            if fallback is _NON_LITERAL:
                continue
            key = node.args[0].value
            seen += 1
            if key in DEFAULTS:
                expected = DEFAULTS[key]
            elif key in FALLBACK_ONLY:
                cls, param = FALLBACK_ONLY[key]
                expected = inspect.signature(cls).parameters[param].default
            else:
                problems.append(
                    f"{path.name}:{node.lineno} {key!r}: inline fallback with "
                    f"no DEFAULT_CONFIG entry and not whitelisted in "
                    f"FALLBACK_ONLY -- give it a config key or whitelist it"
                )
                continue
            if fallback != expected:
                problems.append(
                    f"{path.name}:{node.lineno} {key}: inline fallback "
                    f"{fallback!r} != expected {expected!r} (dead while the "
                    f"key exists in DEFAULT_CONFIG, a landmine the day the "
                    f"key is removed)"
                )
    # Guard the guard: the scan must still be finding the wiring surface.
    assert seen >= 40, "fallback scan went near-empty -- files or matcher moved?"
    assert not problems, "\n" + "\n".join(problems)
