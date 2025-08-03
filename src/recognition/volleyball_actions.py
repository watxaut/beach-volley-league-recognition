"""
Volleyball action definitions.

This module defines the volleyball actions that can be recognized.
"""

from enum import Enum


class VolleyballAction(Enum):
    """Enumeration of volleyball actions to recognize."""
    DIG = "dig"
    SET = "set"
    SPIKE = "spike"
    BLOCK = "block"
    ACE = "ace"
    SERVE = "serve"
    UNKNOWN = "unknown"