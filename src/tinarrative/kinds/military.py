"""Army movements and deployments, and the buildups and navies told from a nation's army counts."""

from __future__ import annotations

from collections.abc import Callable

from ..model.entities import EntityDomain
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole, Rule, Stake
from .narrative import count, narrative_kind, role
from .text import TRANSITION, attribute_label, contextual, list_changed, subject_label


def _presence(event: Event) -> str:
    faction = next((ref for ref in event.entities[1:] if ref.entity_id.domain is EntityDomain.FACTION), None)
    region = next((ref for ref in event.entities[1:] if ref.entity_id.domain is EntityDomain.REGION), None)
    faction_name = faction.label() if faction is not None else "null"
    region_name = region.label() if region is not None else "null"
    present = event.attribute("side") == "after"
    status = "is present only in the after snapshot" if present else "is absent from the after snapshot"
    text = f"{subject_label(event)} (faction {faction_name}, region {region_name}) {status}"
    return text + " (megafauna)" if event.attribute("megafauna") is True else text


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
    contextual("faction", EntityDomain.REGION, "in "),
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
    _presence,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"side"}),
    optional=frozenset({"deployment_type", "megafauna", "home_nation"}),
    rule=Rule.ARMY_PRESENCE,
)
DISAPPEARED = EventKind(
    "army.disappeared",
    _presence,
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
