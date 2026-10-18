"""Explicit reconstruction rules: territorial changes read from region, tracker, executive and war evidence.

Every rule here takes the objective events of one interval (plus the diff and the two snapshots for context) and
returns inferred events. An inferred event names each objective event it rests on in ``constituents`` and cites
all of their sources, so it never loses the evidence beneath it (architecture sections 6 and 10). A diff change
that no analyzer reports (a region's annexation flags) is cited directly. A fact read from a snapshot alone (a
nation holding no regions afterwards, the sides of a war) only qualifies evidence, it is never the evidence.

The evidence is the investigation of 2026-10-14 recorded in ``docs/game-data-notes/higher-level-event-sources.md``
(eight private saves of two campaigns, structure and counts only). In one interval a nation gained many regions
while its GDP delta sat under ``GDPReason_TerritoryChange``, its inequality under ``InqReason_Annexation`` and its
democracy under ``DemReason_AmicableRelease``, and the counterpart lost the same regions; in another a nation's
cohesion delta was under ``CohesionReason_Independence`` with ``lastExecutiveChange.cause = Independence`` and its
control-point count rising from 1 to 4. Re-checked on 2026-10-18 on the two independences of the older sample: both
released nations carried ``DemReason_AmicableRelease`` and both parents ``CohesionReason_NationReleased`` and
``UnrestReason_NationReleased``, so the pair marks a release decided by the parent, not a unification.

Rules:

- ``nation.territory_gained`` / ``nation.territory_lost``: one per nation that gained or lost regions, aggregating
  every ``region.nation_changed`` with a known nation on both sides; high when the nation's tracker maps moved under
  a territory reason, medium on the region events alone.
- ``nation.independence``: a gainer with an ``Independence`` executive cause, an ``*Reason_Independence`` tracker
  delta (on it or on a nation it gained from), a breakaway-parent change, ``DemReason_AmicableRelease`` on it or
  ``*Reason_NationReleased`` on a nation whose moved regions all went to it; high with two signals, medium with
  one. Either release reason marks it ``released`` and names the releasing nation: the earlier holder of the new
  nation's capital when the capital moved in the interval, else its only parent.
- ``nation.unification``: a gainer that took every region of two or more nations; medium.
- ``nation.annexation``: a gainer and loser pair with an annexation flag change on a transferred region or a
  war event in the interval of a war with the two on opposite sides; medium.

When more than one of independence, unification and annexation fits one gainer, every candidate is kept one
confidence level lower, marked ``ambiguous`` and naming the others in ``alternatives``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace

from ..analyzers.common import ChangeIndex, EventBuilder, Lookup, Side, event_id
from ..analyzers.politics.nation_metrics import STATISTIC_SHIFTED, TRACKERS, cause_deltas
from ..analyzers.politics.nations import (
    BREAKAWAY_PARENT_CHANGED,
    DISAPPEARED,
    EXECUTIVE_CHANGE_RECORDED,
    REGION_NATION_CHANGED,
    RELATION_CHANGED,
)
from ..analyzers.politics.wars import ATTACKERS, DEFENDERS, side_members
from ..model.changes import StateChange, StateDiff
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import Confidence, Event, EventSource, EventStatus, SourceRole
from ..model.evidence import SourceLocation
from ..model.snapshot import SaveSnapshot
from ..model.values import FieldValue, FrozenMap, Observed, Unknown

TERRITORY_GAINED = "nation.territory_gained"
TERRITORY_LOST = "nation.territory_lost"
INDEPENDENCE = "nation.independence"
UNIFICATION = "nation.unification"
ANNEXATION = "nation.annexation"
INTERPRETATIONS = (INDEPENDENCE, UNIFICATION, ANNEXATION)
"""Competing readings of one gainer's territory; two of them on one gainer make every candidate ambiguous."""
RULE_TYPES = (TERRITORY_GAINED, TERRITORY_LOST, *INTERPRETATIONS)

TERRITORY_REASONS = frozenset({"TerritoryChange", "Annexation", "RegionTransfer"})
"""Tracker reason suffixes that name a region transfer: ``GDPReason_TerritoryChange``, ``InqReason_Annexation``,
``CohesionReason_Annexation``, ``UnrestReason_RegionTransfer``, ``EducationReason_RegionTransfer`` (notes,
metric cause attribution)."""
INDEPENDENCE_REASON = "Independence"
"""The tracker reason suffix (``GDPReason_``, ``CohesionReason_``, ``UnrestReason_Independence``) and the
``lastExecutiveChange.cause`` value observed together on a nation gaining regions."""
AMICABLE_RELEASE = "DemReason_AmicableRelease"
"""Observed on the released nation in both independences of the older sample (+4.5 and +5.0 democracy)."""
NATION_RELEASED_REASON = "NationReleased"
"""The tracker reason suffix (``CohesionReason_``, ``UnrestReason_NationReleased``) observed on the parent in both
independences of the older sample: the game's attribution of the change to releasing a nation."""
EXECUTIVE_POINT = "Executive"
"""The ``controlPointType`` of a nation's executive control point."""
ANNEXATION_FIELDS = ("isBeingAnnexed", "annexingArmy")
"""Region fields that track an annexation in progress; left in the diff by every analyzer."""
WAR_PREFIX = "war."
WAR_RELATION = "wars"
MIN_UNIFIED = 2
"""Nations giving up every region to one gainer that make a unification. One such nation is not enough: a release
that hands over a parent's last region, or a plain conquest, looks the same."""

_TRACKER_STATISTICS = {tracker: statistic for statistic, tracker in TRACKERS.items()}
_LOWER = {Confidence.HIGH: Confidence.MEDIUM, Confidence.MEDIUM: Confidence.LOW, Confidence.LOW: Confidence.LOW}


@dataclass(frozen=True)
class Support:
    """Evidence behind a rule: constituent events, and diff changes no event reports (cited directly)."""

    events: tuple[Event, ...] = ()
    changes: tuple[StateChange, ...] = ()

    def __add__(self, other: Support) -> Support:
        return Support(self.events + other.events, self.changes + other.changes)

    def __bool__(self) -> bool:
        return bool(self.events or self.changes)


@dataclass(frozen=True)
class Transfer:
    """One ``region.nation_changed`` with a known nation on both sides."""

    event: Event
    region: EntityRef
    loser: EntityId
    gainer: EntityId


class Context:
    """The interval's events indexed for the rules, with the diff and snapshot lookups beside them."""

    def __init__(self, events: Iterable[Event], before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> None:
        self.index = ChangeIndex(diff)
        self.lookup = Lookup(before, after)
        self.build = EventBuilder(before, after)
        self.events: list[Event] = []
        self.by_id: dict[str, Event] = {}
        self.by_subject: dict[tuple[str, EntityId], list[Event]] = defaultdict(list)
        self.transfers: list[Transfer] = []
        self._refs: dict[EntityId, EntityRef] = {}
        self.gainers_of: dict[EntityId, set[EntityId]] = defaultdict(set)
        for event in events:
            if event.status is not EventStatus.OBJECTIVE:
                continue
            self.events.append(event)
            self.by_id[event.id] = event
            if event.entities:
                self.by_subject[(event.event_type, event.entities[0].entity_id)].append(event)
            transfer = _transfer(event)
            if transfer is not None:
                self.transfers.append(transfer)
                self.gainers_of[transfer.loser].add(transfer.gainer)
                for value in (event.attribute("before"), event.attribute("after")):
                    if isinstance(value, EntityRef):
                        self._refs.setdefault(value.entity_id, value)

    def subject_events(self, event_type: str, nation: EntityId) -> tuple[Event, ...]:
        return tuple(self.by_subject.get((event_type, nation), ()))

    def ref(self, entity_id: EntityId) -> EntityRef:
        """The nation's own reference, else the reference a region event carried (every nation here came from one)."""
        return self.lookup.ref(entity_id) or self._refs[entity_id]

    def reasons(self, nation: EntityId, accept: Callable[[str], bool]) -> tuple[tuple[str, ...], Support]:
        """The tracker reasons of ``nation`` that moved in the interval and that ``accept`` takes, with their support.

        A tracker change is cited through the ``nation.statistic_shifted`` event that already cites it, and
        directly when the statistic stayed below its threshold.
        """
        keys: set[str] = set()
        support = Support()
        for tracker, statistic in _TRACKER_STATISTICS.items():
            change = self.index.field(nation, tracker)
            if change is None:
                continue
            deltas = cause_deltas(change.before, change.after)
            if not isinstance(deltas, FrozenMap):
                continue
            found = {reason for reason, _ in deltas.items if accept(reason)}
            if not found:
                continue
            keys |= found
            shifted = self.by_id.get(event_id(STATISTIC_SHIFTED, nation, statistic))
            support += Support(events=(shifted,)) if shifted is not None else Support(changes=(change,))
        return tuple(sorted(keys)), support

    def region_less_after(self, nation: EntityId) -> Support | None:
        """Support (possibly empty) when ``nation`` holds no regions in the later save; ``None`` otherwise."""
        disappeared = self.subject_events(DISAPPEARED, nation)
        if disappeared:
            return Support(events=disappeared)
        state = self.lookup.state(nation, Side.AFTER)
        if state is not None and state.get("regions") == ():
            return Support()
        return None

    def executive_faction(self, nation: EntityId) -> Observed:
        """The faction controlling ``nation``'s executive control point in the earlier snapshot (``null`` when none
        does); ``Unknown`` when the nation or the point is not found."""
        state = self.lookup.state(nation, Side.BEFORE)
        points = state.get("controlPoints") if state is not None else None
        for point in points if isinstance(points, tuple) else ():
            if not isinstance(point, EntityRef):
                continue
            point_state = self.lookup.state(point.entity_id, Side.BEFORE)
            if point_state is not None and point_state.get("controlPointType") == EXECUTIVE_POINT:
                faction = point_state.get("faction")
                return self.lookup.resolve(faction) or faction
        return Unknown()

    def war_support(self, gainer: EntityId, loser: EntityId) -> Support:
        """War events of the interval about a war with the two nations on opposite sides, and their ``wars`` entries."""
        pair = {gainer, loser}
        found: list[Event] = []
        for event in self.events:
            if event.event_type.startswith(WAR_PREFIX) and event.entities:
                if self._opposed(event.entities[0].entity_id, gainer, loser):
                    found.append(event)
            elif event.event_type == RELATION_CHANGED and event.attribute("relation") == WAR_RELATION:
                if {ref.entity_id for ref in event.entities} == pair:
                    found.append(event)
        return Support(events=tuple(found))

    def _opposed(self, war: EntityId, first: EntityId, second: EntityId) -> bool:
        if war.domain is not EntityDomain.WAR:
            return False
        for side in (Side.BEFORE, Side.AFTER):
            attackers = side_members(self.lookup, war, ATTACKERS, side)
            defenders = side_members(self.lookup, war, DEFENDERS, side)
            if (first in attackers and second in defenders) or (first in defenders and second in attackers):
                return True
        return False


def _transfer(event: Event) -> Transfer | None:
    if event.event_type != REGION_NATION_CHANGED or event.attribute("transition") != "changed" or not event.entities:
        return None
    before, after = event.attribute("before"), event.attribute("after")
    if not (isinstance(before, EntityRef) and isinstance(after, EntityRef)):
        return None
    return Transfer(event, event.entities[0], before.entity_id, after.entity_id)


def _suffix(reason: str) -> str:
    return reason.partition("Reason_")[2]


def _territory_reason(reason: str) -> bool:
    return _suffix(reason) in TERRITORY_REASONS


def _independence_reason(reason: str) -> bool:
    return _suffix(reason) == INDEPENDENCE_REASON


def _amicable_release(reason: str) -> bool:
    return reason == AMICABLE_RELEASE


def _nation_released(reason: str) -> bool:
    return _suffix(reason) == NATION_RELEASED_REASON


def territorial_events(
    events: Iterable[Event], before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff
) -> list[Event]:
    """Every territorial inference of one interval (unsorted)."""
    context = Context(events, before, after, diff)
    gains: dict[EntityId, list[Transfer]] = defaultdict(list)
    losses: dict[EntityId, list[Transfer]] = defaultdict(list)
    for transfer in context.transfers:
        gains[transfer.gainer].append(transfer)
        losses[transfer.loser].append(transfer)

    inferred: list[Event] = []
    for nation, transfers in sorted(gains.items(), key=lambda item: item[0].sort_key):
        inferred.append(_territory(context, TERRITORY_GAINED, nation, transfers, lambda t: t.loser))
    for nation, transfers in sorted(losses.items(), key=lambda item: item[0].sort_key):
        inferred.append(_territory(context, TERRITORY_LOST, nation, transfers, lambda t: t.gainer))

    candidates: list[Event] = []
    for gainer, transfers in sorted(gains.items(), key=lambda item: item[0].sort_key):
        candidates.extend(_independence(context, gainer, transfers))
        candidates.extend(_unification(context, gainer, transfers))
        candidates.extend(_annexations(context, gainer, transfers))
    inferred.extend(_resolve_conflicts(candidates))
    return inferred


def _territory(
    context: Context,
    event_type: str,
    nation: EntityId,
    transfers: Sequence[Transfer],
    counterpart: Callable[[Transfer], EntityId],
) -> Event:
    regions = _regions(transfers)
    counterparts = _unique_refs(context, (counterpart(transfer) for transfer in transfers))
    causes, support = context.reasons(nation, _territory_reason)
    return _inferred(
        context,
        event_type,
        id_parts=(nation,),
        transfers=transfers,
        support=support,
        entities=(context.ref(nation), *counterparts, *regions),
        attributes=(
            ("regions", regions),
            ("region_count", len(regions)),
            ("counterparts", counterparts),
            ("territory_causes", causes),
        ),
        confidence=Confidence.HIGH if causes else Confidence.MEDIUM,
    )


def _independence(context: Context, gainer: EntityId, transfers: Sequence[Transfer]) -> list[Event]:
    parents = _unique_refs(context, (transfer.loser for transfer in transfers))
    executive = tuple(
        event
        for event in context.subject_events(EXECUTIVE_CHANGE_RECORDED, gainer)
        if event.attribute("cause") == INDEPENDENCE_REASON
    )
    causes, tracker = context.reasons(gainer, _independence_reason)
    amicable_keys, amicable = context.reasons(gainer, _amicable_release)
    released_keys: tuple[str, ...] = ()
    released = Support()
    for parent in parents:
        parent_causes, parent_support = context.reasons(parent.entity_id, _independence_reason)
        causes += parent_causes
        tracker += parent_support
        if context.gainers_of[parent.entity_id] != {gainer}:
            continue  # the parent's tracker cannot say which of its region recipients it released
        parent_released, parent_released_support = context.reasons(parent.entity_id, _nation_released)
        released_keys += parent_released
        released += parent_released_support
    breakaway = context.subject_events(BREAKAWAY_PARENT_CHANGED, gainer)
    signals = tuple(
        name
        for name, present in (
            ("executive_cause", executive),
            ("tracker_cause", tracker),
            ("breakaway_parent", breakaway),
            ("amicable_release", amicable),
            ("nation_released", released),
        )
        if present
    )
    if not signals:
        return []
    attributes: list[tuple[str, Observed]] = [
        ("parents", parents),
        ("signals", signals),
        ("independence_causes", tuple(sorted(set(causes)))),
        ("released", bool(amicable or released)),
    ]
    if amicable or released:
        attributes += [
            ("release_causes", tuple(sorted(set(amicable_keys + released_keys)))),
            *_releaser(context, gainer, transfers),
        ]
    return [
        _inferred(
            context,
            INDEPENDENCE,
            id_parts=(gainer,),
            transfers=transfers,
            support=Support(events=executive + breakaway) + tracker + amicable + released,
            entities=(context.ref(gainer), *parents),
            attributes=attributes,
            confidence=Confidence.HIGH if len(signals) > 1 else Confidence.MEDIUM,
        )
    ]


def _releaser(context: Context, gainer: EntityId, transfers: Sequence[Transfer]) -> list[tuple[str, Observed]]:
    """The nation that released ``gainer`` and the faction holding its executive at the start of the interval.

    The releasing nation is the earlier holder of the new nation's capital when the capital is among the regions it
    gained (that region event is already cited), else the only nation it gained from; ``null`` when neither says.
    The faction is context read from the earlier snapshot, never a claim that the faction decided the release.
    """
    capital = context.lookup.ref_field(gainer, "capital", Side.AFTER)
    releaser: EntityId | None = None
    basis: str | None = None
    for transfer in transfers:
        if capital is not None and transfer.region.entity_id == capital.entity_id:
            releaser, basis = transfer.loser, "capital"
    losers = list(dict.fromkeys(transfer.loser for transfer in transfers))
    if releaser is None and len(losers) == 1:
        releaser, basis = losers[0], "only_parent"
    return [
        ("releasing_nation", context.ref(releaser) if releaser is not None else None),
        ("releasing_basis", basis),
        ("releasing_executive_faction", context.executive_faction(releaser) if releaser is not None else None),
    ]


def _unification(context: Context, gainer: EntityId, transfers: Sequence[Transfer]) -> list[Event]:
    whole: list[EntityId] = []
    support = Support()
    for loser in dict.fromkeys(transfer.loser for transfer in transfers):
        emptied = context.region_less_after(loser)
        if emptied is not None:
            whole.append(loser)
            support += emptied
    if len(whole) < MIN_UNIFIED:
        return []
    unified = _unique_refs(context, whole)
    return [
        _inferred(
            context,
            UNIFICATION,
            id_parts=(gainer,),
            transfers=[transfer for transfer in transfers if transfer.loser in whole],
            support=support,
            entities=(context.ref(gainer), *unified),
            attributes=(("unified", unified),),
            confidence=Confidence.MEDIUM,
        )
    ]


def _annexations(context: Context, gainer: EntityId, transfers: Sequence[Transfer]) -> list[Event]:
    by_loser: dict[EntityId, list[Transfer]] = defaultdict(list)
    for transfer in transfers:
        by_loser[transfer.loser].append(transfer)
    events: list[Event] = []
    for loser, pair_transfers in sorted(by_loser.items(), key=lambda item: item[0].sort_key):
        flags = tuple(
            change
            for transfer in pair_transfers
            for name in ANNEXATION_FIELDS
            if (change := context.index.field(transfer.region.entity_id, name)) is not None
        )
        wars = context.war_support(gainer, loser)
        if not flags and not wars:
            continue
        regions = _regions(pair_transfers)
        signals = tuple(name for name, present in (("annexation_flags", flags), ("war", wars.events)) if present)
        events.append(
            _inferred(
                context,
                ANNEXATION,
                id_parts=(gainer, loser),
                transfers=pair_transfers,
                support=Support(changes=flags) + wars,
                entities=(context.ref(gainer), context.ref(loser), *regions),
                attributes=(("regions", regions), ("region_count", len(regions)), ("signals", signals)),
                confidence=Confidence.MEDIUM,
            )
        )
    return events


def _resolve_conflicts(candidates: Sequence[Event]) -> list[Event]:
    """Lower and cross-reference the candidates of a gainer that more than one interpretation fits."""
    by_gainer: dict[EntityId, list[Event]] = defaultdict(list)
    for candidate in candidates:
        by_gainer[candidate.entities[0].entity_id].append(candidate)
    resolved: list[Event] = []
    for group in by_gainer.values():
        if len({candidate.event_type for candidate in group}) < 2:
            resolved.extend(group)
            continue
        for candidate in group:
            alternatives = tuple(sorted(other.id for other in group if other.event_type != candidate.event_type))
            resolved.append(
                replace(
                    candidate,
                    confidence=_LOWER[candidate.confidence],
                    attributes=(*candidate.attributes, ("ambiguous", True), ("alternatives", alternatives)),
                )
            )
    return resolved


def _inferred(
    context: Context,
    event_type: str,
    *,
    id_parts: Sequence[object],
    transfers: Sequence[Transfer],
    support: Support,
    entities: Iterable[EntityRef],
    attributes: Iterable[tuple[str, Observed]],
    confidence: Confidence,
) -> Event:
    """An inferred event citing every source of its region events (roles kept) and of its support (corroborating)."""
    region_events = tuple(transfer.event for transfer in transfers)
    return context.build.event(
        event_type,
        id_parts=id_parts,
        sources=_sources(region_events, support),
        entities=entities,
        attributes=attributes,
        confidence=confidence,
        status=EventStatus.INFERRED,
        constituents=[event.id for event in region_events + support.events],
    )


def _sources(region_events: Sequence[Event], support: Support) -> list[EventSource]:
    """The union of the cited sources, each change and member once; a primary citation wins over a corroborating one."""
    cited: dict[tuple[StateChange, FieldValue | None, SourceLocation | None], EventSource] = {}

    def add(source: EventSource) -> None:
        key = (source.change, source.member, source.entry)
        existing = cited.get(key)
        if existing is None or (existing.role is not SourceRole.PRIMARY and source.role is SourceRole.PRIMARY):
            cited[key] = source

    for event in region_events:
        for source in event.sources:
            add(source)
    for event in support.events:
        for source in event.sources:
            add(replace(source, role=SourceRole.CORROBORATING))
    for change in support.changes:
        add(EventSource(change, SourceRole.CORROBORATING))
    return list(cited.values())


def _regions(transfers: Iterable[Transfer]) -> tuple[EntityRef, ...]:
    regions = {transfer.region.entity_id: transfer.region for transfer in transfers}
    return tuple(regions[key] for key in sorted(regions, key=lambda entity_id: entity_id.sort_key))


def _unique_refs(context: Context, ids: Iterable[EntityId]) -> tuple[EntityRef, ...]:
    unique = sorted(set(ids), key=lambda entity_id: entity_id.sort_key)
    return tuple(context.ref(entity_id) for entity_id in unique)
