"""Army movements and deployments, and the buildups and navies told from a nation's army counts."""

from __future__ import annotations

from collections.abc import Callable

from ..model.entities import EntityDomain
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole, Rule, Stake
from .narrative import count, narrative_kind, role
from .text import TRANSITION, attribute_label, contextual, list_changed, subject_label, transition_label


def _presence(verb: str) -> Callable[[Event], str]:
    """``<army> <verb> (megafauna, faction <f>, region <r>)``; a missing faction or region is left out."""

    def describe(event: Event) -> str:
        details = ["megafauna"] if event.attribute("megafauna") is True else []
        for label, domain in (("faction", EntityDomain.FACTION), ("region", EntityDomain.REGION)):
            ref = next((ref for ref in event.entities[1:] if ref.entity_id.domain is domain), None)
            if ref is not None:
                details.append(f"{label} {ref.label()}")
        text = f"{subject_label(event)} {verb}"
        return f"{text} ({', '.join(details)})" if details else text

    return describe


def _faction_changed(event: Event) -> str:
    """``<army> faction: <before> -> <after> (in <region>)``: the new owner leads, the region follows."""
    region = next((ref for ref in event.entities[1:] if ref.entity_id.domain is EntityDomain.REGION), None)
    text = f"{subject_label(event)} {transition_label(event, 'faction')}"
    return f"{text} (in {region.label()})" if region is not None else text


REGION_CHANGED = EventKind(
    "army.region_changed",
    contextual("region", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
    optional=frozenset({"home_nation"}),
)
FACTION_CHANGED = EventKind(
    "army.faction_changed",
    _faction_changed,
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
    optional=frozenset({"home_nation"}),
)
DESTROYED_CHANGED = EventKind(
    "army.destroyed_changed",
    contextual("destroyed flag", EntityDomain.FACTION),
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
    optional=frozenset({"home_nation"}),
)
STRENGTH_CHANGED = EventKind(
    "army.strength_changed",
    contextual("strength", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
    optional=frozenset({"home_nation"}),
)
TYPE_CHANGED = EventKind(
    "army.type_changed",
    contextual("type", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
    optional=frozenset({"home_nation"}),
)
DEPLOYMENT_TYPE_CHANGED = EventKind(
    "army.deployment_type_changed",
    contextual("deployment type", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
    optional=frozenset({"home_nation"}),
)
HOME_REGION_CHANGED = EventKind(
    "army.home_region_changed",
    contextual("home region", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
    optional=frozenset({"home_nation"}),
)
APPEARED = EventKind(
    "army.appeared",
    _presence("appeared"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"side"}),
    optional=frozenset({"deployment_type", "megafauna", "home_nation"}),
    rule=Rule.ARMY_PRESENCE,
)
DISAPPEARED = EventKind(
    "army.disappeared",
    _presence("disappeared"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"side"}),
    optional=frozenset({"deployment_type", "megafauna", "home_nation"}),
    rule=Rule.ARMY_PRESENCE,
)

FACTION_ARMIES_CHANGED = EventKind(
    "faction.armies_changed",
    list_changed,
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
)
NATION_ARMIES_CHANGED = EventKind(
    "nation.armies_changed",
    list_changed,
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
)
REGION_ARMIES_CHANGED = EventKind(
    "region.armies_changed",
    list_changed,
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
)


def _army_count(change: str) -> Callable[[Event], str]:
    def describe(event: Event) -> str:
        return (
            f"{role(event, Role.ACTOR)} {change} its standard armies: {attribute_label(event, 'before')} -> "
            f"{attribute_label(event, 'after')}"
        )

    return describe


def _navy_established(event: Event) -> str:
    return f"{role(event, Role.ACTOR)} established a navy ({count(event.attribute('navies'), 'naval army')})"


_ARMY_COUNT = frozenset({"before", "after", "gdp_rank", "strength_rank"})
MILITARY_BUILDUP = narrative_kind(
    "nation.military_buildup",
    _army_count("built up"),
    required=_ARMY_COUNT,
    base=Significance.MAJOR,
    stake=Stake.ACTOR,
)
DEMOBILIZATION = narrative_kind(
    "nation.demobilization",
    _army_count("demobilized"),
    required=_ARMY_COUNT,
    base=Significance.MAJOR,
    stake=Stake.ACTOR,
)
NAVY_ESTABLISHED = narrative_kind(
    "nation.navy_established",
    _navy_established,
    required=frozenset({"navies", "gdp_rank", "strength_rank"}),
    base=Significance.MAJOR,
    stake=Stake.ACTOR,
)

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
    FACTION_ARMIES_CHANGED,
    NATION_ARMIES_CHANGED,
    REGION_ARMIES_CHANGED,
    MILITARY_BUILDUP,
    DEMOBILIZATION,
    NAVY_ESTABLISHED,
)
