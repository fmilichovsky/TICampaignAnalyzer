"""Control points, councilors, organizations, inferred faction control of nations, and the takeovers it adds up to."""

from __future__ import annotations

from collections.abc import Callable

from ..model.entities import EntityDomain, EntityRef
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole, Rule, Scaling, ShareOf
from ..model.values import Unknown
from .narrative import count, has_role, narrative_kind, role
from .text import (
    TRANSITION,
    attribute_label,
    attribute_text,
    entity,
    name,
    plain,
    refs,
    subject_label,
    transition_label,
)

BOOKKEEPING = EvidenceRole.BOOKKEEPING
EVIDENCE = EvidenceRole.EVIDENCE


def _controller_changed(event: Event) -> str:
    text = f"{subject_label(event)} {transition_label(event, 'controller')}"
    nation = entity(event, EntityDomain.NATION)
    if nation is not None:
        text += f"; nation {nation.label()}"
    recorded = event.attribute("loss_recorded_on")
    if not isinstance(recorded, Unknown):
        text += f"; loss recorded by {attribute_label(event, 'before')} on {attribute_text(event, 'loss_recorded_on')}"
    return text


def _with_context(text: str, label: str, ref: EntityRef | None) -> str:
    """``text (label ref)``; a missing context says nothing and is left out."""
    return text if ref is None else f"{text} ({label} {ref.label()})"


def _control_point_presence(event: Event) -> str:
    """``<point> appeared (nation N, controller C)``; the snapshot side is the type name."""
    context = ", ".join(
        f"{label} {ref.label()}"
        for label, ref in (
            ("nation", entity(event, EntityDomain.NATION)),
            ("controller", entity(event, EntityDomain.FACTION)),
        )
        if ref is not None
    )
    text = f"{subject_label(event)} {_arrival(event)}"
    return f"{text} ({context})" if context else text


def _arrival(event: Event) -> str:
    return "appeared" if event.attribute("side") == "after" else "disappeared"


def _loss_recorded(event: Event) -> str:
    faction = name(entity(event, EntityDomain.FACTION))
    text = f"{faction} records {subject_label(event)} as lost on {attribute_text(event, 'recorded_on')}"
    if not isinstance(event.attribute("previous_recorded_on"), Unknown):
        text += f" (previously {attribute_text(event, 'previous_recorded_on')})"
    return text


def _councilor_field(label: str) -> Callable[[Event], str]:
    def describe(event: Event) -> str:
        text = f"{subject_label(event)} {transition_label(event, label)}"
        return _with_context(text, "faction", entity(event, EntityDomain.FACTION))

    return describe


def _councilor_presence(event: Event) -> str:
    text = f"{subject_label(event)} {_arrival(event)}"
    return _with_context(text, "faction", entity(event, EntityDomain.FACTION))


def _organization_presence(event: Event) -> str:
    text = f"{subject_label(event)} {_arrival(event)}"
    return _with_context(text, "home region", entity(event, EntityDomain.REGION))


def _members(label: str) -> Callable[[Event], str]:
    """``<subject> <label>: added <member>`` (``removed`` likewise), or the literal transition when unresolved."""

    def describe(event: Event) -> str:
        transition = event.attribute("transition")
        if transition == "unresolved":
            return f"{subject_label(event)} {transition_label(event, label)}"
        verb = "added" if transition == "added" else "removed"
        return f"{subject_label(event)} {label}: {verb} {attribute_label(event, 'member')}"

    return describe


def _nation_control_changed(event: Event) -> str:
    return f"{subject_label(event)} {transition_label(event, attribute_text(event, 'scope') + ' control')}"


CONTROL_POINT_CONTROLLER_CHANGED = EventKind(
    "control_point.controller_changed",
    _controller_changed,
    BOOKKEEPING,
    required=TRANSITION,
    optional=frozenset({"loss_recorded_on"}),
    share=ShareOf.CONTROL_POINT,
    scaling=Scaling.POWER,
    base=Significance.MAJOR,
)
CONTROL_POINT_NATION_CHANGED = EventKind(
    "control_point.nation_changed", plain("nation"), BOOKKEEPING, TRANSITION, base=Significance.MINOR
)
CONTROL_POINT_APPEARED = EventKind(
    "control_point.appeared", _control_point_presence, BOOKKEEPING, frozenset({"side"}), base=Significance.MINOR
)
CONTROL_POINT_DISAPPEARED = EventKind(
    "control_point.disappeared", _control_point_presence, BOOKKEEPING, frozenset({"side"}), base=Significance.MINOR
)
CONTROL_POINT_LOSS_RECORDED = EventKind(
    "control_point.loss_recorded",
    _loss_recorded,
    BOOKKEEPING,
    required=frozenset({"recorded_on"}),
    optional=frozenset({"previous_recorded_on"}),
    base=Significance.MINOR,
)
FACTION_CONTROL_POINTS_CHANGED = EventKind(
    "faction.control_points_changed",
    _members("control points"),
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
    base=Significance.MINOR,
)
NATION_CONTROL_POINTS_CHANGED = EventKind(
    "nation.control_points_changed",
    _members("control points"),
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
    base=Significance.MINOR,
)

COUNCILOR_FACTION_CHANGED = EventKind(
    "councilor.faction_changed",
    plain("faction"),
    EVIDENCE,
    TRANSITION,
    share=ShareOf.LEFT_FACTION,
    scaling=Scaling.FACTION,
    base=Significance.MAJOR,
)
COUNCILOR_STATUS_CHANGED = EventKind(
    "councilor.status_changed", _councilor_field("status"), EVIDENCE, TRANSITION, base=Significance.MINOR
)
COUNCILOR_LOCATION_CHANGED = EventKind(
    "councilor.location_changed", _councilor_field("location"), EVIDENCE, TRANSITION, base=Significance.TRIVIAL
)
COUNCILOR_DETAINING_FACTION_CHANGED = EventKind(
    "councilor.detaining_faction_changed",
    _councilor_field("detaining faction"),
    EVIDENCE,
    TRANSITION,
    base=Significance.MAJOR,
)
COUNCILOR_APPEARED = EventKind(
    "councilor.appeared",
    _councilor_presence,
    EVIDENCE,
    frozenset({"side"}),
    rule=Rule.COUNCILOR_PRESENCE,
    base=Significance.MINOR,
)
COUNCILOR_DISAPPEARED = EventKind(
    "councilor.disappeared",
    _councilor_presence,
    EVIDENCE,
    frozenset({"side"}),
    rule=Rule.COUNCILOR_PRESENCE,
    base=Significance.MINOR,
)
FACTION_COUNCILORS_CHANGED = EventKind(
    "faction.councilors_changed",
    _members("councilors"),
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
    base=Significance.MINOR,
)

ORGANIZATION_APPEARED = EventKind(
    "organization.appeared", _organization_presence, BOOKKEEPING, frozenset({"side"}), base=Significance.TRIVIAL
)
ORGANIZATION_DISAPPEARED = EventKind(
    "organization.disappeared", _organization_presence, BOOKKEEPING, frozenset({"side"}), base=Significance.TRIVIAL
)
ORGANIZATION_ASSIGNED_COUNCILOR_CHANGED = EventKind(
    "organization.assigned_councilor_changed",
    plain("assigned councilor"),
    BOOKKEEPING,
    TRANSITION,
    share=ShareOf.ORGANIZATION,
    scaling=Scaling.ORGANIZATION,
    base=Significance.MAJOR,
)
ORGANIZATION_FACTION_ORBIT_CHANGED = EventKind(
    "organization.faction_orbit_changed", plain("faction orbit"), BOOKKEEPING, TRANSITION, base=Significance.MINOR
)
COUNCILOR_ORGS_CHANGED = EventKind(
    "councilor.orgs_changed",
    _members("organizations"),
    EVIDENCE,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
    base=Significance.TRIVIAL,
)
FACTION_UNASSIGNED_ORGS_CHANGED = EventKind(
    "faction.unassigned_orgs_changed",
    _members("unassigned organizations"),
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
    base=Significance.TRIVIAL,
)

NATION_CONTROL_CHANGED = EventKind(
    "faction.nation_control_changed",
    _nation_control_changed,
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
    share=ShareOf.NATION,
    scaling=Scaling.POWER,
    base=Significance.MAJOR,
)


def _takeover(event: Event) -> str:
    text = f"{role(event, Role.ACTOR)} took control of {role(event, Role.TARGET)}"
    if has_role(event, Role.LOSER):
        text += f" from {role(event, Role.LOSER)}"
    if event.attribute("consolidated") is True:
        text += " and holds every control point"
    return text


def _takeover_wave(event: Event) -> str:
    return (
        f"{role(event, Role.ACTOR)} took control in quick succession "
        f"({count(event.attribute('count'), 'takeover')}): {refs(event, 'nations')}"
    )


TAKEOVER = narrative_kind(
    "faction.takeover",
    _takeover,
    required=frozenset(
        {
            "scopes",
            "cause",
            "executive_recorded_on",
            "previous_executive",
            "consolidated",
            "gdp_rank",
            "metric_shifts",
        }
    ),
    # Takeovers sharing an anchor interval: the derived order, else both ambiguous.
    optional=frozenset({"succeeds", "succeeded_by", "ambiguous", "alternatives"}),
    base=Significance.MAJOR,
    share=ShareOf.TARGETS,
    scaling=Scaling.POWER,
)
TAKEOVER_WAVE = narrative_kind(
    "faction.takeover_wave",
    _takeover_wave,
    required=frozenset({"nations", "count"}),
    base=Significance.MAJOR,
    share=ShareOf.TARGETS,
    scaling=Scaling.POWER,
    digests_members=True,
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
    TAKEOVER,
    TAKEOVER_WAVE,
)
