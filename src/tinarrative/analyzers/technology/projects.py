"""Faction projects the save lists as finished.

A faction's ``finishedProjectNames`` is a list of project template names. A name that enters it is a completion,
one event per faction and name with the name as its identity (projects are templates, not save entities, as
technologies are). A repeatable project is listed once per completion, so a name added more than once in an interval
is still one event, with ``completions`` giving the count. A name that leaves the list is not a completion; it is
reported literally as a list change (with ``count`` when repeated), as is a list that changed shape.
``currentProjectProgress`` stays in the diff.
"""

from __future__ import annotations

from collections import Counter

from ...model.changes import ChangeKind, MembershipDetail, StateChange, StateDiff
from ...model.entities import EntityDomain
from ...model.events import Event
from ...model.snapshot import SaveSnapshot
from ...model.values import FieldValue, Observed
from ..common import (
    ChangeIndex,
    EventBuilder,
    Lookup,
    Transition,
    classify,
    confidence_for,
    primary,
    transition_attributes,
)

PROJECT_COMPLETED = "faction.project_completed"
FINISHED_LIST_CHANGED = "faction.finished_project_names_changed"
FINISHED_LIST = "finishedProjectNames"


class ProjectAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = ChangeIndex(diff)
        lookup = Lookup(before, after)
        build = EventBuilder(before, after)
        events: list[Event] = []
        for change in index.fields(EntityDomain.FACTION, FINISHED_LIST):
            events.extend(_finished(change, lookup, build))
        return events


def _finished(change: StateChange, lookup: Lookup, build: EventBuilder) -> list[Event]:
    if change.entity_id is None:
        return []
    faction_id = change.entity_id
    faction = lookup.ref(faction_id)
    if change.kind is not ChangeKind.MEMBERSHIP or not isinstance(change.detail, MembershipDetail):
        transition = classify(change.before, change.after)
        if transition is None:
            return []
        return [
            build.event(
                FINISHED_LIST_CHANGED,
                id_parts=(faction_id, transition.value),
                sources=(primary(change),),
                entities=(faction,),
                attributes=transition_attributes(change, transition),
                confidence=confidence_for(transition),
            )
        ]
    events: list[Event] = []
    for name, count in _names(change.detail.added):
        events.append(
            build.event(
                PROJECT_COMPLETED,
                id_parts=(faction_id, name),
                sources=(primary(change, name),),
                entities=(faction,),
                attributes=(("project", name), *_count("completions", count)),
            )
        )
    for name, count in _names(change.detail.removed):
        events.append(
            build.event(
                FINISHED_LIST_CHANGED,
                id_parts=(faction_id, name, Transition.REMOVED.value),
                sources=(primary(change, name),),
                entities=(faction,),
                attributes=(("member", name), ("transition", Transition.REMOVED.value), *_count("count", count)),
            )
        )
    return events


def _names(members: tuple[FieldValue, ...]) -> list[tuple[str, int]]:
    """The distinct string members in first-seen order, with how often each occurs."""
    return list(Counter(name for name in members if isinstance(name, str)).items())


def _count(attribute: str, count: int) -> tuple[tuple[str, Observed], ...]:
    return ((attribute, count),) if count > 1 else ()
