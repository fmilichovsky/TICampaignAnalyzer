"""Every declared event kind by its type, and the one constructor of a kind's attributes (ADR-0001)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from ..model.kinds import EventKind
from ..model.values import Observed
from . import aliens, campaign, control, military, nations, space, technology, wars

FAMILIES: tuple[tuple[EventKind, ...], ...] = (aliens.KINDS,)
NARRATIVE_FAMILIES: tuple[tuple[EventKind, ...], ...] = (
    campaign.NARRATIVE_KINDS,
    control.NARRATIVE_KINDS,
    military.NARRATIVE_KINDS,
    nations.NARRATIVE_KINDS,
    space.NARRATIVE_KINDS,
    technology.NARRATIVE_KINDS,
    wars.NARRATIVE_KINDS,
)
"""The narrative-event kinds of each family module, whose level a rule sets."""


def _registry(families: Iterable[Iterable[EventKind]]) -> Mapping[str, EventKind]:
    kinds: dict[str, EventKind] = {}
    for family in families:
        for kind in family:
            if kind.event_type in kinds:
                raise ValueError(f"event type {kind.event_type} is declared twice")
            kinds[kind.event_type] = kind
    return MappingProxyType(kinds)


KINDS: Mapping[str, EventKind] = _registry([*FAMILIES, *NARRATIVE_FAMILIES])


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
