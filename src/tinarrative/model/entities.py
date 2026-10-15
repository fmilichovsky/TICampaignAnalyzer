"""Stable entity identity and references."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EntityDomain(StrEnum):
    FACTION = "faction"
    NATION = "nation"
    REGION = "region"
    CONTROL_POINT = "control point"
    COUNCILOR = "councilor"
    ARMY = "army"
    FLEET = "fleet"
    SHIP = "ship"
    SPACE_OBJECT = "space object"
    ORGANIZATION = "organization"
    TECHNOLOGY = "technology"
    WAR = "war"
    FEDERATION = "federation"
    REGION_ALIEN_STATE = "region alien state"


class IdentityConfidence(StrEnum):
    """How an identity was established (not analyzer confidence; see ``events.Confidence``)."""

    IN_SAVE_ID = "in-save-id"
    NAME_KEY = "name-key"
    HEURISTIC = "heuristic"  # reserved; no matching rules exist yet


@dataclass(frozen=True, order=True)
class EntityId:
    """Domain-qualified key: a numeric map ID (as text) or a template-name key."""

    domain: EntityDomain
    key: str

    def __str__(self) -> str:
        return f"{self.domain.value}:{self.key}"

    @property
    def sort_key(self) -> tuple[str, int, int, str]:
        """Natural order: numeric keys by value (``9`` before ``10``), then name keys lexically."""
        numeric = self.key.isdigit()
        return (self.domain.value, 0 if numeric else 1, len(self.key) if numeric else 0, self.key)


@dataclass(frozen=True, order=True)
class EntityRef:
    """An entity identity plus how it was observed, so differing confidence never matches silently."""

    entity_id: EntityId
    confidence: IdentityConfidence
    state_type: str | None = None
    name: str | None = None
