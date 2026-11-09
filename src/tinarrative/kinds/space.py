"""Space: the space campaign, colonisation wave and fleet build-up narrative events.

Narrative events are bookkeeping as constituents: the narrative event holding them states them in summary form.
"""

from __future__ import annotations

from ..diff.render import render_value
from ..model.events import Event, Role
from ..model.kinds import EventKind, EvidenceRole
from .text import attribute_text, count_label, refs_label, role_label

# --- Narrative events (#325) ---------------------------------------------------------------------------------------


def _space_campaign(event: Event) -> str:
    kind = event.attribute("victim_kind")
    target = f"the aliens ({role_label(event, Role.TARGET)})" if kind == "alien" else role_label(event, Role.TARGET)
    text = (
        f"{role_label(event, Role.ACTOR)} fought {target} over "
        f"{count_label(event.attribute('battles'), 'recorded outcome')}"
    )
    losses = [
        count_label(count, label)
        for name, label in (("habs_lost", "hab"), ("fleets_lost", "fleet"))
        if (count := event.attribute(name))
    ]
    if losses:
        text += f", which lost {' and '.join(losses)}"
    won, lost = event.attribute("combats_won"), event.attribute("combats_lost")
    if won or lost:
        text += f"; recorded combats won {render_value(won)}, lost {render_value(lost)}"
    if event.attribute("bodies"):
        text += f"; habs lost at {refs_label(event, 'bodies')}"
    return text


def _colonisation_wave(event: Event) -> str:
    return (
        f"{role_label(event, Role.ACTOR)} reached {refs_label(event, 'bodies')} in quick succession "
        f"({count_label(event.attribute('hab_count'), 'hab')})"
    )


def _fleet_buildup(event: Event) -> str:
    return (
        f"{role_label(event, Role.ACTOR)} put {count_label(event.attribute('count'), 'ship')} of hull "
        f"{attribute_text(event, 'hull')} into service"
    )


SPACE_CAMPAIGN = EventKind(
    "faction.space_campaign",
    _space_campaign,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset(
        {
            "victim_kind",
            "battles",
            "habs_lost",
            "fleets_lost",
            "combats_won",
            "combats_lost",
            "bodies",
            "span_from",
            "span_to",
        }
    ),
    optional=frozenset({"mirror"}),
)
COLONISATION_WAVE = EventKind(
    "faction.colonisation_wave",
    _colonisation_wave,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"bodies", "hab_count", "first_of_any_faction"}),
)
FLEET_BUILDUP = EventKind(
    "faction.fleet_buildup",
    _fleet_buildup,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"hull", "count"}),
)

NARRATIVE_KINDS = (SPACE_CAMPAIGN, COLONISATION_WAVE, FLEET_BUILDUP)
