"""Stable entity identity and references."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EntityDomain(StrEnum):
    FACTION = "faction"
    NATION = "nation"
    REGION = "region"
    CONTROL_POINT = "control point"
    COUNCILOR = "councilor"
    MISSION = "mission"
    ARMY = "army"
    FLEET = "fleet"
    SHIP = "ship"
    SPACE_OBJECT = "space object"
    SPACE_BODY = "space body"
    ORGANIZATION = "organization"
    TECHNOLOGY = "technology"
    WAR = "war"
    FEDERATION = "federation"
    REGION_ALIEN_STATE = "region alien state"
    GLOBAL_VALUES = "global values"
    NOTIFICATION_QUEUE = "notification queue"


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
    # Identities key most dictionaries of the pipeline; the generated hash re-hashed the StrEnum (in Python) each time.
    _hash: int = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_hash", hash((self.domain, self.key)))

    def __hash__(self) -> int:
        return self._hash

    def __reduce__(self) -> tuple[type[EntityId], tuple[EntityDomain, str]]:
        return (EntityId, (self.domain, self.key))  # string hashes differ between processes: rehash on unpickling

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
    _hash: int = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_hash", hash((self.entity_id, self.confidence, self.state_type, self.name)))

    def __hash__(self) -> int:
        return self._hash

    def __reduce__(self) -> tuple[type[EntityRef], tuple[EntityId, IdentityConfidence, str | None, str | None]]:
        return (EntityRef, (self.entity_id, self.confidence, self.state_type, self.name))

    def label(self) -> str:
        """``Name (nation:3857)``: the display name with the ID kept for audit; the bare ID without a name.

        A name-keyed entity whose name is its key (a technology) is not repeated.
        """
        if not self.name or self.name == self.entity_id.key:
            return str(self.entity_id)
        return f"{self.name} ({self.entity_id})"
