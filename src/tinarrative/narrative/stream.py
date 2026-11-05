"""The visible event stream of one rule order, indexed once by type, subject, mention, interval and ID.

Every lookup returns events in stream order, so it equals the matching filter over the stream.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from functools import cached_property
from typing import overload

from ..model.entities import EntityId
from ..model.events import Event
from .chronology import interval_of

_Index = dict[tuple[str, object], list[int]]


class EventStream(Sequence[Event]):
    """A read-only sequence of events with lazily built position indexes."""

    def __init__(self, events: Iterable[Event]) -> None:
        self._events = tuple(events)

    @classmethod
    def of(cls, events: Iterable[Event]) -> EventStream:
        return events if isinstance(events, EventStream) else cls(events)

    @overload
    def __getitem__(self, index: int) -> Event: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[Event]: ...

    def __getitem__(self, index: int | slice) -> Event | Sequence[Event]:
        return self._events[index]

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[Event]:
        return iter(self._events)

    def of_type(self, *types: str) -> list[Event]:
        return self._pick(self._by_type.get(event_type, []) for event_type in types)

    def of_subject(self, subjects: EntityId | Iterable[EntityId], *types: str) -> list[Event]:
        """Events whose first entity is one of ``subjects``."""
        keys = (subjects,) if isinstance(subjects, EntityId) else subjects
        return self._lookup(self._by_subject, keys, types)

    def mentioning(self, entity_id: EntityId, *types: str) -> list[Event]:
        """Events naming ``entity_id`` among their entities."""
        return self._lookup(self._by_mention, (entity_id,), types)

    def in_intervals(self, keys: str | Iterable[str], *types: str) -> list[Event]:
        """Events whose ID is qualified by one of the interval ``keys``."""
        return self._lookup(self._by_interval, (keys,) if isinstance(keys, str) else keys, types)

    def get(self, event_id: str) -> Event | None:
        position = self._position.get(event_id)
        return None if position is None else self._events[position]

    def union(self, *groups: Iterable[Event]) -> list[Event]:
        """Events of this stream in any of ``groups``, once each."""
        return self._pick([self._position[event.id] for event in group] for group in groups)

    def _lookup(self, index: _Index, keys: Iterable[object], types: Sequence[str]) -> list[Event]:
        return self._pick(index.get((event_type, key), []) for key in keys for event_type in types)

    def _pick(self, groups: Iterable[Iterable[int]]) -> list[Event]:
        return [self._events[position] for position in sorted({position for group in groups for position in group})]

    @cached_property
    def _position(self) -> dict[str, int]:
        return {event.id: position for position, event in enumerate(self._events)}

    @cached_property
    def _by_type(self) -> dict[str, list[int]]:
        index: dict[str, list[int]] = defaultdict(list)
        for position, event in enumerate(self._events):
            index[event.event_type].append(position)
        return index

    @cached_property
    def _by_subject(self) -> _Index:
        index: _Index = defaultdict(list)
        for position, event in enumerate(self._events):
            if event.entities:
                index[(event.event_type, event.entities[0].entity_id)].append(position)
        return index

    @cached_property
    def _by_mention(self) -> _Index:
        index: _Index = defaultdict(list)
        for position, event in enumerate(self._events):
            for entity_id in dict.fromkeys(ref.entity_id for ref in event.entities):
                index[(event.event_type, entity_id)].append(position)
        return index

    @cached_property
    def _by_interval(self) -> _Index:
        index: _Index = defaultdict(list)
        for position, event in enumerate(self._events):
            index[(event.event_type, interval_of(event.id))].append(position)
        return index
