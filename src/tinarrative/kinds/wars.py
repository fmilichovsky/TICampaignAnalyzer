"""Wars, the nation lists that corroborate them, and the arc of each war."""

from __future__ import annotations

from ..model.entities import EntityDomain
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole, Scaling, ShareOf, Template
from ..model.values import Unknown
from .narrative import narrative_kind, role
from .text import attribute_label, attribute_text, list_changed, plain, region_count, subject_label, transition_label

BOOKKEEPING = EvidenceRole.BOOKKEEPING
EVIDENCE = EvidenceRole.EVIDENCE


def _side_list(event: Event) -> str:
    nations = ", ".join(ref.label() for ref in event.entities[1:] if ref.entity_id.domain is EntityDomain.NATION)
    return f"nations {nations}" if nations else "no nations"


def _presence(verb: str) -> Template:
    def describe(event: Event) -> str:
        text = f"{subject_label(event)} {verb}"
        if not isinstance(event.attribute("started_on"), Unknown):
            text += f"; start date {attribute_text(event, 'started_on')}"
        return f"{text}; {_side_list(event)}"

    return describe


def _alliance_changed(event: Event) -> str:
    added = event.attribute("transition") == "added"
    member = attribute_label(event, "member")
    movement = "added to" if added else "removed from"
    return f"{member} {movement} the {attribute_text(event, 'side')} side of {subject_label(event)}"


def _alliance_list(side: str) -> Template:
    """``<member> added to the <side> alliance list of <war>`` (``removed from``), or the literal transition."""

    def describe(event: Event) -> str:
        transition = event.attribute("transition")
        if transition == "unresolved":
            return f"{subject_label(event)} {transition_label(event, f'{side} alliance list')}"
        movement = "added to" if transition == "added" else "removed from"
        return f"{attribute_label(event, 'member')} {movement} the {side} alliance list of {subject_label(event)}"

    return describe


APPEARED = EventKind(
    "war.appeared",
    _presence("appeared"),
    EVIDENCE,
    frozenset({"side"}),
    optional=frozenset({"started_on"}),
    base=Significance.MAJOR,
)
DISAPPEARED = EventKind(
    "war.disappeared", _presence("disappeared"), EVIDENCE, frozenset({"side"}), base=Significance.MAJOR
)
ALLIANCE_CHANGED = EventKind(
    "war.alliance_changed",
    _alliance_changed,
    EVIDENCE,
    frozenset({"side", "member", "transition"}),
    base=Significance.MAJOR,
)
ATTACKER_CHANGED = EventKind(
    "war.attacker_changed",
    plain("attacker"),
    BOOKKEEPING,
    required=frozenset({"transition", "before", "after"}),
    base=Significance.MINOR,
)
DEFENDER_CHANGED = EventKind(
    "war.defender_changed",
    plain("defender"),
    BOOKKEEPING,
    required=frozenset({"transition", "before", "after"}),
    base=Significance.MINOR,
)
LAST_FIGHTING_CHANGED = EventKind(
    "war.last_fighting_changed",
    plain("date of last fighting"),
    EVIDENCE,
    required=frozenset({"transition", "before", "after"}),
    base=Significance.MINOR,
)
ATTACKING_ALLIANCE_CHANGED = EventKind(
    "war.attacking_alliance_changed",
    _alliance_list("attacking"),
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
    base=Significance.MINOR,
)
DEFENDING_ALLIANCE_CHANGED = EventKind(
    "war.defending_alliance_changed",
    _alliance_list("defending"),
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
    base=Significance.MINOR,
)
NATION_WARS_CHANGED = EventKind(
    "nation.wars_changed",
    list_changed,
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
    base=Significance.MINOR,
)


def _war_arc(event: Event) -> str:
    text = f"{attribute_label(event, 'war')} between {role(event, Role.ACTOR)} and {role(event, Role.TARGET)}"
    regions = event.attribute("regions_transferred")
    if isinstance(regions, tuple) and regions:
        text += f"; {region_count(len(regions))} changed hands between the sides"
    return text


ARC = narrative_kind(
    "war.arc",
    _war_arc,
    required=frozenset(
        {
            "war",
            "started_on",
            "duration_days",
            "duration_days_at_most",
            "attackers",
            "defenders",
            "regions_transferred",
            "nuclear_strikes",
            "metric_shifts",
        }
    ),
    base=Significance.MAJOR,
    share=ShareOf.WAR_SIDES,
    scaling=Scaling.POWER,
)

KINDS = (
    APPEARED,
    DISAPPEARED,
    ALLIANCE_CHANGED,
    ATTACKER_CHANGED,
    DEFENDER_CHANGED,
    LAST_FIGHTING_CHANGED,
    ATTACKING_ALLIANCE_CHANGED,
    DEFENDING_ALLIANCE_CHANGED,
    NATION_WARS_CHANGED,
    ARC,
)
