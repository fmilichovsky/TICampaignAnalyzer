"""Wars and the nation lists that corroborate them."""

from __future__ import annotations

from ..model.entities import EntityDomain
from ..model.events import Event, Significance
from ..model.kinds import EventKind, EvidenceRole
from ..model.values import Unknown
from .text import attribute_label, attribute_text, list_changed, plain, presence, subject_label

BOOKKEEPING = EvidenceRole.BOOKKEEPING
EVIDENCE = EvidenceRole.EVIDENCE


def _side_list(event: Event) -> str:
    nations = ", ".join(ref.label() for ref in event.entities[1:] if ref.entity_id.domain is EntityDomain.NATION)
    return nations or "no nations"


def _presence(event: Event) -> str:
    text = f"{subject_label(event)} ({_side_list(event)}) {presence(event)}"
    if not isinstance(event.attribute("started_on"), Unknown):
        text += f"; start date {attribute_text(event, 'started_on')}"
    return text


def _alliance_changed(event: Event) -> str:
    sign = "+" if event.attribute("transition") == "added" else "-"
    return f"{subject_label(event)} {attribute_text(event, 'side')} side: {sign}{attribute_label(event, 'member')}"


APPEARED = EventKind(
    "war.appeared", _presence, Significance.MAJOR, EVIDENCE, frozenset({"side"}), optional=frozenset({"started_on"})
)
DISAPPEARED = EventKind("war.disappeared", _presence, Significance.MAJOR, EVIDENCE, frozenset({"side"}))
ALLIANCE_CHANGED = EventKind(
    "war.alliance_changed", _alliance_changed, Significance.MAJOR, EVIDENCE, frozenset({"side", "member", "transition"})
)
ATTACKER_CHANGED = EventKind(
    "war.attacker_changed",
    plain("attacker"),
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset({"transition", "before", "after"}),
)
DEFENDER_CHANGED = EventKind(
    "war.defender_changed",
    plain("defender"),
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset({"transition", "before", "after"}),
)
LAST_FIGHTING_CHANGED = EventKind(
    "war.last_fighting_changed",
    plain("date of last fighting"),
    Significance.MINOR,
    EVIDENCE,
    required=frozenset({"transition", "before", "after"}),
)
ATTACKING_ALLIANCE_CHANGED = EventKind(
    "war.attacking_alliance_changed",
    list_changed,
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
)
DEFENDING_ALLIANCE_CHANGED = EventKind(
    "war.defending_alliance_changed",
    list_changed,
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
)
NATION_WARS_CHANGED = EventKind(
    "nation.wars_changed",
    list_changed,
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
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
)
