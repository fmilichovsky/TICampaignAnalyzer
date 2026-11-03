"""Rule-based, evidence-backed event reconstruction."""

from .control import NATION_CONTROL_CHANGED
from .control import RULE_TYPES as CONTROL_RULE_TYPES
from .inference import infer_events
from .space import BATTLE_OUTCOME, FIRST_HAB_ON_BODY, HAB_DESTROYED, HAB_ESTABLISHED
from .space import RULE_TYPES as SPACE_RULE_TYPES
from .territorial import ANNEXATION, INDEPENDENCE, TERRITORY_GAINED, TERRITORY_LOST, UNIFICATION
from .territorial import ID_ATTRIBUTES as TERRITORIAL_ID_ATTRIBUTES
from .territorial import RULE_TYPES as TERRITORIAL_RULE_TYPES

RULE_TYPES = (*TERRITORIAL_RULE_TYPES, *CONTROL_RULE_TYPES, *SPACE_RULE_TYPES)
ID_ATTRIBUTES = TERRITORIAL_ID_ATTRIBUTES
"""Attributes of inferred events whose value is a tuple of event IDs."""

__all__ = [
    "ANNEXATION",
    "BATTLE_OUTCOME",
    "FIRST_HAB_ON_BODY",
    "HAB_DESTROYED",
    "HAB_ESTABLISHED",
    "ID_ATTRIBUTES",
    "INDEPENDENCE",
    "NATION_CONTROL_CHANGED",
    "RULE_TYPES",
    "TERRITORY_GAINED",
    "TERRITORY_LOST",
    "UNIFICATION",
    "infer_events",
]
