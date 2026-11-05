"""Faction project completions from ``finishedProjectNames`` (template names, not save entities).

A repeatable project is listed once per completion, so a name added several times in an interval is one event
with a ``completions`` count. A name leaving the list is not a completion and is reported as a literal list change.
"""

from __future__ import annotations

from collections import Counter

from ...model.changes import ChangeKind, MembershipDetail, StateChange, StateDiff
from ...model.entities import EntityDomain
from ...model.events import Event
from ...model.snapshot import SaveSnapshot
from ...model.values import FieldValue, Observed
from ..common import (
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
        index = diff.index
        lookup = Lookup(before, after)
        build = EventBuilder(before, after, lookup)
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
