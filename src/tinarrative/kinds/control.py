"""Control points, councilors, organizations and inferred faction control of nations."""

from __future__ import annotations

from collections.abc import Callable

from ..model.entities import EntityDomain
from ..model.events import Event, Significance
from ..model.kinds import EventKind, EvidenceRole, Rule, Stake
from ..model.values import Unknown
from .text import (
    TRANSITION,
    attribute_label,
    attribute_text,
    list_changed,
    plain,
    presence,
    subject_label,
    transition_label,
)

BOOKKEEPING = EvidenceRole.BOOKKEEPING
EVIDENCE = EvidenceRole.EVIDENCE


def _controller_changed(event: Event) -> str:
    text = (
        f"{subject_label(event)} ({_entity_name(event, EntityDomain.NATION)}) {transition_label(event, 'controller')}"
    )
    recorded = event.attribute("loss_recorded_on")
    if not isinstance(recorded, Unknown):
        text += f"; loss recorded by {attribute_label(event, 'before')} on {attribute_text(event, 'loss_recorded_on')}"
    return text


def _entity_name(event: Event, domain: EntityDomain) -> str:
    ref = next((entity for entity in event.entities[1:] if entity.entity_id.domain is domain), None)
    return ref.label() if ref is not None else "null"


def _control_point_presence(event: Event) -> str:
    return (
        f"{subject_label(event)} ({_entity_name(event, EntityDomain.NATION)}, "
        f"controller {_entity_name(event, EntityDomain.FACTION)}) {presence(event)}"
    )


def _loss_recorded(event: Event) -> str:
    faction = _entity_name(event, EntityDomain.FACTION)
    text = f"{faction} records {subject_label(event)} as lost on {attribute_text(event, 'recorded_on')}"
    if not isinstance(event.attribute("previous_recorded_on"), Unknown):
        text += f" (previously {attribute_text(event, 'previous_recorded_on')})"
    return text


def _councilor_field(label: str) -> Callable[[Event], str]:
    def describe(event: Event) -> str:
        return f"{subject_label(event)} ({_entity_name(event, EntityDomain.FACTION)}) {transition_label(event, label)}"

    return describe


def _councilor_presence(event: Event) -> str:
    return f"{subject_label(event)} (faction {_entity_name(event, EntityDomain.FACTION)}) {presence(event)}"


def _organization_presence(event: Event) -> str:
    return f"{subject_label(event)} (home region {_entity_name(event, EntityDomain.REGION)}) {presence(event)}"


def _nation_control_changed(event: Event) -> str:
    return f"{subject_label(event)} {transition_label(event, attribute_text(event, 'scope') + ' control changed')}"


CONTROL_POINT_CONTROLLER_CHANGED = EventKind(
    "control_point.controller_changed",
    _controller_changed,
    Significance.MAJOR,
    BOOKKEEPING,
    required=TRANSITION,
    optional=frozenset({"loss_recorded_on"}),
    stake=Stake.CONTROL_POINT,
)
CONTROL_POINT_NATION_CHANGED = EventKind(
    "control_point.nation_changed", plain("nation"), Significance.MINOR, BOOKKEEPING, TRANSITION
)
CONTROL_POINT_APPEARED = EventKind(
    "control_point.appeared", _control_point_presence, Significance.MINOR, BOOKKEEPING, frozenset({"side"})
)
CONTROL_POINT_DISAPPEARED = EventKind(
    "control_point.disappeared", _control_point_presence, Significance.MINOR, BOOKKEEPING, frozenset({"side"})
)
CONTROL_POINT_LOSS_RECORDED = EventKind(
    "control_point.loss_recorded",
    _loss_recorded,
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset({"recorded_on"}),
    optional=frozenset({"previous_recorded_on"}),
)
FACTION_CONTROL_POINTS_CHANGED = EventKind(
    "faction.control_points_changed",
    list_changed,
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
)
NATION_CONTROL_POINTS_CHANGED = EventKind(
    "nation.control_points_changed",
    list_changed,
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
)

COUNCILOR_FACTION_CHANGED = EventKind(
    "councilor.faction_changed", plain("faction"), Significance.MAJOR, EVIDENCE, TRANSITION
)
COUNCILOR_STATUS_CHANGED = EventKind(
    "councilor.status_changed", _councilor_field("status"), Significance.MINOR, EVIDENCE, TRANSITION
)
COUNCILOR_LOCATION_CHANGED = EventKind(
    "councilor.location_changed", _councilor_field("location"), Significance.TRIVIAL, EVIDENCE, TRANSITION
)
COUNCILOR_DETAINING_FACTION_CHANGED = EventKind(
    "councilor.detaining_faction_changed",
    _councilor_field("detaining faction"),
    Significance.MAJOR,
    EVIDENCE,
    TRANSITION,
)
COUNCILOR_APPEARED = EventKind(
    "councilor.appeared",
    _councilor_presence,
    None,
    EVIDENCE,
    frozenset({"side"}),
    rule=Rule.COUNCILOR_PRESENCE,
)
COUNCILOR_DISAPPEARED = EventKind(
    "councilor.disappeared",
    _councilor_presence,
    None,
    EVIDENCE,
    frozenset({"side"}),
    rule=Rule.COUNCILOR_PRESENCE,
)
FACTION_COUNCILORS_CHANGED = EventKind(
    "faction.councilors_changed",
    list_changed,
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
)

ORGANIZATION_APPEARED = EventKind(
    "organization.appeared", _organization_presence, Significance.TRIVIAL, BOOKKEEPING, frozenset({"side"})
)
ORGANIZATION_DISAPPEARED = EventKind(
    "organization.disappeared", _organization_presence, Significance.TRIVIAL, BOOKKEEPING, frozenset({"side"})
)
ORGANIZATION_ASSIGNED_COUNCILOR_CHANGED = EventKind(
    "organization.assigned_councilor_changed",
    plain("assigned councilor"),
    Significance.MAJOR,
    BOOKKEEPING,
    TRANSITION,
    stake=Stake.ORGANIZATION,
)
ORGANIZATION_FACTION_ORBIT_CHANGED = EventKind(
    "organization.faction_orbit_changed", plain("faction orbit"), Significance.MINOR, BOOKKEEPING, TRANSITION
)
COUNCILOR_ORGS_CHANGED = EventKind(
    "councilor.orgs_changed",
    list_changed,
    Significance.TRIVIAL,
    EVIDENCE,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
)
FACTION_UNASSIGNED_ORGS_CHANGED = EventKind(
    "faction.unassigned_orgs_changed",
    list_changed,
    Significance.TRIVIAL,
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
)

NATION_CONTROL_CHANGED = EventKind(
    "faction.nation_control_changed",
    _nation_control_changed,
    Significance.MAJOR,
    BOOKKEEPING,
    required=frozenset(
        {
            "scope",
            "before",
            "after",
            "shares_before",
            "shares_after",
            "point_count_before",
            "point_count_after",
            "points_moved",
            "cause",
            "recorded_on",
            "new_executive",
            "seat",
            "population",
        }
    ),
    stake=Stake.NATION,
)

KINDS = (
    CONTROL_POINT_CONTROLLER_CHANGED,
    CONTROL_POINT_NATION_CHANGED,
    CONTROL_POINT_APPEARED,
    CONTROL_POINT_DISAPPEARED,
    CONTROL_POINT_LOSS_RECORDED,
    FACTION_CONTROL_POINTS_CHANGED,
    NATION_CONTROL_POINTS_CHANGED,
    COUNCILOR_FACTION_CHANGED,
    COUNCILOR_STATUS_CHANGED,
    COUNCILOR_LOCATION_CHANGED,
    COUNCILOR_DETAINING_FACTION_CHANGED,
    COUNCILOR_APPEARED,
    COUNCILOR_DISAPPEARED,
    FACTION_COUNCILORS_CHANGED,
    ORGANIZATION_APPEARED,
    ORGANIZATION_DISAPPEARED,
    ORGANIZATION_ASSIGNED_COUNCILOR_CHANGED,
    ORGANIZATION_FACTION_ORBIT_CHANGED,
    COUNCILOR_ORGS_CHANGED,
    FACTION_UNASSIGNED_ORGS_CHANGED,
    NATION_CONTROL_CHANGED,
)
