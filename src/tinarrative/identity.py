"""Entity-identity strategy table and a semantics-light identity census.

The table records *where* each entity domain keeps its identifier and how far
that identifier can be trusted. The census counts what is literally serialized
(``Key.value`` versus ``Value.ID.value``); it never compares saves, so claims
about cross-snapshot stability stay unresolved. See
docs/game-data-notes/entity-identity.md.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

STATE_PREFIX = "PavonisInteractive.TerraInvicta."

Confidence = Literal["in-save-id", "name-key"]


@dataclass(frozen=True)
class EntityDomain:
    domain: str
    state_types: tuple[str, ...]
    id_source: str
    confidence: Confidence
    secondary_key: str | None


_NUMERIC_ID = "gamestates/<type>[].Key.value == Value.ID.value"

ENTITY_DOMAINS: tuple[EntityDomain, ...] = (
    EntityDomain("faction", ("TIFactionState",), _NUMERIC_ID, "in-save-id", "Value.templateName"),
    EntityDomain("nation", ("TINationState",), _NUMERIC_ID, "in-save-id", "Value.templateName"),
    EntityDomain("region", ("TIRegionState",), _NUMERIC_ID, "in-save-id", "Value.templateName"),
    EntityDomain(
        "councilor",
        ("TICouncilorState",),
        _NUMERIC_ID,
        "in-save-id",
        None,
    ),
    EntityDomain(
        "army",
        ("TIArmyState", "TIMegafaunaArmyState"),
        _NUMERIC_ID,
        "in-save-id",
        None,
    ),
    EntityDomain(
        "fleet",
        ("TISpaceFleetState",),
        _NUMERIC_ID,
        "in-save-id",
        None,
    ),
    EntityDomain(
        "ship",
        ("TISpaceShipState",),
        _NUMERIC_ID,
        "in-save-id",
        None,
    ),
    EntityDomain(
        "space object",
        (
            "TISpaceBodyState",
            "TILagrangePointState",
            "TIOrbitState",
            "TIAdHocOrbitState",
            "TIHabSiteState",
            "TIHabState",
        ),
        _NUMERIC_ID,
        "in-save-id",
        "Value.templateName (space bodies)",
    ),
    EntityDomain(
        "organization",
        ("TIOrgState",),
        _NUMERIC_ID,
        "in-save-id",
        None,
    ),
    EntityDomain(
        "technology",
        ("TIGlobalResearchState",),
        "gamestates/TIGlobalResearchState[0].Value.finishedTechsNames[], techProgress[].techTemplateName",
        "name-key",
        None,
    ),
)


@dataclass(frozen=True)
class TypeIdentity:
    state_type: str
    present: bool
    entries: int
    id_matches: int
    id_mismatches: int
    id_missing: int
    id_duplicates: int
    min_id: int | None
    max_id: int | None


@dataclass(frozen=True)
class DomainIdentity:
    domain: EntityDomain
    types: tuple[TypeIdentity, ...]


@dataclass(frozen=True)
class IdentityReport:
    domains: tuple[DomainIdentity, ...]
    ids_shared_across_types: int
    total_ids: int
    max_observed_id: int | None
    current_id: int | None


def _int_value(holder: Any) -> int | None:
    """Read ``{"value": <int>}``; booleans are not IDs."""
    if isinstance(holder, dict):
        value = holder.get("value")
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _census_type(state_type: str, entries: Any, owners: dict[int, set[str]]) -> TypeIdentity:
    if not isinstance(entries, list):
        return TypeIdentity(state_type, True, 0, 0, 0, 0, 0, None, None)
    matches = mismatches = missing = 0
    seen: Counter[int] = Counter()
    for entry in entries:
        entry_dict = entry if isinstance(entry, dict) else {}
        value = entry_dict.get("Value")
        key_id = _int_value(entry_dict.get("Key"))
        inner_id = _int_value(value.get("ID")) if isinstance(value, dict) else None
        if key_id is None or inner_id is None:
            missing += 1
        elif key_id == inner_id:
            matches += 1
        else:
            mismatches += 1
        if key_id is not None:
            seen[key_id] += 1
            owners.setdefault(key_id, set()).add(state_type)
    return TypeIdentity(
        state_type=state_type,
        present=True,
        entries=len(entries),
        id_matches=matches,
        id_mismatches=mismatches,
        id_missing=missing,
        id_duplicates=sum(count - 1 for count in seen.values() if count > 1),
        min_id=min(seen) if seen else None,
        max_id=max(seen) if seen else None,
    )


def analyze_identity(root: Any) -> IdentityReport | None:
    """Census every domain's state types; ``None`` when there is no gamestates object."""
    if not isinstance(root, dict) or not isinstance(root.get("gamestates"), dict):
        return None
    gamestates: dict[str, Any] = root["gamestates"]
    owners: dict[int, set[str]] = {}
    domains: list[DomainIdentity] = []
    covered: set[str] = set()
    for domain in ENTITY_DOMAINS:
        types: list[TypeIdentity] = []
        for short_name in domain.state_types:
            full_name = STATE_PREFIX + short_name
            covered.add(full_name)
            if full_name in gamestates:
                types.append(_census_type(short_name, gamestates[full_name], owners))
            else:
                types.append(TypeIdentity(short_name, False, 0, 0, 0, 0, 0, None, None))
        domains.append(DomainIdentity(domain, tuple(types)))
    # Count shared IDs over every state type, not only the table's, to test the shared-counter hypothesis.
    for name, entries in gamestates.items():
        if name not in covered:
            _census_type(name, entries, owners)
    return IdentityReport(
        domains=tuple(domains),
        ids_shared_across_types=sum(1 for types in owners.values() if len(types) > 1),
        total_ids=len(owners),
        max_observed_id=max(owners) if owners else None,
        current_id=_int_value(root.get("currentID")),
    )
