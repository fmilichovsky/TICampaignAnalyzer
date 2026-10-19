"""Situation reports: the deterministic digest of one snapshot that narrative rules and the narrator read as context.

A report is read from one snapshot alone and is snapshot-dated evidence, not an event (architecture 11.4). It holds
literal values and counts, never a reading:

- per nation: the faction holding the executive seat (the control point at ``positionInNation`` 0), the points held
  per faction, the federation, the allies, the wars it is a party to (from the wars' alliances), the region count,
  the summed region population and the regime statistics as literal values. Which faction *controls* a nation is
  never stated; that is inference (``reconstruction.control``);
- federations with members; wars with both leaders, both alliances, ``startDate`` and ``dateOfLastFighting``;
- per faction: habs in total and per body (the hab's ``barycenter``), fleets (by the fleet's ``faction``), ships (by
  the ship's ``fleet``) and finished projects (entries of ``finishedProjectNames``, repeats counted);
- habs, fleets and ships that no faction of the snapshot owns, counted rather than dropped;
- campaign-wide: the nation count (all nation states, and those holding regions), total population, finished
  technologies (research is one campaign-wide state in the model, so this count is not per faction), the global
  milestones, the nuclear and the climate counters, and the player's faction name from the campaign metadata.

A value the snapshot does not establish stays ``Unknown``; it is never reported as zero or empty. Every list is in
the snapshot's entity order (``EntityId.sort_key``) or the serialized order of its record.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from ..analyzers.campaign.global_values import MILESTONES, NUCLEAR_STRIKES, SEA_LEVEL_RISES
from ..analyzers.common import Lookup, Side
from ..analyzers.politics.wars import ATTACKERS, DEFENDERS, LAST_FIGHTING, START_DATE
from ..log import fields, get_logger
from ..model.entities import EntityId, EntityRef
from ..model.records import ItemEntry, KeyedEntry
from ..model.snapshot import EntityState, SaveSnapshot
from ..model.values import FrozenMap, Observed, Unknown, UnknownReason, to_jsonable
from ..reconstruction.common import control_points, executive_seat
from ..reconstruction.control import Holder

logger = get_logger(__name__)

STATISTICS = ("democracy", "cohesion", "unrest", "inequality", "GDP", "spaceFunding_year")
"""The nation fields reported literally as regime statistics."""
NUCLEAR_COUNTERS = (NUCLEAR_STRIKES, "looseNukes", "currentNuclearExchanges")
CLIMATE_COUNTERS = (
    "earthAtmosphericCO2_ppm",
    "earthAtmosphericCH4_ppm",
    "earthAtmosphericN2O_ppm",
    "stratosphericAerosols_ppm",
    "globalSeaLevelAnomaly_cm",
    *SEA_LEVEL_RISES,
)
"""The global-values fields reported literally as nuclear and climate counters."""

Count = int | Unknown


def _named(values: tuple[tuple[str, Observed], ...]) -> dict[str, Any]:
    return {name: to_jsonable(value) for name, value in values}


@dataclass(frozen=True)
class WarParty:
    """A war a nation is listed in, and on which side (``attacker`` or ``defender``)."""

    war: EntityRef
    side: str

    def to_dict(self) -> dict[str, Any]:
        return {"war": to_jsonable(self.war), "side": self.side}


@dataclass(frozen=True)
class NationSituation:
    """One nation: who holds its executive seat and how many points each faction holds, never who controls it."""

    nation: EntityRef
    executive: Holder
    control_points: Count
    shares: FrozenMap | Unknown
    """Points held per faction, keyed by the faction's ID text; uncontrolled and unresolved points are not keys."""
    unresolved_points: Count
    federation: Observed
    allies: Observed
    """The nation's ``allies`` list, as references with their names."""
    wars: tuple[WarParty, ...]
    regions: Count
    population: Observed
    statistics: tuple[tuple[str, Observed], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nation": to_jsonable(self.nation),
            "executive": to_jsonable(self.executive),
            "control_points": to_jsonable(self.control_points),
            "shares": to_jsonable(self.shares),
            "unresolved_points": to_jsonable(self.unresolved_points),
            "federation": to_jsonable(self.federation),
            "allies": to_jsonable(self.allies),
            "wars": [party.to_dict() for party in self.wars],
            "regions": to_jsonable(self.regions),
            "population": to_jsonable(self.population),
            "statistics": _named(self.statistics),
        }


@dataclass(frozen=True)
class FederationSituation:
    federation: EntityRef
    name: Observed
    members: Observed

    def to_dict(self) -> dict[str, Any]:
        return {
            "federation": to_jsonable(self.federation),
            "name": to_jsonable(self.name),
            "members": to_jsonable(self.members),
        }


@dataclass(frozen=True)
class WarSituation:
    war: EntityRef
    attacker: Observed
    defender: Observed
    attacking_alliance: Observed
    defending_alliance: Observed
    start_date: Observed
    last_fighting: Observed

    def to_dict(self) -> dict[str, Any]:
        return {
            "war": to_jsonable(self.war),
            "attacker": to_jsonable(self.attacker),
            "defender": to_jsonable(self.defender),
            "attacking_alliance": to_jsonable(self.attacking_alliance),
            "defending_alliance": to_jsonable(self.defending_alliance),
            "start_date": to_jsonable(self.start_date),
            "last_fighting": to_jsonable(self.last_fighting),
        }


@dataclass(frozen=True)
class BodyHabs:
    body: EntityRef
    habs: int

    def to_dict(self) -> dict[str, Any]:
        return {"body": to_jsonable(self.body), "habs": self.habs}


@dataclass(frozen=True)
class FactionSituation:
    """One faction's holdings; ``habs`` counts every hab it owns, ``habs_by_body`` only those with a known body."""

    faction: EntityRef
    kind: str | None
    """``alien`` or ``human`` by the faction's ``templateName``; ``None`` when it has none."""
    habs: int
    habs_by_body: tuple[BodyHabs, ...]
    fleets: int
    ships: int
    finished_projects: Count

    def to_dict(self) -> dict[str, Any]:
        return {
            "faction": to_jsonable(self.faction),
            "kind": self.kind,
            "habs": self.habs,
            "habs_by_body": [entry.to_dict() for entry in self.habs_by_body],
            "fleets": self.fleets,
            "ships": self.ships,
            "finished_projects": to_jsonable(self.finished_projects),
        }


@dataclass(frozen=True)
class Unattributed:
    """Habs, fleets and ships whose owner is ``null``, unresolved or not a faction of the snapshot."""

    habs: int
    fleets: int
    ships: int

    def to_dict(self) -> dict[str, Any]:
        return {"habs": self.habs, "fleets": self.fleets, "ships": self.ships}


@dataclass(frozen=True)
class Milestone:
    milestone: Observed
    faction: Observed

    def to_dict(self) -> dict[str, Any]:
        return {"milestone": to_jsonable(self.milestone), "faction": to_jsonable(self.faction)}


@dataclass(frozen=True)
class WorldSituation:
    """Campaign-wide counts and counters."""

    nations: int
    nations_with_regions: Count
    """Nations whose region list is known and not empty; unknown when any nation's list is unknown."""
    population: Observed
    finished_technologies: Count
    milestones: tuple[Milestone, ...] | Unknown
    nuclear: tuple[tuple[str, Observed], ...]
    climate: tuple[tuple[str, Observed], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nations": self.nations,
            "nations_with_regions": to_jsonable(self.nations_with_regions),
            "population": to_jsonable(self.population),
            "finished_technologies": to_jsonable(self.finished_technologies),
            "milestones": to_jsonable(self.milestones)
            if isinstance(self.milestones, Unknown)
            else [milestone.to_dict() for milestone in self.milestones],
            "nuclear": _named(self.nuclear),
            "climate": _named(self.climate),
        }


@dataclass(frozen=True)
class SituationReport:
    """The digest of one snapshot (see the module docstring); ``date`` is the snapshot's game date."""

    date: Observed
    player_faction_name: Observed
    nations: tuple[NationSituation, ...]
    federations: tuple[FederationSituation, ...]
    wars: tuple[WarSituation, ...]
    factions: tuple[FactionSituation, ...]
    unattributed: Unattributed
    world: WorldSituation

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": to_jsonable(self.date),
            "player_faction_name": to_jsonable(self.player_faction_name),
            "nations": [nation.to_dict() for nation in self.nations],
            "federations": [federation.to_dict() for federation in self.federations],
            "wars": [war.to_dict() for war in self.wars],
            "factions": [faction.to_dict() for faction in self.factions],
            "unattributed": self.unattributed.to_dict(),
            "world": self.world.to_dict(),
        }


class _Reader:
    """The snapshot's lookups, read on one side only."""

    def __init__(self, snapshot: SaveSnapshot) -> None:
        self.snapshot = snapshot
        self.lookup = Lookup(snapshot, snapshot)

    def state(self, entity_id: EntityId) -> EntityState | None:
        return self.lookup.state(entity_id, Side.AFTER)

    def resolved(self, value: Observed) -> Observed:
        """A reference (or a list of them) with the entity's own name; any other value unchanged."""
        if isinstance(value, EntityRef):
            return self.lookup.resolve(value)
        if isinstance(value, tuple):
            return tuple(self.resolved(item) for item in value)  # type: ignore[misc]
        return value

    def controller(self, point: EntityId) -> Holder:
        state = self.state(point)
        faction = state.get("faction") if state is not None else Unknown(UnknownReason.UNRESOLVED_REFERENCE)
        if faction is None:
            return None
        if isinstance(faction, EntityRef):
            return self.lookup.resolve(faction)
        return faction if isinstance(faction, Unknown) else Unknown(UnknownReason.UNPARSEABLE)

    def owner(self, state: EntityState) -> EntityId | None:
        """The faction ``state`` names in its ``faction`` field, if that faction is in the snapshot."""
        faction = state.get("faction")
        if isinstance(faction, EntityRef) and self.state(faction.entity_id) is not None:
            return faction.entity_id
        return None

    def population(self, regions: Iterable[EntityId]) -> Observed:
        return self.lookup.population(regions, Side.AFTER)


def _count(value: Observed) -> Count:
    """The length of a known list; the ``Unknown`` itself, or ``unparseable`` for a value that is not a list."""
    if isinstance(value, tuple):
        return len(value)
    return value if isinstance(value, Unknown) else Unknown(UnknownReason.UNPARSEABLE)


def _war_parties(snapshot: SaveSnapshot) -> dict[EntityId, list[WarParty]]:
    parties: dict[EntityId, list[WarParty]] = defaultdict(list)
    for war in snapshot.wars:
        for side in (ATTACKERS, DEFENDERS):
            members = war.get(side.alliance)
            for member in members if isinstance(members, tuple) else ():
                if isinstance(member, EntityRef):
                    parties[member.entity_id].append(WarParty(war.ref, side.leader))
    return parties


def _nation(reader: _Reader, state: EntityState, wars: list[WarParty]) -> NationSituation:
    nation_id = state.ref.entity_id
    points = control_points(reader.lookup, nation_id, Side.AFTER)
    executive: Holder
    count: Count
    shares: FrozenMap | Unknown
    unresolved: Count
    if points is None:
        missing = state.get("controlPoints")
        executive = count = shares = unresolved = (
            missing if isinstance(missing, Unknown) else Unknown(UnknownReason.UNPARSEABLE)
        )
    else:
        controllers = [reader.controller(point.entity_id) for point in points]
        seat = executive_seat(reader.lookup, nation_id, Side.AFTER)
        if not points:
            executive = None
        elif seat is None:
            executive = Unknown()
        else:
            executive = reader.controller(seat.ref.entity_id)
        count = len(controllers)
        held = Counter(str(ref.entity_id) for ref in controllers if isinstance(ref, EntityRef))
        shares = FrozenMap(tuple(held.items()))
        unresolved = sum(isinstance(controller, Unknown) for controller in controllers)

    regions = state.get("regions")
    population = (
        reader.population(ref.entity_id for ref in regions if isinstance(ref, EntityRef))
        if isinstance(regions, tuple)
        else _count(regions)
    )
    return NationSituation(
        nation=state.ref,
        executive=executive,
        control_points=count,
        shares=shares,
        unresolved_points=unresolved,
        federation=reader.resolved(state.get("federation")),
        allies=reader.resolved(state.get("allies")),
        wars=tuple(sorted(wars, key=lambda party: (party.war.entity_id.sort_key, party.side))),
        regions=_count(regions),
        population=population,
        statistics=tuple((name, state.get(name)) for name in STATISTICS),
    )


def _date_record(reader: _Reader, war: EntityId, field: str) -> Observed:
    record_set = reader.lookup.record_set(war, field, Side.AFTER)
    if record_set is None:
        return Unknown()
    if isinstance(record_set.entries, Unknown):
        return record_set.entries
    if len(record_set.entries) != 1 or not isinstance(record_set.entries[0], ItemEntry):
        return Unknown(UnknownReason.UNPARSEABLE)
    return record_set.entries[0].value


def _war(reader: _Reader, state: EntityState) -> WarSituation:
    war_id = state.ref.entity_id
    return WarSituation(
        war=state.ref,
        attacker=reader.resolved(state.get(ATTACKERS.leader)),
        defender=reader.resolved(state.get(DEFENDERS.leader)),
        attacking_alliance=reader.resolved(state.get(ATTACKERS.alliance)),
        defending_alliance=reader.resolved(state.get(DEFENDERS.alliance)),
        start_date=_date_record(reader, war_id, START_DATE),
        last_fighting=_date_record(reader, war_id, LAST_FIGHTING),
    )


def _factions(reader: _Reader) -> tuple[tuple[FactionSituation, ...], Unattributed]:
    snapshot = reader.snapshot
    habs: Counter[EntityId] = Counter()
    bodies: dict[EntityId, Counter[EntityId]] = defaultdict(Counter)
    body_refs: dict[EntityId, EntityRef] = {}
    for hab in snapshot.habs:
        owner = reader.owner(hab)
        if owner is None:
            continue
        habs[owner] += 1
        body = reader.resolved(hab.get("barycenter"))
        if isinstance(body, EntityRef):
            bodies[owner][body.entity_id] += 1
            body_refs[body.entity_id] = body

    fleets: Counter[EntityId] = Counter()
    fleet_owner: dict[EntityId, EntityId] = {}
    for fleet in snapshot.fleets:
        owner = reader.owner(fleet)
        if owner is not None:
            fleets[owner] += 1
            fleet_owner[fleet.ref.entity_id] = owner

    ships: Counter[EntityId] = Counter()
    for ship in snapshot.ships:
        fleet_ref = ship.get("fleet")
        owner = fleet_owner.get(fleet_ref.entity_id) if isinstance(fleet_ref, EntityRef) else None
        if owner is not None:
            ships[owner] += 1

    factions = tuple(
        FactionSituation(
            faction=state.ref,
            kind=reader.lookup.faction_kind(state.ref.entity_id),
            habs=habs[state.ref.entity_id],
            habs_by_body=tuple(
                BodyHabs(body_refs[body], count)
                for body, count in sorted(bodies[state.ref.entity_id].items(), key=lambda item: item[0].sort_key)
            ),
            fleets=fleets[state.ref.entity_id],
            ships=ships[state.ref.entity_id],
            finished_projects=_count(state.get("finishedProjectNames")),
        )
        for state in snapshot.factions
    )
    unattributed = Unattributed(
        habs=len(snapshot.habs) - sum(habs.values()),
        fleets=len(snapshot.fleets) - sum(fleets.values()),
        ships=len(snapshot.ships) - sum(ships.values()),
    )
    return factions, unattributed


def _milestones(reader: _Reader, singleton: EntityState | None) -> tuple[Milestone, ...] | Unknown:
    if singleton is None:
        return Unknown()
    record_set = reader.lookup.record_set(singleton.ref.entity_id, MILESTONES, Side.AFTER)
    if record_set is None:
        return Unknown()
    if isinstance(record_set.entries, Unknown):
        return record_set.entries
    return tuple(
        Milestone(entry.key, reader.resolved(entry.value))
        for entry in sorted(record_set.entries, key=lambda entry: entry.index)
        if isinstance(entry, KeyedEntry)
    )


def _world(reader: _Reader, nations: tuple[NationSituation, ...]) -> WorldSituation:
    snapshot = reader.snapshot
    singleton = snapshot.global_values[0] if len(snapshot.global_values) == 1 else None

    def counters(names: Iterable[str]) -> tuple[tuple[str, Observed], ...]:
        return tuple((name, singleton.get(name) if singleton is not None else Unknown()) for name in names)

    population = (
        reader.population(region.ref.entity_id for region in snapshot.regions) if snapshot.regions else Unknown()
    )
    unknown_regions = next((nation.regions for nation in nations if isinstance(nation.regions, Unknown)), None)
    return WorldSituation(
        nations=len(snapshot.nations),
        nations_with_regions=unknown_regions or sum(nation.regions != 0 for nation in nations),
        population=population,
        finished_technologies=_count(snapshot.research.finished_techs_names),
        milestones=_milestones(reader, singleton),
        nuclear=counters(NUCLEAR_COUNTERS),
        climate=counters(CLIMATE_COUNTERS),
    )


def build_situation(snapshot: SaveSnapshot) -> SituationReport:
    """The situation report of one snapshot; the same snapshot always gives an equal report."""
    reader = _Reader(snapshot)
    parties = _war_parties(snapshot)
    factions, unattributed = _factions(reader)
    nations = tuple(_nation(reader, state, parties.get(state.ref.entity_id, [])) for state in snapshot.nations)
    report = SituationReport(
        date=snapshot.date,
        player_faction_name=snapshot.campaign.player_faction_name,
        nations=nations,
        federations=tuple(
            FederationSituation(state.ref, state.get("federationName"), reader.resolved(state.get("members")))
            for state in snapshot.federations
        ),
        wars=tuple(_war(reader, state) for state in snapshot.wars),
        factions=factions,
        unattributed=unattributed,
        world=_world(reader, nations),
    )
    logger.debug(
        "situation built %s",
        fields(
            nations=len(report.nations),
            federations=len(report.federations),
            wars=len(report.wars),
            factions=len(report.factions),
            unattributed=unattributed.habs + unattributed.fleets + unattributed.ships,
        ),
    )
    return report
