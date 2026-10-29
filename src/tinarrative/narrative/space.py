"""The space narrative rules: campaigns, colonisation, milestones, fleet buildups. See architecture 11.3.

No rule names a motive: a campaign is the pair's own recorded losses and combats.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from ..config import SpaceSettings
from ..model.entities import EntityId, EntityRef
from ..model.events import DateBasis, Event, Role, Significance
from ..model.values import FrozenMap
from .aggregation import Join, NarrativeBuilder
from .chronology import interval_of
from .milestones import PROJECT_COMPLETED, TECHNOLOGY_COMPLETED, completed_template, milestone_of
from .rulekit import (
    anchored,
    by_type,
    chained,
    earliest,
    intervals_of,
    last_date,
    latest,
    overlaps,
    ref_attribute,
    refs_attribute,
    subject,
    subject_id,
    unique_refs,
    within,
)
from .situation import SituationReport

SPACE_CAMPAIGN = "faction.space_campaign"
COLONISATION_WAVE = "faction.colonisation_wave"
FIRST_MILESTONE = "campaign.first_milestone"
FLEET_BUILDUP = "faction.fleet_buildup"
TECHNOLOGY_MILESTONE = "technology.milestone"

BATTLE_OUTCOME = "faction.battle_outcome"
HAB_DESTROYED = "hab.destroyed"
DESTRUCTION_RECORDED = "faction.hab_destruction_recorded"
COMBAT_RECORDED = "faction.combat_recorded"
BATTLE_NOTIFICATION = "notification.LogSpaceBattleTakesPlace"
FLEET_DISAPPEARED = "fleet.disappeared"
FIRST_HAB_ON_BODY = "faction.first_hab_on_body"
HAB_APPEARED = "hab.appeared"
GLOBAL_MILESTONE = "campaign.global_milestone_recorded"
TRANSACTION = "faction.transaction_recorded"
SHIP_APPEARED = "ship.appeared"
MILESTONE_LEDGER_LABEL = "Global Milestone"
SHIP_LEDGER_LABEL = "Ship Construction"


def _kind(event: Event, ref: EntityRef) -> str | None:
    kinds = event.attribute("faction_kinds")
    if isinstance(kinds, FrozenMap):
        value = dict(kinds.items).get(str(ref.entity_id))
        return value if isinstance(value, str) else None
    return None


def _dedupe(events: Sequence[Event]) -> list[Event]:
    seen: dict[str, Event] = {}
    for event in events:
        seen.setdefault(event.id, event)
    return list(seen.values())


def _ledger(stream: Sequence[Event], label: str, faction: EntityId, low: str | None, high: str | None) -> list[Event]:
    """Empty unless no other faction carries ``label`` in the window (architecture 11.3, bound 4)."""
    labelled = [
        event
        for event in by_type(stream, TRANSACTION)
        if event.attribute("label") == label and overlaps(event, low, high)
    ]
    candidates = {key for key in map(subject_id, labelled) if key is not None}
    return labelled if candidates == {faction} else []


@dataclass(frozen=True)
class SpaceCampaignRule:
    """``faction.space_campaign``: one faction's recorded space fighting against another, over several intervals.

    Counts are summed from the outcomes, never recounted from the attached events, so nothing is counted twice. An
    ambiguous ``hab.destroyed`` is left out: its destroyer is unsure. The two campaigns of a pair share their combats
    and name each other in ``mirror``.
    """

    settings: SpaceSettings
    name: str = SPACE_CAMPAIGN
    order: int = 0

    @property
    def window_days(self) -> int:
        return self.settings.campaign_gap_days

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        pairs: dict[tuple[EntityId, EntityId], list[Event]] = {}
        for outcome in by_type(stream, BATTLE_OUTCOME):
            victim = ref_attribute(outcome, "victim")
            killer = subject(outcome)
            if killer is not None and victim is not None:
                pairs.setdefault((killer.entity_id, victim.entity_id), []).append(outcome)
        built: list[tuple[tuple[EntityId, EntityId], Event]] = []
        for pair in sorted(pairs, key=lambda item: (item[0].sort_key, item[1].sort_key)):
            for run in chained(pairs[pair], self.settings.campaign_gap_days):
                built.append((pair, self._campaign(stream, situations, build, pair, run)))
        return [_with_mirror(event, pair, built) for pair, event in built]

    def _campaign(
        self,
        stream: Sequence[Event],
        situations: Sequence[SituationReport],
        build: NarrativeBuilder,
        pair: tuple[EntityId, EntityId],
        run: list[Event],
    ) -> Event:
        killer_id, victim_id = pair
        killer = run[0].entities[0]
        victim = ref_attribute(run[0], "victim")
        assert victim is not None
        keys = set(intervals_of(run))

        def here(event: Event) -> bool:
            return interval_of(event.id) in keys

        habs = [
            event
            for event in by_type(stream, HAB_DESTROYED)
            if here(event)
            and event.attribute("ambiguous") is False
            and len(event.entities) > 3
            and event.entities[1].entity_id == victim_id
            and event.entities[3].entity_id == killer_id
        ]
        fleets = [
            event
            for event in by_type(stream, FLEET_DISAPPEARED)
            if here(event) and len(event.entities) > 1 and event.entities[1].entity_id == victim_id
        ]
        lost_fleets = {event.entities[0].entity_id for event in fleets}
        combats = [
            event
            for event in by_type(stream, COMBAT_RECORDED)
            if here(event) and {killer_id, victim_id} <= _side_ids(event)
        ]
        notices = [
            event
            for event in by_type(stream, BATTLE_NOTIFICATION)
            if here(event)
            and (
                any(
                    isinstance(ref, EntityRef) and ref.entity_id in lost_fleets for ref in (event.attribute("subject"),)
                )
                or any(ref.entity_id in pair for ref in event.entities)
            )
        ]
        cited = {constituent for outcome in run for constituent in outcome.constituents}
        entries = [event for event in by_type(stream, DESTRUCTION_RECORDED) if event.id in cited]
        constituents = _dedupe([*run, *habs, *entries, *combats, *notices, *fleets])
        located = [ref_attribute(hab, "body") for hab in habs] + [
            ref_attribute(entry, "space_body") for entry in entries
        ]
        bodies = unique_refs(ref for ref in located if ref is not None)
        start, end = earliest(run[0]), max((date for date in map(latest, run) if date), default=None)
        kind = _kind(run[0], victim)
        return build.event(
            SPACE_CAMPAIGN,
            id_parts=[killer_id, victim_id],
            constituents=constituents,
            roles=[(Role.ACTOR, killer), (Role.TARGET, victim), *((Role.BODY, body) for body in bodies)],
            join=Join.HEURISTIC,
            attributes=(
                ("victim_kind", kind),
                ("battles", len(run)),
                ("habs_lost", _total(run, "habs_lost")),
                ("fleets_lost", _total(run, "fleets_lost")),
                ("combats_won", _total(run, "combats_won")),
                ("combats_lost", _total(run, "combats_lost")),
                ("bodies", bodies),
                ("span_from", start),
                ("span_to", end),
            ),
            significance=Significance.MAJOR,
            open=within(end, last_date(situations), self.settings.campaign_gap_days),
        )


def _with_mirror(
    campaign: Event, pair: tuple[EntityId, EntityId], built: Sequence[tuple[tuple[EntityId, EntityId], Event]]
) -> Event:
    combats = {cid for cid in campaign.constituents if cid.startswith(f"{COMBAT_RECORDED}/")}
    for other_pair, other in built:
        if other_pair == (pair[1], pair[0]) and combats & set(other.constituents):
            return replace(campaign, attributes=(*campaign.attributes, ("mirror", other.id)))
    return campaign


def _side_ids(event: Event) -> set[EntityId]:
    sides = event.attribute("sides")
    found: set[EntityId] = set()
    if isinstance(sides, tuple):
        for side in sides:
            if isinstance(side, tuple) and side and isinstance(side[0], EntityRef):
                found.add(side[0].entity_id)
    return found


def _total(events: Sequence[Event], name: str) -> int:
    return sum(
        value for value in (event.attribute(name) for event in events) if isinstance(value, int) and value is not True
    )


@dataclass(frozen=True)
class ColonisationWaveRule:
    """``faction.colonisation_wave``: a faction reached two or more new bodies close together."""

    settings: SpaceSettings
    name: str = COLONISATION_WAVE
    order: int = 0

    @property
    def window_days(self) -> int:
        return self.settings.colonisation_window_days

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        by_faction: dict[EntityId, list[Event]] = {}
        for event in by_type(stream, FIRST_HAB_ON_BODY):
            key = subject_id(event)
            if key is not None:
                by_faction.setdefault(key, []).append(event)
        appeared = by_type(stream, HAB_APPEARED)
        days = self.settings.colonisation_window_days
        built = []
        for faction_id in sorted(by_faction, key=lambda item: item.sort_key):
            for run in anchored(by_faction[faction_id], days):
                body_refs = [ref for ref in (ref_attribute(event, "body") for event in run) if ref is not None]
                if len({ref.entity_id for ref in body_refs}) < 2:
                    continue
                habs = {ref.entity_id for event in run for ref in refs_attribute(event, "habs")}
                keys = set(intervals_of(run))
                attached = [event for event in appeared if subject_id(event) in habs and interval_of(event.id) in keys]
                faction = run[0].entities[0]
                built.append(
                    build.event(
                        COLONISATION_WAVE,
                        id_parts=[faction_id],
                        constituents=_dedupe([*run, *attached]),
                        roles=[(Role.ACTOR, faction), *((Role.BODY, ref) for ref in body_refs)],
                        join=Join.ENTITY,
                        attributes=(
                            ("bodies", tuple(body_refs)),
                            ("hab_count", _total(run, "hab_count")),
                            (
                                "first_of_any_faction",
                                tuple(event.attribute("first_of_any_faction") is True for event in run),
                            ),
                        ),
                        significance=Significance.MAJOR,
                        open=within(latest(run[0]), last_date(situations), days),
                    )
                )
        return built


@dataclass(frozen=True)
class FirstMilestoneRule:
    """``campaign.first_milestone``: a campaign-wide first, dated by the ledger when that is unambiguous."""

    settings: SpaceSettings
    name: str = FIRST_MILESTONE
    order: int = 0

    @property
    def window_days(self) -> None:
        return None

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        built = []
        for anchor in by_type(stream, GLOBAL_MILESTONE):
            faction = ref_attribute(anchor, "faction")
            charges: list[Event] = []
            if faction is not None:
                same = [
                    event for event in by_type(stream, TRANSACTION) if interval_of(event.id) == interval_of(anchor.id)
                ]
                charges = _ledger(same, MILESTONE_LEDGER_LABEL, faction.entity_id, earliest(anchor), latest(anchor))
            roles = [(Role.ACTOR, faction)] if faction is not None else []
            event = build.event(
                FIRST_MILESTONE,
                id_parts=[anchor.entities[0].entity_id if anchor.entities else "", anchor.attribute("milestone")],
                constituents=[anchor, *charges],
                roles=roles,
                join=Join.ENTITY,
                attributes=(("milestone", anchor.attribute("milestone")), ("faction", faction)),
                significance=Significance.CAMPAIGN_DEFINING,
                open=False,
            )
            dates = [charge.date for charge in charges if charge.date_basis is DateBasis.RECORD]
            if dates and isinstance(dates[0], str) and len(set(dates)) == 1:
                event = replace(
                    event, date=dates[0], date_basis=DateBasis.RECORD, end=dates[0], end_basis=DateBasis.RECORD
                )
            built.append(event)
        return built


@dataclass(frozen=True)
class FleetBuildupRule:
    """``faction.fleet_buildup``: a faction put several ships of one hull into service in one interval."""

    settings: SpaceSettings
    name: str = FLEET_BUILDUP
    order: int = 0

    @property
    def window_days(self) -> None:
        return None

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        groups: dict[tuple[str, EntityId, str], list[Event]] = {}
        for ship in by_type(stream, SHIP_APPEARED):
            hull = ship.attribute("hull")
            owner = ship.entities[2] if len(ship.entities) > 2 else None
            if isinstance(hull, str) and owner is not None:
                groups.setdefault((interval_of(ship.id), owner.entity_id, hull), []).append(ship)
        built = []
        for key in sorted(groups, key=lambda item: (item[0], item[1].sort_key, item[2])):
            ships = groups[key]
            if len(ships) < self.settings.buildup_min_ships:
                continue
            key_interval, owner_id, hull = key
            charges = _ledger(
                [event for event in by_type(stream, TRANSACTION) if interval_of(event.id) == key_interval],
                SHIP_LEDGER_LABEL,
                owner_id,
                earliest(ships[0]),
                latest(ships[0]),
            )
            built.append(
                build.event(
                    FLEET_BUILDUP,
                    id_parts=[owner_id, hull],
                    constituents=[*ships, *charges],
                    roles=[(Role.ACTOR, ships[0].entities[2])],
                    join=Join.ENTITY,
                    attributes=(("hull", hull), ("count", len(ships))),
                    significance=Significance.MINOR,
                    open=False,
                )
            )
        return built


@dataclass(frozen=True)
class TechnologyMilestoneRule:
    """``technology.milestone``: a completion whose template name is in ``MILESTONE_TEMPLATES``, at its tier.

    A technology is campaign-wide, so it has no actor; a project's faction is part of the identity, as factions
    complete projects independently.
    """

    settings: SpaceSettings
    name: str = TECHNOLOGY_MILESTONE
    order: int = 0

    @property
    def window_days(self) -> None:
        return None

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        built = []
        for event in by_type(stream, TECHNOLOGY_COMPLETED, PROJECT_COMPLETED):
            ref, milestone, name = subject(event), milestone_of(event), completed_template(event)
            if ref is None or milestone is None or name is None:
                continue
            is_project = event.event_type == PROJECT_COMPLETED
            built.append(
                build.event(
                    TECHNOLOGY_MILESTONE,
                    id_parts=[event.event_type, *([ref.entity_id] if is_project else []), name],
                    constituents=[event],
                    roles=[(Role.ACTOR, ref)] if is_project else [],
                    join=Join.ENTITY,
                    attributes=(("template", name), ("rationale", milestone.rationale)),
                    significance=milestone.significance,
                    open=False,
                )
            )
        return built


def space_rules(
    settings: SpaceSettings,
) -> tuple[SpaceCampaignRule, ColonisationWaveRule, FirstMilestoneRule, FleetBuildupRule, TechnologyMilestoneRule]:
    return (
        SpaceCampaignRule(settings),
        ColonisationWaveRule(settings),
        FirstMilestoneRule(settings),
        FleetBuildupRule(settings),
        TechnologyMilestoneRule(settings),
    )
