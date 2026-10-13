"""Conservative resolution of serialized ``{"value": id}`` references to entity identities.

A reference resolves only when the ID is present in the save under a state type that belongs to one of
the expected ``EntityDomain`` values (a field such as councilor ``location`` is observed to point at either
a region or a hab). Anything else stays ``Unknown`` with the raw serialized value attached, so the
normalizer never invents a target. The index also remembers which state type owns every other ID in the
save, so the normalizer can report a reference whose target exists under an unexpected type as an unknown
structure while still resolving it to ``Unknown(unresolved_reference)``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..identity import ENTITY_DOMAINS, STATE_PREFIX, read_id_value
from ..log import fields, get_logger
from ..model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from ..model.values import Observed, Unknown, UnknownReason, freeze
from .containers import decode_state_map
from .errors import UnsupportedSaveShapeError

logger = get_logger(__name__)

ExpectedDomains = EntityDomain | frozenset[EntityDomain]
"""One target domain, or the set of domains a reference field is observed to point at."""


def as_domains(expected: ExpectedDomains) -> frozenset[EntityDomain]:
    return expected if isinstance(expected, frozenset) else frozenset((expected,))


_DOMAIN_STATE_TYPES: frozenset[str] = frozenset(
    STATE_PREFIX + short_type
    for strategy in ENTITY_DOMAINS
    if strategy.confidence is IdentityConfidence.IN_SAVE_ID
    for short_type in strategy.state_types
)


@dataclass(frozen=True)
class ReferenceIndex:
    """Map ID -> (domain, short state type) for every domain identified by an in-save ID.

    ``other_owners`` maps the IDs of every remaining ``gamestates`` collection to its state type (prefix
    stripped), read tolerantly, so an ID that exists outside the entity domains can still be named.
    """

    owners: dict[int, tuple[EntityDomain, str]]
    other_owners: dict[int, str] = field(default_factory=dict)

    @classmethod
    def from_gamestates(
        cls, gamestates: dict[str, Any], *, on_skipped: Callable[[str], None] | None = None
    ) -> ReferenceIndex:
        """Index the save; ``on_skipped`` is told the short type of each malformed container that was skipped."""
        owners: dict[int, tuple[EntityDomain, str]] = {}
        skipped = 0
        for strategy in ENTITY_DOMAINS:
            if strategy.confidence is not IdentityConfidence.IN_SAVE_ID:
                continue
            for short_type in strategy.state_types:
                try:
                    entries = decode_state_map(gamestates, short_type)
                except UnsupportedSaveShapeError as error:
                    # A malformed unrelated container must not break the normalized domains.
                    logger.debug("reference index skipped %s", fields(state_type=short_type, reason=str(error)))
                    skipped += 1
                    if on_skipped is not None:
                        on_skipped(short_type)
                    continue
                for entry in entries:
                    owners.setdefault(entry.map_id, (strategy.domain, short_type))
        other_owners: dict[int, str] = {}
        for key, container in gamestates.items():
            if key in _DOMAIN_STATE_TYPES or not isinstance(container, list):
                continue
            short_type = key.removeprefix(STATE_PREFIX)
            for entry in container:
                map_id = read_id_value(entry.get("Key")) if isinstance(entry, dict) else None
                if map_id is not None:
                    other_owners.setdefault(map_id, short_type)
        logger.debug(
            "reference index built %s", fields(ids=len(owners), other_ids=len(other_owners), skipped_types=skipped)
        )
        return cls(owners, other_owners)

    def owner_state_type(self, map_id: int, expected: frozenset[EntityDomain]) -> str | None:
        """The state type owning ``map_id`` when that type is outside ``expected``; ``None`` if absent or expected."""
        owner = self.owners.get(map_id)
        if owner is not None:
            return None if owner[0] in expected else owner[1]
        return self.other_owners.get(map_id)

    def _lookup(self, value: Any, expected: frozenset[EntityDomain]) -> EntityRef | None:
        map_id = read_id_value(value)
        if map_id is None:
            return None
        owner = self.owners.get(map_id)
        if owner is None or owner[0] not in expected:
            return None
        return EntityRef(EntityId(owner[0], str(map_id)), IdentityConfidence.IN_SAVE_ID, state_type=owner[1])

    def resolve(self, value: Any, expected: ExpectedDomains) -> Observed:
        """``null`` stays ``None``; a resolvable reference becomes an ``EntityRef``; otherwise unknown."""
        if value is None:
            return None
        ref = self._lookup(value, as_domains(expected))
        if ref is None:
            return Unknown(UnknownReason.UNRESOLVED_REFERENCE, raw=freeze(value))
        return ref

    def resolve_list(self, value: Any, expected: ExpectedDomains) -> Observed:
        """A list of references; one unresolvable element makes the whole field unknown."""
        if not isinstance(value, list):
            return Unknown(UnknownReason.UNPARSEABLE, raw=freeze(value))
        domains = as_domains(expected)
        refs: list[EntityRef] = []
        for item in value:
            ref = self._lookup(item, domains)
            if ref is None:
                return Unknown(UnknownReason.UNRESOLVED_REFERENCE, raw=freeze(value))
            refs.append(ref)
        return tuple(refs)
