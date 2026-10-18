"""Rule-based, evidence-backed event reconstruction."""

from .inference import infer_events
from .rules import ANNEXATION, INDEPENDENCE, RULE_TYPES, TERRITORY_GAINED, TERRITORY_LOST, UNIFICATION

__all__ = [
    "ANNEXATION",
    "INDEPENDENCE",
    "RULE_TYPES",
    "TERRITORY_GAINED",
    "TERRITORY_LOST",
    "UNIFICATION",
    "infer_events",
]
