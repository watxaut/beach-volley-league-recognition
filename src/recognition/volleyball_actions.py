"""
Volleyball action definitions.

Two vocabularies live here, one per layer of the recognizer:

- :class:`VisualGesture` -- the *context-free* thing the body/ball did at a
  contact (a bump-set pass, an attacking swing, a net block). This is what the
  visual layer (`action_classifier.py`) outputs. A bump-set is deliberately
  ambiguous: on its own it could be a dig, a set, or an overpass.
- :class:`VolleyballAction` -- the *canonical* action, produced by the context
  layer (`action_context.py`) which disambiguates a gesture using rally state
  (touch number, and what happens on the previous/next contact).
"""

from enum import Enum


class VisualGesture(Enum):
    """Context-free visual gesture observed at a ball contact."""
    BUMP_SET = "bump_set"   # controlled up-touch (forearm bump or overhead pass)
    ATTACK = "attack"       # swing / ball driven down or across the net
    BLOCK = "block"         # hands overhead at the net, ball redirected not rising
    UNKNOWN = "unknown"


class VolleyballAction(Enum):
    """Canonical volleyball action after context disambiguation."""
    DIG = "dig"
    SET = "set"
    SPIKE = "spike"
    BLOCK = "block"
    ACE = "ace"
    SERVE = "serve"
    OVERPASS = "overpass"   # a bump-set sent over the net instead of to a teammate
    UNKNOWN = "unknown"
