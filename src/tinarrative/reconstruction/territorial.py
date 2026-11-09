"""Territorial reconstruction rules: territory gained/lost, independence, unification, annexation.

The evidence each rule reads (tracker reasons, records, the game's unification conditions) is in
``docs/game-data-notes/higher-level-event-sources.md``. Territory events aggregate a nation's region transfers; the
interpretations of one gainer compete, and when more than one fits, every candidate is lowered one level, marked
``ambiguous`` and names the others in ``alternatives``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace

from ..analyzers.common import EventBuilder, Lookup, Side, event_id
from ..analyzers.politics.control_points import CONTROLLER_CHANGED
from ..analyzers.politics.control_points import DISAPPEARED as POINT_DISAPPEARED
from ..analyzers.politics.control_points import LOSS_RECORDED as POINT_LOSS_RECORDED
from ..analyzers.politics.nation_metrics import STATISTIC_SHIFTED, TRACKERS, cause_deltas
from ..analyzers.politics.nations import (
    BREAKAWAY_PARENT_CHANGED,
    DISAPPEARED,
    EXECUTIVE_CHANGE_RECORDED,
    EXECUTIVE_FIELD,
    REGION_NATION_CHANGED,
    RELATION_CHANGED,
)
from ..analyzers.politics.wars import ATTACKERS, DEFENDERS, side_members
from ..kinds.wars import FEDERATION_MEMBERS_CHANGED
from ..model.changes import StateDiff
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import Confidence, Event, EventStatus
from ..model.records import KeyedEntry
from ..model.snapshot import SaveSnapshot
from ..model.values import FrozenMap, Observed, Unknown
from .common import Support, control_points, executive_seat, inferred, lower

TERRITORY_GAINED = "nation.territory_gained"
TERRITORY_LOST = "nation.territory_lost"
INDEPENDENCE = "nation.independence"
UNIFICATION = "nation.unification"
ANNEXATION = "nation.annexation"
INTERPRETATIONS = (INDEPENDENCE, UNIFICATION, ANNEXATION)
"""Competing readings of one gainer's territory; two of them on one gainer make every candidate ambiguous."""
RULE_TYPES = (TERRITORY_GAINED, TERRITORY_LOST, *INTERPRETATIONS)
ALTERNATIVES = "alternatives"
ID_ATTRIBUTES = (ALTERNATIVES,)
"""Attributes whose value is a tuple of event IDs (rewritten with the IDs when a sequence qualifies them)."""

TERRITORY_REASONS = frozenset({"TerritoryChange", "Annexation", "RegionTransfer"})
"""Tracker reason suffixes that name a region transfer (notes, metric cause attribution)."""
INDEPENDENCE_REASON = "Independence"
"""Both a tracker reason suffix and a ``lastExecutiveChange.cause`` value."""
AMICABLE_RELEASE = "DemReason_AmicableRelease"
"""On the released nation of a release."""
NATION_RELEASED_REASON = "NationReleased"
"""Tracker reason suffix on the parent of a release: it marks a release decided by the parent, not a unification."""
ANNEXATION_FIELDS = ("isBeingAnnexed", "annexingArmy")
"""Region fields that track an annexation in progress; left in the diff by every analyzer."""
WAR_PREFIX = "war."
WAR_RELATION = "wars"
FEDERATION_BASIS = "federation"
BREAKAWAY_BASIS = "breakaway"
"""Why the game let the two nations unify: a shared federation, or the absorbed nation broke away from the gainer."""
UNIFICATION_SUPPORT_TYPES = frozenset(
    {
        FEDERATION_MEMBERS_CHANGED.event_type,
        BREAKAWAY_PARENT_CHANGED,
        CONTROLLER_CHANGED,
        POINT_DISAPPEARED,
        POINT_LOSS_RECORDED,
    }
)
"""Objective events about an absorbed nation that corroborate its unification."""

_TRACKER_STATISTICS = {tracker: statistic for statistic, tracker in TRACKERS.items()}


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
        self.index = diff.index
        self.lookup = Lookup(before, after)
        self.build = EventBuilder(before, after, self.lookup)
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
        """The faction controlling ``nation``'s executive seat in the earlier snapshot (``null`` when none does);
        ``Unknown`` when the nation or the point is not found."""
        seat = executive_seat(self.lookup, nation, Side.BEFORE)
        if seat is None:
            return Unknown()
        faction = seat.state.get("faction")
        return self.lookup.resolve(faction) or faction

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
    side = Side.AFTER if event_type == TERRITORY_GAINED else Side.BEFORE
    population = context.lookup.population((region.entity_id for region in regions), side)
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
            ("population", population),
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
    """The game's conditions, read from the earlier snapshot: one faction holds every control point of the absorbed
    nation and the gainer's executive seat, and the two share a federation or the absorbed nation broke away from the
    gainer. Every region of the absorbed nation went to the gainer.
    """
    faction = _executive_holder(context, gainer)
    if faction is None:
        return []
    whole: list[EntityId] = []
    bases: dict[EntityId, FrozenMap] = {}
    support = Support()
    for loser in dict.fromkeys(transfer.loser for transfer in transfers):
        emptied = context.region_less_after(loser)
        if emptied is None or context.gainers_of[loser] != {gainer} or not _holds_all(context, loser, faction):
            continue
        basis = _unification_basis(context, gainer, loser)
        if basis is None:
            continue
        whole.append(loser)
        bases[loser] = basis
        support += emptied + Support(events=_unification_support(context, loser))
    if not whole:
        return []
    unified = _unique_refs(context, whole)
    return [
        _inferred(
            context,
            UNIFICATION,
            id_parts=(gainer,),
            transfers=[transfer for transfer in transfers if transfer.loser in whole],
            support=support,
            entities=(context.ref(gainer), *unified, context.lookup.resolve(faction) or faction),
            attributes=(
                ("unified", unified),
                ("unifying_faction", context.lookup.resolve(faction) or faction),
                ("bases", tuple(bases[key] for key in sorted(bases, key=lambda entity_id: entity_id.sort_key))),
                ("executive_since", _executive_since(context, gainer, faction)),
            ),
            confidence=Confidence.HIGH,
        )
    ]


def _faction_of(state_faction: Observed) -> EntityRef | None:
    if isinstance(state_faction, EntityRef) and state_faction.entity_id.domain is EntityDomain.FACTION:
        return state_faction
    return None


def _executive_holder(context: Context, nation: EntityId) -> EntityRef | None:
    seat = executive_seat(context.lookup, nation, Side.BEFORE)
    return _faction_of(seat.state.get("faction")) if seat is not None else None


def _holds_all(context: Context, nation: EntityId, faction: EntityRef) -> bool:
    """``faction`` holds the nation's executive seat and every one of its control points in the earlier snapshot."""
    holder = _executive_holder(context, nation)
    points = control_points(context.lookup, nation, Side.BEFORE)
    if holder is None or holder.entity_id != faction.entity_id or not points:
        return False
    for point in points:
        state = context.lookup.state(point.entity_id, Side.BEFORE)
        held = _faction_of(state.get("faction")) if state is not None else None
        if held is None or held.entity_id != faction.entity_id:
            return False
    return True


def _unification_basis(context: Context, gainer: EntityId, loser: EntityId) -> FrozenMap | None:
    loser_state = context.lookup.state(loser, Side.BEFORE)
    gainer_state = context.lookup.state(gainer, Side.BEFORE)
    if loser_state is None or gainer_state is None:
        return None
    federation, shared = loser_state.get("federation"), gainer_state.get("federation")
    if isinstance(federation, EntityRef) and isinstance(shared, EntityRef) and federation.entity_id == shared.entity_id:
        resolved = context.lookup.resolve(federation) or federation
        return FrozenMap((("nation", context.ref(loser)), ("basis", FEDERATION_BASIS), ("federation", resolved)))
    parent = loser_state.get("breakawayParent")
    if isinstance(parent, EntityRef) and parent.entity_id == gainer:
        return FrozenMap((("nation", context.ref(loser)), ("basis", BREAKAWAY_BASIS), ("federation", None)))
    return None


def _unification_support(context: Context, loser: EntityId) -> tuple[Event, ...]:
    """The absorbed nation's federation exit, breakaway link change and control point changes of the interval."""
    found = []
    for event in context.events:
        if event.event_type not in UNIFICATION_SUPPORT_TYPES:
            continue
        if event.event_type == FEDERATION_MEMBERS_CHANGED.event_type:
            member = event.attribute("member")
            if (
                isinstance(member, EntityRef)
                and member.entity_id == loser
                and event.attribute("transition") == "removed"
            ):
                found.append(event)
        elif event.event_type == BREAKAWAY_PARENT_CHANGED:
            if event.entities and event.entities[0].entity_id == loser:
                found.append(event)
        elif any(ref.entity_id == loser for ref in event.entities[1:]):
            found.append(event)
    return tuple(found)


def _executive_since(context: Context, nation: EntityId, faction: EntityRef) -> Observed:
    """The date of the nation's last executive change when it names ``faction``; ``None`` otherwise."""
    record = context.lookup.record_set(nation, EXECUTIVE_FIELD, Side.BEFORE)
    if record is None or isinstance(record.entries, Unknown):
        return None
    values = {entry.key: entry.value for entry in record.entries if isinstance(entry, KeyedEntry)}
    holder = values.get("newExecutive")
    if not isinstance(holder, EntityRef) or holder.entity_id != faction.entity_id:
        return None
    date = values.get("date")
    return date if isinstance(date, str) else None


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
                    confidence=lower(candidate.confidence),
                    attributes=(*candidate.attributes, ("ambiguous", True), (ALTERNATIVES, alternatives)),
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
    """An inferred event built on its region events, citing every source of them and of its support."""
    return inferred(
        context.build,
        event_type,
        id_parts=id_parts,
        primary=[transfer.event for transfer in transfers],
        support=support,
        entities=entities,
        attributes=attributes,
        confidence=confidence,
    )


def _regions(transfers: Iterable[Transfer]) -> tuple[EntityRef, ...]:
    regions = {transfer.region.entity_id: transfer.region for transfer in transfers}
    return tuple(regions[key] for key in sorted(regions, key=lambda entity_id: entity_id.sort_key))


def _unique_refs(context: Context, ids: Iterable[EntityId]) -> tuple[EntityRef, ...]:
    unique = sorted(set(ids), key=lambda entity_id: entity_id.sort_key)
    return tuple(context.ref(entity_id) for entity_id in unique)
