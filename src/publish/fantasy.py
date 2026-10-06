"""Fantasy rules, the same shape as the ``fantasy_rules`` table.

The web scores from the database (``supabase/migrations``: a rule awards
``points`` to every credited touch whose action is in ``actions`` and whose
outcome equals ``outcome`` -- ``None`` = any outcome -- and, with
``assist_only``, only to sets flagged ``is_assist``). This module applies
the same rules to a bundle, so ``--dry-run`` can show the points before
anything is published. ``G1_RULES`` mirrors the migration's seed (pinned by
``tests/test_publish.py``); edit the table in the web/DB, not here, to
change live scoring.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, TypedDict


class Rule(TypedDict):
    rule_key: str
    label: str
    actions: List[str]
    outcome: Optional[str]
    assist_only: bool
    points: float


G1_RULES: List[Rule] = [
    {"rule_key": "kill", "label": "Kill", "actions": ["spike", "overpass"],
     "outcome": "kill", "assist_only": False, "points": 1.0},
    {"rule_key": "ace", "label": "Ace", "actions": ["serve"],
     "outcome": "ace", "assist_only": False, "points": 1.0},
    {"rule_key": "dig", "label": "Dig", "actions": ["dig"],
     "outcome": None, "assist_only": False, "points": 1.0},
    {"rule_key": "assist", "label": "Assist", "actions": ["set"],
     "outcome": None, "assist_only": True, "points": 0.5},
    {"rule_key": "block", "label": "Block", "actions": ["block"],
     "outcome": None, "assist_only": False, "points": 1.0},
    {"rule_key": "serve_error", "label": "Service error", "actions": ["serve"],
     "outcome": "error", "assist_only": False, "points": -1.0},
    {"rule_key": "attack_error", "label": "Attack error", "actions": ["spike", "overpass"],
     "outcome": "error", "assist_only": False, "points": -1.0},
    {"rule_key": "handling_error", "label": "Ball handling",
     "actions": ["set", "dig", "ball_handling"],
     "outcome": "error", "assist_only": False, "points": -1.0},
]


def rule_matches(rule: Rule, action: Dict[str, Any]) -> bool:
    return (action.get("action") in rule["actions"]
            and (rule["outcome"] is None or action.get("outcome") == rule["outcome"])
            and (not rule["assist_only"] or bool(action.get("is_assist"))))


def score_actions(actions: Iterable[Dict[str, Any]],
                  rules: Iterable[Rule] = G1_RULES) -> Dict[str, Dict[str, Any]]:
    """slot -> {"fantasy": total, "breakdown": {rule_key: count}} over the
    CREDITED touches (``slot`` set), exactly like ``public.action_fantasy``."""
    rules = list(rules)
    out: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"fantasy": 0.0, "breakdown": {}})
    for a in actions:
        slot = a.get("slot")
        if not slot:
            continue
        row = out[slot]
        for rule in rules:
            if rule_matches(rule, a):
                row["fantasy"] = round(row["fantasy"] + rule["points"], 1)
                row["breakdown"][rule["rule_key"]] = row["breakdown"].get(rule["rule_key"], 0) + 1
    return dict(sorted(out.items()))
