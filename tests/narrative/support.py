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
from tinarrative.model.values import FrozenMap, Observed, Unknown
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

UNKNOWN = Unknown()
"""A shared unknown value for argument defaults (``Unknown`` is frozen, so one instance serves every caller)."""


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
    attributes: Sequence[tuple[str, Observed]] = (),
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
        attributes=tuple(attributes),
        significance=significance,
    )


def situation(
    date: Observed,
    *,
    nations: Sequence[EntityRef | NationSituation] = (),
    federations: Sequence[EntityRef | FederationSituation] = (),
    wars: Sequence[EntityRef | WarSituation] = (),
    factions: Sequence[EntityRef] = (),
    nuclear_strikes: Observed = UNKNOWN,
) -> SituationReport:
    """A report listing the given entities and nothing else; every other value is unknown or empty. A bare reference
    stands for a row with unknown values; ``nation_row``, ``federation_row`` and ``war_row`` build fuller ones."""
    return SituationReport(
        date=date,
        player_faction_name=Unknown(),
        nations=tuple(item if isinstance(item, NationSituation) else nation_row(item) for item in nations),
        federations=tuple(
            item if isinstance(item, FederationSituation) else FederationSituation(item, Unknown(), Unknown())
            for item in federations
        ),
        wars=tuple(item if isinstance(item, WarSituation) else war_row(item) for item in wars),
        factions=tuple(FactionSituation(item, None, 0, (), 0, 0, Unknown()) for item in factions),
        unattributed=Unattributed(0, 0, 0),
        world=WorldSituation(
            len(nations), Unknown(), Unknown(), Unknown(), Unknown(), (("nuclearStrikes", nuclear_strikes),), ()
        ),
    )


def nation_row(
    item: EntityRef,
    *,
    gdp: Observed = UNKNOWN,
    executive: Observed = UNKNOWN,
    seat_basis: str | None = None,
    shares: Sequence[tuple[EntityRef, int]] | None = None,
    control_points: Observed = UNKNOWN,
    federation: Observed = None,
    allies: Sequence[EntityRef] = (),
    alien: bool = False,
) -> NationSituation:
    """A nation row; ``shares`` are points held per faction."""
    return NationSituation(
        nation=item,
        executive=executive,  # type: ignore[arg-type]
        seat_basis=seat_basis,
        control_points=control_points,  # type: ignore[arg-type]
        shares=Unknown()
        if shares is None
        else FrozenMap(tuple((str(holder.entity_id), count) for holder, count in shares)),
        unresolved_points=0,
        federation=federation,
        allies=tuple(allies),
        wars=(),
        regions=Unknown(),
        population=Unknown(),
        statistics=(("GDP", gdp),),
        alien=alien,
    )


def federation_row(item: EntityRef, members: Sequence[EntityRef]) -> FederationSituation:
    return FederationSituation(item, Unknown(), tuple(members))


def war_row(
    item: EntityRef,
    attackers: Sequence[EntityRef] = (),
    defenders: Sequence[EntityRef] = (),
    start_date: Observed = UNKNOWN,
) -> WarSituation:
    return WarSituation(
        item,
        attackers[0] if attackers else Unknown(),
        defenders[0] if defenders else Unknown(),
        tuple(attackers),
        tuple(defenders),
        start_date,
        Unknown(),
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
