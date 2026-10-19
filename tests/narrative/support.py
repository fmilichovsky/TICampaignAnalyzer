"""Builders for synthetic qualified event streams and situation reports, and a trivial narrative rule."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from tinarrative.model.changes import StateChange
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import (
    Confidence,
    DateBasis,
    Event,
    EventSource,
    EventStatus,
    Role,
    Significance,
)
from tinarrative.model.evidence import Evidence, SourceLocation
from tinarrative.model.values import Observed, Unknown
from tinarrative.narrative.aggregation import Join, NarrativeBuilder
from tinarrative.narrative.chronology import qualified_id
from tinarrative.narrative.situation import (
    FactionSituation,
    FederationSituation,
    NationSituation,
    SituationReport,
    Unattributed,
    WarSituation,
    WorldSituation,
)


def ref(domain: EntityDomain, key: str, name: str | None = None) -> EntityRef:
    return EntityRef(EntityId(domain, key), IdentityConfidence.IN_SAVE_ID, None, name)


def nation(key: str, name: str | None = None) -> EntityRef:
    return ref(EntityDomain.NATION, key, name)


def faction(key: str, name: str | None = None) -> EntityRef:
    return ref(EntityDomain.FACTION, key, name)


def war(key: str) -> EntityRef:
    return ref(EntityDomain.WAR, key)


def state_change(subject: EntityRef, field: str = "population") -> StateChange:
    """A literal change of one field of ``subject``, for events that need a source."""
    before = SourceLocation("before.save", "TINationState", int(subject.entity_id.key), f"/Value/{field}")
    after = SourceLocation("after.save", "TINationState", int(subject.entity_id.key), f"/Value/{field}")
    return StateChange(
        domain=subject.entity_id.domain.value,
        field=field,
        before=1,
        after=2,
        evidence=Evidence(subject.entity_id.domain.value, field, 1, 2, before, after),
        entity_id=subject.entity_id,
    )


def atomic(
    raw_id: str,
    key: str,
    *,
    date: Observed | None = None,
    not_before: Observed = "2032-01-01T00:00:00",
    date_basis: DateBasis = DateBasis.INTERVAL,
    status: EventStatus = EventStatus.OBJECTIVE,
    confidence: Confidence = Confidence.HIGH,
    significance: Significance = Significance.MINOR,
    entities: Sequence[EntityRef] = (),
    sources: Sequence[EventSource] = (),
) -> Event:
    """An event of the interval ``key``, already qualified as ``run_sequence`` yields it; dated by ``key`` unless a
    ``date`` is given."""
    return Event(
        id=qualified_id(raw_id, key),
        event_type=raw_id.split("/")[0],
        status=status,
        confidence=confidence,
        date=key if date is None else date,
        date_basis=date_basis,
        not_before=not_before,
        sources=tuple(sources),
        entities=tuple(entities),
        significance=significance,
    )


def situation(
    date: Observed,
    *,
    nations: Sequence[EntityRef] = (),
    federations: Sequence[EntityRef] = (),
    wars: Sequence[EntityRef] = (),
    factions: Sequence[EntityRef] = (),
) -> SituationReport:
    """A report listing the given entities and nothing else; every other value is unknown or empty."""
    return SituationReport(
        date=date,
        player_faction_name=Unknown(),
        nations=tuple(
            NationSituation(item, Unknown(), Unknown(), Unknown(), Unknown(), None, (), Unknown(), Unknown(), ())
            for item in nations
        ),
        federations=tuple(FederationSituation(item, Unknown(), Unknown()) for item in federations),
        wars=tuple(
            WarSituation(item, Unknown(), Unknown(), Unknown(), Unknown(), Unknown(), Unknown()) for item in wars
        ),
        factions=tuple(FactionSituation(item, None, 0, (), 0, 0, Unknown()) for item in factions),
        unattributed=Unattributed(0, 0, 0),
        world=WorldSituation(len(nations), Unknown(), Unknown(), Unknown(), Unknown(), (), ()),
    )


@dataclass(frozen=True)
class GroupRule:
    """A trivial rule: one ``<source_type>.arc`` per subject (first entity) over every event of ``source_type``.

    The subject is the actor and the anchor; ``window_days`` is declared, not used.
    """

    name: str
    source_type: str
    order: int = 0
    window_days: int | None = None
    join: Join = Join.ENTITY
    significance: Significance | None = None
    confidence: Confidence | None = None

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        by_subject: dict[EntityRef, list[Event]] = defaultdict(list)
        for event in stream:
            if event.event_type == self.source_type and event.entities:
                by_subject[event.entities[0]].append(event)
        return [
            build.event(
                f"{self.source_type}.arc",
                id_parts=[subject.entity_id],
                constituents=events,
                roles=[(Role.ACTOR, subject)],
                join=self.join,
                anchor=subject,
                significance=self.significance,
                confidence=self.confidence,
            )
            for subject, events in by_subject.items()
        ]


@dataclass(frozen=True)
class CitingRule:
    """A rule that emits one event citing the given events, whatever the stream holds."""

    name: str
    cites: tuple[Event, ...]
    order: int = 0
    window_days: int | None = None

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        return [build.event("test.citing", id_parts=[self.name], constituents=self.cites, roles=(), join=Join.ENTITY)]
