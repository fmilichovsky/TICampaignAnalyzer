"""Every declared event kind by its type, and the one constructor of a kind's attributes (ADR-0001)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from ..model.kinds import EventKind
from ..model.values import Observed
from . import aliens, campaign, faction, military, technology

FAMILIES: tuple[tuple[EventKind, ...], ...] = (
    aliens.KINDS,
    campaign.KINDS,
    faction.KINDS,
    military.KINDS,
    technology.KINDS,
)


def _registry(families: Iterable[Iterable[EventKind]]) -> Mapping[str, EventKind]:
    kinds: dict[str, EventKind] = {}
    for family in families:
        for kind in family:
            if kind.event_type in kinds:
                raise ValueError(f"event type {kind.event_type} is declared twice")
            kinds[kind.event_type] = kind
    return MappingProxyType(kinds)


KINDS: Mapping[str, EventKind] = _registry(FAMILIES)
_PREFIX_KINDS = tuple(kind for kind in KINDS.values() if kind.prefix)


def kind_of(event_type: str) -> EventKind | None:
    """The kind declared for ``event_type``: its exact kind, else the prefix kind it starts with, else ``None``."""
    kind = KINDS.get(event_type)
    if kind is not None:
        return kind
    return next((prefix for prefix in _PREFIX_KINDS if event_type.startswith(prefix.event_type)), None)


def attributes(
    kind: EventKind, pairs: Iterable[tuple[str, Observed]] = (), /, **values: Observed
) -> tuple[tuple[str, Observed], ...]:
    """The attributes of an event of ``kind``, from ``pairs`` then ``values``, in that order.

    Raises ``ValueError`` on a missing required key, an undeclared key or a key given twice: each is a code bug.
    """
    items = (*pairs, *values.items())
    keys = [key for key, _ in items]
    given = set(keys)
    problems = []
    if len(keys) != len(given):
        problems.append(f"repeated {sorted({key for key in keys if keys.count(key) > 1})}")
    if missing := kind.required - given:
        problems.append(f"missing {sorted(missing)}")
    if undeclared := given - kind.required - kind.optional:
        problems.append(f"undeclared {sorted(undeclared)}")
    if problems:
        raise ValueError(f"attributes of {kind.event_type}: {'; '.join(problems)}")
    return items
