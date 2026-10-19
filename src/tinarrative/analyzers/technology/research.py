"""Technology completion and the presence of name-keyed technology states.

A technology's identity is its template name (``name-key`` confidence; see ``entity-identity.md``). A name that
enters ``finishedTechsNames`` is a completion: the technology's own ``finished`` value (or its appearance already
finished) is the primary source and the research singleton's membership change corroborates it. A progress-only
technology that appears or vanishes is reported as present in / absent from one snapshot. ``progress`` values
(accumulated research, contributions) stay in the diff; faction project names are ``ProjectAnalyzer``'s.
"""

from __future__ import annotations

from ...model.changes import ChangeKind, MembershipDetail, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from ...model.events import Event, EventSource, SourceRole
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed
from ..common import (
    ChangeIndex,
    EventBuilder,
    Lookup,
    Side,
    Transition,
    classify,
    confidence_for,
    primary,
    transition_attributes,
)

COMPLETED = "technology.completed"
FINISHED_CHANGED = "technology.finished_changed"
APPEARED = "technology.appeared"
DISAPPEARED = "technology.disappeared"
FINISHED_LIST_CHANGED = "research.finished_techs_changed"

RESEARCH_DOMAIN = "research"
FINISHED_LIST = "finished_techs_names"


class _Names:
    """The names added to and removed from ``finishedTechsNames``, each citable once."""

    def __init__(self, change: StateChange | None) -> None:
        self.change = change
        self.added: list[str] = []
        self.removed: list[str] = []
        if change is not None and change.kind is ChangeKind.MEMBERSHIP and isinstance(change.detail, MembershipDetail):
            self.added = [name for name in change.detail.added if isinstance(name, str)]
            self.removed = [name for name in change.detail.removed if isinstance(name, str)]

    def claim(self, name: str, transition: Transition, role: SourceRole) -> EventSource | None:
        pool = self.added if transition is Transition.ADDED else self.removed
        if self.change is None or name not in pool:
            return None
        pool.remove(name)
        return EventSource(self.change, role, name)


class TechnologyAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = ChangeIndex(diff)
        lookup = Lookup(before, after)
        build = EventBuilder(before, after)
        names = _Names(index.singleton(RESEARCH_DOMAIN, FINISHED_LIST))
        events: list[Event] = []

        for change in index.fields(EntityDomain.TECHNOLOGY, "finished"):
            event = _finished(change, lookup, names, build)
            if event is not None:
                events.append(event)
        for change in index.presence(EntityDomain.TECHNOLOGY):
            events.append(_presence(change, lookup, names, build))
        for pool, transition in ((names.added, Transition.ADDED), (names.removed, Transition.REMOVED)):
            for name in list(pool):
                source = names.claim(name, transition, SourceRole.PRIMARY)
                assert source is not None
                events.append(
                    build.event(
                        FINISHED_LIST_CHANGED,
                        id_parts=(name, transition.value),
                        sources=(source,),
                        entities=(_tech_ref(name, lookup),),
                        attributes=(("member", name), ("transition", transition.value)),
                    )
                )
        return events


def _tech_ref(name: str, lookup: Lookup) -> EntityRef:
    entity_id = EntityId(EntityDomain.TECHNOLOGY, name)
    return lookup.ref(entity_id) or EntityRef(entity_id, IdentityConfidence.NAME_KEY, name=name)


def _finished(change: StateChange, lookup: Lookup, names: _Names, build: EventBuilder) -> Event | None:
    transition = classify(change.before, change.after)
    if transition is None or change.entity_id is None:
        return None
    tech_id = change.entity_id
    sources = [primary(change)]
    membership = Transition.ADDED if change.after is True else Transition.REMOVED if change.before is True else None
    if membership is not None:
        cited = names.claim(tech_id.key, membership, SourceRole.CORROBORATING)
        if cited is not None:
            sources.append(cited)
    completed = change.before is False and change.after is True
    return build.event(
        COMPLETED if completed else FINISHED_CHANGED,
        id_parts=(tech_id,),
        sources=sources,
        entities=(lookup.ref(tech_id),),
        attributes=transition_attributes(change, transition),
        confidence=confidence_for(transition),
    )


def _presence(change: StateChange, lookup: Lookup, names: _Names, build: EventBuilder) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    side = Side.AFTER if appeared else Side.BEFORE
    tech_id = change.entity_id
    assert tech_id is not None
    state = lookup.state(tech_id, side)
    finished: Observed = state.get("finished") if state is not None else None
    sources = [primary(change)]
    if finished is True:
        membership = Transition.ADDED if appeared else Transition.REMOVED
        cited = names.claim(tech_id.key, membership, SourceRole.CORROBORATING)
        if cited is not None:
            sources.append(cited)
    completed = appeared and finished is True
    attributes: tuple[tuple[str, Observed], ...] = (("side", side.value),)
    if not completed:
        attributes += (("finished", finished),)
    return build.event(
        COMPLETED if completed else APPEARED if appeared else DISAPPEARED,
        id_parts=(tech_id,),
        sources=sources,
        entities=(lookup.ref(tech_id),),
        attributes=attributes,
    )
