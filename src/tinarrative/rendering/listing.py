"""Which events a sequence report lists, shared by the Markdown and the JSON renderer so the two cannot drift.

Without a narrative, objective and inferred events are filtered by significance. With one, the minimum filters the
narrative events, and an atomic event is listed only as a constituent of a listed narrative event, followed
transitively through lower-order narrative events and inferred events, and only when constituents are included. A
lower-order narrative event that a listed one cites is listed whatever its significance, so every cited ID resolves.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ..model.events import Event, Significance
from ..sequence import IntervalResult, event_stream


@dataclass(frozen=True)
class Listing:
    """The events a report lists; ``constituents`` is ``None`` when atomic events are filtered by significance."""

    minimum: Significance
    narrative: tuple[Event, ...] | None
    constituents: frozenset[str] | None
    include_constituents: bool

    def keeps(self, event: Event) -> bool:
        """Whether an objective or inferred event is listed."""
        if self.constituents is None:
            return event.significance.rank >= self.minimum.rank
        return event.id in self.constituents

    def kept(self, events: Iterable[Event]) -> tuple[Event, ...]:
        return tuple(event for event in events if self.keeps(event))

    @property
    def filters(self) -> bool:
        """Whether an atomic event can be left out at all."""
        return self.constituents is not None or self.minimum is not Significance.TRIVIAL

    def reason(self) -> str:
        """Why an atomic event is not listed, completing ``N events ...``."""
        if self.constituents is None:
            return f"below {self.minimum.value} significance omitted"
        if self.include_constituents:
            return "omitted: not cited by a listed narrative event"
        return "omitted without --include-constituents"


def listing(
    intervals: Sequence[IntervalResult],
    narrative: Sequence[Event] | None,
    *,
    minimum: Significance,
    include_constituents: bool = False,
) -> Listing:
    """What to list of ``intervals`` and ``narrative`` at ``minimum``."""
    if narrative is None:
        return Listing(minimum, None, None, include_constituents)
    listed = {event.id for event in narrative if event.significance.rank >= minimum.rank}
    atomic: set[str] = set()
    if include_constituents:
        narrative_ids = {event.id: event for event in narrative}
        stream = {event.id: event for event in event_stream(intervals)}
        pending = [constituent for event in narrative if event.id in listed for constituent in event.constituents]
        while pending:
            current = pending.pop()
            if current in listed or current in atomic:
                continue
            found = narrative_ids.get(current)
            if found is not None:
                listed.add(current)
            else:
                found = stream.get(current)
                if found is None:
                    continue
                atomic.add(current)
            pending.extend(found.constituents)
    return Listing(
        minimum,
        tuple(event for event in narrative if event.id in listed),
        frozenset(atomic),
        include_constituents,
    )
