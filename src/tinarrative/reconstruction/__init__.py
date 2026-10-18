"""Rule-based, evidence-backed event reconstruction."""

from .inference import infer_events
from .space import BATTLE_OUTCOME, FIRST_HAB_ON_BODY, HAB_DESTROYED
from .space import RULE_TYPES as SPACE_RULE_TYPES
from .territorial import ANNEXATION, INDEPENDENCE, TERRITORY_GAINED, TERRITORY_LOST, UNIFICATION
from .territorial import ID_ATTRIBUTES as TERRITORIAL_ID_ATTRIBUTES
from .territorial import RULE_TYPES as TERRITORIAL_RULE_TYPES

RULE_TYPES = (*TERRITORIAL_RULE_TYPES, *SPACE_RULE_TYPES)
ID_ATTRIBUTES = TERRITORIAL_ID_ATTRIBUTES
"""Attributes of inferred events whose value is a tuple of event IDs."""

__all__ = [
    "ANNEXATION",
    "BATTLE_OUTCOME",
    "FIRST_HAB_ON_BODY",
    "HAB_DESTROYED",
    "ID_ATTRIBUTES",
    "INDEPENDENCE",
    "RULE_TYPES",
    "TERRITORY_GAINED",
    "TERRITORY_LOST",
    "UNIFICATION",
    "infer_events",
]
