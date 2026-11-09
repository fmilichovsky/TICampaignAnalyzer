"""Nation territory, structure, relations, claims, names, statistics, population, space and rank, and the territorial
readings inferred from region transfers.

Narrator evidence: territory and its readings, names, a nation's end, statistic and band moves, population, space
assets, the nuclear program and relations. The rest is bookkeeping a narrative event states in summary form.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType

from ..model.entities import EntityDomain, EntityRef
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole, Rule, Stake, Template
from ..model.values import Unknown
from .text import (
    METRIC_SHIFTS,
    METRIC_SHIFTS_OMITTED,
    TRANSITION,
    attribute_label,
    attribute_text,
    bands,
    entity,
    has_role,
    list_changed,
    name,
    plain,
    presence,
    refs,
    region_count,
    regions,
    render_event_value,
    role_label,
    subject_label,
    transition_label,
)

EVIDENCE = EvidenceRole.EVIDENCE
BOOKKEEPING = EvidenceRole.BOOKKEEPING


def _relation_changed(event: Event) -> str:
    pair = " and ".join(ref.label() for ref in event.entities)
    listing = (
        "listed by both"
        if event.attribute("reciprocal") is True
        else f"listed by {attribute_label(event, 'listed_by')} only"
    )
    return f"{pair}: {attribute_text(event, 'relation')} entry {attribute_text(event, 'transition')} ({listing})"


def _executive_change(event: Event) -> str:
    text = (
        f"{subject_label(event)} records an executive change dated {attribute_text(event, 'recorded_on')}: "
        f"new executive {attribute_label(event, 'new_executive')}"
    )
    previous = event.attribute("previous_executive")
    if not isinstance(previous, Unknown):
        text += f" (previously {render_event_value(previous)})"
    return text


def _presence(event: Event) -> str:
    return f"{subject_label(event)} {presence(event)}"


def _claims_changed(label: str) -> Callable[[Event], str]:
    """``<nation> <label> list: +[regions] -[regions]``, an empty side left out; an unresolved list as a transition."""

    def describe(event: Event) -> str:
        if not isinstance(event.attribute("transition"), Unknown):
            return f"{subject_label(event)} {transition_label(event, f'{label} list')}"
        parts = [
            f"{sign}{attribute_label(event, key)}"
            for sign, key in (("+", "added"), ("-", "removed"))
            if event.attribute(key)
        ]
        return f"{subject_label(event)} {label} list: {' '.join(parts)}"

    return describe


def _renamed(event: Event) -> str:
    return f"{subject_label(event)} renamed: {attribute_label(event, 'before')} -> {attribute_label(event, 'after')}"


def _unrest_attempts_changed(event: Event) -> str:
    if not isinstance(event.attribute("transition"), Unknown):
        return f"{subject_label(event)} {transition_label(event, 'faction unrest attempts')}"
    label = f"unrest attempts by {attribute_label(event, 'faction')}"
    return f"{subject_label(event)} {transition_label(event, label)}"


def _new_government_recorded(event: Event) -> str:
    if not isinstance(event.attribute("after"), str):
        return f"{subject_label(event)} {transition_label(event, 'new government date')}"
    text = f"{subject_label(event)} records a new government dated {attribute_text(event, 'after')}"
    if isinstance(event.attribute("before"), str):
        text += f" (previously {attribute_text(event, 'before')})"
    return text


def _statistic_shifted(event: Event) -> str:
    """``<nation> <statistic>[ <key>]: before -> after``; the cause map is evidence for readers, not echoed."""
    label = attribute_text(event, "statistic")
    if not isinstance(event.attribute("key"), Unknown):
        label += f" {attribute_text(event, 'key')}"
    return f"{subject_label(event)} {transition_label(event, label)}"


def _policy_changed(event: Event) -> str:
    return f"{subject_label(event)} {transition_label(event, 'policy ' + attribute_text(event, 'policy'))}"


def _band_crossed(event: Event) -> str:
    """``<nation> <statistic>: <band> -> <band> (before -> after)``; the game's own band labels."""
    return (
        f"{subject_label(event)} {bands(event)} "
        f"({attribute_label(event, 'before')} -> {attribute_label(event, 'after')})"
    )


def _population_changed(event: Event) -> str:
    """``<nation> population <direction>: before -> after (residual <residual>)``; the residual excludes territory."""
    return (
        f"{subject_label(event)} population {attribute_text(event, 'direction')}: "
        f"{attribute_label(event, 'before')} -> {attribute_label(event, 'after')} "
        f"(residual {attribute_label(event, 'residual')})"
    )


def _pcgdp_trend(event: Event) -> str:
    """``<nation> per-capita GDP <boom|slump> at quarter <q>: before -> after``, over the trailing window."""
    return (
        f"{subject_label(event)} per-capita GDP {attribute_text(event, 'direction')} at quarter "
        f"{attribute_label(event, 'quarter')}: "
        f"{attribute_label(event, 'before')} -> {attribute_label(event, 'after')}"
    )


def _space_assets_changed(event: Event) -> str:
    """``<nation> <statistic> <growth|decline>: before -> after``; the territory share is evidence, not echoed."""
    return (
        f"{subject_label(event)} {attribute_text(event, 'statistic')} {attribute_text(event, 'direction')}: "
        f"{attribute_label(event, 'before')} -> {attribute_label(event, 'after')}"
    )


def _rank_changed(event: Event) -> str:
    """``<nation> <metric> rank: before -> after``; a side without a place is ``unranked``."""

    def rank(key: str) -> str:
        return "unranked" if event.attribute(key) is None else attribute_label(event, key)

    return (
        f"{subject_label(event)} {attribute_text(event, 'metric')} rank: {rank('before_rank')} -> {rank('after_rank')}"
    )


def _territory_gained(event: Event) -> str:
    return f"{subject_label(event)} gained {regions(event)} from {refs(event, 'counterparts')}"


def _territory_lost(event: Event) -> str:
    return f"{subject_label(event)} lost {regions(event)} to {refs(event, 'counterparts')}"


def _independence(event: Event) -> str:
    releaser = event.attribute("releasing_nation")
    if event.attribute("released") is True and isinstance(releaser, EntityRef):
        return f"{subject_label(event)} was released by {releaser.label()}"
    return f"{subject_label(event)} became independent of {refs(event, 'parents')}"


def _unification(event: Event) -> str:
    return f"{subject_label(event)} unified with {refs(event, 'unified')}"


def _annexation(event: Event) -> str:
    return f"{subject_label(event)} annexed {regions(event)} of {name(entity(event, EntityDomain.NATION))}"


ALTERNATIVES = "alternatives"
AMBIGUITY = frozenset({"ambiguous", ALTERNATIVES})
"""Added to every reading of a gainer that more than one interpretation fits."""

REGION_NATION_CHANGED = EventKind(
    "region.nation_changed",
    plain("nation"),
    Significance.MAJOR,
    EVIDENCE,
    required=TRANSITION,
    stake=Stake.TERRITORY,
)
CAPITAL_CHANGED = EventKind(
    "nation.capital_changed", plain("capital"), Significance.MINOR, BOOKKEEPING, required=TRANSITION
)
RELATION_CHANGED = EventKind(
    "nation.relation_changed",
    _relation_changed,
    Significance.MINOR,
    EVIDENCE,
    required=frozenset({"relation", "transition", "reciprocal"}),
    optional=frozenset({"listed_by"}),
    rule=Rule.RELATION_CHANGED,
    stake=Stake.BELLIGERENTS,
)
BREAKAWAY_PARENT_CHANGED = EventKind(
    "nation.breakaway_parent_changed", plain("breakaway parent"), Significance.MINOR, BOOKKEEPING, required=TRANSITION
)
EXECUTIVE_CHANGE_RECORDED = EventKind(
    "nation.executive_change_recorded",
    _executive_change,
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset({"new_executive", "recorded_on", "cause"}),
    optional=frozenset({"previous_executive", "previous_recorded_on", "previous_cause"}),
    rule=Rule.EXECUTIVE_CHANGE,
    stake=Stake.NATION,
)
APPEARED = EventKind(
    "nation.appeared",
    _presence,
    Significance.CAMPAIGN_DEFINING,
    BOOKKEEPING,
    required=frozenset({"side", "population"}),
    stake=Stake.NATION,
)
DISAPPEARED = EventKind(
    "nation.disappeared",
    _presence,
    Significance.CAMPAIGN_DEFINING,
    EVIDENCE,
    required=frozenset({"side", "population"}),
    stake=Stake.NATION,
)
CLAIMS_CHANGED = EventKind(
    "nation.claims_changed",
    _claims_changed("claims"),
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset(),
    optional=TRANSITION | {"added", "removed", "added_owners"},
    rule=Rule.CLAIMS_CHANGED,
    stake=Stake.NATION,
)
HOSTILE_CLAIMS_CHANGED = EventKind(
    "nation.hostile_claims_changed",
    _claims_changed("hostile claims"),
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset(),
    optional=TRANSITION | {"added", "removed", "added_owners"},
)
RENAMED = EventKind("nation.renamed", _renamed, Significance.MAJOR, EVIDENCE, required=TRANSITION)
UNREST_ATTEMPTS_CHANGED = EventKind(
    "nation.unrest_attempts_changed",
    _unrest_attempts_changed,
    Significance.MINOR,
    BOOKKEEPING,
    required=frozenset({"before", "after"}),
    optional=frozenset({"transition", "faction"}),
)
NEW_GOVERNMENT_RECORDED = EventKind(
    "nation.new_government_recorded",
    _new_government_recorded,
    Significance.MINOR,
    BOOKKEEPING,
    required=TRANSITION,
)
NUCLEAR_PROGRAM_CHANGED = EventKind(
    "nation.nuclear_program_changed", plain("nuclear program"), Significance.MINOR, EVIDENCE, required=TRANSITION
)
POLICY_CHANGED = EventKind(
    "nation.policy_changed",
    _policy_changed,
    Significance.MINOR,
    BOOKKEEPING,
    required=TRANSITION | {"policy"},
)

LIST_FIELDS = ("regions", "breakaways", "allies", "rivals")
"""The nation lists whose leftover members are events: the ones the nation analyzer handles."""


def _list_changed_kind(field: str) -> EventKind:
    return EventKind(
        f"nation.{field}_changed",
        list_changed,
        Significance.MINOR,
        BOOKKEEPING,
        required=frozenset({"transition"}),
        optional=frozenset({"member", "before", "after"}),
    )


LIST_CHANGED: Mapping[str, EventKind] = MappingProxyType({field: _list_changed_kind(field) for field in LIST_FIELDS})
"""The list-changed kind of each handled nation list, by the list's field name."""

BAND_CROSSED = EventKind(
    "nation.band_crossed",
    _band_crossed,
    Significance.TRIVIAL,
    EVIDENCE,
    required=frozenset(
        {"statistic", "before", "after", "from_band", "to_band", "bands_crossed", "margin", "interval_days"}
    ),
    optional=frozenset({"causes", "rest_value_share"}),
)
PCGDP_TREND = EventKind(
    "nation.pcgdp_trend",
    _pcgdp_trend,
    Significance.TRIVIAL,
    EVIDENCE,
    required=frozenset(
        {
            "direction",
            "quarter",
            "window_quarters",
            "window_start",
            "before",
            "after",
            "change",
            "before_sequence",
        }
    ),
)
STATISTIC_SHIFTED = EventKind(
    "nation.statistic_shifted",
    _statistic_shifted,
    Significance.MINOR,
    EVIDENCE,
    required=frozenset({"statistic", "before", "after", "relative_change", "interval_days"}),
    optional=frozenset({"causes", "key"}),
    rule=Rule.STATISTIC_SHIFTED,
    stake=Stake.NATION,
)
POPULATION_CHANGED = EventKind(
    "nation.population_changed",
    _population_changed,
    Significance.MINOR,
    EVIDENCE,
    required=frozenset(
        {"direction", "before", "after", "residual", "relative_change", "interval_days", "nuked_regions", "causes"}
    ),
    rule=Rule.POPULATION_CHANGED,
)
SPACE_ASSETS_CHANGED = EventKind(
    "nation.space_assets_changed",
    _space_assets_changed,
    Significance.MINOR,
    EVIDENCE,
    required=frozenset(
        {
            "statistic",
            "direction",
            "before",
            "after",
            "relative_change",
            "territory_delta",
            "territory_share",
            "regions_gained",
            "regions_lost",
            "interval_days",
        }
    ),
    rule=Rule.SPACE_ASSETS_CHANGED,
)
RANK_CHANGED = EventKind(
    "nation.rank_changed",
    _rank_changed,
    Significance.TRIVIAL,
    BOOKKEEPING,
    required=frozenset({"metric", "before_rank", "after_rank", "before", "after"}),
)

TERRITORY_GAINED = EventKind(
    "nation.territory_gained",
    _territory_gained,
    Significance.MINOR,
    EVIDENCE,
    required=frozenset({"regions", "region_count", "population", "counterparts", "territory_causes"}),
    stake=Stake.TERRITORY,
)
TERRITORY_LOST = EventKind(
    "nation.territory_lost",
    _territory_lost,
    Significance.MINOR,
    EVIDENCE,
    required=frozenset({"regions", "region_count", "population", "counterparts", "territory_causes"}),
    stake=Stake.TERRITORY,
)
INDEPENDENCE = EventKind(
    "nation.independence",
    _independence,
    Significance.MAJOR,
    EVIDENCE,
    required=frozenset({"parents", "signals", "independence_causes", "released"}),
    optional=frozenset({"release_causes", "releasing_nation", "releasing_basis", "releasing_executive_faction"})
    | AMBIGUITY,
    stake=Stake.TERRITORY,
)
UNIFICATION = EventKind(
    "nation.unification",
    _unification,
    Significance.MAJOR,
    EVIDENCE,
    required=frozenset({"unified", "unifying_faction", "bases", "executive_since"}),
    optional=AMBIGUITY,
    stake=Stake.TERRITORY,
)
ANNEXATION = EventKind(
    "nation.annexation",
    _annexation,
    Significance.MAJOR,
    EVIDENCE,
    required=frozenset({"regions", "region_count", "signals"}),
    optional=AMBIGUITY,
    stake=Stake.TERRITORY,
)

KINDS = (
    REGION_NATION_CHANGED,
    CAPITAL_CHANGED,
    RELATION_CHANGED,
    BREAKAWAY_PARENT_CHANGED,
    EXECUTIVE_CHANGE_RECORDED,
    APPEARED,
    DISAPPEARED,
    CLAIMS_CHANGED,
    HOSTILE_CLAIMS_CHANGED,
    RENAMED,
    UNREST_ATTEMPTS_CHANGED,
    NEW_GOVERNMENT_RECORDED,
    NUCLEAR_PROGRAM_CHANGED,
    POLICY_CHANGED,
    *LIST_CHANGED.values(),
    BAND_CROSSED,
    PCGDP_TREND,
    STATISTIC_SHIFTED,
    POPULATION_CHANGED,
    SPACE_ASSETS_CHANGED,
    RANK_CHANGED,
    TERRITORY_GAINED,
    TERRITORY_LOST,
    INDEPENDENCE,
    UNIFICATION,
    ANNEXATION,
)


# --- Narrative events ----------------------------------------------------------------------------------------------


def _expansion(event: Event) -> str:
    text = f"{role_label(event, Role.ACTOR)} expanded over {role_label(event, Role.TARGET)}: {regions(event)}"
    mode = event.attribute("mode")
    return f"{text} ({mode})" if isinstance(mode, str) else text


def _cession(event: Event) -> str:
    return f"{role_label(event, Role.ACTOR)} ceded {regions(event)} to {role_label(event, Role.BENEFICIARY)}"


def _merger(event: Event) -> str:
    text = f"{role_label(event, Role.ACTOR)} absorbed {role_label(event, Role.TARGET)} by unification"
    faction = event.attribute("unifying_faction")
    return f"{text} under {faction.label()}" if isinstance(faction, EntityRef) else text


def _release(event: Event) -> str:
    if has_role(event, Role.ACTOR):
        return f"{role_label(event, Role.ACTOR)} released {role_label(event, Role.BENEFICIARY)}"
    return f"{role_label(event, Role.BENEFICIARY)} was released by one of {refs(event, 'parents')}"


def _breakaway(event: Event) -> str:
    return f"{role_label(event, Role.ACTOR)} broke away from {role_label(event, Role.TARGET)}"


def _claims_declared(event: Event) -> str:
    return f"{role_label(event, Role.ACTOR)} claimed regions of {role_label(event, Role.TARGET)}"


def _band_shift(event: Event) -> str:
    return f"{role_label(event, Role.ACTOR)} {bands(event)}"


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
    return f"{role_label(event, Role.ACTOR)} established space defences ({region_count(event.attribute('regions'))})"


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
