"""Machinery shared by the analyzers: change lookup, transition classification and event construction.

An analyzer reads the :class:`StateDiff` (never re-deriving a fact from the snapshots) and emits events
whose sources are the literal changes. The snapshots are consulted only for context: the reference of an
entity named by a change, the owner of a councilor, the nation of a control point.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from ..log import fields as log_fields
from ..log import get_logger
from ..model.changes import ChangeKind, MembershipDetail, StateChange, StateDiff
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import Confidence, DateBasis, Event, EventSource, EventStatus, SourceRole
from ..model.records import RecordSet
from ..model.snapshot import STATE_COLLECTIONS, EntityState, SaveSnapshot
from ..model.values import FieldValue, Observed, Unknown, UnknownReason
from .base import Analyzer

logger = get_logger(__name__)


class Side(StrEnum):
    BEFORE = "before"
    AFTER = "after"


class Transition(StrEnum):
    """How a value differs between the two sides, in literal terms."""

    SET = "set"
    """``null`` before, a known value after."""
    CLEARED = "cleared"
    """A known value before, ``null`` after."""
    CHANGED = "changed"
    """Known, different values on both sides."""
    UNRESOLVED = "unresolved"
    """At least one side is a reference (or list) the normalizer could not resolve; the new value is unknown."""
    ADDED = "added"
    """A member present in the later list only."""
    REMOVED = "removed"
    """A member present in the earlier list only."""


def is_unresolved(value: Observed) -> bool:
    return isinstance(value, Unknown) and value.reason is UnknownReason.UNRESOLVED_REFERENCE


def classify(before: Observed, after: Observed) -> Transition | None:
    """The transition between two observed values, or ``None`` when a side is missing or unparseable.

    A missing side is a schema difference between the two saves, not a game transition, so nothing is
    emitted for it. An unresolved reference is a transition whose target is unknown.
    """
    if is_unresolved(before) or is_unresolved(after):
        return Transition.UNRESOLVED
    if isinstance(before, Unknown) or isinstance(after, Unknown):
        return None
    if before is None:
        return Transition.SET
    if after is None:
        return Transition.CLEARED
    return Transition.CHANGED


def confidence_for(transition: Transition, *values: Observed) -> Confidence:
    """High when every cited side is known; low when a side is an unresolved reference."""
    if transition is Transition.UNRESOLVED or any(is_unresolved(value) for value in values):
        return Confidence.LOW
    return Confidence.HIGH


def event_id(event_type: str, *parts: object) -> str:
    """Deterministic ID: the type and the subject parts joined by ``/``."""
    return "/".join([event_type, *(str(part) for part in parts)])


def same_entity(value: Observed, entity_id: EntityId) -> bool:
    return isinstance(value, EntityRef) and value.entity_id == entity_id


class ChangeIndex:
    """The changes of one diff, addressable by entity and field or by domain and field."""

    def __init__(self, diff: StateDiff) -> None:
        self._by_entity_field: dict[tuple[EntityId, str], StateChange] = {}
        self._by_domain_field: dict[tuple[str, str], list[StateChange]] = {}
        self._presence: dict[str, list[StateChange]] = {}
        for change in diff.changes:
            if change.field is None:
                self._presence.setdefault(change.domain, []).append(change)
                continue
            if change.entity_id is not None:
                self._by_entity_field[(change.entity_id, change.field)] = change
            self._by_domain_field.setdefault((change.domain, change.field), []).append(change)

    def field(self, entity_id: EntityId, field_name: str) -> StateChange | None:
        return self._by_entity_field.get((entity_id, field_name))

    def fields(self, domain: EntityDomain, field_name: str) -> tuple[StateChange, ...]:
        return tuple(self._by_domain_field.get((domain.value, field_name), ()))

    def presence(self, domain: EntityDomain) -> tuple[StateChange, ...]:
        return tuple(self._presence.get(domain.value, ()))

    def singleton(self, domain: str, field_name: str) -> StateChange | None:
        """The one change of a pseudo-domain field (``campaign``, ``research``: no entity), if any."""
        for change in self._by_domain_field.get((domain, field_name), ()):
            if change.entity_id is None:
                return change
        return None


class Lookup:
    """Context from the two snapshots: entity states, their references and record sets, by side."""

    def __init__(self, before: SaveSnapshot, after: SaveSnapshot) -> None:
        self._states = {Side.BEFORE: _index_states(before), Side.AFTER: _index_states(after)}
        self._records = {Side.BEFORE: _index_records(before), Side.AFTER: _index_records(after)}

    def state(self, entity_id: EntityId, side: Side) -> EntityState | None:
        return self._states[side].get(entity_id)

    def ref(self, entity_id: EntityId) -> EntityRef | None:
        """The entity's own reference (with its display name), from the later snapshot if it is there."""
        for side in (Side.AFTER, Side.BEFORE):
            state = self.state(entity_id, side)
            if state is not None:
                return state.ref
        return None

    def resolve(self, value: Observed) -> EntityRef | None:
        """The entity's own reference for a reference value, or the value itself when the entity is not normalized."""
        if not isinstance(value, EntityRef):
            return None
        return self.ref(value.entity_id) or value

    def ref_field(self, entity_id: EntityId, field_name: str, side: Side) -> EntityRef | None:
        state = self.state(entity_id, side)
        return self.resolve(state.get(field_name)) if state is not None else None

    def context_ref(self, entity_id: EntityId, field_name: str) -> EntityRef | None:
        """A reference field read from the later snapshot, else the earlier one (context only, never a fact)."""
        return self.ref_field(entity_id, field_name, Side.AFTER) or self.ref_field(entity_id, field_name, Side.BEFORE)

    def record_set(self, owner: EntityId, field_name: str, side: Side) -> RecordSet | None:
        return self._records[side].get((owner, field_name))


def _index_states(snapshot: SaveSnapshot) -> dict[EntityId, EntityState]:
    index: dict[EntityId, EntityState] = {}
    for name in STATE_COLLECTIONS:
        states: tuple[EntityState, ...] = getattr(snapshot, name)
        for state in states:
            index[state.ref.entity_id] = state
    return index


def _index_records(snapshot: SaveSnapshot) -> dict[tuple[EntityId, str], RecordSet]:
    return {(record.owner.entity_id, record.field): record for record in snapshot.records}


@dataclass
class _Members:
    change: StateChange
    added: list[FieldValue] = field(default_factory=list)
    removed: list[FieldValue] = field(default_factory=list)


class MembershipLedger:
    """The members of the handled reference lists, and which of them an event has already cited.

    An analyzer claims the members its events explain (as corroboration or as the subject); whatever is
    left over is reported by :meth:`leftovers`, so no literal change on a handled list is dropped. A list
    that is unresolved on one side arrives as one ``unknown`` change and is a single unresolved leftover.
    """

    def __init__(self, index: ChangeIndex, handled: Iterable[tuple[EntityDomain, str]]) -> None:
        self._members: dict[tuple[EntityId, str], _Members] = {}
        self._unresolved: list[StateChange] = []
        for domain, field_name in handled:
            for change in index.fields(domain, field_name):
                if change.entity_id is None:
                    continue
                if change.kind is ChangeKind.MEMBERSHIP and isinstance(change.detail, MembershipDetail):
                    self._members[(change.entity_id, field_name)] = _Members(
                        change, list(change.detail.added), list(change.detail.removed)
                    )
                elif change.kind is ChangeKind.UNKNOWN and classify(change.before, change.after) is not None:
                    self._unresolved.append(change)

    def claim(
        self, owner: EntityId, field_name: str, member: EntityId, transition: Transition, role: SourceRole
    ) -> EventSource | None:
        """Cite ``member`` (added or removed) of ``owner``'s list once; ``None`` when the list does not say so."""
        members = self._members.get((owner, field_name))
        if members is None:
            return None
        pool = members.added if transition is Transition.ADDED else members.removed
        for position, value in enumerate(pool):
            if same_entity(value, member):
                del pool[position]
                return EventSource(members.change, role, value)
        return None

    def pending(self, field_name: str) -> list[tuple[EntityId, EntityRef, Transition]]:
        """The unclaimed reference members of every ``field_name`` list, in change order (a snapshot)."""
        result: list[tuple[EntityId, EntityRef, Transition]] = []
        for (owner, name), members in sorted(self._members.items(), key=lambda item: item[1].change.sort_key):
            if name != field_name:
                continue
            for pool, transition in ((members.added, Transition.ADDED), (members.removed, Transition.REMOVED)):
                result.extend((owner, value, transition) for value in pool if isinstance(value, EntityRef))
        return result

    def leftovers(self) -> Iterator[tuple[StateChange, FieldValue | None, Transition]]:
        """Unclaimed members in change order, then the lists unresolved on one side."""
        for members in sorted(self._members.values(), key=lambda item: item.change.sort_key):
            for value in members.added:
                yield members.change, value, Transition.ADDED
            for value in members.removed:
                yield members.change, value, Transition.REMOVED
        for change in sorted(self._unresolved, key=lambda item: item.sort_key):
            yield change, None, Transition.UNRESOLVED


class EventBuilder:
    """Builds events dated by the interval of the diff, or by a record entry when one is given.

    Analyzers build objective events; the reconstruction stage passes ``status`` and ``constituents``.
    """

    def __init__(self, before: SaveSnapshot, after: SaveSnapshot) -> None:
        self.not_before: Observed = before.date
        self.observed: Observed = after.date

    def event(
        self,
        event_type: str,
        *,
        id_parts: Sequence[object],
        sources: Iterable[EventSource],
        entities: Iterable[EntityRef | None],
        attributes: Iterable[tuple[str, Observed]] = (),
        confidence: Confidence = Confidence.HIGH,
        recorded_on: Observed = None,
        status: EventStatus = EventStatus.OBJECTIVE,
        constituents: Iterable[str] = (),
    ) -> Event:
        """An event, objective by default; ``recorded_on`` (an ISO date string from a record entry) dates it by it."""
        date: Observed = self.observed
        basis = DateBasis.INTERVAL
        if isinstance(recorded_on, str):
            date, basis = recorded_on, DateBasis.RECORD
        return Event(
            id=event_id(event_type, *id_parts),
            event_type=event_type,
            status=status,
            confidence=confidence,
            date=date,
            date_basis=basis,
            not_before=self.not_before,
            sources=tuple(sources),
            entities=tuple(ref for ref in entities if ref is not None),
            attributes=tuple(attributes),
            constituents=tuple(constituents),
        )


def primary(change: StateChange, member: FieldValue | None = None) -> EventSource:
    return EventSource(change, SourceRole.PRIMARY, member)


def run_analyzers(
    analyzers: Sequence[Analyzer], before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff
) -> tuple[Event, ...]:
    """Every event of every analyzer, sorted by date, type and ID; a duplicate ID is a programming error."""
    events: list[Event] = []
    for analyzer in analyzers:
        produced = analyzer.analyze(before, after, diff)
        events.extend(produced)
        if logger.isEnabledFor(logging.DEBUG):
            counts = Counter(event.confidence.value for event in produced)
            logger.debug(
                "analyzer done %s",
                log_fields(
                    analyzer=type(analyzer).__name__,
                    events=len(produced),
                    **{level.value: counts.get(level.value, 0) for level in Confidence},
                ),
            )
    ids = Counter(event.id for event in events)
    duplicates = sorted(event_id for event_id, count in ids.items() if count > 1)
    if duplicates:
        raise ValueError(f"analyzers produced duplicate event IDs: {duplicates[:3]}")
    return tuple(sorted(events, key=lambda event: event.sort_key))


def transition_attributes(change: StateChange, transition: Transition) -> tuple[tuple[str, Observed], ...]:
    return (("transition", transition.value), ("before", change.before), ("after", change.after))


def value_transition_event(
    event_type: str,
    change: StateChange,
    lookup: Lookup,
    build: EventBuilder,
    *,
    context: Iterable[EntityRef | None] = (),
    recorded_on: Observed = None,
) -> Event | None:
    """One field of an entity changed: the literal transition, the subject, ``context`` and both values' entities.

    ``None`` when a side is missing or unparseable (a schema gap, not a transition) or the change has no entity.
    ``recorded_on`` dates the event by a record (see ``EventBuilder.event``).
    """
    transition = classify(change.before, change.after)
    if transition is None or change.entity_id is None:
        return None
    subject = change.entity_id
    return build.event(
        event_type,
        id_parts=(subject,),
        sources=(primary(change),),
        entities=(lookup.ref(subject), *context, lookup.resolve(change.before), lookup.resolve(change.after)),
        attributes=transition_attributes(change, transition),
        confidence=confidence_for(transition),
        recorded_on=recorded_on,
    )


def mirrored_sources(
    change: StateChange, ledger: MembershipLedger, list_field: str, subject: EntityId
) -> list[EventSource]:
    """The primary source plus, when present, the matching entries of the before and after owners' lists.

    For a reference field that points at an owner (a control point's ``faction``, a region's ``nation``), the
    earlier owner's list is expected to lose the subject and the later owner's list to gain it.
    """
    sources = [primary(change)]
    for value, membership in ((change.before, Transition.REMOVED), (change.after, Transition.ADDED)):
        if isinstance(value, EntityRef):
            cited = ledger.claim(value.entity_id, list_field, subject, membership, SourceRole.CORROBORATING)
            if cited is not None:
                sources.append(cited)
    return sources


def list_changed_event(
    event_type: str,
    change: StateChange,
    member: Observed,
    transition: Transition,
    lookup: Lookup,
    build: EventBuilder,
) -> Event:
    """A leftover member of a handled list, or a list unresolved on one side, as its own event."""
    owner_id = change.entity_id
    if owner_id is None:  # handled lists are entity fields
        raise ValueError("a membership change without an entity cannot be reported")
    member_ref = lookup.resolve(member)
    attributes: tuple[tuple[str, Observed], ...]
    id_parts: tuple[object, ...]
    if transition is Transition.UNRESOLVED:
        attributes = transition_attributes(change, transition)
        id_parts = (owner_id, transition.value)
    else:
        attributes = (("member", member), ("transition", transition.value))
        id_parts = (owner_id, member_ref.entity_id if member_ref is not None else member, transition.value)
    return build.event(
        event_type,
        id_parts=id_parts,
        sources=(primary(change, member if isinstance(member, EntityRef) else None),),
        entities=(lookup.ref(owner_id), member_ref),
        attributes=attributes,
        confidence=confidence_for(transition),
    )
