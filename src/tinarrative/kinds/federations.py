"""Federation presence, membership, names, mirrored nation references, and the lifecycle of each federation."""

from __future__ import annotations

from ..model.entities import EntityDomain
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole, Stake
from .narrative import count, narrative_kind, role
from .text import attribute_label, list_changed, plain, presence, subject_label

BOOKKEEPING = EvidenceRole.BOOKKEEPING
EVIDENCE = EvidenceRole.EVIDENCE


def _side_list(event: Event) -> str:
    nations = ", ".join(ref.label() for ref in event.entities[1:] if ref.entity_id.domain is EntityDomain.NATION)
    return nations or "no nations"


def _presence(event: Event) -> str:
    return f"{subject_label(event)} (members {_side_list(event)}) {presence(event)}"


def _members_changed(event: Event) -> str:
    if event.attribute("transition") == "unresolved":
        return list_changed(event)
    sign = "+" if event.attribute("transition") == "added" else "-"
    return f"{subject_label(event)} members: {sign}{attribute_label(event, 'member')}"


def _renamed(event: Event) -> str:
    return f"{subject_label(event)} renamed: {attribute_label(event, 'before')} -> {attribute_label(event, 'after')}"


APPEARED = EventKind("federation.appeared", _presence, Significance.MAJOR, EVIDENCE, frozenset({"side"}))
DISAPPEARED = EventKind("federation.disappeared", _presence, Significance.MAJOR, EVIDENCE, frozenset({"side"}))
MEMBERS_CHANGED = EventKind(
    "federation.members_changed",
    _members_changed,
    Significance.MAJOR,
    EVIDENCE,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
)
RENAMED = EventKind(
    "federation.renamed",
    _renamed,
    Significance.MAJOR,
    EVIDENCE,
    required=frozenset({"transition", "before", "after"}),
    optional=frozenset({"federation_name_before", "federation_name_after"}),
)
NATION_FEDERATION_CHANGED = EventKind(
    "nation.federation_changed",
    plain("federation"),
    Significance.MAJOR,
    BOOKKEEPING,
    required=frozenset({"transition", "before", "after"}),
    stake=Stake.NATION,
)


def _lifecycle(event: Event) -> str:
    changes = event.attribute("member_changes")
    number = len(changes) if isinstance(changes, tuple) else 0
    return (
        f"{role(event, Role.ACTOR)} members {attribute_label(event, 'members_initial')} -> "
        f"{attribute_label(event, 'members_final')} ({count(number, 'member change')})"
    )


LIFECYCLE = narrative_kind(
    "federation.lifecycle",
    _lifecycle,
    required=frozenset({"members_initial", "member_changes", "members_final", "metric_shifts"}),
    base=Significance.MAJOR,
    stake=Stake.MEMBERS,
)

KINDS = (APPEARED, DISAPPEARED, MEMBERS_CHANGED, RENAMED, NATION_FEDERATION_CHANGED, LIFECYCLE)
