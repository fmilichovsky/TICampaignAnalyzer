"""Which events a sequence report lists, shared by the Markdown and the JSON renderer so the two cannot drift.

Without a narrative, objective and inferred events are filtered by significance. With one, the minimum filters the
narrative events, and an atomic event is listed only as a constituent of a listed narrative event, followed
transitively through lower-order narrative events and inferred events, as the ``constituents`` mode says: ``all`` of
them, the narrator ``evidence`` among them, or ``none``. A lower-order narrative event that a listed one cites is
listed whatever its significance, so every cited narrative ID resolves.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from ..model.events import Event, Significance
from ..sequence import IntervalResult, event_stream

Constituents = Literal["all", "evidence", "none"]
CONSTITUENTS: Final[tuple[Constituents, ...]] = ("all", "evidence", "none")

WITHHELD: Final = "omitted with --constituents none"
NOT_CITED: Final = "omitted: not cited by a listed narrative event"
NOT_EVIDENCE: Final = "omitted: not narrator evidence"


@dataclass(frozen=True)
class Listing:
    """The events a report lists; ``constituents`` is ``None`` when atomic events are filtered by significance.

    ``reached`` holds every objective and inferred event the listed narrative events are built from, listed or not.
    """

    minimum: Significance
    narrative: tuple[Event, ...] | None
    constituents: frozenset[str] | None
    reached: frozenset[str]
    mode: Constituents

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

    def reason(self, event: Event) -> str:
        """Why an atomic event is not listed, completing ``N events ...``."""
        if self.constituents is None:
            return f"below {self.minimum.value} significance omitted"
        if self.mode == "none":
            return WITHHELD
        if event.id not in self.reached:
            return NOT_CITED
        return NOT_EVIDENCE

    def omissions(self, events: Iterable[Event]) -> list[tuple[int, str]]:
        """How many of ``events`` are not listed, per reason, in a fixed order."""
        counts = Counter(self.reason(event) for event in events if not self.keeps(event))
        order = (f"below {self.minimum.value} significance omitted", WITHHELD, NOT_CITED, NOT_EVIDENCE)
        return [(counts[reason], reason) for reason in order if counts[reason]]


def listing(
    intervals: Sequence[IntervalResult],
    narrative: Sequence[Event] | None,
    *,
    minimum: Significance,
    constituents: Constituents = "none",
) -> Listing:
    """What to list of ``intervals`` and ``narrative`` at ``minimum``."""
    if narrative is None:
        return Listing(minimum, None, None, frozenset(), constituents)
    listed = {event.id for event in narrative if event.significance.rank >= minimum.rank}
    atomic: set[str] = set()
    if constituents != "none":
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
    # TODO(#160): keep only narrator evidence in the evidence mode.
    return Listing(
        minimum,
        tuple(event for event in narrative if event.id in listed),
        frozenset(atomic),
        frozenset(atomic),
        constituents,
    )
