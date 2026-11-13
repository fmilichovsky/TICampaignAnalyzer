"""The event stream a narrative rule sees, indexed once by type, subject, mention, interval and ID.

Every lookup returns events in stream order, so it equals the matching filter over the stream.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable, Iterator, Sequence
from functools import cached_property
from typing import overload

from ..model.entities import EntityId
from ..model.events import Event
from .chronology import interval_of

_Index = dict[tuple[str, object], list[int]]


class UndeclaredRead(ValueError):
    """A typed lookup of event types the stream hides: a programming error in the reading rule."""

    def __init__(self, types: Collection[str]) -> None:
        self.types = tuple(sorted(types))
        super().__init__(f"reads {list(self.types)}, which it does not declare")


class EventStream(Sequence[Event]):
    """A read-only sequence of events with lazily built position indexes.

    A stream ``hiding`` some event types or ``withholding`` some events shares the indexes of the stream it came from.
    """

    def __init__(self, events: Iterable[Event]) -> None:
        self._indexes = _Indexes(tuple(events))
        self._hidden: frozenset[str] = frozenset()
        self._withheld: frozenset[str] = frozenset()
        self._shown: tuple[Event, ...] | None = None

    @classmethod
    def of(cls, events: Iterable[Event]) -> EventStream:
        return events if isinstance(events, EventStream) else cls(events)

    def hiding(self, types: Iterable[str]) -> EventStream:
        """This stream without the events of ``types``: a typed lookup of one raises ``UndeclaredRead``."""
        hidden = self._hidden | frozenset(types)
        if hidden == self._hidden:
            return self
        return self._view(hidden, self._withheld)

    def withholding(self, event_ids: Iterable[str]) -> EventStream:
        """This stream with the events of ``event_ids`` still read but no longer ``citable``."""
        withheld = self._withheld | frozenset(event_ids)
        if withheld == self._withheld:
            return self
        return self._view(self._hidden, withheld)

    def citable(self, event: Event) -> bool:
        """Whether a rule reading this stream may cite ``event``: not the exclusive constituent of another kind."""
        return event.id not in self._withheld

    def _view(self, hidden: frozenset[str], withheld: frozenset[str]) -> EventStream:
        view = EventStream(())
        view._indexes, view._hidden, view._withheld = self._indexes, hidden, withheld
        return view

    @overload
    def __getitem__(self, index: int) -> Event: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[Event]: ...

    def __getitem__(self, index: int | slice) -> Event | Sequence[Event]:
        return self._visible[index]

    def __len__(self) -> int:
        return len(self._visible)

    def __iter__(self) -> Iterator[Event]:
        return iter(self._visible)

    def of_type(self, *types: str) -> list[Event]:
        self._require(types)
        return self._indexes.pick(self._indexes.by_type.get(event_type, []) for event_type in types)

    def of_subject(self, subjects: EntityId | Iterable[EntityId], *types: str) -> list[Event]:
        """Events whose first entity is one of ``subjects``."""
        keys = (subjects,) if isinstance(subjects, EntityId) else subjects
        return self._lookup(self._indexes.by_subject, keys, types)

    def mentioning(self, entity_id: EntityId, *types: str) -> list[Event]:
        """Events naming ``entity_id`` among their entities."""
        return self._lookup(self._indexes.by_mention, (entity_id,), types)

    def in_intervals(self, keys: str | Iterable[str], *types: str) -> list[Event]:
        """Events whose ID is qualified by one of the interval ``keys``."""
        return self._lookup(self._indexes.by_interval, (keys,) if isinstance(keys, str) else keys, types)

    def get(self, event_id: str) -> Event | None:
        position = self._indexes.position.get(event_id)
        event = None if position is None else self._indexes.events[position]
        return None if event is None or event.event_type in self._hidden else event

    def union(self, *groups: Iterable[Event]) -> list[Event]:
        """Events of this stream in any of ``groups``, once each."""
        return self._indexes.pick([self._indexes.position[event.id] for event in group] for group in groups)

    @property
    def _visible(self) -> tuple[Event, ...]:
        if self._shown is None:
            events = self._indexes.events
            self._shown = tuple(event for event in events if event.event_type not in self._hidden)
        return self._shown

    def _require(self, types: Iterable[str]) -> None:
        hidden = self._hidden.intersection(types)
        if hidden:
            raise UndeclaredRead(hidden)

    def _lookup(self, index: _Index, keys: Iterable[object], types: Sequence[str]) -> list[Event]:
        self._require(types)
        return self._indexes.pick(index.get((event_type, key), []) for key in keys for event_type in types)


class _Indexes:
    def __init__(self, events: tuple[Event, ...]) -> None:
        self.events = events

    def pick(self, groups: Iterable[Iterable[int]]) -> list[Event]:
        return [self.events[position] for position in sorted({position for group in groups for position in group})]

    @cached_property
    def position(self) -> dict[str, int]:
        return {event.id: position for position, event in enumerate(self.events)}

    @cached_property
    def by_type(self) -> dict[str, list[int]]:
        index: dict[str, list[int]] = defaultdict(list)
        for position, event in enumerate(self.events):
            index[event.event_type].append(position)
        return index

    @cached_property
    def by_subject(self) -> _Index:
        index: _Index = defaultdict(list)
        for position, event in enumerate(self.events):
            if event.entities:
                index[(event.event_type, event.entities[0].entity_id)].append(position)
        return index

    @cached_property
    def by_mention(self) -> _Index:
        index: _Index = defaultdict(list)
        for position, event in enumerate(self.events):
            for entity_id in dict.fromkeys(ref.entity_id for ref in event.entities):
                index[(event.event_type, entity_id)].append(position)
        return index

    @cached_property
    def by_interval(self) -> _Index:
        index: _Index = defaultdict(list)
        for position, event in enumerate(self.events):
            index[(event.event_type, interval_of(event.id))].append(position)
        return index
