"""Interstate wars and federations: presence, sides, members, renames and the leftover lists of both.

War presence and sides, last fighting and the federation record dates are narrator evidence; the leading nations,
the alliance lists and the nation mirrors of both are not.
"""

from __future__ import annotations

from ..model.entities import EntityDomain
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole, Stake
from ..model.values import Unknown
from .text import (
    METRIC_SHIFTS,
    METRIC_SHIFTS_OMITTED,
    TRANSITION,
    attribute_label,
    attribute_text,
    count_label,
    list_changed,
    plain,
    presence,
    renamed,
    role_label,
    subject_label,
)

LIST_CHANGED = frozenset({"transition"})
"""The attribute keys every list change carries; a member, or the unresolved before and after, come on top."""
LIST_CHANGED_OPTIONAL = frozenset({"member", "before", "after"})


def _side_list(event: Event) -> str:
    nations = ", ".join(ref.label() for ref in event.entities[1:] if ref.entity_id.domain is EntityDomain.NATION)
    return nations or "no nations"


def _war_presence(event: Event) -> str:
    text = f"{subject_label(event)} ({_side_list(event)}) {presence(event)}"
    if not isinstance(event.attribute("started_on"), Unknown):
        text += f"; start date {attribute_text(event, 'started_on')}"
    return text


def _alliance_changed(event: Event) -> str:
    sign = "+" if event.attribute("transition") == "added" else "-"
    return f"{subject_label(event)} {attribute_text(event, 'side')} side: {sign}{attribute_label(event, 'member')}"


def _members_changed(event: Event) -> str:
    if event.attribute("transition") == "unresolved":
        return list_changed(event)
    sign = "+" if event.attribute("transition") == "added" else "-"
    return f"{subject_label(event)} members: {sign}{attribute_label(event, 'member')}"


def _federation_presence(event: Event) -> str:
    return f"{subject_label(event)} (members {_side_list(event)}) {presence(event)}"


WAR_APPEARED = EventKind(
    "war.appeared",
    _war_presence,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"side"}),
    optional=frozenset({"started_on"}),
)
WAR_DISAPPEARED = EventKind(
    "war.disappeared",
    _war_presence,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"side"}),
    optional=frozenset({"started_on"}),
)
WAR_ALLIANCE_CHANGED = EventKind(
    "war.alliance_changed",
    _alliance_changed,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"side", "member", "transition"}),
)
WAR_ATTACKER_CHANGED = EventKind(
    "war.attacker_changed",
    plain("attacker"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
)
WAR_DEFENDER_CHANGED = EventKind(
    "war.defender_changed",
    plain("defender"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
)
WAR_LAST_FIGHTING_CHANGED = EventKind(
    "war.last_fighting_changed",
    plain("date of last fighting"),
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=TRANSITION,
)
WAR_ATTACKING_ALLIANCE_CHANGED = EventKind(
    "war.attacking_alliance_changed",
    list_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=LIST_CHANGED,
    optional=LIST_CHANGED_OPTIONAL,
)
WAR_DEFENDING_ALLIANCE_CHANGED = EventKind(
    "war.defending_alliance_changed",
    list_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=LIST_CHANGED,
    optional=LIST_CHANGED_OPTIONAL,
)
NATION_WARS_CHANGED = EventKind(
    "nation.wars_changed",
    list_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=LIST_CHANGED,
    optional=LIST_CHANGED_OPTIONAL,
)

INTERSTATE_WARS_CHANGED = EventKind(
    "campaign.interstate_wars_changed",
    list_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=LIST_CHANGED,
    optional=LIST_CHANGED_OPTIONAL,
)

FEDERATION_APPEARED = EventKind(
    "federation.appeared",
    _federation_presence,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"side"}),
)
FEDERATION_DISAPPEARED = EventKind(
    "federation.disappeared",
    _federation_presence,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"side"}),
)
FEDERATION_MEMBERS_CHANGED = EventKind(
    "federation.members_changed",
    _members_changed,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=LIST_CHANGED,
    optional=LIST_CHANGED_OPTIONAL,
)
FEDERATION_RENAMED = EventKind(
    "federation.renamed",
    renamed,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=TRANSITION,
    optional=frozenset({"federation_name_before", "federation_name_after"}),
)
NATION_FEDERATION_CHANGED = EventKind(
    "nation.federation_changed",
    plain("federation"),
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
    stake=Stake.NATION,
)

KINDS = (
    WAR_APPEARED,
    WAR_DISAPPEARED,
    WAR_ALLIANCE_CHANGED,
    WAR_ATTACKER_CHANGED,
    WAR_DEFENDER_CHANGED,
    WAR_LAST_FIGHTING_CHANGED,
    WAR_ATTACKING_ALLIANCE_CHANGED,
    WAR_DEFENDING_ALLIANCE_CHANGED,
    NATION_WARS_CHANGED,
    INTERSTATE_WARS_CHANGED,
    FEDERATION_APPEARED,
    FEDERATION_DISAPPEARED,
    FEDERATION_MEMBERS_CHANGED,
    FEDERATION_RENAMED,
    NATION_FEDERATION_CHANGED,
)


# --- Narrative events ----------------------------------------------------------------------------------------------


def _war_arc(event: Event) -> str:
    war = attribute_label(event, "war")
    text = f"{war} between {role_label(event, Role.ACTOR)} and {role_label(event, Role.TARGET)}"
    regions = event.attribute("regions_transferred")
    if isinstance(regions, tuple) and regions:
        text += f"; {count_label(len(regions), 'region')} changed hands between the sides"
    return text


def _federation_lifecycle(event: Event) -> str:
    changes = event.attribute("member_changes")
    count = len(changes) if isinstance(changes, tuple) else 0
    return (
        f"{role_label(event, Role.ACTOR)} members {attribute_label(event, 'members_initial')} -> "
        f"{attribute_label(event, 'members_final')} ({count} member change{'' if count == 1 else 's'})"
    )


WAR_ARC = EventKind(
    "war.arc",
    _war_arc,
    None,
    EvidenceRole.BOOKKEEPING,
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
        }
    )
    | METRIC_SHIFTS,
    optional=METRIC_SHIFTS_OMITTED,
)
FEDERATION_LIFECYCLE = EventKind(
    "federation.lifecycle",
    _federation_lifecycle,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"members_initial", "member_changes", "members_final"}) | METRIC_SHIFTS,
    optional=METRIC_SHIFTS_OMITTED,
)

NARRATIVE_KINDS = (WAR_ARC, FEDERATION_LIFECYCLE)
