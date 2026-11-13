"""Every declared event kind by its type, and the one constructor of a kind's attributes (ADR-0001)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from ..model.kinds import EventKind, EvidenceRole
from ..model.values import Observed
from . import aliens, campaign, control, faction, federations, military, nations, space, technology, wars

FAMILIES: tuple[tuple[EventKind, ...], ...] = (
    aliens.KINDS,
    campaign.KINDS,
    control.KINDS,
    faction.KINDS,
    federations.KINDS,
    military.KINDS,
    nations.KINDS,
    space.KINDS,
    technology.KINDS,
    wars.KINDS,
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
"""Every kind by its declared type; a prefix kind is keyed by its pattern (``notification.*``)."""
PREFIX_KINDS: tuple[EventKind, ...] = tuple(kind for kind in KINDS.values() if kind.is_prefix)


def kind_for(event_type: str) -> EventKind | None:
    """Return the exact declaration, else the prefix kind covering the type (a save-supplied notification type)."""
    exact = KINDS.get(event_type)
    if exact is not None:
        return exact
    return next((kind for kind in PREFIX_KINDS if event_type.startswith(kind.prefix)), None)


def is_evidence(event_type: str) -> bool:
    """Whether the narrator package lists events of the type as evidence: its kind's declared role; an undeclared
    type is not evidence."""
    kind = kind_for(event_type)
    return kind is not None and kind.evidence is EvidenceRole.EVIDENCE


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
