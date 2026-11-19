"""The space narrative rules: campaigns, colonisation, milestones, fleet buildups.

No rule names a motive: a campaign is the pair's own recorded losses and combats.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from itertools import combinations

from ..config import SpaceSettings
from ..kinds import campaign as campaign_kinds
from ..kinds import space as space_kinds
from ..kinds.faction import TRANSACTION_RECORDED
from ..kinds.space import (
    FACTION_COMBAT_RECORDED,
    FACTION_FIRST_HAB_ON_BODY,
    FACTION_SPACE_LOSSES,
)
from ..kinds.space import (
    HAB_DESTROYED as HAB_DESTROYED_KIND,
)
from ..kinds.space import (
    HAB_ESTABLISHED as HAB_ESTABLISHED_KIND,
)
from ..kinds.space import (
    SHIP_APPEARED as SHIP_APPEARED_KIND,
)
from ..kinds.technology import MILESTONE as TECHNOLOGY_MILESTONE_KIND
from ..model.entities import EntityId, EntityRef
from ..model.events import DateBasis, Event, Role
from ..model.values import FrozenMap
from .aggregation import Join, NarrativeBuilder
from .chronology import interval_of
from .milestones import PROJECT_COMPLETED, TECHNOLOGY_COMPLETED, completed_template, milestone_of
from .rulekit import (
    Run,
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
from .stream import EventStream

SPACE_CAMPAIGN = space_kinds.SPACE_CAMPAIGN.event_type
COLONISATION_WAVE = space_kinds.COLONISATION_WAVE.event_type
FIRST_MILESTONE = campaign_kinds.FIRST_MILESTONE.event_type
FLEET_BUILDUP = space_kinds.FLEET_BUILDUP.event_type
TECHNOLOGY_MILESTONE = TECHNOLOGY_MILESTONE_KIND.event_type

SPACE_LOSSES = FACTION_SPACE_LOSSES.event_type
HAB_DESTROYED = HAB_DESTROYED_KIND.event_type
COMBAT_RECORDED = FACTION_COMBAT_RECORDED.event_type
FIRST_HAB_ON_BODY = FACTION_FIRST_HAB_ON_BODY.event_type
HAB_ESTABLISHED = HAB_ESTABLISHED_KIND.event_type
GLOBAL_MILESTONE = campaign_kinds.GLOBAL_MILESTONE_RECORDED.event_type
TRANSACTION = TRANSACTION_RECORDED.event_type
SHIP_APPEARED = SHIP_APPEARED_KIND.event_type
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
    """Empty unless no other faction carries ``label`` in the window (ADR-0010, bound 4)."""
    labelled = [
        event
        for event in by_type(stream, TRANSACTION)
        if event.attribute("label") == label and overlaps(event, low, high)
    ]
    candidates = {key for key in map(subject_id, labelled) if key is not None}
    return labelled if candidates == {faction} else []


@dataclass(frozen=True)
class SpaceCampaignRule:
    """``faction.space_campaign``: two factions' space losses of either direction and their recorded combats, over
    several intervals (ADR-0023).

    One campaign per unordered pair. Counts are summed from the events it cites, each told once.
    """

    settings: SpaceSettings
    name: str = SPACE_CAMPAIGN
    emitted_types: frozenset[str] = frozenset({SPACE_CAMPAIGN})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()

    @property
    def window_days(self) -> int:
        return self.settings.campaign_gap_days

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        pairs: dict[tuple[EntityId, EntityId], list[Event]] = {}
        refs: dict[EntityId, EntityRef] = {}
        for losses in by_type(stream, SPACE_LOSSES):
            victim, destroyer = ref_attribute(losses, "victim"), subject(losses)
            if victim is not None and destroyer is not None:
                refs.update({victim.entity_id: victim, destroyer.entity_id: destroyer})
                pairs.setdefault(_pair(destroyer.entity_id, victim.entity_id), []).append(losses)
        for combat in by_type(stream, COMBAT_RECORDED):
            for side in _side_refs(combat):
                refs.setdefault(side.entity_id, side)
            for first, second in combinations(sorted(_side_ids(combat), key=lambda item: item.sort_key), 2):
                pairs.setdefault((first, second), []).append(combat)
        built = []
        for pair in sorted(pairs, key=lambda item: (item[0].sort_key, item[1].sort_key)):
            for run in chained(pairs[pair], self.settings.campaign_gap_days):
                built.append(self._campaign(stream, situations, build, pair, run, refs))
        return built

    def _campaign(
        self,
        stream: EventStream,
        situations: Sequence[SituationReport],
        build: NarrativeBuilder,
        pair: tuple[EntityId, EntityId],
        run: Run,
        refs: dict[EntityId, EntityRef],
    ) -> Event:
        losses = [event for event in run if event.event_type == SPACE_LOSSES]
        combats = [event for event in run if event.event_type == COMBAT_RECORDED]
        sides = tuple(refs[entity_id] for entity_id in pair)
        lost = [[event for event in losses if _victim_id(event) == entity_id] for entity_id in pair]
        tied = {ref.entity_id for event in losses for ref in refs_attribute(event, "habs")}
        keys = set(intervals_of(run))
        located = [
            ref_attribute(hab, "body")
            for hab in stream.in_intervals(keys, HAB_DESTROYED)
            if hab.attribute("ambiguous") is False and hab.entities and hab.entities[0].entity_id in tied
        ]
        bodies = unique_refs(ref for ref in located if ref is not None)
        start, end = earliest(run[0]), max((date for date in map(latest, run) if date), default=None)
        return build.event(
            space_kinds.SPACE_CAMPAIGN,
            id_parts=[*pair, *run.discriminator],
            constituents=list(run),
            roles=[*((Role.SIDE, side) for side in sides), *((Role.BODY, body) for body in bodies)],
            join=Join.HEURISTIC,
            attributes=(
                ("sides", sides),
                ("alien", tuple(_alien(run, side) for side in sides)),
                ("ships_lost", tuple(_total(events, "ships_lost") for events in lost)),
                ("habs_lost", tuple(_total(events, "habs_lost") for events in lost)),
                ("combats", len(combats)),
                ("combats_won", tuple(sum(_winner(event) == entity_id for event in combats) for entity_id in pair)),
                ("bodies", bodies),
                ("span_from", start),
                ("span_to", end),
            ),
            open=within(end, last_date(situations), self.settings.campaign_gap_days),
        )


def _pair(first: EntityId, second: EntityId) -> tuple[EntityId, EntityId]:
    return (first, second) if first.sort_key <= second.sort_key else (second, first)


def _victim_id(event: Event) -> EntityId | None:
    victim = ref_attribute(event, "victim")
    return victim.entity_id if victim is not None else None


def _winner(event: Event) -> EntityId | None:
    winner = ref_attribute(event, "winner")
    return winner.entity_id if winner is not None else None


def _alien(run: Sequence[Event], side: EntityRef) -> bool:
    return any(_kind(event, side) == "alien" for event in run)


def _side_refs(event: Event) -> list[EntityRef]:
    sides = event.attribute("sides")
    found: list[EntityRef] = []
    if isinstance(sides, tuple):
        for side in sides:
            if isinstance(side, tuple) and side and isinstance(side[0], EntityRef):
                found.append(side[0])
    return found


def _side_ids(event: Event) -> set[EntityId]:
    return {ref.entity_id for ref in _side_refs(event)}


def _total(events: Sequence[Event], name: str) -> int:
    return sum(
        value for value in (event.attribute(name) for event in events) if isinstance(value, int) and value is not True
    )


@dataclass(frozen=True)
class ColonisationWaveRule:
    """``faction.colonisation_wave``: a faction reached two or more new bodies close together."""

    settings: SpaceSettings
    name: str = COLONISATION_WAVE
    emitted_types: frozenset[str] = frozenset({COLONISATION_WAVE})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()

    @property
    def window_days(self) -> int:
        return self.settings.colonisation_window_days

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        by_faction: dict[EntityId, list[Event]] = {}
        for event in by_type(stream, FIRST_HAB_ON_BODY):
            key = subject_id(event)
            if key is not None:
                by_faction.setdefault(key, []).append(event)
        established = by_type(stream, HAB_ESTABLISHED)
        days = self.settings.colonisation_window_days
        built = []
        for faction_id in sorted(by_faction, key=lambda item: item.sort_key):
            for run in anchored(by_faction[faction_id], days):
                body_refs = [ref for ref in (ref_attribute(event, "body") for event in run) if ref is not None]
                if len({ref.entity_id for ref in body_refs}) < 2:
                    continue
                habs = {ref.entity_id for event in run for ref in refs_attribute(event, "habs")}
                keys = set(intervals_of(run))
                attached = [
                    event for event in established if subject_id(event) in habs and interval_of(event.id) in keys
                ]
                faction = run[0].entities[0]
                built.append(
                    build.event(
                        space_kinds.COLONISATION_WAVE,
                        id_parts=[faction_id, *run.discriminator],
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
                        open=within(latest(run[0]), last_date(situations), days),
                    )
                )
        return built


@dataclass(frozen=True)
class FirstMilestoneRule:
    """``campaign.first_milestone``: a campaign-wide first, dated by the ledger when that is unambiguous."""

    settings: SpaceSettings
    name: str = FIRST_MILESTONE
    emitted_types: frozenset[str] = frozenset({FIRST_MILESTONE})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()

    @property
    def window_days(self) -> None:
        return None

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        built = []
        for anchor in by_type(stream, GLOBAL_MILESTONE):
            faction = ref_attribute(anchor, "faction")
            charges: list[Event] = []
            if faction is not None:
                same = stream.in_intervals(interval_of(anchor.id), TRANSACTION)
                charges = _ledger(same, MILESTONE_LEDGER_LABEL, faction.entity_id, earliest(anchor), latest(anchor))
            roles = [(Role.ACTOR, faction)] if faction is not None else []
            event = build.event(
                campaign_kinds.FIRST_MILESTONE,
                id_parts=[anchor.entities[0].entity_id if anchor.entities else "", anchor.attribute("milestone")],
                constituents=[anchor, *charges],
                roles=roles,
                join=Join.ENTITY,
                attributes=(("milestone", anchor.attribute("milestone")), ("faction", faction)),
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
    emitted_types: frozenset[str] = frozenset({FLEET_BUILDUP})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()

    @property
    def window_days(self) -> None:
        return None

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
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
                stream.in_intervals(key_interval, TRANSACTION),
                SHIP_LEDGER_LABEL,
                owner_id,
                earliest(ships[0]),
                latest(ships[0]),
            )
            built.append(
                build.event(
                    space_kinds.FLEET_BUILDUP,
                    id_parts=[owner_id, hull],
                    constituents=[*ships, *charges],
                    roles=[(Role.ACTOR, ships[0].entities[2])],
                    join=Join.ENTITY,
                    attributes=(("hull", hull), ("count", len(ships))),
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
    emitted_types: frozenset[str] = frozenset({TECHNOLOGY_MILESTONE})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()

    @property
    def window_days(self) -> None:
        return None

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        built = []
        for event in by_type(stream, TECHNOLOGY_COMPLETED, PROJECT_COMPLETED):
            ref, milestone, name = subject(event), milestone_of(event), completed_template(event)
            if ref is None or milestone is None or name is None:
                continue
            is_project = event.event_type == PROJECT_COMPLETED
            built.append(
                build.event(
                    TECHNOLOGY_MILESTONE_KIND,
                    id_parts=[event.event_type, *([ref.entity_id] if is_project else []), name],
                    constituents=[event],
                    roles=[(Role.ACTOR, ref)] if is_project else [],
                    join=Join.ENTITY,
                    attributes=(("template", name), ("rationale", milestone.rationale)),
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
