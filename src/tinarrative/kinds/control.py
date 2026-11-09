"""Who holds what: control points, councilors, organizations and the inferred control of a nation.

A councilor's moves are narrator evidence (who acted); every other type is stated by the narrative event citing it.
"""

from __future__ import annotations

from ..model.entities import EntityDomain
from ..model.events import Event, Significance
from ..model.kinds import EventKind, EvidenceRole, Rule, Stake, Template
from ..model.values import Unknown
from .text import (
    TRANSITION,
    attribute_label,
    attribute_text,
    entity,
    list_changed,
    name,
    plain,
    presence,
    presence_with,
    subject_label,
    transition_label,
)

SIDE = frozenset({"side"})
LIST = frozenset({"transition"})
LIST_DETAIL = frozenset({"member", "before", "after"})
"""A handled list's event names the member or, when the list is unresolved on one side, the literal transition."""


def _controller_changed(event: Event) -> str:
    nation = name(entity(event, EntityDomain.NATION))
    text = f"{subject_label(event)} ({nation}) {transition_label(event, 'controller')}"
    if not isinstance(event.attribute("loss_recorded_on"), Unknown):
        text += f"; loss recorded by {attribute_label(event, 'before')} on {attribute_text(event, 'loss_recorded_on')}"
    return text


def _control_point_presence(event: Event) -> str:
    nation = name(entity(event, EntityDomain.NATION))
    faction = name(entity(event, EntityDomain.FACTION))
    return f"{subject_label(event)} ({nation}, controller {faction}) {presence(event)}"


def _loss_recorded(event: Event) -> str:
    faction = name(entity(event, EntityDomain.FACTION))
    text = f"{faction} records {subject_label(event)} as lost on {attribute_text(event, 'recorded_on')}"
    if not isinstance(event.attribute("previous_recorded_on"), Unknown):
        text += f" (previously {attribute_text(event, 'previous_recorded_on')})"
    return text


def _councilor_field(label: str) -> Template:
    return lambda event: (
        f"{subject_label(event)} ({name(entity(event, EntityDomain.FACTION))}) {transition_label(event, label)}"
    )


def _councilor_presence(event: Event) -> str:
    return f"{subject_label(event)} (faction {name(entity(event, EntityDomain.FACTION))}) {presence(event)}"


def _nation_control_changed(event: Event) -> str:
    return f"{subject_label(event)} {transition_label(event, attribute_text(event, 'scope') + ' control changed')}"


CONTROLLER_CHANGED = EventKind(
    "control_point.controller_changed",
    _controller_changed,
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
    optional=frozenset({"loss_recorded_on"}),
    stake=Stake.CONTROL_POINT,
)
POINT_NATION_CHANGED = EventKind(
    "control_point.nation_changed", plain("nation"), Significance.MINOR, EvidenceRole.BOOKKEEPING, required=TRANSITION
)
POINT_APPEARED = EventKind(
    "control_point.appeared", _control_point_presence, Significance.MINOR, EvidenceRole.BOOKKEEPING, required=SIDE
)
POINT_DISAPPEARED = EventKind(
    "control_point.disappeared", _control_point_presence, Significance.MINOR, EvidenceRole.BOOKKEEPING, required=SIDE
)
LOSS_RECORDED = EventKind(
    "control_point.loss_recorded",
    _loss_recorded,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"recorded_on"}),
    optional=frozenset({"previous_recorded_on"}),
)
FACTION_POINTS_CHANGED = EventKind(
    "faction.control_points_changed",
    list_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=LIST,
    optional=LIST_DETAIL,
)
NATION_POINTS_CHANGED = EventKind(
    "nation.control_points_changed",
    list_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=LIST,
    optional=LIST_DETAIL,
)

COUNCILOR_FACTION_CHANGED = EventKind(
    "councilor.faction_changed", plain("faction"), Significance.MAJOR, EvidenceRole.EVIDENCE, required=TRANSITION
)
COUNCILOR_STATUS_CHANGED = EventKind(
    "councilor.status_changed",
    _councilor_field("status"),
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=TRANSITION,
)
COUNCILOR_LOCATION_CHANGED = EventKind(
    "councilor.location_changed",
    _councilor_field("location"),
    Significance.TRIVIAL,
    EvidenceRole.EVIDENCE,
    required=TRANSITION,
)
DETAINING_FACTION_CHANGED = EventKind(
    "councilor.detaining_faction_changed",
    _councilor_field("detaining faction"),
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=TRANSITION,
)
COUNCILOR_APPEARED = EventKind(
    "councilor.appeared",
    _councilor_presence,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=SIDE,
    rule=Rule.COUNCILOR_PRESENCE,
)
COUNCILOR_DISAPPEARED = EventKind(
    "councilor.disappeared",
    _councilor_presence,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=SIDE,
    rule=Rule.COUNCILOR_PRESENCE,
)
ROSTER_CHANGED = EventKind(
    "faction.councilors_changed",
    list_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=LIST,
    optional=LIST_DETAIL,
)
COUNCILOR_ORGS_CHANGED = EventKind(
    "councilor.orgs_changed",
    list_changed,
    Significance.TRIVIAL,
    EvidenceRole.EVIDENCE,
    required=LIST,
    optional=LIST_DETAIL,
)

ORGANIZATION_APPEARED = EventKind(
    "organization.appeared",
    presence_with(EntityDomain.REGION, "home region"),
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    required=SIDE,
)
ORGANIZATION_DISAPPEARED = EventKind(
    "organization.disappeared",
    presence_with(EntityDomain.REGION, "home region"),
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    required=SIDE,
)
ASSIGNED_COUNCILOR_CHANGED = EventKind(
    "organization.assigned_councilor_changed",
    plain("assigned councilor"),
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
    stake=Stake.ORGANIZATION,
)
FACTION_ORBIT_CHANGED = EventKind(
    "organization.faction_orbit_changed",
    plain("faction orbit"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
)
UNASSIGNED_ORGS_CHANGED = EventKind(
    "faction.unassigned_orgs_changed",
    list_changed,
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    required=LIST,
    optional=LIST_DETAIL,
)

NATION_CONTROL_CHANGED = EventKind(
    "faction.nation_control_changed",
    _nation_control_changed,
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
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
    CONTROLLER_CHANGED,
    POINT_NATION_CHANGED,
    POINT_APPEARED,
    POINT_DISAPPEARED,
    LOSS_RECORDED,
    FACTION_POINTS_CHANGED,
    NATION_POINTS_CHANGED,
    COUNCILOR_FACTION_CHANGED,
    COUNCILOR_STATUS_CHANGED,
    COUNCILOR_LOCATION_CHANGED,
    DETAINING_FACTION_CHANGED,
    COUNCILOR_APPEARED,
    COUNCILOR_DISAPPEARED,
    ROSTER_CHANGED,
    COUNCILOR_ORGS_CHANGED,
    ORGANIZATION_APPEARED,
    ORGANIZATION_DISAPPEARED,
    ASSIGNED_COUNCILOR_CHANGED,
    FACTION_ORBIT_CHANGED,
    UNASSIGNED_ORGS_CHANGED,
    NATION_CONTROL_CHANGED,
)
