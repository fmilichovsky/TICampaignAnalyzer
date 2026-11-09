"""Wars and federations: the war arc and federation lifecycle narrative events.

Narrative events are bookkeeping as constituents: the narrative event holding them states them in summary form.
"""

from __future__ import annotations

from ..model.events import Event, Role
from ..model.kinds import EventKind, EvidenceRole
from .text import METRIC_SHIFTS, METRIC_SHIFTS_OMITTED, attribute_label, count_label, role_label

# --- Narrative events (#325) ---------------------------------------------------------------------------------------


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
