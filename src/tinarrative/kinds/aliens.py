"""Alien presence on Earth as the region sub-states show it: crashdowns, landings, facilities, xenoforming.

None is narrator evidence: no narrative event cites them yet.
"""

from __future__ import annotations

from ..model.events import Event, Significance
from ..model.kinds import EventKind, EvidenceRole
from ..model.values import Unknown
from .text import attribute_text, plain, subject_label, transition_label

TRANSITION = frozenset({"transition", "before", "after"})


def _crashdown(event: Event) -> str:
    if event.sources and event.sources[0].change.field == "crashdownTime":
        return f"{subject_label(event)} {transition_label(event, 'crashdown time')}"
    text = f"{subject_label(event)} {transition_label(event, 'crashdown present')}"
    if not isinstance(event.attribute("crashdown_time"), Unknown):
        text += f"; crashdown time {attribute_text(event, 'crashdown_time')}"
    return text


CRASHDOWN_CHANGED = EventKind(
    "region.crashdown_changed",
    _crashdown,
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
    optional=frozenset({"crashdown_time"}),
)
LANDING_CHANGED = EventKind(
    "region.landing_changed",
    plain("landing present"),
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
)
ALIEN_FACILITY_CHANGED = EventKind(
    "region.alien_facility_changed",
    plain("alien facility built"),
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
)
XENOFORMING_CHANGED = EventKind(
    "region.xenoforming_changed",
    plain("xenoforming level"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
)

KINDS = (CRASHDOWN_CHANGED, LANDING_CHANGED, ALIEN_FACILITY_CHANGED, XENOFORMING_CHANGED)
