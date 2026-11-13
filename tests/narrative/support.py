"""Builders for synthetic qualified event streams and situation reports, and a trivial narrative rule."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from tinarrative.kinds import attributes as kind_attributes
from tinarrative.kinds import kind_for
from tinarrative.kinds.narrative import narrative_kind
from tinarrative.model.changes import StateChange
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import (
    UNSCORED,
    Confidence,
    DateBasis,
    Event,
    EventSource,
    EventStatus,
    Role,
    Significance,
)
from tinarrative.model.evidence import Evidence, SourceLocation
from tinarrative.model.kinds import EventKind
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


def narrative_fixture_kind(event_type: str, base: Significance = Significance.TRIVIAL) -> EventKind:
    """A throwaway narrative-event kind without attributes, scored from ``base``."""
    return narrative_kind(event_type, lambda event: event.id, frozenset(), base=base)


TEST_CITING = narrative_fixture_kind("test.citing")
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


def declared_attributes(
    event_type: str, attributes: Iterable[tuple[str, Observed]]
) -> tuple[tuple[str, Observed], ...]:
    """``attributes`` checked by the type's kind, its required keys the test left out filled with ``Unknown``."""
    values = tuple(attributes)
    kind = kind_for(event_type)
    if kind is None:
        return values
    missing = ((name, Unknown()) for name in sorted(kind.required - dict(values).keys()))
    # EventBuilder generates this context attribute after validating the kind's declared attributes.
    generated = tuple((name, value) for name, value in values if name == "faction_kinds")
    declared = tuple((name, value) for name, value in values if name != "faction_kinds")
    return (*kind_attributes(kind, (*missing, *declared)), *generated)


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
    score: int = UNSCORED,
    entities: Sequence[EntityRef] = (),
    sources: Sequence[EventSource] = (),
    attributes: Sequence[tuple[str, Observed]] = (),
) -> Event:
    """An event of the interval ``key``, already qualified as ``run_sequence`` yields it; dated by ``key`` unless a
    ``date`` is given."""
    event_type = raw_id.split("/")[0]
    event_attributes = declared_attributes(event_type, attributes)
    return Event(
        id=qualified_id(raw_id, key),
        event_type=event_type,
        status=status,
        confidence=confidence,
        date=key if date is None else date,
        date_basis=date_basis,
        not_before=not_before,
        sources=tuple(sources),
        entities=tuple(entities),
        attributes=event_attributes,
        significance=significance,
        score=score,
    )


def unification(
    key: str, gainer: EntityRef, absorbed: EntityRef, *, not_before: Observed, unifier: EntityRef | None = None
) -> Event:
    """The inferred reading of ``gainer`` absorbing ``absorbed`` in interval ``key``, as the reconstruction emits it."""
    return atomic(
        f"nation.unification/{gainer.entity_id}",
        key,
        not_before=not_before,
        status=EventStatus.INFERRED,
        significance=Significance.MAJOR,
        entities=(gainer, absorbed, *((unifier,) if unifier is not None else ())),
        attributes=(
            ("unified", (absorbed,)),
            ("unifying_faction", unifier),
            ("bases", (FrozenMap((("nation", absorbed), ("basis", "federation"), ("federation", None))),)),
            ("executive_since", None),
        ),
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
    statistics: Mapping[str, Observed] | None = None,
    regions: Observed = UNKNOWN,
    armies: Observed = UNKNOWN,
    navies: Observed = UNKNOWN,
    strength: Observed = UNKNOWN,
    boost: Observed = UNKNOWN,
    mission_control: Observed = UNKNOWN,
    space_defence_regions: Observed = UNKNOWN,
    sto_fighters: Observed = UNKNOWN,
    nuclear_weapons: Observed = UNKNOWN,
) -> NationSituation:
    """A nation row; ``shares`` are points held per faction, ``statistics`` the values besides ``GDP``, the rest the
    region count and the asset fields."""
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
        regions=regions,  # type: ignore[arg-type]
        population=Unknown(),
        statistics=(("GDP", gdp), *(statistics or {}).items()),
        alien=alien,
        armies=armies,  # type: ignore[arg-type]
        navies=navies,  # type: ignore[arg-type]
        strength=strength,
        boost=boost,
        mission_control=mission_control,
        space_defence_regions=space_defence_regions,  # type: ignore[arg-type]
        sto_fighters=sto_fighters,
        nuclear_weapons=nuclear_weapons,
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

    The subject is the actor and the anchor; ``window_days`` is declared, not used. A narrative ``source_type`` is
    seen only when ``reads`` or ``explains`` names it.
    """

    name: str
    source_type: str
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    window_days: int | None = None
    join: Join = Join.ENTITY
    base: Significance = Significance.TRIVIAL
    """The base level of the ``.arc`` kind the rule builds."""
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
                narrative_fixture_kind(f"{self.source_type}.arc", self.base),
                id_parts=[subject.entity_id],
                constituents=events,
                roles=[(Role.ACTOR, subject)],
                join=self.join,
                anchor=subject,
                confidence=self.confidence,
            )
            for subject, events in by_subject.items()
        ]

    @property
    def emitted_types(self) -> frozenset[str]:
        return frozenset({f"{self.source_type}.arc"})


@dataclass(frozen=True)
class CitingRule:
    """A rule that emits one event citing the given events, whatever the stream holds."""

    name: str
    cites: tuple[Event, ...]
    reads: frozenset[str] = frozenset()
    window_days: int | None = None
    emitted_types: frozenset[str] = frozenset({"test.citing"})
    explains: frozenset[str] = frozenset()

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        return [build.event(TEST_CITING, id_parts=[self.name], constituents=self.cites, roles=(), join=Join.ENTITY)]


def loyalty_keys(document: object) -> list[str]:
    """The keys of a JSON document that name loyalty; a value may (the ``LoyaltyMonitor`` augment is a trait)."""
    if isinstance(document, Mapping):
        own = [str(key) for key in document if "loyalty" in str(key).lower()]
        return own + [key for value in document.values() for key in loyalty_keys(value)]
    if isinstance(document, list):
        return [key for item in document for key in loyalty_keys(item)]
    return []
