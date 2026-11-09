"""Armies: where they are, whose they are, their literal flags and presence, and the lists that name them.

None is narrator evidence: the military narrative events state armies in summary form.
"""

from __future__ import annotations

from ..model.entities import EntityDomain
from ..model.events import Event, Significance
from ..model.kinds import EventKind, EvidenceRole, Rule, Template
from .text import TRANSITION, entity, list_changed, name, presence, subject_label, with_context


def _value(event_type: str, template: Template, base: Significance) -> EventKind:
    """A literal change of one army field; ``home_nation`` is context the analyzer adds when it resolves."""
    return EventKind(
        event_type,
        template,
        base,
        EvidenceRole.BOOKKEEPING,
        required=TRANSITION,
        optional=frozenset({"home_nation"}),
    )


def _presence(event: Event) -> str:
    faction = name(entity(event, EntityDomain.FACTION))
    region = name(entity(event, EntityDomain.REGION))
    text = f"{subject_label(event)} (faction {faction}, region {region}) {presence(event)}"
    return text + " (megafauna)" if event.attribute("megafauna") is True else text


REGION_CHANGED = _value("army.region_changed", with_context("region", EntityDomain.FACTION), Significance.MINOR)
FACTION_CHANGED = _value(
    "army.faction_changed", with_context("faction", EntityDomain.REGION, "in "), Significance.MAJOR
)
DESTROYED_CHANGED = _value(
    "army.destroyed_changed", with_context("destroyed flag", EntityDomain.FACTION), Significance.MAJOR
)
# The four below were silently MINOR (the default) before the kinds; declared as such.
STRENGTH_CHANGED = _value("army.strength_changed", with_context("strength", EntityDomain.FACTION), Significance.MINOR)
TYPE_CHANGED = _value("army.type_changed", with_context("type", EntityDomain.FACTION), Significance.MINOR)
DEPLOYMENT_TYPE_CHANGED = _value(
    "army.deployment_type_changed", with_context("deployment type", EntityDomain.FACTION), Significance.MINOR
)
HOME_REGION_CHANGED = _value(
    "army.home_region_changed", with_context("home region", EntityDomain.FACTION), Significance.MINOR
)


def _presence_kind(event_type: str) -> EventKind:
    """The rule always decides (megafauna major, else minor); the base is the silent default it never reaches."""
    return EventKind(
        event_type,
        _presence,
        Significance.MINOR,
        EvidenceRole.BOOKKEEPING,
        required=frozenset({"side"}),
        optional=frozenset({"home_nation", "deployment_type", "megafauna"}),
        rule=Rule.ARMY_PRESENCE,
    )


APPEARED = _presence_kind("army.appeared")
DISAPPEARED = _presence_kind("army.disappeared")

LIST_FIELD = "armies"
LIST_OWNERS = (EntityDomain.FACTION, EntityDomain.NATION, EntityDomain.REGION)
ARMIES_CHANGED: dict[str, EventKind] = {
    domain.value: EventKind(
        f"{domain.value}.{LIST_FIELD}_changed",
        list_changed,
        Significance.TRIVIAL,
        EvidenceRole.BOOKKEEPING,
        required=frozenset({"transition"}),
        optional=frozenset({"member", "before", "after"}),
    )
    for domain in LIST_OWNERS
}
"""One kind per owner of an army list: the leftover members no army field explained."""

KINDS = (
    REGION_CHANGED,
    FACTION_CHANGED,
    DESTROYED_CHANGED,
    STRENGTH_CHANGED,
    TYPE_CHANGED,
    DEPLOYMENT_TYPE_CHANGED,
    HOME_REGION_CHANGED,
    APPEARED,
    DISAPPEARED,
    *ARMIES_CHANGED.values(),
)
