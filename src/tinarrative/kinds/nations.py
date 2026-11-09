"""Nations: the territory, diplomacy, metric, nuclear and space-asset narrative events.

Narrative events are bookkeeping as constituents: the narrative event holding them states them in summary form.
"""

from __future__ import annotations

from ..model.entities import EntityRef
from ..model.events import Event, Role
from ..model.kinds import EventKind, EvidenceRole, Template
from .text import (
    METRIC_SHIFTS,
    METRIC_SHIFTS_OMITTED,
    attribute_label,
    attribute_text,
    band_label,
    count_label,
    has_role,
    refs_label,
    role_label,
)

# --- Narrative events (#325) ---------------------------------------------------------------------------------------


def _region_count(event: Event, name: str = "region_count") -> str:
    return count_label(event.attribute(name), "region")


def _expansion(event: Event) -> str:
    text = f"{role_label(event, Role.ACTOR)} expanded over {role_label(event, Role.TARGET)}: {_region_count(event)}"
    mode = event.attribute("mode")
    return f"{text} ({mode})" if isinstance(mode, str) else text


def _cession(event: Event) -> str:
    return f"{role_label(event, Role.ACTOR)} ceded {_region_count(event)} to {role_label(event, Role.BENEFICIARY)}"


def _merger(event: Event) -> str:
    text = f"{role_label(event, Role.ACTOR)} absorbed {role_label(event, Role.TARGET)} by unification"
    faction = event.attribute("unifying_faction")
    return f"{text} under {faction.label()}" if isinstance(faction, EntityRef) else text


def _release(event: Event) -> str:
    if has_role(event, Role.ACTOR):
        return f"{role_label(event, Role.ACTOR)} released {role_label(event, Role.BENEFICIARY)}"
    return f"{role_label(event, Role.BENEFICIARY)} was released by one of {refs_label(event, 'parents')}"


def _breakaway(event: Event) -> str:
    return f"{role_label(event, Role.ACTOR)} broke away from {role_label(event, Role.TARGET)}"


def _claims_declared(event: Event) -> str:
    return f"{role_label(event, Role.ACTOR)} claimed regions of {role_label(event, Role.TARGET)}"


def _band_shift(event: Event) -> str:
    return f"{role_label(event, Role.ACTOR)} {band_label(event)}"


def _population_collapse(event: Event) -> str:
    return (
        f"{role_label(event, Role.ACTOR)} population collapse: "
        f"{attribute_label(event, 'before')} -> {attribute_label(event, 'residual')}"
    )


def _economic_trajectory(event: Event) -> str:
    return (
        f"{role_label(event, Role.ACTOR)} per-capita GDP {attribute_text(event, 'direction')}: "
        f"{attribute_label(event, 'first_value')} -> {attribute_label(event, 'last_value')}"
    )


def _diplomatic_realignment(event: Event) -> str:
    def count(name: str) -> int:
        value = event.attribute(name)
        return len(value) if isinstance(value, tuple) else 0

    text = (
        f"{role_label(event, Role.ACTOR)} realigned its diplomacy with {attribute_label(event, 'partner_count')} "
        f"partners: allies +{count('allies_gained')}/-{count('allies_lost')}, "
        f"rivals +{count('rivals_gained')}/-{count('rivals_lost')}"
    )
    if count("reversed_partners"):
        text += f"; reversed with {attribute_label(event, 'reversed_partners')}"
    if event.attribute("executive") is not None:
        text += f"; executive {attribute_label(event, 'executive')}"
    return text


def _nuclear_arsenal(change: str) -> Template:
    def describe(event: Event) -> str:
        return (
            f"{role_label(event, Role.ACTOR)} {change}: "
            f"{attribute_label(event, 'before')} -> {attribute_label(event, 'after')} nuclear weapons"
        )

    return describe


def _space_program_growth(event: Event) -> str:
    return (
        f"{role_label(event, Role.ACTOR)} space program grew: boost {attribute_label(event, 'boost_before')} -> "
        f"{attribute_label(event, 'boost_after')}, mission control "
        f"{attribute_label(event, 'mission_control_before')} -> {attribute_label(event, 'mission_control_after')}"
    )


def _space_defences_established(event: Event) -> str:
    return f"{role_label(event, Role.ACTOR)} established space defences ({_region_count(event, 'regions')})"


def _ranking_changed(event: Event) -> str:
    text = f"Top {attribute_label(event, 'top')} by {attribute_text(event, 'metric')} changed"
    if has_role(event, Role.BENEFICIARY):
        text += f": entered {role_label(event, Role.BENEFICIARY)}"
    if has_role(event, Role.LOSER):
        text += f"; left {role_label(event, Role.LOSER)}"
    return text


_REGIONS = frozenset({"regions", "region_count"})
_BAND_SHIFT = (
    frozenset({"statistic", "before", "after", "from_band", "to_band", "bands_crossed", "gdp_rank"}) | METRIC_SHIFTS
)
_NUCLEAR_ARSENAL = frozenset({"before", "after", "gdp_rank", "strength_rank"})
_SPACE_METRICS = ("boost", "mission_control")


def _bookkeeping(
    event_type: str, template: Template, required: frozenset[str], optional: frozenset[str] = frozenset()
) -> EventKind:
    return EventKind(event_type, template, None, EvidenceRole.BOOKKEEPING, required=required, optional=optional)


EXPANSION = _bookkeeping(
    "nation.expansion", _expansion, frozenset({"losers", "mode"}) | _REGIONS | METRIC_SHIFTS, METRIC_SHIFTS_OMITTED
)
CESSION = _bookkeeping(
    "nation.cession",
    _cession,
    frozenset({"allied", "shared_federation"}) | _REGIONS | METRIC_SHIFTS,
    METRIC_SHIFTS_OMITTED,
)
MERGER = _bookkeeping(
    "nation.merger",
    _merger,
    frozenset({"absorbed", "unifying_faction", "bases", "executive_since"}) | _REGIONS | METRIC_SHIFTS,
    METRIC_SHIFTS_OMITTED,
)
_SECESSION = frozenset({"parents", "releasing_nation", "executive_faction"}) | METRIC_SHIFTS
RELEASE = _bookkeeping("nation.release", _release, _SECESSION, METRIC_SHIFTS_OMITTED)
BREAKAWAY = _bookkeeping("nation.breakaway", _breakaway, _SECESSION, METRIC_SHIFTS_OMITTED)
CLAIMS_DECLARED = _bookkeeping(
    "nation.claims_declared", _claims_declared, frozenset({"regions"}) | METRIC_SHIFTS, METRIC_SHIFTS_OMITTED
)
UNREST_SHIFT = _bookkeeping("nation.unrest_shift", _band_shift, _BAND_SHIFT, METRIC_SHIFTS_OMITTED)
GOVERNMENT_SHIFT = _bookkeeping("nation.government_shift", _band_shift, _BAND_SHIFT, METRIC_SHIFTS_OMITTED)
EDUCATION_SHIFT = _bookkeeping("nation.education_shift", _band_shift, _BAND_SHIFT, METRIC_SHIFTS_OMITTED)
COHESION_SHIFT = _bookkeeping("nation.cohesion_shift", _band_shift, _BAND_SHIFT, METRIC_SHIFTS_OMITTED)
INEQUALITY_SHIFT = _bookkeeping("nation.inequality_shift", _band_shift, _BAND_SHIFT, METRIC_SHIFTS_OMITTED)
MILTECH_SHIFT = _bookkeeping("nation.miltech_shift", _band_shift, _BAND_SHIFT, METRIC_SHIFTS_OMITTED)
POPULATION_COLLAPSE = _bookkeeping(
    "nation.population_collapse",
    _population_collapse,
    frozenset({"before", "after", "residual", "relative_change", "nuked_regions", "causes", "gdp_rank"})
    | METRIC_SHIFTS,
    METRIC_SHIFTS_OMITTED,
)
ECONOMIC_TRAJECTORY = _bookkeeping(
    "nation.economic_trajectory",
    _economic_trajectory,
    frozenset(
        {
            "direction",
            "start_quarter",
            "end_quarter",
            "first_value",
            "last_value",
            "ratio",
            "before_sequence",
            "gdp_rank",
        }
    ),
)
DIPLOMATIC_REALIGNMENT = _bookkeeping(
    "nation.diplomatic_realignment",
    _diplomatic_realignment,
    frozenset(
        {
            "allies_gained",
            "allies_lost",
            "rivals_gained",
            "rivals_lost",
            "reversed_partners",
            "partner_count",
            "executive",
            "gdp_rank",
            "strength_rank",
        }
    )
    | METRIC_SHIFTS,
    METRIC_SHIFTS_OMITTED,
)
NUCLEAR_ARMAMENT = _bookkeeping(
    "nation.nuclear_armament", _nuclear_arsenal("armed with nuclear weapons"), _NUCLEAR_ARSENAL
)
NUCLEAR_BUILDUP = _bookkeeping(
    "nation.nuclear_buildup", _nuclear_arsenal("built up its nuclear arsenal"), _NUCLEAR_ARSENAL
)
NUCLEAR_DISARMAMENT = _bookkeeping(
    "nation.nuclear_disarmament", _nuclear_arsenal("dismantled its nuclear arsenal"), _NUCLEAR_ARSENAL
)
SPACE_PROGRAM_GROWTH = _bookkeeping(
    "nation.space_program_growth",
    _space_program_growth,
    frozenset(
        f"{metric}_{field}" for metric in _SPACE_METRICS for field in ("before", "after", "territory_share", "rank")
    )
    | {"entered_top"},
)
SPACE_DEFENCES_ESTABLISHED = _bookkeeping(
    "nation.space_defences_established", _space_defences_established, frozenset({"regions"})
)
RANKING_CHANGED = _bookkeeping(
    "world.ranking_changed", _ranking_changed, frozenset({"metric", "top", "entrants", "leavers"})
)

NARRATIVE_KINDS = (
    EXPANSION,
    CESSION,
    MERGER,
    RELEASE,
    BREAKAWAY,
    CLAIMS_DECLARED,
    UNREST_SHIFT,
    GOVERNMENT_SHIFT,
    EDUCATION_SHIFT,
    COHESION_SHIFT,
    INEQUALITY_SHIFT,
    MILTECH_SHIFT,
    POPULATION_COLLAPSE,
    ECONOMIC_TRAJECTORY,
    DIPLOMATIC_REALIGNMENT,
    NUCLEAR_ARMAMENT,
    NUCLEAR_BUILDUP,
    NUCLEAR_DISARMAMENT,
    SPACE_PROGRAM_GROWTH,
    SPACE_DEFENCES_ESTABLISHED,
    RANKING_CHANGED,
)
