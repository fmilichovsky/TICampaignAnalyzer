"""Which events a sequence report lists, shared by the Markdown and the JSON renderer so the two cannot drift.

With a narrative, an atomic event is listed only as a transitive constituent of a listed narrative event (filtered
by the ``constituents`` mode). A lower-order narrative event that a listed one cites is listed whatever its
significance, so every cited narrative ID resolves; a member of a listed ``MEMBER_DIGESTS`` event is listed as a digest.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

from ..model.events import Event, Significance
from ..narrative.evidence import is_evidence
from ..narrative.geopolitics import TAKEOVER_WAVE
from ..sequence import IntervalResult, event_stream

Constituents = Literal["all", "evidence", "none"]
CONSTITUENTS: Final[tuple[Constituents, ...]] = ("all", "evidence", "none")

WITHHELD: Final = "omitted with --constituents none"
NOT_CITED: Final = "omitted: not cited by a listed narrative event"
NOT_EVIDENCE: Final = "omitted: not narrator evidence"

MEMBER_DIGESTS: Final[frozenset[str]] = frozenset({TAKEOVER_WAVE})
"""narrative events that tell their narrative members together: a member only they cite is listed as a digest, whatever
its own significance, and its own constituents are not reached through it."""


@dataclass(frozen=True)
class Listing:
    """``constituents`` is ``None`` when atomic events are filtered by significance.

    ``reached`` holds every objective and inferred event the listed narrative events are built from, listed or not.
    ``digested`` maps each narrative event listed as a digest to the narrative event it is a member of; ``narrative``
    holds both kinds.
    """

    minimum: Significance
    narrative: tuple[Event, ...] | None
    constituents: frozenset[str] | None
    reached: frozenset[str]
    mode: Constituents
    digested: Mapping[str, str] = field(default_factory=dict)

    def keeps(self, event: Event) -> bool:
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
    if narrative is None:
        return Listing(minimum, None, None, frozenset(), constituents)
    roots = {event.id for event in narrative if event.significance.rank >= minimum.rank}
    full, digested = _split(narrative, roots, follow=constituents != "none")
    atomic: dict[str, Event] = {}
    if constituents != "none":
        narrative_ids = {event.id for event in narrative}
        stream = {event.id: event for event in event_stream(intervals)}
        pending = [constituent for event in narrative if event.id in full for constituent in event.constituents]
        while pending:
            current = pending.pop()
            if current in narrative_ids or current in atomic:
                continue
            found = stream.get(current)
            if found is None:
                continue
            atomic[current] = found
            pending.extend(found.constituents)
    kept = {key for key, event in atomic.items() if constituents == "all" or is_evidence(event.event_type)}
    return Listing(
        minimum,
        tuple(event for event in narrative if event.id in full or event.id in digested),
        frozenset(kept),
        frozenset(atomic),
        constituents,
        digested,
    )


def _split(narrative: Sequence[Event], roots: set[str], *, follow: bool) -> tuple[set[str], dict[str, str]]:
    """The narrative events listed in full, and those listed as digests with the narrative event citing them.

    An event is decided after every event citing it (citations only reach earlier layers, so this terminates): in full
    when a full non-digesting event cites it and it is a root or ``follow`` holds, else a digest when a full
    ``MEMBER_DIGESTS`` event cites it, else in full when it is a root.
    """
    by_id = {event.id: event for event in narrative}
    citers: dict[str, list[Event]] = defaultdict(list)
    for event in sorted(narrative, key=lambda item: item.sort_key):
        for constituent in event.constituents:
            if constituent in by_id:
                citers[constituent].append(event)
    full: set[str] = set()
    digested: dict[str, str] = {}
    decided: set[str] = set()

    def decide(identifier: str) -> None:
        if identifier in decided:
            return
        decided.add(identifier)
        for citer in citers[identifier]:
            decide(citer.id)
        listing_citers = [citer for citer in citers[identifier] if citer.id in full]
        waves = [citer for citer in listing_citers if citer.event_type in MEMBER_DIGESTS]
        if len(waves) < len(listing_citers) and (follow or identifier in roots):
            full.add(identifier)
        elif waves:
            digested[identifier] = waves[0].id
        elif identifier in roots:
            full.add(identifier)

    for identifier in by_id:
        decide(identifier)
    return full, digested
