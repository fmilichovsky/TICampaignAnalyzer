"""Federations as the save shows them: presence, the ``members`` list and the literal names.

A nation's ``federation`` reference mirrors the ``members`` list of that federation (observed in every inspected
save), so a member change cites the matching ``nation.federation`` change as corroboration. A ``nation.federation``
change no member change or presence explains is reported on its own as ``nation.federation_changed``.

A change of ``displayName`` or ``federationName`` is one ``federation.renamed`` per federation citing each changed
field; ``before``/``after`` are the display names when those changed, else the federation names, and federation
names that differ from changed display names are carried as ``federation_name_before``/``federation_name_after``.
"""

from __future__ import annotations

from ...model.changes import ChangeKind, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId, EntityRef
from ...model.events import Event, EventSource, SourceRole
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed
from ..common import (
    ChangeIndex,
    EventBuilder,
    Lookup,
    MembershipLedger,
    Side,
    Transition,
    classify,
    confidence_for,
    list_changed_event,
    primary,
    same_entity,
    value_transition_event,
)

APPEARED = "federation.appeared"
DISAPPEARED = "federation.disappeared"
MEMBERS_CHANGED = "federation.members_changed"
FEDERATION_CHANGED = "nation.federation_changed"
RENAMED = "federation.renamed"
NAME_FIELDS = ("displayName", "federationName")
"""The name fields of a federation, in the order their values are preferred for ``before``/``after``."""

HANDLED_LISTS = ((EntityDomain.FEDERATION, "members"),)


class FederationAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = ChangeIndex(diff)
        lookup = Lookup(before, after)
        ledger = MembershipLedger(index, HANDLED_LISTS)
        build = EventBuilder(before, after)
        mirror = _NationFederations(index)
        events: list[Event] = []

        for change in index.presence(EntityDomain.FEDERATION):
            events.append(_presence(change, lookup, mirror, build))
        for federation_id, member, transition in ledger.pending("members"):
            own = ledger.claim(federation_id, "members", member.entity_id, transition, SourceRole.PRIMARY)
            assert own is not None  # pending members are claimable
            sources = [own]
            cited = mirror.claim(member.entity_id, federation_id, transition)
            if cited is not None:
                sources.append(cited)
            events.append(
                build.event(
                    MEMBERS_CHANGED,
                    id_parts=(federation_id, member.entity_id, transition.value),
                    sources=sources,
                    entities=(lookup.ref(federation_id), lookup.resolve(member)),
                    attributes=(("member", member), ("transition", transition.value)),
                    confidence=confidence_for(transition),
                )
            )
        for change, leftover, transition in ledger.leftovers():
            events.append(list_changed_event(MEMBERS_CHANGED, change, leftover, transition, lookup, build))
        for change in mirror.unclaimed():
            event = value_transition_event(FEDERATION_CHANGED, change, lookup, build)
            if event is not None:
                events.append(event)
        events.extend(_renames(index, lookup, build))
        return events


def _renames(index: ChangeIndex, lookup: Lookup, build: EventBuilder) -> list[Event]:
    """One event per federation whose display or federation name changed, citing every changed name field."""
    by_federation: dict[EntityId, list[StateChange]] = {}
    for field_name in NAME_FIELDS:
        for change in index.fields(EntityDomain.FEDERATION, field_name):
            if change.entity_id is not None and classify(change.before, change.after) is not None:
                by_federation.setdefault(change.entity_id, []).append(change)
    events: list[Event] = []
    for federation_id, changes in sorted(by_federation.items(), key=lambda item: item[0].sort_key):
        shown = changes[0]
        transition = classify(shown.before, shown.after)
        assert transition is not None
        attributes: list[tuple[str, Observed]] = [
            ("transition", transition.value),
            ("before", shown.before),
            ("after", shown.after),
        ]
        for change in changes[1:]:
            if (change.before, change.after) != (shown.before, shown.after):
                attributes += [("federation_name_before", change.before), ("federation_name_after", change.after)]
        events.append(
            build.event(
                RENAMED,
                id_parts=(federation_id,),
                sources=[primary(change) for change in changes],
                entities=(lookup.ref(federation_id),),
                attributes=attributes,
                confidence=confidence_for(transition),
            )
        )
    return events


class _NationFederations:
    """The ``nation.federation`` changes, each cited at most once as corroboration per side of the change."""

    def __init__(self, index: ChangeIndex) -> None:
        self._changes = {
            change.entity_id: change
            for change in index.fields(EntityDomain.NATION, "federation")
            if change.entity_id is not None
        }
        self._claimed: set[tuple[EntityId, Transition]] = set()

    def claim(self, nation_id: EntityId, federation_id: EntityId, transition: Transition) -> EventSource | None:
        """The nation's change when it leaves (``removed``) or enters (``added``) ``federation_id``."""
        change = self._changes.get(nation_id)
        if change is None or (nation_id, transition) in self._claimed:
            return None
        value = change.after if transition is Transition.ADDED else change.before
        if not same_entity(value, federation_id):
            return None
        self._claimed.add((nation_id, transition))
        return EventSource(change, SourceRole.CORROBORATING)

    def unclaimed(self) -> list[StateChange]:
        claimed = {nation_id for nation_id, _ in self._claimed}
        return [change for nation_id, change in self._changes.items() if nation_id not in claimed]


def _presence(change: StateChange, lookup: Lookup, mirror: _NationFederations, build: EventBuilder) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    federation_id = change.entity_id
    assert federation_id is not None
    side = Side.AFTER if appeared else Side.BEFORE
    state = lookup.state(federation_id, side)
    members = state.get("members") if state is not None else ()
    listed = members if isinstance(members, tuple) else ()
    nations = [value.entity_id for value in listed if isinstance(value, EntityRef)]
    sources = [primary(change)]
    for nation_id in nations:
        cited = mirror.claim(nation_id, federation_id, Transition.ADDED if appeared else Transition.REMOVED)
        if cited is not None:
            sources.append(cited)
    return build.event(
        APPEARED if appeared else DISAPPEARED,
        id_parts=(federation_id,),
        sources=sources,
        entities=(lookup.ref(federation_id), *(lookup.ref(nation_id) for nation_id in nations)),
        attributes=(("side", side.value),),
    )
