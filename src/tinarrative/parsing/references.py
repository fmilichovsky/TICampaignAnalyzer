"""Conservative resolution of serialized ``{"value": id}`` references to entity identities.

A reference resolves only when the ID is present in the save under a state type that belongs to one of
the expected ``EntityDomain`` values (a field such as councilor ``location`` is observed to point at either
a region or a hab). Anything else stays ``Unknown`` with the raw serialized value attached, so the
normalizer never invents a target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..identity import ENTITY_DOMAINS, read_id_value
from ..model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from ..model.values import Observed, Unknown, UnknownReason, freeze
from .containers import decode_state_map
from .errors import UnsupportedSaveShapeError

ExpectedDomains = EntityDomain | frozenset[EntityDomain]
"""One target domain, or the set of domains a reference field is observed to point at."""


def _as_domains(expected: ExpectedDomains) -> frozenset[EntityDomain]:
    return expected if isinstance(expected, frozenset) else frozenset((expected,))


@dataclass(frozen=True)
class ReferenceIndex:
    """Map ID -> (domain, short state type) for every domain identified by an in-save ID."""

    owners: dict[int, tuple[EntityDomain, str]]

    @classmethod
    def from_gamestates(cls, gamestates: dict[str, Any]) -> ReferenceIndex:
        owners: dict[int, tuple[EntityDomain, str]] = {}
        for strategy in ENTITY_DOMAINS:
            if strategy.confidence is not IdentityConfidence.IN_SAVE_ID:
                continue
            for short_type in strategy.state_types:
                try:
                    entries = decode_state_map(gamestates, short_type)
                except UnsupportedSaveShapeError:
                    continue  # a malformed unrelated container must not break the normalized domains
                for entry in entries:
                    owners.setdefault(entry.map_id, (strategy.domain, short_type))
        return cls(owners)

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
        ref = self._lookup(value, _as_domains(expected))
        if ref is None:
            return Unknown(UnknownReason.UNRESOLVED_REFERENCE, raw=freeze(value))
        return ref

    def resolve_list(self, value: Any, expected: ExpectedDomains) -> Observed:
        """A list of references; one unresolvable element makes the whole field unknown."""
        if not isinstance(value, list):
            return Unknown(UnknownReason.UNPARSEABLE, raw=freeze(value))
        domains = _as_domains(expected)
        refs: list[EntityRef] = []
        for item in value:
            ref = self._lookup(item, domains)
            if ref is None:
                return Unknown(UnknownReason.UNRESOLVED_REFERENCE, raw=freeze(value))
            refs.append(ref)
        return tuple(refs)
